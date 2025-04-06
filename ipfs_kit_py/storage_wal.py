# ipfs_kit_py/storage_wal.py

import os
import time
import uuid
import json
import enum
import logging
import threading
import datetime
import tempfile
from typing import Dict, List, Any, Optional, Tuple, Callable, Union
from pathlib import Path
from queue import Queue, Empty
from collections import defaultdict

# Optional dependencies
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from pyarrow import compute as pc
    from pyarrow.dataset import dataset
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OperationType(enum.Enum):
    """Types of operations that can be stored in the WAL."""
    ADD = "add"
    GET = "get"
    PIN = "pin"
    UNPIN = "unpin"
    RM = "rm"
    CAT = "cat"
    LIST = "list"
    MKDIR = "mkdir"
    COPY = "copy"
    MOVE = "move"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    CUSTOM = "custom"

class OperationStatus(enum.Enum):
    """Status values for WAL operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class BackendType(enum.Enum):
    """Types of storage backends."""
    IPFS = "ipfs"
    S3 = "s3"
    STORACHA = "storacha"
    LOCAL = "local"
    CUSTOM = "custom"

class StorageWriteAheadLog:
    """
    Write-ahead log for IPFS storage operations.
    
    This class provides a reliable way to queue storage operations when backend
    services (IPFS, S3, etc.) are unavailable. Operations are persisted in
    a write-ahead log using parquet files, and processed when backends become available.
    """
    
    def __init__(self, base_path: str = "~/.ipfs_kit/wal", 
                partition_size: int = 1000,
                max_retries: int = 5,
                retry_delay: int = 60,
                archive_completed: bool = True,
                process_interval: int = 5,
                health_monitor: Optional[Any] = None):
        """
        Initialize the storage write-ahead log.
        
        Args:
            base_path: Base directory for WAL storage
            partition_size: Maximum number of operations per partition file
            max_retries: Maximum number of retry attempts for failed operations
            retry_delay: Delay in seconds between retry attempts
            archive_completed: Whether to move completed operations to archive
            process_interval: Interval in seconds for processing pending operations
            health_monitor: Optional backend health monitor
        """
        if not ARROW_AVAILABLE:
            logger.warning("PyArrow not available. Write-ahead log will operate in limited mode.")
            
        self.base_path = os.path.expanduser(base_path)
        self.partitions_path = os.path.join(self.base_path, "partitions")
        self.archives_path = os.path.join(self.base_path, "archives")
        self.partition_size = partition_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.archive_completed = archive_completed
        self.process_interval = process_interval
        self.health_monitor = health_monitor
        
        # Create directories if they don't exist
        os.makedirs(self.partitions_path, exist_ok=True)
        if self.archive_completed:
            os.makedirs(self.archives_path, exist_ok=True)
            
        # Thread safety
        self._lock = threading.RLock()
        self._processing_lock = threading.RLock()
        
        # Operation processing
        self._processing_thread = None
        self._stop_processing = threading.Event()
        self._processing_queue = Queue()
        
        # Schema for operations
        self.schema = self._create_schema()
        
        # Current partition information
        self.current_partition_id = None
        self.current_partition_path = None
        self.current_partition_count = 0
        
        # Initialize partitions
        self._init_partitions()
        
        # Start background processing
        self._start_processing()
    
    def _create_schema(self) -> Optional[Any]:
        """Create the Arrow schema for WAL entries."""
        if not ARROW_AVAILABLE:
            return None
            
        import pyarrow as pa
        return pa.schema([
            # Operation identification
            pa.field('operation_id', pa.string()),
            pa.field('operation_type', pa.string()),  # add, pin, remove, etc.
            
            # Status and timing
            pa.field('status', pa.string()),  # pending, processing, completed, failed
            pa.field('timestamp', pa.timestamp('ms')),
            pa.field('updated_at', pa.timestamp('ms')),
            pa.field('completed_at', pa.timestamp('ms')),
            
            # Storage backend
            pa.field('backend', pa.string()),  # ipfs, s3, storacha
            
            # Operation details
            pa.field('parameters', pa.map_(pa.string(), pa.string())),
            pa.field('result', pa.struct([
                pa.field('cid', pa.string()),
                pa.field('size', pa.int64()),
                pa.field('destination', pa.string())
            ])),
            
            # Error tracking
            pa.field('error', pa.string()),
            pa.field('error_type', pa.string()),
            pa.field('retry_count', pa.int32()),
            pa.field('max_retries', pa.int32()),
            
            # Next retry
            pa.field('next_retry_at', pa.timestamp('ms')),
        ])
    
    def _init_partitions(self):
        """Initialize partitions by scanning existing files."""
        # Find existing partition files
        partition_files = []
        for file in os.listdir(self.partitions_path):
            if file.endswith('.parquet') and file.startswith('wal_'):
                partition_files.append(file)
        
        if not partition_files:
            # No existing partitions, create the first one
            self.current_partition_id = self._generate_partition_id()
            self.current_partition_path = self._get_partition_path(self.current_partition_id)
            self.current_partition_count = 0
            return
        
        # Sort by timestamp (assuming format is wal_TIMESTAMP_COUNTER.parquet)
        partition_files.sort()
        latest_partition = partition_files[-1]
        
        # Extract ID from filename
        self.current_partition_id = latest_partition.split('.')[0]
        self.current_partition_path = self._get_partition_path(self.current_partition_id)
        
        # Count records in the latest partition
        if ARROW_AVAILABLE:
            try:
                table = pq.read_table(self.current_partition_path)
                self.current_partition_count = table.num_rows
            except Exception as e:
                logger.error(f"Error reading partition {self.current_partition_path}: {e}")
                # Create a new partition in case of error
                self.current_partition_id = self._generate_partition_id()
                self.current_partition_path = self._get_partition_path(self.current_partition_id)
                self.current_partition_count = 0
        else:
            # If Arrow not available, try to estimate count from file size
            try:
                file_size = os.path.getsize(self.current_partition_path)
                # Rough estimate - assume 1KB per record
                self.current_partition_count = file_size // 1024
            except Exception:
                # Create a new partition in case of error
                self.current_partition_id = self._generate_partition_id()
                self.current_partition_path = self._get_partition_path(self.current_partition_id)
                self.current_partition_count = 0
    
    def _generate_partition_id(self) -> str:
        """Generate a unique partition ID."""
        timestamp = int(time.time())
        counter = 0
        return f"wal_{timestamp}_{counter}"
    
    def _get_partition_path(self, partition_id: str) -> str:
        """Get the file path for a partition."""
        return os.path.join(self.partitions_path, f"{partition_id}.parquet")
    
    def _get_archive_path(self, archive_id: str) -> str:
        """Get the file path for an archive."""
        return os.path.join(self.archives_path, f"archive_{archive_id}.parquet")
    
    def _start_processing(self):
        """Start the background processing thread."""
        if self._processing_thread is not None and self._processing_thread.is_alive():
            return
            
        self._stop_processing.clear()
        self._processing_thread = threading.Thread(
            target=self._process_loop,
            name="WAL-Processing-Thread",
            daemon=True
        )
        self._processing_thread.start()
        logger.info("WAL processing thread started")
    
    def _stop_processing_thread(self):
        """Stop the background processing thread."""
        if self._processing_thread is None or not self._processing_thread.is_alive():
            return
            
        self._stop_processing.set()
        self._processing_thread.join(timeout=10.0)
        if self._processing_thread.is_alive():
            logger.warning("WAL processing thread did not stop cleanly")
        else:
            logger.info("WAL processing thread stopped")
    
    def _process_loop(self):
        """Main processing loop for background thread."""
        while not self._stop_processing.is_set():
            try:
                # Process pending operations
                self._process_pending_operations()
                
                # Process retry queue
                while not self._processing_queue.empty():
                    try:
                        operation_id = self._processing_queue.get(block=False)
                        self._process_operation(operation_id)
                        self._processing_queue.task_done()
                    except Empty:
                        break
                
            except Exception as e:
                logger.error(f"Error in WAL processing loop: {e}")
            
            # Wait before next processing cycle
            self._stop_processing.wait(self.process_interval)
    
    def _process_pending_operations(self):
        """Process all pending operations."""
        with self._processing_lock:
            # Get list of pending operations
            pending_ops = self.get_operations_by_status(OperationStatus.PENDING.value)
            
            if not pending_ops:
                return
                
            # Check if backends are healthy before processing
            if self.health_monitor:
                backend_statuses = self.health_monitor.get_status()
                
                # Group operations by backend
                backend_ops = defaultdict(list)
                for op in pending_ops:
                    backend = op.get("backend")
                    backend_ops[backend].append(op)
                
                # Process operations for healthy backends
                for backend, ops in backend_ops.items():
                    status = backend_statuses.get(backend, {}).get("status")
                    if status == "online":
                        for op in ops:
                            self._processing_queue.put(op["operation_id"])
                    else:
                        logger.info(f"Skipping {len(ops)} operations for {backend} backend (status: {status})")
            else:
                # No health monitor, process all pending operations
                for op in pending_ops:
                    self._processing_queue.put(op["operation_id"])
    
    def _process_operation(self, operation_id: str):
        """Process a specific operation by ID."""
        # Get the operation
        operation = self.get_operation(operation_id)
        if not operation:
            logger.warning(f"Operation {operation_id} not found")
            return
            
        # Skip if not in pending or retrying state
        status = operation.get("status")
        if status not in [OperationStatus.PENDING.value, OperationStatus.RETRYING.value]:
            logger.debug(f"Skipping operation {operation_id} (status: {status})")
            return
            
        # Update status to processing
        self.update_operation_status(
            operation_id, 
            OperationStatus.PROCESSING.value,
            {"updated_at": int(time.time() * 1000)}
        )
        
        # Simulate actual processing with storage backend
        # In a real implementation, this would call the actual storage backend methods
        try:
            # Get the operation handler
            handler = self._get_operation_handler(operation)
            
            if handler:
                # Call the handler
                result = handler(operation)
                
                if result.get("success", False):
                    # Operation succeeded
                    self.update_operation_status(
                        operation_id,
                        OperationStatus.COMPLETED.value,
                        {
                            "updated_at": int(time.time() * 1000),
                            "completed_at": int(time.time() * 1000),
                            "result": result
                        }
                    )
                else:
                    # Operation failed
                    retry_count = operation.get("retry_count", 0)
                    max_retries = operation.get("max_retries", self.max_retries)
                    
                    if retry_count < max_retries:
                        # Schedule retry
                        next_retry_at = int(time.time() * 1000) + (self.retry_delay * 1000)
                        self.update_operation_status(
                            operation_id,
                            OperationStatus.RETRYING.value,
                            {
                                "updated_at": int(time.time() * 1000),
                                "retry_count": retry_count + 1,
                                "next_retry_at": next_retry_at,
                                "error": result.get("error"),
                                "error_type": result.get("error_type")
                            }
                        )
                    else:
                        # Max retries reached, mark as failed
                        self.update_operation_status(
                            operation_id,
                            OperationStatus.FAILED.value,
                            {
                                "updated_at": int(time.time() * 1000),
                                "error": result.get("error"),
                                "error_type": result.get("error_type")
                            }
                        )
            else:
                # No handler found
                self.update_operation_status(
                    operation_id,
                    OperationStatus.FAILED.value,
                    {
                        "updated_at": int(time.time() * 1000),
                        "error": "No handler found for operation",
                        "error_type": "handler_not_found"
                    }
                )
        except Exception as e:
            # Exception during processing
            self.update_operation_status(
                operation_id,
                OperationStatus.FAILED.value,
                {
                    "updated_at": int(time.time() * 1000),
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            logger.error(f"Error processing operation {operation_id}: {e}")
    
    def _get_operation_handler(self, operation: Dict[str, Any]) -> Optional[Callable]:
        """Get the handler function for an operation type.
        
        In a real implementation, this would return the actual handler function
        from the API or storage backend. For demonstration purposes, we return
        a mock handler that simulates success or failure.
        """
        # This is a placeholder - in a real implementation, you would return
        # the actual handler function from your API or backend
        def mock_handler(op):
            # Simulate some processing time
            time.sleep(0.1)
            
            # Simulate success or failure (90% success rate)
            if operation.get("backend") == "ipfs" and operation.get("operation_type") == "add":
                # Simulate a specific operation
                return {
                    "success": True,
                    "cid": f"Qm{''.join(['abcdef0123456789'[i % 16] for i in range(44)])}"
                }
            elif operation.get("backend") == "s3":
                # S3 backend - always succeeds in this demo
                return {
                    "success": True,
                    "destination": f"s3://bucket/key-{uuid.uuid4()}"
                }
            elif operation.get("backend") == "storacha":
                # Storacha backend - has occasional failures
                if operation.get("retry_count", 0) > 1:
                    # Succeed after a retry
                    return {
                        "success": True,
                        "cid": f"Qm{''.join(['abcdef0123456789'[i % 16] for i in range(44)])}"
                    }
                else:
                    # Fail on first attempt
                    return {
                        "success": False,
                        "error": "Temporary service unavailable",
                        "error_type": "service_unavailable"
                    }
            else:
                # Other operations - random success/failure
                import random
                if random.random() < 0.9:
                    return {"success": True}
                else:
                    return {
                        "success": False,
                        "error": "Operation failed",
                        "error_type": "generic_error"
                    }
        
        return mock_handler
    
    def add_operation(self, operation_type: Union[str, OperationType], 
                     backend: Union[str, BackendType],
                     parameters: Dict[str, Any] = None,
                     max_retries: Optional[int] = None) -> Dict[str, Any]:
        """
        Add a new operation to the WAL.
        
        Args:
            operation_type: Type of operation to add
            backend: Storage backend to use
            parameters: Operation parameters
            max_retries: Maximum retry attempts (None to use default)
            
        Returns:
            Dictionary with operation information
        """
        # Convert enum values to strings
        if isinstance(operation_type, OperationType):
            operation_type = operation_type.value
            
        if isinstance(backend, BackendType):
            backend = backend.value
            
        # Create operation ID
        operation_id = str(uuid.uuid4())
        
        # Create timestamp
        timestamp = int(time.time() * 1000)  # milliseconds
        
        # Create operation object
        operation = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "backend": backend,
            "status": OperationStatus.PENDING.value,
            "timestamp": timestamp,
            "updated_at": timestamp,
            "parameters": parameters or {},
            "retry_count": 0,
            "max_retries": max_retries if max_retries is not None else self.max_retries
        }
        
        # Store the operation
        self._store_operation(operation)
        
        # Queue for processing if backend is healthy
        if self.health_monitor:
            backend_status = self.health_monitor.get_status(backend)
            if backend_status.get("status") == "online":
                self._processing_queue.put(operation_id)
        else:
            # No health monitor, assume backend is healthy
            self._processing_queue.put(operation_id)
        
        return {
            "success": True,
            "operation_id": operation_id,
            "operation_type": operation_type,
            "backend": backend,
            "status": OperationStatus.PENDING.value,
            "timestamp": timestamp
        }
    
    def _store_operation(self, operation: Dict[str, Any]) -> bool:
        """Store an operation in the current partition."""
        with self._lock:
            # Check if we need to create a new partition
            if (self.current_partition_count >= self.partition_size or
                self.current_partition_path is None):
                # Create a new partition
                self.current_partition_id = self._generate_partition_id()
                self.current_partition_path = self._get_partition_path(self.current_partition_id)
                self.current_partition_count = 0
            
            # Store the operation
            success = self._append_to_partition(operation)
            
            if success:
                self.current_partition_count += 1
                
            return success
    
    def _append_to_partition(self, operation: Dict[str, Any]) -> bool:
        """Append an operation to the current partition file."""
        if ARROW_AVAILABLE:
            return self._append_to_partition_arrow(operation)
        else:
            return self._append_to_partition_json(operation)
    
    def _append_to_partition_arrow(self, operation: Dict[str, Any]) -> bool:
        """Append an operation to the current partition using Arrow."""
        try:
            # Convert operation to Arrow RecordBatch
            arrays = []
            
            for field in self.schema:
                field_name = field.name
                
                if field_name in operation:
                    value = operation[field_name]
                    
                    # Handle special types
                    if field.type == pa.timestamp('ms') and isinstance(value, (int, float)):
                        # Create timestamp from milliseconds
                        arrays.append(pa.array([value], type=field.type))
                    elif field.type.id == pa.Type.STRUCT:
                        # Handle struct fields
                        if value is None:
                            arrays.append(pa.array([None], type=field.type))
                        else:
                            # Create struct field with None values for missing fields
                            struct_values = {}
                            for struct_field in field.type:
                                subfield_name = struct_field.name
                                if subfield_name in value:
                                    struct_values[subfield_name] = [value[subfield_name]]
                                else:
                                    struct_values[subfield_name] = [None]
                            arrays.append(pa.StructArray.from_arrays(
                                arrays=list(struct_values.values()),
                                names=list(struct_values.keys())
                            ))
                    elif field.type.id == pa.Type.MAP:
                        # Handle map fields
                        if value is None or not value:
                            arrays.append(pa.array([None], type=field.type))
                        else:
                            # Convert dict to map
                            keys = list(value.keys())
                            values = [str(value[k]) for k in keys]
                            arrays.append(pa.MapArray.from_arrays(
                                pa.array(keys, type=pa.string()),
                                pa.array(values, type=pa.string())
                            ))
                    else:
                        # Regular field
                        arrays.append(pa.array([value], type=field.type))
                else:
                    # Field not present in operation
                    arrays.append(pa.array([None], type=field.type))
            
            # Create RecordBatch
            batch = pa.RecordBatch.from_arrays(arrays, schema=self.schema)
            
            # Convert to Table
            table = pa.Table.from_batches([batch])
            
            # Check if the file exists
            if os.path.exists(self.current_partition_path):
                # Append to existing file
                # We first read the existing data
                existing_table = pq.read_table(self.current_partition_path)
                
                # Concatenate with new data
                combined_table = pa.concat_tables([existing_table, table])
                
                # Write back to file
                pq.write_table(combined_table, self.current_partition_path)
            else:
                # Create new file
                pq.write_table(table, self.current_partition_path)
                
            return True
            
        except Exception as e:
            logger.error(f"Error appending to partition with Arrow: {e}")
            return False
    
    def _append_to_partition_json(self, operation: Dict[str, Any]) -> bool:
        """Append an operation to the current partition using JSON (fallback)."""
        try:
            # Ensure the operation is serializable
            operation_json = json.dumps(operation)
            
            # Check if the file exists
            if os.path.exists(self.current_partition_path):
                # Open in append mode
                mode = 'a'
            else:
                # Create new file
                mode = 'w'
                
            # Write to file (one JSON object per line)
            with open(self.current_partition_path, mode) as f:
                if mode == 'a':
                    # Add a newline before appending
                    f.write('\n')
                f.write(operation_json)
                
            return True
            
        except Exception as e:
            logger.error(f"Error appending to partition with JSON: {e}")
            return False
    
    def get_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get an operation by ID."""
        # Check all partition files
        for partition_file in os.listdir(self.partitions_path):
            if not partition_file.endswith('.parquet'):
                continue
                
            partition_path = os.path.join(self.partitions_path, partition_file)
            
            if ARROW_AVAILABLE:
                try:
                    # Read the table
                    table = pq.read_table(partition_path)
                    
                    # Filter by operation_id
                    mask = pc.equal(table["operation_id"], operation_id)
                    filtered = table.filter(mask)
                    
                    if filtered.num_rows > 0:
                        # Convert to Python dict
                        return filtered.to_pylist()[0]
                except Exception as e:
                    logger.error(f"Error reading partition {partition_path}: {e}")
            else:
                # Fallback to JSON
                try:
                    with open(partition_path) as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                                
                            try:
                                op = json.loads(line)
                                if op.get("operation_id") == operation_id:
                                    return op
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    logger.error(f"Error reading partition {partition_path}: {e}")
        
        # Also check archives if enabled
        if self.archive_completed:
            for archive_file in os.listdir(self.archives_path):
                if not archive_file.endswith('.parquet'):
                    continue
                    
                archive_path = os.path.join(self.archives_path, archive_file)
                
                if ARROW_AVAILABLE:
                    try:
                        # Read the table
                        table = pq.read_table(archive_path)
                        
                        # Filter by operation_id
                        mask = pc.equal(table["operation_id"], operation_id)
                        filtered = table.filter(mask)
                        
                        if filtered.num_rows > 0:
                            # Convert to Python dict
                            return filtered.to_pylist()[0]
                    except Exception as e:
                        logger.error(f"Error reading archive {archive_path}: {e}")
                else:
                    # Fallback to JSON
                    try:
                        with open(archive_path) as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                    
                                try:
                                    op = json.loads(line)
                                    if op.get("operation_id") == operation_id:
                                        return op
                                except json.JSONDecodeError:
                                    continue
                    except Exception as e:
                        logger.error(f"Error reading archive {archive_path}: {e}")
        
        # Operation not found
        return None
    
    def update_operation_status(self, operation_id: str, 
                               new_status: Union[str, OperationStatus],
                               updates: Dict[str, Any] = None) -> bool:
        """
        Update the status of an operation.
        
        Args:
            operation_id: ID of the operation to update
            new_status: New status value
            updates: Additional fields to update
            
        Returns:
            True if the operation was updated, False otherwise
        """
        # Convert enum to string
        if isinstance(new_status, OperationStatus):
            new_status = new_status.value
            
        # Get the operation
        operation = self.get_operation(operation_id)
        if not operation:
            logger.warning(f"Operation {operation_id} not found")
            return False
            
        # Create a copy of the operation
        updated_op = operation.copy()
        
        # Update status
        updated_op["status"] = new_status
        
        # Update additional fields
        if updates:
            updated_op.update(updates)
            
        # Update updated_at timestamp if not provided
        if "updated_at" not in updates:
            updated_op["updated_at"] = int(time.time() * 1000)
        
        # Find the partition containing this operation
        for partition_file in os.listdir(self.partitions_path):
            if not partition_file.endswith('.parquet'):
                continue
                
            partition_path = os.path.join(self.partitions_path, partition_file)
            
            if ARROW_AVAILABLE:
                try:
                    # Read the table
                    table = pq.read_table(partition_path)
                    
                    # Check if operation exists in this partition
                    mask = pc.equal(table["operation_id"], operation_id)
                    filtered = table.filter(mask)
                    
                    if filtered.num_rows > 0:
                        # Operation found in this partition
                        
                        # Filter out the operation
                        inverse_mask = pc.invert(mask)
                        filtered_out = table.filter(inverse_mask)
                        
                        # Create a new record batch with the updated operation
                        arrays = []
                        for field in self.schema:
                            field_name = field.name
                            
                            if field_name in updated_op:
                                value = updated_op[field_name]
                                
                                # Handle special types
                                if field.type == pa.timestamp('ms') and isinstance(value, (int, float)):
                                    # Create timestamp from milliseconds
                                    arrays.append(pa.array([value], type=field.type))
                                elif field.type.id == pa.Type.STRUCT:
                                    # Handle struct fields
                                    if value is None:
                                        arrays.append(pa.array([None], type=field.type))
                                    else:
                                        # Create struct field with None values for missing fields
                                        struct_values = {}
                                        for struct_field in field.type:
                                            subfield_name = struct_field.name
                                            if subfield_name in value:
                                                struct_values[subfield_name] = [value[subfield_name]]
                                            else:
                                                struct_values[subfield_name] = [None]
                                        arrays.append(pa.StructArray.from_arrays(
                                            arrays=list(struct_values.values()),
                                            names=list(struct_values.keys())
                                        ))
                                elif field.type.id == pa.Type.MAP:
                                    # Handle map fields
                                    if value is None or not value:
                                        arrays.append(pa.array([None], type=field.type))
                                    else:
                                        # Convert dict to map
                                        keys = list(value.keys())
                                        values = [str(value[k]) for k in keys]
                                        arrays.append(pa.MapArray.from_arrays(
                                            pa.array(keys, type=pa.string()),
                                            pa.array(values, type=pa.string())
                                        ))
                                else:
                                    # Regular field
                                    arrays.append(pa.array([value], type=field.type))
                            else:
                                # Field not present in operation
                                arrays.append(pa.array([None], type=field.type))
                        
                        # Create record batch
                        batch = pa.RecordBatch.from_arrays(arrays, schema=self.schema)
                        
                        # Convert to table
                        updated_table = pa.Table.from_batches([batch])
                        
                        # If the operation status is completed and archiving is enabled,
                        # move it to the archive instead of updating in-place
                        if new_status == OperationStatus.COMPLETED.value and self.archive_completed:
                            # Write the filtered table back to the partition (without the completed operation)
                            if filtered_out.num_rows > 0:
                                pq.write_table(filtered_out, partition_path)
                            else:
                                # If this was the only operation in the partition, delete the file
                                os.remove(partition_path)
                            
                            # Add to archive
                            self._archive_operation(updated_op)
                        else:
                            # Concatenate with filtered table
                            if filtered_out.num_rows > 0:
                                combined_table = pa.concat_tables([filtered_out, updated_table])
                            else:
                                combined_table = updated_table
                            
                            # Write back to partition
                            pq.write_table(combined_table, partition_path)
                        
                        return True
                except Exception as e:
                    logger.error(f"Error updating operation in partition {partition_path}: {e}")
            else:
                # Fallback to JSON
                try:
                    operations = []
                    found = False
                    
                    with open(partition_path) as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                                
                            try:
                                op = json.loads(line)
                                if op.get("operation_id") == operation_id:
                                    # Found the operation
                                    found = True
                                    
                                    # If the operation status is completed and archiving is enabled,
                                    # don't add it back to the list
                                    if new_status == OperationStatus.COMPLETED.value and self.archive_completed:
                                        continue
                                    
                                    # Otherwise, add the updated operation
                                    operations.append(updated_op)
                                else:
                                    # Add the original operation
                                    operations.append(op)
                            except json.JSONDecodeError:
                                continue
                    
                    if found:
                        # Write operations back to file
                        with open(partition_path, 'w') as f:
                            for op in operations:
                                f.write(json.dumps(op) + '\n')
                        
                        # If the operation status is completed and archiving is enabled,
                        # add it to the archive
                        if new_status == OperationStatus.COMPLETED.value and self.archive_completed:
                            self._archive_operation(updated_op)
                            
                        return True
                except Exception as e:
                    logger.error(f"Error updating operation in partition {partition_path}: {e}")
        
        # Operation not found in any partition
        return False
    
    def _archive_operation(self, operation: Dict[str, Any]) -> bool:
        """Archive a completed operation."""
        if not self.archive_completed:
            return False
            
        # Generate archive ID based on the current date
        archive_id = datetime.datetime.now().strftime("%Y%m%d")
        archive_path = self._get_archive_path(archive_id)
        
        if ARROW_AVAILABLE:
            try:
                # Convert operation to Arrow RecordBatch
                arrays = []
                
                for field in self.schema:
                    field_name = field.name
                    
                    if field_name in operation:
                        value = operation[field_name]
                        
                        # Handle special types
                        if field.type == pa.timestamp('ms') and isinstance(value, (int, float)):
                            # Create timestamp from milliseconds
                            arrays.append(pa.array([value], type=field.type))
                        elif field.type.id == pa.Type.STRUCT:
                            # Handle struct fields
                            if value is None:
                                arrays.append(pa.array([None], type=field.type))
                            else:
                                # Create struct field with None values for missing fields
                                struct_values = {}
                                for struct_field in field.type:
                                    subfield_name = struct_field.name
                                    if subfield_name in value:
                                        struct_values[subfield_name] = [value[subfield_name]]
                                    else:
                                        struct_values[subfield_name] = [None]
                                arrays.append(pa.StructArray.from_arrays(
                                    arrays=list(struct_values.values()),
                                    names=list(struct_values.keys())
                                ))
                        elif field.type.id == pa.Type.MAP:
                            # Handle map fields
                            if value is None or not value:
                                arrays.append(pa.array([None], type=field.type))
                            else:
                                # Convert dict to map
                                keys = list(value.keys())
                                values = [str(value[k]) for k in keys]
                                arrays.append(pa.MapArray.from_arrays(
                                    pa.array(keys, type=pa.string()),
                                    pa.array(values, type=pa.string())
                                ))
                        else:
                            # Regular field
                            arrays.append(pa.array([value], type=field.type))
                    else:
                        # Field not present in operation
                        arrays.append(pa.array([None], type=field.type))
                
                # Create RecordBatch
                batch = pa.RecordBatch.from_arrays(arrays, schema=self.schema)
                
                # Convert to Table
                table = pa.Table.from_batches([batch])
                
                # Check if the archive file exists
                if os.path.exists(archive_path):
                    # Append to existing file
                    existing_table = pq.read_table(archive_path)
                    combined_table = pa.concat_tables([existing_table, table])
                    pq.write_table(combined_table, archive_path)
                else:
                    # Create new file
                    pq.write_table(table, archive_path)
                    
                return True
                
            except Exception as e:
                logger.error(f"Error archiving operation with Arrow: {e}")
                return False
        else:
            # Fallback to JSON
            try:
                # Ensure the operation is serializable
                operation_json = json.dumps(operation)
                
                # Check if the file exists
                if os.path.exists(archive_path):
                    # Open in append mode
                    mode = 'a'
                else:
                    # Create new file
                    mode = 'w'
                    
                # Write to file (one JSON object per line)
                with open(archive_path, mode) as f:
                    if mode == 'a':
                        # Add a newline before appending
                        f.write('\n')
                    f.write(operation_json)
                    
                return True
                
            except Exception as e:
                logger.error(f"Error archiving operation with JSON: {e}")
                return False
    
    def get_operations_by_status(self, status: Union[str, OperationStatus], 
                                limit: int = None) -> List[Dict[str, Any]]:
        """
        Get operations with a specific status.
        
        Args:
            status: Status to filter by
            limit: Maximum number of operations to return (None for all)
            
        Returns:
            List of operations with the specified status
        """
        # Convert enum to string
        if isinstance(status, OperationStatus):
            status = status.value
            
        operations = []
        
        # Check all partition files
        for partition_file in os.listdir(self.partitions_path):
            if not partition_file.endswith('.parquet'):
                continue
                
            partition_path = os.path.join(self.partitions_path, partition_file)
            
            if ARROW_AVAILABLE:
                try:
                    # Read the table
                    table = pq.read_table(partition_path)
                    
                    # Filter by status
                    mask = pc.equal(table["status"], status)
                    filtered = table.filter(mask)
                    
                    if filtered.num_rows > 0:
                        # Convert to Python dicts
                        operations.extend(filtered.to_pylist())
                except Exception as e:
                    logger.error(f"Error reading partition {partition_path}: {e}")
            else:
                # Fallback to JSON
                try:
                    with open(partition_path) as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                                
                            try:
                                op = json.loads(line)
                                if op.get("status") == status:
                                    operations.append(op)
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    logger.error(f"Error reading partition {partition_path}: {e}")
        
        # Sort by timestamp (newest first)
        operations.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        # Apply limit
        if limit is not None and limit > 0:
            operations = operations[:limit]
            
        return operations
    
    def get_all_operations(self) -> List[Dict[str, Any]]:
        """
        Get all operations in the WAL.
        
        Returns:
            List of all operations
        """
        operations = []
        
        # Check all partition files
        for partition_file in os.listdir(self.partitions_path):
            if not partition_file.endswith('.parquet'):
                continue
                
            partition_path = os.path.join(self.partitions_path, partition_file)
            
            if ARROW_AVAILABLE:
                try:
                    # Read the table
                    table = pq.read_table(partition_path)
                    
                    # Convert to Python dicts
                    operations.extend(table.to_pylist())
                except Exception as e:
                    logger.error(f"Error reading partition {partition_path}: {e}")
            else:
                # Fallback to JSON
                try:
                    with open(partition_path) as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                                
                            try:
                                op = json.loads(line)
                                operations.append(op)
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    logger.error(f"Error reading partition {partition_path}: {e}")
        
        # Check archives if enabled
        if self.archive_completed:
            for archive_file in os.listdir(self.archives_path):
                if not archive_file.endswith('.parquet'):
                    continue
                    
                archive_path = os.path.join(self.archives_path, archive_file)
                
                if ARROW_AVAILABLE:
                    try:
                        # Read the table
                        table = pq.read_table(archive_path)
                        
                        # Convert to Python dicts
                        operations.extend(table.to_pylist())
                    except Exception as e:
                        logger.error(f"Error reading archive {archive_path}: {e}")
                else:
                    # Fallback to JSON
                    try:
                        with open(archive_path) as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                    
                                try:
                                    op = json.loads(line)
                                    operations.append(op)
                                except json.JSONDecodeError:
                                    continue
                    except Exception as e:
                        logger.error(f"Error reading archive {archive_path}: {e}")
        
        # Sort by timestamp (newest first)
        operations.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        return operations
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the WAL.
        
        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_operations": 0,
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "retrying": 0,
            "partitions": 0,
            "archives": 0,
            "processing_active": self._processing_thread is not None and self._processing_thread.is_alive()
        }
        
        # Count operations by status
        all_ops = self.get_all_operations()
        stats["total_operations"] = len(all_ops)
        
        for op in all_ops:
            status = op.get("status")
            if status in stats:
                stats[status] += 1
        
        # Count partitions
        for file in os.listdir(self.partitions_path):
            if file.endswith('.parquet'):
                stats["partitions"] += 1
        
        # Count archives
        if self.archive_completed:
            for file in os.listdir(self.archives_path):
                if file.endswith('.parquet'):
                    stats["archives"] += 1
        
        return stats
    
    def cleanup(self, max_age_days: int = 30) -> Dict[str, Any]:
        """
        Clean up old operations.
        
        Args:
            max_age_days: Maximum age in days for operations to keep
            
        Returns:
            Dictionary with cleanup results
        """
        if not self.archive_completed:
            return {
                "success": False,
                "error": "Archive not enabled, cleanup not supported"
            }
            
        result = {
            "success": True,
            "removed_count": 0,
            "removed_files": []
        }
        
        # Calculate cutoff timestamp
        cutoff = time.time() - (max_age_days * 24 * 60 * 60)
        cutoff_ms = cutoff * 1000
        
        # Check all archive files
        for archive_file in os.listdir(self.archives_path):
            if not archive_file.endswith('.parquet'):
                continue
                
            archive_path = os.path.join(self.archives_path, archive_file)
            
            # Parse archive date from filename
            try:
                # Format: archive_YYYYMMDD.parquet
                date_str = archive_file.split('_')[1].split('.')[0]
                archive_date = datetime.datetime.strptime(date_str, "%Y%m%d")
                archive_timestamp = archive_date.timestamp()
                
                # If the archive is older than the cutoff, remove it
                if archive_timestamp < cutoff:
                    # Count operations in the archive
                    if ARROW_AVAILABLE:
                        try:
                            table = pq.read_table(archive_path)
                            result["removed_count"] += table.num_rows
                        except Exception:
                            # Can't read the file, estimate count from file size
                            try:
                                file_size = os.path.getsize(archive_path)
                                # Rough estimate - assume 1KB per record
                                result["removed_count"] += file_size // 1024
                            except Exception:
                                pass
                    else:
                        # Fallback to line counting
                        try:
                            with open(archive_path) as f:
                                for i, _ in enumerate(f):
                                    pass
                                result["removed_count"] += i + 1
                        except Exception:
                            pass
                    
                    # Remove the file
                    os.remove(archive_path)
                    result["removed_files"].append(archive_file)
            except Exception as e:
                logger.error(f"Error cleaning up archive {archive_file}: {e}")
        
        return result
    
    def wait_for_operation(self, operation_id: str, 
                          timeout: int = 60, 
                          check_interval: int = 1) -> Dict[str, Any]:
        """
        Wait for an operation to complete.
        
        Args:
            operation_id: ID of the operation to wait for
            timeout: Maximum time to wait in seconds
            check_interval: Time between checks in seconds
            
        Returns:
            Dictionary with operation result
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Get the operation
            operation = self.get_operation(operation_id)
            
            if not operation:
                return {
                    "success": False,
                    "error": f"Operation {operation_id} not found"
                }
                
            status = operation.get("status")
            
            if status in [OperationStatus.COMPLETED.value, OperationStatus.FAILED.value]:
                # Operation is done
                result = {
                    "success": status == OperationStatus.COMPLETED.value,
                    "status": status,
                    "operation_id": operation_id
                }
                
                # Add result if available
                if "result" in operation:
                    result["result"] = operation["result"]
                    
                # Add error if available
                if "error" in operation:
                    result["error"] = operation["error"]
                    
                return result
                
            # Wait before checking again
            time.sleep(check_interval)
        
        # Timeout reached
        return {
            "success": False,
            "status": "timeout",
            "operation_id": operation_id,
            "error": f"Timeout waiting for operation to complete (waited {timeout}s)"
        }
    
    def close(self):
        """
        Close the WAL and clean up resources.
        
        This method should be called when the WAL is no longer needed.
        """
        # Stop the processing thread
        self._stop_processing_thread()

        # Close any open file handles if mmap_files exists and is not empty
        if hasattr(self, 'mmap_files') and self.mmap_files:
            for _, (file_obj, _) in self.mmap_files.items():
                if file_obj: # Check if file_obj is not None
                    try:
                        file_obj.close()
                    except Exception as e:
                        logger.warning(f"Error closing mmap file: {e}")

        logger.info("WAL closed")


class BackendHealthMonitor:
    """
    Monitor health of storage backends.
    
    This class monitors the health of various storage backends (IPFS, S3, Storacha)
    and provides status information and callbacks for status changes.
    """
    
    def __init__(self, check_interval: int = 60, 
                history_size: int = 25,
                backends: List[str] = None,
                backend_configs: Dict[str, Dict[str, Any]] = None,
                status_change_callback: Optional[Callable[[str, str, str], None]] = None):
        """
        Initialize the backend health monitor.
        
        Args:
            check_interval: Interval in seconds between health checks
            history_size: Number of check results to keep in history
            backends: List of backends to monitor (None for all)
            backend_configs: Configuration for each backend
            status_change_callback: Function called when backend status changes
        """
        self.check_interval = check_interval
        self.history_size = history_size
        self.backends = backends or [b.value for b in BackendType]
        self.backend_configs = backend_configs or {}
        self.status_change_callback = status_change_callback
        
        # Initialize status for each backend
        self.backend_status = {}
        for backend in self.backends:
            self.backend_status[backend] = {
                "status": "unknown",
                "check_history": [],
                "last_check": 0,
                "error": None
            }
        
        # Thread for health checks
        self._check_thread = None
        self._stop_checking = threading.Event()
        
        # Start health checks
        self._start_checking()
    
    def _start_checking(self):
        """Start the health check thread."""
        if self._check_thread is not None and self._check_thread.is_alive():
            return
            
        self._stop_checking.clear()
        self._check_thread = threading.Thread(
            target=self._check_loop,
            name="Backend-Health-Check-Thread",
            daemon=True
        )
        self._check_thread.start()
        logger.info("Backend health check thread started")
    
    def _stop_checking_thread(self):
        """Stop the health check thread."""
        if self._check_thread is None or not self._check_thread.is_alive():
            return
            
        self._stop_checking.set()
        self._check_thread.join(timeout=10.0)
        if self._check_thread.is_alive():
            logger.warning("Backend health check thread did not stop cleanly")
        else:
            logger.info("Backend health check thread stopped")
    
    def _check_loop(self):
        """Main loop for health checks."""
        while not self._stop_checking.is_set():
            try:
                # Check each backend
                for backend in self.backends:
                    self._check_backend(backend)
            except Exception as e:
                logger.error(f"Error in backend health check loop: {e}")
            
            # Wait before next check
            self._stop_checking.wait(self.check_interval)
    
    def _check_backend(self, backend: str):
        """
        Check the health of a specific backend.
        
        Args:
            backend: Backend to check
        """
        try:
            # Get backend configuration
            config = self.backend_configs.get(backend, {})
            
            # Call the appropriate health check function
            if backend == BackendType.IPFS.value:
                healthy = self._check_ipfs_health(config)
            elif backend == BackendType.S3.value:
                healthy = self._check_s3_health(config)
            elif backend == BackendType.STORACHA.value:
                healthy = self._check_storacha_health(config)
            elif backend == BackendType.LOCAL.value:
                healthy = self._check_local_health(config)
            else:
                # Unknown backend
                healthy = False
            
            # Update backend status
            self._update_backend_status(backend, healthy)
            
        except Exception as e:
            logger.error(f"Error checking {backend} health: {e}")
            # Update backend status with error
            self._update_backend_status(backend, False, str(e))
    
    def _check_ipfs_health(self, config: Dict[str, Any]) -> bool:
        """
        Check IPFS health.
        
        Args:
            config: IPFS configuration
            
        Returns:
            True if IPFS is healthy, False otherwise
        """
        # This is a placeholder - in a real implementation, you would
        # check the IPFS daemon health with appropriate API calls
        
        # Simulate some network latency
        time.sleep(0.1)
        
        # In this example, we'll simulate IPFS being healthy 95% of the time
        import random
        return random.random() < 0.95
    
    def _check_s3_health(self, config: Dict[str, Any]) -> bool:
        """
        Check S3 health.
        
        Args:
            config: S3 configuration
            
        Returns:
            True if S3 is healthy, False otherwise
        """
        # This is a placeholder - in a real implementation, you would
        # check the S3 service health with appropriate API calls
        
        # Simulate some network latency
        time.sleep(0.1)
        
        # In this example, we'll simulate S3 being healthy 99% of the time
        import random
        return random.random() < 0.99
    
    def _check_storacha_health(self, config: Dict[str, Any]) -> bool:
        """
        Check Storacha health.
        
        Args:
            config: Storacha configuration
            
        Returns:
            True if Storacha is healthy, False otherwise
        """
        # This is a placeholder - in a real implementation, you would
        # check the Storacha service health with appropriate API calls
        
        # Simulate some network latency
        time.sleep(0.2)
        
        # In this example, we'll simulate Storacha being healthy 90% of the time
        import random
        return random.random() < 0.9
    
    def _check_local_health(self, config: Dict[str, Any]) -> bool:
        """
        Check local storage health.
        
        Args:
            config: Local storage configuration
            
        Returns:
            True if local storage is healthy, False otherwise
        """
        # Local storage should always be healthy
        path = config.get("path", "/")
        
        try:
            # Check if the path exists and is writable
            if not os.path.exists(path):
                return False
                
            # Try to create a temporary file
            fd, temp_path = tempfile.mkstemp(dir=path)
            os.close(fd)
            os.remove(temp_path)
            
            return True
        except Exception:
            return False
    
    def _update_backend_status(self, backend: str, healthy: bool, error: str = None):
        """
        Update the status of a backend.
        
        Args:
            backend: Backend to update
            healthy: Whether the backend is healthy
            error: Error message if any
        """
        status = self.backend_status.get(backend, {
            "status": "unknown",
            "check_history": [],
            "last_check": 0,
            "error": None
        })
        
        # Update check history
        history = status.get("check_history", [])
        history.append(healthy)
        
        # Limit history size
        if len(history) > self.history_size:
            history = history[-self.history_size:]
        
        # Calculate new status based on history
        if len(history) > 0:
            # Need at least 3 checks to determine status
            if len(history) >= 3:
                recent_checks = history[-3:]
                if all(recent_checks):
                    new_status = "online"
                elif not any(recent_checks):
                    new_status = "offline"
                else:
                    new_status = "degraded"
            else:
                # Not enough history, use the current check
                new_status = "online" if healthy else "offline"
        else:
            new_status = "unknown"
        
        # Check if status changed
        old_status = status.get("status", "unknown")
        status_changed = old_status != new_status
        
        # Update status
        status["status"] = new_status
        status["check_history"] = history
        status["last_check"] = time.time()
        status["error"] = error
        
        # Store updated status
        self.backend_status[backend] = status
        
        # Call status change callback if status changed
        if status_changed and self.status_change_callback:
            try:
                self.status_change_callback(backend, old_status, new_status)
            except Exception as e:
                logger.error(f"Error in status change callback: {e}")
    
    def get_status(self, backend: str = None) -> Dict[str, Any]:
        """
        Get the status of one or all backends.
        
        Args:
            backend: Backend to get status for, or None for all
            
        Returns:
            Dictionary with backend status information
        """
        if backend:
            return self.backend_status.get(backend, {
                "status": "unknown",
                "check_history": [],
                "last_check": 0,
                "error": None
            })
        else:
            return self.backend_status
    
    def is_backend_available(self, backend: str) -> bool:
        """
        Check if a backend is available.
        
        Args:
            backend: Backend to check
            
        Returns:
            True if the backend is available, False otherwise
        """
        status = self.get_status(backend)
        return status.get("status") == "online"
    
    def close(self):
        """
        Close the health monitor and clean up resources.
        
        This method should be called when the health monitor is no longer needed.
        """
        # Stop the health check thread
        self._stop_checking_thread()
        
        logger.info("Backend health monitor closed")


# Example usage
if __name__ == "__main__":
    # Enable debug logging
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Create health monitor
    health_monitor = BackendHealthMonitor(
        check_interval=5,
        history_size=10,
        status_change_callback=lambda backend, old, new: print(f"Backend {backend} status changed from {old} to {new}")
    )
    
    # Create WAL
    wal = StorageWriteAheadLog(
        base_path="~/.ipfs_kit/wal",
        partition_size=100,
        health_monitor=health_monitor
    )
    
    # Add some operations
    for i in range(5):
        result = wal.add_operation(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS,
            parameters={"path": f"/tmp/file{i}.txt"}
        )
        print(f"Added operation: {result['operation_id']}")
    
    # Wait for operations to complete
    time.sleep(5)
    
    # Get statistics
    stats = wal.get_statistics()
    print(f"WAL statistics: {stats}")
    
    # Get pending operations
    pending = wal.get_operations_by_status(OperationStatus.PENDING)
    print(f"Pending operations: {len(pending)}")
    
    # Clean up
    wal.close()
    health_monitor.close()
