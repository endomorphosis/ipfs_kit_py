#!/usr/bin/env python3
"""
Unit tests for the enhanced MFS functionality.
"""

import anyio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ipfs_kit_py.mfs_enhanced import (
    MFSTransaction,
    DirectorySynchronizer,
    ContentTypeDetector,
    PathUtils,
    MFSChangeWatcher,
    copy_content_batch,
    move_content_batch,
    create_file_with_type,
    compute_file_hash,
    create_empty_directory_structure
)


class TestPathUtils(unittest.TestCase):
    """Test MFS path utility functions."""

    def test_join_paths(self):
        """Test joining MFS paths."""
        # Test with normal paths
        self.assertEqual(PathUtils.join_paths("/base", "dir", "file.txt"), "/base/dir/file.txt")
        
        # Test with root path
        self.assertEqual(PathUtils.join_paths("/", "dir", "file.txt"), "/dir/file.txt")
        
        # Test with empty components
        self.assertEqual(PathUtils.join_paths("/base", "", "file.txt"), "/base/file.txt")
        
        # Test with None components
        self.assertEqual(PathUtils.join_paths("/base", None, "file.txt"), "/base/file.txt")

    def test_get_parent_dir(self):
        """Test getting parent directory."""
        self.assertEqual(PathUtils.get_parent_dir("/path/to/file.txt"), "/path/to")
        self.assertEqual(PathUtils.get_parent_dir("/file.txt"), "/")
        self.assertEqual(PathUtils.get_parent_dir("/"), "/")

    def test_get_basename(self):
        """Test getting basename."""
        self.assertEqual(PathUtils.get_basename("/path/to/file.txt"), "file.txt")
        self.assertEqual(PathUtils.get_basename("/file.txt"), "file.txt")
        self.assertEqual(PathUtils.get_basename("/path/to/"), "")

    def test_split_path(self):
        """Test splitting path."""
        self.assertEqual(PathUtils.split_path("/path/to/file.txt"), ("/path/to", "file.txt"))
        self.assertEqual(PathUtils.split_path("/file.txt"), ("/", "file.txt"))
        self.assertEqual(PathUtils.split_path("/path/to/"), ("/path/to", ""))

    def test_is_subpath(self):
        """Test checking if path is a subpath."""
        self.assertTrue(PathUtils.is_subpath("/parent", "/parent/path/file.txt"))
        self.assertTrue(PathUtils.is_subpath("/parent/path", "/parent/path/file.txt"))
        self.assertFalse(PathUtils.is_subpath("/other", "/parent/path/file.txt"))
        self.assertFalse(PathUtils.is_subpath("/parent/path/file", "/parent/path/file.txt"))

    def test_normalize_path(self):
        """Test normalizing path."""
        self.assertEqual(PathUtils.normalize_path("/path//to/../to/./file.txt"), "/path/to/file.txt")
        self.assertEqual(PathUtils.normalize_path("//path/./to/file.txt"), "/path/to/file.txt")
        self.assertEqual(PathUtils.normalize_path("/path/to/../../file.txt"), "/file.txt")


