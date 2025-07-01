#!/usr/bin/env python3
"""
Patch Direct MCP Server Script

This script patches the direct_mcp_server.py file to integrate IPFS MCP tools,
filesystem journal tools, and multi-backend storage integration. It ensures that
all tools work seamlessly with the virtual filesystem features.
"""

import os
import sys
import re
import shutil
import logging
import importlib.util
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
DIRECT_MCP_SERVER = "direct_mcp_server.py"
BACKUP_EXT = ".backup"

def backup_file(filepath):
    """Create a backup of a file before modifying it"""
    backup_path = f"{filepath}{BACKUP_EXT}"
    
    # Check if backup already exists
    if os.path.exists(backup_path):
        logger.info(f"Backup already exists: {backup_path}")
        return
    
    # Create backup
    shutil.copy2(filepath, backup_path)
    logger.info(f"Backup created: {backup_path}")

def restore_from_backup(filepath):
    """Restore a file from its backup"""
    backup_path = f"{filepath}{BACKUP_EXT}"
    
    # Check if backup exists
    if not os.path.exists(backup_path):
        logger.error(f"No backup found: {backup_path}")
        return False
    
    # Restore backup
    shutil.copy2(backup_path, filepath)
    logger.info(f"Restored from backup: {filepath}")
    return True

def check_dependency(module_name):
    """Check if a module is installed"""
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except ImportError:
        return False

def patch_imports(content):
    """Add necessary imports to the MCP server"""
    # Check if imports already exist
    if "import ipfs_mcp_tools" in content:
        logger.info("IPFS MCP tools import already exists")
        return content
    
    # Add imports after the last import line
    import_pattern = r'(^import.*$|^from.*$)'
    matches = list(re.finditer(import_pattern, content, re.MULTILINE))
    
    if not matches:
        logger.error("No import statements found in file")
        return content
    
    last_import = matches[-1]
    last_import_pos = last_import.end()
    
    new_imports = '\n\n# IPFS and filesystem integration\ntry:\n'
    new_imports += '    import ipfs_mcp_tools\n'
    new_imports += '    import fs_journal_tools\n'
    new_imports += '    import multi_backend_fs_integration\n'
    new_imports += '    HAS_IPFS_TOOLS = True\n'
    new_imports += 'except ImportError as e:\n'
    new_imports += '    logger.warning(f"Could not import IPFS tools: {e}")\n'
    new_imports += '    HAS_IPFS_TOOLS = False\n'
    
    patched_content = content[:last_import_pos] + new_imports + content[last_import_pos:]
    return patched_content

def patch_register_tools(content):
    """Patch the server to register IPFS and filesystem tools"""
    # Check if tools registration already exists
    if "ipfs_mcp_tools.register_tools" in content:
        logger.info("IPFS MCP tools registration already exists")
        return content
    
    # Find server initialization
    server_init_pattern = r'def\s+start_server\s*\([^)]*\)\s*:'
    matches = list(re.finditer(server_init_pattern, content, re.MULTILINE))
    
    if not matches:
        logger.error("Could not find server initialization method")
        return content
    
    server_init = matches[0]
    
    # Find the server creation line
    server_creation_pattern = r'(\s+)(server\s*=\s*[^#\n]+)'
    creation_matches = list(re.finditer(server_creation_pattern, content[server_init.end():], re.MULTILINE))
    
    if not creation_matches:
        logger.error("Could not find server creation line")
        return content
    
    # Get indentation level
    indent = creation_matches[0].group(1)
    
    # Find position to insert registration code (after server creation)
    server_creation_pos = server_init.end() + creation_matches[0].end()
    
    # Create registration code
    registration_code = f'\n{indent}# Register IPFS and filesystem tools\n'
    registration_code += f'{indent}if HAS_IPFS_TOOLS:\n'
    registration_code += f'{indent}    logger.info("Registering IPFS and filesystem tools...")\n'
    registration_code += f'{indent}    try:\n'
    registration_code += f'{indent}        # Register tools\n'
    registration_code += f'{indent}        ipfs_mcp_tools.register_tools(server)\n'
    registration_code += f'{indent}        fs_journal_tools.register_tools(server)\n'
    registration_code += f'{indent}        multi_backend_fs_integration.register_tools(server)\n'
    registration_code += f'{indent}        logger.info("✅ IPFS and filesystem tools registered successfully")\n'
    registration_code += f'{indent}    except Exception as e:\n'
    registration_code += f'{indent}        logger.error(f"Error registering IPFS tools: {{e}}")\n'
    
    patched_content = content[:server_creation_pos] + registration_code + content[server_creation_pos:]
    return patched_content

