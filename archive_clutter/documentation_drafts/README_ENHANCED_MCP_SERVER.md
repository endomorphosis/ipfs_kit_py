# Enhanced MCP Server for IPFS Kit

This README provides information about the Enhanced MCP server implementation which fixes the issues with the MCP tools.

## Overview

The Enhanced MCP Server is a drop-in replacement for the original MCP server that ensures all model extensions and tools are properly initialized and available for use. It addresses several issues in the original implementation where model extensions were not being properly loaded during server startup.

## Files Added

The following files have been added:

1. **enhanced_mcp_server_fixed.py** - A completely rewritten MCP server that properly initializes all extensions
2. **start_enhanced_mcp_server.sh** - A shell script to start the enhanced server
3. **verify_mcp_tools_fixed.py** - A comprehensive verification script to test all MCP tools
4. **README_ENHANCED_MCP_SERVER.md** - This documentation file

## Key Improvements

The Enhanced MCP Server includes the following improvements:

1. **Robust Model Extension Initialization**: Extensions are explicitly loaded in the correct order
2. **Two-way References**: Two-way references between models are properly set up
3. **CORS Support**: Proper CORS headers are added for browser compatibility
4. **Health Endpoints**: Added special endpoints for checking the health of tools
5. **Explicit Error Handling**: Better error handling and reporting
6. **Comprehensive Testing**: Included detailed testing capabilities

## Quick Start

Start the Enhanced MCP server:

```bash
./start_enhanced_mcp_server.sh
```

Test that all tools are working:

```bash
./verify_mcp_tools_fixed.py
```

## Usage with Cline

The Enhanced MCP server is fully compatible with Cline. When you start the server, it automatically creates or updates the necessary Cline MCP settings file.

## Server Options

The start script provides several configuration options:

```bash
./start_enhanced_mcp_server.sh [options]
```

Available options:
- `--port=NUMBER`: Port number to use (default: 9994)
- `--no-debug`: Disable debug mode
- `--no-isolation`: Disable isolation mode
- `--no-skip-daemon`: Don't skip daemon initialization (enables IPFS daemon management)
- `--api-prefix=PATH`: Set the API prefix (default: /api/v0)
- `--log-file=FILE`: Log file to use (default: mcp_server.log)
- `--foreground`: Run in foreground (don't detach)

## Verification

The verification script can be used to check that all tools are working correctly:

```bash
./verify_mcp_tools_fixed.py [options]
```

Available options:
- `--port=NUMBER`: Port number to check (default: 9994)
- `--api-prefix=PATH`: API prefix to use (default: /api/v0)
- `--start-server`: Attempt to start the server if it's not running
- `--output=FILE`: Save results to a JSON file
- `--quiet`: Suppress detailed output

## Tools and Endpoints

The Enhanced MCP server provides the following tools:

1. **IPFS Add** - Add content to IPFS
   - Endpoint: `/api/v0/ipfs/add`
   - Method: POST
   - Input: `{"content": "string", "pin": boolean}`
   - Output: `{"cid": "string", "size": number}`

2. **IPFS Cat** - Retrieve content from IPFS
   - Endpoint: `/api/v0/ipfs/cat/{cid}`
   - Method: GET
   - Output: The content as plain text

3. **IPFS Pin** - Pin content in IPFS
   - Endpoint: `/api/v0/ipfs/pin`
   - Method: POST
   - Input: `{"cid": "string"}`
   - Output: `{"success": boolean}`

4. **IPFS Pins List** - List pinned content
   - Endpoint: `/api/v0/ipfs/pins`
   - Method: GET
   - Output: `{"pins": array, "count": number}`

5. **Storage Transfer** - Transfer content between storage backends
   - Endpoint: `/api/v0/storage/transfer`
   - Method: POST
   - Input: `{"source": "string", "destination": "string", "identifier": "string"}`
   - Output: `{"success": boolean, "destinationId": "string"}`

6. **Tools Health Check** - Check the health of all tools
   - Endpoint: `/api/v0/tools/health`
   - Method: GET
   - Output: Status of all available model methods

## Troubleshooting

If you encounter issues with the Enhanced MCP server:

1. Check the logs in `mcp_server.log` and `logs/enhanced_mcp_server_stdout.log`
2. Run the verification script to check the status of all tools: `./verify_mcp_tools_fixed.py`
3. Ensure no other instances of the MCP server are running on the same port
4. Check that the required Python packages are installed

## Differences from Original MCP Server

The main differences between the Enhanced MCP server and the original are:

1. The Enhanced server explicitly initializes all model extensions
2. It adds direct instance methods to the model instead of just class methods
3. It ensures two-way references between models are set up correctly
4. It adds CORS headers for browser compatibility
5. It provides additional health check endpoints
6. It implements better error handling and simulation mode

## Implementation Details

The fixes implemented in the Enhanced MCP server address several issues:

1. **Missing Method Initialization**: The original server relied on dynamic patching of methods, which sometimes failed. The enhanced version directly attaches methods to both the class and instances.

2. **Import Path Issues**: The original server had inconsistent import paths. The enhanced version uses consistent imports and handles import errors more gracefully.

3. **Model References**: The original server did not set up bidirectional references between models correctly. The enhanced version ensures proper references.

4. **CORS Headers**: The original server did not include CORS headers, which could cause issues with browser clients. The enhanced version adds CORS middleware.

5. **Health Checks**: The original server lacked detailed health checks. The enhanced version adds specific endpoints to verify the status of all tools.
