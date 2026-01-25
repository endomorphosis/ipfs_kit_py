#!/usr/bin/env python3
"""
Unified Bucket-Based Interface for Multiple Filesystem Backends

This module provides a unified bucket-based interface for all filesystem backends
(Parquet, Arrow, SSHFS, FTP, Google Drive, S3) where content-addressed "pins" 
are stored in buckets and composed into a virtual filesystem in the .ipfs_kit folder.

Key Features:
- Subfolder mapping per bucket in ~/.ipfs_kit/buckets/<backend>/<bucket_name>/
- VFS and pin metadata indices maintained for each subfolder
- Content-addressed pin storage with bucket organization
- Cross-backend VFS composition and querying
"""

import anyio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Tuple

import aiofiles

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

from .bucket_vfs_manager import BucketVFSManager, BucketType, VFSStructureType
from .enhanced_bucket_index import EnhancedBucketIndex
from .pins import EnhancedPinMetadataIndex
from .error import create_result_dict
# NOTE: This file contains asyncio.create_task() calls that need task group context

logger = logging.getLogger(__name__)


class BackendType(Enum):
    """Supported filesystem backend types."""
    PARQUET = "parquet"
    ARROW = "arrow"
    SSHFS = "sshfs"
    FTP = "ftp"
    GDRIVE = "gdrive"
    S3 = "s3"
    IPFS = "ipfs"
    LOTUS = "lotus"
    STORACHA = "storacha"
    HUGGINGFACE = "huggingface"
    GITHUB = "github"
    SYNAPSE = "synapse"
    IPFS_CLUSTER = "ipfs_cluster"
    CLUSTER_FOLLOW = "cluster_follow"


class PinStatus(Enum):
    """Status of content-addressed pins."""
    ACTIVE = "active"
    PENDING = "pending"
    FAILED = "failed"
    ARCHIVED = "archived"
    REPLICATED = "replicated"


