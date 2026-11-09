#!/usr/bin/env python3
"""
Improved Bucket CLI - Abstract Bucket Interface

This provides a clean, abstracted bucket interface that hides storage backend
implementation details and focuses on pins and virtual filesystem features.

Key Design Principles:
- Storage backends are managed by the daemon transparently
- Users work with buckets, pins, and virtual paths
- Content addressing is handled automatically
- Backend selection is policy-driven, not user-specified
"""

import argparse
import anyio
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import the unified bucket interface
try:
    from ipfs_kit_py.unified_bucket_interface import UnifiedBucketInterface, BackendType
    from ipfs_kit_py.bucket_vfs_manager import BucketType
    UNIFIED_AVAILABLE = True
except ImportError:
    logger.warning("Unified bucket interface not available")
    UNIFIED_AVAILABLE = False


class ImprovedBucketCLI:
    """
    Improved bucket CLI that abstracts away storage backend details.
    
    Users work with:
    - Buckets (logical containers)
    - Pins (content-addressed data)
    - Virtual paths (filesystem-like organization)
    
    The daemon handles:
    - Backend selection and management
    - Content addressing and hashing
    - Storage optimization and replication
    """
    
    def __init__(self):
        self.interface = None
        
    async def initialize(self):
        """Initialize the bucket interface."""
        if UNIFIED_AVAILABLE:
            self.interface = UnifiedBucketInterface()
            await self.interface.initialize()
            logger.info("✅ Bucket interface initialized")
        else:
            logger.error("❌ Unified bucket interface not available")
            return False
        return True
    
    def _string_to_bucket_type(self, bucket_type_str: str) -> 'BucketType':
        """Convert string bucket type to BucketType enum."""
        if not UNIFIED_AVAILABLE:
            return bucket_type_str  # Return string if enums not available
            
        type_mapping = {
            "general": BucketType.GENERAL,
            "dataset": BucketType.DATASET,
            "knowledge": BucketType.KNOWLEDGE,
            "media": BucketType.MEDIA,
            "archive": BucketType.ARCHIVE,
            "temp": BucketType.TEMP
        }
        
        return type_mapping.get(bucket_type_str.lower(), BucketType.GENERAL)
    
    async def list_buckets(self, filter_type: Optional[str] = None) -> bool:
        """List all available buckets."""
        try:
            if not self.interface:
                print("❌ Interface not initialized")
                return False
            
            # Get all buckets from registry
            buckets = []
            for bucket_id, bucket_info in self.interface.bucket_registry.items():
                bucket_data = {
                    'bucket_name': bucket_info.get('bucket_name', 'unnamed'),
                    'bucket_type': bucket_info.get('bucket_type', 'general'),
                    'backend': bucket_info.get('backend', 'unknown'),
                    'created_at': bucket_info.get('created_at', 'unknown')
                }
                
                # Get statistics
                try:
                    stats = await self.interface._get_bucket_statistics(
                        BackendType(bucket_info['backend']),
                        bucket_info['bucket_name']
                    )
                    bucket_data['statistics'] = stats
                except Exception:
                    bucket_data['statistics'] = {'pin_count': 0, 'total_size': 0}
                
                buckets.append(bucket_data)
            
            if not buckets:
                print("📦 No buckets found")
                return True
            
            print(f"📦 Found {len(buckets)} bucket(s):")
            print()
            
            for bucket in buckets:
                bucket_name = bucket.get('bucket_name', 'unnamed')
                bucket_type = bucket.get('bucket_type', 'general')
                backend = bucket.get('backend', 'unknown')
                pin_count = bucket.get('statistics', {}).get('pin_count', 0)
                total_size = bucket.get('statistics', {}).get('total_size', 0)
                
                # Format size
                if total_size < 1024:
                    size_str = f"{total_size} B"
                elif total_size < 1024 * 1024:
                    size_str = f"{total_size / 1024:.1f} KB"
                elif total_size < 1024 * 1024 * 1024:
                    size_str = f"{total_size / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
                
                # Filter by type if specified
                if filter_type and bucket_type != filter_type:
                    continue
                
                print(f"  📁 {bucket_name} ({bucket_type})")
                print(f"     🔧 Backend: {backend} (managed by daemon)")
                print(f"     📌 {pin_count} pins | 💾 {size_str}")
                print()
            
            return True
            
        except Exception as e:
            print(f"❌ Error listing buckets: {e}")
            return False
    
    async def create_bucket(
        self, 
        name: str, 
        bucket_type: str = "general",
        description: Optional[str] = None
    ) -> bool:
        """Create a new bucket."""
        try:
            if not self.interface:
                print("❌ Interface not initialized")
                return False
            
            # The daemon will choose the optimal backend based on:
            # - Bucket type (dataset -> parquet, media -> s3, etc.)
            # - Current load and availability
            # - User preferences and policies
            backend = self._choose_optimal_backend(bucket_type)
            
            # Convert string bucket type to enum
            bucket_type_enum = self._string_to_bucket_type(bucket_type)
            
            metadata = {"description": description} if description else {}
            
            result = await self.interface.create_backend_bucket(
                backend=backend,
                bucket_name=name,
                bucket_type=bucket_type_enum,
                metadata=metadata
            )
            
            if result.get('success'):
                print(f"✅ Created bucket '{name}' ({bucket_type})")
                print(f"   📁 Storage managed by daemon")
                if description:
                    print(f"   📝 {description}")
                return True
            else:
                print(f"❌ Failed to create bucket: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Error creating bucket: {e}")
            return False
    
    async def add_file(
        self,
        bucket_name: str,
        file_path: str,
        virtual_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a file to a bucket (content addressing handled automatically)."""
        try:
            if not self.interface:
                print("❌ Interface not initialized")
                return False
            
            # Check if file exists
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                return False
            
            # Read file content
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Generate content hash automatically
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Use filename as virtual path if not specified
            if not virtual_path:
                virtual_path = os.path.basename(file_path)
            
            # Find the bucket and its backend (abstracted from user)
            bucket_info = await self._find_bucket(bucket_name)
            if not bucket_info:
                print(f"❌ Bucket '{bucket_name}' not found")
                return False
            
            backend = BackendType(bucket_info['backend'])
            
            result = await self.interface.add_content_pin(
                backend=backend,
                bucket_name=bucket_name,
                content_hash=content_hash,
                file_path=virtual_path,
                content=content,
                metadata=metadata or {}
            )
            
            if result.get('success'):
                print(f"✅ Added file to bucket '{bucket_name}'")
                print(f"   📄 Virtual path: {virtual_path}")
                print(f"   🔗 Content hash: {content_hash[:16]}...")
                print(f"   💾 Size: {len(content)} bytes")
                return True
            else:
                print(f"❌ Failed to add file: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Error adding file: {e}")
            return False
    
    async def list_files(self, bucket_name: str) -> bool:
        """List files in a bucket."""
        try:
            if not self.interface:
                print("❌ Interface not initialized")
                return False
            
            bucket_info = await self._find_bucket(bucket_name)
            if not bucket_info:
                print(f"❌ Bucket '{bucket_name}' not found")
                return False
            
            # Get VFS composition for the bucket
            result = await self.interface.get_vfs_composition(
                backend_filter=[BackendType(bucket_info['backend'])],
                bucket_filter=bucket_name
            )
            
            if not result.get('success'):
                print(f"❌ Failed to list files: {result.get('error', 'Unknown error')}")
                return False
            
            composition = result.get('data', {})
            bucket_data = composition.get('backend_composition', {}).get(bucket_info['backend'], {})
            bucket_files = bucket_data.get('buckets', {}).get(bucket_name, {}).get('files', [])
            
            if not bucket_files:
                print(f"📦 Bucket '{bucket_name}' is empty")
                return True
            
            print(f"📦 Files in bucket '{bucket_name}':")
            print()
            
            for file_info in bucket_files:
                virtual_path = file_info.get('file_path', 'unknown')
                size = file_info.get('size', 0)
                content_hash = file_info.get('content_hash', 'unknown')
                created_at = file_info.get('created_at', 'unknown')
                
                # Format size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                
                print(f"  📄 {virtual_path}")
                print(f"     🔗 {content_hash[:16]}... | 💾 {size_str}")
                print(f"     🕒 {created_at}")
                print()
            
            return True
            
        except Exception as e:
            print(f"❌ Error listing files: {e}")
            return False
    
    async def remove_file(self, bucket_name: str, virtual_path: str) -> bool:
        """Remove a file from a bucket."""
        try:
            # This would implement file removal
            # For now, just show what would happen
            print(f"🗑️  Would remove '{virtual_path}' from bucket '{bucket_name}'")
            print("   (Implementation pending)")
            return True
            
        except Exception as e:
            print(f"❌ Error removing file: {e}")
            return False
    
    async def show_bucket_info(self, bucket_name: str) -> bool:
        """Show detailed information about a bucket."""
        try:
            if not self.interface:
                print("❌ Interface not initialized")
                return False
            
            bucket_info = await self._find_bucket(bucket_name)
            if not bucket_info:
                print(f"❌ Bucket '{bucket_name}' not found")
                return False
            
            print(f"📦 Bucket Information: {bucket_name}")
            print("=" * 50)
            print(f"Type: {bucket_info.get('bucket_type', 'unknown')}")
            print(f"Storage Backend: {bucket_info.get('backend', 'unknown')} (managed by daemon)")
            print(f"Created: {bucket_info.get('created_at', 'unknown')}")
            
            stats = bucket_info.get('statistics', {})
            pin_count = stats.get('pin_count', 0)
            total_size = stats.get('total_size', 0)
            
            print(f"Pins: {pin_count}")
            print(f"Total Size: {total_size} bytes")
            
            metadata = bucket_info.get('metadata', {})
            if metadata:
                print("\nMetadata:")
                for key, value in metadata.items():
                    print(f"  {key}: {value}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error showing bucket info: {e}")
            return False
    
    def _choose_optimal_backend(self, bucket_type: str) -> BackendType:
        """Choose optimal backend based on bucket type (daemon-managed decision)."""
        # This logic would normally be in the daemon, but for now we implement simple rules
        type_backend_map = {
            'dataset': BackendType.PARQUET,
            'media': BackendType.S3,
            'archive': BackendType.SSHFS,
            'knowledge': BackendType.ARROW,
            'temp': BackendType.PARQUET,
            'general': BackendType.PARQUET
        }
        return type_backend_map.get(bucket_type, BackendType.PARQUET)
    
    async def _find_bucket(self, bucket_name: str) -> Optional[Dict[str, Any]]:
        """Find bucket information by name."""
        try:
            print(f"DEBUG: Looking for bucket '{bucket_name}'")
            print(f"DEBUG: Registry has {len(self.interface.bucket_registry)} buckets")
            for bucket_id, bucket_info in self.interface.bucket_registry.items():
                print(f"DEBUG: Checking bucket_id '{bucket_id}' with name '{bucket_info.get('bucket_name')}'")
                if bucket_info.get('bucket_name') == bucket_name:
                    # Add statistics
                    try:
                        stats = await self.interface._get_bucket_statistics(
                            BackendType(bucket_info['backend']),
                            bucket_info['bucket_name']
                        )
                        bucket_info['statistics'] = stats
                    except Exception:
                        bucket_info['statistics'] = {'pin_count': 0, 'total_size': 0}
                    print(f"DEBUG: Found bucket!")
                    return bucket_info
            print(f"DEBUG: Bucket '{bucket_name}' not found")
            return None
            
        except Exception as e:
            print(f"DEBUG: Exception in _find_bucket: {e}")
            return None


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Improved Bucket Interface - Abstract bucket management for IPFS Kit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all buckets
  python improved_bucket_cli.py list
  
  # Create a dataset bucket
  python improved_bucket_cli.py create ml-models dataset --description "Machine learning models"
  
  # Add a file to a bucket
  python improved_bucket_cli.py add my-bucket /path/to/file.txt
  
  # List files in a bucket
  python improved_bucket_cli.py files my-bucket
  
  # Show bucket information
  python improved_bucket_cli.py info my-bucket

The bucket interface abstracts away storage backend details.
Storage backends are managed by the daemon based on bucket type and policies.
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List buckets
    list_parser = subparsers.add_parser('list', help='List all buckets')
    list_parser.add_argument('--type', help='Filter by bucket type')
    
    # Create bucket
    create_parser = subparsers.add_parser('create', help='Create a new bucket')
    create_parser.add_argument('name', help='Bucket name')
    create_parser.add_argument('type', 
                             choices=['general', 'dataset', 'knowledge', 'media', 'archive', 'temp'],
                             default='general', nargs='?',
                             help='Bucket type (determines optimal storage backend)')
    create_parser.add_argument('--description', help='Bucket description')
    
    # Add file to bucket
    add_parser = subparsers.add_parser('add', help='Add a file to a bucket')
    add_parser.add_argument('bucket', help='Bucket name')
    add_parser.add_argument('file', help='Path to file to add')
    add_parser.add_argument('--virtual-path', help='Virtual path within bucket (defaults to filename)')
    add_parser.add_argument('--metadata', help='JSON metadata for the file')
    
    # List files in bucket
    files_parser = subparsers.add_parser('files', help='List files in a bucket')
    files_parser.add_argument('bucket', help='Bucket name')
    
    # Remove file from bucket
    remove_parser = subparsers.add_parser('remove', help='Remove a file from a bucket')
    remove_parser.add_argument('bucket', help='Bucket name')
    remove_parser.add_argument('path', help='Virtual path of file to remove')
    
    # Show bucket info
    info_parser = subparsers.add_parser('info', help='Show detailed bucket information')
    info_parser.add_argument('bucket', help='Bucket name')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize CLI
    cli = ImprovedBucketCLI()
    if not await cli.initialize():
        return 1
    
    # Execute command
    try:
        if args.command == 'list':
            success = await cli.list_buckets(args.type)
        elif args.command == 'create':
            success = await cli.create_bucket(args.name, args.type, args.description)
        elif args.command == 'add':
            metadata = json.loads(args.metadata) if args.metadata else None
            success = await cli.add_file(args.bucket, args.file, args.virtual_path, metadata)
        elif args.command == 'files':
            success = await cli.list_files(args.bucket)
        elif args.command == 'remove':
            success = await cli.remove_file(args.bucket, args.path)
        elif args.command == 'info':
            success = await cli.show_bucket_info(args.bucket)
        else:
            print(f"❌ Unknown command: {args.command}")
            return 1
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(anyio.run(main))
