#!/bin/bash
#
# Enhanced MCP Server Start Script
# This script starts the enhanced MCP server with all extensions properly initialized.
#

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
PORT=9994
DEBUG="true"
ISOLATION="true"
SKIP_DAEMON="true"
API_PREFIX="/api/v0"
LOG_FILE="mcp_server.log"
BACKGROUND="true"

# Function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --port=NUMBER         Port number to use (default: 9994)"
    echo "  --no-debug            Disable debug mode"
    echo "  --no-isolation        Disable isolation mode"
    echo "  --no-skip-daemon      Don't skip daemon initialization"
    echo "  --api-prefix=PATH     Set the API prefix (default: /api/v0)"
    echo "  --log-file=FILE       Log file to use (default: mcp_server.log)"
    echo "  --foreground          Run in foreground (don't detach)"
    echo "  --help                Show this help message"
    exit 1
}

# Parse command line options
for arg in "$@"; do
    case $arg in
        --port=*)
            PORT="${arg#*=}"
            ;;
        --no-debug)
            DEBUG="false"
            ;;
        --no-isolation)
            ISOLATION="false"
            ;;
        --no-skip-daemon)
            SKIP_DAEMON="false"
            ;;
        --api-prefix=*)
            API_PREFIX="${arg#*=}"
            ;;
        --log-file=*)
            LOG_FILE="${arg#*=}"
            ;;
        --foreground)
            BACKGROUND="false"
            ;;
        --help)
            show_usage
            ;;
        *)
            echo -e "${YELLOW}Unknown option: $arg${NC}"
            show_usage
            ;;
    esac
done

# Create logs directory if it doesn't exist
mkdir -p logs

# Stop any running instances
echo -e "${YELLOW}Checking for running MCP server instances...${NC}"
PID_FILE="/tmp/mcp_server.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        echo -e "${YELLOW}Found running MCP server with PID $PID. Stopping it...${NC}"
        kill "$PID" 2>/dev/null || true
        sleep 2
    else
        echo -e "${YELLOW}No running MCP server found with PID $PID${NC}"
    fi
    rm -f "$PID_FILE"
else
    echo -e "${YELLOW}No PID file found, checking for running processes...${NC}"
    pkill -f "python.*mcp_server" 2>/dev/null || echo -e "${YELLOW}No running MCP server found${NC}"
    sleep 2
fi

# Ensure the log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Run the MCP compatibility verification and fixes
echo -e "${GREEN}Running MCP compatibility checks and fixes...${NC}"
python verify_mcp_compatibility.py

# Create proper MCP settings for Cline if needed
SETTINGS_DIR=".config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings"
SETTINGS_FILE="$SETTINGS_DIR/cline_mcp_settings.json"

if [ ! -f "$SETTINGS_FILE" ]; then
    echo -e "${YELLOW}Creating MCP settings file for Cline integration...${NC}"
    mkdir -p "$SETTINGS_DIR"
    cat > "$SETTINGS_FILE" << EOL
{
  "mcpServers": [
    {
      "name": "ipfs-kit-mcp",
      "description": "IPFS Kit MCP Server with storage backends (IPFS, Filecoin, Hugging Face, Storacha, Lassie, S3)",
      "url": "http://localhost:${PORT}${API_PREFIX}",
      "enabled": true,
      "authentication": {
        "type": "none"
      },
      "resources": [
        {
          "uri": "ipfs://info",
          "description": "IPFS node information",
          "mediaType": "application/json"
        },
        {
          "uri": "storage://backends",
          "description": "Available storage backends",
          "mediaType": "application/json"
        }
      ],
      "tools": [
        {
          "name": "ipfs_add",
          "description": "Add content to IPFS",
          "inputSchema": {
            "type": "object",
            "properties": {
              "content": {
                "type": "string",
                "description": "Content to add to IPFS"
              },
              "pin": {
                "type": "boolean",
                "description": "Whether to pin the content",
                "default": true
              }
            },
            "required": ["content"]
          },
          "outputSchema": {
            "type": "object",
            "properties": {
              "cid": {
                "type": "string",
                "description": "Content identifier (CID) of the added content"
              },
              "size": {
                "type": "integer",
                "description": "Size of the added content in bytes"
              }
            }
          }
        },
        {
          "name": "ipfs_cat",
          "description": "Retrieve content from IPFS",
          "inputSchema": {
            "type": "object",
            "properties": {
              "cid": {
                "type": "string",
                "description": "Content identifier (CID) to retrieve"
              }
            },
            "required": ["cid"]
          },
          "outputSchema": {
            "type": "object",
            "properties": {
              "content": {
                "type": "string",
                "description": "Retrieved content"
              }
            }
          }
        },
        {
          "name": "ipfs_pin",
          "description": "Pin content in IPFS",
          "inputSchema": {
            "type": "object",
            "properties": {
              "cid": {
                "type": "string",
                "description": "Content identifier (CID) to pin"
              }
            },
            "required": ["cid"]
          },
          "outputSchema": {
            "type": "object",
            "properties": {
              "success": {
                "type": "boolean",
                "description": "Whether the pinning was successful"
              }
            }
          }
        },
        {
          "name": "storage_transfer",
          "description": "Transfer content between storage backends",
          "inputSchema": {
            "type": "object",
            "properties": {
              "source": {
                "type": "string",
                "description": "Source storage backend (ipfs, filecoin, huggingface, storacha, lassie, s3)"
              },
              "destination": {
                "type": "string",
                "description": "Destination storage backend (ipfs, filecoin, huggingface, storacha, lassie, s3)"
              },
              "identifier": {
                "type": "string",
                "description": "Content identifier in the source backend"
              }
            },
            "required": ["source", "destination", "identifier"]
          },
          "outputSchema": {
            "type": "object",
            "properties": {
              "success": {
                "type": "boolean",
                "description": "Whether the transfer was successful"
              },
              "destinationId": {
                "type": "string",
                "description": "Identifier of the content in the destination backend"
              }
            }
          }
        }
      ]
    }
  ]
}
EOL
    echo -e "${GREEN}Created MCP settings file for Cline integration${NC}"
