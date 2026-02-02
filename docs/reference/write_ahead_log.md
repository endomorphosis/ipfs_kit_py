# IPFS Kit Write-Ahead Log (WAL) System

## Overview

The Write-Ahead Log (WAL) system in IPFS Kit provides fault tolerance and durability for storage operations. It ensures that operations are safely recorded before execution and can be recovered in case of failures. This is particularly important for distributed systems where backends may become temporarily unavailable.

The WAL system follows the fundamental principle of writing operation details to a durable log before attempting to execute the operation. This approach ensures that no operations are lost due to system crashes, network outages, or backend service failures. When a storage operation fails, the WAL automatically reschedules it for later execution, ensuring eventual consistency even in unstable environments.

## Key Features

- **Operation Durability**: Records operations before execution to ensure they can be recovered
- **Backend Health Monitoring**: Actively monitors the health of storage backends (IPFS, S3, Storacha)
- **Automatic Retry**: Automatically retries failed operations when backends recover
- **Efficient Storage**: Uses Apache Arrow and Parquet for efficient, cross-language compatible storage
- **Partitioning**: Implements efficient partitioning for managing large operation logs
- **Command-Line Interface**: Provides tools for monitoring and managing WAL operations
- **Visualization**: Offers comprehensive visualization and dashboards for monitoring
- **REST API Integration**: Exposes WAL functionality through a RESTful API
- **Performance Benchmarking**: Tools for measuring throughput, latency, and recovery capabilities

## Architecture

### Components

The WAL system is composed of several key components that work together to provide fault-tolerant storage operations:

1. **StorageWriteAheadLog** (`storage_wal.py`): Core WAL implementation
   - Manages the storage of operation logs using Apache Arrow and Parquet
   - Handles operation lifecycle (pending, processing, completed, failed)
   - Implements automatic retries for failed operations
   - Provides partitioning for efficient log management

2. **BackendHealthMonitor** (`storage_wal.py`): Monitoring storage backend health
   - Periodically checks the health of connected backends (IPFS, S3, Storacha)
   - Maintains health check history for pattern detection
   - Provides status information (online, offline, degraded)
   - Triggers operation processing when backends recover

3. **WALIntegration** (`wal_integration.py`): Integration with the high-level API
   - Provides decorators to wrap API methods with WAL functionality
   - Handles transparent operation queueing and result mapping
   - Manages WAL configuration and initialization

4. **WAL API** (`wal_api.py`): REST API extension
   - Adds WAL-specific endpoints to the FastAPI server
   - Provides operation management via REST API
   - Supports metrics retrieval and configuration updates

5. **WAL CLI** (`wal_cli.py`): Command-line interface for WAL management
   - Provides tools for monitoring and managing operations
   - Offers backend health checking capabilities
   - Supports operation retries and cleanup

6. **WAL CLI Integration** (`wal_cli_integration.py`): Integration with main CLI
   - Registers WAL commands with the main CLI system
   - Provides command handlers and argument parsing
   - Ensures consistent command behavior across interfaces

7. **WAL Visualization** (`wal_visualization.py`): Visualization and dashboards
   - Creates charts and visualizations for monitoring WAL performance
   - Generates HTML dashboards with operational insights
   - Supports time-based analysis of operation patterns

8. **WAL Performance Benchmark** (`wal_performance_benchmark.py`): Performance testing
   - Measures throughput, latency, and recovery capabilities
   - Tests performance across different backends
   - Generates detailed reports and visualizations

### Data Flow

The following diagram illustrates the data flow through the WAL system:

```
┌───────────────────┐          ┌───────────────────┐         ┌───────────────────┐
│  Client Request   │          │   High-Level API  │         │  Backend Services │
│  (add, pin, etc.) │──────────▶   (with WAL      │─────────▶  (IPFS, S3, etc.) │
└───────────────────┘          │  Integration)     │         └───────────────────┘
                              │└───────────────────┘                  ▲
                              │          │                            │
                              │          ▼                            │
                              │┌───────────────────┐                  │
                              ││   Operation Log   │                  │
                              ││  (Write to WAL)   │                  │
                              │└───────────────────┘                  │
                              │          │                            │
                              │          ▼                            │
                              │┌───────────────────┐                  │
                              ││  Background       │                  │
                              ││  Processing       │──────────────────┘
                              │└───────────────────┘
                              │          │
                              │          ▼
                              │┌───────────────────┐
                              ││ Status Updates    │
                              │└───────────────────┘
┌───────────────────┐        │           │         ┌───────────────────┐
│     WAL CLI       │◀───────┘           └────────▶│  Visualization    │
└───────────────────┘                              └───────────────────┘
```

### Operation Lifecycle

1. **Logging**: When an operation is requested, it's first logged to the WAL with status "pending".
2. **Processing**: A background thread retrieves pending operations and attempts to execute them.
3. **Status Updates**: As operations are processed, their status is updated (completed, failed, retrying).
4. **Retry**: Failed operations are automatically retried based on configuration settings.
5. **Archival**: Completed operations are optionally archived for historical tracking.

### Storage Schema

The WAL uses Apache Arrow for efficient data representation and Parquet for durable storage. The schema defines the structure of operation records:

