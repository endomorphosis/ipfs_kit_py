#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Filesystem Journal MCP Tools (Phase 1)

Tests all MCP tools for journal operations including:
- journal_enable
- journal_status
- journal_list_entries
- journal_checkpoint
- journal_recover
- journal_mount
- journal_mkdir
- journal_write
- journal_read
- journal_rm
- journal_mv
- journal_ls
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.mcp.servers.fs_journal_mcp_tools import (
    journal_enable,
    journal_status,
    journal_list_entries,
    journal_checkpoint,
    journal_recover,
    journal_mount,
    journal_mkdir,
    journal_write,
    journal_read,
    journal_rm,
    journal_mv,
    journal_ls
)


class TestJournalEnableMCPTool(unittest.TestCase):
    """Test journal_enable MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.FilesystemJournal')
    def test_journal_enable_default(self, mock_journal_class):
        """Test enabling journal with default parameters."""
        mock_journal = Mock()
        mock_journal_class.return_value = mock_journal
        
        result = journal_enable()
        
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.FilesystemJournal')
    def test_journal_enable_custom_path(self, mock_journal_class):
        """Test enabling journal with custom path."""
        mock_journal = Mock()
        mock_journal_class.return_value = mock_journal
        
        result = journal_enable(journal_path="/custom/path")
        
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.FilesystemJournal')
    def test_journal_enable_custom_intervals(self, mock_journal_class):
        """Test enabling journal with custom intervals."""
        mock_journal = Mock()
        mock_journal_class.return_value = mock_journal
        
        result = journal_enable(
            sync_interval=10,
            checkpoint_interval=120
        )
        
        self.assertTrue(result.get("success"))


class TestJournalStatusMCPTool(unittest.TestCase):
    """Test journal_status MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_journal_status_enabled(self, mock_get_journal):
        """Test getting status of enabled journal."""
        mock_journal = Mock()
        mock_journal.get_status.return_value = {
            "enabled": True,
            "total_entries": 100,
            "pending_entries": 5
        }
        mock_get_journal.return_value = mock_journal
        
        result = journal_status()
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertIn("status", result)
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_journal_status_disabled(self, mock_get_journal):
        """Test getting status when journal is disabled."""
        mock_get_journal.return_value = None
        
        result = journal_status()
        
        self.assertIsInstance(result, dict)
        self.assertIn("enabled", result)
        self.assertFalse(result.get("enabled"))


class TestJournalListEntriesMCPTool(unittest.TestCase):
    """Test journal_list_entries MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_list_all_entries(self, mock_get_journal):
        """Test listing all entries."""
        mock_journal = Mock()
        mock_journal.get_entries.return_value = [
            {"id": "1", "operation": "create", "path": "/test1.txt"},
            {"id": "2", "operation": "write", "path": "/test2.txt"}
        ]
        mock_get_journal.return_value = mock_journal
        
        result = journal_list_entries()
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertIn("entries", result)
        self.assertEqual(len(result["entries"]), 2)
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_list_entries_with_filter(self, mock_get_journal):
        """Test listing entries with status filter."""
        mock_journal = Mock()
        mock_journal.get_entries.return_value = [
            {"id": "1", "status": "pending"}
        ]
        mock_get_journal.return_value = mock_journal
        
        result = journal_list_entries(status="pending")
        
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_list_entries_with_limit(self, mock_get_journal):
        """Test listing entries with limit."""
        mock_journal = Mock()
        mock_journal.get_entries.return_value = []
        mock_get_journal.return_value = mock_journal
        
        result = journal_list_entries(limit=50)
        
        self.assertTrue(result.get("success"))


class TestJournalCheckpointMCPTool(unittest.TestCase):
    """Test journal_checkpoint MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_create_checkpoint(self, mock_get_journal):
        """Test creating a checkpoint."""
        mock_journal = Mock()
        mock_journal.create_checkpoint.return_value = "checkpoint_123"
        mock_get_journal.return_value = mock_journal
        
        result = journal_checkpoint(description="Test checkpoint")
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertIn("checkpoint_id", result)
        self.assertEqual(result["checkpoint_id"], "checkpoint_123")
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_create_checkpoint_no_journal(self, mock_get_journal):
        """Test creating checkpoint when journal is disabled."""
        mock_get_journal.return_value = None
        
        result = journal_checkpoint()
        
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success"))
        self.assertIn("error", result)


