#!/usr/bin/env python3
"""
Integrate All IPFS Tools Script

This script runs all the necessary components to integrate IPFS tools,
filesystem journal, and multi-backend storage with the MCP server and
virtual filesystem features.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

import register_all_controller_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_command(command, description=None):
    """Run a command and log output"""
    if description:
        logger.info(f"{description}...")
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stdout.strip():
            logger.info(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        if e.stdout:
            logger.error(f"Output: {e.stdout}")
        if e.stderr:
            logger.error(f"Error: {e.stderr}")
        return False

def make_executable(filepath):
    """Make a file executable"""
    try:
        os.chmod(filepath, 0o755)
        logger.info(f"Made {filepath} executable")
        return True
    except Exception as e:
        logger.error(f"Failed to make {filepath} executable: {e}")
        return False

def check_file_exists(filepath, required=True):
    """Check if a file exists"""
    if os.path.exists(filepath):
        logger.info(f"File exists: {filepath}")
        return True
    else:
        if required:
            logger.error(f"Required file not found: {filepath}")
        else:
            logger.warning(f"Optional file not found: {filepath}")
        return False

def main():
    """Main integration function"""
    # Check for required files
    required_files = [
        "ipfs_mcp_tools.py",
        "fs_journal_tools.py",
        "multi_backend_fs_integration.py",
        "direct_mcp_server.py",
        "patch_direct_mcp_server.py"
    ]
    
    for filepath in required_files:
        if not check_file_exists(filepath):
            return 1
    
    # Make Python scripts executable
    python_scripts = [
        "ipfs_mcp_tools.py",
        "fs_journal_tools.py",
        "multi_backend_fs_integration.py",
        "patch_direct_mcp_server.py"
    ]
    
    for script in python_scripts:
        make_executable(script)
    
    # Run the patch script
    # Register all controller tools
    logger.info("Registering all controller tools...")
    register_all_controller_tools.main()
    
    logger.info("Running patch script...")
    if not run_command(["python3", "patch_direct_mcp_server.py"]):
        return 1
    
    # Make shell scripts executable
    shell_scripts = [
        "start_ipfs_mcp_with_tools.sh",
        "stop_ipfs_mcp.sh",
        "verify_ipfs_tools.py"
    ]
    
    for script in shell_scripts:
        make_executable(script)
    
    # Run verification
    logger.info("Running verification...")
    if not run_command(["python3", "verify_ipfs_tools.py"]):
        logger.warning("Verification found issues. Please check the output.")
    
    logger.info("\n========== INTEGRATION COMPLETE ==========\n")
    logger.info("All IPFS tools have been integrated with the MCP server and virtual filesystem features.")
    logger.info("\nTo start the MCP server with IPFS tools:")
    logger.info("  ./start_ipfs_mcp_with_tools.sh")
    logger.info("\nTo stop the MCP server:")
    logger.info("  ./stop_ipfs_mcp.sh")
    logger.info("\nFor more information, see:")
    logger.info("  README_IPFS_COMPREHENSIVE_TOOLS.md")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
