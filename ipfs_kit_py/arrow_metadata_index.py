"""
Arrow-based metadata index for IPFS content.

This module implements the Arrow-based metadata index (Phase 4A Milestone 4.1), providing:
- Efficient metadata storage using Apache Arrow columnar format
- Parquet persistence for durability
- Fast querying capabilities
- Distributed index synchronization
- Zero-copy access via Arrow C Data Interface
"""

import os
import time
import json
import uuid
import logging
import threading
import mmap
import math
import tempfile
import shutil
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from datetime import datetime
import copy
import pickle
import concurrent.futures

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    from pyarrow.dataset import dataset
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

try:
    import pyarrow.plasma as plasma
    PLASMA_AVAILABLE = True
except ImportError:
    PLASMA_AVAILABLE = False

# Create logger
logger = logging.getLogger(__name__)


class ArrowMetadataIndex:
    """
    Apache Arrow-based metadata index for IPFS content.
    
    This class provides efficient storage and querying of metadata for IPFS content
    using Arrow's columnar format and Parquet persistence. It supports:
    - High-performance in-memory operations
    - Persistence to Parquet files
    - Advanced query capabilities
    - Efficient memory usage with memory mapping
    - Zero-copy access via Arrow C Data Interface
    - Distributed index synchronization
    """
    
    def __init__(self, 
                 index_dir: str = "~/.ipfs_metadata",
                 partition_size: int = 1000000,
                 role: str = "leecher",
                 sync_interval: int = 300,
                 enable_c_interface: bool = True,
                 ipfs_client = None,
                 node_id: Optional[str] = None): # Added node_id
        """
        Initialize the Arrow-based metadata index.
        
        Args:
            index_dir: Directory to store index partitions
            partition_size: Maximum number of records per partition
            role: Node role (master, worker, or leecher)
            sync_interval: Interval for synchronizing with peers (seconds)
            enable_c_interface: Whether to enable the Arrow C Data Interface
            ipfs_client: IPFS client instance for distributed operations
        """
        if not ARROW_AVAILABLE:
            raise ImportError("PyArrow is required for the metadata index.")
        
        self.logger = logger
        self.index_dir = os.path.expanduser(index_dir)
        os.makedirs(self.index_dir, exist_ok=True)
        self.partition_size = partition_size
        self.role = role
        self.sync_interval = sync_interval
        self.enable_c_interface = enable_c_interface and PLASMA_AVAILABLE
        self.ipfs_client = ipfs_client
        self.node_id = node_id # Store node_id
        
        # Set up schema
        self.schema = self._create_default_schema()
        
        # Initialize partitions
        self.partitions = self._discover_partitions()
        self.current_partition_id = max(self.partitions.keys()) if self.partitions else 0
        
        # Memory-mapped access to partition files
        self.mmap_files = {}
        
        # In-memory record batch for fast writes
        self.record_batch = None
        
        # Shared memory for C Data Interface
        self.plasma_client = None
        self.c_data_interface_handle = None
        self.current_object_id = None
        
        # Load current partition
        self._load_current_partition()
        
        # Thread for background operations
        self.sync_thread = None
        self.should_stop = threading.Event()
        
        # Start sync thread if master or worker
        if role in ("master", "worker"):
            self._start_sync_thread()
    
    def _create_default_schema(self) -> pa.Schema:
        """
        Create the default Arrow schema for IPFS metadata.
        
        Returns:
            PyArrow schema object
        """
        return pa.schema([
            # Content identifiers
            pa.field('cid', pa.string()),
            pa.field('cid_version', pa.int8()),
            pa.field('multihash_type', pa.string()),
            
            # Basic metadata
            pa.field('size_bytes', pa.int64()),
            pa.field('blocks', pa.int32()),
            pa.field('links', pa.int32()),
            pa.field('mime_type', pa.string()),
            
            # Storage status
            pa.field('local', pa.bool_()),
            pa.field('pinned', pa.bool_()),
            pa.field('pin_types', pa.list_(pa.string())),
            pa.field('replication', pa.int16()),
            
            # Temporal metadata
            pa.field('created_at', pa.timestamp('ms')),
            pa.field('last_accessed', pa.timestamp('ms')),
            pa.field('access_count', pa.int32()),
            
            # Content organization
            pa.field('path', pa.string()),
            pa.field('filename', pa.string()),
            pa.field('extension', pa.string()),
            
            # Custom metadata
            pa.field('tags', pa.list_(pa.string())),
            pa.field('metadata', pa.struct([
                pa.field('title', pa.string()),
                pa.field('description', pa.string()),
                pa.field('creator', pa.string()),
                pa.field('source', pa.string()),
                pa.field('license', pa.string())
            ])),
            
            # Extended properties as key-value pairs
            pa.field('properties', pa.map_(pa.string(), pa.string())),
            
            # Vector embedding if available
            pa.field('embedding_available', pa.bool_()),
            pa.field('embedding_type', pa.string()),
            pa.field('embedding_dimensions', pa.int32()),
            
            # Indexing metadata
            pa.field('indexed_at', pa.timestamp('ms')),
            pa.field('index_version', pa.string()),
            pa.field('indexer_node_id', pa.string())
        ])
    
    def _discover_partitions(self) -> Dict[int, Dict[str, Any]]:
        """
        Scan the index directory to discover all partition files.
        
        Returns:
            Dictionary mapping partition IDs to metadata
        """
        partitions = {}
        
        try:
            for filename in os.listdir(self.index_dir):
                if not filename.startswith('ipfs_metadata_') or not filename.endswith('.parquet'):
                    continue
                    
                try:
                    # Extract partition ID from filename
                    partition_id = int(filename.split('_')[2].split('.')[0])
                    partition_path = os.path.join(self.index_dir, filename)
                    
                    # Get basic file stats
                    file_stats = os.stat(partition_path)
                    
                    partitions[partition_id] = {
                        'path': partition_path,
                        'size': file_stats.st_size,
                        'mtime': file_stats.st_mtime,
                        'rows': None  # Lazy-loaded
                    }
                    
                except (ValueError, IndexError) as e:
                    self.logger.warning(f"Invalid partition file {filename}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error discovering partitions: {e}")
        
        return partitions
    
    def _get_partition_path(self, partition_id: int) -> str:
        """
        Get the file path for a partition.
        
        Args:
            partition_id: ID of the partition
            
        Returns:
            File path for the partition
        """
        return os.path.join(self.index_dir, f"ipfs_metadata_{partition_id:06d}.parquet")
    
    def _load_current_partition(self) -> None:
        """
        Load the current partition into memory for fast access.
        """
        if self.current_partition_id in self.partitions:
            partition_path = self.partitions[self.current_partition_id]['path']
            
            if os.path.exists(partition_path):
                try:
                    # Use memory mapping for efficiency
                    table = pq.read_table(partition_path, memory_map=True)
                    
                    # Extract as record batch for efficient updates
                    if table.num_rows > 0:
                        self.record_batch = table.to_batches()[0]
                    else:
                        self.record_batch = None
                        
                    # Keep reference to memory mapping
                    file_obj = open(partition_path, 'rb')
                    mmap_obj = mmap.mmap(file_obj.fileno(), 0, access=mmap.ACCESS_READ)
                    self.mmap_files[partition_path] = (file_obj, mmap_obj)
                    
                    # Update partition metadata
                    self.partitions[self.current_partition_id]['rows'] = table.num_rows
                    
                    # Export to C Data Interface if enabled
                    if self.enable_c_interface:
                        self._export_to_c_data_interface()
                        
                    self.logger.debug(f"Loaded partition {self.current_partition_id} with {table.num_rows} rows")
                    
                except Exception as e:
                    self.logger.error(f"Error loading partition {partition_path}: {e}")
                    self.record_batch = None
            else:
                self.record_batch = None
        else:
            self.record_batch = None
    
    def _write_current_batch(self) -> bool:
        """
        Write the current record batch to a parquet file.
        
        Returns:
            True if successful, False otherwise
        """
        if self.record_batch is None or self.record_batch.num_rows == 0:
            return False
            
        try:
            # Convert batch to table
            table = pa.Table.from_batches([self.record_batch])
            
            # Get partition path
            partition_path = self._get_partition_path(self.current_partition_id)
            
            # Write with compression
            pq.write_table(
                table, 
                partition_path,
                compression='zstd',
                compression_level=5,
                use_dictionary=True,
                write_statistics=True
            )
            
            # Update partitions metadata
            self.partitions[self.current_partition_id] = {
                'path': partition_path,
                'size': os.path.getsize(partition_path),
                'mtime': os.path.getmtime(partition_path),
                'rows': table.num_rows
            }
            
            self.logger.debug(f"Wrote partition {self.current_partition_id} with {table.num_rows} rows")
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing partition: {e}")
            return False
    
    def _export_to_c_data_interface(self) -> Optional[Dict[str, Any]]:
        """
        Export the metadata index to Arrow C Data Interface.
        
        This allows zero-copy access from other languages and processes.
        
        Returns:
            Dictionary with C Data Interface metadata or None if failed
        """
        if not self.enable_c_interface or not PLASMA_AVAILABLE:
            return None
            
        try:
            # Create or connect to plasma store
            if not self.plasma_client:
                # Create a plasma store socket path in the index directory
                plasma_socket = os.path.join(self.index_dir, "plasma.sock")
                self.plasma_client = plasma.connect(plasma_socket)
            
            # Create shared table for C Data Interface
            if self.record_batch is not None:
                shared_table = pa.Table.from_batches([self.record_batch])
            else:
                # Create empty table with schema
                empty_arrays = []
                for field in self.schema:
                    empty_arrays.append(pa.array([], type=field.type))
                shared_table = pa.Table.from_arrays(empty_arrays, schema=self.schema)
            
            # Generate object ID for the table
            object_id = plasma.ObjectID(uuid.uuid4().bytes[:20])
            
            # Create and seal the object
            data_size = shared_table.nbytes
            buffer = self.plasma_client.create(object_id, data_size)
            
            # Write the table to the buffer
            writer = pa.RecordBatchStreamWriter(pa.FixedSizeBufferWriter(buffer), shared_table.schema)
            writer.write_table(shared_table)
            writer.close()
            
            # Seal the object
            self.plasma_client.seal(object_id)
            
            # Store the object ID for reference
            self.current_object_id = object_id
            
            # Create handle with metadata
            self.c_data_interface_handle = {
                'object_id': object_id.binary().hex(),
                'plasma_socket': os.path.join(self.index_dir, "plasma.sock"),
                'schema_json': self.schema.to_string(),
                'num_rows': shared_table.num_rows,
                'timestamp': time.time()
            }
            
            # Write handle to disk
            cdi_path = os.path.join(self.index_dir, 'c_data_interface.json')
            with open(cdi_path, 'w') as f:
                json.dump(self.c_data_interface_handle, f)
                
            self.logger.info(f"Exported metadata index to C Data Interface at {cdi_path}")
            return self.c_data_interface_handle
            
        except Exception as e:
            self.logger.error(f"Failed to export to C Data Interface: {e}")
            return None
    
    def get_c_data_interface(self) -> Optional[Dict[str, Any]]:
        """
        Get the C Data Interface handle for external access.
        
        Returns:
            Dictionary with C Data Interface metadata or None
        """
        return self.c_data_interface_handle
    
    def add(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a metadata record to the index.
        
        Args:
            record: Dictionary with metadata fields
            
        Returns:
            Result dictionary with operation status
        """
        result = {
            "success": False,
            "operation": "add_metadata",
            "timestamp": time.time()
        }
        
        if not ARROW_AVAILABLE:
            result["error"] = "PyArrow is not available"
            return result
        
        try:
            # Add current timestamp if not provided
            if 'indexed_at' not in record:
                # Convert to millisecond timestamp for Arrow
                record['indexed_at'] = pa.scalar(int(time.time() * 1000)).cast(pa.timestamp('ms'))
            
            # Add indexer node ID if not provided
            if 'indexer_node_id' not in record and hasattr(self, 'node_id'):
                record['indexer_node_id'] = getattr(self, 'node_id')
            
            # Convert to Arrow arrays
            arrays = []
            for field in self.schema:
                field_name = field.name
                if field_name in record:
                    # Convert value to Arrow array with proper type
                    try:
                        arrays.append(pa.array([record[field_name]], type=field.type))
                    except pa.ArrowInvalid:
                        # If conversion fails, use None instead
                        arrays.append(pa.array([None], type=field.type))
                else:
                    # Field not provided, use None
                    arrays.append(pa.array([None], type=field.type))
                    
            # Create a new record batch with just this record
            new_batch = pa.RecordBatch.from_arrays(arrays, schema=self.schema)
            
            # Add to existing batch or create new one
            if self.record_batch is None:
                self.record_batch = new_batch
            else:
                # Check if record with same CID already exists
                cid_field_index = self.schema.get_field_index('cid')
                if cid_field_index >= 0 and 'cid' in record:
                    # Get existing CIDs
                    existing_cids = self.record_batch.column(cid_field_index).to_pylist()
                    cid = record['cid']
                    
                    # If CID already exists, update the record instead of adding
                    if cid in existing_cids:
                        # Create a copy of the record batch without the matching CID
                        idx = existing_cids.index(cid)
                        mask = pa.compute.invert(pa.compute.equal(
                            pa.array(range(len(existing_cids))), 
                            pa.scalar(idx)
                        ))
                        filtered_batch = self.record_batch.filter(mask)
                        
                        # Concat the filtered batch with the new record
                        self.record_batch = pa.concat_batches([filtered_batch, new_batch])
                        result["updated"] = True
                    else:
                        # Append the new record
                        self.record_batch = pa.concat_batches([self.record_batch, new_batch])
                        result["updated"] = False
                else:
                    # Just append the record
                    self.record_batch = pa.concat_batches([self.record_batch, new_batch])
                    result["updated"] = False
            
            # Check if we need to write and create a new partition
            if self.record_batch.num_rows >= self.partition_size:
                self._write_current_batch()
                self.current_partition_id += 1
                self.record_batch = None
                result["partition_rotated"] = True
            
            # Update the C Data Interface if enabled
            if self.enable_c_interface:
                self._export_to_c_data_interface() # Corrected method name
                
            result["success"] = True
            result["cid"] = record.get('cid')
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            self.logger.error(f"Error adding record: {e}")
            
        return result
    
    def get_by_cid(self, cid: str) -> Optional[Dict[str, Any]]:
        """
        Get a metadata record by CID.
        
        Args:
            cid: Content identifier
            
        Returns:
            Metadata record or None if not found
        """
        try:
            # Check in-memory batch first
            if self.record_batch is not None:
                cid_field_index = self.schema.get_field_index('cid')
                if cid_field_index >= 0:
                    cids = self.record_batch.column(cid_field_index).to_pylist()
                    if cid in cids:
                        idx = cids.index(cid)
                        # Extract row as dictionary
                        row = {}
                        for i, field in enumerate(self.schema):
                            row[field.name] = self.record_batch.column(i)[idx].as_py()
                        return row
            
            # Not found in memory, search in all partitions
            query_results = self.query([("cid", "==", cid)], limit=1)
            
            if query_results.num_rows > 0:
                # Convert to dictionary
                row = {}
                for i, field in enumerate(self.schema):
                    row[field.name] = query_results.column(i)[0].as_py()
                return row
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting record by CID: {e}")
            return None
    
    def update_stats(self, cid: str, access_type: str = "read") -> bool:
        """
        Update access statistics for a record.
        
        Args:
            cid: Content identifier
            access_type: Type of access (read, write, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current record
            record = self.get_by_cid(cid)
            if not record:
                return False
                
            # Update access time and count
            now_ms = int(time.time() * 1000)  # Convert to milliseconds
            record["last_accessed"] = pa.scalar(now_ms).cast(pa.timestamp('ms'))
            record["access_count"] = record.get("access_count", 0) + 1
            
            # Add to index (will update existing record)
            result = self.add(record)
            return result.get("success", False)
            
        except Exception as e:
            self.logger.error(f"Error updating stats for CID {cid}: {e}")
            return False
    
    def delete_by_cid(self, cid: str) -> bool:
        """
        Delete a record by CID.
        
        Args:
            cid: Content identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if record exists
            if not self.get_by_cid(cid):
                return False
                
            # Delete from in-memory batch if present
            if self.record_batch is not None:
                cid_field_index = self.schema.get_field_index('cid')
                if cid_field_index >= 0:
                    cids = self.record_batch.column(cid_field_index).to_pylist()
                    if cid in cids:
                        # Filter out the record
                        idx = cids.index(cid)
                        mask = pa.compute.invert(pa.compute.equal(
                            pa.array(range(len(cids))), 
                            pa.scalar(idx)
                        ))
                        self.record_batch = self.record_batch.filter(mask)
                        
                        # Update C Data Interface
                        if self.enable_c_interface:
                            self._export_to_c_data_interface() # Corrected method name
                        
                        return True
            
            # Not found in memory, need to filter all partitions
            # This is inefficient but works for now
            # A better implementation would track CID to partition mapping
            
            # Query to get all records except the one to delete
            all_records = self.query([("cid", "!=", cid)])
            
            # Clear all partitions
            self._clear_all_partitions()
            
            # Create a new in-memory batch
            if all_records.num_rows > 0:
                self.record_batch = all_records.to_batches()[0]
                
                # Write to disk if needed
                if self.record_batch.num_rows >= self.partition_size:
                    self._write_current_batch()
                    self.current_partition_id += 1
                    self.record_batch = None
            else:
                self.record_batch = None
                
            # Update C Data Interface
            if self.enable_c_interface:
                self._export_to_c_data_interface() # Corrected method name
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting record for CID {cid}: {e}")
            return False
    
    def _clear_all_partitions(self) -> None:
        """
        Clear all partition files.
        """
        try:
            # Close and remove any memory-mapped files
            for path, (file_obj, mmap_obj) in list(self.mmap_files.items()):
                try:
                    mmap_obj.close()
                    file_obj.close()
                    del self.mmap_files[path]
                except Exception as e:
                    self.logger.warning(f"Error closing memory-mapped file {path}: {e}")
            
            # Remove partition files
            for partition_id in list(self.partitions.keys()):
                path = self.partitions[partition_id]['path']
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        self.logger.warning(f"Error removing partition file {path}: {e}")
                
                del self.partitions[partition_id]
                
            # Reset state
            self.current_partition_id = 0
            self.record_batch = None
            
        except Exception as e:
            self.logger.error(f"Error clearing partitions: {e}")
    
    def query(self, filters: Optional[List[Tuple[str, str, Any]]] = None, 
             columns: Optional[List[str]] = None, 
             limit: Optional[int] = None) -> pa.Table:
        """
        Query the metadata index.
        
        Args:
            filters: List of filter conditions as (field, op, value) tuples
            columns: List of columns to include in the result
            limit: Maximum number of rows to return
            
        Returns:
            Arrow Table with query results
        """
        try:
            # Create dataset from persisted partitions
            try:
                ds = dataset(self.index_dir, format="parquet", schema=self.schema)
                persisted_table = ds.to_table()
            except Exception as e:
                # Handle case where directory might be empty or contain invalid files
                self.logger.debug(f"Could not load dataset from {self.index_dir}: {e}")
                persisted_table = None

            # Combine with in-memory batch if it exists
            if self.record_batch is not None:
                in_memory_table = pa.Table.from_batches([self.record_batch])
                if persisted_table is not None and persisted_table.num_rows > 0:
                    # Need to handle potential schema evolution if necessary, but assume same for now
                    # Also handle potential duplicates between persisted and in-memory
                    combined_table = pa.concat_tables([persisted_table, in_memory_table])
                    # Remove duplicates based on CID, keeping the latest (from in-memory)
                    cid_field_index = self.schema.get_field_index('cid')
                    if cid_field_index >= 0:
                         # This is complex with Arrow tables directly. A simpler approach for now
                         # is to prioritize the in-memory batch for updates.
                         # Let's refine this if needed. For now, just concat.
                         # A more robust way might involve pandas or a dedicated merge strategy.
                         # For simplicity, let's just use the combined table for filtering.
                         table_to_filter = combined_table
                    else:
                         table_to_filter = combined_table

                else:
                    table_to_filter = in_memory_table
            elif persisted_table is not None:
                 table_to_filter = persisted_table
            else:
                 # Return empty table if neither persisted nor in-memory data exists
                 empty_arrays = []
                 schema_to_use = pa.schema([self.schema.field(col) for col in columns]) if columns else self.schema
                 for field in schema_to_use:
                     empty_arrays.append(pa.array([], type=field.type))
                 return pa.Table.from_arrays(empty_arrays, schema=schema_to_use)


            # Build filter expression
            filter_expr = None
            if filters:
                for field, op, value in filters:
                    field_expr = pc.field(field)
                    
                    # Convert operation string to Arrow compute function
                    if op == "==":
                        expr = pc.equal(field_expr, pa.scalar(value))
                    elif op == "!=":
                        expr = pc.not_equal(field_expr, pa.scalar(value))
                    elif op == ">":
                        expr = pc.greater(field_expr, pa.scalar(value))
                    elif op == ">=":
                        expr = pc.greater_equal(field_expr, pa.scalar(value))
                    elif op == "<":
                        expr = pc.less(field_expr, pa.scalar(value))
                    elif op == "<=":
                        expr = pc.less_equal(field_expr, pa.scalar(value))
                    elif op == "in":
                        if not isinstance(value, (list, tuple)):
                            value = [value]
                        expr = pc.is_in(field_expr, pa.array(value))
                    elif op == "contains":
                        expr = pc.match_substring(field_expr, value)
                    elif op == "starts_with":
                        expr = pc.starts_with(field_expr, value)
                    elif op == "ends_with":
                        expr = pc.ends_with(field_expr, value)
                    elif op == "is_null":
                        expr = pc.is_null(field_expr) if value else pc.is_valid(field_expr)
                    else:
                        raise ValueError(f"Unsupported operation: {op}")
                    
                    # Combine expressions with AND
                    if filter_expr is None:
                        filter_expr = expr
                    else:
                        filter_expr = pc.and_(filter_expr, expr)
            
            # Apply filter expression to the combined table
            if filter_expr is not None:
                table = table_to_filter.filter(filter_expr)
            else:
                table = table_to_filter

            # Select columns if specified
            if columns is not None:
                table = table.select(columns)
            
            # Apply limit if specified
            if limit is not None and limit < table.num_rows:
                table = table.slice(0, limit)
                
            return table
            
        except Exception as e:
            self.logger.error(f"Error executing query: {e}")
            # Return empty table with schema
            empty_arrays = []
            if columns is not None:
                schema_fields = [field for field in self.schema if field.name in columns]
                schema = pa.schema(schema_fields)
            else:
                schema = self.schema
                
            for field in schema:
                empty_arrays.append(pa.array([], type=field.type))
            
            return pa.Table.from_arrays(empty_arrays, schema=schema)
    
    def search_text(self, text: str, fields: Optional[List[str]] = None, 
                   limit: Optional[int] = None) -> pa.Table:
        """
        Search for text across multiple fields.
        
        Args:
            text: Text to search for
            fields: Fields to search in (defaults to all string fields)
            limit: Maximum number of results to return
            
        Returns:
            Arrow Table with search results
        """
        try:
            # Determine which fields to search
            if fields is None:
                # Get all string fields
                fields = []
                for field in self.schema:
                    # Use pa.string() for type check
                    if (isinstance(field.type, type(pa.string())) or
                        isinstance(field.type, pa.ListType) and isinstance(field.type.value_type, type(pa.string())) or # list<string> for tags
                        isinstance(field.type, pa.MapType)): # map<string, string> for properties
                        # TODO: Handle map search properly if needed
                        if not isinstance(field.type, pa.MapType):
                             fields.append(field.name)
            
            # Build a combined filter for all fields
            filters = []
            for field in fields:
                filters.append((field, "contains", text))
                
            # Execute query for each field separately and combine results
            results = []
            for field_filter in filters:
                field_results = self.query([field_filter], limit=limit)
                if field_results.num_rows > 0:
                    results.append(field_results)
            
            if not results:
                # Return empty table with schema
                empty_arrays = []
                for field in self.schema:
                    empty_arrays.append(pa.array([], type=field.type))
                return pa.Table.from_arrays(empty_arrays, schema=self.schema)
            
            # Combine results and remove duplicates
            combined = pa.concat_tables(results)
            
            # Remove duplicates based on CID
            cid_field_index = self.schema.get_field_index('cid')
            if cid_field_index >= 0:
                cids = combined.column(cid_field_index).to_pylist()
                unique_cids = []
                unique_indices = []
                
                for i, cid in enumerate(cids):
                    if cid not in unique_cids:
                        unique_cids.append(cid)
                        unique_indices.append(i)
                
                # Extract unique rows
                combined = combined.take(pa.array(unique_indices))
            
            # Apply limit if specified
            if limit is not None and limit < combined.num_rows:
                combined = combined.slice(0, limit)
                
            return combined
            
        except Exception as e:
            self.logger.error(f"Error executing text search: {e}")
            # Return empty table with schema
            empty_arrays = []
            for field in self.schema:
                empty_arrays.append(pa.array([], type=field.type))
            return pa.Table.from_arrays(empty_arrays, schema=self.schema)
    
    def count(self, filters: Optional[List[Tuple[str, str, Any]]] = None) -> int:
        """
        Count records matching filters.
        
        Args:
            filters: List of filter conditions as (field, op, value) tuples
            
        Returns:
            Number of matching records
        """
        try:
            results = self.query(filters)
            return results.num_rows
            
        except Exception as e:
            self.logger.error(f"Error counting records: {e}")
            return 0
    
    def _start_sync_thread(self) -> None:
        """
        Start a thread for periodic index synchronization.
        """
        if self.role not in ("master", "worker"):
            return
            
        # Stop existing thread if any
        if self.sync_thread and self.sync_thread.is_alive():
            self.should_stop.set()
            self.sync_thread.join(timeout=5)
            
        # Clear stop flag
        self.should_stop.clear()
        
        # Create and start new thread
        self.sync_thread = threading.Thread(
            target=self._sync_thread_main,
            name="MetadataIndexSync",
            daemon=True
        )
        self.sync_thread.start()
        self.logger.info(f"Started metadata index sync thread with interval {self.sync_interval}s")
    
    def _sync_thread_main(self) -> None:
        """
        Main function for the synchronization thread.
        """
        while not self.should_stop.wait(0.1):  # Quick initial check
            try:
                # Write current batch to disk if needed
                if self.record_batch is not None and self.record_batch.num_rows > 0:
                    self._write_current_batch()
                
                # Sync with peers if we have an IPFS client
                if self.ipfs_client:
                    self._sync_with_peers()
                    
            except Exception as e:
                self.logger.error(f"Error in sync thread: {e}")
                
            # Sleep until next sync interval or until stopped
            if self.should_stop.wait(self.sync_interval):
                break
                
        self.logger.info("Metadata index sync thread stopped")
    
    def _sync_with_peers(self) -> Dict[str, Any]:
        """
        Synchronize index with peers.
        
        Returns:
            Result dictionary with sync status
        """
        result = {
            "success": False,
            "operation": "sync_with_peers",
            "timestamp": time.time(),
            "peers_found": 0,
            "partitions_synced": 0
        }
        
        try:
            # Get list of peers
            peers = self._get_peers()
            result["peers_found"] = len(peers)
            
            if not peers:
                result["message"] = "No peers found for synchronization"
                return result
                
            # Get list of our partitions with timestamps
            local_partitions = {}
            for partition_id, metadata in self.partitions.items():
                local_partitions[partition_id] = {
                    'mtime': metadata['mtime'],
                    'size': metadata['size']
                }
                
            # For each peer, compare partitions and sync as needed
            synced_partitions = 0
            
            for peer in peers:
                try:
                    # Exchange partition metadata with peer
                    peer_partitions = self._get_peer_partitions(peer)
                    
                    if not peer_partitions:
                        continue
                        
                    # Compare partitions and download newer ones
                    for partition_id, metadata in peer_partitions.items():
                        partition_id = int(partition_id)
                        
                        # Skip if we have a newer version
                        if (partition_id in local_partitions and 
                            local_partitions[partition_id]['mtime'] >= metadata['mtime']):
                            continue
                            
                        # Download partition
                        if self._download_partition(peer, partition_id, metadata):
                            synced_partitions += 1
                            
                except Exception as e:
                    self.logger.warning(f"Error syncing with peer {peer}: {e}")
                    
            result["partitions_synced"] = synced_partitions
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Error syncing with peers: {e}")
            
        return result
    
    def _get_peers(self) -> List[str]:
        """
        Get list of peers for synchronization.
        
        Returns:
            List of peer IDs
        """
        peers = []
        
        try:
            if self.ipfs_client and hasattr(self.ipfs_client, 'ipfs_swarm_peers'):
                # Get peers from IPFS swarm
                peers_result = self.ipfs_client.ipfs_swarm_peers()
                
                if peers_result and peers_result.get("success", False):
                    for peer in peers_result.get("Peers", []):
                        if isinstance(peer, dict) and "Peer" in peer:
                            peers.append(peer["Peer"])
                        elif isinstance(peer, str):
                            peers.append(peer)
                            
        except Exception as e:
            self.logger.error(f"Error getting peers: {e}")
            
        return peers
    
    def _get_peer_partitions(self, peer_id: str) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Get partition metadata from a peer.
        
        Args:
            peer_id: ID of the peer
            
        Returns:
            Dictionary mapping partition IDs to metadata or None
        """
        if not self.ipfs_client:
            self.logger.warning("No IPFS client available for peer communication")
            return None
            
        try:
            # Create a topic specific to metadata index partition exchange
            topic = f"ipfs-kit/metadata-index/{self.cluster_id}/partitions"
            
            # Create a message with request for partitions
            message = {
                "type": "partition_request",
                "requester": self.node_id,
                "timestamp": time.time(),
                "request_id": str(uuid.uuid4())
            }
            
            # Create an event to signal when we receive a response
            response_event = threading.Event()
            response_data = {}
            
            # Create a callback to handle responses
            def handle_partition_response(msg):
                try:
                    msg_data = json.loads(msg.get("data", "{}"))
                    if (msg_data.get("type") == "partition_response" and 
                        msg_data.get("request_id") == message["request_id"]):
                        response_data.update(msg_data.get("partitions", {}))
                        response_event.set()
                except Exception as e:
                    self.logger.error(f"Error handling partition response: {e}")
            
            # Subscribe to the response topic temporarily
            response_topic = f"{topic}/responses"
            if hasattr(self.ipfs_client, 'pubsub_subscribe'):
                self.ipfs_client.pubsub_subscribe(response_topic, handle_partition_response)
            
            # Publish request
            if hasattr(self.ipfs_client, 'pubsub_publish'):
                self.ipfs_client.pubsub_publish(topic, json.dumps(message))
                
                # Wait for response with timeout
                if response_event.wait(timeout=30):
                    # Success - we got data
                    return response_data
                else:
                    self.logger.warning(f"Timeout waiting for partition data from peer {peer_id}")
                    return None
            else:
                # Fallback to DAG-based exchange if pubsub not available
                return self._get_peer_partitions_via_dag(peer_id)
                
        except Exception as e:
            self.logger.error(f"Error getting partitions from peer {peer_id}: {e}")
            return None
        finally:
            # Unsubscribe from response topic
            if hasattr(self.ipfs_client, 'pubsub_unsubscribe'):
                self.ipfs_client.pubsub_unsubscribe(response_topic)
    
    def _get_peer_partitions_via_dag(self, peer_id: str) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Alternative implementation to get partition metadata using IPFS DAG.
        
        Args:
            peer_id: ID of the peer
            
        Returns:
            Dictionary mapping partition IDs to metadata or None
        """
        if not self.ipfs_client or not hasattr(self.ipfs_client, 'dag_get'):
            return None
            
        try:
            # Try to get the peer's metadata index DAG node
            # The path would follow a convention like /ipns/<peer_id>/metadata_index/partitions
            path = f"/ipns/{peer_id}/metadata_index/partitions"
            
            # Try to resolve this path
            result = self.ipfs_client.dag_get(path)
            
            if result and result.get("success", False):
                return result.get("value", {})
            else:
                self.logger.warning(f"Failed to get DAG node from peer {peer_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting DAG node from peer {peer_id}: {e}")
            return None
    
    def _download_partition(self, peer_id: str, partition_id: int, 
                           metadata: Dict[str, Any]) -> bool:
        """
        Download a partition from a peer.
        
        Args:
            peer_id: ID of the peer
            partition_id: ID of the partition
            metadata: Metadata about the partition
            
        Returns:
            True if successful, False otherwise
        """
        if not self.ipfs_client:
            self.logger.warning("No IPFS client available for peer communication")
            return False
            
        try:
            # First check if metadata has a CID for the partition
            partition_cid = metadata.get("cid")
            
            if partition_cid:
                # Direct download via IPFS using the CID
                return self._download_partition_by_cid(partition_cid, partition_id)
            else:
                # Request the partition using pubsub
                return self._download_partition_via_pubsub(peer_id, partition_id)
                
        except Exception as e:
            self.logger.error(f"Error downloading partition {partition_id} from peer {peer_id}: {e}")
            return False
            
    def _download_partition_by_cid(self, cid: str, partition_id: int) -> bool:
        """
        Download a partition using its CID.
        
        Args:
            cid: Content identifier of the partition
            partition_id: ID to save the partition as
            
        Returns:
            True if successful, False otherwise
        """
        if not self.ipfs_client or not hasattr(self.ipfs_client, 'cat'):
            return False
            
        try:
            # Get the destination path for the partition
            partition_path = self._get_partition_path(partition_id)
            
            # Download partition data
            result = self.ipfs_client.cat(cid)
            
            if not result or not result.get("success", False):
                self.logger.warning(f"Failed to download partition {partition_id} with CID {cid}")
                return False
                
            # Write the data to the partition file
            with open(partition_path, 'wb') as f:
                f.write(result.get("data", b""))
                
            # Verify the file by trying to read it as a parquet file
            try:
                pq.read_metadata(partition_path)
                
                # Update partition metadata
                self.partitions[partition_id] = {
                    'path': partition_path,
                    'size': os.path.getsize(partition_path),
                    'mtime': os.path.getmtime(partition_path),
                    'rows': None  # Will be loaded when needed
                }
                
                self.logger.info(f"Successfully downloaded partition {partition_id} from CID {cid}")
                return True
                
            except Exception as e:
                self.logger.error(f"Downloaded file is not a valid parquet file: {e}")
                # Delete the invalid file
                if os.path.exists(partition_path):
                    os.remove(partition_path)
                return False
                
        except Exception as e:
            self.logger.error(f"Error downloading partition by CID: {e}")
            return False
            
    def _download_partition_via_pubsub(self, peer_id: str, partition_id: int) -> bool:
        """
        Download a partition using pubsub communication.
        
        Args:
            peer_id: ID of the peer
            partition_id: ID of the partition
            
        Returns:
            True if successful, False otherwise
        """
        if not self.ipfs_client:
            return False
            
        try:
            # Create topic for partition request
            topic = f"ipfs-kit/metadata-index/{self.cluster_id}/partition-data"
            
            # Create a request message
            message = {
                "type": "partition_data_request",
                "requester": self.node_id,
                "partition_id": partition_id,
                "timestamp": time.time(),
                "request_id": str(uuid.uuid4())
            }
            
            # Create event and data storage for response handling
            response_event = threading.Event()
            response_data = {"chunks": [], "total_chunks": 0, "chunk_count": 0}
            
            # Create a callback to handle the response
            def handle_partition_data(msg):
                try:
                    msg_data = json.loads(msg.get("data", "{}"))
                    
                    if (msg_data.get("type") == "partition_data_response" and 
                        msg_data.get("request_id") == message["request_id"]):
                        
                        chunk = msg_data.get("chunk")
                        chunk_index = msg_data.get("chunk_index")
                        total_chunks = msg_data.get("total_chunks")
                        
                        if chunk is None or chunk_index is None or total_chunks is None:
                            self.logger.warning("Received invalid partition data response")
                            return
                            
                        # Initialize chunk storage if needed
                        if response_data["total_chunks"] == 0:
                            response_data["total_chunks"] = total_chunks
                            response_data["chunks"] = [None] * total_chunks
                            
                        # Store the chunk
                        try:
                            # Decode chunk from base64
                            import base64
                            binary_chunk = base64.b64decode(chunk)
                            response_data["chunks"][chunk_index] = binary_chunk
                            response_data["chunk_count"] += 1
                            
                            # Check if we have all chunks
                            if response_data["chunk_count"] == response_data["total_chunks"]:
                                response_event.set()
                                
                        except Exception as e:
                            self.logger.error(f"Error processing partition data chunk: {e}")
                            
                except Exception as e:
                    self.logger.error(f"Error handling partition data response: {e}")
            
            # Subscribe to response topic
            response_topic = f"{topic}/responses/{self.node_id}"
            if hasattr(self.ipfs_client, 'pubsub_subscribe'):
                self.ipfs_client.pubsub_subscribe(response_topic, handle_partition_data)
                
                # Publish request
                if hasattr(self.ipfs_client, 'pubsub_publish'):
                    self.ipfs_client.pubsub_publish(topic, json.dumps(message))
                    
                    # Wait for all chunks with timeout
                    if response_event.wait(timeout=120):  # Longer timeout for large partitions
                        # Combine all chunks
                        partition_data = b"".join(response_data["chunks"])
                        
                        # Write to file
                        partition_path = self._get_partition_path(partition_id)
                        with open(partition_path, 'wb') as f:
                            f.write(partition_data)
                            
                        # Verify the file
                        try:
                            pq.read_metadata(partition_path)
                            
                            # Update partition metadata
                            self.partitions[partition_id] = {
                                'path': partition_path,
                                'size': os.path.getsize(partition_path),
                                'mtime': os.path.getmtime(partition_path),
                                'rows': None  # Will be loaded when needed
                            }
                            
                            self.logger.info(f"Successfully downloaded partition {partition_id} from peer {peer_id}")
                            return True
                            
                        except Exception as e:
                            self.logger.error(f"Downloaded file is not a valid parquet file: {e}")
                            # Delete the invalid file
                            if os.path.exists(partition_path):
                                os.remove(partition_path)
                            return False
                    else:
                        self.logger.warning(f"Timeout waiting for partition data from peer {peer_id}")
                        return False
                else:
                    self.logger.warning("IPFS client doesn't support pubsub_publish")
                    return False
            else:
                self.logger.warning("IPFS client doesn't support pubsub_subscribe")
                return False
                
        except Exception as e:
            self.logger.error(f"Error downloading partition via pubsub: {e}")
            return False
        finally:
            # Unsubscribe from response topic
            if hasattr(self.ipfs_client, 'pubsub_unsubscribe'):
                self.ipfs_client.pubsub_unsubscribe(response_topic)
                
    def handle_partition_request(self, request_data: Dict[str, Any]):
        """
        Handle a request for partition metadata.
        
        This method should be called when a partition request message is received.
        
        Args:
            request_data: Request data including requester ID
        """
        if not self.ipfs_client:
            return
            
        try:
            requester = request_data.get("requester")
            request_id = request_data.get("request_id")
            
            if not requester or not request_id:
                return
                
            # Create response with our partition metadata
            response = {
                "type": "partition_response",
                "responder": self.node_id,
                "request_id": request_id,
                "timestamp": time.time(),
                "partitions": {}
            }
            
            # Add partition metadata
            for partition_id, metadata in self.partitions.items():
                # Convert partition ID to string for JSON
                response["partitions"][str(partition_id)] = {
                    "mtime": metadata["mtime"],
                    "size": metadata["size"],
                    "rows": metadata.get("rows"),
                    # Add CID if available
                    "cid": self._get_partition_cid(partition_id)
                }
                
            # Send response
            response_topic = f"ipfs-kit/metadata-index/{self.cluster_id}/partitions/responses"
            if hasattr(self.ipfs_client, 'pubsub_publish'):
                self.ipfs_client.pubsub_publish(response_topic, json.dumps(response))
                
        except Exception as e:
            self.logger.error(f"Error handling partition request: {e}")
            
    def _get_partition_cid(self, partition_id: int) -> Optional[str]:
        """
        Get the CID for a partition if it's available.
        
        Args:
            partition_id: ID of the partition
            
        Returns:
            CID string or None if not available
        """
        if not self.ipfs_client or not hasattr(self.ipfs_client, 'add_file'):
            return None
            
        partition_path = self._get_partition_path(partition_id)
        if not os.path.exists(partition_path):
            return None
            
        try:
            # Try to get from cache first
            if hasattr(self, '_partition_cids') and partition_id in self._partition_cids:
                return self._partition_cids[partition_id]
                
            # Add the file to IPFS
            result = self.ipfs_client.add_file(partition_path)
            
            if result and result.get("success", False):
                cid = result.get("cid") or result.get("Hash")
                
                # Cache the CID
                if not hasattr(self, '_partition_cids'):
                    self._partition_cids = {}
                self._partition_cids[partition_id] = cid
                
                return cid
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting CID for partition {partition_id}: {e}")
            return None
            
    def handle_partition_data_request(self, request_data: Dict[str, Any]):
        """
        Handle a request for partition data.
        
        This method should be called when a partition data request message is received.
        
        Args:
            request_data: Request data including requester ID and partition ID
        """
        if not self.ipfs_client:
            return
            
        try:
            requester = request_data.get("requester")
            partition_id = request_data.get("partition_id")
            request_id = request_data.get("request_id")
            
            if not requester or partition_id is None or not request_id:
                return
                
            # Convert partition_id to int if it's a string
            if isinstance(partition_id, str):
                try:
                    partition_id = int(partition_id)
                except ValueError:
                    self.logger.warning(f"Invalid partition ID: {partition_id}")
                    return
                    
            # Check if we have this partition
            partition_path = self._get_partition_path(partition_id)
            if not os.path.exists(partition_path):
                self.logger.warning(f"Partition {partition_id} not found")
                return
                
            # Read the partition file
            with open(partition_path, 'rb') as f:
                data = f.read()
                
            # Break into chunks for pubsub (max message size)
            chunk_size = 1024 * 512  # 512KB chunks
            chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
            total_chunks = len(chunks)
            
            # Send each chunk
            response_topic = f"ipfs-kit/metadata-index/{self.cluster_id}/partition-data/responses/{requester}"
            
            for i, chunk in enumerate(chunks):
                # Create response message
                response = {
                    "type": "partition_data_response",
                    "responder": self.node_id,
                    "request_id": request_id,
                    "partition_id": partition_id,
                    "chunk_index": i,
                    "total_chunks": total_chunks,
                    "timestamp": time.time(),
                    # Encode binary chunk as base64
                    "chunk": base64.b64encode(chunk).decode('utf-8')
                }
                
                # Send response
                if hasattr(self.ipfs_client, 'pubsub_publish'):
                    self.ipfs_client.pubsub_publish(response_topic, json.dumps(response))
                    
                    # Small delay between chunks to avoid flooding
                    time.sleep(0.1)
                    
            self.logger.info(f"Sent partition {partition_id} data to {requester} in {total_chunks} chunks")
                
        except Exception as e:
            self.logger.error(f"Error handling partition data request: {e}")
            
    def publish_index_dag(self):
        """
        Publish the metadata index to IPFS DAG for discoverable access.
        
        This creates a DAG node with information about available partitions
        and publishes it to IPNS for discovery by other peers.
        
        Returns:
            Dictionary with operation result
        """
        if not self.ipfs_client or not hasattr(self.ipfs_client, 'dag_put'):
            return {"success": False, "error": "IPFS client doesn't support DAG operations"}
            
        try:
            # Create DAG node with partition information
            dag_node = {
                "type": "metadata_index",
                "node_id": self.node_id,
                "timestamp": time.time(),
                "partitions": {}
            }
            
            # Add partition metadata
            for partition_id, metadata in self.partitions.items():
                # Get CID for partition
                cid = self._get_partition_cid(partition_id)
                
                if cid:
                    dag_node["partitions"][str(partition_id)] = {
                        "cid": cid,
                        "mtime": metadata["mtime"],
                        "size": metadata["size"],
                        "rows": metadata.get("rows")
                    }
                    
            # Put DAG node
            result = self.ipfs_client.dag_put(dag_node)
            
            if not result or not result.get("success", False):
                return {"success": False, "error": "Failed to publish DAG node"}
                
            dag_cid = result.get("cid")
            
            # Publish to IPNS
            ipns_result = self.ipfs_client.name_publish(dag_cid, key="metadata_index")
            
            if not ipns_result or not ipns_result.get("success", False):
                return {
                    "success": False, 
                    "error": "Failed to publish to IPNS",
                    "dag_cid": dag_cid
                }
                
            ipns_name = ipns_result.get("name")
            
            return {
                "success": True,
                "dag_cid": dag_cid,
                "ipns_name": ipns_name
            }
            
        except Exception as e:
            self.logger.error(f"Error publishing index DAG: {e}")
            return {"success": False, "error": str(e)}
    
    def close(self) -> None:
        """
        Close the metadata index and clean up resources.
        """
        try:
            # Stop the sync thread
            if self.sync_thread and self.sync_thread.is_alive():
                self.should_stop.set()
                self.sync_thread.join(timeout=5)
            
            # Write any pending changes
            if self.record_batch is not None and self.record_batch.num_rows > 0:
                self._write_current_batch()
                
            # Close memory-mapped files
            for path, (file_obj, mmap_obj) in list(self.mmap_files.items()):
                try:
                    mmap_obj.close()
                    file_obj.close()
                except Exception as e:
                    self.logger.warning(f"Error closing memory-mapped file {path}: {e}")
                    
            self.mmap_files = {}
            
            # Close plasma client if any
            if self.plasma_client:
                try:
                    self.plasma_client.disconnect()
                    self.plasma_client = None
                except Exception as e:
                    self.logger.warning(f"Error disconnecting from plasma store: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error closing metadata index: {e}")
    
    def __del__(self) -> None:
        """
        Clean up resources when the object is deleted.
        """
        self.close()
    
    @staticmethod
    def access_via_c_data_interface(index_dir: str = "~/.ipfs_metadata") -> Dict[str, Any]:
        """
        Access the metadata index from another process via Arrow C Data Interface.
        
        Args:
            index_dir: Directory where the index is stored
            
        Returns:
            Dict with access information and the Arrow table
        """
        result = {
            "success": False,
            "operation": "access_via_c_data_interface",
            "timestamp": time.time()
        }
        
        try:
            if not ARROW_AVAILABLE:
                result["error"] = "PyArrow is not available"
                return result
                
            if not PLASMA_AVAILABLE:
                result["error"] = "PyArrow Plasma is not available"
                return result
                
            # Expand index directory path
            index_dir = os.path.expanduser(index_dir)
            
            # Find C Data Interface metadata file
            cdi_path = os.path.join(index_dir, 'c_data_interface.json')
            if not os.path.exists(cdi_path):
                result["error"] = f"C Data Interface metadata not found at {cdi_path}"
                return result
                
            # Load metadata
            with open(cdi_path, 'r') as f:
                cdi_metadata = json.load(f)
                
            # Connect to plasma store
            plasma_socket = cdi_metadata.get('plasma_socket')
            if not plasma_socket or not os.path.exists(plasma_socket):
                result["error"] = f"Plasma socket not found at {plasma_socket}"
                return result
                
            # Connect to plasma
            plasma_client = plasma.connect(plasma_socket)
            
            # Get object ID
            object_id_hex = cdi_metadata.get('object_id')
            if not object_id_hex:
                result["error"] = "Object ID not found in metadata"
                plasma_client.disconnect()
                return result
                
            # Convert hex to binary object ID
            object_id = plasma.ObjectID(bytes.fromhex(object_id_hex))
            
            # Check if object exists
            if not plasma_client.contains(object_id):
                result["error"] = f"Object {object_id_hex} not found in plasma store"
                plasma_client.disconnect()
                return result
                
            # Get the object
            buffer = plasma_client.get_buffers([object_id])[object_id]
            reader = pa.RecordBatchStreamReader(buffer)
            table = reader.read_all()
            
            # Success
            result["success"] = True
            result["table"] = table
            result["num_rows"] = table.num_rows
            result["schema"] = table.schema
            result["plasma_client"] = plasma_client  # Keep reference for cleanup
            
            return result
            
        except Exception as e:
            if "plasma_client" in result:
                try:
                    result["plasma_client"].disconnect()
                except:
                    pass
                    
            result["error"] = str(e)
            return result


def create_metadata_from_ipfs_file(ipfs_client, cid: str, 
                                  include_content: bool = False) -> Dict[str, Any]:
    """
    Create metadata record from an IPFS file.
    
    Args:
        ipfs_client: IPFS client instance
        cid: Content identifier
        include_content: Whether to include file content in metadata
        
    Returns:
        Metadata record for the file
    """
    metadata = {
        "cid": cid,
        "indexed_at": pa.scalar(int(time.time() * 1000)).cast(pa.timestamp('ms')),
        "access_count": 0
    }
    
    try:
        # Get file info
        if hasattr(ipfs_client, 'ipfs_object_stat'):
            stat_result = ipfs_client.ipfs_object_stat(cid)
            
            if stat_result and stat_result.get("success", False):
                stats = stat_result.get("Stats", {})
                
                metadata["cid_version"] = 0  # Assume CIDv0 for now
                metadata["size_bytes"] = stats.get("CumulativeSize", 0)
                metadata["blocks"] = stats.get("NumBlocks", 0)
                metadata["links"] = stats.get("NumLinks", 0)
                
        # Get file details
        if hasattr(ipfs_client, 'ipfs_ls'):
            ls_result = ipfs_client.ipfs_ls(cid)
            
            if ls_result and ls_result.get("success", False):
                objects = ls_result.get("Objects", [])
                
                if objects and len(objects) > 0:
                    obj = objects[0]
                    
                    if "Links" in obj and len(obj["Links"]) > 0:
                        # It's a directory
                        metadata["mime_type"] = "application/x-directory"
                    else:
                        # Try to determine mime type
                        if hasattr(ipfs_client, 'ipfs_cat') and include_content:
                            # Get file content
                            cat_result = ipfs_client.ipfs_cat(cid)
                            
                            if cat_result and cat_result.get("success", False):
                                content = cat_result.get("data", b"")
                                
                                # Determine mime type
                                import magic
                                try:
                                    metadata["mime_type"] = magic.from_buffer(content, mime=True)
                                except:
                                    # Fallback mime type determination
                                    if content.startswith(b"%PDF"):
                                        metadata["mime_type"] = "application/pdf"
                                    elif content.startswith(b"\x89PNG"):
                                        metadata["mime_type"] = "image/png"
                                    elif content.startswith(b"\xff\xd8"):
                                        metadata["mime_type"] = "image/jpeg"
                                    elif content.startswith(b"GIF"):
                                        metadata["mime_type"] = "image/gif"
                                    elif content.startswith(b"<!DOCTYPE html") or content.startswith(b"<html"):
                                        metadata["mime_type"] = "text/html"
                                    elif content.startswith(b"{") or content.startswith(b"["):
                                        # Check if it's JSON
                                        try:
                                            json.loads(content)
                                            metadata["mime_type"] = "application/json"
                                        except:
                                            metadata["mime_type"] = "text/plain"
                                    else:
                                        metadata["mime_type"] = "application/octet-stream"
        
        # Get pin status
        if hasattr(ipfs_client, 'ipfs_pin_ls'):
            pin_result = ipfs_client.ipfs_pin_ls(cid)
            
            if pin_result and pin_result.get("success", False):
                keys = pin_result.get("Keys", {})
                
                if cid in keys:
                    metadata["pinned"] = True
                    metadata["pin_types"] = [keys[cid]["Type"]]
                else:
                    metadata["pinned"] = False
                    metadata["pin_types"] = []
        
        # Local status
        metadata["local"] = True
        
        # Set creation time if not set
        if "created_at" not in metadata:
            metadata["created_at"] = metadata["indexed_at"]
        
        # Set last access time if not set
        if "last_accessed" not in metadata:
            metadata["last_accessed"] = metadata["indexed_at"]
            
    except Exception as e:
        # Log the error but continue with partial metadata
        logger.error(f"Error creating metadata for CID {cid}: {e}")
        
    return metadata
