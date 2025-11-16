"""
Query Optimizer for AlpacaDB

Implements rule-based query optimization.
Phase 1: Simple equality predicate optimization with index selection.
"""

from typing import Optional, Any
from dataclasses import dataclass
from ..query.ast_nodes import SelectNode, BinaryOp, ColumnRef, Literal
from ..errors import OptimizerError, TableNotFoundError


@dataclass
class QueryPlan:
    """
    Represents a query execution plan.
    
    Attributes:
        plan_type: 'SeqScan' or 'IndexScan'
        table_name: Name of the table to scan
        index_name: Name of index to use (for IndexScan only)
        index_column: Column name that is indexed (for IndexScan only)
        search_key: Value to search for (for IndexScan only)
        full_predicate: The complete WHERE clause AST (for filtering after scan)
    """
    plan_type: str  # 'SeqScan' or 'IndexScan'
    table_name: str
    index_name: Optional[str] = None
    index_column: Optional[str] = None
    search_key: Optional[Any] = None
    full_predicate: Optional[BinaryOp] = None
    
    def __repr__(self):
        if self.plan_type == 'IndexScan':
            return f"IndexScan(index={self.index_name}, key={self.search_key})"
        return f"SeqScan(table={self.table_name})"


class QueryOptimizer:
    """
    Rule-based query optimizer for AlpacaDB.
    
    Current capabilities (Phase 1):
    - Detects simple equality predicates (column = value)
    - Chooses IndexScan when an index exists on the predicate column
    - Falls back to SeqScan otherwise
    
    Future enhancements (Phase 2+):
    - Cost-based optimization with statistics
    - Range scans (>, <, BETWEEN)
    - Multi-index selection
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
        
        # Always create a SeqScan plan as fallback
        seqscan_plan = QueryPlan(
            plan_type='SeqScan',
            table_name=table_name,
            full_predicate=where_clause
        )
        
        # If no WHERE clause or no index_manager, must use SeqScan
        if not where_clause or not self.index_manager:
            return seqscan_plan
        
        # Try to find a simple equality predicate on an indexed column
        index_opportunity = self._find_index_opportunity(table_name, where_clause)
        
        if index_opportunity:
            # Found an index we can use - create IndexScan plan
            index_name, column_name, search_key = index_opportunity
            indexscan_plan = QueryPlan(
                plan_type='IndexScan',
                table_name=table_name,
                index_name=index_name,
                index_column=column_name,
                search_key=search_key,
                full_predicate=where_clause
            )
            
            # COST-BASED DECISION: Compare costs and pick cheaper plan
            seqscan_cost = self.estimate_cost(seqscan_plan)
            indexscan_cost = self.estimate_cost(indexscan_plan)
            
            # Choose the plan with lower cost
            if indexscan_cost < seqscan_cost:
                return indexscan_plan
            else:
                return seqscan_plan
        
        # No usable index, use SeqScan
        return seqscan_plan
                full_predicate=where_clause  # Still keep full predicate for additional filters
            )
            
            # COST-BASED DECISION: Compare costs and pick cheaper plan
            seqscan_cost = self.estimate_cost(seqscan_plan)
            indexscan_cost = self.estimate_cost(indexscan_plan)
            
            # Choose the plan with lower cost
            if indexscan_cost < seqscan_cost:
                return indexscan_plan
            else:
                return seqscan_plan
        
        # No usable index, use SeqScan
        return seqscan_plan
    
    def _find_index_opportunity(self, table_name: str, predicate: BinaryOp) -> Optional[tuple]:
        """
        Search for an equality predicate on an indexed column.
        
        This function recursively walks the WHERE clause AST looking for patterns like:
        - column = value (simple equality)
        - column = value AND other_condition (equality within AND)
        
        Args:
            table_name: Name of the table being queried
            predicate: WHERE clause AST node
            
        Returns:
            Tuple of (index_name, column_name, search_key) if found, None otherwise
        """
        if not isinstance(predicate, BinaryOp):
            return None
        
        operator = predicate.operator.upper()
        
        # Case 1: Simple equality predicate (column = value)
        if operator == '=':
            # Check if left side is a column and right side is a literal
            if isinstance(predicate.left, ColumnRef) and isinstance(predicate.right, Literal):
                column_name = predicate.left.name.lower()
                search_key = predicate.right.value
                
                # Check if an index exists on this column
                index_name = self._find_index_for_column(table_name, column_name)
                if index_name:
                    return (index_name, column_name, search_key)
            
            # Also check reversed case (value = column)
            if isinstance(predicate.right, ColumnRef) and isinstance(predicate.left, Literal):
                column_name = predicate.right.name.lower()
                search_key = predicate.left.value
                
                index_name = self._find_index_for_column(table_name, column_name)
                if index_name:
                    return (index_name, column_name, search_key)
        
        # Case 2: AND expression - try left side first (prefer leftmost indexed column)
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
