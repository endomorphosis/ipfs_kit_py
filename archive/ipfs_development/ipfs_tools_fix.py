#!/usr/bin/env python3
"""
IPFS MCP Tools Implementation Fix

This module provides implementation for the MCP server tools that may be 
registered but not properly hooked to the JSON-RPC interface.

It connects the registered tools to direct JSON-RPC methods to ensure proper operation.
"""

import os
import sys
import json
import logging
import inspect
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("ipfs-mcp-tools-fix")

# Import jsonrpcserver to register methods
try:
    from jsonrpcserver import method as jsonrpc_method
except ImportError:
    logger.error("jsonrpcserver not available. Please install with: pip install jsonrpcserver")
    jsonrpc_method = lambda func: func  # Use a no-op decorator if jsonrpcserver not available

class IPFSToolsRegistrar:
    """
    Registers the IPFS tools as direct JSON-RPC methods
    """
    
    def __init__(self, server):
        """Initialize with the server instance"""
        self.server = server
        self.registered_count = 0
    
    def register_tools_as_methods(self):
        """
        Register all tools from the server's tool registry directly as JSON-RPC methods
        """
        if not hasattr(self.server, 'tools'):
            logger.error("Server does not have a tools attribute")
            return False
        
        for tool_name, tool_info in self.server.tools.items():
            try:
                # Get the tool's function and register it as a JSON-RPC method
                tool_func = tool_info.get('function')
                if tool_func is None:
                    logger.warning(f"Tool {tool_name} has no function defined")
                    continue
                
                # Register the tool function as a JSON-RPC method
                self._register_tool_as_method(tool_name, tool_func)
                self.registered_count += 1
                
            except Exception as e:
                logger.error(f"Error registering tool {tool_name} as JSON-RPC method: {e}")
                traceback.print_exc()
        
        logger.info(f"Registered {self.registered_count} tools as direct JSON-RPC methods")
        return True
    
    def _register_tool_as_method(self, tool_name, tool_func):
        """Register a single tool as a JSON-RPC method"""
        # Create a wrapper function to handle the tool execution
        @jsonrpc_method(tool_name)
        def method_wrapper(**kwargs):
            try:
                logger.debug(f"Executing tool {tool_name} with params: {kwargs}")
                result = tool_func(**kwargs)
                return result
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                traceback.print_exc()
                raise
        
        # Update the wrapper's metadata
        method_wrapper.__name__ = tool_name
        method_wrapper.__doc__ = tool_func.__doc__
        
        # Add the wrapper to the module's global namespace
        globals()[tool_name] = method_wrapper
        
        logger.debug(f"Registered tool {tool_name} as JSON-RPC method")

def fix_mcp_tools(server):
    """
    Main function to fix MCP tools by registering them as direct JSON-RPC methods
    """
    registrar = IPFSToolsRegistrar(server)
    success = registrar.register_tools_as_methods()
    
    return {
        "success": success, 
        "registered_count": registrar.registered_count,
        "message": "Tools registered as direct JSON-RPC methods" if success else "Failed to register tools"
    }
