# MCP Server CLI Controller Integration

This document describes the integration of the CLI functionality into the MCP (Model-Controller-Persistence) server for the ipfs_kit_py project.

## Overview

The CLI Controller provides an HTTP API interface to all the CLI tool functionality of ipfs_kit_py. This allows users to execute CLI commands through the MCP server's REST API, enabling remote management and automation of IPFS operations.

## Features

The CLI Controller provides the following features:

- **Command Execution**: Execute any supported CLI command remotely
- **Content Management**: Add, retrieve, pin, and unpin content
- **Peer Management**: Connect to peers and list connected peers
- **Filesystem Operations**: Check if files exist, list directory contents
- **WAL Integration**: Manage and monitor the Write-Ahead Log (WAL) system
- **Version Information**: Get version details for the system components

## Endpoints

The CLI Controller exposes the following endpoints:

### Core Commands

- `POST /cli/execute` - Execute a CLI command with arguments
- `GET /cli/version` - Get version information

### Content Management

- `POST /cli/add` - Add content to IPFS
- `GET /cli/cat/{cid}` - Retrieve content by CID
- `POST /cli/pin/{cid}` - Pin content to local node
- `POST /cli/unpin/{cid}` - Unpin content from local node
- `GET /cli/pins` - List pinned content

### IPNS Operations

- `POST /cli/publish/{cid}` - Publish CID to IPNS
- `GET /cli/resolve/{name}` - Resolve IPNS name to CID

### Network Operations

- `POST /cli/connect/{peer}` - Connect to a peer
- `GET /cli/peers` - List connected peers

### Filesystem Operations

- `GET /cli/exists/{path}` - Check if a path exists
- `GET /cli/ls/{path}` - List contents of a directory

### SDK Generation

- `POST /cli/generate-sdk` - Generate client SDK for the API

### WAL Integration (When Available)

- `GET /cli/wal/status` - Get WAL status information
- `GET /cli/wal/list/{operation_type}` - List WAL operations by type
- `GET /cli/wal/show/{operation_id}` - Show details for a specific WAL operation
- `POST /cli/wal/retry/{operation_id}` - Retry a failed WAL operation
- `POST /cli/wal/cleanup` - Clean up old WAL operations
- `GET /cli/wal/metrics` - Get WAL metrics and performance statistics

## Usage Examples

### Python Client

```python
import requests
import json

# Base URL for MCP server
BASE_URL = "http://localhost:8000/api/v0/mcp"

# Execute a CLI command
response = requests.post(
    f"{BASE_URL}/cli/execute",
    json={
        "command": "add",
        "args": ["Hello, IPFS!"],
        "params": {"filename": "hello.txt"}
    }
)
result = response.json()
print(f"Add result: {result}")

# Get content
cid = result["result"]["Hash"]
response = requests.get(f"{BASE_URL}/cli/cat/{cid}")
content = response.content.decode('utf-8')
print(f"Retrieved content: {content}")

# Pin content
response = requests.post(f"{BASE_URL}/cli/pin/{cid}")
print(f"Pin result: {response.json()}")

# List pins
response = requests.get(f"{BASE_URL}/cli/pins")
pins = response.json()
print(f"Pins: {pins}")
```

### cURL Commands

```bash
# Add content
curl -X POST "http://localhost:8000/api/v0/mcp/cli/add" \
     -H "Content-Type: application/json" \
     -d '{"content": "Hello, IPFS!", "filename": "hello.txt"}'

# Get content
curl -X GET "http://localhost:8000/api/v0/mcp/cli/cat/QmXyz123"

# Get version information
curl -X GET "http://localhost:8000/api/v0/mcp/cli/version"

# Execute arbitrary command
curl -X POST "http://localhost:8000/api/v0/mcp/cli/execute" \
     -H "Content-Type: application/json" \
     -d '{"command": "pin", "args": ["QmXyz123"]}'
```

## Implementation Details

The CLI Controller is implemented in the `ipfs_kit_py/mcp/controllers/cli_controller.py` file and uses the following components:

1. **IPFSSimpleAPI**: From the high-level API to execute commands
2. **WAL Integration**: For WAL-related commands (when available)
3. **FastAPI Router**: To register HTTP endpoints
4. **IPFSModel**: For access to core IPFS functionality

The controller is registered with the MCP server in the `_init_components` method of the `MCPServer` class, making it available through the MCP server's API.

## Error Handling

The CLI Controller includes comprehensive error handling:

- All operations return a standard response format with success/error information
- Detailed error messages are provided for debugging
- Proper HTTP status codes for different error types
- Logging of all operations for troubleshooting

## Security Considerations

When exposing this API:

- Consider adding authentication to protect sensitive operations
- Use HTTPS to secure API traffic
- Implement rate limiting to prevent abuse
- Consider access control for different command types

## Testing

The CLI Controller integration can be tested with the included test script:

```bash
python test_mcp_cli.py
```

This will verify that the CLI Controller is properly registered with the MCP server and list all available routes.