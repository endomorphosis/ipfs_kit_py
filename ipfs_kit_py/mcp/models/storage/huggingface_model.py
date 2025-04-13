"""
Hugging Face Model for MCP Server.

This module provides the business logic for Hugging Face Hub operations in the MCP server.
It relies on the huggingface_kit module for underlying functionality.
"""

import logging
import huggingface_hub
from huggingface_hub import HfApi, HfFolder
import os
import tempfile
import time
from typing import Dict, List, Optional, Any, Union

from ipfs_kit_py.huggingface_kit import huggingface_kit
from ipfs_kit_py.mcp.models.storage import BaseStorageModel

# Configure logger
logger = logging.getLogger(__name__)


class HuggingFaceModel(BaseStorageModel):
    """Model for Hugging Face Hub operations."""
    
    def __init__(self, huggingface_kit_instance=None, ipfs_model=None, cache_manager=None, credential_manager=None):
        """Initialize Hugging Face model with dependencies.
        
        Args:
            huggingface_kit_instance: huggingface_kit instance for Hugging Face operations
            ipfs_model: IPFS model for IPFS operations
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
        """
        super().__init__(huggingface_kit_instance, cache_manager, credential_manager)
        
        # Store the huggingface_kit instance
        self.hf_kit = huggingface_kit_instance
        
        # Store the IPFS model for cross-backend operations
        self.ipfs_model = ipfs_model
        
        logger.info("Hugging Face Model initialized")
    
    def authenticate(self, token: str) -> Dict[str, Any]:
        """Authenticate with Hugging Face Hub.
        
        Args:
            token: Hugging Face Hub API token
            
        Returns:
            Result dictionary with operation status and user info
        """
        start_time = time.time()
        result = self._create_result_dict("authenticate")
        
        try:
            # Validate inputs
            if not token:
                result["error"] = "Token is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Use huggingface_kit to authenticate
            if self.hf_kit:
                auth_result = self.hf_kit.login(token=token)
                
                if auth_result.get("success", False):
                    result["success"] = True
                    result["authenticated"] = True
                    
                    # Store user info if available
                    if "user_info" in auth_result:
                        result["user_info"] = auth_result["user_info"]
                else:
                    result["error"] = auth_result.get("error", "Authentication failed")
                    result["error_type"] = auth_result.get("error_type", "AuthenticationError")
            else:
                result["error"] = "Hugging Face kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def create_repository(self, repo_id: str, repo_type: str = "model", private: bool = False) -> Dict[str, Any]:
        """Create a new repository on Hugging Face Hub.
        
        Args:
            repo_id: Repository ID (username/repo-name)
            repo_type: Repository type (model, dataset, space)
            private: Whether the repository should be private
            
        Returns:
            Result dictionary with operation status and repository info
        """
        start_time = time.time()
        result = self._create_result_dict("create_repository")
        
        try:
            # Validate inputs
            if not repo_id:
                result["error"] = "Repository ID is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Validate repo_type
            valid_types = ["model", "dataset", "space"]
            if repo_type not in valid_types:
                result["error"] = f"Invalid repository type. Must be one of: {', '.join(valid_types)}"
                result["error_type"] = "ValidationError"
                return result
            
            # Use huggingface_kit to create repository
            if self.hf_kit:
                repo_result = self.hf_kit.create_repo(repo_id, repo_type=repo_type, private=private)
                
                if repo_result.get("success", False):
                    result["success"] = True
                    result["repo_id"] = repo_id
                    result["repo_type"] = repo_type
                    result["private"] = private
                    
                    # Include repository URL and details if available
                    if "url" in repo_result:
                        result["url"] = repo_result["url"]
                    if "repo" in repo_result:
                        result["repo_details"] = repo_result["repo"]
                else:
                    result["error"] = repo_result.get("error", "Failed to create repository")
                    result["error_type"] = repo_result.get("error_type", "RepositoryCreationError")
            else:
                result["error"] = "Hugging Face kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def upload_file(self, file_path: str, repo_id: str, path_in_repo: Optional[str] = None, 
                    commit_message: Optional[str] = None, repo_type: str = "model") -> Dict[str, Any]:
        """Upload a file to a Hugging Face Hub repository.
        
        Args:
            file_path: Path to the file to upload
            repo_id: Repository ID (username/repo-name)
            path_in_repo: Path within the repository (uses filename if not provided)
            commit_message: Commit message for the upload
            repo_type: Repository type (model, dataset, space)
            
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
            
            if not repo_id:
                result["error"] = "Repository ID is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Default to filename if path_in_repo not provided
            if not path_in_repo:
                path_in_repo = os.path.basename(file_path)
            
            # Default commit message
            if not commit_message:
                commit_message = f"Upload {os.path.basename(file_path)}"
            
            # Get file size for statistics
            file_size = os.path.getsize(file_path)
            
            # Use huggingface_kit to upload the file
            if self.hf_kit:
                upload_result = self.hf_kit.upload_file_to_repo(
                    repo_id=repo_id,
                    file_path=file_path,
                    path_in_repo=path_in_repo,
                    commit_message=commit_message,
                    repo_type=repo_type
                )
                
                if upload_result.get("success", False):
                    result["success"] = True
                    result["repo_id"] = repo_id
                    result["repo_type"] = repo_type
                    result["path_in_repo"] = path_in_repo
                    result["size_bytes"] = file_size
                    
                    # Include URL if available
                    if "url" in upload_result:
                        result["url"] = upload_result["url"]
                    if "commit_url" in upload_result:
                        result["commit_url"] = upload_result["commit_url"]
                else:
                    result["error"] = upload_result.get("error", "Failed to upload file")
                    result["error_type"] = upload_result.get("error_type", "UploadError")
            else:
                result["error"] = "Hugging Face kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result, file_size if result["success"] else None)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def download_file(self, repo_id: str, filename: str, destination: str, 
                      revision: Optional[str] = None, repo_type: str = "model") -> Dict[str, Any]:
        """Download a file from a Hugging Face Hub repository.
        
        Args:
            repo_id: Repository ID (username/repo-name)
            filename: Filename to download
            destination: Local path to save the file
            revision: Optional Git revision (branch, tag, or commit hash)
            repo_type: Repository type (model, dataset, space)
            
        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("download_file")
        
        try:
            # Validate inputs
            if not repo_id:
                result["error"] = "Repository ID is required"
                result["error_type"] = "ValidationError"
                return result
            
            if not filename:
                result["error"] = "Filename is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Create the destination directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
            
            # Use huggingface_kit to download the file
            if self.hf_kit:
                download_result = self.hf_kit.download_file_from_repo(
                    repo_id=repo_id,
                    filename=filename,
                    local_path=destination,
                    revision=revision,
                    repo_type=repo_type
                )
                
                if download_result.get("success", False):
                    # Get file size for statistics
                    file_size = os.path.getsize(destination) if os.path.exists(destination) else 0
                    
                    result["success"] = True
                    result["repo_id"] = repo_id
                    result["repo_type"] = repo_type
                    result["filename"] = filename
                    result["destination"] = destination
                    result["size_bytes"] = file_size
                    
                    if revision:
                        result["revision"] = revision
                else:
                    result["error"] = download_result.get("error", "Failed to download file")
                    result["error_type"] = download_result.get("error_type", "DownloadError")
            else:
                result["error"] = "Hugging Face kit not available"
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
    
    def list_models(self, author: Optional[str] = None, search: Optional[str] = None,
                   limit: int = 50) -> Dict[str, Any]:
        """List models on Hugging Face Hub.
        
        Args:
            author: Optional filter by author/organization
            search: Optional search query
            limit: Maximum number of results
            
        Returns:
            Result dictionary with operation status and model list
        """
        start_time = time.time()
        result = self._create_result_dict("list_models")
        
        try:
            # Use huggingface_kit to list models
            if self.hf_kit:
                list_result = self.hf_kit.list_models(author=author, search=search, limit=limit)
                
                if list_result.get("success", False):
                    result["success"] = True
                    result["models"] = list_result.get("models", [])
                    result["count"] = len(result["models"])
                    
                    if author:
                        result["author"] = author
                    if search:
                        result["search"] = search
                else:
                    result["error"] = list_result.get("error", "Failed to list models")
                    result["error_type"] = list_result.get("error_type", "ListError")
            else:
                result["error"] = "Hugging Face kit not available"
                result["error_type"] = "DependencyError"
            
            # Update statistics
            self._update_stats(result)
            
        except Exception as e:
            self._handle_error(result, e)
            
        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    
    def ipfs_to_huggingface(self, cid: str, repo_id: str, path_in_repo: Optional[str] = None,
                          commit_message: Optional[str] = None, repo_type: str = "model",
                          pin: bool = True) -> Dict[str, Any]:
        """Get content from IPFS and upload to Hugging Face Hub.
        
        Args:
            cid: Content identifier in IPFS
            repo_id: Repository ID (username/repo-name)
            path_in_repo: Path within the repository (uses CID if not provided)
            commit_message: Commit message for the upload
            repo_type: Repository type (model, dataset, space)
            pin: Whether to pin the content in IPFS
            
        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("ipfs_to_huggingface")
        
        try:
            # Validate inputs
            if not cid:
                result["error"] = "CID is required"
                result["error_type"] = "ValidationError"
                return result
            
            if not repo_id:
                result["error"] = "Repository ID is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Use the CID as the path if not provided
            if not path_in_repo:
                path_in_repo = cid
            
            # Default commit message
            if not commit_message:
                commit_message = f"Upload content from IPFS (CID: {cid})"
            
            # Only continue if all dependencies are available
            if not self.hf_kit:
                result["error"] = "Hugging Face kit not available"
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
                
                # Upload to Hugging Face Hub
                upload_result = self.upload_file(
                    file_path=temp_path,
                    repo_id=repo_id,
                    path_in_repo=path_in_repo,
                    commit_message=commit_message,
                    repo_type=repo_type
                )
                
                # Clean up the temporary file
                os.unlink(temp_path)
                
                if not upload_result.get("success", False):
                    result["error"] = upload_result.get("error", "Failed to upload content to Hugging Face Hub")
                    result["error_type"] = upload_result.get("error_type", "HuggingFaceUploadError")
                    result["upload_result"] = upload_result
                    return result
                
                # Set success and copy relevant fields
                result["success"] = True
                result["ipfs_cid"] = cid
                result["repo_id"] = repo_id
                result["repo_type"] = repo_type
                result["path_in_repo"] = path_in_repo
                result["size_bytes"] = upload_result.get("size_bytes")
                
                # Include URLs if available
                if "url" in upload_result:
                    result["url"] = upload_result["url"]
                if "commit_url" in upload_result:
                    result["commit_url"] = upload_result["commit_url"]
            
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
    
    def huggingface_to_ipfs(self, repo_id: str, filename: str, pin: bool = True,
                           revision: Optional[str] = None, repo_type: str = "model") -> Dict[str, Any]:
        """Get content from Hugging Face Hub and add to IPFS.
        
        Args:
            repo_id: Repository ID (username/repo-name)
            filename: Filename to download
            pin: Whether to pin the content in IPFS
            revision: Optional Git revision (branch, tag, or commit hash)
            repo_type: Repository type (model, dataset, space)
            
        Returns:
            Result dictionary with operation status and details
        """
        start_time = time.time()
        result = self._create_result_dict("huggingface_to_ipfs")
        
        try:
            # Validate inputs
            if not repo_id:
                result["error"] = "Repository ID is required"
                result["error_type"] = "ValidationError"
                return result
            
            if not filename:
                result["error"] = "Filename is required"
                result["error_type"] = "ValidationError"
                return result
            
            # Only continue if all dependencies are available
            if not self.hf_kit:
                result["error"] = "Hugging Face kit not available"
                result["error_type"] = "DependencyError"
                return result
                
            if not self.ipfs_model:
                result["error"] = "IPFS model not available"
                result["error_type"] = "DependencyError"
                return result
            
            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                
                # Download content from Hugging Face Hub
                download_result = self.download_file(
                    repo_id=repo_id,
                    filename=filename,
                    destination=temp_path,
                    revision=revision,
                    repo_type=repo_type
                )
                
                if not download_result.get("success", False):
                    result["error"] = download_result.get("error", "Failed to download content from Hugging Face Hub")
                    result["error_type"] = download_result.get("error_type", "HuggingFaceDownloadError")
                    result["download_result"] = download_result
                    os.unlink(temp_path)
                    return result
                
                # Get file size for statistics
                file_size = os.path.getsize(temp_path)
                
                # Read the file content
                with open(temp_path, "rb") as f:
                    content = f.read()
                
                # Add to IPFS
                ipfs_result = self.ipfs_model.add_content(content, filename=filename)
                
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
                result["repo_id"] = repo_id
                result["repo_type"] = repo_type
                result["filename"] = filename
                result["ipfs_cid"] = cid
                result["size_bytes"] = file_size
                
                if revision:
                    result["revision"] = revision
            
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