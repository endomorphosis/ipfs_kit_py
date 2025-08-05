# Enhanced MCP Dashboard - Complete IPFS Kit Control Interface

The Enhanced MCP Dashboard provides a comprehensive web-based interface for controlling and monitoring all aspects of the IPFS Kit system. This dashboard integrates with the real MCP server interfaces and provides full access to all available features.

## 🚀 Features

### Core IPFS Operations
- **Real-time Daemon Monitoring**: Live status, health checks, resource usage
- **Pin Management**: Add, remove, list pins with content addressing metadata
- **Content Operations**: Browse, upload, download IPFS content
- **Peer Management**: Connect, disconnect, monitor peer network
- **Gateway Monitoring**: Check gateway accessibility and performance

### Backend Management
- **Multi-Backend Support**: S3, GitHub, HuggingFace, FTP, SSHFS, Storacha
- **Health Monitoring**: Real-time connectivity and performance testing  
- **Configuration Management**: Create, update, validate backend configurations
- **Load Balancing**: Monitor and optimize backend usage patterns

### Bucket Operations
- **Bucket VFS**: Create, manage, delete buckets with VFS structures
- **File Operations**: Upload, download, browse bucket contents
- **Content Addressing**: IPLD-compatible content addressing
- **Storage Analytics**: Usage patterns, size distribution, access frequency

### Virtual Filesystem (VFS)
- **VFS Browser**: Navigate virtual filesystem structures
- **File Operations**: Read, write, copy, move files through VFS
- **Version Tracking**: Track VFS changes and versions
- **Mount Management**: Manage VFS mount points

### Parquet Analytics
- **Data Storage**: Store DataFrames as Parquet with IPLD addressing
- **SQL Queries**: Execute SQL queries against Parquet datasets
- **Data Retrieval**: Retrieve data in multiple formats (JSON, CSV, Parquet)
- **Dataset Management**: List, analyze, and manage stored datasets

### Advanced Features
- **Conflict-Free Operations**: Content-addressed operations that don't require global state sync
- **Real-time Updates**: WebSocket-based live updates
- **Configuration Widgets**: Interactive configuration management
- **Comprehensive Logging**: Structured logging with pattern detection
- **Metrics Export**: Export metrics in multiple formats
- **Service Monitoring**: Monitor all IPFS Kit services

## 🛠 Installation and Setup

### Prerequisites
- Python 3.8+
- IPFS daemon (optional, can be managed by the dashboard)
- FastAPI and dependencies (installed with ipfs_kit_py)

### Quick Start

1. **Run the dashboard**:
   ```bash
   python run_enhanced_dashboard.py
   ```

2. **Custom configuration**:
   ```bash
   python run_enhanced_dashboard.py --port 8083 --host 0.0.0.0 --mcp-url http://localhost:8080
   ```

3. **Access the dashboard**:
   Open your browser to `http://127.0.0.1:8083`

## 🌐 API Endpoints

### Core Dashboard Endpoints
- `GET /` - Main dashboard interface
- `GET /daemon` - Daemon control panel
- `GET /backends` - Backend management interface
- `GET /buckets` - Bucket operations interface
- `GET /pins` - Pin management interface
- `GET /vfs` - Virtual filesystem browser
- `GET /parquet` - Analytics and data operations
- `GET /ws` - WebSocket connection for real-time updates

### REST API Endpoints

#### MCP Integration
- `POST /api/mcp/tool/{tool_name}` - Execute MCP tool directly
- `GET /api/status` - Get comprehensive system status

#### Bucket Management
- `GET /api/buckets` - List all buckets
- `POST /api/buckets` - Create new bucket
- `DELETE /api/buckets/{bucket_name}` - Delete bucket
- `POST /api/buckets/{bucket_name}/upload` - Upload files to bucket
- `GET /api/buckets/{bucket_name}/download/{content_id}` - Download from bucket

#### Backend Management  
- `GET /api/backends` - List backends with health status
- `POST /api/backends/{backend_name}/test` - Test backend health
- `POST /api/backends/{backend_name}/configure` - Configure backend

#### Pin Management
- `GET /api/pins` - List all pins with metadata
- `POST /api/pins` - Add new pin
- `DELETE /api/pins/{cid}` - Remove pin
- `GET /api/pins/{cid}/content` - Get pin content

#### VFS Operations
- `GET /api/vfs?path={path}` - List VFS directory
- `GET /api/vfs/content?path={path}` - Read VFS file
- `GET /api/vfs/info?path={path}` - Get VFS file info

#### Parquet Analytics
- `POST /api/parquet/store` - Store data as Parquet
- `GET /api/parquet/{cid}` - Retrieve Parquet data
- `POST /api/parquet/query` - Execute SQL query
- `GET /api/parquet/datasets` - List datasets

