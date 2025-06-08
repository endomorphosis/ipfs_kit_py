# Unified MCP Server

This document describes the unified MCP server implementation, which consolidates multiple scattered implementations into a single, comprehensive solution that properly exposes all tools to Claude through the Model Context Protocol (MCP).

## Overview

The Unified MCP Server is a robust implementation that resolves various issues with the previous scattered implementations. It provides:

- JSON-RPC endpoint for VS Code integration
- SSE endpoints for real-time updates
- Initialize endpoint for VS Code
- Complete API support for IPFS and storage operations
- Robust error handling and fallback mechanisms

## Components

### 1. `unified_mcp_server.py`

This is the main server implementation file, which combines the best features from various implementations:

- Contains proper implementations of all required endpoints for VS Code and Claude
- Includes comprehensive error handling
- Provides fallback mechanisms when components fail to initialize
- Automatically applies necessary patches and fixes
- Implements both `/jsonrpc` and `/api/v0/jsonrpc` endpoints
- Correctly exposes tools to Claude

### 2. `start_unified_mcp_server.sh`

This is a comprehensive startup script that:

- Provides a single entrypoint for managing the MCP server
- Stops any existing MCP server processes to avoid conflicts
- Starts the unified server with appropriate parameters
- Updates VS Code settings to point to the correct endpoints
- Tests that all endpoints are working correctly
- Provides helpful commands for monitoring and managing the server

## Usage

### Starting the Server

To start the server with default settings:

```bash
./start_unified_mcp_server.sh
```

### Managing the Server

The script provides several commands for managing the server:

```bash
# Stop the server
./start_unified_mcp_server.sh stop

# Check server status
./start_unified_mcp_server.sh status

# Restart the server
./start_unified_mcp_server.sh restart

# Only update VS Code settings (without restarting)
./start_unified_mcp_server.sh update-settings

# Test the endpoints
./start_unified_mcp_server.sh test
```

### Monitoring

To view the server logs:

```bash
tail -f mcp_server.log
```

## Configuration

The server can be configured using command-line arguments:

```bash
python unified_mcp_server.py --port 9994 --host 0.0.0.0 --api-prefix /api/v0 --debug
```

Key options:

- `--port`: The port to run on (default: 9994)
- `--host`: The host to bind to (default: 0.0.0.0)
- `--api-prefix`: The API prefix for endpoints (default: /api/v0)
- `--debug`: Enable debug mode
- `--isolation`: Enable isolation mode (simulation)
- `--skip-daemon`: Skip daemon initialization

## Endpoints

The server exposes the following key endpoints:

- **Root**: `http://localhost:9994/` - Basic server information
- **Health**: `http://localhost:9994/api/v0/health` - Server health status
- **SSE**: `http://localhost:9994/api/v0/sse` - Server-Sent Events stream
- **JSON-RPC**: `http://localhost:9994/jsonrpc` - JSON-RPC endpoint for VS Code integration
- **IPFS Operations**:
  - `http://localhost:9994/api/v0/ipfs/add` - Add content to IPFS
  - `http://localhost:9994/api/v0/ipfs/cat` - Retrieve content from IPFS
  - `http://localhost:9994/api/v0/ipfs/pin/add` - Pin content to IPFS
- **Storage Operations**:
  - `http://localhost:9994/api/v0/huggingface/status` - HuggingFace status
  - `http://localhost:9994/api/v0/filecoin/status` - Filecoin status
  - `http://localhost:9994/api/v0/storacha/status` - Storacha status
  - `http://localhost:9994/api/v0/lassie/status` - Lassie status

## VS Code Integration

The server integrates with VS Code through:

1. JSON-RPC protocol (for Language Server Protocol capabilities)
2. SSE endpoint for real-time updates
3. Initialize endpoint to respond to VS Code's initial connection

When started, the `start_unified_mcp_server.sh` script will automatically update VS Code settings to point to the correct endpoints.

## Troubleshooting

If you encounter issues:

1. **Check the logs**: `tail -f mcp_server.log`
2. **Check server status**: `./start_unified_mcp_server.sh status`
3. **Restart the server**: `./start_unified_mcp_server.sh restart`
4. **Verify endpoints**: `./start_unified_mcp_server.sh test`
5. **Check VS Code settings**: `cat ~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

## Fallback Mechanisms

If the server cannot initialize some components, it will:

1. Create dummy components for essential functionality
2. Log detailed error information in `mcp_server.log`
3. Continue operating with limited functionality
4. Provide clear indications when operating in fallback mode

## Why This Solution?

This unified solution addresses several issues with previous implementations:

1. **Consolidation**: Combines multiple scattered implementations into a single solution
2. **Reliability**: Includes robust error handling and fallback mechanisms
3. **Compatibility**: Ensures proper VS Code integration through correct endpoints
4. **Maintenance**: Single implementation is easier to maintain and update
5. **Documentation**: Clear documentation for usage and troubleshooting
