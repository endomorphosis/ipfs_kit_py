#!/bin/bash
# Start IPFS MCP Server with Virtual Filesystem Support
#
# This script starts the MCP server with full virtual filesystem support.
# It ensures all IPFS features are properly registered as MCP tools.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PORT=9994
LOG_FILE="ipfs_mcp_server.log"

echo "=== Starting IPFS MCP Server with Virtual Filesystem Support ==="
echo "$(date): Starting server initialization" | tee -a $LOG_FILE

# Function to check if a process is running
check_process() {
    local process=$1
    pgrep -f "$process" > /dev/null
    return $?
}

# Function to check if server is already running
check_server() {
    if curl -s http://localhost:$SERVER_PORT/health > /dev/null; then
        return 0  # Server is running
    else
        return 1  # Server is not running
    fi
}

# Function to wait for server to start
wait_for_server() {
    local timeout=$1
    local count=0
    echo "Waiting for server to start..."
    while ! check_server && [ $count -lt $timeout ]; do
        sleep 1
        count=$((count + 1))
        echo -n "."
    done
    echo ""
    
    if check_server; then
        echo "Server is now running."
        return 0
    else
        echo "Server failed to start within $timeout seconds."
        return 1
    fi
}

# Step 1: Start the MCP server if it's not already running
if check_server; then
    echo "MCP server is already running on port $SERVER_PORT."
else
    echo "MCP server is not running. Starting it now..."
    
    # Try different start scripts that might be available
    if [ -f "${SCRIPT_DIR}/unified_mcp_server.py" ]; then
        echo "Starting unified MCP server..."
        python3 "${SCRIPT_DIR}/unified_mcp_server.py" > $LOG_FILE 2>&1 &
    elif [ -f "${SCRIPT_DIR}/start_unified_mcp_server.sh" ]; then
        echo "Running unified MCP server start script..."
        bash "${SCRIPT_DIR}/start_unified_mcp_server.sh" > $LOG_FILE 2>&1 &
    elif [ -f "${SCRIPT_DIR}/direct_mcp_server.py" ]; then
        echo "Starting direct MCP server..."
        python3 "${SCRIPT_DIR}/direct_mcp_server.py" > $LOG_FILE 2>&1 &
    elif [ -f "${SCRIPT_DIR}/start_mcp_server.sh" ]; then
        echo "Running MCP server start script..."
        bash "${SCRIPT_DIR}/start_mcp_server.sh" > $LOG_FILE 2>&1 &
    elif [ -f "${SCRIPT_DIR}/ipfs_kit_py/run_mcp_server_real_storage.py" ]; then
        echo "Starting MCP server with real storage..."
        python3 "${SCRIPT_DIR}/ipfs_kit_py/run_mcp_server_real_storage.py" > $LOG_FILE 2>&1 &
    else
        echo "ERROR: Could not find an MCP server script to start."
        echo "Please start the MCP server manually and run this script again."
        exit 1
    fi
    
    # Wait for server to start
    if ! wait_for_server 30; then
        echo "Failed to start the MCP server. Please check the logs."
        exit 1
    fi
fi

