#!/usr/bin/env python
"""
Integration test for the IPFS backend and storage manager.

This script tests the integration between the fixed IPFS backend,
the new IPFS model, and the enhanced storage manager.
"""

import logging
import sys
import os
import json
import time
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ipfs_integration_test")

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def run_ipfs_integration_test():
    """Run integration tests for the IPFS components."""
    logger.info("Starting IPFS integration test...")
    
    try:
        # Import the storage manager
        from ipfs_kit_py.mcp.models.storage_manager import StorageManager
        logger.info("Successfully imported StorageManager")
        
        # Create test resources and metadata
        resources = {
            "ipfs": {
                "api_url": "http://localhost:5001/api/v0"
            }
        }
        metadata = {
            "ipfs": {
                "role": "leecher"
            }
        }
        
        # Initialize the storage manager
        storage_manager = StorageManager(
            resources=resources,
            metadata=metadata
        )
        
        if not storage_manager:
            logger.error("Failed to initialize StorageManager")
            return False
            
        logger.info("Successfully initialized StorageManager")
        
        # Check available backends
        available_backends = storage_manager.get_available_backends()
        logger.info(f"Available backends: {json.dumps(available_backends, indent=2)}")
        
        if not available_backends.get("ipfs", False):
            logger.error("IPFS backend not available in StorageManager")
            return False
            
        logger.info("IPFS backend is available in StorageManager")
        
        # Get the IPFS model from storage manager
        ipfs_model = storage_manager.get_model("ipfs")
        if not ipfs_model:
            logger.error("Failed to get IPFS model from StorageManager")
            return False
            
        logger.info("Successfully retrieved IPFS model from StorageManager")
        
        # Test basic operations with the IPFS model
        logger.info("Testing basic operations with IPFS model...")
        
        # Test 1: Add content
        test_content = f"Test content from MCP IPFS integration test - {time.time()}"
        logger.info(f"Adding test content: {test_content}")
        
        # Call the synchronous version of add_content
        add_result = ipfs_model.add_content_sync(test_content)
        logger.info(f"Add content result: {json.dumps(add_result, indent=2, default=str)}")
        
        if not add_result.get("success", False):
            logger.error("❌ Add content operation failed")
            return False
            
        logger.info("✅ Add content operation successful")
        
        # Get CID from result
        cid = add_result.get("cid")
        if not cid:
            logger.error("❌ No CID returned from add_content operation")
            return False
            
        logger.info(f"Content stored with CID: {cid}")
        
        # Test 2: Get content
        logger.info(f"Retrieving content for CID: {cid}")
        
        # Call the synchronous version of get_content
        get_result = ipfs_model.get_content_sync(cid)
        logger.info(f"Get content result: {json.dumps(get_result, indent=2, default=str)}")
        
        if not get_result.get("success", False):
            logger.error("❌ Get content operation failed")
            return False
            
        logger.info("✅ Get content operation successful")
        
        # Check if retrieved content matches
        content = get_result.get("content")
        if isinstance(content, bytes):
            content_text = content.decode("utf-8")
        else:
            content_text = str(content)
            
        if test_content in content_text:
            logger.info("✅ Retrieved content matches stored content")
        else:
            logger.warning("⚠️ Retrieved content doesn't match stored content")
            logger.info(f"Original: {test_content}")
            logger.info(f"Retrieved: {content_text[:100]}")
            
        # Test 3: List content
        logger.info("Listing content")
        
        # Call the synchronous version of list_content
        list_result = ipfs_model.list_content_sync()
        logger.info(f"List content result: {json.dumps(list_result, indent=2, default=str)}")
        
        if not list_result.get("success", False):
            logger.error("❌ List content operation failed")
            return False
            
        logger.info("✅ List content operation successful")
        
        # Check if our CID is in the list
        items = list_result.get("items", [])
        found = False
        for item in items:
            if item.get("identifier") == cid:
                found = True
                break
                
        if found:
            logger.info("✅ Found our CID in the content list")
        else:
            logger.warning("⚠️ Didn't find our CID in the content list")
            
        # Test 4: Get metadata
        logger.info(f"Getting metadata for CID: {cid}")
        
        # Call the synchronous version of get_metadata
        metadata_result = ipfs_model.get_metadata_sync(cid)
        logger.info(f"Get metadata result: {json.dumps(metadata_result, indent=2, default=str)}")
        
        if not metadata_result.get("success", False):
            logger.error("❌ Get metadata operation failed")
            return False
            
        logger.info("✅ Get metadata operation successful")
        
        # Test 5: Update metadata
        logger.info(f"Updating metadata for CID: {cid}")
        
        test_metadata = {
            "test_key": "test_value",
            "timestamp": time.time(),
            "description": "Test metadata from IPFS integration test"
        }
        
        # Call the synchronous version of update_metadata
        update_result = ipfs_model.update_metadata_sync(cid, test_metadata)
        logger.info(f"Update metadata result: {json.dumps(update_result, indent=2, default=str)}")
        
        if not update_result.get("success", False):
            logger.error("❌ Update metadata operation failed")
            return False
            
        logger.info("✅ Update metadata operation successful")
        
        # Test 6: Delete content
        logger.info(f"Deleting content for CID: {cid}")
        
        # Call the synchronous version of delete_content
        delete_result = ipfs_model.delete_content_sync(cid)
        logger.info(f"Delete content result: {json.dumps(delete_result, indent=2, default=str)}")
        
        if not delete_result.get("success", False):
            logger.error("❌ Delete content operation failed")
            return False
            
        logger.info("✅ Delete content operation successful")
        
        # All tests passed
        logger.info("All IPFS integration tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"Error in IPFS integration test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = run_ipfs_integration_test()
    if success:
        logger.info("✅ IPFS integration test passed!")
        sys.exit(0)
    else:
        logger.error("❌ IPFS integration test failed")
        sys.exit(1)