# Consolidated MCP Dashboard (JSON-RPC First)

This project includes a minimal, unified MCP dashboard and server designed to be simple, stable, and JSON-RPC-first. It consolidates prior dashboards into a single service and persists lightweight state under `~/.ipfs_kit`.

## What it provides

- Single FastAPI app serving:
  - HTML UI at `/`
  - Reusable JS SDK at `/mcp-client.js` (inline; if `web/mcp_client.js` exists it is served plus a compatibility shim) and app also loads `/static/mcp-sdk.js` if present
  - JSON-RPC endpoints:
    - `POST /mcp/tools/list`
    - `POST /mcp/tools/call`
  - Health/status:
    - `GET /api/system/health`
    - `GET /api/mcp/status`
  - Observability:
    - `GET /api/logs/stream` (SSE; single event for tests)
    - `WS /ws` (sends one system_update, then echoes "ack")

- File-backed state (default: `~/.ipfs_kit`):
  - `buckets.json`: `[ { name, backend, created_at } ]`
  - `pins.json`: `[ { cid, name, pinned_at } ]`
  - `backends/*.json` and/or `backend_configs/*.yaml`
  - `files/` and per-bucket resolved base paths
  - `car_store/*.car`, `logs/*.log`

- In-memory logs buffer with tools:
  - `get_logs({ component?, level?, limit? })`
  - `clear_logs()`

## How to run via CLI

The CLI uses just-in-time imports and starts the dashboard as a foreground or background process.

Foreground (blocks; best for development):

```bash
python -m ipfs_kit_py.cli mcp start --host 127.0.0.1 --port 8004 --foreground
```

Background (writes PID/log files under `~/.ipfs_kit`):

```bash
python -m ipfs_kit_py.cli mcp start --host 127.0.0.1 --port 8004
```

Check status / stop:

```bash
python -m ipfs_kit_py.cli mcp status --port 8004
python -m ipfs_kit_py.cli mcp stop --port 8004
```

Then visit:

- Dashboard: http://127.0.0.1:8004/
- MCP endpoints: http://127.0.0.1:8004/mcp/*

## Available tools (examples)

List tools:

```json
POST /mcp/tools/list
{ "jsonrpc": "2.0", "method": "tools/list", "id": 1 }
```

Call tool:

```json
POST /mcp/tools/call
{ "jsonrpc": "2.0", "method": "tools/call", "id": 2, "params": { "name": "list_buckets", "arguments": {} } }
```

Implemented tool names (subset):

- get_system_status, get_system_overview, get_system_analytics
- list_services, list_backends
- list_buckets, create_bucket, delete_bucket
- list_pins, create_pin, delete_pin
- get_logs, clear_logs

## JS SDK

The inline UMD-style SDK is available at `/mcp-client.js` and exposes:

- `MCP.createClient({ baseUrl? })`
- `client.toolsList()` / `client.listTools()`
- `client.toolsCall(name, args)` / `client.callTool(name, args)`
- `client.bindToolStubs(target=window)` to attach functions named after tools

The dashboard UI uses this SDK and includes a simple Logs panel as a reference integration.

If `web/mcp_client.js` exists, the server will serve that file and append a small compatibility shim to ensure `window.MCP` and `window.mcpClient` are available.

## File locations

- Server: `consolidated_mcp_dashboard.py` (repository root)
- CLI entry: `ipfs_kit_py/cli.py`
- Data dir: `~/.ipfs_kit` by default (configurable via `--data-dir`)
 - Static UI overrides: `static/app.js`, `static/mcp-sdk.js`
 - Optional external SDK: `web/mcp_client.js`

## UI Panels

The SPA includes the following panels:

- Overview (status, analytics, parquet summary)
- Tools (list/call JSON-RPC tools with args)
- Buckets (list/create/delete; YAML and Parquet registry integration when available)
- Pins (list/create/delete; optional Parquet append/remove)
- Backends (CRUD + per-type diagnostics)
- Services (lightweight service controls and status)
- Integrations (group backends by type; run quick tests)
- Files (list/read/write; bucket path resolution)
- CARs (list/import/export/remove; import-to-bucket)

See `MCP_DASHBOARD_FEATURES_CHECKLIST.md` for requirement coverage.

## Notes

- The SSE and WebSocket endpoints are minimal and geared toward testing/smoke checks. JSON-RPC over HTTP is the primary interface.
- State writes are done via a simple tmp-and-replace strategy for safety.
