# Enhanced MCP Dashboard Documentation

## Overview

The Enhanced MCP Dashboard provides a comprehensive web-based interface for controlling and observing all aspects of the IPFS-Kit package. It has been completely refactored to integrate with the Enhanced MCP Server and leverage all available metadata sources.

## Features

### 🎯 Complete Control Interface
- **Daemon Management**: Start, stop, restart, and monitor the IPFS-Kit daemon
- **MCP Server Control**: Full control over the Enhanced MCP Server
- **Backend Management**: Configure, test, and monitor all 15+ storage backends
- **Service Monitoring**: Monitor IPFS, Lotus, Cluster, and Lassie services
- **Pin Management**: Add, remove, list, and manage pins with full metadata
- **Configuration Management**: View and edit all system configurations

### 📊 Real-time Monitoring
- **System Metrics**: CPU, memory, disk usage with live updates
- **WebSocket Integration**: Real-time updates without page refresh
- **Service Health**: Continuous monitoring of all system components
- **Log Streaming**: Live log viewing with filtering and search
- **Performance Analytics**: Historical metrics and trend analysis

### 🔧 Enhanced Integration
- **MCP Server Parity**: 100% feature compatibility with CLI commands
- **Metadata Efficiency**: Optimized caching with 60-second TTL
- **Daemon Coordination**: Full coordination with intelligent daemon manager
- **Multi-API Support**: Both command interface and REST endpoints

## Installation & Setup

### Prerequisites
```bash
pip install fastapi uvicorn jinja2 aiohttp websockets psutil
```

### Quick Start

#### Option 1: Start with MCP Server
```bash
# Start both MCP server and dashboard together
ipfs-kit mcp start --enhanced --with-dashboard

# Custom ports
ipfs-kit mcp start --enhanced --with-dashboard --port 8001 --dashboard-port 8080
```

#### Option 2: Start Dashboard Separately
```bash
# Start enhanced dashboard
ipfs-kit dashboard start

# With custom configuration
ipfs-kit dashboard start --host 0.0.0.0 --port 8080 --mcp-url http://127.0.0.1:8001
```

#### Option 3: Direct Script Execution
```bash
# Run enhanced dashboard directly
python run_enhanced_dashboard.py

# With configuration
python run_enhanced_dashboard.py --host 127.0.0.1 --port 8080
```

## Configuration

### Dashboard Configuration File
The dashboard uses `enhanced_dashboard_config.json` for comprehensive configuration:

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 8080,
    "title": "IPFS-Kit Enhanced Dashboard"
  },
  "mcp_server": {
    "url": "http://127.0.0.1:8001",
    "timeout": 30,
    "retry_attempts": 3
  },
  "dashboard": {
    "update_interval": 5,
    "real_time_updates": true,
    "system_metrics": true,
    "notifications": true
  }
}
```

### Environment Variables
- `IPFS_KIT_DASHBOARD_HOST`: Dashboard host (default: 127.0.0.1)
- `IPFS_KIT_DASHBOARD_PORT`: Dashboard port (default: 8080)
- `IPFS_KIT_MCP_URL`: MCP server URL (default: http://127.0.0.1:8001)
- `IPFS_KIT_METADATA_PATH`: Metadata directory (default: ~/.ipfs_kit)

## Dashboard Pages

### 🏠 Home Dashboard
- **System Status Overview**: Server, daemon, and MCP status
- **Pin Metrics**: Total, active, pending, and failed pins
- **Backend Status**: Healthy vs unhealthy backends count
- **System Resources**: Real-time CPU, memory, and disk usage
- **Recent Activity**: Latest system events and operations

**URL**: `http://localhost:8080/`

### 🔧 Daemon Control
- **Status Display**: Current daemon state and details
- **Control Buttons**: Start, stop, restart daemon
- **Process Information**: PID, uptime, and resource usage
- **Configuration Details**: Current daemon settings

**URL**: `http://localhost:8080/daemon`

### 📌 Pin Management
- **Add Pins**: Web form to add new pins with metadata
- **Pin Table**: Sortable, filterable list of all pins
- **Pin Actions**: View, remove, and manage individual pins
- **Bulk Operations**: Multi-select operations on pins
- **Status Filtering**: Filter by active, pending, failed status

