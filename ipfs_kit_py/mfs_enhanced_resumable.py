#!/usr/bin/env python3
"""
Enhanced MFS resumable operations for IPFS.

This module provides functionality for resumable file operations in the IPFS
Mutable File System, allowing read and write operations to be paused and resumed.
It implements a comprehensive permissions system to control access to files and
directories based on user identity, groups, and access control lists (ACLs).

Key features:
- Resumable file operations with chunked transfer
- Adaptive chunk sizing for optimal performance
- Parallel transfers for improved throughput
- UNIX-like permission model (read/write/execute)
- User and group-based access control
- Access Control Lists (ACLs) for fine-grained permissions
- Permission inheritance from parent directories
- Configurable permission enforcement
"""

import anyio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union, BinaryIO, Callable, Any

from ipfs_kit_py.mfs_permissions import (
    Permission, FileType, FilePermissions, PermissionManager, AccessDeniedException
)

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class FileChunk:
    """Represents a chunk of a file for resumable operations."""
    start: int
    end: int
    size: int
    hash: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed, failed


class ResumableFileState:
    """Manages state for resumable file operations."""
    
    def __init__(self, 
                file_path: str, 
                total_size: int = 0, 
                chunk_size: int = 1024 * 1024,  # 1MB default chunk size
                metadata: Optional[Dict[str, Any]] = None,
                adaptive_chunking: bool = False):
        """
        Initialize resumable file state.
        
        Args:
            file_path: Path to the file in MFS
            total_size: Total size of the file
            chunk_size: Size of each chunk in bytes
            metadata: Additional metadata for the file
            adaptive_chunking: Whether to dynamically adjust chunk size based on network conditions
        """
        self.file_path = file_path
        self.total_size = total_size
        self.chunk_size = chunk_size
        self.chunks: List[FileChunk] = []
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.updated_at = time.time()
        self.first_chunk_time: Optional[float] = None
        self.latest_chunk_time: Optional[float] = None
        self.bytes_processed = 0
        self.completed = False
        self.adaptive_chunking = adaptive_chunking
        self.chunk_transfer_times: List[Tuple[int, float]] = []  # List of (chunk_size, transfer_time) tuples
        self.optimal_chunk_size: int = chunk_size
        
        # Create chunks if total_size is known
        if total_size > 0:
            self._create_chunks()
    
    def _create_chunks(self):
        """Create chunks based on total size and chunk size."""
        self.chunks = []
        for start in range(0, self.total_size, self.chunk_size):
            end = min(start + self.chunk_size, self.total_size)
            size = end - start
            self.chunks.append(FileChunk(start=start, end=end, size=size))
    
    def update_optimal_chunk_size(self, chunk_size: int, transfer_time: float):
        """
        Update the optimal chunk size based on observed transfer performance.
        
        Args:
            chunk_size: Size of the chunk that was transferred
            transfer_time: Time taken to transfer the chunk in seconds
        """
        if not self.adaptive_chunking or transfer_time <= 0:
            return
        
        # Add this transfer to history
        self.chunk_transfer_times.append((chunk_size, transfer_time))
        
        # Keep only the last 10 transfers for calculations
        if len(self.chunk_transfer_times) > 10:
            self.chunk_transfer_times = self.chunk_transfer_times[-10:]
        
        # Need at least 3 data points to make meaningful adjustments
        if len(self.chunk_transfer_times) < 3:
            return
        
        # Calculate transfer rates (bytes per second) for different chunk sizes
        size_to_rates = {}
        for size, time_taken in self.chunk_transfer_times:
            if size not in size_to_rates:
                size_to_rates[size] = []
            
            rate = size / time_taken  # bytes per second
            size_to_rates[size].append(rate)
        
        # Calculate average rate for each chunk size
        avg_rates = {
            size: sum(rates) / len(rates) 
            for size, rates in size_to_rates.items()
        }
        
        # Find the most efficient chunk size (highest transfer rate)
        if avg_rates:
            best_size = max(avg_rates.items(), key=lambda x: x[1])[0]
            
            # If it's significantly better than current optimal, update
            # Only change if at least 20% improvement to avoid oscillation
            current_rate = avg_rates.get(self.optimal_chunk_size, 0)
            best_rate = avg_rates[best_size]
            
            if best_rate > current_rate * 1.2:
                old_size = self.optimal_chunk_size
                self.optimal_chunk_size = best_size
                
                # Log the change
                logger.info(
                    f"Adapted chunk size from {old_size/1024:.1f}KB to "
                    f"{best_size/1024:.1f}KB (performance gain: {best_rate/current_rate:.2f}x)"
                )
    
    def get_next_chunk(self) -> Optional[FileChunk]:
        """Get the next pending chunk to process."""
        for chunk in self.chunks:
            if chunk.status == "pending":
                chunk.status = "in_progress"
                return chunk
        return None
    
    def update_chunk(self, chunk: FileChunk, status: str, hash_value: Optional[str] = None):
        """Update the status of a chunk."""
        now = time.time()
        
        for i, c in enumerate(self.chunks):
            if c.start == chunk.start and c.end == chunk.end:
                previous_status = c.status
                self.chunks[i].status = status
                if hash_value:
                    self.chunks[i].hash = hash_value
                
                # Update timing and bytes processed if completing a chunk
                if status == "completed" and previous_status != "completed":
                    # Track when we first completed a chunk
                    if self.first_chunk_time is None:
                        self.first_chunk_time = now
                    
                    # Update the latest chunk time
                    self.latest_chunk_time = now
                    
                    # Update bytes processed
                    self.bytes_processed += chunk.size
                
                break
                
        self.updated_at = now
        
        # Check if all chunks are completed
        self.completed = all(c.status == "completed" for c in self.chunks)
    
    def reset_in_progress_chunks(self):
        """Reset all in-progress chunks to pending."""
        for chunk in self.chunks:
            if chunk.status == "in_progress":
                chunk.status = "pending"
        self.updated_at = time.time()
    
    def get_completion_percentage(self) -> float:
        """Get the percentage of completed chunks."""
        if not self.chunks:
            return 0.0
        completed = sum(1 for chunk in self.chunks if chunk.status == "completed")
        return (completed / len(self.chunks)) * 100
        
    def get_transfer_stats(self) -> Dict[str, Any]:
        """
        Get transfer statistics including speed and estimated time remaining.
        
        Returns:
            Dictionary with transfer statistics
        """
        stats = {
            "bytes_processed": self.bytes_processed,
            "bytes_remaining": self.total_size - self.bytes_processed,
            "completion_percentage": self.get_completion_percentage(),
            "average_speed_bytes_per_sec": 0,
            "current_speed_bytes_per_sec": 0,
            "estimated_time_remaining_sec": 0
        }
        
        # Calculate speeds if we have timing information
        if self.first_chunk_time is not None and self.latest_chunk_time is not None:
            # Total time since first chunk
            total_time = self.latest_chunk_time - self.first_chunk_time
            if total_time > 0:
                # Average speed over entire operation
                stats["average_speed_bytes_per_sec"] = self.bytes_processed / total_time
                
                # Estimate time remaining based on average speed
                if stats["average_speed_bytes_per_sec"] > 0 and not self.completed:
                    stats["estimated_time_remaining_sec"] = (
                        stats["bytes_remaining"] / stats["average_speed_bytes_per_sec"]
                    )
                
                # If we have more than one chunk, we can calculate current speed
                completed_chunks = [c for c in self.chunks if c.status == "completed"]
                if len(completed_chunks) >= 2:
                    # Use the last 5 chunks or all completed chunks if fewer
                    recent_chunks_count = min(5, len(completed_chunks))
                    recent_chunks = completed_chunks[-recent_chunks_count:]
                    
                    # Calculate size of recent chunks
                    recent_bytes = sum(c.size for c in recent_chunks)
                    
                    # Calculate time window for recent chunks (approximate based on overall timing)
                    if recent_bytes > 0 and self.bytes_processed > 0:
                        time_fraction = recent_bytes / self.bytes_processed
                        recent_time = total_time * time_fraction
                        if recent_time > 0:
                            stats["current_speed_bytes_per_sec"] = recent_bytes / recent_time
                            
                            # Update estimated time using current speed if it's more accurate
                            if stats["current_speed_bytes_per_sec"] > 0 and not self.completed:
                                curr_estimate = (
                                    stats["bytes_remaining"] / stats["current_speed_bytes_per_sec"]
                                )
                                # Use current speed estimate if it's reasonable (not too far from average)
                                if curr_estimate < stats["estimated_time_remaining_sec"] * 5:
                                    stats["estimated_time_remaining_sec"] = curr_estimate
                    
        return stats
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "file_path": self.file_path,
            "total_size": self.total_size,
            "chunk_size": self.chunk_size,
            "chunks": [
                {
                    "start": chunk.start,
                    "end": chunk.end,
                    "size": chunk.size,
                    "hash": chunk.hash,
                    "status": chunk.status
                }
                for chunk in self.chunks
            ],
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "first_chunk_time": self.first_chunk_time,
            "latest_chunk_time": self.latest_chunk_time,
            "bytes_processed": self.bytes_processed,
            "completed": self.completed,
            "adaptive_chunking": self.adaptive_chunking,
            "optimal_chunk_size": self.optimal_chunk_size,
            "chunk_transfer_times": self.chunk_transfer_times
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResumableFileState":
        """Create state from dictionary."""
        state = cls(
            file_path=data["file_path"],
            total_size=data["total_size"],
            chunk_size=data["chunk_size"],
            metadata=data.get("metadata", {}),
            adaptive_chunking=data.get("adaptive_chunking", False)
        )
        state.created_at = data.get("created_at", time.time())
        state.updated_at = data.get("updated_at", time.time())
        state.first_chunk_time = data.get("first_chunk_time")
        state.latest_chunk_time = data.get("latest_chunk_time")
        state.bytes_processed = data.get("bytes_processed", 0)
        state.completed = data.get("completed", False)
        state.optimal_chunk_size = data.get("optimal_chunk_size", state.chunk_size)
        state.chunk_transfer_times = data.get("chunk_transfer_times", [])
        
        # Recreate chunks
        state.chunks = []
        for chunk_data in data.get("chunks", []):
            chunk = FileChunk(
                start=chunk_data["start"],
                end=chunk_data["end"],
                size=chunk_data["size"],
                hash=chunk_data.get("hash"),
                status=chunk_data.get("status", "pending")
            )
            state.chunks.append(chunk)
        
        return state


