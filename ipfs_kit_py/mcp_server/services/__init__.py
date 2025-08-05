"""
MCP Server Services - Backend integration services

This package contains services for the MCP server:
- MCPDaemonService: Integration with intelligent daemon manager
"""

from .mcp_daemon_service import MCPDaemonService

__all__ = [
    'MCPDaemonService',
]