class TestMFSTransaction(unittest.TestCase):
    """Test MFS transaction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.ipfs_client = AsyncMock()
        self.ipfs_client.files_read = AsyncMock(return_value=b"original content")
        self.ipfs_client.files_write = AsyncMock()
        self.ipfs_client.files_rm = AsyncMock()
        self.ipfs_client.files_stat = AsyncMock(return_value={"Type": "file"})

    async def async_test_successful_transaction(self):
        """Test a successful transaction."""
        async with MFSTransaction(self.ipfs_client) as transaction:
            await transaction.add_operation(
                self.ipfs_client.files_write,
                "/test/file1.txt",
                b"new content",
                create=True
            )
            await transaction.add_operation(
                self.ipfs_client.files_write,
                "/test/file2.txt",
                b"new content 2",
                create=True
            )
        
        # Check that all operations were called
        self.ipfs_client.files_write.assert_any_call(
            "/test/file1.txt", b"new content", create=True
        )
        self.ipfs_client.files_write.assert_any_call(
            "/test/file2.txt", b"new content 2", create=True
        )
        
        # Success should be True
        self.assertTrue(transaction.success)

    async def async_test_failed_transaction(self):
        """Test a transaction that fails and rolls back."""
        # Make the second operation fail
        self.ipfs_client.files_write.side_effect = [
            None,  # First call succeeds
            Exception("Test error")  # Second call fails
        ]
        
        try:
            async with MFSTransaction(self.ipfs_client) as transaction:
                await transaction.add_operation(
                    self.ipfs_client.files_write,
                    "/test/file1.txt",
                    b"new content",
                    create=True
                )
                
                # This will fail
                await transaction.add_operation(
                    self.ipfs_client.files_write,
                    "/test/file2.txt",
                    b"new content 2",
                    create=True
                )
        except Exception:
            pass
        
        # Check that rollback was called for the first file
        self.ipfs_client.files_rm.assert_called_with("/test/file1.txt")
        
        # Success should be False
        self.assertFalse(transaction.success)

    def test_successful_transaction(self):
        """Run async test for successful transaction."""
        anyio.run(self.async_test_successful_transaction())

    def test_failed_transaction(self):
        """Run async test for failed transaction."""
        anyio.run(self.async_test_failed_transaction())


class TestDirectorySynchronizer(unittest.TestCase):
    """Test DirectorySynchronizer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.ipfs_client = AsyncMock()
        self.ipfs_client.files_mkdir = AsyncMock()
        self.ipfs_client.files_write = AsyncMock()
        self.ipfs_client.files_read = AsyncMock(return_value=b"test content")
        self.ipfs_client.files_ls = AsyncMock(return_value={
            "Entries": [
                {"Name": "file1.txt", "Type": 0, "Size": 123},
                {"Name": "file2.txt", "Type": 0, "Size": 456},
                {"Name": "subdir", "Type": 1, "Size": 0}
            ]
        })
        self.ipfs_client.files_stat = AsyncMock(return_value={
            "Hash": "QmTest",
            "Size": 123,
            "Type": "file",
            "Blocks": 1
        })
        
    async def async_test_sync_local_to_mfs(self):
        """Test syncing from local to MFS."""
        # Create temporary directory with test files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            with open(os.path.join(temp_dir, "local1.txt"), "w") as f:
                f.write("local content 1")
            
            with open(os.path.join(temp_dir, "local2.txt"), "w") as f:
                f.write("local content 2")
            
            # Create subdirectory
            subdir = os.path.join(temp_dir, "subdir")
            os.makedirs(subdir, exist_ok=True)
            with open(os.path.join(subdir, "subfile.txt"), "w") as f:
                f.write("subdir content")
            
            # Create synchronizer
            sync = DirectorySynchronizer(self.ipfs_client, temp_dir, "/mfs/dir")
            
            # Perform sync
            result = await sync.sync_local_to_mfs()
            
            # Check that all expected operations were called
            self.ipfs_client.files_mkdir.assert_any_call("/mfs/dir", parents=True)
            self.ipfs_client.files_mkdir.assert_any_call("/mfs/dir/subdir", parents=True)
            
            self.assertEqual(len(result["added"]), 3)  # 3 files added
            self.assertEqual(len(result["updated"]), 0)  # 0 files updated
            
            # Ensure history was updated
            self.assertEqual(len(sync.sync_history["local_to_mfs"]), 3)
            
            # Test incremental sync - no changes
            previous_call_count = self.ipfs_client.files_write.call_count
            result = await sync.sync_local_to_mfs()
            # No new calls should be made
            self.assertEqual(self.ipfs_client.files_write.call_count, previous_call_count)
            
            # Modify a file and test incremental sync
            with open(os.path.join(temp_dir, "local1.txt"), "w") as f:
                f.write("modified content")
            
            result = await sync.sync_local_to_mfs()
            self.assertEqual(len(result["added"]), 0)  # 0 files added
            self.assertEqual(len(result["updated"]), 1)  # 1 file updated

    def test_sync_local_to_mfs(self):
        """Run async test for sync_local_to_mfs."""
        anyio.run(self.async_test_sync_local_to_mfs())


