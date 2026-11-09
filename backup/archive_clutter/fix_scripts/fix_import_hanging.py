#!/usr/bin/env python3
"""
Fix IPFS Import Hanging

This script addresses the import hanging issues in the MCP server by providing
a solution that safely imports modules that might otherwise hang due to
circular imports or other issues.
"""

import os
import sys
import time
import signal
import logging
import importlib
import threading
import traceback
import multiprocessing
from typing import Optional, Dict, Any, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("fix-import-hanging")

def import_with_timeout(module_name: str, timeout: int = 10) -> Tuple[bool, Optional[Any], Optional[str]]:
    """
    Import a module with a timeout to prevent hanging.
    
    Args:
        module_name: Name of the module to import
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (success, module, error_message)
    """
    result_queue = multiprocessing.Queue()
    
    def import_target(module_name, result_queue):
        """Target function for importing a module in a separate process."""
        try:
            module = importlib.import_module(module_name)
            result_queue.put((True, None))
        except Exception as e:
            error_message = f"Error importing {module_name}: {str(e)}\n{traceback.format_exc()}"
            result_queue.put((False, error_message))
    
    # Start the import in a separate process
    process = multiprocessing.Process(target=import_target, args=(module_name, result_queue))
    process.start()
    
    # Wait for the process to complete or timeout
    process.join(timeout)
    
    if process.is_alive():
        # The import is hanging, terminate the process
        process.terminate()
        process.join()
        logger.error(f"Import of {module_name} timed out after {timeout} seconds")
        return False, None, f"Import timed out after {timeout} seconds"
    
    # Get the result
    try:
        success, error_message = result_queue.get(block=False)
        
        if success:
            # The import was successful, now actually import the module in this process
            try:
                module = importlib.import_module(module_name)
                return True, module, None
            except Exception as e:
                error_message = f"Error importing {module_name} in main process: {str(e)}\n{traceback.format_exc()}"
                return False, None, error_message
        else:
            return False, None, error_message
    except Exception as e:
        return False, None, f"Error getting result: {str(e)}"

def safe_import_unified_ipfs_tools() -> Tuple[bool, Optional[Any]]:
    """
    Safely import the unified_ipfs_tools module, addressing known issues.
    
    Returns:
        Tuple of (success, module)
    """
    logger.info("Attempting to safely import unified_ipfs_tools...")
    
    # First, try importing with timeout to detect hanging
    success, module, error = import_with_timeout("unified_ipfs_tools")
    
    if success:
        logger.info("✅ Successfully imported unified_ipfs_tools")
        return True, module
    else:
        logger.error(f"❌ Error importing unified_ipfs_tools: {error}")
        logger.info("Attempting to import with patching...")
        
        # Create a patched version of the module
        patch_unified_ipfs_tools()
        
        # Try importing the patched version
        try:
            import patched_unified_ipfs_tools
            logger.info("✅ Successfully imported patched_unified_ipfs_tools")
            return True, patched_unified_ipfs_tools
        except Exception as e:
            logger.error(f"❌ Error importing patched_unified_ipfs_tools: {e}")
            logger.error(traceback.format_exc())
            return False, None

def patch_unified_ipfs_tools() -> bool:
    """
    Create a patched version of the unified_ipfs_tools module that avoids import hanging.
    
    Returns:
        bool: True if patching was successful, False otherwise
    """
    try:
        # Read the original file
        with open("unified_ipfs_tools.py", "r") as f:
            content = f.read()
        
        # Apply patches to prevent hanging
        patched_content = content
        
        # Patch 1: Remove the problematic fixed_ipfs_model import
        import_block = """
# Try to import fixed IPFS model if available
try:
    from fixed_ipfs_model import IPFSModel as FixedIPFSModel, initialize_ipfs_model as fixed_initialize_ipfs_model
    FIXED_TOOL_MAP = {
        "ipfs_add": add_content,
        "ipfs_cat": cat,
        "ipfs_pin_add": pin_add,
        "ipfs_pin_rm": pin_rm,
        "ipfs_pin_ls": pin_ls,
        "ipfs_files_ls": files_ls,
        "ipfs_files_mkdir": files_mkdir,
        "ipfs_files_write": files_write,
        "ipfs_files_read": files_read,
        "ipfs_files_rm": files_rm,
        "ipfs_files_stat": files_stat,
        "ipfs_files_cp": files_cp,
        "ipfs_files_mv": files_mv
    }
    TOOL_STATUS["fixed_ipfs_model_available"] = True
    logger.info("✅ Fixed IPFS model available")
except ImportError as e:
    logger.warning(f"⚠️ Could not import fixed IPFS model: {e}")
    TOOL_STATUS["fixed_ipfs_model_available"] = False
    FIXED_TOOL_MAP = {}
except Exception as e:
    logger.error(f"❌ Unexpected error importing fixed IPFS model: {e}")
    logger.error(traceback.format_exc())
    TOOL_STATUS["fixed_ipfs_model_available"] = False
    FIXED_TOOL_MAP = {}
"""
        
        replacement = """
# Removed the problematic fixed_ipfs_model import to prevent hanging
TOOL_STATUS["fixed_ipfs_model_available"] = False
FIXED_TOOL_MAP = {}
logger.info("⚠️ Fixed IPFS model import explicitly disabled to prevent hanging")
"""
        
        patched_content = patched_content.replace(import_block, replacement)
        
        # Patch 2: Modify initialize_components to avoid initializing fixed_ipfs_model
        initialize_block = """
        # if TOOL_STATUS["fixed_ipfs_model_available"] and fixed_ipfs_model_instance is None:
        #      fixed_ipfs_model_instance = FixedIPFSModel()
        #      logger.info("✅ Fixed IPFS Model initialized")
"""
        
        replacement = """
        # Fixed IPFS Model initialization removed to prevent hanging
        # fixed_ipfs_model_instance will always be None
"""
        
        patched_content = patched_content.replace(initialize_block, replacement)
        
        # Write the patched content to a new file
        with open("patched_unified_ipfs_tools.py", "w") as f:
            f.write(patched_content)
        
        logger.info("✅ Successfully created patched_unified_ipfs_tools.py")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating patched unified_ipfs_tools: {e}")
        logger.error(traceback.format_exc())
        return False

