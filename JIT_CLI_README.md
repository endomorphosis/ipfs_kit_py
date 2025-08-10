# JIT CLI Usage for Consolidated MCP Dashboard

The IPFS-Kit CLI uses just-in-time (JIT) imports for fast startup and launches the consolidated MCP dashboard/server.

## Commands

- Start (foreground):

```bash
python -m ipfs_kit_py.cli mcp start --foreground --port 8004 --host 127.0.0.1
```

- Start (background):

```bash
python -m ipfs_kit_py.cli mcp start --port 8004 --host 127.0.0.1
```

- Status:

```bash
python -m ipfs_kit_py.cli mcp status --port 8004
```

- Stop:

```bash
python -m ipfs_kit_py.cli mcp stop --port 8004
```

## Files and paths

- Server: `consolidated_mcp_dashboard.py`
- CLI entry: `ipfs_kit_py/cli.py`
- Data directory (PID/logs/state): `~/.ipfs_kit` (overridable via `--data-dir`)

## Notes

- Foreground mode is recommended for development; background mode writes `mcp_<port>.pid` and `mcp_<port>.log` in the data directory for process management.
- The dashboard provides a simple HTML UI, a reusable JS SDK, JSON-RPC tools, minimal SSE/WS, and file-backed state.
