#!/bin/bash
# Final MCP Server - Complete Solution Runner
# This script provides all functionality for running and testing the final MCP server

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
SERVER_FILE="final_mcp_server_enhanced.py"
ORIGINAL_SERVER="final_mcp_server.py"
VENV_DIR=".venv"
PORT=9998
HOST="0.0.0.0"
LOG_FILE="final_mcp_server.log"
PID_FILE="final_mcp_server.pid"

# Ensure we're in the right directory
cd "$(dirname "${BASH_SOURCE[0]}")"

# Helper functions
log() {
    local level="$1"
    local message="$2"
    local color=""
    
    case "$level" in
        "INFO")  color="$GREEN" ;;
        "WARN")  color="$YELLOW" ;;
        "ERROR") color="$RED" ;;
        "DEBUG") color="$BLUE" ;;
        *)       color="$NC" ;;
    esac
    
    echo -e "${color}[$(date +'%Y-%m-%d %H:%M:%S')] ${level}: ${message}${NC}"
}

print_banner() {
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════════╗
║                        🚀 FINAL MCP SERVER 🚀                           ║
║                      Complete Solution & Testing                        ║
║                                                                          ║
║  This is the DEFINITIVE MCP server for ipfs_kit_py                      ║
║  ✅ Production-ready FastAPI server                                       ║
║  ✅ Mock IPFS implementation for reliable testing                         ║
║  ✅ Docker and CI/CD ready                                                ║
║  ✅ VS Code MCP integration compatible                                    ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
EOF
}

check_dependencies() {
    log "INFO" "🔍 Checking dependencies..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log "ERROR" "Python3 is required but not installed"
        exit 1
    fi
    
    # Check virtual environment
    if [ ! -d "$VENV_DIR" ]; then
        log "WARN" "Virtual environment not found, creating one..."
        python3 -m venv "$VENV_DIR"
    fi
    
    # Activate virtual environment and install dependencies
    source "$VENV_DIR/bin/activate"
    
    log "INFO" "📦 Installing/updating dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install -e .
    
    log "INFO" "✅ Dependencies checked and installed"
}

test_server_syntax() {
    log "INFO" "🧪 Testing server syntax..."
    
    if ! python3 -m py_compile "$SERVER_FILE"; then
        log "ERROR" "Syntax check failed for $SERVER_FILE"
        return 1
    fi
    
    log "INFO" "✅ Syntax check passed"
}

test_imports() {
    log "INFO" "🔍 Testing imports..."
    
    if ! "$VENV_DIR/bin/python" -c "
import sys
sys.path.insert(0, '.')
try:
    import fastapi, uvicorn, pydantic
    print('✅ FastAPI dependencies available')
    
    # Test server import
    import ${SERVER_FILE%.*}
    print(f'✅ Server module imports successfully')
    print(f'   Version: {getattr(${SERVER_FILE%.*}, '__version__', 'Unknown')}')
except Exception as e:
    print(f'❌ Import failed: {e}')
    exit(1)
"; then
        log "ERROR" "Import test failed"
        return 1
    fi
    
    log "INFO" "✅ Import test passed"
}

start_server() {
    local background=${1:-false}
    
    log "INFO" "🚀 Starting Final MCP Server..."
    
    # Stop any existing server
    stop_server
    
    # Start server
    if [ "$background" = "true" ]; then
        log "INFO" "Starting server in background on $HOST:$PORT"
        "$VENV_DIR/bin/python" "$SERVER_FILE" --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
        local pid=$!
        echo $pid > "$PID_FILE"
        log "INFO" "Server started with PID: $pid"
    else
        log "INFO" "Starting server in foreground on $HOST:$PORT"
        "$VENV_DIR/bin/python" "$SERVER_FILE" --host "$HOST" --port "$PORT"
    fi
}

stop_server() {
    log "INFO" "⏹️ Stopping server..."
    
    # Kill by PID file
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            log "INFO" "Stopped server with PID: $pid"
        fi
        rm -f "$PID_FILE"
    fi
    
    # Kill by process name
    pkill -f "$SERVER_FILE" 2>/dev/null || true
    
    log "INFO" "✅ Server stopped"
}

