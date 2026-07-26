#!/usr/bin/env python3
"""
IPFS Core Operations - Part 2

Continuing with Node Operations, Content Operations, and DAG Operations.
"""

import requests
import json
import logging
import os
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

# Import core components
import sys
sys.path.append(str(Path(__file__).parent.parent))

from core.tool_registry import tool, ToolCategory
from core.error_handler import create_success_response, create_ipfs_error, ErrorContext
from core.service_manager import ipfs_manager

# Setup logging
logger = logging.getLogger(__name__)

# IPFS API base URL
IPFS_API_BASE = "http://127.0.0.1:5001/api/v0"

class IPFSClient:
    """IPFS API client for core operations"""
    
    def __init__(self, api_url: str = IPFS_API_BASE):
        self.api_url = api_url
        
    def _make_request(self, endpoint: str, method: str = "POST", 
                     params: Optional[Dict] = None, 
                     files: Optional[Dict] = None,
                     data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to IPFS API"""
        try:
            url = f"{self.api_url}/{endpoint}"
            
            if method == "GET":
                response = requests.get(url, params=params, timeout=30)
            else:
                response = requests.post(url, params=params, files=files, data=data, timeout=30)
            
            response.raise_for_status()
            
            # Handle different response types
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                return response.json()
            else:
                return {"content": response.text, "binary": response.content}
                
        except requests.exceptions.ConnectionError:
            raise Exception("IPFS daemon not running or not accessible")
        except requests.exceptions.Timeout:
            raise Exception("IPFS API request timed out")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"IPFS API error: {e}")
        except Exception as e:
            raise Exception(f"IPFS API request failed: {e}")

# Global IPFS client
ipfs_client = IPFSClient()

# ============================================================================
# NODE OPERATIONS
# ============================================================================

@tool(
    name="ipfs_id",
    category="ipfs_core",
    description="Get IPFS node identity information",
    parameters={
        "peer_id": {
            "type": "string",
            "description": "Peer ID to get info for (optional, defaults to local node)",
            "required": False
        }
    },
    returns={
        "id": {"type": "string", "description": "Peer ID"},
        "public_key": {"type": "string", "description": "Public key"},
        "addresses": {"type": "array", "description": "Multiaddresses"},
        "agent_version": {"type": "string", "description": "Agent version"},
        "protocol_version": {"type": "string", "description": "Protocol version"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_id(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get IPFS node identity information"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        peer_id = params.get("peer_id")
        
        # Prepare parameters
        api_params = {}
        if peer_id:
            api_params["arg"] = peer_id
        
        result = ipfs_client._make_request("id", params=api_params)
        
        return create_success_response({
            "id": result.get("ID"),
            "public_key": result.get("PublicKey"),
            "addresses": result.get("Addresses", []),
            "agent_version": result.get("AgentVersion"),
            "protocol_version": result.get("ProtocolVersion")
        })
        
    except Exception as e:
        logger.error(f"IPFS id failed: {e}")
        error = create_ipfs_error(str(e), "id")
        return error.to_dict()

@tool(
    name="ipfs_version",
    category="ipfs_core",
    description="Get IPFS version information",
    parameters={
        "number": {
            "type": "boolean",
            "description": "Only show the version number",
            "default": False
        },
        "commit": {
            "type": "boolean", 
            "description": "Show the commit hash",
            "default": False
        },
        "repo": {
            "type": "boolean",
            "description": "Show repo version",
            "default": False
        },
        "all": {
            "type": "boolean",
            "description": "Show all version information",
            "default": False
        }
    },
    returns={
        "version": {"type": "string", "description": "IPFS version"},
        "commit": {"type": "string", "description": "Git commit hash"},
        "repo": {"type": "string", "description": "Repository version"},
        "system": {"type": "string", "description": "System information"},
        "golang": {"type": "string", "description": "Go version"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_version(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get IPFS version information"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        number = params.get("number", False)
        commit = params.get("commit", False)
        repo = params.get("repo", False)
        all_info = params.get("all", False)
        
        # Prepare parameters
        api_params = {}
        if number:
            api_params["number"] = "true"
        if commit:
            api_params["commit"] = "true"
        if repo:
            api_params["repo"] = "true"
        if all_info:
            api_params["all"] = "true"
        
        result = ipfs_client._make_request("version", params=api_params)
        
        return create_success_response({
            "version": result.get("Version"),
            "commit": result.get("Commit"),
            "repo": result.get("Repo"),
            "system": result.get("System"),
            "golang": result.get("Golang")
        })
        
    except Exception as e:
        logger.error(f"IPFS version failed: {e}")
        error = create_ipfs_error(str(e), "version")
        return error.to_dict()

@tool(
    name="ipfs_stats",
    category="ipfs_core",
    description="Get IPFS node statistics",
    parameters={
        "human": {
            "type": "boolean",
            "description": "Print sizes in human readable format",
            "default": False
        }
    },
    returns={
        "repo_size": {"type": "integer", "description": "Repository size in bytes"},
        "storage_max": {"type": "integer", "description": "Maximum storage"},
        "num_objects": {"type": "integer", "description": "Number of objects"},
        "repo_path": {"type": "string", "description": "Repository path"},
        "version": {"type": "string", "description": "Repository version"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_stats(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get IPFS node statistics"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        human = params.get("human", False)
        
        # Prepare parameters
        api_params = {}
        if human:
            api_params["human"] = "true"
        
        result = ipfs_client._make_request("stats/repo", params=api_params)
        
        return create_success_response({
            "repo_size": result.get("RepoSize"),
            "storage_max": result.get("StorageMax"),
            "num_objects": result.get("NumObjects"),
            "repo_path": result.get("RepoPath"),
            "version": result.get("Version")
        })
        
    except Exception as e:
        logger.error(f"IPFS stats failed: {e}")
        error = create_ipfs_error(str(e), "stats")
        return error.to_dict()

@tool(
    name="ipfs_swarm_peers",
    category="ipfs_core", 
    description="List peers connected to this IPFS node",
    parameters={
        "verbose": {
            "type": "boolean",
            "description": "Display extra information",
            "default": False
        },
        "streams": {
            "type": "boolean",
            "description": "Also list information about streams",
            "default": False
        },
        "latency": {
            "type": "boolean",
            "description": "Also list information about latency",
            "default": False
        }
    },
    returns={
        "peers": {"type": "array", "description": "List of connected peers"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_swarm_peers(params: Dict[str, Any]) -> Dict[str, Any]:
    """List peers connected to this IPFS node"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        verbose = params.get("verbose", False)
        streams = params.get("streams", False)
        latency = params.get("latency", False)
        
        # Prepare parameters
        api_params = {}
        if verbose:
            api_params["verbose"] = "true"
        if streams:
            api_params["streams"] = "true"
        if latency:
            api_params["latency"] = "true"
        
        result = ipfs_client._make_request("swarm/peers", params=api_params)
        
        # Parse result
        peers = []
        if isinstance(result, dict):
            peers_data = result.get("Peers", [])
            peers = [
                {
                    "peer": peer.get("Peer"),
                    "addr": peer.get("Addr"),
                    "direction": peer.get("Direction"),
                    "latency": peer.get("Latency"),
                    "muxer": peer.get("Muxer"),
                    "streams": peer.get("Streams", [])
                }
                for peer in peers_data
            ]
        
        return create_success_response({
            "peers": peers
        })
        
    except Exception as e:
        logger.error(f"IPFS swarm peers failed: {e}")
        error = create_ipfs_error(str(e), "swarm/peers")
        return error.to_dict()

# ============================================================================
# CONTENT OPERATIONS
# ============================================================================

@tool(
    name="ipfs_refs",
    category="ipfs_core",
    description="List object references from IPFS content",
    parameters={
        "cid": {
            "type": "string",
            "description": "Content identifier to get references from"
        },
        "format": {
            "type": "string",
            "description": "Output format for references",
            "default": "<dst>"
        },
        "edges": {
            "type": "boolean",
            "description": "Output edge format: <src> -> <dst>",
            "default": False
        },
        "unique": {
            "type": "boolean",
            "description": "Omit duplicate refs from output", 
            "default": False
        },
        "recursive": {
            "type": "boolean",
            "description": "Recursively list references",
            "default": False
        }
    },
    returns={
        "refs": {"type": "array", "description": "List of references"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_refs(params: Dict[str, Any]) -> Dict[str, Any]:
    """List object references from IPFS content"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        cid = params.get("cid")
        if not cid:
            error = create_ipfs_error("CID parameter is required")
            return error.to_dict()
        
        format_str = params.get("format", "<dst>")
        edges = params.get("edges", False)
        unique = params.get("unique", False)
        recursive = params.get("recursive", False)
        
        # Prepare parameters
        api_params = {
            "arg": cid,
            "format": format_str
        }
        if edges:
            api_params["edges"] = "true"
        if unique:
            api_params["unique"] = "true"
        if recursive:
            api_params["recursive"] = "true"
        
        result = ipfs_client._make_request("refs", params=api_params)
        
        # Parse result (newline-delimited)
        refs = []
        if isinstance(result, dict) and "content" in result:
            lines = result["content"].strip().split('\n')
            refs = [line.strip() for line in lines if line.strip()]
        
        return create_success_response({
            "refs": refs
        })
        
    except Exception as e:
        logger.error(f"IPFS refs failed: {e}")
        error = create_ipfs_error(str(e), "refs")
        return error.to_dict()

@tool(
    name="ipfs_refs_local",
    category="ipfs_core",
    description="List all local references (objects in local storage)",
    parameters={},
    returns={
        "refs": {"type": "array", "description": "List of local references"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_refs_local(params: Dict[str, Any]) -> Dict[str, Any]:
    """List all local references"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        result = ipfs_client._make_request("refs/local")
        
        # Parse result (newline-delimited)
        refs = []
        if isinstance(result, dict) and "content" in result:
            lines = result["content"].strip().split('\n')
            refs = [line.strip() for line in lines if line.strip()]
        
        return create_success_response({
            "refs": refs
        })
        
    except Exception as e:
        logger.error(f"IPFS refs local failed: {e}")
        error = create_ipfs_error(str(e), "refs/local")
        return error.to_dict()

@tool(
    name="ipfs_block_stat",
    category="ipfs_core",
    description="Get statistics for an IPFS block",
    parameters={
        "cid": {
            "type": "string",
            "description": "Content identifier of the block"
        }
    },
    returns={
        "key": {"type": "string", "description": "Block key (CID)"},
        "size": {"type": "integer", "description": "Block size in bytes"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_block_stat(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get statistics for an IPFS block"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        cid = params.get("cid")
        if not cid:
            error = create_ipfs_error("CID parameter is required")
            return error.to_dict()
        
        # Prepare parameters
        api_params = {"arg": cid}
        
        result = ipfs_client._make_request("block/stat", params=api_params)
        
        return create_success_response({
            "key": result.get("Key"),
            "size": result.get("Size")
        })
        
    except Exception as e:
        logger.error(f"IPFS block stat failed: {e}")
        error = create_ipfs_error(str(e), "block/stat")
        return error.to_dict()

@tool(
    name="ipfs_block_get",
    category="ipfs_core",
    description="Get raw IPFS block content",
    parameters={
        "cid": {
            "type": "string",
            "description": "Content identifier of the block"
        }
    },
    returns={
        "data": {"type": "string", "description": "Raw block data (base64 encoded)"},
        "size": {"type": "integer", "description": "Block size in bytes"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_block_get(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get raw IPFS block content"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        cid = params.get("cid")
        if not cid:
            error = create_ipfs_error("CID parameter is required")
            return error.to_dict()
        
        # Prepare parameters
        api_params = {"arg": cid}
        
        result = ipfs_client._make_request("block/get", params=api_params)
        
        # Handle binary data
        if isinstance(result, dict) and "binary" in result:
            import base64
            binary_data = result["binary"]
            encoded_data = base64.b64encode(binary_data).decode('utf-8')
            
            return create_success_response({
                "data": encoded_data,
                "size": len(binary_data)
            })
        else:
            return create_success_response({
                "data": result.get("content", ""),
                "size": len(result.get("content", ""))
            })
        
    except Exception as e:
        logger.error(f"IPFS block get failed: {e}")
        error = create_ipfs_error(str(e), "block/get")
        return error.to_dict()

# ============================================================================
# DAG OPERATIONS
# ============================================================================

@tool(
    name="ipfs_dag_get",
    category="ipfs_core",
    description="Get IPFS DAG node",
    parameters={
        "cid": {
            "type": "string",
            "description": "Content identifier of the DAG node"
        },
        "output_codec": {
            "type": "string",
            "description": "Output codec (dag-json, dag-cbor, etc.)",
            "default": "dag-json"
        }
    },
    returns={
        "data": {"type": "object", "description": "DAG node data"},
        "cid": {"type": "string", "description": "Content identifier"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_dag_get(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get IPFS DAG node"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        cid = params.get("cid")
        if not cid:
            error = create_ipfs_error("CID parameter is required")
            return error.to_dict()
        
        output_codec = params.get("output_codec", "dag-json")
        
        # Prepare parameters
        api_params = {
            "arg": cid,
            "output-codec": output_codec
        }
        
        result = ipfs_client._make_request("dag/get", params=api_params)
        
        # Parse JSON result
        data = result
        if isinstance(result, dict) and "content" in result:
            try:
                data = json.loads(result["content"])
            except json.JSONDecodeError:
                data = {"raw_content": result["content"]}
        
        return create_success_response({
            "data": data,
            "cid": cid
        })
        
    except Exception as e:
        logger.error(f"IPFS dag get failed: {e}")
        error = create_ipfs_error(str(e), "dag/get")
        return error.to_dict()

@tool(
    name="ipfs_dag_put",
    category="ipfs_core", 
    description="Add IPFS DAG node",
    parameters={
        "data": {
            "type": "object",
            "description": "DAG node data to add"
        },
        "input_codec": {
            "type": "string",
            "description": "Input codec (dag-json, dag-cbor, etc.)",
            "default": "dag-json"
        },
        "store_codec": {
            "type": "string",
            "description": "Codec to store the object in",
            "default": "dag-cbor"
        },
        "pin": {
            "type": "boolean",
            "description": "Pin the object",
            "default": False
        }
    },
    returns={
        "cid": {"type": "string", "description": "Content identifier of created DAG node"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_dag_put(params: Dict[str, Any]) -> Dict[str, Any]:
    """Add IPFS DAG node"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        data = params.get("data")
        if not data:
            error = create_ipfs_error("Data parameter is required")
            return error.to_dict()
        
        input_codec = params.get("input_codec", "dag-json")
        store_codec = params.get("store_codec", "dag-cbor")
        pin = params.get("pin", False)
        
        # Prepare parameters
        api_params = {
            "input-codec": input_codec,
            "store-codec": store_codec
        }
        if pin:
            api_params["pin"] = "true"
        
        # Prepare data
        if isinstance(data, dict):
            json_data = json.dumps(data)
        else:
            json_data = str(data)
        
        files = {
            "file": ("data.json", json_data.encode('utf-8'), "application/json")
        }
        
        result = ipfs_client._make_request("dag/put", params=api_params, files=files)
        
        # Parse result
        cid = ""
        if isinstance(result, dict):
            cid = result.get("Cid", {}).get("/", "")
        
        return create_success_response({
            "cid": cid
        })
        
    except Exception as e:
        logger.error(f"IPFS dag put failed: {e}")
        error = create_ipfs_error(str(e), "dag/put")
        return error.to_dict()

# Register all tools with the registry
def register_ipfs_core_tools():
    """Register all IPFS core tools with the tool registry"""
    from core.tool_registry import registry
    
    tools = [
        # Basic Operations
        ("ipfs_add", handle_ipfs_add),
        ("ipfs_cat", handle_ipfs_cat), 
        ("ipfs_get", handle_ipfs_get),
        ("ipfs_ls", handle_ipfs_ls),
        
        # Pin Management  
        ("ipfs_pin_add", handle_ipfs_pin_add),
        ("ipfs_pin_rm", handle_ipfs_pin_rm),
        ("ipfs_pin_ls", handle_ipfs_pin_ls),
        ("ipfs_pin_update", handle_ipfs_pin_update),
        
        # Node Operations
        ("ipfs_id", handle_ipfs_id),
        ("ipfs_version", handle_ipfs_version),
        ("ipfs_stats", handle_ipfs_stats),
        ("ipfs_swarm_peers", handle_ipfs_swarm_peers),
        
        # Content Operations
        ("ipfs_refs", handle_ipfs_refs),
        ("ipfs_refs_local", handle_ipfs_refs_local),
        ("ipfs_block_stat", handle_ipfs_block_stat),
        ("ipfs_block_get", handle_ipfs_block_get),
        
        # DAG Operations
        ("ipfs_dag_get", handle_ipfs_dag_get),
        ("ipfs_dag_put", handle_ipfs_dag_put)
    ]
    
    registered_count = 0
    for tool_name, handler in tools:
        tool_def = getattr(handler, '_tool_meta', None)
        if tool_def:
            from core.tool_registry import ToolSchema, ToolCategory
            
            schema = ToolSchema(
                name=tool_def['name'],
                category=ToolCategory.IPFS_CORE,
                description=tool_def['description'],
                parameters=tool_def['parameters'],
                returns=tool_def['returns'], 
                version=tool_def['version'],
                dependencies=tool_def['dependencies'],
                handler=handler
            )
            
            if registry.register_tool(schema, handler):
                registered_count += 1
    
    logger.info(f"Registered {registered_count} IPFS core tools")
    return registered_count

if __name__ == "__main__":
    # Register tools when module is run directly
    register_ipfs_core_tools()
