#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Filesystem Journal (Phase 1)

Tests all core functionality of the FilesystemJournal class including:
- Journal initialization
- Operation recording
- Transaction management
- Checkpointing
- Recovery
- Status tracking
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.filesystem_journal import (
    FilesystemJournal,
    JournalOperationType,
    JournalEntryStatus
)


class TestFilesystemJournalInitialization(unittest.TestCase):
    """Test journal initialization and configuration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.test_dir, "journal")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_init_default_values(self):
        """Test journal initialization with default values."""
        journal = FilesystemJournal(base_path=self.journal_path)
        
        self.assertIsNotNone(journal)
        self.assertTrue(os.path.exists(os.path.expanduser(self.journal_path)))
        self.assertEqual(journal.sync_interval, 5)
        self.assertEqual(journal.checkpoint_interval, 60)
        self.assertEqual(journal.max_journal_size, 1000)
    
    def test_init_custom_values(self):
        """Test journal initialization with custom values."""
        journal = FilesystemJournal(
            base_path=self.journal_path,
            sync_interval=10,
            checkpoint_interval=120,
            max_journal_size=500,
            auto_recovery=False
        )
        
        self.assertEqual(journal.sync_interval, 10)
        self.assertEqual(journal.checkpoint_interval, 120)
        self.assertEqual(journal.max_journal_size, 500)
    
    def test_init_creates_directory(self):
        """Test that initialization creates journal directory."""
        journal = FilesystemJournal(base_path=self.journal_path)
        journal_dir = os.path.expanduser(self.journal_path)
        
        self.assertTrue(os.path.exists(journal_dir))
        self.assertTrue(os.path.isdir(journal_dir))
    
    def test_init_with_existing_directory(self):
        """Test initialization with existing directory doesn't fail."""
        os.makedirs(self.journal_path, exist_ok=True)
        journal = FilesystemJournal(base_path=self.journal_path)
        
        self.assertIsNotNone(journal)


class TestFilesystemJournalOperations(unittest.TestCase):
    """Test journal operation recording."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.test_dir, "journal")
        self.journal = FilesystemJournal(
            base_path=self.journal_path,
            auto_recovery=False
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, 'journal'):
            try:
                self.journal.close()
            except:
                pass
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_record_create_operation(self):
        """Test recording a create operation."""
        entry_id = self.journal.record_operation(
            operation_type=JournalOperationType.CREATE,
            path="/test/file.txt",
            details={"size": 1024}
        )
        
        self.assertIsNotNone(entry_id)
        self.assertTrue(len(entry_id) > 0)
    
    def test_record_delete_operation(self):
        """Test recording a delete operation."""
        entry_id = self.journal.record_operation(
            operation_type=JournalOperationType.DELETE,
            path="/test/file.txt"
        )
        
        self.assertIsNotNone(entry_id)
    
    def test_record_write_operation(self):
        """Test recording a write operation."""
        entry_id = self.journal.record_operation(
            operation_type=JournalOperationType.WRITE,
            path="/test/file.txt",
            details={"offset": 0, "length": 512}
        )
        
        self.assertIsNotNone(entry_id)
    
    def test_record_mount_operation(self):
        """Test recording a mount operation."""
        entry_id = self.journal.record_operation(
            operation_type=JournalOperationType.MOUNT,
            path="/mnt/ipfs/QmTest",
            details={"cid": "QmTest123"}
        )
        
        self.assertIsNotNone(entry_id)
    
    def test_get_pending_operations(self):
        """Test retrieving pending operations."""
        # Record some operations
        self.journal.record_operation(
            JournalOperationType.CREATE,
            "/test1.txt"
        )
        self.journal.record_operation(
            JournalOperationType.WRITE,
            "/test2.txt"
        )
        
        pending = self.journal.get_pending_operations()
        self.assertIsInstance(pending, list)
        self.assertGreaterEqual(len(pending), 2)


class TestFilesystemJournalStatus(unittest.TestCase):
    """Test journal status management."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.test_dir, "journal")
        self.journal = FilesystemJournal(
            base_path=self.journal_path,
            auto_recovery=False
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, 'journal'):
            try:
                self.journal.close()
            except:
                pass
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_mark_operation_completed(self):
        """Test marking an operation as completed."""
        entry_id = self.journal.record_operation(
            JournalOperationType.CREATE,
            "/test.txt"
        )
        
        result = self.journal.mark_completed(entry_id)
        self.assertTrue(result)
    
    def test_mark_operation_failed(self):
        """Test marking an operation as failed."""
        entry_id = self.journal.record_operation(
            JournalOperationType.DELETE,
            "/test.txt"
        )
        
        result = self.journal.mark_failed(entry_id, reason="Test failure")
        self.assertTrue(result)
    
    def test_get_journal_status(self):
        """Test getting journal status."""
        # Record some operations
        self.journal.record_operation(JournalOperationType.CREATE, "/test1.txt")
        entry_id = self.journal.record_operation(JournalOperationType.WRITE, "/test2.txt")
        self.journal.mark_completed(entry_id)
        
        status = self.journal.get_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn("total_entries", status)
        self.assertIn("pending_entries", status)
        self.assertIn("completed_entries", status)


