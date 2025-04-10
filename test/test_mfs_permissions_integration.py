#!/usr/bin/env python3
"""
Tests for MFS permissions integration with resumable operations.

This module tests the integration of the permissions system with the
MFS resumable operations module.
"""

import os
import tempfile
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import pytest_asyncio

from ipfs_kit_py.mfs_permissions import (
    Permission, FileType, PermissionManager, FilePermissions,
    AccessDeniedException
)
from ipfs_kit_py.mfs_enhanced_resumable import (
    ResumableFileOperations,
    FileChunk,
    ResumableFileState
)


@pytest_asyncio.fixture
async def permission_manager():
    """Create a permission manager with test permissions."""
    # Create a temporary directory for permissions
    temp_dir = tempfile.mkdtemp()
    
    # Create permission manager with test user
    pm = PermissionManager(
        permissions_dir=temp_dir,
        current_user_id="test_user"
    )
    
    # Add test user to groups
    pm.add_user_to_group("test_user", "test_group")
    
    yield pm
    
    # Clean up temporary directory
    if os.path.exists(temp_dir):
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)


@pytest_asyncio.fixture
async def resumable_ops(permission_manager):
    """Create a resumable operations instance with mocked IPFS client and permissions."""
    # Create a temporary directory for state files
    temp_dir = tempfile.mkdtemp()
    
    # Mock IPFS client with enhanced behaviors for permission testing
    mock_ipfs = MagicMock()
    
    # Create async mocks for methods we'll call
    mock_ipfs.files_mkdir = AsyncMock()
    mock_ipfs.files_write = AsyncMock()
    mock_ipfs.files_stat = AsyncMock()
    mock_ipfs.files_read = AsyncMock()
    mock_ipfs.files_cp = AsyncMock()
    
    # Set default return values for mock methods
    # This ensures they don't throw unintended exceptions by default
    mock_ipfs.files_write.return_value = None
    mock_ipfs.files_read.return_value = b"test data"
    mock_ipfs.files_stat.return_value = {"Size": 1024 * 1024, "Hash": "test-hash"}
    
    # Create a real ResumableFileOperations instance with patched _check_permission
    resumable = ResumableFileOperations(
        mock_ipfs,
        state_dir=temp_dir,
        permissions_dir=permission_manager.permissions_dir,
        user_id="test_user",
        max_concurrent_transfers=4,
        enforce_permissions=True
    )
    
    # Keep a reference to the original method to use in our tests
    original_check_permission = resumable._check_permission
    
    # Set up permission manager to be properly consulted
    resumable.permission_manager = permission_manager
    
    yield resumable, mock_ipfs, temp_dir, permission_manager
    
    # Clean up temporary directory
    if os.path.exists(temp_dir):
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)


@pytest_asyncio.fixture
async def resumable_ops_no_permissions(permission_manager):
    """Create a resumable operations instance with enforcement disabled."""
    # Create a temporary directory for state files
    temp_dir = tempfile.mkdtemp()
    
    # Mock IPFS client
    mock_ipfs = MagicMock()
    mock_ipfs.files_mkdir = AsyncMock()
    mock_ipfs.files_write = AsyncMock()
    mock_ipfs.files_stat = AsyncMock()
    mock_ipfs.files_read = AsyncMock()
    mock_ipfs.files_cp = AsyncMock()
    
    # Create resumable operations instance without enforcing permissions
    resumable = ResumableFileOperations(
        mock_ipfs,
        state_dir=temp_dir,
        permissions_dir=permission_manager.permissions_dir,
        user_id="test_user",
        max_concurrent_transfers=4,
        enforce_permissions=False
    )
    
    yield resumable, mock_ipfs, temp_dir, permission_manager
    
    # Clean up temporary directory
    if os.path.exists(temp_dir):
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)


