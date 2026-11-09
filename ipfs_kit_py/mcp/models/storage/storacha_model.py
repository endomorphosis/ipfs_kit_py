"""
Storacha (Web3.Storage) Model for MCP Server.

This module provides the business logic for Storacha (Web3.Storage) operations in the MCP server.
It integrates with the enhanced StorachaConnectionManager for reliable API communication.
"""

import logging
import os
import tempfile
import time
import json
from typing import Dict, Optional, Any, Union, BinaryIO

from ipfs_kit_py.mcp.models.storage.base_storage_model import BaseStorageModel
from ipfs_kit_py.mcp.extensions.storacha_connection import (
    StorachaConnectionManager,
    StorachaApiError
)
from ipfs_kit_py.mcp.mcp_error_handling import (
    MCPError,
    StorageError,
    StorageBackendUnavailableError,
    ContentNotFoundError,
    ValidationError
)

# Configure logger
logger = logging.getLogger(__name__)

# Global instance that can be shared across the application
storacha_kit_instance = None


class StorachaModel(BaseStorageModel):
    """Model for Storacha (Web3.Storage) operations.

    This class implements Storacha (Web3.Storage) storage operations using the BaseStorageModel interface.
    It provides methods for uploading files and CAR files, listing spaces and uploads, and
    cross-backend operations to transfer content between IPFS and Storacha.
    
    It uses the enhanced StorachaConnectionManager for reliable API communication with
    endpoint failover, circuit breaker patterns, and comprehensive error handling.
    """
    def __init__(
        self,
        storacha_kit_instance=None,
        ipfs_model=None,
        cache_manager=None,
        credential_manager=None,
        connection_manager=None,
        validate_endpoints: bool = True
    ):
        """Initialize Storacha model with dependencies.

        Args:
            storacha_kit_instance: storacha_kit instance for Web3.Storage operations
            ipfs_model: IPFS model for IPFS operations
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
            connection_manager: StorachaConnectionManager instance (created if not provided)
            validate_endpoints: Whether to validate connection endpoints on initialization
        """
        super().__init__(storacha_kit_instance, cache_manager, credential_manager)

        # Store the IPFS model for cross-backend operations
        self.ipfs_model = ipfs_model
        
        # Initialize the connection manager
        self.connection_manager = connection_manager
        if not self.connection_manager and credential_manager:
            # Try to get API key from credential manager
            api_key = self._get_api_key_from_credentials()
            
            # Create a new connection manager
            self.connection_manager = StorachaConnectionManager(
                api_key=api_key,
                validate_endpoints=validate_endpoints
            )
        
        self._check_dependencies()
        logger.info("Storacha Model initialized")
    
    def _check_dependencies(self) -> None:
        """Check if dependencies are available and log their status."""
        # Check for either kit or connection manager
        if not self.kit and not self.connection_manager:
            logger.warning("Neither storacha_kit nor connection_manager available - operating in limited mode")
        
        # Check for IPFS model (needed for cross-backend operations)
        if not self.ipfs_model:
            logger.warning("IPFS model not available - cross-backend operations will be unavailable")
    
    def _get_api_key_from_credentials(self) -> Optional[str]:
        """Attempt to get API key from credential manager."""
        if not self.credential_manager:
            return None
            
        try:
            # Try to get the Storacha API key
            credentials = self.credential_manager.get_credentials("storacha")
            if credentials and "api_key" in credentials:
                return credentials["api_key"]
                
            # Try alternative credential names
            for name in ["web3storage", "web3.storage", "w3storage"]:
                credentials = self.credential_manager.get_credentials(name)
                if credentials and "api_key" in credentials:
                    return credentials["api_key"]
                    
        except Exception as e:
            logger.warning(f"Error getting API key from credential manager: {e}")
            
        return None
        
    def is_available(self) -> bool:
        """Check if the Storacha service is available.
        
        Returns:
            True if available, False otherwise
        """
        if self.connection_manager:
            try:
                # Attempt a health check using the connection manager
                response = self.connection_manager.get("health")
                return response.status_code == 200
            except Exception as e:
                logger.warning(f"Storacha service unavailable: {e}")
                return False
        elif self.kit:
            # Fall back to kit availability check
            try:
                return self.kit.is_available()
            except Exception:
                return False
        
        return False

    def create_space(self, name: str = None) -> Dict[str, Any]:
        """Create a new storage space.

        Args:
            name: Optional name for the space

        Returns:
            Result dictionary with operation status and space details
        """
        start_time = time.time()
        result = self._create_result_template("create_space")

        try:
            # Try using the connection manager first
            if self.connection_manager:
                try:
                    data = {"name": name} if name else {}
                    response = self.connection_manager.post("spaces", json=data)
                    space_data = response.json()
                    
                    result["success"] = True
                    result["space_did"] = space_data.get("did")
                    
                    # Copy additional fields
                    for field in ["name", "type", "created"]:
                        if field in space_data:
                            result[field] = space_data[field]
                            
                except StorachaApiError as e:
                    result["error"] = str(e)
                    result["error_type"] = "SpaceCreationError"
                    result["status_code"] = e.status_code
                    
            # Fall back to kit if available and connection manager failed or is unavailable
            elif self.kit and not result["success"]:
                space_result = self.kit.w3_create(name=name)

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
                result["error"] = "Storacha services not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "create", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "create_space")

    def list_spaces(self) -> Dict[str, Any]:
        """List all available spaces.

        Returns:
            Result dictionary with operation status and space list
        """
        start_time = time.time()
        result = self._create_result_template("list_spaces")

        try:
            # Try using the connection manager first
            if self.connection_manager:
                try:
                    response = self.connection_manager.get("spaces")
                    spaces_data = response.json()
                    
                    result["success"] = True
                    result["spaces"] = spaces_data.get("spaces", [])
                    result["count"] = len(result["spaces"])
                            
                except StorachaApiError as e:
                    result["error"] = str(e)
                    result["error_type"] = "ListSpacesError"
                    result["status_code"] = e.status_code
                    
            # Fall back to kit if available and connection manager failed or is unavailable
            elif self.kit and not result["success"]:
                list_result = self.kit.w3_list_spaces()

                if list_result.get("success", False):
                    result["success"] = True
                    result["spaces"] = list_result.get("spaces", [])
                    result["count"] = len(result["spaces"])
                else:
                    result["error"] = list_result.get("error", "Failed to list spaces")
                    result["error_type"] = list_result.get("error_type", "ListSpacesError")
            else:
                result["error"] = "Storacha services not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "list_spaces")

    def set_current_space(self, space_did: str) -> Dict[str, Any]:
        """Set the current space for operations.

        Args:
            space_did: Space DID to use

        Returns:
            Result dictionary with operation status
        """
        start_time = time.time()
        result = self._create_result_template("set_current_space")

        try:
            # Validate inputs
            if not space_did:
                result["error"] = "Space DID is required"
                result["error_type"] = "ValidationError"
                return result

            # Try using the connection manager first
            if self.connection_manager:
                try:
                    response = self.connection_manager.post(f"spaces/{space_did}/use")
                    space_data = response.json()
                    
                    result["success"] = True
                    result["space_did"] = space_did
                    
                    # Copy additional fields
                    if "space_info" in space_data:
                        result["space_info"] = space_data["space_info"]
                            
                except StorachaApiError as e:
                    result["error"] = str(e)
                    result["error_type"] = "SetSpaceError"
                    result["status_code"] = e.status_code
                    
            # Fall back to kit if available and connection manager failed or is unavailable
            elif self.kit and not result["success"]:
                space_result = self.kit.w3_use(space_did)

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
                result["error"] = "Storacha services not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "configure", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "set_current_space")

    def upload_file(
        self, 
        file_path: str, 
        space_did: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Upload a file to Storacha.

        Args:
            file_path: Path to the file to upload
            space_did: Optional space DID to use (otherwise uses current space)
            metadata: Optional metadata to associate with the file

        Returns:
            Result dictionary with operation status and upload details
        """
        start_time = time.time()
        result = self._create_result_template("upload_file")

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
            file_size = self._get_file_size(file_path)
            result["size_bytes"] = file_size

            # Try using the connection manager first
            if self.connection_manager:
                try:
                    upload_result = self.connection_manager.upload_file(file_path, metadata)
                    
                    result["success"] = True
                    result["cid"] = upload_result.get("cid")
                    
                    # Copy additional fields
                    for field in ["root_cid", "shard_size", "upload_id"]:
                        if field in upload_result:
                            result[field] = upload_result[field]
                            
                    # If space_did was provided or set, include it
                    if space_did:
                        result["space_did"] = space_did
                            
                except StorachaApiError as e:
                    result["error"] = str(e)
                    result["error_type"] = "UploadError"
                    result["status_code"] = e.status_code
                    
            # Fall back to kit if available and connection manager failed or is unavailable
            elif self.kit and not result["success"]:
                upload_result = self.kit.w3_up(file_path)

                if upload_result.get("success", False):
                    result["success"] = True
                    result["cid"] = upload_result.get("cid")

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
                result["error"] = "Storacha services not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(
                result, "upload", start_time, file_size if result["success"] else None
            )

        except Exception as e:
            return self._handle_exception(e, result, "upload_file")

    def upload_car(
        self, 
        car_path: str, 
        space_did: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload a CAR file to Storacha.

        Args:
            car_path: Path to the CAR file to upload
            space_did: Optional space DID to use (otherwise uses current space)

        Returns:
            Result dictionary with operation status and upload details
        """
        start_time = time.time()
        result = self._create_result_template("upload_car")

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
            file_size = self._get_file_size(car_path)
            result["size_bytes"] = file_size

            # Try using the connection manager first
            if self.connection_manager:
                try:
                    # Special header for CAR files
                    headers = {"Content-Type": "application/car"}
                    
                    with open(car_path, 'rb') as car_file:
                        response = self.connection_manager.post(
                            "car", 
                            data=car_file, 
                            headers=headers
                        )
                    
                    upload_result = response.json()
                    
                    result["success"] = True
                    result["cid"] = upload_result.get("cid")
                    result["car_cid"] = upload_result.get("carCid", upload_result.get("car_cid"))
                    
                    # Copy additional fields
                    for field in ["root_cid", "shard_size", "upload_id"]:
                        if field in upload_result:
                            result[field] = upload_result[field]
                            
                    # If space_did was provided or set, include it
                    if space_did:
                        result["space_did"] = space_did
                            
                except StorachaApiError as e:
                    result["error"] = str(e)
                    result["error_type"] = "UploadCarError"
                    result["status_code"] = e.status_code
                    
            # Fall back to kit if available and connection manager failed or is unavailable
            elif self.kit and not result["success"]:
                upload_result = self.kit.w3_up_car(car_path)

                if upload_result.get("success", False):
                    result["success"] = True
                    result["cid"] = upload_result.get("cid")
                    result["car_cid"] = upload_result.get("car_cid")

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
                result["error"] = "Storacha services not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(
                result, "upload", start_time, file_size if result["success"] else None
            )

        except Exception as e:
            return self._handle_exception(e, result, "upload_car")

    def list_uploads(
        self, 
        space_did: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List uploads in a space.

        Args:
            space_did: Optional space DID to use (otherwise uses current space)
            limit: Maximum number of uploads to return
            offset: Offset for pagination

        Returns:
            Result dictionary with operation status and upload list
        """
        start_time = time.time()
        result = self._create_result_template("list_uploads")

        try:
            # Set space if provided
            if space_did:
                space_result = self.set_current_space(space_did)
                if not space_result.get("success", False):
                    result["error"] = space_result.get("error", "Failed to set space")
                    result["error_type"] = space_result.get("error_type", "SetSpaceError")
                    result["space_result"] = space_result
                    return result

            # Try using the connection manager first
            if self.connection_manager:
                try:
                    # Construct query parameters
                    params = {
                        "limit": limit,
                        "offset": offset
                    }
                    
                    response = self.connection_manager.get("uploads", params=params)
                    list_data = response.json()
                    
                    result["success"] = True
                    result["uploads"] = list_data.get("uploads", [])
                    result["count"] = len(result["uploads"])
                    result["total"] = list_data.get("total", len(result["uploads"]))
                    
                    # If space_did was provided or set, include it
                    if space_did:
                        result["space_did"] = space_did
                            
                except StorachaApiError as e:
                    result["error"] = str(e)
                    result["error_type"] = "ListUploadsError"
                    result["status_code"] = e.status_code
                    
            # Fall back to kit if available and connection manager failed or is unavailable
            elif self.kit and not result["success"]:
                list_result = self.kit.w3_list()

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
                result["error"] = "Storacha services not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "list", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "list_uploads")

    def delete_upload(self, cid: str, space_did: Optional[str] = None) -> Dict[str, Any]:
        """Delete an upload from Storacha.

        Args:
            cid: Content identifier to delete
            space_did: Optional space DID to use (otherwise uses current space)

        Returns:
            Result dictionary with operation status
        """
        start_time = time.time()
        result = self._create_result_template("delete_upload")

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

            # Try using the connection manager first
            if self.connection_manager:
                try:
                    response = self.connection_manager.delete(f"uploads/{cid}")
                    
                    # If we get here, the deletion was successful
                    result["success"] = True
                    result["cid"] = cid
                    
                    # If space_did was provided or set, include it
                    if space_did:
                        result["space_did"] = space_did
                            
                except StorachaApiError as e:
                    result["error"] = str(e)
                    result["error_type"] = "DeleteUploadError"
                    result["status_code"] = e.status_code
                    
            # Fall back to kit if available and connection manager failed or is unavailable
            elif self.kit and not result["success"]:
                delete_result = self.kit.w3_remove(cid)

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
                result["error"] = "Storacha services not available"
                result["error_type"] = "DependencyError"

            return self._handle_operation_result(result, "delete", start_time)

        except Exception as e:
            return self._handle_exception(e, result, "delete_upload")

    def ipfs_to_storacha(
        self, 
        cid: str, 
        space_did: Optional[str] = None, 
        pin: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get content from IPFS and upload to Storacha.

        Args:
            cid: Content identifier in IPFS
            space_did: Optional space DID to use (otherwise uses current space)
            pin: Whether to pin the content in IPFS
            metadata: Optional metadata to associate with the content

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_template("ipfs_to_storacha")

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
            if not self.connection_manager and not self.kit:
                result["error"] = "Storacha services not available"
                result["error_type"] = "DependencyError"
                return result

            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result

            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{cid}") as temp_file:
                temp_path = temp_file.name

                try:
                    # Retrieve content from IPFS
                    ipfs_result = self.ipfs_model.get_content(cid)

                    if not ipfs_result.get("success", False):
                        result["error"] = ipfs_result.get(
                            "error", "Failed to retrieve content from IPFS"
                        )
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

                    temp_file.write(content)
                    temp_file.flush()

                    # Pin the content if requested
                    if pin:
                        pin_result = self.ipfs_model.pin_content(cid)
                        if not pin_result.get("success", False):
                            logger.warning(f"Failed to pin content {cid}: {pin_result.get('error')}")

                    # Prepare metadata if not provided
                    if not metadata:
                        metadata = {
                            "source": "ipfs",
                            "ipfs_cid": cid,
                            "timestamp": time.time()
                        }
                    else:
                        # Add source info to provided metadata
                        metadata = {**metadata, "source": "ipfs", "ipfs_cid": cid}

                    # Upload to Storacha
                    upload_result = self.upload_file(temp_path, space_did, metadata)

                    if not upload_result.get("success", False):
                        result["error"] = upload_result.get(
                            "error", "Failed to upload content to Storacha"
                        )
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

                finally:
                    # Clean up the temporary file
                    try:
                        os.unlink(temp_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete temporary file {temp_path}: {e}")

            return self._handle_operation_result(
                result,
                "transfer",
                start_time,
                result.get("size_bytes") if result["success"] else None
            )

        except Exception as e:
            return self._handle_exception(e, result, "ipfs_to_storacha")

    def storacha_to_ipfs(
        self, 
        cid: str, 
        space_did: Optional[str] = None, 
        pin: bool = True
    ) -> Dict[str, Any]:
        """Get content from Storacha and add to IPFS.

        Args:
            cid: Content identifier in Storacha
            space_did: Optional space DID to use (otherwise uses current space)
            pin: Whether to pin the content in IPFS

        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_template("storacha_to_ipfs")

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
            if not self.connection_manager and not self.kit:
                result["error"] = "Storacha services not available"
                result["error_type"] = "DependencyError"
                return result

            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result

            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{cid}") as temp_file:
                temp_path = temp_file.name

                try:
                    # Download content from Storacha
                    # First determine the current space if none provided
                    current_space = space_did
                    if not current_space:
                        # Find current space from connection manager or kit
                        if self.connection_manager:
                            try:
                                response = self.connection_manager.get("spaces")
                                spaces_data = response.json()
                                spaces = spaces_data.get("spaces", [])
                                if spaces:
                                    # Find current space (marked as current=true) or use the first one
                                    current_space = next(
                                        (space["did"] for space in spaces if space.get("current", False)),
                                        spaces[0]["did"]
                                    )
                            except Exception as e:
                                logger.warning(f"Error getting current space: {e}")
                                
                        if not current_space and self.kit:
                            # Try with kit as fallback
                            spaces_result = self.kit.w3_list_spaces()
                            if spaces_result.get("success", False) and spaces_result.get("spaces"):
                                spaces = spaces_result.get("spaces", [])
                                if spaces:
                                    # Find current space or use the first one
                                    current_space = next(
                                        (space["did"] for space in spaces if space.get("current", False)),
                                        spaces[0]["did"]
                                    )
                                    
                    if not current_space:
                        result["error"] = "No space available and none provided"
                        result["error_type"] = "NoSpaceError"
                        return result
                                            
                    # Download content from Storacha
                    if self.connection_manager:
                        try:
                            # Get content directly to file
                            with open(temp_path, 'wb') as f:
                                response = self.connection_manager.get(
                                    f"content/{cid}", 
                                    stream=True
                                )
                                for chunk in response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            
                            # Success
                            download_success = True
                        except StorachaApiError as e:
                            logger.warning(f"Error downloading from Storacha: {e}")
                            download_success = False
                    else:
                        # Fallback to kit
                        download_result = self.kit.store_get(
                            space_did=current_space, cid=cid, output_file=temp_path
                        )
                        download_success = download_result.get("success", False)
                        
                    if not download_success:
                        result["error"] = "Failed to download content from Storacha"
                        result["error_type"] = "StorachaDownloadError"
                        return result

                    # Get file size for statistics
                    file_size = self._get_file_size(temp_path)
                    result["size_bytes"] = file_size

                    # Read the file content
                    with open(temp_path, "rb") as f:
                        content = f.read()

                    # Add to IPFS
                    ipfs_result = self.ipfs_model.add_content(
                        content, filename=os.path.basename(temp_path)
                    )

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
                            logger.warning(
                                f"Failed to pin content {ipfs_cid}: {pin_result.get('error')}"
                            )

                    # Set success and copy relevant fields
                    result["success"] = True
                    result["storacha_cid"] = cid
                    result["ipfs_cid"] = ipfs_cid
                    result["size_bytes"] = file_size

                    # If space_did was provided or found, include it
                    if current_space:
                        result["space_did"] = current_space
                        
                finally:
                    # Clean up the temporary file
                    try:
                        os.unlink(temp_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete temporary file {temp_path}: {e}")

            return self._handle_operation_result(
                result,
                "transfer",
                start_time,
                result.get("size_bytes") if result["success"] else None
            )

        except Exception as e:
            return self._handle_exception(e, result, "storacha_to_ipfs")
            
    def get_connection_status(self) -> Dict[str, Any]:
        """Get status information about the Storacha connection.
        
        Returns:
            Status information dictionary
        """
        if self.connection_manager:
            return self.connection_manager.get_status()
        else:
            return {
                "error": "Connection manager not available",
                "using_legacy_kit": self.kit is not None
            }
    
    def _handle_exception(self, exception: Exception, result: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """Handle exceptions during operations.
        
        This method extends the base implementation to handle StorachaApiError exceptions specially.
        
        Args:
            exception: Exception that occurred
            result: Current result dictionary
            operation: Name of the operation that failed
            
        Returns:
            Updated result dictionary
        """
        # Special handling for StorachaApiError
        if isinstance(exception, StorachaApiError):
            result["success"] = False
            result["error"] = str(exception)
            result["error_type"] = "StorachaApiError"
            result["status_code"] = exception.status_code
            if exception.response:
                result["response"] = exception.response
            
            # Log the error
            logger.error(f"Storacha API error during {operation}: {str(exception)}")
            
            return result
            
        # Otherwise use the base implementation
        return super()._handle_exception(exception, result, operation)