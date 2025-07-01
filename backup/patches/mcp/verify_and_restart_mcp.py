#!/usr/bin/env python3
"""
Verify and Restart MCP Server

This script verifies that the MCP server configuration is correct, and then
restarts the MCP server to apply all changes.
"""

import os
import sys
import json
import logging
import subprocess
import time
import requests
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def verify_mcp_config():
    """Verify that the MCP configuration is correct."""
    # Define the path to the settings file
    settings_path = os.path.expanduser("~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")

    if not os.path.exists(settings_path):
        logger.error(f"Settings file not found: {settings_path}")
        return False

    try:
        # Read existing settings
        with open(settings_path, 'r') as f:
            settings = json.load(f)

        # Check if mcpServers is an object
        if 'mcpServers' not in settings or not isinstance(settings['mcpServers'], dict):
            logger.error("mcpServers is not an object in the settings file")
            return False

        # Check if at least one server is defined
        if not settings['mcpServers']:
            logger.error("No MCP servers defined in the settings file")
            return False

        # Check each server for tools
        for server_name, server in settings['mcpServers'].items():
            if 'tools' not in server or not isinstance(server['tools'], list):
                logger.warning(f"Server '{server_name}' has no tools defined")
            elif not server['tools']:
                logger.warning(f"Server '{server_name}' has an empty tools list")
            else:
                logger.info(f"Server '{server_name}' has {len(server['tools'])} tools defined")

            if 'url' not in server:
                logger.warning(f"Server '{server_name}' has no URL defined")
            else:
                logger.info(f"Server '{server_name}' URL: {server['url']}")

        logger.info("MCP configuration verified successfully")
        return True
    except Exception as e:
        logger.error(f"Error verifying MCP configuration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def stop_mcp_server():
    """Stop any running MCP server processes."""
    logger.info("Stopping any running MCP server processes...")
    try:
        # Get PIDs of running MCP server processes
        ps_cmd = "ps aux | grep 'enhanced_mcp_server_fixed.py' | grep -v grep | awk '{print $2}'"
        ps_output = subprocess.check_output(ps_cmd, shell=True).decode('utf-8').strip()

        if ps_output:
            for pid in ps_output.split('\n'):
                if pid:
                    logger.info(f"Killing MCP server process with PID: {pid}")
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except ProcessLookupError:
                        logger.warning(f"Process with PID {pid} no longer exists")
                    except Exception as e:
                        logger.error(f"Error killing process with PID {pid}: {e}")

            # Wait for processes to terminate
            time.sleep(2)
            logger.info("MCP server processes stopped")
        else:
            logger.info("No running MCP server processes found")

        return True
    except Exception as e:
        logger.error(f"Error stopping MCP server processes: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def start_mcp_server():
    """Start the MCP server."""
    logger.info("Starting MCP server...")
    try:
        # Start the MCP server using the enhanced script
        cmd = "python ./enhanced_mcp_server_fixed.py --port 9994 --api-prefix /api/v0 > mcp_server.log 2>&1 &"
        subprocess.run(cmd, shell=True, check=True)

        # Wait for the server to start
        for i in range(5):
            logger.info(f"Waiting for MCP server to start (attempt {i+1}/5)...")
            time.sleep(2)
            try:
                response = requests.get("http://localhost:9994/")
                if response.status_code == 200:
                    logger.info("MCP server started successfully")
                    return True
            except requests.ConnectionError:
                pass

        logger.error("Failed to start MCP server after 5 attempts")
        return False
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def verify_mcp_server():
    """Verify that the MCP server is running and responding correctly."""
    logger.info("Verifying MCP server...")
    try:
        # Check the root endpoint
        response = requests.get("http://localhost:9994/")
        if response.status_code != 200:
            logger.error(f"MCP server root endpoint returned status code {response.status_code}")
            return False

        # Check the health endpoint
        response = requests.get("http://localhost:9994/api/v0/health")
        if response.status_code != 200:
            logger.error(f"MCP server health endpoint returned status code {response.status_code}")
            return False

        # Check the tools endpoint
        response = requests.get("http://localhost:9994/api/v0/tools")
        if response.status_code != 200:
            logger.warning(f"MCP server tools endpoint returned status code {response.status_code}")

        logger.info("MCP server verification successful")
        return True
    except Exception as e:
        logger.error(f"Error verifying MCP server: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function."""
    logger.info("Starting MCP server verification and restart...")

    # Verify the MCP configuration
    if not verify_mcp_config():
        logger.error("MCP configuration verification failed")
        print("❌ MCP configuration verification failed. Please check the logs for details.")
        sys.exit(1)

    # Stop any running MCP server processes
    if not stop_mcp_server():
        logger.error("Failed to stop MCP server processes")
        print("❌ Failed to stop MCP server processes. Please check the logs for details.")
        sys.exit(1)

    # Start the MCP server
    if not start_mcp_server():
        logger.error("Failed to start MCP server")
        print("❌ Failed to start MCP server. Please check the logs for details.")
        sys.exit(1)

    # Verify the MCP server
    if not verify_mcp_server():
        logger.error("MCP server verification failed")
        print("❌ MCP server verification failed. Please check the logs for details.")
        sys.exit(1)

    logger.info("MCP server verification and restart completed successfully")
    print("✅ MCP server verification and restart completed successfully!")
    print("✅ Your MCP tools should now be showing correctly in Claude!")
    print("✅ Please reload the VSCode window if the tools are still not showing.")
    print("✅ MCP server is running at: http://localhost:9994/")
    sys.exit(0)

if __name__ == "__main__":
    main()
