#!/usr/bin/env python3
"""
VFS Performance Testing

Compare query performance between individual bucket files and combined files.
"""

import time
from pathlib import Path
import sys

# Add project root to path
sys.path.append('/home/devel/ipfs_kit_py')

from ipfs_kit_py.parquet_data_reader import ParquetDataReader
from create_individual_bucket_parquet import BucketVFSManager


def test_query_performance():
    """Test query performance for different access patterns."""
    print("🚀 VFS Performance Testing")
    print("=" * 60)
    
    # Initialize reader and VFS manager
    reader = ParquetDataReader()
    vfs_manager = BucketVFSManager()
    
    # Test queries
    test_queries = [
        ("Bucket files query", lambda: reader.query_files_by_bucket("media-bucket")),
        ("CID lookup", lambda: reader.query_cid_location("QmE8U6WzNXR9Zz8qM4c8N5k2z8v3u1L4t6h9q3w2e5r5e")),
        ("All buckets snapshot", lambda: vfs_manager.get_all_bucket_snapshots()),
        ("Single bucket CAR prep", lambda: vfs_manager.prepare_for_car_generation("documents-bucket")),
    ]
    
    # Run performance tests
    results = []
    
    for test_name, test_func in test_queries:
        print(f"\n🔍 Testing: {test_name}")
        
        # Warm up
        try:
            test_func()
        except Exception as e:
            print(f"   ⚠️  Warmup failed: {e}")
            continue
        
        # Time multiple runs
        times = []
        for i in range(5):
            start_time = time.perf_counter()
            try:
                result = test_func()
                end_time = time.perf_counter()
                query_time = (end_time - start_time) * 1000  # ms
                times.append(query_time)
            except Exception as e:
                print(f"   ❌ Run {i+1} failed: {e}")
                continue
        
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"   ⏱️  Average: {avg_time:.2f}ms")
            print(f"   📊 Range: {min_time:.2f}ms - {max_time:.2f}ms")
            
            results.append({
                'test': test_name,
                'avg_time': avg_time,
                'min_time': min_time,
                'max_time': max_time
            })
    
    # Print summary
    print("\n" + "=" * 60)
    print("📈 Performance Summary:")
    
    for result in results:
        print(f"   {result['test']:<25} {result['avg_time']:>8.2f}ms")
    
    # Test data integrity
    print(f"\n🔍 Data Integrity Check:")
    
    try:
        # Check individual bucket files exist
        vfs_root = Path.home() / ".ipfs_kit" / "vfs" / "buckets"
        bucket_files = list(vfs_root.glob("*_vfs.parquet"))
        print(f"   Individual bucket files: {len(bucket_files)}")
        
        # Check manifest
        manifest_path = Path.home() / ".ipfs_kit" / "vfs" / "bucket_manifest.json"
        if manifest_path.exists():
            print(f"   ✅ Manifest exists: {manifest_path}")
        else:
            print(f"   ❌ Manifest missing: {manifest_path}")
        
        # Check snapshots
        snapshots_dir = Path.home() / ".ipfs_kit" / "vfs" / "snapshots"
        snapshot_files = list(snapshots_dir.glob("snapshot_*.json"))
        print(f"   Snapshot files: {len(snapshot_files)}")
        
        # Test file counts
        all_snapshots = vfs_manager.get_all_bucket_snapshots()
        if all_snapshots['success']:
            total_files = all_snapshots['total_files']
            bucket_count = len(all_snapshots['buckets'])
            print(f"   Total files in system: {total_files}")
            print(f"   Bucket count: {bucket_count}")
            print(f"   Global hash: {all_snapshots['global_hash'][:16]}...")
        
    except Exception as e:
        print(f"   ❌ Integrity check failed: {e}")
    
    print(f"\n✅ Performance testing complete!")
    return results


if __name__ == "__main__":
    test_query_performance()
