#!/usr/bin/env python3
import time
import logging
import sys
import importlib.util
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def test_close_all_webrtc_connections():
    """
    Test the close_all_webrtc_connections method directly.
    
    This bypasses the HTTP API and directly tests the method we implemented.
    """
    logger.info("Testing close_all_webrtc_connections method directly...")
    
    # Import the IPFSModelAnyIO class directly
    module_path = Path("/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/models/ipfs_model_anyio.py")
    spec = importlib.util.spec_from_file_location("ipfs_model_anyio", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Get the IPFSModelAnyIO class
    IPFSModelAnyIO = module.IPFSModelAnyIO
    
    # Create a minimal instance for testing
    model = IPFSModelAnyIO()
    
    # Call the method we implemented
    result = model.close_all_webrtc_connections()
    
    # Print the result
    logger.info(f"Result: {result}")
    
    # Check if the method executed successfully
    if result.get("success", False):
        logger.info("✅ WebRTC close_all_webrtc_connections succeeded")
    else:
        logger.error("❌ WebRTC close_all_webrtc_connections failed")
        
    return result

if __name__ == "__main__":
    try:
        # Run the direct test
        result = test_close_all_webrtc_connections()
        
        # Exit with appropriate code
        sys.exit(0 if result.get("success", False) else 1)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        sys.exit(1)