class TestJournalRecoverMCPTool(unittest.TestCase):
    """Test journal_recover MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_recover_from_checkpoint(self, mock_get_journal):
        """Test recovering from a checkpoint."""
        mock_journal = Mock()
        mock_journal.recover.return_value = {
            "success": True,
            "recovered_operations": 10
        }
        mock_get_journal.return_value = mock_journal
        
        result = journal_recover(checkpoint_id="checkpoint_123")
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_recover_without_checkpoint(self, mock_get_journal):
        """Test recovering without specifying checkpoint."""
        mock_journal = Mock()
        mock_journal.recover.return_value = {"success": True}
        mock_get_journal.return_value = mock_journal
        
        result = journal_recover()
        
        self.assertTrue(result.get("success"))


class TestJournalMountMCPTool(unittest.TestCase):
    """Test journal_mount MCP tool."""
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_mount_cid(self, mock_get_journal):
        """Test mounting a CID."""
        mock_journal = Mock()
        mock_journal.record_operation.return_value = "entry_123"
        mock_get_journal.return_value = mock_journal
        
        result = journal_mount(
            cid="QmTest123",
            path="/mnt/ipfs/QmTest"
        )
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertIn("entry_id", result)


class TestJournalFilesystemOperations(unittest.TestCase):
    """Test journal filesystem operation MCP tools."""
    
    def setUp(self):
        """Set up mocks."""
        self.mock_journal = Mock()
        self.mock_journal.record_operation.return_value = "entry_123"
        self.mock_journal.mark_completed.return_value = True
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_journal_mkdir(self, mock_get_journal):
        """Test creating directory via journal."""
        mock_get_journal.return_value = self.mock_journal
        
        result = journal_mkdir(path="/test/dir")
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_journal_write(self, mock_get_journal):
        """Test writing file via journal."""
        mock_get_journal.return_value = self.mock_journal
        
        result = journal_write(
            path="/test/file.txt",
            content="Test content"
        )
        
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_journal_read(self, mock_get_journal):
        """Test reading file via journal."""
        mock_get_journal.return_value = self.mock_journal
        self.mock_journal.read_file.return_value = "File content"
        
        result = journal_read(path="/test/file.txt")
        
        self.assertTrue(result.get("success"))
        self.assertIn("content", result)
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_journal_rm(self, mock_get_journal):
        """Test removing file via journal."""
        mock_get_journal.return_value = self.mock_journal
        
        result = journal_rm(path="/test/file.txt")
        
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_journal_mv(self, mock_get_journal):
        """Test moving/renaming file via journal."""
        mock_get_journal.return_value = self.mock_journal
        
        result = journal_mv(
            source="/test/old.txt",
            destination="/test/new.txt"
        )
        
        self.assertTrue(result.get("success"))
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_journal_ls(self, mock_get_journal):
        """Test listing directory via journal."""
        mock_get_journal.return_value = self.mock_journal
        self.mock_journal.list_directory.return_value = [
            {"name": "file1.txt", "type": "file"},
            {"name": "file2.txt", "type": "file"}
        ]
        
        result = journal_ls(path="/test")
        
        self.assertTrue(result.get("success"))
        self.assertIn("entries", result)
        self.assertEqual(len(result["entries"]), 2)


class TestJournalErrorHandling(unittest.TestCase):
    """Test error handling in journal MCP tools."""
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_operation_without_journal(self, mock_get_journal):
        """Test operations when journal is not enabled."""
        mock_get_journal.return_value = None
        
        result = journal_mkdir(path="/test")
        
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success"))
        self.assertIn("error", result)
    
    @patch('ipfs_kit_py.mcp.servers.fs_journal_mcp_tools.get_journal')
    def test_operation_with_exception(self, mock_get_journal):
        """Test error handling when operation raises exception."""
        mock_journal = Mock()
        mock_journal.record_operation.side_effect = Exception("Test error")
        mock_get_journal.return_value = mock_journal
        
        result = journal_mkdir(path="/test")
        
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success"))
        self.assertIn("error", result)


if __name__ == '__main__':
    unittest.main()
