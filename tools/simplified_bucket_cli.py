#!/usr/bin/env python3
"""
Simplified Bucket CLI

CLI interface for the new simplified bucket architecture.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    # Try direct import first
    from ipfs_kit_py.simplified_bucket_manager import get_global_simplified_bucket_manager
    SIMPLIFIED_BUCKET_AVAILABLE = True
except ImportError:
    try:
        # Try with path manipulation
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ipfs_kit_py.simplified_bucket_manager import get_global_simplified_bucket_manager
        SIMPLIFIED_BUCKET_AVAILABLE = True
    except ImportError as e:
        print(f"Warning: Simplified bucket system not available: {e}")
        SIMPLIFIED_BUCKET_AVAILABLE = False

# Migration tool is optional
try:
    from tools.bucket_migration_tool import BucketMigrationTool
    MIGRATION_AVAILABLE = True
except ImportError:
    MIGRATION_AVAILABLE = False


class SimplifiedBucketCLI:
    """CLI for simplified bucket management."""
    
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = base_path
        if SIMPLIFIED_BUCKET_AVAILABLE:
            self.manager = get_global_simplified_bucket_manager(base_path=base_path)
        else:
            self.manager = None
    
    async def create_bucket(self, bucket_name: str, bucket_type: str = "general", vfs_structure: str = "hybrid"):
        """Create a new bucket."""
        if not self.manager:
            print("Error: Simplified bucket manager not available")
            return
        
        result = await self.manager.create_bucket(
            bucket_name=bucket_name,
            bucket_type=bucket_type, 
            vfs_structure=vfs_structure
        )
        
        if result["success"]:
            print(f"✓ Created bucket '{bucket_name}'")
            print(f"  Type: {bucket_type}")
            print(f"  VFS Structure: {vfs_structure}")
            print(f"  Config: {result['data']['config_file']}")
            print(f"  VFS Index: {result['data']['vfs_index']}")
        else:
            print(f"✗ Failed to create bucket: {result['error']}")
    
    async def list_buckets(self):
        """List all buckets."""
        if not self.manager:
            print("Error: Simplified bucket manager not available")
            return
        
        result = await self.manager.list_buckets()
        
        if result["success"]:
            buckets = result["data"]["buckets"]
            if not buckets:
                print("No buckets found")
                return
            
            print(f"Found {len(buckets)} bucket(s):")
            print()
            
            for bucket in buckets:
                print(f"📦 {bucket['name']}")
                print(f"   Type: {bucket['type']}")
                print(f"   VFS: {bucket['vfs_structure']}")
                print(f"   Files: {bucket['file_count']}")
                print(f"   Size: {self._format_size(bucket['total_size'])}")
                print(f"   Created: {bucket['created_at'][:19]}")
                if bucket.get('vfs_index_cid'):
                    print(f"   VFS CID: {bucket['vfs_index_cid']}")
                if bucket.get('root_cid'):
                    print(f"   Root CID: {bucket['root_cid']}")
                print()
        else:
            print(f"✗ Failed to list buckets: {result['error']}")
    
    async def add_file(self, bucket_name: str, file_path: str, cid: str, size: int, mime_type: str = ""):
        """Add a file to a bucket."""
        if not self.manager:
            print("Error: Simplified bucket manager not available")
            return
        
        result = await self.manager.add_file_to_bucket(
            bucket_name=bucket_name,
            file_path=file_path,
            cid=cid,
            size=size,
            mime_type=mime_type
        )
        
        if result["success"]:
            print(f"✓ Added file to bucket '{bucket_name}'")
            print(f"  Path: {file_path}")
            print(f"  CID: {cid}")
            print(f"  Size: {self._format_size(size)}")
            print(f"  Total files: {result['data']['total_files']}")
        else:
            print(f"✗ Failed to add file: {result['error']}")
    
    async def show_bucket_files(self, bucket_name: str):
        """Show files in a bucket."""
        if not self.manager:
            print("Error: Simplified bucket manager not available")
            return
        
        result = await self.manager.get_bucket_files(bucket_name)
        
        if result["success"]:
            files = result["data"]["files"]
            if not files:
                print(f"No files in bucket '{bucket_name}'")
                return
            
            print(f"Files in bucket '{bucket_name}' ({len(files)} files):")
            print()
            
            for file_info in files:
                print(f"📄 {file_info['path']}")
                print(f"   CID: {file_info['cid']}")
                print(f"   Size: {self._format_size(file_info['size'])}")
                print(f"   Type: {file_info.get('mime_type', 'unknown')}")
                print(f"   Modified: {file_info.get('modified_at', 'unknown')[:19]}")
                if file_info.get('attributes'):
                    print(f"   Attributes: {file_info['attributes']}")
                print()
        else:
            print(f"✗ Failed to get bucket files: {result['error']}")
    
    async def delete_bucket(self, bucket_name: str, force: bool = False):
        """Delete a bucket."""
        if not self.manager:
            print("Error: Simplified bucket manager not available")
            return
        
        result = await self.manager.delete_bucket(bucket_name, force=force)
        
        if result["success"]:
            print(f"✓ Deleted bucket '{bucket_name}'")
        else:
            print(f"✗ Failed to delete bucket: {result['error']}")
    
    async def migrate_buckets(self, dry_run: bool = False, analyze_only: bool = False):
        """Migrate buckets from old structure."""
        if not MIGRATION_AVAILABLE:
            print("Error: Migration tool not available")
            return
        
        migration_tool = BucketMigrationTool(base_path=self.base_path)
        
        if analyze_only:
            print("=== Migration Analysis ===")
            analysis = await migration_tool.analyze_migration()
            print(json.dumps(analysis, indent=2))
        else:
            print(f"=== Bucket Migration (dry_run={dry_run}) ===")
            results = await migration_tool.migrate_buckets(dry_run=dry_run)
            print(json.dumps(results, indent=2))
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"


async def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simplified Bucket CLI")
    parser.add_argument("--base-path", help="Base path for IPFS Kit (default: ~/.ipfs_kit)")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create bucket command
    create_parser = subparsers.add_parser("create", help="Create a new bucket")
    create_parser.add_argument("bucket_name", help="Name of the bucket")
    create_parser.add_argument("--type", default="general", 
                             choices=["general", "dataset", "knowledge", "media", "archive", "temp"],
                             help="Bucket type")
    create_parser.add_argument("--vfs-structure", default="hybrid",
                             choices=["unixfs", "graph", "vector", "hybrid"],
                             help="VFS structure type")
    
    # List buckets command
    list_parser = subparsers.add_parser("list", help="List all buckets")
    
    # Add file command
    add_parser = subparsers.add_parser("add-file", help="Add file to bucket")
    add_parser.add_argument("bucket_name", help="Bucket name")
    add_parser.add_argument("file_path", help="Virtual file path")
    add_parser.add_argument("cid", help="IPFS CID")
    add_parser.add_argument("size", type=int, help="File size in bytes")
    add_parser.add_argument("--mime-type", default="", help="MIME type")
    
    # Show files command
    files_parser = subparsers.add_parser("files", help="Show files in bucket")
    files_parser.add_argument("bucket_name", help="Bucket name")
    
    # Delete bucket command
    delete_parser = subparsers.add_parser("delete", help="Delete a bucket")
    delete_parser.add_argument("bucket_name", help="Bucket name")
    delete_parser.add_argument("--force", action="store_true", help="Force delete even if files exist")
    
    # Migration commands
    migrate_parser = subparsers.add_parser("migrate", help="Migrate from old bucket structure")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Analyze without making changes")
    migrate_parser.add_argument("--analyze", action="store_true", help="Analyze current structure only")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = SimplifiedBucketCLI(base_path=args.base_path)
    
    try:
        if args.command == "create":
            await cli.create_bucket(args.bucket_name, args.type, args.vfs_structure)
        
        elif args.command == "list":
            await cli.list_buckets()
        
        elif args.command == "add-file":
            await cli.add_file(args.bucket_name, args.file_path, args.cid, args.size, args.mime_type)
        
        elif args.command == "files":
            await cli.show_bucket_files(args.bucket_name)
        
        elif args.command == "delete":
            await cli.delete_bucket(args.bucket_name, args.force)
        
        elif args.command == "migrate":
            await cli.migrate_buckets(dry_run=args.dry_run, analyze_only=args.analyze)
        
        else:
            print(f"Unknown command: {args.command}")
    
    except KeyboardInterrupt:
        print("\nOperation cancelled")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
