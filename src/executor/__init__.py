"""
Query Executor Module for AlpacaDB

This module handles the execution of parsed SQL queries.
Now includes query optimization for automatic index selection.
"""

from .executor import QueryExecutor
from .optimizer import QueryOptimizer
from .operators import (
    ScanOperator,
    FilterOperator,
    ProjectOperator,
    SortOperator,
    IndexScanOperator,
)

__all__ = [
    "QueryExecutor",
    "QueryOptimizer",
    "ScanOperator",
    "FilterOperator",
    "ProjectOperator",
    "SortOperator",
    "IndexScanOperator",
]
