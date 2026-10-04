#!/usr/bin/env python3
"""
Manual filesystem bucket creation for testing
"""

import json
import os
from pathlib import Path
from datetime import datetime

def create_filesystem_bucket(bucket_name, bucket_type="general", description=""):
    """Create a simple filesystem bucket."""
    
    # Use the IPFS Kit data directory
    data_dir = Path.home() / ".ipfs_kit"
    buckets_dir = data_dir / "buckets"
    bucket_dir = buckets_dir / bucket_name
    
    # Create directories
    bucket_dir.mkdir(parents=True, exist_ok=True)
    
    # Create metadata
    metadata = {
        "name": bucket_name,
        "type": bucket_type,
        "vfs_structure": "hybrid",
        "created_at": datetime.now().isoformat(),
        "metadata": {
            "description": description,
            "created_by": "manual_script"
        }
    }
    
    # Save metadata
    metadata_file = bucket_dir / "metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Created bucket '{bucket_name}' at {bucket_dir}")
    print(f"📝 Metadata: {json.dumps(metadata, indent=2)}")
    
    return bucket_dir

def list_filesystem_buckets():
    """List existing filesystem buckets."""
    
    data_dir = Path.home() / ".ipfs_kit"
    buckets_dir = data_dir / "buckets"
    
    if not buckets_dir.exists():
        print("No buckets directory found")
        return []
    
    buckets = []
    
    for bucket_dir in buckets_dir.iterdir():
        if bucket_dir.is_dir():
            metadata_file = bucket_dir / "metadata.json"
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        bucket_info = json.load(f)
                except:
                    bucket_info = {"name": bucket_dir.name, "type": "unknown"}
            else:
                bucket_info = {"name": bucket_dir.name, "type": "unknown"}
            
            # Add file count
            file_count = len([f for f in bucket_dir.rglob("*") if f.is_file() and f.name != "metadata.json"])
            bucket_info["file_count"] = file_count
            
            buckets.append(bucket_info)
    
    return buckets

if __name__ == "__main__":
    print("🪣 Current buckets:")
    buckets = list_filesystem_buckets()
    if buckets:
        for bucket in buckets:
            print(f"  - {bucket['name']} (type: {bucket.get('type', 'unknown')}, files: {bucket.get('file_count', 0)})")
    else:
        print("  No buckets found")
    
    print("\n🔨 Creating new bucket...")
    create_filesystem_bucket(
        "manual-test-bucket", 
        "general", 
        "Test bucket created manually via filesystem operations"
    )
    
    print("\n🪣 Updated buckets:")
    buckets = list_filesystem_buckets()
    for bucket in buckets:
        print(f"  - {bucket['name']} (type: {bucket.get('type', 'unknown')}, files: {bucket.get('file_count', 0)})")
