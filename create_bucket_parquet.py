#!/usr/bin/env python3
"""
Convert bucket JSON data to Parquet format for optimized querying.
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime

def create_bucket_parquet_files():
    """Convert bucket data to Parquet format."""
    
    # Paths
    workspace_dir = Path("/home/devel/ipfs_kit_py")
    ipfs_kit_dir = Path.home() / ".ipfs_kit"
    bucket_parquet_dir = ipfs_kit_dir / "bucket_index" / "parquet"
    vfs_parquet_dir = ipfs_kit_dir / "vfs" / "parquet"
    
    # Create directories
    bucket_parquet_dir.mkdir(parents=True, exist_ok=True)
    vfs_parquet_dir.mkdir(parents=True, exist_ok=True)
    
    # Read bucket metadata
    with open(workspace_dir / "test_buckets.json", 'r') as f:
        buckets_data = json.load(f)
    
    # Read bucket files
    with open(workspace_dir / "bucket_files.json", 'r') as f:
        files_data = json.load(f)
    
    # Create bucket metadata DataFrame
    bucket_records = []
    for bucket in buckets_data:
        bucket_records.append({
            'bucket_id': bucket['bucket_id'],
            'name': bucket['name'],
            'backend': bucket['backend'],
            'size_bytes': bucket['size_bytes'],
            'file_count': bucket['file_count'],
            'created_at': bucket['created_at'],
            'last_updated': bucket['last_updated'],
            'description': bucket['description'],
            'tags': json.dumps(bucket['tags']),  # Store as JSON string
            'storage_class': bucket['storage_class'],
            'encryption': bucket['encryption'],
            'region': bucket.get('region', ''),
            'replication_factor': bucket.get('replication_factor', 1),
            'sync_enabled': bucket.get('sync_enabled', False),
            'auto_cleanup': bucket.get('auto_cleanup', False)
        })
    
    buckets_df = pd.DataFrame(bucket_records)
    buckets_parquet_path = bucket_parquet_dir / "buckets.parquet"
    buckets_df.to_parquet(buckets_parquet_path, index=False)
    print(f"✅ Created bucket metadata: {buckets_parquet_path}")
    
    # Create VFS files DataFrame
    vfs_records = []
    for bucket_name, files in files_data.items():
        # Find bucket_id from metadata
        bucket_id = None
        for bucket in buckets_data:
            if bucket['name'] == bucket_name:
                bucket_id = bucket['bucket_id']
                break
        
        if not bucket_id:
            bucket_id = f"{bucket_name}-unknown"
            
        for file_info in files:
            vfs_records.append({
                'file_id': f"{bucket_id}_{file_info['name']}",
                'bucket_id': bucket_id,
                'bucket_name': bucket_name,
                'name': file_info['name'],
                'cid': file_info['cid'],
                'size_bytes': file_info['size_bytes'],
                'mime_type': file_info['mime_type'],
                'uploaded_at': file_info['uploaded_at'],
                'tags': json.dumps(file_info['tags']),  # Store as JSON string
                'path': file_info['path'],
                'vfs_path': file_info['path'],  # Virtual filesystem path
                'mount_point': f"/{bucket_name}",  # Bucket as mount point
                'access_count': 0,  # Initialize
                'last_accessed': file_info['uploaded_at'],
                'content_hash': file_info['cid'],  # Use CID as content hash
                'integrity_status': 'verified',
                'storage_tier': 'primary',
                'compression': None,
                'encryption_status': 'unknown'
            })
    
    vfs_df = pd.DataFrame(vfs_records)
    vfs_parquet_path = vfs_parquet_dir / "bucket_files.parquet"
    vfs_df.to_parquet(vfs_parquet_path, index=False)
    print(f"✅ Created VFS file index: {vfs_parquet_path}")
    
    # Create bucket analytics as Parquet
    analytics_records = []
    
    # Overall analytics
    total_buckets = len(buckets_data)
    total_size = sum(bucket['size_bytes'] for bucket in buckets_data)
    total_files = sum(len(files) for files in files_data.values())
    
    # Backend breakdown
    backend_stats = {}
    for bucket in buckets_data:
        backend = bucket['backend']
        if backend not in backend_stats:
            backend_stats[backend] = {'buckets': 0, 'size_bytes': 0, 'files': 0}
        backend_stats[backend]['buckets'] += 1
        backend_stats[backend]['size_bytes'] += bucket['size_bytes']
        backend_stats[backend]['files'] += bucket['file_count']
    
    # Create analytics records
    for backend, stats in backend_stats.items():
        analytics_records.append({
            'metric_type': 'backend_summary',
            'metric_name': backend,
            'bucket_count': stats['buckets'],
            'total_size_bytes': stats['size_bytes'],
            'file_count': stats['files'],
            'timestamp': datetime.now().isoformat(),
            'metadata': json.dumps({
                'backend_type': backend,
                'avg_bucket_size': stats['size_bytes'] / stats['buckets'] if stats['buckets'] > 0 else 0,
                'avg_files_per_bucket': stats['files'] / stats['buckets'] if stats['buckets'] > 0 else 0
            })
        })
    
    # Overall summary
    analytics_records.append({
        'metric_type': 'global_summary',
        'metric_name': 'total',
        'bucket_count': total_buckets,
        'total_size_bytes': total_size,
        'file_count': total_files,
        'timestamp': datetime.now().isoformat(),
        'metadata': json.dumps({
            'avg_bucket_size': total_size / total_buckets if total_buckets > 0 else 0,
            'avg_file_size': total_size / total_files if total_files > 0 else 0,
            'backends': list(backend_stats.keys())
        })
    })
    
    analytics_df = pd.DataFrame(analytics_records)
    analytics_parquet_path = bucket_parquet_dir / "bucket_analytics.parquet"
    analytics_df.to_parquet(analytics_parquet_path, index=False)
    print(f"✅ Created bucket analytics: {analytics_parquet_path}")
    
    # Create file-to-CID mapping
    cid_mapping_records = []
    for bucket_name, files in files_data.items():
        for file_info in files:
            cid_mapping_records.append({
                'cid': file_info['cid'],
                'bucket_name': bucket_name,
                'file_name': file_info['name'],
                'file_path': file_info['path'],
                'vfs_path': file_info['path'],
                'size_bytes': file_info['size_bytes'],
                'mime_type': file_info['mime_type'],
                'uploaded_at': file_info['uploaded_at'],
                'tags': json.dumps(file_info['tags']),
                'content_hash': file_info['cid'],
                'pinned': True,  # Assume all bucket files are pinned
                'pin_type': 'recursive',
                'replication_factor': 1,
                'storage_tier': 'primary'
            })
    
    cid_df = pd.DataFrame(cid_mapping_records)
    cid_parquet_path = vfs_parquet_dir / "cid_to_bucket_mapping.parquet"
    cid_df.to_parquet(cid_parquet_path, index=False)
    print(f"✅ Created CID mapping: {cid_parquet_path}")
    
    print(f"\n📊 Summary:")
    print(f"   Buckets: {total_buckets}")
    print(f"   Files: {total_files}")
    print(f"   Total Size: {total_size / (1024*1024*1024):.2f} GB")
    print(f"   Backends: {', '.join(backend_stats.keys())}")
    print(f"   Parquet files created in: {bucket_parquet_dir} and {vfs_parquet_dir}")

if __name__ == "__main__":
    create_bucket_parquet_files()