```python
schema = pa.schema([
    # Operation identification
    pa.field('operation_id', pa.string()),
    pa.field('operation_type', pa.string()),  # add, pin, remove, etc.
    
    # Status and timing
    pa.field('status', pa.string()),  # pending, processing, completed, failed
    pa.field('timestamp', pa.timestamp('ms')),
    pa.field('updated_at', pa.timestamp('ms')),
    pa.field('completed_at', pa.timestamp('ms')),
    
    # Storage backend
    pa.field('backend', pa.string()),  # ipfs, s3, storacha
    
    # Operation details
    pa.field('parameters', pa.map_(pa.string(), pa.string())),
    pa.field('result', pa.struct([
        pa.field('cid', pa.string()),
        pa.field('size', pa.int64()),
        pa.field('destination', pa.string())
    ])),
    
    # Error tracking
    pa.field('error', pa.string()),
    pa.field('error_type', pa.string()),
    pa.field('retry_count', pa.int32()),
    pa.field('max_retries', pa.int32()),
    
    # Next retry
    pa.field('next_retry_at', pa.timestamp('ms')),
])
```

### Partitioning Strategy

The WAL implements partitioning to efficiently manage large operation logs:

1. **Partition File Format**: Operations are stored in Parquet files named `wal_[timestamp]_[counter].parquet`.
2. **Partition Size Limit**: Each partition holds up to a configured number of operations (default: 1000).
3. **New Partition Creation**: When a partition reaches its limit, a new one is created automatically.
4. **Archival**: Completed operations can be moved to archive partitions to keep active partitions smaller.
5. **Cleanup**: Older archived partitions can be removed based on age to manage disk usage.

## Usage Guide

### Basic Usage with High-Level API

The WAL is transparently integrated with the high-level API, making it easy to enable fault tolerance for your storage operations:

```python
from ipfs_kit_py import IPFSSimpleAPI

# Initialize API with WAL enabled
api = IPFSSimpleAPI(enable_wal=True)

# Operations are automatically logged to WAL
result = api.add("/path/to/file.txt")

# The result includes an operation ID for tracking
operation_id = result["operation_id"]
print(f"Operation ID: {operation_id}")
print(f"Current status: {result['status']}")

# Check operation status
status = api.get_wal_status(operation_id)
print(f"Operation status: {status['status']}")

# Wait for operation to complete
final_result = api.wait_for_operation(operation_id, timeout=60)
if final_result["success"]:
    print(f"Operation completed successfully: {final_result}")
else:
    print(f"Operation failed: {final_result.get('error')}")

# Check WAL statistics
stats = api.get_wal_stats()
print(f"Pending operations: {stats['stats']['pending']}")
print(f"Completed operations: {stats['stats']['completed']}")
print(f"Failed operations: {stats['stats']['failed']}")
```

### Batch Operations

You can also perform batch operations with WAL support:

```python
# Prepare a batch of files
files = ["/path/to/file1.txt", "/path/to/file2.txt", "/path/to/file3.txt"]

# Add all files to IPFS with WAL support
operation_ids = []
for file_path in files:
    result = api.add(file_path)
    operation_ids.append(result["operation_id"])

# Wait for all operations to complete
for operation_id in operation_ids:
    result = api.wait_for_operation(operation_id)
    print(f"Operation {operation_id}: {result['status']}")
```

### Command-Line Interface

The WAL CLI provides tools for monitoring and managing operations:

```bash
# Show WAL status and statistics
wal-cli status

# List pending operations
wal-cli list pending

# List operations by backend
wal-cli list pending --backend ipfs

# Show details of a specific operation
wal-cli show <operation_id>

# Wait for an operation to complete
wal-cli wait <operation_id> --timeout 60

# Retry a failed operation
wal-cli retry <operation_id>

# Clean up old operations
wal-cli cleanup

# Check backend health
wal-cli health

# Check specific backend health
wal-cli health --backend ipfs
```

You can also access WAL commands through the integrated CLI:

```bash
# Using the integrated CLI
ipfs-kit wal status
ipfs-kit wal list pending
ipfs-kit wal show <operation_id>
ipfs-kit wal wait <operation_id>
ipfs-kit wal health
```

### Visualization and Monitoring

The visualization module provides tools for monitoring WAL operations and backend health:

```python
from ipfs_kit_py import IPFSSimpleAPI
from ipfs_kit_py.wal_visualization import WALVisualization

# Initialize API and visualization
api = IPFSSimpleAPI()
vis = WALVisualization(api=api)

# Collect operation statistics
stats = vis.collect_operation_stats(timeframe_hours=24)

# Create specific visualizations
operation_chart = vis.create_operation_status_chart(stats)
backend_chart = vis.create_backend_health_chart(stats)
latency_chart = vis.create_operation_latency_chart(stats)

# Create dashboard with all visualizations
dashboard = vis.create_dashboard(stats)
print(f"Dashboard created. HTML report: {dashboard['html_report']}")

# Open the dashboard in a browser
import webbrowser
webbrowser.open(dashboard['html_report'])
```

You can also use the command-line tool for visualization:

