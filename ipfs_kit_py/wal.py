"""
Write-Ahead Log (WAL) system for IPFS Kit.

This module provides a Write-Ahead Log implementation for ensuring data consistency
and crash recovery for IPFS operations. It tracks and persists operations to be
performed against backend storage systems, ensuring that operations can be
recovered and completed even in the event of a crash or failure.

Key features:
1. Atomic operation logging and replay
2. Multi-backend support (IPFS, S3, etc.)
3. Operation status tracking
4. Sequential execution guarantee
5. Crash recovery and resume
"""

import os
import json
import time
import uuid
import logging
import threading
import shutil
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)

class OperationType(str, Enum):
    """Types of operations supported by the WAL."""
    ADD = "add"
    GET = "get"
    PIN = "pin"
    UNPIN = "unpin"
    RM = "rm"
    BACKUP = "backup"
    RESTORE = "restore"
    CUSTOM = "custom"

class OperationStatus(str, Enum):
    """Status values for operations in the WAL."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class BackendType(str, Enum):
    """Backend storage types supported by the WAL."""
    IPFS = "ipfs"
    S3 = "s3"
    STORACHA = "storacha"
    FILESYSTEM = "filesystem"
    MEMORY = "memory"
    CUSTOM = "custom"

class WAL:
    """
    Base Write-Ahead Log implementation.
    
    This class implements a simple WAL that logs operations to be performed
    against backend storage systems. It ensures that operations can be
    recovered and completed even in the event of a crash or failure.
    """
    
    def __init__(
        self,
        base_path: str = "~/.ipfs_kit/wal",
        max_retries: int = 3,
        retry_delay: int = 5,
        operation_timeout: int = 60 * 30,  # 30 minutes default timeout
    ):
        """
        Initialize the WAL.
        
        Args:
            base_path: Base directory path for WAL storage
            max_retries: Maximum number of retries for failed operations
            retry_delay: Delay between retries in seconds
            operation_timeout: Maximum time in seconds an operation can be in processing state
        """
        self.base_path = os.path.expanduser(base_path)
        self.operations_dir = os.path.join(self.base_path, "operations")
        self.logs_dir = os.path.join(self.base_path, "logs")
        self.temp_dir = os.path.join(self.base_path, "temp")
        
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.operation_timeout = operation_timeout
        
        # Initialize in-memory operation tracking
        self.operations = {}  # operation_id -> operation_dict
        self.operation_handlers = {}  # operation_type -> handler_function
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Create directory structure if it doesn't exist
        self._ensure_directories()
        
        # Register default operation handlers
        self._register_default_handlers()
        
        # Load existing operations from disk
        self._load_operations()
        
        logger.info(f"WAL initialized at {self.base_path}")
        
    def _ensure_directories(self):
        """Ensure the required directories exist."""
        os.makedirs(self.operations_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def _register_default_handlers(self):
        """Register default operation handlers."""
        # This would be implemented by subclasses
        pass
        
    def _load_operations(self):
        """Load existing operations from disk."""
        try:
            operation_files = [f for f in os.listdir(self.operations_dir) if f.endswith(".json")]
            
            for op_file in operation_files:
                try:
                    with open(os.path.join(self.operations_dir, op_file), 'r') as f:
                        operation = json.load(f)
                        
                    if "operation_id" in operation:
                        self.operations[operation["operation_id"]] = operation
                except Exception as e:
                    logger.error(f"Error loading operation from {op_file}: {e}")
            
            logger.info(f"Loaded {len(self.operations)} operations from disk")
        except Exception as e:
            logger.error(f"Error loading operations: {e}")
            
    def add_operation(
        self,
        operation_type: Union[str, OperationType],
        backend: Union[str, BackendType],
        parameters: Optional[Dict[str, Any]] = None,
        operation_id: Optional[str] = None,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a new operation to the WAL.
        
        Args:
            operation_type: Type of operation to perform
            backend: Backend to perform the operation against
            parameters: Operation-specific parameters
            operation_id: Optional operation ID (generated if not provided)
            priority: Operation priority (higher values = higher priority)
            metadata: Optional metadata for the operation
            
        Returns:
            Dictionary with operation details, including operation_id and success status
        """
        # Convert enum values to strings if necessary
        if hasattr(operation_type, 'value'):
            operation_type = operation_type.value
            
        if hasattr(backend, 'value'):
            backend = backend.value
            
        # Generate operation ID if not provided
        if operation_id is None:
            operation_id = str(uuid.uuid4())
            
        # Create operation record
        operation = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "backend": backend,
            "parameters": parameters or {},
            "status": OperationStatus.PENDING.value,
            "created_time": time.time(),
            "updated_time": time.time(),
            "priority": priority,
            "metadata": metadata or {},
            "retries": 0,
            "logs": []
        }
        
        try:
            # Acquire lock to update operations
            with self._lock:
                # Add to in-memory operations
                self.operations[operation_id] = operation
                
                # Persist operation to disk
                self._persist_operation(operation)
                
            # Log operation creation
            self._add_operation_log(
                operation_id=operation_id,
                log_type="create",
                message=f"Created {operation_type} operation for {backend} backend"
            )
            
            logger.info(f"Added operation {operation_id} ({operation_type}) for {backend} backend")
            
            return {
                "success": True,
                "operation_id": operation_id,
                "operation": operation
            }
            
        except Exception as e:
            logger.error(f"Error adding operation: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
    def _persist_operation(self, operation: Dict[str, Any]) -> bool:
        """
        Persist an operation to disk.
        
        Args:
            operation: Operation dictionary to persist
            
        Returns:
            True if successful, False otherwise
        """
        operation_id = operation["operation_id"]
        try:
            # First write to a temporary file, then rename for atomicity
            temp_path = os.path.join(self.temp_dir, f"{operation_id}.json.tmp")
            final_path = os.path.join(self.operations_dir, f"{operation_id}.json")
            
            with open(temp_path, 'w') as f:
                json.dump(operation, f, indent=2)
                
            # On Windows, we need to remove the target file first
            if os.name == 'nt' and os.path.exists(final_path):
                os.remove(final_path)
                
            # Rename for atomicity
            shutil.move(temp_path, final_path)
            return True
            
        except Exception as e:
            logger.error(f"Error persisting operation {operation_id}: {e}")
            return False
            
    def update_operation_status(
        self,
        operation_id: str,
        new_status: Union[str, OperationStatus],
        updates: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update the status of an operation.
        
        Args:
            operation_id: ID of the operation to update
            new_status: New status for the operation
            updates: Optional additional updates to the operation
            
        Returns:
            Dictionary with update results
        """
        # Convert enum to string if necessary
        if hasattr(new_status, 'value'):
            new_status = new_status.value
            
        try:
            # Acquire lock to update operations
            with self._lock:
                # Check if operation exists
                if operation_id not in self.operations:
                    logger.warning(f"Attempted to update non-existent operation {operation_id}")
                    return {
                        "success": False,
                        "error": f"Operation {operation_id} not found",
                        "error_type": "OperationNotFound"
                    }
                    
                # Get operation
                operation = self.operations[operation_id]
                
                # Update status
                old_status = operation["status"]
                operation["status"] = new_status
                operation["updated_time"] = time.time()
                
                # Apply additional updates
                if updates:
                    for key, value in updates.items():
                        if key not in ["operation_id", "created_time"]:
                            operation[key] = value
                            
                # Persist updated operation
                self._persist_operation(operation)
                
            # Log status change
            self._add_operation_log(
                operation_id=operation_id,
                log_type="status_change",
                message=f"Status changed from {old_status} to {new_status}",
                details=updates
            )
            
            logger.info(f"Updated operation {operation_id} status to {new_status}")
            
            return {
                "success": True,
                "operation_id": operation_id,
                "old_status": old_status,
                "new_status": new_status
            }
            
        except Exception as e:
            logger.error(f"Error updating operation {operation_id} status: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
    def get_operation(self, operation_id: str) -> Dict[str, Any]:
        """
        Get an operation by ID.
        
        Args:
            operation_id: ID of the operation to get
            
        Returns:
            Dictionary with operation details
        """
        try:
            with self._lock:
                if operation_id not in self.operations:
                    return {
                        "success": False,
                        "error": f"Operation {operation_id} not found",
                        "error_type": "OperationNotFound"
                    }
                    
                return {
                    "success": True,
                    "operation": self.operations[operation_id]
                }
                
        except Exception as e:
            logger.error(f"Error getting operation {operation_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
    def get_operations(
        self,
        status: Optional[Union[str, OperationStatus]] = None,
        operation_type: Optional[Union[str, OperationType]] = None,
        backend: Optional[Union[str, BackendType]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        sort_by: str = "created_time",
        sort_desc: bool = True
    ) -> Dict[str, Any]:
        """
        Get operations matching the specified criteria.
        
        Args:
            status: Optional status filter
            operation_type: Optional operation type filter
            backend: Optional backend filter
            limit: Maximum number of operations to return
            offset: Offset for pagination
            sort_by: Field to sort by
            sort_desc: Whether to sort in descending order
            
        Returns:
            Dictionary with matching operations
        """
        try:
            # Convert enum values to strings if necessary
            if hasattr(status, 'value'):
                status = status.value
                
            if hasattr(operation_type, 'value'):
                operation_type = operation_type.value
                
            if hasattr(backend, 'value'):
                backend = backend.value
                
            filtered_operations = []
            
            with self._lock:
                # Apply filters
                for op_id, operation in self.operations.items():
                    # Skip if status doesn't match
                    if status and operation["status"] != status:
                        continue
                        
                    # Skip if operation_type doesn't match
                    if operation_type and operation["operation_type"] != operation_type:
                        continue
                        
                    # Skip if backend doesn't match
                    if backend and operation["backend"] != backend:
                        continue
                        
                    # Include this operation
                    filtered_operations.append(operation)
                    
                # Sort operations
                filtered_operations.sort(
                    key=lambda op: op.get(sort_by, 0),
                    reverse=sort_desc
                )
                
                # Apply pagination
                paginated_operations = filtered_operations[offset:]
                if limit is not None:
                    paginated_operations = paginated_operations[:limit]
                    
                return {
                    "success": True,
                    "operations": paginated_operations,
                    "total": len(filtered_operations),
                    "returned": len(paginated_operations)
                }
                
        except Exception as e:
            logger.error(f"Error getting operations: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
    def _add_operation_log(
        self,
        operation_id: str,
        log_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a log entry for an operation.
        
        Args:
            operation_id: ID of the operation
            log_type: Type of log entry (e.g., create, status_change, error)
            message: Log message
            details: Optional additional details
            
        Returns:
            True if successful, False otherwise
        """
        try:
            log_entry = {
                "timestamp": time.time(),
                "log_type": log_type,
                "message": message,
                "details": details or {}
            }
            
            # Append to in-memory logs
            with self._lock:
                if operation_id in self.operations:
                    self.operations[operation_id]["logs"].append(log_entry)
                    
                    # Persist the updated operation
                    self._persist_operation(self.operations[operation_id])
                    
            # Also write to the operation log file
            log_path = os.path.join(self.logs_dir, f"{operation_id}.log")
            
            with open(log_path, 'a') as f:
                log_str = f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(log_entry['timestamp']))}] "
                log_str += f"[{log_type}] {message}"
                
                if details:
                    log_str += f": {json.dumps(details)}"
                    
                f.write(log_str + "\n")
                
            return True
            
        except Exception as e:
            logger.error(f"Error adding log for operation {operation_id}: {str(e)}")
            return False
            
    def register_operation_handler(
        self,
        operation_type: Union[str, OperationType],
        handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> bool:
        """
        Register a handler function for an operation type.
        
        Args:
            operation_type: Type of operation
            handler: Handler function
            
        Returns:
            True if successful, False otherwise
        """
        # Convert enum to string if necessary
        if hasattr(operation_type, 'value'):
            operation_type = operation_type.value
            
        try:
            with self._lock:
                self.operation_handlers[operation_type] = handler
                
            logger.info(f"Registered handler for operation type: {operation_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering handler for {operation_type}: {str(e)}")
            return False
            
    def execute_operation(self, operation_id: str) -> Dict[str, Any]:
        """
        Execute a specific operation.
        
        Args:
            operation_id: ID of the operation to execute
            
        Returns:
            Dictionary with execution results
        """
        try:
            # Get operation
            operation_result = self.get_operation(operation_id)
            if not operation_result["success"]:
                return operation_result
                
            operation = operation_result["operation"]
            operation_type = operation["operation_type"]
            
            # Check if there's a registered handler
            if operation_type not in self.operation_handlers:
                logger.error(f"No handler registered for operation type: {operation_type}")
                self.update_operation_status(
                    operation_id=operation_id,
                    new_status=OperationStatus.FAILED,
                    updates={
                        "error": f"No handler registered for operation type: {operation_type}",
                        "error_type": "HandlerNotFound"
                    }
                )
                return {
                    "success": False,
                    "error": f"No handler registered for operation type: {operation_type}",
                    "error_type": "HandlerNotFound"
                }
                
            # Update status to processing
            self.update_operation_status(
                operation_id=operation_id,
                new_status=OperationStatus.PROCESSING
            )
            
            # Execute the handler
            handler = self.operation_handlers[operation_type]
            start_time = time.time()
            
            try:
                result = handler(operation)
                duration = time.time() - start_time
                
                # Update status based on result
                if result.get("success", False):
                    self.update_operation_status(
                        operation_id=operation_id,
                        new_status=OperationStatus.COMPLETED,
                        updates={
                            "result": result,
                            "execution_time": duration
                        }
                    )
                else:
                    self.update_operation_status(
                        operation_id=operation_id,
                        new_status=OperationStatus.FAILED,
                        updates={
                            "error": result.get("error", "Unknown error"),
                            "error_type": result.get("error_type", "UnknownError"),
                            "execution_time": duration
                        }
                    )
                    
                # Include execution time in the result
                result["execution_time"] = duration
                return result
                
            except Exception as e:
                # Update status to failed
                duration = time.time() - start_time
                self.update_operation_status(
                    operation_id=operation_id,
                    new_status=OperationStatus.FAILED,
                    updates={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "execution_time": duration
                    }
                )
                
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "execution_time": duration
                }
                
        except Exception as e:
            logger.error(f"Error executing operation {operation_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
    def process_pending_operations(
        self,
        max_operations: Optional[int] = None,
        types: Optional[List[Union[str, OperationType]]] = None,
        backends: Optional[List[Union[str, BackendType]]] = None
    ) -> Dict[str, Any]:
        """
        Process pending operations.
        
        Args:
            max_operations: Maximum number of operations to process
            types: Optional list of operation types to process
            backends: Optional list of backends to process
            
        Returns:
            Dictionary with processing results
        """
        # Convert enum values to strings if necessary
        if types:
            types = [t.value if hasattr(t, 'value') else t for t in types]
            
        if backends:
            backends = [b.value if hasattr(b, 'value') else b for b in backends]
            
        try:
            # Get pending operations
            pending_result = self.get_operations(
                status=OperationStatus.PENDING,
                sort_by="priority",
                sort_desc=True
            )
            
            if not pending_result["success"]:
                return pending_result
                
            pending_operations = pending_result["operations"]
            
            # Filter by types and backends if specified
            if types:
                pending_operations = [
                    op for op in pending_operations
                    if op["operation_type"] in types
                ]
                
            if backends:
                pending_operations = [
                    op for op in pending_operations
                    if op["backend"] in backends
                ]
                
            # Limit number of operations if specified
            if max_operations is not None:
                pending_operations = pending_operations[:max_operations]
                
            # Process operations
            results = {
                "success": True,
                "processed": 0,
                "completed": 0,
                "failed": 0,
                "operation_results": {}
            }
            
            for operation in pending_operations:
                operation_id = operation["operation_id"]
                
                # Execute the operation
                operation_result = self.execute_operation(operation_id)
                
                # Track results
                results["processed"] += 1
                results["operation_results"][operation_id] = operation_result
                
                if operation_result.get("success", False):
                    results["completed"] += 1
                else:
                    results["failed"] += 1
                    
            return results
            
        except Exception as e:
            logger.error(f"Error processing pending operations: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
    def delete_operation(self, operation_id: str) -> Dict[str, Any]:
        """
        Delete an operation.
        
        Args:
            operation_id: ID of the operation to delete
            
        Returns:
            Dictionary with deletion results
        """
        try:
            with self._lock:
                # Check if operation exists
                if operation_id not in self.operations:
                    return {
                        "success": False,
                        "error": f"Operation {operation_id} not found",
                        "error_type": "OperationNotFound"
                    }
                    
                # Remove from in-memory operations
                operation = self.operations.pop(operation_id)
                
                # Remove from disk
                operation_path = os.path.join(self.operations_dir, f"{operation_id}.json")
                if os.path.exists(operation_path):
                    os.remove(operation_path)
                    
                # Remove logs
                log_path = os.path.join(self.logs_dir, f"{operation_id}.log")
                if os.path.exists(log_path):
                    os.remove(log_path)
                    
                logger.info(f"Deleted operation {operation_id}")
                
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "operation_type": operation["operation_type"]
                }
                
        except Exception as e:
            logger.error(f"Error deleting operation {operation_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
    def recover_stalled_operations(self) -> Dict[str, Any]:
        """
        Recover operations that have been in processing state for too long.
        
        Returns:
            Dictionary with recovery results
        """
        try:
            current_time = time.time()
            stalled_operations = []
            
            with self._lock:
                for operation_id, operation in self.operations.items():
                    # Check if operation is in processing state
                    if operation["status"] == OperationStatus.PROCESSING:
                        # Check if it's been processing for too long
                        updated_time = operation.get("updated_time", operation["created_time"])
                        if current_time - updated_time > self.operation_timeout:
                            stalled_operations.append(operation_id)
                            
            # Retry or fail stalled operations
            results = {
                "success": True,
                "recovered": 0,
                "failed": 0,
                "operation_results": {}
            }
            
            for operation_id in stalled_operations:
                # Get operation
                operation = self.operations[operation_id]
                retries = operation.get("retries", 0)
                
                if retries < self.max_retries:
                    # Update to pending for retry
                    update_result = self.update_operation_status(
                        operation_id=operation_id,
                        new_status=OperationStatus.PENDING,
                        updates={
                            "retries": retries + 1,
                            "retry_time": current_time
                        }
                    )
                    
                    logger.info(f"Recovering stalled operation {operation_id} for retry ({retries + 1}/{self.max_retries})")
                    results["recovered"] += 1
                else:
                    # Mark as failed - exceeded max retries
                    update_result = self.update_operation_status(
                        operation_id=operation_id,
                        new_status=OperationStatus.FAILED,
                        updates={
                            "error": "Operation timed out and exceeded maximum retries",
                            "error_type": "MaxRetriesExceeded"
                        }
                    )
                    
                    logger.warning(f"Marking operation {operation_id} as failed after {retries} retries")
                    results["failed"] += 1
                    
                results["operation_results"][operation_id] = update_result
                
            return results
            
        except Exception as e:
            logger.error(f"Error recovering stalled operations: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
    def clear_completed_operations(
        self,
        older_than: Optional[float] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Clear completed operations.
        
        Args:
            older_than: Clear operations completed earlier than this timestamp
            limit: Maximum number of operations to clear
            
        Returns:
            Dictionary with clearing results
        """
        try:
            completed_operations = []
            
            with self._lock:
                # Find completed operations
                for operation_id, operation in self.operations.items():
                    if operation["status"] == OperationStatus.COMPLETED:
                        # Check age if specified
                        if older_than is not None:
                            updated_time = operation.get("updated_time", operation["created_time"])
                            if updated_time >= older_than:
                                continue
                                
                        completed_operations.append(operation_id)
                
                # Apply limit if specified
                if limit is not None:
                    completed_operations = completed_operations[:limit]
                    
                # Delete operations
                deleted_count = 0
                for operation_id in completed_operations:
                    # Remove from in-memory operations
                    self.operations.pop(operation_id)
                    
                    # Remove from disk
                    operation_path = os.path.join(self.operations_dir, f"{operation_id}.json")
                    if os.path.exists(operation_path):
                        os.remove(operation_path)
                        
                    # Remove logs
                    log_path = os.path.join(self.logs_dir, f"{operation_id}.log")
                    if os.path.exists(log_path):
                        os.remove(log_path)
                        
                    deleted_count += 1
                    
                logger.info(f"Cleared {deleted_count} completed operations")
                
                return {
                    "success": True,
                    "cleared": deleted_count,
                    "remaining": len(self.operations)
                }
                
        except Exception as e:
            logger.error(f"Error clearing completed operations: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
    def close(self):
        """Clean up resources."""
        logger.info("WAL closed")
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the WAL.
        
        Returns:
            Dictionary with WAL statistics
        """
        try:
            stats = {
                "total_operations": 0,
                "by_status": {},
                "by_type": {},
                "by_backend": {}
            }
            
            with self._lock:
                # Count operations
                stats["total_operations"] = len(self.operations)
                
                # Group by status
                for operation in self.operations.values():
                    status = operation["status"]
                    if status not in stats["by_status"]:
                        stats["by_status"][status] = 0
                    stats["by_status"][status] += 1
                    
                    # Group by type
                    op_type = operation["operation_type"]
                    if op_type not in stats["by_type"]:
                        stats["by_type"][op_type] = 0
                    stats["by_type"][op_type] += 1
                    
                    # Group by backend
                    backend = operation["backend"]
                    if backend not in stats["by_backend"]:
                        stats["by_backend"][backend] = 0
                    stats["by_backend"][backend] += 1
                    
                return {
                    "success": True,
                    "statistics": stats
                }
                
        except Exception as e:
            logger.error(f"Error getting WAL statistics: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }


    def process_operation(self, operation_id: str) -> Dict[str, Any]:
        """
        Process a specific operation (alias for execute_operation).
        This method is provided for compatibility with tests and external integrations.
        
        Args:
            operation_id: ID of the operation to process
            
        Returns:
            Dictionary with processing results
        """
        return self.execute_operation(operation_id)


# Export key classes and enums
__all__ = [
    'WAL',
    'OperationType',
    'OperationStatus',
    'BackendType'
]