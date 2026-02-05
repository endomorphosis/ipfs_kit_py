# Integration Quick Start Guide

This guide provides step-by-step instructions for using the ipfs_datasets_py and ipfs_accelerate_py integrations in IPFS Kit Python.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start Examples](#quick-start-examples)
- [Common Use Cases](#common-use-cases)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)

## Prerequisites

- Python 3.8+
- IPFS Kit Python installed
- IPFS daemon running (for distributed storage)

## Installation

### Option 1: Without Integrations (Default)
```bash
pip install ipfs-kit-py
# Everything works with local storage and standard compute
```

### Option 2: With Dataset Storage
```bash
pip install ipfs-kit-py ipfs_datasets_py
# Enables distributed, immutable storage across IPFS
```

### Option 3: With Compute Acceleration
```bash
pip install ipfs-kit-py
git submodule update --init external/ipfs_accelerate_py
# Enables 2-5x faster AI/ML operations
```

### Option 4: Full Integration
```bash
pip install ipfs-kit-py ipfs_datasets_py
git submodule update --init external/ipfs_accelerate_py
# Both distributed storage AND compute acceleration
```

## Quick Start Examples

### 1. Enable Dataset Storage for MCP Server

```python
from ipfs_kit_py.mcp.enhanced_server import EnhancedMCPServer

# Create server with dataset storage
server = EnhancedMCPServer(
    host="127.0.0.1",
    port=8001,
    enable_dataset_storage=True,  # Enable ipfs_datasets_py
    dataset_batch_size=100,       # Operations per batch
    ipfs_client=your_ipfs_client  # Optional IPFS client
)

# All MCP commands are automatically tracked!
# Results stored as datasets with CIDs
```

### 2. Enable Compute Acceleration for AI Operations

```python
from ipfs_kit_py.mcp.ai.framework_integration import HuggingFaceIntegration, HuggingFaceConfig

config = HuggingFaceConfig(
    name="my-model",
    model_id="gpt2",
    use_local=True
)

integration = HuggingFaceIntegration(config)
integration.initialize()

# Automatically uses ipfs_accelerate_py if available
result = integration.text_generation("Hello, world!")
# 2-5x faster with acceleration, graceful fallback without it
```

### 3. Track VFS Operations

```python
from ipfs_kit_py.bucket_vfs_manager import BucketVFSManager

manager = BucketVFSManager(
    base_path="~/.ipfs_kit/vfs",
    enable_dataset_storage=True,   # Track operations as datasets
    enable_compute_layer=True,     # Use acceleration if available
    dataset_batch_size=100
)

# Create bucket - operation tracked automatically
bucket = manager.create_bucket("my-bucket")

# Add files - tracked automatically
manager.add_file_to_bucket("my-bucket", "file.txt", b"content")

# All operations stored as immutable datasets!
```

### 4. Enable Dataset Storage for Logging

```python
from ipfs_kit_py.log_manager import LogManager

log_mgr = LogManager(
    enable_dataset_storage=True,
    ipfs_client=ipfs_client,
    dataset_batch_size=50
)

# Store logs as versioned datasets
result = log_mgr.store_logs_as_dataset(
    component="my-service",
    version="1.0.0"
)

print(f"Logs stored with CID: {result['cid']}")
```

### 5. Check Dependency Availability

```python
from ipfs_kit_py.mcp.ai.utils import check_dependencies

deps = check_dependencies()

print("Dependency Status:")
print(f"  ipfs_datasets_py: {deps['ipfs_datasets_py']}")
print(f"  ipfs_accelerate_py: {deps['ipfs_accelerate_py']}")
print(f"  torch: {deps['torch']}")
print(f"  transformers: {deps['transformers']}")

# All return bool, never raise exceptions
```

## Common Use Cases

### Use Case 1: Audit Trail for Compliance

```python
from ipfs_kit_py.mcp.auth.audit_logging import AuditLogger

# Enable immutable audit logging
logger = AuditLogger(
    log_file="/var/log/audit.log",
    enable_dataset_storage=True,
    ipfs_client=ipfs_client,
    dataset_batch_size=100
)

# Log authentication events
logger.log_auth_success("user123", "192.168.1.1")
logger.log_auth_failure("badactor", "10.0.0.1", "Invalid password")

# Logs stored as immutable datasets - tamper-proof!
# Perfect for regulatory compliance (GDPR, CCPA, HIPAA)
```

### Use Case 2: Performance Monitoring

```python
from ipfs_kit_py.wal_telemetry import WALTelemetry

telemetry = WALTelemetry(
    wal=wal_instance,
    metrics_path="~/.ipfs_kit/metrics",
    enable_dataset_storage=True,
    dataset_batch_size=200
)

# Metrics automatically stored as time-series datasets
# Query historical performance data from datasets
```

### Use Case 3: VFS Version Control

```python
from ipfs_kit_py.vfs_version_tracker import VFSVersionTracker

tracker = VFSVersionTracker(
    base_path="~/.ipfs_kit/versions",
    enable_dataset_storage=True,
    ipfs_client=ipfs_client
)

# Create version snapshot
version = tracker.create_version_snapshot(
    bucket_name="my-bucket",
    version_id="v1.0.0",
    metadata={"author": "alice"}
)

# All versions stored as datasets with complete provenance
```

### Use Case 4: Distributed Training Coordination

```python
from ipfs_kit_py.mcp.ai.distributed_training import DistributedTrainingManager

manager = DistributedTrainingManager(
    storage_path="/path/to/storage",
    enable_compute_layer=True  # Use acceleration
)

# Create training job
job = manager.create_job(
    name="model-training",
    config={"lr": 0.001, "epochs": 10},
    framework="pytorch"
)

# Start job with accelerated compute
manager.start_job(job.job_id)
# 2-5x faster with ipfs_accelerate_py
```

## Troubleshooting

### Issue: Dataset storage not working

**Check if ipfs_datasets_py is available:**
```python
from ipfs_kit_py.mcp.ai.utils import check_dependencies
deps = check_dependencies()
if not deps['ipfs_datasets_py']:
    print("ipfs_datasets_py not installed")
    print("Install with: pip install ipfs_datasets_py")
```

**Solution:** Install ipfs_datasets_py or disable dataset storage

### Issue: Compute acceleration not active

**Check if ipfs_accelerate_py is available:**
```python
deps = check_dependencies()
if not deps['ipfs_accelerate_py']:
    print("ipfs_accelerate_py not available")
    print("Initialize with: git submodule update --init external/ipfs_accelerate_py")
```

**Solution:** Initialize submodule or operations will use standard compute

### Issue: CI/CD tests failing

**This shouldn't happen!** All integrations have graceful fallbacks.

**Check test output:**
```bash
python -m pytest tests/ -v
# Tests should skip gracefully if dependencies unavailable
```

**Common causes:**
- Hard dependency on optional package (shouldn't exist in our code)
- Import error in test (check test file)

**Solution:** Report as bug if tests fail due to missing optional dependencies

### Issue: Performance not improving with acceleration

**Verify acceleration is active:**
```python
from ipfs_kit_py.mcp.ai.framework_integration import HAS_ACCELERATE
print(f"Acceleration available: {HAS_ACCELERATE}")
```

**Check compute layer is enabled:**
```python
# In your code initialization
integration = HuggingFaceIntegration(
    config,
    enable_compute_layer=True  # Make sure this is True
)
```

**Verify operations use acceleration:**
- Check logs for "using ipfs_accelerate_py" messages
- Monitor performance metrics

## Performance Tuning

### Batch Size Optimization

Dataset storage uses batching for performance:

```python
# Small batch - more frequent storage, less memory
manager = Manager(
    enable_dataset_storage=True,
    dataset_batch_size=50  # Good for: real-time tracking, low memory
)

# Medium batch - balanced
manager = Manager(
    enable_dataset_storage=True,
    dataset_batch_size=100  # Good for: most use cases (DEFAULT)
)

# Large batch - less frequent storage, more memory
manager = Manager(
    enable_dataset_storage=True,
    dataset_batch_size=500  # Good for: high-throughput, batch operations
)
```

**Guidelines:**
- Real-time tracking: 50-100
- Standard operations: 100-200
- Batch processing: 200-1000
- High throughput: 500-1000

### Manual Flushing

Don't wait for buffer to fill - flush manually when needed:

```python
# After critical operations
server.flush_to_dataset()

# Before shutdown
try:
    # ... operations ...
finally:
    server.flush_to_dataset()  # Ensure all data stored
```

### Memory Management

```python
# Monitor buffer size
current_buffer = len(server._operation_buffer)
if current_buffer > 500:
    server.flush_to_dataset()  # Prevent memory buildup
```

### IPFS Client Optimization

```python
# Use persistent IPFS client
import ipfshttpclient

ipfs_client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001')

# Reuse across all integrations
server = EnhancedMCPServer(
    enable_dataset_storage=True,
    ipfs_client=ipfs_client  # Reuse connection
)

logger = AuditLogger(
    enable_dataset_storage=True,
    ipfs_client=ipfs_client  # Same connection
)
```

## Best Practices

1. **Start with defaults** - Enable integrations, use default batch sizes
2. **Monitor performance** - Check logs and metrics to tune
3. **Use graceful fallbacks** - Don't require optional dependencies
4. **Manual flush critical data** - Don't rely only on automatic batching
5. **Reuse IPFS clients** - One client for multiple integrations
6. **Check dependencies at startup** - Log availability for debugging
7. **Test without dependencies** - Ensure graceful fallbacks work
8. **Document your usage** - Note which integrations you enable

## Next Steps

- Read `COMPLETE_INTEGRATION_SUMMARY.md` for complete list of integrations
- See `MCP_INTEGRATION_ARCHITECTURE.md` for architecture details
- Check `docs/IPFS_DATASETS_COMPREHENSIVE_INTEGRATION.md` for comprehensive reference
- Review `docs/INTEGRATION_OVERVIEW.md` for high-level overview

## Support

For issues or questions:
- Check troubleshooting section above
- Review test files for examples: `tests/test_ipfs_datasets_*.py`
- Check documentation: `docs/` directory
- Report bugs with detailed error messages

