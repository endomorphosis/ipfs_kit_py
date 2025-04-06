# ipfs_kit_py/wal_api_extension.py

import functools
import logging
from typing import Dict, Any, Optional, List, Union, Callable

from .high_level_api import IPFSSimpleAPI
from .storage_wal import (
    StorageWriteAheadLog, 
    BackendHealthMonitor, 
    OperationType, 
    OperationStatus, 
    BackendType
)
from .wal_integration import WALIntegration, with_wal

# Configure logging
logger = logging.getLogger(__name__)

class WALEnabledAPI(IPFSSimpleAPI):
    """
    Extension of the high-level API with Write-Ahead Log (WAL) integration.
    
    This class extends IPFSSimpleAPI to add robust write-ahead logging capabilities,
    enabling fault tolerance and durability for storage operations.
    """
    
    def __init__(self, config_path: Optional[str] = None, **kwargs):
        """
        Initialize the WAL-enabled API.
        
        Args:
            config_path: Path to YAML/JSON configuration file
            **kwargs: Additional configuration parameters
                - enable_wal: Whether to enable WAL (default: True)
                - wal_config: Configuration for WAL
        """
        # Extract WAL-specific configuration
        self.enable_wal = kwargs.pop("enable_wal", True)
        self.wal_config = kwargs.pop("wal_config", {})
        
        # Initialize the base API
        super().__init__(config_path=config_path, **kwargs)
        
        # Merge WAL configuration from parent config
        if "wal" in self.config:
            # Configuration from file takes precedence over the one passed in constructor
            self.enable_wal = self.config["wal"].get("enabled", self.enable_wal)
            self.wal_config.update(self.config["wal"])
        
        # Initialize WAL if enabled
        if self.enable_wal:
            self._init_wal()
            self._wrap_methods()
            logger.info("WAL system initialized and enabled")
        else:
            logger.info("WAL system disabled")
    
    def _init_wal(self):
        """Initialize the WAL system."""
        # Create WAL configuration
        wal_config = {
            "base_path": self.wal_config.get("base_path", "~/.ipfs_kit/wal"),
            "partition_size": self.wal_config.get("partition_size", 1000),
            "max_retries": self.wal_config.get("max_retries", 5),
            "retry_delay": self.wal_config.get("retry_delay", 60),
            "archive_completed": self.wal_config.get("archive_completed", True),
            "process_interval": self.wal_config.get("processing_interval", 5),
            "enable_health_monitoring": self.wal_config.get("enable_health_monitoring", True),
            "health_check_interval": self.wal_config.get("health_check_interval", 60),
            "monitored_backends": self.wal_config.get("monitored_backends"),
        }
        
        # Initialize WAL integration
        self.wal_integration = WALIntegration(config=wal_config)
    
    def _wrap_methods(self):
        """Wrap API methods with WAL decorators."""
        # Define which methods to wrap and their operation types and backends
        methods_to_wrap = {
            "add": (OperationType.ADD, BackendType.IPFS),
            "add_directory": (OperationType.ADD, BackendType.IPFS),
            "get": (OperationType.GET, BackendType.IPFS),
            "pin": (OperationType.PIN, BackendType.IPFS),
            "unpin": (OperationType.UNPIN, BackendType.IPFS),
            "rm": (OperationType.RM, BackendType.IPFS),
            "cat": (OperationType.CAT, BackendType.IPFS),
            "list": (OperationType.LIST, BackendType.IPFS),
            "mkdir": (OperationType.MKDIR, BackendType.IPFS),
            "copy": (OperationType.COPY, BackendType.IPFS),
            "move": (OperationType.MOVE, BackendType.IPFS),
            "upload": (OperationType.UPLOAD, BackendType.IPFS),
            "download": (OperationType.DOWNLOAD, BackendType.IPFS),
        }
        
        # S3-specific methods
        s3_methods = {
            "s3_upload": (OperationType.UPLOAD, BackendType.S3),
            "s3_download": (OperationType.DOWNLOAD, BackendType.S3),
            "s3_copy": (OperationType.COPY, BackendType.S3),
            "s3_move": (OperationType.MOVE, BackendType.S3),
            "s3_delete": (OperationType.RM, BackendType.S3),
            "s3_list": (OperationType.LIST, BackendType.S3),
        }
        methods_to_wrap.update(s3_methods)
        
        # Storacha-specific methods
        storacha_methods = {
            "storacha_upload": (OperationType.UPLOAD, BackendType.STORACHA),
            "storacha_download": (OperationType.DOWNLOAD, BackendType.STORACHA),
            "storacha_delete": (OperationType.RM, BackendType.STORACHA),
            "storacha_list": (OperationType.LIST, BackendType.STORACHA),
        }
        methods_to_wrap.update(storacha_methods)
        
        # Local-specific methods
        local_methods = {
            "local_add": (OperationType.ADD, BackendType.LOCAL),
            "local_get": (OperationType.GET, BackendType.LOCAL),
            "local_delete": (OperationType.RM, BackendType.LOCAL),
            "local_list": (OperationType.LIST, BackendType.LOCAL),
        }
        methods_to_wrap.update(local_methods)
        
        # Wrap methods if they exist
        for method_name, (operation_type, backend_type) in methods_to_wrap.items():
            if hasattr(self, method_name):
                original_method = getattr(self, method_name)
                wrapped_method = with_wal(
                    operation_type=operation_type,
                    backend=backend_type,
                    wal_integration=self.wal_integration
                )(original_method)
                setattr(self, method_name, wrapped_method)
    
    def get_wal_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an operation by ID.
        
        Args:
            operation_id: ID of the operation to get
            
        Returns:
            Operation information or None if not found
        """
        if not self.enable_wal:
            return {"error": "WAL is not enabled"}
        return self.wal_integration.get_operation(operation_id)
    
    def get_wal_operations_by_status(self, status: Union[str, OperationStatus], 
                                    limit: int = None) -> List[Dict[str, Any]]:
        """
        Get operations with a specific status.
        
        Args:
            status: Status to filter by
            limit: Maximum number of operations to return
            
        Returns:
            List of operations with the specified status
        """
        if not self.enable_wal:
            return []
        return self.wal_integration.get_operations_by_status(status, limit)
    
    def get_wal_all_operations(self) -> List[Dict[str, Any]]:
        """
        Get all operations in the WAL.
        
        Returns:
            List of all operations
        """
        if not self.enable_wal:
            return []
        return self.wal_integration.get_all_operations()
    
    def get_wal_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the WAL.
        
        Returns:
            Dictionary with statistics
        """
        if not self.enable_wal:
            return {"error": "WAL is not enabled"}
        return self.wal_integration.get_statistics()
    
    def get_wal_backend_health(self, backend: str = None) -> Dict[str, Any]:
        """
        Get the health status of backends.
        
        Args:
            backend: Backend to get health for, or None for all
            
        Returns:
            Dictionary with backend health information
        """
        if not self.enable_wal:
            return {"error": "WAL is not enabled"}
        return self.wal_integration.get_backend_health(backend)
    
    def wal_cleanup(self, max_age_days: int = 30) -> Dict[str, Any]:
        """
        Clean up old operations.
        
        Args:
            max_age_days: Maximum age in days for operations to keep
            
        Returns:
            Dictionary with cleanup results
        """
        if not self.enable_wal:
            return {"error": "WAL is not enabled"}
        return self.wal_integration.cleanup(max_age_days)
    
    def wait_for_operation(self, operation_id: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Wait for an operation to complete.
        
        Args:
            operation_id: ID of the operation to wait for
            timeout: Maximum time to wait in seconds
            
        Returns:
            Result of the operation
        """
        if not self.enable_wal:
            return {"error": "WAL is not enabled"}
        return self.wal_integration.wait_for_operation(operation_id, timeout)
    
    def close(self):
        """Clean up resources when the API is no longer needed."""
        if self.enable_wal:
            self.wal_integration.close()
        
        # Call parent close method if it exists
        if hasattr(super(), "close"):
            super().close()