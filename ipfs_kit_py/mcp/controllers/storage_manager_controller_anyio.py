"""
Storage Manager Controller AnyIO Module

This module provides AnyIO-compatible storage manager controller functionality.
"""

import anyio
import logging
import sys
import os
import time
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field

# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

logger = logging.getLogger(__name__)


class ReplicationPolicyRequest(BaseModel):
    """Request model for storage replication policies."""
    cid: str = Field(..., description="Content identifier to replicate")
    min_replicas: int = Field(3, description="Minimum number of replicas to maintain")
    backends: List[str] = Field([], description="Specific backends to use for replication")
    priority: str = Field("medium", description="Replication priority (low, medium, high)")
    verify: bool = Field(True, description="Verify replicas after creation")


class ReplicationPolicyResponse(BaseModel):
    """Response model for storage replication policies."""
    success: bool = Field(..., description="Whether the operation was successful")
    cid: str = Field(..., description="Content identifier")
    message: Optional[str] = Field(None, description="Status message")
    replicas: Optional[List[Dict[str, Any]]] = Field(None, description="Information about created replicas")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class StorageStatsRequest(BaseModel):
    """Request model for storage statistics."""
    backend: Optional[str] = Field(None, description="Specific backend to get stats for")
    include_details: bool = Field(False, description="Whether to include detailed statistics")


class StorageStatsResponse(BaseModel):
    """Response model for storage statistics."""
    success: bool = Field(..., description="Whether the operation was successful")
    timestamp: int = Field(..., description="Timestamp of the statistics")
    total_bytes: int = Field(0, description="Total bytes stored")
    available_bytes: int = Field(0, description="Available bytes for storage")
    item_count: int = Field(0, description="Number of stored items")
    backend_stats: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="Statistics by backend")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class StorageBackendRequest(BaseModel):
    """Request model for storage backend operations."""
    backend_id: str = Field(..., description="Identifier for the storage backend")
    backend_type: str = Field(..., description="Type of storage backend")
    config: Dict[str, Any] = Field(..., description="Configuration for the storage backend")
    enabled: bool = Field(True, description="Whether the backend is enabled")
    priority: int = Field(5, description="Priority of the backend (1-10)")


