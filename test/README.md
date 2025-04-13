# Test Suite for IPFS Kit Python

This directory contains the test suite for the IPFS Kit Python package. The tests are organized into a hierarchical structure to improve maintainability and discoverability.

## Test Organization

The tests are organized as follows:

```
test/
├── unit/                       # Unit tests for individual components
│   ├── api/                    # API-related unit tests
│   ├── core/                   # Core functionality unit tests
│   ├── storage/                # Storage-related unit tests 
│   ├── ai_ml/                  # AI/ML related tests
│   ├── wal/                    # Write-Ahead Log tests
│   └── utils/                  # Utility function tests
│
├── integration/                # Tests that verify multiple components working together
│   ├── ipfs/                   # IPFS integration tests
│   ├── libp2p/                 # libp2p integration tests
│   ├── mcp/                    # MCP integration tests
│   ├── s3/                     # S3 integration tests
│   ├── storacha/               # Storacha integration tests
│   ├── webrtc/                 # WebRTC integration tests
│   └── lotus/                  # Lotus integration tests
│
├── functional/                 # End-to-end functional tests
│   ├── cli/                    # CLI functional tests
│   ├── streaming/              # Streaming functionality tests
│   ├── filesystem/             # Filesystem tests
│   └── workflows/              # Complete workflow tests
│
├── performance/                # Performance and benchmark tests
│
├── mcp/                        # MCP-specific tests
│   ├── controller/             # MCP controller tests
│   ├── model/                  # MCP model tests
│   └── server/                 # MCP server tests
│
├── tools/                      # Tests for package tools
│
├── helpers/                    # Test helper scripts and utilities
│
├── config/                     # Test configuration files
│
├── backup/                     # Backup test files
│
├── conftest.py                 # Common test fixtures and configuration
└── __init__.py                 # Package initialization file
```

## Running Tests

You can run the tests using pytest. Here are some common commands:

### Run all tests
```bash
pytest
```

### Run a specific category of tests
```bash
# Run all unit tests
pytest test/unit/

# Run API tests
pytest test/unit/api/

# Run MCP controller tests
pytest test/mcp/controller/
```

### Run with coverage reporting
```bash
pytest --cov=ipfs_kit_py
```

## Writing New Tests

When writing new tests:

1. Place the test in the appropriate directory based on what it's testing
2. Name test files with the prefix `test_` and test functions with the prefix `test_`
3. Use fixtures from `conftest.py` where applicable
4. Update this README if you create new test categories

## Test Dependencies

Most tests require the following dependencies:
- pytest
- pytest-asyncio (for async tests)
- pytest-cov (for coverage reporting)

You can install these with:
```bash
pip install pytest pytest-asyncio pytest-cov
```

Some tests may require additional dependencies based on what they're testing.