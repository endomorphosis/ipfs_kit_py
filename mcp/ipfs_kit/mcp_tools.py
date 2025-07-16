"""
MCP Tool Manager for IPFS Kit.

This module centralizes all MCP tools, using daemon, VFS, and GraphRAG managers.
"""

import logging
import asyncio
from typing import Dict, Any, List

from .daemon import DaemonManager
from .vfs import VFSManager
from .graphrag import GraphRAGSearchEngine

logger = logging.getLogger(__name__)

class MCPToolManager:
    """Manages and executes all available MCP tools."""

    def __init__(self):
        logger.info("Initializing MCPToolManager...")
        self.daemon_manager = DaemonManager()
        self.vfs_manager = VFSManager()
        self.graphrag_engine = GraphRAGSearchEngine()
        self._tools = self._define_tools()
        logger.info("✓ MCPToolManager initialized.")

    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define all available MCP tools."""
        tools = {
            # Daemon Tools
            "daemon_status": {
                "description": "Get the status of the IPFS daemon.",
                "handler": self.daemon_manager.get_status,
                "parameters": []
            },
            "ipfs_command": {
                "description": "Execute a raw IPFS command.",
                "handler": self.daemon_manager.execute_ipfs_operation,
                "parameters": [
                    {"name": "operation", "type": "string", "required": True},
                ]
            },
            # VFS Tools
            "vfs_operation": {
                "description": "Execute a VFS operation.",
                "handler": self.vfs_manager.execute_vfs_operation,
                "parameters": [
                    {"name": "operation", "type": "string", "required": True},
                ]
            },
            # GraphRAG Tools
            "index_content": {
                "description": "Index content for search.",
                "handler": self.graphrag_engine.index_content,
                "parameters": [
                    {"name": "cid", "type": "string", "required": True},
                    {"name": "path", "type": "string", "required": True},
                    {"name": "content", "type": "string", "required": True},
                ]
            },
            "search": {
                "description": "Search indexed content.",
                "handler": self.graphrag_engine.search,
                "parameters": [
                    {"name": "query", "type": "string", "required": True},
                    {"name": "search_type", "type": "string", "required": False, "default": "hybrid"},
                ]
            },
        }
        return tools

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get a list of available tools for MCP."""
        tool_list = []
        for name, tool_info in self._tools.items():
            tool_list.append({
                "name": name,
                "description": tool_info["description"],
                "parameters": tool_info["parameters"]
            })
        return tool_list

    async def handle_tool_request(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request to call an MCP tool."""
        if tool_name not in self._tools:
            return {"success": False, "error": f"Tool '{tool_name}' not found."}

        handler = self._tools[tool_name]["handler"]
        try:
            # This assumes handlers might be async or sync.
            # A better implementation would be consistent.
            if asyncio.iscoroutinefunction(handler):
                return await handler(**arguments)
            else:
                return handler(**arguments)
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}")
            return {"success": False, "error": str(e)}

    def cleanup(self):
        """Cleanup all managed components."""
        logger.info("Cleaning up MCPToolManager...")
        if hasattr(self, 'daemon_manager') and self.daemon_manager:
            self.daemon_manager.cleanup()
        if hasattr(self, 'vfs_manager') and self.vfs_manager:
            self.vfs_manager.cleanup()
        if hasattr(self, 'graphrag_engine') and self.graphrag_engine:
            self.graphrag_engine.cleanup()
        logger.info("✓ MCPToolManager cleaned up.")
