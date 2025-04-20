"""
Asynchronous Streaming Module for MCP Server

This module provides asynchronous streaming capabilities for efficient
transfer of large content using asyncio.
"""

import os
import asyncio
import logging
from typing import Dict, List, Any, Optional, AsyncIterator, Set, Union
from pathlib import Path
import contextlib
import uuid
import time
import aiofiles
from aiofiles.threadpool.binary import AsyncBufferedIOBase
import hashlib
from contextlib import asynccontextmanager

from ipfs_kit_py.mcp.streaming import (
    StreamStatus, StreamDirection, StreamType, StreamOperation, 
    DEFAULT_CHUNK_SIZE, DEFAULT_BUFFER_SIZE, DEFAULT_PROGRESS_INTERVAL,
    StreamProgress
)

# Configure logger
logger = logging.getLogger(__name__)


class AsyncStreamManager:
    """
    Manager for asynchronous streaming operations.
    
    This class provides methods for managing and tracking asynchronous
    streaming operations.
    """
    
    def __init__(self):
        """Initialize the stream manager."""
        self.streams: Dict[str, StreamOperation] = {}
        self.lock = asyncio.Lock()
        self._progress_task = None
        self._progress_interval = DEFAULT_PROGRESS_INTERVAL
        self._shutdown_event = asyncio.Event()
    
    async def initialize(self):
        """Initialize the stream manager."""
        # Start background progress update task
        self._progress_task = asyncio.create_task(self._update_progress())
        logger.info("Async stream manager initialized")
    
    async def shutdown(self):
        """Shutdown the stream manager."""
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for progress task to complete
        if self._progress_task:
            try:
                await asyncio.wait_for(self._progress_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for progress task")
        
        # Cancel all active streams
        async with self.lock:
            for stream_id, stream in self.streams.items():
                if stream.status in (StreamStatus.ACTIVE, StreamStatus.PENDING):
                    stream.update_status(StreamStatus.CANCELED)
        
        logger.info("Async stream manager shutdown complete")
    
    async def _update_progress(self):
        """Background task to update progress information."""
        try:
            while not self._shutdown_event.is_set():
                # Wait for interval or shutdown event
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), 
                        timeout=self._progress_interval
                    )
                except asyncio.TimeoutError:
                    pass
                
                # Skip if shutting down
                if self._shutdown_event.is_set():
                    break
                
                # Update progress for active streams
                async with self.lock:
                    for stream_id, stream in self.streams.items():
                        if stream.status == StreamStatus.ACTIVE:
                            # Just log progress for now
                            progress = stream.progress.to_dict()
                            logger.debug(f"Stream {stream_id} progress: {progress}")
        
        except Exception as e:
            logger.error(f"Error in progress update task: {e}")
    
    async def create_stream(self, 
                           direction: StreamDirection,
                           stream_type: StreamType,
                           source: Any,
                           destination: Any,
                           backend_name: Optional[str] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> StreamOperation:
        """
        Create a new stream operation.
        
        Args:
            direction: Stream direction (upload/download)
            stream_type: Type of stream
            source: Source object
            destination: Destination object
            backend_name: Optional backend name
            metadata: Optional metadata
            
        Returns:
            StreamOperation object
        """
        stream = StreamOperation(
            direction=direction,
            type=stream_type,
            source=source,
            destination=destination,
            backend_name=backend_name,
            metadata=metadata or {}
        )
        
        async with self.lock:
            self.streams[stream.id] = stream
        
        logger.info(f"Created stream {stream.id} ({direction.value} {stream_type.value})")
        return stream
    
    async def get_stream(self, stream_id: str) -> Optional[StreamOperation]:
        """
        Get a stream by ID.
        
        Args:
            stream_id: Stream ID
            
        Returns:
            StreamOperation object or None
        """
        async with self.lock:
            return self.streams.get(stream_id)
    
    async def list_streams(self, 
                          status: Optional[StreamStatus] = None, 
                          direction: Optional[StreamDirection] = None) -> List[StreamOperation]:
        """
        List streams.
        
        Args:
            status: Optional status filter
            direction: Optional direction filter
            
        Returns:
            List of StreamOperation objects
        """
        result = []
        
        async with self.lock:
            for stream in self.streams.values():
                if status and stream.status != status:
                    continue
                
                if direction and stream.direction != direction:
                    continue
                
                result.append(stream)
        
        return result
    
    async def update_stream_status(self, stream_id: str, status: StreamStatus) -> bool:
        """
        Update a stream's status.
        
        Args:
            stream_id: Stream ID
            status: New status
            
        Returns:
            True if successful, False otherwise
        """
        async with self.lock:
            if stream_id not in self.streams:
                return False
            
            stream = self.streams[stream_id]
            stream.update_status(status)
            return True
    
    async def set_stream_error(self, stream_id: str, error: str) -> bool:
        """
        Set a stream's error.
        
        Args:
            stream_id: Stream ID
            error: Error message
            
        Returns:
            True if successful, False otherwise
        """
        async with self.lock:
            if stream_id not in self.streams:
                return False
            
            stream = self.streams[stream_id]
            stream.set_error(error)
            return True
    
    async def set_stream_result(self, stream_id: str, result: Dict[str, Any]) -> bool:
        """
        Set a stream's result.
        
        Args:
            stream_id: Stream ID
            result: Result data
            
        Returns:
            True if successful, False otherwise
        """
        async with self.lock:
            if stream_id not in self.streams:
                return False
            
            stream = self.streams[stream_id]
            stream.set_result(result)
            return True
    
    async def cleanup_streams(self, max_age_hours: float = 24.0) -> int:
        """
        Clean up old streams.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of streams removed
        """
        import datetime
        
        max_age = datetime.timedelta(hours=max_age_hours)
        now = datetime.datetime.now()
        removed = 0
        
        async with self.lock:
            to_remove = []
            
            for stream_id, stream in self.streams.items():
                # Only remove completed, failed, or canceled streams
                if stream.status not in (
                    StreamStatus.COMPLETED, StreamStatus.FAILED, StreamStatus.CANCELED
                ):
                    continue
                
                # Check age
                age = now - stream.updated_at
                if age > max_age:
                    to_remove.append(stream_id)
            
            # Remove streams
            for stream_id in to_remove:
                del self.streams[stream_id]
                removed += 1
        
        if removed > 0:
            logger.info(f"Cleaned up {removed} old streams")
        
        return removed


class AsyncChunkedFileReader:
    """
    Asynchronous chunked file reader.
    
    This class provides asynchronous methods for reading files in chunks.
    """
    
    def __init__(self, path: Union[str, Path], chunk_size: int = DEFAULT_CHUNK_SIZE):
        """
        Initialize the reader.
        
        Args:
            path: Path to file
            chunk_size: Size of chunks in bytes
        """
        self.path = Path(path)
        self.chunk_size = chunk_size
        self.file: Optional[AsyncBufferedIOBase] = None
        self.file_size: int = 0
        self.position: int = 0
        self.progress = StreamProgress()
        self.checksum = hashlib.sha256()
    
    async def open(self) -> bool:
        """
        Open the file for reading.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get file size
            self.file_size = os.path.getsize(self.path)
            
            # Open file
            self.file = await aiofiles.open(self.path, "rb")
            
            # Initialize progress
            self.progress = StreamProgress()
            self.progress.total_bytes = self.file_size
            self.progress.total_chunks = (self.file_size + self.chunk_size - 1) // self.chunk_size
            
            # Reset checksum
            self.checksum = hashlib.sha256()
            
            return True
            
        except Exception as e:
            logger.error(f"Error opening file {self.path}: {e}")
            return False
    
    async def close(self) -> None:
        """Close the file."""
        if self.file:
            await self.file.close()
            self.file = None
    
    async def read_chunk(self) -> bytes:
        """
        Read a chunk from the file.
        
        Returns:
            Bytes read (empty if EOF)
        """
        if not self.file:
            raise ValueError("File not open")
        
        try:
            # Read chunk
            chunk = await self.file.read(self.chunk_size)
            
            # Update position
            self.position += len(chunk)
            
            # Update progress
            self.progress.update(self.position, self.file_size)
            self.progress.increment_chunks()
            
            # Update checksum
            self.checksum.update(chunk)
            
            return chunk
            
        except Exception as e:
            logger.error(f"Error reading from {self.path}: {e}")
            return b''
    
    async def read_all(self) -> bytes:
        """
        Read entire file.
        
        Returns:
            File contents
        """
        if not self.file:
            raise ValueError("File not open")
        
        # Seek to beginning
        await self.file.seek(0)
        self.position = 0
        
        # Read all
        data = await self.file.read()
        
        # Update position and progress
        self.position = len(data)
        self.progress.update(self.position, self.file_size)
        self.progress.increment_chunks(self.progress.total_chunks, self.progress.total_chunks)
        
        # Update checksum
        self.checksum.update(data)
        
        return data
    
    async def seek(self, position: int) -> bool:
        """
        Seek to position.
        
        Args:
            position: Position in bytes
            
        Returns:
            True if successful, False otherwise
        """
        if not self.file:
            raise ValueError("File not open")
        
        try:
            await self.file.seek(position)
            self.position = position
            self.progress.update(self.position, self.file_size)
            return True
            
        except Exception as e:
            logger.error(f"Error seeking in {self.path}: {e}")
            return False
    
    def get_checksum(self) -> str:
        """
        Get file checksum.
        
        Returns:
            Hexadecimal checksum
        """
        return self.checksum.hexdigest()


class AsyncChunkedFileWriter:
    """
    Asynchronous chunked file writer.
    
    This class provides asynchronous methods for writing files in chunks.
    """
    
    def __init__(self, path: Union[str, Path], append: bool = False):
        """
        Initialize the writer.
        
        Args:
            path: Path to file
            append: Whether to append to file
        """
        self.path = Path(path)
        self.append = append
        self.file: Optional[AsyncBufferedIOBase] = None
        self.bytes_written: int = 0
        self.progress = StreamProgress()
        self.checksum = hashlib.sha256()
    
    async def open(self) -> bool:
        """
        Open the file for writing.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            self.path.parent.mkdir(parents=True, exist_ok=True)
            
            # Open file
            mode = "ab" if self.append else "wb"
            self.file = await aiofiles.open(self.path, mode)
            
            # Get current size if appending
            if self.append:
                self.bytes_written = os.path.getsize(self.path)
            else:
                self.bytes_written = 0
            
            # Initialize progress
            self.progress = StreamProgress()
            
            # Reset checksum
            self.checksum = hashlib.sha256()
            
            return True
            
        except Exception as e:
            logger.error(f"Error opening file {self.path}: {e}")
            return False
    
    async def close(self) -> None:
        """Close the file."""
        if self.file:
            await self.file.close()
            self.file = None
    
    async def write(self, data: bytes) -> int:
        """
        Write data to the file.
        
        Args:
            data: Data to write
            
        Returns:
            Number of bytes written
        """
        if not self.file:
            raise ValueError("File not open")
        
        try:
            # Write data
            await self.file.write(data)
            
            # Update position
            self.bytes_written += len(data)
            
            # Update progress
            self.progress.update(self.bytes_written)
            self.progress.increment_chunks()
            
            # Update checksum
            self.checksum.update(data)
            
            return len(data)
            
        except Exception as e:
            logger.error(f"Error writing to {self.path}: {e}")
            return 0
    
    async def flush(self) -> bool:
        """
        Flush file buffers.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.file:
            raise ValueError("File not open")
        
        try:
            await self.file.flush()
            return True
            
        except Exception as e:
            logger.error(f"Error flushing {self.path}: {e}")
            return False
    
    def get_checksum(self) -> str:
        """
        Get file checksum.
        
        Returns:
            Hexadecimal checksum
        """
        return self.checksum.hexdigest()


# Singleton instance
_manager = None

@asynccontextmanager
async def open_async_stream_manager():
    """
    Get or create the singleton stream manager.
    
    Yields:
        AsyncStreamManager instance
    """
    global _manager
    if _manager is None:
        _manager = AsyncStreamManager()
        await _manager.initialize()
    
    try:
        yield _manager
    finally:
        pass  # Don't shut down the manager on context exit


async def get_async_stream_manager() -> AsyncStreamManager:
    """
    Get the singleton stream manager.
    
    Returns:
        AsyncStreamManager instance
    """
    global _manager
    if _manager is None:
        _manager = AsyncStreamManager()
        await _manager.initialize()
    return _manager


async def shutdown_async_stream_manager() -> None:
    """Shutdown the stream manager."""
    global _manager
    if _manager:
        await _manager.shutdown()
        _manager = None


async def create_stream(direction: StreamDirection,
                        stream_type: StreamType,
                        source: Any,
                        destination: Any,
                        backend_name: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> StreamOperation:
    """
    Create a new stream operation.
    
    Args:
        direction: Stream direction (upload/download)
        stream_type: Type of stream
        source: Source object
        destination: Destination object
        backend_name: Optional backend name
        metadata: Optional metadata
        
    Returns:
        StreamOperation object
    """
    manager = await get_async_stream_manager()
    return await manager.create_stream(
        direction, stream_type, source, destination, backend_name, metadata
    )
