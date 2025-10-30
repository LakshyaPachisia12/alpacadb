"""
Physical Operators for Query Execution

These operators use the Volcano/Iterator model:
- Each operator implements: open(), next(), close()
- Operators pull data from children on-demand
- Enables pipelining and efficient memory usage
"""

from typing import List, Optional, Any, Iterator
from abc import ABC, abstractmethod


class ReverseCompare:
    """
    Wrapper class for reverse comparison in sorting.
    Used to handle DESC ordering for non-numeric types.
    """
    def __init__(self, value):
        self.value = value
    
    def __lt__(self, other):
        return self.value > other.value
    
    def __le__(self, other):
        return self.value >= other.value
    
    def __gt__(self, other):
        return self.value < other.value
    
    def __ge__(self, other):
        return self.value <= other.value
    
    def __eq__(self, other):
        return self.value == other.value
    
    def __ne__(self, other):
        return self.value != other.value


class PhysicalOperator(ABC):
    """Base class for all physical operators"""

    def __init__(self):
        self._opened = False
        self._closed = False

    @abstractmethod
    def open(self):
        """Initialize the operator and its children"""
        self._opened = True

    @abstractmethod
    def next(self) -> Optional[List[Any]]:
        """
        Get the next row from this operator.
        Returns None when no more rows are available.
        """
        pass

    @abstractmethod
    def close(self):
        """Clean up resources"""
        self._closed = True

    def execute(self) -> List[List[Any]]:
        """
        Convenience method to get all results at once.
        Useful for terminal operators or testing.
        """
        self.open()
        results = []
        while True:
            row = self.next()
            if row is None:
                break
            results.append(row)
        self.close()
        return results


class ScanOperator(PhysicalOperator):
    """
    Sequential Scan Operator
    Reads all rows from a table by scanning through pages.
    """

    def __init__(self, table_manager, table_name: str, column_names: List[str]):
        super().__init__()
        self.table_manager = table_manager
        self.table_name = table_name
        self.column_names = column_names  # Column names in order
        self._iterator = None

    def open(self):
        super().open()
        # Get all rows from the table
        # We'll use the existing select_all method from table_manager
        rows = self.table_manager.select_all(self.table_name)
        self._iterator = iter(rows)

    def next(self) -> Optional[List[Any]]:
        if not self._opened:
            raise RuntimeError("Operator not opened")

        if self._iterator is None:
            return None

        try:
            return next(self._iterator)
        except StopIteration:
            return None

    def close(self):
        super().close()
        self._iterator = None

    def __repr__(self):
        return f"ScanOperator(table={self.table_name})"


class FilterOperator(PhysicalOperator):
    """
    Filter Operator
    Applies WHERE clause predicates to filter rows from child operator.
    """

    def __init__(self, child: PhysicalOperator, predicate, column_names: List[str]):
        super().__init__()
        self.child = child
        self.predicate = predicate  # AST node representing the condition
        self.column_names = column_names  # For evaluating predicates

    def open(self):
        super().open()
        self.child.open()

    def next(self) -> Optional[List[Any]]:
        if not self._opened:
            raise RuntimeError("Operator not opened")

        # Keep fetching rows until we find one that passes the predicate
        while True:
            row = self.child.next()
            if row is None:
                return None

            # Evaluate predicate on this row
            if self._evaluate_predicate(row):
                return row

    def _evaluate_predicate(self, row: List[Any]) -> bool:
        """Evaluate the predicate on a row"""
        if self.predicate is None:
            return True

        # Import here to avoid circular dependency
        from ..query.ast_nodes import BinaryOp, ColumnRef, Literal

        def evaluate(node):
            if isinstance(node, BinaryOp):
                left = evaluate(node.left)
                right = evaluate(node.right)

                op = node.operator.upper()
                if op == "=":
                    return left == right
                elif op == "!=":
                    return left != right
                elif op == "<>":
                    return left != right
                elif op == "<":
                    return left < right
                elif op == ">":
                    return left > right
                elif op == "<=":
                    return left <= right
                elif op == ">=":
                    return left >= right
                elif op == "AND":
                    return left and right
                elif op == "OR":
                    return left or right
                else:
                    raise ValueError(f"Unknown operator: {op}")

            elif isinstance(node, ColumnRef):
                # Find column index and return value from row
                col_name = node.name.lower()
                try:
                    col_idx = self.column_names.index(col_name)
                    return row[col_idx]
                except ValueError:
                    raise ValueError(f"Unknown column: {col_name}")

            elif isinstance(node, Literal):
                return node.value

            else:
                raise ValueError(f"Unknown node type in predicate: {type(node)}")

        return evaluate(self.predicate)

    def close(self):
        super().close()
        self.child.close()

    def __repr__(self):
        return f"FilterOperator(predicate={self.predicate})"


class ProjectOperator(PhysicalOperator):
    """
    Projection Operator
    Selects specific columns from rows (SELECT clause).
    """

    def __init__(
        self,
        child: PhysicalOperator,
        projection_columns: List[str],  # Columns to project
        input_columns: List[str],
    ):  # All available columns
        super().__init__()
        self.child = child
        self.projection_columns = projection_columns
        self.input_columns = input_columns

        # Pre-compute column indices for efficiency
        if "*" in projection_columns:
            self.column_indices = list(range(len(input_columns)))
        else:
            self.column_indices = []
            for col in projection_columns:
                col_lower = col.lower()
                try:
                    idx = input_columns.index(col_lower)
                    self.column_indices.append(idx)
                except ValueError:
                    raise ValueError(f"Unknown column: {col}")

    def open(self):
        super().open()
        self.child.open()

    def next(self) -> Optional[List[Any]]:
        if not self._opened:
            raise RuntimeError("Operator not opened")

        row = self.child.next()
        if row is None:
            return None

        # Project only the selected columns
        return [row[i] for i in self.column_indices]

    def close(self):
        super().close()
        self.child.close()

    def __repr__(self):
        return f"ProjectOperator(columns={self.projection_columns})"


