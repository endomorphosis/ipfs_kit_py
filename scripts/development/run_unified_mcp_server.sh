#!/bin/bash

# Enhanced Unified MCP Server Startup Script for Virtual Environment
# ==================================================================

echo "🚀 Starting Unified IPFS Kit MCP Server with Full Observability"
echo "================================================================="

# Navigate to project directory
cd /home/barberb/ipfs_kit_py

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Show environment info
echo "🐍 Python environment:"
echo "  - Python executable: $(which python)"
echo "  - Python version: $(python --version)"
echo "  - Working directory: $(pwd)"

# Install/upgrade dependencies
echo "📦 Checking dependencies..."
pip install --quiet --upgrade pip

# Core dependencies for the unified server
echo "📚 Installing core dependencies..."
pip install --quiet fastapi uvicorn jinja2 websockets requests psutil pyyaml

# Enhanced dependencies for full observability
echo "🔍 Installing observability dependencies..."
pip install --quiet prometheus-client aiofiles python-multipart

# Optional IPFS Kit dependencies (with error handling)
echo "🔧 Installing IPFS Kit dependencies..."
pip install --quiet --no-deps -e . 2>/dev/null || echo "⚠️ Some IPFS Kit dependencies may be missing (continuing...)"

# Set environment variables for better observability
echo "⚙️ Setting environment variables..."
export PYTHONUNBUFFERED=1
export IPFS_KIT_DISABLE_LIBP2P=1
export MCP_LOG_LEVEL=INFO
export DASHBOARD_ENABLE_DEBUG=1

# Create logs directory
mkdir -p logs

# Check server status and stop any existing instance
echo "🔍 Checking for existing server instances..."
if lsof -i :8765 > /dev/null 2>&1; then
    echo "⚠️ Port 8765 is in use. Stopping existing processes..."
    pkill -f "unified_mcp_server_with_full_observability.py" 2>/dev/null || true
    pkill -f "integrated_mcp_server_with_dashboard.py" 2>/dev/null || true
    sleep 2
    
    if lsof -i :8765 > /dev/null 2>&1; then
        echo "🔧 Force killing processes on port 8765..."
        kill -9 $(lsof -t -i:8765) 2>/dev/null || true
        sleep 1
    fi
fi

# Start the unified server with full observability
echo ""
echo "🚀 Starting Unified MCP Server with Full Observability..."
echo "========================================================="
echo "📊 Dashboard:      http://127.0.0.1:8765/dashboard"
echo "🔌 MCP HTTP API:   http://127.0.0.1:8765/mcp"
echo "🔌 MCP WebSocket:  ws://127.0.0.1:8765/mcp/ws"
echo "🔍 Observability:  http://127.0.0.1:8765/observability"
echo "🐛 Debug Console:  http://127.0.0.1:8765/debug"
echo "📈 Metrics:        http://127.0.0.1:8765/metrics"
echo "💚 Health Check:   http://127.0.0.1:8765/health"
echo "📚 API Docs:       http://127.0.0.1:8765/docs"
echo ""
echo "Server logs will be saved to: /tmp/unified_mcp_server.log"
echo "Press Ctrl+C to stop the server"
echo "========================================================="
echo ""

# Run the unified server
python mcp/unified_mcp_server_with_full_observability.py --host 127.0.0.1 --port 8765
