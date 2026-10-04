#!/usr/bin/env python3
"""
Add additional IPFS tools to the registry to increase MCP tool coverage.
"""

import os
import re
import json
import logging
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Define all the new tool schemas
NEW_TOOLS = [
    # FS Journal Tools
    {
        "name": "fs_journal_get_history",
        "description": "Get the operation history for a path in the virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to get history for"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of history entries to return",
                    "default": 10
                },
                "operation_types": {
                    "type": "array",
                    "description": "Filter by operation types (read, write, etc.)",
                    "items": {
                        "type": "string"
                    }
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "fs_journal_sync",
        "description": "Force synchronization between virtual filesystem and actual storage",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to sync (defaults to entire filesystem)",
                    "default": "/"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to sync recursively",
                    "default": True
                }
            }
        }
    },
    
    # IPFS Bridge Tools
    {
        "name": "ipfs_fs_bridge_status",
        "description": "Get the status of the IPFS-FS bridge",
        "schema": {
            "type": "object",
            "properties": {
                "detailed": {
                    "type": "boolean",
                    "description": "Whether to include detailed information",
                    "default": False
                }
            }
        }
    },
    {
        "name": "ipfs_fs_bridge_sync",
        "description": "Sync between IPFS and virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to sync",
                    "default": "/"
                },
                "direction": {
                    "type": "string",
                    "description": "Sync direction: to_ipfs, from_ipfs, or both",
                    "enum": ["to_ipfs", "from_ipfs", "both"],
                    "default": "both"
                }
            }
        }
    },
    
    # S3 Storage Tools
    {
        "name": "s3_store_file",
        "description": "Store a file to S3 storage",
        "schema": {
            "type": "object",
            "properties": {
                "local_path": {
                    "type": "string",
                    "description": "Local path of the file to store"
                },
                "bucket": {
                    "type": "string",
                    "description": "S3 bucket name"
                },
                "key": {
                    "type": "string",
                    "description": "S3 object key"
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata for the object"
                }
            },
            "required": ["local_path", "bucket", "key"]
        }
    },
    {
        "name": "s3_retrieve_file",
        "description": "Retrieve a file from S3 storage",
        "schema": {
            "type": "object",
            "properties": {
                "local_path": {
                    "type": "string",
                    "description": "Local path to save the file"
                },
                "bucket": {
                    "type": "string",
                    "description": "S3 bucket name"
                },
                "key": {
                    "type": "string",
                    "description": "S3 object key"
                }
            },
            "required": ["local_path", "bucket", "key"]
        }
    },
    
    # Filecoin Storage Tools
    {
        "name": "filecoin_store_file",
        "description": "Store a file to Filecoin storage",
        "schema": {
            "type": "object",
            "properties": {
                "local_path": {
                    "type": "string",
                    "description": "Local path of the file to store"
                },
                "replication": {
                    "type": "integer",
                    "description": "Number of replicas to store",
                    "default": 1
                },
                "duration": {
                    "type": "integer",
                    "description": "Storage duration in days",
                    "default": 180
                }
            },
            "required": ["local_path"]
        }
    },
    {
        "name": "filecoin_retrieve_deal",
        "description": "Retrieve a file from Filecoin storage by deal ID",
        "schema": {
            "type": "object",
            "properties": {
                "deal_id": {
                    "type": "string",
                    "description": "Filecoin deal ID"
                },
                "local_path": {
                    "type": "string",
                    "description": "Local path to save the file"
                }
            },
            "required": ["deal_id", "local_path"]
        }
    },
    
    # HuggingFace Integration Tools
    {
        "name": "huggingface_model_load",
        "description": "Load a model from HuggingFace",
        "schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "HuggingFace model ID"
                },
                "task": {
                    "type": "string",
                    "description": "Task type (translation, summarization, etc.)",
                    "default": "text-generation"
                },
                "cache_dir": {
                    "type": "string",
                    "description": "Directory to cache the model"
                }
            },
            "required": ["model_id"]
        }
    },
    {
        "name": "huggingface_model_inference",
        "description": "Run inference on a loaded HuggingFace model",
        "schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "HuggingFace model ID"
                },
                "input_text": {
                    "type": "string",
                    "description": "Input text for the model"
                },
                "parameters": {
                    "type": "object",
                    "description": "Additional parameters for the model"
                }
            },
            "required": ["model_id", "input_text"]
        }
    },
    
    # WebRTC Tools
    {
        "name": "webrtc_peer_connect",
        "description": "Connect to another peer via WebRTC",
        "schema": {
            "type": "object",
            "properties": {
                "peer_id": {
                    "type": "string",
                    "description": "ID of the peer to connect to"
                },
                "signaling_server": {
                    "type": "string",
                    "description": "Signaling server URL",
                    "default": "wss://signaling.ipfs.io"
                },
                "ice_servers": {
                    "type": "array",
                    "description": "STUN/TURN servers to use",
                    "items": {
                        "type": "string"
                    }
                }
            },
            "required": ["peer_id"]
        }
    },
    {
        "name": "webrtc_send_data",
        "description": "Send data to a connected WebRTC peer",
        "schema": {
            "type": "object",
            "properties": {
                "peer_id": {
                    "type": "string",
                    "description": "ID of the peer to send data to"
                },
                "data": {
                    "type": "string",
                    "description": "Data to send to the peer"
                },
                "data_type": {
                    "type": "string",
                    "description": "Type of data being sent",
                    "enum": ["text", "binary", "json"],
                    "default": "text"
                }
            },
            "required": ["peer_id", "data"]
        }
    },
    
    # Credential Management Tools
    {
        "name": "credential_store",
        "description": "Store a credential for a specific service",
        "schema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service the credential is for"
                },
                "credential_type": {
                    "type": "string",
                    "description": "Type of credential",
                    "enum": ["api_key", "oauth_token", "username_password", "jwt", "other"],
                    "default": "api_key"
                },
                "credential_data": {
                    "type": "object",
                    "description": "Credential data"
                },
                "expires_at": {
                    "type": "string",
                    "description": "ISO8601 timestamp when the credential expires (optional)"
                }
            },
            "required": ["service", "credential_data"]
        }
    },
    {
        "name": "credential_retrieve",
        "description": "Retrieve a credential for a specific service",
        "schema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service to retrieve credential for"
                },
                "credential_type": {
                    "type": "string",
                    "description": "Type of credential to retrieve",
                    "enum": ["api_key", "oauth_token", "username_password", "jwt", "other"],
                    "default": "api_key"
                }
            },
            "required": ["service"]
        }
    }
]

