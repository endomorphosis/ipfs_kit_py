# IPFS Kit Python with MCP Integration

This project provides a comprehensive integration of IPFS (InterPlanetary File System) and VFS (Virtual File System) features with the MCP (Model Context Protocol) server.

## Code Organization

The code has been organized to address technical debt and improve maintainability:

1. **Consolidated MCP Server**: All functionality from various experimental implementations has been merged into a single `final_mcp_server.py`
2. **Organized Components**: Supporting modules are properly structured and focused on specific functionality
3. **Comprehensive Testing**: Test scripts verify all tool integrations work correctly
4. **Clean Directory Structure**: Non-essential files have been archived

## Key Components

- **final_mcp_server.py**: The main MCP server implementation with complete IPFS and VFS integration
- **mcp_vfs_config.py**: Configuration and registration for Virtual File System tools
- **integrate_vfs_to_final_mcp.py**: Integration module for VFS components
- **unified_ipfs_tools.py**: Unified IPFS tools implementation
- **fs_journal_tools.py**: Filesystem journal functionality
- **ipfs_mcp_fs_integration.py**: IPFS-FS bridge integration
- **multi_backend_fs_integration.py**: Multi-backend storage integration

## Available Tools

This integration provides tools in the following categories:

### IPFS Core Tools
- File operations (add, get, cat, ls)
- Content pinning and unpinning
- IPNS name publishing and resolution
- DAG operations
- Network and swarm management
- Peer connection management

### Virtual Filesystem (VFS) Tools
- File operations (read, write, list, remove)
- Directory operations (create, list, remove)
- File metadata and status information
- Path management

### Filesystem Journal Tools
- Operation tracking and history
- Synchronization with storage backends
- Path tracking management
- Journal status information

### IPFS-FS Bridge Tools
- Mapping between IPFS and local filesystem
- Synchronization tools
- Listing and management of mappings
- Status information

### Multi-Backend Storage Tools
- Backend initialization and management
- Storage status and information
- Mapping and unmapping operations
- Search and conversion functionality

## Installation

To install the integrated MCP server:

```bash
./install_integrated_mcp_server.sh
```

This script will:
1. Back up the existing server if present
2. Install the new integrated server
3. Make the necessary scripts executable

## Usage

### Starting the Server

To start the MCP server with all IPFS and VFS tools:

```bash
./start_integrated_mcp_server.sh
```

### Testing the Integration

To verify that all tools have been properly integrated:

```bash
./test_integrated_mcp_server.py
```

### Cleaning Up the Codebase

To clean up the codebase and move non-essential files to an archive directory:

```bash
./organize_codebase.sh
```

## API Endpoints

The MCP server provides the following endpoints:

- **GET /** - Root endpoint with server information
- **GET /health** - Health check endpoint
- **GET /tools** - List all registered tools
- **POST /jsonrpc** - JSON-RPC endpoint for tool execution

### JSON-RPC Methods

- **use_tool** - Execute a tool by name
- **get_tools** - Get a list of available tools
- **get_server_info** - Get server information

## Example Usage

### Using IPFS Tools

To add content to IPFS:

```json
{
  "jsonrpc": "2.0",
  "method": "use_tool",
  "params": {
    "tool_name": "ipfs_add",
    "arguments": {
      "content": "Hello, IPFS!"
    }
  },
  "id": 1
}
```

### Using VFS Tools

To write a file using the virtual filesystem:

```json
{
  "jsonrpc": "2.0",
  "method": "use_tool",
  "params": {
    "tool_name": "vfs_write_file",
    "arguments": {
      "path": "/example/hello.txt",
      "content": "Hello, VFS!"
    }
  },
  "id": 1
}
```

## Troubleshooting

If you encounter issues with the integration:

1. Check the server log file (`final_mcp_server.log`) for errors
2. Verify that all required dependencies are installed
3. Ensure IPFS daemon is running for IPFS functionality
4. Run the test script to diagnose specific component issues

## License

[MIT License](LICENSE)
