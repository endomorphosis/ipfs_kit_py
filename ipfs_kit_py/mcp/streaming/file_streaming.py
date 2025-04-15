"""
File streaming implementation for MCP server.

This module implements the optimized file streaming capabilities
mentioned in the roadmap, including chunked processing, memory-optimized
streaming downloads, and background pinning operations.
"""

import os
import sys
import time
import uuid
import logging
import asyncio
import tempfile
from typing import Dict, List, Optional, Any, Tuple, Union, Callable, BinaryIO
from pathlib import Path
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

# Configure logger
logger = logging.getLogger(__name__)

@dataclass
class ChunkInfo:
    """Information about a file chunk."""
    index: int
    size: int
    offset: int
    hash: str
    cid: Optional[str] = None
    status: str = "pending"
    retries: int = 0

@dataclass
class ProgressInfo:
    """Information about upload/download progress."""
    total_size: int
    processed_size: int = 0
    total_chunks: int = 0
    processed_chunks: int = 0
    start_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    completed: bool = False
    error: Optional[str] = None
    
    @property
    def progress_percentage(self) -> float:
        """Get progress as a percentage."""
        if self.total_size == 0:
            return 100.0
        return (self.processed_size / self.total_size) * 100.0
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time
    
    @property
    def average_speed(self) -> float:
        """Get average processing speed in bytes per second."""
        elapsed = self.elapsed_time
        if elapsed == 0:
            return 0.0
        return self.processed_size / elapsed
    
    @property
    def estimated_time_remaining(self) -> float:
        """Get estimated time remaining in seconds."""
        if self.completed or self.total_size == 0:
            return 0.0
        
        if self.processed_size == 0:
            return float('inf')
        
        speed = self.average_speed
        if speed == 0:
            return float('inf')
        
        remaining_size = self.total_size - self.processed_size
        return remaining_size / speed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_size": self.total_size,
            "processed_size": self.processed_size,
            "total_chunks": self.total_chunks,
            "processed_chunks": self.processed_chunks,
            "progress_percentage": self.progress_percentage,
            "elapsed_time": self.elapsed_time,
            "average_speed": self.average_speed,
            "estimated_time_remaining": self.estimated_time_remaining,
            "completed": self.completed,
            "error": self.error
        }

