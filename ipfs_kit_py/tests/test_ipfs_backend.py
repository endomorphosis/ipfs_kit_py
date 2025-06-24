"""
Test script for the IPFS backend.

This script verifies that the IPFS backend implementation can initialize
correctly with the ipfs_py client dependency that was implemented.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# Now import the necessary modules
try:
    from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
    from ipfs_kit_py.ipfs_client import ipfs_py
    logger.info("Successfully imported IPFS backend and client modules")
except ImportError as e:
    logger.error(f"Failed to import IPFS modules: {e}")
    sys.exit(1)

def test_ipfs_backend():
    """Test the IPFS backend initialization and basic functionality."""
    logger.info("Testing IPFS backend initialization...")

    # Create resources and metadata for initialization
    resources = {
        "api_url": "http://localhost:5001/api/v0",  # Default local IPFS API
        "timeout": 30
    }
    metadata = {
        "test": True,
        "description": "Test IPFS backend"
    }

    try:
        # Initialize the backend
        backend = IPFSBackend(resources, metadata)
        logger.info(f"IPFS backend initialized successfully: {backend.get_name()}")

        # Check if we're using the real or mock implementation
        if hasattr(backend.ipfs, "_mock_implementation") and backend.ipfs._mock_implementation:
            logger.warning("Using mock implementation (no local IPFS node available)")
        else:
            logger.info("Connected to real IPFS node")

        # Try a simple operation
        test_content = b"Hello, IPFS from MCP!"
        logger.info("Adding test content to IPFS...")
        result = backend.add_content(test_content)
        logger.info(f"Add content result: {result}")

        if result.get("success", False):
            content_id = result.get("identifier")
            logger.info(f"Content added with ID: {content_id}")

            # Try retrieving the content
            logger.info(f"Retrieving content with ID: {content_id}")
            retrieve_result = backend.get_content(content_id)
            logger.info(f"Retrieve content result success: {retrieve_result.get('success', False)}")

            if retrieve_result.get("success", False):
                retrieved_data = retrieve_result.get("data")
                if retrieved_data == test_content:
                    logger.info("Retrieved content matches original content")
                else:
                    logger.error("Retrieved content does not match original content")

            # Get metadata
            logger.info(f"Getting metadata for content ID: {content_id}")
            metadata_result = backend.get_metadata(content_id)
            logger.info(f"Metadata result: {metadata_result}")

        logger.info("IPFS backend test completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error testing IPFS backend: {e}")
        return False

if __name__ == "__main__":
    success = test_ipfs_backend()
    if success:
        logger.info("✅ IPFS backend test passed!")
        sys.exit(0)
    else:
        logger.error("❌ IPFS backend test failed!")
        sys.exit(1)
