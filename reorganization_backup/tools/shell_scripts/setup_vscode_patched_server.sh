#!/bin/bash
# Convert existing MCP server to be VS Code compatible

echo "Setting up VS Code compatible MCP server..."

# 1. First, check if the minimal_mcp_server.py already has the direct /jsonrpc endpoint
if grep -q 'Route("/jsonrpc", endpoint=self.jsonrpc_endpoint, methods=\["POST"\])' /home/barberb/ipfs_kit_py/minimal_mcp_server.py; then
    echo "✅ Direct /jsonrpc endpoint is already present"
else
    echo "Adding direct /jsonrpc endpoint..."
    sed -i 's|Route("/api/v0/jsonrpc", endpoint=self.jsonrpc_endpoint, methods=\["POST"\])|Route("/jsonrpc", endpoint=self.jsonrpc_endpoint, methods=["POST"]),\n                Route("/api/v0/jsonrpc", endpoint=self.jsonrpc_endpoint, methods=["POST"])|g' /home/barberb/ipfs_kit_py/minimal_mcp_server.py
fi

# 2. Create a tool registration helper Python file
cat > /home/barberb/ipfs_kit_py/register_vs_code_tools.py << EOF
#!/usr/bin/env python3
"""
Helper script to register mock IPFS tools for VS Code integration
"""

from datetime import datetime
import logging

logger = logging.getLogger("vs-code-tools")

def register_mock_ipfs_tools(server):
    """Register mock IPFS tools for improved VS Code integration."""
    
    # List of tool names to register
    tool_names = [
        "ipfs_files_ls", "ipfs_files_mkdir", "ipfs_files_write", "ipfs_files_read",
        "ipfs_files_rm", "ipfs_files_stat", "ipfs_files_cp", "ipfs_files_mv",
        "ipfs_name_publish", "ipfs_name_resolve", "ipfs_dag_put", "ipfs_dag_get",
        "fs_journal_get_history", "fs_journal_sync", "ipfs_fs_bridge_status", 
        "ipfs_fs_bridge_sync", "s3_store_file", "s3_retrieve_file",
        "filecoin_store_file", "filecoin_retrieve_deal", "huggingface_model_load",
        "huggingface_model_inference", "webrtc_peer_connect", "webrtc_send_data",
        "credential_store", "credential_retrieve", "ipfs_pubsub_publish", 
        "ipfs_pubsub_subscribe", "ipfs_dht_findpeer", "ipfs_dht_findprovs",
        "ipfs_cluster_pin", "ipfs_cluster_status", "ipfs_cluster_peers",
        "lassie_fetch", "lassie_fetch_with_providers", "ai_model_register",
        "ai_dataset_register", "search_content", "storacha_store",
        "storacha_retrieve", "multi_backend_add_backend", "multi_backend_list_backends",
        "streaming_create_stream", "streaming_publish", "monitoring_get_metrics",
        "monitoring_create_alert"
    ]
    
    for tool_name in tool_names:
        try:
            # Create a closure to capture the tool name
            async def mock_tool_factory(name):
                async def mock_tool(ctx, **kwargs):
                    await ctx.info(f"Called {name} with params: {kwargs}")
                    await ctx.info(f"This is a mock implementation for VS Code integration")
                    return {
                        "success": True,
                        "warning": "Mock implementation",
                        "timestamp": datetime.now().isoformat(),
                        "tool": name,
                        "params": kwargs
                    }
                return mock_tool
            
            # Register the tool
            server.register_tool(
                name=tool_name,
                func=mock_tool_factory(tool_name),
                description=f"IPFS tool: {tool_name}",
                schema={
                    "input": {"type": "object", "properties": {}, "required": []},
                    "output": {"type": "object", "properties": {}}
                }
            )
            logger.info(f"✅ Registered mock tool: {tool_name}")
        except Exception as e:
            logger.error(f"❌ Failed to register mock tool {tool_name}: {e}")
    
    return True

# For testing as standalone
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    print("This module is designed to be imported, not run directly")
    sys.exit(0)
EOF

chmod +x /home/barberb/ipfs_kit_py/register_vs_code_tools.py

