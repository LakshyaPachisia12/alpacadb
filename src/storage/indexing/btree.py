"""
B-Tree implementation for indexing in AlpacaDB.
"""

import struct
import pickle
from typing import Any, List, Optional, Tuple
from ..page_manager import PageManager
from ..page import Page, PAGE_TYPE_INDEX

class BTreeNode:
    def __init__(self, is_leaf: bool = True, order: int = 4):
        self.is_leaf = is_leaf
        self.keys: List[Any] = []
        self.children: List[int] = []  # Page IDs of child nodes
        self.values: List[Tuple[int, int]] = []  # (page_id, row_id) pairs
        self.order = order
        self.page_id: Optional[int] = None
        self.next_leaf_page_id: Optional[int] = None  # For range scans: link to next leaf

    def is_full(self) -> bool:
        return len(self.keys) >= (2 * self.order - 1)

class BTree:
    def __init__(self, page_manager: PageManager, order: int = 4):
        self.order = order
        self.page_manager = page_manager
        self.root_page_id: Optional[int] = None

    def insert(self, key: Any, value: Tuple[int, int]) -> None:
        """Insert a key-value pair into the B-Tree."""
        if self.root_page_id is None:
            # Create root node
            root = BTreeNode(is_leaf=True, order=self.order)
            root.keys.append(key)
            root.values.append(value)
            self.root_page_id = self._save_node(root)
            return

        root = self._load_node(self.root_page_id)
        if root.is_full():
            # Split root
            new_root = BTreeNode(is_leaf=False, order=self.order)
            new_root.children.append(self.root_page_id)
            self._split_child(new_root, 0)
            self.root_page_id = self._save_node(new_root)
            self._insert_non_full(new_root, key, value)
        else:
            self._insert_non_full(root, key, value)

    def search(self, key: Any) -> Optional[Tuple[int, int]]:
        """Search for a key in the B-Tree and return its associated value."""
        if self.root_page_id is None:
            return None
        return self._search_node(self._load_node(self.root_page_id), key)
    
    def search_all(self, key: Any) -> List[Tuple[int, int]]:
        """
        Search for a key in the B-Tree and return ALL associated values.
        
        This handles duplicate keys by returning all matching entries.
        
        Args:
            key: Key to search for
            
        Returns:
            List of (page_id, row_id) tuples for all matching entries
        """
        if self.root_page_id is None:
            return []
        return self._search_all_node(self._load_node(self.root_page_id), key)
    
    def range_search(self, start_key: Any, end_key: Any, 
                     include_start: bool = True, include_end: bool = True) -> List[Tuple[int, int]]:
        """
        Phase 3: Search for all keys in a range [start_key, end_key].
        
        Uses leaf node linking to efficiently traverse the range without
        traversing the entire tree for each key.
        
        Args:
            start_key: Start of range (None = -infinity)
            end_key: End of range (None = +infinity)
            include_start: Whether to include start_key (>= vs >)
            include_end: Whether to include end_key (<= vs <)
            
        Returns:
            List of (page_id, row_id) tuples for all keys in range
        """
        if self.root_page_id is None:
            return []
        
        results = []
        
        # Find the starting leaf node
        if start_key is None:
            # Start from leftmost leaf
            current_node = self._find_leftmost_leaf()
        else:
            current_node = self._find_leaf_for_key(start_key)
        
        # Traverse leaves using next_leaf_page_id links
        while current_node is not None:
            # Collect matching keys from current leaf
            for i, key in enumerate(current_node.keys):
                # Check if key is in range
                if start_key is not None:
                    if include_start:
                        if key < start_key:
                            continue
                    else:
                        if key <= start_key:
                            continue
                
                if end_key is not None:
                    if include_end:
                        if key > end_key:
                            # We've gone past the range, stop
                            return results
                    else:
                        if key >= end_key:
                            return results
                
                # Key is in range, add its value
                results.append(current_node.values[i])
            
            # Move to next leaf
            if current_node.next_leaf_page_id is not None:
                current_node = self._load_node(current_node.next_leaf_page_id)
            else:
                break
        
        return results
    
    def _find_leftmost_leaf(self) -> Optional[BTreeNode]:
        """Find the leftmost (smallest key) leaf node."""
        if self.root_page_id is None:
            return None
        
        node = self._load_node(self.root_page_id)
        while not node.is_leaf:
            if len(node.children) > 0:
                node = self._load_node(node.children[0])
            else:
                return None
        return node
    
    def _find_leaf_for_key(self, key: Any) -> Optional[BTreeNode]:
        """Find the leaf node that would contain the given key."""
        if self.root_page_id is None:
            return None
        
        node = self._load_node(self.root_page_id)
        while not node.is_leaf:
            # Find appropriate child
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1
            
            if i < len(node.children):
                node = self._load_node(node.children[i])
            else:
                return None
        
        return node

    def delete(self, key: Any) -> bool:
        """Delete a key from the B-Tree."""
        if self.root_page_id is None:
            return False
        # TODO: Implement delete - for now just return False
        # Delete is complex and can be deferred
        return False
    
    def delete_entry(self, key: Any, value: Tuple[int, int]) -> bool:
        """
        Phase 3: Delete a specific (key, value) pair from the B-Tree.
        
        This is a simplified deletion that doesn't rebalance the tree.
        Good enough for incremental index maintenance without full rebuild.
        
        Args:
            key: Key to delete
            value: Specific (page_id, row_id) pair to remove
            
        Returns:
            True if entry was found and deleted, False otherwise
        """
        if self.root_page_id is None:
            return False
        
        # Find the leaf node containing this key
        leaf = self._find_leaf_for_key(key)
        if leaf is None:
            return False
        
        # Find the exact (key, value) pair in this leaf
        for i in range(len(leaf.keys)):
            if leaf.keys[i] == key and leaf.values[i] == value:
                # Found it! Remove the entry
                del leaf.keys[i]
                del leaf.values[i]
                
                # Save the modified leaf
                self._save_node(leaf)
                return True
        
        # Entry not found
        return False
    
    def _search_node(self, node: BTreeNode, key: Any) -> Optional[Tuple[int, int]]:
        """
        Search for a key within a node (recursively).
        
        This implements B+Tree search where all values are in leaf nodes.
        
        Args:
            node: Node to search in
            key: Key to search for
            
        Returns:
            (page_id, row_id) tuple if found, None otherwise
        """
        # Find position where key should be
        i = 0
        while i < len(node.keys) and key >= node.keys[i]:
            i += 1
        
        # If leaf node, check if key exists
        if node.is_leaf:
            # Search backwards from position i-1 for exact match
            for j in range(len(node.keys)):
                if node.keys[j] == key:
                    return node.values[j]
            return None
        
        # Internal node: navigate to appropriate child
        if i < len(node.children):
            child = self._load_node(node.children[i])
            return self._search_node(child, key)
        
        return None
    
    def _search_all_node(self, node: BTreeNode, key: Any) -> List[Tuple[int, int]]:
        """
        Search for ALL occurrences of a key within a node (recursively).
        
        Handles duplicate keys by collecting all matching entries.
        
        Args:
            node: Node to search in
            key: Key to search for
            
        Returns:
            List of (page_id, row_id) tuples for all matching entries
        """
        results = []
        
        # Find position where key should be
        i = 0
        while i < len(node.keys) and key >= node.keys[i]:
            i += 1
        
        # If leaf node, collect all matching keys
        if node.is_leaf:
            for j in range(len(node.keys)):
                if node.keys[j] == key:
                    results.append(node.values[j])
            return results
        
        # Internal node: navigate to appropriate child
        if i < len(node.children):
            child = self._load_node(node.children[i])
            return self._search_all_node(child, key)
        
        return results

    def _serialize_node(self, node: BTreeNode) -> bytes:
        """
        Convert node to bytes for storage.
        
        Format:
        - 1 byte: is_leaf flag (1 for leaf, 0 for internal)
        - 2 bytes: number of keys
        - 4 bytes: next_leaf_page_id (or -1 if None) - for Phase 3 range scans
        - Pickled keys list
        - Pickled values list (for leaf nodes)
        - Pickled children list (for internal nodes)
        """
        parts = []
        
        # Is leaf flag
        parts.append(struct.pack('B', 1 if node.is_leaf else 0))
        
        # Number of keys
        parts.append(struct.pack('<H', len(node.keys)))
        
        # Next leaf page ID (for range scans)
        next_leaf = node.next_leaf_page_id if node.next_leaf_page_id is not None else -1
        parts.append(struct.pack('<i', next_leaf))
        
        # Pickle keys, values, and children
        keys_bytes = pickle.dumps(node.keys)
        parts.append(struct.pack('<I', len(keys_bytes)))
        parts.append(keys_bytes)
        
        if node.is_leaf:
            values_bytes = pickle.dumps(node.values)
            parts.append(struct.pack('<I', len(values_bytes)))
            parts.append(values_bytes)
        else:
            children_bytes = pickle.dumps(node.children)
            parts.append(struct.pack('<I', len(children_bytes)))
            parts.append(children_bytes)
        
        return b''.join(parts)

    def _deserialize_node(self, data: bytes) -> BTreeNode:
        """
        Convert bytes back to node.
        
        Reverses the serialization format.
        """
        offset = 0
        
        # Is leaf flag
        is_leaf = struct.unpack('B', data[offset:offset+1])[0] == 1
        offset += 1
        
        # Number of keys
        num_keys = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
        
        # Next leaf page ID (Phase 3 range scans) - handle backward compatibility
        next_leaf = None
        if len(data) > offset + 4:
            next_leaf_id = struct.unpack('<i', data[offset:offset+4])[0]
            offset += 4
            next_leaf = next_leaf_id if next_leaf_id != -1 else None
        
        # Deserialize keys
        keys_len = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4
        keys = pickle.loads(data[offset:offset+keys_len])
        offset += keys_len
        
        # Create node
        node = BTreeNode(is_leaf=is_leaf, order=self.order)
        node.keys = keys
        node.next_leaf_page_id = next_leaf
        
        # Deserialize values (leaf) or children (internal)
        if is_leaf:
            values_len = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            node.values = pickle.loads(data[offset:offset+values_len])
        else:
            children_len = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            node.children = pickle.loads(data[offset:offset+children_len])
        
        return node

    def _load_node(self, page_id: int) -> BTreeNode:
        """Load a node from disk."""
        page = self.page_manager.read_page(page_id)
        node = self._deserialize_node(page.records[0])  # Node stored in first record
        node.page_id = page_id
        return node
    
    def _save_node(self, node: BTreeNode) -> int:
        """Save a node to disk and return its page_id."""
        node_bytes = self._serialize_node(node)
        
        if node.page_id is not None:
            # Update existing page
            page = self.page_manager.read_page(node.page_id)
            page.records = [node_bytes]
            self.page_manager.write_page(page)
            return node.page_id
        else:
            # Allocate new page
            page = self.page_manager.allocate_page(page_type=PAGE_TYPE_INDEX)
            page.records = [node_bytes]
            self.page_manager.write_page(page)
            node.page_id = page.page_id
            return page.page_id
    
    def _split_child(self, parent: BTreeNode, index: int) -> None:
        """
        Split a full child node.
        
        Args:
            parent: Parent node
            index: Index of the child to split in parent.children
        """
        # Load the full child
        full_child_id = parent.children[index]
        full_child = self._load_node(full_child_id)
        
        # Create new node to hold second half
        new_node = BTreeNode(is_leaf=full_child.is_leaf, order=self.order)
        mid_index = self.order - 1
        
        # For leaf nodes: copy mid key up to parent, keep all values in leaves
        # For internal nodes: move mid key up to parent
        if full_child.is_leaf:
            # Copy mid key (don't remove from leaf)
            mid_key = full_child.keys[mid_index]
            new_node.keys = full_child.keys[mid_index:]
            full_child.keys = full_child.keys[:mid_index]
            
            # Split values
            new_node.values = full_child.values[mid_index:]
            full_child.values = full_child.values[:mid_index]
            
            # Phase 3: Link leaf nodes for range scans
            # new_node inherits the old next pointer, full_child points to new_node
            new_node.next_leaf_page_id = full_child.next_leaf_page_id
            # We'll set full_child.next_leaf_page_id after saving new_node (need its page_id)
        else:
            # Move mid key (remove from child)
            mid_key = full_child.keys[mid_index]
            new_node.keys = full_child.keys[mid_index + 1:]
            full_child.keys = full_child.keys[:mid_index]
            
            # Split children
            new_node.children = full_child.children[mid_index + 1:]
            full_child.children = full_child.children[:mid_index + 1]
        
        # Save new node first to get its page_id
        new_node_id = self._save_node(new_node)
        
        # Phase 3: Update leaf linking
        if full_child.is_leaf:
            full_child.next_leaf_page_id = new_node_id
        
        # Save full_child with updated next pointer
        self._save_node(full_child)
        
        # Insert mid key into parent
        parent.keys.insert(index, mid_key)
        parent.children.insert(index + 1, new_node_id)
        
        # Save parent
        self._save_node(parent)
    
    def _insert_non_full(self, node: BTreeNode, key: Any, value: Tuple[int, int]) -> None:
        """
        Insert into a node that is not full.
        
        Args:
            node: Node to insert into
            key: Key to insert
            value: Value associated with key
        """
        if node.is_leaf:
            # Insert into sorted position
            i = len(node.keys) - 1
            while i >= 0 and key < node.keys[i]:
                i -= 1
            node.keys.insert(i + 1, key)
            node.values.insert(i + 1, value)
            self._save_node(node)
        else:
            # Find child to insert into
            i = len(node.keys) - 1
            while i >= 0 and key < node.keys[i]:
                i -= 1
            i += 1
            
            child = self._load_node(node.children[i])
            if child.is_full():
                # Split child first
                self._split_child(node, i)
                # Reload node after split
                node = self._load_node(node.page_id)
                if key > node.keys[i]:
                    i += 1
                child = self._load_node(node.children[i])
            
            self._insert_non_full(child, key, value)