"""
IPFS Kit Program State Storage

This module provides a lightweight program state storage system using Parquet and DuckDB.
It stores essential system state that can be quickly accessed without importing heavy
dependencies or invoking storage backends.

Features:
- Fast read/write access to program state
- No heavy dependencies required for reading
- Separate from logs and config
- Thread-safe operations
- Automatic state updates from daemon
- CLI and MCP server can read without backend invocation

State Categories:
- System: Basic system information (bandwidth, peers, version)
- Files: File listings and metadata
- Storage: Storage backend status and metrics
- Network: Network connectivity and peer information
- Performance: System performance metrics
"""

import os
import json
import time
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class SystemState:
    """System-level state information"""
    bandwidth_in: int = 0
    bandwidth_out: int = 0
    peer_count: int = 0
    ipfs_version: str = ""
    repo_size: int = 0
    last_updated: float = 0.0


@dataclass
class FileState:
    """File system state information"""
    total_files: int = 0
    pinned_files: int = 0
    recent_files: List[Dict[str, Any]] = None
    last_updated: float = 0.0
    
    def __post_init__(self):
        if self.recent_files is None:
            self.recent_files = []


@dataclass
class StorageState:
    """Storage backend state information"""
    backends_active: List[str] = None
    backends_healthy: List[str] = None
    storage_usage: Dict[str, int] = None
    last_updated: float = 0.0
    
    def __post_init__(self):
        if self.backends_active is None:
            self.backends_active = []
        if self.backends_healthy is None:
            self.backends_healthy = []
        if self.storage_usage is None:
            self.storage_usage = {}


@dataclass
class NetworkState:
    """Network connectivity state information"""
    connected_peers: List[Dict[str, str]] = None
    network_health: str = "unknown"
    cluster_status: str = "unknown"
    last_updated: float = 0.0
    
    def __post_init__(self):
        if self.connected_peers is None:
            self.connected_peers = []


