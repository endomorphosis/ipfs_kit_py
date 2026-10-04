#!/usr/bin/env python3
"""
Verify IPFS Tools Script

This script verifies that the environment is properly set up for IPFS MCP tools,
including checking for the IPFS daemon, required Python packages, and the MCP server.
"""

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
    """Check if IPFS daemon is running"""
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
    """Check if a Python module is installed"""
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
    """Check if a file exists"""
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
    """Main verification function"""
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
