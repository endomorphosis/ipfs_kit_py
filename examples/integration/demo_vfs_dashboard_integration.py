#!/usr/bin/env python3
"""
Demo: VFS Dashboard Integration

This demo shows how to use the enhanced dashboard API with integrated
virtual filesystem meta        # Get comprehensive status including replication
        print("\n8. Comprehensive Dashboard Status...")

        comprehensive_status = await controller.get_comprehensive_status()
        print(f"✓ Comprehensive status retrieved: {comprehensive_status.get('success', False)}")

        if comprehensive_status.get("data"):
            status_data = comprehensive_status["data"]
            print(f"  - Total components: {len(status_data)}")

            # Show VFS-related status
            vfs_components = [k for k in status_data.keys()
                            if any(x in k.lower() for x in ['vfs', 'vector', 'knowledge', 'pinset', 'replication'])]
            if vfs_components:
                print(f"  - VFS components: {', '.join(vfs_components)}")

            # Show replication metrics
            if "replication" in status_data:
                replication_data = status_data["replication"]
                print(f"  - Replication efficiency: {replication_data.get('replication_efficiency', 0):.1f}%")
                print(f"  - Under-replicated pins: {replication_data.get('under_replicated', 0)}")

        # Demo CAR archive conversion capabilities
        print("\n9. CAR Archive Conversion Demo...")es, knowledge graphs, and pinsets
using columnar IPLD storage with parquet files and CAR archives.

Features demonstrated:
- VFS dataset listing and metadata retrieval
- Parquet to CAR archive conversion
- Vector index operations and CAR export
- Knowledge graph entity management and CAR export
- Pinset tracking across storage backends
- IPFS CID access to all columnar data
"""

