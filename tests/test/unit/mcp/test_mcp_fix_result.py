#!/usr/bin/env python3

"""
Test script for verifying the fix to the IPFS model's get_content method.

This test focuses on properly handling both raw bytes and dictionary responses
from the underlying IPFS implementation's cat method. It specifically checks that
the operation field is correctly set to "get_content" in both cases.
"""

import unittest
import tempfile
import shutil
import os
import json
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class TestMCPFix(unittest.TestCase):
    """Test case for MCP fix to get_content."""
    
    def setUp(self):
        """Set up test environment with mock IPFS instances."""
        # Import MCP components
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
        from ipfs_kit_py.mcp.persistence.cache_manager import MCPCacheManager
        
        # Create a temporary directory for cache
        self.temp_dir = tempfile.mkdtemp()
        
        # Create cache manager
        self.cache_manager = MCPCacheManager(
            base_path=self.temp_dir,
            memory_limit=10 * 1024 * 1024,  # 10MB
            disk_limit=20 * 1024 * 1024     # 20MB
        )
        
        # Create IPFS mock that returns bytes response
        class MockBytesIPFS:
            """Mock IPFS implementation that returns bytes from cat method."""
            def cat(self, cid):
                """Return bytes for the provided CID."""
                return f"Test content for {cid}".encode("utf-8")
            
            # Implement ipfs_cat for compatibility with both implementations
            def ipfs_cat(self, cid):
                """Return bytes for the provided CID."""
                return self.cat(cid)
        
        # Create IPFS mock that returns dictionary response
        class MockDictIPFS:
            """Mock IPFS implementation that returns dictionary from cat method."""
            def cat(self, cid):
                """Return dictionary for the provided CID."""
                return {
                    "success": True,
                    "operation": "cat",
                    "data": f"Test content for {cid}".encode("utf-8"),
                    "simulated": False
                }
            
            # Implement ipfs_cat for compatibility with both implementations
            def ipfs_cat(self, cid):
                """Return dictionary for the provided CID."""
                return self.cat(cid)
        
        # Create IPFS model instances with different mock implementations
        self.bytes_model = IPFSModel(MockBytesIPFS(), self.cache_manager)
        self.dict_model = IPFSModel(MockDictIPFS(), self.cache_manager)
        
        # Create controllers with these models
        self.bytes_controller = IPFSController(self.bytes_model)
        self.dict_controller = IPFSController(self.dict_model)
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_bytes_response_handling(self):
        """Test handling of raw bytes response from IPFS cat."""
        logger.info("Testing bytes response handling...")
        result = self.bytes_model.get_content("QmTestBytes")
        
        # Verify result structure
        self.assertTrue(result.get("success", False), "Result should have success=True")
        self.assertEqual(result.get("operation"), "get_content", "Operation should be 'get_content', not 'cat'")
        self.assertEqual(result.get("data"), b"Test content for QmTestBytes", "Content should match")
        
        logger.info("✅ Bytes response handling test passed")
    
    def test_dict_response_handling(self):
        """Test handling of dictionary response from IPFS cat."""
        logger.info("Testing dictionary response handling...")
        result = self.dict_model.get_content("QmTestDict")
        
        # Verify result structure
        self.assertTrue(result.get("success", False), "Result should have success=True")
        self.assertEqual(result.get("operation"), "get_content", "Operation should be 'get_content', not 'cat'")
        self.assertEqual(result.get("data"), b"Test content for QmTestDict", "Content should match")
        
        logger.info("✅ Dictionary response handling test passed")
    
    def test_controller_bytes_response(self):
        """Test controller handling of bytes response from model."""
        logger.info("Testing controller with bytes model...")
        
        # Get controller's model and test it directly
        model = self.bytes_controller.ipfs_model
        result = model.get_content("QmTestControllerBytes")
        
        # Verify response
        self.assertTrue(result.get("success", False), "Response should have success=True")
        self.assertEqual(result.get("operation"), "get_content", "Operation should be 'get_content', not 'cat'")
        self.assertTrue("data" in result, "Response should include data field")
        
        logger.info("✅ Controller with bytes model test passed")
    
    def test_controller_dict_response(self):
        """Test controller handling of dictionary response from model."""
        logger.info("Testing controller with dictionary model...")
        
        # Get controller's model and test it directly
        model = self.dict_controller.ipfs_model
        result = model.get_content("QmTestControllerDict")
        
        # Verify response
        self.assertTrue(result.get("success", False), "Response should have success=True")
        self.assertEqual(result.get("operation"), "get_content", "Operation should be 'get_content', not 'cat'")
        self.assertTrue("data" in result, "Response should include data field")
        
        logger.info("✅ Controller with dictionary model test passed")
    
    def test_error_handling(self):
        """Test error handling in get_content method."""
        logger.info("Testing error handling in get_content...")
        
        # Create a model with a mock that raises an exception
        class ErrorMockIPFS:
            def cat(self, cid):
                """Raise an exception for testing error handling."""
                raise ValueError("Simulated error for testing")
            
            # Implement ipfs_cat for compatibility with both implementations
            def ipfs_cat(self, cid):
                """Raise an exception for testing error handling."""
                return self.cat(cid)
        
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        error_model = IPFSModel(ErrorMockIPFS(), self.cache_manager)
        
        # Test the model with error handling
        result = error_model.get_content("QmTestError")
        
        # Verify error result
        self.assertFalse(result.get("success", True), "Error result should have success=False")
        self.assertEqual(result.get("operation"), "get_content", "Operation should be 'get_content', not 'cat'")
        self.assertIn("error", result, "Error result should include error field")
        self.assertIn("Simulated error", result.get("error", ""), "Error message should be included")
        
        logger.info("✅ Error handling test passed")
    
    def test_cache_interaction(self):
        """Test caching functionality with get_content method."""
        logger.info("Testing cache interaction...")
        
        # First access (uncached)
        result1 = self.bytes_model.get_content("QmTestCache")
        self.assertFalse(result1.get("cache_hit", True), "First access should not be a cache hit")
        
        # Second access (should be cached)
        result2 = self.bytes_model.get_content("QmTestCache")
        self.assertTrue(result2.get("cache_hit", False), "Second access should be a cache hit")
        self.assertEqual(result2.get("operation"), "get_content", "Operation should be 'get_content', not 'cat'")
        
        logger.info("✅ Cache interaction test passed")
    
    def run_all_tests(self):
        """Run all tests and return results."""
        tests = [
            self.test_bytes_response_handling,
            self.test_dict_response_handling,
            self.test_controller_bytes_response,
            self.test_controller_dict_response,
            self.test_error_handling,
            self.test_cache_interaction
        ]
        
        results = []
        for test in tests:
            try:
                test()
                results.append({"test": test.__name__, "success": True})
            except Exception as e:
                results.append({"test": test.__name__, "success": False, "error": str(e)})
                
        return results

def main():
    """Run all tests with proper setup and teardown."""
    # Initialize the test case
    test_case = TestMCPFix()
    
    try:
        # Setup
        test_case.setUp()
        
        # Run all tests
        logger.info("Running all MCP fix tests...")
        results = test_case.run_all_tests()
        
        # Log results
        succeeded = sum(1 for r in results if r["success"])
        failed = sum(1 for r in results if not r["success"])
        
        if failed > 0:
            logger.error(f"❌ Tests completed with {succeeded} passed, {failed} failed")
            for result in results:
                if not result["success"]:
                    logger.error(f"  - {result['test']}: FAILED ({result['error']})")
            return 1
        else:
            logger.info(f"✅ All {len(results)} tests passed!")
            return 0
    finally:
        # Ensure teardown happens
        test_case.tearDown()

if __name__ == "__main__":
    import sys
    sys.exit(main())
