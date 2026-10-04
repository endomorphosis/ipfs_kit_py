"""Method Normalizer Module

This module provides utilities for normalizing method interfaces across different
implementations of IPFS clients.
"""

from typing import Any, Callable, Dict, List, Optional, Type, Union
import inspect
import logging
import time  # Added time import

logger = logging.getLogger(__name__)

# Define method name mappings between different IPFS client implementations
# Format: standard_name -> [list of alternative names]
METHOD_MAPPINGS = {
    # Core IPFS operations
    "add": ["ipfs_add", "add_bytes", "add_str", "add_file", "put"],
    "cat": ["ipfs_cat", "get_str", "get_bytes", "get_file", "read"],
    "get": ["ipfs_get", "download", "retrieve"],
    "ls": ["ipfs_ls", "list_directory", "list_files", "list_objects"],
    "pin_add": ["ipfs_pin_add", "pin", "add_pin", "ipfs_pin"],
    "pin_rm": ["ipfs_pin_rm", "unpin", "remove_pin", "ipfs_unpin"],
    "pin_ls": ["ipfs_pin_ls", "list_pins", "get_pins", "ipfs_list_pins"],
    "id": ["ipfs_id", "node_id", "get_id", "get_node_id"],
    
    # Extended operations
    "dag_put": ["ipfs_dag_put", "dag_add", "add_dag", "put_dag"],
    "dag_get": ["ipfs_dag_get", "get_dag", "retrieve_dag"],
    "dag_resolve": ["ipfs_dag_resolve", "resolve_dag", "dag_path"],
    "name_publish": ["ipfs_name_publish", "publish", "ipns_publish"],
    "name_resolve": ["ipfs_name_resolve", "resolve", "ipns_resolve"],
    "files_cp": ["ipfs_files_cp", "copy_files", "files_copy"],
    "files_ls": ["ipfs_files_ls", "list_mfs", "mfs_list"],
    "files_mkdir": ["ipfs_files_mkdir", "make_directory", "mfs_mkdir"],
    "files_rm": ["ipfs_files_rm", "remove_files", "mfs_rm"],
    "key_gen": ["ipfs_key_gen", "generate_key", "create_key"],
    "key_list": ["ipfs_key_list", "list_keys", "get_keys"],
}

# Define simulation functions that can be used in tests or when actual implementations are unavailable
SIMULATION_FUNCTIONS = {
    "add": lambda *args, **kwargs: {
        "success": True, 
        "Hash": "QmSimulatedHash123456789", 
        "Size": 1024, 
        "simulated": True
    },
    "get": lambda *args, **kwargs: {
        "success": True, 
        "data": b"Simulated content from IPFS get operation", 
        "simulated": True
    },
    "cat": lambda *args, **kwargs: {
        "success": True, 
        "data": b"Test content", 
        "simulated": True
    },
    "ls": lambda *args, **kwargs: {
        "success": True, 
        "Objects": [{"Hash": "QmSimulatedHash", "Links": [
            {"Name": "file1.txt", "Hash": "QmFileHash1", "Size": 256},
            {"Name": "file2.txt", "Hash": "QmFileHash2", "Size": 512}
        ]}],
        "simulated": True
    },
    "pin_add": lambda *args, **kwargs: {
        "success": True, 
        "Pins": ["QmSimulatedHash"], 
        "simulated": True
    },
    "pin_rm": lambda *args, **kwargs: {
        "success": True, 
        "Pins": ["QmSimulatedHash"], 
        "simulated": True
    },
    "pin_ls": lambda *args, **kwargs: {
        "success": True, 
        "Keys": {"QmSimulatedHash": {"Type": "recursive"}}, 
        "simulated": True
    },
    "id": lambda *args, **kwargs: {
        "success": True, 
        "ID": "QmNodeIDSimulated", 
        "Addresses": [
            "/ip4/127.0.0.1/tcp/4001/p2p/QmNodeIDSimulated",
            "/ip4/192.168.1.1/tcp/4001/p2p/QmNodeIDSimulated"
        ], 
        "simulated": True
    },
    "dag_put": lambda *args, **kwargs: {
        "success": True, 
        "Cid": {"/": "bafy...simulated"}, 
        "simulated": True
    },
    "dag_get": lambda *args, **kwargs: {
        "success": True, 
        "data": {"key": "value", "nested": {"data": [1, 2, 3]}}, 
        "simulated": True
    },
    "name_publish": lambda *args, **kwargs: {
        "success": True, 
        "Name": "QmSimulatedHash", 
        "Value": "/ipfs/QmSimulatedHash", 
        "simulated": True
    },
    "name_resolve": lambda *args, **kwargs: {
        "success": True, 
        "Path": "/ipfs/QmSimulatedHash", 
        "simulated": True
    },
}


