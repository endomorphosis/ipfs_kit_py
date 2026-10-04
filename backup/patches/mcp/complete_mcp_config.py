#!/usr/bin/env python3
"""
Complete MCP Configuration

This script creates a complete MCP configuration with all necessary fields,
including tools and resources.
"""

import os
import sys
import json
import logging
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_complete_mcp_config():
    """Create a complete MCP configuration from scratch."""
    # Define the path to the settings file
    settings_path = os.path.expanduser("~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")

    # Get server info to ensure it's running
    try:
        response = requests.get("http://localhost:9994/")
        server_info = response.json()
    except Exception as e:
        logger.error(f"Error connecting to MCP server: {e}")
        return False

    # Define the complete configuration
    complete_config = {
        "mcpServers": {
            "ipfs-kit-mcp": {
                "disabled": False,
                "timeout": 60,
                "url": "http://localhost:9994/api/v0/sse",
                "transportType": "sse",
                "jsonRpcUrl": "http://localhost:9994/api/v0/jsonrpc",
                "serverInfo": server_info,
                "authentication": {
                    "type": "none"
                },
                "initialize": {
                    "capabilities": {
                        "tools": ["ipfs_add", "ipfs_cat", "ipfs_pin", "storage_transfer"],
                        "resources": ["ipfs://info", "storage://backends"]
                    },
                    "serverInfo": {
                        "name": "IPFS Kit MCP Server",
                        "version": "1.0.0",
                        "implementationName": "ipfs-kit-py"
                    }
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
            }
        }
    }

    # Add storage-specific tools based on available endpoints
    if 'available_endpoints' in server_info and 'storage' in server_info['available_endpoints']:
        storage_endpoints = server_info['available_endpoints']['storage']

        # Add storage backend tools
        for endpoint in storage_endpoints:
            parts = endpoint.split('/')
            if len(parts) >= 4:
                backend_name = parts[3]  # e.g., "huggingface", "s3", "filecoin"

                # Skip health endpoint
                if backend_name == "health":
                    continue

                # Status endpoint
                if "status" in endpoint:
                    complete_config['mcpServers']['ipfs-kit-mcp']['tools'].append({
                        "name": f"{backend_name}_status",
                        "description": f"Get status of {backend_name} storage backend",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "available": {
                                    "type": "boolean",
                                    "description": f"Whether the {backend_name} backend is available"
                                },
                                "status": {
                                    "type": "string",
                                    "description": "Status information"
                                }
                            }
                        }
                    })

                # Transfer to IPFS
                if "to_ipfs" in endpoint:
                    complete_config['mcpServers']['ipfs-kit-mcp']['tools'].append({
                        "name": f"{backend_name}_to_ipfs",
                        "description": f"Transfer content from {backend_name} to IPFS",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": f"Path to file in {backend_name}"
                                }
                            },
                            "required": ["path"]
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "cid": {
                                    "type": "string",
                                    "description": "Content identifier (CID) in IPFS"
                                },
                                "size": {
                                    "type": "integer",
                                    "description": "Size of the transferred content in bytes"
                                }
                            }
                        }
                    })

                # Transfer from IPFS
                if "from_ipfs" in endpoint:
                    complete_config['mcpServers']['ipfs-kit-mcp']['tools'].append({
                        "name": f"{backend_name}_from_ipfs",
                        "description": f"Transfer content from IPFS to {backend_name}",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "cid": {
                                    "type": "string",
                                    "description": "Content identifier (CID) in IPFS"
                                },
                                "path": {
                                    "type": "string",
                                    "description": f"Destination path in {backend_name}"
                                }
                            },
                            "required": ["cid", "path"]
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "success": {
                                    "type": "boolean",
                                    "description": "Whether the transfer was successful"
                                },
                                "path": {
                                    "type": "string",
                                    "description": f"Path to the content in {backend_name}"
                                }
                            }
                        }
                    })

    try:
        # Write the configuration to the file, completely replacing the existing content
        with open(settings_path, 'w') as f:
            json.dump(complete_config, f, indent=2)

        logger.info(f"Wrote complete MCP configuration to {settings_path}")
        return True
    except Exception as e:
        logger.error(f"Error writing MCP configuration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function."""
    logger.info("Creating complete MCP configuration...")

    if create_complete_mcp_config():
        logger.info("Successfully created complete MCP configuration")
        print("✅ Complete MCP configuration created successfully!")
        print("Please reload the VSCode window or restart the server to apply changes.")
        sys.exit(0)
    else:
        logger.error("Failed to create complete MCP configuration")
        print("❌ Failed to create complete MCP configuration. Check the logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
