#!/usr/bin/env python3
"""
Examples demonstrating how to use the resumable MFS operations.

This file provides practical examples for using the resumable file operations
for IPFS MFS, allowing operations to be paused and resumed after connection loss.
"""

import anyio
import os
import random
import tempfile
import time
from pathlib import Path

# Import the necessary modules
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.mfs_enhanced_resumable import (
    ResumableFileOperations,
    ResumableReadStream,
    ResumableWriteStream,
    open_resumable
)


async def example_resumable_write():
    """Demonstrate resumable writing to MFS."""
    print("\n--- Resumable Write Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create a test directory
    test_dir = "/mfs_resumable_examples"
    await ipfs.files_mkdir(test_dir, parents=True)
    
    # Create a file path for our example
    file_path = f"{test_dir}/resumable_write_example.bin"
    
    # Initialize resumable operations
    resumable = ResumableFileOperations(ipfs)
    
    # Prepare data for writing (1MB chunks)
    total_size = 5 * 1024 * 1024  # 5MB total
    chunk_size = 1 * 1024 * 1024  # 1MB per chunk
    
    # Start a resumable write operation
    file_id = await resumable.start_resumable_write(
        file_path=file_path,
        total_size=total_size,
        chunk_size=chunk_size,
        metadata={"description": "Resumable write example"}
    )
    
    print(f"Started resumable write operation with ID: {file_id}")
    print(f"File path: {file_path}")
    print(f"Total size: {total_size} bytes")
    print(f"Chunk size: {chunk_size} bytes")
    
    # Write the first 3 chunks
    for i in range(3):
        # Generate random data for the chunk
        chunk_data = bytes([random.randint(0, 255) for _ in range(chunk_size)])
        
        # Write the chunk
        result = await resumable.write_chunk(file_id, chunk_data, chunk_index=i)
        
        if result["success"]:
            print(f"Chunk {i+1}/5 written successfully ({result['completion_percentage']:.1f}% complete)")
        else:
            print(f"Failed to write chunk {i+1}: {result.get('error')}")
    
    # Simulate a connection loss or process interruption
    print("\nSimulating connection loss or process interruption...")
    
    # In a real scenario, the program might exit here, and be restarted later
    # When it restarts, it would need to recover the file ID from somewhere
    # (e.g., a database or a file on disk)
    
    # List resumable operations to find our file
    operations = await resumable.list_resumable_operations()
    for op in operations:
        if op["file_path"] == file_path:
            recovered_file_id = op["file_id"]
            print(f"Found resumable operation for {file_path} with ID: {recovered_file_id}")
            print(f"Current completion: {op['completion_percentage']:.1f}%")
            break
    
    # Resume the operation
    resume_result = await resumable.resume_operation(file_id)
    if resume_result["success"]:
        print(f"Operation resumed successfully")
        print(f"Remaining chunks: {len(resume_result['remaining_chunks'])}")
    else:
        print(f"Failed to resume operation: {resume_result.get('error')}")
        return
    
    # Write the remaining chunks
    remaining_chunks = resume_result["remaining_chunks"]
    for i, chunk_info in enumerate(remaining_chunks):
        # Generate random data for the chunk
        chunk_data = bytes([random.randint(0, 255) for _ in range(chunk_info["size"])])
        
        # Write the chunk
        result = await resumable.write_chunk(
            file_id, 
            chunk_data, 
            offset=chunk_info["start"]
        )
        
        if result["success"]:
            print(f"Chunk {i+3+1}/5 written successfully ({result['completion_percentage']:.1f}% complete)")
        else:
            print(f"Failed to write chunk {i+3+1}: {result.get('error')}")
    
    # Finalize the write operation
    finalize_result = await resumable.finalize_write(file_id)
    if finalize_result["success"]:
        print(f"Write operation finalized successfully")
        print(f"File hash: {finalize_result['hash']}")
    else:
        print(f"Failed to finalize write operation: {finalize_result.get('error')}")
    
    # Verify the file size
    stats = await ipfs.files_stat(file_path)
    print(f"Final file size: {stats.get('Size')} bytes")


async def example_resumable_read():
    """Demonstrate resumable reading from MFS."""
    print("\n--- Resumable Read Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create a test directory
    test_dir = "/mfs_resumable_examples"
    await ipfs.files_mkdir(test_dir, parents=True)
    
    # Create a file for reading
    file_path = f"{test_dir}/resumable_read_example.txt"
    
    # Create some test content (100KB of text)
    content = b"This is line %d of the test file.\n" * 5000
    await ipfs.files_write(file_path, content, create=True)
    
    # Get file stats
    stats = await ipfs.files_stat(file_path)
    print(f"Created test file at {file_path}")
    print(f"File size: {stats.get('Size')} bytes")
    
    # Initialize resumable operations
    resumable = ResumableFileOperations(ipfs)
    
    # Start a resumable read operation with 10KB chunks
    chunk_size = 10 * 1024  # 10KB per chunk
    file_id = await resumable.start_resumable_read(
        file_path=file_path,
        chunk_size=chunk_size,
        metadata={"description": "Resumable read example"}
    )
    
    print(f"Started resumable read operation with ID: {file_id}")
    print(f"Chunk size: {chunk_size} bytes")
    
    # Read the first 3 chunks
    for i in range(3):
        result = await resumable.read_chunk(file_id, chunk_index=i)
        
        if result["success"]:
            # Print a sample of the chunk (first 50 bytes)
            sample = result["chunk_data"][:50]
            print(f"Chunk {i+1} read successfully, first 50 bytes: {sample}")
            print(f"Completion: {result['completion_percentage']:.1f}%")
        else:
            print(f"Failed to read chunk {i+1}: {result.get('error')}")
    
    # Simulate a connection loss or process interruption
    print("\nSimulating connection loss or process interruption...")
    
    # Resume the operation
    resume_result = await resumable.resume_operation(file_id)
    if resume_result["success"]:
        print(f"Operation resumed successfully")
        print(f"Current completion: {resume_result['completion_percentage']:.1f}%")
    else:
        print(f"Failed to resume operation: {resume_result.get('error')}")
        return
    
    # Read the next 2 chunks
    for i in range(3, 5):
        result = await resumable.read_chunk(file_id, chunk_index=i)
        
        if result["success"]:
            # Print a sample of the chunk (first 50 bytes)
            sample = result["chunk_data"][:50]
            print(f"Chunk {i+1} read successfully, first 50 bytes: {sample}")
            print(f"Completion: {result['completion_percentage']:.1f}%")
        else:
            print(f"Failed to read chunk {i+1}: {result.get('error')}")
    
    # Finalize the read operation
    finalize_result = await resumable.finalize_read(file_id)
    if finalize_result["success"]:
        print(f"Read operation finalized successfully")
    else:
        print(f"Failed to finalize read operation: {finalize_result.get('error')}")


async def example_file_like_interface():
    """Demonstrate file-like interface for resumable operations."""
    print("\n--- File-like Interface Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create a test directory
    test_dir = "/mfs_resumable_examples"
    await ipfs.files_mkdir(test_dir, parents=True)
    
    # File path for our example
    file_path = f"{test_dir}/file_like_example.txt"
    
    # Open a file for writing
    print("\nWriting to file using file-like interface...")
    async with await open_resumable(ipfs, file_path, mode="wb") as f:
        # Write multiple chunks of data
        for i in range(10):
            data = f"This is line {i+1} of the test file.\n".encode()
            await f.write(data)
            print(f"Wrote {len(data)} bytes at position {await f.tell()}")
    
    # Get file stats after writing
    stats = await ipfs.files_stat(file_path)
    print(f"\nFile size after writing: {stats.get('Size')} bytes")
    
    # Open the file for reading
    print("\nReading from file using file-like interface...")
    async with await open_resumable(ipfs, file_path, mode="rb") as f:
        # Read the entire file
        content = await f.read()
        print(f"Read {len(content)} bytes from file")
        print(f"First 100 bytes: {content[:100]}")
        
        # Seek to a position and read again
        await f.seek(0)  # Go back to the beginning
        first_line = await f.read(50)  # Read 50 bytes
        print(f"\nAfter seek(0), read 50 bytes: {first_line}")
        
        # Seek to middle and read
        await f.seek(len(content) // 2)
        middle_content = await f.read(50)
        print(f"After seek to middle, read 50 bytes: {middle_content}")


async def example_interrupted_large_file():
    """Demonstrate handling interruptions with a large file."""
    print("\n--- Interrupted Large File Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create a test directory
    test_dir = "/mfs_resumable_examples"
    await ipfs.files_mkdir(test_dir, parents=True)
    
    # File path for our example
    file_path = f"{test_dir}/large_interrupted_file.bin"
    
    # Create a temporary local file (10MB)
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name
        # Write 10MB of random data
        for _ in range(10):
            # Write 1MB at a time
            temp_file.write(bytes([random.randint(0, 255) for _ in range(1024 * 1024)]))
    
    print(f"Created temporary file of 10MB at {temp_path}")
    
    # Initialize resumable operations
    resumable = ResumableFileOperations(ipfs)
    
    # Start a resumable write with 2MB chunks
    chunk_size = 2 * 1024 * 1024  # 2MB per chunk
    file_id = await resumable.start_resumable_write(
        file_path=file_path,
        total_size=10 * 1024 * 1024,  # 10MB
        chunk_size=chunk_size
    )
    
    print(f"Started resumable write with ID: {file_id}")
    print(f"Chunk size: {chunk_size} bytes (5 chunks total)")
    
    # Read and upload the first 2 chunks
    with open(temp_path, "rb") as f:
        for i in range(2):
            chunk_data = f.read(chunk_size)
            result = await resumable.write_chunk(file_id, chunk_data, chunk_index=i)
            
            if result["success"]:
                print(f"Chunk {i+1}/5 written successfully ({result['completion_percentage']:.1f}% complete)")
            else:
                print(f"Failed to write chunk {i+1}: {result.get('error')}")
    
    # Simulate interruption
    print("\nSimulating process interruption after 2/5 chunks...")
    
    # In a real scenario, information about the file_id and temporary file would
    # need to be saved and restored. Here we just continue using the same variables.
    
    print("\nResuming upload after interruption...")
    
    # Resume the operation
    resume_result = await resumable.resume_operation(file_id)
    if resume_result["success"]:
        print(f"Operation resumed successfully")
        print(f"Current completion: {resume_result['completion_percentage']:.1f}%")
        print(f"Remaining chunks: {len(resume_result['remaining_chunks'])}")
    else:
        print(f"Failed to resume operation: {resume_result.get('error')}")
        return
    
    # Upload remaining chunks
    with open(temp_path, "rb") as f:
        # Skip the chunks we've already uploaded
        f.seek(2 * chunk_size)
        
        # Upload remaining chunks
        for i in range(2, 5):
            chunk_data = f.read(chunk_size)
            result = await resumable.write_chunk(file_id, chunk_data, chunk_index=i)
            
            if result["success"]:
                print(f"Chunk {i+1}/5 written successfully ({result['completion_percentage']:.1f}% complete)")
            else:
                print(f"Failed to write chunk {i+1}: {result.get('error')}")
    
    # Finalize the write operation
    finalize_result = await resumable.finalize_write(file_id)
    if finalize_result["success"]:
        print(f"Write operation finalized successfully")
        print(f"File hash: {finalize_result['hash']}")
    else:
        print(f"Failed to finalize write operation: {finalize_result.get('error')}")
    
    # Verify the file size
    stats = await ipfs.files_stat(file_path)
    print(f"Final file size: {stats.get('Size')} bytes")
    
    # Clean up the temporary file
    os.unlink(temp_path)


async def example_manage_resumable_operations():
    """Demonstrate managing resumable operations."""
    print("\n--- Managing Resumable Operations Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Initialize resumable operations
    resumable = ResumableFileOperations(ipfs)
    
    # List all current resumable operations
    operations = await resumable.list_resumable_operations()
    
    print(f"Found {len(operations)} active resumable operations:")
    for i, op in enumerate(operations, 1):
        print(f"{i}. File: {op['file_path']}")
        print(f"   ID: {op['file_id']}")
        print(f"   Size: {op['total_size']} bytes")
        print(f"   Completion: {op['completion_percentage']:.1f}%")
        print(f"   Created: {time.ctime(op['created_at'])}")
    
    if operations:
        # Copy a partially completed file to a new location
        print("\nCopying a partially completed file to a new location...")
        source_id = operations[0]["file_id"]
        destination_path = f"/mfs_resumable_examples/copied_partial_file_{int(time.time())}"
        
        copy_result = await resumable.copy_resumable(source_id, destination_path)
        if copy_result["success"]:
            print(f"File copied successfully to {destination_path}")
            print(f"Completion percentage: {copy_result['completion_percentage']:.1f}%")
        else:
            print(f"Failed to copy file: {copy_result.get('error')}")
    else:
        print("\nNo resumable operations to manage")


async def example_progress_monitoring():
    """Demonstrate progress monitoring with callbacks."""
    print("\n--- Progress Monitoring Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create a test directory
    test_dir = "/mfs_resumable_examples"
    await ipfs.files_mkdir(test_dir, parents=True)
    
    # File path for our example
    file_path = f"{test_dir}/progress_monitored_file.bin"
    
    # Initialize resumable operations
    resumable = ResumableFileOperations(ipfs)
    
    # Define progress callback
    def progress_callback(progress_info):
        """Display progress information."""
        if progress_info["status"] == "chunk_completed":
            # Format speeds in KB/s
            avg_speed_kb = progress_info["average_speed_bytes_per_sec"] / 1024
            current_speed_kb = progress_info["current_speed_bytes_per_sec"] / 1024
            
            # Format time remaining
            time_remaining = progress_info["estimated_time_remaining_sec"]
            if time_remaining > 60:
                time_str = f"{time_remaining/60:.1f} minutes"
            else:
                time_str = f"{time_remaining:.1f} seconds"
            
            print(f"Progress: {progress_info['completion_percentage']:.1f}% completed")
            print(f"  Speed: {avg_speed_kb:.2f} KB/s (avg), {current_speed_kb:.2f} KB/s (current)")
            print(f"  Remaining: {progress_info['bytes_remaining']/1024:.1f} KB, estimated {time_str}")
            print()
        elif progress_info["status"] == "operation_resumed":
            print(f"Operation resumed. {progress_info['completion_percentage']:.1f}% already completed")
            print(f"  {len(progress_info['remaining_chunks'])} chunks remaining to process")
            print()
    
    # Create a file with 10 chunks of 1MB each
    total_size = 10 * 1024 * 1024  # 10 MB
    chunk_size = 1 * 1024 * 1024   # 1 MB chunks
    
    # Start a resumable write operation
    file_id = await resumable.start_resumable_write(
        file_path=file_path,
        total_size=total_size,
        chunk_size=chunk_size
    )
    
    # Register progress callback
    resumable.register_progress_callback(file_id, progress_callback)
    
    print(f"Started monitored write operation with ID: {file_id}")
    print(f"File: {file_path}, Size: {total_size/1024/1024:.1f} MB, Chunks: {total_size/chunk_size:.0f}")
    print()
    
    # Write 5 chunks with random delays to simulate network conditions
    for i in range(5):
        # Generate random data
        chunk_data = bytes([random.randint(0, 255) for _ in range(chunk_size)])
        
        # Add a random delay to simulate network conditions
        delay = random.uniform(0.1, 1.0)
        print(f"Waiting {delay:.2f} seconds before writing chunk {i+1}...")
        await anyio.sleep(delay)
        
        # Write the chunk
        result = await resumable.write_chunk(file_id, chunk_data, chunk_index=i)
        
        if not result["success"]:
            print(f"Failed to write chunk {i+1}: {result.get('error')}")
    
    # Simulate longer interrupt
    print("\nSimulating longer interruption (3 seconds)...")
    await anyio.sleep(3)
    
    # Resume operation
    resume_result = await resumable.resume_operation(file_id)
    if not resume_result["success"]:
        print(f"Failed to resume operation: {resume_result.get('error')}")
        return
    
    # Write remaining chunks with different delays
    for i in range(5, 10):
        # Generate random data
        chunk_data = bytes([random.randint(0, 255) for _ in range(chunk_size)])
        
        # Add a different delay pattern to simulate changed network conditions
        delay = random.uniform(0.05, 0.5)  # Faster after "resuming"
        print(f"Waiting {delay:.2f} seconds before writing chunk {i+1}...")
        await anyio.sleep(delay)
        
        # Write the chunk
        result = await resumable.write_chunk(file_id, chunk_data, chunk_index=i)
        
        if not result["success"]:
            print(f"Failed to write chunk {i+1}: {result.get('error')}")
    
    # Finalize the operation
    finalize_result = await resumable.finalize_write(file_id)
    if finalize_result["success"]:
        print(f"\nWrite operation completed successfully")
        print(f"File hash: {finalize_result['hash']}")
    else:
        print(f"\nFailed to finalize write operation: {finalize_result.get('error')}")
    
    # Unregister callback
    resumable.unregister_progress_callback(file_id)

async def example_adaptive_chunking():
    """Demonstrate adaptive chunk sizing based on network conditions."""
    print("\n--- Adaptive Chunk Sizing Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create a test directory
    test_dir = "/mfs_resumable_examples"
    await ipfs.files_mkdir(test_dir, parents=True)
    
    # File path for our example
    file_path = f"{test_dir}/adaptive_chunk_file.bin"
    
    # Initialize resumable operations
    resumable = ResumableFileOperations(ipfs)
    
    # Create a file with 20MB total size, starting with 512KB chunks
    total_size = 20 * 1024 * 1024  # 20 MB
    initial_chunk_size = 512 * 1024  # 512 KB chunks
    
    # Define a callback to monitor chunk statistics
    def stats_callback(progress_info):
        """Display chunk transfer statistics."""
        if progress_info["status"] == "chunk_completed":
            print(f"Chunk completed: {progress_info['chunk_start']/1024/1024:.2f}MB - {progress_info['chunk_end']/1024/1024:.2f}MB")
            print(f"  Transfer time: {progress_info['transfer_time']:.3f} seconds")
            print(f"  Transfer rate: {progress_info['transfer_rate']/1024/1024:.2f} MB/s")
            if "optimal_chunk_size" in progress_info:
                print(f"  Current optimal chunk size: {progress_info['optimal_chunk_size']/1024:.1f} KB")
            print()
    
    # Start a resumable write operation with adaptive chunking
    file_id = await resumable.start_resumable_write(
        file_path=file_path,
        total_size=total_size,
        chunk_size=initial_chunk_size,
        adaptive_chunking=True  # Enable adaptive chunking
    )
    
    # Register progress callback
    resumable.register_progress_callback(file_id, stats_callback)
    
    print(f"Started adaptive write operation with ID: {file_id}")
    print(f"File: {file_path}, Size: {total_size/1024/1024:.1f} MB, Initial chunk size: {initial_chunk_size/1024:.1f} KB")
    print()
    
    # Load state to get chunk info
    state = await resumable.load_state(file_id)
    
    # Test different write speeds to simulate varying network conditions
    
    # First phase: Slow writes (simulate congested network)
    print("Phase 1: Slow network simulation...")
    for i in range(10):
        # Generate random data
        chunk = state.chunks[i]
        chunk_data = bytes([random.randint(0, 255) for _ in range(chunk.size)])
        
        # Add artificial delay to simulate slow network
        delay = random.uniform(0.5, 1.0)  # Longer delay
        await anyio.sleep(delay)
        
        # Write the chunk
        result = await resumable.write_chunk(file_id, chunk_data, chunk_index=i)
        if not result["success"]:
            print(f"Failed to write chunk {i+1}: {result.get('error')}")
    
    print("\nPhase 2: Fast network simulation...")
    # Second phase: Fast writes (simulate better network)
    for i in range(10, len(state.chunks)):
        # Generate random data
        chunk = state.chunks[i]
        chunk_data = bytes([random.randint(0, 255) for _ in range(chunk.size)])
        
        # Add shorter artificial delay to simulate faster network
        delay = random.uniform(0.05, 0.2)  # Shorter delay
        await anyio.sleep(delay)
        
        # Write the chunk
        result = await resumable.write_chunk(file_id, chunk_data, chunk_index=i)
        if not result["success"]:
            print(f"Failed to write chunk {i+1}: {result.get('error')}")
    
    # Finalize the operation
    finalize_result = await resumable.finalize_write(file_id)
    if finalize_result["success"]:
        print(f"\nWrite operation completed successfully")
        print(f"File hash: {finalize_result['hash']}")
        
        # Report final chunk size adaptation
        state = await resumable.load_state(file_id)
        print(f"Final optimal chunk size: {state.optimal_chunk_size/1024:.1f} KB")
        print(f"Initial chunk size: {initial_chunk_size/1024:.1f} KB")
        print(f"Adaptation factor: {state.optimal_chunk_size/initial_chunk_size:.2f}x")
    else:
        print(f"\nFailed to finalize write operation: {finalize_result.get('error')}")
    
    # Unregister callback
    resumable.unregister_progress_callback(file_id)

async def example_parallel_transfers():
    """Demonstrate parallel transfer capabilities for improved throughput."""
    print("\n--- Parallel Transfers Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create a test directory
    test_dir = "/mfs_resumable_examples"
    await ipfs.files_mkdir(test_dir, parents=True)
    
    # Create a file path for our example
    file_path = f"{test_dir}/parallel_transfer_example.bin"
    
    # Initialize resumable operations
    resumable = ResumableFileOperations(ipfs, max_concurrent_transfers=4)
    
    # Total size and chunk size
    total_size = 20 * 1024 * 1024  # 20MB
    chunk_size = 1 * 1024 * 1024   # 1MB chunks (20 chunks total)
    
    # Define a progress callback that shows parallel transfer information
    def parallel_progress_callback(progress_info):
        """Display progress information with parallel transfer details."""
        if progress_info["status"] == "chunk_completed":
            chunk_idx = progress_info.get("chunk_index", "unknown")
            print(f"Chunk {chunk_idx} completed: {progress_info['chunk_start']/1024/1024:.2f}MB - {progress_info['chunk_end']/1024/1024:.2f}MB")
            print(f"  Transfer time: {progress_info['transfer_time']:.3f} seconds")
            print(f"  Transfer rate: {progress_info['transfer_rate']/1024/1024:.2f} MB/s")
            print(f"  Overall progress: {progress_info['completion_percentage']:.1f}%")
            print()
    
    # Start a resumable write operation with parallel transfers enabled
    file_id = await resumable.start_resumable_write(
        file_path=file_path,
        total_size=total_size,
        chunk_size=chunk_size,
        metadata={"description": "Parallel transfer example"},
        parallel_transfers=True,      # Enable parallel transfers
        max_parallel_chunks=4         # Set maximum concurrent chunks
    )
    
    # Register progress callback
    resumable.register_progress_callback(file_id, parallel_progress_callback)
    
    print(f"Started parallel write operation with ID: {file_id}")
    print(f"File path: {file_path}")
    print(f"Total size: {total_size/1024/1024:.1f}MB, {total_size/chunk_size:.0f} chunks of {chunk_size/1024:.0f}KB each")
    print(f"Maximum concurrent transfers: 4")
    print()
    
    # First run a non-parallel transfer for comparison (5 chunks)
    print("Phase 1: Sequential transfers (for comparison)...")
    start_time = time.time()
    for i in range(5):
        # Generate random data
        chunk_data = os.urandom(chunk_size)
        
        # Write the chunk
        result = await resumable.write_chunk(file_id, chunk_data, chunk_index=i)
        if not result["success"]:
            print(f"Failed to write chunk {i+1}: {result.get('error')}")
    
    sequential_time = time.time() - start_time
    print(f"Sequential transfer of 5 chunks took {sequential_time:.2f} seconds")
    print(f"Average time per chunk: {sequential_time/5:.2f} seconds")
    print()
    
    # Now use parallel transfers for the remaining chunks
    print("Phase 2: Parallel transfers (4 concurrent chunks)...")
    
    # Prepare data for 8 chunks to send in parallel
    chunks_data = []
    for i in range(5, 13):
        chunk_data = os.urandom(chunk_size)
        chunks_data.append((i, chunk_data))
    
    # Send multiple chunks in parallel
    start_time = time.time()
    result = await resumable.write_multiple_chunks(file_id, chunks_data)
    parallel_time = time.time() - start_time
    
    print(f"Parallel transfer of 8 chunks took {parallel_time:.2f} seconds")
    print(f"Average time per chunk: {parallel_time/8:.2f} seconds")
    print(f"Speedup factor: {(sequential_time/5)/(parallel_time/8):.2f}x faster per chunk")
    print()
    
    if result["success"]:
        print(f"Successfully transferred {result['completed_chunks']} chunks in parallel")
        print(f"Current completion: {result['completion_percentage']:.1f}%")
    else:
        print(f"Some parallel transfers failed: {result['failed_chunks']} failures")
        print(f"Current completion: {result['completion_percentage']:.1f}%")
    
    # Transfer the remaining chunks individually (still using parallel infrastructure)
    print("\nPhase 3: Individual writes with parallel infrastructure...")
    remaining_start = time.time()
    for i in range(13, 20):
        chunk_data = os.urandom(chunk_size)
        result = await resumable.write_chunk(file_id, chunk_data, chunk_index=i)
        if not result["success"]:
            print(f"Failed to write chunk {i+1}: {result.get('error')}")
    
    remaining_time = time.time() - remaining_start
    print(f"Individual writes of 7 chunks with parallel infrastructure took {remaining_time:.2f} seconds")
    print()
    
    # Finalize the write operation
    finalize_result = await resumable.finalize_write(file_id)
    if finalize_result["success"]:
        print(f"Write operation finalized successfully")
        print(f"File hash: {finalize_result['hash']}")
    else:
        print(f"Failed to finalize write operation: {finalize_result.get('error')}")
    
    # Now demonstrate parallel reads
    print("\n--- Parallel Read Demonstration ---")
    
    # Start a resumable read operation with parallel transfers
    read_file_id = await resumable.start_resumable_read(
        file_path=file_path,
        chunk_size=chunk_size,
        parallel_transfers=True,
        max_parallel_chunks=4
    )
    
    # Register progress callback
    resumable.register_progress_callback(read_file_id, parallel_progress_callback)
    
    print(f"Started parallel read operation with ID: {read_file_id}")
    print()
    
    # First read a few chunks sequentially for comparison
    print("Phase 1: Sequential reads (for comparison)...")
    start_time = time.time()
    for i in range(3):
        result = await resumable.read_chunk(read_file_id, chunk_index=i)
        if not result["success"]:
            print(f"Failed to read chunk {i+1}: {result.get('error')}")
    
    sequential_read_time = time.time() - start_time
    print(f"Sequential reading of 3 chunks took {sequential_read_time:.2f} seconds")
    print(f"Average time per chunk: {sequential_read_time/3:.2f} seconds")
    print()
    
    # Now read multiple chunks in parallel
    print("Phase 2: Parallel reads (4 concurrent chunks)...")
    start_time = time.time()
    result = await resumable.read_multiple_chunks(
        read_file_id,
        chunk_indices=[3, 4, 5, 6, 7, 8, 9],  # Read 7 chunks
        max_chunks=4  # Maximum 4 concurrent chunks
    )
    parallel_read_time = time.time() - start_time
    
    print(f"Parallel reading of 7 chunks took {parallel_read_time:.2f} seconds")
    print(f"Average time per chunk: {parallel_read_time/7:.2f} seconds")
    print(f"Speedup factor: {(sequential_read_time/3)/(parallel_read_time/7):.2f}x faster per chunk")
    print()
    
    if result["success"]:
        print(f"Successfully read {result['completed_chunks']} chunks in parallel")
        total_data = sum(len(result["chunks"][idx]["chunk_data"]) for idx in result["chunks"] if result["chunks"][idx]["success"])
        print(f"Total data read: {total_data/1024/1024:.2f}MB")
    else:
        print(f"Some parallel reads failed: {result['failed_chunks']} failures")
    
    # Read the remaining chunks
    print("\nPhase 3: Reading remaining chunks...")
    for i in range(10, 20):
        result = await resumable.read_chunk(read_file_id, chunk_index=i)
        if not result["success"]:
            print(f"Failed to read chunk {i+1}: {result.get('error')}")
    
    # Finalize the read operation
    await resumable.finalize_read(read_file_id)
    print("Read operation completed successfully")
    
    # Unregister callbacks
    resumable.unregister_progress_callback(file_id)
    resumable.unregister_progress_callback(read_file_id)

async def main():
    """Run all examples."""
    print("=== Resumable MFS Operations Examples ===\n")
    
    # Run the examples
    try:
        # Comment out all examples except the parallel transfers one
        # to focus on just the new functionality
        # await example_resumable_write()
        # await example_resumable_read()
        # await example_file_like_interface()
        # await example_interrupted_large_file()
        # await example_manage_resumable_operations()
        # await example_progress_monitoring()
        # await example_adaptive_chunking()
        await example_parallel_transfers()
    except Exception as e:
        print(f"Error in examples: {str(e)}")
    
    print("\n=== Examples Completed ===")

if __name__ == "__main__":
    anyio.run(main())