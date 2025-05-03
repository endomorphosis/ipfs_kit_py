"""IPFS MCP Tools Integration - Enhanced with specific implementations"""

import os
import sys
import json
import logging
import tempfile
import base64
from datetime import datetime
from ipfs_tools_registry import IPFS_TOOLS

logger = logging.getLogger(__name__)

# Try to import IPFS extensions
try:
    sys.path.append(os.path.join(os.getcwd(), 'ipfs_kit_py'))
    from ipfs_kit_py.mcp.ipfs_extensions import (
        add_content, cat, pin_add, pin_rm, pin_ls, get_version,
        files_ls, files_mkdir, files_write, files_read,
        files_rm, files_stat, files_cp, files_mv, files_flush
    )
    IPFS_EXTENSIONS_AVAILABLE = True
    logger.info("Successfully imported IPFS extensions")
except ImportError as e:
    IPFS_EXTENSIONS_AVAILABLE = False
    logger.warning(f"Could not import IPFS extensions: {e}. Using mock implementations.")
    
    # Mock implementations for when the extensions aren't available
    def add_content(content, **kwargs):
        logger.warning("Using mock implementation of add_content")
        return {"Hash": "QmMockHash", "Size": len(content) if isinstance(content, bytes) else len(content.encode())}
        
    def cat(ipfs_path, **kwargs):
        logger.warning("Using mock implementation of cat")
        return b"Mock content for " + ipfs_path.encode() if isinstance(ipfs_path, str) else ipfs_path
        
    def pin_add(ipfs_path, **kwargs):
        logger.warning("Using mock implementation of pin_add")
        return {"Pins": [ipfs_path]}
        
    def pin_rm(ipfs_path, **kwargs):
        logger.warning("Using mock implementation of pin_rm")
        return {"Pins": [ipfs_path]}
        
    def pin_ls(ipfs_path=None, **kwargs):
        logger.warning("Using mock implementation of pin_ls")
        return {"Keys": {"QmMockHash": {"Type": "recursive"}}}
        
    def get_version(**kwargs):
        logger.warning("Using mock implementation of get_version")
        return {"Version": "mock-0.11.0", "Commit": "mock"}
        
    def files_ls(path="/", **kwargs):
        logger.warning("Using mock implementation of files_ls")
        return {"Entries": [{"Name": "mock-file.txt", "Type": 0, "Size": 123}]}
        
    def files_mkdir(path, **kwargs):
        logger.warning("Using mock implementation of files_mkdir")
        return {}
        
    def files_write(path, content, **kwargs):
        logger.warning("Using mock implementation of files_write")
        return {}
        
    def files_read(path, **kwargs):
        logger.warning("Using mock implementation of files_read")
        return b"Mock content for " + path.encode() if isinstance(path, str) else path
        
    def files_rm(path, **kwargs):
        logger.warning("Using mock implementation of files_rm")
        return {}
        
    def files_stat(path, **kwargs):
        logger.warning("Using mock implementation of files_stat")
        return {"Hash": "QmMockHash", "Size": 123, "Type": "file"}
        
    def files_cp(source, dest, **kwargs):
        logger.warning("Using mock implementation of files_cp")
        return {}
        
    def files_mv(source, dest, **kwargs):
        logger.warning("Using mock implementation of files_mv")
        return {}
        
    def files_flush(path="/", **kwargs):
        logger.warning("Using mock implementation of files_flush")
        return {"Hash": "QmMockHash"}

