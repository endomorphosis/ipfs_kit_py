# Unified MCP Dashboard: Consolidation Plan

This document proposes a practical plan to merge prior dashboards into a single, JSON-RPC–first MCP dashboard that:
- Uses a lightweight JavaScript SDK for tool execution and transport.
- Avoids heavy imports from `ipfs_kit_py` and instead reads/writes state under `~/.ipfs_kit/` (YAML/Parquet/CAR/plain files).
- Achieves functional parity with the CLI for core operations: buckets, pins, files, backends, services, CARs, and logs.
- Is startable via the CLI: `ipfs_kit mcp start`.

## Goals and constraints

- JSON-RPC–first: All UI operations call MCP tools via the SDK (HTTP JSON-RPC). REST helpers allowed where trivial.
- File-first state: Persist and read program state primarily from `~/.ipfs_kit/` to avoid importing internal modules.
- CLI parity: The MCP tool handlers do the same underlying file ops the CLI uses, so both views are consistent.
- Light dependencies: No large frameworks on the client; server keeps FastAPI + Starlette; optional pyarrow/pyyaml.
- Reuse prior work: Migrate proven features from older dashboards (WS, SSE, logs, tools explorer, VFS) but keep code small and testable.

## Sources to mine (selected)

- `consolidated_mcp_dashboard.py` (current unified server + SPA; JSON-RPC-first, file-backed state)
- `dashboard.py` (legacy comprehensive UI: richer WS, uploads, analytics)
- `mcp/dashboard/refactored_unified_mcp_dashboard.py` (earlier unification paths)
These contain implementations and patterns we’ll reuse: tool listing/calling, WS/SSE status, logs, and panel layouts.

- Legacy bucket/pin UIs include YAML/Parquet syncing and richer forms → kept via JSON-RPC tools with YAML/Parquet best-effort.
- File/VFS browsing and basic read/write → implemented via `list_file/read_file/write_file/resolve_bucket_path` tools.
- CAR store ops → implemented (list/import/export/remove/import-to-bucket).
- Logs: in-memory buffer, file tailing, SSE heartbeat, WS echo → implemented.

## Data layout (under ~/.ipfs_kit)

  - JSON: `backends/<name>.json`
  - YAML: `backend_configs/<name>.yaml`
- Buckets
  - JSON registry: `buckets.json`
  - Parquet registry: `bucket_index/bucket_registry.parquet`
- Pins
  - JSON: `pins.json`
  - Parquet: `pin_metadata/parquet_storage/pins.parquet`
- Files VFS
  - Default root: `files/`
- CAR store
  - `car_store/*.car`
- Logs
  - `logs/*.log`, plus top-level `~/.ipfs_kit/*.log`

## Server architecture (FastAPI)
- Static assets
  - `/` → SPA HTML

## MCP tools (parity with CLI/file ops)
  - `get_system_status`, `get_system_overview`, `get_system_analytics`, `get_parquet_summary`
- Backends
  - `list_services`, `control_service` (start/stop/restart; lightweight, logs action)
- Buckets
  - `list_buckets`, `create_bucket`, `delete_bucket`
  - Parquet registry upsert/remove; write bucket YAML mirror
- Pins
  - `list_pins`, `create_pin`, `delete_pin`
  - Parquet append/remove
- Files VFS
  - `list_files`, `read_file`, `write_file`, `resolve_bucket_path`
- CAR store
  - `list_cars`, `import_car`, `export_car`, `remove_car`, `import_car_to_bucket`
- Logs

  - `createClient({ baseUrl })`
  - `toolsList()`, `toolsCall(name, args)`
  - `bindToolStubs(target)` → Attach functions by tool name on `window` for quick usage
- Dashboard loads `/mcp-client.js` (prefers real SDK file) and binds a global `mcpClient`.

## Dashboard UI (SPA panels)

- Overview: status, analytics, parquet summary, WS/SSE heartbeat display
- Tools Explorer: list and call tools (JSON args), see results; useful for development/testing
- Buckets: show registry and actions (create/delete) via Tools Explorer in v1; UI CRUD in v2
- Pins: same as Buckets
- Backends: list/show/create/update/remove/test
- Services: list and control (start/stop/restart)
- Files: list/read/write, resolve bucket paths
- CARs: list/import/export/remove/import-to-bucket
- Logs: in-memory view, file list and tail, auto-tail, SSE heartbeat

Implementation keeps the JS ES5-safe and exports handlers on `window` for inline `onclick` bindings.

Legacy feature merge plan (conscious choices):
- Keep: Tools, Backends, Services, Buckets, Pins, Files, CARs, Logs, Integrations, WS/SSE, analytics (light).
- Drop/Defer: Peer topology/replication management, heavy templating engines, WebRTC panels, cluster metrics with charts, server-side templates. These can be added later if file-first and dependency-light patterns are feasible.

## WebSocket and SSE

- WS: minimal system_update + echo roundtrip; later extend to push pin/bucket mutations
- SSE: heartbeats and log_count for a simple “live” indicator

## CLI integration

- `ipfs_kit mcp start` starts the FastAPI app (uvicorn) using the consolidated server.
- PID file written to `~/.ipfs_kit/mcp_<port>.pid` for management.
- Both CLI and MCP tools operate on the same files under `~/.ipfs_kit/`, keeping state consistent.

## Testing strategy

- Unit tests for tool handlers: backends/buckets/pins/files/CARs/logs
- Integration tests for JSON-RPC: `/mcp/tools/list` and `/mcp/tools/call`
- WS and SSE smoke tests: message receipt and heartbeats
- SDK integration tests: ensure `/mcp-client.js` loads and `toolsList()` works
- E2E with Playwright: boot the server on a test port, validate panels (Overview/Tools/Backends/Buckets/Pins/Integrations/Logs) with strict timeouts and deterministic startup/teardown.

## Phased rollout

1) Stabilize minimal MCP-first dashboard (current) with SDK, Tools Explorer, Logs, Files, CARs, Backends, Services.
2) Add bucket/pin CRUD UI (done), integrations grouping and backend diagnostics (done), and richer status widgets (partial).
3) Optional: Persist UI preferences (e.g., logs auto-refresh), add charts for analytics, and (if needed) add a file upload helper via base64 to complement text writes.

## Risks and mitigations

- Browser JS errors (embedding pitfalls) → Serve static `app.js`; keep ES5-safe; expose `window.*` bindings.
- Missing optional deps (pyarrow/pyyaml) → Guarded imports; fallback to JSON stores.
- State drift between CLI and MCP → Single source of truth: files under `~/.ipfs_kit/` only.

## Acceptance checklist

- [x] Start via `ipfs_kit mcp start` (or `ipfs-kit mcp start`) brings up the dashboard.
- [x] Tools Explorer lists and executes all tools.
- [x] Buckets, pins, backends, services, files, CARs, and logs are manageable via dashboard.
- [x] JSON-RPC SDK flows are used for all core operations.
- [x] State files under `~/.ipfs_kit/` reflect changes; CLI sees them too.
- [x] WS and SSE show live telemetry (basic heartbeat, system update).

## Immediate follow-ups

- Ensure `/mcp-client.js` prefers `web/mcp_client.js`; inline fallback exists (already implemented).
- Keep `/app.js` as a static file to avoid inlined string pitfalls (already implemented).
- Add lightweight docs to the README on how to start and use the dashboard.