else
    echo -e "${GREEN}MCP settings file for Cline integration already exists${NC}"
fi

# Set environment variables for MCP server
export MCP_DEBUG_MODE=$DEBUG
export MCP_ISOLATION_MODE=$ISOLATION
export MCP_SKIP_DAEMON=$SKIP_DAEMON
export MCP_PORT=$PORT
export MCP_API_PREFIX=$API_PREFIX
export PYTHONPATH=$(pwd):$PYTHONPATH

# Make sure the script is executable
chmod +x enhanced_mcp_server_fixed.py

# Build the command with all options
CMD="./enhanced_mcp_server_fixed.py --port $PORT --api-prefix $API_PREFIX --log-file $LOG_FILE"
[ "$DEBUG" = "false" ] && CMD="$CMD --no-debug"
[ "$ISOLATION" = "false" ] && CMD="$CMD --no-isolation"
[ "$SKIP_DAEMON" = "false" ] && CMD="$CMD --no-skip-daemon"

# Start the server
echo -e "${GREEN}Starting Enhanced MCP server on port $PORT...${NC}"
if [ "$BACKGROUND" = "true" ]; then
    # Start in background
    nohup python $CMD > "logs/enhanced_mcp_server_stdout.log" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    echo -e "${GREEN}Enhanced MCP server started with PID $PID${NC}"
    echo -e "${GREEN}Logs are being saved to: $LOG_FILE and logs/enhanced_mcp_server_stdout.log${NC}"
    echo -e "${GREEN}To stop the server, run: ./stop_mcp_server.sh${NC}"
else
    # Start in foreground
    echo -e "${GREEN}Running Enhanced MCP server in foreground...${NC}"
    python $CMD
fi

# Check if server started successfully
if [ "$BACKGROUND" = "true" ]; then
    echo -e "${YELLOW}Waiting for server to start...${NC}"
    sleep 5
    if ps -p "$PID" > /dev/null; then
        echo -e "${GREEN}Enhanced MCP server is running. Testing health endpoint...${NC}"
        if curl -s "http://localhost:$PORT$API_PREFIX/health" > /dev/null 2>&1; then
            echo -e "${GREEN}Enhanced MCP server is healthy${NC}"
            echo -e "${GREEN}You can access the API at: http://localhost:$PORT$API_PREFIX${NC}"
            echo -e "${GREEN}API documentation available at: http://localhost:$PORT/docs${NC}"
            
            # Test tools health endpoint
            if curl -s "http://localhost:$PORT$API_PREFIX/tools/health" > /dev/null 2>&1; then
                echo -e "${GREEN}MCP tools are available${NC}"
                echo -e "${GREEN}To test the tools, run: python test_mcp_tools.py${NC}"
            else
                echo -e "${YELLOW}MCP tools health check failed.${NC}"
                echo -e "${YELLOW}Check the logs at: $LOG_FILE${NC}"
            fi
        else
            echo -e "${YELLOW}Enhanced MCP server did not respond to health check.${NC}"
            echo -e "${YELLOW}This might be normal if the server is still starting.${NC}"
            echo -e "${YELLOW}Check the logs at: $LOG_FILE${NC}"
        fi
    else
        echo -e "${RED}Enhanced MCP server failed to start. Check the logs at: $LOG_FILE${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Enhanced MCP server startup complete${NC}"
