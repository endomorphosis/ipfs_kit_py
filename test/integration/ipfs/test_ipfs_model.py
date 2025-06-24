#!/usr/bin/env python3
"""Test script for IPFSModel directly"""

import sys
import logging
import time
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_model():
    """Test IPFSModel functionality directly."""
    # Create an isolated model instance
    model = IPFSModel()

    logger.info("Testing IPFSModel...")

    # Test health
    logger.info("Testing connection...")
    model._test_connection()

    # Test add content
    logger.info("Testing add content...")
    test_content = "Hello, IPFS from test script!"
    add_result = model.add_content(test_content, filename="test.txt")
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
            logger.info(f"Retrieved content: {content.decode('utf-8', errors='replace')}")

            # Verify content matches
            if content.decode('utf-8', errors='replace') == test_content:
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
        logger.info(f"Retrieved test content: {content.decode('utf-8', errors='replace')}")
    else:
        logger.error(f"Failed to retrieve test content: {test_get_result.get('error', 'Unknown error')}")

    # Test with a known CID
    known_cid = "QmUA5zkE6wtkWLaH71yaSsqZuJuJefdZE3vnKgEdDh6Rzk"
    logger.info(f"Testing get content for known CID: {known_cid}")
    known_get_result = model.get_content(known_cid)
    logger.info(f"Known get result success: {known_get_result.get('success', False)}")

    if known_get_result.get("success", False) and "data" in known_get_result:
        content = known_get_result["data"]
        logger.info(f"Retrieved known content: {content.decode('utf-8', errors='replace')}")
    else:
        logger.error(f"Failed to retrieve known content: {known_get_result.get('error', 'Unknown error')}")

    # Test list pins
    logger.info("Testing list pins...")
    list_result = model.list_pins()
    logger.info(f"List pins result: {list_result}")

    # Test stats
    logger.info("Getting stats...")
    stats = model.get_stats()
    logger.info(f"Model stats: {stats}")

if __name__ == "__main__":
    test_model()