def safe_import_final_mcp_server() -> Tuple[bool, Optional[Any]]:
    """
    Safely import the final_mcp_server module, addressing known issues.
    
    Returns:
        Tuple of (success, module)
    """
    logger.info("Attempting to safely import final_mcp_server...")
    
    # First, try importing with timeout to detect hanging
    success, module, error = import_with_timeout("final_mcp_server")
    
    if success:
        logger.info("✅ Successfully imported final_mcp_server")
        return True, module
    else:
        logger.error(f"❌ Error importing final_mcp_server: {error}")
        logger.info("Attempting to import with patching...")
        
        # Create a patched version of the module
        patch_final_mcp_server()
        
        # Try importing the patched version
        try:
            import patched_final_mcp_server
            logger.info("✅ Successfully imported patched_final_mcp_server")
            return True, patched_final_mcp_server
        except Exception as e:
            logger.error(f"❌ Error importing patched_final_mcp_server: {e}")
            logger.error(traceback.format_exc())
            return False, None

def patch_final_mcp_server() -> bool:
    """
    Create a patched version of the final_mcp_server module that avoids import hanging.
    
    Returns:
        bool: True if patching was successful, False otherwise
    """
    try:
        # Read the original file
        with open("final_mcp_server.py", "r") as f:
            content = f.read()
        
        # Apply patches to prevent hanging
        patched_content = content
        
        # Patch: Modify the register_ipfs_tools function to avoid the problematic imports
        register_ipfs_block = """
def register_ipfs_tools():
  try:
    from ipfs_kit_py.mcp import ipfs_extensions
    logger.info("Registering IPFS tools via ipfs_extensions...")
    ipfs_extensions.register_ipfs_tools(server)
    IPFS_AVAILABLE = True
    registered_tool_categories.add("ipfs_tools")
    return True
  except ImportError:
    logger.warning("ipfs_extensions not found, trying other methods...")
"""
        
        replacement = """
def register_ipfs_tools():
  try:
    # First try our safe import of unified_ipfs_tools
    import fix_import_hanging
    success, unified_tools_module = fix_import_hanging.safe_import_unified_ipfs_tools()
    
    if success and hasattr(unified_tools_module, 'register_all_ipfs_tools'):
      logger.info("Registering IPFS tools via safely imported unified_ipfs_tools...")
      current_tool_count = len(server.tools)
      unified_tools_module.register_all_ipfs_tools(server)
      final_tool_count = len(server.tools)
      tools_added = final_tool_count - current_tool_count
      
      if tools_added > 0:
        logger.info(f"✅ Added {tools_added} IPFS tools using safely imported unified_ipfs_tools")
        IPFS_AVAILABLE = True
        registered_tool_categories.add("ipfs_tools")
        
        # Apply parameter handling fixes if available
        try:
          import apply_fixed_ipfs_params
          apply_fixed_ipfs_params.apply_fixed_params_to_server(server)
        except ImportError:
          logger.warning("apply_fixed_ipfs_params not found, skipping parameter fixes")
        except Exception as e:
          logger.error(f"Error applying parameter fixes: {e}")
          logger.error(traceback.format_exc())
        
        return True
      else:
        logger.warning("⚠️ No tools added by safely imported unified_ipfs_tools")
    
    # Fall back to original approach
    from ipfs_kit_py.mcp import ipfs_extensions
    logger.info("Registering IPFS tools via ipfs_extensions...")
    ipfs_extensions.register_ipfs_tools(server)
    IPFS_AVAILABLE = True
    registered_tool_categories.add("ipfs_tools")
    return True
  except ImportError:
    logger.warning("ipfs_extensions not found, trying other methods...")
"""
        
        patched_content = patched_content.replace(register_ipfs_block, replacement)
        
        # Write the patched content to a new file
        with open("patched_final_mcp_server.py", "w") as f:
            f.write(patched_content)
        
        logger.info("✅ Successfully created patched_final_mcp_server.py")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating patched final_mcp_server: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting import hanging fix...")
    
    # Test importing unified_ipfs_tools
    success_unified, module_unified = safe_import_unified_ipfs_tools()
    
    # Test importing final_mcp_server
    success_final, module_final = safe_import_final_mcp_server()
    
    if success_unified and success_final:
        logger.info("✅ Successfully addressed import hanging issues")
        sys.exit(0)
    else:
        logger.error("❌ Failed to address all import hanging issues")
        sys.exit(1)
