"""
Unit tests for Query Optimizer.

Tests the rule-based optimizer's decision-making logic.
"""

import pytest
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage import PageManager, Catalog, TableManager
from src.storage.indexing.index_manager import IndexManager
from src.query import Lexer, Parser
from src.executor import QueryExecutor
from src.optimizer import QueryOptimizer


class TestOptimizerPlanSelection:
    """Test optimizer's plan selection logic."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        temp_dir = tempfile.mkdtemp(prefix="optimizer_test_")
        db_path = os.path.join(temp_dir, "test.db")
        
        page_manager = PageManager(db_path)
        catalog = Catalog(page_manager)
        index_manager = IndexManager(catalog, page_manager)
        table_manager = TableManager(page_manager, catalog, index_manager)
        
        # Create test table
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'email', 'type': 'STRING', 'nullable': True},
            {'name': 'age', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('users', columns)
        
        # Insert test data
        for i in range(10):
            table_manager.insert_row('users', [i, f'user{i}@test.com', 20 + i])
        
        yield {
            'page_manager': page_manager,
            'catalog': catalog,
            'index_manager': index_manager,
            'table_manager': table_manager
        }
        
        # Cleanup
        page_manager.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def _parse_sql(self, sql):
        """Helper to parse SQL query."""
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        return parser.parse()
    
    def test_no_index_uses_seqscan(self, temp_db):
        """Test that optimizer chooses SeqScan when no index exists."""
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        
        optimizer = QueryOptimizer(catalog, index_manager)
        sql = "SELECT * FROM users WHERE email = 'user5@test.com';"
        ast = self._parse_sql(sql)
        
        plan = optimizer.optimize(ast)
        
        assert plan.plan_type == 'SeqScan'
        assert plan.index_name is None
    
    def test_with_index_uses_indexscan(self, temp_db):
        """Test that optimizer chooses IndexScan when index exists."""
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        # Create index
        index_manager.create_index('idx_email', 'users', 'email', table_manager)
        
        optimizer = QueryOptimizer(catalog, index_manager)
        sql = "SELECT * FROM users WHERE email = 'user5@test.com';"
        ast = self._parse_sql(sql)
        
        plan = optimizer.optimize(ast)
        
        assert plan.plan_type == 'IndexScan'
        assert plan.index_name == 'idx_email'
        assert plan.search_key == 'user5@test.com'
    
    def test_no_where_clause_uses_seqscan(self, temp_db):
        """Test that optimizer chooses SeqScan when no WHERE clause."""
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        # Create index
        index_manager.create_index('idx_email', 'users', 'email', table_manager)
        
        optimizer = QueryOptimizer(catalog, index_manager)
        sql = "SELECT * FROM users;"
        ast = self._parse_sql(sql)
        
        plan = optimizer.optimize(ast)
        
        assert plan.plan_type == 'SeqScan'
    
    def test_and_condition_with_indexed_column(self, temp_db):
        """Test AND condition where one column is indexed."""
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        # Create index on email
        index_manager.create_index('idx_email', 'users', 'email', table_manager)
        
        optimizer = QueryOptimizer(catalog, index_manager)
        sql = "SELECT * FROM users WHERE email = 'user5@test.com' AND age > 25;"
        ast = self._parse_sql(sql)
        
        plan = optimizer.optimize(ast)
        
        # Should use IndexScan for email, then filter by age
        assert plan.plan_type == 'IndexScan'
        assert plan.index_name == 'idx_email'
        assert plan.search_key == 'user5@test.com'
    
    def test_non_equality_predicate_uses_seqscan(self, temp_db):
        """Test that range predicates now use IndexRangeScan (Phase 3)."""
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        # Create index on age
        index_manager.create_index('idx_age', 'users', 'age', table_manager)
        
        optimizer = QueryOptimizer(catalog, index_manager)
        sql = "SELECT * FROM users WHERE age > 25;"
        ast = self._parse_sql(sql)
        
        plan = optimizer.optimize(ast)
        
        # Phase 3: Range queries now supported via IndexRangeScan
        assert plan.plan_type == 'IndexRangeScan'
    
    def test_or_condition_uses_seqscan(self, temp_db):
        """Test that OR conditions fall back to SeqScan."""
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        # Create indexes
        index_manager.create_index('idx_email', 'users', 'email', table_manager)
        index_manager.create_index('idx_age', 'users', 'age', table_manager)
        
        optimizer = QueryOptimizer(catalog, index_manager)
        sql = "SELECT * FROM users WHERE email = 'user5@test.com' OR age = 25;"
        ast = self._parse_sql(sql)
        
        plan = optimizer.optimize(ast)
        
        # OR not yet supported in Phase 1
        assert plan.plan_type == 'SeqScan'
    
    def test_multiple_indexes_chooses_first(self, temp_db):
        """Test that optimizer chooses first indexed column in AND."""
        catalog = temp_db['catalog']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        # Create indexes on both columns
        index_manager.create_index('idx_email', 'users', 'email', table_manager)
        index_manager.create_index('idx_age', 'users', 'age', table_manager)
        
        optimizer = QueryOptimizer(catalog, index_manager)
        sql = "SELECT * FROM users WHERE email = 'user5@test.com' AND age = 25;"
        ast = self._parse_sql(sql)
        
        plan = optimizer.optimize(ast)
        
        # Should use first indexed column (email)
        assert plan.plan_type == 'IndexScan'
        assert plan.index_name == 'idx_email'


class TestOptimizerIntegrationWithExecutor:
    """Test optimizer integration with query executor."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        temp_dir = tempfile.mkdtemp(prefix="optimizer_exec_test_")
        db_path = os.path.join(temp_dir, "test.db")
        
        page_manager = PageManager(db_path)
        catalog = Catalog(page_manager)
        index_manager = IndexManager(catalog, page_manager)
        table_manager = TableManager(page_manager, catalog, index_manager)
        executor = QueryExecutor(table_manager, catalog, index_manager)
        
        # Create test table
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': True},
            {'name': 'email', 'type': 'STRING', 'nullable': True},
            {'name': 'age', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('users', columns)
        
        # Insert test data
        test_data = [
            [1, 'Alice', 'alice@test.com', 25],
            [2, 'Bob', 'bob@test.com', 30],
            [3, 'Charlie', 'charlie@test.com', 35],
            [4, 'Diana', 'diana@test.com', 28],
            [5, 'Eve', 'eve@test.com', 32]
        ]
        for row in test_data:
            table_manager.insert_row('users', row)
        
        yield {
            'page_manager': page_manager,
            'catalog': catalog,
            'index_manager': index_manager,
            'table_manager': table_manager,
            'executor': executor
        }
        
        # Cleanup
        page_manager.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def _execute_sql(self, executor, sql):
        """Helper to execute SQL query."""
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        return executor.execute(ast)
    
    def test_executor_uses_seqscan_without_index(self, temp_db):
        """Test that executor uses SeqScan when no index."""
        executor = temp_db['executor']
        
        sql = "SELECT * FROM users WHERE email = 'alice@test.com';"
        rows, columns = self._execute_sql(executor, sql)
        
        assert executor.last_plan == 'SeqScan'
        assert len(rows) == 1
        assert rows[0][1] == 'Alice'
    
    def test_executor_uses_indexscan_with_index(self, temp_db):
        """Test that executor uses IndexScan when index exists."""
        executor = temp_db['executor']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        # Create index
        index_manager.create_index('idx_email', 'users', 'email', table_manager)
        
        sql = "SELECT * FROM users WHERE email = 'bob@test.com';"
        rows, columns = self._execute_sql(executor, sql)
        
        assert executor.last_plan == 'IndexScan'
        assert len(rows) == 1
        assert rows[0][1] == 'Bob'
    
    def test_results_identical_with_and_without_index(self, temp_db):
        """Test that results are identical with IndexScan and SeqScan."""
        executor = temp_db['executor']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        # Query without index
        sql = "SELECT * FROM users WHERE email = 'charlie@test.com';"
        rows_seqscan, _ = self._execute_sql(executor, sql)
        assert executor.last_plan == 'SeqScan'
        
        # Create index
        index_manager.create_index('idx_email', 'users', 'email', table_manager)
        
        # Query with index
        rows_indexscan, _ = self._execute_sql(executor, sql)
        assert executor.last_plan == 'IndexScan'
        
        # Results should be identical
        assert rows_seqscan == rows_indexscan
    
    def test_indexscan_with_projection(self, temp_db):
        """Test IndexScan works with column projection."""
        executor = temp_db['executor']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        index_manager.create_index('idx_email', 'users', 'email', table_manager)
        
        sql = "SELECT name, age FROM users WHERE email = 'diana@test.com';"
        rows, columns = self._execute_sql(executor, sql)
        
        assert executor.last_plan == 'IndexScan'
        assert columns == ['name', 'age']
        assert len(rows) == 1
        assert rows[0] == ['Diana', 28]
    
    def test_indexscan_with_order_by(self, temp_db):
        """Test IndexScan works with ORDER BY."""
        executor = temp_db['executor']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        # Insert more rows with same email domain
        table_manager.insert_row('users', [6, 'Frank', 'frank@test.com', 40])
        table_manager.insert_row('users', [7, 'Grace', 'grace@test.com', 22])
        
        index_manager.create_index('idx_age', 'users', 'age', table_manager)
        
        sql = "SELECT * FROM users WHERE age = 30 ORDER BY name ASC;"
        rows, _ = self._execute_sql(executor, sql)
        
        assert executor.last_plan == 'IndexScan'
        assert len(rows) == 1
        assert rows[0][1] == 'Bob'
    
    def test_indexscan_with_and_filter(self, temp_db):
        """Test IndexScan with additional filter (AND condition)."""
        executor = temp_db['executor']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        index_manager.create_index('idx_email', 'users', 'email', table_manager)
        
        sql = "SELECT * FROM users WHERE email = 'alice@test.com' AND age > 20;"
        rows, _ = self._execute_sql(executor, sql)
        
        assert executor.last_plan == 'IndexScan'
        assert len(rows) == 1
        assert rows[0][1] == 'Alice'
    
    def test_indexscan_no_match(self, temp_db):
        """Test IndexScan returns empty when key not found."""
        executor = temp_db['executor']
        index_manager = temp_db['index_manager']
        table_manager = temp_db['table_manager']
        
        index_manager.create_index('idx_email', 'users', 'email', table_manager)
        
        sql = "SELECT * FROM users WHERE email = 'nonexistent@test.com';"
        rows, _ = self._execute_sql(executor, sql)
        
        assert executor.last_plan == 'IndexScan'
        assert len(rows) == 0


class TestOptimizerBackwardCompatibility:
    """Test that optimizer maintains backward compatibility."""
    
    @pytest.fixture
    def temp_db_no_index_manager(self):
        """Create database WITHOUT index_manager (old setup)."""
        temp_dir = tempfile.mkdtemp(prefix="compat_test_")
        db_path = os.path.join(temp_dir, "test.db")
        
        page_manager = PageManager(db_path)
        catalog = Catalog(page_manager)
        table_manager = TableManager(page_manager, catalog)  # No index_manager
        executor = QueryExecutor(table_manager, catalog)  # No index_manager
        
        # Create test table
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': True}
        ]
        catalog.create_table('users', columns)
        table_manager.insert_row('users', [1, 'Alice'])
        
        yield {
            'page_manager': page_manager,
            'executor': executor
        }
        
        # Cleanup
        page_manager.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_executor_works_without_index_manager(self, temp_db_no_index_manager):
        """Test that executor still works when index_manager is None."""
        executor = temp_db_no_index_manager['executor']
        
        lexer = Lexer("SELECT * FROM users;")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        rows, columns = executor.execute(ast)
        
        # Should fall back to SeqScan
        assert executor.last_plan == 'SeqScan'
        assert len(rows) == 1
        assert rows[0][1] == 'Alice'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
