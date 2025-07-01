# IPFS MCP Server Documentation

This document provides comprehensive instructions for setting up, running, and using the Model Context Protocol (MCP) server with integrated IPFS tools.

## Overview

The MCP (Model Context Protocol) server provides a unified interface for IPFS functionality and tools. It enables communication between IPFS services and clients such as IDEs, notebooks, and applications.

### Key Features

- **Comprehensive IPFS Tool Coverage**: Access to core IPFS operations and advanced functionality
- **JSON-RPC Support**: Standard API for tool invocation
- **Mutable File System (MFS) Operations**: File management through IPFS
- **Multiple Storage Backend Integration**: IPFS, Filecoin, S3, and more
- **WebRTC Support**: Peer-to-peer connections
- **VS Code Integration**: Enhanced development experience

## Quick Start Guide

### Prerequisites

- Python 3.8+
- IPFS daemon installed and running
- Required Python packages

### Initial Setup

Run the final integration script to prepare the environment:

```bash
python3 final_integration.py
```

This script:
- Checks and configures required dependencies
- Verifies IPFS kit availability
- Prepares unified IPFS tools
- Creates necessary configuration files
- Sets up VS Code integration

### Starting the Server

Start the MCP server using the provided script:

```bash
./start_final_mcp_server.sh
```

By default, the server runs on port 3000. You can verify it's running with:

```bash
curl http://localhost:3000/health
```

### Custom Configuration

You can customize the server startup by editing the script or passing arguments:

```bash
# Change the port
./start_final_mcp_server.sh --port 8080

# Enable debug logging
./start_final_mcp_server.sh --debug

# Specify a different host
./start_final_mcp_server.sh --host 127.0.0.1
```

## Server Architecture

The MCP server is built on a FastAPI/Starlette foundation with several key components:

1. **Core Server**: Handles HTTP requests and manages tool registrations
2. **Tool Registry**: Maintains available IPFS tools
3. **JSON-RPC Interface**: Provides standardized API access
4. **SSE Connection**: Enables server-sent events for real-time updates
5. **IPFS Integration**: Connects to underlying IPFS functionality

## Server Endpoints

The server exposes several endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Homepage with server information |
| `/health` | GET | Health check endpoint |
| `/initialize` | POST | Client initialization endpoint |
| `/mcp` | GET | MCP SSE connection endpoint |
| `/jsonrpc` | POST | JSON-RPC endpoint for tool invocation |

### Example: Health Check

```bash
curl http://localhost:3000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 120.5,
  "registered_tools_count": 46,
  "timestamp": "2025-05-03T12:34:56.789012"
}
```

### Example: Initialization

```bash
curl -X POST http://localhost:3000/initialize
```

Response:
```json
{
  "server_info": {
    "name": "Final MCP Server",
    "version": "1.0.0",
    "status": "ready"
  },
  "capabilities": {
    "tools": ["ipfs_add", "ipfs_cat", "ipfs_pin", ...],
    "jsonrpc": true,
    "ipfs": true,
    "streaming": true
  }
}
```

## Available IPFS Tools

The server provides access to numerous IPFS operations, including:

### Core IPFS Operations
- `ipfs_add`: Add content to IPFS
- `ipfs_cat`: Retrieve content from IPFS
- `ipfs_pin`: Pin content in IPFS
- `ipfs_unpin`: Unpin content from IPFS
- `ipfs_list_pins`: List pinned content
- `ipfs_version`: Get IPFS version information

### Mutable File System (MFS) Operations
- `ipfs_files_ls`: List files and directories
- `ipfs_files_mkdir`: Create directories
- `ipfs_files_write`: Write file content
- `ipfs_files_read`: Read file content
- `ipfs_files_rm`: Remove files or directories
- `ipfs_files_stat`: Get file/directory information
- `ipfs_files_cp`: Copy files
- `ipfs_files_mv`: Move files
- `ipfs_files_flush`: Flush changes to IPFS

### Storage Backend Operations
- `s3_store_file`: Store a file to S3 storage
- `s3_retrieve_file`: Retrieve a file from S3 storage
- `filecoin_store_file`: Store a file to Filecoin storage
- `filecoin_retrieve_deal`: Retrieve a file from Filecoin

### IPNS Operations
- `ipfs_name_publish`: Publish an IPNS name
- `ipfs_name_resolve`: Resolve an IPNS name

### DHT Operations
- `ipfs_dht_findpeer`: Find a peer in the IPFS DHT
- `ipfs_dht_findprovs`: Find providers for a given CID

## Testing the Server

You can test server functionality using the included test script:

```bash
python3 test_final_mcp_server.py
```

This script:
- Checks server health
- Lists available tools
- Tests JSON-RPC endpoint
- Performs basic IPFS operations

## VS Code Integration

The MCP server automatically configures VS Code settings for integration:

1. Open VS Code in the project directory
2. Install any recommended extensions
3. Use the IPFS Kit extension to interact with the server
4. All tools are available through the VS Code command palette

## Troubleshooting

### Server Won't Start

1. Check if another instance is already running:
   ```bash
   ps aux | grep final_mcp_server
   ```

2. Verify Python paths are correctly set:
   ```bash
   echo $PYTHONPATH
   ```

3. Check logs for errors:
   ```bash
   cat final_mcp_server.log
   ```

### Connection Issues

1. Verify the server is running:
   ```bash
   curl http://localhost:3000/health
   ```

2. Check firewall settings if accessing remotely

### Tool Registration Problems

If tools aren't appearing in the initialization response:

1. Check unified_ipfs_tools.py for errors
2. Restart the server after making changes

## Advanced Configuration

For advanced configuration, edit these files:

- `final_mcp_server.py`: Main server implementation
- `unified_ipfs_tools.py`: Tool definitions and implementations
- `start_final_mcp_server.sh`: Startup parameters

## Additional Resources

- MCP Protocol Documentation: See `docs/mcp/protocol.md`
- IPFS Documentation: https://docs.ipfs.tech/
- FastMCP SDK Documentation: `docs/mcp-python-sdk/README.md`
