#\!/usr/bin/env python3
"""
Comprehensive test for IPFS model handling of bytes responses.
"""

import unittest
from unittest.mock import MagicMock, patch
import logging
import json
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IPFSModel:
    """Simplified IPFS model for testing bytes handling."""

    def __init__(self):
        self.ipfs_kit = MagicMock()
        self.operation_stats = {
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0
        }

    def get_content(self, cid):
        """Get content from IPFS."""
        result = {
            "success": False,
            "operation": "get_content",
            "cid": cid
        }

        response = self.ipfs_kit.get(cid)
        if isinstance(response, bytes):
            result["success"] = True
            result["data"] = response
        else:
            result.update(response)

        return result

    def add_content(self, content, pin=False):
        """Add content to IPFS."""
        result = {
            "success": False,
            "operation": "add_content"
        }

        response = self.ipfs_kit.add(content, pin=pin)
        if isinstance(response, bytes):
            result["success"] = True
            result["data"] = response
            try:
                # Try to parse JSON response
                json_data = json.loads(response)
                if "Hash" in json_data:
                    result["cid"] = json_data["Hash"]
            except Exception:
                pass
        else:
            result.update(response)

        return result

    def pin_content(self, cid):
        """Pin content to local node."""
        result = {
            "success": False,
            "operation": "pin_content",
            "cid": cid
        }

        response = self.ipfs_kit.pin(cid)
        if isinstance(response, bytes):
            result["success"] = True
            result["data"] = response
        else:
            result.update(response)

        return result

    def unpin_content(self, cid):
        """Unpin content from local node."""
        result = {
            "success": False,
            "operation": "unpin_content",
            "cid": cid
        }

        response = self.ipfs_kit.unpin(cid)
        if isinstance(response, bytes):
            result["success"] = True
            result["data"] = response
        else:
            result.update(response)

        return result

    def list_pins(self):
        """List pinned content."""
        result = {
            "success": False,
            "operation": "list_pins"
        }

        response = self.ipfs_kit.list_pins()
        if isinstance(response, bytes):
            result["success"] = True
            result["data"] = response
        else:
            result.update(response)

        return result

    def ipfs_name_publish(self, cid, key=None, lifetime=None, ttl=None):
        """Publish CID to IPNS."""
        operation_id = f"name_publish_{int(time.time() * 1000)}"
        start_time = time.time()

        # Initialize result dictionary
        result = {
            "success": False,
            "operation_id": operation_id,
            "operation": "ipfs_name_publish",
            "cid": cid,
            "start_time": start_time
        }

        try:
            cmd_result = self.ipfs_kit.run_ipfs_command(["ipfs", "name", "publish"])

            if isinstance(cmd_result, bytes):
                # Store original for debugging
                result["raw_output"] = cmd_result

                # Convert to string for processing
                if isinstance(cmd_result, bytes):
                    stdout = cmd_result.decode("utf-8", errors="replace")
                else:
                    stdout = str(cmd_result)

                try:
                    # Parse plain text response
                    if "Published to " in stdout:
                        parts = stdout.strip().split("Published to ")[1].split(": ")
                        if len(parts) == 2:
                            name, value = parts
                        else:
                            name = parts[0]
                            value = f"/ipfs/{cid}"

                        result["success"] = True
                        result["name"] = name
                        result["value"] = value
                except Exception as e:
                    result["parse_warning"] = f"Couldn't parse IPFS output: {e}"

            else:
                # Not bytes, check if it's a dictionary
                if isinstance(cmd_result, dict):
                    result.update(cmd_result)
                else:
                    result["error"] = f"Unexpected response type: {type(cmd_result)}"
        except Exception as e:
            result["error"] = str(e)

        return result

    def ipfs_name_resolve(self, name, recursive=True, nocache=False, timeout=None):
        """Resolve IPNS name to CID."""
        operation_id = f"name_resolve_{int(time.time() * 1000)}"
        start_time = time.time()

        # Initialize result dictionary
        result = {
            "success": False,
            "operation_id": operation_id,
            "operation": "ipfs_name_resolve",
            "name": name,
            "start_time": start_time
        }

        try:
            cmd_result = self.ipfs_kit.run_ipfs_command(["ipfs", "name", "resolve"])

            # Handle bytes response
            if isinstance(cmd_result, bytes):
                result["raw_output"] = cmd_result

                try:
                    decoded = cmd_result.decode("utf-8", errors="replace").strip()
                    result["success"] = True
                    result["path"] = decoded
                except Exception as e:
                    result["error"] = f"Failed to decode bytes response: {str(e)}"
            # Handle dictionary response
            elif isinstance(cmd_result, dict):
                if cmd_result.get("success", False):
                    stdout_raw = cmd_result.get("stdout", b"")
                    result["raw_output"] = stdout_raw

                    if isinstance(stdout_raw, bytes):
                        stdout = stdout_raw.decode("utf-8", errors="replace")
                    else:
                        stdout = str(stdout_raw)

                    path = stdout.strip()
                    result["success"] = True
                    result["path"] = path
                else:
                    result["error"] = "Command failed"
            else:
                result["error"] = f"Unexpected response type: {type(cmd_result)}"
        except Exception as e:
            result["error"] = str(e)

        return result


