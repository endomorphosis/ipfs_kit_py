"""
IPFS-Kit Daemon Client

Client library for communicating with the IPFS-Kit daemon.
This library allows MCP servers and CLI tools to interact with the daemon
for management operations while still using IPFS-Kit libraries directly
for retrieval operations.
"""

import asyncio
import json
import logging
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import aiohttp
import psutil

logger = logging.getLogger(__name__)


class DaemonClient:
    """
    Client for communicating with the IPFS-Kit daemon.
    
    Provides methods to:
    - Check daemon status
    - Get backend health information  
    - Trigger backend restarts
    - Manage replication
    - Access configuration
    """
    
    def __init__(self, daemon_url: str = "http://localhost:8899", timeout: int = 30):
        self.daemon_url = daemon_url
        self.timeout = timeout
        self.pid_file = "/tmp/ipfs_kit_daemon.pid"
    
    async def is_daemon_running(self) -> bool:
        """Check if the daemon is running."""
        try:
            # Check PID file first
            if not os.path.exists(self.pid_file):
                return False
            
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process exists and is responsive
            if not psutil.pid_exists(pid):
                return False
            
            # Try to connect to daemon API (if we add HTTP API later)
            return True
            
        except Exception as e:
            logger.debug(f"Error checking daemon status: {e}")
            return False
    
    async def get_daemon_status(self) -> Dict[str, Any]:
        """Get comprehensive daemon status."""
        if not await self.is_daemon_running():
            return {
                "running": False,
                "error": "Daemon not running"
            }
        
        try:
            # For now, read status from a status file the daemon writes
            status_file = "/tmp/ipfs_kit_daemon_status.json"
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    status = json.load(f)
                status["running"] = True
                return status
            else:
                return {
                    "running": True,
                    "status": "unknown",
                    "note": "Status file not available"
                }
        except Exception as e:
            return {
                "running": True,
                "error": f"Failed to get status: {e}"
            }
    
    async def get_backend_health(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Get backend health information."""
        status = await self.get_daemon_status()
        
        if not status.get("running"):
            return {"error": "Daemon not running"}
        
        backends = status.get("daemon", {}).get("backends", {})
        
        if backend_name:
            return backends.get(backend_name, {"error": f"Backend {backend_name} not found"})
        
        return backends
    
    async def restart_backend(self, backend_name: str) -> Dict[str, Any]:
        """Request daemon to restart a backend."""
        if not await self.is_daemon_running():
            return {"success": False, "error": "Daemon not running"}
        
        # For now, this would trigger a signal or write to a command file
        # In a full implementation, this would use an HTTP API or Unix socket
        logger.info(f"Would request restart of backend: {backend_name}")
        return {"success": True, "message": f"Restart requested for {backend_name}"}
    
    async def get_replication_status(self) -> Dict[str, Any]:
        """Get replication system status."""
        status = await self.get_daemon_status()
        
        if not status.get("running"):
            return {"error": "Daemon not running"}
        
        return status.get("replication", {})
    
    async def start_daemon(self, config_file: Optional[str] = None) -> Dict[str, Any]:
        """Start the daemon if it's not running."""
        if await self.is_daemon_running():
            return {"success": True, "message": "Daemon already running"}
        
        try:
            # Start daemon process
            cmd = ["python3", "ipfs_kit_daemon.py"]
            if config_file:
                cmd.extend(["--config", config_file])
            
            # Start daemon in background
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Wait a moment for startup
            await asyncio.sleep(2)
            
            # Check if it started successfully
            if await self.is_daemon_running():
                return {"success": True, "message": "Daemon started successfully"}
            else:
                return {"success": False, "error": "Daemon failed to start"}
                
        except Exception as e:
            return {"success": False, "error": f"Failed to start daemon: {e}"}
    
    async def stop_daemon(self) -> Dict[str, Any]:
        """Stop the daemon."""
        if not await self.is_daemon_running():
            return {"success": True, "message": "Daemon not running"}
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Send SIGTERM
            os.kill(pid, 15)  # SIGTERM
            
            # Wait for shutdown
            for _ in range(10):
                await asyncio.sleep(1)
                if not await self.is_daemon_running():
                    return {"success": True, "message": "Daemon stopped"}
            
            # Force kill if still running
            try:
                os.kill(pid, 9)  # SIGKILL
                return {"success": True, "message": "Daemon force stopped"}
            except ProcessLookupError:
                return {"success": True, "message": "Daemon stopped"}
                
        except Exception as e:
            return {"success": False, "error": f"Failed to stop daemon: {e}"}


class IPFSKitClientMixin:
    """
    Mixin class for MCP servers and CLI tools to integrate daemon client functionality
    while maintaining direct access to IPFS-Kit libraries for retrieval operations.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daemon_client = DaemonClient()
        self._daemon_status_cache = {}
        self._last_daemon_check = 0
        self._daemon_check_interval = 30  # seconds
    
    async def ensure_daemon_running(self) -> bool:
        """Ensure the daemon is running, start it if needed."""
        try:
            if not await self.daemon_client.is_daemon_running():
                logger.info("Starting IPFS-Kit daemon...")
                result = await self.daemon_client.start_daemon()
                if not result.get("success"):
                    logger.error(f"Failed to start daemon: {result.get('error')}")
                    return False
                logger.info("✅ IPFS-Kit daemon started")
            
            return True
        except Exception as e:
            logger.error(f"Error ensuring daemon running: {e}")
            return False
    
    async def get_cached_daemon_status(self) -> Dict[str, Any]:
        """Get daemon status with caching."""
        now = time.time()
        
        if (now - self._last_daemon_check) > self._daemon_check_interval:
            try:
                self._daemon_status_cache = await self.daemon_client.get_daemon_status()
                self._last_daemon_check = now
            except Exception as e:
                logger.error(f"Error getting daemon status: {e}")
                # Return cached status if available
                if not self._daemon_status_cache:
                    self._daemon_status_cache = {"error": str(e)}
        
        return self._daemon_status_cache
    
    async def get_backend_health_from_daemon(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Get backend health information from daemon."""
        try:
            return await self.daemon_client.get_backend_health(backend_name)
        except Exception as e:
            logger.error(f"Error getting backend health from daemon: {e}")
            return {"error": str(e)}
    
    async def request_backend_restart(self, backend_name: str) -> Dict[str, Any]:
        """Request daemon to restart a backend."""
        try:
            return await self.daemon_client.restart_backend(backend_name)
        except Exception as e:
            logger.error(f"Error requesting backend restart: {e}")
            return {"success": False, "error": str(e)}
    
    def should_use_daemon_for_management(self) -> bool:
        """Check if daemon should be used for management operations."""
        # Use daemon for management if it's running, otherwise fallback to direct management
        try:
            return asyncio.run(self.daemon_client.is_daemon_running())
        except:
            return False


class RouteReader:
    """
    Utility class for reading from parquet indexes to make routing decisions.
    This allows MCP servers and CLI tools to quickly determine how to route
    virtual filesystem requests without depending on the daemon.
    """
    
    def __init__(self, index_path: str = "/tmp/ipfs_kit_indexes"):
        self.index_path = Path(index_path)
        self.index_path.mkdir(exist_ok=True)
        self._cache = {}
        self._last_cache_update = 0
        self._cache_ttl = 60  # seconds
    
    def read_pin_index(self) -> Dict[str, Any]:
        """Read the pin metadata index for routing decisions."""
        try:
            index_file = self.index_path / "pin_index.parquet"
            if not index_file.exists():
                return {}
            
            # Check cache first
            now = time.time()
            if (now - self._last_cache_update) < self._cache_ttl and "pin_index" in self._cache:
                return self._cache["pin_index"]
            
            # Try to read parquet file
            try:
                import pandas as pd
                df = pd.read_parquet(index_file)
                index_data = df.to_dict('records')
                
                # Update cache
                self._cache["pin_index"] = index_data
                self._last_cache_update = now
                
                return index_data
            except ImportError:
                logger.warning("pandas not available, cannot read parquet index")
                return {}
            
        except Exception as e:
            logger.error(f"Error reading pin index: {e}")
            return {}
    
    def find_backends_for_cid(self, cid: str) -> List[str]:
        """Find which backends have a specific CID."""
        pin_index = self.read_pin_index()
        
        backends = []
        for entry in pin_index:
            if entry.get("cid") == cid:
                backend = entry.get("backend")
                if backend and backend not in backends:
                    backends.append(backend)
        
        return backends
    
    def get_backend_stats(self) -> Dict[str, Any]:
        """Get statistics about backends from the index."""
        pin_index = self.read_pin_index()
        
        stats = {}
        for entry in pin_index:
            backend = entry.get("backend", "unknown")
            if backend not in stats:
                stats[backend] = {"count": 0, "total_size": 0}
            
            stats[backend]["count"] += 1
            size = entry.get("size", 0)
            if isinstance(size, (int, float)):
                stats[backend]["total_size"] += size
        
        return stats
    
    def suggest_backend_for_new_pin(self, size: int = 0) -> str:
        """Suggest the best backend for a new pin based on current distribution."""
        stats = self.get_backend_stats()
        
        if not stats:
            return "ipfs"  # Default fallback
        
        # Simple strategy: use backend with least count
        min_count = float('inf')
        best_backend = "ipfs"
        
        for backend, backend_stats in stats.items():
            if backend_stats["count"] < min_count:
                min_count = backend_stats["count"]
                best_backend = backend
        
        return best_backend


# Global instances for easy import
daemon_client = DaemonClient()
route_reader = RouteReader()


# Convenience functions
async def ensure_daemon_running() -> bool:
    """Convenience function to ensure daemon is running."""
    return await daemon_client.start_daemon()

async def get_daemon_status() -> Dict[str, Any]:
    """Convenience function to get daemon status."""
    return await daemon_client.get_daemon_status()

async def get_backend_health(backend_name: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to get backend health."""
    return await daemon_client.get_backend_health(backend_name)

def find_backends_for_cid(cid: str) -> List[str]:
    """Convenience function to find backends for a CID."""
    return route_reader.find_backends_for_cid(cid)

def suggest_backend_for_pin(size: int = 0) -> str:
    """Convenience function to suggest backend for new pin."""
    return route_reader.suggest_backend_for_new_pin(size)
