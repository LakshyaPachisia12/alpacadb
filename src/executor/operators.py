"""
Physical Operators for Query Execution

These operators use the Volcano/Iterator model:
- Each operator implements: open(), next(), close()
- Operators pull data from children on-demand
- Enables pipelining and efficient memory usage
"""

from typing import List, Optional, Any, Iterator
from abc import ABC, abstractmethod
from ..errors import ExecutionError, ColumnNotFoundError


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
                    raise ExecutionError(
                        f"Unknown operator: {op}",
                        hint=f"Supported operators: =, !=, <, >, <=, >=, AND, OR. Got: {op}"
                    )

            elif isinstance(node, ColumnRef):
                # Find column index and return value from row
                col_name = node.name.lower()
                try:
                    col_idx = self.column_names.index(col_name)
                    return row[col_idx]
                except ValueError:
                    # Find table name if available (for better error message)
                    raise ColumnNotFoundError(
                        col_name,
                        hint=f"Column '{col_name}' not found in table. Available columns: {', '.join(self.column_names)}"
                    )

            elif isinstance(node, Literal):
                return node.value

            else:
                raise ExecutionError(
                    f"Unknown node type in predicate: {type(node).__name__}",
                    hint="Predicates can only contain column references, literals, and binary operations."
                )

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
                    raise ColumnNotFoundError(
                        col,
                        hint=f"Column '{col}' not found. Available columns: {', '.join(input_columns)}"
                    )

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
            keys: List[Any] = []
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
    Uses a B-Tree index to find rows matching a key.
    
    This operator leverages indexes for point lookups (equality predicates).
    Much faster than sequential scan for large tables.
    Handles duplicate keys by returning all matching rows.
    """

    def __init__(self, table_manager, index_manager, table_name: str, 
                 index_name: str, key: Any, column_names: List[str]):
        """
        Initialize index scan operator.
        
        Args:
            table_manager: TableManager for fetching rows
            index_manager: IndexManager for index lookups
            table_name: Name of the table
            index_name: Name of the index to use
            key: Value to search for in the index
            column_names: Column names in order (for consistency with other operators)
        """
        super().__init__()
        self.table_manager = table_manager
        self.index_manager = index_manager
        self.table_name = table_name
        self.index_name = index_name
        self.key = key
        self.column_names = column_names
        self._rows = []
        self._current_idx = 0

    def open(self):
        super().open()
        # Perform index lookup - get ALL matching rows (handles duplicates)
        results = self.index_manager.search_index_all(self.index_name, self.key)
        
        # Fetch all matching rows
        self._rows = []
        for page_id, row_id in results:
            row = self.table_manager.fetch_row_by_location(
                self.table_name, page_id, row_id
            )
            if row:
                self._rows.append(row)
        
        self._current_idx = 0

    def next(self) -> Optional[List[Any]]:
        if not self._opened:
            raise RuntimeError("Operator not opened")
        
        # Return rows one by one
        if self._current_idx >= len(self._rows):
            return None
        
        row = self._rows[self._current_idx]
        self._current_idx += 1
        return row

    def close(self):
        super().close()
        self._rows = []
        self._current_idx = 0

    def __repr__(self):
        return f"IndexScanOperator(index={self.index_name}, key={self.key})"


class AggregateOperator(PhysicalOperator):
    """
    Aggregation Operator
    Groups rows by specified columns and applies aggregate functions.
    
    Handles GROUP BY and aggregate functions like COUNT, SUM, AVG, MIN, MAX.
    """

    def __init__(self, child: PhysicalOperator, aggregates: List, group_by_columns: Optional[List[str]] = None, 
                 having_predicate=None, column_names: Optional[List[str]] = None):
        super().__init__()
        self.child = child
        self.aggregates = aggregates  # List of AggregateFunction AST nodes
        self.group_by_columns = group_by_columns if group_by_columns is not None else []  # Column names to group by
        self.having_predicate = having_predicate  # HAVING condition
        self.column_names = column_names if column_names is not None else []  # For evaluating HAVING predicates
        self._results = []
        self._current_idx = 0

    def open(self):
        super().open()
        self.child.open()
        
        # Collect all rows from child
        all_rows = []
        while True:
            row = self.child.next()
            if row is None:
                break
            all_rows.append(row)
        
        self.child.close()
        
        # Perform aggregation
        self._results = self._perform_aggregation(all_rows)
        self._current_idx = 0

    def next(self) -> Optional[List[Any]]:
        if not self._opened:
            raise RuntimeError("Operator not opened")
        
        if self._current_idx >= len(self._results):
            return None
        
        row = self._results[self._current_idx]
        self._current_idx += 1
        return row

    def close(self):
        super().close()
        self._results = []
        self._current_idx = 0

    def _perform_aggregation(self, rows: List[List[Any]]) -> List[List[Any]]:
        """Perform grouping and aggregation on the rows."""
        if not self.aggregates and not self.group_by_columns:
            # No aggregation, just pass through (shouldn't happen in practice)
            return rows
        
        # If no GROUP BY, treat all rows as one group
        if not self.group_by_columns:
            groups = {(): rows}
        else:
            # Group rows by GROUP BY columns
            groups = {}
            group_indices = []
            for col_name in self.group_by_columns:
                try:
                    idx = self.column_names.index(col_name.lower())
                    group_indices.append(idx)
                except ValueError:
                    raise ColumnNotFoundError(
                        col_name,
                        hint=f"Column '{col_name}' in GROUP BY not found. Available columns: {', '.join(self.column_names)}"
                    )
            
            for row in rows:
                key = tuple(row[i] for i in group_indices)
                if key not in groups:
                    groups[key] = []
                groups[key].append(row)
        
        # Apply aggregates to each group
        results = []
        for group_key, group_rows in groups.items():
            result_row: List[Any] = list(group_key)  # Start with GROUP BY columns
            
            # Apply each aggregate function
            for agg in self.aggregates:
                if agg.func_name == 'COUNT':
                    if agg.column is None:  # COUNT(*)
                        value = len(group_rows)
                    else:
                        # COUNT(column) - count non-null values
                        col_idx = self.column_names.index(agg.column.lower())
                        value = sum(1 for row in group_rows if row[col_idx] is not None)
                elif agg.func_name == 'SUM':
                    col_idx = self.column_names.index(agg.column.lower())
                    values = [row[col_idx] for row in group_rows if row[col_idx] is not None]
                    value = sum(values) if values else 0
                elif agg.func_name == 'AVG':
                    col_idx = self.column_names.index(agg.column.lower())
                    values = [row[col_idx] for row in group_rows if row[col_idx] is not None]
                    value = sum(values) / len(values) if values else 0
                elif agg.func_name == 'MIN':
                    col_idx = self.column_names.index(agg.column.lower())
                    values = [row[col_idx] for row in group_rows if row[col_idx] is not None]
                    value = min(values) if values else None
                elif agg.func_name == 'MAX':
                    col_idx = self.column_names.index(agg.column.lower())
                    values = [row[col_idx] for row in group_rows if row[col_idx] is not None]
                    value = max(values) if values else None
                else:
                    raise ExecutionError(
                        f"Unknown aggregate function: {agg.func_name}",
                        hint="Supported aggregate functions: COUNT, SUM, AVG, MIN, MAX."
                    )
                
                result_row.append(value)
            
            results.append(result_row)
        
        # Apply HAVING filter if present
        if self.having_predicate:
            filtered_results = []
            for result_row in results:
                if self._evaluate_having(result_row):
                    filtered_results.append(result_row)
            results = filtered_results
        
        return results

    def _evaluate_having(self, row: List[Any]) -> bool:
        """Evaluate HAVING predicate on an aggregated row."""
        if self.having_predicate is None:
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
                    raise ExecutionError(
                        f"Unknown operator in HAVING clause: {op}",
                        hint=f"Supported operators: =, !=, <, >, <=, >=, AND, OR. Got: {op}"
                    )

            elif isinstance(node, ColumnRef):
                # For HAVING, we can reference aggregate results by alias or column name
                # For now, assume we can evaluate against the result row
                # This is simplified - in practice, HAVING can reference aggregates
                col_name = node.name.lower()
                # Try to find in original column names first
                try:
                    col_idx = self.column_names.index(col_name)
                    return row[col_idx]
                except ValueError:
                    # Check if it's an aggregate result (by position)
                    # This is a simplification - proper implementation would track aliases
                    pass
                raise ColumnNotFoundError(
                    col_name,
                    hint=f"Column '{col_name}' in HAVING clause not found. Use aggregate functions or GROUP BY columns."
                )

            elif isinstance(node, Literal):
                return node.value

            else:
                raise ExecutionError(
                    f"Unknown node type in HAVING clause: {type(node).__name__}",
                    hint="HAVING clauses can only contain column references, literals, and binary operations."
                )

        return evaluate(self.having_predicate)

    def __repr__(self):
        agg_names = [f"{a.func_name}({a.column or '*'})" for a in self.aggregates]
        group_cols = ', '.join(self.group_by_columns) if self.group_by_columns else 'None'
        return f"AggregateOperator(aggregates=[{', '.join(agg_names)}], group_by=[{group_cols}])"


class NestedLoopJoinOperator(PhysicalOperator):
    """
    Nested Loop Join Operator
    
    Implements all SQL join types using nested loop algorithm:
    - INNER JOIN: Only matching rows
    - LEFT JOIN: All left rows, NULL-padded right rows
    - RIGHT JOIN: All right rows, NULL-padded left rows  
    - FULL JOIN: All rows from both sides, NULL-padded
    - CROSS JOIN: Cartesian product (no condition)
    """

    def __init__(self, left_child: PhysicalOperator, right_child: PhysicalOperator, 
                 join_type: str, join_condition=None, 
                 left_columns: List[str] = None, right_columns: List[str] = None):
        """
        Initialize join operator.
        
        Args:
            left_child: Left input operator
            right_child: Right input operator
            join_type: 'INNER', 'LEFT', 'RIGHT', 'FULL', 'CROSS'
            join_condition: AST node for join condition (None for CROSS JOIN)
            left_columns: Column names from left side
            right_columns: Column names from right side
        """
        super().__init__()
        self.left_child = left_child
        self.right_child = right_child
        self.join_type = join_type.upper()
        self.join_condition = join_condition
        self.left_columns = left_columns or []
        self.right_columns = right_columns or []
        
        # For evaluation
        self.all_columns = self.left_columns + self.right_columns
        
        # Buffers for different join types
        self._left_rows = []
        self._right_rows = []
        self._output_buffer = []
        self._buffer_idx = 0

    def open(self):
        super().open()
        self.left_child.open()
        self.right_child.open()
        
        # Collect all rows from both children
        self._left_rows = self._collect_all_rows(self.left_child)
        self._right_rows = self._collect_all_rows(self.right_child)
        
        # Close children as we have all their data
        self.left_child.close()
        self.right_child.close()
        
        # Perform the join
        self._output_buffer = self._perform_join()
        self._buffer_idx = 0

    def _collect_all_rows(self, operator: PhysicalOperator) -> List[List[Any]]:
        """Collect all rows from an operator."""
        rows = []
        while True:
            row = operator.next()
            if row is None:
                break
            rows.append(row)
        return rows

    def _perform_join(self) -> List[List[Any]]:
        """Perform the join operation based on join type."""
        results = []
        
        if self.join_type == 'CROSS':
            # Cartesian product - every left row with every right row
            for left_row in self._left_rows:
                for right_row in self._right_rows:
                    results.append(left_row + right_row)
        
        elif self.join_type == 'INNER':
            # Only matching rows
            for left_row in self._left_rows:
                for right_row in self._right_rows:
                    if self._matches_condition(left_row, right_row):
                        results.append(left_row + right_row)
        
        elif self.join_type == 'LEFT':
            # All left rows, NULL-pad right side when no match
            right_nulls = [None] * len(self.right_columns)
            for left_row in self._left_rows:
                found_match = False
                for right_row in self._right_rows:
                    if self._matches_condition(left_row, right_row):
                        results.append(left_row + right_row)
                        found_match = True
                if not found_match:
                    results.append(left_row + right_nulls)
        
        elif self.join_type == 'RIGHT':
            # All right rows, NULL-pad left side when no match
            left_nulls = [None] * len(self.left_columns)
            for right_row in self._right_rows:
                found_match = False
                for left_row in self._left_rows:
                    if self._matches_condition(left_row, right_row):
                        results.append(left_row + right_row)
                        found_match = True
                if not found_match:
                    results.append(left_nulls + right_row)
        
        elif self.join_type == 'FULL':
            # All rows from both sides, NULL-pad when no match
            left_nulls = [None] * len(self.left_columns)
            right_nulls = [None] * len(self.right_columns)
            
            # Track which rows have been matched
            left_matched = [False] * len(self._left_rows)
            right_matched = [False] * len(self._right_rows)
            
            # First, add all matching pairs
            for i, left_row in enumerate(self._left_rows):
                for j, right_row in enumerate(self._right_rows):
                    if self._matches_condition(left_row, right_row):
                        results.append(left_row + right_row)
                        left_matched[i] = True
                        right_matched[j] = True
            
            # Add unmatched left rows
            for i, left_row in enumerate(self._left_rows):
                if not left_matched[i]:
                    results.append(left_row + right_nulls)
            
            # Add unmatched right rows
            for j, right_row in enumerate(self._right_rows):
                if not right_matched[j]:
                    results.append(left_nulls + right_row)
        
        return results

    def _matches_condition(self, left_row: List[Any], right_row: List[Any]) -> bool:
        """Check if a pair of rows matches the join condition."""
        if self.join_condition is None:
            return True  # CROSS JOIN always matches
        
        # Evaluate the join condition
        return self._evaluate_condition(left_row + right_row, self.join_condition)

    def _evaluate_condition(self, row: List[Any], condition) -> bool:
        """Evaluate a condition on a combined row."""
        if condition is None:
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
                elif op == "!=" or op == "<>":
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
                    raise ExecutionError(f"Unknown operator in join condition: {op}")

            elif isinstance(node, ColumnRef):
                # Handle qualified column names (table.column)
                col_name = node.name.lower()
                if '.' in col_name:
                    # Qualified name - find in combined column list
                    try:
                        col_idx = self.all_columns.index(col_name)
                        return row[col_idx]
                    except ValueError:
                        raise ColumnNotFoundError(
                            col_name,
                            hint=f"Qualified column '{col_name}' not found. Available: {', '.join(self.all_columns)}"
                        )
                else:
                    # Unqualified name - ambiguous, but try to find it
                    try:
                        col_idx = self.all_columns.index(col_name)
                        return row[col_idx]
                    except ValueError:
                        raise ColumnNotFoundError(
                            col_name,
                            hint=f"Column '{col_name}' not found. Available: {', '.join(self.all_columns)}"
                        )

            elif isinstance(node, Literal):
                return node.value

            else:
                raise ExecutionError(f"Unsupported node type in join condition: {type(node)}")

        return evaluate(condition)

    def next(self) -> Optional[List[Any]]:
        if not self._opened:
            raise RuntimeError("Operator not opened")
        
        if self._buffer_idx >= len(self._output_buffer):
            return None
        
        row = self._output_buffer[self._buffer_idx]
        self._buffer_idx += 1
        return row

    def close(self):
        super().close()
        self._left_rows = []
        self._right_rows = []
        self._output_buffer = []
        self._buffer_idx = 0

    def __repr__(self):
        return f"{self.join_type}JoinOperator(left={self.left_child}, right={self.right_child})"
