"""
Cost Estimator for Query Plans (Phase 2)

Provides simple cost estimation for sequential scans and index scans
using basic table and index statistics from the catalog.

All costs are in abstract units and relative; only the ordering matters.
"""
from math import log, ceil
from typing import Any, Dict, Optional

# Tunable constants - calibrated to favor indexes for selective predicates
PAGE_IO_COST = 1.0       # Cost to read one page from disk
CPU_TUPLE_COST = 0.01    # Cost to process one tuple/row
DEFAULT_SELECTIVITY_EQ = 0.1  # Fallback selectivity for equality when stats missing
BTREE_ORDER = 4          # Default B-Tree order used in indexing
INDEX_LOOKUP_COST = 1.2  # Base cost for index lookup - higher to account for tree traversal overhead


def cost_seq_scan(table_stats: Optional[Dict[str, int]]) -> float:
    """
    Estimate cost of a sequential scan over a table.

    Uses: num_pages and num_rows if available.
    """
    if not table_stats:
        # Conservative default: assume small table
        return 10 * PAGE_IO_COST

    num_pages = table_stats.get('num_pages', 0) or 0
    num_rows = table_stats.get('num_rows', 0) or 0

    io_cost = num_pages * PAGE_IO_COST
    cpu_cost = num_rows * CPU_TUPLE_COST
    return io_cost + cpu_cost


def _estimate_index_depth(num_distinct: Optional[int]) -> int:
    if not num_distinct or num_distinct <= 1:
        return 1
    try:
        depth = 1 + ceil(log(max(2, num_distinct), BTREE_ORDER))
        return max(1, int(depth))
    except Exception:
        return 3


def cost_index_scan(table_stats: Optional[Dict[str, int]],
                     index_stats: Optional[Dict[str, Any]],
                     predicate_type: str = 'eq') -> float:
    """
    Estimate cost of an index scan for predicate type.

    For equality:
      cost ≈ INDEX_LOOKUP_COST + index_depth * 0.3 * PAGE_IO_COST + expected_matches * CPU_TUPLE_COST
    where expected_matches = selectivity * num_rows.

    Note: B-tree depth cost is reduced (0.3x) because nodes are often cached in memory.
    For low selectivity (> 0.3), index scan is penalized as seq scan becomes more efficient.
    """
    num_rows = 0
    seq_cost_baseline = None
    if table_stats:
        num_rows = table_stats.get('num_rows', 0) or 0
        seq_cost_baseline = cost_seq_scan(table_stats)

    selectivity = DEFAULT_SELECTIVITY_EQ
    num_distinct = None
    if index_stats and predicate_type == 'eq':
        num_distinct = index_stats.get('num_distinct')
        if num_distinct and num_distinct > 0:
            selectivity = 1.0 / float(num_distinct)
            selectivity = max(0.0, min(1.0, selectivity))

    expected_matches = selectivity * num_rows

    index_depth = _estimate_index_depth(num_distinct)

    # Base lookup cost + reduced depth cost (cached nodes) + tuple processing
    io_cost = INDEX_LOOKUP_COST + (index_depth * 0.3 * PAGE_IO_COST)
    cpu_cost = expected_matches * CPU_TUPLE_COST

    base_cost = io_cost + cpu_cost

    # Heavily penalize index scan for poor selectivity (> 30% of rows)
    # When selectivity is poor, sequential scan is much more efficient
    if selectivity > 0.3:
        # Exponential penalty that makes index scan very expensive for low selectivity
        penalty_factor = 1.0 + (selectivity - 0.3) * 15.0
        base_cost *= penalty_factor
        # Ensure index cost is always worse than seq scan for poor selectivity
        if seq_cost_baseline is not None:
            base_cost = max(base_cost, seq_cost_baseline * 1.3)

    return base_cost
