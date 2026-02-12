"""
Zero-copy access interface for ParquetCIDCache using Arrow C Data Interface.

This module implements efficient cross-process data sharing capabilities
for the ParquetCIDCache using Apache Arrow's C Data Interface and shared
memory, enabling zero-copy access to cache data from multiple processes.
"""

from __future__ import annotations

import logging
import os
import time
import tempfile
import uuid
import json
import socket
from typing import Dict, List, Optional, Any, Union, Tuple

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False

try:
    import pyarrow.plasma as plasma
    HAS_PLASMA = True
except ImportError:
    HAS_PLASMA = False

# Initialize logger
logger = logging.getLogger(__name__)

class ZeroCopyManager:
    """Manager for zero-copy data sharing using Arrow C Data Interface.
    
    This class provides efficient cross-process data sharing for Arrow tables
    in the ParquetCIDCache through the Arrow C Data Interface and the Plasma
    shared memory store.
    
    Features:
    - Zero-copy shared memory access to cache data
    - Cross-language compatibility via Arrow C Data Interface
    - Efficient handling of large datasets
    - Automatic resource cleanup and reference counting
    - Support for partial table sharing
    """
    
    def __init__(self, 
                 shared_memory_path: Optional[str] = None,
                 memory_limit_bytes: int = 1000 * 1024 * 1024,  # 1GB default
                 metadata_path: Optional[str] = None,
                 plasma_socket_suffix: str = "",
                 auto_cleanup: bool = True,
                 enable_mmap_fallback: bool = True):
        """Initialize the zero-copy manager.
        
        Args:
            shared_memory_path: Path for shared memory storage (default: auto-created)
            memory_limit_bytes: Maximum shared memory size in bytes
            metadata_path: Path to store C Data Interface metadata
            plasma_socket_suffix: Suffix to add to socket name for isolation
            auto_cleanup: Whether to automatically clean up unused memory
            enable_mmap_fallback: Whether to use mmap as fallback when Plasma is unavailable
        """
        if not HAS_PYARROW:
            raise ImportError("PyArrow is required for ZeroCopyManager")
        
        self.has_plasma = HAS_PLASMA
        self.enable_mmap_fallback = enable_mmap_fallback
        self.auto_cleanup = auto_cleanup
        self.plasma_socket_suffix = plasma_socket_suffix
        
        # Set up shared memory path
        if shared_memory_path:
            self.shared_memory_path = os.path.expanduser(shared_memory_path)
        else:
            # Auto-create in a standard location
            self.shared_memory_path = os.path.join(
                tempfile.gettempdir(), 
                f"ipfs_kit_plasma_{os.getpid()}_{plasma_socket_suffix}"
            )
        
        # Set up metadata path
        if metadata_path:
            self.metadata_path = os.path.expanduser(metadata_path)
        else:
            self.metadata_path = os.path.join(
                tempfile.gettempdir(),
                f"ipfs_kit_c_data_interface_{os.getpid()}_{plasma_socket_suffix}"
            )
        
        # Create directories
        os.makedirs(os.path.dirname(self.shared_memory_path), exist_ok=True)
        os.makedirs(self.metadata_path, exist_ok=True)
        
        # Memory limit
        self.memory_limit_bytes = memory_limit_bytes
        
        # Track shared objects
        self.shared_objects = {}
        self.reference_counts = {}
        self.metadata_registry = {}
        
        # Initialize Plasma store if available
        self.plasma_client = None
        self.plasma_server_pid = None
        
        if self.has_plasma:
            self._initialize_plasma_store()
        elif not self.enable_mmap_fallback:
            raise ImportError("PyArrow Plasma is required unless mmap fallback is enabled")
        else:
            logger.warning("PyArrow Plasma not available, using mmap fallback for zero-copy access")
            
        # Register cleanup handler
        if self.auto_cleanup:
            import atexit
            atexit.register(self.cleanup)
    
    def _initialize_plasma_store(self):
        """Initialize the Plasma store for shared memory.
        
        This starts a Plasma store process if needed and connects to it.
        """
        try:
            # Check if store is already running
            if os.path.exists(self.shared_memory_path):
                # Try connecting to existing store
                try:
                    self.plasma_client = plasma.connect(self.shared_memory_path)
                    logger.info(f"Connected to existing Plasma store at {self.shared_memory_path}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to connect to existing Plasma store: {e}")
                    # Clean up stale socket
                    try:
                        os.unlink(self.shared_memory_path)
                    except Exception:
                        pass
            
            # Start a new Plasma store
            from subprocess import Popen
            import psutil  # For memory detection
            
            # Determine system memory for safe allocation
            system_memory = psutil.virtual_memory().total
            plasma_memory = min(self.memory_limit_bytes, system_memory // 4)  # Use at most 25% of system memory
            
            # Start Plasma store process
            cmd = [
                "plasma_store",
                "-m", str(plasma_memory),
                "-s", self.shared_memory_path
            ]
            
            plasma_process = Popen(cmd)
            self.plasma_server_pid = plasma_process.pid
            
            # Wait for store to initialize
            time.sleep(0.1)
            
            # Connect to store
            max_retries = 5
            for i in range(max_retries):
                try:
                    self.plasma_client = plasma.connect(self.shared_memory_path)
                    logger.info(f"Started Plasma store at {self.shared_memory_path} with {plasma_memory} bytes")
                    break
                except Exception as e:
                    if i == max_retries - 1:
                        raise Exception(f"Failed to connect to Plasma store after {max_retries} retries: {e}")
                    time.sleep(0.5)
                    
        except Exception as e:
            logger.error(f"Failed to initialize Plasma store: {e}")
            self.has_plasma = False
            
            if not self.enable_mmap_fallback:
                raise
    
    def share_table(self, 
                    table: pa.Table, 
                    name: Optional[str] = None, 
                    description: Optional[str] = None,
                    ttl_seconds: Optional[int] = None) -> Dict[str, Any]:
        """Share an Arrow table via C Data Interface.
        
        Args:
            table: The Arrow table to share
            name: Optional name for the shared table
            description: Optional description of the table
            ttl_seconds: Optional time-to-live in seconds
            
        Returns:
            Dictionary with C Data Interface metadata
        """
        if not name:
            name = f"table_{uuid.uuid4().hex[:8]}"
            
        # Create metadata
        metadata = {
            "name": name,
            "description": description or f"Shared Arrow table: {name}",
            "schema": table.schema.to_string(),
            "num_rows": table.num_rows,
            "num_columns": table.num_columns,
            "column_names": table.column_names,
            "created_timestamp": time.time(),
            "expires_timestamp": time.time() + ttl_seconds if ttl_seconds else None,
            "created_by_pid": os.getpid(),
            "hostname": socket.gethostname(),
            "object_id": None,  # Will be filled in
            "plasma_socket": self.shared_memory_path if self.has_plasma else None,
            "fallback_path": None,  # Will be filled in if using mmap fallback
            "serialization_format": "arrow"
        }
        
        # Share via Plasma if available
        if self.has_plasma:
            try:
                # Convert table to record batches for serialization
                batches = table.to_batches()
                
                # Generate object ID
                object_id = plasma.ObjectID(uuid.uuid4().bytes[:20])
                
                # Create object in Plasma
                # Calculate size needed
                data_size = sum(batch.nbytes for batch in batches)
                data_size += 1024  # Add some padding for metadata
                
                # Allocate buffer
                buffer = self.plasma_client.create(object_id, data_size)
                
                # Write batches to buffer
                writer = pa.RecordBatchStreamWriter(pa.FixedSizeBufferWriter(buffer), table.schema)
                for batch in batches:
                    writer.write_batch(batch)
                writer.close()
                
                # Seal the object
                self.plasma_client.seal(object_id)
                
                # Update metadata
                metadata["object_id"] = object_id.binary().hex()
                metadata["access_method"] = "plasma"
                
                # Store reference
                self.shared_objects[name] = {
                    "object_id": object_id,
                    "metadata": metadata,
                    "created": time.time()
                }
                self.reference_counts[name] = 1
                
            except Exception as e:
                logger.error(f"Error sharing table via Plasma: {e}")
                
                if not self.enable_mmap_fallback:
                    raise
                    
                # Fall back to mmap if enabled
                logger.info("Falling back to mmap for sharing table")
                return self._share_table_mmap(table, name, metadata)
        else:
            # Use mmap fallback
            return self._share_table_mmap(table, name, metadata)
        
        # Save metadata to registry
        self.metadata_registry[name] = metadata
        
        # Write metadata to file
        metadata_path = os.path.join(self.metadata_path, f"{name}.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
            
        return metadata
    
    def _share_table_mmap(self, 
                          table: pa.Table, 
                          name: str, 
                          metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Share an Arrow table via memory-mapped file fallback.
        
        Args:
            table: The Arrow table to share
            name: Name for the shared table
            metadata: Metadata dictionary to update
            
        Returns:
            Updated metadata dictionary
        """
        # Create temporary parquet file
        fallback_path = os.path.join(self.metadata_path, f"{name}.parquet")
        
        # Write table to parquet with memory-map friendly settings
        pq.write_table(
            table, 
            fallback_path, 
            compression='snappy',  # Fast decompression
            write_statistics=True,
            use_dictionary=True,
            version='2.0'  # More compatible
        )
        
        # Update metadata
        metadata["fallback_path"] = fallback_path
        metadata["access_method"] = "mmap"
        
        # Store reference
        self.shared_objects[name] = {
            "fallback_path": fallback_path,
            "metadata": metadata,
            "created": time.time()
        }
        self.reference_counts[name] = 1
        
        # Save metadata to registry
        self.metadata_registry[name] = metadata
        
        # Write metadata to file
        metadata_path = os.path.join(self.metadata_path, f"{name}.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
            
        return metadata
    
    def get_shared_table(self, name_or_metadata: Union[str, Dict[str, Any]]) -> Optional[pa.Table]:
        """Get a shared Arrow table.
        
        Args:
            name_or_metadata: Name of the shared table or metadata dictionary
            
        Returns:
            The shared Arrow table or None if not found
        """
        # Extract metadata
        if isinstance(name_or_metadata, str):
            name = name_or_metadata
            # Check local registry first
            if name in self.metadata_registry:
                metadata = self.metadata_registry[name]
            else:
                # Try to load from file
                metadata_path = os.path.join(self.metadata_path, f"{name}.json")
                if not os.path.exists(metadata_path):
                    return None
                    
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
        else:
            metadata = name_or_metadata
            name = metadata.get("name", "unknown")
            
        # Check if expired
        expires = metadata.get("expires_timestamp")
        if expires and time.time() > expires:
            logger.warning(f"Shared table {name} has expired")
            return None
            
        # Get table based on access method
        access_method = metadata.get("access_method")
        
        if access_method == "plasma":
            # Access via Plasma
            if not self.has_plasma:
                logger.error("Cannot access Plasma shared table without Plasma support")
                return None
                
            try:
                # Convert hex to binary object ID
                object_id_hex = metadata.get("object_id")
                if not object_id_hex:
                    logger.error(f"Missing object_id in metadata for {name}")
                    return None
                    
                object_id = plasma.ObjectID(bytes.fromhex(object_id_hex))
                
                # Get from plasma store
                if self.plasma_client.contains(object_id):
                    # Get the object
                    buffer = self.plasma_client.get_buffers([object_id])[object_id]
                    
                    # Read table from buffer
                    reader = pa.RecordBatchStreamReader(buffer)
                    table = reader.read_all()
                    
                    # Update reference count
                    if name in self.reference_counts:
                        self.reference_counts[name] += 1
                        
                    return table
                else:
                    logger.warning(f"Object {object_id_hex} not found in Plasma store")
                    return None
                    
            except Exception as e:
                logger.error(f"Error accessing shared table via Plasma: {e}")
                return None
                
        elif access_method == "mmap":
            # Access via memory-mapped file
            fallback_path = metadata.get("fallback_path")
            if not fallback_path or not os.path.exists(fallback_path):
                logger.error(f"Missing or invalid fallback_path in metadata for {name}")
                return None
                
            try:
                # Read parquet file with memory mapping
                table = pq.read_table(fallback_path, memory_map=True)
                
                # Update reference count
                if name in self.reference_counts:
                    self.reference_counts[name] += 1
                    
                return table
                
            except Exception as e:
                logger.error(f"Error accessing shared table via mmap: {e}")
                return None
                
        else:
            logger.error(f"Unknown access method: {access_method}")
            return None
    
    def list_shared_tables(self) -> List[Dict[str, Any]]:
        """List all shared tables.
        
        Returns:
            List of metadata dictionaries for all shared tables
        """
        # Start with locally known tables
        tables = list(self.metadata_registry.values())
        
        # Scan metadata directory for additional tables
        for filename in os.listdir(self.metadata_path):
            if filename.endswith('.json'):
                table_name = filename[:-5]  # Remove .json
                
                # Skip already known tables
                if table_name in self.metadata_registry:
                    continue
                    
                # Load metadata
                try:
                    with open(os.path.join(self.metadata_path, filename), 'r') as f:
                        metadata = json.load(f)
                        tables.append(metadata)
                except Exception as e:
                    logger.warning(f"Error loading metadata for {filename}: {e}")
                    
        return tables
    
    def unshare_table(self, name: str) -> bool:
        """Unshare a previously shared table.
        
        Args:
            name: Name of the shared table
            
        Returns:
            True if successfully unshared, False otherwise
        """
        # Check if table exists
        if name not in self.shared_objects:
            logger.warning(f"Table {name} not found in shared objects")
            return False
            
        # Get shared object info
        shared_obj = self.shared_objects[name]
        
        # Decrement reference count
        if name in self.reference_counts:
            self.reference_counts[name] -= 1
            
            # If still in use, don't unshare yet
            if self.reference_counts[name] > 0:
                logger.info(f"Table {name} still has {self.reference_counts[name]} references, not unsharing yet")
                return True
                
        # Unshare based on access method
        try:
            if "object_id" in shared_obj:
                # Plasma object
                if self.has_plasma and self.plasma_client:
                    # Cannot explicitly delete from Plasma, but we can remove our reference
                    pass
                    
            if "fallback_path" in shared_obj:
                # Memory-mapped file
                fallback_path = shared_obj["fallback_path"]
                if os.path.exists(fallback_path):
                    try:
                        os.remove(fallback_path)
                    except Exception as e:
                        logger.warning(f"Failed to remove fallback file {fallback_path}: {e}")
            
            # Remove from registry
            if name in self.metadata_registry:
                del self.metadata_registry[name]
                
            # Remove metadata file
            metadata_path = os.path.join(self.metadata_path, f"{name}.json")
            if os.path.exists(metadata_path):
                try:
                    os.remove(metadata_path)
                except Exception as e:
                    logger.warning(f"Failed to remove metadata file {metadata_path}: {e}")
            
            # Remove from shared objects
            del self.shared_objects[name]
            if name in self.reference_counts:
                del self.reference_counts[name]
                
            return True
            
        except Exception as e:
            logger.error(f"Error unsharing table {name}: {e}")
            return False
    
    def get_c_data_interface_handle(self, name: str) -> Optional[Dict[str, Any]]:
        """Get C Data Interface handle for a shared table.
        
        This provides the necessary information for other processes or
        languages to access the shared table via the Arrow C Data Interface.
        
        Args:
            name: Name of the shared table
            
        Returns:
            Dictionary with C Data Interface access information
        """
        # Check if table exists
        if name not in self.metadata_registry:
            logger.warning(f"Table {name} not found in metadata registry")
            return None
            
        metadata = self.metadata_registry[name]
        
        # Create C Data Interface handle
        handle = {
            "name": name,
            "schema_json": metadata.get("schema"),
            "num_rows": metadata.get("num_rows"),
            "column_names": metadata.get("column_names"),
            "timestamp": time.time()
        }
        
        # Add access method specific info
        access_method = metadata.get("access_method")
        if access_method == "plasma":
            handle["object_id"] = metadata.get("object_id")
            handle["plasma_socket"] = metadata.get("plasma_socket")
            handle["access_method"] = "plasma"
        elif access_method == "mmap":
            handle["fallback_path"] = metadata.get("fallback_path")
            handle["access_method"] = "mmap"
        
        return handle
    
    @staticmethod
    def access_via_c_data_interface(handle: Dict[str, Any]) -> Optional[pa.Table]:
        """Access a shared table via C Data Interface from any process.
        
        This static method can be used from any process to access a shared table
        using the handle provided by get_c_data_interface_handle().
        
        Args:
            handle: C Data Interface handle
            
        Returns:
            The shared Arrow table or None if access failed
        """
        if not HAS_PYARROW:
            logger.error("PyArrow is required for C Data Interface access")
            return None
            
        access_method = handle.get("access_method")
        
        if access_method == "plasma":
            # Access via Plasma
            if not HAS_PLASMA:
                logger.error("PyArrow Plasma is required for C Data Interface access via Plasma")
                return None
                
            try:
                # Get plasma socket
                plasma_socket = handle.get("plasma_socket")
                if not plasma_socket or not os.path.exists(plasma_socket):
                    logger.error(f"Invalid plasma socket: {plasma_socket}")
                    return None
                    
                # Get object ID
                object_id_hex = handle.get("object_id")
                if not object_id_hex:
                    logger.error("Missing object_id in handle")
                    return None
                    
                # Connect to plasma store
                plasma_client = plasma.connect(plasma_socket)
                
                # Get object
                object_id = plasma.ObjectID(bytes.fromhex(object_id_hex))
                if not plasma_client.contains(object_id):
                    logger.error(f"Object {object_id_hex} not found in Plasma store")
                    return None
                    
                # Get buffer and read table
                buffer = plasma_client.get_buffers([object_id])[object_id]
                reader = pa.RecordBatchStreamReader(buffer)
                table = reader.read_all()
                
                return table
                
            except Exception as e:
                logger.error(f"Error accessing shared table via Plasma: {e}")
                return None
                
        elif access_method == "mmap":
            # Access via memory-mapped file
            try:
                fallback_path = handle.get("fallback_path")
                if not fallback_path or not os.path.exists(fallback_path):
                    logger.error(f"Invalid fallback path: {fallback_path}")
                    return None
                    
                # Read parquet file with memory mapping
                table = pq.read_table(fallback_path, memory_map=True)
                return table
                
            except Exception as e:
                logger.error(f"Error accessing shared table via mmap: {e}")
                return None
                
        else:
            logger.error(f"Unknown access method: {access_method}")
            return None
    
    def cleanup(self):
        """Clean up resources used by the zero-copy manager."""
        # Unshare all tables
        for name in list(self.shared_objects.keys()):
            self.unshare_table(name)
            
        # Disconnect from Plasma
        if self.has_plasma and self.plasma_client:
            try:
                # No explicit close method, but we can delete the reference
                self.plasma_client = None
            except Exception:
                pass
            
        # Clean up Plasma store process if we started it
        if self.plasma_server_pid:
            try:
                import os
                import signal
                os.kill(self.plasma_server_pid, signal.SIGTERM)
                logger.info(f"Terminated Plasma store process (PID: {self.plasma_server_pid})")
            except Exception as e:
                logger.warning(f"Failed to terminate Plasma store process: {e}")
                
        # Clean up socket file
        if self.has_plasma and os.path.exists(self.shared_memory_path):
            try:
                os.unlink(self.shared_memory_path)
            except Exception as e:
                logger.warning(f"Failed to remove Plasma socket file: {e}")
                
        # Clean up metadata directory
        try:
            for filename in os.listdir(self.metadata_path):
                if filename.endswith(('.json', '.parquet')):
                    try:
                        os.remove(os.path.join(self.metadata_path, filename))
                    except Exception:
                        pass
        except Exception:
            pass
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        if self.auto_cleanup:
            self.cleanup()


class ZeroCopyTable:
    """Wrapper for a shared Arrow table with zero-copy access.
    
    This class provides a convenient interface for working with a shared
    Arrow table, including automatic reference counting and cleanup.
    """
    
    def __init__(self, 
                 manager: ZeroCopyManager, 
                 name: str,
                 table: Optional[pa.Table] = None,
                 description: Optional[str] = None,
                 ttl_seconds: Optional[int] = None):
        """Initialize the zero-copy table.
        
        Args:
            manager: ZeroCopyManager instance
            name: Name for the shared table
            table: Optional Arrow table to share (if None, try to access existing)
            description: Optional description of the table
            ttl_seconds: Optional time-to-live in seconds
        """
        self.manager = manager
        self.name = name
        self.metadata = None
        self.handle = None
        
        if table is not None:
            # Share new table
            self.metadata = manager.share_table(
                table, name, description, ttl_seconds
            )
            self.handle = manager.get_c_data_interface_handle(name)
        else:
            # Try to access existing table
            # Find table by name
            tables = manager.list_shared_tables()
            for table_metadata in tables:
                if table_metadata.get("name") == name:
                    self.metadata = table_metadata
                    self.handle = manager.get_c_data_interface_handle(name)
                    break
    
    def get_table(self) -> Optional[pa.Table]:
        """Get the shared Arrow table.
        
        Returns:
            The shared Arrow table or None if not available
        """
        if self.handle:
            return self.manager.access_via_c_data_interface(self.handle)
        elif self.metadata:
            return self.manager.get_shared_table(self.metadata)
        else:
            return None
    
    def refresh_metadata(self) -> bool:
        """Refresh metadata for the shared table.
        
        Returns:
            True if metadata was refreshed successfully, False otherwise
        """
        tables = self.manager.list_shared_tables()
        for table_metadata in tables:
            if table_metadata.get("name") == self.name:
                self.metadata = table_metadata
                self.handle = self.manager.get_c_data_interface_handle(self.name)
                return True
                
        return False
    
    def release(self):
        """Release the shared table."""
        if self.name:
            self.manager.unshare_table(self.name)
            self.metadata = None
            self.handle = None
    
    def __del__(self):
        """Destructor to ensure proper cleanup."""
        self.release()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()