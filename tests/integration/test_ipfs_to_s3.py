import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

import sys
from ipfs_kit_py.migration_tools.ipfs_to_s3 import ipfs_to_s3
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


# Setup fixture for test
@pytest.fixture
def migration_setup(mock_ipfs):
    """Set up test fixtures for ipfs_to_s3 migration tests."""
    # Create mock resources and metadata
    resources = {"cpu": 2, "memory": "4GB"}
    metadata = {"role": "leecher"}

    # Create a temporary test file
    temp_dir = tempfile.mkdtemp(prefix="test_ipfs_to_s3_")
    test_file_path = os.path.join(temp_dir, "test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("This is test content for IPFS to S3 migration")

    # Create patches for the dependencies
    mock_s3_kit = MagicMock()
    # Use the provided mock_ipfs fixture
    mock_ipfs_kit = mock_ipfs.return_value

    # Configure mock responses
    mock_ipfs_kit.ipfs_cat.return_value = {
        "success": True,
        "data": b"This is test content for IPFS to S3 migration",
        "size": 42,
    }

    mock_ipfs_kit.ipfs_ls_path.return_value = {
        "success": True,
        "links": [
            {"Name": "file1.txt", "Hash": "QmTest123File1", "Size": 42, "Type": 2},  # File
            {"Name": "file2.txt", "Hash": "QmTest123File2", "Size": 24, "Type": 2},  # File
            {"Name": "subdir", "Hash": "QmTest123Dir", "Size": 0, "Type": 1},  # Directory
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
    # The actual imports occur inside the class constructor, so we need to patch there
    s3_kit_patcher = patch("ipfs_kit_py.s3_kit.s3_kit", return_value=mock_s3_kit)
    ipfs_kit_patcher = patch("ipfs_kit_py.ipfs.ipfs_py", return_value=mock_ipfs_kit)

    mock_s3_kit_class = s3_kit_patcher.start()
    mock_ipfs_kit_class = ipfs_kit_patcher.start()

    # Create migration instance with mocked dependencies
    migration = ipfs_to_s3(resources, metadata)

    # Replace the cleanup method to prevent removal of temp dir during tests
    original_cleanup = migration.cleanup
    migration.cleanup = MagicMock()

    # Create a fixture data structure to return everything needed for tests
    fixture_data = {
        "migration": migration,
        "resources": resources,
        "metadata": metadata,
        "temp_dir": temp_dir,
        "test_file_path": test_file_path,
        "mock_s3_kit": mock_s3_kit,
        "mock_ipfs_kit": mock_ipfs_kit,
        "original_cleanup": original_cleanup,
        "s3_kit_patcher": s3_kit_patcher,
        "ipfs_kit_patcher": ipfs_kit_patcher,
    }

    # Return the fixture data
    yield fixture_data

    # Teardown - stop patching
    s3_kit_patcher.stop()
    ipfs_kit_patcher.stop()

    # Restore original cleanup method
    migration.cleanup = original_cleanup

    # Clean up temp dir
    shutil.rmtree(temp_dir)


def test_init(migration_setup):
    """Test initialization of the migration tool."""
    migration = migration_setup["migration"]
    resources = migration_setup["resources"]
    metadata = migration_setup["metadata"]

    assert migration.resources == resources
    assert migration.metadata == metadata
    assert migration.temp_dir is not None
    assert os.path.exists(migration.temp_dir)
    assert migration.s3_kit == migration_setup["mock_s3_kit"]
    assert migration.ipfs == migration_setup["mock_ipfs_kit"]


def test_migrate_file(migration_setup):
    """Test migrating a single file from IPFS to S3."""
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    result = migration.migrate_file("QmTest123", "test-bucket", "test/test_file.txt")

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_file"
    assert result["source"]["type"] == "ipfs"
    assert result["source"]["cid"] == "QmTest123"
    assert result["destination"]["type"] == "s3"
    assert result["destination"]["bucket"] == "test-bucket"
    assert result["destination"]["path"] == "test/test_file.txt"

    # Verify the right methods were called
    mock_ipfs_kit.ipfs_cat.assert_called_once_with("QmTest123")
    mock_s3_kit.s3_ul_file.assert_called_once()
    mock_s3_kit.s3_ls_file.assert_called_once()


def test_migrate_file_with_filename(migration_setup):
    """Test migrating a file with a specific filename."""
    migration = migration_setup["migration"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    result = migration.migrate_file(
        "QmTest123", "test-bucket", "test/", file_name="custom_name.txt"
    )

    # Verify result structure and success
    assert result["success"] is True

    # Verify the file name was used
    # Find the args used in the call to s3_ul_file
    call_args = mock_s3_kit.s3_ul_file.call_args[0]
    assert "custom_name.txt" in call_args[0]  # First arg should be the temp file path


def test_migrate_directory(migration_setup):
    """Test migrating a directory from IPFS to S3."""
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    result = migration.migrate_directory("QmTestDir", "test-bucket", "test/")

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_directory"
    assert result["total_files"] == 3  # Including the directory
    assert result["successful_migrations"] == 2  # Only the files
    assert result["failed_migrations"] == 0

    # Verify the right methods were called
    mock_ipfs_kit.ipfs_ls_path.assert_called_once_with("QmTestDir")
    assert mock_ipfs_kit.ipfs_cat.call_count == 2  # Once for each file
    assert mock_s3_kit.s3_ul_file.call_count == 2  # Once for each file


def test_migrate_by_list(migration_setup):
    """Test migrating a list of files from IPFS to S3."""
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    cid_list = [
        {"cid": "QmTest123File1", "name": "file1.txt"},
        {"cid": "QmTest123File2", "name": "file2.txt"},
    ]

    result = migration.migrate_by_list(cid_list, "test-bucket", "test/")

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_by_list"
    assert result["total_files"] == 2
    assert result["successful_migrations"] == 2
    assert result["failed_migrations"] == 0

    # Verify the right methods were called
    assert mock_ipfs_kit.ipfs_cat.call_count == 2
    assert mock_s3_kit.s3_ul_file.call_count == 2


def test_migrate_by_list_with_string_cids(migration_setup):
    """Test migrating a list of string CIDs."""
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    cid_list = ["QmTest123File1", "QmTest123File2"]

    result = migration.migrate_by_list(cid_list, "test-bucket", "test/")

    # Verify result structure and success
    assert result["success"] is True
    assert result["successful_migrations"] == 2

    # Verify the right methods were called
    assert mock_ipfs_kit.ipfs_cat.call_count == 2
    assert mock_s3_kit.s3_ul_file.call_count == 2


def test_migrate_empty_list(migration_setup):
    """Test migrating an empty list."""
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    result = migration.migrate_by_list([], "test-bucket", "test/")

    # Verify result structure and success
    assert result["success"] is True
    assert "warning" in result
    assert result["migrated_files"] == []

    # Verify no methods were called
    mock_ipfs_kit.ipfs_cat.assert_not_called()
    mock_s3_kit.s3_ul_file.assert_not_called()


def test_migrate_file_failure(migration_setup):
    """Test handling of failures during file migration."""
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_s3_kit = migration_setup["mock_s3_kit"]

    # Configure IPFS cat to fail
    mock_ipfs_kit.ipfs_cat.return_value = {"success": False, "error": "Content not found"}

    result = migration.migrate_file("QmTest123", "test-bucket", "test/test_file.txt")

    # Verify result structure and failure
    assert result["success"] is False
    assert "error" in result

    # Verify S3 methods were not called
    mock_s3_kit.s3_ul_file.assert_not_called()


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
    assert os.path.exists(test_temp_dir) is False
