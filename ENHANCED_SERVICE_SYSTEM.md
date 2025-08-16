# Enhanced Service Configuration and Monitoring System

This document describes the new service configuration and monitoring system implemented for IPFS Kit, addressing the requirements specified in the issue.

## Overview

The enhanced system provides:
- **Service Configuration Management**: Add, remove, and update service configurations
- **Metadata-First Approach**: MCP tools check `~/.ipfs_kit/` metadata before making library calls
- **Proper Storage Services**: Replaced incorrect services with proper storage services
- **Beautiful Dashboard**: Modern UI for service management
- **Monitoring Capabilities**: Real-time monitoring of service health, quota, and statistics

## Architecture

### 1. Metadata Manager (`metadata_manager.py`)

The `MetadataManager` class manages all metadata in the `~/.ipfs_kit/` directory:

```
~/.ipfs_kit/
├── config/          # Global configuration
├── services/        # Service-specific configurations (YAML)
├── state/          # Service state information (JSON)
├── monitoring/     # Monitoring data and statistics (JSON)
├── logs/           # Log files
├── cache/          # Temporary cache data
└── .gitignore      # Excludes sensitive data
```

**Key Features:**
- Thread-safe operations with locking
- Automatic directory structure creation
- Service configuration persistence
- State tracking and monitoring data storage

### 2. Service Registry (`service_registry.py`)

The `ServiceRegistry` manages available storage services:

**Supported Services:**
- **IPFS**: Core IPFS daemon
- **IPFS Cluster**: Distributed IPFS cluster
- **S3**: Amazon S3 compatible storage
- **Storacha**: Web3.Storage service
- **HuggingFace**: HuggingFace Hub integration
- **FTP**: FTP server integration (extensible)
- **SSHFS**: SSH filesystem integration (extensible)
- **Lotus**: Filecoin Lotus node (extensible)
- **Synapse**: Matrix Synapse integration (extensible)
- **Parquet**: Apache Parquet data storage (extensible)
- **Arrow**: Apache Arrow data processing (extensible)
- **GitHub**: GitHub integration (extensible)

**Features:**
- Dynamic service registration
- Health monitoring and status tracking
- Configuration management per service
- Start/stop/restart capabilities

### 3. MCP Metadata Wrapper (`mcp_metadata_wrapper.py`)

The wrapper ensures MCP tools check metadata before making library calls:

**Metadata-First Approach:**
1. Check `~/.ipfs_kit/` metadata first
2. Use cached/stored information when available
3. Fall back to `ipfs_kit_py` library calls only when necessary
4. Update metadata with results

**Benefits:**
- Reduced library call overhead
- Consistent data through metadata
- Better performance with caching
- Centralized configuration management

### 4. Enhanced MCP Server (`enhanced_mcp_server.py`)

FastAPI-based server providing REST API and dashboard:

**API Endpoints:**
```
POST /api/services/add                    # Add new service
DELETE /api/services/{service_name}       # Remove service
GET /api/services/list                    # List all services
GET /api/services/status                  # Get all service statuses
GET /api/services/{name}/status           # Get specific service status
POST /api/services/{name}/start           # Start service
POST /api/services/{name}/stop            # Stop service
GET /api/services/{name}/config           # Get service configuration
PUT /api/services/{name}/config           # Update service configuration
GET /api/services/{name}/stats            # Get service statistics
GET /api/services/{name}/quota            # Get quota information
GET /api/services/{name}/storage          # Get storage information
GET /api/monitoring/{name}                # Get monitoring data
GET /api/backends/stats                   # Get backend statistics
GET /api/system/health                    # Get system health
```

### 5. Unified JavaScript Library (`mcp-sdk.js`)

Enhanced client library for dashboard integration:

**New Features:**
- Service management methods
- `ServiceDashboard` class for UI rendering
- Modal forms for service configuration
- Real-time updates and monitoring
- Beautiful responsive design

## Usage

### Starting the Enhanced MCP Server

