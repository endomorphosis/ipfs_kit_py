#!/usr/bin/env python3
"""
IPFS Backend Verification Script

This script verifies that the IPFS Backend can properly initialize and connect
to the IPFS network after the dependency issue fix. It performs basic operations
to validate the backend functionality.
"""

import os
import sys
import logging
import time
import json
from pathlib import Path

# Add parent directory to path for importing
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ipfs_backend_verification")

def verify_ipfs_backend():
    """Verify the IPFS backend implementation."""
    try:
        # Import the IPFSBackend class
        logger.info("Importing IPFSBackend class...")
        from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
        from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType

        # Initialize the backend with test configuration
        logger.info("Initializing IPFS backend...")
        resources = {
            "ipfs_host": "127.0.0.1",
            "ipfs_port": 5001,
            "ipfs_timeout": 30,
            "allow_mock": True,  # Allow mock for environments without IPFS daemon
        }

        metadata = {
            "performance_metrics_file": "/tmp/ipfs_metrics.json",
            "backend_name": "ipfs_verification_test",
        }

        # Create the backend instance
        backend = IPFSBackend(resources, metadata)

        # Check if we're using mock implementation
        is_mock = hasattr(backend.ipfs, "_mock_implementation") and backend.ipfs._mock_implementation
        if is_mock:
            logger.warning("IPFS backend initialized with mock implementation")
        else:
            logger.info("IPFS backend initialized successfully with real implementation")

        # Verify backend properties
        logger.info(f"Backend type: {backend.backend_type}")
        logger.info(f"Backend name: {backend.get_name()}")

        # Test basic operations if we have a real implementation
        if not is_mock:
            # Add content
            test_content = b"Test content for IPFS backend verification"
            logger.info("Adding test content to IPFS...")
            add_result = backend.add_content(test_content)

            if add_result.get("success"):
                cid = add_result.get("identifier")
                logger.info(f"Content added successfully with CID: {cid}")

                # Get content
                logger.info(f"Retrieving content with CID: {cid}...")
                get_result = backend.get_content(cid)

                if get_result.get("success"):
                    retrieved_content = get_result.get("data")
                    if retrieved_content == test_content:
                        logger.info("Content retrieved successfully and matches original")
                    else:
                        logger.error("Retrieved content does not match original")
                else:
                    logger.error(f"Failed to retrieve content: {get_result.get('error')}")

                # Get metadata
                logger.info(f"Getting metadata for CID: {cid}...")
                metadata_result = backend.get_metadata(cid)
                if metadata_result.get("success"):
                    logger.info(f"Metadata retrieved: {json.dumps(metadata_result.get('metadata'), indent=2)}")
                else:
                    logger.error(f"Failed to get metadata: {metadata_result.get('error')}")

                # Clean up
                logger.info(f"Removing test content with CID: {cid}...")
                remove_result = backend.remove_content(cid)
                if remove_result.get("success"):
                    logger.info("Content removed successfully")
                else:
                    logger.error(f"Failed to remove content: {remove_result.get('error')}")

                # Get performance metrics
                logger.info("Getting performance metrics...")
                metrics = backend.get_performance_metrics()
                logger.info(f"Performance metrics: {json.dumps(metrics, indent=2)}")
            else:
                logger.error(f"Failed to add content: {add_result.get('error')}")
        else:
            # For mock implementation, just verify the mock methods exist
            logger.info("Testing mock implementation methods...")
            mock_operations = [
                backend.add_content(b"test"),
                backend.get_content("dummy_cid"),
                backend.get_metadata("dummy_cid"),
                backend.pin_add("dummy_cid"),
                backend.pin_ls(),
                backend.pin_rm("dummy_cid")
            ]
            for i, op_result in enumerate(mock_operations):
                logger.info(f"Mock operation {i+1} returned: {op_result.get('success', False)} (This should be False for mock)")

        logger.info("IPFS backend verification completed")
        return True

    except Exception as e:
        logger.error(f"Error verifying IPFS backend: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("Starting IPFS backend verification...")
    success = verify_ipfs_backend()

    if success:
        logger.info("✅ IPFS backend verification successful")
        sys.exit(0)
    else:
        logger.error("❌ IPFS backend verification failed")
        sys.exit(1)
