"""
MCP tool manager for IPFS Kit.
"""

from typing import List, Dict, Any, Optional
import logging
import traceback

from .backend_tools import BackendTools
from .system_tools import SystemTools
from .vfs_tools import VFSTools

logger = logging.getLogger(__name__)


class SimplifiedMCPTool:
    """Simplified MCP tool representation."""
    
    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.input_schema = input_schema


class MCPToolManager:
    """Manages MCP tools for the IPFS Kit server."""
    
    def __init__(self, backend_monitor):
        self.backend_monitor = backend_monitor
        
        # Initialize tool handlers
        self.backend_tools = BackendTools(backend_monitor)
        self.system_tools = SystemTools(backend_monitor)
        self.vfs_tools = VFSTools(backend_monitor)
        
        # Create tool registry
        self.tools = self._create_tools()
    
    def _create_tools(self) -> List[SimplifiedMCPTool]:
        """Create the MCP tools registry."""
        
        tools = []
        
        # System tools
        tools.extend([
            SimplifiedMCPTool(
                name="system_health",
                description="Get comprehensive system health status including all backend monitoring",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="get_development_insights",
                description="Get insights and recommendations for development based on backend status",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            )
        ])
        
        # Backend tools
        tools.extend([
            SimplifiedMCPTool(
                name="get_backend_status",
                description="Get comprehensive backend status and monitoring data for all filesystem backends",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Specific backend to check (optional)",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus", "storacha", "synapse", "s3", "huggingface", "parquet"]
                        }
                    }
                }
            ),
            SimplifiedMCPTool(
                name="get_backend_detailed",
                description="Get detailed information about a specific backend",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend name to get detailed info for",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus", "storacha", "synapse", "s3", "huggingface", "parquet"]
                        }
                    },
                    "required": ["backend"]
                }
            ),
            SimplifiedMCPTool(
                name="restart_backend",
                description="Attempt to restart a specific backend",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend to restart",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus"]
                        }
                    },
                    "required": ["backend"]
                }
            ),
            SimplifiedMCPTool(
                name="get_backend_config",
                description="Get configuration for a specific backend",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend name to get config for",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus", "storacha", "synapse", "s3", "huggingface", "parquet"]
                        }
                    },
                    "required": ["backend"]
                }
            ),
            SimplifiedMCPTool(
                name="set_backend_config",
                description="Set configuration for a specific backend",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend name to set config for",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus", "storacha", "synapse", "s3", "huggingface", "parquet"]
                        },
                        "config": {
                            "type": "object",
                            "description": "Configuration object to set"
                        }
                    },
                    "required": ["backend", "config"]
                }
            )
        ])
        
        # VFS tools
        tools.extend([
            SimplifiedMCPTool(
                name="get_vfs_statistics",
                description="Get VFS statistics and metrics",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="get_vfs_cache",
                description="Get VFS cache information",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="get_vfs_vector_index",
                description="Get VFS vector index information",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="get_vfs_knowledge_base",
                description="Get VFS knowledge base information",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            )
        ])
        
        # Metrics and monitoring tools
        tools.extend([
            SimplifiedMCPTool(
                name="get_metrics_history",
                description="Get historical metrics for backends",
                input_schema={
                    "type": "object", 
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend name to get metrics for"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of recent metrics to return",
                            "default": 10
                        }
                    }
                }
            )
        ])
        
        return tools
    
    async def handle_tool_request(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tool requests."""
        
        try:
            # System tools
            if tool_name == "system_health":
                return await self.system_tools.get_system_health()
            
            elif tool_name == "get_development_insights":
                return await self.system_tools.get_development_insights()
            
            # Backend tools
            elif tool_name == "get_backend_status":
                backend = arguments.get("backend")
                return await self.backend_tools.get_backend_status(backend)
            
            elif tool_name == "get_backend_detailed":
                backend = arguments.get("backend")
                if not backend:
                    return {"error": "Backend name is required"}
                return await self.backend_tools.get_backend_detailed(backend)
            
            elif tool_name == "restart_backend":
                backend = arguments.get("backend")
                if not backend:
                    return {"error": "Backend name is required"}
                return await self.backend_tools.restart_backend(backend)
            
            elif tool_name == "get_backend_config":
                backend = arguments.get("backend")
                if not backend:
                    return {"error": "Backend name is required"}
                return await self.backend_tools.get_backend_config(backend)
            
            elif tool_name == "set_backend_config":
                backend = arguments.get("backend")
                config = arguments.get("config")
                if not backend or not config:
                    return {"error": "Backend name and config are required"}
                return await self.backend_tools.set_backend_config(backend, config)
            
            # VFS tools
            elif tool_name == "get_vfs_statistics":
                return await self.vfs_tools.get_vfs_statistics()
            
            elif tool_name == "get_vfs_cache":
                return await self.vfs_tools.get_vfs_cache()
            
            elif tool_name == "get_vfs_vector_index":
                return await self.vfs_tools.get_vfs_vector_index()
            
            elif tool_name == "get_vfs_knowledge_base":
                return await self.vfs_tools.get_vfs_knowledge_base()
            
            # Metrics tools
            elif tool_name == "get_metrics_history":
                backend = arguments.get("backend")
                limit = arguments.get("limit", 10)
                return await self.backend_tools.get_metrics_history(backend, limit)
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Error handling MCP request {tool_name}: {e}")
            return {"error": str(e), "traceback": traceback.format_exc()}
    
    def get_tools(self) -> List[SimplifiedMCPTool]:
        """Get all available MCP tools."""
        return self.tools
