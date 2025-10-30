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
                    column_name: str, index_type: str = "B-Tree", order: Optional[int] = None) -> None:
        """
        Create a new index on a table column with optimal B-Tree order.
        
        Args:
            index_name: Name of the new index
            table_name: Name of the table to index
            column_name: Name of the column to index
            index_type: Type of index (currently only B-Tree supported)
            order: B-Tree order (if None, automatically determined from table size)
        """
        # Determine optimal order if not specified
        if order is None:
            order = self._get_optimal_order(table_name)
        
        # Create new B-Tree with optimal order
        btree = BTree(self.page_manager, order=order)
        
        # Build index by scanning table
        table_schema = self.catalog.get_table_schema(table_name)
        if not table_schema or table_schema.first_page_id is None:
            # Empty table or doesn't exist - just create empty index
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
            
            if page is None:
                break
            
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
    
    def _get_optimal_order(self, table_name: str) -> int:
        """
        Determine optimal B-Tree order based on table size.
        
        Uses heuristics:
        - Small tables (< 10k rows): order = 10
        - Medium tables (10k-100k rows): order = 15  
        - Large tables (100k+ rows): order = 20
        
        Args:
            table_name: Name of the table
            
        Returns:
            Optimal B-Tree order
        """
        # Estimate row count
        table_schema = self.catalog.get_table_schema(table_name)
        if not table_schema or table_schema.first_page_id is None:
            return 10  # Default for empty table
        
        # Quick row count estimation
        row_count = 0
        current_page_id = table_schema.first_page_id
        page_count = 0
        
        # Sample first 3 pages
        while current_page_id is not None and page_count < 3:
            page = self.page_manager.read_page(current_page_id)
            if page:
                row_count += len(page.records)
                current_page_id = page.next_page_id
                page_count += 1
            else:
                break
        
        # Estimate total rows
        if page_count > 0:
            # Count remaining pages
            total_pages = page_count
            while current_page_id is not None:
                total_pages += 1
                page = self.page_manager.read_page(current_page_id)
                if page:
                    current_page_id = page.next_page_id
                else:
                    break
            
            estimated_rows = (row_count // page_count) * total_pages
            
            # Choose order based on size
            if estimated_rows < 10_000:
                return 10  # Small dataset
            elif estimated_rows < 100_000:
                return 15  # Medium dataset
            else:
                return 20  # Large dataset
        
        return 10  # Default
    
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
        if page is None or not page.records:
            return
        
        # Create a temporary BTree instance to use its deserialize method
        temp_btree = BTree(self.page_manager, order=10)
        node = temp_btree._deserialize_node(page.records[0])
        
        # Recursively free child pages
        if not node.is_leaf:
            for child_id in node.children:
                self._free_btree_pages(child_id)
        
        # Note: Actual page freeing would require a free page list implementation
        # For now, we just break the references in the catalog