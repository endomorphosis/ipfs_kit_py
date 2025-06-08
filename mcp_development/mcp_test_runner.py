#!/usr/bin/env python3
"""
MCP Test Runner

This script runs automated tests against an MCP server to verify its functionality.
It tests the JSON-RPC endpoints and tool availability.

Usage:
  python3 mcp_test_runner.py --port 9997 [--host localhost] [--server-file final_mcp_server.py]
"""

import sys
import time
import json
import argparse
import logging
import subprocess
import os
import requests
from typing import Dict, Any, Optional, List, Tuple, Union, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mcp_test_runner.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mcp-test-runner")


class MCPTestRunner:
    """MCP Server Test Runner."""

    def __init__(self, host: str = "localhost", port: int = 9999, server_file: str = None):
        """Initialize the test runner.
        
        Args:
            host: The MCP server host
            port: The MCP server port
            server_file: Optional path to the MCP server file (for validation)
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.jsonrpc_url = f"{self.base_url}/jsonrpc"
        self.health_url = f"{self.base_url}/health"
        self.server_file = server_file
        self.test_results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "server_info": None,
            "health_check": None,
            "tests": []
        }
        self.test_count = 0
        self.pass_count = 0
        self.fail_count = 0

    def log_test(self, name: str, passed: bool, details: Any = None) -> None:
        """Log a test result.
        
        Args:
            name: The name of the test
            passed: Whether the test passed
            details: Optional details about the test
        """
        status = "PASS" if passed else "FAIL"
        self.test_count += 1
        if passed:
            self.pass_count += 1
            logger.info(f"✅ {status}: {name}")
        else:
            self.fail_count += 1
            logger.error(f"❌ {status}: {name}")
        
        if details:
            if isinstance(details, dict) or isinstance(details, list):
                details_str = json.dumps(details, indent=2)
                if not passed:
                    logger.error(f"Details: {details_str}")
            else:
                details_str = str(details)
                if not passed:
                    logger.error(f"Details: {details_str}")
        
        self.test_results["tests"].append({
            "name": name,
            "passed": passed,
            "details": details
        })

    def call_jsonrpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call a JSON-RPC method.
        
        Args:
            method: The method name
            params: Optional parameters
            
        Returns:
            The JSON-RPC response
        """
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
        except Exception as e:
            logger.error(f"Error calling {method}: {e}")
            return {"error": {"message": str(e)}}

    def check_server_health(self) -> bool:
        """Check the server's health endpoint.
        
        Returns:
            True if server is healthy, False otherwise
        """
        logger.info(f"Checking server health at {self.health_url}")
        
        try:
            response = requests.get(self.health_url, timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                self.test_results["health_check"] = health_data
                self.log_test("Health Check", True, health_data)
                return True
            else:
                self.log_test("Health Check", False, 
                             f"Status code: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Health Check", False, str(e))
            return False

    def test_basic_methods(self) -> bool:
        """Test basic JSON-RPC methods.
        
        Returns:
            True if all tests passed, False otherwise
        """
        # Test ping
        ping_result = self.call_jsonrpc("ping")
        ping_success = "result" in ping_result and ping_result["result"] == "pong"
        self.log_test("Ping Method", ping_success, ping_result)
        
        # Test server info
        server_info = self.call_jsonrpc("get_server_info")
        server_info_success = "result" in server_info and "version" in server_info["result"]
        if server_info_success:
            self.test_results["server_info"] = server_info["result"]
        self.log_test("Server Info Method", server_info_success, server_info)
        
        # Test tool listing - try get_tools first, fall back to list_tools if needed
        get_tools_result = self.call_jsonrpc("get_tools")
        tools_success = False
        
        # First try with get_tools
        if "result" in get_tools_result and "tools" in get_tools_result["result"]:
            tools_success = True
            tools_data = get_tools_result["result"]
            self.log_test("get_tools Method", tools_success, {
                "count": len(tools_data["tools"]),
                "sample": tools_data["tools"][:3] if tools_data["tools"] else []
            })
        else:
            # Fall back to list_tools
            list_tools_result = self.call_jsonrpc("list_tools")
            if "result" in list_tools_result and "tools" in list_tools_result["result"]:
                tools_success = True
                tools_data = list_tools_result["result"]
                self.log_test("list_tools Method", tools_success, {
                    "count": len(tools_data["tools"]),
                    "sample": tools_data["tools"][:3] if tools_data["tools"] else []
                })
            else:
                self.log_test("Tools Listing Methods", False, {
                    "get_tools_result": get_tools_result,
                    "list_tools_result": list_tools_result
                })
                
        return ping_success and server_info_success and tools_success

    def run_tests(self) -> bool:
        """Run all tests.
        
        Returns:
            True if all tests passed, False otherwise
        """
        logger.info(f"Starting MCP server tests against {self.base_url}")
        
        # Check server health
        if not self.check_server_health():
            logger.error("Server health check failed, aborting further tests")
            return False
        
        # Test basic methods
        basic_methods_result = self.test_basic_methods()
        
        # Save test results
        with open("mcp_test_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)
        
        # Print summary
        logger.info(f"Test Summary: {self.pass_count}/{self.test_count} tests passed, {self.fail_count} failed")
        return self.fail_count == 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="MCP Server Test Runner")
    parser.add_argument("--host", type=str, default="localhost", help="MCP server host")
    parser.add_argument("--port", type=int, default=9999, help="MCP server port")
    parser.add_argument("--server-file", type=str, help="Path to the MCP server file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    test_runner = MCPTestRunner(
        host=args.host,
        port=args.port,
        server_file=args.server_file
    )
    
    success = test_runner.run_tests()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())