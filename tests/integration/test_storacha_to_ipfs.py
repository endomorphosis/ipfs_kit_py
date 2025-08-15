import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

import sys
from ipfs_kit_py.migration_tools.storacha_to_ipfs import storacha_to_ipfs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


@pytest.fixture
def migration_setup(mock_ipfs):
    """Set up test fixtures for storacha_to_ipfs migration tests."""
    # Create mock resources and metadata
    resources = {"cpu": 2, "memory": "4GB"}
    metadata = {"role": "leecher"}

    # Create a temporary test file
    temp_dir = tempfile.mkdtemp(prefix="test_storacha_to_ipfs_")
    test_file_path = os.path.join(temp_dir, "test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("This is test content for Storacha to IPFS migration")

    # Create patches for the dependencies
    mock_storacha_kit = MagicMock()
    # Use the provided mock_ipfs fixture
    mock_ipfs_kit = mock_ipfs.return_value

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

    # Configure IPFS mock responses (beyond what the fixture provides)
    mock_ipfs_kit.ipfs_add.return_value = {
        "success": True,
        "cid": "QmTest123",
        "size": 42,
        "name": "test_file.txt",
    }

    mock_ipfs_kit.ipfs_pin_add.return_value = {
        "success": True,
        "pins": ["QmTest123"],
        "count": 1,
    }

    # Start patching
    storacha_kit_patcher = patch(
        "ipfs_kit_py.storacha_kit.storacha_kit",
        return_value=mock_storacha_kit,
    )
    ipfs_kit_patcher = patch("ipfs_kit_py.ipfs.ipfs_py", return_value=mock_ipfs_kit)

    mock_storacha_kit_class = storacha_kit_patcher.start()
    mock_ipfs_kit_class = ipfs_kit_patcher.start()

    # Create migration instance with mocked dependencies
    migration = storacha_to_ipfs(resources, metadata)

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
        "mock_storacha_kit": mock_storacha_kit,
        "mock_ipfs_kit": mock_ipfs_kit,
        "original_cleanup": original_cleanup,
        "storacha_kit_patcher": storacha_kit_patcher,
        "ipfs_kit_patcher": ipfs_kit_patcher,
    }

    # Return the fixture data
    yield fixture_data

    # Teardown - stop patching
    storacha_kit_patcher.stop()
    ipfs_kit_patcher.stop()

    # Restore original cleanup method
    migration.cleanup = original_cleanup

    # Clean up temp dir
    shutil.rmtree(temp_dir)


def test_init(migration_setup):
    """Test initialization of the migration tool."""
    assert migration_setup["migration"].resources == migration_setup["resources"]
    assert migration_setup["migration"].metadata == migration_setup["metadata"]
    assert migration_setup["migration"].temp_dir is not None
    assert os.path.exists(migration_setup["migration"].temp_dir)
    assert migration_setup["migration"].storacha_kit == migration_setup["mock_storacha_kit"]
    assert migration_setup["migration"].ipfs == migration_setup["mock_ipfs_kit"]


def test_migrate_file(migration_setup):
    """Test migrating a single file from Storacha to IPFS."""
    # Setup
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]

    result = migration.migrate_file("test-space", "bagbaiera123")

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_file"
    assert result["source"]["type"] == "storacha"
    assert result["source"]["space"] == "test-space"
    assert result["source"]["cid"] == "bagbaiera123"
    assert result["destination"]["type"] == "ipfs"
    assert result["ipfs_cid"] == "QmTest123"

    # Verify the right methods were called
    mock_storacha_kit.store_get.assert_called_once()
    mock_ipfs_kit.ipfs_add.assert_called_once()
    mock_ipfs_kit.ipfs_pin_add.assert_called_once_with("QmTest123")


def test_migrate_file_no_pin(migration_setup):
    """Test migrating a file without pinning."""
    # Setup
    migration = migration_setup["migration"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]

    result = migration.migrate_file("test-space", "bagbaiera123", pin=False)

    # Verify result structure and success
    assert result["success"] is True
    assert result["ipfs_cid"] == "QmTest123"

    # Verify pinning was not called
    mock_ipfs_kit.ipfs_pin_add.assert_not_called()


def test_migrate_directory(migration_setup):
    """Test migrating a directory from Storacha to IPFS."""
    # Setup
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]

    result = migration.migrate_directory("test-space", "bagbaiera123dir")

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_directory"
    assert result["ipfs_cid"] == "QmTest123"
    assert result["total_files"] == 2
    assert result["successful_migrations"] == 2
    assert result["failed_migrations"] == 0

    # Verify the right methods were called
    mock_storacha_kit.store_ls.assert_called_once()
    assert mock_storacha_kit.store_get.call_count == 2
    mock_ipfs_kit.ipfs_add.assert_called_once()
    mock_ipfs_kit.ipfs_pin_add.assert_called_once()


def test_migrate_by_list(migration_setup):
    """Test migrating a list of files from Storacha to IPFS."""
    # Setup
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]

    file_list = [
        {"cid": "bagbaiera123file1", "name": "file1.txt"},
        {"cid": "bagbaiera123file2", "name": "file2.txt"},
    ]

    result = migration.migrate_by_list("test-space", file_list)

    # Verify result structure and success
    assert result["success"] is True
    assert result["operation"] == "migrate_by_list"
    assert result["total_files"] == 2
    assert result["successful_migrations"] == 2
    assert result["failed_migrations"] == 0

    # Verify the right methods were called
    assert mock_storacha_kit.store_get.call_count == 2
    assert mock_ipfs_kit.ipfs_add.call_count == 2
    assert mock_ipfs_kit.ipfs_pin_add.call_count == 2


def test_migrate_empty_list(migration_setup):
    """Test migrating an empty list."""
    # Setup
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]

    result = migration.migrate_by_list("test-space", [])

    # Verify result structure and success
    assert result["success"] is True
    assert "warning" in result
    assert result["migrated_files"] == []

    # Verify no methods were called
    mock_storacha_kit.store_get.assert_not_called()
    mock_ipfs_kit.ipfs_add.assert_not_called()
    mock_ipfs_kit.ipfs_pin_add.assert_not_called()


def test_migrate_file_failure(migration_setup):
    """Test handling of failures during file migration."""
    # Setup
    migration = migration_setup["migration"]
    mock_storacha_kit = migration_setup["mock_storacha_kit"]
    mock_ipfs_kit = migration_setup["mock_ipfs_kit"]

    # Configure Storacha download to fail
    mock_storacha_kit.store_get.return_value = {
        "success": False,
        "error": "Content not found",
    }

    result = migration.migrate_file("test-space", "bagbaiera123")

    # Verify result structure and failure
    assert result["success"] is False
    assert "error" in result

    # Verify IPFS methods were not called
    mock_ipfs_kit.ipfs_add.assert_not_called()
    mock_ipfs_kit.ipfs_pin_add.assert_not_called()


def test_cleanup(migration_setup):
    """Test cleanup of temporary resources."""
    # Setup
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
