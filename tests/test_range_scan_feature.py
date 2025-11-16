"""
Test suite for Range Scan feature implementation.

This suite tests the complete range scan feature across all layers:
1. B-Tree range_scan method
2. IndexManager range_scan_index method
3. Optimizer range predicate detection
4. IndexRangeScanOperator
5. End-to-end range query execution

Author: AlpacaDB Team
Date: 2024
"""

import pytest
import os
import shutil
from pathlib import Path
from src.storage.catalog import Catalog
from src.storage.table_manager import TableManager
from src.storage.indexing.index_manager import IndexManager
from src.storage.indexing.btree import BTree
from src.storage.page_manager import PageManager
from src.optimizer.optimizer import QueryOptimizer
from src.executor.executor import QueryExecutor
from src.executor.operators import IndexRangeScanOperator
from src.query.parser import Parser
from src.query.lexer import Lexer


@pytest.fixture
def test_db_dir(tmp_path):
    """Create a temporary database directory."""
    db_dir = tmp_path / "test_range_scan_db"
    db_dir.mkdir()
    yield str(db_dir)
    # Cleanup
    if db_dir.exists():
        shutil.rmtree(db_dir)


@pytest.fixture
def page_manager(tmp_path):
    """Create a page manager instance."""
    db_file = tmp_path / "test.db"
    pm = PageManager(str(db_file))
    yield pm
    pm.close()
    if db_file.exists():
        os.remove(db_file)


@pytest.fixture
def catalog(page_manager):
    """Create a catalog instance."""
    return Catalog(page_manager)


@pytest.fixture
def table_manager(page_manager, catalog, index_manager):
    """Create a table manager instance."""
    tm = TableManager(page_manager, catalog)
    tm.index_manager = index_manager
    return tm


@pytest.fixture
def index_manager(catalog, page_manager):
    """Create an index manager instance."""
    return IndexManager(catalog, page_manager)


@pytest.fixture
def executor(catalog, table_manager, index_manager):
    """Create an executor with optimizer."""
    from src.query.lexer import Lexer
    from src.query.parser import Parser
    
    class ExecutorWrapper:
        def __init__(self, table_manager, catalog, index_manager):
            self.executor = QueryExecutor(table_manager, catalog, index_manager)
            
        def execute(self, sql):
            lexer = Lexer(sql)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            ast = parser.parse()
            return self.executor.execute(ast)
            
        @property
        def last_plan(self):
            return self.executor.last_plan
    
    return ExecutorWrapper(table_manager, catalog, index_manager)


