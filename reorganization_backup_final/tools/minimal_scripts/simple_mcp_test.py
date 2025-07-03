#!/usr/bin/env python3
"""
Simple MCP Test Runner

This version focuses only on testing basic functionality without complex reporting.
"""

import argparse
import json
import logging
import requests
import sys
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('simple_mcp_test.log', mode='w')
    ]
)
logger = logging.getLogger("simple-mcp-test")

class SimpleMCPTester:
    """A simplified MCP test runner that tolerates missing methods"""
    
    def __init__(self, port=9997):
        self.port = port
        self.base_url = f"http://localhost:{port}"
        self.jsonrpc_url = f"{self.base_url}/jsonrpc"
        self.health_url = f"{self.base_url}/health"
        self.results = {"passed": 0, "failed": 0, "skipped": 0}
        
    def call_jsonrpc(self, method, params=None):
        """Call JSON-RPC method with proper error handling"""
        if params is None:
            params = {}
            
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000)
        }
        
        try:
            response = requests.post(self.jsonrpc_url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error calling {method}: {e}")
            return {"error": {"message": str(e)}}
    
    def test_health(self):
        """Test the health endpoint"""
        logger.info("Testing health endpoint...")
        try:
            response = requests.get(self.health_url)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Health endpoint OK: {data}")
                self.results["passed"] += 1
                return True
            else:
                logger.error(f"Health endpoint failed with status {response.status_code}")
                self.results["failed"] += 1
                return False
        except Exception as e:
            logger.error(f"Error testing health endpoint: {e}")
            self.results["failed"] += 1
            return False
    
    def test_ping(self):
        """Test the ping method"""
        logger.info("Testing ping method...")
        result = self.call_jsonrpc("ping")
        if "result" in result and result["result"] == "pong":
            logger.info("Ping test successful")
            self.results["passed"] += 1
            return True
        else:
            logger.error(f"Ping test failed: {result}")
            self.results["failed"] += 1
            return False
    
    def test_list_tools(self):
        """Test the list_tools method"""
        logger.info("Testing list_tools method...")
        result = self.call_jsonrpc("list_tools")
        if "result" in result and "tools" in result["result"]:
            tools = result["result"]["tools"]
            logger.info(f"Found {len(tools)} tools")
            self.results["passed"] += 1
            return tools
        else:
            logger.error(f"list_tools test failed: {result}")
            self.results["failed"] += 1
            return []
    
    def test_ipfs_methods(self, tools):
        """Test IPFS methods if available"""
        logger.info("Testing IPFS methods...")
        ipfs_tools = [t for t in tools if isinstance(t, dict) and t.get("name", "").startswith("ipfs_")]
        logger.info(f"Found {len(ipfs_tools)} IPFS tools")
        
        # Test ipfs_version if available
        if any(t.get("name") == "ipfs_version" for t in ipfs_tools):
            logger.info("Testing ipfs_version...")
            result = self.call_jsonrpc("ipfs_version")
            if "result" in result:
                logger.info(f"ipfs_version successful: {result['result']}")
                self.results["passed"] += 1
            elif "error" in result and "Method not found" in result["error"].get("message", ""):
                logger.info("ipfs_version method not found (skipped)")
                self.results["skipped"] += 1
            else:
                logger.error(f"ipfs_version test failed: {result}")
                self.results["failed"] += 1
        
        # Test ipfs_add/cat if available
        if any(t.get("name") == "ipfs_add" for t in ipfs_tools):
            test_content = "Hello from Simple MCP Tester!"
            logger.info("Testing ipfs_add...")
            add_result = self.call_jsonrpc("ipfs_add", {"content": test_content})
            
            if "error" in add_result and "Method not found" in add_result["error"].get("message", ""):
                logger.info("ipfs_add method not found (skipped)")
                self.results["skipped"] += 1
                return
                
            if "result" in add_result:
                cid = None
                if isinstance(add_result["result"], dict):
                    cid = add_result["result"].get("Hash") or add_result["result"].get("cid")
                elif isinstance(add_result["result"], str):
                    cid = add_result["result"]
                    
                if cid:
                    logger.info(f"ipfs_add successful, got CID: {cid}")
                    self.results["passed"] += 1
                    
                    # Test ipfs_cat if add was successful
                    if any(t.get("name") == "ipfs_cat" for t in ipfs_tools):
                        logger.info("Testing ipfs_cat...")
                        cat_result = self.call_jsonrpc("ipfs_cat", {"cid": cid})
                        if "error" in cat_result and "Method not found" in cat_result["error"].get("message", ""):
                            logger.info("ipfs_cat method not found (skipped)")
                            self.results["skipped"] += 1
                        elif "result" in cat_result:
                            content = cat_result["result"]
                            if isinstance(content, dict) and "content" in content:
                                content = content["content"]
                            
                            if content == test_content:
                                logger.info("ipfs_cat successful, retrieved correct content")
                                self.results["passed"] += 1
                            else:
                                logger.error(f"ipfs_cat retrieved incorrect content: {content}")
                                self.results["failed"] += 1
                        else:
                            logger.error(f"ipfs_cat test failed: {cat_result}")
                            self.results["failed"] += 1
                else:
                    logger.error(f"ipfs_add did not return a valid CID: {add_result}")
                    self.results["failed"] += 1
            else:
                logger.error(f"ipfs_add test failed: {add_result}")
                self.results["failed"] += 1
    
    def test_vfs_methods(self, tools):
        """Test VFS methods if available"""
        logger.info("Testing VFS methods...")
        vfs_tools = [t for t in tools if isinstance(t, dict) and t.get("name", "").startswith("vfs_")]
        logger.info(f"Found {len(vfs_tools)} VFS tools")
        
        # Only run VFS tests if we have vfs_mkdir
        if not any(t.get("name") == "vfs_mkdir" for t in vfs_tools):
            logger.info("vfs_mkdir not available, skipping VFS tests")
            return
            
        test_dir = f"/test-{int(time.time())}"
        test_file = f"{test_dir}/test.txt"
        test_content = "Hello VFS from Simple MCP Tester!"
        
        # Test vfs_mkdir
        logger.info(f"Testing vfs_mkdir: {test_dir}")
        mkdir_result = self.call_jsonrpc("vfs_mkdir", {"path": test_dir})
        if "error" in mkdir_result and "Method not found" in mkdir_result["error"].get("message", ""):
            logger.info("vfs_mkdir method not found (skipped)")
            self.results["skipped"] += 1
            return
            
        if "result" in mkdir_result:
            logger.info(f"vfs_mkdir successful: {test_dir}")
            self.results["passed"] += 1
            
            # Test vfs_write if mkdir was successful
            if any(t.get("name") == "vfs_write" for t in vfs_tools):
                logger.info(f"Testing vfs_write: {test_file}")
                write_result = self.call_jsonrpc("vfs_write", {"path": test_file, "content": test_content})
                
                if "error" in write_result and "Method not found" in write_result["error"].get("message", ""):
                    logger.info("vfs_write method not found (skipped)")
                    self.results["skipped"] += 1
                elif "result" in write_result:
                    logger.info(f"vfs_write successful: {test_file}")
                    self.results["passed"] += 1
                    
                    # Test vfs_read if write was successful
                    if any(t.get("name") == "vfs_read" for t in vfs_tools):
                        logger.info(f"Testing vfs_read: {test_file}")
                        read_result = self.call_jsonrpc("vfs_read", {"path": test_file})
                        
                        if "error" in read_result and "Method not found" in read_result["error"].get("message", ""):
                            logger.info("vfs_read method not found (skipped)")
                            self.results["skipped"] += 1
                        elif "result" in read_result:
                            content = read_result["result"]
                            if isinstance(content, dict) and "content" in content:
                                content = content["content"]
                                
                            if content == test_content:
                                logger.info("vfs_read successful, retrieved correct content")
                                self.results["passed"] += 1
                            else:
                                logger.error(f"vfs_read retrieved incorrect content: {content}")
                                self.results["failed"] += 1
                        else:
                            logger.error(f"vfs_read test failed: {read_result}")
                            self.results["failed"] += 1
                else:
                    logger.error(f"vfs_write test failed: {write_result}")
                    self.results["failed"] += 1
                    
            # Clean up - test vfs_rm
            if any(t.get("name") == "vfs_rm" for t in vfs_tools):
                logger.info(f"Testing vfs_rm: {test_file}")
                rm_result = self.call_jsonrpc("vfs_rm", {"path": test_file})
                
                if "error" in rm_result and "Method not found" in rm_result["error"].get("message", ""):
                    logger.info("vfs_rm method not found (skipped)")
                    self.results["skipped"] += 1
                elif "result" in rm_result:
                    logger.info(f"vfs_rm successful: {test_file}")
                    self.results["passed"] += 1
                else:
                    logger.error(f"vfs_rm test failed: {rm_result}")
                    self.results["failed"] += 1
            
            # Clean up - test vfs_rmdir
            if any(t.get("name") == "vfs_rmdir" for t in vfs_tools):
                logger.info(f"Testing vfs_rmdir: {test_dir}")
                rmdir_result = self.call_jsonrpc("vfs_rmdir", {"path": test_dir})
                
                if "error" in rmdir_result and "Method not found" in rmdir_result["error"].get("message", ""):
                    logger.info("vfs_rmdir method not found (skipped)")
                    self.results["skipped"] += 1
                elif "result" in rmdir_result:
                    logger.info(f"vfs_rmdir successful: {test_dir}")
                    self.results["passed"] += 1
                else:
                    logger.error(f"vfs_rmdir test failed: {rmdir_result}")
                    self.results["failed"] += 1
        else:
            logger.error(f"vfs_mkdir test failed: {mkdir_result}")
            self.results["failed"] += 1
    
    def run_tests(self):
        """Run all tests"""
        logger.info("Starting simple MCP tests...")
        
        if not self.test_health():
            logger.error("Health endpoint test failed, aborting")
            return False
            
        if not self.test_ping():
            logger.error("Ping test failed, aborting")
            return False
            
        tools = self.test_list_tools()
        if tools:
            self.test_ipfs_methods(tools)
            self.test_vfs_methods(tools)
            
        # Print results
        logger.info("Tests completed")
        logger.info(f"Passed: {self.results['passed']}")
        logger.info(f"Failed: {self.results['failed']}")
        logger.info(f"Skipped: {self.results['skipped']}")
        
        # Return True if all tests passed or were skipped
        return self.results["failed"] == 0

def main():
    parser = argparse.ArgumentParser(description="Simple MCP Tester")
    parser.add_argument("--port", type=int, default=9997, help="Port the MCP server is running on")
    args = parser.parse_args()
    
    tester = SimpleMCPTester(port=args.port)
    success = tester.run_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
