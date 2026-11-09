#!/usr/bin/env python3
"""
Simple verification script to test our fixes without using pytest.
"""
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_fixes")

def test_lotus_kit_available():
    """Verify that LOTUS_KIT_AVAILABLE is properly set in lotus_kit."""
    try:
        from ipfs_kit_py.lotus_kit import LOTUS_KIT_AVAILABLE
        logger.info(f"LOTUS_KIT_AVAILABLE = {LOTUS_KIT_AVAILABLE}")
        return True
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to import LOTUS_KIT_AVAILABLE: {e}")
        return False

def test_backend_storage():
    """Verify that BackendStorage is properly available."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backend_base import BackendStorage
        logger.info("Successfully imported BackendStorage")
        return True
    except ImportError as e:
        logger.error(f"Failed to import BackendStorage: {e}")
        return False

def verify_all_fixes():
    """Run all verification tests."""
    results = {
        "lotus_kit_available": test_lotus_kit_available(),
        "backend_storage": test_backend_storage()
    }
    
    # Print summary
    logger.info("\n=== VERIFICATION RESULTS ===")
    for test_name, result in results.items():
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
    
    # Calculate overall success
    success_count = sum(1 for result in results.values() if result)
    total_count = len(results)
    logger.info(f"\nPassed {success_count}/{total_count} tests")
    
    return success_count == total_count

if __name__ == "__main__":
    logger.info("Starting verification of fixes...")
    success = verify_all_fixes()
    sys.exit(0 if success else 1)