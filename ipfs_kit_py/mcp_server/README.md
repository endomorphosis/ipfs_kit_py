# MCP Server Compatibility Module

## Purpose

This directory exists for backward compatibility purposes only. The MCP server implementation has been consolidated in the `ipfs_kit_py/mcp/` directory as of Q2 2025.

## Usage

This module provides compatibility imports for code that may still be importing from the old paths. It will emit deprecation warnings and redirect imports to the new consolidated structure.

```python
# Old imports (deprecated)
from ipfs_kit_py.mcp_server import IPFSBackend

# New imports (recommended)
from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
```

## Migration

All code should be updated to use the new import paths from the consolidated structure. This compatibility layer may be removed in a future version.

See the `mcp_roadmap.md` file for more details on the server architecture consolidation.