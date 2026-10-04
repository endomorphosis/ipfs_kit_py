"""
Hugging Face Model for MCP Server (AnyIO Version).

This module provides the business logic for Hugging Face Hub operations in the MCP server
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


class HuggingFaceModelAnyIO(BaseStorageModel):
    """Model for Hugging Face Hub operations with AnyIO support."""
    def __init__(
        self
huggingface_kit_instance = None
ipfs_model = None
cache_manager = None
credential_manager = None
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

        logger.info("Hugging Face Model (AnyIO) initialized")

    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None

    async def authenticate_async(self, token: str) -> Dict[str, Any]:
        """Authenticate with Hugging Face Hub asynchronously.

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
                # Run the authenticate operation in a thread
                auth_result = await anyio.to_thread.run_sync(lambda: self.hf_kit.login(token=token))

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

    def authenticate(self, token: str) -> Dict[str, Any]:
        """Authenticate with Hugging Face Hub (sync version).

        This method supports both sync and async contexts.
        In async contexts, it logs a warning and returns an error.

        Args:
            token: Hugging Face Hub API token

        Returns:
            Result dictionary with operation status and user info
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync authenticate() in async context ({backend}). Consider using authenticate_async() instead"

            # Create a result with warning
            result = self._create_result_dict("authenticate")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use authenticate_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
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

    async def create_repository_async(
        self, repo_id: str, repo_type: str = "model", private: bool = False
        """Create a new repository on Hugging Face Hub asynchronously.

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
                result["error"] = (
                    f"Invalid repository type. Must be one of: {', '.join(valid_types)}"
                result["error_type"] = "ValidationError"
                return result

            # Use huggingface_kit to create repository
            if self.hf_kit:
                # Run the create repo operation in a thread
                repo_result = await anyio.to_thread.run_sync(
                    lambda: self.hf_kit.create_repo(repo_id, repo_type=repo_type, private=private)

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

    def create_repository(
        self, repo_id: str, repo_type: str = "model", private: bool = False
        """Create a new repository on Hugging Face Hub (sync version).

        This method supports both sync and async contexts.
        In async contexts, it logs a warning and returns an error.

        Args:
            repo_id: Repository ID (username/repo-name)
            repo_type: Repository type (model, dataset, space)
            private: Whether the repository should be private

        Returns:
            Result dictionary with operation status and repository info
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync create_repository() in async context ({backend}). Consider using create_repository_async() instead"

            # Create a result with warning
            result = self._create_result_dict("create_repository")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use create_repository_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
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
                result["error"] = (
                    f"Invalid repository type. Must be one of: {', '.join(valid_types)}"
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

    async def upload_file_async(
    self,
    file_path: str
        repo_id: str
        path_in_repo: Optional[str] = None,
        commit_message: Optional[str] = None,
        repo_type: str = "model",
        """Upload a file to a Hugging Face Hub repository asynchronously.

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
            file_exists = await anyio.to_thread.run_sync(lambda: os.path.exists(file_path))
            if not file_exists:
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
            file_size = await anyio.to_thread.run_sync(lambda: os.path.getsize(file_path))

            # Use huggingface_kit to upload the file
            if self.hf_kit:
                # Run the upload operation in a thread
                upload_result = await anyio.to_thread.run_sync(
                    lambda: self.hf_kit.upload_file_to_repo(
repo_id=repo_id
file_path=file_path
path_in_repo=path_in_repo
commit_message=commit_message
repo_type=repo_type

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

    def upload_file(
    self,
    file_path: str
        repo_id: str
        path_in_repo: Optional[str] = None,
        commit_message: Optional[str] = None,
        repo_type: str = "model",
        """Upload a file to a Hugging Face Hub repository (sync version).

        This method supports both sync and async contexts.
        In async contexts, it logs a warning and returns an error.

        Args:
            file_path: Path to the file to upload
            repo_id: Repository ID (username/repo-name)
            path_in_repo: Path within the repository (uses filename if not provided)
            commit_message: Commit message for the upload
            repo_type: Repository type (model, dataset, space)

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
repo_id=repo_id
file_path=file_path
path_in_repo=path_in_repo
commit_message=commit_message
repo_type=repo_type

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

    async def download_file_async(
    self,
    repo_id: str
        filename: str
        destination: str
        revision: Optional[str] = None,
        repo_type: str = "model",
        """Download a file from a Hugging Face Hub repository asynchronously.

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
            dest_dir = os.path.dirname(os.path.abspath(destination))
            await anyio.to_thread.run_sync(lambda: os.makedirs(dest_dir, exist_ok=True))

            # Use huggingface_kit to download the file
            if self.hf_kit:
                # Run the download operation in a thread
                download_result = await anyio.to_thread.run_sync(
                    lambda: self.hf_kit.download_file_from_repo(
repo_id=repo_id
filename=filename
local_path=destination
revision=revision
repo_type=repo_type

                if download_result.get("success", False):
                    # Get file size for statistics
                    file_exists = await anyio.to_thread.run_sync(
                        lambda: os.path.exists(destination)
                    file_size = 0
                    if file_exists:
                        file_size = await anyio.to_thread.run_sync(
                            lambda: os.path.getsize(destination)

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

    def download_file(
    self,
    repo_id: str
        filename: str
        destination: str
        revision: Optional[str] = None,
        repo_type: str = "model",
        """Download a file from a Hugging Face Hub repository (sync version).

        This method supports both sync and async contexts.
        In async contexts, it logs a warning and returns an error.

        Args:
            repo_id: Repository ID (username/repo-name)
            filename: Filename to download
            destination: Local path to save the file
            revision: Optional Git revision (branch, tag, or commit hash)
            repo_type: Repository type (model, dataset, space)

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
repo_id=repo_id
filename=filename
local_path=destination
revision=revision
repo_type=repo_type

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

    async def list_models_async(
    self,
    author: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        """List models on Hugging Face Hub asynchronously.

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
                # Run the list models operation in a thread
                list_result = await anyio.to_thread.run_sync(
                    lambda: self.hf_kit.list_models(author=author, search=search, limit=limit)

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

    def list_models(
    self,
    author: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        """List models on Hugging Face Hub (sync version).

        This method supports both sync and async contexts.
        In async contexts, it logs a warning and returns an error.

        Args:
            author: Optional filter by author/organization
            search: Optional search query
            limit: Maximum number of results

        Returns:
            Result dictionary with operation status and model list
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync list_models() in async context ({backend}). Consider using list_models_async() instead"

            # Create a result with warning
            result = self._create_result_dict("list_models")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use list_models_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
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

    async def ipfs_to_huggingface_async(
    self,
    cid: str
        repo_id: str
        path_in_repo: Optional[str] = None,
        commit_message: Optional[str] = None,
        repo_type: str = "model",
        pin: bool = True,
        """Get content from IPFS and upload to Hugging Face Hub asynchronously.

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

                # Upload to Hugging Face Hub
                upload_result = await self.upload_file_async(
file_path=temp_path
repo_id=repo_id
path_in_repo=path_in_repo
commit_message=commit_message
repo_type=repo_type

                if not upload_result.get("success", False):
                    result["error"] = upload_result.get(
                        "error", "Failed to upload content to Hugging Face Hub"
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

    def ipfs_to_huggingface(
    self,
    cid: str
        repo_id: str
        path_in_repo: Optional[str] = None,
        commit_message: Optional[str] = None,
        repo_type: str = "model",
        pin: bool = True,
        """Get content from IPFS and upload to Hugging Face Hub (sync version).

        This method supports both sync and async contexts.
        In async contexts, it logs a warning and returns an error.

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
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync ipfs_to_huggingface() in async context ({backend}). Consider using ipfs_to_huggingface_async() instead"

            # Create a result with warning
            result = self._create_result_dict("ipfs_to_huggingface")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use ipfs_to_huggingface_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
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

                # Upload to Hugging Face Hub
                upload_result = self.upload_file(
file_path=temp_path
repo_id=repo_id
path_in_repo=path_in_repo
commit_message=commit_message
repo_type=repo_type

                # Clean up the temporary file
                os.unlink(temp_path)

                if not upload_result.get("success", False):
                    result["error"] = upload_result.get(
                        "error", "Failed to upload content to Hugging Face Hub"
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

    async def huggingface_to_ipfs_async(
    self,
    repo_id: str
        filename: str
        pin: bool = True,
        revision: Optional[str] = None,
        repo_type: str = "model",
        """Get content from Hugging Face Hub and add to IPFS asynchronously.

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
            temp_fd, temp_path = await anyio.to_thread.run_sync(tempfile.mkstemp)
            try:
                # Close the file descriptor
                await anyio.to_thread.run_sync(lambda: os.close(temp_fd))

                # Download content from Hugging Face Hub
                download_result = await self.download_file_async(
repo_id=repo_id
filename=filename
destination=temp_path
revision=revision
repo_type=repo_type

                if not download_result.get("success", False):
                    result["error"] = download_result.get(
                        "error", "Failed to download content from Hugging Face Hub"
                    result["error_type"] = download_result.get(
                        "error_type", "HuggingFaceDownloadError"
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
                        content, filename=filename
                else:
                    # Fall back to sync version
                    ipfs_result = await anyio.to_thread.run_sync(
                        lambda: self.ipfs_model.add_content(content, filename=filename)

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
                result["repo_id"] = repo_id
                result["repo_type"] = repo_type
                result["filename"] = filename
                result["ipfs_cid"] = cid
                result["size_bytes"] = file_size

                if revision:
                    result["revision"] = revision

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

    def huggingface_to_ipfs(
    self,
    repo_id: str
        filename: str
        pin: bool = True,
        revision: Optional[str] = None,
        repo_type: str = "model",
        """Get content from Hugging Face Hub and add to IPFS (sync version).

        This method supports both sync and async contexts.
        In async contexts, it logs a warning and returns an error.

        Args:
            repo_id: Repository ID (username/repo-name)
            filename: Filename to download
            pin: Whether to pin the content in IPFS
            revision: Optional Git revision (branch, tag, or commit hash)
            repo_type: Repository type (model, dataset, space)

        Returns:
            Result dictionary with operation status and details
        """
        backend = self.get_backend()
        if backend:
            # We're in an async context, but this is a sync method
            logger.warning(
                f"Called sync huggingface_to_ipfs() in async context ({backend}). Consider using huggingface_to_ipfs_async() instead"

            # Create a result with warning
            result = self._create_result_dict("huggingface_to_ipfs")
            result["warning"] = f"Called sync method in async context ({backend})"
            result["error"] = "Use huggingface_to_ipfs_async() in async contexts"
            result["error_type"] = "AsyncContextError"
            return result

        # Synchronous implementation (same as original method)
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
repo_id=repo_id
filename=filename
destination=temp_path
revision=revision
repo_type=repo_type

                if not download_result.get("success", False):
                    result["error"] = download_result.get(
                        "error", "Failed to download content from Hugging Face Hub"
                    result["error_type"] = download_result.get(
                        "error_type", "HuggingFaceDownloadError"
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

    async def get_stats_async(self) -> Dict[str, Any]:
        """Get current operation statistics asynchronously."""
        return {"operation_stats": self.operation_stats, "timestamp": time.time()}

    async def reset_async(self) -> None:
        """Reset model state for testing asynchronously."""
        self.operation_stats = self._initialize_stats()
        self.correlation_id = str(uuid.uuid4())
        logger.info(f"Reset HuggingFaceModel (AnyIO) state, new ID: {self.correlation_id}")
