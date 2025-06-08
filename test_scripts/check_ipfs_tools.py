#!/usr/bin/env python3
"""
Script to check IPFS tool registration with MCP server
"""

import os
import sys
import json
import logging
import requests
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("check-ipfs-tools")

def check_health(url):
    """Check the health of the MCP server"""
    try:
        response = requests.get(f"{url}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Health check failed with status code {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error checking health: {e}")
        return None

def list_tools(url):
    """List all tools registered with the server using JSON-RPC"""
    try:
        # Try JSON-RPC method
        payload = {
            "jsonrpc": "2.0",
            "method": "rpc.discover",
            "id": 1
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            f"{url}/jsonrpc",
            headers=headers,
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                return result["result"]
            else:
                logger.warning(f"No result in JSON-RPC response: {result}")
                return None
        else:
            logger.warning(f"JSON-RPC failed with status code {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        return None

def check_tool_categories(tools_list):
    """Check and categorize tools by prefix"""
    categories = {}
    
    for tool in tools_list:
        prefix = tool.split("_")[0] if "_" in tool else "other"
        if prefix not in categories:
            categories[prefix] = []
        categories[prefix].append(tool)
    
    return categories

def main():
    # URL of the MCP server
    server_url = "http://localhost:8002"
    
    # Check if the server is running
    logger.info(f"Checking MCP server at {server_url}...")
    health = check_health(server_url)
    
    if not health:
        logger.error("Could not connect to MCP server")
        return 1
    
    logger.info(f"Server status: {health['status']}")
    logger.info(f"Server version: {health['version']}")
    logger.info(f"Server uptime: {health['uptime_seconds']} seconds")
    logger.info(f"Tools count: {health['tools_count']}")
    logger.info(f"Registered tool categories: {health['registered_tool_categories']}")
    
    # List tools
    logger.info("Listing registered tools...")
    tools_data = list_tools(server_url)
    
    if not tools_data:
        logger.warning("Could not list tools")
        return 1
    
    # Get the list of method names
    if isinstance(tools_data, dict) and "methods" in tools_data:
        # Format from rpc.discover
        methods = list(tools_data["methods"].keys())
    else:
        # Direct list format
        methods = tools_data if isinstance(tools_data, list) else []
    
    logger.info(f"Found {len(methods)} methods")
    
    # Check for IPFS tools
    ipfs_tools = [method for method in methods if method.startswith("ipfs_")]
    logger.info(f"Found {len(ipfs_tools)} IPFS tools")
    
    # Print all IPFS tools
    if ipfs_tools:
        logger.info("IPFS tools:")
        for tool in sorted(ipfs_tools):
            logger.info(f"  - {tool}")
    else:
        logger.warning("No IPFS tools found!")
    
    # Check all tool categories
    categories = check_tool_categories(methods)
    logger.info("Tool categories:")
    for category, tools in categories.items():
        logger.info(f"  - {category}: {len(tools)} tools")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
