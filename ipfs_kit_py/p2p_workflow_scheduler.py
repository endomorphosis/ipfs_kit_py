"""
P2P Workflow Scheduler for IPFS Kit

This module provides a peer-to-peer workflow scheduling system that allows
workflows to bypass the GitHub API by distributing task execution across
P2P network nodes using a merkle clock for task assignment and fibonacci
heap for priority scheduling.

Key Features:
- Merkle clock for distributed consensus on task ownership
- Fibonacci heap for efficient priority-based task scheduling
- Hamming distance calculation for peer selection
- Workflow tagging for P2P-eligible workflows
- Integration with existing workflow management systems
"""

import hashlib
import heapq
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class WorkflowTag(Enum):
    """Tags for workflow execution mode"""
    GITHUB_API = "github-api"  # Standard GitHub API workflows
    P2P_ELIGIBLE = "p2p-eligible"  # Can be executed via P2P network
    P2P_ONLY = "p2p-only"  # Must be executed via P2P network (bypasses GitHub)
    UNIT_TEST = "unit-test"  # Unit test workflows (GitHub API)
    CODE_GENERATION = "code-generation"  # Code generation tasks (P2P-eligible)
    WEB_SCRAPING = "web-scraping"  # Web scraping tasks (P2P-eligible)
    DATA_PROCESSING = "data-processing"  # Data processing tasks (P2P-eligible)


@dataclass
class MerkleClock:
    """
    Merkle clock for distributed consensus in P2P network.
    
    Uses a vector clock combined with merkle tree hashing to determine
    the canonical state of the distributed system at any point in time.
    """
    node_id: str
    vector: Dict[str, int] = field(default_factory=dict)
    merkle_root: Optional[str] = None
    
    def __post_init__(self):
        if self.node_id not in self.vector:
            self.vector[self.node_id] = 0
    
    def tick(self) -> None:
        """Increment this node's clock"""
        self.vector[self.node_id] = self.vector.get(self.node_id, 0) + 1
        self._update_merkle_root()
    
    def update(self, other: 'MerkleClock') -> None:
        """Update clock by merging with another clock (Lamport-style)"""
        for node_id, timestamp in other.vector.items():
            self.vector[node_id] = max(self.vector.get(node_id, 0), timestamp)
        self.tick()
    
    def _update_merkle_root(self) -> None:
        """Calculate merkle root from vector clock state"""
        # Sort vector clock entries for deterministic hashing
        sorted_entries = sorted(self.vector.items())
        clock_data = json.dumps(sorted_entries, sort_keys=True)
        self.merkle_root = hashlib.sha256(clock_data.encode()).hexdigest()
    
    def get_hash(self) -> str:
        """Get the merkle clock head hash"""
        if self.merkle_root is None:
            self._update_merkle_root()
        return self.merkle_root
    
    def compare(self, other: 'MerkleClock') -> int:
        """
        Compare two merkle clocks.
        
        Returns:
            -1 if self < other (self happened before)
            0 if concurrent (no causal relationship)
            1 if self > other (self happened after)
        """
        self_before = True
        other_before = True
        
        all_nodes = set(self.vector.keys()) | set(other.vector.keys())
        
        for node in all_nodes:
            self_ts = self.vector.get(node, 0)
            other_ts = other.vector.get(node, 0)
            
            if self_ts > other_ts:
                other_before = False
            elif self_ts < other_ts:
                self_before = False
        
        if self_before and not other_before:
            return -1
        elif not self_before and other_before:
            return 1
        else:
            return 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'node_id': self.node_id,
            'vector': self.vector,
            'merkle_root': self.get_hash()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MerkleClock':
        """Deserialize from dictionary"""
        clock = cls(node_id=data['node_id'], vector=data.get('vector', {}))
        clock.merkle_root = data.get('merkle_root')
        return clock


class FibonacciHeapNode:
    """Node in a Fibonacci heap for efficient priority queue operations"""
    
    def __init__(self, key: int, data: Any):
        self.key = key
        self.data = data
        self.degree = 0
        self.mark = False
        self.parent = None
        self.child = None
        self.left = self
        self.right = self