class StorageBackendResponse(BaseModel):
    """Response model for storage backend operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    backend_id: str = Field(..., description="Identifier for the storage backend")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class StorageManagerControllerAnyIO:
    """Storage manager controller with AnyIO support."""

    def __init__(self, storage_manager_model):
        """
        Initialize the storage manager controller.

        Args:
            storage_manager_model: Storage manager model for handling storage operations
        """
        self.storage_manager_model = storage_manager_model
        logger.info("Storage Manager Controller (AnyIO) initialized")

    def register_routes(self, router):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Get storage statistics
        router.add_api_route(
            "/stats",
            self.get_storage_stats,
            methods=["POST"],
            response_model=StorageStatsResponse,
            summary="Get storage statistics",
            description="Get statistics about storage usage across backends"
        )

        # Create replication policy
        router.add_api_route(
            "/replicate",
            self.create_replication_policy,
            methods=["POST"],
            response_model=ReplicationPolicyResponse,
            summary="Create replication policy",
            description="Create a policy for replicating content across storage backends"
        )

        # Add storage backend
        router.add_api_route(
            "/backends/add",
            self.add_storage_backend,
            methods=["POST"],
            response_model=StorageBackendResponse,
            summary="Add storage backend",
            description="Add a new storage backend to the system"
        )

        # Remove storage backend
        router.add_api_route(
            "/backends/remove/{backend_id}",
            self.remove_storage_backend,
            methods=["DELETE"],
            response_model=StorageBackendResponse,
            summary="Remove storage backend",
            description="Remove a storage backend from the system"
        )

        # List storage backends
        router.add_api_route(
            "/backends/list",
            self.list_storage_backends,
            methods=["GET"],
            summary="List storage backends",
            description="List all storage backends in the system"
        )

        logger.info("Storage Manager Controller (AnyIO) routes registered")

    async def get_storage_stats(self, request: StorageStatsRequest) -> Dict[str, Any]:
        """
        Get storage statistics.

        Args:
            request: Storage statistics request

        Returns:
            Dictionary with storage statistics
        """
        try:
            logger.info("Getting storage statistics")
            
            # Call the model's get_storage_stats method
            result = await self.storage_manager_model.get_storage_stats(
                backend=request.backend,
                include_details=request.include_details
            )
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error getting storage statistics: {error_msg}")
                return {
                    "success": False,
                    "timestamp": int(time.time()),
                    "error": error_msg
                }
            
            return {
                "success": True,
                "timestamp": result.get("timestamp", int(time.time())),
                "total_bytes": result.get("total_bytes", 0),
                "available_bytes": result.get("available_bytes", 0),
                "item_count": result.get("item_count", 0),
                "backend_stats": result.get("backend_stats", {})
            }
            
        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}")
            return {
                "success": False,
                "timestamp": int(time.time()),
                "error": str(e)
            }

    async def create_replication_policy(self, request: ReplicationPolicyRequest) -> Dict[str, Any]:
        """
        Create a replication policy.

        Args:
            request: Replication policy request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Creating replication policy for CID: {request.cid}")
            
            # Call the model's create_replication_policy method
            result = await self.storage_manager_model.create_replication_policy(
                cid=request.cid,
                min_replicas=request.min_replicas,
                backends=request.backends,
                priority=request.priority,
                verify=request.verify
            )
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error creating replication policy: {error_msg}")
                return {
                    "success": False,
                    "cid": request.cid,
                    "error": error_msg
                }
            
            return {
                "success": True,
                "cid": request.cid,
                "message": result.get("message", "Replication policy created successfully"),
                "replicas": result.get("replicas", [])
            }
            
        except Exception as e:
            logger.error(f"Error creating replication policy: {e}")
            return {
                "success": False,
                "cid": request.cid,
                "error": str(e)
            }

    async def add_storage_backend(self, request: StorageBackendRequest) -> Dict[str, Any]:
        """
        Add a storage backend.

        Args:
            request: Storage backend request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Adding storage backend: {request.backend_id} (type: {request.backend_type})")
            
            # Call the model's add_storage_backend method
            result = await self.storage_manager_model.add_storage_backend(
                backend_id=request.backend_id,
                backend_type=request.backend_type,
                config=request.config,
                enabled=request.enabled,
                priority=request.priority
            )
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error adding storage backend: {error_msg}")
                return {
                    "success": False,
                    "backend_id": request.backend_id,
                    "error": error_msg
                }
            
            return {
                "success": True,
                "backend_id": request.backend_id,
                "message": result.get("message", "Storage backend added successfully")
            }
            
        except Exception as e:
            logger.error(f"Error adding storage backend: {e}")
            return {
                "success": False,
                "backend_id": request.backend_id,
                "error": str(e)
            }

    async def remove_storage_backend(self, backend_id: str) -> Dict[str, Any]:
        """
        Remove a storage backend.

        Args:
            backend_id: ID of the storage backend to remove

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Removing storage backend: {backend_id}")
            
            # Call the model's remove_storage_backend method
            result = await self.storage_manager_model.remove_storage_backend(backend_id)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error removing storage backend: {error_msg}")
                return {
                    "success": False,
                    "backend_id": backend_id,
                    "error": error_msg
                }
            
            return {
                "success": True,
                "backend_id": backend_id,
                "message": result.get("message", "Storage backend removed successfully")
            }
            
        except Exception as e:
            logger.error(f"Error removing storage backend: {e}")
            return {
                "success": False,
                "backend_id": backend_id,
                "error": str(e)
            }

    async def list_storage_backends(self) -> Dict[str, Any]:
        """
        List storage backends.

        Returns:
            Dictionary with list of storage backends
        """
        try:
            logger.info("Listing storage backends")
            
            # Call the model's list_storage_backends method
            result = await self.storage_manager_model.list_storage_backends()
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error listing storage backends: {error_msg}")
                return {
                    "success": False,
                    "backends": [],
                    "error": error_msg
                }
            
            return {
                "success": True,
                "backends": result.get("backends", []),
                "count": len(result.get("backends", []))
            }
            
        except Exception as e:
            logger.error(f"Error listing storage backends: {e}")
            return {
                "success": False,
                "backends": [],
                "error": str(e)
            }
