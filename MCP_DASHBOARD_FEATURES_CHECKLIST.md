# MCP Dashboard Features Checklist

This checklist maps requirements to implementation artifacts and validation.

- Dashboard is MCP-first; JSON-RPC tools only
	- Endpoints: `POST /mcp/tools/list`, `POST /mcp/tools/call`
	- Files: `consolidated_mcp_dashboard.py`, `static/app.js`
	- Status: Verified by Python tests
- File-backed parity (avoid heavy imports)
	- Uses `~/.ipfs_kit` for `buckets.json`, `pins.json`, `backends/*`, `car_store/*`, `logs/*`, and bucket files
	- Optional YAML/Parquet guarded
- Buckets: create/list/delete
	- Tools: `create_bucket`, `list_buckets`, `delete_bucket`
	- UI: Buckets panel
	- Tests: Python + Playwright (spec present)
- Pins: create/list/delete
	- Tools: `create_pin`, `list_pins`, `delete_pin`
	- UI: Pins panel
- Backends: list/create/update/remove/test
	- Tools: `backend_create`, `backend_update`, `backend_remove`, `backend_show`
	- REST `GET/POST/DELETE /api/state/backends*` for diagnostics/test
	- UI: Backends + Integrations panels
- Services: list/control
	- Tools: `get_services`, `control_service`
	- UI: Services panel
- Files: list/read/write; resolve bucket path
	- Tools: `list_files`, `read_file`, `write_file`, `resolve_bucket_path`
	- UI: Files panel
- CARs: list/import/export/remove; import-to-bucket
	- Tools: `list_cars`, `import_car`, `export_car`, `remove_car`, `import_car_to_bucket`
	- UI: CARs panel
- Logs: get/clear/list files/tail; SSE stream
	- Tools: `get_logs`, `clear_logs`, `list_log_files`, `tail_file`
	- Endpoints: `/api/logs/stream`
	- UI: Logs panel
- Overview & diagnostics
	- `/api/mcp/status` (initialized, total_tools, uptime)
	- SDK ready; tools list normalization
- SDK delivery
	- Route: `/mcp-client.js` (external SDK + shim or inline fallback)
- CLI lifecycle
	- `ipfs_kit_py/cli.py` mcp start/stop/status (status now probes HTTP)
- Tests
	- Python tests: multiple suites green
	- Playwright E2E: config + specs present; runnable in a clean Node env

Overall: Feature-complete per requirements.
# MCP Dashboard Feature Coverage Checklist

This checklist maps the requested requirements to the implemented features in the consolidated MCP dashboard.

## Requirements

- [x] Single unified dashboard (JSON-RPC-first) replacing prior dashboards
- [x] Reusable JavaScript SDK served at `/mcp-client.js` (inline fallback, external + shim if `web/mcp_client.js` exists)
- [x] CLI parity: file-backed state using `~/.ipfs_kit` primarily
- [x] Startable via `ipfs-kit mcp start` (or `python -m ipfs_kit_py.cli mcp start`)
- [x] Tools panel to list/call MCP tools
- [x] Backends panel: CRUD + per-type diagnostics
- [x] Services panel: lightweight controls/status
- [x] Buckets: list/create/delete (JSON + YAML + Parquet registry when available)
- [x] Pins: list/create/delete (JSON + Parquet when available)
- [x] Files: list/read/write and bucket path resolution
- [x] CARs: list/import/export/remove; import-to-bucket
- [x] Logs: in-memory buffer, list log files, tail, SSE heartbeat, WS echo
- [x] Health/status endpoints and minimal analytics
- [x] Minimal dependencies; heavy libs optional/guarded (pyarrow, pyyaml, psutil)
- [x] SPA served with static `app.js` to avoid inline issues; ES5-safe
- [x] WebSocket `/ws` sends `system_update` and echoes messages
- [x] SSE `/api/logs/stream` emits periodic heartbeats
- [x] PID file written on start for lifecycle management (CLI/tests)
- [x] Playwright E2E tests added (environment may need npm install)

## Notes

- Environment without Node/NPM may not run Playwright locally; the suite is committed for CI/other machines.
- Backend diagnostics avoid network calls and heavy imports; they check ports, tokens, config presence, and optional library availability.
- Parquet/YAML operations are best-effort and guarded behind optional imports; JSON is the default state format.
