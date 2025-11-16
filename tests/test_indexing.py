"""
Tests for indexing functionality.

Tests CREATE INDEX, DROP INDEX, and index validation.
"""

import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.query import Lexer, Parser
from src.query.ast_nodes import CreateIndexNode, DropIndexNode
from src.storage import PageManager, Catalog


class TestIndexParsing:
    """Test parsing of index-related SQL commands."""
    
    def test_create_index_basic(self):
        """Test basic CREATE INDEX parsing."""
        sql = "CREATE INDEX idx_email ON users(email);"
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert isinstance(ast, CreateIndexNode)
        assert ast.index_name == "idx_email"
        assert ast.table_name == "users"
        assert ast.column_name == "email"
    
    def test_create_index_no_semicolon(self):
        """Test CREATE INDEX without semicolon."""
        sql = "CREATE INDEX idx_age ON users(age)"
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert isinstance(ast, CreateIndexNode)
        assert ast.index_name == "idx_age"
        assert ast.column_name == "age"
    
    def test_create_index_with_using(self):
        """Test CREATE INDEX with USING clause."""
        sql = "CREATE INDEX idx_name ON users(name) USING BTREE;"
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert isinstance(ast, CreateIndexNode)
        assert ast.index_name == "idx_name"
    
    def test_drop_index_basic(self):
        """Test basic DROP INDEX parsing."""
        sql = "DROP INDEX idx_email ON users;"
        lexer = Lexer(sql)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        
        assert isinstance(ast, DropIndexNode)
        assert ast.index_name == "idx_email"
        assert ast.table_name == "users"
    
    def test_multiple_indexes_on_same_table(self):
        """Test creating multiple indexes on the same table."""
        indexes = [
            "CREATE INDEX idx_email ON users(email);",
            "CREATE INDEX idx_age ON users(age);",
            "CREATE INDEX idx_name ON users(name);"
        ]
        
        for sql in indexes:
            lexer = Lexer(sql)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            ast = parser.parse()
            assert isinstance(ast, CreateIndexNode)


