"""
Parquet-IPLD Bridge for IPFS Kit.

This module implements a bridge between Apache Parquet/Arrow storage and IPLD 
content addressing, enabling Parquet datasets to be stored and retrieved as 
IPLD-addressable content within the tiered storage hierarchy.

Key features:
1. Parquet datasets as IPLD-addressable content
2. Content-addressed Parquet partitions
3. Integration with existing tiered cache and VFS
4. Arrow-optimized data pipelines
5. Metadata indexing with fast queries
6. Replication and WAL integration

This bridge enables efficient storage of structured data (DataFrames, tables)
while maintaining IPFS content addressing and distributed storage benefits.
"""

import os
import time
import json
import logging
import hashlib
import tempfile
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple, BinaryIO
from pathlib import Path

# Import Arrow/Parquet dependencies
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    from pyarrow.dataset import dataset
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

# Import IPFS Kit components with protobuf conflict protection
try:
    from .error import IPFSError, create_result_dict, handle_error
    IPFS_ERROR_AVAILABLE = True
except ImportError:
    IPFS_ERROR_AVAILABLE = False
    # Create minimal error handling
    def create_result_dict(operation: str) -> Dict[str, Any]:
        return {"operation": operation, "success": False}
    
    def handle_error(operation: str, error: Exception) -> Dict[str, Any]:
        return {"operation": operation, "success": False, "error": str(error)}
    
    class IPFSError(Exception):
        pass

# Optional IPLD extension (may cause protobuf conflicts)
try:
    from .ipld_extension import IPLDExtension
    IPLD_AVAILABLE = True
except ImportError as e:
    IPLD_AVAILABLE = False
    logging.warning(f"IPLD extension not available (protobuf conflicts): {e}")
    
    # Create mock IPLD extension
    class IPLDExtension:
        def __init__(self, ipfs_client=None):
            self.ipfs_client = ipfs_client
            logging.warning("Using mock IPLD extension - some features disabled")

# Import existing components for integration
try:
    from .tiered_cache_manager import TieredCacheManager
    from .arc_cache import ARCache
    from .storage_wal import StorageWriteAheadLog, OperationType, BackendType
    from .fs_journal_replication import MetadataReplicationManager
    from .arrow_metadata_index import ArrowMetadataIndex
    STORAGE_COMPONENTS_AVAILABLE = True
except ImportError as e:
    STORAGE_COMPONENTS_AVAILABLE = False
    logging.warning(f"Some storage components not available for ParquetIPLDBridge: {e}")
    
    # Create minimal mocks
    class TieredCacheManager:
        def __init__(self, *args, **kwargs): pass
        def get(self, key): return None
        def set(self, key, value): pass
    
    class StorageWriteAheadLog:
        def __init__(self, *args, **kwargs): pass
        def log_operation(self, *args, **kwargs): pass
    
    class MetadataReplicationManager:
        def __init__(self, *args, **kwargs): pass
        def replicate_metadata(self, *args, **kwargs): pass
    
    class ArrowMetadataIndex:
        def __init__(self, *args, **kwargs): pass
        def index_metadata(self, *args, **kwargs): pass

logger = logging.getLogger(__name__)