class SortOperator(PhysicalOperator):
    """
    Sort Operator
    Sorts rows based on ORDER BY clause.
    This is a blocking operator (must consume all input before producing output).
    """

    def __init__(
        self,
        child: PhysicalOperator,
        order_by_columns: List[tuple],  # [(column_name, is_desc), ...]
        column_names: List[str],
    ):
        super().__init__()
        self.child = child
        self.order_by_columns = order_by_columns
        self.column_names = column_names
        self._sorted_rows = None
        self._iterator = None

    def open(self):
        super().open()
        self.child.open()

        # Collect all rows from child (blocking operation)
        rows = []
        while True:
            row = self.child.next()
            if row is None:
                break
            rows.append(row)

        self.child.close()

        # Sort the rows
        self._sorted_rows = self._sort_rows(rows)
        self._iterator = iter(self._sorted_rows)

    def _sort_rows(self, rows: List[List[Any]]) -> List[List[Any]]:
        """Sort rows based on ORDER BY clause"""
        if not self.order_by_columns:
            return rows

        # Build sort key function with proper DESC handling
        def sort_key(row):
            keys = []
            for col_name, is_desc in self.order_by_columns:
                col_idx = self.column_names.index(col_name.lower())
                value = row[col_idx]
                
                # Handle None values (put them last)
                if value is None:
                    # For DESC, None should be at the beginning (smallest)
                    # For ASC, None should be at the end (largest)
                    value = float("-inf") if is_desc else float("inf")
                
                # For DESC columns, negate numeric values or use reverse comparison
                # We'll use a tuple trick: (is_desc, value) and let Python handle it
                # For DESC: negate if numeric, otherwise we need custom comparison
                if is_desc:
                    # Negate numeric values for DESC ordering
                    if isinstance(value, (int, float)):
                        keys.append(-value)
                    else:
                        # For strings, we can't negate, so we'll use a wrapper
                        # that reverses comparison
                        keys.append(ReverseCompare(value))
                else:
                    keys.append(value)
            return keys

        # Sort with the multi-key function
        sorted_rows = sorted(rows, key=sort_key)
        return sorted_rows

    def next(self) -> Optional[List[Any]]:
        if not self._opened:
            raise RuntimeError("Operator not opened")

        if self._iterator is None:
            return None

        try:
            return next(self._iterator)
        except StopIteration:
            return None

    def close(self):
        super().close()
        self._sorted_rows = None
        self._iterator = None

    def __repr__(self):
        return f"SortOperator(order_by={self.order_by_columns})"


class IndexScanOperator(PhysicalOperator):
    """
    Index Scan Operator
    
    Uses a B-Tree index to directly locate rows matching a specific key value,
    avoiding expensive full table scans. This provides O(log n) lookup time
    instead of O(n) for sequential scans.
    
    Example: SELECT * FROM users WHERE email = 'alice@example.com'
    If an index exists on 'email', this operator uses it for fast lookup.
    """

    def __init__(
        self,
        index_manager,
        table_manager,
        table_name: str,
        index_name: str,
        search_key: Any,
        column_names: List[str],
    ):
        """
        Args:
            index_manager: IndexManager for B-Tree lookups
            table_manager: TableManager for fetching actual row data
            table_name: Name of the table to scan
            index_name: Name of the index to use
            search_key: The key value to search for (e.g., 'alice@example.com')
            column_names: All column names in the table (for row construction)
        """
        super().__init__()
        self.index_manager = index_manager
        self.table_manager = table_manager
        self.table_name = table_name
        self.index_name = index_name
        self.search_key = search_key
        self.column_names = column_names
        self._result_row = None
        self._row_returned = False

    def open(self):
        """Initialize the index scan"""
        super().open()
        
        # Perform index lookup (O(log n) operation)
        result = self.index_manager.search_index(self.index_name, self.search_key)
        
        if result is not None:
            page_id, row_id = result
            # Fetch the actual row data from storage
            self._result_row = self._fetch_row_by_location(page_id, row_id)
        else:
            self._result_row = None
        
        self._row_returned = False

    def next(self) -> Optional[List[Any]]:
        """Return the matching row (at most one)"""
        if not self._opened:
            raise RuntimeError("Operator not opened")
        
        # Index lookups return at most one row (for equality predicates)
        if not self._row_returned and self._result_row is not None:
            self._row_returned = True
            return self._result_row
        
        return None

    def _fetch_row_by_location(self, page_id: int, row_id: int) -> Optional[List[Any]]:
        """
        Fetch a single row by its physical storage location.
        
        Args:
            page_id: The page ID where the row is stored
            row_id: The row index within that page
            
        Returns:
            List of column values, or None if not found
        """
        schema = self.table_manager.catalog.get_table_schema(self.table_name)
        if not schema:
            return None
        
        try:
            page = self.table_manager.page_manager.read_page(page_id)
            if not page or row_id >= len(page.records):
                return None
            
            record_bytes = page.records[row_id]
            row = self.table_manager._deserialize_row(schema, record_bytes)
            return row
        except Exception:
            return None

    def close(self):
        """Clean up resources"""
        super().close()
        self._result_row = None
        self._row_returned = False

    def __repr__(self):
        return f"IndexScanOperator(table={self.table_name}, index={self.index_name}, key={self.search_key})"
