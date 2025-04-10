"""Hugging Face Hub integration for ipfs_kit_py.

This module provides integration with the Hugging Face Hub for model and dataset access,
extending the ipfs_kit_py ecosystem with a new storage backend. It allows for seamless
authentication, content retrieval, and caching across Hugging Face repositories.
"""

import json
import logging
import os
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Union

try:
    from huggingface_hub import (
        HfApi,
        HfFolder,
        Repository,
        create_repo,
        login,
        whoami,
    )
    from huggingface_hub.utils import RepositoryNotFoundError, RevisionNotFoundError

    HUGGINGFACE_HUB_AVAILABLE = True
except ImportError:
    HUGGINGFACE_HUB_AVAILABLE = False
    # Create placeholder for imports
    HfApi = None
    HfFolder = None
    Repository = None
    create_repo = None
    login = None
    whoami = None
    RepositoryNotFoundError = Exception
    RevisionNotFoundError = Exception

# Configure logger
logger = logging.getLogger(__name__)


def create_result_dict(operation, correlation_id=None):
    """Create a standardized result dictionary."""
    return {
        "success": False,
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id or str(uuid.uuid4()),
    }


def handle_error(result, error, message=None):
    """Handle errors in a standardized way."""
    result["success"] = False
    result["error"] = message or str(error)
    result["error_type"] = type(error).__name__
    return result