# 3. Create a patched version of minimal_mcp_server.py
cat > /home/barberb/ipfs_kit_py/vscode_patched_mcp_server.py << EOF
#!/usr/bin/env python3
"""
Patched version of minimal_mcp_server.py for VS Code compatibility
"""

import os
import sys
import logging
from datetime import datetime
import minimal_mcp_server
from minimal_mcp_server import *  # Import all from original server

# Add direct import for register_mock_ipfs_tools
try:
    from register_vs_code_tools import register_mock_ipfs_tools
    logger.info("Successfully imported VS Code tool registration helper")
except Exception as e:
    logger.error(f"Failed to import VS Code tool registration helper: {e}")
    register_mock_ipfs_tools = None

# Override original register_default_tools to add our VS Code compatible mock tools
original_register_default_tools = minimal_mcp_server.register_default_tools

def patched_register_default_tools():
    """Register default tools plus VS Code compatible mock tools."""
    result = original_register_default_tools()
    
    # Add our VS Code compatible mock tools
    if register_mock_ipfs_tools:
        try:
            logger.info("Registering VS Code compatible mock tools...")
            register_mock_ipfs_tools(server)
            logger.info("Successfully registered VS Code compatible mock tools")
        except Exception as e:
            logger.error(f"Failed to register VS Code compatible mock tools: {e}")
    
    return result

# Patch the original function
minimal_mcp_server.register_default_tools = patched_register_default_tools

if __name__ == "__main__":
    # Use the original main function with our patched register_default_tools
    minimal_mcp_server.main()
EOF

chmod +x /home/barberb/ipfs_kit_py/vscode_patched_mcp_server.py

# 4. Create a run script
cat > /home/barberb/ipfs_kit_py/run_vscode_patched_server.sh << EOF
#!/bin/bash

# Kill all existing Python servers
echo "Stopping all existing MCP servers..."
pkill -9 -f "python.*mcp.*server" || echo "No MCP server processes to kill"
pkill -9 -f "python.*minimal_mcp_server" || echo "No minimal MCP server processes to kill"
pkill -9 -f "python.*simple_mcp_server" || echo "No simple MCP server processes to kill"
pkill -9 -f "python.*vscode_patched_mcp_server" || echo "No patched MCP server processes to kill"
sleep 2

echo "Starting the VS Code patched MCP server..."
cd /home/barberb/ipfs_kit_py

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "Activated virtual environment"
elif [ -d "venv" ]; then
    source venv/bin/activate
    echo "Activated virtual environment"
fi

# Start the server
echo "Launching server on port 9996..."
python3 vscode_patched_mcp_server.py --port 9996 > vscode_patched_server.log 2>&1 &
SERVER_PID=\$!

# Write PID to file for future reference
echo \$SERVER_PID > vscode_patched_server.pid
echo "Server started with PID: \$SERVER_PID"

# Wait for server to initialize
echo "Waiting for server to initialize..."
sleep 5

# Check if server is running
if ps -p \$SERVER_PID > /dev/null; then
    echo "Server is running successfully with PID: \$SERVER_PID"
    echo "Testing health endpoint..."
    curl -s http://localhost:9996/health
    
    echo -e "\nTesting initialize endpoint..."
    curl -s -X POST http://localhost:9996/initialize | grep tools | head -n 1
    
    echo -e "\nTesting JSON-RPC endpoint..."
    curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"health_check","params":{},"id":1}' http://localhost:9996/jsonrpc
    
    echo -e "\n\nServer is ready! VS Code should now be able to discover all the IPFS tools."
    echo "You may need to restart VS Code to see the changes."
    
    # Create a marker file for VS Code to find
    echo "Writing marker file for VS Code integration..."
    echo "VS Code patched MCP server is running on port 9996" > /home/barberb/ipfs_kit_py/vscode_patched_server_active.txt
else
    echo "Server failed to start. Check the log file: vscode_patched_server.log"
    cat vscode_patched_server.log
fi
EOF

chmod +x /home/barberb/ipfs_kit_py/run_vscode_patched_server.sh

echo "Setup complete! Run the VS Code patched server with:"
echo "./run_vscode_patched_server.sh"
