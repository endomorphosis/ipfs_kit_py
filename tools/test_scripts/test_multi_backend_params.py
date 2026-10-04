#!/usr/bin/env python3
"""
Test Multi-Backend Parameter Handling

This script tests the multi-backend filesystem tools with various parameter naming
conventions to verify that the enhanced parameter handling is working correctly.
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("multi_backend_test.log")
    ]
)
logger = logging.getLogger(__name__)

# Path to test data
TEST_DATA_DIR = Path(os.path.expanduser("~/ipfs_test_data"))
os.makedirs(TEST_DATA_DIR, exist_ok=True)

class ToolContext:
    """Mock tool context for testing"""
    
    def __init__(self, arguments):
        self.arguments = arguments
    
    async def info(self, message):
        logger.info(message)
    
    async def warning(self, message):
        logger.warning(message)
    
    async def error(self, message):
        logger.error(message)


async def test_backend_registration_parameters():
    """Test backend registration with various parameter namings"""
    logger.info("===== Testing Backend Registration Parameters =====")
    
    from enhanced.multi_backend_tool_adapters import handle_mbfs_register_backend
    
    # Test with standard parameter names
    standard_ctx = ToolContext({
        "backend_id": "test-ipfs",
        "backend_type": "ipfs",
        "config": {
            "api_url": "/ip4/127.0.0.1/tcp/5001",
            "gateway_url": "https://ipfs.io/ipfs/"
        },
        "make_default": True
    })
    
    result1 = await handle_mbfs_register_backend(standard_ctx)
    logger.info(f"Standard parameters result: {json.dumps(result1, indent=2)}")
    
    # Test with alternative parameter names
    alt_ctx = ToolContext({
        "name": "test-ipfs-alt",
        "type": "ipfs",
        "config": {
            "api_url": "/ip4/127.0.0.1/tcp/5001",
            "gateway_url": "https://ipfs.io/ipfs/"
        }
    })
    
    result2 = await handle_mbfs_register_backend(alt_ctx)
    logger.info(f"Alternative parameters result: {json.dumps(result2, indent=2)}")
    
    # Test with mix of parameter names
    mix_ctx = ToolContext({
        "id": "test-ipfs-mix",
        "backend_type": "ipfs",
        "config": {
            "api_url": "/ip4/127.0.0.1/tcp/5001",
            "gateway_url": "https://ipfs.io/ipfs/"
        }
    })
    
    result3 = await handle_mbfs_register_backend(mix_ctx)
    logger.info(f"Mixed parameters result: {json.dumps(result3, indent=2)}")
    
    return result1["success"] and result2["success"] and result3["success"]


async def test_store_parameters():
    """Test content storage with various parameter namings"""
    logger.info("===== Testing Content Storage Parameters =====")
    
    from enhanced.multi_backend_tool_adapters import handle_mbfs_store
    
    # Create test content
    test_content = "This is test content for multi-backend parameter tests"
    
    # Test with standard parameter names
    standard_ctx = ToolContext({
        "content": test_content,
        "path": "test-file.txt",
        "backend_id": "test-ipfs",
        "metadata": {
            "content_type": "text/plain",
            "description": "Test file"
        }
    })
    
    result1 = await handle_mbfs_store(standard_ctx)
    logger.info(f"Standard parameters result: {json.dumps(result1, indent=2)}")
    
    # Test with alternative parameter names
    alt_ctx = ToolContext({
        "data": test_content,
        "file_path": "test-file-alt.txt",
        "backend": "test-ipfs",
        "metadata": {
            "content_type": "text/plain",
            "description": "Test file (alt params)"
        }
    })
    
    result2 = await handle_mbfs_store(alt_ctx)
    logger.info(f"Alternative parameters result: {json.dumps(result2, indent=2)}")
    
    # Test with mix of parameter names
    mix_ctx = ToolContext({
        "text": test_content,
        "filepath": "test-file-mix.txt",
        "id": "test-ipfs",
        "metadata": {
            "content_type": "text/plain",
            "description": "Test file (mixed params)"
        }
    })
    
    result3 = await handle_mbfs_store(mix_ctx)
    logger.info(f"Mixed parameters result: {json.dumps(result3, indent=2)}")
    
    return result1["success"] and result2["success"] and result3["success"]


async def test_retrieve_parameters():
    """Test content retrieval with various parameter namings"""
    logger.info("===== Testing Content Retrieval Parameters =====")
    
    from enhanced.multi_backend_tool_adapters import handle_mbfs_retrieve
    
    # Store a test file first to get an identifier
    await test_store_parameters()
    
    # Get the latest backend info to find a valid identifier
    from multi_backend_fs_integration import get_backend_manager
    backend_manager = get_backend_manager()
    backends = backend_manager.get_backends()
    ipfs_backend = backends.get("test-ipfs")
    
    if not ipfs_backend:
        logger.error("IPFS backend not found")
        return False
    
    # List files to get an identifier
    list_result = await backend_manager.list("", "test-ipfs")
    logger.info(f"Available files: {json.dumps(list_result, indent=2)}")
    
    # Extract a valid identifier
    if not list_result["success"] or not list_result.get("items"):
        logger.error("No items found in backend")
        return False
    
    identifier = list_result["items"][0]["identifier"]
    
    # Test with standard parameter names
    standard_ctx = ToolContext({
        "identifier": identifier,
        "backend_id": "test-ipfs"
    })
    
    result1 = await handle_mbfs_retrieve(standard_ctx)
    logger.info(f"Standard parameters result: {json.dumps(result1, indent=2)}")
    
    # Test with alternative parameter names
    alt_ctx = ToolContext({
        "id": identifier,
        "backend": "test-ipfs"
    })
    
    result2 = await handle_mbfs_retrieve(alt_ctx)
    logger.info(f"Alternative parameters result: {json.dumps(result2, indent=2)}")
    
    # Test with mix of parameter names
    mix_ctx = ToolContext({
        "cid": identifier,
        "backend_id": "test-ipfs"
    })
    
    result3 = await handle_mbfs_retrieve(alt_ctx)
    logger.info(f"Mixed parameters result: {json.dumps(result3, indent=2)}")
    
    return result1["success"] and result2["success"] and result3["success"]


async def run_all_tests():
    """Run all parameter tests"""
    try:
        logger.info("Starting multi-backend parameter tests...")
        
        # Run tests
        backend_test = await test_backend_registration_parameters()
        store_test = await test_store_parameters()
        retrieve_test = await test_retrieve_parameters()
        
        # Report results
        logger.info("===== Test Results =====")
        logger.info(f"Backend Registration: {'✅ PASSED' if backend_test else '❌ FAILED'}")
        logger.info(f"Content Storage: {'✅ PASSED' if store_test else '❌ FAILED'}")
        logger.info(f"Content Retrieval: {'✅ PASSED' if retrieve_test else '❌ FAILED'}")
        
        all_passed = backend_test and store_test and retrieve_test
        logger.info(f"Overall Result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
        
        return all_passed
    
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    # Run all tests
    asyncio.run(run_all_tests())
