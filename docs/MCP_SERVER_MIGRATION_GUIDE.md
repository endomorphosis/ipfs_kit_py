# MCP Server Migration Guide

Status: Active
Canonical Runtime: ipfs_kit_py.mcp.servers.unified_mcp_server

## Summary

Legacy MCP server variants remain in the repository for compatibility tests but are deprecated.
Production runtime is the unified server only.

## Canonical Import

```python
from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server
```

## Production Guard

Legacy servers now enforce runtime guard behavior:
- if `IPFS_KIT_MCP_MODE=production` and `IPFS_KIT_ALLOW_LEGACY_MCP` is not enabled,
- legacy server initialization raises a runtime error.

Temporary override for emergency compatibility:
- `IPFS_KIT_ALLOW_LEGACY_MCP=1`

## Deprecated Paths

Examples of deprecated runtime modules:
- `ipfs_kit_py.mcp.servers.enhanced_mcp_server_with_vfs`
- `ipfs_kit_py.mcp.servers.standalone_vfs_mcp_server`
- `ipfs_kit_py.mcp.servers.enhanced_mcp_server_with_daemon_mgmt`

## Migration Steps

1. Replace legacy imports with unified import.
2. Update runbooks and startup scripts to call unified `create_mcp_server`.
3. Validate behavior with contract suites:
   - `pytest external/ipfs_kit/tests/test_vfs_contract_hardening.py -q`
   - `pytest external/ipfs_kit/tests/test_datasets_metadata_index_contract.py -q`
   - `pytest external/ipfs_kit/tests/test_mcp_vfs_adapter_contract.py -q`

## Tooling Surface

`tools/list` must only advertise tools with callable handlers.
`tools/call` behavior in unified server must be contract-consistent with `tools/list`.
