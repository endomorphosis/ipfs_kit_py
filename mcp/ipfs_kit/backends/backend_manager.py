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
