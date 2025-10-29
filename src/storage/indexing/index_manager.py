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
        # Create new B-Tree
        btree = BTree(self.page_manager)
        
        # Build index by scanning table
        table = self.catalog.get_table(table_name)
        for page_id in table.data_pages:
            page = self.page_manager.read_page(page_id)
            for row_id, row in enumerate(page.read_rows()):
                key = row[column_name]
                btree.insert(key, (page_id, row_id))
        
        # Store index metadata
        index_info = IndexInfo(
            index_name=index_name,
            table_name=table_name,
            column_name=column_name,
            index_type=index_type,
            root_page_id=btree.root_page_id
        )
        self.catalog.add_index(index_info)
        
        # Cache the B-Tree
        self._btrees[index_name] = btree
    
    def drop_index(self, index_name: str, table_name: str) -> None:
        """
        Drop an existing index.
        
        Args:
            index_name: Name of the index to drop
            table_name: Name of the table the index is on
        """
        index = self.catalog.get_index(index_name, table_name)
        if index:
            # Remove from cache
            if index_name in self._btrees:
                del self._btrees[index_name]
            
            # Remove from catalog
            self.catalog.remove_index(index_name, table_name)
            
            # Free B-Tree pages
            self._free_btree_pages(index.root_page_id)
    
    def get_btree(self, index_name: str) -> Optional[BTree]:
        """Get a B-Tree index by name."""
        if index_name not in self._btrees:
            index = self.catalog.get_index_by_name(index_name)
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
        node = BTree._deserialize_node(page.read_data())
        
        # Recursively free child pages
        if not node.is_leaf:
            for child_id in node.children:
                self._free_btree_pages(child_id)
        
        # Free this page
        self.page_manager.free_page(root_page_id)