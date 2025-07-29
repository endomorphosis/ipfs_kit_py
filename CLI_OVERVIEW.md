# IPFS-Kit CLI Comprehensive Usage Guide

## Executive Summary

The IPFS-Kit CLI has been comprehensively enhanced with **real data integration**, **three-tier policy management**, and **multi-backend storage operations**. The CLI now provides lock-free daemon status monitoring, comprehensive configuration management, and fine-grained control over replication, caching, and storage quotas across all backends.

## Latest CLI Architecture

### Enhanced Command Structure
```
ipfs-kit-cli
├── daemon           # Daemon and service management
├── pin              # IPFS pin operations with policy support
├── backend          # Multi-backend storage operations (15 backends)
├── health           # System health and monitoring
├── config           # Configuration and global policy management  
├── bucket           # Virtual filesystem and bucket-level policies
├── mcp              # Model Context Protocol server management
├── metrics          # Performance metrics and analytics
├── resource         # Resource tracking and monitoring
└── log              # Unified log aggregation and viewing
```

### Three-Tier Policy System Integration
- **Global Policies**: `config pinset-policy` - System-wide defaults
- **Bucket Policies**: `bucket policy` - Per-bucket overrides
- **Backend Quotas**: `backend <name> configure` - Hard limits and retention

## Core Command Categories

### 1. Daemon Management (`daemon`)

**Purpose**: Manage IPFS-Kit daemon and related services

```bash
# Basic daemon operations
ipfs-kit daemon start          # Start the daemon with auto-discovery
ipfs-kit daemon stop           # Stop daemon gracefully  
ipfs-kit daemon status         # Enhanced status with program state data
ipfs-kit daemon restart        # Restart daemon

# Service-specific management
ipfs-kit daemon ipfs {start,stop,status}        # IPFS node management
ipfs-kit daemon lotus {start,stop,status}       # Lotus/Filecoin node
ipfs-kit daemon cluster {start,stop,status}     # IPFS Cluster service
ipfs-kit daemon lassie {start,stop,status}      # Lassie retrieval service

# Role management for cluster operations
ipfs-kit daemon set-role {master,worker,leecher}  # Set node role
ipfs-kit daemon get-role                           # Get current role
ipfs-kit daemon auto-role                          # Auto-detect optimal role
```

**Enhanced Features**:
- **Lock-free status**: Read daemon status without API locks
- **Program state data**: Performance metrics from Parquet files
- **Service orchestration**: Manage multiple related services
- **Role-based clustering**: Hierarchical node roles

### 2. Configuration Management (`config`)

**Purpose**: Manage system configuration and global policies

```bash
# Basic configuration
ipfs-kit config show                    # Display all configuration
ipfs-kit config validate               # Validate all config files
ipfs-kit config set <key> <value>      # Set configuration value
ipfs-kit config init                   # Interactive setup wizard
ipfs-kit config backup                 # Backup configuration
ipfs-kit config restore <file>         # Restore from backup
ipfs-kit config reset                  # Reset to defaults

# Global Pinset Policy Management (NEW)
ipfs-kit config pinset-policy show     # Show current global policies
ipfs-kit config pinset-policy set [OPTIONS]  # Set global policies
ipfs-kit config pinset-policy reset    # Reset to defaults
```

**Global Policy Options**:
```bash
# Replication strategies
--replication-strategy {single,multi-backend,tiered,adaptive}
--min-replicas N --max-replicas N
--geographic-distribution {local,regional,global}

# Cache policies  
--cache-policy {lru,lfu,fifo,mru,adaptive,tiered}
--cache-size N --cache-memory-limit SIZE --auto-gc

# Performance and tiering
--performance-tier {speed-optimized,balanced,persistence-optimized}
--auto-tier --hot-tier-duration SECONDS --warm-tier-duration SECONDS

# Backend management
--preferred-backends "backend1,backend2,backend3"
--backend-weights "arrow:0.3,s3:0.4,filecoin:0.3"
```

### 3. Pin Management (`pin`)

**Purpose**: IPFS content pinning with policy support

```bash
ipfs-kit pin add <hash>                 # Pin content with policy application
ipfs-kit pin remove <hash>              # Unpin content
ipfs-kit pin list                       # List all pins from Parquet data
ipfs-kit pin pending                    # List pending operations in WAL
ipfs-kit pin status <hash>              # Check specific pin status
ipfs-kit pin get <hash>                 # Download pinned content to file
ipfs-kit pin cat <hash>                 # Stream pinned content to stdout
ipfs-kit pin init                       # Initialize pin metadata with samples
```