@pytest.mark.asyncio
async def test_start_resumable_write_with_permissions(resumable_ops):
    """Test starting a resumable write operation with permissions."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    
    # Create permissions for the file
    file_permissions = FilePermissions(
        path="/test/file.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.READ, Permission.WRITE},
        group_permissions={Permission.READ},
        other_permissions=set()
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Start resumable write
    file_id = await resumable.start_resumable_write(
        file_path="/test/file.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024
    )
    
    # Verify file_id is generated
    assert file_id is not None
    
    # Verify state is saved
    state_path = os.path.join(temp_dir, f"{file_id}.json")
    assert os.path.exists(state_path)
    
    # Verify empty file was created
    mock_ipfs.files_write.assert_called_once()
    
    # Verify operation type was stored in metadata
    state = await resumable.load_state(file_id)
    assert "operation_type" in state.metadata
    assert state.metadata["operation_type"] == "write"


@pytest.mark.asyncio
async def test_start_resumable_write_permission_denied(resumable_ops):
    """Test permission denied when starting a resumable write operation."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Create permissions for the file with no write access
    file_permissions = FilePermissions(
        path="/test/no_write.txt",
        file_type=FileType.FILE,
        owner_id="other_user",  # Different owner
        group_id="other_group",
        owner_permissions={Permission.READ, Permission.WRITE},
        group_permissions={Permission.READ},
        other_permissions=set()  # No permissions for others
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Attempt to start resumable write
    with pytest.raises(AccessDeniedException) as excinfo:
        await resumable.start_resumable_write(
            file_path="/test/no_write.txt",
            total_size=1024 * 1024,
            chunk_size=256 * 1024
        )
    
    # Verify permission error
    assert "lacks w permission" in str(excinfo.value)


@pytest.mark.asyncio
async def test_write_chunk_permission_check(resumable_ops):
    """Test permission check when writing a chunk."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    
    # Create permissions for the file
    file_permissions = FilePermissions(
        path="/test/write_chunk.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.READ, Permission.WRITE},
        group_permissions={Permission.READ},
        other_permissions=set()
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Start resumable write
    file_id = await resumable.start_resumable_write(
        file_path="/test/write_chunk.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024
    )
    
    # Prepare chunk data
    chunk_data = b"x" * (256 * 1024)
    
    # Write first chunk
    result = await resumable.write_chunk(file_id, chunk_data, chunk_index=0)
    
    # Verify success
    assert result["success"] is True
    
    # Now revoke write permission
    file_permissions.owner_permissions = {Permission.READ}  # Remove write permission
    await permission_manager.save_permissions(file_permissions)
    
    # Make sure we don't have write permission
    has_permission = await permission_manager.check_permission(
        file_path="/test/write_chunk.txt",
        permission=Permission.WRITE,
        user_id="test_user"
    )
    assert has_permission is False, "Permission should be revoked but check returned True"
    
    # Try to write another chunk
    result = await resumable.write_chunk(file_id, chunk_data, chunk_index=1)
    
    # Verify permission denied
    assert result["success"] is False, "Write operation should fail due to permission denied"
    assert "permission_denied" in result, "Missing permission_denied flag in result"
    assert result["permission_denied"] is True, "Permission denied flag should be True"
    assert "error" in result, "Error message should be present"
    assert "permission" in result["error"].lower(), "Error message should mention permission"


@pytest.mark.asyncio
async def test_start_resumable_read_with_permissions(resumable_ops):
    """Test starting a resumable read operation with permissions."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.return_value = {"Size": 1024 * 1024, "Hash": "test-hash"}
    
    # Create permissions for the file
    file_permissions = FilePermissions(
        path="/test/read_file.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.READ, Permission.WRITE},
        group_permissions={Permission.READ},
        other_permissions=set()
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Start resumable read
    file_id = await resumable.start_resumable_read(
        file_path="/test/read_file.txt",
        chunk_size=256 * 1024
    )
    
    # Verify file_id is generated
    assert file_id is not None
    
    # Verify state is saved
    state_path = os.path.join(temp_dir, f"{file_id}.json")
    assert os.path.exists(state_path)
    
    # Verify operation type was stored in metadata
    state = await resumable.load_state(file_id)
    assert "operation_type" in state.metadata
    assert state.metadata["operation_type"] == "read"


@pytest.mark.asyncio
async def test_start_resumable_read_permission_denied(resumable_ops):
    """Test permission denied when starting a resumable read operation."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Create permissions for the file with no read access
    file_permissions = FilePermissions(
        path="/test/no_read.txt",
        file_type=FileType.FILE,
        owner_id="other_user",  # Different owner
        group_id="other_group",
        owner_permissions={Permission.READ, Permission.WRITE},
        group_permissions={Permission.READ},
        other_permissions=set()  # No permissions for others
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Attempt to start resumable read
    with pytest.raises(AccessDeniedException) as excinfo:
        await resumable.start_resumable_read(
            file_path="/test/no_read.txt",
            chunk_size=256 * 1024
        )
    
    # Verify permission error
    assert "lacks r permission" in str(excinfo.value)


@pytest.mark.asyncio
async def test_read_chunk_permission_check(resumable_ops):
    """Test permission check when reading a chunk."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.return_value = {"Size": 1024 * 1024, "Hash": "test-hash"}
    mock_ipfs.files_read.return_value = b"x" * (256 * 1024)
    
    # Create permissions for the file with only read permission initially
    file_permissions = FilePermissions(
        path="/test/read_chunk.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.READ},  # Only READ permission
        group_permissions=set(),  # No group permissions
        other_permissions=set()  # No other permissions
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Clear cache to ensure permissions are loaded from disk
    await permission_manager.clear_cache()
    
    # Start resumable read
    file_id = await resumable.start_resumable_read(
        file_path="/test/read_chunk.txt",
        chunk_size=256 * 1024
    )
    
    # Read first chunk
    result = await resumable.read_chunk(file_id, chunk_index=0)
    
    # Verify success
    assert result["success"] is True
    
    # Now revoke read permission completely
    file_permissions.owner_permissions = set()  # No permissions at all
    await permission_manager.save_permissions(file_permissions)
    
    # Clear cache to ensure permission change is visible
    await permission_manager.clear_cache("/test/read_chunk.txt")
    
    # Verify permission change
    has_permission = await permission_manager.check_permission(
        file_path="/test/read_chunk.txt",
        permission=Permission.READ,
        user_id="test_user"
    )
    assert has_permission is False, "Permission should be revoked but check returned True"
    
    # Set up mock for read call to not raise an exception
    mock_ipfs.files_read.return_value = b"more test data"
    
    # Add logging to help debug permission issues
    print(f"\nPermission check before read_chunk:")
    print(f"- User {resumable.user_id} requesting READ permission for {file_permissions.path}")
    print(f"- Permission settings: {file_permissions.owner_permissions}")
    print(f"- Verify result from db: {has_permission}")
    
    # Try to read another chunk
    result = await resumable.read_chunk(file_id, chunk_index=1)
    
    print(f"\nRead result: {result}")
    
    # Verify permission denied
    assert result["success"] is False, "Read operation should fail due to permission denied"
    assert "permission_denied" in result, "Missing permission_denied flag in result"
    assert result["permission_denied"] is True, "Permission denied flag should be True"
    assert "error" in result, "Error message should be present"
    assert "permission" in result["error"].lower(), "Error message should mention permission"


@pytest.mark.asyncio
async def test_finalize_write_permission_check(resumable_ops):
    """Test permission check when finalizing a write operation."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.side_effect = [
        Exception("File not found"),  # For start_resumable_write
        {"Size": 1024 * 1024, "Hash": "test-hash"},  # For finalize_write
        {"Size": 1024 * 1024, "Hash": "test-hash"}   # For any other files_stat call
    ]
    
    # Create permissions for the file
    file_permissions = FilePermissions(
        path="/test/finalize_write.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.READ, Permission.WRITE},
        group_permissions={Permission.READ},
        other_permissions=set()
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Start resumable write
    file_id = await resumable.start_resumable_write(
        file_path="/test/finalize_write.txt",
        total_size=1024 * 1024,
        chunk_size=1024 * 1024  # Single chunk for simplicity
    )
    
    # Mark the chunk as completed (simulate writing)
    state = await resumable.load_state(file_id)
    state.chunks[0].status = "completed"  # Mark as completed
    state.completed = True
    await resumable.save_state(file_id, state)
    
    # Now revoke write permission
    file_permissions.owner_permissions = {Permission.READ}  # Remove write permission
    await permission_manager.save_permissions(file_permissions)
    
    # Clear cache to ensure permission change is visible
    await permission_manager.clear_cache("/test/finalize_write.txt")
    
    # Verify permission change
    has_permission = await permission_manager.check_permission(
        file_path="/test/finalize_write.txt",
        permission=Permission.WRITE,
        user_id="test_user"
    )
    assert has_permission is False, "Permission should be revoked but check returned True"
    
    # Reset mock.files_stat to ensure it doesn't throw any exceptions
    mock_ipfs.files_stat.side_effect = None
    mock_ipfs.files_stat.return_value = {"Size": 1024 * 1024, "Hash": "test-hash"}
    
    # Try to finalize write
    result = await resumable.finalize_write(file_id)
    
    # Verify permission denied
    assert result["success"] is False, "Write operation should fail due to permission denied"
    assert "permission_denied" in result, "Missing permission_denied flag in result"
    assert result["permission_denied"] is True, "Permission denied flag should be True"
    assert "error" in result, "Error message should be present"
    assert "permission" in result["error"].lower(), "Error message should mention permission"


@pytest.mark.asyncio
async def test_finalize_read_permission_check(resumable_ops):
    """Test permission check when finalizing a read operation."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.return_value = {"Size": 1024 * 1024, "Hash": "test-hash"}
    mock_ipfs.files_read.return_value = b"test data"
    
    # Create permissions for the file with only read permission initially
    file_permissions = FilePermissions(
        path="/test/finalize_read.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.READ},  # Only READ permission
        group_permissions=set(),  # No group permissions
        other_permissions=set()  # No other permissions
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Clear cache to ensure permissions are loaded from disk
    await permission_manager.clear_cache()
    
    # Start resumable read
    file_id = await resumable.start_resumable_read(
        file_path="/test/finalize_read.txt",
        chunk_size=1024 * 1024  # Single chunk for simplicity
    )
    
    # Now revoke read permission completely
    file_permissions.owner_permissions = set()  # No permissions at all
    await permission_manager.save_permissions(file_permissions)
    
    # Clear cache to ensure permission change is visible
    await permission_manager.clear_cache("/test/finalize_read.txt")
    
    # Verify permission change
    has_permission = await permission_manager.check_permission(
        file_path="/test/finalize_read.txt",
        permission=Permission.READ,
        user_id="test_user"
    )
    assert has_permission is False, "Permission should be revoked but check returned True"
    
    # Try to finalize read
    result = await resumable.finalize_read(file_id)
    
    # Verify permission denied
    assert result["success"] is False, "Read operation should fail due to permission denied"
    assert "permission_denied" in result, "Missing permission_denied flag in result"
    assert result["permission_denied"] is True, "Permission denied flag should be True"
    assert "error" in result, "Error message should be present"
    assert "permission" in result["error"].lower(), "Error message should mention permission"


@pytest.mark.asyncio
async def test_resume_operation_permission_check(resumable_ops):
    """Test permission check when resuming an operation."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Configure mock for write operation
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    mock_ipfs.files_write.return_value = None
    
    # Create permissions for the file
    file_permissions = FilePermissions(
        path="/test/resume_op.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.READ, Permission.WRITE},
        group_permissions={Permission.READ},
        other_permissions=set()
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Start resumable write
    file_id = await resumable.start_resumable_write(
        file_path="/test/resume_op.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024
    )
    
    # Verify the operation is of type "write" in the metadata
    state = await resumable.load_state(file_id)
    assert state.metadata["operation_type"] == "write", "Operation should be of type 'write'"
    
    # Now revoke write permission
    file_permissions.owner_permissions = {Permission.READ}  # Remove write permission
    await permission_manager.save_permissions(file_permissions)
    
    # Clear cache to ensure permission change is visible
    await permission_manager.clear_cache("/test/resume_op.txt")
    
    # Verify permission change
    has_permission = await permission_manager.check_permission(
        file_path="/test/resume_op.txt",
        permission=Permission.WRITE,
        user_id="test_user"
    )
    assert has_permission is False, "Permission should be revoked but check returned True"
    
    # Try to resume operation
    result = await resumable.resume_operation(file_id)
    
    # Verify permission denied
    assert result["success"] is False, "Resume operation should fail due to permission denied"
    assert "permission_denied" in result, "Missing permission_denied flag in result"
    assert result["permission_denied"] is True, "Permission denied flag should be True"
    assert "error" in result, "Error message should be present"
    assert "permission" in result["error"].lower(), "Error message should mention permission"


@pytest.mark.asyncio
async def test_copy_resumable_permission_check(resumable_ops):
    """Test permission check when copying a resumable operation."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Configure mock for file operations
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    mock_ipfs.files_write.return_value = None
    mock_ipfs.files_cp.return_value = None
    
    # Create permissions for source file with READ and WRITE permission initially
    source_permissions = FilePermissions(
        path="/test/source.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.READ, Permission.WRITE},  # Need both READ and WRITE for start_resumable_write
        group_permissions=set(),  # No group permissions
        other_permissions=set()  # No other permissions
    )
    await permission_manager.save_permissions(source_permissions)
    
    # Create permissions for destination file with only WRITE permission initially
    dest_permissions = FilePermissions(
        path="/test/dest.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.WRITE},  # Only WRITE permission
        group_permissions=set(),  # No group permissions
        other_permissions=set()  # No other permissions
    )
    await permission_manager.save_permissions(dest_permissions)
    
    # Clear cache to ensure permissions are loaded from disk
    await permission_manager.clear_cache()
    
    # Start resumable write for source
    source_id = await resumable.start_resumable_write(
        file_path="/test/source.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024
    )
    
    # Case 1: Test with both permissions present
    result = await resumable.copy_resumable(source_id, "/test/dest.txt")
    mock_ipfs.files_cp.assert_called_once()
    assert result["success"] is True, "Copy should succeed with both permissions"
    
    # Reset mock
    mock_ipfs.files_cp.reset_mock()
    
    # Case 2: Remove read permission from source
    source_permissions.owner_permissions = set()  # No permissions at all
    await permission_manager.save_permissions(source_permissions)
    
    # Clear cache to ensure permission change is visible
    await permission_manager.clear_cache("/test/source.txt")
    
    # Verify permission change
    has_permission = await permission_manager.check_permission(
        file_path="/test/source.txt",
        permission=Permission.READ,
        user_id="test_user"
    )
    assert has_permission is False, "Read permission should be revoked but check returned True"
    
    result = await resumable.copy_resumable(source_id, "/test/dest.txt")
    
    # Verify permission denied
    assert result["success"] is False, "Copy operation should fail due to source read permission denied"
    assert "permission_denied" in result, "Missing permission_denied flag in result"
    assert result["permission_denied"] is True, "Permission denied flag should be True"
    assert "error" in result, "Error message should be present"
    assert "permission" in result["error"].lower(), "Error message should mention permission"
    
    # Case 3: Restore read permission to source but remove write from destination
    source_permissions.owner_permissions = {Permission.READ}  # Only read permission, no write
    await permission_manager.save_permissions(source_permissions)
    
    # Clear cache to ensure permission change is visible
    await permission_manager.clear_cache("/test/source.txt")
    
    # Verify read permission restored
    has_permission = await permission_manager.check_permission(
        file_path="/test/source.txt",
        permission=Permission.READ,
        user_id="test_user"
    )
    assert has_permission is True, "Read permission should be restored but check returned False"
    
    dest_permissions.owner_permissions = set()  # No permissions at all
    await permission_manager.save_permissions(dest_permissions)
    
    # Clear cache to ensure permission change is visible
    await permission_manager.clear_cache("/test/dest.txt")
    
    # Verify destination write permission change
    has_permission = await permission_manager.check_permission(
        file_path="/test/dest.txt",
        permission=Permission.WRITE,
        user_id="test_user"
    )
    assert has_permission is False, "Destination write permission should be revoked but check returned True"
    
    result = await resumable.copy_resumable(source_id, "/test/dest.txt")
    
    # Verify permission denied
    assert result["success"] is False, "Copy operation should fail due to destination write permission denied"
    assert "permission_denied" in result, "Missing permission_denied flag in result"
    assert result["permission_denied"] is True, "Permission denied flag should be True"
    assert "error" in result, "Error message should be present"
    assert "permission" in result["error"].lower(), "Error message should mention permission"


@pytest.mark.asyncio
async def test_read_multiple_chunks_permission_check(resumable_ops):
    """Test permission check when reading multiple chunks in parallel."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.return_value = {"Size": 1024 * 1024, "Hash": "test-hash"}
    mock_ipfs.files_read.return_value = b"test data"
    
    # Create permissions for the file with only read permission initially
    file_permissions = FilePermissions(
        path="/test/multi_read.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.READ},  # Only READ permission
        group_permissions=set(),  # No group permissions
        other_permissions=set()  # No other permissions
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Clear cache to ensure permissions are loaded from disk
    await permission_manager.clear_cache()
    
    # Start resumable read with parallel transfers
    file_id = await resumable.start_resumable_read(
        file_path="/test/multi_read.txt",
        chunk_size=256 * 1024,
        parallel_transfers=True,
        max_parallel_chunks=3
    )
    
    # First test successful read with permissions
    result = await resumable.read_multiple_chunks(
        file_id,
        chunk_indices=[0, 1, 2]
    )
    assert result["success"] is True, "Reading multiple chunks should succeed with proper permissions"
    
    # Now revoke read permission completely 
    file_permissions.owner_permissions = set()  # No permissions at all
    await permission_manager.save_permissions(file_permissions)
    
    # Clear cache to ensure permission change is visible
    await permission_manager.clear_cache("/test/multi_read.txt")
    
    # Verify permission change
    has_permission = await permission_manager.check_permission(
        file_path="/test/multi_read.txt",
        permission=Permission.READ,
        user_id="test_user"
    )
    assert has_permission is False, "Read permission should be revoked but check returned True"
    
    # Set mock returns for the read calls - make sure it returns data so permission check is the only thing that can fail
    mock_ipfs.files_read.return_value = b"test data"
    
    # Try to read multiple chunks
    result = await resumable.read_multiple_chunks(
        file_id,
        chunk_indices=[0, 1, 2]
    )
    
    # Verify permission denied
    assert result["success"] is False, "Reading multiple chunks should fail due to permission denied"
    assert "permission_denied" in result, "Missing permission_denied flag in result"
    assert result["permission_denied"] is True, "Permission denied flag should be True" 
    assert "error" in result, "Error message should be present"
    assert "permission" in result["error"].lower(), "Error message should mention permission"


@pytest.mark.asyncio
async def test_write_multiple_chunks_permission_check(resumable_ops):
    """Test permission check when writing multiple chunks in parallel."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    mock_ipfs.files_write.return_value = None
    
    # Create permissions for the file
    file_permissions = FilePermissions(
        path="/test/multi_write.txt",
        file_type=FileType.FILE,
        owner_id="test_user",
        group_id="test_group",
        owner_permissions={Permission.READ, Permission.WRITE},
        group_permissions={Permission.READ},
        other_permissions=set()
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Start resumable write with parallel transfers
    file_id = await resumable.start_resumable_write(
        file_path="/test/multi_write.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024,
        parallel_transfers=True,
        max_parallel_chunks=3
    )
    
    # Prepare chunk data for all 4 chunks
    chunks_data = []
    for i in range(4):
        chunk_data = bytes([i]) * (256 * 1024)  # Different data for each chunk
        chunks_data.append((i, chunk_data))
    
    # First test successful write with permissions
    # Configure mock to return success for write
    reset_mock_files_stat = mock_ipfs.files_stat.side_effect
    mock_ipfs.files_stat.side_effect = None
    mock_ipfs.files_stat.return_value = {"Size": 0, "Hash": "initial-hash"}
    
    # Write first set of chunks with proper permissions
    initial_result = await resumable.write_multiple_chunks(file_id, chunks_data[:2])
    assert initial_result["success"] is True, "Writing multiple chunks should succeed with proper permissions"
    
    # Restore the mock files_stat behavior
    mock_ipfs.files_stat.side_effect = reset_mock_files_stat
    
    # Now revoke write permission
    file_permissions.owner_permissions = {Permission.READ}  # Remove write permission
    await permission_manager.save_permissions(file_permissions)
    
    # Clear cache to ensure permission change is visible
    await permission_manager.clear_cache("/test/multi_write.txt")
    
    # Verify permission change
    has_permission = await permission_manager.check_permission(
        file_path="/test/multi_write.txt",
        permission=Permission.WRITE,
        user_id="test_user"
    )
    assert has_permission is False, "Write permission should be revoked but check returned True"
    
    # Configure mock to avoid any success status
    mock_ipfs.files_write.return_value = None
    mock_ipfs.files_stat.side_effect = None
    mock_ipfs.files_stat.return_value = {"Size": 100, "Hash": "test-hash"}
    
    # Try to write multiple chunks
    result = await resumable.write_multiple_chunks(file_id, chunks_data[2:])
    
    # Verify permission denied
    assert result["success"] is False, "Writing multiple chunks should fail due to permission denied"
    assert "permission_denied" in result, "Missing permission_denied flag in result"
    assert result["permission_denied"] is True, "Permission denied flag should be True"
    assert "error" in result, "Error message should be present"
    assert "permission" in result["error"].lower(), "Error message should mention permission"


@pytest.mark.asyncio
async def test_bypassing_permissions(resumable_ops_no_permissions):
    """Test that permissions are bypassed when enforce_permissions is False."""
    resumable, mock_ipfs, temp_dir, permission_manager = resumable_ops_no_permissions
    
    # Configure mock
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    
    # Create permissions for the file with no permissions for the test user
    file_permissions = FilePermissions(
        path="/test/no_permissions.txt",
        file_type=FileType.FILE,
        owner_id="other_user",  # Different owner
        group_id="other_group",
        owner_permissions={Permission.READ, Permission.WRITE},
        group_permissions={Permission.READ},
        other_permissions=set()  # No permissions for others
    )
    await permission_manager.save_permissions(file_permissions)
    
    # Start resumable write - should succeed despite lack of permissions
    file_id = await resumable.start_resumable_write(
        file_path="/test/no_permissions.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024
    )
    
    # Verify file_id is generated and operation succeeded
    assert file_id is not None
    
    # Write a chunk
    chunk_data = b"x" * (256 * 1024)
    result = await resumable.write_chunk(file_id, chunk_data, chunk_index=0)
    
    # Verify success despite lack of permissions
    assert result["success"] is True
    
    # Finalize the write
    mock_ipfs.files_stat.side_effect = None
    mock_ipfs.files_stat.return_value = {"Hash": "test-hash", "Size": 1024 * 1024}
    
    # Update state to mark operation as complete
    state = await resumable.load_state(file_id)
    for chunk in state.chunks:
        chunk.status = "completed"
    state.completed = True
    await resumable.save_state(file_id, state)
    
    result = await resumable.finalize_write(file_id)
    
    # Verify success despite lack of permissions
    assert result["success"] is True