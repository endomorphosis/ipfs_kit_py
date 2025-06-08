# MCP Testing Framework

A comprehensive testing framework for verifying the IPFS Kit Python MCP server functionality, ensuring all IPFS and Virtual Filesystem (VFS) features are properly exposed as MCP tools.

## Overview

This testing framework provides a robust solution for testing, verifying, and diagnosing issues with MCP servers that integrate with the IPFS Kit Python module. It offers:

- Comprehensive tool testing with detailed reporting
- IPFS/VFS integration verification
- VSCode MCP extension integration testing
- Server start/stop/restart management
- Comparison of different server versions
- Detailed diagnostic reports

## Components

The framework consists of two main components:

1. **start_final_solution.sh**: A Bash script that manages the MCP server lifecycle and orchestrates testing.
2. **mcp_test_runner.py**: A Python module that performs detailed testing of all MCP tools.

## Prerequisites

- Python 3.6+
- Bash shell
- curl (for health endpoint testing)
- IPFS Kit Python module installed
- MCP server implementation

## Usage

### Basic Usage

To run a complete verification of your MCP server:

```bash
./start_final_solution.sh
```

This will:
1. Start the MCP server if it's not running
2. Run comprehensive tests on all MCP tools
3. Test IPFS/VFS integration
4. Verify VSCode integration
5. Generate detailed reports

### Command-Line Options

The script supports various command-line options:

```
Usage: ./start_final_solution.sh [OPTIONS]

Options:
  --restart               Restart the MCP server
  --tests-only            Run only the tests without verification
  --verify                Run a complete system verification
  --check-vscode          Check VSCode integration only
  --compare               Compare different server versions
  --server-file FILE      Use a custom server file (default: final_mcp_server.py)
  --server-files FILE1 FILE2 ... Use when comparing multiple server files
  --port PORT             Use a custom port (default: 9996)
  --help                  Show this help message
```

### Common Usage Scenarios

#### 1. Testing a specific MCP server implementation

```bash
./start_final_solution.sh --server-file my_custom_server.py
```

#### 2. Running only the tests (without server restart)

```bash
./start_final_solution.sh --tests-only
```

#### 3. Comparing multiple server versions

```bash
./start_final_solution.sh --compare --server-files final_mcp_server.py enhanced_final_mcp_server.py experimental_server.py
```

#### 4. Checking only VSCode integration

```bash
./start_final_solution.sh --check-vscode
```

## Output Files

The framework generates several output files:

- **mcp_test_results.json**: Raw test results in JSON format
- **mcp_detailed_report.md**: A markdown report with test results and recommendations
- **mcp_version_comparison.md**: Generated when comparing multiple server versions
- **mcp_server.log**: Server log output
- **mcp_server_debug.log**: Detailed debug logs from the testing process

## Test Coverage

The framework tests the following categories of tools:

1. **Core Tools**: Basic server functionality (ping, health, list_tools, server_info)
2. **IPFS Tools**: Standard IPFS operations (ipfs_add, ipfs_cat, ipfs_version, etc.)
3. **MFS Tools**: IPFS Mutable File System operations (ipfs_files_*)
4. **VFS Tools**: Virtual Filesystem operations (vfs_ls, vfs_mkdir, vfs_write, etc.)
5. **Other Tools**: Any additional tools not in the categories above

## IPFS/VFS Integration Testing

The framework performs integration testing between IPFS and VFS by:

1. Adding content to IPFS
2. Creating a directory in VFS
3. Writing the IPFS CID to a file in VFS
4. Reading the CID back from VFS
5. Using the CID to retrieve content from IPFS
6. Verifying the retrieved content matches the original

## VSCode Integration Testing

VSCode integration testing verifies:

1. Correct configuration in VSCode MCP settings
2. Proper functioning of the SSE endpoint
3. Server discovery and tool listings

## Troubleshooting

### Common Issues

1. **Server fails to start**: Check the server log file (`mcp_server.log`) for errors.
2. **Missing tools**: Implementation issues in the server - see the detailed report for required tools.
3. **VSCode integration issues**: Verify settings in the VSCode MCP settings file.

### Generating Detailed Reports

To generate a detailed troubleshooting report:

```bash
./start_final_solution.sh --verify
```

The report will be saved as `mcp_detailed_report.md` and will contain:
- Test summary
- Tool coverage metrics
- Failed tools (if any)
- Missing required tools (if any)
- Recommendations for fixing issues

## Extending the Framework

### Adding Custom Tests

The `mcp_test_runner.py` module can be extended with additional tests:

1. Add a new test function
2. Register the test in the appropriate test category
3. Update the `run_tests` function to include your test

### Testing New Tool Categories

To test new tool categories:

1. Update the `categorize_tools` function in `mcp_test_runner.py`
2. Add the new category to the tool counts and reporting code
3. Add default test parameters for the new tool types

## License

Same as the IPFS Kit Python module.