### 4. Backend Operations (`backend`)

**Purpose**: Multi-backend storage operations with 15 supported backends

```bash
# Backend management
ipfs-kit backend list                   # List all available backends
ipfs-kit backend test                   # Test all backend connections

# Individual backend operations (15 backends supported)
ipfs-kit backend {huggingface,github,s3,storacha,ipfs,gdrive,lotus,
                  synapse,sshfs,ftp,ipfs-cluster,ipfs-cluster-follow,
                  parquet,arrow} <action>
```

**Supported Backends with Configuration**:

#### HuggingFace Hub Operations
```bash
ipfs-kit backend huggingface configure --token <token> --storage-quota 1GB
ipfs-kit backend huggingface login --token <token>
ipfs-kit backend huggingface list --type model --limit 5
ipfs-kit backend huggingface download microsoft/DialoGPT-medium model.bin
ipfs-kit backend huggingface files microsoft/DialoGPT-medium
```

#### GitHub Repository Operations  
```bash
ipfs-kit backend github configure --token <token> --storage-quota 1GB --lfs-quota 100GB
ipfs-kit backend github login --token <token>
ipfs-kit backend github list --user endomorphosis
ipfs-kit backend github clone endomorphosis/ipfs_kit_py
ipfs-kit backend github upload repo file.txt path/file.txt --message "Update"
```

#### Amazon S3 Operations
```bash
ipfs-kit backend s3 configure --access-key <key> --secret-key <secret> \
  --account-quota 10TB --retention-policy lifecycle --cost-optimization
ipfs-kit backend s3 list                        # List buckets
ipfs-kit backend s3 create my-bucket             # Create bucket
ipfs-kit backend s3 upload file.txt my-bucket   # Upload file
ipfs-kit backend s3 download my-bucket file.txt # Download file
```

#### Filecoin/Lotus Operations
```bash
ipfs-kit backend lotus configure --endpoint <rpc_url> --token <token> \
  --quota-size 50TB --retention-policy permanent --auto-renew
ipfs-kit backend lotus status                   # Node status
ipfs-kit backend lotus store ./data.txt --duration 525600  # Store for 1 year
```

#### Google Drive Operations
```bash
ipfs-kit backend gdrive configure --credentials creds.json \
  --storage-quota 15GB --version-retention 100
ipfs-kit backend gdrive auth --credentials creds.json
ipfs-kit backend gdrive list --folder <folder_id>
ipfs-kit backend gdrive upload file.txt --folder <folder_id>
```

#### Web3/Storacha Operations
```bash
ipfs-kit backend storacha configure --api-key <key> \
  --storage-quota 1TB --deal-duration 180 --auto-renew
ipfs-kit backend storacha upload ./dataset --name "my-dataset"
ipfs-kit backend storacha list
```

#### IPFS Cluster Operations
```bash
ipfs-kit backend ipfs-cluster configure --endpoint http://127.0.0.1:9094 \
  --global-replication-min 3 --global-cache-policy adaptive
ipfs-kit backend ipfs-cluster status
ipfs-kit backend ipfs-cluster pin <hash> --replication-min 3
ipfs-kit backend ipfs-cluster unpin <hash>
```

#### Remote Storage (SSHFS/FTP)
```bash
# SSHFS operations
ipfs-kit backend sshfs configure --hostname server.com --username user \
  --storage-quota 1TB --retention-days 90 --auto-reconnect
ipfs-kit backend sshfs upload ./file.txt /remote/path/
ipfs-kit backend sshfs download /remote/file.txt ./local/

# FTP operations  
ipfs-kit backend ftp configure --host ftp.example.com --username user \
  --storage-quota 500GB --bandwidth-limit 10MB/s
ipfs-kit backend ftp upload ./file.txt /remote/file.txt
ipfs-kit backend ftp list /remote/directory
```

#### Data Processing (Arrow/Parquet)
```bash
# Apache Arrow operations
ipfs-kit backend arrow configure --memory-quota 16GB --session-retention 48
ipfs-kit backend arrow convert ./data.csv ./data.parquet
ipfs-kit backend arrow compute ./data.parquet --operation mean --column price

# Parquet operations
ipfs-kit backend parquet configure --storage-quota 5TB --auto-compaction
ipfs-kit backend parquet read ./data.parquet --limit 100 --columns id,name
ipfs-kit backend parquet write ./data.csv ./output.parquet
```

### 5. Bucket Management (`bucket`)

**Purpose**: Virtual filesystem and bucket-level policy management

