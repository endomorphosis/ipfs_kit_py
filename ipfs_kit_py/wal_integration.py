# ipfs_kit_py/wal_integration.py

import os
import time
import uuid
import functools
import logging
from typing import Dict, Any, Optional, Callable, Union, TypeVar, List

from .storage_wal import (
    StorageWriteAheadLog, 
    BackendHealthMonitor, 
    OperationType, 
    OperationStatus, 
    BackendType
)

# Configure logging
logger = logging.getLogger(__name__)

# Type variables for generics
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

class WALIntegration:
    """
    Integration for the Write-Ahead Log (WAL) system with the high-level API.
    
    This class provides decorators to wrap API methods with WAL functionality.
    """
    
    def __init__(self, wal: Optional[StorageWriteAheadLog] = None, config: Dict[str, Any] = None):
        """
        Initialize the WAL integration.
        
        Args:
            wal: Optional existing WAL instance to use
            config: Configuration for WAL if creating a new instance
        """
        self.wal = wal
        self.config = config or {}
        
        if self.wal is None:
            # Create WAL instance if not provided
            base_path = self.config.get("base_path", "~/.ipfs_kit/wal")
            partition_size = self.config.get("partition_size", 1000)
            max_retries = self.config.get("max_retries", 5)
            retry_delay = self.config.get("retry_delay", 60)
            archive_completed = self.config.get("archive_completed", True)
            process_interval = self.config.get("processing_interval", 5)
            
            # Create health monitor if enabled
            health_monitor = None
            if self.config.get("enable_health_monitoring", True):
                health_check_interval = self.config.get("health_check_interval", 60)
                health_monitor = BackendHealthMonitor(
                    check_interval=health_check_interval,
                    backends=self.config.get("monitored_backends")
                )
            
            # Create WAL instance
            self.wal = StorageWriteAheadLog(
                base_path=base_path,
                partition_size=partition_size,
                max_retries=max_retries,
                retry_delay=retry_delay,
                archive_completed=archive_completed,
                process_interval=process_interval,
                health_monitor=health_monitor
            )
            
        # Track operations by method
        self.method_operations = {}
    
    def with_wal(self, operation_type: Union[str, OperationType], 
                backend: Union[str, BackendType],
                wait_for_completion: bool = False,
                max_wait_time: int = 60) -> Callable[[F], F]:
        """
        Decorator to wrap an API method with WAL functionality.
        
        Args:
            operation_type: Type of operation (add, pin, etc.)
            backend: Storage backend (ipfs, s3, etc.)
            wait_for_completion: Whether to wait for the operation to complete
            max_wait_time: Maximum time to wait in seconds
            
        Returns:
            Decorated method with WAL integration
        """
        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Skip WAL if disabled in the call
                skip_wal = kwargs.pop('skip_wal', False)
                if skip_wal:
                    return func(*args, **kwargs)
                
                # Get the function name safely, handling mocks
                try:
                    method_name = func.__name__
                except (AttributeError, TypeError):
                    # For mocks or objects without __name__
                    method_name = "unknown_method"
                
                # Extract parameters for WAL
                parameters = self._extract_parameters(method_name, args, kwargs)
                
                # Add operation to WAL
                operation_result = self.wal.add_operation(
                    operation_type=operation_type,
                    backend=backend,
                    parameters=parameters
                )
                
                operation_id = operation_result["operation_id"]
                
                # Store operation in method tracking
                if method_name not in self.method_operations:
                    self.method_operations[method_name] = []
                self.method_operations[method_name].append(operation_id)
                
                # Execute the operation if the backend is healthy
                # or if wait_for_completion is True
                if (self.wal.health_monitor and self.wal.health_monitor.is_backend_available(backend)) or wait_for_completion:
                    try:
                        # Call the original function
                        result = func(*args, **kwargs)
                        
                        # Update operation status
                        completed_at = int(time.time() * 1000)
                        success = result.get("success", False) if isinstance(result, dict) else True
                        
                        if success:
                            # Operation succeeded
                            self.wal.update_operation_status(
                                operation_id,
                                OperationStatus.COMPLETED,
                                {
                                    "updated_at": completed_at,
                                    "completed_at": completed_at,
                                    "result": result if isinstance(result, dict) else {"value": str(result)}
                                }
                            )
                        else:
                            # Operation failed
                            self.wal.update_operation_status(
                                operation_id,
                                OperationStatus.FAILED,
                                {
                                    "updated_at": completed_at,
                                    "error": result.get("error", "Unknown error"),
                                    "error_type": result.get("error_type", "unknown_error")
                                }
                            )
                            
                        # Add WAL metadata to result
                        if isinstance(result, dict):
                            result["wal_operation_id"] = operation_id
                            result["wal_status"] = "completed" if success else "failed"
                        else:
                            # If result is not a dict, wrap it
                            result = {
                                "success": success,
                                "result": result,
                                "wal_operation_id": operation_id,
                                "wal_status": "completed" if success else "failed"
                            }
                        
                        return result
                    except Exception as e:
                        # Operation failed with exception
                        error_message = str(e)
                        error_type = type(e).__name__
                        
                        # Update operation status
                        self.wal.update_operation_status(
                            operation_id,
                            OperationStatus.FAILED,
                            {
                                "updated_at": int(time.time() * 1000),
                                "error": error_message,
                                "error_type": error_type
                            }
                        )
                        
                        # Re-raise the exception
                        raise
                
                # If wait_for_completion is True, wait for the operation to complete
                if wait_for_completion:
                    return self.wait_for_operation(operation_id, max_wait_time)
                
                # Return the operation result
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "status": "pending",
                    "message": "Operation recorded in WAL"
                }
                
            return wrapper
        
        return decorator
    
    def _extract_parameters(self, method_name: str, args: tuple, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract parameters from method arguments.
        
        Args:
            method_name: Name of the method
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Dictionary of parameters
        """
        parameters = {}
        
        # Handle method_name from a real function or a mock
        if hasattr(method_name, '__name__'):
            method_name = method_name.__name__
        
        # Add all keyword arguments
        parameters.update(kwargs)
        
        # Make sure args is non-empty before trying to access elements
        if args:
            # Add first argument if it's a string or path-like (likely a file path)
            if len(args) > 1 and isinstance(args[1], (str, os.PathLike)):
                parameters["path"] = str(args[1])
            
            # Add CID if present
            if "cid" in kwargs:
                parameters["cid"] = kwargs["cid"]
            elif len(args) > 1 and isinstance(args[1], str) and args[1].startswith("Qm"):
                parameters["cid"] = args[1]
                
            # Add content if small enough
            content_arg = None
            if "content" in kwargs:
                content_arg = kwargs["content"]
            elif len(args) > 1 and isinstance(args[1], (bytes, bytearray)):
                content_arg = args[1]
                
            if content_arg is not None:
                # Only store small content samples in WAL
                if isinstance(content_arg, (bytes, bytearray)) and len(content_arg) < 100:
                    parameters["content_sample"] = content_arg.decode('utf-8', errors='replace')
                elif isinstance(content_arg, str) and len(content_arg) < 100:
                    parameters["content_sample"] = content_arg
        
        # Add metadata about method
        parameters["method"] = method_name
        parameters["timestamp"] = time.time()
        
        return parameters

    def wait_for_operation(self, operation_id: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Wait for an operation to complete.
        
        Args:
            operation_id: ID of the operation to wait for
            timeout: Maximum time to wait in seconds
            
        Returns:
            Result of the operation
        """
        return self.wal.wait_for_operation(operation_id, timeout)
    
    def get_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an operation by ID.
        
        Args:
            operation_id: ID of the operation to get
            
        Returns:
            Operation information or None if not found
        """
        return self.wal.get_operation(operation_id)
    
    def get_operations_by_status(self, status: Union[str, OperationStatus], 
                                limit: int = None) -> List[Dict[str, Any]]:
        """
        Get operations with a specific status.
        
        Args:
            status: Status to filter by
            limit: Maximum number of operations to return
            
        Returns:
            List of operations with the specified status
        """
        return self.wal.get_operations_by_status(status, limit)
    
    def get_all_operations(self) -> List[Dict[str, Any]]:
        """
        Get all operations in the WAL.
        
        Returns:
            List of all operations
        """
        return self.wal.get_all_operations()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the WAL.
        
        Returns:
            Dictionary with statistics
        """
        return self.wal.get_statistics()
    
    def get_backend_health(self, backend: str = None) -> Dict[str, Any]:
        """
        Get the health status of backends.
        
        Args:
            backend: Backend to get health for, or None for all
            
        Returns:
            Dictionary with backend health information
        """
        if self.wal.health_monitor:
            return self.wal.health_monitor.get_status(backend)
        else:
            return {"error": "Health monitoring not enabled"}
    
    def cleanup(self, max_age_days: int = 30) -> Dict[str, Any]:
        """
        Clean up old operations.
        
        Args:
            max_age_days: Maximum age in days for operations to keep
            
        Returns:
            Dictionary with cleanup results
        """
        return self.wal.cleanup(max_age_days)
    
    def close(self):
        """Close the WAL integration and clean up resources."""
        if self.wal:
            self.wal.close()


# Decorator factory for simpler usage
def with_wal(operation_type: Union[str, OperationType], 
            backend: Union[str, BackendType],
            wal_integration: Optional[WALIntegration] = None,
            wait_for_completion: bool = False,
            max_wait_time: int = 60) -> Callable[[F], F]:
    """
    Decorator factory for WAL integration.
    
    This is a convenience function for using WAL decorators without
    having to directly access the WALIntegration instance.
    
    Args:
        operation_type: Type of operation (add, pin, etc.)
        backend: Storage backend (ipfs, s3, etc.)
        wal_integration: WAL integration instance (can be None for testing)
        wait_for_completion: Whether to wait for the operation to complete
        max_wait_time: Maximum time to wait in seconds
        
    Returns:
        Decorator for WAL integration
    """
    # Handle case where wal_integration is missing (for tests)
    if wal_integration is None:
        # For testing purposes, just return a simple decorator that passes through
        def simple_decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return simple_decorator
    
    # Normal case: delegate to the WAL integration instance
    return wal_integration.with_wal(
        operation_type=operation_type,
        backend=backend,
        wait_for_completion=wait_for_completion,
        max_wait_time=max_wait_time
    )