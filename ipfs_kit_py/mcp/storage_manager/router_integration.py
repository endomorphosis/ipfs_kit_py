"""
Storage Manager Router Integration

This module integrates the advanced content router with the UnifiedStorageManager
to enable intelligent content-aware backend selection.
"""

import time
import logging
from typing import Dict, List, Any, Optional, Union, BinaryIO, Tuple

from .storage_types import StorageBackendType, ContentReference
from .router import get_instance as get_basic_router
from .router.balanced import get_balanced_instance

# Configure logger
logger = logging.getLogger(__name__)


class RouterIntegration:
    """
    Integration between the storage manager and content router.
    
    This class bridges the UnifiedStorageManager with the intelligent
    content router to enable optimal backend selection.
    """
    
    def __init__(self, 
                 config: Optional[Dict[str, Any]] = None,
                 available_backends: Optional[List[StorageBackendType]] = None):
        """
        Initialize the router integration.
        
        Args:
            config: Router configuration
            available_backends: List of available backend types
        """
        self.config = config or {}
        self.available_backends = available_backends or []
        
        # Determine which router implementation to use
        router_type = self.config.get("router_type", "balanced")
        
        if router_type == "balanced":
            # Use the advanced balanced router
            self.router = get_balanced_instance(config, available_backends)
            logger.info("Using balanced router for optimal backend selection")
        else:
            # Use the basic router
            self.router = get_basic_router(config, available_backends)
            logger.info("Using basic router for backend selection")
    
    def select_backend(self, request_data: Dict[str, Any]) -> Tuple[Optional[StorageBackendType], str]:
        """
        Select the optimal backend for a storage request.
        
        Args:
            request_data: Dictionary with request data
            
        Returns:
            Tuple of (selected backend type, reason)
        """
        return self.router.select_backend(request_data)
    
    def update_available_backends(self, backends: List[StorageBackendType]):
        """
        Update the list of available backends.
        
        Args:
            backends: List of available backend types
        """
        self.available_backends = backends
        self.router.update_available_backends(backends)
    
    def record_operation_result(self, 
                               backend: StorageBackendType,
                               operation: str,
                               latency: float,
                               size: Optional[int] = None,
                               success: bool = True):
        """
        Record the result of a storage operation.
        
        Args:
            backend: Backend used
            operation: Operation type (store, retrieve, etc.)
            latency: Operation latency in seconds
            size: Size of data in bytes
            success: Whether operation was successful
        """
        # Check if router supports operation recording
        if hasattr(self.router, 'record_operation_result'):
            self.router.record_operation_result(
                backend=backend,
                operation=operation,
                latency=latency,
                size=size,
                success=success
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get router statistics.
        
        Returns:
            Dictionary of router statistics
        """
        return self.router.get_statistics()


# Helper function to create a router integration
def create_router_integration(
    config: Optional[Dict[str, Any]] = None,
    available_backends: Optional[List[StorageBackendType]] = None
) -> RouterIntegration:
    """
    Create a router integration instance.
    
    Args:
        config: Router configuration
        available_backends: List of available backend types
        
    Returns:
        RouterIntegration instance
    """
    return RouterIntegration(config, available_backends)


# Patch for UnifiedStorageManager integration
def patch_storage_manager(manager):
    """
    Patch the UnifiedStorageManager to use the router integration.
    
    This function modifies the _select_backend method of the UnifiedStorageManager
    to use our intelligent content router.
    
    Args:
        manager: UnifiedStorageManager instance to patch
    """
    # Get available backends from manager
    available_backends = list(manager.backends.keys())
    
    # Create router integration
    router_config = manager.config.get("router", {})
    router = create_router_integration(router_config, available_backends)
    
    # Save original method for reference
    original_select_backend = manager._select_backend
    
    # Define new method that uses the router
    def new_select_backend(self, data=None, content_type=None, size=None, preference=None):
        """Enhanced backend selection with intelligent routing."""
        # Create request data dictionary
        request_data = {
            "data": data,
            "content_type": content_type,
            "size": size,
            "preference": preference,
            "operation": "store",  # Default to store operation
            "options": {}
        }
        
        # Try to determine operation type
        stack = traceback.extract_stack()
        for frame in stack:
            if frame.name in ["store", "retrieve", "delete", "list_content"]:
                request_data["operation"] = frame.name
                break
        
        # Extract filename from data if it's a file-like object
        if hasattr(data, 'name'):
            request_data["filename"] = getattr(data, 'name', None)
        
        # Use router to select backend
        start_time = time.time()
        backend_type, reason = router.select_backend(request_data)
        decision_time = time.time() - start_time
        
        logger.info(f"Selected backend {backend_type.value if backend_type else 'None'} "
                   f"for {request_data['operation']} operation. Reason: {reason}. "
                   f"Decision took {decision_time*1000:.2f}ms")
        
        return backend_type, reason
    
    # Patch the manager's _select_backend method
    import types
    import traceback
    manager._select_backend = types.MethodType(new_select_backend, manager)
    
    # Store the router integration in the manager for later use
    manager._router_integration = router
    
    # Patch the store method to record operation results
    original_store = manager.store
    
    def new_store(self, data, backend_preference=None, content_type=None, 
                 metadata=None, container=None, path=None, content_id=None, options=None):
        """Enhanced store method with operation tracking."""
        start_time = time.time()
        result = original_store(data, backend_preference, content_type, metadata, 
                               container, path, content_id, options)
        end_time = time.time()
        
        # Record operation result if successful
        if result.get("success", False) and "backend" in result:
            try:
                backend_type = StorageBackendType.from_string(result["backend"])
                router.record_operation_result(
                    backend=backend_type,
                    operation="store",
                    latency=end_time - start_time,
                    size=result.get("size"),
                    success=True
                )
            except Exception as e:
                logger.warning(f"Failed to record operation result: {e}")
        
        return result
    
    # Patch the retrieve method to record operation results
    original_retrieve = manager.retrieve
    
    def new_retrieve(self, content_id, backend_preference=None, container=None, options=None):
        """Enhanced retrieve method with operation tracking."""
        start_time = time.time()
        result = original_retrieve(content_id, backend_preference, container, options)
        end_time = time.time()
        
        # Record operation result if successful
        if result.get("success", False) and "backend" in result:
            try:
                backend_type = StorageBackendType.from_string(result["backend"])
                
                # Estimate size if available
                size = None
                if "data" in result:
                    data = result["data"]
                    if isinstance(data, bytes):
                        size = len(data)
                    elif isinstance(data, str):
                        size = len(data.encode("utf-8"))
                
                router.record_operation_result(
                    backend=backend_type,
                    operation="retrieve",
                    latency=end_time - start_time,
                    size=size,
                    success=True
                )
            except Exception as e:
                logger.warning(f"Failed to record operation result: {e}")
        
        return result
    
    # Apply the patches
    manager.store = types.MethodType(new_store, manager)
    manager.retrieve = types.MethodType(new_retrieve, manager)
    
    # Add a method to get router statistics
    def get_router_statistics(self):
        """Get statistics from the content router."""
        if hasattr(self, '_router_integration'):
            return self._router_integration.get_statistics()
        return {"error": "Router integration not available"}
    
    manager.get_router_statistics = types.MethodType(get_router_statistics, manager)
    
    logger.info("Successfully patched UnifiedStorageManager with intelligent content router")
    
    return manager