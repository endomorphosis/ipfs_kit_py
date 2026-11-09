#!/usr/bin/env python3
"""
Apply Fixed IPFS Parameter Handling

This module integrates the parameter validation and handling fixes with
the IPFS tools implementation, ensuring all tools properly validate, normalize,
and handle parameters before passing to the underlying implementation.
"""

import os
import sys
import logging
import importlib
import traceback
from typing import Dict, Any, List, Optional, Union, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("fix-ipfs-param-integration")

# Import our fixed parameter handling
try:
    from fixed_ipfs_param_handling import IPFSParamHandler
    logger.info("✅ Successfully imported fixed parameter handling")
    PARAM_HANDLER_AVAILABLE = True
except ImportError as ie:
    logger.error(f"❌ Error importing fixed parameter handling: {ie}")
    PARAM_HANDLER_AVAILABLE = False
except Exception as e:
    logger.error(f"❌ Unexpected error importing parameter handler: {e}")
    logger.error(traceback.format_exc())
    PARAM_HANDLER_AVAILABLE = False

# Import our fixed IPFS model
try:
    from fixed_ipfs_model import IPFSModel
    logger.info("✅ Successfully imported fixed IPFS model")
    FIXED_MODEL_AVAILABLE = True
except ImportError as ie:
    logger.error(f"❌ Error importing fixed IPFS model: {ie}")
    FIXED_MODEL_AVAILABLE = False
except Exception as e:
    logger.error(f"❌ Unexpected error importing fixed IPFS model: {e}")
    logger.error(traceback.format_exc())
    FIXED_MODEL_AVAILABLE = False

# Initialize fixed IPFS model
ipfs_model_instance = None
if FIXED_MODEL_AVAILABLE:
    try:
        ipfs_model_instance = IPFSModel()
        if ipfs_model_instance.ipfs_client is None:
            logger.warning("⚠️ Fixed IPFS model initialized but client is None")
        else:
            logger.info("✅ Successfully initialized fixed IPFS model with client")
    except Exception as e:
        logger.error(f"❌ Error initializing fixed IPFS model: {e}")
        logger.error(traceback.format_exc())
        ipfs_model_instance = None

# Function to create parameter-fixed wrapper functions for IPFS tools
def create_fixed_tool_wrapper(tool_name: str, 
                             func: Callable[..., Any],
                             validator_func: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> Callable[..., Any]:
    """Create a wrapper function that applies parameter validation and handling."""
    
    async def wrapper(**kwargs) -> Dict[str, Any]:
        """
        Wrapper function that handles parameter validation and error handling
        for IPFS tool functions.
        """
        try:
            # If we have a validator function and the parameter handler is available, use it
            if validator_func is not None and PARAM_HANDLER_AVAILABLE:
                try:
                    # Validate and normalize parameters
                    validated_kwargs = validator_func(kwargs)
                    logger.debug(f"Validated parameters for {tool_name}: {validated_kwargs}")
                except ValueError as ve:
                    logger.error(f"Parameter validation error in {tool_name}: {ve}")
                    return {
                        "success": False,
                        "error": str(ve),
                        "tool": tool_name
                    }
                except Exception as e:
                    logger.error(f"Unexpected error in parameter validation for {tool_name}: {e}")
                    logger.error(traceback.format_exc())
                    return {
                        "success": False,
                        "error": f"Parameter validation error: {str(e)}",
                        "tool": tool_name
                    }
            else:
                # No validation, just use the parameters as provided
                validated_kwargs = kwargs
            
            # Check if we have a fixed IPFS model instance
            if ipfs_model_instance is not None and ipfs_model_instance.ipfs_client is not None:
                try:
                    # Use the fixed IPFS model implementation
                    # Import the function from fixed_ipfs_model
                    fixed_func = getattr(sys.modules['fixed_ipfs_model'], func.__name__)
                    result = await fixed_func(ipfs_model_instance.ipfs_client, **validated_kwargs)
                    return result
                except AttributeError:
                    logger.warning(f"⚠️ Function {func.__name__} not found in fixed_ipfs_model")
                    # Fall back to original function
                    return await func(**validated_kwargs)
                except Exception as e:
                    logger.error(f"❌ Error in fixed implementation of {tool_name}: {e}")
                    logger.error(traceback.format_exc())
                    # Fall back to original function
                    return await func(**validated_kwargs)
            else:
                # No fixed model available, use original function
                return await func(**validated_kwargs)
                
        except Exception as e:
            logger.error(f"❌ Unhandled error in {tool_name}: {e}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name
            }
    
    # Preserve function metadata
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    
    return wrapper

# Create validator mapping for IPFS tools
VALIDATOR_MAP = {
    "ipfs_add": IPFSParamHandler.validate_ipfs_add_params if PARAM_HANDLER_AVAILABLE else None,
    "ipfs_cat": IPFSParamHandler.validate_ipfs_cat_params if PARAM_HANDLER_AVAILABLE else None,
    "ipfs_files_ls": IPFSParamHandler.validate_ipfs_files_ls_params if PARAM_HANDLER_AVAILABLE else None,
    # Add more validators as needed
}

def apply_fixed_params_to_server(server):
    """
    Apply parameter handling fixes to an MCP server.
    
    This function wraps the existing IPFS tool functions with fixed parameter
    handling implementations.
    
    Args:
        server: The MCP server instance
        
    Returns:
        bool: True if any fixes were applied, False otherwise
    """
    if not PARAM_HANDLER_AVAILABLE:
        logger.warning("⚠️ Parameter handler not available, skipping fixes")
        return False
    
    fixes_applied = 0
    
    # Get existing tools from the server
    for tool_name in server.tools:
        # Only apply fixes to IPFS tools
        if tool_name.startswith("ipfs_"):
            original_tool = server.tools[tool_name]
            
            # Get the validator for this tool if we have one
            validator = VALIDATOR_MAP.get(tool_name)
            
            if validator:
                # Create a fixed wrapper for this tool
                fixed_wrapper = create_fixed_tool_wrapper(tool_name, original_tool, validator)
                
                # Replace the original tool with our fixed wrapper
                server.tools[tool_name] = fixed_wrapper
                logger.info(f"✅ Applied parameter handling fix to {tool_name}")
                fixes_applied += 1
    
    logger.info(f"✅ Applied parameter handling fixes to {fixes_applied} IPFS tools")
    return fixes_applied > 0

if __name__ == "__main__":
    logger.info("This module should be imported and used with an MCP server, not run directly.")
