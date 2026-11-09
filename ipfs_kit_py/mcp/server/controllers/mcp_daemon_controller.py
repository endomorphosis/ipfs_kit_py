#!/usr/bin/env python3
"""
MCP Daemon Controller - Mirrors CLI daemon commands

This controller provides MCP tools that mirror the CLI daemon commands,
allowing MCP clients to manage daemon services with the same functionality
as the command line interface.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..models.mcp_metadata_manager import MCPMetadataManager
from ..services.mcp_daemon_service import MCPDaemonService

logger = logging.getLogger(__name__)


class MCPDaemonController:
    """
    MCP Daemon Controller that mirrors CLI daemon commands
    
    Provides MCP tools for:
    - daemon status (mirrors 'ipfs-kit daemon status')
    - daemon intelligent status (mirrors 'ipfs-kit daemon intelligent status')
    - daemon intelligent insights (mirrors 'ipfs-kit daemon intelligent insights')
    - daemon start (mirrors 'ipfs-kit daemon start')
    - daemon stop (mirrors 'ipfs-kit daemon stop')
    """
    
    def __init__(self, metadata_manager: MCPMetadataManager, daemon_service: MCPDaemonService):
        """Initialize the daemon controller."""
        self.metadata_manager = metadata_manager
        self.daemon_service = daemon_service
        logger.info("MCP Daemon Controller initialized")
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle daemon tool calls by routing to appropriate methods."""
        try:
            if tool_name == "daemon_status":
                return await self.get_daemon_status(arguments)
            elif tool_name == "daemon_intelligent_status":
                return await self.get_intelligent_status(arguments)
            elif tool_name == "daemon_intelligent_insights":
                return await self.get_intelligent_insights(arguments)
            elif tool_name == "daemon_start":
                return await self.start_daemon(arguments)
            elif tool_name == "daemon_stop":
                return await self.stop_daemon(arguments)
            else:
                return {"error": f"Unknown daemon tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Error handling daemon tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def get_daemon_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get daemon status (mirrors 'ipfs-kit daemon status')
        
        Arguments:
        - detailed: Show detailed status
        - json: Output in JSON format (always true for MCP)
        """
        detailed = arguments.get("detailed", False)
        
        try:
            # Get basic daemon status
            daemon_status = await self.daemon_service.get_daemon_status()
            
            if detailed:
                # Get additional metadata summary
                metadata_summary = await self.metadata_manager.get_metadata_summary()
                
                return {
                    "daemon_status": {
                        "is_running": daemon_status.is_running,
                        "pid": daemon_status.pid,
                        "role": daemon_status.role,
                        "start_time": daemon_status.start_time.isoformat() if daemon_status.start_time else None,
                        "last_heartbeat": daemon_status.last_heartbeat.isoformat() if daemon_status.last_heartbeat else None,
                        "port": daemon_status.port,
                        "services": daemon_status.services,
                        "error_message": daemon_status.error_message
                    },
                    "metadata_summary": metadata_summary,
                    "detailed": True
                }
            else:
                return {
                    "is_running": daemon_status.is_running,
                    "pid": daemon_status.pid,
                    "role": daemon_status.role,
                    "status": "healthy" if daemon_status.is_running else "stopped"
                }
                
        except Exception as e:
            logger.error(f"Error getting daemon status: {e}")
            return {"error": str(e)}
    
    async def get_intelligent_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get intelligent daemon status (mirrors 'ipfs-kit daemon intelligent status')
        
        Arguments:
        - json: Output in JSON format (always true for MCP)
        """
        try:
            # Get intelligent daemon status from daemon service
            status = await self.daemon_service.get_intelligent_status()
            
            # Add MCP-specific metadata
            status["mcp_context"] = {
                "tool": "daemon_intelligent_status",
                "timestamp": status.get("timestamp"),
                "source": "mcp_daemon_controller"
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting intelligent daemon status: {e}")
            return {"error": str(e)}
    
    async def get_intelligent_insights(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get intelligent daemon insights (mirrors 'ipfs-kit daemon intelligent insights')
        
        Arguments:
        - json: Output in JSON format (always true for MCP)
        """
        try:
            # Get intelligent daemon insights from daemon service
            insights = await self.daemon_service.get_intelligent_insights()
            
            # Add MCP-specific metadata
            insights["mcp_context"] = {
                "tool": "daemon_intelligent_insights",
                "timestamp": insights.get("timestamp"),
                "source": "mcp_daemon_controller"
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting intelligent daemon insights: {e}")
            return {"error": str(e)}
    
    async def start_daemon(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start daemon services (mirrors 'ipfs-kit daemon start')
        
        Arguments:
        - service: Specific service to start
        - background: Run in background (always true for MCP)
        """
        service = arguments.get("service")
        
        try:
            if self.daemon_service.is_running:
                return {
                    "action": "start_daemon",
                    "status": "already_running",
                    "message": "Daemon service is already running",
                    "uptime_seconds": (await self.daemon_service.get_status()).uptime_seconds
                }
            
            # Start the daemon service
            await self.daemon_service.start()
            
            # Get status to confirm startup
            status = await self.daemon_service.get_status()
            
            return {
                "action": "start_daemon",
                "status": "started",
                "message": "Daemon service started successfully",
                "is_running": status.is_running,
                "total_backends": status.total_backends
            }
            
        except Exception as e:
            logger.error(f"Error starting daemon: {e}")
            return {
                "action": "start_daemon",
                "status": "failed",
                "error": str(e)
            }
    
    async def stop_daemon(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stop daemon services (mirrors 'ipfs-kit daemon stop')
        
        Arguments:
        - service: Specific service to stop
        """
        service = arguments.get("service")
        
        try:
            if not self.daemon_service.is_running:
                return {
                    "action": "stop_daemon",
                    "status": "not_running",
                    "message": "Daemon service is not running"
                }
            
            # Get uptime before stopping
            status = await self.daemon_service.get_status()
            uptime = status.uptime_seconds
            
            # Stop the daemon service
            await self.daemon_service.stop()
            
            return {
                "action": "stop_daemon",
                "status": "stopped",
                "message": "Daemon service stopped successfully",
                "final_uptime_seconds": uptime
            }
            
        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
            return {
                "action": "stop_daemon",
                "status": "failed",
                "error": str(e)
            }