class TestIndexCatalog:
    """Test index operations in the catalog."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_file = tmp_path / "test_index.db"
        page_manager = PageManager(str(db_file))
        catalog = Catalog(page_manager)
        
        # Create a test table
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': True},
            {'name': 'email', 'type': 'STRING', 'nullable': True},
            {'name': 'age', 'type': 'INT', 'nullable': True}
        ]
        catalog.create_table('users', columns)
        
        yield catalog, page_manager
        
        # Cleanup - close the page manager before deleting
        page_manager.close()
        if db_file.exists():
            os.remove(db_file)
    
    def test_create_index_success(self, temp_db):
        """Test successful index creation."""
        catalog, _ = temp_db
        
        success = catalog.create_index('idx_email', 'users', 'email')
        assert success is True
        assert 'idx_email' in catalog.indexes
        
        index = catalog.get_index('idx_email')
        assert index is not None
        assert index.table_name == 'users'
        assert index.column_name == 'email'
    
    def test_create_duplicate_index(self, temp_db):
        """Test that duplicate index names are rejected."""
        catalog, _ = temp_db
        
        # Create first index
        success = catalog.create_index('idx_email', 'users', 'email')
        assert success is True
        
        # Try to create duplicate
        success = catalog.create_index('idx_email', 'users', 'age')
        assert success is False
        assert len(catalog.indexes) == 1
    
    def test_create_index_on_nonexistent_table(self, temp_db):
        """Test creating index on non-existent table."""
        catalog, _ = temp_db
        
        success = catalog.create_index('idx_test', 'nonexistent', 'col')
        assert success is False
        assert 'idx_test' not in catalog.indexes
    
    def test_create_index_on_nonexistent_column(self, temp_db):
        """Test creating index on non-existent column."""
        catalog, _ = temp_db
        
        success = catalog.create_index('idx_test', 'users', 'nonexistent_col')
        assert success is False
        assert 'idx_test' not in catalog.indexes
    
    def test_drop_index_success(self, temp_db):
        """Test successful index dropping."""
        catalog, _ = temp_db
        
        # Create index
        catalog.create_index('idx_email', 'users', 'email')
        assert 'idx_email' in catalog.indexes
        
        # Drop index
        success = catalog.drop_index('idx_email')
        assert success is True
        assert 'idx_email' not in catalog.indexes
    
    def test_drop_nonexistent_index(self, temp_db):
        """Test dropping non-existent index."""
        catalog, _ = temp_db
        
        success = catalog.drop_index('nonexistent_idx')
        assert success is False
    
    def test_get_indexes_for_table(self, temp_db):
        """Test getting all indexes for a specific table."""
        catalog, _ = temp_db
        
        # Create multiple indexes
        catalog.create_index('idx_email', 'users', 'email')
        catalog.create_index('idx_age', 'users', 'age')
        catalog.create_index('idx_name', 'users', 'name')
        
        indexes = catalog.get_indexes_for_table('users')
        assert len(indexes) == 3
        
        index_names = [idx.index_name for idx in indexes]
        assert 'idx_email' in index_names
        assert 'idx_age' in index_names
        assert 'idx_name' in index_names
    
    def test_list_all_indexes(self, temp_db):
        """Test listing all indexes."""
        catalog, _ = temp_db
        
        catalog.create_index('idx_email', 'users', 'email')
        catalog.create_index('idx_age', 'users', 'age')
        
        all_indexes = catalog.list_indexes()
        assert len(all_indexes) == 2
        assert 'idx_email' in all_indexes
        assert 'idx_age' in all_indexes
    
    def test_index_persistence(self, tmp_path):
        """Test that indexes are persisted to disk."""
        db_file = tmp_path / "test_persist.db"
        
        # Create database and index
        page_manager1 = PageManager(str(db_file))
        catalog1 = Catalog(page_manager1)
        
        columns = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'email', 'type': 'STRING', 'nullable': True}
        ]
        catalog1.create_table('users', columns)
        catalog1.create_index('idx_email', 'users', 'email')
        
        # Close and reopen
        page_manager1.close()
        del catalog1
        del page_manager1
        
        page_manager2 = PageManager(str(db_file))
        catalog2 = Catalog(page_manager2)
        
        # Check if index persisted
        assert 'idx_email' in catalog2.indexes
        index = catalog2.get_index('idx_email')
        assert index.table_name == 'users'
        assert index.column_name == 'email'
        
        # Cleanup - close before deleting
        page_manager2.close()
        del catalog2
        del page_manager2
        if db_file.exists():
            os.remove(db_file)


class TestIndexValidation:
    """Test edge cases and validation."""
    
    def test_index_name_case_sensitivity(self):
        """Test that index names are case-sensitive."""
        sql1 = "CREATE INDEX idx_email ON users(email);"
        sql2 = "CREATE INDEX IDX_EMAIL ON users(email);"
        
        lexer1 = Lexer(sql1)
        ast1 = Parser(lexer1.tokenize()).parse()
        
        lexer2 = Lexer(sql2)
        ast2 = Parser(lexer2.tokenize()).parse()
        
        assert ast1.index_name == "idx_email"
        assert ast2.index_name == "IDX_EMAIL"
        assert ast1.index_name != ast2.index_name
    
    def test_index_on_multiple_tables(self, tmp_path):
        """Test creating indexes with same name on different tables."""
        db_file = tmp_path / "test_multi_table.db"
        page_manager = PageManager(str(db_file))
        catalog = Catalog(page_manager)
        
        # Create two tables
        columns = [{'name': 'id', 'type': 'INT', 'nullable': False}]
        catalog.create_table('users', columns)
        catalog.create_table('orders', columns)
        
        # Try to create same index name on different tables
        success1 = catalog.create_index('idx_id', 'users', 'id')
        success2 = catalog.create_index('idx_id', 'orders', 'id')
        
        # Second should fail (same index name)
        assert success1 is True
        assert success2 is False
        
        # Cleanup - close before deleting
        page_manager.close()
        del catalog
        del page_manager
        if db_file.exists():
            os.remove(db_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
