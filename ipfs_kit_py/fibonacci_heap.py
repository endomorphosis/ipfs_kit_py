#!/usr/bin/env python3
"""
Fibonacci Heap Implementation for Workflow Priority Queue

This module implements a Fibonacci heap data structure optimized for
workflow scheduling in resource-constrained environments. The Fibonacci
heap provides efficient priority queue operations:

- Insert: O(1)
- Find minimum: O(1)
- Delete minimum: O(log n) amortized
- Decrease key: O(1) amortized
- Merge: O(1)

This makes it ideal for dynamic priority scheduling where workflows
may need to be re-prioritized based on available resources.
"""

from typing import Any, Dict, List, Optional, Generic, TypeVar
from dataclasses import dataclass, field
import math


T = TypeVar('T')


@dataclass
class FibonacciNode(Generic[T]):
    """Node in a Fibonacci heap."""
    key: float
    value: T
    parent: Optional['FibonacciNode[T]'] = None
    child: Optional['FibonacciNode[T]'] = None
    left: Optional['FibonacciNode[T]'] = None
    right: Optional['FibonacciNode[T]'] = None
    degree: int = 0
    mark: bool = False
    
    def __post_init__(self):
        """Initialize circular doubly-linked list."""
        if self.left is None:
            self.left = self
        if self.right is None:
            self.right = self


