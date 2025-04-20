"""
Unified Storage Manager implementation.

This module implements the UnifiedStorageManager class that coordinates
operations across all storage backends and provides a unified interface
for storage operations regardless of the underlying technology.
"""

import json
import logging
import os
import time
import uuid
import hashlib
from typing import Dict, List, Any, Optional, Union, BinaryIO, Tuple

from .storage_types import StorageBackendType, ContentReference
from .backend_base import BackendStorage
from ipfs_kit_py.mcp.controllers.migration_controller import MigrationController, MigrationPolicy

# Import backend implementations if available
try:
    from .backends.ipfs_backend import IPFSBackend
except ImportError:
    IPFSBackend = None

try:
    from .backends.s3_backend import S3Backend
except ImportError:
    S3Backend = None

try:
    from .backends.storacha_backend import StorachaBackend
except ImportError:
    StorachaBackend = None

try:
    from .backends.filecoin_backend import FilecoinBackend
except ImportError:
    FilecoinBackend = None

try:
    from .backends.huggingface_backend import HuggingFaceBackend
except ImportError:
    HuggingFaceBackend = None

try:
    from .backends.lassie_backend import LassieBackend
except ImportError:
    LassieBackend = None

# Configure logger
logger = logging.getLogger(__name__)


class UnifiedStorageManager:
    """
    Unified Storage Manager for coordinating storage operations across backends.

    This class provides a single interface for performing storage operations
    across multiple storage backends, with intelligent backend selection,
    content tracking, and migration capabilities.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        resources: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the unified storage manager.

        Args:
            config: Configuration options for the manager and backends
            resources: Shared resources for backend initialization
        """
        self.config = config or {}
        self.resources = resources or {}

        # Initialize storage for tracked content
        self.content_registry: Dict[str, ContentReference] = {}

        # Initialize available backends
        self.backends: Dict[StorageBackendType, BackendStorage] = {}
        self._initialize_backends()

        # Create migration controller
        self.migration_controller = MigrationController(
            storage_manager=self,
            options=self.config.get("migration", {}),
        )

        # Load content registry from disk if available
        self._load_content_registry()

    def _initialize_backends(self):
        """Initialize available storage backends based on configuration."""
        backend_configs = self.config.get("backends", {})

        # Initialize IPFS backend if enabled and available
        if backend_configs.get("ipfs", {}).get("enabled", True) and IPFSBackend:
            try:
                ipfs_config = backend_configs.get("ipfs", {})
                logger.info("Initializing IPFS backend")
                ipfs_backend = IPFSBackend(
                    resources=self.resources,
                    metadata=ipfs_config.get("metadata", {}),
                )
                self.backends[StorageBackendType.IPFS] = ipfs_backend
                logger.info("IPFS backend initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize IPFS backend: {e}")

        # Initialize S3 backend if enabled and available
        if backend_configs.get("s3", {}).get("enabled", False) and S3Backend:
            try:
                s3_config = backend_configs.get("s3", {})
                logger.info("Initializing S3 backend")
                s3_backend = S3Backend(
                    resources=self.resources,
                    metadata=s3_config.get("metadata", {}),
                )
                self.backends[StorageBackendType.S3] = s3_backend
                logger.info("S3 backend initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize S3 backend: {e}")

        # Initialize Storacha backend if enabled and available
        if backend_configs.get("storacha", {}).get("enabled", False) and StorachaBackend:
            try:
                storacha_config = backend_configs.get("storacha", {})
                logger.info("Initializing Storacha (Web3.Storage) backend")
                storacha_backend = StorachaBackend(
                    resources=self.resources,
                    metadata=storacha_config.get("metadata", {}),
                )
                self.backends[StorageBackendType.STORACHA] = storacha_backend
                logger.info("Storacha backend initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Storacha backend: {e}")

        # Initialize Filecoin backend if enabled and available
        if backend_configs.get("filecoin", {}).get("enabled", False) and FilecoinBackend:
            try:
                filecoin_config = backend_configs.get("filecoin", {})
                logger.info("Initializing Filecoin backend")
                filecoin_backend = FilecoinBackend(
                    resources=self.resources,
                    metadata=filecoin_config.get("metadata", {}),
                )
                self.backends[StorageBackendType.FILECOIN] = filecoin_backend
                logger.info("Filecoin backend initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Filecoin backend: {e}")

        # Initialize HuggingFace backend if enabled and available
        if backend_configs.get("huggingface", {}).get("enabled", False) and HuggingFaceBackend:
            try:
                huggingface_config = backend_configs.get("huggingface", {})
                logger.info("Initializing HuggingFace backend")
                huggingface_backend = HuggingFaceBackend(
                    resources=self.resources,
                    metadata=huggingface_config.get("metadata", {}),
                )
                self.backends[StorageBackendType.HUGGINGFACE] = huggingface_backend
                logger.info("HuggingFace backend initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize HuggingFace backend: {e}")

        # Initialize Lassie backend if enabled and available
        if backend_configs.get("lassie", {}).get("enabled", False) and LassieBackend:
            try:
                lassie_config = backend_configs.get("lassie", {})
                logger.info("Initializing Lassie backend")
                lassie_backend = LassieBackend(
                    resources=self.resources,
                    metadata=lassie_config.get("metadata", {}),
                )
                self.backends[StorageBackendType.LASSIE] = lassie_backend
                logger.info("Lassie backend initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Lassie backend: {e}")

        logger.info(f"Initialized {len(self.backends)} storage backends")

    def _load_content_registry(self):
        """Load content registry from disk if available."""
        registry_path = self.config.get("content_registry_path")
        
        if not registry_path:
            # Use default path in home directory
            registry_path = os.path.expanduser("~/.ipfs_kit_py/content_registry.json")
        
        try:
            if os.path.exists(registry_path):
                with open(registry_path, "r") as f:
                    registry_data = json.load(f)
                
                for content_id, data in registry_data.items():
                    self.content_registry[content_id] = ContentReference.from_dict(data)
                
                logger.info(f"Loaded {len(self.content_registry)} items from content registry")
            else:
                logger.info("Content registry file not found, starting with empty registry")
        except Exception as e:
            logger.error(f"Failed to load content registry: {e}")

    def _save_content_registry(self):
        """Save content registry to disk."""
        registry_path = self.config.get("content_registry_path")
        
        if not registry_path:
            # Use default path in home directory
            registry_dir = os.path.expanduser("~/.ipfs_kit_py")
            os.makedirs(registry_dir, exist_ok=True)
            registry_path = os.path.join(registry_dir, "content_registry.json")
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(registry_path), exist_ok=True)
            
            # Convert registry to JSON-serializable format
            registry_data = {
                content_id: content_ref.to_dict() 
                for content_id, content_ref in self.content_registry.items()
            }
            
            # Write to temporary file first
            temp_path = f"{registry_path}.tmp"
            with open(temp_path, "w") as f:
                json.dump(registry_data, f, indent=2)
            
            # Rename to target file (atomic operation)
            os.replace(temp_path, registry_path)
            
            logger.info(f"Saved {len(self.content_registry)} items to content registry")
        except Exception as e:
            logger.error(f"Failed to save content registry: {e}")

    def _select_backend(
        self, 
        data: Optional[Union[bytes, BinaryIO, str]] = None, 
        content_type: Optional[str] = None,
        size: Optional[int] = None,
        preference: Optional[Union[StorageBackendType, str]] = None
    ) -> Tuple[Optional[StorageBackendType], Optional[str]]:
        """
        Select the best backend for storing content based on various criteria.
        
        Args:
            data: The data to be stored (optional, for content-aware selection)
            content_type: MIME type of the content (optional)
            size: Size of the content in bytes (optional)
            preference: Preferred backend (optional)
            
        Returns:
            Tuple of (selected backend type, reason)
        """
        # If preference is specified and available, use it
        if preference:
            if isinstance(preference, str):
                try:
                    preference = StorageBackendType.from_string(preference)
                except ValueError:
                    # Invalid backend name, ignore preference
                    pass
            
            if preference in self.backends:
                return preference, "user_preference"
        
        # Get backend selection rules from config
        selection_rules = self.config.get("backend_selection", {})
        
        # Check content type rules
        if content_type and "content_type_rules" in selection_rules:
            for type_pattern, backend_name in selection_rules["content_type_rules"].items():
                if type_pattern in content_type:
                    try:
                        backend_type = StorageBackendType.from_string(backend_name)
                        if backend_type in self.backends:
                            return backend_type, f"content_type_rule:{type_pattern}"
                    except ValueError:
                        pass
        
        # Check size rules
        if size is not None and "size_rules" in selection_rules:
            for size_rule, backend_name in selection_rules["size_rules"].items():
                # Parse rule like ">=1000000" (greater than 1MB)
                if size_rule.startswith(">=") and size >= int(size_rule[2:]):
                    try:
                        backend_type = StorageBackendType.from_string(backend_name)
                        if backend_type in self.backends:
                            return backend_type, f"size_rule:{size_rule}"
                    except ValueError:
                        pass
                elif size_rule.startswith("<=") and size <= int(size_rule[2:]):
                    try:
                        backend_type = StorageBackendType.from_string(backend_name)
                        if backend_type in self.backends:
                            return backend_type, f"size_rule:{size_rule}"
                    except ValueError:
                        pass
        
        # If IPFS is available, use it as default
        if StorageBackendType.IPFS in self.backends:
            return StorageBackendType.IPFS, "default_ipfs"
        
        # Otherwise use the first available backend
        if self.backends:
            backend_type = next(iter(self.backends.keys()))
            return backend_type, "first_available"
        
        # No backends available
        return None, "no_backends_available"

    def _generate_content_id(self, data: Union[bytes, BinaryIO, str]) -> str:
        """
        Generate a unique content ID for the data.
        
        Args:
            data: The data to generate an ID for
            
        Returns:
            Content ID string
        """
        # Convert data to bytes if needed
        if isinstance(data, str):
            data_bytes = data.encode("utf-8")
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            # For file-like objects, read data and reset position
            current_pos = data.tell()
            data.seek(0)
            data_bytes = data.read()
            data.seek(current_pos)
        
        # Generate hash of the data
        content_hash = hashlib.sha256(data_bytes).hexdigest()
        
        # Generate a UUID based on the hash (consistent UUID derivation)
        namespace = uuid.UUID('00000000-0000-0000-0000-000000000000')
        content_uuid = uuid.uuid5(namespace, content_hash)
        
        return f"mcp-{content_uuid}"

    def _calculate_content_hash(self, data: Union[bytes, BinaryIO, str]) -> str:
        """
        Calculate a hash of the content for integrity verification.
        
        Args:
            data: The data to hash
            
        Returns:
            Content hash string
        """
        # Convert data to bytes if needed
        if isinstance(data, str):
            data_bytes = data.encode("utf-8")
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            # For file-like objects, read data and reset position
            current_pos = data.tell()
            data.seek(0)
            data_bytes = data.read()
            data.seek(current_pos)
        
        # Generate hash of the data
        content_hash = hashlib.sha256(data_bytes).hexdigest()
        
        return content_hash

    def store(
        self,
        data: Union[bytes, BinaryIO, str],
        backend_preference: Optional[Union[StorageBackendType, str]] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        container: Optional[str] = None,
        path: Optional[str] = None,
        content_id: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store content in the unified storage system.
        
        Args:
            data: Data to store (bytes, file-like object, or string)
            backend_preference: Preferred backend to use
            content_type: MIME type of the content
            metadata: Additional metadata about the content
            container: Container to store in (e.g., bucket for S3)
            path: Path within container
            content_id: Optional explicit content ID
            options: Additional options for storage
            
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        metadata = metadata or {}
        result = {
            "success": False,
            "operation": "store",
            "timestamp": time.time(),
        }
        
        try:
            # Calculate size if possible
            if isinstance(data, bytes):
                size = len(data)
            elif isinstance(data, str):
                size = len(data.encode("utf-8"))
            else:
                # Try to get size from file-like object
                try:
                    current_pos = data.tell()
                    data.seek(0, os.SEEK_END)
                    size = data.tell()
                    data.seek(current_pos)
                except (AttributeError, IOError):
                    size = None
            
            # Select backend
            backend_type, selection_reason = self._select_backend(
                data=data,
                content_type=content_type,
                size=size,
                preference=backend_preference,
            )
            
            if not backend_type:
                result["error"] = "No suitable storage backend available"
                result["error_type"] = "no_backend"
                return result
            
            # Get the backend instance
            backend = self.backends[backend_type]
            
            # Generate content ID if not provided
            if not content_id:
                content_id = self._generate_content_id(data)
            
            # Calculate content hash for integrity verification
            content_hash = self._calculate_content_hash(data)
            
            # Add metadata
            full_metadata = {
                "content_id": content_id,
                "content_hash": content_hash,
                "content_type": content_type,
                "stored_at": time.time(),
                "size": size,
                **metadata,
            }
            
            # Update options with metadata
            store_options = {**options, "metadata": full_metadata}
            
            # Store in backend
            logger.info(f"Storing content {content_id} in {backend_type.value} backend")
            backend_result = backend.store(
                data=data,
                container=container,
                path=path,
                options=store_options,
            )
            
            if not backend_result.get("success", False):
                result["error"] = backend_result.get("error", "Unknown error")
                result["error_type"] = backend_result.get("error_type", "storage_error")
                result["backend_result"] = backend_result
                return result
            
            # Get backend-specific identifier
            backend_identifier = backend_result.get("identifier")
            if not backend_identifier:
                result["error"] = "Backend did not return an identifier"
                result["error_type"] = "missing_identifier"
                result["backend_result"] = backend_result
                return result
            
            # Create or update content reference
            if content_id in self.content_registry:
                # Update existing reference
                content_ref = self.content_registry[content_id]
                content_ref.add_location(backend_type, backend_identifier)
                content_ref.metadata.update(full_metadata)
            else:
                # Create new reference
                content_ref = ContentReference(
                    content_id=content_id,
                    content_hash=content_hash,
                    backend_locations={backend_type: backend_identifier},
                    metadata=full_metadata,
                )
                self.content_registry[content_id] = content_ref
            
            # Save registry
            self._save_content_registry()
            
            # Return success result
            result["success"] = True
            result["content_id"] = content_id
            result["content_hash"] = content_hash
            result["backend"] = backend_type.value
            result["backend_id"] = backend_identifier
            result["selection_reason"] = selection_reason
            result["size"] = size
            
            return result
            
        except Exception as e:
            logger.exception(f"Error storing content: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result

    def retrieve(
        self,
        content_id: str,
        backend_preference: Optional[Union[StorageBackendType, str]] = None,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve content from the unified storage system.
        
        Args:
            content_id: Content ID to retrieve
            backend_preference: Preferred backend to use
            container: Container to retrieve from
            options: Additional options for retrieval
            
        Returns:
            Dictionary with operation result and content data
        """
        options = options or {}
        result = {
            "success": False,
            "operation": "retrieve",
            "timestamp": time.time(),
            "content_id": content_id,
        }
        
        try:
            # Check if content is tracked
            if content_id not in self.content_registry:
                result["error"] = f"Content ID not found: {content_id}"
                result["error_type"] = "content_not_found"
                return result
            
            # Get content reference
            content_ref = self.content_registry[content_id]
            content_ref.record_access()
            
            # Determine which backend to use
            backend_type = None
            backend_id = None
            
            # If preference is specified and content is available there, use it
            if backend_preference:
                if isinstance(backend_preference, str):
                    try:
                        backend_preference = StorageBackendType.from_string(backend_preference)
                    except ValueError:
                        # Invalid backend name, ignore preference
                        pass
                
                if content_ref.has_location(backend_preference):
                    backend_type = backend_preference
                    backend_id = content_ref.get_location(backend_preference)
                    result["backend_selection"] = "preference_match"
            
            # If no preference match, try backends in priority order
            if not backend_type:
                # Define backend priority from config or use default
                backend_priority = self.config.get(
                    "retrieval_priority", 
                    [
                        StorageBackendType.IPFS,
                        StorageBackendType.S3,
                        StorageBackendType.STORACHA,
                        StorageBackendType.FILECOIN,
                        StorageBackendType.HUGGINGFACE,
                        StorageBackendType.LASSIE,
                    ]
                )
                
                # Try backends in priority order
                for priority_backend in backend_priority:
                    if content_ref.has_location(priority_backend):
                        backend_type = priority_backend
                        backend_id = content_ref.get_location(priority_backend)
                        result["backend_selection"] = "priority_order"
                        break
            
            # If still no match, use any available backend
            if not backend_type:
                for available_backend, location_id in content_ref.backend_locations.items():
                    backend_type = available_backend
                    backend_id = location_id
                    result["backend_selection"] = "any_available"
                    break
            
            # If no backends have the content, return error
            if not backend_type or not backend_id:
                result["error"] = f"Content exists but is not available in any active backend"
                result["error_type"] = "no_backend_available"
                return result
            
            # Get the backend instance
            if backend_type not in self.backends:
                result["error"] = f"Backend {backend_type.value} is not available"
                result["error_type"] = "backend_unavailable"
                return result
            
            backend = self.backends[backend_type]
            
            # Retrieve from backend
            logger.info(f"Retrieving content {content_id} from {backend_type.value} backend")
            backend_result = backend.retrieve(
                identifier=backend_id,
                container=container,
                options=options,
            )
            
            if not backend_result.get("success", False):
                result["error"] = backend_result.get("error", "Unknown error")
                result["error_type"] = backend_result.get("error_type", "retrieval_error")
                result["backend_result"] = backend_result
                return result
            
            # Get data from backend result
            data = backend_result.get("data")
            if data is None:
                result["error"] = "Backend did not return any data"
                result["error_type"] = "missing_data"
                result["backend_result"] = backend_result
                return result
            
            # Verify content hash if available
            if content_ref.content_hash and isinstance(data, (bytes, str)):
                data_hash = self._calculate_content_hash(data)
                if data_hash != content_ref.content_hash:
                    result["warning"] = "Content hash mismatch"
                    result["expected_hash"] = content_ref.content_hash
                    result["actual_hash"] = data_hash
            
            # Save registry with updated access info
            self._save_content_registry()
            
            # Return success result
            result["success"] = True
            result["data"] = data
            result["backend"] = backend_type.value
            result["backend_id"] = backend_id
            result["metadata"] = content_ref.metadata
            result["content_hash"] = content_ref.content_hash
            
            return result
            
        except Exception as e:
            logger.exception(f"Error retrieving content: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result

    def delete(
        self,
        content_id: str,
        backend: Optional[Union[StorageBackendType, str]] = None,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete content from the unified storage system.
        
        Args:
            content_id: Content ID to delete
            backend: Specific backend to delete from (or all if None)
            container: Container to delete from
            options: Additional options for deletion
            
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        result = {
            "success": False,
            "operation": "delete",
            "timestamp": time.time(),
            "content_id": content_id,
        }
        
        try:
            # Check if content is tracked
            if content_id not in self.content_registry:
                result["error"] = f"Content ID not found: {content_id}"
                result["error_type"] = "content_not_found"
                return result
            
            # Get content reference
            content_ref = self.content_registry[content_id]
            
            # Convert backend to enum if needed
            if backend is not None and isinstance(backend, str):
                try:
                    backend = StorageBackendType.from_string(backend)
                except ValueError:
                    result["error"] = f"Invalid backend type: {backend}"
                    result["error_type"] = "invalid_backend"
                    return result
            
            # Determine which backends to delete from
            if backend is None:
                # Delete from all backends
                backends_to_delete = list(content_ref.backend_locations.keys())
            else:
                # Delete from specific backend
                if not content_ref.has_location(backend):
                    result["error"] = f"Content not found in backend: {backend.value}"
                    result["error_type"] = "backend_location_not_found"
                    return result
                backends_to_delete = [backend]
            
            # Delete from each backend
            delete_results = {}
            overall_success = True
            
            for backend_type in backends_to_delete:
                # Skip if backend is not available
                if backend_type not in self.backends:
                    delete_results[backend_type.value] = {
                        "success": False,
                        "error": "Backend not available",
                        "error_type": "backend_unavailable",
                    }
                    overall_success = False
                    continue
                
                # Get backend instance and identifier
                backend_instance = self.backends[backend_type]
                backend_id = content_ref.get_location(backend_type)
                
                # Delete from backend
                logger.info(f"Deleting content {content_id} from {backend_type.value} backend")
                backend_result = backend_instance.delete(
                    identifier=backend_id,
                    container=container,
                    options=options,
                )
                
                delete_results[backend_type.value] = backend_result
                
                if backend_result.get("success", False):
                    # Remove location from content reference
                    content_ref.remove_location(backend_type)
                else:
                    overall_success = False
            
            # Update or remove content reference
            if not content_ref.backend_locations:
                # Content is not stored anywhere, remove from registry
                del self.content_registry[content_id]
                result["removed_from_registry"] = True
            else:
                # Content still exists in some backends
                result["remaining_backends"] = list(content_ref.backend_locations.keys())
            
            # Save registry
            self._save_content_registry()
            
            # Return result
            result["success"] = overall_success
            result["backend_results"] = delete_results
            result["deleted_from"] = [
                backend_type.value
                for backend_type in backends_to_delete
                if delete_results.get(backend_type.value, {}).get("success", False)
            ]
            
            if not overall_success:
                result["warning"] = "Some backends failed to delete the content"
            
            return result
            
        except Exception as e:
            logger.exception(f"Error deleting content: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result

    def list_content(
        self,
        backend: Optional[Union[StorageBackendType, str]] = None,
        container: Optional[str] = None,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        List content in the unified storage system.
        
        Args:
            backend: Filter by backend
            container: Filter by container
            prefix: Filter by prefix
            limit: Maximum number of items to return
            offset: Number of items to skip
            options: Additional options for listing
            
        Returns:
            Dictionary with operation result and content list
        """
        options = options or {}
        result = {
            "success": False,
            "operation": "list_content",
            "timestamp": time.time(),
        }
        
        try:
            # Convert backend to enum if needed
            if backend is not None and isinstance(backend, str):
                try:
                    backend = StorageBackendType.from_string(backend)
                except ValueError:
                    result["error"] = f"Invalid backend type: {backend}"
                    result["error_type"] = "invalid_backend"
                    return result
            
            # Filter content based on criteria
            filtered_content = {}
            
            for content_id, content_ref in self.content_registry.items():
                # Filter by backend if specified
                if backend is not None and not content_ref.has_location(backend):
                    continue
                
                # Filter by prefix if specified
                if prefix is not None and not content_id.startswith(prefix):
                    continue
                
                # Add to filtered content
                filtered_content[content_id] = content_ref
            
            # Sort content by creation time (newest first)
            sorted_content = sorted(
                filtered_content.items(), 
                key=lambda x: x[1].created_at, 
                reverse=True
            )
            
            # Apply pagination
            paginated_content = sorted_content[offset : offset + limit]
            
            # Format results
            content_list = []
            for content_id, content_ref in paginated_content:
                content_list.append({
                    "content_id": content_id,
                    "content_hash": content_ref.content_hash,
                    "backends": [
                        {
                            "backend": backend_type.value,
                            "location": location_id,
                        }
                        for backend_type, location_id in content_ref.backend_locations.items()
                    ],
                    "metadata": content_ref.metadata,
                    "created_at": content_ref.created_at,
                    "last_accessed": content_ref.last_accessed,
                    "access_count": content_ref.access_count,
                })
            
            # Return success result
            result["success"] = True
            result["items"] = content_list
            result["total"] = len(filtered_content)
            result["limit"] = limit
            result["offset"] = offset
            result["has_more"] = (offset + limit) < len(filtered_content)
            
            return result
            
        except Exception as e:
            logger.exception(f"Error listing content: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result

    def get_content_info(self, content_id: str) -> Dict[str, Any]:
        """
        Get information about a specific content item.
        
        Args:
            content_id: Content ID to get information for
            
        Returns:
            Dictionary with content information
        """
        result = {
            "success": False,
            "operation": "get_content_info",
            "timestamp": time.time(),
            "content_id": content_id,
        }
        
        try:
            # Check if content is tracked
            if content_id not in self.content_registry:
                result["error"] = f"Content ID not found: {content_id}"
                result["error_type"] = "content_not_found"
                return result
            
            # Get content reference
            content_ref = self.content_registry[content_id]
            
            # Get backend details
            backend_details = []
            for backend_type, location_id in content_ref.backend_locations.items():
                backend_info = {
                    "backend": backend_type.value,
                    "location": location_id,
                    "backend_available": backend_type in self.backends,
                }
                
                # Try to get metadata from backend if available
                if backend_type in self.backends:
                    try:
                        backend = self.backends[backend_type]
                        metadata_result = backend.get_metadata(
                            identifier=location_id,
                            options={"timeout": 5},  # Set a short timeout
                        )
                        
                        if metadata_result.get("success", False):
                            backend_info["backend_metadata"] = metadata_result.get("metadata", {})
                    except Exception as e:
                        backend_info["metadata_error"] = str(e)
                
                backend_details.append(backend_info)
            
            # Return success result
            result["success"] = True
            result["content_hash"] = content_ref.content_hash
            result["backends"] = backend_details
            result["metadata"] = content_ref.metadata
            result["created_at"] = content_ref.created_at
            result["last_accessed"] = content_ref.last_accessed
            result["access_count"] = content_ref.access_count
            
            return result
            
        except Exception as e:
            logger.exception(f"Error getting content info: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result

    def search_content(
        self,
        query: str,
        search_metadata: bool = True,
        search_content_ids: bool = True,
        backend: Optional[Union[StorageBackendType, str]] = None,
        limit: int = 100,
        offset: int = 0,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Search for content in the unified storage system.
        
        Args:
            query: Search query string
            search_metadata: Whether to search in metadata
            search_content_ids: Whether to search in content IDs
            backend: Filter by backend
            limit: Maximum number of items to return
            offset: Number of items to skip
            options: Additional options for searching
            
        Returns:
            Dictionary with search results
        """
        options = options or {}
        result = {
            "success": False,
            "operation": "search_content",
            "timestamp": time.time(),
            "query": query,
        }
        
        try:
            # Check if query is provided
            if not query:
                result["error"] = "Search query is required"
                result["error_type"] = "missing_query"
                return result
            
            # Convert backend to enum if needed
            if backend is not None and isinstance(backend, str):
                try:
                    backend = StorageBackendType.from_string(backend)
                except ValueError:
                    result["error"] = f"Invalid backend type: {backend}"
                    result["error_type"] = "invalid_backend"
                    return result
            
            # Convert query to lowercase for case-insensitive search
            query_lower = query.lower()
            
            # Search content
            matching_content = {}
            
            for content_id, content_ref in self.content_registry.items():
                # Filter by backend if specified
                if backend is not None and not content_ref.has_location(backend):
                    continue
                
                # Search in content ID if enabled
                if search_content_ids and query_lower in content_id.lower():
                    matching_content[content_id] = content_ref
                    continue
                
                # Search in metadata if enabled
                if search_metadata:
                    metadata_str = json.dumps(content_ref.metadata).lower()
                    if query_lower in metadata_str:
                        matching_content[content_id] = content_ref
                        continue
            
            # Sort by relevance (currently just creation time)
            sorted_content = sorted(
                matching_content.items(), 
                key=lambda x: x[1].created_at, 
                reverse=True
            )
            
            # Apply pagination
            paginated_content = sorted_content[offset : offset + limit]
            
            # Format results
            search_results = []
            for content_id, content_ref in paginated_content:
                search_results.append({
                    "content_id": content_id,
                    "content_hash": content_ref.content_hash,
                    "backends": [
                        {
                            "backend": backend_type.value,
                            "location": location_id,
                        }
                        for backend_type, location_id in content_ref.backend_locations.items()
                    ],
                    "metadata": content_ref.metadata,
                    "created_at": content_ref.created_at,
                    "last_accessed": content_ref.last_accessed,
                    "access_count": content_ref.access_count,
                })
            
            # Return success result
            result["success"] = True
            result["items"] = search_results
            result["total"] = len(matching_content)
            result["limit"] = limit
            result["offset"] = offset
            result["has_more"] = (offset + limit) < len(matching_content)
            
            return result
            
        except Exception as e:
            logger.exception(f"Error searching content: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result

    def migrate_content(
        self,
        content_id: str,
        source_backend: Union[StorageBackendType, str],
        target_backend: Union[StorageBackendType, str],
        delete_source: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Migrate content from one backend to another.
        
        Args:
            content_id: Content ID to migrate
            source_backend: Source backend
            target_backend: Target backend
            delete_source: Whether to delete content from source after migration
            options: Additional options for migration
            
        Returns:
            Dictionary with operation result
        """
        options = options or {}
        result = {
            "success": False,
            "operation": "migrate_content",
            "timestamp": time.time(),
            "content_id": content_id,
        }
        
        # Set up migration options
        migration_options = {
            **options,
            "delete_source": delete_source,
        }
        
        # Use migration controller to create and execute a migration task
        task_result = self.migration_controller.add_task(
            content_id=content_id,
            source_backend=source_backend,
            target_backend=target_backend,
            priority=options.get("priority", 2),  # Default to HIGH priority
            options=migration_options,
        )
        
        if not task_result.get("success", False):
            return task_result
        
        task_id = task_result.get("task_id")
        
        # If this is a synchronous request, wait for task to complete
        if options.get("synchronous", False):
            max_wait_time = options.get("timeout", 60)  # Default timeout of 60 seconds
            wait_interval = 0.5  # Check every 0.5 seconds
            
            total_waited = 0
            while total_waited < max_wait_time:
                # Get task status
                task_info = self.migration_controller.get_task(task_id)
                
                if not task_info:
                    result["error"] = f"Migration task {task_id} not found"
                    result["error_type"] = "task_not_found"
                    return result
                
                # Check if task is completed
                if task_info.get("status") in ["completed", "failed", "cancelled"]:
                    # Task is done, return result
                    result["success"] = task_info.get("status") == "completed"
                    result["task_id"] = task_id
                    result["task_status"] = task_info.get("status")
                    result["task"] = task_info
                    
                    if task_info.get("status") == "failed":
                        result["error"] = task_info.get("error", "Unknown error")
                        result["error_type"] = "migration_failed"
                    
                    return result
                
                # Wait before checking again
                time.sleep(wait_interval)
                total_waited += wait_interval
            
            # Timeout reached
            result["success"] = False
            result["error"] = f"Migration timed out after {max_wait_time} seconds"
            result["error_type"] = "migration_timeout"
            result["task_id"] = task_id
            return result
        
        # Asynchronous request, return task information
        result["success"] = True
        result["task_id"] = task_id
        result["async"] = True
        result["message"] = "Migration task created successfully"
        
        return result

    def create_migration_policy(
        self,
        name: str,
        source_backend: Union[StorageBackendType, str],
        target_backend: Union[StorageBackendType, str],
        criteria: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a migration policy.
        
        Args:
            name: Policy name
            source_backend: Source backend
            target_backend: Target backend
            criteria: Criteria for selecting content to migrate
            description: Policy description
            options: Additional policy options
            
        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "create_migration_policy",
            "timestamp": time.time(),
            "policy_name": name,
        }
        
        try:
            # Create policy
            policy = MigrationPolicy(
                name=name,
                source_backend=source_backend,
                target_backend=target_backend,
                description=description,
                criteria=criteria,
                options=options,
            )
            
            # Add to migration controller
            add_result = self.migration_controller.add_policy(policy)
            
            if not add_result:
                result["error"] = f"Failed to add policy, name may already exist: {name}"
                result["error_type"] = "policy_add_failed"
                return result
            
            # Return success result
            result["success"] = True
            result["policy"] = policy.to_dict()
            
            return result
            
        except Exception as e:
            logger.exception(f"Error creating migration policy: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result

    def get_backend_status(self) -> Dict[str, Any]:
        """
        Get status information about all available backends.
        
        Returns:
            Dictionary with backend status information
        """
        result = {
            "success": True,
            "operation": "get_backend_status",
            "timestamp": time.time(),
            "backends": {},
        }
        
        # Check each backend
        for backend_type, backend in self.backends.items():
            backend_info = {
                "backend_type": backend_type.value,
                "available": True,
                "name": backend.get_name(),
            }
            
            # Try to get more specific status information if possible
            try:
                if hasattr(backend, "get_status"):
                    status = backend.get_status()
                    backend_info["status"] = status
            except Exception as e:
                backend_info["status_error"] = str(e)
            
            # Add to result
            result["backends"][backend_type.value] = backend_info
        
        # Add information about content distribution
        backend_counts = {}
        for backend_type in StorageBackendType:
            backend_counts[backend_type.value] = 0
        
        for content_ref in self.content_registry.values():
            for backend_type in content_ref.backend_locations.keys():
                backend_counts[backend_type.value] += 1
        
        result["content_distribution"] = backend_counts
        result["total_content"] = len(self.content_registry)
        
        return result

    def get_migration_status(self) -> Dict[str, Any]:
        """
        Get status information about the migration controller.
        
        Returns:
            Dictionary with migration status information
        """
        # Get statistics from migration controller
        stats = self.migration_controller.get_statistics()
        
        result = {
            "success": True,
            "operation": "get_migration_status",
            "timestamp": time.time(),
            "migration_controller": stats,
            "policies": self.migration_controller.list_policies(),
        }
        
        return result