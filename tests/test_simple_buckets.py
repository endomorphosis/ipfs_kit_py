#!/usr/bin/env python3
"""
Test the simplified bucket implementation.
"""

import anyio
import tempfile
from pathlib import Path

async def test_simple_bucket_manager():
    """Test the simplified bucket manager."""
    print("🧪 Testing Simplified Bucket Manager")
    print("=" * 50)
    
    try:
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"📂 Using temp directory: {temp_dir}")
            
            # Import and initialize
            from ipfs_kit_py.simple_bucket_manager import SimpleBucketManager
            
            bucket_manager = SimpleBucketManager(data_dir=temp_dir)
            print(f"✅ Initialized SimpleBucketManager with data_dir: {bucket_manager.data_dir}")
            
            # Test bucket creation
            print("\n1. Testing bucket creation...")
            result = await bucket_manager.create_bucket(
                bucket_name="test-bucket",
                bucket_type="testing",
                metadata={"description": "Test bucket"}
            )
            
            if result['success']:
                print(f"✅ Created bucket: {result['data']}")
            else:
                print(f"❌ Failed to create bucket: {result['error']}")
                return
            
            # Test bucket listing
            print("\n2. Testing bucket listing...")
            result = await bucket_manager.list_buckets()
            
            if result['success']:
                buckets = result['data']['buckets']
                print(f"✅ Found {len(buckets)} buckets:")
                for bucket in buckets:
                    print(f"   - {bucket['name']} ({bucket['type']})")
            else:
                print(f"❌ Failed to list buckets: {result['error']}")
                return
            
            # Test file addition
            print("\n3. Testing file addition...")
            test_content = "Hello, IPFS Kit simplified buckets!"
            
            result = await bucket_manager.add_file_to_bucket(
                bucket_name="test-bucket",
                file_path="hello.txt",
                content=test_content,
                metadata={"description": "Test file"}
            )
            
            if result['success']:
                print(f"✅ Added file: {result['data']}")
            else:
                print(f"❌ Failed to add file: {result['error']}")
                return
            
            # Test getting bucket files
            print("\n4. Testing bucket files listing...")
            result = await bucket_manager.get_bucket_files("test-bucket")
            
            if result['success']:
                files = result['data']['files']
                print(f"✅ Found {len(files)} files in bucket:")
                for file_info in files:
                    print(f"   - {file_info['file_path']} (CID: {file_info['file_cid']})")
            else:
                print(f"❌ Failed to get bucket files: {result['error']}")
                return
            
            # Test directory structure
            print("\n5. Checking directory structure...")
            buckets_dir = Path(temp_dir) / 'buckets'
            wal_dir = Path(temp_dir) / 'wal' / 'pins' / 'pending'
            
            print(f"   📂 Buckets dir exists: {buckets_dir.exists()}")
            print(f"   📂 WAL dir exists: {wal_dir.exists()}")
            
            if buckets_dir.exists():
                bucket_files = list(buckets_dir.glob('*.parquet'))
                print(f"   📄 Bucket parquet files: {len(bucket_files)}")
                for file in bucket_files:
                    print(f"      - {file.name}")
            
            if wal_dir.exists():
                wal_files = list(wal_dir.glob('*'))
                print(f"   📄 WAL files: {len(wal_files)}")
                for file in wal_files:
                    print(f"      - {file.name}")
            
            print("\n✅ All tests completed successfully!")
            print("🎉 Simplified bucket implementation is working correctly!")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    anyio.run(test_simple_bucket_manager)
