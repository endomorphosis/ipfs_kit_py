#!/usr/bin/env python3
"""
Test script for IPFS Model methods in the MCP server.

This script tests the newly added methods in the IPFSModel class:
- get_content
- add_content
- pin_content

These methods are required for the Storacha integration.
"""

import json
import sys
import time
import logging
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_add_content():
    """Test the add_content method."""
    logger.info("Testing add_content method...")
    
    # Create an IPFS Kit instance with explicit parameters
    kit = ipfs_kit(auto_start_daemons=True)
    
    # Verify kit initialization
    daemon_status = kit.check_daemon_status()
    logger.info(f"IPFS daemon status: {daemon_status}")
    
    # Create an IPFS Model instance
    model = IPFSModel(ipfs_kit_instance=kit)
    
    # Test content
    test_content = b"Test content for IPFS Model add_content method"
    
    # Add content
    result = model.add_content(test_content)
    
    # Print result
    logger.info(f"add_content result: {json.dumps(result, indent=2, default=str)}")
    
    # Return CID for further testing
    return result.get("cid") if result.get("success", False) else None

def test_get_content(cid):
    """Test the get_content method."""
    logger.info(f"Testing get_content method with CID: {cid}...")
    
    # Create an IPFS Kit instance with explicit parameters
    kit = ipfs_kit(auto_start_daemons=True)
    
    # Verify kit initialization
    daemon_status = kit.check_daemon_status()
    logger.info(f"IPFS daemon status: {daemon_status}")
    
    # Create an IPFS Model instance
    model = IPFSModel(ipfs_kit_instance=kit)
    
    # Get content
    result = model.get_content(cid)
    
    # Print result
    logger.info(f"get_content result: {json.dumps(result, indent=2, default=str)}")
    
    # Verify content
    if result.get("success", False):
        data = result.get("data")
        if isinstance(data, bytes):
            logger.info(f"Retrieved content: {data.decode('utf-8')}")
        else:
            logger.info(f"Retrieved content: {data}")
    
    return result.get("success", False)

def test_pin_content(cid):
    """Test the pin_content method."""
    logger.info(f"Testing pin_content method with CID: {cid}...")
    
    # Create an IPFS Kit instance with explicit parameters
    kit = ipfs_kit(auto_start_daemons=True)
    
    # Verify kit initialization
    daemon_status = kit.check_daemon_status()
    logger.info(f"IPFS daemon status: {daemon_status}")
    
    # Create an IPFS Model instance
    model = IPFSModel(ipfs_kit_instance=kit)
    
    # Pin content
    result = model.pin_content(cid)
    
    # Print result
    logger.info(f"pin_content result: {json.dumps(result, indent=2, default=str)}")
    
    return result.get("success", False)

def main():
    """Run the tests."""
    logger.info("Starting IPFS Model methods test")
    
    try:
        # Test add_content
        cid = test_add_content()
        if not cid:
            logger.error("Failed to add content - cannot continue tests")
            return 1
        
        # Test get_content
        if not test_get_content(cid):
            logger.error("Failed to get content")
            return 1
        
        # Test pin_content
        if not test_pin_content(cid):
            logger.error("Failed to pin content")
            return 1
        
        logger.info("All tests passed successfully!")
        return 0
        
    except Exception as e:
        logger.exception(f"Test failed with error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())