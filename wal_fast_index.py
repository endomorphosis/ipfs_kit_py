#!/usr/bin/env python3
"""
Fast WAL Index - Lightweight Write-Ahead Log reader for CLI and MCP server.

This module provides ultra-fast access to WAL information without loading
heavy dependencies. It's designed to be imported by CLI and MCP server
for instant access to WAL status, pending operations, and statistics.

Storage Location: ~/.ipfs_kit/wal/
Index Database: ~/.ipfs_kit/wal/wal_index.db (SQLite)
Parquet Data: ~/.ipfs_kit/wal/data/ (partitioned by date)

Dependencies: Only built-in Python modules + sqlite3
"""

import sqlite3
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

class FastWALReader:
    """
    Ultra-fast WAL reader using SQLite index.
    
    This class provides instant access to WAL information by maintaining
    a lightweight SQLite index that's updated by the daemon but can be
    read instantly by CLI/MCP without any heavy imports.
    """
    
    def __init__(self, base_path: str = "~/.ipfs_kit/wal"):
        self.base_path = Path(os.path.expanduser(base_path))
        self.index_path = self.base_path / "wal_index.db"
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
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON wal_operations(status)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_backend_type ON wal_operations(backend_type)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON wal_operations(created_at)
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wal_stats (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            conn.commit()
    
    def get_status(self) -> Dict[str, Any]:
        """Get overall WAL status."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get operation counts by status
                cursor.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM wal_operations 
                    GROUP BY status
                """)
                status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
                
                # Get operation counts by backend
                cursor.execute("""
                    SELECT backend_type, COUNT(*) as count 
                    FROM wal_operations 
                    GROUP BY backend_type
                """)
                backend_counts = {row['backend_type']: row['count'] for row in cursor.fetchall()}
                
                # Get latest stats
                cursor.execute("""
                    SELECT key, value, updated_at 
                    FROM wal_stats 
                    ORDER BY updated_at DESC
                """)
                stats = {row['key']: json.loads(row['value']) for row in cursor.fetchall()}
                
                return {
                    "total_operations": sum(status_counts.values()),
                    "pending_operations": status_counts.get("pending", 0),
                    "failed_operations": status_counts.get("failed", 0),
                    "completed_operations": status_counts.get("completed", 0),
                    "processing_operations": status_counts.get("processing", 0),
                    "status_breakdown": status_counts,
                    "backend_breakdown": backend_counts,
                    "stats": stats,
                    "last_updated": time.time()
                }
        except Exception as e:
            return {
                "error": f"Failed to read WAL status: {e}",
                "total_operations": 0,
                "pending_operations": 0,
                "failed_operations": 0,
                "completed_operations": 0,
                "last_updated": time.time()
            }
    
    def list_pending_operations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List pending WAL operations."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, operation_type, backend_type, status, created_at, 
                           path, size, retry_count, error_message, metadata_json
                    FROM wal_operations 
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (limit,))
                
                operations = []
                for row in cursor.fetchall():
                    op = dict(row)
                    op['created_datetime'] = datetime.fromtimestamp(op['created_at']).isoformat()
                    if op['metadata_json']:
                        try:
                            op['metadata'] = json.loads(op['metadata_json'])
                        except:
                            op['metadata'] = {}
                    del op['metadata_json']
                    operations.append(op)
                
                return operations
        except Exception as e:
            return [{"error": f"Failed to list pending operations: {e}"}]
    
    def list_failed_operations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List failed WAL operations."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, operation_type, backend_type, status, created_at, 
                           updated_at, path, size, retry_count, error_message, metadata_json
                    FROM wal_operations 
                    WHERE status = 'failed'
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (limit,))
                
                operations = []
                for row in cursor.fetchall():
                    op = dict(row)
                    op['created_datetime'] = datetime.fromtimestamp(op['created_at']).isoformat()
                    op['updated_datetime'] = datetime.fromtimestamp(op['updated_at']).isoformat()
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
    
    def get_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific WAL operation by ID."""
        try:
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM wal_operations WHERE id = ?
                """, (operation_id,))
                
                row = cursor.fetchone()
                if row:
                    op = dict(row)
                    op['created_datetime'] = datetime.fromtimestamp(op['created_at']).isoformat()
                    op['updated_datetime'] = datetime.fromtimestamp(op['updated_at']).isoformat()
                    if op['metadata_json']:
                        try:
                            op['metadata'] = json.loads(op['metadata_json'])
                        except:
                            op['metadata'] = {}
                    del op['metadata_json']
                    return op
                return None
        except Exception as e:
            return {"error": f"Failed to get operation: {e}"}
    
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get WAL statistics for the specified time period."""
        try:
            cutoff_time = time.time() - (hours * 3600)
            
            with sqlite3.connect(str(self.index_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Operations in time period
                cursor.execute("""
                    SELECT operation_type, backend_type, status, COUNT(*) as count
                    FROM wal_operations 
                    WHERE created_at >= ?
                    GROUP BY operation_type, backend_type, status
                """, (cutoff_time,))
                
                stats = {}
                for row in cursor.fetchall():
                    op_type = row['operation_type']
                    backend = row['backend_type']
                    status = row['status']
                    count = row['count']
                    
                    if op_type not in stats:
                        stats[op_type] = {}
                    if backend not in stats[op_type]:
                        stats[op_type][backend] = {}
                    stats[op_type][backend][status] = count
                
                # Overall totals
                cursor.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                           SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                           SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                    FROM wal_operations 
                    WHERE created_at >= ?
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
        """Check WAL health and accessibility."""
        try:
            # Check database connectivity
            with sqlite3.connect(str(self.index_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM wal_operations")
                total_ops = cursor.fetchone()[0]
            
            # Check data directory
            data_files = len(list(self.data_path.glob("*.parquet"))) if self.data_path.exists() else 0
            
            # Check disk space
            try:
                stat = os.statvfs(str(self.base_path))
                free_bytes = stat.f_frsize * stat.f_availfavail
                free_gb = free_bytes / (1024**3)
            except:
                free_gb = "unknown"
            
            return {
                "status": "healthy",
                "database_accessible": True,
                "total_operations": total_ops,
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


class StandaloneWALReader:
    """
    Completely standalone WAL reader with zero external dependencies.
    Used when even the fast reader is too heavy.
    """
    
    def __init__(self, base_path: str = "~/.ipfs_kit/wal"):
        self.base_path = Path(os.path.expanduser(base_path))
        self.index_path = self.base_path / "wal_index.db"
    
    def get_quick_status(self) -> Dict[str, Any]:
        """Get basic WAL status with minimal processing."""
        try:
            if not self.index_path.exists():
                return {
                    "status": "not_initialized",
                    "message": "WAL not initialized",
                    "operations": 0
                }
            
            import sqlite3
            with sqlite3.connect(str(self.index_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM wal_operations WHERE status = 'pending'")
                pending = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM wal_operations WHERE status = 'failed'")
                failed = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM wal_operations")
                total = cursor.fetchone()[0]
            
            status = "healthy"
            if failed > 0:
                status = "has_failures"
            elif pending > 100:
                status = "high_pending"
            
            return {
                "status": status,
                "total_operations": total,
                "pending_operations": pending,
                "failed_operations": failed,
                "last_check": time.time()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "operations": 0
            }


if __name__ == "__main__":
    """CLI interface for testing WAL fast index."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python wal_fast_index.py [status|pending|failed|stats|health]")
        sys.exit(1)
    
    command = sys.argv[1]
    reader = FastWALReader()
    
    if command == "status":
        result = reader.get_status()
    elif command == "pending":
        result = reader.list_pending_operations(limit=20)
    elif command == "failed":
        result = reader.list_failed_operations(limit=20)
    elif command == "stats":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        result = reader.get_statistics(hours=hours)
    elif command == "health":
        result = reader.health_check()
    else:
        result = {"error": f"Unknown command: {command}"}
    
    print(json.dumps(result, indent=2, default=str))
