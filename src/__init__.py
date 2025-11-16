"""
AlpacaDB - A custom relational database management system.

This package contains the core implementation of AlpacaDB,
including storage engine, query processing, and transaction management.
"""

__version__ = "0.2.0"
__author__ = "AlpacaDB Team"

# Export error classes
from .errors import (
    AlpacaDBError,
    SyntaxError,
    ParserError,
    LexerError,
    OptimizerError,
    ExecutionError,
    TableNotFoundError,
    ColumnNotFoundError,
    IndexError,
    IndexNotFoundError,
)