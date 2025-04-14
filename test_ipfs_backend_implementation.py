"""
Test version of the fixed IPFS backend implementation.

This module provides a simplified version for testing without package dependencies.
"""

import logging
import time
import sys
import os
import glob
from typing import Dict, Any, Optional, Union, BinaryIO

# Configure logger
logger = logging.getLogger(__name__)

# Mock storage backend type for testing
class StorageBackendType:
    IPFS = "ipfs"

# Mock base storage class for testing
class BackendStorage:
    def __init__(self, backend_type, resources, metadata):
        self.backend_type = backend_type
        self.resources = resources
        self.metadata = metadata
    
    def get_name(self):
        return self.backend_type

class IPFSBackend(BackendStorage):
    """IPFS backend implementation."""
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize IPFS backend."""
        super().__init__(StorageBackendType.IPFS, resources, metadata)

        # Import dependencies with improved error handling
        ipfs_py_class = self._get_ipfs_py_class()
        
        # Initialize IPFS client
        self.ipfs = ipfs_py_class(resources, metadata)
        
        # Log the initialization status
        if hasattr(self.ipfs, "_mock_implementation") and self.ipfs._mock_implementation:
            logger.warning("IPFS backend initialized with mock implementation")
        else:
            logger.info("IPFS backend successfully initialized with real implementation")

    def _get_ipfs_py_class(self):
        """
        Helper method to obtain the ipfs_py class with proper error handling.
        This resolves the "missing ipfs_py client dependency" issue mentioned in the roadmap.
        
        Returns:
            The ipfs_py class or a mock implementation if not found
        """
        # First try: direct import from ipfs_kit_py.ipfs
        try:
            from ipfs_kit_py.ipfs import ipfs_py
            logger.info("Successfully imported ipfs_py from ipfs_kit_py.ipfs")
            return ipfs_py
        except ImportError as e1:
            logger.warning(f"Could not import ipfs_py from ipfs_kit_py.ipfs: {e1}")
        
        # Second try: import from the root ipfs module
        try:
            # Add the project root to the path
            project_root = os.path.dirname(os.path.abspath(__file__))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            # Try to import from ipfs module
            from ipfs import ipfs_py
            logger.info("Successfully imported ipfs_py from ipfs module")
            return ipfs_py
        except ImportError as e2:
            logger.warning(f"Could not import ipfs_py from ipfs module: {e2}")
        
        # Third try: find ipfs.py file in the project and import from it
        try:
            project_root = os.path.dirname(os.path.abspath(__file__))
            
            # Search for ipfs.py files
            potential_ipfs_files = glob.glob(os.path.join(project_root, "**", "ipfs.py"), recursive=True)
            if not potential_ipfs_files:
                # Try a more specific search
                specific_search_path = os.path.join(project_root, "ipfs_kit_py", "ipfs.py")
                if os.path.exists(specific_search_path):
                    potential_ipfs_files = [specific_search_path]
            
            if potential_ipfs_files:
                # Found at least one ipfs.py file, add its directory to sys.path
                ipfs_file = potential_ipfs_files[0]
                logger.info(f"Found ipfs.py file at: {ipfs_file}")
                
                ipfs_dir = os.path.dirname(ipfs_file)
                if ipfs_dir not in sys.path:
                    sys.path.insert(0, ipfs_dir)
                
                # Try to import the module
                try:
                    # Try relative module path
                    ipfs_module_path = os.path.relpath(ipfs_file, project_root).replace('/', '.').replace('\\', '.').replace('.py', '')
                    ipfs_module = __import__(ipfs_module_path, fromlist=['ipfs_py'])
                    logger.info(f"Successfully imported ipfs_py from module: {ipfs_module_path}")
                    return ipfs_module.ipfs_py
                except (ImportError, ValueError) as e:
                    logger.warning(f"Failed to import as module: {e}")
                    
                    # Try direct file import
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("ipfs_module", ipfs_file)
                    if spec and spec.loader:
                        ipfs_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(ipfs_module)
                        logger.info(f"Successfully loaded ipfs_py from file: {ipfs_file}")
                        if hasattr(ipfs_module, 'ipfs_py'):
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
                # For testing purposes, we'll make this method work with a simulated CID
                import hashlib
                if args and isinstance(args[0], bytes):
                    data = args[0]
                    # Generate a deterministic CID-like string based on content hash
                    h = hashlib.sha256(data).hexdigest()
                    cid = f"Qm{h[:44]}"  # Make it look like a CIDv0
                    return {"success": True, "Hash": cid, "cid": cid, "Size": len(data)}
                return {"success": False, "error": "Mock IPFS implementation", "error_type": "MockImplementation"}
            
            def ipfs_cat(self, *args, **kwargs):
                # For testing purposes, return the CID as content
                if args and isinstance(args[0], str):
                    cid = args[0]
                    # Generate predictable content based on CID
                    content = f"Mock content for CID: {cid}".encode("utf-8")
                    return {"success": True, "data": content}
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
                return {"success": True, "metadata": args[1] if len(args) > 1 else {}}
            
            def __getattr__(self, name):
                # Handle any method call with a standard error response
                def method(*args, **kwargs):
                    return {"success": False, "error": f"Mock IPFS implementation (method: {name})", "error_type": "MockImplementation"}
                return method
        
        return MockIPFSPy

    def store(
        self,
        data: Union[bytes, BinaryIO, str],
        container: Optional[str] = None,
        path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store data in IPFS."""
        options = options or {}

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
            cid = result.get("Hash") or result.get("cid")
            if cid:
                self.ipfs.ipfs_add_metadata(
                    cid, {"mcp_added": time.time(), "mcp_backend": self.get_name()}
                )

            return {
                "success": True,
                "identifier": cid,
                "backend": self.get_name(),
                "details": result,
            }

        return {
            "success": False,
            "error": result.get("error", "Failed to store data in IPFS"),
            "backend": self.get_name(),
            "details": result,
        }

    def retrieve(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Retrieve data from IPFS."""
        options = options or {}

        # Get data from IPFS
        result = self.ipfs.ipfs_cat(identifier)

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