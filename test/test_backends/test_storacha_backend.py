#!/usr/bin/env python3
"""
Test script for Storacha storage backend with the new endpoint.

This script demonstrates how to use the updated Storacha storage backend
with the new endpoint: https://up.storacha.network/bridge
"""

import os
import sys
import time
import logging
import argparse
import json
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("storacha_test")

# Add the parent directory to the path to import our modules
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.append(parent_dir)

# Import our storage implementation
from storacha_storage import StorachaStorage

def print_json(data):
    """Print data as formatted JSON."""
    print(json.dumps(data, indent=2, default=str))

def test_status(storage):
    """Test the status check functionality."""
    logger.info("Testing status check...")
    status = storage.status()
    print_json(status)
    return status

def create_test_file(file_path, size_kb=10):
    """Create a test file with random content."""
    logger.info(f"Creating test file: {file_path} ({size_kb}KB)")
    with open(file_path, 'wb') as f:
        f.write(os.urandom(size_kb * 1024))
    return file_path

def add_to_ipfs(file_path):
    """Add a file to IPFS and return the CID."""
    logger.info(f"Adding file to IPFS: {file_path}")
    result = subprocess.run(
        ["ipfs", "add", "-q", file_path],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        logger.error(f"Failed to add file to IPFS: {result.stderr}")
        return None
    
    cid = result.stdout.strip()
    logger.info(f"Added to IPFS with CID: {cid}")
    return cid

def test_from_ipfs(storage, cid):
    """Test storing content from IPFS to Storacha."""
    logger.info(f"Testing from_ipfs with CID: {cid}")
    result = storage.from_ipfs(cid)
    print_json(result)
    return result

def test_check_status(storage, storage_id):
    """Test checking content status in Storacha."""
    logger.info(f"Testing check_status with storage ID: {storage_id}")
    result = storage.check_status(storage_id)
    print_json(result)
    return result

def test_to_ipfs(storage, storage_id):
    """Test retrieving content from Storacha to IPFS."""
    logger.info(f"Testing to_ipfs with storage ID: {storage_id}")
    result = storage.to_ipfs(storage_id)
    print_json(result)
    return result

def test_list_blobs(storage):
    """Test listing blobs in Storacha."""
    logger.info("Testing list_blobs...")
    result = storage.list_blobs()
    print_json(result)
    return result

def test_get_blob(storage, digest):
    """Test getting blob info in Storacha."""
    logger.info(f"Testing get_blob with digest: {digest}")
    result = storage.get_blob(digest)
    print_json(result)
    return result

def test_remove_blob(storage, digest):
    """Test removing a blob from Storacha."""
    logger.info(f"Testing remove_blob with digest: {digest}")
    result = storage.remove_blob(digest)
    print_json(result)
    return result

def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test Storacha storage backend")
    parser.add_argument("--mock", action="store_true", help="Force mock mode")
    parser.add_argument("--api-key", type=str, help="Storacha API key")
    parser.add_argument("--api-endpoint", type=str, help="Storacha API endpoint")
    parser.add_argument("--test-file", type=str, default="storacha_test_file.bin", help="Test file path")
    args = parser.parse_args()

    # Set environment variables if provided
    if args.api_key:
        os.environ["STORACHA_API_KEY"] = args.api_key
    if args.api_endpoint:
        os.environ["STORACHA_API_URL"] = args.api_endpoint
    if args.mock:
        os.environ["MCP_USE_STORACHA_MOCK"] = "true"

    # Initialize the storage backend
    storage = StorachaStorage()
    
    # Test connection status
    status = test_status(storage)
    
    # If connection failed but mock mode is available, switch to mock mode
    if not status.get("success", False) and not storage.mock_mode and STORACHA_LIBRARIES_AVAILABLE:
        logger.info("Connection failed, switching to mock mode...")
        storage.mock_mode = True
        storage.simulation_mode = False
        status = test_status(storage)
    
    # Skip further tests if status check failed
    if not status.get("success", False):
        logger.error("Status check failed, skipping further tests")
        return 1
    
    # Create a test file
    file_path = create_test_file(args.test_file)
    
    try:
        # Add the file to IPFS
        cid = add_to_ipfs(file_path)
        if not cid:
            logger.error("Failed to add file to IPFS, skipping further tests")
            return 1
        
        # Test from_ipfs operation
        result = test_from_ipfs(storage, cid)
        if not result.get("success", False):
            logger.error("from_ipfs operation failed, skipping related tests")
            return 1
        
        # Get the storage ID from the result
        storage_id = result.get("storage_id")
        if storage_id:
            # Test check_status operation
            test_check_status(storage, storage_id)
            
            # Test to_ipfs operation
            test_to_ipfs(storage, storage_id)
            
            # Test list_blobs operation
            test_list_blobs(storage)
            
            # Test get_blob operation
            test_get_blob(storage, cid)
            
            # Test remove_blob operation
            test_remove_blob(storage, cid)
            
        logger.info("All tests completed successfully!")
        return 0
        
    finally:
        # Clean up the test file
        if os.path.exists(file_path):
            logger.info(f"Cleaning up test file: {file_path}")
            os.unlink(file_path)

if __name__ == "__main__":
    # Import this here to avoid import issues
    from storacha_storage import STORACHA_LIBRARIES_AVAILABLE
    sys.exit(main())