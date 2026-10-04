#!/usr/bin/env python3
"""
VSCode MCP Extension Configuration

This script creates a custom MCP configuration that works with VSCode's
extension, exposing all IPFS features to Claude.
"""

import os
import json
import logging
import argparse
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='vscode_mcp.log'
)
logger = logging.getLogger(__name__)

# Add console handler
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Configure VSCode MCP extension for IPFS Kit")
    parser.add_argument("--apply", action="store_true", default=False,
                      help="Apply changes to VSCode settings")
    parser.add_argument("--server-name", type=str, default="ipfs-kit-mcp",
                      help="Custom server name for the MCP settings")
    return parser.parse_args()

def find_vscode_settings():
    """Find the VSCode MCP settings file."""
    # Try different potential locations
    potential_paths = [
        os.path.expanduser('~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json'),
        os.path.expanduser('~/.vscode/extensions/saoudrizwan.claude-dev/settings/cline_mcp_settings.json'),
        os.path.expanduser('~/.vscode-server/extensions/saoudrizwan.claude-dev/settings/cline_mcp_settings.json')
    ]

    for path in potential_paths:
        if os.path.exists(path):
            logger.info(f"Found VSCode MCP settings at: {path}")
            return path

    logger.warning("Could not find VSCode MCP settings file")
    return None

def create_ipfs_mcp_config(server_name="ipfs-kit-mcp"):
    """Create a custom MCP configuration for IPFS Kit."""
    # Define tools with schemas that VSCode can use
    tools = [
        {
            "name": "ipfs_add",
            "description": "Add content to IPFS",
            "input_schema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to add to IPFS"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional filename for the content",
                        "default": "file.txt"
                    },
                    "pin": {
                        "type": "boolean",
                        "description": "Whether to pin the content",
                        "default": True
                    }
                },
                "required": ["content"]
            }
        },
        {
            "name": "ipfs_cat",
            "description": "Retrieve content from IPFS",
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
        },
        {
            "name": "ipfs_pin",
            "description": "Pin content to the local IPFS node",
            "input_schema": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "Content ID (CID) to pin"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to recursively pin the content",
                        "default": True
                    }
                },
                "required": ["cid"]
            }
        },
        {
            "name": "ipfs_files_ls",
            "description": "List files in the MFS (Mutable File System)",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in MFS to list",
                        "default": "/"
                    },
                    "long": {
                        "type": "boolean",
                        "description": "Show detailed file information",
                        "default": False
                    }
                }
            }
        },
        {
            "name": "ipfs_files_mkdir",
            "description": "Create a directory in MFS",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in MFS to create"
                    },
                    "parents": {
                        "type": "boolean",
                        "description": "Create parent directories if they don't exist",
                        "default": True
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "ipfs_files_write",
            "description": "Write content to a file in MFS",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in MFS to write to"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
                    },
                    "create": {
                        "type": "boolean",
                        "description": "Create the file if it doesn't exist",
                        "default": True
                    },
                    "truncate": {
                        "type": "boolean",
                        "description": "Truncate the file before writing",
                        "default": True
                    }
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "ipfs_files_read",
            "description": "Read content from a file in MFS",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in MFS to read"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset to start reading from",
                        "default": 0
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of bytes to read (0 means read all)",
                        "default": 0
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "list_files",
            "description": "List files in the local filesystem",
            "input_schema": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to list",
                        "default": "."
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "List recursively",
                        "default": False
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Include hidden files",
                        "default": False
                    }
                }
            }
        },
        {
            "name": "read_file",
            "description": "Read a file from the local filesystem",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "write_file",
            "description": "Write content to a file in the local filesystem",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
                    }
                },
                "required": ["path", "content"]
            }
        }
    ]

    # Define resources
    resources = [
        {
            "uri": "ipfs://info",
            "description": "Information about the IPFS node"
        },
        {
            "uri": "ipfs://stats",
            "description": "Statistics about the IPFS node"
        },
        {
            "uri": "storage://backends",
            "description": "Available storage backends"
        },
        {
            "uri": "mfs://root",
            "description": "Root of the Mutable File System"
        }
    ]

    # Create server configuration
    server_config = {
        "name": server_name,
        "url": "http://localhost:9994",
        "tools": tools,
        "resources": resources
    }

    return server_config

def update_vscode_settings(settings_path, server_config):
    """Update VSCode settings with the new MCP configuration."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)

        # Load existing settings if they exist
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                settings = json.load(f)
        else:
            settings = {"servers": []}

        # Remove existing server with the same name if it exists
        settings["servers"] = [s for s in settings.get("servers", []) if s.get("name") != server_config["name"]]

        # Add the new server configuration
        settings["servers"].append(server_config)

        # Write the updated settings
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)

        logger.info(f"Successfully updated VSCode MCP settings at {settings_path}")
        return True
    except Exception as e:
        logger.error(f"Error updating VSCode settings: {e}")
        return False

def main():
    """Main function."""
    args = parse_args()

    # Find VSCode settings
    settings_path = find_vscode_settings()
    if not settings_path and args.apply:
        logger.error("Could not find VSCode settings file")
        return 1

    # Create MCP configuration
    server_config = create_ipfs_mcp_config(args.server_name)
    logger.info(f"Created MCP configuration for server: {args.server_name}")

    # Show configuration
    print(f"MCP Server Configuration for {args.server_name}:")
    print(json.dumps(server_config, indent=2))

    # Update VSCode settings if requested
    if args.apply and settings_path:
        success = update_vscode_settings(settings_path, server_config)
        if success:
            print(f"Successfully updated VSCode MCP settings with {len(server_config['tools'])} tools")
            print("Restart VSCode to apply the changes")
        else:
            print("Failed to update VSCode MCP settings")
    elif args.apply:
        print("Could not apply changes: VSCode settings file not found")
    else:
        print("Dry run: Use --apply to update VSCode settings")

    return 0

if __name__ == "__main__":
    sys.exit(main())
