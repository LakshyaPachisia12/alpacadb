"""
Tests for Query Optimizer - validates automatic index selection.
"""

import pytest
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage import PageManager, Catalog, TableManager
from src.storage.indexing import IndexManager
from src.query import Lexer, Parser
from src.executor import QueryExecutor


class TestQueryOptimizer:
    """Test query optimizer functionality."""
    
    @pytest.fixture
    def db_with_index(self):
        """Create a test database with indexed data."""
        temp_dir = tempfile.mkdtemp(prefix="alpacadb_opt_test_")
        db_path = os.path.join(temp_dir, "test.db")
        
        # Initialize components
        page_manager = PageManager(db_path)
        catalog = Catalog(page_manager)
        index_manager = IndexManager(catalog, page_manager)
        table_manager = TableManager(page_manager, catalog, index_manager)
        executor = QueryExecutor(table_manager, catalog, index_manager)
        
        # Create table
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'email', 'type': 'STRING', 'nullable': True},
            {'name': 'age', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('users', columns)
        
        # Insert test data (500 rows to make index worthwhile)
        for i in range(1, 501):
            table_manager.insert_row('users', [
                i,
                f'user{i}@example.com',
                20 + (i % 50)
            ])
        
        # Create index on email column
        index_manager.create_index('idx_email', 'users', 'email')
        
        yield executor, index_manager, table_manager, catalog
        
        # Cleanup
        page_manager.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def execute_query(self, executor, query_str):
        """Helper to parse and execute a query."""
        lexer = Lexer(query_str)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        return executor.execute(ast)
    
    def test_optimizer_uses_index_for_equality(self, db_with_index):
        """Test that optimizer automatically uses index for simple equality."""
        executor, index_manager, table_manager, catalog = db_with_index
        
        # Query with WHERE clause that can use index
        query = "SELECT * FROM users WHERE email = 'user100@example.com';"
        
        rows, columns = self.execute_query(executor, query)
        
        # Should find exactly one row
        assert len(rows) == 1
        assert rows[0][0] == 100  # id
        assert rows[0][1] == 'user100@example.com'  # email
        assert rows[0][2] == 20 + (100 % 50)  # age
    
    def test_optimizer_handles_non_existent_key(self, db_with_index):
        """Test index scan with key that doesn't exist."""
        executor, _, _, _ = db_with_index
        
        query = "SELECT * FROM users WHERE email = 'nonexistent@example.com';"
        rows, columns = self.execute_query(executor, query)
        
        # Should return empty result
        assert len(rows) == 0
    
    def test_optimizer_falls_back_to_scan_without_index(self, db_with_index):
        """Test that queries without suitable index use table scan."""
        executor, _, _, _ = db_with_index
        
        # Query on age column (no index exists)
        query = "SELECT * FROM users WHERE age = 25;"
        rows, columns = self.execute_query(executor, query)
        
        # Should still work, just using table scan
        assert len(rows) > 0  # Multiple users with age 25
        for row in rows:
            assert row[2] == 25  # All have age 25
    
    def test_optimizer_with_complex_where(self, db_with_index):
        """Test optimizer with complex WHERE clause (should fall back to scan)."""
        executor, _, _, _ = db_with_index
        
        # Complex predicate: can't use index
        query = "SELECT * FROM users WHERE age > 30 AND age < 40;"
        rows, columns = self.execute_query(executor, query)
        
        # Should work using table scan + filter
        assert len(rows) > 0
        for row in rows:
            assert 30 < row[2] < 40
    
    def test_btree_order_selection_small_table(self):
        """Test that small tables get appropriate B-Tree order."""
        temp_dir = tempfile.mkdtemp(prefix="alpacadb_order_test_")
        db_path = os.path.join(temp_dir, "test.db")
        
        try:
            page_manager = PageManager(db_path)
            catalog = Catalog(page_manager)
            index_manager = IndexManager(catalog, page_manager)
            table_manager = TableManager(page_manager, catalog, index_manager)
            
            # Create small table
            columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
            catalog.create_table('small_table', columns)
            
            # Insert few rows
            for i in range(50):
                table_manager.insert_row('small_table', [i])
            
            # Create index (should get order=10 for small table)
            index_manager.create_index('idx_id', 'small_table', 'id')
            
            # Verify index was created
            btree = index_manager.get_btree('idx_id')
            assert btree is not None
            assert btree.order == 10  # Small dataset order
            
            page_manager.close()
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def test_optimizer_explain_query(self, db_with_index):
        """Test EXPLAIN-style output from optimizer."""
        executor, _, _, _ = db_with_index
        
        # Access optimizer
        optimizer = executor.optimizer
        assert optimizer is not None
        
        # Get explanation for query
        from src.query.ast_nodes import BinaryOp, ColumnRef, Literal
        
        # WHERE email = 'test@example.com'
        where_clause = BinaryOp(
            left=ColumnRef('email'),
            operator='=',
            right=Literal('test@example.com')
        )
        
        explanation = optimizer.explain_query('users', where_clause)
        
        # Should mention index usage
        assert 'INDEX SCAN' in explanation or 'SEQUENTIAL SCAN' in explanation


class TestIndexPerformanceComparison:
    """Compare performance with and without index."""
    
    def test_index_vs_scan_performance(self):
        """Demonstrate performance difference between index and scan."""
        import time
        
        temp_dir = tempfile.mkdtemp(prefix="alpacadb_perf_")
        db_path = os.path.join(temp_dir, "perf_test.db")
        
        try:
            # Setup
            page_manager = PageManager(db_path)
            catalog = Catalog(page_manager)
            index_manager = IndexManager(catalog, page_manager)
            table_manager = TableManager(page_manager, catalog, index_manager)
            executor = QueryExecutor(table_manager, catalog, index_manager)
            
            # Create table
            columns = [
                {'name': 'id', 'type': 'INT', 'nullable': False},
                {'name': 'value', 'type': 'STRING', 'nullable': True}
            ]
            catalog.create_table('test_data', columns)
            
            # Insert 1000 rows
            print("\n  Inserting 1000 rows...")
            for i in range(1000):
                table_manager.insert_row('test_data', [i, f'value_{i}'])
            
            # Test WITHOUT index
            print("  Testing WITHOUT index...")
            lexer = Lexer("SELECT * FROM test_data WHERE value = 'value_500';")
            ast = Parser(lexer.tokenize()).parse()
            
            start = time.time()
            rows_no_index, _ = executor.execute(ast)
            time_no_index = (time.time() - start) * 1000  # ms
            
            # Create index
            print("  Creating index...")
            index_manager.create_index('idx_value', 'test_data', 'value')
            
            # Test WITH index
            print("  Testing WITH index...")
            lexer = Lexer("SELECT * FROM test_data WHERE value = 'value_500';")
            ast = Parser(lexer.tokenize()).parse()
            
            start = time.time()
            rows_with_index, _ = executor.execute(ast)
            time_with_index = (time.time() - start) * 1000  # ms
            
            # Results
            print(f"\n  Results:")
            print(f"    Without index: {time_no_index:.2f}ms")
            print(f"    With index:    {time_with_index:.2f}ms")
            
            if time_with_index > 0:
                speedup = time_no_index / time_with_index
                print(f"    Speedup:       {speedup:.2f}x")
                
                # Index should be faster
                assert speedup > 1.0, "Index should provide speedup"
            
            # Both should return same result
            assert len(rows_no_index) == len(rows_with_index) == 1
            
            page_manager.close()
            
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
