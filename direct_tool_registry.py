#!/usr/bin/env python3
"""
Direct Tool Registry for IPFS Kit MCP

This script provides a direct definition of IPFS tools for the MCP server,
avoiding any issues with importing existing registries.
"""

import json
import os
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_tool_registry():
    """Create a direct registry of IPFS tools for MCP"""
    tools = [
        # Core IPFS features
        {
            "name": "ipfs_add",
            "description": "Add content to IPFS",
            "schema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to add to IPFS"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional filename for the content"
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
            "schema": {
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
            "name": "ipfs_ls",
            "description": "List directory contents in IPFS",
            "schema": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "CID of the directory to list"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list recursively",
                        "default": False
                    }
                },
                "required": ["cid"]
            }
        },
        
        # MFS (Mutable File System) operations
        {
            "name": "ipfs_files_ls",
            "description": "List files in the MFS",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to list",
                        "default": "/"
                    },
                    "long": {
                        "type": "boolean",
                        "description": "Whether to use long listing format",
                        "default": False
                    }
                }
            }
        },
        {
            "name": "ipfs_files_mkdir",
            "description": "Create a directory in the MFS",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to create"
                    },
                    "parents": {
                        "type": "boolean",
                        "description": "Whether to create parent directories",
                        "default": True
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "ipfs_files_write",
            "description": "Write to a file in the MFS",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to write to"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
                    },
                    "create": {
                        "type": "boolean",
                        "description": "Whether to create the file if it doesn't exist",
                        "default": True
                    },
                    "truncate": {
                        "type": "boolean",
                        "description": "Whether to truncate the file",
                        "default": True
                    }
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "ipfs_files_read",
            "description": "Read a file from the MFS",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to read"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset to start reading from",
                        "default": 0
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of bytes to read",
                        "default": -1
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "ipfs_files_rm",
            "description": "Remove a file or directory from the MFS",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to remove"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to remove recursively",
                        "default": False
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "ipfs_files_stat",
            "description": "Get stats for a file or directory in the MFS",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to get stats for"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "ipfs_files_cp",
            "description": "Copy files in the MFS",
            "schema": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Source path in the MFS"
                    },
                    "dest": {
                        "type": "string",
                        "description": "Destination path in the MFS"
                    }
                },
                "required": ["source", "dest"]
            }
        },
        {
            "name": "ipfs_files_mv",
            "description": "Move files in the MFS",
            "schema": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Source path in the MFS"
                    },
                    "dest": {
                        "type": "string",
                        "description": "Destination path in the MFS"
                    }
                },
                "required": ["source", "dest"]
            }
        },
        {
            "name": "ipfs_files_flush",
            "description": "Flush the MFS",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path in the MFS to flush",
                        "default": "/"
                    }
                }
            }
        },
        
        # Advanced IPFS features
        {
            "name": "ipfs_pubsub_publish",
            "description": "Publish a message to a pubsub topic",
            "schema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to publish to"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message to publish"
                    }
                },
                "required": ["topic", "message"]
            }
        },
        {
            "name": "ipfs_pubsub_subscribe",
            "description": "Subscribe to messages on a pubsub topic",
            "schema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to subscribe to"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 10
                    }
                },
                "required": ["topic"]
            }
        },
        {
            "name": "ipfs_dht_findpeer",
            "description": "Find a peer in the DHT",
            "schema": {
                "type": "object",
                "properties": {
                    "peer_id": {
                        "type": "string",
                        "description": "Peer ID to find"
                    }
                },
                "required": ["peer_id"]
            }
        },
        {
            "name": "ipfs_dht_findprovs",
            "description": "Find providers for a CID in the DHT",
            "schema": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "CID to find providers for"
                    },
                    "num_providers": {
                        "type": "integer",
                        "description": "Number of providers to find",
                        "default": 20
                    }
                },
                "required": ["cid"]
            }
        },
        
        # Multi-backend tools
        {
            "name": "fs_journal_get_history",
            "description": "Get the operation history for a path in the virtual filesystem",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to get history for",
                        "default": None
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of operations to return",
                        "default": 100
                    }
                },
                "required": ["ctx"]
            }
        },
        {
            "name": "fs_journal_sync",
            "description": "Force synchronization between virtual filesystem and actual storage",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to synchronize",
                        "default": None
                    }
                },
                "required": ["ctx"]
            }
        },
        {
            "name": "ipfs_fs_bridge_status",
            "description": "Get the status of the IPFS-FS bridge",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    }
                },
                "required": ["ctx"]
            }
        },
        {
            "name": "ipfs_fs_bridge_sync",
            "description": "Sync between IPFS and virtual filesystem",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "direction": {
                        "type": "string",
                        "description": "Direction of synchronization (ipfs_to_fs, fs_to_ipfs, or both)",
                        "default": "both"
                    }
                },
                "required": ["ctx"]
            }
        },
        
        # Storage backend tools
        {
            "name": "init_huggingface_backend",
            "description": "Initialize HuggingFace backend for the virtual filesystem",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name for the backend",
                        "default": "huggingface"
                    },
                    "root_path": {
                        "type": "string",
                        "description": "Root path for the backend",
                        "default": "/hf"
                    }
                },
                "required": ["ctx"]
            }
        },
        {
            "name": "init_filecoin_backend",
            "description": "Initialize Filecoin backend for the virtual filesystem",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name for the backend",
                        "default": "filecoin"
                    },
                    "root_path": {
                        "type": "string",
                        "description": "Root path for the backend",
                        "default": "/fil"
                    }
                },
                "required": ["ctx"]
            }
        },
        {
            "name": "init_s3_backend",
            "description": "Initialize S3 backend for the virtual filesystem",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name for the backend",
                        "default": "s3"
                    },
                    "root_path": {
                        "type": "string",
                        "description": "Root path for the backend",
                        "default": "/s3"
                    },
                    "bucket": {
                        "type": "string",
                        "description": "S3 bucket to use",
                        "default": None
                    }
                },
                "required": ["ctx"]
            }
        },
        {
            "name": "init_storacha_backend",
            "description": "Initialize Storacha backend for the virtual filesystem",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name for the backend",
                        "default": "storacha"
                    },
                    "root_path": {
                        "type": "string",
                        "description": "Root path for the backend",
                        "default": "/storacha"
                    }
                },
                "required": ["ctx"]
            }
        },
        {
            "name": "init_ipfs_cluster_backend",
            "description": "Initialize IPFS Cluster backend for the virtual filesystem",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name for the backend",
                        "default": "ipfs_cluster"
                    },
                    "root_path": {
                        "type": "string",
                        "description": "Root path for the backend",
                        "default": "/ipfs_cluster"
                    }
                },
                "required": ["ctx"]
            }
        },
        
        # Multi-backend management tools
        {
            "name": "multi_backend_map",
            "description": "Map a backend path to a local filesystem path",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "backend_path": {
                        "type": "string",
                        "description": "Path in the backend"
                    },
                    "local_path": {
                        "type": "string",
                        "description": "Path in the local filesystem"
                    }
                },
                "required": ["ctx", "backend_path", "local_path"]
            }
        },
        {
            "name": "multi_backend_unmap",
            "description": "Remove a mapping between backend and local filesystem",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "backend_path": {
                        "type": "string",
                        "description": "Path in the backend"
                    }
                },
                "required": ["ctx", "backend_path"]
            }
        },
        {
            "name": "multi_backend_list_mappings",
            "description": "List all mappings between backends and local filesystem",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    }
                },
                "required": ["ctx"]
            }
        },
        {
            "name": "multi_backend_status",
            "description": "Get status of the multi-backend filesystem",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    }
                },
                "required": ["ctx"]
            }
        },
        {
            "name": "multi_backend_sync",
            "description": "Synchronize all mapped paths",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    }
                },
                "required": ["ctx"]
            }
        },
        {
            "name": "multi_backend_search",
            "description": "Search indexed content",
            "schema": {
                "type": "object",
                "properties": {
                    "ctx": {
                        "type": "string",
                        "description": "Context for the operation"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 100
                    }
                },
                "required": ["ctx", "query"]
            }
        }
    ]
    
    return tools

def register_tools():
    """Register tools with the MCP server by writing them to a file"""
    try:
        tools = create_tool_registry()
        
        # Write tools to a file that will be loaded by the MCP server
        with open("mcp_registered_tools.json", "w") as f:
            json.dump(tools, f, indent=2)
            
        logger.info(f"✅ Successfully registered {len(tools)} tools with MCP server")
        return True
    except Exception as e:
        logger.error(f"Error registering tools: {e}")
        return False

if __name__ == "__main__":
    register_tools()