```bash
# Create a dashboard for the last 24 hours
python -m ipfs_kit_py.wal_visualization --timeframe 24 --output /path/to/output

# Generate specific charts
python -m ipfs_kit_py.wal_visualization --chart operation_status --timeframe 24 --output /path/to/output
python -m ipfs_kit_py.wal_visualization --chart backend_health --timeframe 24 --output /path/to/output
python -m ipfs_kit_py.wal_visualization --chart operation_latency --timeframe 24 --output /path/to/output
```

### REST API

The WAL system exposes functionality through a RESTful API, making it accessible to other services and applications:

```
# List operations with optional filtering
GET /api/v0/wal/operations?status=pending&backend=ipfs&limit=10

# Get specific operation details
GET /api/v0/wal/operations/{operation_id}

# Retry a failed operation
POST /api/v0/wal/operations/{operation_id}/retry

# Get WAL metrics
GET /api/v0/wal/metrics

# Get WAL configuration
GET /api/v0/wal/config

# Update WAL configuration
POST /api/v0/wal/config
{
  "max_retries": 10,
  "retry_delay": 120,
  "archive_completed": true
}

# Delete an operation
DELETE /api/v0/wal/operations/{operation_id}
```

### Performance Benchmarking

The performance benchmarking tool helps you measure WAL system performance under various conditions:

```python
from ipfs_kit_py.examples.wal_performance_benchmark import WALBenchmark

# Create benchmark tool
benchmark = WALBenchmark()

# Benchmark single operations
results = benchmark.benchmark_add_operation(
    num_operations=100,
    file_size_kb=10,
    backends=["ipfs", "s3", "storacha"]
)

# Benchmark batch operations
batch_results = benchmark.benchmark_batch_operations(
    num_batches=10,
    batch_size=10,
    file_size_kb=10,
    backends=["ipfs", "s3", "storacha"]
)

# Benchmark recovery capabilities
recovery_results = benchmark.benchmark_recovery(
    num_operations=50,
    file_size_kb=10,
    failure_rate=0.2,
    backend="ipfs"
)

# Generate visualization plots
plots = benchmark.plot_results()

# Generate summary report
report_path = benchmark.generate_summary_report()
print(f"Benchmark report: {report_path}")
```

You can also run benchmarks from the command line:

```bash
# Run all benchmarks
python -m ipfs_kit_py.examples.wal_performance_benchmark --all --plots

# Run specific benchmarks
python -m ipfs_kit_py.examples.wal_performance_benchmark --add --num-operations 100 --file-size-kb 10
python -m ipfs_kit_py.examples.wal_performance_benchmark --batch --num-batches 10 --batch-size 10
python -m ipfs_kit_py.examples.wal_performance_benchmark --recovery --failure-rate 0.2

# Run benchmarks for specific backends
python -m ipfs_kit_py.examples.wal_performance_benchmark --add --backends ipfs s3
```

## Configuration

The WAL system can be configured through the high-level API to customize its behavior:

```python
config = {
    "wal": {
        # Basic configuration
        "enabled": True,                # Enable/disable WAL functionality
        "base_path": "~/.ipfs_kit/wal", # Base directory for WAL storage
        
        # Partitioning settings
        "partition_size": 1000,         # Maximum operations per partition
        
        # Retry behavior
        "max_retries": 5,               # Maximum retry attempts for failed operations
        "retry_delay": 60,              # Seconds between retry attempts
        "processing_interval": 10,      # Seconds between processing cycles
        
        # Storage management
        "archive_completed": True,      # Move completed operations to archive
        "cleanup_interval": 86400,      # Cleanup interval in seconds (24 hours)
        "max_age_days": 30,             # Maximum age of archived operations (days)
        
        # Health monitoring
        "health_check_interval": 60,    # Backend health check interval (seconds)
        "health_check_timeout": 10,     # Timeout for health check requests (seconds)
        "health_history_size": 25,      # Number of historical health checks to maintain
        
        # Backend-specific configuration
        "backends": {
            "ipfs": {
                "endpoint": "http://localhost:5001/api/v0",
                "connection_timeout": 5
            },
            "s3": {
                "region": "us-west-2",
                "connection_timeout": 10
            },
            "storacha": {
                "endpoint": "https://api.web3.storage",
                "connection_timeout": 15
            }
        }
    }
}

# Create API with custom WAL configuration
api = IPFSSimpleAPI(config=config)
```

You can also customize configuration through environment variables:

```bash
# Basic configuration
export IPFS_KIT_WAL_ENABLED=true
export IPFS_KIT_WAL_PATH=~/.ipfs_kit/wal

# Partitioning settings
export IPFS_KIT_WAL_PARTITION_SIZE=1000

# Retry behavior
export IPFS_KIT_WAL_MAX_RETRIES=5
export IPFS_KIT_WAL_RETRY_DELAY=60
export IPFS_KIT_WAL_PROCESS_INTERVAL=10

# Storage management
export IPFS_KIT_WAL_ARCHIVE_COMPLETED=true
export IPFS_KIT_WAL_CLEANUP_INTERVAL=86400
export IPFS_KIT_WAL_MAX_AGE_DAYS=30

# Health monitoring
export IPFS_KIT_WAL_HEALTH_CHECK_INTERVAL=60
export IPFS_KIT_WAL_HEALTH_HISTORY_SIZE=25
```

