#!/usr/bin/env python3
"""
Integrate All Tools with MCP Server

This script ensures all tools are properly registered with the MCP server.
It targets direct_mcp_server_with_tools.py since it seems to be the most
stable and functional version.
"""

import os
import sys
import re
import shutil
import logging
import importlib
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("integrate_all_mcp_tools.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("integrate-tools")

# Paths
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
SERVER_PATH = BASE_DIR / "direct_mcp_server_with_tools.py"
BACKUP_PATH = SERVER_PATH.with_suffix(".py.bak.integration")

# Tool Registries
TOOLS_TO_INTEGRATE = [
    {
        "name": "IPFS Tools",
        "module": "ipfs_mcp_tools_integration",
        "function": "register_ipfs_tools",
        "import_line": "from ipfs_mcp_tools_integration import register_ipfs_tools"
    },
    {
        "name": "VFS Tools",
        "module": "enhance_vfs_mcp_integration",
        "function": "register_all_fs_tools",
        "import_line": "from enhance_vfs_mcp_integration import register_all_fs_tools"
    },
    {
        "name": "FS Journal Tools",
        "module": "fs_journal_tools",
        "function": "register_fs_journal_tools",
        "import_line": "from fs_journal_tools import register_fs_journal_tools" 
    },
    {
        "name": "Multi-Backend Tools",
        "module": "register_all_backend_tools",
        "function": "register_all_tools",
        "import_line": "from register_all_backend_tools import register_all_tools"
    },
    {
        "name": "IPFS-FS Bridge Tools",
        "module": "ipfs_mcp_fs_integration",
        "function": "register_integration_tools",
        "import_line": "from ipfs_mcp_fs_integration import register_integration_tools"
    }
]

def backup_server():
    """Create backup of server file"""
    logger.info(f"Backing up {SERVER_PATH} to {BACKUP_PATH}")
    shutil.copy2(SERVER_PATH, BACKUP_PATH)
    logger.info("Backup created")
    
def restore_backup():
    """Restore backup if available"""
    if BACKUP_PATH.exists():
        logger.info(f"Restoring backup from {BACKUP_PATH}")
        shutil.copy2(BACKUP_PATH, SERVER_PATH)
        logger.info("Backup restored")
        return True
    else:
        logger.error("No backup file found")
        return False

def check_module_exists(module_name):
    """Check if a module exists"""
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ImportError, ValueError):
        return False

def update_server_file():
    """Update server file with proper tool registrations"""
    # Read server file
    with open(SERVER_PATH, 'r') as f:
        content = f.read()
    
    # Insert imports if needed
    import_section_end = None
    lines = content.split('\n')
    
    # Find import section end
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            import_section_end = i
    
    if import_section_end is None:
        logger.error("Could not find import section")
        return False
    
    # Add missing imports
    imports_added = []
    for tool in TOOLS_TO_INTEGRATE:
        if tool["import_line"] not in content and check_module_exists(tool["module"]):
            lines.insert(import_section_end + 1, tool["import_line"])
            import_section_end += 1
            imports_added.append(tool["name"])
            logger.info(f"Added import for {tool['name']}")
    
    # Find tool registration section
    for i, line in enumerate(lines):
        if "# Register all IPFS tools and backend integrations" in line or "Registering all IPFS" in line:
            registration_section = i
            break
    else:
        # If not found, look for the server initialization
        for i, line in enumerate(lines):
            if "server = FastMCP(" in line:
                # Add registration section after server initialization
                registration_section = i + 1
                lines.insert(registration_section, "\n# Register all IPFS tools and backend integrations")
                registration_section += 1
                break
        else:
            logger.error("Could not find server initialization or registration section")
            return False
    
    # Add tool registrations
    registrations_added = []
    for tool in TOOLS_TO_INTEGRATE:
        function_call = f"{tool['function']}(server)"
        if function_call not in content and check_module_exists(tool["module"]):
            lines.insert(registration_section + 1, f"    {function_call}")
            registration_section += 1
            registrations_added.append(tool["name"])
            logger.info(f"Added registration for {tool['name']}")
    
    # Write updated content
    if imports_added or registrations_added:
        with open(SERVER_PATH, 'w') as f:
            f.write('\n'.join(lines))
        logger.info(f"Updated server file with {len(imports_added)} imports and {len(registrations_added)} tool registrations")
        return True
    else:
        logger.info("No changes needed to server file")
        return True

