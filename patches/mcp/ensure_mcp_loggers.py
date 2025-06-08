#!/usr/bin/env python3
"""
Wrapper module to ensure loggers are defined in MCP resource handlers
"""

import sys
import logging
import importlib
import types

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def patch_module(module_name):
    """Patch a module to ensure logger is defined."""
    try:
        # Import the module
        if module_name in sys.modules:
            module = sys.modules[module_name]
        else:
            module = importlib.import_module(module_name)
        
        # Add logger if not present
        if not hasattr(module, 'logger'):
            module.logger = logging.getLogger(module_name)
            logger.info(f"Added logger to module {module_name}")
        
        # Return the patched module
        return module
    except ImportError:
        logger.warning(f"Could not import module {module_name}")
        return None
    except Exception as e:
        logger.error(f"Error patching module {module_name}: {e}")
        return None

def patch_all_mcp_resources():
    """Patch all MCP resource modules."""
    modules_to_patch = [
        'mcp.server.lowlevel.server',
        'mcp.server.lowlevel.resource',
        'mcp.server.lowlevel.handler',
        'mcp.server.fastmcp'
    ]
    
    for module_name in modules_to_patch:
        patch_module(module_name)
    
    logger.info("Completed MCP resource module patching")

if __name__ == "__main__":
    patch_all_mcp_resources()
