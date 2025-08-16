#!/usr/bin/env python3
"""
Test Suite for Enhanced MCP Server Phase 1
==========================================

This script tests all Phase 1 tools in the enhanced MCP server,
covering core IPFS operations and system monitoring tools.

Tests both mock and real IPFS implementations where available.
"""

import asyncio
import json
import subprocess
import sys
import time
import tempfile
import os
from typing import Dict, Any, List

# Test configuration
TEST_TIMEOUT = 30
VERBOSE = True


class MCPTestClient:
    """Test client for MCP server communication."""
    
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.process = None
        self.initialized = False
    
    async def start_server(self):
        """Start the MCP server process."""
        print(f"Starting MCP server: {self.server_path}")
        
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, self.server_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Initialize the server
        await self.initialize()
        
    async def stop_server(self):
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            await self.process.wait()
    
    async def send_request(self, method: str, params: Dict[str, Any] = None, request_id: int = 1) -> Dict[str, Any]:
        """Send a request to the MCP server."""
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method
        }
        
        if params is not None:
            request["params"] = params
        
        request_json = json.dumps(request) + "\n"
        
        if VERBOSE:
            print(f"→ {request_json.strip()}")
        
        # Send request
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        response_json = response_line.decode().strip()
        
        if VERBOSE:
            print(f"← {response_json}")
        
        try:
            response = json.loads(response_json)
            return response
        except json.JSONDecodeError as e:
            print(f"Failed to parse response: {e}")
            print(f"Raw response: {response_json}")
            raise
    
    async def initialize(self):
        """Initialize the MCP server."""
        response = await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {}
        })
        
        if "error" in response:
            raise Exception(f"Initialization failed: {response['error']}")
        
        self.initialized = True
        print("✓ Server initialized successfully")
        
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        response = await self.send_request("tools/list")
        
        if "error" in response:
            raise Exception(f"Failed to list tools: {response['error']}")
        
        return response["result"]["tools"]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a specific tool."""
        params = {"name": tool_name}
        if arguments:
            params["arguments"] = arguments
        
        response = await self.send_request("tools/call", params)
        
        if "error" in response:
            return {"success": False, "error": response["error"]["message"]}
        
        # Parse the tool result from the response content
        content = response["result"]["content"][0]["text"]
        try:
            result = json.loads(content)
            return result
        except json.JSONDecodeError:
            return {"success": False, "error": f"Failed to parse tool result: {content}"}


class Phase1TestSuite:
    """Test suite for Phase 1 tools."""
    
    def __init__(self, client: MCPTestClient):
        self.client = client
        self.test_results = []
        self.failed_tests = []
    
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result."""
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"  {details}")
        
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        
        if not passed:
            self.failed_tests.append(test_name)
    
    async def test_tool_listing(self):
        """Test that all expected tools are listed."""
        print("\n=== Testing Tool Listing ===")
        
        try:
            tools = await self.client.list_tools()
            tool_names = [tool["name"] for tool in tools]
            
            expected_tools = [
                # Existing tools
                "ipfs_add", "ipfs_get", "ipfs_pin",
                # Phase 1 core tools
                "ipfs_cat", "ipfs_ls", "ipfs_stat", "ipfs_version", "ipfs_id",
                "ipfs_list_pins", "ipfs_unpin", "ipfs_block_get", "ipfs_block_stat",
                "ipfs_dag_get", "ipfs_object_stat",
                # System tools
                "filesystem_health", "system_health", "ipfs_cluster_status"
            ]
            
            missing_tools = [tool for tool in expected_tools if tool not in tool_names]
            extra_tools = [tool for tool in tool_names if tool not in expected_tools]
            
            if missing_tools:
                self.log_test("Tool Listing", False, f"Missing tools: {missing_tools}")
            elif extra_tools:
                self.log_test("Tool Listing", True, f"Extra tools found: {extra_tools}")
            else:
                self.log_test("Tool Listing", True, f"All {len(expected_tools)} tools found")
            
            print(f"Available tools: {', '.join(tool_names)}")
            
        except Exception as e:
            self.log_test("Tool Listing", False, f"Exception: {e}")
    
    async def test_ipfs_add(self):
        """Test IPFS add functionality."""
        print("\n=== Testing ipfs_add ===")
        
        test_content = "Hello, IPFS MCP Test!"
        
        try:
            result = await self.client.call_tool("ipfs_add", {"content": test_content})
            
            if result.get("success"):
                cid = result.get("cid")
                if cid and len(cid) > 10:  # Basic CID validation
                    self.log_test("ipfs_add", True, f"Generated CID: {cid}")
                    return cid  # Return CID for other tests
                else:
                    self.log_test("ipfs_add", False, "Invalid CID generated")
            else:
                self.log_test("ipfs_add", False, f"Error: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            self.log_test("ipfs_add", False, f"Exception: {e}")
        
        return None
    
    async def test_ipfs_cat(self, test_cid: str = None):
        """Test IPFS cat functionality."""
        print("\n=== Testing ipfs_cat ===")
        
        if not test_cid:
            test_cid = "bafkreie1234567890abcdef1234567890abcdef1234567890abcdef12"  # Use valid mock CID
        
        try:
            result = await self.client.call_tool("ipfs_cat", {"cid": test_cid})
            
            if result.get("success"):
                content = result.get("content")
                if content:
                    self.log_test("ipfs_cat", True, f"Retrieved content: {content[:50]}...")
                else:
                    self.log_test("ipfs_cat", False, "No content returned")
            else:
                self.log_test("ipfs_cat", False, f"Error: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            self.log_test("ipfs_cat", False, f"Exception: {e}")
    
    async def test_ipfs_ls(self, test_cid: str = None):
        """Test IPFS ls functionality."""
        print("\n=== Testing ipfs_ls ===")
        
        if not test_cid:
            test_cid = "bafkreie1234567890abcdef1234567890abcdef1234567890abcdef12"  # Use valid mock CID
        
        try:
            result = await self.client.call_tool("ipfs_ls", {"cid": test_cid})
            
            if result.get("success"):
                contents = result.get("contents")
                self.log_test("ipfs_ls", True, f"Listed contents for {test_cid}")
            else:
                self.log_test("ipfs_ls", False, f"Error: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            self.log_test("ipfs_ls", False, f"Exception: {e}")
    
    async def test_ipfs_stat(self, test_cid: str = None):
        """Test IPFS stat functionality."""
        print("\n=== Testing ipfs_stat ===")
        
        if not test_cid:
            test_cid = "bafkreie1234567890abcdef1234567890abcdef1234567890abcdef12"
        
        try:
            result = await self.client.call_tool("ipfs_stat", {"cid": test_cid})
            
            if result.get("success"):
                stats = result.get("stats")
                self.log_test("ipfs_stat", True, f"Got stats for {test_cid}")
            else:
                self.log_test("ipfs_stat", False, f"Error: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            self.log_test("ipfs_stat", False, f"Exception: {e}")
    
    async def test_ipfs_version(self):
        """Test IPFS version functionality."""
        print("\n=== Testing ipfs_version ===")
        
        try:
            result = await self.client.call_tool("ipfs_version")
            
            if result.get("success"):
                version_info = result.get("version_info")
                self.log_test("ipfs_version", True, f"Version info retrieved")
            else:
                self.log_test("ipfs_version", False, f"Error: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            self.log_test("ipfs_version", False, f"Exception: {e}")
    
    async def test_ipfs_id(self):
        """Test IPFS id functionality."""
        print("\n=== Testing ipfs_id ===")
        
        try:
            result = await self.client.call_tool("ipfs_id")
            
            if result.get("success"):
                identity = result.get("identity")
                self.log_test("ipfs_id", True, f"Identity retrieved")
            else:
                self.log_test("ipfs_id", False, f"Error: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            self.log_test("ipfs_id", False, f"Exception: {e}")
    
    async def test_ipfs_pin_operations(self, test_cid: str = None):
        """Test IPFS pin/unpin/list operations."""
        print("\n=== Testing Pin Operations ===")
        
        if not test_cid:
            test_cid = "bafkreie1234567890abcdef1234567890abcdef1234567890abcdef12"
        
        # Test pin add
        try:
            result = await self.client.call_tool("ipfs_pin", {"cid": test_cid})
            
            if result.get("success"):
                self.log_test("ipfs_pin", True, f"Pinned {test_cid}")
            else:
                self.log_test("ipfs_pin", False, f"Pin error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.log_test("ipfs_pin", False, f"Pin exception: {e}")
        
        # Test pin list
        try:
            result = await self.client.call_tool("ipfs_list_pins")
            
            if result.get("success"):
                pins = result.get("pins")
                self.log_test("ipfs_list_pins", True, f"Listed pins")
            else:
                self.log_test("ipfs_list_pins", False, f"List pins error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.log_test("ipfs_list_pins", False, f"List pins exception: {e}")
        
        # Test unpin
        try:
            result = await self.client.call_tool("ipfs_unpin", {"cid": test_cid})
            
            if result.get("success"):
                self.log_test("ipfs_unpin", True, f"Unpinned {test_cid}")
            else:
                self.log_test("ipfs_unpin", False, f"Unpin error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.log_test("ipfs_unpin", False, f"Unpin exception: {e}")
    
    async def test_ipfs_block_operations(self, test_cid: str = None):
        """Test IPFS block operations."""
        print("\n=== Testing Block Operations ===")
        
        if not test_cid:
            test_cid = "bafkreie1234567890abcdef1234567890abcdef1234567890abcdef12"
        
        # Test block get
        try:
            result = await self.client.call_tool("ipfs_block_get", {"cid": test_cid})
            
            if result.get("success"):
                self.log_test("ipfs_block_get", True, f"Got block for {test_cid}")
            else:
                self.log_test("ipfs_block_get", False, f"Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.log_test("ipfs_block_get", False, f"Exception: {e}")
        
        # Test block stat
        try:
            result = await self.client.call_tool("ipfs_block_stat", {"cid": test_cid})
            
            if result.get("success"):
                self.log_test("ipfs_block_stat", True, f"Got block stats for {test_cid}")
            else:
                self.log_test("ipfs_block_stat", False, f"Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.log_test("ipfs_block_stat", False, f"Exception: {e}")
    
    async def test_ipfs_dag_operations(self, test_cid: str = None):
        """Test IPFS DAG operations."""
        print("\n=== Testing DAG Operations ===")
        
        if not test_cid:
            test_cid = "bafkreie1234567890abcdef1234567890abcdef1234567890abcdef12"
        
        try:
            result = await self.client.call_tool("ipfs_dag_get", {"cid": test_cid})
            
            if result.get("success"):
                self.log_test("ipfs_dag_get", True, f"Got DAG object for {test_cid}")
            else:
                self.log_test("ipfs_dag_get", False, f"Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.log_test("ipfs_dag_get", False, f"Exception: {e}")
    
    async def test_ipfs_object_operations(self, test_cid: str = None):
        """Test IPFS object operations."""
        print("\n=== Testing Object Operations ===")
        
        if not test_cid:
            test_cid = "bafkreie1234567890abcdef1234567890abcdef1234567890abcdef12"
        
        try:
            result = await self.client.call_tool("ipfs_object_stat", {"cid": test_cid})
            
            if result.get("success"):
                self.log_test("ipfs_object_stat", True, f"Got object stats for {test_cid}")
            else:
                self.log_test("ipfs_object_stat", False, f"Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.log_test("ipfs_object_stat", False, f"Exception: {e}")
    
    async def test_system_tools(self):
        """Test system monitoring tools."""
        print("\n=== Testing System Tools ===")
        
        # Test filesystem health
        try:
            result = await self.client.call_tool("filesystem_health", {"path": "/tmp"})
            
            if result.get("success"):
                health_status = result.get("health_status")
                self.log_test("filesystem_health", True, f"Health status: {health_status}")
            else:
                self.log_test("filesystem_health", False, f"Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.log_test("filesystem_health", False, f"Exception: {e}")
        
        # Test system health
        try:
            result = await self.client.call_tool("system_health")
            
            if result.get("success"):
                self.log_test("system_health", True, "System health retrieved")
            else:
                self.log_test("system_health", False, f"Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.log_test("system_health", False, f"Exception: {e}")
        
        # Test cluster status
        try:
            result = await self.client.call_tool("ipfs_cluster_status")
            
            if result.get("success"):
                self.log_test("ipfs_cluster_status", True, "Cluster status retrieved")
            else:
                self.log_test("ipfs_cluster_status", False, f"Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            self.log_test("ipfs_cluster_status", False, f"Exception: {e}")
    
    async def run_all_tests(self):
        """Run all test cases."""
        print("🚀 Starting Phase 1 MCP Server Tests")
        print("=" * 50)
        
        # Test tool listing first
        await self.test_tool_listing()
        
        # Test IPFS add and get CID for other tests
        test_cid = await self.test_ipfs_add()
        
        # Test core IPFS operations
        await self.test_ipfs_cat(test_cid)
        await self.test_ipfs_ls(test_cid)
        await self.test_ipfs_stat(test_cid)
        await self.test_ipfs_version()
        await self.test_ipfs_id()
        
        # Test pin operations
        await self.test_ipfs_pin_operations(test_cid)
        
        # Test block operations
        await self.test_ipfs_block_operations(test_cid)
        
        # Test DAG operations
        await self.test_ipfs_dag_operations(test_cid)
        
        # Test object operations
        await self.test_ipfs_object_operations(test_cid)
        
        # Test system tools
        await self.test_system_tools()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 50)
        print("🏁 Test Summary")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if self.failed_tests:
            print(f"\nFailed tests:")
            for test_name in self.failed_tests:
                print(f"  ✗ {test_name}")
        else:
            print("\n🎉 All tests passed!")


async def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print("Usage: python test_enhanced_mcp_phase1.py <path_to_enhanced_server>")
        print("Example: python test_enhanced_mcp_phase1.py ./enhanced_mcp_server_phase1.py")
        sys.exit(1)
    
    server_path = sys.argv[1]
    
    if not os.path.exists(server_path):
        print(f"Error: Server file not found: {server_path}")
        sys.exit(1)
    
    print(f"Testing Enhanced MCP Server Phase 1")
    print(f"Server path: {server_path}")
    print(f"Test timeout: {TEST_TIMEOUT}s")
    print()
    
    client = MCPTestClient(server_path)
    test_suite = Phase1TestSuite(client)
    
    try:
        # Start server
        await client.start_server()
        
        # Run tests
        await asyncio.wait_for(test_suite.run_all_tests(), timeout=TEST_TIMEOUT)
        
    except asyncio.TimeoutError:
        print(f"\n⚠️  Tests timed out after {TEST_TIMEOUT} seconds")
        
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up
        await client.stop_server()
    
    # Exit with appropriate code
    if test_suite.failed_tests:
        print(f"\n❌ {len(test_suite.failed_tests)} test(s) failed")
        sys.exit(1)
    else:
        print(f"\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