# Step 2: Check if our tools are already registered
echo "Checking current tool registration..."
TOOLS_RESPONSE=$(curl -s http://localhost:$SERVER_PORT/initialize)
echo "Retrieved server initialization data"

# Check if the tools we need are already registered
if echo "$TOOLS_RESPONSE" | grep -q "ipfs_files_ls"; then
    echo "Virtual filesystem tools are already registered."
else
    echo "Need to register virtual filesystem tools."

    # Step 3: Apply our tool enhancements
    echo "Applying tool enhancements..."
    
    # Try different approaches to register tools
    if [ -f "${SCRIPT_DIR}/fix_mcp_tool_registration.py" ]; then
        echo "Running MCP tool registration fix..."
        python3 "${SCRIPT_DIR}/fix_mcp_tool_registration.py" --apply
    elif [ -f "${SCRIPT_DIR}/enhance_mcp_tools.py" ]; then
        echo "Running MCP tool enhancer..."
        python3 "${SCRIPT_DIR}/enhance_mcp_tools.py" --apply
    elif [ -f "${SCRIPT_DIR}/apply_mcp_tool_enhancements.sh" ]; then
        echo "Running tool enhancement script..."
        bash "${SCRIPT_DIR}/apply_mcp_tool_enhancements.sh"
    else
        echo "WARNING: Could not find tool enhancement scripts."
        echo "Virtual filesystem tools may not be available."
    fi
fi

# Step 4: Set up a proxy for VS Code MCP integration if necessary
if [ -f "${SCRIPT_DIR}/mcp_jsonrpc_proxy.py" ]; then
    echo "Starting MCP JSON-RPC proxy for better IDE integration..."
    python3 "${SCRIPT_DIR}/mcp_jsonrpc_proxy.py" > mcp_proxy.log 2>&1 &
    echo "Proxy running. Check mcp_proxy.log for details."
fi

# Step 5: Verify tools are now available
echo "Verifying virtual filesystem tools..."
TOOLS_RESPONSE=$(curl -s http://localhost:$SERVER_PORT/initialize)

# Print available tools for debugging
echo "Available tools according to server:"
echo "$TOOLS_RESPONSE" | grep -o '"tools":\[[^]]*\]' | sed 's/"tools":\[//g' | sed 's/\]//g' | tr ',' '\n' | sed 's/"//g' | sort

# Step 6: Start a test file to demonstrate usage
cat > example_ipfs_fs_usage.py << 'EOF'
#!/usr/bin/env python3
"""
Example IPFS Virtual Filesystem Usage

This script demonstrates how to use the IPFS virtual filesystem
features exposed through the MCP server.
"""

import requests
import json
import base64

MCP_SERVER = "http://localhost:9994"

def mcp_request(endpoint, method="GET", data=None):
    """Make a request to the MCP server."""
    url = f"{MCP_SERVER}/{endpoint}"
    if method == "GET":
        response = requests.get(url)
    else:
        response = requests.post(url, json=data)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return None
    
    return response.json()

# Check server health
health = mcp_request("health")
print(f"Server health: {health}")

# Get capabilities
init = mcp_request("initialize")
print(f"Available tools: {init.get('capabilities', {}).get('tools', [])}")

# Example 1: Create a directory in MFS
print("\nExample 1: Creating a directory in MFS")
mkdir_data = {
    "name": "ipfs_files_mkdir",
    "server": "ipfs-kit-mcp",
    "args": {
        "path": "/test_dir",
        "parents": True
    }
}
mkdir_result = mcp_request("mcp/tools", method="POST", data=mkdir_data)
print(f"Mkdir result: {mkdir_result}")

# Example 2: Write a file to MFS
print("\nExample 2: Writing a file to MFS")
content = "Hello, IPFS Virtual Filesystem!"
write_data = {
    "name": "ipfs_files_write",
    "server": "ipfs-kit-mcp",
    "args": {
        "path": "/test_dir/hello.txt",
        "content": content,
        "create": True,
        "truncate": True
    }
}
write_result = mcp_request("mcp/tools", method="POST", data=write_data)
print(f"Write result: {write_result}")

# Example 3: List files in directory
print("\nExample 3: Listing files in directory")
ls_data = {
    "name": "ipfs_files_ls",
    "server": "ipfs-kit-mcp",
    "args": {
        "path": "/test_dir",
        "long": True
    }
}
ls_result = mcp_request("mcp/tools", method="POST", data=ls_data)
print(f"List result: {ls_result}")

# Example 4: Read file content
print("\nExample 4: Reading file content")
read_data = {
    "name": "ipfs_files_read",
    "server": "ipfs-kit-mcp",
    "args": {
        "path": "/test_dir/hello.txt"
    }
}
read_result = mcp_request("mcp/tools", method="POST", data=read_data)
if read_result and read_result.get("content"):
    content = read_result.get("content")
    if read_result.get("content_encoding") == "base64":
        content = base64.b64decode(content).decode("utf-8")
    print(f"File content: {content}")
else:
    print(f"Read error: {read_result}")

print("\nCompleted IPFS virtual filesystem test!")
EOF

chmod +x example_ipfs_fs_usage.py

echo "=== IPFS MCP Server with Virtual Filesystem is Ready ==="
echo "The server is running on http://localhost:$SERVER_PORT"
echo "You can now use all IPFS virtual filesystem features through MCP."
echo ""
echo "Try the example script to see how it works:"
echo "    python3 example_ipfs_fs_usage.py"
echo ""
echo "For more information, please refer to README_MCP_IPFS_ENHANCEMENTS.md"
