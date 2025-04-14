"""
MCP Streaming Module for efficient transfer of large content.

This module provides optimized streaming capabilities for the MCP server, including:
1. Chunked file uploads and downloads for memory efficiency
2. Progress tracking and throughput calculation
3. Background processing for non-blocking operations
4. Stream multiplexing for parallel transfers
"""

import os
import io
import time
import uuid
import json
import logging
import threading
import queue
import tempfile
import asyncio
from typing import Dict, Any, List, Optional, Union, BinaryIO, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

# Configure logger
logger = logging.getLogger(__name__)

# Define constants
DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
DEFAULT_BUFFER_SIZE = 8 * 1024 * 1024  # 8MB
DEFAULT_PROGRESS_INTERVAL = 0.5  # seconds
MAX_CONCURRENT_CHUNKS = 4


class StreamStatus(Enum):
    """Status of a stream operation."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class StreamDirection(Enum):
    """Direction of a stream operation."""
    UPLOAD = "upload"
    DOWNLOAD = "download"


class StreamType(Enum):
    """Type of streaming operation."""
    FILE = "file"
    MEMORY = "memory"
    PIPE = "pipe"
    NETWORK = "network"


@dataclass
class StreamProgress:
    """Progress information for a stream operation."""
    bytes_processed: int = 0
    total_bytes: int = 0
    start_time: float = field(default_factory=time.time)
    last_update_time: float = field(default_factory=time.time)
    last_bytes_processed: int = 0
    chunks_processed: int = 0
    total_chunks: int = 0
    current_speed: float = 0.0  # bytes/second
    average_speed: float = 0.0  # bytes/second
    estimated_remaining: float = 0.0  # seconds
    percentage: float = 0.0
    
    def update(self, bytes_processed: int, total_bytes: Optional[int] = None) -> None:
        """
        Update progress information.
        
        Args:
            bytes_processed: Current number of bytes processed
            total_bytes: Optional total bytes (if known)
        """
        now = time.time()
        time_diff = now - self.last_update_time
        
        # Update byte counts
        self.bytes_processed = bytes_processed
        if total_bytes is not None:
            self.total_bytes = total_bytes
        
        # Only update speed calculations if enough time has passed
        if time_diff >= 0.1:  # 100ms minimum to avoid division by very small numbers
            # Calculate current speed
            bytes_diff = bytes_processed - self.last_bytes_processed
            self.current_speed = bytes_diff / time_diff if time_diff > 0 else 0
            
            # Calculate average speed
            elapsed = now - self.start_time
            self.average_speed = bytes_processed / elapsed if elapsed > 0 else 0
            
            # Estimate remaining time
            if self.total_bytes > 0 and self.average_speed > 0:
                remaining_bytes = self.total_bytes - bytes_processed
                self.estimated_remaining = remaining_bytes / self.average_speed
            else:
                self.estimated_remaining = 0
            
            # Calculate percentage
            if self.total_bytes > 0:
                self.percentage = (bytes_processed / self.total_bytes) * 100
            else:
                self.percentage = 0
            
            # Update tracking variables
            self.last_update_time = now
            self.last_bytes_processed = bytes_processed
    
    def increment_chunks(self, processed: int = 1, total: Optional[int] = None) -> None:
        """
        Increment chunk counters.
        
        Args:
            processed: Number of chunks processed
            total: Optional total chunks (if known)
        """
        self.chunks_processed += processed
        if total is not None:
            self.total_chunks = total
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert progress to dictionary."""
        return {
            "bytes_processed": self.bytes_processed,
            "total_bytes": self.total_bytes,
            "elapsed_time": time.time() - self.start_time,
            "chunks_processed": self.chunks_processed,
            "total_chunks": self.total_chunks,
            "current_speed": self.current_speed,
            "average_speed": self.average_speed,
            "estimated_remaining": self.estimated_remaining,
            "percentage": self.percentage
        }


