#!/usr/bin/env python3
"""
IPFS Core Operations - Phase 2 Implementation

This module implements the 18 core IPFS tools:
- Basic Operations: ipfs_add, ipfs_cat, ipfs_get, ipfs_ls
- Pin Management: ipfs_pin_add, ipfs_pin_rm, ipfs_pin_ls, ipfs_pin_update  
- Node Operations: ipfs_id, ipfs_version, ipfs_stats, ipfs_swarm_peers
- Content Operations: ipfs_refs, ipfs_refs_local, ipfs_block_stat, ipfs_block_get
- DAG Operations: ipfs_dag_get, ipfs_dag_put
"""

import requests
import json
import logging
import os
import hashlib
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import tempfile
import subprocess

# Import core components
import sys
sys.path.append(str(Path(__file__).parent.parent))

from ipfs_kit_py.core.tool_registry import tool, ToolCategory
from ipfs_kit_py.core.error_handler import create_success_response, create_ipfs_error, ErrorContext
from ipfs_kit_py.core.service_manager import ipfs_manager

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
# BASIC OPERATIONS
# ============================================================================

@tool(
    name="ipfs_add",
    category="ipfs_core",
    description="Add content to IPFS and return its CID",
    parameters={
        "content": {
            "type": "string",
            "description": "Content to add to IPFS"
        },
        "file_path": {
            "type": "string", 
            "description": "Path to file to add to IPFS (alternative to content)",
            "required": False
        },
        "pin": {
            "type": "boolean",
            "description": "Whether to pin the content",
            "default": True
        },
        "wrap_with_directory": {
            "type": "boolean", 
            "description": "Wrap the content in a directory",
            "default": False
        }
    },
    returns={
        "cid": {"type": "string", "description": "Content identifier"},
        "size": {"type": "string", "description": "Size of added content"},
        "name": {"type": "string", "description": "Name of added content"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_add(params: Dict[str, Any]) -> Dict[str, Any]:
    """Add content to IPFS"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        content = params.get("content")
        file_path = params.get("file_path")
        pin = params.get("pin", True)
        wrap_with_directory = params.get("wrap_with_directory", False)
        
        if not content and not file_path:
            error = create_ipfs_error("Either content or file_path must be provided")
            return error.to_dict()
        
        # Prepare parameters
        api_params = {
            "pin": "true" if pin else "false",
            "wrap-with-directory": "true" if wrap_with_directory else "false"
        }
        
        files = {}
        
        if file_path:
            # Add file
            if not os.path.exists(file_path):
                error = create_ipfs_error(f"File not found: {file_path}")
                return error.to_dict()
            
            with open(file_path, 'rb') as f:
                files['file'] = (os.path.basename(file_path), f, 'application/octet-stream')
                result = ipfs_client._make_request("add", params=api_params, files=files)
        else:
            # Add content as string
            files['file'] = ('content.txt', content.encode('utf-8'), 'text/plain')
            result = ipfs_client._make_request("add", params=api_params, files=files)
        
        # Parse result (IPFS returns newline-delimited JSON)
        if isinstance(result, dict) and "content" in result:
            lines = result["content"].strip().split('\n')
            # Get the last line (root object)
            last_line = lines[-1]
            add_result = json.loads(last_line)
        else:
            add_result = result
        
        return create_success_response({
            "cid": add_result.get("Hash"),
            "size": add_result.get("Size"),
            "name": add_result.get("Name", "")
        })
        
    except Exception as e:
        logger.error(f"IPFS add failed: {e}")
        error = create_ipfs_error(str(e), "add")
        return error.to_dict()

@tool(
    name="ipfs_cat",
    category="ipfs_core", 
    description="Get content from IPFS by CID",
    parameters={
        "cid": {
            "type": "string",
            "description": "Content identifier to retrieve"
        },
        "offset": {
            "type": "integer",
            "description": "Byte offset to start reading",
            "required": False
        },
        "length": {
            "type": "integer", 
            "description": "Maximum number of bytes to read",
            "required": False
        }
    },
    returns={
        "content": {"type": "string", "description": "Content data"},
        "size": {"type": "integer", "description": "Content size in bytes"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_cat(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get content from IPFS by CID"""
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
        
        if "offset" in params:
            api_params["offset"] = params["offset"]
        if "length" in params:
            api_params["length"] = params["length"]
        
        result = ipfs_client._make_request("cat", params=api_params)
        
        content = result.get("content", "")
        
        return create_success_response({
            "content": content,
            "size": len(content.encode('utf-8'))
        })
        
    except Exception as e:
        logger.error(f"IPFS cat failed: {e}")
        error = create_ipfs_error(str(e), "cat")
        return error.to_dict()

@tool(
    name="ipfs_get",
    category="ipfs_core",
    description="Download IPFS content to local filesystem", 
    parameters={
        "cid": {
            "type": "string",
            "description": "Content identifier to download"
        },
        "output_path": {
            "type": "string",
            "description": "Local path to save content",
            "required": False
        }
    },
    returns={
        "path": {"type": "string", "description": "Local path where content was saved"},
        "size": {"type": "integer", "description": "Downloaded size in bytes"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_get(params: Dict[str, Any]) -> Dict[str, Any]:
    """Download IPFS content to local filesystem"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        cid = params.get("cid")
        if not cid:
            error = create_ipfs_error("CID parameter is required")
            return error.to_dict()
        
        output_path = params.get("output_path")
        if not output_path:
            output_path = f"./{cid}"
        
        # Prepare parameters
        api_params = {
            "arg": cid,
            "output": output_path
        }
        
        result = ipfs_client._make_request("get", params=api_params)
        
        # Check if file was created
        if os.path.exists(output_path):
            # Get size
            if os.path.isfile(output_path):
                size = os.path.getsize(output_path)
            else:
                # Directory - calculate total size
                size = sum(os.path.getsize(os.path.join(dirpath, filename))
                          for dirpath, dirnames, filenames in os.walk(output_path)
                          for filename in filenames)
        else:
            size = 0
        
        return create_success_response({
            "path": output_path,
            "size": size
        })
        
    except Exception as e:
        logger.error(f"IPFS get failed: {e}")
        error = create_ipfs_error(str(e), "get")
        return error.to_dict()

@tool(
    name="ipfs_ls",
    category="ipfs_core",
    description="List directory contents in IPFS",
    parameters={
        "path": {
            "type": "string", 
            "description": "IPFS path to list (e.g., /ipfs/QmHash or just QmHash)"
        },
        "resolve_type": {
            "type": "boolean",
            "description": "Resolve the type of each entry",
            "default": True
        }
    },
    returns={
        "entries": {"type": "array", "description": "Directory entries"},
        "path": {"type": "string", "description": "Listed path"}
    },
    version="1.0.0", 
    dependencies=["requests"]
)
def handle_ipfs_ls(params: Dict[str, Any]) -> Dict[str, Any]:
    """List directory contents in IPFS"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        path = params.get("path")
        if not path:
            error = create_ipfs_error("Path parameter is required")
            return error.to_dict()
        
        resolve_type = params.get("resolve_type", True)
        
        # Prepare parameters
        api_params = {
            "arg": path,
            "resolve-type": "true" if resolve_type else "false"
        }
        
        result = ipfs_client._make_request("ls", params=api_params)
        
        # Parse result
        entries = []
        if isinstance(result, dict):
            objects = result.get("Objects", [])
            if objects:
                links = objects[0].get("Links", [])
                entries = [
                    {
                        "Name": link.get("Name"),
                        "Hash": link.get("Hash"), 
                        "Size": link.get("Size"),
                        "Type": link.get("Type")
                    }
                    for link in links
                ]
        
        return create_success_response({
            "entries": entries,
            "path": path
        })
        
    except Exception as e:
        logger.error(f"IPFS ls failed: {e}")
        error = create_ipfs_error(str(e), "ls")
        return error.to_dict()

# ============================================================================
# PIN MANAGEMENT
# ============================================================================

@tool(
    name="ipfs_pin_add",
    category="ipfs_core",
    description="Pin content in IPFS to prevent garbage collection",
    parameters={
        "cid": {
            "type": "string",
            "description": "Content identifier to pin"
        },
        "recursive": {
            "type": "boolean", 
            "description": "Recursively pin the object linked to by the specified object(s)",
            "default": True
        }
    },
    returns={
        "pins": {"type": "array", "description": "List of pinned CIDs"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_pin_add(params: Dict[str, Any]) -> Dict[str, Any]:
    """Pin content in IPFS"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        cid = params.get("cid")
        if not cid:
            error = create_ipfs_error("CID parameter is required")
            return error.to_dict()
        
        recursive = params.get("recursive", True)
        
        # Prepare parameters
        api_params = {
            "arg": cid,
            "recursive": "true" if recursive else "false"
        }
        
        result = ipfs_client._make_request("pin/add", params=api_params)
        
        # Parse result
        pins = []
        if isinstance(result, dict):
            pins_data = result.get("Pins", [])
            pins = [pin for pin in pins_data if pin]
        
        return create_success_response({
            "pins": pins
        })
        
    except Exception as e:
        logger.error(f"IPFS pin add failed: {e}")
        error = create_ipfs_error(str(e), "pin/add")
        return error.to_dict()

@tool(
    name="ipfs_pin_rm",
    category="ipfs_core",
    description="Remove pin from IPFS content",
    parameters={
        "cid": {
            "type": "string",
            "description": "Content identifier to unpin"
        },
        "recursive": {
            "type": "boolean",
            "description": "Recursively unpin the object linked to by the specified object(s)", 
            "default": True
        }
    },
    returns={
        "pins": {"type": "array", "description": "List of unpinned CIDs"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_pin_rm(params: Dict[str, Any]) -> Dict[str, Any]:
    """Remove pin from IPFS content"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        cid = params.get("cid")
        if not cid:
            error = create_ipfs_error("CID parameter is required")
            return error.to_dict()
        
        recursive = params.get("recursive", True)
        
        # Prepare parameters
        api_params = {
            "arg": cid,
            "recursive": "true" if recursive else "false"
        }
        
        result = ipfs_client._make_request("pin/rm", params=api_params)
        
        # Parse result
        pins = []
        if isinstance(result, dict):
            pins_data = result.get("Pins", [])
            pins = [pin for pin in pins_data if pin]
        
        return create_success_response({
            "pins": pins
        })
        
    except Exception as e:
        logger.error(f"IPFS pin rm failed: {e}")
        error = create_ipfs_error(str(e), "pin/rm")
        return error.to_dict()

@tool(
    name="ipfs_pin_ls",
    category="ipfs_core",
    description="List pinned objects in IPFS",
    parameters={
        "type": {
            "type": "string",
            "description": "Type of pins to list: all, direct, indirect, recursive",
            "default": "all"
        },
        "cid": {
            "type": "string",
            "description": "Specific CID to check (optional)",
            "required": False
        }
    },
    returns={
        "pins": {"type": "object", "description": "Map of CID to pin type"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_pin_ls(params: Dict[str, Any]) -> Dict[str, Any]:
    """List pinned objects in IPFS"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        pin_type = params.get("type", "all")
        cid = params.get("cid")
        
        # Prepare parameters
        api_params = {"type": pin_type}
        if cid:
            api_params["arg"] = cid
        
        result = ipfs_client._make_request("pin/ls", params=api_params)
        
        # Parse result
        pins = {}
        if isinstance(result, dict):
            keys = result.get("Keys", {})
            pins = {cid: pin_info.get("Type", "") for cid, pin_info in keys.items()}
        
        return create_success_response({
            "pins": pins
        })
        
    except Exception as e:
        logger.error(f"IPFS pin ls failed: {e}")
        error = create_ipfs_error(str(e), "pin/ls")
        return error.to_dict()

@tool(
    name="ipfs_pin_update",
    category="ipfs_core",
    description="Update a pin to a new CID",
    parameters={
        "old_cid": {
            "type": "string",
            "description": "CID to unpin"
        },
        "new_cid": {
            "type": "string", 
            "description": "CID to pin"
        },
        "unpin": {
            "type": "boolean",
            "description": "Remove the old pin",
            "default": True
        }
    },
    returns={
        "pins": {"type": "array", "description": "List of updated pins"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_ipfs_pin_update(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update a pin to a new CID"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        old_cid = params.get("old_cid")
        new_cid = params.get("new_cid")
        
        if not old_cid or not new_cid:
            error = create_ipfs_error("Both old_cid and new_cid parameters are required")
            return error.to_dict()
        
        unpin = params.get("unpin", True)
        
        # Prepare parameters
        api_params = {
            "arg": [old_cid, new_cid],
            "unpin": "true" if unpin else "false"
        }
        
        result = ipfs_client._make_request("pin/update", params=api_params)
        
        # Parse result
        pins = []
        if isinstance(result, dict):
            pins_data = result.get("Pins", [])
            pins = [pin for pin in pins_data if pin]
        
        return create_success_response({
            "pins": pins
        })
        
    except Exception as e:
        logger.error(f"IPFS pin update failed: {e}")
        error = create_ipfs_error(str(e), "pin/update")
        return error.to_dict()

# Continue with remaining tools in next part...