#### System Monitoring
- `GET /api/metrics` - Get comprehensive metrics
- `GET /api/metrics/export` - Export metrics
- `GET /api/logs` - Get system logs
- `GET /api/config` - Get configuration

## 📊 Real-time Features

### WebSocket Updates
The dashboard provides real-time updates through WebSocket connections:

```javascript
const ws = new WebSocket('ws://127.0.0.1:8083/ws');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Handle real-time updates
};
```

### Live Monitoring
- **Daemon Status**: Real-time daemon health and resource usage
- **Backend Health**: Continuous backend connectivity monitoring
- **Pin Changes**: Live updates when pins are added/removed
- **VFS Changes**: Real-time filesystem change notifications
- **Metrics Streaming**: Live system metrics and performance data

## 🔧 Configuration

### Environment Variables
- `IPFS_KIT_METADATA_PATH`: Path to IPFS Kit metadata (default: ~/.ipfs_kit)
- `MCP_SERVER_URL`: MCP server URL (default: http://127.0.0.1:8080)
- `DASHBOARD_HOST`: Dashboard host (default: 127.0.0.1)
- `DASHBOARD_PORT`: Dashboard port (default: 8083)

### Configuration Files
The dashboard reads configuration from:
- `~/.ipfs_kit/backend_configs/` - Backend configurations
- `~/.ipfs_kit/bucket_configs/` - Bucket configurations
- `~/.ipfs_kit/config/` - General configuration

## 🏗 Architecture

### Components
1. **FastAPI Server**: Web server and API endpoints
2. **WebSocket Handler**: Real-time communication
3. **MCP Integration**: Direct integration with MCP tools
4. **Data Sources**: Real filesystem and IPFS data
5. **Health Monitors**: Backend and service monitoring
6. **Analytics Engine**: Parquet and metrics processing

### Data Flow
```
Browser <-> FastAPI <-> MCP Server <-> IPFS Kit <-> IPFS Daemon
         <-> WebSocket <-> Real-time Updates
         <-> Static Files <-> Dashboard UI
```

## 🧪 Testing

### Manual Testing
1. Start the dashboard: `python run_enhanced_dashboard.py`
2. Test each endpoint in the browser or with curl
3. Verify real-time updates work through WebSocket
4. Test backend health monitoring with different backends
5. Upload/download files through bucket interface

### API Testing
```bash
# Test MCP integration
curl -X POST http://127.0.0.1:8083/api/mcp/tool/ipfs_add \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello World"}'

# Test bucket operations
curl -X POST http://127.0.0.1:8083/api/buckets \
  -H "Content-Type: application/json" \
  -d '{"bucket_name": "test-bucket", "bucket_type": "general"}'

# Test backend health
curl -X POST http://127.0.0.1:8083/api/backends/primary_s3/test
```

## 🐛 Troubleshooting

### Common Issues

1. **Dashboard won't start**:
   - Check if port is already in use
   - Verify Python dependencies are installed
   - Check IPFS Kit installation

2. **MCP server connection failed**:
   - Verify MCP server is running
   - Check MCP server URL configuration
   - Review firewall settings

3. **Backend health checks failing**:
   - Verify backend credentials in configuration files
   - Check network connectivity
   - Review backend-specific requirements

4. **Real-time updates not working**:
   - Check WebSocket connection in browser console
   - Verify firewall allows WebSocket connections
   - Check browser WebSocket support

### Debug Mode
Run with debug logging:
```bash
PYTHONPATH=. python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
import asyncio
from run_enhanced_dashboard import main
asyncio.run(main())
"
```

## 🚀 Development

### Adding New Features
1. Add API endpoints in `enhanced_dashboard.py`
2. Implement backend methods for real data integration
3. Add corresponding UI components in templates
4. Update WebSocket handlers for real-time updates
5. Add comprehensive error handling and logging

### Code Structure
```
ipfs_kit_py/mcp/enhanced_dashboard.py  # Main dashboard class
run_enhanced_dashboard.py              # Runner script
templates/                             # HTML templates
static/                               # CSS, JS, assets
```

## 📈 Performance

### Optimization Features
- **Caching**: Intelligent caching of expensive operations
- **Pagination**: Large datasets are paginated
- **Lazy Loading**: UI components load on demand
- **Connection Pooling**: Efficient HTTP connection reuse
- **Background Tasks**: Long operations run in background

### Monitoring
- Resource usage tracking
- Response time monitoring
- Error rate tracking
- WebSocket connection monitoring

## 🔒 Security

### Features
- **Input Validation**: All inputs are validated
- **Error Handling**: Secure error messages
- **Connection Limits**: WebSocket connection limits
- **File Upload Limits**: Size and type restrictions

### Best Practices
- Run dashboard on internal network only
- Use HTTPS in production
- Implement authentication if needed
- Regular security updates

## 📄 License

This dashboard is part of the IPFS Kit package and follows the same license terms.
