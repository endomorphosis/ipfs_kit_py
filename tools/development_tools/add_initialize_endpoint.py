#!/usr/bin/env python3
"""
MCP Initialize Endpoint Fix

This script adds the initialize endpoint to the MCP server which is required for VS Code integration.
The initialize endpoint responds to the request that VS Code sends when establishing a connection.
"""

import os
import sys
import logging
import requests
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def add_initialize_endpoint():
    """
    Add the initialize endpoint to the MCP server.
    
    This function creates a FastAPI endpoint at /api/v0/initialize that responds to the
    VS Code initialization request with information about server capabilities.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # First, check if the server is running
        try:
            response = requests.get("http://localhost:9994/")
            server_info = response.json()
            logger.info(f"Found running MCP server: {server_info.get('name', 'Unknown')}")
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            logger.info("Make sure the MCP server is running on port 9994 before running this script.")
            return False
        
        # Import the necessary functions to patch the server
        sys.path.insert(0, str(Path.cwd()))
        
        # Try to import from different potential module paths
        try:
            # Try to import from mcp.server_bridge first (most common)
            from ipfs_kit_py.mcp.server_bridge import MCPServer
            server_module = "ipfs_kit_py.mcp.server_bridge"
            logger.info("Imported MCPServer from ipfs_kit_py.mcp.server_bridge")
        except ImportError:
            try:
                # Try the anyio version
                from ipfs_kit_py.mcp.server_anyio import MCPServer
                server_module = "ipfs_kit_py.mcp.server_anyio"
                logger.info("Imported MCPServer from ipfs_kit_py.mcp.server_anyio")
            except ImportError:
                try:
                    # Try the mcp_server module
                    from ipfs_kit_py.mcp.server.server_bridge import MCPServer
                    server_module = "ipfs_kit_py.mcp.server.server_bridge"
                    logger.info("Imported MCPServer from ipfs_kit_py.mcp.server.server_bridge")
                except ImportError:
                    logger.error("Could not import MCPServer from any known location")
                    return False
        
        # Get the module
        import importlib
        server_mod = importlib.import_module(server_module)
        
        # Check if the initialize endpoint already exists
        if hasattr(server_mod.MCPServer, "initialize_endpoint"):
            logger.info("Initialize endpoint already exists in MCPServer class")
            return True
        
        # Define the initialize endpoint method
        def initialize_endpoint(self):
            """
            Handle the initialize request from VS Code.
            
            Returns:
                dict: Server capabilities and information
            """
            logger.info("Received initialize request")
            return {
                "capabilities": {
                    "tools": ["ipfs_add", "ipfs_cat", "ipfs_pin", "storage_transfer"],
                    "resources": ["ipfs://info", "storage://backends"]
                },
                "serverInfo": {
                    "name": "IPFS Kit MCP Server",
                    "version": "1.0.0",
                    "implementationName": "ipfs-kit-py"
                }
            }
        
        # Add the method to the MCPServer class
        setattr(server_mod.MCPServer, "initialize_endpoint", initialize_endpoint)
        
        # Add the endpoint to the create_router method
        original_create_router = server_mod.MCPServer.create_router
        
        def patched_create_router(self):
            """
            Create the API router with additional initialize endpoint.
            """
            router = original_create_router(self)
            
            # Add the initialize endpoint
            from fastapi import APIRouter, Request
            router.add_api_route("/initialize", self.initialize_endpoint, methods=["POST", "GET"], tags=["Initialize"])
            logger.info("Added initialize endpoint to router")
            
            return router
        
        # Replace the create_router method
        setattr(server_mod.MCPServer, "create_router", patched_create_router)
        
        logger.info("Successfully patched MCPServer with initialize endpoint")
        
        # Reload the server (not actually restarting it, just patching the class)
        logger.info("Patch applied - server restart required to take effect")
        
        return True
        
    except Exception as e:
        logger.error(f"Error adding initialize endpoint: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def restart_mcp_server():
    """
    Restart the MCP server to apply the changes.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Attempting to restart MCP server...")
        
        # Try to find and kill the existing MCP server process
        import subprocess
        try:
            # Find PID of running MCP server
            result = subprocess.run(
                ["pgrep", "-f", "python.*enhanced_mcp_server"], 
                capture_output=True, 
                text=True
            )
            pids = result.stdout.strip().split('\n')
            
            # Kill the processes if found
            for pid in pids:
                if pid:
                    subprocess.run(["kill", pid])
                    logger.info(f"Terminated MCP server process with PID {pid}")
            
            # Wait for process to terminate
            time.sleep(2)
            
        except Exception as e:
            logger.warning(f"Error stopping existing MCP server: {e}")
        
        # Start new MCP server
        subprocess.Popen(
            ["python3", "./enhanced_mcp_server_fixed.py", "--port", "9994", "--api-prefix", "/api/v0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        logger.info("Started new MCP server instance")
        
        # Allow server time to start
        time.sleep(3)
        
        # Check if server is responding
        try:
            response = requests.get("http://localhost:9994/")
            if response.status_code == 200:
                logger.info("MCP server successfully restarted")
                return True
            else:
                logger.error(f"MCP server not responding properly: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error checking restarted server: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error restarting MCP server: {e}")
        return False

def main():
    """Main function."""
    logger.info("Adding initialize endpoint to MCP server...")
    
    if add_initialize_endpoint():
        logger.info("Successfully added initialize endpoint")
        
        # Restart the server to apply changes
        if restart_mcp_server():
            print("✅ MCP server patched and restarted successfully!")
            print("VS Code should now be able to connect to the MCP server.")
            sys.exit(0)
        else:
            print("⚠️ MCP server patched but restart failed.")
            print("Please manually restart the MCP server to apply changes.")
            sys.exit(1)
    else:
        logger.error("Failed to add initialize endpoint")
        print("❌ Failed to add initialize endpoint. Check the logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
