#!/usr/bin/env python3
"""
Direct test for the libp2p controller and model to verify implementation.

This script tests the LibP2PController directly without going through HTTP
to verify the anyio-based implementation is working properly.
"""

import logging
import asyncio
import anyio
import sys
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the controller and model classes
from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel

async def test_health_check():
    """Test the health check endpoint directly."""
    logger.info("Creating LibP2PModel instance")
    model = LibP2PModel(metadata={"auto_start": False})  # Avoid starting the peer for faster testing
    
    logger.info("Creating LibP2PController instance")
    controller = LibP2PController(model)
    
    logger.info("Calling health_check method directly")
    try:
        result = await controller.health_check()
        logger.info(f"Health check result: {result}")
        
        # Verify that the result has the expected format
        assert isinstance(result, dict)
        assert "success" in result
        assert "libp2p_available" in result
        assert "peer_initialized" in result
        logger.info("Health check response validation successful")
        
        return result
    except Exception as e:
        logger.error(f"Error testing health check: {e}")
        raise

async def run_all_tests():
    """Run all tests for the libp2p controller."""
    logger.info("Starting libp2p controller direct tests")
    
    # Test health check
    health_result = await test_health_check()
    logger.info(f"Health check test completed: {health_result['success']}")
    
    # Add more tests for other controller methods as needed
    
    logger.info("All tests completed")
    return health_result

def main():
    """Main entry point for running the tests."""
    logger.info("Starting direct test for libp2p controller")
    
    # Run with anyio to be backend-agnostic (will work with both asyncio and trio)
    result = anyio.run(run_all_tests)
    
    # Print final result
    print("\n" + "="*50)
    print("TEST RESULTS:")
    print(f"Success: {result['success']}")
    print(f"libp2p_available: {result['libp2p_available']}")
    print(f"peer_initialized: {result['peer_initialized']}")
    if result.get('error'):
        print(f"Error: {result['error']}")
    print("="*50)
    
    # Exit with appropriate status code
    sys.exit(0 if result['success'] else 1)

if __name__ == "__main__":
    main()