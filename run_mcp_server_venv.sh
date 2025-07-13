#!/bin/bash

# Script to run the MCP server with comprehensive backend monitoring in virtual environment

echo "🔧 Activating virtual environment..."
cd /home/barberb/ipfs_kit_py
source venv/bin/activate

echo "🐍 Using Python: $(which python)"
echo "📦 Python version: $(python --version)"

echo "🚀 Starting MCP server with comprehensive backend monitoring..."
echo "📊 Dashboard will be available at: http://127.0.0.1:8765/dashboard"
echo "🔌 MCP HTTP API at: http://127.0.0.1:8765/mcp"
echo "🔌 MCP WebSocket at: ws://127.0.0.1:8765/mcp/ws"
echo "📈 Metrics at: http://127.0.0.1:8765/metrics"
echo "💚 Health check at: http://127.0.0.1:8765/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=================================="

# Set environment variables for better performance
export PYTHONUNBUFFERED=1
export IPFS_KIT_DISABLE_LIBP2P=1

# Run the server
python mcp/integrated_mcp_server_with_dashboard.py
