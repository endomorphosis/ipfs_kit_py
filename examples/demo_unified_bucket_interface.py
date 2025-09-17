#!/usr/bin/env python3
"""
Unified Bucket-Based Interface Demo

Demonstrates the unified bucket-based interface for multiple filesystem backends
with content-addressed pins, VFS composition, and metadata indices.

This demo shows:
1. Creating buckets for different backends (Parquet, Arrow, SSHFS, FTP, S3, etc.)
2. Adding content-addressed pins to buckets
3. VFS composition across backends
4. Cross-backend querying
5. Directory structure organization in ~/.ipfs_kit/
"""

import asyncio
import json
import tempfile
import os
from pathlib import Path

from ipfs_kit_py.unified_bucket_interface import (
    UnifiedBucketInterface,
    BackendType,
    BucketType,
    VFSStructureType
)


async def demo_unified_bucket_interface():
    """Comprehensive demo of the unified bucket interface."""
    
    print("🚀 Unified Bucket-Based Interface Demo")
    print("=" * 60)
    print()
    
    # Initialize interface
    print("1. Initializing Unified Bucket Interface...")
    interface = UnifiedBucketInterface()
    
    result = await interface.initialize()
    if not result["success"]:
        print(f"❌ Failed to initialize: {result.get('error')}")
        return False
    
    print("✅ Interface initialized successfully")
    print(f"   Base directory: {interface.ipfs_kit_dir}")
    print()
    
    try:
        # Demo 1: Create buckets for different backends
        print("2. Creating Buckets for Different Backends...")
        print("-" * 50)
        
        backend_configs = [
            {
                "backend": BackendType.PARQUET,
                "bucket_name": "ml_datasets",
                "bucket_type": BucketType.DATASET,
                "vfs_structure": VFSStructureType.HYBRID,
                "metadata": {"purpose": "Machine learning datasets", "owner": "data_team"}
            },
            {
                "backend": BackendType.ARROW,
                "bucket_name": "analytics_data",
                "bucket_type": BucketType.DATASET,
                "vfs_structure": VFSStructureType.VECTOR,
                "metadata": {"purpose": "Analytics data processing", "retention_days": 90}
            },
            {
                "backend": BackendType.S3,
                "bucket_name": "cloud_storage",
                "bucket_type": BucketType.GENERAL,
                "vfs_structure": VFSStructureType.UNIXFS,
                "metadata": {"region": "us-west-2", "storage_class": "standard"}
            },
            {
                "backend": BackendType.SSHFS,
                "bucket_name": "remote_files",
                "bucket_type": BucketType.ARCHIVE,
                "vfs_structure": VFSStructureType.UNIXFS,
                "metadata": {"hostname": "backup.example.com", "port": 22}
            },
            {
                "backend": BackendType.GDRIVE,
                "bucket_name": "documents",
                "bucket_type": BucketType.MEDIA,
                "vfs_structure": VFSStructureType.GRAPH,
                "metadata": {"folder_id": "1ABC123...", "sync_enabled": True}
            }
        ]
        
        created_buckets = []
        
        for config in backend_configs:
            print(f"   Creating bucket '{config['bucket_name']}' for {config['backend'].value}...")
            
            result = await interface.create_backend_bucket(
                backend=config["backend"],
                bucket_name=config["bucket_name"],
                bucket_type=config["bucket_type"],
                vfs_structure=config["vfs_structure"],
                metadata=config["metadata"]
            )
            
            if result["success"]:
                created_buckets.append(config)
                print(f"   ✅ Created successfully")
                print(f"      Storage: {result['data']['storage_path']}")
                print(f"      VFS Index: {result['data']['vfs_index_path']}")
            else:
                print(f"   ❌ Failed: {result.get('error')}")
        
        print(f"\n✅ Created {len(created_buckets)} buckets")
        print()
        
        # Demo 2: Add content-addressed pins to buckets
        print("3. Adding Content-Addressed Pins...")
        print("-" * 40)
        
        # Create sample content files
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_files = []
            
            # Create sample files
            files_to_create = [
                ("dataset1.csv", "id,name,value\n1,Alice,100\n2,Bob,200\n3,Charlie,300"),
                ("config.json", json.dumps({"version": "1.0", "enabled": True, "timeout": 30}, indent=2)),
                ("readme.md", "# Sample Dataset\n\nThis is a sample dataset for demo purposes.\n"),
                ("data.parquet", b"PAR1\x15\x00\x15\x10\x15\x14L\x15\x02\x15\x00\x12\x00\x00\x08"),  # Mock Parquet header
                ("archive.tar.gz", b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff")  # Mock gzip header
            ]
            
            for filename, content in files_to_create:
                file_path = Path(temp_dir) / filename
                if isinstance(content, str):
                    file_path.write_text(content)
                else:
                    file_path.write_bytes(content)
                sample_files.append(file_path)
            
            # Add pins to different buckets
            pin_configs = [
                {
                    "backend": BackendType.PARQUET,
                    "bucket": "ml_datasets",
                    "file": sample_files[0],  # dataset1.csv
                    "vfs_path": "/data/training/dataset1.csv",
                    "hash": "QmDataset1Hash123",
                    "metadata": {"format": "csv", "rows": 3, "columns": 3}
                },
                {
                    "backend": BackendType.ARROW,
                    "bucket": "analytics_data",
                    "file": sample_files[3],  # data.parquet
                    "vfs_path": "/analytics/monthly/data.parquet",
                    "hash": "QmParquetHash456",
                    "metadata": {"format": "parquet", "schema_version": "1.0"}
                },
                {
                    "backend": BackendType.S3,
                    "bucket": "cloud_storage",
                    "file": sample_files[1],  # config.json
                    "vfs_path": "/configs/app_config.json",
                    "hash": "QmConfigHash789",
                    "metadata": {"content_type": "application/json", "environment": "production"}
                },
                {
                    "backend": BackendType.SSHFS,
                    "bucket": "remote_files",
                    "file": sample_files[4],  # archive.tar.gz
                    "vfs_path": "/backups/2024/archive.tar.gz",
                    "hash": "QmArchiveHashABC",
                    "metadata": {"compression": "gzip", "backup_date": "2024-01-15"}
                },
                {
                    "backend": BackendType.GDRIVE,
                    "bucket": "documents",
                    "file": sample_files[2],  # readme.md
                    "vfs_path": "/projects/demo/README.md",
                    "hash": "QmReadmeHashDEF",
                    "metadata": {"format": "markdown", "shared": True}
                }
            ]
            
            added_pins = []
            
            for config in pin_configs:
                print(f"   Adding pin to {config['backend'].value}/{config['bucket']}...")
                
                with open(config["file"], 'rb') as f:
                    content = f.read()
                
                result = await interface.add_content_pin(
                    backend=config["backend"],
                    bucket_name=config["bucket"],
                    content_hash=config["hash"],
                    file_path=config["vfs_path"],
                    content=content,
                    metadata=config["metadata"]
                )
                
                if result["success"]:
                    added_pins.append(config)
                    print(f"   ✅ Added pin '{config['hash']}'")
                    print(f"      Path: {config['vfs_path']}")
                    print(f"      Size: {len(content)} bytes")
                else:
                    print(f"   ❌ Failed: {result.get('error')}")
        
        print(f"\n✅ Added {len(added_pins)} pins across {len(set(p['backend'] for p in added_pins))} backends")
        print()
        
        # Demo 3: List buckets and show organization
        print("4. Listing Buckets and Organization...")
        print("-" * 40)
        
        result = await interface.list_backend_buckets()
        if result["success"]:
            buckets = result["data"]["buckets"]
            
            print(f"📋 Total buckets: {len(buckets)}")
            print()
            
            # Group by backend
            backends = {}
            for bucket in buckets:
                backend = bucket["backend"]
                if backend not in backends:
                    backends[backend] = []
                backends[backend].append(bucket)
            
            for backend, backend_buckets in backends.items():
                print(f"🔧 {backend.upper()} Backend:")
                for bucket in backend_buckets:
                    print(f"   📁 {bucket['bucket_name']} ({bucket['bucket_type']})")
                    print(f"      Pins: {bucket['pin_count']:,} | VFS Files: {bucket['vfs_files']:,}")
                    print(f"      Size: {format_size(bucket['total_size'])}")
                    print(f"      Structure: {bucket['vfs_structure']}")
                print()
        
        # Demo 4: Show VFS composition
        print("5. Virtual Filesystem Composition...")
        print("-" * 40)
        
        result = await interface.get_vfs_composition()
        if result["success"]:
            composition = result["data"]
            
            print(f"🗂️ Global VFS Statistics:")
            print(f"   Total Pins: {composition['total_pins']:,}")
            print(f"   Total Size: {format_size(composition['total_size'])}")
            print(f"   Backends: {len(composition['backends'])}")
            print()
            
            if composition["file_types"]:
                print("📊 File Type Distribution:")
                for file_type, count in sorted(composition["file_types"].items()):
                    print(f"   {file_type}: {count}")
                print()
            
            print("🏗️ Backend Composition:")
            for backend_name, backend_data in composition["backends"].items():
                print(f"   🔧 {backend_name.upper()}:")
                print(f"      Pins: {backend_data['total_pins']:,}")
                print(f"      Size: {format_size(backend_data['total_size'])}")
                print(f"      Buckets: {len(backend_data['buckets'])}")
                
                for bucket_name, bucket_data in backend_data["buckets"].items():
                    print(f"        📁 {bucket_name}: {bucket_data['pin_count']} pins")
            print()
        
        # Demo 5: Cross-backend querying (if DuckDB available)
        print("6. Cross-Backend Querying...")
        print("-" * 30)
        
        if interface.enable_cross_backend_queries:
            # First sync indices to ensure Parquet exports are available
            print("   Synchronizing indices for querying...")
            sync_result = await interface.sync_bucket_indices()
            
            if sync_result["success"]:
                print("   ✅ Indices synchronized")
                
                # Example queries
                queries = [
                    "SELECT COUNT(*) as total_files FROM vfs_parquet_ml_datasets",
                    "SELECT backend, bucket, COUNT(*) as pin_count FROM vfs_s3_cloud_storage GROUP BY backend, bucket",
                ]
                
                for query in queries:
                    print(f"   🔍 Query: {query}")
                    try:
                        result = await interface.query_across_backends(query)
                        if result["success"]:
                            data = result["data"]
                            print(f"      Results: {data['row_count']} rows")
                            for row in data["rows"][:3]:  # Show first 3 rows
                                print(f"      {row}")
                        else:
                            print(f"      ❌ Query failed: {result.get('error')}")
                    except Exception as e:
                        print(f"      ⚠️  Query not ready yet: {e}")
                    print()
            else:
                print("   ⚠️  Could not sync indices for querying")
        else:
            print("   ⚠️  Cross-backend querying not available (DuckDB not installed)")
        
        print()
        
        # Demo 6: Show directory structure
        print("7. Directory Structure in ~/.ipfs_kit/...")
        print("-" * 45)
        
        def print_tree(path, prefix="", max_depth=3, current_depth=0):
            """Print directory tree with depth limit."""
            if current_depth >= max_depth:
                return
            
            try:
                items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
                
                for i, item in enumerate(items[:10]):  # Limit items per directory
                    is_last = i == len(items) - 1
                    current_prefix = "└── " if is_last else "├── "
                    
                    if item.is_dir():
                        print(f"{prefix}{current_prefix}📁 {item.name}/")
                        next_prefix = prefix + ("    " if is_last else "│   ")
                        print_tree(item, next_prefix, max_depth, current_depth + 1)
                    else:
                        try:
                            size = item.stat().st_size
                            print(f"{prefix}{current_prefix}📄 {item.name} ({format_size(size)})")
                        except (OSError, PermissionError):
                            print(f"{prefix}{current_prefix}📄 {item.name}")
                            
                if len(items) > 10:
                    print(f"{prefix}    ... and {len(items) - 10} more items")
                    
            except PermissionError:
                print(f"{prefix}❌ Permission denied")
        
        print(f"📁 {interface.ipfs_kit_dir}")
        print_tree(interface.ipfs_kit_dir)
        print()
        
        # Demo 7: Synchronization
        print("8. Final Index Synchronization...")
        print("-" * 35)
        
        result = await interface.sync_bucket_indices()
        if result["success"]:
            data = result["data"]
            print(f"✅ Synchronized {data['successful_syncs']}/{data['total_buckets']} buckets")
            
            for sync_result in data["synced_buckets"]:
                bucket_id = sync_result["bucket_id"]
                sync_data = sync_result["sync_result"]
                
                if sync_data["success"]:
                    pin_count = sync_data["data"]["pin_count"]
                    total_size = sync_data["data"]["total_size"]
                    print(f"   ✅ {bucket_id}: {pin_count} pins ({format_size(total_size)})")
                else:
                    print(f"   ❌ {bucket_id}: {sync_data.get('error')}")
        else:
            print(f"❌ Synchronization failed: {result.get('error')}")
        
        print()
        print("🎉 Demo Complete!")
        print()
        print("Key Features Demonstrated:")
        print("✅ Multi-backend bucket creation")
        print("✅ Content-addressed pin storage")
        print("✅ VFS composition across backends")
        print("✅ Organized .ipfs_kit directory structure")
        print("✅ Cross-backend metadata indices")
        print("✅ Unified querying interface")
        print()
        print("Directory Layout Created:")
        print("~/.ipfs_kit/")
        print("├── buckets/")
        print("│   ├── parquet/ml_datasets/")
        print("│   ├── arrow/analytics_data/")
        print("│   ├── s3/cloud_storage/")
        print("│   ├── sshfs/remote_files/")
        print("│   └── gdrive/documents/")
        print("├── bucket_index/")
        print("├── pin_metadata/")
        print("├── vfs_indices/")
        print("└── bucket_registry.json")
        
        return True
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        await interface.cleanup()


def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


async def main():
    """Main demo entry point."""
    try:
        success = await demo_unified_bucket_interface()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⚠️  Demo cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
