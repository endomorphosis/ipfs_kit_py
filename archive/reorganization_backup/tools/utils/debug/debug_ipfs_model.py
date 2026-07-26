#!/usr/bin/env python3
"""
Debug script to test the IPFS model's check_daemon_status method directly.
This will help identify if the issue is in the model or in the server.
"""

import sys
import logging
import time
import json
import traceback
import inspect
from typing import Dict, Any, Optional

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_ipfs_model.log')
    ]
)
logger = logging.getLogger("debug_ipfs_model")

# Try to import the IPFS model
try:
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    logger.info("Successfully imported IPFSModel")
except ImportError:
    logger.error("Failed to import IPFSModel. Make sure the module is available.")
    sys.exit(1)

# Try to import ipfs_kit
try:
    from ipfs_kit_py.ipfs_kit import ipfs_kit
    logger.info("Successfully imported ipfs_kit")
except ImportError:
    logger.error("Failed to import ipfs_kit. Make sure the module is available.")
    sys.exit(1)

def test_ipfs_model():
    """Test the IPFSModel's check_daemon_status method directly."""
    logger.info("Creating IPFSModel instance with real ipfs_kit")
    
    try:
        # Create the ipfs_kit instance
        kit = ipfs_kit()
        logger.info(f"Created ipfs_kit instance: {kit}")
        
        # Create the model with the real kit
        model = IPFSModel(ipfs_kit_instance=kit)
        logger.info(f"Created IPFSModel instance with real kit: {model}")
        
        # Inspect the check_daemon_status method in ipfs_kit
        if hasattr(kit, 'check_daemon_status'):
            signature = inspect.signature(kit.check_daemon_status)
            logger.info(f"kit.check_daemon_status signature: {signature}")
            logger.info(f"Parameters: {signature.parameters}")
            logger.info(f"Parameter count: {len(signature.parameters)}")
        else:
            logger.warning("ipfs_kit has no check_daemon_status method")
            
        # Test with no daemon_type
        logger.info("Testing check_daemon_status with no daemon_type")
        try:
            result = model.check_daemon_status()
            logger.info(f"Success: {result.get('success', False)}")
            logger.info(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            logger.error(f"Error in check_daemon_status with no daemon_type: {e}")
            logger.error(traceback.format_exc())
            
        # Test with daemon_type="ipfs"
        logger.info("Testing check_daemon_status with daemon_type='ipfs'")
        try:
            result = model.check_daemon_status("ipfs")
            logger.info(f"Success: {result.get('success', False)}")
            logger.info(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            logger.error(f"Error in check_daemon_status with daemon_type='ipfs': {e}")
            logger.error(traceback.format_exc())
            
        return True
        
    except Exception as e:
        logger.error(f"Error in test_ipfs_model: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting debug script for IPFSModel")
    success = test_ipfs_model()
    sys.exit(0 if success else 1)