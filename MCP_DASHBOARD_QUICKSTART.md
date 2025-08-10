# MCP Dashboard Quickstart

Start the consolidated dashboard and verify it quickly.

## start
```bash
ipfs-kit mcp start --port 8004
```

## status
```bash
ipfs-kit mcp status --port 8004
# Example: MCP (port 8004) PID file present: pid=12345 alive=True
#          HTTP status: ok initialized=True tools=30
```

## stop
```bash
ipfs-kit mcp stop --port 8004
```

## browse
- Open http://127.0.0.1:8004
- Panels: Overview, Tools, Backends, Services, Files, CARs, Buckets, Pins, Logs, Integrations

## test (python)
```bash
# from repo root, in venv
pytest -q tests/test_dashboard_status_ws.py tests/test_dashboard_logs.py tests/test_backends_services_tools.py -q
```

## test (playwright)
- Ensure a clean Node environment with write access.
```bash
npm install
npx playwright install --with-deps
DASHBOARD_URL=http://127.0.0.1:8014 npm run e2e
```

Notes:
- State is stored under `~/.ipfs_kit`.
- Optional YAML/Parquet features activate only when libraries are installed.
