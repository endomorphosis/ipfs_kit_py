#!/usr/bin/env python3
"""
Parameter Handling Integration Tests

This script tests that the parameter handling fixes are working correctly
with the enhanced MCP server.
"""

import os
import sys
import json
import time
import logging
import requests
import traceback
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("param_tests.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("param-tests")

# Configuration
PORT = 9998
HOST = "localhost"
ENDPOINT = f"http://{HOST}:{PORT}/jsonrpc"
RESULTS_DIR = "test_results"

# Ensure results directory exists
Path(RESULTS_DIR).mkdir(exist_ok=True)

def execute_jsonrpc(method, params):
    """
    Execute a JSON-RPC method call.
    
    Args:
        method: The method name
        params: The parameters for the method
        
    Returns:
        The JSON-RPC response
    """
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": int(time.time())
    }
    
    try:
        response = requests.post(
            ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Request failed with status code {response.status_code}")
            return {"error": f"HTTP {response.status_code}", "raw_response": response.text}
    except Exception as e:
        logger.error(f"Error executing JSON-RPC: {e}")
        return {"error": str(e)}

def test_ipfs_add():
    """Test ipfs_add with various parameter combinations."""
    logger.info("Testing ipfs_add parameter handling")
    
    test_cases = [
        {
            "name": "Basic add",
            "params": {"content": "Hello IPFS!"},
            "expected_result": True,
            "check_points": ["cid"]
        },
        {
            "name": "Add with filename",
            "params": {"content": "Hello with filename", "filename": "test.txt"},
            "expected_result": True,
            "check_points": ["cid", "name"]
        },
        {
            "name": "Add with string boolean (true)",
            "params": {"content": "Hello with string boolean", "pin": "true"},
            "expected_result": True,
            "check_points": ["cid", "pinned"]
        },
        {
            "name": "Add with string boolean (false)",
            "params": {"content": "Hello with string boolean", "pin": "false"},
            "expected_result": True,
            "check_points": ["cid", "pinned"]
        },
        {
            "name": "Add with wrap_with_directory",
            "params": {"content": "Hello with wrap", "wrap_with_directory": True},
            "expected_result": True,
            "check_points": ["cid"]
        },
        {
            "name": "Add with filename (should auto-wrap)",
            "params": {"content": "Hello with auto-wrap", "filename": "auto_wrap.txt"},
            "expected_result": True,
            "check_points": ["cid", "name"]
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        logger.info(f"Running test: {test_case['name']}")
        
        response = execute_jsonrpc("ipfs_add", test_case["params"])
        
        result = {
            "name": test_case["name"],
            "params": test_case["params"],
            "response": response,
            "passed": False
        }
        
        if "error" in response:
            logger.error(f"Test failed: {response['error']}")
        elif "result" not in response:
            logger.error("Test failed: No result in response")
        else:
            success = True
            for check in test_case["check_points"]:
                if check not in str(response["result"]):
                    logger.error(f"Test failed: '{check}' not in result")
                    success = False
                    break
            
            if success:
                logger.info("Test passed!")
                result["passed"] = True
            else:
                logger.error(f"Test failed: Response does not meet expectations")
        
        results.append(result)
    
    return results

def test_ipfs_cat():
    """Test ipfs_cat with various parameter combinations."""
    logger.info("Testing ipfs_cat parameter handling")
    
    # First, add some content to get a valid CID
    add_response = execute_jsonrpc("ipfs_add", {"content": "Content for cat testing"})
    
    if "error" in add_response or "result" not in add_response:
        logger.error("Failed to add content for cat testing")
        return []
    
    cid = add_response["result"].get("cid") or add_response["result"].get("hash")
    
    if not cid:
        logger.error("No CID in add response")
        return []
    
    logger.info(f"Added content with CID: {cid}")
    
    test_cases = [
        {
            "name": "Basic cat",
            "params": {"hash": cid},
            "expected_result": True,
            "check_points": ["content"]
        },
        {
            "name": "Cat with offset",
            "params": {"hash": cid, "offset": 5},
            "expected_result": True,
            "check_points": ["content"]
        },
        {
            "name": "Cat with string offset",
            "params": {"hash": cid, "offset": "10"},
            "expected_result": True,
            "check_points": ["content"]
        },
        {
            "name": "Cat with length",
            "params": {"hash": cid, "length": 10},
            "expected_result": True,
            "check_points": ["content"]
        },
        {
            "name": "Cat with offset and length",
            "params": {"hash": cid, "offset": 5, "length": 10},
            "expected_result": True,
            "check_points": ["content"]
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        logger.info(f"Running test: {test_case['name']}")
        
        response = execute_jsonrpc("ipfs_cat", test_case["params"])
        
        result = {
            "name": test_case["name"],
            "params": test_case["params"],
            "response": response,
            "passed": False
        }
        
        if "error" in response:
            logger.error(f"Test failed: {response['error']}")
        elif "result" not in response:
            logger.error("Test failed: No result in response")
        else:
            success = True
            for check in test_case["check_points"]:
                if check not in str(response["result"]):
                    logger.error(f"Test failed: '{check}' not in result")
                    success = False
                    break
            
            if success:
                logger.info("Test passed!")
                result["passed"] = True
            else:
                logger.error(f"Test failed: Response does not meet expectations")
        
        results.append(result)
    
    return results

def test_ipfs_files_ls():
    """Test ipfs_files_ls with various parameter combinations."""
    logger.info("Testing ipfs_files_ls parameter handling")
    
    test_cases = [
        {
            "name": "Basic ls",
            "params": {"path": "/"},
            "expected_result": True,
            "check_points": ["entries"]
        },
        {
            "name": "Ls with long format",
            "params": {"path": "/", "long": True},
            "expected_result": True,
            "check_points": ["entries"]
        },
        {
            "name": "Ls with string boolean",
            "params": {"path": "/", "long": "true"},
            "expected_result": True,
            "check_points": ["entries"]
        },
        {
            "name": "Ls with no path (should default to /)",
            "params": {},
            "expected_result": True,
            "check_points": ["entries"]
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        logger.info(f"Running test: {test_case['name']}")
        
        response = execute_jsonrpc("ipfs_files_ls", test_case["params"])
        
        result = {
            "name": test_case["name"],
            "params": test_case["params"],
            "response": response,
            "passed": False
        }
        
        if "error" in response:
            logger.error(f"Test failed: {response['error']}")
        elif "result" not in response:
            logger.error("Test failed: No result in response")
        else:
            success = True
            for check in test_case["check_points"]:
                if check not in str(response["result"]):
                    logger.error(f"Test failed: '{check}' not in result")
                    success = False
                    break
            
            if success:
                logger.info("Test passed!")
                result["passed"] = True
            else:
                logger.error(f"Test failed: Response does not meet expectations")
        
        results.append(result)
    
    return results

def generate_report(results):
    """
    Generate a report from the test results.
    
    Args:
        results: Dictionary of test results by category
        
    Returns:
        tuple: (json_path, md_path) - Paths to the generated reports
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = Path(RESULTS_DIR) / f"param_tests_{timestamp}.json"
    md_path = Path(RESULTS_DIR) / f"param_tests_{timestamp}.md"
    
    # Calculate success rates
    total_tests = sum(len(tests) for tests in results.values())
    passed_tests = sum(sum(1 for test in tests if test["passed"]) for tests in results.values())
    
    # Save JSON report
    with open(json_path, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": f"{passed_tests/total_tests*100:.1f}%" if total_tests > 0 else "N/A",
            "results": results
        }, f, indent=2)
    
    # Generate Markdown report
    md_content = f"""# Parameter Handling Integration Test Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

- Total tests: {total_tests}
- Passed tests: {passed_tests}
- Success rate: {passed_tests/total_tests*100:.1f}% if total_tests > 0 else "N/A"}

## Results

"""
    
    for category, tests in results.items():
        md_content += f"### {category}\n\n"
        md_content += "| Test | Parameters | Status | Details |\n"
        md_content += "|------|------------|--------|--------|\n"
        
        for test in tests:
            name = test["name"]
            params = json.dumps(test["params"])
            status = "✅ PASS" if test["passed"] else "❌ FAIL"
            
            if test["passed"]:
                if "result" in test["response"]:
                    details = str(test["response"]["result"])
                    if len(details) > 50:
                        details = details[:47] + "..."
                else:
                    details = "No result"
            else:
                if "error" in test["response"]:
                    details = f"Error: {test['response']['error']}"
                elif "result" in test["response"]:
                    details = f"Unexpected result: {test['response']['result']}"
                else:
                    details = "Unknown error"
            
            md_content += f"| {name} | `{params}` | {status} | `{details}` |\n"
        
        md_content += "\n"
    
    # Save Markdown report
    with open(md_path, "w") as f:
        f.write(md_content)
    
    logger.info(f"Reports generated at:")
    logger.info(f"  - JSON: {json_path}")
    logger.info(f"  - Markdown: {md_path}")
    
    return json_path, md_path

def check_server():
    """Check if the server is running."""
    try:
        response = requests.get(f"http://{HOST}:{PORT}/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ Server is running and responding to health checks")
            return True
        else:
            logger.error(f"❌ Server is not responding correctly: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Server is not running or not accessible: {e}")
        return False

def main():
    """Main entry point."""
    logger.info("Starting Parameter Handling Integration Tests")
    
    # Check if server is running
    if not check_server():
        logger.error("Server must be running to run these tests. Please start the server first.")
        return 1
    
    # Initialize results dictionary
    all_results = {}
    
    # Test ipfs_add
    all_results["ipfs_add"] = test_ipfs_add()
    
    # Test ipfs_cat
    all_results["ipfs_cat"] = test_ipfs_cat()
    
    # Test ipfs_files_ls
    all_results["ipfs_files_ls"] = test_ipfs_files_ls()
    
    # Generate report
    generate_report(all_results)
    
    # Check overall success
    total_tests = sum(len(tests) for tests in all_results.values())
    passed_tests = sum(sum(1 for test in tests if test["passed"]) for tests in all_results.values())
    
    logger.info(f"\nOverall test results: {passed_tests}/{total_tests} tests passed "
                f"({passed_tests/total_tests*100:.1f}% success rate)")
    
    if passed_tests == total_tests:
        logger.info("✅ All parameter handling tests passed!")
        return 0
    else:
        logger.error(f"❌ {total_tests - passed_tests} parameter handling tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