class ProgressTracker:
    """Track progress of streaming operations."""
    
    def __init__(self, operation_id: str = None):
        """
        Initialize progress tracker.
        
        Args:
            operation_id: Unique identifier for the operation
        """
        self.operation_id = operation_id or str(uuid.uuid4())
        self.progress_info = ProgressInfo(total_size=0)
        self._callbacks: List[Callable[[ProgressInfo], None]] = []
    
    def register_callback(self, callback: Callable[[ProgressInfo], None]):
        """
        Register a callback function for progress updates.
        
        Args:
            callback: Function to call with progress updates
        """
        self._callbacks.append(callback)
    
    def initialize(self, total_size: int, total_chunks: int = 0):
        """
        Initialize progress tracking with total size.
        
        Args:
            total_size: Total size in bytes
            total_chunks: Total number of chunks
        """
        self.progress_info = ProgressInfo(
            total_size=total_size,
            total_chunks=total_chunks
        )
        self._notify_update()
    
    def update(self, processed_size: int, processed_chunks: int = 0):
        """
        Update progress tracking.
        
        Args:
            processed_size: Size processed so far in bytes
            processed_chunks: Number of chunks processed
        """
        self.progress_info.processed_size = processed_size
        self.progress_info.processed_chunks = processed_chunks
        self.progress_info.last_update = time.time()
        self._notify_update()
    
    def increment(self, size_increment: int, chunks_increment: int = 0):
        """
        Increment progress tracking by specified amount.
        
        Args:
            size_increment: Additional size processed in bytes
            chunks_increment: Additional chunks processed
        """
        self.progress_info.processed_size += size_increment
        self.progress_info.processed_chunks += chunks_increment
        self.progress_info.last_update = time.time()
        self._notify_update()
    
    def complete(self):
        """Mark operation as completed."""
        self.progress_info.completed = True
        self.progress_info.processed_size = self.progress_info.total_size
        self.progress_info.processed_chunks = self.progress_info.total_chunks
        self.progress_info.last_update = time.time()
        self._notify_update()
    
    def fail(self, error: str):
        """
        Mark operation as failed.
        
        Args:
            error: Error message
        """
        self.progress_info.error = error
        self.progress_info.last_update = time.time()
        self._notify_update()
    
    def _notify_update(self):
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(self.progress_info)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get current progress information.
        
        Returns:
            Dictionary with progress information
        """
        return {
            "operation_id": self.operation_id,
            "progress": self.progress_info.to_dict()
        }


class ChunkedFileUploader:
    """
    Chunked file uploader for efficient large file uploads.
    
    This class implements chunked file uploads with configurable
    chunk size and concurrency, as mentioned in the roadmap.
    """
    
    def __init__(self, chunk_size: int = 1024 * 1024, max_concurrent: int = 5, 
                 max_retries: int = 3):
        """
        Initialize the chunked file uploader.
        
        Args:
            chunk_size: Size of each chunk in bytes
            max_concurrent: Maximum number of concurrent uploads
            max_retries: Maximum number of retries for failed chunks
        """
        self.chunk_size = chunk_size
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
    
    async def upload(self, file_path: Union[str, Path], destination: Any, 
                    progress_tracker: Optional[ProgressTracker] = None) -> Dict[str, Any]:
        """
        Upload a file in chunks.
        
        Args:
            file_path: Path to the file to upload
            destination: Destination object with add_chunk method
            progress_tracker: Progress tracker for this operation
            
        Returns:
            Dictionary with upload result
        """
        file_path = Path(file_path)
        
        # Ensure file exists
        if not file_path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        
        # Get file size
        file_size = file_path.stat().st_size
        
        # Create progress tracker if not provided
        progress_tracker = progress_tracker or ProgressTracker()
        
        # Calculate number of chunks
        num_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        
        # Initialize progress tracking
        progress_tracker.initialize(file_size, num_chunks)
        
        # Prepare chunks
        chunks: List[ChunkInfo] = []
        for i in range(num_chunks):
            offset = i * self.chunk_size
            size = min(self.chunk_size, file_size - offset)
            
            # Calculate hash for this chunk
            chunk_hash = f"chunk_{i}_{file_path.name}_{size}"
            
            chunks.append(ChunkInfo(
                index=i,
                size=size,
                offset=offset,
                hash=chunk_hash
            ))
        
        # Create semaphore for controlling concurrency
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Define chunk upload function
        async def upload_chunk(chunk: ChunkInfo):
            async with semaphore:
                chunk.status = "uploading"
                
                try:
                    # Read chunk data
                    with open(file_path, "rb") as f:
                        f.seek(chunk.offset)
                        data = f.read(chunk.size)
                    
                    # Upload chunk
                    result = await destination.add_chunk(data)
                    
                    if result.get("success", False):
                        chunk.status = "uploaded"
                        chunk.cid = result.get("chunk_id")
                        progress_tracker.increment(chunk.size, 1)
                        return True
                    else:
                        chunk.status = "failed"
                        chunk.retries += 1
                        logger.warning(f"Chunk {chunk.index} upload failed: {result.get('error')}")
                        return False
                except Exception as e:
                    chunk.status = "failed"
                    chunk.retries += 1
                    logger.error(f"Error uploading chunk {chunk.index}: {e}")
                    return False
        
        # Upload chunks with retry logic
        for attempt in range(self.max_retries + 1):
            # Get chunks that need uploading
            pending_chunks = [chunk for chunk in chunks if chunk.status != "uploaded" and chunk.retries <= attempt]
            
            if not pending_chunks:
                break
            
            # Upload chunks concurrently
            tasks = [upload_chunk(chunk) for chunk in pending_chunks]
            results = await asyncio.gather(*tasks)
            
            # Check if all chunks uploaded successfully
            if all(results):
                break
        
        # Check for any failed chunks
        failed_chunks = [chunk for chunk in chunks if chunk.status != "uploaded"]
        if failed_chunks:
            progress_tracker.fail(f"Failed to upload {len(failed_chunks)} chunks")
            return {
                "success": False, 
                "error": f"Failed to upload {len(failed_chunks)} chunks",
                "failed_chunks": [chunk.index for chunk in failed_chunks]
            }
        
        # Finalize upload
        try:
            # Call finalize method on destination
            chunk_ids = [chunk.cid for chunk in chunks]
            result = await destination.finalize(chunk_ids)
            
            if result.get("success", False):
                progress_tracker.complete()
                return {
                    "success": True,
                    "cid": result.get("cid"),
                    "size": file_size,
                    "chunks": len(chunks),
                    "total_size": result.get("total_size", file_size)
                }
            else:
                progress_tracker.fail(f"Failed to finalize upload: {result.get('error')}")
                return {
                    "success": False,
                    "error": f"Failed to finalize upload: {result.get('error')}"
                }
                
        except Exception as e:
            progress_tracker.fail(f"Error finalizing upload: {e}")
            return {
                "success": False,
                "error": f"Error finalizing upload: {e}"
            }


class StreamingDownloader:
    """
    Streaming downloader for memory-efficient downloads.
    
    This class implements memory-optimized streaming downloads
    as mentioned in the roadmap.
    """
    
    def __init__(self, chunk_size: int = 1024 * 1024, max_concurrent: int = 3,
                max_retries: int = 3):
        """
        Initialize the streaming downloader.
        
        Args:
            chunk_size: Size of each chunk in bytes
            max_concurrent: Maximum number of concurrent downloads
            max_retries: Maximum number of retries for failed chunks
        """
        self.chunk_size = chunk_size
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
    
    @asynccontextmanager
    async def stream(self, source: Any, identifier: str, 
                    progress_tracker: Optional[ProgressTracker] = None):
        """
        Stream content from source.
        
        Args:
            source: Source object with get_content method
            identifier: Content identifier
            progress_tracker: Progress tracker
            
        Yields:
            Async generator yielding content chunks
        """
        # Create progress tracker if not provided
        progress_tracker = progress_tracker or ProgressTracker()
        
        # Get content info
        try:
            info_result = await source.get_info(identifier)
            if not info_result.get("success", False):
                progress_tracker.fail(f"Failed to get content info: {info_result.get('error')}")
                yield None
                return
            
            content_size = info_result.get("size", 0)
            
            # Initialize progress tracking
            progress_tracker.initialize(content_size)
            
            # Create and yield the generator
            async def content_generator():
                offset = 0
                
                while offset < content_size:
                    chunk_size = min(self.chunk_size, content_size - offset)
                    
                    # Try to get chunk with retries
                    for attempt in range(self.max_retries + 1):
                        try:
                            result = await source.get_content_range(
                                identifier, offset, offset + chunk_size - 1
                            )
                            
                            if result.get("success", False):
                                data = result.get("data")
                                progress_tracker.increment(len(data))
                                yield data
                                break
                            elif attempt < self.max_retries:
                                logger.warning(f"Retry {attempt + 1}/{self.max_retries} for range {offset}-{offset + chunk_size - 1}")
                                await asyncio.sleep(0.5 * (attempt + 1))
                            else:
                                progress_tracker.fail(f"Failed to get chunk: {result.get('error')}")
                                return
                        except Exception as e:
                            if attempt < self.max_retries:
                                logger.warning(f"Retry {attempt + 1}/{self.max_retries} after error: {e}")
                                await asyncio.sleep(0.5 * (attempt + 1))
                            else:
                                progress_tracker.fail(f"Error getting chunk: {e}")
                                return
                    
                    offset += chunk_size
                
                # Mark as complete
                progress_tracker.complete()
            
            yield content_generator()
            
        except Exception as e:
            progress_tracker.fail(f"Error setting up stream: {e}")
            yield None
    
    async def download_to_file(self, source: Any, identifier: str, 
                              output_path: Union[str, Path],
                              progress_tracker: Optional[ProgressTracker] = None) -> Dict[str, Any]:
        """
        Download content to a file.
        
        Args:
            source: Source object with get_content method
            identifier: Content identifier
            output_path: Path to output file
            progress_tracker: Progress tracker
            
        Returns:
            Dictionary with download result
        """
        output_path = Path(output_path)
        
        # Create parent directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Open output file
            with open(output_path, "wb") as f:
                # Stream content
                async with self.stream(source, identifier, progress_tracker) as stream:
                    if stream is None:
                        return {"success": False, "error": "Failed to set up stream"}
                    
                    # Process chunks
                    async for chunk in stream:
                        f.write(chunk)
                
                # Check if completed successfully
                if progress_tracker.progress_info.error is not None:
                    return {
                        "success": False,
                        "error": progress_tracker.progress_info.error
                    }
                
                return {
                    "success": True,
                    "path": str(output_path),
                    "size": progress_tracker.progress_info.processed_size
                }
                
        except Exception as e:
            if progress_tracker:
                progress_tracker.fail(f"Error downloading to file: {e}")
            
            return {
                "success": False,
                "error": f"Error downloading to file: {e}"
            }


class BackgroundPinningManager:
    """
    Manager for background pinning operations.
    
    This class implements background pinning operations
    as mentioned in the roadmap.
    """
    
    def __init__(self, max_concurrent: int = 10):
        """
        Initialize the background pinning manager.
        
        Args:
            max_concurrent: Maximum number of concurrent pinning operations
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._operations: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._task = None
    
    def start(self):
        """Start the background pinning manager."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._process_operations())
            logger.info("Background pinning manager started")
    
    def stop(self):
        """Stop the background pinning manager."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("Background pinning manager stopped")
    
    async def pin(self, backend: Any, cid: str, 
                 progress_tracker: Optional[ProgressTracker] = None) -> str:
        """
        Schedule a pinning operation.
        
        Args:
            backend: Backend object with pin_add method
            cid: Content identifier to pin
            progress_tracker: Progress tracker
            
        Returns:
            Operation ID
        """
        # Create operation ID
        operation_id = f"pin_{cid}_{uuid.uuid4()}"
        
        # Create progress tracker if not provided
        progress_tracker = progress_tracker or ProgressTracker(operation_id)
        progress_tracker.initialize(100)  # Use percentage as size
        
        # Record operation
        self._operations[operation_id] = {
            "id": operation_id,
            "type": "pin",
            "cid": cid,
            "backend": backend,
            "progress": progress_tracker,
            "status": "pending",
            "created_at": time.time()
        }
        
        # Ensure manager is running
        self.start()
        
        return operation_id
    
    async def unpin(self, backend: Any, cid: str,
                   progress_tracker: Optional[ProgressTracker] = None) -> str:
        """
        Schedule an unpinning operation.
        
        Args:
            backend: Backend object with pin_rm method
            cid: Content identifier to unpin
            progress_tracker: Progress tracker
            
        Returns:
            Operation ID
        """
        # Create operation ID
        operation_id = f"unpin_{cid}_{uuid.uuid4()}"
        
        # Create progress tracker if not provided
        progress_tracker = progress_tracker or ProgressTracker(operation_id)
        progress_tracker.initialize(100)  # Use percentage as size
        
        # Record operation
        self._operations[operation_id] = {
            "id": operation_id,
            "type": "unpin",
            "cid": cid,
            "backend": backend,
            "progress": progress_tracker,
            "status": "pending",
            "created_at": time.time()
        }
        
        # Ensure manager is running
        self.start()
        
        return operation_id
    
    def get_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an operation.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            Dictionary with operation information or None if not found
        """
        if operation_id not in self._operations:
            return None
        
        operation = self._operations[operation_id]
        return {
            "id": operation["id"],
            "type": operation["type"],
            "cid": operation["cid"],
            "status": operation["status"],
            "created_at": operation["created_at"],
            "progress": operation["progress"].get_info()["progress"]
        }
    
    def list_operations(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all operations.
        
        Args:
            status: Filter by status
            
        Returns:
            List of operation information dictionaries
        """
        operations = []
        
        for operation_id, operation in self._operations.items():
            if status is None or operation["status"] == status:
                operations.append(self.get_operation(operation_id))
        
        return operations
    
    async def _process_operations(self):
        """Process pending operations in background."""
        try:
            while self._running:
                # Find pending operations
                pending_operations = [
                    op for op_id, op in self._operations.items()
                    if op["status"] == "pending"
                ]
                
                if not pending_operations:
                    # No pending operations, sleep and check again
                    await asyncio.sleep(1)
                    continue
                
                # Process operations concurrently
                tasks = []
                for operation in pending_operations:
                    tasks.append(asyncio.create_task(self._execute_operation(operation)))
                
                # Wait for a batch to complete
                await asyncio.gather(*tasks)
                
                # Sleep briefly before next batch
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.info("Background pinning manager task cancelled")
        except Exception as e:
            logger.error(f"Error in background pinning manager: {e}")
    
    async def _execute_operation(self, operation: Dict[str, Any]):
        """
        Execute a pinning operation.
        
        Args:
            operation: Operation information
        """
        # Get operation info
        operation_id = operation["id"]
        operation_type = operation["type"]
        cid = operation["cid"]
        backend = operation["backend"]
        progress = operation["progress"]
        
        # Mark as running
        operation["status"] = "running"
        progress.update(10)  # 10% progress for starting
        
        try:
            # Acquire semaphore for concurrency control
            async with self.semaphore:
                # Update progress
                progress.update(20)  # 20% progress
                
                if operation_type == "pin":
                    # Execute pin operation
                    result = await backend.pin_add(cid)
                else:
                    # Execute unpin operation
                    result = await backend.pin_rm(cid)
                
                # Update progress and status based on result
                if result.get("success", False):
                    operation["status"] = "completed"
                    progress.complete()
                else:
                    operation["status"] = "failed"
                    progress.fail(f"Operation failed: {result.get('error')}")
                
                # Record result
                operation["result"] = result
                
        except Exception as e:
            # Handle errors
            operation["status"] = "failed"
            progress.fail(f"Error executing operation: {e}")
            operation["error"] = str(e)
            logger.error(f"Error executing pin operation {operation_id}: {e}")