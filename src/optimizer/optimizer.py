"""
Query Optimizer for AlpacaDB

Implements rule-based query optimization.
Phase 1: Simple equality predicate optimization with index selection.
"""

from typing import Optional, Any
from dataclasses import dataclass
from ..query.ast_nodes import SelectNode, BinaryOp, ColumnRef, Literal
from .cost_estimator import cost_seq_scan, cost_index_scan
from ..errors import OptimizerError, TableNotFoundError


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
    
    def __init__(self, catalog, index_manager=None, table_manager=None):
        """
        Initialize optimizer.
        
        Args:
            catalog: Database catalog for schema lookups
            index_manager: Optional IndexManager for index availability checks
            table_manager: Optional TableManager for table size estimation
        """
        self.catalog = catalog
        self.index_manager = index_manager
        self.table_manager = table_manager
    
    def optimize(self, select_node: SelectNode) -> QueryPlan:
        """
        Optimize a SELECT query and return an execution plan.
        
        Uses cost-based optimization: compares SeqScan vs IndexScan costs
        and chooses the cheaper option.
        
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
        
        # Rule 2: Try to find a simple equality predicate on an indexed column
        index_opportunity = self._find_index_opportunity(table_name, where_clause)

        if index_opportunity:
            # Check if it's an equality or range predicate
            if index_opportunity[0] == 'equality':
                _, index_name, column_name, search_key = index_opportunity
                
                # Gather stats
                table_stats = self.catalog.get_table_stats(table_name) if hasattr(self.catalog, 'get_table_stats') else None
                index_stats = self.catalog.get_index_stats(index_name) if hasattr(self.catalog, 'get_index_stats') else None

                # If stats are very incomplete (no rows recorded), prefer index (rule-based fallback)
                if not table_stats or table_stats.get('num_rows', 0) == 0:
                    use_index = True
                else:
                    try:
                        seq_cost = cost_seq_scan(table_stats)
                        idx_cost = cost_index_scan(table_stats, index_stats, predicate_type='eq')
                        
                        # Hybrid decision: prefer index if selectivity is high (unique/near-unique)
                        # even if costs are close, since indexes exist for a reason
                        num_rows = table_stats.get('num_rows', 0)
                        num_distinct = index_stats.get('num_distinct') if index_stats else None
                        
                        if num_distinct and num_rows > 0:
                            selectivity = 1.0 / num_distinct
                            # If highly selective (< 50% of rows), strongly prefer index
                            # This balances cost-based optimization with practical index usage
                            if selectivity < 0.5:
                                use_index = True
                            else:
                                use_index = idx_cost <= seq_cost
                        else:
                            # No selectivity info - use pure cost comparison
                            use_index = idx_cost <= seq_cost
                    except Exception:
                        # Fallback to rule-based decision if cost estimation fails
                        use_index = True

                if use_index:
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
                )        # Rule 3: No usable index, fall back to SeqScan
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
        
        # Case 3: OR expression - cannot use index (would need to union results)
        # Future enhancement: could use bitmap index scans
        
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
        
        # Add cost estimation
        cost = self.estimate_cost(plan)
        lines.append(f"  Estimated Cost: {cost:.2f}")
        
        return '\n'.join(lines)
    
    def estimate_cost(self, plan: QueryPlan) -> float:
        """
        Estimate the cost of executing a query plan.
        
        Cost model:
        - SeqScan: cost = number of pages * page_read_cost
        - IndexScan: cost = index_lookup_cost + result_fetch_cost
        
        Args:
            plan: Query plan to estimate
            
        Returns:
            Estimated cost (lower is better)
        """
        table_name = plan.table_name
        
        # Get table statistics
        table_schema = self.catalog.get_table_schema(table_name)
        if not table_schema:
            return float('inf')  # Table doesn't exist
        
        # Estimate table size (number of rows)
        # For now, we'll try to get actual count if possible
        num_rows = self._estimate_table_size(table_name)
        
        # Cost constants
        PAGE_READ_COST = 1.0  # Cost to read one page
        INDEX_LOOKUP_COST = 2.0  # Cost for index traversal
        INDEX_FETCH_COST = 0.5  # Cost per row fetched via index
        
        if plan.plan_type == 'SeqScan':
            # Sequential scan: read all pages
            # Estimate pages needed (assuming ~100 rows per page for simplicity)
            estimated_pages = max(1, num_rows / 100)
            cost = estimated_pages * PAGE_READ_COST
            
            # Add filter cost (0.1 per row checked)
            if plan.full_predicate:
                cost += num_rows * 0.1
            
        elif plan.plan_type == 'IndexScan':
            # Index scan: lookup + fetch
            cost = INDEX_LOOKUP_COST
            
            # Estimate selectivity (what fraction of rows match)
            # For equality predicates, assume high selectivity (few matches)
            # For now, estimate 1-5% of rows match (optimistic)
            estimated_matches = max(1, num_rows * 0.01) if num_rows > 100 else 1
            
            # Fetch cost scales with number of matches
            cost += estimated_matches * INDEX_FETCH_COST
            
            # Additional filter cost for remaining predicates
            if plan.full_predicate:
                cost += estimated_matches * 0.1
        else:
            cost = float('inf')
        
        return cost
    
    def _estimate_table_size(self, table_name: str) -> int:
        """
        Estimate the number of rows in a table.
        
        For now, we try to get actual count if table_manager is available.
        Otherwise, estimate based on page count.
        """
        # Try to get actual row count if we have access to table_manager
        if self.table_manager:
            try:
                rows = self.table_manager.select_all(table_name)
                return len(rows)
            except:
                pass
        # In a real implementation, we'd maintain statistics
        return 100  # Default estimate