class TestContentTypeDetector(unittest.TestCase):
    """Test ContentTypeDetector functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.ipfs_client = AsyncMock()
        self.ipfs_client.files_read = AsyncMock()
        self.detector = ContentTypeDetector()

    async def async_test_detect_by_extension(self):
        """Test detecting content type by file extension."""
        # Test various extensions
        extensions = {
            "/test/file.txt": "text/plain",
            "/test/file.html": "text/html",
            "/test/file.json": "application/json",
            "/test/file.jpg": "image/jpeg",
            "/test/file.png": "image/png",
            "/test/file.pdf": "application/pdf"
        }
        
        for path, expected_type in extensions.items():
            content_type = await self.detector.detect_type_by_extension(path)
            self.assertEqual(content_type, expected_type)

    async def async_test_detect_by_content(self):
        """Test detecting content type by file content."""
        # Mock different file contents
        content_samples = {
            b"<!DOCTYPE html><html>": "text/html",
            b"{\"key\": \"value\"}": "application/json",
            b"\x89PNG\r\n\x1a\n": "image/png",
            b"\xff\xd8\xff\xe0": "image/jpeg",
            b"%PDF-1.5": "application/pdf",
            b"Just plain text": "text/plain"
        }
        
        for content, expected_type in content_samples.items():
            self.ipfs_client.files_read.return_value = content
            content_type = await self.detector.detect_type_by_content(self.ipfs_client, "/test/file")
            self.assertEqual(content_type, expected_type)

    def test_detect_by_extension(self):
        """Run async test for detect_by_extension."""
        anyio.run(self.async_test_detect_by_extension())

    def test_detect_by_content(self):
        """Run async test for detect_by_content."""
        anyio.run(self.async_test_detect_by_content())


class TestMFSChangeWatcher(unittest.TestCase):
    """Test MFSChangeWatcher functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.ipfs_client = AsyncMock()
        self.ipfs_client.files_ls = AsyncMock()
        self.callback = MagicMock()

    async def async_test_detect_changes(self):
        """Test detecting changes in MFS."""
        # Initial directory state
        self.ipfs_client.files_ls.side_effect = [
            # First call - initial state
            {"Entries": [
                {"Name": "file1.txt", "Type": 0, "Size": 123, "Hash": "QmHash1"},
                {"Name": "file2.txt", "Type": 0, "Size": 456, "Hash": "QmHash2"}
            ]},
            # Second call - file added
            {"Entries": [
                {"Name": "file1.txt", "Type": 0, "Size": 123, "Hash": "QmHash1"},
                {"Name": "file2.txt", "Type": 0, "Size": 456, "Hash": "QmHash2"},
                {"Name": "file3.txt", "Type": 0, "Size": 789, "Hash": "QmHash3"}
            ]},
            # Third call - file modified
            {"Entries": [
                {"Name": "file1.txt", "Type": 0, "Size": 123, "Hash": "QmHash1Modified"},
                {"Name": "file2.txt", "Type": 0, "Size": 456, "Hash": "QmHash2"},
                {"Name": "file3.txt", "Type": 0, "Size": 789, "Hash": "QmHash3"}
            ]},
            # Fourth call - file removed
            {"Entries": [
                {"Name": "file1.txt", "Type": 0, "Size": 123, "Hash": "QmHash1Modified"},
                {"Name": "file3.txt", "Type": 0, "Size": 789, "Hash": "QmHash3"}
            ]}
        ]
        
        # Create watcher
        watcher = MFSChangeWatcher(self.ipfs_client, "/test", callback=self.callback)
        
        # Initialize state
        await watcher._initialize_state()
        
        # Check for changes - should detect new file
        await watcher._check_for_changes()
        self.callback.assert_called_with("added", "/test/file3.txt", {
            "Type": 0, "Size": 789, "Hash": "QmHash3"
        })
        self.callback.reset_mock()
        
        # Check for changes again - should detect modified file
        await watcher._check_for_changes()
        self.callback.assert_called_with("modified", "/test/file1.txt", {
            "Type": 0, "Size": 123, "Hash": "QmHash1Modified"
        })
        self.callback.reset_mock()
        
        # Check for changes again - should detect removed file
        await watcher._check_for_changes()
        self.callback.assert_called_with("removed", "/test/file2.txt", None)

    def test_detect_changes(self):
        """Run async test for detect_changes."""
        anyio.run(self.async_test_detect_changes())


