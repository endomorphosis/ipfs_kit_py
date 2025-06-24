#!/usr/bin/env python3
"""
Simple test script for IPFS Kit Python.

This script verifies the specific fixes we've made without relying on pytest.
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ipfs_kit_tester")

def test_lotus_kit_available():
    """Test that LOTUS_KIT_AVAILABLE is defined and set to True."""
    try:
        from ipfs_kit_py.lotus_kit import LOTUS_KIT_AVAILABLE
        logger.info(f"✅ LOTUS_KIT_AVAILABLE = {LOTUS_KIT_AVAILABLE}")
        assert LOTUS_KIT_AVAILABLE is True, "LOTUS_KIT_AVAILABLE should be True"
        return True
    except Exception as e:
        logger.error(f"❌ Error in test_lotus_kit_available: {e}")
        return False

def test_backend_storage():
    """Test that BackendStorage class exists and has expected methods."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backend_base import BackendStorage

        # Verify it's a class
        assert isinstance(BackendStorage, type), "BackendStorage should be a class"

        # Check for expected methods
        methods = ['store', 'retrieve', 'list_keys', 'delete']
        for method in methods:
            assert hasattr(BackendStorage, method), f"BackendStorage missing '{method}' method"

        logger.info(f"✅ BackendStorage class exists with required methods: {', '.join(methods)}")
        return True
    except Exception as e:
        logger.error(f"❌ Error in test_backend_storage: {e}")
        return False

def test_ipfs_kit_import():
    """Test basic IPFS Kit import."""
    try:
        import ipfs_kit_py
        logger.info(f"✅ Successfully imported ipfs_kit_py (version: {getattr(ipfs_kit_py, '__version__', 'unknown')})")
        return True
    except Exception as e:
        logger.error(f"❌ Error importing ipfs_kit_py: {e}")
        return False

def run_tests():
    """Run all tests and report results."""
    tests = [
        test_lotus_kit_available,
        test_backend_storage,
        test_ipfs_kit_import
    ]

    results = []
    for test in tests:
        try:
            logger.info(f"Running {test.__name__}...")
            result = test()
            results.append(result)
            if result:
                logger.info(f"✅ {test.__name__} - PASSED")
            else:
                logger.error(f"❌ {test.__name__} - FAILED")
        except Exception as e:
            logger.error(f"❌ {test.__name__} - ERROR: {e}")
            results.append(False)

    # Print summary
    passed = sum(1 for r in results if r)
    total = len(results)

    logger.info("\n" + "=" * 50)
    logger.info(f"TEST SUMMARY: {passed}/{total} tests passed")
    logger.info("=" * 50)

    return passed == total

if __name__ == "__main__":
    logger.info("Starting IPFS Kit Python tests...")
    success = run_tests()
    sys.exit(0 if success else 1)
