#!/usr/bin/env python3
"""
Storacha Connection Test Script

This script tests the enhanced Storacha connection handling with the following features:
- Multiple endpoint support with automatic failover
- Exponential backoff for retries
- Health checking and endpoint validation
- Detailed connection status reporting
"""

import os
import sys
import time
import json
import logging
import argparse
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our enhanced Storacha implementation
try:
    from enhanced_storacha_storage import EnhancedStorachaStorage
    from mcp_extensions.storacha_connection import StorachaConnectionManager
except ImportError as e:
    logger.error(f"Import error: {e}")
    sys.exit(1)

def test_connection_manager(api_key: Optional[str] = None, api_endpoint: Optional[str] = None) -> None:
    """
    Test the Storacha connection manager with various scenarios.
    
    Args:
        api_key: Optional API key
        api_endpoint: Optional API endpoint
    """
    logger.info("-" * 80)
    logger.info("TESTING STORACHA CONNECTION MANAGER")
    logger.info("-" * 80)
    
    # Get credentials from environment if not provided
    if not api_key:
        api_key = os.environ.get("STORACHA_API_KEY")
    
    if not api_endpoint:
        api_endpoint = os.environ.get("STORACHA_API_URL") or os.environ.get("STORACHA_API_ENDPOINT")
    
    logger.info(f"API Key: {'Provided' if api_key else 'Not provided'}")
    logger.info(f"API Endpoint: {api_endpoint or 'Not provided'}")
    
    # Create connection manager with default settings
    conn_manager = StorachaConnectionManager(
        api_key=api_key,
        api_endpoint=api_endpoint,
        validate_endpoints=True
    )
    
    # Display initial status
    status = conn_manager.get_status()
    logger.info(f"Initial connection status:")
    logger.info(f"Working endpoint: {status['working_endpoint']}")
    logger.info(f"Authenticated: {status['authenticated']}")
    
    # Display endpoint health
    logger.info("Endpoint health status:")
    for endpoint in status['endpoints']:
        logger.info(f"  {endpoint['url']}: {'Healthy' if endpoint['healthy'] else 'Unhealthy'} (Failures: {endpoint['failures']})")
    
    # Test connection with health check
    logger.info("\nTesting health check endpoint...")
    try:
        response = conn_manager.send_request("GET", "health")
        logger.info(f"Health check successful: {response.status_code}")
        try:
            logger.info(f"Response: {json.dumps(response.json(), indent=2)}")
        except:
            logger.info(f"Response: {response.text[:100]}...")
    except Exception as e:
        logger.error(f"Health check failed: {e}")
    
    # Get updated status
    status = conn_manager.get_status()
    logger.info(f"\nUpdated connection status:")
    logger.info(f"Working endpoint: {status['working_endpoint']}")
    
    # Display endpoint health
    logger.info("Updated endpoint health status:")
    for endpoint in status['endpoints']:
        logger.info(f"  {endpoint['url']}: {'Healthy' if endpoint['healthy'] else 'Unhealthy'} (Failures: {endpoint['failures']})")
    
    logger.info("-" * 80)
    
