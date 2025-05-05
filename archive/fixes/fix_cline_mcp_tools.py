#!/usr/bin/env python3
"""
Fix Cline MCP Tools

This script fixes the issues with the MCP tools integration,
ensuring all tools are properly initialized and available.
"""

import os
import sys
import logging
import json
import inspect
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fix_cline_mcp_tools")

def fix_ipfs_model_extensions():
    """
    Fix the IPFS model extensions to ensure they are properly attached.
    """
    logger.info("Fixing IPFS model extensions...")
    
    try:
        # Import the model and extensions
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        from ipfs_kit_py.mcp.models.ipfs_model_extensions import add_ipfs_model_extensions
        
        # Get all the extension methods
        extension_funcs = {}
        for name, obj in inspect.getmembers(sys.modules['ipfs_kit_py.mcp.models.ipfs_model_extensions']):
            if inspect.isfunction(obj) and name not in ['add_ipfs_model_extensions']:
                extension_funcs[name] = obj
                logger.info(f"Found extension method: {name}")
        
        # Explicitly monkey-patch the IPFSModel class with each method
        for name, func in extension_funcs.items():
            setattr(IPFSModel, name, func)
            logger.info(f"Added {name} to IPFSModel")
        
        # Create a sample instance to verify
        ipfs_model = IPFSModel()
        for name in extension_funcs.keys():
            if hasattr(ipfs_model, name):
                logger.info(f"Verified {name} is on IPFSModel instance")
            else:
                logger.warning(f"Failed to verify {name} on IPFSModel instance")
        
        return True
    except Exception as e:
        logger.error(f"Error fixing IPFS model extensions: {e}")
        return False

def fix_cline_mcp_settings():
    """
    Fix the Cline MCP settings file.
    """
    logger.info("Fixing Cline MCP settings...")
    
    settings_path = os.path.expanduser("~/.config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")
    
    try:
        # Read the current settings
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        
        # Check if mcpServers exists
        if "mcpServers" not in settings:
            settings["mcpServers"] = []
        
        # If no servers, add one
        if not settings["mcpServers"]:
            settings["mcpServers"].append({
                "name": "ipfs-kit-mcp",
                "description": "IPFS Kit MCP Server with storage backends (IPFS, Filecoin, Hugging Face, Storacha, Lassie, S3)",
                "url": "http://localhost:9994/api/v0",
                "enabled": True,
                "authentication": {
                    "type": "none"
                }
            })
        
        # Get the first server
        server = settings["mcpServers"][0]
        
        # Make sure it has resources
        if "resources" not in server:
            server["resources"] = [
                {
                    "uri": "ipfs://info",
                    "description": "IPFS node information",
                    "mediaType": "application/json"
                },
                {
                    "uri": "storage://backends",
                    "description": "Available storage backends",
                    "mediaType": "application/json"
                }
            ]
        
        # Make sure it has tools
        if "tools" not in server:
            server["tools"] = []
        
        # Define the required tools
        required_tools = {
            "ipfs_add": {
                "description": "Add content to IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Content to add to IPFS"
                        },
                        "pin": {
                            "type": "boolean",
                            "description": "Whether to pin the content",
                            "default": True
                        }
                    },
                    "required": ["content"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {
                            "type": "string",
                            "description": "Content identifier (CID) of the added content"
                        },
                        "size": {
                            "type": "integer",
                            "description": "Size of the added content in bytes"
                        }
                    }
                }
            },
            "ipfs_cat": {
                "description": "Retrieve content from IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {
                            "type": "string",
                            "description": "Content identifier (CID) to retrieve"
                        }
                    },
                    "required": ["cid"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Retrieved content"
                        }
                    }
                }
            },
            "ipfs_pin": {
                "description": "Pin content in IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {
                            "type": "string",
                            "description": "Content identifier (CID) to pin"
                        }
                    },
                    "required": ["cid"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the pinning was successful"
                        }
                    }
                }
            },
            "storage_transfer": {
                "description": "Transfer content between storage backends",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Source storage backend (ipfs, filecoin, huggingface, storacha, lassie, s3)"
                        },
                        "destination": {
                            "type": "string",
                            "description": "Destination storage backend (ipfs, filecoin, huggingface, storacha, lassie, s3)"
                        },
                        "identifier": {
                            "type": "string",
                            "description": "Content identifier in the source backend"
                        }
                    },
                    "required": ["source", "destination", "identifier"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the transfer was successful"
                        },
                        "destinationId": {
                            "type": "string",
                            "description": "Identifier of the content in the destination backend"
                        }
                    }
                }
            }
        }
        
        # Add missing tools
        existing_tool_names = {tool.get("name") for tool in server["tools"]}
        for tool_name, tool_def in required_tools.items():
            if tool_name not in existing_tool_names:
                server["tools"].append({
                    "name": tool_name,
                    **tool_def
                })
                logger.info(f"Added missing tool: {tool_name}")
        
        # Write back the updated settings
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)
        
        logger.info(f"Updated Cline MCP settings at: {settings_path}")
        return True
    except Exception as e:
        logger.error(f"Error fixing Cline MCP settings: {e}")
        return False

def main():
    """
    Main function to fix all issues.
    """
    logger.info("Starting MCP tools fix...")
    
    # Fix IPFS model extensions
    if fix_ipfs_model_extensions():
        logger.info("Successfully fixed IPFS model extensions")
    else:
        logger.error("Failed to fix IPFS model extensions")
    
    # Fix Cline MCP settings
    if fix_cline_mcp_settings():
        logger.info("Successfully fixed Cline MCP settings")
    else:
        logger.error("Failed to fix Cline MCP settings")
    
    logger.info("MCP tools fix completed")
    
if __name__ == "__main__":
    main()
