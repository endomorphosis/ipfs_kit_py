# Configuration Save and Persistence Fix

## Overview

This fix addresses the issue where configuration settings in the IPFS Kit MCP server dashboard were not being saved or persisted when users clicked the "Save Configuration" button.

## Problem Statement

When using the `ipfs-kit mcp start` dashboard, users could:
1. Edit service configurations (IPFS, FTP, S3, etc.)
2. Click "Save Configuration"
3. But the settings were NOT persisted
4. Settings were lost on page reload
5. Configurations were not applied to the underlying services

## Solution Implemented

### 1. Backend Configuration Persistence

**File**: `ipfs_kit_py/mcp/services/comprehensive_service_manager.py`

Added comprehensive configuration management:

- **`configure_service()`**: Saves configuration to JSON files and applies to actual services
- **`_apply_service_config()`**: Dispatcher that routes configuration to the appropriate service handler
- **Service-specific config handlers**:
  - `_apply_ipfs_config()`: Modifies IPFS `config` file (JSON format)
  - `_apply_ipfs_cluster_config()`: Modifies IPFS Cluster `service.json`
  - `_apply_lotus_config()`: Modifies Lotus `config.toml` (TOML format)
  - `_apply_aria2_config()`: Modifies Aria2 `aria2.conf` (key=value format)
  - `_apply_lassie_config()`: Creates Lassie `config.json`
  - `_apply_storage_backend_config()`: Saves credentials securely for storage backends

### 2. Configuration Format Support

The fix supports multiple configuration formats:

- **JSON**: IPFS, IPFS Cluster, Lassie, storage backends
- **TOML**: Lotus (requires `toml` library)
- **Key=Value**: Aria2
- **Credentials**: Secure storage for S3, HuggingFace, GitHub, etc.

### 3. Frontend JavaScript Implementation

**File**: `ipfs_kit_py/mcp/main_dashboard.py`

Added complete frontend implementation:

- **`saveBackendConfig()`**: Collects form data and sends to API
- **`editBackendConfig()`**: Loads existing configuration for editing
- **`updateBackendConfigFields()`**: Dynamic form generation based on backend type
- **`refreshBackendConfigs()`**: Loads and displays all saved configurations
- **`testBackendConfig()`**: Tests backend connectivity
- **`deleteBackendConfig()`**: Removes saved configurations

### 4. API Endpoints

Implemented fully functional API endpoints:

```python
GET    /api/backend_configs              # List all configurations
GET    /api/backend_configs/{name}       # Get specific configuration
POST   /api/backend_configs              # Create new configuration
PUT    /api/backend_configs/{name}       # Update configuration
DELETE /api/backend_configs/{name}       # Delete configuration
POST   /api/backend_configs/{name}/test  # Test configuration
```

### 5. Configuration Persistence

Configurations are stored in `~/.ipfs_kit/`:

```
~/.ipfs_kit/
├── backend_configs/
│   ├── ipfs.json
│   ├── my-s3-backup.json
│   └── ftp-server.json
├── ipfs_config.json
├── s3_config.json
├── s3_credentials.json
└── services_config.json
```

### 6. Automatic Configuration Reload

**Key Features**:
- Configuration loaded on service manager initialization
- Configuration re-applied when services start
- Configuration persists across dashboard restarts
- Individual service configs merged with defaults

## Configuration Examples

### IPFS Configuration

```json
{
  "config_dir": "/home/user/.ipfs",
  "port": 5001,
  "gateway_port": 8080,
  "swarm_port": 4001,
  "auto_start": true
}
```

Generates IPFS `config` file:
```json
{
  "Addresses": {
    "API": "/ip4/127.0.0.1/tcp/5001",
    "Gateway": "/ip4/127.0.0.1/tcp/8080",
    "Swarm": [
      "/ip4/0.0.0.0/tcp/4001",
      "/ip6/::/tcp/4001"
    ]
  }
}
```

### S3 Configuration

```json
{
  "type": "s3",
  "access_key": "AKIA...",
  "secret_key": "wJalr...",
  "endpoint": "https://s3.amazonaws.com",
  "bucket": "my-bucket",
  "region": "us-east-1"
}
```

Saves credentials securely with 0o600 permissions.

### FTP Configuration

```json
{
  "type": "ftp",
  "host": "ftp.example.com",
  "port": 21,
  "username": "ftpuser",
  "password": "secret123",
  "directory": "/uploads"
}
```

### Aria2 Configuration

```json
{
  "port": 6800,
  "rpc_secret": "my_secret_token"
}
```

Generates `aria2.conf`:
```
rpc-listen-port=6800
rpc-secret=my_secret_token
enable-rpc=true
rpc-allow-origin-all=true
...
```

## Usage

### 1. Access the Dashboard

```bash
ipfs-kit mcp start
```

Navigate to `http://127.0.0.1:8004` (or configured port)

### 2. Configure a Service

