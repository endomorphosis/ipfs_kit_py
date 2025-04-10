#!/usr/bin/env python3
"""Direct test of IPFSModel functionality"""

import sys
import os
import logging
import time
import importlib.util

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Directly import the IPFSModel class without depending on other modules
def get_ipfs_model_class():
    """Import the IPFSModel class directly."""
    model_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/models/ipfs_model.py"
    module_name = "ipfs_model"
    
    spec = importlib.util.spec_from_file_location(module_name, model_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    return module.IPFSModel

def test_model():
    """Test IPFSModel functionality directly."""
    # Get IPFSModel class
    IPFSModel = get_ipfs_model_class()
    
    # Create an isolated model instance
    model = IPFSModel()
    
    logger.info("Testing IPFSModel...")
    
    # Test add content
    logger.info("Testing add content...")
    test_content = "Hello, IPFS from direct test script!"
    add_result = model.add_content(test_content, filename="direct_test.txt")
    logger.info(f"Add result: {add_result}")
    
    # If add was successful, get the CID
    if add_result.get("success", False) and "cid" in add_result:
        cid = add_result["cid"]
        logger.info(f"Added content with CID: {cid}")
        
        # Test get content
        logger.info(f"Testing get content for CID: {cid}")
        get_result = model.get_content(cid)
        logger.info(f"Get result success: {get_result.get('success', False)}")
        
        # Check if data was retrieved
        if get_result.get("success", False) and "data" in get_result:
            content = get_result["data"]
            if isinstance(content, bytes):
                content_str = content.decode('utf-8', errors='replace')
            else:
                content_str = str(content)
                
            logger.info(f"Retrieved content: {content_str}")
            
            # Verify content matches
            if content_str == test_content:
                logger.info("Content verification successful!")
            else:
                logger.warning("Content verification failed - content doesn't match")
        else:
            logger.error(f"Failed to retrieve content: {get_result.get('error', 'Unknown error')}")
    else:
        logger.error(f"Add content failed: {add_result.get('error', 'Unknown error')}")
    
    # Test with QmTest123
    logger.info("Testing get content for test CID: QmTest123")
    test_get_result = model.get_content("QmTest123")
    logger.info(f"Test get result success: {test_get_result.get('success', False)}")
    
    if test_get_result.get("success", False) and "data" in test_get_result:
        content = test_get_result["data"]
        if isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='replace')
        else:
            content_str = str(content)
        logger.info(f"Retrieved test content: {content_str}")
    else:
        logger.error(f"Failed to retrieve test content: {test_get_result.get('error', 'Unknown error')}")
    
    # Test with a known CID
    known_cid = "QmUA5zkE6wtkWLaH71yaSsqZuJuJefdZE3vnKgEdDh6Rzk"
    logger.info(f"Testing get content for known CID: {known_cid}")
    known_get_result = model.get_content(known_cid)
    logger.info(f"Known get result success: {known_get_result.get('success', False)}")
    
    if known_get_result.get("success", False) and "data" in known_get_result:
        content = known_get_result["data"]
        if isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='replace')
        else:
            content_str = str(content)
        logger.info(f"Retrieved known content: {content_str}")
    else:
        logger.error(f"Failed to retrieve known content: {known_get_result.get('error', 'Unknown error')}")
    
    # Test stats
    logger.info("Getting stats...")
    stats = model.get_stats()
    logger.info(f"Model stats: {stats}")

if __name__ == "__main__":
    test_model()