import anyio
import json
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_vfs_dashboard_integration():
    """Demonstrate VFS and columnar IPLD integration with dashboard."""

    print("🔧 VFS Dashboard Integration Demo")
    print("=" * 50)

    try:
        # Import the enhanced dashboard controller
        from ipfs_kit_py.mcp.ipfs_kit.api.enhanced_dashboard_api import (
            DashboardController,
            VirtualFilesystemRequest,
            VectorIndexRequest,
            KnowledgeGraphRequest,
            PinsetRequest,
            ReplicationRequest,
            BackupRestoreRequest,
            ReplicationSettings,
        )

        # Initialize dashboard controller
        print("\n1. Initializing Dashboard Controller...")
        controller = DashboardController()
        await controller.initialize()

        print("✓ Dashboard controller initialized")
        print(f"✓ VFS API available: {controller.vfs_api is not None}")
        print(f"✓ Vector API available: {controller.vector_api is not None}")
        print(f"✓ Knowledge Graph available: {controller.knowledge_graph is not None}")
        print(f"✓ Pinset API available: {controller.pinset_api is not None}")
        print(f"✓ Parquet Bridge available: {controller.parquet_bridge is not None}")
        print(f"✓ CAR Bridge available: {controller.car_bridge is not None}")
        print(f"✓ Replication Manager available: {controller.replication_manager is not None}")

        # Demo VFS operations
        print("\n2. Virtual Filesystem Operations...")

        # List VFS datasets
        vfs_list_request = VirtualFilesystemRequest(action="list")
        vfs_result = await controller.perform_vfs_operation(vfs_list_request)
        print(f"✓ VFS datasets listed: {vfs_result.get('success', False)}")
        if vfs_result.get("data"):
            print(f"  - Total datasets: {vfs_result['data'].get('total_count', 0)}")

        # Demo vector operations
        print("\n3. Vector Index Operations...")

        # List vector collections
        vector_list_request = VectorIndexRequest(action="list")
        vector_result = await controller.perform_vector_operation(vector_list_request)
        print(f"✓ Vector collections listed: {vector_result.get('success', False)}")
        if vector_result.get("data"):
            print(f"  - Total collections: {vector_result['data'].get('total_collections', 0)}")

        # Get vector status
        vector_status_request = VectorIndexRequest(action="get_status")
        vector_status = await controller.perform_vector_operation(vector_status_request)
        print(f"✓ Vector status retrieved: {vector_status.get('success', False)}")

        # Demo knowledge graph operations
        print("\n4. Knowledge Graph Operations...")

        # List KG entities
        kg_list_request = KnowledgeGraphRequest(action="list_entities")
        kg_result = await controller.perform_kg_operation(kg_list_request)
        print(f"✓ KG entities listed: {kg_result.get('success', False)}")
        if kg_result.get("data"):
            print(f"  - Total entities: {kg_result['data'].get('total_entities', 0)}")

        # Demo pinset operations
        print("\n5. Pinset Management Operations...")

        # List pins
        pinset_list_request = PinsetRequest(action="list")
        pinset_result = await controller.perform_pinset_operation(pinset_list_request)
        print(f"✓ Pinset pins listed: {pinset_result.get('success', False)}")
        if pinset_result.get("data"):
            print(f"  - Total pins: {pinset_result['data'].get('total_pins', 0)}")

        # Track storage backends
        pinset_backends_request = PinsetRequest(action="track_backends")
        backends_result = await controller.perform_pinset_operation(pinset_backends_request)
        print(f"✓ Storage backends tracked: {backends_result.get('success', False)}")

        # Demo replication management operations
        print("\n6. Replication Management Operations...")

        # Get replication status
        replication_status_request = ReplicationRequest(action="analyze")
        replication_status = await controller.perform_replication_operation(
            replication_status_request
        )
        print(f"✓ Replication status retrieved: {replication_status.get('success', False)}")
        if replication_status.get("data"):
            status_data = replication_status["data"]["data"]
            print(f"  - Total pins: {status_data.get('total_pins', 0)}")
            print(
                f"  - Replication efficiency: {status_data.get('replication_efficiency', 0):.1f}%"
            )
            print(f"  - Under-replicated: {status_data.get('under_replicated', 0)}")

        # Configure replication settings
        replication_settings = ReplicationSettings(
            min_replicas=2,
            target_replicas=3,
            max_replicas=5,
            max_size_gb=100.0,
            auto_replication=True,
            replication_strategy="balanced",
        )

        settings_request = ReplicationRequest(action="configure", settings=replication_settings)
        settings_result = await controller.perform_replication_operation(settings_request)
        print(f"✓ Replication settings configured: {settings_result.get('success', False)}")

        # Demo backup operations
        print("\n7. Backup & Data Protection Operations...")

        # Export backup for IPFS backend
        backup_request = BackupRestoreRequest(
            action="export_pins", backend_name="ipfs", include_metadata=True, compress=True
        )
        backup_result = await controller.perform_backup_restore_operation(backup_request)
        print(f"✓ Backup export attempted: {backup_result.get('success', False)}")
        if backup_result.get("data") and backup_result["data"].get("backup_path"):
            print(f"  - Backup path: {backup_result['data']['backup_path']}")
            print(f"  - Pins exported: {backup_result['data'].get('pins_exported', 0)}")

        # Get comprehensive status including replication
        print("\n8. Comprehensive Dashboard Status...")

        comprehensive_status = await controller.get_comprehensive_status()
        print(f"✓ Comprehensive status retrieved: {comprehensive_status.get('success', False)}")

        if comprehensive_status.get("data"):
            status_data = comprehensive_status["data"]
            print(f"  - Total components: {len(status_data)}")

            # Show VFS-related status
            vfs_components = [
                k
                for k in status_data.keys()
                if any(x in k.lower() for x in ["vfs", "vector", "knowledge", "pinset"])
            ]
            if vfs_components:
                print(f"  - VFS components: {', '.join(vfs_components)}")

        # Demo CAR archive conversion capabilities
        print("\n7. CAR Archive Conversion Demo...")

        if controller.car_bridge:
            print("✓ CAR bridge available for parquet <-> CAR conversion")
            print("  - Can convert parquet datasets to IPLD CAR archives")
            print("  - Can convert CAR archives back to parquet files")
            print("  - Content-addressed storage with IPFS CIDs")
            print("  - Vector indexes and knowledge graphs included in CAR exports")

        # Display API endpoints summary
        print("\n10. Available API Endpoints...")
        print("📡 VFS Endpoints:")
        print("  - POST /api/vfs/operation - General VFS operations")
        print("  - GET /api/vfs/datasets - List all datasets")
        print("  - GET /api/vfs/datasets/{id} - Get dataset metadata")
        print("  - POST /api/vfs/datasets/{id}/convert_to_car - Convert to CAR")

        print("\n📊 Vector Index Endpoints:")
        print("  - POST /api/vector/operation - General vector operations")
        print("  - GET /api/vector/collections - List collections")
        print("  - POST /api/vector/search - Vector similarity search")
        print("  - POST /api/vector/collections/{id}/export_car - Export to CAR")

        print("\n🕸️ Knowledge Graph Endpoints:")
        print("  - POST /api/kg/operation - General KG operations")
        print("  - GET /api/kg/entities - List entities")
        print("  - GET /api/kg/entities/{id} - Get entity details")
        print("  - POST /api/kg/search - Search entities")
        print("  - POST /api/kg/export_car - Export KG to CAR")

        print("\n📌 Pinset Management Endpoints:")
        print("  - POST /api/pinset/operation - General pinset operations")
        print("  - GET /api/pinset/pins - List all pins")
        print("  - GET /api/pinset/pins/{cid} - Get pin info")
        print("  - POST /api/pinset/pins/{cid}/replicate - Replicate pin")
        print("  - GET /api/pinset/backends - Track storage backends")

        print("\n🛡️ Replication Management Endpoints:")
        print("  - POST /api/replication/operation - General replication operations")
        print("  - GET /api/replication/status - Get replication status")
        print("  - GET/POST /api/replication/settings - Manage replication settings")
        print("  - POST /api/replication/pins/{cid}/replicate - Replicate specific pin")
        print("  - GET /api/replication/backends - Get backend capabilities")

        print("\n💾 Backup & Restore Endpoints:")
        print("  - POST /api/backup/operation - General backup operations")
        print("  - POST /api/backup/{backend}/export - Export backend pins")
        print("  - POST /api/backup/{backend}/import - Import backup to backend")
        print("  - GET /api/backup/{backend}/list - List available backups")
        print("  - POST /api/backup/verify - Verify backup integrity")

        print("\n🎯 Key Features Achieved:")
        print("✓ Virtual filesystem metadata in columnar IPLD format")
        print("✓ Vector indexes stored as parquet files")
        print("✓ Knowledge graphs in columnar format")
        print("✓ Pinset tracking across storage backends")
        print("✓ Parquet to CAR archive conversion")
        print("✓ IPFS CID access to all columnar data")
        print("✓ Dashboard interface for all VFS operations")
        print("✓ Content-addressed distribution via CAR archives")
        print("✓ Comprehensive replication management system")
        print("✓ Cross-backend pin replication with configurable settings")
        print("✓ Data loss protection with backup/restore capabilities")
        print("✓ Real-time replication health monitoring")
        print("✓ Automated replication based on target replica counts")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Some components may not be available")
    except Exception as e:
        logger.error(f"Demo error: {e}")
        print(f"❌ Demo failed: {e}")


