# MCP Server

This directory contains the production MCP server for IPFS Kit.

## Production Server

- `enhanced_mcp_server_with_daemon_mgmt.py` - The main production MCP server with enhanced daemon management and real IPFS integration.

## Features

- Real IPFS operations using direct commands
- Automatic daemon management and startup
- Graceful fallback handling for protobuf compatibility issues
- Comprehensive error handling and logging
- Full MCP protocol compliance

## Usage

The server is configured in VS Code and Cline through their respective configuration files:
- VS Code: `.vscode/settings.json`
- Cline: `.config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

## Available Tools

- `ipfs_add` - Add content to IPFS
- `ipfs_cat` - Retrieve content from IPFS
- `ipfs_pin` - Pin content to prevent garbage collection
- `ipfs_list_pins` - List all pinned content
- `ipfs_version` - Get IPFS daemon version
- `ipfs_id` - Get IPFS node identity
- `system_health` - Get system health status
