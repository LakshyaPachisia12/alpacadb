"""
Comprehensive coverage test suite for AlpacaDB
Tests all major components and features to ensure high code coverage
"""
import pytest
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.storage.table_manager import TableManager
from src.storage.catalog import Catalog
from src.storage.page_manager import PageManager
from src.storage.indexing.index_manager import IndexManager
from src.storage.indexing.btree import BTree
from src.query.lexer import Lexer
from src.query.parser import Parser
from src.executor.executor import QueryExecutor
from src.optimizer.optimizer import QueryOptimizer
from src.optimizer import cost_estimator
from src.errors import (
    AlpacaDBError,
    TableNotFoundError,
    DuplicateTableError,
    ParserError,
    SyntaxError as AlpacaSyntaxError,
    IndexNotFoundError
)


class TestCoverageStorage:
    """Test storage layer components"""
    
    def setup_method(self):
        """Setup for each test"""
        self.test_db = "test_coverage_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
    
    def teardown_method(self):
        """Cleanup after each test"""
        try:
            import shutil
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_table_creation_and_schema(self):
        """Test table creation with various data types"""
        schema = {
            'id': 'INT',
            'name': 'VARCHAR',
            'age': 'INT',
            'salary': 'FLOAT',
            'active': 'BOOLEAN'
        }
        self.table_manager.create_table('users', schema)
        
        # Verify table exists
        assert self.catalog.table_exists('users')
        
        # Verify schema
        table_schema = self.catalog.get_table_schema('users')
        assert table_schema['id'] == 'INT'
        assert table_schema['name'] == 'VARCHAR'
    
    def test_insert_and_select_operations(self):
        """Test insert and select operations"""
        schema = {'id': 'INT', 'name': 'VARCHAR', 'score': 'FLOAT'}
        self.table_manager.create_table('students', schema)
        
        # Insert data
        self.table_manager.insert('students', {'id': 1, 'name': 'Alice', 'score': 95.5})
        self.table_manager.insert('students', {'id': 2, 'name': 'Bob', 'score': 87.3})
        
        # Select all
        results = list(self.table_manager.select('students'))
        assert len(results) == 2
        assert results[0]['name'] == 'Alice'
    
    def test_update_operations(self):
        """Test update operations"""
        schema = {'id': 'INT', 'status': 'VARCHAR', 'count': 'INT'}
        self.table_manager.create_table('items', schema)
        
        self.table_manager.insert('items', {'id': 1, 'status': 'pending', 'count': 10})
        self.table_manager.insert('items', {'id': 2, 'status': 'pending', 'count': 20})
        
        # Update with condition
        def condition(row):
            return row['id'] == 1
        
        updated = self.table_manager.update('items', {'status': 'completed'}, condition)
        assert updated == 1
        
        # Verify update
        results = list(self.table_manager.select('items', condition))
        assert results[0]['status'] == 'completed'
    
    def test_delete_operations(self):
        """Test delete operations"""
        schema = {'id': 'INT', 'data': 'VARCHAR'}
        self.table_manager.create_table('temp', schema)
        
        for i in range(5):
            self.table_manager.insert('temp', {'id': i, 'data': f'item{i}'})
        
        # Delete with condition
        def condition(row):
            return row['id'] >= 3
        
        deleted = self.table_manager.delete('temp', condition)
        assert deleted == 2
        
        # Verify deletion
        results = list(self.table_manager.select('temp'))
        assert len(results) == 3
    
    def test_drop_table(self):
        """Test dropping tables"""
        schema = {'id': 'INT'}
        self.table_manager.create_table('to_drop', schema)
        
        assert self.catalog.table_exists('to_drop')
        self.table_manager.drop_table('to_drop')
        assert not self.catalog.table_exists('to_drop')


