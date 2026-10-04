# MCP IPFS/VFS Server Integration with VSCode

This document explains how the MCP (Model Context Protocol) server integrates with VSCode, IPFS, and virtual filesystem functionality.

## Overview

The comprehensive MCP server provides a unified interface for working with:

1. **IPFS Core Functionality** - Add content, retrieve content, pin management
2. **Virtual File System (VFS)** - Full filesystem operations (mkdir, read, write, ls, etc.)
3. **IPFS Mutable File System (MFS)** - IPFS-specific filesystem operations

All functionality is exposed through multiple transport protocols:

- **JSON-RPC** - Traditional request/response API
- **SSE (Server-Sent Events)** - Event-based streaming for VSCode integration

## Tools Available

The server exposes the following tool categories:

### Core Tools
- `ping` - Test server responsiveness
- `health` - Get server health status
- `list_tools` - Get list of all available tools
- `server_info` - Get server information
- `initialize` - Initialize server resources

### IPFS Core Tools
- `ipfs_version` - Get IPFS node version
- `ipfs_add` - Add content to IPFS
- `ipfs_cat` - Retrieve content from IPFS
- `ipfs_pin_add` - Pin a CID in IPFS
- `ipfs_pin_rm` - Unpin a CID in IPFS
- `ipfs_pin_ls` - List pinned CIDs in IPFS

### Virtual File System Tools
- `vfs_ls` - List directory contents
- `vfs_mkdir` - Create directory
- `vfs_rmdir` - Remove directory
- `vfs_read` - Read file content
- `vfs_write` - Write file content
- `vfs_rm` - Remove file

### IPFS MFS Tools
- `ipfs_files_mkdir` - Create directory in MFS
- `ipfs_files_write` - Write to file in MFS
- `ipfs_files_read` - Read file from MFS
- `ipfs_files_ls` - List directory contents in MFS
- `ipfs_files_rm` - Remove file or directory from MFS

## VSCode Integration

The server is fully compatible with VSCode's Cline MCP extension. This integration is achieved through:

1. Server-Sent Events (SSE) endpoint at `/sse`
2. Special server configuration in `cline_mcp_settings.json`

### Configuration

The MCP server is configured in VSCode's `cline_mcp_settings.json` file:

```json
{
  "mcpServers": {
    "direct-ipfs-kit-mcp2": {
      "autoApprove": [
        "health_check"
      ],
      "disabled": false,
      "timeout": 60,
      "url": "http://localhost:9996/sse",
      "transportType": "sse"
    }
  }
}
```

## Testing

The comprehensive testing framework validates:

1. Server connectivity and health
2. Tool availability and functionality
3. Integration between IPFS and VFS
4. End-to-end operations

Run the testing framework using:

```bash
./start_final_solution.sh --verify
```

Other test options include:

- `--tests-only` - Run only the tests
- `--inspect` - Perform deep inspection of IPFS/VFS integration
- `--check-connectivity` - Verify server connectivity
- `--analyze` - Analyze tool coverage

## Example Usage

Here are examples of using various tools:

### IPFS Core Examples

Add content to IPFS:
```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"ipfs_add","params":{"content":"Hello IPFS!"},"id":1}' \
  http://localhost:9996/jsonrpc
```

Retrieve content:
```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"ipfs_cat","params":{"cid":"YOUR_CID_HERE"},"id":1}' \
  http://localhost:9996/jsonrpc
```

### VFS Examples

Create a directory:
```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"vfs_mkdir","params":{"path":"/test"},"id":1}' \
  http://localhost:9996/jsonrpc
```

Write to a file:
```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"vfs_write","params":{"path":"/test/hello.txt","content":"Hello VFS!"},"id":1}' \
  http://localhost:9996/jsonrpc
```

Read from a file:
```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"vfs_read","params":{"path":"/test/hello.txt"},"id":1}' \
  http://localhost:9996/jsonrpc
```

## Architecture

The system architecture consists of several layers:

1. **Transport Layer** - HTTP endpoints for JSON-RPC and SSE
2. **API Layer** - Tool registration and invocation
3. **Implementation Layer** - Actual tool implementations
4. **Integration Layer** - Connections between IPFS and VFS

This layered approach ensures modularity, testability, and maintainability of the codebase.

## Troubleshooting

If VSCode's Cline extension doesn't connect to the MCP server:

1. Ensure server is running: `./start_final_solution.sh --check-connectivity`
2. Verify `/sse` endpoint works: `curl -N http://localhost:9996/sse`
3. Check `cline_mcp_settings.json` for correct URL and transport type
