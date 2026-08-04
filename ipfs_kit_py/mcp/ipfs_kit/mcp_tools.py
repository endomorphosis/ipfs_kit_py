"""Canonical MCP tool surface for the ipfs_kit MCP package (KITA-037).

This module is a **facade** over the registry-derived MCP / MCP++ adapters in
``ipfs_kit_py.mcp_server.tools``.  It is the reviewed package-path projection
for KITA-037.

Note: a historical package directory ``mcp_tools/`` may shadow this module
under plain ``import ipfs_kit_py.mcp.ipfs_kit.mcp_tools``.  Callers that need
the registry-backed surface should import from
``ipfs_kit_py.mcp_server.tools`` (or load this file by path).  The supervisor
declared-output path is this file.

Importing the loaded module is inert: it does not start daemons, open network
connections, or load optional storage providers.
"""

from __future__ import annotations

from ipfs_kit_py.mcp_server.tools.manager import (
    MCPToolManager,
    build_tool_manager,
)
from ipfs_kit_py.mcp_server.tools.operation_adapter import (
    DuplicateToolRegistrationError,
    MCPPlusPlusToolAdapter,
    MCPToolAdapter,
    MCPToolAdapterError,
    UnknownToolError,
    build_mcp_plusplus_tool_adapter,
    build_mcp_tool_adapter,
    semantic_payload,
    strip_transport_fields,
)

__all__ = [
    "DuplicateToolRegistrationError",
    "MCPPlusPlusToolAdapter",
    "MCPToolAdapter",
    "MCPToolAdapterError",
    "MCPToolManager",
    "UnknownToolError",
    "build_mcp_plusplus_tool_adapter",
    "build_mcp_tool_adapter",
    "build_tool_manager",
    "semantic_payload",
    "strip_transport_fields",
]
