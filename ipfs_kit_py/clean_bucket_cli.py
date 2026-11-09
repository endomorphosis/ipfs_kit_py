#!/usr/bin/env python3
"""
Clean Bucket CLI for IPFS Kit.

This provides a simplified, working CLI for bucket operations using BucketVFSManager.
"""

import anyio
import argparse

import sys
import os
from pathlib import Path


def create_parser():
    """Create the argument parser for bucket operations."""
    parser = argparse.ArgumentParser(description='IPFS Kit Bucket Manager')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Core bucket operations
    list_parser = subparsers.add_parser('list', help='List available buckets')
    list_parser.add_argument('--detailed', action='store_true', help='Show detailed bucket information')
    
    create_parser = subparsers.add_parser('create', help='Create a new bucket')
    create_parser.add_argument('bucket_name', help='Bucket name')
    create_parser.add_argument('--bucket-type', choices=['general', 'dataset', 'knowledge', 'media', 'archive', 'temp'], 
                              default='general', help='Bucket type')
    create_parser.add_argument('--vfs-structure', choices=['unixfs', 'graph', 'vector', 'hybrid'], 
                              default='hybrid', help='VFS structure type')
    create_parser.add_argument('--metadata', help='JSON metadata for the bucket')
    
    rm_parser = subparsers.add_parser('rm', help='Remove a bucket')
    rm_parser.add_argument('bucket_name', help='Bucket name to remove')
    rm_parser.add_argument('--force', action='store_true', help='Force removal without confirmation')
    
    # File operations within buckets
    add_parser = subparsers.add_parser('add', help='Add file to bucket')
    add_parser.add_argument('bucket_name', help='Bucket name')
    add_parser.add_argument('file_path', help='Path to file to add')
    add_parser.add_argument('--virtual-path', help='Virtual path within bucket (defaults to filename)')
    add_parser.add_argument('--metadata', help='JSON metadata for the file')
    
    get_parser = subparsers.add_parser('get', help='Get file from bucket')
    get_parser.add_argument('bucket_name', help='Bucket name')
    get_parser.add_argument('virtual_path', help='Virtual path within bucket')
    get_parser.add_argument('--output', help='Output file path (defaults to original filename)')
    
    cat_parser = subparsers.add_parser('cat', help='Display file content from bucket')
    cat_parser.add_argument('bucket_name', help='Bucket name')
    cat_parser.add_argument('virtual_path', help='Virtual path within bucket')
    cat_parser.add_argument('--limit', type=int, help='Limit output to N bytes')
    
    rm_file_parser = subparsers.add_parser('rm-file', help='Remove file from bucket')
    rm_file_parser.add_argument('bucket_name', help='Bucket name')
    rm_file_parser.add_argument('virtual_path', help='Virtual path within bucket')
    
    files_parser = subparsers.add_parser('files', help='List files in bucket')
    files_parser.add_argument('bucket_name', help='Bucket name')
    files_parser.add_argument('--limit', type=int, help='Limit number of results')
    files_parser.add_argument('--prefix', help='Filter by path prefix')
    
    return parser


async def handle_list(args):
    """Handle list command."""
    try:
        from .bucket_vfs_manager import get_global_bucket_manager
        
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        result = await bucket_manager.list_buckets()
        
        if result["success"]:
            buckets = result["data"]["buckets"]
            if buckets:
                print(f"✅ Found {len(buckets)} bucket(s):")
                print()
                for bucket in buckets:
                    print(f"📁 {bucket['name']}")
                    print(f"   Type: {bucket.get('type', 'unknown')}")
                    print(f"   Structure: {bucket.get('vfs_structure', 'unknown')}")
                    print(f"   Files: {bucket.get('file_count', 0)}")
                    print(f"   Size: {bucket.get('total_size', 0)} bytes")
                    print(f"   Created: {bucket.get('created_at', 'unknown')}")
                    print()
            else:
                print("📭 No buckets found")
        else:
            print(f"❌ Failed to list buckets: {result['error']}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error listing buckets: {e}")
        return 1


async def handle_create(args):
    """Handle create command."""
    try:
        from .bucket_vfs_manager import get_global_bucket_manager, BucketType, VFSStructureType
        import json
        
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Parse metadata if provided
        metadata = {}
        if args.metadata:
            try:
                metadata = json.loads(args.metadata)
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON metadata: {e}")
                return 1
        
        # Convert string values to enums
        bucket_type = BucketType(args.bucket_type)
        vfs_structure = VFSStructureType(args.vfs_structure)
        
        result = await bucket_manager.create_bucket(
            bucket_name=args.bucket_name,
            bucket_type=bucket_type,
            vfs_structure=vfs_structure,
            metadata=metadata
        )
        
        if result["success"]:
            print(f"✅ Created bucket '{args.bucket_name}'")
            print(f"   Type: {args.bucket_type}")
            print(f"   Structure: {args.vfs_structure}")
            print(f"   Storage path: {result['data']['storage_path']}")
        else:
            print(f"❌ Failed to create bucket: {result['error']}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error creating bucket: {e}")
        return 1


