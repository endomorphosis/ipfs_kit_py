# MCP Dashboard Unification Plan

Date: 2025-08-09
Branch: new_cope
Owner: endomorphosis/ipfs_kit_py

## Goals
- Single "MCP-first" dashboard launched via `ipfs-kit mcp start`.
- Feature parity with CLI without heavy ipfs_kit_py imports.
- Use the JavaScript MCP SDK from the dashboard to call server tools.
- Persist and control state primarily via files in `~/.ipfs_kit/`.
- Manage buckets, pins, backends, services; browse files; view logs; test tools.
- Lightweight FastAPI app with JSON-RPC, REST, SSE, and WebSocket.

## Requirements Checklist
- JSON-RPC endpoints
  - [ ] /mcp/tools/list returns server tool descriptors
  - [ ] /mcp/tools/call executes tools (buckets, pins, files, logs, services)
- REST endpoints (thin wrappers around the same logic)
  - [ ] GET/POST /api/state/backends
  - [ ] GET/POST/DELETE /api/state/backends/{name}
  - [ ] POST /api/state/backends/{name}/test
  - [ ] GET /api/services
  - [ ] GET/POST/DELETE /api/state/buckets and /api/state/buckets/{name}
  - [ ] GET/POST/DELETE /api/pins and /api/pins/{cid}
  - [ ] GET /api/files/list, GET /api/files/read, POST /api/files/write
  - [ ] GET /api/system/health, GET /api/mcp/status
- Real-time
  - [ ] GET /api/logs/stream (SSE)
  - [ ] /ws (WebSocket: initial system_update + echo/ack)
- Frontend
  - [ ] Single-page UI served at /
  - [ ] Tabs: Overview, Tools, Backends, Buckets, Pins, Files, Services, Logs
  - [ ] Loads JS MCP SDK (prefer static file, fallback inline)
  - [ ] Tools Explorer and simple forms for state operations
