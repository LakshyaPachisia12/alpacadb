"""
Storage Engine Module

Handles all physical data persistence, including:
- Page-based storage layout
- File I/O operations
- Table schema management
- Basic CRUD operations
"""

from .page import Page, PAGE_SIZE, HEADER_SIZE
from .page_manager import PageManager
from .catalog import Catalog, TableSchema
from .table_manager import TableManager

__all__ = [
    'Page',
    'PAGE_SIZE',
    'HEADER_SIZE',
    'PageManager',
    'Catalog',
    'TableSchema',
    'TableManager'
]