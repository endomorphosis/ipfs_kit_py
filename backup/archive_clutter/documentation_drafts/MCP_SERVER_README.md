# IPFS Kit MCP Server

This is a running implementation of the Model Context Protocol (MCP) server with IPFS integration.

## Current Status

The server is now operational on port 9996 with 47 registered IPFS-related tools.

## How to Run

To start the MCP server, follow these steps:

1. Navigate to the project directory:
   ```
   cd /home/barberb/ipfs_kit_py
   ```

2. Run the server script:
   ```
   ./run_mcp_server.sh
   ```

3. The server will start on http://localhost:9996

## Available Endpoints

- **Health Check**: `GET http://localhost:9996/health`
- **Server Initialization**: `POST http://localhost:9996/initialize`
- **MCP Streaming**: `GET http://localhost:9996/mcp` 
- **JSON-RPC Tool Invocation**: `POST http://localhost:9996/jsonrpc`

## Troubleshooting

If the server doesn't start properly, here are some things to check:

1. Check if the port is already in use:
   ```
   lsof -i :9996
   ```

2. Check the server logs:
   ```
   cat minimal_mcp_server.log
   ```

3. Stop any running server instances:
   ```
   pkill -f "minimal_mcp_server.py"
   ```

## Issues Fixed

The following issues were fixed in the current implementation:

1. **Port Configuration**: Changed from the default port 3000 to 9996 for VSCode/Cline compatibility
2. **Missing Functions**: Added proper implementations of missing functions
3. **Dependency Issues**: Resolved issues with module imports
4. **Environment Integration**: Added proper virtual environment activation
5. **Logging**: Enhanced logging for better debugging

## Available Tools

The server provides 47 IPFS-related tools that can be used through the JSON-RPC interface, including:

- IPFS file operations (ls, mkdir, write, read, etc.)
- IPFS name operations (publish, resolve)
- IPFS DAG operations (put, get)
- Filecoin storage operations
- WebRTC peer operations
- And many more

To see the full list of available tools, make a POST request to the initialize endpoint:
```
curl -X POST http://localhost:9996/initialize
```

## Example Tool Usage

To invoke a tool using JSON-RPC, send a POST request to `/jsonrpc` with the following structure:

```json
{
  "jsonrpc": "2.0",
  "method": "health_check",
  "params": {},
  "id": 1
}
```

For example:
```
curl -X POST http://localhost:9996/jsonrpc -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"health_check","params":{},"id":1}'
```
