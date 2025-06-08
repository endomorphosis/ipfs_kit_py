#!/usr/bin/env python3
"""
Comprehensive MCP Test

This script performs comprehensive tests on an MCP server to verify:
1. Server connectivity and health
2. JSON-RPC endpoint functionality
3. Available tools and their schemas
4. IPFS Kit integration
5. Virtual File System (VFS) integration

Usage:
  python3 comprehensive_mcp_test.py --url http://localhost:9996 [--output results.json] [--verbose]
"""

import argparse
import json
import os
import sys
import time
import requests
import datetime
import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("comprehensive_mcp_test")

class MCPComprehensiveTest:
    """Comprehensive test for MCP servers."""

    def __init__(self, url: str, output_file: str = None, verbose: bool = False):
        """Initialize the test.
        
        Args:
            url: The base URL of the MCP server
            output_file: Path to output file for test results
            verbose: Whether to print verbose output
        """
        self.base_url = url
        self.rpc_url = urljoin(url, "/jsonrpc")
        self.health_url = urljoin(url, "/health")
        self.sse_url = urljoin(url, "/sse")
        self.output_file = output_file
        self.verbose = verbose
        self.tools_schema = {}
        self.available_tools = []
        self.results = {
            "timestamp": datetime.datetime.now().isoformat(),
            "server_url": url,
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "success_rate": 0.0
            },
            "tool_categories": {},
            "tests": []
        }
        
        # Set up detailed logging if verbose
        if verbose:
            logger.setLevel(logging.DEBUG)
            logger.debug(f"Verbose logging enabled")

    def log(self, message: str, level: str = "info"):
        """Log a message.
        
        Args:
            message: The message to log
            level: The log level
        """
        if level == "debug" and self.verbose:
            logger.debug(message)
        elif level == "info":
            logger.info(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        elif level == "success" and self.verbose:
            logger.info(f"SUCCESS: {message}")

    def check_server_health(self) -> bool:
        """Check if the server is healthy.
        
        Returns:
            True if the server is healthy, False otherwise.
        """
        self.log(f"Checking server health at {self.health_url}...")
        
        try:
            response = requests.get(self.health_url, timeout=5)
            if response.status_code == 200:
                self.log(f"Server is healthy: {response.text}", "success")
                return True
            else:
                self.log(f"Server returned non-200 status code: {response.status_code}", "error")
                return False
        except Exception as e:
            self.log(f"Error checking server health: {e}", "error")
            return False

    def test_jsonrpc_connectivity(self) -> bool:
        """Test connectivity to the JSON-RPC endpoint.
        
        Returns:
            True if the JSON-RPC endpoint is accessible, False otherwise.
        """
        self.log(f"Testing JSON-RPC connectivity at {self.rpc_url}...")
        
        try:
            # Test with system.listMethods
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "system.listMethods"
            }
            response = requests.post(self.rpc_url, json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    methods = data["result"]
                    self.log(f"JSON-RPC endpoint is accessible, found {len(methods)} methods", "success")
                    self.available_tools = methods
                    return True
                else:
                    self.log(f"JSON-RPC endpoint returned error: {data.get('error', 'Unknown error')}", "error")
                    return False
            else:
                self.log(f"JSON-RPC endpoint returned non-200 status code: {response.status_code}", "error")
                return False
        except Exception as e:
            self.log(f"Error testing JSON-RPC connectivity: {e}", "error")
            return False

    def get_tools_schema(self) -> bool:
        """Get the schema for all available tools.
        
        Returns:
            True if successful, False otherwise.
        """
        self.log("Getting tools schema...")
        
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "get_tools_schema"
            }
            response = requests.post(self.rpc_url, json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    self.tools_schema = data["result"]
                    self.log(f"Got schema for {len(self.tools_schema)} tools", "success")
                    
                    # Categorize tools
                    categories = {}
                    for tool_name in self.tools_schema:
                        category = tool_name.split('.')[0] if '.' in tool_name else "other"
                        if category not in categories:
                            categories[category] = []
                        categories[category].append(tool_name)
                    
                    self.results["tool_categories"] = categories
                    
                    # Print tool count by category
                    self.log("Tool count by category:")
                    for category, tools in categories.items():
                        self.log(f"  {category}: {len(tools)}")
                    
                    return True
                else:
                    self.log(f"Error getting tools schema: {data.get('error', 'Unknown error')}", "error")
                    return False
            else:
                self.log(f"Error getting tools schema: HTTP {response.status_code}", "error")
                return False
        except Exception as e:
            self.log(f"Error getting tools schema: {e}", "error")
            return False

    def test_tool(self, tool_name: str) -> Tuple[bool, Any, Optional[str]]:
        """Test a specific tool.
        
        Args:
            tool_name: The name of the tool to test
            
        Returns:
            Tuple of (success, result, error_message)
        """
        self.log(f"Testing tool: {tool_name}", "debug")
        
        # Skip certain tools that require complex parameters
        if any(skip in tool_name for skip in ["add", "cat", "write", "read"]):
            self.log(f"Skipping complex tool: {tool_name}", "debug")
            return (False, None, "Skipped (requires complex parameters)")
        
        try:
            # Simple test with empty parameters
            payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": tool_name,
                "params": {}
            }
            
            # For specific tools, provide test parameters
            if tool_name == "ipfs.version":
                payload["params"] = {}
            elif tool_name == "vfs.ls":
                payload["params"] = {"path": "/"}
            elif tool_name == "vfs.mkdir":
                payload["params"] = {"path": "/test_" + str(time.time()).replace(".", "")}
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return (True, data["result"], None)
                else:
                    return (False, None, f"Error: {data.get('error', {}).get('message', 'Unknown error')}")
            else:
                return (False, None, f"HTTP Error: {response.status_code}")
        except Exception as e:
            return (False, None, f"Exception: {str(e)}")

    def test_all_tools(self) -> None:
        """Test all available tools."""
        if not self.available_tools:
            self.log("No tools available to test", "error")
            return
        
        self.log(f"Testing {len(self.available_tools)} tools...")
        
        total = len(self.available_tools)
        passed = 0
        failed = 0
        skipped = 0
        
        for tool_name in self.available_tools:
            success, result, error = self.test_tool(tool_name)
            
            test_result = {
                "name": tool_name,
                "success": success,
                "skipped": error == "Skipped (requires complex parameters)"
            }
            
            if error:
                test_result["error"] = error
            
            if success:
                passed += 1
                self.log(f"✅ {tool_name}: SUCCESS", "success")
            elif error == "Skipped (requires complex parameters)":
                skipped += 1
                self.log(f"⏭️ {tool_name}: SKIPPED", "debug")
            else:
                failed += 1
                self.log(f"❌ {tool_name}: FAILED - {error}", "error")
            
            self.results["tests"].append(test_result)
        
        # Update summary
        success_rate = (passed / (total - skipped)) * 100 if (total - skipped) > 0 else 0
        self.results["summary"] = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": round(success_rate, 2)
        }
        
        self.log(f"Test summary: {passed} passed, {failed} failed, {skipped} skipped, {success_rate:.2f}% success rate")

    def save_results(self) -> None:
        """Save test results to a file."""
        if not self.output_file:
            self.log("No output file specified, not saving results", "debug")
            return
        
        self.log(f"Saving test results to {self.output_file}...")
        
        try:
            with open(self.output_file, "w") as f:
                json.dump(self.results, f, indent=2)
            self.log(f"Results saved to {self.output_file}", "success")
        except Exception as e:
            self.log(f"Error saving results: {e}", "error")

    def run_all_tests(self) -> bool:
        """Run all tests.
        
        Returns:
            True if all tests passed, False otherwise.
        """
        self.log("Starting comprehensive MCP server tests...")
        
        # Check server health
        if not self.check_server_health():
            self.log("Server health check failed, aborting tests", "error")
            return False
        
        # Test JSON-RPC connectivity
        if not self.test_jsonrpc_connectivity():
            self.log("JSON-RPC connectivity test failed, aborting tests", "error")
            return False
        
        # Get tools schema
        if not self.get_tools_schema():
            self.log("Failed to get tools schema, continuing with limited tests", "warning")
        
        # Test all available tools
        self.test_all_tools()
        
        # Save results
        self.save_results()
        
        # Check if tests were successful
        success = self.results["summary"]["failed"] == 0
        
        if success:
            self.log("All tests passed successfully!", "success")
        else:
            self.log(f"{self.results['summary']['failed']} tests failed", "error")
        
        return success

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Comprehensive MCP Server Test")
    parser.add_argument("--url", default="http://localhost:9996", help="URL of the MCP server")
    parser.add_argument("--output", help="Output file for test results (JSON)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    
    tester = MCPComprehensiveTest(args.url, args.output, args.verbose)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