class ParquetIPLDBridge:
    """
    Bridge between Parquet/Arrow storage and IPLD content addressing.
    
    This class enables storing structured data (DataFrames, tables) as 
    content-addressed Parquet files that can be retrieved and manipulated
    through IPFS/IPLD while leveraging Arrow's columnar efficiency.
    """
    
    def __init__(
        self,
        storage_path: str = "~/.ipfs_parquet_storage",
        ipfs_client = None,
        cache_manager: Optional[TieredCacheManager] = None,
        wal_manager: Optional[StorageWriteAheadLog] = None,
        replication_manager: Optional[MetadataReplicationManager] = None,
        metadata_index: Optional[ArrowMetadataIndex] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the Parquet-IPLD bridge.
        
        Args:
            storage_path: Base path for Parquet storage
            ipfs_client: IPFS client instance
            cache_manager: Tiered cache manager
            wal_manager: Write-ahead log manager
            replication_manager: Metadata replication manager
            metadata_index: Arrow metadata index
            config: Configuration options
        """
        if not ARROW_AVAILABLE:
            raise ImportError("PyArrow is required for ParquetIPLDBridge. Install with: pip install pyarrow")
        
        self.storage_path = os.path.expanduser(storage_path)
        self.partitions_path = os.path.join(self.storage_path, "partitions")
        self.metadata_path = os.path.join(self.storage_path, "metadata")
        self.ipfs_client = ipfs_client
        
        # Create storage directories
        os.makedirs(self.partitions_path, exist_ok=True)
        os.makedirs(self.metadata_path, exist_ok=True)
        
        # Initialize integrated components
        self.cache_manager = cache_manager
        self.wal_manager = wal_manager
        self.replication_manager = replication_manager
        self.metadata_index = metadata_index
        
        # Initialize IPLD extension for CAR/DAG operations
        self.ipld = IPLDExtension(ipfs_client)
        
        # Configuration
        self.config = config or {}
        self.max_partition_size = self.config.get("max_partition_size", 100 * 1024 * 1024)  # 100MB
        self.compression = self.config.get("compression", "zstd")
        self.enable_replication = self.config.get("enable_replication", True)
        self.enable_wal = self.config.get("enable_wal", True)
        
        # Content addressing
        self.cid_to_path = {}  # Map CIDs to local Parquet files
        self.path_to_cid = {}  # Map local paths to CIDs
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info(f"ParquetIPLDBridge initialized with storage at {self.storage_path}")
    
    def store_dataframe(
        self,
        df: Any,  # DataFrame-like object (pandas, polars, pyarrow)
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        partition_cols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Store a DataFrame as content-addressed Parquet with IPLD integration.
        
        Args:
            df: DataFrame to store (pandas, polars, or pyarrow Table)
            name: Optional name for the dataset
            metadata: Additional metadata to store
            partition_cols: Columns to partition by
            
        Returns:
            Dict with operation result and CID
        """
        result = create_result_dict("store_dataframe")
        
        try:
            # Convert to Arrow Table for consistent handling
            if hasattr(df, 'to_arrow'):
                # Polars DataFrame
                table = df.to_arrow()
            elif hasattr(df, 'to_pyarrow'):
                # Pandas DataFrame with pyarrow backend
                table = df.to_pyarrow()
            elif isinstance(df, pa.Table):
                # Already Arrow Table
                table = df
            else:
                # Try pandas conversion
                table = pa.Table.from_pandas(df)
            
            # Generate content-based identifier
            table_hash = self._compute_table_hash(table)
            timestamp = int(time.time())
            
            if name:
                cid_base = f"{name}_{table_hash}_{timestamp}"
            else:
                cid_base = f"table_{table_hash}_{timestamp}"
            
            # Create Parquet file path
            parquet_filename = f"{cid_base}.parquet"
            parquet_path = os.path.join(self.partitions_path, parquet_filename)
            
            # Store enhanced metadata
            storage_metadata = {
                "original_metadata": metadata or {},
                "schema": table.schema.to_string(),
                "num_rows": len(table),
                "num_columns": len(table.columns),
                "column_names": table.column_names,
                "column_types": [str(field.type) for field in table.schema],
                "size_bytes": 0,  # Will be filled after writing
                "timestamp": timestamp,
                "compression": self.compression,
                "partition_cols": partition_cols or []
            }
            
            # Write to WAL if enabled
            if self.enable_wal and self.wal_manager:
                wal_entry = {
                    "operation_type": OperationType.ADD,
                    "backend_type": BackendType.CUSTOM,
                    "operation_data": {
                        "parquet_path": parquet_path,
                        "table_hash": table_hash,
                        "metadata": storage_metadata
                    }
                }
                self.wal_manager.log_operation(**wal_entry)
            
            # Write Parquet file with optimized settings
            with self._lock:
                if partition_cols:
                    # Partitioned dataset
                    dataset_path = os.path.join(self.partitions_path, cid_base)
                    os.makedirs(dataset_path, exist_ok=True)
                    
                    pq.write_to_dataset(
                        table,
                        root_path=dataset_path,
                        partition_cols=partition_cols,
                        compression=self.compression,
                        use_dictionary=True,
                        row_group_size=50000,
                        data_page_size=1024*1024  # 1MB pages
                    )
                    
                    # Calculate total size
                    total_size = sum(
                        os.path.getsize(os.path.join(root, file))
                        for root, _, files in os.walk(dataset_path)
                        for file in files
                    )
                    storage_metadata["size_bytes"] = total_size
                    storage_metadata["is_partitioned"] = True
                    storage_metadata["dataset_path"] = dataset_path
                    
                else:
                    # Single file
                    pq.write_table(
                        table,
                        parquet_path,
                        compression=self.compression,
                        use_dictionary=True,
                        row_group_size=50000,
                        data_page_size=1024*1024
                    )
                    
                    storage_metadata["size_bytes"] = os.path.getsize(parquet_path)
                    storage_metadata["is_partitioned"] = False
                    storage_metadata["file_path"] = parquet_path
            
            # Generate IPFS-compatible CID
            cid = self._generate_cid_from_metadata(storage_metadata)
            
            # Store mapping
            with self._lock:
                self.cid_to_path[cid] = parquet_path if not partition_cols else dataset_path
                self.path_to_cid[parquet_path if not partition_cols else dataset_path] = cid
            
            # Add to metadata index
            if self.metadata_index:
                try:
                    index_metadata = {
                        "cid": cid,
                        "content_type": "application/parquet",
                        "size": storage_metadata["size_bytes"],
                        "timestamp": timestamp,
                        "schema_hash": hashlib.sha256(table.schema.to_string().encode()).hexdigest(),
                        "table_metadata": storage_metadata
                    }
                    self.metadata_index.add_record(index_metadata)
                except Exception as e:
                    logger.warning(f"Failed to add to metadata index: {e}")
            
            # Add to cache if available
            if self.cache_manager:
                try:
                    # Store metadata in cache for quick access
                    cache_data = {
                        "metadata": storage_metadata,
                        "cid": cid,
                        "path": parquet_path if not partition_cols else dataset_path
                    }
                    self.cache_manager.put(cid, json.dumps(cache_data).encode(), storage_metadata)
                except Exception as e:
                    logger.warning(f"Failed to add to cache: {e}")
            
            # Trigger replication if enabled
            if self.enable_replication and self.replication_manager:
                try:
                    replication_data = {
                        "cid": cid,
                        "metadata": storage_metadata,
                        "content_type": "parquet_dataset"
                    }
                    self.replication_manager.replicate_metadata(replication_data)
                except Exception as e:
                    logger.warning(f"Failed to trigger replication: {e}")
            
            result.update({
                "success": True,
                "cid": cid,
                "size_bytes": storage_metadata["size_bytes"],
                "num_rows": storage_metadata["num_rows"],
                "num_columns": storage_metadata["num_columns"],
                "compression": self.compression,
                "is_partitioned": storage_metadata.get("is_partitioned", False),
                "storage_path": parquet_path if not partition_cols else dataset_path
            })
            
            logger.info(f"Stored DataFrame as CID {cid} ({storage_metadata['size_bytes']} bytes)")
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def retrieve_dataframe(
        self,
        cid: str,
        columns: Optional[List[str]] = None,
        filters: Optional[List] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieve a DataFrame from content-addressed Parquet storage.
        
        Args:
            cid: Content identifier
            columns: Specific columns to retrieve
            filters: PyArrow filters to apply
            use_cache: Whether to use cache
            
        Returns:
            Dict with operation result and DataFrame
        """
        result = create_result_dict("retrieve_dataframe")
        
        try:
            # Check cache first
            if use_cache and self.cache_manager:
                cached = self.cache_manager.get(cid)
                if cached:
                    cache_data = json.loads(cached.decode())
                    result["from_cache"] = True
                    result["cache_metadata"] = cache_data.get("metadata", {})
            
            # Get storage path
            with self._lock:
                storage_path = self.cid_to_path.get(cid)
            
            if not storage_path:
                # Try to locate by scanning storage
                storage_path = self._find_storage_path_by_cid(cid)
                if storage_path:
                    with self._lock:
                        self.cid_to_path[cid] = storage_path
            
            if not storage_path or not os.path.exists(storage_path):
                raise FileNotFoundError(f"Content with CID {cid} not found in storage")
            
            # Read Parquet data
            if os.path.isdir(storage_path):
                # Partitioned dataset
                dataset_obj = dataset(storage_path, format="parquet")
                
                # Apply filters and column selection
                scanner = dataset_obj.scanner(
                    columns=columns,
                    filter=filters[0] if filters else None
                )
                table = scanner.to_table()
            else:
                # Single file
                table = pq.read_table(
                    storage_path,
                    columns=columns,
                    filters=filters
                )
            
            # Get metadata
            metadata_path = os.path.join(self.metadata_path, f"{cid}_metadata.json")
            stored_metadata = {}
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    stored_metadata = json.load(f)
            
            result.update({
                "success": True,
                "table": table,
                "cid": cid,
                "num_rows": len(table),
                "num_columns": len(table.columns),
                "column_names": table.column_names,
                "schema": table.schema.to_string(),
                "metadata": stored_metadata,
                "storage_path": storage_path
            })
            
            logger.info(f"Retrieved DataFrame for CID {cid} ({len(table)} rows, {len(table.columns)} columns)")
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def query_dataframes(
        self,
        sql: str,
        cid_aliases: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute SQL queries across stored Parquet datasets.
        
        Args:
            sql: SQL query string
            cid_aliases: Map of table aliases to CIDs
            
        Returns:
            Dict with query result
        """
        result = create_result_dict("query_dataframes")
        
        try:
            import pyarrow.sql as pa_sql
            
            # Build context with available datasets
            context = {}
            
            if cid_aliases:
                for alias, cid in cid_aliases.items():
                    retrieve_result = self.retrieve_dataframe(cid, use_cache=True)
                    if retrieve_result["success"]:
                        context[alias] = retrieve_result["table"]
            
            # Execute query
            query_result = pa_sql.execute(sql, context)
            
            result.update({
                "success": True,
                "result_table": query_result,
                "num_rows": len(query_result),
                "num_columns": len(query_result.columns),
                "sql": sql
            })
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def _compute_table_hash(self, table: pa.Table) -> str:
        """Compute content hash for Arrow Table."""
        # Use schema and a sample of data for hashing
        schema_str = table.schema.to_string()
        
        # Get deterministic sample
        sample_size = min(1000, len(table))
        if sample_size > 0:
            sample_table = table.slice(0, sample_size)
            # Convert to string representation for hashing
            sample_str = str(sample_table.to_pydict())
        else:
            sample_str = ""
        
        # Combine schema and sample
        content = f"{schema_str}:{sample_str}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _generate_cid_from_metadata(self, metadata: Dict[str, Any]) -> str:
        """Generate IPFS-compatible CID from metadata."""
        # Create deterministic string from metadata
        meta_str = json.dumps(metadata, sort_keys=True)
        content_hash = hashlib.sha256(meta_str.encode()).hexdigest()
        
        # Create CID-like identifier (simplified)
        # In a full implementation, this would use proper IPFS CID generation
        return f"bafy{content_hash[:52]}"
    
    def _find_storage_path_by_cid(self, cid: str) -> Optional[str]:
        """Find storage path by scanning for CID in metadata."""
        try:
            # Check for metadata file
            metadata_path = os.path.join(self.metadata_path, f"{cid}_metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    return metadata.get("file_path") or metadata.get("dataset_path")
            
            # Fallback: scan partition directory
            for filename in os.listdir(self.partitions_path):
                if cid in filename:
                    path = os.path.join(self.partitions_path, filename)
                    return path
                    
        except Exception as e:
            logger.warning(f"Error finding storage path for CID {cid}: {e}")
        
        return None
    
    def list_datasets(self) -> Dict[str, Any]:
        """List all stored datasets with metadata."""
        result = create_result_dict("list_datasets")
        
        try:
            datasets = []
            
            with self._lock:
                for cid, path in self.cid_to_path.items():
                    if os.path.exists(path):
                        # Get basic info
                        is_dir = os.path.isdir(path)
                        
                        if is_dir:
                            # Partitioned dataset
                            total_size = sum(
                                os.path.getsize(os.path.join(root, file))
                                for root, _, files in os.walk(path)
                                for file in files if file.endswith('.parquet')
                            )
                        else:
                            # Single file
                            total_size = os.path.getsize(path)
                        
                        # Try to get metadata
                        metadata_path = os.path.join(self.metadata_path, f"{cid}_metadata.json")
                        stored_metadata = {}
                        if os.path.exists(metadata_path):
                            with open(metadata_path, 'r') as f:
                                stored_metadata = json.load(f)
                        
                        datasets.append({
                            "cid": cid,
                            "path": path,
                            "is_partitioned": is_dir,
                            "size_bytes": total_size,
                            "metadata": stored_metadata
                        })
            
            result.update({
                "success": True,
                "datasets": datasets,
                "total_datasets": len(datasets)
            })
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def delete_dataset(self, cid: str) -> Dict[str, Any]:
        """Delete a dataset and its metadata."""
        result = create_result_dict("delete_dataset")
        
        try:
            with self._lock:
                storage_path = self.cid_to_path.get(cid)
                
                if storage_path and os.path.exists(storage_path):
                    if os.path.isdir(storage_path):
                        import shutil
                        shutil.rmtree(storage_path)
                    else:
                        os.remove(storage_path)
                
                # Remove from mappings
                if cid in self.cid_to_path:
                    del self.cid_to_path[cid]
                if storage_path in self.path_to_cid:
                    del self.path_to_cid[storage_path]
            
            # Remove metadata file
            metadata_path = os.path.join(self.metadata_path, f"{cid}_metadata.json")
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
            
            # Remove from cache
            if self.cache_manager:
                self.cache_manager.evict(cid)
            
            result.update({
                "success": True,
                "cid": cid,
                "deleted_path": storage_path
            })
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics and health information."""
        result = create_result_dict("get_storage_stats")
        
        try:
            total_files = 0
            total_size = 0
            partitioned_datasets = 0
            single_files = 0
            
            for root, dirs, files in os.walk(self.storage_path):
                for file in files:
                    if file.endswith('.parquet'):
                        file_path = os.path.join(root, file)
                        total_files += 1
                        total_size += os.path.getsize(file_path)
            
            # Count datasets
            with self._lock:
                for path in self.cid_to_path.values():
                    if os.path.isdir(path):
                        partitioned_datasets += 1
                    else:
                        single_files += 1
            
            result.update({
                "success": True,
                "total_parquet_files": total_files,
                "total_size_bytes": total_size,
                "total_datasets": len(self.cid_to_path),
                "partitioned_datasets": partitioned_datasets,
                "single_file_datasets": single_files,
                "storage_path": self.storage_path,
                "cache_enabled": self.cache_manager is not None,
                "wal_enabled": self.wal_manager is not None,
                "replication_enabled": self.replication_manager is not None
            })
            
        except Exception as e:
            handle_error(result, e, logger)
        
        return result
