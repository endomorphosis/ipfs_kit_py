# IPFS Kit FS Integration

This document provides an overview of the enhanced IPFS Kit Python integration with virtual filesystem features. The integration adds a layer of filesystem tracking and synchronization between IPFS and the local filesystem, expanding the capabilities of the IPFS Kit Python library.

## Components

### FS Journal

The Filesystem Journal (`FSJournal`) tracks operations performed on files and directories, maintaining a history of reads, writes, creations, deletions, and other operations. This provides an audit trail of filesystem activity and enables synchronization between different storage backends.

Key features:
- Track operations with timestamps and metadata
- Query operation history by path
- Cache file content for efficient operations
- Synchronize cached changes to disk

### IPFS-FS Bridge

The IPFS-FS Bridge (`IPFSFSBridge`) maps between IPFS paths and local filesystem paths, allowing seamless integration between IPFS and the local filesystem. This enables operations to be performed on IPFS content as if it were local, and vice versa.

Key features:
- Map IPFS paths to local filesystem paths
- Track content identifiers (CIDs) for local files
- Synchronize content between IPFS and local filesystem
- Query mapping status and relationships

## MCP Tools

The integration adds several tools to the MCP server:

| Tool Name | Description |
|-----------|-------------|
| `fs_journal_get_history` | Get the operation history for a path in the virtual filesystem |
| `fs_journal_sync` | Force synchronization between virtual filesystem and actual storage |
| `fs_journal_track` | Start tracking operations on a path in the filesystem |
| `fs_journal_untrack` | Stop tracking operations on a path in the filesystem |
| `ipfs_fs_bridge_status` | Get the status of the IPFS-FS bridge |
| `ipfs_fs_bridge_map` | Map an IPFS path to a filesystem path |
| `ipfs_fs_bridge_unmap` | Remove a mapping between IPFS and filesystem |
| `ipfs_fs_bridge_list_mappings` | List all mappings between IPFS and filesystem |
| `ipfs_fs_bridge_sync` | Sync between IPFS and filesystem |

## Installation

The FS Journal and IPFS-FS Bridge integration is included with IPFS Kit Python. To ensure all components are properly installed:

1. Clone the repository (if not already done):
   ```bash
   git clone https://github.com/example/ipfs_kit_py.git
   cd ipfs_kit_py
   ```

2. Install the package with virtual filesystem support:
   ```bash
   pip install -e .
   ```

## Usage

### Starting the MCP Server with FS Integration

Use the provided script to start the MCP server with FS Journal integration:

```bash
chmod +x start_ipfs_mcp_with_fs.sh
./start_ipfs_mcp_with_fs.sh
```

### Registering the Tools (if needed)

If tools aren't automatically registered, use the registration script:

```bash
python register_integration_tools.py
```

### Using the FS Journal

The FS Journal can be used to track operations on files and directories:

```python
from fs_journal_tools import FSJournal, FSOperation, FSOperationType

# Initialize the journal
journal = FSJournal("/path/to/base/dir")

# Track a directory
journal.track_path("/path/to/track")

# Record an operation
journal.record_operation(FSOperation(
    operation_type=FSOperationType.WRITE,
    path="/path/to/file.txt",
    metadata={"size": 1024}
))

# Get operation history
history = journal.get_history("/path/to/file.txt")
print(f"Found {len(history)} operations")
```

### Using the IPFS-FS Bridge

The IPFS-FS Bridge can be used to map between IPFS and the local filesystem:

```python
from fs_journal_tools import FSJournal, IPFSFSBridge

# Initialize the journal and bridge
journal = FSJournal("/path/to/base/dir")
bridge = IPFSFSBridge(journal)

# Map an IPFS path to a local path
bridge.map_path("/ipfs/QmExample", "/path/to/local/file.txt")

# Get bridge status
status = bridge.get_status()
print(f"Bridge has {status['mappings_count']} mappings")
```

### Using MCP Tools

FS Journal and IPFS-FS Bridge tools can be used through the MCP server API:

```python
import requests

# Get operation history
response = requests.post("http://127.0.0.1:3000/mcpserver/use-tool", json={
    "server_name": "direct-ipfs-kit-mcp",
    "tool_name": "fs_journal_get_history",
    "arguments": {
        "ctx": "test",
        "path": "/path/to/file.txt",
        "limit": 10
    }
})
history = response.json()
```

## Advanced Features

### Synchronization

Synchronize changes between the virtual filesystem and disk:

```python
# Sync all cached changes to disk
result = journal.sync_to_disk()
print(f"Synced {result['synced_files']} files")

# Sync a specific path
result = journal.sync_to_disk("/path/to/specific/file.txt")
```

### Tracking Control

Control which paths are tracked:

```python
# Start tracking a path
journal.track_path("/path/to/track")

# Stop tracking a path
journal.untrack_path("/path/to/untrack")

# Check if a path is being tracked
is_tracked = journal.is_tracked("/path/to/check")
```

## Integration with IPFS MFS

The integration works seamlessly with IPFS Mutable File System (MFS) operations:

```python
# Map an IPFS MFS path to a local path
bridge.map_path("/my-files/documents", "/local/documents")

# List mappings
mappings = bridge.list_mappings()
```

## Troubleshooting

If you encounter issues with the integration:

1. Check the MCP server logs:
   ```bash
   tail -f mcp_server.log
   ```

2. Verify the server is running:
   ```bash
   curl http://127.0.0.1:3000/api/v0/health
   ```

3. Run the verification script:
   ```bash
   python verify_integration_tools.py
   ```

4. If tools aren't registered correctly, try restarting the server:
   ```bash
   ./stop_ipfs_enhanced_mcp.sh
   ./start_ipfs_mcp_with_fs.sh
   ```

## Contributing

Contributions to improve the FS Journal and IPFS-FS Bridge integration are welcome. Please see the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
