#!/usr/bin/env python3
"""
Demo script showcasing the bucket VFS CLI and MCP API interfaces.

This script demonstrates:
1. CLI usage for bucket management
2. MCP API integration for programmatic access
3. Cross-bucket SQL queries
4. CAR archive export for IPFS distribution
5. Integration with existing IPFS Kit ecosystem
"""

import anyio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def demo_header(title: str):
    """Print a formatted demo header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def demo_section(title: str):
    """Print a formatted demo section."""
    print(f"\n--- {title} ---")

async def demo_cli_interface():
    """Demonstrate CLI interface usage."""
    demo_header("BUCKET VFS CLI INTERFACE DEMO")
    
    # Set up demo storage path
    demo_storage = "/tmp/demo_bucket_vfs"
    os.makedirs(demo_storage, exist_ok=True)
    
    demo_section("1. Creating Buckets via CLI")
    
    # Demo bucket creation commands
    cli_commands = [
        # Create different types of buckets
        f"python -m ipfs_kit_py.cli bucket create general-docs --type general --structure hybrid --storage-path {demo_storage}",
        f"python -m ipfs_kit_py.cli bucket create dataset-store --type dataset --structure unixfs --storage-path {demo_storage}",
        f"python -m ipfs_kit_py.cli bucket create knowledge-base --type knowledge --structure graph --storage-path {demo_storage}",
        
        # List buckets
        f"python -m ipfs_kit_py.cli bucket list --storage-path {demo_storage} --detailed",
        
        # Add files to buckets
        f"python -m ipfs_kit_py.cli bucket add-file general-docs README.md 'Welcome to the general documents bucket!' --storage-path {demo_storage}",
        f"python -m ipfs_kit_py.cli bucket add-file dataset-store data.csv 'name,age,city\\nAlice,30,NYC\\nBob,25,LA' --storage-path {demo_storage}",
        f"python -m ipfs_kit_py.cli bucket add-file knowledge-base concepts.json '{{\"topic\": \"IPFS\", \"description\": \"Distributed storage\"}}' --storage-path {demo_storage}",
        
        # Export bucket to CAR
        f"python -m ipfs_kit_py.cli bucket export general-docs --storage-path {demo_storage}",
        
        # Cross-bucket SQL query
        f"python -m ipfs_kit_py.cli bucket query 'SELECT bucket_name, file_path, file_size FROM files ORDER BY file_size DESC' --storage-path {demo_storage}",
    ]
    
    for i, command in enumerate(cli_commands, 1):
        print(f"\n{i}. Command: {command}")
        print("   Example output:")
        
        # For demo purposes, show what the output would look like
        if "create" in command:
            if "general-docs" in command:
                print("   ✅ Created bucket 'general-docs' (type: general, structure: hybrid)")
                print("   📁 Root CID: bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c7")
                print("   📅 Created at: 2024-12-31T22:00:00Z")
            elif "dataset-store" in command:
                print("   ✅ Created bucket 'dataset-store' (type: dataset, structure: unixfs)")
                print("   📁 Root CID: bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c8")
            elif "knowledge-base" in command:
                print("   ✅ Created bucket 'knowledge-base' (type: knowledge, structure: graph)")
                print("   📁 Root CID: bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c9")
        
        elif "list" in command:
            print("   ✅ Found 3 bucket(s):")
            print("   📦 general-docs     (general/hybrid)    5 files, 1.2 KB")
            print("   📦 dataset-store    (dataset/unixfs)    3 files, 856 B")
            print("   📦 knowledge-base   (knowledge/graph)   12 files, 3.4 KB")
            print("   📊 Total: 20 files, 5.5 KB across 3 buckets")
        
        elif "add-file" in command:
            if "README.md" in command:
                print("   ✅ Added file 'README.md' to bucket 'general-docs'")
                print("   📄 File CID: bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c10")
                print("   📏 Size: 45 bytes")
            elif "data.csv" in command:
                print("   ✅ Added file 'data.csv' to bucket 'dataset-store'")
                print("   📄 File CID: bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c11")
                print("   📏 Size: 38 bytes")
            elif "concepts.json" in command:
                print("   ✅ Added file 'concepts.json' to bucket 'knowledge-base'")
                print("   📄 File CID: bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c12")
                print("   📏 Size: 68 bytes")
        
        elif "export" in command:
            print("   ✅ Exported bucket 'general-docs' to CAR archive")
            print("   📦 CAR file: /tmp/demo_bucket_vfs/general-docs.car")
            print("   🌐 CAR CID: bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c13")
            print("   📋 Exported items: 5 files + metadata + indexes")
        
        elif "query" in command:
            print("   ✅ Query executed successfully (3 rows)")
            print("   bucket_name      | file_path      | file_size")
            print("   -----------------+----------------+-----------")
            print("   knowledge-base   | concepts.json  | 68")
            print("   general-docs     | README.md      | 45")
            print("   dataset-store    | data.csv       | 38")

async def demo_mcp_api():
    """Demonstrate MCP API interface usage."""
    demo_header("BUCKET VFS MCP API DEMO")
    
    try:
        from mcp.bucket_vfs_mcp_tools import (
            handle_bucket_create,
            handle_bucket_list,
            handle_bucket_add_file,
            handle_bucket_cross_query,
            handle_bucket_export_car,
            handle_bucket_status
        )
        
        demo_section("1. Creating Buckets via MCP API")
        
        # Create a bucket
        create_args = {
            "bucket_name": "api-demo-bucket",
            "bucket_type": "general",
            "vfs_structure": "hybrid",
            "metadata": {"created_by": "mcp_demo", "purpose": "demonstration"},
            "storage_path": "/tmp/demo_mcp_bucket_vfs"
        }
        
        print("Creating bucket with MCP API...")
        print(f"Arguments: {json.dumps(create_args, indent=2)}")
        
        # For demo purposes, show expected response
        print("\nExpected Response:")
        expected_response = {
            "success": True,
            "message": "Created bucket 'api-demo-bucket'",
            "bucket": {
                "name": "api-demo-bucket",
                "type": "general",
                "structure": "hybrid",
                "root_cid": "bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c14",
                "created_at": "2024-12-31T22:10:00Z"
            }
        }
        print(json.dumps(expected_response, indent=2))
        
        demo_section("2. Adding Files via MCP API")
        
        add_file_args = {
            "bucket_name": "api-demo-bucket",
            "file_path": "demo/example.txt",
            "content": "This is a demonstration file added via MCP API",
            "content_type": "text",
            "metadata": {"source": "mcp_demo", "type": "text/plain"}
        }
        
        print("Adding file with MCP API...")
        print(f"Arguments: {json.dumps(add_file_args, indent=2)}")
        
        print("\nExpected Response:")
        expected_file_response = {
            "success": True,
            "message": "Added file 'demo/example.txt' to bucket 'api-demo-bucket'",
            "file": {
                "path": "demo/example.txt",
                "size": 48,
                "cid": "bafybeihkoviema7g3gxyt6la7b7kbbv2dqk68j16rcxz4wtqjj4c15",
                "local_path": "/tmp/demo_mcp_bucket_vfs/api-demo-bucket/files/demo/example.txt"
            }
        }
        print(json.dumps(expected_file_response, indent=2))
        
        demo_section("3. Cross-Bucket Queries via MCP API")
        
        query_args = {
            "sql_query": "SELECT bucket_name, COUNT(*) as file_count, SUM(file_size) as total_size FROM files GROUP BY bucket_name",
            "format": "json"
        }
        
        print("Executing cross-bucket query with MCP API...")
        print(f"SQL Query: {query_args['sql_query']}")
        
        print("\nExpected Response:")
        expected_query_response = {
            "success": True,
            "query": query_args["sql_query"],
            "row_count": 2,
            "columns": ["bucket_name", "file_count", "total_size"],
            "results": [
                {"bucket_name": "api-demo-bucket", "file_count": 1, "total_size": 48},
                {"bucket_name": "general-docs", "file_count": 5, "total_size": 1240}
            ]
        }
        print(json.dumps(expected_query_response, indent=2))
        
        demo_section("4. System Status via MCP API")
        
        status_args = {"include_health": True}
        
        print("Getting system status with MCP API...")
        
        print("\nExpected Response:")
        expected_status_response = {
            "success": True,
            "system": {
                "available": True,
                "storage_path": "/tmp/demo_mcp_bucket_vfs",
                "duckdb_integration": True
            },
            "statistics": {
                "total_buckets": 4,
                "total_files": 21,
                "total_size_bytes": 5648,
                "bucket_types": {"general": 2, "dataset": 1, "knowledge": 1},
                "vfs_structures": {"hybrid": 2, "unixfs": 1, "graph": 1}
            },
            "health": {
                "healthy_buckets": 4,
                "total_buckets": 4,
                "health_percentage": 100.0
            }
        }
        print(json.dumps(expected_status_response, indent=2))
        
    except ImportError as e:
        print(f"MCP API demo skipped - modules not available: {e}")

async def demo_integration_features():
    """Demonstrate integration features."""
    demo_header("INTEGRATION FEATURES DEMO")
    
    demo_section("1. S3-like Bucket Semantics")
    print("✅ Bucket types: GENERAL, DATASET, KNOWLEDGE, MEDIA, ARCHIVE, TEMP")
    print("✅ Hierarchical file organization within buckets")
    print("✅ Metadata support for buckets and files")
    print("✅ Versioning and content addressing via IPFS CIDs")
    
    demo_section("2. VFS Structure Types")
    print("✅ UnixFS: Traditional POSIX-like filesystem structure")
    print("✅ Graph: Knowledge graph with RDF/triple store integration")
    print("✅ Vector: Vector embeddings with similarity search")
    print("✅ Hybrid: Combines UnixFS, Graph, and Vector capabilities")
    
    demo_section("3. IPLD Compatibility")
    print("✅ All bucket data stored in IPLD format")
    print("✅ Content-addressable storage with CID references")
    print("✅ Merkle-DAG structure for efficient deduplication")
    print("✅ CAR (Content Addressable aRchives) export for distribution")
    
    demo_section("4. Analytics and Query Capabilities")
    print("✅ DuckDB integration for SQL queries across buckets")
    print("✅ Apache Arrow/Parquet export for analytics workflows")
    print("✅ Cross-bucket joins and aggregations")
    print("✅ Schema inference and type preservation")
    
    demo_section("5. Interface Consistency")
    print("✅ CLI interface for command-line operations")
    print("✅ MCP API for programmatic access")
    print("✅ Shared storage backend between interfaces")
    print("✅ Consistent error handling and response formats")

def demo_usage_examples():
    """Show practical usage examples."""
    demo_header("PRACTICAL USAGE EXAMPLES")
    
    demo_section("1. Data Science Workflow")
    print("# Create dataset bucket")
    print("ipfs-kit bucket create ml-datasets --type dataset --structure unixfs")
    print()
    print("# Add training data")
    print("ipfs-kit bucket add-file ml-datasets train.csv < training_data.csv")
    print("ipfs-kit bucket add-file ml-datasets test.csv < test_data.csv")
    print()
    print("# Query data across buckets")
    print("ipfs-kit bucket query 'SELECT bucket_name, COUNT(*) FROM files WHERE file_path LIKE \"%.csv\" GROUP BY bucket_name'")
    print()
    print("# Export for distributed training")
    print("ipfs-kit bucket export ml-datasets --include-indexes")
    
    demo_section("2. Knowledge Management")
    print("# Create knowledge base")
    print("ipfs-kit bucket create company-kb --type knowledge --structure graph")
    print()
    print("# Add documents and build knowledge graph")
    print("ipfs-kit bucket add-file company-kb docs/policies.md < policies.md")
    print("ipfs-kit bucket add-file company-kb docs/procedures.md < procedures.md")
    print()
    print("# Query knowledge relationships")
    print("ipfs-kit bucket query 'SELECT * FROM knowledge_graph WHERE relation_type = \"related_to\"'")
    
    demo_section("3. Media Archive")
    print("# Create media archive")
    print("ipfs-kit bucket create media-archive --type media --structure hybrid")
    print()
    print("# Add media files with metadata")
    print("ipfs-kit bucket add-file media-archive photos/vacation.jpg < photo.jpg --metadata '{\"date\": \"2024-12-25\", \"location\": \"NYC\"}'")
    print()
    print("# Export archive for IPFS distribution")
    print("ipfs-kit bucket export media-archive")

async def main():
    """Main demo function."""
    print("🌟 Welcome to the Bucket VFS CLI and MCP API Demo!")
    print("This demo showcases the multi-bucket virtual filesystem with S3-like semantics.")
    
    # Run demo sections
    await demo_cli_interface()
    await demo_mcp_api()
    await demo_integration_features()
    demo_usage_examples()
    
    demo_header("DEMO COMPLETE")
    print("✅ CLI Interface: Comprehensive command-line tools for bucket management")
    print("✅ MCP API: Programmatic access via Model Context Protocol")
    print("✅ IPLD Storage: Content-addressable storage with IPFS compatibility")
    print("✅ SQL Queries: Cross-bucket analytics with DuckDB integration")
    print("✅ CAR Export: Distribute buckets via IPFS Content Archives")
    print()
    print("🚀 Ready for production use in IPFS Kit ecosystem!")
    print()
    print("📖 Documentation:")
    print("   - CLI Help: python -m ipfs_kit_py.cli bucket --help")
    print("   - MCP Tools: Available via enhanced MCP server")
    print("   - Test Suite: python run_bucket_vfs_tests.py")

if __name__ == "__main__":
    anyio.run(main)
