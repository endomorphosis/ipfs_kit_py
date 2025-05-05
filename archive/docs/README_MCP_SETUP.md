# MCP Server with VS Code Integration

This directory contains an enhanced MCP (Model-Controller-Persistence) server implementation with VS Code integration.

## Key Components

1. **Enhanced MCP Server** - The core MCP server that handles IPFS operations
2. **Simple JSON-RPC Server** - A lightweight server that implements the Language Server Protocol (LSP) for VS Code integration
3. **Verification Script** - A tool to test if all components are working correctly
4. **Startup Script** - A convenient way to start both servers with one command

## Quick Start

To start both the MCP server and JSON-RPC server, run:

```bash
./start_mcp_server.sh
```

This script will:
- Stop any existing MCP or JSON-RPC servers
- Start the enhanced MCP server on port 9994
- Start the JSON-RPC server on port 9995
- Update your VS Code settings to connect to these servers
- Verify that everything is working correctly

## Manual Testing

You can test the servers manually using the verification script:

```bash
./verify_mcp_setup.py
```

Or test individual endpoints with curl:

```bash
# Test MCP server
curl http://localhost:9994/

# Test SSE endpoint
curl -N http://localhost:9994/api/v0/sse

# Test JSON-RPC endpoint
curl -X POST -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
     http://localhost:9995/jsonrpc
```

## VS Code Integration

The server setup updates your VS Code settings to connect to:
- MCP SSE endpoint: `http://localhost:9994/api/v0/sse`
- JSON-RPC endpoint: `http://localhost:9995/jsonrpc`

These settings enable VS Code extensions to communicate with the MCP server for IPFS operations and other features.

## Troubleshooting

If you're experiencing issues:

1. Check if both servers are running:
   ```bash
   ps aux | grep -E "python.*enhanced_mcp_server|python.*simple_jsonrpc_server" | grep -v grep
   ```

2. Check the log files:
   ```bash
   tail -50 mcp_server.log
   tail -50 simple_jsonrpc_server.log
   ```

3. Verify your VS Code settings:
   ```bash
   cat ~/.config/Code\ -\ Insiders/User/settings.json | grep -A 10 mcp
   ```

4. Restart the servers:
   ```bash
   ./start_mcp_server.sh
   ```

## Additional Scripts

- `verify_mcp_setup.py` - Tests all server components
- `simple_jsonrpc_server.py` - Standalone JSON-RPC server for VS Code
- `enhanced_mcp_server_fixed.py` - Enhanced MCP server with all features
