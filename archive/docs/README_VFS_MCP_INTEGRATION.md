# IPFS Kit Virtual Filesystem MCP Integration

This project enhances the existing IPFS Kit MCP (Model Context Protocol) server with comprehensive virtual filesystem capabilities. It provides a complete toolset for working with virtual files, directories, and enabling interoperability between IPFS and local filesystem operations.

## Overview

The IPFS Kit Virtual Filesystem MCP Integration adds the following key components:

1. **Filesystem Journal** - Record and track all filesystem operations
2. **IPFS-FS Bridge** - Map between IPFS content and virtual filesystem paths
3. **Multi-Backend Storage** - Support for various storage backends (IPFS, Filecoin, S3, etc.)
4. **VirtualFS Operations** - Complete virtual filesystem operations (read, write, mkdir, etc.)

## Tool Categories

The integration adds over 30 new tools to the MCP server across the following categories:

### FS Journal Tools

- `fs_journal_get_history` - Get operation history for filesystem paths
- `fs_journal_sync` - Synchronize the journal with storage backends
- `fs_journal_track` - Start tracking operations for a path
- `fs_journal_untrack` - Stop tracking operations for a path
- `fs_journal_status` - Get journal status information

### IPFS-FS Bridge Tools

- `ipfs_fs_bridge_status` - Get bridge status
- `ipfs_fs_bridge_sync` - Sync content between IPFS and filesystem
- `ipfs_fs_bridge_map` - Map an IPFS path to a filesystem path
- `ipfs_fs_bridge_unmap` - Remove a mapping
- `ipfs_fs_bridge_list_mappings` - List all mappings
- `ipfs_fs_mount` - Mount IPFS to a filesystem path
- `ipfs_fs_unmount` - Unmount IPFS from a filesystem path
- `ipfs_fs_export_to_ipfs` - Export from filesystem to IPFS
- `ipfs_fs_import_from_ipfs` - Import from IPFS to filesystem

### Storage Backend Tools

- `init_ipfs_backend` - Initialize IPFS backend
- `init_filecoin_backend` - Initialize Filecoin backend
- `init_s3_backend` - Initialize S3 backend
- `init_huggingface_backend` - Initialize HuggingFace backend
- `storage_status` - Check storage backend status
- `storage_transfer` - Transfer between storage backends

### Virtual Filesystem Operations

- `vfs_list` - List directory contents
- `vfs_read` - Read file contents
- `vfs_write` - Write to a file
- `vfs_mkdir` - Create a directory
- `vfs_rm` - Remove a file or directory
- `vfs_copy` - Copy files or directories
- `vfs_move` - Move files or directories
- `vfs_stat` - Get file or directory information

## Installation & Setup

### Prerequisites

- Python 3.8+
- IPFS daemon (recommended, but mock implementations are available)
- VS Code with Claude extension (for interacting with MCP)

### Quick Installation

For a quick all-in-one installation:

```bash
./setup_ipfs_vfs_integration.sh
```

This script will install dependencies, configure the MCP server, and set up monitoring.

### Manual Installation Steps

If you prefer to install components manually:

1. **Update the MCP server with virtual filesystem tools:**

```bash
python update_mcp_with_vfs_tools.py --all
```

2. **Install dependencies:**

```bash
./install_vfs_dependencies.sh
```

3. **Start the enhanced MCP server:**

```bash
./restart_mcp_with_vfs.sh
```

4. **Test the integration:**

```bash
python ipfs_vfs_integration_test.py
```

### Configuration

You can customize the virtual filesystem behavior by editing `vfs_config.json`. Options include:

- Setting storage backend preferences
- Configuring IPFS endpoints
- Setting up automatic tracking and synchronization
- Defining filesystem paths and journal locations

To get the current configuration through MCP, use the `vfs_get_config` tool.

## Architecture

### Component Relationships

```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│     MCP Server  │    │  Virtual Filesystem│    │  Storage Backends│
│ (direct_mcp_server.py)│◄──►│ (fs_journal.py)   │◄──►│ (IPFS, S3, etc.) │
└────────┬────────┘    └──────────────────┘    └──────────────────┘
         │                      ▲                        ▲
         │                      │                        │
         ▼                      │                        │
┌─────────────────┐             │                        │
│   MCP Tools     │             │                        │
│ (direct_tool_registry.py)│    │                        │
└────────┬────────┘             │                        │
         │                      │                        │
         ▼                      │                        │
┌─────────────────┐    ┌──────────────────┐             │
│ VFS Integration │    │   IPFS-FS Bridge │             │
│ (enhance_vfs_mcp_integration.py)│◄──►│ (fs_ipfs_bridge.py)│◄───────────┘
└─────────────────┘    └──────────────────┘
```

