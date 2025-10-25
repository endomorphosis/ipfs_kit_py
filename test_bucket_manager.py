#!/usr/bin/env python3

# Test script to debug SimpleBucketManager
import asyncio
import sys
import os
sys.path.insert(0, '/home/devel/ipfs_kit_py')

from ipfs_kit_py.simple_bucket_manager import SimpleBucketManager

async def test_bucket_manager():
    print("Testing SimpleBucketManager...")
    
    # Initialize bucket manager
    bucket_manager = SimpleBucketManager()
    print(f"Initialized with data_dir: {bucket_manager.data_dir}")
    
    # Test bucket creation
    bucket_name = "test"
    print(f"Creating bucket: {bucket_name}")
    create_result = await bucket_manager.create_bucket(bucket_name)
    print(f"Create result: {create_result}")
    
    # Test file upload
    test_content = "Hello, World! This is a test file."
    file_path = "test.txt"
    print(f"Uploading file: {file_path}")
    
    try:
        upload_result = await bucket_manager.add_file_to_bucket(
            bucket_name=bucket_name,
            file_path=file_path,
            content=test_content.encode("utf-8"),
            metadata={
                "upload_mode": "text",
                "test": True
            }
        )
        print(f"Upload result: {upload_result}")
    except Exception as e:
        print(f"Upload error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test file listing
    print(f"Listing files in bucket: {bucket_name}")
    try:
        list_result = await bucket_manager.get_bucket_files(bucket_name)
        print(f"List result: {list_result}")
    except Exception as e:
        print(f"List error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_bucket_manager())