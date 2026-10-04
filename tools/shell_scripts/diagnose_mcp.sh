#!/bin/bash

echo "=== MCP Server Diagnostic Tool ==="
echo "Running on: $(date)"
echo "Python version: $(python3 --version)"
echo "Current directory: $(pwd)"

# Check server script
if [ -f "final_mcp_server.py" ]; then
    echo "✅ Server script final_mcp_server.py exists"
    # Check if executable
    if [ -x "final_mcp_server.py" ]; then
        echo "✅ Script is executable"
    else
        echo "⚠️ Script is not executable. Fix with: chmod +x final_mcp_server.py"
    fi
else
    echo "❌ Server script final_mcp_server.py not found"
fi

# Check PID file
if [ -f "final_mcp_server.pid" ]; then
    PID=$(cat final_mcp_server.pid)
    if ps -p $PID > /dev/null; then
        echo "✅ Server process with PID $PID is running"
    else
        echo "⚠️ PID file exists but process $PID is not running"
    fi
else
    echo "ℹ️ No PID file found. Server is not running or was not properly started"
fi

# Check log file
if [ -f "final_mcp_server.log" ]; then
    echo "✅ Log file exists"
    echo "Recent errors:"
    grep -i "error" final_mcp_server.log | tail -5
else
    echo "⚠️ No log file found"
fi

# Check port usage
PORT=9998
if netstat -tuln | grep -q ":$PORT "; then
    echo "ℹ️ Port $PORT is in use"
    # Try to identify the process
    echo "Process using port $PORT:"
    lsof -i :$PORT
else
    echo "ℹ️ Port $PORT is available"
fi

# Check Python dependencies
echo -e "\nChecking Python dependencies:"
for pkg in fastapi uvicorn jsonrpcserver requests; do
    if python3 -c "import $pkg" 2>/dev/null; then
        echo "✅ $pkg is installed"
    else
        echo "❌ $pkg is not installed. Install with: pip install $pkg"
    fi
done

echo -e "\nDiagnostic complete."
echo "To start the server, run: python3 final_mcp_server.py --debug"
echo "To check server status, run: python3 check_server.py"