## Backend Health Monitoring

The WAL system includes a robust backend health monitoring component that continually tracks the health of connected storage backends:

### Key Features of Health Monitoring

1. **Periodic Health Checks**: Automatically tests the health of each backend at configurable intervals.
2. **Health History**: Maintains a history of health check results to detect patterns and transient issues.
3. **Status Classification**: Categorizes backends as:
   - **Online**: Backend is fully operational
   - **Degraded**: Backend is operational but showing signs of issues
   - **Offline**: Backend is not responding or encountering serious errors
4. **Automatic Recovery**: Triggers retry of operations when a previously offline backend becomes available.
5. **Intelligent Status Determination**: Uses multiple recent health checks to prevent false positives/negatives.

### Health Check Implementation

Each backend type has a specific health check implementation:

```python
# IPFS health check
def _check_ipfs_health(self, config):
    """Check if the IPFS daemon is responsive."""
    try:
        # Try to get the IPFS node ID
        response = requests.post(
            f"{config.get('endpoint', 'http://localhost:5001/api/v0')}/id",
            timeout=config.get('connection_timeout', 5)
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

# S3 health check
def _check_s3_health(self, config):
    """Check if the S3 service is responsive."""
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import ClientError
        
        # Create S3 client with timeout
        s3_config = Config(
            connect_timeout=config.get('connection_timeout', 10),
            retries={'max_attempts': 1}
        )
        s3 = boto3.client('s3', config=s3_config, region_name=config.get('region'))
        
        # Try to list buckets (simple operation to check service availability)
        s3.list_buckets()
        return True
    except (ImportError, ClientError):
        return False

# Storacha health check
def _check_storacha_health(self, config):
    """Check if the Storacha (Web3.Storage) service is responsive."""
    try:
        response = requests.get(
            f"{config.get('endpoint', 'https://api.web3.storage')}/status",
            timeout=config.get('connection_timeout', 15)
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False
```

### Monitoring Backend Health

You can monitor backend health through the API:

```python
# Get backend health status through the API
health_status = api.get_backend_health()
print("Backend Health:")
for backend, status in health_status.items():
    print(f"  {backend}: {status['status']}")
    print(f"    Last check: {datetime.fromtimestamp(status['last_check'])}")
    print(f"    Check history: {''.join('✓' if check else '✗' for check in status['check_history'])}")
```

Or through the CLI:

```bash
# Check health of all backends
wal-cli health

# Check specific backend
wal-cli health --backend ipfs
```

## Examples

Complete examples are available in the `examples` directory to help you get started with the WAL system:

### Basic WAL Usage

`examples/wal_high_level_api_example.py`: Demonstrates using the WAL with the high-level API

```python
from ipfs_kit_py import IPFSSimpleAPI
import time
import os

# Create a test file
test_file = "/tmp/test_file.txt"
with open(test_file, "w") as f:
    f.write("This is a test file for WAL example.")

# Initialize API with WAL enabled
api = IPFSSimpleAPI(enable_wal=True)

# Add file to IPFS through WAL
print("Adding file to IPFS...")
result = api.add(test_file)
print(f"Result: {result}")

# Get operation ID
operation_id = result["operation_id"]

# Check operation status
print("\nChecking operation status...")
status = api.get_wal_status(operation_id)
print(f"Status: {status}")

# Wait for operation to complete
print("\nWaiting for operation to complete...")
final_result = api.wait_for_operation(operation_id)
print(f"Final result: {final_result}")

# Check WAL statistics
print("\nWAL Statistics:")
stats = api.get_wal_stats()
print(f"Pending operations: {stats['stats']['pending']}")
print(f"Completed operations: {stats['stats']['completed']}")
print(f"Failed operations: {stats['stats']['failed']}")
```

### WAL CLI Example

`examples/wal_cli_example.py`: Demonstrates using the WAL CLI tools

```python
import subprocess
import time
import os

# Create a test file
test_file = "/tmp/test_file.txt"
with open(test_file, "w") as f:
    f.write("This is a test file for WAL CLI example.")

# Add file to IPFS
print("Adding file to IPFS...")
result = subprocess.run(
    ["python", "-m", "ipfs_kit_py.wal_cli", "add", test_file],
    capture_output=True,
    text=True
)
print(result.stdout)

# Extract operation ID from output
import json
output_lines = result.stdout.strip().split("\n")
for line in output_lines:
    if "Result:" in line:
        result_json = json.loads(line.replace("Result:", "").strip())
        operation_id = result_json.get("operation_id")
        break

# Check WAL status
print("\nChecking WAL status...")
subprocess.run(
    ["python", "-m", "ipfs_kit_py.wal_cli", "status"],
    text=True
)

# Show operation details
print(f"\nShowing operation details for {operation_id}...")
subprocess.run(
    ["python", "-m", "ipfs_kit_py.wal_cli", "show", operation_id],
    text=True
)

# Wait for operation to complete
print(f"\nWaiting for operation {operation_id} to complete...")
subprocess.run(
    ["python", "-m", "ipfs_kit_py.wal_cli", "wait", operation_id],
    text=True
)

# Check backend health
print("\nChecking backend health...")
subprocess.run(
    ["python", "-m", "ipfs_kit_py.wal_cli", "health"],
    text=True
)
```