class TestFilesystemJournalCheckpointing(unittest.TestCase):
    """Test journal checkpointing functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.test_dir, "journal")
        self.journal = FilesystemJournal(
            base_path=self.journal_path,
            auto_recovery=False
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, 'journal'):
            try:
                self.journal.close()
            except:
                pass
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_create_checkpoint(self):
        """Test creating a checkpoint."""
        # Record some operations
        for i in range(5):
            entry_id = self.journal.record_operation(
                JournalOperationType.CREATE,
                f"/test{i}.txt"
            )
            self.journal.mark_completed(entry_id)
        
        checkpoint_id = self.journal.create_checkpoint(
            description="Test checkpoint"
        )
        
        self.assertIsNotNone(checkpoint_id)
        self.assertTrue(len(checkpoint_id) > 0)
    
    def test_list_checkpoints(self):
        """Test listing checkpoints."""
        # Create some checkpoints
        self.journal.create_checkpoint("Checkpoint 1")
        self.journal.create_checkpoint("Checkpoint 2")
        
        checkpoints = self.journal.list_checkpoints()
        
        self.assertIsInstance(checkpoints, list)
        self.assertGreaterEqual(len(checkpoints), 2)


class TestFilesystemJournalRecovery(unittest.TestCase):
    """Test journal recovery functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.test_dir, "journal")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_recovery_on_startup(self):
        """Test that recovery runs on startup with auto_recovery=True."""
        # Create journal with some operations
        journal1 = FilesystemJournal(
            base_path=self.journal_path,
            auto_recovery=False
        )
        journal1.record_operation(JournalOperationType.CREATE, "/test.txt")
        journal1.close()
        
        # Create new journal with auto_recovery
        journal2 = FilesystemJournal(
            base_path=self.journal_path,
            auto_recovery=True
        )
        
        # Should have recovered entries
        status = journal2.get_status()
        self.assertGreater(status.get("total_entries", 0), 0)
        
        journal2.close()
    
    def test_manual_recovery(self):
        """Test manual recovery."""
        journal = FilesystemJournal(
            base_path=self.journal_path,
            auto_recovery=False
        )
        
        # Record some operations
        journal.record_operation(JournalOperationType.CREATE, "/test.txt")
        
        # Manually trigger recovery
        result = journal.recover()
        
        # Should succeed (returns True or dict with success info)
        self.assertIsNotNone(result)
        
        journal.close()


class TestFilesystemJournalCleanup(unittest.TestCase):
    """Test journal cleanup and maintenance."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.test_dir, "journal")
        self.journal = FilesystemJournal(
            base_path=self.journal_path,
            auto_recovery=False
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, 'journal'):
            try:
                self.journal.close()
            except:
                pass
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_cleanup_old_entries(self):
        """Test cleanup of old completed entries."""
        # Record and complete some operations
        for i in range(10):
            entry_id = self.journal.record_operation(
                JournalOperationType.CREATE,
                f"/test{i}.txt"
            )
            self.journal.mark_completed(entry_id)
        
        # Cleanup old entries (age=0 to clean all completed)
        result = self.journal.cleanup(keep_days=0)
        
        self.assertIsNotNone(result)
    
    def test_close_journal(self):
        """Test closing the journal."""
        # Record some operations
        self.journal.record_operation(JournalOperationType.CREATE, "/test.txt")
        
        # Close should not raise exceptions
        self.journal.close()


if __name__ == '__main__':
    unittest.main()
