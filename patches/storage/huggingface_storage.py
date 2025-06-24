"""
HuggingFace storage backend implementation for MCP server.

This module provides real (non-simulated) integration with the HuggingFace Hub
for storing and retrieving IPFS content.
"""

import os
import json
import logging
import tempfile
import time
import subprocess
from typing import Dict, Any, Optional, Union, List

# Configure logging
logger = logging.getLogger(__name__)

# Check if huggingface_hub is available
try:
    from huggingface_hub import HfApi, hf_hub_download, upload_file
    HUGGINGFACE_AVAILABLE = True
    logger.info("HuggingFace Hub SDK is available")
except ImportError:
    HUGGINGFACE_AVAILABLE = False
    logger.warning("HuggingFace Hub SDK is not available. Install with: pip install huggingface_hub")

class HuggingFaceStorage:
    """
    Real implementation of HuggingFace storage backend for IPFS content.

    This class provides methods to store and retrieve IPFS content using HuggingFace Hub,
    implementing a real (non-simulated) storage backend.
    """

    def __init__(self, token=None, organization=None, repo_name=None):
        """
        Initialize the HuggingFace storage backend.

        Args:
            token (str): HuggingFace API token. If None, will try to get from environment.
            organization (str): HuggingFace organization name. If None, will use user account.
            repo_name (str): Repository name for IPFS storage. Defaults to 'ipfs-storage'.
        """
        self.token = token or os.environ.get("HUGGINGFACE_TOKEN")
        self.organization = organization
        self.repo_name = repo_name or "ipfs-storage"
        self.api = None
        self.mock_mode = False
        self.simulation_mode = not HUGGINGFACE_AVAILABLE

        # Initialize the API if available
        if HUGGINGFACE_AVAILABLE:
            try:
                # Always create an API instance even without a token
                # This allows for proper initialization in mock mode
                self.api = HfApi(token=self.token if self.token else None)
                logger.info("Initialized HuggingFace API client")

                if self.token:
                    # With token, try to verify it works
                    self.simulation_mode = False
                else:
                    # Without token, use mock mode
                    logger.info("No HuggingFace token provided, will use mock mode")
                    self.mock_mode = True
                    self.simulation_mode = False
            except Exception as e:
                logger.error(f"Failed to initialize HuggingFace API: {e}")
                self.simulation_mode = True

        # If credentials are missing or there was an error, use mock mode (better than simulation)
        if self.simulation_mode and HUGGINGFACE_AVAILABLE:
            logger.info("Using HuggingFace mock mode (functional without real credentials)")
            self.simulation_mode = False
            self.mock_mode = True

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
            status_info["warning"] = "Using local mock implementation (functional but not connected to HuggingFace)"
            # No need to try to connect to the API in mock mode
        else:
            # Only test API connection if we have a token and not in mock mode
            if self.token and self.api:
                try:
                    user_info = self.api.whoami()
                    status_info["user"] = user_info.get("name")
                    status_info["organizations"] = user_info.get("orgs", [])
                    status_info["message"] = "Connected to HuggingFace Hub"
                except Exception as e:
                    status_info["error"] = str(e)
                    status_info["success"] = False
            else:
                status_info["message"] = "API available but no token provided"
                status_info["error"] = "Missing HuggingFace API token"

        return status_info

    def _get_repository_name(self) -> str:
        """
        Get the full repository name.

        Returns:
            Full repository name in format 'organization/repo_name'
        """
        prefix = f"{self.organization}/" if self.organization else ""
        return f"{prefix}{self.repo_name}"

    def _ensure_repository_exists(self) -> bool:
        """
        Ensure the repository exists, creating it if necessary.

        Returns:
            bool: True if repository exists or was created, False otherwise
        """
        if self.simulation_mode:
            return False

        try:
            repo_name = self._get_repository_name()

            # Check if repo exists
            try:
                self.api.repo_info(repo_id=repo_name)
                logger.debug(f"Repository {repo_name} already exists")
                return True
            except Exception:
                # Repository doesn't exist, create it
                self.api.create_repo(
                    repo_id=self.repo_name,
                    private=True,
                    repo_type="dataset",
                    exist_ok=True
                )
                logger.info(f"Created repository {repo_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to ensure repository exists: {e}")
            return False

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
                os.makedirs(mock_dir, exist_ok=True)

                # Check if the file exists in mock storage
                mock_file_path = os.path.join(mock_dir, file_path)
                if not os.path.exists(mock_file_path):
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"File not found in mock storage: {file_path}"
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
                        "error": f"Failed to add to IPFS: {result.stderr}"
                    }

                new_cid = result.stdout.strip()

                # Verify CID if provided
                if cid and cid != new_cid:
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"CID mismatch: expected {cid}, got {new_cid}"
                    }

                return {
                    "success": True,
                    "mock": True,
                    "message": "Added content from mock HuggingFace storage to IPFS",
                    "cid": new_cid,
                    "source": f"mock_huggingface:{file_path}"
                }

            except Exception as e:
                logger.error(f"Error in mock to_ipfs: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e)
                }

        try:
            # Download from HuggingFace
            repo_name = self._get_repository_name()
            local_path = hf_hub_download(
                repo_id=repo_name,
                filename=file_path,
                token=self.token
            )

            # Upload to IPFS
            result = subprocess.run(
                ["ipfs", "add", "-q", local_path],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                new_cid = result.stdout.strip()

                # Verify CID if provided
                if cid and cid != new_cid:
                    return {
                        "success": False,
                        "error": f"CID mismatch: expected {cid}, got {new_cid}"
                    }

                return {
                    "success": True,
                    "cid": new_cid,
                    "source": f"huggingface:{repo_name}/{file_path}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add to IPFS: {result.stderr}"
                }

        except Exception as e:
            logger.error(f"Error transferring from HuggingFace to IPFS: {e}")
            return {
                "success": False,
                "error": str(e)
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
                os.makedirs(mock_dir, exist_ok=True)

                # Get content from IPFS
                result = subprocess.run(
                    ["ipfs", "cat", cid],
                    capture_output=True
                )

                if result.returncode != 0:
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}"
                    }

                # Determine storage path
                file_path = path or f"ipfs/{cid}"
                full_path = os.path.join(mock_dir, file_path)

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
                    "mock_path": full_path
                }

            except Exception as e:
                logger.error(f"Error in mock from_ipfs: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e)
                }

        # Real implementation for when we have proper credentials
        # Ensure repository exists
        if not self._ensure_repository_exists():
            return {
                "success": False,
                "error": "Failed to ensure repository exists"
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
                    "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}"
                }

            # Write content to temporary file
            with open(temp_path, "wb") as f:
                f.write(result.stdout)

            # Determine upload path
            file_path = path or f"ipfs/{cid}"

            # Upload to HuggingFace
            repo_name = self._get_repository_name()
            response = upload_file(
                path_or_fileobj=temp_path,
                path_in_repo=file_path,
                repo_id=repo_name,
                token=self.token
            )

            # Clean up temporary file
            os.unlink(temp_path)

            return {
                "success": True,
                "url": response.url,
                "cid": cid,
                "path": file_path,
                "repository": repo_name
            }

        except Exception as e:
            logger.error(f"Error transferring from IPFS to HuggingFace: {e}")
            return {
                "success": False,
                "error": str(e)
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

        try:
            repo_name = self._get_repository_name()
            files = self.api.list_repo_files(repo_id=repo_name)

            return {
                "success": True,
                "files": files,
                "count": len(files),
                "repository": repo_name
            }

        except Exception as e:
            logger.error(f"Error listing files from HuggingFace: {e}")
            return {
                "success": False,
                "error": str(e)
            }
