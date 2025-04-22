# MCP Server Quick Start Guide

This guide provides simple instructions to start and stop the MCP (Model-Controller-Persistence) server for the IPFS Kit project.

## Quick Start

Start the server with default settings:

```bash
./start_mcp_server.sh
```

Stop the server:

```bash
./stop_mcp_server.sh
```

## Starting Options

The start script provides several configuration options:

```bash
./start_mcp_server.sh [options]
```

Available options:
- `--port=NUMBER`: Port number to use (default: 9994)
- `--no-debug`: Disable debug mode
- `--no-isolation`: Disable isolation mode
- `--no-skip-daemon`: Don't skip daemon initialization (enables IPFS daemon management)
- `--api-prefix=PATH`: Set the API prefix (default: /api/v0)
- `--log-file=FILE`: Log file to use (default: mcp_server.log)
- `--foreground`: Run in foreground (don't detach)

Example:
```bash
./start_mcp_server.sh --port=8080 --no-isolation --no-skip-daemon
```

## Stopping Options

The stop script can be used with:

```bash
./stop_mcp_server.sh [options]
```

Available options:
- `--force`: Force kill the server instead of graceful shutdown

## API Endpoints

Once running, the server provides API endpoints:

- API Root: http://localhost:9994/api/v0
- Documentation: http://localhost:9994/docs
- Health Check: http://localhost:9994/api/v0/health

## Storage Backends

The MCP server supports multiple storage backends:

- IPFS (default)
- Hugging Face
- Storacha
- Filecoin
- Lassie
- S3

## Server Logs

Logs are stored in:
- Main log file: mcp_server.log (configurable)
- Console output: logs/mcp_server_stdout.log

## Direct Python Usage

You can also run the server directly with Python:

```bash
python run_mcp_server.py [options]
```

This accepts the same options as the shell script (without the -- prefix).

## For Developers

The MCP server implementation is located at:
- `ipfs_kit_py/run_mcp_server_real_storage.py`

Main server configuration files:
- `run_mcp_server.py`: Python entrypoint
- `start_mcp_server.sh`: Shell script to start server
- `stop_mcp_server.sh`: Shell script to stop server

See the full documentation at `docs/mcp/MCP_SERVER_README.md` for more details.
