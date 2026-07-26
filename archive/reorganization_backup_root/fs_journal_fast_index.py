#!/usr/bin/env python3
"""
Fast FS Journal Index - Lightweight filesystem journal reader for CLI and MCP server.

This module provides ultra-fast access to filesystem journal information without
loading heavy dependencies. It's designed to be imported by CLI and MCP server
for instant access to filesystem operation history, statistics, and current state.

Storage Location: ~/.ipfs_kit/fs_journal/
Index Database: ~/.ipfs_kit/fs_journal/fs_journal_index.db (SQLite)
Parquet Data: ~/.ipfs_kit/fs_journal/data/ (partitioned by date)

Dependencies: Only built-in Python modules + sqlite3
"""

import sqlite3
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

class FastFSJournalReader:
    """
    Ultra-fast FS Journal reader using SQLite index.
    
    This class provides instant access to filesystem journal information by
    maintaining a lightweight SQLite index that's updated by the daemon but
    can be read instantly by CLI/MCP without any heavy imports.
    """
    
    def __init__(self, base_path: str = "~/.ipfs_kit/fs_journal"):
        self.base_path = Path(os.path.expanduser(base_path))
        self.index_path = self.base_path / "fs_journal_index.db"
        self.data_path = self.base_path / "data"
        
        # Ensure directories exist
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize index database
        self._init_index_db()
    
    def _init_index_db(self):
        """Initialize the SQLite index database."""
        with sqlite3.connect(str(self.index_path)) as conn:
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
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_operation_type ON fs_operations(operation_type)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_path ON fs_operations(path)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON fs_operations(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_success ON fs_operations(success)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_backend_name ON fs_operations(backend_name)
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fs_stats (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
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
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vfs_backend ON virtual_filesystem(backend_name)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vfs_type ON virtual_filesystem(file_type)
            """)
            
            conn.commit()
    
    def get_status(self) -> Dict[str, Any]:
        """Get overall FS Journal status."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get operation counts by type
                cursor.execute("""
                    SELECT operation_type, COUNT(*) as count 
                    FROM fs_operations 
                    GROUP BY operation_type
                """)
                operation_counts = {row['operation_type']: row['count'] for row in cursor.fetchall()}
                
                # Get success/failure counts
                cursor.execute("""
                    SELECT success, COUNT(*) as count 
                    FROM fs_operations 
                    GROUP BY success
                """)
                success_counts = {('success' if row['success'] else 'failure'): row['count'] for row in cursor.fetchall()}
                
                # Get backend counts
                cursor.execute("""
                    SELECT backend_name, COUNT(*) as count 
                    FROM fs_operations 
                    WHERE backend_name IS NOT NULL
                    GROUP BY backend_name
                """)
                backend_counts = {row['backend_name']: row['count'] for row in cursor.fetchall()}
                
                # Get virtual filesystem stats
                cursor.execute("""
                    SELECT file_type, COUNT(*) as count, 
                           SUM(COALESCE(size, 0)) as total_size
                    FROM virtual_filesystem 
                    GROUP BY file_type
                """)
                vfs_stats = {}
                for row in cursor.fetchall():
                    vfs_stats[row['file_type']] = {
                        'count': row['count'],
                        'total_size': row['total_size'] or 0
                    }
                
                # Get latest stats
                cursor.execute("""
                    SELECT key, value, updated_at 
                    FROM fs_stats 
                    ORDER BY updated_at DESC
                """)
                stats = {row['key']: json.loads(row['value']) for row in cursor.fetchall()}
                
                return {
                    "total_operations": sum(operation_counts.values()),
                    "successful_operations": success_counts.get("success", 0),
                    "failed_operations": success_counts.get("failure", 0),
                    "operation_breakdown": operation_counts,
                    "backend_breakdown": backend_counts,
                    "virtual_filesystem": vfs_stats,
                    "stats": stats,
                    "last_updated": time.time()
                }
        except Exception as e:
            return {
                "error": f"Failed to read FS Journal status: {e}",
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "last_updated": time.time()
            }
    
    def list_recent_operations(self, limit: int = 100, hours: int = 24) -> List[Dict[str, Any]]:
        """List recent filesystem operations."""
        try:
            cutoff_time = time.time() - (hours * 3600)
            
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, operation_type, path, backend_name, success, 
                           timestamp, size, error_message, duration_ms, metadata_json
                    FROM fs_operations 
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (cutoff_time, limit))
                
                operations = []
                for row in cursor.fetchall():
                    op = dict(row)
                    op['datetime'] = datetime.fromtimestamp(op['timestamp']).isoformat()
                    if op['metadata_json']:
                        try:
                            op['metadata'] = json.loads(op['metadata_json'])
                        except:
                            op['metadata'] = {}
                    del op['metadata_json']
                    operations.append(op)
                
                return operations
        except Exception as e:
            return [{"error": f"Failed to list recent operations: {e}"}]
    
    def list_failed_operations(self, limit: int = 100, hours: int = 24) -> List[Dict[str, Any]]:
        """List failed filesystem operations."""
        try:
            cutoff_time = time.time() - (hours * 3600)
            
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, operation_type, path, backend_name, timestamp, 
                           size, error_message, duration_ms, metadata_json
                    FROM fs_operations 
                    WHERE success = 0 AND timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (cutoff_time, limit))
                
                operations = []
                for row in cursor.fetchall():
                    op = dict(row)
                    op['datetime'] = datetime.fromtimestamp(op['timestamp']).isoformat()
                    if op['metadata_json']:
                        try:
                            op['metadata'] = json.loads(op['metadata_json'])
                        except:
                            op['metadata'] = {}
                    del op['metadata_json']
                    operations.append(op)
                
                return operations
        except Exception as e:
            return [{"error": f"Failed to list failed operations: {e}"}]
    
    def list_virtual_files(self, path_prefix: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
        """List files in the virtual filesystem."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if path_prefix:
                    cursor.execute("""
                        SELECT path, file_type, size, created_at, modified_at, 
                               backend_name, hash, metadata_json
                        FROM virtual_filesystem 
                        WHERE path LIKE ?
                        ORDER BY path
                        LIMIT ?
                    """, (f"{path_prefix}%", limit))
                else:
                    cursor.execute("""
                        SELECT path, file_type, size, created_at, modified_at, 
                               backend_name, hash, metadata_json
                        FROM virtual_filesystem 
                        ORDER BY path
                        LIMIT ?
                    """, (limit,))
                
                files = []
                for row in cursor.fetchall():
                    file_info = dict(row)
                    file_info['created_datetime'] = datetime.fromtimestamp(file_info['created_at']).isoformat()
                    file_info['modified_datetime'] = datetime.fromtimestamp(file_info['modified_at']).isoformat()
                    if file_info['metadata_json']:
                        try:
                            file_info['metadata'] = json.loads(file_info['metadata_json'])
                        except:
                            file_info['metadata'] = {}
                    del file_info['metadata_json']
                    files.append(file_info)
                
                return files
        except Exception as e:
            return [{"error": f"Failed to list virtual files: {e}"}]
    
    def get_file_info(self, path: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific file in the virtual filesystem."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM virtual_filesystem WHERE path = ?
                """, (path,))
                
                row = cursor.fetchone()
                if row:
                    file_info = dict(row)
                    file_info['created_datetime'] = datetime.fromtimestamp(file_info['created_at']).isoformat()
                    file_info['modified_datetime'] = datetime.fromtimestamp(file_info['modified_at']).isoformat()
                    if file_info['metadata_json']:
                        try:
                            file_info['metadata'] = json.loads(file_info['metadata_json'])
                        except:
                            file_info['metadata'] = {}
                    del file_info['metadata_json']
                    
                    # Get recent operations on this file
                    cursor.execute("""
                        SELECT operation_type, success, timestamp, error_message
                        FROM fs_operations 
                        WHERE path = ?
                        ORDER BY timestamp DESC
                        LIMIT 10
                    """, (path,))
                    
                    operations = []
                    for op_row in cursor.fetchall():
                        op = dict(op_row)
                        op['datetime'] = datetime.fromtimestamp(op['timestamp']).isoformat()
                        operations.append(op)
                    
                    file_info['recent_operations'] = operations
                    return file_info
                return None
        except Exception as e:
            return {"error": f"Failed to get file info: {e}"}
    
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get FS Journal statistics for the specified time period."""
        try:
            cutoff_time = time.time() - (hours * 3600)
            
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Operations in time period
                cursor.execute("""
                    SELECT operation_type, backend_name, success, COUNT(*) as count,
                           AVG(COALESCE(duration_ms, 0)) as avg_duration,
                           SUM(COALESCE(size, 0)) as total_size
                    FROM fs_operations 
                    WHERE timestamp >= ?
                    GROUP BY operation_type, backend_name, success
                """, (cutoff_time,))
                
                stats = {}
                for row in cursor.fetchall():
                    op_type = row['operation_type']
                    backend = row['backend_name'] or 'unknown'
                    success = 'success' if row['success'] else 'failure'
                    
                    if op_type not in stats:
                        stats[op_type] = {}
                    if backend not in stats[op_type]:
                        stats[op_type][backend] = {}
                    
                    stats[op_type][backend][success] = {
                        'count': row['count'],
                        'avg_duration_ms': row['avg_duration'],
                        'total_size': row['total_size']
                    }
                
                # Overall totals
                cursor.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                           SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed,
                           AVG(COALESCE(duration_ms, 0)) as avg_duration,
                           SUM(COALESCE(size, 0)) as total_size
                    FROM fs_operations 
                    WHERE timestamp >= ?
                """, (cutoff_time,))
                
                totals = dict(cursor.fetchone())
                
                return {
                    "time_period_hours": hours,
                    "totals": totals,
                    "breakdown": stats,
                    "generated_at": time.time()
                }
        except Exception as e:
            return {"error": f"Failed to get statistics: {e}"}
    
    def health_check(self) -> Dict[str, Any]:
        """Check FS Journal health and accessibility."""
        try:
            # Check database connectivity
            with sqlite3.connect(str(self.index_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM fs_operations")
                total_ops = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM virtual_filesystem")
                total_files = cursor.fetchone()[0]
            
            # Check data directory
            data_files = len(list(self.data_path.glob("*.parquet"))) if self.data_path.exists() else 0
            
            # Check disk space
            try:
                stat = os.statvfs(str(self.base_path))
                free_bytes = stat.f_frsize * stat.f_bavail
                free_gb = free_bytes / (1024**3)
            except:
                free_gb = "unknown"
            
            return {
                "status": "healthy",
                "database_accessible": True,
                "total_operations": total_ops,
                "virtual_files": total_files,
                "parquet_files": data_files,
                "free_disk_gb": free_gb,
                "base_path": str(self.base_path),
                "last_check": time.time()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "database_accessible": False,
                "last_check": time.time()
            }


class StandaloneFSJournalReader:
    """
    Completely standalone FS Journal reader with zero external dependencies.
    Used when even the fast reader is too heavy.
    """
    
    def __init__(self, base_path: str = "~/.ipfs_kit/fs_journal"):
        self.base_path = Path(os.path.expanduser(base_path))
        self.index_path = self.base_path / "fs_journal_index.db"
    
    def get_quick_status(self) -> Dict[str, Any]:
        """Get basic FS Journal status with minimal processing."""
        try:
            if not self.index_path.exists():
                return {
                    "status": "not_initialized",
                    "message": "FS Journal not initialized",
                    "operations": 0,
                    "files": 0
                }
            
            import sqlite3
            with sqlite3.connect(str(self.index_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM fs_operations")
                total_ops = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM fs_operations WHERE success = 0")
                failed_ops = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM virtual_filesystem")
                total_files = cursor.fetchone()[0]
            
            status = "healthy"
            if failed_ops > 10:
                status = "has_failures"
            elif total_ops == 0:
                status = "no_activity"
            
            return {
                "status": status,
                "total_operations": total_ops,
                "failed_operations": failed_ops,
                "virtual_files": total_files,
                "last_check": time.time()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "operations": 0,
                "files": 0
            }


if __name__ == "__main__":
    """CLI interface for testing FS Journal fast index."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python fs_journal_fast_index.py [status|recent|failed|files|stats|health]")
        sys.exit(1)
    
    command = sys.argv[1]
    reader = FastFSJournalReader()
    
    if command == "status":
        result = reader.get_status()
    elif command == "recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        result = reader.list_recent_operations(limit=limit)
    elif command == "failed":
        result = reader.list_failed_operations(limit=20)
    elif command == "files":
        prefix = sys.argv[2] if len(sys.argv) > 2 else ""
        result = reader.list_virtual_files(path_prefix=prefix, limit=50)
    elif command == "stats":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        result = reader.get_statistics(hours=hours)
    elif command == "health":
        result = reader.health_check()
    else:
        result = {"error": f"Unknown command: {command}"}
    
    print(json.dumps(result, indent=2, default=str))
