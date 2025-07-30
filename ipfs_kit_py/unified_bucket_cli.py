#!/usr/bin/env python3
"""
CLI Commands for Unified Bucket-Based Interface

Provides CLI access to the unified bucket interface for managing
content-addressed pins across multiple filesystem backends with
VFS and pin metadata indices.
"""

import asyncio
import json
import sys
from typing import Optional, List

from .unified_bucket_interface import (
    UnifiedBucketInterface,
    BackendType,
    BucketType,
    VFSStructureType,
    get_global_unified_bucket_interface,
    initialize_global_unified_bucket_interface
)


class UnifiedBucketCLI:
    """CLI interface for unified bucket management."""
    
    def __init__(self):
        self.interface: Optional[UnifiedBucketInterface] = None
    
    async def initialize(self):
        """Initialize the unified bucket interface."""
        self.interface = get_global_unified_bucket_interface()
        result = await self.interface.initialize()
        if not result["success"]:
            print(f"❌ Failed to initialize unified bucket interface: {result.get('error')}")
            return False
        print("✅ Unified bucket interface initialized")
        return True
    
    async def create_bucket(
        self,
        backend: str,
        bucket_name: str,
        bucket_type: str = "general",
        vfs_structure: str = "hybrid",
        metadata: Optional[str] = None
    ):
        """Create a new bucket for a specific backend."""
        try:
            backend_type = BackendType(backend.lower())
            bucket_type_enum = BucketType(bucket_type.lower())
            vfs_structure_enum = VFSStructureType(vfs_structure.lower())
            
            metadata_dict = {}
            if metadata:
                metadata_dict = json.loads(metadata)
            
            result = await self.interface.create_backend_bucket(
                backend=backend_type,
                bucket_name=bucket_name,
                bucket_type=bucket_type_enum,
                vfs_structure=vfs_structure_enum,
                metadata=metadata_dict
            )
            
            if result["success"]:
                data = result["data"]
                print(f"✅ Created bucket '{bucket_name}' for backend '{backend}'")
                print(f"   Bucket ID: {data['bucket_id']}")
                print(f"   Storage: {data['storage_path']}")
                print(f"   VFS Index: {data['vfs_index_path']}")
                print(f"   Pin Metadata: {data['pin_metadata_path']}")
            else:
                print(f"❌ Failed to create bucket: {result.get('error')}")
                return False
                
        except ValueError as e:
            print(f"❌ Invalid parameter: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid metadata JSON: {e}")
            return False
        except Exception as e:
            print(f"❌ Error creating bucket: {e}")
            return False
        
        return True
    
    async def add_pin(
        self,
        backend: str,
        bucket_name: str,
        content_hash: str,
        file_path: str,
        content_file: str,
        metadata: Optional[str] = None
    ):
        """Add a content-addressed pin to a bucket."""
        try:
            backend_type = BackendType(backend.lower())
            
            # Read content from file
            try:
                with open(content_file, 'rb') as f:
                    content = f.read()
            except FileNotFoundError:
                print(f"❌ Content file not found: {content_file}")
                return False
            
            metadata_dict = {}
            if metadata:
                metadata_dict = json.loads(metadata)
            
            result = await self.interface.add_content_pin(
                backend=backend_type,
                bucket_name=bucket_name,
                content_hash=content_hash,
                file_path=file_path,
                content=content,
                metadata=metadata_dict
            )
            
            if result["success"]:
                data = result["data"]
                print(f"✅ Added pin '{content_hash}' to bucket '{bucket_name}' on '{backend}'")
                print(f"   File path: {data['file_path']}")
                print(f"   Size: {len(content)} bytes")
                print(f"   Metadata: {data['pin_metadata_path']}")
            else:
                print(f"❌ Failed to add pin: {result.get('error')}")
                return False
                
        except ValueError as e:
            print(f"❌ Invalid parameter: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid metadata JSON: {e}")
            return False
        except Exception as e:
            print(f"❌ Error adding pin: {e}")
            return False
        
        return True
    
    async def list_buckets(self, backend: Optional[str] = None):
        """List buckets, optionally filtered by backend."""
        try:
            backend_type = None
            if backend:
                backend_type = BackendType(backend.lower())
            
            result = await self.interface.list_backend_buckets(backend=backend_type)
            
            if result["success"]:
                buckets = result["data"]["buckets"]
                total_count = result["data"]["total_count"]
                
                if total_count == 0:
                    filter_msg = f" for backend '{backend}'" if backend else ""
                    print(f"📭 No buckets found{filter_msg}")
                    return True
                
                print(f"📋 Found {total_count} bucket{'s' if total_count != 1 else ''}:")
                print("=" * 80)
                
                for bucket in buckets:
                    print(f"📁 {bucket['bucket_name']} ({bucket['backend']})")
                    print(f"   Type: {bucket['bucket_type']} | Structure: {bucket['vfs_structure']}")
                    print(f"   Pins: {bucket['pin_count']:,} | Size: {self._format_size(bucket['total_size'])}")
                    print(f"   VFS Files: {bucket['vfs_files']:,}")
                    print(f"   Created: {bucket['created_at']}")
                    if bucket['last_modified']:
                        print(f"   Modified: {bucket['last_modified']}")
                    print(f"   Storage: {bucket['storage_path']}")
                    print()
            else:
                print(f"❌ Failed to list buckets: {result.get('error')}")
                return False
                
        except ValueError as e:
            print(f"❌ Invalid backend: {e}")
            return False
        except Exception as e:
            print(f"❌ Error listing buckets: {e}")
            return False
        
        return True
    
    async def show_vfs_composition(
        self,
        backend: Optional[str] = None,
        bucket_name: Optional[str] = None
    ):
        """Show virtual filesystem composition."""
        try:
            backend_type = None
            if backend:
                backend_type = BackendType(backend.lower())
            
            result = await self.interface.get_vfs_composition(
                backend=backend_type,
                bucket_name=bucket_name
            )
            
            if result["success"]:
                composition = result["data"]
                
                print("🗂️ Virtual Filesystem Composition")
                print("=" * 50)
                print(f"Total Pins: {composition['total_pins']:,}")
                print(f"Total Size: {self._format_size(composition['total_size'])}")
                print(f"Last Updated: {composition['last_updated']}")
                print()
                
                if composition["file_types"]:
                    print("📊 File Types:")
                    for file_type, count in sorted(composition["file_types"].items()):
                        print(f"   {file_type}: {count:,}")
                    print()
                
                print("🔧 Backends:")
                for backend_name, backend_data in composition["backends"].items():
                    print(f"   📦 {backend_name.upper()}")
                    print(f"      Pins: {backend_data['total_pins']:,}")
                    print(f"      Size: {self._format_size(backend_data['total_size'])}")
                    print(f"      Buckets: {len(backend_data['buckets'])}")
                    
                    for bucket_name, bucket_data in backend_data["buckets"].items():
                        print(f"        📁 {bucket_name}")
                        print(f"           Pins: {bucket_data['pin_count']:,}")
                        print(f"           Size: {self._format_size(bucket_data['total_size'])}")
                        print(f"           VFS: {bucket_data['vfs_structure']}")
                    print()
            else:
                print(f"❌ Failed to get VFS composition: {result.get('error')}")
                return False
                
        except ValueError as e:
            print(f"❌ Invalid parameter: {e}")
            return False
        except Exception as e:
            print(f"❌ Error getting VFS composition: {e}")
            return False
        
        return True
    
    async def query_backends(self, sql_query: str, backends: Optional[str] = None):
        """Execute SQL query across backends."""
        try:
            backend_filter = None
            if backends:
                backend_list = [b.strip() for b in backends.split(",")]
                backend_filter = [BackendType(b.lower()) for b in backend_list]
            
            result = await self.interface.query_across_backends(
                sql_query=sql_query,
                backend_filter=backend_filter
            )
            
            if result["success"]:
                data = result["data"]
                columns = data["columns"]
                rows = data["rows"]
                row_count = data["row_count"]
                
                print(f"📊 Query Results ({row_count} rows)")
                print("=" * 50)
                
                if row_count == 0:
                    print("📭 No results found")
                    return True
                
                # Print column headers
                if columns:
                    header = " | ".join(f"{col:20s}" for col in columns)
                    print(header)
                    print("-" * len(header))
                
                # Print rows
                for row in rows:
                    row_str = " | ".join(f"{str(cell):20s}" for cell in row)
                    print(row_str)
                
                print()
                print(f"Query: {data['query']}")
                if data.get('backend_filter'):
                    print(f"Backends: {', '.join(data['backend_filter'])}")
            else:
                print(f"❌ Query failed: {result.get('error')}")
                return False
                
        except ValueError as e:
            print(f"❌ Invalid backend: {e}")
            return False
        except Exception as e:
            print(f"❌ Error executing query: {e}")
            return False
        
        return True
    
    async def sync_indices(
        self,
        backend: Optional[str] = None,
        bucket_name: Optional[str] = None
    ):
        """Synchronize VFS and pin metadata indices."""
        try:
            backend_type = None
            if backend:
                backend_type = BackendType(backend.lower())
            
            print("🔄 Synchronizing bucket indices...")
            
            result = await self.interface.sync_bucket_indices(
                backend=backend_type,
                bucket_name=bucket_name
            )
            
            if result["success"]:
                data = result["data"]
                total_buckets = data["total_buckets"]
                successful_syncs = data["successful_syncs"]
                failed_syncs = data["failed_syncs"]
                
                print(f"✅ Sync complete: {successful_syncs}/{total_buckets} buckets")
                
                if failed_syncs > 0:
                    print(f"⚠️  {failed_syncs} bucket(s) failed to sync")
                
                for sync_result in data["synced_buckets"]:
                    bucket_id = sync_result["bucket_id"]
                    sync_data = sync_result["sync_result"]
                    
                    if sync_data["success"]:
                        pin_count = sync_data["data"]["pin_count"]
                        total_size = sync_data["data"]["total_size"]
                        print(f"   ✅ {bucket_id}: {pin_count} pins, {self._format_size(total_size)}")
                    else:
                        print(f"   ❌ {bucket_id}: {sync_data.get('error')}")
            else:
                print(f"❌ Sync failed: {result.get('error')}")
                return False
                
        except ValueError as e:
            print(f"❌ Invalid parameter: {e}")
            return False
        except Exception as e:
            print(f"❌ Error syncing indices: {e}")
            return False
        
        return True
    
    async def show_directory_structure(self):
        """Show the .ipfs_kit directory structure."""
        if not self.interface:
            print("❌ Interface not initialized")
            return False
        
        print("📁 ~/.ipfs_kit Directory Structure")
        print("=" * 40)
        
        ipfs_kit_dir = self.interface.ipfs_kit_dir
        
        def print_directory_tree(path, prefix=""):
            """Recursively print directory tree."""
            try:
                if not path.exists():
                    return
                
                items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
                
                for i, item in enumerate(items):
                    is_last = i == len(items) - 1
                    current_prefix = "└── " if is_last else "├── "
                    
                    if item.is_dir():
                        print(f"{prefix}{current_prefix}📁 {item.name}/")
                        next_prefix = prefix + ("    " if is_last else "│   ")
                        print_directory_tree(item, next_prefix)
                    else:
                        size = item.stat().st_size
                        print(f"{prefix}{current_prefix}📄 {item.name} ({self._format_size(size)})")
            except PermissionError:
                print(f"{prefix}❌ Permission denied")
        
        print_directory_tree(ipfs_kit_dir)
        return True
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.interface:
            await self.interface.cleanup()


