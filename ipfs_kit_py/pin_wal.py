#!/usr/bin/env python3
"""
Pin Write-Ahead Log (WAL) system for IPFS Kit.

This module provides a specialized WAL for pin operations that allows non-blocking
writes while ensuring data consistency and eventual replication across backends.
The daemon processes WAL entries asynchronously to update metadata indexes.
"""

import asyncio
import json
import os
import time
import uuid
import logging
import aiofiles
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

class PinOperationType(str, Enum):
    """Types of pin operations supported by the WAL."""
    ADD = "add"
    REMOVE = "remove"
    UPDATE = "update"
    METADATA_UPDATE = "metadata_update"

class PinOperationStatus(str, Enum):
    """Status values for pin operations in the WAL."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class PinWAL:
    """
    Write-Ahead Log for pin operations.
    
    This specialized WAL handles pin operations in a non-blocking manner,
    allowing the CLI and MCP server to write operations without waiting
    for database locks or slow I/O operations.
    """
    
    def __init__(self, base_path: str = "/tmp/ipfs_kit_wal"):
        self.base_path = Path(base_path)
        self.pending_dir = self.base_path / "pending"
        self.processing_dir = self.base_path / "processing"
        self.completed_dir = self.base_path / "completed"
        self.failed_dir = self.base_path / "failed"
        
        # Ensure directories exist
        for directory in [self.pending_dir, self.processing_dir, 
                         self.completed_dir, self.failed_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for recent operations
        self._operation_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_max_size = 1000
        
        logger.info(f"Pin WAL initialized at {self.base_path}")
    
    async def add_pin_operation(
        self,
        cid: str,
        operation_type: PinOperationType,
        name: Optional[str] = None,
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 0
    ) -> str:
        """
        Add a pin operation to the WAL.
        
        This is a non-blocking operation that immediately writes the operation
        to the pending queue and returns an operation ID.
        
        Args:
            cid: The content identifier to pin
            operation_type: Type of pin operation
            name: Optional name for the pin
            recursive: Whether the pin is recursive
            metadata: Additional metadata for the pin
            priority: Operation priority (higher = more urgent)
            
        Returns:
            Operation ID for tracking
        """
        operation_id = str(uuid.uuid4())
        timestamp = time.time()
        
        operation = {
            "operation_id": operation_id,
            "operation_type": operation_type.value,
            "cid": cid,
            "name": name,
            "recursive": recursive,
            "metadata": metadata or {},
            "priority": priority,
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "status": PinOperationStatus.PENDING.value,
            "retry_count": 0,
            "last_error": None
        }
        
        # Write to pending directory
        pending_file = self.pending_dir / f"{timestamp:.6f}_{priority:03d}_{operation_id}.json"
        
        try:
            async with aiofiles.open(pending_file, 'w') as f:
                await f.write(json.dumps(operation, indent=2))
            
            # Add to cache
            self._operation_cache[operation_id] = operation
            self._cleanup_cache()
            
            logger.info(f"Added pin operation {operation_id} for CID {cid}")
            return operation_id
            
        except Exception as e:
            logger.error(f"Failed to add pin operation: {e}")
            raise
    
    async def get_pending_operations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get pending operations sorted by priority and timestamp.
        
        Args:
            limit: Maximum number of operations to return
            
        Returns:
            List of pending operations
        """
        try:
            pending_files = list(self.pending_dir.glob("*.json"))
            
            # Sort by filename (which includes timestamp and priority)
            pending_files.sort()
            
            operations = []
            for file_path in pending_files[:limit]:
                try:
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                        operation = json.loads(content)
                        operations.append(operation)
                except Exception as e:
                    logger.error(f"Failed to read operation file {file_path}: {e}")
            
            return operations
            
        except Exception as e:
            logger.error(f"Failed to get pending operations: {e}")
            return []
    
    async def move_to_processing(self, operation_id: str) -> bool:
        """
        Move an operation from pending to processing.
        
        Args:
            operation_id: The operation ID to move
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the pending file
            pending_files = list(self.pending_dir.glob(f"*_{operation_id}.json"))
            if not pending_files:
                logger.warning(f"No pending operation found for {operation_id}")
                return False
            
            pending_file = pending_files[0]
            
            # Read the operation
            async with aiofiles.open(pending_file, 'r') as f:
                content = await f.read()
                operation = json.loads(content)
            
            # Update status and timestamp
            operation["status"] = PinOperationStatus.PROCESSING.value
            operation["processing_started_at"] = time.time()
            
            # Write to processing directory
            processing_file = self.processing_dir / f"{time.time():.6f}_{operation_id}.json"
            async with aiofiles.open(processing_file, 'w') as f:
                await f.write(json.dumps(operation, indent=2))
            
            # Remove from pending
            pending_file.unlink()
            
            # Update cache
            self._operation_cache[operation_id] = operation
            
            logger.debug(f"Moved operation {operation_id} to processing")
            return True
            
        except Exception as e:
            logger.error(f"Failed to move operation {operation_id} to processing: {e}")
            return False
    
    async def mark_completed(self, operation_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark an operation as completed.
        
        Args:
            operation_id: The operation ID to complete
            result: Optional result data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the processing file
            processing_files = list(self.processing_dir.glob(f"*_{operation_id}.json"))
            if not processing_files:
                logger.warning(f"No processing operation found for {operation_id}")
                return False
            
            processing_file = processing_files[0]
            
            # Read the operation
            async with aiofiles.open(processing_file, 'r') as f:
                content = await f.read()
                operation = json.loads(content)
            
            # Update status and result
            operation["status"] = PinOperationStatus.COMPLETED.value
            operation["completed_at"] = time.time()
            operation["result"] = result or {}
            
            # Write to completed directory
            completed_file = self.completed_dir / f"{time.time():.6f}_{operation_id}.json"
            async with aiofiles.open(completed_file, 'w') as f:
                await f.write(json.dumps(operation, indent=2))
            
            # Remove from processing
            processing_file.unlink()
            
            # Update cache
            self._operation_cache[operation_id] = operation
            
            logger.info(f"Marked operation {operation_id} as completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark operation {operation_id} as completed: {e}")
            return False
    
    async def mark_failed(self, operation_id: str, error: str, retry: bool = True) -> bool:
        """
        Mark an operation as failed.
        
        Args:
            operation_id: The operation ID that failed
            error: Error message
            retry: Whether to retry the operation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the processing file
            processing_files = list(self.processing_dir.glob(f"*_{operation_id}.json"))
            if not processing_files:
                logger.warning(f"No processing operation found for {operation_id}")
                return False
            
            processing_file = processing_files[0]
            
            # Read the operation
            async with aiofiles.open(processing_file, 'r') as f:
                content = await f.read()
                operation = json.loads(content)
            
            # Update status and error
            operation["retry_count"] = operation.get("retry_count", 0) + 1
            operation["last_error"] = error
            operation["failed_at"] = time.time()
            
            # Determine if we should retry
            max_retries = 3
            if retry and operation["retry_count"] < max_retries:
                operation["status"] = PinOperationStatus.RETRYING.value
                
                # Move back to pending with a delay
                retry_timestamp = time.time() + (operation["retry_count"] * 60)  # Exponential backoff
                pending_file = self.pending_dir / f"{retry_timestamp:.6f}_999_{operation_id}.json"  # Low priority
                
                async with aiofiles.open(pending_file, 'w') as f:
                    await f.write(json.dumps(operation, indent=2))
                
                logger.info(f"Operation {operation_id} queued for retry (attempt {operation['retry_count']})")
            else:
                operation["status"] = PinOperationStatus.FAILED.value
                
                # Write to failed directory
                failed_file = self.failed_dir / f"{time.time():.6f}_{operation_id}.json"
                async with aiofiles.open(failed_file, 'w') as f:
                    await f.write(json.dumps(operation, indent=2))
                
                logger.error(f"Operation {operation_id} failed permanently: {error}")
            
            # Remove from processing
            processing_file.unlink()
            
            # Update cache
            self._operation_cache[operation_id] = operation
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark operation {operation_id} as failed: {e}")
            return False
    
    async def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of an operation.
        
        Args:
            operation_id: The operation ID to check
            
        Returns:
            Operation data if found, None otherwise
        """
        # Check cache first
        if operation_id in self._operation_cache:
            return self._operation_cache[operation_id]
        
        # Search all directories
        for directory in [self.pending_dir, self.processing_dir, 
                         self.completed_dir, self.failed_dir]:
            try:
                files = list(directory.glob(f"*_{operation_id}.json"))
                if files:
                    async with aiofiles.open(files[0], 'r') as f:
                        content = await f.read()
                        operation = json.loads(content)
                        
                    # Add to cache
                    self._operation_cache[operation_id] = operation
                    return operation
            except Exception as e:
                logger.error(f"Error reading operation from {directory}: {e}")
        
        return None
    
    async def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """
        Clean up completed operations older than specified hours.
        
        Args:
            older_than_hours: Remove completed operations older than this
            
        Returns:
            Number of operations cleaned up
        """
        cutoff_time = time.time() - (older_than_hours * 3600)
        cleaned_count = 0
        
        for completed_file in self.completed_dir.glob("*.json"):
            try:
                # Extract timestamp from filename
                timestamp_str = completed_file.name.split('_')[0]
                file_timestamp = float(timestamp_str)
                
                if file_timestamp < cutoff_time:
                    completed_file.unlink()
                    cleaned_count += 1
                    
                    # Remove from cache if present
                    operation_id = completed_file.name.split('_')[-1].replace('.json', '')
                    self._operation_cache.pop(operation_id, None)
                    
            except Exception as e:
                logger.error(f"Error cleaning up {completed_file}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} completed operations")
        
        return cleaned_count
    
    def _cleanup_cache(self):
        """Clean up the operation cache if it gets too large."""
        if len(self._operation_cache) > self._cache_max_size:
            # Remove oldest entries (simple LRU)
            sorted_items = sorted(
                self._operation_cache.items(),
                key=lambda x: x[1].get("timestamp", 0)
            )
            
            # Keep the most recent half
            keep_count = self._cache_max_size // 2
            for operation_id, _ in sorted_items[:-keep_count]:
                del self._operation_cache[operation_id]
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get WAL statistics.
        
        Returns:
            Dictionary with WAL statistics
        """
        try:
            pending_count = len(list(self.pending_dir.glob("*.json")))
            processing_count = len(list(self.processing_dir.glob("*.json")))
            completed_count = len(list(self.completed_dir.glob("*.json")))
            failed_count = len(list(self.failed_dir.glob("*.json")))
            
            return {
                "pending": pending_count,
                "processing": processing_count,
                "completed": completed_count,
                "failed": failed_count,
                "cache_size": len(self._operation_cache),
                "total_operations": pending_count + processing_count + completed_count + failed_count
            }
        except Exception as e:
            logger.error(f"Failed to get WAL stats: {e}")
            return {}


