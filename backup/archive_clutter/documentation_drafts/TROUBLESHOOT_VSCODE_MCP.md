# MCP Server VS Code Integration Troubleshooting Guide

If you're experiencing issues with VS Code connecting to the MCP server, particularly with errors like:

```
Waiting for server to respond to `initialize` request...
```

This guide will help you resolve the issues.

## Step 1: Make Sure Servers Are Running

First, verify both servers are running correctly:

```bash
# Start both servers with our script
./start_mcp_stack.sh

# Alternatively, start them manually
python ./enhanced_mcp_server_fixed.py --port 9994 --api-prefix /api/v0 &
python ./simple_jsonrpc_server.py &
```

## Step 2: Verify Server Responses

Test if the servers are responding correctly:

```bash
# Test MCP server
curl http://localhost:9994/

# Test JSON-RPC server
curl http://localhost:9995/

# Test JSON-RPC initialize request
curl -X POST -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
     http://localhost:9995/jsonrpc
```

## Step 3: Check VS Code Settings

Make sure your VS Code settings (`settings.json`) contain the correct configuration:

```json
{
  "mcp": {
    "servers": {
      "my-mcp-server": {
        "url": "http://localhost:9994/api/v0/sse"
      }
    }
  },
  "localStorageNetworkingTools": {
    "lspEndpoint": {
      "url": "http://localhost:9995/jsonrpc"
    }
  }
}
```

You can run our settings fix tool:

```bash
python ./fix_vscode_mcp_integration.py --restart-servers
```

## Step 4: Reload VS Code

After updating settings, reload VS Code:
- Press F1
- Type "Reload Window"
- Press Enter

## Step 5: Check Network Issues

If VS Code still can't connect:

1. Try using `127.0.0.1` instead of `localhost` in your settings
2. Check for any firewall or network issues that might be blocking local connections
3. Make sure VS Code has network permissions

## Step 6: Check VS Code Extensions

Verify the MCP/IPFS extensions are correctly installed:
1. Open Extensions view (Ctrl+Shift+X)
2. Search for "IPFS" or "MCP"
3. Make sure they're installed and enabled

## Step 7: Debug Connection Issues

Run our diagnostic tools:

```bash
# Test VS Code connections
python ./debug_vscode_connection.py

# Diagnose VS Code extension issues
python ./diagnose_vscode_extension.py
```

## Step 8: Check VS Code Logs

Look for errors in the VS Code logs:
1. In VS Code, press F1
2. Type "Developer: Open Logs Folder" and press Enter
3. Look for errors related to "mcp", "jsonrpc", or "initialize"

## Step 9: Try Alternative Ports

If all else fails, try running the servers on different ports:

```bash
python ./enhanced_mcp_server_fixed.py --port 8994 --api-prefix /api/v0 &
python ./simple_jsonrpc_server.py --port 8995 &
```

Then update your VS Code settings to use these new ports.

## Need More Help?

If you're still experiencing issues, run our comprehensive diagnosis tool and share the output:

```bash
python ./diagnose_vscode_extension.py > vscode_diagnosis.log
```
