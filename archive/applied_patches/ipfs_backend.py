#!/usr/bin/env python3
"""
IPFS Storage Backend

This module provides IPFS storage capabilities through a standardized backend interface.
It dynamically loads the ipfs_py library if available or creates a mock implementation.

Features:
- Standard storage operations (store, retrieve, delete, list)
- Content pinning management
- DHT (Distributed Hash Table) operations
- Performance statistics tracking
- Standardized error handling
"""

import os
import sys
import glob
import importlib
import logging
import time
import traceback
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ipfs_backend")

# Import the standardized error handling
try:
    from mcp_error_handling import (
        create_error_response, 
        handle_backend_error, 
        handle_daemon_error,
        handle_exception
    )
    STANDARD_ERROR_HANDLING = True
    logger.info("Using standardized MCP error handling")
except ImportError:
    STANDARD_ERROR_HANDLING = False
    logger.warning("Standardized MCP error handling not available, using internal handlers")

class IPFSErrorHandler:
    """
    Standardized error handling for IPFS operations.
    Provides consistent error formatting and categorization.
    """

    # Error categories
    NETWORK_ERROR = "NetworkError"
    TIMEOUT_ERROR = "TimeoutError"
    NOT_FOUND_ERROR = "NotFoundError"
    PERMISSION_ERROR = "PermissionError"
    VALIDATION_ERROR = "ValidationError"
    DEPENDENCY_ERROR = "DependencyError"
    INTERNAL_ERROR = "InternalError"
    UNKNOWN_ERROR = "UnknownError"

    # MCP error code mapping
    MCP_ERROR_MAPPING = {
        NETWORK_ERROR: "UPSTREAM_ERROR",
        TIMEOUT_ERROR: "TIMEOUT",
        NOT_FOUND_ERROR: "CONTENT_NOT_FOUND",
        PERMISSION_ERROR: "UNAUTHORIZED",
        VALIDATION_ERROR: "VALIDATION_ERROR",
        DEPENDENCY_ERROR: "DAEMON_ERROR",
        INTERNAL_ERROR: "INTERNAL_ERROR", 
        UNKNOWN_ERROR: "INTERNAL_ERROR"
    }

    @staticmethod
    def format_error(error_type: str, message: str, details: Optional[Any] = None) -> Dict[str, Any]:
        """
        Format an error response in a standardized structure.

        Args:
            error_type: Category of error
            message: Human-readable error message
            details: Optional additional details about the error

        Returns:
            Standardized error response dictionary
        """
        # Use the standardized error handling if available
        if STANDARD_ERROR_HANDLING:
            # Map our error type to MCP error codes
            mcp_error_code = IPFSErrorHandler.MCP_ERROR_MAPPING.get(error_type, "INTERNAL_ERROR")
            return create_error_response(
                code=mcp_error_code,
                message_override=message,
                details=details,
                doc_category="storage"
            )
        
        # Fall back to original format if standardized handling not available
        error_response = {
            "success": False,
            "error_type": error_type,
            "error": message,
            "timestamp": time.time()
        }

        if details:
            error_response["details"] = details

        return error_response

    @staticmethod
    def handle_exception(e: Exception, operation: str) -> Dict[str, Any]:
        """
        Convert an exception into a standardized error response.

        Args:
            e: The caught exception
            operation: The operation that was being performed

        Returns:
            Standardized error response dictionary
        """
        # Use standardized error handling if available
        if STANDARD_ERROR_HANDLING:
            return handle_backend_error(e, backend_name="ipfs", endpoint=f"/ipfs/{operation}")
            
        # Fall back to original implementation
        error_type = IPFSErrorHandler.UNKNOWN_ERROR

        # Categorize based on exception type
        if isinstance(e, (ConnectionError, ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError)):
            error_type = IPFSErrorHandler.NETWORK_ERROR
        elif isinstance(e, TimeoutError):
            error_type = IPFSErrorHandler.TIMEOUT_ERROR
        elif isinstance(e, FileNotFoundError):
            error_type = IPFSErrorHandler.NOT_FOUND_ERROR
        elif isinstance(e, (PermissionError, OSError)):
            error_type = IPFSErrorHandler.PERMISSION_ERROR
        elif isinstance(e, (ValueError, TypeError)):
            error_type = IPFSErrorHandler.VALIDATION_ERROR
        elif isinstance(e, ImportError):
            error_type = IPFSErrorHandler.DEPENDENCY_ERROR
        elif isinstance(e, RuntimeError):
            error_type = IPFSErrorHandler.INTERNAL_ERROR

        # Log the exception with traceback for debugging
        logger.error(f"Error during {operation}: {str(e)}", exc_info=True)

        # Get stack trace for detailed debugging
        stack_trace = traceback.format_exc()

        return IPFSErrorHandler.format_error(
            error_type=error_type,
            message=f"Error during {operation}: {str(e)}",
            details={
                "exception_type": e.__class__.__name__,
                "stack_trace": stack_trace
            }
        )

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
            "dht_provide": {"count": 0, "total_time": 0, "avg_time": 0},
            "dht_find_provider": {"count": 0, "total_time": 0, "avg_time": 0},
            "dht_find_peer": {"count": 0, "total_time": 0, "avg_time": 0},
            "dht_query": {"count": 0, "total_time": 0, "avg_time": 0},
        }

        # Initialize the IPFS client
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the IPFS client."""
        # Load IPFS implementation
        try:
            self.ipfs = self._load_ipfs_implementation()

            # Check if we got a mock implementation
            self.is_mock = getattr(self.ipfs, "_mock_implementation", False)

            if self.is_mock:
                logger.warning("Using mock IPFS implementation - limited functionality available")
            else:
                logger.info("IPFS backend initialized successfully")

            self.initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize IPFS backend: {e}", exc_info=True)
            self.is_mock = True
            self.initialized = False

            # Create mock implementation as fallback
            self.ipfs = self._create_mock_implementation()

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
            import ipfs_py # type: ignore
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
                            import importlib.util # type: ignore
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
        return self._create_mock_implementation()

    def _create_mock_implementation(self):
        """
        Create a mock implementation of the IPFS client.
        This is used as a fallback when the real IPFS client can't be loaded.

        Returns:
            A mock IPFS client that returns appropriate error responses
        """
        logger.warning("Creating mock IPFS implementation due to initialization failure")

        class MockIPFSPy:
            """Mock implementation of ipfs_py for when the real one can't be imported."""
            _mock_implementation = True

            def __init__(self):
                self.logger = logging.getLogger("mock_ipfs_py")
                self.logger.warning("Using mock IPFS implementation - limited functionality available")

                # Add some mock data to simulate a minimally functional implementation
                self.mock_pins: Dict[str, str] = {}
                self.mock_objects: Dict[str, Any] = {}

            def ipfs_add_file(self, file_obj, *args, **kwargs):
                """Mock file addition that returns a consistent error."""
                mock_cid = "mock-unavailable-cid-" + str(time.time())
                return IPFSErrorHandler.format_error(
                    IPFSErrorHandler.DEPENDENCY_ERROR,
                    "IPFS implementation unavailable (mock mode)",
                    {"mock_cid": mock_cid, "method": "ipfs_add_file"}
                )

            def ipfs_add_bytes(self, data, *args, **kwargs):
                """Mock bytes addition that returns a consistent error."""
                mock_cid = "mock-unavailable-cid-" + str(time.time())
                return IPFSErrorHandler.format_error(
                    IPFSErrorHandler.DEPENDENCY_ERROR,
                    "IPFS implementation unavailable (mock mode)",
                    {"mock_cid": mock_cid, "method": "ipfs_add_bytes"}
                )

            def ipfs_cat(self, cid, *args, **kwargs):
                """Mock content retrieval that returns a consistent error."""
                return IPFSErrorHandler.format_error(
                    IPFSErrorHandler.DEPENDENCY_ERROR,
                    "IPFS implementation unavailable (mock mode)",
                    {"mock_cid": cid, "method": "ipfs_cat"}
                )

            # Explicitly define methods to satisfy Pylance, returning standard error
            def ipfs_pin_add(self, cid, *args, **kwargs): # type: ignore
                """Mock pin add that simulates success but warns about mock mode."""
                self.mock_pins[cid] = "recursive"
                return {
                    "success": True,
                    "pins": [cid],
                    "warning": "This is a mock implementation. Content is not actually pinned.",
                    "error_type": "MockImplementation"
                }

            def ipfs_pin_rm(self, cid, *args, **kwargs): # type: ignore
                """Mock pin removal that simulates success for user experience."""
                if cid in self.mock_pins:
                    del self.mock_pins[cid]
                return {
                    "success": True,
                    "pins": [cid],
                    "warning": "This is a mock implementation. No actual pin was removed.",
                    "error_type": "MockImplementation"
                }

            def ipfs_pin_ls(self, *args, **kwargs): # type: ignore
                 """Mock pin list that returns mock pins."""
                 return { "success": True, "pins": self.mock_pins, "error_type": "MockImplementation" }

            def ipfs_object_stat(self, cid, *args, **kwargs): # type: ignore
                 """Mock object stat that returns placeholder data."""
                 return {
                     "success": True,
                     "stats": {"NumLinks": 0, "BlockSize": 0, "LinksSize": 0, "DataSize": 0, "CumulativeSize": 0},
                     "warning": "This is a mock implementation. Stats are not accurate.",
                     "error_type": "MockImplementation"
                 }

            def ipfs_add_metadata(self, *args, **kwargs):
                """Mock metadata addition."""
                return IPFSErrorHandler.format_error(
                    IPFSErrorHandler.DEPENDENCY_ERROR,
                    "IPFS implementation unavailable (mock mode)",
                    {"method": "ipfs_add_metadata"}
                )

            # Explicitly define DHT methods
            def ipfs_dht_provide(self, *args, **kwargs):
                return self.__getattr__('ipfs_dht_provide')(*args, **kwargs)

            def ipfs_dht_find_providers(self, *args, **kwargs):
                return IPFSErrorHandler.format_error(
                    IPFSErrorHandler.DEPENDENCY_ERROR,
                    "IPFS implementation unavailable (mock mode)",
                    {"method": "ipfs_dht_find_providers"}
                )

            def ipfs_dht_find_peer(self, *args, **kwargs):
                return IPFSErrorHandler.format_error(
                    IPFSErrorHandler.DEPENDENCY_ERROR,
                    "IPFS implementation unavailable (mock mode)",
                    {"method": "ipfs_dht_find_peer"}
                )

            def ipfs_dht_query(self, *args, **kwargs):
                return IPFSErrorHandler.format_error(
                    IPFSErrorHandler.DEPENDENCY_ERROR,
                    "IPFS implementation unavailable (mock mode)",
                    {"method": "ipfs_dht_query"}
                )

            def __getattr__(self, name):
                """
                Handle any method call with a standardized error response.
                This ensures all API calls have a consistent response format.
                """
                def method(*args, **kwargs):
                    return IPFSErrorHandler.format_error(
                        IPFSErrorHandler.DEPENDENCY_ERROR,
                        f"IPFS implementation unavailable (mock mode) - method: {name}",
                        {"method": name}
                    )
                return method

        return MockIPFSPy()

    def _update_perf_stats(self, operation: str, duration: float):
        """Helper to update performance stats, ensuring float division."""
        stats = self.performance_stats[operation]
        stats["count"] = int(stats["count"]) + 1
        stats["total_time"] = float(stats["total_time"]) + duration
        count = stats["count"]
        if count > 0:
            stats["avg_time"] = float(stats["total_time"]) / count


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

        try:
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

            cid = result.get("cid") # Get CID early for pinning
            success = result.get("success", False)

            if success and cid and options.get("pin", True):
                # Pin the content if requested (default: True)
                pin_result = self.ipfs.ipfs_pin_add(cid)
                result["pin_result"] = pin_result

            # Update performance stats
            duration = time.time() - start_time
            self._update_perf_stats("store", duration)

            return {
                "success": success,
                "identifier": cid,
                "backend": self.get_name(),
                "details": result,
            }
        except Exception as e:
            return IPFSErrorHandler.handle_exception(e, "store")

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

        try:
            # Get data from IPFS
            result = self.ipfs.ipfs_cat(identifier)

            # Update performance stats
            duration = time.time() - start_time
            self._update_perf_stats("retrieve", duration)

            success = result.get("success", False)
            data_content = result.get("data") if success else None

            return {
                "success": success,
                "data": data_content,
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result if not success else {"message": "Data retrieved"}, # Avoid duplicating data
            }
        except Exception as e:
            return IPFSErrorHandler.handle_exception(e, "retrieve")

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

        try:
            # Unpin the content
            result = self.ipfs.ipfs_pin_rm(identifier)

            # Update performance stats
            duration = time.time() - start_time
            self._update_perf_stats("delete", duration)

            return {
                "success": result.get("success", False),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result,
            }
        except Exception as e:
            return IPFSErrorHandler.handle_exception(e, "delete")

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

        try:
            # List pinned items
            result = self.ipfs.ipfs_pin_ls()

            # Update performance stats
            duration = time.time() - start_time
            self._update_perf_stats("list", duration)

            success = result.get("success", False)
            items = []
            if success:
                pins = result.get("pins", {})
                for cid, pin_info in pins.items(): # Adapt to potential dict format
                    pin_type = pin_info.get("Type", "unknown") if isinstance(pin_info, dict) else pin_info
                    # Apply prefix filter if provided
                    if prefix and not cid.startswith(prefix):
                        continue
                    items.append({"identifier": cid, "type": pin_type, "backend": self.get_name()})

            return {
                "success": success,
                "items": items,
                "backend": self.get_name(),
                "details": result if not success else {"count": len(items)}, # Avoid large pin list in details
            }
        except Exception as e:
            return IPFSErrorHandler.handle_exception(e, "list")

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

        try:
            # Check if pinned by attempting to list the specific pin
            # Pass the identifier as 'arg' based on typical API usage
            result = self.ipfs.ipfs_pin_ls(arg=identifier)

            # Check if the result indicates the pin exists.
            # The exact structure might vary, check common patterns.
            if result.get("success", False):
                 pins = result.get("pins", {})
                 # Check if the identifier is a key in the pins dictionary
                 return identifier in pins
            return False
        except Exception as e:
            logger.error(f"Error during exists check for {identifier}: {e}", exc_info=True)
            return False

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

        try:
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
            # Ensure stats values are JSON serializable (convert floats if needed)
            serializable_stats = {
                op: {k: float(v) if isinstance(v, float) else v for k, v in data.items()}
                for op, data in self.performance_stats.items()
            }
            return {
                "success": True,
                "stats": serializable_stats,
                "backend": self.get_name(),
            }
        except Exception as e:
            return IPFSErrorHandler.handle_exception(e, "get_stats")

    def add_content(self, *args, **kwargs):
        """Legacy method for backwards compatibility. Use store() instead."""
        return self.store(*args, **kwargs)

    # ---- DHT Operations ----

    def dht_provide(
        self,
        identifier: str,
        recursive: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Announce to the network that we are providing content with the given CID.

        This improves content discoverability in the IPFS network as it makes the
        local node a provider of the specific content, enabling other peers to find it.

        Args:
            identifier: The CID of the content to provide
            recursive: Whether to recursively provide entire DAG (for directory CIDs)
            options: Additional options for the DHT provide operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()

        try:
            # Call the DHT provide method
            result = self.ipfs.ipfs_dht_provide(identifier, recursive=recursive)

            # Update performance stats
            duration = time.time() - start_time
            self._update_perf_stats("dht_provide", duration)

            return {
                "success": result.get("success", False),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result,
            }
        except Exception as e:
            return IPFSErrorHandler.handle_exception(e, "dht_provide")

    def dht_find_providers(
        self,
        identifier: str,
        num_providers: int = 20,
        timeout: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Find providers for the specified content in the IPFS network.

        This operation queries the DHT to find peers who have announced
        that they are providing the content with the given CID.

        Args:
            identifier: The CID to find providers for
            num_providers: Maximum number of providers to find
            timeout: Timeout in seconds for the operation
            options: Additional options for the find providers operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()

        try:
            # Call the DHT find providers method
            result = self.ipfs.ipfs_dht_find_providers(
                identifier,
                num_providers=num_providers,
                timeout=timeout
            )

            # Update performance stats
            duration = time.time() - start_time
            self._update_perf_stats("dht_find_provider", duration)

            success = result.get("success", False)
            providers = result.get("providers", []) if success else []

            return {
                "success": success,
                "providers": providers,
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result if not success else {"count": len(providers)},
            }
        except Exception as e:
            return IPFSErrorHandler.handle_exception(e, "dht_find_providers")

    def dht_find_peer(
        self,
        peer_id: str,
        timeout: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Find information about a specific peer using the DHT.

        This operation queries the DHT to find the multiaddresses and
        connection information for a specific peer by its ID.

        Args:
            peer_id: The ID of the peer to find
            timeout: Timeout in seconds for the operation
            options: Additional options for the find peer operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()

        try:
            # Call the DHT find peer method
            result = self.ipfs.ipfs_dht_find_peer(peer_id, timeout=timeout)

            # Update performance stats
            duration = time.time() - start_time
            self._update_perf_stats("dht_find_peer", duration)

            success = result.get("success", False)

            return {
                "success": success,
                "peer_info": result.get("peer_info", {}) if success else {},
                "addresses": result.get("addresses", []) if success else [],
                "backend": self.get_name(),
                "peer_id": peer_id,
                "details": result,
            }
        except Exception as e:
            return IPFSErrorHandler.handle_exception(e, "dht_find_peer")

    def dht_query(
        self,
        key: str,
        timeout: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Query the DHT for a specific key.

        This operation performs a direct query to the DHT for a key,
        which can be used for custom DHT-based applications.

        Args:
            key: The key to query in the DHT
            timeout: Timeout in seconds for the operation
            options: Additional options for the DHT query operation

        Returns:
            Dictionary with operation results
        """
        options = options or {}
        start_time = time.time()

        try:
            # Call the DHT query method
            result = self.ipfs.ipfs_dht_query(key, timeout=timeout)

            # Update performance stats
            duration = time.time() - start_time
            self._update_perf_stats("dht_query", duration)

            success = result.get("success", False)

            return {
                "success": success,
                "responses": result.get("responses", []) if success else [],
                "backend": self.get_name(),
                "key": key,
                "details": result,
            }
        except Exception as e:
            return IPFSErrorHandler.handle_exception(e, "dht_query")

# Singleton instance
_instance = None

def get_instance(config=None):
    """Get or create a singleton instance of the backend."""
    global _instance
    if _instance is None:
        _instance = IPFSStorageBackend(config)
    return _instance
