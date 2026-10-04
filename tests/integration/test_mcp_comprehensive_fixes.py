import unittest
import json
import time
from unittest.mock import patch, MagicMock

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel


class TestMCPFixesComprehensive(unittest.TestCase):
    """
    Comprehensive test for all methods in the MCP server's IPFS model
    that might have issues handling bytes responses.
    """

    def setUp(self):
        """Set up test environment."""
        # Create a mock IPFS kit instance
        self.mock_ipfs_kit = MagicMock()
        
        # Create instance with mock IPFS kit
        self.ipfs_model = IPFSModel(ipfs_kit_instance=self.mock_ipfs_kit)
        
        # Reset operation stats
        self.ipfs_model.operation_stats = {
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
            "add_count": 0,
            "get_count": 0,
            "pin_count": 0,
            "unpin_count": 0,
            "list_count": 0,
            "bytes_added": 0,
            "bytes_retrieved": 0
        }

    def test_get_content_handles_bytes_response(self):
        """Test that get_content properly handles bytes responses."""
        # Prepare mock response
        test_bytes = b"Test content data"
        self.mock_ipfs_kit.cat.return_value = test_bytes
        
        # Call the method
        result = self.ipfs_model.get_content("QmTestCID")
        
        # Verify the method correctly handled the bytes response
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "get_content")
        self.assertEqual(result["data"], test_bytes)
    
    def test_add_content_handles_bytes_response(self):
        """Test that add_content properly handles bytes responses."""
        # Prepare mock response
        test_bytes = b"Added file response"
        self.mock_ipfs_kit.add_file.return_value = test_bytes
        
        # Call the method
        result = self.ipfs_model.add_content("Test content")
        
        # Verify the method correctly handled the bytes response
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "add_content")
        self.assertEqual(result["data"], test_bytes)
    
    def test_pin_content_handles_bytes_response(self):
        """Test that pin_content properly handles bytes responses."""
        # Prepare mock response
        test_bytes = b"Pin response data"
        self.mock_ipfs_kit.pin.return_value = test_bytes
        
        # Call the method
        result = self.ipfs_model.pin_content("QmTestCID")
        
        # Verify the method correctly handled the bytes response
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "pin_content")
        self.assertEqual(result["data"], test_bytes)
    
    def test_unpin_content_handles_bytes_response(self):
        """Test that unpin_content properly handles bytes responses."""
        # Prepare mock response
        test_bytes = b"Unpin response data"
        self.mock_ipfs_kit.unpin.return_value = test_bytes
        
        # Call the method
        result = self.ipfs_model.unpin_content("QmTestCID")
        
        # Verify the method correctly handled the bytes response
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "unpin_content")
        self.assertEqual(result["data"], test_bytes)
    
    def test_list_pins_handles_bytes_response(self):
        """Test that list_pins properly handles bytes responses."""
        # Prepare mock response
        test_bytes = b"List pins response data"
        self.mock_ipfs_kit.list_pins.return_value = test_bytes
        
        # Call the method
        result = self.ipfs_model.list_pins()
        
        # Verify the method correctly handled the bytes response
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
        self.assertEqual(result["cid"], "QmTestCID")
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
    
    def test_fs_read_handles_bytes_content(self):
        """Test that fs_read properly handles bytes content from get method."""
        # First, we need to set up the filesystem journal mock
        self.ipfs_model.filesystem_journal = MagicMock()
        journal_manager = MagicMock()
        journal = MagicMock()
        journal.get_fs_state.return_value = {
            "/test.txt": {"type": "file", "cid": "QmTestCID"}
        }
        journal_manager.journal = journal
        self.ipfs_model.filesystem_journal.journal_manager = journal_manager
        
        # Now mock the get response to return bytes directly
        mock_get_result = {
            "success": True,
            "content": b"File content"
        }
        self.mock_ipfs_kit.get.return_value = mock_get_result
        
        # Call the method
        result = self.ipfs_model.fs_read("/test.txt")
        
        # Verify the method correctly handled the content
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "fs_read")
        self.assertEqual(result["content"], b"File content")

    def test_check_webrtc_dependencies_handles_response(self):
        """Test that check_webrtc_dependencies properly formats its response."""
        # This method calls _check_webrtc which should return a dictionary
        # Make _check_webrtc method return a valid dictionary
        with patch.object(self.ipfs_model, '_check_webrtc') as mock_check:
            mock_check.return_value = {
                "webrtc_available": True,
                "dependencies": {
                    "aiortc": True,
                    "av": True
                }
            }
            
            # Call the method
            result = self.ipfs_model.check_webrtc_dependencies()
            
            # Verify the response is properly formatted
            self.assertTrue(result["success"])
            self.assertEqual(result["operation"], "check_webrtc_dependencies")
            self.assertTrue(result["webrtc_available"])
            self.assertIn("dependencies", result)


if __name__ == "__main__":
    unittest.main()