```bash
# Basic bucket operations
ipfs-kit bucket list                    # List available buckets
ipfs-kit bucket discover                # Discover new buckets
ipfs-kit bucket analytics               # Show bucket analytics
ipfs-kit bucket refresh                 # Refresh bucket index
ipfs-kit bucket files <bucket>          # List files in bucket
ipfs-kit bucket find-cid <cid>          # Find bucket for CID
ipfs-kit bucket snapshots <bucket>      # Show bucket snapshots

# Bucket Policy Management (NEW)
ipfs-kit bucket policy show [bucket]    # Show policies for bucket(s) 
ipfs-kit bucket policy set <bucket> [OPTIONS]  # Set bucket policy
ipfs-kit bucket policy copy <src> <dest>        # Copy policy between buckets
ipfs-kit bucket policy template <bucket> <template>  # Apply policy template
ipfs-kit bucket policy reset <bucket>           # Reset to global defaults

# CAR file operations
ipfs-kit bucket prepare-car <bucket>    # Prepare bucket for CAR generation
ipfs-kit bucket generate-index-car <bucket>  # Generate CAR files
ipfs-kit bucket list-cars               # List generated CAR files
ipfs-kit bucket upload-ipfs <bucket>    # Upload CAR files to IPFS

# VFS operations
ipfs-kit bucket upload-index <bucket>   # Upload VFS index to IPFS
ipfs-kit bucket download-vfs <bucket>   # Download VFS indexes
ipfs-kit bucket verify-ipfs <bucket>    # Verify content in IPFS
ipfs-kit bucket ipfs-history <bucket>   # Show IPFS upload history
```

**Bucket Policy Options**:
```bash
# Backend selection
--primary-backend {s3,filecoin,arrow,parquet,ipfs,storacha,sshfs,ftp}
--replication-backends "backend1,backend2,backend3"

# Cache configuration
--cache-policy {lru,lfu,fifo,mru,adaptive,inherit}
--cache-size N --cache-priority {low,normal,high,critical}

# Performance and lifecycle
--performance-tier {speed-optimized,balanced,persistence-optimized}
--retention-days N --max-size SIZE
--quota-action {warn,block,auto-archive,auto-delete}

# Auto-tiering
--auto-tier --hot-backend BACKEND --warm-backend BACKEND
--cold-backend BACKEND --archive-backend BACKEND
```

### 6. Health Monitoring (`health`)

**Purpose**: System health and performance monitoring

```bash
ipfs-kit health                         # Comprehensive system health check
ipfs-kit health --backend <name>        # Backend-specific health check
ipfs-kit health --detailed              # Detailed health metrics
ipfs-kit health --format json           # JSON output format
```

### 7. MCP Server Management (`mcp`)

**Purpose**: Model Context Protocol server operations

```bash
ipfs-kit mcp start                      # Start MCP server
ipfs-kit mcp stop                       # Stop MCP server  
ipfs-kit mcp status                     # Check MCP server status
ipfs-kit mcp restart                    # Restart MCP server
ipfs-kit mcp role                       # Configure server role
ipfs-kit mcp cli                        # Use MCP CLI tool
```

### 8. Metrics and Analytics (`metrics`)

**Purpose**: Performance metrics and system analytics

```bash
ipfs-kit metrics                        # Show performance metrics
ipfs-kit metrics --backend <name>       # Backend-specific metrics
ipfs-kit metrics --timeframe 24h        # Metrics for specific timeframe
ipfs-kit metrics --export csv           # Export metrics to CSV
```

### 9. Resource Management (`resource`)

**Purpose**: Resource tracking and monitoring

```bash
ipfs-kit resource                       # Show resource usage
ipfs-kit resource --backend <name>      # Backend-specific resources
ipfs-kit resource --limits              # Show resource limits
ipfs-kit resource --alerts              # Show resource alerts
```

### 10. Log Management (`log`)

**Purpose**: Unified log aggregation and viewing

```bash
ipfs-kit log                            # Show recent logs
ipfs-kit log --follow                   # Follow logs in real-time
ipfs-kit log --level error              # Filter by log level
ipfs-kit log --backend <name>           # Backend-specific logs
ipfs-kit log --export                   # Export logs to file
```

## Policy System Examples

### Complete Multi-Tier Configuration

#### 1. Set Global Policies
```bash
# Configure system-wide defaults
ipfs-kit config pinset-policy set \
  --replication-strategy adaptive \
  --min-replicas 2 \
  --max-replicas 5 \
  --cache-policy lru \
  --cache-size 10000 \
  --cache-memory-limit 4GB \
  --performance-tier balanced \
  --auto-tier \
  --preferred-backends "filecoin,s3,arrow"
```

