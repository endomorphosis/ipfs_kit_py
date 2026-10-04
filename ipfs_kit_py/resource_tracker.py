#!/usr/bin/env python3
"""
Resource Tracker - Bandwidth and Storage Monitoring for Remote Filesystem Backends

This module provides comprehensive tracking of resource consumption across all
remote filesystem backends using the fast index system. It monitors:
- Bandwidth usage (upload/download)
- Storage consumption
- Operation costs
- Performance metrics

Storage Location: ~/.ipfs_kit/resource_tracking/
Index Database: ~/.ipfs_kit/resource_tracking/resource_tracker.db (SQLite)
Metrics Data: ~/.ipfs_kit/resource_tracking/metrics/ (partitioned by date/backend)

Dependencies: Only built-in Python modules + sqlite3
"""

import sqlite3
import json
import time
import os
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

class ResourceType(Enum):
    """Types of resources being tracked."""
    BANDWIDTH_UPLOAD = "bandwidth_upload"
    BANDWIDTH_DOWNLOAD = "bandwidth_download"
    STORAGE_USED = "storage_used"
    STORAGE_ALLOCATED = "storage_allocated"
    API_CALLS = "api_calls"
    OPERATION_COST = "operation_cost"

class BackendType(Enum):
    """Supported backend types."""
    S3 = "s3"
    IPFS = "ipfs"
    HUGGINGFACE = "huggingface"
    STORACHA = "storacha"
    FILECOIN = "filecoin"
    LASSIE = "lassie"
    LOCAL = "local"

