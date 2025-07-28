# IPFS-Kit CLI Overview

## Executive Summary

The IPFS-Kit CLI has been comprehensively enhanced with **real data integration** from multiple sources including config files, Parquet data, WAL operations, FS journal operations, and program state monitoring. The CLI now provides lock-free daemon status monitoring using program state Parquet files, eliminating the need for daemon API locks while providing rich real-time metrics.

## Architecture Innovation

### Lock-Free Daemon Status
- **Primary Data Source**: Program state Parquet files written by daemon
- **Fallback**: Daemon API calls if Parquet data unavailable
- **Benefits**: No daemon locks, real-time performance metrics, comprehensive status
- **Data Files**: 4 Parquet files (system_state, network_state, storage_state, files_state)

### Real Configuration Integration
- **Config Sources**: 5 configuration files from ~/.ipfs_kit/
- **Formats**: YAML and JSON configurations
- **Files**: package_config.yaml, s3_config.yaml, lotus_config.yaml, wal/config.json, fs_journal/config.json

## Core Command Categories

### 1. Daemon Management (`daemon`)
- `daemon start` - Start IPFS-Kit daemon with auto-discovery
- `daemon stop` - Stop daemon gracefully
- **`daemon status`** - Enhanced status with program state data
  - **Features**: Lock-free operation, performance metrics, network status, storage info
  - **Data Sources**: Program state Parquet files (primary), API calls (fallback)
  - **Metrics**: Bandwidth I/O, repository size, connected peers, IPFS version, last updated

### 2. Configuration Management (`config`)
- **`config show`** - Display all configuration from real ~/.ipfs_kit/ files
  - **Sources**: 5 config files (S3, Lotus, Package, WAL, FS Journal)
  - **Format**: Unified display with source file references
- **`config validate`** - Validate all configuration files
  - **Features**: Real file validation, format checking, comprehensive summary

### 3. Pin Management (`pin`)
- `pin add <hash>` - Pin content with Parquet logging
- `pin remove <hash>` - Unpin content 
- `pin list` - List all pins from real Parquet data
- `pin status <hash>` - Check specific pin status

### 4. Backend Operations (`backend`)
- `backend add <name> <type>` - Add storage backend
- `backend list` - List configured backends
- `backend remove <name>` - Remove backend
- `backend status` - Check backend health

### 5. Health Monitoring (`health`)
- `health check` - Comprehensive system health
- `health metrics` - Performance metrics
- `health logs` - Recent log entries

### 6. Cloud Storage (`bucket`)
- `bucket create <name>` - Create S3 bucket
- `bucket list` - List available buckets
- `bucket upload <path>` - Upload to bucket
- `bucket download <key>` - Download from bucket

### 7. MCP Server (`mcp`)
- `mcp start` - Start Model Context Protocol server
- `mcp stop` - Stop MCP server
- `mcp status` - Check MCP server status
- `mcp config` - Configure MCP settings

### 8. WAL Operations (`wal`)
- `wal show` - Display WAL from real Parquet data
- `wal replay` - Replay operations
- `wal clear` - Clear WAL entries

### 9. FS Journal (`fs-journal`)
- `fs-journal show` - Display filesystem operations from Parquet
- `fs-journal monitor` - Start filesystem monitoring
- `fs-journal replay` - Replay filesystem operations

### 10. Resource Management (`resource`)
- `resource usage` - System resource utilization
- `resource limits` - Resource limits and quotas

## Real Data Sources

### Configuration Files (5 sources)
1. **package_config.yaml** - Package settings and version info
2. **s3_config.yaml** - S3 storage configuration (region, endpoint)
3. **lotus_config.yaml** - Lotus node configuration (URL, token)
4. **wal/config.json** - Write-Ahead Log settings (enabled, batch size)
5. **fs_journal/config.json** - Filesystem journal settings (enabled, monitor path)

### Program State Data (4 Parquet files)
1. **system_state.parquet** - System performance and health metrics
2. **network_state.parquet** - Network connectivity and peer information
3. **storage_state.parquet** - Storage usage and repository information
4. **files_state.parquet** - File operations and management state

### Operational Data
- **Pin Data**: 3 pins tracked in Parquet format
- **WAL Operations**: 1 operation logged with timestamps
- **FS Journal**: 2 filesystem operations monitored

## Enhanced Features

### Program State Integration
- **Lock-Free Access**: Read daemon status without API locks
- **Rich Metrics**: Bandwidth (1KB/s in, 2KB/s out), repository size (976.6KB)
- **Network Status**: Connected peers (5), IPFS version (0.29.0)
- **Real-Time Updates**: Last updated timestamps from daemon

### Configuration Management
- **Multi-Format Support**: YAML and JSON configuration files
- **Validation**: Comprehensive config file validation with error reporting
- **Source Tracking**: Display which files provide each configuration value

### Data Integration Architecture
```
Daemon → Writes to Parquet → CLI reads lock-free
       ↓
   DuckDB synchronizes periodically
       ↓
   Real-time status without daemon locks
```

## Usage Examples

### Check Daemon Status (Enhanced)
```bash
ipfs-kit daemon status
```
**Output**: Program state metrics, network status, storage info, performance data

### View Configuration (Enhanced)
```bash
ipfs-kit config show
```
**Output**: All 5 config files displayed with sources

### Validate Configuration (Enhanced)
```bash
ipfs-kit config validate
```
**Output**: Real file validation results

### View Real Pin Data
```bash
ipfs-kit pin list
```
**Output**: Pins from Parquet data with timestamps

### View WAL Operations
```bash
ipfs-kit wal show
```
**Output**: Real WAL operations from Parquet

## Technical Implementation

### ParquetDataReader Enhancements
- **Config Integration**: `read_configuration()`, `get_config_value()`
- **Program State**: `read_program_state()`, `get_current_daemon_status()`
- **Multi-Format**: YAML and JSON config file parsing
- **Error Handling**: Graceful fallbacks and comprehensive error reporting

### CLI Architecture
- **Real Data Priority**: Program state → Config files → API calls
- **Lock-Free Design**: No daemon API locks for status checking
- **Comprehensive Display**: Rich formatting with emojis and structured output

## Benefits

1. **Lock-Free Operations**: Daemon status without API locks or daemon interaction
2. **Real Data Integration**: All commands use actual stored data when available
3. **Comprehensive Monitoring**: Rich performance metrics and status information
4. **Configuration Management**: Real config file integration with validation
5. **Operational Transparency**: View actual stored operations (pins, WAL, FS journal)
6. **Fallback Architecture**: Graceful degradation when data sources unavailable

## Data Architecture Summary

The CLI now provides a sophisticated multi-tier data access strategy:
- **Tier 1**: Program state Parquet files (fastest, lock-free)
- **Tier 2**: Configuration files (reliable, persistent)
- **Tier 3**: Operational Parquet data (pins, WAL, FS journal)
- **Tier 4**: API calls (fallback when needed)

This architecture enables comprehensive system monitoring and management without the traditional limitations of daemon API dependencies.
