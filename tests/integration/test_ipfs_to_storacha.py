import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from ipfs_kit_py.migration_tools.ipfs_to_storacha import ipfs_to_storacha


@pytest.fixture
def migration_setup(mock_ipfs):
    """Set up test fixtures for ipfs_to_storacha migration tests."""
    # Create mock resources and metadata
    resources = {"cpu": 2, "memory": "4GB"}
    metadata = {"role": "leecher"}

    # Create a temporary test file
    temp_dir = tempfile.mkdtemp(prefix="test_ipfs_to_storacha_")
    test_file_path = os.path.join(temp_dir, "test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("This is test content for IPFS to Storacha migration")

    # Create patches for the dependencies
    mock_storacha_kit = MagicMock()
    mock_s3_kit = MagicMock()
    # Use the provided mock_ipfs fixture
    mock_ipfs_kit = mock_ipfs.return_value

    # Configure mock responses
    mock_ipfs_kit.ipfs_cat.return_value = {
        "success": True,
        "data": b"This is test content for IPFS to Storacha migration",
        "size": 42,
    }

    mock_ipfs_kit.ipfs_ls_path.return_value = {
        "success": True,
        "links": [
            {"Name": "file1.txt", "Hash": "QmTest123File1", "Size": 42, "Type": 2},  # File
            {"Name": "file2.txt", "Hash": "QmTest123File2", "Size": 24, "Type": 2},  # File
        ],
    }

    mock_storacha_kit.store_add.return_value = {
        "success": True,
        "cid": "bafy2bzacedfake123",
        "size": 42,
    }

    # Start patching
    storacha_kit_patcher = patch(
        "ipfs_kit_py.storacha_kit.storacha_kit",
        return_value=mock_storacha_kit,
    )
    s3_kit_patcher = patch("ipfs_kit_py.s3_kit.s3_kit", return_value=mock_s3_kit)

    mock_storacha_kit_class = storacha_kit_patcher.start()
    mock_s3_kit_class = s3_kit_patcher.start()

    # Create migration instance with mocked dependencies
    migration = ipfs_to_storacha(resources, metadata)

    # Replace the cleanup method to prevent removal of temp dir during tests
    if hasattr(migration, "cleanup"):
        original_cleanup = migration.cleanup
        migration.cleanup = MagicMock()
    else:
        original_cleanup = None

    # Create a fixture data structure to return everything needed for tests
    fixture_data = {
        "migration": migration,
        "resources": resources,
        "metadata": metadata,
        "temp_dir": temp_dir,
        "test_file_path": test_file_path,
        "mock_storacha_kit": mock_storacha_kit,
        "mock_s3_kit": mock_s3_kit,
        "mock_ipfs_kit": mock_ipfs_kit,
        "original_cleanup": original_cleanup,
        "storacha_kit_patcher": storacha_kit_patcher,
        "s3_kit_patcher": s3_kit_patcher,
    }

    # Return the fixture data
    yield fixture_data

    # Teardown - stop patching
    storacha_kit_patcher.stop()
    s3_kit_patcher.stop()

    # Restore original cleanup method if it existed
    if original_cleanup and hasattr(migration, "cleanup"):
        migration.cleanup = original_cleanup

    # Clean up temp dir
    shutil.rmtree(temp_dir)


def test_init(migration_setup):
    """Test initialization of the migration tool."""
    assert migration_setup["migration"].resources == migration_setup["resources"]
    assert migration_setup["migration"].metadata == migration_setup["metadata"]
    assert migration_setup["migration"].storacha_kit == migration_setup["mock_storacha_kit"]
    assert migration_setup["migration"].ipfs == migration_setup["mock_ipfs_kit"]


def test_migrate_file(migration_setup):
    """Test migrating a single file from IPFS to Storacha."""
    # Setup
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]

    result = migration.migrate_file("test-space", "QmTest123")

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_file"
    assert result["source"]["type"] == "ipfs"
    assert result["source"]["cid"] == "QmTest123"
    assert result["destination"]["type"] == "storacha"
    assert result["destination"]["space"] == "test-space"
    assert result["storacha_cid"] == "bafy2bzacedfake123"

    # Verify the right methods were called
    mock_ipfs_kit.ipfs_cat.assert_called_once()
    mock_storacha_kit.store_add.assert_called_once()


def test_migrate_directory(migration_setup):
    """Test migrating a directory from IPFS to Storacha."""
    # Setup
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]

    result = migration.migrate_directory("test-space", "QmTestDir123")

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_directory"
    assert result["source"]["type"] == "ipfs"
    assert result["source"]["cid"] == "QmTestDir123"
    assert result["destination"]["type"] == "storacha"
    assert result["total_files"] == 2
    assert result["successful_migrations"] == 2
    assert result["failed_migrations"] == 0

    # Verify the right methods were called
    mock_ipfs_kit.ipfs_ls_path.assert_called_once()
    assert mock_ipfs_kit.ipfs_cat.call_count == 2
    assert mock_storacha_kit.store_add.call_count >= 1


def test_migrate_by_list(migration_setup):
    """Test migrating a list of files from IPFS to Storacha."""
    # Setup
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]

    file_list = ["QmTest123File1", "QmTest123File2"]
    result = migration.migrate_by_list("test-space", file_list)

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_by_list"
    assert result["total_files"] == 2
    assert result["successful_migrations"] == 2
    assert result["failed_migrations"] == 0

    # Verify the right methods were called
    assert mock_ipfs_kit.ipfs_cat.call_count == 2
    assert mock_storacha_kit.store_add.call_count == 2


def test_migrate_empty_list(migration_setup):
    """Test migrating an empty list."""
    # Setup
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]

    result = migration.migrate_by_list("test-space", [])

    # Verify result structure and success
    assert result["success"] is True
    assert "warning" in result
    assert result["migrated_files"] == []

    # Verify no methods were called
    mock_ipfs_kit.ipfs_cat.assert_not_called()
    mock_storacha_kit.store_add.assert_not_called()


def test_migrate_file_failure(migration_setup):
    """Test handling of failures during file migration."""
    # Setup
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]

    # Configure IPFS download to fail
    mock_ipfs_kit.ipfs_cat.return_value = {"success": False, "error": "Content not found"}

    result = migration.migrate_file("test-space", "QmTest123")

    # Verify result structure and failure
    assert result["success"] is False
    assert "error" in result

    # Verify Storacha methods were not called
    mock_storacha_kit.store_add.assert_not_called()


def test_cleanup(migration_setup):
    """Test cleanup of temporary resources."""
    # Setup
    migration = migration_setup["migration"]
    original_cleanup = migration_setup["original_cleanup"]

    if not original_cleanup:
        pytest.skip("Cleanup method not implemented in the class yet")

    # Restore the original cleanup method
    migration.cleanup = original_cleanup

    # Create a temporary directory for testing cleanup
    test_temp_dir = tempfile.mkdtemp(prefix="test_cleanup_")
    migration.temp_dir = test_temp_dir

    # Call cleanup
    migration.cleanup()

    # Verify the directory was removed
    assert not os.path.exists(test_temp_dir)
