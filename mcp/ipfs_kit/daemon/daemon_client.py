"""
IPFS Kit Daemon Client Library.

Lightweight client library for communicating with the IPFS Kit daemon.
Used by MCP servers and CLI tools to make requests to the daemon.
"""

import json
import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

class IPFSKitDaemonClient:
    """
    Client for communicating with the IPFS Kit daemon.
    
    Provides high-level methods for all daemon operations:
    - Health monitoring
    - Pin management  
    - Backend control
    - Configuration
    """
    
    def __init__(self, 
                 daemon_host: str = "127.0.0.1",
                 daemon_port: int = 9999,
                 timeout: int = 30):
        self.daemon_host = daemon_host
        self.daemon_port = daemon_port
        self.base_url = f"http://{daemon_host}:{daemon_port}"
        self.timeout = timeout
        
        logger.info(f"🔗 IPFS Kit daemon client initialized: {self.base_url}")
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request to the daemon."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, **kwargs)
                elif method.upper() == "POST":
                    response = await client.post(url, **kwargs)
                elif method.upper() == "PUT":
                    response = await client.put(url, **kwargs)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                return response.json()
                
        except httpx.ConnectError:
            logger.error(f"❌ Cannot connect to daemon at {self.base_url}")
            return {"success": False, "error": "Daemon not reachable"}
        except httpx.TimeoutException:
            logger.error(f"⏰ Timeout connecting to daemon at {self.base_url}")
            return {"success": False, "error": "Daemon timeout"}
        except Exception as e:
            logger.error(f"❌ Error making request to daemon: {e}")
            return {"success": False, "error": str(e)}
    
    # Health monitoring methods
    async def get_health(self) -> Dict[str, Any]:
        """Get comprehensive daemon health status."""
        return await self._make_request("GET", "/health")
    
    async def get_backend_health(self) -> Dict[str, Any]:
        """Get backend-specific health status."""
        return await self._make_request("GET", "/health/backends")
    
    async def get_filesystem_health(self) -> Dict[str, Any]:
        """Get filesystem status from parquet files."""
        return await self._make_request("GET", "/health/filesystem")
    
    # Pin management methods
    async def list_pins(self) -> Dict[str, Any]:
        """List all pins with metadata."""
        return await self._make_request("GET", "/pins")
    
    async def add_pin(self, cid: str) -> Dict[str, Any]:
        """Add a pin and update index."""
        return await self._make_request("POST", f"/pins/{cid}")
    
    async def remove_pin(self, cid: str) -> Dict[str, Any]:
        """Remove a pin and update index."""
        return await self._make_request("DELETE", f"/pins/{cid}")
    
    # Backend management methods
    async def start_backend(self, backend_name: str) -> Dict[str, Any]:
        """Start a specific backend service."""
        return await self._make_request("POST", f"/backends/{backend_name}/start")
    
    async def stop_backend(self, backend_name: str) -> Dict[str, Any]:
        """Stop a specific backend service."""
        return await self._make_request("POST", f"/backends/{backend_name}/stop")
    
    async def get_backend_logs(self, backend_name: str, lines: int = 100) -> Dict[str, Any]:
        """Get logs for a specific backend."""
        return await self._make_request("GET", f"/backends/{backend_name}/logs", params={"lines": lines})
    
    # Configuration methods
    async def get_config(self) -> Dict[str, Any]:
        """Get daemon configuration."""
        return await self._make_request("GET", "/config")
    
    async def update_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update daemon configuration."""
        return await self._make_request("PUT", "/config", json=config_data)
    
    # Status methods
    async def get_daemon_status(self) -> Dict[str, Any]:
        """Get overall daemon status."""
        return await self._make_request("GET", "/status")
    
    async def is_daemon_running(self) -> bool:
        """Check if daemon is running and responsive."""
        try:
            status = await self.get_daemon_status()
            return status.get("running", False)
        except Exception:
            return False
    
    # High-level convenience methods
    async def wait_for_daemon(self, max_wait: int = 30) -> bool:
        """Wait for daemon to become available."""
        logger.info(f"⏳ Waiting for daemon at {self.base_url}...")
        
        for attempt in range(max_wait):
            if await self.is_daemon_running():
                logger.info("✓ Daemon is running")
                return True
            
            logger.debug(f"Attempt {attempt + 1}/{max_wait}: daemon not ready")
            await asyncio.sleep(1)
        
        logger.error(f"❌ Daemon not available after {max_wait} seconds")
        return False
    
    async def ensure_healthy_backends(self, required_backends: List[str] = None) -> Dict[str, Any]:
        """Ensure required backends are healthy."""
        if not required_backends:
            required_backends = ["ipfs"]
        
        logger.info(f"🏥 Checking health of backends: {required_backends}")
        
        health_status = await self.get_backend_health()
        if not health_status.get("success", False):
            return {"success": False, "error": "Could not get backend health"}
        
        backends = health_status.get("backends", {})
        unhealthy_backends = []
        
        for backend_name in required_backends:
            backend = backends.get(backend_name, {})
            if backend.get("health") != "healthy":
                unhealthy_backends.append(backend_name)
        
        if unhealthy_backends:
            logger.warning(f"⚠️ Unhealthy backends: {unhealthy_backends}")
            return {
                "success": False, 
                "unhealthy_backends": unhealthy_backends,
                "all_backends": backends
            }
        else:
            logger.info("✓ All required backends are healthy")
            return {"success": True, "backends": backends}
    
    async def get_pin_routing_info(self, cid: str) -> Dict[str, Any]:
        """Get routing information for a specific CID."""
        pins_data = await self.list_pins()
        
        if not pins_data.get("pins"):
            return {"success": False, "error": "No pin data available"}
        
        # Look for the CID in pin data
        for pin in pins_data["pins"]:
            if pin.get("cid") == cid:
                return {
                    "success": True,
                    "cid": cid,
                    "pin_info": pin,
                    "routing": {
                        "primary_backend": pin.get("primary_tier", "ipfs"),
                        "storage_tiers": pin.get("storage_tiers", ["ipfs"]),
                        "replication_factor": pin.get("replication_factor", 1)
                    }
                }
        
        return {"success": False, "error": f"CID {cid} not found in pin index"}


class DaemonAwareComponent:
    """
    Base class for components that need to communicate with the daemon.
    
    Provides common functionality for MCP servers, CLI tools, etc.
    """
    
    def __init__(self, daemon_client: IPFSKitDaemonClient = None):
        if daemon_client:
            self.daemon_client = daemon_client
        else:
            self.daemon_client = IPFSKitDaemonClient()
        
        self.daemon_available = False
    
    async def ensure_daemon_connection(self) -> bool:
        """Ensure connection to daemon is available."""
        if not self.daemon_available:
            self.daemon_available = await self.daemon_client.wait_for_daemon()
        
        return self.daemon_available
    
    async def get_filesystem_status(self) -> Dict[str, Any]:
        """Get filesystem status via daemon."""
        if not await self.ensure_daemon_connection():
            return {"success": False, "error": "Daemon not available"}
        
        return await self.daemon_client.get_filesystem_health()
    
    async def route_pin_request(self, cid: str, operation: str) -> Dict[str, Any]:
        """Route a pin request via daemon with proper backend selection."""
        if not await self.ensure_daemon_connection():
            return {"success": False, "error": "Daemon not available"}
        
        # Get routing info first
        routing_info = await self.daemon_client.get_pin_routing_info(cid)
        
        if operation == "add":
            result = await self.daemon_client.add_pin(cid)
        elif operation == "remove":
            result = await self.daemon_client.remove_pin(cid)
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}
        
        # Add routing info to result
        if routing_info.get("success"):
            result["routing_info"] = routing_info["routing"]
        
        return result


# Utility functions for daemon integration
async def check_daemon_health(daemon_host: str = "127.0.0.1", daemon_port: int = 9999) -> Dict[str, Any]:
    """Quick health check for daemon."""
    client = IPFSKitDaemonClient(daemon_host, daemon_port)
    return await client.get_health()

async def ensure_daemon_running(daemon_host: str = "127.0.0.1", daemon_port: int = 9999) -> bool:
    """Ensure daemon is running before proceeding."""
    client = IPFSKitDaemonClient(daemon_host, daemon_port)
    return await client.wait_for_daemon()

# Export key classes
__all__ = [
    "IPFSKitDaemonClient",
    "DaemonAwareComponent", 
    "check_daemon_health",
    "ensure_daemon_running"
]
