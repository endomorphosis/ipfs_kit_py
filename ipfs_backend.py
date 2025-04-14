#!/usr/bin/env python3
"""
IPFS Storage Backend

This module provides IPFS storage capabilities through a standardized backend interface.
It dynamically loads the ipfs_py library if available or creates a mock implementation.
"""

import os
import sys
import glob
import importlib
import logging
import time
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ipfs_backend")

class IPFSStorageBackend:
    """Storage backend implementation for IPFS."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the IPFS storage backend.
        
        Args:
            config: Configuration dictionary for the backend.
        """
        self.config = config or {}
        self.name = "ipfs"
        self.description = "IPFS Storage Backend"
        self.initialized = False
        self.performance_stats = {
            "store": {"count": 0, "total_time": 0, "avg_time": 0},
            "retrieve": {"count": 0, "total_time": 0, "avg_time": 0},
            "delete": {"count": 0, "total_time": 0, "avg_time": 0},
            "list": {"count": 0, "total_time": 0, "avg_time": 0},
        }
        
        # Initialize the IPFS client
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize the IPFS client."""
        # Load IPFS implementation
        self.ipfs = self._load_ipfs_implementation()
        
        # Check if we got a mock implementation
        self.is_mock = getattr(self.ipfs, "_mock_implementation", False)
        
        if self.is_mock:
            logger.warning("Using mock IPFS implementation - limited functionality available")
        else:
            logger.info("IPFS backend initialized successfully")
        
        self.initialized = True
    
    def get_name(self) -> str:
        """Get the backend name."""
        return self.name
    
    def get_description(self) -> str:
        """Get the backend description."""
        return self.description
    
    def is_available(self) -> bool:
        """Check if the backend is available."""
        return self.initialized and not self.is_mock
    
    def _load_ipfs_implementation(self):
        """
        Dynamically load the ipfs_py implementation.
        
        This will try several approaches:
        1. Direct import of ipfs_py
        2. Look for ipfs_py in common locations
        3. Fall back to a mock implementation if all else fails
        """
        # First attempt: direct import
        try:
            import ipfs_py
            logger.info("Successfully imported ipfs_py directly")
            return ipfs_py
        except ImportError:
            logger.warning("Could not import ipfs_py directly, trying alternative methods")
        
        # Second attempt: search for ipfs_py in common locations
        paths_to_check = [
            os.path.expanduser("~/.local/lib/python*/site-packages/ipfs_py"),
            os.path.expanduser("~/ipfs_py"),
            "/usr/local/lib/python*/site-packages/ipfs_py",
            "/usr/lib/python*/site-packages/ipfs_py",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipfs_py"),
        ]
        
        for path_pattern in paths_to_check:
            for ipfs_dir in glob.glob(path_pattern):
                ipfs_file = os.path.join(ipfs_dir, "ipfs_py.py")
                
                if os.path.isfile(ipfs_file):
                    logger.info(f"Found ipfs_py at {ipfs_file}")
                    
                    # Try to import as a module
                    try:
                        module_name = os.path.basename(os.path.dirname(ipfs_file))
                        try:
                            module = importlib.import_module(module_name)
                            if hasattr(module, "ipfs_py"):
                                logger.info(f"Successfully imported {module_name}")
                                return module.ipfs_py
                        except (ImportError, AttributeError) as e:
                            logger.warning(f"Failed to import as module {module_name}: {e}")
                            
                            # Fall back to direct file execution
                            import importlib.util
                            spec = importlib.util.spec_from_file_location("ipfs_module", ipfs_file)
                            if spec and spec.loader:
                                ipfs_module = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(ipfs_module)
                                logger.info(f"Successfully loaded ipfs_py from file: {ipfs_file}")
                                return ipfs_module.ipfs_py
                    except Exception as e3:
                        logger.warning(f"Could not import ipfs_py from discovered files: {e3}")
        
        # Final fallback: create a mock implementation
        logger.error("Could not import ipfs_py. Creating mock implementation.")
        
        class MockIPFSPy:
            """Mock implementation of ipfs_py for when the real one can't be imported."""
            _mock_implementation = True
            
            def __init__(self, *args, **kwargs):
                self.logger = logging.getLogger("mock_ipfs_py")
                self.logger.warning("Using mock IPFS implementation - limited functionality available")
            
            def ipfs_add_file(self, *args, **kwargs):
                return {"success": False, "error": "Mock IPFS implementation", "error_type": "MockImplementation"}
            
            def ipfs_add_bytes(self, *args, **kwargs):
                return {"success": False, "error": "Mock IPFS implementation", "error_type": "MockImplementation"}
            
            def ipfs_cat(self, *args, **kwargs):
                return {"success": False, "error": "Mock IPFS implementation", "error_type": "MockImplementation"}
            
            def ipfs_pin_ls(self, *args, **kwargs):
                return {"success": False, "error": "Mock IPFS implementation", "error_type": "MockImplementation"}
            
            def ipfs_pin_add(self, *args, **kwargs):
                return {"success": False, "error": "Mock IPFS implementation", "error_type": "MockImplementation"}
            
            def ipfs_pin_rm(self, *args, **kwargs):
                return {"success": False, "error": "Mock IPFS implementation", "error_type": "MockImplementation"}
            
            def ipfs_object_stat(self, *args, **kwargs):
                return {"success": False, "error": "Mock IPFS implementation", "error_type": "MockImplementation"}
            
            def ipfs_add_metadata(self, *args, **kwargs):
                return {"success": False, "error": "Mock IPFS implementation", "error_type": "MockImplementation"}
            
            def __getattr__(self, name):
                # Handle any method call with a standard error response
                def method(*args, **kwargs):
                    return {"success": False, "error": f"Mock IPFS implementation (method: {name})", "error_type": "MockImplementation"}
                return method
        
        return MockIPFSPy()

    def store(
        self,
        data: Union[bytes, BinaryIO, str],
        container: Optional[str] = None,
        path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store data in IPFS.
        
        Args:
            data: The data to store, can be bytes, file-like object, or string
            container: Optional container name (not used in IPFS)
            path: Optional path within container (not used in IPFS)
            options: Additional options for the storage operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # Handle different data types
        if isinstance(data, str):
            # If it's a string, convert to bytes
            data = data.encode("utf-8")

        if isinstance(data, bytes):
            # Add data directly
            result = self.ipfs.ipfs_add_bytes(data)
        else:
            # Assume it's a file-like object
            result = self.ipfs.ipfs_add_file(data)

        if result.get("success", False):
            # Add MCP metadata for tracking
            cid = result.get("cid")
            if options.get("pin", True):
                # Pin the content if requested (default: True)
                pin_result = self.ipfs.ipfs_pin_add(cid)
                result["pin_result"] = pin_result
        
        # Update performance stats
        duration = time.time() - start_time
        self.performance_stats["store"]["count"] += 1
        self.performance_stats["store"]["total_time"] += duration
        self.performance_stats["store"]["avg_time"] = (
            self.performance_stats["store"]["total_time"] / self.performance_stats["store"]["count"]
        )
        
        return {
            "success": result.get("success", False),
            "identifier": result.get("cid"),
            "backend": self.get_name(),
            "details": result,
        }

    def retrieve(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve data from IPFS.
        
        Args:
            identifier: The CID of the content to retrieve
            container: Optional container name (not used in IPFS)
            options: Additional options for the retrieval operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # Get data from IPFS
        result = self.ipfs.ipfs_cat(identifier)
        
        # Update performance stats
        duration = time.time() - start_time
        self.performance_stats["retrieve"]["count"] += 1
        self.performance_stats["retrieve"]["total_time"] += duration
        self.performance_stats["retrieve"]["avg_time"] = (
            self.performance_stats["retrieve"]["total_time"] / self.performance_stats["retrieve"]["count"]
        )

        if result.get("success", False):
            return {
                "success": True,
                "data": result.get("data"),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result,
            }

        return {
            "success": False,
            "error": result.get("error", "Failed to retrieve data from IPFS"),
            "backend": self.get_name(),
            "identifier": identifier,
            "details": result,
        }

    def delete(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete data from IPFS.

        Note: In IPFS, content is immutable and content-addressed, so this
        effectively just unpins the content.
        
        Args:
            identifier: The CID of the content to unpin
            container: Optional container name (not used in IPFS)
            options: Additional options for the delete operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # Unpin the content
        result = self.ipfs.ipfs_pin_rm(identifier)
        
        # Update performance stats
        duration = time.time() - start_time
        self.performance_stats["delete"]["count"] += 1
        self.performance_stats["delete"]["total_time"] += duration
        self.performance_stats["delete"]["avg_time"] = (
            self.performance_stats["delete"]["total_time"] / self.performance_stats["delete"]["count"]
        )

        return {
            "success": result.get("success", False),
            "backend": self.get_name(),
            "identifier": identifier,
            "details": result,
        }

    def list(
        self,
        container: Optional[str] = None,
        prefix: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        List pinned items in IPFS.
        
        Args:
            container: Optional container name (not used in IPFS)
            prefix: Optional prefix to filter results by
            options: Additional options for the list operation
            
        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()
        
        # List pinned items
        result = self.ipfs.ipfs_pin_ls()
        
        # Update performance stats
        duration = time.time() - start_time
        self.performance_stats["list"]["count"] += 1
        self.performance_stats["list"]["total_time"] += duration
        self.performance_stats["list"]["avg_time"] = (
            self.performance_stats["list"]["total_time"] / self.performance_stats["list"]["count"]
        )

        if result.get("success", False):
            pins = result.get("pins", {})
            items = []

            for cid, pin_type in pins.items():
                # Apply prefix filter if provided
                if prefix and not cid.startswith(prefix):
                    continue

                items.append({"identifier": cid, "type": pin_type, "backend": self.get_name()})

            return {
                "success": True,
                "items": items,
                "backend": self.get_name(),
                "details": result,
            }

        return {
            "success": False,
            "error": result.get("error", "Failed to list pins in IPFS"),
            "backend": self.get_name(),
            "details": result,
        }

    def exists(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if content exists (is pinned) in IPFS.
        
        Args:
            identifier: The CID to check
            container: Optional container name (not used in IPFS)
            options: Additional options for the check operation
            
        Returns:
            Boolean indicating if the content exists and is pinned
        """
        options = options or {}
        
        # Check if pinned
        result = self.ipfs.ipfs_pin_ls(identifier)
        
        return result.get("success", False)
    
    def get_stats(
        self,
        identifier: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get statistics for content in IPFS.
        
        Args:
            identifier: Optional CID to get stats for
            options: Additional options for the stats operation
            
        Returns:
            Dictionary with statistics
        """
        options = options or {}
        
        if identifier:
            # Get stats for a specific CID
            result = self.ipfs.ipfs_object_stat(identifier)
            
            if result.get("success", False):
                return {
                    "success": True,
                    "stats": result.get("stats", {}),
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "details": result,
                }
            
            return {
                "success": False,
                "error": result.get("error", "Failed to get stats for IPFS object"),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result,
            }
        
        # Return backend performance stats
        return {
            "success": True,
            "stats": self.performance_stats,
            "backend": self.get_name(),
        }
    
    def add_content(self, *args, **kwargs):
        """Legacy method for backwards compatibility. Use store() instead."""
        return self.store(*args, **kwargs)

# Singleton instance
_instance = None

def get_instance(config=None):
    """Get or create a singleton instance of the backend."""
    global _instance
    if _instance is None:
        _instance = IPFSStorageBackend(config)
    return _instance
