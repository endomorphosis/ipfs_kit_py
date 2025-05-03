# IPFS MCP Integration

This document explains how the IPFS Kit Python library has been integrated with the Model Context Protocol (MCP) to enable tools that can be used from Visual Studio Code and Claude.

## Overview

We've implemented a complete MCP server that exposes IPFS functionality as tools that can be used directly from Claude AI through the VS Code MCP extension. This integration includes:

1. **SSE Protocol Support**: Full implementation of the Server-Sent Events (SSE) protocol required by the VS Code MCP extension
2. **Tool Schema Definitions**: Complete tool schemas with parameters, descriptions, and types
3. **Virtual Filesystem Bridge**: Integration with the virtual filesystem layer
4. **VS Code Integration**: Configuration for the VS Code MCP extension

## Available Tools

The following tools are available through the MCP integration:

### Basic Filesystem Operations
- `list_files`: List files in a directory
- `read_file`: Read file contents
- `write_file`: Write content to a file

### IPFS Core Operations
- `ipfs_add`: Add content to IPFS
- `ipfs_cat`: Retrieve content by CID 
- `ipfs_pin`: Pin content

### IPFS MFS Operations (MFS = Mutable File System)
Multiple additional MFS operations are defined in the config but not yet implemented in the server:
- `ipfs_files_ls`: List files in MFS
- `ipfs_files_mkdir`: Create directories
- `ipfs_files_write`: Write to MFS files
- `ipfs_files_read`: Read from MFS files

## Components

### MCP Server with SSE (`mcp_server_with_sse.py`)

This is the main server that:
- Provides the `/initialize` endpoint with tool schemas
- Implements the SSE endpoint required by VS Code
- Provides the tool execution endpoints
- Manages connections and events

### VS Code Configuration

The configuration for VS Code MCP extension is stored in:
`~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

This file registers our IPFS MCP server with the extension.

### Test Client (`test_mcp_client.py`)

A simple MCP client that tests:
- Server information
- Server health
- Filesystem tools
- IPFS tools

## Starting and Stopping

You can start and stop the MCP server using:

```bash
# Start the server
./start_mcp_ipfs_integration.sh

# Stop the server
./stop_mcp_ipfs_integration.sh
```

## Testing

You can test the MCP server using:

```bash
# Test all tools
./test_mcp_client.py

# Test the server health
curl http://localhost:8000/health

# Test the server initialization endpoint
curl http://localhost:8000/initialize
```

## VS Code Integration

After starting the server, you should be able to use the IPFS tools directly from Claude in VS Code. The tools will be available in the `/tools` panel or by typing `/tools` in the chat.

## Implementation Details

### Tool Schemas

Each tool has a schema that defines:
- A name
- A description
- Parameters with types and descriptions
- Required parameters

These schemas are used by Claude to understand how to call the tools.

### SSE Implementation

The server implements the SSE protocol which allows for real-time communication between the server and VS Code. This includes:
- Initial connection events
- Heartbeats to keep connections alive
- Tool result events

### Mock IPFS Tools

The current implementation includes mock versions of IPFS tools that don't require a running IPFS daemon. This allows for testing and development without a full IPFS setup.

## Future Improvements

1. **Implement Real IPFS Tools**: Replace mock implementations with real IPFS operations
2. **Add More IPFS Features**: Add support for more IPFS operations like dag, pubsub, etc.
3. **Improved Virtual Filesystem Integration**: Better integration with the virtual filesystem layer
4. **Enhanced Error Handling**: More robust error handling and reporting
5. **Support for More MFS Operations**: Implement all MFS operations

## Troubleshooting

If you encounter issues:
1. Check the server logs: `tail -f mcp_proxy.log`
2. Ensure the server is running: `curl http://localhost:8000/health`
3. Restart the server: `./stop_mcp_ipfs_integration.sh && ./start_mcp_ipfs_integration.sh`
4. Check VS Code extension settings
