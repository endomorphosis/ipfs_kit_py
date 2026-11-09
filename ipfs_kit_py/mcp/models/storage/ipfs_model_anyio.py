"""
IPFS Storage Model with AnyIO support for MCP server.

This module provides the asynchronous IPFS implementation of the BaseStorageModel
interface for the MCP server.
"""

import time
import logging
import json
import anyio
from typing import Dict, Any, Optional, Union, BinaryIO

from .ipfs_model import IPFSModel

# Configure logger
logger = logging.getLogger(__name__)


class IPFSModelAnyIO(IPFSModel):
    """
    Asynchronous IPFS storage model for MCP server.
    
    This class extends IPFSModel to provide fully asynchronous methods
    for interacting with IPFS storage using AnyIO.
    """

    def __init__(
        self,
        ipfs_backend=None,
        cache_manager=None,
        credential_manager=None,
    ):
        """
        Initialize asynchronous IPFS storage model.

        Args:
            ipfs_backend: IPFSBackend instance or similar adapter
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
        """
        # Initialize the base class
        super().__init__(
            ipfs_backend=ipfs_backend,
            cache_manager=cache_manager,
            credential_manager=credential_manager,
        )
        
        logger.info("IPFS AnyIO Model initialized")

    async def _read_file_content_async(self, file_path: str) -> bytes:
        """
        Read file content asynchronously.

        Args:
            file_path: Path to file

        Returns:
            bytes: File content
        """
        async with await anyio.open_file(file_path, "rb") as file:
            return await file.read()

    async def _write_file_content_async(self, file_path: str, content: bytes) -> None:
        """
        Write content to file asynchronously.

        Args:
            file_path: Path to file
            content: Content to write
        """
        async with await anyio.open_file(file_path, "wb") as file:
            await file.write(content)

    async def add_content_from_file(
        self, 
        file_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Add content from file to IPFS asynchronously.

        Args:
            file_path: Path to file
            **kwargs: Additional parameters (see add_content)

        Returns:
            Dict: Result of the operation with CID
        """
        result = self._create_result_template("add_content_from_file")
        start_time = time.time()
        
        try:
            # Read file content asynchronously
            content = await self._read_file_content_async(file_path)
            content_size = len(content)
            
            # Use file name as filename parameter if not provided
            if "filename" not in kwargs:
                import os
                kwargs["filename"] = os.path.basename(file_path)
                
            # Add to IPFS
            add_result = await self.add_content(content, **kwargs)
            
            # Copy results
            for key, value in add_result.items():
                if key not in ["operation", "operation_id"]:
                    result[key] = value
                    
            result["success"] = add_result.get("success", False)
            result["file_path"] = file_path
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "add_content_from_file")
        
        return await self._handle_operation_result_async(
            result, "upload", start_time, content_size
        )

    async def get_content_to_file(
        self, 
        content_id: str,
        file_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Retrieve content from IPFS to file asynchronously.

        Args:
            content_id: CID of content
            file_path: Path where content should be saved
            **kwargs: Additional parameters (see get_content)

        Returns:
            Dict: Result of the operation
        """
        result = self._create_result_template("get_content_to_file")
        start_time = time.time()
        
        try:
            # Get content from IPFS
            get_result = await self.get_content(content_id, **kwargs)
            
            if get_result.get("success", False):
                content = get_result.get("content")
                
                # Write content to file asynchronously
                if content:
                    await self._write_file_content_async(file_path, content)
                    
                    # Copy results
                    for key, value in get_result.items():
                        if key not in ["operation", "operation_id", "content"]:
                            result[key] = value
                            
                    result["success"] = True
                    result["file_path"] = file_path
                    result["size"] = len(content) if isinstance(content, bytes) else 0
                else:
                    result["success"] = False
                    result["error"] = "Retrieved content is empty"
                    result["error_type"] = "ContentError"
            else:
                # Copy error information
                result["success"] = False
                result["error"] = get_result.get("error", "Unknown error retrieving content")
                result["error_type"] = get_result.get("error_type", "IPFSError")
                result["backend_details"] = get_result.get("backend_details", {})
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "get_content_to_file")
        
        return await self._handle_operation_result_async(
            result, "download", start_time, result.get("size", 0)
        )

    async def verify_content(
        self, 
        content_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Verify that content exists and is retrievable in IPFS.

        Args:
            content_id: CID of content to verify
            **kwargs: Additional parameters:
                - check_retrievable (bool): Whether to attempt retrieval (default: True)
                - timeout (int): Timeout in seconds for retrieval check

        Returns:
            Dict: Result of the verification
        """
        result = self._create_result_template("verify_content")
        start_time = time.time()
        
        try:
            # Check if pinned
            exists = self.ipfs_backend.exists(content_id)
            result["exists"] = exists
            
            # Try to retrieve if requested
            check_retrievable = kwargs.get("check_retrievable", True)
            if check_retrievable:
                timeout = kwargs.get("timeout", 10)
                
                # Try retrieval with timeout
                options = {"timeout": timeout}
                backend_result = self.ipfs_backend.retrieve(
                    identifier=content_id,
                    options=options
                )
                
                retrievable = backend_result.get("success", False)
                result["retrievable"] = retrievable
                
                if retrievable:
                    # Get content size
                    content_data = backend_result.get("data")
                    content_size = len(content_data) if isinstance(content_data, bytes) else 0
                    result["size"] = content_size
                else:
                    result["retrieval_error"] = backend_result.get("error")
            
            # Get metadata if content exists
            if exists:
                metadata_result = self.ipfs_backend.get_metadata(content_id)
                if metadata_result.get("success", False):
                    result["metadata"] = metadata_result.get("metadata", {})
            
            # Set overall success based on existence and retrievability
            result["success"] = exists
            if check_retrievable:
                result["success"] = exists and result["retrievable"]
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "verify_content")
        
        return await self._handle_operation_result_async(result, "verify", start_time)

    async def get_network_stats(self, **kwargs) -> Dict[str, Any]:
        """
        Get IPFS network statistics.

        Args:
            **kwargs: Additional parameters:
                - timeout (int): Timeout in seconds

        Returns:
            Dict: Network statistics
        """
        result = self._create_result_template("get_network_stats")
        start_time = time.time()
        
        try:
            # This is a mock implementation since we don't have direct access
            # to IPFS network stats through the backend
            # In a real implementation, this would call ipfs stats commands
            
            result["success"] = True
            result["stats"] = {
                "bandwidth": {
                    "total_in": 0,
                    "total_out": 0,
                    "rate_in": 0,
                    "rate_out": 0,
                },
                "peers": {
                    "count": 0,
                },
                "repo": {
                    "size": 0,
                    "objects": 0,
                },
            }
            
            # Get actual stats if the backend supports it
            if hasattr(self.ipfs_backend, 'get_stats'):
                backend_stats = self.ipfs_backend.get_stats()
                if backend_stats:
                    result["stats"] = backend_stats
            
        except Exception as e:
            return await self._handle_exception_async(e, result, "get_network_stats")
        
        return await self._handle_operation_result_async(result, "stats", start_time)

    # Create synchronous versions of async methods using the helper decorator
    add_content_from_file_sync = IPFSModel._create_sync_method(add_content_from_file)
    get_content_to_file_sync = IPFSModel._create_sync_method(get_content_to_file)
    verify_content_sync = IPFSModel._create_sync_method(verify_content)
    get_network_stats_sync = IPFSModel._create_sync_method(get_network_stats)