@dataclass
class StreamOperation:
    """Information about a streaming operation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    direction: StreamDirection = StreamDirection.UPLOAD
    type: StreamType = StreamType.FILE
    status: StreamStatus = StreamStatus.PENDING
    source: Optional[Union[str, BinaryIO]] = None
    destination: Optional[Union[str, BinaryIO]] = None
    backend_name: Optional[str] = None
    content_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    progress: StreamProgress = field(default_factory=StreamProgress)
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_status(self, status: StreamStatus) -> None:
        """
        Update the status of the operation.
        
        Args:
            status: New status
        """
        self.status = status
        self.updated_at = datetime.now()
    
    def set_error(self, error: str) -> None:
        """
        Set error information and update status.
        
        Args:
            error: Error message
        """
        self.error = error
        self.update_status(StreamStatus.FAILED)
    
    def set_result(self, result: Dict[str, Any]) -> None:
        """
        Set operation result and update status.
        
        Args:
            result: Operation result
        """
        self.result = result
        self.update_status(StreamStatus.COMPLETED)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert operation to dictionary."""
        return {
            "id": self.id,
            "direction": self.direction.value,
            "type": self.type.value,
            "status": self.status.value,
            "source": str(self.source) if self.source else None,
            "destination": str(self.destination) if self.destination else None,
            "backend_name": self.backend_name,
            "content_id": self.content_id,
            "metadata": self.metadata,
            "progress": self.progress.to_dict(),
            "error": self.error,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class StreamProgressCallback:
    """Callback handler for stream progress notifications."""
    
    def __init__(self, 
                callback: Callable[[str, Dict[str, Any]], None], 
                interval: float = DEFAULT_PROGRESS_INTERVAL):
        """
        Initialize the progress callback.
        
        Args:
            callback: Function to call with progress updates
            interval: Minimum interval between callbacks in seconds
        """
        self.callback = callback
        self.interval = interval
        self.last_callback_time = 0
    
    def __call__(self, operation_id: str, progress: StreamProgress) -> None:
        """
        Call the callback if enough time has passed.
        
        Args:
            operation_id: ID of the stream operation
            progress: Current progress information
        """
        now = time.time()
        if now - self.last_callback_time >= self.interval:
            self.callback(operation_id, progress.to_dict())
            self.last_callback_time = now


class ChunkedFileReader:
    """Utility for reading files in chunks with progress tracking."""
    
    def __init__(self, 
                file_or_path: Union[str, BinaryIO], 
                chunk_size: int = DEFAULT_CHUNK_SIZE,
                progress: Optional[StreamProgress] = None):
        """
        Initialize the chunked file reader.
        
        Args:
            file_or_path: File path or file-like object
            chunk_size: Size of chunks in bytes
            progress: Optional progress tracker
        """
        self.chunk_size = chunk_size
        self.progress = progress or StreamProgress()
        self.total_read = 0
        self.eof = False
        
        # Handle different input types
        if isinstance(file_or_path, str):
            # It's a file path
            self.file_size = os.path.getsize(file_or_path)
            self.file = open(file_or_path, 'rb')
            self.should_close = True
        else:
            # It's a file-like object
            self.file = file_or_path
            self.should_close = False
            
            # Try to determine file size
            try:
                # Try to get file size from file object
                if hasattr(self.file, 'seek') and hasattr(self.file, 'tell'):
                    current_pos = self.file.tell()
                    self.file.seek(0, os.SEEK_END)
                    self.file_size = self.file.tell()
                    self.file.seek(current_pos)
                else:
                    self.file_size = 0
            except (IOError, OSError):
                self.file_size = 0
        
        # Update progress with total size if known
        if self.file_size > 0 and self.progress:
            self.progress.total_bytes = self.file_size
    
    def __iter__(self):
        """Return self as iterator."""
        return self
    
    def __next__(self) -> bytes:
        """Get next chunk of data."""
        if self.eof:
            raise StopIteration
        
        chunk = self.file.read(self.chunk_size)
        if not chunk:
            self.eof = True
            if self.should_close:
                self.file.close()
            raise StopIteration
        
        self.total_read += len(chunk)
        
        # Update progress
        if self.progress:
            self.progress.update(self.total_read, self.file_size)
            self.progress.increment_chunks()
        
        return chunk
    
    def close(self) -> None:
        """Close the file if we opened it."""
        if self.should_close and hasattr(self.file, 'close'):
            self.file.close()


class ChunkedFileWriter:
    """Utility for writing files in chunks with progress tracking."""
    
    def __init__(self, 
                file_or_path: Union[str, BinaryIO], 
                total_size: int = 0,
                progress: Optional[StreamProgress] = None):
        """
        Initialize the chunked file writer.
        
        Args:
            file_or_path: File path or file-like object
            total_size: Expected total size in bytes (if known)
            progress: Optional progress tracker
        """
        self.progress = progress or StreamProgress()
        if total_size > 0:
            self.progress.total_bytes = total_size
        
        self.total_written = 0
        
        # Handle different input types
        if isinstance(file_or_path, str):
            # It's a file path
            self.file = open(file_or_path, 'wb')
            self.should_close = True
        else:
            # It's a file-like object
            self.file = file_or_path
            self.should_close = False
    
    def write(self, data: bytes) -> int:
        """
        Write data to the file.
        
        Args:
            data: Bytes to write
            
        Returns:
            Number of bytes written
        """
        bytes_written = self.file.write(data)
        self.total_written += bytes_written
        
        # Update progress
        if self.progress:
            self.progress.update(self.total_written)
            self.progress.increment_chunks()
        
        return bytes_written
    
    def close(self) -> None:
        """Close the file if we opened it."""
        if self.should_close and hasattr(self.file, 'close'):
            self.file.close()


class StreamManager:
    """Manager for streaming operations."""
    
    def __init__(self, backend_registry: Optional[Dict[str, Any]] = None):
        """
        Initialize the stream manager.
        
        Args:
            backend_registry: Dictionary mapping backend names to instances
        """
        self.backend_registry = backend_registry or {}
        self.operations = {}  # store operations by ID
        self.worker_pool = ThreadPoolExecutor(max_workers=10)
        self.lock = threading.RLock()
        
        # For progress callbacks
        self.callbacks = {}  # map operation ID to callback
        
        # For in-memory streams
        self.memory_buffers = {}  # store memory buffers by operation ID
    
    def stream_upload(self,
                     source: Union[str, BinaryIO],
                     backend_name: str,
                     content_id: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None,
                     progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                     progress_interval: float = DEFAULT_PROGRESS_INTERVAL) -> Dict[str, Any]:
        """
        Stream content to a backend.
        
        Args:
            source: File path or file-like object
            backend_name: Name of target backend
            content_id: Optional content ID (generated if not provided)
            metadata: Optional metadata
            progress_callback: Optional function to call with progress updates
            progress_interval: Minimum interval between progress callbacks
            
        Returns:
            Dict with operation details
        """
        # Create operation
        operation = StreamOperation(
            direction=StreamDirection.UPLOAD,
            type=StreamType.FILE if isinstance(source, str) else StreamType.MEMORY,
            source=source,
            backend_name=backend_name,
            content_id=content_id,
            metadata=metadata or {}
        )
        
        # Add to operations dictionary
        with self.lock:
            self.operations[operation.id] = operation
        
        # Set up progress callback if provided
        if progress_callback:
            self.callbacks[operation.id] = StreamProgressCallback(
                progress_callback, progress_interval
            )
        
        # Start background thread for upload
        self.worker_pool.submit(self._perform_upload, operation.id)
        
        # Return operation info
        return {
            "success": True,
            "operation_id": operation.id,
            "status": operation.status.value,
            "details": operation.to_dict()
        }
    
    def stream_download(self,
                       backend_name: str,
                       content_id: str,
                       destination: Optional[Union[str, BinaryIO]] = None,
                       progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                       progress_interval: float = DEFAULT_PROGRESS_INTERVAL) -> Dict[str, Any]:
        """
        Stream content from a backend.
        
        Args:
            backend_name: Name of source backend
            content_id: Content ID to download
            destination: Optional file path or file-like object
            progress_callback: Optional function to call with progress updates
            progress_interval: Minimum interval between progress callbacks
            
        Returns:
            Dict with operation details
        """
        # If no destination provided, create in-memory buffer
        if destination is None:
            buffer = io.BytesIO()
            destination = buffer
            stream_type = StreamType.MEMORY
            
            # Store buffer for later retrieval
            self.memory_buffers[str(uuid.uuid4())] = buffer
        else:
            stream_type = StreamType.FILE if isinstance(destination, str) else StreamType.MEMORY
        
        # Create operation
        operation = StreamOperation(
            direction=StreamDirection.DOWNLOAD,
            type=stream_type,
            destination=destination,
            backend_name=backend_name,
            content_id=content_id
        )
        
        # Add to operations dictionary
        with self.lock:
            self.operations[operation.id] = operation
        
        # Set up progress callback if provided
        if progress_callback:
            self.callbacks[operation.id] = StreamProgressCallback(
                progress_callback, progress_interval
            )
        
        # Start background thread for download
        self.worker_pool.submit(self._perform_download, operation.id)
        
        # Return operation info
        return {
            "success": True,
            "operation_id": operation.id,
            "status": operation.status.value,
            "details": operation.to_dict()
        }
    
    def _perform_upload(self, operation_id: str) -> None:
        """
        Perform the upload operation in background.
        
        Args:
            operation_id: ID of the operation
        """
        with self.lock:
            operation = self.operations.get(operation_id)
            if not operation:
                logger.error(f"Operation {operation_id} not found")
                return
        
        try:
            # Update status
            operation.update_status(StreamStatus.ACTIVE)
            
            # Get the backend
            backend = self.backend_registry.get(operation.backend_name)
            if not backend:
                operation.set_error(f"Backend '{operation.backend_name}' not found")
                return
            
            # Set up progress tracking
            progress = operation.progress
            
            # Create chunked reader
            reader = ChunkedFileReader(operation.source, progress=progress)
            
            # Create temporary file for complete content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                
                try:
                    # Copy all chunks to temporary file
                    for chunk in reader:
                        temp_file.write(chunk)
                        
                        # Call progress callback if registered
                        callback = self.callbacks.get(operation_id)
                        if callback:
                            callback(operation_id, progress)
                    
                    temp_file.flush()
                    
                    # Close temporary file before passing to backend
                    temp_file.close()
                    
                    # Upload complete file to backend
                    with open(temp_path, 'rb') as upload_file:
                        result = backend.add_content(
                            upload_file,
                            metadata=operation.metadata
                        )
                    
                    # Check result
                    if not result.get("success", False):
                        operation.set_error(
                            f"Upload failed: {result.get('error', 'Unknown error')}"
                        )
                        return
                    
                    # Set result
                    operation.set_result(result)
                    
                finally:
                    # Clean up
                    try:
                        os.unlink(temp_path)
                    except (OSError, IOError):
                        pass
            
        except Exception as e:
            logger.error(f"Error in upload operation {operation_id}: {e}")
            operation.set_error(str(e))
        
        finally:
            # Close resources
            reader.close()
            
            # Remove progress callback
            with self.lock:
                if operation_id in self.callbacks:
                    del self.callbacks[operation_id]
    
    def _perform_download(self, operation_id: str) -> None:
        """
        Perform the download operation in background.
        
        Args:
            operation_id: ID of the operation
        """
        with self.lock:
            operation = self.operations.get(operation_id)
            if not operation:
                logger.error(f"Operation {operation_id} not found")
                return
        
        try:
            # Update status
            operation.update_status(StreamStatus.ACTIVE)
            
            # Get the backend
            backend = self.backend_registry.get(operation.backend_name)
            if not backend:
                operation.set_error(f"Backend '{operation.backend_name}' not found")
                return
            
            # Get content from backend
            result = backend.get_content(operation.content_id)
            
            # Check result
            if not result.get("success", False):
                operation.set_error(
                    f"Download failed: {result.get('error', 'Unknown error')}"
                )
                return
            
            # Get content data
            data = result.get("data")
            if not data:
                operation.set_error("No data returned from backend")
                return
            
            # Set up progress tracking
            progress = operation.progress
            progress.total_bytes = len(data)
            
            # Create chunked writer
            writer = ChunkedFileWriter(operation.destination, total_size=len(data), progress=progress)
            
            try:
                # Write data in chunks to avoid memory issues with large files
                position = 0
                while position < len(data):
                    chunk = data[position:position + DEFAULT_CHUNK_SIZE]
                    writer.write(chunk)
                    position += len(chunk)
                    
                    # Call progress callback if registered
                    callback = self.callbacks.get(operation_id)
                    if callback:
                        callback(operation_id, progress)
                
                # Set result
                operation.set_result({
                    "success": True,
                    "content_id": operation.content_id,
                    "backend": operation.backend_name,
                    "size": len(data),
                    "details": result.get("details", {})
                })
                
            finally:
                # Close writer
                writer.close()
            
        except Exception as e:
            logger.error(f"Error in download operation {operation_id}: {e}")
            operation.set_error(str(e))
        
        finally:
            # Remove progress callback
            with self.lock:
                if operation_id in self.callbacks:
                    del self.callbacks[operation_id]
    
    def get_operation(self, operation_id: str) -> Dict[str, Any]:
        """
        Get information about a streaming operation.
        
        Args:
            operation_id: ID of the operation
            
        Returns:
            Dict with operation details
        """
        with self.lock:
            operation = self.operations.get(operation_id)
            if not operation:
                return {
                    "success": False,
                    "error": f"Operation {operation_id} not found"
                }
            
            return {
                "success": True,
                "operation": operation.to_dict()
            }
    
    def cancel_operation(self, operation_id: str) -> Dict[str, Any]:
        """
        Cancel a streaming operation.
        
        Args:
            operation_id: ID of the operation
            
        Returns:
            Dict with operation status
        """
        with self.lock:
            operation = self.operations.get(operation_id)
            if not operation:
                return {
                    "success": False,
                    "error": f"Operation {operation_id} not found"
                }
            
            # Only cancel if not already completed or failed
            if operation.status in [StreamStatus.COMPLETED, StreamStatus.FAILED]:
                return {
                    "success": False,
                    "error": f"Cannot cancel operation with status {operation.status.value}"
                }
            
            # Update status
            operation.update_status(StreamStatus.CANCELED)
            
            # Remove progress callback
            if operation_id in self.callbacks:
                del self.callbacks[operation_id]
            
            return {
                "success": True,
                "operation": operation.to_dict()
            }
    
    def list_operations(self, 
                       status: Optional[Union[StreamStatus, str]] = None,
                       direction: Optional[Union[StreamDirection, str]] = None,
                       limit: int = 100) -> Dict[str, Any]:
        """
        List streaming operations.
        
        Args:
            status: Optional status filter
            direction: Optional direction filter
            limit: Maximum number of operations to return
            
        Returns:
            Dict with list of operations
        """
        # Convert string enums to enum objects
        if isinstance(status, str):
            try:
                status = StreamStatus(status)
            except ValueError:
                pass
        
        if isinstance(direction, str):
            try:
                direction = StreamDirection(direction)
            except ValueError:
                pass
        
        with self.lock:
            # Get all operations
            all_operations = list(self.operations.values())
            
            # Apply filters
            if status:
                all_operations = [op for op in all_operations if op.status == status]
            
            if direction:
                all_operations = [op for op in all_operations if op.direction == direction]
            
            # Sort by creation time (newest first)
            all_operations.sort(key=lambda op: op.created_at, reverse=True)
            
            # Apply limit
            operations = all_operations[:limit]
            
            return {
                "success": True,
                "operations": [op.to_dict() for op in operations],
                "count": len(operations),
                "total": len(all_operations)
            }
    
    def cleanup_completed(self, max_age: int = 3600) -> Dict[str, Any]:
        """
        Remove completed operations older than specified age.
        
        Args:
            max_age: Maximum age in seconds
            
        Returns:
            Dict with cleanup results
        """
        now = datetime.now()
        removed_count = 0
        
        with self.lock:
            operations_to_remove = []
            
            for op_id, operation in self.operations.items():
                # Only remove completed, failed, or canceled operations
                if operation.status in [StreamStatus.COMPLETED, StreamStatus.FAILED, StreamStatus.CANCELED]:
                    # Check age
                    age = (now - operation.updated_at).total_seconds()
                    if age > max_age:
                        operations_to_remove.append(op_id)
            
            # Remove operations
            for op_id in operations_to_remove:
                del self.operations[op_id]
                
                # Remove callbacks if any
                if op_id in self.callbacks:
                    del self.callbacks[op_id]
                
                # Remove memory buffers if any
                if op_id in self.memory_buffers:
                    del self.memory_buffers[op_id]
                
                removed_count += 1
            
            return {
                "success": True,
                "removed_count": removed_count,
                "remaining_count": len(self.operations)
            }
    
    def close(self) -> None:
        """Clean up resources."""
        self.worker_pool.shutdown(wait=False)


class ThreadPoolExecutor:
    """Simple thread pool executor for background tasks."""
    
    def __init__(self, max_workers: int = 10):
        """
        Initialize the thread pool.
        
        Args:
            max_workers: Maximum number of worker threads
        """
        self.max_workers = max_workers
        self.workers = []
        self.queue = queue.Queue()
        self.shutdown_flag = threading.Event()
        
        # Start worker threads
        for _ in range(max_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self.workers.append(worker)
    
    def submit(self, func: Callable, *args, **kwargs) -> None:
        """
        Submit a task to the thread pool.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
        """
        self.queue.put((func, args, kwargs))
    
    def _worker_loop(self) -> None:
        """Worker thread loop."""
        while not self.shutdown_flag.is_set():
            try:
                # Get task with timeout to check shutdown flag periodically
                func, args, kwargs = self.queue.get(timeout=0.5)
                try:
                    # Execute the task
                    func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in thread pool task: {e}")
                finally:
                    # Mark task as done
                    self.queue.task_done()
            except queue.Empty:
                # Queue is empty, check shutdown flag again
                pass
    
    def shutdown(self, wait: bool = True) -> None:
        """
        Shut down the thread pool.
        
        Args:
            wait: Whether to wait for pending tasks to complete
        """
        self.shutdown_flag.set()
        
        if wait:
            # Wait for all tasks to complete
            self.queue.join()
        
        # Wait for all threads to finish
        for worker in self.workers:
            worker.join(timeout=1.0)