**URL**: `http://localhost:8080/pins`

### 🔗 Backend Management
- **Backend Overview**: Status of all 15+ supported backends
- **Backend Testing**: Test connectivity for each backend
- **Configuration**: View and edit backend settings
- **Health Monitoring**: Continuous backend health checks
- **Authentication**: Backend-specific auth instructions

**URL**: `http://localhost:8080/backends`

**Supported Backends**:
- HuggingFace Hub
- GitHub
- Amazon S3
- Storacha (Web3.Storage)
- IPFS
- Google Drive
- Lotus (Filecoin)
- Synapse
- SSHFS
- FTP
- IPFS Cluster
- Parquet
- Apache Arrow

### 🔧 Service Monitoring
- **Service Cards**: Status of IPFS, Lotus, Cluster, Lassie
- **Service Control**: Start, stop, restart services
- **Metrics Display**: Service-specific performance metrics
- **Log Integration**: Recent logs for each service
- **Health Checks**: Automated service health monitoring

**URL**: `http://localhost:8080/services`

### 📋 Log Viewer
- **Real-time Logs**: Live streaming log display
- **Filtering**: By component, level, and search terms
- **Export**: Download logs in JSON/CSV format
- **Log Levels**: Debug, Info, Warning, Error, Critical
- **Component Filtering**: Daemon, Pin, Backend, Service, MCP

**URL**: `http://localhost:8080/logs`

### ⚙️ Configuration
- **Configuration Tree**: Hierarchical view of all settings
- **Live Editing**: Modify configuration values in real-time
- **Backup/Restore**: Configuration backup and restore functionality
- **Validation**: Input validation for configuration changes
- **History**: Track configuration changes over time

**URL**: `http://localhost:8080/config`

### 📊 Metrics & Analytics
- **Performance Charts**: Historical system performance data
- **Pin Analytics**: Pin operation success rates and timing
- **Backend Analytics**: Backend usage and performance metrics
- **System Trends**: Long-term system health trends
- **Export Options**: Download metrics in various formats

**URL**: `http://localhost:8080/metrics`

## API Endpoints

### System Status
- `GET /api/status` - Overall system status
- `GET /api/health` - Dashboard health check

### Daemon Control
- `GET /api/daemon/status` - Get daemon status
- `POST /api/daemon/start` - Start daemon
- `POST /api/daemon/stop` - Stop daemon
- `POST /api/daemon/restart` - Restart daemon

### Pin Management
- `GET /api/pins` - List all pins
- `POST /api/pins` - Add new pin
- `DELETE /api/pins/{cid}` - Remove pin by CID
- `GET /api/pins/{cid}` - Get pin details

### Backend Management
- `GET /api/backends` - List all backends
- `GET /api/backends/{name}/status` - Get backend status
- `POST /api/backends/{name}/test` - Test backend connection

### Service Monitoring
- `GET /api/services` - Get all service statuses
- `GET /api/services/{name}/status` - Get specific service status

### Logs
- `GET /api/logs` - Get logs with filtering
- `POST /api/logs/clear` - Clear all logs

### Configuration
- `GET /api/config` - Get current configuration
- `POST /api/config/set` - Update configuration value

### Metrics
- `GET /api/metrics` - Get detailed metrics

## WebSocket Integration

### Real-time Updates
The dashboard uses WebSocket connections for real-time updates:

**Connection**: `ws://localhost:8080/ws`

**Message Types**:
- `metrics_update`: System metrics updates every 5 seconds
- `notification`: System notifications and alerts
- `log_entry`: New log entries (when log streaming is enabled)
- `status_change`: Service/daemon status changes

### JavaScript Integration
```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    
    switch(message.type) {
        case 'metrics_update':
            updateDashboardMetrics(message.data);
            break;
        case 'notification':
            showNotification(message.data.message, message.data.type);
            break;
    }
};
```

## Advanced Features

### Multi-tenancy
The dashboard supports multiple IPFS-Kit instances:
- Different metadata paths
- Multiple MCP server connections
- Instance switching in UI

