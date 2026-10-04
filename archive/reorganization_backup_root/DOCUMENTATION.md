# IPFS-Kit Enhanced Technical Documentation v2.0

## Table of Contents

### Getting Started
- [Quick Start Guide](#quick-start-guide)
- [Installation](#installation)  
- [CLI Usage](#cli-usage)
- [Docker Deployment](#docker-deployment)

### Core Components
- [IPFS-Kit Daemon](#ipfs-kit-daemon)
- [Enhanced CLI Tool](#enhanced-cli-tool)
- [Multiprocessing Engine](#multiprocessing-engine)
- [Backend Management](#backend-management)

### Deployment
- [Docker Containers](#docker-containers)
- [Kubernetes](#kubernetes)
- [CI/CD Pipeline](#ci-cd-pipeline)

### Advanced Topics
- [Performance Optimization](#performance-optimization)
- [Monitoring and Observability](#monitoring-and-observability)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

## Quick Start Guide

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py

# Build and run with Docker Compose
docker-compose -f docker/docker-compose.enhanced.yml up -d

# Check status
curl http://localhost:9999/api/v1/status

# Use the CLI
docker exec -it ipfs-kit-daemon python ipfs_kit_enhanced_cli.py daemon status
```

### Option 2: Local Installation

```bash
# Install dependencies
pip install -r requirements.txt
pip install -e .

# Start the daemon
python ipfs_kit_enhanced_cli.py daemon start --detach

# Check status
python ipfs_kit_enhanced_cli.py daemon status

# Add a pin
python ipfs_kit_enhanced_cli.py pin add QmYourCIDHere --name "my-file"

# List pins
python ipfs_kit_enhanced_cli.py pin list --metadata
```

### Option 3: CLI-Only Mode

```bash
# Install CLI tool
pip install -e .

# Use enhanced CLI directly
python ipfs_kit_enhanced_cli.py --help

# Start daemon in foreground for debugging
python ipfs_kit_enhanced_cli.py daemon start
```

## CLI Usage

The enhanced CLI provides comprehensive management capabilities:

### Daemon Management
```bash
# Start daemon in background
python ipfs_kit_enhanced_cli.py daemon start --detach

# Stop daemon
python ipfs_kit_enhanced_cli.py daemon stop

# Restart daemon
python ipfs_kit_enhanced_cli.py daemon restart

# Show detailed status
python ipfs_kit_enhanced_cli.py daemon status
```

### Pin Operations
```bash
# Add a pin with metadata
python ipfs_kit_enhanced_cli.py pin add QmHash --name "important-file"

# List pins with metadata
python ipfs_kit_enhanced_cli.py pin list --limit 100 --metadata

# Remove a pin
python ipfs_kit_enhanced_cli.py pin remove QmHash
```

### Backend Management
```bash
# Start a specific backend
python ipfs_kit_enhanced_cli.py backend start ipfs

# Check backend status
python ipfs_kit_enhanced_cli.py backend status ipfs

# Check all backends
python ipfs_kit_enhanced_cli.py backend status
```

### Health Monitoring
```bash
# Comprehensive health check
python ipfs_kit_enhanced_cli.py health check

# Check specific backend health
python ipfs_kit_enhanced_cli.py health check ipfs
```

### Performance Metrics
```bash
# Show performance metrics
python ipfs_kit_enhanced_cli.py metrics

# Show detailed metrics
python ipfs_kit_enhanced_cli.py metrics --detailed
```

### Configuration Management
```bash
# Show current configuration
python ipfs_kit_enhanced_cli.py config show

# Set configuration values
python ipfs_kit_enhanced_cli.py config set daemon.health_check_interval 60
python ipfs_kit_enhanced_cli.py config set backends.ipfs_cluster.enabled true
```

### VFS Operations
```bash
# Mount a VFS path
python ipfs_kit_enhanced_cli.py vfs mount /ipfs/QmHash --mount-point /mnt/ipfs

# List VFS mounts
python ipfs_kit_enhanced_cli.py vfs list
```

## Docker Deployment

### Single Container Deployment

```dockerfile
# Use the enhanced Dockerfile
docker build -f docker/Dockerfile.enhanced -t ipfs-kit:latest .

# Run with all services
docker run -d \
  --name ipfs-kit \
  -p 4001:4001 \
  -p 5001:5001 \
  -p 8080:8080 \
  -p 9999:9999 \
  -v ipfs_data:/home/ipfs_user/.ipfs \
  -v config_data:/tmp/ipfs_kit_config \
  ipfs-kit:latest all
```

### Multi-Container Cluster Deployment

```bash
# Deploy full cluster with monitoring
cd docker
docker-compose -f docker-compose.enhanced.yml up -d

# Services included:
# - ipfs-kit: Main IPFS-Kit daemon
# - ipfs-kit-cluster: Cluster node
# - prometheus: Metrics collection
# - grafana: Dashboard (admin/admin)
```

### Container Modes

The enhanced Docker image supports multiple operation modes:

```bash
# Daemon only (lightweight)
docker run ipfs-kit:latest daemon-only

# IPFS only (just IPFS daemon)
docker run ipfs-kit:latest ipfs-only

# MCP server only
docker run ipfs-kit:latest mcp-only

# Full cluster mode
docker run ipfs-kit:latest cluster

# All services (default)
docker run ipfs-kit:latest all
```

### Health Monitoring

The container includes comprehensive health checks:

```bash
# Check container health
docker exec ipfs-kit /healthcheck.sh

# View logs
docker logs ipfs-kit

# Monitor with built-in dashboard
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
```

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [IPFS-Kit Daemon](#ipfs-kit-daemon)
4. [Multiprocessing Enhancements](#multiprocessing-enhancements)
5. [Installation and Setup](#installation-and-setup)
6. [Usage Guide](#usage-guide)
7. [Performance Benchmarks](#performance-benchmarks)
8. [Testing](#testing)
9. [API Reference](#api-reference)
10. [Troubleshooting](#troubleshooting)

## Overview

IPFS-Kit is a comprehensive toolkit for managing IPFS (InterPlanetary File System) infrastructure with advanced features including daemon management, multiprocessing optimizations, and integrated backend support. The system is designed for high-performance, scalable operations across distributed storage networks.

### Key Features

- **Standalone Daemon Architecture**: Separate daemon for backend infrastructure management
- **Multiprocessing Optimization**: 3-8x performance improvements through parallel processing
- **Backend Health Monitoring**: Real-time monitoring of IPFS, Cluster, Lotus, and other backends
- **Replication Management**: Automated replication across storage backends
- **MCP Server Integration**: Model Context Protocol server with multiprocessing support
- **Enhanced CLI Tools**: Command-line tools with parallel batch operations
- **Real-time Monitoring**: Comprehensive observability and metrics collection

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    IPFS-Kit Architecture                    │
├─────────────────────┬─────────────────────┬─────────────────┤
│                     │                     │                 │
│   CLI Tools         │    MCP Server       │    Daemon       │
│   ┌─────────────┐   │   ┌─────────────┐   │  ┌─────────────┐│
│   │ Enhanced    │   │   │ Enhanced    │   │  │ IPFS-Kit    ││
│   │ CLI with    │   │   │ MCP Server  │   │  │ Daemon      ││
│   │ Parallel    │   │   │ Multi-      │   │  │ Backend     ││
│   │ Processing  │   │   │ processing  │   │  │ Manager     ││
│   └─────────────┘   │   └─────────────┘   │  └─────────────┘│
│                     │                     │                 │
├─────────────────────┼─────────────────────┼─────────────────┤
│                     │                     │                 │
│   Process Pools     │   Uvicorn Workers   │ Background      │
│   • IPFS Ops        │   • VFS Pool        │ Tasks           │
│   • Backend Checks  │   • Backend Pool    │ • Health Checks │
│   • I/O Operations  │   • Route Pool      │ • Replication   │
│                     │   • Thread Pools    │ • Log Collection│
│                     │                     │ • Pin Indexing  │
└─────────────────────┴─────────────────────┴─────────────────┘
```

### Design Principles

1. **Separation of Concerns**: Daemon handles infrastructure, MCP handles protocols, CLI handles user operations
2. **Multiprocessing First**: All components designed for parallel execution
3. **Fault Tolerance**: Robust error handling and graceful degradation
4. **Observability**: Comprehensive logging, metrics, and monitoring
5. **Scalability**: Automatic resource detection and optimization

## IPFS-Kit Daemon

### Overview

The IPFS-Kit Daemon (`ipfs_kit_daemon.py`) is a standalone service responsible for managing filesystem backend infrastructure. It operates independently from the MCP server and CLI tools, providing a clean separation of concerns.

### Responsibilities

- **Backend Management**: Starting, stopping, and configuring IPFS, Cluster, Lotus, and other backends
- **Health Monitoring**: Continuous monitoring of backend health and performance
- **Replication Management**: Automated replication across storage backends
- **Log Collection**: Centralized log aggregation and rotation
- **Pin Index Maintenance**: Updating and maintaining pin metadata indexes
- **Configuration Management**: Dynamic configuration updates and validation

### Configuration

The daemon uses a JSON configuration file with the following structure:

```json
{
  "daemon": {
    "pid_file": "/tmp/ipfs_kit_daemon.pid",
    "log_level": "INFO",
    "health_check_interval": 30,
    "replication_check_interval": 300,
    "log_rotation_interval": 3600
  },
  "backends": {
    "ipfs": {"enabled": true, "auto_start": true},
    "ipfs_cluster": {"enabled": true, "auto_start": true},
    "lotus": {"enabled": false, "auto_start": false},
    "lassie": {"enabled": true, "auto_start": true},
    "storacha": {"enabled": false, "auto_start": false}
  },
  "replication": {
    "enabled": true,
    "auto_replication": true,
    "min_replicas": 2,
    "max_replicas": 5,
    "check_interval": 300
  },
  "monitoring": {
    "health_checks": true,
    "metrics_collection": true,
    "log_aggregation": true,
    "performance_monitoring": true
  }
}
```

### Key Features

#### Background Task Management

```python
async def _health_monitoring_loop(self):
    """Background health monitoring loop"""
    while self.running:
        for backend_name in self.config["backends"].keys():
            if self.config["backends"][backend_name].get("enabled"):
                await self._check_backend_health(backend_name)
        await asyncio.sleep(self.health_check_interval)
```

#### Signal Handling

```python
def _signal_handler(self, signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    self.running = False
```

#### Dynamic Configuration

```python
async def _check_config_changes(self):
    """Check for configuration file changes"""
    if os.path.exists(self.config_file):
        mtime = os.path.getmtime(self.config_file)
        if hasattr(self, '_last_config_mtime') and mtime > self._last_config_mtime:
            self.config = self._load_config()
            await self._reconfigure_components()
```

## Multiprocessing Enhancements

### Performance Improvements

Our comprehensive testing shows significant performance improvements:

- **CPU-Intensive Tasks**: Up to 3.4x speedup with optimal worker configuration
- **I/O-Intensive Tasks**: Up to 22.9x speedup with async processing
- **Mixed Workloads**: Improved load balancing and resource utilization
- **Memory Efficiency**: Optimized memory usage with shared state management

### Enhanced MCP Server

The enhanced MCP server (`enhanced_multiprocessing_mcp_server.py`) provides:

#### Multiple Worker Processes
```python
class EnhancedMultiprocessingMCPServer:
    def __init__(self, host="127.0.0.1", port=8888, workers=None):
        self.workers = workers or min(mp.cpu_count(), 4)
        self.vfs_pool = ProcessPoolExecutor(max_workers=self.workers//2)
        self.backend_pool = ProcessPoolExecutor(max_workers=2)
        self.route_pool = ProcessPoolExecutor(max_workers=2)
```

#### Specialized Process Pools
- **VFS Pool**: Handles virtual filesystem operations
- **Backend Pool**: Manages backend health checks and operations
- **Route Pool**: Optimizes routing decisions
- **Thread Pools**: Non-blocking I/O operations

#### Load Balancing
```python
async def handle_request(self, request):
    """Handle request with load balancing"""
    start_time = time.time()
    success = False
    
    try:
        # Route to appropriate process pool
        if request.path.startswith('/vfs/'):
            result = await self._handle_vfs_request(request)
        elif request.path.startswith('/backend/'):
            result = await self._handle_backend_request(request)
        else:
            result = await self._handle_route_request(request)
        
        success = True
        return result
    finally:
        response_time = time.time() - start_time
        self.stats.record_request(success, response_time)
```

### Enhanced CLI

The enhanced CLI (`enhanced_multiprocessing_cli.py`) provides:

#### Parallel Batch Operations
```python
async def add_files_batch(self, file_paths: List[str]) -> List[Dict[str, Any]]:
    """Add multiple files in parallel"""
    with Progress() as progress:
        task = progress.add_task("Adding files...", total=len(file_paths))
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(add_file_worker, file_path, self.config): file_path 
                for file_path in file_paths
            }
            
            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                progress.advance(task)
```

#### Progress Tracking
```python
class ProgressTracker:
    def __init__(self):
        self.total_operations = Value('i', 0)
        self.completed_operations = Value('i', 0)
        self.failed_operations = Value('i', 0)
        self.start_time = time.time()
    
    def update_progress(self):
        """Update and display progress"""
        elapsed = time.time() - self.start_time
        completion_rate = self.completed_operations.value / max(self.total_operations.value, 1)
        eta = elapsed / max(completion_rate, 0.01) - elapsed if completion_rate > 0 else 0
        
        return {
            "progress": completion_rate * 100,
            "eta": eta,
            "throughput": self.completed_operations.value / elapsed
        }
```

### Enhanced Daemon

The enhanced daemon (`enhanced_multiprocessing_daemon.py`) provides:

#### Process Pool Management
```python
def start_process_pools(self):
    """Start process pools for parallel operations"""
    self.health_pool = ProcessPoolExecutor(
        max_workers=self.config["health_workers"],
        mp_context=mp.get_context('spawn')
    )
    
    self.pin_pool = ProcessPoolExecutor(
        max_workers=self.config["pin_index_workers"],
        mp_context=mp.get_context('spawn')
    )
    
    self.api_thread_pool = ThreadPoolExecutor(
        max_workers=self.config["api_threads"],
        thread_name_prefix="api-thread"
    )
```

#### Shared Statistics
```python
class ProcessStats:
    """Shared statistics for worker processes"""
    def __init__(self):
        self.total_requests = Value('i', 0)
        self.successful_requests = Value('i', 0)
        self.failed_requests = Value('i', 0)
        self.total_response_time = Value('d', 0.0)
        self.active_workers = Value('i', 0)
        self.peak_workers = Value('i', 0)
```

#### Worker Functions
```python
def health_check_worker(backend_name: str, config: Dict[str, Any], 
                       result_queue: MPQueue, stats: ProcessStats):
    """Worker function for checking backend health"""
    try:
        health_monitor = BackendHealthMonitor(config_dir=config.get("config_dir"))
        health_result = health_monitor.check_backend_health_sync(backend_name)
        
        result = {
            "backend": backend_name,
            "status": "healthy",
            "response_time": time.time() - start_time,
            "details": health_result
        }
        
        stats.update_request_count(1)
        stats.update_success_count(1)
        result_queue.put(result)
    except Exception as e:
        logger.error(f"Health check worker error: {e}")
```

## Installation and Setup

### Prerequisites

- Python 3.8+ with multiprocessing support
- IPFS node (optional for full functionality)
- Required Python packages (see requirements.txt)

### Installation

```bash
# Clone repository
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py

# Install dependencies
pip install -r requirements.txt

# Install IPFS-Kit
pip install -e .
```

### Configuration

1. **Create configuration directory**:
```bash
mkdir -p /tmp/ipfs_kit_config
```

2. **Generate default configuration**:
```bash
python ipfs_kit_daemon.py --config /tmp/ipfs_kit_config/daemon.json
```

3. **Configure backends** in the generated configuration file

### Starting Services

1. **Start the daemon**:
```bash
python ipfs_kit_daemon.py --config /tmp/ipfs_kit_config/daemon.json
```

2. **Start enhanced MCP server**:
```bash
python enhanced_multiprocessing_mcp_server.py --workers 4
```

3. **Use enhanced CLI**:
```bash
python enhanced_multiprocessing_cli.py ipfs add file1,file2,file3 --parallel
```

## Usage Guide

### Daemon Operations

#### Start Daemon
```bash
# Foreground mode
python ipfs_kit_daemon.py

# With custom config
python ipfs_kit_daemon.py --config /path/to/config.json

# With debug logging
python ipfs_kit_daemon.py --debug
```

#### Check Daemon Status
```bash
python ipfs_kit_daemon.py --status
```

#### Stop Daemon
```bash
python ipfs_kit_daemon.py --stop
```

### MCP Server Operations

#### Start Enhanced MCP Server
```bash
# Default configuration
python enhanced_multiprocessing_mcp_server.py

# Custom worker count
python enhanced_multiprocessing_mcp_server.py --workers 8

# Custom VFS workers
python enhanced_multiprocessing_mcp_server.py --vfs-workers 4
```

#### Server Configuration Options
- `--workers`: Number of Uvicorn worker processes
- `--vfs-workers`: Number of VFS process pool workers
- `--backend-workers`: Number of backend process pool workers
- `--host`: Server host address
- `--port`: Server port
- `--debug`: Enable debug logging

### CLI Operations

#### Basic Operations
```bash
# Add files in parallel
python enhanced_multiprocessing_cli.py ipfs add file1.txt,file2.txt,file3.txt --parallel

# Check backend health
python enhanced_multiprocessing_cli.py backend health --parallel

# Optimize routes
python enhanced_multiprocessing_cli.py route optimize QmHash1,QmHash2,QmHash3

# Pin management
python enhanced_multiprocessing_cli.py pin add QmHash1,QmHash2 --parallel
python enhanced_multiprocessing_cli.py pin remove QmHash1,QmHash2 --parallel
```

#### Advanced Options
- `--workers`: Override number of worker processes
- `--parallel`: Enable parallel processing
- `--progress`: Show progress bars
- `--debug`: Enable debug logging
- `--timeout`: Set operation timeout

### Programming API

#### Daemon API
```python
from ipfs_kit_daemon import IPFSKitDaemon

# Create daemon instance
daemon = IPFSKitDaemon(config_file="/path/to/config.json")

# Start daemon
await daemon.start()

# Get status
status = daemon.get_status()

# Get backend health
health = daemon.get_backend_health("ipfs")

# Restart backend
result = await daemon.restart_backend("ipfs")
```

#### Enhanced MCP Server API
```python
from enhanced_multiprocessing_mcp_server import EnhancedMultiprocessingMCPServer

# Create server
server = EnhancedMultiprocessingMCPServer(host="127.0.0.1", port=8888, workers=4)

# Start process pools
server.start_process_pools()

# Get server statistics
stats = server.get_server_stats()

# Cleanup
await server.cleanup()
```

#### Enhanced CLI API
```python
from enhanced_multiprocessing_cli import EnhancedMultiprocessingCLI

# Create CLI instance
cli = EnhancedMultiprocessingCLI(max_workers=8)

# Add files in parallel
results = await cli.add_files_batch(["file1.txt", "file2.txt"])

# Check backend health
health = await cli.check_backend_health_parallel(["ipfs", "cluster"])

# Get statistics
stats = cli.get_stats()
```

## Performance Benchmarks

### Test Environment
- **System**: 40 CPU cores
- **Python**: 3.12
- **Platform**: Linux

### CPU-Intensive Workloads

| Method | Workers | Duration (s) | Throughput | Speedup |
|--------|---------|--------------|------------|---------|
| Sequential | 1 | 1.04 | 19.2 | 1.0x |
| Multiprocessing | 2 | 0.58 | 34.3 | 1.8x |
| Multiprocessing | 4 | 0.30 | 58.0 | 3.0x |
| Multiprocessing | 8 | 0.30 | 65.1 | **3.4x** |
| Multiprocessing | 40 | 0.48 | 25.1 | 1.6x |

**Key Insights**:
- Optimal performance at 8 workers (CPU cores / 5)
- Diminishing returns beyond optimal worker count
- 42.5% parallel efficiency at peak performance

### I/O-Intensive Workloads

| Method | Concurrency | Duration (s) | Throughput | Speedup |
|--------|-------------|--------------|------------|---------|
| Sequential | 1 | 0.51 | 99.1 | 1.0x |
| Threading | 10 | 0.05 | 936.9 | **9.4x** |
| Async | 25 | 0.02 | 2275.8 | **22.9x** |

**Key Insights**:
- Async processing provides best I/O performance
- Threading shows significant improvement over sequential
- High concurrency levels beneficial for I/O operations

### Memory Usage

- **Initial Memory**: ~100 MB
- **Peak Memory**: ~137 MB
- **Memory Overhead**: ~37 MB for multiprocessing
- **Memory Efficiency**: Shared state minimizes per-worker overhead

### Load Balancing

The system automatically optimizes worker distribution:

- **Light Load (10 ops)**: 2 workers, 2.0x speedup
- **Medium Load (50 ops)**: 4 workers, 4.2x speedup  
- **Heavy Load (100 ops)**: 8 workers, 3.4x speedup

## Testing

### Test Suite Overview

The project includes comprehensive test suites:

1. **Unit Tests**: Individual component testing
2. **Integration Tests**: End-to-end workflow testing
3. **Performance Tests**: Multiprocessing benchmark testing
4. **Regression Tests**: Ensuring stability across updates

### Running Tests

#### Comprehensive Test Suite
```bash
python test_daemon_multiprocessing_comprehensive.py
```

Expected output:
```
🚀 Starting IPFS-Kit Daemon Test Suite
============================================================
✅ Basic Daemon Functionality: 0.01s
✅ Enhanced Daemon Creation: 0.02s
✅ Multiprocessing MCP Server: 0.15s
✅ Multiprocessing CLI: 0.12s
✅ Process Stats Tracking: 0.01s
✅ Configuration Management: 0.01s
✅ Process Pool Management: 0.08s
✅ Error Handling: 0.03s
✅ System Resource Detection: 0.01s

Test Summary:
Total Tests: 9
Passed: 9
Failed: 0
Success Rate: 100.0%
Total Duration: 0.44s
```

#### Performance Test Suite
```bash
python test_performance_multiprocessing.py
```

Expected output:
```
🚀 Starting Comprehensive Performance Tests
System: 40 CPU cores detected
============================================================
🔥 Running CPU Performance Tests
💾 Running I/O Performance Tests
⚖️ Running Load Balancing Tests

Performance Summary:
CPU Performance:
  Best Speedup: 3.4x
  Efficiency: 42.5%
  Optimal Workers: 8

I/O Performance:
  Threading Speedup: 9.4x
  Async Speedup: 22.9x

System Resources:
  CPU Cores: 40
  Memory Usage: 37.5 MB
```

#### Individual Component Tests
```bash
# Test daemon functionality
python test_daemon_startup.py

# Test multiprocessing suite
python test_multi_processing_suite.py

# Test enhanced demo
python demo_enhanced_multiprocessing.py
```

### Test Configuration

Create test configuration file at `/tmp/ipfs_kit_config/test_daemon.json`:

```json
{
  "daemon": {
    "health_check_interval": 5,
    "replication_check_interval": 10,
    "log_rotation_interval": 30
  },
  "backends": {
    "ipfs": {"enabled": true, "auto_start": false}
  },
  "replication": {"enabled": false},
  "monitoring": {"health_checks": true}
}
```

## API Reference

### IPFSKitDaemon Class

#### Constructor
```python
IPFSKitDaemon(config_file: Optional[str] = None)
```

#### Methods

##### `async start() -> bool`
Start the daemon with all background services.

**Returns**: `bool` - Success status

##### `get_status() -> Dict[str, Any]`
Get comprehensive daemon status.

**Returns**: 
```python
{
    "daemon": {...},      # Daemon status
    "backends": {...},    # Backend status
    "replication": {...}, # Replication status
    "config": {...}       # Current configuration
}
```

##### `get_backend_health(backend_name: Optional[str] = None) -> Dict[str, Any]`
Get backend health status.

**Parameters**:
- `backend_name`: Specific backend name (optional)

**Returns**: Backend health information

##### `async restart_backend(backend_name: str) -> Dict[str, Any]`
Restart a specific backend.

**Parameters**:
- `backend_name`: Name of backend to restart

**Returns**: Operation result

### EnhancedMultiprocessingMCPServer Class

#### Constructor
```python
EnhancedMultiprocessingMCPServer(host: str = "127.0.0.1", port: int = 8888, workers: Optional[int] = None)
```

#### Methods

##### `start_process_pools()`
Initialize all process pools for parallel operations.

##### `get_server_stats() -> Dict[str, Any]`
Get comprehensive server statistics.

##### `async cleanup()`
Clean up all resources and shutdown gracefully.

### EnhancedMultiprocessingCLI Class

#### Constructor
```python
EnhancedMultiprocessingCLI(max_workers: int = 8)
```

#### Methods

##### `async add_files_batch(file_paths: List[str]) -> List[Dict[str, Any]]`
Add multiple files to IPFS in parallel.

##### `async check_backend_health_parallel(backends: List[str]) -> Dict[str, Any]`
Check health of multiple backends in parallel.

##### `get_stats() -> Dict[str, Any]`
Get CLI operation statistics.

## CI/CD Pipeline

### Overview

IPFS-Kit includes a comprehensive CI/CD pipeline that ensures code quality, security, and reliable deployments. The pipeline consists of multiple stages that run automatically on code changes.

### Pipeline Stages

#### 1. Code Quality and Security
- **Linting**: Black, isort, flake8 for code formatting and style
- **Security Scanning**: Bandit for security vulnerabilities, Safety for dependency vulnerabilities
- **Type Checking**: MyPy for static type analysis

#### 2. Testing
- **Unit Tests**: Comprehensive test suite across Python 3.9, 3.10, and 3.11
- **Integration Tests**: Full daemon and API testing
- **Performance Tests**: Multiprocessing benchmarks and performance regression detection
- **Docker Tests**: Container functionality and health checks

#### 3. Build and Package
- **Docker Images**: Multi-platform builds (linux/amd64, linux/arm64)
- **Container Registry**: Automatic publishing to GitHub Container Registry
- **Vulnerability Scanning**: Trivy security scanning of container images

#### 4. Deployment
- **Staging Deployment**: Automatic deployment to staging environment
- **Release Creation**: Automated GitHub releases for tagged versions
- **Image Cleanup**: Automatic cleanup of old container images

### Running the Pipeline

#### Local Testing
```bash
# Run linting
black --check .
isort --check-only .
flake8 .

# Run security checks
bandit -r .
safety check

# Run tests
python test_daemon_multiprocessing_comprehensive.py
python test_performance_multiprocessing.py
```

#### Docker Testing
```bash
# Build and test container
docker build -f docker/Dockerfile.enhanced -t ipfs-kit:test .
docker run --rm ipfs-kit:test daemon-only
```

#### Performance Benchmarks
```bash
# Run performance tests
python test_performance_multiprocessing.py --benchmark

# Expected results:
# - 3.4x CPU speedup with multiprocessing
# - 22.9x I/O performance improvement
# - Memory usage optimization
```

### Workflow Triggers

The CI/CD pipeline is triggered by:

1. **Push Events**: On main, master, develop, and new_cope branches
2. **Pull Requests**: For code review and validation
3. **Tag Creation**: For release builds (v*)
4. **Scheduled Runs**: Daily health checks and performance monitoring

### Monitoring and Notifications

- **GitHub Actions**: All workflow runs visible in GitHub Actions tab
- **Security Alerts**: Automated security vulnerability notifications
- **Performance Tracking**: Performance regression detection and reporting
- **Health Checks**: Daily automated health monitoring

### Release Process

#### Automatic Releases
```bash
# Tag a release
git tag v1.2.3
git push origin v1.2.3

# Pipeline automatically:
# 1. Runs full test suite
# 2. Builds multi-platform Docker images
# 3. Performs security scans
# 4. Creates GitHub release
# 5. Publishes to container registry
```

#### Manual Deployment
```bash
# Deploy to staging
gh workflow run enhanced-ci-cd.yml --ref main

# Deploy specific version
docker pull ghcr.io/endomorphosis/ipfs_kit_py:v1.2.3
docker run ghcr.io/endomorphosis/ipfs_kit_py:v1.2.3
```

### Configuration

#### GitHub Secrets Required
- `GITHUB_TOKEN`: Automatic (provided by GitHub)

#### Environment Variables
```yaml
REGISTRY: ghcr.io
IMAGE_NAME: ${{ github.repository }}
```

#### Workflow Files
- `.github/workflows/enhanced-ci-cd.yml`: Main CI/CD pipeline
- `.github/workflows/daemon-tests.yml`: Specialized daemon testing
- `docker/Dockerfile.enhanced`: Multi-stage container build
- `docker/docker-compose.enhanced.yml`: Multi-container deployment

### Common Issues

#### 1. Daemon Won't Start

**Symptoms**: Daemon fails to start with connection errors

**Solutions**:
```bash
# Check if IPFS daemon is running
ipfs id

# Check port availability
netstat -tulpn | grep :5001

# Verify configuration
python ipfs_kit_daemon.py --config /path/to/config.json --debug
```

#### 2. Poor Multiprocessing Performance

**Symptoms**: No performance improvement with multiprocessing

**Diagnosis**:
```python
import multiprocessing as mp
print(f"CPU count: {mp.cpu_count()}")
print(f"Multiprocessing context: {mp.get_context()}")
```

**Solutions**:
- Ensure sufficient CPU cores
- Adjust worker count: `workers = min(mp.cpu_count(), 8)`
- Check for GIL-bound operations
- Use ProcessPoolExecutor for CPU-intensive tasks
- Use ThreadPoolExecutor for I/O-intensive tasks

#### 3. Memory Issues

**Symptoms**: High memory usage or out-of-memory errors

**Solutions**:
```python
# Monitor memory usage
import psutil
process = psutil.Process()
print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")

# Reduce worker count
workers = min(mp.cpu_count() // 2, 4)

# Use spawn context to avoid memory sharing issues
mp_context = mp.get_context('spawn')
```

#### 4. Process Pool Deadlocks

**Symptoms**: Operations hang indefinitely

**Solutions**:
```python
# Use timeouts
with ProcessPoolExecutor(max_workers=4) as executor:
    future = executor.submit(task)
    try:
        result = future.result(timeout=30)
    except TimeoutError:
        logger.error("Task timed out")

# Avoid shared state in worker functions
# Use multiprocessing.Manager for shared data
```

#### 5. Configuration Issues

**Symptoms**: Invalid configuration errors

**Solutions**:
```bash
# Validate configuration
python -c "
import json
with open('/path/to/config.json') as f:
    config = json.load(f)
print('Configuration valid')
"

# Reset to defaults
rm /path/to/config.json
python ipfs_kit_daemon.py  # Regenerates default config
```

### Performance Optimization

#### 1. Worker Count Tuning

```python
# For CPU-intensive tasks
cpu_workers = min(mp.cpu_count(), 8)

# For I/O-intensive tasks  
io_workers = min(mp.cpu_count() * 2, 20)

# For mixed workloads
mixed_workers = min(mp.cpu_count(), 6)
```

#### 2. Memory Optimization

```python
# Use shared memory for large data
from multiprocessing import shared_memory

# Limit process pool size
max_workers = min(mp.cpu_count(), 4)

# Use spawn context to avoid memory issues
mp_context = mp.get_context('spawn')
```

#### 3. I/O Optimization

```python
# Use async for high-concurrency I/O
import asyncio

async def process_many_io_tasks(tasks):
    semaphore = asyncio.Semaphore(50)  # Limit concurrency
    
    async def limited_task(task):
        async with semaphore:
            return await process_task(task)
    
    return await asyncio.gather(*[limited_task(task) for task in tasks])
```

### Logging and Debugging

#### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or via command line
python ipfs_kit_daemon.py --debug
```

#### Monitor Process Activity

```bash
# Monitor system resources
htop

# Monitor IPFS Kit processes
ps aux | grep ipfs_kit

# Monitor network connections
netstat -tulpn | grep python
```

#### Log Files

Default log locations:
- Daemon logs: `/tmp/ipfs_kit_logs/ipfs_kit_daemon.log`
- MCP server logs: `/tmp/ipfs_kit_logs/enhanced_mcp_server.log`
- CLI logs: `/tmp/ipfs_kit_logs/enhanced_cli.log`

### Support

For additional support:

1. **Check the logs** for detailed error messages
2. **Run tests** to verify system functionality
3. **Review configuration** for correct settings
4. **Monitor system resources** for bottlenecks
5. **Update dependencies** to latest versions

### Version Information

- **IPFS-Kit Version**: 1.0.0
- **Python Requirements**: 3.8+
- **Key Dependencies**: 
  - `psutil` for system monitoring
  - `uvicorn` for MCP server
  - `rich` for enhanced CLI output
  - `asyncio` for async operations

---

This documentation provides comprehensive coverage of the IPFS-Kit daemon architecture and multiprocessing enhancements. For the latest updates and additional examples, refer to the project repository and test suites.
