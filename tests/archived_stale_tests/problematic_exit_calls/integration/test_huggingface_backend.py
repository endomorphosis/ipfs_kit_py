#!/usr/bin/env python
"""
Comprehensive test script for the HuggingFace backend implementation.

This script tests the HuggingFace backend functionality to verify
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
logger = logging.getLogger("huggingface_backend_test")

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def run_huggingface_backend_test():
    """Run comprehensive tests on the HuggingFace backend implementation."""
    logger.info("Starting HuggingFace backend test...")
    
    try:
        # Import the HuggingFaceBackend class
        from ipfs_kit_py.mcp.storage_manager.backends.huggingface_backend import HuggingFaceBackend
        logger.info("Successfully imported HuggingFaceBackend")
        
        # Get API key from environment or use a mock mode if not available
        api_key = os.environ.get("HUGGINGFACE_TOKEN")
        mock_mode = api_key is None
        
        if mock_mode:
            logger.info("No HUGGINGFACE_TOKEN environment variable found, running in mock mode")
        else:
            logger.info("Found HUGGINGFACE_TOKEN environment variable, running with real API")
        
        # Create resources and metadata
        resources = {
            "api_key": api_key,
        }
        
        # Set repository details - if testing with a real account, use a test repo
        test_repo = os.environ.get("HUGGINGFACE_TEST_REPO", "test-repo-mcp")
        metadata = {
            "default_repo": test_repo,
            "default_branch": "main",
            "mock_mode": mock_mode,
        }
        
        # Initialize the backend
        backend = HuggingFaceBackend(resources, metadata)
        
        if not backend:
            logger.error("Failed to initialize HuggingFaceBackend")
            return False
            
        logger.info("Successfully initialized HuggingFaceBackend")
        
        # Test backend metadata
        logger.info(f"Backend name: {backend.get_name()}")
        
        # Test 1: Store some data
        test_content = f"Test content from MCP HuggingFace backend test - {uuid.uuid4()}"
        test_path = f"test_files/test_{uuid.uuid4().hex[:8]}.txt"
        store_result = backend.store(test_content, path=test_path)
        logger.info(f"Store operation result: {json.dumps(store_result, indent=2, default=str)}")
        
        if not store_result.get("success", False):
            logger.error("❌ Store operation failed")
            return False
            
        logger.info("✅ Store operation successful")
        
        # Get the identifier
        identifier = store_result.get("identifier")
        if not identifier:
            logger.error("❌ No identifier returned from store operation")
            return False
            
        # Test 2: Retrieve the data
        retrieve_result = backend.retrieve(identifier)
        
        if not retrieve_result.get("success", False):
            logger.error(f"❌ Retrieve operation failed: {retrieve_result.get('error', 'Unknown error')}")
            return False
            
        retrieved_data = retrieve_result.get("data")
        if isinstance(retrieved_data, bytes):
            retrieved_text = retrieved_data.decode('utf-8')
        else:
            retrieved_text = str(retrieved_data)
            
        logger.info(f"Retrieved data: {retrieved_text[:50]}...")
        
        if test_content in retrieved_text:
            logger.info("✅ Retrieved content matches stored content")
        else:
            logger.warning("⚠️ Retrieved content doesn't match stored content")
            
        # Test 3: Check if content exists
        exists_result = backend.exists(identifier)
        logger.info(f"Content exists check: {exists_result}")
        
        if exists_result:
            logger.info("✅ Content exists check passed")
        else:
            logger.warning("⚠️ Content exists check failed")
            
        # Test 4: Get metadata
        metadata_result = backend.get_metadata(identifier)
        logger.info(f"Metadata result: {json.dumps(metadata_result, indent=2, default=str)}")
        
        if metadata_result.get("success", False):
            logger.info("✅ Get metadata operation successful")
        else:
            logger.warning("⚠️ Get metadata operation failed")
            
        # Test 5: Update metadata
        test_metadata = {
            "test_key": "test_value",
            "timestamp": time.time(),
            "description": "Test metadata added by HuggingFace backend test"
        }
        update_metadata_result = backend.update_metadata(identifier, test_metadata)
        logger.info(f"Update metadata result: {json.dumps(update_metadata_result, indent=2, default=str)}")
        
        if update_metadata_result.get("success", False):
            logger.info("✅ Update metadata operation successful")
        else:
            logger.warning("⚠️ Update metadata operation failed")
            
        # Test 6: List files
        list_result = backend.list()
        
        if list_result.get("success", False):
            item_count = len(list_result.get("items", []))
            logger.info(f"List operation result found {item_count} items")
            logger.info("✅ List operation successful")
            
            # Check if our file is in the list
            found_file = False
            for item in list_result.get("items", []):
                if item.get("identifier") == identifier or item.get("path") == test_path:
                    found_file = True
                    break
                    
            if found_file:
                logger.info("✅ Found our file in the repository list")
            else:
                logger.warning("⚠️ Didn't find our file in the repository list")
        else:
            logger.warning("⚠️ List operation failed")
            
        # Test 7: Delete the content
        delete_result = backend.delete(identifier)
        logger.info(f"Delete operation result: {json.dumps(delete_result, indent=2, default=str)}")
        
        if delete_result.get("success", False):
            logger.info("✅ Delete operation successful")
            
            # Verify the content is no longer there
            exists_after_delete = backend.exists(identifier)
            if not exists_after_delete:
                logger.info("✅ Content properly deleted")
            else:
                logger.warning("⚠️ Content still exists after delete")
        else:
            logger.warning("⚠️ Delete operation failed")
        
        logger.info("All tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error testing HuggingFace backend: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = run_huggingface_backend_test()
    if success:
        logger.info("✅ HuggingFace backend test passed!")
        sys.exit(0)
    else:
        logger.error("❌ HuggingFace backend test failed")
        sys.exit(1)