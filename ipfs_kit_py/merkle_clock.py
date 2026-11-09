#!/usr/bin/env python3
"""
Merkle Clock Implementation for Distributed Task Coordination

This module implements a Merkle clock data structure for maintaining distributed,
tamper-resistant logs in a peer-to-peer environment. It combines Merkle Trees for
cryptographic consistency with logical clock mechanisms for causal ordering.

The implementation is designed to work with the IPFS ecosystem and peer-to-peer
workflow distribution system.
"""

import hashlib
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MerkleClockNode:
    """Represents a node in the Merkle clock tree."""
    timestamp: float
    peer_id: str
    data: Dict[str, Any]
    parent_hash: Optional[str] = None
    hash: Optional[str] = None
    logical_clock: int = 0
    
    def __post_init__(self):
        """Calculate hash after initialization if not provided."""
        if self.hash is None:
            self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """Calculate the hash of this node using SHA-256."""
        content = {
            'timestamp': self.timestamp,
            'peer_id': self.peer_id,
            'data': self.data,
            'parent_hash': self.parent_hash,
            'logical_clock': self.logical_clock
        }
        json_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary representation."""
        return {
            'timestamp': self.timestamp,
            'peer_id': self.peer_id,
            'data': self.data,
            'parent_hash': self.parent_hash,
            'hash': self.hash,
            'logical_clock': self.logical_clock
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MerkleClockNode':
        """Create node from dictionary representation."""
        return cls(
            timestamp=data['timestamp'],
            peer_id=data['peer_id'],
            data=data['data'],
            parent_hash=data.get('parent_hash'),
            hash=data.get('hash'),
            logical_clock=data.get('logical_clock', 0)
        )


class MerkleClock:
    """
    Merkle Clock for distributed consensus and task coordination.
    
    The Merkle clock maintains a cryptographically verifiable history of events
    in a distributed system, enabling peers to agree on task assignments and
    track workflow execution.
    """
    
    def __init__(self, peer_id: str):
        """
        Initialize a new Merkle clock.
        
        Args:
            peer_id: Unique identifier for this peer
        """
        self.peer_id = peer_id
        self.nodes: List[MerkleClockNode] = []
        self.head_hash: Optional[str] = None
        self.logical_clock: int = 0
    
    def append(self, data: Dict[str, Any]) -> MerkleClockNode:
        """
        Append a new event to the clock.
        
        Args:
            data: Event data to append
            
        Returns:
            The newly created node
        """
        self.logical_clock += 1
        
        node = MerkleClockNode(
            timestamp=time.time(),
            peer_id=self.peer_id,
            data=data,
            parent_hash=self.head_hash,
            logical_clock=self.logical_clock
        )
        
        self.nodes.append(node)
        self.head_hash = node.hash
        
        return node
    
    def get_head(self) -> Optional[MerkleClockNode]:
        """Get the most recent node in the clock."""
        return self.nodes[-1] if self.nodes else None
    
    def verify_chain(self) -> bool:
        """
        Verify the integrity of the entire chain.
        
        Returns:
            True if the chain is valid, False otherwise
        """
        if not self.nodes:
            return True
        
        for i, node in enumerate(self.nodes):
            # Verify hash
            if node.hash != node.calculate_hash():
                return False
            
            # Verify parent link
            if i > 0:
                expected_parent = self.nodes[i - 1].hash
                if node.parent_hash != expected_parent:
                    return False
        
        return True
    
    def merge(self, other: 'MerkleClock') -> None:
        """
        Merge another clock into this one (simple append strategy).
        
        Args:
            other: Another MerkleClock to merge
        """
        for node in other.nodes:
            # Only add nodes we don't have
            if not any(n.hash == node.hash for n in self.nodes):
                self.nodes.append(node)
                if node.logical_clock > self.logical_clock:
                    self.logical_clock = node.logical_clock
        
        # Update head to latest node
        if self.nodes:
            self.nodes.sort(key=lambda n: (n.logical_clock, n.timestamp))
            self.head_hash = self.nodes[-1].hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert clock to dictionary representation."""
        return {
            'peer_id': self.peer_id,
            'head_hash': self.head_hash,
            'logical_clock': self.logical_clock,
            'nodes': [node.to_dict() for node in self.nodes]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MerkleClock':
        """Create clock from dictionary representation."""
        clock = cls(peer_id=data['peer_id'])
        clock.head_hash = data.get('head_hash')
        clock.logical_clock = data.get('logical_clock', 0)
        clock.nodes = [MerkleClockNode.from_dict(n) for n in data.get('nodes', [])]
        return clock


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Calculate the Hamming distance between two hash strings.
    
    The Hamming distance is the number of positions at which the corresponding
    characters are different.
    
    Args:
        hash1: First hash string
        hash2: Second hash string
        
    Returns:
        Hamming distance as an integer
    """
    if len(hash1) != len(hash2):
        # If lengths differ, pad the shorter one
        max_len = max(len(hash1), len(hash2))
        hash1 = hash1.ljust(max_len, '0')
        hash2 = hash2.ljust(max_len, '0')
    
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))


def select_task_owner(
    merkle_clock_head: str,
    task_hash: str,
    peer_ids: List[str]
) -> Tuple[str, int]:
    """
    Select which peer should handle a task based on Hamming distance.
    
    This function uses the merkle clock head hash, task hash, and peer IDs
    to deterministically select which peer should execute a given task.
    
    Args:
        merkle_clock_head: Current head hash of the merkle clock
        task_hash: Hash of the task to be assigned
        peer_ids: List of available peer IDs
        
    Returns:
        Tuple of (selected_peer_id, hamming_distance)
    """
    if not peer_ids:
        raise ValueError("No peers available for task assignment")
    
    # Combine merkle clock head and task hash
    combined = hashlib.sha256(
        f"{merkle_clock_head}:{task_hash}".encode()
    ).hexdigest()
    
    # Find peer with minimum Hamming distance
    min_distance = float('inf')
    selected_peer = None
    
    for peer_id in peer_ids:
        peer_hash = hashlib.sha256(peer_id.encode()).hexdigest()
        distance = hamming_distance(combined, peer_hash)
        
        if distance < min_distance:
            min_distance = distance
            selected_peer = peer_id
    
    return selected_peer, min_distance


def create_task_hash(workflow_data: Dict[str, Any]) -> str:
    """
    Create a deterministic hash for a workflow task.
    
    Args:
        workflow_data: Dictionary containing workflow information
        
    Returns:
        SHA-256 hash of the workflow data
    """
    json_str = json.dumps(workflow_data, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()


if __name__ == "__main__":
    # Example usage
    print("Merkle Clock Example")
    print("=" * 50)
    
    # Create a clock
    clock = MerkleClock(peer_id="peer-1")
    
    # Add some events
    clock.append({"type": "workflow_start", "workflow_id": "wf-001"})
    clock.append({"type": "task_assigned", "task_id": "task-001"})
    clock.append({"type": "task_completed", "task_id": "task-001"})
    
    print(f"Clock head: {clock.head_hash}")
    print(f"Logical clock: {clock.logical_clock}")
    print(f"Chain valid: {clock.verify_chain()}")
    
    # Task assignment example
    peers = ["peer-1", "peer-2", "peer-3"]
    task_data = {"workflow": "test-workflow", "action": "scrape"}
    task_hash = create_task_hash(task_data)
    
    selected_peer, distance = select_task_owner(
        clock.head_hash,
        task_hash,
        peers
    )
    
    print(f"\nTask assigned to: {selected_peer}")
    print(f"Hamming distance: {distance}")
