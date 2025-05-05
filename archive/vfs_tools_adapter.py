#!/usr/bin/env python3
"""
VFS Tools Adapter for MCP Server

This module serves as an adapter between the MCP server and various VFS tool implementations.
It matches the function signatures expected by the MCP server with the actual implementations
in the various VFS modules.
"""

import os
import sys
import logging
import traceback
import importlib.util
from typing import Dict, List, Any, Optional, Union, Callable

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_module(module_name, fail_silently=True):
    """
    Load a module dynamically

    Args:
        module_name: Name of the module to load
        fail_silently: If True, return None on error instead of raising an exception

    Returns:
        The loaded module or None if it couldn't be loaded and fail_silently is True
    """
    try:
        # Try to import the module
        if module_name in sys.modules:
            return sys.modules[module_name]

        spec = importlib.util.find_spec(module_name)
        if spec is None:
            logger.warning(f"Module not found: {module_name}")
            if fail_silently:
                return None
            else:
                raise ImportError(f"Module not found: {module_name}")

        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        else:
            logger.warning(f"Module {module_name} found but couldn't be loaded (no spec.loader)")
            if fail_silently:
                return None
            else:
                raise ImportError(f"Module {module_name} found but couldn't be loaded")
    except Exception as e:
        logger.error(f"Error loading module {module_name}: {e}")
        if fail_silently:
            return None
        else:
            raise

# Function name mappings between what MCP expects and what our modules provide
FUNCTION_MAPPINGS = {
    # FS Journal mappings
    "register_fs_journal_tools": "register_tools",  # from fs_journal_tools
    
    # VFS integration mappings
    "register_vfs_integration": "register_all_fs_tools",  # from integrate_vfs_to_final_mcp
    
    # IPFS-FS bridge mappings
    "register_ipfs_fs_bridge": "register_integration_tools",  # from ipfs_mcp_fs_integration
    
    # Multi-backend mappings
    "register_multi_backend_fs": "register_tools",  # from multi_backend_fs_integration
}

def register_fs_journal_tools(server):
    """Adapter for fs_journal_tools.register_tools"""
    try:
        fs_journal = load_module("fs_journal_tools")
        if fs_journal and hasattr(fs_journal, "register_tools"):
            logger.info("Registering FS Journal tools through adapter")
            result = fs_journal.register_tools(server)
            if result:
                logger.info("✅ Successfully registered FS Journal tools")
            else:
                logger.warning("⚠️ Failed to register FS Journal tools")
            return result
        else:
            logger.error("FS Journal tools module not found or missing register_tools function")
            return False
    except Exception as e:
        logger.error(f"Error registering FS Journal tools: {e}")
        logger.error(traceback.format_exc())
        return False

def register_vfs_integration(server):
    """Adapter for integrate_vfs_to_final_mcp.register_all_fs_tools"""
    try:
        vfs_integrate = load_module("integrate_vfs_to_final_mcp")
        if vfs_integrate and hasattr(vfs_integrate, "register_all_fs_tools"):
            logger.info("Registering VFS integration through adapter")
            result = vfs_integrate.register_all_fs_tools(server)
            if result:
                logger.info("✅ Successfully registered VFS integration")
            else:
                logger.warning("⚠️ Failed to register VFS integration")
            return result
        else:
            logger.error("VFS integration module not found or missing register_all_fs_tools function")
            return False
    except Exception as e:
        logger.error(f"Error registering VFS integration: {e}")
        logger.error(traceback.format_exc())
        return False

def register_ipfs_fs_bridge(server):
    """Adapter for ipfs_mcp_fs_integration.register_integration_tools"""
    try:
        ipfs_fs = load_module("ipfs_mcp_fs_integration")
        if ipfs_fs and hasattr(ipfs_fs, "register_integration_tools"):
            logger.info("Registering IPFS-FS bridge through adapter")
            result = ipfs_fs.register_integration_tools(server)
            if result:
                logger.info("✅ Successfully registered IPFS-FS bridge")
            else:
                logger.warning("⚠️ Failed to register IPFS-FS bridge")
            return result
        else:
            logger.error("IPFS-FS bridge module not found or missing register_integration_tools function")
            return False
    except Exception as e:
        logger.error(f"Error registering IPFS-FS bridge: {e}")
        logger.error(traceback.format_exc())
        return False

def register_multi_backend_fs(server):
    """Adapter for multi_backend_fs_integration.register_tools"""
    try:
        multi_backend = load_module("multi_backend_fs_integration")
        if multi_backend and hasattr(multi_backend, "register_tools"):
            logger.info("Registering Multi-backend FS through adapter")
            result = multi_backend.register_tools(server)
            if result:
                logger.info("✅ Successfully registered Multi-backend FS")
            else:
                logger.warning("⚠️ Failed to register Multi-backend FS")
            return result
        else:
            logger.error("Multi-backend FS module not found or missing register_tools function")
            return False
    except Exception as e:
        logger.error(f"Error registering Multi-backend FS: {e}")
        logger.error(traceback.format_exc())
        return False

def register_all_vfs_tools(server):
    """Register all VFS tools with the server"""
    results = {
        "fs_journal": register_fs_journal_tools(server),
        "vfs_integration": register_vfs_integration(server),
        "ipfs_fs_bridge": register_ipfs_fs_bridge(server),
        "multi_backend_fs": register_multi_backend_fs(server)
    }
    
    # Report success count
    successful = sum(1 for value in results.values() if value)
    total = len(results)
    
    logger.info(f"VFS tools registration: {successful}/{total} components successfully registered")
    
    return successful > 0  # Return True if at least one component was registered

if __name__ == "__main__":
    logger.info("This module should be imported by an MCP server, not run directly")
    sys.exit(0)
