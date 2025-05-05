#!/usr/bin/env python3
"""
Tool Registration Script for IPFS and VFS Tools

This script registers all available IPFS and VFS tools with a running MCP server.
It should be run after the MCP server is already running.
"""

import sys
import os
import logging
import importlib
import json
import requests
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ipfs-vfs-tools-register')

# Add current directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ipfs_kit_py')))

# Server configuration
SERVER_URL = "http://localhost:3000"
HEALTH_ENDPOINT = f"{SERVER_URL}/health"
INITIALIZE_ENDPOINT = f"{SERVER_URL}/initialize"
JSONRPC_ENDPOINT = f"{SERVER_URL}/jsonrpc"

def check_server_health():
    """Check if the MCP server is running and healthy."""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        if response.status_code == 200:
            logger.info("✅ Server is running and healthy")
            return True
        logger.error(f"❌ Server returned status code {response.status_code}")
        return False
    except requests.RequestException as e:
        logger.error(f"❌ Failed to connect to server: {e}")
        return False

def import_module_safely(module_name):
    """Safely import a module, returning None if it fails."""
    try:
        return importlib.import_module(module_name)
    except (ImportError, ModuleNotFoundError) as e:
        logger.warning(f"⚠️ Could not import {module_name}: {e}")
        return None

def register_tools_from_module(module_name):
    """Register all tools from a given module."""
    module = import_module_safely(module_name)
    if not module:
        return False
    
    # Look for register functions
    registration_functions = [
        'register_all_tools',
        'register_tools',
        'register_all_components',
        'register_all_fs_tools',
        'register_vfs_tools',
        'register_ipfs_tools'
    ]
    
    for func_name in registration_functions:
        if hasattr(module, func_name):
            logger.info(f"Found registration function {func_name} in {module_name}")
            try:
                # Call the function with a DirectTools registry since we can't access the server directly
                getattr(module, func_name)(DirectToolsRegistry())
                return True
            except Exception as e:
                logger.error(f"❌ Error calling {func_name}: {e}")
    
    # If we get here, no registration functions were found or called successfully
    logger.warning(f"⚠️ No usable registration functions found in {module_name}")
    return False

class DirectToolsRegistry:
    """A class that mimics the MCP server's tool registry but directly registers tools via JSON-RPC."""
    
    def __init__(self):
        self.registered_tools = []
    
    def register_tool(self, tool_name, tool_func, input_schema=None, output_schema=None, description=None):
        """Register a tool with the MCP server."""
        logger.info(f"Registering tool: {tool_name}")
        
        # Create a simplified schema if none is provided
        if input_schema is None:
            input_schema = {
                "type": "object",
                "properties": {},
                "additionalProperties": True
            }
        
        if output_schema is None:
            output_schema = {
                "type": "object",
                "additionalProperties": True
            }
        
        # Create the JSON-RPC registration payload
        payload = {
            "jsonrpc": "2.0",
            "method": "register_tool",
            "params": {
                "name": tool_name,
                "input_schema": input_schema,
                "output_schema": output_schema,
                "description": description or f"Tool: {tool_name}"
            },
            "id": len(self.registered_tools) + 1
        }
        
        try:
            response = requests.post(JSONRPC_ENDPOINT, json=payload)
            if response.status_code == 200:
                result = response.json()
                if 'result' in result and result['result'].get('success', False):
                    logger.info(f"✅ Successfully registered tool: {tool_name}")
                    self.registered_tools.append(tool_name)
                    return True
                else:
                    error = result.get('error', {}).get('message', 'Unknown error')
                    logger.error(f"❌ Failed to register tool {tool_name}: {error}")
            else:
                logger.error(f"❌ Server returned status code {response.status_code} when registering {tool_name}")
            return False
        except Exception as e:
            logger.error(f"❌ Exception when registering tool {tool_name}: {e}")
            return False

