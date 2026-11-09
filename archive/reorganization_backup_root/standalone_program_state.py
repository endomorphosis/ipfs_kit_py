#!/usr/bin/env python3
"""
Standalone Program State Storage

Completely independent program state storage that can be used without
importing the IPFS Kit package or triggering any heavy dependencies.
"""

import os
import json
import time
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict

# State directory
STATE_DIR = Path.home() / ".ipfs_kit" / "program_state"
DB_PATH = STATE_DIR / "program_state.db"

@dataclass
class SystemState:
    bandwidth_in: int = 0
    bandwidth_out: int = 0  
    peer_count: int = 0
    ipfs_version: str = ""
    repo_size: int = 0
    last_updated: str = ""

@dataclass  
class FileState:
    total_files: int = 0
    pinned_files: int = 0
    recent_files: List[Dict[str, Any]] = None
    last_updated: str = ""
    
    def __post_init__(self):
        if self.recent_files is None:
            self.recent_files = []

@dataclass
class StorageState:
    backends_active: int = 0
    backends_healthy: int = 0
    total_capacity: int = 0
    used_capacity: int = 0
    backend_status: List[Dict[str, Any]] = None
    last_updated: str = ""
    
    def __post_init__(self):
        if self.backend_status is None:
            self.backend_status = []

@dataclass
class NetworkState:
    connected_peers: List[Dict[str, Any]] = None
    network_health: str = "unknown"
    cluster_status: str = "unknown"  
    last_updated: str = ""
    
    def __post_init__(self):
        if self.connected_peers is None:
            self.connected_peers = []


class StandaloneProgramStateManager:
    """Program state manager without IPFS Kit dependencies."""
    
    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = state_dir or STATE_DIR
        self.db_path = self.state_dir / "program_state.db"
        self.lock = threading.RLock()
        
        # Ensure directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Initialize with default state
        self._ensure_default_state()
    
    def _init_database(self):
        """Initialize SQLite database with state schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS program_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    timestamp REAL
                )
            """)
            conn.commit()
    
    def _ensure_default_state(self):
        """Ensure default state exists."""
        with self.lock:
            try:
                # Check if state exists
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM program_state")
                    count = cursor.fetchone()[0]
                
                # If no state exists, create default
                if count == 0:
                    self._create_default_state()
            except Exception:
                # If anything fails, recreate database
                self._init_database()
                self._create_default_state()
    
    def _create_default_state(self):
        """Create default state values."""
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Create default states
        system_state = SystemState(last_updated=current_time)
        file_state = FileState(
            total_files=150,
            pinned_files=75,
            recent_files=[
                {"cid": "QmTest1", "name": "test1.txt", "size": 100},
                {"cid": "QmTest2", "name": "test2.txt", "size": 200}
            ],
            last_updated=current_time
        )
        storage_state = StorageState(
            backends_active=3,
            backends_healthy=2,
            last_updated=current_time
        )
        network_state = NetworkState(
            connected_peers=[
                {"id": "peer1", "addr": "/ip4/127.0.0.1/tcp/4001"},
                {"id": "peer2", "addr": "/ip4/192.168.1.100/tcp/4001"}
            ],
            network_health="healthy",
            cluster_status="running",
            last_updated=current_time
        )
        
        # Store in database
        with sqlite3.connect(str(self.db_path)) as conn:
            timestamp = time.time()
            
            conn.execute(
                "INSERT OR REPLACE INTO program_state (key, value, timestamp) VALUES (?, ?, ?)",
                ("system_state", json.dumps(asdict(system_state)), timestamp)
            )
            conn.execute(
                "INSERT OR REPLACE INTO program_state (key, value, timestamp) VALUES (?, ?, ?)",
                ("file_state", json.dumps(asdict(file_state)), timestamp)
            )
            conn.execute(
                "INSERT OR REPLACE INTO program_state (key, value, timestamp) VALUES (?, ?, ?)",
                ("storage_state", json.dumps(asdict(storage_state)), timestamp)
            )
            conn.execute(
                "INSERT OR REPLACE INTO program_state (key, value, timestamp) VALUES (?, ?, ?)",
                ("network_state", json.dumps(asdict(network_state)), timestamp)
            )
            
            conn.commit()


class StandaloneFastStateReader:
    """Fast state reader without any dependencies."""
    
    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = state_dir or STATE_DIR
        self.db_path = self.state_dir / "program_state.db"
        
        # Check if database exists
        if not self.db_path.exists():
            raise FileNotFoundError(f"Program state database not found at {self.db_path}")
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """Get a value from the state database."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "SELECT value FROM program_state WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                
                if row:
                    return json.loads(row[0])
                return default
        except Exception:
            return default
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the current program state."""
        try:
            system_state = self.get_value("system_state", {})
            file_state = self.get_value("file_state", {})
            storage_state = self.get_value("storage_state", {})
            network_state = self.get_value("network_state", {})
            
            return {
                "bandwidth_in": system_state.get("bandwidth_in", 0),
                "bandwidth_out": system_state.get("bandwidth_out", 0),
                "peer_count": system_state.get("peer_count", 0),
                "total_files": file_state.get("total_files", 0),
                "pinned_files": file_state.get("pinned_files", 0),
                "backends_active": storage_state.get("backends_active", 0),
                "network_health": network_state.get("network_health", "unknown"),
                "cluster_status": network_state.get("cluster_status", "unknown")
            }
        except Exception:
            return {
                "error": "Failed to read program state",
                "bandwidth_in": 0,
                "bandwidth_out": 0,
                "peer_count": 0,
                "total_files": 0,
                "pinned_files": 0,
                "backends_active": 0,
                "network_health": "unknown",
                "cluster_status": "unknown"
            }


def ensure_state_exists():
    """Ensure program state database exists with default values."""
    try:
        manager = StandaloneProgramStateManager()
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Test the standalone state system
    print("Testing standalone state system...")
    
    # Ensure state exists
    if ensure_state_exists():
        print("✓ State database created/verified")
    else:
        print("✗ Failed to create state database")
        exit(1)
    
    # Test reading
    try:
        reader = StandaloneFastStateReader()
        summary = reader.get_summary()
        print("✓ State reading successful")
        print("Summary:", summary)
    except Exception as e:
        print(f"✗ State reading failed: {e}")
        exit(1)
    
    print("✓ All tests passed!")
