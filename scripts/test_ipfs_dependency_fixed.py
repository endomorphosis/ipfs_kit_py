#!/usr/bin/env python3
"""
Focused test script to verify the IPFS backend can import the ipfs_py dependency.

This directly addresses the critical issue mentioned in the roadmap:
"Missing Dependency: The backend currently fails to initialize due to a missing
ipfs_py client dependency (`ipfs_kit_py.ipfs.ipfs_py`), likely lost during consolidation."
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
logger = logging.getLogger("ipfs_dependency_test")

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

def test_ipfs_py_import():
    """Test if ipfs_py can be directly imported from ipfs_kit_py.ipfs."""
    try:
        from ipfs_kit_py.ipfs import ipfs_py
        logger.info(f"✅ Successfully imported ipfs_py class: {ipfs_py}")

        # Check if we can instantiate it
        instance = ipfs_py()
        logger.info(f"✅ Successfully instantiated ipfs_py: {instance}")
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import ipfs_py: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error creating ipfs_py instance: {e}")
        return False

def test_ipfs_backend_import_mechanism():
    """Test if the IPFS backend's import mechanism for ipfs_py works."""
    try:
        # Import the backend class
        from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
        logger.info("✅ Successfully imported IPFSBackend class")

        # Access the _get_ipfs_py_class method
        get_ipfs_py_class = IPFSBackend._get_ipfs_py_class
        logger.info(f"✅ Successfully accessed _get_ipfs_py_class method: {get_ipfs_py_class}")

        # Create a dummy instance with minimal setup to test the method
        class DummyBackend:
            pass

        backend = DummyBackend()
        backend.backend_type = "ipfs"
        backend.resources = {}
        backend.metadata = {}

        # Call the method to get the ipfs_py class
        ipfs_py_class = get_ipfs_py_class(backend)
        logger.info(f"✅ Successfully obtained ipfs_py class: {ipfs_py_class}")

        # Check if we can instantiate it
        instance = ipfs_py_class({}, {})
        logger.info(f"✅ Successfully instantiated ipfs_py: {instance}")

        return True
    except ImportError as e:
        logger.error(f"❌ Import error in backend: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error in backend import mechanism: {e}")
        return False

def main():
    """Run the targeted tests for the IPFS dependency issue."""
    logger.info("Starting focused IPFS dependency tests...")

    # Test 1: Direct import of ipfs_py
    direct_import_success = test_ipfs_py_import()

    # Test 2: Backend import mechanism
    backend_import_success = test_ipfs_backend_import_mechanism()

    # Determine overall success
    if direct_import_success and backend_import_success:
        logger.info("✅ All dependency tests passed! The IPFS backend can now properly access ipfs_py.")
        logger.info("✅ The critical issue from the roadmap has been resolved.")
        return True
    else:
        logger.error("❌ Some dependency tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
