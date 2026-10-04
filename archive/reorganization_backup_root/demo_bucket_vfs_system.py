#!/usr/bin/env python3
"""
Demo script for Multi-Bucket Virtual Filesystem

This demonstrates the enhanced IPFS-Kit daemon with multi-bucket VFS support,
where each bucket contains:
- UnixFS structure for file organization  
- Knowledge graph in IPLD format
- Vector index with IPLD compatibility
- Automatic export to Parquet/Arrow for DuckDB support
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, '/home/devel/ipfs_kit_py')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def demo_bucket_vfs_system():
    """Demonstrate the multi-bucket VFS system."""
    print("🗂️ Multi-Bucket Virtual Filesystem Demo")
    print("=" * 60)
    
    try:
        # Import bucket VFS manager
        from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager, BucketType, VFSStructureType
        
        print("✅ Successfully imported bucket VFS components")
        
        # Initialize bucket manager
        bucket_manager = get_global_bucket_manager(
            storage_path="/tmp/demo_buckets",
            enable_parquet_export=True,
            enable_duckdb_integration=True
        )
        
        print("✅ Bucket VFS Manager initialized")
        
    except ImportError as e:
        print(f"❌ Failed to import bucket VFS components: {e}")
        return
    
    # Demo 1: Create different types of buckets
    print("\n1. Creating Buckets")
    print("-" * 30)
    
    buckets_to_create = [
        {
            "name": "documents",
            "type": BucketType.GENERAL,
            "structure": VFSStructureType.HYBRID,
            "metadata": {"description": "General document storage"}
        },
        {
            "name": "datasets",
            "type": BucketType.DATASET,
            "structure": VFSStructureType.HYBRID,
            "metadata": {"description": "Structured data collections"}
        },
        {
            "name": "knowledge_base",
            "type": BucketType.KNOWLEDGE,
            "structure": VFSStructureType.GRAPH,
            "metadata": {"description": "Knowledge graphs and ontologies"}
        },
        {
            "name": "media_files",
            "type": BucketType.MEDIA,
            "structure": VFSStructureType.UNIXFS,
            "metadata": {"description": "Media files and metadata"}
        }
    ]
    
    for bucket_config in buckets_to_create:
        try:
            result = await bucket_manager.create_bucket(
                bucket_name=bucket_config["name"],
                bucket_type=bucket_config["type"],
                vfs_structure=bucket_config["structure"],
                metadata=bucket_config["metadata"]
            )
            
            if result["success"]:
                print(f"✅ Created bucket '{bucket_config['name']}' (type: {bucket_config['type'].value})")
                print(f"   - Structure: {bucket_config['structure'].value}")
                print(f"   - Root CID: {result['data']['cid']}")
            else:
                print(f"❌ Failed to create bucket '{bucket_config['name']}': {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Error creating bucket '{bucket_config['name']}': {e}")
    
    # Demo 2: List buckets
    print("\n2. Listing Buckets")
    print("-" * 30)
    
    try:
        buckets_result = await bucket_manager.list_buckets()
        
        if buckets_result["success"]:
            buckets = buckets_result["data"]["buckets"]
            print(f"📋 Found {len(buckets)} buckets:")
            
            for bucket in buckets:
                print(f"   • {bucket['name']} ({bucket['type']})")
                print(f"     - Files: {bucket['file_count']}, Size: {bucket['size_bytes']} bytes")
                print(f"     - Structure: {bucket['vfs_structure']}")
                print(f"     - Root CID: {bucket['root_cid']}")
        else:
            print(f"❌ Failed to list buckets: {buckets_result.get('error')}")
            
    except Exception as e:
        print(f"❌ Error listing buckets: {e}")
    
    # Demo 3: Add files to different buckets
    print("\n3. Adding Files to Buckets")
    print("-" * 30)
    
    files_to_add = [
        {
            "bucket": "documents",
            "path": "/readme.txt",
            "content": "# Welcome to Documents Bucket\n\nThis is a hybrid VFS with UnixFS structure, knowledge graph, and vector index.",
            "metadata": {"type": "documentation", "language": "en"}
        },
        {
            "bucket": "datasets",
            "path": "/sales_data.csv",
            "content": "date,product,sales\n2024-01-01,widget,100\n2024-01-02,gadget,150",
            "metadata": {"format": "csv", "schema": "sales"}
        },
        {
            "bucket": "knowledge_base",
            "path": "/concepts.json",
            "content": json.dumps({
                "entities": [
                    {"id": "ipfs", "type": "technology", "description": "InterPlanetary File System"},
                    {"id": "ipld", "type": "data_model", "description": "InterPlanetary Linked Data"}
                ],
                "relationships": [
                    {"from": "ipfs", "to": "ipld", "type": "uses", "description": "IPFS uses IPLD for data representation"}
                ]
            }, indent=2),
            "metadata": {"format": "json", "schema": "knowledge_graph"}
        },
        {
            "bucket": "media_files",
            "path": "/images/logo.svg",
            "content": """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                <rect width="100" height="100" fill="#007acc"/>
                <text x="50" y="50" fill="white" text-anchor="middle">IPFS</text>
            </svg>""",
            "metadata": {"type": "image", "format": "svg"}
        }
    ]
    
    for file_config in files_to_add:
        try:
            bucket = await bucket_manager.get_bucket(file_config["bucket"])
            if bucket:
                result = await bucket.add_file(
                    file_path=file_config["path"],
                    content=file_config["content"],
                    metadata=file_config["metadata"]
                )
                
                if result["success"]:
                    print(f"✅ Added file '{file_config['path']}' to bucket '{file_config['bucket']}'")
                    print(f"   - Size: {result['data']['size']} bytes")
                    if result['data']['cid']:
                        print(f"   - CID: {result['data']['cid']}")
                else:
                    print(f"❌ Failed to add file: {result.get('error')}")
            else:
                print(f"❌ Bucket '{file_config['bucket']}' not found")
                
        except Exception as e:
            print(f"❌ Error adding file to bucket '{file_config['bucket']}': {e}")
    
    # Demo 4: Export buckets to IPLD/CAR format
    print("\n4. Exporting Buckets to CAR Archives")
    print("-" * 30)
    
    try:
        buckets_result = await bucket_manager.list_buckets()
        
        if buckets_result["success"]:
            for bucket_info in buckets_result["data"]["buckets"]:
                bucket_name = bucket_info["name"]
                
                try:
                    export_result = await bucket_manager.export_bucket_to_car(
                        bucket_name=bucket_name,
                        include_indexes=True
                    )
                    
                    if export_result["success"]:
                        print(f"✅ Exported bucket '{bucket_name}' to CAR archive")
                        print(f"   - CAR file: {export_result['data']['car_path']}")
                        print(f"   - Items exported: {export_result['data']['exported_items']}")
                        if export_result['data'].get('car_cid'):
                            print(f"   - CAR CID: {export_result['data']['car_cid']}")
                    else:
                        print(f"❌ Failed to export bucket '{bucket_name}': {export_result.get('error')}")
                        
                except Exception as e:
                    print(f"❌ Error exporting bucket '{bucket_name}': {e}")
    
    except Exception as e:
        print(f"❌ Error during bucket export: {e}")
    
    # Demo 5: Cross-bucket SQL queries (if DuckDB available)
    print("\n5. Cross-Bucket SQL Queries")
    print("-" * 30)
    
    try:
        if bucket_manager.enable_duckdb_integration:
            # Example SQL queries
            queries = [
                "SELECT COUNT(*) as total_buckets FROM information_schema.tables WHERE table_schema = 'main'",
                "SHOW TABLES",
            ]
            
            for query in queries:
                try:
                    result = await bucket_manager.cross_bucket_query(query)
                    
                    if result["success"]:
                        print(f"✅ Query: {query}")
                        print(f"   - Columns: {result['data']['columns']}")
                        print(f"   - Rows: {len(result['data']['rows'])}")
                        if result['data']['rows']:
                            for row in result['data']['rows'][:3]:  # Show first 3 rows
                                print(f"     {row}")
                    else:
                        print(f"❌ Query failed: {result.get('error')}")
                        
                except Exception as e:
                    print(f"❌ Error executing query '{query}': {e}")
        else:
            print("⚠️ DuckDB integration not available")
    
    except Exception as e:
        print(f"❌ Error during cross-bucket queries: {e}")
    
    # Demo 6: Show bucket structures and IPLD compatibility
    print("\n6. Bucket Structures and IPLD Compatibility")
    print("-" * 30)
    
    try:
        buckets_result = await bucket_manager.list_buckets()
        
        if buckets_result["success"]:
            for bucket_info in buckets_result["data"]["buckets"]:
                bucket_name = bucket_info["name"]
                bucket = await bucket_manager.get_bucket(bucket_name)
                
                if bucket:
                    print(f"📁 Bucket: {bucket_name}")
                    print(f"   - Type: {bucket.bucket_type.value}")
                    print(f"   - VFS Structure: {bucket.vfs_structure.value}")
                    print(f"   - Root CID: {bucket.root_cid}")
                    print(f"   - Storage Path: {bucket.storage_path}")
                    
                    # Show directory structure
                    print("   - Directory Structure:")
                    for dir_name, dir_path in bucket.dirs.items():
                        exists = "✅" if dir_path.exists() else "❌"
                        print(f"     {exists} {dir_name}: {dir_path}")
                    
                    # Show component availability
                    print("   - Components:")
                    kg_status = "✅" if bucket.knowledge_graph else "❌"
                    vector_status = "✅" if bucket.vector_index else "❌"
                    print(f"     {kg_status} Knowledge Graph")
                    print(f"     {vector_status} Vector Index")
                    
                    print()
    
    except Exception as e:
        print(f"❌ Error showing bucket structures: {e}")
    
    print("\n🎯 Demo Summary")
    print("-" * 30)
    print("✅ Multi-bucket VFS system demonstrated successfully!")
    print("\n📋 Features Demonstrated:")
    print("• S3-like bucket semantics with different types")
    print("• UnixFS structure for file organization")
    print("• Knowledge graph integration in IPLD format")
    print("• Vector index with IPLD compatibility")
    print("• Automatic Parquet/Arrow export for DuckDB")
    print("• CAR archive export for IPFS distribution")
    print("• Cross-bucket SQL queries")
    print("• IPFS content addressing and traversal")
    
    print("\n🔗 IPFS Compatibility:")
    print("• All bucket data is stored in IPLD format")
    print("• CAR archives enable IPFS network distribution")
    print("• Root CIDs allow direct IPFS access: ipfs://CID")
    print("• File structure is traversable via IPFS gateway")
    
    print("\n📊 Cross-Platform Support:")
    print("• Parquet export enables DuckDB integration")
    print("• Arrow format supports multiple languages")
    print("• JSON exports work with any JSON parser")
    print("• Standard filesystem APIs for existing tools")


if __name__ == "__main__":
    asyncio.run(demo_bucket_vfs_system())
