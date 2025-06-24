#!/usr/bin/env python3
"""
Test script to verify if the ipfs_py class can be imported correctly
and if the IPFSBackend class can be initialized.
"""

import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Try direct import
try:
    logger.info("Attempting to import ipfs_py directly...")
    from ipfs_kit_py.ipfs_client import ipfs_py
    logger.info("✅ Successfully imported ipfs_py")

    # Create an instance to test basic functionality
    client = ipfs_py()
    logger.info(f"ipfs_py instance created. Path: {client.ipfs_path}")
except ImportError as e:
    logger.error(f"❌ Failed to import ipfs_py: {e}")

# Try importing and initializing IPFSBackend
try:
    logger.info("\nAttempting to import and initialize IPFSBackend...")
    from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend

    # Create a mock resources and metadata dict
    resources = {}
    metadata = {"ipfs_path": os.path.expanduser("~/.ipfs")}

    # Initialize the backend
    backend = IPFSBackend(resources, metadata)

    # Check if using mock implementation
    if hasattr(backend.ipfs, "_mock_implementation") and backend.ipfs._mock_implementation:
        logger.warning("❌ IPFSBackend initialized with MOCK implementation")
    else:
        logger.info("✅ IPFSBackend initialized with REAL implementation")

except Exception as e:
    logger.error(f"❌ Failed to initialize IPFSBackend: {e}")
    import traceback
    traceback.print_exc()