- Storage & State
  - [ ] Files under data_dir (default: ~/.ipfs_kit)
  - [ ] buckets.json, pins.json
  - [ ] backends/*.json + backend_configs/*.yaml
  - [ ] Optional parquet registries (pyarrow) for fast list/append
  - [ ] Atomic/locked writes; resilient reads with defaults
- CLI Parity
  - [ ] Dashboard tools mirror CLI functionality (list/create/delete, etc.)
  - [ ] `ipfs-kit mcp start` starts this dashboard reliably

## Repository Inventory (relevant)
- Primary module: consolidated_mcp_dashboard.py (keep)
- Prior art (for reference, not heavy imports):
  - ipfs_kit_py/mcp/dashboard/* (static assets, templates)
  - unified_dashboard.py, standalone_dashboard.py, modern_hybrid_mcp_dashboard.py
  - deprecated_dashboards/* (UI patterns and forms)
- Tests to satisfy
  - tests/test_dashboard_sdk_integration.py
  - tests/test_dashboard_logs.py, tests/test_dashboard_logs_clear.py
  - tests/test_dashboard_status_ws.py
  - tests/test_dashboard_state_buckets_pins.py

## Architecture
- FastAPI app with two integration modes:
  1) JSON-RPC (MCP) first-class: /mcp/tools/list, /mcp/tools/call
  2) REST mirrors that call the same Python functions (or delegate to JSON-RPC)
- File-backed state rooted at data_dir (cfg.data_dir or ~/.ipfs_kit)
- Optional Parquet acceleration (pyarrow if present); degrade gracefully when absent
- Minimal external deps: stdlib + FastAPI/Starlette; psutil optional
- Strict separation from heavy ipfs_kit_py imports; implement helpers locally

## Data Layout (default: ~/.ipfs_kit)
- buckets.json: {"buckets": [{name, backend, created_at}]}
- pins.json: {"pins": [{cid, name, pinned_at}]}
- backends/: {name}.json
- backend_configs/: {name}.yaml
- parquet/ (optional): buckets.parquet, pins.parquet
- logs/: *.log (optional list/tail helpers)

## API Surface (Server)
- JSON-RPC tools (subset):
  - get_system_status, get_system_overview, get_system_analytics
  - list_services
  - list_backends, backend_create/update/remove
  - list_buckets, create_bucket(name, backend), delete_bucket(name)
  - list_pins, create_pin(cid, name?), delete_pin(cid)
  - get_logs(limit, level?, component?), clear_logs()
  - files: list(path,bucket?), read(path,bucket?), write(path,content,bucket?)
- REST endpoints map 1:1 to internal functions; same validation and results

## Frontend (Client)
- Serve HTML at / with:
  - <script src="/static/mcp-sdk.js"></script> (fallback to /mcp-client.js)
  - <script src="/app.js"></script>
- app.js responsibilities:
  - ensureMcp(): fetch /mcp/tools/list and cache descriptors
  - rpcTool(name, args): call /mcp/tools/call and return result
  - UI Tabs
    - Overview: status + analytics
    - Tools: list tools; invoke with JSON forms
    - Backends: list/create/update/delete/test
    - Buckets: list/create/delete
    - Pins: list/create/delete
    - Files: list/read/write (within data_dir or selected bucket directory)
    - Services: detect binaries and running ports
    - Logs: live SSE panel + clear button
  - SSE: connect to /api/logs/stream for "log" events
  - WS: connect to /ws; read initial system_update; keep-alive optional

## Security & Hardening (phased)
- Phase 1: local dev only, no auth
- Phase 2: add CORS limits, simple token-based auth, rate limits for write routes
- Phase 3: optional OAuth or API key middleware (building blocks in repo exist)

## Implementation Phases
1) Stabilize the consolidated module
   - Fix route registration drift (buckets/pins/files currently 404 at runtime)
   - Ensure SDK alias and HTML/JS are clean and consistent
   - Smoke test with TestClient: root, tools list/call, services, backends, buckets, pins, files, logs, ws
2) Wire CLI lifecycle
   - Confirm ipfs_kit mcp start imports consolidated_mcp_dashboard.ConsolidatedMCPDashboard
   - PID file and logs under data_dir
3) Complete REST parity
   - Ensure all REST routes map to the same internal helpers
   - Add consistent JSON response envelopes {success, data|error}
4) Frontend polish
   - Tools Explorer: dynamic forms from inputSchema
   - Forms for backends/buckets/pins/files; optimistic updates on success
   - SSE log viewer and clear button
5) Optional accelerations
   - Parquet read/write if pyarrow installed; otherwise fallback to JSON
   - Simple in-memory cache for lists
6) Tests & QA
   - Make above test files pass locally
   - Add a minimal e2e smoke script (requests + websockets) as CI step

## Migration Strategy
- Retire duplicate dashboards by keeping their assets for inspiration only
- Keep consolidated_mcp_dashboard.py as the single entry point
- Reference static assets from ipfs_kit_py/mcp/dashboard_static when available
- Avoid importing legacy heavy modules; port only minimal helper logic as needed

## Risks & Mitigations
- Route drift between editor and runtime — verify by listing app.routes at startup
- Parquet optional dep — wrap with try/except and return None when unavailable
- State corruption — use locks and write temp + atomic rename
- CLI divergence — ensure CLI uses the same Python entry point

## Milestones
- M1: Routes fixed; buckets/pins/files REST working; tools list/call ok (1–2 days)
- M2: Frontend tabs wired; SDK integration complete; SSE/WS validated (1–2 days)
- M3: CLI parity checks; add small docs; pass existing dashboard tests (1 day)

## Verification
- Run:
  - tests/test_dashboard_sdk_integration.py
  - tests/test_dashboard_logs.py & tests/test_dashboard_logs_clear.py
  - tests/test_dashboard_status_ws.py
  - tests/test_dashboard_state_buckets_pins.py
- Manual:
  - Start with `ipfs-kit mcp start`, open http://127.0.0.1:8000/
  - Exercise all tabs and confirm ~/.ipfs_kit files update

---

Appendix A: Immediate Fixes Queue
- Fix consolidated_mcp_dashboard.py to register these missing routes at runtime:
  - GET/POST/DELETE /api/state/buckets
  - GET/POST/DELETE /api/pins
  - GET/POST /api/files/*
- Ensure /mcp-client.js serves SDK (or use /static/mcp-sdk.js when present)
- Add a tiny route dump at startup in debug mode to catch drift