class TestIPFSModelBytesHandling(unittest.TestCase):
    """Test bytes handling in IPFS model."""

    def setUp(self):
        self.ipfs_model = IPFSModel()
        self.mock_ipfs_kit = self.ipfs_model.ipfs_kit

    def test_get_content_handles_bytes(self):
        """Test that get_content properly handles bytes response."""
        test_bytes = b"Test content"
        self.mock_ipfs_kit.get.return_value = test_bytes

        result = self.ipfs_model.get_content("QmTestCID")

        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "get_content")
        self.assertEqual(result["data"], test_bytes)

    def test_add_content_handles_bytes(self):
        """Test that add_content properly handles bytes response."""
        test_bytes = b'{"Hash": "QmTestCID", "Size": "123"}'
        self.mock_ipfs_kit.add.return_value = test_bytes

        result = self.ipfs_model.add_content("test content")

        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "add_content")
        self.assertEqual(result["data"], test_bytes)
        self.assertEqual(result["cid"], "QmTestCID")

    def test_pin_content_handles_bytes(self):
        """Test that pin_content properly handles bytes response."""
        test_bytes = b"Pinned QmTestCID"
        self.mock_ipfs_kit.pin.return_value = test_bytes

        result = self.ipfs_model.pin_content("QmTestCID")

        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "pin_content")
        self.assertEqual(result["data"], test_bytes)

    def test_unpin_content_handles_bytes(self):
        """Test that unpin_content properly handles bytes response."""
        test_bytes = b"Unpinned QmTestCID"
        self.mock_ipfs_kit.unpin.return_value = test_bytes

        result = self.ipfs_model.unpin_content("QmTestCID")

        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "unpin_content")
        self.assertEqual(result["data"], test_bytes)

    def test_list_pins_handles_bytes(self):
        """Test that list_pins properly handles bytes response."""
        test_bytes = b'{"Pins": ["QmTestCID1", "QmTestCID2"]}'
        self.mock_ipfs_kit.list_pins.return_value = test_bytes

        result = self.ipfs_model.list_pins()

        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "list_pins")
        self.assertEqual(result["data"], test_bytes)

    def test_ipfs_name_publish_handles_bytes_stdout(self):
        """Test that ipfs_name_publish properly handles bytes in stdout."""
        # Test case with bytes output directly
        test_bytes = b"Published to k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8: /ipfs/QmTestCID"
        self.mock_ipfs_kit.run_ipfs_command.return_value = test_bytes

        # Call the method
        result = self.ipfs_model.ipfs_name_publish("QmTestCID")

        # Verify the method correctly handled the bytes response
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ipfs_name_publish")
        self.assertEqual(result["raw_output"], test_bytes)
        self.assertEqual(result["name"], "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8")
        self.assertEqual(result["value"], "/ipfs/QmTestCID")

    def test_ipfs_name_resolve_handles_bytes_stdout(self):
        """Test that ipfs_name_resolve properly handles bytes in stdout."""
        # Test direct bytes response from run_ipfs_command
        test_bytes = b"/ipfs/QmResolvedTestCID"
        self.mock_ipfs_kit.run_ipfs_command.return_value = test_bytes

        # Call the method
        result = self.ipfs_model.ipfs_name_resolve("test")

        # Verify the method correctly handled the bytes response
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ipfs_name_resolve")
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["path"], "/ipfs/QmResolvedTestCID")
        self.assertEqual(result["raw_output"], test_bytes)


if __name__ == "__main__":
    unittest.main()
