# Comprehensive MCP Dashboard

## Overview

The Comprehensive MCP Dashboard is a feature-rich web interface that provides complete monitoring and management capabilities for the IPFS Kit MCP server ecosystem. It integrates ALL features from the previous MCP dashboard while adding new capabilities for bucket management, VFS browsing, and file operations.

## Features

### 🏠 **Overview Tab**
- Real-time system status monitoring
- Quick access to all system components
- Health indicators for all services
- Summary statistics

### ⚙️ **Services Tab**
- IPFS daemon control and monitoring
- Lotus node management
- Cluster service monitoring
- Lassie service control
- Start/stop/restart capabilities

### 🔧 **Backends Tab**
- Backend health monitoring
- Sync status across all backends
- Configuration management
- Performance metrics

### 🪣 **Buckets Tab**
- Complete bucket management interface
- File upload with drag-and-drop support
- Bucket creation and configuration
- File download and deletion
- Content addressing operations

### 📁 **VFS Browser Tab**
- Virtual filesystem browsing
- Navigation through bucket structures
- File and directory management
- Content preview capabilities

### 🌐 **Peers Tab**
- IPFS peer management
- Connect/disconnect functionality
- Peer statistics and monitoring
- Network topology view

### 📌 **Pins Tab**
- PIN management interface
- Add/remove pins with metadata
- Cross-backend PIN synchronization
- PIN analytics

### 📊 **Metrics Tab**
- Real-time system metrics
- CPU, memory, disk usage
- Network I/O statistics
- Historical data visualization

### 📝 **Logs Tab**
- Real-time log streaming
- Component-specific filtering
- Log level management
- Export capabilities

### ⚙️ **Configuration Tab**
- System configuration management
- Component-specific settings
- Save/load configuration profiles
- Runtime parameter adjustment

### 📈 **Analytics Tab**
- Bucket usage analytics
- Performance analysis
- Cross-backend query interface
- CAR file generation and management

### 🔌 **MCP Server Tab**
- Direct MCP server interface
- API endpoint testing
- Server status monitoring
- Debug information

## Quick Start

### 1. Using the Startup Script

```bash
./run_comprehensive_dashboard.sh
```

### 2. Manual Startup

```bash
cd ipfs_kit_py/dashboard
python3 comprehensive_mcp_dashboard.py --host 127.0.0.1 --port 8085
```

### 3. With Custom Configuration

```bash
python3 comprehensive_mcp_dashboard.py \
  --host 0.0.0.0 \
  --port 8080 \
  --mcp-server-url http://localhost:8004 \
  --data-dir ~/.ipfs_kit \
  --debug \
  --update-interval 3
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | 127.0.0.1 | Dashboard host address |
| `--port` | 8085 | Dashboard port |
| `--mcp-server-url` | http://localhost:8004 | MCP server URL |
| `--data-dir` | ~/.ipfs_kit | Data directory path |
| `--debug` | false | Enable debug mode |
| `--update-interval` | 5 | Update interval in seconds |

## Environment Variables

You can also configure the dashboard using environment variables:

```bash
export DASHBOARD_HOST="0.0.0.0"
export DASHBOARD_PORT="8080"
export MCP_SERVER_URL="http://localhost:8004"
export DATA_DIR="~/.ipfs_kit"
export DEBUG="true"
export UPDATE_INTERVAL="3"
```

## Features Overview

### Real-Time Updates
- WebSocket-based real-time updates
- Automatic refresh of all components
- Live system monitoring

### File Operations
- Drag-and-drop file uploads
- Batch file operations
- Content addressing
- CAR file generation

### Cross-Backend Operations
- Query across multiple backends
- Synchronized PIN management
- Unified bucket interface

### Mobile Support
- Responsive design
- Touch-friendly interface
- Optimized for tablets and phones

### Advanced Features
- Custom metrics collection
- Performance analytics
- Configuration management
- Debug capabilities

## API Endpoints

The dashboard provides a comprehensive REST API:

### System
- `GET /api/status` - System status
- `GET /api/health` - Health check
- `GET /api/mcp/status` - MCP server status

### Services
- `GET /api/services` - List services
- `POST /api/services/{service}/control` - Control service

### Backends
- `GET /api/backends` - List backends
- `POST /api/backends/sync` - Sync backends

### Buckets
- `GET /api/buckets` - List buckets
- `POST /api/buckets` - Create bucket
- `GET /api/buckets/{name}` - Bucket details
- `POST /api/buckets/{name}/upload` - Upload file
- `GET /api/buckets/{name}/download/{path}` - Download file

### VFS
- `GET /api/vfs/structure` - VFS structure
- `GET /api/vfs/browse/{bucket}` - Browse bucket

### Peers
- `GET /api/peers` - List peers
- `POST /api/peers/connect` - Connect peer
- `POST /api/peers/disconnect` - Disconnect peer

### Pins
- `GET /api/pins` - List pins
- `POST /api/pins/add` - Add pin
- `POST /api/pins/remove` - Remove pin
- `POST /api/pins/sync` - Sync pins

### Metrics & Analytics
- `GET /api/metrics` - System metrics
- `GET /api/analytics/summary` - Analytics summary
- `GET /api/logs` - System logs

### Configuration
- `GET /api/configuration` - Get configuration
- `POST /api/configuration` - Update configuration

## Integration

The dashboard integrates with:

- **MCP Server**: Full integration with all MCP endpoints
- **IPFS Daemon**: Direct IPFS operations
- **Bucket Interface**: Unified bucket management
- **VFS System**: Virtual filesystem access
- **PIN Management**: Cross-backend PIN operations

## Development

### Requirements
- Python 3.8+
- FastAPI
- uvicorn
- aiohttp
- psutil
- websockets

### Running in Development Mode

```bash
python3 comprehensive_mcp_dashboard.py --debug --update-interval 1
```

### Custom Styling
The dashboard includes comprehensive CSS styling with:
- Responsive grid layouts
- Dark/light theme support
- Mobile-optimized interface
- Professional styling

## Troubleshooting

### Common Issues

1. **Dashboard won't start**
   - Check if port is available
   - Verify Python dependencies
   - Check data directory permissions

2. **MCP server connection failed**
   - Verify MCP server is running
   - Check MCP server URL
   - Review network connectivity

3. **File upload issues**
   - Check data directory permissions
   - Verify bucket exists
   - Check available disk space

### Debug Mode
Run with `--debug` flag for detailed logging:

```bash
python3 comprehensive_mcp_dashboard.py --debug
```

## Contributing

The dashboard is designed to be extensible:

1. Add new tabs by extending the HTML template
2. Add API endpoints in the FastAPI application
3. Extend backend functionality with new methods
4. Add JavaScript functions for new features

## License

This dashboard is part of the IPFS Kit project and follows the same license terms.