class TestBTreeRangeScan:
    """Test B-Tree range_scan method directly."""

    def test_range_scan_basic(self, page_manager):
        """Test basic range scan on B-Tree."""
        btree = BTree(page_manager, order=4)
        
        # Insert values 1-10 with corresponding page_id/row_id
        for i in range(1, 11):
            btree.insert(i, (i, i))  # Using integers for page_id and row_id
        
        # Range scan [3, 7]
        results = btree.range_scan(3, 7, min_inclusive=True, max_inclusive=True)
        
        # Should return 5 results (keys 3-7)
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        
        # Check that we got the right values (page_id, row_id pairs)
        expected_values = [(i, i) for i in range(3, 8)]  # 3, 4, 5, 6, 7
        assert results == expected_values, f"Expected {expected_values}, got {results}"

    def test_range_scan_exclusive(self, page_manager):
        """Test range scan with exclusive bounds."""
        btree = BTree(page_manager, order=4)
        
        # Insert values 1-10
        for i in range(1, 11):
            btree.insert(i, (i, i))
        
        # Range scan (3, 7) - exclusive
        results = btree.range_scan(3, 7, min_inclusive=False, max_inclusive=False)
        
        # Should return 3 results (keys 4, 5, 6)
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        expected_values = [(i, i) for i in range(4, 7)]  # 4, 5, 6
        assert results == expected_values

    def test_range_scan_min_only(self, page_manager):
        """Test range scan with only minimum bound."""
        btree = BTree(page_manager, order=4)
        
        # Insert values 1-10
        for i in range(1, 11):
            btree.insert(i, (i, i))
        
        # Range scan [5, infinity)
        results = btree.range_scan(5, None, min_inclusive=True, max_inclusive=True)
        
        # Should return 6 results (keys 5-10)
        assert len(results) == 6, f"Expected 6 results, got {len(results)}"
        expected_values = [(i, i) for i in range(5, 11)]  # 5-10
        assert results == expected_values

    def test_range_scan_max_only(self, page_manager):
        """Test range scan with only maximum bound."""
        btree = BTree(page_manager, order=4)
        
        # Insert values 1-10
        for i in range(1, 11):
            btree.insert(i, (i, i))
        
        # Range scan (-infinity, 5]
        results = btree.range_scan(None, 5, min_inclusive=True, max_inclusive=True)
        
        # Should return 5 results (keys 1-5)
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        expected_values = [(i, i) for i in range(1, 6)]  # 1-5
        assert results == expected_values

    def test_range_scan_empty_range(self, page_manager):
        """Test range scan with no matching values."""
        btree = BTree(page_manager, order=4)
        
        # Insert values 1-10
        for i in range(1, 11):
            btree.insert(i, (f"page_{i}", i))
        
        # Range scan [20, 30] - no values in tree
        results = btree.range_scan(20, 30, min_inclusive=True, max_inclusive=True)
        assert results == [], f"Expected empty list, got {results}"

    def test_range_scan_duplicates(self, page_manager):
        """Test range scan with duplicate keys."""
        btree = BTree(page_manager, order=4)
        
        # Insert duplicate keys
        btree.insert(5, ("page_1", 1))
        btree.insert(5, ("page_2", 2))
        btree.insert(7, ("page_3", 3))
        btree.insert(7, ("page_4", 4))
        btree.insert(9, ("page_5", 5))
        
        # Range scan [5, 7]
        results = btree.range_scan(5, 7, min_inclusive=True, max_inclusive=True)
        assert len(results) == 4, f"Expected 4 results (2 x key=5, 2 x key=7), got {len(results)}"


class TestIndexManagerRangeScan:
    """Test IndexManager range_scan_index method."""

    def test_index_manager_range_scan(self, catalog, table_manager, index_manager):
        """Test range scan through IndexManager."""
        # Create table
        catalog.create_table("users", [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "age", "type": "int", "nullable": False},
        ])
        
        # Insert data
        for i in range(1, 11):
            table_manager.insert_row("users", [i, i * 10])
        
        # Create index on age
        index_manager.create_index("age_idx", "users", "age", table_manager)
        
        # Range scan [30, 70]
        results = index_manager.range_scan_index(
            "age_idx",
            min_key=30, max_key=70,
            min_inclusive=True, max_inclusive=True
        )
        
        # Should return (page_id, row_id) tuples for ages 30, 40, 50, 60, 70
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"


class TestOptimizerRangeDetection:
    """Test optimizer's ability to detect range predicates."""

    def test_optimizer_detects_greater_than(self, catalog, index_manager):
        """Test optimizer detects > operator."""
        # Create table with index
        catalog.create_table("products", [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "price", "type": "int", "nullable": False},
        ])
        index_manager.create_index("price_idx", "products", "price")
        
        # Parse query with >
        query = "SELECT * FROM products WHERE price > 100"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        # Optimize
        optimizer = QueryOptimizer(catalog, index_manager)
        plan = optimizer.optimize(ast)
        
        assert plan.plan_type == 'IndexRangeScan', f"Expected IndexRangeScan, got {plan.plan_type}"
        assert plan.range_min == 100
        assert plan.range_min_inclusive is False
        assert plan.range_max is None

    def test_optimizer_detects_less_than_or_equal(self, catalog, index_manager):
        """Test optimizer detects <= operator."""
        catalog.create_table("products", [
            {"name": "id", "type": "int", "nullable": False},
            {"name": "price", "type": "int", "nullable": False},
        ])
        index_manager.create_index("price_idx", "products", "price")
        
        query = "SELECT * FROM products WHERE price <= 500"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        optimizer = QueryOptimizer(catalog, index_manager)
        plan = optimizer.optimize(ast)
        
        assert plan.plan_type == 'IndexRangeScan'
        assert plan.range_max == 500
        assert plan.range_max_inclusive is True
        assert plan.range_min is None

    def test_optimizer_detects_between(self, test_db_dir, catalog, index_manager):
        """Test optimizer detects BETWEEN operator (if implemented)."""
        # Note: BETWEEN may need to be broken down into >= AND <=
        # This is a placeholder for future implementation
        pass


