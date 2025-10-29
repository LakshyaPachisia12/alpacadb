"""
TableManager - High-level table operations (INSERT, SELECT).

This bridges user intent (insert a row, select data) with the
physical storage layer (pages, serialization, I/O).
"""

import struct
from typing import List, Any, Optional
from .page_manager import PageManager
from .catalog import Catalog, TableSchema
from .page import Page


class TableManager:
    """
    Manages high-level table operations.

    Responsibilities:
    - Inserting rows into tables
    - Selecting rows from tables
    - Serializing/deserializing data according to schema
    - Managing page chains for tables
    """

    # Type ID constants for serialization
    TYPE_INT = 1
    TYPE_STRING = 2
    TYPE_BOOLEAN = 3
    TYPE_NULL = 0

    def __init__(self, page_manager: PageManager, catalog: Catalog):
        """
        Initialize table manager.

        Args:
            page_manager: PageManager for I/O operations
            catalog: Catalog for schema lookups
        """
        self.page_manager = page_manager
        self.catalog = catalog

    def insert_row(self, table_name: str, values: List[Any]) -> bool:
        """
        Insert a single row into a table.

        Args:
            table_name: Name of the table
            values: List of column values in schema order

        Returns:
            True if successful, False on error
        """
        # Step 1: Validate table exists
        schema = self.catalog.get_table_schema(table_name)
        if not schema:
            print(f"❌ Table '{table_name}' does not exist")
            return False

        # Step 2: Validate value count
        if len(values) != len(schema.columns):
            print(f"❌ Expected {len(schema.columns)} values, got {len(values)}")
            return False

        # Step 3: Validate and serialize values
        try:
            row_bytes = self._serialize_row(schema, values)
        except (ValueError, TypeError) as e:
            print(f"❌ Serialization error: {e}")
            return False

        # Step 4: Find or allocate page with space
        if schema.first_page_id is None:
            # First insert for this table - allocate initial page
            page = self.page_manager.allocate_page()
            schema.first_page_id = page.page_id
            self.catalog._save_catalog()  # Update catalog
        else:
            # Find last page in chain
            page = self._get_last_page(schema.first_page_id)

        # Step 5: Try to add record to page
        if not page.add_record(row_bytes):
            # Page full - allocate new page and chain it
            new_page = self.page_manager.allocate_page()
            page.next_page_id = new_page.page_id
            self.page_manager.write_page(page)  # Update old page with link

            page = new_page
            page.add_record(row_bytes)  # Add to new page

        # Step 6: Write page to disk
        self.page_manager.write_page(page)

        print(f"✅ Inserted row into '{table_name}': {values}")
        return True

    def select_all(self, table_name: str) -> List[List[Any]]:
        """
        Read all rows from a table (full table scan).

        Args:
            table_name: Name of the table

        Returns:
            List of rows, where each row is a list of values
        """
        # Step 1: Validate table exists
        schema = self.catalog.get_table_schema(table_name)
        if not schema:
            print(f"❌ Table '{table_name}' does not exist")
            return []

        if schema.first_page_id is None:
            print(f"📭 Table '{table_name}' is empty")
            return []

        # Step 2: Traverse all pages in chain
        rows = []
        current_page_id = schema.first_page_id

        while current_page_id is not None:
            page = self.page_manager.read_page(current_page_id)

            if not page:
                print(f"⚠️  Warning: Missing page {current_page_id} in table chain")
                break

            # Deserialize all records in this page
            for record_bytes in page.records:
                try:
                    row = self._deserialize_row(schema, record_bytes)
                    rows.append(row)
                except (ValueError, struct.error) as e:
                    print(f"⚠️  Warning: Failed to deserialize record: {e}")
                    continue

            current_page_id = page.next_page_id

        print(f"📊 Retrieved {len(rows)} row(s) from '{table_name}'")
        return rows

    def _serialize_row(self, schema: TableSchema, values: List[Any]) -> bytes:
        """
        Convert a row of values into binary format.

        Format for each column: [1-byte type ID][type-specific data]

        Args:
            schema: Table schema defining column types
            values: List of values to serialize

        Returns:
            Serialized row as bytes

        Raises:
            ValueError: If type mismatch or invalid data
        """
        row_data = bytearray()

        for col, value in zip(schema.columns, values):
            col_type = col["type"].upper()

            # Handle NULL values
            if value is None:
                if not col.get("nullable", True):
                    raise ValueError(f"Column '{col['name']}' cannot be NULL")
                row_data.append(self.TYPE_NULL)
                continue

            # Serialize based on type
            if col_type == "INT":
                row_data.append(self.TYPE_INT)
                row_data.extend(struct.pack("<i", int(value)))  # 4-byte signed int

            elif col_type == "STRING":
                value_str = str(value)
                encoded = value_str.encode("utf-8")

                if len(encoded) > 65535:  # Max for 2-byte length
                    raise ValueError(f"String too long: {len(encoded)} bytes")

                row_data.append(self.TYPE_STRING)
                row_data.extend(struct.pack("<H", len(encoded)))  # 2-byte length
                row_data.extend(encoded)

            elif col_type == "BOOLEAN" or col_type == "BOOL":
                row_data.append(self.TYPE_BOOLEAN)
                row_data.append(1 if value else 0)

            else:
                raise ValueError(f"Unsupported type: {col_type}")

        return bytes(row_data)

    def _deserialize_row(self, schema: TableSchema, row_bytes: bytes) -> List[Any]:
        """
        Convert binary data back into Python values.

        Args:
            schema: Table schema defining expected types
            row_bytes: Serialized row data

        Returns:
            List of deserialized values

        Raises:
            ValueError: If data is corrupted or invalid
        """
        values = []
        offset = 0

        for col in schema.columns:
            if offset >= len(row_bytes):
                raise ValueError("Unexpected end of row data")

            # Read type ID
            type_id = row_bytes[offset]
            offset += 1

            # Handle based on type ID
            if type_id == self.TYPE_NULL:
                values.append(None)

            elif type_id == self.TYPE_INT:
                value = struct.unpack("<i", row_bytes[offset : offset + 4])[0]
                offset += 4
                values.append(value)

            elif type_id == self.TYPE_STRING:
                str_len = struct.unpack("<H", row_bytes[offset : offset + 2])[0]
                offset += 2
                value = row_bytes[offset : offset + str_len].decode("utf-8")
                offset += str_len
                values.append(value)

            elif type_id == self.TYPE_BOOLEAN:
                value = bool(row_bytes[offset])
                offset += 1
                values.append(value)

            else:
                raise ValueError(f"Unknown type ID {type_id} during deserialization")

        return values

    def _get_last_page(self, page_id: int) -> "Page":
        """
        Follow the chain of pages to find the last one.

        Args:
            page_id: ID of the first page in the chain

        Returns:
            The last Page object in the chain

        Raises:
            ValueError: If the page chain is broken
        """
        page = self.page_manager.read_page(page_id)

        if not page:
            raise ValueError(f"Invalid page chain: start page {page_id} not found")

        while page.next_page_id is not None:
            next_page = self.page_manager.read_page(page.next_page_id)
            if not next_page:
                raise ValueError(
                    f"Broken page chain: page {page.page_id} "
                    f"points to missing page {page.next_page_id}"
                )
            page = next_page

        return page

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"TableManager(catalog={self.catalog})"

    def _clear_table(self, table_name: str):
        """
        Clear all data from a table (used by UPDATE/DELETE).
        Resets the table to an empty state.
        """
        schema = self.catalog.get_table_schema(table_name)
        if not schema:
            raise ValueError(f"Table '{table_name}' does not exist")

        # Allocate a fresh empty page for the table
        first_page = self.page_manager.allocate_page()
        first_page.records = []
        first_page.next_page_id = None
        self.page_manager.write_page(first_page)

        # Update catalog with new first page
        schema.first_page_id = first_page.page_id
        self.catalog._save_catalog()
