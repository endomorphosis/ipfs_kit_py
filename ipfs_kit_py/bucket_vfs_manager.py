#!/usr/bin/env python3
"""
Multi-Bucket Virtual Filesystem Manager for IPFS-Kit

This module implements a comprehensive multi-bucket virtual filesystem architecture
where each bucket contains:
- UnixFS structure for file organization
- Knowledge graph in IPLD format
- Vector index with IPLD compatibility
- Automatic export to Parquet/Arrow for DuckDB and cross-language support

The system provides S3-like bucket semantics with IPFS content addressing,
ensuring data is both traversable in IPFS and portable across different tools.
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
from typing import Any, Dict, List, Optional, Set, Union

import aiofiles

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

# Import IPFS-Kit components
from .parquet_ipld_bridge import ParquetIPLDBridge
from .parquet_car_bridge import ParquetCARBridge
from .ipld_knowledge_graph import IPLDGraphDB, GraphRAG
from .tiered_cache_manager import TieredCacheManager
from .error import create_result_dict, handle_error
# NOTE: This file contains asyncio.create_task() calls that need task group context

# Import CAR WAL Manager
try:
    from .car_wal_manager import get_car_wal_manager
    CAR_WAL_AVAILABLE = True
except ImportError:
    CAR_WAL_AVAILABLE = False


logger = logging.getLogger(__name__)


class BucketType(Enum):
    """Types of bucket virtual filesystems."""
    GENERAL = "general"           # General purpose file storage
    DATASET = "dataset"          # Structured data collections
    KNOWLEDGE = "knowledge"      # Knowledge graphs and ontologies
    MEDIA = "media"             # Media files and metadata
    ARCHIVE = "archive"         # Long-term archive storage
    TEMP = "temp"               # Temporary workspace


class VFSStructureType(Enum):
    """Types of virtual filesystem structures."""
    UNIXFS = "unixfs"           # Traditional Unix-like filesystem
    GRAPH = "graph"             # Graph-based knowledge structure
    VECTOR = "vector"           # Vector database structure
    HYBRID = "hybrid"           # Combination of above types


class BucketVFSManager:
    """
    Manager for multi-bucket virtual filesystems with IPLD compatibility.
    
    Each bucket provides:
    - S3-like bucket semantics
    - UnixFS structure for file organization
    - Knowledge graph in IPLD format
    - Vector index with IPLD representation
    - Automatic Parquet/Arrow export for cross-platform compatibility
    """
    
    def __init__(
        self,
        storage_path: str = "/tmp/ipfs_kit_buckets",
        ipfs_client=None,
        enable_parquet_export: bool = True,
        enable_duckdb_integration: bool = True
    ):
        """
        Initialize the bucket VFS manager.
        
        Args:
            storage_path: Base path for bucket storage
            ipfs_client: IPFS client instance
            enable_parquet_export: Enable automatic Parquet export
            enable_duckdb_integration: Enable DuckDB SQL interface
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.ipfs_client = ipfs_client
        self.enable_parquet_export = enable_parquet_export and ARROW_AVAILABLE
        self.enable_duckdb_integration = enable_duckdb_integration and DUCKDB_AVAILABLE
        
        # Core components
        self.parquet_bridge = ParquetIPLDBridge() if ARROW_AVAILABLE else None
        self.car_bridge = ParquetCARBridge() if ARROW_AVAILABLE else None
        self.cache_manager = TieredCacheManager()
        
        # Bucket registry
        self.buckets: Dict[str, 'BucketVFS'] = {}
        self._bucket_metadata_file = self.storage_path / "bucket_registry.json"
        
        # DuckDB connection for cross-bucket queries
        if self.enable_duckdb_integration:
            self.duckdb_conn = duckdb.connect(str(self.storage_path / "cross_bucket.duckdb"))
        else:
            self.duckdb_conn = None
        
        # Load existing buckets
        asyncio.create_task(self._load_bucket_registry())
        
        logger.info(f"BucketVFSManager initialized at {storage_path}")
    
    async def create_bucket(
        self,
        bucket_name: str,
        bucket_type: BucketType = BucketType.GENERAL,
        vfs_structure: VFSStructureType = VFSStructureType.HYBRID,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new bucket with specified structure.
        
        Args:
            bucket_name: Unique bucket identifier
            bucket_type: Type of bucket to create
            vfs_structure: Virtual filesystem structure type
            metadata: Additional bucket metadata
            
        Returns:
            Result dictionary with bucket creation status
        """
        try:
            if bucket_name in self.buckets:
                return create_result_dict(
                    False, 
                    error=f"Bucket '{bucket_name}' already exists"
                )
            
            # Create bucket instance
            bucket = BucketVFS(
                name=bucket_name,
                bucket_type=bucket_type,
                vfs_structure=vfs_structure,
                storage_path=self.storage_path / bucket_name,
                ipfs_client=self.ipfs_client,
                parquet_bridge=self.parquet_bridge,
                car_bridge=self.car_bridge,
                cache_manager=self.cache_manager,
                duckdb_conn=self.duckdb_conn
            )
            
            # Initialize bucket
            result = await bucket.initialize(metadata or {})
            if not result["success"]:
                return result
            
            # Register bucket
            self.buckets[bucket_name] = bucket
            await self._save_bucket_registry()
            
            logger.info(f"Created bucket '{bucket_name}' of type {bucket_type.value}")
            
            return create_result_dict(
                "create_bucket",
                success=True,
                data={
                    "bucket_name": bucket_name,
                    "bucket_type": bucket_type.value,
                    "vfs_structure": vfs_structure.value,
                    "cid": bucket.root_cid,
                    "created_at": bucket.created_at
                }
            )
            
        except Exception as e:
            logger.error(f"Error in create_bucket: {e}")
            return create_result_dict(
                "create_bucket", 
                success=False,
                error=f"Failed to create bucket: {str(e)}"
            )
    
    async def get_bucket(self, bucket_name: str) -> Optional['BucketVFS']:
        """Get bucket instance by name."""
        return self.buckets.get(bucket_name)
    
    async def list_buckets(self) -> Dict[str, Any]:
        """List all available buckets."""
        try:
            bucket_list = []
            
            for name, bucket in self.buckets.items():
                bucket_info = {
                    "name": name,
                    "type": bucket.bucket_type.value,
                    "vfs_structure": bucket.vfs_structure.value,
                    "created_at": bucket.created_at,
                    "root_cid": bucket.root_cid,
                    "file_count": await bucket.get_file_count(),
                    "size_bytes": await bucket.get_total_size(),
                    "last_modified": await bucket.get_last_modified()
                }
                bucket_list.append(bucket_info)
            
            return create_result_dict(
                "list_buckets",
                success=True,
                data={
                    "buckets": bucket_list,
                    "total_count": len(bucket_list)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in list_buckets: {e}")
            return create_result_dict(
                "list_buckets",
                success=False,
                error=f"Failed to list buckets: {str(e)}"
            )
    
    async def delete_bucket(
        self, 
        bucket_name: str, 
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Delete a bucket and all its contents.
        
        Args:
            bucket_name: Name of bucket to delete
            force: Force deletion even if bucket contains data
        """
        try:
            if bucket_name not in self.buckets:
                return create_result_dict(
                    "delete_bucket",
                    success=False,
                    error=f"Bucket '{bucket_name}' not found"
                )
            
            bucket = self.buckets[bucket_name]
            
            # Check if bucket is empty (unless force=True)
            if not force:
                file_count = await bucket.get_file_count()
                if file_count > 0:
                    return create_result_dict(
                        "delete_bucket",
                        success=False,
                        error=f"Bucket '{bucket_name}' contains {file_count} files. Use force=True to delete."
                    )
            
            # Delete bucket data
            await bucket.cleanup()
            
            # Remove from registry
            del self.buckets[bucket_name]
            await self._save_bucket_registry()
            
            logger.info(f"Deleted bucket '{bucket_name}'")
            
            return create_result_dict(
                "delete_bucket",
                success=True,
                data={"bucket_name": bucket_name}
            )
            
        except Exception as e:
            logger.error(f"Error in delete_bucket: {e}")
            return create_result_dict(
                "delete_bucket",
                success=False,
                error=f"Failed to delete bucket: {str(e)}"
            )
    
    async def cross_bucket_query(
        self, 
        sql_query: str,
        bucket_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute SQL queries across multiple buckets using DuckDB.
        
        Args:
            sql_query: SQL query to execute
            bucket_filter: Optional list of bucket names to include
        """
        try:
            if not self.enable_duckdb_integration:
                return create_result_dict(
                    "cross_bucket_query",
                    success=False,
                    error="DuckDB integration not available"
                )
            
            # Register bucket tables in DuckDB
            buckets_to_query = bucket_filter or list(self.buckets.keys())
            
            for bucket_name in buckets_to_query:
                if bucket_name in self.buckets:
                    bucket = self.buckets[bucket_name]
                    await bucket.register_duckdb_tables(self.duckdb_conn)
            
            # Execute query (only if duckdb_conn is not None)
            if self.duckdb_conn is None:
                return create_result_dict(
                    "cross_bucket_query",
                    success=False,
                    error="DuckDB connection not initialized"
                )
                
            result = self.duckdb_conn.execute(sql_query).fetchall()
            columns = [desc[0] for desc in self.duckdb_conn.description] if self.duckdb_conn.description else []
            
            return create_result_dict(
                "cross_bucket_query",
                success=True,
                data={
                    "columns": columns,
                    "rows": result,
                    "row_count": len(result)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in cross_bucket_query: {e}")
            return create_result_dict(
                "cross_bucket_query",
                success=False,
                error=f"Failed to execute query: {str(e)}"
            )
    
    async def export_bucket_to_car(
        self, 
        bucket_name: str,
        include_indexes: bool = True
    ) -> Dict[str, Any]:
        """
        Export bucket contents to CAR archive for IPFS distribution.
        
        Args:
            bucket_name: Name of bucket to export
            include_indexes: Include vector and knowledge graph indexes
        """
        try:
            if bucket_name not in self.buckets:
                return create_result_dict(
                    "export_bucket_to_car",
                    success=False,
                    error=f"Bucket '{bucket_name}' not found"
                )
            
            bucket = self.buckets[bucket_name]
            return await bucket.export_to_car(include_indexes=include_indexes)
            
        except Exception as e:
            logger.error(f"Error in export_bucket_to_car: {e}")
            return create_result_dict(
                "export_bucket_to_car",
                success=False,
                error=f"Failed to export bucket: {str(e)}"
            )
    
    async def _load_bucket_registry(self):
        """Load bucket registry from disk."""
        try:
            if self._bucket_metadata_file.exists():
                async with aiofiles.open(self._bucket_metadata_file, 'r') as f:
                    content = await f.read()
                    registry = json.loads(content)
                
                # Reconstruct bucket instances
                for bucket_name, bucket_data in registry.items():
                    try:
                        bucket = BucketVFS(
                            name=bucket_name,
                            bucket_type=BucketType(bucket_data["type"]),
                            vfs_structure=VFSStructureType(bucket_data["vfs_structure"]),
                            storage_path=Path(bucket_data["storage_path"]),
                            ipfs_client=self.ipfs_client,
                            parquet_bridge=self.parquet_bridge,
                            car_bridge=self.car_bridge,
                            cache_manager=self.cache_manager,
                            duckdb_conn=self.duckdb_conn
                        )
                        
                        # Load existing bucket data
                        await bucket.load_existing()
                        self.buckets[bucket_name] = bucket
                        
                    except Exception as e:
                        logger.error(f"Failed to load bucket '{bucket_name}': {e}")
                
                logger.info(f"Loaded {len(self.buckets)} buckets from registry")
            
        except Exception as e:
            logger.error(f"Failed to load bucket registry: {e}")
    
    async def _save_bucket_registry(self):
        """Save bucket registry to disk."""
        try:
            registry = {}
            
            for bucket_name, bucket in self.buckets.items():
                registry[bucket_name] = {
                    "type": bucket.bucket_type.value,
                    "vfs_structure": bucket.vfs_structure.value,
                    "storage_path": str(bucket.storage_path),
                    "created_at": bucket.created_at,
                    "root_cid": bucket.root_cid
                }
            
            async with aiofiles.open(self._bucket_metadata_file, 'w') as f:
                await f.write(json.dumps(registry, indent=2))
            
        except Exception as e:
            logger.error(f"Failed to save bucket registry: {e}")


class BucketVFS:
    """
    Individual bucket virtual filesystem implementation.
    
    Each bucket provides:
    - UnixFS structure for file organization
    - Knowledge graph in IPLD format
    - Vector index with IPLD compatibility
    - Automatic Parquet/Arrow export
    """
    
    def __init__(
        self,
        name: str,
        bucket_type: BucketType,
        vfs_structure: VFSStructureType,
        storage_path: Path,
        ipfs_client=None,
        parquet_bridge=None,
        car_bridge=None,
        cache_manager=None,
        duckdb_conn=None
    ):
        """Initialize bucket VFS instance."""
        self.name = name
        self.bucket_type = bucket_type
        self.vfs_structure = vfs_structure
        self.storage_path = storage_path
        self.ipfs_client = ipfs_client
        self.parquet_bridge = parquet_bridge
        self.car_bridge = car_bridge
        self.cache_manager = cache_manager
        self.duckdb_conn = duckdb_conn
        
        # Bucket metadata
        self.created_at: Optional[str] = None
        self.root_cid: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        
        # Component instances
        self.knowledge_graph: Optional[IPLDGraphDB] = None
        self.graph_rag: Optional[GraphRAG] = None
        self.vector_index: Optional[Dict[str, Any]] = None
        
        # Directory structure
        self.dirs = {
            "files": self.storage_path / "files",         # UnixFS file storage
            "knowledge": self.storage_path / "knowledge", # Knowledge graph data
            "vectors": self.storage_path / "vectors",     # Vector index data
            "parquet": self.storage_path / "parquet",     # Parquet exports
            "car": self.storage_path / "car",             # CAR archives
            "metadata": self.storage_path / "metadata"    # Bucket metadata
        }
    
    async def initialize(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize the bucket with specified metadata."""
        try:
            # Create directory structure
            for dir_path in self.dirs.values():
                dir_path.mkdir(parents=True, exist_ok=True)
            
            # Set metadata
            self.created_at = datetime.utcnow().isoformat()
            self.metadata = {
                **metadata,
                "created_at": self.created_at,
                "bucket_type": self.bucket_type.value,
                "vfs_structure": self.vfs_structure.value
            }
            
            # Initialize components based on VFS structure
            await self._initialize_components()
            
            # Create root IPLD node
            await self._create_root_node()
            
            # Save metadata
            await self._save_metadata()
            
            return create_result_dict(
                "bucket_initialize",
                success=True,
                data={"root_cid": self.root_cid}
            )
            
        except Exception as e:
            logger.error(f"Error in bucket initialize: {e}")
            return create_result_dict(
                "bucket_initialize", 
                success=False,
                error=f"Failed to initialize bucket: {str(e)}"
            )
    
    async def _initialize_components(self):
        """Initialize bucket components based on VFS structure."""
        try:
            # Always initialize knowledge graph for metadata
            if self.ipfs_client:
                self.knowledge_graph = IPLDGraphDB(
                    ipfs_client=self.ipfs_client,
                    base_path=str(self.dirs["knowledge"])
                )
                self.graph_rag = GraphRAG(self.knowledge_graph)
            
            # Initialize vector index
            self.vector_index = {
                "collections": {},
                "metadata": {
                    "dimension": 384,  # Default embedding dimension
                    "total_vectors": 0,
                    "created_at": self.created_at
                }
            }
            
            # Structure-specific initialization
            if self.vfs_structure in [VFSStructureType.GRAPH, VFSStructureType.HYBRID]:
                await self._setup_graph_structure()
            
            if self.vfs_structure in [VFSStructureType.VECTOR, VFSStructureType.HYBRID]:
                await self._setup_vector_structure()
            
            if self.vfs_structure in [VFSStructureType.UNIXFS, VFSStructureType.HYBRID]:
                await self._setup_unixfs_structure()
            
        except Exception as e:
            logger.error(f"Failed to initialize bucket components: {e}")
            raise
    
    async def _setup_graph_structure(self):
        """Setup knowledge graph structure."""
        if self.knowledge_graph:
            # Create bucket-specific entities
            await asyncio.to_thread(
                self.knowledge_graph.add_entity,
                f"bucket_{self.name}",
                "bucket",
                {
                    "name": self.name,
                    "type": self.bucket_type.value,
                    "created_at": self.created_at
                }
            )
    
    async def _setup_vector_structure(self):
        """Setup vector index structure."""
        # Create default vector collection
        collection_id = f"{self.name}_default"
        self.vector_index["collections"][collection_id] = {
            "id": collection_id,
            "name": f"Default collection for {self.name}",
            "dimension": 384,
            "vector_count": 0,
            "created_at": self.created_at,
            "index_type": "flat",
            "metadata": {}
        }
    
    async def _setup_unixfs_structure(self):
        """Setup UnixFS directory structure."""
        # Create standard Unix-like directories
        standard_dirs = ["bin", "etc", "var", "tmp", "home", "usr"]
        
        for dir_name in standard_dirs:
            dir_path = self.dirs["files"] / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            
            # Create .gitkeep file to maintain directory in git
            gitkeep = dir_path / ".gitkeep"
            gitkeep.touch()
    
    async def _create_root_node(self):
        """Create root IPLD node for the bucket."""
        if not self.ipfs_client:
            self.root_cid = f"mock_cid_{self.name}_{uuid.uuid4().hex[:8]}"
            return
        
        try:
            # Create root node structure
            root_node = {
                "bucket_name": self.name,
                "bucket_type": self.bucket_type.value,
                "vfs_structure": self.vfs_structure.value,
                "created_at": self.created_at,
                "metadata": self.metadata,
                "structure": {
                    "files": {"type": "unixfs_directory", "cid": None},
                    "knowledge": {"type": "ipld_graph", "cid": None},
                    "vectors": {"type": "vector_index", "cid": None},
                    "parquet": {"type": "parquet_exports", "cid": None}
                }
            }
            
            # Store in IPFS
            self.root_cid = await asyncio.to_thread(
                self.ipfs_client.dag_put, 
                root_node
            )
            
            logger.info(f"Created root node for bucket '{self.name}': {self.root_cid}")
            
        except Exception as e:
            logger.error(f"Failed to create root node: {e}")
            self.root_cid = f"error_cid_{self.name}_{uuid.uuid4().hex[:8]}"
    
    async def add_file(
        self, 
        file_path: str, 
        content: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a file to the bucket VFS.
        
        Args:
            file_path: Virtual path within bucket
            content: File content
            metadata: Optional file metadata
        """
        try:
            # Determine target path
            target_path = self.dirs["files"] / file_path.lstrip("/")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file content
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            async with aiofiles.open(target_path, 'wb') as f:
                await f.write(content)
            
            # Add to IPFS if client available
            file_cid = None
            if self.ipfs_client:
                file_cid = await asyncio.to_thread(
                    self.ipfs_client.add_bytes,
                    content
                )
            
            # Update knowledge graph
            if self.knowledge_graph:
                file_entity_id = f"file_{self.name}_{file_path.replace('/', '_')}"
                await asyncio.to_thread(
                    self.knowledge_graph.add_entity,
                    file_entity_id,
                    "file",
                    {
                        "path": file_path,
                        "size": len(content),
                        "cid": file_cid,
                        "bucket": self.name,
                        "created_at": datetime.utcnow().isoformat(),
                        **(metadata or {})
                    }
                )
            
            # Export to Parquet if enabled
            if self.parquet_bridge and ARROW_AVAILABLE:
                await self._export_file_metadata_to_parquet(file_path, content, metadata)
            
            return create_result_dict(
                "add_file",
                success=True,
                data={
                    "file_path": file_path,
                    "size": len(content),
                    "cid": file_cid,
                    "local_path": str(target_path)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in add_file: {e}")
            return create_result_dict(
                "add_file",
                success=False,
                error=f"Failed to add file: {str(e)}"
            )

    async def get_file(self, file_path: str, local_path: str) -> Dict[str, Any]:
        """
        Get a file from the bucket and save to local path.
        
        Args:
            file_path: Virtual path within bucket
            local_path: Local destination path
        """
        try:
            # Determine source path
            source_path = self.dirs["files"] / file_path.lstrip("/")
            
            if not source_path.exists():
                return create_result_dict(
                    "get_file",
                    success=False,
                    error=f"File '{file_path}' not found in bucket '{self.name}'"
                )
            
            # Create parent directory if needed
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            async with aiofiles.open(source_path, 'rb') as src:
                content = await src.read()
                async with aiofiles.open(local_path, 'wb') as dst:
                    await dst.write(content)
            
            return create_result_dict(
                "get_file",
                success=True,
                data={
                    "file_path": file_path,
                    "local_path": local_path,
                    "size": len(content)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in get_file: {e}")
            return create_result_dict(
                "get_file",
                success=False,
                error=f"Failed to get file: {str(e)}"
            )

    async def cat_file(self, file_path: str) -> Dict[str, Any]:
        """
        Get file content as string.
        
        Args:
            file_path: Virtual path within bucket
        """
        try:
            # Determine source path
            source_path = self.dirs["files"] / file_path.lstrip("/")
            
            if not source_path.exists():
                return create_result_dict(
                    "cat_file",
                    success=False,
                    error=f"File '{file_path}' not found in bucket '{self.name}'"
                )
            
            # Read file content
            async with aiofiles.open(source_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            return create_result_dict(
                "cat_file",
                success=True,
                data={
                    "file_path": file_path,
                    "content": content,
                    "size": len(content.encode('utf-8'))
                }
            )
            
        except Exception as e:
            logger.error(f"Error in cat_file: {e}")
            return create_result_dict(
                "cat_file",
                success=False,
                error=f"Failed to cat file: {str(e)}"
            )

    async def remove_file(self, file_path: str) -> Dict[str, Any]:
        """
        Remove a file from the bucket.
        
        Args:
            file_path: Virtual path within bucket
        """
        try:
            # Determine source path
            source_path = self.dirs["files"] / file_path.lstrip("/")
            
            if not source_path.exists():
                return create_result_dict(
                    "remove_file",
                    success=False,
                    error=f"File '{file_path}' not found in bucket '{self.name}'"
                )
            
            # Remove file
            source_path.unlink()
            
            # Update knowledge graph if available
            if self.knowledge_graph:
                file_entity_id = f"file_{self.name}_{file_path.replace('/', '_')}"
                try:
                    await asyncio.to_thread(
                        self.knowledge_graph.remove_entity,
                        file_entity_id
                    )
                except Exception as kg_e:
                    logger.warning(f"Failed to update knowledge graph: {kg_e}")
            
            return create_result_dict(
                "remove_file",
                success=True,
                data={
                    "file_path": file_path,
                    "removed": True
                }
            )
            
        except Exception as e:
            logger.error(f"Error in remove_file: {e}")
            return create_result_dict(
                "remove_file",
                success=False,
                error=f"Failed to remove file: {str(e)}"
            )

    async def list_files(self, prefix: str = "") -> Dict[str, Any]:
        """
        List files in the bucket.
        
        Args:
            prefix: Optional path prefix to filter files
        """
        try:
            files_dir = self.dirs["files"]
            files = []
            
            # Walk through files directory
            if files_dir.exists():
                for file_path in files_dir.rglob("*"):
                    if file_path.is_file():
                        # Get relative path from files directory
                        rel_path = file_path.relative_to(files_dir)
                        rel_path_str = str(rel_path).replace("\\", "/")  # Normalize path separators
                        
                        # Apply prefix filter
                        if prefix and not rel_path_str.startswith(prefix):
                            continue
                        
                        # Get file stats
                        stat = file_path.stat()
                        files.append({
                            "path": "/" + rel_path_str,
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "type": "file"
                        })
            
            return create_result_dict(
                "list_files",
                success=True,
                data={
                    "bucket": self.name,
                    "files": files,
                    "count": len(files)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in list_files: {e}")
            return create_result_dict(
                "list_files",
                success=False,
                error=f"Failed to list files: {str(e)}"
            )
    
    async def _export_file_metadata_to_parquet(
        self, 
        file_path: str, 
        content: bytes, 
        metadata: Optional[Dict[str, Any]]
    ):
        """Export file metadata to Parquet for DuckDB compatibility."""
        try:
            # Create Arrow table with file metadata
            file_metadata = {
                "path": [file_path],
                "size": [len(content)],
                "bucket": [self.name],
                "created_at": [datetime.utcnow().isoformat()],
                "content_type": [metadata.get("content_type", "application/octet-stream") if metadata else "application/octet-stream"],
                "checksum": [None],  # Could add hash here
            }
            
            # Add custom metadata fields
            if metadata:
                for key, value in metadata.items():
                    if key not in file_metadata:
                        file_metadata[f"meta_{key}"] = [value]
            
            table = pa.table(file_metadata)
            
            # Write to Parquet
            parquet_path = self.dirs["parquet"] / "file_metadata.parquet"
            
            # Append to existing Parquet file or create new one
            if parquet_path.exists():
                existing_table = pq.read_table(parquet_path)
                combined_table = pa.concat_tables([existing_table, table])
                pq.write_table(combined_table, parquet_path)
            else:
                pq.write_table(table, parquet_path)
            
        except Exception as e:
            logger.error(f"Failed to export file metadata to Parquet: {e}")
    
    async def get_file_count(self) -> int:
        """Get total number of files in bucket."""
        try:
            count = 0
            for root, dirs, files in os.walk(self.dirs["files"]):
                count += len(files)
            return count
        except Exception:
            return 0
    
    async def get_total_size(self) -> int:
        """Get total size of bucket in bytes."""
        try:
            total_size = 0
            for root, dirs, files in os.walk(self.storage_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
            return total_size
        except Exception:
            return 0
    
    async def get_last_modified(self) -> str:
        """Get last modification time of bucket."""
        try:
            latest_time = 0
            for root, dirs, files in os.walk(self.storage_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path):
                        mtime = os.path.getmtime(file_path)
                        latest_time = max(latest_time, mtime)
            
            if latest_time > 0:
                return datetime.fromtimestamp(latest_time).isoformat()
            else:
                return self.created_at or datetime.utcnow().isoformat()
        except Exception:
            return self.created_at or datetime.utcnow().isoformat()
    
    async def export_to_car(self, include_indexes: bool = True) -> Dict[str, Any]:
        """Export bucket contents to CAR archive."""
        try:
            if not self.car_bridge:
                return create_result_dict(
                    "export_to_car",
                    success=False,
                    error="CAR bridge not available"
                )
            
            car_path = self.dirs["car"] / f"{self.name}_{int(time.time())}.car"
            
            # Collect data to export
            export_data = {}
            
            # Add file metadata
            parquet_files = list(self.dirs["parquet"].glob("*.parquet"))
            for parquet_file in parquet_files:
                export_data[f"parquet/{parquet_file.name}"] = str(parquet_file)
            
            # Add knowledge graph data if available
            if include_indexes and self.knowledge_graph:
                # Use proper export method - simplified call
                kg_export = {"success": True, "data": {}}  # Placeholder
                if kg_export["success"]:
                    export_data["knowledge_graph.json"] = kg_export["data"]
            
            # Add vector index data if available
            if include_indexes and self.vector_index:
                vector_export_path = self.dirs["vectors"] / "index_export.json"
                async with aiofiles.open(vector_export_path, 'w') as f:
                    await f.write(json.dumps(self.vector_index or {}, indent=2))
                export_data["vector_index.json"] = str(vector_export_path)
            
            # Create CAR archive using convert_parquet_to_car
            if export_data and self.car_bridge and hasattr(self.car_bridge, 'convert_parquet_to_car'):
                # For demo purposes, create a temporary parquet file with export data
                temp_parquet_path = self.dirs["car"] / f"temp_export_{int(time.time())}.parquet"
                
                # Create a simple dataframe with export info
                import pandas as pd
                export_df = pd.DataFrame([{
                    "name": name,
                    "path": path,
                    "type": "exported_file"
                } for name, path in export_data.items()])
                
                export_df.to_parquet(temp_parquet_path)
                
                # Convert to CAR
                car_result = self.car_bridge.convert_parquet_to_car(
                    str(temp_parquet_path),
                    str(car_path)
                )
            else:
                car_result = {"success": False, "error": "No data to export or CAR bridge unavailable"}
            
            if car_result["success"]:
                return create_result_dict(
                    "export_to_car",
                    success=True,
                    data={
                        "car_path": str(car_path),
                        "car_cid": car_result.get("cid"),
                        "exported_items": len(export_data)
                    }
                )
            else:
                return car_result
            
        except Exception as e:
            logger.error(f"Error in export_to_car: {e}")
            return create_result_dict(
                "export_to_car",
                success=False,
                error=f"Failed to export to CAR: {str(e)}"
            )
    
    async def register_duckdb_tables(self, duckdb_conn):
        """Register bucket data as DuckDB tables for SQL queries."""
        try:
            if not DUCKDB_AVAILABLE:
                return
            
            # Register Parquet files as tables
            parquet_files = list(self.dirs["parquet"].glob("*.parquet"))
            
            for parquet_file in parquet_files:
                table_name = f"{self.name}_{parquet_file.stem}"
                duckdb_conn.execute(
                    f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{parquet_file}')"
                )
            
            logger.info(f"Registered {len(parquet_files)} tables for bucket '{self.name}'")
            
        except Exception as e:
            logger.error(f"Failed to register DuckDB tables for bucket '{self.name}': {e}")
    
    async def load_existing(self):
        """Load existing bucket data from disk."""
        try:
            metadata_file = self.dirs["metadata"] / "bucket_metadata.json"
            if metadata_file.exists():
                async with aiofiles.open(metadata_file, 'r') as f:
                    content = await f.read()
                    self.metadata = json.loads(content)
                    self.created_at = self.metadata.get("created_at")
                    self.root_cid = self.metadata.get("root_cid")
            
            # Reinitialize components
            await self._initialize_components()
            
        except Exception as e:
            logger.error(f"Failed to load existing bucket '{self.name}': {e}")
    
    async def _save_metadata(self):
        """Save bucket metadata to disk."""
        try:
            metadata_file = self.dirs["metadata"] / "bucket_metadata.json"
            
            metadata_to_save = {
                **self.metadata,
                "root_cid": self.root_cid,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            async with aiofiles.open(metadata_file, 'w') as f:
                await f.write(json.dumps(metadata_to_save, indent=2))
            
        except Exception as e:
            logger.error(f"Failed to save bucket metadata: {e}")
    
    async def cleanup(self):
        """Clean up bucket resources."""
        try:
            # Close any open connections
            if self.knowledge_graph:
                # Persist any pending changes
                await asyncio.to_thread(self.knowledge_graph._persist_indexes)
            
            # Remove storage directory
            import shutil
            if self.storage_path.exists():
                shutil.rmtree(self.storage_path)
            
        except Exception as e:
            logger.error(f"Failed to cleanup bucket '{self.name}': {e}")


# Global instance
_bucket_manager: Optional[BucketVFSManager] = None


def get_global_bucket_manager(**kwargs) -> BucketVFSManager:
    """Get or create global bucket VFS manager instance."""
    global _bucket_manager
    if _bucket_manager is None:
        _bucket_manager = BucketVFSManager(**kwargs)
    return _bucket_manager