class FibonacciHeap(Generic[T]):
    """
    Fibonacci Heap for efficient priority queue operations.
    
    The heap maintains a collection of trees with the heap property,
    where parent keys are always less than or equal to child keys.
    This implementation uses a min-heap by default (smallest key has
    highest priority).
    """
    
    def __init__(self):
        """Initialize an empty Fibonacci heap."""
        self.min_node: Optional[FibonacciNode[T]] = None
        self.total_nodes: int = 0
        self.root_list: List[FibonacciNode[T]] = []
    
    def is_empty(self) -> bool:
        """Check if the heap is empty."""
        return self.min_node is None
    
    def insert(self, key: float, value: T) -> FibonacciNode[T]:
        """
        Insert a new node into the heap.
        
        Args:
            key: Priority key (lower values have higher priority)
            value: Data associated with this node
            
        Returns:
            The newly created node
        """
        node = FibonacciNode(key=key, value=value)
        
        if self.min_node is None:
            # First node in heap
            self.min_node = node
        else:
            # Add to root list
            self._add_to_root_list(node)
            if node.key < self.min_node.key:
                self.min_node = node
        
        self.total_nodes += 1
        return node
    
    def find_min(self) -> Optional[T]:
        """
        Get the value with minimum key without removing it.
        
        Returns:
            Value of the minimum node, or None if heap is empty
        """
        return self.min_node.value if self.min_node else None
    
    def extract_min(self) -> Optional[T]:
        """
        Remove and return the value with minimum key.
        
        Returns:
            Value of the minimum node, or None if heap is empty
        """
        min_node = self.min_node
        
        if min_node is None:
            return None
        
        # Add all children to root list
        if min_node.child is not None:
            child = min_node.child
            children = []
            
            # Collect all children
            start = child
            while True:
                children.append(child)
                child = child.right
                if child == start:
                    break
            
            # Add children to root list
            for child in children:
                child.parent = None
                self._add_to_root_list(child)
        
        # Remove min_node from root list
        self._remove_from_root_list(min_node)
        
        if min_node == min_node.right:
            # This was the only node
            self.min_node = None
        else:
            # Set min to an arbitrary root, then consolidate
            self.min_node = min_node.right
            self._consolidate()
        
        self.total_nodes -= 1
        return min_node.value
    
    def decrease_key(self, node: FibonacciNode[T], new_key: float) -> None:
        """
        Decrease the key of a node.
        
        Args:
            node: Node to update
            new_key: New key value (must be less than current key)
        """
        if new_key > node.key:
            raise ValueError("New key is greater than current key")
        
        node.key = new_key
        parent = node.parent
        
        if parent is not None and node.key < parent.key:
            self._cut(node, parent)
            self._cascading_cut(parent)
        
        if node.key < self.min_node.key:
            self.min_node = node
    
    def merge(self, other: 'FibonacciHeap[T]') -> None:
        """
        Merge another heap into this one.
        
        Args:
            other: Another FibonacciHeap to merge
        """
        if other.min_node is None:
            return
        
        if self.min_node is None:
            self.min_node = other.min_node
        else:
            # Concatenate root lists
            self._concatenate_lists(self.min_node, other.min_node)
            if other.min_node.key < self.min_node.key:
                self.min_node = other.min_node
        
        self.total_nodes += other.total_nodes
    
    def _add_to_root_list(self, node: FibonacciNode[T]) -> None:
        """Add a node to the root list."""
        if self.min_node is None:
            self.min_node = node
            node.left = node
            node.right = node
        else:
            # Insert into circular list
            node.right = self.min_node
            node.left = self.min_node.left
            self.min_node.left.right = node
            self.min_node.left = node
    
    def _remove_from_root_list(self, node: FibonacciNode[T]) -> None:
        """Remove a node from the root list."""
        if node.right == node:
            # This was the only node
            return
        
        node.left.right = node.right
        node.right.left = node.left
    
    def _consolidate(self) -> None:
        """Consolidate trees to maintain heap structure."""
        if self.min_node is None:
            return
        
        # Calculate max degree
        max_degree = int(math.log(self.total_nodes) * 2) + 1
        degree_table: List[Optional[FibonacciNode[T]]] = [None] * max_degree
        
        # Collect all root nodes
        roots = []
        root = self.min_node
        if root is not None:
            start = root
            while True:
                roots.append(root)
                root = root.right
                if root == start:
                    break
        
        # Process each root
        for root in roots:
            degree = root.degree
            
            while degree_table[degree] is not None:
                # Another tree with same degree
                other = degree_table[degree]
                
                if root.key > other.key:
                    root, other = other, root
                
                # Link other as child of root
                self._link(other, root)
                degree_table[degree] = None
                degree += 1
            
            degree_table[degree] = root
        
        # Rebuild root list and find new minimum
        self.min_node = None
        for node in degree_table:
            if node is not None:
                if self.min_node is None:
                    self.min_node = node
                    node.left = node
                    node.right = node
                else:
                    self._add_to_root_list(node)
                    if node.key < self.min_node.key:
                        self.min_node = node
    
    def _link(self, child: FibonacciNode[T], parent: FibonacciNode[T]) -> None:
        """Link child as a child of parent."""
        # Remove child from root list
        self._remove_from_root_list(child)
        
        # Make child a child of parent
        child.parent = parent
        if parent.child is None:
            parent.child = child
            child.left = child
            child.right = child
        else:
            child.right = parent.child
            child.left = parent.child.left
            parent.child.left.right = child
            parent.child.left = child
        
        parent.degree += 1
        child.mark = False
    
    def _cut(self, node: FibonacciNode[T], parent: FibonacciNode[T]) -> None:
        """Cut node from parent and add to root list."""
        # Remove node from parent's child list
        if node.right == node:
            parent.child = None
        else:
            node.left.right = node.right
            node.right.left = node.left
            if parent.child == node:
                parent.child = node.right
        
        parent.degree -= 1
        
        # Add to root list
        self._add_to_root_list(node)
        node.parent = None
        node.mark = False
    
    def _cascading_cut(self, node: FibonacciNode[T]) -> None:
        """Cascading cut operation."""
        parent = node.parent
        
        if parent is not None:
            if not node.mark:
                node.mark = True
            else:
                self._cut(node, parent)
                self._cascading_cut(parent)
    
    def _concatenate_lists(
        self,
        list1: FibonacciNode[T],
        list2: FibonacciNode[T]
    ) -> None:
        """Concatenate two circular doubly-linked lists."""
        list1_last = list1.left
        list2_last = list2.left
        
        list1_last.right = list2
        list2.left = list1_last
        list2_last.right = list1
        list1.left = list2_last
    
    def size(self) -> int:
        """Get the number of nodes in the heap."""
        return self.total_nodes
    
    def to_list(self) -> List[tuple[float, T]]:
        """
        Convert heap to a sorted list (for debugging).
        Note: This is destructive and empties the heap.
        
        Returns:
            List of (key, value) tuples in priority order
        """
        result = []
        while not self.is_empty():
            value = self.extract_min()
            if value is not None:
                result.append(value)
        return result