class UnifiedBucketInterface:
    """
    Unified bucket-based interface for multiple filesystem backends.
    
    Manages bucket organization in ~/.ipfs_kit/ with:
    - Per-backend subfolders
    - Per-bucket VFS metadata
    - Content-addressed pin indices
    - Cross-backend composition
    """
    
    def __init__(
        self,
        ipfs_kit_dir: Optional[str] = None,
        enable_cross_backend_queries: bool = True,
        auto_sync_interval: int = 300  # 5 minutes
    ):
        """
        Initialize unified bucket interface.
        
        Args:
            ipfs_kit_dir: Base directory (defaults to ~/.ipfs_kit)
            enable_cross_backend_queries: Enable cross-backend SQL queries
            auto_sync_interval: Auto-sync interval in seconds
        """
        self.ipfs_kit_dir = Path(ipfs_kit_dir or os.path.expanduser("~/.ipfs_kit"))
        self.ipfs_kit_dir.mkdir(parents=True, exist_ok=True)
        
        # Core directories
        self.buckets_dir = self.ipfs_kit_dir / "buckets"
        self.buckets_dir.mkdir(parents=True, exist_ok=True)
        
        self.pin_metadata_dir = self.ipfs_kit_dir / "pin_metadata"
        self.pin_metadata_dir.mkdir(parents=True, exist_ok=True)
        
        self.bucket_index_dir = self.ipfs_kit_dir / "bucket_index"
        self.bucket_index_dir.mkdir(parents=True, exist_ok=True)
        
        self.vfs_indices_dir = self.ipfs_kit_dir / "vfs_indices"
        self.vfs_indices_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.enable_cross_backend_queries = enable_cross_backend_queries and DUCKDB_AVAILABLE
        self.auto_sync_interval = auto_sync_interval
        
        # Backend managers
        self.backend_managers: Dict[BackendType, Any] = {}
        self.bucket_vfs_managers: Dict[BackendType, BucketVFSManager] = {}
        
        # Indices
        self.global_bucket_index = EnhancedBucketIndex(
            index_dir=str(self.bucket_index_dir)
        )
        self.global_pin_index = EnhancedPinMetadataIndex(
            data_dir=str(self.pin_metadata_dir)
        )
        
        # Cross-backend query engine
        if self.enable_cross_backend_queries:
            self.duckdb_conn = duckdb.connect(str(self.ipfs_kit_dir / "unified_vfs.duckdb"))
        else:
            self.duckdb_conn = None
        
        # Registry for active buckets
        self.bucket_registry: Dict[str, Dict[str, Any]] = {}
        self.registry_file = self.ipfs_kit_dir / "bucket_registry.json"
        
        # Background sync task
        self._sync_task: Optional[asyncio.Task] = None
        self._shutdown_event = anyio.Event()
        
        logger.info(f"Unified Bucket Interface initialized at {self.ipfs_kit_dir}")
    
    async def initialize(self):
        """Initialize the unified bucket interface."""
        try:
            # Load existing bucket registry
            await self._load_bucket_registry()
            
            # Initialize backend managers
            await self._initialize_backend_managers()
            
            # Start background sync
            if self.auto_sync_interval > 0:
                self._sync_task = asyncio.create_task(self._background_sync())
            
            logger.info("Unified Bucket Interface initialization complete")
            return create_result_dict("initialize", success=True)
            
        except Exception as e:
            logger.error(f"Failed to initialize unified bucket interface: {e}")
            return create_result_dict("initialize", success=False, error=str(e))
    
    async def create_backend_bucket(
        self,
        backend: BackendType,
        bucket_name: str,
        bucket_type: BucketType = BucketType.GENERAL,
        vfs_structure: VFSStructureType = VFSStructureType.HYBRID,
        backend_config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new bucket for a specific backend.
        
        Args:
            backend: Target backend type
            bucket_name: Unique bucket name within backend
            bucket_type: Type of bucket to create
            vfs_structure: VFS structure type
            backend_config: Backend-specific configuration
            metadata: Additional bucket metadata
        """
        try:
            # Create bucket directory structure directly under buckets/
            bucket_dir = self.buckets_dir / bucket_name
            if bucket_dir.exists():
                return create_result_dict(
                    "create_backend_bucket",
                    success=False,
                    error=f"Bucket '{bucket_name}' already exists"
                )
            
            # Create bucket VFS manager for this bucket
            # Use bucket name as key instead of backend
            bucket_key = bucket_name
            if bucket_key not in self.bucket_vfs_managers:
                self.bucket_vfs_managers[bucket_key] = BucketVFSManager(
                    storage_path=str(bucket_dir),
                    enable_parquet_export=True,
                    enable_duckdb_integration=self.enable_cross_backend_queries
                )
            
            bucket_manager = self.bucket_vfs_managers[bucket_key]
            
            # Create bucket
            result = await bucket_manager.create_bucket(
                bucket_name=bucket_name,
                bucket_type=bucket_type,
                vfs_structure=vfs_structure,
                metadata={
                    **(metadata or {}),
                    "backend": backend.value,
                    "backend_config": backend_config or {},
                    "created_via": "unified_interface"
                }
            )
            
            if not result["success"]:
                return result
            
            # Create VFS index directory for this bucket (directly under vfs_indices)
            vfs_index_dir = self.vfs_indices_dir / bucket_name
            vfs_index_dir.mkdir(parents=True, exist_ok=True)
            
            # Create pin metadata directory for this bucket (directly under pin_metadata)
            pin_dir = self.pin_metadata_dir / bucket_name
            pin_dir.mkdir(parents=True, exist_ok=True)
            
            # Register bucket (use bucket name directly as key)
            self.bucket_registry[bucket_name] = {
                "backend": backend.value,
                "bucket_name": bucket_name,
                "bucket_type": bucket_type.value,
                "vfs_structure": vfs_structure.value,
                "storage_path": str(bucket_dir),
                "vfs_index_path": str(vfs_index_dir),
                "pin_metadata_path": str(pin_dir),
                "created_at": datetime.utcnow().isoformat(),
                "backend_config": backend_config or {},
                "metadata": metadata or {}
            }
            
            # Save registry
            await self._save_bucket_registry()
            
            # Update global indices
            await self._update_global_indices()
            
            logger.info(f"Created bucket '{bucket_name}' for backend '{backend.value}'")
            
            return create_result_dict(
                "create_backend_bucket",
                success=True,
                data={
                    "bucket_name": bucket_name,
                    "backend": backend.value,
                    "storage_path": str(bucket_dir),
                    "vfs_index_path": str(vfs_index_dir),
                    "pin_metadata_path": str(pin_dir)
                }
            )
            
        except Exception as e:
            logger.error(f"Error creating backend bucket: {e}")
            return create_result_dict(
                "create_backend_bucket",
                success=False,
                error=f"Failed to create bucket: {str(e)}"
            )
    
    async def add_content_pin(
        self,
        backend: BackendType,
        bucket_name: str,
        content_hash: str,
        file_path: str,
        content: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add content-addressed pin to a bucket.
        
        Args:
            backend: Target backend
            bucket_name: Target bucket name
            content_hash: Content hash (CID or similar)
            file_path: Virtual file path within bucket
            content: File content
            metadata: Additional pin metadata
        """
        try:
            # Use bucket name directly as key
            print(f"DEBUG: Looking for bucket '{bucket_name}' in registry")
            print(f"DEBUG: Registry keys: {list(self.bucket_registry.keys())}")
            if bucket_name not in self.bucket_registry:
                return create_result_dict(
                    "add_content_pin",
                    success=False,
                    error=f"Bucket '{bucket_name}' not found for backend '{backend.value}'"
                )
            
            print(f"DEBUG: Bucket found in registry")
            # Get bucket manager (now keyed by bucket name)
            bucket_manager = self.bucket_vfs_managers.get(bucket_name)
            print(f"DEBUG: Bucket manager for '{bucket_name}': {bucket_manager is not None}")
            if not bucket_manager:
                return create_result_dict(
                    "add_content_pin",
                    success=False,
                    error=f"Bucket manager for '{bucket_name}' not initialized"
                )
            
            print(f"DEBUG: Getting bucket '{bucket_name}' from manager")
            print(f"DEBUG: Manager buckets: {list(bucket_manager.buckets.keys())}")
            bucket = await bucket_manager.get_bucket(bucket_name)
            print(f"DEBUG: Bucket from manager: {bucket is not None}")
            if not bucket:
                return create_result_dict(
                    "add_content_pin",
                    success=False,
                    error=f"Bucket '{bucket_name}' not found"
                )
            
            # Add content to bucket VFS
            add_result = await bucket.add_file(
                file_path=file_path,
                content=content,
                metadata={
                    **(metadata or {}),
                    "content_hash": content_hash,
                    "backend": backend.value,
                    "bucket_name": bucket_name,
                    "pin_status": PinStatus.ACTIVE.value,
                    "added_at": datetime.utcnow().isoformat()
                }
            )
            
            if not add_result["success"]:
                return add_result
            
            # Update pin metadata index
            pin_metadata = {
                "cid": content_hash,
                "bucket": bucket_name,
                "backend": backend.value,
                "file_path": file_path,
                "size": len(content) if isinstance(content, (bytes, str)) else 0,
                "status": PinStatus.ACTIVE.value,
                "created_at": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
            
            # Save pin metadata to bucket-specific directory (prefer Parquet over JSON)
            pin_dir = Path(self.bucket_registry[bucket_name]["pin_metadata_path"])
            
            # Save as Parquet if Arrow is available
            if ARROW_AVAILABLE:
                await self._save_pin_metadata_parquet(pin_dir, content_hash, pin_metadata)
                pin_file = pin_dir / f"{content_hash}.parquet"
            else:
                # Fallback to JSON if Arrow not available
                pin_file = pin_dir / f"{content_hash}.json"
                async with aiofiles.open(pin_file, 'w') as f:
                    await f.write(json.dumps(pin_metadata, indent=2))
            
            # Update VFS index
            await self._update_vfs_index(backend, bucket_name, file_path, pin_metadata)
            
            # Update global indices
            await self._update_global_indices()
            
            logger.info(f"Added pin '{content_hash}' to bucket '{bucket_name}' on backend '{backend.value}'")
            
            return create_result_dict(
                "add_content_pin",
                success=True,
                data={
                    "content_hash": content_hash,
                    "bucket_name": bucket_name,
                    "file_path": file_path,
                    "pin_metadata_path": str(pin_file)
                }
            )
            
        except Exception as e:
            logger.error(f"Error adding content pin: {e}")
            return create_result_dict(
                "add_content_pin",
                success=False,
                error=f"Failed to add pin: {str(e)}"
            )
    
    async def list_all_pins(self) -> Dict[str, Any]:
        """List all pins across all managed buckets."""
        if not self.global_pin_index:
            return create_result_dict("list_all_pins", success=False, error="Global pin index not initialized")

        try:
            all_pins = self.global_pin_index.get_all_pins()
            return create_result_dict("list_all_pins", success=True, data={"pins": all_pins})
        except Exception as e:
            logger.error(f"Error listing all pins: {e}")
            return create_result_dict("list_all_pins", success=False, error=str(e))
    
    async def list_backend_buckets(self, backend: Optional[BackendType] = None) -> Dict[str, Any]:
        """
        List buckets, optionally filtered by backend.
        
        Args:
            backend: Optional backend filter
        """
        try:
            buckets = []
            
            for bucket_id, bucket_info in self.bucket_registry.items():
                if backend and bucket_info["backend"] != backend.value:
                    continue
                
                # Get bucket statistics
                bucket_stats = await self._get_bucket_statistics(
                    BackendType(bucket_info["backend"]),
                    bucket_info["bucket_name"]
                )
                
                bucket_data = {
                    "bucket_id": bucket_id,
                    "backend": bucket_info["backend"],
                    "bucket_name": bucket_info["bucket_name"],
                    "bucket_type": bucket_info["bucket_type"],
                    "vfs_structure": bucket_info["vfs_structure"],
                    "created_at": bucket_info["created_at"],
                    "storage_path": bucket_info["storage_path"],
                    "pin_count": bucket_stats.get("pin_count", 0),
                    "total_size": bucket_stats.get("total_size", 0),
                    "last_modified": bucket_stats.get("last_modified"),
                    "vfs_files": bucket_stats.get("vfs_files", 0)
                }
                buckets.append(bucket_data)
            
            # Sort by creation time
            buckets.sort(key=lambda x: x["created_at"], reverse=True)
            
            return create_result_dict(
                "list_backend_buckets",
                success=True,
                data={
                    "buckets": buckets,
                    "total_count": len(buckets),
                    "backend_filter": backend.value if backend else None
                }
            )
            
        except Exception as e:
            logger.error(f"Error listing backend buckets: {e}")
            return create_result_dict(
                "list_backend_buckets",
                success=False,
                error=f"Failed to list buckets: {str(e)}"
            )
    
    async def list_all_pins(self) -> Dict[str, Any]:
        """List all pins across all managed buckets."""
        if not self.global_pin_index:
            return create_result_dict("list_all_pins", success=False, error="Global pin index not initialized")

        try:
            all_pins = self.global_pin_index.get_all_pins()
            return create_result_dict("list_all_pins", success=True, data={"pins": all_pins})
        except Exception as e:
            logger.error(f"Error listing all pins: {e}")
            return create_result_dict("list_all_pins", success=False, error=str(e))

    async def remove_pin(self, cid: str) -> Dict[str, Any]:
        """Remove a pin by CID."""
        if not self.global_pin_index:
            return create_result_dict("remove_pin", success=False, error="Global pin index not initialized")

        try:
            result = self.global_pin_index.remove_pin(cid)
            if result["success"]:
                return create_result_dict("remove_pin", success=True, message=f"Pin {cid} removed successfully.")
            else:
                return create_result_dict("remove_pin", success=False, error=result["error"])
        except Exception as e:
            logger.error(f"Error removing pin {cid}: {e}")
            return create_result_dict("remove_pin", success=False, error=str(e))

    async def update_bucket(
        self,
        bucket_name: str,
        backend_config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update an existing bucket's configuration or metadata."""
        if bucket_name not in self.bucket_registry:
            return create_result_dict("update_bucket", success=False, error=f"Bucket '{bucket_name}' not found")

        try:
            bucket_info = self.bucket_registry[bucket_name]
            
            # Update backend_config and metadata
            if backend_config is not None:
                bucket_info["backend_config"] = {**bucket_info.get("backend_config", {}), **backend_config}
            if metadata is not None:
                bucket_info["metadata"] = {**bucket_info.get("metadata", {}), **metadata}
            
            bucket_info["last_modified"] = datetime.utcnow().isoformat()

            # Save updated registry
            await self._save_bucket_registry()
            
            # Update the underlying bucket VFS manager if necessary
            bucket_manager = self.bucket_vfs_managers.get(bucket_name)
            if bucket_manager:
                # Assuming BucketVFSManager has an update_bucket_metadata method
                # This might need to be implemented in BucketVFSManager if it doesn't exist
                if hasattr(bucket_manager, 'update_bucket_metadata'):
                    await bucket_manager.update_bucket_metadata(bucket_name, metadata=bucket_info["metadata"])

            return create_result_dict("update_bucket", success=True, message=f"Bucket '{bucket_name}' updated successfully.")
        except Exception as e:
            logger.error(f"Error updating bucket {bucket_name}: {e}")
            return create_result_dict("update_bucket", success=False, error=str(e))

    async def get_content_from_bucket(self, bucket_name: str, file_path: str) -> Dict[str, Any]:
        """Get content of a file from a specific bucket."""
        if bucket_name not in self.bucket_registry:
            return create_result_dict("get_content_from_bucket", success=False, error=f"Bucket '{bucket_name}' not found")

        try:
            bucket_manager = self.bucket_vfs_managers.get(bucket_name)
            if not bucket_manager:
                return create_result_dict("get_content_from_bucket", success=False, error=f"Bucket manager for '{bucket_name}' not initialized")

            bucket = await bucket_manager.get_bucket(bucket_name)
            if not bucket:
                return create_result_dict("get_content_from_bucket", success=False, error=f"Bucket '{bucket_name}' not found in manager")

            content_result = await bucket.get_file_content(file_path)
            if content_result["success"]:
                return create_result_dict("get_content_from_bucket", success=True, data={"content": content_result["data"], "content_type": "application/octet-stream"}) # Default content type
            else:
                return create_result_dict("get_content_from_bucket", success=False, error=content_result["error"])
        except Exception as e:
            logger.error(f"Error getting content from bucket {bucket_name}/{file_path}: {e}")
            return create_result_dict("get_content_from_bucket", success=False, error=str(e))

    async def delete_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """Delete a bucket and its associated data."""
        if bucket_name not in self.bucket_registry:
            return create_result_dict("delete_bucket", success=False, error=f"Bucket '{bucket_name}' not found")

        try:
            bucket_info = self.bucket_registry[bucket_name]
            storage_path = Path(bucket_info["storage_path"])
            vfs_index_path = Path(bucket_info["vfs_index_path"])
            pin_metadata_path = Path(bucket_info["pin_metadata_path"])

            # Remove directories
            import shutil
            if storage_path.exists():
                shutil.rmtree(storage_path)
            if vfs_index_path.exists():
                shutil.rmtree(vfs_index_path)
            if pin_metadata_path.exists():
                shutil.rmtree(pin_metadata_path)

            # Remove from registry
            del self.bucket_registry[bucket_name]
            await self._save_bucket_registry()

            # Remove from bucket_vfs_managers if present
            if bucket_name in self.bucket_vfs_managers:
                del self.bucket_vfs_managers[bucket_name]

            # Update global indices
            await self._update_global_indices()

            return create_result_dict("delete_bucket", success=True, message=f"Bucket '{bucket_name}' and its data deleted successfully.")
        except Exception as e:
            logger.error(f"Error deleting bucket {bucket_name}: {e}")
            return create_result_dict("delete_bucket", success=False, error=str(e))

    async def query_across_backends(
        self,
        sql_query: str,
        backend_filter: Optional[List[BackendType]] = None
    ) -> Dict[str, Any]:
        """
        Execute SQL query across multiple backends using DuckDB.
        
        Args:
            sql_query: SQL query to execute
            backend_filter: Optional list of backends to include
        """
        try:
            if not self.enable_cross_backend_queries:
                return create_result_dict(
                    "query_across_backends",
                    success=False,
                    error="Cross-backend queries not enabled (DuckDB not available)"
                )
            
            # Register tables for querying
            await self._register_cross_backend_tables(backend_filter)
            
            # Execute query
            result = self.duckdb_conn.execute(sql_query).fetchall()
            columns = [desc[0] for desc in self.duckdb_conn.description] if self.duckdb_conn.description else []
            
            return create_result_dict(
                "query_across_backends",
                success=True,
                data={
                    "columns": columns,
                    "rows": result,
                    "row_count": len(result),
                    "query": sql_query,
                    "backend_filter": [b.value for b in backend_filter] if backend_filter else None
                }
            )
            
        except Exception as e:
            logger.error(f"Error in cross-backend query: {e}")
            return create_result_dict(
                "query_across_backends",
                success=False,
                error=f"Query failed: {str(e)}"
            )
    
    async def get_vfs_composition(
        self,
        backend: Optional[BackendType] = None,
        bucket_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get virtual filesystem composition.
        
        Args:
            backend: Optional backend filter
            bucket_name: Optional bucket filter
        """
        try:
            vfs_composition = {
                "backends": {},
                "total_pins": 0,
                "total_size": 0,
                "file_types": {},
                "last_updated": datetime.utcnow().isoformat()
            }
            
            for bucket_id, bucket_info in self.bucket_registry.items():
                bucket_backend = BackendType(bucket_info["backend"])
                bucket_bucket_name = bucket_info["bucket_name"]
                
                # Apply filters
                if backend and bucket_backend != backend:
                    continue
                if bucket_name and bucket_bucket_name != bucket_name:
                    continue
                
                # Get VFS index data
                vfs_index_path = Path(bucket_info["vfs_index_path"])
                vfs_data = await self._load_vfs_index(vfs_index_path)
                
                if bucket_backend.value not in vfs_composition["backends"]:
                    vfs_composition["backends"][bucket_backend.value] = {
                        "buckets": {},
                        "total_pins": 0,
                        "total_size": 0
                    }
                
                backend_data = vfs_composition["backends"][bucket_backend.value]
                
                backend_data["buckets"][bucket_bucket_name] = {
                    "pin_count": vfs_data.get("pin_count", 0),
                    "total_size": vfs_data.get("total_size", 0),
                    "file_types": vfs_data.get("file_types", {}),
                    "last_modified": vfs_data.get("last_modified"),
                    "vfs_structure": bucket_info["vfs_structure"]
                }
                
                # Update totals
                pin_count = vfs_data.get("pin_count", 0)
                total_size = vfs_data.get("total_size", 0)
                
                backend_data["total_pins"] += pin_count
                backend_data["total_size"] += total_size
                
                vfs_composition["total_pins"] += pin_count
                vfs_composition["total_size"] += total_size
                
                # Merge file types
                for file_type, count in vfs_data.get("file_types", {}).items():
                    vfs_composition["file_types"][file_type] = vfs_composition["file_types"].get(file_type, 0) + count
            
            return create_result_dict(
                "get_vfs_composition",
                success=True,
                data=vfs_composition
            )
            
        except Exception as e:
            logger.error(f"Error getting VFS composition: {e}")
            return create_result_dict(
                "get_vfs_composition",
                success=False,
                error=f"Failed to get VFS composition: {str(e)}"
            )
    
    async def sync_bucket_indices(
        self,
        backend: Optional[BackendType] = None,
        bucket_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synchronize VFS and pin metadata indices.
        
        Args:
            backend: Optional backend filter
            bucket_name: Optional bucket filter
        """
        try:
            sync_results = []
            
            for bucket_id, bucket_info in self.bucket_registry.items():
                bucket_backend = BackendType(bucket_info["backend"])
                bucket_bucket_name = bucket_info["bucket_name"]
                
                # Apply filters
                if backend and bucket_backend != backend:
                    continue
                if bucket_name and bucket_bucket_name != bucket_name:
                    continue
                
                # Sync this bucket
                sync_result = await self._sync_bucket_index(bucket_backend, bucket_bucket_name)
                sync_results.append({
                    "bucket_id": bucket_id,
                    "backend": bucket_backend.value,
                    "bucket_name": bucket_bucket_name,
                    "sync_result": sync_result
                })
            
            # Update global indices
            await self._update_global_indices()
            
            successful_syncs = len([r for r in sync_results if r["sync_result"]["success"]])
            
            return create_result_dict(
                "sync_bucket_indices",
                success=True,
                data={
                    "synced_buckets": sync_results,
                    "total_buckets": len(sync_results),
                    "successful_syncs": successful_syncs,
                    "failed_syncs": len(sync_results) - successful_syncs
                }
            )
            
        except Exception as e:
            logger.error(f"Error syncing bucket indices: {e}")
            return create_result_dict(
                "sync_bucket_indices",
                success=False,
                error=f"Failed to sync indices: {str(e)}"
            )
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            # Stop background sync
            if self._sync_task and not self._sync_task.done():
                self._shutdown_event.set()
                try:
                    with anyio.fail_after(5.0):
                        await self._sync_task
                except TimeoutError:
                    self._sync_task.cancel()
            
            # Close DuckDB connection
            if self.duckdb_conn:
                self.duckdb_conn.close()
            
            # Cleanup backend managers
            for backend_manager in self.bucket_vfs_managers.values():
                if hasattr(backend_manager, 'cleanup'):
                    await backend_manager.cleanup()
            
            logger.info("Unified Bucket Interface cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def _initialize_backend_managers(self):
        """Initialize bucket-specific managers from existing bucket directories."""
        # Scan buckets directory for existing buckets
        if self.buckets_dir.exists():
            for bucket_dir in self.buckets_dir.iterdir():
                if bucket_dir.is_dir():
                    bucket_name = bucket_dir.name
                    self.bucket_vfs_managers[bucket_name] = BucketVFSManager(
                        storage_path=str(bucket_dir),
                        enable_parquet_export=True,
                        enable_duckdb_integration=self.enable_cross_backend_queries
                    )
    
    async def _load_bucket_registry(self):
        """Load bucket registry from disk (prefer Parquet over JSON)."""
        try:
            parquet_path = self.ipfs_kit_dir / "bucket_registry.parquet"
            
            # Try to load from Parquet first if available
            if ARROW_AVAILABLE and parquet_path.exists():
                await self._load_bucket_registry_parquet(parquet_path)
            elif self.registry_file.exists():
                # Fallback to JSON
                async with aiofiles.open(self.registry_file, 'r') as f:
                    content = await f.read()
                    self.bucket_registry = json.loads(content)
            else:
                self.bucket_registry = {}
                
            logger.info(f"Loaded {len(self.bucket_registry)} buckets from registry")
        except Exception as e:
            logger.error(f"Failed to load bucket registry: {e}")
            self.bucket_registry = {}

    async def _load_bucket_registry_parquet(self, parquet_path: Path):
        """Load bucket registry from Parquet file."""
        try:
            import pandas as pd
            
            df = pd.read_parquet(parquet_path)
            self.bucket_registry = {}
            
            for _, row in df.iterrows():
                bucket_id = row["bucket_id"]
                metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                backend_config = json.loads(row.get("backend_config_json", "{}")) if row.get("backend_config_json") else {}

                self.bucket_registry[bucket_id] = {
                    "backend": row["backend"],
                    "bucket_name": row["bucket_name"],
                    "bucket_type": row["bucket_type"],
                    "vfs_structure": row.get("vfs_structure", "hybrid"),  # Use stored value or default
                    "storage_path": row["bucket_path"],  # Map bucket_path back to storage_path
                    "vfs_index_path": row["vfs_index_path"],
                    "pin_metadata_path": row["pin_metadata_path"],
                    "created_at": row["created_at"],
                    "backend_config": backend_config,
                    "metadata": metadata
                }
                
        except Exception as e:
            logger.error(f"Failed to load bucket registry from Parquet: {e}")
            raise
    
    async def _save_bucket_registry(self):
        """Save bucket registry to disk (prefer Parquet over JSON)."""
        try:
            if ARROW_AVAILABLE:
                await self._save_bucket_registry_parquet()
                # Also save JSON as backup for compatibility
                async with aiofiles.open(self.registry_file, 'w') as f:
                    await f.write(json.dumps(self.bucket_registry, indent=2))
            else:
                # Fallback to JSON if Arrow not available
                async with aiofiles.open(self.registry_file, 'w') as f:
                    await f.write(json.dumps(self.bucket_registry, indent=2))
        except Exception as e:
            logger.error(f"Failed to save bucket registry: {e}")

    async def _save_bucket_registry_parquet(self):
        """Save bucket registry as Parquet file."""
        try:
            import pandas as pd
            
            if not self.bucket_registry:
                return
                
            # Convert bucket registry to DataFrame
            bucket_records = []
            for bucket_id, bucket_info in self.bucket_registry.items():
                record = {
                    "bucket_id": bucket_id,
                    "backend": bucket_info.get("backend", ""),
                    "bucket_name": bucket_info.get("bucket_name", ""),
                    "bucket_type": bucket_info.get("bucket_type", ""),
                    "vfs_structure": bucket_info.get("vfs_structure", "hybrid"),
                    "bucket_path": bucket_info.get("storage_path", ""),  # Use storage_path instead of bucket_path
                    "vfs_index_path": bucket_info.get("vfs_index_path", ""),
                    "pin_metadata_path": bucket_info.get("pin_metadata_path", ""),
                    "created_at": bucket_info.get("created_at", ""),
                    "backend_config_json": json.dumps(bucket_info.get("backend_config", {})),
                    "metadata_json": json.dumps(bucket_info.get("metadata", {}))
                }
                bucket_records.append(record)
            
            df = pd.DataFrame(bucket_records)
            parquet_path = self.ipfs_kit_dir / "bucket_registry.parquet"
            df.to_parquet(parquet_path, index=False)
            
        except Exception as e:
            logger.error(f"Failed to save bucket registry as Parquet: {e}")
    
    async def _update_global_indices(self):
        """Update global bucket and pin indices."""
        try:
            # Update bucket index
            if hasattr(self.global_bucket_index, 'update_from_bucket_manager'):
                await asyncio.to_thread(self.global_bucket_index.update_from_bucket_manager)
            
            # Update pin index  
            if hasattr(self.global_pin_index, 'refresh_index'):
                await asyncio.to_thread(self.global_pin_index.refresh_index)
                
        except Exception as e:
            logger.error(f"Failed to update global indices: {e}")
    
    async def _update_vfs_index(
        self,
        backend: BackendType,
        bucket_name: str,
        file_path: str,
        pin_metadata: Dict[str, Any]
    ):
        """Update VFS index for a specific bucket."""
        try:
            if bucket_name not in self.bucket_registry:
                return
            
            vfs_index_path = Path(self.bucket_registry[bucket_name]["vfs_index_path"])
            index_file = vfs_index_path / "vfs_index.json"
            
            # Load existing index
            vfs_index = {}
            if index_file.exists():
                async with aiofiles.open(index_file, 'r') as f:
                    content = await f.read()
                    vfs_index = json.loads(content)
            
            # Update index
            if "files" not in vfs_index:
                vfs_index["files"] = {}
            if "metadata" not in vfs_index:
                vfs_index["metadata"] = {}
            
            vfs_index["files"][file_path] = pin_metadata
            vfs_index["metadata"].update({
                "last_updated": datetime.utcnow().isoformat(),
                "backend": backend.value,
                "bucket_name": bucket_name,
                "pin_count": len(vfs_index["files"]),
                "total_size": sum(f.get("size", 0) for f in vfs_index["files"].values())
            })
            
            # Save updated index (prefer Parquet over JSON)
            if ARROW_AVAILABLE:
                await self._export_vfs_index_to_parquet(vfs_index_path, vfs_index)
                # Also save JSON as backup for compatibility
                index_file = vfs_index_path / "vfs_index.json"
                async with aiofiles.open(index_file, 'w') as f:
                    await f.write(json.dumps(vfs_index, indent=2))
            else:
                # Fallback to JSON only if Arrow not available
                index_file = vfs_index_path / "vfs_index.json"
                async with aiofiles.open(index_file, 'w') as f:
                    await f.write(json.dumps(vfs_index, indent=2))
                
        except Exception as e:
            logger.error(f"Failed to update VFS index: {e}")
    
    async def _load_pin_metadata_parquet(self, pin_file: Path) -> Dict[str, Any]:
        """Load pin metadata from Parquet file.""" 
        try:
            import pandas as pd
            
            df = pd.read_parquet(pin_file)
            if len(df) == 0:
                return {}
                
            row = df.iloc[0]  # Should only be one record per file
            metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            
            return {
                "cid": row["cid"],
                "backend": row["backend"],
                "bucket": row["bucket"],
                "file_path": row["file_path"],
                "size": row["size"],
                "status": row["status"],
                "created_at": row["created_at"],
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to load pin metadata from Parquet {pin_file}: {e}")
            return {}

    async def _save_pin_metadata_parquet(self, pin_dir: Path, content_hash: str, pin_metadata: Dict[str, Any]):
        """Save pin metadata as Parquet file."""
        try:
            import pandas as pd
            
            # Convert nested metadata to JSON string for Parquet storage
            flattened_metadata = {
                "content_hash": content_hash,
                "cid": pin_metadata.get("cid", ""),
                "backend": pin_metadata.get("backend", ""),
                "bucket": pin_metadata.get("bucket", ""),
                "file_path": pin_metadata.get("file_path", ""),
                "size": pin_metadata.get("size", 0),
                "status": pin_metadata.get("status", ""),
                "created_at": pin_metadata.get("created_at", ""),
                "metadata_json": json.dumps(pin_metadata.get("metadata", {}))
            }
            
            df = pd.DataFrame([flattened_metadata])
            parquet_path = pin_dir / f"{content_hash}.parquet"
            df.to_parquet(parquet_path, index=False)
            
        except Exception as e:
            logger.error(f"Failed to save pin metadata as Parquet: {e}")
            # Fallback to JSON
            pin_file = pin_dir / f"{content_hash}.json"
            async with aiofiles.open(pin_file, 'w') as f:
                await f.write(json.dumps(pin_metadata, indent=2))

    async def _export_vfs_index_to_parquet(self, vfs_index_path: Path, vfs_index: Dict[str, Any]):
        """Export VFS index to Parquet format."""
        try:
            # Create DataFrame from VFS index
            import pandas as pd
            
            file_records = []
            for file_path, metadata in vfs_index.get("files", {}).items():
                record = {
                    "file_path": file_path,
                    "content_hash": metadata.get("cid", ""),
                    "size": metadata.get("size", 0),
                    "backend": metadata.get("backend", ""),
                    "bucket": metadata.get("bucket", ""),
                    "status": metadata.get("status", ""),
                    "created_at": metadata.get("created_at", ""),
                    "metadata_json": json.dumps(metadata.get("metadata", {}))
                }
                file_records.append(record)
            
            if file_records:
                df = pd.DataFrame(file_records)
                parquet_path = vfs_index_path / "vfs_index.parquet"
                df.to_parquet(parquet_path)
                
        except Exception as e:
            logger.error(f"Failed to export VFS index to Parquet: {e}")
    
    async def _load_vfs_index(self, vfs_index_path: Path) -> Dict[str, Any]:
        """Load VFS index from disk (prefer Parquet over JSON)."""
        try:
            parquet_file = vfs_index_path / "vfs_index.parquet"
            index_file = vfs_index_path / "vfs_index.json"
            
            # Try to load from Parquet first if available
            if ARROW_AVAILABLE and parquet_file.exists():
                return await self._load_vfs_index_parquet(parquet_file)
            elif index_file.exists():
                # Fallback to JSON
                async with aiofiles.open(index_file, 'r') as f:
                    content = await f.read()
                    return json.loads(content)
            return {}
        except Exception as e:
            logger.error(f"Failed to load VFS index: {e}")
            return {}

    async def _load_vfs_index_parquet(self, parquet_file: Path) -> Dict[str, Any]:
        """Load VFS index from Parquet file."""
        try:
            import pandas as pd
            
            df = pd.read_parquet(parquet_file)
            vfs_index = {
                "files": {},
                "metadata": {}
            }
            
            for _, row in df.iterrows():
                file_path = row["file_path"]
                metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                
                vfs_index["files"][file_path] = {
                    "cid": row["content_hash"],
                    "size": row["size"],
                    "backend": row["backend"],
                    "bucket": row["bucket"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "metadata": metadata
                }
            
            # Reconstruct metadata
            if vfs_index["files"]:
                first_file = next(iter(vfs_index["files"].values()))
                vfs_index["metadata"] = {
                    "backend": first_file["backend"],
                    "bucket_name": first_file["bucket"],
                    "pin_count": len(vfs_index["files"]),
                    "total_size": sum(f.get("size", 0) for f in vfs_index["files"].values())
                }
            
            return vfs_index
            
        except Exception as e:
            logger.error(f"Failed to load VFS index from Parquet: {e}")
            return {}
    
    async def _get_bucket_statistics(
        self,
        backend: BackendType,
        bucket_name: str
    ) -> Dict[str, Any]:
        """Get statistics for a specific bucket."""
        try:
            if bucket_name not in self.bucket_registry:
                return {}
            
            bucket_info = self.bucket_registry[bucket_name]
            
            # Load VFS index
            vfs_index_path = Path(bucket_info["vfs_index_path"])
            vfs_index = await self._load_vfs_index(vfs_index_path)
            
            # Load pin metadata (check both Parquet and JSON files)
            pin_metadata_path = Path(bucket_info["pin_metadata_path"])
            pin_files = list(pin_metadata_path.glob("*.parquet")) + list(pin_metadata_path.glob("*.json"))
            
            # Calculate statistics
            total_size = sum(f.get("size", 0) for f in vfs_index.get("files", {}).values())
            pin_count = len(pin_files)
            vfs_files = len(vfs_index.get("files", {}))
            
            # Get last modified time
            last_modified = None
            if pin_files:
                latest_mtime = max(f.stat().st_mtime for f in pin_files)
                last_modified = datetime.fromtimestamp(latest_mtime).isoformat()
            
            return {
                "pin_count": pin_count,
                "vfs_files": vfs_files,
                "total_size": total_size,
                "last_modified": last_modified or bucket_info.get("created_at")
            }
            
        except Exception as e:
            logger.error(f"Failed to get bucket statistics: {e}")
            return {}
    
    async def _sync_bucket_index(
        self,
        backend: BackendType,
        bucket_name: str
    ) -> Dict[str, Any]:
        """Synchronize index for a specific bucket."""
        try:
            if bucket_name not in self.bucket_registry:
                return create_result_dict("sync_bucket_index", success=False, error="Bucket not found")
            
            bucket_info = self.bucket_registry[bucket_name]
            
            # Refresh VFS index from actual storage
            bucket_manager = self.bucket_vfs_managers.get(backend)
            if bucket_manager:
                bucket = await bucket_manager.get_bucket(bucket_name)
                if bucket:
                    # Update bucket metadata
                    await bucket._save_metadata()
            
            # Rebuild VFS index from pin metadata
            pin_metadata_path = Path(bucket_info["pin_metadata_path"])
            vfs_index_path = Path(bucket_info["vfs_index_path"])
            
            vfs_index = {
                "files": {},
                "metadata": {
                    "backend": backend.value,
                    "bucket_name": bucket_name,
                    "last_updated": datetime.utcnow().isoformat()
                }
            }
            
            # Process all pin files (both Parquet and JSON)
            for pin_file in pin_metadata_path.glob("*.parquet"):
                try:
                    pin_data = await self._load_pin_metadata_parquet(pin_file)
                    if pin_data:
                        file_path = pin_data.get("file_path", pin_file.stem)
                        vfs_index["files"][file_path] = pin_data
                except Exception as e:
                    logger.warning(f"Failed to load pin file {pin_file}: {e}")
                    
            # Also process JSON files for backward compatibility
            for pin_file in pin_metadata_path.glob("*.json"):
                try:
                    async with aiofiles.open(pin_file, 'r') as f:
                        content = await f.read()
                        pin_data = json.loads(content)
                        file_path = pin_data.get("file_path", pin_file.stem)
                        vfs_index["files"][file_path] = pin_data
                except Exception as e:
                    logger.warning(f"Failed to load pin file {pin_file}: {e}")
            
            # Update metadata
            vfs_index["metadata"].update({
                "pin_count": len(vfs_index["files"]),
                "total_size": sum(f.get("size", 0) for f in vfs_index["files"].values())
            })
            
            # Save updated index (prefer Parquet over JSON)
            if ARROW_AVAILABLE:
                await self._export_vfs_index_to_parquet(vfs_index_path, vfs_index)
                # Also save JSON as backup for compatibility
                index_file = vfs_index_path / "vfs_index.json"
                async with aiofiles.open(index_file, 'w') as f:
                    await f.write(json.dumps(vfs_index, indent=2))
            else:
                # Fallback to JSON only if Arrow not available
                index_file = vfs_index_path / "vfs_index.json"
                async with aiofiles.open(index_file, 'w') as f:
                    await f.write(json.dumps(vfs_index, indent=2))

            # Export to Parquet
            if ARROW_AVAILABLE:
                await self._export_vfs_index_to_parquet(vfs_index_path, vfs_index)
            
            return create_result_dict(
                "sync_bucket_index",
                success=True,
                data={
                    "pin_count": vfs_index["metadata"]["pin_count"],
                    "total_size": vfs_index["metadata"]["total_size"]
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to sync bucket index: {e}")
            return create_result_dict("sync_bucket_index", success=False, error=str(e))
    
    async def _register_cross_backend_tables(self, backend_filter: Optional[List[BackendType]]):
        """Register tables for cross-backend queries."""
        try:
            if not self.duckdb_conn:
                return
            
            for bucket_id, bucket_info in self.bucket_registry.items():
                backend = BackendType(bucket_info["backend"])
                if backend_filter and backend not in backend_filter:
                    continue
                
                # Register VFS index Parquet files
                vfs_index_path = Path(bucket_info["vfs_index_path"])
                parquet_file = vfs_index_path / "vfs_index.parquet"
                
                if parquet_file.exists():
                    table_name = f"vfs_{backend.value}_{bucket_info['bucket_name']}"
                    self.duckdb_conn.execute(
                        f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{parquet_file}')"
                    )
                    
        except Exception as e:
            logger.error(f"Failed to register cross-backend tables: {e}")
    
    async def _background_sync(self):
        """Background task for periodic synchronization."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Wait for sync interval or shutdown
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.auto_sync_interval
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    # Sync interval elapsed, perform sync
                    logger.debug("Starting background sync")
                    await self.sync_bucket_indices()
                    logger.debug("Background sync complete")
                    
        except asyncio.CancelledError:
            logger.info("Background sync task cancelled")
        except Exception as e:
            logger.error(f"Error in background sync: {e}")


# Global instance
_global_unified_bucket_interface: Optional[UnifiedBucketInterface] = None


def get_global_unified_bucket_interface(**kwargs) -> UnifiedBucketInterface:
    """Get or create global unified bucket interface instance."""
    global _global_unified_bucket_interface
    if _global_unified_bucket_interface is None:
        _global_unified_bucket_interface = UnifiedBucketInterface(**kwargs)
    return _global_unified_bucket_interface


async def initialize_global_unified_bucket_interface(**kwargs):
    """Initialize global unified bucket interface."""
    interface = get_global_unified_bucket_interface(**kwargs)
    return await interface.initialize()


async def cleanup_global_unified_bucket_interface():
    """Cleanup global unified bucket interface."""
    global _global_unified_bucket_interface
    if _global_unified_bucket_interface:
        await _global_unified_bucket_interface.cleanup()
        _global_unified_bucket_interface = None