### Security
- CORS configuration for cross-origin requests
- Optional rate limiting
- Authentication hooks (extensible)

### Theming
- Light/Dark theme support
- Auto theme detection
- Custom CSS themes

### Monitoring Integration
- Prometheus metrics export
- Grafana dashboard templates
- Alert manager integration

## Troubleshooting

### Common Issues

#### Dashboard Won't Start
```bash
# Check if port is available
netstat -an | grep :8080

# Check MCP server connection
curl http://localhost:8001/health

# Check logs
tail -f ~/.ipfs_kit/logs/dashboard.log
```

#### WebSocket Connection Issues
- Ensure firewall allows WebSocket connections
- Check browser console for connection errors
- Verify WebSocket proxy configuration if using reverse proxy

#### MCP Server Connection Failed
- Verify MCP server is running: `ipfs-kit mcp status`
- Check MCP server URL in dashboard config
- Test API endpoint: `curl http://localhost:8001/health`

#### Missing Features
- Ensure using Enhanced MCP Server: `ipfs-kit mcp start --enhanced`
- Verify all dependencies installed: `pip install -r requirements.txt`
- Check compatibility: Enhanced Dashboard requires Enhanced MCP Server

### Performance Optimization

#### For Large Pin Sets
- Increase cache TTL in configuration
- Use pagination for pin listings
- Enable backend pin count optimization

#### For High Update Frequency  
- Adjust WebSocket update interval
- Disable real-time updates for specific components
- Use polling fallback for stability

## Development

### Extending the Dashboard

#### Adding New Pages
1. Create template in `dashboard_templates/`
2. Add route in `enhanced_dashboard.py`
3. Update navigation in base template

#### Custom Widgets
1. Create widget component in static/js/
2. Register widget in dashboard configuration
3. Add widget to desired pages

#### API Extensions
1. Add handler method to `EnhancedMCPDashboard`
2. Register route in `_register_routes()`
3. Update API documentation

### Testing
```bash
# Run dashboard tests
python -m pytest tests/test_dashboard.py

# Integration tests with MCP server
python -m pytest tests/test_mcp_integration.py

# Load testing
python tests/load_test_dashboard.py
```

## Migration from Legacy Dashboard

### Differences from Legacy
- **Architecture**: FastAPI-based vs Flask-based
- **Real-time**: WebSocket integration vs polling
- **Features**: Complete MCP integration vs limited functionality
- **Performance**: Optimized caching vs direct file access
- **UI**: Modern responsive design vs basic interface

### Migration Steps
1. **Backup Configuration**: Export existing dashboard settings
2. **Update Dependencies**: Install new requirements
3. **Start Enhanced Dashboard**: Use `--legacy` flag for gradual migration
4. **Migrate Customizations**: Update custom themes and extensions
5. **Test Integration**: Verify all functionality works correctly

### Compatibility Mode
Use legacy dashboard during transition:
```bash
ipfs-kit dashboard start --legacy
```

## Support & Contributing

### Getting Help
- **Documentation**: Check this guide and API docs
- **Issues**: Report bugs on GitHub
- **Discussions**: Join community discussions
- **Support**: Contact maintainers

### Contributing
1. **Fork Repository**: Create your fork
2. **Development Setup**: Install development dependencies
3. **Make Changes**: Implement features or fixes
4. **Test Changes**: Run test suite
5. **Submit PR**: Create pull request with description

### Feature Requests
- Open GitHub issue with feature description
- Provide use cases and requirements
- Include mockups or examples if possible

---

## Version History

### v2.0.0 (Current)
- Complete rewrite with Enhanced MCP Server integration
- Real-time WebSocket updates
- 100% CLI feature parity
- Modern responsive UI
- Comprehensive backend management
- Advanced metrics and analytics

### v1.x (Legacy)
- Basic Flask-based dashboard
- Limited MCP integration
- Polling-based updates
- Basic pin management
- Simple configuration interface

---

**Enhanced MCP Dashboard v2.0.0** - Complete control and observation interface for IPFS-Kit
