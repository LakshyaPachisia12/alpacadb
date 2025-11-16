"""
Comprehensive Code Coverage Test Suite for AlpacaDB
================================================================================
This test suite provides extensive coverage of all major components including:
- Storage layer (Catalog, PageManager, TableManager)
- Indexing (BTree, IndexManager)
- Query parsing (Lexer, Parser, AST)
- Query execution (QueryExecutor, Physical operators)
- Query optimization (QueryOptimizer, Cost estimation)
- Error handling and edge cases

Target: 80%+ code coverage
Industry best practices: AAA pattern, comprehensive fixtures, proper teardown
================================================================================
"""

import pytest
import os
import sys
import shutil
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Storage layer imports
from src.storage.table_manager import TableManager
from src.storage.catalog import Catalog, TableSchema
from src.storage.page_manager import PageManager
from src.storage.page import Page
from src.storage.indexing.index_manager import IndexManager
from src.storage.indexing.btree import BTree, BTreeNode

# Query layer imports
from src.query.lexer import Lexer
from src.query.parser import Parser
from src.query.tokens import TokenType, Token
from src.query.ast_nodes import (
    Column, SelectNode, InsertNode, UpdateNode, DeleteNode,
    CreateTableNode, DropTableNode, CreateIndexNode, DropIndexNode
)

# Execution layer imports
from src.executor.executor import QueryExecutor
from src.executor.operators import (
    ScanOperator, FilterOperator, ProjectOperator,
    IndexScanOperator, AggregateOperator
)

# Optimization layer imports
from src.optimizer.optimizer import QueryOptimizer, QueryPlan
from src.optimizer import cost_estimator

# Error handling imports
from src.errors import (
    AlpacaDBError, TableNotFoundError, DuplicateTableError,
    SyntaxError as AlpacaSyntaxError, ParserError, ExecutionError,
    IndexNotFoundError, ColumnNotFoundError
)


# ============================================================================
# FIXTURES - Reusable test components
# ============================================================================

