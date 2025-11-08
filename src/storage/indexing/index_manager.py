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
                    column_name: str, index_type: str = "B-Tree") -> None:
        """
        Create a new index on a table column.
        
        Args:
            index_name: Name of the new index
            table_name: Name of the table to index
            column_name: Name of the column to index
            index_type: Type of index (currently only B-Tree supported)
        """
        # Validate table exists
        table_schema = self.catalog.get_table_schema(table_name)
        if not table_schema:
            raise ValueError(f"Table '{table_name}' does not exist")
        
        # Create new B-Tree
        btree = BTree(self.page_manager)
        
        # Build index by scanning table
        if table_schema.first_page_id is None:
            # Empty table - just create empty index
            index_info = IndexInfo(
                index_name=index_name,
                table_name=table_name,
                column_name=column_name,
                index_type=index_type,
                root_page_id=btree.root_page_id
            )
            self.catalog.indexes[index_name] = index_info
            self.catalog._save_catalog()
            self._btrees[index_name] = btree
            return
        
        # Find column index
        col_index = None
        for i, col in enumerate(table_schema.columns):
            if col['name'] == column_name:
                col_index = i
                break
        
        if col_index is None:
            raise ValueError(f"Column '{column_name}' not found in table '{table_name}'")
        
        # Scan table and build index
        current_page_id = table_schema.first_page_id
        while current_page_id is not None:
            page = self.page_manager.read_page(current_page_id)
            
            # Use TableManager to deserialize rows
            from ..table_manager import TableManager
            tm = TableManager(self.page_manager, self.catalog)
            
            for row_id, record_bytes in enumerate(page.records):
                try:
                    row = tm._deserialize_row(table_schema, record_bytes)
                    key = row[col_index]
                    btree.insert(key, (current_page_id, row_id))
                except Exception as e:
                    print(f"⚠️  Warning: Failed to index row: {e}")
                    continue
            
            current_page_id = page.next_page_id
        
        # Store index metadata
        index_info = IndexInfo(
            index_name=index_name,
            table_name=table_name,
            column_name=column_name,
            index_type=index_type,
            root_page_id=btree.root_page_id
        )
        self.catalog.indexes[index_name] = index_info
        self.catalog._save_catalog()
        
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
            
            # TODO: Free B-Tree pages (requires PageManager.free_page implementation)
            # self._free_btree_pages(index.root_page_id)
    
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
                    # Update root_page_id in case it changed
                    index.root_page_id = btree.root_page_id
                    self.catalog._save_catalog()
    
    def delete_entry(self, table_name: str, column_values: Dict[str, Any],
                    page_id: int, row_id: int) -> None:
        """
        Delete entries from all indexes for a table.
        
        Args:
            table_name: Name of the table
            column_values: Dict of column name to value
            page_id: Page ID where row was
            row_id: Row ID within page
        """
        indexes = self.catalog.get_indexes_for_table(table_name)
        for index in indexes:
            if index.column_name in column_values:
                btree = self.get_btree(index.index_name)
                if btree:
                    key = column_values[index.column_name]
                    btree.delete(key)
    
    def search_index(self, index_name: str, key: Any) -> Optional[Tuple[int, int]]:
        """
        Search an index for a key.
        
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
        Search an index for ALL occurrences of a key (handles duplicates).
        
        Args:
            index_name: Name of the index to search
            key: Key to search for
            
        Returns:
            List of (page_id, row_id) tuples for all matching entries
        """
        btree = self.get_btree(index_name)
        if btree:
            return btree.search_all(key)
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
        
        # Create temporary BTree to deserialize the node
        btree = BTree(self.page_manager)    
        node = btree._deserialize_node(page.records[0])
        
        # Recursively free child pages
        if not node.is_leaf:
            for child_id in node.children:
                self._free_btree_pages(child_id)
        
        # Free this page
        self.page_manager.free_page(root_page_id)
    
    def rebuild_indexes_for_table(self, table_name: str) -> None:
        """
        Rebuild all indexes for a table.
        
        This is a temporary solution for UPDATE/DELETE operations since
        B-Tree delete is not yet implemented. After rewriting a table,
        we drop and recreate all indexes to maintain correctness.
        
        TODO: Replace with proper B-Tree delete implementation in Phase 3.
        
        Args:
            table_name: Name of the table whose indexes should be rebuilt
        """
        # Get all indexes for this table
        indexes = self.catalog.get_indexes_for_table(table_name)
        
        if not indexes:
            return  # No indexes to rebuild
        
        print(f"🔄 Rebuilding {len(indexes)} index(es) for table '{table_name}'...")
        
        # Store index definitions
        index_definitions = []
        for index in indexes:
            index_definitions.append({
                'index_name': index.index_name,
                'column_name': index.column_name,
                'index_type': index.index_type
            })
        
        # Drop all indexes
        for index_def in index_definitions:
            self.drop_index(index_def['index_name'], table_name)
        
        # Recreate all indexes
        for index_def in index_definitions:
            self.create_index(
                index_def['index_name'],
                table_name,
                index_def['column_name'],
                index_def['index_type']
            )
        
        print(f"✅ Index rebuild complete")


