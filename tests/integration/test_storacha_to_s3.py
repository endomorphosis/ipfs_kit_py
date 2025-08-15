import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

import sys
from ipfs_kit_py.migration_tools.storacha_to_s3 import storacha_to_s3
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


@pytest.fixture
def migration_setup():
    """Set up test fixtures for storacha_to_s3 migration tests."""
    # Create mock resources and metadata
    resources = {"cpu": 2, "memory": "4GB"}
    metadata = {"role": "leecher"}

    # Create a temporary test file
    temp_dir = tempfile.mkdtemp(prefix="test_storacha_to_s3_")
    test_file_path = os.path.join(temp_dir, "test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("This is test content for Storacha to S3 migration")

    # Create patches for the dependencies
    mock_storacha_kit = MagicMock()
    mock_s3_kit = MagicMock()

    # Configure mock responses
    mock_storacha_kit.store_get.return_value = {
        "success": True,
        "cid": "bagbaiera123",
        "output_file": test_file_path,
    }

    mock_storacha_kit.store_ls.return_value = {
        "success": True,
        "files": [
            {"name": "file1.txt", "cid": "bagbaiera123file1", "size": 42},
            {"name": "file2.txt", "cid": "bagbaiera123file2", "size": 24},
        ],
    }

    mock_s3_kit.s3_ul_file.return_value = {
        "key": "test/test_file.txt",
        "last_modified": 1234567890.0,
        "size": 42,
        "e_tag": "abcdef123456",
    }

    mock_s3_kit.s3_ls_file.return_value = {
        "test/test_file.txt": {
            "key": "test/test_file.txt",
            "last_modified": 1234567890.0,
            "size": 42,
            "e_tag": "abcdef123456",
        }
    }

    # Start patching
    storacha_kit_patcher = patch(
        "ipfs_kit_py.migration_tools.storacha_to_s3.storacha_kit",
        return_value=mock_storacha_kit,
    )
    s3_kit_patcher = patch(
        "ipfs_kit_py.migration_tools.storacha_to_s3.s3_kit", return_value=mock_s3_kit
    )

    mock_storacha_kit_class = storacha_kit_patcher.start()
    mock_s3_kit_class = s3_kit_patcher.start()

    # Create migration instance with mocked dependencies
    migration = storacha_to_s3(resources, metadata)

    # Replace the cleanup method to prevent removal of temp dir during tests
    original_cleanup = migration.cleanup
    migration.cleanup = MagicMock()

    # Create a fixture data structure to return everything needed for tests
    fixture_data = {
        "migration": migration,
        "mock_storacha_kit": mock_storacha_kit,
        "mock_s3_kit": mock_s3_kit,
        "resources": resources,
        "metadata": metadata,
        "temp_dir": temp_dir,
        "test_file_path": test_file_path,
        "original_cleanup": original_cleanup,
        "patchers": [storacha_kit_patcher, s3_kit_patcher],
    }

    # Return the fixture data
    yield fixture_data

    # Teardown - stop patching
    for patcher in fixture_data["patchers"]:
        patcher.stop()

    # Clean up temp dir
    shutil.rmtree(temp_dir)


def test_init(migration_setup):
    """Test initialization of the migration tool."""
    migration = migration_setup["migration"]
    resources = migration_setup["resources"]
    metadata = migration_setup["metadata"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    assert migration.resources == resources
    assert migration.metadata == metadata
    assert migration.temp_dir is not None
    assert os.path.exists(migration.temp_dir)
    assert migration.storacha_kit == mock_storacha_kit
    assert migration.s3_kit == mock_s3_kit


def test_migrate_file(migration_setup):
    """Test migrating a single file from Storacha to S3."""
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    result = migration.migrate_file(
        "test-space", "bagbaiera123", "test-bucket", "test/test_file.txt"
    )

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_file"
    assert result["source"]["type"] == "storacha"
    assert result["source"]["space"] == "test-space"
    assert result["source"]["cid"] == "bagbaiera123"
    assert result["destination"]["type"] == "s3"
    assert result["destination"]["bucket"] == "test-bucket"
    assert result["destination"]["path"] == "test/test_file.txt"

    # Verify the right methods were called
    mock_storacha_kit.store_get.assert_called_once()
    mock_s3_kit.s3_ul_file.assert_called_once()
    mock_s3_kit.s3_ls_file.assert_called_once()


def test_migrate_directory(migration_setup):
    """Test migrating a directory from Storacha to S3."""
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    result = migration.migrate_directory("test-space", "bagbaiera123dir", "test-bucket", "test/")

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_directory"
    assert result["total_files"] == 2
    assert result["successful_migrations"] == 2
    assert result["failed_migrations"] == 0

    # Verify the right methods were called
    mock_storacha_kit.store_ls.assert_called_once()
    assert mock_storacha_kit.store_get.call_count == 2
    assert mock_s3_kit.s3_ul_file.call_count == 2
    assert mock_s3_kit.s3_ls_file.call_count == 2


def test_migrate_by_list(migration_setup):
    """Test migrating a list of files from Storacha to S3."""
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    file_list = [
        {"cid": "bagbaiera123file1", "name": "file1.txt"},
        {"cid": "bagbaiera123file2", "name": "file2.txt"},
    ]

    result = migration.migrate_by_list("test-space", file_list, "test-bucket", "test/")

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_by_list"
    assert result["total_files"] == 2
    assert result["successful_migrations"] == 2
    assert result["failed_migrations"] == 0

    # Verify the right methods were called
    assert mock_storacha_kit.store_get.call_count == 2
    assert mock_s3_kit.s3_ul_file.call_count == 2
    assert mock_s3_kit.s3_ls_file.call_count == 2


def test_migrate_empty_list(migration_setup):
    """Test migrating an empty list."""
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    result = migration.migrate_by_list("test-space", [], "test-bucket", "test/")

    # Verify result structure and success
    assert result["success"] is True
    assert "warning" in result
    assert result["migrated_files"] == []

    # Verify no methods were called
    mock_storacha_kit.store_get.assert_not_called()
    mock_s3_kit.s3_ul_file.assert_not_called()
    mock_s3_kit.s3_ls_file.assert_not_called()


def test_migrate_file_failure_download(migration_setup):
    """Test handling of failures during file download from Storacha."""
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    # Configure Storacha download to fail
    mock_storacha_kit.store_get.return_value = {
        "success": False,
        "error": "Content not found",
    }

    result = migration.migrate_file(
        "test-space", "bagbaiera123", "test-bucket", "test/test_file.txt"
    )

    # Verify result structure and failure
    assert result["success"] is False
    assert "error" in result

    # Verify S3 methods were not called
    mock_s3_kit.s3_ul_file.assert_not_called()
    mock_s3_kit.s3_ls_file.assert_not_called()


def test_migrate_file_failure_upload(migration_setup):
    """Test handling of failures during file upload to S3."""
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    # Configure S3 upload to fail
    mock_s3_kit.s3_ul_file.return_value = None

    result = migration.migrate_file(
        "test-space", "bagbaiera123", "test-bucket", "test/test_file.txt"
    )

    # Verify result structure and failure
    assert result["success"] is False
    assert "error" in result

    # Verify methods were called in the right order
    mock_storacha_kit.store_get.assert_called_once()
    mock_s3_kit.s3_ul_file.assert_called_once()
    mock_s3_kit.s3_ls_file.assert_not_called()


def test_cleanup(migration_setup):
    """Test cleanup of temporary resources."""
    migration = migration_setup["migration"]
    original_cleanup = migration_setup["original_cleanup"]

    # Restore the original cleanup method
    migration.cleanup = original_cleanup

    # Create a temporary directory for testing cleanup
    test_temp_dir = tempfile.mkdtemp(prefix="test_cleanup_")
    migration.temp_dir = test_temp_dir

    # Call cleanup
    migration.cleanup()

    # Verify the directory was removed
    assert not os.path.exists(test_temp_dir)
