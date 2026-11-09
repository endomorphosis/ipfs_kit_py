"""
HuggingFace backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for HuggingFace Hub,
providing access to models, datasets, and other assets from the HuggingFace ecosystem.
"""

import logging
import time
import os
import json
import tempfile
import shutil
import uuid
import threading
from typing import Dict, Any, Optional, Union, BinaryIO, List, Tuple
from urllib.parse import urljoin

# Import the base class and storage types
from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)

# Define constants
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_RETRIES = 3
DEFAULT_CACHE_DIR = None  # Will be set to a temp directory if not provided


class HuggingFaceBackend(BackendStorage):
    """HuggingFace Hub backend implementation for the unified storage manager."""
    
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize HuggingFace backend.
        
        Args:
            resources: Connection resources including API tokens
            metadata: Additional configuration metadata
        """
        super().__init__(StorageBackendType.HUGGINGFACE, resources, metadata)
        
        # Try importing huggingface_hub
        try:
            import huggingface_hub
            self.huggingface_hub = huggingface_hub
            logger.info("Successfully imported huggingface_hub")
        except ImportError:
            logger.error("huggingface_hub package is required. Please install with 'pip install huggingface_hub'")
            raise ImportError("huggingface_hub is required for HuggingFace backend")
        
        # Extract configuration from resources/metadata
        self.api_token = resources.get("api_token") or os.environ.get("HUGGINGFACE_TOKEN")
        self.timeout = int(resources.get("timeout", DEFAULT_TIMEOUT))
        self.max_retries = int(resources.get("max_retries", DEFAULT_MAX_RETRIES))
        self.default_repo = resources.get("default_repo")
        
        # Set up caching
        self.cache_dir = resources.get("cache_dir", DEFAULT_CACHE_DIR)
        if not self.cache_dir:
            self.cache_dir = os.path.join(
                tempfile.gettempdir(), f"mcp_huggingface_cache_{uuid.uuid4().hex[:8]}"
            )
            os.makedirs(self.cache_dir, exist_ok=True)
            logger.info(f"Created HuggingFace cache directory: {self.cache_dir}")
        
        # Initialize huggingface_hub client and API
        self._init_client()
        
        # Set up lock for thread safety
        self.lock = threading.RLock()
        
        # Internal tracking for caching
        self._cache_registry = {}
    
    def _init_client(self):
        """Initialize the HuggingFace Hub client."""
        # Create HuggingFace API client
        self.api = self.huggingface_hub.HfApi(token=self.api_token)
        logger.info("HuggingFace Hub API client initialized")
        
        # Test connection
        try:
            whoami = self.api.whoami()
            self.username = whoami.get("name", "anonymous")
            logger.info(f"Successfully connected to HuggingFace Hub as {self.username}")
        except Exception as e:
            if not self.api_token:
                logger.warning("No API token provided, operating in read-only mode")
                self.username = "anonymous"
            else:
                logger.error(f"Failed to authenticate with HuggingFace Hub: {e}")
                self.username = "unknown"
    
    def get_name(self) -> str:
        """Get the name of this backend implementation.
        
        Returns:
            String representation of the backend name
        """
        return "huggingface"

    def add_content(self, content: Union[str, bytes, BinaryIO], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add content to HuggingFace Hub.
        
        Args:
            content: Content to add (file path, bytes, or file-like object)
            metadata: Metadata for the content
            
        Returns:
            Dict with operation result
        """
        repo_id = metadata.get("repo_id", self.default_repo) if metadata else self.default_repo
        if not repo_id:
            return {
                "success": False,
                "error": "No repository specified, and no default repository configured",
                "error_type": "ConfigurationError",
                "backend": self.backend_type.value
            }
        
        # Get path information
        path = metadata.get("path", None) if metadata else None
        if not path:
            # Generate a unique path if none provided
            file_ext = ".bin"
            if isinstance(content, str) and os.path.isfile(content):
                _, file_ext = os.path.splitext(content)
            path = f"mcp_upload_{int(time.time())}_{uuid.uuid4().hex[:8]}{file_ext}"
        
        # Get branch/revision information
        repo_type = metadata.get("repo_type", "dataset") if metadata else "dataset"
        branch = metadata.get("branch", "main") if metadata else "main"
        commit_message = metadata.get("commit_message", f"Upload via MCP at {time.time()}") if metadata else None
        
        # Prepare content for upload
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                if isinstance(content, str) and os.path.isfile(content):
                    # If content is a file path, copy the file
                    shutil.copyfile(content, temp_file.name)
                    temp_path = temp_file.name
                elif isinstance(content, (bytes, bytearray)):
                    # If content is bytes, write directly
                    temp_file.write(content)
                    temp_path = temp_file.name
                elif hasattr(content, 'read'):
                    # If content is a file-like object, read and write
                    shutil.copyfileobj(content, temp_file)
                    temp_path = temp_file.name
                else:
                    # Unsupported content type
                    os.unlink(temp_file.name)
                    return {
                        "success": False,
                        "error": f"Unsupported content type: {type(content)}",
                        "error_type": "InvalidContentType",
                        "backend": self.backend_type.value
                    }
            
            # Upload file
            response = self.api.upload_file(
                path_or_fileobj=temp_path,
                path_in_repo=path,
                repo_id=repo_id,
                repo_type=repo_type,
                revision=branch,
                commit_message=commit_message
            )
            
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            
            # Generate a unique identifier that includes repo, path, and revision
            identifier = f"{repo_id}/{path}"
            if branch != "main":
                identifier = f"{identifier}@{branch}"
            
            # Process response
            return {
                "success": True,
                "identifier": identifier,
                "backend": self.backend_type.value,
                "details": {
                    "repo_id": repo_id,
                    "path": path,
                    "branch": branch,
                    "repo_type": repo_type,
                    "url": response
                }
            }
        
        except Exception as e:
            # Clean up temporary file if it exists
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            
            logger.error(f"Error uploading to HuggingFace Hub: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "HuggingFaceUploadError",
                "backend": self.backend_type.value
            }

    def get_content(self, content_id: str) -> Dict[str, Any]:
        """Retrieve content from HuggingFace Hub.
        
        Args:
            content_id: Content identifier (repo_id/path[@revision])
            
        Returns:
            Dict with operation result including content data
        """
        try:
            # Parse content_id to extract repo_id, path, and revision
            repo_id, path, revision = self._parse_content_id(content_id)
            
            # Check cache first
            cache_key = f"{repo_id}/{path}@{revision}"
            cached_path = self._get_from_cache(cache_key)
            
            if cached_path and os.path.isfile(cached_path):
                # Read from cache
                with open(cached_path, 'rb') as f:
                    data = f.read()
                
                return {
                    "success": True,
                    "data": data,
                    "backend": self.backend_type.value,
                    "identifier": content_id,
                    "cached": True,
                    "details": {
                        "repo_id": repo_id,
                        "path": path,
                        "revision": revision,
                        "cache_path": cached_path
                    }
                }
            
            # Download from HuggingFace Hub
            local_path = self.huggingface_hub.hf_hub_download(
                repo_id=repo_id,
                filename=path,
                revision=revision,
                cache_dir=self.cache_dir,
                token=self.api_token,
                local_files_only=False
            )
            
            # Read the downloaded file
            with open(local_path, 'rb') as f:
                data = f.read()
            
            # Add to cache
            self._add_to_cache(cache_key, local_path)
            
            return {
                "success": True,
                "data": data,
                "backend": self.backend_type.value,
                "identifier": content_id,
                "details": {
                    "repo_id": repo_id,
                    "path": path,
                    "revision": revision,
                    "local_path": local_path
                }
            }
        
        except self.huggingface_hub.utils.RepositoryNotFoundError:
            return {
                "success": False,
                "error": f"Repository not found: {repo_id}",
                "error_type": "RepositoryNotFound",
                "backend": self.backend_type.value
            }
        
        except self.huggingface_hub.utils.EntryNotFoundError:
            return {
                "success": False,
                "error": f"File not found: {path} in {repo_id}@{revision}",
                "error_type": "EntryNotFound",
                "backend": self.backend_type.value
            }
        
        except self.huggingface_hub.utils.RevisionNotFoundError:
            return {
                "success": False,
                "error": f"Revision not found: {revision} in {repo_id}",
                "error_type": "RevisionNotFound",
                "backend": self.backend_type.value
            }
        
        except Exception as e:
            logger.error(f"Error retrieving content from HuggingFace Hub: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "HuggingFaceDownloadError",
                "backend": self.backend_type.value
            }

    def remove_content(self, content_id: str) -> Dict[str, Any]:
        """Remove content from HuggingFace Hub.
        
        Args:
            content_id: Content identifier (repo_id/path[@revision])
            
        Returns:
            Dict with operation result
        """
        try:
            # Parse content_id to extract repo_id, path, and revision
            repo_id, path, revision = self._parse_content_id(content_id)
            
            # Check permissions
            if not self.api_token:
                return {
                    "success": False,
                    "error": "API token required for deletion operations",
                    "error_type": "AuthenticationError",
                    "backend": self.backend_type.value
                }
            
            # Delete file
            commit_url = self.api.delete_file(
                path_in_repo=path,
                repo_id=repo_id,
                revision=revision,
                commit_message=f"Delete {path} via MCP at {time.time()}"
            )
            
            # Remove from cache if present
            cache_key = f"{repo_id}/{path}@{revision}"
            self._remove_from_cache(cache_key)
            
            return {
                "success": True,
                "backend": self.backend_type.value,
                "identifier": content_id,
                "details": {
                    "repo_id": repo_id,
                    "path": path,
                    "revision": revision,
                    "commit_url": commit_url
                }
            }
        
        except self.huggingface_hub.utils.RepositoryNotFoundError:
            return {
                "success": False,
                "error": f"Repository not found: {repo_id}",
                "error_type": "RepositoryNotFound",
                "backend": self.backend_type.value
            }
        
        except self.huggingface_hub.utils.EntryNotFoundError:
            return {
                "success": False,
                "error": f"File not found: {path} in {repo_id}@{revision}",
                "error_type": "EntryNotFound",
                "backend": self.backend_type.value
            }
        
        except Exception as e:
            logger.error(f"Error deleting content from HuggingFace Hub: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "HuggingFaceDeleteError",
                "backend": self.backend_type.value
            }

    def get_metadata(self, content_id: str) -> Dict[str, Any]:
        """Get metadata for content from HuggingFace Hub.
        
        Args:
            content_id: Content identifier (repo_id/path[@revision])
            
        Returns:
            Dict with operation result including metadata
        """
        try:
            # Parse content_id to extract repo_id, path, and revision
            repo_id, path, revision = self._parse_content_id(content_id)
            
            # Get file metadata
            try:
                file_info = self.api.model_info(
                    repo_id=repo_id,
                    revision=revision
                )
                
                # Find the specific file in siblings
                file_metadata = None
                for sibling in file_info.siblings:
                    if sibling.rfilename == path:
                        file_metadata = {
                            "size": sibling.size,
                            "lfs": sibling.lfs,
                            "blob_id": sibling.blob_id,
                            "last_modified": sibling.lastModified
                        }
                        break
                
                if not file_metadata:
                    # File exists but no detailed metadata found
                    # Try to get basic info using api.repo_info
                    repo_info = self.api.repo_info(
                        repo_id=repo_id,
                        revision=revision
                    )
                    
                    file_metadata = {
                        "last_modified": repo_info.lastModified,
                        "exists": True,
                        "limited_info": True
                    }
                
                # Add repository metadata
                metadata = {
                    **file_metadata,
                    "repo_id": repo_id,
                    "path": path,
                    "revision": revision,
                    "backend": self.backend_type.value
                }
                
                # Get repository info for additional metadata
                repo_metadata = {
                    "author": file_info.author,
                    "tags": file_info.tags,
                    "downloads": file_info.downloads,
                    "likes": file_info.likes,
                    "private": file_info.private
                }
                
                return {
                    "success": True,
                    "metadata": metadata,
                    "backend": self.backend_type.value,
                    "identifier": content_id,
                    "details": {
                        "repo_metadata": repo_metadata
                    }
                }
            
            except self.huggingface_hub.utils.EntryNotFoundError:
                # If file-specific info fails, try to get just repo info
                repo_info = self.api.repo_info(
                    repo_id=repo_id,
                    revision=revision
                )
                
                metadata = {
                    "repo_id": repo_id,
                    "path": path,
                    "revision": revision,
                    "file_exists": False,
                    "repo_exists": True,
                    "last_modified": repo_info.lastModified,
                    "backend": self.backend_type.value
                }
                
                return {
                    "success": True,
                    "metadata": metadata,
                    "backend": self.backend_type.value,
                    "identifier": content_id,
                    "details": {
                        "repo_info": {
                            "author": repo_info.author,
                            "tags": repo_info.tags,
                            "private": repo_info.private
                        }
                    }
                }
        
        except self.huggingface_hub.utils.RepositoryNotFoundError:
            return {
                "success": False,
                "error": f"Repository not found: {repo_id}",
                "error_type": "RepositoryNotFound",
                "backend": self.backend_type.value
            }
        
        except self.huggingface_hub.utils.RevisionNotFoundError:
            return {
                "success": False,
                "error": f"Revision not found: {revision} in {repo_id}",
                "error_type": "RevisionNotFound",
                "backend": self.backend_type.value
            }
        
        except Exception as e:
            logger.error(f"Error retrieving metadata from HuggingFace Hub: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "HuggingFaceMetadataError",
                "backend": self.backend_type.value
            }

    def update_metadata(self, identifier: str, metadata: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Update metadata for content on HuggingFace Hub.
        
        Args:
            identifier: Content identifier (repo_id/path[@revision])
            metadata: Metadata to update
            **kwargs: Additional options
            
        Returns:
            Dict with operation result
        """
        try:
            # Parse content_id to extract repo_id, path, and revision
            repo_id, path, revision = self._parse_content_id(identifier)
            
            # Check permissions
            if not self.api_token:
                return {
                    "success": False,
                    "error": "API token required for metadata update operations",
                    "error_type": "AuthenticationError",
                    "backend": self.backend_type.value
                }
            
            # HuggingFace Hub doesn't support direct metadata updates for files
            # We can only update repository-level metadata
            if "repo_metadata" in metadata:
                repo_metadata = metadata["repo_metadata"]
                
                # Extract relevant fields
                tags = repo_metadata.get("tags")
                description = repo_metadata.get("description")
                
                # Update repository metadata
                if tags or description:
                    self.api.update_repo_visibility(
                        repo_id=repo_id,
                        private=repo_metadata.get("private", None)
                    )
                    
                    # Update other metadata if provided
                    if tags:
                        model_info = self.api.model_info(repo_id=repo_id)
                        current_tags = model_info.tags
                        
                        # Add new tags
                        for tag in tags:
                            if tag not in current_tags:
                                self.api.add_tag(repo_id=repo_id, tag=tag)
                    
                    return {
                        "success": True,
                        "backend": self.backend_type.value,
                        "identifier": identifier,
                        "details": {
                            "repo_id": repo_id,
                            "updated_fields": list(repo_metadata.keys())
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": "No valid repository metadata fields to update",
                        "error_type": "InvalidMetadata",
                        "backend": self.backend_type.value
                    }
            else:
                return {
                    "success": False,
                    "error": "HuggingFace Hub doesn't support file-level metadata updates",
                    "error_type": "UnsupportedOperation",
                    "backend": self.backend_type.value,
                    "details": {
                        "message": "Use 'repo_metadata' field to update repository-level metadata"
                    }
                }
        
        except self.huggingface_hub.utils.RepositoryNotFoundError:
            return {
                "success": False,
                "error": f"Repository not found: {repo_id}",
                "error_type": "RepositoryNotFound",
                "backend": self.backend_type.value
            }
        
        except Exception as e:
            logger.error(f"Error updating metadata on HuggingFace Hub: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "HuggingFaceUpdateError",
                "backend": self.backend_type.value
            }

    def list(self, prefix: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """List content from HuggingFace Hub.
        
        Args:
            prefix: Optional repository prefix to filter
            **kwargs: Additional options
            
        Returns:
            Dict with operation result including list of items
        """
        try:
            # Extract options
            limit = kwargs.get("limit", 100)
            offset = kwargs.get("offset", 0)
            
            # If a specific repository is provided
            if prefix and '/' in prefix:
                # Assume format is repo_id/path_prefix
                parts = prefix.split('/', 1)
                repo_id = parts[0]
                path_prefix = parts[1] if len(parts) > 1 else ""
                
                # Get files in repository
                revision = kwargs.get("revision", "main")
                
                try:
                    files = self.api.list_repo_files(
                        repo_id=repo_id,
                        revision=revision
                    )
                    
                    # Filter by path prefix if provided
                    if path_prefix:
                        files = [f for f in files if f.startswith(path_prefix)]
                    
                    # Apply pagination
                    files = files[offset:offset+limit]
                    
                    # Format items
                    items = [
                        {
                            "identifier": f"{repo_id}/{f}{'@'+revision if revision != 'main' else ''}",
                            "path": f,
                            "repo_id": repo_id,
                            "revision": revision,
                            "backend": self.backend_type.value
                        }
                        for f in files
                    ]
                    
                    return {
                        "success": True,
                        "items": items,
                        "count": len(items),
                        "backend": self.backend_type.value,
                        "details": {
                            "repo_id": repo_id,
                            "revision": revision,
                            "total_files": len(files)
                        }
                    }
                
                except (self.huggingface_hub.utils.RepositoryNotFoundError, self.huggingface_hub.utils.RevisionNotFoundError):
                    return {
                        "success": False,
                        "error": f"Repository or revision not found: {repo_id}@{revision}",
                        "error_type": "RepositoryNotFound",
                        "backend": self.backend_type.value
                    }
            
            else:
                # List repositories
                repo_type = kwargs.get("repo_type", "model")
                author = kwargs.get("author", None)
                
                # Determine if we have a prefix
                search_query = None
                if prefix:
                    search_query = prefix
                
                # Get repositories
                models = self.api.list_models(
                    filter=author,
                    search=search_query,
                    limit=limit,
                    offset=offset
                ) if repo_type in ["model", "all"] else []
                
                datasets = self.api.list_datasets(
                    filter=author,
                    search=search_query,
                    limit=limit,
                    offset=offset
                ) if repo_type in ["dataset", "all"] else []
                
                # Format items
                items = []
                
                for model in models:
                    items.append({
                        "identifier": model.id,
                        "name": model.id.split('/')[-1],
                        "repo_id": model.id,
                        "author": model.id.split('/')[0] if '/' in model.id else None,
                        "type": "model",
                        "last_modified": model.lastModified,
                        "backend": self.backend_type.value
                    })
                
                for dataset in datasets:
                    items.append({
                        "identifier": dataset.id,
                        "name": dataset.id.split('/')[-1],
                        "repo_id": dataset.id,
                        "author": dataset.id.split('/')[0] if '/' in dataset.id else None,
                        "type": "dataset",
                        "last_modified": dataset.lastModified,
                        "backend": self.backend_type.value
                    })
                
                return {
                    "success": True,
                    "items": items,
                    "count": len(items),
                    "backend": self.backend_type.value,
                    "details": {
                        "repo_type": repo_type,
                        "author": author,
                        "search_query": search_query
                    }
                }
        
        except Exception as e:
            logger.error(f"Error listing content from HuggingFace Hub: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "HuggingFaceListError",
                "backend": self.backend_type.value
            }

    def exists(self, identifier: str, **kwargs) -> bool:
        """Check if content exists on HuggingFace Hub.
        
        Args:
            identifier: Content identifier (repo_id/path[@revision])
            **kwargs: Additional options
            
        Returns:
            True if content exists, False otherwise
        """
        try:
            # Parse content_id to extract repo_id, path, and revision
            repo_id, path, revision = self._parse_content_id(identifier)
            
            # Check if file exists
            try:
                # Try to get hf_hub_url which will throw if the file doesn't exist
                self.huggingface_hub.hf_hub_url(
                    repo_id=repo_id,
                    filename=path,
                    revision=revision
                )
                return True
            except self.huggingface_hub.utils.EntryNotFoundError:
                return False
        
        except (self.huggingface_hub.utils.RepositoryNotFoundError, self.huggingface_hub.utils.RevisionNotFoundError):
            return False
        
        except Exception as e:
            logger.error(f"Error checking if content exists on HuggingFace Hub: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get the status of the HuggingFace backend.
        
        Returns:
            Dict with status information
        """
        try:
            # Check connection to HuggingFace Hub
            try:
                whoami = self.api.whoami()
                username = whoami.get("name", "anonymous")
                connection_status = "connected"
            except Exception as e:
                if not self.api_token:
                    connection_status = "connected_readonly"
                    username = "anonymous"
                else:
                    connection_status = f"error: {str(e)}"
                    username = "unknown"
            
            # Get cache information
            cache_size = 0
            cache_files = 0
            
            if os.path.exists(self.cache_dir):
                for dirpath, dirnames, filenames in os.walk(self.cache_dir):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        cache_size += os.path.getsize(fp)
                        cache_files += 1
            
            return {
                "success": True,
                "backend": self.backend_type.value,
                "available": connection_status in ["connected", "connected_readonly"],
                "status": {
                    "connection": connection_status,
                    "username": username,
                    "authenticated": bool(self.api_token),
                    "readonly": not bool(self.api_token),
                    "default_repo": self.default_repo,
                    "cache": {
                        "directory": self.cache_dir,
                        "files": cache_files,
                        "size_bytes": cache_size,
                        "size_human": f"{cache_size / (1024*1024):.2f} MB"
                    }
                }
            }
        
        except Exception as e:
            logger.error(f"Error getting HuggingFace backend status: {e}")
            return {
                "success": False,
                "backend": self.backend_type.value,
                "available": False,
                "error": str(e)
            }

    def _parse_content_id(self, content_id: str) -> Tuple[str, str, str]:
        """Parse a content ID into repository ID, path, and revision.
        
        Args:
            content_id: Content identifier (repo_id/path[@revision])
            
        Returns:
            Tuple of (repo_id, path, revision)
        """
        # Check if revision is specified
        revision = "main"
        if "@" in content_id:
            content_parts, revision = content_id.rsplit("@", 1)
        else:
            content_parts = content_id
        
        # Split into repo_id and path
        if "/" in content_parts:
            repo_id, path = content_parts.split("/", 1)
        else:
            # If no path specified, assume it's just a repo_id
            repo_id = content_parts
            path = ""
        
        return repo_id, path, revision

    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """Get a file path from the cache if it exists.
        
        Args:
            cache_key: Cache key to look up
            
        Returns:
            Path to cached file or None if not found
        """
        with self.lock:
            return self._cache_registry.get(cache_key)

    def _add_to_cache(self, cache_key: str, file_path: str) -> None:
        """Add a file to the cache.
        
        Args:
            cache_key: Cache key
            file_path: Path to the file
        """
        with self.lock:
            self._cache_registry[cache_key] = file_path

    def _remove_from_cache(self, cache_key: str) -> None:
        """Remove a file from the cache.
        
        Args:
            cache_key: Cache key to remove
        """
        with self.lock:
            if cache_key in self._cache_registry:
                del self._cache_registry[cache_key]

    def cleanup(self) -> None:
        """Clean up resources used by this backend."""
        # Clean up cache directory if we created it
        if hasattr(self, 'cache_dir') and self.cache_dir and 'mcp_huggingface_cache_' in self.cache_dir:
            try:
                if os.path.exists(self.cache_dir):
                    shutil.rmtree(self.cache_dir)
                    logger.info(f"Removed HuggingFace cache directory: {self.cache_dir}")
            except Exception as e:
                logger.warning(f"Failed to remove cache directory: {e}")