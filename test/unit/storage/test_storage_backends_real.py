#!/usr/bin/env python3
"""
Test script for real API storage backends.
"""

import os
import sys
import json
import time
import requests
import logging
import argparse
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
TEST_FILE = "/tmp/storage_test_file.txt"
TEST_CONTENT = "This is test content for storage backends\n" * 100

def create_test_file():
    """Create a test file with known content."""
    with open(TEST_FILE, "w") as f:
        f.write(TEST_CONTENT)
    logger.info(f"Created test file at {TEST_FILE} ({os.path.getsize(TEST_FILE)} bytes)")
    return TEST_FILE

def test_backend(server_url, backend):
    """Test a specific storage backend."""
    logger.info(f"Testing {backend} backend")
    
    # Check status
    status_url = f"{server_url}/{backend}/status"
    try:
        response = requests.get(status_url)
        if response.status_code == 200:
            status = response.json()
            logger.info(f"{backend} status: {status}")
            
            is_simulation = status.get("simulation", True)
            logger.info(f"Running in {'SIMULATION' if is_simulation else 'REAL'} mode")
            
            # Only proceed if backend is available
            if not status.get("is_available", False):
                logger.error(f"{backend} is not available, skipping")
                return {"success": False, "error": "Backend not available"}
        else:
            logger.error(f"Failed to get {backend} status: {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        logger.error(f"Error testing {backend} status: {e}")
        return {"success": False, "error": str(e)}
    
    # For HuggingFace, test IPFS to HuggingFace
    if backend == "huggingface":
        # Upload to IPFS first
        logger.info("Uploading test file to IPFS")
        try:
            with open(TEST_FILE, "rb") as f:
                response = requests.post(
                    f"{server_url}/ipfs/add",
                    files={"file": f}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    cid = result.get("cid")
                    logger.info(f"Uploaded to IPFS with CID: {cid}")
                    
                    # Transfer to HuggingFace
                    logger.info(f"Transferring from IPFS to HuggingFace")
                    response = requests.post(
                        f"{server_url}/huggingface/from_ipfs",
                        json={"cid": cid, "repo_id": "test-repo"}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"Transfer to HuggingFace result: {result}")
                        
                        # Transfer back to IPFS
                        logger.info(f"Transferring from HuggingFace to IPFS")
                        response = requests.post(
                            f"{server_url}/huggingface/to_ipfs",
                            json={"repo_id": "test-repo", "path_in_repo": result.get("path_in_repo")}
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            logger.info(f"Transfer back to IPFS result: {result}")
                            return {"success": True, "result": result}
                        else:
                            logger.error(f"Failed to transfer back to IPFS: {response.status_code} - {response.text}")
                            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                    else:
                        logger.error(f"Failed to transfer to HuggingFace: {response.status_code} - {response.text}")
                        return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                else:
                    logger.error(f"Failed to upload to IPFS: {response.status_code} - {response.text}")
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            logger.error(f"Error testing {backend}: {e}")
            return {"success": False, "error": str(e)}
    
    # Default case for other backends
    return {"success": True, "message": f"{backend} status check passed"}

def main():
    parser = argparse.ArgumentParser(description="Test real API storage backends")
    parser.add_argument("--url", default="http://localhost:9992/api/v0", help="Server URL")
    parser.add_argument("--backend", help="Specific backend to test")
    args = parser.parse_args()
    
    print(f"=== TESTING STORAGE BACKENDS - {args.url} ===\n")
    
    # Create test file
    create_test_file()
    
    # Define backends to test
    backends = ["huggingface"]
    if args.backend:
        backends = [args.backend]
    
    # Test each backend
    results = {}
    for backend in backends:
        print(f"\n--- Testing {backend.upper()} backend ---")
        result = test_backend(args.url, backend)
        results[backend] = result
        status = "✅ PASSED" if result.get("success", False) else "❌ FAILED"
        print(f"{backend}: {status}")
    
    # Print summary
    print("\n=== SUMMARY ===")
    for backend, result in results.items():
        status = "✅ PASSED" if result.get("success", False) else "❌ FAILED"
        print(f"{backend}: {status}")
        if not result.get("success", False) and "error" in result:
            print(f"  Error: {result['error']}")

if __name__ == "__main__":
    main()