def show_example_usage():
    """Show example API usage patterns."""

    print("\n" + "=" * 60)
    print("📋 EXAMPLE API USAGE PATTERNS")
    print("=" * 60)

    examples = {
        "List VFS Datasets": {
            "method": "GET",
            "url": "/api/vfs/datasets",
            "description": "Get all virtual filesystem datasets",
        },
        "Get Dataset with CAR Info": {
            "method": "GET",
            "url": "/api/vfs/datasets/QmExample123?include_car=true",
            "description": "Get dataset metadata including CAR archive info",
        },
        "Convert Dataset to CAR": {
            "method": "POST",
            "url": "/api/vfs/datasets/QmExample123/convert_to_car",
            "body": {"include_vector_index": True, "include_knowledge_graph": True},
            "description": "Convert parquet dataset to IPLD CAR archive",
        },
        "Vector Similarity Search": {
            "method": "POST",
            "url": "/api/vector/search",
            "body": {"query_vector": [0.1, 0.2, 0.3, 0.4, 0.5], "top_k": 10},
            "description": "Find similar vectors using cosine similarity",
        },
        "Search Knowledge Graph": {
            "method": "POST",
            "url": "/api/kg/search",
            "body": {"query": "file system metadata"},
            "description": "Semantic search across KG entities",
        },
        "Replicate Pin to CAR Archive": {
            "method": "POST",
            "url": "/api/pinset/pins/QmPinExample456/replicate",
            "body": {"target_backend": "car_archive"},
            "description": "Create CAR archive for pin distribution",
        },
        "Configure Replication Settings": {
            "method": "POST",
            "url": "/api/replication/settings",
            "body": {
                "min_replicas": 2,
                "target_replicas": 3,
                "max_replicas": 5,
                "max_size_gb": 100.0,
                "auto_replication": True,
                "replication_strategy": "balanced",
            },
            "description": "Update replication management settings",
        },
        "Get Replication Status": {
            "method": "GET",
            "url": "/api/replication/status",
            "description": "Get overall replication health and statistics",
        },
        "Replicate Pin to Multiple Backends": {
            "method": "POST",
            "url": "/api/replication/pins/QmExample789/replicate",
            "body": {
                "target_backends": ["ipfs_cluster", "storacha", "car_archive"],
                "force": False,
            },
            "description": "Replicate pin to specific storage backends",
        },
        "Export Backend Backup": {
            "method": "POST",
            "url": "/api/backup/ipfs/export",
            "body": {
                "backup_path": "/tmp/ipfs_backup.json",
                "include_metadata": True,
                "compress": True,
            },
            "description": "Export all pins from IPFS backend to backup file",
        },
        "Import Backend Backup": {
            "method": "POST",
            "url": "/api/backup/ipfs_cluster/import",
            "body": {"backup_path": "/tmp/ipfs_backup.json", "include_metadata": True},
            "description": "Import pins from backup to IPFS Cluster backend",
        },
        "Verify Backup Integrity": {
            "method": "POST",
            "url": "/api/backup/verify",
            "body": {"backup_path": "/tmp/ipfs_backup.json"},
            "description": "Verify backup file integrity and metadata",
        },
    }

    for title, example in examples.items():
        print(f"\n🔧 {title}")
        print(f"   {example['method']} {example['url']}")
        if "body" in example:
            print(f"   Body: {json.dumps(example['body'], indent=8)}")
        print(f"   → {example['description']}")


if __name__ == "__main__":
    print("🚀 Starting VFS Dashboard Integration Demo\n")

    # Run the main demo
    anyio.run(demo_vfs_dashboard_integration)

    # Show example usage patterns
    show_example_usage()

    print(f"\n✅ Demo completed at {datetime.now().isoformat()}")
    print("\n🎉 VFS Dashboard Integration with Replication Management Complete!")
    print("Your virtual filesystem metadata, vector indexes, knowledge graphs,")
    print("and pinsets are now available via the dashboard with full columnar")
    print("IPLD support, parquet files, CAR archive distribution, and")
    print("comprehensive replication management with data loss protection! 🌟")
