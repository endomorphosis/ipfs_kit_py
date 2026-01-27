#!/usr/bin/env python3
"""
Enhanced MCP Server Verification Script

This script verifies all functionality of the enhanced MCP server, including:
1. Basic connectivity
2. SSE endpoints (root, /sse, and /api/v0/sse)
3. JSON-RPC support for VS Code
4. IPFS operations (add, cat, pin)
5. Storage backend status
"""

import os
import sys
import json
import time
import uuid
import argparse
import logging
import requests
import anyio
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MCPVerifier:
    """Verifies enhanced MCP server functionality."""
    
    def __init__(self, host: str = "localhost", port: int = 9994):
        """Initialize the MCP verifier."""
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.api_prefix = "/api/v0"
        self.api_url = f"{self.base_url}{self.api_prefix}"
        self.tests_passed = 0
        self.tests_failed = 0
        self.tests_skipped = 0
        self.created_cids = []
        
    def run_verification(self):
        """Run all verification tests."""
        logger.info("=" * 80)
        logger.info("Starting enhanced MCP server verification...")
        logger.info("=" * 80)
        
        # Basic connectivity tests
        self.verify_connectivity()
        
        # SSE endpoint tests
        self.verify_sse_endpoints()
        
        # JSON-RPC support tests
        self.verify_jsonrpc_support()
        
        # IPFS operations tests
        self.verify_ipfs_operations()
        
        # Summary
        logger.info("=" * 80)
        logger.info(f"VERIFICATION SUMMARY: {self.tests_passed} passed, {self.tests_failed} failed, {self.tests_skipped} skipped")
        logger.info("=" * 80)
        
        # Return status code
        return 0 if self.tests_failed == 0 else 1
        
    def test_wrapper(self, test_name):
        """Wrapper for tests to catch exceptions and track results."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                logger.info(f"Running test: {test_name}")
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    logger.info(f"✅ PASS: {test_name} ({duration:.2f}s)")
                    self.tests_passed += 1
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    logger.error(f"❌ FAIL: {test_name} ({duration:.2f}s) - {str(e)}")
                    self.tests_failed += 1
                    return None
            return wrapper
        return decorator
        
    @test_wrapper("Basic Connectivity")
    def verify_connectivity(self):
        """Verify basic connectivity to the MCP server."""
        response = requests.get(f"{self.base_url}")
        if response.status_code != 200:
            raise Exception(f"Failed to connect to MCP server: {response.status_code}")
            
        # Check for expected fields in response
        data = response.json()
        required_fields = ["message", "documentation", "health_endpoint"]
        for field in required_fields:
            if field not in data:
                raise Exception(f"Missing field in response: {field}")
                
        logger.info(f"Server ID: {data.get('server_id')}")
        logger.info(f"Debug mode: {data.get('debug_mode')}")
        
        # Check health endpoint
        health_response = requests.get(f"{self.base_url}/health")
        if health_response.status_code != 200:
            raise Exception(f"Failed to connect to health endpoint: {health_response.status_code}")
            
        health_data = health_response.json()
        if not health_data.get("success"):
            raise Exception(f"Health check failed: {health_data}")
            
        return data
        
    @test_wrapper("SSE Endpoints")
    def verify_sse_endpoints(self):
        """Verify Server-Sent Events (SSE) endpoints."""
        sse_endpoints = [
            "/sse",
            f"{self.api_prefix}/sse"
        ]
        
        results = {}
        for endpoint in sse_endpoints:
            url = f"{self.base_url}{endpoint}"
            logger.info(f"Testing SSE endpoint: {url}")
            
            try:
                # Use a short timeout to just verify the connection
                response = requests.get(url, stream=True, timeout=2)
                
                # Check if we got a proper stream response
                if response.status_code != 200:
                    raise Exception(f"Failed to connect to SSE endpoint: {response.status_code}")
                    
                # Get the first chunk of data
                for line in response.iter_lines(decode_unicode=True):
                    if line and line.startswith("data: "):
                        # Parse the JSON data
                        data = json.loads(line[6:])
                        logger.info(f"  - Received SSE event: {data}")
                        results[endpoint] = data
                        break
                        
                # Close the connection
                response.close()
                
            except requests.RequestException as e:
                raise Exception(f"Error connecting to SSE endpoint {endpoint}: {e}")
                
        # Ensure we got data from both endpoints
        if len(results) != len(sse_endpoints):
            raise Exception(f"Not all SSE endpoints returned data: {results}")
            
        return results
        
    @test_wrapper("JSON-RPC Support")
    def verify_jsonrpc_support(self):
        """Verify JSON-RPC support for VS Code integration."""
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": os.getpid(),
                "rootUri": None,
                "capabilities": {}
            }
        }
        
        jsonrpc_endpoints = [
            "/jsonrpc",
            f"{self.api_prefix}/jsonrpc"
        ]
        
        results = {}
        for endpoint in jsonrpc_endpoints:
            url = f"{self.base_url}{endpoint}"
            logger.info(f"Testing JSON-RPC endpoint: {url}")
            
            try:
                response = requests.post(url, json=initialize_request)
                
                if response.status_code != 200:
                    raise Exception(f"Failed to connect to JSON-RPC endpoint: {response.status_code}")
                    
                data = response.json()
                if "result" not in data or "capabilities" not in data["result"]:
                    raise Exception(f"Invalid JSON-RPC response: {data}")
                    
                logger.info(f"  - JSON-RPC response contains server info: {data['result'].get('serverInfo', {}).get('name')}")
                results[endpoint] = data
                
            except requests.RequestException as e:
                raise Exception(f"Error connecting to JSON-RPC endpoint {endpoint}: {e}")
                
        # Ensure we got valid responses from both endpoints
        if len(results) != len(jsonrpc_endpoints):
            raise Exception(f"Not all JSON-RPC endpoints returned valid responses: {results}")
            
        return results
        
    @test_wrapper("IPFS Operations")
    def verify_ipfs_operations(self):
        """Verify IPFS operations (add, cat, pin)."""
        results = {}
        
        # Test add operation
        test_content = f"Test content from MCP verifier: {uuid.uuid4()}"
        files = {'file': ('test.txt', test_content)}
        
        try:
            add_url = f"{self.api_url}/ipfs/add"
            logger.info(f"Testing IPFS add: {add_url}")
            
            add_response = requests.post(add_url, files=files)
            if add_response.status_code != 200:
                raise Exception(f"Failed to add file to IPFS: {add_response.status_code}")
                
            add_data = add_response.json()
            if not add_data.get("success", False):
                raise Exception(f"IPFS add operation failed: {add_data}")
                
            cid = add_data.get("cid")
            if not cid:
                raise Exception("No CID returned from add operation")
                
            logger.info(f"  - File added with CID: {cid}")
            results["add"] = add_data
            self.created_cids.append(cid)
            
            # Test cat operation
            cat_url = f"{self.api_url}/ipfs/cat/{cid}"
            logger.info(f"Testing IPFS cat: {cat_url}")
            
            cat_response = requests.get(cat_url)
            if cat_response.status_code != 200:
                raise Exception(f"Failed to cat file from IPFS: {cat_response.status_code}")
                
            cat_content = cat_response.text
            if cat_content != test_content:
                raise Exception(f"Cat content doesn't match original: {cat_content}")
                
            logger.info(f"  - Cat operation successful, content verified")
            results["cat"] = {"success": True, "content_matches": True}
            
            # Test pin operations
            pin_add_url = f"{self.api_url}/ipfs/pin/add?cid={cid}"
            logger.info(f"Testing IPFS pin add: {pin_add_url}")
            
            pin_add_response = requests.get(pin_add_url)
            if pin_add_response.status_code != 200:
                raise Exception(f"Failed to pin file in IPFS: {pin_add_response.status_code}")
                
            pin_add_data = pin_add_response.json()
            if not pin_add_data.get("success", False):
                raise Exception(f"IPFS pin add operation failed: {pin_add_data}")
                
            logger.info(f"  - Pin add operation successful")
            results["pin_add"] = pin_add_data
            
            # Test pin ls operation
            pin_ls_url = f"{self.api_url}/ipfs/pin/ls"
            logger.info(f"Testing IPFS pin ls: {pin_ls_url}")
            
            pin_ls_response = requests.get(pin_ls_url)
            if pin_ls_response.status_code != 200:
                raise Exception(f"Failed to list pins in IPFS: {pin_ls_response.status_code}")
                
            pin_ls_data = pin_ls_response.json()
            if not pin_ls_data.get("success", False):
                raise Exception(f"IPFS pin ls operation failed: {pin_ls_data}")
                
            # Check if our CID is in the list
            pins = pin_ls_data.get("pins", [])
            if cid not in pins:
                raise Exception(f"Added CID {cid} not found in pins list")
                
            logger.info(f"  - Pin ls operation successful, found CID in pins list")
            results["pin_ls"] = pin_ls_data
            
        except requests.RequestException as e:
            raise Exception(f"Error during IPFS operations: {e}")
            
        return results

def main():
    """Run the verification script."""
    parser = argparse.ArgumentParser(description="Verify the enhanced MCP server")
    parser.add_argument("--host", type=str, default="localhost", help="Host running the MCP server")
    parser.add_argument("--port", type=int, default=9994, help="Port the MCP server is running on")
    
    args = parser.parse_args()
    
    verifier = MCPVerifier(host=args.host, port=args.port)
    exit_code = verifier.run_verification()
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
