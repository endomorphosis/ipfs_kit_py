"""
Unified Storage Manager implementation.

This module implements the main UnifiedStorageManager class that coordinates
operations across all storage backends.
"""

import logging
import time
import json
import os
import uuid
import hashlib
from typing import Dict, List, Any, Optional, Union, BinaryIO, Set

from .storage_types import StorageBackendType, ContentReference
from .backend_base import BackendStorage
from .backends import IPFSBackend, S3Backend, StorachaBackend

# Configure logger
logger = logging.getLogger(__name__)


class UnifiedStorageManager:
    """
    Unified Storage Manager for MCP.
    
    This class provides a single interface for interacting with all supported
    storage backends in the MCP system, implementing the features from the
    "Unified Data Management" section of the roadmap.
    """
    
    def __init__(self, resources=None, metadata=None):
        """
        Initialize the unified storage manager.
        
        Args:
            resources: Dictionary of available resources
            metadata: Additional configuration metadata
        """
        self.resources = resources or {}
        self.metadata = metadata or {}
        
        # Dictionary to store backend instances
        self.backends = {}
        
        # Content reference registry
        self.content_registry = {}
        
        # Last used backend for operations
        self.last_backend = None
        
        # Statistics
        self.stats = {
            "operations": {
                "store": 0,
                "retrieve": 0,
                "delete": 0,
                "list": 0
            },
            "backend_usage": {},
            "total_content_size": 0,
            "content_count": 0
        }
        
        # Load available backends
        self._load_backends()
        
        # Load content references from persistent storage if available
        self._load_content_registry()
        
    def _load_backends(self):
        """Load all available backend implementations."""
        # Initialize supported backends based on configuration
        backend_configs = self.metadata.get("backends", {})
        
        # Initialize IPFS backend if configured
        if backend_configs.get("ipfs", {}).get("enabled", True):
            try:
                self.backends[StorageBackendType.IPFS] = IPFSBackend(
                    self.resources,
                    backend_configs.get("ipfs", {})
                )
                logger.info("Initialized IPFS backend")
            except ImportError as e:
                logger.warning(f"Failed to initialize IPFS backend: {e}")
        
        # Initialize S3 backend if configured
        if backend_configs.get("s3", {}).get("enabled", True):
            try:
                self.backends[StorageBackendType.S3] = S3Backend(
                    self.resources,
                    backend_configs.get("s3", {})
                )
                logger.info("Initialized S3 backend")
            except ImportError as e:
                logger.warning(f"Failed to initialize S3 backend: {e}")
                
        # Initialize Storacha backend if configured
        if backend_configs.get("storacha", {}).get("enabled", True):
            try:
                self.backends[StorageBackendType.STORACHA] = StorachaBackend(
                    self.resources,
                    backend_configs.get("storacha", {})
                )
                logger.info("Initialized Storacha backend")
            except ImportError as e:
                logger.warning(f"Failed to initialize Storacha backend: {e}")

        # Initialize Filecoin backend if configured
        if backend_configs.get("filecoin", {}).get("enabled", True):
            try:
                self.backends[StorageBackendType.FILECOIN] = FilecoinBackend(
                    self.resources,
                    backend_configs.get("filecoin", {})
                )
                logger.info("Initialized Filecoin backend")
            except ImportError as e:
                logger.warning(f"Failed to initialize Filecoin backend: {e}")
                
        # Initialize HuggingFace backend if configured
        if backend_configs.get("huggingface", {}).get("enabled", True):
            try:
                self.backends[StorageBackendType.HUGGINGFACE] = HuggingFaceBackend(
                    self.resources,
                    backend_configs.get("huggingface", {})
                )
                logger.info("Initialized HuggingFace backend")
            except ImportError as e:
                logger.warning(f"Failed to initialize HuggingFace backend: {e}")
                
        # Initialize Lassie backend if configured
        if backend_configs.get("lassie", {}).get("enabled", True):
            try:
                self.backends[StorageBackendType.LASSIE] = LassieBackend(
                    self.resources,
                    backend_configs.get("lassie", {})
                )
                logger.info("Initialized Lassie backend")
            except ImportError as e:
                logger.warning(f"Failed to initialize Lassie backend: {e}")
                
        # Initialize statistics for each backend
        for backend_type in self.backends:
            self.stats["backend_usage"][backend_type.value] = {
                "store": 0,
                "retrieve": 0,
                "delete": 0,
                "list": 0,
                "total_bytes": 0
            }
                
        logger.info(f"Loaded {len(self.backends)} storage backends")
    
    def _load_content_registry(self):
        """Load content references from persistent storage."""
        registry_path = self.metadata.get("content_registry_path")
        
        if registry_path and os.path.exists(registry_path):
            try:
                with open(registry_path, 'r') as f:
                    registry_data = json.load(f)
                    
                for content_id, content_data in registry_data.items():
                    self.content_registry[content_id] = ContentReference.from_dict(content_data)
                    
                self.stats["content_count"] = len(self.content_registry)
                self.stats["total_content_size"] = sum(
                    ref.metadata.get("size", 0) for ref in self.content_registry.values()
                )
                    
                logger.info(f"Loaded {len(self.content_registry)} content references from registry")
            except Exception as e:
                logger.error(f"Failed to load content registry: {e}")
    
    def _save_content_registry(self):
        """Save content references to persistent storage."""
        registry_path = self.metadata.get("content_registry_path")
        
        if registry_path:
            try:
                registry_data = {
                    content_id: ref.to_dict()
                    for content_id, ref in self.content_registry.items()
                }
                
                with open(registry_path, 'w') as f:
                    json.dump(registry_data, f, indent=2)
                    
                logger.info(f"Saved {len(self.content_registry)} content references to registry")
            except Exception as e:
                logger.error(f"Failed to save content registry: {e}")
    
    def _generate_content_id(self, data, metadata=None):
        """
        Generate a unique content ID for data.
        
        Args:
            data: Content data
            metadata: Additional metadata
            
        Returns:
            Content ID string
        """
        # Create a hash of the content
        hasher = hashlib.sha256()
        
        # Update with content data
        if isinstance(data, bytes):
            hasher.update(data)
        elif isinstance(data, str):
            hasher.update(data.encode('utf-8'))
        elif hasattr(data, 'read'):
            # For file-like objects, compute hash in chunks
            data.seek(0)
            for chunk in iter(lambda: data.read(4096), b''):
                hasher.update(chunk)
            data.seek(0)
        
        # Add timestamp for uniqueness
        hasher.update(str(time.time()).encode('utf-8'))
        
        # Generate content ID
        return f"mcp-{hasher.hexdigest()}"
    
    def _update_stats(self, operation, backend_type, data_size=0):
        """
        Update operation statistics.
        
        Args:
            operation: Operation type (store, retrieve, delete, list)
            backend_type: Backend type
            data_size: Size of data involved in operation
        """
        # Update operation count
        if operation in self.stats["operations"]:
            self.stats["operations"][operation] += 1
            
        # Update backend usage stats
        backend_key = backend_type.value if isinstance(backend_type, StorageBackendType) else str(backend_type)
        if backend_key in self.stats["backend_usage"]:
            if operation in self.stats["backend_usage"][backend_key]:
                self.stats["backend_usage"][backend_key][operation] += 1
                
            if operation == "store" and data_size > 0:
                self.stats["backend_usage"][backend_key]["total_bytes"] += data_size
    
    def _select_backend(self, preference=None, operation=None, metadata=None):
        """
        Select the best backend for an operation based on content characteristics.
        
        Args:
            preference: Preferred backend type
            operation: Operation type (store, retrieve, delete, list)
            metadata: Content metadata including size, type, priorities
            
        Returns:
            Selected backend instance
        """
        if preference:
            # Convert string to enum if needed
            if isinstance(preference, str):
                try:
                    preference = StorageBackendType.from_string(preference)
                except ValueError:
                    logger.warning(f"Invalid backend preference: {preference}")
                    preference = None
            
            # Use preferred backend if available
            if preference in self.backends:
                self.last_backend = preference
                return self.backends[preference]
        
        # Content-aware backend selection based on characteristics
        if metadata:
            size = metadata.get("size", 0)
            content_type = metadata.get("content_type", "")
            durability_priority = metadata.get("durability_priority", 0)  # 0-10 scale
            speed_priority = metadata.get("speed_priority", 5)  # 0-10 scale
            cost_priority = metadata.get("cost_priority", 5)  # 0-10 scale (higher means more cost-sensitive)
            
            # AI model files (.safetensors, .bin, .pt, .onnx, etc.)
            if (content_type and any(model_ext in content_type.lower() for model_ext in [
                'model', 'safetensors', 'bin', 'pt', 'onnx', 'pb', 'tflite', 'h5'
            ])) or (metadata.get("is_model", False)):
                # Models should preferably go to HuggingFace
                if StorageBackendType.HUGGINGFACE in self.backends:
                    self.last_backend = StorageBackendType.HUGGINGFACE
                    return self.backends[StorageBackendType.HUGGINGFACE]
                # Fallback to S3 for large models
                elif size > 50 * 1024 * 1024 and StorageBackendType.S3 in self.backends:
                    self.last_backend = StorageBackendType.S3
                    return self.backends[StorageBackendType.S3]
            
            # High durability needs (archival)
            if durability_priority > 7:
                # Filecoin is best for long-term archival
                if StorageBackendType.FILECOIN in self.backends:
                    self.last_backend = StorageBackendType.FILECOIN
                    return self.backends[StorageBackendType.FILECOIN]
                # Storacha (Web3.Storage) is also good for durability
                elif StorageBackendType.STORACHA in self.backends:
                    self.last_backend = StorageBackendType.STORACHA
                    return self.backends[StorageBackendType.STORACHA]
            
            # High speed priority (fast retrieval)
            if speed_priority > 7:
                # Lassie is optimized for fast IPFS content retrieval
                if operation == "retrieve" and StorageBackendType.LASSIE in self.backends:
                    self.last_backend = StorageBackendType.LASSIE
                    return self.backends[StorageBackendType.LASSIE]
                # S3 is generally fast for both storing and retrieving
                elif StorageBackendType.S3 in self.backends:
                    self.last_backend = StorageBackendType.S3
                    return self.backends[StorageBackendType.S3]
            
            # Size-based selection
            if size > 0:
                # Very large files (>1GB)
                if size > 1024 * 1024 * 1024:
                    # S3 is best for very large files
                    if StorageBackendType.S3 in self.backends:
                        self.last_backend = StorageBackendType.S3
                        return self.backends[StorageBackendType.S3]
                    # HuggingFace is good for large dataset files
                    elif metadata.get("is_dataset", False) and StorageBackendType.HUGGINGFACE in self.backends:
                        self.last_backend = StorageBackendType.HUGGINGFACE
                        return self.backends[StorageBackendType.HUGGINGFACE]
                
                # Large files (>100MB but <1GB)
                elif size > 100 * 1024 * 1024:
                    # S3 for general large files
                    if StorageBackendType.S3 in self.backends:
                        self.last_backend = StorageBackendType.S3
                        return self.backends[StorageBackendType.S3]
                    # Storacha for decentralized storage of large files
                    elif cost_priority < 5 and StorageBackendType.STORACHA in self.backends:
                        self.last_backend = StorageBackendType.STORACHA
                        return self.backends[StorageBackendType.STORACHA]
                
                # Medium files (1MB to 100MB)
                elif size > 1024 * 1024:
                    # IPFS is good for medium-sized files in most cases
                    if StorageBackendType.IPFS in self.backends:
                        self.last_backend = StorageBackendType.IPFS
                        return self.backends[StorageBackendType.IPFS]
                
                # Small files (<1MB)
                else:
                    # IPFS is ideal for small files
                    if StorageBackendType.IPFS in self.backends:
                        self.last_backend = StorageBackendType.IPFS
                        return self.backends[StorageBackendType.IPFS]
            
            # Cost-sensitive selection
            if cost_priority > 7:
                # IPFS is generally low cost
                if StorageBackendType.IPFS in self.backends:
                    self.last_backend = StorageBackendType.IPFS
                    return self.backends[StorageBackendType.IPFS]
                # Storacha can be economical for long-term storage
                elif StorageBackendType.STORACHA in self.backends:
                    self.last_backend = StorageBackendType.STORACHA
                    return self.backends[StorageBackendType.STORACHA]
        
        # Operation-specific defaults
        if operation == "retrieve":
            # Lassie is optimized for retrieval
            if StorageBackendType.LASSIE in self.backends:
                self.last_backend = StorageBackendType.LASSIE
                return self.backends[StorageBackendType.LASSIE]
                
        # Default fallbacks
        if StorageBackendType.IPFS in self.backends:
            self.last_backend = StorageBackendType.IPFS
            return self.backends[StorageBackendType.IPFS]
        elif self.backends:
            backend_type = next(iter(self.backends))
            self.last_backend = backend_type
            return self.backends[backend_type]
        
        # No backends available
        raise ValueError("No storage backends available")
    
    def _calculate_data_size(self, data):
        """
        Calculate the size of data in bytes.
        
        Args:
            data: Data to measure
            
        Returns:
            Size in bytes
        """
        if isinstance(data, bytes):
            return len(data)
        elif isinstance(data, str):
            return len(data.encode('utf-8'))
        elif hasattr(data, 'seek') and hasattr(data, 'tell'):
            # For file-like objects
            current_pos = data.tell()
            data.seek(0, os.SEEK_END)
            size = data.tell()
            data.seek(current_pos)
            return size
        
        # Default fallback
        return 0
    
    def store(
        self,
        data: Union[bytes, BinaryIO, str],
        backend_preference: Optional[Union[StorageBackendType, str]] = None,
        container: Optional[str] = None,
        path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store data in the optimal backend.
        
        Args:
            data: Data to store
            backend_preference: Preferred backend to use (optional)
            container: Container to store in (for backends that use containers)
            path: Path within container (optional)
            metadata: Additional metadata to associate with the content
            options: Additional options for the storage operation
            
        Returns:
            Dictionary with operation result
        """
        metadata = metadata or {}
        options = options or {}
        
        try:
            # Calculate data size
            data_size = self._calculate_data_size(data)
            metadata["size"] = data_size
            
            # Select the backend to use
            backend = self._select_backend(
                preference=backend_preference,
                operation="store",
                metadata=metadata
            )
            
            # Store the data
            result = backend.store(
                data=data,
                container=container,
                path=path,
                options=options
            )
            
            # Update stats
            self._update_stats("store", backend.backend_type, data_size)
            
            if result.get("success", False):
                # Generate global content ID if not already in metadata
                content_id = metadata.get("content_id") or self._generate_content_id(data, metadata)
                
                # Create or update content reference
                if content_id in self.content_registry:
                    # Update existing reference
                    content_ref = self.content_registry[content_id]
                    content_ref.add_location(backend.backend_type, result["identifier"])
                    
                    # Update metadata
                    content_ref.metadata.update(metadata)
                else:
                    # Create new reference
                    content_ref = ContentReference(
                        content_id=content_id,
                        content_hash=metadata.get("hash"),
                        metadata=metadata
                    )
                    content_ref.add_location(backend.backend_type, result["identifier"])
                    self.content_registry[content_id] = content_ref
                    
                    # Update stats
                    self.stats["content_count"] += 1
                    self.stats["total_content_size"] += data_size
                
                # Save updated registry
                self._save_content_registry()
                
                # Include content reference in result
                result["content_id"] = content_id
                result["content_reference"] = content_ref.to_dict()
            
            return result
            
        except Exception as e:
            logger.exception(f"Error storing data: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def retrieve(
        self,
        content_id: str,
        backend_preference: Optional[Union[StorageBackendType, str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve data by content ID.
        
        Args:
            content_id: Content ID to retrieve
            backend_preference: Preferred backend to use (optional)
            options: Additional options for the retrieval operation
            
        Returns:
            Dictionary with operation result and data
        """
        options = options or {}
        
        try:
            # Check if content exists in registry
            if content_id not in self.content_registry:
                return {
                    "success": False,
                    "error": f"Content ID not found: {content_id}",
                    "error_type": "ContentNotFound"
                }
            
            # Get content reference
            content_ref = self.content_registry[content_id]
            content_ref.record_access()
            
            # Determine which backend to use
            backend_type = None
            location_id = None
            container = None
            
            if backend_preference:
                # Try preferred backend first
                if isinstance(backend_preference, str):
                    try:
                        backend_preference = StorageBackendType.from_string(backend_preference)
                    except ValueError:
                        pass
                
                if isinstance(backend_preference, StorageBackendType) and content_ref.has_location(backend_preference):
                    backend_type = backend_preference
                    location_id = content_ref.get_location(backend_type)
            
            # If preferred backend not available, use any available backend
            if not backend_type:
                for b_type in content_ref.backend_locations:
                    if b_type in self.backends:
                        backend_type = b_type
                        location_id = content_ref.get_location(b_type)
                        break
            
            if not backend_type or not location_id:
                return {
                    "success": False,
                    "error": f"Content not available in any active backend: {content_id}",
                    "error_type": "ContentUnavailable"
                }
            
            # Get the backend instance
            backend = self.backends[backend_type]
            
            # For S3, we need container information
            if backend_type == StorageBackendType.S3:
                # Check if container info is in the location ID
                if ":" in location_id:
                    container, location_id = location_id.split(":", 1)
                else:
                    # Use default bucket
                    container = backend.metadata.get("default_bucket")
            
            # Retrieve the data
            result = backend.retrieve(
                identifier=location_id,
                container=container,
                options=options
            )
            
            # Update stats
            self._update_stats("retrieve", backend_type)
            
            # Include content reference in result
            if result.get("success", False):
                result["content_id"] = content_id
                result["content_reference"] = content_ref.to_dict()
            
            return result
            
        except Exception as e:
            logger.exception(f"Error retrieving data: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def delete(
        self,
        content_id: str,
        backend: Optional[Union[StorageBackendType, str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Delete content by content ID.
        
        Args:
            content_id: Content ID to delete
            backend: Backend to delete from (if None, deletes from all backends)
            options: Additional options for the delete operation
            
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        
        try:
            # Check if content exists in registry
            if content_id not in self.content_registry:
                return {
                    "success": False,
                    "error": f"Content ID not found: {content_id}",
                    "error_type": "ContentNotFound"
                }
            
            # Get content reference
            content_ref = self.content_registry[content_id]
            
            # Determine which backend(s) to delete from
            backend_types = []
            
            if backend:
                # Delete from specific backend
                if isinstance(backend, str):
                    try:
                        backend = StorageBackendType.from_string(backend)
                    except ValueError:
                        return {
                            "success": False,
                            "error": f"Invalid backend type: {backend}",
                            "error_type": "InvalidBackend"
                        }
                
                if content_ref.has_location(backend):
                    backend_types = [backend]
                else:
                    return {
                        "success": False,
                        "error": f"Content not available in specified backend: {backend.value}",
                        "error_type": "ContentUnavailable"
                    }
            else:
                # Delete from all backends
                backend_types = [
                    b_type for b_type in content_ref.backend_locations
                    if b_type in self.backends
                ]
            
            if not backend_types:
                return {
                    "success": False,
                    "error": f"Content not available in any active backend: {content_id}",
                    "error_type": "ContentUnavailable"
                }
            
            # Track results
            results = {}
            all_success = True
            
            # Delete from each backend
            for b_type in backend_types:
                b_instance = self.backends[b_type]
                location_id = content_ref.get_location(b_type)
                container = None
                
                # For S3, we need container information
                if b_type == StorageBackendType.S3:
                    # Check if container info is in the location ID
                    if ":" in location_id:
                        container, location_id = location_id.split(":", 1)
                    else:
                        # Use default bucket
                        container = b_instance.metadata.get("default_bucket")
                
                # Delete the content
                result = b_instance.delete(
                    identifier=location_id,
                    container=container,
                    options=options
                )
                
                # Update stats
                self._update_stats("delete", b_type)
                
                # Store result
                results[b_type.value] = result
                
                # Update success flag
                all_success = all_success and result.get("success", False)
                
                # Remove location from content reference if successful
                if result.get("success", False):
                    content_ref.remove_location(b_type)
            
            # If content has no more locations, remove from registry
            if not content_ref.backend_locations:
                # Update stats before removal
                self.stats["content_count"] -= 1
                self.stats["total_content_size"] -= content_ref.metadata.get("size", 0)
                
                # Remove from registry
                del self.content_registry[content_id]
            
            # Save updated registry
            self._save_content_registry()
            
            return {
                "success": all_success,
                "content_id": content_id,
                "backends": results
            }
            
        except Exception as e:
            logger.exception(f"Error deleting data: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def list_content(
        self,
        backend: Optional[Union[StorageBackendType, str]] = None,
        prefix: Optional[str] = None,
        container: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        List available content.
        
        Args:
            backend: Backend to list from (if None, lists from registry)
            prefix: Filter by content ID prefix
            container: Container to list (for backends that use containers)
            limit: Maximum number of items to return
            offset: Number of items to skip
            options: Additional options for the list operation
            
        Returns:
            Dictionary with operation result and items
        """
        options = options or {}
        
        try:
            items = []
            
            if backend:
                # List from specific backend
                if isinstance(backend, str):
                    try:
                        backend = StorageBackendType.from_string(backend)
                    except ValueError:
                        return {
                            "success": False,
                            "error": f"Invalid backend type: {backend}",
                            "error_type": "InvalidBackend"
                        }
                
                if backend not in self.backends:
                    return {
                        "success": False,
                        "error": f"Backend not available: {backend.value}",
                        "error_type": "BackendUnavailable"
                    }
                
                # Get backend instance
                backend_instance = self.backends[backend]
                
                # List items from backend
                result = backend_instance.list(
                    container=container,
                    prefix=prefix,
                    options=options
                )
                
                # Update stats
                self._update_stats("list", backend)
                
                if result.get("success", False):
                    # Get backend items
                    backend_items = result.get("items", [])
                    
                    # Apply pagination
                    paginated_items = backend_items[offset:offset+limit]
                    
                    # Try to match with content registry
                    for item in paginated_items:
                        identifier = item.get("identifier")
                        
                        # Look for content reference with this location
                        content_id = None
                        for cid, ref in self.content_registry.items():
                            if ref.get_location(backend) == identifier:
                                content_id = cid
                                break
                        
                        # Add to result list
                        items.append({
                            "backend": backend.value,
                            "identifier": identifier,
                            "content_id": content_id,
                            "details": item
                        })
                    
                    return {
                        "success": True,
                        "items": items,
                        "total": len(backend_items),
                        "limit": limit,
                        "offset": offset
                    }
                
                return result
            else:
                # List from content registry
                all_refs = list(self.content_registry.items())
                
                # Apply prefix filter
                if prefix:
                    all_refs = [(cid, ref) for cid, ref in all_refs if cid.startswith(prefix)]
                
                # Apply pagination
                paginated_refs = all_refs[offset:offset+limit]
                
                # Convert to result items
                for cid, ref in paginated_refs:
                    items.append({
                        "content_id": cid,
                        "locations": {k.value: v for k, v in ref.backend_locations.items()},
                        "metadata": ref.metadata,
                        "created_at": ref.created_at,
                        "last_accessed": ref.last_accessed,
                        "access_count": ref.access_count
                    })
                
                return {
                    "success": True,
                    "items": items,
                    "total": len(all_refs),
                    "limit": limit,
                    "offset": offset
                }
            
        except Exception as e:
            logger.exception(f"Error listing content: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def get_content_info(self, content_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a content item.
        
        Args:
            content_id: Content ID to retrieve info for
            
        Returns:
            Dictionary with content information
        """
        try:
            # Check if content exists in registry
            if content_id not in self.content_registry:
                return {
                    "success": False,
                    "error": f"Content ID not found: {content_id}",
                    "error_type": "ContentNotFound"
                }
            
            # Get content reference
            content_ref = self.content_registry[content_id]
            
            # Collect backend-specific metadata
            backend_metadata = {}
            
            for backend_type, location_id in content_ref.backend_locations.items():
                if backend_type in self.backends:
                    backend = self.backends[backend_type]
                    container = None
                    
                    # For S3, we need container information
                    if backend_type == StorageBackendType.S3:
                        # Check if container info is in the location ID
                        if ":" in location_id:
                            container, location_id = location_id.split(":", 1)
                        else:
                            # Use default bucket
                            container = backend.metadata.get("default_bucket")
                    
                    # Get metadata from backend
                    result = backend.get_metadata(
                        identifier=location_id,
                        container=container
                    )
                    
                    if result.get("success", False):
                        backend_metadata[backend_type.value] = result.get("metadata", {})
            
            return {
                "success": True,
                "content_id": content_id,
                "content_reference": content_ref.to_dict(),
                "backend_metadata": backend_metadata
            }
            
        except Exception as e:
            logger.exception(f"Error getting content info: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def replicate(
        self,
        content_id: str,
        target_backend: Union[StorageBackendType, str],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Replicate content to another backend.
        
        Args:
            content_id: Content ID to replicate
            target_backend: Backend to replicate to
            options: Additional options for the replication operation
            
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        
        try:
            # Check if content exists in registry
            if content_id not in self.content_registry:
                return {
                    "success": False,
                    "error": f"Content ID not found: {content_id}",
                    "error_type": "ContentNotFound"
                }
            
            # Get content reference
            content_ref = self.content_registry[content_id]
            
            # Convert target backend to enum if needed
            if isinstance(target_backend, str):
                try:
                    target_backend = StorageBackendType.from_string(target_backend)
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid target backend: {target_backend}",
                        "error_type": "InvalidBackend"
                    }
            
            # Check if target backend is available
            if target_backend not in self.backends:
                return {
                    "success": False,
                    "error": f"Target backend not available: {target_backend.value}",
                    "error_type": "BackendUnavailable"
                }
            
            # Check if content is already in target backend
            if content_ref.has_location(target_backend):
                return {
                    "success": True,
                    "content_id": content_id,
                    "message": f"Content already exists in {target_backend.value}",
                    "location": content_ref.get_location(target_backend)
                }
            
            # Retrieve data from any available backend
            retrieve_result = self.retrieve(content_id)
            
            if not retrieve_result.get("success", False):
                return {
                    "success": False,
                    "error": f"Failed to retrieve content: {retrieve_result.get('error')}",
                    "error_type": "RetrievalFailed"
                }
            
            # Get data
            data = retrieve_result.get("data")
            
            # Store in target backend
            target_backend_instance = self.backends[target_backend]
            container = options.get("container")
            path = options.get("path")
            
            store_result = target_backend_instance.store(
                data=data,
                container=container,
                path=path,
                options=options
            )
            
            if store_result.get("success", False):
                # Update content reference
                content_ref.add_location(target_backend, store_result["identifier"])
                
                # Save updated registry
                self._save_content_registry()
                
                return {
                    "success": True,
                    "content_id": content_id,
                    "target_backend": target_backend.value,
                    "location": store_result["identifier"],
                    "details": store_result
                }
            
            return {
                "success": False,
                "error": f"Failed to store in target backend: {store_result.get('error')}",
                "error_type": "StorageFailed",
                "details": store_result
            }
            
        except Exception as e:
            logger.exception(f"Error replicating content: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def update_metadata(
        self,
        content_id: str,
        metadata: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update metadata for content.
        
        Args:
            content_id: Content ID to update
            metadata: New metadata to set or update
            options: Additional options for the update operation
            
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        
        try:
            # Check if content exists in registry
            if content_id not in self.content_registry:
                return {
                    "success": False,
                    "error": f"Content ID not found: {content_id}",
                    "error_type": "ContentNotFound"
                }
            
            # Get content reference
            content_ref = self.content_registry[content_id]
            
            # Update metadata in the content reference
            content_ref.metadata.update(metadata)
            
            # Update backed-specific metadata if requested
            update_backends = options.get("update_backends", False)
            
            if update_backends:
                # Track backend update results
                backend_results = {}
                
                for backend_type, location_id in content_ref.backend_locations.items():
                    if backend_type in self.backends:
                        backend = self.backends[backend_type]
                        container = None
                        
                        # For S3, we need container information
                        if backend_type == StorageBackendType.S3:
                            # Check if container info is in the location ID
                            if ":" in location_id:
                                container, location_id = location_id.split(":", 1)
                            else:
                                # Use default bucket
                                container = backend.metadata.get("default_bucket")
                        
                        # Update metadata in backend
                        result = backend.update_metadata(
                            identifier=location_id,
                            metadata=metadata,
                            container=container,
                            options=options
                        )
                        
                        backend_results[backend_type.value] = result
            
            # Save updated registry
            self._save_content_registry()
            
            result = {
                "success": True,
                "content_id": content_id,
                "updated_metadata": content_ref.metadata
            }
            
            if update_backends:
                result["backend_results"] = backend_results
                
            return result
            
        except Exception as e:
            logger.exception(f"Error updating metadata: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def get_backends(self) -> List[Dict[str, Any]]:
        """
        Get information about available backends.
        
        Returns:
            List of backend information dictionaries
        """
        return [
            {
                "type": backend_type.value,
                "name": backend.get_name(),
                "usage_stats": self.stats["backend_usage"].get(backend_type.value, {})
            }
            for backend_type, backend in self.backends.items()
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        return {
            "operations": self.stats["operations"],
            "backend_usage": self.stats["backend_usage"],
            "content_count": self.stats["content_count"],
            "total_content_size": self.stats["total_content_size"],
            "available_backends": [b.value for b in self.backends]
        }
    
    def cleanup(self):
        """Clean up resources and save state."""
        logger.info("Cleaning up unified storage manager")
        self._save_content_registry()