"""
HuggingFace backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for HuggingFace,
allowing the Unified Storage Manager to interact with HuggingFace repositories.
"""

import logging
import time
import os
import tempfile
import json
from typing import Dict, List, Any, Optional, Union, BinaryIO

from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class HuggingFaceBackend(BackendStorage):
    """HuggingFace backend implementation."""
    
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize HuggingFace backend."""
        super().__init__(StorageBackendType.HUGGINGFACE, resources, metadata)
        
        # Import dependencies
        try:
            from ipfs_kit_py.huggingface_kit import huggingface_kit
            self.huggingface = huggingface_kit(resources, metadata)
            logger.info("Initialized HuggingFace backend")
        except ImportError as e:
            logger.error(f"Failed to initialize HuggingFace backend: {e}")
            raise ImportError(f"Failed to import huggingface_kit: {e}")
        
        # Configuration
        self.default_repo = metadata.get("default_repo")
        self.default_branch = metadata.get("default_branch", "main")
        self.space_mode = metadata.get("space_mode", False)  # True for using Spaces instead of regular repos
        
    def store(
        self, 
        data: Union[bytes, BinaryIO, str],
        container: Optional[str] = None,
        path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store data in HuggingFace.
        
        Args:
            data: Data to store (bytes, file-like object, or string)
            container: Repository name (overrides default_repo)
            path: Path within repository
            options: Additional options for storage
            
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        
        # Get repository name
        repo_name = container or self.default_repo
        if not repo_name:
            return {
                "success": False,
                "error": "No HuggingFace repository specified",
                "backend": self.get_name()
            }
        
        # Get path within repository
        if not path:
            # Generate a default path if none provided
            path = f"content/{int(time.time())}"
            # Add extension based on content type if available
            content_type = options.get("content_type") or options.get("metadata", {}).get("content_type")
            if content_type:
                if content_type.startswith("text/"):
                    path += ".txt"
                elif content_type.startswith("image/"):
                    ext = content_type.split("/")[1]
                    path += f".{ext}"
                elif content_type == "application/json":
                    path += ".json"
                elif content_type == "application/pdf":
                    path += ".pdf"
        
        # Get branch name
        branch = options.get("branch", self.default_branch)
        
        # Get commit message
        commit_message = options.get("commit_message", f"Upload {path}")
        
        # Use temporary file for upload
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                temp_file = tmp.name
                
                if isinstance(data, str):
                    # If data is a string, encode to bytes first
                    tmp.write(data.encode('utf-8'))
                elif isinstance(data, bytes):
                    # Write bytes to temporary file
                    tmp.write(data)
                else:
                    # Write file-like object to temporary file
                    data.seek(0)
                    while True:
                        chunk = data.read(8192)
                        if not chunk:
                            break
                        tmp.write(chunk)
                    data.seek(0)  # Reset file pointer
            
            # Upload to HuggingFace
            if self.space_mode:
                # For Spaces mode
                result = self.huggingface.upload_to_space(
                    space_name=repo_name,
                    file_path=temp_file,
                    path_in_space=path,
                    commit_message=commit_message
                )
            else:
                # For regular repos
                result = self.huggingface.upload_file(
                    repo_name=repo_name,
                    file_path=temp_file,
                    path_in_repo=path,
                    branch=branch,
                    commit_message=commit_message
                )
            
            if result.get("success", False):
                # Extract identifier information
                identifier = result.get("url") or f"{repo_name}/{path}"
                
                # Add MCP metadata if supported
                if options.get("add_metadata", True):
                    metadata = {
                        "mcp_added": time.time(),
                        "mcp_backend": self.get_name()
                    }
                    # Note: HuggingFace doesn't natively support custom metadata,
                    # but we could potentially store it in a separate metadata file
                    # This would be a future enhancement
                
                return {
                    "success": True,
                    "identifier": identifier,
                    "repo_name": repo_name,
                    "path": path,
                    "branch": branch,
                    "url": result.get("url"),
                    "backend": self.get_name(),
                    "details": result
                }
            
            return {
                "success": False,
                "error": result.get("error", "Failed to store data in HuggingFace"),
                "backend": self.get_name(),
                "details": result
            }
            
        except Exception as e:
            logger.exception(f"Error storing data in HuggingFace: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")
        
    def retrieve(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve data from HuggingFace.
        
        Args:
            identifier: Path or URL to the content
            container: Repository name (optional if included in identifier)
            options: Additional options for retrieval
            
        Returns:
            Dictionary with operation result and data
        """
        options = options or {}
        
        # Parse identifier and container
        repo_name, path, branch = self._parse_identifier(identifier, container, options)
        
        if not repo_name:
            return {
                "success": False,
                "error": "No HuggingFace repository specified",
                "backend": self.get_name()
            }
        
        # Use temporary file for download
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                temp_file = tmp.name
            
            # Download from HuggingFace
            if self.space_mode:
                # For Spaces mode
                result = self.huggingface.download_from_space(
                    space_name=repo_name,
                    path_in_space=path,
                    output_path=temp_file
                )
            else:
                # For regular repos
                result = self.huggingface.download_file(
                    repo_name=repo_name,
                    path_in_repo=path,
                    output_path=temp_file,
                    branch=branch
                )
            
            if result.get("success", False):
                # Read the data
                with open(temp_file, 'rb') as f:
                    data = f.read()
                    
                return {
                    "success": True,
                    "data": data,
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "repo_name": repo_name,
                    "path": path,
                    "branch": branch,
                    "details": result
                }
            
            return {
                "success": False,
                "error": result.get("error", "Failed to retrieve data from HuggingFace"),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result
            }
            
        except Exception as e:
            logger.exception(f"Error retrieving data from HuggingFace: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "identifier": identifier
            }
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")
        
    def delete(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Delete data from HuggingFace.
        
        Args:
            identifier: Path or URL to delete
            container: Repository name (optional if included in identifier)
            options: Additional options for deletion
            
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        
        # Parse identifier and container
        repo_name, path, branch = self._parse_identifier(identifier, container, options)
        
        if not repo_name:
            return {
                "success": False,
                "error": "No HuggingFace repository specified",
                "backend": self.get_name()
            }
        
        # Get commit message
        commit_message = options.get("commit_message", f"Delete {path}")
        
        try:
            # Delete from HuggingFace
            if self.space_mode:
                # For Spaces mode
                result = self.huggingface.delete_from_space(
                    space_name=repo_name,
                    path_in_space=path,
                    commit_message=commit_message
                )
            else:
                # For regular repos
                result = self.huggingface.delete_file(
                    repo_name=repo_name,
                    path_in_repo=path,
                    branch=branch,
                    commit_message=commit_message
                )
            
            return {
                "success": result.get("success", False),
                "backend": self.get_name(),
                "identifier": identifier,
                "repo_name": repo_name,
                "path": path,
                "branch": branch,
                "details": result
            }
            
        except Exception as e:
            logger.exception(f"Error deleting data from HuggingFace: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "identifier": identifier
            }
        
    def list(
        self,
        container: Optional[str] = None,
        prefix: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        List items in HuggingFace repository.
        
        Args:
            container: Repository name
            prefix: Path prefix to filter by
            options: Additional listing options
            
        Returns:
            Dictionary with operation result and items
        """
        options = options or {}
        
        # Get repository name
        repo_name = container or self.default_repo
        if not repo_name:
            return {
                "success": False,
                "error": "No HuggingFace repository specified",
                "backend": self.get_name()
            }
        
        # Get branch name
        branch = options.get("branch", self.default_branch)
        
        try:
            # List files from HuggingFace
            if self.space_mode:
                # For Spaces mode
                result = self.huggingface.list_space_files(
                    space_name=repo_name,
                    path=prefix or ""
                )
            else:
                # For regular repos
                result = self.huggingface.list_repo_files(
                    repo_name=repo_name,
                    path=prefix or "",
                    branch=branch
                )
            
            if result.get("success", False):
                items = []
                
                # Extract file information
                for file_info in result.get("files", []):
                    # Skip directories if specified
                    if options.get("skip_directories", False) and file_info.get("type") == "directory":
                        continue
                        
                    # Create file item
                    items.append({
                        "identifier": f"{repo_name}/{file_info.get('path')}",
                        "repo_name": repo_name,
                        "path": file_info.get("path"),
                        "type": file_info.get("type"),
                        "size": file_info.get("size", 0),
                        "last_modified": file_info.get("last_modified"),
                        "url": file_info.get("url"),
                        "backend": self.get_name()
                    })
                
                return {
                    "success": True,
                    "items": items,
                    "backend": self.get_name(),
                    "repo_name": repo_name,
                    "details": result
                }
            
            return {
                "success": False,
                "error": result.get("error", "Failed to list files in HuggingFace"),
                "backend": self.get_name(),
                "details": result
            }
            
        except Exception as e:
            logger.exception(f"Error listing files in HuggingFace: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }
        
    def exists(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if content exists in HuggingFace.
        
        Args:
            identifier: Path or URL to check
            container: Repository name (optional if included in identifier)
            options: Additional options
            
        Returns:
            True if content exists
        """
        options = options or {}
        
        # Parse identifier and container
        repo_name, path, branch = self._parse_identifier(identifier, container, options)
        
        if not repo_name:
            return False
        
        try:
            # Check if file exists
            if self.space_mode:
                # For Spaces mode
                result = self.huggingface.check_file_in_space(
                    space_name=repo_name,
                    path_in_space=path
                )
            else:
                # For regular repos
                result = self.huggingface.check_file_exists(
                    repo_name=repo_name,
                    path_in_repo=path,
                    branch=branch
                )
            
            return result.get("success", False) and result.get("exists", False)
            
        except Exception as e:
            logger.exception(f"Error checking if file exists in HuggingFace: {e}")
            return False
        
    def get_metadata(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for HuggingFace content.
        
        Args:
            identifier: Path or URL to get metadata for
            container: Repository name (optional if included in identifier)
            options: Additional options
            
        Returns:
            Dictionary with metadata information
        """
        options = options or {}
        
        # Parse identifier and container
        repo_name, path, branch = self._parse_identifier(identifier, container, options)
        
        if not repo_name:
            return {
                "success": False,
                "error": "No HuggingFace repository specified",
                "backend": self.get_name()
            }
        
        try:
            # Get file metadata
            if self.space_mode:
                # For Spaces mode
                result = self.huggingface.get_space_file_info(
                    space_name=repo_name,
                    path_in_space=path
                )
            else:
                # For regular repos
                result = self.huggingface.get_file_info(
                    repo_name=repo_name,
                    path_in_repo=path,
                    branch=branch
                )
            
            if result.get("success", False):
                # Extract metadata
                file_info = result.get("file_info", {})
                
                metadata = {
                    "size": file_info.get("size", 0),
                    "last_modified": file_info.get("last_modified"),
                    "path": file_info.get("path"),
                    "type": file_info.get("type"),
                    "url": file_info.get("url"),
                    "backend": self.get_name()
                }
                
                # Try to get additional metadata if available
                try:
                    # Look for a metadata file with the same name but .json extension
                    metadata_path = f"{path}.metadata.json"
                    metadata_result = None
                    
                    if self.space_mode:
                        metadata_result = self.huggingface.download_from_space(
                            space_name=repo_name,
                            path_in_space=metadata_path,
                            output_path=None  # Get raw content
                        )
                    else:
                        metadata_result = self.huggingface.download_file(
                            repo_name=repo_name,
                            path_in_repo=metadata_path,
                            output_path=None,  # Get raw content
                            branch=branch
                        )
                    
                    if metadata_result.get("success", False) and metadata_result.get("content"):
                        # Parse the JSON metadata
                        custom_metadata = json.loads(metadata_result.get("content"))
                        metadata.update(custom_metadata)
                except Exception as e:
                    # Metadata file might not exist, which is fine
                    pass
                
                return {
                    "success": True,
                    "metadata": metadata,
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "repo_name": repo_name,
                    "path": path,
                    "details": result
                }
            
            return {
                "success": False,
                "error": result.get("error", "Failed to get metadata from HuggingFace"),
                "backend": self.get_name(),
                "identifier": identifier,
                "details": result
            }
            
        except Exception as e:
            logger.exception(f"Error getting metadata from HuggingFace: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "identifier": identifier
            }
        
    def update_metadata(
        self,
        identifier: str,
        metadata: Dict[str, Any],
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update metadata for HuggingFace content.
        
        Note: HuggingFace doesn't natively support metadata, so this implementation
        creates a separate metadata file alongside the content.
        
        Args:
            identifier: Path or URL to update metadata for
            metadata: New metadata to set
            container: Repository name (optional if included in identifier)
            options: Additional options
            
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        
        # Parse identifier and container
        repo_name, path, branch = self._parse_identifier(identifier, container, options)
        
        if not repo_name:
            return {
                "success": False,
                "error": "No HuggingFace repository specified",
                "backend": self.get_name()
            }
        
        # Get commit message
        commit_message = options.get("commit_message", f"Update metadata for {path}")
        
        try:
            # Create metadata file path
            metadata_path = f"{path}.metadata.json"
            
            # Create temporary file with metadata
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                temp_file = tmp.name
                json.dump(metadata, tmp, indent=2)
            
            try:
                # Upload metadata file
                if self.space_mode:
                    # For Spaces mode
                    result = self.huggingface.upload_to_space(
                        space_name=repo_name,
                        file_path=temp_file,
                        path_in_space=metadata_path,
                        commit_message=commit_message
                    )
                else:
                    # For regular repos
                    result = self.huggingface.upload_file(
                        repo_name=repo_name,
                        file_path=temp_file,
                        path_in_repo=metadata_path,
                        branch=branch,
                        commit_message=commit_message
                    )
                
                return {
                    "success": result.get("success", False),
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "repo_name": repo_name,
                    "path": path,
                    "metadata_path": metadata_path,
                    "details": result
                }
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            
        except Exception as e:
            logger.exception(f"Error updating metadata in HuggingFace: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "identifier": identifier
            }
    
    def _parse_identifier(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str, str]:
        """
        Parse identifier into repository name, path, and branch.
        
        Args:
            identifier: Path or URL identifier
            container: Repository name (optional)
            options: Additional options
            
        Returns:
            Tuple of (repo_name, path, branch)
        """
        options = options or {}
        
        # Initialize with defaults
        repo_name = container or self.default_repo
        path = identifier
        branch = options.get("branch", self.default_branch)
        
        # Check if identifier includes repository name
        if identifier.startswith("huggingface:"):
            # Format: huggingface:repo_name/path
            parts = identifier[12:].split("/", 1)
            if len(parts) > 0:
                repo_name = parts[0]
            if len(parts) > 1:
                path = parts[1]
        elif identifier.startswith("hf:"):
            # Format: hf:repo_name/path
            parts = identifier[3:].split("/", 1)
            if len(parts) > 0:
                repo_name = parts[0]
            if len(parts) > 1:
                path = parts[1]
        elif "/" in identifier and not container:
            # Format: repo_name/path
            parts = identifier.split("/", 1)
            repo_name = parts[0]
            if len(parts) > 1:
                path = parts[1]
                
        # Extract branch if included in path (path@branch)
        if "@" in path and not options.get("branch"):
            path_parts = path.split("@", 1)
            path = path_parts[0]
            branch = path_parts[1]
        
        return repo_name, path, branch