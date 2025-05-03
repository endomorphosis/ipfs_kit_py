# IPFS Kit MCP Tool Enhancements

This documentation covers enhancements made to the MCP server for ipfs_kit_py, providing comprehensive tool coverage for all IPFS features and ensuring proper integration with virtual filesystem features.

## Overview

The enhancements include:

1. **Extended IPFS Tool Coverage** - Added tools for all core IPFS operations
2. **MFS (Mutable File System) Integration** - Complete support for IPFS virtual filesystem operations
3. **IPNS Support** - Name publishing and resolution capabilities
4. **Storage Backend Integration** - Tools for interacting with all storage backends
5. **Proper Error Handling** - Robust error handling with informative error messages

## Available Tools

The following tool categories have been added:

### Core IPFS Operations

- `ipfs_add` - Add content to IPFS
- `ipfs_cat` - Retrieve content from IPFS
- `ipfs_pin` - Pin content to local node
- `ipfs_unpin` - Unpin content from local node
- `ipfs_list_pins` - List pinned content
- `ipfs_version` - Get IPFS version information
- `ipfs_id` - Get node identity information

### MFS (Mutable File System) Operations

- `ipfs_files_ls` - List files and directories in MFS
- `ipfs_files_stat` - Get information about a file or directory in MFS
- `ipfs_files_mkdir` - Create a directory in MFS
- `ipfs_files_read` - Read content from a file in MFS
- `ipfs_files_write` - Write content to a file in MFS
- `ipfs_files_rm` - Remove a file or directory from MFS
- `ipfs_files_cp` - Copy files in MFS
- `ipfs_files_mv` - Move files in MFS
- `ipfs_files_flush` - Flush changes in MFS to IPFS

### IPNS Operations

- `ipfs_name_publish` - Publish an IPFS path to IPNS
- `ipfs_name_resolve` - Resolve an IPNS name to an IPFS path
- `ipfs_name_list` - List IPNS keys

### Advanced Operations

- `ipfs_dag_put` - Add a DAG node to IPFS
- `ipfs_dag_get` - Get a DAG node from IPFS
- `ipfs_dag_resolve` - Resolve a DAG path
- `ipfs_block_put` - Add a raw block to IPFS
- `ipfs_block_get` - Get a raw block from IPFS
- `ipfs_block_stat` - Get statistics about a block
- `ipfs_dht_findpeer` - Find a peer using DHT
- `ipfs_dht_findprovs` - Find providers for a CID using DHT
- `ipfs_swarm_peers` - List connected peers
- `ipfs_swarm_connect` - Connect to a peer
- `ipfs_swarm_disconnect` - Disconnect from a peer

### Storage Backend Operations

- `storage_transfer` - Transfer content between storage backends
- `storage_status` - Get status of storage backends
- `storage_backends` - List available storage backends
- `storage_*_to_ipfs` - Transfer from specific backend to IPFS
- `storage_*_from_ipfs` - Transfer from IPFS to specific backend

## Installation & Usage

### 1. Installation

Run the provided script to apply the enhancements:

```bash
./apply_mcp_tool_enhancements.sh
```

This script will:
- Check if the MCP server is running (and start it if not)
- Apply the enhancements to the server
- Verify that the tools are properly registered

### 2. Manual Installation

If you prefer to manually install:

1. Make sure the MCP server is running
2. Run `python3 enhance_mcp_tools.py --apply`
3. Verify with `python3 verify_mcp_enhancements.py`

### 3. How to Use the Enhanced Tools

Once installed, these tools are available through the MCP protocol. You can use them from any client that supports MCP, including Claude via the VSCode extension.

Example usage in Claude:

```
<use_mcp_tool>
<server_name>ipfs-kit-mcp</server_name>
<tool_name>ipfs_files_ls</tool_name>
<arguments>
{
  "path": "/"
}
</arguments>
</use_mcp_tool>
```

## Integration with Virtual Filesystem

The enhanced tools fully integrate with the IPFS virtual filesystem (MFS) features, allowing you to:

1. **Navigate the IPFS Filesystem**: Browse, create, and manage directories
2. **Read and Write Files**: Access and modify files in MFS
3. **Mount IPFS in Local Filesystem**: Work with IPFS content as if it were local

This integration makes it possible to treat IPFS content as a normal filesystem, while maintaining all the benefits of content addressing.

## Implementation Details

The enhancements are implemented in `enhance_mcp_tools.py`, which:

1. Enhances the MCP initialize endpoint with extended capability information
2. Creates tool functions for all IPFS operations
3. Registers these tools with the MCP server
4. Implements proper error handling and result formatting

All tools follow a consistent pattern:
- They accept properly typed arguments
- They handle errors gracefully with informative messages
- They return results in a standardized format

For debugging purposes, each tool logs its activity to `mcp_enhanced_tools.log`.

## Troubleshooting

If you encounter issues:

1. Check the log file: `mcp_enhanced_tools.log`
2. Verify the MCP server is running: `pgrep -f unified_mcp_server.py`
3. Check the server health: `curl http://localhost:9994/health`
4. Verify tool registration: `curl http://localhost:9994/initialize` (should list all tools)

## Future Extensions

The enhancement framework is designed to be extensible. To add more capabilities:

1. Add new tool definitions in `enhance_mcp_tools.py`
2. Update the capabilities list in the `enhance_mcp_initialize_endpoint` function
3. Register the new tools in the `register_mcp_tools` function
4. Run the application script again

---

For more details on IPFS Kit, see the main [README.md](./README.md).
