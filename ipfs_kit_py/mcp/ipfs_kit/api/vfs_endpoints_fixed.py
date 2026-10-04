"""
VFS API endpoints for comprehensive VFS analytics and observability.
"""

import anyio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class VFSEndpoints:
    """VFS API endpoints handler with timeout protection."""
    
    def __init__(self, backend_monitor):
        self.backend_monitor = backend_monitor

    async def get_vfs_analytics(self) -> Dict[str, Any]:
        """Get comprehensive VFS analytics with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            with anyio.fail_after(10):  # 10 second timeout
                if hasattr(self.backend_monitor, 'vfs_observer') and self.backend_monitor.vfs_observer:
                    vfs_stats = await self.backend_monitor.vfs_observer.get_vfs_statistics()
                    return {"success": True, "data": vfs_stats}
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except TimeoutError:
            logger.error("VFS analytics check timed out")
            return {"success": False, "error": "VFS analytics check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS analytics: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_health(self) -> Dict[str, Any]:
        """Get VFS health status with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            with anyio.fail_after(10):  # 10 second timeout
                if hasattr(self.backend_monitor, 'vfs_observer') and self.backend_monitor.vfs_observer:
                    # Get comprehensive health information
                    vfs_stats = await self.backend_monitor.vfs_observer.get_vfs_statistics()
                    
                    # Extract health indicators
                    health_data = {
                        "status": "healthy",
                        "filesystem_status": vfs_stats.get("filesystem_status", {}),
                        "resource_utilization": vfs_stats.get("resource_utilization", {}),
                        "cache_performance": vfs_stats.get("cache_performance", {}),
                        "timestamp": vfs_stats.get("timestamp")
                    }
                    
                    # Determine overall health status
                    resource_util = health_data.get("resource_utilization", {})
                    memory_usage = resource_util.get("memory_usage", {})
                    if memory_usage.get("system_used_percent", 0) > 90:
                        health_data["status"] = "warning"
                        health_data["warnings"] = ["High memory usage detected"]
                    
                    return {"success": True, "health": health_data}
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except TimeoutError:
            logger.error("VFS health check timed out")
            return {"success": False, "error": "VFS health check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS health: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_performance(self) -> Dict[str, Any]:
        """Get detailed VFS performance metrics and analysis with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            with anyio.fail_after(8):  # 8 second timeout
                if hasattr(self.backend_monitor, 'vfs_observer') and self.backend_monitor.vfs_observer:
                    vfs_stats = await self.backend_monitor.vfs_observer.get_vfs_statistics()
                    
                    return {
                        "success": True, 
                        "performance_data": vfs_stats,
                        "timestamp": vfs_stats.get("timestamp")
                    }
                else:
                    return {"success": False, "error": "VFS Observer not available"}
                    
        except TimeoutError:
            logger.error("VFS performance check timed out")
            return {"success": False, "error": "VFS performance check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS performance: {e}")
            return {"success": False, "error": str(e)}

    async def get_vfs_cache(self) -> Dict[str, Any]:
        """Get VFS cache information with timeout protection."""
        try:
            # Add timeout to prevent hanging requests
            with anyio.fail_after(5):  # 5 second timeout
                if hasattr(self.backend_monitor, 'vfs_observer') and self.backend_monitor.vfs_observer:
                    return await self.backend_monitor.vfs_observer.get_cache_statistics()
                else:
                    logger.warning("VFS observer not available, returning error for get_vfs_cache")
                    return {"error": "VFS observer not available"}
                    
        except TimeoutError:
            logger.error("VFS cache check timed out")
            return {"error": "VFS cache check timed out"}
        except Exception as e:
            logger.error(f"Error getting VFS cache: {e}", exc_info=True)
            return {"error": str(e)}
