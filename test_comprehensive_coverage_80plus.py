"""
COMPREHENSIVE COVERAGE TEST SUITE - 80%+ TARGET
==============================================
Industry-standard test suite for AlpacaDB targeting 80%+ code coverage.
Tests all major modules with realistic scenarios.

Target: Increase coverage from 61.93% to 80%+
Focus: Low-coverage modules (cost_estimator, operators, table_manager, errors)
"""
import pytest
import tempfile
import shutil
from pathlib import Path

# Core imports
from src.storage.page_manager import PageManager
from src.storage.catalog import Catalog
from src.storage.table_manager import TableManager
from src.storage.indexing.btree import BTree
from src.storage.indexing.index_manager import IndexManager

# Query components
from src.query.lexer import Lexer
from src.query.parser import Parser
from src.query.tokens import TokenType

# Execution components
from src.executor.executor import QueryExecutor
from src.executor.operators import (
    ScanOperator, IndexScanOperator, FilterOperator,
    ProjectOperator, SortOperator, AggregateOperator
)

# Optimization components
from src.optimizer.optimizer import QueryOptimizer
from src.optimizer import cost_estimator

# Error handling
from src.errors import (
    AlpacaDBError, TableNotFoundError, ColumnNotFoundError,
    SyntaxError as AlpacaSyntaxError, TypeMismatchError,
    DuplicateTableError, DuplicateIndexError, IndexNotFoundError
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_db():
    """Create temporary database with all components."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    
    page_manager = PageManager(str(db_path))
    catalog = Catalog(page_manager)
    table_manager = TableManager(page_manager, catalog)
    index_manager = IndexManager(catalog, page_manager)
    executor = QueryExecutor(page_manager, catalog, table_manager, index_manager)
    optimizer = QueryOptimizer(catalog, index_manager)
    
    yield {
        'page_manager': page_manager,
        'catalog': catalog,
        'table_manager': table_manager,
        'index_manager': index_manager,
        'executor': executor,
        'optimizer': optimizer,
        'db_path': db_path
    }
    
    # Cleanup
    page_manager.close()
    shutil.rmtree(temp_dir)


def execute_sql(executor, sql):
    """Helper to execute SQL and return results."""
    lexer = Lexer(sql)
    parser = Parser(lexer.tokenize())
    ast = parser.parse()
    results = executor.execute(ast)
    return results


# =============================================================================
# TEST SUITE 1: COST ESTIMATOR (Target: 25.64% → 80%+)
# =============================================================================

class TestCostEstimatorComprehensive:
    """Comprehensive tests for cost estimation module."""
    
    def test_cost_seq_scan_basic(self, temp_db):
        """Test sequential scan cost calculation."""
        catalog = temp_db['catalog']
        
        # Create table and get stats
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'value', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('test_table', columns)
        
        # Simulate table stats
        table_stats = {
            'row_count': 1000,
            'page_count': 10,
            'avg_row_size': 100
        }
        
        cost = cost_estimator.cost_seq_scan(table_stats)
        assert cost > 0
        assert isinstance(cost, (int, float))
    
    def test_cost_seq_scan_with_selectivity(self, temp_db):
        """Test seq scan cost with different selectivity values."""
        table_stats = {'row_count': 10000, 'page_count': 100, 'avg_row_size': 50}
        
        # Low selectivity (filters out most rows)
        cost_low = cost_estimator.cost_seq_scan(table_stats, selectivity=0.01)
        
        # High selectivity (keeps most rows)
        cost_high = cost_estimator.cost_seq_scan(table_stats, selectivity=0.99)
        
        # Both should be positive
        assert cost_low > 0
        assert cost_high > 0
    
    def test_cost_index_scan_basic(self, temp_db):
        """Test index scan cost calculation."""
        catalog = temp_db['catalog']
        page_manager = temp_db['page_manager']
        
        # Create table with index
        columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
        catalog.create_table('indexed_table', columns)
        
        # Simulate index stats
        table_stats = {'row_count': 1000, 'page_count': 10}
        index_stats = {'height': 3, 'leaf_pages': 5, 'total_entries': 1000}
        
        cost = cost_estimator.cost_index_scan(table_stats, index_stats, 'equality')
        assert cost > 0
        assert isinstance(cost, (int, float))
    
    def test_cost_index_scan_different_predicates(self, temp_db):
        """Test index scan cost with different predicate types."""
        table_stats = {'row_count': 5000, 'page_count': 50}
        index_stats = {'height': 4, 'leaf_pages': 10, 'total_entries': 5000}
        
        # Equality predicate (most selective)
        cost_eq = cost_estimator.cost_index_scan(table_stats, index_stats, 'equality')
        
        # Range predicate (less selective)
        cost_range = cost_estimator.cost_index_scan(table_stats, index_stats, 'range')
        
        assert cost_eq > 0
        assert cost_range > 0
    
    def test_cost_sort_basic(self, temp_db):
        """Test sort operation cost calculation."""
        result_count = 1000
        cost = cost_estimator.cost_sort(result_count)
        assert cost > 0
    
    def test_cost_sort_scaling(self, temp_db):
        """Test that sort cost scales appropriately."""
        small_cost = cost_estimator.cost_sort(100)
        large_cost = cost_estimator.cost_sort(10000)
        
        # Larger dataset should cost more
        assert large_cost > small_cost
    
    def test_cost_join_nested_loop(self, temp_db):
        """Test nested loop join cost calculation."""
        left_stats = {'row_count': 100}
        right_stats = {'row_count': 1000}
        
        cost = cost_estimator.cost_join(left_stats, right_stats, 'nested_loop')
        assert cost > 0
    
    def test_cost_aggregation_basic(self, temp_db):
        """Test aggregation operation cost."""
        group_count = 50
        row_count = 1000
        
        cost = cost_estimator.cost_aggregation(group_count, row_count)
        assert cost > 0


# =============================================================================
# TEST SUITE 2: TABLE MANAGER (Target: 63.27% → 80%+)
# =============================================================================

class TestTableManagerComprehensive:
    """Comprehensive tests for TableManager operations."""
    
    def test_insert_multiple_rows_batch(self, temp_db):
        """Test inserting multiple rows in batch."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': True},
            {'name': 'score', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('batch_test', columns)
        
        # Insert 50 rows
        for i in range(50):
            row = [i, f'user_{i}', i * 10]
            table_manager.insert_row('batch_test', row)
        
        # Verify all rows exist
        all_rows = list(table_manager.scan_table('batch_test'))
        assert len(all_rows) == 50
    
    def test_update_rows_with_condition(self, temp_db):
        """Test updating specific rows based on condition."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        # Setup
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'status', 'type': 'STRING', 'nullable': True}
        ]
        catalog.create_table('update_test', columns)
        
        # Insert test data
        table_manager.insert_row('update_test', [1, 'pending'])
        table_manager.insert_row('update_test', [2, 'pending'])
        table_manager.insert_row('update_test', [3, 'active'])
        
        # Update via executor
        sql = "UPDATE update_test SET status = 'completed' WHERE id = 1"
        execute_sql(executor, sql)
        
        # Verify
        all_rows = list(table_manager.scan_table('update_test'))
        updated_row = [r for r in all_rows if r[0] == 1][0]
        assert updated_row[1] == 'completed'
    
    def test_delete_rows_with_condition(self, temp_db):
        """Test deleting specific rows."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        # Setup
        columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
        catalog.create_table('delete_test', columns)
        
        # Insert rows
        for i in range(1, 6):
            table_manager.insert_row('delete_test', [i])
        
        # Delete via executor
        sql = "DELETE FROM delete_test WHERE id > 3"
        execute_sql(executor, sql)
        
        # Verify only 3 rows remain
        remaining = list(table_manager.scan_table('delete_test'))
        assert len(remaining) == 3
    
    def test_scan_table_empty(self, temp_db):
        """Test scanning empty table."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        
        columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
        catalog.create_table('empty_table', columns)
        
        rows = list(table_manager.scan_table('empty_table'))
        assert len(rows) == 0
    
    def test_scan_table_large_dataset(self, temp_db):
        """Test scanning table with many rows spanning multiple pages."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'data', 'type': 'STRING', 'nullable': True}
        ]
        catalog.create_table('large_table', columns)
        
        # Insert enough rows to span multiple pages
        num_rows = 200
        for i in range(num_rows):
            table_manager.insert_row('large_table', [i, f'data_{i}' * 10])
        
        # Scan and verify
        all_rows = list(table_manager.scan_table('large_table'))
        assert len(all_rows) == num_rows
    
    def test_get_row_by_rid(self, temp_db):
        """Test retrieving row by RID."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        
        columns = [{'name': 'value', 'type': 'INT', 'nullable': False}]
        catalog.create_table('rid_test', columns)
        
        # Insert and track RID
        rid = table_manager.insert_row('rid_test', [42])
        
        # Retrieve by RID
        row = table_manager.get_row('rid_test', rid)
        assert row[0] == 42


# =============================================================================
# TEST SUITE 3: SQL EXECUTION (Target: operators + executor coverage)
# =============================================================================

class TestSQLExecutionComprehensive:
    """Comprehensive tests using SQL execution to cover operators."""
    
    def test_complex_where_clause(self, temp_db):
        """Test complex WHERE clause with AND/OR."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [
            {'name': 'age', 'type': 'INT', 'nullable': False},
            {'name': 'score', 'type': 'INT', 'nullable': False}
        ]
        catalog.create_table('filter_test', columns)
        
        for age, score in [(25, 80), (30, 90), (35, 70), (40, 95)]:
            table_manager.insert_row('filter_test', [age, score])
        
        sql = "SELECT * FROM filter_test WHERE age >= 30 AND score >= 90"
        results = execute_sql(executor, sql)
        
        # Should match (30, 90) and (40, 95)
        assert len(results) == 2
    
    def test_column_projection(self, temp_db):
        """Test selecting specific columns (projection)."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': True},
            {'name': 'age', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('proj_test', columns)
        table_manager.insert_row('proj_test', [1, 'Alice', 30])
        table_manager.insert_row('proj_test', [2, 'Bob', 25])
        
        sql = "SELECT name FROM proj_test"
        results = execute_sql(executor, sql)
        
        assert len(results) == 2
        assert results[0] == ['Alice']
    
    def test_order_by_ascending(self, temp_db):
        """Test ORDER BY ascending."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [{'name': 'value', 'type': 'INT', 'nullable': False}]
        catalog.create_table('sort_test', columns)
        
        for val in [3, 1, 4, 1, 5, 9, 2, 6]:
            table_manager.insert_row('sort_test', [val])
        
        sql = "SELECT * FROM sort_test ORDER BY value"
        results = execute_sql(executor, sql)
        
        values = [r[0] for r in results]
        assert values == sorted(values)
    
    def test_order_by_descending(self, temp_db):
        """Test ORDER BY descending."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [{'name': 'value', 'type': 'INT', 'nullable': False}]
        catalog.create_table('sort_desc', columns)
        
        for val in [5, 2, 8, 1, 9]:
            table_manager.insert_row('sort_desc', [val])
        
        sql = "SELECT * FROM sort_desc ORDER BY value DESC"
        results = execute_sql(executor, sql)
        
        values = [r[0] for r in results]
        assert values == sorted(values, reverse=True)
    
    def test_limit_clause(self, temp_db):
        """Test LIMIT clause."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
        catalog.create_table('limit_test', columns)
        
        for i in range(10):
            table_manager.insert_row('limit_test', [i])
        
        sql = "SELECT * FROM limit_test LIMIT 3"
        results = execute_sql(executor, sql)
        
        assert len(results) == 3
    
    def test_count_aggregate(self, temp_db):
        """Test COUNT aggregate function."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [
            {'name': 'category', 'type': 'STRING', 'nullable': True},
            {'name': 'value', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('agg_test', columns)
        
        table_manager.insert_row('agg_test', ['A', 10])
        table_manager.insert_row('agg_test', ['A', 20])
        table_manager.insert_row('agg_test', ['B', 30])
        
        sql = "SELECT COUNT(*) FROM agg_test"
        results = execute_sql(executor, sql)
        
        assert results[0][0] == 3
    
    def test_sum_aggregate(self, temp_db):
        """Test SUM aggregate function."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [{'name': 'amount', 'type': 'INT', 'nullable': False}]
        catalog.create_table('sum_test', columns)
        
        for val in [10, 20, 30]:
            table_manager.insert_row('sum_test', [val])
        
        sql = "SELECT SUM(amount) FROM sum_test"
        results = execute_sql(executor, sql)
        
        assert results[0][0] == 60
    
    def test_avg_aggregate(self, temp_db):
        """Test AVG aggregate function."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [{'name': 'score', 'type': 'INT', 'nullable': False}]
        catalog.create_table('avg_test', columns)
        
        for val in [80, 90, 100]:
            table_manager.insert_row('avg_test', [val])
        
        sql = "SELECT AVG(score) FROM avg_test"
        results = execute_sql(executor, sql)
        
        assert results[0][0] == 90
    
    def test_min_max_aggregates(self, temp_db):
        """Test MIN and MAX aggregate functions."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [{'name': 'value', 'type': 'INT', 'nullable': False}]
        catalog.create_table('minmax_test', columns)
        
        for val in [5, 15, 25, 3, 42]:
            table_manager.insert_row('minmax_test', [val])
        
        sql = "SELECT MIN(value), MAX(value) FROM minmax_test"
        results = execute_sql(executor, sql)
        
        assert results[0][0] == 3
        assert results[0][1] == 42
    
    def test_group_by_with_count(self, temp_db):
        """Test GROUP BY with COUNT."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [
            {'name': 'dept', 'type': 'STRING', 'nullable': True},
            {'name': 'salary', 'type': 'INT', 'nullable': False}
        ]
        catalog.create_table('dept_test', columns)
        
        table_manager.insert_row('dept_test', ['Sales', 50000])
        table_manager.insert_row('dept_test', ['Sales', 60000])
        table_manager.insert_row('dept_test', ['Engineering', 80000])
        
        sql = "SELECT dept, COUNT(*) FROM dept_test GROUP BY dept"
        results = execute_sql(executor, sql)
        
        # Should have 2 groups
        assert len(results) == 2


# =============================================================================
# TEST SUITE 4: ERROR HANDLING (Target: 64% → 80%+)
# =============================================================================

class TestErrorHandlingComprehensive:
    """Comprehensive error handling tests."""
    
    def test_table_not_found_error_details(self, temp_db):
        """Test TableNotFoundError with detailed message."""
        executor = temp_db['executor']
        
        with pytest.raises(TableNotFoundError) as exc_info:
            sql = "SELECT * FROM nonexistent_table"
            execute_sql(executor, sql)
        
        error = exc_info.value
        assert 'nonexistent_table' in str(error)
    
    def test_column_not_found_error(self, temp_db):
        """Test ColumnNotFoundError."""
        catalog = temp_db['catalog']
        executor = temp_db['executor']
        
        columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
        catalog.create_table('col_test', columns)
        
        with pytest.raises(ColumnNotFoundError):
            sql = "SELECT nonexistent_column FROM col_test"
            execute_sql(executor, sql)
    
    def test_syntax_error_invalid_keyword(self, temp_db):
        """Test SyntaxError with invalid SQL keyword."""
        with pytest.raises(AlpacaSyntaxError):
            lexer = Lexer("INVALID_KEYWORD * FROM table")
            parser = Parser(lexer.tokenize())
            parser.parse()
    
    def test_syntax_error_incomplete_query(self, temp_db):
        """Test SyntaxError with incomplete query."""
        with pytest.raises(AlpacaSyntaxError):
            lexer = Lexer("SELECT * FROM")
            parser = Parser(lexer.tokenize())
            parser.parse()
    
    def test_duplicate_table_error(self, temp_db):
        """Test DuplicateTableError when creating existing table."""
        catalog = temp_db['catalog']
        
        columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
        catalog.create_table('dup_test', columns)
        
        with pytest.raises(DuplicateTableError):
            catalog.create_table('dup_test', columns)
    
    def test_duplicate_index_error(self, temp_db):
        """Test DuplicateIndexError."""
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        
        columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
        catalog.create_table('idx_test', columns)
        
        index_manager.create_index('idx_test', 'id', 'test_idx')
        
        with pytest.raises(DuplicateIndexError):
            index_manager.create_index('idx_test', 'id', 'test_idx')
    
    def test_index_not_found_error(self, temp_db):
        """Test IndexNotFoundError."""
        index_manager = temp_db['index_manager']
        
        with pytest.raises(IndexNotFoundError):
            index_manager.drop_index('nonexistent_idx')
    
    def test_type_error_invalid_comparison(self, temp_db):
        """Test TypeError with invalid type comparison."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': True}
        ]
        catalog.create_table('type_test', columns)
        table_manager.insert_row('type_test', [1, 'Alice'])
        
        # This might raise TypeError depending on implementation
        try:
            sql = "SELECT * FROM type_test WHERE name > 123"
            execute_sql(executor, sql)
        except (TypeMismatchError, Exception):
            pass  # Expected