class IPFSMethodAdapter:
    """Adapter for normalizing IPFS method interfaces."""
    
    def __init__(self, instance: Any):
        """Initialize with an IPFS instance to adapt."""
        self.instance = instance
        self.methods = {}
        self._discover_methods()
    
    def _discover_methods(self) -> None:
        """Discover available methods on the instance."""
        for attr_name in dir(self.instance):
            if attr_name.startswith('_'):
                continue
            attr = getattr(self.instance, attr_name)
            if callable(attr):
                self.methods[attr_name] = attr
    
    def has_method(self, method_name: str) -> bool:
        """Check if the instance has the specified method."""
        return method_name in self.methods
    
    def call_method(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a method on the adapted instance."""
        if not self.has_method(method_name):
            raise NotImplementedError(f"Method {method_name} not implemented")
        return self.methods[method_name](*args, **kwargs)


class NormalizedIPFS:
    """
    A normalized interface for IPFS operations.
    
    This class provides a standardized interface for interacting with IPFS
    regardless of the underlying implementation.
    """
    
    def __init__(self, instance: Any, logger=None):
        """
        Initialize with an IPFS instance.
        
        Args:
            instance: The IPFS instance to normalize
            logger: Optional logger for operation tracking
        """
        self._original_instance = instance
        self._instance = instance
        self._logger = logger or logging.getLogger(__name__)
        
        # Initialize operation statistics
        self.operation_stats = {
            "operations": {},
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
            "last_operation_time": None,
        }
        
        # Add any methods from METHOD_MAPPINGS that don't exist
        self._add_normalized_methods()
    
    def _add_normalized_methods(self):
        """Add normalized methods based on METHOD_MAPPINGS."""
        for standard_name, alternatives in METHOD_MAPPINGS.items():
            # Check if the method already exists on this instance
            if hasattr(self, standard_name):
                continue
                
            # First check if the standard name exists on the underlying instance
            if hasattr(self._instance, standard_name):
                # Create a wrapper for the standard method
                setattr(self, standard_name, self._create_method_wrapper(standard_name))
                self._logger.debug(f"Added standard method: {standard_name}")
                continue
                
            # If standard method doesn't exist, check for alternative names
            for alt_name in alternatives:
                if hasattr(self._instance, alt_name):
                    # Create a method that calls the alternative method
                    setattr(self, standard_name, self._create_alt_method_wrapper(standard_name, alt_name))
                    self._logger.debug(f"Added normalized method: {standard_name} (using {alt_name})")
                    break
            else:
                # No method found, add a simulation method if available
                if standard_name in SIMULATION_FUNCTIONS:
                    setattr(self, standard_name, self._create_simulation_wrapper(standard_name))
                    self._logger.debug(f"Added simulation method: {standard_name}")
    
    def _create_method_wrapper(self, method_name):
        """Create a wrapper for a method on the instance."""
        original_method = getattr(self._instance, method_name)
        
        def wrapped_method(*args, **kwargs):
            start_time = time.time()
            
            # Update statistics
            if method_name not in self.operation_stats["operations"]:
                self.operation_stats["operations"][method_name] = {
                    "count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "last_duration": None,
                }
            
            self.operation_stats["operations"][method_name]["count"] += 1
            self.operation_stats["total_operations"] += 1
            
            try:
                result = original_method(*args, **kwargs)
                
                # If result is a dict, ensure it has success field
                if isinstance(result, dict) and "success" not in result:
                    result["success"] = True
                
                # Update success statistics
                self.operation_stats["success_count"] += 1
                self.operation_stats["operations"][method_name]["success_count"] += 1
                
                duration = time.time() - start_time
                self.operation_stats["operations"][method_name]["last_duration"] = duration
                self.operation_stats["last_operation_time"] = time.time()
                
                return result
            except Exception as e:
                # Update failure statistics
                self.operation_stats["failure_count"] += 1
                self.operation_stats["operations"][method_name]["failure_count"] += 1
                
                self._logger.exception(f"Error in {method_name}: {str(e)}")
                
                # Return a standardized error response
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": e.__class__.__name__,
                    "method": method_name,
                }
        
        return wrapped_method
    
    def _create_alt_method_wrapper(self, standard_name, alt_name):
        """Create a wrapper that calls an alternative method name."""
        original_method = getattr(self._instance, alt_name)
        
        def wrapped_method(*args, **kwargs):
            self._logger.debug(f"Calling {alt_name} as {standard_name}")
            start_time = time.time()
            
            # Update statistics
            if standard_name not in self.operation_stats["operations"]:
                self.operation_stats["operations"][standard_name] = {
                    "count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "last_duration": None,
                    "alt_method": alt_name,
                }
            
            self.operation_stats["operations"][standard_name]["count"] += 1
            self.operation_stats["total_operations"] += 1
            
            try:
                result = original_method(*args, **kwargs)
                
                # If result is a dict, ensure it has success field
                if isinstance(result, dict) and "success" not in result:
                    result["success"] = True
                
                # Update success statistics
                self.operation_stats["success_count"] += 1
                self.operation_stats["operations"][standard_name]["success_count"] += 1
                
                duration = time.time() - start_time
                self.operation_stats["operations"][standard_name]["last_duration"] = duration
                self.operation_stats["last_operation_time"] = time.time()
                
                return result
            except Exception as e:
                # Update failure statistics
                self.operation_stats["failure_count"] += 1
                self.operation_stats["operations"][standard_name]["failure_count"] += 1
                
                self._logger.exception(f"Error in {standard_name} (using {alt_name}): {str(e)}")
                
                # Return a standardized error response
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": e.__class__.__name__,
                    "method": standard_name,
                    "alt_method": alt_name,
                }
        
        return wrapped_method
    
    def _create_simulation_wrapper(self, method_name):
        """Create a wrapper that uses a simulation function."""
        simulation_func = SIMULATION_FUNCTIONS[method_name]
        
        def wrapped_method(*args, **kwargs):
            self._logger.debug(f"Using simulation for {method_name}")
            start_time = time.time()
            
            # Update statistics
            if method_name not in self.operation_stats["operations"]:
                self.operation_stats["operations"][method_name] = {
                    "count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "last_duration": None,
                    "simulated": True,
                }
            
            self.operation_stats["operations"][method_name]["count"] += 1
            self.operation_stats["total_operations"] += 1
            
            try:
                result = simulation_func(*args, **kwargs)
                
                # Ensure the result indicates it's simulated
                if isinstance(result, dict):
                    result["simulated"] = True
                
                # Update success statistics
                self.operation_stats["success_count"] += 1
                self.operation_stats["operations"][method_name]["success_count"] += 1
                
                duration = time.time() - start_time
                self.operation_stats["operations"][method_name]["last_duration"] = duration
                self.operation_stats["last_operation_time"] = time.time()
                
                return result
            except Exception as e:
                # Update failure statistics
                self.operation_stats["failure_count"] += 1
                self.operation_stats["operations"][method_name]["failure_count"] += 1
                
                self._logger.exception(f"Error in simulated {method_name}: {str(e)}")
                
                # Return a standardized error response
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": e.__class__.__name__,
                    "method": method_name,
                    "simulated": True,
                }
        
        return wrapped_method
    
    def __getattr__(self, name):
        """Forward attribute access to the underlying instance if not found locally."""
        # First, check if this is a known method with an alternative name
        for standard_name, alternatives in METHOD_MAPPINGS.items():
            if name == standard_name or name in alternatives:
                # Add this method if it exists on the underlying instance
                for method_name in [standard_name] + alternatives:
                    if hasattr(self._instance, method_name):
                        wrapper = self._create_method_wrapper(method_name)
                        setattr(self, name, wrapper)
                        return wrapper
                
                # If we reach here, check for a simulation function
                if standard_name in SIMULATION_FUNCTIONS:
                    wrapper = self._create_simulation_wrapper(standard_name)
                    setattr(self, name, wrapper)
                    return wrapper
        
        # If not a known method, try to get it from the underlying instance
        if hasattr(self._instance, name):
            # For callable attributes, wrap them to track statistics
            attr = getattr(self._instance, name)
            if callable(attr):
                wrapper = self._create_method_wrapper(name)
                setattr(self, name, wrapper)
                return wrapper
            else:
                return attr
        
        # Attribute not found
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def get_stats(self):
        """Get operation statistics."""
        return {
            "operation_stats": self.operation_stats,
            "timestamp": time.time(),
        }


def normalize_instance(instance: Any, logger=None) -> NormalizedIPFS:
    """
    Create a normalized IPFS interface for any IPFS implementation.
    
    Args:
        instance: IPFS instance to normalize
        logger: Optional logger for operation tracking
        
    Returns:
        Normalized IPFS interface
    """
    return NormalizedIPFS(instance, logger=logger)