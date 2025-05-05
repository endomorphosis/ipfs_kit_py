# IPFS Kit Enhanced Tool Coverage

This document provides comprehensive information on the enhanced tool coverage for IPFS Kit, including integration with the virtual filesystem and expanded functionality across multiple storage backends.

## Overview

The enhanced tool coverage extends IPFS Kit with additional MCP tools that provide access to a wider range of IPFS features and integration with multiple storage backends. These enhancements include:

1. Core IPFS features expansion
2. IPFS Cluster integration
3. Lassie content retrieval capabilities
4. AI/ML model management
5. Multi-backend storage support
6. Seamless virtual filesystem integration
7. Monitoring and metrics tools

## New Tools Added

### IPFS Core Advanced Features

| Tool Name | Description |
|-----------|-------------|
| `ipfs_pubsub_publish` | Publish messages to an IPFS pubsub topic |
| `ipfs_pubsub_subscribe` | Subscribe to messages on an IPFS pubsub topic |
| `ipfs_dht_findpeer` | Find a peer in the IPFS DHT |
| `ipfs_dht_findprovs` | Find providers for a given CID in the IPFS DHT |

### IPFS Cluster Integration

| Tool Name | Description |
|-----------|-------------|
| `ipfs_cluster_pin` | Pin a CID across the IPFS cluster |
| `ipfs_cluster_status` | Get the status of a CID in the IPFS cluster |
| `ipfs_cluster_peers` | List peers in the IPFS cluster |

### Lassie Content Retrieval

| Tool Name | Description |
|-----------|-------------|
| `lassie_fetch` | Fetch content using Lassie content retrieval from Filecoin and IPFS |
| `lassie_fetch_with_providers` | Fetch content using Lassie with specific providers |

### AI/ML Model Integration

| Tool Name | Description |
|-----------|-------------|
| `ai_model_register` | Register an AI model with IPFS and metadata |
| `ai_dataset_register` | Register a dataset with IPFS and metadata |

### Search Tools

| Tool Name | Description |
|-----------|-------------|
| `search_content` | Search indexed content across IPFS and storage backends |

### Storacha Integration

| Tool Name | Description |
|-----------|-------------|
| `storacha_store` | Store content using Storacha distributed storage |
| `storacha_retrieve` | Retrieve content from Storacha distributed storage |

### Multi-Backend Management

| Tool Name | Description |
|-----------|-------------|
| `multi_backend_add_backend` | Add a new storage backend to the multi-backend filesystem |
| `multi_backend_list_backends` | List all configured storage backends |

### Streaming Tools

| Tool Name | Description |
|-----------|-------------|
| `streaming_create_stream` | Create a new data stream |
| `streaming_publish` | Publish data to a stream |

### Monitoring and Metrics

| Tool Name | Description |
|-----------|-------------|
| `monitoring_get_metrics` | Get monitoring metrics |
| `monitoring_create_alert` | Create a monitoring alert |

## Virtual Filesystem Integration

The tools have been integrated with the virtual filesystem, enabling seamless operations between filesystem actions and IPFS operations. This integration provides:

1. Automatic synchronization between filesystem operations and IPFS operations
2. Event-based triggers for filesystem changes
3. Coordinated access to multiple storage backends through a unified filesystem interface

### Filesystem Operation Mapping

| Filesystem Operation | IPFS Operation | Description |
|----------------------|----------------|-------------|
| `write` | `ipfs_files_write` | When a file is created or modified |
| `read` | `ipfs_files_read` | When a file is read |
| `mkdir` | `ipfs_files_mkdir` | When a directory is created |
| `remove` | `ipfs_files_rm` | When a file or directory is removed |
| `copy` | `ipfs_files_cp` | When a file or directory is copied |
| `move` | `ipfs_files_mv` | When a file or directory is moved |

## Multi-Backend Support

The enhanced tools provide integration with multiple storage backends:

| Backend | Mount Point | Description |
|---------|-------------|-------------|
| IPFS | `/ipfs` | InterPlanetary File System |
| Filecoin | `/fil` | Decentralized storage network |
| S3 | `/s3` | Amazon S3 compatible storage |
| Storacha | `/storacha` | Distributed storage system |
| HuggingFace | `/hf` | AI model repository |
| IPFS Cluster | `/cluster` | Collaborative IPFS pinning |

## Getting Started

### Installation

The enhanced tools are already integrated into your existing IPFS Kit setup. To ensure everything is properly set up, run:

```bash
python enhance_tool_coverage.py
```

This script adds the new tools to the registry and creates their implementations.

### Integrating with Virtual Filesystem

To integrate the enhanced tools with the virtual filesystem, run:

