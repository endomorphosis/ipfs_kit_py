"""
IPFS backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for IPFS.
"""

import logging
import time
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

        # Import dependencies
        from ipfs_kit_py.ipfs import ipfs_py

        # Initialize IPFS client
        self.ipfs = ipfs_py(resources, metadata)

    def store(
        self
        data: Union[bytes, BinaryIO, str]
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
                "success": True
                "identifier": cid
                "backend": self.get_name(),
                "details": result
            }

        return {
            "success": False
            "error": result.get("error", "Failed to store data in IPFS"),
            "backend": self.get_name(),
            "details": result
        }

    def retrieve(
        self
        identifier: str
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Retrieve data from IPFS."""
        options = options or {}

        # Get data from IPFS
        result = self.ipfs.ipfs_cat(identifier)

        if result.get("success", False):
            return {
                "success": True
                "data": result.get("data"),
                "backend": self.get_name(),
                "identifier": identifier
                "details": result
            }

        return {
            "success": False
            "error": result.get("error", "Failed to retrieve data from IPFS"),
            "backend": self.get_name(),
            "identifier": identifier
            "details": result
        }

    def delete(
        self
        identifier: str
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
            "identifier": identifier
            "details": result
        }

    def list(
        self
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
                "success": True
                "items": items
                "backend": self.get_name(),
                "details": result
            }

        return {
            "success": False
            "error": result.get("error", "Failed to list pins in IPFS"),
            "backend": self.get_name(),
            "details": result
        }

    def exists(
        self
        identifier: str
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if content exists (is pinned) in IPFS."""
        options = options or {}

        # Check if pinned
        result = self.ipfs.ipfs_pin_ls(identifier)

        return result.get("success", False)

    def get_metadata(
        self
        identifier: str
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get metadata for IPFS content."""
        options = options or {}

        # Get object stats
        result = self.ipfs.ipfs_object_stat(identifier)

        if result.get("success", False):
            return {
                "success": True
                "metadata": {
                    "size": result.get("CumulativeSize", 0),
                    "links": result.get("NumLinks", 0),
                    "blocks": 1,  # Simplified
                    "backend": self.get_name(),
                },
                "backend": self.get_name(),
                "identifier": identifier
                "details": result
            }

        return {
            "success": False
            "error": result.get("error", "Failed to get metadata from IPFS"),
            "backend": self.get_name(),
            "identifier": identifier
            "details": result
        }

    def update_metadata(
        self
        identifier: str
        metadata: Dict[str, Any]
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update metadata for IPFS content.

        Note: IPFS doesn't natively support metadata updates for immutable content,
        so this uses a custom metadata storage approach.
        """
        options = options or {}

        # Use custom metadata storage
        result = self.ipfs.ipfs_add_metadata(identifier, metadata)

        return {
            "success": result.get("success", False),
            "backend": self.get_name(),
            "identifier": identifier
            "details": result
        }
