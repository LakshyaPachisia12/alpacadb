"""
Phase 3 Tests: Range Scans and Incremental Index Maintenance

Tests:
1. B+Tree range_search() functionality
2. B+Tree delete_entry() functionality  
3. Leaf node linking
4. IndexRangeScanOperator
5. Incremental index maintenance performance
"""

import os
import tempfile
import shutil
import pytest
from src.storage.catalog import Catalog
from src.storage.page_manager import PageManager
from src.storage.table_manager import TableManager
from src.storage.indexing.index_manager import IndexManager
from src.storage.indexing.btree import BTree
from src.executor.operators import IndexRangeScanOperator


class TestPhase3RangeScans:
    """Test range search functionality"""
    
    def setup_method(self):
        """Set up fresh test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.db_file = os.path.join(self.test_dir, "test.db")
        self.page_manager = PageManager(self.db_file)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
        self.index_manager = IndexManager(self.catalog, self.page_manager)
    
    def teardown_method(self):
        """Clean up test environment"""
        self.page_manager.close()
        shutil.rmtree(self.test_dir)
    
    def test_range_search_basic(self):
        """Test basic range search on B+Tree"""
        # Create B+Tree and insert values
        btree = BTree(self.page_manager, order=4)
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        
        for val in values:
            btree.insert(val, (0, val))  # Use val as row_id for testing
        
        # Test range [30, 70] inclusive
        results = btree.range_search(30, 70, include_start=True, include_end=True)
        result_keys = [val for _, val in results]
        assert result_keys == [30, 40, 50, 60, 70], f"Expected [30,40,50,60,70], got {result_keys}"
        
        # Test range (30, 70) exclusive
        results = btree.range_search(30, 70, include_start=False, include_end=False)
        result_keys = [val for _, val in results]
        assert result_keys == [40, 50, 60], f"Expected [40,50,60], got {result_keys}"
        
        # Test range [30, 70) half-open
        results = btree.range_search(30, 70, include_start=True, include_end=False)
        result_keys = [val for _, val in results]
        assert result_keys == [30, 40, 50, 60], f"Expected [30,40,50,60], got {result_keys}"
    
    def test_range_search_unbounded(self):
        """Test range search with unbounded ranges"""
        btree = BTree(self.page_manager, order=4)
        values = [10, 20, 30, 40, 50]
        
        for val in values:
            btree.insert(val, (0, val))
        
        # Test [None, 30] - all values <= 30
        results = btree.range_search(None, 30, include_end=True)
        result_keys = [val for _, val in results]
        assert result_keys == [10, 20, 30], f"Expected [10,20,30], got {result_keys}"
        
        # Test [40, None] - all values >= 40
        results = btree.range_search(40, None, include_start=True)
        result_keys = [val for _, val in results]
        assert result_keys == [40, 50], f"Expected [40,50], got {result_keys}"
    
    def test_range_search_empty_results(self):
        """Test range search with no matching values"""
        btree = BTree(self.page_manager, order=4)
        values = [10, 20, 30, 50, 60]
        
        for val in values:
            btree.insert(val, (0, val))
        
        # Test range with no values [35, 45]
        results = btree.range_search(35, 45)
        assert results == [], f"Expected empty results, got {results}"
    
    def test_delete_entry_basic(self):
        """Test delete_entry() removes specific entries"""
        btree = BTree(self.page_manager, order=4)
        
        # Insert values with duplicates
        btree.insert(10, (1, 1))
        btree.insert(20, (1, 2))
        btree.insert(20, (1, 3))  # Duplicate key
        btree.insert(30, (1, 4))
        
        # Delete one of the duplicates
        success = btree.delete_entry(20, (1, 2))
        assert success, "delete_entry should return True on success"
        
        # Verify only one entry with key=20 was deleted
        results = btree.search_all(20)
        assert len(results) == 1, f"Expected 1 entry with key=20, got {len(results)}"
        assert results[0] == (1, 3), f"Expected (1, 3), got {results[0]}"
        
        # Verify other entries still exist
        assert btree.search(10) == (1, 1)
        assert btree.search(30) == (1, 4)
    
    def test_delete_entry_nonexistent(self):
        """Test delete_entry() returns False for nonexistent entries"""
        btree = BTree(self.page_manager, order=4)
        btree.insert(10, (1, 1))
        
        # Try to delete nonexistent entry
        success = btree.delete_entry(20, (1, 1))
        assert not success, "delete_entry should return False for nonexistent entry"
        
        # Try to delete with wrong value
        success = btree.delete_entry(10, (2, 2))
        assert not success, "delete_entry should return False for wrong value"
        
        # Original entry should still exist
        assert btree.search(10) == (1, 1)


class TestPhase3IndexRangeScan:
    """Test IndexRangeScanOperator"""
    
    def setup_method(self):
        """Set up fresh test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.db_file = os.path.join(self.test_dir, "test.db")
        self.page_manager = PageManager(self.db_file)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
        self.index_manager = IndexManager(self.catalog, self.page_manager)
        
        # Create test table with correct types
        self.catalog.create_table(
            'employees',
            [
                {'name': 'id', 'type': 'INT', 'nullable': False},
                {'name': 'name', 'type': 'STRING', 'nullable': True},
                {'name': 'salary', 'type': 'INT', 'nullable': False},
            ]
        )
        
        # Insert test data - use manual insertion since we're testing low-level
        for i in range(1, 11):
            row_data = [i, f'Employee{i}', i * 10000]  # List, not dict!
            self.table_manager.insert_row('employees', row_data)
        
        # Create index on salary - pass table_manager to build index
        self.index_manager.create_index('idx_salary', 'employees', 'salary', self.table_manager)
    
    def teardown_method(self):
        """Clean up test environment"""
        self.page_manager.close()
        shutil.rmtree(self.test_dir)
    
    def test_index_range_scan_operator(self):
        """Test IndexRangeScanOperator returns correct rows"""
        # Range scan for salaries [30000, 70000]
        operator = IndexRangeScanOperator(
            self.table_manager,
            self.index_manager,
            'employees',
            'idx_salary',
            start_key=30000,
            end_key=70000,
            include_start=True,
            include_end=True,
            column_names=['id', 'name', 'salary']
        )
        
        results = operator.execute()
        
        # Should get employees 3, 4, 5, 6, 7 (salaries 30k-70k)
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        
        salaries = [row[2] for row in results]
        assert salaries == [30000, 40000, 50000, 60000, 70000], \
            f"Expected salaries [30k-70k], got {salaries}"
    
    def test_index_range_scan_open_range(self):
        """Test IndexRangeScanOperator with open ranges"""
        # Range scan for salaries > 80000
        operator = IndexRangeScanOperator(
            self.table_manager,
            self.index_manager,
            'employees',
            'idx_salary',
            start_key=80000,
            end_key=None,
            include_start=False,
            include_end=True,
            column_names=['id', 'name', 'salary']
        )
        
        results = operator.execute()
        
        # Should get employees 9, 10 (salaries > 80k)
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        salaries = [row[2] for row in results]
        assert salaries == [90000, 100000], \
            f"Expected salaries [90k, 100k], got {salaries}"


