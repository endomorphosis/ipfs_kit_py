#!/usr/bin/env python3
"""
P2P Workflow Coordinator

This module coordinates the execution of GitHub Actions workflows across a
peer-to-peer IPFS network, bypassing the GitHub API completely. It uses:

- Merkle Clock: For distributed consensus on task assignment
- Hamming Distance: To determine which peer handles each task
- Fibonacci Heap: For priority-based workflow scheduling

The coordinator handles workflows tagged for P2P execution, distributing them
across the network based on resource availability and peer distance.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .merkle_clock import MerkleClock, select_task_owner, create_task_hash
from .fibonacci_heap import WorkflowPriorityQueue

# Configure logger
logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Status of a workflow in the P2P network."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowTask:
    """Represents a workflow task to be executed."""
    workflow_id: str
    name: str
    workflow_file: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    priority: float = 5.0  # Default medium priority
    tags: Set[str] = field(default_factory=set)
    status: WorkflowStatus = WorkflowStatus.PENDING
    assigned_peer: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'workflow_id': self.workflow_id,
            'name': self.name,
            'workflow_file': self.workflow_file,
            'inputs': self.inputs,
            'priority': self.priority,
            'tags': list(self.tags),
            'status': self.status.value,
            'assigned_peer': self.assigned_peer,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'result': self.result,
            'error': self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowTask':
        """Create from dictionary representation."""
        return cls(
            workflow_id=data['workflow_id'],
            name=data['name'],
            workflow_file=data['workflow_file'],
            inputs=data.get('inputs', {}),
            priority=data.get('priority', 5.0),
            tags=set(data.get('tags', [])),
            status=WorkflowStatus(data.get('status', 'pending')),
            assigned_peer=data.get('assigned_peer'),
            created_at=data.get('created_at', time.time()),
            started_at=data.get('started_at'),
            completed_at=data.get('completed_at'),
            result=data.get('result'),
            error=data.get('error')
        )


class P2PWorkflowCoordinator:
    """
    Coordinates P2P workflow execution across IPFS network peers.
    
    This coordinator manages the lifecycle of workflows that are tagged
    for peer-to-peer execution, handling task assignment, prioritization,
    and result tracking without using the GitHub API.
    """
    
    P2P_TAG = "p2p-workflow"
    OFFLINE_TAG = "offline-workflow"
    
    def __init__(
        self,
        peer_id: str,
        data_dir: Optional[str] = None,
        enable_auto_sync: bool = True
    ):
        """
        Initialize the P2P workflow coordinator.
        
        Args:
            peer_id: Unique identifier for this peer
            data_dir: Directory for storing workflow state
            enable_auto_sync: Whether to automatically sync with other peers
        """
        self.peer_id = peer_id
        self.data_dir = Path(data_dir or os.path.expanduser("~/.ipfs_kit/p2p_workflows"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.enable_auto_sync = enable_auto_sync
        
        # Initialize merkle clock for consensus
        self.merkle_clock = MerkleClock(peer_id=peer_id)
        
        # Initialize priority queue for workflow scheduling
        self.workflow_queue = WorkflowPriorityQueue()
        
        # Track workflows
        self.workflows: Dict[str, WorkflowTask] = {}
        self.peer_list: List[str] = [peer_id]  # Start with just ourselves
        
        # Load state if exists
        self._load_state()
        
        logger.info(f"P2P Workflow Coordinator initialized for peer {peer_id}")
    
    def parse_workflow_file(self, workflow_path: Path) -> Dict[str, Any]:
        """
        Parse a GitHub Actions workflow file to extract metadata.
        
        Args:
            workflow_path: Path to the workflow YAML file
            
        Returns:
            Dictionary with workflow metadata
        """
        try:
            import yaml
            
            with open(workflow_path, 'r') as f:
                workflow_data = yaml.safe_load(f)
            
            # Extract P2P tags from workflow
            tags = set()
            
            # Check workflow-level labels/tags
            if 'labels' in workflow_data:
                tags.update(workflow_data['labels'])
            
            # Check for P2P marker in workflow name or jobs
            if self.P2P_TAG in str(workflow_data.get('name', '')).lower():
                tags.add(self.P2P_TAG)
            
            if self.OFFLINE_TAG in str(workflow_data.get('name', '')).lower():
                tags.add(self.OFFLINE_TAG)
            
            # Check jobs for P2P tags
            jobs = workflow_data.get('jobs', {})
            for job_name, job_data in jobs.items():
                if isinstance(job_data, dict):
                    if self.P2P_TAG in job_data.get('name', '').lower():
                        tags.add(self.P2P_TAG)
                    if 'labels' in job_data:
                        tags.update(job_data['labels'])
            
            return {
                'name': workflow_data.get('name', workflow_path.stem),
                'tags': tags,
                'jobs': list(jobs.keys()),
                'triggers': workflow_data.get('on', []),
                'raw': workflow_data
            }
        
        except Exception as e:
            logger.error(f"Failed to parse workflow file {workflow_path}: {e}")
            return {
                'name': workflow_path.stem,
                'tags': set(),
                'error': str(e)
            }
    
    def is_p2p_workflow(self, workflow_metadata: Dict[str, Any]) -> bool:
        """
        Check if a workflow should be executed via P2P network.
        
        Args:
            workflow_metadata: Metadata extracted from workflow file
            
        Returns:
            True if workflow is tagged for P2P execution
        """
        tags = workflow_metadata.get('tags', set())
        return self.P2P_TAG in tags or self.OFFLINE_TAG in tags
    
    def submit_workflow(
        self,
        workflow_file: str,
        name: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        priority: Optional[float] = None
    ) -> str:
        """
        Submit a workflow for P2P execution.
        
        Args:
            workflow_file: Path to workflow file or workflow content
            name: Optional workflow name
            inputs: Optional input parameters
            priority: Optional priority (lower = higher priority)
            
        Returns:
            Workflow ID
        """
        # Parse workflow if it's a file path
        workflow_path = Path(workflow_file)
        if workflow_path.exists():
            metadata = self.parse_workflow_file(workflow_path)
        else:
            metadata = {'name': name or 'unnamed', 'tags': set()}
        
        # Generate workflow ID
        workflow_id = hashlib.sha256(
            f"{self.peer_id}:{time.time()}:{workflow_file}".encode()
        ).hexdigest()[:16]
        
        # Create workflow task
        task = WorkflowTask(
            workflow_id=workflow_id,
            name=name or metadata.get('name', 'unnamed'),
            workflow_file=workflow_file,
            inputs=inputs or {},
            priority=priority or 5.0,
            tags=metadata.get('tags', set())
        )
        
        # Store workflow
        self.workflows[workflow_id] = task
        
        # Add to priority queue
        self.workflow_queue.add_workflow(
            workflow_id=workflow_id,
            priority=task.priority,
            workflow_data=task.to_dict()
        )
        
        # Record in merkle clock
        self.merkle_clock.append({
            'event': 'workflow_submitted',
            'workflow_id': workflow_id,
            'peer_id': self.peer_id,
            'timestamp': time.time()
        })
        
        self._save_state()
        
        logger.info(f"Workflow {workflow_id} submitted: {task.name}")
        return workflow_id
    
    def assign_workflows(self) -> List[str]:
        """
        Assign pending workflows to peers based on merkle clock consensus.
        
        Returns:
            List of workflow IDs that were assigned
        """
        assigned = []
        
        # Get merkle clock head
        head = self.merkle_clock.get_head()
        if head is None:
            logger.warning("No merkle clock head available for task assignment")
            return assigned
        
        # Process pending workflows
        for workflow_id, task in self.workflows.items():
            if task.status != WorkflowStatus.PENDING:
                continue
            
            # Create task hash
            task_hash = create_task_hash({
                'workflow_id': workflow_id,
                'name': task.name,
                'priority': task.priority
            })
            
            # Select peer based on hamming distance
            try:
                selected_peer, distance = select_task_owner(
                    merkle_clock_head=head.hash,
                    task_hash=task_hash,
                    peer_ids=self.peer_list
                )
                
                # Update task
                task.assigned_peer = selected_peer
                task.status = WorkflowStatus.ASSIGNED
                
                # Record in merkle clock
                self.merkle_clock.append({
                    'event': 'workflow_assigned',
                    'workflow_id': workflow_id,
                    'peer_id': selected_peer,
                    'hamming_distance': distance,
                    'timestamp': time.time()
                })
                
                assigned.append(workflow_id)
                
                logger.info(
                    f"Workflow {workflow_id} assigned to peer {selected_peer} "
                    f"(distance: {distance})"
                )
            
            except Exception as e:
                logger.error(f"Failed to assign workflow {workflow_id}: {e}")
        
        if assigned:
            self._save_state()
        
        return assigned
    
    def get_my_workflows(self) -> List[WorkflowTask]:
        """
        Get workflows assigned to this peer.
        
        Returns:
            List of workflow tasks assigned to this peer
        """
        return [
            task for task in self.workflows.values()
            if task.assigned_peer == self.peer_id
        ]
    
    def update_workflow_status(
        self,
        workflow_id: str,
        status: WorkflowStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Update the status of a workflow.
        
        Args:
            workflow_id: ID of the workflow
            status: New status
            result: Optional result data
            error: Optional error message
            
        Returns:
            True if updated successfully
        """
        if workflow_id not in self.workflows:
            logger.error(f"Workflow {workflow_id} not found")
            return False
        
        task = self.workflows[workflow_id]
        old_status = task.status
        task.status = status
        
        if status == WorkflowStatus.IN_PROGRESS and task.started_at is None:
            task.started_at = time.time()
        
        if status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED):
            task.completed_at = time.time()
            if result:
                task.result = result
            if error:
                task.error = error
        
        # Record in merkle clock
        self.merkle_clock.append({
            'event': 'workflow_status_changed',
            'workflow_id': workflow_id,
            'old_status': old_status.value,
            'new_status': status.value,
            'peer_id': self.peer_id,
            'timestamp': time.time()
        })
        
        self._save_state()
        
        logger.info(f"Workflow {workflow_id} status: {old_status.value} -> {status.value}")
        return True
    
    def add_peer(self, peer_id: str) -> None:
        """
        Add a peer to the network.
        
        Args:
            peer_id: Unique identifier of the peer to add
        """
        if peer_id not in self.peer_list:
            self.peer_list.append(peer_id)
            self.merkle_clock.append({
                'event': 'peer_added',
                'peer_id': peer_id,
                'timestamp': time.time()
            })
            self._save_state()
            logger.info(f"Peer {peer_id} added to network")
    
    def remove_peer(self, peer_id: str) -> None:
        """
        Remove a peer from the network.
        
        Args:
            peer_id: Unique identifier of the peer to remove
        """
        if peer_id in self.peer_list:
            self.peer_list.remove(peer_id)
            self.merkle_clock.append({
                'event': 'peer_removed',
                'peer_id': peer_id,
                'timestamp': time.time()
            })
            self._save_state()
            logger.info(f"Peer {peer_id} removed from network")
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a workflow.
        
        Args:
            workflow_id: ID of the workflow
            
        Returns:
            Dictionary with workflow status, or None if not found
        """
        if workflow_id not in self.workflows:
            return None
        
        return self.workflows[workflow_id].to_dict()
    
    def list_workflows(
        self,
        status: Optional[WorkflowStatus] = None,
        peer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List workflows with optional filtering.
        
        Args:
            status: Optional status filter
            peer_id: Optional peer ID filter
            
        Returns:
            List of workflow dictionaries
        """
        workflows = self.workflows.values()
        
        if status is not None:
            workflows = [w for w in workflows if w.status == status]
        
        if peer_id is not None:
            workflows = [w for w in workflows if w.assigned_peer == peer_id]
        
        return [w.to_dict() for w in workflows]
    
    def _save_state(self) -> None:
        """Save coordinator state to disk."""
        try:
            state = {
                'peer_id': self.peer_id,
                'peer_list': self.peer_list,
                'merkle_clock': self.merkle_clock.to_dict(),
                'workflows': {wid: w.to_dict() for wid, w in self.workflows.items()},
                'saved_at': time.time()
            }
            
            state_file = self.data_dir / f"coordinator_state_{self.peer_id}.json"
            temp_file = state_file.with_suffix('.tmp')
            
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            temp_file.replace(state_file)
            
        except Exception as e:
            logger.error(f"Failed to save coordinator state: {e}")
    
    def _load_state(self) -> None:
        """Load coordinator state from disk."""
        try:
            state_file = self.data_dir / f"coordinator_state_{self.peer_id}.json"
            
            if not state_file.exists():
                return
            
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            self.peer_list = state.get('peer_list', [self.peer_id])
            self.merkle_clock = MerkleClock.from_dict(state.get('merkle_clock', {}))
            
            # Restore workflows
            for wid, wdata in state.get('workflows', {}).items():
                self.workflows[wid] = WorkflowTask.from_dict(wdata)
                
                # Re-add to queue if pending
                if self.workflows[wid].status == WorkflowStatus.PENDING:
                    self.workflow_queue.add_workflow(
                        workflow_id=wid,
                        priority=self.workflows[wid].priority,
                        workflow_data=wdata
                    )
            
            logger.info(f"Loaded state with {len(self.workflows)} workflows")
            
        except Exception as e:
            logger.error(f"Failed to load coordinator state: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get coordinator statistics.
        
        Returns:
            Dictionary with coordinator stats
        """
        status_counts = {}
        for task in self.workflows.values():
            status = task.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'peer_id': self.peer_id,
            'total_workflows': len(self.workflows),
            'queue_size': self.workflow_queue.size(),
            'peer_count': len(self.peer_list),
            'merkle_clock_height': self.merkle_clock.logical_clock,
            'status_counts': status_counts,
            'my_workflows': len(self.get_my_workflows())
        }


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    print("P2P Workflow Coordinator Example")
    print("=" * 50)
    
    # Create coordinator for this peer
    coordinator = P2PWorkflowCoordinator(peer_id="peer-alpha")
    
    # Add some peers to the network
    coordinator.add_peer("peer-beta")
    coordinator.add_peer("peer-gamma")
    
    # Submit workflows
    wf1 = coordinator.submit_workflow(
        workflow_file="scrape_website.yml",
        name="Scrape E-commerce Site",
        priority=3.0
    )
    
    wf2 = coordinator.submit_workflow(
        workflow_file="generate_code.yml",
        name="Generate API Client",
        priority=1.0
    )
    
    wf3 = coordinator.submit_workflow(
        workflow_file="process_data.yml",
        name="Process Dataset",
        priority=2.0
    )
    
    # Assign workflows to peers
    assigned = coordinator.assign_workflows()
    print(f"\nAssigned {len(assigned)} workflows")
    
    # Show statistics
    stats = coordinator.get_stats()
    print(f"\nCoordinator Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Show workflows assigned to this peer
    my_workflows = coordinator.get_my_workflows()
    print(f"\nMy workflows ({len(my_workflows)}):")
    for task in my_workflows:
        print(f"  - {task.name} (ID: {task.workflow_id})")
