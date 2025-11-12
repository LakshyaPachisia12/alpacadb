"""
Query Optimizer for AlpacaDB

Implements rule-based query optimization.
Phase 1: Simple equality predicate optimization with index selection.
"""

from typing import Optional, Any
from dataclasses import dataclass
from ..query.ast_nodes import SelectNode, BinaryOp, ColumnRef, Literal


@dataclass
class QueryPlan:
    """
    Represents a query execution plan.
    
    Attributes:
        plan_type: 'SeqScan', 'IndexScan', or 'IndexRangeScan'
        table_name: Name of the table to scan
        index_name: Name of index to use (for IndexScan/IndexRangeScan)
        index_column: Column name that is indexed
        search_key: Value to search for (for IndexScan only)
        range_min: Minimum value for range scan (for IndexRangeScan)
        range_max: Maximum value for range scan (for IndexRangeScan)
        range_min_inclusive: Include min value (>= vs >)
        range_max_inclusive: Include max value (<= vs <)
        full_predicate: The complete WHERE clause AST (for filtering after scan)
    """
    plan_type: str  # 'SeqScan', 'IndexScan', or 'IndexRangeScan'
    table_name: str
    index_name: Optional[str] = None
    index_column: Optional[str] = None
    search_key: Optional[Any] = None
    range_min: Optional[Any] = None
    range_max: Optional[Any] = None
    range_min_inclusive: bool = True
    range_max_inclusive: bool = True
    full_predicate: Optional[BinaryOp] = None
    
    def __repr__(self):
        if self.plan_type == 'IndexScan':
            return f"IndexScan(index={self.index_name}, key={self.search_key})"
        elif self.plan_type == 'IndexRangeScan':
            min_op = '>=' if self.range_min_inclusive else '>'
            max_op = '<=' if self.range_max_inclusive else '<'
            range_str = f"{self.range_min} {min_op} {self.index_column} {max_op} {self.range_max}"
            return f"IndexRangeScan(index={self.index_name}, range={range_str})"
        return f"SeqScan(table={self.table_name})"


