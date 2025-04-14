"""
Lassie backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for Lassie,
a specialized IPFS/Filecoin content retrieval client.
"""

import logging
import time
import os
import json
import tempfile
import subprocess
import shutil
from typing import Dict, Any, Optional, Union, BinaryIO, List
import io
import uuid

from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class LassieBackend(BackendStorage):
    """
    Lassie backend implementation for optimized content retrieval.
    
    Lassie is a specialized content retrieval client that can fetch content
    from the IPFS/Filecoin network with optimized strategies.
    """
    
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize Lassie backend."""
        super().__init__(StorageBackendType.LASSIE, resources, metadata)
        
        # Extract configuration
        self.lassie_path = resources.get('lassie_path') or self._find_lassie_binary()
        self.temp_dir = resources.get('temp_dir') or tempfile.gettempdir()
        self.download_dir = resources.get('download_dir') or os.path.join(self.temp_dir, 'lassie_downloads')
        self.ipfs_gateways = resources.get('ipfs_gateways') or [
            "https://ipfs.io",
            "https://cloudflare-ipfs.com",
            "https://dweb.link"
        ]
        self.use_ipfs_gateways = resources.get('use_ipfs_gateways', True)
        self.max_retries = resources.get('max_retries', 3)
        self.timeout = resources.get('timeout', 60)  # seconds
        
        # Create download directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Initialize metadata cache
        self._metadata_cache = {}
        
        # Verify Lassie installation
        self._verify_lassie()
        
    def _find_lassie_binary(self) -> Optional[str]:
        """Find Lassie binary in PATH."""
        try:
            result = subprocess.run(['which', 'lassie'], capture_output=True, text=True)
            if result.returncode == 0:
                lassie_path = result.stdout.strip()
                logger.info(f"Found Lassie binary at {lassie_path}")
                return lassie_path
        except Exception as e:
            logger.warning(f"Failed to find Lassie binary: {str(e)}")
            
        return None
        
    def _verify_lassie(self):
        """Verify Lassie installation and functionality."""
        if not self.lassie_path:
            logger.warning("Lassie binary not found. Will use IPFS gateways as fallback.")
            return
            
        try:
            # Check if Lassie works
            result = subprocess.run(
                [self.lassie_path, '--version'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"Lassie version: {version}")
            else:
                logger.warning(f"Lassie binary check failed: {result.stderr}")
                self.lassie_path = None
        except Exception as e:
            logger.warning(f"Failed to verify Lassie: {str(e)}")
            self.lassie_path = None
            
    def _fetch_with_lassie(self, cid: str, output_path: str, timeout: int = None) -> Dict[str, Any]:
        """Fetch content using Lassie CLI."""
        if not self.lassie_path:
            return {
                "success": False,
                "error": "Lassie binary not available",
                "fallback": True
            }
            
        timeout = timeout or self.timeout
        
        try:
            cmd = [
                self.lassie_path,
                'fetch',
                cid,
                '--output-dir', output_path,
                '--timeout', str(timeout)
            ]
            
            logger.info(f"Executing Lassie command: {' '.join(cmd)}")
            
            # Run Lassie command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5  # Add buffer to timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Lassie successfully retrieved {cid}")
                return {
                    "success": True,
                    "output": result.stdout,
                    "path": os.path.join(output_path, cid)
                }
            else:
                logger.error(f"Lassie fetch failed: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr,
                    "code": result.returncode,
                    "fallback": True
                }
                
        except subprocess.TimeoutExpired:
            logger.error(f"Lassie fetch timed out after {timeout}s for {cid}")
            return {
                "success": False,
                "error": f"Fetch timed out after {timeout}s",
                "fallback": True
            }
        except Exception as e:
            logger.error(f"Lassie fetch error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "fallback": True
            }
            
    def _fetch_from_gateway(self, cid: str) -> Dict[str, Any]:
        """Fetch content from IPFS gateways."""
        if not self.use_ipfs_gateways:
            return {
                "success": False,
                "error": "IPFS gateway fallback disabled"
            }
            
        # Try each gateway
        for gateway in self.ipfs_gateways:
            url = f"{gateway}/ipfs/{cid}"
            
            try:
                logger.info(f"Trying to fetch {cid} from {gateway}")
                
                import requests
                response = requests.get(url, timeout=self.timeout)
                
                if response.status_code == 200:
                    logger.info(f"Successfully retrieved {cid} from {gateway}")
                    
                    # Save content to file in download directory
                    output_path = os.path.join(self.download_dir, cid)
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                        
                    return {
                        "success": True,
                        "data": response.content,
                        "path": output_path,
                        "gateway": gateway,
                        "content_type": response.headers.get('Content-Type')
                    }
                else:
                    logger.warning(f"Failed to fetch from {gateway}: HTTP {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"Error fetching from {gateway}: {str(e)}")
                continue
                
        # All gateways failed
        return {
            "success": False,
            "error": "Failed to retrieve from all gateways",
            "tried_gateways": self.ipfs_gateways
        }
            
    def store(
        self, 
        data: Union[bytes, BinaryIO, str],
        container: Optional[str] = None,
        path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store data using Lassie.
        
        Note: Lassie is primarily a retrieval client and does not support direct storage.
        This implementation uses an IPFS gateway or local IPFS node if available,
        or returns an error if no storage method is available.
        """
        options = options or {}
        
        try:
            # Check if we have an IPFS backend configured
            try:
                from ipfs_kit_py.ipfs import ipfs_py
                
                # Create IPFS client
                ipfs = ipfs_py()
                
                # Use IPFS to store the data
                if isinstance(data, str):
                    if os.path.isfile(data):
                        # It's a file path
                        with open(data, 'rb') as f:
                            result = ipfs.ipfs_add_file(f)
                    else:
                        # It's string content
                        result = ipfs.ipfs_add_bytes(data.encode('utf-8'))
                elif isinstance(data, bytes):
                    result = ipfs.ipfs_add_bytes(data)
                else:
                    # Assume it's a file-like object
                    result = ipfs.ipfs_add_file(data)
                    
                if result.get("success", False):
                    # Get CID from result
                    cid = result.get("Hash") or result.get("cid")
                    
                    if cid:
                        # Add to metadata cache
                        self._metadata_cache[cid] = {
                            "cid": cid,
                            "created": time.time(),
                            "size": len(data) if isinstance(data, (str, bytes)) else None,
                            "stored_with": "ipfs"
                        }
                    
                    return {
                        "success": True,
                        "identifier": cid,
                        "backend": self.get_name(),
                        "details": {
                            "stored_with": "ipfs",
                            "ipfs_result": result
                        }
                    }
            except ImportError:
                logger.warning("IPFS not available for storage")
                pass
                
            # IPFS not available, try HTTP upload to a gateway that supports it
            try:
                import requests
                
                # Pick a gateway that supports uploads
                # Note: Most public gateways don't support uploads, this is just a placeholder
                # for a real implementation with a writeable endpoint
                writable_endpoint = options.get('writable_endpoint')
                
                if not writable_endpoint:
                    raise ValueError("No writable endpoint configured and IPFS not available")
                    
                # Prepare data for upload
                files = {}
                
                if isinstance(data, str):
                    if os.path.isfile(data):
                        # It's a file path
                        files = {'file': open(data, 'rb')}
                    else:
                        # It's string content
                        files = {'file': io.BytesIO(data.encode('utf-8'))}
                elif isinstance(data, bytes):
                    files = {'file': io.BytesIO(data)}
                else:
                    # Assume it's a file-like object
                    files = {'file': data}
                    
                response = requests.post(writable_endpoint, files=files)
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        cid = result.get('cid') or result.get('Hash')
                        
                        if cid:
                            # Add to metadata cache
                            self._metadata_cache[cid] = {
                                "cid": cid,
                                "created": time.time(),
                                "stored_with": "gateway",
                                "gateway": writable_endpoint
                            }
                        
                        return {
                            "success": True,
                            "identifier": cid,
                            "backend": self.get_name(),
                            "details": {
                                "stored_with": "gateway",
                                "gateway": writable_endpoint,
                                "response": result
                            }
                        }
                    except:
                        raise ValueError(f"Invalid response from gateway: {response.text}")
                else:
                    raise ValueError(f"Gateway upload failed: HTTP {response.status_code}")
                    
            except Exception as gateway_error:
                logger.error(f"Gateway storage failed: {str(gateway_error)}")
                
            return {
                "success": False,
                "error": "Lassie is primarily a retrieval client and no storage method is available",
                "backend": self.get_name()
            }
                
        except Exception as e:
            logger.error(f"Lassie store error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }
        
    def retrieve(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Retrieve content using Lassie."""
        options = options or {}
        cid = identifier
        
        try:
            # Create a unique directory for this retrieval
            retrieval_dir = os.path.join(self.download_dir, f"lassie_{int(time.time())}_{uuid.uuid4().hex[:8]}")
            os.makedirs(retrieval_dir, exist_ok=True)
            
            # Try to retrieve with Lassie first
            if self.lassie_path:
                result = self._fetch_with_lassie(cid, retrieval_dir, options.get('timeout'))
                
                if result.get("success", False):
                    # Read the content from the downloaded file
                    content_path = result.get("path")
                    
                    if os.path.isfile(content_path):
                        with open(content_path, 'rb') as f:
                            data = f.read()
                            
                        # Update metadata cache
                        self._metadata_cache[cid] = {
                            "cid": cid,
                            "retrieved": time.time(),
                            "size": len(data),
                            "local_path": content_path,
                            "retrieved_with": "lassie"
                        }
                        
                        return {
                            "success": True,
                            "data": data,
                            "backend": self.get_name(),
                            "identifier": cid,
                            "details": {
                                "path": content_path,
                                "size": len(data),
                                "retrieved_with": "lassie"
                            }
                        }
                    elif os.path.isdir(content_path):
                        # It's a directory, let's create a tar archive
                        import tarfile
                        
                        tar_path = os.path.join(self.download_dir, f"{cid}.tar")
                        with tarfile.open(tar_path, "w") as tar:
                            tar.add(content_path, arcname=os.path.basename(content_path))
                            
                        # Update metadata cache
                        self._metadata_cache[cid] = {
                            "cid": cid,
                            "retrieved": time.time(),
                            "is_directory": True,
                            "local_path": content_path,
                            "tar_path": tar_path,
                            "retrieved_with": "lassie"
                        }
                        
                        return {
                            "success": True,
                            "is_directory": True,
                            "directory_path": content_path,
                            "tar_path": tar_path,
                            "backend": self.get_name(),
                            "identifier": cid,
                            "details": {
                                "retrieved_with": "lassie"
                            }
                        }
                    else:
                        logger.error(f"Lassie reported success but no content found at {content_path}")
                
            # Lassie failed or not available, try gateways
            if result.get("fallback", True) and self.use_ipfs_gateways:
                gateway_result = self._fetch_from_gateway(cid)
                
                if gateway_result.get("success", False):
                    # Update metadata cache
                    self._metadata_cache[cid] = {
                        "cid": cid,
                        "retrieved": time.time(),
                        "size": len(gateway_result.get("data", b"")),
                        "gateway": gateway_result.get("gateway"),
                        "local_path": gateway_result.get("path"),
                        "retrieved_with": "gateway"
                    }
                    
                    return {
                        "success": True,
                        "data": gateway_result.get("data"),
                        "backend": self.get_name(),
                        "identifier": cid,
                        "details": {
                            "retrieved_with": "gateway",
                            "gateway": gateway_result.get("gateway"),
                            "path": gateway_result.get("path"),
                            "content_type": gateway_result.get("content_type")
                        }
                    }
                else:
                    # Both Lassie and gateways failed
                    return {
                        "success": False,
                        "error": "Failed to retrieve content with both Lassie and gateways",
                        "backend": self.get_name(),
                        "details": {
                            "lassie_error": result.get("error") if isinstance(result, dict) else "Lassie not available",
                            "gateway_error": gateway_result.get("error")
                        }
                    }
            
            # Lassie failed and gateways not enabled or also failed
            return {
                "success": False,
                "error": "Failed to retrieve content",
                "backend": self.get_name(),
                "details": result if isinstance(result, dict) else {"error": "Unknown error"}
            }
                
        except Exception as e:
            logger.error(f"Lassie retrieve error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }
        finally:
            # Clean up temporary directory if it's empty
            try:
                if os.path.exists(retrieval_dir) and not os.listdir(retrieval_dir):
                    os.rmdir(retrieval_dir)
            except:
                pass
        
    def delete(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Delete local copy of content retrieved via Lassie.
        
        Note: This only deletes the local copy, not the content from the network.
        """
        options = options or {}
        cid = identifier
        
        try:
            # Check if we have metadata for this CID
            if cid in self._metadata_cache:
                metadata = self._metadata_cache[cid]
                local_path = metadata.get("local_path")
                
                # Delete the local file or directory
                if local_path and os.path.exists(local_path):
                    if os.path.isfile(local_path):
                        os.remove(local_path)
                    elif os.path.isdir(local_path):
                        shutil.rmtree(local_path)
                        
                # Delete any associated tar file
                tar_path = metadata.get("tar_path")
                if tar_path and os.path.exists(tar_path):
                    os.remove(tar_path)
                    
                # Remove from cache
                del self._metadata_cache[cid]
                
                return {
                    "success": True,
                    "warning": "Only the local copy was deleted",
                    "backend": self.get_name(),
                    "identifier": cid,
                    "details": {
                        "deleted_path": local_path
                    }
                }
            else:
                # Try to find the file in the download directory
                potential_paths = [
                    os.path.join(self.download_dir, cid),
                    os.path.join(self.download_dir, f"{cid}.tar")
                ]
                
                deleted_paths = []
                for path in potential_paths:
                    if os.path.exists(path):
                        if os.path.isfile(path):
                            os.remove(path)
                        elif os.path.isdir(path):
                            shutil.rmtree(path)
                        deleted_paths.append(path)
                        
                if deleted_paths:
                    return {
                        "success": True,
                        "warning": "Only the local copy was deleted",
                        "backend": self.get_name(),
                        "identifier": cid,
                        "details": {
                            "deleted_paths": deleted_paths
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": "No local copy found to delete",
                        "backend": self.get_name(),
                        "identifier": cid
                    }
                
        except Exception as e:
            logger.error(f"Lassie delete error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }
        
    def list(
        self,
        container: Optional[str] = None,
        prefix: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        List locally cached content retrieved via Lassie.
        
        Note: This only lists locally cached content, not content available on the network.
        """
        options = options or {}
        
        try:
            # List files in the download directory
            if not os.path.exists(self.download_dir):
                return {
                    "success": True,
                    "items": [],
                    "backend": self.get_name(),
                    "details": {
                        "download_dir": self.download_dir
                    }
                }
                
            # Get directory listing
            items = []
            
            # First add items from metadata cache
            for cid, metadata in self._metadata_cache.items():
                # Apply prefix filter if provided
                if prefix and not cid.startswith(prefix):
                    continue
                    
                # Check if the file still exists
                local_path = metadata.get("local_path")
                if not local_path or not os.path.exists(local_path):
                    continue
                    
                items.append({
                    "identifier": cid,
                    "path": local_path,
                    "size": metadata.get("size"),
                    "is_directory": metadata.get("is_directory", False),
                    "retrieved": metadata.get("retrieved"),
                    "retrieved_with": metadata.get("retrieved_with"),
                    "backend": self.get_name()
                })
                
            # Then scan download directory for any items not in cache
            for item in os.listdir(self.download_dir):
                item_path = os.path.join(self.download_dir, item)
                
                # Skip if not a file or directory
                if not os.path.isfile(item_path) and not os.path.isdir(item_path):
                    continue
                    
                # Extract CID - if the filename is a CID itself or starts with a CID
                cid = item
                if item.endswith(".tar"):
                    cid = item[:-4]
                    
                # Apply prefix filter if provided
                if prefix and not cid.startswith(prefix):
                    continue
                    
                # Skip if already added from cache
                if any(i.get("identifier") == cid for i in items):
                    continue
                    
                # Add to list
                items.append({
                    "identifier": cid,
                    "path": item_path,
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None,
                    "is_directory": os.path.isdir(item_path),
                    "retrieved": None,  # Unknown, not in cache
                    "backend": self.get_name()
                })
                
            return {
                "success": True,
                "items": items,
                "backend": self.get_name(),
                "details": {
                    "download_dir": self.download_dir,
                    "count": len(items)
                }
            }
                
        except Exception as e:
            logger.error(f"Lassie list error: {str(e)}")
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
        Check if content exists locally or is retrievable via Lassie.
        
        Args:
            identifier: CID of the content to check
            container: Not used in this backend
            options: Additional options
                - check_network: Whether to check the network or only local cache
                
        Returns:
            True if content exists locally or is retrievable
        """
        options = options or {}
        cid = identifier
        check_network = options.get('check_network', False)
        
        try:
            # First check metadata cache
            if cid in self._metadata_cache:
                metadata = self._metadata_cache[cid]
                local_path = metadata.get("local_path")
                
                # Verify file still exists
                if local_path and os.path.exists(local_path):
                    return True
                    
            # Then check download directory for the file
            potential_paths = [
                os.path.join(self.download_dir, cid),
                os.path.join(self.download_dir, f"{cid}.tar")
            ]
            
            for path in potential_paths:
                if os.path.exists(path):
                    return True
                    
            # If not checking network, we're done
            if not check_network:
                return False
                
            # Try a HEAD request to a gateway to check if available on network
            if self.use_ipfs_gateways:
                import requests
                
                for gateway in self.ipfs_gateways:
                    url = f"{gateway}/ipfs/{cid}"
                    try:
                        response = requests.head(url, timeout=5)
                        if response.status_code == 200:
                            return True
                    except:
                        continue
                
            return False
                
        except Exception as e:
            logger.error(f"Lassie exists check error: {str(e)}")
            return False
        
    def get_metadata(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get metadata for content retrieved via Lassie."""
        options = options or {}
        cid = identifier
        
        try:
            # First check metadata cache
            if cid in self._metadata_cache:
                metadata = self._metadata_cache[cid]
                return {
                    "success": True,
                    "metadata": metadata,
                    "backend": self.get_name(),
                    "identifier": cid,
                    "details": {
                        "source": "cache"
                    }
                }
                
            # Then check if file exists locally
            potential_paths = [
                os.path.join(self.download_dir, cid),
                os.path.join(self.download_dir, f"{cid}.tar")
            ]
            
            for path in potential_paths:
                if os.path.exists(path):
                    metadata = {
                        "cid": cid,
                        "local_path": path,
                        "size": os.path.getsize(path) if os.path.isfile(path) else None,
                        "is_directory": os.path.isdir(path),
                        "retrieved_with": "unknown"  # Not in cache, so don't know
                    }
                    
                    # Update cache
                    self._metadata_cache[cid] = metadata
                    
                    return {
                        "success": True,
                        "metadata": metadata,
                        "backend": self.get_name(),
                        "identifier": cid,
                        "details": {
                            "source": "filesystem"
                        }
                    }
                    
            # Not found locally, check network if requested
            if options.get('check_network', False) and self.use_ipfs_gateways:
                import requests
                
                for gateway in self.ipfs_gateways:
                    url = f"{gateway}/ipfs/{cid}"
                    try:
                        response = requests.head(url, timeout=5)
                        if response.status_code == 200:
                            metadata = {
                                "cid": cid,
                                "available_on_network": True,
                                "gateway": gateway,
                                "content_type": response.headers.get('Content-Type'),
                                "content_length": response.headers.get('Content-Length')
                            }
                            
                            return {
                                "success": True,
                                "metadata": metadata,
                                "backend": self.get_name(),
                                "identifier": cid,
                                "details": {
                                    "source": "network",
                                    "gateway": gateway
                                }
                            }
                    except:
                        continue
                        
            # Not found
            return {
                "success": False,
                "error": "Content not found locally",
                "backend": self.get_name(),
                "identifier": cid
            }
                
        except Exception as e:
            logger.error(f"Lassie get_metadata error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }
        
    def update_metadata(
        self,
        identifier: str,
        metadata: Dict[str, Any],
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update metadata for content in local cache.
        
        Note: This only updates local metadata, not metadata on the network.
        """
        options = options or {}
        cid = identifier
        
        try:
            # Check if content exists in cache
            current_metadata = self._metadata_cache.get(cid, {})
            
            if not current_metadata:
                # Check if file exists locally
                potential_paths = [
                    os.path.join(self.download_dir, cid),
                    os.path.join(self.download_dir, f"{cid}.tar")
                ]
                
                for path in potential_paths:
                    if os.path.exists(path):
                        current_metadata = {
                            "cid": cid,
                            "local_path": path,
                            "size": os.path.getsize(path) if os.path.isfile(path) else None,
                            "is_directory": os.path.isdir(path)
                        }
                        break
                        
            if not current_metadata:
                return {
                    "success": False,
                    "error": "Content not found in local cache",
                    "backend": self.get_name(),
                    "identifier": cid
                }
                
            # Update metadata
            updated_metadata = {**current_metadata}
            for k, v in metadata.items():
                if v is None and k in updated_metadata:
                    del updated_metadata[k]
                else:
                    updated_metadata[k] = v
                    
            # Store updated metadata
            self._metadata_cache[cid] = updated_metadata
            
            return {
                "success": True,
                "backend": self.get_name(),
                "identifier": cid,
                "details": {
                    "metadata": updated_metadata
                }
            }
                
        except Exception as e:
            logger.error(f"Lassie update_metadata error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }
            
    # Extended Lassie-specific operations
    
    def fetch_car(
        self,
        cid: str,
        output_path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch content as CAR file using Lassie.
        
        Args:
            cid: CID of the content to fetch
            output_path: Path to save the CAR file
            options: Additional options
                - timeout: Timeout in seconds
                
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        
        if not self.lassie_path:
            return {
                "success": False,
                "error": "Lassie binary not available",
                "backend": self.get_name()
            }
            
        try:
            # Use default output path if not specified
            if not output_path:
                output_path = os.path.join(self.download_dir, f"{cid}.car")
                
            # Run Lassie with CAR output
            timeout = options.get('timeout') or self.timeout
            
            cmd = [
                self.lassie_path,
                'fetch',
                '--car',
                '--output-file', output_path,
                '--timeout', str(timeout),
                cid
            ]
            
            logger.info(f"Executing Lassie CAR command: {' '.join(cmd)}")
            
            # Run command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5  # Add buffer
            )
            
            if result.returncode == 0:
                logger.info(f"Lassie successfully fetched CAR for {cid}")
                
                # Update metadata cache
                self._metadata_cache[cid] = {
                    "cid": cid,
                    "car_path": output_path,
                    "retrieved": time.time(),
                    "retrieved_with": "lassie_car"
                }
                
                return {
                    "success": True,
                    "car_path": output_path,
                    "backend": self.get_name(),
                    "identifier": cid,
                    "details": {
                        "output": result.stdout
                    }
                }
            else:
                logger.error(f"Lassie CAR fetch failed: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr,
                    "backend": self.get_name(),
                    "details": {
                        "code": result.returncode
                    }
                }
                
        except subprocess.TimeoutExpired:
            logger.error(f"Lassie CAR fetch timed out after {timeout}s for {cid}")
            return {
                "success": False,
                "error": f"Fetch timed out after {timeout}s",
                "backend": self.get_name()
            }
        except Exception as e:
            logger.error(f"Lassie CAR fetch error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }
            
    def clear_cache(
        self,
        identifier: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Clear local cache of retrieved content.
        
        Args:
            identifier: Optional CID to clear (if None, clears all)
            options: Additional options
                - keep_metadata: Whether to keep metadata even after deleting files
                
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        keep_metadata = options.get('keep_metadata', False)
        
        try:
            deleted_items = []
            
            # If specific CID provided, only delete that
            if identifier:
                result = self.delete(identifier, options=options)
                
                if result.get("success", False):
                    deleted_items.append(identifier)
                    
                return {
                    "success": True,
                    "deleted_items": deleted_items,
                    "backend": self.get_name(),
                    "details": result.get("details", {})
                }
                
            # Delete all cached items
            if os.path.exists(self.download_dir):
                for item in os.listdir(self.download_dir):
                    item_path = os.path.join(self.download_dir, item)
                    
                    try:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                            
                        deleted_items.append(item)
                    except Exception as delete_error:
                        logger.warning(f"Failed to delete {item_path}: {str(delete_error)}")
                        
            # Clear metadata cache if requested
            if not keep_metadata:
                self._metadata_cache.clear()
                
            return {
                "success": True,
                "deleted_items": deleted_items,
                "metadata_cleared": not keep_metadata,
                "backend": self.get_name(),
                "details": {
                    "download_dir": self.download_dir
                }
            }
                
        except Exception as e:
            logger.error(f"Lassie clear_cache error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }