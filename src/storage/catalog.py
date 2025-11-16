"""
Catalog - The database's memory of its own structure.

Stores table schemas (what tables exist, what columns they have)
and index information in special metadata pages. This is the "data dictionary" that
allows the database to interpret raw bytes as meaningful tables.
"""

import json
from typing import Dict, List, Optional, Tuple, Any
from .page_manager import PageManager
from .page import Page, PAGE_TYPE_META


class IndexInfo:
    """
    Describes an index on a table column.
    """
    def __init__(self, index_name: str, table_name: str, column_name: str, 
                 index_type: str = "B-Tree", root_page_id: Optional[int] = None,
                 stats: Optional[Dict[str, Any]] = None):
        self.index_name = index_name
        self.table_name = table_name
        self.column_name = column_name
        self.index_type = index_type
        self.root_page_id = root_page_id
        # Per-index statistics on the indexed column
        # keys: num_distinct, null_count, min_value, max_value
        self.stats: Dict[str, Any] = stats or {}

    def to_dict(self) -> Dict:
        return {
            "index_name": self.index_name,
            "table_name": self.table_name,
            "column_name": self.column_name,
            "index_type": self.index_type,
            "root_page_id": self.root_page_id,
            "stats": self.stats,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'IndexInfo':
        return cls(
            data["index_name"],
            data["table_name"],
            data["column_name"],
            data["index_type"],
            data.get("root_page_id"),
            data.get("stats", {}),
        )


class TableSchema:
    """
    Describes the structure of a single table.
    
    Contains:
    - Table name
    - Column definitions (name, type, nullable)
    - Pointer to first data page
    """
    
    def __init__(self, table_name: str, columns: List[Dict]):
        """
        Create a table schema.
        
        Args:
            table_name: Name of the table
            columns: List of column definitions, each with:
                     {'name': str, 'type': str, 'nullable': bool}
        """
        self.table_name = table_name
        self.columns = columns
        self.first_page_id: Optional[int] = None  # Where table data starts
        # Basic table-level statistics (Phase 2)
        self.num_rows: int = 0
        self.num_pages: int = 0
    
    def to_dict(self) -> dict:
        """Serialize schema to dictionary for JSON storage."""
        return {
            'table_name': self.table_name,
            'columns': self.columns,
            'first_page_id': self.first_page_id,
            'num_rows': self.num_rows,
            'num_pages': self.num_pages,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TableSchema':
        """Deserialize schema from dictionary."""
        schema = cls(data['table_name'], data['columns'])
        schema.first_page_id = data.get('first_page_id')
        schema.num_rows = int(data.get('num_rows', 0))
        schema.num_pages = int(data.get('num_pages', 0))
        return schema
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        cols = ', '.join(f"{c['name']}:{c['type']}" for c in self.columns)
        return f"TableSchema({self.table_name}[{cols}])"


class Catalog:
    """
    Manages the database catalog (system metadata).
    
    The catalog is stored in page 0 as JSON. It tracks:
    - What tables exist
    - Schema for each table
    - Where each table's data begins
    """
    
    def __init__(self, page_manager: PageManager):
        """
        Initialize catalog from the database file.
        
        Args:
            page_manager: PageManager instance for I/O
        """
        self.page_manager = page_manager
        self.tables: Dict[str, TableSchema] = {}
        self.indexes: Dict[str, IndexInfo] = {}  # Track indexes by name
        self._load_catalog()
    
    def _load_catalog(self):
        """
        Read catalog from page 0 (metadata page).
        
        If database is new, catalog will be empty.
        """
        meta_page = self.page_manager.read_page(0)
        
        if not meta_page:
            print("⚠️  No metadata page found (corrupted database?)")
            return
        
        if meta_page.records:
            # Deserialize JSON from first record
            try:
                catalog_json = meta_page.records[0].decode('utf-8')
                catalog_data = json.loads(catalog_json)
                
                for table_data in catalog_data.get('tables', []):
                    schema = TableSchema.from_dict(table_data)
                    self.tables[schema.table_name] = schema
                
                # Load indexes
                for index_data in catalog_data.get('indexes', []):
                    index_info = IndexInfo.from_dict(index_data)
                    self.indexes[index_info.index_name] = index_info
                
                print(f"📚 Loaded catalog: {len(self.tables)} table(s), {len(self.indexes)} index(es)")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"⚠️  Failed to parse catalog: {e}")
        else:
            print("📚 Initialized empty catalog")
    
    def _save_catalog(self):
        """
        Persist catalog to page 0.
        
        This is called after any schema change (CREATE TABLE, etc.)
        """
        # Serialize all table schemas and indexes to JSON
        catalog_data = {
            'tables': [schema.to_dict() for schema in self.tables.values()],
            'indexes': [index.to_dict() for index in self.indexes.values()],
            'version': '0.1.0'  # For future schema migrations
        }
        
        catalog_json = json.dumps(catalog_data, indent=2)
        
        # Write to metadata page
        meta_page = Page(page_id=0, page_type=PAGE_TYPE_META)
        success = meta_page.add_record(catalog_json.encode('utf-8'))
        
        if not success:
            raise RuntimeError("Catalog too large to fit in single page!")
        
        self.page_manager.write_page(meta_page)
        print("💾 Catalog saved")
    
    def create_table(self, table_name: str, columns: List[Dict]) -> bool:
        """
        Register a new table in the catalog.
        
        Args:
            table_name: Name of the table to create
            columns: List of column definitions
            
        Returns:
            True if successful, False if table already exists
        """
        # Validate table doesn't exist
        if table_name in self.tables:
            print(f"❌ Table '{table_name}' already exists")
            return False
        
        # Validate column definitions
        for col in columns:
            if 'name' not in col or 'type' not in col:
                print(f"❌ Invalid column definition: {col}")
                return False
            
            # Set default nullable
            if 'nullable' not in col:
                col['nullable'] = True
        
        # Create schema
        schema = TableSchema(table_name, columns)
        self.tables[table_name] = schema
        
        # Persist
        self._save_catalog()
        
        print(f"✅ Table '{table_name}' created with {len(columns)} column(s)")
        return True
    
    def get_table_schema(self, table_name: str) -> Optional[TableSchema]:
        """
        Retrieve schema for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            TableSchema if table exists, None otherwise
        """
        return self.tables.get(table_name)
    
    def list_tables(self) -> List[str]:
        """
        Get list of all table names.
        
        Returns:
            List of table names
        """
        return list(self.tables.keys())
    
    def drop_table(self, table_name: str) -> bool:
        """
        Remove a table from the catalog.
        
        Note: This doesn't delete the data pages (that's for future sprints).
        
        Args:
            table_name: Name of table to drop
            
        Returns:
            True if successful, False if table doesn't exist
        """
        if table_name not in self.tables:
            print(f"❌ Table '{table_name}' does not exist")
            return False
        
        del self.tables[table_name]
        self._save_catalog()
        
        print(f"✅ Table '{table_name}' dropped")
        return True
    
    # ==================== Index Management ====================
    
    def create_index(self, index_name: str, table_name: str, column_name: str, 
                    index_manager=None) -> bool:
        """
        Create an index entry in the catalog.
        
        Args:
            index_name: Name of the index
            table_name: Name of the table being indexed
            column_name: Name of the column being indexed
            index_manager: Optional IndexManager to build actual B-Tree
            
        Returns:
            True if successful
            
        Raises:
            ValueError: If table/column doesn't exist or index name is duplicate
        """
        # Check if index already exists
        if index_name in self.indexes:
            raise ValueError(f"Index '{index_name}' already exists")
        
        # Check if table exists
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        
        # Check if column exists in table
        table_schema = self.tables[table_name]
        column_exists = any(col['name'] == column_name for col in table_schema.columns)
        if not column_exists:
            raise ValueError(f"Column '{column_name}' not found in table '{table_name}'")
        
        # Create index info (B-Tree will be built by IndexManager)
        index_info = IndexInfo(
            index_name=index_name,
            table_name=table_name,
            column_name=column_name,
            index_type="B-Tree",
            root_page_id=None  # Will be set by IndexManager
        )
        
        self.indexes[index_name] = index_info
        self._save_catalog()
        return True
    
    def drop_index(self, index_name: str) -> bool:
        """
        Remove an index from the catalog.
        
        Args:
            index_name: Name of index to drop
            
        Returns:
            True if successful, False if index doesn't exist
        """
        if index_name not in self.indexes:
            print(f"❌ Index '{index_name}' does not exist")
            return False
        
        del self.indexes[index_name]
        self._save_catalog()
        return True
    
    def get_index(self, index_name: str) -> Optional[IndexInfo]:
        """Get index information by name."""
        return self.indexes.get(index_name)
    
    def update_index_root(self, index_name: str, root_page_id: int) -> None:
        """Update the root page ID for an index."""
        if index_name in self.indexes:
            self.indexes[index_name].root_page_id = root_page_id
            self._save_catalog()
    
    def get_indexes_for_table(self, table_name: str) -> List[IndexInfo]:
        """Get all indexes for a specific table."""
        return [idx for idx in self.indexes.values() if idx.table_name == table_name]
    
    def list_indexes(self) -> List[str]:
        """Get list of all index names."""
        return list(self.indexes.keys())
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"Catalog(tables={list(self.tables.keys())}, indexes={list(self.indexes.keys())})"

    # ==================== Statistics Helpers (Phase 2) ====================

    def get_table_stats(self, table_name: str) -> Optional[Dict[str, int]]:
        """
        Return basic statistics for a table: num_rows, num_pages.
        """
        schema = self.get_table_schema(table_name)
        if not schema:
            return None
        return {"num_rows": schema.num_rows, "num_pages": schema.num_pages}

    def update_table_stats(self, table_name: str, rows_delta: int = 0, pages_delta: int = 0,
                           persist: bool = True) -> None:
        """
        Incrementally update table statistics and optionally persist the catalog.
        """
        schema = self.get_table_schema(table_name)
        if not schema:
            return
        schema.num_rows = max(0, schema.num_rows + int(rows_delta))
        schema.num_pages = max(0, schema.num_pages + int(pages_delta))
        if persist:
            self._save_catalog()

    def get_index_stats(self, index_name: str) -> Optional[Dict[str, Any]]:
        """
        Return statistics for an index on a specific column.
        keys: num_distinct, null_count, min_value, max_value
        """
        idx = self.get_index(index_name)
        if not idx:
            return None
        return idx.stats or {}
