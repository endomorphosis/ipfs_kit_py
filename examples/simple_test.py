"""
Simple test for IPFS Kit High-Level API.

This script demonstrates basic usage of the High-Level API with mock objects.
"""

import sys
import os
from unittest.mock import MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock necessary components
def create_mock_environment():
    """Create mock environment for testing."""
    # Create mock IPFSKit
    mock_kit = MagicMock()
    mock_fs = MagicMock()
    mock_kit.get_filesystem.return_value = mock_fs
    
    # Mock common methods
    mock_kit.ipfs_add.return_value = {"success": True, "cid": "QmTest"}
    mock_kit.ipfs_cat.return_value = b"Test content"
    
    # Create a module mock
    mock_module = MagicMock()
    mock_module.IPFSKit = MagicMock(return_value=mock_kit)
    
    # Replace the real module with the mock
    sys.modules['ipfs_kit_py.ipfs_kit'] = mock_module

# Create the mock environment
create_mock_environment()

# Mock validation function to avoid actual validation
sys.modules['ipfs_kit_py.validation'] = MagicMock()
sys.modules['ipfs_kit_py.validation'].validate_parameters = MagicMock(side_effect=lambda params, spec: params)

# Now import the High-Level API
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Create API instance
api = IPFSSimpleAPI()

# Test adding content
result = api.add("Hello, world!")
print(f"Add result: {result}")

# Test getting content
content = api.get("QmTest")
print(f"Get result: {content}")

print("Test completed successfully!")