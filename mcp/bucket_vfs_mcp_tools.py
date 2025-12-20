"""
MCP Tools for Bucket VFS Management.

This module provides Model Context Protocol (MCP) tools for managing 
multi-bucket virtual filesystems with S3-like semantics, IPLD compatibility,
and cross-platform data export capabilities.
"""

import asyncio
import json
import logging
import os
import tempfile
import traceback
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Import MCP types with fallback
try:
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    # Fallback for when MCP is not available
    class Tool:
        def __init__(self, name: str, description: str, inputSchema: Dict[str, Any]):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema
    
    class TextContent:
        def __init__(self, type: str, text: str):
            self.type = type
            self.text = text
    
    MCP_AVAILABLE = False

# Import bucket VFS components
BUCKET_VFS_AVAILABLE = False
BucketType = None
VFSStructureType = None
get_global_bucket_manager = None

try:
    from ipfs_kit_py.bucket_vfs_manager import (
        get_global_bucket_manager as _get_global_bucket_manager,
        BucketType as _BucketType,
        VFSStructureType as _VFSStructureType
    )
    from ipfs_kit_py.error import create_result_dict, handle_error
    BUCKET_VFS_AVAILABLE = True
    BucketType = _BucketType
    VFSStructureType = _VFSStructureType
    get_global_bucket_manager = _get_global_bucket_manager
except ImportError as e:
    logger.warning(f"Bucket VFS not available: {e}")

# Global bucket manager instance
_bucket_manager = None

def get_bucket_manager(ipfs_client=None, storage_path: str = "/tmp/mcp_buckets"):
    """Get or create the global bucket manager instance."""
    global _bucket_manager
    if _bucket_manager is None and BUCKET_VFS_AVAILABLE and get_global_bucket_manager:
        _bucket_manager = get_global_bucket_manager(
            storage_path=storage_path,
            ipfs_client=ipfs_client
        )
    return _bucket_manager

