#!/usr/bin/env python3
"""
Simple MCP Validator
A lightweight validator to test basic MCP functionality
"""

import argparse
import json
import requests
import sys
import time
from typing import Dict, Any, List, Optional

def log(message: str) -> None:
    """Simple logging function"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")

class MCPValidator:
    def __init__(self, url: str = "http://localhost:9997"):
        self.base_url = url
        self.jsonrpc_url = f"{self.base_url}/jsonrpc" 
        self.health_url = f"{self.base_url}/health"
        self.all_tests_passed = True
        log(f"Initialized MCP validator for server at {self.base_url}")
        
    def check_health(self) -> bool:
        """Check if the server's health endpoint is responding"""
        log("Testing health endpoint...")
        try:
            response = requests.get(self.health_url, timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                log(f"Health check passed! Server status: {health_data.get('status')}, " +
                    f"version: {health_data.get('version')}, " +
                    f"tools count: {health_data.get('tools_count')}")
                return True
            else:
                log(f"Health check failed: Status code {response.status_code}")
                return False
        except Exception as e:
            log(f"Health check failed with error: {str(e)}")
            return False
    
    def call_jsonrpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a JSON-RPC call to the server"""
        if params is None:
            params = {}
            
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000)
        }
        
        try:
            response = requests.post(self.jsonrpc_url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log(f"Error calling {method}: {str(e)}")
            return {"error": {"message": str(e)}}
    
    def test_ping(self) -> bool:
        """Test the ping method"""
        log("Testing ping method...")
        result = self.call_jsonrpc("ping")
        if "result" in result and result["result"] == "pong":
            log("Ping test passed!")
            return True
        else:
            log(f"Ping test failed: {json.dumps(result)}")
            self.all_tests_passed = False
            return False
    
    def test_tool_methods(self) -> Dict[str, bool]:
        """Test both get_tools and list_tools methods"""
        results = {}
        
        # Test get_tools
        log("Testing get_tools method...")
        get_tools_result = self.call_jsonrpc("get_tools")
        if "result" in get_tools_result and "tools" in get_tools_result["result"]:
            tool_count = len(get_tools_result["result"]["tools"])
            log(f"get_tools test passed! Found {tool_count} tools.")
            results["get_tools"] = True
        else:
            log(f"get_tools test failed: {json.dumps(get_tools_result)}")
            results["get_tools"] = False
            self.all_tests_passed = False
        
        # Test list_tools (which may be an alias for get_tools)
        log("Testing list_tools method...")
        list_tools_result = self.call_jsonrpc("list_tools")
        if "result" in list_tools_result and "tools" in list_tools_result["result"]:
            tool_count = len(list_tools_result["result"]["tools"])
            log(f"list_tools test passed! Found {tool_count} tools.")
            results["list_tools"] = True
        else:
            log(f"list_tools test failed: {json.dumps(list_tools_result)}")
            results["list_tools"] = False
            self.all_tests_passed = False
            
        return results
    
    def test_server_info(self) -> bool:
        """Test the get_server_info method"""
        log("Testing get_server_info method...")
        result = self.call_jsonrpc("get_server_info")
        if "result" in result and "version" in result["result"]:
            log(f"get_server_info test passed! Version: {result['result']['version']}")
            return True
        else:
            log(f"get_server_info test failed: {json.dumps(result)}")
            self.all_tests_passed = False
            return False
            
    def run_all_tests(self) -> bool:
        """Run all validation tests"""
        log("Starting MCP validation tests...")
        
        # First check if the server is healthy
        if not self.check_health():
            log("Server health check failed, aborting further tests")
            return False
            
        # Run the JSON-RPC tests
        self.test_ping()
        self.test_tool_methods()
        self.test_server_info()
        
        # Report final status
        if self.all_tests_passed:
            log("All MCP validation tests PASSED! The server is working correctly.")
        else:
            log("Some MCP validation tests FAILED. The server may have issues.")
            
        return self.all_tests_passed

def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(description="Simple MCP Validator")
    parser.add_argument("--url", type=str, default="http://localhost:9997", 
                       help="The base URL of the MCP server")
    args = parser.parse_args()
    
    validator = MCPValidator(url=args.url)
    success = validator.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
