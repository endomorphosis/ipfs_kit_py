#!/usr/bin/env python3
"""
Direct IPFS MCP Fix

This script creates a new implementation for the IPFS tools in the MCP server.
"""

import logging
import os
import traceback

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("direct-fix")

def create_direct_ipfs_tools():
    """Create direct IPFS tools implementation."""
    filepath = "/home/barberb/ipfs_kit_py/direct_ipfs_tools.py"
    
    content = """#!/usr/bin/env python3
'''
Direct IPFS Tools Implementation

This module provides direct implementation of IPFS tools for the MCP server.
'''

import os
import sys
import logging
import inspect
import hashlib
import traceback
import asyncio
from typing import Dict, Any, Callable, Optional, Union, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("direct-ipfs-tools")

# Try to import the real implementations
try:
    from ipfs_kit_py.mcp.ipfs_extensions import (
        add_content, cat, pin_add, pin_rm, pin_ls, get_version,
        files_ls, files_mkdir, files_write, files_read,
        files_rm, files_stat, files_cp, files_mv, files_flush
    )
    using_real_implementations = True
    logger.info("✅ Using real IPFS implementations")
except ImportError as e:
    using_real_implementations = False
    logger.warning(f"⚠️ Using mock IPFS implementations: {e}")

# Mock implementations
async def mock_add_content(content, filename=None, pin=True):
    """Mock implementation of add_content."""
    logger.info(f"[MOCK] Adding content to IPFS (length: {len(content) if isinstance(content, str) else 'binary'})")
    
    # Generate a mock CID based on content
    if isinstance(content, str):
        content_hash = hashlib.sha256(content.encode()).hexdigest()
    elif isinstance(content, bytes):
        content_hash = hashlib.sha256(content).hexdigest()
    else:
        content_str = str(content)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()
        
    mock_cid = f"Qm{content_hash[:38]}"
    
    return {
        "success": True,
        "cid": mock_cid,
        "name": filename or "unnamed_file",
        "size": len(content) if isinstance(content, str) else len(content),
        "pinned": pin,
        "warning": "This is a mock implementation"
    }

async def mock_cat(cid):
    """Mock implementation of cat."""
    logger.info(f"[MOCK] Retrieving content for CID: {cid}")
    
    mock_content = f"This is mock content for CID: {cid}"
    
    return {
        "success": True,
        "cid": cid,
        "content": mock_content,
        "warning": "This is a mock implementation"
    }

async def mock_pin_add(cid, recursive=True):
    """Mock implementation of pin_add."""
    logger.info(f"[MOCK] Pinning CID: {cid} (recursive={recursive})")
    
    return {
        "success": True,
        "cid": cid,
        "pins": [cid],
        "recursive": recursive,
        "warning": "This is a mock implementation"
    }

async def mock_pin_rm(cid, recursive=True):
    """Mock implementation of pin_rm."""
    logger.info(f"[MOCK] Unpinning CID: {cid} (recursive={recursive})")
    
    return {
        "success": True,
        "cid": cid,
        "pins": [cid],
        "recursive": recursive,
        "warning": "This is a mock implementation"
    }

async def mock_pin_ls(cid=None, type_filter="all"):
    """Mock implementation of pin_ls."""
    logger.info(f"[MOCK] Listing pins (cid={cid}, filter={type_filter})")
    
    pins = [f"QmMock{i}" for i in range(5)]
    if cid:
        pins.append(cid)
    
    return {
        "success": True,
        "pins": pins,
        "warning": "This is a mock implementation"
    }

async def mock_files_mkdir(path, parents=True):
    """Mock implementation of files_mkdir."""
    logger.info(f"[MOCK] Creating directory: {path} (parents={parents})")
    
    return {
        "success": True,
        "path": path,
        "warning": "This is a mock implementation"
    }

async def mock_files_write(path, content, create=True, truncate=True, offset=0):
    """Mock implementation of files_write."""
    logger.info(f"[MOCK] Writing to file: {path} (create={create}, truncate={truncate}, offset={offset})")
    
    return {
        "success": True,
        "path": path,
        "size": len(content) if isinstance(content, str) else len(content),
        "warning": "This is a mock implementation"
    }

async def mock_files_read(path, offset=0, count=-1):
    """Mock implementation of files_read."""
    logger.info(f"[MOCK] Reading file: {path} (offset={offset}, count={count})")
    
    mock_content = f"This is mock content for file: {path}"
    
    return {
        "success": True,
        "path": path,
        "content": mock_content,
        "size": len(mock_content),
        "warning": "This is a mock implementation"
    }

async def mock_files_ls(path, long=False):
    """Mock implementation of files_ls."""
    logger.info(f"[MOCK] Listing directory: {path} (long={long})")
    
    entries = [
        {"name": "file1.txt", "type": "file", "size": 100},
        {"name": "file2.txt", "type": "file", "size": 200},
        {"name": "dir1", "type": "directory"}
    ]
    
    return {
        "success": True,
        "path": path,
        "entries": entries,
        "warning": "This is a mock implementation"
    }

async def mock_files_rm(path, recursive=False):
    """Mock implementation of files_rm."""
    logger.info(f"[MOCK] Removing path: {path} (recursive={recursive})")
    
    return {
        "success": True,
        "path": path,
        "warning": "This is a mock implementation"
    }

async def mock_files_stat(path):
    """Mock implementation of files_stat."""
    logger.info(f"[MOCK] Getting stat for path: {path}")
    
    return {
        "success": True,
        "path": path,
        "size": 100,
        "cid": f"QmMock{hashlib.sha256(path.encode()).hexdigest()[:10]}",
        "type": "file" if not path.endswith("/") else "directory",
        "warning": "This is a mock implementation"
    }

async def mock_files_cp(source, dest):
    """Mock implementation of files_cp."""
    logger.info(f"[MOCK] Copying from {source} to {dest}")
    
    return {
        "success": True,
        "source": source,
        "dest": dest,
        "warning": "This is a mock implementation"
    }

async def mock_files_mv(source, dest):
    """Mock implementation of files_mv."""
    logger.info(f"[MOCK] Moving from {source} to {dest}")
    
    return {
        "success": True,
        "source": source,
        "dest": dest,
        "warning": "This is a mock implementation"
    }

# Use real implementations if available, otherwise use mock implementations
add = add_content if using_real_implementations else mock_add_content
cat_impl = cat if using_real_implementations else mock_cat
pin_add_impl = pin_add if using_real_implementations else mock_pin_add
pin_rm_impl = pin_rm if using_real_implementations else mock_pin_rm
pin_ls_impl = pin_ls if using_real_implementations else mock_pin_ls
files_mkdir_impl = files_mkdir if using_real_implementations else mock_files_mkdir
files_write_impl = files_write if using_real_implementations else mock_files_write
files_read_impl = files_read if using_real_implementations else mock_files_read
files_ls_impl = files_ls if using_real_implementations else mock_files_ls
files_rm_impl = files_rm if using_real_implementations else mock_files_rm
files_stat_impl = files_stat if using_real_implementations else mock_files_stat
files_cp_impl = files_cp if using_real_implementations else mock_files_cp
files_mv_impl = files_mv if using_real_implementations else mock_files_mv

# --- Tool Handlers ---

class SimpleContext:
    """Simple context object for tools."""
    
    def __init__(self, args_dict):
        self.arguments = args_dict
        for key, value in args_dict.items():
            setattr(self, key, value)

async def handle_ipfs_add(ctx):
    """Handle ipfs_add with robust parameter extraction."""
    logger.debug(f"Processing ipfs_add request: {type(ctx)}")
    
    # Extract content parameter
    content = None
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['content', 'data', 'text', 'value']:
            if param_name in ctx:
                content = ctx[param_name]
                break
        filename = ctx.get('filename', ctx.get('name', None))
        pin = ctx.get('pin', True)
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['content', 'data', 'text', 'value']:
                if param_name in args:
                    content = args[param_name]
                    break
            filename = args.get('filename', args.get('name', None))
            pin = args.get('pin', True)
        else:
            # Try direct attribute access
            for attr_name in ['content', 'data', 'text', 'value']:
                if hasattr(ctx, attr_name):
                    content = getattr(ctx, attr_name)
                    break
            filename = getattr(ctx, 'filename', getattr(ctx, 'name', None))
            pin = getattr(ctx, 'pin', True)
    
    if content is None:
        logger.error("Missing required parameter: content")
        return {"error": "Missing required parameter: content"}
    
    try:
        result = await add(content, filename, pin)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_add: {e}")
        return {"error": str(e)}

async def handle_ipfs_cat(ctx):
    """Handle ipfs_cat with robust parameter extraction."""
    logger.debug(f"Processing ipfs_cat request: {type(ctx)}")
    
    # Extract cid parameter
    cid = None
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['cid', 'hash', 'content_id']:
            if param_name in ctx:
                cid = ctx[param_name]
                break
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['cid', 'hash', 'content_id']:
                if param_name in args:
                    cid = args[param_name]
                    break
        else:
            # Try direct attribute access
            for attr_name in ['cid', 'hash', 'content_id']:
                if hasattr(ctx, attr_name):
                    cid = getattr(ctx, attr_name)
                    break
    
    if cid is None:
        logger.error("Missing required parameter: cid")
        return {"error": "Missing required parameter: cid"}
    
    try:
        result = await cat_impl(cid)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_cat: {e}")
        return {"error": str(e)}

async def handle_ipfs_pin_add(ctx):
    """Handle ipfs_pin_add with robust parameter extraction."""
    logger.debug(f"Processing ipfs_pin_add request: {type(ctx)}")
    
    # Extract parameters
    cid = None
    recursive = True
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['cid', 'hash', 'content_id']:
            if param_name in ctx:
                cid = ctx[param_name]
                break
        recursive = ctx.get('recursive', True)
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['cid', 'hash', 'content_id']:
                if param_name in args:
                    cid = args[param_name]
                    break
            recursive = args.get('recursive', True)
        else:
            # Try direct attribute access
            for attr_name in ['cid', 'hash', 'content_id']:
                if hasattr(ctx, attr_name):
                    cid = getattr(ctx, attr_name)
                    break
            recursive = getattr(ctx, 'recursive', True)
    
    if cid is None:
        logger.error("Missing required parameter: cid")
        return {"error": "Missing required parameter: cid"}
    
    try:
        result = await pin_add_impl(cid, recursive)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_pin_add: {e}")
        return {"error": str(e)}

async def handle_ipfs_pin_rm(ctx):
    """Handle ipfs_pin_rm with robust parameter extraction."""
    logger.debug(f"Processing ipfs_pin_rm request: {type(ctx)}")
    
    # Extract parameters
    cid = None
    recursive = True
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['cid', 'hash', 'content_id']:
            if param_name in ctx:
                cid = ctx[param_name]
                break
        recursive = ctx.get('recursive', True)
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['cid', 'hash', 'content_id']:
                if param_name in args:
                    cid = args[param_name]
                    break
            recursive = args.get('recursive', True)
        else:
            # Try direct attribute access
            for attr_name in ['cid', 'hash', 'content_id']:
                if hasattr(ctx, attr_name):
                    cid = getattr(ctx, attr_name)
                    break
            recursive = getattr(ctx, 'recursive', True)
    
    if cid is None:
        logger.error("Missing required parameter: cid")
        return {"error": "Missing required parameter: cid"}
    
    try:
        result = await pin_rm_impl(cid, recursive)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_pin_rm: {e}")
        return {"error": str(e)}

async def handle_ipfs_pin_ls(ctx):
    """Handle ipfs_pin_ls with robust parameter extraction."""
    logger.debug(f"Processing ipfs_pin_ls request: {type(ctx)}")
    
    # Extract parameters
    cid = None
    type_filter = "all"
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['cid', 'hash', 'content_id']:
            if param_name in ctx:
                cid = ctx[param_name]
                break
        type_filter = ctx.get('type', ctx.get('filter', 'all'))
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['cid', 'hash', 'content_id']:
                if param_name in args:
                    cid = args[param_name]
                    break
            type_filter = args.get('type', args.get('filter', 'all'))
        else:
            # Try direct attribute access
            for attr_name in ['cid', 'hash', 'content_id']:
                if hasattr(ctx, attr_name):
                    cid = getattr(ctx, attr_name)
                    break
            type_filter = getattr(ctx, 'type', getattr(ctx, 'filter', 'all'))
    
    try:
        result = await pin_ls_impl(cid, type_filter)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_pin_ls: {e}")
        return {"error": str(e)}

async def handle_ipfs_files_mkdir(ctx):
    """Handle ipfs_files_mkdir with robust parameter extraction."""
    logger.debug(f"Processing ipfs_files_mkdir request: {type(ctx)}")
    
    # Extract parameters
    path = None
    parents = True
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['path', 'dir_path', 'directory']:
            if param_name in ctx:
                path = ctx[param_name]
                break
        parents = ctx.get('parents', ctx.get('p', True))
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['path', 'dir_path', 'directory']:
                if param_name in args:
                    path = args[param_name]
                    break
            parents = args.get('parents', args.get('p', True))
        else:
            # Try direct attribute access
            for attr_name in ['path', 'dir_path', 'directory']:
                if hasattr(ctx, attr_name):
                    path = getattr(ctx, attr_name)
                    break
            parents = getattr(ctx, 'parents', getattr(ctx, 'p', True))
    
    if path is None:
        logger.error("Missing required parameter: path")
        return {"error": "Missing required parameter: path"}
    
    try:
        result = await files_mkdir_impl(path, parents)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_files_mkdir: {e}")
        return {"error": str(e)}

async def handle_ipfs_files_write(ctx):
    """Handle ipfs_files_write with robust parameter extraction."""
    logger.debug(f"Processing ipfs_files_write request: {type(ctx)}")
    
    # Extract parameters
    path = None
    content = None
    create = True
    truncate = True
    offset = 0
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['path', 'file_path', 'filepath']:
            if param_name in ctx:
                path = ctx[param_name]
                break
        for param_name in ['content', 'data', 'text', 'value']:
            if param_name in ctx:
                content = ctx[param_name]
                break
        create = ctx.get('create', True)
        truncate = ctx.get('truncate', True)
        offset = ctx.get('offset', 0)
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['path', 'file_path', 'filepath']:
                if param_name in args:
                    path = args[param_name]
                    break
            for param_name in ['content', 'data', 'text', 'value']:
                if param_name in args:
                    content = args[param_name]
                    break
            create = args.get('create', True)
            truncate = args.get('truncate', True)
            offset = args.get('offset', 0)
        else:
            # Try direct attribute access
            for attr_name in ['path', 'file_path', 'filepath']:
                if hasattr(ctx, attr_name):
                    path = getattr(ctx, attr_name)
                    break
            for attr_name in ['content', 'data', 'text', 'value']:
                if hasattr(ctx, attr_name):
                    content = getattr(ctx, attr_name)
                    break
            create = getattr(ctx, 'create', True)
            truncate = getattr(ctx, 'truncate', True)
            offset = getattr(ctx, 'offset', 0)
    
    if path is None:
        logger.error("Missing required parameter: path")
        return {"error": "Missing required parameter: path"}
    
    if content is None:
        logger.error("Missing required parameter: content")
        return {"error": "Missing required parameter: content"}
    
    try:
        result = await files_write_impl(path, content, create, truncate, offset)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_files_write: {e}")
        return {"error": str(e)}

async def handle_ipfs_files_read(ctx):
    """Handle ipfs_files_read with robust parameter extraction."""
    logger.debug(f"Processing ipfs_files_read request: {type(ctx)}")
    
    # Extract parameters
    path = None
    offset = 0
    count = -1
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['path', 'file_path', 'filepath']:
            if param_name in ctx:
                path = ctx[param_name]
                break
        offset = ctx.get('offset', 0)
        count = ctx.get('count', ctx.get('length', -1))
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['path', 'file_path', 'filepath']:
                if param_name in args:
                    path = args[param_name]
                    break
            offset = args.get('offset', 0)
            count = args.get('count', args.get('length', -1))
        else:
            # Try direct attribute access
            for attr_name in ['path', 'file_path', 'filepath']:
                if hasattr(ctx, attr_name):
                    path = getattr(ctx, attr_name)
                    break
            offset = getattr(ctx, 'offset', 0)
            count = getattr(ctx, 'count', getattr(ctx, 'length', -1))
    
    if path is None:
        logger.error("Missing required parameter: path")
        return {"error": "Missing required parameter: path"}
    
    try:
        result = await files_read_impl(path, offset, count)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_files_read: {e}")
        return {"error": str(e)}

async def handle_ipfs_files_ls(ctx):
    """Handle ipfs_files_ls with robust parameter extraction."""
    logger.debug(f"Processing ipfs_files_ls request: {type(ctx)}")
    
    # Extract parameters
    path = None
    long = False
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['path', 'dir_path', 'directory']:
            if param_name in ctx:
                path = ctx[param_name]
                break
        long = ctx.get('long', ctx.get('l', False))
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['path', 'dir_path', 'directory']:
                if param_name in args:
                    path = args[param_name]
                    break
            long = args.get('long', args.get('l', False))
        else:
            # Try direct attribute access
            for attr_name in ['path', 'dir_path', 'directory']:
                if hasattr(ctx, attr_name):
                    path = getattr(ctx, attr_name)
                    break
            long = getattr(ctx, 'long', getattr(ctx, 'l', False))
    
    if path is None:
        path = "/"  # Default to root directory
    
    try:
        result = await files_ls_impl(path, long)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_files_ls: {e}")
        return {"error": str(e)}

async def handle_ipfs_files_rm(ctx):
    """Handle ipfs_files_rm with robust parameter extraction."""
    logger.debug(f"Processing ipfs_files_rm request: {type(ctx)}")
    
    # Extract parameters
    path = None
    recursive = False
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['path', 'file_path', 'filepath']:
            if param_name in ctx:
                path = ctx[param_name]
                break
        recursive = ctx.get('recursive', ctx.get('r', False))
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['path', 'file_path', 'filepath']:
                if param_name in args:
                    path = args[param_name]
                    break
            recursive = args.get('recursive', args.get('r', False))
        else:
            # Try direct attribute access
            for attr_name in ['path', 'file_path', 'filepath']:
                if hasattr(ctx, attr_name):
                    path = getattr(ctx, attr_name)
                    break
            recursive = getattr(ctx, 'recursive', getattr(ctx, 'r', False))
    
    if path is None:
        logger.error("Missing required parameter: path")
        return {"error": "Missing required parameter: path"}
    
    try:
        result = await files_rm_impl(path, recursive)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_files_rm: {e}")
        return {"error": str(e)}

async def handle_ipfs_files_stat(ctx):
    """Handle ipfs_files_stat with robust parameter extraction."""
    logger.debug(f"Processing ipfs_files_stat request: {type(ctx)}")
    
    # Extract parameters
    path = None
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['path', 'file_path', 'filepath']:
            if param_name in ctx:
                path = ctx[param_name]
                break
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['path', 'file_path', 'filepath']:
                if param_name in args:
                    path = args[param_name]
                    break
        else:
            # Try direct attribute access
            for attr_name in ['path', 'file_path', 'filepath']:
                if hasattr(ctx, attr_name):
                    path = getattr(ctx, attr_name)
                    break
    
    if path is None:
        logger.error("Missing required parameter: path")
        return {"error": "Missing required parameter: path"}
    
    try:
        result = await files_stat_impl(path)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_files_stat: {e}")
        return {"error": str(e)}

async def handle_ipfs_files_cp(ctx):
    """Handle ipfs_files_cp with robust parameter extraction."""
    logger.debug(f"Processing ipfs_files_cp request: {type(ctx)}")
    
    # Extract parameters
    source = None
    dest = None
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['source', 'src', 'from', 'from_path']:
            if param_name in ctx:
                source = ctx[param_name]
                break
        for param_name in ['dest', 'destination', 'to', 'to_path']:
            if param_name in ctx:
                dest = ctx[param_name]
                break
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['source', 'src', 'from', 'from_path']:
                if param_name in args:
                    source = args[param_name]
                    break
            for param_name in ['dest', 'destination', 'to', 'to_path']:
                if param_name in args:
                    dest = args[param_name]
                    break
        else:
            # Try direct attribute access
            for attr_name in ['source', 'src', 'from', 'from_path']:
                if hasattr(ctx, attr_name):
                    source = getattr(ctx, attr_name)
                    break
            for attr_name in ['dest', 'destination', 'to', 'to_path']:
                if hasattr(ctx, attr_name):
                    dest = getattr(ctx, attr_name)
                    break
    
    if source is None:
        logger.error("Missing required parameter: source")
        return {"error": "Missing required parameter: source"}
    
    if dest is None:
        logger.error("Missing required parameter: dest")
        return {"error": "Missing required parameter: dest"}
    
    try:
        result = await files_cp_impl(source, dest)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_files_cp: {e}")
        return {"error": str(e)}

async def handle_ipfs_files_mv(ctx):
    """Handle ipfs_files_mv with robust parameter extraction."""
    logger.debug(f"Processing ipfs_files_mv request: {type(ctx)}")
    
    # Extract parameters
    source = None
    dest = None
    
    if isinstance(ctx, dict):
        # Direct dictionary access
        for param_name in ['source', 'src', 'from', 'from_path']:
            if param_name in ctx:
                source = ctx[param_name]
                break
        for param_name in ['dest', 'destination', 'to', 'to_path']:
            if param_name in ctx:
                dest = ctx[param_name]
                break
    else:
        # Try to extract from context object
        if hasattr(ctx, 'arguments') and ctx.arguments:
            args = ctx.arguments
            for param_name in ['source', 'src', 'from', 'from_path']:
                if param_name in args:
                    source = args[param_name]
                    break
            for param_name in ['dest', 'destination', 'to', 'to_path']:
                if param_name in args:
                    dest = args[param_name]
                    break
        else:
            # Try direct attribute access
            for attr_name in ['source', 'src', 'from', 'from_path']:
                if hasattr(ctx, attr_name):
                    source = getattr(ctx, attr_name)
                    break
            for attr_name in ['dest', 'destination', 'to', 'to_path']:
                if hasattr(ctx, attr_name):
                    dest = getattr(ctx, attr_name)
                    break
    
    if source is None:
        logger.error("Missing required parameter: source")
        return {"error": "Missing required parameter: source"}
    
    if dest is None:
        logger.error("Missing required parameter: dest")
        return {"error": "Missing required parameter: dest"}
    
    try:
        result = await files_mv_impl(source, dest)
        return result
    except Exception as e:
        logger.error(f"Error in ipfs_files_mv: {e}")
        return {"error": str(e)}

# Dictionary mapping tool names to handler functions
TOOL_HANDLERS = {
    # IPFS Core tools
    "ipfs_add": handle_ipfs_add,
    "ipfs_cat": handle_ipfs_cat,
    
    # IPFS Pin tools
    "ipfs_pin_add": handle_ipfs_pin_add,
    "ipfs_pin_rm": handle_ipfs_pin_rm,
    "ipfs_pin_ls": handle_ipfs_pin_ls,
    
    # IPFS MFS tools
    "ipfs_files_mkdir": handle_ipfs_files_mkdir,
    "ipfs_files_write": handle_ipfs_files_write,
    "ipfs_files_read": handle_ipfs_files_read,
    "ipfs_files_ls": handle_ipfs_files_ls,
    "ipfs_files_rm": handle_ipfs_files_rm,
    "ipfs_files_stat": handle_ipfs_files_stat,
    "ipfs_files_cp": handle_ipfs_files_cp,
    "ipfs_files_mv": handle_ipfs_files_mv,
}

def register_all_ipfs_tools(mcp_server):
    """Register all IPFS tools with the MCP server."""
    logger.info("Registering IPFS tools directly...")
    
    registered_tools = []
    for tool_name, handler in TOOL_HANDLERS.items():
        try:
            mcp_server.register_tool(tool_name, handler)
            registered_tools.append(tool_name)
            logger.info(f"Registered tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error registering tool {tool_name}: {e}")
    
    logger.info(f"Successfully registered {len(registered_tools)} IPFS tools")
    return registered_tools
"""
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    logger.info(f"Created direct IPFS tools implementation: {filepath}")
    return True

