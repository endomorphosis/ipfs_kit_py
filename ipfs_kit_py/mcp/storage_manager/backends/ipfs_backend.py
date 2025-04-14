"""
IPFS backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for IPFS to support
content storage and retrieval through the IPFS network.
"""

import logging
import time
import sys
import os
import glob
from typing import Dict, Any, Optional, Union, BinaryIO

# Import the base class and storage types
from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType

# Import performance monitoring
from ..monitoring import IPFSPerformanceMonitor, PerformanceTracker, OperationType

# Import WebSocket notification system
from ...streaming.websocket_notifications import get_ws_manager, EventType

# Configure logger
logger = logging.getLogger(__name__)


class IPFSBackend(BackendStorage):
    """IPFS backend implementation."""
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize IPFS backend."""
        super().__init__(StorageBackendType.IPFS, resources, metadata)
        
        # Set up performance monitoring
        self.monitor = IPFSPerformanceMonitor(
            metrics_file=metadata.get("performance_metrics_file", None)
        )
        logger.info("IPFS performance monitoring initialized")

        # Import dependencies with improved error handling
        ipfs_py_class = self._get_ipfs_py_class()
        
        # Initialize IPFS client
        self.ipfs = ipfs_py_class(resources, metadata)
        
        # Log the initialization status
        if hasattr(self.ipfs, "_mock_implementation") and self.ipfs._mock_implementation:
            logger.warning("IPFS backend initialized with mock implementation")
        else:
            logger.info("IPFS backend successfully initialized with real implementation")
    
    def get_name(self) -> str:
        """Get the name of this backend implementation.
        
        Returns:
            String representation of the backend name
        """
        return "ipfs"

    def _get_ipfs_py_class(self):
        """
        Helper method to obtain the ipfs_py class with proper error handling.
        This resolves the "missing ipfs_py client dependency" issue mentioned in the roadmap.
        
        Returns:
            The ipfs_py class or a mock implementation if not found
        """
        # First try: import directly from the root ipfs.py module
        try:
            from ipfs_kit_py.ipfs import ipfs_py
            logger.info("Successfully imported ipfs_py from ipfs_kit_py.ipfs")
            return ipfs_py
        except ImportError as e:
            logger.warning(f"Could not import ipfs_py from ipfs_kit_py.ipfs: {e}")
        
        # Second try: import from ipfs_client directly
        try:
            from ipfs_kit_py.ipfs_client import ipfs_py
            logger.info("Successfully imported ipfs_py from ipfs_kit_py.ipfs_client")
            return ipfs_py
        except ImportError as e:
            logger.warning(f"Could not import ipfs_py from ipfs_kit_py.ipfs_client: {e}")
        
        # Third try: direct import attempt after fixing potential absolute/relative import issues
        try:
            import sys
            import os
            # Add the parent directory to path to ensure module can be found
            parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            if parent_dir not in sys.path:
                sys.path.append(parent_dir)
            
            # Try importing after path adjustment
            from ipfs_kit_py import ipfs
            logger.info("Successfully imported ipfs_py after path adjustment")
            return ipfs.ipfs_py
        except ImportError as e:
            logger.warning(f"Could not import ipfs_py after path adjustment: {e}")
            
        # Fourth try: direct file import using importlib
        try:
            import importlib.util
            import os
            
            # Get the absolute path to the ipfs.py file
            ipfs_py_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
                'ipfs_kit_py', 'ipfs.py'
            )
            
            # Check if the file exists
            if os.path.exists(ipfs_py_path):
                # Load the module from the file path
                spec = importlib.util.spec_from_file_location("ipfs_module", ipfs_py_path)
                ipfs_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(ipfs_module)
                
                # Get the ipfs_py class from the loaded module
                if hasattr(ipfs_module, 'ipfs_py'):
                    logger.info(f"Successfully imported ipfs_py from file: {ipfs_py_path}")
                    return ipfs_module.ipfs_py
                else:
                    logger.warning(f"File {ipfs_py_path} exists but does not contain ipfs_py class")
            else:
                logger.warning(f"Could not find ipfs.py at path: {ipfs_py_path}")
        except Exception as e:
            logger.warning(f"Error importing ipfs_py from file: {e}")

        # Fallback: create a mock implementation if all imports fail
        logger.error("Creating mock implementation for ipfs_py since all import attempts failed.")

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
                def mock_method(*args, **kwargs):
                    return {"success": False, "error": f"Mock IPFS implementation - {name} not implemented", "error_type": "MockImplementation"}
                return mock_method
        return MockIPFSPy

    # Renamed from 'store' to match base class and made synchronous
    def add_content(self, content: Union[str, bytes, BinaryIO], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add content to IPFS.

        Args:
            content: Content to add (can be file path, bytes, or file-like object)
            metadata: Optional metadata to associate with the content
            
        Returns:
            Dict with operation result including CID
        """
        # Track performance for this operation
        with PerformanceTracker(self.monitor, OperationType.ADD) as tracker:
            try:
                # Handle different content types
                content_size = 0
                if isinstance(content, str) and os.path.isfile(content):
                    # Content is a file path
                    content_size = os.path.getsize(content)
                    tracker.set_size(content_size)
                    # Use ipfs_add_file which handles file paths
                    with open(content, 'rb') as f:
                        result = self.ipfs.ipfs_add_file(f)
                elif isinstance(content, (bytes, bytearray)):
                    # Content is bytes
                    content_size = len(content)
                    tracker.set_size(content_size)
                    result = self.ipfs.ipfs_add_bytes(content)
                elif hasattr(content, 'read'):
                    # Content is a file-like object
                    # ipfs_add_file handles file-like objects
                    result = self.ipfs.ipfs_add_file(content)
                else:
                    # Invalid content type
                    return {"success": False, "error": f"Unsupported content type: {type(content)}", "error_type": "InvalidContentType"}
                    
                # Add metadata if provided and add_content was successful
                cid = result.get("Hash") or result.get("cid") # Get CID from result
                if result.get("success") and cid:
                    if metadata and hasattr(self.ipfs, "ipfs_add_metadata"):
                        metadata_result = self.ipfs.ipfs_add_metadata(cid, metadata)
                        if not metadata_result.get("success"):
                            # Still return success for content, but include metadata error
                            result["metadata_error"] = metadata_result.get("error")
                    
                    # Send WebSocket notification for successful content addition
                    ws_manager = get_ws_manager()
                    notification_data = {
                        "type": EventType.CONTENT_ADDED,
                        "cid": cid,
                        "backend": self.backend_type.value,
                        "timestamp": time.time(),
                        "size": content_size,
                        "metadata": metadata or {}
                    }
                    ws_manager.notify("content", notification_data)
                    
                    # Return standardized success response
                    return {
                        "success": True,
                        "identifier": cid,
                        "backend": self.backend_type.value,
                        "details": result,
                    }
                else:
                    # Return standardized error response
                    return {
                        "success": False,
                        "error": result.get("error", "Failed to store data in IPFS"),
                        "backend": self.backend_type.value,
                        "details": result,
                    }
            except Exception as e:
                # Handle any exceptions
                return {"success": False, "error": str(e), "backend": self.backend_type.value, "error_type": "IPFSBackendError"}

    # Renamed from 'retrieve' to match base class and made synchronous
    def get_content(self, content_id: str) -> Dict[str, Any]:
        """Retrieve content from IPFS.

        Args:
            content_id: CID of the content to retrieve

        Returns:
            Dict with operation result including content data
        """
        # Track performance for this operation
        with PerformanceTracker(self.monitor, OperationType.GET) as tracker:
            try:
                # ipfs_cat returns the result dict which includes 'data'
                result = self.ipfs.ipfs_cat(content_id)
                # Ensure the structure matches expected return (data field)
                if result.get("success"):
                    # Set the data size for performance tracking
                    if result.get("data") and isinstance(result.get("data"), (bytes, bytearray)):
                        tracker.set_size(len(result.get("data")))
                        
                    # Send WebSocket notification for content retrieval
                    ws_manager = get_ws_manager()
                    notification_data = {
                        "type": EventType.CONTENT_RETRIEVED,
                        "cid": content_id,
                        "backend": self.backend_type.value,
                        "timestamp": time.time(),
                        "size": len(result.get("data")) if result.get("data") and isinstance(result.get("data"), (bytes, bytearray)) else 0
                    }
                    ws_manager.notify("content", notification_data)
                        
                    return {
                        "success": True,
                        "data": result.get("data"),
                        "backend": self.backend_type.value,
                        "identifier": content_id,
                        "details": result
                    }
                else:
                    # Standardize error response
                    return {
                        "success": False,
                        "error": result.get("error", "Failed to retrieve data from IPFS"),
                        "backend": self.backend_type.value,
                        "identifier": content_id,
                        "details": result,
                    }
            except Exception as e:
                return {"success": False, "error": str(e), "backend": self.backend_type.value, "error_type": "IPFSBackendError"}

    # Renamed from 'delete' to match base class and made synchronous
    def remove_content(self, content_id: str) -> Dict[str, Any]:
        """Remove content from IPFS (unpin).

        Args:
            content_id: CID of the content to remove

        Returns:
            Dict with operation result
        """
        # Track performance for this operation
        with PerformanceTracker(self.monitor, OperationType.UNPIN):
            try:
                result = self.ipfs.ipfs_pin_rm(content_id)
                
                # Send WebSocket notification for content removal
                if result.get("success", False):
                    ws_manager = get_ws_manager()
                    notification_data = {
                        "type": EventType.CONTENT_REMOVED,
                        "cid": content_id,
                        "backend": self.backend_type.value,
                        "timestamp": time.time()
                    }
                    ws_manager.notify("content", notification_data)
                
                # Standardize return format slightly
                return {
                    "success": result.get("success", False),
                    "backend": self.backend_type.value,
                    "identifier": content_id,
                    "details": result
                }
            except Exception as e:
                return {"success": False, "error": str(e), "backend": self.backend_type.value, "error_type": "IPFSBackendError"}

    # Kept name, made synchronous
    def get_metadata(self, content_id: str) -> Dict[str, Any]:
        """Get metadata for content in IPFS (uses object stat).

        Args:
            content_id: CID of the content

        Returns:
            Dict with operation result including basic object stats as metadata
        """
        # Track performance for this operation
        with PerformanceTracker(self.monitor, OperationType.STAT):
            try:
                # Use object_stat for basic metadata
                result = self.ipfs.ipfs_object_stat(content_id)

                if result.get("success"):
                    # Format the stats into the expected metadata structure
                    return {
                        "success": True,
                        "metadata": {
                            "size": result.get("CumulativeSize", 0),
                            "links": result.get("NumLinks", 0),
                            "blocks": result.get("Blocks", 1), # Assuming 1 block if not specified
                            "backend": self.backend_type.value,
                            "data_size": result.get("DataSize", 0),
                            "link_size": result.get("LinksSize", 0),
                            "cid_version": 0,  # Assume v0 CID unless specified otherwise
                            "created": time.time(),  # Add current timestamp as creation time
                            "last_accessed": time.time(),  # Add current timestamp as last accessed
                            "content_type": "application/octet-stream",  # Default content type
                        },
                        "backend": self.backend_type.value,
                        "identifier": content_id,
                        "details": result
                    }
                else:
                    # Standardize error response
                    return {
                        "success": False,
                        "error": result.get("error", "Failed to get metadata from IPFS"),
                        "backend": self.backend_type.value,
                        "identifier": content_id,
                        "details": result,
                    }
            except Exception as e:
                return {"success": False, "error": str(e), "backend": self.backend_type.value, "error_type": "IPFSBackendError"}

    # --- IPFS Specific Methods (Not part of base interface) ---

    def pin_add(self, content_id: str) -> Dict[str, Any]:
        """Pin content in IPFS.

        Args:
            content_id: CID of the content to pin

        Returns:
            Dict with operation result
        """
        try:
            # Assuming ipfs_pin_add exists and is synchronous
            result = self.ipfs.ipfs_pin_add(content_id)
            
            # Send WebSocket notification for successful pin operation
            if result.get("success", False):
                ws_manager = get_ws_manager()
                notification_data = {
                    "type": EventType.PIN_ADDED,
                    "cid": content_id,
                    "backend": self.backend_type.value,
                    "timestamp": time.time()
                }
                ws_manager.notify("pinning", notification_data)
                
            return result
        except AttributeError:
             # Fallback if ipfs_pin_add doesn't exist on the client
             logger.warning("ipfs_pin_add method not found on ipfs client, attempting direct command")
             result = self.ipfs.run_ipfs_command(["pin", "add", content_id])
             if result.get("success"):
                 result["Pins"] = [content_id] # Simulate expected output
                 
                 # Send WebSocket notification for successful pin operation
                 ws_manager = get_ws_manager()
                 notification_data = {
                     "type": EventType.PIN_ADDED,
                     "cid": content_id,
                     "backend": self.backend_type.value,
                     "timestamp": time.time()
                 }
                 ws_manager.notify("pinning", notification_data)
                 
             return result
        except Exception as e:
            return {"success": False, "error": str(e), "backend": self.backend_type.value, "error_type": "IPFSBackendError"}

    def pin_ls(self, cid: Optional[str] = None) -> Dict[str, Any]:
        """List pinned content in IPFS.

        Args:
            cid: Optional CID to filter by

        Returns:
            Dict with operation result including list of pins
        """
        try:
            return self.ipfs.ipfs_pin_ls(cid)
        except Exception as e:
            return {"success": False, "error": str(e), "backend": self.backend_type.value, "error_type": "IPFSBackendError"}

    def pin_rm(self, content_id: str) -> Dict[str, Any]:
        """Unpin content in IPFS.

        Args:
            content_id: CID of the content to unpin

        Returns:
            Dict with operation result
        """
        try:
            result = self.ipfs.ipfs_pin_rm(content_id)
            
            # Send WebSocket notification for successful unpin operation
            if result.get("success", False):
                ws_manager = get_ws_manager()
                notification_data = {
                    "type": EventType.PIN_REMOVED,
                    "cid": content_id,
                    "backend": self.backend_type.value,
                    "timestamp": time.time()
                }
                ws_manager.notify("pinning", notification_data)
                
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "backend": self.backend_type.value, "error_type": "IPFSBackendError"}

    # Added exists method (not in base class but useful)
    def exists(self, identifier: str, **kwargs) -> bool:
         """Check if content exists (is pinned) in IPFS."""
         try:
             result = self.ipfs.ipfs_pin_ls(identifier)
             # Check if the specific CID is in the returned pins
             return result.get("success", False) and identifier in result.get("pins", {})
         except Exception:
             return False

    # Added list method (not in base class but useful)
    def list(self, prefix: Optional[str] = None, **kwargs) -> Dict[str, Any]:
         """List pinned items in IPFS."""
         try:
             result = self.ipfs.ipfs_pin_ls()
             if result.get("success", False):
                 pins = result.get("pins", {})
                 items = []
                 for cid, pin_info in pins.items():
                     if prefix and not cid.startswith(prefix):
                         continue
                     items.append({"identifier": cid, "type": pin_info.get("Type"), "backend": self.backend_type.value}) # Use backend_type.value
                 return {
                     "success": True,
                     "items": items,
                     "backend": self.backend_type.value, # Use backend_type.value
                     "details": result,
                 }
             else:
                 return result # Return error result
         except Exception as e: # Removed trailing content after 'e:'
             return {"success": False, "error": str(e), "backend": self.backend_type.value, "error_type": "IPFSBackendError"}

    # Added update_metadata (not in base class, placeholder) - Made synchronous
    def update_metadata(self, identifier: str, metadata: Dict[str, Any], **kwargs) -> Dict[str, Any]: # Corrected definition
         """Update metadata for IPFS content."""
         try:
             if hasattr(self.ipfs, 'ipfs_add_metadata'):
                 result = self.ipfs.ipfs_add_metadata(identifier, metadata)
                 return {
                     "success": result.get("success", False),
                     "backend": self.backend_type.value, # Use backend_type.value
                     "identifier": identifier,
                     "details": result,
                 }
             else:
                 logger.warning(f"update_metadata called for {identifier}, but ipfs_add_metadata not available.")
                 return {"success": False, "error": "Metadata update not supported by this IPFS client", "backend": self.backend_type.value, "error_type": "NotSupported"}
         except Exception as e:
             return {"success": False, "error": str(e), "backend": self.backend_type.value, "error_type": "IPFSBackendError"}

    # New method to get performance metrics
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for IPFS operations.
        
        This method addresses the 'Test performance monitoring after fix' 
        item in the MCP roadmap.
        
        Returns:
            Dict with detailed performance metrics
        """
        return self.monitor.get_metrics()
    
    # New method to get detailed stats for a specific operation
    def get_operation_stats(self, operation_type: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific operation type.
        
        Args:
            operation_type: Type of operation (use OperationType constants)
            
        Returns:
            Dict with detailed statistics for the operation
        """
        return self.monitor.get_operation_stats(operation_type)
