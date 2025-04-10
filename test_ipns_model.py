#!/usr/bin/env python3
"""
Test script for verifying IPNS functionality in the IPFSModel.

This script tests:
1. The IPNS publish functionality (name_publish)
2. The IPNS resolve functionality (name_resolve)
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure ipfs_kit_py is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the model directly to test IPNS methods
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel

def test_name_publish():
    """Test IPNS publishing via the model directly."""
    logger.info("Testing IPNS publishing via the model...")
    
    # Create model instance
    model = IPFSModel()
    
    # Add some content first
    test_content = b"Test content for IPNS publish"
    result = model.add_content(test_content)
    if not result.get("success", False):
        logger.error(f"Failed to add content: {result}")
        return False
    
    cid = result.get("cid", result.get("Hash", None))
    logger.info(f"Added content with CID: {cid}")
    
    # Publish to IPNS
    publish_result = model.name_publish(cid)
    logger.info(f"IPNS publish result: {publish_result}")
    
    if not publish_result.get("success", False):
        logger.error(f"Failed to publish to IPNS: {publish_result}")
        return False
    
    # Check the result for expected fields
    ipns_name = publish_result.get("name")
    value = publish_result.get("value")
    
    logger.info(f"Published {cid} to IPNS name: {ipns_name} with value: {value}")
    
    # Verify fields
    if not ipns_name or not value:
        logger.error("Missing required fields in publish result")
        return False
    
    if not value.endswith(cid):
        logger.warning(f"Value {value} does not end with CID {cid}")
    
    return ipns_name

def test_name_resolve(ipns_name):
    """Test IPNS resolution via the model directly."""
    logger.info(f"Testing IPNS resolution via the model for name: {ipns_name}...")
    
    # Create model instance
    model = IPFSModel()
    
    # Resolve IPNS name
    resolve_result = model.name_resolve(ipns_name)
    logger.info(f"IPNS resolve result: {resolve_result}")
    
    if not resolve_result.get("success", False):
        logger.error(f"Failed to resolve IPNS name: {resolve_result}")
        return False
    
    # Check the result for expected fields
    resolved_path = resolve_result.get("path")
    
    logger.info(f"Resolved IPNS name {ipns_name} to path: {resolved_path}")
    
    # Verify field
    if not resolved_path:
        logger.error("Missing required field 'path' in resolve result")
        return False
    
    if not resolved_path.startswith("/ipfs/"):
        logger.error(f"Resolved path {resolved_path} does not start with /ipfs/")
        return False
    
    return True

def run_tests():
    """Run all IPNS tests and report results."""
    results = {}
    
    # Test publish method
    logger.info("\n=== Testing name_publish Method ===")
    ipns_name = test_name_publish()
    if ipns_name:
        results["publish"] = True
        
        # Test resolve method
        logger.info("\n=== Testing name_resolve Method ===")
        results["resolve"] = test_name_resolve(ipns_name)
    else:
        results["publish"] = False
        results["resolve"] = False
    
    # Report results
    logger.info("\n=== IPNS Testing Results ===")
    for test, result in results.items():
        logger.info(f"{test}: {'PASS' if result else 'FAIL'}")
    
    return all(results.values())

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)