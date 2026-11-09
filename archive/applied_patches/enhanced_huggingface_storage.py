"""
Enhanced HuggingFace storage backend implementation for MCP server.

This module provides robust integration with the HuggingFace Hub
for storing and retrieving IPFS content, with improved repository
management and error handling.
"""

import os
import json
import logging
import tempfile
import time
import subprocess
import re
from typing import Dict, Any, Optional, Union, List, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Check if huggingface_hub is available
try:
    from huggingface_hub import HfApi, hf_hub_download, upload_file, create_repo, Repository
    from huggingface_hub.utils import RepositoryNotFoundError, RevisionNotFoundError, HfHubHTTPError
    HUGGINGFACE_AVAILABLE = True
    logger.info("HuggingFace Hub SDK is available")
except ImportError:
    HUGGINGFACE_AVAILABLE = False
    logger.warning("HuggingFace Hub SDK is not available. Install with: pip install huggingface_hub")

# Default repository settings
DEFAULT_REPO_NAME = "ipfs-storage"
DEFAULT_REPO_TYPE = "dataset"  # Other options: "model", "space"

class HuggingFaceStorage:
    """
    Enhanced implementation of HuggingFace storage backend for IPFS content.
    
    This class provides methods to store and retrieve IPFS content using HuggingFace Hub,
    with improved repository management, error handling, and configuration options.
    """
    
    def __init__(self, token=None, organization=None, repo_name=None, repo_type=None):
        """
        Initialize the HuggingFace storage backend.
        
        Args:
            token (str): HuggingFace API token. If None, will try to get from environment.
            organization (str): HuggingFace organization name. If None, will use user account.
            repo_name (str): Repository name for IPFS storage. Defaults to environment variable or 'ipfs-storage'.
            repo_type (str): Repository type ('dataset', 'model', or 'space'). Defaults to environment variable or 'dataset'.
        """
        # Get configuration from environment variables or parameters
        self.token = token or os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
        self.organization = organization or os.environ.get("HUGGINGFACE_ORGANIZATION") or os.environ.get("HF_ORGANIZATION")
        self.repo_name = (repo_name or 
                         os.environ.get("HUGGINGFACE_REPO") or 
                         os.environ.get("HF_REPO") or 
                         DEFAULT_REPO_NAME)
        self.repo_type = (repo_type or 
                         os.environ.get("HUGGINGFACE_REPO_TYPE") or 
                         os.environ.get("HF_REPO_TYPE") or 
                         DEFAULT_REPO_TYPE)
        
        # Initialize state variables
        self.api = None
        self.mock_mode = os.environ.get("HF_MOCK_MODE", "").lower() in ["true", "1", "yes"]
        self.simulation_mode = not HUGGINGFACE_AVAILABLE
        self.user_info = None
        self.repo_info = None
        self.repo_exists = False
        self.repo_creation_attempted = False
        
        # Initialize the API if available
        if HUGGINGFACE_AVAILABLE:
            try:
                # Always create an API instance even without a token
                # This allows for proper initialization in mock mode
                self.api = HfApi(token=self.token if self.token else None)
                logger.info("Initialized HuggingFace API client")
                
                if self.token:
                    # With token, try to verify it works
                    try:
                        self.user_info = self.api.whoami()
                        logger.info(f"Authenticated as {self.user_info.get('name')}")
                        self.simulation_mode = False
                    except Exception as e:
                        logger.warning(f"Failed to authenticate with HuggingFace API: {e}")
                        self.mock_mode = True
                else:
                    # Without token, use mock mode
                    logger.info("No HuggingFace token provided, will use mock mode")
                    self.mock_mode = True
                    self.simulation_mode = False
            except Exception as e:
                logger.error(f"Failed to initialize HuggingFace API: {e}")
                self.simulation_mode = True
        
        # If in mock mode, set up mock storage
        if self.mock_mode:
            self._setup_mock_storage()
            self.simulation_mode = False
    
    def _setup_mock_storage(self):
        """Set up mock storage for local testing."""
        try:
            # Create directories for mock storage
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_huggingface")
            repo_dir = os.path.join(mock_dir, self._get_repository_name())
            os.makedirs(repo_dir, exist_ok=True)
            
            # Create subdirectories for organization if applicable
            if self.organization:
                org_dir = os.path.join(mock_dir, self.organization)
                os.makedirs(org_dir, exist_ok=True)
            
            logger.info(f"Set up mock HuggingFace storage at {repo_dir}")
        except Exception as e:
            logger.error(f"Failed to set up mock storage: {e}")
    
    def status(self) -> Dict[str, Any]:
        """
        Get the status of the HuggingFace storage backend.
        
        Returns:
            Dict containing status information
        """
        status_info = {
            "success": True,
            "available": HUGGINGFACE_AVAILABLE and (self.api is not None or self.mock_mode),
            "simulation": self.simulation_mode,
            "mock": self.mock_mode,
            "timestamp": time.time()
        }
        
        if self.simulation_mode:
            status_info["message"] = "Running in simulation mode"
            if not HUGGINGFACE_AVAILABLE:
                status_info["error"] = "HuggingFace Hub SDK not installed"
            elif not self.token:
                status_info["error"] = "HuggingFace API token not provided"
        elif self.mock_mode:
            status_info["message"] = "Running in mock mode"
            # Include mock storage details
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_huggingface")
            status_info["mock_storage_path"] = mock_dir
            status_info["mock_repo"] = self._get_repository_name()
        else:
            # Only test API connection if we have a token and not in mock mode
            if self.token and self.api:
                try:
                    if not self.user_info:
                        self.user_info = self.api.whoami()
                    
                    status_info["user"] = self.user_info.get("name")
                    status_info["organizations"] = self.user_info.get("orgs", [])
                    status_info["message"] = "Connected to HuggingFace Hub"
                    
                    # Check repository status
                    repo_exists, repo_info = self._check_repository_exists()
                    if repo_exists:
                        status_info["repository"] = {
                            "id": self._get_repository_name(),
                            "type": repo_info.get("type"),
                            "private": repo_info.get("private", False)
                        }
                    else:
                        status_info["repository"] = {
                            "id": self._get_repository_name(),
                            "exists": False
                        }
                except Exception as e:
                    status_info["error"] = str(e)
                    status_info["success"] = False
                    status_info["message"] = "Failed to connect to HuggingFace Hub"
            else:
                status_info["message"] = "API available but no token provided"
                status_info["error"] = "Missing HuggingFace API token"
        
        return status_info
    
    def _get_repository_name(self) -> str:
        """
        Get the full repository name.
        
        Returns:
            Full repository name in format 'organization/repo_name' or 'repo_name'
        """
        if self.organization:
            return f"{self.organization}/{self.repo_name}"
        return self.repo_name
    
    def _check_repository_exists(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if the repository exists.
        
        Returns:
            Tuple of (exists: bool, info: Optional[Dict])
        """
        if self.repo_exists and self.repo_info:
            return True, self.repo_info
            
        if self.simulation_mode or not self.api:
            return False, None
            
        # If in mock mode, check local directory
        if self.mock_mode:
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_huggingface")
            repo_dir = os.path.join(mock_dir, self._get_repository_name())
            exists = os.path.isdir(repo_dir)
            
            if exists:
                # Create mock repo info
                self.repo_exists = True
                self.repo_info = {
                    "id": self._get_repository_name(),
                    "type": self.repo_type,
                    "private": True,
                    "files": self._list_mock_files(repo_dir)
                }
                return True, self.repo_info
            return False, None
            
        # Real implementation
        try:
            repo_name = self._get_repository_name()
            repo_info = self.api.repo_info(repo_id=repo_name, repo_type=self.repo_type)
            self.repo_exists = True
            self.repo_info = repo_info
            return True, repo_info
        except RepositoryNotFoundError:
            return False, None
        except Exception as e:
            logger.warning(f"Error checking if repository exists: {e}")
            return False, None
    
    def _list_mock_files(self, repo_dir):
        """List files in mock repository."""
        files = []
        for root, _, filenames in os.walk(repo_dir):
            for filename in filenames:
                # Get relative path from repo_dir
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, repo_dir)
                files.append(rel_path)
        return files
    
    def _ensure_repository_exists(self) -> bool:
        """
        Ensure the repository exists, creating it if necessary.
        
        Returns:
            bool: True if repository exists or was created, False otherwise
        """
        # If in simulation mode, cannot ensure repository
        if self.simulation_mode:
            return False
            
        # If repository already exists and confirmed, no need to check again
        if self.repo_exists and self.repo_info:
            return True
            
        # Check if repository exists
        repo_exists, _ = self._check_repository_exists()
        if repo_exists:
            return True
            
        # If we already tried to create it once and failed, don't try again
        if self.repo_creation_attempted:
            return False
            
        try:
            repo_name = self._get_repository_name()
            
            # If in mock mode, create local directory
            if self.mock_mode:
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_huggingface")
                repo_dir = os.path.join(mock_dir, repo_name)
                os.makedirs(repo_dir, exist_ok=True)
                logger.info(f"Created mock repository directory at {repo_dir}")
                self.repo_exists = True
                self.repo_info = {
                    "id": repo_name,
                    "type": self.repo_type,
                    "private": True,
                    "files": []
                }
                return True
                
            # Real implementation - create repository
            logger.info(f"Creating HuggingFace repository: {repo_name} (type: {self.repo_type})")
            
            # Mark that we attempted to create the repository
            self.repo_creation_attempted = True
            
            # Get repo_id without organization prefix for create_repo call
            # (create_repo expects organization as separate parameter)
            repo_id = self.repo_name
            namespace = self.organization
            
            self.api.create_repo(
                repo_id=repo_id,
                token=self.token,
                organization=namespace,
                private=True,
                repo_type=self.repo_type,
                exist_ok=True
            )
            
            # Verify repository was created
            repo_exists, repo_info = self._check_repository_exists()
            if repo_exists:
                logger.info(f"Successfully created repository {repo_name}")
                return True
            else:
                logger.error(f"Failed to create repository {repo_name}")
                return False
        except Exception as e:
            logger.error(f"Failed to ensure repository exists: {e}")
            return False
    
    def _parse_error_message(self, error_message: str) -> Dict[str, Any]:
        """
        Parse error message to extract useful information.
        
        Args:
            error_message: Error message string
            
        Returns:
            Dict with structured error information
        """
        result = {
            "original_message": error_message,
            "possible_causes": [],
            "suggested_actions": []
        }
        
        # Repository not found
        if "Repository Not Found" in error_message:
            result["error_type"] = "repository_not_found"
            result["possible_causes"].append("The specified repository does not exist")
            result["possible_causes"].append("You don't have permission to access this repository")
            result["suggested_actions"].append("Create the repository manually")
            result["suggested_actions"].append("Check your permissions")
            
            # Extract repository details from error
            repo_match = re.search(r"https://huggingface.co/api/([^/]+)/([^/]+)", error_message)
            if repo_match:
                result["repo_type"] = repo_match.group(1)
                result["repo_id"] = repo_match.group(2)
                
                # Check if there's a repo type mismatch
                if result["repo_type"] != self.repo_type:
                    result["possible_causes"].append(f"Repository type mismatch: API expects '{result['repo_type']}' but configured for '{self.repo_type}'")
                    result["suggested_actions"].append(f"Set HUGGINGFACE_REPO_TYPE environment variable to '{result['repo_type']}'")
        
        # Authentication issues
        elif "401 Client Error" in error_message or "unauthorized" in error_message.lower():
            result["error_type"] = "authentication"
            result["possible_causes"].append("Invalid API token")
            result["possible_causes"].append("Token expired or revoked")
            result["suggested_actions"].append("Check your HuggingFace token")
            result["suggested_actions"].append("Generate a new token at https://huggingface.co/settings/tokens")
        
        # Permission issues
        elif "403 Client Error" in error_message or "permission" in error_message.lower():
            result["error_type"] = "permission"
            result["possible_causes"].append("Insufficient permissions")
            result["possible_causes"].append("Token doesn't have write access")
            result["suggested_actions"].append("Ensure your token has write privileges")
            
        # Rate limiting
        elif "429 Client Error" in error_message or "rate limit" in error_message.lower():
            result["error_type"] = "rate_limit"
            result["possible_causes"].append("Too many requests in a short period")
            result["suggested_actions"].append("Implement exponential backoff")
            result["suggested_actions"].append("Reduce request frequency")
            
        else:
            result["error_type"] = "unknown"
            result["possible_causes"].append("Unexpected error occurred")
            result["suggested_actions"].append("Check HuggingFace status page")
            result["suggested_actions"].append("Retry the operation")
            
        return result
    
    def to_ipfs(self, file_path: str, cid: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload content from HuggingFace to IPFS.
        
        Args:
            file_path: Path to file on HuggingFace
            cid: Optional CID to assign (for verification)
            
        Returns:
            Dict with upload status and CID
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "HuggingFace backend is in simulation mode"
            }
        
        # If in mock mode, simulate the operation with local storage
        if self.mock_mode:
            try:
                # Create a mock storage directory if it doesn't exist
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_huggingface")
                repo_name = self._get_repository_name()
                repo_dir = os.path.join(mock_dir, repo_name)
                
                # Check if the file exists in mock storage
                mock_file_path = os.path.join(repo_dir, file_path)
                if not os.path.exists(mock_file_path):
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"File not found in mock storage: {file_path}",
                        "repository": repo_name
                    }
                
                # Add the file to IPFS
                result = subprocess.run(
                    ["ipfs", "add", "-q", mock_file_path],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"Failed to add to IPFS: {result.stderr}",
                        "repository": repo_name
                    }
                
                new_cid = result.stdout.strip()
                
                # Verify CID if provided
                if cid and cid != new_cid:
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"CID mismatch: expected {cid}, got {new_cid}",
                        "repository": repo_name
                    }
                
                return {
                    "success": True,
                    "mock": True,
                    "message": "Added content from mock HuggingFace storage to IPFS",
                    "cid": new_cid,
                    "source": f"mock_huggingface:{repo_name}/{file_path}",
                    "repository": repo_name
                }
                
            except Exception as e:
                logger.error(f"Error in mock to_ipfs: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e)
                }
        
        try:
            # Ensure repository exists
            if not self._ensure_repository_exists():
                return {
                    "success": False,
                    "error": "Failed to ensure repository exists",
                    "repository": self._get_repository_name()
                }
                
            # Download from HuggingFace
            repo_name = self._get_repository_name()
            
            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                
            try:
                # Download the file from HuggingFace
                local_path = hf_hub_download(
                    repo_id=repo_name,
                    filename=file_path,
                    token=self.token,
                    repo_type=self.repo_type,
                    local_dir=os.path.dirname(temp_path),
                    local_dir_use_symlinks=False
                )
                
                # Upload to IPFS
                result = subprocess.run(
                    ["ipfs", "add", "-q", local_path],
                    capture_output=True,
                    text=True
                )
                
                # Clean up the temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                
                if result.returncode == 0:
                    new_cid = result.stdout.strip()
                    
                    # Verify CID if provided
                    if cid and cid != new_cid:
                        return {
                            "success": False,
                            "error": f"CID mismatch: expected {cid}, got {new_cid}",
                            "repository": repo_name
                        }
                    
                    return {
                        "success": True,
                        "cid": new_cid,
                        "source": f"huggingface:{repo_name}/{file_path}",
                        "repository": repo_name
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to add to IPFS: {result.stderr}",
                        "repository": repo_name
                    }
            except RepositoryNotFoundError as e:
                error_info = self._parse_error_message(str(e))
                return {
                    "success": False,
                    "error": f"Repository not found: {repo_name}",
                    "repository": repo_name,
                    "error_details": error_info
                }
            except HfHubHTTPError as e:
                error_info = self._parse_error_message(str(e))
                return {
                    "success": False,
                    "error": f"HuggingFace API error: {str(e)}",
                    "repository": repo_name,
                    "error_details": error_info
                }
                
        except Exception as e:
            logger.error(f"Error transferring from HuggingFace to IPFS: {e}")
            error_info = self._parse_error_message(str(e))
            return {
                "success": False,
                "error": str(e),
                "error_details": error_info,
                "repository": self._get_repository_name()
            }
    
    def from_ipfs(self, cid: str, path: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload content from IPFS to HuggingFace.
        
        Args:
            cid: Content ID to upload
            path: Optional path within repository
            
        Returns:
            Dict with upload status and URL
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "HuggingFace backend is in simulation mode"
            }
        
        # If in mock mode, simulate the operation with local storage
        if self.mock_mode:
            try:
                # Create a mock storage directory if it doesn't exist
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_huggingface")
                repo_name = self._get_repository_name()
                repo_dir = os.path.join(mock_dir, repo_name)
                os.makedirs(repo_dir, exist_ok=True)
                
                # Get content from IPFS
                result = subprocess.run(
                    ["ipfs", "cat", cid],
                    capture_output=True
                )
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}",
                        "repository": repo_name
                    }
                
                # Determine storage path
                file_path = path or f"ipfs/{cid}"
                full_path = os.path.join(repo_dir, file_path)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Write content to file
                with open(full_path, "wb") as f:
                    f.write(result.stdout)
                
                return {
                    "success": True,
                    "mock": True,
                    "message": "Content stored in mock HuggingFace storage",
                    "url": f"file://{full_path}",
                    "cid": cid,
                    "path": file_path,
                    "mock_path": full_path,
                    "repository": repo_name
                }
                
            except Exception as e:
                logger.error(f"Error in mock from_ipfs: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e),
                    "repository": self._get_repository_name()
                }
        
        # Real implementation for when we have proper credentials
        # Ensure repository exists
        if not self._ensure_repository_exists():
            return {
                "success": False,
                "error": "Failed to ensure repository exists",
                "repository": self._get_repository_name()
            }
        
        try:
            # Create a temporary file to store the IPFS content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Get content from IPFS
            result = subprocess.run(
                ["ipfs", "cat", cid],
                capture_output=True
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}",
                    "repository": self._get_repository_name()
                }
            
            # Write content to temporary file
            with open(temp_path, "wb") as f:
                f.write(result.stdout)
            
            # Determine upload path
            file_path = path or f"ipfs/{cid}"
            
            # Upload to HuggingFace
            repo_name = self._get_repository_name()
            
            try:
                logger.info(f"Uploading to HuggingFace repo {repo_name} (type: {self.repo_type}): {file_path}")
                response = upload_file(
                    path_or_fileobj=temp_path,
                    path_in_repo=file_path,
                    repo_id=repo_name,
                    token=self.token,
                    repo_type=self.repo_type
                )
                
                # Clean up temporary file
                os.unlink(temp_path)
                
                return {
                    "success": True,
                    "url": response.url if hasattr(response, "url") else str(response),
                    "cid": cid,
                    "path": file_path,
                    "repository": repo_name,
                    "type": self.repo_type
                }
            except RepositoryNotFoundError as e:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
                error_info = self._parse_error_message(str(e))
                
                # Special handling for repository not found errors
                if error_info.get("error_type") == "repository_not_found":
                    # If the API is expecting a different repo type, let's try that
                    expected_type = error_info.get("repo_type")
                    if expected_type and expected_type != self.repo_type:
                        logger.warning(f"Repository type mismatch. API expects '{expected_type}' but configured for '{self.repo_type}'. Trying with expected type.")
                        
                        # Switch to the expected repo type and try again
                        original_type = self.repo_type
                        self.repo_type = expected_type
                        self.repo_exists = False
                        self.repo_info = None
                        self.repo_creation_attempted = False
                        
                        try:
                            # Try repository creation again with new type
                            if self._ensure_repository_exists():
                                # Try the upload again
                                try:
                                    response = upload_file(
                                        path_or_fileobj=temp_path,
                                        path_in_repo=file_path,
                                        repo_id=repo_name,
                                        token=self.token,
                                        repo_type=self.repo_type
                                    )
                                    
                                    # Clean up temporary file
                                    if os.path.exists(temp_path):
                                        os.unlink(temp_path)
                                        
                                    logger.info(f"Successfully uploaded to repository with type '{expected_type}'")
                                    
                                    return {
                                        "success": True,
                                        "url": response.url if hasattr(response, "url") else str(response),
                                        "cid": cid,
                                        "path": file_path,
                                        "repository": repo_name,
                                        "type": self.repo_type,
                                        "note": f"Used repository type '{expected_type}' instead of configured '{original_type}'"
                                    }
                                except Exception as upload_error:
                                    # If upload fails, revert back to original repo type
                                    self.repo_type = original_type
                                    
                                    # Clean up temporary file
                                    if os.path.exists(temp_path):
                                        os.unlink(temp_path)
                                        
                                    logger.error(f"Failed upload with expected type '{expected_type}': {upload_error}")
                                    
                                    # Continue to return the original error
                            else:
                                # Revert back to original repo type
                                self.repo_type = original_type
                                logger.error(f"Failed to create repository with type '{expected_type}'")
                        except Exception as type_error:
                            # Revert back to original repo type
                            self.repo_type = original_type
                            logger.error(f"Error trying with expected type '{expected_type}': {type_error}")
                
                return {
                    "success": False,
                    "error": f"Repository not found or access denied: {repo_name}",
                    "repository": repo_name,
                    "error_details": error_info
                }
                
            except HfHubHTTPError as e:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
                error_info = self._parse_error_message(str(e))
                return {
                    "success": False,
                    "error": f"HuggingFace API error: {str(e)}",
                    "repository": repo_name,
                    "error_details": error_info
                }
                
        except Exception as e:
            logger.error(f"Error transferring from IPFS to HuggingFace: {e}")
            error_info = self._parse_error_message(str(e))
            return {
                "success": False,
                "error": str(e),
                "error_details": error_info,
                "repository": self._get_repository_name()
            }
    
    def list_files(self) -> Dict[str, Any]:
        """
        List files in the HuggingFace repository.
        
        Returns:
            Dict with list of files
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "HuggingFace backend is in simulation mode"
            }
            
        # Ensure repository exists
        if not self._ensure_repository_exists():
            return {
                "success": False,
                "error": "Failed to ensure repository exists",
                "repository": self._get_repository_name()
            }
        
        # If in mock mode, list files from local directory
        if self.mock_mode:
            try:
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_huggingface")
                repo_name = self._get_repository_name()
                repo_dir = os.path.join(mock_dir, repo_name)
                
                if not os.path.isdir(repo_dir):
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"Mock repository directory not found: {repo_dir}",
                        "repository": repo_name
                    }
                
                files = self._list_mock_files(repo_dir)
                
                return {
                    "success": True,
                    "mock": True,
                    "files": files,
                    "count": len(files),
                    "repository": repo_name
                }
                
            except Exception as e:
                logger.error(f"Error listing files from mock repository: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e),
                    "repository": self._get_repository_name()
                }
        
        try:
            repo_name = self._get_repository_name()
            files = self.api.list_repo_files(repo_id=repo_name, repo_type=self.repo_type)
            
            return {
                "success": True,
                "files": files,
                "count": len(files),
                "repository": repo_name
            }
            
        except RepositoryNotFoundError as e:
            error_info = self._parse_error_message(str(e))
            return {
                "success": False,
                "error": f"Repository not found: {repo_name}",
                "repository": repo_name,
                "error_details": error_info
            }
            
        except HfHubHTTPError as e:
            error_info = self._parse_error_message(str(e))
            return {
                "success": False,
                "error": f"HuggingFace API error: {str(e)}",
                "repository": self._get_repository_name(),
                "error_details": error_info
            }
            
        except Exception as e:
            logger.error(f"Error listing files from HuggingFace: {e}")
            return {
                "success": False,
                "error": str(e),
                "repository": self._get_repository_name()
            }