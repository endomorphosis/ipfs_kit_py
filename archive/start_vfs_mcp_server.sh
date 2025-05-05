#!/bin/bash
# Start the VFS-enabled MCP server

set -e

echo "Starting VFS-enabled MCP server..."
echo "=================================="

# Check if server is already running
if [ -f "vfs_mcp_server.pid" ]; then
  pid=$(cat vfs_mcp_server.pid)
  if ps -p $pid > /dev/null; then
    echo "Server is already running with PID $pid"
    echo "To stop it, use: kill $pid"
    echo "To force restart, use: kill $pid && $0"
    exit 1
  else
    echo "Stale PID file found, cleaning up..."
    rm -f vfs_mcp_server.pid
  fi
fi

# Make sure the VFS config module exists
if [ ! -f "mcp_vfs_config.py" ]; then
  echo "❌ Error: mcp_vfs_config.py not found!"
  echo "Please make sure the VFS configuration module is available in the current directory."
  exit 1
fi

# Make sure the VFS server exists
if [ ! -f "vfs_mcp_server.py" ]; then
  echo "❌ Error: vfs_mcp_server.py not found!"
  echo "Please run create_standalone_vfs_server.py first to create the VFS server."
  exit 1
fi

# Start the server
echo "Starting server with VFS tools on port 3030..."
python vfs_mcp_server.py --port 3030 --log-file vfs_mcp_server.log --pid-file vfs_mcp_server.pid &

# Wait for server to start
echo "Waiting for server to initialize..."
sleep 3

# Check if the server is running
if [ -f "vfs_mcp_server.pid" ]; then
  pid=$(cat vfs_mcp_server.pid)
  if ps -p $pid > /dev/null; then
    echo "✅ Server is running with PID $pid"
  else
    echo "❌ Error: Server failed to start. Check vfs_mcp_server.log for details."
    exit 1
  fi
else
  echo "❌ Error: Server PID file not found. Server may have failed to start."
  echo "Check vfs_mcp_server.log for details."
  exit 1
fi

# Verify that server is responding
echo "Verifying server is responding..."
for i in {1..10}; do
  if curl -s http://localhost:3030/ > /dev/null; then
    echo "✅ Server is responding to HTTP requests"
    break
  elif [ $i -eq 10 ]; then
    echo "❌ Error: Server is not responding to HTTP requests after 10 attempts"
    echo "Check vfs_mcp_server.log for details."
    exit 1
  else
    echo "Waiting for server to respond (attempt $i/10)..."
    sleep 2
  fi
done

# Verify VFS tools are registered
echo "Verifying VFS tools are registered..."
TOOLS_JSON=$(curl -s -X POST http://localhost:3030/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"get_tools","params":{}}')

# Check if VFS tools exist in the response
if echo "$TOOLS_JSON" | grep -q "vfs_"; then
  echo "✅ VFS tools are registered!"
  
  # Count VFS tools
  VFS_TOOL_COUNT=$(echo "$TOOLS_JSON" | grep -o "vfs_" | wc -l)
  echo "Found $VFS_TOOL_COUNT VFS tools"
  
  # List VFS tools
  echo "VFS tools available:"
  echo "$TOOLS_JSON" | grep -o '"name":"[^"]*vfs_[^"]*"' | sed 's/"name":"//g' | sed 's/"//g' | sort | while read -r tool; do
    echo "  - $tool"
  done
else
  echo "❌ Error: No VFS tools found in the server response"
  echo "Check vfs_mcp_server.log for details."
  exit 1
fi

# Verify FS journal tools
if echo "$TOOLS_JSON" | grep -q "fs_journal_"; then
  echo "✅ FS Journal tools are registered!"
  
  # Count journal tools
  FS_JOURNAL_TOOL_COUNT=$(echo "$TOOLS_JSON" | grep -o "fs_journal_" | wc -l)
  echo "Found $FS_JOURNAL_TOOL_COUNT FS Journal tools"
  
  # List journal tools
  echo "FS Journal tools available:"
  echo "$TOOLS_JSON" | grep -o '"name":"[^"]*fs_journal_[^"]*"' | sed 's/"name":"//g' | sed 's/"//g' | sort | while read -r tool; do
    echo "  - $tool"
  done
else
  echo "⚠️ Warning: No FS Journal tools found in the server response"
fi

# Verify IPFS-FS tools
if echo "$TOOLS_JSON" | grep -q "ipfs_fs_"; then
  echo "✅ IPFS-FS integration tools are registered!"
  
  # Count IPFS-FS tools
  IPFS_FS_TOOL_COUNT=$(echo "$TOOLS_JSON" | grep -o "ipfs_fs_" | wc -l)
  echo "Found $IPFS_FS_TOOL_COUNT IPFS-FS integration tools"
  
  # List IPFS-FS tools
  echo "IPFS-FS integration tools available:"
  echo "$TOOLS_JSON" | grep -o '"name":"[^"]*ipfs_fs_[^"]*"' | sed 's/"name":"//g' | sed 's/"//g' | sort | while read -r tool; do
    echo "  - $tool"
  done
else
  echo "⚠️ Warning: No IPFS-FS integration tools found in the server response"
fi

echo ""
echo "VFS-enabled MCP server is running successfully on port 3030!"
echo "You can access the server at http://localhost:3030/"
echo "To stop the server, run: kill $(cat vfs_mcp_server.pid)"
echo ""
echo "For testing VFS tools, use the JSON-RPC endpoint at http://localhost:3030/jsonrpc"
echo "Example: Test vfs_list_files tool"
echo "curl -X POST http://localhost:3030/jsonrpc \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"execute_tool\",\"params\":{\"name\":\"vfs_list_files\",\"arguments\":{\"path\":\".\"}}}'"