class WorkflowPriorityQueue:
    """
    Priority queue for workflow scheduling using Fibonacci heap.
    
    This class provides a high-level interface for scheduling workflows
    based on priority and resource constraints.
    """
    
    def __init__(self):
        """Initialize the workflow priority queue."""
        self.heap: FibonacciHeap[Dict[str, Any]] = FibonacciHeap()
        self.workflow_nodes: Dict[str, FibonacciNode[Dict[str, Any]]] = {}
    
    def add_workflow(
        self,
        workflow_id: str,
        priority: float,
        workflow_data: Dict[str, Any]
    ) -> None:
        """
        Add a workflow to the queue.
        
        Args:
            workflow_id: Unique identifier for the workflow
            priority: Priority value (lower is higher priority)
            workflow_data: Dictionary containing workflow information
        """
        workflow_data['workflow_id'] = workflow_id
        node = self.heap.insert(priority, workflow_data)
        self.workflow_nodes[workflow_id] = node
    
    def get_next_workflow(self) -> Optional[Dict[str, Any]]:
        """
        Get and remove the highest priority workflow.
        
        Returns:
            Workflow data dictionary, or None if queue is empty
        """
        workflow = self.heap.extract_min()
        if workflow and 'workflow_id' in workflow:
            workflow_id = workflow['workflow_id']
            if workflow_id in self.workflow_nodes:
                del self.workflow_nodes[workflow_id]
        return workflow
    
    def peek_next(self) -> Optional[Dict[str, Any]]:
        """
        Get the highest priority workflow without removing it.
        
        Returns:
            Workflow data dictionary, or None if queue is empty
        """
        return self.heap.find_min()
    
    def update_priority(self, workflow_id: str, new_priority: float) -> None:
        """
        Update the priority of a workflow in the queue.
        
        Args:
            workflow_id: ID of the workflow to update
            new_priority: New priority value (must be lower than current)
        """
        if workflow_id not in self.workflow_nodes:
            raise ValueError(f"Workflow {workflow_id} not found in queue")
        
        node = self.workflow_nodes[workflow_id]
        self.heap.decrease_key(node, new_priority)
    
    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return self.heap.is_empty()
    
    def size(self) -> int:
        """Get the number of workflows in the queue."""
        return self.heap.size()


if __name__ == "__main__":
    # Example usage
    print("Fibonacci Heap - Workflow Priority Queue Example")
    print("=" * 50)
    
    queue = WorkflowPriorityQueue()
    
    # Add workflows with different priorities
    queue.add_workflow("wf-001", priority=5.0, workflow_data={
        "name": "Data scraping",
        "resources": {"cpu": 2, "memory": "4GB"}
    })
    
    queue.add_workflow("wf-002", priority=1.0, workflow_data={
        "name": "Code generation",
        "resources": {"cpu": 4, "memory": "8GB"}
    })
    
    queue.add_workflow("wf-003", priority=3.0, workflow_data={
        "name": "Model training",
        "resources": {"cpu": 8, "memory": "16GB"}
    })
    
    print(f"Queue size: {queue.size()}")
    print(f"\nNext workflow: {queue.peek_next()}")
    
    # Process workflows in priority order
    print("\nProcessing workflows in priority order:")
    while not queue.is_empty():
        workflow = queue.get_next_workflow()
        if workflow:
            print(f"  - {workflow['name']} (Priority: {workflow.get('priority', 'N/A')})")
