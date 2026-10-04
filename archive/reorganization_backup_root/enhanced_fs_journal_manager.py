#!/usr/bin/env python3
"""
Enhanced FS Journal Manager with Parquet Storage and Fast Indexing

This module provides an enhanced Filesystem Journal system that:
1. Tracks all filesystem operations in partitioned Parquet files
2. Maintains a fast SQLite index for CLI/MCP instant access
3. Provides a virtual filesystem view with current file states
4. Supports high-throughput operation logging with minimal latency
5. Enables fast querying of filesystem history and statistics

The system is designed so that:
- Daemon writes operations to both Parquet files and SQLite index
- CLI/MCP read from the lightweight SQLite index for instant responses
- Virtual filesystem provides current state without heavy backend queries
- Full historical analysis can be performed on Parquet files when needed

Storage Structure:
~/.ipfs_kit/fs_journal/
├── fs_journal_index.db            # Fast SQLite index
├── data/                          # Parquet data files
│   ├── YYYY-MM-DD/               # Date partitions
│   │   ├── operations.parquet    # Daily operations
│   │   └── metadata.json         # Partition metadata
│   └── current/                  # Active partition
└── config.json                   # Journal configuration
"""

import os
import time
import uuid
import json
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Set
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

logger = logging.getLogger(__name__)

