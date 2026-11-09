#!/usr/bin/env python3
"""
Enhanced WAL Manager with Parquet Storage and Fast Indexing

This module provides an enhanced Write-Ahead Log system that:
1. Stores operations in partitioned Parquet files for efficient querying
2. Maintains a fast SQLite index for CLI/MCP instant access
3. Supports high-throughput operation logging with minimal latency
4. Provides automatic cleanup and archiving of old operations

The system is designed so that:
- Daemon writes operations to both Parquet files and SQLite index
- CLI/MCP read from the lightweight SQLite index for instant responses
- Full analytical queries can be performed on Parquet files when needed

Storage Structure:
~/.ipfs_kit/wal/
├── wal_index.db                    # Fast SQLite index
├── data/                           # Parquet data files
│   ├── YYYY-MM-DD/                # Date partitions
│   │   ├── operations.parquet     # Daily operations
│   │   └── metadata.json          # Partition metadata
│   └── current/                   # Active partition
└── config.json                    # WAL configuration
"""

import os
import time
import uuid
import json
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, date, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# Optional PyArrow for Parquet support
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from pyarrow import compute as pc
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False


# Import CAR WAL manager
try:
    from ipfs_kit_py.car_wal_manager import get_car_wal_manager
    CAR_WAL_AVAILABLE = True
except ImportError:
    CAR_WAL_AVAILABLE = False

logger = logging.getLogger(__name__)

class WALOperationType(Enum):
    """Types of WAL operations."""
    ADD = "add"
    GET = "get"
    PIN = "pin"
    UNPIN = "unpin"
    RM = "rm"
    CAT = "cat"
    LIST = "list"
    MKDIR = "mkdir"
    COPY = "copy"
    MOVE = "move"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SYNC = "sync"
    CUSTOM = "custom"

