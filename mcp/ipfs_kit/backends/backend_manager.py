"""
Backend manager for coordinating backend operations.
"""

import logging
from typing import Dict, Any, List
from .health_monitor import BackendHealthMonitor

logger = logging.getLogger(__name__)


class BackendManager:
    """Manages backend operations and coordination."""
    
    def __init__(self, health_monitor: BackendHealthMonitor):
        self.health_monitor = health_monitor
        self.backends = health_monitor.backends
    
    async def get_all_backend_info(self) -> Dict[str, Any]:
        """Get information about all backends."""
        return await self.health_monitor.check_all_backends()
    
    async def get_backend_info(self, backend_name: str) -> Dict[str, Any]:
        """Get information about a specific backend."""
        return await self.health_monitor.check_backend_health(backend_name)
    
    def get_backend_names(self) -> List[str]:
        """Get list of all backend names."""
        return list(self.backends.keys())
    
    def list_backends(self) -> List[str]:
        """Get list of all backend names (alias for get_backend_names for compatibility)."""
        return self.get_backend_names()

    def get_backend(self, backend_name: str) -> Any:
        """Get a specific backend object by name."""
        return self.backends.get(backend_name)
    
    async def restart_all_backends(self) -> Dict[str, bool]:
        """Restart all backends."""
        results = {}
        for backend_name in self.backends.keys():
            try:
                results[backend_name] = await self.health_monitor.restart_backend(backend_name)
            except Exception as e:
                logger.error(f"Failed to restart {backend_name}: {e}")
                results[backend_name] = False
        return results
    
    async def get_backend_logs(self, backend_name: str, limit: int = 100) -> List[str]:
        """Get logs for a specific backend."""
        return await self.health_monitor.get_backend_logs(backend_name)
    
    def get_all_backend_logs(self, limit: int = 50) -> Dict[str, List]:
        """Get logs for all backends."""
        if hasattr(self.health_monitor, 'log_manager'):
            return self.health_monitor.log_manager.get_all_backend_logs(limit)
        return {}
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get logging statistics."""
        if hasattr(self.health_monitor, 'log_manager'):
            return self.health_monitor.log_manager.get_log_statistics()
        return {"error": "Log manager not available"}
    
    def clear_backend_logs(self, backend_name: str) -> bool:
        """Clear logs for a specific backend."""
        try:
            if hasattr(self.health_monitor, 'log_manager'):
                self.health_monitor.log_manager.clear_backend_logs(backend_name)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to clear logs for {backend_name}: {e}")
            return False
