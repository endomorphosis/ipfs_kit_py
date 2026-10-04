#!/usr/bin/env python3
"""
Verify Tools

This script connects to the MCP server and lists all available tools,
grouped by category for better organization.
"""

import os
import sys
import json
import logging
import requests
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP Server URL
MCP_URL = "http://127.0.0.1:3000"

def get_all_tools():
    """Get all tools from the MCP server"""
    try:
        response = requests.post(f"{MCP_URL}/jsonrpc", json={
            "jsonrpc": "2.0", 
            "method": "get_tools",
            "params": {},
            "id": 1
        })
        response.raise_for_status()
        data = response.json()
        
        if "result" in data and "tools" in data["result"]:
            return data["result"]["tools"]
        else:
            logger.error("Unexpected response format")
            return []
    except Exception as e:
        logger.error(f"Failed to get tools: {e}")
        return []

def group_tools_by_category(tools):
    """Group tools by their category for better organization"""
    categories = {}
    
    for tool in tools:
        name = tool.get("name", "")
        
        # Determine category based on name prefix
        category = "Other"
        if name.startswith("ipfs_"):
            category = "IPFS Core"
        elif name.startswith("fs_journal_"):
            category = "FS Journal"
        elif name.startswith("ipfs_fs_"):
            category = "IPFS-FS Bridge"
        elif name.startswith("multi_backend_"):
            category = "Multi-Backend Storage"
        elif name.startswith("huggingface_"):
            category = "HuggingFace Integration"
        elif name.startswith("s3_"):
            category = "S3 Integration"
        elif name.startswith("filecoin_"):
            category = "Filecoin Integration"
        elif name.startswith("credential_"):
            category = "Credential Management"
        elif name.startswith("webrtc_"):
            category = "WebRTC Integration"
        
        # Add to appropriate category
        if category not in categories:
            categories[category] = []
        categories[category].append(tool)
    
    return categories

def print_tools_by_category(categories):
    """Print tools organized by category"""
    print("\n=== MCP Server Tools ===\n")
    
    total_tools = sum(len(tools) for tools in categories.values())
    print(f"Total tools available: {total_tools}\n")
    
    # Print each category
    for category, tools in sorted(categories.items()):
        print(f"== {category} ({len(tools)}) ==")
        for tool in sorted(tools, key=lambda t: t.get("name", "")):
            name = tool.get("name", "")
            description = tool.get("description", "No description")
            print(f"  - {name}: {description}")
        print()

def main():
    """Main function"""
    logger.info("Connecting to MCP server...")
    
    # Get all tools
    tools = get_all_tools()
    if not tools:
        logger.error("No tools found. Make sure the MCP server is running.")
        return 1
    
    # Group and print tools
    categories = group_tools_by_category(tools)
    print_tools_by_category(categories)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
