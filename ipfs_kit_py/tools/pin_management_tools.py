#!/usr/bin/env python3
"""
Pin Management Tools for IPFS Kit MCP Server
=============================================

This module provides enhanced pin management tools for the Pin Management Dashboard:
- list_pins: List all pins with enhanced metadata
- get_pin_stats: Get statistics about pins
- get_pin_metadata: Get detailed metadata for a specific pin
- unpin_content: Unpin content (wrapper for ipfs_pin_rm)
- bulk_unpin: Bulk unpin multiple CIDs
- export_pins: Export pins to JSON/CSV format
"""

import json
import csv
import logging
import io
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

# Import core components from MCP infrastructure
from ipfs_kit_py.mcp.ipfs_kit.core.tool_registry import tool, ToolCategory
from ipfs_kit_py.mcp.ipfs_kit.core.error_handler import create_success_response, create_ipfs_error
from ipfs_kit_py.mcp.ipfs_kit.core.service_manager import ipfs_manager

# Import IPFS client from ipfs_core_tools in same package
from .ipfs_core_tools import ipfs_client

# Setup logging
logger = logging.getLogger(__name__)

# ============================================================================
# PIN MANAGEMENT TOOLS
# ============================================================================

@tool(
    name="list_pins",
    category="ipfs_core",
    description="List all pinned content with enhanced metadata for dashboard display",
    parameters={
        "type": {
            "type": "string",
            "description": "Type of pins to list: all, direct, indirect, recursive",
            "default": "all",
            "required": False
        },
        "include_metadata": {
            "type": "boolean",
            "description": "Include additional metadata for each pin",
            "default": True,
            "required": False
        }
    },
    returns={
        "success": {"type": "boolean", "description": "Operation success status"},
        "pins": {"type": "array", "description": "List of pin objects with metadata"},
        "total_count": {"type": "integer", "description": "Total number of pins"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_list_pins(params: Dict[str, Any]) -> Dict[str, Any]:
    """List all pinned content with enhanced metadata"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        pin_type = params.get("type", "all")
        include_metadata = params.get("include_metadata", True)
        
        # Get pins from IPFS
        api_params = {"type": pin_type}
        result = ipfs_client._make_request("pin/ls", params=api_params)
        
        # Parse pins
        pins_list = []
        if isinstance(result, dict):
            keys = result.get("Keys", {})
            
            for cid, pin_info in keys.items():
                pin_obj = {
                    "cid": cid,
                    "type": pin_info.get("Type", "unknown"),
                    "created": datetime.now().isoformat(),  # IPFS doesn't track creation time
                    "size": "unknown",  # Will be populated if metadata requested
                    "metadata": {}
                }
                
                if include_metadata:
                    # Try to get object stats for size
                    try:
                        stat_result = ipfs_client._make_request("object/stat", params={"arg": cid})
                        if isinstance(stat_result, dict):
                            size_bytes = stat_result.get("CumulativeSize", 0)
                            pin_obj["size"] = format_size(size_bytes)
                            pin_obj["metadata"]["size_bytes"] = size_bytes
                            pin_obj["metadata"]["num_links"] = stat_result.get("NumLinks", 0)
                    except Exception as e:
                        logger.debug(f"Could not get stats for {cid}: {e}")
                    
                    # Add default metadata
                    pin_obj["metadata"]["backend"] = "ipfs"
                    pin_obj["metadata"]["tags"] = []
                    pin_obj["metadata"]["replication_count"] = 1
                    pin_obj["metadata"]["name"] = ""
                    pin_obj["metadata"]["description"] = ""
                
                pins_list.append(pin_obj)
        
        return create_success_response({
            "pins": pins_list,
            "total_count": len(pins_list)
        })
        
    except Exception as e:
        logger.error(f"Failed to list pins: {e}")
        error = create_ipfs_error(str(e), "list_pins")
        return error.to_dict()


@tool(
    name="get_pin_stats",
    category="ipfs_core",
    description="Get statistics about pinned content",
    parameters={},
    returns={
        "success": {"type": "boolean", "description": "Operation success status"},
        "stats": {"type": "object", "description": "Pin statistics"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_get_pin_stats(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get statistics about pinned content"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        # Get all pins
        result = ipfs_client._make_request("pin/ls", params={"type": "all"})
        
        stats = {
            "total_pins": 0,
            "by_type": {
                "recursive": 0,
                "direct": 0,
                "indirect": 0
            },
            "by_backend": {
                "ipfs": 0
            }
        }
        
        if isinstance(result, dict):
            keys = result.get("Keys", {})
            stats["total_pins"] = len(keys)
            
            for cid, pin_info in keys.items():
                pin_type = pin_info.get("Type", "unknown")
                if pin_type in stats["by_type"]:
                    stats["by_type"][pin_type] += 1
                stats["by_backend"]["ipfs"] += 1
        
        return create_success_response({
            "stats": stats
        })
        
    except Exception as e:
        logger.error(f"Failed to get pin stats: {e}")
        error = create_ipfs_error(str(e), "get_pin_stats")
        return error.to_dict()


@tool(
    name="get_pin_metadata",
    category="ipfs_core",
    description="Get detailed metadata for a specific pin",
    parameters={
        "cid": {
            "type": "string",
            "description": "Content identifier to get metadata for"
        }
    },
    returns={
        "success": {"type": "boolean", "description": "Operation success status"},
        "metadata": {"type": "object", "description": "Pin metadata"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_get_pin_metadata(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get detailed metadata for a specific pin"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        cid = params.get("cid")
        if not cid:
            error = create_ipfs_error("CID parameter is required")
            return error.to_dict()
        
        # Check if pin exists
        pin_result = ipfs_client._make_request("pin/ls", params={"arg": cid})
        
        if not isinstance(pin_result, dict) or not pin_result.get("Keys"):
            error = create_ipfs_error(f"Pin not found: {cid}")
            return error.to_dict()
        
        pin_info = pin_result.get("Keys", {}).get(cid, {})
        
        # Get object stats
        metadata = {
            "cid": cid,
            "type": pin_info.get("Type", "unknown"),
            "created": datetime.now().isoformat(),
            "size": "unknown",
            "status": "pinned",
            "metadata": {
                "backend": "ipfs",
                "tags": [],
                "replication_count": 1,
                "name": "",
                "description": ""
            }
        }
        
        try:
            stat_result = ipfs_client._make_request("object/stat", params={"arg": cid})
            if isinstance(stat_result, dict):
                size_bytes = stat_result.get("CumulativeSize", 0)
                metadata["size"] = format_size(size_bytes)
                metadata["metadata"]["size_bytes"] = size_bytes
                metadata["metadata"]["num_links"] = stat_result.get("NumLinks", 0)
                metadata["metadata"]["block_size"] = stat_result.get("BlockSize", 0)
                metadata["metadata"]["data_size"] = stat_result.get("DataSize", 0)
        except Exception as e:
            logger.debug(f"Could not get stats for {cid}: {e}")
        
        return create_success_response({
            "metadata": metadata
        })
        
    except Exception as e:
        logger.error(f"Failed to get pin metadata: {e}")
        error = create_ipfs_error(str(e), "get_pin_metadata")
        return error.to_dict()


@tool(
    name="unpin_content",
    category="ipfs_core",
    description="Unpin content from IPFS (remove pin)",
    parameters={
        "cid": {
            "type": "string",
            "description": "Content identifier to unpin"
        },
        "recursive": {
            "type": "boolean",
            "description": "Recursively unpin the object",
            "default": True,
            "required": False
        }
    },
    returns={
        "success": {"type": "boolean", "description": "Operation success status"},
        "pins": {"type": "array", "description": "List of unpinned CIDs"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_unpin_content(params: Dict[str, Any]) -> Dict[str, Any]:
    """Unpin content from IPFS"""
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
        
        # Unpin using IPFS API
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
        logger.error(f"Failed to unpin content: {e}")
        error = create_ipfs_error(str(e), "unpin_content")
        return error.to_dict()


@tool(
    name="bulk_unpin",
    category="ipfs_core",
    description="Unpin multiple CIDs in bulk",
    parameters={
        "cids": {
            "type": "array",
            "description": "List of CIDs to unpin",
            "items": {"type": "string"}
        },
        "recursive": {
            "type": "boolean",
            "description": "Recursively unpin the objects",
            "default": True,
            "required": False
        }
    },
    returns={
        "success": {"type": "boolean", "description": "Operation success status"},
        "total": {"type": "integer", "description": "Total CIDs to unpin"},
        "success_count": {"type": "integer", "description": "Number of successfully unpinned CIDs"},
        "error_count": {"type": "integer", "description": "Number of failed unpins"},
        "errors": {"type": "array", "description": "List of errors encountered"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_bulk_unpin(params: Dict[str, Any]) -> Dict[str, Any]:
    """Unpin multiple CIDs in bulk"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        cids = params.get("cids", [])
        if not cids or not isinstance(cids, list):
            error = create_ipfs_error("cids parameter must be a non-empty array")
            return error.to_dict()
        
        recursive = params.get("recursive", True)
        
        # Unpin each CID
        success_count = 0
        error_count = 0
        errors = []
        
        for cid in cids:
            try:
                api_params = {
                    "arg": cid,
                    "recursive": "true" if recursive else "false"
                }
                ipfs_client._make_request("pin/rm", params=api_params)
                success_count += 1
            except Exception as e:
                error_count += 1
                errors.append({
                    "cid": cid,
                    "error": str(e)
                })
                logger.error(f"Failed to unpin {cid}: {e}")
        
        return create_success_response({
            "total": len(cids),
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors
        })
        
    except Exception as e:
        logger.error(f"Failed to bulk unpin: {e}")
        error = create_ipfs_error(str(e), "bulk_unpin")
        return error.to_dict()


@tool(
    name="export_pins",
    category="ipfs_core",
    description="Export pins to JSON or CSV format",
    parameters={
        "format": {
            "type": "string",
            "description": "Export format: json or csv",
            "enum": ["json", "csv"]
        },
        "filter_type": {
            "type": "string",
            "description": "Filter by pin type",
            "required": False
        }
    },
    returns={
        "success": {"type": "boolean", "description": "Operation success status"},
        "data": {"type": "string", "description": "Exported data as string"},
        "count": {"type": "integer", "description": "Number of pins exported"}
    },
    version="1.0.0",
    dependencies=["requests"]
)
def handle_export_pins(params: Dict[str, Any]) -> Dict[str, Any]:
    """Export pins to JSON or CSV format"""
    try:
        # Ensure IPFS is running
        if not ipfs_manager.ensure_ipfs_running():
            error = create_ipfs_error("IPFS daemon not running")
            return error.to_dict()
        
        export_format = params.get("format", "json").lower()
        filter_type = params.get("filter_type")
        
        if export_format not in ["json", "csv"]:
            error = create_ipfs_error("format must be 'json' or 'csv'")
            return error.to_dict()
        
        # Get pins
        api_params = {"type": filter_type or "all"}
        result = ipfs_client._make_request("pin/ls", params=api_params)
        
        pins_list = []
        if isinstance(result, dict):
            keys = result.get("Keys", {})
            
            for cid, pin_info in keys.items():
                pin_obj = {
                    "cid": cid,
                    "type": pin_info.get("Type", "unknown"),
                    "created": datetime.now().isoformat()
                }
                pins_list.append(pin_obj)
        
        # Export based on format
        if export_format == "json":
            data = json.dumps(pins_list, indent=2)
        else:  # csv
            output = io.StringIO()
            if pins_list:
                fieldnames = pins_list[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(pins_list)
            data = output.getvalue()
        
        return create_success_response({
            "data": data,
            "count": len(pins_list)
        })
        
    except Exception as e:
        logger.error(f"Failed to export pins: {e}")
        error = create_ipfs_error(str(e), "export_pins")
        return error.to_dict()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable string"""
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.2f} {units[unit_index]}"
