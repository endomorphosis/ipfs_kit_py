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
    - `GET /api/mcp/status` now returns lightweight telemetry fields:
      - `counts.requests` – total HTTP requests handled since process start (incremented by a minimal middleware)
      - `security.auth_enabled` – boolean indicating whether an API token was configured (read-only endpoints remain open)

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

See also: `MCP_DASHBOARD_FEATURE_PARITY_CHECKLIST.md` for a checklist to track visual/functional parity with the legacy dashboard.

## Finalized Features (2025)

- **Modern schema-driven UI**: SPA with sidebar navigation, dashboard cards, and real-time updates
- **Tool Runner UI**: Legacy and beta (schema-driven) UIs available
  - Enable beta UI via `?ui=beta` or `localStorage.setItem('toolRunner.beta', 'true')`
- **MCP JS SDK**: `/mcp-client.js` exposes `window.MCP` with all tool namespaces
- **Endpoints**:
  - `/` (UI)
  - `/mcp-client.js` (SDK)
  - `/app.js` (UI logic)
  - `/api/mcp/status`, `/api/system/health` (status)
  - Status includes `counts.requests` and `security.auth_enabled` for basic observability & security introspection.
  - `/api/logs/stream` (SSE), `/ws` (WebSocket)
  - `POST /mcp/tools/list`, `POST /mcp/tools/call` (JSON-RPC)
  - `/api/state/backends`, `/api/services`, `/api/files`, etc.
- **Panels**:
  - Overview, Tools, Buckets, Pins, Backends, Services, Integrations, Files, CARs, Logs
- **Accessibility**: ARIA roles, keyboard navigation, responsive design
- **Testing**: Playwright E2E, Python smoke/unit tests
- **Data locations** (default):
  - `~/.ipfs_kit/buckets.json`, `~/.ipfs_kit/pins.json`
  - `~/.ipfs_kit/backends/*.json`, `~/.ipfs_kit/backend_configs/*.yaml`
  - `~/.ipfs_kit/files/`, `~/.ipfs_kit/car_store/*.car`, `~/.ipfs_kit/logs/*.log`

---

## Quickstart

Start the dashboard server:

```bash
ipfs-kit mcp start --host 127.0.0.1 --port 8004
# or
python -m ipfs_kit_py.cli mcp start --host 127.0.0.1 --port 8004
```

Open the UI at [http://127.0.0.1:8004/](http://127.0.0.1:8004/)

Stop or check status:

```bash
ipfs-kit mcp stop --port 8004
ipfs-kit mcp status --port 8004
```

---

## Tool Runner UI

- **Legacy UI**: Simple select + run
- **Beta UI**: Schema-driven forms, ARIA, validation, keyboard shortcuts
  - Enable via `?ui=beta` or `localStorage.setItem('toolRunner.beta', 'true')`

## MCP JS SDK

- Exposed at `/mcp-client.js` as `window.MCP`
- Namespaces: Services, Backends, Buckets, Pins, Files, IPFS, CARs, State, Logs, Server
- Methods: `listTools()`, `callTool(name, args)`, plus per-namespace helpers

## Panels

- Overview, Tools, Buckets, Pins, Backends, Services, Integrations, Files, CARs, Logs

## Data Locations

- All state is file-backed under `~/.ipfs_kit` for CLI parity

## Testing

- Playwright E2E tests (see `tests/e2e/`)
- Python smoke and unit tests

## Documentation

- See `MCP_DASHBOARD_UI_PLAN.md` for UI/UX and implementation plan
- See `README_BETA_UI.md` for beta Tool Runner UI details

---

## Notes

- The SSE and WebSocket endpoints are minimal and geared toward testing/smoke checks. JSON-RPC over HTTP is the primary interface.
- State writes are done via a simple tmp-and-replace strategy for safety.
