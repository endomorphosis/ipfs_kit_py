# Consolidated IPFS-VFS MCP Server

This is the final, consolidated MCP server implementation that integrates all IPFS and Virtual Filesystem tools into a single, reliable server. It resolves previous code debt issues and provides a clean, organized codebase.

## Features

- **Core IPFS Functionality**: Direct integration with the IPFS network
- **Virtual Filesystem (VFS)**: In-memory filesystem for temporary storage and manipulation
- **IPFS-VFS Bridge**: Seamless integration between IPFS and the virtual filesystem
- **Filesystem Journal**: Logging of all filesystem operations
- **JSON-RPC Interface**: Consistent API following the Model Context Protocol
- **Health Monitoring**: Endpoint for checking server status
- **VSCode Integration**: Initialize endpoint for IDE integration

## Architecture

The consolidated server is designed with a clean, modular architecture:

1. **VirtualFileSystem**: In-memory filesystem implementation
2. **FilesystemJournal**: Records all operations performed on the filesystem
3. **IPFSVFSBridge**: Connects the virtual filesystem to IPFS
4. **IPFSTools**: Core IPFS API wrapper
5. **MCPServer**: Main server implementation that exposes all tools
6. **JSON-RPC Handler**: Processes client requests

## Available Tools

The server exposes the following tool categories:

### IPFS Tools
- `ipfs_add`: Add content to IPFS
- `ipfs_cat`: Retrieve content from IPFS
- `ipfs_pin_add`: Pin content to local IPFS node
- `ipfs_pin_ls`: List pinned content
- `ipfs_pin_rm`: Unpin content from local IPFS node

### VFS Tools
- `vfs_mkdir`: Create a directory in the virtual filesystem
- `vfs_write`: Write content to a file in the virtual filesystem
- `vfs_read`: Read content from a file in the virtual filesystem
- `vfs_stat`: Get information about a file or directory
- `vfs_list`: List the contents of a directory
- `vfs_rm`: Remove a file or directory

### IPFS-VFS Bridge Tools
- `ipfs_fs_export_to_ipfs`: Export a file from VFS to IPFS
- `ipfs_fs_import_from_ipfs`: Import content from IPFS to VFS
- `ipfs_fs_bridge_status`: Get the status of the bridge
- `ipfs_fs_bridge_list_mappings`: List all VFS/IPFS mappings

### Filesystem Journal Tools
- `fs_journal_record`: Record an operation in the journal
- `fs_journal_get_history`: Get the operation history
- `fs_journal_status`: Get the journal status
- `fs_journal_clear`: Clear the journal

### Utility Tools
- `utility_ping`: Test server connectivity
- `utility_server_info`: Get server information

## Usage

### Starting the Server

Use the provided start script:

```bash
./start_consolidated_mcp_server.sh
```

This script will:
1. Check if the IPFS daemon is running and start it if needed
2. Launch the MCP server on port 3000

### Stopping the Server

To stop the running server:

```bash
./stop_consolidated_mcp_server.sh
```

### Testing the Server

A comprehensive test script is provided:

```bash
python3 test_consolidated_mcp_server.py
```

This will test all available tools and verify they are working correctly.

### API Endpoints

- `http://127.0.0.1:3000/jsonrpc`: Main JSON-RPC endpoint
- `http://127.0.0.1:3000/health`: Health check endpoint
- `http://127.0.0.1:3000/initialize`: VSCode integration endpoint
- `http://127.0.0.1:3000/tools`: Available tools list

### JSON-RPC Example

```javascript
// Example request to add content to IPFS
fetch("http://127.0.0.1:3000/jsonrpc", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    jsonrpc: "2.0",
    method: "use_tool",
    params: {
      tool_name: "ipfs_add",
      content: "Hello, IPFS!",
      name: "hello.txt"
    },
    id: 1
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

## Development

The consolidated server is designed to be easily extendable. To add new tools:

1. Implement the tool functionality
2. Register the tool in the `_register_tools` method of the `MCPServer` class
3. Update the test script to include tests for the new tool

## Requirements

- Python 3.6+
- IPFS daemon
- Python packages: starlette, uvicorn, requests

## License

This project is licensed under the terms specified in the LICENSE file.