### Key Components

1. **Virtual Filesystem** - Maintains in-memory representation of files/directories
2. **Filesystem Journal** - Records all operations with timestamps
3. **IPFS-FS Bridge** - Handles IPFS CID mappings and import/export operations
4. **Storage Backend Manager** - Manages different storage backends

## Usage Examples

### Creating and Writing to a File

Using the MCP JSON-RPC API:

```json
{
  "jsonrpc": "2.0",
  "method": "use_tool",
  "params": {
    "tool_name": "vfs_write",
    "arguments": {
      "path": "/example/hello.txt",
      "content": "Hello, virtual filesystem!"
    }
  },
  "id": 1
}
```

### Exporting a File to IPFS

```json
{
  "jsonrpc": "2.0",
  "method": "use_tool",
  "params": {
    "tool_name": "ipfs_fs_export_to_ipfs",
    "arguments": {
      "path": "/example/hello.txt"
    }
  },
  "id": 2
}
```

### Viewing Operation History

```json
{
  "jsonrpc": "2.0",
  "method": "use_tool",
  "params": {
    "tool_name": "fs_journal_get_history",
    "arguments": {
      "path": "/example/hello.txt",
      "limit": 10
    }
  },
  "id": 3
}
```

## Advanced Usage Patterns

### Working with Multi-Backend Storage

The virtual filesystem can store content across multiple backends. Here's how to use this feature:

1. **Initialize storage backends:**

```json
{
  "jsonrpc": "2.0",
  "method": "use_tool",
  "params": {
    "tool_name": "init_s3_backend",
    "arguments": {
      "bucket_name": "my-ipfs-bucket"
    }
  },
  "id": 1
}
```

2. **Transfer content between backends:**

```json
{
  "jsonrpc": "2.0",
  "method": "use_tool",
  "params": {
    "tool_name": "storage_transfer",
    "arguments": {
      "source": "ipfs",
      "destination": "s3",
      "identifier": "QmXa12...hash"
    }
  },
  "id": 2
}
```

### Creating Complex File Structures

You can build complex directory structures:

```python
# Create directories with nested structure
await call_tool("vfs_mkdir", {"path": "/project/src/components"})
await call_tool("vfs_mkdir", {"path": "/project/src/utils"})
await call_tool("vfs_mkdir", {"path": "/project/tests"})

# Create files in those directories
await call_tool("vfs_write", {
    "path": "/project/src/components/App.js",
    "content": "function App() { return <div>Hello World</div>; }"
})

await call_tool("vfs_write", {
    "path": "/project/src/utils/helpers.js",
    "content": "export function formatDate(date) { return date.toISOString(); }"
})

# Export the entire structure to IPFS
result = await call_tool("ipfs_fs_export_to_ipfs", {
    "path": "/project"
})
project_cid = result["cid"]
print(f"Project CID: {project_cid}")
```

### Synchronizing with Local Filesystem

You can map virtual filesystem paths to local filesystem paths:

```python
import os

# Map a local directory to virtual filesystem
local_dir = os.path.expanduser("~/my_project")
vfs_dir = "/vfs/my_project"

# First add local directory to IPFS
result = await call_tool("ipfs_add", {
    "path": local_dir,
    "recursive": True
})
cid = result["cid"]

# Map IPFS CID to virtual filesystem path
await call_tool("ipfs_fs_bridge_map", {
    "ipfs_path": cid,
    "fs_path": vfs_dir
})

# Sync changes both ways
await call_tool("ipfs_fs_bridge_sync", {
    "direction": "both" 
})
```

## Benefits

1. **Persistent Virtual Filesystem** - Files persist across MCP server restarts
2. **IPFS Integration** - Seamlessly work with both local and IPFS content
3. **Operation History** - Track all file operations with timestamps
4. **Multi-Backend Support** - Store content in IPFS, Filecoin, S3, etc.
5. **Enhanced AI Capabilities** - AIs can work with virtual files and directories

## Further Extensions

Future enhancements could include:

1. **File Search** - Full-text search across virtual filesystem
2. **Version Control** - Track file versions and changes
3. **Access Controls** - Implement permissions for files/directories
4. **Collaborative Editing** - Support for multiple users editing files

## Troubleshooting

Common issues:

1. **Missing Dependencies** - Run `./install_vfs_dependencies.sh`
2. **Server Not Running** - Check `direct_mcp_server.py` is running
3. **Tools Not Registered** - Ensure `update_mcp_with_vfs_tools.py --all` was run
4. **IPFS Connection Issues** - Check IPFS daemon status

## Contributing

Contributions to enhance the virtual filesystem capabilities are welcome!

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

Please follow existing code style and add appropriate tests.
