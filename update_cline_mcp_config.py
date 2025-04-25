#!/usr/bin/env python3
"""
Update Cline MCP Configuration

This script updates the Cline MCP settings to ensure it works with our fixed MCP server.
"""

import os
import json
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("update_config")

def main():
    """Update Cline MCP configuration."""
    logger.info("Updating Cline MCP configuration...")
    
    # Define the path to the MCP settings file
    home_dir = os.path.expanduser("~")
    settings_path = os.path.join(
        home_dir,
        ".config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    )
    
    if not os.path.exists(settings_path):
        logger.error(f"MCP settings file not found: {settings_path}")
        return False
    
    # Read the current settings
    try:
        with open(settings_path, "r") as f:
            settings = json.load(f)
        logger.info("Successfully read MCP settings")
    except Exception as e:
        logger.error(f"Failed to read MCP settings: {e}")
        return False
    
    # Check if settings has the required structure
    if "mcpServers" not in settings:
        logger.error("Invalid settings file: mcpServers key not found")
        return False
    
    # Update the MCP server configuration - make sure all needed tools are defined
    updated = False
    
    # Ensure mcpServers exists and is a list
    if "mcpServers" not in settings:
        settings["mcpServers"] = []
        updated = True
    elif not isinstance(settings["mcpServers"], list):
        # If it's not a list, convert it to one
        logger.warning("mcpServers is not a list, converting it")
        settings["mcpServers"] = [settings["mcpServers"]] if settings["mcpServers"] else []
        updated = True
        
    # Check if our server exists
    server_exists = False
    for i, server in enumerate(settings["mcpServers"]):
        if isinstance(server, dict) and "name" in server and server.get("name") == "ipfs-kit-mcp":
            server_exists = True
            # Server already exists, make sure it has all required tools
            required_tools = ["ipfs_add", "ipfs_cat", "ipfs_pin", "storage_transfer"]
            
            # Check if tools key exists
            if "tools" not in server:
                server["tools"] = []
            
            # Ensure each required tool is defined
            for tool_name in required_tools:
                tool_exists = any(tool.get("name") == tool_name for tool in server["tools"])
                
                if not tool_exists:
                    # Add the missing tool
                    if tool_name == "ipfs_add":
                        server["tools"].append({
                            "name": "ipfs_add",
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
                        })
                        logger.info("Added ipfs_add tool")
                    elif tool_name == "ipfs_cat":
                        server["tools"].append({
                            "name": "ipfs_cat",
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
                        })
                        logger.info("Added ipfs_cat tool")
                    elif tool_name == "ipfs_pin":
                        server["tools"].append({
                            "name": "ipfs_pin",
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
                        })
                        logger.info("Added ipfs_pin tool")
                    elif tool_name == "storage_transfer":
                        server["tools"].append({
                            "name": "storage_transfer",
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
                        })
                        logger.info("Added storage_transfer tool")
                    
                    updated = True
            
            # Make sure the server is enabled
            if not server.get("enabled", False):
                server["enabled"] = True
                updated = True
                logger.info("Enabled MCP server")
            
            # Make sure the URL is correct
            port = os.environ.get("MCP_PORT", "9994")
            api_prefix = os.environ.get("MCP_API_PREFIX", "/api/v0")
            expected_url = f"http://localhost:{port}{api_prefix}"
            
            if server.get("url") != expected_url:
                server["url"] = expected_url
                updated = True
                logger.info(f"Updated server URL to {expected_url}")
            
            break
    else:
        # Server doesn't exist, create it
        port = os.environ.get("MCP_PORT", "9994")
        api_prefix = os.environ.get("MCP_API_PREFIX", "/api/v0")
        
        settings["mcpServers"].append({
            "name": "ipfs-kit-mcp",
            "description": "IPFS Kit MCP Server with storage backends (IPFS, Filecoin, Hugging Face, Storacha, Lassie, S3)",
            "url": f"http://localhost:{port}{api_prefix}",
            "enabled": True,
            "authentication": {
                "type": "none"
            },
            "resources": [
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
            ],
            "tools": [
                {
                    "name": "ipfs_add",
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
                {
                    "name": "ipfs_cat",
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
                {
                    "name": "ipfs_pin",
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
                {
                    "name": "storage_transfer",
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
            ]
        })
        logger.info("Added new MCP server configuration")
        updated = True
    
    # Write the updated settings back to the file if changes were made
    if updated:
        try:
            # Create backup
            backup_path = f"{settings_path}.bak"
            with open(backup_path, "w") as f:
                json.dump(settings, f, indent=2)
            logger.info(f"Created backup at {backup_path}")
            
            # Write updated settings
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=2)
            logger.info("Successfully wrote updated MCP settings")
        except Exception as e:
            logger.error(f"Failed to write updated MCP settings: {e}")
            return False
    else:
        logger.info("No changes were needed to the MCP settings")
    
    logger.info("Cline MCP configuration update completed successfully")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