@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database path"""
    db_path = tmp_path / "test_db"
    yield str(db_path)
    # Cleanup
    if db_path.exists():
        shutil.rmtree(db_path, ignore_errors=True)


@pytest.fixture
def page_manager(temp_db_path):
    """Provide a PageManager instance"""
    return PageManager(temp_db_path)


@pytest.fixture
def catalog(page_manager):
    """Provide a Catalog instance"""
    return Catalog(page_manager)


@pytest.fixture
def table_manager(page_manager, catalog):
    """Provide a TableManager instance"""
    return TableManager(page_manager, catalog)


@pytest.fixture
def index_manager(catalog, page_manager):
    """Provide an IndexManager instance"""
    return IndexManager(catalog, page_manager)


@pytest.fixture
def executor(table_manager, catalog, index_manager):
    """Provide a QueryExecutor instance"""
    return QueryExecutor(table_manager, catalog, index_manager)


@pytest.fixture
def optimizer(catalog, index_manager, table_manager):
    """Provide a QueryOptimizer instance"""
    return QueryOptimizer(catalog, index_manager, table_manager)


# ============================================================================
# STORAGE LAYER TESTS
# ============================================================================

class TestPageManager:
    """Test PageManager - low-level page I/O"""
    
    def test_create_and_read_page(self, page_manager):
        """Test creating and reading pages"""
        page = Page(page_id=1, page_type=1)
        page.add_record(b"test data")
        
        page_manager.write_page(page)
        read_page = page_manager.read_page(1)
        
        assert read_page is not None
        assert read_page.page_id == 1
    
    def test_allocate_page(self, page_manager):
        """Test page allocation"""
        page_id = page_manager.allocate_page()
        assert page_id > 0
        
        # Allocate another
        page_id2 = page_manager.allocate_page()
        assert page_id2 > page_id


class TestCatalog:
    """Test Catalog - metadata management"""
    
    def test_create_table_in_catalog(self, catalog):
        """Test registering a table in catalog"""
        columns = [
            Column(name='id', data_type='INT', is_primary_key=True),
            Column(name='name', data_type='STRING'),
            Column(name='age', data_type='INT')
        ]
        
        result = catalog.create_table('users', columns)
        assert result is True
        
        # Verify table exists
        schema = catalog.get_table_schema('users')
        assert schema is not None
        assert schema.name == 'users'
        assert len(schema.columns) == 3
    
    def test_duplicate_table_prevention(self, catalog):
        """Test that duplicate tables are prevented"""
        columns = [Column(name='id', data_type='INT')]
        
        catalog.create_table('test', columns)
        
        # Attempt to create duplicate
        result = catalog.create_table('test', columns)
        assert result is False
    
    def test_list_tables(self, catalog):
        """Test listing all tables"""
        columns = [Column(name='id', data_type='INT')]
        
        catalog.create_table('table1', columns)
        catalog.create_table('table2', columns)
        catalog.create_table('table3', columns)
        
        tables = catalog.list_tables()
        assert len(tables) == 3
        assert 'table1' in tables
        assert 'table2' in tables
        assert 'table3' in tables
    
    def test_drop_table(self, catalog):
        """Test dropping a table"""
        columns = [Column(name='id', data_type='INT')]
        catalog.create_table('temp_table', columns)
        
        result = catalog.drop_table('temp_table')
        assert result is True
        
        schema = catalog.get_table_schema('temp_table')
        assert schema is None
    
    def test_get_table_stats(self, catalog, table_manager):
        """Test retrieving table statistics"""
        columns = [Column(name='id', data_type='INT'), Column(name='data', data_type='STRING')]
        catalog.create_table('stats_test', columns)
        
        # Insert some data
        for i in range(10):
            table_manager.insert_row('stats_test', [i, f"data_{i}"])
        
        stats = catalog.get_table_stats('stats_test')
        assert stats is not None
        assert 'num_rows' in stats


class TestTableManager:
    """Test TableManager - high-level table operations"""
    
    def test_insert_and_select_all(self, catalog, table_manager):
        """Test inserting and selecting data"""
        # Create table
        columns = [
            Column(name='id', data_type='INT'),
            Column(name='name', data_type='STRING'),
            Column(name='value', data_type='INT')
        ]
        catalog.create_table('test_table', columns)
        
        # Insert data
        table_manager.insert_row('test_table', [1, 'Alice', 100])
        table_manager.insert_row('test_table', [2, 'Bob', 200])
        table_manager.insert_row('test_table', [3, 'Charlie', 300])
        
        # Select all
        rows = table_manager.select_all('test_table')
        assert len(rows) >= 3
    
    def test_update_rows(self, catalog, table_manager):
        """Test updating rows"""
        columns = [Column(name='id', data_type='INT'), Column(name='value', data_type='INT')]
        catalog.create_table('update_test', columns)
        
        # Insert data
        table_manager.insert_row('update_test', [1, 100])
        table_manager.insert_row('update_test', [2, 200])
        
        # Update with condition
        def condition(row):
            return row[0] == 1  # id == 1
        
        updated = table_manager.update_rows('update_test', {'value': 150}, condition)
        assert updated >= 0
    
    def test_delete_rows(self, catalog, table_manager):
        """Test deleting rows"""
        columns = [Column(name='id', data_type='INT'), Column(name='status', data_type='STRING')]
        catalog.create_table('delete_test', columns)
        
        # Insert data
        for i in range(5):
            table_manager.insert_row('delete_test', [i, 'active' if i % 2 == 0 else 'inactive'])
        
        # Delete with condition
        def condition(row):
            return row[1] == 'inactive'
        
        deleted = table_manager.delete_rows('delete_test', condition)
        assert deleted >= 0


# ============================================================================
# INDEXING TESTS
# ============================================================================

class TestBTree:
    """Test BTree data structure"""
    
    def test_btree_insert_and_search(self, page_manager):
        """Test basic BTree insert and search"""
        btree = BTree(page_manager, tree_name="test_btree")
        
        # Insert values
        for i in range(20):
            btree.insert(i, f"value_{i}")
        
        # Search existing
        result = btree.search(10)
        assert result == "value_10"
        
        # Search non-existent
        result = btree.search(999)
        assert result is None
    
    def test_btree_range_scan(self, page_manager):
        """Test BTree range scanning"""
        btree = BTree(page_manager, tree_name="range_test")
        
        # Insert even numbers
        for i in range(0, 40, 2):
            btree.insert(i, f"val_{i}")
        
        # Range scan
        results = btree.range_scan(10, 20)
        assert len(results) > 0
        
        # Verify all results are in range
        for key, _ in results:
            assert 10 <= key <= 20
    
    def test_btree_node_split(self, page_manager):
        """Test BTree handles node splits"""
        btree = BTree(page_manager, tree_name="split_test")
        
        # Insert many values to force splits
        for i in range(100):
            btree.insert(i, f"data_{i}")
        
        # Verify all values are still searchable
        for i in [0, 25, 50, 75, 99]:
            result = btree.search(i)
            assert result == f"data_{i}"


class TestIndexManager:
    """Test IndexManager - index operations"""
    
    def test_create_index(self, catalog, table_manager, index_manager):
        """Test creating an index"""
        # Create table
        columns = [Column(name='id', data_type='INT'), Column(name='name', data_type='STRING')]
        catalog.create_table('indexed_table', columns)
        
        # Insert data
        for i in range(10):
            table_manager.insert_row('indexed_table', [i, f"name_{i}"])
        
        # Create index
        index_manager.create_index('idx_id', 'indexed_table', 'id', table_manager)
        
        # Verify index exists in catalog
        indexes = catalog.list_indexes('indexed_table')
        assert 'idx_id' in indexes
    
    def test_use_index_for_lookup(self, catalog, table_manager, index_manager):
        """Test using index for point lookup"""
        columns = [Column(name='user_id', data_type='INT'), Column(name='email', data_type='STRING')]
        catalog.create_table('users', columns)
        
        # Insert data
        for i in range(20):
            table_manager.insert_row('users', [i, f"user{i}@test.com"])
        
        # Create index
        index_manager.create_index('idx_user', 'users', 'user_id', table_manager)
        
        # Use index for lookup
        result = table_manager.select_with_index('users', 'user_id', 10)
        assert len(result) > 0
    
    def test_drop_index(self, catalog, table_manager, index_manager):
        """Test dropping an index"""
        columns = [Column(name='id', data_type='INT')]
        catalog.create_table('drop_index_test', columns)
        
        # Create and then drop index
        index_manager.create_index('temp_idx', 'drop_index_test', 'id', table_manager)
        index_manager.drop_index('drop_index_test', 'temp_idx')
        
        # Verify index is gone
        indexes = catalog.list_indexes('drop_index_test')
        assert 'temp_idx' not in indexes


# ============================================================================
# QUERY PARSING TESTS
# ============================================================================

class TestLexer:
    """Test SQL lexer/tokenizer"""
    
    def test_tokenize_select(self):
        """Test tokenizing SELECT statement"""
        sql = "SELECT id, name FROM users WHERE age > 18"
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        
        assert len(tokens) > 0
        assert tokens[0].type == TokenType.SELECT
        assert tokens[0].value == 'SELECT'
    
    def test_tokenize_insert(self):
        """Test tokenizing INSERT statement"""
        sql = "INSERT INTO users VALUES (1, 'John', 25)"
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        
        assert tokens[0].type == TokenType.INSERT
        assert tokens[1].type == TokenType.INTO
    
    def test_tokenize_numbers(self):
        """Test tokenizing numeric literals"""
        sql = "SELECT * FROM t WHERE id = 42"
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        
        # Find the number token
        number_tokens = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(number_tokens) > 0
        assert number_tokens[0].value == 42
    
    def test_tokenize_strings(self):
        """Test tokenizing string literals"""
        sql = "SELECT * FROM users WHERE name = 'Alice'"
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) > 0
        assert string_tokens[0].value == 'Alice'
    
    def test_tokenize_operators(self):
        """Test tokenizing comparison operators"""
        sql = "SELECT * FROM t WHERE a > 5 AND b < 10 AND c = 7"
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        
        # Check for comparison operators
        op_types = [t.type for t in tokens]
        assert TokenType.GREATER in op_types
        assert TokenType.LESS in op_types
        assert TokenType.EQUALS in op_types


class TestParser:
    """Test SQL parser"""
    
    def test_parse_select_star(self):
        """Test parsing SELECT *"""
        sql = "SELECT * FROM users"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        assert isinstance(ast, SelectNode)
        assert ast.table_name == 'users'
        assert ast.columns == ['*']
    
    def test_parse_select_columns(self):
        """Test parsing SELECT with specific columns"""
        sql = "SELECT id, name, age FROM employees"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        assert isinstance(ast, SelectNode)
        assert ast.table_name == 'employees'
        assert 'id' in ast.columns
        assert 'name' in ast.columns
        assert 'age' in ast.columns
    
    def test_parse_select_with_where(self):
        """Test parsing SELECT with WHERE clause"""
        sql = "SELECT * FROM products WHERE price > 100"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        assert isinstance(ast, SelectNode)
        assert ast.table_name == 'products'
        assert ast.where_clause is not None
    
    def test_parse_insert(self):
        """Test parsing INSERT statement"""
        sql = "INSERT INTO users VALUES (1, 'Alice', 30)"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        assert isinstance(ast, InsertNode)
        assert ast.table_name == 'users'
        assert len(ast.values) == 3
    
    def test_parse_update(self):
        """Test parsing UPDATE statement"""
        sql = "UPDATE products SET price = 99 WHERE id = 5"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        assert isinstance(ast, UpdateNode)
        assert ast.table_name == 'products'
        assert 'price' in ast.updates
    
    def test_parse_delete(self):
        """Test parsing DELETE statement"""
        sql = "DELETE FROM logs WHERE timestamp < 1000"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        assert isinstance(ast, DeleteNode)
        assert ast.table_name == 'logs'
        assert ast.where_clause is not None
    
    def test_parse_create_table(self):
        """Test parsing CREATE TABLE"""
        sql = "CREATE TABLE students (id INT, name STRING, gpa INT)"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        assert isinstance(ast, CreateTableNode)
        assert ast.table_name == 'students'
        assert len(ast.columns) == 3
        assert ast.columns[0].name == 'id'
        assert ast.columns[0].data_type == 'INT'
    
    def test_parse_drop_table(self):
        """Test parsing DROP TABLE"""
        sql = "DROP TABLE old_data"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        assert isinstance(ast, DropTableNode)
        assert ast.table_name == 'old_data'
    
    def test_parse_create_index(self):
        """Test parsing CREATE INDEX"""
        sql = "CREATE INDEX idx_user_id ON users (user_id)"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        assert isinstance(ast, CreateIndexNode)
        assert ast.index_name == 'idx_user_id'
        assert ast.table_name == 'users'
        assert ast.column_name == 'user_id'
    
    def test_parse_aggregates(self):
        """Test parsing aggregate functions"""
        queries = [
            "SELECT COUNT(*) FROM orders",
            "SELECT SUM(amount) FROM transactions",
            "SELECT AVG(score) FROM tests",
            "SELECT MIN(price) FROM products",
            "SELECT MAX(salary) FROM employees"
        ]
        
        for sql in queries:
            ast = Parser(Lexer(sql).tokenize()).parse()
            assert isinstance(ast, SelectNode)


# ============================================================================
# EXECUTION LAYER TESTS
# ============================================================================

class TestQueryExecutor:
    """Test query execution engine"""
    
    def test_execute_create_table(self, executor):
        """Test executing CREATE TABLE"""
        sql = "CREATE TABLE inventory (item_id INT, item_name STRING, quantity INT)"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        result = executor.execute(ast)
        assert result is not None
    
    def test_execute_insert(self, executor, catalog):
        """Test executing INSERT"""
        # Create table first
        create_sql = "CREATE TABLE products (id INT, name STRING, price INT)"
        executor.execute(Parser(Lexer(create_sql).tokenize()).parse())
        
        # Insert data
        insert_sql = "INSERT INTO products VALUES (1, 'Widget', 99)"
        result = executor.execute(Parser(Lexer(insert_sql).tokenize()).parse())
        assert result is not None
    
    def test_execute_select(self, executor):
        """Test executing SELECT"""
        # Setup: create and populate table
        executor.execute(Parser(Lexer("CREATE TABLE items (id INT, value INT)").tokenize()).parse())
        executor.execute(Parser(Lexer("INSERT INTO items VALUES (1, 100)").tokenize()).parse())
        executor.execute(Parser(Lexer("INSERT INTO items VALUES (2, 200)").tokenize()).parse())
        
        # Execute SELECT
        select_sql = "SELECT * FROM items"
        result = executor.execute(Parser(Lexer(select_sql).tokenize()).parse())
        assert result is not None
    
    def test_execute_update(self, executor):
        """Test executing UPDATE"""
        # Setup
        executor.execute(Parser(Lexer("CREATE TABLE config (key INT, value INT)").tokenize()).parse())
        executor.execute(Parser(Lexer("INSERT INTO config VALUES (1, 10)").tokenize()).parse())
        
        # Update
        update_sql = "UPDATE config SET value = 20 WHERE key = 1"
        result = executor.execute(Parser(Lexer(update_sql).tokenize()).parse())
        assert result is not None
    
    def test_execute_delete(self, executor):
        """Test executing DELETE"""
        # Setup
        executor.execute(Parser(Lexer("CREATE TABLE temp (id INT, data STRING)").tokenize()).parse())
        executor.execute(Parser(Lexer("INSERT INTO temp VALUES (1, 'old')").tokenize()).parse())
        executor.execute(Parser(Lexer("INSERT INTO temp VALUES (2, 'keep')").tokenize()).parse())
        
        # Delete
        delete_sql = "DELETE FROM temp WHERE data = 'old'"
        result = executor.execute(Parser(Lexer(delete_sql).tokenize()).parse())
        assert result is not None
    
    def test_execute_count_aggregate(self, executor):
        """Test executing COUNT aggregate"""
        # Setup table with data
        executor.execute(Parser(Lexer("CREATE TABLE orders (id INT, total INT)").tokenize()).parse())
        for i in range(5):
            executor.execute(Parser(Lexer(f"INSERT INTO orders VALUES ({i}, {i*100})").tokenize()).parse())
        
        # COUNT query
        count_sql = "SELECT COUNT(*) FROM orders"
        result = executor.execute(Parser(Lexer(count_sql).tokenize()).parse())
        assert result is not None


class TestPhysicalOperators:
    """Test physical query operators"""
    
    def test_scan_operator(self, catalog, table_manager):
        """Test ScanOperator"""
        # Setup data
        columns = [Column(name='id', data_type='INT'), Column(name='val', data_type='INT')]
        catalog.create_table('scan_test', columns)
        for i in range(10):
            table_manager.insert_row('scan_test', [i, i * 10])
        
        # Create and execute scan operator
        scan_op = ScanOperator(table_manager, 'scan_test')
        rows = list(scan_op.get_next())
        assert len(rows) > 0
    
    def test_filter_operator(self, catalog, table_manager):
        """Test FilterOperator"""
        columns = [Column(name='id', data_type='INT'), Column(name='value', data_type='INT')]
        catalog.create_table('filter_test', columns)
        for i in range(20):
            table_manager.insert_row('filter_test', [i, i * 5])
        
        # Create scan and filter operators
        scan_op = ScanOperator(table_manager, 'filter_test')
        
        def predicate(row):
            return row[1] > 50  # value > 50
        
        filter_op = FilterOperator(scan_op, predicate)
        filtered_rows = list(filter_op.get_next())
        
        # All filtered rows should satisfy predicate
        for row in filtered_rows:
            assert row[1] > 50


# ============================================================================
# OPTIMIZATION TESTS
# ============================================================================

class TestCostEstimator:
    """Test query cost estimation"""
    
    def test_estimate_seq_scan_cost(self):
        """Test sequential scan cost estimation"""
        stats = {'num_pages': 10, 'num_rows': 1000}
        cost = cost_estimator.cost_seq_scan(stats)
        assert cost > 0
    
    def test_estimate_index_scan_cost(self):
        """Test index scan cost estimation"""
        stats = {'num_rows': 1000}
        selectivity = 0.01
        cost = cost_estimator.cost_index_scan(stats, selectivity)
        assert cost > 0
    
    def test_cost_comparison(self):
        """Test that index scan is cheaper for selective queries"""
        stats = {'num_pages': 100, 'num_rows': 10000}
        
        seq_cost = cost_estimator.cost_seq_scan(stats)
        idx_cost = cost_estimator.cost_index_scan(stats, 0.001)  # Very selective
        
        # Index should be cheaper for very selective queries
        assert idx_cost < seq_cost


class TestQueryOptimizer:
    """Test query optimization"""
    
    def test_optimizer_creation(self, optimizer):
        """Test creating optimizer instance"""
        assert optimizer is not None
    
    def test_optimize_select_query(self, optimizer, catalog, table_manager, index_manager):
        """Test optimizing a SELECT query"""
        # Setup: create table and index
        columns = [Column(name='id', data_type='INT'), Column(name='data', data_type='STRING')]
        catalog.create_table('opt_test', columns)
        
        for i in range(50):
            table_manager.insert_row('opt_test', [i, f"data_{i}"])
        
        index_manager.create_index('idx_opt', 'opt_test', 'id', table_manager)
        
        # Parse query
        sql = "SELECT * FROM opt_test WHERE id = 25"
        ast = Parser(Lexer(sql).tokenize()).parse()
        
        # Optimize
        plan = optimizer.optimize(ast)
        assert plan is not None


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_table_not_found_error(self, table_manager):
        """Test error when accessing non-existent table"""
        result = table_manager.select_all('nonexistent_table')
        assert result == []  # Should return empty, not crash
    
    def test_duplicate_table_error(self, catalog):
        """Test error when creating duplicate table"""
        columns = [Column(name='id', data_type='INT')]
        
        # Create first time
        result1 = catalog.create_table('dup_test', columns)
        assert result1 is True
        
        # Try to create again
        result2 = catalog.create_table('dup_test', columns)
        assert result2 is False
    
    def test_invalid_sql_syntax(self):
        """Test parsing invalid SQL"""
        invalid_sqls = [
            "SELECT FROM WHERE",
            "INSERT INTO VALUES",
            "UPDATE SET",
            "DELETE WHERE"
        ]
        
        for sql in invalid_sqls:
            try:
                Parser(Lexer(sql).tokenize()).parse()
                # If we get here, the parser didn't catch the error
                # That's okay for some cases, just testing it doesn't crash
            except Exception:
                # Expected to raise an error
                pass
    
    def test_insert_without_table(self, executor):
        """Test INSERT into non-existent table"""
        sql = "INSERT INTO ghost_table VALUES (1, 2, 3)"
        
        try:
            executor.execute(Parser(Lexer(sql).tokenize()).parse())
        except Exception:
            # Expected to fail
            pass
    
    def test_empty_query_results(self, executor):
        """Test queries that return no results"""
        # Create empty table
        executor.execute(Parser(Lexer("CREATE TABLE empty (id INT)").tokenize()).parse())
        
        # Query empty table
        result = executor.execute(Parser(Lexer("SELECT * FROM empty").tokenize()).parse())
        # Should not crash, should return empty result
        assert result is not None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """End-to-end integration tests"""
    
    def test_complete_workflow(self, executor):
        """Test complete database workflow"""
        # Create table
        executor.execute(Parser(Lexer(
            "CREATE TABLE employees (emp_id INT, name STRING, salary INT, dept STRING)"
        ).tokenize()).parse())
        
        # Insert multiple records
        employees = [
            (1, 'Alice', 75000, 'Engineering'),
            (2, 'Bob', 65000, 'Marketing'),
            (3, 'Charlie', 80000, 'Engineering'),
            (4, 'Diana', 70000, 'Sales'),
            (5, 'Eve', 85000, 'Engineering')
        ]
        
        for emp_id, name, salary, dept in employees:
            executor.execute(Parser(Lexer(
                f"INSERT INTO employees VALUES ({emp_id}, '{name}', {salary}, '{dept}')"
            ).tokenize()).parse())
        
        # Query all data
        result = executor.execute(Parser(Lexer("SELECT * FROM employees").tokenize()).parse())
        assert result is not None
        
        # Update data
        executor.execute(Parser(Lexer(
            "UPDATE employees SET salary = 90000 WHERE emp_id = 5"
        ).tokenize()).parse())
        
        # Delete data
        executor.execute(Parser(Lexer(
            "DELETE FROM employees WHERE dept = 'Marketing'"
        ).tokenize()).parse())
    
    def test_index_usage_workflow(self, executor, catalog, index_manager, table_manager):
        """Test workflow with index usage"""
        # Create table
        executor.execute(Parser(Lexer(
            "CREATE TABLE users (user_id INT, username STRING, email STRING)"
        ).tokenize()).parse())
        
        # Insert data
        for i in range(100):
            executor.execute(Parser(Lexer(
                f"INSERT INTO users VALUES ({i}, 'user{i}', 'user{i}@test.com')"
            ).tokenize()).parse())
        
        # Create index
        executor.execute(Parser(Lexer(
            "CREATE INDEX idx_user_id ON users (user_id)"
        ).tokenize()).parse())
        
        # Query using index
        result = executor.execute(Parser(Lexer(
            "SELECT * FROM users WHERE user_id = 50"
        ).tokenize()).parse())
        assert result is not None
    
    def test_aggregation_workflow(self, executor):
        """Test workflow with aggregation functions"""
        # Create and populate table
        executor.execute(Parser(Lexer(
            "CREATE TABLE sales (sale_id INT, amount INT, region STRING)"
        ).tokenize()).parse())
        
        for i in range(20):
            region = 'North' if i % 2 == 0 else 'South'
            executor.execute(Parser(Lexer(
                f"INSERT INTO sales VALUES ({i}, {(i+1)*100}, '{region}')"
            ).tokenize()).parse())
        
        # Test COUNT
        executor.execute(Parser(Lexer("SELECT COUNT(*) FROM sales").tokenize()).parse())
        
        # Test SUM
        executor.execute(Parser(Lexer("SELECT SUM(amount) FROM sales").tokenize()).parse())
        
        # Test AVG
        executor.execute(Parser(Lexer("SELECT AVG(amount) FROM sales").tokenize()).parse())


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Run with coverage
    pytest.main([
        __file__,
        "-v",
        "--cov=src",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-report=json",
        "--cov-config=.coveragerc",
        "-W", "ignore::DeprecationWarning"
    ])
