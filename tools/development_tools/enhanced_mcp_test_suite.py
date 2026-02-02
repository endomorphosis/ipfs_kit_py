#!/usr/bin/env python3
"""
Enhanced MCP Server Test Suite

This script provides a comprehensive test suite for the MCP server with
detailed diagnostics and error reporting. It will help identify issues
more quickly in the future if they arise.

Usage:
  python3 enhanced_mcp_test_suite.py --url http://localhost:9997 [--output-dir data/test_results]
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Set
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("enhanced_mcp_test")

class MCPTestSuite:
    def __init__(self, base_url: str, output_dir: str = "data/test_results", verbose: bool = False):
        """Initialize the test suite.
        
        Args:
            base_url: Base URL of the MCP server
            output_dir: Directory to store test results
            verbose: Whether to enable verbose output
        """
        self.base_url = base_url.rstrip("/")
        self.jsonrpc_url = f"{self.base_url}/jsonrpc"
        self.health_url = f"{self.base_url}/health"
        self.output_dir = output_dir
        self.verbose = verbose
        self.test_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results = {
            "timestamp": self.test_id,
            "base_url": base_url,
            "tests": {},
            "overall_result": False,
            "error_count": 0,
            "success_count": 0,
            "server_info": {},
            "missing_parameters": [],
            "connection_issues": []
        }
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp."""
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
            
        if self.verbose:
            print(f"[{level}] {message}")
    
    def check_server_health(self) -> bool:
        """Check if the MCP server is healthy."""
        self.log(f"Checking server health at {self.health_url}")
        
        try:
            response = requests.get(self.health_url, timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                self.results["server_info"] = health_data
                self.log(f"Server is healthy: {json.dumps(health_data)}", "INFO")
                return True
            else:
                self.results["connection_issues"].append({
                    "endpoint": "health",
                    "status_code": response.status_code,
                    "error": response.text
                })
                self.log(f"Server health check failed: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.results["connection_issues"].append({
                "endpoint": "health",
                "error": str(e)
            })
            self.log(f"Error checking server health: {e}", "ERROR")
            return False
    
    def call_jsonrpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """Call a JSON-RPC method on the MCP server.
        
        Args:
            method: Name of the method to call
            params: Parameters to pass to the method
            
        Returns:
            Tuple of (success, result)
        """
        if params is None:
            params = {}
            
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000)
        }
        
        self.log(f"Calling JSON-RPC method {method} with params: {json.dumps(params)}")
        
        try:
            response = requests.post(
                self.jsonrpc_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30  # Increased timeout for complex operations
            )
            
            if response.status_code != 200:
                self.log(f"JSON-RPC call failed: {response.status_code} - {response.text}", "ERROR")
                return False, {"error": {"code": response.status_code, "message": response.text}}
                
            result = response.json()
            
            if "error" in result:
                self.log(f"JSON-RPC error: {json.dumps(result['error'])}", "ERROR")
                return False, result
                
            if "result" in result:
                if self.verbose:
                    self.log(f"JSON-RPC result: {json.dumps(result['result'])}")
                return True, result
                
            self.log(f"Unexpected JSON-RPC response: {json.dumps(result)}", "WARNING")
            return False, result
            
        except Exception as e:
            self.log(f"Exception during JSON-RPC call to {method}: {e}", "ERROR")
            return False, {"error": {"code": -32603, "message": str(e)}}
    
    def test_jsonrpc_endpoint(self) -> bool:
        """Test the JSON-RPC endpoint with basic methods."""
        self.log("Testing basic JSON-RPC methods")
        
        methods = ["ping", "get_tools", "list_tools", "get_server_info"]
        all_passed = True
        
        for method in methods:
            self.log(f"Testing {method} method")
            success, result = self.call_jsonrpc(method)
            
            self.results["tests"][method] = {
                "success": success,
                "result": result
            }
            
            if success:
                self.results["success_count"] += 1
                self.log(f"Method {method} test passed", "INFO")
            else:
                self.results["error_count"] += 1
                all_passed = False
                self.log(f"Method {method} test failed", "ERROR")
        
        return all_passed
    
    def test_tool_parameters(self) -> bool:
        """Test if all tools have proper parameters defined."""
        self.log("Testing tool parameters")
        
        # Get all tools
        success, result = self.call_jsonrpc("get_tools")
        if not success:
            self.log("Failed to get tools, skipping parameter check", "ERROR")
            return False
            
        tools = result.get("result", {}).get("tools", [])
        missing_parameters = []
        
        for tool in tools:
            tool_name = tool.get("name")
            parameters = tool.get("parameters", {})
            description = tool.get("description", "")
            
            # Check if tool has empty parameters but description suggests it needs some
            needs_params = any(keyword in description.lower() for keyword in ["path", "file", "cid", "id", "content"])
            if needs_params and not parameters and len(description) > 0:
                missing_parameters.append({
                    "tool": tool_name,
                    "description": description
                })
                self.log(f"Tool {tool_name} might be missing parameters based on its description", "WARNING")
        
        self.results["missing_parameters"] = missing_parameters
        return len(missing_parameters) == 0
    
    def test_ipfs_functionality(self) -> bool:
        """Test basic IPFS functionality if available."""
        self.log("Testing IPFS functionality")
        
        # Check if IPFS tools are available
        success, result = self.call_jsonrpc("get_tools")
        if not success:
            self.log("Failed to get tools, skipping IPFS functionality check", "ERROR")
            return False
            
        tools = result.get("result", {}).get("tools", [])
        tool_names = [tool.get("name") for tool in tools]
        
        ipfs_tools = [name for name in tool_names if name.startswith("ipfs_")]
        if not ipfs_tools:
            self.log("No IPFS tools found, skipping IPFS functionality check", "WARNING")
            return True
            
        # Test adding content to IPFS if the tool is available
        if "ipfs_add" in tool_names:
            test_content = f"Hello IPFS from enhanced test suite! {datetime.now().isoformat()}"
            success, result = self.call_jsonrpc("ipfs_add", {"content": test_content})
            
            self.results["tests"]["ipfs_add"] = {
                "success": success,
                "result": result
            }
            
            if success and "result" in result and "cid" in result["result"]:
                cid = result["result"]["cid"]
                self.log(f"Successfully added content to IPFS, CID: {cid}", "INFO")
                
                # Test retrieving content if the tool is available
                if "ipfs_cat" in tool_names:
                    success, result = self.call_jsonrpc("ipfs_cat", {"cid": cid})
                    
                    self.results["tests"]["ipfs_cat"] = {
                        "success": success,
                        "result": result
                    }
                    
                    if success and "result" in result and "content" in result["result"]:
                        retrieved_content = result["result"]["content"]
                        if retrieved_content == test_content:
                            self.log("Successfully retrieved content from IPFS, content matches", "INFO")
                            return True
                        else:
                            self.log(f"Retrieved content doesn't match: {retrieved_content} vs {test_content}", "ERROR")
                            return False
                    else:
                        self.log("Failed to retrieve content from IPFS", "ERROR")
                        return False
            else:
                self.log("Failed to add content to IPFS", "ERROR")
                return False
        
        # If we didn't run the specific test but IPFS tools are available, consider it a success
        return True
    
    def run_all_tests(self) -> bool:
        """Run all tests and return overall result."""
        start_time = time.time()
        self.log("Starting MCP server test suite")
        
        # Step 1: Check server health
        health_check = self.check_server_health()
        if not health_check:
            self.log("Server health check failed, stopping tests", "ERROR")
            self.results["overall_result"] = False
            self.save_results()
            return False
        
        # Step 2: Test JSON-RPC endpoint
        jsonrpc_test = self.test_jsonrpc_endpoint()
        if not jsonrpc_test:
            self.log("Basic JSON-RPC tests failed", "ERROR")
        
        # Step 3: Test tool parameters
        param_test = self.test_tool_parameters()
        if not param_test:
            self.log("Tool parameter check found issues", "WARNING")
        
        # Step 4: Test IPFS functionality if available
        ipfs_test = self.test_ipfs_functionality()
        if not ipfs_test:
            self.log("IPFS functionality test failed", "ERROR")
        
        # Calculate overall result
        self.results["overall_result"] = health_check and jsonrpc_test
        self.results["execution_time"] = time.time() - start_time
        
        # Save results
        self.save_results()
        
        # Print summary
        self.print_summary()
        
        return self.results["overall_result"]
    
    def save_results(self):
        """Save test results to a file."""
        filename = f"mcp_test_{self.test_id}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, "w") as f:
            json.dump(self.results, f, indent=2)
        
        self.log(f"Test results saved to {filepath}", "INFO")
    
    def print_summary(self):
        """Print a summary of the test results."""
        print("\n" + "="*80)
        print(f"MCP SERVER TEST SUMMARY")
        print("="*80)
        print(f"Server URL: {self.base_url}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Overall Result: {'PASSED' if self.results['overall_result'] else 'FAILED'}")
        print(f"Success Count: {self.results['success_count']}")
        print(f"Error Count: {self.results['error_count']}")
        print(f"Execution Time: {self.results['execution_time']:.2f} seconds")
        print("-"*80)
        
        # Server info
        if self.results["server_info"]:
            print("Server Information:")
            for key, value in self.results["server_info"].items():
                print(f"  {key}: {value}")
        
        # Missing parameters warning
        if self.results["missing_parameters"]:
            print("\nWARNING: Tools with potentially missing parameters:")
            for item in self.results["missing_parameters"]:
                print(f"  {item['tool']} - {item['description']}")
        
        # Connection issues
        if self.results["connection_issues"]:
            print("\nConnection Issues:")
            for issue in self.results["connection_issues"]:
                print(f"  {issue['endpoint']} - {issue.get('status_code', 'N/A')} - {issue.get('error', 'Unknown error')}")
        
        print("="*80)

def main():
    """Run the MCP server test suite."""
    parser = argparse.ArgumentParser(description="Enhanced MCP Server Test Suite")
    parser.add_argument("--url", type=str, default="http://localhost:9997", help="Base URL of the MCP server")
    parser.add_argument("--output-dir", type=str, default="data/test_results", help="Directory to store test results")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    test_suite = MCPTestSuite(args.url, args.output_dir, args.verbose)
    success = test_suite.run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
