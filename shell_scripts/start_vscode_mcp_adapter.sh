#!/bin/bash
# Start the VS Code MCP adapter as a background service

# Check if adapter is already running
if pgrep -f "python3 vscode_mcp_adapter.py" > /dev/null; then
    echo "VS Code MCP adapter is already running"
    exit 0
fi

# Start the adapter
echo "Starting VS Code MCP adapter..."
cd "$(dirname "$0")"  # Change to the script directory

# Start the adapter in the background
nohup python3 vscode_mcp_adapter.py --backend http://localhost:9998 --port 9999 > vscode_mcp_adapter.log 2>&1 &

# Save the PID
echo $! > vscode_mcp_adapter.pid

echo "VS Code MCP adapter started with PID: $!"
echo "Log file: vscode_mcp_adapter.log"
