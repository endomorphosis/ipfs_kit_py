#!/usr/bin/env python3
"""
MCP Server Quick Test Helper

A helper script that tests the essential functionality of an MCP server.
It provides a simple way to:
1. Verify server connectivity
2. Test basic JSON-RPC methods
3. Check tool availability
4. Diagnose common issues

Usage:
  python3 test_mcp_quick.py [--url http://localhost:9998] [--verbose]
"""

import argparse
import json
import sys
import time
import requests
from typing import Dict, Any, Optional, List, Tuple, Union

def log(message: str, verbose: bool = False) -> None:
    """Print a log message with timestamp."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")
    
class MCPQuickTester:
    """A quick tester for MCP servers."""
    
    def __init__(self, base_url: str = "http://localhost:9998", verbose: bool = False):
        """Initialize the tester."""
        self.base_url = base_url
        self.jsonrpc_url = f"{base_url}/jsonrpc"
        self.health_url = f"{base_url}/health"
        self.verbose = verbose
        self.all_tests_passed = True
        self.test_results = []
        
    def log(self, message: str) -> None:
        """Log a message."""
        log(message, self.verbose)
        
    def test_passed(self, test_name: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record a passing test."""
        self.log(f"✅ PASS: {test_name}")
        self.test_results.append({
            "name": test_name,
            "passed": True,
            "details": details
        })
        
    def test_failed(self, test_name: str, error_message: str) -> None:
        """Record a failing test."""
        self.all_tests_passed = False
        self.log(f"❌ FAIL: {test_name} - {error_message}")
        self.test_results.append({
            "name": test_name,
            "passed": False,
            "error": error_message
        })
        
    def make_jsonrpc_call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a JSON-RPC call."""
        if params is None:
            params = {}
            
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000)
        }
        
        try:
            response = requests.post(self.jsonrpc_url, json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": {"message": str(e)}}
            
    def check_health(self) -> bool:
        """Check server health."""
        self.log(f"Testing health endpoint: {self.health_url}")
        try:
            response = requests.get(self.health_url, timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                self.log(f"Health check passed! Server is healthy.")
                if self.verbose:
                    self.log(f"Health details: {json.dumps(health_data, indent=2)}")
                self.test_passed("Health Check", health_data)
                return True
            else:
                self.test_failed("Health Check", f"Status code: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.test_failed("Health Check", str(e))
            return False
            
    def test_ping(self) -> bool:
        """Test the ping method."""
        self.log("Testing ping method")
        result = self.make_jsonrpc_call("ping")
        
        if "result" in result and result["result"] == "pong":
            self.test_passed("Ping Method", result)
            return True
        else:
            self.test_failed("Ping Method", json.dumps(result))
            return False
            
    def test_get_server_info(self) -> bool:
        """Test the get_server_info method."""
        self.log("Testing get_server_info method")
        result = self.make_jsonrpc_call("get_server_info")
        
        if "result" in result and "version" in result["result"]:
            self.test_passed("Server Info Method", result["result"])
            return True
        else:
            self.test_failed("Server Info Method", json.dumps(result))
            return False
            
    def test_tools_method(self) -> bool:
        """Test both get_tools and list_tools methods."""
        self.log("Testing tools methods")
        
        # First try get_tools
        get_tools_result = self.make_jsonrpc_call("get_tools")
        if "result" in get_tools_result and "tools" in get_tools_result["result"]:
            tools = get_tools_result["result"]["tools"]
            self.test_passed("get_tools Method", {
                "count": len(tools),
                "tool_names": [t["name"] for t in tools[:3]] if tools else []
            })
            return True
            
        # If that fails, try list_tools
        list_tools_result = self.make_jsonrpc_call("list_tools")
        if "result" in list_tools_result and "tools" in list_tools_result["result"]:
            tools = list_tools_result["result"]["tools"]
            self.test_passed("list_tools Method", {
                "count": len(tools),
                "tool_names": [t["name"] for t in tools[:3]] if tools else []
            })
            return True
            
        # Both failed
        self.test_failed("Tools Methods", 
                        f"Both get_tools and list_tools failed. get_tools: {json.dumps(get_tools_result)}, " + 
                        f"list_tools: {json.dumps(list_tools_result)}")
        return False
        
    def run_tests(self) -> bool:
        """Run all tests."""
        self.log(f"Starting quick MCP server tests against {self.base_url}")
        
        # Health check first
        if not self.check_health():
            self.log("Health check failed. Server may not be running properly.")
            return False
            
        # Run all tests
        self.test_ping()
        self.test_get_server_info()
        self.test_tools_method()
        
        # Print summary
        self.log(f"\nTest Summary:")
        pass_count = sum(1 for t in self.test_results if t["passed"])
        fail_count = len(self.test_results) - pass_count
        self.log(f"{pass_count}/{len(self.test_results)} tests passed, {fail_count} failed")
        
        if self.all_tests_passed:
            self.log("✅ All tests passed! The MCP server is working correctly.")
        else:
            self.log("❌ Some tests failed. The MCP server may have issues.")
            
        # Show how to get more information
        self.log("\nNext steps:")
        self.log("- For detailed testing: python3 mcp_test_runner.py --port 9998 --verbose")
        self.log("- For comprehensive tests: bash run_final_mcp_solution.sh")
        self.log("- Check server logs: cat final_mcp_server.log")
        
        return self.all_tests_passed
        
def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="MCP Server Quick Test Helper")
    parser.add_argument("--url", type=str, default="http://localhost:9998", help="Base URL of the MCP server")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    
    tester = MCPQuickTester(base_url=args.url, verbose=args.verbose)
    success = tester.run_tests()
    
    return 0 if success else 1
    
if __name__ == "__main__":
    sys.exit(main())
