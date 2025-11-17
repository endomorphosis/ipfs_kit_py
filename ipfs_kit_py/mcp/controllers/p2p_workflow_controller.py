"""
P2P Workflow Controller Module

This module provides the P2P Workflow Controller functionality for the MCP server.
Exposes P2P workflow scheduling operations as MCP tools.
"""

import logging
import time
import uuid
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Try to import the P2P workflow scheduler
try:
    from ...p2p_workflow_scheduler import (
        P2PWorkflowScheduler,
        P2PTask,
        WorkflowTag,
        MerkleClock
    )
    P2P_SCHEDULER_AVAILABLE = True
except ImportError:
    P2P_SCHEDULER_AVAILABLE = False
    logger.warning("P2P workflow scheduler not available")


class P2PWorkflowController:
    """Controller for P2P workflow scheduling operations."""
    
    def __init__(self, peer_id: Optional[str] = None, bootstrap_peers: Optional[List[str]] = None):
        """
        Initialize P2P Workflow Controller.
        
        Args:
            peer_id: This node's peer ID (will be auto-generated if not provided)
            bootstrap_peers: List of known peer IDs for initial connectivity
        """
        self.logger = logging.getLogger(__name__)
        
        if not P2P_SCHEDULER_AVAILABLE:
            self.logger.error("P2P workflow scheduler not available")
            self.scheduler = None
            return
        
        # Generate peer ID if not provided
        if peer_id is None:
            import socket
            peer_id = f"peer-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        
        self.scheduler = P2PWorkflowScheduler(
            peer_id=peer_id,
            bootstrap_peers=bootstrap_peers
        )
        self.logger.info(f"P2P Workflow Controller initialized with peer_id: {peer_id}")
    
    def get_status(self, request: Optional[Any] = None) -> Dict[str, Any]:
        """
        Get P2P workflow scheduler status.
        
        Returns:
            Scheduler status including queue size, peer count, and task counts
        """
        self.logger.info("Getting P2P scheduler status")
        
        if not P2P_SCHEDULER_AVAILABLE or self.scheduler is None:
            return {
                "success": False,
                "message": "P2P scheduler not available",
                "timestamp": time.time()
            }
        
        try:
            status = self.scheduler.get_status()
            status["success"] = True
            status["message"] = "Status retrieved successfully"
            status["timestamp"] = time.time()
            return status
        except Exception as e:
            self.logger.error(f"Error getting P2P scheduler status: {e}")
            return {
                "success": False,
                "message": f"Error getting status: {str(e)}",
                "timestamp": time.time()
            }
    
    def submit_task(self, request) -> Dict[str, Any]:
        """
        Submit a task to the P2P workflow scheduler.
        
        Args:
            request: Request object with fields:
                - task_id: Unique task identifier
                - workflow_id: Workflow this task belongs to
                - name: Human-readable task name
                - tags: List of tags (e.g., "p2p-only", "code-generation")
                - priority: Task priority (1-10, default 5)
        
        Returns:
            Submission status and task details
        """
        if not P2P_SCHEDULER_AVAILABLE or self.scheduler is None:
            return {
                "success": False,
                "message": "P2P scheduler not available",
                "timestamp": time.time()
            }
        
        try:
            task_id = request.task_id
            workflow_id = request.workflow_id
            name = request.name
            tags = request.tags if hasattr(request, 'tags') else []
            priority = request.priority if hasattr(request, 'priority') else 5
            
            self.logger.info(f"Submitting task {task_id} to P2P scheduler")
            
            # Convert string tags to WorkflowTag enums
            workflow_tags = []
            for tag_str in tags:
                try:
                    enum_name = tag_str.upper().replace('-', '_')
                    workflow_tags.append(WorkflowTag[enum_name])
                except (KeyError, AttributeError):
                    self.logger.warning(f"Unknown tag: {tag_str}, skipping")
            
            # Create task
            task = P2PTask(
                task_id=task_id,
                workflow_id=workflow_id,
                name=name,
                tags=workflow_tags,
                priority=priority,
                created_at=time.time()
            )
            
            # Submit task
            success = self.scheduler.submit_task(task)
            
            return {
                "success": success,
                "message": f"Task {task_id} submitted successfully" if success else f"Failed to submit task {task_id}",
                "task_id": task_id,
                "task_hash": task.task_hash,
                "priority": priority,
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"Error submitting task: {e}")
            return {
                "success": False,
                "message": f"Error submitting task: {str(e)}",
                "timestamp": time.time()
            }
    
    def get_next_task(self, request: Optional[Any] = None) -> Dict[str, Any]:
        """
        Get the next task to execute from the P2P scheduler.
        
        Uses merkle clock + hamming distance to determine if this peer should handle the task.
        
        Returns:
            Next task details or None if no tasks available
        """
        if not P2P_SCHEDULER_AVAILABLE or self.scheduler is None:
            return {
                "success": False,
                "message": "P2P scheduler not available",
                "timestamp": time.time()
            }
        
        try:
            self.logger.info("Getting next task from P2P scheduler")
            task = self.scheduler.get_next_task()
            
            if task is None:
                return {
                    "success": True,
                    "message": "No tasks available for this peer",
                    "task": None,
                    "timestamp": time.time()
                }
            
            return {
                "success": True,
                "message": f"Retrieved task {task.task_id}",
                "task": {
                    "task_id": task.task_id,
                    "workflow_id": task.workflow_id,
                    "name": task.name,
                    "tags": [tag.value for tag in task.tags],
                    "priority": task.priority,
                    "task_hash": task.task_hash,
                    "assigned_peer": task.assigned_peer
                },
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting next task: {e}")
            return {
                "success": False,
                "message": f"Error getting next task: {str(e)}",
                "timestamp": time.time()
            }
    
    def mark_task_complete(self, request) -> Dict[str, Any]:
        """
        Mark a task as completed in the P2P scheduler.
        
        Args:
            request: Request object with fields:
                - task_id: Task identifier
        
        Returns:
            Completion status
        """
        if not P2P_SCHEDULER_AVAILABLE or self.scheduler is None:
            return {
                "success": False,
                "message": "P2P scheduler not available",
                "timestamp": time.time()
            }
        
        try:
            task_id = request.task_id
            self.logger.info(f"Marking task {task_id} as complete")
            
            success = self.scheduler.mark_task_complete(task_id)
            
            return {
                "success": success,
                "message": f"Task {task_id} marked complete" if success else f"Task {task_id} not found",
                "task_id": task_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"Error marking task complete: {e}")
            return {
                "success": False,
                "message": f"Error marking task complete: {str(e)}",
                "timestamp": time.time()
            }
    
    def check_workflow_tags(self, request) -> Dict[str, Any]:
        """
        Check if a workflow should bypass GitHub API based on tags.
        
        Args:
            request: Request object with fields:
                - tags: List of workflow tags
        
        Returns:
            Information about whether workflow should use P2P
        """
        if not P2P_SCHEDULER_AVAILABLE or self.scheduler is None:
            return {
                "success": False,
                "message": "P2P scheduler not available",
                "timestamp": time.time()
            }
        
        try:
            tags = request.tags if hasattr(request, 'tags') else []
            
            # Convert string tags to WorkflowTag enums
            workflow_tags = []
            for tag_str in tags:
                try:
                    enum_name = tag_str.upper().replace('-', '_')
                    workflow_tags.append(WorkflowTag[enum_name])
                except (KeyError, AttributeError):
                    pass
            
            should_bypass = self.scheduler.should_bypass_github(workflow_tags)
            is_p2p_only = self.scheduler.is_p2p_only(workflow_tags)
            
            return {
                "success": True,
                "should_bypass_github": should_bypass,
                "is_p2p_only": is_p2p_only,
                "tags": tags,
                "message": "Tags checked successfully",
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"Error checking workflow tags: {e}")
            return {
                "success": False,
                "message": f"Error checking tags: {str(e)}",
                "timestamp": time.time()
            }
    
    def update_peer_state(self, request) -> Dict[str, Any]:
        """
        Update state information for a peer in the network.
        
        Args:
            request: Request object with fields:
                - peer_id: Peer identifier
                - clock_data: Merkle clock data from peer
        
        Returns:
            Update status
        """
        if not P2P_SCHEDULER_AVAILABLE or self.scheduler is None:
            return {
                "success": False,
                "message": "P2P scheduler not available",
                "timestamp": time.time()
            }
        
        try:
            peer_id = request.peer_id
            clock_data = request.clock_data
            
            # Reconstruct merkle clock from data
            clock = MerkleClock.from_dict(clock_data)
            
            # Update peer state
            self.scheduler.update_peer_state(peer_id, clock)
            
            return {
                "success": True,
                "message": f"Peer {peer_id} state updated",
                "peer_id": peer_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"Error updating peer state: {e}")
            return {
                "success": False,
                "message": f"Error updating peer state: {str(e)}",
                "timestamp": time.time()
            }
    
    def get_merkle_clock(self, request: Optional[Any] = None) -> Dict[str, Any]:
        """
        Get this peer's current merkle clock state.
        
        Returns:
            Merkle clock data
        """
        if not P2P_SCHEDULER_AVAILABLE or self.scheduler is None:
            return {
                "success": False,
                "message": "P2P scheduler not available",
                "timestamp": time.time()
            }
        
        try:
            clock_data = self.scheduler.merkle_clock.to_dict()
            clock_data["success"] = True
            clock_data["message"] = "Merkle clock retrieved successfully"
            clock_data["timestamp"] = time.time()
            
            return clock_data
            
        except Exception as e:
            self.logger.error(f"Error getting merkle clock: {e}")
            return {
                "success": False,
                "message": f"Error getting merkle clock: {str(e)}",
                "timestamp": time.time()
            }
