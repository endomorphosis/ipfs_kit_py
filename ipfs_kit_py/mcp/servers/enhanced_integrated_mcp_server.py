"""
Enhanced MCP Server with Complete Parquet-IPLD-VFS Integration.

This is the final integration server that combines:
1. IPFS Kit with daemon management
2. Parquet-IPLD bridge for structured data storage
3. Virtual filesystem integration
4. Arrow-based analytics
5. Tiered caching with ARC
6. Write-ahead logging
7. Metadata replication
8. Comprehensive MCP tools
"""

import warnings
warnings.warn(
    "This MCP server is deprecated. Use ipfs_kit_py.mcp.servers.unified_mcp_server instead. "
    "See docs/MCP_SERVER_MIGRATION_GUIDE.md for migration instructions. "
    "This module will be removed in approximately 6 months.",
    DeprecationWarning,
    stacklevel=2
)


import anyio
import json
import logging
import os
import sys
import tempfile
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

# Standard MCP imports
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource

# Core IPFS Kit imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from ipfs_kit import ipfs_kit
    from daemon_config_manager import DaemonConfigManager
    from parquet_ipld_bridge import ParquetIPLDBridge
    from parquet_vfs_integration import create_parquet_vfs_integration, ParquetVirtualFileSystem
    from arrow_metadata_index import ArrowMetadataIndex
    from tiered_cache_manager import TieredCacheManager
    from ipfs_kit_py.storage_wal import StorageWriteAheadLog
    from ipfs_kit_py.fs_journal_replication import MetadataReplicationManager
    IPFS_KIT_AVAILABLE = True
except ImportError as e:
    IPFS_KIT_AVAILABLE = False
    print(f"IPFS Kit components not available: {e}")

# Bucket VFS MCP tools import
try:
    from bucket_vfs_mcp_tools import create_bucket_tools, handle_bucket_tool, BUCKET_VFS_AVAILABLE
    BUCKET_MCP_AVAILABLE = True
except ImportError as e:
    BUCKET_MCP_AVAILABLE = False
    print(f"Bucket VFS MCP tools not available: {e}")

# VFS Version Tracking MCP tools import
try:
    from vfs_version_mcp_tools import get_vfs_version_tools, get_vfs_version_handlers, VFS_TRACKER_AVAILABLE
    VFS_VERSION_MCP_AVAILABLE = True
except ImportError as e:
    VFS_VERSION_MCP_AVAILABLE = False
    print(f"VFS Version Tracking MCP tools not available: {e}")

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    import pandas as pd
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

try:
    import fsspec
    FSSPEC_AVAILABLE = True
except ImportError:
    FSSPEC_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global server state
server_state = {
    "ipfs_kit": None,
    "daemon_manager": None,
    "parquet_bridge": None,
    "parquet_vfs": None,
    "cache_manager": None,
    "wal_manager": None,
    "replication_manager": None,
    "metadata_index": None,
    "initialized": False
}


def create_result_dict(success: bool, **kwargs) -> Dict[str, Any]:
    """Create standardized result dictionary."""
    result = {"success": success}
    result.update(kwargs)
    return result


def handle_error(operation: str, error: Exception) -> Dict[str, Any]:
    """Handle and log errors consistently."""
    error_msg = f"{operation} failed: {str(error)}"
    logger.error(error_msg)
    logger.debug(traceback.format_exc())
    return create_result_dict(False, error=error_msg, error_type=type(error).__name__)


