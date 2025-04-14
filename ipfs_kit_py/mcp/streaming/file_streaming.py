"""
Optimized file streaming for MCP server.

This module implements efficient streaming operations for large files,
addressing the Optimized File Streaming requirements in the Streaming Operations
section of the MCP roadmap.
"""

import asyncio
import logging
import os
import time
import threading
import tempfile
import hashlib
from typing import Dict, Any, Optional, BinaryIO, List, Union, Callable, AsyncGenerator, Tuple
from enum import Enum
import json
from pathlib import Path
import uuid
import io

# Import the WebSocket notification system for progress updates
from .websocket_notifications import get_ws_manager, EventType

# Configure logger
logger = logging.getLogger(__name__)

# Constants for chunk size and buffer management
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1MB chunks
MAX_CONCURRENT_CHUNKS = 5  # Number of chunks to process concurrently
MAX_MEMORY_BUFFER = 50 * 1024 * 1024  # 50MB max memory buffer


class StreamingOperationType(str, Enum):
    """Types of streaming operations."""
    UPLOAD = "upload"
    DOWNLOAD = "download"
    PINNING = "pinning"
    REPLICATION = "replication"
    MIGRATION = "migration"


class StreamingStatus(str, Enum):
    """Status of a streaming operation."""
    CREATED = "created"
    QUEUED = "queued"
    STARTED = "started" 
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    PAUSED = "paused"


