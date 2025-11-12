"""
Index manager for handling database index operations.
"""

from typing import Any, Dict, List, Optional, Tuple
from ..catalog import Catalog, IndexInfo
from ..page_manager import PageManager
from .btree import BTree


class IndexManager:
    """
    Manages database indexes using B-Trees.
    
    Responsibilities:
    - Create and drop indexes
    - Maintain indexes during insert/update/delete operations
    - Use indexes for query optimization
    """
    
    def __init__(self, catalog: Catalog, page_manager: PageManager):
        self.catalog = catalog
        self.page_manager = page_manager
        self._btrees: Dict[str, BTree] = {}  # Cache of open B-Trees
        
    def create_index(self, index_name: str, table_name: str, 
                    column_name: str, table_manager=None) -> None:
        """
        Create a new index on a table column.
        
        Args:
            index_name: Name of the new index
            table_name: Name of the table to index
            column_name: Name of the column to index
            table_manager: TableManager instance to scan table data
        """
        # Create index metadata in catalog first
        if not self.catalog.create_index(index_name, table_name, column_name):
            return  # Error already printed by catalog
        
        # Get the column index in the schema
        schema = self.catalog.get_table_schema(table_name)
        if not schema:
            print(f"❌ Table '{table_name}' not found")
            return
            
        column_index = None
        for idx, col in enumerate(schema.columns):
            if col['name'] == column_name:
                column_index = idx
                break
        
        if column_index is None:
            print(f"❌ Column '{column_name}' not found in table")
            return
        
        # Create new B-Tree
        btree = BTree(self.page_manager)
        
        # Build index by scanning table if table_manager provided
        if table_manager and schema.first_page_id is not None:
            print(f"🔨 Building index '{index_name}' on {table_name}({column_name})...")
            
            # Scan all pages in the table
            current_page_id = schema.first_page_id
            total_entries = 0
            
            while current_page_id is not None:
                page = self.page_manager.read_page(current_page_id)
                if not page:
                    break
                
                # Deserialize each row and extract the indexed column
                for row_id, record_bytes in enumerate(page.records):
                    try:
                        row = table_manager._deserialize_row(schema, record_bytes)
                        key = row[column_index]  # Extract indexed column value
                        
                        # Insert into B-Tree: key -> (page_id, row_id)
                        btree.insert(key, (current_page_id, row_id))
                        total_entries += 1
                    except Exception as e:
                        print(f"⚠️  Warning: Failed to index row {row_id} on page {current_page_id}: {e}")
                        continue
                
                current_page_id = page.next_page_id
            
            print(f"✅ Index '{index_name}' built with {total_entries} entries")
        
        # Update catalog with B-Tree root page
        if btree.root_page_id is not None:
            self.catalog.update_index_root(index_name, btree.root_page_id)
        
        # Cache the B-Tree
        self._btrees[index_name] = btree
    
    def drop_index(self, index_name: str, table_name: str) -> None:
        """
        Drop an existing index.
        
        Args:
            index_name: Name of the index to drop
            table_name: Name of the table the index is on
        """
        index = self.catalog.get_index(index_name)
        if index:
            # Remove from cache
            if index_name in self._btrees:
                del self._btrees[index_name]
            
            # Remove from catalog
            self.catalog.drop_index(index_name)
            
            # Free B-Tree pages
            self._free_btree_pages(index.root_page_id)
    
    def get_btree(self, index_name: str) -> Optional[BTree]:
        """Get a B-Tree index by name."""
        if index_name not in self._btrees:
            index = self.catalog.get_index(index_name)
            if index and index.root_page_id is not None:
                btree = BTree(self.page_manager)
                btree.root_page_id = index.root_page_id
                self._btrees[index_name] = btree
        
        return self._btrees.get(index_name)
    
    def insert_entry(self, table_name: str, column_values: Dict[str, Any],
                   page_id: int, row_id: int) -> None:
        """
        Insert entries into all indexes for a table.
        
        Args:
            table_name: Name of the table
            column_values: Dict of column name to value
            page_id: Page ID where row was inserted
            row_id: Row ID within page
        """
        indexes = self.catalog.get_indexes_for_table(table_name)
        for index in indexes:
            if index.column_name in column_values:
                btree = self.get_btree(index.index_name)
                if btree:
                    key = column_values[index.column_name]
                    btree.insert(key, (page_id, row_id))
    
    def delete_entry(self, table_name: str, column_values: Dict[str, Any],
                    page_id: int, row_id: int) -> None:
        """
        Delete specific entries from all indexes for a table.
        
        Args:
            table_name: Name of the table
            column_values: Dict of column name to value
            page_id: Page ID where row was deleted
            row_id: Row ID within page
        """
        indexes = self.catalog.get_indexes_for_table(table_name)
        for index in indexes:
            if index.column_name in column_values:
                btree = self.get_btree(index.index_name)
                if btree:
                    key = column_values[index.column_name]
                    # Delete specific (key, value) pair to handle duplicates correctly
                    btree.delete(key, value=(page_id, row_id))
    
    def search_index(self, index_name: str, key: Any) -> Optional[Tuple[int, int]]:
        """
        Search an index for a key (returns first match only).
        
        Args:
            index_name: Name of the index to search
            key: Key to search for
            
        Returns:
            Tuple of (page_id, row_id) if found, None if not found
        """
        btree = self.get_btree(index_name)
        if btree:
            return btree.search(key)
        return None
    
    def search_index_all(self, index_name: str, key: Any) -> List[Tuple[int, int]]:
        """
        Search an index for ALL occurrences of a key.
        Handles duplicate keys properly.
        
        Args:
            index_name: Name of the index to search
            key: Key to search for
            
        Returns:
            List of (page_id, row_id) tuples for all matches
        """
        btree = self.get_btree(index_name)
        if btree:
            return btree.search_all(key)
        return []
    
    def range_scan_index(self, index_name: str, min_key: Optional[Any] = None, 
                        max_key: Optional[Any] = None, min_inclusive: bool = True,
                        max_inclusive: bool = True) -> List[Tuple[int, int]]:
        """
        Perform a range scan on an index.
        
        Args:
            index_name: Name of the index to scan
            min_key: Minimum key (None for no lower bound)
            max_key: Maximum key (None for no upper bound)
            min_inclusive: Include min_key (True for >=, False for >)
            max_inclusive: Include max_key (True for <=, False for <)
            
        Returns:
            List of (page_id, row_id) tuples for all keys in range
            
        Examples:
            range_scan_index('idx_age', 18, 65) -> age >= 18 AND age <= 65
            range_scan_index('idx_price', 100, None) -> price >= 100
            range_scan_index('idx_date', None, '2025-01-01') -> date <= '2025-01-01'
        """
        btree = self.get_btree(index_name)
        if btree:
            return btree.range_scan(min_key, max_key, min_inclusive, max_inclusive)
        return []
    
    def _free_btree_pages(self, root_page_id: Optional[int]) -> None:
        """
        Recursively free all pages in a B-Tree.
        
        Args:
            root_page_id: Root page ID of the B-Tree
        """
        if root_page_id is None:
            return
        
        # Load the root node
        page = self.page_manager.read_page(root_page_id)
        if not page or not page.records:
            return
        
        try:
            from .btree import BTreeNode
            node = BTreeNode.deserialize(page.records[0])
            
            # Recursively free child pages
            if not node.is_leaf:
                for child_id in node.children:
                    self._free_btree_pages(child_id)
            
            # Free this page (commented out - page deallocation not implemented yet)
            # self.page_manager.free_page(root_page_id)
        except Exception:
            # Silently ignore deserialization errors during cleanup
            pass