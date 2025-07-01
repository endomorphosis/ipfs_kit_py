# MCP Server VS Code Integration

This folder contains scripts and tools to improve the integration between the MCP server and VS Code.

## Quick Start

To start both the MCP server and the enhanced JSON-RPC server for VS Code, run:

```bash
./start_enhanced_mcp_stack.sh
```

This script will:
- Stop any existing MCP or JSON-RPC servers
- Start the enhanced MCP server on port 9994
- Start the enhanced VS Code JSON-RPC server on port 9995
- Update your VS Code settings to point to these servers
- Verify that everything is working correctly

## Troubleshooting

If VS Code still shows "Waiting for server to respond to initialize request", see the detailed troubleshooting guide:

```bash
cat TROUBLESHOOT_VSCODE_MCP.md
```

## Diagnostic Tools

This repository includes several diagnostic tools to help identify and fix VS Code integration issues:

- `debug_vscode_connection.py` - Tests the basic JSON-RPC and SSE connections
- `diagnose_vscode_extension.py` - More comprehensive VS Code extension diagnostics
- `fix_vscode_mcp_integration.py` - Fixes VS Code settings and server configuration

## Manual Testing

You can manually test the key components:

```bash
# Test MCP server
curl http://localhost:9994/

# Test JSON-RPC server
curl http://localhost:9995/

# Test SSE endpoint
curl -N http://localhost:9994/api/v0/sse | head -1

# Test JSON-RPC initialize request
curl -X POST -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
     http://localhost:9995/jsonrpc
```

## VS Code Settings

Make sure your VS Code settings contain:

```json
{
  "mcp": {
    "servers": {
      "my-mcp-server": {
        "url": "http://localhost:9994/api/v0/sse"
      }
    }
  },
  "localStorageNetworkingTools": {
    "lspEndpoint": {
      "url": "http://localhost:9995/jsonrpc"
    }
  }
}
```
