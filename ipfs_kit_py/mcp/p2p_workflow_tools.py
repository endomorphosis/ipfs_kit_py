#!/usr/bin/env python3
"""
MCP Server Tools for P2P Workflow Management

This module exposes P2P workflow coordination functionality as MCP server tools,
allowing AI assistants and external systems to manage distributed workflow execution
across the IPFS peer-to-peer network.
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from ..p2p_workflow_coordinator import (
    P2PWorkflowCoordinator,
    WorkflowStatus,
    WorkflowTask
)

logger = logging.getLogger(__name__)


class P2PWorkflowTools:
    """
    MCP tools for P2P workflow coordination.
    
    These tools provide a high-level interface for managing workflows
    distributed across a peer-to-peer IPFS network.
    """
    
    def __init__(self, coordinator: Optional[P2PWorkflowCoordinator] = None):
        """
        Initialize P2P workflow tools.
        
        Args:
            coordinator: Optional existing coordinator instance
        """
        self.coordinator = coordinator
        self._default_peer_id = "mcp-server-peer"
    
    def _ensure_coordinator(self) -> P2PWorkflowCoordinator:
        """Ensure coordinator is initialized."""
        if self.coordinator is None:
            self.coordinator = P2PWorkflowCoordinator(
                peer_id=self._default_peer_id
            )
        return self.coordinator
    
    def submit_p2p_workflow(
        self,
        workflow_file: str,
        name: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        priority: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Submit a workflow for P2P execution.
        
        This tool submits a GitHub Actions workflow to the P2P network
        for execution, bypassing the GitHub API completely.
        
        Args:
            workflow_file: Path to workflow YAML file or workflow content
            name: Optional workflow name
            inputs: Optional workflow inputs
            priority: Optional priority (lower = higher priority, default 5.0)
        
        Returns:
            Dictionary with workflow_id and status
        """
        try:
            coordinator = self._ensure_coordinator()
            
            workflow_id = coordinator.submit_workflow(
                workflow_file=workflow_file,
                name=name,
                inputs=inputs or {},
                priority=priority
            )
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                "message": f"Workflow submitted successfully: {workflow_id}",
                "status": "pending"
            }
        
        except Exception as e:
            logger.error(f"Failed to submit P2P workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to submit workflow"
            }
    
    def assign_p2p_workflows(self) -> Dict[str, Any]:
        """
        Assign pending workflows to peers.
        
        This tool triggers the workflow assignment process, using merkle clock
        consensus and hamming distance to determine which peer should handle
        each workflow.
        
        Returns:
            Dictionary with assignment results
        """
        try:
            coordinator = self._ensure_coordinator()
            assigned = coordinator.assign_workflows()
            
            return {
                "success": True,
                "assigned_count": len(assigned),
                "workflow_ids": assigned,
                "message": f"Assigned {len(assigned)} workflows to peers"
            }
        
        except Exception as e:
            logger.error(f"Failed to assign P2P workflows: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to assign workflows"
            }
    
    def get_p2p_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get the status of a P2P workflow.
        
        Args:
            workflow_id: Unique identifier of the workflow
        
        Returns:
            Dictionary with workflow status and details
        """
        try:
            coordinator = self._ensure_coordinator()
            status = coordinator.get_workflow_status(workflow_id)
            
            if status is None:
                return {
                    "success": False,
                    "error": "Workflow not found",
                    "workflow_id": workflow_id
                }
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                **status
            }
        
        except Exception as e:
            logger.error(f"Failed to get P2P workflow status: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_id": workflow_id
            }
    
    def list_p2p_workflows(
        self,
        status: Optional[str] = None,
        peer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List P2P workflows with optional filtering.
        
        Args:
            status: Optional status filter (pending, assigned, in_progress, completed, failed)
            peer_id: Optional peer ID filter
        
        Returns:
            Dictionary with list of workflows
        """
        try:
            coordinator = self._ensure_coordinator()
            
            status_filter = None
            if status:
                try:
                    status_filter = WorkflowStatus(status)
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid status: {status}",
                        "valid_statuses": [s.value for s in WorkflowStatus]
                    }
            
            workflows = coordinator.list_workflows(
                status=status_filter,
                peer_id=peer_id
            )
            
            return {
                "success": True,
                "count": len(workflows),
                "workflows": workflows,
                "filters": {
                    "status": status,
                    "peer_id": peer_id
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to list P2P workflows: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to list workflows"
            }
    
    def update_p2p_workflow_status(
        self,
        workflow_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update the status of a P2P workflow.
        
        Args:
            workflow_id: Unique identifier of the workflow
            status: New status (pending, assigned, in_progress, completed, failed, cancelled)
            result: Optional result data
            error: Optional error message
        
        Returns:
            Dictionary with update confirmation
        """
        try:
            coordinator = self._ensure_coordinator()
            
            try:
                status_enum = WorkflowStatus(status)
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid status: {status}",
                    "valid_statuses": [s.value for s in WorkflowStatus]
                }
            
            success = coordinator.update_workflow_status(
                workflow_id=workflow_id,
                status=status_enum,
                result=result,
                error=error
            )
            
            if success:
                return {
                    "success": True,
                    "workflow_id": workflow_id,
                    "new_status": status,
                    "message": "Workflow status updated successfully"
                }
            else:
                return {
                    "success": False,
                    "workflow_id": workflow_id,
                    "error": "Failed to update workflow status"
                }
        
        except Exception as e:
            logger.error(f"Failed to update P2P workflow status: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_id": workflow_id
            }
    
    def add_p2p_peer(self, peer_id: str) -> Dict[str, Any]:
        """
        Add a peer to the P2P network.
        
        Args:
            peer_id: Unique identifier of the peer to add
        
        Returns:
            Dictionary with confirmation
        """
        try:
            coordinator = self._ensure_coordinator()
            coordinator.add_peer(peer_id)
            
            return {
                "success": True,
                "peer_id": peer_id,
                "message": f"Peer {peer_id} added to network"
            }
        
        except Exception as e:
            logger.error(f"Failed to add P2P peer: {e}")
            return {
                "success": False,
                "error": str(e),
                "peer_id": peer_id
            }
    
    def remove_p2p_peer(self, peer_id: str) -> Dict[str, Any]:
        """
        Remove a peer from the P2P network.
        
        Args:
            peer_id: Unique identifier of the peer to remove
        
        Returns:
            Dictionary with confirmation
        """
        try:
            coordinator = self._ensure_coordinator()
            coordinator.remove_peer(peer_id)
            
            return {
                "success": True,
                "peer_id": peer_id,
                "message": f"Peer {peer_id} removed from network"
            }
        
        except Exception as e:
            logger.error(f"Failed to remove P2P peer: {e}")
            return {
                "success": False,
                "error": str(e),
                "peer_id": peer_id
            }
    
    def get_p2p_stats(self) -> Dict[str, Any]:
        """
        Get P2P workflow coordinator statistics.
        
        Returns:
            Dictionary with coordinator stats
        """
        try:
            coordinator = self._ensure_coordinator()
            stats = coordinator.get_stats()
            
            return {
                "success": True,
                **stats
            }
        
        except Exception as e:
            logger.error(f"Failed to get P2P stats: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to retrieve stats"
            }
    
    def parse_workflow_tags(self, workflow_file: str) -> Dict[str, Any]:
        """
        Parse a workflow file to check if it's tagged for P2P execution.
        
        Args:
            workflow_file: Path to workflow YAML file
        
        Returns:
            Dictionary with workflow metadata and P2P eligibility
        """
        try:
            coordinator = self._ensure_coordinator()
            workflow_path = Path(workflow_file)
            
            if not workflow_path.exists():
                return {
                    "success": False,
                    "error": f"Workflow file not found: {workflow_file}",
                    "is_p2p": False
                }
            
            metadata = coordinator.parse_workflow_file(workflow_path)
            is_p2p = coordinator.is_p2p_workflow(metadata)
            
            return {
                "success": True,
                "workflow_file": str(workflow_file),
                "is_p2p": is_p2p,
                "metadata": {
                    "name": metadata.get('name'),
                    "tags": list(metadata.get('tags', [])),
                    "jobs": metadata.get('jobs', [])
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to parse workflow tags: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_file": workflow_file,
                "is_p2p": False
            }
    
    def get_my_p2p_workflows(self) -> Dict[str, Any]:
        """
        Get workflows assigned to this peer.
        
        Returns:
            Dictionary with workflows assigned to this peer
        """
        try:
            coordinator = self._ensure_coordinator()
            my_workflows = coordinator.get_my_workflows()
            
            return {
                "success": True,
                "count": len(my_workflows),
                "peer_id": coordinator.peer_id,
                "workflows": [w.to_dict() for w in my_workflows]
            }
        
        except Exception as e:
            logger.error(f"Failed to get my P2P workflows: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to retrieve workflows"
            }


# MCP tool definitions for registration
MCP_TOOLS = [
    {
        "name": "submit_p2p_workflow",
        "description": "Submit a workflow for P2P execution across IPFS network",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_file": {
                    "type": "string",
                    "description": "Path to workflow YAML file"
                },
                "name": {
                    "type": "string",
                    "description": "Optional workflow name"
                },
                "inputs": {
                    "type": "object",
                    "description": "Optional workflow inputs"
                },
                "priority": {
                    "type": "number",
                    "description": "Optional priority (lower = higher priority, default 5.0)"
                }
            },
            "required": ["workflow_file"]
        }
    },
    {
        "name": "assign_p2p_workflows",
        "description": "Assign pending workflows to peers using merkle clock consensus",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_p2p_workflow_status",
        "description": "Get the status of a P2P workflow",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Unique identifier of the workflow"
                }
            },
            "required": ["workflow_id"]
        }
    },
    {
        "name": "list_p2p_workflows",
        "description": "List P2P workflows with optional filtering",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "assigned", "in_progress", "completed", "failed", "cancelled"],
                    "description": "Optional status filter"
                },
                "peer_id": {
                    "type": "string",
                    "description": "Optional peer ID filter"
                }
            }
        }
    },
    {
        "name": "update_p2p_workflow_status",
        "description": "Update the status of a P2P workflow",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Unique identifier of the workflow"
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "assigned", "in_progress", "completed", "failed", "cancelled"],
                    "description": "New status"
                },
                "result": {
                    "type": "object",
                    "description": "Optional result data"
                },
                "error": {
                    "type": "string",
                    "description": "Optional error message"
                }
            },
            "required": ["workflow_id", "status"]
        }
    },
    {
        "name": "add_p2p_peer",
        "description": "Add a peer to the P2P network",
        "inputSchema": {
            "type": "object",
            "properties": {
                "peer_id": {
                    "type": "string",
                    "description": "Unique identifier of the peer"
                }
            },
            "required": ["peer_id"]
        }
    },
    {
        "name": "remove_p2p_peer",
        "description": "Remove a peer from the P2P network",
        "inputSchema": {
            "type": "object",
            "properties": {
                "peer_id": {
                    "type": "string",
                    "description": "Unique identifier of the peer"
                }
            },
            "required": ["peer_id"]
        }
    },
    {
        "name": "get_p2p_stats",
        "description": "Get P2P workflow coordinator statistics",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "parse_workflow_tags",
        "description": "Parse a workflow file to check if it's tagged for P2P execution",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_file": {
                    "type": "string",
                    "description": "Path to workflow YAML file"
                }
            },
            "required": ["workflow_file"]
        }
    },
    {
        "name": "get_my_p2p_workflows",
        "description": "Get workflows assigned to this peer",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]
