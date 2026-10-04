"""
Data Migration Module for MCP Storage Manager.

This module provides functionality for migrating data between different storage backends
with advanced features like validation, scheduling, and policy-based migration.
"""

import logging
import time
import json
import os
import uuid
import hashlib
from typing import Dict, Any, List, Optional, Union, BinaryIO # Added BinaryIO
from enum import Enum
from datetime import datetime, timedelta
import threading
import queue

# Configure logger
logger = logging.getLogger(__name__)


class MigrationType(Enum):
    """Types of migration operations."""
    COPY = "copy"  # Copy data, keeping the original
    MOVE = "move"  # Copy data and delete the original after successful copy
    SYNC = "sync"  # Establish ongoing synchronization between backends


class ValidationLevel(Enum):
    """Levels of validation for migrated data."""
    NONE = "none"           # No validation
    EXISTS = "exists"       # Verify the data exists in target
    HASH = "hash"           # Verify hash of migrated data
    CONTENT = "content"     # Compare full content
    METADATA = "metadata"   # Verify metadata was preserved
    FULL = "full"           # Verify content and metadata


class MigrationStatus(Enum):
    """Possible statuses for migration operations."""
    PENDING = "pending"           # Waiting to be processed
    IN_PROGRESS = "in_progress"   # Currently being processed
    COMPLETED = "completed"       # Successfully completed
    FAILED = "failed"             # Failed to complete
    PARTIAL = "partial"           # Partially completed with issues
    SCHEDULED = "scheduled"       # Scheduled for future execution
    VALIDATING = "validating"     # Validation in progress
    VALIDATED = "validated"       # Successfully validated


