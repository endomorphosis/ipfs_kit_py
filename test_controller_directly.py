#!/usr/bin/env python3
"""Test daemon status functionality for IPFS cluster daemons."""
import os
import sys
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ipfs_cluster_service_status():
    """Test the status functionality for IPFS cluster service daemon."""
    try:
        # Import the module
        from ipfs_kit_py.ipfs_cluster_service import ipfs_cluster_service
        
        # Create an instance
        service = ipfs_cluster_service()
        
        # Call the status method
        result = service.ipfs_cluster_service_status()
        
        # Print the result
        logger.info("IPFS Cluster Service Status:")
        logger.info(f"Running: {result.get('process_running', False)}")
        logger.info(f"Process count: {result.get('process_count', 0)}")
        logger.info(f"Success: {result.get('success', False)}")
        
        return result
    except Exception as e:
        logger.error(f"Error testing IPFS cluster service status: {str(e)}")
        return {"error": str(e)}

def test_ipfs_cluster_follow_status():
    """Test the status functionality for IPFS cluster follow daemon."""
    try:
        # Import the module
        from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow
        
        # Create an instance
        follow = ipfs_cluster_follow()
        
        # Call the status method
        result = follow.ipfs_cluster_follow_status()
        
        # Print the result
        logger.info("IPFS Cluster Follow Status:")
        logger.info(f"Running: {result.get('process_running', False)}")
        logger.info(f"Process count: {result.get('process_count', 0)}")
        logger.info(f"Success: {result.get('success', False)}")
        
        return result
    except Exception as e:
        logger.error(f"Error testing IPFS cluster follow status: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    # Test IPFS cluster service status
    logger.info("Testing IPFS cluster service status...")
    service_result = test_ipfs_cluster_service_status()
    print(f"Service result: {json.dumps(service_result, indent=2)}")
    
    # Test IPFS cluster follow status
    logger.info("\nTesting IPFS cluster follow status...")
    follow_result = test_ipfs_cluster_follow_status()
    print(f"Follow result: {json.dumps(follow_result, indent=2)}")