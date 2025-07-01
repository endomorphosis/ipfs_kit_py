# MCP Diagnostic Tools

This document provides information about the diagnostic tools included with the MCP Testing Framework. These tools help identify and resolve common issues with MCP servers, especially those integrating with IPFS Kit Python and Virtual Filesystem (VFS).

## Overview

The diagnostic tools complement the main testing framework by providing targeted, low-level diagnostics for troubleshooting MCP server issues. While the main testing framework (`start_final_solution.sh` and `mcp_test_runner.py`) focuses on comprehensive tool testing and verification, the diagnostic tools help identify specific configuration or implementation issues.

## Available Tools

### diagnose_mcp.sh

A Bash script that performs detailed diagnostics on MCP server implementations. It checks for common issues with:

- Server file syntax
- JSON-RPC implementation
- SSE implementation
- CORS middleware
- Health endpoint
- Tool registration methods
- Network configuration
- IPFS integration
- VFS integration
- Python dependencies
- VSCode integration

#### Usage

```bash
./diagnose_mcp.sh [options]
```

#### Options

- `--server-file FILE`: MCP server file to diagnose (default: final_mcp_server.py)
- `--port PORT`: Port used by the MCP server (default: 9996)
- `--check-imports`: Perform detailed Python import checking
- `--check-dependencies`: Check if all required dependencies are installed
- `--check-vscode`: Verify VSCode integration
- `--quick`: Quick diagnosis of critical issues only
- `--full`: Full system diagnosis (recommended)
- `--help`: Display help message

#### Example Usage

For a quick check of the current MCP server:

```bash
./diagnose_mcp.sh
```

For a comprehensive diagnostic:

```bash
./diagnose_mcp.sh --full
```

To diagnose a specific server implementation:

```bash
./diagnose_mcp.sh --server-file enhanced_final_mcp_server.py --port 9997
```

## Integration with the Testing Framework

The diagnostic tools work alongside the main testing framework to provide a complete solution for MCP server development and maintenance:

1. **Testing Framework (`start_final_solution.sh` and `mcp_test_runner.py`)**: Provides high-level testing of MCP tools and integration, identifying which tools are working and which are not.

2. **Diagnostic Tools (`diagnose_mcp.sh`)**: Provides low-level diagnostics to help identify why specific tools or integrations might be failing.

## Diagnostic Process

When troubleshooting MCP server issues, we recommend the following process:

1. Run the main testing framework to identify which tools or integrations are failing:
   ```bash
   ./start_final_solution.sh --verify
   ```

2. For any failed tools or integrations, run the diagnostic tools to identify specific issues:
   ```bash
   ./diagnose_mcp.sh --full
   ```

3. Review the diagnostic output for specific issues and recommendations.

4. Fix the identified issues in the server implementation.

5. Re-run the testing framework to verify the fixes.

## Common Issues and Fixes

The diagnostic tools help identify several common issues:

1. **Missing JSON-RPC Implementation**: Ensure your server properly implements the JSON-RPC 2.0 protocol. Key components include:
   - JSON-RPC endpoint
   - Method dispatcher
   - Error handling

2. **Missing SSE Implementation**: Required for VSCode integration. Key components include:
   - Server-Sent Events (SSE) endpoint
   - Event source response handling
   - Tool registration events

3. **Missing Tool Registration**: Ensure your server has proper methods for registering tools and notifying clients of available tools.

4. **Missing Required Endpoints**: Ensure your server implements all required endpoints:
   - `/jsonrpc` for JSON-RPC requests
   - `/sse` for Server-Sent Events
   - `/health` for health checks
   - `/initialize` for client initialization

5. **Dependency Issues**: Ensure all required Python packages are installed.

6. **VSCode Integration Issues**: Ensure the VSCode MCP settings file is properly configured for your server.

## Advanced Diagnostics

For persistent issues, you can use both tools together to perform advanced diagnostics:

```bash
./diagnose_mcp.sh --full > diagnostic_report.txt
./start_final_solution.sh --verify > test_report.txt
```

Then compare the outputs to identify correlations between specific diagnostic issues and test failures.
