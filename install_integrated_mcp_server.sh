#!/bin/bash
# Install the new integrated MCP server

echo "🚀 Installing Integrated MCP Server with IPFS and VFS Support"
echo "========================================================="

# Directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SOURCE_FILE="final_mcp_server.py.new"
TARGET_FILE="final_mcp_server.py"
BACKUP_FILE="final_mcp_server.py.bak.$(date +%Y%m%d%H%M%S)"

# Check if source file exists
if [ ! -f "$SOURCE_FILE" ]; then
    echo -e "${RED}❌ Source file $SOURCE_FILE does not exist.${NC}"
    exit 1
fi

# Check if server is running
if [ -f "final_mcp_server.pid" ]; then
    PID=$(cat "final_mcp_server.pid")
    if ps -p "$PID" > /dev/null; then
        echo -e "${YELLOW}⚠️ MCP server is currently running. Stopping it...${NC}"
        kill -15 "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null
        sleep 2
        echo -e "${GREEN}✅ MCP server stopped.${NC}"
    else
        echo -e "${YELLOW}⚠️ Stale PID file found. Removing it...${NC}"
        rm -f "final_mcp_server.pid"
    fi
fi

# Backup existing file if it exists
if [ -f "$TARGET_FILE" ]; then
    echo -e "${BLUE}Creating backup of existing $TARGET_FILE as $BACKUP_FILE...${NC}"
    cp "$TARGET_FILE" "$BACKUP_FILE"
    echo -e "${GREEN}✅ Backup created.${NC}"
fi

# Install the new server
echo -e "${BLUE}Installing new MCP server...${NC}"
cp "$SOURCE_FILE" "$TARGET_FILE"
chmod +x "$TARGET_FILE"
echo -e "${GREEN}✅ New MCP server installed.${NC}"

# Check if test file exists, if not, create it from existing test files
if [ ! -f "test_integrated_mcp_server.py" ] && [ -f "test_ipfs_methods.py" ]; then
    echo -e "${YELLOW}⚠️ test_integrated_mcp_server.py not found. Creating from existing test files...${NC}"
    cp "test_ipfs_methods.py" "test_integrated_mcp_server.py"
    chmod +x "test_integrated_mcp_server.py"
    echo -e "${GREEN}✅ Test file created.${NC}"
else
    chmod +x "test_integrated_mcp_server.py" 2>/dev/null || true
fi

# Create start script if it doesn't exist
if [ ! -f "start_integrated_mcp_server.sh" ]; then
    echo -e "${YELLOW}⚠️ start_integrated_mcp_server.sh not found. Creating it...${NC}"
    cat > "start_integrated_mcp_server.sh" << 'EOL'
#!/bin/bash
# Start the integrated final MCP server

echo "🚀 Starting Integrated MCP Server"
echo "==============================="

# Start the server
python3 final_mcp_server.py "$@"
EOL
    chmod +x "start_integrated_mcp_server.sh"
    echo -e "${GREEN}✅ Start script created.${NC}"
fi

echo -e "${GREEN}=================================${NC}"
echo -e "${GREEN}🚀 Installation Complete 🚀${NC}"
echo -e "${GREEN}=================================${NC}"
echo -e "${BLUE}To start the server, run:${NC}"
echo -e "  ./start_integrated_mcp_server.sh"
echo -e "${BLUE}To test the server, run:${NC}"
echo -e "  ./test_integrated_mcp_server.py"
echo -e "${GREEN}=================================${NC}"