async def initialize_enhanced_server():
    """Initialize all server components."""
    try:
        if not IPFS_KIT_AVAILABLE:
            raise ImportError("IPFS Kit is not available")
        
        if not ARROW_AVAILABLE:
            raise ImportError("PyArrow is not available")
        
        logger.info("Initializing enhanced IPFS-Parquet MCP server...")
        
        # Initialize daemon manager
        daemon_manager = DaemonConfigManager()
        server_state["daemon_manager"] = daemon_manager
        
        # Initialize IPFS Kit with auto-daemon management
        ipfs_instance = ipfs_kit(auto_daemon=True)
        server_state["ipfs_kit"] = ipfs_instance
        
        # Initialize storage components
        storage_path = os.path.expanduser("~/.ipfs_parquet_storage")
        os.makedirs(storage_path, exist_ok=True)
        
        # Initialize metadata index
        metadata_index = ArrowMetadataIndex(storage_path=storage_path)
        server_state["metadata_index"] = metadata_index
        
        # Initialize cache manager
        cache_manager = TieredCacheManager(
            storage_path=storage_path,
            max_memory_gb=1.0,
            max_disk_gb=10.0
        )
        server_state["cache_manager"] = cache_manager
        
        # Initialize WAL manager
        wal_manager = StorageWriteAheadLog(storage_path=storage_path)
        server_state["wal_manager"] = wal_manager
        
        # Initialize replication manager
        replication_manager = MetadataReplicationManager(storage_path=storage_path)
        server_state["replication_manager"] = replication_manager
        
        # Initialize Parquet-IPLD bridge and VFS
        parquet_bridge, parquet_vfs = create_parquet_vfs_integration(
            ipfs_client=ipfs_instance.client if hasattr(ipfs_instance, 'client') else None,
            storage_path=storage_path,
            cache_manager=cache_manager,
            wal_manager=wal_manager,
            replication_manager=replication_manager,
            metadata_index=metadata_index
        )
        
        server_state["parquet_bridge"] = parquet_bridge
        server_state["parquet_vfs"] = parquet_vfs
        
        server_state["initialized"] = True
        logger.info("Enhanced server initialization completed successfully")
        
        return create_result_dict(True, message="Server initialized")
        
    except Exception as e:
        error_result = handle_error("Server initialization", e)
        server_state["initialized"] = False
        return error_result


# Create the MCP server
app = Server("enhanced-ipfs-parquet-server")


@app.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List all available tools."""
    tools = [
        # Core IPFS tools
        Tool(
            name="ipfs_add",
            description="Add content to IPFS and return the CID",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to add to IPFS"},
                    "file_path": {"type": "string", "description": "Path to file to add to IPFS"}
                }
            }
        ),
        Tool(
            name="ipfs_cat",
            description="Retrieve and display content from IPFS",
            inputSchema={
                "type": "object",
                "properties": {
                    "cid": {"type": "string", "description": "IPFS CID to retrieve content from"}
                },
                "required": ["cid"]
            }
        ),
        Tool(
            name="ipfs_ls",
            description="List directory contents for an IPFS path",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "IPFS path to list (e.g., /ipfs/<cid>)"}
                },
                "required": ["path"]
            }
        ),
        
        # Parquet storage tools
        Tool(
            name="parquet_store_dataframe",
            description="Store a DataFrame as Parquet with IPLD addressing",
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "JSON data or CSV data to store"},
                    "format": {"type": "string", "enum": ["json", "csv"], "description": "Data format"},
                    "name": {"type": "string", "description": "Optional dataset name"},
                    "metadata": {"type": "object", "description": "Additional metadata"}
                },
                "required": ["data", "format"]
            }
        ),
        Tool(
            name="parquet_retrieve_dataframe",
            description="Retrieve a DataFrame from Parquet storage",
            inputSchema={
                "type": "object",
                "properties": {
                    "cid": {"type": "string", "description": "Content identifier of the dataset"},
                    "columns": {"type": "array", "items": {"type": "string"}, "description": "Specific columns to retrieve"},
                    "filters": {"type": "array", "description": "PyArrow-compatible filters"},
                    "format": {"type": "string", "enum": ["json", "csv", "parquet"], "default": "json", "description": "Output format"}
                },
                "required": ["cid"]
            }
        ),
        Tool(
            name="parquet_query_datasets",
            description="Query datasets using SQL",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL query to execute"},
                    "format": {"type": "string", "enum": ["json", "csv"], "default": "json", "description": "Output format"}
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="parquet_list_datasets",
            description="List all stored datasets",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        
        # VFS tools
        Tool(
            name="vfs_ls",
            description="List VFS directory contents",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "/", "description": "VFS path to list"},
                    "detail": {"type": "boolean", "default": True, "description": "Show detailed information"}
                }
            }
        ),
        Tool(
            name="vfs_cat",
            description="Read file content from VFS",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "VFS path to read"},
                    "encoding": {"type": "string", "default": "utf-8", "description": "File encoding"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="vfs_info",
            description="Get file/directory information from VFS",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "VFS path to inspect"}
                },
                "required": ["path"]
            }
        ),
        
        # System health and diagnostics
        Tool(
            name="system_health",
            description="Get comprehensive system health status",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="cache_stats",
            description="Get cache performance statistics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="wal_status",
            description="Get write-ahead log status",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]
    
    # Add bucket VFS tools if available
    if BUCKET_MCP_AVAILABLE:
        bucket_tools = create_bucket_tools()
        tools.extend(bucket_tools)
    
    # Add VFS version tracking tools if available
    if VFS_VERSION_MCP_AVAILABLE:
        vfs_version_tools = get_vfs_version_tools()
        tools.extend(vfs_version_tools)
    
    return tools


@app.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    try:
        # Ensure server is initialized
        if not server_state["initialized"]:
            init_result = await initialize_enhanced_server()
            if not init_result["success"]:
                return [TextContent(type="text", text=f"Server initialization failed: {init_result.get('error')}")]
        
        # Route to appropriate handler
        if name.startswith("ipfs_"):
            result = await handle_ipfs_tool(name, arguments)
        elif name.startswith("parquet_"):
            result = await handle_parquet_tool(name, arguments)
        elif name.startswith("vfs_") and not name.startswith("vfs_version"):
            result = await handle_vfs_tool(name, arguments)
        elif name.startswith("bucket_") and BUCKET_MCP_AVAILABLE:
            # Handle bucket VFS tools
            tool_result = await handle_bucket_tool(name, arguments)
            # Convert TextContent result to dict for consistency
            if tool_result and len(tool_result) > 0:
                return tool_result  # Return TextContent directly for bucket tools
            else:
                result = create_result_dict(False, error="Empty result from bucket tool")
        elif name.startswith("vfs_") and VFS_VERSION_MCP_AVAILABLE:
            # Handle VFS version tracking tools
            vfs_handlers = get_vfs_version_handlers()
            if name in vfs_handlers:
                tool_result = await vfs_handlers[name](arguments)
                if tool_result and len(tool_result) > 0:
                    return tool_result  # Return TextContent directly for VFS tools
                else:
                    result = create_result_dict(False, error="Empty result from VFS tool")
            else:
                result = create_result_dict(False, error=f"Unknown VFS version tool: {name}")
        elif name in ["system_health", "cache_stats", "wal_status"]:
            result = await handle_diagnostic_tool(name, arguments)
        else:
            result = create_result_dict(False, error=f"Unknown tool: {name}")
        
        # For non-bucket/VFS tools, wrap result in TextContent
        if name.startswith("bucket_") or (name.startswith("vfs_") and VFS_VERSION_MCP_AVAILABLE):
            return tool_result if tool_result else [TextContent(type="text", text=json.dumps({"success": False, "error": "No result"}, indent=2))]
        else:
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
    except Exception as e:
        error_result = handle_error(f"Tool call {name}", e)
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


async def handle_ipfs_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle IPFS-related tools."""
    ipfs = server_state["ipfs_kit"]
    if not ipfs:
        return create_result_dict(False, error="IPFS Kit not initialized")
    
    try:
        if name == "ipfs_add":
            if "content" in arguments:
                result = ipfs.add(arguments["content"])
            elif "file_path" in arguments:
                result = ipfs.add_file(arguments["file_path"])
            else:
                return create_result_dict(False, error="Either content or file_path required")
            
            return create_result_dict(True, result=result)
        
        elif name == "ipfs_cat":
            result = ipfs.cat(arguments["cid"])
            return create_result_dict(True, content=result)
        
        elif name == "ipfs_ls":
            result = ipfs.ls(arguments["path"])
            return create_result_dict(True, contents=result)
        
        else:
            return create_result_dict(False, error=f"Unknown IPFS tool: {name}")
            
    except Exception as e:
        return handle_error(f"IPFS tool {name}", e)


