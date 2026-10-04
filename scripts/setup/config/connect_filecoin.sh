#!/bin/bash
# connect_filecoin.sh - Connect to Filecoin network via public gateway
#
# This script sets up the MCP server to connect to the Filecoin network
# through a public gateway instead of requiring a local Lotus node.

set -e  # Exit on any error

echo "Setting up Filecoin connection via public gateway..."

# Create necessary directories
mkdir -p ~/.lotus-gateway
mkdir -p bin

# Configure Filecoin gateway connection
GATEWAY_API="https://api.node.glif.io/rpc/v0"
GATEWAY_TOKEN=""

# Save gateway configuration
echo "$GATEWAY_API" > ~/.lotus-gateway/api
echo "$GATEWAY_TOKEN" > ~/.lotus-gateway/token

# Create Lotus gateway script
cat > bin/lotus << 'EOF'
#!/bin/bash
# Lotus Gateway Client
# Connects to Filecoin network via public gateway

# Configuration
LOTUS_PATH="$HOME/.lotus-gateway"
API_URL=$(cat "$LOTUS_PATH/api")
API_TOKEN=$(cat "$LOTUS_PATH/token")

# Export for subprocesses
export LOTUS_PATH

# Process arguments
COMMAND="$1"
shift

# Execute command
case "$COMMAND" in
    version)
        echo "Lotus Gateway Client v0.1.0"
        echo "Connected to public Filecoin gateway"
        exit 0
        ;;
    chain)
        if [ "$1" = "head" ]; then
            curl -s -X POST -H "Content-Type: application/json" \
                 -d '{"jsonrpc":"2.0","method":"Filecoin.ChainHead","params":[],"id":1}' \
                 "$API_URL" | python3 -c '
import sys, json
try:
    data = json.load(sys.stdin)
    if "result" in data:
        print(json.dumps(data["result"], indent=2))
    else:
        print(json.dumps(data, indent=2))
except:
    print("Error parsing response")'
            exit $?
        fi
        ;;
    *)
        # Forward other commands to the API
        curl -s -X POST -H "Content-Type: application/json" \
             -d "{\"jsonrpc\":\"2.0\",\"method\":\"Filecoin.$COMMAND\",\"params\":[],\"id\":1}" \
             "$API_URL" | python3 -c '
import sys, json
try:
    data = json.load(sys.stdin)
    if "result" in data:
        print(json.dumps(data["result"], indent=2))
    else:
        print(json.dumps(data, indent=2))
except:
    print("Error parsing response")'
        exit $?
        ;;
esac
EOF

# Make the script executable
chmod +x bin/lotus

echo "Testing Filecoin gateway connection..."
if ./bin/lotus chain head >/dev/null 2>&1; then
    echo "✅ Successfully connected to Filecoin gateway!"
else
    echo "⚠️ Warning: Could not connect to Filecoin gateway. Some features may not work."
fi

# Update filecoin_storage.py to work with the gateway
if [ -f "filecoin_storage.py" ]; then
    echo "Updating Filecoin storage implementation..."
    
    # Check for gateway mode
    if ! grep -q "LOTUS_GATEWAY_MODE" filecoin_storage.py; then
        # Add gateway mode flag
        sed -i '/LOTUS_AVAILABLE = False/a LOTUS_GATEWAY_MODE = False' filecoin_storage.py
        
        # Add check for gateway script
        sed -i '/if not LOTUS_AVAILABLE:/i # Check for Lotus gateway script\ngw_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "lotus")\nif os.path.exists(gw_script) and os.access(gw_script, os.X_OK):\n    try:\n        result = subprocess.run([gw_script, "version"], capture_output=True, text=True)\n        if "Gateway Client" in result.stdout:\n            LOTUS_PATH = gw_script\n            LOTUS_AVAILABLE = True\n            LOTUS_GATEWAY_MODE = True\n            logger.info(f"Using Lotus gateway script")\n    except Exception as e:\n        logger.warning(f"Error testing gateway script: {e}")' filecoin_storage.py
    fi
    
    echo "Filecoin storage implementation updated."
else
    echo "⚠️ Warning: filecoin_storage.py not found. Manual updates may be needed."
fi

# Create MCP configuration
mkdir -p logs
cat > mcp_gateway_config.sh << EOF
#!/bin/bash
# MCP Filecoin Gateway Configuration

# Filecoin gateway configuration
export LOTUS_PATH="$HOME/.lotus-gateway"
export LOTUS_GATEWAY_MODE="true"
export PATH="$(pwd)/bin:$PATH"

echo "Filecoin gateway configured with:"
echo "  API: $GATEWAY_API"
echo "  Lotus script: $(pwd)/bin/lotus"
EOF

chmod +x mcp_gateway_config.sh

# Restart MCP server
echo "Restarting MCP server with Filecoin gateway configuration..."
pkill -f "enhanced_mcp_server.py" || true
sleep 2

source .venv/bin/activate
source ./mcp_gateway_config.sh
nohup python enhanced_mcp_server.py --port 9997 --debug > logs/enhanced_mcp_filecoin.log 2>&1 &
PID=$!
echo $PID > mcp_server.pid
echo "MCP server started with PID $PID"

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Check server health
echo "Checking MCP server health..."
if curl -s http://localhost:9997/api/v0/health | grep -q "filecoin"; then
    echo "✅ MCP server is running with Filecoin integration!"
    echo "  Health status: http://localhost:9997/api/v0/health"
    echo "  Server logs: $(pwd)/logs/enhanced_mcp_filecoin.log"
else
    echo "⚠️ Warning: MCP server may not be running correctly."
    echo "  Check logs: $(pwd)/logs/enhanced_mcp_filecoin.log"
fi

echo "Setup complete."