```bash
python integrate_fs_with_tools.py
```

This script:
1. Registers filesystem event handlers with the IPFS tools
2. Sets up the multi-backend integration
3. Registers all tools with the MCP server
4. Creates restart and verification scripts

### Starting the MCP Server with Enhanced Tools

To start the MCP server with the enhanced tools and filesystem integration, run:

```bash
./restart_mcp_with_tools.sh
```

### Verifying the Integration

To verify that the integration is working correctly, run:

```bash
python verify_fs_tool_integration.py
```

This script tests:
1. Basic filesystem operations through IPFS
2. Multi-backend operations
3. Enhanced tool functionality

## Usage Examples

### Example 1: Using IPFS MFS with Virtual Filesystem

```python
# Create a directory in the virtual filesystem
result = call_mcp_method("ipfs_files_mkdir", {"path": "/mydir"})

# Write a file to the virtual filesystem
result = call_mcp_method("ipfs_files_write", {
    "path": "/mydir/myfile.txt",
    "content": "Hello, IPFS!"
})

# Read the file
result = call_mcp_method("ipfs_files_read", {"path": "/mydir/myfile.txt"})
print(result)  # Output: Hello, IPFS!
```

### Example 2: Using Multi-Backend Storage

```python
# Store a file on Filecoin
result = call_mcp_method("filecoin_store_file", {
    "local_path": "/path/to/local/file.txt",
    "replication": 3
})

# Retrieve a file from Storacha
result = call_mcp_method("storacha_retrieve", {
    "content_id": "storacha-content-id",
    "output_path": "/path/to/output/file.txt"
})
```

### Example 3: Working with IPFS PubSub

```python
# Publish a message to a topic
result = call_mcp_method("ipfs_pubsub_publish", {
    "topic": "my-topic",
    "message": "Hello, PubSub!"
})

# Subscribe to a topic (with 30-second timeout)
result = call_mcp_method("ipfs_pubsub_subscribe", {
    "topic": "my-topic",
    "timeout": 30
})
```

### Example 4: Managing AI Models

```python
# Register an AI model
result = call_mcp_method("ai_model_register", {
    "model_path": "/path/to/model",
    "model_name": "My Image Classifier",
    "model_type": "classification",
    "version": "1.0.0",
    "metadata": {
        "accuracy": 0.95,
        "framework": "PyTorch"
    }
})
```

## Troubleshooting

### Common Issues

1. **Tool not found**: Ensure that the MCP server has been restarted after adding the new tools.
2. **Filesystem integration not working**: Check that the `ipfs_mcp_fs_integration.py` and `fs_journal_tools.py` files exist and are properly configured.
3. **Backend not available**: Some backends (like Filecoin or Storacha) may require additional setup or credentials.

### Diagnostic Steps

1. Check the MCP server logs for errors
2. Verify that the tools are registered by using the `/health` endpoint
3. Run the verification script to check specific tool functionality

## Architecture

The enhanced tool coverage architecture consists of several key components:

1. **Tool Registry**: Defines the available tools and their schemas
2. **Tool Implementations**: Provides the actual implementation for each tool
3. **FS Integration**: Connects filesystem operations with IPFS operations
4. **Multi-Backend Manager**: Coordinates access to different storage backends
5. **MCP Server**: Exposes the tools via JSON-RPC interface

### Component Diagram

```
                  ┌─────────────────┐
                  │                 │
                  │    MCP Server   │
                  │                 │
                  └────────┬────────┘
                           │
                           ▼
            ┌─────────────────────────────┐
            │                             │
            │     Tool Registry & Impl    │
            │                             │
            └───┬─────────────┬─────────┬─┘
                │             │         │
                ▼             ▼         ▼
┌───────────────────┐ ┌─────────────┐ ┌────────────────┐
│                   │ │             │ │                │
│ FS Integration    │ │  IPFS Core  │ │ Storage        │
│                   │ │             │ │ Backends       │
└─────────┬─────────┘ └──────┬──────┘ └────────┬───────┘
          │                  │                 │
          │                  ▼                 │
          │         ┌─────────────────┐        │
          └────────►│                 │◄───────┘
                    │ Virtual FS &    │
                    │ Object Storage  │
                    │                 │
                    └─────────────────┘
```

## Contributing

To extend the tool coverage further:

1. Add new tool definitions to `ipfs_tools_registry.py`
2. Implement the tool functionality in `enhanced_tool_implementations.py`
3. If necessary, update the filesystem integration in `integrate_fs_with_tools.py`
4. Update this documentation with the new tool information
5. Run the verification script to ensure proper functionality

## License

This project is licensed under the same license as IPFS Kit.
