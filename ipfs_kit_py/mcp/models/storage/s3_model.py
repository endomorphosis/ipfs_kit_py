"""
S3 Model for MCP Server.

This module provides the business logic for S3 operations in the MCP server.
It relies on the s3_kit module for underlying functionality.
"""

import logging
import os
import tempfile
import time
from typing import Dict, List, Optional, Any, Union

from ipfs_kit_py.s3_kit import s3_kit
from ipfs_kit_py.mcp.models.storage import BaseStorageModel

# Configure logger
logger = logging.getLogger(__name__)


class S3Model(BaseStorageModel):
    """Model for S3 operations."""
    
    def __init__(self, s3_kit_instance=None, ipfs_model=None, cache_manager=None, credential_manager=None):
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
        
        logger.info("S3 Model initialized")
    
    def upload_file(self, file_path: str, bucket: str, key: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Upload a file to S3.
        
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
    
    def download_file(self, bucket: str, key: str, destination: str) -> Dict[str, Any]:
        """Download a file from S3.
        
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
    
    def list_objects(self, bucket: str, prefix: Optional[str] = None) -> Dict[str, Any]:
        """List objects in an S3 bucket.
        
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
                    result["error"] = s3_result.get("error", "Unknown error during S3 list operation")
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
    
    def delete_object(self, bucket: str, key: str) -> Dict[str, Any]:
        """Delete an object from S3.
        
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
                s3_result = self.s3_kit.s3_rm_file(key, bucket)
                
                if s3_result.get("success", False):
                    result["success"] = True
                    result["bucket"] = bucket
                    result["key"] = key
                else:
                    result["error"] = s3_result.get("error", "Unknown error during S3 delete operation")
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
    
    def ipfs_to_s3(self, cid: str, bucket: str, key: Optional[str] = None, pin: bool = True) -> Dict[str, Any]:
        """Get content from IPFS and upload to S3.
        
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
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                
                # Retrieve content from IPFS
                ipfs_result = self.ipfs_model.get_content(cid)
                
                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get("error", "Failed to retrieve content from IPFS")
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
                upload_result = self.upload_file(
                    temp_path, bucket, key, 
                    metadata={"ipfs_cid": cid}
                )
                
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
    
    def list_buckets(self) -> Dict[str, Any]:
        """List all available S3 buckets.
        
        Returns:
            Result dictionary with operation status and bucket list
        """
        start_time = time.time()
        result = self._create_result_dict("list_buckets")
        
        try:
            # Only continue if S3 kit is available
            if not self.s3_kit:
                result["error"] = "S3 kit not available"
                result["error_type"] = "DependencyError"
                return result
                
            # Use s3_kit to list buckets
            s3_result = self.s3_kit.s3_list_buckets()
            
            if s3_result.get("success", False):
                result["success"] = True
                result["buckets"] = s3_result.get("buckets", [])
                result["count"] = len(result["buckets"])
            else:
                result["error"] = s3_result.get("error", "Unknown error during S3 list buckets operation")
                result["error_type"] = s3_result.get("error_type", "S3ListBucketsError")
                
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
            
    def s3_to_ipfs(self, bucket: str, key: str, pin: bool = True) -> Dict[str, Any]:
        """Get content from S3 and add to IPFS.
        
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
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                
                # Download content from S3
                download_result = self.download_file(bucket, key, temp_path)
                
                if not download_result.get("success", False):
                    result["error"] = download_result.get("error", "Failed to download content from S3")
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