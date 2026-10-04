# IPFS Backend Implementation

## Overview

This directory contains the IPFS backend implementation for the MCP storage manager. The backend provides a standardized interface for interacting with IPFS networks through the `BackendStorage` interface.

## Implementation Details

The IPFS backend implementation consists of:

- **IPFSBackend class** - Implements the `BackendStorage` interface for IPFS
- **ipfs_py reference implementation** - Provides the core IPFS functionality

## Dependency Resolution

The IPFS backend had a critical issue where it failed to initialize due to a missing `ipfs_py` client dependency. This issue has been fixed by:

1. Creating a dedicated reference implementation in `ipfs_kit_py/ipfs/ipfs_py.py`
2. Updating the import mechanism to properly locate this implementation
3. Adding multiple fallback strategies for robustness

## Key Features

- Content addition, retrieval, and pinning
- Metadata management
- Advanced performance monitoring
- WebSocket integration for real-time events
- Robust error handling

## Usage

```python
from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend

# Configure connection parameters
resources = {
    "ipfs_host": "127.0.0.1", 
    "ipfs_port": 5001,
    "ipfs_timeout": 30
}

# Optional metadata
metadata = {
    "backend_name": "my_ipfs_backend",
    "performance_metrics_file": "/path/to/metrics.json"
}

# Initialize the backend
ipfs_backend = IPFSBackend(resources, metadata)

# Add content
result = ipfs_backend.add_content("Hello, IPFS!")
cid = result.get("identifier")

# Retrieve content
content = ipfs_backend.get_content(cid)

# Get performance metrics
metrics = ipfs_backend.get_performance_metrics()
```

## Verification

You can verify the IPFS backend is working correctly using the provided test scripts:

```bash
# Verify IPFS dependency issue is fixed
./scripts/verify_ipfs_dependency.py

# Run comprehensive integration tests
./run_integration_tests.py --component ipfs
```

## Implementation Notes

- The backend supports both synchronous and asynchronous operation
- Performance monitoring tracks all operations
- Event notifications are sent through WebSocket
- Mock implementation is provided for environments without IPFS