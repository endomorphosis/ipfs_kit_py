#!/usr/bin/env python3
"""
Test script for Synapse SDK virtual filesystem integration.
"""

import os
import sys
import asyncio
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_synapse_integration():
    """Test Synapse SDK integration with virtual filesystem."""
    logger.info("Testing Synapse SDK integration...")
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Import Synapse storage
    total_tests += 1
    try:
        from ipfs_kit_py.synapse_storage import synapse_storage
        logger.info("✓ Test 1: Synapse storage import successful")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ Test 1: Synapse storage import failed: {e}")
    
    # Test 2: Import Synapse configuration
    total_tests += 1
    try:
        from ipfs_kit_py.config_synapse_sdk import config_synapse_sdk
        logger.info("✓ Test 2: Synapse configuration import successful")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ Test 2: Synapse configuration import failed: {e}")
    
    # Test 3: Test FSSpec integration
    total_tests += 1
    try:
        from ipfs_kit_py.enhanced_fsspec import IPFSFileSystem
        fs = IPFSFileSystem(backend="synapse")
        logger.info("✓ Test 3: Synapse FSSpec backend initialization successful")
        tests_passed += 1
    except Exception as e:
        logger.error(f"✗ Test 3: Synapse FSSpec backend initialization failed: {e}")
    
    # Test 4: Test IPFS Kit integration
    total_tests += 1
    try:
        from ipfs_kit_py.ipfs_kit import ipfs_kit
        kit = ipfs_kit(metadata={"role": "leecher"})
        if hasattr(kit, 'synapse_storage'):
            logger.info("✓ Test 4: IPFS Kit Synapse integration successful")
            tests_passed += 1
        else:
            logger.error("✗ Test 4: IPFS Kit missing synapse_storage attribute")
    except Exception as e:
        logger.error(f"✗ Test 4: IPFS Kit integration failed: {e}")
    
    # Test 5: Test configuration files
    total_tests += 1
    try:
        config_file = os.path.join(project_root, "config", "synapse_config.yaml")
        if os.path.exists(config_file):
            logger.info("✓ Test 5: Synapse configuration file exists")
            tests_passed += 1
        else:
            logger.error("✗ Test 5: Synapse configuration file not found")
    except Exception as e:
        logger.error(f"✗ Test 5: Configuration file check failed: {e}")
    
    # Summary
    logger.info(f"\nIntegration test completed: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        logger.info("🎉 All tests passed! Synapse SDK integration is ready.")
        return True
    else:
        logger.warning(f"⚠ {total_tests - tests_passed} tests failed. Check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_synapse_integration())
    sys.exit(0 if success else 1)