def update_final_mcp_server():
    """Update final_mcp_server.py to use direct_ipfs_tools.py."""
    filepath = "/home/barberb/ipfs_kit_py/final_mcp_server.py"
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Update the imports
        if "import direct_ipfs_tools" not in content:
            # Find the import section
            import_section = "# --- BEGIN MCP SERVER DIAGNOSTIC LOGGING ---"
            if import_section in content:
                new_import = "import direct_ipfs_tools  # Direct IPFS tool registration\n"
                content = content.replace(import_section, new_import + import_section)
        
        # Update the register_ipfs_tools function
        register_pattern = r'def register_ipfs_tools\(server\):(.*?)(?=def|class)'
        if re.search(register_pattern, content, re.DOTALL):
            old_register = re.search(register_pattern, content, re.DOTALL).group(0)
            new_register = """def register_ipfs_tools(server):
    """Register IPFS tools with the MCP server."""
    logger.info("Registering IPFS tools...")
    
    try:
        # Try to use direct_ipfs_tools first
        direct_ipfs_tools.register_all_ipfs_tools(server)
        logger.info("✅ Registered IPFS tools using direct_ipfs_tools")
        return True
    except Exception as e:
        logger.error(f"❌ Error registering IPFS tools with direct_ipfs_tools: {e}")
        logger.info("Falling back to unified_ipfs_tools...")
        
        try:
            # Fall back to unified_ipfs_tools
            import unified_ipfs_tools
            unified_ipfs_tools.register_all_ipfs_tools(server)
            logger.info("✅ Registered IPFS tools using unified_ipfs_tools")
            return True
        except Exception as e:
            logger.error(f"❌ Error in unified_ipfs_tools: {e}")
            return False

"""
            content = content.replace(old_register, new_register)
        
        # Write the updated content back to the file
        with open(filepath, 'w') as f:
            f.write(content)
        
        logger.info(f"Updated {filepath} to use direct_ipfs_tools.py")
        return True
    except Exception as e:
        logger.error(f"Error updating {filepath}: {e}")
        logger.error(traceback.format_exc())
        return False