@dataclass
class ResourceMetric:
    """Represents a single resource measurement."""
    backend_name: str
    backend_type: BackendType
    resource_type: ResourceType
    amount: int  # bytes for bandwidth/storage, count for API calls, cents for cost
    operation_id: Optional[str] = None
    file_path: Optional[str] = None
    timestamp: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class FastResourceTracker:
    """
    Ultra-fast resource tracker using SQLite index.
    
    This class provides instant access to resource consumption metrics across
    all remote filesystem backends. It's designed to be lightweight and fast
    for CLI/MCP integration.
    """
    
    def __init__(self, base_path: str = "~/.ipfs_kit/resource_tracking"):
        self.base_path = Path(os.path.expanduser(base_path))
        self.index_path = self.base_path / "resource_tracker.db"
        self.metrics_path = self.base_path / "metrics"
        self.lock = threading.RLock()
        
        # Ensure directories exist
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.metrics_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize index database
        self._init_index_db()
    
    def _init_index_db(self):
        """Initialize the SQLite index database."""
        with sqlite3.connect(str(self.index_path)) as conn:
            # Resource usage table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resource_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backend_name TEXT NOT NULL,
                    backend_type TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    operation_id TEXT,
                    file_path TEXT,
                    timestamp REAL NOT NULL,
                    metadata_json TEXT
                )
            """)
            
            # Indexes for fast queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_backend_name ON resource_usage(backend_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_backend_type ON resource_usage(backend_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_resource_type ON resource_usage(resource_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON resource_usage(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_operation_id ON resource_usage(operation_id)")
            
            # Aggregated statistics table for fast summary queries
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resource_summary (
                    backend_name TEXT NOT NULL,
                    backend_type TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    period TEXT NOT NULL,  -- 'hour', 'day', 'week', 'month'
                    period_start REAL NOT NULL,
                    total_amount INTEGER NOT NULL,
                    operation_count INTEGER NOT NULL,
                    avg_amount REAL NOT NULL,
                    max_amount INTEGER NOT NULL,
                    min_amount INTEGER NOT NULL,
                    last_updated REAL NOT NULL,
                    PRIMARY KEY (backend_name, backend_type, resource_type, period, period_start)
                )
            """)
            
            # Backend configuration and limits
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backend_limits (
                    backend_name TEXT PRIMARY KEY,
                    backend_type TEXT NOT NULL,
                    bandwidth_limit_mbps INTEGER,
                    storage_limit_gb INTEGER,
                    api_calls_limit_per_hour INTEGER,
                    cost_limit_cents_per_day INTEGER,
                    last_updated REAL NOT NULL
                )
            """)
            
            # Current backend status
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backend_status (
                    backend_name TEXT PRIMARY KEY,
                    backend_type TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    current_bandwidth_usage_mbps REAL DEFAULT 0,
                    current_storage_usage_gb REAL DEFAULT 0,
                    last_operation_timestamp REAL,
                    health_status TEXT DEFAULT 'unknown',
                    last_health_check REAL,
                    metadata_json TEXT
                )
            """)
    
    def track_resource_usage(self, metric: ResourceMetric) -> bool:
        """
        Track a resource usage event.
        
        Args:
            metric: ResourceMetric containing usage information
            
        Returns:
            bool: True if tracking was successful
        """
        try:
            with self.lock:
                timestamp = metric.timestamp or time.time()
                metadata_json = json.dumps(metric.metadata) if metric.metadata else None
                
                with sqlite3.connect(str(self.index_path)) as conn:
                    conn.execute("""
                        INSERT INTO resource_usage 
                        (backend_name, backend_type, resource_type, amount, 
                         operation_id, file_path, timestamp, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        metric.backend_name,
                        metric.backend_type.value,
                        metric.resource_type.value,
                        metric.amount,
                        metric.operation_id,
                        metric.file_path,
                        timestamp,
                        metadata_json
                    ))
                
                # Update aggregated statistics
                self._update_summary_stats(metric, timestamp)
                
                return True
                
        except Exception as e:
            print(f"Error tracking resource usage: {e}")
            return False
    
    def _update_summary_stats(self, metric: ResourceMetric, timestamp: float):
        """Update aggregated statistics for fast summary queries."""
        periods = {
            'hour': 3600,
            'day': 86400,
            'week': 604800,
            'month': 2592000
        }
        
        with sqlite3.connect(str(self.index_path)) as conn:
            for period_name, period_seconds in periods.items():
                period_start = timestamp - (timestamp % period_seconds)
                
                # Get existing summary
                existing = conn.execute("""
                    SELECT total_amount, operation_count, max_amount, min_amount
                    FROM resource_summary
                    WHERE backend_name = ? AND backend_type = ? AND resource_type = ?
                    AND period = ? AND period_start = ?
                """, (
                    metric.backend_name,
                    metric.backend_type.value,
                    metric.resource_type.value,
                    period_name,
                    period_start
                )).fetchone()
                
                if existing:
                    # Update existing summary
                    total_amount = existing[0] + metric.amount
                    operation_count = existing[1] + 1
                    max_amount = max(existing[2], metric.amount)
                    min_amount = min(existing[3], metric.amount)
                    avg_amount = total_amount / operation_count
                    
                    conn.execute("""
                        UPDATE resource_summary 
                        SET total_amount = ?, operation_count = ?, avg_amount = ?,
                            max_amount = ?, min_amount = ?, last_updated = ?
                        WHERE backend_name = ? AND backend_type = ? AND resource_type = ?
                        AND period = ? AND period_start = ?
                    """, (
                        total_amount, operation_count, avg_amount,
                        max_amount, min_amount, timestamp,
                        metric.backend_name, metric.backend_type.value,
                        metric.resource_type.value, period_name, period_start
                    ))
                else:
                    # Create new summary
                    conn.execute("""
                        INSERT INTO resource_summary
                        (backend_name, backend_type, resource_type, period, period_start,
                         total_amount, operation_count, avg_amount, max_amount, min_amount, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        metric.backend_name, metric.backend_type.value,
                        metric.resource_type.value, period_name, period_start,
                        metric.amount, 1, metric.amount, metric.amount, metric.amount, timestamp
                    ))
    
    def get_resource_usage(self, 
                          backend_name: Optional[str] = None,
                          backend_type: Optional[BackendType] = None,
                          resource_type: Optional[ResourceType] = None,
                          hours_back: int = 24,
                          limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get resource usage records.
        
        Args:
            backend_name: Filter by backend name
            backend_type: Filter by backend type
            resource_type: Filter by resource type
            hours_back: How many hours back to query
            limit: Maximum records to return
            
        Returns:
            List of resource usage records
        """
        try:
            cutoff_time = time.time() - (hours_back * 3600)
            
            conditions = ["timestamp >= ?"]
            params = [cutoff_time]
            
            if backend_name:
                conditions.append("backend_name = ?")
                params.append(backend_name)
            
            if backend_type:
                conditions.append("backend_type = ?")
                params.append(backend_type.value)
                
            if resource_type:
                conditions.append("resource_type = ?")
                params.append(resource_type.value)
            
            where_clause = " AND ".join(conditions)
            params.append(limit)
            
            with sqlite3.connect(str(self.index_path)) as conn:
                cursor = conn.execute(f"""
                    SELECT backend_name, backend_type, resource_type, amount,
                           operation_id, file_path, timestamp, metadata_json
                    FROM resource_usage
                    WHERE {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, params)
                
                results = []
                for row in cursor.fetchall():
                    metadata = json.loads(row[7]) if row[7] else {}
                    results.append({
                        'backend_name': row[0],
                        'backend_type': row[1],
                        'resource_type': row[2],
                        'amount': row[3],
                        'operation_id': row[4],
                        'file_path': row[5],
                        'timestamp': row[6],
                        'datetime': datetime.fromtimestamp(row[6]).isoformat(),
                        'metadata': metadata
                    })
                
                return results
                
        except Exception as e:
            print(f"Error getting resource usage: {e}")
            return []
    
    def get_resource_summary(self, 
                           backend_name: Optional[str] = None,
                           backend_type: Optional[BackendType] = None,
                           period: str = 'day') -> Dict[str, Any]:
        """
        Get aggregated resource summary.
        
        Args:
            backend_name: Filter by backend name
            backend_type: Filter by backend type
            period: Time period ('hour', 'day', 'week', 'month')
            
        Returns:
            Dictionary with resource summary by type
        """
        try:
            current_time = time.time()
            
            # Calculate period boundaries
            period_seconds = {
                'hour': 3600,
                'day': 86400,
                'week': 604800,
                'month': 2592000
            }.get(period, 86400)
            
            period_start = current_time - (current_time % period_seconds)
            
            conditions = ["period = ?", "period_start = ?"]
            params = [period, period_start]
            
            if backend_name:
                conditions.append("backend_name = ?")
                params.append(backend_name)
            
            if backend_type:
                conditions.append("backend_type = ?")
                params.append(backend_type.value)
            
            where_clause = " AND ".join(conditions)
            
            with sqlite3.connect(str(self.index_path)) as conn:
                cursor = conn.execute(f"""
                    SELECT backend_name, backend_type, resource_type,
                           total_amount, operation_count, avg_amount, max_amount, min_amount
                    FROM resource_summary
                    WHERE {where_clause}
                    ORDER BY backend_name, resource_type
                """, params)
                
                summary = {
                    'period': period,
                    'period_start': datetime.fromtimestamp(period_start).isoformat(),
                    'backends': {},
                    'totals': {
                        'bandwidth_upload': 0,
                        'bandwidth_download': 0,
                        'storage_used': 0,
                        'api_calls': 0,
                        'operation_cost': 0
                    }
                }
                
                for row in cursor.fetchall():
                    backend_name = row[0]
                    backend_type = row[1]
                    resource_type = row[2]
                    total_amount = row[3]
                    operation_count = row[4]
                    avg_amount = row[5]
                    max_amount = row[6]
                    min_amount = row[7]
                    
                    if backend_name not in summary['backends']:
                        summary['backends'][backend_name] = {
                            'backend_type': backend_type,
                            'resources': {}
                        }
                    
                    summary['backends'][backend_name]['resources'][resource_type] = {
                        'total_amount': total_amount,
                        'operation_count': operation_count,
                        'avg_amount': avg_amount,
                        'max_amount': max_amount,
                        'min_amount': min_amount,
                        'formatted_amount': self._format_resource_amount(resource_type, total_amount)
                    }
                    
                    # Add to totals
                    if resource_type in summary['totals']:
                        summary['totals'][resource_type] += total_amount
                
                return summary
                
        except Exception as e:
            print(f"Error getting resource summary: {e}")
            return {'error': str(e)}
    
    def _format_resource_amount(self, resource_type: str, amount: int) -> str:
        """Format resource amount for human readability."""
        if resource_type in ['bandwidth_upload', 'bandwidth_download', 'storage_used', 'storage_allocated']:
            # Format bytes
            if amount < 1024:
                return f"{amount} B"
            elif amount < 1024 * 1024:
                return f"{amount / 1024:.1f} KB"
            elif amount < 1024 * 1024 * 1024:
                return f"{amount / (1024 * 1024):.1f} MB"
            else:
                return f"{amount / (1024 * 1024 * 1024):.1f} GB"
        elif resource_type == 'api_calls':
            return f"{amount:,} calls"
        elif resource_type == 'operation_cost':
            return f"${amount / 100:.2f}"
        else:
            return str(amount)
    
    def get_backend_status(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current status of backends.
        
        Args:
            backend_name: Specific backend name, or None for all
            
        Returns:
            Dictionary with backend status information
        """
        try:
            conditions = []
            params = []
            
            if backend_name:
                conditions.append("backend_name = ?")
                params.append(backend_name)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            with sqlite3.connect(str(self.index_path)) as conn:
                cursor = conn.execute(f"""
                    SELECT backend_name, backend_type, is_active,
                           current_bandwidth_usage_mbps, current_storage_usage_gb,
                           last_operation_timestamp, health_status, last_health_check,
                           metadata_json
                    FROM backend_status
                    {where_clause}
                    ORDER BY backend_name
                """, params)
                
                results = {}
                for row in cursor.fetchall():
                    metadata = json.loads(row[8]) if row[8] else {}
                    results[row[0]] = {
                        'backend_type': row[1],
                        'is_active': bool(row[2]),
                        'current_bandwidth_usage_mbps': row[3],
                        'current_storage_usage_gb': row[4],
                        'last_operation_timestamp': row[5],
                        'last_operation_datetime': datetime.fromtimestamp(row[5]).isoformat() if row[5] else None,
                        'health_status': row[6],
                        'last_health_check': row[7],
                        'last_health_check_datetime': datetime.fromtimestamp(row[7]).isoformat() if row[7] else None,
                        'metadata': metadata
                    }
                
                return results
                
        except Exception as e:
            print(f"Error getting backend status: {e}")
            return {'error': str(e)}
    
    def update_backend_status(self, 
                            backend_name: str,
                            backend_type: BackendType,
                            is_active: bool = True,
                            bandwidth_usage_mbps: Optional[float] = None,
                            storage_usage_gb: Optional[float] = None,
                            health_status: str = 'healthy',
                            metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update backend status information.
        
        Args:
            backend_name: Name of the backend
            backend_type: Type of backend
            is_active: Whether backend is currently active
            bandwidth_usage_mbps: Current bandwidth usage in Mbps
            storage_usage_gb: Current storage usage in GB
            health_status: Health status string
            metadata: Additional metadata
            
        Returns:
            bool: True if update was successful
        """
        try:
            with self.lock:
                current_time = time.time()
                metadata_json = json.dumps(metadata) if metadata else None
                
                with sqlite3.connect(str(self.index_path)) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO backend_status
                        (backend_name, backend_type, is_active, current_bandwidth_usage_mbps,
                         current_storage_usage_gb, last_operation_timestamp, health_status,
                         last_health_check, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        backend_name,
                        backend_type.value,
                        1 if is_active else 0,
                        bandwidth_usage_mbps,
                        storage_usage_gb,
                        current_time,
                        health_status,
                        current_time,
                        metadata_json
                    ))
                
                return True
                
        except Exception as e:
            print(f"Error updating backend status: {e}")
            return False

# Singleton instance for global access
_resource_tracker = None

def get_resource_tracker() -> FastResourceTracker:
    """Get the global resource tracker instance."""
    global _resource_tracker
    if _resource_tracker is None:
        _resource_tracker = FastResourceTracker()
    return _resource_tracker

# Convenience functions for common tracking operations
def track_bandwidth_upload(backend_name: str, backend_type: BackendType, bytes_uploaded: int, 
                          operation_id: Optional[str] = None, file_path: Optional[str] = None) -> bool:
    """Track bandwidth upload usage."""
    tracker = get_resource_tracker()
    metric = ResourceMetric(
        backend_name=backend_name,
        backend_type=backend_type,
        resource_type=ResourceType.BANDWIDTH_UPLOAD,
        amount=bytes_uploaded,
        operation_id=operation_id,
        file_path=file_path
    )
    return tracker.track_resource_usage(metric)

def track_bandwidth_download(backend_name: str, backend_type: BackendType, bytes_downloaded: int,
                            operation_id: Optional[str] = None, file_path: Optional[str] = None) -> bool:
    """Track bandwidth download usage."""
    tracker = get_resource_tracker()
    metric = ResourceMetric(
        backend_name=backend_name,
        backend_type=backend_type,
        resource_type=ResourceType.BANDWIDTH_DOWNLOAD,
        amount=bytes_downloaded,
        operation_id=operation_id,
        file_path=file_path
    )
    return tracker.track_resource_usage(metric)

def track_storage_usage(backend_name: str, backend_type: BackendType, bytes_stored: int,
                       operation_id: Optional[str] = None, file_path: Optional[str] = None) -> bool:
    """Track storage usage."""
    tracker = get_resource_tracker()
    metric = ResourceMetric(
        backend_name=backend_name,
        backend_type=backend_type,
        resource_type=ResourceType.STORAGE_USED,
        amount=bytes_stored,
        operation_id=operation_id,
        file_path=file_path
    )
    return tracker.track_resource_usage(metric)

def track_api_call(backend_name: str, backend_type: BackendType, 
                  operation_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Track API call usage."""
    tracker = get_resource_tracker()
    metric = ResourceMetric(
        backend_name=backend_name,
        backend_type=backend_type,
        resource_type=ResourceType.API_CALLS,
        amount=1,
        operation_id=operation_id,
        metadata=metadata
    )
    return tracker.track_resource_usage(metric)
