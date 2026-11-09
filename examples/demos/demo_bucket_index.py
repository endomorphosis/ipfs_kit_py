#!/usr/bin/env python3
"""
Demo script for Enhanced Bucket Index - Quick Virtual Filesystem Discovery

This demonstrates the new bucket index functionality that allows quick discovery
of virtual filesystems in ~/.ipfs_kit/ similar to how the pin index works.
"""

import anyio
import logging
import tempfile
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Demonstrate the enhanced bucket index functionality."""
    print("🗂️ Enhanced Bucket Index Demonstration")
    print("=" * 60)
    
    try:
        # Import bucket index
        from ipfs_kit_py.enhanced_bucket_index import get_global_enhanced_bucket_index, print_bucket_metrics
        print("✅ Imported Enhanced Bucket Index")
        
        # Import bucket VFS manager to create test data
        from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager, BucketType, VFSStructureType
        print("✅ Imported Bucket VFS Manager")
        
        # Use a temporary directory for demo
        with tempfile.TemporaryDirectory() as temp_dir:
            demo_storage = Path(temp_dir) / "demo_buckets"
            demo_index = Path(temp_dir) / "demo_index"
            
            print(f"📁 Demo storage: {demo_storage}")
            print(f"📁 Demo index: {demo_index}")
            
            # Initialize bucket manager with demo data
            bucket_manager = get_global_bucket_manager(
                storage_path=str(demo_storage),
                enable_parquet_export=True,
                enable_duckdb_integration=True
            )
            
            # Initialize bucket index
            bucket_index = get_global_enhanced_bucket_index(storage_dir=str(demo_index))
            
            print("✅ Initialized bucket manager and index")
            
            # 1. Create some demo buckets
            print("\n1. Creating Demo Buckets")
            print("-" * 30)
            
            demo_buckets = [
                {
                    "name": "documents",
                    "type": BucketType.GENERAL,
                    "structure": VFSStructureType.HYBRID,
                    "metadata": {"description": "Document storage"}
                },
                {
                    "name": "datasets",
                    "type": BucketType.DATASET,
                    "structure": VFSStructureType.HYBRID,
                    "metadata": {"description": "Data collections"}
                },
                {
                    "name": "knowledge_base",
                    "type": BucketType.KNOWLEDGE,
                    "structure": VFSStructureType.GRAPH,
                    "metadata": {"description": "Knowledge graphs"}
                }
            ]
            
            for bucket_config in demo_buckets:
                result = await bucket_manager.create_bucket(
                    bucket_name=bucket_config["name"],
                    bucket_type=bucket_config["type"],
                    vfs_structure=bucket_config["structure"],
                    metadata=bucket_config["metadata"]
                )
                
                if result["success"]:
                    print(f"✅ Created bucket: {bucket_config['name']}")
                else:
                    print(f"❌ Failed to create bucket: {bucket_config['name']}")
            
            # 2. Refresh bucket index
            print("\n2. Refreshing Bucket Index")
            print("-" * 30)
            
            refresh_result = bucket_index.refresh_index()
            if refresh_result["success"]:
                print("✅ Bucket index refreshed")
                print(f"   Indexed buckets: {refresh_result['data']['bucket_count']}")
            else:
                print(f"❌ Failed to refresh index: {refresh_result.get('error')}")
            
            # 3. List all buckets
            print("\n3. Listing All Virtual Filesystems")
            print("-" * 30)
            
            buckets_result = bucket_index.list_all_buckets(include_metadata=True)
            if buckets_result["success"]:
                buckets = buckets_result["data"]["buckets"]
                print(f"📋 Found {len(buckets)} virtual filesystems:")
                
                for bucket in buckets:
                    print(f"  📁 {bucket['name']}")
                    print(f"     Type: {bucket['type']}")
                    print(f"     Structure: {bucket['vfs_structure']}")
                    print(f"     Files: {bucket['file_count']}")
                    print(f"     Created: {bucket['created_at']}")
            else:
                print(f"❌ Error listing buckets: {buckets_result.get('error')}")
            
            # 4. Show comprehensive metrics
            print("\n4. Comprehensive Metrics")
            print("-" * 30)
            
            metrics_result = bucket_index.get_comprehensive_metrics()
            if metrics_result["success"]:
                print_bucket_metrics(metrics_result)
            else:
                print(f"❌ Error getting metrics: {metrics_result.get('error')}")
            
            # 5. Get bucket details
            print("\n5. Bucket Details")
            print("-" * 30)
            
            details_result = bucket_index.get_bucket_details("documents")
            if details_result["success"]:
                details = details_result["data"]
                print(f"📊 Details for '{details['name']}':")
                print(f"   Type: {details['type']}")
                print(f"   Storage: {details['storage_path']}")
                print(f"   Access count: {details['access_count']}")
                print(f"   Last indexed: {details['last_indexed']}")
            else:
                print(f"❌ Error getting details: {details_result.get('error')}")
            
            # 6. Search buckets
            print("\n6. Searching Buckets")
            print("-" * 30)
            
            search_result = bucket_index.search_buckets("knowledge", "name")
            if search_result["success"]:
                results = search_result["data"]["results"]
                print(f"🔍 Found {len(results)} buckets matching 'knowledge':")
                for bucket in results:
                    print(f"   📁 {bucket['name']} ({bucket['type']})")
            else:
                print(f"❌ Error searching: {search_result.get('error')}")
            
            # 7. Bucket types summary
            print("\n7. Bucket Types Summary")
            print("-" * 30)
            
            types_result = bucket_index.get_bucket_types_summary()
            if types_result["success"]:
                types_data = types_result["data"]
                for bucket_type, info in types_data.items():
                    print(f"📁 {bucket_type}: {info['count']} buckets")
                    print(f"   Files: {info['total_files']}")
                    print(f"   Buckets: {', '.join(info['buckets'])}")
            else:
                print(f"❌ Error getting types: {types_result.get('error')}")
            
            print("\n🎯 Enhanced Bucket Index Features Demonstrated:")
            print("✅ Fast virtual filesystem discovery in ~/.ipfs_kit/")
            print("✅ Parquet-based storage for efficient querying")
            print("✅ Comprehensive metadata tracking")
            print("✅ Real-time statistics and analytics")
            print("✅ Search functionality across bucket attributes")
            print("✅ Background index updates and synchronization")
            print("✅ Integration with bucket VFS manager")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure bucket index and VFS components are available")
    except Exception as e:
        print(f"❌ Demo error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    anyio.run(main)
