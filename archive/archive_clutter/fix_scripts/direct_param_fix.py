#!/usr/bin/env python3
"""
Direct Parameter Fix for IPFS Tools

This module contains direct fixes for parameter handling issues in the IPFS tools.
It works by directly wrapping the tool implementations and handling parameter mapping
without relying on the generic adapter mechanism.
"""

import logging
import sys
import os
from typing import Dict, Any, Optional, List, Callable

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct-param-fix")

def install_parameter_fix():
    """Install the parameter fix by patching the relevant modules"""
    logger.info("Installing direct parameter fix for IPFS tools")
    
    # Add the current directory to Python path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Import the relevant modules
    try:
        from unified_ipfs_tools import mock_add_content, register_all_ipfs_tools
        
        # Store the original function
        original_register_all_ipfs_tools = register_all_ipfs_tools
        
        # Define the patched function
        def patched_register_all_ipfs_tools(mcp_server):
            """Patched version of register_all_ipfs_tools with parameter fixes"""
            logger.info("Using patched version of register_all_ipfs_tools")
            
            # Define custom handlers for problematic tools
            async def fixed_ipfs_add(ctx):
                """Fixed handler for ipfs_add that properly maps parameters"""
                # Extract parameters
                args = {}
                if hasattr(ctx, 'arguments') and ctx.arguments is not None:
                    args = ctx.arguments
                elif hasattr(ctx, 'params') and ctx.params is not None:
                    args = ctx.params
                
                # Map parameters correctly
                content = args.get('content', args.get('data', args.get('text')))
                filename = args.get('filename', args.get('name'))
                pin = args.get('pin', True)
                
                # Call the implementation with correct parameters
                try:
                    return await mock_add_content(content, filename, pin)
                except Exception as e:
                    logger.error(f"Error in fixed_ipfs_add: {e}")
                    return {"success": False, "error": str(e)}
            
            # Register the fixed handler directly
            try:
                mcp_server.tool(
                    name="ipfs_add",
                    description="Add content to IPFS"
                )(fixed_ipfs_add)
                logger.info("✅ Registered fixed ipfs_add handler")
            except Exception as e:
                logger.error(f"❌ Error registering fixed ipfs_add handler: {e}")
            
            # Call the original function to register other tools
            result = original_register_all_ipfs_tools(mcp_server)
            return result
        
        # Replace the original function with our patched version
        import unified_ipfs_tools
        unified_ipfs_tools.register_all_ipfs_tools = patched_register_all_ipfs_tools
        
        logger.info("✅ Successfully installed IPFS parameter fix")
        return True
    except Exception as e:
        logger.error(f"❌ Error installing parameter fix: {e}")
        return False

if __name__ == "__main__":
    # Install the fix when this module is run directly
    success = install_parameter_fix()
    print(f"Parameter fix installation {'successful' if success else 'failed'}")