class StreamingOperation:
    """
    Represents a streaming operation (upload, download, etc.) with tracking capabilities.
    """
    
    def __init__(
        self,
        operation_type: StreamingOperationType,
        source: Union[str, BinaryIO],
        identifier: Optional[str] = None,
        target: Optional[Union[str, BinaryIO]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        backend: Optional[str] = None,
        total_size: Optional[int] = None,
    ):
        """
        Initialize a streaming operation.
        
        Args:
            operation_type: Type of operation (upload, download, etc.)
            source: Source of data (file path, file-like object, CID)
            identifier: Optional identifier for the operation
            target: Optional target (file path, file-like object)
            metadata: Optional metadata for the operation
            chunk_size: Size of chunks for processing
            backend: Optional backend identifier
            total_size: Optional total size of the data
        """
        self.operation_id = identifier or str(uuid.uuid4())
        self.operation_type = operation_type
        self.source = source
        self.target = target
        self.metadata = metadata or {}
        self.chunk_size = chunk_size
        self.backend = backend
        self.total_size = total_size
        
        # Status tracking
        self.status = StreamingStatus.CREATED
        self.start_time = None
        self.end_time = None
        self.last_update_time = time.time()
        
        # Progress tracking
        self.bytes_processed = 0
        self.chunks_processed = 0
        self.total_chunks = None
        if total_size is not None:
            self.total_chunks = (total_size + chunk_size - 1) // chunk_size
        
        # Result data
        self.result = None
        self.error = None
        
        # For temporary file management
        self.temp_files = []
        
        # Performance metrics
        self.throughput_samples = []
        self.last_throughput_time = None
        self.last_throughput_bytes = 0
        
        logger.info(f"Created {operation_type.value} operation: {self.operation_id}")
    
    def start(self):
        """Mark the operation as started."""
        self.status = StreamingStatus.STARTED
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.last_throughput_time = time.time()
        logger.info(f"Started {self.operation_type.value} operation: {self.operation_id}")
        
        # Send notification about operation start
        self._send_notification(EventType.OPERATION_STARTED)
    
    def update_progress(self, bytes_processed: int, force_notification: bool = False):
        """
        Update the progress of the operation.
        
        Args:
            bytes_processed: Number of bytes processed in this update
            force_notification: Whether to force sending a notification
        """
        now = time.time()
        self.bytes_processed += bytes_processed
        self.chunks_processed = (self.bytes_processed + self.chunk_size - 1) // self.chunk_size
        self.last_update_time = now
        
        # Calculate throughput
        if self.last_throughput_time:
            time_diff = now - self.last_throughput_time
            if time_diff >= 1.0:  # Only calculate throughput after at least 1 second
                bytes_diff = self.bytes_processed - self.last_throughput_bytes
                throughput = bytes_diff / time_diff  # bytes per second
                self.throughput_samples.append(throughput)
                
                # Keep only last 10 samples for moving average
                if len(self.throughput_samples) > 10:
                    self.throughput_samples.pop(0)
                
                self.last_throughput_time = now
                self.last_throughput_bytes = self.bytes_processed
        
        # Update status
        if self.status != StreamingStatus.IN_PROGRESS:
            self.status = StreamingStatus.IN_PROGRESS
        
        # Send notification about progress
        # Limit notifications to avoid flooding (send every ~5% progress or at least every 3 seconds)
        should_notify = force_notification
        
        if self.total_size:
            progress_percent = (self.bytes_processed / self.total_size) * 100
            # Send notification every 5% or if it's been 3+ seconds since last notification
            if progress_percent % 5 < (bytes_processed / self.total_size) * 100 or (now - self.last_update_time) > 3:
                should_notify = True
        else:
            # If we don't know total size, send notification every 3 seconds
            if (now - self.last_update_time) > 3:
                should_notify = True
        
        if should_notify:
            self._send_notification(EventType.OPERATION_PROGRESS)
    
    def complete(self, result: Optional[Any] = None):
        """
        Mark the operation as completed.
        
        Args:
            result: Optional result data
        """
        self.status = StreamingStatus.COMPLETED
        self.end_time = time.time()
        self.result = result
        logger.info(f"Completed {self.operation_type.value} operation: {self.operation_id}")
        
        # Clean up any temporary files
        self._cleanup_temp_files()
        
        # Send notification about completion
        self._send_notification(EventType.OPERATION_COMPLETED)
    
    def fail(self, error: Union[str, Exception]):
        """
        Mark the operation as failed.
        
        Args:
            error: Error message or exception
        """
        self.status = StreamingStatus.FAILED
        self.end_time = time.time()
        self.error = str(error)
        logger.error(f"Failed {self.operation_type.value} operation: {self.operation_id} - {self.error}")
        
        # Clean up any temporary files
        self._cleanup_temp_files()
        
        # Send notification about failure
        self._send_notification(EventType.OPERATION_FAILED)
    
    def cancel(self):
        """Cancel the operation."""
        self.status = StreamingStatus.CANCELED
        self.end_time = time.time()
        logger.info(f"Canceled {self.operation_type.value} operation: {self.operation_id}")
        
        # Clean up any temporary files
        self._cleanup_temp_files()
        
        # Send notification about cancellation
        self._send_notification(EventType.OPERATION_FAILED, {"reason": "canceled"})
    
    def add_temp_file(self, file_path: str):
        """
        Register a temporary file for cleanup.
        
        Args:
            file_path: Path to temporary file
        """
        self.temp_files.append(file_path)
    
    def _cleanup_temp_files(self):
        """Clean up temporary files."""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.debug(f"Removed temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {file_path}: {e}")
        
        self.temp_files = []
    
    def get_current_throughput(self) -> float:
        """
        Get the current throughput in bytes per second.
        
        Returns:
            Current throughput (bytes/second)
        """
        if not self.throughput_samples:
            return 0.0
        
        # Return moving average of throughput samples
        return sum(self.throughput_samples) / len(self.throughput_samples)
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get the current progress information.
        
        Returns:
            Dictionary with progress information
        """
        duration = 0.0
        if self.start_time:
            if self.end_time:
                duration = self.end_time - self.start_time
            else:
                duration = time.time() - self.start_time
        
        progress_percent = 0.0
        estimated_remaining = None
        
        if self.total_size and self.total_size > 0:
            progress_percent = min(100.0, (self.bytes_processed / self.total_size) * 100)
            
            # Calculate estimated time remaining
            if progress_percent > 0 and self.status == StreamingStatus.IN_PROGRESS:
                throughput = self.get_current_throughput()
                if throughput > 0:
                    bytes_remaining = self.total_size - self.bytes_processed
                    estimated_remaining = bytes_remaining / throughput  # seconds
        
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type.value,
            "status": self.status.value,
            "bytes_processed": self.bytes_processed,
            "total_size": self.total_size,
            "progress_percent": progress_percent,
            "chunks_processed": self.chunks_processed,
            "total_chunks": self.total_chunks,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": duration,
            "throughput_bps": self.get_current_throughput(),
            "estimated_remaining_seconds": estimated_remaining,
            "backend": self.backend,
            "result": self.result,
            "error": self.error
        }
    
    def _send_notification(self, event_type: EventType, additional_data: Optional[Dict[str, Any]] = None):
        """
        Send a notification about this operation.
        
        Args:
            event_type: Type of event to send
            additional_data: Optional additional data to include
        """
        try:
            ws_manager = get_ws_manager()
            notification_data = {
                "type": event_type,
                "operation": {
                    "id": self.operation_id,
                    "type": self.operation_type.value,
                    "status": self.status.value,
                },
                "timestamp": time.time(),
                "progress": self.get_progress()
            }
            
            if additional_data:
                notification_data.update(additional_data)
            
            ws_manager.notify("operations", notification_data)
        except Exception as e:
            logger.error(f"Failed to send operation notification: {e}")


class StreamingManager:
    """
    Manages streaming operations for the MCP server.
    
    This class implements the optimized file streaming capabilities required
    in the Streaming Operations section of the MCP roadmap.
    """
    
    def __init__(self):
        """Initialize the streaming manager."""
        self.operations: Dict[str, StreamingOperation] = {}
        self.lock = threading.RLock()
        self.temp_dir = tempfile.gettempdir()
        self.upload_handlers: Dict[str, Callable] = {}
        self.download_handlers: Dict[str, Callable] = {}
        self.pinning_handlers: Dict[str, Callable] = {}
    
    def register_upload_handler(self, backend: str, handler: Callable):
        """
        Register a handler for uploads to a specific backend.
        
        Args:
            backend: Backend identifier
            handler: Upload handler function
        """
        self.upload_handlers[backend] = handler
        logger.info(f"Registered upload handler for backend: {backend}")
    
    def register_download_handler(self, backend: str, handler: Callable):
        """
        Register a handler for downloads from a specific backend.
        
        Args:
            backend: Backend identifier
            handler: Download handler function
        """
        self.download_handlers[backend] = handler
        logger.info(f"Registered download handler for backend: {backend}")
    
    def register_pinning_handler(self, backend: str, handler: Callable):
        """
        Register a handler for pinning operations on a specific backend.
        
        Args:
            backend: Backend identifier
            handler: Pinning handler function
        """
        self.pinning_handlers[backend] = handler
        logger.info(f"Registered pinning handler for backend: {backend}")
    
    def create_upload_operation(
        self,
        source: Union[str, BinaryIO],
        backend: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        operation_id: Optional[str] = None
    ) -> StreamingOperation:
        """
        Create a new upload operation.
        
        Args:
            source: Source file path or file-like object
            backend: Backend to upload to
            metadata: Optional metadata for the upload
            chunk_size: Size of chunks for uploading
            operation_id: Optional identifier for the operation
            
        Returns:
            StreamingOperation instance
        """
        # Determine total size if possible
        total_size = None
        if isinstance(source, str) and os.path.isfile(source):
            total_size = os.path.getsize(source)
        elif hasattr(source, 'seek') and hasattr(source, 'tell'):
            # Try to determine size from file-like object
            try:
                current_pos = source.tell()
                source.seek(0, os.SEEK_END)
                total_size = source.tell()
                source.seek(current_pos)  # Restore position
            except (OSError, IOError):
                # Cannot determine size
                pass
        
        # Create the operation
        operation = StreamingOperation(
            operation_type=StreamingOperationType.UPLOAD,
            source=source,
            identifier=operation_id,
            metadata=metadata,
            chunk_size=chunk_size,
            backend=backend,
            total_size=total_size
        )
        
        # Store the operation
        with self.lock:
            self.operations[operation.operation_id] = operation
        
        return operation
    
    def create_download_operation(
        self,
        source_cid: str,
        backend: str,
        target: Optional[Union[str, BinaryIO]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        operation_id: Optional[str] = None,
        total_size: Optional[int] = None
    ) -> StreamingOperation:
        """
        Create a new download operation.
        
        Args:
            source_cid: CID of content to download
            backend: Backend to download from
            target: Optional target file path or file-like object
            metadata: Optional metadata for the download
            chunk_size: Size of chunks for downloading
            operation_id: Optional identifier for the operation
            total_size: Optional total size of the content
            
        Returns:
            StreamingOperation instance
        """
        # Create the operation
        operation = StreamingOperation(
            operation_type=StreamingOperationType.DOWNLOAD,
            source=source_cid,
            target=target,
            identifier=operation_id,
            metadata=metadata,
            chunk_size=chunk_size,
            backend=backend,
            total_size=total_size
        )
        
        # Store the operation
        with self.lock:
            self.operations[operation.operation_id] = operation
        
        return operation
    
    def create_pinning_operation(
        self,
        cid: str,
        backend: str,
        metadata: Optional[Dict[str, Any]] = None,
        operation_id: Optional[str] = None,
        total_size: Optional[int] = None
    ) -> StreamingOperation:
        """
        Create a new pinning operation.
        
        Args:
            cid: CID to pin
            backend: Backend to pin on
            metadata: Optional metadata for the pinning
            operation_id: Optional identifier for the operation
            total_size: Optional total size of the content
            
        Returns:
            StreamingOperation instance
        """
        # Create the operation
        operation = StreamingOperation(
            operation_type=StreamingOperationType.PINNING,
            source=cid,
            identifier=operation_id,
            metadata=metadata,
            backend=backend,
            total_size=total_size
        )
        
        # Store the operation
        with self.lock:
            self.operations[operation.operation_id] = operation
        
        return operation
    
    def get_operation(self, operation_id: str) -> Optional[StreamingOperation]:
        """
        Get an operation by ID.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            StreamingOperation instance or None if not found
        """
        with self.lock:
            return self.operations.get(operation_id)
    
    def list_operations(
        self,
        operation_type: Optional[StreamingOperationType] = None,
        status: Optional[StreamingStatus] = None,
        backend: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List operations with optional filtering.
        
        Args:
            operation_type: Optional type filter
            status: Optional status filter
            backend: Optional backend filter
            limit: Maximum number of operations to return
            offset: Offset for pagination
            
        Returns:
            List of operation progress dictionaries
        """
        with self.lock:
            # Apply filters
            filtered_ops = self.operations.values()
            
            if operation_type:
                filtered_ops = [op for op in filtered_ops if op.operation_type == operation_type]
            
            if status:
                filtered_ops = [op for op in filtered_ops if op.status == status]
            
            if backend:
                filtered_ops = [op for op in filtered_ops if op.backend == backend]
            
            # Sort by start time (newest first)
            sorted_ops = sorted(
                filtered_ops,
                key=lambda op: op.start_time or 0,
                reverse=True
            )
            
            # Apply pagination
            paginated_ops = sorted_ops[offset:offset+limit]
            
            # Convert to progress dictionaries
            return [op.get_progress() for op in paginated_ops]
    
    def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel an operation.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            operation = self.operations.get(operation_id)
            if not operation:
                return False
            
            if operation.status in [StreamingStatus.COMPLETED, StreamingStatus.FAILED, StreamingStatus.CANCELED]:
                return False
            
            operation.cancel()
            return True
    
    def cleanup_old_operations(self, max_age_seconds: int = 86400) -> int:
        """
        Remove old completed/failed operations to free up memory.
        
        Args:
            max_age_seconds: Maximum age of operations to keep
            
        Returns:
            Number of operations removed
        """
        now = time.time()
        removed_count = 0
        
        with self.lock:
            for operation_id in list(self.operations.keys()):
                operation = self.operations[operation_id]
                
                # Check if operation is completed or failed and is old enough
                if (operation.status in [StreamingStatus.COMPLETED, StreamingStatus.FAILED, StreamingStatus.CANCELED] and
                    operation.end_time and (now - operation.end_time) > max_age_seconds):
                    # Remove the operation
                    del self.operations[operation_id]
                    removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old operations")
        
        return removed_count
    
    async def stream_upload(
        self,
        operation: StreamingOperation,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Stream an upload operation.
        
        Args:
            operation: Upload operation to stream
            callback: Optional callback for progress updates
            
        Returns:
            Result of the upload
        """
        if operation.status != StreamingStatus.CREATED:
            raise ValueError(f"Operation {operation.operation_id} is already in progress or completed")
        
        if operation.operation_type != StreamingOperationType.UPLOAD:
            raise ValueError(f"Operation {operation.operation_id} is not an upload operation")
        
        # Check if handler exists for this backend
        if operation.backend not in self.upload_handlers:
            operation.fail(f"No upload handler registered for backend: {operation.backend}")
            return {"success": False, "error": f"No upload handler for backend: {operation.backend}"}
        
        # Start the operation
        operation.start()
        
        # Create temporary file if source is file-like object but not a file path
        # This helps with handlers that require file paths
        temp_file_path = None
        source = operation.source
        
        try:
            if not isinstance(source, str) and hasattr(source, 'read'):
                # Source is a file-like object, create a temporary file
                fd, temp_file_path = tempfile.mkstemp(prefix=f"mcp_upload_{operation.operation_id}_", dir=self.temp_dir)
                operation.add_temp_file(temp_file_path)
                
                with os.fdopen(fd, 'wb') as temp_file:
                    # Stream the content to the temporary file in chunks
                    chunk = source.read(operation.chunk_size)
                    while chunk:
                        temp_file.write(chunk)
                        operation.update_progress(len(chunk))
                        if callback:
                            callback(operation.get_progress())
                        chunk = source.read(operation.chunk_size)
                
                source = temp_file_path
            
            # Get the handler for this backend
            handler = self.upload_handlers[operation.backend]
            
            # Call the handler
            result = await handler(
                source=source,
                metadata=operation.metadata,
                progress_callback=lambda bytes_processed: self._update_operation_progress(operation, bytes_processed, callback)
            )
            
            # Process the result
            if result.get("success"):
                operation.complete(result)
                return result
            else:
                operation.fail(result.get("error", "Unknown error"))
                return result
                
        except Exception as e:
            logger.exception(f"Error in upload operation {operation.operation_id}")
            operation.fail(str(e))
            return {"success": False, "error": str(e)}
    
    async def stream_download(
        self,
        operation: StreamingOperation,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Stream a download operation.
        
        Args:
            operation: Download operation to stream
            callback: Optional callback for progress updates
            
        Returns:
            Result of the download
        """
        if operation.status != StreamingStatus.CREATED:
            raise ValueError(f"Operation {operation.operation_id} is already in progress or completed")
        
        if operation.operation_type != StreamingOperationType.DOWNLOAD:
            raise ValueError(f"Operation {operation.operation_id} is not a download operation")
        
        # Check if handler exists for this backend
        if operation.backend not in self.download_handlers:
            operation.fail(f"No download handler registered for backend: {operation.backend}")
            return {"success": False, "error": f"No download handler for backend: {operation.backend}"}
        
        # Start the operation
        operation.start()
        
        # Create temporary file if target is not specified or is a file-like object
        temp_file_path = None
        target = operation.target
        
        try:
            if target is None:
                # No target specified, create a temporary file
                fd, temp_file_path = tempfile.mkstemp(prefix=f"mcp_download_{operation.operation_id}_", dir=self.temp_dir)
                operation.add_temp_file(temp_file_path)
                os.close(fd)
                target = temp_file_path
            
            # Get the handler for this backend
            handler = self.download_handlers[operation.backend]
            
            # Call the handler
            result = await handler(
                cid=operation.source,
                target=target,
                metadata=operation.metadata,
                progress_callback=lambda bytes_processed: self._update_operation_progress(operation, bytes_processed, callback)
            )
            
            # Process the result
            if result.get("success"):
                # If download was to a temporary file, read the content
                if temp_file_path and os.path.exists(temp_file_path):
                    with open(temp_file_path, 'rb') as f:
                        result["data"] = f.read()
                
                operation.complete(result)
                return result
            else:
                operation.fail(result.get("error", "Unknown error"))
                return result
                
        except Exception as e:
            logger.exception(f"Error in download operation {operation.operation_id}")
            operation.fail(str(e))
            return {"success": False, "error": str(e)}
    
    async def stream_pin(
        self,
        operation: StreamingOperation,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Stream a pinning operation.
        
        Args:
            operation: Pinning operation to stream
            callback: Optional callback for progress updates
            
        Returns:
            Result of the pinning
        """
        if operation.status != StreamingStatus.CREATED:
            raise ValueError(f"Operation {operation.operation_id} is already in progress or completed")
        
        if operation.operation_type != StreamingOperationType.PINNING:
            raise ValueError(f"Operation {operation.operation_id} is not a pinning operation")
        
        # Check if handler exists for this backend
        if operation.backend not in self.pinning_handlers:
            operation.fail(f"No pinning handler registered for backend: {operation.backend}")
            return {"success": False, "error": f"No pinning handler for backend: {operation.backend}"}
        
        # Start the operation
        operation.start()
        
        try:
            # Get the handler for this backend
            handler = self.pinning_handlers[operation.backend]
            
            # Call the handler
            result = await handler(
                cid=operation.source,
                metadata=operation.metadata,
                progress_callback=lambda bytes_processed: self._update_operation_progress(operation, bytes_processed, callback)
            )
            
            # Process the result
            if result.get("success"):
                operation.complete(result)
                return result
            else:
                operation.fail(result.get("error", "Unknown error"))
                return result
                
        except Exception as e:
            logger.exception(f"Error in pinning operation {operation.operation_id}")
            operation.fail(str(e))
            return {"success": False, "error": str(e)}
    
    def _update_operation_progress(
        self,
        operation: StreamingOperation,
        bytes_processed: int,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        Update an operation's progress and call the callback if provided.
        
        Args:
            operation: Operation to update
            bytes_processed: Number of bytes processed
            callback: Optional callback to call with progress information
        """
        operation.update_progress(bytes_processed)
        if callback:
            callback(operation.get_progress())


# Helper functions for chunked file processing
async def chunk_file_generator(
    file_path: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE
) -> AsyncGenerator[Tuple[bytes, int, int], None]:
    """
    Generate chunks from a file asynchronously.
    
    Args:
        file_path: Path to the file
        chunk_size: Size of each chunk
        
    Yields:
        Tuple of (chunk_data, chunk_index, total_chunks)
    """
    file_size = os.path.getsize(file_path)
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    
    with open(file_path, 'rb') as f:
        chunk_index = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            
            yield chunk, chunk_index, total_chunks
            chunk_index += 1
            
            # Yield control to event loop periodically
            await asyncio.sleep(0)


async def process_file_chunks(
    file_path: str,
    chunk_processor: Callable[[bytes, int, int], Awaitable[Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_concurrent: int = MAX_CONCURRENT_CHUNKS
) -> List[Any]:
    """
    Process file chunks concurrently with limited concurrency.
    
    Args:
        file_path: Path to the file
        chunk_processor: Async function to process each chunk
        chunk_size: Size of each chunk
        max_concurrent: Maximum number of chunks to process concurrently
        
    Returns:
        List of results from each chunk processor
    """
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_chunk(chunk: bytes, index: int, total: int) -> Any:
        async with semaphore:
            return await chunk_processor(chunk, index, total)
    
    # Create tasks for each chunk
    tasks = []
    async for chunk, index, total in chunk_file_generator(file_path, chunk_size):
        task = asyncio.create_task(process_chunk(chunk, index, total))
        tasks.append(task)
    
    # Wait for all tasks to complete
    for result in await asyncio.gather(*tasks):
        results.append(result)
    
    return results


# Singleton instance
_streaming_manager = None

def get_streaming_manager() -> StreamingManager:
    """
    Get the global streaming manager instance.
    
    Returns:
        StreamingManager instance
    """
    global _streaming_manager
    if _streaming_manager is None:
        _streaming_manager = StreamingManager()
    return _streaming_manager
