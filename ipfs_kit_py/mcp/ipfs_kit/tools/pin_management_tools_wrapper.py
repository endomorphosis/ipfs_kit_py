#!/usr/bin/env python3
"""
Pin Management Tools - MCP Wrapper

This is a thin wrapper that re-exports all functionality from the main
ipfs_kit_py.tools.pin_management_tools module. This ensures that:
1. The single source of truth is in the ipfs_kit_py package
2. MCP tools import from the main package (correct architecture)
3. Backward compatibility is maintained for existing MCP code

For new code, import directly from ipfs_kit_py.tools.pin_management_tools
"""

# Re-export everything from the main package
from ipfs_kit_py.tools.pin_management_tools import *

# Maintain backward compatibility
__all__ = [
    'handle_list_pins',
    'handle_get_pin_stats',
    'handle_get_pin_metadata',
    'handle_unpin_content',
    'handle_bulk_unpin',
    'handle_export_pins',
    'format_size',
]
