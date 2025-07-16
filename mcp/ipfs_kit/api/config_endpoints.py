"""
Configuration endpoints for API routes.
"""

import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ConfigEndpoints:
    """Configuration-related API endpoints."""
    
    def __init__(self, backend_monitor):
        self.backend_monitor = backend_monitor
    
    async def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get backend configuration."""
        try:
            return await self.backend_monitor.get_backend_config(backend_name)
        except Exception as e:
            logger.error(f"Error getting config for {backend_name}: {e}")
            return {"error": str(e)}
    
    async def set_backend_config(self, backend_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Set backend configuration."""
        try:
            return await self.backend_monitor.set_backend_config(backend_name, config)
        except Exception as e:
            logger.error(f"Error setting config for {backend_name}: {e}")
            return {"error": str(e)}
    
    async def get_package_config(self) -> Dict[str, Any]:
        """Get package configuration."""
        try:
            return self.backend_monitor.get_package_config()
        except Exception as e:
            logger.error(f"Error getting package config: {e}")
            return {"error": str(e)}
    
    async def set_package_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Set package configuration."""
        try:
            return self.backend_monitor.set_package_config(config)
        except Exception as e:
            logger.error(f"Error setting package config: {e}")
            return {"error": str(e)}
    
    async def export_config(self) -> Dict[str, Any]:
        """Export all configuration."""
        try:
            # Get package config
            package_config = self.backend_monitor.get_package_config()
            
            # Get all backend configs
            backend_configs = {}
            for backend_name in self.backend_monitor.backends.keys():
                config_result = await self.backend_monitor.get_backend_config(backend_name)
                if "error" not in config_result:
                    backend_configs[backend_name] = config_result.get("config", {})
            
            return {
                "package_config": package_config,
                "backend_configs": backend_configs,
                "export_timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error exporting config: {e}")
            return {"error": str(e)}
