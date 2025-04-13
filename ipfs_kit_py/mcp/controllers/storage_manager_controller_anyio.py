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
        logger.info(f"Registering routes for StorageManagerControllerAnyIO with router: {router}")
        
        # Tracks whether all critical routes were registered
        all_routes_registered = True
        registration_errors = {}
        
        # Route definitions with fallback mechanisms
        routes = [
            {
                "path": "/storage/status",
                "handler": self.handle_status_request_async,
                "methods": ["GET"],
                "response_model": AllBackendsStatusResponse,
                "summary": "Storage Status",
                "description": "Get status of all storage backends",
                "critical": True,  # This is a critical route that must be registered
                "fallback": self._create_fallback_status  # Fallback function to use if registration fails
            },
            {
                "path": "/storage/{backend_name}/status",
                "handler": self.handle_backend_status_request_async,
                "methods": ["GET"],
                "response_model": BackendStatusResponse,
                "summary": "Backend Status",
                "description": "Get status of a specific storage backend",
                "critical": True,
                "fallback": self._create_fallback_backend_status
            },
            {
                "path": "/storage/transfer",
                "handler": self.handle_transfer_request_async,
                "methods": ["POST"],
                "response_model": StorageTransferResponse,
                "summary": "Transfer Content",
                "description": "Transfer content between storage backends",
                "critical": True,
                "fallback": self._create_fallback_transfer
            },
            {
                "path": "/storage/verify",
                "handler": self.handle_verify_request_async,
                "methods": ["POST"],
                "response_model": OperationResponse,
                "summary": "Verify Content",
                "description": "Verify content across storage backends",
                "critical": False
            },
            {
                "path": "/storage/migrate",
                "handler": self.handle_migration_request_async,
                "methods": ["POST"],
                "response_model": ContentMigrationResponse,
                "summary": "Migrate Content",
                "description": "Migrate content between storage backends",
                "critical": False
            },
            {
                "path": "/storage/apply-policy",
                "handler": self.handle_replication_policy_request_async,
                "methods": ["POST"],
                "response_model": ReplicationPolicyResponse,
                "summary": "Apply Replication Policy",
                "description": "Apply storage replication policy to content based on content characteristics",
                "critical": False
            }
        ]
        
        # Register each route with error handling
        for route in routes:
            try:
                router.add_api_route(
                    route["path"],
                    route["handler"],
                    methods=route["methods"],
                    response_model=route.get("response_model"),
                    summary=route.get("summary"),
                    description=route.get("description")
                )
                logger.info(f"Successfully registered {route['path']} endpoint")
            except Exception as e:
                error_msg = f"Error registering {route['path']} endpoint: {str(e)}"
                logger.error(error_msg)
                registration_errors[route["path"]] = str(e)
                
                # If this is a critical route, mark registration as failed
                if route.get("critical", False):
                    all_routes_registered = False
                    
                    # Check if we have a fallback handler
                    if "fallback" in route and callable(route["fallback"]):
                        try:
                            # Register the fallback handler
                            fallback_handler = route["fallback"]()
                            router.add_api_route(
                                route["path"],
                                fallback_handler,
                                methods=route["methods"],
                                summary=f"{route.get('summary')} (Fallback)",
                                description=f"Fallback handler for {route['path']}"
                            )
                            logger.info(f"Registered fallback handler for {route['path']}")
                        except Exception as fallback_e:
                            logger.error(f"Error registering fallback for {route['path']}: {fallback_e}")
        
        # List all routes in the router after registration
        try:
            logger.info("Routes in router after registration:")
            route_paths = set()
            for route in router.routes:
                route_info = f"  Path: {route.path}"
                if hasattr(route, 'methods'):
                    route_info += f", Methods: {route.methods}"
                logger.info(route_info)
                route_paths.add(route.path)
            
            # Check for missing critical routes
            for route in routes:
                if route.get("critical", False) and route["path"] not in route_paths:
                    logger.error(f"Critical route {route['path']} not registered")
        except Exception as e:
            logger.error(f"Error listing router routes: {e}")
        
        # Log summary of registration
        if all_routes_registered:
            logger.info("All critical Storage Manager Controller routes registered successfully")
        else:
            logger.warning(f"Some critical routes failed to register: {registration_errors}")
        
        logger.info("Storage Manager Controller routes registered with AnyIO support")
    
    def _create_fallback_status(self):
        """Create a fallback handler for the status endpoint."""
        async def fallback_storage_status():
            """Fallback for storage status endpoint."""
            start_time = time.time()
            return {
                "success": True,
                "operation_id": f"storage_status_{int(start_time * 1000)}",
                "backends": {},
                "available_count": 0,
                "total_count": 0,
                "duration_ms": (time.time() - start_time) * 1000,
                "fallback": True,
                "timestamp": time.time()
            }
        return fallback_storage_status
        
    def _create_fallback_backend_status(self):
        """Create a fallback handler for the backend status endpoint."""
        async def fallback_backend_status(backend_name: str):
            """Fallback for backend status endpoint."""
            start_time = time.time()
            return {
                "success": False,
                "operation_id": f"backend_status_{int(start_time * 1000)}",
                "backend_name": backend_name,
                "is_available": False,
                "capabilities": [],
                "error": "Backend status unavailable due to route registration failure",
                "error_type": "FallbackHandlerError",
                "fallback": True,
                "duration_ms": (time.time() - start_time) * 1000,
                "timestamp": time.time()
            }
        return fallback_backend_status
    
    def _create_fallback_transfer(self):
        """Create a fallback handler for the transfer endpoint."""
        async def fallback_transfer(request: StorageTransferRequest):
            """Fallback for transfer endpoint."""
            start_time = time.time()
            return {
                "success": False,
                "operation_id": f"transfer_{int(start_time * 1000)}",
                "source_backend": request.source_backend,
                "target_backend": request.target_backend,
                "content_id": request.content_id,
                "error": "Transfer unavailable due to route registration failure",
                "error_type": "FallbackHandlerError",
                "fallback": True,
                "duration_ms": (time.time() - start_time) * 1000,
                "timestamp": time.time()
            }
        return fallback_transfer