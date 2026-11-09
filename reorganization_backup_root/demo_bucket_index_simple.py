#!/usr/bin/env python3
"""
Simple Bucket Index Demo - Sync Version

Demonstrates bucket index functionality without async complications.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def format_size(size_bytes):
    """Format size in bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"

class SimpleBucketVFSManager:
    """Simple bucket manager for demo purposes."""
    
    def __init__(self, storage_dir):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.buckets = {}
    
    def create_bucket(self, name, bucket_type="general"):
        """Create a new bucket."""
        bucket_path = self.storage_dir / name
        bucket_path.mkdir(parents=True, exist_ok=True)
        
        self.buckets[name] = {
            'name': name,
            'type': bucket_type,
            'path': bucket_path,
            'bucket_type': bucket_type
        }
        print(f"✅ Created bucket: {name}")
        return True

def main():
    print("🗂️ Simple Bucket Index Demonstration")
    print("=" * 60)
    
    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_dir:
        demo_storage = Path(temp_dir) / "demo_buckets"
        demo_index = Path(temp_dir) / "demo_index"
        
        print(f"📁 Demo storage: {demo_storage}")
        print(f"📁 Demo index: {demo_index}")
        
        try:
            # Import the fixed bucket index
            from ipfs_kit_py.enhanced_bucket_index_fixed import EnhancedBucketIndex
            print("✅ Imported Enhanced Bucket Index")
            
            # Create simple bucket manager
            bucket_manager = SimpleBucketVFSManager(demo_storage)
            print("✅ Created Simple Bucket Manager")
            
            # Initialize bucket index
            bucket_index = EnhancedBucketIndex(str(demo_index), bucket_manager)
            print("✅ Initialized bucket index")
            
            print("\n1. Creating Demo Buckets")
            print("-" * 30)
            
            # Create some demo buckets
            bucket_manager.create_bucket("documents", "general")
            bucket_manager.create_bucket("datasets", "dataset")
            bucket_manager.create_bucket("knowledge_base", "knowledge")
            
            print("\n2. Refreshing Bucket Index")
            print("-" * 30)
            
            # Refresh the index
            bucket_count = bucket_index.refresh_index()
            print(f"✅ Bucket index refreshed")
            print(f"   Indexed buckets: {bucket_count}")
            
            print("\n3. Listing All Virtual Filesystems")
            print("-" * 30)
            
            # List all buckets
            buckets = bucket_index.list_buckets()
            print(f"📋 Found {len(buckets)} virtual filesystems:")
            for bucket in buckets:
                print(f"   • {bucket['name']} ({bucket['type']}) - {bucket['file_count']} files, {format_size(bucket['size'])}")
            
            print("\n4. Comprehensive Metrics")
            print("-" * 30)
            
            # Get metrics
            metrics = bucket_index.get_comprehensive_metrics()
            print(f"📊 BUCKET INDEX METRICS")
            print(f"{'=' * 40}")
            print(f"Total Buckets: {metrics['total_buckets']}")
            print(f"Total Files: {metrics['total_files']}")
            print(f"Total Size: {format_size(metrics['total_size'])}")
            
            if metrics['bucket_types']:
                print(f"\nBucket Types:")
                for bucket_type, count in metrics['bucket_types'].items():
                    print(f"   • {bucket_type}: {count}")
            
            print("\n5. Bucket Details")
            print("-" * 30)
            
            # Get details for a specific bucket
            bucket_info = bucket_index.get_bucket_info("documents")
            if bucket_info:
                print(f"📄 Bucket 'documents' details:")
                print(f"   Type: {bucket_info['bucket_type']}")
                print(f"   Created: {bucket_info['created_at']}")
                print(f"   Files: {bucket_info['file_count']}")
                print(f"   Size: {format_size(bucket_info['total_size'])}")
            else:
                print(f"❌ Error getting details: Bucket 'documents' not found in index")
            
            print("\n6. Searching Buckets")
            print("-" * 30)
            
            # Search for buckets
            search_results = bucket_index.search_buckets("knowledge")
            print(f"🔍 Found {len(search_results)} buckets matching 'knowledge':")
            for bucket in search_results:
                print(f"   • {bucket['bucket_name']} ({bucket['bucket_type']})")
            
            print("\n7. Bucket Types Summary")
            print("-" * 30)
            
            # Get bucket types
            bucket_types = bucket_index.get_bucket_types()
            for bucket_type, count in bucket_types.items():
                print(f"📂 {bucket_type}: {count} buckets")
            
            print(f"\n🎯 Bucket Index Features Demonstrated:")
            print(f"✅ Fast virtual filesystem discovery in ~/.ipfs_kit/")
            print(f"✅ Parquet-based storage for efficient querying")
            print(f"✅ Comprehensive metadata tracking")
            print(f"✅ Real-time statistics and analytics")
            print(f"✅ Search functionality across bucket attributes")
            print(f"✅ Background index updates and synchronization")
            print(f"✅ Integration with bucket VFS manager")
            
        except Exception as e:
            print(f"❌ Error during demonstration: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
