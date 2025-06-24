#!/usr/bin/env python
"""
Simplified MCP server test focusing only on IPFS model test
"""

import unittest
from unittest.mock import MagicMock, patch

class TestIPFSModel:
    """Custom IPFS model for testing."""

    def __init__(self):
        self.operation_stats = {
            "add_count": 0,
            "get_count": 0,
            "pin_count": 0,
            "unpin_count": 0,
            "list_count": 0,
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
            "bytes_added": 0,
            "bytes_retrieved": 0
        }

    def add_content(self, content, filename=None):
        """Add content to IPFS."""
        self.operation_stats["add_count"] += 1
        self.operation_stats["total_operations"] += 1
        self.operation_stats["success_count"] += 1

        return {
            "success": True,
            "cid": "QmTest123",
            "size": len(content) if content else 0,
            "operation_id": "test-op-1",
            "duration_ms": 0.5
        }

    def get_content(self, cid):
        """Get content from IPFS by CID."""
        self.operation_stats["get_count"] += 1
        self.operation_stats["total_operations"] += 1
        self.operation_stats["success_count"] += 1

        return {
            "success": True,
            "data": b"Test content",
            "size": len(b"Test content"),
            "operation_id": "test-op-2",
            "duration_ms": 0.3
        }

    def pin_content(self, cid):
        """Pin content by CID."""
        self.operation_stats["pin_count"] += 1
        self.operation_stats["total_operations"] += 1
        self.operation_stats["success_count"] += 1

        return {
            "success": True,
            "cid": cid,
            "operation_id": "test-op-3",
            "duration_ms": 0.2
        }

    def unpin_content(self, cid):
        """Unpin content by CID."""
        self.operation_stats["unpin_count"] += 1
        self.operation_stats["total_operations"] += 1
        self.operation_stats["success_count"] += 1

        return {
            "success": True,
            "cid": cid,
            "operation_id": "test-op-4",
            "duration_ms": 0.1
        }

    def list_pins(self):
        """List pinned content."""
        self.operation_stats["list_count"] += 1
        self.operation_stats["total_operations"] += 1
        self.operation_stats["success_count"] += 1

        return {
            "success": True,
            "pins": [{"cid": "QmTest123", "type": "recursive"}],
            "operation_id": "test-op-5",
            "duration_ms": 0.4
        }


class MockMCPServer:
    """Mock MCP server for testing."""

    def __init__(self, debug_mode=True, isolation_mode=True):
        self.debug_mode = debug_mode
        self.isolation_mode = isolation_mode
        self.models = {"ipfs": TestIPFSModel()}
        self.controllers = {}
        self.persistence = MagicMock()


class TestSimpleMCPServer(unittest.TestCase):
    """Simple test for MCP server."""

    def setUp(self):
        """Set up test environment."""
        self.mcp_server = MockMCPServer(debug_mode=True, isolation_mode=True)

    def test_server_initialization(self):
        """Test that the MCP server initializes correctly."""
        # Verify that all components are initialized
        self.assertTrue(hasattr(self.mcp_server, "models"))
        self.assertTrue(hasattr(self.mcp_server, "controllers"))
        self.assertTrue(hasattr(self.mcp_server, "persistence"))

        # Verify that the IPFS model is initialized
        self.assertIn("ipfs", self.mcp_server.models)
        # Check that the IPFS model has the necessary methods
        ipfs_model = self.mcp_server.models["ipfs"]
        self.assertTrue(hasattr(ipfs_model, "add_content"))
        self.assertTrue(hasattr(ipfs_model, "get_content"))
        self.assertTrue(hasattr(ipfs_model, "pin_content"))
        self.assertTrue(hasattr(ipfs_model, "unpin_content"))
        self.assertTrue(hasattr(ipfs_model, "list_pins"))

        # Verify that debug mode is enabled
        self.assertTrue(self.mcp_server.debug_mode)

        # Verify that isolation mode is enabled
        self.assertTrue(self.mcp_server.isolation_mode)

    def test_ipfs_model(self):
        """Test the IPFS model operations."""
        ipfs_model = self.mcp_server.models["ipfs"]

        # Test adding content
        content = b"Test content"
        result = ipfs_model.add_content(content)
        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], "QmTest123")

        # Test getting content
        content_result = ipfs_model.get_content("QmTest123")
        self.assertTrue(content_result["success"])
        self.assertEqual(content_result["data"], b"Test content")

        # Test pinning content
        pin_result = ipfs_model.pin_content("QmTest123")
        self.assertTrue(pin_result["success"])

        # Test unpinning content
        unpin_result = ipfs_model.unpin_content("QmTest123")
        self.assertTrue(unpin_result["success"])

        # Test listing pins
        pins_result = ipfs_model.list_pins()
        self.assertTrue(pins_result["success"])
        # The pins field should exist
        self.assertTrue("pins" in pins_result, "Response missing 'pins' field")

        # Handle different possible pin formats:
        # 1. List of dictionaries with 'cid' field
        # 2. List of strings containing CIDs
        # 3. Other format - extract CIDs from the response
        pin_cids = []
        if isinstance(pins_result["pins"], list):
            for pin in pins_result["pins"]:
                if isinstance(pin, dict) and "cid" in pin:
                    pin_cids.append(pin["cid"])
                elif isinstance(pin, str):
                    pin_cids.append(pin)

        # If no CIDs found in pins list, try "Keys" field as fallback
        if not pin_cids and "Keys" in pins_result:
            pin_cids = list(pins_result["Keys"].keys())

        # Our test CID should be in the pins
        self.assertIn("QmTest123", pin_cids,
                      f"Expected CID not found in pins. Pins: {pins_result}")


if __name__ == "__main__":
    unittest.main()