class FSOperationType(Enum):
    """Types of filesystem operations."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    LIST = "list"
    MKDIR = "mkdir"
    PIN = "pin"
    UNPIN = "unpin"
    MOVE = "move"
    COPY = "copy"
    STAT = "stat"
    SYNC = "sync"
    IMPORT = "import"
    EXPORT = "export"
    MOUNT = "mount"
    UNMOUNT = "unmount"

class FSFileType(Enum):
    """Types of files in the virtual filesystem."""
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    MOUNT_POINT = "mount_point"

@dataclass
class FSOperation:
    """Represents a filesystem operation."""
    id: str
    operation_type: FSOperationType
    path: str
    backend_name: Optional[str]
    success: bool
    timestamp: float
    size: Optional[int] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['operation_type'] = self.operation_type.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FSOperation':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            operation_type=FSOperationType(data['operation_type']),
            path=data['path'],
            backend_name=data.get('backend_name'),
            success=data['success'],
            timestamp=data['timestamp'],
            size=data.get('size'),
            error_message=data.get('error_message'),
            duration_ms=data.get('duration_ms'),
            metadata=data.get('metadata')
        )

@dataclass
class VirtualFile:
    """Represents a file in the virtual filesystem."""
    path: str
    file_type: FSFileType
    size: Optional[int]
    created_at: float
    modified_at: float
    backend_name: Optional[str] = None
    hash: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['file_type'] = self.file_type.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VirtualFile':
        """Create from dictionary."""
        return cls(
            path=data['path'],
            file_type=FSFileType(data['file_type']),
            size=data.get('size'),
            created_at=data['created_at'],
            modified_at=data['modified_at'],
            backend_name=data.get('backend_name'),
            hash=data.get('hash'),
            metadata=data.get('metadata')
        )

class EnhancedFSJournalManager:
    """
    Enhanced FS Journal Manager with Parquet storage and fast indexing.
    
    This class manages the complete filesystem journal lifecycle:
    1. Records all filesystem operations with detailed metadata
    2. Maintains a virtual filesystem view for fast queries
    3. Stores operations in partitioned Parquet files for analysis
    4. Provides fast SQLite index for CLI/MCP instant access
    5. Supports filesystem consistency checks and repair
    """
    
    def __init__(self, 
                 base_path: str = "~/.ipfs_kit/fs_journal",
                 partition_size: int = 1000,
                 auto_cleanup_days: int = 90,
                 index_sync_interval: int = 5,
                 enable_virtual_fs: bool = True):
        """
        Initialize the enhanced FS journal manager.
        
        Args:
            base_path: Base directory for journal storage
            partition_size: Operations per Parquet partition
            auto_cleanup_days: Days after which to cleanup old operations
            index_sync_interval: Seconds between index sync operations
            enable_virtual_fs: Whether to maintain virtual filesystem
        """
        self.base_path = Path(os.path.expanduser(base_path))
        self.data_path = self.base_path / "data"
        self.current_path = self.data_path / "current"
        self.index_path = self.base_path / "fs_journal_index.db"
        self.config_path = self.base_path / "config.json"
        
        self.partition_size = partition_size
        self.auto_cleanup_days = auto_cleanup_days
        self.index_sync_interval = index_sync_interval
        self.enable_virtual_fs = enable_virtual_fs
        
        # Thread-safe operation tracking
        self._lock = threading.RLock()
        self._virtual_filesystem: Dict[str, VirtualFile] = {}
        self._operation_buffer: List[FSOperation] = []
        self._last_index_sync = 0
        
        # Initialize storage
        self._ensure_directories()
        self._init_index_db()
        self._load_config()
        self._load_virtual_filesystem()
        
        logger.info(f"Enhanced FS Journal Manager initialized at {self.base_path}")
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.current_path.mkdir(parents=True, exist_ok=True)
    
    def _init_index_db(self):
        """Initialize the SQLite index database."""
        with sqlite3.connect(str(self.index_path)) as conn:
            # Operations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fs_operations (
                    id TEXT PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    backend_name TEXT,
                    success INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    size INTEGER,
                    error_message TEXT,
                    duration_ms INTEGER,
                    parquet_file TEXT,
                    metadata_json TEXT
                )
            """)
            
            # Indexes for operations
            conn.execute("CREATE INDEX IF NOT EXISTS idx_operation_type ON fs_operations(operation_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON fs_operations(path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON fs_operations(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_success ON fs_operations(success)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_backend_name ON fs_operations(backend_name)")
            
            # Virtual filesystem table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS virtual_filesystem (
                    path TEXT PRIMARY KEY,
                    file_type TEXT NOT NULL,
                    size INTEGER,
                    created_at REAL NOT NULL,
                    modified_at REAL NOT NULL,
                    backend_name TEXT,
                    hash TEXT,
                    metadata_json TEXT
                )
            """)
            
            # Indexes for virtual filesystem
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vfs_backend ON virtual_filesystem(backend_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vfs_type ON virtual_filesystem(file_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vfs_modified ON virtual_filesystem(modified_at)")
            
            # Statistics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fs_stats (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            conn.commit()
    
    def _load_config(self):
        """Load journal configuration."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.partition_size = config.get('partition_size', self.partition_size)
                self.auto_cleanup_days = config.get('auto_cleanup_days', self.auto_cleanup_days)
                self.enable_virtual_fs = config.get('enable_virtual_fs', self.enable_virtual_fs)
        else:
            self._save_config()
    
    def _save_config(self):
        """Save current configuration."""
        config = {
            'partition_size': self.partition_size,
            'auto_cleanup_days': self.auto_cleanup_days,
            'index_sync_interval': self.index_sync_interval,
            'enable_virtual_fs': self.enable_virtual_fs,
            'created_at': time.time()
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def _load_virtual_filesystem(self):
        """Load virtual filesystem from database."""
        if not self.enable_virtual_fs:
            return
        
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM virtual_filesystem")
                
                for row in cursor.fetchall():
                    file_data = dict(row)
                    if file_data['metadata_json']:
                        file_data['metadata'] = json.loads(file_data['metadata_json'])
                    del file_data['metadata_json']
                    
                    vf = VirtualFile.from_dict(file_data)
                    self._virtual_filesystem[vf.path] = vf
                    
            logger.info(f"Loaded {len(self._virtual_filesystem)} files into virtual filesystem")
        except Exception as e:
            logger.error(f"Failed to load virtual filesystem: {e}")
    
    def record_operation(self, 
                        operation_type: FSOperationType,
                        path: str,
                        success: bool,
                        backend_name: Optional[str] = None,
                        size: Optional[int] = None,
                        error_message: Optional[str] = None,
                        duration_ms: Optional[int] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record a filesystem operation.
        
        Args:
            operation_type: Type of operation performed
            path: File or directory path
            success: Whether the operation succeeded
            backend_name: Backend that performed the operation
            size: Size of file/data involved
            error_message: Error message if operation failed
            duration_ms: Duration of operation in milliseconds
            metadata: Additional metadata
            
        Returns:
            Operation ID
        """
        operation_id = str(uuid.uuid4())
        current_time = time.time()
        
        operation = FSOperation(
            id=operation_id,
            operation_type=operation_type,
            path=path,
            backend_name=backend_name,
            success=success,
            timestamp=current_time,
            size=size,
            error_message=error_message,
            duration_ms=duration_ms,
            metadata=metadata or {}
        )
        
        with self._lock:
            # Add to buffer
            self._operation_buffer.append(operation)
            
            # Update virtual filesystem if enabled and operation was successful
            if self.enable_virtual_fs and success:
                self._update_virtual_filesystem(operation)
            
            # Write to storage
            self._write_operation_to_storage(operation)
            self._sync_operation_to_index(operation)
            
            # Flush buffer if it's getting large
            if len(self._operation_buffer) >= 100:
                self._flush_buffer()
        
        logger.debug(f"Recorded FS operation {operation_id}: {operation_type.value} on {path}")
        return operation_id
    
    def _update_virtual_filesystem(self, operation: FSOperation):
        """Update the virtual filesystem based on an operation."""
        path = operation.path
        current_time = operation.timestamp
        
        if operation.operation_type in [FSOperationType.WRITE, FSOperationType.IMPORT]:
            # File created or modified
            if path in self._virtual_filesystem:
                vf = self._virtual_filesystem[path]
                vf.modified_at = current_time
                if operation.size:
                    vf.size = operation.size
                if operation.backend_name:
                    vf.backend_name = operation.backend_name
                if operation.metadata:
                    vf.metadata = {**(vf.metadata or {}), **operation.metadata}
            else:
                # New file
                file_type = FSFileType.DIRECTORY if operation.operation_type == FSOperationType.MKDIR else FSFileType.FILE
                vf = VirtualFile(
                    path=path,
                    file_type=file_type,
                    size=operation.size,
                    created_at=current_time,
                    modified_at=current_time,
                    backend_name=operation.backend_name,
                    metadata=operation.metadata
                )
                self._virtual_filesystem[path] = vf
        
        elif operation.operation_type == FSOperationType.MKDIR:
            # Directory created
            vf = VirtualFile(
                path=path,
                file_type=FSFileType.DIRECTORY,
                size=None,
                created_at=current_time,
                modified_at=current_time,
                backend_name=operation.backend_name,
                metadata=operation.metadata
            )
            self._virtual_filesystem[path] = vf
        
        elif operation.operation_type == FSOperationType.DELETE:
            # File/directory deleted
            if path in self._virtual_filesystem:
                del self._virtual_filesystem[path]
        
        elif operation.operation_type == FSOperationType.MOVE:
            # File moved (need destination in metadata)
            dest_path = operation.metadata.get('destination') if operation.metadata else None
            if dest_path and path in self._virtual_filesystem:
                vf = self._virtual_filesystem[path]
                del self._virtual_filesystem[path]
                vf.path = dest_path
                vf.modified_at = current_time
                self._virtual_filesystem[dest_path] = vf
    
    def _write_operation_to_storage(self, operation: FSOperation):
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
                'path': [operation.path],
                'backend_name': [operation.backend_name],
                'success': [operation.success],
                'timestamp': [operation.timestamp],
                'size': [operation.size],
                'error_message': [operation.error_message],
                'duration_ms': [operation.duration_ms],
                'metadata_json': [operation_data['metadata_json']]
            })
            
            # Determine partition path
            date_str = datetime.fromtimestamp(operation.timestamp).strftime("%Y-%m-%d")
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
    
    def _sync_operation_to_index(self, operation: FSOperation):
        """Sync operation to SQLite index."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                metadata_json = json.dumps(operation.metadata) if operation.metadata else None
                parquet_file = operation.metadata.get('parquet_file') if operation.metadata else None
                
                conn.execute("""
                    INSERT INTO fs_operations 
                    (id, operation_type, path, backend_name, success, timestamp,
                     size, error_message, duration_ms, parquet_file, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation.id,
                    operation.operation_type.value,
                    operation.path,
                    operation.backend_name,
                    1 if operation.success else 0,
                    operation.timestamp,
                    operation.size,
                    operation.error_message,
                    operation.duration_ms,
                    parquet_file,
                    metadata_json
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to sync operation to index: {e}")
    
    def _sync_virtual_filesystem_to_index(self):
        """Sync virtual filesystem to SQLite index."""
        if not self.enable_virtual_fs:
            return
        
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                # Insert or update virtual filesystem entries
                for vf in self._virtual_filesystem.values():
                    metadata_json = json.dumps(vf.metadata) if vf.metadata else None
                    
                    conn.execute("""
                        INSERT OR REPLACE INTO virtual_filesystem 
                        (path, file_type, size, created_at, modified_at,
                         backend_name, hash, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        vf.path,
                        vf.file_type.value,
                        vf.size,
                        vf.created_at,
                        vf.modified_at,
                        vf.backend_name,
                        vf.hash,
                        metadata_json
                    ))
                
                conn.commit()
                logger.debug(f"Synced {len(self._virtual_filesystem)} virtual files to index")
        except Exception as e:
            logger.error(f"Failed to sync virtual filesystem to index: {e}")
    
    def _flush_buffer(self):
        """Flush the operation buffer."""
        if not self._operation_buffer:
            return
        
        logger.debug(f"Flushing {len(self._operation_buffer)} operations from buffer")
        self._operation_buffer.clear()
    
    def get_virtual_filesystem(self) -> Dict[str, VirtualFile]:
        """Get the current virtual filesystem."""
        with self._lock:
            return dict(self._virtual_filesystem)
    
    def get_file_info(self, path: str) -> Optional[VirtualFile]:
        """Get information about a specific file."""
        with self._lock:
            return self._virtual_filesystem.get(path)
    
    def list_directory(self, path: str) -> List[VirtualFile]:
        """List files in a directory."""
        with self._lock:
            path = path.rstrip('/')
            files = []
            for file_path, vf in self._virtual_filesystem.items():
                if file_path.startswith(path + '/') and '/' not in file_path[len(path)+1:]:
                    files.append(vf)
            return files
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive FS journal statistics."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Operation type breakdown
                cursor.execute("""
                    SELECT operation_type, success, COUNT(*) as count,
                           AVG(COALESCE(duration_ms, 0)) as avg_duration,
                           SUM(COALESCE(size, 0)) as total_size
                    FROM fs_operations 
                    GROUP BY operation_type, success
                """)
                
                operation_stats = {}
                for row in cursor.fetchall():
                    op_type = row['operation_type']
                    success = 'success' if row['success'] else 'failure'
                    
                    if op_type not in operation_stats:
                        operation_stats[op_type] = {}
                    
                    operation_stats[op_type][success] = {
                        'count': row['count'],
                        'avg_duration_ms': row['avg_duration'],
                        'total_size': row['total_size']
                    }
                
                # Backend breakdown
                cursor.execute("""
                    SELECT backend_name, COUNT(*) as count 
                    FROM fs_operations 
                    WHERE backend_name IS NOT NULL
                    GROUP BY backend_name
                """)
                backend_stats = {row['backend_name']: row['count'] for row in cursor.fetchall()}
                
                # Virtual filesystem stats
                vfs_stats = {}
                if self.enable_virtual_fs:
                    cursor.execute("""
                        SELECT file_type, COUNT(*) as count,
                               SUM(COALESCE(size, 0)) as total_size
                        FROM virtual_filesystem 
                        GROUP BY file_type
                    """)
                    vfs_stats = {row['file_type']: {
                        'count': row['count'],
                        'total_size': row['total_size']
                    } for row in cursor.fetchall()}
                
                # Recent activity
                cutoff_time = time.time() - (24 * 3600)
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM fs_operations 
                    WHERE timestamp >= ?
                """, (cutoff_time,))
                recent_count = cursor.fetchone()['count']
                
                return {
                    'operation_breakdown': operation_stats,
                    'backend_breakdown': backend_stats,
                    'virtual_filesystem': vfs_stats,
                    'recent_24h': recent_count,
                    'buffer_size': len(self._operation_buffer),
                    'virtual_files_in_memory': len(self._virtual_filesystem),
                    'generated_at': time.time()
                }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {'error': str(e)}
    
    def cleanup_old_operations(self, days: int = None) -> int:
        """Clean up old operations."""
        days = days or self.auto_cleanup_days
        cutoff_time = time.time() - (days * 24 * 3600)
        
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM fs_operations WHERE timestamp < ?", (cutoff_time,))
                cleaned_count = cursor.rowcount
                conn.commit()
                
            logger.info(f"Cleaned up {cleaned_count} old operations")
            return cleaned_count
        except Exception as e:
            logger.error(f"Failed to cleanup old operations: {e}")
            return 0
    
    def sync_index(self):
        """Force synchronization of all data to indexes."""
        with self._lock:
            self._flush_buffer()
            self._sync_virtual_filesystem_to_index()
        
        # Update stats
        stats = self.get_statistics()
        with sqlite3.connect(str(self.index_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO fs_stats (key, value, updated_at)
                VALUES ('latest_stats', ?, ?)
            """, (json.dumps(stats), time.time()))
            conn.commit()
        
        self._last_index_sync = time.time()
        logger.debug("FS Journal index synchronized")


if __name__ == "__main__":
    """Example usage and testing."""
    import sys
    
    # Create FS journal manager
    journal = EnhancedFSJournalManager()
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Add some test operations
        print("Recording test operations...")
        
        # Create some files
        for i in range(5):
            journal.record_operation(
                FSOperationType.WRITE,
                f"/test/file_{i}.txt",
                success=True,
                backend_name="ipfs",
                size=1024 * (i + 1),
                duration_ms=50 + i * 10,
                metadata={"test": True, "index": i}
            )
        
        # Create a directory
        journal.record_operation(
            FSOperationType.MKDIR,
            "/test/subdir",
            success=True,
            backend_name="ipfs",
            duration_ms=25
        )
        
        # Record a failed operation
        journal.record_operation(
            FSOperationType.DELETE,
            "/test/nonexistent.txt",
            success=False,
            backend_name="ipfs",
            error_message="File not found",
            duration_ms=15
        )
        
        # Show statistics
        stats = journal.get_statistics()
        print("\nFS Journal Statistics:")
        print(json.dumps(stats, indent=2))
        
        # Show virtual filesystem
        if journal.enable_virtual_fs:
            print(f"\nVirtual Filesystem ({len(journal._virtual_filesystem)} files):")
            for path, vf in journal.get_virtual_filesystem().items():
                print(f"  {path} ({vf.file_type.value}, {vf.size or 0} bytes)")
        
    else:
        print("Usage: python enhanced_fs_journal_manager.py [test]")
        print(f"FS Journal Manager initialized at: {journal.base_path}")
        print(f"Virtual filesystem enabled: {journal.enable_virtual_fs}")
        if journal.enable_virtual_fs:
            print(f"Current virtual files: {len(journal._virtual_filesystem)}")
