"""
Page - The fundamental unit of storage in AlpacaDB.

A page is a fixed-size container (4KB) that stores records on disk.
All I/O operations happen at page granularity for efficiency.
"""

import struct
import zlib
from typing import List, Optional

# Constants
PAGE_SIZE = 4096  # 4 KB - matches most filesystem block sizes
HEADER_SIZE = 64  # Bytes reserved for page metadata

# Page Type Constants
PAGE_TYPE_DATA = 1   # Stores table rows
PAGE_TYPE_INDEX = 2  # Stores B-Tree nodes (future sprint)
PAGE_TYPE_META = 3   # Stores table schemas


class Page:
    """
    Represents a single page in the database file.
    
    Structure:
    ┌──────────────────────────────────────┐
    │ Header (64 bytes)                    │
    ├──────────────────────────────────────┤
    │ Record 1 [length|data]               │
    │ Record 2 [length|data]               │
    │ ...                                  │
    │ Record N [length|data]               │
    │ [Free space]                         │
    └──────────────────────────────────────┘
    """
    
    def __init__(self, page_id: int, page_type: int = PAGE_TYPE_DATA):
        """
        Initialize a new page.
        
        Args:
            page_id: Unique identifier for this page
            page_type: Type of data stored (DATA, INDEX, or META)
        """
        self.page_id = page_id
        self.page_type = page_type
        self.records: List[bytes] = []
        self.next_page_id: Optional[int] = None  # For chaining pages
    
    def add_record(self, data: bytes) -> bool:
        """
        Attempt to add a record to this page.
        
        Args:
            data: Raw bytes of the record to add
            
        Returns:
            True if record was added successfully
            False if page is full (caller should allocate new page)
        """
        record_size = len(data) + 2  # +2 bytes for length prefix
        
        if self.get_free_space() < record_size:
            return False  # Page full
        
        self.records.append(data)
        return True
    
    def get_free_space(self) -> int:
        """
        Calculate remaining free space in this page.
        
        Returns:
            Number of bytes available for new records
        """
        used_space = HEADER_SIZE
        for record in self.records:
            used_space += len(record) + 2  # Data + length prefix
        
        return PAGE_SIZE - used_space
    
    def serialize(self) -> bytes:
        """
        Convert this page to raw bytes for disk storage.
        
        This is the critical operation that makes data durable.
        The serialized format can survive power loss and be
        deserialized back into a Page object.
        
        Returns:
            Exactly PAGE_SIZE bytes ready to write to disk
        """
        # Step 1: Build data section
        data_section = bytearray()
        for record in self.records:
            # Write: [2-byte length][variable data]
            data_section.extend(struct.pack('<H', len(record)))  # Unsigned short, little-endian
            data_section.extend(record)
        
        # Step 2: Calculate checksum for data integrity
        checksum = zlib.crc32(data_section) & 0xFFFFFFFF  # Ensure 32-bit unsigned
        
        # Step 3: Build header
        header = struct.pack(
            '<IBHHII',  # Format string
            self.page_id,              # I = unsigned int (4 bytes)
            self.page_type,            # B = unsigned char (1 byte)
            self.get_free_space(),     # H = unsigned short (2 bytes)
            len(self.records),         # H = unsigned short (2 bytes)
            self.next_page_id or 0,    # I = unsigned int (4 bytes)
            checksum                   # I = unsigned int (4 bytes)
        )
        # Total: 4+1+2+2+4+4 = 17 bytes, pad to HEADER_SIZE
        
        header = header.ljust(HEADER_SIZE, b'\x00')
        
        # Step 4: Combine and pad to PAGE_SIZE
        full_page = header + bytes(data_section)
        full_page = full_page.ljust(PAGE_SIZE, b'\x00')
        
        return full_page
    
    @classmethod
    def deserialize(cls, raw_bytes: bytes) -> 'Page':
        """
        Reconstruct a Page object from disk bytes.
        
        This is the resurrection spell - bringing data back to life.
        
        Args:
            raw_bytes: Exactly PAGE_SIZE bytes read from disk
            
        Returns:
            Reconstructed Page object
            
        Raises:
            ValueError: If data is corrupted or invalid
        """
        if len(raw_bytes) != PAGE_SIZE:
            raise ValueError(f"Invalid page size: expected {PAGE_SIZE}, got {len(raw_bytes)}")
        
        # Step 1: Parse header
        header_data = struct.unpack('<IBHHII', raw_bytes[:17])
        page_id, page_type, free_space, num_records, next_page_id, stored_checksum = header_data
        
        # Step 2: Create page object
        page = cls(page_id, page_type)
        page.next_page_id = next_page_id if next_page_id != 0 else None
        
        # Step 3: Parse records from data section
        offset = HEADER_SIZE
        for _ in range(num_records):
            # Read length prefix
            if offset + 2 > PAGE_SIZE:
                raise ValueError(f"Page {page_id}: Corrupted record length at offset {offset}")
            
            record_len = struct.unpack('<H', raw_bytes[offset:offset+2])[0]
            offset += 2
            
            # Read record data
            if offset + record_len > PAGE_SIZE:
                raise ValueError(f"Page {page_id}: Record extends beyond page boundary")
            
            record_data = raw_bytes[offset:offset+record_len]
            offset += record_len
            
            page.records.append(record_data)
        
        # Step 4: Verify checksum (data integrity)
        actual_data_section = raw_bytes[HEADER_SIZE:offset]
        calculated_checksum = zlib.crc32(actual_data_section) & 0xFFFFFFFF
        
        if calculated_checksum != stored_checksum:
            raise ValueError(
                f"Page {page_id} corrupted! "
                f"Checksum mismatch: expected {stored_checksum:08x}, got {calculated_checksum:08x}"
            )
        
        return page
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"Page(id={self.page_id}, type={self.page_type}, "
            f"records={len(self.records)}, free={self.get_free_space()}b)"
        )