"""
Filesystem Journal for IPFS Kit.

This module implements a filesystem journal to ensure data consistency and
recovery for the virtual filesystem in case of unexpected shutdowns or power outages.
It works alongside the Write-Ahead Log (WAL) but focuses specifically on the
filesystem metadata and structure.

Key features:
1. Transaction-based journaling of filesystem operations
2. Atomic operation support through write-ahead journaling
3. Automatic recovery on startup
4. Periodic checkpointing
5. Multi-tier storage integration
6. Integration with ipfs_datasets_py for distributed dataset operations
"""

import os
import sys
import json
import time
import uuid
import logging
import threading
import tempfile
import shutil
import hashlib
from collections import deque
from typing import Dict, List, Any, Optional, Tuple, Union, Set
from enum import Enum
import atexit

# Try to import ipfs_datasets integration
try:
    from .ipfs_datasets_integration import get_ipfs_datasets_manager, IPFS_DATASETS_AVAILABLE
except ImportError:
    IPFS_DATASETS_AVAILABLE = False
    def get_ipfs_datasets_manager(*args, **kwargs):
        return None

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from pyarrow import compute as pc
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

class JournalOperationType(str, Enum):
    """Types of filesystem operations tracked in the journal."""
    CREATE = "create"          # Create a file or directory
    DELETE = "delete"          # Delete a file or directory
    RENAME = "rename"          # Rename a file or directory
    WRITE = "write"            # Write to a file
    TRUNCATE = "truncate"      # Truncate a file
    METADATA = "metadata"      # Update metadata
    CHECKPOINT = "checkpoint"  # Completed transaction checkpoint
    MOUNT = "mount"            # Mount a new CID
    UNMOUNT = "unmount"        # Unmount a CID
    DATASET = "dataset"        # Dataset operation (store, version, etc.)


class JournalEntryStatus(str, Enum):
    """Status values for journal entries."""
    PENDING = "pending"        # Operation has been recorded but not completed
    COMPLETED = "completed"    # Operation has been completed successfully
    FAILED = "failed"          # Operation has failed
    ROLLED_BACK = "rolled_back"  # Operation has been rolled back


