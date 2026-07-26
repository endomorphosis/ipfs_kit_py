#!/usr/bin/env python3
"""
Test script to verify that IPFS methods are properly registered
"""
import sys
import logging
import json
import requests
import time

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_mcp_ipfs_methods():
    """Test IPFS methods via MCP server API"""
    BASE_URL = "http://localhost:9994/api/v0"
    
    # Test 1: Add content
    logger.info("Testing add_content method...")
    try:
        response = requests.post(
            f"{BASE_URL}/ipfs/add_content", 
            json={"content": "Hello, IPFS world!", "pin": True}
        )
        result = response.json()
        logger.info(f"add_content result: {json.dumps(result, indent=2)}")
        
        if result.get("success") is True and "cid" in result:
            cid = result["cid"]
            logger.info(f"Successfully added content with CID: {cid}")
            
            # Test 2: Cat content
            logger.info("Testing cat method...")
            response = requests.post(f"{BASE_URL}/ipfs/cat", json={"cid": cid})
            cat_result = response.json()
            logger.info(f"cat result: {json.dumps(cat_result, indent=2)}")
            
            # Test 3: Pin list
            logger.info("Testing pin_ls method...")
            response = requests.post(f"{BASE_URL}/ipfs/pin_ls", json={})
            pin_ls_result = response.json()
            logger.info(f"pin_ls result: {json.dumps(pin_ls_result, indent=2)}")
            
            # Test 4: Unpin
            logger.info("Testing pin_rm method...")
            response = requests.post(f"{BASE_URL}/ipfs/pin_rm", json={"cid": cid})
            unpin_result = response.json()
            logger.info(f"pin_rm result: {json.dumps(unpin_result, indent=2)}")
            
            return True
        else:
            logger.error(f"Failed to add content: {result}")
            return False
    except Exception as e:
        logger.exception(f"Error testing IPFS methods: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting IPFS methods test")
    time.sleep(2)  # Give server time to fully start up
    success = test_mcp_ipfs_methods()
    if success:
        logger.info("✅ All IPFS methods tests completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ IPFS methods tests failed")
        sys.exit(1)