def create_bucket_tools() -> List[Tool]:
    """Create MCP tools for bucket VFS operations."""
    if not BUCKET_VFS_AVAILABLE:
        return []
    
    tools = [
        Tool(
            name="bucket_create",
            description="Create a new bucket with S3-like semantics and IPLD compatibility",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket_name": {
                        "type": "string",
                        "description": "Name of the bucket to create"
                    },
                    "bucket_type": {
                        "type": "string",
                        "enum": ["general", "dataset", "knowledge", "media", "archive", "temp"],
                        "default": "general",
                        "description": "Type of bucket for specialized operations"
                    },
                    "vfs_structure": {
                        "type": "string", 
                        "enum": ["unixfs", "graph", "vector", "hybrid"],
                        "default": "hybrid",
                        "description": "Virtual filesystem structure type"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional metadata for the bucket"
                    },
                    "storage_path": {
                        "type": "string",
                        "description": "Custom storage path for bucket data"
                    }
                },
                "required": ["bucket_name"]
            }
        ),
        
        Tool(
            name="bucket_list",
            description="List all available buckets with their metadata and statistics",
            inputSchema={
                "type": "object",
                "properties": {
                    "storage_path": {
                        "type": "string",
                        "description": "Storage path to list buckets from"
                    },
                    "detailed": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include detailed statistics for each bucket"
                    }
                }
            }
        ),
        
        Tool(
            name="bucket_delete",
            description="Delete a bucket and all its contents",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket_name": {
                        "type": "string",
                        "description": "Name of the bucket to delete"
                    },
                    "force": {
                        "type": "boolean",
                        "default": False,
                        "description": "Force deletion even if bucket contains data"
                    },
                    "storage_path": {
                        "type": "string",
                        "description": "Storage path for bucket data"
                    }
                },
                "required": ["bucket_name"]
            }
        ),
        
        Tool(
            name="bucket_add_file",
            description="Add a file to a bucket with automatic IPLD content addressing",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket_name": {
                        "type": "string",
                        "description": "Name of the target bucket"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Virtual path within the bucket"
                    },
                    "content": {
                        "type": "string",
                        "description": "File content (text) or base64 encoded binary data"
                    },
                    "content_type": {
                        "type": "string",
                        "enum": ["text", "base64", "json"],
                        "default": "text",
                        "description": "Type of content being added"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional metadata for the file"
                    },
                    "storage_path": {
                        "type": "string",
                        "description": "Storage path for bucket data"
                    }
                },
                "required": ["bucket_name", "file_path", "content"]
            }
        ),
        
        Tool(
            name="bucket_export_car",
            description="Export bucket contents to CAR archive for IPFS distribution",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket_name": {
                        "type": "string",
                        "description": "Name of the bucket to export"
                    },
                    "include_indexes": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include knowledge graph and vector indexes"
                    },
                    "storage_path": {
                        "type": "string",
                        "description": "Storage path for bucket data"
                    }
                },
                "required": ["bucket_name"]
            }
        ),
        
        Tool(
            name="bucket_cross_query",
            description="Execute SQL queries across multiple buckets using DuckDB",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql_query": {
                        "type": "string",
                        "description": "SQL query to execute across buckets"
                    },
                    "bucket_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of bucket names to include (default: all)"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["table", "json", "csv"],
                        "default": "table",
                        "description": "Output format for query results"
                    },
                    "storage_path": {
                        "type": "string",
                        "description": "Storage path for bucket data"
                    }
                },
                "required": ["sql_query"]
            }
        ),
        
        Tool(
            name="bucket_get_info",
            description="Get detailed information about a specific bucket",
            inputSchema={
                "type": "object",
                "properties": {
                    "bucket_name": {
                        "type": "string",
                        "description": "Name of the bucket to inspect"
                    },
                    "include_files": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include file listing in the response"
                    },
                    "storage_path": {
                        "type": "string",
                        "description": "Storage path for bucket data"
                    }
                },
                "required": ["bucket_name"]
            }
        ),
        
        Tool(
            name="bucket_status",
            description="Get overall status of the bucket VFS system",
            inputSchema={
                "type": "object",
                "properties": {
                    "storage_path": {
                        "type": "string",
                        "description": "Storage path for bucket data"
                    },
                    "include_health": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include health check information"
                    }
                }
            }
        )
    ]
    
    return tools

