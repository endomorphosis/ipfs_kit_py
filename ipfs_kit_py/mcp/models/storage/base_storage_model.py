"""
BaseStorageModel module for MCP server.

This module provides the base class for all storage backend models in the MCP server.
It defines a standard interface and common functionality for all storage backends,
ensuring consistent behavior and error handling across different implementations.
"""

import time
import uuid
import logging
import os
from typing import Any, Dict, List, Optional, Union

# Configure logger
logger = logging.getLogger(__name__)

class BaseStorageModel:
    """
    Base model for storage backend operations.
    
    This class provides a foundation for all storage backend models, including
    common functionality like statistics tracking, error handling, and operation
    result formatting. All specific storage backend models should inherit from
    this class and implement their specific operations.
    """
    
    def __init__(self, 
                 kit_instance: Any = None, 
                 cache_manager: Any = None, 
                 credential_manager: Any = None):
        """
        Initialize storage model with dependencies.
        
        Args:
            kit_instance: Storage backend kit instance (e.g., s3_kit, huggingface_kit)
            cache_manager: Cache manager for caching operations
            credential_manager: Credential manager for handling authentication
        """
        self.kit = kit_instance
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager
        self.backend_name = self._get_backend_name()
        self.operation_stats = self._initialize_stats()
        logger.info(f"{self.backend_name} Model initialized")
    
    def _get_backend_name(self) -> str:
        """
        Get the name of the storage backend.
        
        This method should be overridden by subclasses to return their specific backend name.
        
        Returns:
            str: Name of the storage backend
        """
        # Default implementation uses class name without "Model" suffix
        class_name = self.__class__.__name__
        if class_name.endswith("Model"):
            return class_name[:-5]
        return class_name
    
    def _initialize_stats(self) -> Dict[str, Any]:
        """
        Initialize operation statistics tracking.
        
        Returns:
            Dict: Dictionary with initial statistics values
        """
        return {
            "upload_count": 0,
            "download_count": 0,
            "list_count": 0,
            "delete_count": 0,
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
            "bytes_uploaded": 0,
            "bytes_downloaded": 0,
            "start_time": time.time(),
            "last_operation_time": None
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current operation statistics.
        
        Returns:
            Dict: Dictionary with current statistics
        """
        return {
            "backend_name": self.backend_name,
            "operation_stats": self.operation_stats,
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.operation_stats["start_time"]
        }
    
    def reset(self) -> Dict[str, Any]:
        """
        Reset operation statistics.
        
        Returns:
            Dict: Result of the reset operation
        """
        prev_stats = self.operation_stats.copy()
        self.operation_stats = self._initialize_stats()
        
        logger.info(f"{self.backend_name} Model statistics reset")
        
        return {
            "success": True,
            "operation": "reset_stats",
            "backend_name": self.backend_name,
            "previous_stats": prev_stats,
            "timestamp": time.time()
        }
    
    def _update_stats(self, 
                      operation: str, 
                      success: bool, 
                      bytes_count: Optional[int] = None) -> None:
        """
        Update operation statistics.
        
        Args:
            operation: Type of operation (upload, download, list, delete)
            success: Whether the operation was successful
            bytes_count: Number of bytes uploaded or downloaded
        """
        self.operation_stats["total_operations"] += 1
        self.operation_stats["last_operation_time"] = time.time()
        
        if success:
            self.operation_stats["success_count"] += 1
        else:
            self.operation_stats["failure_count"] += 1
            
        if operation == "upload":
            self.operation_stats["upload_count"] += 1
            if bytes_count is not None:
                self.operation_stats["bytes_uploaded"] += bytes_count
        elif operation == "download":
            self.operation_stats["download_count"] += 1
            if bytes_count is not None:
                self.operation_stats["bytes_downloaded"] += bytes_count
        elif operation == "list":
            self.operation_stats["list_count"] += 1
        elif operation == "delete":
            self.operation_stats["delete_count"] += 1
    
    def _create_operation_id(self, operation: str) -> str:
        """
        Create a unique operation ID.
        
        Args:
            operation: Type of operation
            
        Returns:
            str: Unique operation ID
        """
        return f"{self.backend_name.lower()}_{operation}_{uuid.uuid4()}"
    
    def _create_result_template(self, operation: str) -> Dict[str, Any]:
        """
        Create a standard result template for operations.
        
        Args:
            operation: Type of operation
            
        Returns:
            Dict: Result template with common fields
        """
        operation_id = self._create_operation_id(operation)
        timestamp = time.time()
        
        return {
            "success": False,  # Default to False, will be set to True if operation succeeds
            "operation": operation,
            "operation_id": operation_id,
            "backend_name": self.backend_name,
            "timestamp": timestamp
        }
    
    def _handle_operation_result(self, 
                                result: Dict[str, Any], 
                                operation: str, 
                                start_time: float, 
                                bytes_count: Optional[int] = None) -> Dict[str, Any]:
        """
        Process and finalize an operation result.
        
        Args:
            result: Operation result dictionary
            operation: Type of operation
            start_time: Start time of the operation
            bytes_count: Number of bytes processed
            
        Returns:
            Dict: Finalized operation result
        """
        # Calculate duration
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        result["duration_ms"] = duration_ms
        
        # Update statistics
        self._update_stats(operation, result.get("success", False), bytes_count)
        
        return result
    
    def _handle_exception(self, 
                         e: Exception, 
                         result: Dict[str, Any], 
                         operation: str) -> Dict[str, Any]:
        """
        Handle an exception during an operation.
        
        Args:
            e: Exception that occurred
            result: Current operation result
            operation: Type of operation
            
        Returns:
            Dict: Updated operation result with error information
        """
        logger.error(f"Error in {self.backend_name} {operation}: {str(e)}")
        
        result["success"] = False
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        
        # For specific error types, add more detailed information
        if hasattr(e, "response") and hasattr(e.response, "status_code"):
            result["status_code"] = e.response.status_code
            
        return result
    
    def _get_credentials(self, service: Optional[str] = None) -> Dict[str, Any]:
        """
        Get credentials for a service.
        
        Args:
            service: Optional service name to get specific credentials
            
        Returns:
            Dict: Credentials for the service
        """
        if self.credential_manager is None:
            logger.warning(f"No credential manager available for {self.backend_name}")
            return {}
            
        service_name = service or self.backend_name.lower()
        return self.credential_manager.get_credentials(service_name) or {}
    
    def _get_file_size(self, file_path: str) -> int:
        """
        Get the size of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            int: Size of the file in bytes
        """
        try:
            return os.path.getsize(file_path)
        except (OSError, IOError) as e:
            logger.warning(f"Error getting file size for {file_path}: {str(e)}")
            return 0
    
    def _cache_get(self, key: str) -> Optional[Any]:
        """
        Get an item from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Any: Cached item or None if not found
        """
        if self.cache_manager is None:
            return None
            
        cache_key = f"{self.backend_name.lower()}:{key}"
        return self.cache_manager.get(cache_key)
    
    def _cache_put(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Put an item in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            metadata: Optional metadata for the cached item
            
        Returns:
            bool: Whether the operation was successful
        """
        if self.cache_manager is None:
            return False
            
        cache_key = f"{self.backend_name.lower()}:{key}"
        return self.cache_manager.put(cache_key, value, metadata)
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the storage backend.
        
        This method should be overridden by subclasses to implement a specific
        health check for the backend.
        
        Returns:
            Dict: Health check result
        """
        result = self._create_result_template("health_check")
        start_time = time.time()
        
        try:
            # Default implementation just returns basic kit information
            result["success"] = self.kit is not None
            result["kit_available"] = self.kit is not None
            result["cache_available"] = self.cache_manager is not None
            result["credential_available"] = self.credential_manager is not None
            
            # Add backend-specific information if available
            if hasattr(self.kit, "get_version"):
                try:
                    result["version"] = self.kit.get_version()
                except Exception:
                    result["version"] = "unknown"
        
        except Exception as e:
            return self._handle_exception(e, result, "health_check")
            
        return self._handle_operation_result(result, "health_check", start_time)