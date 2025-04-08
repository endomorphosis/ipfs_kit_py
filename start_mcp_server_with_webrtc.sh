#!/bin/bash
# Script to start the MCP server with WebRTC dependencies forced available

# Set environment variables to force WebRTC availability
export IPFS_KIT_FORCE_WEBRTC=1
export FORCE_WEBRTC_TESTS=1
export IPFS_KIT_RUN_ALL_TESTS=1

# Print status information
echo "Starting MCP server with WebRTC forced available"
echo "IPFS_KIT_FORCE_WEBRTC=${IPFS_KIT_FORCE_WEBRTC}"
echo "FORCE_WEBRTC_TESTS=${FORCE_WEBRTC_TESTS}"

# Kill any existing MCP server processes
pids=$(ps aux | grep "uvicorn run_mcp_server:app" | grep -v grep | awk '{print $2}')
if [ -n "$pids" ]; then
    echo "Stopping existing MCP server processes: $pids"
    kill -9 $pids
fi

# Start the MCP server with uvicorn
uvicorn run_mcp_server:app --port 9999 --log-level info