class ProgramStateManager:
    """
    Lightweight program state manager using SQLite for fast access.
    
    This provides a simple key-value store for program state that can be
    accessed quickly without importing heavy dependencies.
    """
    
    def __init__(self, state_dir: Optional[str] = None):
        """Initialize the program state manager"""
        if state_dir is None:
            state_dir = os.path.expanduser("~/.ipfs_kit/program_state")
        
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.state_dir / "program_state.db"
        self.parquet_dir = self.state_dir / "parquet"
        self.parquet_dir.mkdir(exist_ok=True)
        
        self._lock = threading.Lock()
        self._init_database()
        
        # Also initialize the standalone database for fast access
        self._init_standalone_database()
        
        # Initialize state objects
        self.system_state = SystemState()
        self.file_state = FileState()
        self.storage_state = StorageState()
        self.network_state = NetworkState()
    
    def _init_database(self):
        """Initialize the SQLite database with required tables"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS program_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    category TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_category 
                ON program_state(category)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_updated_at 
                ON program_state(updated_at)
            """)
            
    def _init_standalone_database(self):
        """Initialize the standalone database for fast access."""
        try:
            # Import and initialize the standalone state manager
            import sys
            import os
            standalone_path = os.path.dirname(os.path.dirname(__file__))
            if standalone_path not in sys.path:
                sys.path.insert(0, standalone_path)
            from standalone_program_state import StandaloneProgramStateManager
            
            # This will create the database with default values if it doesn't exist
            self._standalone_manager = StandaloneProgramStateManager()
        except Exception as e:
            # If standalone initialization fails, that's okay - we'll continue with regular state
            self._standalone_manager = None
            
    def _get_current_time(self) -> float:
        """Get current timestamp"""
        return time.time()
    
    def set_state(self, key: str, value: Any, category: str = "general") -> None:
        """Set a state value"""
        with self._lock:
            serialized_value = json.dumps(value, default=str)
            updated_at = self._get_current_time()
            
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO program_state 
                    (key, value, updated_at, category) 
                    VALUES (?, ?, ?, ?)
                """, (key, serialized_value, updated_at, category))
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT value FROM program_state WHERE key = ?
            """, (key,))
            
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0]
            return default
    
    def get_category_state(self, category: str) -> Dict[str, Any]:
        """Get all state values for a category"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT key, value FROM program_state WHERE category = ?
            """, (category,))
            
            result = {}
            for key, value in cursor.fetchall():
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    result[key] = value
            return result
    
    def update_system_state(self, **kwargs) -> None:
        """Update system state"""
        for key, value in kwargs.items():
            if hasattr(self.system_state, key):
                setattr(self.system_state, key, value)
        
        self.system_state.last_updated = self._get_current_time()
        self.set_state("system_state", asdict(self.system_state), "system")
        self._sync_to_standalone()  # Sync to standalone database
    
    def update_file_state(self, **kwargs) -> None:
        """Update file state"""
        for key, value in kwargs.items():
            if hasattr(self.file_state, key):
                setattr(self.file_state, key, value)
        
        self.file_state.last_updated = self._get_current_time()
        self.set_state("file_state", asdict(self.file_state), "files")
        self._sync_to_standalone()  # Sync to standalone database
    
    def update_storage_state(self, **kwargs) -> None:
        """Update storage state"""
        for key, value in kwargs.items():
            if hasattr(self.storage_state, key):
                setattr(self.storage_state, key, value)
        
        self.storage_state.last_updated = self._get_current_time()
        self.set_state("storage_state", asdict(self.storage_state), "storage")
        self._sync_to_standalone()  # Sync to standalone database
    
    def update_network_state(self, **kwargs) -> None:
        """Update network state"""
        for key, value in kwargs.items():
            if hasattr(self.network_state, key):
                setattr(self.network_state, key, value)
        
        self.network_state.last_updated = self._get_current_time()
        self.set_state("network_state", asdict(self.network_state), "network")
        self._sync_to_standalone()  # Sync to standalone database
    
    def _sync_to_standalone(self):
        """Sync current state to the standalone database for fast access."""
        if not self._standalone_manager:
            return
            
        try:
            # Get current state data
            system_data = asdict(self.system_state)
            file_data = asdict(self.file_state)
            storage_data = asdict(self.storage_state)
            network_data = asdict(self.network_state)
            
            # Update standalone database
            with sqlite3.connect(str(self._standalone_manager.db_path)) as conn:
                timestamp = time.time()
                
                conn.execute(
                    "INSERT OR REPLACE INTO program_state (key, value, timestamp) VALUES (?, ?, ?)",
                    ("system_state", json.dumps(system_data), timestamp)
                )
                conn.execute(
                    "INSERT OR REPLACE INTO program_state (key, value, timestamp) VALUES (?, ?, ?)",
                    ("file_state", json.dumps(file_data), timestamp)
                )
                conn.execute(
                    "INSERT OR REPLACE INTO program_state (key, value, timestamp) VALUES (?, ?, ?)",
                    ("storage_state", json.dumps(storage_data), timestamp)
                )
                conn.execute(
                    "INSERT OR REPLACE INTO program_state (key, value, timestamp) VALUES (?, ?, ?)",
                    ("network_state", json.dumps(network_data), timestamp)
                )
                
                conn.commit()
        except Exception:
            # If sync fails, that's okay - standalone is optional
            pass
    
    def get_system_state(self) -> SystemState:
        """Get current system state"""
        state_data = self.get_state("system_state", {})
        if isinstance(state_data, dict):
            return SystemState(**state_data)
        return SystemState()
    
    def get_file_state(self) -> FileState:
        """Get current file state"""
        state_data = self.get_state("file_state", {})
        if isinstance(state_data, dict):
            return FileState(**state_data)
        return FileState()
    
    def get_storage_state(self) -> StorageState:
        """Get current storage state"""
        state_data = self.get_state("storage_state", {})
        if isinstance(state_data, dict):
            return StorageState(**state_data)
        return StorageState()
    
    def get_network_state(self) -> NetworkState:
        """Get current network state"""
        state_data = self.get_state("network_state", {})
        if isinstance(state_data, dict):
            return NetworkState(**state_data)
        return NetworkState()
    
    def get_all_state(self) -> Dict[str, Any]:
        """Get all program state"""
        return {
            "system": self.get_system_state(),
            "files": self.get_file_state(),
            "storage": self.get_storage_state(),
            "network": self.get_network_state(),
        }
    
    def export_to_parquet(self) -> None:
        """Export current state to Parquet files for external access"""
        try:
            import pandas as pd
            import pyarrow as pa
            import pyarrow.parquet as pq
            
            # Export each category to separate Parquet files
            categories = ["system", "files", "storage", "network"]
            
            for category in categories:
                data = self.get_category_state(category)
                if data:
                    df = pd.DataFrame([data])
                    df['updated_at'] = self._get_current_time()
                    
                    parquet_file = self.parquet_dir / f"{category}_state.parquet"
                    df.to_parquet(str(parquet_file), index=False)
                    
        except ImportError:
            # If pandas/pyarrow not available, skip Parquet export
            pass
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get a lightweight summary of current state"""
        system = self.get_system_state()
        files = self.get_file_state()
        storage = self.get_storage_state()
        network = self.get_network_state()
        
        return {
            "bandwidth": {
                "in": system.bandwidth_in,
                "out": system.bandwidth_out
            },
            "peers": system.peer_count,
            "files": {
                "total": files.total_files,
                "pinned": files.pinned_files
            },
            "storage": {
                "backends_active": len(storage.backends_active),
                "backends_healthy": len(storage.backends_healthy)
            },
            "network": {
                "health": network.network_health,
                "cluster_status": network.cluster_status
            },
            "last_updated": max(
                system.last_updated,
                files.last_updated,
                storage.last_updated,
                network.last_updated
            )
        }


class FastStateReader:
    """
    Minimal dependency reader for program state.
    
    This class can be used to read program state with minimal imports,
    making it suitable for CLI tools and quick status checks.
    """
    
    def __init__(self, state_dir: Optional[str] = None):
        if state_dir is None:
            state_dir = os.path.expanduser("~/.ipfs_kit/program_state")
        
        self.state_dir = Path(state_dir)
        self.db_path = self.state_dir / "program_state.db"
        
        if not self.db_path.exists():
            raise FileNotFoundError(f"Program state database not found at {self.db_path}")
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """Get a single state value with minimal overhead"""
        try:
            import sqlite3
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("SELECT value FROM program_state WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    try:
                        import json
                        return json.loads(row[0])
                    except:
                        return row[0]
                return default
        except Exception:
            return default
    
    def get_summary(self) -> Dict[str, Any]:
        """Get state summary with minimal dependencies"""
        try:
            import sqlite3
            import json
            
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("""
                    SELECT key, value FROM program_state 
                    WHERE key IN ('system_state', 'file_state', 'storage_state', 'network_state')
                """)
                
                result = {}
                for key, value in cursor.fetchall():
                    try:
                        result[key] = json.loads(value)
                    except:
                        result[key] = value
                
                # Extract key metrics
                system = result.get('system_state', {})
                files = result.get('file_state', {})
                storage = result.get('storage_state', {})
                network = result.get('network_state', {})
                
                return {
                    "bandwidth_in": system.get('bandwidth_in', 0),
                    "bandwidth_out": system.get('bandwidth_out', 0),
                    "peer_count": system.get('peer_count', 0),
                    "total_files": files.get('total_files', 0),
                    "pinned_files": files.get('pinned_files', 0),
                    "backends_active": len(storage.get('backends_active', [])),
                    "network_health": network.get('network_health', 'unknown'),
                    "cluster_status": network.get('cluster_status', 'unknown')
                }
        except Exception:
            return {}


# Global instance for easy access
_global_state_manager = None


def get_program_state_manager() -> ProgramStateManager:
    """Get the global program state manager instance"""
    global _global_state_manager
    if _global_state_manager is None:
        _global_state_manager = ProgramStateManager()
    return _global_state_manager


def get_fast_state_reader() -> FastStateReader:
    """Get a fast state reader for minimal dependency access"""
    return FastStateReader()
