"""
Unit Tests for the AlpacaDB Storage Engine

These tests verify page serialization, file I/O, catalog
management, and basic table operations.

Requires: pytest, pytest-cov
Run from root: pytest
"""

import os
import shutil
import pytest
from src.storage import (
    Page, PAGE_SIZE, HEADER_SIZE,
    PageManager,
    Catalog,
    TableManager
)

# --- Test Fixtures ---

@pytest.fixture
def db_path():
    """Fixture to provide a clean test database path."""
    TEST_DIR = "data_test"
    TEST_DB_FILE = os.path.join(TEST_DIR, "test_alpaca.db")
    
    # Setup: Clean directory before test
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)
    
    yield TEST_DB_FILE  # This is what the test function gets
    
    # Teardown: Clean up after test
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)

@pytest.fixture
def page_manager(db_path):
    """Fixture to provide an initialized PageManager."""
    pm = PageManager(db_path)
    yield pm
    pm.close()

@pytest.fixture
def catalog(page_manager):
    """Fixture to provide an initialized Catalog."""
    return Catalog(page_manager)

@pytest.fixture
def table_manager(page_manager, catalog):
    """Fixture to provide an initialized TableManager."""
    return TableManager(page_manager, catalog)


# --- Test Cases ---

class TestPage:
    def test_page_init(self):
        page = Page(page_id=1, page_type=1)
        assert page.page_id == 1
        assert page.page_type == 1
        assert page.get_free_space() == PAGE_SIZE - HEADER_SIZE

    def test_add_record(self):
        page = Page(page_id=1)
        record = b'hello world'
        record_size = len(record) + 2  # + length prefix
        
        initial_free = page.get_free_space()
        assert page.add_record(record) == True
        assert len(page.records) == 1
        assert page.records[0] == record
        assert page.get_free_space() == initial_free - record_size

    def test_page_full(self):
        page = Page(page_id=1)
        record = b'A' * 1000
        
        for _ in range(4):  # 4 * (1000 + 2) = 4008 bytes
            assert page.add_record(record) == True
        
        assert page.get_free_space() < (1000 + 2)
        assert page.add_record(record) == False  # Should fail

    def test_serialize_deserialize_cycle(self):
        page = Page(page_id=5, page_type=1)
        page.add_record(b'record_one')
        page.add_record(b'record_two_is_longer')
        page.next_page_id = 6
        
        # Serialize
        raw_bytes = page.serialize()
        assert len(raw_bytes) == PAGE_SIZE
        
        # Deserialize
        new_page = Page.deserialize(raw_bytes)
        assert new_page.page_id == 5
        assert new_page.page_type == 1
        assert new_page.next_page_id == 6
        assert len(new_page.records) == 2
        assert new_page.records[0] == b'record_one'
        assert new_page.records[1] == b'record_two_is_longer'
        assert new_page.get_free_space() == page.get_free_space()

    def test_checksum_corruption(self):
        page = Page(page_id=1)
        page.add_record(b'good data')
        raw_bytes = page.serialize()
        
        # Corrupt the data
        corrupted_bytes = bytearray(raw_bytes)
        corrupted_bytes[HEADER_SIZE + 3] = 0xAA  # Flip a bit
        
        with pytest.raises(ValueError, match="corrupted"):
            Page.deserialize(bytes(corrupted_bytes))

class TestPageManager:
    def test_init_creates_file(self, db_path):
        assert os.path.exists(db_path) == False
        pm = PageManager(db_path)
        assert os.path.exists(db_path) == True
        pm.close()

    def test_init_opens_existing(self, page_manager):
        assert page_manager.get_num_pages() == 1  # Meta page 0
        
        path = page_manager.db_file_path
        page_manager.close()
        
        # Open again
        pm2 = PageManager(path)
        assert pm2.get_num_pages() == 1
        pm2.close()

    def test_allocate_page(self, page_manager):
        assert page_manager.get_num_pages() == 1
        new_page = page_manager.allocate_page()
        assert new_page.page_id == 1
        assert page_manager.get_num_pages() == 2

    def test_read_write_page(self, page_manager):
        page = page_manager.allocate_page()
        page_id = page.page_id
        
        page.add_record(b'test data')
        page_manager.write_page(page)
        
        # Read back
        read_page = page_manager.read_page(page_id)
        assert read_page is not None
        assert read_page.page_id == page_id
        assert len(read_page.records) == 1
        assert read_page.records[0] == b'test data'

class TestCatalogAndTableManager:
    @pytest.fixture
    def setup_table(self, catalog):
        schema = [
            {'name': 'id', 'type': 'INT', 'nullable': False},
            {'name': 'name', 'type': 'STRING', 'nullable': False},
            {'name': 'active', 'type': 'BOOL', 'nullable': True}
        ]
        assert catalog.create_table('users', schema) == True
        return schema

    def test_create_table(self, catalog, setup_table):
        schema = catalog.get_table_schema('users')
        assert schema is not None
        assert schema.table_name == 'users'
        assert len(schema.columns) == 3
        assert schema.columns[0]['name'] == 'id'

    def test_catalog_persistence(self, page_manager, db_path):
        catalog = Catalog(page_manager)
        schema_def = [{'name': 'col1', 'type': 'STRING'}]
        catalog.create_table('test_table', schema_def)
        page_manager.close()
        
        # Re-open and check
        pm2 = PageManager(db_path)
        catalog2 = Catalog(pm2)
        assert catalog2.list_tables() == ['test_table']
        schema = catalog2.get_table_schema('test_table')
        assert schema.columns[0]['name'] == 'col1'
        pm2.close()

    def test_insert_select_cycle(self, table_manager, setup_table):
        # Insert
        assert table_manager.insert_row('users', [1, 'Alice', True]) == True
        assert table_manager.insert_row('users', [2, 'Bob', False]) == True
        assert table_manager.insert_row('users', [3, 'Charlie', None]) == True
        
        # Select
        rows = table_manager.select_all('users')
        assert len(rows) == 3
        assert rows[0] == [1, 'Alice', True]
        assert rows[1] == [2, 'Bob', False]
        assert rows[2] == [3, 'Charlie', None]

    def test_insert_validations(self, table_manager, setup_table):
        # Wrong table
        assert table_manager.insert_row('bad_table', [1]) == False
        # Wrong column count
        assert table_manager.insert_row('users', [1, 'Alice']) == False
        # Non-nullable violation
        with pytest.raises(ValueError, match="cannot be NULL"):
            table_manager._serialize_row(
                table_manager.catalog.get_table_schema('users'), 
                [1, None, True]
            )

    def test_page_chaining(self, table_manager, catalog, setup_table):
        # Insert records until pages chain
        schema = catalog.get_table_schema('users')
        
        # Find rough size: 1 INT + 1 Bool + 50-char string
        # (1+4) + (1+2+50) + (1+1) + (2-byte len) = ~62 bytes
        # 4032 / 62 = ~65 records per page
        
        num_rows = 250
        for i in range(num_rows):
            name = f"User {i}"
            assert table_manager.insert_row('users', [i, name, True]) == True
        
        # Check that the first page now has a next_page_id
        first_page = table_manager.page_manager.read_page(schema.first_page_id)
        assert first_page.next_page_id is not None
        
        # Check that we get all rows back
        rows = table_manager.select_all('users')
        assert len(rows) == num_rows
        assert rows[0] == [0, 'User 0', True]
        assert rows[-1] == [num_rows - 1, f"User {num_rows - 1}", True]