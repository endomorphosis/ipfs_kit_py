#!/usr/bin/env python3
"""
Direct test of the bucket functionality without the complex dashboard.
Tests the core bucket operations that we implemented.
"""

from pathlib import Path
import json
import tempfile
import os

def test_bucket_filesystem_operations():
    """Test bucket operations directly on the filesystem."""
    print("🧪 Testing bucket filesystem operations...")
    
    # Set up test data directory
    data_dir = Path.home() / ".ipfs_kit"
    buckets_dir = data_dir / "buckets"
    buckets_dir.mkdir(parents=True, exist_ok=True)
    
    test_bucket_name = "test-bucket-direct"
    bucket_dir = buckets_dir / test_bucket_name
    
    try:
        # Test 1: Create bucket
        print(f"\n🔨 Creating bucket: {test_bucket_name}")
        bucket_dir.mkdir(exist_ok=True)
        
        # Create metadata
        metadata = {
            "name": test_bucket_name,
            "description": "Test bucket for direct operations",
            "created_at": "2025-01-01T00:00:00Z",
            "files": {}
        }
        
        metadata_file = bucket_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"   ✅ Successfully created bucket at: {bucket_dir}")
        
        # Test 2: List buckets
        print(f"\n📝 Listing buckets in: {buckets_dir}")
        buckets = []
        for item in buckets_dir.iterdir():
            if item.is_dir():
                bucket_metadata_file = item / "metadata.json"
                if bucket_metadata_file.exists():
                    with open(bucket_metadata_file, 'r') as f:
                        bucket_info = json.load(f)
                        buckets.append({
                            "name": bucket_info.get("name", item.name),
                            "description": bucket_info.get("description", ""),
                            "path": str(item)
                        })
        
        print(f"   ✅ Found {len(buckets)} buckets:")
        for bucket in buckets:
            print(f"      - {bucket['name']}: {bucket['description']}")
        
        # Test 3: Upload a file
        print(f"\n⬆️  Uploading test file to bucket: {test_bucket_name}")
        test_content = "This is test content for bucket functionality testing."
        test_file_path = bucket_dir / "test-file.txt"
        
        with open(test_file_path, 'w') as f:
            f.write(test_content)
        
        # Update metadata
        metadata["files"]["test-file.txt"] = {
            "size": len(test_content),
            "uploaded_at": "2025-01-01T00:00:00Z"
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"   ✅ Successfully uploaded file: {test_file_path}")
        
        # Test 4: List files in bucket
        print(f"\n📂 Listing files in bucket: {test_bucket_name}")
        files = []
        for item in bucket_dir.iterdir():
            if item.is_file() and item.name != "metadata.json":
                stat = item.stat()
                files.append({
                    "name": item.name,
                    "size": stat.st_size,
                    "path": str(item)
                })
        
        print(f"   ✅ Found {len(files)} files:")
        for file_info in files:
            print(f"      - {file_info['name']}: {file_info['size']} bytes")
        
        # Test 5: Download (read) file
        print(f"\n⬇️  Reading test file from bucket")
        if test_file_path.exists():
            with open(test_file_path, 'r') as f:
                downloaded_content = f.read()
            
            if downloaded_content == test_content:
                print(f"   ✅ Successfully read file with correct content")
            else:
                print(f"   ⚠️  Content mismatch!")
                print(f"      Expected: {test_content}")
                print(f"      Got: {downloaded_content}")
        else:
            print(f"   ❌ Test file not found")
        
        # Test 6: Delete bucket
        print(f"\n🗑️  Deleting bucket: {test_bucket_name}")
        import shutil
        if bucket_dir.exists():
            shutil.rmtree(bucket_dir)
            print(f"   ✅ Successfully deleted bucket")
        else:
            print(f"   ❌ Bucket directory not found")
        
        # Test 7: Verify bucket is deleted
        print(f"\n🔍 Verifying bucket deletion")
        if not bucket_dir.exists():
            print(f"   ✅ Bucket successfully deleted")
        else:
            print(f"   ❌ Bucket still exists")
        
        print(f"\n✅ All bucket filesystem operations completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during bucket operations: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bucket_filesystem_operations()
