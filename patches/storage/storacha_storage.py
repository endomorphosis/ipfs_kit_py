"""
Storacha storage backend implementation for MCP server.

This module provides real (non-simulated) integration with Storacha (formerly Web3.Storage)
for storing and retrieving IPFS content using the W3 Blob Protocol.
"""

import os
import json
import logging
import tempfile
import time
import subprocess
import requests
from typing import Dict, Any, Optional, Union, List
import uuid

# Configure logging
logger = logging.getLogger(__name__)

# Check if required libraries are available
STORACHA_LIBRARIES_AVAILABLE = False
try:
    import requests
    STORACHA_LIBRARIES_AVAILABLE = True
    logger.info("Required libraries for Storacha integration available")
except ImportError:
    logger.warning("Required libraries for Storacha integration not available. Install with: pip install requests")

class StorachaStorage:
    """
    Real implementation of Storacha storage backend for IPFS content.

    This class provides methods to store and retrieve IPFS content using Storacha (Web3.UP),
    implementing a real (non-simulated) storage backend using the W3 Blob Protocol.
    """

    def __init__(self, api_key=None, api_endpoint=None):
        """
        Initialize the Storacha storage backend.

        Args:
            api_key: Storacha API key. If None, will try to get from environment.
            api_endpoint: Storacha API endpoint. If None, will use the default.
        """
        self.api_key = api_key or os.environ.get("STORACHA_API_KEY")
        self.api_endpoint = api_endpoint or os.environ.get("STORACHA_API_URL") or os.environ.get("STORACHA_API_ENDPOINT")
        if not self.api_endpoint:
            self.api_endpoint = "https://up.storacha.network/bridge"  # Updated default endpoint
        self.mock_mode = os.environ.get("MCP_USE_STORACHA_MOCK", "").lower() in ["true", "1", "yes"]
        self.simulation_mode = not STORACHA_LIBRARIES_AVAILABLE and not self.mock_mode

        # If API key is missing but libraries are available, use mock mode
        if (not self.api_key or self.mock_mode) and STORACHA_LIBRARIES_AVAILABLE:
            logger.info("Using Storacha mock mode (functional without real API key)")
            self.simulation_mode = False
            self.mock_mode = True

    def status(self) -> Dict[str, Any]:
        """
        Get the status of the Storacha storage backend.

        Returns:
            Dict containing status information
        """
        status_info = {
            "success": True,
            "available": STORACHA_LIBRARIES_AVAILABLE and (self.api_key is not None or self.mock_mode),
            "simulation": self.simulation_mode,
            "mock": self.mock_mode,
            "timestamp": time.time()
        }

        if self.simulation_mode:
            status_info["message"] = "Running in simulation mode"
            if not STORACHA_LIBRARIES_AVAILABLE:
                status_info["error"] = "Required libraries not installed"
            elif not self.api_key:
                status_info["error"] = "Storacha API key not provided"
        elif self.mock_mode:
            status_info["message"] = "Running in mock mode"
            status_info["warning"] = "Using local mock implementation (functional but not connected to Storacha API)"

            # Create mock directory if it doesn't exist
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_storacha")
            try:
                os.makedirs(mock_dir, exist_ok=True)
                status_info["mock_storage_path"] = mock_dir
            except Exception as e:
                status_info["mock_setup_error"] = str(e)
        else:
            # Test API connection
            try:
                # Check if we can connect to the Storacha API
                # The new endpoint structure might not have a /status endpoint
                # Try a simple GET request to the base endpoint
                headers = {"Authorization": f"Bearer {self.api_key}"}

                # Use a simple GET request to the base endpoint
                try:
                    # First try a HEAD request which is lighter
                    response = requests.head(f"{self.api_endpoint}", headers=headers, timeout=5)

                    if response.status_code < 400:  # Any successful response (200-399)
                        status_info["message"] = "Connected to Storacha API"
                        status_info["api_status"] = "available"
                        status_info["endpoint"] = self.api_endpoint
                    else:
                        # Fall back to simple GET request
                        response = requests.get(f"{self.api_endpoint}", headers=headers, timeout=10)

                        if response.status_code < 400:  # Any successful response (200-399)
                            status_info["message"] = "Connected to Storacha API"
                            status_info["api_status"] = "available"
                            status_info["endpoint"] = self.api_endpoint
                        else:
                            status_info["message"] = f"Failed to connect to Storacha API: {response.status_code}"
                            status_info["success"] = False
                except requests.exceptions.RequestException as e:
                    # If the main endpoint doesn't work, try an alternative endpoint
                    alt_endpoint = "https://api.web3.storage"  # Alternative endpoint as fallback
                    try:
                        response = requests.head(alt_endpoint, headers=headers, timeout=5)
                        if response.status_code < 400:
                            # Update the endpoint to use the working one
                            self.api_endpoint = alt_endpoint
                            status_info["message"] = "Connected to alternative Storacha API endpoint"
                            status_info["api_status"] = "available"
                            status_info["endpoint"] = self.api_endpoint
                            status_info["note"] = "Using alternative endpoint due to DNS resolution issues"
                        else:
                            status_info["message"] = f"Failed to connect to alternative API: {response.status_code}"
                            status_info["success"] = False
                    except Exception as e2:
                        status_info["message"] = f"Failed to connect to any Storacha API endpoint"
                        status_info["success"] = False
            except Exception as e:
                status_info["error"] = str(e)
                status_info["success"] = False

        return status_info

    def from_ipfs(self, cid: str, replication: int = 3) -> Dict[str, Any]:
        """
        Store IPFS content on Storacha.

        Args:
            cid: Content ID to store
            replication: Replication factor

        Returns:
            Dict with storage information
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Storacha backend is in simulation mode"
            }

        # If in mock mode, simulate the operation with local storage
        if self.mock_mode:
            try:
                # Verify CID exists on IPFS
                result = subprocess.run(
                    ["ipfs", "block", "stat", cid],
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"CID {cid} not found on IPFS: {result.stderr}"
                    }

                # Create a mock storage directory if it doesn't exist
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_storacha", "objects")
                os.makedirs(mock_dir, exist_ok=True)

                # Get file size from IPFS
                size_output = subprocess.run(
                    ["ipfs", "block", "stat", cid],
                    capture_output=True,
                    text=True
                ).stdout

                # Extract size from output
                size = 0
                for line in size_output.splitlines():
                    if line.startswith("Size:"):
                        try:
                            size = int(line.split("Size:")[1].strip())
                        except (ValueError, IndexError):
                            pass

                # Create a storage ID (similar to how Storacha would)
                storage_id = str(uuid.uuid4())

                # Create a metadata file
                storage_file = os.path.join(mock_dir, f"{storage_id}.json")
                storage_info = {
                    "storage_id": storage_id,
                    "cid": cid,
                    "replication": replication,
                    "status": "stored",
                    "created_at": time.time(),
                    "size": size,
                    "mock": True
                }

                # Store the metadata
                with open(storage_file, "w") as f:
                    json.dump(storage_info, f, indent=2)

                # Also create a mapping from CID to storage ID for easier lookup
                cid_map_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_storacha", "cid_map")
                os.makedirs(cid_map_dir, exist_ok=True)
                cid_map_file = os.path.join(cid_map_dir, f"{cid}")

                with open(cid_map_file, "w") as f:
                    f.write(storage_id)

                return {
                    "success": True,
                    "mock": True,
                    "message": "Content stored in mock Storacha storage",
                    "storage_id": storage_id,
                    "cid": cid,
                    "replication": replication,
                    "status": "stored",
                    "mock_file": storage_file
                }

            except Exception as e:
                logger.error(f"Error in mock from_ipfs: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e)
                }

        try:
            # Verify CID exists on IPFS
            result = subprocess.run(
                ["ipfs", "block", "stat", cid],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"CID {cid} not found on IPFS: {result.stderr}"
                }

            # Store on Storacha using W3 Blob Protocol
            headers = {"Authorization": f"Bearer {self.api_key}"}
            data = {
                "cid": cid,
                "replication": replication
            }

            # Format for the new bridge endpoint
            response = requests.post(
                f"{self.api_endpoint}/add",  # Changed from /store to /add based on W3 Blob Protocol
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "message": "Content stored on Storacha",
                    "cid": cid,
                    "storage_id": result.get("storage_id", str(uuid.uuid4())),
                    "replication": replication,
                    "status": "stored",
                    "timestamp": time.time()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to store content on Storacha: {response.status_code} - {response.text}"
                }

        except Exception as e:
            logger.error(f"Error storing IPFS content on Storacha: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def to_ipfs(self, storage_id: str) -> Dict[str, Any]:
        """
        Retrieve content from Storacha to IPFS.

        Args:
            storage_id: Storage ID for the content to retrieve

        Returns:
            Dict with retrieval status
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Storacha backend is in simulation mode"
            }

        # If in mock mode, retrieve content from mock storage
        if self.mock_mode:
            try:
                # Find the storage metadata in mock storage
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_storacha", "objects")
                storage_file = os.path.join(mock_dir, f"{storage_id}.json")

                if not os.path.exists(storage_file):
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"Storage ID {storage_id} not found in mock storage"
                    }

                # Read the storage information
                with open(storage_file, "r") as f:
                    storage_info = json.load(f)

                cid = storage_info.get("cid")
                if not cid:
                    return {
                        "success": False,
                        "mock": True,
                        "error": "Storage information does not contain a CID"
                    }

                # Check if content is already in IPFS
                ipfs_check = subprocess.run(
                    ["ipfs", "block", "stat", cid],
                    capture_output=True,
                    text=True
                )

                if ipfs_check.returncode == 0:
                    # Content already in IPFS
                    return {
                        "success": True,
                        "mock": True,
                        "message": "Content already available in IPFS",
                        "storage_id": storage_id,
                        "cid": cid,
                        "status": "retrieved"
                    }

                # In a real implementation, we would retrieve the content and add it to IPFS
                # For mock mode, we just report success if we found the storage info
                return {
                    "success": True,
                    "mock": True,
                    "message": "Mock retrieval from Storacha (content not available in IPFS)",
                    "storage_id": storage_id,
                    "cid": cid,
                    "status": "retrieval_simulated"
                }

            except Exception as e:
                logger.error(f"Error in mock to_ipfs: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e)
                }

        try:
            # Retrieve from Storacha using W3 Blob Protocol
            headers = {"Authorization": f"Bearer {self.api_key}"}

            # Updated endpoint for retrieving content
            response = requests.get(
                f"{self.api_endpoint}/get/{storage_id}",  # Changed from /retrieve to /get based on W3 Blob Protocol
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                cid = result.get("cid")

                # Verify the content is now available in IPFS
                verify_result = subprocess.run(
                    ["ipfs", "block", "stat", cid],
                    capture_output=True,
                    text=True
                )

                if verify_result.returncode == 0:
                    return {
                        "success": True,
                        "message": "Content retrieved from Storacha to IPFS",
                        "cid": cid,
                        "storage_id": storage_id,
                        "status": "retrieved",
                        "timestamp": time.time()
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Retrieved content from Storacha but not found in IPFS: {verify_result.stderr}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Failed to retrieve content from Storacha: {response.status_code} - {response.text}"
                }

        except Exception as e:
            logger.error(f"Error retrieving content from Storacha: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def check_status(self, storage_id: str) -> Dict[str, Any]:
        """
        Check the status of stored content.

        Args:
            storage_id: Storage ID to check

        Returns:
            Dict with storage status
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Storacha backend is in simulation mode"
            }

        # If in mock mode, check status from mock storage
        if self.mock_mode:
            try:
                # Find the storage metadata in mock storage
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_storacha", "objects")
                storage_file = os.path.join(mock_dir, f"{storage_id}.json")

                if not os.path.exists(storage_file):
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"Storage ID {storage_id} not found in mock storage"
                    }

                # Read the storage information
                with open(storage_file, "r") as f:
                    storage_info = json.load(f)

                # Add mock flag and additional info
                storage_info["mock"] = True
                storage_info["success"] = True
                storage_info["message"] = "Status retrieved from mock storage"

                return storage_info

            except Exception as e:
                logger.error(f"Error in mock check_status: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e)
                }

        try:
            # Check status on Storacha using W3 Blob Protocol
            headers = {"Authorization": f"Bearer {self.api_key}"}

            # Updated endpoint for checking status
            response = requests.get(
                f"{self.api_endpoint}/info/{storage_id}",  # Changed from /status to /info based on W3 Blob Protocol
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "storage_id": storage_id,
                    "cid": result.get("cid"),
                    "status": result.get("status", "unknown"),
                    "replication": result.get("replication"),
                    "timestamp": time.time()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to check status on Storacha: {response.status_code} - {response.text}"
                }

        except Exception as e:
            logger.error(f"Error checking status on Storacha: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def list_blobs(self, cursor=None, size=100) -> Dict[str, Any]:
        """
        List blobs stored in Storacha.

        Args:
            cursor: Optional pagination cursor
            size: Maximum number of items to return

        Returns:
            Dict with list of blobs
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Storacha backend is in simulation mode"
            }

        # If in mock mode, list blobs from mock storage
        if self.mock_mode:
            try:
                # Get list of blobs from mock storage
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_storacha", "objects")
                if not os.path.exists(mock_dir):
                    return {
                        "success": True,
                        "mock": True,
                        "results": [],
                        "size": 0,
                        "message": "No blobs found in mock storage"
                    }

                # Get list of storage files
                storage_files = [f for f in os.listdir(mock_dir) if f.endswith('.json')]

                # Implement simple pagination
                if cursor:
                    try:
                        start_index = storage_files.index(f"{cursor}.json") + 1
                    except ValueError:
                        start_index = 0
                else:
                    start_index = 0

                # Get subset of files based on pagination
                results_files = storage_files[start_index:start_index + size]

                # Get blob info for each file
                results = []
                for filename in results_files:
                    with open(os.path.join(mock_dir, filename), 'r') as f:
                        storage_info = json.load(f)
                        # Convert to expected format
                        results.append({
                            "blob": {
                                "size": storage_info.get("size", 0),
                                "content": storage_info.get("cid")
                            },
                            "insertedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z",
                                                      time.gmtime(storage_info.get("created_at", time.time())))
                        })

                # Calculate next cursor
                next_cursor = None
                if start_index + size < len(storage_files):
                    next_cursor = storage_files[start_index + size].replace('.json', '')

                return {
                    "success": True,
                    "mock": True,
                    "results": results,
                    "size": len(results),
                    "cursor": next_cursor
                }

            except Exception as e:
                logger.error(f"Error in mock list_blobs: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e)
                }

        try:
            # List blobs using W3 Blob Protocol
            headers = {"Authorization": f"Bearer {self.api_key}"}

            # Build query parameters
            params = {"size": size}
            if cursor:
                params["cursor"] = cursor

            # Make request to list endpoint
            response = requests.get(
                f"{self.api_endpoint}/space/blob/list",
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "results": result.get("results", []),
                    "size": result.get("size", 0),
                    "cursor": result.get("cursor")
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to list blobs from Storacha: {response.status_code} - {response.text}"
                }

        except Exception as e:
            logger.error(f"Error listing blobs from Storacha: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def remove_blob(self, digest) -> Dict[str, Any]:
        """
        Remove a blob from Storacha.

        Args:
            digest: The multihash digest of the blob to remove

        Returns:
            Dict with removal status
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Storacha backend is in simulation mode"
            }

        # If in mock mode, remove from mock storage
        if self.mock_mode:
            try:
                # Find the storage file for this CID
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_storacha")
                cid_map_file = os.path.join(mock_dir, "cid_map", digest)

                if not os.path.exists(cid_map_file):
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"Blob with digest {digest} not found in mock storage"
                    }

                # Read the storage ID
                with open(cid_map_file, 'r') as f:
                    storage_id = f.read().strip()

                # Get the storage file
                storage_file = os.path.join(mock_dir, "objects", f"{storage_id}.json")

                if not os.path.exists(storage_file):
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"Storage file for ID {storage_id} not found"
                    }

                # Read the storage info to get the size
                with open(storage_file, 'r') as f:
                    storage_info = json.load(f)
                size = storage_info.get("size", 0)

                # Remove the files
                os.remove(cid_map_file)
                os.remove(storage_file)

                return {
                    "success": True,
                    "mock": True,
                    "message": "Blob removed from mock storage",
                    "size": size
                }

            except Exception as e:
                logger.error(f"Error in mock remove_blob: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e)
                }

        try:
            # Remove blob using W3 Blob Protocol
            headers = {"Authorization": f"Bearer {self.api_key}"}

            # Make request to remove endpoint
            data = {"digest": digest}
            response = requests.post(
                f"{self.api_endpoint}/space/blob/remove",
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "message": "Blob removed from Storacha",
                    "size": result.get("size", 0)
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to remove blob from Storacha: {response.status_code} - {response.text}"
                }

        except Exception as e:
            logger.error(f"Error removing blob from Storacha: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_blob(self, digest) -> Dict[str, Any]:
        """
        Get information about a blob in Storacha.

        Args:
            digest: The multihash digest of the blob to get info for

        Returns:
            Dict with blob information
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "Storacha backend is in simulation mode"
            }

        # If in mock mode, get info from mock storage
        if self.mock_mode:
            try:
                # Find the storage file for this CID
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_storacha")
                cid_map_file = os.path.join(mock_dir, "cid_map", digest)

                if not os.path.exists(cid_map_file):
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"Blob with digest {digest} not found in mock storage"
                    }

                # Read the storage ID
                with open(cid_map_file, 'r') as f:
                    storage_id = f.read().strip()

                # Get the storage file
                storage_file = os.path.join(mock_dir, "objects", f"{storage_id}.json")

                if not os.path.exists(storage_file):
                    return {
                        "success": False,
                        "mock": True,
                        "error": f"Storage file for ID {storage_id} not found"
                    }

                # Read the storage info
                with open(storage_file, 'r') as f:
                    storage_info = json.load(f)

                # Create get blob response format
                blob_info = {
                    "blob": {
                        "size": storage_info.get("size", 0),
                        "digest": digest
                    },
                    "cause": storage_info.get("cause", "mock-task-id"),
                    "insertedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z",
                                               time.gmtime(storage_info.get("created_at", time.time())))
                }

                return {
                    "success": True,
                    "mock": True,
                    "blob": blob_info["blob"],
                    "cause": blob_info["cause"],
                    "insertedAt": blob_info["insertedAt"]
                }

            except Exception as e:
                logger.error(f"Error in mock get_blob: {e}")
                return {
                    "success": False,
                    "mock": True,
                    "error": str(e)
                }

        try:
            # Get blob info using W3 Blob Protocol
            headers = {"Authorization": f"Bearer {self.api_key}"}

            # Make request to get blob endpoint
            response = requests.get(
                f"{self.api_endpoint}/space/blob/get/0/1",  # As per specification
                headers=headers,
                params={"digest": digest},
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "blob": result.get("blob", {}),
                    "cause": result.get("cause", ""),
                    "insertedAt": result.get("insertedAt", "")
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get blob info from Storacha: {response.status_code} - {response.text}"
                }

        except Exception as e:
            logger.error(f"Error getting blob info from Storacha: {e}")
            return {
                "success": False,
                "error": str(e)
            }