class FibonacciHeap:
    """
    Fibonacci heap implementation for O(1) insert and amortized O(log n) delete-min.
    
    Used for efficient priority-based workflow scheduling where we frequently
    insert new tasks and extract the highest priority task.
    """
    
    def __init__(self):
        self.min_node = None
        self.total_nodes = 0
    
    def is_empty(self) -> bool:
        """Check if heap is empty"""
        return self.min_node is None
    
    def insert(self, key: int, data: Any) -> FibonacciHeapNode:
        """
        Insert a new node with given priority key and data.
        
        Args:
            key: Priority key (lower = higher priority)
            data: Associated data (workflow task)
        
        Returns:
            The inserted node
        """
        node = FibonacciHeapNode(key, data)
        
        if self.min_node is None:
            self.min_node = node
        else:
            # Add to root list
            node.left = self.min_node
            node.right = self.min_node.right
            self.min_node.right.left = node
            self.min_node.right = node
            
            if node.key < self.min_node.key:
                self.min_node = node
        
        self.total_nodes += 1
        return node
    
    def get_min(self) -> Optional[Tuple[int, Any]]:
        """
        Get the minimum element without removing it.
        
        Returns:
            Tuple of (key, data) or None if empty
        """
        if self.min_node is None:
            return None
        return (self.min_node.key, self.min_node.data)
    
    def extract_min(self) -> Optional[Tuple[int, Any]]:
        """
        Extract and return the minimum element.
        
        Returns:
            Tuple of (key, data) or None if empty
        """
        min_node = self.min_node
        
        if min_node is None:
            return None
        
        # Add all children to root list
        if min_node.child is not None:
            children = []
            child = min_node.child
            while True:
                children.append(child)
                child = child.right
                if child == min_node.child:
                    break
            
            for child in children:
                # Remove from child list
                child.left.right = child.right
                child.right.left = child.left
                
                # Add to root list
                child.left = self.min_node
                child.right = self.min_node.right
                self.min_node.right.left = child
                self.min_node.right = child
                child.parent = None
        
        # Remove min_node from root list
        min_node.left.right = min_node.right
        min_node.right.left = min_node.left
        
        if min_node == min_node.right:
            self.min_node = None
        else:
            self.min_node = min_node.right
            self._consolidate()
        
        self.total_nodes -= 1
        return (min_node.key, min_node.data)
    
    def _consolidate(self) -> None:
        """Consolidate trees to maintain heap properties"""
        if self.min_node is None:
            return
        
        # Calculate max degree
        max_degree = int(self.total_nodes ** 0.5) + 1
        degree_table = [None] * (max_degree + 1)
        
        # Collect all root nodes
        roots = []
        root = self.min_node
        if root is not None:
            while True:
                roots.append(root)
                root = root.right
                if root == self.min_node:
                    break
        
        # Consolidate
        for root in roots:
            degree = root.degree
            while degree_table[degree] is not None:
                other = degree_table[degree]
                if root.key > other.key:
                    root, other = other, root
                
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
                    node.left = self.min_node
                    node.right = self.min_node.right
                    self.min_node.right.left = node
                    self.min_node.right = node
                    
                    if node.key < self.min_node.key:
                        self.min_node = node
    
    def _link(self, child: FibonacciHeapNode, parent: FibonacciHeapNode) -> None:
        """Link child node under parent node"""
        # Remove child from root list
        child.left.right = child.right
        child.right.left = child.left
        
        # Add child to parent's child list
        if parent.child is None:
            parent.child = child
            child.left = child
            child.right = child
        else:
            child.left = parent.child
            child.right = parent.child.right
            parent.child.right.left = child
            parent.child.right = child
        
        child.parent = parent
        parent.degree += 1
        child.mark = False
    
    def size(self) -> int:
        """Get the number of nodes in the heap"""
        return self.total_nodes


def calculate_hamming_distance(hash1: str, hash2: str) -> int:
    """
    Calculate Hamming distance between two hex hash strings.
    
    Used to determine which peer should handle a task based on the
    distance between their peer ID hash and the task hash.
    
    Args:
        hash1: First hash (hex string)
        hash2: Second hash (hex string)
    
    Returns:
        Hamming distance (number of differing bits)
    """
    # Convert hex to binary
    bin1 = bin(int(hash1, 16))[2:].zfill(len(hash1) * 4)
    bin2 = bin(int(hash2, 16))[2:].zfill(len(hash2) * 4)
    
    # Count differing bits
    return sum(b1 != b2 for b1, b2 in zip(bin1, bin2))


