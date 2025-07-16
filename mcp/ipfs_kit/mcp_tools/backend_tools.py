"""
Backend tools for MCP server.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BackendTools:
    """Tools for backend operations."""
    
    def __init__(self, backend_monitor):
        self.backend_monitor = backend_monitor
    
    async def get_backend_status(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Get backend status."""
        if backend_name:
            return await self.backend_monitor.check_backend_health(backend_name)
        else:
            return await self.backend_monitor.check_all_backends()
    
    async def get_backend_detailed(self, backend_name: str) -> Dict[str, Any]:
        """Get detailed backend information."""
        try:
            backend_info = await self.backend_monitor.check_backend_health(backend_name)
            if backend_name in self.backend_monitor.backends:
                client = self.backend_monitor.backends[backend_name]
                detailed_info = await client.get_status()
                backend_info["detailed"] = detailed_info
            return backend_info
        except Exception as e:
            return {"error": str(e)}
    
    async def restart_backend(self, backend_name: str) -> Dict[str, Any]:
        """Restart a backend."""
        try:
            result = await self.backend_monitor.restart_backend(backend_name)
            return {"success": result, "message": f"Backend {backend_name} restart initiated"}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get backend configuration."""
        try:
            if backend_name in self.backend_monitor.backends:
                client = self.backend_monitor.backends[backend_name]
                config = await client.get_config()
                return {"backend": backend_name, "config": config}
            else:
                return {"error": f"Backend {backend_name} not found"}
        except Exception as e:
            return {"error": str(e)}
    
    async def set_backend_config(self, backend_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Set backend configuration."""
        try:
            if backend_name in self.backend_monitor.backends:
                client = self.backend_monitor.backends[backend_name]
                success = await client.set_config(config)
                return {"success": success, "message": f"Configuration updated for {backend_name}"}
            else:
                return {"error": f"Backend {backend_name} not found"}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_metrics_history(self, backend_name: str, limit: int = 10) -> Dict[str, Any]:
        """Get metrics history for a backend."""
        try:
            history = self.backend_monitor.get_metrics_history(backend_name, limit)
            return {"backend": backend_name, "metrics": history}
        except Exception as e:
            return {"error": str(e)}
