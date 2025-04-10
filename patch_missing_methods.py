#!/usr/bin/env python3
"""
Patch missing methods in the ipfs_kit class.
This script adds the missing DHT and MFS methods to the ipfs_kit class.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the ipfs_kit class and error handling utilities
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.error import create_result_dict, handle_error, IPFSError

# DHT Methods
def dht_findpeer(self, peer_id, **kwargs):
    """Find a specific peer via the DHT and retrieve addresses.
    
    Args:
        peer_id: The ID of the peer to find
        **kwargs: Additional parameters for the operation
        
    Returns:
        Dict with operation result containing peer multiaddresses
    """
    operation = "dht_findpeer"
    correlation_id = kwargs.get("correlation_id")
    result = create_result_dict(operation, correlation_id)
    
    try:
        # Delegate to the ipfs instance
        if not hasattr(self, "ipfs"):
            return handle_error(result, IPFSError("IPFS instance not initialized"))
            
        # Call the ipfs module's implementation
        response = self.ipfs.dht_findpeer(peer_id)
        result.update(response)
        result["success"] = response.get("success", False)
        return result
    except Exception as e:
        return handle_error(result, e)

def dht_findprovs(self, cid, num_providers=None, **kwargs):
    """Find providers for a CID via the DHT.
    
    Args:
        cid: The Content ID to find providers for
        num_providers: Maximum number of providers to find
        **kwargs: Additional parameters for the operation
        
    Returns:
        Dict with operation result containing provider information
    """
    operation = "dht_findprovs"
    correlation_id = kwargs.get("correlation_id")
    result = create_result_dict(operation, correlation_id)
    
    try:
        # Delegate to the ipfs instance
        if not hasattr(self, "ipfs"):
            return handle_error(result, IPFSError("IPFS instance not initialized"))
            
        # Build kwargs to pass to ipfs
        ipfs_kwargs = {}
        if num_providers is not None:
            ipfs_kwargs["num_providers"] = num_providers
            
        # Call the ipfs module's implementation
        response = self.ipfs.dht_findprovs(cid, **ipfs_kwargs)
        result.update(response)
        result["success"] = response.get("success", False)
        return result
    except Exception as e:
        return handle_error(result, e)
        
# IPFS MFS (Mutable File System) Methods
def files_mkdir(self, path, parents=False, **kwargs):
    """Create a directory in the MFS.
    
    Args:
        path: Path to create in the MFS
        parents: Whether to create parent directories if they don't exist
        **kwargs: Additional parameters for the operation
        
    Returns:
        Dict with operation result
    """
    operation = "files_mkdir"
    correlation_id = kwargs.get("correlation_id")
    result = create_result_dict(operation, correlation_id)
    
    try:
        # Delegate to the ipfs instance
        if not hasattr(self, "ipfs"):
            return handle_error(result, IPFSError("IPFS instance not initialized"))
            
        # Call the ipfs module's implementation
        response = self.ipfs.files_mkdir(path, parents)
        result.update(response)
        result["success"] = response.get("success", False)
        return result
    except Exception as e:
        return handle_error(result, e)
        
def files_ls(self, path="/", **kwargs):
    """List directory contents in the MFS.
    
    Args:
        path: Directory path in the MFS to list
        **kwargs: Additional parameters for the operation
            - long: Boolean, whether to use long listing format (include size, type, etc.)
            - U: Boolean, do not sort; list entries in directory order
            - correlation_id: Optional ID for tracking related operations
        
    Returns:
        Dict with operation result containing directory entries
    """
    operation = "files_ls"
    correlation_id = kwargs.get("correlation_id")
    result = create_result_dict(operation, correlation_id)
    
    try:
        # Delegate to the ipfs instance
        if not hasattr(self, "ipfs"):
            return handle_error(result, IPFSError("IPFS instance not initialized"))
            
        # Extract the long parameter
        long = kwargs.get("long", False)
            
        # Call the ipfs module's implementation with the proper parameters
        if long:
            # Add 'long' to the query parameters if needed
            response = self.ipfs.files_ls(path, {"long": long})
        else:
            # Call without the long parameter
            response = self.ipfs.files_ls(path)
        result.update(response)
        result["success"] = response.get("success", False)
        return result
    except Exception as e:
        return handle_error(result, e)
        
def files_stat(self, path, **kwargs):
    """Get file information from the MFS.
    
    Args:
        path: Path to file or directory in the MFS
        **kwargs: Additional parameters for the operation
            - format: Optional format string for output
            - hash: Boolean, include hash in output (default: True)
            - size: Boolean, include size in output (default: True)
            - correlation_id: Optional ID for tracking related operations
        
    Returns:
        Dict with operation result containing file statistics
    """
    import time  # Import time module here in case it's needed in any error handling
    
    operation = "files_stat"
    correlation_id = kwargs.get("correlation_id")
    result = create_result_dict(operation, correlation_id)
    
    try:
        # Delegate to the ipfs instance
        if not hasattr(self, "ipfs"):
            return handle_error(result, IPFSError("IPFS instance not initialized"))
            
        # Extract optional parameters
        format_opt = kwargs.get("format", None)
        hash_opt = kwargs.get("hash", True)
        size_opt = kwargs.get("size", True)
        
        # Build kwargs to pass to ipfs
        ipfs_kwargs = {}
        if format_opt is not None:
            ipfs_kwargs["format"] = format_opt
        if not hash_opt:
            ipfs_kwargs["hash"] = False
        if not size_opt:
            ipfs_kwargs["size"] = False
            
        # Call the ipfs module's implementation
        response = self.ipfs.files_stat(path, **ipfs_kwargs)
        result.update(response)
        result["success"] = response.get("success", False)
        return result
    except Exception as e:
        return handle_error(result, e)

# Add these methods to the ipfs_kit class
ipfs_kit.dht_findpeer = dht_findpeer
ipfs_kit.dht_findprovs = dht_findprovs
ipfs_kit.files_mkdir = files_mkdir
ipfs_kit.files_ls = files_ls
ipfs_kit.files_stat = files_stat

print("Successfully patched missing methods to ipfs_kit class")