"""
Lassie backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for Lassie,
a robust content fetching library for IPFS/Filecoin, providing
efficient content retrieval from the distributed web.
"""

import logging
import time
import os
import json
import tempfile
import shutil
import hashlib
import uuid
import threading
from typing import Dict, Any, Optional, Union, BinaryIO, List, Tuple

# Import the base class and storage types
from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)

# Define constants
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_RETRIES = 3
DEFAULT_CACHE_DIR = None  # Will be set to a temp directory if not provided


class LassieBackend(BackendStorage):
    """Lassie backend implementation for content retrieval from IPFS/Filecoin."""
    
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize Lassie backend.
        
        Args:
            resources: Connection resources including API tokens
            metadata: Additional configuration metadata
        """
        super().__init__(StorageBackendType.LASSIE, resources, metadata)
        
        # Try importing lassie client
        try:
            import lassie
            self.lassie = lassie
            logger.info("Successfully imported lassie client")
        except ImportError:
            logger.error("lassie package is required. Please install with 'pip install lassie'")
            raise ImportError("lassie is required for Lassie backend")
        
        # Extract configuration from resources/metadata
        self.timeout = int(resources.get("timeout", DEFAULT_TIMEOUT))
        self.max_retries = int(resources.get("max_retries", DEFAULT_MAX_RETRIES))
        
        # Set up caching
        self.cache_dir = resources.get("cache_dir", DEFAULT_CACHE_DIR)
        if not self.cache_dir:
            self.cache_dir = os.path.join(
                tempfile.gettempdir(), f"mcp_lassie_cache_{uuid.uuid4().hex[:8]}"
            )
            os.makedirs(self.cache_dir, exist_ok=True)
            logger.info(f"Created Lassie cache directory: {self.cache_dir}")
        
        # IPFS gateway for direct access (optional)
        self.ipfs_gateway = resources.get("ipfs_gateway", "https://ipfs.io/ipfs/")
        
        # Handle additional configuration
        self.providers = resources.get("providers", [])
        self.ipni_endpoints = resources.get("ipni_endpoints", [])
        self.allow_local = resources.get("allow_local", True)
        
        # Configure Lassie client
        self._init_client()
        
        # Set up lock for thread safety
        self.lock = threading.RLock()
        
        # Set up content cache tracking
        self._content_cache = {}
        
    def _init_client(self):
        """Initialize the Lassie client with configuration."""
        try:
            # Create configuration dictionary
            config = {
                "timeout": self.timeout
            }
            
            # Add optional configuration if provided
            if self.providers:
                config["providers"] = self.providers
                
            if self.ipni_endpoints:
                config["ipni_endpoints"] = self.ipni_endpoints
                
            # Get Lassie client instance
            self.client = self.lassie.Client(**config)
            
            logger.info("Lassie client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Lassie client: {e}")
            raise
    
    def get_name(self) -> str:
        """Get the name of this backend implementation.
        
        Returns:
            String representation of the backend name
        """
        return "lassie"

    def add_content(self, content: Union[str, bytes, BinaryIO], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add content is not supported for Lassie backend (read-only).
        
        Args:
            content: Content to add (file path, bytes, or file-like object)
            metadata: Metadata for the content
            
        Returns:
            Dict with error result
        """
        return {
            "success": False,
            "error": "Lassie backend is read-only and doesn't support content addition",
            "error_type": "UnsupportedOperation",
            "backend": self.backend_type.value
        }

    def get_content(self, content_id: str) -> Dict[str, Any]:
        """Retrieve content from IPFS/Filecoin using Lassie.
        
        Args:
            content_id: CID of the content to retrieve
            
        Returns:
            Dict with operation result including content data
        """
        try:
            # Normalize CID format - remove ipfs:// or any prefix
            if "://" in content_id:
                prefix, cid = content_id.split("://", 1)
                if prefix.lower() in ["ipfs", "ipld", "dag-pb", "dag-cbor"]:
                    content_id = cid
            
            # Check if content is already in cache
            cached_path = self._get_cached_path(content_id)
            if cached_path and os.path.exists(cached_path):
                logger.info(f"Using cached content for CID: {content_id}")
                
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
                        "cid": content_id,
                        "cache_path": cached_path,
                        "size": len(data)
                    }
                }
            
            # Fetch content using Lassie
            logger.info(f"Fetching content with CID: {content_id}")
            start_time = time.time()
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Fetch using Lassie client
            result = self.client.fetch(f"ipfs://{content_id}", output_path=temp_path)
            
            end_time = time.time()
            fetch_time = end_time - start_time
            
            # Read the fetched content
            with open(temp_path, 'rb') as f:
                data = f.read()
            
            # Move to cache
            cache_path = os.path.join(self.cache_dir, f"{content_id}")
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            shutil.move(temp_path, cache_path)
            
            # Add to cache tracking
            self._add_to_cache(content_id, cache_path)
            
            return {
                "success": True,
                "data": data,
                "backend": self.backend_type.value,
                "identifier": content_id,
                "details": {
                    "cid": content_id,
                    "cache_path": cache_path,
                    "size": len(data),
                    "fetch_time_seconds": fetch_time
                }
            }
            
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Content not found: {content_id}",
                "error_type": "ContentNotFound",
                "backend": self.backend_type.value
            }
            
        except Exception as e:
            logger.error(f"Error retrieving content with Lassie: {e}")
            
            # Handle specific Lassie errors if possible
            error_type = "LassieRetrievalError"
            
            return {
                "success": False,
                "error": str(e),
                "error_type": error_type,
                "backend": self.backend_type.value
            }

    def remove_content(self, content_id: str) -> Dict[str, Any]:
        """Remove content from local cache only.
        
        Args:
            content_id: CID of the content to remove from cache
            
        Returns:
            Dict with operation result
        """
        try:
            # Get cached path
            cached_path = self._get_cached_path(content_id)
            
            if not cached_path or not os.path.exists(cached_path):
                return {
                    "success": False,
                    "error": f"Content not found in cache: {content_id}",
                    "error_type": "ContentNotFound",
                    "backend": self.backend_type.value
                }
            
            # Remove from cache
            os.remove(cached_path)
            
            # Remove from cache tracking
            with self.lock:
                if content_id in self._content_cache:
                    del self._content_cache[content_id]
            
            return {
                "success": True,
                "backend": self.backend_type.value,
                "identifier": content_id,
                "details": {
                    "removed_from_cache": True,
                    "cache_path": cached_path
                }
            }
            
        except Exception as e:
            logger.error(f"Error removing content from cache: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "CacheRemovalError",
                "backend": self.backend_type.value
            }

    def get_metadata(self, content_id: str) -> Dict[str, Any]:
        """Get metadata for content.
        
        Args:
            content_id: CID of the content
            
        Returns:
            Dict with operation result including metadata
        """
        try:
            # Check if content is in cache first
            cached_path = self._get_cached_path(content_id)
            if cached_path and os.path.exists(cached_path):
                # Get file stats
                stat_info = os.stat(cached_path)
                
                # Calculate hash of file
                file_hash = self._calculate_file_hash(cached_path)
                
                return {
                    "success": True,
                    "metadata": {
                        "cid": content_id,
                        "size": stat_info.st_size,
                        "last_accessed": stat_info.st_atime,
                        "last_modified": stat_info.st_mtime,
                        "cached": True,
                        "hash": file_hash,
                        "backend": self.backend_type.value
                    },
                    "backend": self.backend_type.value,
                    "identifier": content_id
                }
            
            # For content not in cache, attempt to check if it exists by contacting IPFS gateway
            # This is a lightweight check that doesn't download the full content
            import requests
            
            gateway_url = f"{self.ipfs_gateway.rstrip('/')}/{content_id}"
            try:
                response = requests.head(gateway_url, timeout=10)
                
                if response.status_code == 200:
                    # Content exists, get what metadata we can from headers
                    size = response.headers.get("Content-Length")
                    content_type = response.headers.get("Content-Type")
                    
                    return {
                        "success": True,
                        "metadata": {
                            "cid": content_id,
                            "size": int(size) if size and size.isdigit() else None,
                            "content_type": content_type,
                            "cached": False,
                            "backend": self.backend_type.value
                        },
                        "backend": self.backend_type.value,
                        "identifier": content_id
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Content not found or not accessible: {content_id}",
                        "error_type": "ContentNotFound",
                        "backend": self.backend_type.value
                    }
            except requests.RequestException as e:
                logger.warning(f"Error checking content existence via gateway: {e}")
                
                # Fall back to minimal metadata
                return {
                    "success": True,
                    "metadata": {
                        "cid": content_id,
                        "cached": False,
                        "existence_verified": False,
                        "backend": self.backend_type.value
                    },
                    "backend": self.backend_type.value,
                    "identifier": content_id
                }
            
        except Exception as e:
            logger.error(f"Error getting metadata: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "MetadataError",
                "backend": self.backend_type.value
            }

    def update_metadata(self, identifier: str, metadata: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Update metadata for content (not supported in Lassie backend).
        
        Args:
            identifier: Content identifier
            metadata: Metadata to update
            **kwargs: Additional options
            
        Returns:
            Dict with error result
        """
        return {
            "success": False,
            "error": "Metadata updates are not supported by the Lassie backend",
            "error_type": "UnsupportedOperation",
            "backend": self.backend_type.value
        }

    def list(self, prefix: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """List cached content (only local cache is supported).
        
        Args:
            prefix: Optional CID prefix to filter by
            **kwargs: Additional options
            
        Returns:
            Dict with operation result including list of items
        """
        try:
            # List is only supported for the local cache
            cached_items = []
            
            with self.lock:
                cached_cids = list(self._content_cache.keys())
            
            # Filter by prefix if specified
            if prefix:
                cached_cids = [cid for cid in cached_cids if cid.startswith(prefix)]
            
            # Apply pagination if requested
            limit = kwargs.get("limit", len(cached_cids))
            offset = kwargs.get("offset", 0)
            
            paginated_cids = cached_cids[offset:offset+limit]
            
            # Get details for each cached item
            for cid in paginated_cids:
                cached_path = self._get_cached_path(cid)
                
                if cached_path and os.path.exists(cached_path):
                    # Get file stats
                    stat_info = os.stat(cached_path)
                    
                    cached_items.append({
                        "identifier": cid,
                        "size": stat_info.st_size,
                        "last_modified": stat_info.st_mtime,
                        "cache_path": cached_path,
                        "backend": self.backend_type.value
                    })
            
            return {
                "success": True,
                "items": cached_items,
                "count": len(cached_items),
                "total": len(cached_cids),
                "backend": self.backend_type.value,
                "details": {
                    "cached_only": True,
                    "prefix": prefix,
                    "limit": limit,
                    "offset": offset
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing cached content: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "ListError",
                "backend": self.backend_type.value
            }

    def exists(self, identifier: str, **kwargs) -> bool:
        """Check if content exists.
        
        Args:
            identifier: CID of the content
            **kwargs: Additional options
            
        Returns:
            True if content exists, False otherwise
        """
        try:
            # First check local cache
            cached_path = self._get_cached_path(identifier)
            if cached_path and os.path.exists(cached_path):
                return True
            
            # If not in cache and check_remote is True, check gateway
            check_remote = kwargs.get("check_remote", True)
            if check_remote:
                import requests
                
                gateway_url = f"{self.ipfs_gateway.rstrip('/')}/{identifier}"
                try:
                    response = requests.head(gateway_url, timeout=10)
                    return response.status_code == 200
                except requests.RequestException:
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if content exists: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get the status of the Lassie backend.
        
        Returns:
            Dict with status information
        """
        try:
            # Count cached items
            cached_items = 0
            cache_size = 0
            
            if os.path.exists(self.cache_dir):
                for dirpath, dirnames, filenames in os.walk(self.cache_dir):
                    cached_items += len(filenames)
                    for filename in filenames:
                        file_path = os.path.join(dirpath, filename)
                        cache_size += os.path.getsize(file_path)
            
            # Get lassie version if available
            lassie_version = getattr(self.lassie, "__version__", "unknown")
            
            return {
                "success": True,
                "backend": self.backend_type.value,
                "available": True,
                "status": {
                    "lassie_version": lassie_version,
                    "cache": {
                        "directory": self.cache_dir,
                        "items": cached_items,
                        "size_bytes": cache_size,
                        "size_human": f"{cache_size / (1024*1024):.2f} MB"
                    },
                    "configuration": {
                        "timeout": self.timeout,
                        "max_retries": self.max_retries,
                        "ipfs_gateway": self.ipfs_gateway,
                        "providers": self.providers,
                        "ipni_endpoints": self.ipni_endpoints,
                        "allow_local": self.allow_local
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting Lassie backend status: {e}")
            return {
                "success": False,
                "backend": self.backend_type.value,
                "available": False,
                "error": str(e)
            }

    def _get_cached_path(self, content_id: str) -> Optional[str]:
        """Get the cached file path for a content ID.
        
        Args:
            content_id: Content ID (CID)
            
        Returns:
            Path to cached file or None if not in cache
        """
        with self.lock:
            if content_id in self._content_cache:
                return self._content_cache[content_id]
            
            # Try the default cache path structure
            default_path = os.path.join(self.cache_dir, content_id)
            if os.path.exists(default_path):
                self._content_cache[content_id] = default_path
                return default_path
            
            return None

    def _add_to_cache(self, content_id: str, path: str) -> None:
        """Add a content ID to the cache tracking.
        
        Args:
            content_id: Content ID (CID)
            path: Path to the cached file
        """
        with self.lock:
            self._content_cache[content_id] = path

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hex digest of the file hash
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            # Read the file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                
        return sha256_hash.hexdigest()

    def cleanup(self) -> None:
        """Clean up resources used by this backend."""
        # Clean up cache directory if we created it
        if hasattr(self, 'cache_dir') and self.cache_dir and 'mcp_lassie_cache_' in self.cache_dir:
            try:
                if os.path.exists(self.cache_dir):
                    shutil.rmtree(self.cache_dir)
                    logger.info(f"Removed Lassie cache directory: {self.cache_dir}")
            except Exception as e:
                logger.warning(f"Failed to remove cache directory: {e}")