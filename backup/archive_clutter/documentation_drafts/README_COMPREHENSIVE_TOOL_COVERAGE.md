# IPFS Kit Comprehensive Tool Coverage

This document describes the comprehensive tool coverage for IPFS Kit, including integration with the virtual filesystem features and the MCP server.

## Overview

We have successfully enhanced the MCP server with a comprehensive set of tools that cover:

1. Core IPFS operations
2. Mutable File System (MFS) operations
3. Virtual filesystem operations
4. Multi-backend storage integration
5. Storage backend initialization and management

The tools are integrated with the MCP server, making them available through the JSON-RPC interface.

## Available Tools

### Core IPFS Operations

| Tool Name | Description |
|-----------|-------------|
| `ipfs_add` | Add content to IPFS |
| `ipfs_cat` | Retrieve content from IPFS |
| `ipfs_ls` | List directory contents in IPFS |
| `ipfs_dht_findpeer` | Find a peer in the DHT |
| `ipfs_dht_findprovs` | Find providers for a CID in the DHT |
| `ipfs_pubsub_publish` | Publish a message to a pubsub topic |
| `ipfs_pubsub_subscribe` | Subscribe to messages on a pubsub topic |

### Mutable File System (MFS) Operations

| Tool Name | Description |
|-----------|-------------|
| `ipfs_files_ls` | List files in the MFS |
| `ipfs_files_mkdir` | Create a directory in the MFS |
| `ipfs_files_write` | Write to a file in the MFS |
| `ipfs_files_read` | Read a file from the MFS |
| `ipfs_files_rm` | Remove a file or directory from the MFS |
| `ipfs_files_stat` | Get stats for a file or directory in the MFS |
| `ipfs_files_cp` | Copy files in the MFS |
| `ipfs_files_mv` | Move files in the MFS |
| `ipfs_files_flush` | Flush the MFS |

### Virtual Filesystem Operations

| Tool Name | Description |
|-----------|-------------|
| `fs_journal_get_history` | Get the operation history for a path in the virtual filesystem |
| `fs_journal_sync` | Force synchronization between virtual filesystem and actual storage |
| `ipfs_fs_bridge_status` | Get the status of the IPFS-FS bridge |
| `ipfs_fs_bridge_sync` | Sync between IPFS and virtual filesystem |

### Storage Backend Tools

| Tool Name | Description |
|-----------|-------------|
| `init_huggingface_backend` | Initialize HuggingFace backend for the virtual filesystem |
| `init_filecoin_backend` | Initialize Filecoin backend for the virtual filesystem |
| `init_s3_backend` | Initialize S3 backend for the virtual filesystem |
| `init_storacha_backend` | Initialize Storacha backend for the virtual filesystem |
| `init_ipfs_cluster_backend` | Initialize IPFS Cluster backend for the virtual filesystem |

### Multi-Backend Management Tools

| Tool Name | Description |
|-----------|-------------|
| `multi_backend_map` | Map a backend path to a local filesystem path |
| `multi_backend_unmap` | Remove a mapping between backend and local filesystem |
| `multi_backend_list_mappings` | List all mappings between backends and local filesystem |
| `multi_backend_status` | Get status of the multi-backend filesystem |
| `multi_backend_sync` | Synchronize all mapped paths |
| `multi_backend_search` | Search indexed content |
| `multi_backend_convert_format` | Convert a file from one format to another |

## Integration with Virtual Filesystem

The tools are integrated with the virtual filesystem, allowing:

1. **Cross-Backend Operations**: Work with files across different storage backends seamlessly
2. **Filesystem Journaling**: Track operations across the virtual filesystem
3. **Synchronization**: Sync between IPFS and virtual filesystem
4. **Multiple Storage Backends**: Use different storage backends for different types of data

## How to Use

### Starting the Enhanced MCP Server

1. Run the restart script to start the MCP server with enhanced tools:

```bash
./restart_mcp_with_tools.sh
```

2. The script will:
   - Stop any running MCP servers
   - Start a new instance with the enhanced tools
   - Wait for the server to initialize

### Using the Tools

You can use the tools through the MCP server's JSON-RPC interface. Here are some examples:

#### Adding Content to IPFS

```json
{
  "method": "use_mcp_tool",
  "params": {
    "server_name": "direct-ipfs-kit-mcp",
    "tool_name": "ipfs_add",
    "arguments": {
      "content": "Hello, IPFS!",
      "pin": true
    }
  },
  "jsonrpc": "2.0",
  "id": 1
}
```

#### Reading a File from MFS

```json
{
  "method": "use_mcp_tool",
  "params": {
    "server_name": "direct-ipfs-kit-mcp",
    "tool_name": "ipfs_files_read",
    "arguments": {
      "path": "/path/to/file"
    }
  },
  "jsonrpc": "2.0",
  "id": 2
}
```

#### Initializing a Storage Backend

```json
{
  "method": "use_mcp_tool",
  "params": {
    "server_name": "direct-ipfs-kit-mcp",
    "tool_name": "init_s3_backend",
    "arguments": {
      "ctx": "s3_context",
      "name": "my_s3",
      "root_path": "/s3"
    }
  },
  "jsonrpc": "2.0",
  "id": 3
}
```

#### Mapping a Backend Path

```json
{
  "method": "use_mcp_tool",
  "params": {
    "server_name": "direct-ipfs-kit-mcp",
    "tool_name": "multi_backend_map",
    "arguments": {
      "ctx": "map_context",
      "backend_path": "/s3/data",
      "local_path": "/tmp/s3_data"
    }
  },
  "jsonrpc": "2.0",
  "id": 4
}
```

## Advanced Features

### Virtual Filesystem Journaling

The virtual filesystem maintains a journal of operations, which you can query using the `fs_journal_get_history` tool:

```json
{
  "method": "use_mcp_tool",
  "params": {
    "server_name": "direct-ipfs-kit-mcp",
    "tool_name": "fs_journal_get_history",
    "arguments": {
      "ctx": "journal_context",
      "path": "/some/path",
      "limit": 50
    }
  },
  "jsonrpc": "2.0",
  "id": 5
}
```

### IPFS-FS Bridge

The IPFS-FS bridge allows bidirectional synchronization between IPFS and the virtual filesystem:

```json
{
  "method": "use_mcp_tool",
  "params": {
    "server_name": "direct-ipfs-kit-mcp",
    "tool_name": "ipfs_fs_bridge_sync",
    "arguments": {
      "ctx": "bridge_context",
      "direction": "both"
    }
  },
  "jsonrpc": "2.0",
  "id": 6
}
```

## Implementation Details

### Tool Registry

The tools are defined in `direct_tool_registry.py` and registered with the MCP server via `patch_direct_mcp.py`.

### Patched MCP Server

The patched MCP server (`direct_mcp_server_with_tools.py`) includes all the enhanced tools, making them available through the MCP server's JSON-RPC interface.

### Integration with Virtual Filesystem

The virtual filesystem features (journaling, multi-backend support, etc.) are integrated with the MCP tools, allowing for consistent and reliable cross-backend operations.

## Conclusion

With these enhancements, IPFS Kit now provides a comprehensive set of tools for working with IPFS and various storage backends through a unified interface. The integration with the virtual filesystem allows for more sophisticated data management capabilities, including cross-backend operations, journaling, and synchronization.
