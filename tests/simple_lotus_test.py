#!/usr/bin/env python3
"""Simple test to verify lotus_kit is available."""

import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add current directory to path
sys.path.insert(0, os.path.abspath('.'))

def main():
    """Test lotus_kit availability."""
    logger.info("Testing lotus_kit availability...")
    
    try:
        import ipfs_kit_py
        logger.info("✓ Successfully imported ipfs_kit_py")
        
        # Create instance
        kit = ipfs_kit_py.ipfs_kit()
        logger.info("✓ Successfully created ipfs_kit instance")
        
        # Check if lotus_kit exists
        has_lotus_kit = hasattr(kit, 'lotus_kit')
        logger.info(f"✓ lotus_kit available: {has_lotus_kit}")
        
        if has_lotus_kit:
            logger.info(f"✓ lotus_kit type: {type(kit.lotus_kit)}")
            logger.info("✓ TEST PASSED - lotus_kit is available")
            return True
        else:
            logger.error("✗ TEST FAILED - lotus_kit is NOT available")
            return False
            
    except Exception as e:
        logger.error(f"✗ TEST FAILED with exception: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