async def handle_parquet_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Parquet-related tools."""
    bridge = server_state["parquet_bridge"]
    if not bridge:
        return create_result_dict(False, error="Parquet bridge not initialized")
    
    try:
        if name == "parquet_store_dataframe":
            # Convert input data to DataFrame
            data_format = arguments["format"]
            data_content = arguments["data"]
            
            if data_format == "json":
                if isinstance(data_content, str):
                    data_content = json.loads(data_content)
                df = pd.DataFrame(data_content)
            elif data_format == "csv":
                import io
                df = pd.read_csv(io.StringIO(data_content))
            else:
                return create_result_dict(False, error=f"Unsupported format: {data_format}")
            
            # Store the DataFrame
            result = bridge.store_dataframe(
                df,
                name=arguments.get("name"),
                metadata=arguments.get("metadata")
            )
            return result
        
        elif name == "parquet_retrieve_dataframe":
            result = bridge.retrieve_dataframe(
                arguments["cid"],
                columns=arguments.get("columns"),
                filters=arguments.get("filters")
            )
            
            if result["success"]:
                # Convert to requested format
                output_format = arguments.get("format", "json")
                table = result["table"]
                
                if output_format == "json":
                    df = table.to_pandas()
                    result["data"] = df.to_dict(orient="records")
                elif output_format == "csv":
                    df = table.to_pandas()
                    result["data"] = df.to_csv(index=False)
                elif output_format == "parquet":
                    # Return metadata about the Parquet file
                    result["data"] = f"Parquet file at: {result['storage_path']}"
                
                # Remove the table from result to avoid serialization issues
                result.pop("table", None)
            
            return result
        
        elif name == "parquet_query_datasets":
            result = bridge.query_datasets(arguments["sql"])
            
            if result["success"]:
                # Convert to requested format
                output_format = arguments.get("format", "json")
                table = result["result"]
                
                if output_format == "json":
                    df = table.to_pandas()
                    result["data"] = df.to_dict(orient="records")
                elif output_format == "csv":
                    df = table.to_pandas()
                    result["data"] = df.to_csv(index=False)
                
                # Remove the table from result
                result.pop("result", None)
            
            return result
        
        elif name == "parquet_list_datasets":
            return bridge.list_datasets()
        
        else:
            return create_result_dict(False, error=f"Unknown Parquet tool: {name}")
            
    except Exception as e:
        return handle_error(f"Parquet tool {name}", e)


async def handle_vfs_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle VFS-related tools."""
    vfs = server_state["parquet_vfs"]
    if not vfs:
        return create_result_dict(False, error="Parquet VFS not initialized")
    
    try:
        if name == "vfs_ls":
            path = arguments.get("path", "/")
            detail = arguments.get("detail", True)
            entries = vfs.ls(path, detail=detail)
            return create_result_dict(True, entries=entries)
        
        elif name == "vfs_cat":
            path = arguments["path"]
            encoding = arguments.get("encoding", "utf-8")
            
            try:
                content_bytes = vfs.cat_file(path)
                content = content_bytes.decode(encoding)
                return create_result_dict(True, content=content)
            except UnicodeDecodeError:
                # Return as base64 if decoding fails
                import base64
                content_b64 = base64.b64encode(content_bytes).decode('ascii')
                return create_result_dict(True, content=content_b64, encoding="base64")
        
        elif name == "vfs_info":
            path = arguments["path"]
            info = vfs.info(path)
            return create_result_dict(True, info=info)
        
        else:
            return create_result_dict(False, error=f"Unknown VFS tool: {name}")
            
    except Exception as e:
        return handle_error(f"VFS tool {name}", e)


