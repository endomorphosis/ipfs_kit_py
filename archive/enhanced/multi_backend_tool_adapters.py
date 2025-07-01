#!/usr/bin/env python3
"""
Multi-Backend Tool Adapters Module

This module provides specialized adapters for multi-backend filesystem tools to ensure 
proper parameter mapping between client calls and tool implementations.
"""

import logging
import inspect
import asyncio
from typing import Dict, Any, Callable, Optional, Union

# Import the enhanced parameter adapter
try:
    from enhanced_parameter_adapter import ToolContext
    logger = logging.getLogger("multi-backend-tool-adapters")
except ImportError as e:
    # Fallback logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("multi-backend-tool-adapters")
    logger.error(f"Error importing enhanced parameter adapter: {e}")

# Import the backend manager
try:
    from multi_backend_fs_integration import MultiBackendManager, get_backend_manager
    
    # Get the backend manager instance
    backend_manager = get_backend_manager()
    logger.info("✅ Loaded Multi-Backend manager")
except ImportError as e:
    logger.error(f"❌ Error importing Multi-Backend manager: {e}")
    # Define placeholder manager
    backend_manager = None


# Custom direct handlers for each multi-backend tool
async def handle_mbfs_register_backend(ctx):
    """Custom handler for mbfs_register_backend with direct parameter mapping"""
    wrapped_ctx = ToolContext(ctx)
    arguments = wrapped_ctx.arguments
    
    # Extract parameters with fallbacks
    backend_id = arguments.get('backend_id', arguments.get('name', arguments.get('id')))
    backend_type = arguments.get('backend_type', arguments.get('type'))
    config = arguments.get('config', {})
    make_default = arguments.get('make_default', False)
    
    if not backend_id or not backend_type:
        return {
            "success": False,
            "error": "Missing required parameters: backend_id and backend_type"
        }
    
    try:
        if not backend_manager:
            return {
                "success": False,
                "error": "Backend manager not available"
            }
        
        # Register backend
        success = backend_manager.register_backend(backend_id, backend_type, config)
        
        if not success:
            return {
                "success": False,
                "error": f"Failed to register backend: {backend_id}"
            }
        
        # Set as default if requested
        if make_default:
            backend_manager.set_default_backend(backend_id)
        
        return {
            "success": True,
            "backend_id": backend_id,
            "backend_type": backend_type,
            "is_default": backend_id == backend_manager.default_backend_id
        }
    except Exception as e:
        error_msg = f"Error in mbfs_register_backend: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": str(e),
            "function": "mbfs_register_backend"
        }

async def handle_mbfs_store(ctx):
    """Custom handler for mbfs_store with direct parameter mapping"""
    wrapped_ctx = ToolContext(ctx)
    arguments = wrapped_ctx.arguments
    
    # Extract parameters with fallbacks
    content = arguments.get('content', arguments.get('data', arguments.get('text')))
    path = arguments.get('path', arguments.get('file_path', arguments.get('filepath')))
    backend_id = arguments.get('backend_id', arguments.get('backend', arguments.get('id')))
    metadata = arguments.get('metadata', {})
    
    if not content:
        return {
            "success": False,
            "error": "Missing required parameter: content"
        }
    
    if not path:
        path = f"file-{hash(content)[:8]}"
    
    try:
        if not backend_manager:
            return {
                "success": False,
                "error": "Backend manager not available"
            }
        
        # Store content
        result = await backend_manager.store(content, path, backend_id, metadata)
        return result
    except Exception as e:
        error_msg = f"Error in mbfs_store: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": str(e),
            "function": "mbfs_store"
        }

async def handle_mbfs_retrieve(ctx):
    """Custom handler for mbfs_retrieve with direct parameter mapping"""
    wrapped_ctx = ToolContext(ctx)
    arguments = wrapped_ctx.arguments
    
    # Extract parameters with fallbacks
    identifier = arguments.get('identifier', arguments.get('id', arguments.get('cid')))
    backend_id = arguments.get('backend_id', arguments.get('backend'))
    
    if not identifier:
        return {
            "success": False,
            "error": "Missing required parameter: identifier"
        }
    
    try:
        if not backend_manager:
            return {
                "success": False,
                "error": "Backend manager not available"
            }
        
        # Retrieve content
        result = await backend_manager.retrieve(identifier, backend_id)
        return result
    except Exception as e:
        error_msg = f"Error in mbfs_retrieve: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": str(e),
            "function": "mbfs_retrieve"
        }

async def handle_mbfs_delete(ctx):
    """Custom handler for mbfs_delete with direct parameter mapping"""
    wrapped_ctx = ToolContext(ctx)
    arguments = wrapped_ctx.arguments
    
    # Extract parameters with fallbacks
    identifier = arguments.get('identifier', arguments.get('id', arguments.get('cid')))
    backend_id = arguments.get('backend_id', arguments.get('backend'))
    
    if not identifier:
        return {
            "success": False,
            "error": "Missing required parameter: identifier"
        }
    
    try:
        if not backend_manager:
            return {
                "success": False,
                "error": "Backend manager not available"
            }
        
        # Delete content
        result = await backend_manager.delete(identifier, backend_id)
        return result
    except Exception as e:
        error_msg = f"Error in mbfs_delete: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": str(e),
            "function": "mbfs_delete"
        }

async def handle_mbfs_list(ctx):
    """Custom handler for mbfs_list with direct parameter mapping"""
    wrapped_ctx = ToolContext(ctx)
    arguments = wrapped_ctx.arguments
    
    # Extract parameters with fallbacks
    prefix = arguments.get('prefix', arguments.get('path', ""))
    backend_id = arguments.get('backend_id', arguments.get('backend'))
    
    try:
        if not backend_manager:
            return {
                "success": False,
                "error": "Backend manager not available"
            }
        
        # List content
        result = await backend_manager.list(prefix, backend_id)
        return result
    except Exception as e:
        error_msg = f"Error in mbfs_list: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": str(e),
            "function": "mbfs_list"
        }

# Dictionary mapping tool names to their direct handlers
TOOL_HANDLERS = {
    "mbfs_register_backend": handle_mbfs_register_backend,
    "mbfs_store": handle_mbfs_store,
    "mbfs_retrieve": handle_mbfs_retrieve,
    "mbfs_delete": handle_mbfs_delete,
    "mbfs_list": handle_mbfs_list,
    # Add more handlers as needed
}

def get_tool_handler(tool_name):
    """Get a direct handler for a specific tool"""
    return TOOL_HANDLERS.get(tool_name)
