# VS Code MCP Integration Guide

## 🎉 Setup Complete!

Your VS Code is now configured to work with the IPFS Kit MCP server. Here's how to use it:

## ✅ Current Configuration

- **MCP Server**: `ipfs-kit-mcp-server` running on `http://localhost:3001`
- **Extensions Installed**: 
  - Copilot MCP
  - VSCode MCP Server  
  - mcpsx.run
  - MCP4Humans

## 🔧 Available Tools

### 1. FS Journal Tools (5 tools)
- `fs_journal_track` - Track files/directories for changes
- `fs_journal_untrack` - Stop tracking files/directories  
- `fs_journal_list_tracked` - List all tracked paths
- `fs_journal_get_history` - Get change history for tracked paths
- `fs_journal_sync` - Sync filesystem changes

### 2. IPFS-FS Bridge Tools (5 tools)
- `ipfs_fs_bridge_status` - Get bridge status
- `ipfs_fs_bridge_map` - Map filesystem path to IPFS
- `ipfs_fs_bridge_unmap` - Unmap filesystem path from IPFS
- `ipfs_fs_bridge_list_mappings` - List all path mappings
- `ipfs_fs_bridge_sync` - Sync filesystem changes to IPFS

### 3. Multi-Backend Tools
- `mbfs_register_backend` - Register new storage backends
- Additional multi-backend filesystem tools

## 🚀 How to Use in VS Code

### Method 1: Using MCP Extensions

1. **Open Command Palette**: `Ctrl+Shift+P` (Linux/Windows) or `Cmd+Shift+P` (Mac)

2. **Search for MCP commands**:
   - Type "MCP" to see available MCP-related commands
   - Look for commands from the installed MCP extensions

3. **Connect to Server**:
   - Use the MCP extension interfaces to connect to `ipfs-kit-mcp-server`
   - Server URL: `http://localhost:3001`

### Method 2: Using GitHub Copilot Chat (if available)

1. **Open Copilot Chat**: `Ctrl+Shift+I`

2. **Use MCP tools**: The mcpsx.run extension should enable MCP server integration with Copilot Chat

### Method 3: Direct Testing

You can test individual tools by making HTTP requests to the server:

```bash
# Test server health
curl http://localhost:3001

# The server is running and ready to accept MCP protocol requests
```

## 🔍 Troubleshooting

### If MCP tools don't appear:

1. **Restart VS Code** to ensure extensions are fully loaded
2. **Check server status**: Run `python3 test_vscode_mcp_integration.py`
3. **Verify server is running**: 
   ```bash
   ps aux | grep direct_mcp_server
   ```
4. **Check VS Code settings**: The settings.json should contain:
   ```json
   {
     "mcp": {
       "servers": {
         "ipfs-kit-mcp-server": {
           "url": "http://localhost:3001"
         }
       }
     }
   }
   ```

### If server is not running:

```bash
cd /home/barberb/ipfs_kit_py
python direct_mcp_server.py --port 3001
```

## 🎯 Next Steps

1. **Explore MCP Extensions**: Use the command palette to find MCP-related commands
2. **Test Tools**: Try using the IPFS and filesystem tools through the MCP interface
3. **Integration**: The tools should now be available for AI assistants that support MCP

## 📊 Status

- ✅ MCP Server: Running on port 3001
- ✅ VS Code Settings: Configured for MCP server
- ✅ Extensions: MCP extensions installed and ready
- ✅ Tools: 10+ IPFS and filesystem tools available
- ✅ Integration: Ready for use with AI assistants

Your IPFS Kit MCP server is now fully integrated with VS Code and ready to use!