async def handle_add(args):
    """Handle add file command."""
    try:
        from .bucket_vfs_manager import get_global_bucket_manager
        import json
        
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Get bucket
        bucket = await bucket_manager.get_bucket(args.bucket_name)
        if not bucket:
            print(f"❌ Bucket '{args.bucket_name}' not found")
            return 1
        
        # Determine virtual path
        virtual_path = args.virtual_path or os.path.basename(args.file_path)
        if not virtual_path.startswith('/'):
            virtual_path = '/' + virtual_path
        
        # Read file content
        try:
            with open(args.file_path, 'rb') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"❌ File not found: {args.file_path}")
            return 1
        
        # Parse metadata if provided
        metadata = {}
        if args.metadata:
            try:
                metadata = json.loads(args.metadata)
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON metadata: {e}")
                return 1
        
        result = await bucket.add_file(virtual_path, content, metadata)
        
        if result["success"]:
            print(f"✅ Added file '{virtual_path}' to bucket '{args.bucket_name}'")
            print(f"   Size: {result['data']['size']} bytes")
            if result['data'].get('cid'):
                print(f"   CID: {result['data']['cid']}")
        else:
            print(f"❌ Failed to add file: {result['error']}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error adding file: {e}")
        return 1


async def handle_get(args):
    """Handle get file command."""
    try:
        from .bucket_vfs_manager import get_global_bucket_manager
        
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Get bucket
        bucket = await bucket_manager.get_bucket(args.bucket_name)
        if not bucket:
            print(f"❌ Bucket '{args.bucket_name}' not found")
            return 1
        
        # Determine output path
        output_path = args.output or os.path.basename(args.virtual_path)
        
        result = await bucket.get_file(args.virtual_path, output_path)
        
        if result["success"]:
            print(f"✅ Retrieved file '{args.virtual_path}' from bucket '{args.bucket_name}'")
            print(f"   Saved to: {output_path}")
            print(f"   Size: {result['data']['size']} bytes")
        else:
            print(f"❌ Failed to get file: {result['error']}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error getting file: {e}")
        return 1


async def handle_cat(args):
    """Handle cat file command."""
    try:
        from .bucket_vfs_manager import get_global_bucket_manager
        
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Get bucket
        bucket = await bucket_manager.get_bucket(args.bucket_name)
        if not bucket:
            print(f"❌ Bucket '{args.bucket_name}' not found")
            return 1
        
        result = await bucket.cat_file(args.virtual_path)
        
        if result["success"]:
            content = result["data"]["content"]
            if args.limit:
                content = content[:args.limit]
            print(content, end='')  # Don't add extra newline
        else:
            print(f"❌ Failed to cat file: {result['error']}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error displaying file: {e}")
        return 1


async def handle_rm_file(args):
    """Handle remove file command."""
    try:
        from .bucket_vfs_manager import get_global_bucket_manager
        
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Get bucket
        bucket = await bucket_manager.get_bucket(args.bucket_name)
        if not bucket:
            print(f"❌ Bucket '{args.bucket_name}' not found")
            return 1
        
        result = await bucket.remove_file(args.virtual_path)
        
        if result["success"]:
            print(f"✅ Removed file '{args.virtual_path}' from bucket '{args.bucket_name}'")
        else:
            print(f"❌ Failed to remove file: {result['error']}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error removing file: {e}")
        return 1


async def handle_files(args):
    """Handle list files command."""
    try:
        from .bucket_vfs_manager import get_global_bucket_manager
        
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Get bucket
        bucket = await bucket_manager.get_bucket(args.bucket_name)
        if not bucket:
            print(f"❌ Bucket '{args.bucket_name}' not found")
            return 1
        
        result = await bucket.list_files(prefix=args.prefix or "")
        
        if result["success"]:
            files = result["data"]["files"]
            if files:
                # Apply limit if specified
                if args.limit:
                    files = files[:args.limit]
                
                print(f"📁 Files in bucket '{args.bucket_name}':")
                if args.prefix:
                    print(f"   (filtered by prefix: {args.prefix})")
                print()
                
                for file_info in files:
                    print(f"  {file_info['path']}")
                    print(f"    Size: {file_info['size']} bytes")
                    print(f"    Type: {file_info['type']}")
                    print(f"    Modified: {file_info['modified']}")
                    print()
                
                print(f"Total: {len(files)} files")
                if args.limit and len(result["data"]["files"]) > args.limit:
                    print(f"(showing first {args.limit} files)")
            else:
                print(f"📁 Bucket '{args.bucket_name}' is empty")
                if args.prefix:
                    print(f"   (no files matching prefix: {args.prefix})")
        else:
            print(f"❌ Failed to list files: {result['error']}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error listing files: {e}")
        return 1


async def handle_rm(args):
    """Handle remove bucket command."""
    try:
        from .bucket_vfs_manager import get_global_bucket_manager
        
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Confirm deletion unless --force is used
        if not args.force:
            response = input(f"Are you sure you want to delete bucket '{args.bucket_name}'? (y/N): ")
            if response.lower() not in ['y', 'yes']:
                print("❌ Operation cancelled")
                return 1
        
        result = await bucket_manager.delete_bucket(args.bucket_name, force_delete=True)
        
        if result["success"]:
            print(f"✅ Deleted bucket '{args.bucket_name}'")
        else:
            print(f"❌ Failed to delete bucket: {result['error']}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error deleting bucket: {e}")
        return 1


async def main():
    """Main async function."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Map commands to handlers
    handlers = {
        'list': handle_list,
        'create': handle_create,
        'add': handle_add,
        'get': handle_get,
        'cat': handle_cat,
        'rm-file': handle_rm_file,
        'files': handle_files,
        'rm': handle_rm,
    }
    
    handler = handlers.get(args.command)
    if not handler:
        print(f"❌ Unknown command: {args.command}")
        return 1
    
    try:
        return await handler(args)
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def sync_main():
    """Synchronous entry point."""
    try:
        return anyio.run(main)
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(sync_main())