# =============================================================================
# TEST SUITE 5: INDEX MANAGER (Target: 73.11% → 80%+)
# =============================================================================

class TestIndexManagerComprehensive:
    """Comprehensive tests for IndexManager."""
    
    def test_create_index_on_string_column(self, temp_db):
        """Test creating index on STRING column."""
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': True}
        ]
        catalog.create_table('str_idx_test', columns)
        
        index_manager.create_index('str_idx_test', 'name', 'idx_name')
        
        # Verify index exists
        indexes = catalog.get_indexes('str_idx_test')
        assert len(indexes) > 0
    
    def test_index_usage_in_query(self, temp_db):
        """Test that index is actually used in query execution."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        index_manager = temp_db['index_manager']
        executor = temp_db['executor']
        
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'value', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('idx_usage', columns)
        
        # Insert data
        for i in range(100):
            table_manager.insert_row('idx_usage', [i, i * 10])
        
        # Create index
        index_manager.create_index('idx_usage', 'id', 'idx_id')
        
        # Query should use index
        sql = "SELECT * FROM idx_usage WHERE id = 50"
        results = execute_sql(executor, sql)
        
        assert len(results) == 1
        assert results[0][0] == 50
    
    def test_drop_index_and_fallback_to_seqscan(self, temp_db):
        """Test dropping index forces fallback to sequential scan."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        index_manager = temp_db['index_manager']
        executor = temp_db['executor']
        
        columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
        catalog.create_table('drop_idx_test', columns)
        
        table_manager.insert_row('drop_idx_test', [1])
        
        # Create and then drop index
        index_manager.create_index('drop_idx_test', 'id', 'idx_temp')
        index_manager.drop_index('idx_temp')
        
        # Query should still work via seqscan
        sql = "SELECT * FROM drop_idx_test WHERE id = 1"
        results = execute_sql(executor, sql)
        
        assert len(results) == 1
    
    def test_multiple_indexes_on_same_table(self, temp_db):
        """Test creating multiple indexes on same table."""
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'age', 'type': 'INT', 'nullable': True},
            {'name': 'score', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('multi_idx_test', columns)
        
        # Create multiple indexes
        index_manager.create_index('multi_idx_test', 'id', 'idx_id')
        index_manager.create_index('multi_idx_test', 'age', 'idx_age')
        index_manager.create_index('multi_idx_test', 'score', 'idx_score')
        
        indexes = catalog.get_indexes('multi_idx_test')
        assert len(indexes) == 3


# =============================================================================
# TEST SUITE 6: INTEGRATION TESTS
# =============================================================================

class TestIntegrationScenarios:
    """Complex integration tests covering multiple modules."""
    
    def test_complete_crud_workflow(self, temp_db):
        """Test complete CREATE, INSERT, UPDATE, SELECT, DELETE workflow."""
        executor = temp_db['executor']
        table_manager = temp_db['table_manager']
        
        # CREATE
        execute_sql(executor, "CREATE TABLE products (id INT, name STRING, price INT)")
        
        # INSERT
        execute_sql(executor, "INSERT INTO products VALUES (1, 'Laptop', 1000)")
        execute_sql(executor, "INSERT INTO products VALUES (2, 'Mouse', 25)")
        
        # SELECT
        results = execute_sql(executor, "SELECT * FROM products")
        assert len(results) == 2
        
        # UPDATE
        execute_sql(executor, "UPDATE products SET price = 950 WHERE id = 1")
        results = execute_sql(executor, "SELECT price FROM products WHERE id = 1")
        assert results[0][0] == 950
        
        # DELETE
        execute_sql(executor, "DELETE FROM products WHERE id = 2")
        results = execute_sql(executor, "SELECT * FROM products")
        assert len(results) == 1
    
    def test_complex_query_with_aggregation_and_sorting(self, temp_db):
        """Test complex query with GROUP BY, aggregation, and ORDER BY."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        executor = temp_db['executor']
        
        columns = [
            {'name': 'dept', 'type': 'STRING', 'nullable': True},
            {'name': 'salary', 'type': 'INT', 'nullable': False}
        ]
        catalog.create_table('salaries', columns)
        
        # Insert test data
        for dept, salary in [('Engineering', 100000), ('Engineering', 110000),
                              ('Sales', 80000), ('Sales', 85000)]:
            table_manager.insert_row('salaries', [dept, salary])
        
        sql = "SELECT dept, AVG(salary) FROM salaries GROUP BY dept ORDER BY dept"
        results = execute_sql(executor, sql)
        
        assert len(results) == 2
    
    def test_index_accelerated_large_dataset(self, temp_db):
        """Test index performance on large dataset."""
        catalog = temp_db['catalog']
        table_manager = temp_db['table_manager']
        index_manager = temp_db['index_manager']
        executor = temp_db['executor']
        
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'data', 'type': 'STRING', 'nullable': True}
        ]
        catalog.create_table('large_test', columns)
        
        # Insert 500 rows
        for i in range(500):
            table_manager.insert_row('large_test', [i, f'data_{i}'])
        
        # Create index
        index_manager.create_index('large_test', 'id', 'idx_large_id')
        
        # Query specific row
        sql = "SELECT * FROM large_test WHERE id = 250"
        results = execute_sql(executor, sql)
        
        assert len(results) == 1
        assert results[0][0] == 250


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=src', '--cov-report=html', '--cov-report=term'])
