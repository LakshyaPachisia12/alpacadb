"""
Index management module for AlpacaDB.

Provides B-Tree implementation and index management with automatic
order selection and query optimization support.
"""

from .btree import BTree, BTreeNode
from .index_manager import IndexManager

__all__ = ["BTree", "BTreeNode", "IndexManager"]