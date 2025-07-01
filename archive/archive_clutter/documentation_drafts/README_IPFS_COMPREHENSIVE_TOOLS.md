# IPFS Kit Comprehensive Tools Integration

This document provides an overview of the comprehensive IPFS tools integration with the MCP server and how the existing tools have been integrated with the virtual filesystem features.

## Table of Contents
- [Overview](#overview)
- [Integrated Tools](#integrated-tools)
  - [IPFS MCP Tools](#ipfs-mcp-tools)
  - [Filesystem Journal Tools](#filesystem-journal-tools)
  - [Multi-Backend Filesystem Integration](#multi-backend-filesystem-integration)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)

## Overview

The IPFS Kit Python project now features comprehensive integration between IPFS core functionality and the MCP (Model Context Protocol) server infrastructure. This integration includes:

1. **IPFS Core Tools** - Basic IPFS operations (add, cat, pin, etc.)
2. **Filesystem Journal** - Tracking and logging filesystem changes
3. **Multi-Backend Storage** - Unified interface for IPFS, Filecoin, S3 and other storage backends
4. **Virtual Filesystem Bridge** - Integration with virtual filesystem features

All these tools are made available via the MCP server, allowing AI models like Claude to interact with IPFS, filesystem journaling, and multi-backend storage directly.

## Integrated Tools

### IPFS MCP Tools

The following IPFS tools are now available through the MCP server:

| Tool Name | Description |
|-----------|-------------|
| `ipfs_add` | Add content to IPFS |
| `ipfs_cat` | Retrieve content from IPFS |
| `ipfs_ls` | List directory contents in IPFS |
| `ipfs_pin` | Pin content in IPFS |
| `ipfs_unpin` | Unpin content from IPFS |
| `ipfs_pin_ls` | List pinned content |
| `ipfs_stat` | Get stats about IPFS objects |
| `ipfs_dag_get` | Get data from an IPFS DAG node |
| `ipfs_dag_put` | Store data as an IPFS DAG node |
| `ipfs_name_publish` | Publish to IPNS |
| `ipfs_name_resolve` | Resolve IPNS names |
| `ipfs_files_cp` | Copy files in MFS |
| `ipfs_files_ls` | List files in MFS |
| `ipfs_files_mkdir` | Create directory in MFS |
| `ipfs_files_rm` | Remove files from MFS |
| `ipfs_files_stat` | Get stats about MFS files |
| `ipfs_files_write` | Write to a file in MFS |
| `ipfs_files_read` | Read from a file in MFS |

### Filesystem Journal Tools

The filesystem journal tools track and log changes to your files and directories:

| Tool Name | Description |
|-----------|-------------|
| `fs_journal_track` | Start tracking a file or directory for changes |
| `fs_journal_untrack` | Stop tracking a file or directory |
| `fs_journal_list_tracked` | List all tracked files and directories |
| `fs_journal_get_history` | Get history of operations for a path |
| `fs_journal_sync` | Sync the journal with the filesystem |

### Multi-Backend Filesystem Integration

The multi-backend filesystem provides a unified interface for storing and retrieving data across multiple storage backends:

| Tool Name | Description |
|-----------|-------------|
| `mbfs_register_backend` | Register a storage backend |
| `mbfs_get_backend` | Get information about a backend |
| `mbfs_list_backends` | List all registered backends |
| `mbfs_store` | Store content using a storage backend |
| `mbfs_retrieve` | Retrieve content from a storage backend |
| `mbfs_delete` | Delete content from a storage backend |
| `mbfs_list` | List content in a storage backend |


### Advanced IPFS Tools

| Tool Name | Description |
|-----------|-------------|
| `ipfs_dag_get` | Get data from an IPFS DAG node |
| `ipfs_dag_put` | Store data as an IPFS DAG node |
| `ipfs_dht_findpeer` | Find a peer in the DHT |
| `ipfs_dht_findprovs` | Find providers for a CID |
| `ipfs_dht_get` | Get a value from the DHT |
| `ipfs_dht_put` | Put a value in the DHT |
| `ipfs_name_publish` | Publish to IPNS |
| `ipfs_name_resolve` | Resolve IPNS names |

### LibP2P Tools

| Tool Name | Description |
|-----------|-------------|
| `libp2p_connect` | Connect to a peer |
| `libp2p_disconnect` | Disconnect from a peer |
| `libp2p_findpeer` | Find a peer |
| `libp2p_peers` | List connected peers |
| `libp2p_pubsub_publish` | Publish a message to a topic |
| `libp2p_pubsub_subscribe` | Subscribe to a topic |

### Aria2 Download Tools

| Tool Name | Description |
|-----------|-------------|
| `aria2_add_uri` | Add a download URI |
| `aria2_remove` | Remove a download |
| `aria2_pause` | Pause a download |
| `aria2_resume` | Resume a download |
| `aria2_list` | List all downloads |
| `aria2_get_status` | Get download status |

### WebRTC Tools

| Tool Name | Description |
|-----------|-------------|
| `webrtc_create_offer` | Create a WebRTC offer |
| `webrtc_answer` | Answer a WebRTC offer |
| `webrtc_send` | Send data over WebRTC |
| `webrtc_receive` | Receive data over WebRTC |
| `webrtc_video_start` | Start video stream |
| `webrtc_video_stop` | Stop video stream |

### Credential Management Tools

| Tool Name | Description |
|-----------|-------------|
| `credential_add` | Add a credential |
| `credential_remove` | Remove a credential |
| `credential_list` | List credentials |
| `credential_verify` | Verify a credential |


### Advanced IPFS Tools

| Tool Name | Description |
|-----------|-------------|
| `ipfs_dag_get` | Get data from an IPFS DAG node |
| `ipfs_dag_put` | Store data as an IPFS DAG node |
| `ipfs_dht_findpeer` | Find a peer in the DHT |
| `ipfs_dht_findprovs` | Find providers for a CID |
| `ipfs_dht_get` | Get a value from the DHT |
| `ipfs_dht_put` | Put a value in the DHT |
| `ipfs_name_publish` | Publish to IPNS |
| `ipfs_name_resolve` | Resolve IPNS names |

### LibP2P Tools

| Tool Name | Description |
|-----------|-------------|
| `libp2p_connect` | Connect to a peer |
| `libp2p_disconnect` | Disconnect from a peer |
| `libp2p_findpeer` | Find a peer |
| `libp2p_peers` | List connected peers |
| `libp2p_pubsub_publish` | Publish a message to a topic |
| `libp2p_pubsub_subscribe` | Subscribe to a topic |

### Aria2 Download Tools

| Tool Name | Description |
|-----------|-------------|
| `aria2_add_uri` | Add a download URI |
| `aria2_remove` | Remove a download |
| `aria2_pause` | Pause a download |
| `aria2_resume` | Resume a download |
| `aria2_list` | List all downloads |
| `aria2_get_status` | Get download status |

### WebRTC Tools

| Tool Name | Description |
|-----------|-------------|
| `webrtc_create_offer` | Create a WebRTC offer |
| `webrtc_answer` | Answer a WebRTC offer |
| `webrtc_send` | Send data over WebRTC |
| `webrtc_receive` | Receive data over WebRTC |
| `webrtc_video_start` | Start video stream |
| `webrtc_video_stop` | Stop video stream |

### Credential Management Tools

| Tool Name | Description |
|-----------|-------------|
| `credential_add` | Add a credential |
| `credential_remove` | Remove a credential |
| `credential_list` | List credentials |
| `credential_verify` | Verify a credential |


### Advanced IPFS Tools

| Tool Name | Description |
|-----------|-------------|
| `ipfs_dag_get` | Get data from an IPFS DAG node |
| `ipfs_dag_put` | Store data as an IPFS DAG node |
| `ipfs_dht_findpeer` | Find a peer in the DHT |
| `ipfs_dht_findprovs` | Find providers for a CID |
| `ipfs_dht_get` | Get a value from the DHT |
| `ipfs_dht_put` | Put a value in the DHT |
| `ipfs_name_publish` | Publish to IPNS |
| `ipfs_name_resolve` | Resolve IPNS names |

### LibP2P Tools

| Tool Name | Description |
|-----------|-------------|
| `libp2p_connect` | Connect to a peer |
| `libp2p_disconnect` | Disconnect from a peer |
| `libp2p_findpeer` | Find a peer |
| `libp2p_peers` | List connected peers |
| `libp2p_pubsub_publish` | Publish a message to a topic |
| `libp2p_pubsub_subscribe` | Subscribe to a topic |

### Aria2 Download Tools

| Tool Name | Description |
|-----------|-------------|
| `aria2_add_uri` | Add a download URI |
| `aria2_remove` | Remove a download |
| `aria2_pause` | Pause a download |
| `aria2_resume` | Resume a download |
| `aria2_list` | List all downloads |
| `aria2_get_status` | Get download status |

### WebRTC Tools

| Tool Name | Description |
|-----------|-------------|
| `webrtc_create_offer` | Create a WebRTC offer |
| `webrtc_answer` | Answer a WebRTC offer |
| `webrtc_send` | Send data over WebRTC |
| `webrtc_receive` | Receive data over WebRTC |
| `webrtc_video_start` | Start video stream |
| `webrtc_video_stop` | Stop video stream |

### Credential Management Tools

| Tool Name | Description |
|-----------|-------------|
| `credential_add` | Add a credential |
| `credential_remove` | Remove a credential |
| `credential_list` | List credentials |
| `credential_verify` | Verify a credential |


### Advanced IPFS Tools

| Tool Name | Description |
|-----------|-------------|
| `ipfs_dag_get` | Get data from an IPFS DAG node |
| `ipfs_dag_put` | Store data as an IPFS DAG node |
| `ipfs_dht_findpeer` | Find a peer in the DHT |
| `ipfs_dht_findprovs` | Find providers for a CID |
| `ipfs_dht_get` | Get a value from the DHT |
| `ipfs_dht_put` | Put a value in the DHT |
| `ipfs_name_publish` | Publish to IPNS |
| `ipfs_name_resolve` | Resolve IPNS names |

### LibP2P Tools

| Tool Name | Description |
|-----------|-------------|
| `libp2p_connect` | Connect to a peer |
| `libp2p_disconnect` | Disconnect from a peer |
| `libp2p_findpeer` | Find a peer |
| `libp2p_peers` | List connected peers |
| `libp2p_pubsub_publish` | Publish a message to a topic |
| `libp2p_pubsub_subscribe` | Subscribe to a topic |

### Aria2 Download Tools

| Tool Name | Description |
|-----------|-------------|
| `aria2_add_uri` | Add a download URI |
| `aria2_remove` | Remove a download |
| `aria2_pause` | Pause a download |
| `aria2_resume` | Resume a download |
| `aria2_list` | List all downloads |
| `aria2_get_status` | Get download status |

### WebRTC Tools

| Tool Name | Description |
|-----------|-------------|
| `webrtc_create_offer` | Create a WebRTC offer |
| `webrtc_answer` | Answer a WebRTC offer |
| `webrtc_send` | Send data over WebRTC |
| `webrtc_receive` | Receive data over WebRTC |
| `webrtc_video_start` | Start video stream |
| `webrtc_video_stop` | Stop video stream |

### Credential Management Tools

| Tool Name | Description |
|-----------|-------------|
| `credential_add` | Add a credential |
| `credential_remove` | Remove a credential |
| `credential_list` | List credentials |
| `credential_verify` | Verify a credential |

## Architecture

The integration architecture follows these key principles:

1. **Modularity** - Each tool set is implemented as a separate module that can be loaded independently
2. **Error Resilience** - All tools handle errors gracefully and provide clear error messages
3. **Consistent Interface** - All tools follow a consistent interface pattern
4. **Virtual Filesystem Integration** - Tools are integrated with the virtual filesystem features

The architecture diagram below shows how the components interact:





```
+---------------------+        +---------------------+
|      MCP Server     |<------>|   IPFS MCP Tools    |
+---------------------+        +---------------------+
          ^                             ^
          |                             |
          v                             v
+---------------------+        +---------------------+
| Filesystem Journal  |<------>|  Multi-Backend FS   |
+---------------------+        +---------------------+
          ^                             ^
          |                             |
          v                             v
+---------------------+        +---------------------+
|   Virtual FS API    |<------>|     IPFS Daemon     |
+---------------------+        +---------------------+
          ^                             ^
          |                             |
          v                             v
+---------------------+        +---------------------+
|   LibP2P Network    |<------>|   WebRTC / Aria2    |
+---------------------+        +---------------------+
```





## Installation

The installation and setup process has been simplified with the `patch_direct_mcp_server.py` script, which integrates all tools with the MCP server.

### Prerequisites

- Python 3.7+
- IPFS daemon installed and running
- Direct MCP server setup

### Setup Steps

1. Make sure all required files are present:
   - `ipfs_mcp_tools.py`
   - `fs_journal_tools.py`
   - `multi_backend_fs_integration.py`
   - `direct_mcp_server.py`

2. Run the patch script:
   ```bash
   python3 patch_direct_mcp_server.py
   ```

3. Verify your installation:
   ```bash
   python3 verify_ipfs_tools.py
   ```

4. Start the MCP server with IPFS tools:
   ```bash
   ./start_ipfs_mcp_with_tools.sh
   ```

## Usage Examples

### Adding Content to IPFS

```python
# Store a text file in IPFS
result = await ipfs_add(
    content="Hello, IPFS!",
    filename="hello.txt"
)
cid = result["hash"]
print(f"Content added to IPFS with CID: {cid}")
```

### Using the Filesystem Journal

```python
# Start tracking a directory
result = await fs_journal_track(
    path="/path/to/watch",
    recursive=True
)
print(f"Tracking {result['files_tracked']} files and {result['directories_tracked']} directories")

# Sync to detect changes
changes = await fs_journal_sync()
for change in changes["changes"]:
    print(f"{change['path']} was {change['change']}")
```

### Multi-Backend Storage

```python
# Register S3 backend
await mbfs_register_backend(
    backend_id="my-s3",
    backend_type="s3",
    config={
        "bucket": "my-bucket",
        "region": "us-east-1"
    }
)

# Store content using IPFS backend
result = await mbfs_store(
    content="Multi-backend storage example",
    path="/examples/multi-backend.txt",
    backend_id="ipfs-default"
)
ipfs_uri = result["uri"]

# Retrieve the content
data = await mbfs_retrieve(uri=ipfs_uri)
print(f"Retrieved content: {data}")
```

## Troubleshooting

### IPFS Daemon Not Running

If the IPFS daemon is not running, you'll see errors when trying to use IPFS tools. Start the daemon with:

```bash
ipfs daemon
```

### Import Errors

If you see import errors for modules like `ipfshttpclient` or `boto3`, install the required dependencies:

```bash
pip install ipfshttpclient boto3
```

### MCP Server Connection Issues

If the MCP server fails to start or you can't connect to it:

1. Check if another instance is already running
2. Verify the port settings in the direct_mcp_server.py file
3. Check the logs for error messages

For more troubleshooting help, run:

```bash
python3 verify_ipfs_tools.py