### WAL Visualization Example

`examples/wal_visualization_example.py`: Demonstrates using the visualization module

```python
from ipfs_kit_py import IPFSSimpleAPI
from ipfs_kit_py.wal_visualization import WALVisualization
import os
import time

# Initialize API
api = IPFSSimpleAPI(enable_wal=True)

# Create some test operations
test_files = []
for i in range(10):
    test_file = f"/tmp/test_file_{i}.txt"
    with open(test_file, "w") as f:
        f.write(f"This is test file {i} for WAL visualization example.")
    test_files.append(test_file)
    api.add(test_file)

# Create visualization
vis = WALVisualization(api=api)

# Collect operation statistics
print("Collecting operation statistics...")
stats = vis.collect_operation_stats(timeframe_hours=24)
print(f"Collected stats for {len(stats.get('operations', []))} operations")

# Create operation status chart
print("Creating operation status chart...")
status_chart = vis.create_operation_status_chart(stats)
print(f"Chart saved to: {status_chart}")

# Create backend health chart
print("Creating backend health chart...")
health_chart = vis.create_backend_health_chart(stats)
print(f"Chart saved to: {health_chart}")

# Create latency chart
print("Creating operation latency chart...")
latency_chart = vis.create_operation_latency_chart(stats)
print(f"Chart saved to: {latency_chart}")

# Create dashboard with all visualizations
print("Creating dashboard...")
dashboard = vis.create_dashboard(stats)
print(f"Dashboard created. HTML report: {dashboard['html_report']}")
```

### WAL Performance Benchmark Example

`examples/wal_performance_benchmark.py`: Demonstrates benchmarking the WAL system

```python
from ipfs_kit_py.examples.wal_performance_benchmark import WALBenchmark, run_benchmarks
import argparse

# Create argument parser
parser = argparse.ArgumentParser(description="WAL Performance Benchmark Example")
parser.add_argument("--output-dir", default="./benchmark_results", help="Output directory for benchmark results")
parser.add_argument("--num-operations", type=int, default=100, help="Number of operations")
parser.add_argument("--file-size-kb", type=int, default=10, help="Size of test files in KB")
parser.add_argument("--plots", action="store_true", help="Generate plots")

# Parse arguments
args = parser.parse_args()

# Create benchmark tool
print("Creating WAL benchmark tool...")
benchmark = WALBenchmark(output_dir=args.output_dir)

# Run add operation benchmark
print(f"Benchmarking add operations ({args.num_operations} operations, {args.file_size_kb}KB files)...")
results = benchmark.benchmark_add_operation(
    num_operations=args.num_operations,
    file_size_kb=args.file_size_kb,
    backends=["ipfs", "s3", "storacha"]
)

# Run batch operations benchmark
print("Benchmarking batch operations...")
batch_results = benchmark.benchmark_batch_operations(
    num_batches=10,
    batch_size=10,
    file_size_kb=args.file_size_kb,
    backends=["ipfs", "s3", "storacha"]
)

# Run recovery benchmark
print("Benchmarking recovery capabilities...")
recovery_results = benchmark.benchmark_recovery(
    num_operations=50,
    file_size_kb=args.file_size_kb,
    failure_rate=0.2,
    backend="ipfs"
)

# Save results
results_path = benchmark.save_results()
print(f"Benchmark results saved to: {results_path}")

# Generate plots if requested
if args.plots:
    print("Generating visualization plots...")
    plots = benchmark.plot_results()
    for name, path in plots.items():
        if path:
            print(f"  {name}: {path}")

# Clean up
benchmark.cleanup()
```

### WAL CLI Integration Example

`examples/wal_cli_integration_example.py`: Demonstrates using the integrated WAL CLI

```python
import subprocess
import time
import os

# Create a test file
test_file = "/tmp/test_file.txt"
with open(test_file, "w") as f:
    f.write("This is a test file for WAL CLI integration example.")

# Add file to IPFS using integrated CLI
print("Adding file to IPFS...")
result = subprocess.run(
    ["python", "-m", "ipfs_kit_py.cli", "wal", "add", test_file],
    capture_output=True,
    text=True
)
print(result.stdout)

# Extract operation ID from output
import json
output_lines = result.stdout.strip().split("\n")
for line in output_lines:
    if "Result:" in line:
        result_json = json.loads(line.replace("Result:", "").strip())
        operation_id = result_json.get("operation_id")
        break

# Check WAL status using integrated CLI
print("\nChecking WAL status...")
subprocess.run(
    ["python", "-m", "ipfs_kit_py.cli", "wal", "status"],
    text=True
)

# Show operation details using integrated CLI
print(f"\nShowing operation details for {operation_id}...")
subprocess.run(
    ["python", "-m", "ipfs_kit_py.cli", "wal", "show", operation_id],
    text=True
)

# Wait for operation to complete using integrated CLI
print(f"\nWaiting for operation {operation_id} to complete...")
subprocess.run(
    ["python", "-m", "ipfs_kit_py.cli", "wal", "wait", operation_id],
    text=True
)

# Check backend health using integrated CLI
print("\nChecking backend health...")
subprocess.run(
    ["python", "-m", "ipfs_kit_py.cli", "wal", "health"],
    text=True
)
```

