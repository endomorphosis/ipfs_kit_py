#!/usr/bin/env python3
"""
Demo: Enhanced Parquet Metadata with Git VFS and New Backends

This script demonstrates the updated parquet metadata functionality that includes:
1. Git VFS translation metadata tracking
2. Enhanced backend support (SSHFS, FTP)
3. VFS snapshots with content addressing
4. Backend health monitoring with new fields

Usage:
    python3 demo_enhanced_parquet_metadata.py

Features Demonstrated:
- Reading enhanced pin data with Git VFS fields
- Backend health metadata for new backends
- VFS snapshot tracking
- Git VFS translation status
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ipfs_kit_py.parquet_data_reader import ParquetDataReader
    from ipfs_kit_py.mcp.storage_types import StorageBackendType
    # Skip model imports for demo - just demonstrate the concepts
    MODELS_AVAILABLE = False
except ImportError as e:
    print(f"ℹ️ Some imports not available, running concept demo: {e}")
    
    # Create minimal classes for demo
    class ParquetDataReader:
        def __init__(self):
            pass
    
    class StorageBackendType:
        IPFS = "ipfs"
        S3 = "s3"
        HUGGINGFACE = "huggingface"
        STORACHA = "storacha"
        GDRIVE = "gdrive"
        LOTUS = "lotus"
        SYNAPSE = "synapse"
        SSHFS = "sshfs"
        FTP = "ftp"
        
        def __iter__(self):
            return iter([self.IPFS, self.S3, self.HUGGINGFACE, self.STORACHA, 
                        self.GDRIVE, self.LOTUS, self.SYNAPSE, self.SSHFS, self.FTP])
    
    MODELS_AVAILABLE = False


def demo_enhanced_pin_metadata():
    """Demonstrate enhanced pin metadata with Git VFS fields."""
    print("\n🔍 Enhanced Pin Metadata Demo")
    print("=" * 50)
    
    reader = ParquetDataReader()
    
    # Create sample enhanced pin data
    sample_pins = [
        {
            'cid': 'QmY1Q2YxKXR9Zz8qM4c8N5k2z8v3u1L4t6h9q3w2e5r7t',
            'name': 'enhanced_document.pdf',
            'pin_type': 'recursive',
            'timestamp': datetime.now().timestamp(),
            'size_bytes': 2048000,
            'vfs_path': '/vfs/git_repos/my_project/docs/document.pdf',
            'mount_point': '/vfs/git_repos',
            'access_count': 5,
            'storage_tiers': ['ipfs', 'sshfs', 's3'],
            'primary_tier': 'ipfs',
            'replication_factor': 2,
            'content_hash': 'blake3:a1b2c3d4e5f6...',
            'integrity_status': 'verified',
            
            # Git VFS translation metadata
            'git_vfs_enabled': True,
            'git_repository_url': 'https://github.com/user/my_project.git',
            'git_commit_hash': 'abc123def456...',
            'git_branch': 'main',
            'vfs_snapshot_id': 'snap_2024_001',
            'vfs_snapshot_timestamp': datetime.now().isoformat(),
            'git_vfs_translation_status': 'synced',
            'content_addressing_type': 'blake3',
            
            # New backend support
            'backend_types': ['ipfs', 'sshfs', 's3'],
            'sshfs_backend_active': True,
            'ftp_backend_active': False,
            'backend_health_status': {
                'ipfs': 'healthy',
                'sshfs': 'healthy',
                's3': 'warning'
            },
            'backend_last_sync': {
                'ipfs': datetime.now().isoformat(),
                'sshfs': datetime.now().isoformat(),
                's3': '2024-01-15T10:30:00Z'
            },
            
            # Enhanced metadata
            'remote_file_path': '/home/user/projects/my_project/docs/document.pdf',
            'sync_metadata': {
                'last_full_sync': datetime.now().isoformat(),
                'incremental_syncs': 3,
                'conflicts_resolved': 0
            },
            'translation_metadata': {
                'git_to_vfs_mappings': 15,
                'vfs_to_git_mappings': 15,
                'metadata_version': '2.0'
            }
        }
    ]
    
    # Display enhanced metadata
    for pin in sample_pins:
        print(f"\n📌 Pin: {pin['name']}")
        print(f"   CID: {pin['cid']}")
        print(f"   VFS Path: {pin['vfs_path']}")
        print(f"   Storage Tiers: {', '.join(pin['storage_tiers'])}")
        print(f"   Git VFS Enabled: {pin['git_vfs_enabled']}")
        print(f"   Repository: {pin['git_repository_url']}")
        print(f"   Commit: {pin['git_commit_hash']}")
        print(f"   Translation Status: {pin['git_vfs_translation_status']}")
        print(f"   Active Backends: SSHFS={pin['sshfs_backend_active']}, FTP={pin['ftp_backend_active']}")
        print(f"   Backend Health: {pin['backend_health_status']}")
    
    print(f"\n✅ Enhanced pin metadata structure demonstrated")


def demo_git_vfs_metadata():
    """Demonstrate Git VFS translation metadata tracking."""
    print("\n🔄 Git VFS Translation Metadata Demo")
    print("=" * 50)
    
    # Sample Git VFS metadata
    sample_git_vfs = [
        {
            'repository_path': '/home/user/projects/my_project',
            'repository_url': 'https://github.com/user/my_project.git',
            'vfs_bucket_id': 'bucket_git_my_project',
            'translation_status': 'active',
            'last_sync_timestamp': datetime.now().isoformat(),
            'commit_count': 150,
            'vfs_snapshots_count': 25,
            'content_addressing_type': 'blake3',
            'git_branch': 'main',
            'latest_commit_hash': 'abc123def456789...',
            'vfs_metadata_hash': 'blake3:xyz789abc123...',
            'translation_errors': [],
            'supported_operations': ['sync_git_to_vfs', 'sync_vfs_to_git', 'create_snapshot'],
            'backend_integrations': {
                'ipfs': True,
                'sshfs': True,
                'ftp': False,
                's3': True
            }
        }
    ]
    
    for repo in sample_git_vfs:
        print(f"\n📂 Repository: {repo['repository_path']}")
        print(f"   URL: {repo['repository_url']}")
        print(f"   VFS Bucket: {repo['vfs_bucket_id']}")
        print(f"   Translation Status: {repo['translation_status']}")
        print(f"   Commits: {repo['commit_count']}, Snapshots: {repo['vfs_snapshots_count']}")
        print(f"   Latest Commit: {repo['latest_commit_hash']}")
        print(f"   Backend Integrations:")
        for backend, enabled in repo['backend_integrations'].items():
            status = "✅" if enabled else "❌"
            print(f"     {backend}: {status}")
    
    print(f"\n✅ Git VFS translation metadata structure demonstrated")


def demo_backend_health_metadata():
    """Demonstrate enhanced backend health metadata."""
    print("\n🏥 Enhanced Backend Health Metadata Demo")
    print("=" * 50)
    
    # Sample backend health data for new backends
    sample_backends = [
        {
            'backend_type': 'sshfs',
            'backend_id': 'sshfs_remote_server',
            'is_healthy': True,
            'last_health_check': datetime.now().isoformat(),
            'connection_status': 'connected',
            'connection_latency_ms': 45,
            'active_connections': 3,
            'total_operations': 1250,
            'successful_operations': 1220,
            'failed_operations': 30,
            'error_rate_24h': 2.4,
            'avg_response_time_ms': 120,
            'storage_used_bytes': 5368709120,  # 5GB
            'storage_available_bytes': 53687091200,  # 50GB
            'remote_host': 'remote.example.com',
            'remote_port': 22,
            'connection_pool_size': 5,
            'transfer_speed_mbps': 12.5,
            'git_vfs_enabled': True,
            'git_repositories_count': 3,
            'vfs_snapshots_count': 15,
            'recent_errors': ['Connection timeout on 2024-01-15'],
            'configuration_status': {
                'authentication': 'key_based',
                'encryption': 'enabled',
                'compression': 'enabled'
            }
        },
        {
            'backend_type': 'ftp',
            'backend_id': 'ftp_backup_server',
            'is_healthy': False,
            'last_health_check': datetime.now().isoformat(),
            'connection_status': 'connection_error',
            'connection_latency_ms': 0,
            'active_connections': 0,
            'total_operations': 450,
            'successful_operations': 380,
            'failed_operations': 70,
            'error_rate_24h': 15.6,
            'avg_response_time_ms': 0,
            'storage_used_bytes': 2147483648,  # 2GB
            'storage_available_bytes': 21474836480,  # 20GB
            'remote_host': 'ftp.backup.com',
            'remote_port': 21,
            'connection_pool_size': 3,
            'transfer_speed_mbps': 0.0,
            'git_vfs_enabled': False,
            'git_repositories_count': 0,
            'vfs_snapshots_count': 0,
            'recent_errors': [
                'Authentication failed on 2024-01-15T14:30:00Z',
                'Connection refused on 2024-01-15T15:00:00Z'
            ],
            'configuration_status': {
                'authentication': 'password_based',
                'encryption': 'disabled',
                'passive_mode': 'enabled'
            }
        }
    ]
    
    for backend in sample_backends:
        health_icon = "🟢" if backend['is_healthy'] else "🔴"
        print(f"\n{health_icon} Backend: {backend['backend_type'].upper()}")
        print(f"   ID: {backend['backend_id']}")
        print(f"   Host: {backend['remote_host']}:{backend['remote_port']}")
        print(f"   Status: {backend['connection_status']}")
        print(f"   Connections: {backend['active_connections']}/{backend['connection_pool_size']}")
        print(f"   Operations: {backend['successful_operations']}/{backend['total_operations']} successful")
        print(f"   Error Rate (24h): {backend['error_rate_24h']}%")
        print(f"   Transfer Speed: {backend['transfer_speed_mbps']} Mbps")
        print(f"   Storage: {backend['storage_used_bytes'] / (1024**3):.1f}GB used")
        print(f"   Git VFS: {'✅' if backend['git_vfs_enabled'] else '❌'}")
        if backend['recent_errors']:
            print(f"   Recent Errors: {len(backend['recent_errors'])}")
            for error in backend['recent_errors'][-2:]:  # Show last 2 errors
                print(f"     - {error}")
    
    print(f"\n✅ Enhanced backend health metadata structure demonstrated")


def demo_vfs_snapshots():
    """Demonstrate VFS snapshot metadata tracking."""
    print("\n📸 VFS Snapshots Metadata Demo")
    print("=" * 50)
    
    # Sample VFS snapshot data
    sample_snapshots = [
        {
            'snapshot_id': 'snap_2024_001',
            'bucket_id': 'bucket_git_my_project',
            'created_timestamp': datetime.now().isoformat(),
            'git_commit_hash': 'abc123def456789...',
            'git_branch': 'main',
            'content_hash': 'blake3:snapshot_hash_123...',
            'file_count': 125,
            'total_size_bytes': 104857600,  # 100MB
            'snapshot_type': 'git_sync',
            'parent_snapshot_id': 'snap_2024_000',
            'backend_storage': {
                'ipfs': True,
                'sshfs': True,
                'ftp': False,
                's3': True
            },
            'metadata_changes': {
                'files_added': 5,
                'files_modified': 12,
                'files_deleted': 2
            },
            'translation_status': 'complete',
            'vfs_mount_points': ['/vfs/git_repos/my_project'],
            'content_addressing_hashes': {
                'manifest_hash': 'blake3:manifest_abc123...',
                'metadata_hash': 'blake3:metadata_def456...',
                'content_tree_hash': 'blake3:tree_ghi789...'
            }
        }
    ]
    
    for snapshot in sample_snapshots:
        print(f"\n📸 Snapshot: {snapshot['snapshot_id']}")
        print(f"   Bucket: {snapshot['bucket_id']}")
        print(f"   Created: {snapshot['created_timestamp']}")
        print(f"   Git Commit: {snapshot['git_commit_hash']}")
        print(f"   Files: {snapshot['file_count']} ({snapshot['total_size_bytes'] / (1024**2):.1f}MB)")
        print(f"   Type: {snapshot['snapshot_type']}")
        print(f"   Translation: {snapshot['translation_status']}")
        print(f"   Backend Storage:")
        for backend, stored in snapshot['backend_storage'].items():
            status = "✅" if stored else "❌"
            print(f"     {backend}: {status}")
        print(f"   Changes: +{snapshot['metadata_changes']['files_added']} ~{snapshot['metadata_changes']['files_modified']} -{snapshot['metadata_changes']['files_deleted']}")
    
    print(f"\n✅ VFS snapshots metadata structure demonstrated")


def demo_storage_backend_types():
    """Demonstrate updated storage backend types."""
    print("\n💾 Updated Storage Backend Types Demo")
    print("=" * 50)
    
    print("Available Storage Backend Types:")
    if MODELS_AVAILABLE:
        for backend_type in StorageBackendType:
            print(f"  • {backend_type.value}")
    else:
        # Demo version - list the backends
        backends = ['ipfs', 's3', 'huggingface', 'storacha', 'gdrive', 'lotus', 'synapse', 'sshfs', 'ftp']
        for backend in backends:
            print(f"  • {backend}")
    
    print(f"\n✅ Updated storage backend types include SSHFS and FTP")


def main():
    """Run all parquet metadata enhancement demos."""
    print("🚀 Enhanced Parquet Metadata Demo")
    print("=" * 60)
    print("Demonstrating new metadata fields for:")
    print("  • Git VFS translation layer")
    print("  • SSHFS and FTP backend support")
    print("  • Enhanced health monitoring")
    print("  • VFS snapshots with content addressing")
    
    try:
        demo_enhanced_pin_metadata()
        demo_git_vfs_metadata()
        demo_backend_health_metadata()
        demo_vfs_snapshots()
        demo_storage_backend_types()
        
        print(f"\n🎉 All parquet metadata enhancements demonstrated successfully!")
        print("\nKey Enhancements:")
        print("  ✅ Git VFS translation metadata tracking")
        print("  ✅ SSHFS and FTP backend integration")
        print("  ✅ Enhanced backend health monitoring")
        print("  ✅ VFS snapshots with content addressing")
        print("  ✅ Extended pin metadata with Git integration")
        print("  ✅ Backend-specific operation tracking")
        
        print(f"\n📁 Parquet files will be stored in: ~/.ipfs_kit/")
        print("  • Git VFS metadata: git_vfs/metadata/")
        print("  • Backend health: backend_health/metadata/")
        print("  • VFS snapshots: vfs_snapshots/metadata/")
        print("  • Enhanced pins: pin_metadata/parquet_storage/")
        
    except Exception as e:
        print(f"❌ Demo error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
