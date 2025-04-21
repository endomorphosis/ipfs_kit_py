"""
S3 Model for MCP Server (AnyIO Version).

This module provides the business logic for S3 operations in the MCP server
using AnyIO for backend-agnostic async capabilities.
"""

import logging
import os
import tempfile
import time
import anyio
import sniffio
import uuid
from typing import Dict, Optional, Any
from ipfs_kit_py.mcp.models.storage import BaseStorageModel

# Configure logger
logger = logging.getLogger(__name__)


class S3ModelAnyIO(BaseStorageModel):
    """Model for S3 operations with AnyIO support."""
    def __init__(
        self
s3_kit_instance = None
ipfs_model = None
cache_manager = None
credential_manager = None
        """Initialize S3 model with dependencies.

        Args:
            s3_kit_instance: s3_kit instance for S3 operations
            ipfs_model: IPFS model for IPFS operations
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
        """
        super().__init__(s3_kit_instance, cache_manager, credential_manager)

        # Store the s3_kit instance
        self.s3_kit = s3_kit_instance

        # Store the IPFS model for cross-backend operations
        self.ipfs_model = ipfs_model

        logger.info("S3 Model (AnyIO) initialized")

    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None

    async def upload_file_async(
    self,
    file_path: str
        bucket: str
        key: str
        metadata: Optional[Dict[str, Any]] = None,
        """Upload a file to S3 asynchronously.

        Args:
            file_path: Path to the file to upload
            bucket: S3 bucket name
            key: S3 object key
            metadata: Optional metadata to attach to the object

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("upload_file")

        try:
            # Validate inputs
            file_exists = await anyio.to_thread.run_sync(lambda: os.path.exists(file_path))
            if not file_exists:
                result["error"] = f"File not found: {file_path}"
                result["error_type"] = "FileNotFoundError"
                return result

            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            if not key:
                result["error"] = "Key is required"
                result["error_type"] = "ValidationError"
                return result

            # Get file size for statistics
            file_size = await anyio.to_thread.run_sync(lambda: os.path.getsize(file_path))

            # Use s3_kit to upload the file
            if self.s3_kit:
                # Run the upload operation in a thread
                s3_result = await anyio.to_thread.run_sync(
                    lambda: self.s3_kit.s3_ul_file(file_path, bucket, key, metadata)

                if s3_result.get("success", False):
                    result["success"] = True
                    result["bucket"] = bucket
                    result["key"] = key
                    result["etag"] = s3_result.get("ETag")
                    result["size_bytes"] = file_size
                else:
                    result["error"] = s3_result.get("error", "Unknown error during S3 upload")
                    result["error_type"] = s3_result.get("error_type", "S3UploadError")
            else:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            self._update_stats(result, file_size if result["success"] else None)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def upload_file(
    self,
    file_path: str
        bucket: str
        key: str
        metadata: Optional[Dict[str, Any]] = None,
        """Upload a file to S3 (sync version).

        This method supports both sync and async contexts.
        In async contexts, it logs a warning and attempts to delegate to the async version.

        Args:
            file_path: Path to the file to upload
            bucket: S3 bucket name
            key: S3 object key
            metadata: Optional metadata to attach to the object

        Returns:
            Result dictionary with operation status and details
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync upload_file() in async context ({backend}). Consider using upload_file_async() instead"

            # Create a result with warning
            result = self._create_result_dict("upload_file")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use upload_file_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
        start_time = time.time()
        result = self._create_result_dict("upload_file")

        try:
            # Validate inputs
            if not os.path.exists(file_path):
                result["error"] = f"File not found: {file_path}"
                result["error_type"] = "FileNotFoundError"
                return result

            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            if not key:
                result["error"] = "Key is required"
                result["error_type"] = "ValidationError"
                return result

            # Get file size for statistics
            file_size = os.path.getsize(file_path)

            # Use s3_kit to upload the file
            if self.s3_kit:
                s3_result = self.s3_kit.s3_ul_file(file_path, bucket, key, metadata)

                if s3_result.get("success", False):
                    result["success"] = True
                    result["bucket"] = bucket
                    result["key"] = key
                    result["etag"] = s3_result.get("ETag")
                    result["size_bytes"] = file_size
                else:
                    result["error"] = s3_result.get("error", "Unknown error during S3 upload")
                    result["error_type"] = s3_result.get("error_type", "S3UploadError")
            else:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            self._update_stats(result, file_size if result["success"] else None)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    async def download_file_async(self, bucket: str, key: str, destination: str) -> Dict[str, Any]:
        """Download a file from S3 asynchronously.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            destination: Local path to save the file

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("download_file")

        try:
            # Validate inputs
            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            if not key:
                result["error"] = "Key is required"
                result["error_type"] = "ValidationError"
                return result

            # Create the destination directory if it doesn't exist
            dest_dir = os.path.dirname(os.path.abspath(destination))
            await anyio.to_thread.run_sync(lambda: os.makedirs(dest_dir, exist_ok=True))

            # Use s3_kit to download the file
            if self.s3_kit:
                # Run the download operation in a thread
                s3_result = await anyio.to_thread.run_sync(
                    lambda: self.s3_kit.s3_dl_file(bucket, key, destination)

                if s3_result.get("success", False):
                    # Get file size for statistics
                    file_exists = await anyio.to_thread.run_sync(
                        lambda: os.path.exists(destination)
                    file_size = 0
                    if file_exists:
                        file_size = await anyio.to_thread.run_sync(
                            lambda: os.path.getsize(destination)

                    result["success"] = True
                    result["bucket"] = bucket
                    result["key"] = key
                    result["destination"] = destination
                    result["size_bytes"] = file_size
                else:
                    result["error"] = s3_result.get("error", "Unknown error during S3 download")
                    result["error_type"] = s3_result.get("error_type", "S3DownloadError")
            else:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            if result["success"] and "size_bytes" in result:
                self._update_stats(result, result["size_bytes"])
            else:
                self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def download_file(self, bucket: str, key: str, destination: str) -> Dict[str, Any]:
        """Download a file from S3 (sync version).

        This method supports both sync and async contexts.
        In async contexts, it logs a warning and returns an error.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            destination: Local path to save the file

        Returns:
            Result dictionary with operation status and details
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync download_file() in async context ({backend}). Consider using download_file_async() instead"

            # Create a result with warning
            result = self._create_result_dict("download_file")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use download_file_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
        start_time = time.time()
        result = self._create_result_dict("download_file")

        try:
            # Validate inputs
            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            if not key:
                result["error"] = "Key is required"
                result["error_type"] = "ValidationError"
                return result

            # Create the destination directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)

            # Use s3_kit to download the file
            if self.s3_kit:
                s3_result = self.s3_kit.s3_dl_file(bucket, key, destination)

                if s3_result.get("success", False):
                    # Get file size for statistics
                    file_size = os.path.getsize(destination) if os.path.exists(destination) else 0

                    result["success"] = True
                    result["bucket"] = bucket
                    result["key"] = key
                    result["destination"] = destination
                    result["size_bytes"] = file_size
                else:
                    result["error"] = s3_result.get("error", "Unknown error during S3 download")
                    result["error_type"] = s3_result.get("error_type", "S3DownloadError")
            else:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            if result["success"] and "size_bytes" in result:
                self._update_stats(result, result["size_bytes"])
            else:
                self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    async def list_objects_async(self, bucket: str, prefix: Optional[str] = None) -> Dict[str, Any]:
        """List objects in an S3 bucket asynchronously.

        Args:
            bucket: S3 bucket name
            prefix: Optional prefix to filter objects

        Returns:
            Result dictionary with operation status and object list
        """
        start_time = time.time()
        result = self._create_result_dict("list_objects")

        try:
            # Validate inputs
            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            # Use s3_kit to list objects
            if self.s3_kit:
                # Run the list operation in a thread
                if prefix:
                    s3_result = await anyio.to_thread.run_sync(
                        lambda: self.s3_kit.s3_ls_dir(prefix, bucket)
                else:
                    s3_result = await anyio.to_thread.run_sync(
                        lambda: self.s3_kit.s3_ls_dir("", bucket)

                if s3_result.get("success", False):
                    result["success"] = True
                    result["bucket"] = bucket
                    result["prefix"] = prefix
                    result["objects"] = s3_result.get("files", [])
                    result["count"] = len(result["objects"])
                else:
                    result["error"] = s3_result.get(
                        "error", "Unknown error during S3 list operation"
                    result["error_type"] = s3_result.get("error_type", "S3ListError")
            else:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def list_objects(self, bucket: str, prefix: Optional[str] = None) -> Dict[str, Any]:
        """List objects in an S3 bucket (sync version).

        Args:
            bucket: S3 bucket name
            prefix: Optional prefix to filter objects

        Returns:
            Result dictionary with operation status and object list
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync list_objects() in async context ({backend}). Consider using list_objects_async() instead"

            # Create a result with warning
            result = self._create_result_dict("list_objects")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use list_objects_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
        start_time = time.time()
        result = self._create_result_dict("list_objects")

        try:
            # Validate inputs
            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            # Use s3_kit to list objects
            if self.s3_kit:
                if prefix:
                    s3_result = self.s3_kit.s3_ls_dir(prefix, bucket)
                else:
                    s3_result = self.s3_kit.s3_ls_dir("", bucket)

                if s3_result.get("success", False):
                    result["success"] = True
                    result["bucket"] = bucket
                    result["prefix"] = prefix
                    result["objects"] = s3_result.get("files", [])
                    result["count"] = len(result["objects"])
                else:
                    result["error"] = s3_result.get(
                        "error", "Unknown error during S3 list operation"
                    result["error_type"] = s3_result.get("error_type", "S3ListError")
            else:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    async def delete_object_async(self, bucket: str, key: str) -> Dict[str, Any]:
        """Delete an object from S3 asynchronously.

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            Result dictionary with operation status
        """
        start_time = time.time()
        result = self._create_result_dict("delete_object")

        try:
            # Validate inputs
            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            if not key:
                result["error"] = "Key is required"
                result["error_type"] = "ValidationError"
                return result

            # Use s3_kit to delete the object
            if self.s3_kit:
                # Run the delete operation in a thread
                s3_result = await anyio.to_thread.run_sync(
                    lambda: self.s3_kit.s3_rm_file(key, bucket)

                if s3_result.get("success", False):
                    result["success"] = True
                    result["bucket"] = bucket
                    result["key"] = key
                else:
                    result["error"] = s3_result.get(
                        "error", "Unknown error during S3 delete operation"
                    result["error_type"] = s3_result.get("error_type", "S3DeleteError")
            else:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def delete_object(self, bucket: str, key: str) -> Dict[str, Any]:
        """Delete an object from S3 (sync version).

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            Result dictionary with operation status
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync delete_object() in async context ({backend}). Consider using delete_object_async() instead"

            # Create a result with warning
            result = self._create_result_dict("delete_object")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use delete_object_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
        start_time = time.time()
        result = self._create_result_dict("delete_object")

        try:
            # Validate inputs
            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            if not key:
                result["error"] = "Key is required"
                result["error_type"] = "ValidationError"
                return result

            # Use s3_kit to delete the object
            if self.s3_kit:
                s3_result = self.s3_kit.s3_rm_file(key, bucket)

                if s3_result.get("success", False):
                    result["success"] = True
                    result["bucket"] = bucket
                    result["key"] = key
                else:
                    result["error"] = s3_result.get(
                        "error", "Unknown error during S3 delete operation"
                    result["error_type"] = s3_result.get("error_type", "S3DeleteError")
            else:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"

            # Update statistics
            self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    async def ipfs_to_s3_async(
        self, cid: str, bucket: str, key: Optional[str] = None, pin: bool = True
        """Get content from IPFS and upload to S3 asynchronously.

        Args:
            cid: Content identifier in IPFS
            bucket: S3 bucket name
            key: S3 object key (defaults to CID if not provided)
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("ipfs_to_s3")

        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result

            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            # Use the CID as the key if not provided
            if not key:
                key = cid

            # Only continue if all dependencies are available
            if not self.s3_kit:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"
                return result

            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result

            # Create a temporary file to store the content
            temp_fd, temp_path = await anyio.to_thread.run_sync(tempfile.mkstemp)
            try:
                # Close the file descriptor
                await anyio.to_thread.run_sync(lambda: os.close(temp_fd))

                # Retrieve content from IPFS
                if hasattr(self.ipfs_model, "get_content_async") and callable(
                    getattr(self.ipfs_model, "get_content_async")
                    # Use async version if available
                    ipfs_result = await self.ipfs_model.get_content_async(cid)
                else:
                    # Fall back to sync version
                    ipfs_result = await anyio.to_thread.run_sync(
                        lambda: self.ipfs_model.get_content(cid)

                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get(
                        "error", "Failed to retrieve content from IPFS"
                    result["error_type"] = ipfs_result.get("error_type", "IPFSGetError")
                    result["ipfs_result"] = ipfs_result
                    return result

                # Write content to temporary file
                content = ipfs_result.get("data")
                if not content:
                    result["error"] = "No content retrieved from IPFS"
                    result["error_type"] = "ContentMissingError"
                    result["ipfs_result"] = ipfs_result
                    return result

                # Write the content to the temporary file
                async with await anyio.open_file(temp_path, "wb") as f:
                    await f.write(content)

                # Pin the content if requested
                if pin:
                    if hasattr(self.ipfs_model, "pin_content_async") and callable(
                        getattr(self.ipfs_model, "pin_content_async")
                        # Use async version if available
                        pin_result = await self.ipfs_model.pin_content_async(cid)
                    else:
                        # Fall back to sync version
                        pin_result = await anyio.to_thread.run_sync(
                            lambda: self.ipfs_model.pin_content(cid)

                    if not pin_result.get("success", False):
                        logger.warning(f"Failed to pin content {cid}: {pin_result.get('error')}")

                # Upload to S3
                upload_result = await self.upload_file_async(
                    temp_path, bucket, key, metadata={"ipfs_cid": cid}

                if not upload_result.get("success", False):
                    result["error"] = upload_result.get("error", "Failed to upload content to S3")
                    result["error_type"] = upload_result.get("error_type", "S3UploadError")
                    result["upload_result"] = upload_result
                    return result

                # Set success and copy relevant fields
                result["success"] = True
                result["ipfs_cid"] = cid
                result["bucket"] = bucket
                result["key"] = key
                result["size_bytes"] = upload_result.get("size_bytes")
                result["etag"] = upload_result.get("etag")

            finally:
                # Clean up the temporary file
                try:
                    await anyio.to_thread.run_sync(lambda: os.unlink(temp_path))
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {temp_path}: {e}")

            # Update statistics
            if result["success"] and "size_bytes" in result:
                self._update_stats(result, result["size_bytes"])
            else:
                self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def ipfs_to_s3(
        self, cid: str, bucket: str, key: Optional[str] = None, pin: bool = True
        """Get content from IPFS and upload to S3 (sync version).

        Args:
            cid: Content identifier in IPFS
            bucket: S3 bucket name
            key: S3 object key (defaults to CID if not provided)
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync ipfs_to_s3() in async context ({backend}). Consider using ipfs_to_s3_async() instead"

            # Create a result with warning
            result = self._create_result_dict("ipfs_to_s3")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use ipfs_to_s3_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
        start_time = time.time()
        result = self._create_result_dict("ipfs_to_s3")

        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result

            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            # Use the CID as the key if not provided
            if not key:
                key = cid

            # Only continue if all dependencies are available
            if not self.s3_kit:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"
                return result

            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result

            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

                # Retrieve content from IPFS
                ipfs_result = self.ipfs_model.get_content(cid)

                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get(
                        "error", "Failed to retrieve content from IPFS"
                    result["error_type"] = ipfs_result.get("error_type", "IPFSGetError")
                    result["ipfs_result"] = ipfs_result
                    os.unlink(temp_path)
                    return result

                # Write content to temporary file
                content = ipfs_result.get("data")
                if not content:
                    result["error"] = "No content retrieved from IPFS"
                    result["error_type"] = "ContentMissingError"
                    result["ipfs_result"] = ipfs_result
                    os.unlink(temp_path)
                    return result

                temp_file.write(content)
                temp_file.flush()

                # Pin the content if requested
                if pin:
                    pin_result = self.ipfs_model.pin_content(cid)
                    if not pin_result.get("success", False):
                        logger.warning(f"Failed to pin content {cid}: {pin_result.get('error')}")

                # Upload to S3
                upload_result = self.upload_file(temp_path, bucket, key, metadata={"ipfs_cid": cid})

                # Clean up the temporary file
                os.unlink(temp_path)

                if not upload_result.get("success", False):
                    result["error"] = upload_result.get("error", "Failed to upload content to S3")
                    result["error_type"] = upload_result.get("error_type", "S3UploadError")
                    result["upload_result"] = upload_result
                    return result

                # Set success and copy relevant fields
                result["success"] = True
                result["ipfs_cid"] = cid
                result["bucket"] = bucket
                result["key"] = key
                result["size_bytes"] = upload_result.get("size_bytes")
                result["etag"] = upload_result.get("etag")

            # Update statistics
            if result["success"] and "size_bytes" in result:
                self._update_stats(result, result["size_bytes"])
            else:
                self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    async def s3_to_ipfs_async(self, bucket: str, key: str, pin: bool = True) -> Dict[str, Any]:
        """Get content from S3 and add to IPFS asynchronously.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("s3_to_ipfs")

        try:
            # Validate inputs
            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            if not key:
                result["error"] = "Key is required"
                result["error_type"] = "ValidationError"
                return result

            # Only continue if all dependencies are available
            if not self.s3_kit:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"
                return result

            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result

            # Create a temporary file to store the content
            temp_fd, temp_path = await anyio.to_thread.run_sync(tempfile.mkstemp)
            try:
                # Close the file descriptor
                await anyio.to_thread.run_sync(lambda: os.close(temp_fd))

                # Download content from S3
                download_result = await self.download_file_async(bucket, key, temp_path)

                if not download_result.get("success", False):
                    result["error"] = download_result.get(
                        "error", "Failed to download content from S3"
                    result["error_type"] = download_result.get("error_type", "S3DownloadError")
                    result["download_result"] = download_result
                    return result

                # Get file size for statistics
                file_size = await anyio.to_thread.run_sync(lambda: os.path.getsize(temp_path))

                # Read the file content
                async with await anyio.open_file(temp_path, "rb") as f:
                    content = await f.read()

                # Add to IPFS
                if hasattr(self.ipfs_model, "add_content_async") and callable(
                    getattr(self.ipfs_model, "add_content_async")
                    # Use async version if available
                    ipfs_result = await self.ipfs_model.add_content_async(
                        content, filename=os.path.basename(key)
                else:
                    # Fall back to sync version
                    ipfs_result = await anyio.to_thread.run_sync(
                        lambda: self.ipfs_model.add_content(content, filename=os.path.basename(key))

                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get("error", "Failed to add content to IPFS")
                    result["error_type"] = ipfs_result.get("error_type", "IPFSAddError")
                    result["ipfs_result"] = ipfs_result
                    return result

                cid = ipfs_result.get("cid")

                # Pin the content if requested
                if pin and cid:
                    if hasattr(self.ipfs_model, "pin_content_async") and callable(
                        getattr(self.ipfs_model, "pin_content_async")
                        # Use async version if available
                        pin_result = await self.ipfs_model.pin_content_async(cid)
                    else:
                        # Fall back to sync version
                        pin_result = await anyio.to_thread.run_sync(
                            lambda: self.ipfs_model.pin_content(cid)

                    if not pin_result.get("success", False):
                        logger.warning(f"Failed to pin content {cid}: {pin_result.get('error')}")

                # Set success and copy relevant fields
                result["success"] = True
                result["bucket"] = bucket
                result["key"] = key
                result["ipfs_cid"] = cid
                result["size_bytes"] = file_size

            finally:
                # Clean up the temporary file
                try:
                    await anyio.to_thread.run_sync(lambda: os.unlink(temp_path))
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {temp_path}: {e}")

            # Update statistics
            if result["success"] and "size_bytes" in result:
                self._update_stats(result, result["size_bytes"])
            else:
                self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    def s3_to_ipfs(self, bucket: str, key: str, pin: bool = True) -> Dict[str, Any]:
        """Get content from S3 and add to IPFS (sync version).

        Args:
            bucket: S3 bucket name
            key: S3 object key
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync s3_to_ipfs() in async context ({backend}). Consider using s3_to_ipfs_async() instead"

            # Create a result with warning
            result = self._create_result_dict("s3_to_ipfs")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use s3_to_ipfs_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
        start_time = time.time()
        result = self._create_result_dict("s3_to_ipfs")

        try:
            # Validate inputs
            if not bucket:
                result["error"] = "Bucket name is required"
                result["error_type"] = "ValidationError"
                return result

            if not key:
                result["error"] = "Key is required"
                result["error_type"] = "ValidationError"
                return result

            # Only continue if all dependencies are available
            if not self.s3_kit:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"
                return result

            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result

            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

                # Download content from S3
                download_result = self.download_file(bucket, key, temp_path)

                if not download_result.get("success", False):
                    result["error"] = download_result.get(
                        "error", "Failed to download content from S3"
                    result["error_type"] = download_result.get("error_type", "S3DownloadError")
                    result["download_result"] = download_result
                    os.unlink(temp_path)
                    return result

                # Get file size for statistics
                file_size = os.path.getsize(temp_path)

                # Read the file content
                with open(temp_path, "rb") as f:
                    content = f.read()

                # Add to IPFS
                ipfs_result = self.ipfs_model.add_content(content, filename=os.path.basename(key))

                # Clean up the temporary file
                os.unlink(temp_path)

                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get("error", "Failed to add content to IPFS")
                    result["error_type"] = ipfs_result.get("error_type", "IPFSAddError")
                    result["ipfs_result"] = ipfs_result
                    return result

                cid = ipfs_result.get("cid")

                # Pin the content if requested
                if pin and cid:
                    pin_result = self.ipfs_model.pin_content(cid)
                    if not pin_result.get("success", False):
                        logger.warning(f"Failed to pin content {cid}: {pin_result.get('error')}")

                # Set success and copy relevant fields
                result["success"] = True
                result["bucket"] = bucket
                result["key"] = key
                result["ipfs_cid"] = cid
                result["size_bytes"] = file_size

            # Update statistics
            if result["success"] and "size_bytes" in result:
                self._update_stats(result, result["size_bytes"])
            else:
                self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result

    async def get_stats_async(self) -> Dict[str, Any]:
        """Get current operation statistics asynchronously."""
        return {"operation_stats": self.operation_stats, "timestamp": time.time()}

    async def reset_async(self) -> None:
        """Reset model state for testing asynchronously."""
        self.operation_stats = self._initialize_stats()
        self.correlation_id = str(uuid.uuid4())
        logger.info(f"Reset S3Model (AnyIO) state, new ID: {self.correlation_id}")
