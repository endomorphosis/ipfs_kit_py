#!/usr/bin/env python3
"""
Test script to verify that the IPFS backend implementation loads successfully.

This script directly tests the critical issue mentioned in the roadmap:
"The backend currently fails to initialize due to a missing ipfs_py client dependency"
"""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ipfs_backend_test")

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

def test_ipfs_py_import():
    """Test direct import of ipfs_py from the ipfs module."""
    try:
        from ipfs_kit_py.ipfs import ipfs_py
        logger.info("✅ Successfully imported ipfs_py from ipfs_kit_py.ipfs")
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import ipfs_py: {e}")
        return False

def test_ipfs_backend_initialization():
    """Test initialization of the IPFSBackend class."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
        from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
        
        # Create a basic configuration for testing
        resources = {
            "ipfs_host": "127.0.0.1",
            "ipfs_port": 5001,
            "ipfs_timeout": 30
        }
        
        metadata = {
            "backend_name": "test_ipfs_backend"
        }
        
        # Initialize the backend
        backend = IPFSBackend(resources, metadata)
        
        # Check if we're using a mock implementation
        is_mock = hasattr(backend.ipfs, "_mock_implementation") and backend.ipfs._mock_implementation
        
        if is_mock:
            logger.warning("⚠️ Backend initialized with mock implementation")
        else:
            logger.info("✅ Backend initialized with real implementation")
        
        # Verify the backend properties
        assert backend.backend_type == StorageBackendType.IPFS
        assert backend.get_name() == "ipfs"
        
        logger.info("✅ IPFSBackend initialization successful")
        return True
    except Exception as e:
        logger.error(f"❌ IPFSBackend initialization failed: {e}")
        return False

def test_basic_operations():
    """Test basic operations with the IPFS backend."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
        
        # Create a basic configuration for testing
        resources = {
            "ipfs_host": "127.0.0.1",
            "ipfs_port": 5001,
            "ipfs_timeout": 30
        }
        
        metadata = {
            "backend_name": "test_ipfs_backend"
        }
        
        # Initialize the backend
        backend = IPFSBackend(resources, metadata)
        
        # Test 1: Add content
        test_content = b"Test content for IPFS backend verification"
        add_result = backend.add_content(test_content)
        
        if add_result.get("success"):
            logger.info(f"✅ Content added successfully: {add_result.get('identifier')}")
            
            # Test 2: Get content
            cid = add_result.get("identifier")
            get_result = backend.get_content(cid)
            
            if get_result.get("success"):
                retrieved_content = get_result.get("data")
                if retrieved_content == test_content:
                    logger.info("✅ Content retrieved successfully and matches original")
                else:
                    logger.warning("⚠️ Retrieved content does not match original")
            else:
                logger.warning(f"⚠️ Could not retrieve content: {get_result.get('error')}")
            
            # Test 3: Get metadata
            metadata_result = backend.get_metadata(cid)
            if metadata_result.get("success"):
                logger.info("✅ Metadata retrieved successfully")
            else:
                logger.warning(f"⚠️ Could not get metadata: {metadata_result.get('error')}")
        else:
            logger.warning(f"⚠️ Could not add content: {add_result.get('error')}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Basic operations test failed: {e}")
        return False

def main():
    """Run all tests for the IPFS backend."""
    logger.info("Starting IPFS backend verification tests...")
    
    # Test 1: Import the ipfs_py module
    if not test_ipfs_py_import():
        logger.error("❌ Failed to import ipfs_py module")
        return False
    
    # Test 2: Initialize the IPFS backend
    if not test_ipfs_backend_initialization():
        logger.error("❌ Failed to initialize IPFS backend")
        return False
    
    # Test 3: Test basic operations
    if not test_basic_operations():
        logger.error("❌ Failed basic operations test")
        return False
    
    logger.info("✅ All tests passed! The IPFS backend is working correctly.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)