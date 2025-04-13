#!/usr/bin/env python3
"""
Comprehensive test for the libp2p controller and model with anyio integration.

This script tests various aspects of the LibP2PController and LibP2PModel
to verify that the anyio-based implementation works correctly, handling both
synchronous and asynchronous methods appropriately.
"""

import logging
import os
import json
import anyio
import sys
import tempfile
from typing import Dict, Any, List

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the controller and model classes
from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel

class TestResults:
    """Simple class to track test results."""
    def __init__(self):
        self.passed = []
        self.failed = []
        
    def add_pass(self, test_name):
        """Add a passing test."""
        self.passed.append(test_name)
        logger.info(f"✅ PASS: {test_name}")
        
    def add_fail(self, test_name, error):
        """Add a failing test."""
        self.failed.append((test_name, error))
        logger.error(f"❌ FAIL: {test_name} - {error}")
        
    def summary(self):
        """Get a summary of test results."""
        total = len(self.passed) + len(self.failed)
        return {
            "total": total,
            "passed": len(self.passed),
            "failed": len(self.failed),
            "pass_rate": f"{len(self.passed) / total * 100:.1f}%" if total > 0 else "N/A",
            "passing_tests": self.passed,
            "failing_tests": [f"{name}: {error}" for name, error in self.failed]
        }

async def test_health_check(controller, results):
    """Test the health check endpoint."""
    test_name = "health_check"
    
    try:
        # Call the health check method
        result = await controller.health_check()
        
        # Verify response format
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "success" in result, "Result should have 'success' field"
        assert "libp2p_available" in result, "Result should have 'libp2p_available' field"
        assert "peer_initialized" in result, "Result should have 'peer_initialized' field"
        
        # Note: We don't check the actual values since they depend on libp2p availability
        
        # Test passed
        results.add_pass(test_name)
        return result
    except Exception as e:
        results.add_fail(test_name, str(e))
        return None

async def test_is_available(model, results):
    """Test the is_available method."""
    test_name = "is_available"
    
    try:
        # Call the async is_available method
        result = await model.is_available()
        
        # Verify result format
        assert isinstance(result, bool), "Result should be a boolean"
        
        # Test passed
        results.add_pass(test_name)
        return result
    except Exception as e:
        results.add_fail(test_name, str(e))
        return None

async def test_controller_initialization(model, results):
    """Test controller initialization with model."""
    test_name = "controller_initialization"
    
    try:
        # Create controller with the model
        controller = LibP2PController(model)
        
        # Verify controller attributes
        assert controller.libp2p_model == model, "Controller should store the model instance"
        assert hasattr(controller, "initialized_endpoints"), "Controller should have initialized_endpoints attribute"
        assert isinstance(controller.initialized_endpoints, set), "initialized_endpoints should be a set"
        
        # Test passed
        results.add_pass(test_name)
        return controller
    except Exception as e:
        results.add_fail(test_name, str(e))
        return None

async def test_get_health_async(model, results):
    """Test the get_health_async method."""
    test_name = "get_health_async"
    
    # Skip if the model doesn't have the method
    if not hasattr(model, 'get_health_async'):
        logger.warning(f"SKIP: {test_name} - Method not available")
        return None
    
    try:
        # Call the get_health_async method
        result = await model.get_health_async()
        
        # Verify result format
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "success" in result, "Result should have 'success' field"
        assert "operation" in result, "Result should have 'operation' field"
        assert "timestamp" in result, "Result should have 'timestamp' field"
        
        # Test passed
        results.add_pass(test_name)
        return result
    except Exception as e:
        results.add_fail(test_name, str(e))
        return None

async def test_shutdown(controller, results):
    """Test the shutdown method."""
    test_name = "shutdown"
    
    try:
        # Call the shutdown method
        await controller.shutdown()
        
        # Verify shutdown flag
        assert controller.is_shutting_down, "is_shutting_down flag should be True after shutdown"
        
        # Test passed
        results.add_pass(test_name)
        return True
    except Exception as e:
        results.add_fail(test_name, str(e))
        return False

async def run_all_tests():
    """Run all tests for the libp2p controller and model."""
    logger.info("Starting comprehensive libp2p tests")
    
    # Initialize test results tracker
    results = TestResults()
    
    # Create model instance with configuration to avoid actual peer startup
    logger.info("Creating LibP2PModel instance")
    # Create a temporary directory for test identity
    temp_dir = tempfile.mkdtemp(prefix="ipfs_test_")
    identity_path = os.path.join(temp_dir, "test_identity.key")
    model = LibP2PModel(
        metadata={
            "auto_start": False,  # Don't start the peer
            "auto_install_dependencies": False,  # Don't attempt to install dependencies
            "identity_path": identity_path,
            "test_mode": True  # Enable test mode for mock behavior
        }
    )
    
    # Test model methods
    await test_is_available(model, results)
    await test_get_health_async(model, results)
    
    # Test controller initialization
    controller = await test_controller_initialization(model, results)
    if controller:
        # Test controller methods
        await test_health_check(controller, results)
        await test_shutdown(controller, results)
    
    # Get test summary
    summary = results.summary()
    logger.info(f"Tests completed: {summary['passed']} passed, {summary['failed']} failed")
    
    return summary

def main():
    """Main entry point for running the tests."""
    logger.info("Starting comprehensive test for libp2p with anyio")
    
    # Run with anyio to be backend-agnostic (will work with both asyncio and trio)
    summary = anyio.run(run_all_tests)
    
    # Print final summary
    print("\n" + "="*50)
    print("TEST SUMMARY:")
    print(f"Total tests: {summary['total']}")
    print(f"Passing: {summary['passed']} ({summary['pass_rate']})")
    print(f"Failing: {summary['failed']}")
    
    if summary['failing_tests']:
        print("\nFailing tests:")
        for test in summary['failing_tests']:
            print(f"  - {test}")
    
    print("="*50)
    
    # Exit with appropriate status code
    sys.exit(0 if summary['failed'] == 0 else 1)

if __name__ == "__main__":
    main()