def create_test_script():
    """Create a test script to run tests with the updated implementation."""
    filepath = "/home/barberb/ipfs_kit_py/test_direct_ipfs_mcp.sh"
    
    content = """#!/bin/bash
# Direct Test Script for IPFS MCP
# This script tests the direct IPFS tool implementation

set -e

echo "===== Starting Direct IPFS MCP Test ====="
echo "Current directory: $(pwd)"

# Stop any running server
if [ -f "./final_mcp_server.pid" ]; then
    SERVER_PID=$(cat ./final_mcp_server.pid)
    if ps -p $SERVER_PID > /dev/null; then
        echo "Stopping existing server with PID $SERVER_PID"
        kill $SERVER_PID || true
        sleep 2
    fi
    rm -f ./final_mcp_server.pid
fi

# Start server in the background
echo "Starting MCP server..."
python3 ./final_mcp_server.py --host 0.0.0.0 --port 9998 --debug > ./final_mcp_server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > ./final_mcp_server.pid
echo "Started server with PID $SERVER_PID"

# Wait for server to start
echo "Waiting for server to start..."
for i in {1..30}; do
    if curl -s http://localhost:9998/health > /dev/null; then
        echo "✅ Server started successfully"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Failed to start server within 30 seconds"
        cat ./final_mcp_server.log
        exit 1
    fi
    echo "Attempt $i/30: Server not ready yet, waiting..."
    sleep 1
done

# Wait a bit for the server to fully initialize
echo "Giving the server a moment to fully initialize..."
sleep 2

# Create test file with content
echo "Creating test file..."
TEST_CONTENT="Hello IPFS MCP World - Test Content!"
echo "$TEST_CONTENT" > test_ipfs_file.txt

# Test ipfs_add with explicit content parameter
echo -e "\n===== Testing ipfs_add with explicit content parameter ====="
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"ipfs_add","params":{"content":"'"$TEST_CONTENT"'"},"id":1}' http://localhost:9998/jsonrpc | python3 -m json.tool

# Test ipfs_add with file content loaded from file
echo -e "\n===== Testing ipfs_add with file content ====="
FILE_CONTENT=$(cat test_ipfs_file.txt)
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"ipfs_add","params":{"content":"'"$FILE_CONTENT"'"},"id":2}' http://localhost:9998/jsonrpc | python3 -m json.tool

# Run diagnostic tests
echo -e "\n===== Running diagnostic tests ====="
python3 ./diagnose_ipfs_tools.py

# Check final server status
echo -e "\n===== Final server status ====="
curl -s http://localhost:9998/health | python3 -m json.tool

# Show recent server logs
echo -e "\n===== Server logs ====="
tail -50 ./final_mcp_server.log

# Don't stop the server to allow further testing
echo -e "\n===== Test run complete ====="
echo "Server is still running with PID $SERVER_PID"
echo "To stop it, run: kill $SERVER_PID"
"""
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    # Make the script executable
    os.chmod(filepath, 0o755)
    
    logger.info(f"Created test script: {filepath}")
    return True

if __name__ == "__main__":
    logger.info("Starting direct IPFS MCP fix...")
    
    if create_direct_ipfs_tools():
        logger.info("Successfully created direct IPFS tools implementation")
    else:
        logger.error("Failed to create direct IPFS tools implementation")
        sys.exit(1)
    
    if update_final_mcp_server():
        logger.info("Successfully updated final MCP server to use direct IPFS tools")
    else:
        logger.error("Failed to update final MCP server")
        sys.exit(1)
    
    if create_test_script():
        logger.info("Successfully created test script")
    else:
        logger.error("Failed to create test script")
        sys.exit(1)
    
    logger.info("Direct IPFS MCP fix completed successfully")
    logger.info("Run the test script with: ./test_direct_ipfs_mcp.sh")
