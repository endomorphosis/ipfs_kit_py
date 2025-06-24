"""
Tests for metadata replication functionality in the high-level API.

These tests verify that the high-level API correctly initializes and uses the
MetadataReplicationManager with the required minimum replication factor of 3.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import pytest

from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.fs_journal_replication import (
    MetadataReplicationManager,
    ReplicationLevel,
    ReplicationStatus
)


class TestHighLevelAPIMetadataReplication(unittest.TestCase):
    """Tests for the metadata replication features in the high-level API."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()

        # Create patches for required components
        self.patches = []

        # Create a config for testing
        self.config = {
            "role": "master",
            "metadata_replication": {
                "enabled": True,
                "min_replication_factor": 3,
                "target_replication_factor": 4,
                "max_replication_factor": 5,
                "replication_level": "QUORUM"
            }
        }

        # Patch create_replication_manager
        self.mock_create_manager = MagicMock()
        create_manager_patch = patch(
            'ipfs_kit_py.high_level_api.create_replication_manager',
            self.mock_create_manager
        )
        self.patches.append(create_manager_patch)

        # Start all patches
        for p in self.patches:
            p.start()

        # Create mock replication manager
        self.mock_replication_manager = MagicMock(spec=MetadataReplicationManager)
        self.mock_create_manager.return_value = self.mock_replication_manager

        # Initialize API with replication enabled
        self.api = IPFSSimpleAPI(config=self.config)

    def tearDown(self):
        """Clean up after tests."""
        # Stop all patches
        for p in self.patches:
            p.stop()

        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_metadata_replication(self):
        """Test that metadata replication is properly initialized."""
        # Verify replication manager was created with proper arguments
        self.mock_create_manager.assert_called_once()

        # Get the call arguments
        _, kwargs = self.mock_create_manager.call_args

        # Check that minimum replication factor is at least 3
        self.assertIn("config", kwargs)
        self.assertIn("min_replication_factor", kwargs["config"])
        self.assertGreaterEqual(kwargs["config"]["min_replication_factor"], 3)

        # Check target and max factors
        self.assertIn("target_replication_factor", kwargs["config"])
        self.assertEqual(kwargs["config"]["target_replication_factor"], 4)

        self.assertIn("max_replication_factor", kwargs["config"])
        self.assertEqual(kwargs["config"]["max_replication_factor"], 5)

        # Check that replication manager was attached to API
        self.assertIsNotNone(self.api.replication_manager)

    def test_register_peer(self):
        """Test registering a peer for replication."""
        # Setup mock return value
        self.mock_replication_manager.register_peer.return_value = True

        # Call the API method
        peer_id = "test-peer-123"
        metadata = {"role": "worker", "address": "192.168.1.100"}
        result = self.api.register_peer(peer_id, metadata)

        # Verify replication manager method was called
        self.mock_replication_manager.register_peer.assert_called_once_with(peer_id, metadata)

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["peer_id"], peer_id)

    def test_register_peer_failure(self):
        """Test handling of peer registration failure."""
        # Setup mock return value for failure
        self.mock_replication_manager.register_peer.return_value = False

        # Call the API method
        peer_id = "test-peer-123"
        metadata = {"role": "worker", "address": "192.168.1.100"}
        result = self.api.register_peer(peer_id, metadata)

        # Verify result reflects failure
        self.assertFalse(result["success"])
        self.assertEqual(result["peer_id"], peer_id)

    def test_unregister_peer(self):
        """Test unregistering a peer."""
        # Setup mock return value
        self.mock_replication_manager.unregister_peer = MagicMock(return_value=True)

        # Call the API method
        peer_id = "test-peer-123"
        result = self.api.unregister_peer(peer_id)

        # Verify replication manager method was called
        self.mock_replication_manager.unregister_peer.assert_called_once_with(peer_id)

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["peer_id"], peer_id)

    def test_store_metadata(self):
        """Test storing metadata with replication."""
        # Setup mock return for replication
        replication_result = {
            "success": True,
            "operation": "replicate_journal_entry",
            "entry_id": "test-entry-123",
            "status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4
        }
        self.mock_replication_manager.replicate_journal_entry.return_value = replication_result

        # Call the API method
        path = "/test/file.txt"
        metadata = {"size": 1024, "type": "text"}
        replication_level = "QUORUM"
        result = self.api.store_metadata(path, metadata, replication_level=replication_level)

        # Verify replication manager method was called
        self.mock_replication_manager.replicate_journal_entry.assert_called_once()

        # Get the call arguments
        args, _ = self.mock_replication_manager.replicate_journal_entry.call_args
        journal_entry = args[0]
        level = args[1]

        # Check journal entry contents
        self.assertEqual(journal_entry["path"], path)
        self.assertEqual(journal_entry["data"], metadata)

        # Check replication level
        self.assertEqual(level, ReplicationLevel.QUORUM)

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["path"], path)
        self.assertEqual(result["replication_status"], ReplicationStatus.COMPLETE.value)
        self.assertEqual(result["success_count"], 4)

    def test_get_metadata(self):
        """Test retrieving metadata."""
        # Setup mock return value
        mock_entry = {
            "entry_id": "test-entry-123",
            "path": "/test/file.txt",
            "data": {"size": 1024, "type": "text"},
            "timestamp": 1234567890
        }
        self.mock_replication_manager.get_journal_entry = MagicMock(return_value=mock_entry)

        # Call the API method
        path = "/test/file.txt"
        result = self.api.get_metadata(path)

        # Verify replication manager method was called
        self.mock_replication_manager.get_journal_entry.assert_called_once_with(path=path)

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["path"], path)
        self.assertEqual(result["metadata"], mock_entry["data"])

    def test_verify_metadata_replication(self):
        """Test verifying metadata replication status."""
        # Setup mock return value
        replication_status = {
            "entry_id": "test-entry-123",
            "status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4,
            "quorum_size": 3
        }
        self.mock_replication_manager.get_replication_status = MagicMock(return_value=replication_status)

        # Call the API method
        entry_id = "test-entry-123"
        result = self.api.verify_metadata_replication(entry_id)

        # Verify replication manager method was called
        self.mock_replication_manager.get_replication_status.assert_called_once_with(entry_id)

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["entry_id"], entry_id)
        self.assertEqual(result["replication_status"], ReplicationStatus.COMPLETE.value)
        self.assertEqual(result["success_count"], 4)
        self.assertEqual(result["target_count"], 4)
        # Verify minimum replication factor of 3 is reported
        self.assertEqual(result["quorum_size"], 3)

    def test_init_without_metadata_replication(self):
        """Test that API works properly when metadata replication is disabled."""
        # Create API with replication disabled
        config_no_replication = {
            "role": "leecher",
            "metadata_replication": {
                "enabled": False
            }
        }

        api_no_replication = IPFSSimpleAPI(config=config_no_replication)

        # Verify replication manager is None
        self.assertIsNone(api_no_replication.replication_manager)

        # Verify API functions gracefully when replication is disabled
        result = api_no_replication.register_peer("test-peer", {})
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Metadata replication not enabled")

    def test_min_factor_at_least_three(self):
        """Test that the minimum replication factor is forced to at least 3."""
        # Create config with too low min_replication_factor
        config_low_min = {
            "role": "master",
            "metadata_replication": {
                "enabled": True,
                "min_replication_factor": 1,  # This should be increased to 3
                "target_replication_factor": 2,
                "max_replication_factor": 3
            }
        }

        # Reset mock to track new calls
        self.mock_create_manager.reset_mock()

        # Create new API with this config
        api_low_min = IPFSSimpleAPI(config=config_low_min)

        # Verify replication manager was created with properly adjusted min factor
        _, kwargs = self.mock_create_manager.call_args
        self.assertGreaterEqual(kwargs["config"]["min_replication_factor"], 3,
                             "Minimum replication factor should be at least 3")

        # Verify target is at least min
        self.assertGreaterEqual(
            kwargs["config"]["target_replication_factor"],
            kwargs["config"]["min_replication_factor"],
            "Target replication factor should be at least min_replication_factor"
        )

        # Verify max is at least target
        self.assertGreaterEqual(
            kwargs["config"]["max_replication_factor"],
            kwargs["config"]["target_replication_factor"],
            "Maximum replication factor should be at least target_replication_factor"
        )


if __name__ == "__main__":
    unittest.main()