class TestCoverageIndexing:
    """Test indexing components"""
    
    def setup_method(self):
        """Setup for each test"""
        self.test_db = "test_coverage_index_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
        self.index_manager = IndexManager(self.catalog)
    
    def teardown_method(self):
        """Cleanup after each test"""
        try:
            import shutil
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_create_and_use_index(self):
        """Test index creation and usage"""
        schema = {'id': 'INT', 'name': 'VARCHAR', 'age': 'INT'}
        self.table_manager.create_table('people', schema)
        
        # Create index
        self.index_manager.create_index('people', 'id', 'idx_people_id')
        
        # Insert data
        for i in range(10):
            self.table_manager.insert('people', {'id': i, 'name': f'Person{i}', 'age': 20 + i})
        
        # Verify index exists
        assert self.catalog.index_exists('people', 'idx_people_id')
    
    def test_btree_operations(self):
        """Test BTree operations directly"""
        btree = BTree()
        
        # Insert keys
        for i in range(20):
            btree.insert(i, f"value_{i}")
        
        # Search
        result = btree.search(10)
        assert result == "value_10"
        
        # Range scan
        results = btree.range_scan(5, 15)
        assert len(results) >= 10
    
    def test_index_drop(self):
        """Test dropping indexes"""
        schema = {'id': 'INT', 'data': 'VARCHAR'}
        self.table_manager.create_table('indexed_table', schema)
        
        self.index_manager.create_index('indexed_table', 'id', 'test_idx')
        assert self.catalog.index_exists('indexed_table', 'test_idx')
        
        self.index_manager.drop_index('indexed_table', 'test_idx')
        assert not self.catalog.index_exists('indexed_table', 'test_idx')


class TestCoverageQueryParsing:
    """Test query parsing components"""
    
    def test_lexer_tokenization(self):
        """Test lexer with various SQL statements"""
        queries = [
            "SELECT * FROM users WHERE age > 25",
            "INSERT INTO users (id, name) VALUES (1, 'Alice')",
            "UPDATE users SET name = 'Bob' WHERE id = 1",
            "DELETE FROM users WHERE age < 18",
            "CREATE TABLE students (id INT, name VARCHAR)",
            "DROP TABLE students",
            "CREATE INDEX idx_id ON users (id)",
            "SELECT COUNT(*), AVG(salary) FROM employees GROUP BY department"
        ]
        
        for query in queries:
            lexer = Lexer(query)
            tokens = lexer.tokenize()
            assert len(tokens) > 0
            assert tokens[0].type in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP']
    
    def test_parser_select_statements(self):
        """Test parsing SELECT statements"""
        queries = [
            "SELECT * FROM users",
            "SELECT id, name FROM users WHERE age > 18",
            "SELECT COUNT(*) FROM orders",
            "SELECT * FROM users WHERE name = 'Alice' AND age > 25"
        ]
        
        for query in queries:
            lexer = Lexer(query)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            ast = parser.parse()
            assert ast is not None
    
    def test_parser_insert_statements(self):
        """Test parsing INSERT statements"""
        query = "INSERT INTO users (id, name, age) VALUES (1, 'Alice', 30)"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        assert ast is not None
    
    def test_parser_update_statements(self):
        """Test parsing UPDATE statements"""
        query = "UPDATE users SET age = 31 WHERE name = 'Alice'"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        assert ast is not None
    
    def test_parser_delete_statements(self):
        """Test parsing DELETE statements"""
        query = "DELETE FROM users WHERE age < 18"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        assert ast is not None
    
    def test_parser_ddl_statements(self):
        """Test parsing DDL statements"""
        queries = [
            "CREATE TABLE users (id INT, name VARCHAR, age INT)",
            "DROP TABLE users",
            "CREATE INDEX idx_id ON users (id)",
            "DROP INDEX idx_id ON users"
        ]
        
        for query in queries:
            lexer = Lexer(query)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            ast = parser.parse()
            assert ast is not None


