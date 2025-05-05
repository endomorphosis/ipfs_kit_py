# IPFS Kit and Virtual File System Integration with MCP Server

This document outlines the comprehensive integration of the IPFS Kit Python module, Virtual File System (VFS), and related components with the MCP server. This integration brings powerful distributed storage capabilities to the MCP ecosystem through a unified interface.

## Overview

The integration provides a bridge between:
- IPFS Kit Python module (`ipfs_kit_py`)
- Virtual File System (VFS) components
- MCP (Model Context Protocol) server

By connecting these components, we enable seamless access to IPFS, Filecoin, and other distributed storage systems through standard MCP tools and resources.

## Integrated Components

### 1. IPFS Kit Python Module

The `ipfs_kit_py` module provides Python bindings for interacting with IPFS and related technologies:

- IPFS core functionality: add, get, cat, pin, etc.
- Filecoin integration via Lotus
- Storacha distributed storage
- WebRTC streaming capabilities
- HuggingFace model integration

### 2. Virtual File System (VFS)

The VFS layer provides file-system-like abstractions over distributed storage:

- `fs_journal_tools`: Operation journaling and history
- `ipfs_mcp_fs_integration`: Bridge between IPFS and file systems
- `multi_backend_fs_integration`: Support for multiple storage backends
- Virtual directories and files mapped to IPFS content

### 3. MCP Server

The MCP server exposes these capabilities as tools and resources:

- Tool registry for registering function-based tools
- Resource registry for accessing data sources
- JSON-RPC interface for external communication
- SSE (Server-Sent Events) for streaming updates

## Available Tools

After integration, the following tool categories are available through the MCP server:

### IPFS Core Tools

- `ipfs_files_ls`: List files in IPFS MFS
- `ipfs_files_mkdir`: Create directories in IPFS MFS
- `ipfs_files_write`: Write data to IPFS MFS
- `ipfs_files_read`: Read data from IPFS MFS
- `ipfs_files_rm`: Remove files from IPFS MFS
- `ipfs_files_stat`: Get file information
- `ipfs_files_cp`: Copy files within IPFS MFS
- `ipfs_files_mv`: Move files within IPFS MFS

### IPNS Tools

- `ipfs_name_publish`: Publish IPNS names
- `ipfs_name_resolve`: Resolve IPNS names

### DAG Tools

- `ipfs_dag_put`: Add a DAG node to IPFS
- `ipfs_dag_get`: Get a DAG node from IPFS

### Virtual File System Tools

- `fs_journal_get_history`: Get operation history for a path
- `fs_journal_sync`: Force synchronization between VFS and storage
- `ipfs_fs_bridge_status`: Get bridge status
- `ipfs_fs_bridge_sync`: Sync IPFS and VFS

### Storage Backend Tools

- `s3_store_file`: Store a file to S3
- `s3_retrieve_file`: Retrieve a file from S3
- `filecoin_store_file`: Store a file to Filecoin
- `filecoin_retrieve_deal`: Retrieve a Filecoin deal
- `storacha_store`: Store content using Storacha
- `storacha_retrieve`: Retrieve from Storacha
- `multi_backend_add_backend`: Add storage backend
- `multi_backend_list_backends`: List storage backends

### AI Model Tools

- `huggingface_model_load`: Load a model from HuggingFace
- `huggingface_model_inference`: Run inference on a model
- `ai_model_register`: Register an AI model with metadata
- `ai_dataset_register`: Register a dataset with metadata

### Network and Communication Tools

- `webrtc_peer_connect`: Connect to a WebRTC peer
- `webrtc_send_data`: Send data to a WebRTC peer
- `ipfs_pubsub_publish`: Publish IPFS pubsub messages
- `ipfs_pubsub_subscribe`: Subscribe to IPFS pubsub
- `ipfs_dht_findpeer`: Find a peer in IPFS DHT
- `ipfs_dht_findprovs`: Find providers for a CID

### Security and Credentials

- `credential_store`: Store a service credential
- `credential_retrieve`: Retrieve a service credential

### System Tools

- `streaming_create_stream`: Create a data stream
- `streaming_publish`: Publish to a stream
- `monitoring_get_metrics`: Get monitoring metrics
- `monitoring_create_alert`: Create a monitoring alert
- `health_check`: Check system health

## Setup and Usage

### Prerequisites