class ResumableFileOperations:
    """
    Provides resumable file operations for IPFS MFS with permission management.
    
    This class implements resumable read and write operations for IPFS MFS,
    allowing operations to be paused and resumed even after connection loss.
    It fully integrates with the permission system to control access to files,
    enforcing user and group-based permissions for all file operations.
    
    The permission system implements a UNIX-like model with read, write, and
    execute permissions for owner, group, and others. Additionally, it supports
    Access Control Lists (ACLs) for more fine-grained permission control.
    
    Permission checks are performed at multiple levels:
    - When starting operations (read/write)
    - During individual chunk operations
    - When finalizing operations
    - During copy operations (for both source and destination)
    
    Permissions can be bypassed for system operations by setting enforce_permissions=False
    when initializing the class.
    """
    
    def __init__(self, 
                ipfs_client, 
                state_dir: Optional[str] = None,
                permissions_dir: Optional[str] = None,
                user_id: Optional[str] = None,
                max_concurrent_transfers: int = 4,
                enforce_permissions: bool = True):
        """
        Initialize resumable file operations.
        
        Args:
            ipfs_client: IPFS client instance
            state_dir: Directory to store state files, defaults to ~/.ipfs_kit/resumable
            permissions_dir: Directory to store permission files, defaults to ~/.ipfs_kit/permissions
            user_id: Current user ID, defaults to "default_user"
            max_concurrent_transfers: Maximum number of concurrent chunk transfers
            enforce_permissions: Whether to enforce permissions (if False, all operations are allowed)
        """
        self.ipfs_client = ipfs_client
        self.state_dir = state_dir or os.path.expanduser("~/.ipfs_kit/resumable")
        os.makedirs(self.state_dir, exist_ok=True)
        self.active_operations: Dict[str, ResumableFileState] = {}
        self.progress_callbacks: Dict[str, Callable] = {}
        self.max_concurrent_transfers = max_concurrent_transfers
        self.transfer_semaphores: Dict[str, anyio.Semaphore] = {}
        self.active_transfers: Dict[str, Dict[int, anyio.Task]] = {}
        
        # Initialize permissions
        self.enforce_permissions = enforce_permissions
        self.user_id = user_id or "default_user"
        self.permission_manager = PermissionManager(
            permissions_dir=permissions_dir,
            current_user_id=self.user_id
        ) if enforce_permissions else None
    
    def _get_state_path(self, file_id: str) -> str:
        """Get path to the state file for a resumable operation."""
        return os.path.join(self.state_dir, f"{file_id}.json")
    
    async def _check_permission(self, file_path: str, permission: Permission) -> bool:
        """
        Check if the current user has permission for an operation.
        
        This method verifies if the current user has the specified permission for the
        given file path. It delegates to the PermissionManager to perform the actual
        permission check based on user, group, and ACL information.
        
        If enforce_permissions is False, this method always returns True, bypassing
        the permission check. This is useful for system operations that need to run
        regardless of user permissions.
        
        Args:
            file_path: Path to the file in MFS
            permission: Permission to check (READ, WRITE, EXECUTE)
            
        Returns:
            bool: Whether the user has the requested permission
            
        Raises:
            AccessDeniedException: If the user doesn't have permission and enforce_permissions is True
        """
        logger.debug(f"Permission check started for user={self.user_id}, path={file_path}, permission={permission.value}")
        logger.debug(f"Enforce permissions: {self.enforce_permissions}, permission manager exists: {self.permission_manager is not None}")
        
        if not self.enforce_permissions or not self.permission_manager:
            logger.debug(f"Permissions bypassed, returning True")
            return True
        
        # Load the permissions directly from disk to verify what's stored
        if hasattr(self.permission_manager, '_get_permissions_path') and logger.isEnabledFor(logging.DEBUG):
            perm_path = self.permission_manager._get_permissions_path(file_path)
            logger.debug(f"Permission file path: {perm_path}")
            if os.path.exists(perm_path):
                logger.debug(f"Permission file exists: {perm_path}")
                try:
                    with open(perm_path) as f:
                        perm_data = json.load(f)
                        logger.debug(f"Raw permission data from disk: {perm_data.get('owner_permissions', [])}")
                except Exception as e:
                    logger.debug(f"Error reading permission file: {e}")
        
        # Perform the actual permission check
        logger.debug(f"Calling permission_manager.check_permission...")
        has_permission = await self.permission_manager.check_permission(
            file_path=file_path,
            permission=permission,
            user_id=self.user_id
        )
        logger.debug(f"Permission check result: {has_permission}")
        
        if not has_permission:
            logger.debug(f"Access denied, raising AccessDeniedException")
            logger.warning(
                f"Access denied for user {self.user_id} on {file_path}: "
                f"lacks {permission.value} permission"
            )
            raise AccessDeniedException(file_path, permission, self.user_id)
        
        logger.debug(f"Permission check passed")    
        return True
        
    async def _ensure_permissions(self, file_path: str, file_type: FileType) -> None:
        """
        Ensure permissions exist for a file, creating them if needed.
        
        This method checks if permissions are defined for the given file path and
        creates default permissions if they don't exist. The default permissions
        are based on the file type and system defaults from the PermissionManager.
        
        For new files, permissions are typically inherited from parent directories
        according to the permission inheritance rules. If no parent directory exists
        or has permissions, system defaults are used.
        
        Args:
            file_path: Path to the file in MFS
            file_type: Type of file (FILE, DIRECTORY, SYMLINK)
        """
        if not self.enforce_permissions or not self.permission_manager:
            return
            
        await self.permission_manager.ensure_permissions(
            file_path=file_path,
            file_type=file_type
        )
    
    async def save_state(self, file_id: str, state: ResumableFileState):
        """Save operation state to disk."""
        state_path = self._get_state_path(file_id)
        # Keep an in-memory copy for quick access
        self.active_operations[file_id] = state
        
        # Save to disk for persistence
        async with anyio.Lock():
            with open(state_path, "w") as f:
                json.dump(state.to_dict(), f)
    
    async def load_state(self, file_id: str) -> Optional[ResumableFileState]:
        """Load operation state from disk."""
        # Check in-memory cache first
        if file_id in self.active_operations:
            return self.active_operations[file_id]
        
        # Try to load from disk
        state_path = self._get_state_path(file_id)
        if os.path.exists(state_path):
            try:
                with open(state_path, "r") as f:
                    data = json.load(f)
                state = ResumableFileState.from_dict(data)
                self.active_operations[file_id] = state
                return state
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error loading state file {state_path}: {e}")
        
        return None
    
    async def clear_state(self, file_id: str):
        """Clear operation state."""
        if file_id in self.active_operations:
            del self.active_operations[file_id]
        
        # Clear any progress callback
        if file_id in self.progress_callbacks:
            del self.progress_callbacks[file_id]
        
        state_path = self._get_state_path(file_id)
        if os.path.exists(state_path):
            os.remove(state_path)
            
    def register_progress_callback(self, file_id: str, callback: Callable):
        """
        Register a callback function to monitor progress of a resumable operation.
        
        Args:
            file_id: Unique identifier for the resumable operation
            callback: Function that will be called with progress updates
                     The callback should accept a dict with progress information
        """
        self.progress_callbacks[file_id] = callback
    
    def unregister_progress_callback(self, file_id: str):
        """
        Unregister a progress callback for a resumable operation.
        
        Args:
            file_id: Unique identifier for the resumable operation
        """
        if file_id in self.progress_callbacks:
            del self.progress_callbacks[file_id]
    
    async def _report_progress(self, file_id: str, state: ResumableFileState, status: str, **kwargs):
        """
        Report progress for a resumable operation by calling the registered callback.
        
        Args:
            file_id: Unique identifier for the resumable operation
            state: Current state of the operation
            status: Status message (e.g., "chunk_completed", "operation_resumed")
            **kwargs: Additional information to include in progress report
        """
        if file_id not in self.progress_callbacks:
            return
        
        # Get transfer statistics
        transfer_stats = state.get_transfer_stats()
        
        # Create progress report
        progress_info = {
            "file_id": file_id,
            "file_path": state.file_path,
            "total_size": state.total_size,
            "total_chunks": len(state.chunks),
            "completed_chunks": sum(1 for chunk in state.chunks if chunk.status == "completed"),
            "failed_chunks": sum(1 for chunk in state.chunks if chunk.status == "failed"),
            "completion_percentage": state.get_completion_percentage(),
            "status": status,
            "timestamp": time.time(),
            # Include transfer statistics
            "bytes_processed": transfer_stats["bytes_processed"],
            "bytes_remaining": transfer_stats["bytes_remaining"],
            "average_speed_bytes_per_sec": transfer_stats["average_speed_bytes_per_sec"],
            "current_speed_bytes_per_sec": transfer_stats["current_speed_bytes_per_sec"],
            "estimated_time_remaining_sec": transfer_stats["estimated_time_remaining_sec"],
            **kwargs
        }
        
        # Include adaptive chunking information if enabled
        if state.adaptive_chunking:
            progress_info["adaptive_chunking"] = True
            progress_info["optimal_chunk_size"] = state.optimal_chunk_size
            progress_info["initial_chunk_size"] = state.chunk_size
            
            # Calculate improvement factor if different from initial
            if state.optimal_chunk_size != state.chunk_size:
                progress_info["chunk_size_adaptation_factor"] = state.optimal_chunk_size / state.chunk_size
        
        # Call the callback
        try:
            callback = self.progress_callbacks[file_id]
            if anyio.iscoroutinefunction(callback):
                await callback(progress_info)
            else:
                callback(progress_info)
        except Exception as e:
            logger.error(f"Error in progress callback for {file_id}: {e}")
    
    async def list_resumable_operations(self) -> List[Dict[str, Any]]:
        """List all resumable operations."""
        operations = []
        
        # Load all state files
        for filename in os.listdir(self.state_dir):
            if filename.endswith(".json"):
                file_id = filename[:-5]  # Remove .json extension
                state = await self.load_state(file_id)
                if state:
                    operations.append({
                        "file_id": file_id,
                        "file_path": state.file_path,
                        "total_size": state.total_size,
                        "completion_percentage": state.get_completion_percentage(),
                        "created_at": state.created_at,
                        "updated_at": state.updated_at,
                        "completed": state.completed,
                        "metadata": state.metadata
                    })
        
        return operations
    
    def generate_file_id(self, file_path: str) -> str:
        """Generate a unique file ID for a resumable operation."""
        # Use timestamp and file path to create a unique ID
        timestamp = int(time.time() * 1000)
        # Create safe filename by replacing problematic characters
        safe_path = file_path.replace("/", "_").replace(".", "_")
        return f"{timestamp}_{safe_path}"
    
    async def start_resumable_write(self, 
                                   file_path: str, 
                                   total_size: int, 
                                   chunk_size: int = 1024 * 1024,
                                   metadata: Optional[Dict[str, Any]] = None,
                                   adaptive_chunking: bool = False,
                                   parallel_transfers: bool = False,
                                   max_parallel_chunks: Optional[int] = None,
                                   owner_id: Optional[str] = None,
                                   group_id: Optional[str] = None) -> str:
        """
        Start a resumable write operation.
        
        Initiates a resumable write operation for the specified file path, after
        verifying that the current user has write permission for the file.
        
        This method first checks if the user has write permission for the file.
        If permissions are being enforced and the user doesn't have write permission,
        an AccessDeniedException is raised.
        
        For new files, this method creates default permissions based on the current
        user and group settings. The owner_id and group_id parameters can be used
        to specify a different owner and group for the file.
        
        Args:
            file_path: Path to the file in MFS
            total_size: Total size of the file
            chunk_size: Size of each chunk in bytes
            metadata: Additional metadata for the file
            adaptive_chunking: Whether to dynamically adjust chunk size based on network conditions
            parallel_transfers: Whether to enable parallel chunk transfers
            max_parallel_chunks: Maximum number of chunks to transfer in parallel (defaults to self.max_concurrent_transfers)
            owner_id: Owner of the file (defaults to current user)
            group_id: Group of the file (defaults to "users")
            
        Returns:
            file_id: Unique identifier for the resumable operation
            
        Raises:
            AccessDeniedException: If the user doesn't have permission to write to the file
        """
        # Check write permission for the file path
        await self._check_permission(file_path, Permission.WRITE)
        
        # Create permissions for the file if needed
        if self.enforce_permissions and self.permission_manager:
            file_type = FileType.FILE
            
            # If owner_id is provided, set custom owner
            if owner_id:
                await self.permission_manager.set_owner(
                    file_path=file_path,
                    owner_id=owner_id,
                    group_id=group_id
                )
            else:
                # Create default permissions
                await self._ensure_permissions(file_path, file_type)
        
        file_id = self.generate_file_id(file_path)
        
        # Initialize metadata
        if metadata is None:
            metadata = {}
        
        # Set operation type in metadata
        metadata["operation_type"] = "write"
        
        # Create state
        state = ResumableFileState(
            file_path=file_path,
            total_size=total_size,
            chunk_size=chunk_size,
            metadata=metadata,
            adaptive_chunking=adaptive_chunking
        )
        
        # Add parallel transfer metadata if enabled
        if parallel_transfers:
            if "parallel_transfer" not in state.metadata:
                state.metadata["parallel_transfer"] = {}
            
            state.metadata["parallel_transfer"]["enabled"] = True
            state.metadata["parallel_transfer"]["max_chunks"] = max_parallel_chunks or self.max_concurrent_transfers
        
        # Create semaphore for this operation if parallel transfers are enabled
        if parallel_transfers:
            max_parallel = max_parallel_chunks or self.max_concurrent_transfers
            self.transfer_semaphores[file_id] = anyio.Semaphore(max_parallel)
            self.active_transfers[file_id] = {}
        
        # Save state
        await self.save_state(file_id, state)
        
        # Create empty file if it doesn't exist
        try:
            await self.ipfs_client.files_stat(file_path)
        except Exception:
            # File doesn't exist, create it
            await self.ipfs_client.files_write(
                file_path,
                b"",
                create=True,
                truncate=True
            )
        
        return file_id
    
    async def _write_single_chunk(self, 
                               file_id: str, 
                               chunk_data: bytes, 
                               chunk: FileChunk,
                               chunk_index: Optional[int] = None) -> Dict[str, Any]:
        """
        Internal method to write a single chunk of data to a file.
        
        Args:
            file_id: Unique identifier for the resumable operation
            chunk_data: Data to write
            chunk: The chunk to write
            chunk_index: Index of the chunk (for reporting)
            
        Returns:
            result: Result of the operation
        """
        state = await self.load_state(file_id)
        if not state:
            return {
                "success": False,
                "error": f"No resumable operation found with ID {file_id}"
            }
        
        # Check write permission
        try:
            await self._check_permission(state.file_path, Permission.WRITE)
        except AccessDeniedException as e:
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "permission_denied": True
            }
        
        # Attempt to write the chunk
        try:
            # Check if data size matches chunk size
            if len(chunk_data) != chunk.size:
                return {
                    "success": False,
                    "error": f"Chunk data size ({len(chunk_data)}) doesn't match expected size ({chunk.size})"
                }
            
            # Track start time for performance monitoring
            start_time = time.time()
            
            # Write the chunk
            await self.ipfs_client.files_write(
                state.file_path,
                chunk_data,
                offset=chunk.start,
                create=True
            )
            
            # Calculate transfer time
            transfer_time = time.time() - start_time
            
            # Update adaptive chunking statistics
            if state.adaptive_chunking:
                state.update_optimal_chunk_size(chunk.size, transfer_time)
            
            # Update chunk status
            state.update_chunk(chunk, "completed")
            await self.save_state(file_id, state)
            
            # Report progress
            await self._report_progress(
                file_id, 
                state, 
                status="chunk_completed",
                chunk_start=chunk.start,
                chunk_end=chunk.end,
                chunk_index=chunk_index,
                transfer_time=transfer_time,
                transfer_rate=chunk.size / transfer_time if transfer_time > 0 else 0
            )
            
            # Return success
            return {
                "success": True,
                "file_id": file_id,
                "chunk_start": chunk.start,
                "chunk_end": chunk.end,
                "chunk_index": chunk_index,
                "completion_percentage": state.get_completion_percentage(),
                "completed": state.completed,
                "transfer_time": transfer_time,
                "transfer_rate": chunk.size / transfer_time if transfer_time > 0 else 0
            }
            
        except Exception as e:
            # Mark chunk as failed
            state.update_chunk(chunk, "failed")
            await self.save_state(file_id, state)
            
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "chunk_start": chunk.start,
                "chunk_end": chunk.end,
                "chunk_index": chunk_index
            }
    
    async def write_chunk(self, 
                         file_id: str, 
                         chunk_data: bytes, 
                         chunk_index: Optional[int] = None,
                         offset: Optional[int] = None) -> Dict[str, Any]:
        """
        Write a chunk of data to a file.
        
        Args:
            file_id: Unique identifier for the resumable operation
            chunk_data: Data to write
            chunk_index: Index of the chunk to write (mutually exclusive with offset)
            offset: Byte offset to write at (mutually exclusive with chunk_index)
            
        Returns:
            result: Result of the operation
        """
        state = await self.load_state(file_id)
        if not state:
            return {
                "success": False,
                "error": f"No resumable operation found with ID {file_id}"
            }
        
        # Determine which chunk to write
        chunk = None
        if chunk_index is not None and 0 <= chunk_index < len(state.chunks):
            chunk = state.chunks[chunk_index]
        elif offset is not None:
            for c in state.chunks:
                if c.start <= offset < c.end:
                    chunk = c
                    break
        else:
            # Get next pending chunk
            chunk = state.get_next_chunk()
        
        if not chunk:
            return {
                "success": False,
                "error": "No suitable chunk found to write"
            }
        
        # Check if this operation is using parallel transfers
        is_parallel = (file_id in self.transfer_semaphores)
        
        if is_parallel:
            # Get the chunk index
            idx = next((i for i, c in enumerate(state.chunks) if c.start == chunk.start), None)
            
            # Check if a transfer is already active for this chunk
            if file_id in self.active_transfers and idx in self.active_transfers[file_id]:
                # Wait for the existing transfer to complete
                try:
                    result = await self.active_transfers[file_id][idx]
                    return result
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error waiting for active transfer: {str(e)}",
                        "file_id": file_id,
                        "chunk_index": idx
                    }
            
            # Add a new transfer task
            async def write_with_semaphore():
                async with self.transfer_semaphores[file_id]:
                    return await self._write_single_chunk(file_id, chunk_data, chunk, idx)
            
            task = anyio.create_task(write_with_semaphore())
            self.active_transfers[file_id][idx] = task
            
            # Return the result of the task
            try:
                result = await task
                # Remove from active transfers when done
                if idx in self.active_transfers[file_id]:
                    del self.active_transfers[file_id][idx]
                return result
            except Exception as e:
                if idx in self.active_transfers[file_id]:
                    del self.active_transfers[file_id][idx]
                return {
                    "success": False,
                    "error": f"Error in parallel transfer: {str(e)}",
                    "file_id": file_id,
                    "chunk_index": idx
                }
        else:
            # Non-parallel mode: directly call the single chunk writer
            return await self._write_single_chunk(file_id, chunk_data, chunk, chunk_index)
    
    async def finalize_write(self, file_id: str) -> Dict[str, Any]:
        """
        Finalize a resumable write operation.
        
        Completes a resumable write operation after verifying that the current user
        has write permission for the file. If all chunks have been successfully 
        written, this method marks the operation as complete and returns file metadata.
        
        Permission checks are performed to ensure the user still has write permission
        for the file, which might have changed since the operation started.
        
        Args:
            file_id: Unique identifier for the resumable operation
            
        Returns:
            result: Result of the operation with the following fields:
                - success: Whether the operation was successful
                - file_path: Path to the file in MFS
                - total_size: Total size of the file in bytes
                - hash: IPFS hash of the file (CID)
                - metadata: Additional metadata for the file
                - error: Error message if operation failed
                - permission_denied: True if user doesn't have permission (if applicable)
        """
        state = await self.load_state(file_id)
        if not state:
            return {
                "success": False,
                "error": f"No resumable operation found with ID {file_id}"
            }
        
        # Check write permission
        try:
            await self._check_permission(state.file_path, Permission.WRITE)
        except AccessDeniedException as e:
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "permission_denied": True
            }
        
        # Check if all chunks are completed
        if not state.completed:
            return {
                "success": False,
                "error": "Cannot finalize incomplete operation",
                "completion_percentage": state.get_completion_percentage(),
                "missing_chunks": [
                    {"start": c.start, "end": c.end, "status": c.status}
                    for c in state.chunks if c.status != "completed"
                ]
            }
        
        # Get file stats
        try:
            stats = await self.ipfs_client.files_stat(state.file_path)
            
            # Clear state
            await self.clear_state(file_id)
            
            return {
                "success": True,
                "file_path": state.file_path,
                "total_size": state.total_size,
                "hash": stats.get("Hash"),
                "metadata": state.metadata
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error finalizing write: {str(e)}"
            }
    
    async def start_resumable_read(self, 
                                  file_path: str,
                                  chunk_size: int = 1024 * 1024,
                                  metadata: Optional[Dict[str, Any]] = None,
                                  adaptive_chunking: bool = False,
                                  parallel_transfers: bool = False,
                                  max_parallel_chunks: Optional[int] = None) -> str:
        """
        Start a resumable read operation.
        
        Initiates a resumable read operation for the specified file path, after
        verifying that the current user has read permission for the file.
        
        This method first checks if the user has read permission for the file.
        If permissions are being enforced and the user doesn't have read permission,
        an AccessDeniedException is raised.
        
        The method stores operation metadata including the operation type ("read"),
        which is used by other methods to apply the appropriate permission checks
        during the operation lifecycle.
        
        Args:
            file_path: Path to the file in MFS
            chunk_size: Size of each chunk in bytes
            metadata: Additional metadata for the file
            adaptive_chunking: Whether to dynamically adjust chunk size based on network conditions
            parallel_transfers: Whether to enable parallel chunk transfers
            max_parallel_chunks: Maximum number of chunks to transfer in parallel (defaults to self.max_concurrent_transfers)
            
        Returns:
            file_id: Unique identifier for the resumable operation
            
        Raises:
            AccessDeniedException: If the user doesn't have permission to read the file
        """
        try:
            # Check read permission for the file path
            await self._check_permission(file_path, Permission.READ)
            
            # Create permissions for the file if needed
            if self.enforce_permissions and self.permission_manager:
                file_type = FileType.FILE
                await self._ensure_permissions(file_path, file_type)
            
            # Get file stats
            stats = await self.ipfs_client.files_stat(file_path)
            total_size = stats.get("Size", 0)
            
            file_id = self.generate_file_id(file_path)
            
            # Initialize metadata
            if metadata is None:
                metadata = {}
            
            # Set operation type in metadata
            metadata["operation_type"] = "read"
            
            # Create state
            state = ResumableFileState(
                file_path=file_path,
                total_size=total_size,
                chunk_size=chunk_size,
                metadata=metadata,
                adaptive_chunking=adaptive_chunking
            )
            
            # Add parallel transfer metadata if enabled
            if parallel_transfers:
                if "parallel_transfer" not in state.metadata:
                    state.metadata["parallel_transfer"] = {}
                
                state.metadata["parallel_transfer"]["enabled"] = True
                state.metadata["parallel_transfer"]["max_chunks"] = max_parallel_chunks or self.max_concurrent_transfers
            
            # Create semaphore for this operation if parallel transfers are enabled
            if parallel_transfers:
                max_parallel = max_parallel_chunks or self.max_concurrent_transfers
                self.transfer_semaphores[file_id] = anyio.Semaphore(max_parallel)
                self.active_transfers[file_id] = {}
            
            # Save state
            await self.save_state(file_id, state)
            
            return file_id
            
        except AccessDeniedException:
            # Re-raise permission errors
            raise
        except Exception as e:
            raise ValueError(f"Error starting resumable read: {str(e)}")
    
    async def _read_single_chunk(self, 
                           file_id: str, 
                           chunk: FileChunk,
                           chunk_index: Optional[int] = None) -> Dict[str, Any]:
        """
        Internal method to read a single chunk of data from a file.
        
        Args:
            file_id: Unique identifier for the resumable operation
            chunk: The chunk to read
            chunk_index: Index of the chunk (for reporting)
            
        Returns:
            result: Result of the operation including the chunk data
        """
        state = await self.load_state(file_id)
        if not state:
            return {
                "success": False,
                "error": f"No resumable operation found with ID {file_id}"
            }
        
        # Check read permission
        try:
            await self._check_permission(state.file_path, Permission.READ)
        except AccessDeniedException as e:
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "permission_denied": True
            }
        
        # Attempt to read the chunk
        try:
            # Track start time for performance monitoring
            start_time = time.time()
            
            # Read the chunk
            chunk_data = await self.ipfs_client.files_read(
                state.file_path,
                offset=chunk.start,
                count=chunk.size
            )
            
            # Calculate transfer time
            transfer_time = time.time() - start_time
            
            # Update adaptive chunking statistics
            if state.adaptive_chunking:
                state.update_optimal_chunk_size(chunk.size, transfer_time)
            
            # Update chunk status
            state.update_chunk(chunk, "completed")
            await self.save_state(file_id, state)
            
            # Report progress
            await self._report_progress(
                file_id, 
                state, 
                status="chunk_read",
                chunk_start=chunk.start,
                chunk_end=chunk.end,
                chunk_index=chunk_index,
                chunk_size=len(chunk_data),
                transfer_time=transfer_time,
                transfer_rate=chunk.size / transfer_time if transfer_time > 0 else 0
            )
            
            # Return success
            return {
                "success": True,
                "file_id": file_id,
                "chunk_start": chunk.start,
                "chunk_end": chunk.end,
                "chunk_data": chunk_data,
                "chunk_size": len(chunk_data),
                "completion_percentage": state.get_completion_percentage(),
                "completed": state.completed,
                "transfer_time": transfer_time,
                "transfer_rate": chunk.size / transfer_time if transfer_time > 0 else 0
            }
            
        except Exception as e:
            # Mark chunk as failed
            state.update_chunk(chunk, "failed")
            await self.save_state(file_id, state)
            
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "chunk_start": chunk.start,
                "chunk_end": chunk.end
            }
            
    async def read_chunk(self, 
                        file_id: str, 
                        chunk_index: Optional[int] = None,
                        offset: Optional[int] = None) -> Dict[str, Any]:
        """
        Read a chunk of data from a file.
        
        Args:
            file_id: Unique identifier for the resumable operation
            chunk_index: Index of the chunk to read (mutually exclusive with offset)
            offset: Byte offset to read from (mutually exclusive with chunk_index)
            
        Returns:
            result: Result of the operation including the chunk data
        """
        state = await self.load_state(file_id)
        if not state:
            return {
                "success": False,
                "error": f"No resumable operation found with ID {file_id}"
            }
        
        # Determine which chunk to read
        chunk = None
        if chunk_index is not None and 0 <= chunk_index < len(state.chunks):
            chunk = state.chunks[chunk_index]
        elif offset is not None:
            for c in state.chunks:
                if c.start <= offset < c.end:
                    chunk = c
                    break
        else:
            # Get next pending chunk
            chunk = state.get_next_chunk()
        
        if not chunk:
            return {
                "success": False,
                "error": "No suitable chunk found to read"
            }
        
        # Check if this operation is using parallel transfers
        is_parallel = (file_id in self.transfer_semaphores)
        
        if is_parallel:
            # Get the chunk index
            idx = next((i for i, c in enumerate(state.chunks) if c.start == chunk.start), None)
            
            # Check if a transfer is already active for this chunk
            if file_id in self.active_transfers and idx in self.active_transfers[file_id]:
                # Wait for the existing transfer to complete
                try:
                    result = await self.active_transfers[file_id][idx]
                    return result
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error waiting for active transfer: {str(e)}",
                        "file_id": file_id,
                        "chunk_index": idx
                    }
            
            # Add a new transfer task
            async def read_with_semaphore():
                async with self.transfer_semaphores[file_id]:
                    return await self._read_single_chunk(file_id, chunk, idx)
            
            task = anyio.create_task(read_with_semaphore())
            self.active_transfers[file_id][idx] = task
            
            # Return the result of the task
            try:
                result = await task
                # Remove from active transfers when done
                if idx in self.active_transfers[file_id]:
                    del self.active_transfers[file_id][idx]
                return result
            except Exception as e:
                if idx in self.active_transfers[file_id]:
                    del self.active_transfers[file_id][idx]
                return {
                    "success": False,
                    "error": f"Error in parallel transfer: {str(e)}",
                    "file_id": file_id,
                    "chunk_index": idx
                }
        else:
            # Non-parallel mode: directly call the single chunk reader
            return await self._read_single_chunk(file_id, chunk, chunk_index)
    
    async def finalize_read(self, file_id: str) -> Dict[str, Any]:
        """
        Finalize a resumable read operation.
        
        Completes a resumable read operation after verifying that the current user
        has read permission for the file. This method clears the operation state
        and returns file metadata.
        
        Permission checks are performed to ensure the user still has read permission
        for the file, which might have changed since the operation started.
        
        Args:
            file_id: Unique identifier for the resumable operation
            
        Returns:
            result: Result of the operation with the following fields:
                - success: Whether the operation was successful
                - file_path: Path to the file in MFS
                - total_size: Total size of the file in bytes
                - completion_percentage: Percentage of chunks that were successfully read
                - metadata: Additional metadata for the file
                - error: Error message if operation failed
                - permission_denied: True if user doesn't have permission (if applicable)
        """
        state = await self.load_state(file_id)
        if not state:
            return {
                "success": False,
                "error": f"No resumable operation found with ID {file_id}"
            }
        
        # Check read permission
        try:
            await self._check_permission(state.file_path, Permission.READ)
        except AccessDeniedException as e:
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "permission_denied": True
            }
        
        # Clear state
        await self.clear_state(file_id)
        
        return {
            "success": True,
            "file_path": state.file_path,
            "total_size": state.total_size,
            "completion_percentage": state.get_completion_percentage(),
            "metadata": state.metadata
        }
    
    async def read_multiple_chunks(self, 
                              file_id: str,
                              chunk_indices: Optional[List[int]] = None,
                              max_chunks: Optional[int] = None) -> Dict[str, Any]:
        """
        Read multiple chunks in parallel.
        
        This method is optimized for parallel transfers and will read multiple chunks
        concurrently up to the maximum allowed parallel transfers.
        
        Args:
            file_id: Unique identifier for the resumable operation
            chunk_indices: List of chunk indices to read (if None, reads next pending chunks)
            max_chunks: Maximum number of chunks to read (defaults to all pending if chunk_indices 
                        is None, or length of chunk_indices otherwise)
                        
        Returns:
            result: Dictionary with results for each chunk and overall success status
        """
        state = await self.load_state(file_id)
        if not state:
            return {
                "success": False,
                "error": f"No resumable operation found with ID {file_id}"
            }
        
        # Check read permission
        try:
            await self._check_permission(state.file_path, Permission.READ)
        except AccessDeniedException as e:
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "permission_denied": True
            }
        
        # Check if this operation supports parallel transfers
        is_parallel = (file_id in self.transfer_semaphores)
        if not is_parallel:
            return {
                "success": False,
                "error": "Parallel transfers not enabled for this operation"
            }
        
        # Determine which chunks to read
        chunks_to_read = []
        
        if chunk_indices is not None:
            # Read specified chunks
            for idx in chunk_indices:
                if 0 <= idx < len(state.chunks):
                    chunks_to_read.append((idx, state.chunks[idx]))
        else:
            # Read next pending chunks
            for idx, chunk in enumerate(state.chunks):
                if chunk.status == "pending":
                    chunks_to_read.append((idx, chunk))
                    
                    # Limit number of chunks if specified
                    if max_chunks is not None and len(chunks_to_read) >= max_chunks:
                        break
        
        if not chunks_to_read:
            return {
                "success": False,
                "error": "No chunks found to read"
            }
        
        # Limit number of chunks if specified
        if max_chunks is not None and len(chunks_to_read) > max_chunks:
            chunks_to_read = chunks_to_read[:max_chunks]
        
        # Create tasks for each chunk
        tasks = []
        for idx, chunk in chunks_to_read:
            # Check if a transfer is already active for this chunk
            if idx in self.active_transfers.get(file_id, {}):
                # Use existing task
                tasks.append((idx, self.active_transfers[file_id][idx]))
            else:
                # Create a new task
                async def read_with_semaphore(chunk_idx, chunk_data):
                    async with self.transfer_semaphores[file_id]:
                        return await self._read_single_chunk(file_id, chunk_data, chunk_idx)
                
                task = anyio.create_task(read_with_semaphore(idx, chunk))
                self.active_transfers.setdefault(file_id, {})[idx] = task
                tasks.append((idx, task))
        
        # Wait for all tasks to complete
        results = {
            "success": True,
            "file_id": file_id,
            "chunks": {},
            "completed_chunks": 0,
            "failed_chunks": 0
        }
        
        # Process completed tasks
        for idx, task in tasks:
            try:
                chunk_result = await task
                results["chunks"][idx] = chunk_result
                
                if chunk_result.get("success", False):
                    results["completed_chunks"] += 1
                else:
                    results["failed_chunks"] += 1
                    results["success"] = False  # Mark overall operation as failed if any chunk fails
                    
                    # If permission was denied, propagate to parent result
                    if chunk_result.get("permission_denied", False):
                        results["permission_denied"] = True
                    
                # Remove from active transfers
                if idx in self.active_transfers.get(file_id, {}):
                    del self.active_transfers[file_id][idx]
                    
            except Exception as e:
                # Handle task exception
                results["chunks"][idx] = {
                    "success": False,
                    "error": f"Exception in read task: {str(e)}",
                    "chunk_index": idx
                }
                results["failed_chunks"] += 1
                results["success"] = False
                
                # Remove from active transfers
                if idx in self.active_transfers.get(file_id, {}):
                    del self.active_transfers[file_id][idx]
        
        # Add overall statistics
        if state:
            results["completion_percentage"] = state.get_completion_percentage()
            results["completed"] = state.completed
        
        return results
        
    async def write_multiple_chunks(self, 
                               file_id: str,
                               chunks_data: List[Tuple[int, bytes]]) -> Dict[str, Any]:
        """
        Write multiple chunks in parallel.
        
        This method is optimized for parallel transfers and will write multiple chunks
        concurrently up to the maximum allowed parallel transfers.
        
        Args:
            file_id: Unique identifier for the resumable operation
            chunks_data: List of tuples (chunk_index, chunk_data) to write
                        
        Returns:
            result: Dictionary with results for each chunk and overall success status
        """
        state = await self.load_state(file_id)
        if not state:
            return {
                "success": False,
                "error": f"No resumable operation found with ID {file_id}"
            }
        
        # Check write permission
        try:
            await self._check_permission(state.file_path, Permission.WRITE)
        except AccessDeniedException as e:
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "permission_denied": True
            }
        
        # Check if this operation supports parallel transfers
        is_parallel = (file_id in self.transfer_semaphores)
        if not is_parallel:
            return {
                "success": False,
                "error": "Parallel transfers not enabled for this operation"
            }
        
        # Validate chunks
        valid_chunks = []
        for chunk_idx, chunk_data in chunks_data:
            if 0 <= chunk_idx < len(state.chunks):
                chunk = state.chunks[chunk_idx]
                if len(chunk_data) == chunk.size:
                    valid_chunks.append((chunk_idx, chunk_data, chunk))
                else:
                    return {
                        "success": False,
                        "error": f"Chunk data size ({len(chunk_data)}) doesn't match expected size ({chunk.size}) for chunk {chunk_idx}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Invalid chunk index: {chunk_idx}"
                }
        
        if not valid_chunks:
            return {
                "success": False,
                "error": "No valid chunks to write"
            }
        
        # Create tasks for each chunk
        tasks = []
        for idx, data, chunk in valid_chunks:
            # Check if a transfer is already active for this chunk
            if idx in self.active_transfers.get(file_id, {}):
                # Use existing task
                tasks.append((idx, self.active_transfers[file_id][idx]))
            else:
                # Create a new task
                async def write_with_semaphore(chunk_idx, chunk_data, chunk_obj):
                    async with self.transfer_semaphores[file_id]:
                        return await self._write_single_chunk(file_id, chunk_data, chunk_obj, chunk_idx)
                
                task = anyio.create_task(write_with_semaphore(idx, data, chunk))
                self.active_transfers.setdefault(file_id, {})[idx] = task
                tasks.append((idx, task))
        
        # Wait for all tasks to complete
        results = {
            "success": True,
            "file_id": file_id,
            "chunks": {},
            "completed_chunks": 0,
            "failed_chunks": 0
        }
        
        # Process completed tasks
        for idx, task in tasks:
            try:
                chunk_result = await task
                results["chunks"][idx] = chunk_result
                
                if chunk_result.get("success", False):
                    results["completed_chunks"] += 1
                else:
                    results["failed_chunks"] += 1
                    results["success"] = False  # Mark overall operation as failed if any chunk fails
                    
                    # If permission was denied, propagate to parent result
                    if chunk_result.get("permission_denied", False):
                        results["permission_denied"] = True
                    
                # Remove from active transfers
                if idx in self.active_transfers.get(file_id, {}):
                    del self.active_transfers[file_id][idx]
                    
            except Exception as e:
                # Handle task exception
                results["chunks"][idx] = {
                    "success": False,
                    "error": f"Exception in write task: {str(e)}",
                    "chunk_index": idx
                }
                results["failed_chunks"] += 1
                results["success"] = False
                
                # Remove from active transfers
                if idx in self.active_transfers.get(file_id, {}):
                    del self.active_transfers[file_id][idx]
        
        # Add overall statistics
        if state:
            results["completion_percentage"] = state.get_completion_percentage()
            results["completed"] = state.completed
        
        return results
        
    async def resume_operation(self, file_id: str) -> Dict[str, Any]:
        """
        Resume a paused or failed operation.
        
        Args:
            file_id: Unique identifier for the resumable operation
            
        Returns:
            result: Information about the resumed operation
        """
        state = await self.load_state(file_id)
        if not state:
            return {
                "success": False,
                "error": f"No resumable operation found with ID {file_id}"
            }
        
        # Determine operation type from metadata and check appropriate permission
        operation_type = state.metadata.get("operation_type", "read")  # Default to read
        
        try:
            # Check appropriate permission based on operation type
            if operation_type == "write":
                await self._check_permission(state.file_path, Permission.WRITE)
            else:  # read operation
                await self._check_permission(state.file_path, Permission.READ)
        except AccessDeniedException as e:
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "permission_denied": True
            }
        
        # Reset any in-progress chunks
        state.reset_in_progress_chunks()
        await self.save_state(file_id, state)
        
        # Report progress
        remaining_chunks = [
            {"start": c.start, "end": c.end, "size": c.size}
            for c in state.chunks if c.status != "completed"
        ]
        
        await self._report_progress(
            file_id, 
            state, 
            status="operation_resumed",
            remaining_chunks=remaining_chunks
        )
        
        return {
            "success": True,
            "file_id": file_id,
            "file_path": state.file_path,
            "total_size": state.total_size,
            "completion_percentage": state.get_completion_percentage(),
            "remaining_chunks": remaining_chunks
        }
    
    async def copy_resumable(self, source_id: str, destination_path: str) -> Dict[str, Any]:
        """
        Copy a file that was partially uploaded/downloaded to a new location.
        
        This is useful when you want to save a partial download to a different location.
        
        Args:
            source_id: File ID of the source resumable operation
            destination_path: Path to copy the file to
            
        Returns:
            result: Result of the operation
        """
        source_state = await self.load_state(source_id)
        if not source_state:
            return {
                "success": False,
                "error": f"No resumable operation found with ID {source_id}"
            }
        
        # Check read permission for source file
        try:
            await self._check_permission(source_state.file_path, Permission.READ)
        except AccessDeniedException as e:
            return {
                "success": False,
                "error": f"Read permission denied: {str(e)}",
                "source_id": source_id,
                "permission_denied": True
            }
        
        # Check write permission for destination path
        try:
            await self._check_permission(destination_path, Permission.WRITE)
        except AccessDeniedException as e:
            return {
                "success": False,
                "error": f"Write permission denied: {str(e)}",
                "destination_path": destination_path,
                "permission_denied": True
            }
        
        try:
            # Copy file
            await self.ipfs_client.files_cp(
                source_state.file_path,
                destination_path
            )
            
            # Create permissions for the destination file if needed
            if self.enforce_permissions and self.permission_manager:
                file_type = FileType.FILE
                await self._ensure_permissions(destination_path, file_type)
            
            return {
                "success": True,
                "source_path": source_state.file_path,
                "destination_path": destination_path,
                "completion_percentage": source_state.get_completion_percentage()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error copying file: {str(e)}"
            }


