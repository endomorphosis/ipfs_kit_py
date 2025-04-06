"""
Simple import test for ipfs_kit_py modules.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Test importing key modules."""
    try:
        logger.info("Importing high_level_api")
        from ipfs_kit_py import high_level_api
        logger.info("high_level_api imported successfully")
        
        logger.info("Importing IPFSSimpleAPI")
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        logger.info("IPFSSimpleAPI imported successfully")
        
        logger.info("All imports successful")
        return True
    except Exception as e:
        logger.error(f"Import error: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    test_imports()