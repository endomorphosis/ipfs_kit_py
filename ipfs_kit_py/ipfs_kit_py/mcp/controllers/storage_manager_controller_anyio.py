"""
AnyIO-compatible Storage Manager Controller for MCP.

This module provides an asynchronous implementation of the StorageManagerController
using the AnyIO library for compatibility with different async backends.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Union
import anyio

from ipfs_kit_py.mcp.controllers.storage_manager_controller import (
    StorageManagerController,
    OperationResponse,
    BackendStatusResponse,
    AllBackendsStatusResponse,
    StorageTransferRequest,
    StorageTransferResponse,
    ContentMigrationRequest,
    ContentMigrationResponse,
    ReplicationPolicyRequest,
    ReplicationPolicyResponse,
)

# Configure logger
logger = logging.getLogger(__name__)


class StorageManagerControllerAnyIO(StorageManagerController):
    """
    AnyIO-compatible implementation of the Storage Manager Controller.
    
    This class extends the base StorageManagerController with AnyIO-specific
    asynchronous functionality for better compatibility with different async backends.
    """
    
    async def shutdown(self):
        """
        Safely shut down the Storage Manager Controller using AnyIO.
        
        This method ensures proper cleanup of all storage-related resources,
        including closing active transfers and connections to storage backends.
        """
        logger.info("Storage Manager Controller AnyIO shutdown initiated")
        
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
                    # Add specific cancellation logic here
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
                # Use to_thread.run_sync for anyio >= 3.0, otherwise use run_sync_in_worker_thread
                try:
                    await anyio.to_thread.run_sync(self.storage_manager.reset)
                except AttributeError:
                    await anyio.run_sync_in_worker_thread(self.storage_manager.reset)
            except Exception as e:
                error_msg = f"Error resetting storage models: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # 3. Clean up each storage model individually
        if hasattr(self.storage_manager, "get_all_models"):
            try:
                # Use appropriate anyio method based on version
                try:
                    models = await anyio.to_thread.run_sync(self.storage_manager.get_all_models)
                except AttributeError:
                    models = await anyio.run_sync_in_worker_thread(self.storage_manager.get_all_models)
                logger.info(f"Shutting down {len(models)} storage models")
                
                for model_name, model in models.items():
                    try:
                        # Try to call shutdown method if it exists
                        if hasattr(model, "shutdown"):
                            logger.debug(f"Shutting down {model_name} model")
                            if hasattr(model.shutdown, "__await__"):
                                await model.shutdown()
                            else:
                                try:
                                    await anyio.to_thread.run_sync(model.shutdown)
                                except AttributeError:
                                    await anyio.run_sync_in_worker_thread(model.shutdown)
                        elif hasattr(model, "close"):
                            logger.debug(f"Closing {model_name} model")
                            if hasattr(model.close, "__await__"):
                                await model.close()
                            else:
                                try:
                                    await anyio.to_thread.run_sync(model.close)
                                except AttributeError:
                                    await anyio.run_sync_in_worker_thread(model.close)
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
                    if hasattr(bridge.shutdown, "__await__"):
                        await bridge.shutdown()
                    else:
                        try:
                            await anyio.to_thread.run_sync(bridge.shutdown)
                        except AttributeError:
                            await anyio.run_sync_in_worker_thread(bridge.shutdown)
                elif hasattr(bridge, "close"):
                    logger.info("Closing storage bridge")
                    if hasattr(bridge.close, "__await__"):
                        await bridge.close()
                    else:
                        try:
                            await anyio.to_thread.run_sync(bridge.close)
                        except AttributeError:
                            await anyio.run_sync_in_worker_thread(bridge.close)
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
                f"Storage Manager Controller AnyIO shutdown completed with {len(errors)} errors"
            )
        else:
            logger.info("Storage Manager Controller AnyIO shutdown completed successfully")
    
    # Override methods from the base class to use AnyIO's async functionality
    
    async def handle_status_request(self):
        """
        Handle request for status of all storage backends (AnyIO version).
        
        Returns:
            Dictionary with status of all storage backends
        """
        start_time = time.time()
        
        try:
            # Create default response structure first
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
                # Use appropriate anyio method based on version
                try:
                    available_backends = await anyio.to_thread.run_sync(
                        self.storage_manager.get_available_backends
                    )
                except AttributeError:
                    available_backends = await anyio.run_sync_in_worker_thread(
                        self.storage_manager.get_available_backends
                    )
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
                try:
                    models = await anyio.to_thread.run_sync(self.storage_manager.get_all_models)
                except AttributeError:
                    models = await anyio.run_sync_in_worker_thread(self.storage_manager.get_all_models)
                models = models or {}
            except Exception as e:
                logger.error(f"Error getting backend models: {str(e)}")
                models = {}
            
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
                            if hasattr(backend_model.get_stats, "__await__"):
                                stats = await backend_model.get_stats()
                            else:
                                try:
                                    stats = await anyio.to_thread.run_sync(backend_model.get_stats)
                                except AttributeError:
                                    stats = await anyio.run_sync_in_worker_thread(backend_model.get_stats)
                    except Exception as e:
                        logger.error(f"Error getting stats for {backend_name}: {str(e)}")
                        stats = {"error": str(e), "error_type": type(e).__name__}
                    
                    # Get capabilities
                    capabilities = []
                    try:
                        if backend_model:
                            try:
                                capabilities = await anyio.to_thread.run_sync(
                                    self._get_backend_capabilities, backend_name, backend_model
                                )
                            except AttributeError:
                                capabilities = await anyio.run_sync_in_worker_thread(
                                    self._get_backend_capabilities, backend_name, backend_model
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
        Handle request for status of a specific storage backend (AnyIO version).
        
        Args:
            backend_name: Name of the storage backend
            
        Returns:
            Dictionary with status of the specified backend
        """
        # AnyIO implementation of backend status request
        # This would be similar to the base class but using anyio.run_sync_in_worker_thread 
        # for blocking operations
        result = await super().handle_backend_status_request(backend_name)
        return result
    
    async def handle_transfer_request(self, request: StorageTransferRequest):
        """
        Handle request to transfer content between storage backends (AnyIO version).
        
        Args:
            request: Transfer request parameters
            
        Returns:
            Dictionary with transfer operation result
        """
        # AnyIO implementation of transfer request
        # This would be similar to the base class but using anyio.run_sync_in_worker_thread
        # for blocking operations
        result = await super().handle_transfer_request(request)
        return result
    
    async def handle_verify_request(self, content_id: str, backends: Optional[List[str]] = None):
        """
        Handle request to verify content across storage backends (AnyIO version).
        
        Args:
            content_id: Content identifier to verify
            backends: Optional list of backends to check (defaults to all)
            
        Returns:
            Dictionary with verification results
        """
        # AnyIO implementation of verify request
        # This would be similar to the base class but using anyio.run_sync_in_worker_thread
        # for blocking operations
        result = await super().handle_verify_request(content_id, backends)
        return result
    
    async def handle_migration_request(self, request: ContentMigrationRequest):
        """
        Handle request to migrate content between storage backends (AnyIO version).
        
        Args:
            request: Migration request parameters
            
        Returns:
            Dictionary with migration operation results
        """
        # AnyIO implementation of migration request
        # This would be similar to the base class but using anyio.run_sync_in_worker_thread
        # for blocking operations
        result = await super().handle_migration_request(request)
        return result
    
    async def handle_replication_policy_request(self, request: ReplicationPolicyRequest):
        """
        Handle request to apply a replication policy to content (AnyIO version).
        
        Args:
            request: Replication policy request parameters
            
        Returns:
            Dictionary with replication policy application result
        """
        # AnyIO implementation of replication policy request
        # This would be similar to the base class but using anyio.run_sync_in_worker_thread
        # for blocking operations
        result = await super().handle_replication_policy_request(request)
        return result
