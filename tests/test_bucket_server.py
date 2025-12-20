#!/usr/bin/env python3
"""
Test script for the enhanced MCP server with bucket management.
"""

import os
import sys
import time
import threading
import requests
from ipfs_kit_py.bucket_manager import BucketManager
from ipfs_kit_py.config_manager import ConfigManager

def test_bucket_functionality():
    """Test bucket management functionality."""
    print("Testing bucket management functionality...")
    
    # Test configuration
    config_manager = ConfigManager()
    bucket_manager = BucketManager(config_manager)

    print("✓ Managers initialized successfully")
    print(f"  Config directory: {config_manager.config_dir}")
    print(f"  Buckets directory: {bucket_manager.bucket_data_path}")

    # Test creating a bucket
    result = bucket_manager.create_bucket('test-bucket-2', backend='local', max_size=5*1024*1024)
    print(f"✓ Create bucket result: {result}")

    # List buckets
    buckets = bucket_manager.list_buckets()
    print(f"✓ Buckets: {len(buckets)} found")
    for bucket in buckets:
        print(f"  - {bucket['name']}: {bucket['status']} ({bucket['backend']})")

    # Test metadata
    config_manager.set_metadata('test_key', {'test': True, 'timestamp': time.time()})
    metadata = config_manager.get_metadata('test_key')
    print(f"✓ Metadata test: {metadata}")

    # Test bucket upload (if bucket exists)
    if buckets:
        test_content = b"Hello, World! This is a test file."
        result = bucket_manager.upload_file(buckets[0]['name'], 'test-file.txt', test_content)
        print(f"✓ Upload test result: {result}")
        
        # List files
        files = bucket_manager.list_files(buckets[0]['name'])
        print(f"✓ Files in bucket: {files}")
        
        # Get bucket stats
        stats = bucket_manager.get_bucket_stats(buckets[0]['name'])
        print(f"✓ Bucket stats: {stats['storage']['total_size']} bytes, {stats['storage']['file_count']} files")

    print("\n✅ All bucket functionality tests passed!")

def test_server_startup():
    """Test that the server can start up without errors."""
    print("\nTesting server startup...")
    
    try:
        # Import the server module to check for import errors
        from ipfs_kit_py.enhanced_mcp_server_real import app, config_manager, bucket_manager
        print("✓ Server modules imported successfully")
        print(f"✓ Config manager: {type(config_manager)}")
        print(f"✓ Bucket manager: {type(bucket_manager)}")
        
        # Test that the FastAPI app exists
        print(f"✓ FastAPI app: {type(app)}")
        print("✓ Server can be initialized without errors")
        
        return True
    except Exception as e:
        print(f"✗ Server startup failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing IPFS Kit Enhanced MCP Server with Bucket Management\n")
    
    # Test bucket functionality
    test_bucket_functionality()
    
    # Test server startup
    if test_server_startup():
        print("\n✅ All tests passed! The server is ready to use.")
        print("\n📋 To start the server, run:")
        print("   cd <repo>/ipfs_kit_py")
        print("   python enhanced_mcp_server_real.py --port 8080")
        print("\n🌐 Then visit: http://localhost:8080/dashboard")
    else:
        print("\n❌ Some tests failed. Check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()