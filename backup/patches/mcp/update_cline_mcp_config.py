#!/usr/bin/env python3
"""
Update the Claude MCP configuration with correct server information and tool definitions.

This script updates the MCP configuration file for Claude to properly connect to our
enhanced MCP server and define tools and resources.
"""

import os
import sys
import json
import logging
import argparse
import requests
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_server_info(base_url):
    """
    Get server information from the MCP server.

    Args:
        base_url: Base URL of the MCP server

    Returns:
        Dictionary with server information
    """
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get server info: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error getting server info: {e}")
        return None

def create_mcp_configuration(base_url, settings_path):
    """
    Create MCP configuration with tools and resources based on server information.

    Args:
        base_url: Base URL of the MCP server
        settings_path: Path to the Claude MCP settings file

    Returns:
        Boolean indicating success
    """
    server_info = get_server_info(base_url)
    if not server_info:
        return False

    # Check if the settings file exists
    if not os.path.exists(settings_path):
        logger.error(f"Settings file not found: {settings_path}")
        return False

    try:
        # Read existing settings
        with open(settings_path, 'r') as f:
            settings = json.load(f)

        # Create or update the localhost server entry
        if 'mcpServers' not in settings:
            settings['mcpServers'] = {}

        # Define the server
        settings['mcpServers']['localhost'] = {
            "autoApprove": [],
            "disabled": False,
            "timeout": 60,
            "url": f"{base_url}/api/v0/sse",
            "transportType": "sse"
        }

        # Define additional MCP resources and tools based on server endpoints
        tools = []
        resources = []

        # Add IPFS tools
        if 'ipfs' in server_info.get('controllers', []):
            tools.append({
                "name": "ipfs_add",
                "description": "Add content to IPFS",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Content to add to IPFS"
                        },
                        "pin": {
                            "type": "boolean",
                            "description": "Whether to pin the content"
                        }
                    },
                    "required": ["content"]
                }
            })

            tools.append({
                "name": "ipfs_cat",
                "description": "Get content from IPFS by CID",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "cid": {
                            "type": "string",
                            "description": "Content ID (CID) to retrieve"
                        }
                    },
                    "required": ["cid"]
                }
            })

            tools.append({
                "name": "ipfs_pin",
                "description": "Pin content in IPFS by CID",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "cid": {
                            "type": "string",
                            "description": "Content ID (CID) to pin"
                        }
                    },
                    "required": ["cid"]
                }
            })

        # Add storage backend tools
        storage_backends = server_info.get('storage_backends', {})
        for backend_name, backend_info in storage_backends.items():
            if backend_info.get('available', False):
                tools.append({
                    "name": f"{backend_name}_status",
                    "description": f"Get {backend_name} storage backend status",
                    "input_schema": {
                        "type": "object",
                        "properties": {}
                    }
                })

                if backend_name != "ipfs":
                    tools.append({
                        "name": f"{backend_name}_to_ipfs",
                        "description": f"Transfer content from {backend_name} to IPFS",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": f"Path to file in {backend_name}"
                                }
                            },
                            "required": ["file_path"]
                        }
                    })

                    tools.append({
                        "name": f"{backend_name}_from_ipfs",
                        "description": f"Transfer content from IPFS to {backend_name}",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "cid": {
                                    "type": "string",
                                    "description": "Content ID (CID) to transfer"
                                },
                                "path": {
                                    "type": "string",
                                    "description": f"Destination path in {backend_name}"
                                }
                            },
                            "required": ["cid"]
                        }
                    })

        # Add server information for documentation
        settings['mcpServers']['localhost']['serverInfo'] = server_info
        settings['mcpServers']['localhost']['tools'] = tools
        settings['mcpServers']['localhost']['resources'] = resources

        # Save the updated settings
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)

        logger.info(f"Updated MCP configuration with {len(tools)} tools and {len(resources)} resources")
        return True

    except Exception as e:
        logger.error(f"Error creating MCP configuration: {e}")
        return False

def main():
    """Run the MCP configuration update script."""
    parser = argparse.ArgumentParser(description="Update Claude MCP configuration")
    parser.add_argument("--url", type=str, default="http://localhost:9997", help="Base URL of the MCP server")
    parser.add_argument("--settings", type=str, default=os.path.expanduser("~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"), help="Path to Claude MCP settings file")

    args = parser.parse_args()

    logger.info(f"Updating MCP configuration for server at {args.url}...")

    # Make sure the server is running
    try:
        response = requests.get(f"{args.url}/")
        if response.status_code != 200:
            logger.error(f"Server at {args.url} is not responding correctly: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error connecting to server at {args.url}: {e}")
        sys.exit(1)

    # Create the MCP configuration
    if create_mcp_configuration(args.url, args.settings):
        logger.info("MCP configuration updated successfully")
        print("MCP configuration updated successfully!")
        print("Please reload the VSCode window or restart the server to apply changes.")
        sys.exit(0)
    else:
        logger.error("Failed to update MCP configuration")
        print("Failed to update MCP configuration. Check the logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