- Python 3.8+
- IPFS daemon running locally or accessible
- MCP SDK installed

### Starting the Integrated Server

Use the provided script to start the server with all integrations:

```bash
./start_mcp_with_vfs_integration.sh
```

This script:
1. Stops any running instances
2. Sets up Python paths
3. Backs up configuration files
4. Runs the final integration script
5. Starts the MCP server on port 3000

### Accessing the Server

Once running, the server provides multiple endpoints:

- `http://localhost:3000/`: Home page with server information
- `http://localhost:3000/health`: Health check endpoint
- `http://localhost:3000/initialize`: Client initialization endpoint
- `http://localhost:3000/mcp`: MCP SSE connection endpoint
- `http://localhost:3000/jsonrpc`: JSON-RPC endpoint

### Using MCP Tools

You can use the integrated tools through:

1. **MCP Client SDK**: Connect to the server and call tools directly
2. **JSON-RPC**: Send JSON-RPC requests to the /jsonrpc endpoint
3. **Direct API Calls**: For some functionality, you can use REST API endpoints

Example JSON-RPC request to list files in IPFS MFS:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "run_tool",
  "params": {
    "tool": "ipfs_files_ls",
    "args": {
      "ctx": "/some/path"
    }
  }
}
```

## Integration Components

The integration consists of several key components:

### 1. `final_mcp_server.py`

The main server implementation that:
- Sets up Python paths
- Imports required modules
- Registers all tools
- Sets up endpoints
- Handles JSON-RPC requests

### 2. `enhance_vfs_mcp_integration.py`

Bridge module that connects VFS components to MCP:
- Loads VFS modules dynamically
- Registers VFS tools with the MCP server
- Handles fallbacks for missing components

### 3. `final_integration.py`

Script that verifies and sets up the integration:
- Checks for required dependencies
- Verifies IPFS Kit availability
- Checks VFS components
- Validates unified IPFS tools

### 4. `unified_ipfs_tools.py`

Module that provides a unified interface to all IPFS tools:
- Imports IPFS extensions
- Loads the IPFS Model
- Registers all IPFS tools with the MCP server

### 5. Support Scripts

- `start_mcp_with_vfs_integration.sh`: Starts the integrated server
- `stop_ipfs_mcp_server.sh`: Stops the server safely

## Architecture

The integration follows a layered architecture:

1. **Storage Layer**: IPFS, Filecoin, S3, etc.
2. **VFS Layer**: Abstraction over storage systems
3. **IPFS Kit Layer**: High-level API for IPFS operations
4. **MCP Integration Layer**: Bridges IPFS Kit with MCP
5. **MCP Server Layer**: Exposes functionality as tools and resources

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure Python paths are set correctly:
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd):$(pwd)/ipfs_kit_py
   ```

2. **IPFS Connection Issues**: Verify the IPFS daemon is running:
   ```bash
   ipfs --api=/ip4/127.0.0.1/tcp/5001 id
   ```

3. **Module Availability**: If modules are missing, install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. **Port Conflicts**: If port 3000 is in use, modify the port in start scripts or use:
   ```bash
   netstat -tuln | grep 3000
   ```

5. **Missing Module Errors**: Verify all components are installed correctly

### Logs

Check the following log files for detailed error information:

- `final_mcp_server.log`: Main server logs
- `~/.ipfs_kit/logs/`: IPFS Kit logs

## Advanced Configuration

### Custom Storage Backends

To add custom storage backends:

1. Implement the backend in a new module
2. Register it using `multi_backend_add_backend`
3. Access it through the VFS abstraction

### Tool Registration

To register additional tools:

1. Create a new module with tool implementations
2. Use the server's tool registration mechanism:
   ```python
   @server.tool(name="my_custom_tool", description="...")
   async def my_custom_tool(ctx: Context, param1: str):
       # Implementation
       return result
   ```

## References

- [MCP Server Documentation](README_MCP_SERVER.md)
- [IPFS Kit Comprehensive Features](IPFS_KIT_COMPREHENSIVE_FEATURES.md)
- [MCP IPFS Integration](README_IPFS_MCP_INTEGRATION.md)
- [Comprehensive Tool Coverage](README_COMPREHENSIVE_TOOL_COVERAGE.md)

## Contributors

This integration builds on work from multiple contributors across the IPFS, Filecoin, and MCP ecosystems.