class QueryOptimizer:
    """
    Rule-based query optimizer for AlpacaDB.
    
    Current capabilities:
    - Detects simple equality predicates (column = value) → IndexScan
    - Detects range predicates (column >, <, >=, <=, BETWEEN value) → IndexRangeScan
    - Chooses appropriate scan when an index exists on the predicate column
    - Falls back to SeqScan otherwise
    
    Future enhancements:
    - Cost-based optimization with statistics
    - Multi-index selection
    - Composite indexes
    - Join optimization
    """
    
    def __init__(self, catalog, index_manager=None):
        """
        Initialize optimizer.
        
        Args:
            catalog: Database catalog for schema lookups
            index_manager: Optional IndexManager for index availability checks
        """
        self.catalog = catalog
        self.index_manager = index_manager
    
    def optimize(self, select_node: SelectNode) -> QueryPlan:
        """
        Optimize a SELECT query and return an execution plan.
        
        Args:
            select_node: Parsed SELECT AST node
            
        Returns:
            QueryPlan specifying how to execute the query
        """
        table_name = select_node.table_name
        where_clause = select_node.where_clause
        
        # Rule 1: If no WHERE clause or no index_manager, use SeqScan
        if not where_clause or not self.index_manager:
            return QueryPlan(
                plan_type='SeqScan',
                table_name=table_name,
                full_predicate=where_clause
            )
        
        # Rule 2: Try to find indexable predicate (equality or range)
        index_opportunity = self._find_index_opportunity(table_name, where_clause)
        
        if index_opportunity:
            # Found an index we can use!
            if index_opportunity[0] == 'equality':
                _, index_name, column_name, search_key = index_opportunity
                return QueryPlan(
                    plan_type='IndexScan',
                    table_name=table_name,
                    index_name=index_name,
                    index_column=column_name,
                    search_key=search_key,
                    full_predicate=where_clause
                )
            elif index_opportunity[0] == 'range':
                _, index_name, column_name, min_key, max_key, min_inc, max_inc = index_opportunity
                return QueryPlan(
                    plan_type='IndexRangeScan',
                    table_name=table_name,
                    index_name=index_name,
                    index_column=column_name,
                    range_min=min_key,
                    range_max=max_key,
                    range_min_inclusive=min_inc,
                    range_max_inclusive=max_inc,
                    full_predicate=where_clause
                )
        
        # Rule 3: No usable index, fall back to SeqScan
        return QueryPlan(
            plan_type='SeqScan',
            table_name=table_name,
            full_predicate=where_clause
        )
    
    def _find_index_opportunity(self, table_name: str, predicate: BinaryOp) -> Optional[tuple]:
        """
        Search for an equality or range predicate on an indexed column.
        
        Returns tuple of:
        - ('equality', index_name, column_name, search_key) for equality
        - ('range', index_name, column_name, min_key, max_key, min_inc, max_inc) for range
        
        Args:
            table_name: Name of the table being queried
            predicate: WHERE clause AST node
            
        Returns:
            Tuple describing the index opportunity if found, None otherwise
        """
        if not isinstance(predicate, BinaryOp):
            return None
        
        operator = predicate.operator.upper()
        
        # Case 1: Equality predicate (column = value)
        if operator == '=':
            # Check if left side is a column and right side is a literal
            if isinstance(predicate.left, ColumnRef) and isinstance(predicate.right, Literal):
                column_name = predicate.left.name.lower()
                search_key = predicate.right.value
                
                index_name = self._find_index_for_column(table_name, column_name)
                if index_name:
                    return ('equality', index_name, column_name, search_key)
            
            # Also check reversed case (value = column)
            if isinstance(predicate.right, ColumnRef) and isinstance(predicate.left, Literal):
                column_name = predicate.right.name.lower()
                search_key = predicate.left.value
                
                index_name = self._find_index_for_column(table_name, column_name)
                if index_name:
                    return ('equality', index_name, column_name, search_key)
        
        # Case 2: Range predicates (>, <, >=, <=)
        elif operator in ('>', '<', '>=', '<='):
            column_name = None
            value = None
            
            # Check if left is column, right is literal
            if isinstance(predicate.left, ColumnRef) and isinstance(predicate.right, Literal):
                column_name = predicate.left.name.lower()
                value = predicate.right.value
                
                index_name = self._find_index_for_column(table_name, column_name)
                if index_name:
                    # Convert to min/max format
                    if operator in ('>', '>='):
                        # column >= value → range [value, None]
                        return ('range', index_name, column_name, value, None, 
                               operator == '>=', True)
                    else:  # < or <=
                        # column <= value → range [None, value]
                        return ('range', index_name, column_name, None, value,
                               True, operator == '<=')
            
            # Check if right is column, left is literal (reversed)
            elif isinstance(predicate.right, ColumnRef) and isinstance(predicate.left, Literal):
                column_name = predicate.right.name.lower()
                value = predicate.left.value
                
                index_name = self._find_index_for_column(table_name, column_name)
                if index_name:
                    # Reverse the operator: value > column → column < value
                    if operator in ('>', '>='):
                        # value >= column → column <= value
                        return ('range', index_name, column_name, None, value,
                               True, operator == '>=')
                    else:  # < or <=
                        # value <= column → column >= value
                        return ('range', index_name, column_name, value, None,
                               operator == '<=', True)
        
        # Case 3: AND expression - try to find range or equality
        elif operator == 'AND':
            # Try left side
            left_opportunity = self._find_index_opportunity(table_name, predicate.left)
            if left_opportunity:
                return left_opportunity
            
            # Try right side
            right_opportunity = self._find_index_opportunity(table_name, predicate.right)
            if right_opportunity:
                return right_opportunity
        
        # Case 4: OR expression - cannot use index (would need to union results)
        
        return None
    
    def _find_index_for_column(self, table_name: str, column_name: str) -> Optional[str]:
        """
        Find an index that covers a specific column.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column
            
        Returns:
            Index name if found, None otherwise
        """
        if not self.index_manager:
            return None
        
        # Get all indexes for this table
        indexes = self.catalog.get_indexes_for_table(table_name)
        
        # Find first index that matches the column
        for index_info in indexes:
            if index_info.column_name.lower() == column_name:
                return index_info.index_name
        
        return None
    
    def explain(self, plan: QueryPlan) -> str:
        """
        Generate a human-readable explanation of a query plan.
        
        Args:
            plan: Query plan to explain
            
        Returns:
            Formatted explanation string
        """
        lines = []
        lines.append(f"Query Plan for table '{plan.table_name}':")
        lines.append(f"  Scan Type: {plan.plan_type}")
        
        if plan.plan_type == 'IndexScan':
            lines.append(f"  Index: {plan.index_name}")
            lines.append(f"  Column: {plan.index_column}")
            lines.append(f"  Search Key: {plan.search_key}")
        
        if plan.full_predicate:
            lines.append(f"  Additional Filters: {plan.full_predicate}")
        
        return '\n'.join(lines)
