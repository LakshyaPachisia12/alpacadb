"""
Query Executor - Main Execution Engine

Converts AST nodes into physical operator trees and executes them.
"""

from typing import List, Any, Optional, Tuple
from .operators import ScanOperator, FilterOperator, ProjectOperator, SortOperator
from ..query.ast_nodes import (
    SelectNode,
    InsertNode,
    CreateTableNode,
    UpdateNode,
    DeleteNode,
)


class QueryExecutor:
    """
    Main query executor that converts AST to physical operators and executes them.
    """

    def __init__(self, table_manager, catalog):
        self.table_manager = table_manager
        self.catalog = catalog

    def execute(self, ast_node) -> Tuple[List[List[Any]], Optional[List[str]]]:
        """
        Execute an AST node and return results.

        Returns:
            (rows, column_names) for SELECT queries
            ([], None) for other queries (INSERT, CREATE, etc.)
        """
        if isinstance(ast_node, SelectNode):
            return self._execute_select(ast_node)
        elif isinstance(ast_node, InsertNode):
            return self._execute_insert(ast_node)
        elif isinstance(ast_node, CreateTableNode):
            return self._execute_create_table(ast_node)
        elif isinstance(ast_node, UpdateNode):
            return self._execute_update(ast_node)
        elif isinstance(ast_node, DeleteNode):
            return self._execute_delete(ast_node)
        else:
            raise ValueError(f"Unknown AST node type: {type(ast_node)}")

    def _execute_select(self, node: SelectNode) -> Tuple[List[List[Any]], List[str]]:
        """
        Execute a SELECT query by building an operator tree.

        Operator tree structure:
            ProjectOperator (SELECT columns)
                ↓
            SortOperator (ORDER BY) [optional]
                ↓
            FilterOperator (WHERE) [optional]
                ↓
            ScanOperator (FROM table)
        """
        # Get table schema
        table_schema = self.catalog.get_table_schema(node.table_name)
        if not table_schema:
            raise ValueError(f"Table '{node.table_name}' does not exist")

        # Extract column names from schema
        all_column_names = [col['name'].lower() for col in table_schema.columns]

        # Build operator tree from bottom up

        # 1. Scan Operator (leaf node)
        scan = ScanOperator(
            table_manager=self.table_manager,
            table_name=node.table_name,
            column_names=all_column_names,
        )

        current_operator = scan

        # 2. Filter Operator (WHERE clause)
        if node.where_clause:
            current_operator = FilterOperator(
                child=current_operator,
                predicate=node.where_clause,
                column_names=all_column_names,
            )

        # 3. Sort Operator (ORDER BY clause)
        if node.order_by:
            # Convert order_by to list of (column, is_desc) tuples
            order_by_list = []
            if isinstance(node.order_by, tuple):
                # Parser format: (column, 'ASC'|'DESC')
                col_name, direction = node.order_by
                is_desc = (direction == 'DESC')
                order_by_list.append((col_name, is_desc))
            else:
                # Executor format: list of dicts
                for order in node.order_by:
                    col_name = order["column"]
                    is_desc = order.get("desc", False)
                    order_by_list.append((col_name, is_desc))

            current_operator = SortOperator(
                child=current_operator,
                order_by_columns=order_by_list,
                column_names=all_column_names,
            )

        # 4. Project Operator (SELECT columns) - always at the top
        projection_columns = node.columns if node.columns else ["*"]

        current_operator = ProjectOperator(
            child=current_operator,
            projection_columns=projection_columns,
            input_columns=all_column_names,
        )

        # Execute the operator tree
        results = current_operator.execute()

        # Determine output column names
        if "*" in projection_columns:
            output_columns = all_column_names
        else:
            output_columns = [col.lower() for col in projection_columns]

        return results, output_columns

    def _execute_insert(self, node: InsertNode) -> Tuple[List[List[Any]], None]:
        """Execute an INSERT query"""
        # Get table schema to validate
        table_schema = self.catalog.get_table_schema(node.table_name)
        if not table_schema:
            raise ValueError(f"Table '{node.table_name}' does not exist")

        # Insert the row
        self.table_manager.insert_row(node.table_name, node.values)

        return [], None

    def _execute_create_table(
        self, node: CreateTableNode
    ) -> Tuple[List[List[Any]], None]:
        """Execute a CREATE TABLE query"""
        # Convert columns to the format expected by catalog
        # Catalog expects: List[Dict] with {"name": str, "type": str, "nullable": bool}
        columns_list = []
        for col in node.columns:
            columns_list.append({
                "name": col.name,
                "type": col.data_type,
                "nullable": col.nullable
            })

        # Create the table via catalog
        self.catalog.create_table(node.table_name, columns_list)

        return [], None

    def _execute_update(self, node: UpdateNode) -> Tuple[List[List[Any]], None]:
        """
        Execute an UPDATE query.

        Strategy:
        1. Scan the table with filter (WHERE clause)
        2. For each matching row, update the specified columns
        3. Write back to storage
        """
        # Get table schema
        table_schema = self.catalog.get_table_schema(node.table_name)
        if not table_schema:
            raise ValueError(f"Table '{node.table_name}' does not exist")

        all_column_names = [col['name'].lower() for col in table_schema.columns]

        # Get ALL rows first
        all_rows = self.table_manager.select_all(node.table_name)

        updated_count = 0

        # Build filter once for efficiency
        if node.where_clause:
            scan = ScanOperator(
                table_manager=self.table_manager,
                table_name=node.table_name,
                column_names=all_column_names,
            )
            filter_op = FilterOperator(
                child=scan,
                predicate=node.where_clause,
                column_names=all_column_names,
            )

            # Apply updates to matching rows
            for row in all_rows:
                # Check if this row matches the WHERE clause
                if filter_op._evaluate_predicate(row):
                    # Apply updates
                    for col_name, new_value in node.assignments:
                        col_idx = all_column_names.index(col_name.lower())
                        row[col_idx] = new_value
                    updated_count += 1
        else:
            # No WHERE clause - update all rows
            for row in all_rows:
                for col_name, new_value in node.assignments:
                    col_idx = all_column_names.index(col_name.lower())
                    row[col_idx] = new_value
                updated_count += 1

        # Clear table and re-insert (simple approach)
        # TODO: This is inefficient - should be improved with row IDs
        self.table_manager._clear_table(node.table_name)
        for row in all_rows:
            self.table_manager.insert_row(node.table_name, row)

        print(f"Updated {updated_count} row(s).")
        return [], None

    def _execute_delete(self, node: DeleteNode) -> Tuple[List[List[Any]], None]:
        """
        Execute a DELETE query.

        Strategy:
        1. Scan the table with filter (WHERE clause)
        2. Collect rows that DON'T match the condition
        3. Clear table and re-insert non-matching rows
        """
        # Get table schema
        table_schema = self.catalog.get_table_schema(node.table_name)
        if not table_schema:
            raise ValueError(f"Table '{node.table_name}' does not exist")

        all_column_names = [col['name'].lower() for col in table_schema.columns]

        # Get all rows
        all_rows = self.table_manager.select_all(node.table_name)

        # Filter rows to keep (opposite of DELETE condition)
        rows_to_keep = []
        deleted_count = 0

        if node.where_clause:
            # Build filter once for efficiency
            scan = ScanOperator(
                self.table_manager, node.table_name, all_column_names
            )
            filter_op = FilterOperator(
                child=scan,
                predicate=node.where_clause,
                column_names=all_column_names,
            )

            # Evaluate predicate on each row
            for row in all_rows:
                # If row passes filter, it should be deleted
                if filter_op._evaluate_predicate(row):
                    deleted_count += 1
                else:
                    rows_to_keep.append(row)
        else:
            # No WHERE clause - delete all rows
            deleted_count = len(all_rows)
            rows_to_keep = []

        # Clear table and re-insert kept rows
        self.table_manager._clear_table(node.table_name)
        for row in rows_to_keep:
            self.table_manager.insert_row(node.table_name, row)

        print(f"Deleted {deleted_count} row(s).")
        return [], None