test_api() {
    log "INFO" "🧪 Testing API endpoints..."
    
    local base_url="http://localhost:$PORT"
    local failed=0
    
    # Wait for server to start
    log "INFO" "⏳ Waiting for server to start..."
    for i in {1..30}; do
        if curl -s "$base_url/health" > /dev/null 2>&1; then
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            log "ERROR" "Server failed to start within 30 seconds"
            return 1
        fi
    done
    
    log "INFO" "🏥 Testing health endpoint..."
    if curl -s "$base_url/health" | grep -q "healthy"; then
        log "INFO" "✅ Health endpoint works"
    else
        log "ERROR" "❌ Health endpoint failed"
        ((failed++))
    fi
    
    log "INFO" "📋 Testing tools endpoint..."
    if curl -s "$base_url/mcp/tools" | grep -q "tools"; then
        log "INFO" "✅ Tools endpoint works"
    else
        log "ERROR" "❌ Tools endpoint failed"
        ((failed++))
    fi
    
    log "INFO" "📤 Testing IPFS add endpoint..."
    local add_response=$(curl -s -X POST "$base_url/ipfs/add" \
        -H "Content-Type: application/json" \
        -d '{"content": "Hello, Final MCP Server!"}')
    
    if echo "$add_response" | grep -q "success"; then
        log "INFO" "✅ IPFS add works"
        
        # Extract CID for cat test
        local cid=$(echo "$add_response" | grep -o '"cid":"[^"]*"' | cut -d'"' -f4)
        
        if [ -n "$cid" ]; then
            log "INFO" "📥 Testing IPFS cat endpoint with CID: $cid"
            if curl -s "$base_url/ipfs/cat/$cid" | grep -q "Hello, Final MCP Server!"; then
                log "INFO" "✅ IPFS cat works"
            else
                log "ERROR" "❌ IPFS cat failed"
                ((failed++))
            fi
        fi
    else
        log "ERROR" "❌ IPFS add failed"
        ((failed++))
    fi
    
    log "INFO" "🔍 Testing version endpoint..."
    if curl -s "$base_url/ipfs/version" | grep -q "Version"; then
        log "INFO" "✅ Version endpoint works"
    else
        log "ERROR" "❌ Version endpoint failed"
        ((failed++))
    fi
    
    if [ $failed -eq 0 ]; then
        log "INFO" "🎉 All API tests passed!"
        return 0
    else
        log "ERROR" "💥 $failed API tests failed"
        return 1
    fi
}

run_comprehensive_test() {
    log "INFO" "🧪 Running comprehensive test suite..."
    
    local failed=0
    
    # Test syntax
    if ! test_server_syntax; then
        ((failed++))
    fi
    
    # Test imports  
    if ! test_imports; then
        ((failed++))
    fi
    
    # Start server in background for API testing
    start_server true
    sleep 3
    
    # Test API
    if ! test_api; then
        ((failed++))
    fi
    
    # Stop server
    stop_server
    
    if [ $failed -eq 0 ]; then
        log "INFO" "🎉 ALL TESTS PASSED! The Final MCP Server is ready for production!"
        log "INFO" "📚 API Documentation: http://localhost:$PORT/docs"
        log "INFO" "🏥 Health Check: http://localhost:$PORT/health"
        log "INFO" "🐳 Docker: docker-compose -f docker-compose.final.yml up"
        return 0
    else
        log "ERROR" "💥 $failed test groups failed"
        return 1
    fi
}

show_help() {
    cat << EOF
Final MCP Server - Complete Solution Runner

USAGE:
    $0 [COMMAND] [OPTIONS]

COMMANDS:
    start           Start the server in foreground
    start-bg        Start the server in background
    stop            Stop the server
    restart         Restart the server
    test            Run comprehensive tests
    status          Check server status
    logs            Show server logs
    docker-build    Build Docker image
    docker-run      Run with Docker
    help            Show this help

EXAMPLES:
    $0 test                    # Run all tests
    $0 start                   # Start server in foreground
    $0 start-bg               # Start server in background
    $0 docker-build           # Build Docker image
    $0 docker-run             # Run with Docker Compose

The Final MCP Server provides:
✅ FastAPI-based REST API
✅ Mock IPFS implementation
✅ Health monitoring
✅ Docker support
✅ VS Code MCP integration
✅ Production-ready logging
EOF
}

# Main command handler
case "${1:-help}" in
    "start")
        print_banner
        check_dependencies
        start_server false
        ;;
    "start-bg")
        print_banner
        check_dependencies
        start_server true
        ;;
    "stop")
        stop_server
        ;;
    "restart")
        stop_server
        sleep 2
        check_dependencies
        start_server true
        ;;
    "test")
        print_banner
        check_dependencies
        run_comprehensive_test
        ;;
    "status")
        if [ -f "$PID_FILE" ]; then
            local pid=$(cat "$PID_FILE")
            if kill -0 "$pid" 2>/dev/null; then
                log "INFO" "✅ Server is running (PID: $pid)"
                curl -s "http://localhost:$PORT/health" | grep -q "healthy" && \
                    log "INFO" "✅ Server is healthy" || \
                    log "WARN" "⚠️ Server may not be responding"
            else
                log "INFO" "❌ Server is not running"
            fi
        else
            log "INFO" "❌ No PID file found - server is not running"
        fi
        ;;
    "logs")
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            log "ERROR" "No log file found"
        fi
        ;;
    "docker-build")
        log "INFO" "🐳 Building Docker image..."
        docker build -f Dockerfile.final -t final-mcp-server .
        log "INFO" "✅ Docker image built successfully"
        ;;
    "docker-run")
        log "INFO" "🐳 Running with Docker Compose..."
        docker-compose -f docker-compose.final.yml up -d
        log "INFO" "✅ Docker container started"
        log "INFO" "📚 API Documentation: http://localhost:9998/docs"
        ;;
    "help"|*)
        show_help
        ;;
esac