class ResumableReadStream:
    """
    Provides a file-like object for resumable reading from IPFS MFS.
    
    This class implements a file-like interface that can be used to read
    from IPFS MFS with resumable capabilities.
    """
    
    def __init__(self, 
                resumable: ResumableFileOperations, 
                file_id: str,
                buffer_size: int = 8192):
        """
        Initialize a resumable read stream.
        
        Args:
            resumable: ResumableFileOperations instance
            file_id: Unique identifier for the resumable operation
            buffer_size: Size of the read buffer
        """
        self.resumable = resumable
        self.file_id = file_id
        self.buffer_size = buffer_size
        self.position = 0
        self.buffer = bytearray()
        self.buffer_start = 0
        self.eof = False
        self.closed = False
    
    async def _fill_buffer(self) -> int:
        """Fill the buffer with data from the file."""
        if self.eof or self.closed:
            return 0
        
        # Check if we need to fill buffer
        if self.position >= self.buffer_start + len(self.buffer):
            # Read next chunk
            result = await self.resumable.read_chunk(
                self.file_id,
                offset=self.position
            )
            
            if not result.get("success"):
                raise IOError(f"Error reading from file: {result.get('error')}")
            
            # Update buffer
            self.buffer = result.get("chunk_data", b"")
            self.buffer_start = result.get("chunk_start", 0)
            
            # Check if EOF
            if len(self.buffer) == 0:
                self.eof = True
                return 0
            
            return len(self.buffer)
        
        return len(self.buffer) - (self.position - self.buffer_start)
    
    async def read(self, size: int = -1) -> bytes:
        """
        Read up to size bytes from the file.
        
        Args:
            size: Maximum number of bytes to read, -1 to read all available
            
        Returns:
            data: Bytes read from the file
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        if size < 0:
            # Read all available data
            chunks = []
            while not self.eof:
                await self._fill_buffer()
                if self.eof:
                    break
                
                # Get remaining data in buffer
                buffer_pos = self.position - self.buffer_start
                data = bytes(self.buffer[buffer_pos:])
                self.position += len(data)
                chunks.append(data)
            
            return b"".join(chunks)
        
        elif size == 0:
            return b""
        
        else:
            # Read specific size
            result = bytearray(size)
            bytes_read = 0
            
            while bytes_read < size and not self.eof:
                # Ensure buffer has data
                await self._fill_buffer()
                if self.eof and bytes_read == 0:
                    return b""
                
                # Copy from buffer to result
                buffer_pos = self.position - self.buffer_start
                bytes_to_copy = min(
                    size - bytes_read,
                    len(self.buffer) - buffer_pos
                )
                
                if bytes_to_copy <= 0:
                    break
                
                result[bytes_read:bytes_read + bytes_to_copy] = self.buffer[
                    buffer_pos:buffer_pos + bytes_to_copy
                ]
                
                self.position += bytes_to_copy
                bytes_read += bytes_to_copy
            
            return bytes(result[:bytes_read]) if bytes_read < size else bytes(result)
    
    async def seek(self, offset: int, whence: int = 0) -> int:
        """
        Change the stream position.
        
        Args:
            offset: Offset relative to position indicated by whence
            whence: 0 = start of file, 1 = current position, 2 = end of file
            
        Returns:
            new_position: New position in the file
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        # Get file size
        state = await self.resumable.load_state(self.file_id)
        if not state:
            raise ValueError(f"No resumable operation found with ID {self.file_id}")
        
        if whence == 0:  # Start of file
            new_position = offset
        elif whence == 1:  # Current position
            new_position = self.position + offset
        elif whence == 2:  # End of file
            new_position = state.total_size + offset
        else:
            raise ValueError(f"Invalid whence value: {whence}")
        
        # Clamp position to file size
        self.position = max(0, min(new_position, state.total_size))
        
        # Reset EOF flag
        self.eof = (self.position >= state.total_size)
        
        # Clear buffer if seeking outside it
        if self.position < self.buffer_start or self.position >= self.buffer_start + len(self.buffer):
            self.buffer = bytearray()
            self.buffer_start = 0
        
        return self.position
    
    async def tell(self) -> int:
        """Return the current position in the file."""
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        return self.position
    
    async def close(self):
        """Close the file."""
        if not self.closed:
            await self.resumable.finalize_read(self.file_id)
            self.closed = True
    
    async def __aenter__(self):
        """Enter context manager."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        await self.close()


class ResumableWriteStream:
    """
    Provides a file-like object for resumable writing to IPFS MFS.
    
    This class implements a file-like interface that can be used to write
    to IPFS MFS with resumable capabilities.
    """
    
    def __init__(self, 
                resumable: ResumableFileOperations, 
                file_id: str,
                buffer_size: int = 8192):
        """
        Initialize a resumable write stream.
        
        Args:
            resumable: ResumableFileOperations instance
            file_id: Unique identifier for the resumable operation
            buffer_size: Size of the write buffer
        """
        self.resumable = resumable
        self.file_id = file_id
        self.buffer_size = buffer_size
        self.position = 0
        self.buffer = bytearray()
        self.closed = False
    
    async def _flush_buffer(self) -> int:
        """Flush the buffer to the file."""
        if not self.buffer or self.closed:
            return 0
        
        # Get state to check chunk boundaries
        state = await self.resumable.load_state(self.file_id)
        if not state:
            raise ValueError(f"No resumable operation found with ID {self.file_id}")
        
        # Find chunk for current position
        buffer_start = self.position - len(self.buffer)
        chunk = None
        for c in state.chunks:
            if c.start <= buffer_start < c.end:
                chunk = c
                break
        
        if not chunk:
            raise ValueError(f"No chunk found for position {buffer_start}")
        
        # Ensure buffer aligns with chunk boundaries
        if buffer_start != chunk.start or len(self.buffer) > chunk.size:
            # Need to adjust buffer to match chunk boundaries
            if buffer_start < chunk.start:
                # Buffer starts before chunk
                offset = chunk.start - buffer_start
                self.buffer = self.buffer[offset:]
                buffer_start = chunk.start
            
            # Truncate buffer to chunk size
            buffer_size = min(len(self.buffer), chunk.end - buffer_start)
            self.buffer = self.buffer[:buffer_size]
        
        # Write the chunk
        bytes_to_write = bytes(self.buffer)
        result = await self.resumable.write_chunk(
            self.file_id,
            bytes_to_write,
            offset=buffer_start
        )
        
        if not result.get("success"):
            raise IOError(f"Error writing to file: {result.get('error')}")
        
        # Clear buffer
        bytes_written = len(self.buffer)
        self.buffer = bytearray()
        
        return bytes_written
    
    async def write(self, data: bytes) -> int:
        """
        Write a bytes object to the file.
        
        Args:
            data: Bytes to write
            
        Returns:
            bytes_written: Number of bytes written
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        # Add data to buffer
        self.buffer.extend(data)
        self.position += len(data)
        
        # Flush if buffer is large enough
        if len(self.buffer) >= self.buffer_size:
            await self._flush_buffer()
        
        return len(data)
    
    async def flush(self):
        """Flush the write buffer."""
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        await self._flush_buffer()
    
    async def seek(self, offset: int, whence: int = 0) -> int:
        """
        Change the stream position.
        
        Args:
            offset: Offset relative to position indicated by whence
            whence: 0 = start of file, 1 = current position, 2 = end of file
            
        Returns:
            new_position: New position in the file
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        # Flush buffer first
        await self._flush_buffer()
        
        # Get file size
        state = await self.resumable.load_state(self.file_id)
        if not state:
            raise ValueError(f"No resumable operation found with ID {self.file_id}")
        
        if whence == 0:  # Start of file
            new_position = offset
        elif whence == 1:  # Current position
            new_position = self.position + offset
        elif whence == 2:  # End of file
            new_position = state.total_size + offset
        else:
            raise ValueError(f"Invalid whence value: {whence}")
        
        # Clamp position to file size
        self.position = max(0, min(new_position, state.total_size))
        
        return self.position
    
    async def tell(self) -> int:
        """Return the current position in the file."""
        if self.closed:
            raise ValueError("I/O operation on closed file")
        
        return self.position
    
    async def close(self):
        """Close the file."""
        if not self.closed:
            await self._flush_buffer()
            await self.resumable.finalize_write(self.file_id)
            self.closed = True
    
    async def __aenter__(self):
        """Enter context manager."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        await self.close()