class WALOperationStatus(Enum):
    """Status values for WAL operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    ARCHIVED = "archived"

class WALBackendType(Enum):
    """Types of storage backends."""
    IPFS = "ipfs"
    S3 = "s3"
    STORACHA = "storacha"
    LOCAL = "local"
    GDRIVE = "gdrive"
    CUSTOM = "custom"

@dataclass
class WALOperation:
    """Represents a single WAL operation."""
    id: str
    operation_type: WALOperationType
    backend_type: WALBackendType
    status: WALOperationStatus
    created_at: float
    updated_at: float
    path: Optional[str] = None
    size: Optional[int] = None
    retry_count: int = 0
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        # Convert enums to strings
        result['operation_type'] = self.operation_type.value
        result['backend_type'] = self.backend_type.value
        result['status'] = self.status.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WALOperation':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            operation_type=WALOperationType(data['operation_type']),
            backend_type=WALBackendType(data['backend_type']),
            status=WALOperationStatus(data['status']),
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            path=data.get('path'),
            size=data.get('size'),
            retry_count=data.get('retry_count', 0),
            error_message=data.get('error_message'),
            metadata=data.get('metadata'),
            duration_ms=data.get('duration_ms')
        )

class EnhancedWALManager:
    """
    Enhanced WAL Manager with Parquet storage and fast indexing.
    
    This class manages the complete WAL lifecycle:
    1. Accepts new operations and assigns unique IDs
    2. Writes operations to both Parquet files and SQLite index
    3. Processes pending operations asynchronously
    4. Updates operation status and maintains indexes
    5. Archives completed operations and cleans up old data
    """
    
    def __init__(self, 
                 base_path: str = "~/.ipfs_kit/wal",
                 max_pending_operations: int = 10000,
                 partition_size: int = 1000,
                 auto_archive_days: int = 30,
                 index_sync_interval: int = 5):
        """
        Initialize the enhanced WAL manager.
        
        Args:
            base_path: Base directory for WAL storage
            max_pending_operations: Maximum pending operations before backpressure
            partition_size: Operations per Parquet partition
            auto_archive_days: Days after which to archive completed operations
            index_sync_interval: Seconds between index sync operations
        """
        self.base_path = Path(os.path.expanduser(base_path))
        self.data_path = self.base_path / "data"
        self.current_path = self.data_path / "current"
        self.index_path = self.base_path / "wal_index.db"
        self.config_path = self.base_path / "config.json"
        
        self.max_pending_operations = max_pending_operations
        self.partition_size = partition_size
        self.auto_archive_days = auto_archive_days
        self.index_sync_interval = index_sync_interval
        
        # Thread-safe operation tracking
        self._lock = threading.RLock()
        self._pending_operations = {}
        self._current_partition_count = 0
        self._last_index_sync = 0
        
        # Initialize storage
        self._ensure_directories()
        self._init_index_db()
        self._load_config()
        
        logger.info(f"Enhanced WAL Manager initialized at {self.base_path}")
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.current_path.mkdir(parents=True, exist_ok=True)
    
    def _init_index_db(self):
        """Initialize the SQLite index database."""
        with sqlite3.connect(str(self.index_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wal_operations (
                    id TEXT PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    backend_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    path TEXT,
                    size INTEGER,
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    parquet_file TEXT,
                    metadata_json TEXT
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON wal_operations(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_backend_type ON wal_operations(backend_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON wal_operations(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_updated_at ON wal_operations(updated_at)")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wal_stats (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            conn.commit()
    
    def _load_config(self):
        """Load WAL configuration."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.max_pending_operations = config.get('max_pending_operations', self.max_pending_operations)
                self.partition_size = config.get('partition_size', self.partition_size)
        else:
            self._save_config()
    
    def _save_config(self):
        """Save current configuration."""
        config = {
            'max_pending_operations': self.max_pending_operations,
            'partition_size': self.partition_size,
            'auto_archive_days': self.auto_archive_days,
            'index_sync_interval': self.index_sync_interval,
            'created_at': time.time()
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def add_operation(self, 
                     operation_type: WALOperationType,
                     backend_type: WALBackendType,
                     path: Optional[str] = None,
                     size: Optional[int] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new operation to the WAL.
        
        Args:
            operation_type: Type of operation
            backend_type: Target backend
            path: Optional file path
            size: Optional file size
            metadata: Optional metadata dictionary
            
        Returns:
            Operation ID
        """
        operation_id = str(uuid.uuid4())
        current_time = time.time()
        
        operation = WALOperation(
            id=operation_id,
            operation_type=operation_type,
            backend_type=backend_type,
            status=WALOperationStatus.PENDING,
            created_at=current_time,
            updated_at=current_time,
            path=path,
            size=size,
            metadata=metadata or {}
        )
        
        with self._lock:
            # Check if we're at capacity
            if len(self._pending_operations) >= self.max_pending_operations:
                raise Exception(f"WAL at capacity: {len(self._pending_operations)} pending operations")
            
            # Add to pending operations
            self._pending_operations[operation_id] = operation
            
            # Write to storage
            self._write_operation_to_storage(operation)
            self._sync_operation_to_index(operation)
            
        logger.debug(f"Added WAL operation {operation_id}: {operation_type.value} on {backend_type.value}")
        return operation_id
    
    def _write_operation_to_storage(self, operation: WALOperation):
        """Write operation to Parquet storage."""
        if not ARROW_AVAILABLE:
            logger.warning("PyArrow not available, skipping Parquet storage")
            return
        
        try:
            # Create table with operation data
            operation_data = operation.to_dict()
            operation_data['metadata_json'] = json.dumps(operation.metadata) if operation.metadata else None
            
            table = pa.table({
                'id': [operation.id],
                'operation_type': [operation.operation_type.value],
                'backend_type': [operation.backend_type.value],
                'status': [operation.status.value],
                'created_at': [operation.created_at],
                'updated_at': [operation.updated_at],
                'path': [operation.path],
                'size': [operation.size],
                'retry_count': [operation.retry_count],
                'error_message': [operation.error_message],
                'metadata_json': [operation_data['metadata_json']],
                'duration_ms': [operation.duration_ms]
            })
            
            # Determine partition path
            date_str = datetime.fromtimestamp(operation.created_at).strftime("%Y-%m-%d")
            partition_path = self.data_path / date_str
            partition_path.mkdir(exist_ok=True)
            
            parquet_file = partition_path / f"operations_{int(time.time())}.parquet"
            
            # Write to Parquet file
            pq.write_table(table, str(parquet_file))
            
            # Update operation with parquet file reference
            operation.metadata = operation.metadata or {}
            operation.metadata['parquet_file'] = str(parquet_file)
            
        except Exception as e:
            logger.error(f"Failed to write operation to Parquet: {e}")
    
    def _sync_operation_to_index(self, operation: WALOperation):
        """Sync operation to SQLite index."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                metadata_json = json.dumps(operation.metadata) if operation.metadata else None
                parquet_file = operation.metadata.get('parquet_file') if operation.metadata else None
                
                conn.execute("""
                    INSERT OR REPLACE INTO wal_operations 
                    (id, operation_type, backend_type, status, created_at, updated_at,
                     path, size, retry_count, error_message, parquet_file, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation.id,
                    operation.operation_type.value,
                    operation.backend_type.value,
                    operation.status.value,
                    operation.created_at,
                    operation.updated_at,
                    operation.path,
                    operation.size,
                    operation.retry_count,
                    operation.error_message,
                    parquet_file,
                    metadata_json
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to sync operation to index: {e}")
    
    def update_operation_status(self, 
                              operation_id: str, 
                              status: WALOperationStatus,
                              error_message: Optional[str] = None,
                              duration_ms: Optional[int] = None) -> bool:
        """
        Update the status of an operation.
        
        Args:
            operation_id: ID of the operation to update
            status: New status
            error_message: Optional error message
            duration_ms: Optional operation duration
            
        Returns:
            True if update was successful
        """
        with self._lock:
            operation = self._pending_operations.get(operation_id)
            if not operation:
                logger.warning(f"Operation {operation_id} not found in pending operations")
                return False
            
            # Update operation
            operation.status = status
            operation.updated_at = time.time()
            if error_message:
                operation.error_message = error_message
            if duration_ms:
                operation.duration_ms = duration_ms
            
            # If failed, increment retry count
            if status == WALOperationStatus.FAILED:
                operation.retry_count += 1
            
            # If completed or permanently failed, remove from pending
            if status in [WALOperationStatus.COMPLETED, WALOperationStatus.FAILED]:
                if operation.retry_count >= 3:  # Max retries exceeded
                    del self._pending_operations[operation_id]
            
            # Update storage
            self._write_operation_to_storage(operation)
            self._sync_operation_to_index(operation)
            
        return True
    
    def get_pending_operations(self, backend_type: Optional[WALBackendType] = None) -> List[WALOperation]:
        """Get list of pending operations, optionally filtered by backend type."""
        with self._lock:
            operations = list(self._pending_operations.values())
            if backend_type:
                operations = [op for op in operations if op.backend_type == backend_type]
            return operations
    
    def get_operation(self, operation_id: str) -> Optional[WALOperation]:
        """Get a specific operation by ID."""
        with self._lock:
            return self._pending_operations.get(operation_id)
    
    def cleanup_old_operations(self, days: int = None) -> int:
        """
        Clean up old completed operations.
        
        Args:
            days: Days to keep (defaults to auto_archive_days)
            
        Returns:
            Number of operations cleaned up
        """
        days = days or self.auto_archive_days
        cutoff_time = time.time() - (days * 24 * 3600)
        
        cleaned_count = 0
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                cursor = conn.cursor()
                
                # Get old completed operations
                cursor.execute("""
                    SELECT id FROM wal_operations 
                    WHERE status = 'completed' AND updated_at < ?
                """, (cutoff_time,))
                
                old_operations = [row[0] for row in cursor.fetchall()]
                
                # Move to archived status
                cursor.execute("""
                    UPDATE wal_operations 
                    SET status = 'archived' 
                    WHERE status = 'completed' AND updated_at < ?
                """, (cutoff_time,))
                
                cleaned_count = cursor.rowcount
                conn.commit()
                
            logger.info(f"Archived {cleaned_count} old operations")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old operations: {e}")
        
        return cleaned_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive WAL statistics."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Overall counts
                cursor.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM wal_operations 
                    GROUP BY status
                """)
                status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
                
                # Backend breakdown
                cursor.execute("""
                    SELECT backend_type, status, COUNT(*) as count 
                    FROM wal_operations 
                    GROUP BY backend_type, status
                """)
                backend_stats = {}
                for row in cursor.fetchall():
                    backend = row['backend_type']
                    if backend not in backend_stats:
                        backend_stats[backend] = {}
                    backend_stats[backend][row['status']] = row['count']
                
                # Recent activity (last 24 hours)
                cutoff_time = time.time() - (24 * 3600)
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM wal_operations 
                    WHERE created_at >= ?
                """, (cutoff_time,))
                recent_count = cursor.fetchone()['count']
                
                return {
                    'total_operations': sum(status_counts.values()),
                    'status_breakdown': status_counts,
                    'backend_breakdown': backend_stats,
                    'recent_24h': recent_count,
                    'pending_in_memory': len(self._pending_operations),
                    'generated_at': time.time()
                }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {'error': str(e)}
    
    def sync_index(self):
        """Force synchronization of in-memory operations to index."""
        with self._lock:
            for operation in self._pending_operations.values():
                self._sync_operation_to_index(operation)
        
        # Update stats
        stats = self.get_statistics()
        with sqlite3.connect(str(self.index_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO wal_stats (key, value, updated_at)
                VALUES ('latest_stats', ?, ?)
            """, (json.dumps(stats), time.time()))
            conn.commit()
        
        self._last_index_sync = time.time()
        logger.debug("WAL index synchronized")


if __name__ == "__main__":
    """Example usage and testing."""
    import sys
    
    # Create WAL manager
    wal = EnhancedWALManager()
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Add some test operations
        print("Adding test operations...")
        
        for i in range(5):
            op_id = wal.add_operation(
                WALOperationType.ADD,
                WALBackendType.IPFS,
                path=f"/test/file_{i}.txt",
                size=1024 * i,
                metadata={"test": True, "index": i}
            )
            print(f"Added operation {op_id}")
        
        # Update some operations
        ops = wal.get_pending_operations()
        for i, op in enumerate(ops[:2]):
            status = WALOperationStatus.COMPLETED if i == 0 else WALOperationStatus.FAILED
            wal.update_operation_status(op.id, status, 
                                      error_message="Test error" if status == WALOperationStatus.FAILED else None,
                                      duration_ms=100 + i * 50)
        
        # Show statistics
        stats = wal.get_statistics()
        print("\nWAL Statistics:")
        print(json.dumps(stats, indent=2))
        
    else:
        print("Usage: python enhanced_wal_manager.py [test]")
        print(f"WAL Manager initialized at: {wal.base_path}")
        print(f"Current pending operations: {len(wal.get_pending_operations())}")
