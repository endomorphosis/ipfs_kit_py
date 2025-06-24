#!/usr/bin/env python3
"""
Test script to check IPFS add functionality.
"""

import os
import tempfile
import time
import logging
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.ipfs import ipfs_py

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_ipfs_add():
    """Test adding content to IPFS."""
    print("Creating IPFS Kit instance...")
    kit = ipfs_kit()
    print("Kit initialized")

    # Also create a direct IPFS instance
    print("Creating direct IPFS instance...")
    direct_ipfs = ipfs_py()
    print("Direct IPFS instance initialized")

    # Check if kit.ipfs exists
    if hasattr(kit, 'ipfs'):
        print(f"kit.ipfs is available: {kit.ipfs}")
        if kit.ipfs:
            ipfs_methods = [m for m in dir(kit.ipfs) if not m.startswith('_') and callable(getattr(kit.ipfs, m))]
            print(f"Methods on kit.ipfs: {ipfs_methods}")
    else:
        print("kit.ipfs is not available")

    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        print(f"Created temporary file: {tmp.name}")
        tmp.write(b'Test content for IPFS')
        tmp_path = tmp.name

    try:
        # Try adding content using direct IPFS instance
        print(f"Adding file to IPFS using direct_ipfs.ipfs_add_file...")
        direct_result = direct_ipfs.ipfs_add_file(tmp_path)
        print(f"direct_ipfs.ipfs_add_file result: {direct_result}")

        # Try with kit.ipfs_add
        print(f"Adding file to IPFS using kit.ipfs_add...")
        kit_result = kit.ipfs_add(tmp_path)
        print(f"kit.ipfs_add result: {kit_result}")

        # Now try the MCP approach
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        print("Creating IPFSModel instance...")
        model = IPFSModel()
        print("IPFSModel initialized")

        print("Adding content using IPFSModel.add_content...")
        with open(tmp_path, 'rb') as f:
            content = f.read()
        model_result = model.add_content(content, filename="test.txt")
        print(f"IPFSModel.add_content result: {model_result}")

    finally:
        # Clean up
        os.unlink(tmp_path)
        print("Temporary file deleted")

if __name__ == "__main__":
    test_ipfs_add()
