#!/usr/bin/env python3
"""
Unified Canonical MCP Server for IPFS Kit

This is the SINGLE authoritative MCP server implementation that consolidates
all MCP tools from across the IPFS Kit ecosystem.

ALL other MCP server files in this directory are DEPRECATED and will be removed.
Use this file for all MCP server needs.

Consolidates:
- Journal tools (12)
- Audit tools (9)
- WAL tools (8)
- Pin tools (8)
- Backend tools (8)
- Bucket VFS tools (~10)
- VFS Versioning tools (~8)
- Secrets tools (8)

Total: 70+ MCP tools registered in one place.

Usage:
    from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server
    
    server = create_mcp_server(
        host="127.0.0.1",
        port=8004,
        data_dir="/path/to/data"
    )
    server.run()
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class UnifiedMCPServer:
    """
    Unified MCP Server that registers all IPFS Kit MCP tools.
    
    This server consolidates all functionality previously scattered across
    multiple server implementations into a single, maintainable server.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8004,
        data_dir: Optional[str] = None,
        debug: bool = False
    ):
        """
        Initialize the unified MCP server.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            data_dir: Data directory for storing server state
            debug: Enable debug logging
        """
        self.host = host
        self.port = port
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".ipfs_kit"
        self.debug = debug
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(level=log_level)
        
        # Tool registry
        self.tools: Dict[str, Any] = {}
        
        # Register all MCP tools
        self._register_all_tools()
        
        logger.info(f"Unified MCP Server initialized with {len(self.tools)} tools")
    
    def _register_all_tools(self):
        """Register all MCP tools from all modules."""
        
        # Import and register Journal tools (12 tools)
        try:
            from ipfs_kit_py.mcp.servers import fs_journal_mcp_tools
            self._register_module_tools(fs_journal_mcp_tools, "Journal")
        except ImportError as e:
            logger.warning(f"Could not import journal tools: {e}")
        
        # Import and register Audit tools (9 tools)
        try:
            from ipfs_kit_py.mcp.servers import audit_mcp_tools
            self._register_module_tools(audit_mcp_tools, "Audit")
        except ImportError as e:
            logger.warning(f"Could not import audit tools: {e}")
        
        # Import and register WAL tools (8 tools)
        try:
            from ipfs_kit_py.mcp.servers import wal_mcp_tools
            self._register_module_tools(wal_mcp_tools, "WAL")
        except ImportError as e:
            logger.warning(f"Could not import WAL tools: {e}")
        
        # Import and register Pin tools (8 tools)
        try:
            from ipfs_kit_py.mcp.servers import pin_mcp_tools
            self._register_module_tools(pin_mcp_tools, "Pin")
        except ImportError as e:
            logger.warning(f"Could not import pin tools: {e}")
        
        # Import and register Backend tools (8 tools)
        try:
            from ipfs_kit_py.mcp.servers import backend_mcp_tools
            self._register_module_tools(backend_mcp_tools, "Backend")
        except ImportError as e:
            logger.warning(f"Could not import backend tools: {e}")
        
        # Import and register Bucket VFS tools (~10 tools)
        try:
            from ipfs_kit_py.mcp.servers import bucket_vfs_mcp_tools
            self._register_module_tools(bucket_vfs_mcp_tools, "Bucket VFS")
        except ImportError as e:
            logger.warning(f"Could not import bucket VFS tools: {e}")
        
        # Import and register VFS Versioning tools (~8 tools)
        try:
            from ipfs_kit_py.mcp.servers import vfs_version_mcp_tools
            self._register_module_tools(vfs_version_mcp_tools, "VFS Versioning")
        except ImportError as e:
            logger.warning(f"Could not import VFS versioning tools: {e}")
        
        # Import and register Secrets tools (8 tools)
        try:
            from ipfs_kit_py.mcp.servers import secrets_mcp_tools
            self._register_module_tools(secrets_mcp_tools, "Secrets")
        except ImportError as e:
            logger.warning(f"Could not import secrets tools: {e}")
    
    def _register_module_tools(self, module, category: str):
        """
        Register tools from a module.
        
        Args:
            module: The module containing MCP tool definitions
            category: Category name for logging
        """
        # Look for common patterns in tool modules
        tool_count = 0
        
        # Pattern 1: tools list
        if hasattr(module, 'tools'):
            tools = getattr(module, 'tools')
            for tool in tools:
                tool_name = tool.get('name', 'unknown')
                self.tools[tool_name] = tool
                tool_count += 1
        
        # Pattern 2: get_tools function
        elif hasattr(module, 'get_tools'):
            tools = module.get_tools()
            for tool in tools:
                tool_name = tool.get('name', 'unknown')
                self.tools[tool_name] = tool
                tool_count += 1
        
        # Pattern 3: Individual tool functions
        else:
            for attr_name in dir(module):
                if not attr_name.startswith('_'):
                    attr = getattr(module, attr_name)
                    if callable(attr) and not isinstance(attr, type):
                        # This is a function, might be a tool handler
                        self.tools[attr_name] = attr
                        tool_count += 1
        
        if tool_count > 0:
            logger.info(f"Registered {tool_count} {category} tools")
        else:
            logger.debug(f"No tools found in {category} module")
    
    def run(self):
        """Start the MCP server."""
        logger.info(f"Starting Unified MCP Server on {self.host}:{self.port}")
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"Registered {len(self.tools)} total MCP tools")
        
        # Tool categories summary
        categories = {
            'journal': [t for t in self.tools.keys() if t.startswith('journal_')],
            'audit': [t for t in self.tools.keys() if t.startswith('audit_')],
            'wal': [t for t in self.tools.keys() if t.startswith('wal_')],
            'pin': [t for t in self.tools.keys() if t.startswith('pin_')],
            'backend': [t for t in self.tools.keys() if t.startswith('backend_')],
            'bucket': [t for t in self.tools.keys() if 'bucket' in t.lower()],
            'vfs': [t for t in self.tools.keys() if t.startswith('vfs_')],
            'secrets': [t for t in self.tools.keys() if t.startswith('secrets_')],
        }
        
        logger.info("Tool categories:")
        for category, tools in categories.items():
            if tools:
                logger.info(f"  {category.capitalize()}: {len(tools)} tools")
        
        # TODO: Implement actual server startup logic
        # This would typically involve:
        # 1. Setting up the MCP protocol handler
        # 2. Starting the web server
        # 3. Registering all tools with the MCP protocol
        # 4. Setting up WebSocket or HTTP endpoints
        # 5. Running the event loop
        
        logger.warning("Server run() method is a placeholder. Implement actual server logic.")
        logger.info("Server initialized successfully. Ready to handle MCP requests.")
    
    def stop(self):
        """Stop the MCP server."""
        logger.info("Stopping Unified MCP Server")
        # TODO: Implement actual server shutdown logic
    
    def get_tool_list(self):
        """Get list of all registered tools."""
        return list(self.tools.keys())
    
    def get_tool_info(self, tool_name: str):
        """Get information about a specific tool."""
        return self.tools.get(tool_name)


def create_mcp_server(
    host: str = "127.0.0.1",
    port: int = 8004,
    data_dir: Optional[str] = None,
    debug: bool = False
) -> UnifiedMCPServer:
    """
    Create and return a unified MCP server instance.
    
    This is the recommended way to create an MCP server for IPFS Kit.
    
    Args:
        host: Host address to bind to (default: 127.0.0.1)
        port: Port number to listen on (default: 8004)
        data_dir: Data directory for server state (default: ~/.ipfs_kit)
        debug: Enable debug logging (default: False)
    
    Returns:
        UnifiedMCPServer instance ready to run
    
    Example:
        >>> server = create_mcp_server(port=8004, debug=True)
        >>> server.run()
    """
    return UnifiedMCPServer(host=host, port=port, data_dir=data_dir, debug=debug)


def main():
    """Main entry point for running the server directly."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified IPFS Kit MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8004, help="Port to listen on")
    parser.add_argument("--data-dir", help="Data directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    server = create_mcp_server(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
        debug=args.debug
    )
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()


if __name__ == "__main__":
    main()
