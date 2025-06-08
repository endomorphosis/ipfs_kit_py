# MCP Testing Framework Documentation

## Overview

This documentation covers the comprehensive MCP (Model Context Protocol) testing framework designed to diagnose compatibility issues between different MCP server implementations. The framework consists of several components that work together to provide thorough testing and analysis of MCP server functionality.

## Components

1. **Test Runner (`mcp_test_runner.py`)**: Executes individual tests for each MCP tool to verify correct functionality.
2. **IPFS Coverage Analyzer (`minimal_coverage_analyzer.py`)**: Checks that all expected IPFS functions are exposed as MCP tools.
3. **Testing Framework Script (`start_final_solution.sh`)**: Orchestrates the testing process, starts/stops the server, and runs tests.
4. **Cross-Version Comparison Tool (`compare_mcp_servers.sh`)**: Compares different MCP server implementations for compatibility issues.

## Test Runner

The test runner (`mcp_test_runner.py`) performs the following functions:

- Connects to the MCP server via JSON-RPC
- Retrieves the list of available tools
- Categorizes tools by their namespace (ipfs, vfs, mfs, etc.)
- Executes appropriate tests for each tool
- Performs integration tests between IPFS and VFS functionalities
- Generates test results

### Key Features:

- Supports both string and object tool representations
- Handles different server response formats
- Provides detailed error messages for failed tests
- Includes integration tests for critical system interactions

## IPFS Coverage Analyzer

The coverage analyzer (`minimal_coverage_analyzer.py`) ensures complete coverage of IPFS functionality:

- Extracts and categorizes all MCP tools
- Compares with a predefined list of expected IPFS functions
- Identifies missing IPFS functions
- Generates a coverage report

## Testing Framework Script

The testing framework script (`start_final_solution.sh`) provides:

- Server lifecycle management (start/stop/restart)
- Test execution coordination
- Result reporting and logging
- Command-line options for flexible testing

### Usage:

```bash
./start_final_solution.sh [options]

Options:
  --server-file FILE    Specify the MCP server file (default: final_mcp_server.py)
  --port PORT           Specify the port to use (default: 9996)
  --tests-only          Only run the tests without starting/stopping server
  --integration-only    Only run the integration tests
  --restart             Restart the MCP server
  --stop                Stop the MCP server
  --help                Show this help message
```

## Cross-Version Comparison Tool

The comparison tool (`compare_mcp_servers.sh`) enables:

- Side-by-side comparison of different MCP server implementations
- Identification of unique and common tools
- Compatibility assessment of common tools
- Test result comparison between implementations

### Usage:

```bash
./compare_mcp_servers.sh [options]

Options:
  --server FILE:PORT    Specify a server file and port to compare (can be used multiple times)
  --help                Show this help message
```

## Workflow

### Basic Testing Workflow:

1. Start the MCP server using `start_final_solution.sh`
2. Run tests with `start_final_solution.sh --tests-only`
3. Check test results for any issues
4. Run integration tests with `start_final_solution.sh --integration-only`
5. Analyze IPFS coverage with `minimal_coverage_analyzer.py`

### Cross-Version Testing Workflow:

1. Ensure multiple MCP server implementations are running
2. Run `compare_mcp_servers.sh` to compare implementations
3. Review comparison reports in the `cross_version_results` directory
4. Identify compatibility issues between implementations

## Test Cases

The framework includes tests for the following functional areas:

### IPFS Tools:
- **ipfs_version**: Tests version retrieval
- **ipfs_add**: Tests adding content to IPFS
- **ipfs_cat**: Tests retrieving content from IPFS
- **ipfs_ls**: Tests listing IPFS directory contents
- **ipfs_pin_add**: Tests pinning content
- **ipfs_pin_ls**: Tests listing pins
- **ipfs_pin_rm**: Tests removing pins
- **ipfs_refs**: Tests references
- **ipfs_refs_local**: Tests local references
- **ipfs_block_stat**: Tests block status
- **ipfs_block_get**: Tests block retrieval

### VFS Tools:
- **vfs_ls**: Tests listing directory contents
- **vfs_mkdir**: Tests directory creation
- **vfs_rmdir**: Tests directory removal
- **vfs_read**: Tests file reading
- **vfs_write**: Tests file writing
- **vfs_rm**: Tests file removal
- **vfs_cp**: Tests file copying
- **vfs_mv**: Tests file moving
- **vfs_stat**: Tests file status

### Integration Tests:
- IPFS-VFS Integration: Tests the interaction between IPFS and VFS systems
- Content Integrity: Tests that content remains intact through the system
- CID Verification: Tests that content identifiers are consistent

## Extending the Framework

To add new tests:

1. Add test functions to `mcp_test_runner.py`
2. Update the tool categorization logic if necessary
3. Update expected IPFS functions in `minimal_coverage_analyzer.py` if testing new IPFS features

To support new MCP server implementations:

1. Add the server to the default list in `compare_mcp_servers.sh`
2. Ensure the server adheres to the expected JSON-RPC interface
3. Run comparison tests to validate compatibility

## Troubleshooting

Common issues and their solutions:

- **Server won't start**: Check Python dependencies and port availability
- **Tests failing**: Examine server logs and test details for specific errors
- **Integration tests failing**: Verify that both IPFS and VFS subsystems are operational
- **Cross-version comparison errors**: Ensure all servers are running and accessible

## Conclusion

This testing framework provides comprehensive validation of MCP server implementations and helps diagnose compatibility issues between different versions. By using these tools systematically, you can ensure that your MCP server correctly implements all required functionality and integrates properly with the IPFS and VFS subsystems.