class TestIndexRangeScanOperator:
    """Test IndexRangeScanOperator directly."""

    def test_operator_basic_range(self, catalog, table_manager, index_manager):
        """Test IndexRangeScanOperator execution."""
        # Create table
        catalog.create_table("employees", [
            {"name": "id", "type": "INT", "nullable": False},
            {"name": "salary", "type": "INT", "nullable": False},
            {"name": "name", "type": "STRING", "nullable": False},
        ])
        
        # Insert data
        table_manager.insert_row("employees", [1, 30000, "Alice"])
        table_manager.insert_row("employees", [2, 45000, "Bob"])
        table_manager.insert_row("employees", [3, 60000, "Charlie"])
        table_manager.insert_row("employees", [4, 75000, "David"])
        table_manager.insert_row("employees", [5, 90000, "Eve"])
        
        # Create index on salary
        index_manager.create_index("salary_idx", "employees", "salary", table_manager)
        
        # Create operator for range [45000, 75000]
        operator = IndexRangeScanOperator(
            table_manager=table_manager,
            index_manager=index_manager,
            table_name="employees",
            index_name="salary_idx",
            range_min=45000,
            range_max=75000,
            min_inclusive=True,
            max_inclusive=True,
            column_names=["id", "salary", "name"]
        )
        
        operator.open()
        results = []
        while True:
            row = operator.next()
            if row is None:
                break
            results.append(row)
        operator.close()
        
        # Should return Bob, Charlie, David
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        salaries = [row[1] for row in results]
        assert 45000 in salaries and 60000 in salaries and 75000 in salaries


