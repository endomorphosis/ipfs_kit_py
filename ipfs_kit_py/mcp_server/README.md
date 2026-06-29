# ipfs_kit_py MCP++ server

A canonical MCP++ server for `ipfs_kit_py`, aligned to the
[Mcp-Plus-Plus](../../../../Mcp-Plus-Plus) packet spec so third parties
interoperate via the standard. It mirrors the tool-group architecture used in
`ipfs_datasets_py` and exposes **one** tool registry across four surfaces.

## One registry, four surfaces

`tools/__init__.py::TOOL_GROUPS` is the single source of truth. Each tool is a
thin async wrapper over `core_operations._call` (canonical biz logic over the
`ipfs_kit` orchestrator). Surfaces:

| Surface | How |
|---------|-----|
| Python import | `from ipfs_kit_py.mcp_server.tools.ipfs_tools import ipfs_add` |
| CLI | `ipfs-kit-mcp-tools ipfs_tools ipfs_add --file_path x` |
| MCP server | `ipfs-kit-mcp --transport stdio\|http` — JSON-RPC `tools/list`, `tools/call` |
| JavaScript | `python -m ipfs_kit_py.mcp_server.js_sdk.generate` → `ipfs-kit-mcp-sdk.js` |

## Tool groups

`ipfs_tools`, `pin_tools`, `dag_tools`, `cluster_tools` — add via a new module
under `tools/` + an entry in `TOOL_GROUPS`. Schemas auto-derive from signatures.

## Runtime

anyio on the **trio** backend; HTTP via **Hypercorn** (trio worker); optional
**libp2p**/UCAN/CID via the graceful `mcplusplus` layer (no-op when extras
absent). Backwards-compatible with stock MCP clients (initialize/tools/*).

## Tests

`pytest ipfs_kit_py/mcp_server/tests_e2e_interop.py` — proves Python/CLI/MCP
(stdio+HTTP)/JS-SDK share the same 7 tools and contract.
