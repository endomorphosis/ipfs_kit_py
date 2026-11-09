#!/usr/bin/env python3
"""
Comprehensive MCP Tools Test

This script tests all registered tools in the MCP server by category.
It verifies that each tool is registered properly and can be executed.
"""

import os
import sys
import json
import logging
import requests
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-tools-test")

# Server configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9998
DEFAULT_TIMEOUT = 30  # seconds

class MCPToolsTest:
    """Test all MCP tools by category."""
    
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: int = DEFAULT_TIMEOUT):
        """Initialize the tester."""
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.jsonrpc_url = f"{self.base_url}/jsonrpc"
        self.health_url = f"{self.base_url}/health"
        self.timeout = timeout
        self.tools = {}
        self.tool_categories = set()
        self.test_results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "tool_results": {}
        }
    
    def check_server_health(self) -> bool:
        """Check if the server is healthy."""
        try:
            logger.info(f"Checking server health at {self.health_url}")
            response = requests.get(self.health_url, timeout=self.timeout)
            
            if response.status_code == 200:
                health_data = response.json()
                logger.info(f"Server is healthy: {json.dumps(health_data)}")
                return True
            else:
                logger.error(f"Server health check failed with status code {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error checking server health: {e}")
            return False
    
    def call_jsonrpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call the JSON-RPC endpoint."""
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                "id": int(time.time() * 1000)
            }
            
            logger.debug(f"Sending JSON-RPC request: {json.dumps(payload)}")
            response = requests.post(self.jsonrpc_url, json=payload, timeout=self.timeout)
            
            if response.status_code != 200:
                logger.error(f"JSON-RPC request failed with status code {response.status_code}")
                return {"error": f"HTTP error: {response.status_code}"}
            
            result = response.json()
            logger.debug(f"Received JSON-RPC response: {json.dumps(result)}")
            return result
        except Exception as e:
            logger.error(f"Error calling JSON-RPC: {e}")
            return {"error": str(e)}
    
    def get_all_tools(self) -> bool:
        """Get all registered tools from the server."""
        try:
            logger.info("Getting list of all tools")
            result = self.call_jsonrpc("get_tools")
            
            if "result" in result and "tools" in result["result"]:
                tools = result["result"]["tools"]
                logger.info(f"Found {len(tools)} tools")
                
                # Organize tools by category
                for tool in tools:
                    name = tool.get("name", "")
                    category = "unknown"
                    
                    if name.startswith("ipfs_"):
                        category = "ipfs"
                    elif name.startswith("vfs_"):
                        category = "vfs"
                    elif name.startswith("fs_journal"):
                        category = "fs_journal"
                    elif name.startswith("multi_backend") or name.startswith("mbfs_"):
                        category = "multi_backend"
                    
                    if category not in self.tools:
                        self.tools[category] = []
                    
                    self.tools[category].append(tool)
                    self.tool_categories.add(category)
                
                # Print summary of tools by category
                logger.info("Tools by category:")
                for category, category_tools in self.tools.items():
                    logger.info(f"  {category}: {len(category_tools)} tools")
                
                return True
            else:
                logger.error(f"Failed to get tools: {json.dumps(result)}")
                return False
        except Exception as e:
            logger.error(f"Error getting tools: {e}")
            return False
    
    def test_tool(self, tool: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Test a specific tool."""
        tool_name = tool.get("name", "")
        description = tool.get("description", "")
        logger.info(f"Testing tool: {tool_name} - {description}")
        
        try:
            # Prepare test parameters based on tool category
            test_params = self.get_test_params_for_tool(tool_name)
            
            # Call the tool with minimal parameters just to check if it responds
            result = self.call_jsonrpc("use_tool", {
                "tool_name": tool_name,
                "arguments": test_params,
                "context": {}
            })
            
            if "error" in result:
                logger.error(f"Error testing tool {tool_name}: {result['error']}")
                return False, result
            
            # Check for common error patterns in the result
            if "result" in result and isinstance(result["result"], dict) and "error" in result["result"]:
                error_msg = result["result"]["error"]
                logger.error(f"Tool {tool_name} returned error: {error_msg}")
                return False, result
            
            logger.info(f"Tool {tool_name} test passed")
            return True, result
        except Exception as e:
            logger.error(f"Exception testing tool {tool_name}: {e}")
            return False, {"error": str(e)}
    
    def get_test_params_for_tool(self, tool_name: str) -> Dict[str, Any]:
        """Get test parameters for a specific tool."""
        # Default minimal parameters
        params = {}
        
        # IPFS tools
        if tool_name == "ipfs_add":
            params = {"content": "Hello MCP Test World!"}
        elif tool_name == "ipfs_cat":
            params = {"cid": "QmPK1s3pNYLi9ERiq3BDxKa4XosgWwFRQUydHUtz4YgpqB"}
        elif tool_name == "ipfs_pin_add":
            params = {"cid": "QmPK1s3pNYLi9ERiq3BDxKa4XosgWwFRQUydHUtz4YgpqB"}
        elif tool_name == "ipfs_pin_rm":
            params = {"cid": "QmPK1s3pNYLi9ERiq3BDxKa4XosgWwFRQUydHUtz4YgpqB"}
        elif tool_name == "ipfs_pin_ls":
            params = {}
        elif tool_name == "ipfs_files_mkdir":
            params = {"path": "/mcp_test"}
        elif tool_name == "ipfs_files_write":
            params = {"path": "/mcp_test/test.txt", "content": "Hello MFS World!"}
        elif tool_name == "ipfs_files_read":
            params = {"path": "/mcp_test/test.txt"}
        elif tool_name == "ipfs_files_ls":
            params = {"path": "/"}
        elif tool_name == "ipfs_files_rm":
            params = {"path": "/mcp_test"}
            
        # VFS tools
        elif tool_name == "vfs_mkdir":
            params = {"path": "/tmp/mcp_test"}
        elif tool_name == "vfs_write":
            params = {"path": "/tmp/mcp_test/test.txt", "content": "Hello VFS World!"}
        elif tool_name == "vfs_read":
            params = {"path": "/tmp/mcp_test/test.txt"}
        elif tool_name == "vfs_ls":
            params = {"path": "/tmp"}
            
        # FS Journal tools
        elif tool_name == "fs_journal_get_history":
            params = {"path": "/tmp/mcp_test"}
        elif tool_name == "fs_journal_sync":
            params = {}
            
        # Multi-backend tools
        elif tool_name.startswith("multi_backend") or tool_name.startswith("mbfs_"):
            if "list" in tool_name:
                params = {}
            elif "add" in tool_name or "register" in tool_name:
                params = {"name": "test_backend", "type": "local", "mount_point": "/test"}
            else:
                params = {"backend": "local"}
                
        return params
    
    def run_tests(self) -> bool:
        """Run tests for all tools."""
        # Check server health
        if not self.check_server_health():
            logger.error("Server health check failed, aborting tests")
            return False
        
        # Get all tools
        if not self.get_all_tools():
            logger.error("Failed to get tools, aborting tests")
            return False
        
        # Test each tool by category
        for category, tools in self.tools.items():
            logger.info(f"\nTesting {len(tools)} tools in category: {category}")
            category_results = {
                "total": len(tools),
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "tool_results": {}
            }
            
            for tool in tools:
                tool_name = tool.get("name", "")
                self.test_results["total"] += 1
                
                # Skip certain tools that require complex setup
                if self.should_skip_tool(tool_name):
                    logger.info(f"Skipping test for {tool_name} (requires complex setup)")
                    self.test_results["skipped"] += 1
                    category_results["skipped"] += 1
                    category_results["tool_results"][tool_name] = {
                        "status": "skipped",
                        "reason": "Requires complex setup"
                    }
                    continue
                
                # Test the tool
                success, result = self.test_tool(tool)
                
                # Record the result
                if success:
                    self.test_results["passed"] += 1
                    category_results["passed"] += 1
                    category_results["tool_results"][tool_name] = {
                        "status": "passed",
                        "result": result
                    }
                else:
                    self.test_results["failed"] += 1
                    category_results["failed"] += 1
                    category_results["tool_results"][tool_name] = {
                        "status": "failed",
                        "error": result.get("error", "Unknown error"),
                        "result": result
                    }
            
            # Save category results
            self.test_results["tool_results"][category] = category_results
            
            # Print category summary
            logger.info(f"Category {category} summary:")
            logger.info(f"  Total: {category_results['total']}")
            logger.info(f"  Passed: {category_results['passed']}")
            logger.info(f"  Failed: {category_results['failed']}")
            logger.info(f"  Skipped: {category_results['skipped']}")
            
        # Print overall summary
        logger.info("\nOverall test summary:")
        logger.info(f"  Total tools: {self.test_results['total']}")
        logger.info(f"  Passed: {self.test_results['passed']}")
        logger.info(f"  Failed: {self.test_results['failed']}")
        logger.info(f"  Skipped: {self.test_results['skipped']}")
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = "data/test_results"
        os.makedirs(results_dir, exist_ok=True)
        results_file = os.path.join(results_dir, f"tool_test_results_{timestamp}.json")
        
        with open(results_file, "w") as f:
            json.dump(self.test_results, f, indent=2)
        
        logger.info(f"Test results saved to {results_file}")
        
        # Return success if all tests passed
        return self.test_results["failed"] == 0
    
    def should_skip_tool(self, tool_name: str) -> bool:
        """Check if a tool should be skipped in testing."""
        # Skip tools that require complex setup or external services
        skip_tools = [
            "ipfs_cluster_",  # Cluster tools need an actual IPFS cluster
            "ipfs_pubsub_",   # Pubsub tools require active subscriptions
            "ipfs_dht_",      # DHT tools need connected peers
            "lassie_",        # Lassie tools need complex setup
            "huggingface_",   # HuggingFace tools need model setup
            "ai_model_",      # AI model tools need model setup
            "credential_"     # Credential tools need credential setup
        ]
        
        for skip_prefix in skip_tools:
            if tool_name.startswith(skip_prefix):
                return True
                
        return False

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test all MCP tools")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Server host (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Server port (default: {DEFAULT_PORT})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger("mcp-tools-test").setLevel(logging.DEBUG)
    
    # Run tests
    tester = MCPToolsTest(host=args.host, port=args.port, timeout=args.timeout)
    success = tester.run_tests()
    
    # Exit with appropriate status code
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
