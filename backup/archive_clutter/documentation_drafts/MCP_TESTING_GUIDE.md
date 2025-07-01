# MCP Server Testing Guide

This document provides guidance on testing the Model Context Protocol (MCP) server implementation.

## Testing Overview

Thorough testing is essential to ensure the MCP server operates correctly. This guide outlines multiple testing approaches.

## Important Updates (May 14, 2025)

Several improvements have been made to the testing framework:

1. **Port Consistency**: The default port in `final_mcp_server.py` is 9998, but scripts were using 9997. This has been updated for consistency.
2. **Test Runner Improvements**: The `mcp_test_runner.py` has been enhanced with better error handling and support for both `get_tools` and `list_tools` methods.
3. **Method Compatibility**: All test scripts now handle both `get_tools` and `list_tools` methods with proper fallback mechanisms.

## Server Configuration

The MCP server is configured in `final_mcp_server.py`. Key settings include:
- **Default port**: 9998 (defined in the server code)
- **Host**: 0.0.0.0 (listens on all interfaces)
- **Debug mode**: Optional, enables detailed logging

## Test Scripts and Tools

### 1. Simple MCP Validator

The `simple_mcp_validator.py` script we created provides a quick way to check core functionality:

```bash
python3 simple_mcp_validator.py
```

This tests:
- Health endpoint
- Ping method
- Both `get_tools` and `list_tools` methods
- Server info

### 2. Shell Script Testing

The `run_final_mcp_solution.sh` script includes integrated tests:

```bash
bash run_final_mcp_solution.sh
```

This will:
- Start the server
- Run JSON-RPC tests
- Run comprehensive tests
- Run enhanced tests

### 3. Manual JSON-RPC Testing

You can test the JSON-RPC endpoints directly:

```bash
# Test ping method
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}' \
  http://localhost:9997/jsonrpc

# Test get_tools method
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"get_tools","params":{},"id":2}' \
  http://localhost:9997/jsonrpc
```

## Key Testing Insights

### Method Compatibility

Our testing revealed the MCP server supports dual method naming:
- Both `get_tools` and `list_tools` methods work
- The `list_tools` method is an alias for `get_tools`
- Test clients should support both for maximum compatibility

### Testing Best Practices

1. **Test Health First**: Always check the `/health` endpoint before deeper tests
2. **Method Compatibility**: Test both `get_tools` and `list_tools`
3. **Graceful Failure**: Test how the server handles invalid requests
4. **Parameter Validation**: Check if tools properly validate their parameters

## Common Issues and Solutions

### 1. Test Runner Issues

If the test runner fails:
- Check for syntax errors in test files
- Verify Python dependencies are installed
- Confirm path references are correct
- Check if the runner's `main()` function is properly called with `sys.exit(main())`

### 2. Method Not Found Errors

If you see "Method not found" errors:
- Verify the method name (e.g., `get_tools` vs `list_tools`)
- Check if the server implements that specific method
- Consider using a method alias if available

### 3. Port Configuration Issues

Port-related issues are common in the MCP setup:
- The `final_mcp_server.py` defines `PORT = 9998` by default
- The `run_final_mcp_solution.sh` was using port 9997 (now updated to 9998)
- Always check what port the server is actually using: `curl http://localhost:PORT/health`
- Use `--port PORT` parameter when starting the server or running tests
- If a port is already in use, try a different one, like 9999

### 4. Parameter Validation

Some tool methods lack proper parameter definitions. Future improvements should include:
- Adding complete parameter schemas
- Better validation error messages
- Documentation for expected parameter formats

## Test Development Guidelines

When developing tests for the MCP server:

1. Start with basic connectivity checks
2. Test core methods (ping, get_tools, health)
3. Test specialized tool methods
4. Include negative test cases
5. Add performance tests for production scenarios

## Future Testing Improvements

1. Add a comprehensive test suite that covers all 53 tools
2. Create automated performance testing
3. Implement integration tests with real IPFS and backends
4. Add security and penetration testing