class huggingface_kit:
    """Interface to Hugging Face Hub for model and dataset management.

    This class provides an integration with Hugging Face Hub for accessing models
    and datasets, supporting authentication, content retrieval, and uploading.
    It follows the storage backend pattern used in other ipfs_kit_py components,
    making it compatible with the adaptive replacement cache.
    """
    
    def _check_and_install_dependencies(self):
        """Check if required dependencies are available and install if possible.
        
        This method ensures that the huggingface_hub library is available
        and attempts to install it if missing.
        
        Returns:
            bool: True if dependencies are available, False otherwise
        """
        global HUGGINGFACE_HUB_AVAILABLE
        
        if not HUGGINGFACE_HUB_AVAILABLE:
            logger.warning("huggingface_hub package not available. Some functionality will be limited.")
            logger.info("You can install it with: pip install huggingface_hub")
            
        return HUGGINGFACE_HUB_AVAILABLE

    def __init__(self, resources=None, metadata=None):
        """Initialize the Hugging Face Hub interface.

        Args:
            resources: Dictionary with resources and configuration
            metadata: Additional metadata
        """
        # Store resources
        self.resources = resources or {}
        
        # Store metadata
        self.metadata = metadata or {}
        
        # Generate correlation ID for tracking operations
        self.correlation_id = str(uuid.uuid4())
        
        # Initialize authentication state
        self.is_authenticated = False
        self.user_info = None
        
        # Auto-install dependencies on first run if they're not already installed
        if not self.metadata.get("skip_dependency_check", False):
            self._check_and_install_dependencies()
        
        # Check HuggingFace Hub availability (after potential installation)
        if not HUGGINGFACE_HUB_AVAILABLE:
            logger.warning(
                "huggingface_hub package is not installed. HuggingFace Hub functionality will be limited."
            )
            logger.warning(
                "To enable HuggingFace Hub support, install with: pip install ipfs_kit_py[huggingface]"
            )
        
        # Generate API client
        self.api = HfApi() if HUGGINGFACE_HUB_AVAILABLE else None
        
        # Set up cache directories
        self.cache_dir = self.metadata.get("cache_dir", os.path.expanduser("~/.cache/huggingface/ipfs_kit"))
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Try to authenticate with token from resources or environment
        self._try_authenticate()

    def __call__(self, method, **kwargs):
        """Call a method on the HuggingFace Hub kit.

        Args:
            method: Method name to call
            **kwargs: Arguments to pass to the method

        Returns:
            Result of the method call
        """
        # Forward the call to the appropriate method
        if method == "login":
            return self.login(**kwargs)
        elif method == "whoami":
            return self.whoami(**kwargs)
        elif method == "create_repo":
            return self.create_repo(**kwargs)
        elif method == "delete_repo":
            return self.delete_repo(**kwargs)
        elif method == "list_repos":
            return self.list_repos(**kwargs)
        elif method == "download_file":
            return self.download_file(**kwargs)
        elif method == "upload_file":
            return self.upload_file(**kwargs)
        elif method == "list_files":
            return self.list_files(**kwargs)
        elif method == "repo_info":
            return self.repo_info(**kwargs)
        else:
            result = create_result_dict(method, self.correlation_id)
            result["error"] = f"Unknown method: {method}"
            return result

    def _try_authenticate(self):
        """Try to authenticate with available credentials."""
        if not HUGGINGFACE_HUB_AVAILABLE:
            return False

        # Check if token is provided in resources
        token = self.resources.get("token")
        
        # If not in resources, check environment
        if not token:
            token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
        
        # If token is available, try to authenticate
        if token:
            try:
                login(token=token, add_to_git_credential=False)
                self.user_info = whoami()
                self.is_authenticated = True
                logger.info(f"Authenticated with HuggingFace Hub as {self.user_info['name']}")
                return True
            except Exception as e:
                logger.warning(f"Failed to authenticate with HuggingFace Hub: {str(e)}")
                return False
        
        # Check if already logged in via local token
        try:
            user_info = whoami()
            if user_info:
                self.user_info = user_info
                self.is_authenticated = True
                logger.info(f"Using existing HuggingFace Hub authentication as {self.user_info['name']}")
                return True
        except Exception:
            logger.debug("No existing HuggingFace Hub authentication found")
            return False
            
        return False

    def login(self, token=None, **kwargs):
        """Authenticate with Hugging Face Hub.

        Args:
            token: Authentication token
            **kwargs: Additional arguments

        Returns:
            Result dictionary with authentication status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("login", correlation_id)
        
        if not HUGGINGFACE_HUB_AVAILABLE:
            result["error"] = "HuggingFace Hub integration not available"
            return result
        
        try:
            # Use token from parameters, resources, or environment
            auth_token = token or self.resources.get("token")
            
            if not auth_token:
                auth_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
                if not auth_token:
                    result["error"] = "No authentication token provided"
                    return result
            
            # Authenticate with token
            login(token=auth_token, add_to_git_credential=False)
            
            # Get user information
            self.user_info = whoami()
            self.is_authenticated = True
            
            # Set result success and add user info
            result["success"] = True
            result["user"] = {
                "name": self.user_info["name"],
                "email": self.user_info.get("email", ""),
                "orgs": self.user_info.get("orgs", []),
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in login: {str(e)}")
            return handle_error(result, e)

    def whoami(self, **kwargs):
        """Get information about the authenticated user.

        Args:
            **kwargs: Additional arguments

        Returns:
            Result dictionary with user information
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("whoami", correlation_id)
        
        if not HUGGINGFACE_HUB_AVAILABLE:
            result["error"] = "HuggingFace Hub integration not available"
            return result
        
        try:
            # Check if already authenticated
            if not self.is_authenticated:
                # Try to authenticate
                auth_success = self._try_authenticate()
                if not auth_success:
                    result["error"] = "Not authenticated with HuggingFace Hub"
                    return result
            
            # Get user information
            user_info = whoami()
            
            # Set result success and add user info
            result["success"] = True
            result["user"] = {
                "name": user_info["name"],
                "email": user_info.get("email", ""),
                "orgs": user_info.get("orgs", []),
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in whoami: {str(e)}")
            return handle_error(result, e)

    def create_repo(self, repo_id, repo_type="model", private=False, exist_ok=False, **kwargs):
        """Create a new repository on Hugging Face Hub.

        Args:
            repo_id: Repository ID (namespace/name)
            repo_type: Repository type ("model", "dataset", or "space")
            private: Whether the repository should be private
            exist_ok: Whether to ignore if the repository already exists
            **kwargs: Additional arguments

        Returns:
            Result dictionary with repository information
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("create_repo", correlation_id)
        result["repo_id"] = repo_id
        result["repo_type"] = repo_type
        
        if not HUGGINGFACE_HUB_AVAILABLE:
            result["error"] = "HuggingFace Hub integration not available"
            return result
        
        try:
            # Check if authenticated
            if not self.is_authenticated:
                auth_success = self._try_authenticate()
                if not auth_success:
                    result["error"] = "Not authenticated with HuggingFace Hub"
                    return result
            
            # Create the repository
            repo_url = create_repo(
                repo_id=repo_id,
                token=HfFolder.get_token(),
                repo_type=repo_type,
                private=private,
                exist_ok=exist_ok,
            )
            
            # Set result success and add repository information
            result["success"] = True
            result["repo_url"] = repo_url
            result["private"] = private
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in create_repo: {str(e)}")
            return handle_error(result, e)

    def delete_repo(self, repo_id, repo_type="model", **kwargs):
        """Delete a repository from Hugging Face Hub.

        Args:
            repo_id: Repository ID (namespace/name)
            repo_type: Repository type ("model", "dataset", or "space")
            **kwargs: Additional arguments

        Returns:
            Result dictionary with deletion status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("delete_repo", correlation_id)
        result["repo_id"] = repo_id
        result["repo_type"] = repo_type
        
        if not HUGGINGFACE_HUB_AVAILABLE:
            result["error"] = "HuggingFace Hub integration not available"
            return result
        
        try:
            # Check if authenticated
            if not self.is_authenticated:
                auth_success = self._try_authenticate()
                if not auth_success:
                    result["error"] = "Not authenticated with HuggingFace Hub"
                    return result
            
            # Delete the repository
            self.api.delete_repo(
                repo_id=repo_id,
                repo_type=repo_type,
                token=HfFolder.get_token(),
            )
            
            # Set result success
            result["success"] = True
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in delete_repo: {str(e)}")
            return handle_error(result, e)

    def list_repos(self, repo_type="model", **kwargs):
        """List repositories for the authenticated user.

        Args:
            repo_type: Repository type ("model", "dataset", or "space")
            **kwargs: Additional arguments

        Returns:
            Result dictionary with repository list
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("list_repos", correlation_id)
        result["repo_type"] = repo_type
        
        if not HUGGINGFACE_HUB_AVAILABLE:
            result["error"] = "HuggingFace Hub integration not available"
            return result
        
        try:
            # Check if authenticated
            if not self.is_authenticated:
                auth_success = self._try_authenticate()
                if not auth_success:
                    result["error"] = "Not authenticated with HuggingFace Hub"
                    return result
            
            # Get repository list
            repos = self.api.list_repos(
                token=HfFolder.get_token(),
                repo_type=repo_type,
            )
            
            # Extract relevant information
            repo_list = []
            for repo in repos:
                repo_info = {
                    "id": repo.id,
                    "name": repo.name,
                    "owner": repo.namespace,
                    "url": repo.url,
                    "private": repo.private,
                    "type": repo.repo_type,
                    "last_modified": repo.lastModified,
                }
                repo_list.append(repo_info)
            
            # Set result success and add repository list
            result["success"] = True
            result["repos"] = repo_list
            result["count"] = len(repo_list)
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in list_repos: {str(e)}")
            return handle_error(result, e)

    def download_file(self, repo_id, filename, revision="main", repo_type="model", **kwargs):
        """Download a file from a Hugging Face repository.

        Args:
            repo_id: Repository ID (namespace/name)
            filename: Path to the file in the repository
            revision: Git revision (branch, tag, or commit hash)
            repo_type: Repository type ("model", "dataset", or "space")
            **kwargs: Additional arguments

        Returns:
            Result dictionary with downloaded content and metadata
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("download_file", correlation_id)
        result["repo_id"] = repo_id
        result["filename"] = filename
        result["revision"] = revision
        result["repo_type"] = repo_type
        
        if not HUGGINGFACE_HUB_AVAILABLE:
            result["error"] = "HuggingFace Hub integration not available"
            return result
        
        try:
            # Define local path to store the cached file
            # Create a deterministic path based on repo_id, revision, and filename
            cache_key = f"{repo_id}/{revision}/{filename}".replace("/", "_")
            local_path = os.path.join(self.cache_dir, cache_key)
            
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download the file
            local_file = self.api.hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                repo_type=repo_type,
                local_dir=self.cache_dir,
                local_dir_use_symlinks=False,
            )
            
            # Read the file content
            with open(local_file, "rb") as f:
                content = f.read()
            
            # Get file metadata
            file_stats = os.stat(local_file)
            
            # Set result success and add file information
            result["success"] = True
            result["content"] = content
            result["size"] = file_stats.st_size
            result["local_path"] = local_file
            result["last_modified"] = file_stats.st_mtime
            
            # Include repository info in metadata for caching purposes
            result["metadata"] = {
                "repo_id": repo_id,
                "filename": filename,
                "revision": revision,
                "repo_type": repo_type,
                "huggingface_source": True,
                "download_time": time.time(),
            }
            
            return result
            
        except RepositoryNotFoundError as e:
            logger.error(f"Repository not found: {repo_id}")
            return handle_error(result, e, f"Repository not found: {repo_id}")
            
        except RevisionNotFoundError as e:
            logger.error(f"Revision not found: {revision} in {repo_id}")
            return handle_error(result, e, f"Revision not found: {revision} in {repo_id}")
            
        except Exception as e:
            logger.exception(f"Error in download_file: {str(e)}")
            return handle_error(result, e)

    def upload_file(self, repo_id, local_file, path_in_repo, commit_message=None, revision="main", repo_type="model", **kwargs):
        """Upload a file to a Hugging Face repository.

        Args:
            repo_id: Repository ID (namespace/name)
            local_file: Path to local file or file-like object content
            path_in_repo: Path in the repository to save the file
            commit_message: Commit message
            revision: Git revision (branch, tag, or commit hash)
            repo_type: Repository type ("model", "dataset", or "space")
            **kwargs: Additional arguments

        Returns:
            Result dictionary with upload status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("upload_file", correlation_id)
        result["repo_id"] = repo_id
        result["path_in_repo"] = path_in_repo
        result["revision"] = revision
        result["repo_type"] = repo_type
        
        if not HUGGINGFACE_HUB_AVAILABLE:
            result["error"] = "HuggingFace Hub integration not available"
            return result
        
        try:
            # Check if authenticated
            if not self.is_authenticated:
                auth_success = self._try_authenticate()
                if not auth_success:
                    result["error"] = "Not authenticated with HuggingFace Hub"
                    return result
            
            # Prepare the file content
            if isinstance(local_file, bytes):
                # If content is provided directly as bytes
                file_content = local_file
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(file_content)
                    temp_file_path = temp_file.name
                    
                try:
                    # Upload the file
                    self.api.upload_file(
                        path_or_fileobj=temp_file_path,
                        path_in_repo=path_in_repo,
                        repo_id=repo_id,
                        token=HfFolder.get_token(),
                        repo_type=repo_type,
                        revision=revision,
                        commit_message=commit_message or f"Upload {path_in_repo}",
                    )
                    
                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                    
            else:
                # If local file path is provided
                file_path = local_file
                
                # Check if file exists
                if not os.path.exists(file_path):
                    result["error"] = f"Local file not found: {file_path}"
                    return result
                
                # Upload the file
                self.api.upload_file(
                    path_or_fileobj=file_path,
                    path_in_repo=path_in_repo,
                    repo_id=repo_id,
                    token=HfFolder.get_token(),
                    repo_type=repo_type,
                    revision=revision,
                    commit_message=commit_message or f"Upload {path_in_repo}",
                )
            
            # Set result success
            result["success"] = True
            
            return result
            
        except RepositoryNotFoundError as e:
            logger.error(f"Repository not found: {repo_id}")
            return handle_error(result, e, f"Repository not found: {repo_id}")
            
        except RevisionNotFoundError as e:
            logger.error(f"Revision not found: {revision} in {repo_id}")
            return handle_error(result, e, f"Revision not found: {revision} in {repo_id}")
            
        except Exception as e:
            logger.exception(f"Error in upload_file: {str(e)}")
            return handle_error(result, e)

    def list_files(self, repo_id, path="", revision="main", repo_type="model", **kwargs):
        """List files in a Hugging Face repository.

        Args:
            repo_id: Repository ID (namespace/name)
            path: Path in the repository to list files from
            revision: Git revision (branch, tag, or commit hash)
            repo_type: Repository type ("model", "dataset", or "space")
            **kwargs: Additional arguments

        Returns:
            Result dictionary with file list
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("list_files", correlation_id)
        result["repo_id"] = repo_id
        result["path"] = path
        result["revision"] = revision
        result["repo_type"] = repo_type
        
        if not HUGGINGFACE_HUB_AVAILABLE:
            result["error"] = "HuggingFace Hub integration not available"
            return result
        
        try:
            # List files in the repository
            files = self.api.list_repo_files(
                repo_id=repo_id,
                revision=revision,
                repo_type=repo_type,
            )
            
            # Filter files by path if specified
            if path:
                # Add trailing slash to path if not present for directory matching
                if path and not path.endswith("/"):
                    path = path + "/"
                    
                # Filter files that start with the specified path
                filtered_files = [f for f in files if f.startswith(path)]
                
                # Extract relative paths
                relative_files = [f[len(path):] for f in filtered_files]
                
                # Get unique directories at this level
                dirs = set()
                files_in_dir = []
                
                for file in relative_files:
                    if "/" in file:
                        # This is a file in a subdirectory
                        dir_name = file.split("/")[0]
                        dirs.add(dir_name)
                    else:
                        # This is a file in the current directory
                        files_in_dir.append(file)
                
                # Format result
                result["directories"] = sorted(list(dirs))
                result["files"] = sorted(files_in_dir)
                result["full_paths"] = sorted(filtered_files)
                
            else:
                # No path filtering, return all files
                # Extract directories at the root level
                dirs = set()
                files_in_root = []
                
                for file in files:
                    if "/" in file:
                        # This is a file in a subdirectory
                        dir_name = file.split("/")[0]
                        dirs.add(dir_name)
                    else:
                        # This is a file in the root directory
                        files_in_root.append(file)
                
                # Format result
                result["directories"] = sorted(list(dirs))
                result["files"] = sorted(files_in_root)
                result["full_paths"] = sorted(files)
            
            # Set result success
            result["success"] = True
            result["count"] = len(result["full_paths"])
            
            return result
            
        except RepositoryNotFoundError as e:
            logger.error(f"Repository not found: {repo_id}")
            return handle_error(result, e, f"Repository not found: {repo_id}")
            
        except RevisionNotFoundError as e:
            logger.error(f"Revision not found: {revision} in {repo_id}")
            return handle_error(result, e, f"Revision not found: {revision} in {repo_id}")
            
        except Exception as e:
            logger.exception(f"Error in list_files: {str(e)}")
            return handle_error(result, e)

    def repo_info(self, repo_id, repo_type="model", **kwargs):
        """Get information about a Hugging Face repository.

        Args:
            repo_id: Repository ID (namespace/name)
            repo_type: Repository type ("model", "dataset", or "space")
            **kwargs: Additional arguments

        Returns:
            Result dictionary with repository information
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("repo_info", correlation_id)
        result["repo_id"] = repo_id
        result["repo_type"] = repo_type
        
        if not HUGGINGFACE_HUB_AVAILABLE:
            result["error"] = "HuggingFace Hub integration not available"
            return result
        
        try:
            # Get repository information
            repo_info = self.api.repo_info(
                repo_id=repo_id,
                repo_type=repo_type,
            )
            
            # Extract relevant information
            info = {
                "id": repo_info.id,
                "name": repo_info.name,
                "owner": repo_info.namespace,
                "url": repo_info.url,
                "private": repo_info.private,
                "type": repo_info.repo_type,
                "last_modified": repo_info.lastModified,
                "tags": repo_info.tags,
                "siblings": repo_info.siblings,
                "card_data": repo_info.card_data,
                "default_branch": repo_info.default_branch,
            }
            
            # Set result success and add repository information
            result["success"] = True
            result["info"] = info
            
            return result
            
        except RepositoryNotFoundError as e:
            logger.error(f"Repository not found: {repo_id}")
            return handle_error(result, e, f"Repository not found: {repo_id}")
            
        except Exception as e:
            logger.exception(f"Error in repo_info: {str(e)}")
            return handle_error(result, e)