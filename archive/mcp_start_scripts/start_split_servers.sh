#!/bin/bash
#
# Simplified MCP Server Startup Script
# This script:
# 1. Starts the standard MCP Server
# 2. Starts the JSON-RPC server for VS Code integration
# 3. Updates VS Code settings to use the correct endpoints
#

# Default settings
MCP_PORT=9994
JSONRPC_PORT=9995
LOG_DIR="logs"
MCP_LOG="${LOG_DIR}/mcp_server.log"
JSONRPC_LOG="${LOG_DIR}/mcp_jsonrpc.log"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Stop any existing servers
echo "Stopping any existing MCP server processes..."
pkill -f "python.*mcp_server_fixed_all" 2>/dev/null || true
pkill -f "python.*enhanced_mcp_server" 2>/dev/null || true
pkill -f "python.*run_mcp_server" 2>/dev/null || true
pkill -f "python.*mcp_jsonrpc" 2>/dev/null || true
sleep 2

# Start MCP server
echo "Starting MCP server on port ${MCP_PORT}..."
python run_mcp_server.py --port ${MCP_PORT} --debug --isolation --skip-daemon --api-prefix /api/v0 --log-file ${MCP_LOG} > ${LOG_DIR}/mcp_output.log 2>&1 &
MCP_PID=$!
echo "${MCP_PID}" > /tmp/mcp_server.pid
echo "MCP server started with PID ${MCP_PID}"

# Wait for MCP server to start
sleep 3

# Start JSON-RPC standalone server
echo "Starting JSON-RPC server on port ${JSONRPC_PORT}..."
python mcp_jsonrpc_standalone.py --port ${JSONRPC_PORT} --debug --log-file ${JSONRPC_LOG} > ${LOG_DIR}/jsonrpc_output.log 2>&1 &
JSONRPC_PID=$!
echo "${JSONRPC_PID}" > /tmp/mcp_jsonrpc.pid
echo "JSON-RPC server started with PID ${JSONRPC_PID}"

# Wait for JSON-RPC server to start
sleep 2

# Update VS Code settings
echo "Updating VS Code settings..."
VSCODE_SETTINGS_FILE="$HOME/.config/Code - Insiders/User/settings.json"

if [ -f "${VSCODE_SETTINGS_FILE}" ]; then
    # Backup settings file
    cp "${VSCODE_SETTINGS_FILE}" "${VSCODE_SETTINGS_FILE}.bak"
    
    # Use jq if available, otherwise use sed
    if command -v jq &> /dev/null; then
        jq '.["localStorageNetworkingTools.lspEndpoint"].url = "http://localhost:'${JSONRPC_PORT}'/jsonrpc"' \
           "${VSCODE_SETTINGS_FILE}" > /tmp/vscode_settings.tmp && \
           mv /tmp/vscode_settings.tmp "${VSCODE_SETTINGS_FILE}"
    else
        # Try to replace existing setting
        if grep -q "localStorageNetworkingTools.lspEndpoint" "${VSCODE_SETTINGS_FILE}"; then
            sed -i 's|"url": "http://localhost:[0-9]*/.*"|"url": "http://localhost:'${JSONRPC_PORT}'/jsonrpc"|g' "${VSCODE_SETTINGS_FILE}"
        else
            # Add the setting to the file
            TMP_FILE=$(mktemp)
            echo '{' > ${TMP_FILE}
            echo '  "localStorageNetworkingTools.lspEndpoint": {' >> ${TMP_FILE}
            echo '    "url": "http://localhost:'${JSONRPC_PORT}'/jsonrpc"' >> ${TMP_FILE}
            echo '  },' >> ${TMP_FILE}
            tail -n +2 "${VSCODE_SETTINGS_FILE}" >> ${TMP_FILE}
            mv ${TMP_FILE} "${VSCODE_SETTINGS_FILE}"
        fi
    fi
    
    # Also set MCP server settings if needed
    if ! grep -q "mcp.servers" "${VSCODE_SETTINGS_FILE}"; then
        # Add MCP server settings
        TMP_FILE=$(mktemp)
        jq -r '. += {"mcp": {"servers": {"my-mcp-server": {"url": "http://localhost:'${MCP_PORT}'/api/v0/sse"}}}}' \
           "${VSCODE_SETTINGS_FILE}" > ${TMP_FILE} || \
        sed -i '/"localStorageNetworkingTools/a \ \ "mcp": {\n    "servers": {\n      "my-mcp-server": {\n        "url": "http://localhost:'${MCP_PORT}'/api/v0/sse"\n      }\n    }\n  },' "${VSCODE_SETTINGS_FILE}"
    fi
    
    echo "VS Code settings updated successfully"
else
    # Create settings file if it doesn't exist
    mkdir -p $(dirname "${VSCODE_SETTINGS_FILE}")
    cat > "${VSCODE_SETTINGS_FILE}" << EOL
{
  "localStorageNetworkingTools.lspEndpoint": {
    "url": "http://localhost:${JSONRPC_PORT}/jsonrpc"
  },
  "mcp": {
    "servers": {
      "my-mcp-server": {
        "url": "http://localhost:${MCP_PORT}/api/v0/sse"
      }
    }
  }
}
EOL
    echo "Created new VS Code settings file"
fi

# Verify that servers are running
echo "Verifying MCP server..."
curl -s "http://localhost:${MCP_PORT}/" > /dev/null
if [ $? -eq 0 ]; then
    echo "MCP server is running at http://localhost:${MCP_PORT}/"
else
    echo "WARNING: MCP server doesn't seem to be responding. Check ${MCP_LOG}"
fi

echo "Verifying JSON-RPC server..."
curl -s "http://localhost:${JSONRPC_PORT}/" > /dev/null
if [ $? -eq 0 ]; then
    echo "JSON-RPC server is running at http://localhost:${JSONRPC_PORT}/"
else
    echo "WARNING: JSON-RPC server doesn't seem to be responding. Check ${JSONRPC_LOG}"
fi

echo "Setup complete. Both servers should now be running."
echo "MCP server: http://localhost:${MCP_PORT}/"
echo "JSON-RPC server: http://localhost:${JSONRPC_PORT}/"
echo
echo "To test JSON-RPC functionality, run:"
echo "curl -X POST -H \"Content-Type: application/json\" -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}' http://localhost:${JSONRPC_PORT}/jsonrpc"