1. Go to "Backend Configs" or "Configuration" tab
2. Click "Add Backend" or "Configure"
3. Select backend type (IPFS, S3, FTP, etc.)
4. Fill in configuration fields
5. Click "Save Configuration"

### 3. Verify Configuration Saved

- Configuration immediately persisted to `~/.ipfs_kit/backend_configs/{name}.json`
- Configuration applied to service (if service is installed)
- Status message shows success/failure and whether config was applied

### 4. Configuration Reload

Configuration is automatically reloaded:
- When dashboard restarts
- When service manager initializes
- When service starts (configuration re-applied)

## Testing

### Run Unit Tests

```bash
python3 /tmp/test_config_persistence.py
```

Tests:
- Configuration save to JSON
- Configuration persistence across manager instances
- Multiple service types (IPFS, S3)
- Configuration reload

### Run Integration Tests

```bash
python3 /tmp/test_dashboard_config.py
```

Tests:
- Dashboard API endpoints
- Configuration CRUD operations
- Multiple backend types
- Service manager integration
- Configuration persistence
- Update and reload functionality

## Architecture

```
┌─────────────────────────────────────────┐
│         Dashboard Frontend              │
│  (JavaScript saveBackendConfig)         │
└────────────┬────────────────────────────┘
             │
             │ POST /api/backend_configs
             ▼
┌─────────────────────────────────────────┐
│      Dashboard API Endpoints             │
│  (_create_backend_config)                │
└────────────┬────────────────────────────┘
             │
             │ Save JSON
             ▼
┌─────────────────────────────────────────┐
│   ComprehensiveServiceManager           │
│  (configure_service)                     │
└────────────┬────────────────────────────┘
             │
             ├─► Save to {service}_config.json
             │
             ├─► _apply_service_config()
             │
             └─► Service-specific handler
                 │
                 ├─► _apply_ipfs_config()
                 ├─► _apply_lotus_config()
                 ├─► _apply_aria2_config()
                 └─► _apply_storage_backend_config()
                     │
                     ▼
┌─────────────────────────────────────────┐
│   Actual Service Configuration Files    │
│  ~/.ipfs/config                          │
│  ~/.aria2/aria2.conf                     │
│  ~/.lotus/config.toml                    │
│  ~/.ipfs_kit/{service}_credentials.json  │
└─────────────────────────────────────────┘
```

## Files Modified

1. **`ipfs_kit_py/mcp/services/comprehensive_service_manager.py`**
   - Enhanced `configure_service()` method
   - Added `_apply_service_config()` dispatcher
   - Implemented service-specific configuration handlers
   - Added configuration reload on service start
   - Added `_load_individual_service_configs()` for persistence

2. **`ipfs_kit_py/mcp/main_dashboard.py`**
   - Implemented `_get_all_backend_configs()`
   - Implemented `_get_backend_config()`
   - Implemented `_create_backend_config()`
   - Implemented `_update_backend_config()`
   - Implemented `_delete_backend_config()`
   - Implemented `_test_backend_config()`
   - Added frontend JavaScript functions for configuration management

## Benefits

1. **Persistent Configuration**: Settings survive page reloads and dashboard restarts
2. **Format Agnostic**: Handles JSON, YAML, TOML, and key=value formats
3. **Service Integration**: Actually configures the underlying services
4. **User-Friendly**: Clear success/failure messages with details
5. **Secure**: Credentials stored with restricted permissions
6. **Automatic Reload**: Configurations applied on service start
7. **Type Support**: Multiple backend types (daemons, storage, network)

## Future Enhancements

Potential improvements:
- Add YAML configuration support (requires `pyyaml`)
- Implement configuration validation before saving
- Add configuration backup/restore
- Implement configuration templates
- Add configuration import/export
- Implement configuration versioning
- Add rollback functionality
- Enhanced error handling and validation
- Configuration diff/comparison

## Security Considerations

- Credentials stored in separate files with 0o600 permissions
- Passwords not logged or displayed in error messages
- Configuration files stored in user's home directory
- No hardcoded credentials or secrets

## Troubleshooting

### Configuration Not Applied

Check service status:
```bash
# For IPFS
ipfs id

# Check config file
cat ~/.ipfs/config
```

### Configuration Not Persisted

Check file exists:
```bash
ls -la ~/.ipfs_kit/backend_configs/
cat ~/.ipfs_kit/{service}_config.json
```

### Permission Issues

Ensure proper permissions:
```bash
chmod 600 ~/.ipfs_kit/*_credentials.json
```

### Service Not Found

Ensure service is installed:
```bash
which ipfs
which ipfs-cluster-service
which aria2c
```

## Conclusion

This fix provides comprehensive configuration management for the IPFS Kit MCP dashboard, ensuring that user settings are properly saved, persisted, and applied to the underlying services. The implementation supports multiple configuration formats and provides a user-friendly interface for managing service configurations.
