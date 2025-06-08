#!/usr/bin/env python3
"""
Tests for the enhanced MFS resumable operations.

This module tests the resumable file operations for IPFS MFS,
including parallel transfers functionality.
"""

import anyio
import os
import random
import time
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
import uuid

import pytest

from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.mfs_enhanced_resumable import (
    ResumableFileOperations,
    ResumableReadStream,
    ResumableWriteStream,
    FileChunk,
    ResumableFileState,
    open_resumable
)


@pytest.fixture
async def resumable_ops():
    """Create a resumable operations instance with mocked IPFS client."""
    # Create a temporary directory for state files
    temp_dir = tempfile.mkdtemp()
    
    # Mock IPFS client
    mock_ipfs = MagicMock()
    mock_ipfs.files_mkdir = AsyncMock()
    mock_ipfs.files_write = AsyncMock()
    mock_ipfs.files_stat = AsyncMock()
    mock_ipfs.files_read = AsyncMock()
    mock_ipfs.files_cp = AsyncMock()
    
    # Create resumable operations instance
    resumable = ResumableFileOperations(
        mock_ipfs,
        state_dir=temp_dir,
        max_concurrent_transfers=4
    )
    
    yield resumable, mock_ipfs, temp_dir
    
    # Clean up temporary directory
    if os.path.exists(temp_dir):
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)


@pytest.mark.asyncio
async def test_start_resumable_write(resumable_ops):
    """Test starting a resumable write operation."""
    resumable, mock_ipfs, temp_dir = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    
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
    
    # Verify chunks were created
    state = await resumable.load_state(file_id)
    assert len(state.chunks) == 4  # 1MB / 256KB = 4 chunks
    
    # Verify each chunk has correct size
    for i, chunk in enumerate(state.chunks):
        assert chunk.start == i * 256 * 1024
        assert chunk.size == 256 * 1024
        assert chunk.status == "pending"


@pytest.mark.asyncio
async def test_start_resumable_write_with_parallel(resumable_ops):
    """Test starting a resumable write operation with parallel transfers."""
    resumable, mock_ipfs, temp_dir = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    
    # Start resumable write with parallel transfers
    file_id = await resumable.start_resumable_write(
        file_path="/test/file.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024,
        parallel_transfers=True,
        max_parallel_chunks=3
    )
    
    # Verify file_id is generated
    assert file_id is not None
    
    # Verify state is saved
    state_path = os.path.join(temp_dir, f"{file_id}.json")
    assert os.path.exists(state_path)
    
    # Verify a semaphore was created
    assert file_id in resumable.transfer_semaphores
    
    # Verify semaphore has correct value
    assert resumable.transfer_semaphores[file_id]._value == 3
    
    # Verify empty file was created
    mock_ipfs.files_write.assert_called_once()


@pytest.mark.asyncio
async def test_write_chunk(resumable_ops):
    """Test writing a single chunk."""
    resumable, mock_ipfs, temp_dir = resumable_ops
    
    # Start a resumable write
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    file_id = await resumable.start_resumable_write(
        file_path="/test/file.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024
    )
    
    # Reset mock to clear call count
    mock_ipfs.files_write.reset_mock()
    
    # Prepare chunk data
    chunk_data = b"x" * (256 * 1024)
    
    # Write first chunk
    result = await resumable.write_chunk(file_id, chunk_data, chunk_index=0)
    
    # Verify result
    assert result["success"] is True
    assert result["chunk_start"] == 0
    assert result["chunk_end"] == 256 * 1024
    
    # Verify write was called with correct parameters
    mock_ipfs.files_write.assert_called_once_with(
        "/test/file.txt",
        chunk_data,
        offset=0,
        create=True
    )
    
    # Verify chunk status was updated
    state = await resumable.load_state(file_id)
    assert state.chunks[0].status == "completed"
    assert state.get_completion_percentage() == 25.0  # 1/4 chunks


@pytest.mark.asyncio
async def test_parallel_write_chunk(resumable_ops):
    """Test writing a chunk with parallel transfers enabled."""
    resumable, mock_ipfs, temp_dir = resumable_ops
    
    # Start a resumable write with parallel transfers
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    file_id = await resumable.start_resumable_write(
        file_path="/test/file.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024,
        parallel_transfers=True,
        max_parallel_chunks=3
    )
    
    # Reset mock to clear call count
    mock_ipfs.files_write.reset_mock()
    
    # Prepare chunk data
    chunk_data = b"x" * (256 * 1024)
    
    # Write first chunk
    result = await resumable.write_chunk(file_id, chunk_data, chunk_index=0)
    
    # Verify result
    assert result["success"] is True
    assert result["chunk_start"] == 0
    assert result["chunk_end"] == 256 * 1024
    
    # Verify write was called with correct parameters
    mock_ipfs.files_write.assert_called_once_with(
        "/test/file.txt",
        chunk_data,
        offset=0,
        create=True
    )
    
    # Verify chunk status was updated
    state = await resumable.load_state(file_id)
    assert state.chunks[0].status == "completed"
    assert state.get_completion_percentage() == 25.0  # 1/4 chunks


