"""
Query Optimizer - Chooses optimal execution plan for queries.

The optimizer decides between:
- Full table scan (ScanOperator)
- Index scan (IndexScanOperator)

Based on cost estimation and available indexes.
"""

from typing import Optional, Any, Tuple
from ..query.ast_nodes import BinaryOp, ColumnRef, Literal


class QueryOptimizer:
    """
    Simple cost-based query optimizer.
    
    Makes decisions about:
    1. Whether to use an index or do a full table scan
    2. Which index to use if multiple are available
    3. Optimal B-Tree order based on dataset size
    """
    
    # Cost constants (arbitrary units)
    COST_INDEX_SEARCH = 5      # Cost of one B-Tree search (log n)
    COST_PAGE_READ = 10        # Cost of reading one page
    COST_ROW_COMPARE = 1       # Cost of comparing one row in memory
    
    # B-Tree order selection based on dataset size
    BTREE_ORDER_SMALL = 10     # For < 10k rows
    BTREE_ORDER_MEDIUM = 15    # For 10k-100k rows
    BTREE_ORDER_LARGE = 20     # For 100k+ rows
    
    def __init__(self, catalog, index_manager, table_manager):
        """
        Args:
            catalog: Database catalog for schema info
            index_manager: Index manager for checking available indexes
            table_manager: Table manager for row count estimates
        """
        self.catalog = catalog
        self.index_manager = index_manager
        self.table_manager = table_manager
    
    def can_use_index(self, table_name: str, where_clause) -> Optional[Tuple[str, Any]]:
        """
        Determine if an index can be used for a WHERE clause.
        
        Currently supports simple equality predicates only:
        - WHERE column = value
        
        Args:
            table_name: Name of the table being queried
            where_clause: The WHERE clause AST node
            
        Returns:
            Tuple of (index_name, search_key) if index can be used, None otherwise
        """
        if where_clause is None:
            return None
        
        # Check if WHERE clause is a simple equality: column = value
        if not isinstance(where_clause, BinaryOp):
            return None
        
        if where_clause.operator.upper() != "=":
            return None  # Only support equality for now
        
        # Check if one side is a column and other is a literal
        left = where_clause.left
        right = where_clause.right
        
        column_name = None
        search_key = None
        
        if isinstance(left, ColumnRef) and isinstance(right, Literal):
            column_name = left.name
            search_key = right.value
        elif isinstance(right, ColumnRef) and isinstance(left, Literal):
            column_name = right.name
            search_key = left.value
        else:
            return None  # More complex predicate (e.g., column = column)
        
        # Check if an index exists on this column
        indexes = self.catalog.get_indexes_for_table(table_name)
        for index in indexes:
            if index.column_name.lower() == column_name.lower():
                return (index.index_name, search_key)
        
        return None  # No suitable index found
    
    def should_use_index(self, table_name: str, index_name: str) -> bool:
        """
        Cost-based decision: should we use the index or do a full scan?
        
        Index is beneficial when:
        - Table has many rows (high scan cost)
        - Index selectivity is good (few rows match)
        
        Args:
            table_name: Name of the table
            index_name: Name of the index to consider
            
        Returns:
            True if index should be used, False for full scan
        """
        # Estimate table size
        table_rows = self._estimate_table_rows(table_name)
        
        # For very small tables (< 100 rows), full scan is often faster
        # due to index overhead
        if table_rows < 100:
            return False
        
        # Calculate estimated costs
        scan_cost = self._estimate_scan_cost(table_rows)
        index_cost = self._estimate_index_cost(table_rows)
        
        # Use index if it's cheaper
        return index_cost < scan_cost
    
    def _estimate_table_rows(self, table_name: str) -> int:
        """
        Estimate number of rows in a table.
        
        For now, we do a quick count. In a real system, this would
        use statistics stored in the catalog.
        """
        schema = self.catalog.get_table_schema(table_name)
        if not schema or schema.first_page_id is None:
            return 0
        
        # Quick estimation: count pages and assume avg rows per page
        row_count = 0
        current_page_id = schema.first_page_id
        page_count = 0
        
        # Sample first few pages to estimate
        while current_page_id is not None and page_count < 5:
            page = self.table_manager.page_manager.read_page(current_page_id)
            if page:
                row_count += len(page.records)
                current_page_id = page.next_page_id
                page_count += 1
            else:
                break
        
        # If we have samples, estimate total
        if page_count > 0:
            avg_rows_per_page = row_count / page_count
            
            # Count remaining pages
            total_pages = page_count
            while current_page_id is not None:
                total_pages += 1
                page = self.table_manager.page_manager.read_page(current_page_id)
                if page:
                    current_page_id = page.next_page_id
                else:
                    break
            
            return int(avg_rows_per_page * total_pages)
        
        return row_count
    
    def _estimate_scan_cost(self, row_count: int) -> float:
        """
        Estimate cost of full table scan.
        
        Cost = (pages to read × page read cost) + (rows × comparison cost)
        """
        # Assume ~50 rows per page (rough estimate)
        pages = max(1, row_count // 50)
        
        cost = (pages * self.COST_PAGE_READ) + (row_count * self.COST_ROW_COMPARE)
        return cost
    
    def _estimate_index_cost(self, row_count: int) -> float:
        """
        Estimate cost of index scan.
        
        Cost = B-Tree search cost + page read for result row
        
        B-Tree search is O(log n) with tree traversal
        """
        import math
        
        if row_count == 0:
            return 0
        
        # B-Tree height depends on order and row count
        # For order=10-20, typical height is log_10(n) to log_20(n)
        tree_height = max(1, math.log(row_count, 15))  # Assume order ~15
        
        # Cost = traversing tree levels + reading index pages + fetching data page
        cost = (tree_height * self.COST_INDEX_SEARCH) + self.COST_PAGE_READ
        
        return cost
    
    def get_optimal_btree_order(self, estimated_rows: int) -> int:
        """
        Choose optimal B-Tree order based on dataset size.
        
        Smaller orders (4-10):
        - Good for small datasets
        - Lower per-node search cost
        - More tree levels
        
        Larger orders (15-25):
        - Good for large datasets
        - Fewer tree levels
        - Higher per-node search cost
        
        Args:
            estimated_rows: Estimated number of rows in table
            
        Returns:
            Optimal B-Tree order
        """
        if estimated_rows < 10_000:
            return self.BTREE_ORDER_SMALL  # 10
        elif estimated_rows < 100_000:
            return self.BTREE_ORDER_MEDIUM  # 15
        else:
            return self.BTREE_ORDER_LARGE  # 20
    
    def explain_query(self, table_name: str, where_clause) -> str:
        """
        Generate an EXPLAIN-style output showing query plan.
        
        Useful for debugging and understanding optimizer decisions.
        """
        lines = []
        lines.append("Query Execution Plan:")
        lines.append("=" * 50)
        
        # Check for index usage
        index_info = self.can_use_index(table_name, where_clause)
        
        if index_info:
            index_name, search_key = index_info
            should_use = self.should_use_index(table_name, index_name)
            
            if should_use:
                lines.append(f"✓ INDEX SCAN on {table_name}")
                lines.append(f"  - Index: {index_name}")
                lines.append(f"  - Search Key: {search_key}")
                lines.append(f"  - Estimated Cost: O(log n)")
            else:
                lines.append(f"✓ SEQUENTIAL SCAN on {table_name}")
                lines.append(f"  - Reason: Table too small for index benefit")
                lines.append(f"  - Available Index: {index_name} (not used)")
        else:
            lines.append(f"✓ SEQUENTIAL SCAN on {table_name}")
            lines.append(f"  - Reason: No suitable index available")
        
        lines.append("=" * 50)
        return "\n".join(lines)
