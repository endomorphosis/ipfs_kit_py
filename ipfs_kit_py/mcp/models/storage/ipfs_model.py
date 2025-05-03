"""
IPFS Storage Model for MCP server.

This module provides the IPFS implementation of the BaseStorageModel
interface for the MCP server.
"""

import time
import logging
import json
from typing import Dict, Any, Optional, Union, BinaryIO

from .base_storage_model import BaseStorageModel

# Configure logger
logger = logging.getLogger(__name__)


class IPFSModel(BaseStorageModel):
    """
    IPFS storage model for MCP server.
    
    This class implements the storage model interface for IPFS,
    providing a standardized way to interact with IPFS storage.
    """

    def __init__(
        self,
        ipfs_backend=None,
        cache_manager=None,
        credential_manager=None,
        debug_mode=False,
        log_level="INFO",
        config=None,
    ):
        """
        Initialize IPFS storage model.

        Args:
            ipfs_backend: IPFSBackend instance or similar adapter
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
            debug_mode: Enable debug mode
            log_level: Logging level
            config: Configuration dictionary
        """
        # Initialize the base class
        super().__init__(
            kit_instance=None,  # We're using ipfs_backend instead of a kit
            cache_manager=cache_manager,
            credential_manager=credential_manager,
        )
        
        # Store IPFS backend
        self.ipfs_backend = ipfs_backend
        self.kit = ipfs_backend  # Alias for compatibility with base class
        
        # Set the backend name specifically for IPFS
        self.backend_name = "IPFS"
        
        # Store debug and configuration settings
        self.debug_mode = debug_mode
        self.log_level = log_level
        
        # Extract configuration if provided
        if config is not None:
            self.debug_mode = config.get("debug", self.debug_mode)
            self.log_level = config.get("log_level", self.log_level)
            self.isolation_mode = config.get("isolation", True)
        else:
            self.isolation_mode = True
        
        logger.info("IPFS Model initialized")

    def _get_backend_name(self) -> str:
        """
        Get the name of the storage backend.

        Returns:
            str: Name of the storage backend
        """
        return "IPFS"

    async def add_content(
        self, 
        content: Union[bytes, str, BinaryIO],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Add content to IPFS.

        Args:
            content: Content to add (bytes, string, or file-like object)
            **kwargs: Additional parameters:
                - pin (bool): Whether to pin the content (default: True)
                - filename (str): Optional filename for the content
                - metadata (Dict): Optional metadata to associate with the content

        Returns:
            Dict: Result of the operation with CID
        """
        result = self._create_result_template("add_content")
        start_time = time.time()
        
        try:
            # Process optional parameters
            pin = kwargs.get("pin", True)
            filename = kwargs.get("filename")
            metadata = kwargs.get("metadata", {})
            
            # Calculate content size for stats
            content_size = None
            if isinstance(content, bytes):
                content_size = len(content)
            elif isinstance(content, str):
                content_size = len(content.encode('utf-8'))
            elif hasattr(content, 'seek') and hasattr(content, 'tell'):
                # For file-like objects, get size if possible
                try:
                    current_pos = content.tell()
                    content.seek(0, 2)  # Seek to end
                    content_size = content.tell()
                    content.seek(current_pos)  # Restore position
                except (AttributeError, IOError):
                    content_size = None
            
            # Add content to IPFS through the backend
            options = {
                "pin": pin,
                "filename": filename,
                "metadata": metadata,
            }
            
            container = kwargs.get("container")
            path = kwargs.get("path")
            
            # Store the content
            backend_result = self.ipfs_backend.store(
                data=content,
                container=container,
                path=path,
                options=options
            )
            
            # Process result
            if backend_result.get("success", False):
                result["success"] = True
                result["cid"] = backend_result.get("identifier")
                result["size"] = content_size
                result["pinned"] = pin
                result["backend_details"] = backend_result.get("details", {})
                
                # Add metadata if provided
                if metadata:
                    # Update the metadata on IPFS
                    metadata_result = self.ipfs_backend.update_metadata(
                        identifier=result["cid"],
                        metadata=metadata,
                        container=container,
                        options=options
                    )
                    result["metadata_updated"] = metadata_result.get("success", False)
                    result["metadata"] = metadata
            else:
                # Copy error information from backend result
                result["success"] = False
                result["error"] = backend_result.get("error", "Unknown error adding content to IPFS")
                result["error_type"] = backend_result.get("error_type", "IPFSError")
                result["backend_details"] = backend_result.get("details", {})
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "add_content")
        
        return await self._handle_operation_result_async(
            result, "upload", start_time, content_size
        )

    async def get_content(
        self, 
        content_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Retrieve content from IPFS.

        Args:
            content_id: CID of the content to retrieve
            **kwargs: Additional parameters:
                - timeout (int): Timeout in seconds
                - encoding (str): Optional encoding for string conversion

        Returns:
            Dict: Result of the operation with content
        """
        result = self._create_result_template("get_content")
        start_time = time.time()
        
        try:
            # Check cache first
            cached_content = await self._cache_get_async(content_id)
            if cached_content is not None:
                result["success"] = True
                result["content"] = cached_content
                result["cid"] = content_id
                result["cached"] = True
                logger.debug(f"Retrieved {content_id} from cache")
                return await self._handle_operation_result_async(
                    result, "download", start_time, len(cached_content) if isinstance(cached_content, bytes) else 0
                )
            
            # Retrieve from IPFS
            container = kwargs.get("container")
            options = {
                "timeout": kwargs.get("timeout", 30),
                "encoding": kwargs.get("encoding"),
            }
            
            # Get the content
            backend_result = self.ipfs_backend.retrieve(
                identifier=content_id,
                container=container,
                options=options
            )
            
            # Process result
            if backend_result.get("success", False):
                content_data = backend_result.get("data")
                content_size = len(content_data) if isinstance(content_data, bytes) else 0
                
                result["success"] = True
                result["content"] = content_data
                result["cid"] = content_id
                result["size"] = content_size
                result["backend_details"] = backend_result.get("details", {})
                
                # Cache the content for future use
                cache_ttl = kwargs.get("cache_ttl", 3600)  # Default 1 hour
                if cache_ttl > 0 and content_size > 0:
                    await self._cache_put_async(content_id, content_data, {
                        "cid": content_id,
                        "timestamp": time.time(),
                        "size": content_size,
                    })
                    result["cached"] = True
                
                return await self._handle_operation_result_async(
                    result, "download", start_time, content_size
                )
            else:
                # Copy error information from backend result
                result["success"] = False
                result["error"] = backend_result.get("error", "Unknown error retrieving content from IPFS")
                result["error_type"] = backend_result.get("error_type", "IPFSError")
                result["backend_details"] = backend_result.get("details", {})
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "get_content")
        
        return await self._handle_operation_result_async(result, "download", start_time)

    async def delete_content(
        self, 
        content_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Delete (unpin) content from IPFS.

        Note: This doesn't actually delete the content from the IPFS network,
        it just removes the local pin.

        Args:
            content_id: CID of the content to unpin
            **kwargs: Additional parameters:
                - recursive (bool): Whether to recursively unpin (default: True)
                - force (bool): Force unpinning even if pinned recursively

        Returns:
            Dict: Result of the operation
        """
        result = self._create_result_template("delete_content")
        start_time = time.time()
        
        try:
            # Process options
            container = kwargs.get("container")
            options = {
                "recursive": kwargs.get("recursive", True),
                "force": kwargs.get("force", False),
            }
            
            # Delete/unpin the content
            backend_result = self.ipfs_backend.delete(
                identifier=content_id,
                container=container,
                options=options
            )
            
            # Process result
            if backend_result.get("success", False):
                result["success"] = True
                result["cid"] = content_id
                result["unpinned"] = True
                result["backend_details"] = backend_result.get("details", {})
                
                # Remove from cache if present
                if self.cache_manager:
                    await self._cache_put_async(content_id, None)
            else:
                # Copy error information from backend result
                result["success"] = False
                result["error"] = backend_result.get("error", "Unknown error unpinning content from IPFS")
                result["error_type"] = backend_result.get("error_type", "IPFSError")
                result["backend_details"] = backend_result.get("details", {})
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "delete_content")
        
        return await self._handle_operation_result_async(result, "delete", start_time)

    async def list_content(self, **kwargs) -> Dict[str, Any]:
        """
        List pinned content in IPFS.

        Args:
            **kwargs: Additional parameters:
                - prefix (str): Filter by prefix
                - pin_type (str): Filter by pin type (recursive, direct, indirect)
                - limit (int): Maximum number of items to return
                - offset (int): Number of items to skip

        Returns:
            Dict: Result of the operation with content list
        """
        result = self._create_result_template("list_content")
        start_time = time.time()
        
        try:
            # Process options
            container = kwargs.get("container")
            prefix = kwargs.get("prefix")
            options = {
                "pin_type": kwargs.get("pin_type"),
                "limit": kwargs.get("limit"),
                "offset": kwargs.get("offset"),
            }
            
            # List the content
            backend_result = self.ipfs_backend.list(
                container=container,
                prefix=prefix,
                options=options
            )
            
            # Process result
            if backend_result.get("success", False):
                items = backend_result.get("items", [])
                
                result["success"] = True
                result["items"] = items
                result["count"] = len(items)
                result["backend_details"] = backend_result.get("details", {})
            else:
                # Copy error information from backend result
                result["success"] = False
                result["error"] = backend_result.get("error", "Unknown error listing content from IPFS")
                result["error_type"] = backend_result.get("error_type", "IPFSError")
                result["backend_details"] = backend_result.get("details", {})
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "list_content")
        
        return await self._handle_operation_result_async(result, "list", start_time)

    async def get_metadata(self, content_id: str, **kwargs) -> Dict[str, Any]:
        """
        Get metadata for content in IPFS.

        Args:
            content_id: CID of the content
            **kwargs: Additional parameters

        Returns:
            Dict: Result of the operation with metadata
        """
        result = self._create_result_template("get_metadata")
        start_time = time.time()
        
        try:
            # Retrieve metadata from backend
            container = kwargs.get("container")
            options = kwargs.get("options", {})
            
            backend_result = self.ipfs_backend.get_metadata(
                identifier=content_id,
                container=container,
                options=options
            )
            
            # Process result
            if backend_result.get("success", False):
                metadata = backend_result.get("metadata", {})
                
                result["success"] = True
                result["cid"] = content_id
                result["metadata"] = metadata
                result["backend_details"] = backend_result.get("details", {})
            else:
                # Copy error information from backend result
                result["success"] = False
                result["error"] = backend_result.get("error", "Unknown error getting metadata from IPFS")
                result["error_type"] = backend_result.get("error_type", "IPFSError")
                result["backend_details"] = backend_result.get("details", {})
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "get_metadata")
        
        return await self._handle_operation_result_async(result, "metadata", start_time)

    async def update_metadata(self, content_id: str, metadata: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Update metadata for content in IPFS.

        Args:
            content_id: CID of the content
            metadata: Metadata to update
            **kwargs: Additional parameters

        Returns:
            Dict: Result of the operation
        """
        result = self._create_result_template("update_metadata")
        start_time = time.time()
        
        try:
            # Update metadata in backend
            container = kwargs.get("container")
            options = kwargs.get("options", {})
            
            backend_result = self.ipfs_backend.update_metadata(
                identifier=content_id,
                metadata=metadata,
                container=container,
                options=options
            )
            
            # Process result
            if backend_result.get("success", False):
                result["success"] = True
                result["cid"] = content_id
                result["metadata"] = metadata
                result["backend_details"] = backend_result.get("details", {})
            else:
                # Copy error information from backend result
                result["success"] = False
                result["error"] = backend_result.get("error", "Unknown error updating metadata in IPFS")
                result["error_type"] = backend_result.get("error_type", "IPFSError")
                result["backend_details"] = backend_result.get("details", {})
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "update_metadata")
        
        return await self._handle_operation_result_async(result, "metadata", start_time)

    async def pin_content(self, content_id: str, **kwargs) -> Dict[str, Any]:
        """
        Pin content in IPFS.

        Args:
            content_id: CID of the content to pin
            **kwargs: Additional parameters:
                - recursive (bool): Whether to recursively pin (default: True)

        Returns:
            Dict: Result of the operation
        """
        result = self._create_result_template("pin_content")
        start_time = time.time()
        
        try:
            # Process options
            container = kwargs.get("container")
            options = {
                "recursive": kwargs.get("recursive", True),
            }
            
            # Call our own add_content with pin=True
            # We use the backend directly since we already have it
            backend_result = self.ipfs_backend.store(
                data=content_id,  # Just pass the CID, backend should handle it as a pin
                container=container,
                options={**options, "pin_only": True}
            )
            
            # Process result
            if backend_result.get("success", False):
                result["success"] = True
                result["cid"] = content_id
                result["pinned"] = True
                result["backend_details"] = backend_result.get("details", {})
            else:
                # Copy error information from backend result
                result["success"] = False
                result["error"] = backend_result.get("error", "Unknown error pinning content in IPFS")
                result["error_type"] = backend_result.get("error_type", "IPFSError")
                result["backend_details"] = backend_result.get("details", {})
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "pin_content")
        
        return await self._handle_operation_result_async(result, "pin", start_time)

    # Create synchronous versions of async methods using the helper decorator
    add_content_sync = BaseStorageModel._create_sync_method(add_content)
    get_content_sync = BaseStorageModel._create_sync_method(get_content)
    delete_content_sync = BaseStorageModel._create_sync_method(delete_content)
    list_content_sync = BaseStorageModel._create_sync_method(list_content)
    get_metadata_sync = BaseStorageModel._create_sync_method(get_metadata)
    update_metadata_sync = BaseStorageModel._create_sync_method(update_metadata)
    pin_content_sync = BaseStorageModel._create_sync_method(pin_content)