@pytest.mark.asyncio
async def test_write_multiple_chunks(resumable_ops):
    """Test writing multiple chunks in parallel."""
    resumable, mock_ipfs, temp_dir = resumable_ops
    
    # Start a resumable write with parallel transfers
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    file_id = await resumable.start_resumable_write(
        file_path="/test/file.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024,
        parallel_transfers=True,
        max_parallel_chunks=3
    )
    
    # Reset mock to clear call count
    mock_ipfs.files_write.reset_mock()
    
    # Prepare chunk data for all 4 chunks
    chunks_data = []
    for i in range(4):
        chunk_data = bytes([i]) * (256 * 1024)  # Different data for each chunk
        chunks_data.append((i, chunk_data))
    
    # Write multiple chunks in parallel
    result = await resumable.write_multiple_chunks(file_id, chunks_data)
    
    # Verify result
    assert result["success"] is True
    assert result["completed_chunks"] == 4
    assert result["failed_chunks"] == 0
    
    # Verify write was called 4 times
    assert mock_ipfs.files_write.call_count == 4
    
    # Verify all chunks are marked as completed
    state = await resumable.load_state(file_id)
    for chunk in state.chunks:
        assert chunk.status == "completed"
    
    # Verify completion is 100%
    assert state.get_completion_percentage() == 100.0
    assert state.completed is True


@pytest.mark.asyncio
async def test_read_multiple_chunks(resumable_ops):
    """Test reading multiple chunks in parallel."""
    resumable, mock_ipfs, temp_dir = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.return_value = {"Size": 1024 * 1024, "Hash": "test-hash"}
    
    # Start a resumable read with parallel transfers
    file_id = await resumable.start_resumable_read(
        file_path="/test/file.txt",
        chunk_size=256 * 1024,
        parallel_transfers=True,
        max_parallel_chunks=3
    )
    
    # Configure mock to return different data for each chunk
    async def mock_read(path, offset, count):
        chunk_index = offset // (256 * 1024)
        return bytes([chunk_index]) * count
        
    mock_ipfs.files_read.side_effect = mock_read
    
    # Read multiple chunks in parallel
    result = await resumable.read_multiple_chunks(
        file_id,
        chunk_indices=[0, 1, 2, 3],
        max_chunks=3
    )
    
    # Verify result
    assert result["success"] is True
    assert result["completed_chunks"] == 4
    assert result["failed_chunks"] == 0
    
    # Verify read was called for each chunk
    assert mock_ipfs.files_read.call_count == 4
    
    # Verify chunks have different content
    for i in range(4):
        assert i in result["chunks"]
        chunk_result = result["chunks"][i]
        assert chunk_result["success"] is True
        assert len(chunk_result["chunk_data"]) == 256 * 1024
        # First byte should match chunk index
        assert chunk_result["chunk_data"][0] == i


@pytest.mark.asyncio
async def test_concurrent_same_chunk_request_deduplication(resumable_ops):
    """Test that concurrent requests for the same chunk are deduplicated."""
    resumable, mock_ipfs, temp_dir = resumable_ops
    
    # Start a resumable write with parallel transfers
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    file_id = await resumable.start_resumable_write(
        file_path="/test/file.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024,
        parallel_transfers=True,
        max_parallel_chunks=3
    )
    
    # Reset mock
    mock_ipfs.files_write.reset_mock()
    
    # Configure mock to delay responses
    async def delayed_write(*args, **kwargs):
        await anyio.sleep(0.1)
        return {"Hash": "test-hash"}
        
    mock_ipfs.files_write.side_effect = delayed_write
    
    # Prepare chunk data
    chunk_data = b"x" * (256 * 1024)
    
    # Create multiple concurrent requests for the same chunk
    tasks = []
    for _ in range(3):
        task = anyio.create_task(
            resumable.write_chunk(file_id, chunk_data, chunk_index=0)
        )
        tasks.append(task)
    
    # Wait for all tasks to complete
    results = await anyio.gather(*tasks)
    
    # Verify all tasks succeeded
    for result in results:
        assert result["success"] is True
    
    # Verify write was called only once (deduplication worked)
    assert mock_ipfs.files_write.call_count == 1


