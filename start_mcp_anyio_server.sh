#!/bin/bash
# AnyIO MCP Server Launcher Script

# Default values
PORT=8002
BACKEND="asyncio"
DEBUG=false
ISOLATION=false
LOG_LEVEL="INFO"
API_PREFIX="/api/v0/mcp"
HOST="0.0.0.0"
PERSISTENCE_PATH=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -p|--port)
      PORT="$2"
      shift
      shift
      ;;
    -b|--backend)
      BACKEND="$2"
      shift
      shift
      ;;
    -d|--debug)
      DEBUG=true
      shift
      ;;
    -i|--isolation)
      ISOLATION=true
      shift
      ;;
    -l|--log-level)
      LOG_LEVEL="$2"
      shift
      shift
      ;;
    --api-prefix)
      API_PREFIX="$2"
      shift
      shift
      ;;
    -h|--host)
      HOST="$2"
      shift
      shift
      ;;
    --persistence-path)
      PERSISTENCE_PATH="$2"
      shift
      shift
      ;;
    *)
      echo "Unknown option: $key"
      exit 1
      ;;
  esac
done

# Build command arguments
ARGS=("--port" "$PORT" "--host" "$HOST" "--log-level" "$LOG_LEVEL" "--api-prefix" "$API_PREFIX" "--backend" "$BACKEND")

if $DEBUG; then
  ARGS+=("--debug")
fi

if $ISOLATION; then
  ARGS+=("--isolation")
fi

if [ -n "$PERSISTENCE_PATH" ]; then
  ARGS+=("--persistence-path" "$PERSISTENCE_PATH")
fi

# Print server info
echo "Starting MCP server with AnyIO support"
echo "-------------------------------------"
echo "Host:                $HOST"
echo "Port:                $PORT"
echo "Backend:             $BACKEND"
echo "Debug Mode:          $DEBUG"
echo "Isolation Mode:      $ISOLATION"
echo "Log Level:           $LOG_LEVEL"
echo "API Prefix:          $API_PREFIX"
if [ -n "$PERSISTENCE_PATH" ]; then
  echo "Persistence Path:    $PERSISTENCE_PATH"
fi
echo "-------------------------------------"

# Run the server
python run_mcp_server_anyio.py "${ARGS[@]}"