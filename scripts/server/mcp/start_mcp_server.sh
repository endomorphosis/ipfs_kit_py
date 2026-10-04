#!/bin/bash
#
# MCP Server Launcher Script
# This script configures and starts the MCP server with optimal settings
#

# Set error handling
set -e

# Create logs directory
mkdir -p logs

# Stop any running MCP server instances
echo "Stopping any running MCP server instances..."
pkill -f "python.*enhanced_mcp_server.py" || echo "No running MCP server found"
sleep 2  # Give processes time to terminate

# Ensure IPFS daemon is running
echo "Checking IPFS daemon..."
ipfs --version >/dev/null 2>&1 || { echo "IPFS is not installed or not in PATH"; exit 1; }
ipfs id >/dev/null 2>&1 || { 
    echo "Starting IPFS daemon..."
    nohup ipfs daemon --routing=dht > logs/ipfs_daemon.log 2>&1 &
    sleep 3  # Give IPFS daemon time to start
}
echo "IPFS daemon is running"

# Set up environment variables for storage backends
echo "Configuring storage backends..."

# Create directories for mock storage if needed
mkdir -p ~/.ipfs_kit/mock_huggingface
mkdir -p ~/.ipfs_kit/mock_s3/ipfs-storage-demo
mkdir -p ~/.ipfs_kit/mock_filecoin/deals
mkdir -p ~/.ipfs_kit/mock_storacha
mkdir -p ~/.ipfs_kit/mock_lassie

# Configure environment variables
cat > mcp_config.sh << 'EOF'
#!/bin/bash

# Use mock mode only as fallback if real credentials are not available
export MCP_USE_MOCK_MODE="false"

# HuggingFace configuration
if [ -f ~/.cache/huggingface/token ]; then
  export HUGGINGFACE_TOKEN=$(cat ~/.cache/huggingface/token)
  echo "Found HuggingFace token"
else
  echo "No HuggingFace token found, will use mock mode"
  export HF_MOCK_MODE="true"
fi

# AWS S3 configuration - check for credentials
if [ -f ~/.aws/credentials ] || [ -n "$AWS_ACCESS_KEY_ID" ]; then
  echo "AWS credentials found"
  # AWS credentials will be loaded from environment or ~/.aws/credentials
  export AWS_S3_BUCKET_NAME="ipfs-storage-demo"
else
  echo "No AWS credentials found, will use mock mode"
  export AWS_S3_BUCKET_NAME="ipfs-storage-demo"
  export AWS_ACCESS_KEY_ID="mock_key"
  export AWS_SECRET_ACCESS_KEY="mock_secret"
  export AWS_DEFAULT_REGION="us-east-1"
fi

# Filecoin configuration
if [ -n "$LOTUS_API_TOKEN" ] && [ -n "$LOTUS_API_ENDPOINT" ]; then
  echo "Lotus API credentials found"
else
  echo "No Lotus API credentials found, will use mock mode"
  export LOTUS_API_TOKEN="mock_token"
  export LOTUS_API_ENDPOINT="http://localhost:1234/rpc/v0"
fi

# Storacha configuration
if [ -n "$STORACHA_API_KEY" ]; then
  echo "Storacha API key found"
else
  echo "No Storacha API key found, will use mock mode"
  export STORACHA_API_KEY="mock_key"
fi

# Lassie configuration
if [ -n "$LASSIE_API_URL" ]; then
  echo "Lassie API URL found"
else
  echo "No Lassie API configuration found, will use mock mode"
  export LASSIE_API_URL="http://localhost:5000"
  export LASSIE_ENABLED="true"
fi

# Fix any permissions issues in the directories
chmod -R 755 ~/.ipfs_kit 2>/dev/null || true
EOF

chmod +x mcp_config.sh
source ./mcp_config.sh

# Ensure dependencies are installed
echo "Checking dependencies..."
source .venv/bin/activate
pip install -q requests huggingface_hub boto3 2>/dev/null || echo "Some dependencies may be missing"

# Create mock data for testing
echo "Setting up mock data for testing..."
mkdir -p ~/.ipfs_kit/mock_s3/ipfs-storage-demo/test
echo "This is a test file for MCP server" > ~/.ipfs_kit/mock_s3/ipfs-storage-demo/test/test.txt

mkdir -p ~/.ipfs_kit/mock_huggingface/test
echo "This is a test file for HuggingFace" > ~/.ipfs_kit/mock_huggingface/test/test.txt

# Create PID file directory if it doesn't exist
mkdir -p /tmp/mcp

# Start the MCP server
echo "Starting MCP server..."
cd "$(dirname "$0")"
source .venv/bin/activate
nohup python enhanced_mcp_server.py --port 9997 --debug > logs/enhanced_mcp_server.log 2>&1 &
echo $! > /tmp/mcp/server.pid

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Check if server is running
if curl -s http://localhost:9997/api/v0/health > /dev/null; then
    echo "MCP server started successfully on port 9997"
    echo "---------------------------------------------"
    echo "Server status:"
    curl -s http://localhost:9997/api/v0/health | python3 -m json.tool
    echo "---------------------------------------------"
    echo "Server log is available at: $(pwd)/logs/enhanced_mcp_server.log"
    echo "To stop the server: kill \$(cat /tmp/mcp/server.pid)"
    exit 0
else
    echo "Failed to start MCP server. Check logs at $(pwd)/logs/enhanced_mcp_server.log"
    exit 1
fi