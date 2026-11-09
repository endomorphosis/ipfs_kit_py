#!/usr/bin/env python3
"""
Examples demonstrating how to use the enhanced MFS functionality.

This file contains practical examples for using the enhanced MFS features 
implemented in the ipfs_kit_py.mfs_enhanced module.
"""

import anyio
import os
import tempfile
import time
from pathlib import Path

# Import the necessary modules
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.mfs_enhanced import (
    MFSTransaction, 
    DirectorySynchronizer, 
    ContentTypeDetector,
    PathUtils,
    MFSChangeWatcher,
    copy_content_batch,
    move_content_batch,
    create_file_with_type
)

async def example_mfs_transaction():
    """Demonstrate using MFSTransaction for atomic operations."""
    print("\n--- MFSTransaction Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create a test directory
    test_dir = "/mfs_examples"
    await ipfs.files_mkdir(test_dir, parents=True)
    
    # Use a transaction to create multiple files atomically
    async with MFSTransaction(ipfs) as transaction:
        # Add files to the transaction
        await transaction.add_operation(
            ipfs.files_write, 
            f"{test_dir}/file1.txt", 
            "Content for file 1".encode(),
            create=True
        )
        
        await transaction.add_operation(
            ipfs.files_write, 
            f"{test_dir}/file2.txt", 
            "Content for file 2".encode(),
            create=True
        )
        
        # This would cause an error - uncomment to test rollback
        # await transaction.add_operation(
        #     ipfs.files_cp, 
        #     "/non_existent_file", 
        #     f"{test_dir}/file3.txt"
        # )
    
    # Check the result
    ls_result = await ipfs.files_ls(test_dir)
    print(f"Files created in transaction: {[entry['Name'] for entry in ls_result.get('Entries', [])]}")
    
    # Demonstrate a transaction that rolls back
    print("\nNow demonstrating a transaction that will roll back:")
    try:
        async with MFSTransaction(ipfs) as transaction:
            # Add a valid operation
            await transaction.add_operation(
                ipfs.files_write, 
                f"{test_dir}/will_not_exist.txt", 
                "This file should not exist after rollback".encode(),
                create=True
            )
            
            # Add an operation that will fail
            await transaction.add_operation(
                ipfs.files_cp, 
                "/non_existent_file", 
                f"{test_dir}/another_file.txt"
            )
    except Exception as e:
        print(f"Transaction failed and rolled back as expected: {str(e)}")
    
    # Verify the file doesn't exist after rollback
    ls_result = await ipfs.files_ls(test_dir)
    print(f"Files after failed transaction: {[entry['Name'] for entry in ls_result.get('Entries', [])]}")
    print("'will_not_exist.txt' should not be in the list if rollback worked correctly.")

async def example_directory_synchronizer():
    """Demonstrate using DirectorySynchronizer for bidirectional syncing."""
    print("\n--- DirectorySynchronizer Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create temporary local directory
    with tempfile.TemporaryDirectory() as local_dir:
        # Create some local test files
        with open(os.path.join(local_dir, "local_file1.txt"), "w") as f:
            f.write("Content for local file 1")
            
        with open(os.path.join(local_dir, "local_file2.txt"), "w") as f:
            f.write("Content for local file 2")
            
        # Create a subdirectory with a file
        subdir = os.path.join(local_dir, "subdir")
        os.makedirs(subdir, exist_ok=True)
        with open(os.path.join(subdir, "subdir_file.txt"), "w") as f:
            f.write("Content for file in subdirectory")
        
        # Create test MFS directory
        mfs_dir = "/mfs_sync_example"
        await ipfs.files_mkdir(mfs_dir, parents=True)
        
        # Create a file directly in MFS
        await ipfs.files_write(f"{mfs_dir}/mfs_file.txt", "Content for MFS file".encode(), create=True)
        
        # Initialize the synchronizer
        sync = DirectorySynchronizer(ipfs, local_dir, mfs_dir)
        
        # Perform initial sync from local to MFS
        print("\nSyncing from local directory to MFS:")
        sync_result = await sync.sync_local_to_mfs()
        print(f"Files added: {len(sync_result['added'])}")
        print(f"Files updated: {len(sync_result['updated'])}")
        
        # List files in MFS after sync
        ls_result = await ipfs.files_ls(mfs_dir, long=True)
        print("\nFiles in MFS after sync:")
        for entry in ls_result.get('Entries', []):
            print(f"- {entry['Name']} ({entry['Size']} bytes)")
            
        # Create a new file in MFS
        await ipfs.files_write(
            f"{mfs_dir}/new_mfs_file.txt", 
            "This is a new file created in MFS".encode(), 
            create=True
        )
        
        # Sync from MFS to local
        print("\nSyncing from MFS to local directory:")
        sync_result = await sync.sync_mfs_to_local()
        print(f"Files added: {len(sync_result['added'])}")
        print(f"Files updated: {len(sync_result['updated'])}")
        
        # List local files after sync
        print("\nFiles in local directory after sync:")
        for root, _, files in os.walk(local_dir):
            rel_path = os.path.relpath(root, local_dir)
            prefix = "" if rel_path == "." else f"{rel_path}/"
            for file in files:
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                print(f"- {prefix}{file} ({size} bytes)")
                
        # Demonstrate incremental sync
        print("\nTesting incremental sync:")
        # Modify an existing file locally
        with open(os.path.join(local_dir, "local_file1.txt"), "w") as f:
            f.write("Modified content for local file 1")
            
        # Sync changes to MFS
        sync_result = await sync.sync_local_to_mfs()
        print(f"Files added: {len(sync_result['added'])}")
        print(f"Files updated: {len(sync_result['updated'])}")
        
        # Verify the file was updated in MFS
        file_content = await ipfs.files_read(f"{mfs_dir}/local_file1.txt")
        print(f"Updated file content in MFS: {file_content.decode()}")

async def example_content_type_detector():
    """Demonstrate using ContentTypeDetector for MIME type detection."""
    print("\n--- ContentTypeDetector Example ---")
    
    # Initialize IPFS client and content type detector
    ipfs = IPFSKit()
    detector = ContentTypeDetector()
    
    # Create a test directory
    test_dir = "/mfs_content_type_examples"
    await ipfs.files_mkdir(test_dir, parents=True)
    
    # Example files with different content types
    test_files = {
        "text_file.txt": "This is a plain text file.".encode(),
        "html_file.html": "<html><body><h1>Hello, World!</h1></body></html>".encode(),
        "json_file.json": '{"key": "value", "numbers": [1, 2, 3]}'.encode(),
        "binary_file.bin": bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),  # PNG header
        "no_extension": "Content with no file extension".encode()
    }
    
    # Create the files and detect content types
    for filename, content in test_files.items():
        file_path = f"{test_dir}/{filename}"
        
        # Create the file in MFS
        await ipfs.files_write(file_path, content, create=True)
        
        # Detect content type
        content_type = await detector.detect_type(ipfs, file_path)
        print(f"Detected content type for {filename}: {content_type}")
    
    # Use create_file_with_type utility
    custom_type = "application/custom+json"
    custom_file = f"{test_dir}/custom_type.data"
    await create_file_with_type(
        ipfs, 
        custom_file, 
        '{"custom": "data"}'.encode(), 
        content_type=custom_type, 
        detect_type=False
    )
    
    # Verify the custom content type
    custom_type_result = await detector.detect_type(ipfs, custom_file)
    print(f"Custom content type for custom_type.data: {custom_type_result}")

async def example_path_utils():
    """Demonstrate using PathUtils for MFS path manipulation."""
    print("\n--- PathUtils Example ---")
    
    # Examples of path joining
    path1 = PathUtils.join_paths("/base", "subdir", "file.txt")
    print(f"Joined path: {path1}")
    
    path2 = PathUtils.join_paths("/", "deeply", "nested", "path")
    print(f"Joined path with root: {path2}")
    
    # Getting parent directory
    parent = PathUtils.get_parent_dir("/path/to/file.txt")
    print(f"Parent directory: {parent}")
    
    # Getting basename
    basename = PathUtils.get_basename("/path/to/file.txt")
    print(f"Basename: {basename}")
    
    # Path splitting
    dir_path, file_name = PathUtils.split_path("/path/to/file.txt")
    print(f"Split path: directory={dir_path}, filename={file_name}")
    
    # Checking if path is a subpath
    is_subpath = PathUtils.is_subpath("/parent/path", "/parent/path/subdir/file.txt")
    print(f"Is subpath: {is_subpath}")
    
    not_subpath = PathUtils.is_subpath("/other/path", "/parent/path/file.txt")
    print(f"Is not subpath: {not_subpath}")
    
    # Normalize path
    normalized = PathUtils.normalize_path("/path//to/..//to/./file.txt")
    print(f"Normalized path: {normalized}")

async def example_mfs_change_watcher():
    """Demonstrate using MFSChangeWatcher for monitoring MFS changes."""
    print("\n--- MFSChangeWatcher Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create a test directory
    test_dir = "/mfs_watch_example"
    await ipfs.files_mkdir(test_dir, parents=True)
    
    # Initialize the change watcher
    changes = []
    def change_callback(event_type, path, details=None):
        changes.append({"type": event_type, "path": path, "details": details})
        print(f"Change detected: {event_type} - {path}")
    
    watcher = MFSChangeWatcher(ipfs, test_dir, callback=change_callback)
    
    # Start watching (in the background)
    await watcher.start(poll_interval=1)
    
    # Make some changes to MFS
    print("\nMaking changes to MFS directory...")
    await ipfs.files_write(f"{test_dir}/file1.txt", "Initial content".encode(), create=True)
    await anyio.sleep(1.5)  # Wait for polling to detect changes
    
    await ipfs.files_write(f"{test_dir}/file1.txt", "Modified content".encode(), create=True)
    await anyio.sleep(1.5)
    
    await ipfs.files_mkdir(f"{test_dir}/subdir")
    await anyio.sleep(1.5)
    
    await ipfs.files_rm(f"{test_dir}/file1.txt")
    await anyio.sleep(1.5)
    
    # Stop the watcher
    await watcher.stop()
    
    # Print summary of changes
    print("\nSummary of detected changes:")
    for i, change in enumerate(changes, 1):
        print(f"{i}. {change['type']} - {change['path']}")

async def example_batch_operations():
    """Demonstrate using batch operations for MFS."""
    print("\n--- Batch Operations Example ---")
    
    # Initialize IPFS client
    ipfs = IPFSKit()
    
    # Create test directories
    source_dir = "/mfs_batch_source"
    target_dir = "/mfs_batch_target"
    
    await ipfs.files_mkdir(source_dir, parents=True)
    await ipfs.files_mkdir(target_dir, parents=True)
    
    # Create some test files in the source directory
    for i in range(5):
        file_path = f"{source_dir}/file{i}.txt"
        await ipfs.files_write(file_path, f"Content for file {i}".encode(), create=True)
    
    # List files in source directory
    ls_result = await ipfs.files_ls(source_dir)
    print(f"Files in source directory: {[entry['Name'] for entry in ls_result.get('Entries', [])]}")
    
    # Define batch copy operations
    copy_operations = [
        {"source": f"{source_dir}/file{i}.txt", "destination": f"{target_dir}/copy_of_file{i}.txt"}
        for i in range(5)
    ]
    
    # Execute batch copy
    print("\nExecuting batch copy operations...")
    copy_results = await copy_content_batch(ipfs, copy_operations)
    print(f"Batch copy results: {len(copy_results)} operations completed")
    
    # List files in target directory after copy
    ls_result = await ipfs.files_ls(target_dir)
    print(f"Files in target directory after copy: {[entry['Name'] for entry in ls_result.get('Entries', [])]}")
    
    # Define batch move operations
    move_operations = [
        {"source": f"{target_dir}/copy_of_file{i}.txt", "destination": f"{target_dir}/moved_file{i}.txt"}
        for i in range(5)
    ]
    
    # Execute batch move
    print("\nExecuting batch move operations...")
    move_results = await move_content_batch(ipfs, move_operations)
    print(f"Batch move results: {len(move_results)} operations completed")
    
    # List files in target directory after move
    ls_result = await ipfs.files_ls(target_dir)
    print(f"Files in target directory after move: {[entry['Name'] for entry in ls_result.get('Entries', [])]}")

async def main():
    """Run all examples."""
    print("=== Enhanced MFS Functionality Examples ===\n")
    
    # Run all examples
    try:
        await example_mfs_transaction()
        await example_directory_synchronizer()
        await example_content_type_detector()
        await example_path_utils()
        await example_mfs_change_watcher()
        await example_batch_operations()
    except Exception as e:
        print(f"Error in examples: {str(e)}")
    
    print("\n=== Examples Completed ===")

if __name__ == "__main__":
    anyio.run(main())