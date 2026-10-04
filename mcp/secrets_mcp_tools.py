"""Compatibility shim for `mcp.secrets_mcp_tools`.

The canonical implementation lives under `ipfs_kit_py.mcp.servers.secrets_mcp_tools`.

Why this file exists:
- Provides backward compatibility for imports
- Allows tests to patch functions and have handlers use the patched values
- Follows the established pattern used by other MCP tools
"""

from __future__ import annotations

from ipfs_kit_py.mcp.servers.secrets_mcp_tools import *  # noqa: F403, F401

# Re-export everything from the canonical implementation
from ipfs_kit_py.mcp.servers import secrets_mcp_tools as _impl

# Re-export key components
SECRETS_AVAILABLE = _impl.SECRETS_AVAILABLE
AES_ENCRYPTION_AVAILABLE = getattr(_impl, "AES_ENCRYPTION_AVAILABLE", False)
MCP_AVAILABLE = getattr(_impl, "MCP_AVAILABLE", False)

create_secrets_tools = _impl.create_secrets_tools
get_secrets_manager = _impl.get_secrets_manager
SECRETS_HANDLERS = _impl.SECRETS_HANDLERS

# Re-export handlers
handle_secrets_store = _impl.handle_secrets_store
handle_secrets_retrieve = _impl.handle_secrets_retrieve
handle_secrets_rotate = _impl.handle_secrets_rotate
handle_secrets_delete = _impl.handle_secrets_delete
handle_secrets_list = _impl.handle_secrets_list
handle_secrets_migrate = _impl.handle_secrets_migrate
handle_secrets_statistics = _impl.handle_secrets_statistics
handle_secrets_encryption_info = _impl.handle_secrets_encryption_info
