#!/usr/bin/env python3
"""
Quick fix for the JSON-RPC dispatcher issue in fixed_final_mcp_server.py
"""

import os
import sys
import re
import logging
import traceback
import shutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def backup_file(file_path):
    """Create a backup of the file."""
    backup_path = f"{file_path}.bak.jsonrpc_fix"
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup at {backup_path}")
    return backup_path

def fix_jsonrpc_dispatcher(file_path):
    """Fix the JSON-RPC dispatcher in fixed_final_mcp_server.py."""
    target_file = file_path
    
    # Create a backup
    backup_file(target_file)
    
    logger.info(f"Reading {target_file}...")
    with open(target_file, 'r') as f:
        content = f.read()
    
    # Fix the setup_jsonrpc function
    setup_jsonrpc_pattern = re.compile(
        r'(def setup_jsonrpc\(\):.*?)from jsonrpc\.dispatcher import Dispatcher(.*?)jsonrpc_dispatcher = Dispatcher\(\)(.*?return False)',
        re.DOTALL
    )
    
    if setup_jsonrpc_pattern.search(content):
        # Replace with the updated jsonrpcserver import and dispatch method
        modified_content = setup_jsonrpc_pattern.sub(
            r'\1try:\n        from jsonrpcserver import dispatch, methods\n        \n        global jsonrpc_dispatcher\n        jsonrpc_dispatcher = methods\n        \n        # Add method to dispatcher with proper async handling\n        logger.info("JSON-RPC dispatcher initialized successfully")\n        return True\n    except ImportError:\n        logger.error("Failed to import JSON-RPC components: No module named \'jsonrpcserver\'")\n        logger.info("Please install required dependencies with: pip install jsonrpcserver")\n        return False\n    except Exception as e:\n        logger.error(f"Failed to import JSON-RPC components: {e}")\n        logger.info("Please install required dependencies with: pip install jsonrpcserver")\3',
            content
        )
        
        logger.info("Updated setup_jsonrpc function with correct imports and initialization.")
    else:
        logger.error("Could not find setup_jsonrpc function with expected pattern.")
        return False
    
    # Fix the handle_jsonrpc function
    handle_jsonrpc_pattern = re.compile(
        r'(async def handle_jsonrpc\(request\):.*?)response = await jsonrpc_dispatcher\.dispatch\(request_json\)(.*?return JSONResponse\()',
        re.DOTALL
    )
    
    if handle_jsonrpc_pattern.search(modified_content):
        modified_content = handle_jsonrpc_pattern.sub(
            r'\1from jsonrpcserver.responses import JsonResponse\n        \n        # Process the request\n        response_dict = await dispatch(request_json)\n        \2return JSONResponse(response_dict, status_code=200\n        )',
            modified_content
        )
        
        logger.info("Updated handle_jsonrpc function to use the jsonrpcserver dispatch method.")
    else:
        logger.warning("Could not find handle_jsonrpc function with expected pattern. Skipping this update.")
    
    # Write the modified content back to the file
    logger.info(f"Writing changes back to {target_file}...")
    with open(target_file, 'w') as f:
        f.write(modified_content)
    
    return True

def main():
    """Main function."""
    logger.info("Fixing JSON-RPC dispatcher in fixed_final_mcp_server.py...")
    
    target_file = "/home/barberb/ipfs_kit_py/fixed_final_mcp_server.py"
    
    if not os.path.exists(target_file):
        logger.error(f"Target file {target_file} not found.")
        return 1
    
    jsonrpc_fix_result = fix_jsonrpc_dispatcher(target_file)
    
    if jsonrpc_fix_result:
        logger.info("\n✅ JSON-RPC fix applied successfully")
        logger.info("The server should now be able to handle JSON-RPC requests properly")
        logger.info("Restart the MCP server to apply the changes")
        return 0
    else:
        logger.error("Failed to apply JSON-RPC fixes")
        return 1

if __name__ == "__main__":
    sys.exit(main())
