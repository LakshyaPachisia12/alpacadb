"""
B-Tree implementation for indexing in AlpacaDB.
Disk-based B-Tree with O(log n) search and insert complexity.
"""

import struct
import pickle
from typing import Any, List, Optional, Tuple
from ..page_manager import PageManager


class BTreeNode:
    """
    Represents a node in the B-Tree.
    
    Each node contains:
    - keys: List of indexed values (sorted)
    - values: List of (page_id, row_id) tuples (for leaf nodes)
    - children: List of child page IDs (for internal nodes)
    - is_leaf: Whether this is a leaf node
    """
    
    def __init__(self, order: int, is_leaf: bool = True):
        """
        Initialize a B-Tree node.
        
        Args:
            order: Maximum number of children per node
            is_leaf: True if this is a leaf node
        """
        self.order = order
        self.is_leaf = is_leaf
        self.keys: List[Any] = []
        self.values: List[Tuple[int, int]] = []  # Only for leaf nodes
        self.children: List[int] = []  # Page IDs of child nodes
    
    def is_full(self) -> bool:
        """Check if node is full and needs splitting."""
        return len(self.keys) >= self.order - 1
    
    def serialize(self) -> bytes:
        """Serialize node to bytes for storage."""
        return pickle.dumps({
            'order': self.order,
            'is_leaf': self.is_leaf,
            'keys': self.keys,
            'values': self.values,
            'children': self.children
        })
    
    @staticmethod
    def deserialize(data: bytes) -> 'BTreeNode':
        """Deserialize node from bytes."""
        node_data = pickle.loads(data)
        node = BTreeNode(node_data['order'], node_data['is_leaf'])
        node.keys = node_data['keys']
        node.values = node_data['values']
        node.children = node_data['children']
        return node