def create_full_startup_script():
    """Create a full startup script that ensures all tools are registered"""
    script_path = os.path.join(BASE_DIR, "start_full_mcp_server.sh")
    logger.info(f"Creating startup script at {script_path}")
    
    script_content = """#!/bin/bash
# Start Full MCP Server with All Tools
set -e

echo "Starting Full MCP Server with all tools..."

# Change to script directory
cd "$(dirname "$0")"

# Clean up any existing servers
pkill -f "python.*direct_mcp_server" || echo "No running servers"
echo "Cleared previous logs..." > direct_mcp_server.log

# Check if IPFS daemon is running
echo "Checking IPFS daemon status..."
if ! pgrep -x "ipfs" > /dev/null; then
    echo "IPFS daemon not running, starting it..."
    ipfs daemon --init &
    # Wait a bit for IPFS to start
    sleep 3
else
    echo "IPFS daemon is already running."
fi

echo "Cleaning up any existing MCP server processes..."
if [ -f direct_mcp_server.pid ]; then
    pid=$(cat direct_mcp_server.pid 2>/dev/null || echo "")
    if [ -n "$pid" ] && ps -p $pid > /dev/null 2>&1; then
        kill $pid
        sleep 2
    fi
fi

# Set environment variables
echo "Setting up Python environment..."
export PYTHONPATH="$PYTHONPATH:$(pwd):$(pwd)/docs/mcp-python-sdk/src"

# Run the enhancer first to ensure all tools are integrated
echo "Starting enhanced MCP server with compatibility fixes..."
python3 integrate_all_mcp_tools.py --fix-server

# Start the server
echo "Starting direct_mcp_server_with_tools.py..."
nohup python3 direct_mcp_server_with_tools.py --port 3000 > direct_mcp_server.log 2>&1 &
echo $! > direct_mcp_server.pid
echo "Server started with PID: $(cat direct_mcp_server.pid)"

# Wait a moment for server to initialize
echo "Waiting for server initialization..."
sleep 5

# Check if running
if ps -p $(cat direct_mcp_server.pid) > /dev/null; then
    echo "✅ Server started successfully!"
    
    # Check tool count
    echo "Checking available tools..."
    python3 check_mcp_tools.py
    
    echo -e "\nServer is running at http://localhost:3000/"
    echo "Health check: http://localhost:3000/health"
    echo "To stop: kill $(cat direct_mcp_server.pid)"
else
    echo "❌ Server process stopped unexpectedly."
    echo "Last 20 lines of output:"
    tail -20 direct_mcp_server.log
    exit 1
fi
"""
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_path, 0o755)
    logger.info(f"Created startup script at {script_path} and made it executable")
    
    return True

def fix_server():
    """Fix server to ensure proper tool registration"""
    logger.info("Starting server fix process")
    
    # First create backup
    backup_server()
    
    # Update server file
    if not update_server_file():
        logger.error("Failed to update server file")
        restore_backup()
        return False
    
    # Create startup script
    if not create_full_startup_script():
        logger.error("Failed to create startup script")
        restore_backup()
        return False
    
    logger.info("Server fix completed successfully!")
    return True

if __name__ == "__main__":
    # Simple command line processing
    if len(sys.argv) > 1 and sys.argv[1] == "--fix-server":
        fix_server()
    elif len(sys.argv) > 1 and sys.argv[1] == "--restore-backup":
        restore_backup()
    else:
        print("Usage: integrate_all_mcp_tools.py [--fix-server|--restore-backup]")
        print("  --fix-server     Fix the server file to register all tools")
        print("  --restore-backup Restore the backup version of the server file")