def patch_shutdown(content):
    """Patch the server to cleanly shut down IPFS connections"""
    # Check if shutdown code already exists
    if "shutdown IPFS connections" in content:
        logger.info("IPFS shutdown code already exists")
        return content
    
    # Find server shutdown method
    shutdown_pattern = r'def\s+stop_server\s*\([^)]*\)\s*:'
    matches = list(re.finditer(shutdown_pattern, content, re.MULTILINE))
    
    if not matches:
        # If no specific shutdown method, add to main block
        shutdown_pattern = r'if\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:'
        matches = list(re.finditer(shutdown_pattern, content, re.MULTILINE))
        
        if not matches:
            logger.error("Could not find a place to add shutdown code")
            return content
    
    shutdown_match = matches[0]
    
    # Find a good place to insert shutdown code
    server_stop_pattern = r'(\s+)(server\.stop\(\))'
    stop_matches = list(re.finditer(server_stop_pattern, content[shutdown_match.end():], re.MULTILINE))
    
    insertion_pos = None
    indent = "    "
    
    if stop_matches:
        # Insert after server.stop()
        insertion_pos = shutdown_match.end() + stop_matches[0].end()
        indent = stop_matches[0].group(1)
    else:
        # Insert at the end of the function body
        func_body_pattern = r'def\s+stop_server[^:]*:(.+?)(?=\n\S|\Z)'
        body_match = re.search(func_body_pattern, content[shutdown_match.start():], re.DOTALL)
        
        if body_match:
            insertion_pos = shutdown_match.start() + body_match.end()
            # Extract indentation from the function body
            indent_match = re.search(r'(\s+)\S', body_match.group(1))
            if indent_match:
                indent = indent_match.group(1)
        else:
            # Default position at the end of function declaration
            insertion_pos = shutdown_match.end()
    
    if insertion_pos is None:
        logger.error("Could not determine where to insert shutdown code")
        return content
    
    # Create shutdown code
    shutdown_code = f'\n{indent}# Clean up IPFS connections\n'
    shutdown_code += f'{indent}if "HAS_IPFS_TOOLS" in globals() and HAS_IPFS_TOOLS:\n'
    shutdown_code += f'{indent}    logger.info("Shutting down IPFS connections...")\n'
    shutdown_code += f'{indent}    try:\n'
    shutdown_code += f'{indent}        # Any cleanup needed for IPFS connections\n'
    shutdown_code += f'{indent}        pass\n'
    shutdown_code += f'{indent}    except Exception as e:\n'
    shutdown_code += f'{indent}        logger.error(f"Error shutting down IPFS connections: {{e}}")\n'
    
    patched_content = content[:insertion_pos] + shutdown_code + content[insertion_pos:]
    return patched_content

def patch_server():
    """Patch the MCP server to integrate IPFS and filesystem tools"""
    # Check if direct MCP server exists
    if not os.path.exists(DIRECT_MCP_SERVER):
        logger.error(f"Could not find {DIRECT_MCP_SERVER}")
        return False
    
    # Create backup
    backup_file(DIRECT_MCP_SERVER)
    
    # Read file
    with open(DIRECT_MCP_SERVER, 'r') as f:
        content = f.read()
    
    # Apply patches
    patched_content = patch_imports(content)
    patched_content = patch_register_tools(patched_content)
    patched_content = patch_shutdown(patched_content)
    
    # Write patched file
    with open(DIRECT_MCP_SERVER, 'w') as f:
        f.write(patched_content)
    
    logger.info(f"Successfully patched {DIRECT_MCP_SERVER}")
    return True

def create_startup_script():
    """Create a script to start the MCP server with IPFS tools"""
    script_path = "start_ipfs_mcp_with_tools.sh"
    
    script_content = """#!/bin/bash
# Start MCP server with IPFS tools
# This script starts the MCP server with IPFS and filesystem tools

# Check if IPFS daemon is running
if ! ipfs id > /dev/null 2>&1; then
    echo "Warning: IPFS daemon not running. Starting IPFS daemon..."
    ipfs daemon &
    # Wait for daemon to start
    sleep 5
fi

# Start MCP server
echo "Starting MCP server with IPFS tools..."
python3 direct_mcp_server.py
"""
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_path, 0o755)
    logger.info(f"Created startup script: {script_path}")
    
    # Create stop script
    stop_script_path = "stop_ipfs_mcp.sh"
    
    stop_script_content = """#!/bin/bash
# Stop MCP server and optionally IPFS daemon
# This script stops the MCP server and optionally the IPFS daemon

# Stop MCP server
echo "Stopping MCP server..."
pkill -f "python3 direct_mcp_server.py"

# Ask if IPFS daemon should be stopped
read -p "Do you want to stop the IPFS daemon too? (y/n): " stop_ipfs

if [[ $stop_ipfs == "y" || $stop_ipfs == "Y" ]]; then
    echo "Stopping IPFS daemon..."
    ipfs shutdown
fi

echo "Done."
"""
    
    with open(stop_script_path, 'w') as f:
        f.write(stop_script_content)
    
    # Make executable
    os.chmod(stop_script_path, 0o755)
    logger.info(f"Created stop script: {stop_script_path}")
    
    return True

