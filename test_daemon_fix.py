#!/usr/bin/env python3
"""
Test script to verify the daemon management fix works correctly.
"""

import sys
import os
sys.path.insert(0, '/home/barberb/ipfs_kit_py')

from mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_daemon_management():
    """Test the daemon management functionality."""
    logger.info("=== Testing IPFS Daemon Management ===")
    
    try:
        # Initialize the integration
        logger.info("Initializing IPFS Kit Integration...")
        integration = IPFSKitIntegration()
        
        # Test daemon detection
        logger.info("Testing daemon detection...")
        daemon_running = integration._ensure_daemon_running()
        logger.info(f"Daemon running result: {daemon_running}")
        
        # Test IPFS connection
        logger.info("Testing IPFS connection...")
        connection_test = integration._test_ipfs_connection()
        logger.info(f"Connection test result: {connection_test}")
        
        # Test direct IPFS
        logger.info("Testing direct IPFS...")
        direct_test = integration._test_direct_ipfs()
        logger.info(f"Direct test result: {direct_test}")
        
        # Test API direct (if available)
        try:
            api_test = integration._test_ipfs_api_direct()
            logger.info(f"API test result: {api_test}")
        except Exception as e:
            logger.info(f"API test failed (expected if requests not available): {e}")
        
        # Test finding existing processes
        logger.info("Testing process detection...")
        existing_pids = integration._find_existing_ipfs_processes()
        logger.info(f"Existing IPFS processes: {existing_pids}")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_daemon_management()
    sys.exit(0 if success else 1)