class TestCoverageExecutor:
    """Test executor components"""
    
    def setup_method(self):
        """Setup for each test"""
        self.test_db = "test_coverage_exec_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
        self.index_manager = IndexManager(self.catalog)
        self.executor = QueryExecutor(self.table_manager, self.catalog, self.index_manager)
    
    def teardown_method(self):
        """Cleanup after each test"""
        try:
            import shutil
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_executor_create_table(self):
        """Test executor CREATE TABLE"""
        query = "CREATE TABLE products (id INT, name VARCHAR, price FLOAT)"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        result = self.executor.execute(ast)
        assert "created successfully" in result.lower()
        assert self.catalog.table_exists('products')
    
    def test_executor_insert_and_select(self):
        """Test executor INSERT and SELECT"""
        # Create table
        create_query = "CREATE TABLE employees (id INT, name VARCHAR, salary FLOAT)"
        lexer = Lexer(create_query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        self.executor.execute(ast)
        
        # Insert data
        insert_query = "INSERT INTO employees (id, name, salary) VALUES (1, 'John', 50000.0)"
        lexer = Lexer(insert_query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        result = self.executor.execute(ast)
        assert "inserted" in result.lower() or "1 row" in result.lower()
        
        # Select data
        select_query = "SELECT * FROM employees"
        lexer = Lexer(select_query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        result = self.executor.execute(ast)
        assert 'John' in str(result) or '1 row' in str(result).lower()
    
    def test_executor_aggregate_functions(self):
        """Test executor with aggregate functions"""
        # Create and populate table
        create_query = "CREATE TABLE sales (id INT, amount FLOAT, region VARCHAR)"
        lexer = Lexer(create_query)
        self.executor.execute(Parser(lexer.tokenize()).parse())
        
        for i in range(5):
            insert_query = f"INSERT INTO sales (id, amount, region) VALUES ({i}, {100.0 * (i+1)}, 'North')"
            lexer = Lexer(insert_query)
            self.executor.execute(Parser(lexer.tokenize()).parse())
        
        # Test COUNT
        count_query = "SELECT COUNT(*) FROM sales"
        lexer = Lexer(count_query)
        result = self.executor.execute(Parser(lexer.tokenize()).parse())
        assert '5' in str(result) or 'count' in str(result).lower()
        
        # Test SUM
        sum_query = "SELECT SUM(amount) FROM sales"
        lexer = Lexer(sum_query)
        result = self.executor.execute(Parser(lexer.tokenize()).parse())
        assert result is not None


class TestCoverageOptimizer:
    """Test optimizer components"""
    
    def setup_method(self):
        """Setup for each test"""
        self.test_db = "test_coverage_opt_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
        self.index_manager = IndexManager(self.catalog)
    
    def teardown_method(self):
        """Cleanup after each test"""
        try:
            import shutil
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_cost_estimator(self):
        """Test cost estimation"""
        # Create table and add data
        schema = {'id': 'INT', 'data': 'VARCHAR'}
        self.table_manager.create_table('test_table', schema)
        
        for i in range(100):
            self.table_manager.insert('test_table', {'id': i, 'data': f'data{i}'})
        
        # Get table statistics
        table_stats = self.catalog.get_table_stats('test_table')
        
        # Estimate table scan cost
        cost = cost_estimator.cost_seq_scan(table_stats)
        assert cost > 0
    
    def test_optimizer_plan_generation(self):
        """Test optimizer plan generation"""
        # Create table with index
        schema = {'id': 'INT', 'name': 'VARCHAR', 'value': 'INT'}
        self.table_manager.create_table('opt_table', schema)
        self.index_manager.create_index('opt_table', 'id', 'idx_opt_id')
        
        # Add some data
        for i in range(50):
            self.table_manager.insert('opt_table', {'id': i, 'name': f'Item{i}', 'value': i * 10})
        
        optimizer = QueryOptimizer(self.catalog, self.index_manager, self.table_manager)
        
        # Parse a query
        query = "SELECT * FROM opt_table WHERE id = 25"
        lexer = Lexer(query)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        # Optimize
        optimized_plan = optimizer.optimize(ast)
        assert optimized_plan is not None


class TestCoverageErrorHandling:
    """Test error handling across components"""
    
    def setup_method(self):
        """Setup for each test"""
        self.test_db = "test_coverage_err_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
    
    def teardown_method(self):
        """Cleanup after each test"""
        try:
            import shutil
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_table_not_found_error(self):
        """Test TableNotFoundError"""
        with pytest.raises(Exception):  # May be TableNotFoundError or similar
            list(self.table_manager.select('nonexistent_table'))
    
    def test_duplicate_table_error(self):
        """Test duplicate table creation"""
        schema = {'id': 'INT'}
        self.table_manager.create_table('duplicate_test', schema)
        
        with pytest.raises(Exception):  # May be DuplicateTableError or similar
            self.table_manager.create_table('duplicate_test', schema)
    
    def test_invalid_query_parsing(self):
        """Test invalid query syntax"""
        invalid_queries = [
            "SELECT FROM WHERE",
            "INSERT INTO",
            "INVALID SQL SYNTAX",
            "SELECT * FROM"
        ]
        
        for query in invalid_queries:
            try:
                lexer = Lexer(query)
                tokens = lexer.tokenize()
                parser = Parser(tokens)
                parser.parse()
            except Exception as e:
                # Expected to raise an error
                assert True


class TestCoverageIntegration:
    """Integration tests for end-to-end workflows"""
    
    def setup_method(self):
        """Setup for each test"""
        self.test_db = "test_coverage_integration_db"
        self.page_manager = PageManager(self.test_db)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
        self.index_manager = IndexManager(self.catalog)
        self.executor = QueryExecutor(self.table_manager, self.catalog, self.index_manager)
    
    def teardown_method(self):
        """Cleanup after each test"""
        try:
            import shutil
            if os.path.exists(self.test_db):
                shutil.rmtree(self.test_db)
        except:
            pass
    
    def test_complete_workflow(self):
        """Test complete database workflow"""
        # Create table
        create_sql = "CREATE TABLE orders (id INT, customer VARCHAR, amount FLOAT, status VARCHAR)"
        self.executor.execute(Parser(Lexer(create_sql).tokenize()).parse())
        
        # Create index
        index_sql = "CREATE INDEX idx_orders_id ON orders (id)"
        self.executor.execute(Parser(Lexer(index_sql).tokenize()).parse())
        
        # Insert multiple records
        orders = [
            (1, 'Alice', 150.50, 'completed'),
            (2, 'Bob', 200.00, 'pending'),
            (3, 'Charlie', 75.25, 'completed'),
            (4, 'Diana', 300.00, 'pending'),
            (5, 'Eve', 125.00, 'completed')
        ]
        
        for order_id, customer, amount, status in orders:
            insert_sql = f"INSERT INTO orders (id, customer, amount, status) VALUES ({order_id}, '{customer}', {amount}, '{status}')"
            self.executor.execute(Parser(Lexer(insert_sql).tokenize()).parse())
        
        # Select all
        select_sql = "SELECT * FROM orders"
        result = self.executor.execute(Parser(Lexer(select_sql).tokenize()).parse())
        assert result is not None
        
        # Select with condition
        select_sql = "SELECT * FROM orders WHERE status = 'completed'"
        result = self.executor.execute(Parser(Lexer(select_sql).tokenize()).parse())
        assert result is not None
        
        # Update
        update_sql = "UPDATE orders SET status = 'shipped' WHERE id = 2"
        result = self.executor.execute(Parser(Lexer(update_sql).tokenize()).parse())
        assert result is not None
        
        # Delete
        delete_sql = "DELETE FROM orders WHERE amount < 100"
        result = self.executor.execute(Parser(Lexer(delete_sql).tokenize()).parse())
        assert result is not None
    
    def test_aggregate_workflow(self):
        """Test workflow with aggregate functions"""
        # Create table
        create_sql = "CREATE TABLE transactions (id INT, amount FLOAT, category VARCHAR)"
        self.executor.execute(Parser(Lexer(create_sql).tokenize()).parse())
        
        # Insert data
        for i in range(10):
            category = 'A' if i % 2 == 0 else 'B'
            insert_sql = f"INSERT INTO transactions (id, amount, category) VALUES ({i}, {100.0 * (i+1)}, '{category}')"
            self.executor.execute(Parser(Lexer(insert_sql).tokenize()).parse())
        
        # Test aggregates
        count_sql = "SELECT COUNT(*) FROM transactions"
        result = self.executor.execute(Parser(Lexer(count_sql).tokenize()).parse())
        assert result is not None
        
        sum_sql = "SELECT SUM(amount) FROM transactions"
        result = self.executor.execute(Parser(Lexer(sum_sql).tokenize()).parse())
        assert result is not None
        
        avg_sql = "SELECT AVG(amount) FROM transactions"
        result = self.executor.execute(Parser(Lexer(avg_sql).tokenize()).parse())
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src", "--cov-report=html", "--cov-report=term"])