async def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Unified Bucket-Based Interface CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a bucket for Parquet backend
  python -m ipfs_kit_py.unified_bucket_cli create-bucket parquet my-dataset --bucket-type dataset
  
  # Add a pin to the bucket
  python -m ipfs_kit_py.unified_bucket_cli add-pin parquet my-dataset QmHash123 /data/file1.txt content.txt
  
  # List all buckets
  python -m ipfs_kit_py.unified_bucket_cli list-buckets
  
  # List buckets for specific backend
  python -m ipfs_kit_py.unified_bucket_cli list-buckets --backend s3
  
  # Show VFS composition
  python -m ipfs_kit_py.unified_bucket_cli vfs-composition
  
  # Query across backends
  python -m ipfs_kit_py.unified_bucket_cli query "SELECT * FROM vfs_parquet_my_dataset LIMIT 10"
  
  # Sync indices
  python -m ipfs_kit_py.unified_bucket_cli sync-indices
  
  # Show directory structure
  python -m ipfs_kit_py.unified_bucket_cli directory-structure
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create bucket command
    create_parser = subparsers.add_parser('create-bucket', help='Create a new bucket')
    create_parser.add_argument('backend', help='Backend type')
    create_parser.add_argument('bucket_name', help='Bucket name')
    create_parser.add_argument('--bucket-type', default='general', 
                              choices=['general', 'dataset', 'knowledge', 'media', 'archive', 'temp'],
                              help='Bucket type (default: general)')
    create_parser.add_argument('--vfs-structure', default='hybrid',
                              choices=['unixfs', 'graph', 'vector', 'hybrid'],
                              help='VFS structure type (default: hybrid)')
    create_parser.add_argument('--metadata', help='JSON metadata for the bucket')
    
    # Add pin command
    add_parser = subparsers.add_parser('add-pin', help='Add content-addressed pin to bucket')
    add_parser.add_argument('backend', help='Backend type')
    add_parser.add_argument('bucket_name', help='Bucket name')
    add_parser.add_argument('content_hash', help='Content hash (CID)')
    add_parser.add_argument('file_path', help='Virtual file path within bucket')
    add_parser.add_argument('content_file', help='Path to content file')
    add_parser.add_argument('--metadata', help='JSON metadata for the pin')
    
    # List buckets command
    list_parser = subparsers.add_parser('list-buckets', help='List buckets')
    list_parser.add_argument('--backend', help='Filter by backend type')
    
    # VFS composition command
    vfs_parser = subparsers.add_parser('vfs-composition', help='Show VFS composition')
    vfs_parser.add_argument('--backend', help='Filter by backend type')
    vfs_parser.add_argument('--bucket', help='Filter by bucket name')
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query across backends')
    query_parser.add_argument('sql_query', help='SQL query to execute')
    query_parser.add_argument('--backends', help='Comma-separated list of backends to include')
    
    # Sync indices command
    sync_parser = subparsers.add_parser('sync-indices', help='Synchronize indices')
    sync_parser.add_argument('--backend', help='Filter by backend type')
    sync_parser.add_argument('--bucket', help='Filter by bucket name')
    
    # Directory structure command
    subparsers.add_parser('directory-structure', help='Show .ipfs_kit directory structure')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    cli = UnifiedBucketCLI()
    
    try:
        # Initialize interface
        if not await cli.initialize():
            return 1
        
        # Execute command
        success = True
        
        if args.command == 'create-bucket':
            success = await cli.create_bucket(
                backend=args.backend,
                bucket_name=args.bucket_name,
                bucket_type=args.bucket_type,
                vfs_structure=args.vfs_structure,
                metadata=args.metadata
            )
        
        elif args.command == 'add-pin':
            success = await cli.add_pin(
                backend=args.backend,
                bucket_name=args.bucket_name,
                content_hash=args.content_hash,
                file_path=args.file_path,
                content_file=args.content_file,
                metadata=args.metadata
            )
        
        elif args.command == 'list-buckets':
            success = await cli.list_buckets(backend=args.backend)
        
        elif args.command == 'vfs-composition':
            success = await cli.show_vfs_composition(
                backend=args.backend,
                bucket_name=getattr(args, 'bucket', None)
            )
        
        elif args.command == 'query':
            success = await cli.query_backends(
                sql_query=args.sql_query,
                backends=args.backends
            )
        
        elif args.command == 'sync-indices':
            success = await cli.sync_indices(
                backend=args.backend,
                bucket_name=getattr(args, 'bucket', None)
            )
        
        elif args.command == 'directory-structure':
            success = await cli.show_directory_structure()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1
    finally:
        await cli.cleanup()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