def register_all_modules():
    """Register tools from all available IPFS and VFS modules."""
    modules_to_register = [
        'unified_ipfs_tools',
        'ipfs_tools_registry',
        'ipfs_mcp_tools',
        'fs_journal_tools',
        'ipfs_mcp_fs_integration',
        'multi_backend_fs_integration',
        'ipfs_mcp_tools_integration',
        'enhance_vfs_mcp_integration',
        'integrate_fs_with_tools'
    ]
    
    success_count = 0
    for module_name in modules_to_register:
        logger.info(f"Attempting to register tools from {module_name}")
        if register_tools_from_module(module_name):
            success_count += 1
    
    logger.info(f"✅ Registered tools from {success_count}/{len(modules_to_register)} modules")
    
    # Also try direct registration for common tools
    registry = DirectToolsRegistry()
    try:
        # Import VFS components
        from ipfs_kit_py.vfs import IPFSFileSystem, FileManager
        from ipfs_kit_py.vfs.journal import FileSystemJournal
        
        # Register basic VFS tools
        registry.register_tool(
            "vfs_list_directory",
            None,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            {"type": "object", "properties": {"entries": {"type": "array"}}},
            "List contents of a directory in the virtual file system"
        )
        
        registry.register_tool(
            "vfs_read_file",
            None,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            {"type": "object", "properties": {"content": {"type": "string"}}},
            "Read a file from the virtual file system"
        )
        
        registry.register_tool(
            "vfs_write_file",
            None,
            {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
            {"type": "object", "properties": {"success": {"type": "boolean"}}},
            "Write content to a file in the virtual file system"
        )
        
        registry.register_tool(
            "vfs_delete_file",
            None,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            {"type": "object", "properties": {"success": {"type": "boolean"}}},
            "Delete a file from the virtual file system"
        )
        
        registry.register_tool(
            "vfs_create_directory",
            None,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            {"type": "object", "properties": {"success": {"type": "boolean"}}},
            "Create a directory in the virtual file system"
        )
        
        # Register IPFS tools
        registry.register_tool(
            "ipfs_add_file",
            None,
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            {"type": "object", "properties": {"cid": {"type": "string"}}},
            "Add a file to IPFS and return its CID"
        )
        
        registry.register_tool(
            "ipfs_get_file",
            None,
            {"type": "object", "properties": {"cid": {"type": "string"}, "output_path": {"type": "string"}}, "required": ["cid"]},
            {"type": "object", "properties": {"success": {"type": "boolean"}, "path": {"type": "string"}}},
            "Get a file from IPFS by its CID"
        )
        
        registry.register_tool(
            "ipfs_pin_cid",
            None,
            {"type": "object", "properties": {"cid": {"type": "string"}}, "required": ["cid"]},
            {"type": "object", "properties": {"success": {"type": "boolean"}}},
            "Pin a CID to keep it in the local IPFS node"
        )
        
        registry.register_tool(
            "ipfs_list_pins",
            None,
            {"type": "object", "properties": {}},
            {"type": "object", "properties": {"pins": {"type": "array"}}},
            "List all pinned CIDs in the local IPFS node"
        )
        
        # Bridge tools for VFS and IPFS integration
        registry.register_tool(
            "vfs_to_ipfs",
            None,
            {"type": "object", "properties": {"vfs_path": {"type": "string"}}, "required": ["vfs_path"]},
            {"type": "object", "properties": {"cid": {"type": "string"}}},
            "Add a file from the virtual file system to IPFS"
        )
        
        registry.register_tool(
            "ipfs_to_vfs",
            None,
            {"type": "object", "properties": {"cid": {"type": "string"}, "vfs_path": {"type": "string"}}, "required": ["cid", "vfs_path"]},
            {"type": "object", "properties": {"success": {"type": "boolean"}}},
            "Get a file from IPFS and save it to the virtual file system"
        )
        
    except ImportError as e:
        logger.warning(f"⚠️ Could not import some VFS components: {e}")

def verify_tools_registration():
    """Verify that tools were successfully registered."""
    try:
        response = requests.get(SERVER_URL)
        if response.status_code == 200:
            data = response.json()
            tool_count = data.get('registered_tools_count', 0)
            tools = data.get('registered_tools', [])
            
            logger.info(f"Server now has {tool_count} registered tools:")
            for tool in tools:
                logger.info(f"  - {tool}")
            
            if tool_count > 0:
                logger.info("✅ Tool registration successful")
                return True
            else:
                logger.warning("⚠️ No tools were registered")
                return False
        else:
            logger.error(f"❌ Server returned status code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error verifying tool registration: {e}")
        return False

def main():
    """Main function."""
    logger.info("Starting IPFS/VFS tool registration")
    
    if not check_server_health():
        logger.error("❌ Server is not running or not healthy. Make sure the MCP server is running.")
        return 1
    
    # Register all modules
    register_all_modules()
    
    # Verify registration
    time.sleep(1)  # Give the server a moment to process registrations
    if verify_tools_registration():
        logger.info("✅ IPFS/VFS tools successfully integrated with the MCP server")
        return 0
    else:
        logger.error("❌ Failed to integrate IPFS/VFS tools with the MCP server")
        return 1

if __name__ == "__main__":
    sys.exit(main())