@pytest.mark.asyncio
async def test_parallel_read_performance(resumable_ops):
    """Test that parallel reads improve performance."""
    resumable, mock_ipfs, temp_dir = resumable_ops
    
    # Configure mock
    mock_ipfs.files_stat.return_value = {"Size": 10 * 1024 * 1024, "Hash": "test-hash"}
    
    # Configure mock to simulate network delay
    async def slow_read(path, offset, count):
        await anyio.sleep(0.05)  # 50ms per read
        return b"x" * count
        
    mock_ipfs.files_read.side_effect = slow_read
    
    # Start a sequential read
    seq_file_id = await resumable.start_resumable_read(
        file_path="/test/file.txt",
        chunk_size=1 * 1024 * 1024,  # 1MB chunks
        parallel_transfers=False
    )
    
    # Read 3 chunks sequentially
    start_time = time.time()
    for i in range(3):
        result = await resumable.read_chunk(seq_file_id, chunk_index=i)
        assert result["success"] is True
    sequential_time = time.time() - start_time
    
    # Reset mock read count
    mock_ipfs.files_read.reset_mock()
    
    # Start a parallel read
    par_file_id = await resumable.start_resumable_read(
        file_path="/test/file.txt",
        chunk_size=1 * 1024 * 1024,  # 1MB chunks
        parallel_transfers=True,
        max_parallel_chunks=3
    )
    
    # Read 3 chunks in parallel
    start_time = time.time()
    result = await resumable.read_multiple_chunks(
        par_file_id,
        chunk_indices=[0, 1, 2]
    )
    parallel_time = time.time() - start_time
    
    # Verify parallel read was faster
    assert parallel_time < sequential_time
    
    # Read should be called 3 times for each method
    assert mock_ipfs.files_read.call_count == 3
    
    # All chunks should be successful
    assert result["success"] is True
    assert result["completed_chunks"] == 3


@pytest.mark.asyncio
async def test_resume_operation(resumable_ops):
    """Test resuming an interrupted operation."""
    resumable, mock_ipfs, temp_dir = resumable_ops
    
    # Start a resumable write
    mock_ipfs.files_stat.side_effect = Exception("File not found")
    file_id = await resumable.start_resumable_write(
        file_path="/test/file.txt",
        total_size=1024 * 1024,
        chunk_size=256 * 1024
    )
    
    # Write first two chunks
    chunk_data = b"x" * (256 * 1024)
    await resumable.write_chunk(file_id, chunk_data, chunk_index=0)
    await resumable.write_chunk(file_id, chunk_data, chunk_index=1)
    
    # Mark a chunk as in-progress (simulating interruption)
    state = await resumable.load_state(file_id)
    state.chunks[2].status = "in_progress"
    await resumable.save_state(file_id, state)
    
    # Resume operation
    result = await resumable.resume_operation(file_id)
    
    # Verify result
    assert result["success"] is True
    assert result["completion_percentage"] == 50.0  # 2/4 chunks
    assert len(result["remaining_chunks"]) == 2
    
    # Verify in-progress chunk is reset to pending
    state = await resumable.load_state(file_id)
    assert state.chunks[2].status == "pending"


@pytest.mark.asyncio
async def test_file_like_interface(resumable_ops):
    """Test file-like interface for reading and writing."""
    resumable, mock_ipfs, temp_dir = resumable_ops
    
    # Mock open_resumable to return our test instances
    async def mock_open_resumable(ipfs, path, mode, **kwargs):
        if mode == "rb":
            read_stream = ResumableReadStream(resumable, "test-read-id")
            read_stream.read = AsyncMock(return_value=b"test data")
            read_stream.seek = AsyncMock(return_value=0)
            read_stream.tell = AsyncMock(return_value=0)
            read_stream.close = AsyncMock()
            return read_stream
        else:
            write_stream = ResumableWriteStream(resumable, "test-write-id")
            write_stream.write = AsyncMock(return_value=9)  # length of "test data"
            write_stream.flush = AsyncMock()
            write_stream.seek = AsyncMock(return_value=0)
            write_stream.tell = AsyncMock(return_value=9)
            write_stream.close = AsyncMock()
            return write_stream
    
    with patch('ipfs_kit_py.mfs_enhanced_resumable.open_resumable', mock_open_resumable):
        # Test writing
        write_stream = await open_resumable(mock_ipfs, "/test/file.txt", mode="wb")
        bytes_written = await write_stream.write(b"test data")
        assert bytes_written == 9
        await write_stream.flush()
        position = await write_stream.tell()
        assert position == 9
        await write_stream.close()
        
        # Test reading
        read_stream = await open_resumable(mock_ipfs, "/test/file.txt", mode="rb")
        data = await read_stream.read()
        assert data == b"test data"
        await read_stream.seek(0)
        position = await read_stream.tell()
        assert position == 0
        await read_stream.close()