async def open_resumable(ipfs_client, 
                        file_path: str, 
                        mode: str = "rb", 
                        chunk_size: int = 1024 * 1024,
                        buffer_size: int = 8192,
                        metadata: Optional[Dict[str, Any]] = None,
                        state_dir: Optional[str] = None,
                        adaptive_chunking: bool = False) -> Union[ResumableReadStream, ResumableWriteStream]:
    """
    Open a file in MFS with resumable capabilities.
    
    This function provides a convenient way to open a file in MFS for resumable
    reading or writing, similar to the built-in open() function.
    
    Args:
        ipfs_client: IPFS client instance
        file_path: Path to the file in MFS
        mode: File mode, 'rb' for reading, 'wb' for writing
        chunk_size: Size of each chunk in bytes
        buffer_size: Size of the read/write buffer
        metadata: Additional metadata for the file
        state_dir: Directory to store state files
        adaptive_chunking: Whether to dynamically adjust chunk size based on network conditions
        
    Returns:
        file: File-like object for reading or writing
    """
    if mode not in ("rb", "wb"):
        raise ValueError(f"Unsupported mode: {mode}, only 'rb' and 'wb' are supported")
    
    # Create resumable operations instance
    resumable = ResumableFileOperations(ipfs_client, state_dir)
    
    if mode == "rb":
        # Start resumable read operation
        file_id = await resumable.start_resumable_read(
            file_path=file_path,
            chunk_size=chunk_size,
            metadata=metadata,
            adaptive_chunking=adaptive_chunking
        )
        
        # Create read stream
        return ResumableReadStream(resumable, file_id, buffer_size)
    
    else:  # mode == "wb"
        # Get file size
        try:
            stats = await ipfs_client.files_stat(file_path)
            total_size = stats.get("Size", 0)
        except Exception:
            # File doesn't exist, will be created
            total_size = 0
        
        # Start resumable write operation
        file_id = await resumable.start_resumable_write(
            file_path=file_path,
            total_size=total_size,
            chunk_size=chunk_size,
            metadata=metadata,
            adaptive_chunking=adaptive_chunking
        )
        
        # Create write stream
        return ResumableWriteStream(resumable, file_id, buffer_size)