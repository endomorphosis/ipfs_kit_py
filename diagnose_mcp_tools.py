#!/usr/bin/env python3
"""
Script to diagnose and fix the MCP server registration issues.
This script should be run after the MCP server is started.
"""

import requests
import json
import time
import logging
import sys
import os
from typing import Dict, List, Any, Optional, Tuple
import tabulate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("mcp-diagnostics")

def jsonrpc_call(method, params=None):
    """Make a JSON-RPC call to the MCP server."""
    url = "http://localhost:9998/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": int(time.time() * 1000)
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                logger.error(f"Error in JSON-RPC call: {result['error']}")
                return {"error": result["error"]}
            return result.get("result", {})
        else:
            return {"error": f"HTTP error {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def check_server_health():
    """Check if the MCP server is running and healthy."""
    try:
        response = requests.get("http://localhost:9998/health", timeout=2)
        if response.status_code == 200:
            logger.info("MCP server is healthy")
            return True
        else:
            logger.error(f"MCP server health check failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"MCP server health check failed: {e}")
        return False

def get_available_tools() -> List[Dict[str, Any]]:
    """Get all available tools from the MCP server."""
    result = jsonrpc_call("get_tools")
    if "error" in result:
        logger.error(f"Failed to get available tools: {result['error']}")
        return []
    
    return result if isinstance(result, list) else []

def test_ipfs_add():
    """Test the ipfs_add tool."""
    test_content = "Hello IPFS from diagnostics!"
    result = jsonrpc_call("ipfs_add", {"content": test_content})
    
    if "error" in result:
        logger.error(f"ipfs_add test failed: {result['error']}")
        return {"status": "failed", "error": result["error"]}
    
    if "cid" not in result:
        logger.error("ipfs_add test failed: No CID in response")
        return {"status": "failed", "error": "No CID in response"}
        
    logger.info(f"ipfs_add test succeeded. CID: {result['cid']}")
    return {"status": "success", "cid": result["cid"]}

def test_ipfs_cat(cid):
    """Test the ipfs_cat tool."""
    logger.info(f"Testing ipfs_cat with CID: {cid}")
    
    result = jsonrpc_call("ipfs_cat", {"cid": cid})
    
    if "error" in result:
        logger.error(f"ipfs_cat failed: {result['error']}")
        return None
    
    logger.info(f"ipfs_cat result: {result}")
    return result.get("content")

def test_ipfs_ls(cid):
    """Test the ipfs_ls tool."""
    logger.info(f"Testing ipfs_ls with CID: {cid}")
    
    result = jsonrpc_call("ipfs_ls", {"cid": cid})
    
    if "error" in result:
        logger.error(f"ipfs_ls failed: {result['error']}")
        return None
    
    logger.info(f"ipfs_ls result: {result}")
    return result

def test_ipfs_pin(cid):
    """Test the IPFS pin tools."""
    results = {}
    
    # Test pin_add
    result = jsonrpc_call("ipfs_pin_add", {"cid": cid})
    if "error" in result:
        logger.error(f"ipfs_pin_add test failed: {result['error']}")
        results["pin_add"] = {"status": "failed", "error": result["error"]}
    else:
        logger.info("ipfs_pin_add test succeeded")
        results["pin_add"] = {"status": "success"}
    
    # Test pin_ls
    result = jsonrpc_call("ipfs_pin_ls", {})
    if "error" in result:
        logger.error(f"ipfs_pin_ls test failed: {result['error']}")
        results["pin_ls"] = {"status": "failed", "error": result["error"]}
    else:
        pins = result.get("pins", [])
        if cid in pins:
            logger.info(f"ipfs_pin_ls test succeeded, found CID in pins")
            results["pin_ls"] = {"status": "success"}
        else:
            logger.warning(f"ipfs_pin_ls test partially succeeded, but CID not found in pins")
            results["pin_ls"] = {"status": "warning", "detail": "CID not found in pins"}
    
    # Test pin_rm
    result = jsonrpc_call("ipfs_pin_rm", {"cid": cid})
    if "error" in result:
        logger.error(f"ipfs_pin_rm test failed: {result['error']}")
        results["pin_rm"] = {"status": "failed", "error": result["error"]}
    else:
        logger.info("ipfs_pin_rm test succeeded")
        results["pin_rm"] = {"status": "success"}
    
    return results

def test_ipns_publish_resolve(cid):
    """Test the IPNS publish and resolve tools."""
    results = {}
    
    # Test name_publish
    result = jsonrpc_call("ipfs_name_publish", {"cid": cid})
    if "error" in result:
        logger.error(f"ipfs_name_publish test failed: {result['error']}")
        results["name_publish"] = {"status": "failed", "error": result["error"]}
        return results
    
    logger.info(f"ipfs_name_publish test succeeded")
    results["name_publish"] = {"status": "success"}
    
    if "name" not in result:
        logger.error("ipfs_name_publish didn't return required name field")
        results["name_resolve"] = {"status": "skipped", "detail": "No name returned from publish"}
        return results
    
    ipns_name = result["name"]
    logger.info(f"Published to IPNS name: {ipns_name}")
    
    # Test name_resolve
    result = jsonrpc_call("ipfs_name_resolve", {"name": ipns_name})
    if "error" in result:
        logger.error(f"ipfs_name_resolve test failed: {result['error']}")
        results["name_resolve"] = {"status": "failed", "error": result["error"]}
    else:
        if "cid" not in result:
            logger.warning("ipfs_name_resolve didn't return required CID field")
            results["name_resolve"] = {"status": "warning", "detail": "No CID in resolve response"}
        else:
            resolved_cid = result["cid"]
            if resolved_cid == cid:
                logger.info(f"ipfs_name_resolve test succeeded with matching CID")
                results["name_resolve"] = {"status": "success"}
            else:
                logger.warning(f"ipfs_name_resolve returned different CID: {resolved_cid} (expected {cid})")
                results["name_resolve"] = {"status": "warning", "detail": f"CID mismatch: {resolved_cid} != {cid}"}
    
    return results

def compare_required_vs_available_tools():
    """Compare the tools required by tests versus what is available."""
    required_tools = {
        'ipfs_add': "Add content to IPFS",
        'ipfs_cat': "Get content from IPFS",
        'ipfs_ls': "List directory contents in IPFS",
        'ipfs_pin_add': "Pin content in IPFS",
        'ipfs_pin_rm': "Remove a pin from IPFS content",
        'ipfs_pin_ls': "List pinned content in IPFS",
        'ipfs_name_publish': "Publish content to IPNS",
        'ipfs_name_resolve': "Resolve an IPNS name to its value"
    }
    
    # Get available tools
    available_tools = get_available_tools()
    available_tool_names = [t["name"] for t in available_tools]
    
    # Show status of each required tool
    print("\nTool Registration Status:")
    print("=" * 100)
    print(f"{'Tool Name':<30} {'Status':<10} {'Description':<50}")
    print("-" * 100)
    
    missing_tools = []
    for tool_name, description in required_tools.items():
        if tool_name in available_tool_names:
            status = "✅ Available"
        else:
            status = "❌ Missing"
            missing_tools.append(tool_name)
            
        print(f"{tool_name:<30} {status:<10} {description:<50}")
    
    print("=" * 100)
    
    if missing_tools:
        logger.warning(f"Found {len(missing_tools)} missing tools: {', '.join(missing_tools)}")
        return False
    else:
        logger.info("All required tools are available")
        return True

def run_functional_tests():
    """Run functional tests on the available tools."""
    logger.info("Running functional tests on available tools...")
    
    # Test ipfs_add first to get a CID
    add_result = test_ipfs_add()
    test_results = {"ipfs_add": add_result}
    
    if add_result.get("status") == "success":
        cid = add_result["cid"]
        
        # Test pin tools
        test_results["ipfs_pin"] = test_ipfs_pin(cid)
        
        # Test IPNS tools
        test_results["ipns"] = test_ipns_publish_resolve(cid)
    else:
        logger.error("Skipping further tests because ipfs_add failed")
    
    return test_results

def print_test_summary(test_results):
    """Print a summary of the test results."""
    print("\nFunctional Test Results:")
    print("=" * 80)
    
    if "ipfs_add" in test_results:
        add_result = test_results["ipfs_add"]
        status = add_result.get("status", "unknown")
        detail = ""
        if status == "success":
            detail = f"CID: {add_result.get('cid', 'N/A')}"
        elif status == "failed":
            detail = f"Error: {add_result.get('error', 'unknown error')}"
        
        print(f"ipfs_add: {status.upper()} {detail}")
    
    if "ipfs_pin" in test_results:
        pin_results = test_results["ipfs_pin"]
        print("\nIPFS Pin Tools:")
        for tool, result in pin_results.items():
            status = result.get("status", "unknown").upper()
            detail = ""
            if status == "FAILED":
                detail = f" - Error: {result.get('error', 'unknown error')}"
            elif status == "WARNING":
                detail = f" - {result.get('detail', '')}"
            
            print(f"  {tool}: {status}{detail}")
    
    if "ipns" in test_results:
        ipns_results = test_results["ipns"]
        print("\nIPNS Tools:")
        for tool, result in ipns_results.items():
            status = result.get("status", "unknown").upper()
            detail = ""
            if status == "FAILED":
                detail = f" - Error: {result.get('error', 'unknown error')}"
            elif status == "WARNING":
                detail = f" - {result.get('detail', '')}"
                
            print(f"  {tool}: {status}{detail}")
    
    print("=" * 80)

def main():
    """Main function."""
    logger.info("=== MCP Server Diagnostics ===")
    
    # Check if server is healthy
    if not check_server_health():
        logger.error("MCP server is not healthy. Exiting.")
        return False
    
    # Compare required vs. available tools
    tools_available = compare_required_vs_available_tools()
    
    # Run functional tests
    if tools_available:
        logger.info("All tools are available, running functional tests...")
    else:
        logger.warning("Some tools are missing, but will attempt functional tests anyway")
    
    test_results = run_functional_tests()
    print_test_summary(test_results)
    
    # Determine overall success
    success = True
    if not tools_available:
        success = False
    
    if "ipfs_add" in test_results and test_results["ipfs_add"].get("status") != "success":
        success = False
    
    if success:
        logger.info("Diagnostics completed successfully")
    else:
        logger.warning("Diagnostics identified issues that need to be addressed")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
