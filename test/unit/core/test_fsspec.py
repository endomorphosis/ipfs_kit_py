"""
Simple test script to verify FSSpec integration in high_level_api.py
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    # Import high_level_api
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    
    # Initialize API
    api = IPFSSimpleAPI()
    
    # Try to get filesystem
    logger.info("Testing get_filesystem() method")
    fs = api.get_filesystem()
    
    if fs is None:
        logger.warning("Filesystem is None - likely fsspec is not installed")
    else:
        logger.info(f"Successfully created filesystem: {type(fs).__name__}")
        logger.info(f"Protocol: {fs.protocol}")
        logger.info(f"Role: {fs.role}")
    
    logger.info("Test completed")
except Exception as e:
    logger.error(f"Error during test: {type(e).__name__}: {e}")