@dataclass
class P2PTask:
    """A task to be scheduled in the P2P network"""
    task_id: str
    workflow_id: str
    name: str
    tags: List[WorkflowTag]
    priority: int  # 1-10, higher = more important
    created_at: float
    task_hash: str = ""
    assigned_peer: Optional[str] = None
    
    def __post_init__(self):
        if not self.task_hash:
            # Generate task hash from task_id and workflow_id
            task_data = f"{self.task_id}:{self.workflow_id}".encode()
            self.task_hash = hashlib.sha256(task_data).hexdigest()
    
    def __lt__(self, other):
        """For priority comparison in heap (higher priority = lower key)"""
        # Invert priority so higher priority comes first
        # Add creation time as tiebreaker
        return (10 - self.priority, self.created_at) < (10 - other.priority, other.created_at)


class P2PWorkflowScheduler:
    """
    Main P2P workflow scheduler that coordinates task distribution
    across the peer-to-peer network.
    """
    
    def __init__(self, peer_id: str, bootstrap_peers: Optional[List[str]] = None):
        """
        Initialize P2P workflow scheduler.
        
        Args:
            peer_id: This node's peer ID
            bootstrap_peers: List of known peer IDs for initial connectivity
        """
        self.peer_id = peer_id
        self.peer_id_hash = hashlib.sha256(peer_id.encode()).hexdigest()
        
        # Merkle clock for distributed consensus
        self.merkle_clock = MerkleClock(node_id=peer_id)
        
        # Fibonacci heap for priority scheduling
        self.task_queue = FibonacciHeap()
        
        # Track known peers and their states
        self.known_peers: Dict[str, Dict[str, Any]] = {}
        if bootstrap_peers:
            for peer in bootstrap_peers:
                self.known_peers[peer] = {
                    'peer_id': peer,
                    'peer_id_hash': hashlib.sha256(peer.encode()).hexdigest(),
                    'last_seen': time.time(),
                    'clock': None
                }
        
        # Track tasks
        self.pending_tasks: Dict[str, P2PTask] = {}
        self.assigned_tasks: Dict[str, P2PTask] = {}
        self.completed_tasks: Dict[str, P2PTask] = {}
        
        logger.info(f"P2P Workflow Scheduler initialized for peer {peer_id}")
    
    def should_bypass_github(self, tags: List[WorkflowTag]) -> bool:
        """
        Determine if a workflow should bypass GitHub API based on tags.
        
        Args:
            tags: List of workflow tags
        
        Returns:
            True if workflow should bypass GitHub API
        """
        return (WorkflowTag.P2P_ONLY in tags or 
                WorkflowTag.P2P_ELIGIBLE in tags)
    
    def is_p2p_only(self, tags: List[WorkflowTag]) -> bool:
        """Check if workflow must use P2P (cannot use GitHub API)"""
        return WorkflowTag.P2P_ONLY in tags
    
    def submit_task(self, task: P2PTask) -> bool:
        """
        Submit a task to the P2P scheduler.
        
        Args:
            task: Task to schedule
        
        Returns:
            True if task was accepted
        """
        if task.task_id in self.pending_tasks or task.task_id in self.assigned_tasks:
            logger.warning(f"Task {task.task_id} already exists")
            return False
        
        # Add to pending tasks
        self.pending_tasks[task.task_id] = task
        
        # Add to priority queue (use inverted priority for min-heap)
        priority_key = 10 - task.priority
        self.task_queue.insert(priority_key, task)
        
        # Update merkle clock
        self.merkle_clock.tick()
        
        logger.info(f"Task {task.task_id} submitted with priority {task.priority}")
        return True
    
    def determine_task_owner(self, task: P2PTask) -> str:
        """
        Determine which peer should handle a task based on hamming distance.
        
        Uses the merkle clock head hash + task hash compared to peer ID hashes
        to deterministically select the responsible peer.
        
        Args:
            task: Task to assign
        
        Returns:
            Peer ID of the responsible peer
        """
        # Combine merkle clock head with task hash
        clock_hash = self.merkle_clock.get_hash()
        combined = hashlib.sha256(f"{clock_hash}:{task.task_hash}".encode()).hexdigest()
        
        # Calculate hamming distance to all known peers (including self)
        all_peers = {self.peer_id: self.peer_id_hash}
        all_peers.update({pid: info['peer_id_hash'] for pid, info in self.known_peers.items()})
        
        min_distance = float('inf')
        selected_peer = self.peer_id
        
        for peer_id, peer_hash in all_peers.items():
            distance = calculate_hamming_distance(combined, peer_hash)
            if distance < min_distance:
                min_distance = distance
                selected_peer = peer_id
        
        logger.debug(f"Task {task.task_id} assigned to peer {selected_peer} (distance: {min_distance})")
        return selected_peer
    
    def check_peer_failure(self, peer_id: str, timeout_seconds: int = 300) -> bool:
        """
        Check if a peer has failed to respond (for task reassignment).
        
        Args:
            peer_id: Peer to check
            timeout_seconds: How long before considering peer failed
        
        Returns:
            True if peer appears to have failed
        """
        if peer_id not in self.known_peers:
            return True
        
        peer_info = self.known_peers[peer_id]
        time_since_seen = time.time() - peer_info.get('last_seen', 0)
        
        return time_since_seen > timeout_seconds
    
    def get_next_task(self) -> Optional[P2PTask]:
        """
        Get the next task that should be executed by this peer.
        
        Returns:
            Next task to execute, or None if no tasks available
        """
        while not self.task_queue.is_empty():
            priority_key, task = self.task_queue.extract_min()
            
            if task.task_id not in self.pending_tasks:
                # Task was already processed
                continue
            
            # Determine if this peer should handle the task
            assigned_peer = self.determine_task_owner(task)
            task.assigned_peer = assigned_peer
            
            if assigned_peer == self.peer_id:
                # This peer should handle the task
                self.pending_tasks.pop(task.task_id)
                self.assigned_tasks[task.task_id] = task
                return task
            elif self.check_peer_failure(assigned_peer):
                # Assigned peer has failed, we'll take the task
                logger.warning(f"Peer {assigned_peer} failed, taking task {task.task_id}")
                self.pending_tasks.pop(task.task_id)
                self.assigned_tasks[task.task_id] = task
                return task
            else:
                # Task is for another peer
                logger.debug(f"Task {task.task_id} assigned to peer {assigned_peer}")
                self.pending_tasks.pop(task.task_id)
                continue
        
        return None
    
    def mark_task_complete(self, task_id: str) -> bool:
        """
        Mark a task as completed.
        
        Args:
            task_id: Task to mark complete
        
        Returns:
            True if task was found and marked complete
        """
        if task_id in self.assigned_tasks:
            task = self.assigned_tasks.pop(task_id)
            self.completed_tasks[task_id] = task
            self.merkle_clock.tick()
            logger.info(f"Task {task_id} marked complete")
            return True
        
        logger.warning(f"Task {task_id} not found in assigned tasks")
        return False
    
    def update_peer_state(self, peer_id: str, clock: MerkleClock) -> None:
        """
        Update state information for a peer.
        
        Args:
            peer_id: Peer to update
            clock: Peer's merkle clock
        """
        if peer_id not in self.known_peers:
            self.known_peers[peer_id] = {
                'peer_id': peer_id,
                'peer_id_hash': hashlib.sha256(peer_id.encode()).hexdigest(),
                'last_seen': time.time(),
                'clock': clock
            }
        else:
            self.known_peers[peer_id]['last_seen'] = time.time()
            self.known_peers[peer_id]['clock'] = clock
        
        # Update our merkle clock
        self.merkle_clock.update(clock)
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status information"""
        return {
            'peer_id': self.peer_id,
            'merkle_clock': self.merkle_clock.to_dict(),
            'pending_tasks': len(self.pending_tasks),
            'assigned_tasks': len(self.assigned_tasks),
            'completed_tasks': len(self.completed_tasks),
            'queue_size': self.task_queue.size(),
            'known_peers': len(self.known_peers)
        }
