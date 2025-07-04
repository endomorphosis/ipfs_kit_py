#!/usr/bin/env python3
"""Debug script to understand lotus_kit availability in test environment."""

import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add current directory to path
sys.path.insert(0, os.path.abspath('.'))

def debug_lotus_kit():
    """Debug lotus_kit availability step by step."""
    logger.info("=== Starting lotus_kit debug ===")
    
    try:
        # Test 1: Direct import of lotus_kit
        logger.info("1. Testing direct lotus_kit import...")
        from ipfs_kit_py.lotus_kit import lotus_kit
        logger.info("✓ Direct lotus_kit import successful")
        
        # Test 2: Check ipfs_kit.py module HAS_LOTUS
        logger.info("2. Checking HAS_LOTUS from ipfs_kit.py...")
        from ipfs_kit_py.ipfs_kit import HAS_LOTUS
        logger.info(f"✓ HAS_LOTUS from ipfs_kit.py: {HAS_LOTUS}")
        
        # Test 3: Create ipfs_kit instance
        logger.info("3. Creating ipfs_kit instance...")
        import ipfs_kit_py
        kit = ipfs_kit_py.ipfs_kit()
        logger.info("✓ ipfs_kit instance created")
        
        # Test 4: Check if lotus_kit is available
        logger.info("4. Checking lotus_kit availability...")
        has_lotus_kit = hasattr(kit, 'lotus_kit')
        logger.info(f"✓ Has lotus_kit attribute: {has_lotus_kit}")
        
        if has_lotus_kit:
            logger.info(f"✓ lotus_kit type: {type(kit.lotus_kit)}")
        else:
            logger.error("✗ lotus_kit NOT available")
            logger.error(f"Available attributes: {[attr for attr in dir(kit) if not attr.startswith('_')]}")
            
            # Test 5: Check what went wrong during initialization
            logger.info("5. Debugging initialization...")
            logger.info(f"  Role: {kit.role}")
            logger.info(f"  Metadata: {kit.metadata}")
            
            # Re-import to check HAS_LOTUS again
            import ipfs_kit_py.ipfs_kit
            logger.info(f"  HAS_LOTUS in module: {getattr(ipfs_kit_py.ipfs_kit, 'HAS_LOTUS', 'NOT_FOUND')}")
            
        return has_lotus_kit
        
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_lotus_kit()
    logger.info(f"=== Debug complete. Success: {success} ===")
    sys.exit(0 if success else 1)
