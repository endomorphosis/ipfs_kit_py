# Aria2 Integration for IPFS Kit

This document describes the Aria2 integration with IPFS Kit and the MCP Server.

## Overview

The Aria2 integration adds high-performance download capabilities to IPFS Kit through the [Aria2](https://aria2.github.io/) download utility. Aria2 is a lightweight, multi-protocol & multi-source command-line download utility that supports HTTP/HTTPS, FTP, SFTP, BitTorrent, and Metalink.

## Features

- High-speed downloads with multi-connection and multi-source support
- Support for HTTP/HTTPS, FTP, SFTP, BitTorrent, and Metalink
- Integration with the MCP server for RESTful API access
- Caching of download status and statistics for improved performance
- Credential management for secure RPC access
- Comprehensive error handling and operation tracking

## Components

The integration consists of three main components:

1. **aria2_kit.py**: Core implementation that interacts with the Aria2 daemon via JSON-RPC
2. **models/aria2_model.py**: MCP model implementation with caching and operation tracking
3. **controllers/aria2_controller.py**: FastAPI controller for RESTful API access

## API Endpoints

When integrated with the MCP server, the following RESTful API endpoints are available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/aria2/health` | GET | Check Aria2 health status |
| `/aria2/version` | GET | Get Aria2 version information |
| `/aria2/add` | POST | Add a download by URI |
| `/aria2/add-torrent` | POST | Add a download by torrent file |
| `/aria2/add-metalink` | POST | Add a download by metalink file |
| `/aria2/create-metalink` | POST | Create a metalink file |
| `/aria2/remove` | POST | Remove a download |
| `/aria2/pause` | POST | Pause a download |
| `/aria2/resume` | POST | Resume a paused download |
| `/aria2/status/{gid}` | GET | Get download status |
| `/aria2/list` | GET | List all downloads |
| `/aria2/purge` | POST | Purge completed/error/removed downloads |
| `/aria2/global-stats` | GET | Get global download statistics |
| `/aria2/daemon/start` | POST | Start the Aria2 daemon |
| `/aria2/daemon/stop` | POST | Stop the Aria2 daemon |

## Usage Examples

### Starting the Aria2 Daemon

```python
from ipfs_kit_py.aria2_kit import aria2_kit

# Initialize aria2_kit
kit = aria2_kit()

# Start the daemon with custom options
result = kit.start_daemon(
    rpc_secret="your_secret",
    rpc_listen_port=6800,
    dir="/path/to/downloads",
    continue=True,
    max_concurrent_downloads=5
)

if result["success"]:
    print("Aria2 daemon started successfully")
else:
    print(f"Failed to start Aria2 daemon: {result['error']}")
```

### Adding a Download by URI

```python
from ipfs_kit_py.aria2_kit import aria2_kit

# Initialize aria2_kit
kit = aria2_kit()

# Add a download
result = kit.add_uri(
    uris="https://example.com/file.zip",
    filename="file.zip",
    options={
        "dir": "/path/to/downloads",
        "split": 8,  # Use 8 connections
        "max-connection-per-server": 8
    }
)

if result["success"]:
    gid = result["gid"]
    print(f"Download started with GID: {gid}")
else:
    print(f"Failed to start download: {result['error']}")
```

### Checking Download Status

```python
from ipfs_kit_py.aria2_kit import aria2_kit

# Initialize aria2_kit
kit = aria2_kit()

# Check download status
result = kit.get_status(gid="2089b05ecca3d829")

if result["success"]:
    print(f"Status: {result['state']}")
    print(f"Progress: {result['completed_length']}/{result['total_length']}")
    print(f"Download speed: {result['download_speed']} bytes/sec")
else:
    print(f"Failed to get status: {result['error']}")
```

### Using the MCP Server API

When the MCP server is running, you can use the RESTful API:

```bash
# Add a download
curl -X POST http://localhost:8000/mcp/aria2/add \
  -H "Content-Type: application/json" \
  -d '{"uris": "https://example.com/file.zip", "filename": "file.zip", "options": {"dir": "/tmp"}}'

# Check download status
curl http://localhost:8000/mcp/aria2/status/2089b05ecca3d829

# List all downloads
curl http://localhost:8000/mcp/aria2/list

# Pause a download
curl -X POST http://localhost:8000/mcp/aria2/pause \
  -H "Content-Type: application/json" \
  -d '{"gid": "2089b05ecca3d829"}'
```

## Testing the Integration

1. Start the Aria2 daemon:

```bash
python start_aria2_daemon.py
```

2. Run the integration tests:

```bash
python test_mcp_aria2.py
```

For manual testing with a temporary server:

```bash
python test_mcp_aria2_manual.py
```

## Configuration

The Aria2 integration can be configured through the following methods:

1. **RPC credentials**: Stored securely in the credential manager
   ```python
   from ipfs_kit_py.credential_manager import CredentialManager
   
   # Initialize the credential manager
   cm = CredentialManager()
   
   # Store Aria2 credentials
   cm.add_credential("aria2", "default", {
       "rpc_secret": "your_secret",
       "rpc_url": "http://localhost:6800/jsonrpc"
   })
   ```

2. **Resources parameter**: Passed when initializing aria2_kit
   ```python
   from ipfs_kit_py.aria2_kit import aria2_kit
   
   # Initialize with custom resources
   kit = aria2_kit(resources={
       "rpc_secret": "your_secret",
       "rpc_url": "http://localhost:6800/jsonrpc"
   })
   ```

3. **Server options**: When starting the daemon
   ```python
   kit.start_daemon(
       rpc_secret="your_secret",
       rpc_listen_port=6800,
       dir="/path/to/downloads",
       continue=True,
       max_concurrent_downloads=5
   )
   ```

## Requirements

- Python 3.8+
- Aria2 1.30+ (installed via package manager or `install_aria2.py`)
- requests
- pydantic (for the MCP server integration)
- fastapi (for the MCP server integration)

## Installation

1. Install Aria2:
   ```bash
   # On Debian/Ubuntu
   apt-get install aria2
   
   # On macOS
   brew install aria2
   
   # On Windows
   choco install aria2
   
   # Or use the provided installer
   python install_aria2.py
   ```

2. Install the IPFS Kit package with Aria2 support:
   ```bash
   pip install ipfs_kit
   ```