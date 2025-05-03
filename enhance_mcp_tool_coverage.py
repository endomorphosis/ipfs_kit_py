#!/usr/bin/env python3
"""
Add additional MCP tools to increase coverage of IPFS Kit features.
This script adds virtual filesystem, additional storage backends, 
WebRTC, and credential management tools.
"""

import os
import re
import sys
import json
import logging
import argparse
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Tool definitions for new MCP tools
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

def update_ipfs_tools_registry(tools: List[Dict[str, Any]]) -> bool:
    """Update the IPFS tools registry with new tools"""
    registry_path = "ipfs_tools_registry.py"
    
    try:
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

def create_tool_handlers() -> bool:
    """Create the enhanced_mcp_tools.py file with handlers for all new tools"""
    try:
        # Create the file with all the necessary tool implementations
        with open("enhanced_mcp_tools.py", "w") as f:
            f.write("""#!/usr/bin/env python3
"""
Enhanced MCP Tools Integration

This module provides implementations for the enhanced MCP tools that expose
additional IPFS Kit features like virtual filesystem, additional storage backends,
WebRTC, and credential management.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Try to import the required modules
try:
    from ipfs_kit_py.mcp.fs.fs_journal import FSJournal, VirtualFS, FSOperation, FSOperationType
    from ipfs_kit_py.mcp.fs.fs_ipfs_bridge import IPFSFSBridge
    FS_MODULES_AVAILABLE = True
except ImportError:
    logger.warning("FS Journal modules not available, some functionality will be limited.")
    FS_MODULES_AVAILABLE = False

try:
    from ipfs_kit_py.mcp.controllers.storage.s3_controller import S3Controller
    S3_AVAILABLE = True
except ImportError:
    logger.warning("S3 controller not available, S3 functionality will be limited.")
    S3_AVAILABLE = False

try:
    from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
    FILECOIN_AVAILABLE = True
except ImportError:
    logger.warning("Filecoin controller not available, Filecoin functionality will be limited.")
    FILECOIN_AVAILABLE = False

try:
    from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    logger.warning("HuggingFace controller not available, HuggingFace functionality will be limited.")
    HUGGINGFACE_AVAILABLE = False

try:
    from ipfs_kit_py.mcp.controllers.webrtc_controller import WebRTCController
    WEBRTC_AVAILABLE = True
except ImportError:
    logger.warning("WebRTC controller not available, WebRTC functionality will be limited.")
    WEBRTC_AVAILABLE = False

try:
    from ipfs_kit_py.mcp.controllers.credential_controller import CredentialController
    CREDENTIAL_AVAILABLE = True
except ImportError:
    logger.warning("Credential controller not available, credential functionality will be limited.")
    CREDENTIAL_AVAILABLE = False

# Initialize global instances (will be set on register_enhanced_tools call)
fs_journal = None
fs_bridge = None
s3_controller = None
filecoin_controller = None
huggingface_controller = None
webrtc_controller = None
credential_controller = None

def register_enhanced_tools(mcp_server):
    """Register all enhanced tools with the MCP server"""
    global fs_journal, fs_bridge, s3_controller, filecoin_controller, huggingface_controller, webrtc_controller, credential_controller
    
    # Initialize fs_journal and fs_bridge
    if FS_MODULES_AVAILABLE:
        fs_journal = FSJournal()
        fs_bridge = IPFSFSBridge(fs_journal)
    
    # Initialize controllers for other components
    if S3_AVAILABLE:
        s3_controller = S3Controller()
    
    if FILECOIN_AVAILABLE:
        filecoin_controller = FilecoinController()
    
    if HUGGINGFACE_AVAILABLE:
        huggingface_controller = HuggingFaceController()
    
    if WEBRTC_AVAILABLE:
        webrtc_controller = WebRTCController()
    
    if CREDENTIAL_AVAILABLE:
        credential_controller = CredentialController()
    
    logger.info("Registering enhanced MCP tools...")

    # FS Journal Tools
    @mcp_server.tool(name="fs_journal_get_history", description="Get the operation history for a path in the virtual filesystem")
    async def fs_journal_get_history(ctx):
        params = ctx.params
        path = params.get("path", "/")
        limit = params.get("limit", 10)
        operation_types = params.get("operation_types", None)
        
        if not FS_MODULES_AVAILABLE:
            return {"success": False, "error": "FS Journal modules not available"}
        
        try:
            # Convert operation_types strings to enum values if provided
            op_types = None
            if operation_types:
                op_types = [FSOperationType(op_type) for op_type in operation_types]
            
            history = fs_journal.get_history(path, limit=limit, operation_types=op_types)
            
            # Convert history objects to dictionaries
            history_dicts = [op.to_dict() for op in history]
            
            return {
                "success": True,
                "history": history_dicts,
                "path": path,
                "count": len(history_dicts)
            }
        except Exception as e:
            logger.error(f"Error getting FS journal history: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool(name="fs_journal_sync", description="Force synchronization between virtual filesystem and actual storage")
    async def fs_journal_sync(ctx):
        params = ctx.params
        path = params.get("path", "/")
        recursive = params.get("recursive", True)
        
        if not FS_MODULES_AVAILABLE:
            return {"success": False, "error": "FS Journal modules not available"}
        
        try:
            fs_journal.sync(path, recursive=recursive)
            return {
                "success": True,
                "message": f"Successfully synced {path}",
                "recursive": recursive
            }
        except Exception as e:
            logger.error(f"Error syncing FS journal: {e}")
            return {"success": False, "error": str(e)}

    # IPFS Bridge Tools
    @mcp_server.tool(name="ipfs_fs_bridge_status", description="Get the status of the IPFS-FS bridge")
    async def ipfs_fs_bridge_status(ctx):
        params = ctx.params
        detailed = params.get("detailed", False)
        
        if not FS_MODULES_AVAILABLE:
            return {"success": False, "error": "FS Bridge modules not available"}
        
        try:
            status = fs_bridge.get_status(detailed=detailed)
            return {
                "success": True,
                "status": status
            }
        except Exception as e:
            logger.error(f"Error getting IPFS-FS bridge status: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool(name="ipfs_fs_bridge_sync", description="Sync between IPFS and virtual filesystem")
    async def ipfs_fs_bridge_sync(ctx):
        params = ctx.params
        path = params.get("path", "/")
        direction = params.get("direction", "both")
        
        if not FS_MODULES_AVAILABLE:
            return {"success": False, "error": "FS Bridge modules not available"}
        
        try:
            result = fs_bridge.sync(path, direction=direction)
            return {
                "success": True,
                "path": path,
                "direction": direction,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error syncing IPFS-FS bridge: {e}")
            return {"success": False, "error": str(e)}

    # S3 Storage Tools
    @mcp_server.tool(name="s3_store_file", description="Store a file to S3 storage")
    async def s3_store_file(ctx):
        params = ctx.params
        local_path = params.get("local_path")
        bucket = params.get("bucket")
        key = params.get("key")
        metadata = params.get("metadata", {})
        
        if not S3_AVAILABLE:
            return {"success": False, "error": "S3 controller not available"}
        
        try:
            result = await s3_controller.store_file(local_path, bucket, key, metadata)
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error storing file to S3: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool(name="s3_retrieve_file", description="Retrieve a file from S3 storage")
    async def s3_retrieve_file(ctx):
        params = ctx.params
        local_path = params.get("local_path")
        bucket = params.get("bucket")
        key = params.get("key")
        
        if not S3_AVAILABLE:
            return {"success": False, "error": "S3 controller not available"}
        
        try:
            result = await s3_controller.retrieve_file(bucket, key, local_path)
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error retrieving file from S3: {e}")
            return {"success": False, "error": str(e)}

    # Filecoin Storage Tools
    @mcp_server.tool(name="filecoin_store_file", description="Store a file to Filecoin storage")
    async def filecoin_store_file(ctx):
        params = ctx.params
        local_path = params.get("local_path")
        replication = params.get("replication", 1)
        duration = params.get("duration", 180)
        
        if not FILECOIN_AVAILABLE:
            return {"success": False, "error": "Filecoin controller not available"}
        
        try:
            result = await filecoin_controller.store_file(local_path, replication, duration)
            return {
                "success": True,
                "deal_id": result.get("deal_id"),
                "status": result.get("status")
            }
        except Exception as e:
            logger.error(f"Error storing file to Filecoin: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool(name="filecoin_retrieve_deal", description="Retrieve a file from Filecoin storage by deal ID")
    async def filecoin_retrieve_deal(ctx):
        params = ctx.params
        deal_id = params.get("deal_id")
        local_path = params.get("local_path")
        
        if not FILECOIN_AVAILABLE:
            return {"success": False, "error": "Filecoin controller not available"}
        
        try:
            result = await filecoin_controller.retrieve_deal(deal_id, local_path)
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error retrieving file from Filecoin: {e}")
            return {"success": False, "error": str(e)}

    # HuggingFace Integration Tools
    @mcp_server.tool(name="huggingface_model_load", description="Load a model from HuggingFace")
    async def huggingface_model_load(ctx):
        params = ctx.params
        model_id = params.get("model_id")
        task = params.get("task", "text-generation")
        cache_dir = params.get("cache_dir")
        
        if not HUGGINGFACE_AVAILABLE:
            return {"success": False, "error": "HuggingFace controller not available"}
        
        try:
            result = await huggingface_controller.load_model(model_id, task, cache_dir)
            return {
                "success": True,
                "model_id": model_id,
                "task": task,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error loading HuggingFace model: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool(name="huggingface_model_inference", description="Run inference on a loaded HuggingFace model")
    async def huggingface_model_inference(ctx):
        params = ctx.params
        model_id = params.get("model_id")
        input_text = params.get("input_text")
        parameters = params.get("parameters", {})
        
        if not HUGGINGFACE_AVAILABLE:
            return {"success": False, "error": "HuggingFace controller not available"}
        
        try:
            result = await huggingface_controller.run_inference(model_id, input_text, parameters)
            return {
                "success": True,
                "model_id": model_id,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error running HuggingFace inference: {e}")
            return {"success": False, "error": str(e)}

    # WebRTC Tools
    @mcp_server.tool(name="webrtc_peer_connect", description="Connect to another peer via WebRTC")
    async def webrtc_peer_connect(ctx):
        params = ctx.params
        peer_id = params.get("peer_id")
        signaling_server = params.get("signaling_server", "wss://signaling.ipfs.io")
        ice_servers = params.get("ice_servers", [])
        
        if not WEBRTC_AVAILABLE:
            return {"success": False, "error": "WebRTC controller not available"}
        
        try:
            connection = await webrtc_controller.connect_to_peer(peer_id, signaling_server, ice_servers)
            return {
                "success": True,
                "peer_id": peer_id,
                "connection_id": connection.id,
                "status": connection.status
            }
        except Exception as e:
            logger.error(f"Error connecting to WebRTC peer: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool(name="webrtc_send_data", description="Send data to a connected WebRTC peer")
    async def webrtc_send_data(ctx):
        params = ctx.params
        peer_id = params.get("peer_id")
        data = params.get("data")
        data_type = params.get("data_type", "text")
        
        if not WEBRTC_AVAILABLE:
            return {"success": False, "error": "WebRTC controller not available"}
        
        try:
            result = await webrtc_controller.send_data(peer_id, data, data_type)
            return {
                "success": True,
                "peer_id": peer_id,
                "bytes_sent": result.get("bytes_sent"),
                "status": result.get("status")
            }
        except Exception as e:
            logger.error(f"Error sending data to WebRTC peer: {e}")
            return {"success": False, "error": str(e)}

    # Credential Management Tools
    @mcp_server.tool(name="credential_store", description="Store a credential for a specific service")
    async def credential_store(ctx):
        params = ctx.params
        service = params.get("service")
        credential_type = params.get("credential_type", "api_key")
        credential_data = params.get("credential_data")
        expires_at = params.get("expires_at")
        
        if not CREDENTIAL_AVAILABLE:
            return {"success": False, "error": "Credential controller not available"}
        
        try:
            result = await credential_controller.store_credential(service, credential_type, credential_data, expires_at)
            return {
                "success": True,
                "service": service,
                "credential_id": result.get("credential_id"),
                "status": "stored"
            }
        except Exception as e:
            logger.error(f"Error storing credential: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool(name="credential_retrieve", description="Retrieve a credential for a specific service")
    async def credential_retrieve(ctx):
        params = ctx.params
        service = params.get("service")
        credential_type = params.get("credential_type", "api_key")
        
        if not CREDENTIAL_AVAILABLE:
            return {"success": False, "error": "Credential controller not available"}
        
        try:
            credential = await credential_controller.retrieve_credential(service, credential_type)
            return {
                "success": True,
                "service": service,
                "credential": credential
            }
        except Exception as e:
            logger.error(f"Error retrieving credential: {e}")
            return {"success": False, "error": str(e)}
    
    logger.info("✅ Successfully registered all enhanced MCP tools")
    return True
""")
        logger.info("✅ Created enhanced_mcp_tools.py with all tool handlers")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating tool handlers: {e}")
        return False

def create_integration_script() -> bool:
    """Create a script to integrate the new tools with direct_mcp_server.py"""
    try:
        integration_script = "integrate_enhanced_tools.py"
        with open(integration_script, "w") as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Integrate enhanced IPFS tools with the MCP server
\"\"\"

import os
import sys
import logging
import importlib
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def add_import_statement(file_path, import_statement):
    \"\"\"Add an import statement to a Python file\"\"\"
    try:
        with open(file_path, "r") as f:
            content = f.read()
        
        # Check if import already exists
        if import_statement in content:
            logger.info(f"Import statement already exists in {file_path}")
            return True
        
        # Find the last import statement
        import_pattern = r"^import .*$|^from .* import .*$"
        matches = list(re.finditer(import_pattern, content, re.MULTILINE))
        
        if not matches:
            logger.error(f"No import statements found in {file_path}")
            return False
        
        last_import = matches[-1]
        last_import_end = last_import.end()
        
        # Insert the new import after the last import
        updated_content = content[:last_import_end] + "\\n" + import_statement + content[last_import_end:]