## Advanced Topics

### Handling Backend Failures

The WAL system is designed to handle a variety of backend failures:

#### Transient Network Issues

For temporary network issues, the WAL will automatically retry operations with exponential backoff:

```python
def _handle_transient_failure(self, operation_id, error, error_type):
    """Handle a transient failure for an operation."""
    # Get the operation
    operation = self.get_operation(operation_id)
    if not operation:
        return False
        
    # Check retry count
    retry_count = operation.get("retry_count", 0)
    max_retries = operation.get("max_retries", self.max_retries)
    
    if retry_count < max_retries:
        # Calculate next retry time with exponential backoff
        base_delay = self.retry_delay
        backoff_factor = min(2 ** retry_count, 10)  # Cap at 10x
        next_retry_delay = base_delay * backoff_factor
        next_retry_at = int(time.time() * 1000) + (next_retry_delay * 1000)
        
        # Update operation status
        self.update_operation_status(
            operation_id,
            OperationStatus.RETRYING,
            {
                "retry_count": retry_count + 1,
                "next_retry_at": next_retry_at,
                "error": error,
                "error_type": error_type
            }
        )
        return True
    else:
        # Max retries reached
        self.update_operation_status(
            operation_id,
            OperationStatus.FAILED,
            {
                "error": error,
                "error_type": error_type
            }
        )
        return False
```

#### Backend Service Outages

For backend service outages, the WAL uses the health monitoring system to detect when a backend becomes available again:

```python
def _process_pending_operations(self):
    """Process all pending operations."""
    # Get backend health status
    backend_status = self.health_monitor.get_status()
    
    # Get pending operations grouped by backend
    pending_ops_by_backend = {}
    for op in self.get_operations_by_status(OperationStatus.PENDING):
        backend = op.get("backend")
        if backend not in pending_ops_by_backend:
            pending_ops_by_backend[backend] = []
        pending_ops_by_backend[backend].append(op)
    
    # Process operations for healthy backends
    for backend, ops in pending_ops_by_backend.items():
        status = backend_status.get(backend, {}).get("status")
        if status == "online":
            for op in ops:
                self._process_operation(op["operation_id"])
        else:
            logger.info(f"Skipping {len(ops)} operations for {backend} backend (status: {status})")
```

#### Permanent Failures

For permanent failures, the WAL provides manual intervention options:

```python
def handle_permanent_failure(self, operation_id, new_backend=None):
    """Handle a permanent failure by potentially moving to a different backend.
    
    Args:
        operation_id: ID of the failed operation
        new_backend: Optional new backend to try
        
    Returns:
        New operation ID if redirected, or None if not possible
    """
    # Get the operation
    operation = self.get_operation(operation_id)
    if not operation:
        return None
        
    # Check if operation is failed
    if operation.get("status") != OperationStatus.FAILED.value:
        return None
        
    # If no new backend specified, mark as permanently failed
    if not new_backend:
        self.update_operation_status(
            operation_id,
            OperationStatus.FAILED,
            {
                "error_type": "permanent_failure",
                "error": "Operation marked as permanently failed"
            }
        )
        return None
        
    # Create a new operation with the same parameters but different backend
    new_operation = {
        "operation_type": operation.get("operation_type"),
        "parameters": operation.get("parameters", {}),
        "max_retries": operation.get("max_retries")
    }
    
    # Add to the new backend
    result = self.add_operation(
        operation_type=new_operation["operation_type"],
        backend=new_backend,
        parameters=new_operation["parameters"],
        max_retries=new_operation["max_retries"]
    )
    
    # Return the new operation ID
    return result.get("operation_id")
```

### Data Consistency Guarantees

The WAL system provides important data consistency guarantees:

#### Operation Atomicity

Each operation is treated as an atomic unit that either completes successfully or fails entirely. This atomicity ensures that data remains consistent even during failures.

#### Operation Durability

All operations are written to durable storage before execution, ensuring that they can be recovered and retried in case of failures.

#### Eventual Consistency

The WAL system implements an eventual consistency model. While operations may temporarily fail, the WAL will automatically retry them until they succeed (up to the configured retry limit). This ensures that operations eventually complete if the backend services recover.

#### Transaction Logs

All operation state transitions are logged, providing a complete audit trail of operation execution. This log can be used for troubleshooting and recovery purposes.

### Performance Considerations

The WAL system is designed for performance, but there are some considerations to keep in mind:

#### Throughput vs. Latency

The WAL introduces a small latency overhead for each operation to ensure durability. However, it enables higher overall throughput by allowing operations to be queued and processed asynchronously.

#### Batch Processing

For high-throughput workloads, consider using batch operations to amortize the overhead of WAL logging across multiple operations.

#### Partition Management

The partition size configuration affects memory usage and processing efficiency. Larger partitions reduce the frequency of new partition creation but may increase memory usage for in-memory operations.

#### Archival Strategy

Archiving completed operations improves the performance of active partitions but introduces additional I/O. Configure the archival strategy based on your performance and durability requirements.

#### Recovery Performance