```python
from ipfs_kit_py.enhanced_mcp_server import start_enhanced_mcp_server

# Start server on default port 8004
await start_enhanced_mcp_server()
```

Or use the demo script:
```bash
python demo_enhanced_mcp_server.py
```

### Using the Service Registry

```python
from ipfs_kit_py.service_registry import get_service_registry

registry = get_service_registry()

# Add a service
await registry.add_service("s3", {
    "region": "us-east-1",
    "bucket": "my-bucket"
})

# Start the service
await registry.start_service("s3")

# Get service status
status = await registry.get_service_status("s3")
```

### Using the Metadata Manager

```python
from ipfs_kit_py.metadata_manager import get_metadata_manager

manager = get_metadata_manager()

# Set service configuration
manager.set_service_config("ipfs", {
    "host": "localhost",
    "port": 5001
})

# Get service state
state = manager.get_service_state("ipfs")

# Set monitoring data
manager.set_monitoring_data("ipfs", {
    "cpu_usage": 25.5,
    "memory_usage": 512
})
```

### Using the JavaScript Library

```html
<script src="/static/mcp-sdk.js"></script>
<script>
const client = MCP.createClient({ baseUrl: '' });
const dashboard = MCP.createServiceDashboard(client, {
    container: document.getElementById('dashboard')
});
await dashboard.init();
</script>
```

## Dashboard Features

The dashboard provides a modern, responsive interface with:

### Service Management
- **Service Cards**: Visual representation of each service with status indicators
- **Add Service**: Modal form to add new services with all available types
- **Configure Services**: JSON-based configuration editing
- **Start/Stop Services**: One-click service control
- **Remove Services**: Safe service removal with confirmation

### Monitoring
- **Real-time Status**: Live service status updates
- **Statistics Display**: Service-specific statistics and metrics
- **Health Indicators**: Visual health status with color coding
- **Resource Monitoring**: CPU, memory, and storage usage tracking

### Visual Design
- **Modern UI**: Gradient backgrounds and smooth animations
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Modal Dialogs**: Intuitive forms for service management
- **Status Badges**: Clear visual indicators for service states
- **Dark Mode Support**: Automatic dark mode detection

## Configuration Examples

### IPFS Service
```yaml
metadata:
  service_name: ipfs
  last_updated: '2025-08-16T00:11:58.327192+00:00'
  version: '1.0'
config:
  host: localhost
  port: 5001
  gateway_port: 8080
  enabled: true
```

### S3 Service
```yaml
metadata:
  service_name: s3
  last_updated: '2025-08-16T00:11:58.328057+00:00'
  version: '1.0'
config:
  region: us-east-1
  bucket: test-bucket
  access_key_id: AKIAI...
  secret_access_key: xxx...
```

### HuggingFace Service
```yaml
metadata:
  service_name: huggingface
  last_updated: '2025-08-16T00:11:58.328057+00:00'
  version: '1.0'
config:
  token: hf_xxx...
  cache_dir: ~/.cache/huggingface
  model_hub_url: https://huggingface.co
```

## Benefits

1. **Centralized Configuration**: All service configurations stored in `~/.ipfs_kit/`
2. **Metadata-First Performance**: Reduced library calls through metadata caching
3. **Proper Service Architecture**: Correct storage services instead of inappropriate ones
4. **Beautiful UI**: Modern dashboard for easy service management
5. **Comprehensive Monitoring**: Real-time health and performance tracking
6. **Extensible Design**: Easy to add new storage services
7. **Thread-Safe Operations**: Concurrent access handling
8. **Persistent State**: Service state survives restarts

## Migration

The system automatically creates the `~/.ipfs_kit/` directory structure and migrates existing configurations. No manual intervention required.

## Future Enhancements

- **Service Templates**: Predefined configurations for common setups
- **Automated Health Checks**: Scheduled service health monitoring
- **Performance Metrics**: Historical performance data and trends
- **Service Dependencies**: Automatic dependency management
- **Backup/Restore**: Configuration backup and restoration
- **Multi-Node Support**: Distributed service management