def create_verification_script():
    """Create a script to verify the environment and dependencies"""
    script_path = "verify_ipfs_tools.py"
    
    script_content = """#!/usr/bin/env python3
\"\"\"
Verify IPFS Tools Script

This script verifies that the environment is properly set up for IPFS MCP tools,
including checking for the IPFS daemon, required Python packages, and the MCP server.
\"\"\"

import os
import sys
import subprocess
import importlib.util
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_ipfs_daemon():
    \"\"\"Check if IPFS daemon is running\"\"\"
    try:
        result = subprocess.run(["ipfs", "id"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✅ IPFS daemon is running")
            return True
        else:
            logger.error("❌ IPFS daemon is not running")
            logger.info("Start the IPFS daemon with: ipfs daemon")
            return False
    except FileNotFoundError:
        logger.error("❌ IPFS command not found. Is IPFS installed?")
        logger.info("Install IPFS from: https://docs.ipfs.tech/install/")
        return False

def check_python_module(module_name):
    \"\"\"Check if a Python module is installed\"\"\"
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is not None:
            logger.info(f"✅ Python module {module_name} is installed")
            return True
        else:
            logger.error(f"❌ Python module {module_name} is not installed")
            return False
    except ImportError:
        logger.error(f"❌ Python module {module_name} is not installed")
        return False

def check_file_exists(filepath, required=True):
    \"\"\"Check if a file exists\"\"\"
    if os.path.exists(filepath):
        logger.info(f"✅ File exists: {filepath}")
        return True
    else:
        if required:
            logger.error(f"❌ Required file not found: {filepath}")
        else:
            logger.warning(f"⚠️ Optional file not found: {filepath}")
        return False

def main():
    \"\"\"Main verification function\"\"\"
    success = True
    
    # Check IPFS daemon
    if not check_ipfs_daemon():
        success = False
    
    # Check Python modules
    modules = [
        "sqlite3",
        "hashlib",
    ]
    
    optional_modules = [
        "ipfshttpclient",
        "boto3",
    ]
    
    for module in modules:
        if not check_python_module(module):
            success = False
    
    for module in optional_modules:
        check_python_module(module)
    
    # Check required files
    required_files = [
        "direct_mcp_server.py",
        "ipfs_mcp_tools.py",
        "fs_journal_tools.py",
        "multi_backend_fs_integration.py",
    ]
    
    optional_files = [
        "start_ipfs_mcp_with_tools.sh",
        "stop_ipfs_mcp.sh",
    ]
    
    for filepath in required_files:
        if not check_file_exists(filepath):
            success = False
    
    for filepath in optional_files:
        check_file_exists(filepath, required=False)
    
    # Final result
    if success:
        logger.info("✅ All required components are available")
        logger.info("You can now start the MCP server with IPFS tools")
        logger.info("Run: ./start_ipfs_mcp_with_tools.sh")
    else:
        logger.error("❌ Some required components are missing")
        logger.error("Please address the issues above before starting the server")
    
    return success

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
"""
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_path, 0o755)
    logger.info(f"Created verification script: {script_path}")
    
    return True

def main():
    """Main function"""
    # Check if IPFS tools are present
    required_files = [
        "ipfs_mcp_tools.py",
        "fs_journal_tools.py",
        "multi_backend_fs_integration.py",
    ]
    
    for filepath in required_files:
        if not os.path.exists(filepath):
            logger.error(f"Required file not found: {filepath}")
            return 1
    
    # Patch server
    if not patch_server():
        return 1
    
    # Create startup script
    create_startup_script()
    
    # Create verification script
    create_verification_script()
    
    logger.info("\n=== Installation Complete ===\n")
    logger.info("To verify your environment:")
    logger.info("  python3 verify_ipfs_tools.py")
    logger.info("\nTo start the MCP server with IPFS tools:")
    logger.info("  ./start_ipfs_mcp_with_tools.sh")
    logger.info("\nTo stop the MCP server:")
    logger.info("  ./stop_ipfs_mcp.sh")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
