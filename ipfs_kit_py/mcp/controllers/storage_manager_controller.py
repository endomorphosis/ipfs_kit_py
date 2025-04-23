"""
Storage Manager Controller for MCP Server.

This controller provides a unified interface for managing multiple storage backends
and their integration with the MCP server.
"""

import logging
import time
import sys
import os
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

# Configure logger
logger = logging.getLogger(__name__)


# Define Pydantic models for requests and responses
class OperationResponse(BaseModel):
    """Base response model for operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: Optional[str] = Field(None, description="Unique identifier for this operation")
    duration_ms: Optional[float] = Field(
        None, description="Duration of the operation in milliseconds"
    )


class ReplicationPolicyRequest(BaseModel):
    """Request model for applying replication policies to content."""
    content_id: str = Field(..., description="Content identifier (CID)")
    policy: Dict[str, Any] = Field(..., description="Replication policy configuration")


class ReplicationPolicyResponse(OperationResponse):
    """Response model for replication policy application."""
    content_id: str = Field(..., description="Content identifier (CID)")
    source_backend: str = Field(..., description="Source backend name")
    backends_selected: List[str] = Field([], description="List of backends selected by the policy")
    policy_applied: bool = Field(False, description="Whether the policy was successfully applied")
    successful_backends: List[str] = Field(
        [], description="List of backends where replication succeeded"
    )
    failed_backends: List[str] = Field([], description="List of backends where replication failed")
    bytes_transferred: Optional[int] = Field(None, description="Number of bytes transferred")


class BackendStatusResponse(OperationResponse):
    """Response model for backend status information."""
    backend_name: str = Field(..., description="Name of the storage backend")
    is_available: bool = Field(..., description="Whether the backend is available")
    capabilities: List[str] = Field(
        [], description="List of capabilities supported by this backend"
    )
    stats: Optional[Dict[str, Any]] = Field(None, description="Backend statistics")


class AllBackendsStatusResponse(OperationResponse):
    """Response model for status of all storage backends."""
    backends: Dict[str, Any] = Field(
        {}, description="Status of each storage backend"
    )
    available_count: int = Field(0, description="Number of available backends")
    total_count: int = Field(0, description="Total number of backends")


class StorageTransferRequest(BaseModel):
    """Request model for transferring content between storage backends."""
    source_backend: str = Field(..., description="Source backend name")
    target_backend: str = Field(..., description="Target backend name")
    content_id: str = Field(..., description="Content identifier (CID)")
    options: Optional[Dict[str, Any]] = Field(None, description="Backend-specific options")


class StorageTransferResponse(OperationResponse):
    """Response model for content transfer operations."""
    source_backend: str = Field(..., description="Source backend name")
    target_backend: str = Field(..., description="Target backend name")
    content_id: str = Field(..., description="Content identifier (CID)")
    target_location: Optional[str] = Field(None, description="Location in the target backend")
    source_location: Optional[str] = Field(None, description="Location in the source backend")
    bytes_transferred: Optional[int] = Field(None, description="Number of bytes transferred")


class ContentMigrationRequest(BaseModel):
    """Request model for migrating content between storage backends."""
    source_backend: str = Field(..., description="Source backend name")
    target_backend: str = Field(..., description="Target backend name")
    content_ids: List[str] = Field(..., description="List of content identifiers (CIDs) to migrate")
    options: Optional[Dict[str, Any]] = Field(None, description="Backend-specific options")
    delete_source: bool = Field(
        False, description="Whether to delete content from source after migration"
    )
    verify_integrity: bool = Field(
        True, description="Whether to verify content integrity after migration"
    )


class ContentMigrationResponse(OperationResponse):
    """Response model for content migration operations."""
    source_backend: str = Field(..., description="Source backend name")
    target_backend: str = Field(..., description="Target backend name")
    content_count: int = Field(..., description="Number of content items in migration")
    successful_count: int = Field(..., description="Number of successfully migrated items")
    failed_count: int = Field(..., description="Number of failed migrations")
    total_bytes_transferred: int = Field(0, description="Total bytes transferred")
    results: Dict[str, Any] = Field({}, description="Detailed results for each content item")


class StorageManagerController:
    """
    Controller for storage manager operations.

    Provides endpoints for managing multiple storage backends and
    transferring content between them.
    """
    def __init__(self, storage_manager):
        """
        Initialize the storage manager controller.

        Args:
            storage_manager: The storage manager to use for operations
        """
        self.storage_manager = storage_manager
        self.is_shutting_down = False
        self.active_transfers = {}
        logger.info("Storage Manager Controller initialized")

    async def shutdown(self):
        """
        Safely shut down the Storage Manager Controller.

        This method ensures proper cleanup of all storage-related resources,
        including closing active transfers and connections to storage backends.
        """
        logger.info("Storage Manager Controller shutdown initiated")

        # Signal that we're shutting down to prevent new operations
        self.is_shutting_down = True

        # Track any errors during shutdown
        errors = []

        # 1. Clean up any active transfers
        if hasattr(self, "active_transfers") and self.active_transfers:
            logger.info(f"Cleaning up {len(self.active_transfers)} active transfers")
            for transfer_id, transfer_info in list(self.active_transfers.items()):
                try:
                    logger.debug(f"Cancelling transfer {transfer_id}")
                    # Add specific cancellation logic here if needed
                    # For now, just remove from tracking
                    if transfer_id in self.active_transfers:
                        del self.active_transfers[transfer_id]
                except Exception as e:
                    error_msg = f"Error cancelling transfer {transfer_id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        # 2. Reset all models in the storage manager
        if hasattr(self.storage_manager, "reset"):
            try:
                logger.info("Resetting all storage models")
                self.storage_manager.reset()
            except Exception as e:
                error_msg = f"Error resetting storage models: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # 3. Clean up each storage model individually
        if hasattr(self.storage_manager, "get_all_models"):
            try:
                models = self.storage_manager.get_all_models()
                logger.info(f"Shutting down {len(models)} storage models")

                for model_name, model in models.items():
                    try:
                        # Try to call shutdown method if it exists
                        if hasattr(model, "shutdown"):
                            logger.debug(f"Shutting down {model_name} model")
                            model.shutdown()
                        elif hasattr(model, "close"):
                            logger.debug(f"Closing {model_name} model")
                            model.close()
                    except Exception as e:
                        error_msg = f"Error shutting down {model_name} model: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
            except Exception as e:
                error_msg = f"Error accessing storage models: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # 4. Clean up storage bridge if it exists
        if (
            hasattr(self.storage_manager, "storage_bridge")
            and self.storage_manager.storage_bridge is not None
        ):
            try:
                bridge = self.storage_manager.storage_bridge
                if hasattr(bridge, "shutdown"):
                    logger.info("Shutting down storage bridge")
                    bridge.shutdown()
                elif hasattr(bridge, "close"):
                    logger.info("Closing storage bridge")
                    bridge.close()
            except Exception as e:
                error_msg = f"Error shutting down storage bridge: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # 5. Final cleanup of any remaining resources
        try:
            # Clear any dictionaries or references that might hold resources
            if hasattr(self, "active_transfers"):
                self.active_transfers.clear()
        except Exception as e:
            error_msg = f"Error in final cleanup: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        # Log shutdown status
        if errors:
            logger.warning(
                f"Storage Manager Controller shutdown completed with {len(errors)} errors"
            )
        else:
            logger.info("Storage Manager Controller shutdown completed successfully")

    def sync_shutdown(self):
        """
        Synchronous version of shutdown for backward compatibility.

        This method provides a synchronous way to shut down the controller
        for contexts where async/await cannot be used directly.
        """
        logger.info("Running synchronous shutdown for Storage Manager Controller")

        # Signal that we're shutting down
        self.is_shutting_down = True

        # Check for interpreter shutdown
        import sys

        is_interpreter_shutdown = hasattr(sys, "is_finalizing") and sys.is_finalizing()

        # Fast path for interpreter shutdown
        if is_interpreter_shutdown:
            logger.warning("Detected interpreter shutdown, using simplified cleanup")
            try:
                # Clear active resources without trying to create new threads
                if hasattr(self, "active_transfers"):
                    self.active_transfers.clear()

                logger.info(
                    "Simplified Storage Manager Controller shutdown completed during interpreter shutdown"
                )
                return
            except Exception as e:
                logger.error(f"Error during simplified shutdown: {e}")
                # Continue with standard shutdown which might fail gracefully

        try:
            # Try using anyio
            try:
                import anyio

                anyio.run(self.shutdown)
                return
            except ImportError:
                logger.warning("anyio not available, falling back to asyncio")
            except Exception as e:
                logger.warning(f"Error using anyio.run for shutdown: {e}, falling back to asyncio")

            # Fallback to asyncio
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # Create a new event loop if needed and not in shutdown
                if is_interpreter_shutdown:
                    logger.warning("Cannot get event loop during interpreter shutdown")
                    # Just clear resources directly
                    if hasattr(self, "active_transfers"):
                        self.active_transfers.clear()
                    return

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run the shutdown method
            try:
                loop.run_until_complete(self.shutdown())
            except RuntimeError as e:
                if "This event loop is already running" in str(e):
                    logger.warning("Cannot use run_until_complete in a running event loop")
                    # Cannot handle properly in this case
                elif "can't create new thread" in str(e):
                    logger.warning("Thread creation failed during interpreter shutdown")
                    # Clear resources directly
                    if hasattr(self, "active_transfers"):
                        self.active_transfers.clear()
                else:
                    raise

        except Exception as e:
            logger.error(f"Error in sync_shutdown for Storage Manager Controller: {e}")
            # Ensure resources are cleared even on error
            try:
                if hasattr(self, "active_transfers"):
                    self.active_transfers.clear()
            except Exception as clear_error:
                logger.error(f"Error clearing resources during error handling: {clear_error}")

        logger.info("Synchronous shutdown for Storage Manager Controller completed")

    def register_routes(self, router: APIRouter, prefix: str = ""):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Get status of all storage backends
        router.add_api_route(
            "/storage/status",
            self.handle_status_request,
            methods=["GET"],
            response_model=AllBackendsStatusResponse,
            summary="Storage Status",
            description="Get status of all storage backends",
        )

        # Get status of a specific backend
        router.add_api_route(
            "/storage/{backend_name}/status",
            self.handle_backend_status_request,
            methods=["GET"],
            response_model=BackendStatusResponse,
            summary="Backend Status",
            description="Get status of a specific storage backend",
        )

        # Transfer content between backends
        router.add_api_route(
            "/storage/transfer",
            self.handle_transfer_request,
            methods=["POST"],
            response_model=StorageTransferResponse,
            summary="Transfer Content",
            description="Transfer content between storage backends",
        )

        # Register routes for storage bridge operations
        router.add_api_route(
            "/storage/verify",
            self.handle_verify_request,
            methods=["POST"],
            response_model=OperationResponse,
            summary="Verify Content",
            description="Verify content across storage backends",
        )

        # Register migration endpoint
        router.add_api_route(
            "/storage/migrate",
            self.handle_migration_request,
            methods=["POST"],
            response_model=ContentMigrationResponse,
            summary="Migrate Content",
            description="Migrate content between storage backends",
        )

        # Register replication policy endpoint
        router.add_api_route(
            "/storage/apply-policy",
            self.handle_replication_policy_request,
            methods=["POST"],
            response_model=ReplicationPolicyResponse,
            summary="Apply Replication Policy",
            description="Apply storage replication policy to content based on content characteristics",
        )

        logger.info("Storage Manager Controller routes registered")

    async def handle_status_request(self):
        """
        Handle request for status of all storage backends.

        Returns:
            Dictionary with status of all storage backends
        """
        start_time = time.time()

        try:
            # Create default response structure first to ensure we always return a valid response
            response = {
                "success": True,
                "operation_id": f"storage_status_{int(start_time * 1000)}",
                "backends": {},
                "available_count": 0,
                "total_count": 0,
                "duration_ms": 0,
            }

            try:
                # Get available backends
                available_backends = self.storage_manager.get_available_backends()
                response["total_count"] = len(available_backends)
            except Exception as e:
                logger.error(f"Error getting available backends: {str(e)}")
                response["error"] = f"Failed to get backends: {str(e)}"
                response["error_type"] = type(e).__name__
                response["success"] = False
                response["duration_ms"] = (time.time() - start_time) * 1000
                return response

            try:
                # Get all models - protect against None
                models = self.storage_manager.get_all_models() or {}
            except Exception as e:
                logger.error(f"Error getting backend models: {str(e)}")
                models = {}
                # Still continue to provide partial status

            # Prepare response
            backends_status = {}
            available_count = 0

            # Process each backend
            for backend_name, is_available in available_backends.items():
                try:
                    if is_available:
                        available_count += 1

                    backend_model = None
                    try:
                        backend_model = models.get(backend_name)
                    except Exception as e:
                        logger.error(f"Error accessing model for {backend_name}: {str(e)}")

                    # Get stats
                    stats = None
                    try:
                        if backend_model:
                            stats = backend_model.get_stats()
                    except Exception as e:
                        logger.error(f"Error getting stats for {backend_name}: {str(e)}")
                        stats = {"error": str(e), "error_type": type(e).__name__}

                    # Get capabilities
                    capabilities = []
                    try:
                        if backend_model:
                            capabilities = self._get_backend_capabilities(
                                backend_name, backend_model
                            )
                    except Exception as e:
                        logger.error(f"Error getting capabilities for {backend_name}: {str(e)}")

                    backends_status[backend_name] = {
                        "backend_name": backend_name,
                        "is_available": is_available,
                        "capabilities": capabilities,
                        "stats": stats,
                    }
                except Exception as e:
                    logger.error(f"Error processing backend {backend_name}: {str(e)}")
                    backends_status[backend_name] = {
                        "backend_name": backend_name,
                        "is_available": False,
                        "capabilities": [],
                        "stats": {"error": str(e), "error_type": type(e).__name__},
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }

            # Update response
            response["backends"] = backends_status
            response["available_count"] = available_count
            response["duration_ms"] = (time.time() - start_time) * 1000

            return response
        except Exception as e:
            logger.error(f"Error handling storage status request: {str(e)}")
            return {
                "success": False,
                "operation_id": f"storage_status_{int(start_time * 1000)}",
                "error": str(e),
                "error_type": type(e).__name__,
                "backends": {},
                "available_count": 0,
                "total_count": 0,
                "duration_ms": (time.time() - start_time) * 1000,
            }

    async def handle_backend_status_request(self, backend_name: str):
        """
        Handle request for status of a specific storage backend.

        Args:
            backend_name: Name of the storage backend

        Returns:
            Dictionary with status of the specified backend
        """
        start_time = time.time()

        try:
            # Create default response structure to ensure consistency
            response = {
                "success": True,
                "operation_id": f"backend_status_{int(start_time * 1000)}",
                "backend_name": backend_name,
                "is_available": False,
                "capabilities": [],
                "stats": None,
                "duration_ms": 0,
            }

            # Get backend model
            try:
                backend_model = self.storage_manager.get_model(backend_name)

                if not backend_model:
                    logger.warning(f"Storage backend '{backend_name}' not found")
                    response["error"] = f"Storage backend '{backend_name}' not found"
                    response["error_type"] = "BackendNotFoundError"
                    response["success"] = False
                    response["duration_ms"] = (time.time() - start_time) * 1000
                    return response
            except Exception as e:
                logger.error(f"Error retrieving model for backend '{backend_name}': {str(e)}")
                response["error"] = f"Error retrieving model: {str(e)}"
                response["error_type"] = type(e).__name__
                response["success"] = False
                response["duration_ms"] = (time.time() - start_time) * 1000
                return response

            # Get backend stats
            try:
                stats = backend_model.get_stats()
                response["stats"] = stats
            except Exception as e:
                logger.error(f"Error getting stats for backend '{backend_name}': {str(e)}")
                response["stats"] = {"error": str(e), "error_type": type(e).__name__}

            # Get backend capabilities
            try:
                capabilities = self._get_backend_capabilities(backend_name, backend_model)
                response["capabilities"] = capabilities
            except Exception as e:
                logger.error(f"Error getting capabilities for backend '{backend_name}': {str(e)}")
                # Keep default empty capabilities list

            # Update response fields
            response["is_available"] = True
            response["duration_ms"] = (time.time() - start_time) * 1000

            return response

        except Exception as e:
            logger.error(f"Unhandled error in backend_status for '{backend_name}': {str(e)}")
            return {
                "success": False,
                "operation_id": f"backend_status_{int(start_time * 1000)}",
                "backend_name": backend_name,
                "is_available": False,
                "capabilities": [],
                "stats": None,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": (time.time() - start_time) * 1000,
            }

    async def handle_transfer_request(self, request: StorageTransferRequest):
        """
        Handle request to transfer content between storage backends.

        Args:
            request: Transfer request parameters

        Returns:
            Dictionary with transfer operation result
        """
        start_time = time.time()

        try:
            # Initialize default response
            result = {
                "success": False,
                "operation_id": f"transfer_{int(start_time * 1000)}",
                "source_backend": request.source_backend,
                "target_backend": request.target_backend,
                "content_id": request.content_id,
                "duration_ms": 0,
            }

            # Validate source backend
            try:
                source_backend = self.storage_manager.get_model(request.source_backend)
                if not source_backend:
                    logger.warning(f"Source backend '{request.source_backend}' not found")
                    result["error"] = f"Source backend '{request.source_backend}' not found"
                    result["error_type"] = "BackendNotFoundError"
                    result["duration_ms"] = (time.time() - start_time) * 1000
                    return result
            except Exception as e:
                logger.error(f"Error accessing source backend '{request.source_backend}': {str(e)}")
                result["error"] = f"Error accessing source backend: {str(e)}"
                result["error_type"] = type(e).__name__
                result["duration_ms"] = (time.time() - start_time) * 1000
                return result

            # Validate target backend
            try:
                target_backend = self.storage_manager.get_model(request.target_backend)
                if not target_backend:
                    logger.warning(f"Target backend '{request.target_backend}' not found")
                    result["error"] = f"Target backend '{request.target_backend}' not found"
                    result["error_type"] = "BackendNotFoundError"
                    result["duration_ms"] = (time.time() - start_time) * 1000
                    return result
            except Exception as e:
                logger.error(f"Error accessing target backend '{request.target_backend}': {str(e)}")
                result["error"] = f"Error accessing target backend: {str(e)}"
                result["error_type"] = type(e).__name__
                result["duration_ms"] = (time.time() - start_time) * 1000
                return result

            # Check if storage bridge is available
            storage_bridge_available = False
            try:
                storage_bridge_available = (
                    hasattr(self.storage_manager, "storage_bridge")
                    and self.storage_manager.storage_bridge is not None
                )
            except Exception as e:
                logger.error(f"Error checking storage bridge: {str(e)}")

            # Delegate to storage bridge for transfer
            if storage_bridge_available:
                try:
                    bridge_result = self.storage_manager.storage_bridge.transfer_content(
                        request.source_backend,
                        request.target_backend,
                        request.content_id,
                        target_options=request.options,
                    )
                    # Update our result with bridge result
                    result.update(bridge_result)

                except Exception as e:
                    logger.error(f"Error using storage bridge for transfer: {str(e)}")
                    result["error"] = f"Storage bridge transfer failed: {str(e)}"
                    result["error_type"] = type(e).__name__
                    result["duration_ms"] = (time.time() - start_time) * 1000
                    return result
            else:
                # If no storage bridge, use a basic implementation
                logger.info("Storage bridge not available, using basic transfer implementation")

                # Get content from source backend
                try:
                    source_method = self._get_backend_method(request.source_backend, "get_content")
                    if not source_method:
                        result["error"] = (
                            f"Source backend '{request.source_backend}' does not support content retrieval"
                        )
                        result["error_type"] = "UnsupportedOperationError"
                        result["duration_ms"] = (time.time() - start_time) * 1000
                        return result

                    source_result = source_method(request.content_id)
                    if not source_result.get("success", False):
                        result["error"] = (
                            f"Failed to retrieve content from source backend: {source_result.get('error', 'Unknown error')}"
                        )
                        result["error_type"] = source_result.get(
                            "error_type", "ContentRetrievalError"
                        )
                        result["duration_ms"] = (time.time() - start_time) * 1000
                        return result

                except Exception as e:
                    logger.error(f"Error retrieving content from source backend: {str(e)}")
                    result["error"] = f"Error retrieving content: {str(e)}"
                    result["error_type"] = type(e).__name__
                    result["duration_ms"] = (time.time() - start_time) * 1000
                    return result

                # Get content from source result
                try:
                    content = source_result.get("content")
                    if not content:
                        result["error"] = "Source backend returned empty content"
                        result["error_type"] = "ContentRetrievalError"
                        result["duration_ms"] = (time.time() - start_time) * 1000
                        return result

                    result["source_location"] = source_result.get("location")
                except Exception as e:
                    logger.error(f"Error processing source result: {str(e)}")
                    result["error"] = f"Error processing source result: {str(e)}"
                    result["error_type"] = type(e).__name__
                    result["duration_ms"] = (time.time() - start_time) * 1000
                    return result

                # Put content in target backend
                try:
                    target_method = self._get_backend_method(request.target_backend, "put_content")
                    if not target_method:
                        result["error"] = (
                            f"Target backend '{request.target_backend}' does not support content storage"
                        )
                        result["error_type"] = "UnsupportedOperationError"
                        result["duration_ms"] = (time.time() - start_time) * 1000
                        return result

                    target_result = target_method(request.content_id, content, request.options)
                    if not target_result.get("success", False):
                        result["error"] = (
                            f"Failed to store content in target backend: {target_result.get('error', 'Unknown error')}"
                        )
                        result["error_type"] = target_result.get(
                            "error_type", "ContentStorageError"
                        )
                        result["duration_ms"] = (time.time() - start_time) * 1000
                        return result

                    result["target_location"] = target_result.get("location")
                except Exception as e:
                    logger.error(f"Error storing content in target backend: {str(e)}")
                    result["error"] = f"Error storing content: {str(e)}"
                    result["error_type"] = type(e).__name__
                    result["duration_ms"] = (time.time() - start_time) * 1000
                    return result

                # Set bytes transferred
                try:
                    result["bytes_transferred"] = (
                        len(content) if isinstance(content, (bytes, bytearray)) else None
                    )
                except Exception as e:
                    logger.warning(f"Error calculating content size: {str(e)}")
                    # Not critical, continue

                # Mark as success
                result["success"] = True

            # Add duration
            result["duration_ms"] = (time.time() - start_time) * 1000

            return result

        except Exception as e:
            logger.error(f"Unhandled error in content transfer: {str(e)}")
            return {
                "success": False,
                "operation_id": f"transfer_{int(start_time * 1000)}",
                "error": str(e),
                "error_type": type(e).__name__,
                "source_backend": request.source_backend if request else "unknown",
                "target_backend": request.target_backend if request else "unknown",
                "content_id": request.content_id if request else "unknown",
                "duration_ms": (time.time() - start_time) * 1000,
            }

    async def handle_verify_request(
        self,
        content_id: str = Body(..., embed=True),
        backends: List[str] = Body(None, embed=True),
    ):
        """
        Handle request to verify content across storage backends.

        Args:
            content_id: Content identifier to verify
            backends: Optional list of backends to check (defaults to all)

        Returns:
            Dictionary with verification results
        """
        start_time = time.time()

        # Use all available backends if not specified
        if not backends:
            available_backends = self.storage_manager.get_available_backends()
            backends = [name for name, available in available_backends.items() if available]

        # Verify content in each backend
        verification_results = {}

        for backend_name in backends:
            backend_model = self.storage_manager.get_model(backend_name)
            if not backend_model:
                verification_results[backend_name] = {
                    "success": False,
                    "error": f"Backend '{backend_name}' not found",
                    "error_type": "BackendNotFoundError",
                }
                continue

            # Get verification method for backend
            verify_method = self._get_backend_method(backend_name, "verify_content")
            if verify_method:
                result = verify_method(content_id)
                verification_results[backend_name] = result
            else:
                # If no verification method, try to get content
                get_method = self._get_backend_method(backend_name, "get_content")
                if get_method:
                    result = get_method(content_id)
                    verification_results[backend_name] = {
                        "success": result.get("success", False),
                        "has_content": result.get("success", False),
                        "error": result.get("error"),
                        "error_type": result.get("error_type"),
                    }
                else:
                    verification_results[backend_name] = {
                        "success": False,
                        "error": f"Backend '{backend_name}' does not support content verification or retrieval",
                        "error_type": "UnsupportedOperationError",
                    }

        # Create aggregate result
        verified_backends = [
            name for name, result in verification_results.items() if result.get("success", False)
        ]

        response = {
            "success": len(verified_backends) > 0,
            "operation_id": f"verify_{int(start_time * 1000)}",
            "content_id": content_id,
            "verified_backends": verified_backends,
            "total_backends_checked": len(backends),
            "verification_results": verification_results,
            "duration_ms": (time.time() - start_time) * 1000,
        }

        return response

    async def handle_migration_request(self, request: ContentMigrationRequest):
        """
        Handle request to migrate content between storage backends.

        Args:
            request: Migration request parameters

        Returns:
            Dictionary with migration operation results
        """
        start_time = time.time()

        # Validate source backend
        source_backend = self.storage_manager.get_model(request.source_backend)
        if not source_backend:
            mcp_error_handling.raise_http_exception(
                code="CONTENT_NOT_FOUND",
                message_override=f"Source backend '{request.source_backend}' not found",
                details={"backend_name": request.source_backend},
                endpoint="/storage/migrate",
                doc_category="storage"
            )

        # Validate target backend
        target_backend = self.storage_manager.get_model(request.target_backend)
        if not target_backend:
            mcp_error_handling.raise_http_exception(
                code="CONTENT_NOT_FOUND",
                message_override=f"Target backend '{request.target_backend}' not found",
                details={"backend_name": request.target_backend},
                endpoint="/storage/migrate",
                doc_category="storage"
            )

        # Initialize result
        result = {
            "success": True,
            "operation_id": f"migrate_{int(start_time * 1000)}",
            "source_backend": request.source_backend,
            "target_backend": request.target_backend,
            "content_count": len(request.content_ids),
            "successful_count": 0,
            "failed_count": 0,
            "total_bytes_transferred": 0,
            "results": {},
        }

        # Check if storage bridge is available
        storage_bridge = None
        if hasattr(self.storage_manager, "storage_bridge"):
            storage_bridge = self.storage_manager.storage_bridge

        # Process each content ID
        for content_id in request.content_ids:
            # Transfer content
            transfer_result = None

            if storage_bridge:
                # Use storage bridge for transfer
                transfer_result = storage_bridge.transfer_content(
                    request.source_backend,
                    request.target_backend,
                    content_id,
                    source_options=request.options,
                    target_options=request.options,
                )
            else:
                # Fallback to basic implementation
                transfer_result = self._transfer_content(
                    request.source_backend,
                    request.target_backend,
                    content_id,
                    request.options,
                )

            result["results"][content_id] = transfer_result

            # Update success/failure counts
            if transfer_result.get("success", False):
                result["successful_count"] += 1

                # Add bytes transferred
                bytes_transferred = transfer_result.get("bytes_transferred", 0)
                if bytes_transferred:
                    result["total_bytes_transferred"] += bytes_transferred

                # Verify integrity if requested
                if request.verify_integrity:
                    if storage_bridge:
                        # Use storage bridge for verification
                        verify_result = storage_bridge.verify_content(
                            content_id,
                            backends=[request.target_backend],
                            reference_backend=request.source_backend,
                        )

                        # Add verification result
                        result["results"][content_id]["verify_result"] = verify_result

                        # Check if verification failed
                        if not verify_result.get("success", False):
                            # Mark transfer as failed if verification failed
                            result["results"][content_id]["success"] = False
                            result["results"][content_id]["error"] = "Verification failed"
                            result["results"][content_id]["error_type"] = "VerificationError"

                            # Update counts
                            result["successful_count"] -= 1
                            result["failed_count"] += 1
                    else:
                        # Skip verification if storage bridge not available
                        result["results"][content_id]["verify_result"] = {
                            "success": False,
                            "error": "Storage bridge not available for verification",
                            "error_type": "StorageBridgeNotAvailable",
                        }

                # Delete from source if requested
                if request.delete_source and transfer_result.get("success", True):
                    if hasattr(source_backend, "delete_object"):
                        delete_result = source_backend.delete_object(content_id)
                        result["results"][content_id]["delete_result"] = delete_result
                    elif hasattr(source_backend, "remove"):
                        delete_result = source_backend.remove(content_id)
                        result["results"][content_id]["delete_result"] = delete_result
                    else:
                        result["results"][content_id]["delete_result"] = {
                            "success": False,
                            "error": f"Source backend '{request.source_backend}' does not support content deletion",
                            "error_type": "UnsupportedOperationError",
                        }
            else:
                result["failed_count"] += 1

        # Update overall success
        result["success"] = result["failed_count"] == 0

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    def _transfer_content(
        self,
        source_backend: str,
        target_backend: str,
        content_id: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Basic implementation for transferring content between backends.

        Args:
            source_backend: Source backend name
            target_backend: Target backend name
            content_id: Content ID to transfer
            options: Backend-specific options

        Returns:
            Dictionary with transfer result
        """
        start_time = time.time()

        result = {
            "success": False,
            "operation": "transfer_content",
            "source_backend": source_backend,
            "target_backend": target_backend,
            "content_id": content_id,
            "timestamp": time.time(),
        }

        try:
            # Get content from source backend
            source_model = self.storage_manager.get_model(source_backend)
            if not source_model:
                result["error"] = f"Source backend '{source_backend}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            target_model = self.storage_manager.get_model(target_backend)
            if not target_model:
                result["error"] = f"Target backend '{target_backend}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            # Get content from source
            source_method = self._get_backend_method(source_backend, "get_content")
            if not source_method:
                result["error"] = (
                    f"Source backend '{source_backend}' does not support content retrieval"
                )
                result["error_type"] = "UnsupportedOperationError"
                return result

            source_result = source_method(content_id)
            if not source_result.get("success", False):
                result["error"] = source_result.get(
                    "error", f"Failed to retrieve content from {source_backend}"
                )
                result["error_type"] = source_result.get("error_type", "ContentRetrievalError")
                return result

            content = source_result.get("content")
            if not content:
                result["error"] = f"No content returned from source backend '{source_backend}'"
                result["error_type"] = "ContentRetrievalError"
                return result

            # Store in target backend
            target_method = self._get_backend_method(target_backend, "put_content")
            if not target_method:
                result["error"] = (
                    f"Target backend '{target_backend}' does not support content storage"
                )
                result["error_type"] = "UnsupportedOperationError"
                return result

            target_result = target_method(content_id, content, options)
            if not target_result.get("success", False):
                result["error"] = target_result.get(
                    "error", f"Failed to store content in {target_backend}"
                )
                result["error_type"] = target_result.get("error_type", "ContentStorageError")
                return result

            # Transfer successful
            result["success"] = True
            result["source_location"] = source_result.get("location")
            result["target_location"] = target_result.get("location")
            result["bytes_transferred"] = (
                len(content) if isinstance(content, (bytes, bytearray)) else None
            )

        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error transferring content: {e}")

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    def _get_backend_capabilities(self, backend_name: str, backend_model) -> List[str]:
        """
        Get capabilities of a storage backend.

        Args:
            backend_name: Name of the storage backend
            backend_model: Model instance for the backend

        Returns:
            List of capabilities supported by the backend
        """
        # Generic capabilities based on method presence
        capabilities = []

        try:
            # Check for common methods
            common_methods = {
                "upload_file": "file_upload",
                "download_file": "file_download",
                "get_content": "content_retrieval",
                "put_content": "content_storage",
                "list_objects": "object_listing",
                "delete_object": "object_deletion",
                "verify_content": "content_verification",
            }

            for method_name, capability in common_methods.items():
                try:
                    if hasattr(backend_model, method_name):
                        capabilities.append(capability)
                except Exception as e:
                    logger.debug(f"Error checking method {method_name} on {backend_name}: {str(e)}")

            # Backend-specific capabilities
            if backend_name == "s3":
                capabilities.extend(["bucket_management", "multipart_upload"])
            elif backend_name == "storacha":
                capabilities.extend(["car_packaging", "space_management"])
            elif backend_name == "huggingface":
                capabilities.extend(["model_registry", "dataset_management"])
            elif backend_name == "filecoin":
                capabilities.extend(["deal_making", "retrieval_market"])
            elif backend_name == "lassie":
                capabilities.extend(["content_discovery", "retrieval_optimization"])

            return capabilities
        except Exception as e:
            logger.error(f"Error determining capabilities for {backend_name}: {str(e)}")
            return []

    def _get_backend_method(self, backend_name: str, method_name: str):
        """
        Get a method from a backend if it exists.

        This function provides robust error handling when attempting to access
        backend methods, with specific error detection for common issues.

        Args:
            backend_name: Name of the storage backend
            method_name: Name of the method to get

        Returns:
            Method if it exists, None otherwise
        """
        # Verify storage_manager is available
        if not hasattr(self, "storage_manager") or self.storage_manager is None:
            logger.error("Storage manager is not available")
            return None

        try:
            # Get backend model with error handling
            try:
                backend_model = self.storage_manager.get_model(backend_name)
            except AttributeError:
                logger.error("Storage manager doesn't have get_model method")
                return None
            except Exception as e:
                logger.error(f"Error calling get_model on storage manager: {str(e)}")
                return None

            # Check if backend exists
            if not backend_model:
                logger.debug(f"Backend model not found: {backend_name}")
                return None

            # Validate method_name parameter
            if not method_name or not isinstance(method_name, str):
                logger.error(f"Invalid method name: {method_name}")
                return None

            # Get method from backend model
            try:
                method = getattr(backend_model, method_name, None)

                # Check if method exists and is callable
                if method is None:
                    logger.debug(f"Method {method_name} not found on {backend_name}")
                    return None

                if not callable(method):
                    logger.debug(
                        f"Method {method_name} exists on {backend_name} but is not callable"
                    )
                    return None

                # Method exists and is callable
                return method

            except AttributeError as e:
                logger.error(f"AttributeError accessing {method_name} on {backend_name}: {str(e)}")
                return None
            except Exception as e:
                logger.error(
                    f"Error accessing method {method_name} on {backend_name}: {type(e).__name__}: {str(e)}"
                )
                return None

        except Exception as e:
            # Catch-all for any unexpected errors
            logger.error(
                f"Unexpected error in _get_backend_method for {backend_name}.{method_name}: {type(e).__name__}: {str(e)}"
            )
            return None

    async def handle_replication_policy_request(self, request: ReplicationPolicyRequest):
        """
        Handle request to apply a replication policy to content.

        The policy specifies how content should be distributed across backends
        based on various criteria like content type, size, and importance.

        Args:
            request: Replication policy request parameters

        Returns:
            Dictionary with replication policy application result
        """
        start_time = time.time()

        # Check if storage bridge is available
        if not hasattr(self.storage_manager, "storage_bridge"):
            mcp_error_handling.raise_http_exception(
                code="EXTENSION_NOT_AVAILABLE",
                message_override="Storage bridge not available for policy application",
                details={"operation": "apply_replication_policy", "content_id": request.content_id},
                endpoint="/storage/apply-policy",
                doc_category="storage"
            )

        # Apply the policy using storage bridge
        result = self.storage_manager.storage_bridge.apply_replication_policy(
            request.content_id, request.policy
        )

        # Add operation ID
        result["operation_id"] = f"policy_{int(start_time * 1000)}"

        # Ensure duration is set
        if "duration_ms" not in result:
            result["duration_ms"] = (time.time() - start_time) * 1000

        return result
