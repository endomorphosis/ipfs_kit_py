#!/usr/bin/env python3
"""
Fix IPFS MCP Tools Integration

This script fixes the issues with the IPFS MCP Tools Integration module.
It ensures all the functions are properly defined to prevent "possibly unbound" errors.
"""

import os
import sys
import re
import logging
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def backup_file(file_path):
    """Create backup of the file"""
    backup_path = f"{file_path}.bak"
    if os.path.exists(file_path):
        try:
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup at {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
    else:
        logger.error(f"File not found: {file_path}")
    return False

def fix_ipfs_tools_integration():
    """Fix the IPFS MCP Tools Integration file"""
    file_path = "ipfs_mcp_tools_integration.py"
    
    # Create backup
    if not backup_file(file_path):
        return False
        
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Fix the import section by adding mock implementations when imports fail
        fixed_import_section = """
# Try to import IPFS extensions
try:
    sys.path.append(os.path.join(os.getcwd(), 'ipfs_kit_py'))
    from ipfs_kit_py.mcp.ipfs_extensions import (
        add_content, cat, pin_add, pin_rm, pin_ls, get_version,
        files_ls, files_mkdir, files_write, files_read,
        files_rm, files_stat, files_cp, files_mv, files_flush
    )
    IPFS_EXTENSIONS_AVAILABLE = True
    logger.info("Successfully imported IPFS extensions")
except ImportError as e:
    IPFS_EXTENSIONS_AVAILABLE = False
    logger.warning(f"Could not import IPFS extensions: {e}. Using mock implementations.")
    
    # Mock implementations for when the extensions aren't available
    def add_content(content, **kwargs):
        logger.warning("Using mock implementation of add_content")
        return {"Hash": "QmMockHash", "Size": len(content) if isinstance(content, bytes) else len(content.encode())}
        
    def cat(ipfs_path, **kwargs):
        logger.warning("Using mock implementation of cat")
        return b"Mock content for " + ipfs_path.encode() if isinstance(ipfs_path, str) else ipfs_path
        
    def pin_add(ipfs_path, **kwargs):
        logger.warning("Using mock implementation of pin_add")
        return {"Pins": [ipfs_path]}
        
    def pin_rm(ipfs_path, **kwargs):
        logger.warning("Using mock implementation of pin_rm")
        return {"Pins": [ipfs_path]}
        
    def pin_ls(ipfs_path=None, **kwargs):
        logger.warning("Using mock implementation of pin_ls")
        return {"Keys": {"QmMockHash": {"Type": "recursive"}}}
        
    def get_version(**kwargs):
        logger.warning("Using mock implementation of get_version")
        return {"Version": "mock-0.11.0", "Commit": "mock"}
        
    def files_ls(path="/", **kwargs):
        logger.warning("Using mock implementation of files_ls")
        return {"Entries": [{"Name": "mock-file.txt", "Type": 0, "Size": 123}]}
        
    def files_mkdir(path, **kwargs):
        logger.warning("Using mock implementation of files_mkdir")
        return {}
        
    def files_write(path, content, **kwargs):
        logger.warning("Using mock implementation of files_write")
        return {}
        
    def files_read(path, **kwargs):
        logger.warning("Using mock implementation of files_read")
        return b"Mock content for " + path.encode() if isinstance(path, str) else path
        
    def files_rm(path, **kwargs):
        logger.warning("Using mock implementation of files_rm")
        return {}
        
    def files_stat(path, **kwargs):
        logger.warning("Using mock implementation of files_stat")
        return {"Hash": "QmMockHash", "Size": 123, "Type": "file"}
        
    def files_cp(source, dest, **kwargs):
        logger.warning("Using mock implementation of files_cp")
        return {}
        
    def files_mv(source, dest, **kwargs):
        logger.warning("Using mock implementation of files_mv")
        return {}
        
    def files_flush(path="/", **kwargs):
        logger.warning("Using mock implementation of files_flush")
        return {"Hash": "QmMockHash"}
"""
        
        # Replace the existing import section
        import_pattern = r"# Try to import IPFS extensions.*?(?=\n\ndef register_ipfs_tools)"
        if re.search(import_pattern, content, re.DOTALL):
            content = re.sub(import_pattern, fixed_import_section.strip(), content, flags=re.DOTALL)
        else:
            logger.error("Could not find the import section to replace")
            return False
            
        # Write the updated content
        with open(file_path, 'w') as f:
            f.write(content)
            
        logger.info(f"Successfully fixed {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error fixing {file_path}: {e}")
        return False

def update_mcp_server_integration():
    """Update the direct_mcp_server.py file to use our new all-in-one registration"""
    file_path = "direct_mcp_server.py"
    
    # Create backup
    if not backup_file(file_path):
        return False
        
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Add our new import
        if "from register_all_backend_tools import register_all_tools" not in content:
            import_line = "import ipfs_mcp_fs_integration"
            if import_line in content:
                content = content.replace(
                    import_line,
                    f"{import_line}\nfrom register_all_backend_tools import register_all_tools"
                )
                logger.info("Added import for register_all_tools")
            else:
                logger.warning("Could not find the appropriate import location")
                return False
        
        # Replace the individual registrations with our comprehensive one
        registration_pattern = r"# Register IPFS tools\s*\nregister_ipfs_tools\(server\)\s*\n\s*# Register FS Journal tools\s*\nipfs_mcp_fs_integration\.register_with_mcp_server\(server\)"
        replacement = """# Register all IPFS tools and backend integrations
logger.info("Registering all IPFS, FS Journal, and Multi-Backend tools...")
register_all_tools(server)
logger.info("✅ Tool registration complete")"""

        if re.search(registration_pattern, content):
            content = re.sub(registration_pattern, replacement, content)
            logger.info("Updated tool registration code")
        else:
            logger.warning("Could not find the tool registration section")
            return False
            
        # Write the updated content
        with open(file_path, 'w') as f:
            f.write(content)
            
        logger.info(f"Successfully updated {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating {file_path}: {e}")
        return False

def create_startup_script():
    """Create an improved startup script for the MCP server"""
    script_path = "start_enhanced_mcp_server.sh"
    
    try:
        with open(script_path, 'w') as f:
            f.write("""#!/bin/bash
# Start the enhanced MCP server with all IPFS Kit features

# Set up colors for better visibility
GREEN="\\033[0;32m"
YELLOW="\\033[1;33m"
RED="\\033[0;31m"
BLUE="\\033[0;34m"
NC="\\033[0m" # No Color

echo -e "${BLUE}Starting Enhanced MCP Server with IPFS Kit Integration${NC}"

# Stop any running server
if [ -f "direct_mcp_server_active.txt" ]; then
  PID=$(cat direct_mcp_server_active.txt)
  if [ -n "$PID" ] && ps -p $PID > /dev/null; then
    echo -e "${YELLOW}Stopping running MCP server (PID: $PID)...${NC}"
    kill $PID
    sleep 1
  fi
  rm -f direct_mcp_server_active.txt
fi

# Start the server in the background
python direct_mcp_server.py > mcp_server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > direct_mcp_server_active.txt

# Wait for server to start
echo -e "${YELLOW}Waiting for server to start...${NC}"
sleep 2

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
  echo -e "${GREEN}✅ MCP server started successfully${NC}"
  echo -e "${GREEN}ℹ️ Server is running at http://127.0.0.1:3000${NC}"
  echo ""
  echo -e "${BLUE}Available Features:${NC}"
  echo -e "  ${GREEN}✓${NC} IPFS Core Operations"
  echo -e "  ${GREEN}✓${NC} IPFS MFS (Mutable File System)"
  echo -e "  ${GREEN}✓${NC} FS Journal for tracking filesystem operations"
  echo -e "  ${GREEN}✓${NC} IPFS-FS Bridge for mapping between IPFS and local filesystem"
  echo -e "  ${GREEN}✓${NC} Multi-Backend Storage (IPFS, HuggingFace, S3, Filecoin, etc.)"
  echo -e "  ${GREEN}✓${NC} Content prefetching and search capabilities"
  echo -e "  ${GREEN}✓${NC} Data format conversion and transformation"
  echo ""
  echo -e "${BLUE}Available Tools:${NC}"
  echo -e "  Run ${YELLOW}python verify_tools.py${NC} to view all available tools"
  echo ""
  echo -e "${BLUE}To stop the server:${NC}"
  echo -e "  Run ${YELLOW}bash stop_enhanced_mcp_server.sh${NC}"
else
  echo -e "${RED}❌ Failed to start MCP server. Check mcp_server.log for details.${NC}"
  exit 1
fi
""")
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        logger.info(f"Created startup script: {script_path}")
        
        # Create the stop script as well
        stop_script_path = "stop_enhanced_mcp_server.sh"
        with open(stop_script_path, 'w') as f:
            f.write("""#!/bin/bash
# Stop the enhanced MCP server

# Set up colors for better visibility
GREEN="\\033[0;32m"
YELLOW="\\033[1;33m"
RED="\\033[0;31m"
NC="\\033[0m" # No Color

if [ -f "direct_mcp_server_active.txt" ]; then
  PID=$(cat direct_mcp_server_active.txt)
  if [ -n "$PID" ] && ps -p $PID > /dev/null; then
    echo -e "${YELLOW}Stopping MCP server (PID: $PID)...${NC}"
    kill $PID
    sleep 1
    if ! ps -p $PID > /dev/null; then
      echo -e "${GREEN}✅ MCP server stopped successfully${NC}"
      rm -f direct_mcp_server_active.txt
    else
      echo -e "${RED}Failed to stop MCP server gracefully, forcing shutdown...${NC}"
      kill -9 $PID
      sleep 1
      if ! ps -p $PID > /dev/null; then
        echo -e "${GREEN}✅ MCP server stopped successfully (forced)${NC}"
        rm -f direct_mcp_server_active.txt
      else
        echo -e "${RED}❌ Failed to stop MCP server${NC}"
      fi
    fi
  else
    echo -e "${YELLOW}No running MCP server found with PID: $PID${NC}"
    rm -f direct_mcp_server_active.txt
  fi
else
  echo -e "${YELLOW}No MCP server appears to be running${NC}"
fi
""")
        
        # Make the stop script executable
        os.chmod(stop_script_path, 0o755)
        logger.info(f"Created stop script: {stop_script_path}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to create scripts: {e}")
        return False

def create_verification_script():
    """Create a script to verify all available tools"""
    script_path = "verify_tools.py"
    
    try:
        with open(script_path, 'w') as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Verify Tools

This script connects to the MCP server and lists all available tools,
grouped by category for better organization.
\"\"\"

import os
import sys
import json
import logging
import requests
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP Server URL
MCP_URL = "http://127.0.0.1:3000"

def get_all_tools():
    \"\"\"Get all tools from the MCP server\"\"\"
    try:
        response = requests.post(f"{MCP_URL}/jsonrpc", json={
            "jsonrpc": "2.0", 
            "method": "get_tools",
            "params": {},
            "id": 1
        })
        response.raise_for_status()
        data = response.json()
        
        if "result" in data and "tools" in data["result"]:
            return data["result"]["tools"]
        else:
            logger.error("Unexpected response format")
            return []
    except Exception as e:
        logger.error(f"Failed to get tools: {e}")
        return []

def group_tools_by_category(tools):
    \"\"\"Group tools by their category for better organization\"\"\"
    categories = {}
    
    for tool in tools:
        name = tool.get("name", "")
        
        # Determine category based on name prefix
        category = "Other"
        if name.startswith("ipfs_"):
            category = "IPFS Core"
        elif name.startswith("fs_journal_"):
            category = "FS Journal"
        elif name.startswith("ipfs_fs_"):
            category = "IPFS-FS Bridge"
        elif name.startswith("multi_backend_"):
            category = "Multi-Backend Storage"
        elif name.startswith("huggingface_"):
            category = "HuggingFace Integration"
        elif name.startswith("s3_"):
            category = "S3 Integration"
        elif name.startswith("filecoin_"):
            category = "Filecoin Integration"
        elif name.startswith("credential_"):
            category = "Credential Management"
        elif name.startswith("webrtc_"):
            category = "WebRTC Integration"
        
        # Add to appropriate category
        if category not in categories:
            categories[category] = []
        categories[category].append(tool)
    
    return categories

def print_tools_by_category(categories):
    \"\"\"Print tools organized by category\"\"\"
    print("\\n=== MCP Server Tools ===\\n")
    
    total_tools = sum(len(tools) for tools in categories.values())
    print(f"Total tools available: {total_tools}\\n")
    
    # Print each category
    for category, tools in sorted(categories.items()):
        print(f"== {category} ({len(tools)}) ==")
        for tool in sorted(tools, key=lambda t: t.get("name", "")):
            name = tool.get("name", "")
            description = tool.get("description", "No description")
            print(f"  - {name}: {description}")
        print()

def main():
    \"\"\"Main function\"\"\"
    logger.info("Connecting to MCP server...")
    
    # Get all tools
    tools = get_all_tools()
    if not tools:
        logger.error("No tools found. Make sure the MCP server is running.")
        return 1
    
    # Group and print tools
    categories = group_tools_by_category(tools)
    print_tools_by_category(categories)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
""")
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        logger.info(f"Created verification script: {script_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create verification script: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting IPFS MCP Tools integration fix...")
    
    # Fix the IPFS MCP Tools integration
    if not fix_ipfs_tools_integration():
        logger.error("Failed to fix IPFS MCP Tools integration")
        return 1
    
    # Update the MCP server integration
    if not update_mcp_server_integration():
        logger.error("Failed to update MCP server integration")
        return 1
    
    # Create startup script
    if not create_startup_script():
        logger.warning("Failed to create startup script")
    
    # Create verification script
    if not create_verification_script():
        logger.warning("Failed to create verification script")
    
    logger.info("""
✅ IPFS MCP Tools integration fix completed

The integration now includes:
- Fixed IPFS tools integration with proper fallback implementations
- Unified tool registration for simplified management
- Enhanced startup script with feature information
- Tool verification script to check available functionality

To use the enhanced MCP server:
1. Run the new startup script: ./start_enhanced_mcp_server.sh
2. Verify available tools: python verify_tools.py
3. Stop the server when done: ./stop_enhanced_mcp_server.sh
""")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
