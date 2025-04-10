"""
Storacha (Web3.Storage) Model for MCP Server.

This module provides the business logic for Storacha (Web3.Storage) operations in the MCP server.
It relies on the storacha_kit module for underlying functionality.
"""

import logging
import os
import tempfile
import time
from typing import Dict, List, Optional, Any, Union

from ipfs_kit_py.storacha_kit import storacha_kit
from ipfs_kit_py.mcp.models.storage import BaseStorageModel

# Configure logger
logger = logging.getLogger(__name__)


class StorachaModel(BaseStorageModel):
    """Model for Storacha (Web3.Storage) operations."""
    
    def __init__(self, storacha_kit_instance=None, ipfs_model=None, cache_manager=None, credential_manager=None):
        """Initialize Storacha model with dependencies.
        
        Args:
            storacha_kit_instance: storacha_kit instance for Web3.Storage operations
            ipfs_model: IPFS model for IPFS operations
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
        """
        super().__init__(storacha_kit_instance, cache_manager, credential_manager)
        
        # Store the storacha_kit instance
        self.storacha_kit = storacha_kit_instance
        
        # Store the IPFS model for cross-backend operations
        self.ipfs_model = ipfs_model
        
        logger.info("Storacha Model initialized")
    
    def create_space(self, name: str = None) -> Dict[str, Any]:
        """Create a new storage space.
        
        Args:
            name: Optional name for the space
            
        Returns:
            Result dictionary with operation status and space details
        """
        start_time = time.time()
        result = self._create_result_dict("create_space")
        
        try:
            # Use storacha_kit to create a space
            if self.storacha_kit:
                space_result = self.storacha_kit.w3_create(name=name)
                
                if space_result.get("success", False):
                    result["success"] = True
                    result["space_did"] = space_result.get("space_did")
                    
                    # Copy other fields if available
                    for field in ["name", "email", "type", "space_info"]:
                        if field in space_result:
                            result[field] = space_result[field]
                else:
                    result["error"] = space_result.get("error", "Failed to create space")
                    result["error_type"] = space_result.get("error_type", "SpaceCreationError")
            else:
                result["error"] = "Storacha kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_spaces(self) -> Dict[str, Any]:
        """List all available spaces.
        
        Returns:
            Result dictionary with operation status and space list
        """
        start_time = time.time()
        result = self._create_result_dict("list_spaces")
        
        try:
            # Use storacha_kit to list spaces
            if self.storacha_kit:
                list_result = self.storacha_kit.w3_list_spaces()
                
                if list_result.get("success", False):
                    result["success"] = True
                    result["spaces"] = list_result.get("spaces", [])
                    result["count"] = len(result["spaces"])
                else:
                    result["error"] = list_result.get("error", "Failed to list spaces")
                    result["error_type"] = list_result.get("error_type", "ListSpacesError")
            else:
                result["error"] = "Storacha kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def set_current_space(self, space_did: str) -> Dict[str, Any]:
        """Set the current space for operations.
        
        Args:
            space_did: Space DID to use
            
        Returns:
            Result dictionary with operation status
        """
        start_time = time.time()
        result = self._create_result_dict("set_current_space")
        
        try:
            # Validate inputs
            if not space_did:
                result["error"] = "Space DID is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Use storacha_kit to set the current space
            if self.storacha_kit:
                space_result = self.storacha_kit.w3_use(space_did)
                
                if space_result.get("success", False):
                    result["success"] = True
                    result["space_did"] = space_did
                    
                    # Copy space info if available
                    if "space_info" in space_result:
                        result["space_info"] = space_result["space_info"]
                else:
                    result["error"] = space_result.get("error", "Failed to set current space")
                    result["error_type"] = space_result.get("error_type", "SetSpaceError")
            else:
                result["error"] = "Storacha kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def upload_file(self, file_path: str, space_did: Optional[str] = None) -> Dict[str, Any]:
        """Upload a file to Storacha.
        
        Args:
            file_path: Path to the file to upload
            space_did: Optional space DID to use (otherwise uses current space)
            
        Returns:
            Result dictionary with operation status and upload details
        """
        start_time = time.time()
        result = self._create_result_dict("upload_file")
        
        try:
            # Validate inputs
            if not os.path.exists(file_path):
                result["error"] = f"File not found: {file_path}"
                result["error_type"] = "FileNotFoundError"
                return result
            
            # Set space if provided
            if space_did:
                space_result = self.set_current_space(space_did)
                if not space_result.get("success", False):
                    result["error"] = space_result.get("error", "Failed to set space")
                    result["error_type"] = space_result.get("error_type", "SetSpaceError")
                    result["space_result"] = space_result
                    return result
            
            # Get file size for statistics
            file_size = os.path.getsize(file_path)
            
            # Use storacha_kit to upload the file
            if self.storacha_kit:
                upload_result = self.storacha_kit.w3_up(file_path)
                
                if upload_result.get("success", False):
                    result["success"] = True
                    result["cid"] = upload_result.get("cid")
                    result["size_bytes"] = file_size
                    
                    # Copy additional fields if available
                    for field in ["root_cid", "shard_size", "upload_id"]:
                        if field in upload_result:
                            result[field] = upload_result[field]
                    
                    # If space_did was provided or set, include it
                    if space_did:
                        result["space_did"] = space_did
                else:
                    result["error"] = upload_result.get("error", "Failed to upload file")
                    result["error_type"] = upload_result.get("error_type", "UploadError")
            else:
                result["error"] = "Storacha kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result, file_size if result["success"] else None)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def upload_car(self, car_path: str, space_did: Optional[str] = None) -> Dict[str, Any]:
        """Upload a CAR file to Storacha.
        
        Args:
            car_path: Path to the CAR file to upload
            space_did: Optional space DID to use (otherwise uses current space)
            
        Returns:
            Result dictionary with operation status and upload details
        """
        start_time = time.time()
        result = self._create_result_dict("upload_car")
        
        try:
            # Validate inputs
            if not os.path.exists(car_path):
                result["error"] = f"CAR file not found: {car_path}"
                result["error_type"] = "FileNotFoundError"
                return result
            
            # Set space if provided
            if space_did:
                space_result = self.set_current_space(space_did)
                if not space_result.get("success", False):
                    result["error"] = space_result.get("error", "Failed to set space")
                    result["error_type"] = space_result.get("error_type", "SetSpaceError")
                    result["space_result"] = space_result
                    return result
            
            # Get file size for statistics
            file_size = os.path.getsize(car_path)
            
            # Use storacha_kit to upload the CAR file
            if self.storacha_kit:
                upload_result = self.storacha_kit.w3_up_car(car_path)
                
                if upload_result.get("success", False):
                    result["success"] = True
                    result["cid"] = upload_result.get("cid")
                    result["car_cid"] = upload_result.get("car_cid")
                    result["size_bytes"] = file_size
                    
                    # Copy additional fields if available
                    for field in ["root_cid", "shard_size", "upload_id"]:
                        if field in upload_result:
                            result[field] = upload_result[field]
                    
                    # If space_did was provided or set, include it
                    if space_did:
                        result["space_did"] = space_did
                else:
                    result["error"] = upload_result.get("error", "Failed to upload CAR file")
                    result["error_type"] = upload_result.get("error_type", "UploadCarError")
            else:
                result["error"] = "Storacha kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result, file_size if result["success"] else None)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def list_uploads(self, space_did: Optional[str] = None) -> Dict[str, Any]:
        """List uploads in a space.
        
        Args:
            space_did: Optional space DID to use (otherwise uses current space)
            
        Returns:
            Result dictionary with operation status and upload list
        """
        start_time = time.time()
        result = self._create_result_dict("list_uploads")
        
        try:
            # Set space if provided
            if space_did:
                space_result = self.set_current_space(space_did)
                if not space_result.get("success", False):
                    result["error"] = space_result.get("error", "Failed to set space")
                    result["error_type"] = space_result.get("error_type", "SetSpaceError")
                    result["space_result"] = space_result
                    return result
            
            # Use storacha_kit to list uploads
            if self.storacha_kit:
                list_result = self.storacha_kit.w3_list()
                
                if list_result.get("success", False):
                    result["success"] = True
                    result["uploads"] = list_result.get("uploads", [])
                    result["count"] = len(result["uploads"])
                    
                    # If space_did was provided or set, include it
                    if space_did:
                        result["space_did"] = space_did
                else:
                    result["error"] = list_result.get("error", "Failed to list uploads")
                    result["error_type"] = list_result.get("error_type", "ListUploadsError")
            else:
                result["error"] = "Storacha kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def delete_upload(self, cid: str, space_did: Optional[str] = None) -> Dict[str, Any]:
        """Delete an upload from Storacha.
        
        Args:
            cid: Content identifier to delete
            space_did: Optional space DID to use (otherwise uses current space)
            
        Returns:
            Result dictionary with operation status
        """
        start_time = time.time()
        result = self._create_result_dict("delete_upload")
        
        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Set space if provided
            if space_did:
                space_result = self.set_current_space(space_did)
                if not space_result.get("success", False):
                    result["error"] = space_result.get("error", "Failed to set space")
                    result["error_type"] = space_result.get("error_type", "SetSpaceError")
                    result["space_result"] = space_result
                    return result
            
            # Use storacha_kit to delete the upload
            if self.storacha_kit:
                delete_result = self.storacha_kit.w3_remove(cid)
                
                if delete_result.get("success", False):
                    result["success"] = True
                    result["cid"] = cid
                    
                    # If space_did was provided or set, include it
                    if space_did:
                        result["space_did"] = space_did
                else:
                    result["error"] = delete_result.get("error", "Failed to delete upload")
                    result["error_type"] = delete_result.get("error_type", "DeleteUploadError")
            else:
                result["error"] = "Storacha kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def ipfs_to_storacha(self, cid: str, space_did: Optional[str] = None, pin: bool = True) -> Dict[str, Any]:
        """Get content from IPFS and upload to Storacha.
        
        Args:
            cid: Content identifier in IPFS
            space_did: Optional space DID to use (otherwise uses current space)
            pin: Whether to pin the content in IPFS
            
        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("ipfs_to_storacha")
        
        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Set space if provided
            if space_did:
                space_result = self.set_current_space(space_did)
                if not space_result.get("success", False):
                    result["error"] = space_result.get("error", "Failed to set space")
                    result["error_type"] = space_result.get("error_type", "SetSpaceError")
                    result["space_result"] = space_result
                    return result
            
            # Only continue if all dependencies are available
            if not self.storacha_kit:
                result["error"] = "Storacha kit not available"
                result["error_type"] = "DependencyError"
                return result
                
            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result
            
            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{cid}") as temp_file:
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
                
                # Upload to Storacha
                upload_result = self.upload_file(temp_path, space_did)
                
                # Clean up the temporary file
                os.unlink(temp_path)
                
                if not upload_result.get("success", False):
                    result["error"] = upload_result.get("error", "Failed to upload content to Storacha")
                    result["error_type"] = upload_result.get("error_type", "StorachaUploadError")
                    result["upload_result"] = upload_result
                    return result
                
                # Set success and copy relevant fields
                result["success"] = True
                result["ipfs_cid"] = cid
                result["storacha_cid"] = upload_result.get("cid")
                result["size_bytes"] = upload_result.get("size_bytes")
                
                # Copy additional fields if available
                for field in ["root_cid", "upload_id"]:
                    if field in upload_result:
                        result[field] = upload_result[field]
                
                # If space_did was provided or set, include it
                if space_did:
                    result["space_did"] = space_did
            
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
        
    def storacha_to_ipfs(self, cid: str, space_did: Optional[str] = None, pin: bool = True) -> Dict[str, Any]:
        """Get content from Storacha and add to IPFS.
        
        Args:
            cid: Content identifier in Storacha
            space_did: Optional space DID to use (otherwise uses current space)
            pin: Whether to pin the content in IPFS
            
        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("storacha_to_ipfs")
        
        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Set space if provided
            if space_did:
                space_result = self.set_current_space(space_did)
                if not space_result.get("success", False):
                    result["error"] = space_result.get("error", "Failed to set space")
                    result["error_type"] = space_result.get("error_type", "SetSpaceError")
                    result["space_result"] = space_result
                    return result
            
            # Only continue if all dependencies are available
            if not self.storacha_kit:
                result["error"] = "Storacha kit not available"
                result["error_type"] = "DependencyError"
                return result
                
            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result
            
            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{cid}") as temp_file:
                temp_path = temp_file.name
                
                # Download content from Storacha
                # First get the current space if none provided
                current_space = space_did
                if not current_space:
                    # Find current space from Storacha kit
                    spaces_result = self.storacha_kit.w3_list_spaces()
                    if not spaces_result.get("success", False) or not spaces_result.get("spaces"):
                        result["error"] = "No space available and none provided"
                        result["error_type"] = "NoSpaceError"
                        os.unlink(temp_path)
                        return result
                    
                    # Use the first space if current space not found
                    spaces = spaces_result.get("spaces", [])
                    if not spaces:
                        result["error"] = "No spaces available"
                        result["error_type"] = "NoSpaceError"
                        os.unlink(temp_path)
                        return result
                    
                    # Find current space (marked as current=true) or use the first one
                    current_space = next((space["did"] for space in spaces if space.get("current", False)), spaces[0]["did"])
                
                # Download from Storacha
                download_result = self.storacha_kit.store_get(
                    space_did=current_space,
                    cid=cid,
                    output_file=temp_path
                )
                
                if not download_result.get("success", False):
                    result["error"] = download_result.get("error", "Failed to download content from Storacha")
                    result["error_type"] = download_result.get("error_type", "StorachaDownloadError")
                    result["download_result"] = download_result
                    os.unlink(temp_path)
                    return result
                
                # Get file size for statistics
                file_size = os.path.getsize(temp_path)
                
                # Read the file content
                with open(temp_path, "rb") as f:
                    content = f.read()
                
                # Add to IPFS
                ipfs_result = self.ipfs_model.add_content(content, filename=os.path.basename(temp_path))
                
                # Clean up the temporary file
                os.unlink(temp_path)
                
                if not ipfs_result.get("success", False):
                    result["error"] = ipfs_result.get("error", "Failed to add content to IPFS")
                    result["error_type"] = ipfs_result.get("error_type", "IPFSAddError")
                    result["ipfs_result"] = ipfs_result
                    return result
                
                ipfs_cid = ipfs_result.get("cid")
                
                # Pin the content if requested
                if pin and ipfs_cid:
                    pin_result = self.ipfs_model.pin_content(ipfs_cid)
                    if not pin_result.get("success", False):
                        logger.warning(f"Failed to pin content {ipfs_cid}: {pin_result.get('error')}")
                
                # Set success and copy relevant fields
                result["success"] = True
                result["storacha_cid"] = cid
                result["ipfs_cid"] = ipfs_cid
                result["size_bytes"] = file_size
                
                # If space_did was provided or found, include it
                if current_space:
                    result["space_did"] = current_space
            
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