class BTree:
    """
    Disk-based B-Tree for indexing with O(log n) operations.
    
    Maps keys to (page_id, row_id) tuples for fast lookups.
    Nodes are persisted to disk pages for scalability.
    """
    
    def __init__(self, page_manager: PageManager, order: int = 50):
        """
        Initialize B-Tree.
        
        Args:
            page_manager: PageManager for disk I/O
            order: B-Tree order (max children per node, default 50)
        """
        self.order = order
        self.page_manager = page_manager
        self.root_page_id: Optional[int] = None
        # CACHE DISABLED: Every access reads from disk for true O(log n) behavior
        # self._node_cache = {}  # Cache nodes in memory for performance
        
        # Create root node
        if self.root_page_id is None:
            root_node = BTreeNode(order, is_leaf=True)
            self.root_page_id = self._write_node(root_node)

    def _write_node(self, node: BTreeNode) -> int:
        """
        Write a node to disk and return its page ID.
        
        Args:
            node: The node to write
            
        Returns:
            Page ID where the node is stored
        """
        page = self.page_manager.allocate_page(page_type=2)  # INDEX type
        serialized = node.serialize()
        page.records = [serialized]  # Store entire node as one record
        self.page_manager.write_page(page)
        # CACHE DISABLED: No cache updates
        # self._node_cache[page.page_id] = node
        return page.page_id
    
    def _read_node(self, page_id: int) -> Optional[BTreeNode]:
        """
        Read a node from disk (NO CACHING - true O(log n) behavior).
        
        Args:
            page_id: Page ID to read from
            
        Returns:
            BTreeNode or None if not found
        """
        # CACHE DISABLED: Always read from disk for accurate performance
        page = self.page_manager.read_page(page_id)
        if not page or not page.records:
            return None
        
        node = BTreeNode.deserialize(page.records[0])
        return node
    
    def _update_node(self, page_id: int, node: BTreeNode) -> None:
        """
        Update a node on disk.
        
        Args:
            page_id: Page ID to update
            node: Updated node
        """
        page = self.page_manager.read_page(page_id)
        if page:
            serialized = node.serialize()
            page.records = [serialized]
            self.page_manager.write_page(page)
            # CACHE DISABLED: No cache updates
            # self._node_cache[page_id] = node
    
    def _binary_search(self, keys: List[Any], key: Any) -> int:
        """
        Binary search to find insertion position.
        
        Args:
            keys: Sorted list of keys
            key: Key to search for
            
        Returns:
            Index where key should be inserted
        """
        left, right = 0, len(keys)
        while left < right:
            mid = (left + right) // 2
            if keys[mid] < key:
                left = mid + 1
            else:
                right = mid
        return left

    def search(self, key: Any) -> Optional[Tuple[int, int]]:
        """
        Search for a key in the B-Tree.
        O(log n) complexity.
        
        NOTE: Returns only the FIRST match. For duplicate keys, use search_all().
        
        Args:
            key: The value to search for
            
        Returns:
            (page_id, row_id) tuple if found, None otherwise
        """
        if self.root_page_id is None:
            return None
        
        # Track search depth (commented out for performance)
        # self._search_depth = 0
        result = self._search_recursive(self.root_page_id, key)
        # print(f"🔍 Search depth: {self._search_depth}")
        return result
    
    def search_all(self, key: Any) -> List[Tuple[int, int]]:
        """
        Search for ALL occurrences of a key in the B-Tree.
        Handles duplicate keys by returning all matches.
        O(log n + k) complexity where k is the number of matches.
        
        Args:
            key: The value to search for
            
        Returns:
            List of (page_id, row_id) tuples for all matches
        """
        if self.root_page_id is None:
            return []
        
        results = []
        self._search_all_recursive(self.root_page_id, key, results)
        return results
    
    def _search_all_recursive(self, page_id: int, key: Any, results: List[Tuple[int, int]]) -> None:
        """
        Recursive search to find ALL occurrences of a key.
        
        Args:
            page_id: Current node's page ID
            key: Key to search for
            results: List to accumulate results (modified in place)
        """
        node = self._read_node(page_id)
        if not node:
            return
        
        # Binary search to find first occurrence of key
        idx = self._binary_search(node.keys, key)
        
        if node.is_leaf:
            # Collect all matching keys in this leaf node
            # Keys are sorted, so collect consecutive matches
            while idx < len(node.keys) and node.keys[idx] == key:
                results.append(node.values[idx])
                idx += 1
        else:
            # For internal nodes, search in appropriate subtree(s)
            # Check if key exists at this position
            if idx < len(node.keys) and node.keys[idx] == key:
                # Key found - search both left and right subtrees
                self._search_all_recursive(node.children[idx], key, results)
                self._search_all_recursive(node.children[idx + 1], key, results)
            else:
                # Key not at this position - search appropriate child
                self._search_all_recursive(node.children[idx], key, results)

    def range_scan(self, min_key: Optional[Any] = None, max_key: Optional[Any] = None,
                   min_inclusive: bool = True, max_inclusive: bool = True) -> List[Tuple[int, int]]:
        """
        Perform a range scan on the B-Tree.
        
        Args:
            min_key: Minimum key (None for no lower bound)
            max_key: Maximum key (None for no upper bound)
            min_inclusive: Include min_key in results (True for >=, False for >)
            max_inclusive: Include max_key in results (True for <=, False for <)
            
        Returns:
            List of (page_id, row_id) tuples for all keys in range
            
        Examples:
            range_scan(10, 20) -> keys >= 10 AND <= 20
            range_scan(10, 20, True, False) -> keys >= 10 AND < 20
            range_scan(10, None) -> keys >= 10
            range_scan(None, 20) -> keys <= 20
        """
        if self.root_page_id is None:
            return []
        
        results = []
        self._range_scan_node(self._read_node(self.root_page_id), min_key, max_key,
                             min_inclusive, max_inclusive, results)
        return results
    
    def _range_scan_node(self, node: BTreeNode, min_key: Optional[Any], max_key: Optional[Any],
                        min_inclusive: bool, max_inclusive: bool, results: List) -> None:
        """
        Recursively scan nodes for keys in range.
        
        This performs an in-order traversal of the B-Tree, collecting all
        keys that fall within the specified range.
        """
        if node.is_leaf:
            # Leaf node: check each key
            for i, key in enumerate(node.keys):
                in_range = True
                
                # Check lower bound
                if min_key is not None:
                    if min_inclusive:
                        in_range = in_range and (key >= min_key)
                    else:
                        in_range = in_range and (key > min_key)
                
                # Check upper bound
                if max_key is not None:
                    if max_inclusive:
                        in_range = in_range and (key <= max_key)
                    else:
                        in_range = in_range and (key < max_key)
                
                if in_range:
                    results.append(node.values[i])
        else:
            # Internal node: recursively visit children
            for i in range(len(node.children)):
                # Visit child
                child = self._read_node(node.children[i])
                self._range_scan_node(child, min_key, max_key, min_inclusive, max_inclusive, results)

    
    def _search_recursive(self, page_id: int, key: Any, depth: int = 0) -> Optional[Tuple[int, int]]:
        """
        Recursive search through B-Tree.
        
        Args:
            page_id: Current node's page ID
            key: Key to search for
            depth: Current depth in tree (for debugging)
            
        Returns:
            (page_id, row_id) if found, None otherwise
        """
        # self._search_depth = depth  # Track depth
        node = self._read_node(page_id)
        if not node:
            return None
        
        # Binary search within node
        idx = self._binary_search(node.keys, key)
        
        # Check if key exists at this position
        if idx < len(node.keys) and node.keys[idx] == key:
            if node.is_leaf:
                return node.values[idx]
            # For internal nodes, go to right child
            return self._search_recursive(node.children[idx + 1], key, depth + 1)
        
        # If leaf node and not found
        if node.is_leaf:
            return None
        
        # Recurse to appropriate child
        return self._search_recursive(node.children[idx], key, depth + 1)

    def insert(self, key: Any, value: Tuple[int, int]) -> None:
        """
        Insert a key-value pair into the B-Tree.
        O(log n) complexity with potential node splits.
        
        Args:
            key: The indexed value (e.g., email address)
            value: Tuple of (page_id, row_id) where the row is stored
        """
        root = self._read_node(self.root_page_id)
        
        # If root is full, split it
        if root.is_full():
            new_root = BTreeNode(self.order, is_leaf=False)
            new_root.children.append(self.root_page_id)
            
            # Split the old root
            new_child_id = self._split_child(self.root_page_id, new_root, 0)
            
            # Write new root
            self.root_page_id = self._write_node(new_root)
        
        # Insert into non-full root
        self._insert_non_full(self.root_page_id, key, value)
    
    def _insert_non_full(self, page_id: int, key: Any, value: Tuple[int, int]) -> None:
        """
        Insert into a node that is not full.
        
        Args:
            page_id: Node's page ID
            key: Key to insert
            value: Value to insert
        """
        node = self._read_node(page_id)
        idx = self._binary_search(node.keys, key)
        
        if node.is_leaf:
            # Insert into leaf node
            node.keys.insert(idx, key)
            node.values.insert(idx, value)
            self._update_node(page_id, node)
        else:
            # Recurse to child
            child_id = node.children[idx]
            child = self._read_node(child_id)
            
            if child.is_full():
                # Split child before recursing
                self._split_child(child_id, node, idx)
                self._update_node(page_id, node)
                
                # Determine which of the two children to recurse to
                if key > node.keys[idx]:
                    idx += 1
                child_id = node.children[idx]
            
            self._insert_non_full(child_id, key, value)
    
    def _split_child(self, child_id: int, parent: BTreeNode, idx: int) -> int:
        """
        Split a full child node.
        
        Args:
            child_id: Page ID of child to split
            parent: Parent node
            idx: Index of child in parent's children list
            
        Returns:
            Page ID of new right sibling
        """
        child = self._read_node(child_id)
        mid = len(child.keys) // 2
        
        # CRITICAL FIX: Save the median key BEFORE modifying arrays
        # For leaf nodes, promote the first key of right sibling
        # For internal nodes, promote the median key
        if child.is_leaf:
            promoted_key = child.keys[mid]
        else:
            promoted_key = child.keys[mid]
        
        # Create new right sibling
        new_node = BTreeNode(self.order, is_leaf=child.is_leaf)
        
        # Move half of keys to new node
        if child.is_leaf:
            # For leaf nodes: keep median in left, copy to right
            new_node.keys = child.keys[mid:]
            child.keys = child.keys[:mid]
            new_node.values = child.values[mid:]
            child.values = child.values[:mid]
        else:
            # For internal nodes: median goes to parent, split children
            new_node.keys = child.keys[mid + 1:]
            child.keys = child.keys[:mid]
            new_node.children = child.children[mid + 1:]
            child.children = child.children[:mid + 1]
        
        # Write new sibling
        new_node_id = self._write_node(new_node)
        
        # Update child
        self._update_node(child_id, child)
        
        # Insert promoted key into parent
        parent.keys.insert(idx, promoted_key)
        parent.children.insert(idx + 1, new_node_id)
        
        return new_node_id

    def delete(self, key: Any, value: Optional[Tuple[int, int]] = None) -> bool:
        """
        Delete a key (or specific key-value pair) from the B-Tree.
        
        Args:
            key: Key to delete
            value: Optional specific value to delete (for duplicate keys)
                   If None, deletes first matching key
        
        Returns:
            True if deletion successful, False if key not found
        
        Note: This is a simplified implementation that rebuilds affected nodes.
        For production use, consider implementing proper B-Tree deletion with
        borrowing and merging.
        """
        if self.root_page_id is None:
            return False
        
        root = self._read_node(self.root_page_id)
        success = self._delete_from_node(self.root_page_id, root, key, value)
        
        # If root is now empty and has children, promote first child
        if success and not root.is_leaf and len(root.keys) == 0:
            if len(root.children) > 0:
                self.root_page_id = root.children[0]
        
        return success
    
    def _delete_from_node(self, page_id: int, node: BTreeNode, key: Any, value: Optional[Tuple[int, int]]) -> bool:
        """
        Delete a key from a node (simplified implementation).
        
        This uses a simplified deletion strategy:
        1. Find the key in the leaf
        2. Remove it
        3. Don't worry about underflow (acceptable for educational DBMS)
        
        For production, should implement:
        - Borrowing from siblings when underflow occurs
        - Merging nodes when borrowing isn't possible
        - Redistributing keys properly
        """
        if node.is_leaf:
            # Leaf node: try to find and remove the key
            for i, k in enumerate(node.keys):
                if k == key:
                    # If specific value requested, check if it matches
                    if value is not None and node.values[i] != value:
                        continue
                    
                    # Remove key and value
                    node.keys.pop(i)
                    node.values.pop(i)
                    self._update_node(page_id, node)
                    return True
            
            return False  # Key not found
        
        else:
            # Internal node: find appropriate child
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1
            
            if i < len(node.children):
                child_id = node.children[i]
                child = self._read_node(child_id)
                return self._delete_from_node(child_id, child, key, value)
            
            return False
    
    def size(self) -> int:
        """
        Return the number of entries in the index.
        Note: Requires traversing entire tree.
        """
        if self.root_page_id is None:
            return 0
        return self._count_keys(self.root_page_id)
    
    def _count_keys(self, page_id: int) -> int:
        """Recursively count keys in tree."""
        node = self._read_node(page_id)
        if not node:
            return 0
        
        count = len(node.keys)
        if not node.is_leaf:
            for child_id in node.children:
                count += self._count_keys(child_id)
        
        return count