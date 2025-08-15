import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Import the actual class instead of mocking it
import sys
from ipfs_kit_py.migration_tools.s3_to_storacha import s3_to_storacha
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


@pytest.fixture
def migration_setup():
    """Set up test fixtures for migration tests."""
    # Create mock resources and metadata
    resources = {"cpu": 2, "memory": "4GB"}
    metadata = {"role": "leecher"}

    # Create a temporary test file
    temp_dir = tempfile.mkdtemp(prefix="test_s3_to_storacha_")
    test_file_path = os.path.join(temp_dir, "test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("This is test content for S3 to Storacha migration")

    # Create mock objects
    mock_storacha_kit = MagicMock()
    mock_s3_kit = MagicMock()

    # Configure mock responses
    mock_s3_kit.s3_dl_file.return_value = {
        "success": True,
        "key": "test/test_file.txt",
        "last_modified": 1234567890.0,
        "size": 42,
        "e_tag": "abcdef123456",
        "local_path": test_file_path,
    }

    mock_s3_kit.s3_ls_dir.return_value = [
        {
            "key": "test/test_file1.txt",
            "last_modified": 1234567890.0,
            "size": 42,
            "e_tag": "abcdef123456",
        },
        {
            "key": "test/test_file2.txt",
            "last_modified": 1234567890.0,
            "size": 24,
            "e_tag": "abcdef654321",
        },
    ]

    mock_s3_kit.s3_ls_file.return_value = {
        "test/test_file.txt": {
            "key": "test/test_file.txt",
            "last_modified": 1234567890.0,
            "size": 42,
            "e_tag": "abcdef123456",
        }
    }

    mock_storacha_kit.store_add.return_value = {
        "success": True,
        "cid": "bafy2bzacedfake123",
        "size": 42,
    }

    mock_storacha_kit.space_add_cids.return_value = {
        "success": True,
        "space": "test-space",
        "cids": ["bafy2bzacedfake123", "bafy2bzacedfake456"],
        "count": 2,
    }

    # Create migration instance
    with patch("ipfs_kit_py.s3_kit.s3_kit", return_value=mock_s3_kit), patch(
        "ipfs_kit_py.storacha_kit.storacha_kit", return_value=mock_storacha_kit
    ):
        migration = s3_to_storacha(resources, metadata)

        # Make sure temp_dir exists
        if not hasattr(migration, "temp_dir"):
            migration.temp_dir = tempfile.mkdtemp(prefix="s3_to_storacha_")

    # Return everything needed by tests
    yield {
        "migration": migration,
        "resources": resources,
        "metadata": metadata,
        "temp_dir": temp_dir,
        "test_file_path": test_file_path,
        "mock_storacha_kit": mock_storacha_kit,
        "mock_s3_kit": mock_s3_kit,
    }

    # Clean up temp dir
    shutil.rmtree(temp_dir)

    # Clean up migration's temp dir if it exists
    if hasattr(migration, "temp_dir") and os.path.exists(migration.temp_dir):
        try:
            shutil.rmtree(migration.temp_dir)
        except Exception:
            pass


class TestS3ToStoracha:
    """Test the S3 to Storacha migration tool."""

    def test_init(self, migration_setup):
        """Test initialization of the migration tool."""
        migration = migration_setup["migration"]
        resources = migration_setup["resources"]
        metadata = migration_setup["metadata"]

        # Assertions
        assert migration.resources == resources
        assert migration.metadata == metadata
        assert migration.storacha_kit == migration_setup["mock_storacha_kit"]
        assert migration.s3_kit == migration_setup["mock_s3_kit"]

    def test_migrate_file(self, migration_setup):
        """Test migrating a single file from S3 to Storacha."""
        migration = migration_setup["migration"]
        mock_s3_kit = migration_setup["mock_s3_kit"]
        mock_storacha_kit = migration_setup["mock_storacha_kit"]

        # Test the migrate_file method
        result = migration.migrate_file("test/test_file.txt")

        # Verify method calls
        mock_s3_kit.s3_dl_file.assert_called_once()
        mock_storacha_kit.store_add.assert_called_once()

        # Verify results
        assert result["success"] is True
        assert "cid" in result
        assert result["cid"] == "bafy2bzacedfake123"
        assert result["operation"] == "migrate_file"
        assert result["s3_key"] == "test/test_file.txt"

    def test_migrate_directory(self, migration_setup):
        """Test migrating a directory from S3 to Storacha."""
        migration = migration_setup["migration"]
        mock_s3_kit = migration_setup["mock_s3_kit"]

        # Test the migrate_directory method
        result = migration.migrate_directory("test/")

        # Verify method calls
        mock_s3_kit.s3_ls_dir.assert_called_once_with("test/")
        assert mock_s3_kit.s3_dl_file.call_count == 2

        # Verify results
        assert result["success"] is True
        assert result["files_migrated"] == 2
        assert result["files_failed"] == 0
        assert "test/test_file1.txt" in result["file_results"]
        assert "test/test_file2.txt" in result["file_results"]

    def test_migrate_by_list(self, migration_setup):
        """Test migrating a list of files from S3 to Storacha."""
        migration = migration_setup["migration"]
        mock_s3_kit = migration_setup["mock_s3_kit"]

        # Test the migrate_by_list method
        result = migration.migrate_by_list(["test/file1.txt", "test/file2.txt"])

        # Verify method calls
        assert mock_s3_kit.s3_dl_file.call_count == 2

        # Verify results
        assert result["success"] is True
        assert result["files_migrated"] == 2
        assert result["files_failed"] == 0
        assert len(result["cids"]) == 2
        assert "test/file1.txt" in result["file_results"]
        assert "test/file2.txt" in result["file_results"]
        assert result["operation"] == "migrate_by_list"

    def test_migrate_empty_list(self, migration_setup):
        """Test migrating an empty list."""
        migration = migration_setup["migration"]
        mock_s3_kit = migration_setup["mock_s3_kit"]

        # Test with empty list
        result = migration.migrate_by_list([])

        # Verify no methods were called
        mock_s3_kit.s3_dl_file.assert_not_called()

        # Verify results
        assert result["success"] is True
        assert "warning" in result
        assert result["files_migrated"] == 0
        assert result["files_failed"] == 0
        assert result["s3_key_count"] == 0

    def test_migrate_file_failure(self, migration_setup):
        """Test handling of failures during file migration."""
        migration = migration_setup["migration"]
        mock_s3_kit = migration_setup["mock_s3_kit"]

        # Configure mock to simulate failure
        mock_s3_kit.s3_dl_file.return_value = {
            "success": False,
            "error": "File not found",
            "error_type": "NotFoundError",
        }

        # Test method with simulated failure
        result = migration.migrate_file("test/nonexistent.txt")

        # Verify results
        assert result["success"] is False
        assert "error" in result
        assert "error_type" in result
        assert "File not found" in result["error"]

    def test_cleanup(self, migration_setup):
        """Test cleanup of temporary resources."""
        migration = migration_setup["migration"]
        temp_dir = migration.temp_dir

        # Create a test file in the temp directory
        test_file = os.path.join(temp_dir, "cleanup_test.txt")
        with open(test_file, "w") as f:
            f.write("Test content for cleanup")

        # Verify the file exists
        assert os.path.exists(test_file)

        # Call cleanup
        migration.cleanup()

        # Verify the directory is gone
        assert not os.path.exists(temp_dir)
