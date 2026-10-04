# MCP Integration Tests

This directory contains integration tests for the MCP server components following the architecture consolidation completed in Q2 2025.

## Purpose

These tests verify that all components of the MCP server are functioning correctly within the unified codebase structure. The tests specifically address the reassessment requirements mentioned in the MCP roadmap.

## Test Files

- **`test_ipfs_backend.py`**: Verifies the IPFS backend implementation after fixing the dependency issues
  - Tests initialization, content operations, metadata handling, and performance monitoring
  - Can run in mock mode when IPFS daemon is not available

## Running the Tests

To run all integration tests:

```bash
cd /home/barberb/ipfs_kit_py
python -m unittest discover -s tests/integration
```

To run a specific test:

```bash
python -m unittest tests/integration/backends/test_ipfs_backend.py
```

## Verification Scripts

In addition to these tests, there are verification scripts in the `scripts` directory:

- **`verify_ipfs_backend.py`**: Script to verify the IPFS backend functionality
- **`verify_api_endpoints.py`**: Script to verify all API endpoints are working properly

These scripts can be run directly:

```bash
./scripts/verify_ipfs_backend.py
./scripts/verify_api_endpoints.py
```

## Test Environment

The tests can run in two modes:

1. **Real Mode**: Connects to actual services (IPFS daemon, etc.)
2. **Mock Mode**: Uses mock implementations when services are not available

Environment variables can be used to configure the test behavior:

- `MCP_TEST_MOCK=1`: Force mock mode for all tests
- `MCP_SERVER_URL`: Specify the MCP server URL for API tests (default: http://localhost:5000)