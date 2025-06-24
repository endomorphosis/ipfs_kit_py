"""
Simple test script for FSSpec integration
"""

import logging
from ipfs_kit_py import IPFSSimpleAPI

# Set up logging
logging.basicConfig(level=logging.INFO)

def test_fsspec_integration():
    """Test that FSSpec integration works properly."""
    # Initialize simple API
    api = IPFSSimpleAPI()

    # Try to get a filesystem
    fs = api.get_filesystem()

    # Check if it worked
    if fs is None:
        print("FSSpec integration not available. Make sure fsspec is installed.")
        return False

    print(f"FSSpec integration available. Filesystem type: {type(fs)}")
    return True

if __name__ == "__main__":
    test_fsspec_integration()
