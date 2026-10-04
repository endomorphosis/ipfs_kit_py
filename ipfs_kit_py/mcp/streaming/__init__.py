"""
MCP Streaming Module for efficient transfer of large content.

This module provides basic streaming types and constants used by both
synchronous and asynchronous streaming implementations.
"""

import time
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Set
from dataclasses import dataclass, field
from datetime import datetime

# Define constants
DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
DEFAULT_BUFFER_SIZE = 8 * 1024 * 1024  # 8MB
DEFAULT_PROGRESS_INTERVAL = 0.5  # seconds


class StreamStatus(str, Enum):
    """Status of a stream operation."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class StreamDirection(str, Enum):
    """Direction of a stream operation."""
    UPLOAD = "upload"
    DOWNLOAD = "download"


class StreamType(str, Enum):
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
    source: Optional[Any] = None
    destination: Optional[Any] = None
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
