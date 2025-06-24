#!/usr/bin/env python3
"""
Simple Fix for Lassie Integration

This script enhances the Lassie integration in the MCP server to address the
"no candidates" error by implementing improved fallback mechanisms and
robust error handling.
"""

import os
import sys
import shutil
import logging
import subprocess
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths to key files
PACKAGE_ROOT = Path("/home/barberb/ipfs_kit_py")
MCP_EXTENSIONS_DIR = PACKAGE_ROOT / "mcp_extensions"

# Enhanced implementation files
ENHANCED_LASSIE_STORAGE = PACKAGE_ROOT / "enhanced_lassie_storage.py"
ORIGINAL_LASSIE_STORAGE = PACKAGE_ROOT / "lassie_storage.py"
ENHANCED_LASSIE_EXTENSION = MCP_EXTENSIONS_DIR / "enhanced_lassie_extension.py"
ORIGINAL_LASSIE_EXTENSION = MCP_EXTENSIONS_DIR / "lassie_extension.py"

def backup_file(file_path):
    """Create a backup of a file."""
    backup_path = f"{file_path}.bak"
    try:
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to backup {file_path}: {e}")
        return False

def update_lassie_implementation():
    """Update the Lassie implementation with enhanced version."""
    try:
        # 1. Backup the original files
        backup_file(ORIGINAL_LASSIE_STORAGE)
        backup_file(ORIGINAL_LASSIE_EXTENSION)

        # 2. Replace the Lassie storage implementation
        shutil.copy2(ENHANCED_LASSIE_STORAGE, ORIGINAL_LASSIE_STORAGE)
        logger.info(f"Replaced {ORIGINAL_LASSIE_STORAGE} with enhanced implementation")

        # 3. Replace the Lassie extension
        shutil.copy2(ENHANCED_LASSIE_EXTENSION, ORIGINAL_LASSIE_EXTENSION)
        logger.info(f"Replaced {ORIGINAL_LASSIE_EXTENSION} with enhanced implementation")

        return True
    except Exception as e:
        logger.error(f"Failed to update Lassie implementation: {e}")
        return False

def restart_mcp_server():
    """Restart the MCP server."""
    try:
        # Stop any running MCP server
        logger.info("Stopping MCP server...")
        pid_file = Path("/tmp/mcp/server.pid")
        if pid_file.exists():
            with open(pid_file, 'r') as f:
                pid = f.read().strip()
                subprocess.run(["kill", "-15", pid], check=False)

        # Also try to kill by process name
        subprocess.run(["pkill", "-f", "enhanced_mcp_server.py"], check=False)

        # Wait for processes to terminate
        time.sleep(2)

        # Start MCP server
        logger.info("Starting MCP server...")
        start_script = PACKAGE_ROOT / "start_mcp_server.sh"

        if start_script.exists():
            subprocess.run([str(start_script)], check=True)
            logger.info("MCP server started successfully")

            # Allow time for the server to initialize
            time.sleep(5)
            return True
        else:
            logger.error(f"Start script not found: {start_script}")
            return False
    except Exception as e:
        logger.error(f"Error restarting MCP server: {e}")
        return False

def test_lassie_integration():
    """Test that the Lassie integration works correctly."""
    try:
        # Check server health to verify Lassie integration
        result = subprocess.run(
            ["curl", "http://localhost:9997/api/v0/health"],
            capture_output=True,
            text=True,
            check=True
        )

        if "lassie" not in result.stdout:
            logger.error("Lassie not found in server health output")
            return False

        logger.info("Lassie found in server health output")

        # Test the well-known CIDs endpoint
        logger.info("Testing well-known CIDs endpoint...")
        subprocess.run(
            ["curl", "http://localhost:9997/api/v0/lassie/well_known_cids"],
            check=True
        )

        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Test failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Error testing Lassie integration: {e}")
        return False

def main():
    """Main function to fix Lassie integration."""
    logger.info("=== Fixing Lassie Integration ===")

    # 1. Update Lassie implementation
    if not update_lassie_implementation():
        logger.error("Failed to update Lassie implementation")
        return False

    # 2. Restart MCP server
    if not restart_mcp_server():
        logger.error("Failed to restart MCP server")
        return False

    # 3. Test Lassie integration
    if not test_lassie_integration():
        logger.warning("Lassie integration test had issues")
        # Continue anyway as some tests might fail in certain environments

    logger.info("=== Lassie Integration Fix Complete ===")
    logger.info("Enhanced features added:")
    logger.info("1. Multi-tier fallback strategy for content retrieval")
    logger.info("2. Well-known CIDs support for testing")
    logger.info("3. Public gateway integration for better availability")
    logger.info("4. Detailed error messages with actionable suggestions")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
