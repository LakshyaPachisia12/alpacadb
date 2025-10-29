"""
PageManager - Manages the database file and page-level I/O.

This is the bridge between the logical page abstraction and
the physical disk. It handles allocation, reading, and writing
of pages to the database file.
"""

import os
from typing import Optional
from .page import Page, PAGE_SIZE, PAGE_TYPE_META


class PageManager:
    """
    Manages all page I/O operations for the database.
    
    Responsibilities:
    - Creating and opening database files
    - Allocating new pages
    - Reading pages from disk
    - Writing pages to disk
    - Ensuring durability (fsync)
    """
    
    def __init__(self, db_file_path: str):
        """
        Initialize the page manager.
        
        Args:
            db_file_path: Path to the database file (e.g., 'data/alpacadb.db')
        """
        self.db_file_path = db_file_path
        self.file_handle = None
        self._open_or_create_file()
    
    def _open_or_create_file(self):
        """
        Open existing database file or create a new one.
        
        If creating new file, initializes it with a metadata page (page 0).
        """
        is_new_file = not os.path.exists(self.db_file_path)
        
        if is_new_file:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.db_file_path) or '.', exist_ok=True)
            
            # Create new file with metadata page
            with open(self.db_file_path, 'wb') as f:
                meta_page = Page(page_id=0, page_type=PAGE_TYPE_META)
                f.write(meta_page.serialize())
            
            print(f"✨ Created new database file: {self.db_file_path}")
        
        # Open for reading and writing in binary mode
        self.file_handle = open(self.db_file_path, 'r+b')
        
        if not is_new_file:
            print(f"📂 Opened existing database: {self.db_file_path}")
    
    def allocate_page(self, page_type: int = 1) -> Page:
        """
        Allocate a brand new page and append it to the database file.
        
        This expands the database by one page (4KB).
        
        Args:
            page_type: Type of page to allocate (DATA, INDEX, or META)
            
        Returns:
            Newly created Page object with assigned ID
        """
        # Find next available page ID
        self.file_handle.seek(0, 2)  # Seek to end of file
        file_size = self.file_handle.tell()
        next_page_id = file_size // PAGE_SIZE
        
        # Create new empty page
        new_page = Page(page_id=next_page_id, page_type=page_type)
        
        # Write to disk immediately
        self.write_page(new_page)
        
        print(f"📄 Allocated page {next_page_id} (type={page_type})")
        return new_page
    
    def write_page(self, page: Page) -> None:
        """
        Persist a page to disk at its designated position.
        
        This is THE critical operation for durability. We use fsync
        to guarantee data reaches physical storage.
        
        Args:
            page: Page object to write
        """
        offset = page.page_id * PAGE_SIZE
        
        # Seek to page position
        self.file_handle.seek(offset)
        
        # Serialize and write
        serialized = page.serialize()
        self.file_handle.write(serialized)
        
        # CRITICAL: Flush to disk
        self.file_handle.flush()           # Flush Python buffer to OS
        os.fsync(self.file_handle.fileno())  # Force OS to write to physical disk
        
        # This two-step flush ensures data survives power loss
    
    def read_page(self, page_id: int) -> Optional[Page]:
        """
        Load a page from disk by its ID.
        
        Args:
            page_id: ID of the page to read
            
        Returns:
            Page object if it exists, None otherwise
        """
        offset = page_id * PAGE_SIZE
        
        # Check if page exists in file
        self.file_handle.seek(0, 2)  # Seek to end
        file_size = self.file_handle.tell()
        
        if offset >= file_size:
            return None  # Page doesn't exist yet
        
        # Read raw bytes
        self.file_handle.seek(offset)
        raw_bytes = self.file_handle.read(PAGE_SIZE)
        
        if len(raw_bytes) != PAGE_SIZE:
            raise IOError(f"Incomplete page read: expected {PAGE_SIZE} bytes, got {len(raw_bytes)}")
        
        # Deserialize
        try:
            return Page.deserialize(raw_bytes)
        except ValueError as e:
            print(f"⚠️  Warning: Failed to read page {page_id}: {e}")
            return None
    
    def get_num_pages(self) -> int:
        """
        Get total number of pages in the database.
        
        Returns:
            Total page count
        """
        self.file_handle.seek(0, 2)
        file_size = self.file_handle.tell()
        return file_size // PAGE_SIZE
    
    def close(self):
        """
        Cleanly close the database file.
        
        Always call this before program exit!
        """
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
            print("🔒 Database file closed")
    
    def __del__(self):
        """Ensure file is closed even if close() wasn't called."""
        self.close()
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        num_pages = self.get_num_pages()
        return f"PageManager(file='{self.db_file_path}', pages={num_pages})"