class TestEndToEndRangeQueries:
    """Test complete range query execution through executor."""

    def test_e2e_greater_than_query(self, executor):
        """Test end-to-end execution of > query."""
        # Create table
        executor.execute("CREATE TABLE students (id INT, score INT, name STRING)")
        
        # Insert data
        executor.execute("INSERT INTO students VALUES (1, 65, 'Alice')")
        executor.execute("INSERT INTO students VALUES (2, 75, 'Bob')")
        executor.execute("INSERT INTO students VALUES (3, 85, 'Charlie')")
        executor.execute("INSERT INTO students VALUES (4, 95, 'David')")
        
        # Create index
        executor.execute("CREATE INDEX score_idx ON students(score)")
        
        # Execute range query
        results, _ = executor.execute("SELECT * FROM students WHERE score > 75")
        
        # Should return Charlie (85) and David (95)
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        scores = [row[1] for row in results]
        assert 85 in scores and 95 in scores

    def test_e2e_less_than_or_equal_query(self, executor):
        """Test end-to-end execution of <= query."""
        executor.execute("CREATE TABLE items (id INT, stock INT, name STRING)")
        executor.execute("INSERT INTO items VALUES (1, 5, 'Laptop')")
        executor.execute("INSERT INTO items VALUES (2, 15, 'Mouse')")
        executor.execute("INSERT INTO items VALUES (3, 25, 'Keyboard')")
        executor.execute("INSERT INTO items VALUES (4, 35, 'Monitor')")
        
        executor.execute("CREATE INDEX stock_idx ON items(stock)")
        
        results, _ = executor.execute("SELECT * FROM items WHERE stock <= 15")
        
        # Should return Laptop (5) and Mouse (15)
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"

    def test_e2e_greater_than_or_equal_query(self, executor):
        """Test end-to-end execution of >= query."""
        executor.execute("CREATE TABLE orders (id INT, amount INT, status STRING)")
        executor.execute("INSERT INTO orders VALUES (1, 100, 'pending')")
        executor.execute("INSERT INTO orders VALUES (2, 200, 'shipped')")
        executor.execute("INSERT INTO orders VALUES (3, 300, 'delivered')")
        
        executor.execute("CREATE INDEX amount_idx ON orders(amount)")
        
        results, _ = executor.execute("SELECT * FROM orders WHERE amount >= 200")
        
        # Should return orders with amount 200 and 300
        assert len(results) == 2
        amounts = [row[1] for row in results]
        assert 200 in amounts and 300 in amounts

    def test_e2e_range_with_strings(self, executor):
        """Test range queries work with string comparisons."""
        executor.execute("CREATE TABLE books (id INT, title STRING, rating INT)")
        executor.execute("INSERT INTO books VALUES (1, 'Alice', 4)")
        executor.execute("INSERT INTO books VALUES (2, 'Bob', 5)")
        executor.execute("INSERT INTO books VALUES (3, 'Charlie', 3)")
        executor.execute("INSERT INTO books VALUES (4, 'David', 4)")
        
        executor.execute("CREATE INDEX title_idx ON books(title)")
        
        results, _ = executor.execute("SELECT * FROM books WHERE title > 'Bob'")
        
        # Should return Charlie and David (alphabetically > 'Bob')
        assert len(results) == 2

    def test_plan_type_verification(self, executor):
        """Verify that optimizer actually uses IndexRangeScan plan."""
        executor.execute("CREATE TABLE test_table (id INT, value INT)")
        executor.execute("INSERT INTO test_table VALUES (1, 10)")
        executor.execute("INSERT INTO test_table VALUES (2, 20)")
        executor.execute("INSERT INTO test_table VALUES (3, 30)")
        
        executor.execute("CREATE INDEX value_idx ON test_table(value)")
        
        # Execute range query
        executor.execute("SELECT * FROM test_table WHERE value > 15")
        
        # Check that the plan type was IndexRangeScan
        assert executor.last_plan == 'IndexRangeScan', \
            f"Expected plan type 'IndexRangeScan', got '{executor.last_plan}'"


class TestBTreeDelete:
    """Test B-Tree delete functionality."""

    def test_delete_leaf_node(self, page_manager):
        """Test deleting from a leaf node."""
        btree = BTree(page_manager, order=4)
        
        # Insert values
        for i in [5, 10, 15, 20, 25]:
            btree.insert(i, (f"page_{i}", i))
        
        # Delete a value
        btree.delete(15, (f"page_15", 15))
        
        # Search should return None
        result = btree.search(15)
        assert result is None or 15 not in [k for k, _ in result], \
            f"Key 15 should be deleted, but search returned {result}"

    def test_delete_with_duplicates(self, page_manager):
        """Test deleting specific value when duplicates exist."""
        btree = BTree(page_manager, order=4)
        
        # Insert duplicate keys
        btree.insert(10, ("page_1", 1))
        btree.insert(10, ("page_2", 2))
        btree.insert(10, ("page_3", 3))
        
        # Delete one specific value
        btree.delete(10, ("page_2", 2))
        
        # Should still have 2 values for key 10
        results = btree.search(10)
        assert len(results) == 2, f"Expected 2 remaining values, got {len(results)}"

    def test_delete_nonexistent(self, page_manager):
        """Test deleting non-existent key."""
        btree = BTree(page_manager, order=4)
        
        # Insert values
        btree.insert(5, ("page_5", 5))
        btree.insert(10, ("page_10", 10))
        
        # Try to delete non-existent key (should not crash)
        btree.delete(999, ("page_999", 999))
        
        # Original values should still be there
        assert btree.search(5) is not None
        assert btree.search(10) is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
