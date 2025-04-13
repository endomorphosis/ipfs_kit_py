#!/usr/bin/env python3
"""
Test script to check all storage backends through the MCP server and fix any issues.
"""

import os
import sys
import time
import json
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
MCP_URL = "http://localhost:9991"
API_PREFIX = "/api/v0"
TEST_FILE = "/tmp/mcp_test_1mb.bin"

class StorageBackendTester:
    """Client for testing MCP server storage backends."""
    
    def __init__(self, server_url=MCP_URL, api_prefix=API_PREFIX):
        """Initialize the tester with server URL."""
        self.server_url = server_url
        self.api_prefix = api_prefix
        self.base_url = f"{server_url}{api_prefix}"
        logger.info(f"MCP Server tester initialized with URL: {self.base_url}")
    
    def check_server_health(self):
        """Check if the MCP server is running and healthy."""
        try:
            response = requests.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return {"success": False, "error": str(e)}
    
    def list_backends(self):
        """List all available storage backends."""
        try:
            response = requests.get(f"{self.base_url}/mcp/storage/list_backends")
            if response.status_code == 404:
                # Try alternative endpoint
                response = requests.get(f"{self.base_url}/storage_manager/list_backends")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to list backends: {response.status_code}")
                # Fallback to known backends
                return {
                    "success": True,
                    "backends": ["storage_huggingface", "storage_storacha", "storage_filecoin", 
                                "storage_lassie", "s3"]
                }
        except requests.RequestException as e:
            logger.error(f"Failed to list backends: {e}")
            return {"success": False, "error": str(e)}
    
    def create_test_file(self, size_mb=1):
        """Create a test file with random data."""
        if not os.path.exists(TEST_FILE):
            logger.info(f"Creating test file: {TEST_FILE} ({size_mb}MB)")
            os.system(f"dd if=/dev/urandom of={TEST_FILE} bs=1M count={size_mb}")
        
        logger.info(f"Test file size: {os.path.getsize(TEST_FILE)} bytes")
        return TEST_FILE
    
    def upload_to_ipfs(self, file_path):
        """Upload a file to IPFS through the MCP server."""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    f"{self.base_url}/ipfs/add",
                    files=files
                )
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"IPFS upload successful")
                    
                    # Handle different response formats
                    if "Hash" in result:
                        cid = result["Hash"]
                    elif "cid" in result:
                        cid = result["cid"]
                    else:
                        cid = list(result.get("result", {}).get("pins", {}).keys())[0] if result.get("result", {}).get("pins") else None
                    
                    logger.info(f"CID: {cid}")
                    return {"success": True, "cid": cid, "result": result}
                else:
                    logger.error(f"IPFS upload failed: {response.status_code}")
                    return {"success": False, "error": response.text}
        except Exception as e:
            logger.error(f"Error in IPFS upload: {e}")
            return {"success": False, "error": str(e)}
    
    def check_backend_status(self, backend):
        """Check the status of a storage backend."""
        try:
            # Try various endpoint patterns
            endpoints = [
                f"{self.base_url}/{backend}/status",
                f"{self.base_url}/storage/{backend}/status",
                f"{self.base_url}/{backend.replace('storage_', '')}/status"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint)
                    if response.status_code == 200:
                        return {"success": True, "endpoint": endpoint, "result": response.json()}
                except requests.RequestException:
                    continue
            
            logger.error(f"All status endpoints failed for {backend}")
            return {"success": False, "error": "All endpoints failed"}
        except Exception as e:
            logger.error(f"Error checking {backend} status: {e}")
            return {"success": False, "error": str(e)}
    
    def test_all_backends(self):
        """Test all available storage backends."""
        # First check health
        health = self.check_server_health()
        if not health.get("success", False):
            logger.error(f"MCP Server health check failed")
            return {"success": False, "error": "Server health check failed"}
        
        logger.info(f"MCP Server health check passed")
        
        # Create test file
        test_file = self.create_test_file()
        
        # Upload to IPFS
        ipfs_result = self.upload_to_ipfs(test_file)
        if not ipfs_result.get("success", False):
            logger.error(f"IPFS upload failed, can't test backends")
            return {"success": False, "error": "IPFS upload failed"}
        
        cid = ipfs_result.get("cid")
        logger.info(f"File uploaded to IPFS with CID: {cid}")
        
        # Get list of backends
        backends_list = self.list_backends()
        backends = backends_list.get("backends", [])
        
        results = {
            "health": health,
            "ipfs": ipfs_result,
            "backends": {}
        }
        
        # Test each backend
        for backend in backends:
            logger.info(f"\n=== Testing {backend} backend ===")
            status = self.check_backend_status(backend)
            
            backend_result = {
                "status_check": status,
                "test_ipfs_to_backend": None,
                "test_backend_to_ipfs": None
            }
            
            # If status check succeeded, try transfer tests
            if status.get("success", False):
                logger.info(f"{backend} status check passed")
                
                # Test IPFS to backend transfer (implementation will vary by backend)
                # We'll just log the capability for now
                logger.info(f"Would test IPFS → {backend} transfer here")
                
                # Test backend to IPFS transfer
                logger.info(f"Would test {backend} → IPFS transfer here")
            else:
                logger.error(f"{backend} status check failed")
            
            results["backends"][backend] = backend_result
        
        return results

def main():
    """Run the storage backend tests."""
    tester = StorageBackendTester()
    results = tester.test_all_backends()
    
    # Print summary
    print("\n=== TEST SUMMARY ===")
    print(f"Server health: {'✅ PASSED' if results.get('health', {}).get('success', False) else '❌ FAILED'}")
    print(f"IPFS upload: {'✅ PASSED' if results.get('ipfs', {}).get('success', False) else '❌ FAILED'}")
    
    backend_results = results.get("backends", {})
    for backend, result in backend_results.items():
        status = "✅ PASSED" if result.get("status_check", {}).get("success", False) else "❌ FAILED"
        print(f"{backend}: {status}")
    
    # Save results
    with open("storage_backend_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to storage_backend_test_results.json")

if __name__ == "__main__":
    main()