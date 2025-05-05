#!/bin/bash
# Restart MCP Server with VFS Tools
# This script stops any running MCP server, updates the server code to use the VFS tools,
# and restarts the server with VFS integration.

echo "🚀 Restarting MCP Server with VFS Tools Integration"
echo "==================================================="

# Make the verification script executable
chmod +x verify_vfs_tools.py

# Stop any running MCP server instances
echo "Stopping any existing MCP server processes..."
pkill -f "python.*direct_mcp_server.py" || true
sleep 2

# Update the MCP server code to import and use our VFS tools
echo "Updating MCP server code to use VFS tools..."
MCP_SERVER_FILE="direct_mcp_server.py"
BACKUP_FILE="${MCP_SERVER_FILE}.bak.vfs_integrated"

# Create a backup of the original file
cp "$MCP_SERVER_FILE" "$BACKUP_FILE"
echo "Created backup at $BACKUP_FILE"

# Add the import for our VFS tools module at the appropriate place
VFS_IMPORT="import mcp_vfs_config"
if grep -q "$VFS_IMPORT" "$MCP_SERVER_FILE"; then
  echo "VFS import already added"
else
  # Find a good place to insert the import - just before the 'def register_all_tools' function
  LINE_NUM=$(grep -n "def register_all_tools" "$MCP_SERVER_FILE" | cut -d: -f1)
  if [ -n "$LINE_NUM" ]; then
    # Insert two lines above the function
    INSERT_LINE=$((LINE_NUM - 2))
    sed -i "${INSERT_LINE}i # Import VFS tools module\n$VFS_IMPORT" "$MCP_SERVER_FILE"
    echo "Added VFS tools import"
  else
    echo "Error: Could not find 'register_all_tools' function in $MCP_SERVER_FILE"
    exit 1
  fi
fi

# Add the call to register_vfs_tools in the register_all_tools function
# Find the right place to insert the call - after the first try/except block in the function
LINE_NUM=$(grep -n "Register virtual filesystem tools" "$MCP_SERVER_FILE" | cut -d: -f1)
if [ -n "$LINE_NUM" ]; then
  # Replace the existing register_all_fs_tools call with our VFS tools
  START_LINE=$LINE_NUM
  END_LINE=$((LINE_NUM + 5))  # Assuming the try/except block is 5 lines total
  
  # Create the replacement text
  REPLACEMENT="    # Register virtual filesystem tools\n    try:\n        mcp_vfs_config.register_vfs_tools(mcp_server)\n        logger.info(\"✅ Successfully registered virtual filesystem tools\")\n    except Exception as e:\n        logger.error(f\"Failed to register virtual filesystem tools: {e}\")"
  
  # Use sed to replace the specified lines
  sed -i "${START_LINE},${END_LINE}c\\${REPLACEMENT}" "$MCP_SERVER_FILE"
  
  echo "Updated register_all_tools function to use mcp_vfs_config.register_vfs_tools"
else
  echo "Error: Could not find VFS registration section in $MCP_SERVER_FILE"
  exit 1
fi

# Choose a port number that's not in use
PORT=3030  # Try a different port than 3000 since that one is in use

# Start the MCP server on the new port
echo "Starting MCP server with VFS tools on port $PORT..."
cd /home/barberb/ipfs_kit_py
sed -i "s/SERVER_PORT = 3000/SERVER_PORT = $PORT/" "$MCP_SERVER_FILE"
python3 "$MCP_SERVER_FILE" > mcp_server_vfs_integrated.log 2>&1 &
echo $! > mcp_server_vfs_integrated.pid
echo "Server started with PID $(cat mcp_server_vfs_integrated.pid)"

# Wait for server to initialize
echo "Waiting for server to initialize..."
sleep 5

# Check server status
echo "Verifying server is running..."
TRIES=0
MAX_TRIES=10
SERVER_UP=0

while [ $TRIES -lt $MAX_TRIES ] && [ $SERVER_UP -eq 0 ]; do
    TRIES=$((TRIES+1))
    curl -s "http://localhost:$PORT/" > /dev/null
    if [ $? -eq 0 ]; then
        SERVER_UP=1
    else
        echo "Server not ready yet, waiting... (attempt $TRIES/$MAX_TRIES)"
        sleep 2
    fi
done

if [ $SERVER_UP -eq 0 ]; then
    echo "❌ Error: Could not connect to MCP server after multiple attempts"
    echo "Last 20 lines of server log:"
    tail -n 20 mcp_server_vfs_integrated.log
    exit 1
else
    echo "✅ MCP server is running!"
    SERVER_INFO=$(curl -s "http://localhost:$PORT/")
    echo "$SERVER_INFO"
fi

# Update the verification script to use the new port
sed -i "s/MCP_SERVER_URL = \"http:\/\/localhost:3000\"/MCP_SERVER_URL = \"http:\/\/localhost:$PORT\"/" verify_vfs_tools.py

# Verify VFS tool registration
echo "Verifying VFS tool registration..."
python3 verify_vfs_tools.py

if [ $? -eq 0 ]; then
    echo "✅ VFS integration successful!"
    echo "The MCP server is now running with Virtual Filesystem tools."
    echo "Server PID: $(cat mcp_server_vfs_integrated.pid)"
    echo "Server log: mcp_server_vfs_integrated.log"
    echo "Server URL: http://localhost:$PORT"
    
    # Update VSCode settings to use the new MCP server
    VSCODE_SETTINGS="/home/barberb/.vscode/settings.json"
    if [ -f "$VSCODE_SETTINGS" ]; then
        # Backup settings
        cp "$VSCODE_SETTINGS" "${VSCODE_SETTINGS}.bak"
        # Update settings
        python3 -c "
import json
with open('$VSCODE_SETTINGS', 'r') as f:
    settings = json.load(f)
settings['claude-dev.mcp.serverUrl'] = 'http://localhost:$PORT'
with open('$VSCODE_SETTINGS', 'w') as f:
    json.dump(settings, f, indent=2)
"
        echo "Updated VSCode settings to use MCP server at http://localhost:$PORT"
    fi
    
    # Create a test file to demonstrate VFS tools
    TIMESTAMP=$(date +%s)
    TEST_CONTENT="This is a test file created by the VFS integration test at $(date)"
    TEST_FILE="vfs_test_$TIMESTAMP.txt"

    echo "Creating a test file using the VFS tools..."
    curl -s -X POST "http://localhost:$PORT/jsonrpc" \
      -H "Content-Type: application/json" \
      -d "{
        \"jsonrpc\": \"2.0\",
        \"id\": 2,
        \"method\": \"execute_tool\",
        \"params\": {
          \"name\": \"vfs_write_file\",
          \"arguments\": {
            \"path\": \"$TEST_FILE\",
            \"content\": \"$TEST_CONTENT\"
          }
        }
      }" | grep -q "\"success\":true" && echo "✅ Successfully created test file $TEST_FILE" || echo "❌ Failed to create test file"

    # Check the contents of the test file
    if [ -f "$TEST_FILE" ]; then
        echo "Test file contents:"
        cat "$TEST_FILE"
        echo ""
        echo "✅ VFS write operation confirmed"
    else
        echo "❌ Test file was not created"
    fi
else
    echo "❌ VFS integration verification failed"
    echo "Last 20 lines of server log:"
    tail -n 20 mcp_server_vfs_integrated.log
    exit 1
fi

echo ""
echo "⚠️  The MCP server is running in the background. To stop it, run:"
echo "kill \$(cat mcp_server_vfs_integrated.pid)"
echo ""
echo "✅ VFS integration complete!"
