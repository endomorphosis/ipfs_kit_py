"""
Storage Manager Controller for MCP Server with AnyIO support.

This controller provides a unified interface for managing multiple storage backends
and their integration with the MCP server, with support for both asyncio and trio
via the AnyIO library.
"""

import logging
import time
import warnings
import sniffio
from typing import Dict, List, Any, Optional, Union

# AnyIO import
import anyio

# Import Pydantic models for request/response validation
from fastapi import APIRouter, HTTPException, Depends, Body, Response, Path, Query

try:
    from pydantic import BaseModel, Field
except ImportError:
    # For testing without Pydantic
    class BaseModel:
        pass
    def Field(*args, **kwargs):
        return None

# Import original controller for inheritance
from ipfs_kit_py.mcp.controllers.storage_manager_controller import (
    StorageManagerController, 
    OperationResponse,
    ReplicationPolicyRequest,
    ReplicationPolicyResponse,
    BackendStatusResponse,
    AllBackendsStatusResponse,
    StorageTransferRequest,
    StorageTransferResponse,
    ContentMigrationRequest,
    ContentMigrationResponse
)

# Configure logger
logger = logging.getLogger(__name__)

class StorageManagerControllerAnyIO(StorageManagerController):
    """
    Controller for storage manager operations with AnyIO support.
    
    Provides endpoints for managing multiple storage backends and
    transferring content between them, supporting both asyncio and trio
    backends through AnyIO compatibility.
    """
    
    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
    
    def _warn_if_async_context(self, method_name):
        """Warn if called from async context without using async version."""
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
                stacklevel=3
            )
    
    def handle_status_request(self):
        """
        Handle request for status of all storage backends.
        
        Returns:
            Dictionary with status of all storage backends
        """
        self._warn_if_async_context("handle_status_request")
        return super().handle_status_request()
    
    def handle_backend_status_request(self, backend_name: str):
        """
        Handle request for status of a specific storage backend.
        
        Args:
            backend_name: Name of the storage backend
            
        Returns:
            Dictionary with status of the specified backend
        """
        self._warn_if_async_context("handle_backend_status_request")
        return super().handle_backend_status_request(backend_name)
    
    def handle_transfer_request(self, request: StorageTransferRequest):
        """
        Handle request to transfer content between storage backends.
        
        Args:
            request: Transfer request parameters
            
        Returns:
            Dictionary with transfer operation result
        """
        self._warn_if_async_context("handle_transfer_request")
        return super().handle_transfer_request(request)
    
    def handle_verify_request(self, content_id: str = Body(..., embed=True), backends: List[str] = Body(None, embed=True)):
        """
        Handle request to verify content across storage backends.
        
        Args:
            content_id: Content identifier to verify
            backends: Optional list of backends to check (defaults to all)
            
        Returns:
            Dictionary with verification results
        """
        self._warn_if_async_context("handle_verify_request")
        return super().handle_verify_request(content_id, backends)
    
    def handle_migration_request(self, request: ContentMigrationRequest):
        """
        Handle request to migrate content between storage backends.
        
        Args:
            request: Migration request parameters
            
        Returns:
            Dictionary with migration operation results
        """
        self._warn_if_async_context("handle_migration_request")
        return super().handle_migration_request(request)
    
    def handle_replication_policy_request(self, request: ReplicationPolicyRequest):
        """
        Handle request to apply a replication policy to content.
        
        The policy specifies how content should be distributed across backends
        based on various criteria like content type, size, and importance.
        
        Args:
            request: Replication policy request parameters
            
        Returns:
            Dictionary with replication policy application result
        """
        self._warn_if_async_context("handle_replication_policy_request")
        return super().handle_replication_policy_request(request)
    
    # Async versions of all handler methods
    
    async def handle_status_request_async(self):
        """
        Handle request for status of all storage backends asynchronously.
        
        Returns:
            Dictionary with status of all storage backends
        """
        return await anyio.to_thread.run_sync(self.handle_status_request)
    
    async def handle_backend_status_request_async(self, backend_name: str):
        """
        Handle request for status of a specific storage backend asynchronously.
        
        Args:
            backend_name: Name of the storage backend
            
        Returns:
            Dictionary with status of the specified backend
        """
        return await anyio.to_thread.run_sync(
            self.handle_backend_status_request,
            backend_name
        )
    
    async def handle_transfer_request_async(self, request: StorageTransferRequest):
        """
        Handle request to transfer content between storage backends asynchronously.
        
        Args:
            request: Transfer request parameters
            
        Returns:
            Dictionary with transfer operation result
        """
        return await anyio.to_thread.run_sync(
            self.handle_transfer_request,
            request
        )
    
    async def handle_verify_request_async(self, content_id: str = Body(..., embed=True), backends: List[str] = Body(None, embed=True)):
        """
        Handle request to verify content across storage backends asynchronously.
        
        Args:
            content_id: Content identifier to verify
            backends: Optional list of backends to check (defaults to all)
            
        Returns:
            Dictionary with verification results
        """
        return await anyio.to_thread.run_sync(
            self.handle_verify_request,
            content_id,
            backends
        )
    
    async def handle_migration_request_async(self, request: ContentMigrationRequest):
        """
        Handle request to migrate content between storage backends asynchronously.
        
        Args:
            request: Migration request parameters
            
        Returns:
            Dictionary with migration operation results
        """
        return await anyio.to_thread.run_sync(
            self.handle_migration_request,
            request
        )
    
    async def handle_replication_policy_request_async(self, request: ReplicationPolicyRequest):
        """
        Handle request to apply a replication policy to content asynchronously.
        
        The policy specifies how content should be distributed across backends
        based on various criteria like content type, size, and importance.
        
        Args:
            request: Replication policy request parameters
            
        Returns:
            Dictionary with replication policy application result
        """
        return await anyio.to_thread.run_sync(
            self.handle_replication_policy_request,
            request
        )
    
    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.
        
        In AnyIO mode, registers the async versions of handlers.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Get status of all storage backends
        router.add_api_route(
            "/storage/status",
            self.handle_status_request_async,
            methods=["GET"],
            response_model=AllBackendsStatusResponse,
            summary="Storage Status",
            description="Get status of all storage backends"
        )
        
        # Get status of a specific backend
        router.add_api_route(
            "/storage/{backend_name}/status",
            self.handle_backend_status_request_async,
            methods=["GET"],
            response_model=BackendStatusResponse,
            summary="Backend Status",
            description="Get status of a specific storage backend"
        )
        
        # Transfer content between backends
        router.add_api_route(
            "/storage/transfer",
            self.handle_transfer_request_async,
            methods=["POST"],
            response_model=StorageTransferResponse,
            summary="Transfer Content",
            description="Transfer content between storage backends"
        )
        
        # Register routes for storage bridge operations
        router.add_api_route(
            "/storage/verify",
            self.handle_verify_request_async,
            methods=["POST"],
            response_model=OperationResponse,
            summary="Verify Content",
            description="Verify content across storage backends"
        )
        
        # Register migration endpoint
        router.add_api_route(
            "/storage/migrate",
            self.handle_migration_request_async,
            methods=["POST"],
            response_model=ContentMigrationResponse,
            summary="Migrate Content",
            description="Migrate content between storage backends"
        )
        
        # Register replication policy endpoint
        router.add_api_route(
            "/storage/apply-policy",
            self.handle_replication_policy_request_async,
            methods=["POST"],
            response_model=ReplicationPolicyResponse,
            summary="Apply Replication Policy",
            description="Apply storage replication policy to content based on content characteristics"
        )
        
        logger.info("Storage Manager Controller routes registered with AnyIO support")