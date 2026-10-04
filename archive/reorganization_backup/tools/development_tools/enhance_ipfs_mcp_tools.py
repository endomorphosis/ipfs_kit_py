#!/usr/bin/env python3
"""
Enhance IPFS MCP Tools

This script adds additional IPFS-specific tools to the MCP server to increase
coverage of IPFS features and ensure proper integration with virtual filesystem.
"""

import os
import sys
import json
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def update_mcp_config(config_path):
    """Update the MCP config file to include additional IPFS tools."""
    try:
        if not os.path.exists(config_path):
            logger.error(f"❌ Config file not found: {config_path}")
            return False
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Check if the configuration has a mcpServers section
        if 'mcpServers' not in config:
            logger.error("❌ Invalid configuration: 'mcpServers' section not found")
            return False
        
        # The configuration structure is different than expected
        # We need to create a new configuration file specifically for tools
        tools_config_path = os.path.join(os.path.dirname(config_path), 'mcp_tools_config.json')
        
        # Create a new configuration structure for the tools
        ipfs_server = {
            "name": "direct-ipfs-kit-mcp",
            "url": config['mcpServers'].get('direct-ipfs-kit-mcp', {}).get('url', 'http://localhost:3000/sse'),
            "tools": []
        }
        
        if not ipfs_server:
            logger.error("❌ IPFS server configuration not found")
            return False
        
        # Add or update IPFS tools
        ipfs_tools = [
            {
                "name": "ipfs_files_ls",
                "description": "List files and directories in the IPFS MFS (Mutable File System)",
                "schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string", 
                            "description": "Path within MFS to list (default: /)",
                            "default": "/"
                        },
                        "long": {
                            "type": "boolean", 
                            "description": "Use long listing format (include size, type)",
                            "default": False
                        }
                    }
                }
            },
            {
                "name": "ipfs_files_mkdir",
                "description": "Create directories in the IPFS MFS (Mutable File System)",
                "schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string", 
                            "description": "Path to create within MFS"
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
                "description": "Write data to a file in the IPFS MFS (Mutable File System)",
                "schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string", 
                            "description": "Path within MFS to write to"
                        },
                        "content": {
                            "type": "string", 
                            "description": "Content to write to the file"
                        },
                        "create": {
                            "type": "boolean", 
                            "description": "Create the file if it doesn't exist",
                            "default": True
                        },
                        "truncate": {
                            "type": "boolean", 
                            "description": "Truncate the file if it already exists",
                            "default": True
                        }
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "ipfs_files_read",
                "description": "Read a file from the IPFS MFS (Mutable File System)",
                "schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string", 
                            "description": "Path within MFS to read from"
                        },
                        "offset": {
                            "type": "integer", 
                            "description": "Byte offset to start reading from",
                            "default": 0
                        },
                        "count": {
                            "type": "integer", 
                            "description": "Maximum number of bytes to read",
                            "default": -1
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "ipfs_files_rm",
                "description": "Remove files or directories from the IPFS MFS",
                "schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string", 
                            "description": "Path within MFS to remove"
                        },
                        "recursive": {
                            "type": "boolean", 
                            "description": "Recursively remove directories",
                            "default": False
                        },
                        "force": {
                            "type": "boolean", 
                            "description": "Forcibly remove the file/directory",
                            "default": False
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "ipfs_files_stat",
                "description": "Get information about a file or directory in the MFS",
                "schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string", 
                            "description": "Path within MFS to get stats for"
                        },
                        "with_local": {
                            "type": "boolean", 
                            "description": "Compute the amount of the dag that is local",
                            "default": False
                        },
                        "size": {
                            "type": "boolean", 
                            "description": "Compute the total size of the dag",
                            "default": True
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "ipfs_files_cp",
                "description": "Copy files within the IPFS MFS",
                "schema": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string", 
                            "description": "Source path (can be an MFS or IPFS path)"
                        },
                        "dest": {
                            "type": "string", 
                            "description": "Destination path within MFS"
                        }
                    },
                    "required": ["source", "dest"]
                }
            },
            {
                "name": "ipfs_files_mv",
                "description": "Move files within the IPFS MFS",
                "schema": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string", 
                            "description": "Source path (must be an MFS path)"
                        },
                        "dest": {
                            "type": "string", 
                            "description": "Destination path within MFS"
                        }
                    },
                    "required": ["source", "dest"]
                }
            },
            {
                "name": "ipfs_name_publish",
                "description": "Publish an IPNS name",
                "schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string", 
                            "description": "IPFS path to publish"
                        },
                        "resolve": {
                            "type": "boolean", 
                            "description": "Resolve before publishing",
                            "default": True
                        },
                        "lifetime": {
                            "type": "string", 
                            "description": "Time duration that the record will be valid for",
                            "default": "24h"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "ipfs_name_resolve",
                "description": "Resolve an IPNS name",
                "schema": {
                    "type": "object", 
                    "properties": {
                        "name": {
                            "type": "string", 
                            "description": "The IPNS name to resolve"
                        },
                        "recursive": {
                            "type": "boolean", 
                            "description": "Resolve until the result is not an IPNS name",
                            "default": True
                        },
                        "nocache": {
                            "type": "boolean", 
                            "description": "Do not use cached entries",
                            "default": False
                        }
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "ipfs_dag_put",
                "description": "Add a DAG node to IPFS",
                "schema": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "object", 
                            "description": "The data to store as a DAG node"
                        },
                        "format": {
                            "type": "string", 
                            "description": "The format to use for the DAG node",
                            "default": "cbor",
                            "enum": ["cbor", "json", "raw"]
                        },
                        "input_codec": {
                            "type": "string", 
                            "description": "The codec that the input data is encoded with",
                            "default": "json"
                        },
                        "pin": {
                            "type": "boolean", 
                            "description": "Pin this object when adding",
                            "default": False
                        }
                    },
                    "required": ["data"]
                }
            },
            {
                "name": "ipfs_dag_get",
                "description": "Get a DAG node from IPFS",
                "schema": {
                    "type": "object",
                    "properties": {
                        "cid": {
                            "type": "string", 
                            "description": "The CID of the DAG node to get"
                        },
                        "path": {
                            "type": "string", 
                            "description": "The path within the DAG structure to retrieve",
                            "default": ""
                        }
                    },
                    "required": ["cid"]
                }
            }
        ]
        
        # Update tools in the configuration
        if 'tools' not in ipfs_server:
            ipfs_server['tools'] = []
        
        # Check which tools are already in the configuration
        existing_tool_names = {tool['name'] for tool in ipfs_server['tools']}
        
        # Add new tools, update existing ones
        for tool in ipfs_tools:
            if tool['name'] in existing_tool_names:
                # Update existing tool
                for i, existing_tool in enumerate(ipfs_server['tools']):
                    if existing_tool['name'] == tool['name']:
                        ipfs_server['tools'][i] = tool
                        logger.info(f"📝 Updated tool: {tool['name']}")
                        break
            else:
                # Add new tool
                ipfs_server['tools'].append(tool)
                logger.info(f"➕ Added new tool: {tool['name']}")
        
        # Create the tools configuration file
        tools_config = {
            "servers": [ipfs_server]
        }
        
        # Write the tools configuration to the file
        with open(tools_config_path, 'w') as f:
            json.dump(tools_config, f, indent=2)
        
        logger.info(f"✅ Successfully created IPFS tools configuration at {tools_config_path}")
        
        # Update the local MCP server configuration to point to this file
        logger.info(f"📝 To use these tools, you will need to configure the IPFS MCP server to use this configuration")
        logger.info(f"📋 The tool definition file has been saved at: {tools_config_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error updating MCP configuration: {e}")
        return False

def main():
    """Main function to enhance IPFS MCP tools."""
    parser = argparse.ArgumentParser(description='Enhance IPFS MCP Tools')
    parser.add_argument('--config', help='Path to the MCP config file', 
                        default=os.path.expanduser('~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json'))
    args = parser.parse_args()
    
    logger.info("🔧 Enhancing IPFS MCP Tools...")
    
    if update_mcp_config(args.config):
        logger.info("✅ Successfully enhanced IPFS MCP Tools")
        logger.info("🔄 Please restart the MCP server for changes to take effect")
    else:
        logger.error("❌ Failed to enhance IPFS MCP Tools")
        sys.exit(1)

if __name__ == "__main__":
    main()