Recovery performance depends on the number of pending operations and the health of the backend services. Monitor recovery performance using the benchmark tools to optimize your configuration.

## Development

### Adding a New Operation Type

To add a new operation type to the WAL system:

1. Define the operation type in the `OperationType` enum in `storage_wal.py`:

   ```python
   class OperationType(enum.Enum):
       """Types of operations that can be stored in the WAL."""
       # Existing types
       ADD = "add"
       GET = "get"
       PIN = "pin"
       UNPIN = "unpin"
       
       # New operation type
       MY_NEW_OPERATION = "my_new_operation"
   ```

2. Create the corresponding operation handler in the high-level API (`api.py`):

   ```python
   def my_new_operation(self, param1, param2, **kwargs):
       """Perform my new operation with WAL support.
       
       Args:
           param1: First parameter
           param2: Second parameter
           
       Returns:
           Operation result
       """
       # Implementation
       pass
   ```

3. Wrap the handler with the WAL integration decorator in `wal_api_extension.py`:

   ```python
   @wal_operation(operation_type=OperationType.MY_NEW_OPERATION, backend=BackendType.IPFS)
   def my_new_operation(self, param1, param2, **kwargs):
       """Perform my new operation with WAL support."""
       # Forward to the original implementation
       return self._api.my_new_operation(param1, param2, **kwargs)
   ```

4. Add the operation to the CLI in `wal_cli_integration.py`:

   ```python
   def register_wal_commands(subparsers):
       """Register WAL commands with the CLI."""
       # Existing commands
       
       # New operation command
       my_new_operation_parser = wal_subparsers.add_parser(
           "my_new_operation", 
           help="Perform my new operation"
       )
       my_new_operation_parser.add_argument(
           "param1",
           help="First parameter"
       )
       my_new_operation_parser.add_argument(
           "param2",
           help="Second parameter"
       )
   ```

5. Add command handler in `wal_cli_integration.py`:

   ```python
   def handle_wal_command(client, args):
       """Handle WAL commands."""
       # Existing handlers
       
       # Handle my_new_operation command
       if args.command == "my_new_operation":
           result = client.my_new_operation(args.param1, args.param2)
           print(json.dumps(result, indent=2))
           return result
   ```

6. Add appropriate tests and documentation:

   ```python
   def test_my_new_operation():
       """Test my new operation with WAL support."""
       api = IPFSSimpleAPI(enable_wal=True)
       result = api.my_new_operation("test_param1", "test_param2")
       assert result["success"] is True
       assert "operation_id" in result
       
       # Wait for operation to complete
       final_result = api.wait_for_operation(result["operation_id"])
       assert final_result["success"] is True
   ```

### Extending Backend Health Monitoring

To add support for monitoring a new backend type:

1. Add the backend type to the `BackendType` enum in `storage_wal.py`:

   ```python
   class BackendType(enum.Enum):
       """Types of storage backends."""
       # Existing backends
       IPFS = "ipfs"
       S3 = "s3"
       STORACHA = "storacha"
       
       # New backend
       MY_NEW_BACKEND = "my_new_backend"
   ```

2. Create a health check function for the backend in `storage_wal.py`:

   ```python
   def _check_my_new_backend_health(self, config):
       """Check if my new backend is responsive.
       
       Args:
           config: Backend configuration
           
       Returns:
           True if healthy, False otherwise
       """
       try:
           # Implementation specific to your backend
           # For example, make an API call to check status
           response = requests.get(
               f"{config.get('endpoint', 'https://api.mynewbackend.com')}/status",
               timeout=config.get('connection_timeout', 10)
           )
           return response.status_code == 200
       except requests.exceptions.RequestException:
           return False
   ```

3. Add the health check function to the `_check_backend` method in `BackendHealthMonitor`:

   ```python
   def _check_backend(self, backend):
       """Check the health of a specific backend."""
       try:
           # Get backend configuration
           config = self.backend_configs.get(backend, {})
           
           # Call the appropriate health check function
           if backend == BackendType.IPFS.value:
               healthy = self._check_ipfs_health(config)
           elif backend == BackendType.S3.value:
               healthy = self._check_s3_health(config)
           elif backend == BackendType.STORACHA.value:
               healthy = self._check_storacha_health(config)
           elif backend == BackendType.MY_NEW_BACKEND.value:
               healthy = self._check_my_new_backend_health(config)
           else:
               # Unknown backend
               healthy = False
           
           # Update backend status
           self._update_backend_status(backend, healthy)
           
       except Exception as e:
           logger.error(f"Error checking {backend} health: {e}")
           # Update backend status with error
           self._update_backend_status(backend, False, str(e))
   ```

4. Update the visualization components to display the new backend:

   ```python
   def create_backend_health_chart(self, stats):
       """Create a chart showing backend health status."""
       # Add color for new backend
       backend_colors = {
           "ipfs": "#3498DB",
           "s3": "#F1C40F",
           "storacha": "#9B59B6",
           "my_new_backend": "#2ECC71"  # Add color for new backend
       }
       
       # Rest of the implementation
   ```

