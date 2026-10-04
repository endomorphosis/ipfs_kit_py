# IPFS Kit MCP Integration with Virtual Filesystem

This document provides comprehensive information about the enhanced IPFS tools coverage and integration with the virtual filesystem capabilities in the `ipfs_kit_py` project.

## Overview

We've expanded the IPFS kit with:

1. **Enhanced Tool Coverage**: Added 26 IPFS-related tools to cover all IPFS functionality
2. **FS Journal System**: Added tracking of filesystem operations with history
3. **IPFS-FS Bridge**: Created bidirectional synchronization between IPFS and the filesystem
4. **MCP Server Integration**: Seamlessly integrated all tools with the MCP server

## Components

### 1. IPFS Tools Registry (`ipfs_tools_registry.py`)

A comprehensive registry of all IPFS-related tools including:
- Core IPFS operations (add, cat, etc.)
- MFS operations (files_ls, files_mkdir, etc.)
- FS Journal operations (get_history, sync)
- IPFS-FS Bridge operations (status, sync)
- Storage integrations (S3, Filecoin)
- Additional tools (WebRTC, HuggingFace, credential management)

### 2. FS Journal (`fs_journal_tools.py`)

Virtual filesystem with operation tracking capabilities:
- Records all file operations (read, write, mkdir, etc.)
- Maintains an operation history with timestamps
- Provides synchronization between virtual and actual filesystem
- Exposes async API for MCP integration

### 3. IPFS-FS Bridge (`ipfs_mcp_fs_integration.py`)

Connects IPFS with the virtual filesystem:
- Maps IPFS CIDs to filesystem paths
- Synchronizes content bidirectionally
- Intercepts IPFS controller operations to record them in the journal
- Provides integration points for the MCP server

### 4. Startup Script (`start_ipfs_mcp_with_fs.sh`)

Automates the integration process:
- Creates necessary files if missing
- Patches the MCP server for FS integration
- Validates all required components
- Starts the MCP server with all integrations

## Usage

### Starting the Server with Integration

```bash
# Make the script executable
chmod +x start_ipfs_mcp_with_fs.sh

# Run the script to start the server with all integrations
./start_ipfs_mcp_with_fs.sh
```

### Using the Tools via MCP

The tools can be accessed through the MCP server using:

```python
import requests

# Use a FS Journal tool
response = requests.post(
    "http://127.0.0.1:3000/mcpserver/use-tool",
    json={
        "server_name": "direct-ipfs-kit-mcp",
        "tool_name": "fs_journal_get_history",
        "arguments": {"path": "/some/path", "limit": 10}
    }
)
print(response.json())

# Use an IPFS-FS Bridge tool
response = requests.post(
    "http://127.0.0.1:3000/mcpserver/use-tool",
    json={
        "server_name": "direct-ipfs-kit-mcp",
        "tool_name": "ipfs_fs_bridge_sync",
        "arguments": {"path": "/some/path", "direction": "both"}
    }
)
print(response.json())
```

## Tool Categories and Capabilities

### IPFS MFS Tools
- `ipfs_files_ls`: List files in the IPFS MFS
- `ipfs_files_mkdir`: Create directories in the IPFS MFS
- `ipfs_files_write`: Write data to a file in the IPFS MFS
- `ipfs_files_read`: Read a file from the IPFS MFS
- `ipfs_files_rm`: Remove files or directories from the IPFS MFS
- `ipfs_files_stat`: Get information about a file or directory in the IPFS MFS
- `ipfs_files_cp`: Copy files within the IPFS MFS
- `ipfs_files_mv`: Move files within the IPFS MFS

### IPFS Core Tools
- `ipfs_name_publish`: Publish an IPNS name
- `ipfs_name_resolve`: Resolve an IPNS name
- `ipfs_dag_put`: Add a DAG node to IPFS
- `ipfs_dag_get`: Get a DAG node from IPFS

### FS Journal Tools
- `fs_journal_get_history`: Get the operation history for a path
- `fs_journal_sync`: Force synchronization between virtual and actual filesystem

### IPFS-FS Bridge Tools
- `ipfs_fs_bridge_status`: Get the status of the IPFS-FS bridge
- `ipfs_fs_bridge_sync`: Synchronize between IPFS and the filesystem

### Storage Tools
- `s3_store_file`: Store a file to S3
- `s3_retrieve_file`: Retrieve a file from S3
- `filecoin_store_file`: Store a file on Filecoin
- `filecoin_retrieve_deal`: Retrieve a deal from Filecoin

### Additional Tools
- `huggingface_model_load`: Load a model from HuggingFace
- `huggingface_model_inference`: Run inference on a loaded model
- `webrtc_peer_connect`: Connect to a WebRTC peer
- `webrtc_send_data`: Send data to a connected peer
- `credential_store`: Store credentials
- `credential_retrieve`: Retrieve stored credentials

## Virtual Filesystem Features

The FS Journal provides a virtual filesystem with these features:

1. **Operation Tracking**: All file operations are recorded with:
   - Operation type (read, write, mkdir, etc.)
   - Path
   - Timestamp
   - User information
   - Success/failure status
   - Additional metadata

2. **History Retrieval**: Retrieve operations history filtered by:
   - Path
   - Operation type
   - Time range
   - Limit

3. **Caching**: File contents are cached for improved performance

4. **Synchronization**: Force sync between virtual cache and filesystem

## IPFS Integration

The IPFS integration provides these capabilities:

1. **MFS-to-FS Mapping**: Maps IPFS MFS paths to filesystem paths
2. **CID Tracking**: Tracks which files are associated with which CIDs
3. **Bidirectional Sync**: Push to and pull from IPFS
4. **Operation Hooks**: Intercepts IPFS operations to record them in the journal

## Architecture

```
┌─────────────────┐       ┌─────────────────┐
│   MCP Server    │◄─────►│ IPFS Controller │
└───────┬─────────┘       └────────┬────────┘
        │                          │
        │                          │
        ▼                          ▼
┌─────────────────┐       ┌─────────────────┐
│  FS Journal &   │◄─────►│   IPFS Tools    │
│  IPFS Bridge    │       │   Registry      │
└───────┬─────────┘       └─────────────────┘
        │
        │
        ▼
┌─────────────────┐
│  Virtual File   │
│     System      │
└─────────────────┘
```

## Future Enhancements

Potential areas for further improvement:

1. **Real IPFS Node Integration**: Connect to an actual IPFS node for production use
2. **Distributed Journal**: Make the FS Journal work across multiple nodes
3. **Content Addressable Storage**: Implement CAS for the virtual filesystem
4. **Advanced Caching**: Add LRU/TTL cache policies
5. **Access Control**: Add permissions and user-based access control

## Troubleshooting

### Common Issues

1. **Tool Registration Failures**
   - Check the MCP server logs for registration errors
   - Verify the tool registry format is correct
   - Ensure the MCP server is running

2. **Integration Issues**
   - Verify all required files exist
   - Check the patch script output for errors
   - Ensure the correct paths are being used

3. **Synchronization Problems**
   - Verify file permissions
   - Check for conflicting operations
   - Inspect the journal history for failed operations

## Conclusion

This integration enhances the `ipfs_kit_py` project with comprehensive tool coverage and a powerful virtual filesystem that maintains a detailed operation history and provides seamless synchronization with IPFS.