#### 2. Configure Backend Quotas
```bash
# High-persistence, low-speed backend (Filecoin)
ipfs-kit backend lotus configure \
  --quota-size 50TB \
  --retention-policy permanent \
  --auto-renew \
  --redundancy-level 3

# High-speed, low-persistence backend (Arrow)  
ipfs-kit backend arrow configure \
  --memory-quota 16GB \
  --retention-policy temporary \
  --session-retention 48 \
  --spill-to-disk

# Balanced backend (S3)
ipfs-kit backend s3 configure \
  --account-quota 10TB \
  --retention-policy lifecycle \
  --cost-optimization \
  --auto-delete-after 365
```

#### 3. Set Bucket-Level Policies
```bash
# High-performance ML training bucket
ipfs-kit bucket policy set ml-training \
  --primary-backend arrow \
  --replication-backends "arrow,parquet" \
  --performance-tier speed-optimized \
  --cache-priority high \
  --retention-days 30

# Long-term archive bucket
ipfs-kit bucket policy set archive \
  --primary-backend filecoin \
  --replication-backends "filecoin,s3,storacha" \
  --performance-tier persistence-optimized \
  --retention-days 2555 \
  --quota-action auto-archive

# Multi-tier production bucket
ipfs-kit bucket policy set production \
  --auto-tier \
  --hot-backend arrow \
  --warm-backend parquet \
  --cold-backend s3 \
  --archive-backend filecoin
```

## Data Sources and Architecture

### Real Data Integration
- **Configuration Files**: 5 config files from ~/.ipfs_kit/
- **Program State**: 4 Parquet files for lock-free daemon status
- **Operational Data**: Pins, WAL operations, FS journal from Parquet
- **Policy Data**: Global, bucket, and backend policies

### Lock-Free Architecture
```
CLI Commands → Program State Parquet → Lock-free status
            ↓
         Config Files → Persistent settings
            ↓
         Policy System → Multi-tier control
            ↓
         Backend APIs → Storage operations
```

## Advanced Usage Patterns

### Development Workflow
```bash
# Setup development environment
ipfs-kit config pinset-policy set --performance-tier speed-optimized
ipfs-kit bucket policy set dev-bucket --primary-backend arrow --retention-days 7

# Production deployment
ipfs-kit config pinset-policy set --replication-strategy adaptive --min-replicas 3
ipfs-kit bucket policy set prod-bucket --auto-tier --retention-days 365
```

### Multi-Backend Replication
```bash
# Configure for high availability
ipfs-kit config pinset-policy set \
  --replication-strategy multi-backend \
  --geographic-distribution global \
  --failover-strategy immediate

ipfs-kit bucket policy set critical-data \
  --replication-backends "filecoin,s3,storacha,github" \
  --min-replicas 4
```

### Cost Optimization
```bash
# Cost-optimized global policy
ipfs-kit config pinset-policy set \
  --backend-weights "filecoin:0.6,s3:0.3,arrow:0.1" \
  --auto-tier \
  --warm-tier-duration 86400

# Enable S3 cost optimization
ipfs-kit backend s3 configure --cost-optimization --retention-policy lifecycle
```

## Benefits of Enhanced CLI

1. **Comprehensive Control**: Fine-grained policies across all storage tiers
2. **Multi-Backend Support**: 15 different storage backends with unified interface
3. **Lock-Free Operations**: Daemon status without API locks or blocking
4. **Real Data Integration**: All commands use actual stored data when available
5. **Policy Inheritance**: Hierarchical policy system reduces configuration complexity
6. **Automated Management**: Auto-tiering and lifecycle management
7. **Production Ready**: Comprehensive monitoring, logging, and health checks

## Quick Reference

### Most Common Commands
```bash
# System status and health
ipfs-kit daemon status                  # Daemon status
ipfs-kit health                         # System health
ipfs-kit metrics                        # Performance metrics

# Policy management
ipfs-kit config pinset-policy show     # Global policies
ipfs-kit bucket policy show            # Bucket policies
ipfs-kit backend test                   # Backend health

# Content operations
ipfs-kit pin add <hash>                 # Pin content
ipfs-kit bucket list                    # List buckets
ipfs-kit backend s3 upload file.txt    # Upload to S3
```

This enhanced CLI provides a comprehensive, production-ready interface for managing distributed storage with fine-grained policy control across all backends while maintaining ease of use and operational transparency.

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
