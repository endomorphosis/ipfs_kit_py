"""Exceptions for the ipfs_kit_py MCP++ server.

Mirrors the canonical exception taxonomy used by ipfs_datasets_py's mcp_server
so error shapes stay interoperable across the Mcp-Plus-Plus aligned servers.
"""
from __future__ import annotations


class MCPServerError(Exception):
    """Base error for the MCP++ server."""


class ToolNotFoundError(MCPServerError):
    def __init__(self, category: str, tool: str) -> None:
        self.category = category
        self.tool = tool
        super().__init__(f"tool not found: {category}/{tool}")


class CategoryNotFoundError(MCPServerError):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(f"category not found: {category}")


class ToolExecutionError(MCPServerError):
    def __init__(self, tool: str, cause: Exception) -> None:
        self.tool = tool
        self.cause = cause
        super().__init__(f"tool execution failed: {tool}: {cause}")


class ConfigurationError(MCPServerError):
    pass