class MigrationPriority(Enum):
    """Priority levels for migration tasks."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class MigrationResult:
    """Result of a migration operation."""
    
    def __init__(self, 
                 success: bool,
                 source_backend: str,
                 target_backend: str,
                 source_id: str,
                 target_id: Optional[str] = None,
                 status: MigrationStatus = MigrationStatus.COMPLETED,
                 error: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None,
                 validation_result: Optional[Dict[str, Any]] = None):
        """
        Initialize a migration result.
        
        Args:
            success: Whether the migration was successful
            source_backend: Name of the source backend
            target_backend: Name of the target backend
            source_id: Identifier in the source backend
            target_id: Identifier in the target backend
            status: Status of the migration
            error: Error message if failed
            details: Additional details about the migration
            validation_result: Results from validation
        """
        self.success = success
        self.source_backend = source_backend
        self.target_backend = target_backend
        self.source_id = source_id
        self.target_id = target_id
        self.status = status
        self.error = error
        self.details = details or {}
        self.validation_result = validation_result
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary."""
        return {
            "success": self.success,
            "source_backend": self.source_backend,
            "target_backend": self.target_backend,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "status": self.status.value,
            "error": self.error,
            "details": self.details,
            "validation_result": self.validation_result,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MigrationResult':
        """Create a result from a dictionary."""
        return cls(
            success=data["success"],
            source_backend=data["source_backend"],
            target_backend=data["target_backend"],
            source_id=data["source_id"],
            target_id=data.get("target_id"),
            status=MigrationStatus(data["status"]),
            error=data.get("error"),
            details=data.get("details", {}),
            validation_result=data.get("validation_result")
        )


class MigrationTask:
    """Task for migrating data between backends."""
    
    def __init__(self,
                 source_backend: str,
                 target_backend: str,
                 source_id: str,
                 migration_type: MigrationType = MigrationType.COPY,
                 validation_level: ValidationLevel = ValidationLevel.HASH,
                 priority: MigrationPriority = MigrationPriority.NORMAL,
                 options: Optional[Dict[str, Any]] = None,
                 scheduled_time: Optional[datetime] = None,
                 source_container: Optional[str] = None,
                 target_container: Optional[str] = None,
                 target_path: Optional[str] = None):
        """
        Initialize a migration task.
        
        Args:
            source_backend: Name of the source backend
            target_backend: Name of the target backend
            source_id: Identifier in the source backend
            migration_type: Type of migration operation
            validation_level: Level of validation to perform
            priority: Priority level of the task
            options: Additional options for the migration
            scheduled_time: When to execute the task (None for immediate)
            source_container: Container/bucket in source backend
            target_container: Container/bucket in target backend
            target_path: Optional path in target backend
        """
        self.id = str(uuid.uuid4())
        self.source_backend = source_backend
        self.target_backend = target_backend
        self.source_id = source_id
        self.migration_type = migration_type
        self.validation_level = validation_level
        self.priority = priority
        self.options = options or {}
        self.scheduled_time = scheduled_time
        self.source_container = source_container
        self.target_container = target_container
        self.target_path = target_path
        
        self.status = MigrationStatus.SCHEDULED if scheduled_time else MigrationStatus.PENDING
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.result = None
        self.attempts = 0
        self.max_attempts = self.options.get("max_attempts", 3)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the task to a dictionary."""
        return {
            "id": self.id,
            "source_backend": self.source_backend,
            "target_backend": self.target_backend,
            "source_id": self.source_id,
            "migration_type": self.migration_type.value,
            "validation_level": self.validation_level.value,
            "priority": self.priority.value,
            "options": self.options,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "source_container": self.source_container,
            "target_container": self.target_container,
            "target_path": self.target_path,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "result": self.result.to_dict() if self.result else None,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MigrationTask':
        """Create a task from a dictionary."""
        task = cls(
            source_backend=data["source_backend"],
            target_backend=data["target_backend"],
            source_id=data["source_id"],
            migration_type=MigrationType(data["migration_type"]),
            validation_level=ValidationLevel(data["validation_level"]),
            priority=MigrationPriority(data["priority"]),
            options=data.get("options", {}),
            scheduled_time=datetime.fromisoformat(data["scheduled_time"]) if data.get("scheduled_time") else None,
            source_container=data.get("source_container"),
            target_container=data.get("target_container"),
            target_path=data.get("target_path")
        )
        
        task.id = data["id"]
        task.status = MigrationStatus(data["status"])
        task.created_at = datetime.fromisoformat(data["created_at"])
        task.updated_at = datetime.fromisoformat(data["updated_at"])
        task.result = MigrationResult.from_dict(data["result"]) if data.get("result") else None
        task.attempts = data.get("attempts", 0)
        task.max_attempts = data.get("max_attempts", 3)
        
        return task
    
    def update_status(self, status: MigrationStatus) -> None:
        """Update the status of the task."""
        self.status = status
        self.updated_at = datetime.now()


class MigrationManager:
    """Manager for data migration between backends."""
    
    def __init__(self, backend_registry: Dict[str, Any], max_workers: int = 3):
        """
        Initialize the migration manager.
        
        Args:
            backend_registry: Dictionary mapping backend names to instances
            max_workers: Maximum number of concurrent migration tasks
        """
        self.backend_registry = backend_registry
        self.max_workers = max_workers
        
        # Queue for pending tasks
        self.task_queue = queue.PriorityQueue()
        
        # Dictionary to store tasks by ID
        self.tasks = {}
        
        # List to store completed tasks (limited size)
        self.completed_tasks = []
        self.max_completed_tasks = 1000
        
        # Create worker threads
        self.workers = []
        self.worker_lock = threading.RLock()
        self.active_workers = 0
        self.shutdown_flag = threading.Event()
        
        # Start worker threads
        self._start_workers()
        
        # Scheduled task thread
        self.schedule_thread = threading.Thread(target=self._schedule_runner, daemon=True)
        self.schedule_thread.start()
    
    def _start_workers(self) -> None:
        """Start worker threads."""
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_thread, 
                                     name=f"MigrationWorker-{i+1}",
                                     daemon=True)
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {self.max_workers} migration worker threads")
    
    def _worker_thread(self) -> None:
        """Worker thread function to process migration tasks."""
        while not self.shutdown_flag.is_set():
            try:
                # Get a task from the queue with timeout
                try:
                    priority, _, task = self.task_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Mark as active
                with self.worker_lock:
                    self.active_workers += 1
                
                # Process the task
                self._process_task(task)
                
                # Mark task as done
                self.task_queue.task_done()
                
                # Decrement active worker count
                with self.worker_lock:
                    self.active_workers -= 1
                    
            except Exception as e:
                logger.error(f"Error in migration worker: {e}")
                # Decrement active worker count on error
                with self.worker_lock:
                    self.active_workers -= 1
    
    def _schedule_runner(self) -> None:
        """Thread function to handle scheduled tasks."""
        while not self.shutdown_flag.is_set():
            try:
                # Check for due scheduled tasks
                now = datetime.now()
                tasks_to_queue = []
                
                with self.worker_lock:
                    for task_id, task in self.tasks.items():
                        if (task.status == MigrationStatus.SCHEDULED and 
                            task.scheduled_time and 
                            task.scheduled_time <= now):
                            # Update task status
                            task.status = MigrationStatus.PENDING
                            task.updated_at = now
                            tasks_to_queue.append(task)
                
                # Queue the due tasks
                for task in tasks_to_queue:
                    logger.info(f"Scheduling due task {task.id}: {task.source_backend}->{task.target_backend}")
                    self._queue_task(task)
                    
                # Sleep before checking again    
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in schedule runner: {e}")
                time.sleep(30)  # Wait longer on error
    
    def _process_task(self, task: MigrationTask) -> None:
        """
        Process a migration task.
        
        Args:
            task: The migration task to process
        """
        logger.info(f"Processing migration task {task.id}: {task.source_backend}->{task.target_backend}")
        
        # Update task status
        task.status = MigrationStatus.IN_PROGRESS
        task.updated_at = datetime.now()
        task.attempts += 1
        
        try:
            # Get source and target backends
            source_backend = self.backend_registry.get(task.source_backend)
            target_backend = self.backend_registry.get(task.target_backend)
            
            if not source_backend:
                raise ValueError(f"Source backend '{task.source_backend}' not found")
            
            if not target_backend:
                raise ValueError(f"Target backend '{task.target_backend}' not found")
            
            # Perform the migration based on the type
            if task.migration_type == MigrationType.COPY:
                result = self._migrate_copy(task, source_backend, target_backend)
            elif task.migration_type == MigrationType.MOVE:
                result = self._migrate_move(task, source_backend, target_backend)
            elif task.migration_type == MigrationType.SYNC:
                result = self._migrate_sync(task, source_backend, target_backend)
            else:
                raise ValueError(f"Unsupported migration type: {task.migration_type}")
            
            # Store the result
            task.result = result
            
            # Update task status based on result
            if result.success:
                task.status = MigrationStatus.VALIDATED if task.validation_level != ValidationLevel.NONE else MigrationStatus.COMPLETED
            else:
                # Check if we should retry
                if task.attempts < task.max_attempts:
                    # Schedule retry
                    retry_delay = task.options.get("retry_delay", 60)  # Default 60 seconds
                    task.scheduled_time = datetime.now() + timedelta(seconds=retry_delay)
                    task.status = MigrationStatus.SCHEDULED
                    logger.info(f"Scheduling retry for task {task.id} in {retry_delay} seconds")
                else:
                    task.status = MigrationStatus.FAILED
                    logger.warning(f"Migration task {task.id} failed after {task.attempts} attempts")
            
            # Update task timestamp
            task.updated_at = datetime.now()
            
            # Store completed task
            if task.status in [MigrationStatus.COMPLETED, MigrationStatus.VALIDATED, MigrationStatus.FAILED]:
                self._add_to_completed(task)
            
        except Exception as e:
            logger.error(f"Error processing migration task {task.id}: {e}")
            
            # Create failure result
            task.result = MigrationResult(
                success=False,
                source_backend=task.source_backend,
                target_backend=task.target_backend,
                source_id=task.source_id,
                status=MigrationStatus.FAILED,
                error=str(e),
                details={"exception": str(e), "exception_type": type(e).__name__}
            )
            
            # Check if we should retry
            if task.attempts < task.max_attempts:
                # Schedule retry
                retry_delay = task.options.get("retry_delay", 60)  # Default 60 seconds
                task.scheduled_time = datetime.now() + timedelta(seconds=retry_delay)
                task.status = MigrationStatus.SCHEDULED
                logger.info(f"Scheduling retry for task {task.id} in {retry_delay} seconds")
            else:
                task.status = MigrationStatus.FAILED
                # Add to completed tasks
                self._add_to_completed(task)
                
            # Update task timestamp
            task.updated_at = datetime.now()
    
    def _migrate_copy(self, task: MigrationTask, source_backend: Any, target_backend: Any) -> MigrationResult:
        """
        Copy data from source to target backend.
        
        Args:
            task: Migration task
            source_backend: Source backend instance
            target_backend: Target backend instance
            
        Returns:
            Result of the migration
        """
        # Start with metadata for tracking
        migration_metadata = {
            "migration_id": task.id,
            "migration_type": task.migration_type.value,
            "source_backend": task.source_backend,
            "source_id": task.source_id,
            "migration_time": datetime.now().isoformat(),
            **task.options.get("metadata", {})
        }
        
        start_time = time.time()
        
        # Check if source backend has a migrate_to method (optimized path)
        if hasattr(source_backend, 'migrate_to'):
            logger.info(f"Using optimized migrate_to path for {task.id}")
            
            # Prepare options
            options = {
                "verify": task.validation_level != ValidationLevel.NONE,
                "validation_strategy": task.validation_level.value,
                "migration_metadata": migration_metadata,
                **task.options
            }
            
            # Call the optimized migration method
            migrate_result = source_backend.migrate_to(
                source_identifier=task.source_id,
                target_backend=target_backend,
                target_container=task.target_container,
                target_path=task.target_path,
                source_container=task.source_container,
                options=options
            )
            
            # Create result from the backend's response
            result = MigrationResult(
                success=migrate_result.get("success", False),
                source_backend=task.source_backend,
                target_backend=task.target_backend,
                source_id=task.source_id,
                target_id=migrate_result.get("target_identifier"),
                status=MigrationStatus.COMPLETED if migrate_result.get("success", False) else MigrationStatus.FAILED,
                error=migrate_result.get("error"),
                details=migrate_result,
                validation_result=migrate_result.get("verification")
            )
            
        else:
            # Manual migration path
            logger.info(f"Using manual migration path for {task.id}")
            
            # Retrieve content from source
            retrieve_result = source_backend.get_content(task.source_id, container=task.source_container)
            
            if not retrieve_result.get("success", False):
                # Failed to retrieve content
                return MigrationResult(
                    success=False,
                    source_backend=task.source_backend,
                    target_backend=task.target_backend,
                    source_id=task.source_id,
                    status=MigrationStatus.FAILED,
                    error=f"Failed to retrieve content: {retrieve_result.get('error', 'Unknown error')}",
                    details=retrieve_result
                )
            
            # Get content and metadata
            content = retrieve_result.get("data")
            
            # Try to get metadata if available
            try:
                metadata_result = source_backend.get_metadata(task.source_id, container=task.source_container)
                source_metadata = metadata_result.get("metadata", {}) if metadata_result.get("success", False) else {}
            except Exception as e:
                logger.warning(f"Error retrieving metadata for {task.id}: {e}")
                source_metadata = {}
            
            # Prepare metadata for target
            target_metadata = {**source_metadata, **migration_metadata}
            
            # Store in target
            store_options = {"metadata": target_metadata}
            
            store_result = target_backend.add_content(
                content=content,
                metadata={
                    **target_metadata,
                    "container": task.target_container,
                    "path": task.target_path
                }
            )
            
            if not store_result.get("success", False):
                # Failed to store content
                return MigrationResult(
                    success=False,
                    source_backend=task.source_backend,
                    target_backend=task.target_backend,
                    source_id=task.source_id,
                    status=MigrationStatus.FAILED,
                    error=f"Failed to store content: {store_result.get('error', 'Unknown error')}",
                    details={"retrieve_result": retrieve_result, "store_result": store_result}
                )
            
            # Success - get target ID
            target_id = store_result.get("identifier")
            
            # Validate if required
            validation_result = None
            if task.validation_level != ValidationLevel.NONE:
                validation_result = self._validate_migration(
                    task, source_backend, target_backend, content, target_id
                )
                
                if not validation_result.get("success", False):
                    # Validation failed
                    return MigrationResult(
                        success=False,
                        source_backend=task.source_backend,
                        target_backend=task.target_backend,
                        source_id=task.source_id,
                        target_id=target_id,
                        status=MigrationStatus.FAILED,
                        error=f"Validation failed: {validation_result.get('error', 'Unknown error')}",
                        details={"retrieve_result": retrieve_result, "store_result": store_result},
                        validation_result=validation_result
                    )
            
            # Build successful result
            result = MigrationResult(
                success=True,
                source_backend=task.source_backend,
                target_backend=task.target_backend,
                source_id=task.source_id,
                target_id=target_id,
                status=MigrationStatus.VALIDATED if validation_result else MigrationStatus.COMPLETED,
                details={
                    "retrieve_result": retrieve_result,
                    "store_result": store_result,
                    "duration": time.time() - start_time
                },
                validation_result=validation_result
            )
        
        return result
    
    def _migrate_move(self, task: MigrationTask, source_backend: Any, target_backend: Any) -> MigrationResult:
        """
        Move data from source to target backend (copy then delete).
        
        Args:
            task: Migration task
            source_backend: Source backend instance
            target_backend: Target backend instance
            
        Returns:
            Result of the migration
        """
        # First copy the content
        copy_result = self._migrate_copy(task, source_backend, target_backend)
        
        # If copy failed, return the failure
        if not copy_result.success:
            return copy_result
        
        # If copy succeeded, delete from source
        delete_result = source_backend.remove_content(task.source_id, container=task.source_container)
        
        # Add deletion info to result
        copy_result.details["delete_result"] = delete_result
        copy_result.details["delete_success"] = delete_result.get("success", False)
        
        # If deletion failed, mark as partial
        if not delete_result.get("success", False):
            copy_result.status = MigrationStatus.PARTIAL
            copy_result.error = f"Data copied successfully but failed to delete from source: {delete_result.get('error', 'Unknown error')}"
        
        return copy_result
    
    def _migrate_sync(self, task: MigrationTask, source_backend: Any, target_backend: Any) -> MigrationResult:
        """
        Synchronize data between backends.
        
        Args:
            task: Migration task
            source_backend: Source backend instance
            target_backend: Target backend instance
            
        Returns:
            Result of the migration
        """
        # Sync is not fully implemented yet, fall back to copy
        logger.warning(f"Sync migration not fully implemented, falling back to copy for {task.id}")
        return self._migrate_copy(task, source_backend, target_backend)
    
    def _validate_migration(self, task: MigrationTask, source_backend: Any, target_backend: Any, 
                           content: Optional[bytes] = None, target_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate migrated content.
        
        Args:
            task: Migration task
            source_backend: Source backend instance
            target_backend: Target backend instance
            content: Original content if available
            target_id: Target content ID
            
        Returns:
            Validation result dictionary
        """
        validation_level = task.validation_level
        
        # Basic existence check
        if validation_level == ValidationLevel.EXISTS:
            exists = target_backend.exists(target_id, container=task.target_container)
            return {
                "success": exists,
                "validation_level": validation_level.value,
                "error": None if exists else "Content doesn't exist in target"
            }
        
        # Hash validation
        if validation_level == ValidationLevel.HASH:
            # Try to get source metadata with hash
            source_metadata = source_backend.get_metadata(task.source_id, container=task.source_container)
            target_metadata = target_backend.get_metadata(target_id, container=task.target_container)
            
            if not source_metadata.get("success", False) or not target_metadata.get("success", False):
                return {
                    "success": False,
                    "validation_level": validation_level.value,
                    "error": "Failed to retrieve metadata for hash validation"
                }
            
            # Extract hash values (different backends might use different field names)
            source_hash = self._extract_hash(source_metadata.get("metadata", {}))
            target_hash = self._extract_hash(target_metadata.get("metadata", {}))
            
            if not source_hash or not target_hash:
                logger.warning(f"Hash validation not possible for {task.id}, falling back to content validation")
                # Fall back to content validation
                validation_level = ValidationLevel.CONTENT
            else:
                return {
                    "success": source_hash == target_hash,
                    "validation_level": validation_level.value,
                    "error": None if source_hash == target_hash else "Hash mismatch",
                    "source_hash": source_hash,
                    "target_hash": target_hash
                }
        
        # Content validation
        if validation_level == ValidationLevel.CONTENT:
            # If we don't already have the content, retrieve it
            if content is None:
                source_result = source_backend.get_content(task.source_id, container=task.source_container)
                if not source_result.get("success", False):
                    return {
                        "success": False,
                        "validation_level": validation_level.value,
                        "error": f"Failed to retrieve source content for validation: {source_result.get('error', 'Unknown error')}"
                    }
                content = source_result.get("data")
            
            # Get target content
            target_result = target_backend.get_content(target_id, container=task.target_container)
            if not target_result.get("success", False):
                return {
                    "success": False,
                    "validation_level": validation_level.value,
                    "error": f"Failed to retrieve target content for validation: {target_result.get('error', 'Unknown error')}"
                }
            
            target_content = target_result.get("data")
            
            # Compare content
            content_match = content == target_content
            
            return {
                "success": content_match,
                "validation_level": validation_level.value,
                "error": None if content_match else "Content mismatch",
                "source_size": len(content),
                "target_size": len(target_content)
            }
        
        # Metadata validation
        if validation_level == ValidationLevel.METADATA:
            # Get source and target metadata
            source_metadata = source_backend.get_metadata(task.source_id, container=task.source_container)
            target_metadata = target_backend.get_metadata(target_id, container=task.target_container)
            
            if not source_metadata.get("success", False) or not target_metadata.get("success", False):
                return {
                    "success": False,
                    "validation_level": validation_level.value,
                    "error": "Failed to retrieve metadata for validation"
                }
            
            # Extract metadata fields (excluding backend-specific fields)
            s_meta = source_metadata.get("metadata", {})
            t_meta = target_metadata.get("metadata", {})
            
            # Check essential fields
            missing_fields = []
            for key, value in s_meta.items():
                # Skip backend-specific fields
                if key in ["backend", "identifier"]:
                    continue
                
                # Check if key exists in target metadata
                if key not in t_meta:
                    missing_fields.append(key)
            
            return {
                "success": len(missing_fields) == 0,
                "validation_level": validation_level.value,
                "error": None if len(missing_fields) == 0 else f"Missing metadata fields: {', '.join(missing_fields)}",
                "missing_fields": missing_fields
            }
        
        # Full validation (content + metadata)
        if validation_level == ValidationLevel.FULL:
            # Perform content validation
            content_validation = self._validate_migration(
                task, source_backend, target_backend, content, target_id
            )
            
            # Save original validation level
            original_level = task.validation_level
            
            # Perform metadata validation
            task.validation_level = ValidationLevel.METADATA
            metadata_validation = self._validate_migration(
                task, source_backend, target_backend, content, target_id
            )
            
            # Restore original validation level
            task.validation_level = original_level
            
            # Combine results
            success = content_validation.get("success", False) and metadata_validation.get("success", False)
            
            return {
                "success": success,
                "validation_level": validation_level.value,
                "error": None if success else "Full validation failed",
                "content_validation": content_validation,
                "metadata_validation": metadata_validation
            }
        
        # NONE validation level or unknown
        return {
            "success": True,
            "validation_level": ValidationLevel.NONE.value,
            "message": "No validation performed"
        }
    
    def _extract_hash(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Extract hash value from metadata.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            Hash value if found, None otherwise
        """
        # Different backends might use different field names for hash
        hash_fields = ["hash", "cid", "etag", "md5", "sha256", "content_hash"]
        
        for field in hash_fields:
            if field in metadata and metadata[field]:
                return metadata[field]
        
        return None
    
    def create_task(self, source_backend: str, target_backend: str, source_id: str, **kwargs) -> str:
        """
        Create a migration task.
        
        Args:
            source_backend: Name of the source backend
            target_backend: Name of the target backend
            source_id: Identifier in the source backend
            **kwargs: Additional options
            
        Returns:
            Task ID
        """
        # Extract options
        migration_type = kwargs.get("migration_type", MigrationType.COPY)
        if isinstance(migration_type, str):
            migration_type = MigrationType(migration_type)
        
        validation_level = kwargs.get("validation_level", ValidationLevel.HASH)
        if isinstance(validation_level, str):
            validation_level = ValidationLevel(validation_level)
        
        priority = kwargs.get("priority", MigrationPriority.NORMAL)
        if isinstance(priority, int):
            priority = MigrationPriority(priority)
        
        # Create task
        task = MigrationTask(
            source_backend=source_backend,
            target_backend=target_backend,
            source_id=source_id,
            migration_type=migration_type,
            validation_level=validation_level,
            priority=priority,
            options=kwargs.get("options", {}),
            scheduled_time=kwargs.get("scheduled_time"),
            source_container=kwargs.get("source_container"),
            target_container=kwargs.get("target_container"),
            target_path=kwargs.get("target_path")
        )
        
        # Add to tasks dictionary
        with self.worker_lock:
            self.tasks[task.id] = task
        
        # If not scheduled for future, add to queue
        if task.status == MigrationStatus.PENDING:
            self._queue_task(task)
        
        logger.info(f"Created migration task {task.id}: {source_backend}->{target_backend}")
        return task.id
    
    def _queue_task(self, task: MigrationTask) -> None:
        """
        Add a task to the queue based on priority.
        
        Args:
            task: Task to queue
        """
        # Priority queue uses lowest value first, so negate priority value
        self.task_queue.put((-task.priority.value, time.time(), task))
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task dictionary or None if not found
        """
        with self.worker_lock:
            task = self.tasks.get(task_id)
            if not task:
                # Check completed tasks
                for completed_task in self.completed_tasks:
                    if completed_task.id == task_id:
                        return completed_task.to_dict()
                return None
            
            return task.to_dict()
    
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a pending or scheduled task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Result dictionary
        """
        with self.worker_lock:
            task = self.tasks.get(task_id)
            if not task:
                return {"success": False, "error": f"Task {task_id} not found"}
            
            # Can only cancel pending or scheduled tasks
            if task.status not in [MigrationStatus.PENDING, MigrationStatus.SCHEDULED]:
                return {
                    "success": False,
                    "error": f"Cannot cancel task with status {task.status.value}"
                }
            
            # Update task status
            task.status = MigrationStatus.FAILED
            task.error = "Canceled by user"
            task.updated_at = datetime.now()
            
            # Add to completed tasks
            self._add_to_completed(task)
            
            # Remove from tasks dictionary
            del self.tasks[task_id]
            
            return {"success": True, "message": f"Task {task_id} canceled"}
    
    def _add_to_completed(self, task: MigrationTask) -> None:
        """
        Add a task to the completed tasks list.
        
        Args:
            task: Completed task
        """
        with self.worker_lock:
            # Add to completed tasks
            self.completed_tasks.append(task)
            
            # Remove oldest if exceeding limit
            while len(self.completed_tasks) > self.max_completed_tasks:
                self.completed_tasks.pop(0)
            
            # Remove from active tasks if present
            if task.id in self.tasks:
                del self.tasks[task.id]
    
    def list_tasks(self, status: Optional[Union[MigrationStatus, str]] = None, 
                  source_backend: Optional[str] = None,
                  target_backend: Optional[str] = None,
                  include_completed: bool = False) -> List[Dict[str, Any]]:
        """
        List migration tasks.
        
        Args:
            status: Optional status filter
            source_backend: Optional source backend filter
            target_backend: Optional target backend filter
            include_completed: Whether to include completed tasks
            
        Returns:
            List of task dictionaries
        """
        # Convert string status to enum
        if isinstance(status, str):
            try:
                status = MigrationStatus(status)
            except ValueError:
                pass
        
        tasks_list = []
        
        with self.worker_lock:
            # Add active tasks
            for task in self.tasks.values():
                # Apply filters
                if status and task.status != status:
                    continue
                if source_backend and task.source_backend != source_backend:
                    continue
                if target_backend and task.target_backend != target_backend:
                    continue
                
                tasks_list.append(task.to_dict())
            
            # Add completed tasks if requested
            if include_completed:
                for task in self.completed_tasks:
                    # Apply filters
                    if status and task.status != status:
                        continue
                    if source_backend and task.source_backend != source_backend:
                        continue
                    if target_backend and task.target_backend != target_backend:
                        continue
                    
                    tasks_list.append(task.to_dict())
        
        return tasks_list
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get migration statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0,
            "scheduled": 0,
            "partial": 0,
            "validating": 0,
            "validated": 0,
            "active_workers": 0,
            "queue_size": 0,
            "total_completed": 0
        }
        
        with self.worker_lock:
            # Count by status
            for task in self.tasks.values():
                status = task.status.value
                if status in stats:
                    stats[status] += 1
            
            # Add completed task counts
            for task in self.completed_tasks:
                status = task.status.value
                if status in stats:
                    stats[status] += 1
            
            stats["active_workers"] = self.active_workers
            stats["queue_size"] = self.task_queue.qsize()
            stats["total_completed"] = len(self.completed_tasks)
        
        return stats
    
    def shutdown(self) -> None:
        """Shutdown the migration manager."""
        logger.info("Shutting down migration manager")
        self.shutdown_flag.set()
        
        # Wait for workers to finish
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=1.0)
        
        # Wait for schedule thread to finish
        if self.schedule_thread.is_alive():
            self.schedule_thread.join(timeout=1.0)
        
        logger.info("Migration manager shutdown complete")


def calculate_content_hash(content: Union[bytes, BinaryIO]) -> str:
    """
    Calculate SHA-256 hash of content.
    
    Args:
        content: Content as bytes or file-like object
        
    Returns:
        Hex digest of the hash
    """
    hasher = hashlib.sha256()
    
    if isinstance(content, bytes):
        hasher.update(content)
    else:
        # File-like object
        for chunk in iter(lambda: content.read(4096), b''):
            hasher.update(chunk)
        
        # Reset file pointer if possible
        if hasattr(content, 'seek'):
            content.seek(0)
    
    return hasher.hexdigest()


def create_migration_manager(backend_registry: Dict[str, Any], max_workers: int = 3) -> MigrationManager:
    """
    Create a migration manager.
    
    Args:
        backend_registry: Dictionary mapping backend names to instances
        max_workers: Maximum number of concurrent migration tasks
        
    Returns:
        MigrationManager instance
    """
    return MigrationManager(backend_registry, max_workers)
