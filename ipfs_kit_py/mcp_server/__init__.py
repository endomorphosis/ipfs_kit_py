"""
MCP Server - Refactored to align with CLI codebase

This module provides the Model Context Protocol (MCP) server implementation that
mirrors the CLI functionality while adapting to the MCP protocol requirements.

The refactored MCP server:
1. Uses similar codebase structure to the CLI
2. Leverages metadata from ~/.ipfs_kit/ efficiently  
3. Integrates with the intelligent daemon for backend synchronization
4. Provides all CLI features through MCP protocol
5. Maintains compatibility with existing MCP clients
"""

from .server import MCPServer, MCPServerConfig
from .models.mcp_metadata_manager import MCPMetadataManager
from .services.mcp_daemon_service import MCPDaemonService

__all__ = [
    'MCPServer',
    'MCPServerConfig', 
    'MCPMetadataManager',
    'MCPDaemonService',
]
