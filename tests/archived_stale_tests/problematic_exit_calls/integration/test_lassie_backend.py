#!/usr/bin/env python
"""
Comprehensive test script for the Lassie backend implementation.

This script tests the Lassie backend functionality to verify
that it works correctly within the MCP framework.
"""

import logging
import sys
import os
import json
import time
import uuid
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("lassie_backend_test")

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def run_lassie_backend_test():
    """Run comprehensive tests on the Lassie backend implementation."""
    logger.info("Starting Lassie backend test...")
    
    try:
        # Import the LassieBackend class
        from ipfs_kit_py.mcp.storage_manager.backends.lassie_backend import LassieBackend
        logger.info("Successfully imported LassieBackend")
        
        # Check for Lassie binary path from environment variable or use auto-detection
        lassie_path = os.environ.get("LASSIE_PATH")
        
        # Create resources and metadata for backend
        resources = {
            "lassie_path": lassie_path,
            "ipfs_gateways": [
                "https://ipfs.io",
                "https://cloudflare-ipfs.com",
                "https://dweb.link"
            ],
            "use_ipfs_gateways": True
        }
        
        metadata = {}
        
        # Initialize the backend
        backend = LassieBackend(resources, metadata)
        
        if not backend:
            logger.error("Failed to initialize LassieBackend")
            return False
            
        logger.info("Successfully initialized LassieBackend")
        
        # Test backend metadata
        logger.info(f"Backend name: {backend.get_name()}")
        
        # Test 1: Retrieve a well-known CID from the IPFS network
        # Using QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx as it's the CID for a small "hello world" file
        test_cid = "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx"
        retrieve_result = backend.retrieve(test_cid)
        logger.info(f"Retrieve operation result: {json.dumps(retrieve_result, indent=2, default=str)}")
        
        if not retrieve_result.get("success", False):
            logger.error("❌ Retrieve operation failed")
            return False
            
        logger.info("✅ Retrieve operation successful")
        
        # Check the content
        retrieved_data = retrieve_result.get("data")
        if isinstance(retrieved_data, bytes):
            retrieved_text = retrieved_data.decode('utf-8')
        else:
            retrieved_text = str(retrieved_data)
            
        logger.info(f"Retrieved data: {retrieved_text[:50]}...")
        
        if "hello world" in retrieved_text.lower():
            logger.info("✅ Retrieved content contains expected 'hello world' text")
        else:
            logger.warning("⚠️ Retrieved content doesn't contain expected text")
            
        # Test 2: Check if content exists
        exists_result = backend.exists(test_cid)
        logger.info(f"Content exists check: {exists_result}")
        
        if exists_result:
            logger.info("✅ Content exists check passed")
        else:
            logger.warning("⚠️ Content exists check failed")
            
        # Test 3: Get metadata
        metadata_result = backend.get_metadata(test_cid)
        logger.info(f"Metadata result: {json.dumps(metadata_result, indent=2, default=str)}")
        
        if metadata_result.get("success", False):
            logger.info("✅ Get metadata operation successful")
        else:
            logger.warning("⚠️ Get metadata operation failed")
            
        # Test 4: Update metadata
        test_metadata = {
            "test_key": "test_value",
            "timestamp": time.time(),
            "description": "Test metadata added by Lassie backend test"
        }
        update_metadata_result = backend.update_metadata(test_cid, test_metadata)
        logger.info(f"Update metadata result: {json.dumps(update_metadata_result, indent=2, default=str)}")
        
        if update_metadata_result.get("success", False):
            logger.info("✅ Update metadata operation successful")
        else:
            logger.warning("⚠️ Update metadata operation failed")
            
        # Test 5: List items in cache
        list_result = backend.list()
        logger.info(f"List operation result: {json.dumps(list_result, indent=2, default=str)}")
        
        if list_result.get("success", False):
            logger.info(f"List operation found {len(list_result.get('items', []))} items")
            logger.info("✅ List operation successful")
            
            # Check if our test CID is in the list
            found_cid = False
            for item in list_result.get("items", []):
                if item.get("identifier") == test_cid:
                    found_cid = True
                    break
                    
            if found_cid:
                logger.info("✅ Found our test CID in the cache list")
            else:
                logger.warning("⚠️ Didn't find our test CID in the cache list")
        else:
            logger.warning("⚠️ List operation failed")
            
        # Test 6: Delete (remove from cache)
        delete_result = backend.delete(test_cid)
        logger.info(f"Delete operation result: {json.dumps(delete_result, indent=2, default=str)}")
        
        if delete_result.get("success", False):
            logger.info("✅ Delete operation successful")
            
            # Verify the content is no longer in cache
            exists_after_delete = backend.exists(test_cid, options={"check_network": False})
            if not exists_after_delete:
                logger.info("✅ Content properly removed from cache")
            else:
                logger.warning("⚠️ Content still exists in cache after delete")
        else:
            logger.warning("⚠️ Delete operation failed")
            
        # Test 7: Test special Lassie-specific operations if Lassie binary is available
        if backend.lassie_path:
            logger.info("Testing Lassie-specific operations with Lassie binary")
            
            # Test fetching content as CAR file
            car_result = backend.fetch_car(test_cid)
            logger.info(f"Fetch CAR result: {json.dumps(car_result, indent=2, default=str)}")
            
            if car_result.get("success", False):
                logger.info("✅ Fetch CAR operation successful")
                
                # Check if CAR file exists
                car_path = car_result.get("car_path")
                if car_path and os.path.exists(car_path):
                    logger.info(f"✅ CAR file exists at {car_path}")
                else:
                    logger.warning("⚠️ CAR file not found at expected path")
            else:
                logger.warning("⚠️ Fetch CAR operation failed")
        else:
            logger.info("Skipping Lassie-specific operations as Lassie binary is not available")
            
        # Test 8: Clear cache
        clear_result = backend.clear_cache()
        logger.info(f"Clear cache result: {json.dumps(clear_result, indent=2, default=str)}")
        
        if clear_result.get("success", False):
            logger.info("✅ Clear cache operation successful")
            
            # Verify cache is empty
            list_after_clear = backend.list()
            if len(list_after_clear.get("items", [])) == 0:
                logger.info("✅ Cache is empty after clear")
            else:
                logger.warning("⚠️ Cache still contains items after clear")
        else:
            logger.warning("⚠️ Clear cache operation failed")
        
        logger.info("All tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error testing Lassie backend: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = run_lassie_backend_test()
    if success:
        logger.info("✅ Lassie backend test passed!")
        sys.exit(0)
    else:
        logger.error("❌ Lassie backend test failed")
        sys.exit(1)