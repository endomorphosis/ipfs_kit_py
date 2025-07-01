"""
Fixed IPFS backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for IPFS with improved
import handling to fix the missing dependency issue identified in the MCP roadmap.
"""

import logging
import time
import sys
import os
import glob
from typing import Dict, Any, Optional, Union, BinaryIO
from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


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
            project_root = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "..", ".."
            ))
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
            project_root = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "..", ".."
            ))

            # Search for ipfs.py files
            potential_ipfs_files = glob.glob(os.path.join(project_root, "**", "ipfs.py"), recursive=True)
            if not potential_ipfs_files:
                # Try a more specific search that matches the project structure
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

                # If the file is in a module, import it directly
                module_name = os.path.relpath(ipfs_file, project_root).replace('/', '.').replace('\\', '.').replace('.py', '')
                try:
                    # Try to import using the module name
                    ipfs_module = __import__(module_name, fromlist=['ipfs_py'])
                    logger.info(f"Successfully imported ipfs_py from module: {module_name}")
                    return ipfs_module.ipfs_py
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
        """
        options = options or {}

        # Unpin the content
        result = self.ipfs.ipfs_pin_rm(identifier)

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
        """List pinned items in IPFS."""
        options = options or {}

        # List pinned items
        result = self.ipfs.ipfs_pin_ls()

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
        """Check if content exists (is pinned) in IPFS."""
        options = options or {}

        # Check if pinned
        result = self.ipfs.ipfs_pin_ls(identifier)

        return result.get("success", False)

    def get_metadata(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get metadata for IPFS content."""
        options = options or {}

        # Get object stats
        result = self.ipfs.ipfs_object_stat(identifier)

        if result.get("success", False):
            return {
                "success": True,
                "metadata": {
                    "size": result.get("CumulativeSize", 0),
                    "links": result.get("NumLinks", 0),
                    "blocks": 1,  # Simplified
                    "backend": self.get_name(),
                },
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result,
            }

        return {
            "success": False,
            "error": result.get("error", "Failed to get metadata from IPFS"),
            "backend": self.get_name(),
            "identifier": identifier,
            "details": result,
        }

    def update_metadata(
        self,
        identifier: str,
        metadata: Dict[str, Any],
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update metadata for IPFS content.

        Note: Since IPFS content is immutable, this method stores metadata separately
        using the IPFS client's metadata storage capabilities.

        Args:
            identifier: Content identifier (CID)
            metadata: Metadata to update
            container: Not used for IPFS
            options: Backend-specific options

        Returns:
            Dictionary with operation result
        """
        options = options or {}

        try:
            # Try to use the ipfs client's metadata API if available
            if hasattr(self.ipfs, 'ipfs_add_metadata'):
                result = self.ipfs.ipfs_add_metadata(identifier, metadata)
                return {
                    "success": result.get("success", False),
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "details": result,
                }

            # Fall back to a more generic approach if specific method not available
            logger.warning(f"ipfs_add_metadata not available for {identifier}, using alternative approach")

            # Create a new metadata object and link it to the original content
            # Store the metadata as JSON
            import json
            metadata_str = json.dumps({
                "target_cid": identifier,
                "mcp_metadata": metadata,
                "mcp_timestamp": time.time(),
                "mcp_backend": self.get_name()
            })

            # Add the metadata to IPFS
            result = self.ipfs.ipfs_add_bytes(metadata_str.encode('utf-8'))

            if result.get("success", False):
                metadata_cid = result.get("Hash") or result.get("cid")
                return {
                    "success": True,
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "metadata_cid": metadata_cid,
                    "details": result,
                }

            return {
                "success": False,
                "error": result.get("error", "Failed to store metadata in IPFS"),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result,
            }

        except Exception as e:
            error_msg = f"Error updating metadata for {identifier}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "backend": self.get_name(),
                "identifier": identifier,
            }