def register_ipfs_tools(mcp_server):
    """Register all IPFS tools with the MCP server with proper implementations"""
    logger.info(f"Registering {len(IPFS_TOOLS)} IPFS tools with MCP server")

    # Register each tool with specific implementations
    for tool in IPFS_TOOLS:
        tool_name = tool["name"]
        tool_schema = tool.get("schema", {})
        description = tool.get("description", f"IPFS tool: {tool_name}")
        
        # Determine the correct handler to use based on the tool name
        if IPFS_EXTENSIONS_AVAILABLE:
            # Use real implementation if available
            if tool_name == "ipfs_add":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_add_handler(ctx, content, filename=None, pin=True):
                    await ctx.info(f"Adding content to IPFS{' and pinning' if pin else ''}")
                    result = await add_content(content, filename, pin)
                    if result.get("success"):
                        await ctx.info(f"Successfully added content with CID: {result.get('cid')}")
                    else:
                        await ctx.error(f"Failed to add content: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_cat":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_cat_handler(ctx, cid):
                    await ctx.info(f"Retrieving content for CID: {cid}")
                    result = await cat(cid)
                    if result.get("success"):
                        await ctx.info(f"Successfully retrieved content ({result.get('size', 0)} bytes)")
                    else:
                        await ctx.error(f"Failed to retrieve content: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_pin":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_pin_handler(ctx, cid, recursive=True):
                    await ctx.info(f"Pinning CID: {cid} (recursive={recursive})")
                    result = await pin_add(cid, recursive)
                    if result.get("success"):
                        await ctx.info(f"Successfully pinned {cid}")
                    else:
                        await ctx.error(f"Failed to pin content: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_unpin":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_unpin_handler(ctx, cid, recursive=True):
                    await ctx.info(f"Unpinning CID: {cid} (recursive={recursive})")
                    result = await pin_rm(cid, recursive)
                    if result.get("success"):
                        await ctx.info(f"Successfully unpinned {cid}")
                    else:
                        await ctx.error(f"Failed to unpin content: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_list_pins":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_list_pins_handler(ctx, type_filter="all"):
                    await ctx.info(f"Listing pins (filter={type_filter})")
                    result = await pin_ls(type_filter=type_filter)
                    if result.get("success"):
                        pin_count = len(result.get("pins", []))
                        await ctx.info(f"Found {pin_count} pinned items")
                    else:
                        await ctx.error(f"Failed to list pins: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_version":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_version_handler(ctx):
                    await ctx.info("Getting IPFS version information")
                    result = await get_version()
                    if result.get("success"):
                        await ctx.info(f"IPFS version: {result.get('version')}")
                    else:
                        await ctx.error(f"Failed to get IPFS version: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_files_ls":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_files_ls_handler(ctx, path="/", long=False):
                    await ctx.info(f"Listing files in MFS path: {path}")
                    result = await files_ls(path, long)
                    if result.get("success"):
                        entry_count = len(result.get("entries", []))
                        await ctx.info(f"Found {entry_count} entries in {path}")
                    else:
                        await ctx.error(f"Failed to list files: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_files_mkdir":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_files_mkdir_handler(ctx, path, parents=True):
                    await ctx.info(f"Creating directory in MFS: {path}")
                    result = await files_mkdir(path, parents)
                    if result.get("success"):
                        await ctx.info(f"Successfully created directory {path}")
                    else:
                        await ctx.error(f"Failed to create directory: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_files_write":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_files_write_handler(ctx, path, content, create=True, truncate=True):
                    await ctx.info(f"Writing to file in MFS: {path}")
                    result = await files_write(path, content, create, truncate)
                    if result.get("success"):
                        await ctx.info(f"Successfully wrote {result.get('size', len(content))} bytes to {path}")
                    else:
                        await ctx.error(f"Failed to write file: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_files_read":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_files_read_handler(ctx, path, offset=0, count=-1):
                    await ctx.info(f"Reading file from MFS: {path}")
                    result = await files_read(path, offset, count)
                    if result.get("success"):
                        await ctx.info(f"Successfully read {result.get('size', 0)} bytes from {path}")
                    else:
                        await ctx.error(f"Failed to read file: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_files_rm":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_files_rm_handler(ctx, path, recursive=False, force=False):
                    await ctx.info(f"Removing {path} from MFS")
                    result = await files_rm(path, recursive, force)
                    if result.get("success"):
                        await ctx.info(f"Successfully removed {path}")
                    else:
                        await ctx.error(f"Failed to remove {path}: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_files_stat":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_files_stat_handler(ctx, path):
                    await ctx.info(f"Getting stats for MFS path: {path}")
                    result = await files_stat(path)
                    if result.get("success"):
                        await ctx.info(f"Successfully got stats for {path}")
                    else:
                        await ctx.error(f"Failed to get stats: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_files_cp":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_files_cp_handler(ctx, source, dest):
                    await ctx.info(f"Copying {source} to {dest} in MFS")
                    result = await files_cp(source, dest)
                    if result.get("success"):
                        await ctx.info(f"Successfully copied {source} to {dest}")
                    else:
                        await ctx.error(f"Failed to copy: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_files_mv":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_files_mv_handler(ctx, source, dest):
                    await ctx.info(f"Moving {source} to {dest} in MFS")
                    result = await files_mv(source, dest)
                    if result.get("success"):
                        await ctx.info(f"Successfully moved {source} to {dest}")
                    else:
                        await ctx.error(f"Failed to move: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            elif tool_name == "ipfs_files_flush":
                @mcp_server.tool(name=tool_name, description=description)
                async def ipfs_files_flush_handler(ctx, path="/"):
                    await ctx.info(f"Flushing MFS path: {path}")
                    result = await files_flush(path)
                    if result.get("success"):
                        await ctx.info(f"Successfully flushed {path} to {result.get('cid', 'IPFS')}")
                    else:
                        await ctx.error(f"Failed to flush: {result.get('error')}")
                    return result
                logger.info(f"Registered tool with real implementation: {tool_name}")
                
            else:
                # Generic mock implementation for other tools
                @mcp_server.tool(name=tool_name, description=description)
                async def generic_tool_handler(ctx):
                    # Extract parameters from context
                    params = ctx.params
                    await ctx.info(f"Called {tool_name} with params: {params}")
                    await ctx.warning(f"Using mock implementation for {tool_name}")
                    return {
                        "success": True,
                        "warning": "Mock implementation",
                        "timestamp": datetime.now().isoformat(),
                        "tool": tool_name,
                        "params": params
                    }
                # Rename the function to avoid name collisions
                generic_tool_handler.__name__ = f"ipfs_{tool_name}_handler"
                logger.info(f"Registered tool with mock implementation: {tool_name}")
        else:
            # Use mock implementations for all tools
            @mcp_server.tool(name=tool_name, description=description)
            async def mock_tool_handler(ctx):
                # Extract parameters from context
                params = ctx.params
                await ctx.info(f"Called {tool_name} with params: {params}")
                await ctx.warning("Using mock implementation (IPFS extensions not available)")
                return {
                    "success": True,
                    "warning": "Mock implementation (IPFS extensions not available)",
                    "timestamp": datetime.now().isoformat(),
                    "tool": tool_name,
                    "params": params
                }
            # Rename the function to avoid name collisions
            mock_tool_handler.__name__ = f"ipfs_{tool_name}_handler"
            logger.info(f"Registered tool with mock implementation: {tool_name}")

    logger.info("✅ Successfully registered all IPFS tools")
    return True