def update_ipfs_tools_registry(tools, registry_path="ipfs_tools_registry.py"):
    """Update the IPFS tools registry with new tools"""
    try:
        # Check if the registry file exists
        if not os.path.exists(registry_path):
            logger.info(f"Creating new registry file: {registry_path}")
            # Create the registry file with the new tools
            with open(registry_path, "w") as f:
                f.write("""\"\"\"IPFS MCP Tools Registry - Generated by add_new_ipfs_tools.py\"\"\"

def get_ipfs_tools():
    \"\"\"Get all IPFS tool definitions\"\"\"
    return IPFS_TOOLS

IPFS_TOOLS = [
]
""")
        
        # Read the current registry
        with open(registry_path, 'r') as f:
            content = f.read()
        
        # Find the end of the IPFS_TOOLS list
        match = re.search(r'IPFS_TOOLS\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if not match:
            logger.error(f"❌ Could not find IPFS_TOOLS list in {registry_path}")
            return False
        
        # Get the current list content
        current_list = match.group(1)
        
        # Format the new tools to add
        new_tools_str = ""
        for tool in tools:
            new_tools_str += f"""
    {{
        "name": "{tool['name']}",
        "description": "{tool['description']}",
        "schema": {json.dumps(tool['schema'], indent=4).replace('"True"', 'True').replace('"False"', 'False')}
    }},"""
        
        # Replace the list with the updated one
        updated_list = current_list + new_tools_str
        updated_content = content.replace(match.group(1), updated_list)
        
        # Write the updated content
        with open(registry_path, 'w') as f:
            f.write(updated_content)
        
        logger.info(f"✅ Added {len(tools)} new tools to {registry_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error updating IPFS tools registry: {e}")
        return False

def main():
    """Main function"""
    # Update the IPFS tools registry
    update_ipfs_tools_registry(NEW_TOOLS)
    
    logger.info("✅ Tool coverage has been improved")
    logger.info("ℹ️ Next steps:")
    logger.info("   1. Create implementation handlers for the new tools")
    logger.info("   2. Update the MCP server to use the new tools")
    logger.info("   3. Test the new tools")

if __name__ == "__main__":
    main()
