#!/usr/bin/env python3
"""
Debug FastMCP Tools Registration

This script checks if the IPFS tools are properly registered with the FastMCP server.
"""

import sys
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("debug-fastmcp")

# Try to import requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    logger.warning("requests not available, using subprocess for HTTP calls")
    import subprocess
    REQUESTS_AVAILABLE = False

def check_server_tools():
    """Check what tools are available on the FastMCP server"""
    server_url = "http://localhost:3001"
    
    try:
        # Check health endpoint
        logger.info("Checking server health...")
        
        if REQUESTS_AVAILABLE:
            health_response = requests.get(f"{server_url}/health")
            logger.info(f"Health status: {health_response.status_code}")
            if health_response.status_code == 200:
                logger.info(f"Health response: {health_response.json()}")
        else:
            # Use curl for HTTP requests
            import subprocess
            result = subprocess.run(['curl', '-s', f"{server_url}/health"], 
                                  capture_output=True, text=True)
            logger.info(f"Health response: {result.stdout}")
            
    except Exception as e:
        logger.error(f"Error checking server tools: {e}")

def check_fastmcp_internals():
    """Try to check FastMCP internals by importing the server module"""
    try:
        logger.info("Attempting to import server module...")
        
        # Add the current directory to sys.path
        import os
        current_dir = os.getcwd()
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # Try to import the direct server module
        try:
            import direct_mcp_server
            logger.info("Successfully imported direct_mcp_server")
            
            # Check if the server variable exists
            if hasattr(direct_mcp_server, 'server'):
                server = direct_mcp_server.server
                logger.info(f"Server object found: {type(server)}")
                
                # Check for tools attribute
                if hasattr(server, 'tools'):
                    tools = server.tools
                    logger.info(f"Tools found: {len(tools) if hasattr(tools, '__len__') else 'Unknown count'}")
                    if hasattr(tools, '__len__') and len(tools) > 0:
                        logger.info(f"Tool names: {list(tools.keys()) if hasattr(tools, 'keys') else str(tools)[:200]}")
                else:
                    logger.info("No 'tools' attribute found on server")
                    
                # Check for other attributes that might contain tools
                attrs = dir(server)
                tool_attrs = [attr for attr in attrs if 'tool' in attr.lower()]
                if tool_attrs:
                    logger.info(f"Tool-related attributes: {tool_attrs}")
                    
            else:
                logger.info("No 'server' variable found in direct_mcp_server")
                
        except ImportError as e:
            logger.error(f"Could not import direct_mcp_server: {e}")
            
    except Exception as e:
        logger.error(f"Error checking FastMCP internals: {e}")

def main():
    """Main function"""
    logger.info("=== FastMCP Tools Debug ===")
    
    logger.info("1. Checking server tools via HTTP...")
    check_server_tools()
    
    logger.info("\n2. Checking FastMCP internals...")
    check_fastmcp_internals()
    
    logger.info("=== Debug Complete ===")

if __name__ == "__main__":
    main()
