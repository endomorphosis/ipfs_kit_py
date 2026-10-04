#!/bin/bash
# Startup script for VS Code MCP Server Integration

set -e

echo "=== VS Code MCP Server Setup ==="
echo "Starting IPFS Kit MCP Server for VS Code integration..."

# Change to project directory
cd /home/barberb/ipfs_kit_py

# Function to kill existing servers
cleanup_servers() {
    echo "Stopping any existing MCP servers..."
    pkill -f "vscode_mcp_server.py" 2>/dev/null || true
    pkill -f "python.*mcp.*server" 2>/dev/null || true
    sleep 2
}

# Function to check dependencies
check_dependencies() {
    echo "Checking dependencies..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo "ERROR: Python 3 is required but not installed"
        exit 1
    fi
    
    # Check required packages and install if missing
    if ! python3 -c "import starlette, uvicorn" 2>/dev/null; then
        echo "Installing required packages..."
        pip install starlette uvicorn psutil
    fi
    
    echo "Dependencies OK"
}

# Function to start the server
start_server() {
    local port=${1:-9996}
    
    echo "Starting MCP server on port $port..."
    
    # Start server in background
    python3 vscode_mcp_server.py --port $port --host 127.0.0.1 > vscode_mcp_server.log 2>&1 &
    local server_pid=$!
    
    # Save PID
    echo $server_pid > vscode_mcp_server.pid
    echo "Server started with PID: $server_pid"
    
    # Wait for server to initialize
    echo "Waiting for server to initialize..."
    sleep 3
    
    # Test server health
    local retries=5
    while [ $retries -gt 0 ]; do
        if curl -s http://127.0.0.1:$port/health > /dev/null 2>&1; then
            echo "✓ Server is healthy and responding"
            break
        else
            echo "Waiting for server... ($retries retries left)"
            sleep 2
            ((retries--))
        fi
    done
    
    if [ $retries -eq 0 ]; then
        echo "ERROR: Server failed to start properly"
        cat vscode_mcp_server.log
        exit 1
    fi
    
    # Test initialization endpoint
    echo "Testing MCP initialization..."
    local tools_count=$(curl -s -X POST http://127.0.0.1:$port/initialize | jq -r '.tools | length' 2>/dev/null || echo "unknown")
    echo "✓ MCP server initialized with $tools_count tools"
    
    return 0
}

# Function to create VS Code settings
create_vscode_config() {
    echo "Creating VS Code MCP configuration..."
    
    local vscode_dir=".vscode"
    mkdir -p "$vscode_dir"
    
    # Create VS Code settings for MCP integration
    cat > "$vscode_dir/settings.json" << 'EOF'
{
    "mcp.servers": {
        "ipfs-kit": {
            "command": "python3",
            "args": [
                "/home/barberb/ipfs_kit_py/vscode_mcp_server.py",
                "--port", "9996",
                "--host", "127.0.0.1"
            ],
            "env": {
                "PYTHONPATH": "/home/barberb/ipfs_kit_py"
            }
        }
    },
    "mcp.enabled": true,
    "cline.mcpServers": {
        "ipfs-kit": {
            "command": "python3",
            "args": [
                "/home/barberb/ipfs_kit_py/vscode_mcp_server.py", 
                "--port", "9996"
            ]
        }
    }
}
EOF
    
    echo "✓ VS Code settings created in $vscode_dir/settings.json"
}

# Function to show usage information
show_usage_info() {
    echo ""
    echo "=== MCP Server Integration Complete ==="
    echo ""
    echo "Server Information:"
    echo "  • URL: http://127.0.0.1:9996"
    echo "  • Health Check: curl http://127.0.0.1:9996/health"
    echo "  • Log File: vscode_mcp_server.log"
    echo "  • PID File: vscode_mcp_server.pid"
    echo ""
    echo "Available Tools:"
    echo "  • ipfs_add - Add content to IPFS"
    echo "  • ipfs_get - Retrieve content by CID"
    echo "  • ipfs_pin - Pin content to prevent GC"
    echo "  • ipfs_cluster_status - Get cluster status"
    echo "  • filesystem_health - Check disk usage"
    echo "  • system_health - Get system metrics"
    echo ""
    echo "VS Code Integration:"
    echo "  1. Install the MCP extension in VS Code"
    echo "  2. The configuration is already set in .vscode/settings.json"
    echo "  3. Restart VS Code to load the MCP server"
    echo ""
    echo "Manual Testing:"
    echo "  • curl -X POST http://127.0.0.1:9996/initialize"
    echo "  • curl -X POST http://127.0.0.1:9996/tools/list"
    echo ""
    echo "To stop the server:"
    echo "  • kill \$(cat vscode_mcp_server.pid)"
    echo "  • or run: pkill -f vscode_mcp_server.py"
    echo ""
}

# Main execution
main() {
    local port=${1:-9996}
    
    cleanup_servers
    check_dependencies
    start_server $port
    create_vscode_config
    show_usage_info
    
    echo "✓ MCP Server is ready for VS Code integration!"
}

# Handle script arguments
case "${1:-}" in
    -h|--help)
        echo "Usage: $0 [PORT]"
        echo "Start the VS Code MCP Server for IPFS Kit"
        echo ""
        echo "Arguments:"
        echo "  PORT    Port number (default: 9996)"
        echo ""
        echo "Options:"
        echo "  -h, --help    Show this help message"
        echo "  --stop        Stop the running server"
        echo "  --status      Check server status"
        exit 0
        ;;
    --stop)
        echo "Stopping MCP server..."
        cleanup_servers
        echo "✓ Server stopped"
        exit 0
        ;;
    --status)
        if [ -f "vscode_mcp_server.pid" ]; then
            local pid=$(cat vscode_mcp_server.pid)
            if ps -p $pid > /dev/null 2>&1; then
                echo "✓ MCP server is running (PID: $pid)"
                curl -s http://127.0.0.1:9996/health | jq . 2>/dev/null || echo "Server not responding"
            else
                echo "✗ MCP server is not running (stale PID file)"
            fi
        else
            echo "✗ MCP server is not running (no PID file)"
        fi
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