class FilesystemJournal:
    """
    Transaction-based filesystem journal for the IPFS virtual filesystem.
    
    This class maintains a journal of filesystem operations to ensure data consistency
    and recovery in case of unexpected shutdowns or power outages. It works alongside
    the Write-Ahead Log (WAL) but focuses specifically on the filesystem metadata.
    """
    
    def __init__(
        self,
        base_path: str = "~/.ipfs_kit/journal",
        sync_interval: int = 5,
        checkpoint_interval: int = 60,
        max_journal_size: int = 1000,
        auto_recovery: bool = True,
        wal = None,  # Optional WAL integration
        enable_ipfs_datasets: bool = False,  # Enable ipfs_datasets_py integration
        ipfs_client = None  # Optional IPFS client for ipfs_datasets
    ):
        """
        Initialize the filesystem journal.
        
        Args:
            base_path: Base directory for journal storage
            sync_interval: Interval in seconds for syncing journal to disk
            checkpoint_interval: Interval in seconds for creating checkpoints
            max_journal_size: Maximum number of entries in the journal before forcing a checkpoint
            auto_recovery: Whether to automatically run recovery on startup
            wal: Optional WAL instance for integration
            enable_ipfs_datasets: Enable ipfs_datasets_py integration for distributed operations
            ipfs_client: Optional IPFS client instance for dataset operations
        """
        self.base_path = os.path.expanduser(base_path)
        self.journal_dir = os.path.join(self.base_path, "journals")
        self.checkpoint_dir = os.path.join(self.base_path, "checkpoints")
        self.temp_dir = os.path.join(self.base_path, "temp")
        
        self.sync_interval = sync_interval
        self.checkpoint_interval = checkpoint_interval
        self.max_journal_size = max_journal_size
        self.auto_recovery = auto_recovery
        self.wal = wal
        
        # Initialize ipfs_datasets integration if requested and available
        self.enable_ipfs_datasets = enable_ipfs_datasets and IPFS_DATASETS_AVAILABLE
        self.ipfs_datasets_manager = None
        if self.enable_ipfs_datasets:
            try:
                self.ipfs_datasets_manager = get_ipfs_datasets_manager(
                    ipfs_client=ipfs_client,
                    enable=True
                )
                if self.ipfs_datasets_manager and self.ipfs_datasets_manager.is_available():
                    logger.info("ipfs_datasets_py integration enabled for filesystem journal")
                else:
                    logger.info("ipfs_datasets_py not available, using local-only operations")
                    self.enable_ipfs_datasets = False
            except Exception as e:
                logger.warning(f"Failed to initialize ipfs_datasets integration: {e}")
                self.enable_ipfs_datasets = False
        
        # Journal state
        self.current_journal_id = None
        self.current_journal_path = None
        self.journal_entries = []
        self.in_transaction = False
        self.transaction_entries = []
        self.last_sync_time = 0
        self.last_checkpoint_time = 0
        self.entry_count = 0
        
        # Thread safety
        self._lock = threading.RLock()
        self._sync_thread = None
        self._stop_sync = threading.Event()
        
        # Filesystem state
        self.fs_state = {}  # Path -> metadata
        
        # Create directories
        self._ensure_directories()
        
        # Initialize journal
        self._init_journal()
        
        # Start background threads
        self._start_sync_thread()
        
        # Run recovery if needed
        if self.auto_recovery:
            self.recover()
        
        # Register shutdown handler
        atexit.register(self.close)
        
        logger.info(f"Filesystem journal initialized at {self.base_path}")
    
    def _ensure_directories(self):
        """Create the required directories if they don't exist."""
        os.makedirs(self.journal_dir, exist_ok=True)
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def _init_journal(self):
        """Initialize the journal by loading the latest checkpoint and journal."""
        with self._lock:
            # Find the latest checkpoint
            checkpoint_files = [f for f in os.listdir(self.checkpoint_dir) 
                               if f.startswith("checkpoint_") and f.endswith(".json")]
            
            if checkpoint_files:
                # Sort by timestamp (newest first)
                checkpoint_files.sort(reverse=True)
                latest_checkpoint = checkpoint_files[0]
                
                # Load the checkpoint
                checkpoint_path = os.path.join(self.checkpoint_dir, latest_checkpoint)
                try:
                    with open(checkpoint_path, 'r') as f:
                        checkpoint_data = json.load(f)
                        
                    # Load filesystem state from checkpoint
                    self.fs_state = checkpoint_data.get("fs_state", {})
                    self.last_checkpoint_time = checkpoint_data.get("timestamp", time.time())
                    
                    logger.info(f"Loaded checkpoint from {checkpoint_path}")
                except Exception as e:
                    logger.error(f"Error loading checkpoint {checkpoint_path}: {e}")
                    # Start with empty state if checkpoint is corrupted
                    self.fs_state = {}
                    self.last_checkpoint_time = time.time()
            else:
                # No checkpoint found, start with empty state
                self.fs_state = {}
                self.last_checkpoint_time = time.time()
            
            # Create a new journal
            self._create_new_journal()
    
    def _create_new_journal(self):
        """Create a new journal file."""
        timestamp = int(time.time())
        self.current_journal_id = f"journal_{timestamp}_{uuid.uuid4().hex[:8]}"
        self.current_journal_path = os.path.join(self.journal_dir, f"{self.current_journal_id}.json")
        self.journal_entries = []
        self.entry_count = 0
        
        # Write empty journal to disk
        self._write_journal()
        
        if not getattr(self, "_stop_sync", threading.Event()).is_set():
            logger.info(f"Created new journal at {self.current_journal_path}")
    
    def _write_journal(self):
        """Write the current journal entries to disk."""
        # Create a temporary file first
        temp_path = os.path.join(self.temp_dir, f"{self.current_journal_id}.json.tmp")
        try:
            # Directories may have been removed (e.g. temp test dirs cleaned up)
            # before this journal flush runs during teardown/atexit.
            self._ensure_directories()

            with open(temp_path, 'w') as f:
                json.dump(self.journal_entries, f, indent=2)
            
            # Move to final location (atomic operation)
            shutil.move(temp_path, self.current_journal_path)
            
            self.last_sync_time = time.time()
            return True
        except Exception as e:
            logger.error(f"Error writing journal: {e}")
            return False
    
    def _start_sync_thread(self):
        """Start the background sync thread."""
        if self._sync_thread is not None and self._sync_thread.is_alive():
            return
            
        self._stop_sync.clear()
        self._sync_thread = threading.Thread(
            target=self._sync_loop,
            name="Journal-Sync-Thread",
            daemon=True
        )
        self._sync_thread.start()
        logger.info("Journal sync thread started")
    
    def _sync_loop(self):
        """Main sync loop for background thread."""
        while not self._stop_sync.is_set():
            try:
                # Check if it's time to sync
                current_time = time.time()
                
                with self._lock:
                    # Sync journal if needed
                    if current_time - self.last_sync_time >= self.sync_interval:
                        self._write_journal()
                    
                    # Create checkpoint if needed
                    if (current_time - self.last_checkpoint_time >= self.checkpoint_interval or
                        self.entry_count >= self.max_journal_size):
                        self.create_checkpoint()
            except Exception as e:
                logger.error(f"Error in journal sync loop: {e}")
            
            # Wait for next sync check
            self._stop_sync.wait(1.0)  # Check more frequently than sync_interval
    
    def add_journal_entry(
        self,
        operation_type: Union[str, JournalOperationType],
        path: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: Union[str, JournalEntryStatus] = JournalEntryStatus.PENDING
    ) -> Dict[str, Any]:
        """
        Add an entry to the journal.
        
        Args:
            operation_type: Type of operation
            path: Filesystem path for the operation
            data: Operation-specific data
            metadata: Optional metadata
            status: Initial status for the entry
            
        Returns:
            Journal entry dictionary with entry_id
        """
        # Convert enum to string if necessary
        if hasattr(operation_type, 'value'):
            operation_type = operation_type.value
            
        if hasattr(status, 'value'):
            status = status.value
        
        # Create entry
        entry_id = str(uuid.uuid4())
        entry = {
            "entry_id": entry_id,
            "timestamp": time.time(),
            "operation_type": operation_type,
            "path": path,
            "data": data or {},
            "metadata": metadata or {},
            "status": status,
            "transaction_id": None  # Will be set if in a transaction
        }
        
        # Add to journal or transaction
        with self._lock:
            if self.in_transaction:
                # Add to transaction buffer
                self.transaction_entries.append(entry)
            else:
                # Add directly to journal
                self.journal_entries.append(entry)
                self.entry_count += 1
                
                # Write journal if this is a critical operation
                if operation_type in [JournalOperationType.CREATE.value, 
                                     JournalOperationType.DELETE.value, 
                                     JournalOperationType.RENAME.value]:
                    self._write_journal()
        
        return entry

    def record_operation(
        self,
        operation_type: Union[str, JournalOperationType],
        path: str,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Compatibility wrapper to record an operation and return entry ID."""
        entry = self.add_journal_entry(
            operation_type=operation_type,
            path=path,
            data=details or {},
            metadata=metadata
        )
        return entry.get("entry_id")

    def mark_completed(self, entry_id: str) -> bool:
        """Mark a journal entry as completed."""
        return self.update_entry_status(entry_id, JournalEntryStatus.COMPLETED)

    def mark_failed(self, entry_id: str, reason: Optional[str] = None) -> bool:
        """Mark a journal entry as failed."""
        result = {"reason": reason} if reason else None
        return self.update_entry_status(entry_id, JournalEntryStatus.FAILED, result=result)

    def mark_entry_completed(self, entry_id: str) -> bool:
        """Alias for mark_completed used by MCP tools."""
        return self.mark_completed(entry_id)

    def mark_entry_failed(self, entry_id: str, reason: Optional[str] = None) -> bool:
        """Alias for mark_failed used by MCP tools."""
        return self.mark_failed(entry_id, reason=reason)

    def get_pending_operations(self) -> List[Dict[str, Any]]:
        """Compatibility wrapper for pending entries."""
        return self.get_pending_journal_entries()

    def get_entries(
        self,
        status: Optional[str] = None,
        operation_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get journal entries with optional filtering."""
        entries = list(self.journal_entries)
        if status:
            entries = [e for e in entries if e.get("status") == status]
        if operation_type:
            entries = [e for e in entries if e.get("operation_type") == operation_type]
        if limit:
            entries = entries[:limit]
        return entries
    
    def update_entry_status(
        self,
        entry_id: str,
        status: Union[str, JournalEntryStatus],
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update the status of a journal entry.
        
        Args:
            entry_id: ID of the entry to update
            status: New status
            result: Optional operation result
            
        Returns:
            True if successful, False otherwise
        """
        # Convert enum to string if necessary
        if hasattr(status, 'value'):
            status = status.value
            
        with self._lock:
            # First check transaction entries if in a transaction
            if self.in_transaction:
                for entry in self.transaction_entries:
                    if entry["entry_id"] == entry_id:
                        entry["status"] = status
                        if result:
                            entry["result"] = result
                        return True
            
            # Then check journal entries
            for entry in self.journal_entries:
                if entry["entry_id"] == entry_id:
                    entry["status"] = status
                    if result:
                        entry["result"] = result
                    
                    # Write journal if updating a critical operation
                    if entry["operation_type"] in [JournalOperationType.CREATE.value, 
                                                 JournalOperationType.DELETE.value, 
                                                 JournalOperationType.RENAME.value]:
                        self._write_journal()
                    
                    return True
        
        # Entry not found
        return False
    
    def begin_transaction(self) -> str:
        """
        Begin a new transaction.
        
        Returns:
            Transaction ID
        """
        with self._lock:
            if self.in_transaction:
                raise RuntimeError("Transaction already in progress")
                
            self.in_transaction = True
            self.transaction_entries = []
            transaction_id = str(uuid.uuid4())
            
            # Add a special entry to mark the start of the transaction
            self.add_journal_entry(
                operation_type=JournalOperationType.CHECKPOINT,
                path="transaction_begin",
                data={"transaction_id": transaction_id},
                status=JournalEntryStatus.COMPLETED
            )
            
            return transaction_id
    
    def commit_transaction(self) -> bool:
        """
        Commit the current transaction.
        
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if not self.in_transaction:
                return False
                
            # Set transaction ID on all entries
            transaction_id = self.transaction_entries[0]["transaction_id"] if self.transaction_entries else str(uuid.uuid4())
            for entry in self.transaction_entries:
                entry["transaction_id"] = transaction_id
            
            # Add all transaction entries to the journal
            self.journal_entries.extend(self.transaction_entries)
            self.entry_count += len(self.transaction_entries)
            
            # Add a special entry to mark the end of the transaction
            self.add_journal_entry(
                operation_type=JournalOperationType.CHECKPOINT,
                path="transaction_commit",
                data={"transaction_id": transaction_id},
                status=JournalEntryStatus.COMPLETED
            )
            
            # Reset transaction state
            self.in_transaction = False
            self.transaction_entries = []
            
            # Write journal to disk
            return self._write_journal()
    
    def rollback_transaction(self) -> bool:
        """
        Rollback the current transaction.
        
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if not self.in_transaction:
                return False
                
            # Get transaction ID if available
            transaction_id = self.transaction_entries[0]["transaction_id"] if self.transaction_entries else str(uuid.uuid4())
            
            # Add a special entry to mark the rollback
            self.add_journal_entry(
                operation_type=JournalOperationType.CHECKPOINT,
                path="transaction_rollback",
                data={"transaction_id": transaction_id},
                status=JournalEntryStatus.COMPLETED
            )
            
            # Clear transaction entries
            self.in_transaction = False
            self.transaction_entries = []
            
            return True
    
    def create_checkpoint(self, description: Optional[str] = None) -> Union[str, bool]:
        """
        Create a checkpoint of the current filesystem state.
        
        A checkpoint represents a clean, consistent state of the filesystem.
        After creating a checkpoint, the journal can be cleared.
        
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            # Can't create checkpoint during transaction
            if self.in_transaction:
                logger.warning("Cannot create checkpoint during transaction")
                return False
            
            try:
                # Create checkpoint data
                checkpoint_data = {
                    "timestamp": time.time(),
                    "fs_state": self.fs_state.copy(),
                    "checksum": self._calculate_state_checksum(),
                    "description": description
                }
                
                # Create checkpoint ID
                checkpoint_id = f"checkpoint_{int(checkpoint_data['timestamp'])}_{uuid.uuid4().hex[:8]}"
                checkpoint_path = os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")
                
                # Write to temporary file first
                temp_path = os.path.join(self.temp_dir, f"{checkpoint_id}.json.tmp")
                with open(temp_path, 'w') as f:
                    json.dump(checkpoint_data, f, indent=2)
                
                # Move to final location (atomic operation)
                shutil.move(temp_path, checkpoint_path)
                
                # Update checkpoint time
                self.last_checkpoint_time = checkpoint_data["timestamp"]
                
                # Add checkpoint entry to journal
                self.add_journal_entry(
                    operation_type=JournalOperationType.CHECKPOINT,
                    path="checkpoint",
                    data={"checkpoint_id": checkpoint_id, "description": description},
                    status=JournalEntryStatus.COMPLETED
                )
                
                # Create new journal
                self._create_new_journal()
                
                # Clean up old checkpoints and journals
                self._cleanup_old_files()
                
                if not getattr(self, "_stop_sync", threading.Event()).is_set():
                    logger.info(f"Created checkpoint {checkpoint_id}")
                return checkpoint_id
                
            except Exception as e:
                logger.error(f"Error creating checkpoint: {e}")
                return False

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List available checkpoints."""
        checkpoints = []
        try:
            for filename in sorted(os.listdir(self.checkpoint_dir)):
                if filename.startswith("checkpoint_") and filename.endswith(".json"):
                    checkpoint_id = filename.replace(".json", "")
                    checkpoints.append({
                        "checkpoint_id": checkpoint_id,
                        "path": os.path.join(self.checkpoint_dir, filename)
                    })
        except Exception:
            pass
        return checkpoints

    def get_status(self) -> Dict[str, Any]:
        """Return journal status summary."""
        entries = list(self.journal_entries)
        if not entries:
            try:
                journal_files = [f for f in os.listdir(self.journal_dir)
                                if f.startswith("journal_") and f.endswith(".json")]
                if journal_files:
                    journal_files.sort(reverse=True)
                    for filename in journal_files:
                        with open(os.path.join(self.journal_dir, filename), "r") as handle:
                            file_entries = json.load(handle)
                        if file_entries:
                            entries = file_entries
                            break
            except Exception:
                entries = []

        pending = len([e for e in entries if e.get("status") == JournalEntryStatus.PENDING.value])
        completed = len([e for e in entries if e.get("status") == JournalEntryStatus.COMPLETED.value])
        failed = len([e for e in entries if e.get("status") == JournalEntryStatus.FAILED.value])
        return {
            "total_entries": len(entries),
            "pending_entries": pending,
            "completed_entries": completed,
            "failed_entries": failed
        }

    def cleanup(self, keep_days: int = 30) -> Dict[str, Any]:
        """Cleanup old completed/failed entries."""
        cutoff = time.time() - (keep_days * 86400)
        before = len(self.journal_entries)
        self.journal_entries = [
            e for e in self.journal_entries
            if not (
                e.get("status") in {JournalEntryStatus.COMPLETED.value, JournalEntryStatus.FAILED.value}
                and e.get("timestamp", time.time()) < cutoff
            )
        ]
        removed = before - len(self.journal_entries)
        self.entry_count = len(self.journal_entries)
        self._write_journal()
        return {"removed": removed, "remaining": len(self.journal_entries)}
    
    def _cleanup_old_files(self):
        """Clean up old checkpoint and journal files."""
        try:
            # Keep last 5 checkpoints
            checkpoint_files = [f for f in os.listdir(self.checkpoint_dir) 
                               if f.startswith("checkpoint_") and f.endswith(".json")]
            
            if len(checkpoint_files) > 5:
                # Sort by timestamp (oldest first)
                checkpoint_files.sort()
                
                # Remove oldest files
                for file in checkpoint_files[:-5]:
                    os.remove(os.path.join(self.checkpoint_dir, file))
            
            # Keep journals from after the oldest checkpoint we're keeping
            journal_files = [f for f in os.listdir(self.journal_dir) 
                            if f.startswith("journal_") and f.endswith(".json")]
            
            if checkpoint_files and journal_files:
                # Get timestamp of oldest checkpoint we're keeping
                oldest_kept = checkpoint_files[-5] if len(checkpoint_files) > 5 else checkpoint_files[0]
                oldest_timestamp = int(oldest_kept.split("_")[1])
                
                # Remove journals older than oldest checkpoint
                for file in journal_files:
                    try:
                        journal_timestamp = int(file.split("_")[1])
                        if journal_timestamp < oldest_timestamp:
                            os.remove(os.path.join(self.journal_dir, file))
                    except (IndexError, ValueError):
                        # Skip files with invalid format
                        pass
            
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
    
    def recover(self) -> Dict[str, Any]:
        """
        Perform recovery from journal and checkpoints.
        
        Returns:
            Dictionary with recovery results
        """
        with self._lock:
            recovery_result = {
                "success": False,
                "checkpoints_loaded": 0,
                "journals_processed": 0,
                "entries_processed": 0,
                "entries_applied": 0,
                "errors": []
            }
            
            try:
                # Load the latest checkpoint
                checkpoint_files = [f for f in os.listdir(self.checkpoint_dir) 
                                   if f.startswith("checkpoint_") and f.endswith(".json")]
                
                if checkpoint_files:
                    # Sort by timestamp (newest first)
                    checkpoint_files.sort(reverse=True)
                    
                    # Try checkpoints in order until one works
                    for checkpoint_file in checkpoint_files:
                        checkpoint_path = os.path.join(self.checkpoint_dir, checkpoint_file)
                        try:
                            with open(checkpoint_path, 'r') as f:
                                checkpoint_data = json.load(f)
                            
                            # Verify checksum
                            stored_checksum = checkpoint_data.get("checksum")
                            if stored_checksum:
                                # Calculate checksum from state
                                fs_state = checkpoint_data.get("fs_state", {})
                                calculated_checksum = self._calculate_checksum(json.dumps(fs_state, sort_keys=True))
                                
                                if calculated_checksum != stored_checksum:
                                    recovery_result["errors"].append(
                                        f"Checksum mismatch for checkpoint {checkpoint_file}")
                                    continue
                            
                            # Load state from checkpoint
                            self.fs_state = checkpoint_data.get("fs_state", {})
                            self.last_checkpoint_time = checkpoint_data.get("timestamp", time.time())
                            
                            recovery_result["checkpoints_loaded"] += 1
                            logger.info(f"Recovered from checkpoint {checkpoint_path}")
                            
                            # Stop after loading one valid checkpoint
                            break
                            
                        except Exception as e:
                            recovery_result["errors"].append(
                                f"Error loading checkpoint {checkpoint_file}: {str(e)}")
                
                # Find journal files newer than the loaded checkpoint
                journal_files = [f for f in os.listdir(self.journal_dir) 
                                if f.startswith("journal_") and f.endswith(".json")]
                
                if journal_files and hasattr(self, 'last_checkpoint_time'):
                    # Filter and sort journals by timestamp (oldest first)
                    valid_journals = []
                    for file in journal_files:
                        try:
                            # Extract timestamp from filename
                            timestamp = int(file.split("_")[1])
                            if timestamp >= self.last_checkpoint_time:
                                valid_journals.append((timestamp, file))
                        except (IndexError, ValueError):
                            recovery_result["errors"].append(f"Invalid journal filename: {file}")
                    
                    # Sort by timestamp
                    valid_journals.sort()
                    
                    # Apply journals in order
                    for _, journal_file in valid_journals:
                        journal_path = os.path.join(self.journal_dir, journal_file)
                        
                        try:
                            with open(journal_path, 'r') as f:
                                journal_entries = json.load(f)
                            
                            # Apply completed entries in order
                            entries_processed = 0
                            entries_applied = 0
                            
                            for entry in journal_entries:
                                entries_processed += 1
                                
                                # Skip entries that aren't completed
                                if entry.get("status") != JournalEntryStatus.COMPLETED.value:
                                    continue
                                
                                # Apply the operation to fs_state
                                if self._apply_journal_entry(entry):
                                    entries_applied += 1
                            
                            recovery_result["journals_processed"] += 1
                            recovery_result["entries_processed"] += entries_processed
                            recovery_result["entries_applied"] += entries_applied
                            
                            logger.info(f"Processed journal {journal_path}: "
                                        f"{entries_applied}/{entries_processed} entries applied")
                                
                        except Exception as e:
                            recovery_result["errors"].append(
                                f"Error processing journal {journal_file}: {str(e)}")
                
                # Create a new journal
                self._create_new_journal()
                
                recovery_result["success"] = True
                
            except Exception as e:
                recovery_result["errors"].append(f"Recovery error: {str(e)}")
                logger.error(f"Error during recovery: {e}")
            
            return recovery_result
    
    def _apply_journal_entry(self, entry: Dict[str, Any]) -> bool:
        """
        Apply a journal entry to the filesystem state.
        
        Args:
            entry: Journal entry to apply
            
        Returns:
            True if successfully applied, False otherwise
        """
        operation_type = entry.get("operation_type")
        path = entry.get("path")
        data = entry.get("data", {})
        
        try:
            if operation_type == JournalOperationType.CREATE.value:
                # Create file or directory
                is_dir = data.get("is_directory", False)
                metadata = data.get("metadata", {})
                
                self.fs_state[path] = {
                    "type": "directory" if is_dir else "file",
                    "created_at": entry.get("timestamp", time.time()),
                    "modified_at": entry.get("timestamp", time.time()),
                    "metadata": metadata
                }
                
                if not is_dir:
                    # Add CID for file
                    self.fs_state[path]["cid"] = data.get("cid")
                    self.fs_state[path]["size"] = data.get("size", 0)
                
            elif operation_type == JournalOperationType.DELETE.value:
                # Delete file or directory
                if path in self.fs_state:
                    # Find all children to delete
                    to_delete = [p for p in self.fs_state if p == path or p.startswith(path + "/")]
                    
                    # Delete from state
                    for p in to_delete:
                        if p in self.fs_state:
                            del self.fs_state[p]
            
            elif operation_type == JournalOperationType.RENAME.value:
                # Rename file or directory
                old_path = path
                new_path = data.get("new_path")
                
                if old_path in self.fs_state:
                    # Handle renaming a directory with contents
                    if self.fs_state[old_path].get("type") == "directory":
                        # Find all paths starting with old_path
                        to_rename = [(p, p.replace(old_path, new_path, 1)) 
                                     for p in self.fs_state 
                                     if p == old_path or p.startswith(old_path + "/")]
                        
                        # Rename each path
                        for old, new in to_rename:
                            if old in self.fs_state:
                                self.fs_state[new] = self.fs_state[old].copy()
                                del self.fs_state[old]
                                
                                # Update modified time
                                self.fs_state[new]["modified_at"] = entry.get("timestamp", time.time())
                    else:
                        # Simple file rename
                        self.fs_state[new_path] = self.fs_state[old_path].copy()
                        del self.fs_state[old_path]
                        
                        # Update modified time
                        self.fs_state[new_path]["modified_at"] = entry.get("timestamp", time.time())
            
            elif operation_type == JournalOperationType.WRITE.value:
                # Write to file
                if path in self.fs_state and self.fs_state[path].get("type") == "file":
                    # Update CID and size
                    self.fs_state[path]["cid"] = data.get("cid")
                    self.fs_state[path]["size"] = data.get("size", 0)
                    self.fs_state[path]["modified_at"] = entry.get("timestamp", time.time())
            
            elif operation_type == JournalOperationType.TRUNCATE.value:
                # Truncate file
                if path in self.fs_state and self.fs_state[path].get("type") == "file":
                    # Update CID and size
                    self.fs_state[path]["cid"] = data.get("cid")
                    self.fs_state[path]["size"] = data.get("size", 0)
                    self.fs_state[path]["modified_at"] = entry.get("timestamp", time.time())
            
            elif operation_type == JournalOperationType.METADATA.value:
                # Update metadata
                if path in self.fs_state:
                    metadata_updates = data.get("metadata", {})
                    
                    # Update metadata
                    current_metadata = self.fs_state[path].get("metadata", {})
                    updated_metadata = {**current_metadata, **metadata_updates}
                    
                    self.fs_state[path]["metadata"] = updated_metadata
                    self.fs_state[path]["modified_at"] = entry.get("timestamp", time.time())
            
            elif operation_type == JournalOperationType.MOUNT.value:
                # Mount a CID at a path
                is_dir = data.get("is_directory", False)
                cid = data.get("cid")
                
                self.fs_state[path] = {
                    "type": "directory" if is_dir else "file",
                    "cid": cid,
                    "mounted": True,
                    "created_at": entry.get("timestamp", time.time()),
                    "modified_at": entry.get("timestamp", time.time()),
                    "metadata": data.get("metadata", {})
                }
                
                if not is_dir:
                    self.fs_state[path]["size"] = data.get("size", 0)
            
            elif operation_type == JournalOperationType.UNMOUNT.value:
                # Unmount a CID
                if path in self.fs_state:
                    # Just remove the mounted flag
                    if "mounted" in self.fs_state[path]:
                        del self.fs_state[path]["mounted"]
            
            elif operation_type == JournalOperationType.CHECKPOINT.value:
                # Checkpoint entries don't modify the filesystem state
                pass
            
            else:
                logger.warning(f"Unknown operation type: {operation_type}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying journal entry: {e}")
            return False
    
    def _calculate_state_checksum(self) -> str:
        """Calculate checksum of current filesystem state."""
        state_str = json.dumps(self.fs_state, sort_keys=True)
        return self._calculate_checksum(state_str)
    
    def _calculate_checksum(self, data: str) -> str:
        """Calculate SHA-256 checksum of string data."""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    def get_fs_state(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the current filesystem state.
        
        Returns:
            Dictionary with path -> metadata mapping
        """
        with self._lock:
            return self.fs_state.copy()
    
    def get_pending_journal_entries(self) -> List[Dict[str, Any]]:
        """
        Get pending journal entries.
        
        Returns:
            List of pending journal entries
        """
        with self._lock:
            return [entry for entry in self.journal_entries 
                   if entry.get("status") == JournalEntryStatus.PENDING.value]
    
    def close(self):
        """Close the journal and clean up resources."""
        try:
            # Stop sync thread
            if hasattr(self, '_stop_sync'):
                self._stop_sync.set()
                
            if hasattr(self, '_sync_thread') and self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=2.0)
            
            # Ensure journal is synced to disk
            with self._lock:
                if hasattr(self, 'journal_entries'):
                    self._write_journal()
            # Avoid logging during teardown/atexit; pytest's capture streams
            # can be closed, which causes noisy logging-internal tracebacks.
            
        except Exception as e:
            # Best-effort cleanup; avoid logging during teardown.
            _ = e
    
    def store_dataset(self, dataset_path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Store a dataset using ipfs_datasets_py integration with journal logging.
        
        This method provides distributed dataset storage with proper event logging
        and provenance tracking. Falls back to local operations if ipfs_datasets_py
        is not available.
        
        Args:
            dataset_path: Path to the dataset file or directory
            metadata: Optional metadata to attach (includes provenance info)
        
        Returns:
            Dictionary containing operation result, CID (if distributed), and event log entry
        """
        with self._lock:
            # Add journal entry for the dataset store operation
            entry = self.add_journal_entry(
                operation_type=JournalOperationType.DATASET,  # Using DATASET type for dataset operations
                path=dataset_path,
                data={
                    "operation": "dataset_store",
                    "metadata": metadata or {},
                    "timestamp": time.time()
                }
            )
            
            try:
                # Try to use ipfs_datasets if available
                if self.enable_ipfs_datasets and self.ipfs_datasets_manager:
                    result = self.ipfs_datasets_manager.store(dataset_path, metadata)
                    
                    # Update journal entry with result
                    entry["data"]["result"] = result
                    entry["data"]["distributed"] = result.get("distributed", False)
                    if "cid" in result:
                        entry["data"]["cid"] = result["cid"]
                    
                    self.update_entry_status(
                        entry_id=entry["entry_id"],
                        status=JournalEntryStatus.COMPLETED,
                        result=result
                    )
                    
                    logger.info(f"Stored dataset {dataset_path} with distributed={result.get('distributed', False)}")
                    return result
                else:
                    # Fallback to local operation
                    result = {
                        "success": True,
                        "local_path": dataset_path,
                        "metadata": metadata or {},
                        "distributed": False,
                        "message": "ipfs_datasets not available, using local storage"
                    }
                    
                    self.update_entry_status(
                        entry_id=entry["entry_id"],
                        status=JournalEntryStatus.COMPLETED,
                        result=result
                    )
                    
                    logger.info(f"Stored dataset {dataset_path} locally (ipfs_datasets not available)")
                    return result
                    
            except Exception as e:
                logger.error(f"Error storing dataset {dataset_path}: {e}")
                error_result = {
                    "success": False,
                    "error": str(e)
                }
                
                self.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.FAILED,
                    result=error_result
                )
                
                return error_result
    
    def version_dataset(self, dataset_id: str, version: str, 
                       parent_version: Optional[str] = None,
                       transformations: Optional[List[str]] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a versioned dataset with provenance tracking.
        
        This method creates a new version of a dataset with full lineage tracking,
        logging transformations applied and parent versions. This enables complete
        dataset provenance for reproducibility.
        
        Args:
            dataset_id: Identifier for the dataset
            version: New version string (e.g., "1.0.0")
            parent_version: Optional parent version for lineage
            transformations: Optional list of transformation descriptions
            metadata: Additional metadata
        
        Returns:
            Dictionary with version info, CID (if distributed), and provenance log entry
        """
        with self._lock:
            # Prepare metadata with provenance
            full_metadata = metadata or {}
            full_metadata["provenance"] = {
                "parent_version": parent_version,
                "transformations": transformations or []
            }
            
            # Add journal entry for versioning operation
            entry = self.add_journal_entry(
                operation_type=JournalOperationType.DATASET,  # Using DATASET type for dataset operations
                path=f"dataset:{dataset_id}",
                data={
                    "operation": "dataset_version",
                    "dataset_id": dataset_id,
                    "version": version,
                    "parent_version": parent_version,
                    "transformations": transformations or [],
                    "metadata": full_metadata,
                    "timestamp": time.time()
                }
            )
            
            try:
                # Try to use ipfs_datasets if available
                if self.enable_ipfs_datasets and self.ipfs_datasets_manager:
                    result = self.ipfs_datasets_manager.version(
                        dataset_id=dataset_id,
                        version=version,
                        parent_version=parent_version,
                        transformations=transformations
                    )
                    
                    # Update journal entry with result
                    entry["data"]["result"] = result
                    if "cid" in result:
                        entry["data"]["cid"] = result["cid"]
                    
                    self.update_entry_status(
                        entry_id=entry["entry_id"],
                        status=JournalEntryStatus.COMPLETED,
                        result=result
                    )
                    
                    logger.info(f"Created dataset version {dataset_id}:{version}")
                    return result
                else:
                    # Fallback to local versioning
                    result = {
                        "success": True,
                        "dataset_id": dataset_id,
                        "version": version,
                        "metadata": full_metadata,
                        "distributed": False,
                        "message": "ipfs_datasets not available, version logged locally"
                    }
                    
                    self.update_entry_status(
                        entry_id=entry["entry_id"],
                        status=JournalEntryStatus.COMPLETED,
                        result=result
                    )
                    
                    logger.info(f"Created local dataset version {dataset_id}:{version}")
                    return result
                    
            except Exception as e:
                logger.error(f"Error versioning dataset {dataset_id}: {e}")
                error_result = {
                    "success": False,
                    "error": str(e)
                }
                
                self.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.FAILED,
                    result=error_result
                )
                
                return error_result
    
    def get_dataset_event_log(self) -> List[Dict[str, Any]]:
        """
        Get event log for all dataset operations.
        
        Returns:
            List of event log entries for dataset operations
        """
        if self.enable_ipfs_datasets and self.ipfs_datasets_manager:
            return self.ipfs_datasets_manager.get_event_log()
        else:
            # Fallback: extract dataset operations from journal entries
            dataset_events = []
            with self._lock:
                for entry in self.journal_entries:
                    if entry.get("data", {}).get("operation", "").startswith("dataset_"):
                        dataset_events.append({
                            "operation": entry["data"]["operation"],
                            "path": entry.get("path"),
                            "timestamp": entry.get("timestamp"),
                            "status": entry.get("status"),
                            "data": entry.get("data")
                        })
            return dataset_events
    
    def get_dataset_provenance_log(self) -> List[Dict[str, Any]]:
        """
        Get provenance log showing dataset lineage and transformations.
        
        Returns:
            List of provenance entries tracking dataset evolution
        """
        if self.enable_ipfs_datasets and self.ipfs_datasets_manager:
            return self.ipfs_datasets_manager.get_provenance_log()
        else:
            # Fallback: extract versioning operations from journal
            provenance_log = []
            with self._lock:
                for entry in self.journal_entries:
                    if entry.get("data", {}).get("operation") == "dataset_version":
                        data = entry.get("data", {})
                        provenance_log.append({
                            "dataset_id": data.get("dataset_id"),
                            "version": data.get("version"),
                            "parent_version": data.get("parent_version"),
                            "transformations": data.get("transformations", []),
                            "timestamp": entry.get("timestamp"),
                            "cid": data.get("cid")
                        })
            return provenance_log


class FilesystemJournalManager:
    """
    Manager for integrating the FilesystemJournal with a filesystem implementation.
    
    This class provides a higher-level interface for using the FilesystemJournal,
    integrating it with the actual filesystem operations and the Write-Ahead Log.
    """
    
    def __init__(
        self,
        journal: FilesystemJournal,
        wal = None,
        fs_interface = None
    ):
        """
        Initialize the journal manager.
        
        Args:
            journal: FilesystemJournal instance
            wal: Optional WAL instance
            fs_interface: Optional filesystem interface
        """
        self.journal = journal
        self.wal = wal
        self.fs_interface = fs_interface
        
        # Lock for operations
        self._lock = threading.RLock()
    
    def create_file(self, path: str, content: bytes, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a new file with the given content.
        
        Args:
            path: Path to create
            content: File content
            metadata: Optional metadata
            
        Returns:
            Result dictionary
        """
        with self._lock:
            # Begin transaction
            transaction_id = self.journal.begin_transaction()
            
            try:
                # Add journal entry
                entry = self.journal.add_journal_entry(
                    operation_type=JournalOperationType.CREATE,
                    path=path,
                    data={
                        "is_directory": False,
                        "size": len(content),
                        "metadata": metadata or {}
                    }
                )
                
                # Integrate with WAL if available
                if self.wal:
                    wal_result = self.wal.add_operation(
                        operation_type="write",
                        backend="filesystem",
                        parameters={
                            "path": path,
                            "size": len(content),
                            "journal_entry_id": entry["entry_id"]
                        }
                    )
                    
                    # Link the WAL operation ID
                    entry["data"]["wal_operation_id"] = wal_result.get("operation_id")
                
                # Perform actual filesystem operation
                result = None
                if self.fs_interface:
                    # Call the filesystem interface to create the file
                    result = self.fs_interface.write_file(path, content, metadata)
                    
                    # Update journal entry with CID if available
                    if result and "cid" in result:
                        entry["data"]["cid"] = result["cid"]
                
                # Mark journal entry as completed
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.COMPLETED,
                    result=result
                )
                
                # Commit transaction
                self.journal.commit_transaction()
                
                return {
                    "success": True,
                    "path": path,
                    "entry_id": entry["entry_id"],
                    "transaction_id": transaction_id,
                    "result": result
                }
                
            except Exception as e:
                # Rollback transaction on error
                self.journal.rollback_transaction()
                
                logger.error(f"Error creating file {path}: {e}")
                return {
                    "success": False,
                    "path": path,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
    
    def create_directory(self, path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a new directory.
        
        Args:
            path: Path to create
            metadata: Optional metadata
            
        Returns:
            Result dictionary
        """
        with self._lock:
            # Begin transaction
            transaction_id = self.journal.begin_transaction()
            
            try:
                # Add journal entry
                entry = self.journal.add_journal_entry(
                    operation_type=JournalOperationType.CREATE,
                    path=path,
                    data={
                        "is_directory": True,
                        "metadata": metadata or {}
                    }
                )
                
                # Integrate with WAL if available
                if self.wal:
                    wal_result = self.wal.add_operation(
                        operation_type="mkdir",
                        backend="filesystem",
                        parameters={
                            "path": path,
                            "journal_entry_id": entry["entry_id"]
                        }
                    )
                    
                    # Link the WAL operation ID
                    entry["data"]["wal_operation_id"] = wal_result.get("operation_id")
                
                # Perform actual filesystem operation
                result = None
                if self.fs_interface:
                    # Call the filesystem interface to create the directory
                    result = self.fs_interface.mkdir(path, metadata)
                
                # Mark journal entry as completed
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.COMPLETED,
                    result=result
                )
                
                # Commit transaction
                self.journal.commit_transaction()
                
                return {
                    "success": True,
                    "path": path,
                    "entry_id": entry["entry_id"],
                    "transaction_id": transaction_id,
                    "result": result
                }
                
            except Exception as e:
                # Rollback transaction on error
                self.journal.rollback_transaction()
                
                logger.error(f"Error creating directory {path}: {e}")
                return {
                    "success": False,
                    "path": path,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
    
    def delete(self, path: str) -> Dict[str, Any]:
        """
        Delete a file or directory.
        
        Args:
            path: Path to delete
            
        Returns:
            Result dictionary
        """
        with self._lock:
            # Begin transaction
            transaction_id = self.journal.begin_transaction()
            
            try:
                # Add journal entry
                entry = self.journal.add_journal_entry(
                    operation_type=JournalOperationType.DELETE,
                    path=path
                )
                
                # Integrate with WAL if available
                if self.wal:
                    wal_result = self.wal.add_operation(
                        operation_type="rm",
                        backend="filesystem",
                        parameters={
                            "path": path,
                            "journal_entry_id": entry["entry_id"]
                        }
                    )
                    
                    # Link the WAL operation ID
                    entry["data"]["wal_operation_id"] = wal_result.get("operation_id")
                
                # Perform actual filesystem operation
                result = None
                if self.fs_interface:
                    # Check if it's a file or directory
                    is_dir = False
                    if hasattr(self.fs_interface, "isdir"):
                        is_dir = self.fs_interface.isdir(path)
                    
                    # Call the appropriate method
                    if is_dir:
                        result = self.fs_interface.rmdir(path)
                    else:
                        result = self.fs_interface.rm(path)
                
                # Mark journal entry as completed
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.COMPLETED,
                    result=result
                )
                
                # Commit transaction
                self.journal.commit_transaction()
                
                return {
                    "success": True,
                    "path": path,
                    "entry_id": entry["entry_id"],
                    "transaction_id": transaction_id,
                    "result": result
                }
                
            except Exception as e:
                # Rollback transaction on error
                self.journal.rollback_transaction()
                
                logger.error(f"Error deleting {path}: {e}")
                return {
                    "success": False,
                    "path": path,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
    
    def rename(self, old_path: str, new_path: str) -> Dict[str, Any]:
        """
        Rename a file or directory.
        
        Args:
            old_path: Current path
            new_path: New path
            
        Returns:
            Result dictionary
        """
        with self._lock:
            # Begin transaction
            transaction_id = self.journal.begin_transaction()
            
            try:
                # Add journal entry
                entry = self.journal.add_journal_entry(
                    operation_type=JournalOperationType.RENAME,
                    path=old_path,
                    data={"new_path": new_path}
                )
                
                # Integrate with WAL if available
                if self.wal:
                    wal_result = self.wal.add_operation(
                        operation_type="move",
                        backend="filesystem",
                        parameters={
                            "src_path": old_path,
                            "dst_path": new_path,
                            "journal_entry_id": entry["entry_id"]
                        }
                    )
                    
                    # Link the WAL operation ID
                    entry["data"]["wal_operation_id"] = wal_result.get("operation_id")
                
                # Perform actual filesystem operation
                result = None
                if self.fs_interface:
                    result = self.fs_interface.move(old_path, new_path)
                
                # Mark journal entry as completed
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.COMPLETED,
                    result=result
                )
                
                # Commit transaction
                self.journal.commit_transaction()
                
                return {
                    "success": True,
                    "old_path": old_path,
                    "new_path": new_path,
                    "entry_id": entry["entry_id"],
                    "transaction_id": transaction_id,
                    "result": result
                }
                
            except Exception as e:
                # Rollback transaction on error
                self.journal.rollback_transaction()
                
                logger.error(f"Error renaming {old_path} to {new_path}: {e}")
                return {
                    "success": False,
                    "old_path": old_path,
                    "new_path": new_path,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
    
    def write_file(self, path: str, content: bytes, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Write content to a file, creating it if it doesn't exist.
        
        Args:
            path: Path to write
            content: File content
            metadata: Optional metadata
            
        Returns:
            Result dictionary
        """
        with self._lock:
            # Check if file exists
            fs_state = self.journal.get_fs_state()
            if path in fs_state:
                # File exists, use write operation
                return self._write_existing_file(path, content, metadata)
            else:
                # File doesn't exist, create it
                return self.create_file(path, content, metadata)
    
    def _write_existing_file(self, path: str, content: bytes, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Write to an existing file."""
        with self._lock:
            # Begin transaction
            transaction_id = self.journal.begin_transaction()
            
            try:
                # Add journal entry
                entry = self.journal.add_journal_entry(
                    operation_type=JournalOperationType.WRITE,
                    path=path,
                    data={
                        "size": len(content),
                        "metadata": metadata or {}
                    }
                )
                
                # Integrate with WAL if available
                if self.wal:
                    wal_result = self.wal.add_operation(
                        operation_type="write",
                        backend="filesystem",
                        parameters={
                            "path": path,
                            "size": len(content),
                            "journal_entry_id": entry["entry_id"]
                        }
                    )
                    
                    # Link the WAL operation ID
                    entry["data"]["wal_operation_id"] = wal_result.get("operation_id")
                
                # Perform actual filesystem operation
                result = None
                if self.fs_interface:
                    result = self.fs_interface.write_file(path, content, metadata)
                    
                    # Update journal entry with CID if available
                    if result and "cid" in result:
                        entry["data"]["cid"] = result["cid"]
                
                # Mark journal entry as completed
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.COMPLETED,
                    result=result
                )
                
                # Commit transaction
                self.journal.commit_transaction()
                
                return {
                    "success": True,
                    "path": path,
                    "entry_id": entry["entry_id"],
                    "transaction_id": transaction_id,
                    "result": result
                }
                
            except Exception as e:
                # Rollback transaction on error
                self.journal.rollback_transaction()
                
                logger.error(f"Error writing to file {path}: {e}")
                return {
                    "success": False,
                    "path": path,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
    
    def update_metadata(self, path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update metadata for a file or directory.
        
        Args:
            path: Path to update
            metadata: Metadata to update
            
        Returns:
            Result dictionary
        """
        with self._lock:
            # Begin transaction
            transaction_id = self.journal.begin_transaction()
            
            try:
                # Add journal entry
                entry = self.journal.add_journal_entry(
                    operation_type=JournalOperationType.METADATA,
                    path=path,
                    data={"metadata": metadata}
                )
                
                # Integrate with WAL if available
                if self.wal:
                    wal_result = self.wal.add_operation(
                        operation_type="metadata",
                        backend="filesystem",
                        parameters={
                            "path": path,
                            "metadata": metadata,
                            "journal_entry_id": entry["entry_id"]
                        }
                    )
                    
                    # Link the WAL operation ID
                    entry["data"]["wal_operation_id"] = wal_result.get("operation_id")
                
                # Perform actual filesystem operation
                result = None
                if self.fs_interface:
                    result = self.fs_interface.update_metadata(path, metadata)
                
                # Mark journal entry as completed
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.COMPLETED,
                    result=result
                )
                
                # Commit transaction
                self.journal.commit_transaction()
                
                return {
                    "success": True,
                    "path": path,
                    "entry_id": entry["entry_id"],
                    "transaction_id": transaction_id,
                    "result": result
                }
                
            except Exception as e:
                # Rollback transaction on error
                self.journal.rollback_transaction()
                
                logger.error(f"Error updating metadata for {path}: {e}")
                return {
                    "success": False,
                    "path": path,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
    
    def mount(self, path: str, cid: str, is_directory: bool = False, 
             metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Mount a CID at a specific path.
        
        Args:
            path: Path to mount at
            cid: Content ID to mount
            is_directory: Whether the CID represents a directory
            metadata: Optional metadata
            
        Returns:
            Result dictionary
        """
        with self._lock:
            # Begin transaction
            transaction_id = self.journal.begin_transaction()
            
            try:
                # Add journal entry
                entry = self.journal.add_journal_entry(
                    operation_type=JournalOperationType.MOUNT,
                    path=path,
                    data={
                        "cid": cid,
                        "is_directory": is_directory,
                        "metadata": metadata or {}
                    }
                )
                
                # Integrate with WAL if available
                if self.wal:
                    wal_result = self.wal.add_operation(
                        operation_type="mount",
                        backend="filesystem",
                        parameters={
                            "path": path,
                            "cid": cid,
                            "is_directory": is_directory,
                            "journal_entry_id": entry["entry_id"]
                        }
                    )
                    
                    # Link the WAL operation ID
                    entry["data"]["wal_operation_id"] = wal_result.get("operation_id")
                
                # Perform actual filesystem operation
                result = None
                if self.fs_interface and hasattr(self.fs_interface, "mount"):
                    result = self.fs_interface.mount(path, cid, is_directory, metadata)
                
                # Mark journal entry as completed
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.COMPLETED,
                    result=result
                )
                
                # Commit transaction
                self.journal.commit_transaction()
                
                return {
                    "success": True,
                    "path": path,
                    "cid": cid,
                    "entry_id": entry["entry_id"],
                    "transaction_id": transaction_id,
                    "result": result
                }
                
            except Exception as e:
                # Rollback transaction on error
                self.journal.rollback_transaction()
                
                logger.error(f"Error mounting CID {cid} at {path}: {e}")
                return {
                    "success": False,
                    "path": path,
                    "cid": cid,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
    
    def unmount(self, path: str) -> Dict[str, Any]:
        """
        Unmount a path.
        
        Args:
            path: Path to unmount
            
        Returns:
            Result dictionary
        """
        with self._lock:
            # Begin transaction
            transaction_id = self.journal.begin_transaction()
            
            try:
                # Add journal entry
                entry = self.journal.add_journal_entry(
                    operation_type=JournalOperationType.UNMOUNT,
                    path=path
                )
                
                # Integrate with WAL if available
                if self.wal:
                    wal_result = self.wal.add_operation(
                        operation_type="unmount",
                        backend="filesystem",
                        parameters={
                            "path": path,
                            "journal_entry_id": entry["entry_id"]
                        }
                    )
                    
                    # Link the WAL operation ID
                    entry["data"]["wal_operation_id"] = wal_result.get("operation_id")
                
                # Perform actual filesystem operation
                result = None
                if self.fs_interface and hasattr(self.fs_interface, "unmount"):
                    result = self.fs_interface.unmount(path)
                
                # Mark journal entry as completed
                self.journal.update_entry_status(
                    entry_id=entry["entry_id"],
                    status=JournalEntryStatus.COMPLETED,
                    result=result
                )
                
                # Commit transaction
                self.journal.commit_transaction()
                
                return {
                    "success": True,
                    "path": path,
                    "entry_id": entry["entry_id"],
                    "transaction_id": transaction_id,
                    "result": result
                }
                
            except Exception as e:
                # Rollback transaction on error
                self.journal.rollback_transaction()
                
                logger.error(f"Error unmounting {path}: {e}")
                return {
                    "success": False,
                    "path": path,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
    
    def get_journal_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the journal.
        
        Returns:
            Dictionary with journal statistics
        """
        try:
            with self._lock:
                # Get stats from journal
                stats = {
                    "entry_count": self.journal.entry_count,
                    "journal_id": self.journal.current_journal_id,
                    "last_sync_time": self.journal.last_sync_time,
                    "last_checkpoint_time": self.journal.last_checkpoint_time,
                    "in_transaction": self.journal.in_transaction,
                    "state_paths": len(self.journal.fs_state),
                    "transaction_entries": len(self.journal.transaction_entries) if self.journal.in_transaction else 0
                }
                
                # Count entries by type and status
                entry_types = {}
                entry_statuses = {}
                
                for entry in self.journal.journal_entries:
                    op_type = entry.get("operation_type")
                    status = entry.get("status")
                    
                    if op_type not in entry_types:
                        entry_types[op_type] = 0
                    entry_types[op_type] += 1
                    
                    if status not in entry_statuses:
                        entry_statuses[status] = 0
                    entry_statuses[status] += 1
                
                stats["entries_by_type"] = entry_types
                stats["entries_by_status"] = entry_statuses
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting journal stats: {e}")
            return {"error": str(e)}


# Export key classes and enums
__all__ = [
    'FilesystemJournal',
    'FilesystemJournalManager',
    'JournalOperationType',
    'JournalEntryStatus'
]