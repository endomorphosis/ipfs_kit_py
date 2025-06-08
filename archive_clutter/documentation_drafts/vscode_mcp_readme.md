# VS Code MCP Integration

This document explains how to fix issues with VS Code MCP integration, specifically when the MCP server is showing "no tools" even though they are correctly registered.

## Problem

The VS Code MCP extension expects tools to be returned in a specific format from the `/tools` endpoint:

- VS Code expects: `[{name: "tool1", ...}, {name: "tool2", ...}]`
- But some MCP servers return: `{"tools": [{name: "tool1", ...}, {name: "tool2", ...}]}`

This format mismatch causes VS Code to show "no tools" even though the server has tools registered.

## Solution

We've created an adapter that sits between VS Code and the MCP server to fix this format mismatch.

### Components

1. **vscode_mcp_adapter.py** - A Flask-based adapter that transforms the MCP server responses to match what VS Code expects
2. **start_vscode_mcp_adapter.sh** - A script to start the adapter as a background service

### How It Works

1. The adapter proxies requests from VS Code to the MCP server
2. For the `/tools` endpoint, it transforms the response format to what VS Code expects
3. For other endpoints, it passes through the requests and responses unchanged

### Setup Instructions

1. Start the adapter:
   ```bash
   ./start_vscode_mcp_adapter.sh
   ```

2. Update your VS Code settings to point to the adapter instead of directly to the MCP server:
   ```json
   "mcp": {
     "servers": {
       "my-mcp-server-329f7b54": {
         "url": "http://localhost:9999"
       }
     },
     "defaultServer": "my-mcp-server-329f7b54"
   }
   ```

3. Restart VS Code

### Troubleshooting

If you're still having issues:

1. Check the adapter logs:
   ```bash
   cat vscode_mcp_adapter.log
   ```

2. Make sure the adapter is running:
   ```bash
   ps aux | grep vscode_mcp_adapter.py
   ```

3. Test the adapter directly:
   ```bash
   curl -s http://localhost:9999/tools | python -m json.tool
   ```

4. Check the original MCP server:
   ```bash
   curl -s http://localhost:9998/tools | python -m json.tool
   ```

### Starting the Adapter on Boot

To start the adapter automatically when you log in:

1. Open your startup applications settings
2. Add a new startup application
3. Name: "VS Code MCP Adapter"
4. Command: `/full/path/to/start_vscode_mcp_adapter.sh`
5. Comment: "Adapter for VS Code MCP integration"

Alternatively, you can add it to your crontab with `@reboot`:

```bash
crontab -e
```

Add this line:
```
@reboot /full/path/to/start_vscode_mcp_adapter.sh
```

## How to Check if It's Working

1. Start the adapter
2. Open VS Code
3. Open the Command Palette (Ctrl+Shift+P)
4. Type "MCP: Show Available Tools"
5. You should see all the tools from your MCP server
