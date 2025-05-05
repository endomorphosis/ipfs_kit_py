#!/bin/bash
# IPFS Kit Virtual Filesystem Integration Installer
# This script installs and configures the IPFS Kit VFS integration for MCP

echo "======================================================="
echo "  IPFS Kit Virtual Filesystem Integration Installer"
echo "======================================================="

# Check if we have sudo access if needed
if [ "$EUID" -ne 0 ] && ! sudo -v &> /dev/null; then
  echo "Some operations may require sudo access, but sudo is not available."
  echo "Continuing with limited functionality..."
fi

# Create installation directory if needed
INSTALL_DIR=$(pwd)
CONFIG_DIR="$HOME/.ipfs_kit"

echo "Creating config directory: $CONFIG_DIR"
mkdir -p "$CONFIG_DIR"

# Install dependencies
echo "Installing required dependencies..."
pip install asyncio aiohttp requests boto3 aioipfs

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
if [[ $(echo "$PYTHON_VERSION" | cut -d'.' -f1) -lt 3 || ($(echo "$PYTHON_VERSION" | cut -d'.' -f1) -eq 3 && $(echo "$PYTHON_VERSION" | cut -d'.' -f2) -lt 7) ]]; then
  echo "Warning: Python version $PYTHON_VERSION detected. Python 3.7+ is recommended."
fi

# Check for IPFS daemon
echo "Checking for IPFS daemon..."
if ! command -v ipfs &> /dev/null; then
  echo "Warning: IPFS not found. Some virtual filesystem features may be limited."
  
  # Offer to install IPFS
  read -p "Would you like to install IPFS? (y/n): " install_ipfs
  if [[ $install_ipfs == "y" || $install_ipfs == "Y" ]]; then
    echo "Installing IPFS..."
    
    # Try to install IPFS using package manager
    if command -v apt &> /dev/null; then
      sudo apt update
      sudo apt install -y golang-go
      go get -u github.com/ipfs/go-ipfs/cmd/ipfs
    elif command -v brew &> /dev/null; then
      brew install ipfs
    else
      echo "Could not install IPFS automatically. Please install it manually."
      echo "Visit https://docs.ipfs.tech/install/ipfs-desktop/"
    fi
  fi
fi

# Create necessary script files
echo "Setting up virtual filesystem integration scripts..."

# Run the integration update script
echo "Updating MCP server with virtual filesystem tools..."
python update_mcp_with_vfs_tools.py --all

# Make auxiliary scripts executable
chmod +x install_vfs_dependencies.sh
chmod +x restart_mcp_with_vfs.sh
chmod +x ipfs_vfs_integration_test.py

# Create MCP Server Monitoring Script
echo "Creating MCP server monitoring script..."

cat > mcp_vfs_monitor.sh << 'EOL'
#!/bin/bash
# Monitor MCP server with VFS integration

echo "Monitoring MCP Server with Virtual Filesystem Integration"
echo "Press Ctrl+C to exit"

check_server() {
  curl -s http://localhost:3000/health > /dev/null
  return $?
}

while true; do
  if check_server; then
    echo "[$(date +"%H:%M:%S")] MCP server is running"
  else
    echo "[$(date +"%H:%M:%S")] MCP server is down! Restarting..."
    ./restart_mcp_with_vfs.sh
    sleep 5
  fi
  
  sleep 30
done
EOL

chmod +x mcp_vfs_monitor.sh

echo "======================================================="
echo "Installation complete!"
echo "======================================================="
echo 
echo "To start the enhanced MCP server:"
echo "  ./restart_mcp_with_vfs.sh"
echo 
echo "To test the integration:"
echo "  python ipfs_vfs_integration_test.py"
echo
echo "To monitor the MCP server:"
echo "  ./mcp_vfs_monitor.sh"
echo
echo "For more information, see README_VFS_MCP_INTEGRATION.md"
echo "======================================================="