class TestPhase3IncrementalMaintenance:
    """Test incremental index maintenance performance"""
    
    def setup_method(self):
        """Set up fresh test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.db_file = os.path.join(self.test_dir, "test.db")
        self.page_manager = PageManager(self.db_file)
        self.catalog = Catalog(self.page_manager)
        self.table_manager = TableManager(self.page_manager, self.catalog)
        self.index_manager = IndexManager(self.catalog, self.page_manager)
        
        # Create test table
        self.catalog.create_table(
            'products',
            [
                {'name': 'id', 'type': 'INT', 'nullable': False},
                {'name': 'name', 'type': 'STRING', 'nullable': True},
                {'name': 'price', 'type': 'INT', 'nullable': False},
            ]
        )
        
        # Insert test data
        for i in range(1, 21):
            row_data = [i, f'Product{i}', i * 100]
            self.table_manager.insert_row('products', row_data)
        
        # Create index on price - pass table_manager to build index
        self.index_manager.create_index('idx_price', 'products', 'price', self.table_manager)
    
    def teardown_method(self):
        """Clean up test environment"""
        self.page_manager.close()
        shutil.rmtree(self.test_dir)
    
    def test_incremental_delete(self):
        """Test that delete uses incremental maintenance"""
        # Verify initial index has all entries
        results = self.index_manager.range_search_index('idx_price', 0, 10000)
        assert len(results) == 20, f"Expected 20 entries, got {len(results)}"
        
        # Get all rows and find the one to delete
        all_rows = self.table_manager.select_all('products')
        row_to_delete = None
        for row in all_rows:
            if row[0] == 10:  # id = 10
                row_to_delete = row
                break
        
        assert row_to_delete is not None, "Should find row with id=10"
        
        # Manually delete the row and its index entries
        # This simulates what would happen in a DELETE operation
        schema = self.catalog.get_table_schema('products')
        page_id = schema.first_page_id
        found = False
        
        while page_id is not None and not found:
            page = self.page_manager.read_page(page_id)
            for row_id in range(len(page.records)):
                record_bytes = page.records[row_id]
                row = self.table_manager._deserialize_row(schema, record_bytes)
                if row[0] == 10:  # id = 10
                    # Delete from index
                    col_values = {'id': row[0], 'name': row[1], 'price': row[2]}
                    self.index_manager.delete_entry('products', col_values, page_id, row_id)
                    found = True
                    break
            if not found:
                page_id = page.next_page_id
        
        # Verify index was updated incrementally
        results = self.index_manager.range_search_index('idx_price', 0, 10000)
        assert len(results) == 19, f"Expected 19 entries after delete, got {len(results)}"
        
        # Verify deleted entry is gone
        price_1000 = self.index_manager.search_index_all('idx_price', 1000)
        assert len(price_1000) == 0, "Deleted entry should not be in index"
        
        # Verify other entries still exist
        price_500 = self.index_manager.search_index_all('idx_price', 500)
        assert len(price_500) == 1, "Non-deleted entries should still exist"


class TestPhase3LeafLinking:
    """Test leaf node linking for range scans"""
    
    def setup_method(self):
        """Set up fresh test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.db_file = os.path.join(self.test_dir, "test.db")
        self.page_manager = PageManager(self.db_file)
    
    def teardown_method(self):
        """Clean up test environment"""
        self.page_manager.close()
        shutil.rmtree(self.test_dir)
    
    def test_leaf_linking_after_split(self):
        """Test that leaf nodes are properly linked after splits"""
        btree = BTree(self.page_manager, order=4)
        
        # Insert enough values to cause splits (order=4 means max 7 keys per node)
        for i in range(1, 16):
            btree.insert(i, (0, i))
        
        # Find leftmost leaf
        leftmost = btree._find_leftmost_leaf()
        assert leftmost is not None, "Should find leftmost leaf"
        
        # Traverse leaves using links
        visited_keys = []
        current = leftmost
        while current is not None:
            visited_keys.extend(current.keys)
            if current.next_leaf_page_id is not None:
                current = btree._load_node(current.next_leaf_page_id)
            else:
                break
        
        # Should have visited all keys in order
        assert visited_keys == list(range(1, 16)), \
            f"Expected keys 1-15 in order, got {visited_keys}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