5. Add tests for the new backend:

   ```python
   def test_my_new_backend_health_check():
       """Test health check for my new backend."""
       health_monitor = BackendHealthMonitor(
           backends=[BackendType.MY_NEW_BACKEND.value],
           backend_configs={
               BackendType.MY_NEW_BACKEND.value: {
                   "endpoint": "https://api.mynewbackend.com",
                   "connection_timeout": 10
               }
           }
       )
       
       # Mock the health check response
       with patch('requests.get') as mock_get:
           mock_response = MagicMock()
           mock_response.status_code = 200
           mock_get.return_value = mock_response
           
           # Check health
           health_monitor._check_backend(BackendType.MY_NEW_BACKEND.value)
           
           # Verify status
           status = health_monitor.get_status(BackendType.MY_NEW_BACKEND.value)
           assert status["status"] == "online"
   ```

## Troubleshooting

### Common Issues

1. **Operation Stuck in "Pending" State**: 
   - **Cause**: Backend might be offline or experiencing issues.
   - **Diagnosis**: Check backend health with `wal-cli health` or `api.get_backend_health()`.
   - **Solution**: If backend is offline, wait for it to come back online or consider moving the operation to another backend. If backend is online but operation is still pending, check for configuration issues or log errors.

2. **Excessive Disk Usage**:
   - **Cause**: Completed operations accumulating in the WAL.
   - **Diagnosis**: Check WAL statistics with `wal-cli status` or `api.get_wal_stats()`.
   - **Solution**: Run cleanup with `wal-cli cleanup` or `api.cleanup_wal()`. Adjust the `archive_completed` and `cleanup_interval` configurations.

3. **Performance Issues**:
   - **Cause**: Inefficient WAL configuration for the workload.
   - **Diagnosis**: Run benchmarks to identify bottlenecks.
   - **Solution**: Optimize configuration based on benchmark results. Consider reducing `partition_size`, increasing `processing_interval`, or using a faster disk for WAL storage.

4. **Backend Keeps Going Offline**:
   - **Cause**: Backend service may be unstable or misconfigured.
   - **Diagnosis**: Check health history with `wal-cli health` or `api.get_backend_health()`.
   - **Solution**: Adjust `health_check_interval` and `health_check_timeout` to better match backend characteristics. Consider adding more sophisticated health checks for the specific backend.

5. **WAL Processing Thread Not Running**:
   - **Cause**: Background processing thread may have stopped unexpectedly.
   - **Diagnosis**: Check if processing is active with `wal-cli status` or `api.get_wal_stats()`.
   - **Solution**: Restart the WAL or the entire application. If the issue persists, check logs for errors that might be causing the thread to terminate.

### Debugging

Enable debug logging for more detailed information:

```python
import logging
logging.getLogger('ipfs_kit_py.storage_wal').setLevel(logging.DEBUG)
```

Or use the `--debug` flag with CLI tools:

```bash
wal-cli --debug status
ipfs-kit wal --debug status
```

### Logging and Debugging Tips

1. **Examine Operation Lifecycle**:
   - Track the lifecycle of an operation from creation through completion or failure:
   ```python
   # Create operation
   result = api.add("/path/to/file.txt")
   operation_id = result["operation_id"]
   print(f"Created operation: {operation_id}")
   
   # Check initial status
   status = api.get_wal_status(operation_id)
   print(f"Initial status: {status}")
   
   # Wait a bit and check again
   time.sleep(5)
   status = api.get_wal_status(operation_id)
   print(f"Status after 5s: {status}")
   
   # Wait for completion
   final_result = api.wait_for_operation(operation_id)
   print(f"Final result: {final_result}")
   ```

2. **Monitor Health Check History**:
   - Watch the health check history to identify patterns in backend availability:
   ```python
   health_status = api.get_backend_health()
   for backend, status in health_status.items():
       print(f"Backend: {backend}")
       print(f"  Status: {status['status']}")
       print(f"  Health history: {''.join('✓' if check else '✗' for check in status['check_history'])}")
   ```

3. **Performance Analysis**:
   - Use the benchmarking tools to analyze performance under different conditions:
   ```bash
   python -m ipfs_kit_py.examples.wal_performance_benchmark --add --backends ipfs --num-operations 100 --plots
   ```

4. **Manual Operation Inspection**:
   - Directly examine WAL partitions for troubleshooting:
   ```python
   # Get path to current partition
   wal_path = "~/.ipfs_kit/wal/partitions"
   expanded_path = os.path.expanduser(wal_path)
   partition_files = [f for f in os.listdir(expanded_path) if f.endswith('.parquet')]
   
   # Read latest partition
   import pyarrow.parquet as pq
   latest_partition = os.path.join(expanded_path, sorted(partition_files)[-1])
   table = pq.read_table(latest_partition)
   print(f"Partition contents: {table.to_pandas()}")
   ```

## Related Documentation

- [High-Level API Documentation](high_level_api.md): Details on using the high-level API with WAL integration
- [Tiered Cache System](../reference/tiered_cache.md): Information on the caching system that works alongside the WAL
- [Backend Storage Systems](storage_backends.md): Documentation on the supported storage backends
- [Performance Metrics](performance_metrics.md): Details on measuring and monitoring performance
- [CLI Documentation](cli.md): Information on using the command-line interface
- [API Reference](api_reference.md): Complete reference for the REST API