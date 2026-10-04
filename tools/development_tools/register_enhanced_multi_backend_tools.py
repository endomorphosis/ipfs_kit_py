#!/usr/bin/env python3
"""
Multi-Backend Tools Registration with Enhanced Parameter Handling

This module updates the multi-backend tools registration to use the enhanced
parameter handling approach, improving compatibility with different client
parameter naming conventions.
"""

import sys
import logging
import asyncio
from typing import Dict, Any, Callable, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def register_multi_backend_tools(server):
    """
    Register multi-backend filesystem tools with enhanced parameter handling.
    
    Args:
        server: The MCP server instance
    
    Returns:
        bool: True if registration was successful, False otherwise
    """
    logger.info("🔄 Registering multi-backend filesystem tools with enhanced parameter handling...")
    
    try:
        # Import required modules
        from multi_backend_fs_integration import get_backend_manager
        
        # Try to import enhanced parameter adapter
        try:
            from enhanced_parameter_adapter import create_tool_wrapper, adapt_parameters
            from enhanced.multi_backend_tool_adapters import get_tool_handler
            
            # Get backend manager
            backend_manager = get_backend_manager()
            
            # Check if backend manager is initialized
            if not backend_manager:
                logger.error("❌ Backend manager not initialized")
                return False
            
            # Using enhanced parameter adapter
            logger.info("✅ Using enhanced parameter adapter for multi-backend tools")
            using_direct_handlers = True
            
            # Define a function to register a tool with the server
            def register_tool(tool_name, description, handler_func=None):
                try:
                    # Try to get a direct handler first
                    if using_direct_handlers:
                        direct_handler = get_tool_handler(tool_name)
                        if direct_handler:
                            # Register with direct handler
                            server.tool(name=tool_name, description=description)(direct_handler)
                            logger.info(f"✅ Registered {tool_name} with direct handler")
                            return True
                    
                    # Fall back to tool wrapper if no direct handler or direct handlers disabled
                    if handler_func:
                        wrapped_handler = create_tool_wrapper(handler_func, tool_name)
                        server.tool(name=tool_name, description=description)(wrapped_handler)
                        logger.info(f"✅ Registered {tool_name} with wrapped handler")
                        return True
                    else:
                        logger.warning(f"⚠️ No handler for {tool_name}")
                        return False
                except Exception as e:
                    logger.error(f"❌ Error registering {tool_name}: {e}")
                    return False
            
            # Register multi-backend tools
            tools_registered = []
            
            # Tool: Register a storage backend
            if register_tool(
                "mbfs_register_backend", 
                "Register a storage backend (IPFS, S3, etc.)",
                backend_manager.register_backend_handler
            ):
                tools_registered.append("mbfs_register_backend")
            
            # Tool: Store content
            if register_tool(
                "mbfs_store", 
                "Store content in a registered backend",
                backend_manager.store_handler
            ):
                tools_registered.append("mbfs_store")
            
            # Tool: Retrieve content
            if register_tool(
                "mbfs_retrieve", 
                "Retrieve content from a backend by identifier",
                backend_manager.retrieve_handler
            ):
                tools_registered.append("mbfs_retrieve")
            
            # Tool: Delete content
            if register_tool(
                "mbfs_delete", 
                "Delete content from a backend by identifier",
                backend_manager.delete_handler
            ):
                tools_registered.append("mbfs_delete")
            
            # Tool: List content
            if register_tool(
                "mbfs_list", 
                "List content in a backend with optional prefix",
                backend_manager.list_handler
            ):
                tools_registered.append("mbfs_list")
            
            # Tool: Get backend info
            if register_tool(
                "mbfs_get_backend_info", 
                "Get information about a registered backend",
                backend_manager.get_backend_info_handler
            ):
                tools_registered.append("mbfs_get_backend_info")
            
            # Tool: List backends
            if register_tool(
                "mbfs_list_backends", 
                "List all registered storage backends",
                backend_manager.list_backends_handler
            ):
                tools_registered.append("mbfs_list_backends")
            
            # Tool: Set default backend
            if register_tool(
                "mbfs_set_default_backend", 
                "Set the default storage backend",
                backend_manager.set_default_backend_handler
            ):
                tools_registered.append("mbfs_set_default_backend")
            
            # Tool: Get storage stats
            if register_tool(
                "mbfs_get_storage_stats", 
                "Get storage statistics for a backend",
                backend_manager.get_storage_stats_handler
            ):
                tools_registered.append("mbfs_get_storage_stats")
            
            # Tool: Verify content
            if register_tool(
                "mbfs_verify_content", 
                "Verify content integrity in a backend",
                backend_manager.verify_content_handler
            ):
                tools_registered.append("mbfs_verify_content")
            
            logger.info(f"✅ Registered {len(tools_registered)} multi-backend filesystem tools")
            return True
            
        except ImportError as e:
            logger.warning(f"⚠️ Enhanced parameter adapter not available, using fallback: {e}")
            
            # Fallback to direct registration without parameter adapter
            from multi_backend_fs_integration import register_tools_with_server
            
            # Register tools using the built-in function
            success = register_tools_with_server(server)
            
            if success:
                logger.info("✅ Registered multi-backend filesystem tools using fallback method")
            else:
                logger.error("❌ Failed to register multi-backend filesystem tools using fallback")
            
            return success
    
    except Exception as e:
        logger.error(f"❌ Error registering multi-backend filesystem tools: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    # Test code to register tools with a mock server
    class MockServer:
        def tool(self, name, description):
            def decorator(func):
                print(f"Registered tool: {name} - {description}")
                return func
            return decorator
    
    # Create mock server
    server = MockServer()
    
    # Register tools
    success = register_multi_backend_tools(server)
    
    print(f"Registration {'succeeded' if success else 'failed'}")