def test_enhanced_storage(api_key: Optional[str] = None, api_endpoint: Optional[str] = None) -> None:
    """
    Test the enhanced Storacha storage implementation.
    
    Args:
        api_key: Optional API key
        api_endpoint: Optional API endpoint
    """
    logger.info("-" * 80)
    logger.info("TESTING ENHANCED STORACHA STORAGE")
    logger.info("-" * 80)
    
    # Get credentials from environment if not provided
    if not api_key:
        api_key = os.environ.get("STORACHA_API_KEY")
    
    if not api_endpoint:
        api_endpoint = os.environ.get("STORACHA_API_URL") or os.environ.get("STORACHA_API_ENDPOINT")
    
    logger.info(f"API Key: {'Provided' if api_key else 'Not provided'}")
    logger.info(f"API Endpoint: {api_endpoint or 'Not provided'}")
    
    # Create enhanced storage
    storage = EnhancedStorachaStorage(
        api_key=api_key,
        api_endpoint=api_endpoint
    )
    
    # Check status
    status = storage.status()
    logger.info(f"Storage status: {json.dumps(status, indent=2)}")
    
    # Determine if we're in mock mode
    mock_mode = status.get("mock", False)
    logger.info(f"Mock mode: {mock_mode}")
    
    # Test basic operations
    if not mock_mode:
        logger.info("\nTesting real Storacha operations...")
        
        # Step 1: Create a test file and add it to IPFS
        logger.info("Creating test file and adding to IPFS...")
        test_content = f"Test file created at {time.time()}".encode("utf-8")
        
        # Create temp file with test content
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name
        
        # Add to IPFS
        import subprocess
        process = subprocess.run(
            ["ipfs", "add", "-Q", temp_file_path],
            capture_output=True,
            timeout=30
        )
        
        # Clean up temp file
        try:
            os.unlink(temp_file_path)
        except:
            pass
        
        if process.returncode != 0:
            logger.error(f"Error adding to IPFS: {process.stderr.decode('utf-8')}")
            return
        
        cid = process.stdout.decode("utf-8").strip()
        logger.info(f"File added to IPFS with CID: {cid}")
        
        # Step 2: Store file from IPFS to Storacha
        logger.info(f"Storing CID {cid} in Storacha...")
        from_ipfs_result = storage.from_ipfs(cid)
        logger.info(f"Result: {json.dumps(from_ipfs_result, indent=2)}")
        
        if not from_ipfs_result.get("success", False):
            logger.error("Storacha storage test failed at from_ipfs step")
            return
        
        storage_id = from_ipfs_result.get("storage_id")
        logger.info(f"Stored in Storacha with ID: {storage_id}")
        
        # Step 3: Check status
        logger.info(f"Checking status for storage ID {storage_id}...")
        time.sleep(1)  # Give it a moment
        status_result = storage.check_status(storage_id)
        logger.info(f"Status result: {json.dumps(status_result, indent=2)}")
        
        # Step 4: List blobs
        logger.info("Listing blobs in Storacha...")
        list_result = storage.list_blobs(size=5)
        logger.info(f"List result: {json.dumps(list_result, indent=2)}")
        
        # Step 5: Retrieve from Storacha back to IPFS
        logger.info(f"Retrieving storage ID {storage_id} back to IPFS...")
        to_ipfs_result = storage.to_ipfs(storage_id)
        logger.info(f"Result: {json.dumps(to_ipfs_result, indent=2)}")
        
        if to_ipfs_result.get("success", False):
            retrieved_cid = to_ipfs_result.get("cid")
            logger.info(f"Retrieved to IPFS with CID: {retrieved_cid}")
            
            # Verify CIDs match
            if retrieved_cid == cid:
                logger.info("SUCCESS: Retrieved CID matches original CID")
            else:
                logger.warning(f"WARNING: Retrieved CID {retrieved_cid} does not match original CID {cid}")
        
        # Step 6 (optional): Remove blob
        # Uncomment to test removal
        # logger.info(f"Removing storage ID {storage_id} from Storacha...")
        # remove_result = storage.remove_blob(storage_id)
        # logger.info(f"Remove result: {json.dumps(remove_result, indent=2)}")
    
    else:
        logger.info("\nTesting mock Storacha operations...")
        
        # Mock mode testing process is similar but will use local storage
        # Step 1: Create a test file and add it to IPFS
        logger.info("Creating test file and adding to IPFS...")
        test_content = f"Mock test file created at {time.time()}".encode("utf-8")
        
        # Create temp file with test content
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name
        
        # Add to IPFS
        import subprocess
        process = subprocess.run(
            ["ipfs", "add", "-Q", temp_file_path],
            capture_output=True,
            timeout=30
        )
        
        # Clean up temp file
        try:
            os.unlink(temp_file_path)
        except:
            pass
        
        if process.returncode != 0:
            logger.error(f"Error adding to IPFS: {process.stderr.decode('utf-8')}")
            return
        
        cid = process.stdout.decode("utf-8").strip()
        logger.info(f"File added to IPFS with CID: {cid}")
        
        # Step 2: Store file from IPFS to Storacha
        logger.info(f"Storing CID {cid} in mock Storacha...")
        from_ipfs_result = storage.from_ipfs(cid)
        logger.info(f"Result: {json.dumps(from_ipfs_result, indent=2)}")
        
        if not from_ipfs_result.get("success", False):
            logger.error("Mock Storacha storage test failed at from_ipfs step")
            return
        
        storage_id = from_ipfs_result.get("storage_id")
        logger.info(f"Stored in mock Storacha with ID: {storage_id}")
        
        # Step 3: Check status
        logger.info(f"Checking status for storage ID {storage_id}...")
        status_result = storage.check_status(storage_id)
        logger.info(f"Status result: {json.dumps(status_result, indent=2)}")
        
        # Step 4: List blobs
        logger.info("Listing blobs in mock Storacha...")
        list_result = storage.list_blobs(size=5)
        logger.info(f"List result: {json.dumps(list_result, indent=2)}")
        
        # Step 5: Retrieve from Storacha back to IPFS
        logger.info(f"Retrieving storage ID {storage_id} back to IPFS...")
        to_ipfs_result = storage.to_ipfs(storage_id)
        logger.info(f"Result: {json.dumps(to_ipfs_result, indent=2)}")
        
        if to_ipfs_result.get("success", False):
            retrieved_cid = to_ipfs_result.get("cid")
            logger.info(f"Retrieved to IPFS with CID: {retrieved_cid}")
            
            # Verify CIDs match
            if retrieved_cid == cid:
                logger.info("SUCCESS: Retrieved CID matches original CID")
            else:
                logger.warning(f"WARNING: Retrieved CID {retrieved_cid} does not match original CID {cid}")
        
        # Step 6: Remove blob
        logger.info(f"Removing storage ID {storage_id} from mock Storacha...")
        remove_result = storage.remove_blob(storage_id)
        logger.info(f"Remove result: {json.dumps(remove_result, indent=2)}")
    
    logger.info("-" * 80)

def test_all(api_key: Optional[str] = None, api_endpoint: Optional[str] = None) -> None:
    """
    Run all tests.
    
    Args:
        api_key: Optional API key
        api_endpoint: Optional API endpoint
    """
    # Test connection manager
    test_connection_manager(api_key, api_endpoint)
    
    # Test enhanced storage
    test_enhanced_storage(api_key, api_endpoint)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Storacha API connection handling")
    parser.add_argument("--api-key", help="Storacha API key")
    parser.add_argument("--api-endpoint", help="Storacha API endpoint")
    parser.add_argument("--test", choices=["connection", "storage", "all"], default="all", help="Test to run")
    
    args = parser.parse_args()
    
    if args.test == "connection":
        test_connection_manager(args.api_key, args.api_endpoint)
    elif args.test == "storage":
        test_enhanced_storage(args.api_key, args.api_endpoint)
    else:
        test_all(args.api_key, args.api_endpoint)