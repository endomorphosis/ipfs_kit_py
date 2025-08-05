# Unified MCP Dashboard Server

This unified server combines the IPFS Kit MCP server and dashboard into a single application that runs on one port and uses JSON-RPC communication instead of WebSocket.

## Features

- **🔧 MCP Server**: Full Model Context Protocol server with JSON-RPC API
- **📊 Dashboard**: Modern web interface with real-time metrics and controls
- **🌐 Single Port**: Both services share the same port for simplified deployment
- **📡 JSON-RPC**: Standardized JSON-RPC 2.0 communication protocol
- **⚡ FastAPI**: High-performance async web framework
- **🎨 Modern UI**: Responsive design with Tailwind CSS and Chart.js

## Quick Start

### Option 1: Using the Launcher (Recommended)
```bash
python launch_unified_mcp_dashboard.py --port 8083 --host 0.0.0.0
```

### Option 2: Direct Execution
```bash
python unified_mcp_dashboard_server.py --port 8083 --host 0.0.0.0
```

## Access Points

Once started, the unified server provides:

- **Dashboard Web Interface**: http://localhost:8083
- **JSON-RPC API Endpoint**: http://localhost:8083/api/jsonrpc
- **Health Check**: http://localhost:8083/health

## JSON-RPC API Methods

The server exposes comprehensive MCP functionality via JSON-RPC:

### System Methods
- `system.info` - Get system information
- `system.health` - Check system health
- `system.metrics` - Get system metrics

### Daemon Management
- `daemon.status` - Check IPFS daemon status
- `daemon.start` - Start IPFS daemon
- `daemon.stop` - Stop IPFS daemon
- `daemon.restart` - Restart IPFS daemon

### IPFS Operations
- `ipfs.add` - Add content to IPFS
- `ipfs.get` - Get content from IPFS
- `ipfs.cat` - Display content from IPFS
- `ipfs.pin.add` - Pin content
- `ipfs.pin.remove` - Unpin content
- `ipfs.pin.list` - List pinned content

### Bucket Operations
- `bucket.list` - List available buckets
- `bucket.create` - Create new bucket
- `bucket.status` - Get bucket status
- `bucket.sync` - Sync bucket content

### Backend Management
- `backend.list` - List available backends
- `backend.status` - Get backend status
- `backend.sync` - Sync with backend

### Peer Operations
- `peer.list` - List connected peers
- `peer.connect` - Connect to peer
- `peer.info` - Get peer information

## Example JSON-RPC Requests

### Get System Information
```bash
curl -X POST http://localhost:8083/api/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "system.info",
    "id": 1
  }'
```

### Add Content to IPFS
```bash
curl -X POST http://localhost:8083/api/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "ipfs.add",
    "params": {
      "content": "Hello, IPFS!",
      "filename": "greeting.txt"
    },
    "id": 2
  }'
```

### List Buckets
```bash
curl -X POST http://localhost:8083/api/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "bucket.list",
    "id": 3
  }'
```

## Dashboard Features

The web dashboard provides:

- **📊 System Metrics**: CPU, memory, storage usage
- **🔧 Daemon Control**: Start/stop/restart IPFS daemon
- **📁 Bucket Management**: List, create, sync buckets
- **🌐 Backend Status**: Monitor backend connections
- **👥 Peer Information**: View connected peers
- **📋 Operation Logs**: Real-time operation logging

## Configuration

### Environment Variables
- `IPFS_KIT_HOST`: Server host (default: 127.0.0.1)
- `IPFS_KIT_PORT`: Server port (default: 8083)
- `IPFS_KIT_DEBUG`: Enable debug mode (default: false)

### Command Line Options
```
--host HOST     Host to bind to (default: 127.0.0.1)
--port PORT     Port to run on (default: 8083)
--debug         Enable debug mode
--help          Show help message
```

## Architecture

```
┌─────────────────┐    JSON-RPC     ┌─────────────────┐
│   Web Dashboard │ ◄──────────────► │   MCP Server    │
│   (Frontend)    │                 │   (Backend)     │
└─────────────────┘                 └─────────────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Unified Server                 │
│                  Single Port: 8083                  │
└─────────────────────────────────────────────────────┘
```

## Deployment

### Development
```bash
python launch_unified_mcp_dashboard.py --host 127.0.0.1 --port 8083 --debug
```

### Production
```bash
python launch_unified_mcp_dashboard.py --host 0.0.0.0 --port 8083
```

### Docker (if available)
```bash
# Build container
docker build -t ipfs-kit-unified .

# Run container
docker run -p 8083:8083 ipfs-kit-unified
```

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```
   Error: [Errno 98] Address already in use
   ```
   Solution: Use a different port with `--port XXXX`

2. **IPFS daemon not found**
   ```
   Warning: IPFS daemon not available
   ```
   Solution: Install IPFS or ensure it's in your PATH

3. **Permission denied**
   ```
   Error: Permission denied
   ```
   Solution: Use a port > 1024 or run with appropriate permissions

### Logs

The server provides detailed logging. Enable debug mode for verbose output:
```bash
python launch_unified_mcp_dashboard.py --debug
```

## Migration from Separate Services

If you were previously running separate MCP server and dashboard:

1. **Stop existing services**
2. **Update any scripts** to use the unified server
3. **Update client connections** to use JSON-RPC instead of WebSocket
4. **Verify functionality** with the new unified interface

## Dependencies

Required:
- Python 3.8+
- FastAPI
- Uvicorn

Optional (with fallbacks):
- IPFS daemon
- Additional backends

## License

Same as IPFS Kit project.
