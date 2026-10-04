#!/bin/bash
# Final Deployment Verification Script
# Checks all components of the MCP server deployment

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
SERVER_FILE="final_mcp_server_enhanced.py"
PORT=9998

echo -e "${BOLD}🚀 Final MCP Server Deployment Verification${NC}"
echo "=============================================="

# Function to check and report status
check_status() {
    local test_name="$1"
    local command="$2"
    
    echo -n "Checking $test_name... "
    
    if eval "$command" &>/dev/null; then
        echo -e "${GREEN}✅ PASS${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        return 1
    fi
}

# Track overall success
OVERALL_SUCCESS=true

# 1. File Structure Checks
echo -e "\n${BLUE}📁 File Structure Verification${NC}"
echo "--------------------------------"

FILES=(
    "final_mcp_server_enhanced.py:Enhanced MCP Server"
    "final_mcp_server.py:Original MCP Server"
    "Dockerfile:Main Docker Configuration" 
    "Dockerfile.final:Production Docker Configuration"
    "docker-compose.final.yml:Docker Compose Configuration"
    "run_final_mcp.sh:Deployment Script"
    ".github/workflows/final-mcp-server.yml:CI/CD Workflow"
    "requirements.txt:Python Dependencies"
)

for file_info in "${FILES[@]}"; do
    IFS=':' read -r file desc <<< "$file_info"
    if ! check_status "$desc" "test -f '$file'"; then
        OVERALL_SUCCESS=false
    fi
done

# 2. Python Environment Checks
echo -e "\n${BLUE}🐍 Python Environment Verification${NC}"
echo "-----------------------------------"

if ! check_status "Python Installation" "python --version"; then
    OVERALL_SUCCESS=false
fi

if ! check_status "Required Packages" "python -c 'import fastapi, uvicorn, pydantic'"; then
    OVERALL_SUCCESS=false
fi

if ! check_status "Server Syntax" "python -m py_compile $SERVER_FILE"; then
    OVERALL_SUCCESS=false
fi

if ! check_status "Server Import" "python -c 'import final_mcp_server_enhanced'"; then
    OVERALL_SUCCESS=false
fi

# 3. Docker Environment Checks
echo -e "\n${BLUE}🐳 Docker Environment Verification${NC}"
echo "-----------------------------------"

if ! check_status "Docker Installation" "docker --version"; then
    OVERALL_SUCCESS=false
fi

if ! check_status "Docker Compose Installation" "docker-compose --version"; then
    OVERALL_SUCCESS=false
fi

if ! check_status "Dockerfile Syntax" "docker build -t mcp-syntax-check -f Dockerfile --target syntax-check . 2>/dev/null || docker build -t mcp-syntax-check -f Dockerfile . >/dev/null 2>&1"; then
    OVERALL_SUCCESS=false
fi

if ! check_status "Docker Compose Config" "docker-compose -f docker-compose.final.yml config >/dev/null"; then
    OVERALL_SUCCESS=false
fi

# 4. Configuration Verification
echo -e "\n${BLUE}⚙️  Configuration Verification${NC}"
echo "-------------------------------"

# Check if Dockerfile uses enhanced server
if grep -q "final_mcp_server_enhanced.py" Dockerfile; then
    echo -e "Dockerfile CMD: ${GREEN}✅ Uses enhanced server${NC}"
else
    echo -e "Dockerfile CMD: ${RED}❌ Does not use enhanced server${NC}"
    OVERALL_SUCCESS=false
fi

# Check if CI/CD workflow includes enhanced server
if grep -q "final_mcp_server_enhanced.py" .github/workflows/final-mcp-server.yml; then
    echo -e "CI/CD Workflow: ${GREEN}✅ Includes enhanced server${NC}"
else
    echo -e "CI/CD Workflow: ${RED}❌ Does not include enhanced server${NC}"
    OVERALL_SUCCESS=false
fi

# Check if deployment script uses enhanced server
if grep -q "final_mcp_server_enhanced.py" run_final_mcp.sh; then
    echo -e "Deployment Script: ${GREEN}✅ Uses enhanced server${NC}"
else
    echo -e "Deployment Script: ${RED}❌ Does not use enhanced server${NC}"
    OVERALL_SUCCESS=false
fi

# 5. Server Functionality Test
echo -e "\n${BLUE}🔧 Server Functionality Verification${NC}"
echo "-------------------------------------"

# Start server in background for testing
echo "Starting server for functionality test..."
python $SERVER_FILE --host 127.0.0.1 --port $PORT &
SERVER_PID=$!

# Wait for server to start
sleep 5

# Test health endpoint
if curl -s "http://127.0.0.1:$PORT/health" | grep -q "healthy"; then
    echo -e "Health Endpoint: ${GREEN}✅ Responding correctly${NC}"
else
    echo -e "Health Endpoint: ${RED}❌ Not responding or unhealthy${NC}"
    OVERALL_SUCCESS=false
fi

# Test root endpoint
if curl -s "http://127.0.0.1:$PORT/" | grep -q "Final MCP Server"; then
    echo -e "Root Endpoint: ${GREEN}✅ Responding correctly${NC}"
else
    echo -e "Root Endpoint: ${RED}❌ Not responding correctly${NC}"
    OVERALL_SUCCESS=false
fi

# Test docs endpoint
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/docs" | grep -q "200"; then
    echo -e "Docs Endpoint: ${GREEN}✅ Accessible${NC}"
else
    echo -e "Docs Endpoint: ${RED}❌ Not accessible${NC}"
    OVERALL_SUCCESS=false
fi

# Stop the test server
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

# 6. Deployment Readiness
echo -e "\n${BLUE}🚀 Deployment Readiness Summary${NC}"
echo "--------------------------------"

if [[ "$OVERALL_SUCCESS" == true ]]; then
    echo -e "${GREEN}${BOLD}🎉 ALL CHECKS PASSED!${NC}"
    echo ""
    echo -e "${GREEN}✅ Final MCP Server is PRODUCTION READY${NC}"
    echo ""
    echo "Available deployment options:"
    echo "  • Direct: python final_mcp_server_enhanced.py"
    echo "  • Script: ./run_final_mcp.sh start"
    echo "  • Docker: docker-compose -f docker-compose.final.yml up -d"
    echo ""
    echo "Monitoring endpoints:"
    echo "  • Health: http://localhost:9998/health"
    echo "  • Docs:   http://localhost:9998/docs"
    echo ""
    exit 0
else
    echo -e "${RED}${BOLD}❌ SOME CHECKS FAILED${NC}"
    echo ""
    echo -e "${YELLOW}Please review the failed checks above and fix any issues.${NC}"
    echo ""
    exit 1
fi
