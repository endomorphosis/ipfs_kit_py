#!/usr/bin/env python3
"""
Update VS Code MCP Configuration

This script updates the VS Code MCP configuration to register our IPFS MCP server
with all the tools.
"""

import os
import json
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# VS Code MCP configuration path
CONFIG_PATH = os.path.expanduser("~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")

# The server configuration to add
IPFS_MCP_CONFIG = {
    "name": "ipfs-mcp-server",
    "url": "http://localhost:8000",
    "tools": [
        {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to list files from"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list files recursively"
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Whether to include hidden files"
                    }
                },
                "required": []
            }
        },
        {
            "name": "read_file",
            "description": "Read a file's contents",
            "parameters": {
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
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "ipfs_add",
            "description": "Add content to IPFS",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to add to IPFS"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Name of the file in IPFS"
                    },
                    "pin": {
                        "type": "boolean",
                        "description": "Whether to pin the content"
                    }
                },
                "required": ["content"]
            }
        },
        {
            "name": "ipfs_cat",
            "description": "Retrieve content from IPFS by CID",
            "parameters": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "CID of the content to retrieve"
                    }
                },
                "required": ["cid"]
            }
        },
        {
            "name": "ipfs_pin",
            "description": "Pin content in IPFS",
            "parameters": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "CID of the content to pin"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to pin recursively"
                    }
                },
                "required": ["cid"]
            }
        },
        {
            "name": "ipfs_unpin",
            "description": "Unpin content in IPFS",
            "parameters": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "CID of the content to unpin"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to unpin recursively"
                    }
                },
                "required": ["cid"]
            }
        },
        {
            "name": "ipfs_list_pins",
            "description": "List pinned items in IPFS",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "Type of pins to list (all, direct, recursive, indirect)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "ipfs_version",
            "description": "Get IPFS version information",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "ipfs_files_ls",
            "description": "List files in the MFS",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to list files from"
                    }
                },
                "required": []
            }
        },
        {
            "name": "ipfs_files_mkdir",
            "description": "Create a directory in the MFS",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to create the directory"
                    },
                    "parents": {
                        "type": "boolean",
                        "description": "Whether to create parent directories if they don't exist"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "ipfs_files_write",
            "description": "Write content to a file in the MFS",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to write to"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    },
                    "create": {
                        "type": "boolean",
                        "description": "Whether to create the file if it doesn't exist"
                    },
                    "truncate": {
                        "type": "boolean",
                        "description": "Whether to truncate the file if it exists"
                    }
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "ipfs_files_read",
            "description": "Read content from a file in the MFS",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to read from"
                    }
                },
                "required": ["path"]
            }
        }
    ]
}

def update_vscode_mcp_config():
    """Update the VS Code MCP configuration."""
    try:
        # Ensure the configuration directory exists
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        
        # Load existing configuration if it exists
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                try:
                    config = json.load(f)
                    logger.info(f"Loaded existing configuration from {CONFIG_PATH}")
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse {CONFIG_PATH}, creating a new configuration")
                    config = {"servers": []}
        else:
            logger.info(f"No existing configuration found at {CONFIG_PATH}, creating a new one")
            config = {"servers": []}
        
        # Remove any existing IPFS MCP server configuration
        config["servers"] = [s for s in config.get("servers", []) if s.get("name") != "ipfs-mcp-server"]
        
        # Add the new IPFS MCP server configuration
        config["servers"].append(IPFS_MCP_CONFIG)
        
        # Save the updated configuration
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
            logger.info(f"Updated configuration saved to {CONFIG_PATH}")
        
        logger.info("VS Code MCP configuration updated successfully")
        logger.info(f"The IPFS MCP server is now registered with {len(IPFS_MCP_CONFIG['tools'])} tools")
        
        return True
    except Exception as e:
        logger.error(f"Error updating VS Code MCP configuration: {e}")
        return False

if __name__ == "__main__":
    if update_vscode_mcp_config():
        print("✅ VS Code MCP configuration updated successfully")
        print("Please restart VS Code for the changes to take effect")
    else:
        print("❌ Failed to update VS Code MCP configuration")
        sys.exit(1)