async def handle_diagnostic_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle diagnostic tools."""
    try:
        if name == "system_health":
            health_status = {
                "server_initialized": server_state["initialized"],
                "ipfs_kit_available": server_state["ipfs_kit"] is not None,
                "parquet_bridge_available": server_state["parquet_bridge"] is not None,
                "parquet_vfs_available": server_state["parquet_vfs"] is not None,
                "cache_manager_available": server_state["cache_manager"] is not None,
                "wal_manager_available": server_state["wal_manager"] is not None,
                "replication_manager_available": server_state["replication_manager"] is not None,
                "metadata_index_available": server_state["metadata_index"] is not None,
                "arrow_available": ARROW_AVAILABLE,
                "fsspec_available": FSSPEC_AVAILABLE
            }
            
            # Add IPFS daemon status if available
            ipfs = server_state["ipfs_kit"]
            if ipfs:
                try:
                    daemon_status = ipfs.system_health()
                    health_status["ipfs_daemon"] = daemon_status
                except:
                    health_status["ipfs_daemon"] = {"status": "unknown"}
            
            return create_result_dict(True, health=health_status)
        
        elif name == "cache_stats":
            cache_manager = server_state["cache_manager"]
            if cache_manager:
                stats = cache_manager.get_performance_metrics()
                return create_result_dict(True, stats=stats)
            else:
                return create_result_dict(False, error="Cache manager not available")
        
        elif name == "wal_status":
            wal_manager = server_state["wal_manager"]
            if wal_manager:
                status = wal_manager.get_status()
                return create_result_dict(True, status=status)
            else:
                return create_result_dict(False, error="WAL manager not available")
        
        else:
            return create_result_dict(False, error=f"Unknown diagnostic tool: {name}")
            
    except Exception as e:
        return handle_error(f"Diagnostic tool {name}", e)


async def main():
    """Main server entry point."""
    logger.info("Starting Enhanced IPFS-Parquet MCP Server")
    
    # Pre-initialize the server
    init_result = await initialize_enhanced_server()
    if not init_result["success"]:
        logger.error(f"Failed to initialize server: {init_result.get('error')}")
        return
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, 
            write_stream, 
            InitializationOptions(
                server_name="enhanced-ipfs-parquet-server",
                server_version="1.0.0",
                capabilities={}
            )
        )


if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        logger.info("Server shutdown by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.debug(traceback.format_exc())
