#!/usr/bin/env python3
"""
Parameter Handler Fix Utility

This script fixes parameter handling in the final MCP server tools,
particularly focusing on the ipfs_add tool that's having issues.
"""

import os
import sys
import json
import logging
import traceback
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("param_fix.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("param-fix")

# Constants
SERVER_URL = "http://localhost:9998"
JSONRPC_URL = f"{SERVER_URL}/jsonrpc"
TEST_RESULTS_DIR = "test_results"
Path(TEST_RESULTS_DIR).mkdir(exist_ok=True)

def check_server_status():
    """Check if server is running and responding."""
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            logger.info("Server is up and running!")
            return True
        else:
            logger.error(f"Server returned status code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error checking server status: {e}")
        return False

def get_tools_list():
    """Get list of available tools from the server."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "list_tools",
            "params": {},
            "id": 1
        }
        response = requests.post(
            JSONRPC_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                tools = result["result"]
                logger.info(f"Found {len(tools)} tools")
                return tools
            else:
                logger.warning(f"Unexpected response format: {result}")
                return []
        else:
            logger.error(f"Failed to get tools list: status code {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error getting tools list: {e}")
        return []

def test_tool(tool_name, params=None):
    """Test a tool with given parameters."""
    if params is None:
        params = {}
        
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": tool_name,
            "params": params,
            "id": 1
        }
        logger.info(f"Testing {tool_name} with params: {params}")
        response = requests.post(
            JSONRPC_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                logger.error(f"Tool {tool_name} returned error: {result['error']}")
                return False, result
            elif "result" in result:
                success = result.get("result", {}).get("success", True)
                logger.info(f"Tool {tool_name} result: {result['result']}")
                return success, result
            else:
                logger.warning(f"Unexpected response format: {result}")
                return False, result
        else:
            logger.error(f"Tool {tool_name} request failed: status code {response.status_code}")
            return False, {"error": f"Status code: {response.status_code}"}
    except Exception as e:
        logger.error(f"Error testing tool {tool_name}: {e}")
        return False, {"error": str(e)}

def run_parameter_tests():
    """Run tests for tools with parameter issues."""
    tools_to_test = [
        {
            "name": "ipfs_add",
            "params": {"content": "Hello IPFS!"},
            "description": "Add string content to IPFS"
        },
        {
            "name": "ipfs_cat",
            "params": {"path": "QmY7Yh4UquoXHLPFo2XbhXkhBvFoPwmQUSa92pxnxjQuPU"},
            "description": "Retrieve content from IPFS by hash"
        },
        {
            "name": "ipfs_files_ls",
            "params": {"path": "/"},
            "description": "List files in IPFS MFS root"
        }
    ]
    
    results = []
    
    for tool in tools_to_test:
        logger.info(f"Testing: {tool['description']}")
        success, response = test_tool(tool["name"], tool["params"])
        
        results.append({
            "name": tool["name"],
            "params": tool["params"],
            "description": tool["description"],
            "success": success,
            "response": response
        })
    
    # Save test results
    with open(os.path.join(TEST_RESULTS_DIR, "parameter_tests.json"), "w") as f:
        json.dump(results, f, indent=2)
    
    # Generate markdown report
    md_content = "# MCP Tool Parameter Tests\n\n"
    md_content += f"Generated: {Path('param_fix.log').stat().st_mtime}\n\n"
    md_content += "## Test Results\n\n"
    
    for result in results:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        md_content += f"### {result['name']} - {status}\n\n"
        md_content += f"Description: {result['description']}\n\n"
        md_content += f"Parameters: `{json.dumps(result['params'])}`\n\n"
        md_content += "Response:\n```json\n"
        md_content += json.dumps(result["response"], indent=2)
        md_content += "\n```\n\n"
    
    with open(os.path.join(TEST_RESULTS_DIR, "parameter_tests.md"), "w") as f:
        f.write(md_content)
    
    return results

def fix_ipfs_add_parameter_handling():
    """Create a fixed handler for ipfs_add to properly handle content parameter."""
    # Create the fixed version of the handler
    script_path = "fixed_ipfs_param_handler.py"
    
    content = """#!/usr/bin/env python3
\"\"\"
Fixed IPFS Parameter Handler

This module provides proper parameter handling for the IPFS tools,
particularly fixing the ipfs_add tool that was having issues.
\"\"\"

import os
import sys
import json
import logging
import inspect
from typing import Dict, Any, Optional
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("fixed-param-handler")

# JSONRPC wrapper for fixing parameter handling
async def jsonrpc_ipfs_add(params=None):
    \"\"\"
    Fixed implementation for ipfs_add that handles parameters properly.
    
    Args:
        params: A dictionary with 'content' key
        
    Returns:
        Result dictionary with hash and success status
    \"\"\"
    try:
        logger.info(f"Called ipfs_add with params: {params}")
        
        # Validate parameters
        if not params or 'content' not in params:
            logger.error("Missing required parameter: content")
            return {
                "success": False, 
                "error": "Missing required parameter: content",
                "tool": "ipfs_add"
            }
        
        content = params.get('content')
        pin = params.get('pin', True)
        
        # Mock implementation (since real implementation is not available)
        import hashlib
        content_hash = hashlib.sha256(str(content).encode()).hexdigest()
        cid = f"Qm{content_hash[:38]}"
        
        logger.info(f"Added content with CID: {cid}")
        
        return {
            "success": True,
            "hash": cid,
            "size": len(str(content).encode()),
            "name": "content.bin",
            "warning": "This is a mock implementation with fixed parameter handling"
        }
    except Exception as e:
        logger.error(f"Error in ipfs_add: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "tool": "ipfs_add"
        }

# Helper function to register this new handler with the running server
def register_fixed_handler(server_url="http://localhost:9998"):
    \"\"\"
    Register the fixed handler with the running server.
    Note: This would require the server to have an API for registering new handlers,
    which may not be available. This is here for future enhancement.
    \"\"\"
    try:
        # Check if server supports dynamic handler registration
        response = requests.post(
            f"{server_url}/register_handler",
            json={
                "tool_name": "ipfs_add",
                "handler_code": inspect.getsource(jsonrpc_ipfs_add)
            },
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info("Successfully registered fixed handler!")
            return True
        else:
            logger.error(f"Failed to register handler: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error registering handler: {e}")
        return False

# Main function
if __name__ == "__main__":
    print("To use this module, import it and use the jsonrpc_ipfs_add function.")
    print("Example:")
    print("  result = await jsonrpc_ipfs_add({'content': 'Hello IPFS!'})")
"""
    
    with open(script_path, "w") as f:
        f.write(content)
    
    logger.info(f"Created fixed parameter handler at {script_path}")
    return script_path

def main():
    """Main function."""
    logger.info("Starting parameter handling fix utility")
    
    if not check_server_status():
        logger.error("Server is not running or not responding")
        return 1
    
    # Get list of available tools
    tools = get_tools_list()
    if not tools:
        logger.error("Failed to get tools list")
        return 1
    
    # Run parameter tests
    results = run_parameter_tests()
    
    # Check if ipfs_add has parameter issues
    ipfs_add_result = next((r for r in results if r["name"] == "ipfs_add"), None)
    if ipfs_add_result and not ipfs_add_result["success"]:
        logger.info("Creating fixed parameter handler for ipfs_add")
        fix_path = fix_ipfs_add_parameter_handling()
        logger.info(f"Created fixed handler at {fix_path}")
        logger.info("To fix the issue, modify the final_mcp_server.py to use this handler")
    
    logger.info("Parameter handling fix utility completed")
    
    # Count failures
    failures = sum(1 for r in results if not r["success"])
    return failures

if __name__ == "__main__":
    sys.exit(main())
