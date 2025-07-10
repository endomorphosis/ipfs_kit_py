#!/usr/bin/env python3
"""Run only the lotus daemon functionality test."""

import sys
import os
import logging

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
    
    try:
        # Check if lotus_kit can be imported directly
        from ipfs_kit_py.lotus_kit import lotus_kit as lotus_kit_class
        logger.info("✓ Direct lotus_kit import successful")
        
        # Check HAS_LOTUS from ipfs_kit module
        from ipfs_kit_py.ipfs_kit import HAS_LOTUS
        logger.info(f"✓ HAS_LOTUS from ipfs_kit.py: {HAS_LOTUS}")
        
        import ipfs_kit_py
        
        # Create an ipfs_kit instance
        kit = ipfs_kit_py.ipfs_kit()
        logger.info("✓ ipfs_kit instance created")
        
        # Check if lotus_kit is available
        if hasattr(kit, 'lotus_kit'):
            logger.info("✓ lotus_kit is available")
            logger.info(f"✓ lotus_kit type: {type(kit.lotus_kit)}")
            
            # Test basic functionality
            daemon_status = kit.lotus_kit.daemon_status()
            logger.info(f"✓ Daemon status: {daemon_status}")
            
            return True
        else:
            logger.error("✗ lotus_kit not available in ipfs_kit instance")
            logger.error(f"✗ Available attributes: {[attr for attr in dir(kit) if not attr.startswith('_')]}")
            logger.error(f"✗ Kit role: {kit.role}")
            
            # Check if HAS_LOTUS is available at module level
            import ipfs_kit_py.ipfs_kit
            has_lotus_in_module = getattr(ipfs_kit_py.ipfs_kit, 'HAS_LOTUS', 'NOT_FOUND')
            logger.error(f"✗ HAS_LOTUS in ipfs_kit module: {has_lotus_in_module}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error testing lotus daemon functionality: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_lotus_daemon_functionality()
    logger.info(f"Test result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
