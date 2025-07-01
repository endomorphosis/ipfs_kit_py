# Archived MCP Server Scripts

This directory contains archived versions of various MCP server start scripts. These scripts have been consolidated into a single unified solution: `start_unified_mcp_server.sh`, which is located in the root directory.

## Reason for Archiving

The unified script combines the best features and functionalities from all these scripts into a single, comprehensive solution that:

1. Properly handles server startup and shutdown
2. Supports both unified and separate JSON-RPC servers
3. Provides extensive command-line options
4. Updates VS Code settings for both regular and Claude/Cline versions
5. Tests endpoints to ensure server health
6. Includes thorough error handling and verbose status reporting
7. Maintains backward compatibility with legacy server implementations
8. Provides separate commands for different operations (start, stop, status, test, etc.)

## Relationship to Unified Script

The unified script located at the root project directory (`start_unified_mcp_server.sh`) has been designed to replace all these separate scripts. It offers:

- A single entry point for managing MCP servers
- Better organized and structured code
- More consistent error handling
- Comprehensive help documentation
- Detailed status reporting
- Support for various configurations

For more information, see the `README_UNIFIED_MCP_SERVER.md` file in the root directory.
