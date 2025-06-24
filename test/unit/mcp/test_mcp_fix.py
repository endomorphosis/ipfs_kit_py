#!/usr/bin/env python3

"""
Test script to verify the fix for the MCP server's get_content method.
This script specifically tests handling of bytes responses from the underlying IPFS implementation.
"""

import unittest
import json
import time
import sys

# Simple test that directly creates an instance of the IPFS model with our fix
def test_get_content_bytes_fix():
    """Test the fix for the get_content method handling bytes responses."""
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel

    class MockIPFS:
        """Minimal mock IPFS instance."""
        def cat(self, cid):
            """Return bytes for the cat method."""
            return b"Test content"

    # Create IPFS model with our mock
    ipfs_model = IPFSModel(MockIPFS(), None)

    # Call the get_content method
    result = ipfs_model.get_content("QmTest123")

    # Check if the result is valid
    if not result.get("success", False):
        print("❌ TEST FAILED: Result success is not True")
        return False

    if result.get("data") != b"Test content":
        print(f"❌ TEST FAILED: Result data does not match. Expected: b'Test content', Got: {result.get('data')}")
        return False

    if result.get("operation") != "get_content":
        print(f"❌ TEST FAILED: Result operation is not 'get_content'. Got: {result.get('operation')}")
        return False

    print("✅ TEST PASSED: get_content correctly handles bytes responses")
    return True

# Additional test for dictionary response
def test_get_content_dict_fix():
    """Test the fix for the get_content method handling dictionary responses."""
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel

    class MockIPFS:
        """Minimal mock IPFS instance."""
        def cat(self, cid):
            """Return a dictionary for the cat method."""
            return {
                "success": True,
                "operation": "cat",
                "data": b"Test content",
                "simulated": False
            }

    # Create IPFS model with our mock
    ipfs_model = IPFSModel(MockIPFS(), None)

    # Call the get_content method
    result = ipfs_model.get_content("QmTest123")

    # Check if the result is valid
    if not result.get("success", False):
        print("❌ TEST FAILED: Result success is not True")
        return False

    if result.get("data") != b"Test content":
        print(f"❌ TEST FAILED: Result data does not match. Expected: b'Test content', Got: {result.get('data')}")
        return False

    if result.get("operation") != "get_content":
        print(f"❌ TEST FAILED: Result operation is not 'get_content'. Got: {result.get('operation')}")
        return False

    print("✅ TEST PASSED: get_content correctly handles dictionary responses")
    return True

if __name__ == "__main__":
    print("Testing MCP Server get_content method fix for handling bytes responses...")

    # Run the tests
    bytes_test_success = test_get_content_bytes_fix()
    dict_test_success = test_get_content_dict_fix()

    # Exit with appropriate code
    if bytes_test_success and dict_test_success:
        print("\n✅ ALL TESTS PASSED: The fix for get_content method is working correctly!")
        sys.exit(0)
    else:
        print("\n❌ TESTS FAILED: The fix for get_content method is not working correctly.")
        sys.exit(1)
