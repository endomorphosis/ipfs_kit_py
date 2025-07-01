"""
API stability verification module.

This module provides utilities to verify API stability and backward compatibility
between different versions of the IPFS Kit library.
"""

import inspect
import logging
from typing import Dict, List, Set, Any, Callable, Optional, Union, Type

logger = logging.getLogger(__name__)

# API Versions
API_VERSIONS = {
    "0.1.0": "Initial public API",
    "0.2.0": "Added libp2p integration",
    "0.3.0": "Added storage backends",
    "0.4.0": "Added MCP server",
    "0.5.0": "Refactored MCP modules",
    "0.6.0": "Current development version"
}

# API Compatibility Mapping
API_COMPATIBILITY = {
    "0.1.0": ["0.1.0"],
    "0.2.0": ["0.1.0", "0.2.0"],
    "0.3.0": ["0.1.0", "0.2.0", "0.3.0"],
    "0.4.0": ["0.1.0", "0.2.0", "0.3.0", "0.4.0"],
    "0.5.0": ["0.1.0", "0.2.0", "0.3.0", "0.4.0", "0.5.0"],
    "0.6.0": ["0.1.0", "0.2.0", "0.3.0", "0.4.0", "0.5.0", "0.6.0"]
}

# Core API Functions (must remain stable)
CORE_API_FUNCTIONS = {
    "ipfs_kit": [
        "add",
        "get",
        "cat",
        "connect_to_peer",
        "create_dag",
        "get_dag",
        "pin",
        "unpin",
        "list_pins"
    ],
    "ipfs_simple_api": [
        "add_file",
        "get_file",
        "add_directory",
        "get_directory",
        "create_mfs_directory",
        "ls",
        "connect_to_peer",
        "create_dag_node",
        "get_dag_node"
    ]
}

class APISignature:
    """Represents the signature of an API function."""
    
    def __init__(self, func: Callable):
        """Initialize from a function."""
        self.name = func.__name__
        self.signature = inspect.signature(func)
        self.parameters = list(self.signature.parameters.keys())
        self.return_annotation = self.signature.return_annotation
        self.module = func.__module__
    
    def __eq__(self, other: 'APISignature') -> bool:
        """Check if two API signatures are equal."""
        if not isinstance(other, APISignature):
            return False
        
        # Basic equality: name and module
        if self.name != other.name or self.module != other.module:
            return False
            
        # Compare parameters
        if self.parameters != other.parameters:
            return False
            
        # Return type can change as long as it's compatible
        # For now, just check strict equality
        if self.return_annotation != other.return_annotation:
            return False
            
        return True
    
    def is_compatible_with(self, other: 'APISignature') -> bool:
        """Check if this signature is backward compatible with another."""
        if self.name != other.name or self.module != other.module:
            return False
            
        # Check that all parameters in other exist in self
        # New optional parameters are allowed
        for param in other.parameters:
            if param not in self.parameters:
                return False
                
        # Return type should be compatible (not strictly checked here)
        return True
        
    def __str__(self) -> str:
        """Get string representation."""
        return f"{self.module}.{self.name}{self.signature}"


class APISnapshot:
    """Represents a snapshot of an API at a specific version."""
    
    def __init__(self, version: str, api_dict: Dict[str, Dict[str, Callable]]):
        """Initialize from a version string and API dictionary."""
        self.version = version
        self.api = {}
        
        # Create signatures for all functions
        for module_name, functions in api_dict.items():
            self.api[module_name] = {}
            for func_name, func in functions.items():
                self.api[module_name][func_name] = APISignature(func)
    
    def is_compatible_with(self, other: 'APISnapshot') -> bool:
        """Check if this snapshot is backward compatible with another."""
        # Check version compatibility
        if other.version not in API_COMPATIBILITY.get(self.version, []):
            logger.warning(f"Version incompatibility: {self.version} not compatible with {other.version}")
            return False
            
        # Check API compatibility
        for module_name, funcs in other.api.items():
            if module_name not in self.api:
                logger.warning(f"Module missing: {module_name}")
                return False
                
            for func_name, signature in funcs.items():
                if func_name not in self.api[module_name]:
                    logger.warning(f"Function missing: {module_name}.{func_name}")
                    return False
                    
                if not self.api[module_name][func_name].is_compatible_with(signature):
                    logger.warning(f"Function signature changed: {module_name}.{func_name}")
                    return False
                    
        return True
    
    def get_differences(self, other: 'APISnapshot') -> Dict[str, List[str]]:
        """Get differences between this snapshot and another."""
        differences = {
            "missing_modules": [],
            "missing_functions": [],
            "signature_changes": []
        }
        
        # Check for missing modules and functions
        for module_name, funcs in other.api.items():
            if module_name not in self.api:
                differences["missing_modules"].append(module_name)
                continue
                
            for func_name, signature in funcs.items():
                if func_name not in self.api[module_name]:
                    differences["missing_functions"].append(f"{module_name}.{func_name}")
                elif not self.api[module_name][func_name].is_compatible_with(signature):
                    differences["signature_changes"].append(f"{module_name}.{func_name}")
                    
        return differences


def verify_api_compatibility(current_api: Dict[str, Dict[str, Callable]], 
                            reference_api: Dict[str, Dict[str, Callable]],
                            current_version: str = "0.6.0",
                            reference_version: str = "0.5.0") -> bool:
    """
    Verify that the current API is backward compatible with the reference API.
    
    Args:
        current_api: Current API dictionary
        reference_api: Reference API dictionary
        current_version: Current API version
        reference_version: Reference API version
        
    Returns:
        True if compatible, False otherwise
    """
    current_snapshot = APISnapshot(current_version, current_api)
    reference_snapshot = APISnapshot(reference_version, reference_api)
    
    return current_snapshot.is_compatible_with(reference_snapshot)


def get_api_diff(current_api: Dict[str, Dict[str, Callable]], 
                reference_api: Dict[str, Dict[str, Callable]],
                current_version: str = "0.6.0",
                reference_version: str = "0.5.0") -> Dict[str, List[str]]:
    """
    Get differences between current API and reference API.
    
    Args:
        current_api: Current API dictionary
        reference_api: Reference API dictionary
        current_version: Current API version
        reference_version: Reference API version
        
    Returns:
        Dictionary of differences
    """
    current_snapshot = APISnapshot(current_version, current_api)
    reference_snapshot = APISnapshot(reference_version, reference_api)
    
    return current_snapshot.get_differences(reference_snapshot)


# Default API configuration for testing
TEST_API = {
    "ipfs_kit": {
        "add": lambda path, **kwargs: None,
        "get": lambda cid, **kwargs: None,
        "cat": lambda cid, **kwargs: None,
        "connect_to_peer": lambda peer_id, **kwargs: None,
        "create_dag": lambda data, **kwargs: None,
        "get_dag": lambda cid, **kwargs: None,
        "pin": lambda cid, **kwargs: None,
        "unpin": lambda cid, **kwargs: None,
        "list_pins": lambda **kwargs: None
    },
    "ipfs_simple_api": {
        "add_file": lambda path, **kwargs: None,
        "get_file": lambda cid, path, **kwargs: None,
        "add_directory": lambda path, **kwargs: None,
        "get_directory": lambda cid, path, **kwargs: None,
        "create_mfs_directory": lambda path, **kwargs: None,
        "ls": lambda path, **kwargs: None,
        "connect_to_peer": lambda peer_id, **kwargs: None,
        "create_dag_node": lambda data, **kwargs: None,
        "get_dag_node": lambda cid, **kwargs: None
    }
}