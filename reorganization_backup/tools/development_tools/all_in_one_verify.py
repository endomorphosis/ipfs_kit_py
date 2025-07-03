#!/usr/bin/env python3
"""
All-in-One MCP Server Verification Script

This script verifies all functionality of the all-in-one MCP server, including:
1. Basic connectivity
2. IPFS operations (add, cat, pin)
3. JSON-RPC support (using integrated endpoint)
4. Storage backend functionality
"""

import os
import sys
import json
import time
import uuid
import argparse
import requests
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AllInOneVerifier:
    """Verifies all-in-one MCP server functionality."""
    
    def __init__(self, host: str = "localhost", port: int = 9994):
        """Initialize the MCP verifier."""
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.api_prefix = "/api/v0"
        self.api_url = f"{self.base_url}{self.api_prefix}"
        self.json_rpc_url = f"{self.base_url}/jsonrpc"  # Integrated JSON-RPC endpoint
        self.tests_passed = 0
        self.tests_failed = 0
        self.tests_skipped = 0
        self.created_cids = []
        
    def run_verification(self):
        """Run all verification tests."""
        logger.info("=" * 80)
        logger.info("Starting All-in-One MCP Server Verification...")
        logger.info("=" * 80)
        
        # Basic connectivity tests
        self.verify_connectivity()
        
        # JSON-RPC support tests
        self.verify_jsonrpc_support()
        
        # IPFS operations tests
        self.verify_ipfs_operations()
        
        # Health check tests
        self.verify_health_check()
        
        # Storage backend tests
        self.verify_storage_backends()
        
        # Summary
        logger.info("=" * 80)
        logger.info(f"VERIFICATION SUMMARY: {self.tests_passed} passed, {self.tests_failed} failed, {self.tests_skipped} skipped")
        logger.info("=" * 80)
        
        # If we created any CIDs, clean them up
        self.cleanup()
        
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
        required_fields = ["message", "controllers", "example_endpoints"]
        for field in required_fields:
            if field not in data:
                raise Exception(f"Missing field in response: {field}")
                
        # Check for expected controllers
        required_controllers = ["ipfs", "storage_manager"]
        for controller in required_controllers:
            if controller not in data["controllers"]:
                raise Exception(f"Missing controller: {controller}")
                
        return data
        
    @test_wrapper("JSON-RPC Support - Initialize")
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
        
        # Test the integrated JSON-RPC endpoint
        response = requests.post(
            self.json_rpc_url,
            json=initialize_request
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to connect to JSON-RPC endpoint: {response.status_code}")
            
        data = response.json()
        if "result" not in data or "capabilities" not in data["result"]:
            raise Exception(f"Invalid JSON-RPC response: {data}")
            
        # Test the API prefix endpoint
        api_response = requests.post(
            f"{self.api_url}/jsonrpc",
            json=initialize_request
        )
        
        if api_response.status_code != 200:
            raise Exception(f"Failed to connect to API JSON-RPC endpoint: {api_response.status_code}")
            
        api_data = api_response.json()
        if "result" not in api_data or "capabilities" not in api_data["result"]:
            raise Exception(f"Invalid JSON-RPC response from API endpoint: {api_data}")
            
        return {"root": data, "api": api_data}
    
    @test_wrapper("IPFS Add Operation")
    def verify_ipfs_add(self):
        """Verify IPFS add operation."""
        # Create test content
        test_content = f"Test content from All-in-One verifier: {uuid.uuid4()}"
        files = {'file': ('test.txt', test_content)}
        
        response = requests.post(
            f"{self.api_url}/ipfs/add",
            files=files
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to add file to IPFS: {response.status_code}")
            
        data = response.json()
        if not data.get("success") or "cid" not in data:
            raise Exception(f"Invalid response for IPFS add: {data}")
            
        # Save CID for later tests
        self.created_cids.append(data["cid"])
        
        return data
    
    @test_wrapper("IPFS Cat Operation")
    def verify_ipfs_cat(self):
        """Verify IPFS cat operation."""
        if not self.created_cids:
            self.tests_skipped += 1
            logger.warning("⚠️ SKIP: IPFS Cat Operation - No CIDs available")
            return None
            
        cid = self.created_cids[0]
        response = requests.get(f"{self.api_url}/ipfs/cat/{cid}")
        
        if response.status_code != 200:
            raise Exception(f"Failed to cat file from IPFS: {response.status_code}")
            
        # Content should be returned directly
        content = response.content.decode('utf-8')
        if not content or len(content) == 0:
            raise Exception("Empty content returned from IPFS cat")
            
        return {"cid": cid, "content_length": len(content)}
    
    @test_wrapper("IPFS Pin Add Operation")
    def verify_ipfs_pin_add(self):
        """Verify IPFS pin add operation."""
        if not self.created_cids:
            self.tests_skipped += 1
            logger.warning("⚠️ SKIP: IPFS Pin Add Operation - No CIDs available")
            return None
            
        cid = self.created_cids[0]
        response = requests.get(f"{self.api_url}/ipfs/pin/add?cid={cid}")
        
        if response.status_code != 200:
            raise Exception(f"Failed to pin file in IPFS: {response.status_code}")
            
        data = response.json()
        if not data.get("success") or data.get("cid") != cid:
            raise Exception(f"Invalid response for IPFS pin add: {data}")
            
        return data
    
    @test_wrapper("IPFS Pin List Operation")
    def verify_ipfs_pin_ls(self):
        """Verify IPFS pin ls operation."""
        response = requests.get(f"{self.api_url}/ipfs/pin/ls")
        
        if response.status_code != 200:
            raise Exception(f"Failed to list pins in IPFS: {response.status_code}")
            
        data = response.json()
        if not data.get("success") or "pins" not in data:
            raise Exception(f"Invalid response for IPFS pin ls: {data}")
            
        return data
    
    @test_wrapper("IPFS Pin Remove Operation")
    def verify_ipfs_pin_rm(self):
        """Verify IPFS pin rm operation."""
        if not self.created_cids:
            self.tests_skipped += 1
            logger.warning("⚠️ SKIP: IPFS Pin Remove Operation - No CIDs available")
            return None
            
        cid = self.created_cids[0]
        response = requests.get(f"{self.api_url}/ipfs/pin/rm?cid={cid}")
        
        if response.status_code != 200:
            raise Exception(f"Failed to unpin file from IPFS: {response.status_code}")
            
        data = response.json()
        if not data.get("success") or data.get("cid") != cid:
            raise Exception(f"Invalid response for IPFS pin rm: {data}")
            
        return data
    
    @test_wrapper("Health Check")
    def verify_health_check(self):
        """Verify health check endpoint."""
        response = requests.get(f"{self.api_url}/tools/health")
        
        if response.status_code != 200:
            raise Exception(f"Failed to check health: {response.status_code}")
            
        data = response.json()
        if "methods" not in data:
            raise Exception(f"Invalid response for health check: {data}")
            
        pin_methods = ["pin_add", "pin_rm", "pin_ls"]
        for method in pin_methods:
            if method not in data["methods"] or not data["methods"][method].get("available"):
                raise Exception(f"Missing or unavailable method: {method}")
                
        return data
        
    def verify_ipfs_operations(self):
        """Verify all IPFS operations."""
        # Add
        add_result = self.verify_ipfs_add()
        
        # Cat
        cat_result = self.verify_ipfs_cat()
        
        # Pin add
        pin_add_result = self.verify_ipfs_pin_add()
        
        # Pin ls
        pin_ls_result = self.verify_ipfs_pin_ls()
        
        # Pin rm
        pin_rm_result = self.verify_ipfs_pin_rm()
    
    @test_wrapper("Storage Backends Health")
    def verify_storage_backends(self):
        """Verify storage backends are available."""
        # Check root endpoint for storage backends info
        response = requests.get(f"{self.base_url}")
        
        if response.status_code != 200:
            raise Exception(f"Failed to connect to MCP server: {response.status_code}")
            
        data = response.json()
        if "storage_backends" not in data:
            raise Exception("Storage backends information not available")
            
        # Check that at least IPFS backend is available
        if "ipfs" not in data["storage_backends"] or not data["storage_backends"]["ipfs"]["available"]:
            raise Exception("IPFS storage backend not available")
            
        return data["storage_backends"]
    
    def cleanup(self):
        """Clean up any resources created during verification."""
        logger.info("Cleaning up resources...")
        
        for cid in self.created_cids:
            try:
                # Try to unpin if it's still pinned
                requests.get(f"{self.api_url}/ipfs/pin/rm?cid={cid}")
                logger.info(f"Unpinned CID: {cid}")
            except Exception as e:
                logger.warning(f"Failed to unpin CID {cid}: {e}")
        
        logger.info("Cleanup completed")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Verify All-in-One MCP Server functionality")
    parser.add_argument("--host", type=str, default="localhost",
                      help="MCP server host (default: localhost)")
    parser.add_argument("--port", type=int, default=9994,
                      help="MCP server port (default: 9994)")
    
    args = parser.parse_args()
    
    verifier = AllInOneVerifier(
        host=args.host,
        port=args.port
    )
    
    return verifier.run_verification()

if __name__ == "__main__":
    sys.exit(main())
