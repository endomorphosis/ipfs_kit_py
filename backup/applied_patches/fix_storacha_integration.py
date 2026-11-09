#!/usr/bin/env python3
"""
Fix Storacha Integration

This script implements the enhanced Storacha integration with proper fallback
mechanisms and endpoint handling as outlined in the MCP roadmap.
"""

import os
import sys
import logging
import json
import subprocess
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def ensure_enhanced_implementation():
    """
    Verify the enhanced Storacha implementation is properly set up.

    Returns:
        bool: True if setup succeeded, False otherwise
    """
    # Check if enhanced implementation exists
    enhanced_path = Path("enhanced_storacha_storage.py")
    if not enhanced_path.exists():
        logger.error("Enhanced Storacha implementation not found")
        return False

    # Ensure the extension is using the enhanced implementation
    extension_path = Path("mcp_extensions/storacha_extension.py")
    if not extension_path.exists():
        logger.error("Storacha extension not found")
        return False

    # Check if the extension is already using the enhanced implementation
    with open(extension_path, "r") as f:
        content = f.read()
        if "enhanced_storacha_storage" in content:
            logger.info("Extension is already using enhanced implementation")
        else:
            logger.warning("Extension is not using enhanced implementation")
            return False

    logger.info("Enhanced Storacha implementation is properly set up")
    return True

def test_storacha_integration():
    """
    Test the Storacha integration to verify it's working properly.

    Returns:
        bool: True if tests pass, False otherwise
    """
    # Ensure MCP server is running
    try:
        health_output = subprocess.run(
            ["curl", "http://localhost:9997/api/v0/health"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if health_output.returncode != 0:
            logger.error("MCP server is not running")
            return False

        # Check Storacha status
        storacha_output = subprocess.run(
            ["curl", "http://localhost:9997/api/v0/storacha/status"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if storacha_output.returncode != 0:
            logger.error("Failed to get Storacha status")
            return False

        # Parse the status
        try:
            status = json.loads(storacha_output.stdout)
            logger.info(f"Storacha status: {json.dumps(status, indent=2)}")

            # Check if the status is healthy
            if status.get("success", False):
                logger.info("Storacha integration is working")
                return True
            else:
                logger.warning("Storacha integration reported failure")
                logger.warning(f"Error: {status.get('error', 'Unknown')}")
                return False
        except json.JSONDecodeError:
            logger.error("Failed to parse Storacha status")
            logger.error(f"Output: {storacha_output.stdout}")
            return False

    except Exception as e:
        logger.error(f"Error testing Storacha integration: {e}")
        return False

def restart_mcp_server():
    """
    Restart the MCP server with the updated Storacha integration.

    Returns:
        bool: True if restart succeeded, False otherwise
    """
    # Stop any running MCP server
    logger.info("Stopping any running MCP server instances...")
    try:
        # Try to kill using the PID file
        pid_file = Path("/tmp/mcp/server.pid")
        if pid_file.exists():
            with open(pid_file, "r") as f:
                pid = f.read().strip()
                subprocess.run(["kill", "-15", pid], check=False)
                logger.info(f"Stopped MCP server with PID {pid}")

        # Also try to kill by process name
        subprocess.run(
            ["pkill", "-f", "enhanced_mcp_server.py"],
            check=False
        )

        # Wait for it to stop
        time.sleep(2)
    except Exception as e:
        logger.warning(f"Error stopping MCP server: {e}")

    # Start the MCP server using the start script
    logger.info("Starting MCP server...")
    try:
        subprocess.run(
            ["./start_mcp_server.sh"],
            check=True
        )

        # Wait for it to start
        time.sleep(5)

        # Verify it's running
        health_output = subprocess.run(
            ["curl", "http://localhost:9997/api/v0/health"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if health_output.returncode != 0:
            logger.error("Failed to start MCP server")
            return False

        logger.info("MCP server started successfully")
        return True

    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return False

def main():
    """
    Main function to fix the Storacha integration.
    """
    logger.info("=== Fixing Storacha Integration ===")

    # Ensure the enhanced implementation is set up
    if not ensure_enhanced_implementation():
        logger.error("Failed to set up enhanced Storacha implementation")
        return False

    # Restart the MCP server
    if not restart_mcp_server():
        logger.error("Failed to restart MCP server")
        return False

    # Test the Storacha integration
    if not test_storacha_integration():
        logger.warning("Storacha integration test failed")
        return False

    logger.info("=== Storacha Integration Fixed Successfully ===")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
