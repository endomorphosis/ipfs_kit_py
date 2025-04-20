"""
Enhanced Storacha Storage Implementation

This module provides an improved implementation of the Storacha storage backend
with robust error handling, automatic endpoint failover, and enhanced features.
"""

import os
import json
import time
import logging
import tempfile
import subprocess
import requests
import hashlib
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from urllib.parse import urlparse

# Configure logging
logger = logging.getLogger(__name__)

# Check for required dependencies
try:
    import requests
    STORACHA_LIBRARIES_AVAILABLE = True
except ImportError:
    STORACHA_LIBRARIES_AVAILABLE = False
    logger.warning("Required libraries for Storacha not available. Install with: pip install requests")

# Import our connection manager
try:
    from mcp_extensions.storacha_connection import StorachaConnectionManager
    ENHANCED_CONNECTION_AVAILABLE = True
    logger.info("Enhanced Storacha connection manager available")
except ImportError:
    ENHANCED_CONNECTION_AVAILABLE = False
    logger.warning("Enhanced Storacha connection manager not available")

class EnhancedStorachaStorage:
    """
    Enhanced Storacha storage backend implementation.
    
    This class provides methods to interact with the Storacha service for storing
    and retrieving content, with robust error handling and connection management.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        api_endpoint: Optional[str] = None,
        mock_storage_path: Optional[str] = None
    ):
        """
        Initialize the Storacha storage implementation.
        
        Args:
            api_key: Storacha API key
            api_endpoint: Storacha API endpoint
            mock_storage_path: Path for mock storage (when running in mock mode)
        """
        self.api_key = api_key or os.environ.get("STORACHA_API_KEY")
        self.api_endpoint = api_endpoint or os.environ.get("STORACHA_API_URL") or os.environ.get("STORACHA_API_ENDPOINT")
        
        # Check if we have valid credentials for real operation
        self.mock_mode = not self.api_key or self.api_key.startswith("mock_") or not STORACHA_LIBRARIES_AVAILABLE
        
        # Set up mock storage if needed
        if self.mock_mode:
            # Create a directory for mock storage
            if mock_storage_path:
                self.mock_storage_path = mock_storage_path
            else:
                self.mock_storage_path = os.path.expanduser("~/.ipfs_kit/mock_storacha_storage")
            
            # Ensure the mock storage directory exists
            os.makedirs(self.mock_storage_path, exist_ok=True)
            logger.info(f"Using mock storage at {self.mock_storage_path}")
        
        # Initialize connection manager if available and not in mock mode
        self.connection_manager = None
        if not self.mock_mode and ENHANCED_CONNECTION_AVAILABLE:
            try:
                self.connection_manager = StorachaConnectionManager(
                    api_key=self.api_key,
                    api_endpoint=self.api_endpoint,
                    validate_endpoints=True  # Validate on initialization
                )
                if self.connection_manager.working_endpoint:
                    self.working_endpoint = self.connection_manager.working_endpoint
                    logger.info(f"Successfully connected to Storacha API at {self.working_endpoint}")
                else:
                    logger.warning("Failed to establish connection to any Storacha endpoint")
                    # Fall back to mock mode if we can't connect
                    self.mock_mode = True
                    
                    # Set up mock storage if needed
                    self.mock_storage_path = os.path.expanduser("~/.ipfs_kit/mock_storacha_storage")
                    os.makedirs(self.mock_storage_path, exist_ok=True)
                    logger.info(f"Falling back to mock storage at {self.mock_storage_path}")
            except Exception as e:
                logger.error(f"Error initializing Storacha connection manager: {e}")
                # Fall back to mock mode if connection manager fails
                self.mock_mode = True
                self.mock_storage_path = os.path.expanduser("~/.ipfs_kit/mock_storacha_storage")
                os.makedirs(self.mock_storage_path, exist_ok=True)
        else:
            # If not using enhanced connection manager, set up basic connection for real mode
            if not self.mock_mode:
                # Create session for connection pooling
                self.session = requests.Session()
                self.session.headers.update({
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json"
                })
                self.working_endpoint = self.api_endpoint
    
    def status(self) -> Dict[str, Any]:
        """
        Get the status of the Storacha storage backend.
        
        Returns:
            Dict with status information
        """
        if self.mock_mode:
            # Count objects in mock storage
            try:
                object_count = len(os.listdir(self.mock_storage_path))
            except:
                object_count = 0
            
            return {
                "success": True,
                "simulation": False,  # Not a simulation, it's a mock
                "mock": True,
                "message": "Using mock Storacha storage",
                "mock_storage_path": self.mock_storage_path,
                "mock_object_count": object_count
            }
        
        try:
            # Use connection manager if available
            if self.connection_manager:
                # Get connection manager status
                conn_status = self.connection_manager.get_status()
                
                # Try a health check request
                try:
                    response = self.connection_manager.send_request("GET", "health")
                    health_data = response.json() if response.status_code == 200 else None
                except Exception as e:
                    logger.warning(f"Health check failed: {e}")
                    health_data = None
                
                return {
                    "success": True,
                    "simulation": False,
                    "mock": False,
                    "message": "Connected to real Storacha API",
                    "endpoint": conn_status["working_endpoint"],
                    "endpoints": conn_status["endpoints"],
                    "service_info": health_data
                }
            else:
                # Without connection manager, do a basic health check
                try:
                    response = self.session.get(f"{self.working_endpoint}/health", timeout=10)
                    if response.status_code == 200:
                        return {
                            "success": True,
                            "simulation": False,
                            "mock": False,
                            "message": "Connected to real Storacha API",
                            "endpoint": self.working_endpoint,
                            "service_info": response.json()
                        }
                    else:
                        return {
                            "success": False,
                            "simulation": False,
                            "mock": False,
                            "message": "Connected to Storacha API but health check failed",
                            "endpoint": self.working_endpoint,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "simulation": False,
                        "mock": False,
                        "message": "Error connecting to Storacha API",
                        "endpoint": self.working_endpoint,
                        "error": str(e)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error checking Storacha storage status: {e}"
            }
    
    def from_ipfs(self, cid: str, replication: int = 3) -> Dict[str, Any]:
        """
        Store IPFS content in Storacha.
        
        Args:
            cid: Content ID to store
            replication: Replication factor
            
        Returns:
            Dict with storage result
        """
        logger.info(f"Storing CID {cid} in Storacha (replication: {replication})")
        
        if self.mock_mode:
            return self._mock_from_ipfs(cid, replication)
        
        try:
            # First, get the content from IPFS
            try:
                process = subprocess.run(
                    ["ipfs", "cat", cid],
                    capture_output=True,
                    timeout=60
                )
                
                if process.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Error retrieving content from IPFS: {process.stderr.decode('utf-8', errors='replace')}"
                    }
                
                content_data = process.stdout
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error running IPFS command: {e}"
                }
            
            # Calculate the IPFS CID to verify later
            try:
                # Get the real CID using ipfs-only-hash
                verify_process = subprocess.run(
                    ["ipfs", "add", "--only-hash", "-Q"],
                    input=content_data,
                    capture_output=True,
                    timeout=30
                )
                
                if verify_process.returncode == 0:
                    verified_cid = verify_process.stdout.decode('utf-8').strip()
                    if verified_cid != cid:
                        logger.warning(f"CID mismatch: requested {cid}, calculated {verified_cid}")
                else:
                    logger.warning(f"Could not verify CID: {verify_process.stderr.decode('utf-8', errors='replace')}")
                    verified_cid = cid
            except Exception as e:
                logger.warning(f"Error verifying CID: {e}")
                verified_cid = cid
            
            # Upload to Storacha using the appropriate method
            if self.connection_manager:
                try:
                    # Create multipart form data
                    files = {
                        'file': (f"{cid}.bin", content_data)
                    }
                    
                    # Add metadata about IPFS origin
                    metadata = {
                        "source": "ipfs",
                        "ipfs_cid": cid,
                        "replication": replication
                    }
                    
                    # Send request via connection manager
                    response = self.connection_manager.send_request(
                        "POST", 
                        "upload", 
                        files=files,
                        data={"metadata": json.dumps(metadata)}
                    )
                    
                    if response.status_code == 200 or response.status_code == 201:
                        data = response.json()
                        return {
                            "success": True,
                            "storage_id": data.get("cid", data.get("id", data.get("hash", ""))),
                            "size": len(content_data),
                            "replication": replication,
                            "timestamp": time.time(),
                            "ipfs_cid": cid,
                            "verified_cid": verified_cid,
                            "endpoint": self.connection_manager.working_endpoint
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error uploading to Storacha: {e}"
                    }
            else:
                # Without connection manager, use regular requests
                try:
                    files = {
                        'file': (f"{cid}.bin", content_data)
                    }
                    
                    # Add metadata about IPFS origin
                    metadata = {
                        "source": "ipfs",
                        "ipfs_cid": cid,
                        "replication": replication
                    }
                    
                    response = self.session.post(
                        f"{self.working_endpoint}/upload",
                        files=files,
                        data={"metadata": json.dumps(metadata)},
                        timeout=60
                    )
                    
                    if response.status_code == 200 or response.status_code == 201:
                        data = response.json()
                        return {
                            "success": True,
                            "storage_id": data.get("cid", data.get("id", data.get("hash", ""))),
                            "size": len(content_data),
                            "replication": replication,
                            "timestamp": time.time(),
                            "ipfs_cid": cid,
                            "verified_cid": verified_cid,
                            "endpoint": self.working_endpoint
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error uploading to Storacha: {e}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error storing content in Storacha: {e}"
            }
    
    def to_ipfs(self, storage_id: str) -> Dict[str, Any]:
        """
        Retrieve content from Storacha and store it in IPFS.
        
        Args:
            storage_id: Storage ID to retrieve
            
        Returns:
            Dict with retrieval result
        """
        logger.info(f"Retrieving storage ID {storage_id} from Storacha to IPFS")
        
        if self.mock_mode:
            return self._mock_to_ipfs(storage_id)
        
        try:
            # Download content from Storacha
            if self.connection_manager:
                try:
                    # Send request via connection manager
                    response = self.connection_manager.send_request(
                        "GET", 
                        f"download/{storage_id}"
                    )
                    
                    if response.status_code != 200:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                    
                    content_data = response.content
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error downloading from Storacha: {e}"
                    }
            else:
                # Without connection manager, use regular requests
                try:
                    response = self.session.get(
                        f"{self.working_endpoint}/download/{storage_id}",
                        timeout=60
                    )
                    
                    if response.status_code != 200:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                    
                    content_data = response.content
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error downloading from Storacha: {e}"
                    }
            
            # Store content in IPFS
            try:
                # Create a temporary file for the content
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(content_data)
                    temp_file_path = temp_file.name
                
                # Add to IPFS
                process = subprocess.run(
                    ["ipfs", "add", "-Q", temp_file_path],
                    capture_output=True,
                    timeout=60
                )
                
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                
                if process.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Error adding content to IPFS: {process.stderr.decode('utf-8', errors='replace')}"
                    }
                
                cid = process.stdout.decode('utf-8').strip()
                
                return {
                    "success": True,
                    "cid": cid,
                    "size": len(content_data),
                    "timestamp": time.time(),
                    "storage_id": storage_id
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error storing content in IPFS: {e}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error retrieving content from Storacha: {e}"
            }
    
    def check_status(self, storage_id: str) -> Dict[str, Any]:
        """
        Check the status of stored content.
        
        Args:
            storage_id: Storage ID to check
            
        Returns:
            Dict with status information
        """
        logger.info(f"Checking status for storage ID {storage_id}")
        
        if self.mock_mode:
            return self._mock_check_status(storage_id)
        
        try:
            # Get blob info from Storacha
            if self.connection_manager:
                try:
                    # Send request via connection manager
                    response = self.connection_manager.send_request(
                        "GET", 
                        f"status/{storage_id}"
                    )
                    
                    if response.status_code != 200:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                    
                    data = response.json()
                    return {
                        "success": True,
                        "storage_id": storage_id,
                        "status": data.get("status", "unknown"),
                        "size": data.get("size", 0),
                        "created": data.get("created", time.time()),
                        "deals": data.get("deals", []),
                        "pins": data.get("pins", []),
                        "endpoint": self.connection_manager.working_endpoint
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error checking status in Storacha: {e}"
                    }
            else:
                # Without connection manager, use regular requests
                try:
                    response = self.session.get(
                        f"{self.working_endpoint}/status/{storage_id}",
                        timeout=30
                    )
                    
                    if response.status_code != 200:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                    
                    data = response.json()
                    return {
                        "success": True,
                        "storage_id": storage_id,
                        "status": data.get("status", "unknown"),
                        "size": data.get("size", 0),
                        "created": data.get("created", time.time()),
                        "deals": data.get("deals", []),
                        "pins": data.get("pins", []),
                        "endpoint": self.working_endpoint
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error checking status in Storacha: {e}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error checking storage status: {e}"
            }
    
    def list_blobs(self, cursor: Optional[str] = None, size: int = 100) -> Dict[str, Any]:
        """
        List blobs stored in Storacha.
        
        Args:
            cursor: Pagination cursor
            size: Maximum number of items to return
            
        Returns:
            Dict with list of blobs
        """
        logger.info(f"Listing blobs from Storacha (cursor: {cursor}, size: {size})")
        
        if self.mock_mode:
            return self._mock_list_blobs(cursor, size)
        
        try:
            # Prepare query parameters
            params = {"size": size}
            if cursor:
                params["cursor"] = cursor
            
            # Get list from Storacha
            if self.connection_manager:
                try:
                    # Send request via connection manager
                    response = self.connection_manager.send_request(
                        "GET", 
                        "list",
                        params=params
                    )
                    
                    if response.status_code != 200:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                    
                    data = response.json()
                    return {
                        "success": True,
                        "blobs": data.get("blobs", []),
                        "next_cursor": data.get("next", None),
                        "endpoint": self.connection_manager.working_endpoint
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error listing blobs from Storacha: {e}"
                    }
            else:
                # Without connection manager, use regular requests
                try:
                    response = self.session.get(
                        f"{self.working_endpoint}/list",
                        params=params,
                        timeout=30
                    )
                    
                    if response.status_code != 200:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                    
                    data = response.json()
                    return {
                        "success": True,
                        "blobs": data.get("blobs", []),
                        "next_cursor": data.get("next", None),
                        "endpoint": self.working_endpoint
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error listing blobs from Storacha: {e}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error listing blobs: {e}"
            }
    
    def get_blob(self, digest: str) -> Dict[str, Any]:
        """
        Get information about a blob in Storacha.
        
        Args:
            digest: The multihash digest of the blob
            
        Returns:
            Dict with blob information
        """
        logger.info(f"Getting blob info for digest {digest}")
        
        if self.mock_mode:
            return self._mock_get_blob(digest)
        
        try:
            # Get blob info from Storacha
            if self.connection_manager:
                try:
                    # Send request via connection manager
                    response = self.connection_manager.send_request(
                        "GET", 
                        f"blob/{digest}"
                    )
                    
                    if response.status_code != 200:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                    
                    data = response.json()
                    return {
                        "success": True,
                        "digest": digest,
                        "size": data.get("size", 0),
                        "created": data.get("created", time.time()),
                        "status": data.get("status", "unknown"),
                        "endpoint": self.connection_manager.working_endpoint
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error getting blob info from Storacha: {e}"
                    }
            else:
                # Without connection manager, use regular requests
                try:
                    response = self.session.get(
                        f"{self.working_endpoint}/blob/{digest}",
                        timeout=30
                    )
                    
                    if response.status_code != 200:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                    
                    data = response.json()
                    return {
                        "success": True,
                        "digest": digest,
                        "size": data.get("size", 0),
                        "created": data.get("created", time.time()),
                        "status": data.get("status", "unknown"),
                        "endpoint": self.working_endpoint
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error getting blob info from Storacha: {e}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting blob info: {e}"
            }
    
    def remove_blob(self, digest: str) -> Dict[str, Any]:
        """
        Remove a blob from Storacha.
        
        Args:
            digest: The multihash digest of the blob
            
        Returns:
            Dict with removal result
        """
        logger.info(f"Removing blob with digest {digest}")
        
        if self.mock_mode:
            return self._mock_remove_blob(digest)
        
        try:
            # Remove blob from Storacha
            if self.connection_manager:
                try:
                    # Send request via connection manager
                    response = self.connection_manager.send_request(
                        "DELETE", 
                        f"blob/{digest}"
                    )
                    
                    if response.status_code != 200 and response.status_code != 204:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                    
                    return {
                        "success": True,
                        "digest": digest,
                        "removed": True,
                        "timestamp": time.time(),
                        "endpoint": self.connection_manager.working_endpoint
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error removing blob from Storacha: {e}"
                    }
            else:
                # Without connection manager, use regular requests
                try:
                    response = self.session.delete(
                        f"{self.working_endpoint}/blob/{digest}",
                        timeout=30
                    )
                    
                    if response.status_code != 200 and response.status_code != 204:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}"
                        }
                    
                    return {
                        "success": True,
                        "digest": digest,
                        "removed": True,
                        "timestamp": time.time(),
                        "endpoint": self.working_endpoint
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error removing blob from Storacha: {e}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error removing blob: {e}"
            }
    
    # Mock implementation methods
    
    def _mock_from_ipfs(self, cid: str, replication: int = 3) -> Dict[str, Any]:
        """Mock implementation of from_ipfs for testing."""
        try:
            # Get content from IPFS
            process = subprocess.run(
                ["ipfs", "cat", cid],
                capture_output=True,
                timeout=30
            )
            
            if process.returncode != 0:
                return {
                    "success": False,
                    "simulation": False,
                    "mock": True,
                    "error": f"Error retrieving content from IPFS: {process.stderr.decode('utf-8', errors='replace')}"
                }
            
            content_data = process.stdout
            
            # Calculate a storage ID based on content hash
            content_hash = hashlib.sha256(content_data).hexdigest()
            storage_id = f"mock-{content_hash[:16]}"
            
            # Save to mock storage
            storage_path = os.path.join(self.mock_storage_path, storage_id)
            with open(storage_path, "wb") as f:
                f.write(content_data)
            
            # Create metadata file
            metadata = {
                "cid": cid,
                "storage_id": storage_id,
                "size": len(content_data),
                "replication": replication,
                "timestamp": time.time()
            }
            
            metadata_path = os.path.join(self.mock_storage_path, f"{storage_id}.json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f)
            
            return {
                "success": True,
                "simulation": False,
                "mock": True,
                "storage_id": storage_id,
                "size": len(content_data),
                "replication": replication,
                "timestamp": time.time(),
                "ipfs_cid": cid
            }
        except Exception as e:
            return {
                "success": False,
                "simulation": False,
                "mock": True,
                "error": f"Error in mock from_ipfs: {e}"
            }
    
    def _mock_to_ipfs(self, storage_id: str) -> Dict[str, Any]:
        """Mock implementation of to_ipfs for testing."""
        try:
            # Check if storage ID exists
            storage_path = os.path.join(self.mock_storage_path, storage_id)
            if not os.path.exists(storage_path):
                return {
                    "success": False,
                    "simulation": False,
                    "mock": True,
                    "error": f"Storage ID {storage_id} not found in mock storage"
                }
            
            # Read content
            with open(storage_path, "rb") as f:
                content_data = f.read()
            
            # Add to IPFS
            process = subprocess.run(
                ["ipfs", "add", "-Q"],
                input=content_data,
                capture_output=True,
                timeout=30
            )
            
            if process.returncode != 0:
                return {
                    "success": False,
                    "simulation": False,
                    "mock": True,
                    "error": f"Error adding content to IPFS: {process.stderr.decode('utf-8', errors='replace')}"
                }
            
            cid = process.stdout.decode('utf-8').strip()
            
            return {
                "success": True,
                "simulation": False,
                "mock": True,
                "cid": cid,
                "size": len(content_data),
                "timestamp": time.time(),
                "storage_id": storage_id
            }
        except Exception as e:
            return {
                "success": False,
                "simulation": False,
                "mock": True,
                "error": f"Error in mock to_ipfs: {e}"
            }
    
    def _mock_check_status(self, storage_id: str) -> Dict[str, Any]:
        """Mock implementation of check_status for testing."""
        try:
            # Check if storage ID exists
            storage_path = os.path.join(self.mock_storage_path, storage_id)
            metadata_path = os.path.join(self.mock_storage_path, f"{storage_id}.json")
            
            if not os.path.exists(storage_path):
                return {
                    "success": False,
                    "simulation": False,
                    "mock": True,
                    "error": f"Storage ID {storage_id} not found in mock storage"
                }
            
            # Get file size
            size = os.path.getsize(storage_path)
            
            # Read metadata if available
            metadata = {}
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                except:
                    pass
            
            return {
                "success": True,
                "simulation": False,
                "mock": True,
                "storage_id": storage_id,
                "status": "stored",
                "size": size,
                "created": metadata.get("timestamp", os.path.getctime(storage_path)),
                "ipfs_cid": metadata.get("cid", "unknown"),
                "replication": metadata.get("replication", 3),
                "deals": [],
                "pins": []
            }
        except Exception as e:
            return {
                "success": False,
                "simulation": False,
                "mock": True,
                "error": f"Error in mock check_status: {e}"
            }
    
    def _mock_list_blobs(self, cursor: Optional[str] = None, size: int = 100) -> Dict[str, Any]:
        """Mock implementation of list_blobs for testing."""
        try:
            # List files in mock storage
            files = [f for f in os.listdir(self.mock_storage_path) if not f.endswith(".json")]
            
            # Sort by creation time (newest first)
            files.sort(key=lambda f: os.path.getctime(os.path.join(self.mock_storage_path, f)), reverse=True)
            
            # Apply pagination
            start_idx = 0
            if cursor:
                try:
                    start_idx = int(cursor)
                except:
                    start_idx = 0
            
            end_idx = min(start_idx + size, len(files))
            
            # Get slice of files
            page_files = files[start_idx:end_idx]
            
            # Build blob list
            blobs = []
            for file in page_files:
                file_path = os.path.join(self.mock_storage_path, file)
                metadata_path = os.path.join(self.mock_storage_path, f"{file}.json")
                
                # Get file info
                file_size = os.path.getsize(file_path)
                file_created = os.path.getctime(file_path)
                
                # Read metadata if available
                metadata = {}
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                    except:
                        pass
                
                blobs.append({
                    "digest": file,
                    "size": file_size,
                    "created": metadata.get("timestamp", file_created),
                    "cid": metadata.get("cid", "unknown"),
                    "status": "stored"
                })
            
            # Build response
            response = {
                "success": True,
                "simulation": False,
                "mock": True,
                "blobs": blobs
            }
            
            # Add next cursor if there are more blobs
            if end_idx < len(files):
                response["next_cursor"] = str(end_idx)
            
            return response
        except Exception as e:
            return {
                "success": False,
                "simulation": False,
                "mock": True,
                "error": f"Error in mock list_blobs: {e}"
            }
    
    def _mock_get_blob(self, digest: str) -> Dict[str, Any]:
        """Mock implementation of get_blob for testing."""
        try:
            # Check if blob exists
            storage_path = os.path.join(self.mock_storage_path, digest)
            metadata_path = os.path.join(self.mock_storage_path, f"{digest}.json")
            
            if not os.path.exists(storage_path):
                return {
                    "success": False,
                    "simulation": False,
                    "mock": True,
                    "error": f"Blob with digest {digest} not found in mock storage"
                }
            
            # Get file size
            size = os.path.getsize(storage_path)
            
            # Read metadata if available
            metadata = {}
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                except:
                    pass
            
            return {
                "success": True,
                "simulation": False,
                "mock": True,
                "digest": digest,
                "size": size,
                "created": metadata.get("timestamp", os.path.getctime(storage_path)),
                "cid": metadata.get("cid", "unknown"),
                "status": "stored"
            }
        except Exception as e:
            return {
                "success": False,
                "simulation": False,
                "mock": True,
                "error": f"Error in mock get_blob: {e}"
            }
    
    def _mock_remove_blob(self, digest: str) -> Dict[str, Any]:
        """Mock implementation of remove_blob for testing."""
        try:
            # Check if blob exists
            storage_path = os.path.join(self.mock_storage_path, digest)
            metadata_path = os.path.join(self.mock_storage_path, f"{digest}.json")
            
            if not os.path.exists(storage_path):
                return {
                    "success": False,
                    "simulation": False,
                    "mock": True,
                    "error": f"Blob with digest {digest} not found in mock storage"
                }
            
            # Remove files
            os.unlink(storage_path)
            if os.path.exists(metadata_path):
                os.unlink(metadata_path)
            
            return {
                "success": True,
                "simulation": False,
                "mock": True,
                "digest": digest,
                "removed": True,
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "success": False,
                "simulation": False,
                "mock": True,
                "error": f"Error in mock remove_blob: {e}"
            }