# Global WAL instance
_global_pin_wal: Optional[PinWAL] = None

def get_global_pin_wal() -> PinWAL:
    """Get or create the global Pin WAL instance."""
    global _global_pin_wal
    if _global_pin_wal is None:
        _global_pin_wal = PinWAL()
    return _global_pin_wal

async def add_pin_to_wal(
    cid: str,
    name: Optional[str] = None,
    recursive: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
    priority: int = 0
) -> str:
    """
    Convenience function to add a pin operation to the global WAL.
    
    Args:
        cid: The content identifier to pin
        name: Optional name for the pin
        recursive: Whether the pin is recursive
        metadata: Additional metadata for the pin
        priority: Operation priority
        
    Returns:
        Operation ID for tracking
    """
    wal = get_global_pin_wal()
    return await wal.add_pin_operation(
        cid=cid,
        operation_type=PinOperationType.ADD,
        name=name,
        recursive=recursive,
        metadata=metadata,
        priority=priority
    )

async def remove_pin_from_wal(
    cid: str,
    metadata: Optional[Dict[str, Any]] = None,
    priority: int = 0
) -> str:
    """
    Convenience function to add a pin removal operation to the global WAL.
    
    Args:
        cid: The content identifier to unpin
        metadata: Additional metadata
        priority: Operation priority
        
    Returns:
        Operation ID for tracking
    """
    wal = get_global_pin_wal()
    return await wal.add_pin_operation(
        cid=cid,
        operation_type=PinOperationType.REMOVE,
        metadata=metadata,
        priority=priority
    )
