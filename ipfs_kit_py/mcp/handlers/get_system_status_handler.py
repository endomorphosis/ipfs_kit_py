"""
MCP RPC Handler for get_system_status

Auto-generated comprehensive handler for bridging legacy function to new architecture.
Category: system
Priority: 1 (Core)
Complexity: 1 (Simple)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class GetSystemStatusHandler:
    """Handler for get_system_status MCP RPC calls."""
    
    def __init__(self, ipfs_kit_dir: Path):
        self.ipfs_kit_dir = ipfs_kit_dir
        self.category = "system"
        self.priority = 1
        self.complexity = 1
    
    async def handle(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_system_status RPC call.
        
        Legacy function: get_system_status
        New implementation: system_health_monitor
        Category: system
        """
        try:
            # Execute the new bucket-centric implementation
            result = await self._execute_system_health_monitor(params)
            
            return {
                "success": True,
                "method": "get_system_status",
                "category": "system",
                "data": result,
                "source": "comprehensive_bridge",
                "priority": 1,
                "complexity": 1
            }
            
        except Exception as e:
            logger.error(f"Error in get_system_status handler: {e}")
            return {
                "success": False,
                "error": str(e),
                "method": "get_system_status",
                "category": "system"
            }
    
    async def _execute_system_health_monitor(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the new implementation for get_system_status."""
        from .state_file_utils import load_json_file, load_json_glob
        
        try:
            # Load system health and services
            health_file = load_json_file(self.ipfs_kit_dir / "system" / "health.json")
            services = load_json_glob(self.ipfs_kit_dir, "services/*.json")
            
            # Extract service data
            service_data = [item.get("data", {}) for item in services if item.get("data")]
            
            # Aggregate service statuses
            running_services = sum(1 for svc in service_data if svc.get("running"))
            total_services = len(service_data)
            
            # Build status report
            status_report = {
                "timestamp": health_file.get("timestamp") if health_file else None,
                "uptime": health_file.get("uptime") if health_file else None,
                "cpu_usage": health_file.get("cpu_usage") if health_file else None,
                "memory_usage": health_file.get("memory_usage") if health_file else None
            }
            
            return {
                "message": "System status monitor",
                "system_operational": total_services > 0 and running_services == total_services,
                "running_services": running_services,
                "total_services": total_services,
                "uptime_info": status_report,
                "services": [{"name": svc.get("name"), "running": svc.get("running")} for svc in service_data],
                "sources": [item.get("path") for item in services]
            }
            
        except Exception as e:
            logger.error(f"Error checking system status: {e}")
            return {
                "message": "System status monitor (empty state)",
                "system_operational": False,
                "running_services": 0,
                "total_services": 0,
                "uptime_info": {},
                "services": [],
                "sources": [],
                "error": str(e)
            }
