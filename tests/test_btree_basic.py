"""
Basic B-Tree functionality tests.
"""

import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage import PageManager, Catalog, TableManager
from src.storage.indexing.index_manager import IndexManager


class TestBTreeBasicOperations:
    """Test basic B-Tree insert and search operations."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database with sample data."""
        db_file = tmp_path / "test_btree.db"
        page_manager = PageManager(str(db_file))
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
        test_data = [
            [1, 'alice@example.com', 25],
            [2, 'bob@example.com', 30],
            [3, 'charlie@example.com', 35],
            [4, 'diana@example.com', 28],
            [5, 'eve@example.com', 32]
        ]
        
        for row in test_data:
            table_manager.insert_row('users', row)
        
        yield page_manager, catalog, index_manager, table_manager
        
        # Cleanup
        page_manager.close()
        if db_file.exists():
            os.remove(db_file)
    
    def test_btree_insert_and_search(self, temp_db):
        """Test that B-Tree can insert and retrieve values."""
        page_manager, catalog, index_manager, table_manager = temp_db
        
        # Create index on email column
        index_manager.create_index('idx_email', 'users', 'email')
        
        # Verify index was created
        assert 'idx_email' in catalog.indexes
        
        # Search for existing emails
        btree = index_manager.get_btree('idx_email')
        assert btree is not None
        
        result = btree.search('alice@example.com')
        assert result is not None, "Should find alice@example.com"
        page_id, row_id = result
        assert isinstance(page_id, int)
        assert isinstance(row_id, int)
        
        result = btree.search('bob@example.com')
        assert result is not None, "Should find bob@example.com"
        
        result = btree.search('eve@example.com')
        assert result is not None, "Should find eve@example.com"
    
    def test_btree_search_nonexistent(self, temp_db):
        """Test that B-Tree returns None for non-existent keys."""
        page_manager, catalog, index_manager, table_manager = temp_db
        
        # Create index
        index_manager.create_index('idx_email', 'users', 'email')
        btree = index_manager.get_btree('idx_email')
        
        # Search for non-existent email
        result = btree.search('nonexistent@example.com')
        assert result is None, "Should return None for non-existent key"
    
    def test_index_maintenance_on_insert(self, temp_db):
        """Test that indexes are automatically maintained on insert."""
        page_manager, catalog, index_manager, table_manager = temp_db
        
        # Create index on existing data
        index_manager.create_index('idx_email', 'users', 'email')
        btree = index_manager.get_btree('idx_email')
        
        # Insert new row
        table_manager.insert_row('users', [6, 'frank@example.com', 40])
        
        # Verify new row is in index
        result = btree.search('frank@example.com')
        assert result is not None, "Newly inserted row should be in index"
    
    def test_multiple_indexes_on_same_table(self, temp_db):
        """Test creating multiple indexes on different columns."""
        page_manager, catalog, index_manager, table_manager = temp_db
        
        # Create indexes on email and age
        index_manager.create_index('idx_email', 'users', 'email')
        index_manager.create_index('idx_age', 'users', 'age')
        
        # Verify both indexes work
        email_btree = index_manager.get_btree('idx_email')
        age_btree = index_manager.get_btree('idx_age')
        
        assert email_btree.search('alice@example.com') is not None
        assert age_btree.search(25) is not None
        assert age_btree.search(30) is not None
        assert age_btree.search(35) is not None
    
    def test_btree_with_many_inserts(self, temp_db):
        """Test B-Tree with enough data to trigger node splits."""
        page_manager, catalog, index_manager, table_manager = temp_db
        
        # Create index
        index_manager.create_index('idx_id', 'users', 'id')
        btree = index_manager.get_btree('idx_id')
        
        # Insert many more rows to trigger splits (order=4 means max 7 keys per node)
        for i in range(6, 25):
            table_manager.insert_row('users', [i, f'user{i}@example.com', 20 + i])
        
        # Verify all can be found
        for i in range(1, 25):
            result = btree.search(i)
            assert result is not None, f"Should find id={i}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
