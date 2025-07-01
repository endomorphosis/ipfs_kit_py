# MCP Server Testing Tools

This directory contains a suite of tools for testing and managing the MCP (Model Context Protocol) server implementation.

## Overview of Testing Tools

### 1. Enhanced MCP Server Management Script

**File:** `run_enhanced_solution.sh`

This is the main script for starting, testing, and managing the MCP server. It combines the functionality of the original `run_final_solution.sh` with improved diagnostics and test integration.

**Usage:**
```bash
# Start the server and run tests
./run_enhanced_solution.sh

# Start the server without running tests
./run_enhanced_solution.sh --start-only

# Run tests against an existing server
./run_enhanced_solution.sh --test-only

# Enable verbose output
./run_enhanced_solution.sh --verbose

# Skip running tests after starting the server
./run_enhanced_solution.sh --skip-tests
```

### 2. Server Status Check Tool

**File:** `check_server.py`

A Python script for checking the status of the MCP server, starting/stopping the server, and retrieving information about the registered tools.

**Usage:**
```bash
# Check if server is running
./check_server.py

# Start the server
./check_server.py --start

# Stop the server
./check_server.py --stop

# Restart the server
./check_server.py --restart

# Get detailed server information
./check_server.py --info

# List all registered tools
./check_server.py --list-tools
```

See `MCP_SERVER_CHECK_TOOL.md` for detailed documentation.

### 3. Enhanced IPFS MCP Test

**File:** `enhanced_ipfs_mcp_test.py`

An improved version of the original `test_ipfs_mcp_tools.py` script that fixes issues with the original script and adds better diagnostics.

**Usage:**
```bash
# Run all tests
./enhanced_ipfs_mcp_test.py

# Run only basic tests
./enhanced_ipfs_mcp_test.py --basic-only

# Verbose output
./enhanced_ipfs_mcp_test.py --verbose
```

### 4. MCP Server Test Runner

**File:** `run_mcp_tests.sh`

A wrapper script that uses our enhanced test scripts to run tests with better diagnostics and error handling.

**Usage:**
```bash
# Run all tests
./run_mcp_tests.sh
```

## Troubleshooting

If you encounter issues with the MCP server or tests, try the following:

1. **Check server status:**
   ```bash
   ./check_server.py
   ```

2. **Restart the server:**
   ```bash
   ./check_server.py --restart
   ```

3. **Check detailed server information:**
   ```bash
   ./check_server.py --info
   ```

4. **Run basic tests only:**
   ```bash
   ./enhanced_ipfs_mcp_test.py --basic-only
   ```

5. **Check server logs:**
   ```bash
   tail -n 50 final_mcp_server.log
   ```

## Test Results

Test results are stored in the `test_results` directory with timestamps for easy reference.
