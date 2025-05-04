# Comprehensive IPFS MCP Tools Integration

This package provides a comprehensive set of IPFS tools that are integrated with the Model Context Protocol (MCP) server, allowing AI assistants to interact with the InterPlanetary File System (IPFS) network. The tools cover the full range of IPFS functionality and are integrated with virtual filesystem features.

## Features

The comprehensive IPFS MCP tools provide the following features:

- **Swarm Operations**: Connect to and manage peer connections in the IPFS network.
- **Mutable File System (MFS) Operations**: Work with the IPFS mutable file system to create, read, write, and manage files and directories.
- **Content Management**: Add, retrieve, and manage content in the IPFS network.
- **Pin Management**: Pin and unpin content in IPFS to ensure it's persistently stored.
- **IPNS Operations**: Publish and resolve IPNS names for dynamic content addressing.
- **DAG Operations**: Work with IPFS DAG (Directed Acyclic Graph) structures.
- **Block Operations**: Low-level operations with raw IPFS blocks.
- **DHT Operations**: Interact with the IPFS distributed hash table.
- **Node Operations**: Manage and get information about the IPFS node.
- **Filesystem Integration**: Connect the local filesystem with IPFS for seamless content management.

## Tool Categories

The tools are organized into the following categories:

### 1. ipfs_swarm
- `swarm_peers`: List connected peers in the IPFS network
- `swarm_connect`: Connect to a peer in the IPFS network
- `swarm_disconnect`: Disconnect from a peer in the IPFS network

### 2. ipfs_mfs
- `list_files`: List files in an MFS directory
- `stat_file`: Get information about a file or directory in MFS
- `make_directory`: Create a directory in MFS
- `read_file`: Read content from a file in MFS
- `write_file`: Write content to a file in MFS
- `remove_file`: Remove a file or directory from MFS

### 3. ipfs_content
- `add_content`: Add content to IPFS
- `get_content`: Get content from IPFS by CID
- `get_content_as_tar`: Download content as a TAR archive

### 4. ipfs_pins
- `pin_content`: Pin content to IPFS
- `unpin_content`: Unpin content from IPFS
- `list_pins`: List pinned content

### 5. ipfs_ipns
- `publish_name`: Publish an IPFS path to IPNS
- `resolve_name`: Resolve an IPNS name to an IPFS path

### 6. ipfs_dag
- `dag_put`: Add a DAG node to IPFS
- `dag_get`: Get a DAG node from IPFS
- `dag_resolve`: Resolve a path through a DAG structure

### 7. ipfs_block
- `block_put`: Add a raw block to IPFS
- `block_get`: Get a raw block from IPFS
- `block_stat`: Get stats about a block

### 8. ipfs_dht
- `dht_findpeer`: Find a peer using the DHT
- `dht_findprovs`: Find providers for a CID

### 9. ipfs_node
- `get_node_id`: Get node identity information
- `get_version`: Get IPFS version information
- `get_stats`: Get statistics about IPFS operations
- `check_daemon_status`: Check status of IPFS daemons
- `get_replication_status`: Get replication status for a CID

### 10. ipfs_fs_integration
- `map_ipfs_to_fs`: Map an IPFS CID to a virtual filesystem path
- `unmap_ipfs_from_fs`: Remove a mapping between IPFS and filesystem
- `sync_fs_to_ipfs`: Synchronize a filesystem directory to IPFS
- `sync_ipfs_to_fs`: Synchronize IPFS directory to filesystem
- `list_fs_ipfs_mappings`: List mappings between filesystem and IPFS
- `mount_ipfs_to_fs`: Mount IPFS to a filesystem path
- `unmount_ipfs_from_fs`: Unmount IPFS from a filesystem path

## Setup and Usage

### Prerequisites

- IPFS daemon must be installed and running
- Python 3.8 or higher
- ipfs_kit_py library installed

### Starting the MCP Server with IPFS Tools

The `start_ipfs_mcp_server.sh` script automatically:

1. Checks if the IPFS daemon is running and starts it if necessary
2. Registers all IPFS tools with the MCP server
3. Starts the MCP server on an available port (3000-3010)
4. Updates the VSCode MCP settings to use the selected port

```bash
./start_ipfs_mcp_server.sh
```

### Stopping the MCP Server

To stop the MCP server and optionally the IPFS daemon:

```bash
./stop_ipfs_mcp_server.sh
```

## Example Usage

### Adding Content to IPFS

```python
result = use_mcp_tool("direct-ipfs-kit-mcp", "add_content", {
    "content": "Hello, IPFS!",
    "filename": "hello.txt",
    "pin": True
})
# Returns: {"Hash": "QmWATWQ7fVPP2EFGu71UkfnqhYXDYH566qy47CnJDgvs8u", "Name": "hello.txt", "Size": "12"}
```

### Reading a File from MFS

```python
result = use_mcp_tool("direct-ipfs-kit-mcp", "read_file", {
    "path": "/hello.txt"
})
# Returns: {"Content": "Hello, IPFS!", "Size": 12}
```

### Filesystem Integration

```python
# Map an IPFS CID to a virtual filesystem path
result = use_mcp_tool("direct-ipfs-kit-mcp", "map_ipfs_to_fs", {
    "cid": "QmWATWQ7fVPP2EFGu71UkfnqhYXDYH566qy47CnJDgvs8u",
    "path": "/ipfs/hello.txt"
})

# Sync a local directory to IPFS
result = use_mcp_tool("direct-ipfs-kit-mcp", "sync_fs_to_ipfs", {
    "fs_path": "/local/documents",
    "ipfs_path": "/ipfs/documents"
})
```

## Architecture

The IPFS MCP tools are implemented using a layered architecture:

1. **MCP Server Layer**: Provides the JSON-RPC API for AI assistants to call
2. **Tool Registry Layer**: Defines the available tools and their parameters
3. **Controller Layer**: Implements the business logic for each tool
4. **IPFS API Layer**: Interacts with the IPFS daemon via HTTP API
5. **Filesystem Integration Layer**: Connects IPFS with the local filesystem

## Extension and Customization

The modular design allows for easy extension with additional tools:

1. Define new tool definitions in `add_comprehensive_ipfs_tools.py`
2. Implement the corresponding methods in the IPFS controller
3. Register the new tools with the MCP server using `register_ipfs_tools_with_mcp.py`

## Troubleshooting

- Ensure the IPFS daemon is running: `ipfs daemon --routing=dhtclient`
- Check the MCP server logs in `mcp_server.log`
- Verify the MCP server port in `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
- Restart the MCP server: `./restart_mcp_server.sh`
