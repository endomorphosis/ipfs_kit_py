#!/usr/bin/env python3
"""Run only the lotus daemon functionality test."""

import sys
import os
import logging

import pytest

# Add current directory to path
sys.path.insert(0, os.path.abspath('.'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_lotus_daemon_functionality():
    """Test that lotus daemon can be started and is functional."""
    logger.info("Testing lotus daemon functionality...")

    from ipfs_kit_py.ipfs_kit import HAS_LOTUS
    if not HAS_LOTUS:
        pytest.skip("Lotus support not available in this environment")
    
    try:
        # Check if lotus_kit can be imported directly
        from ipfs_kit_py.lotus_kit import lotus_kit as lotus_kit_class
        logger.info("✓ Direct lotus_kit import successful")
        
        logger.info(f"✓ HAS_LOTUS from ipfs_kit.py: {HAS_LOTUS}")
        
        import ipfs_kit_py
        
        # Create an ipfs_kit instance
        kit_metadata = {
            "auto_download_binaries": False,
            "auto_start_daemons": False,
            "skip_dependency_check": True,
        }
        kit = ipfs_kit_py.ipfs_kit(metadata=kit_metadata, auto_start_daemons=False)
        logger.info("✓ ipfs_kit instance created")
        
        # Check if lotus_kit is available
        if hasattr(kit, 'lotus_kit'):
            logger.info("✓ lotus_kit is available")
            logger.info(f"✓ lotus_kit type: {type(kit.lotus_kit)}")
            
            # Test basic functionality
            assert callable(getattr(kit.lotus_kit, "daemon_status", None))
            try:
                daemon_status = kit.lotus_kit.daemon_status()
                logger.info(f"✓ Daemon status: {daemon_status}")
            except FileNotFoundError as e:
                pytest.skip(f"Lotus binary not available: {e}")
        else:
            logger.error("✗ lotus_kit not available in ipfs_kit instance")
            logger.error(f"✗ Available attributes: {[attr for attr in dir(kit) if not attr.startswith('_')]}")
            logger.error(f"✗ Kit role: {kit.role}")
            
            # Check if HAS_LOTUS is available at module level
            import ipfs_kit_py.ipfs_kit
            has_lotus_in_module = getattr(ipfs_kit_py.ipfs_kit, 'HAS_LOTUS', 'NOT_FOUND')
            logger.error(f"✗ HAS_LOTUS in ipfs_kit module: {has_lotus_in_module}")
            pytest.fail("lotus_kit not available in ipfs_kit instance")
            
    except Exception as e:
        logger.error(f"✗ Error testing lotus daemon functionality: {e}")
        import traceback
        logger.error(traceback.format_exc())
        pytest.fail(f"Error testing lotus daemon functionality: {e}")

if __name__ == "__main__":
    success = test_lotus_daemon_functionality()
    logger.info(f"Test result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