async def handle_bucket_create(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle bucket creation."""
    try:
        bucket_name = arguments.get("bucket_name")
        bucket_type = arguments.get("bucket_type", "general")
        vfs_structure = arguments.get("vfs_structure", "hybrid")
        metadata = arguments.get("metadata", {})
        storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
        
        if not bucket_name:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "bucket_name is required",
                }, indent=2)
            )]
        
        # Get bucket manager
        bucket_manager = get_bucket_manager(storage_path=storage_path)
        if not bucket_manager:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "Bucket VFS system not available",
                }, indent=2)
            )]
        
        # Convert string enums
        try:
            if not BucketType or not VFSStructureType:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": "Bucket VFS enums not available"
                    }, indent=2)
                )]
            
            bucket_type_enum = BucketType(bucket_type)
            vfs_structure_enum = VFSStructureType(vfs_structure)
        except ValueError as e:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Invalid enum value: {e}",
                }, indent=2)
            )]
        
        # Create bucket
        result = await bucket_manager.create_bucket(
            bucket_name=bucket_name,
            bucket_type=bucket_type_enum,
            vfs_structure=vfs_structure_enum,
            metadata=metadata
        )
        
        if result["success"]:
            data = result.get("data", {})
            response = {
                "success": True,
                "message": f"Created bucket '{bucket_name}'",
                "bucket": {
                    "name": bucket_name,
                    "type": data.get("bucket_type"),
                    "structure": data.get("vfs_structure"),
                    "root_cid": data.get("cid"),
                    "created_at": data.get("created_at")
                }
            }
        else:
            response = {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
        
    except Exception as e:
        error_response = {
            "success": False,
            "error": f"Exception in bucket_create: {str(e)}",
            "traceback": traceback.format_exc()
        }
        return [TextContent(
            type="text", 
            text=json.dumps(error_response, indent=2)
        )]

async def handle_bucket_list(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle bucket listing."""
    try:
        storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
        detailed = arguments.get("detailed", False)
        
        # Get bucket manager
        bucket_manager = get_bucket_manager(storage_path=storage_path)
        if not bucket_manager:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "Bucket VFS system not available"
                }, indent=2)
            )]
        
        # List buckets
        result = await bucket_manager.list_buckets()
        
        if result["success"]:
            buckets_data = result.get("data", {})
            buckets = buckets_data.get("buckets", [])
            
            response = {
                "success": True,
                "total_buckets": buckets_data.get("total_count", 0),
                "buckets": []
            }
            
            for bucket in buckets:
                bucket_info = {
                    "name": bucket["name"],
                    "type": bucket["type"],
                    "structure": bucket["vfs_structure"],
                    "root_cid": bucket.get("root_cid"),
                    "created_at": bucket.get("created_at")
                }
                
                if detailed:
                    bucket_info.update({
                        "file_count": bucket.get("file_count", 0),
                        "size_bytes": bucket.get("size_bytes", 0),
                        "last_modified": bucket.get("last_modified")
                    })
                
                response["buckets"].append(bucket_info)
        else:
            response = {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
        
    except Exception as e:
        error_response = {
            "success": False,
            "error": f"Exception in bucket_list: {str(e)}",
            "traceback": traceback.format_exc()
        }
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

async def handle_bucket_delete(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle bucket deletion."""
    try:
        bucket_name = arguments.get("bucket_name")
        force = arguments.get("force", False)
        storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
        
        if not bucket_name:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "bucket_name is required"
                }, indent=2)
            )]
        
        # Get bucket manager
        bucket_manager = get_bucket_manager(storage_path=storage_path)
        if not bucket_manager:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "Bucket VFS system not available"
                }, indent=2)
            )]
        
        # Delete bucket
        result = await bucket_manager.delete_bucket(bucket_name, force=force)
        
        if result["success"]:
            response = {
                "success": True,
                "message": f"Deleted bucket '{bucket_name}'"
            }
        else:
            response = {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
        
    except Exception as e:
        error_response = {
            "success": False,
            "error": f"Exception in bucket_delete: {str(e)}",
            "traceback": traceback.format_exc()
        }
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

async def handle_bucket_add_file(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle adding a file to a bucket."""
    try:
        bucket_name = arguments.get("bucket_name")
        file_path = arguments.get("file_path")
        content = arguments.get("content")
        content_type = arguments.get("content_type", "text")
        metadata = arguments.get("metadata", {})
        storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
        
        if not all([bucket_name, file_path, content is not None]):
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "bucket_name, file_path, and content are required"
                }, indent=2)
            )]
        
        # Get bucket manager
        bucket_manager = get_bucket_manager(storage_path=storage_path)
        if not bucket_manager:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "Bucket VFS system not available"
                }, indent=2)
            )]
        
        # Get bucket
        bucket = await bucket_manager.get_bucket(bucket_name)
        if not bucket:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Bucket '{bucket_name}' not found"
                }, indent=2)
            )]
        
        # Process content based on type
        if content_type == "text":
            content_bytes = content.encode('utf-8')
        elif content_type == "base64":
            import base64
            content_bytes = base64.b64decode(content)
        elif content_type == "json":
            content_bytes = json.dumps(content).encode('utf-8')
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Unknown content_type: {content_type}"
                }, indent=2)
            )]
        
        # Add file to bucket
        result = await bucket.add_file(file_path, content_bytes, metadata)
        
        if result["success"]:
            data = result.get("data", {})
            response = {
                "success": True,
                "message": f"Added file '{file_path}' to bucket '{bucket_name}'",
                "file": {
                    "path": file_path,
                    "size": data.get("size"),
                    "cid": data.get("cid"),
                    "local_path": data.get("local_path")
                }
            }
        else:
            response = {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
        
    except Exception as e:
        error_response = {
            "success": False,
            "error": f"Exception in bucket_add_file: {str(e)}",
            "traceback": traceback.format_exc()
        }
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

async def handle_bucket_export_car(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle bucket export to CAR archive."""
    try:
        bucket_name = arguments.get("bucket_name")
        include_indexes = arguments.get("include_indexes", True)
        storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
        
        if not bucket_name:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "bucket_name is required"
                }, indent=2)
            )]
        
        # Get bucket manager
        bucket_manager = get_bucket_manager(storage_path=storage_path)
        if not bucket_manager:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "Bucket VFS system not available"
                }, indent=2)
            )]
        
        # Export bucket
        result = await bucket_manager.export_bucket_to_car(
            bucket_name,
            include_indexes=include_indexes
        )
        
        if result["success"]:
            data = result.get("data", {})
            response = {
                "success": True,
                "message": f"Exported bucket '{bucket_name}' to CAR archive",
                "export": {
                    "car_path": data.get("car_path"),
                    "car_cid": data.get("car_cid"),
                    "exported_items": data.get("exported_items")
                }
            }
        else:
            response = {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
        
    except Exception as e:
        error_response = {
            "success": False,
            "error": f"Exception in bucket_export_car: {str(e)}",
            "traceback": traceback.format_exc()
        }
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

async def handle_bucket_cross_query(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle cross-bucket SQL query."""
    try:
        sql_query = arguments.get("sql_query")
        bucket_filter = arguments.get("bucket_filter")
        format_type = arguments.get("format", "table")
        storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
        
        if not sql_query:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "sql_query is required"
                }, indent=2)
            )]
        
        # Get bucket manager
        bucket_manager = get_bucket_manager(storage_path=storage_path)
        if not bucket_manager:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "Bucket VFS system not available"
                }, indent=2)
            )]
        
        # Execute query
        result = await bucket_manager.cross_bucket_query(
            sql_query,
            bucket_filter=bucket_filter
        )
        
        if result["success"]:
            data = result.get("data", {})
            columns = data.get("columns", [])
            rows = data.get("rows", [])
            
            response = {
                "success": True,
                "query": sql_query,
                "row_count": len(rows),
                "columns": columns
            }
            
            if format_type == "json":
                # Convert rows to JSON objects
                response["results"] = [
                    dict(zip(columns, row)) for row in rows
                ]
            elif format_type == "csv":
                # Convert to CSV format
                import io
                import csv
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(columns)
                writer.writerows(rows)
                response["results"] = output.getvalue()
            else:  # table format
                response["results"] = {
                    "columns": columns,
                    "rows": rows
                }
        else:
            response = {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
        
    except Exception as e:
        error_response = {
            "success": False,
            "error": f"Exception in bucket_cross_query: {str(e)}",
            "traceback": traceback.format_exc()
        }
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

async def handle_bucket_get_info(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle getting bucket information."""
    try:
        bucket_name = arguments.get("bucket_name")
        include_files = arguments.get("include_files", False)
        storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
        
        if not bucket_name:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "bucket_name is required"
                }, indent=2)
            )]
        
        # Get bucket manager
        bucket_manager = get_bucket_manager(storage_path=storage_path)
        if not bucket_manager:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "Bucket VFS system not available"
                }, indent=2)
            )]
        
        # Get bucket
        bucket = await bucket_manager.get_bucket(bucket_name)
        if not bucket:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Bucket '{bucket_name}' not found"
                }, indent=2)
            )]
        
        # Build bucket info
        bucket_info = {
            "name": bucket.name,
            "type": bucket.bucket_type.value,
            "vfs_structure": bucket.vfs_structure.value,
            "root_cid": bucket.root_cid,
            "created_at": bucket.created_at,
            "storage_path": str(bucket.storage_path),
            "file_count": await bucket.get_file_count(),
            "total_size": await bucket.get_total_size(),
            "last_modified": await bucket.get_last_modified()
        }
        
        # Include directory structure
        bucket_info["directories"] = {
            name: str(path) for name, path in bucket.dirs.items()
            if path.exists()
        }
        
        # Include component status
        bucket_info["components"] = {
            "knowledge_graph": bucket.knowledge_graph is not None,
            "vector_index": bucket.vector_index is not None,
            "parquet_bridge": bucket.parquet_bridge is not None,
            "car_bridge": bucket.car_bridge is not None
        }
        
        # Include files if requested
        if include_files:
            files_dir = bucket.dirs["files"]
            if files_dir.exists():
                file_list = []
                for file_path in files_dir.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(files_dir)
                        file_list.append({
                            "path": str(rel_path),
                            "size": file_path.stat().st_size,
                            "modified": file_path.stat().st_mtime
                        })
                bucket_info["files"] = file_list
        
        response = {
            "success": True,
            "bucket": bucket_info
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
        
    except Exception as e:
        error_response = {
            "success": False,
            "error": f"Exception in bucket_get_info: {str(e)}",
            "traceback": traceback.format_exc()
        }
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

async def handle_bucket_status(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle getting bucket VFS system status."""
    try:
        storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
        include_health = arguments.get("include_health", True)
        
        # Get bucket manager
        bucket_manager = get_bucket_manager(storage_path=storage_path)
        if not bucket_manager:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "Bucket VFS system not available"
                }, indent=2)
            )]
        
        # Get bucket list for statistics
        buckets_result = await bucket_manager.list_buckets()
        
        response = {
            "success": True,
            "system": {
                "available": BUCKET_VFS_AVAILABLE,
                "storage_path": storage_path,
                "duckdb_integration": bucket_manager.enable_duckdb_integration if bucket_manager else False
            }
        }
        
        if buckets_result["success"]:
            buckets_data = buckets_result.get("data", {})
            buckets = buckets_data.get("buckets", [])
            
            # Calculate statistics
            total_files = sum(bucket.get("file_count", 0) for bucket in buckets)
            total_size = sum(bucket.get("size_bytes", 0) for bucket in buckets)
            
            bucket_types = {}
            vfs_structures = {}
            
            for bucket in buckets:
                bucket_type = bucket.get("type", "unknown")
                vfs_structure = bucket.get("vfs_structure", "unknown")
                
                bucket_types[bucket_type] = bucket_types.get(bucket_type, 0) + 1
                vfs_structures[vfs_structure] = vfs_structures.get(vfs_structure, 0) + 1
            
            response["statistics"] = {
                "total_buckets": len(buckets),
                "total_files": total_files,
                "total_size_bytes": total_size,
                "bucket_types": bucket_types,
                "vfs_structures": vfs_structures
            }
            
            if include_health:
                # Check health of each bucket
                healthy_buckets = 0
                for bucket in buckets:
                    # Simple health check - bucket has root CID
                    if bucket.get("root_cid"):
                        healthy_buckets += 1
                
                response["health"] = {
                    "healthy_buckets": healthy_buckets,
                    "total_buckets": len(buckets),
                    "health_percentage": (healthy_buckets / len(buckets) * 100) if buckets else 100
                }
        else:
            response["error"] = buckets_result.get("error", "Failed to get bucket statistics")
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
        
    except Exception as e:
        error_response = {
            "success": False,
            "error": f"Exception in bucket_status: {str(e)}",
            "traceback": traceback.format_exc()
        }
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

# Tool handler mapping
BUCKET_TOOL_HANDLERS = {
    "bucket_create": handle_bucket_create,
    "bucket_list": handle_bucket_list,
    "bucket_delete": handle_bucket_delete,
    "bucket_add_file": handle_bucket_add_file,
    "bucket_export_car": handle_bucket_export_car,
    "bucket_cross_query": handle_bucket_cross_query,
    "bucket_get_info": handle_bucket_get_info,
    "bucket_status": handle_bucket_status
}

async def handle_bucket_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle bucket VFS tool calls."""
    handler = BUCKET_TOOL_HANDLERS.get(name)
    if handler:
        return await handler(arguments)
    else:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": f"Unknown bucket tool: {name}"
            }, indent=2)
        )]