class TestBatchOperations(unittest.TestCase):
    """Test batch operations functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.ipfs_client = AsyncMock()
        self.ipfs_client.files_cp = AsyncMock()
        self.ipfs_client.files_mv = AsyncMock()

    async def async_test_copy_content_batch(self):
        """Test batch copying of content."""
        operations = [
            {"source": "/src/file1.txt", "destination": "/dst/file1.txt"},
            {"source": "/src/file2.txt", "destination": "/dst/file2.txt"}
        ]
        
        results = await copy_content_batch(self.ipfs_client, operations)
        
        # Check that all operations were called
        self.ipfs_client.files_cp.assert_any_call("/src/file1.txt", "/dst/file1.txt")
        self.ipfs_client.files_cp.assert_any_call("/src/file2.txt", "/dst/file2.txt")
        
        # Check results
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertTrue(result["success"])

    async def async_test_move_content_batch(self):
        """Test batch moving of content."""
        operations = [
            {"source": "/src/file1.txt", "destination": "/dst/file1.txt"},
            {"source": "/src/file2.txt", "destination": "/dst/file2.txt"}
        ]
        
        results = await move_content_batch(self.ipfs_client, operations)
        
        # Check that all operations were called
        self.ipfs_client.files_mv.assert_any_call("/src/file1.txt", "/dst/file1.txt")
        self.ipfs_client.files_mv.assert_any_call("/src/file2.txt", "/dst/file2.txt")
        
        # Check results
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertTrue(result["success"])

    def test_copy_content_batch(self):
        """Run async test for copy_content_batch."""
        anyio.run(self.async_test_copy_content_batch())

    def test_move_content_batch(self):
        """Run async test for move_content_batch."""
        anyio.run(self.async_test_move_content_batch())


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""

    def test_compute_file_hash(self):
        """Test computing file hash."""
        # Test with string content
        content = "test content"
        hash1 = compute_file_hash(content.encode())
        
        # Test with same content - should get same hash
        hash2 = compute_file_hash(content.encode())
        self.assertEqual(hash1, hash2)
        
        # Test with different content - should get different hash
        hash3 = compute_file_hash("different content".encode())
        self.assertNotEqual(hash1, hash3)

    async def async_test_create_empty_directory_structure(self):
        """Test creating empty directory structure."""
        ipfs_client = AsyncMock()
        ipfs_client.files_mkdir = AsyncMock()
        
        paths = [
            "/base/dir1/subdir1",
            "/base/dir1/subdir2",
            "/base/dir2"
        ]
        
        await create_empty_directory_structure(ipfs_client, "/base", paths)
        
        # Check that mkdir was called for each directory
        ipfs_client.files_mkdir.assert_any_call("/base/dir1", parents=True)
        ipfs_client.files_mkdir.assert_any_call("/base/dir1/subdir1", parents=True)
        ipfs_client.files_mkdir.assert_any_call("/base/dir1/subdir2", parents=True)
        ipfs_client.files_mkdir.assert_any_call("/base/dir2", parents=True)

    async def async_test_create_file_with_type(self):
        """Test creating file with content type."""
        ipfs_client = AsyncMock()
        ipfs_client.files_write = AsyncMock()
        
        # Create file with auto-detected type
        await create_file_with_type(
            ipfs_client,
            "/test/file.json",
            b'{"key": "value"}',
            detect_type=True
        )
        
        ipfs_client.files_write.assert_called_with(
            "/test/file.json",
            b'{"key": "value"}',
            create=True
        )
        
        # Create file with custom type
        await create_file_with_type(
            ipfs_client,
            "/test/file.data",
            b'custom data',
            content_type="application/custom",
            detect_type=False
        )
        
        ipfs_client.files_write.assert_called_with(
            "/test/file.data",
            b'custom data',
            create=True
        )

    def test_create_empty_directory_structure(self):
        """Run async test for create_empty_directory_structure."""
        anyio.run(self.async_test_create_empty_directory_structure())

    def test_create_file_with_type(self):
        """Run async test for create_file_with_type."""
        anyio.run(self.async_test_create_file_with_type())


if __name__ == "__main__":
    unittest.main()