"""
Test MFS (Mutable File System) operations in the MCP server.

This test module verifies the functionality of IPFS MFS operations in the MCP model.
"""

import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel


class TestMCPMFSOperations(unittest.TestCase):
    """Test IPFS MFS operations in the MCP model."""
    
    def setUp(self):
        """Set up a test environment."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a mock IPFS kit instance
        self.mock_ipfs_kit = MagicMock()
        
        # Set up the mock responses for MFS operations
        self._setup_mock_responses()
        
        # Create the IPFS model with the mock kit
        self.ipfs_model = IPFSModel(ipfs_kit_instance=self.mock_ipfs_kit)
    
    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _setup_mock_responses(self):
        """Set up mock responses for IPFS kit methods."""
        # Mock files_mkdir
        self.mock_ipfs_kit.files_mkdir.return_value = {
            "Path": "/test_dir", 
            "Success": True
        }
        
        # Mock files_ls
        self.mock_ipfs_kit.files_ls.return_value = {
            "Entries": [
                {"Name": "test_file.txt", "Type": 0, "Size": 1024, "Hash": "QmTestFile"},
                {"Name": "test_subdir", "Type": 1, "Size": 0, "Hash": "QmTestDir"}
            ]
        }
        
        # Mock files_stat
        self.mock_ipfs_kit.files_stat.return_value = {
            "Size": 1024,
            "Type": 0,  # 0 for file, 1 for directory
            "Hash": "QmTestFileStat",
            "Blocks": 1,
            "CumulativeSize": 1024
        }
        
        # Mock files_read
        self.mock_ipfs_kit.files_read.return_value = b"Test content from MFS file"
        
        # Mock files_write
        self.mock_ipfs_kit.files_write.return_value = {
            "Path": "/test_file.txt",
            "Success": True,
            "Bytes": 26  # Length of "Test content for MFS file"
        }
        
        # Mock files_rm
        self.mock_ipfs_kit.files_rm.return_value = {
            "Path": "/test_file.txt",
            "Success": True
        }
    
    def test_files_mkdir(self):
        """Test creating a directory in MFS."""
        # Call the files_mkdir method
        result = self.ipfs_model.files_mkdir("/test_dir", parents=True)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["path"], "/test_dir")
        self.assertEqual(result["operation"], "files_mkdir")
        
        # Verify that the mock was called with correct arguments
        self.mock_ipfs_kit.files_mkdir.assert_called_once_with(
            "/test_dir", parents=True, flush=True
        )
    
    def test_files_ls(self):
        """Test listing directory contents in MFS."""
        # Call the files_ls method
        result = self.ipfs_model.files_ls("/test_dir", long=True)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["path"], "/test_dir")
        self.assertEqual(result["operation"], "files_ls")
        self.assertEqual(len(result["entries"]), 2)
        
        # Verify entries are properly formatted
        entries = result["entries"]
        self.assertEqual(entries[0]["Name"], "test_file.txt")
        self.assertEqual(entries[0]["Type"], 0)  # File
        self.assertEqual(entries[0]["Size"], 1024)
        self.assertEqual(entries[0]["Hash"], "QmTestFile")
        
        self.assertEqual(entries[1]["Name"], "test_subdir")
        self.assertEqual(entries[1]["Type"], 1)  # Directory
        
        # Verify that the mock was called with correct arguments
        self.mock_ipfs_kit.files_ls.assert_called_once_with("/test_dir", long=True)
    
    def test_files_stat(self):
        """Test getting file/directory stats in MFS."""
        # Call the files_stat method
        result = self.ipfs_model.files_stat("/test_dir/test_file.txt")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["path"], "/test_dir/test_file.txt")
        self.assertEqual(result["operation"], "files_stat")
        self.assertEqual(result["size"], 1024)
        self.assertEqual(result["type"], 0)  # File
        self.assertEqual(result["cid"], "QmTestFileStat")
        self.assertEqual(result["blocks"], 1)
        
        # Verify that the mock was called with correct arguments
        self.mock_ipfs_kit.files_stat.assert_called_once_with("/test_dir/test_file.txt")
    
    def test_files_read(self):
        """Test reading content from a file in MFS."""
        # Call the files_read method
        result = self.ipfs_model.files_read("/test_dir/test_file.txt", offset=0, count=10)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["path"], "/test_dir/test_file.txt")
        self.assertEqual(result["operation"], "files_read")
        self.assertEqual(result["data"], b"Test content from MFS file")
        self.assertEqual(result["size"], len(b"Test content from MFS file"))
        
        # Verify that the mock was called with correct arguments
        self.mock_ipfs_kit.files_read.assert_called_once_with("/test_dir/test_file.txt", offset=0, count=10)
    
    def test_files_write(self):
        """Test writing content to a file in MFS."""
        # Test content to write
        test_content = "Test content for MFS file"
        
        # Call the files_write method
        result = self.ipfs_model.files_write(
            "/test_dir/test_file.txt", 
            test_content,
            create=True,
            truncate=True
        )
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["path"], "/test_dir/test_file.txt")
        self.assertEqual(result["operation"], "files_write")
        self.assertEqual(result["bytes_written"], len(test_content.encode('utf-8')))
        
        # Verify that the mock was called with correct arguments
        self.mock_ipfs_kit.files_write.assert_called_once()
        call_args = self.mock_ipfs_kit.files_write.call_args[0]
        self.assertEqual(call_args[0], "/test_dir/test_file.txt")
        self.assertEqual(call_args[1], test_content.encode('utf-8'))
    
    def test_files_rm(self):
        """Test removing a file or directory from MFS."""
        # Call the files_rm method
        result = self.ipfs_model.files_rm("/test_dir/test_file.txt", recursive=False, force=False)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["path"], "/test_dir/test_file.txt")
        self.assertEqual(result["operation"], "files_rm")
        
        # Verify that the mock was called with correct arguments
        self.mock_ipfs_kit.files_rm.assert_called_once_with(
            "/test_dir/test_file.txt", recursive=False, force=False
        )
    
    def test_simulation_mode(self):
        """Test simulation mode when methods are not available."""
        # Create an IPFS model with a mock kit that doesn't have the MFS methods
        mock_kit_no_mfs = MagicMock()
        # Remove MFS method attributes
        del mock_kit_no_mfs.files_mkdir
        del mock_kit_no_mfs.files_ls
        del mock_kit_no_mfs.files_stat
        del mock_kit_no_mfs.files_read
        del mock_kit_no_mfs.files_write
        del mock_kit_no_mfs.files_rm
        
        # Create model with this kit
        model = IPFSModel(ipfs_kit_instance=mock_kit_no_mfs)
        
        # Test mkdir in simulation mode
        mkdir_result = model.files_mkdir("/test_dir")
        self.assertTrue(mkdir_result["success"])
        self.assertTrue(mkdir_result.get("simulation", False))
        
        # Test ls in simulation mode
        ls_result = model.files_ls("/")
        self.assertTrue(ls_result["success"])
        self.assertTrue(ls_result.get("simulation", False))
        self.assertTrue(len(ls_result["entries"]) > 0)
        
        # Test stat in simulation mode
        stat_result = model.files_stat("/test_dir/test_file.txt")
        self.assertTrue(stat_result["success"])
        self.assertTrue(stat_result.get("simulation", False))
        self.assertTrue("size" in stat_result)
        self.assertTrue("type" in stat_result)
        self.assertTrue("cid" in stat_result)
        
        # Test read in simulation mode
        read_result = model.files_read("/test_dir/test_file.txt")
        self.assertTrue(read_result["success"])
        self.assertTrue(read_result.get("simulation", False))
        self.assertTrue(len(read_result["data"]) > 0)
        
        # Test write in simulation mode
        write_result = model.files_write("/test_dir/test_file.txt", "Test content")
        self.assertTrue(write_result["success"])
        self.assertTrue(write_result.get("simulation", False))
        self.assertEqual(write_result["bytes_written"], len("Test content"))
        
        # Test rm in simulation mode
        rm_result = model.files_rm("/test_dir/test_file.txt")
        self.assertTrue(rm_result["success"])
        self.assertTrue(rm_result.get("simulation", False))
    
    def test_error_handling(self):
        """Test error handling in MFS operations."""
        # Set up a mock IPFS kit that raises exceptions
        mock_kit_error = MagicMock()
        mock_kit_error.files_mkdir.side_effect = Exception("Test error")
        mock_kit_error.files_ls.side_effect = Exception("Test error")
        mock_kit_error.files_stat.side_effect = Exception("Test error")
        mock_kit_error.files_read.side_effect = Exception("Test error")
        mock_kit_error.files_write.side_effect = Exception("Test error")
        mock_kit_error.files_rm.side_effect = Exception("Test error")
        
        # Create model with this kit
        model = IPFSModel(ipfs_kit_instance=mock_kit_error)
        
        # Test mkdir error handling - should fall back to simulation
        mkdir_result = model.files_mkdir("/test_dir")
        self.assertTrue(mkdir_result["success"])  # Success as simulation is used
        self.assertTrue(mkdir_result.get("simulation", False))
        self.assertEqual(mkdir_result.get("mkdir_error"), "Test error")
        
        # Test ls error handling - should fall back to simulation
        ls_result = model.files_ls("/")
        self.assertTrue(ls_result["success"])  # Success as simulation is used
        self.assertTrue(ls_result.get("simulation", False))
        self.assertEqual(ls_result.get("ls_error"), "Test error")
        
        # Test stat error handling - should fall back to simulation
        stat_result = model.files_stat("/test_dir/test_file.txt")
        self.assertTrue(stat_result["success"])  # Success as simulation is used
        self.assertTrue(stat_result.get("simulation", False))
        self.assertEqual(stat_result.get("stat_error"), "Test error")


if __name__ == "__main__":
    unittest.main()