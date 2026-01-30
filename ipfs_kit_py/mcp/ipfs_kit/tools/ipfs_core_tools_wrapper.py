#!/usr/bin/env python3
"""
IPFS Core Tools - MCP Wrapper

This is a thin wrapper that re-exports all functionality from the main
ipfs_kit_py.tools.ipfs_core_tools module. This ensures that:
1. The single source of truth is in the ipfs_kit_py package
2. MCP tools import from the main package (correct architecture)
3. Backward compatibility is maintained for existing MCP code

For new code, import directly from ipfs_kit_py.tools.ipfs_core_tools
"""

# Re-export everything from the main package
from ipfs_kit_py.tools.ipfs_core_tools import *

# Maintain backward compatibility
__all__ = [
    'IPFSClient',
    'ipfs_client',
    'handle_ipfs_add',
    'handle_ipfs_cat',
    'handle_ipfs_get',
    'handle_ipfs_ls',
    'handle_ipfs_pin_add',
    'handle_ipfs_pin_rm',
    'handle_ipfs_pin_ls',
    'handle_ipfs_pin_update',
]
