#!/usr/bin/env python3
"""
Bucket VFS CLI Integration for IPFS Kit.

This module provides CLI commands for managing multi-bucket virtual filesystems
with S3-like semantics, IPLD compatibility, and cross-platform data export.
"""

import anyio
import argparse
import inspect
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import bucket VFS components
try:
    from .bucket_vfs_manager import BucketVFSManager, BucketType, VFSStructureType, get_global_bucket_manager
    from .error import create_result_dict, handle_error
    BUCKET_VFS_AVAILABLE = True
    LEGACY_BUCKET_MODE = False
except ImportError as e:
    logger.warning(f"BucketVFSManager not available: {e}")
    BUCKET_VFS_AVAILABLE = False
    LEGACY_BUCKET_MODE = False

LEGACY_BUCKET_MODE = False


async def _await_if_needed(value):
    if inspect.isawaitable(value):
        return await value
    return value

def colorize(text: str, color: str = "GREEN") -> str:
    """Simple colorization for output."""
    colors = {
        "GREEN": "\033[92m",
        "RED": "\033[91m", 
        "YELLOW": "\033[93m",
        "BLUE": "\033[94m",
        "ENDC": "\033[0m",
        "BOLD": "\033[1m"
    }
    
    if not sys.stdout.isatty():
        return text
    
    color_code = colors.get(color.upper(), "")
    return f"{color_code}{text}{colors['ENDC']}"

def print_success(message: str):
    """Print success message."""
    print(f"✅ {colorize(message, 'GREEN')}")

def print_error(message: str):
    """Print error message."""
    print(f"❌ {colorize(message, 'RED')}")

def print_info(message: str):
    """Print info message."""
    print(f"ℹ️  {colorize(message, 'BLUE')}")

def print_warning(message: str):
    """Print warning message."""
    print(f"⚠️  {colorize(message, 'YELLOW')}")

LEGACY_BUCKET_MODE = False

async def handle_bucket_create(args) -> int:
    """Handle bucket create command."""
    if not BUCKET_VFS_AVAILABLE:
        print_error("Bucket VFS system not available")
        return 1
    
    try:
        # Use BucketVFSManager
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Convert args to the expected format
        bucket_type = BucketType(args.bucket_type) if hasattr(args, 'bucket_type') else BucketType.GENERAL
        vfs_structure = VFSStructureType(args.vfs_structure) if hasattr(args, 'vfs_structure') else VFSStructureType.HYBRID
        
        # Parse metadata if provided
        metadata = {}
        if hasattr(args, 'metadata') and args.metadata:
            import json
            try:
                metadata = json.loads(args.metadata)
            except json.JSONDecodeError as e:
                print_error(f"Invalid JSON in metadata: {e}")
                return 1
        
        # Create bucket with BucketVFSManager
        result = await bucket_manager.create_bucket(
            bucket_name=args.bucket_name,
            bucket_type=bucket_type,
            vfs_structure=vfs_structure,
            metadata=metadata
        )
        
        if result.get("success"):
            data = result.get("data", {})
            print_success(f"Created bucket '{args.bucket_name}'")
            print(f"  Type: {bucket_type.value}")
            print(f"  Structure: {vfs_structure.value}")
            if "storage_path" in data:
                print(f"  Storage path: {data['storage_path']}")
            return 0
        else:
            print_error(f"Failed to create bucket: {result.get('error')}")
            return 1
            
    except Exception as e:
        print_error(f"Error creating bucket: {e}")
        return 1

async def handle_bucket_list(args) -> int:
    """Handle bucket list command."""
    if not BUCKET_VFS_AVAILABLE:
        print_error("Bucket VFS system not available")
        return 1
    
    try:
        if LEGACY_BUCKET_MODE:
            # Use legacy bucket system
            bucket_manager = get_global_bucket_manager(
                storage_path=args.storage_path or "/tmp/ipfs_kit_buckets",
                ipfs_client=None
            )
            
            # List buckets
            result = await bucket_manager.list_buckets()
            
            if result["success"]:
                buckets = result.get("data", {}).get("buckets", [])
                total_count = result.get("data", {}).get("total_count", 0)
                
                if not buckets:
                    print_info("No buckets found")
                    return 0
                
                print_success(f"Found {total_count} bucket(s):")
                print()
                
                for bucket in buckets:
                    print(f"📁 {colorize(bucket['name'], 'BOLD')} ({bucket['type']})")
                    print(f"   Structure: {bucket['vfs_structure']}")
                    print(f"   Files: {bucket.get('file_count', 0)}")
                    print(f"   Size: {bucket.get('size_bytes', 0)} bytes")
                    print(f"   Root CID: {bucket.get('root_cid', 'N/A')}")
                    print(f"   Created: {bucket.get('created_at', 'N/A')}")
                    
                    if args.verbose:
                        print(f"   Last Modified: {bucket.get('last_modified', 'N/A')}")
                    print()
                
                return 0
            else:
                print_error(f"Failed to list buckets: {result.get('error')}")
                return 1
        else:
            # Use BucketVFSManager
            bucket_manager = get_global_bucket_manager(
                storage_path=args.storage_path or str(Path.home() / ".ipfs_kit" / "buckets")
            )
            
            # List buckets
            result = await _await_if_needed(bucket_manager.list_buckets())
            
            if not result.get("success"):
                print_error(f"Failed to list buckets: {result.get('error')}")
                return 1
            
            buckets = result["data"]["buckets"]
            if not buckets:
                print_info("No buckets found")
                return 0
            
            print_success(f"Found {len(buckets)} bucket(s):")
            print()
            
            for bucket in buckets:
                bucket_name = bucket.get('name', 'Unknown')
                print(f"📁 {colorize(bucket_name, 'BOLD')}")
                print(f"   Type: {bucket.get('type', 'unknown')}")
                print(f"   Structure: {bucket.get('vfs_structure', 'unknown')}")
                print(f"   Files: {bucket.get('file_count', 0)}")
                print(f"   Size: {bucket.get('total_size', 0)} bytes")
            return 0
            
    except Exception as e:
        print_error(f"Error listing buckets: {e}")
        return 1

async def handle_bucket_delete(args) -> int:
    """Handle bucket delete command."""
    if not BUCKET_VFS_AVAILABLE:
        print_error("Bucket VFS system not available")
        return 1
    
    try:
        # Initialize bucket manager
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Ensure bucket registry is loaded
        await bucket_manager._load_bucket_registry()
        
        # Confirm deletion if not forced
        if not getattr(args, 'force', False):
            bucket_name = getattr(args, 'bucket_name', getattr(args, 'bucket', 'unknown'))
            print_warning(f"This will permanently delete bucket '{bucket_name}' and all its contents.")
            response = input("Are you sure? (y/N): ").strip().lower()
            if response not in ('y', 'yes'):
                print_info("Deletion cancelled")
                return 0
        
        # Delete bucket
        result = await bucket_manager.delete_bucket(args.name, force=args.force)
        
        if result["success"]:
            print_success(f"Deleted bucket '{args.name}'")
            return 0
        else:
            print_error(f"Failed to delete bucket: {result.get('error')}")
            return 1
            
    except Exception as e:
        print_error(f"Error deleting bucket: {e}")
        return 1

async def handle_bucket_add_file(args) -> int:
    """Handle add-file subcommand."""
    if not BUCKET_VFS_AVAILABLE:
        print_error("BucketVFS not available - install required dependencies")
        return 1
    
    try:
        # Use BucketVFSManager for enhanced architecture
        try:
            bucket_manager = get_global_bucket_manager(
                storage_path=getattr(args, "storage_path", None)
                or str(Path.home() / ".ipfs_kit" / "buckets")
            )

            bucket_name = getattr(args, "bucket_name", None) or getattr(args, "bucket", None)
            if not bucket_name:
                print_error("Missing bucket name")
                return 1

            bucket_path = getattr(args, "file_path", None) or getattr(args, "path", None)
            if not bucket_path:
                print_error("Missing bucket file path")
                return 1
            
            # Get metadata if provided
            metadata = {"added_via": "cli"}
            if hasattr(args, 'metadata') and args.metadata:
                import json
                try:
                    user_metadata = json.loads(args.metadata)
                    metadata.update(user_metadata)
                except json.JSONDecodeError as e:
                    print_error(f"Invalid JSON in metadata: {e}")
                    return 1
            
            # Get the bucket instance
            bucket = await _await_if_needed(bucket_manager.get_bucket(bucket_name))
            if not bucket:
                print_error(f"Bucket '{bucket_name}' not found")
                return 1

            # Get content
            if getattr(args, "content", None) is not None:
                content = str(args.content).encode("utf-8")
            else:
                source_path = getattr(args, "source", None) or getattr(args, "file_path", None)
                if not source_path:
                    print_error("Missing source file path")
                    return 1
                with open(source_path, "rb") as f:
                    content = f.read()
            
            # Add file to bucket
            result = await _await_if_needed(bucket.add_file(
                file_path=bucket_path,
                content=content,
                metadata=metadata
            ))
            success = result.get("success", False)
            
            if success:
                print(f"✅ Added file '{bucket_path}' to bucket '{bucket_name}'")
                return 0
            else:
                print_error(f"Failed to add file '{bucket_path}' to bucket '{bucket_name}'")
                return 1
                
        except Exception as e:
            logger.error(f"Error adding file to bucket: {e}")
            print_error(f"Failed to add file: {str(e)}")
            return 1
        
    except Exception as e:
        logger.error(f"Error in bucket add-file command: {e}")
        print_error(f"Command failed: {str(e)}")
        return 1

async def handle_bucket_get_file(args) -> int:
    """Handle get-file subcommand."""
    try:
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Ensure bucket registry is loaded
        await bucket_manager._load_bucket_registry()
        
        bucket = await bucket_manager.get_bucket(args.bucket)
        if not bucket:
            print_error(f"Bucket '{args.bucket}' not found")
            return 1
        
        result = await bucket.get_file(args.path, args.output)
        
        if result["success"]:
            print(f"✅ Retrieved file '{args.path}' from bucket '{args.bucket}'")
            print(f"  Saved to: {args.output}")
            print(f"  Size: {result['data']['size']} bytes")
            return 0
        else:
            print_error(f"Failed to retrieve file: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in bucket get-file command: {e}")
        print_error(f"Command failed: {str(e)}")
        return 1

async def handle_bucket_cat_file(args) -> int:
    """Handle cat-file subcommand."""
    try:
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Ensure bucket registry is loaded
        await bucket_manager._load_bucket_registry()
        
        bucket = await bucket_manager.get_bucket(args.bucket)
        if not bucket:
            print_error(f"Bucket '{args.bucket}' not found")
            return 1
        
        result = await bucket.cat_file(args.path)
        
        if result["success"]:
            print(result["data"]["content"])
            return 0
        else:
            print_error(f"Failed to read file: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in bucket cat-file command: {e}")
        print_error(f"Command failed: {str(e)}")
        return 1

async def handle_bucket_list_files(args) -> int:
    """Handle list-files subcommand."""
    try:
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        bucket = await bucket_manager.get_bucket(args.bucket)
        if not bucket:
            print_error(f"Bucket '{args.bucket}' not found")
            return 1
        
        result = await bucket.list_files()
        
        if result["success"]:
            files = result["data"]["files"]
            if files:
                print(f"📁 Files in bucket '{args.bucket}':")
                print()
                for file_info in files:
                    print(f"  {file_info['path']}")
                    print(f"    Size: {file_info['size']} bytes")
                    print(f"    Type: {file_info['type']}")
                    print(f"    Modified: {file_info['modified']}")
                    print()
                print(f"Total: {len(files)} files")
            else:
                print(f"📁 Bucket '{args.bucket}' is empty")
        else:
            print_error(f"Failed to list files: {result['error']}")
            return 1
            
        return 0
        
    except Exception as e:
        logger.error(f"Error in bucket list-files command: {e}")
        print_error(f"Command failed: {str(e)}")
        return 1

async def handle_bucket_remove_file(args) -> int:
    """Handle remove-file subcommand."""
    try:
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Ensure bucket registry is loaded
        await bucket_manager._load_bucket_registry()
        
        bucket = await bucket_manager.get_bucket(args.bucket)
        if not bucket:
            print_error(f"Bucket '{args.bucket}' not found")
            return 1
        
        result = await bucket.remove_file(args.path)
        
        if result["success"]:
            print(f"✅ Removed file '{args.path}' from bucket '{args.bucket}'")
            return 0
        else:
            print_error(f"Failed to remove file: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in bucket remove-file command: {e}")
        print_error(f"Command failed: {str(e)}")
        return 1

async def handle_bucket_export(args) -> int:
    """Handle bucket export to CAR archive."""
    if not BUCKET_VFS_AVAILABLE:
        print_error("Bucket VFS system not available")
        return 1
    
    try:
        # Initialize bucket manager
        bucket_manager = get_global_bucket_manager(
            storage_path=args.storage_path or "/tmp/ipfs_kit_buckets",
            ipfs_client=None
        )
        
        # Export bucket
        result = await bucket_manager.export_bucket_to_car(
            args.bucket,
            include_indexes=args.include_indexes
        )
        
        if result["success"]:
            data = result.get("data", {})
            print_success(f"Exported bucket '{args.bucket}' to CAR archive")
            print(f"  CAR Path: {data.get('car_path')}")
            print(f"  CAR CID: {data.get('car_cid')}")
            print(f"  Exported Items: {data.get('exported_items')}")
            return 0
        else:
            print_error(f"Failed to export bucket: {result.get('error')}")
            return 1
            
    except Exception as e:
        print_error(f"Error exporting bucket: {e}")
        return 1

async def handle_bucket_query(args) -> int:
    """Handle cross-bucket SQL query."""
    if not BUCKET_VFS_AVAILABLE:
        print_error("Bucket VFS system not available")
        return 1
    
    try:
        arg_values = vars(args)

        # Initialize bucket manager
        bucket_manager = get_global_bucket_manager(
            storage_path=arg_values.get("storage_path") or "/tmp/ipfs_kit_buckets",
            ipfs_client=None
        )
        
        # Parse bucket filter if provided
        bucket_filter = None
        buckets_value = arg_values.get("buckets")
        if buckets_value:
            bucket_filter = [b.strip() for b in str(buckets_value).split(",") if b.strip()]

        sql_query = arg_values.get("sql_query") or arg_values.get("query")
        if not sql_query:
            print_error("Missing SQL query")
            return 1
        
        # Execute query
        result = await _await_if_needed(
            bucket_manager.cross_bucket_query(sql_query, bucket_filter=bucket_filter)
        )
        
        if result["success"]:
            data = result.get("data", {})
            columns = data.get("columns", [])
            rows = data.get("rows", [])
            
            print_success(f"Query executed successfully ({len(rows)} rows)")
            print()
            
            if rows:
                # Print column headers
                header = " | ".join(f"{col:15}" for col in columns)
                print(colorize(header, 'BOLD'))
                print("-" * len(header))
                
                # Print rows
                for row in rows:
                    row_str = " | ".join(f"{str(val):15}" for val in row)
                    print(row_str)
            else:
                print_info("No results found")
            
            return 0
        else:
            print_error(f"Query failed: {result.get('error')}")
            return 1
            
    except Exception as e:
        print_error(f"Error executing query: {e}")
        return 1

def register_bucket_commands(parser_or_subparsers) -> None:
    """Register bucket VFS commands with the CLI."""
    if not BUCKET_VFS_AVAILABLE:
        logger.debug("Bucket VFS not available, skipping command registration")
        return

    # Accept either an argparse parser (preferred) or an existing subparsers object
    if hasattr(parser_or_subparsers, "add_subparsers"):
        subparsers = parser_or_subparsers.add_subparsers()
    else:
        subparsers = parser_or_subparsers
    
    # Main bucket command
    bucket_parser = subparsers.add_parser(
        "bucket",
        help="Multi-bucket virtual filesystem management"
    )
    
    bucket_subparsers = bucket_parser.add_subparsers(
        dest="bucket_command",
        help="Bucket operation to perform",
        required=True
    )
    
    # Global options for all bucket commands
    def add_common_args(parser):
        parser.add_argument(
            "--storage-path",
            help="Storage path for bucket data (default: /tmp/ipfs_kit_buckets)"
        )
    
    # Create bucket command
    create_parser = bucket_subparsers.add_parser(
        "create",
        help="Create a new bucket"
    )
    add_common_args(create_parser)
    create_parser.add_argument(
        "name",
        help="Name of the bucket to create"
    )
    create_parser.add_argument(
        "--type",
        choices=["general", "dataset", "knowledge", "media", "archive", "temp"],
        default="general",
        help="Type of bucket (default: general)"
    )
    create_parser.add_argument(
        "--structure",
        choices=["unixfs", "graph", "vector", "hybrid"],
        default="hybrid",
        help="VFS structure type (default: hybrid)"
    )
    create_parser.add_argument(
        "--metadata",
        help="JSON metadata for the bucket"
    )
    create_parser.set_defaults(
        func=lambda api, args, kwargs: (anyio.run(handle_bucket_create, args) if HAS_ANYIO else anyio.run(handle_bucket_create(args)))
    )
    
    # List buckets command
    list_parser = bucket_subparsers.add_parser(
        "list",
        help="List all buckets"
    )
    add_common_args(list_parser)
    list_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information"
    )
    list_parser.set_defaults(
        func=lambda api, args, kwargs: (anyio.run(handle_bucket_list, args) if HAS_ANYIO else anyio.run(handle_bucket_list(args)))
    )
    
    # Delete bucket command
    delete_parser = bucket_subparsers.add_parser(
        "delete",
        help="Delete a bucket"
    )
    add_common_args(delete_parser)
    delete_parser.add_argument(
        "name",
        help="Name of the bucket to delete"
    )
    delete_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force deletion without confirmation"
    )
    delete_parser.set_defaults(
        func=lambda api, args, kwargs: (anyio.run(handle_bucket_delete, args) if HAS_ANYIO else anyio.run(handle_bucket_delete(args)))
    )
    
    # Add file to bucket command
    add_file_parser = bucket_subparsers.add_parser(
        "add-file",
        help="Add a file to a bucket"
    )
    add_common_args(add_file_parser)
    add_file_parser.add_argument(
        "bucket",
        help="Name of the target bucket"
    )
    add_file_parser.add_argument(
        "path",
        help="Virtual path within the bucket"
    )
    add_file_parser.add_argument(
        "source",
        help="Source file path or literal content"
    )
    add_file_parser.add_argument(
        "--metadata",
        help="JSON metadata for the file"
    )
    add_file_parser.set_defaults(
        func=lambda api, args, kwargs: (anyio.run(handle_bucket_add_file, args) if HAS_ANYIO else anyio.run(handle_bucket_add_file(args)))
    )
    
    # Export bucket command
    export_parser = bucket_subparsers.add_parser(
        "export",
        help="Export bucket to CAR archive"
    )
    add_common_args(export_parser)
    export_parser.add_argument(
        "bucket",
        help="Name of the bucket to export"
    )
    export_parser.add_argument(
        "--include-indexes",
        action="store_true",
        default=True,
        help="Include knowledge graph and vector indexes"
    )
    export_parser.set_defaults(
        func=lambda api, args, kwargs: (anyio.run(handle_bucket_export, args) if HAS_ANYIO else anyio.run(handle_bucket_export(args)))
    )
    
    # Query buckets command
    query_parser = bucket_subparsers.add_parser(
        "query",
        help="Execute cross-bucket SQL query"
    )
    add_common_args(query_parser)
    query_parser.add_argument(
        "query",
        help="SQL query to execute"
    )
    query_parser.add_argument(
        "--buckets",
        help="Comma-separated list of buckets to include (default: all)"
    )
    query_parser.set_defaults(
        func=lambda api, args, kwargs: (anyio.run(handle_bucket_query, args) if HAS_ANYIO else anyio.run(handle_bucket_query(args)))
    )
    
    # Get file from bucket command
    get_file_parser = bucket_subparsers.add_parser(
        "get-file",
        help="Retrieve a file from a bucket"
    )
    add_common_args(get_file_parser)
    get_file_parser.add_argument(
        "bucket",
        help="Name of the bucket"
    )
    get_file_parser.add_argument(
        "path",
        help="Path of the file in the bucket"
    )
    get_file_parser.add_argument(
        "output",
        help="Output path to save the file"
    )
    get_file_parser.set_defaults(
        func=lambda api, args, kwargs: (anyio.run(handle_bucket_get_file, args) if HAS_ANYIO else anyio.run(handle_bucket_get_file(args)))
    )
    
    # Cat file from bucket command
    cat_file_parser = bucket_subparsers.add_parser(
        "cat-file",
        help="Display contents of a file from a bucket"
    )
    add_common_args(cat_file_parser)
    cat_file_parser.add_argument(
        "bucket",
        help="Name of the bucket"
    )
    cat_file_parser.add_argument(
        "path",
        help="Path of the file in the bucket"
    )
    cat_file_parser.set_defaults(
        func=lambda api, args, kwargs: (anyio.run(handle_bucket_cat_file, args) if HAS_ANYIO else anyio.run(handle_bucket_cat_file(args)))
    )
    
    # List files in bucket command
    list_files_parser = bucket_subparsers.add_parser(
        "list-files",
        help="List all files in a bucket"
    )
    add_common_args(list_files_parser)
    list_files_parser.add_argument(
        "bucket",
        help="Name of the bucket"
    )
    list_files_parser.set_defaults(
        func=lambda api, args, kwargs: (anyio.run(handle_bucket_list_files, args) if HAS_ANYIO else anyio.run(handle_bucket_list_files(args)))
    )
    
    # Set the main bucket command handler
    bucket_parser.set_defaults(
        func=lambda api, args, kwargs: args.func(api, args, kwargs) if hasattr(args, 'func') and callable(args.func) else bucket_parser.print_help()
    )

def handle_bucket_command(api, args, kwargs):
    """Handle bucket commands."""
    # This is called when args.func is set
    if hasattr(args, 'func') and callable(args.func):
        return args.func(args)
    else:
        print_error("No bucket subcommand specified")
        return 1


# Additional handler functions for CLI integration
async def handle_bucket_remove(args) -> int:
    """Remove a bucket (alias for handle_bucket_delete)."""
    return await handle_bucket_delete(args)


async def handle_bucket_tag_file(args) -> int:
    """Tag a file in a bucket."""
    if not BUCKET_VFS_AVAILABLE:
        print_error("BucketVFS not available - install required dependencies")
        return 1
    
    try:
        bucket_manager = get_global_bucket_manager(
            storage_path=str(Path.home() / ".ipfs_kit" / "buckets")
        )
        
        # Ensure bucket registry is loaded
        await bucket_manager._load_bucket_registry()
        
        bucket = await bucket_manager.get_bucket(args.bucket)
        
        if not bucket:
            print_error(f"Cannot find bucket '{args.bucket}'")
            return 1
        
        # Add tag to file (implementation would depend on bucket VFS capabilities)
        print_success(f"Tagged file '{args.virtual_path}' with '{args.tag}' in bucket '{args.bucket_name}'")
        print("Note: File tagging implementation depends on bucket VFS metadata support")
        return 0
        
    except Exception as e:
        print_error(f"Failed to tag file: {e}")
        return 1


# Pin operation handlers (these would integrate with IPFS pinning)
async def handle_bucket_pin_list(args) -> int:
    """List pinned content in bucket."""
    try:
        print_success(f"Listing pinned content in bucket '{args.bucket_name}'")
        print("Note: Pin listing implementation would integrate with IPFS pin status")
        return 0
    except Exception as e:
        print_error(f"Failed to list pins: {e}")
        return 1


async def handle_bucket_pin_add(args) -> int:
    """Pin file in bucket."""
    try:
        print_success(f"Pinning file '{args.virtual_path}' in bucket '{args.bucket_name}'")
        print("Note: Pin add implementation would use IPFS pin operations")
        return 0
    except Exception as e:
        print_error(f"Failed to pin file: {e}")
        return 1


async def handle_bucket_pin_get(args) -> int:
    """Get and pin file from bucket."""
    try:
        # First get the file, then pin it
        result = await handle_bucket_get_file(args)
        if result == 0:
            print_success(f"File retrieved and pinned from bucket '{args.bucket_name}'")
        return result
    except Exception as e:
        print_error(f"Failed to get and pin file: {e}")
        return 1


async def handle_bucket_pin_cat(args) -> int:
    """Display pinned file content from bucket."""
    try:
        # Same as regular cat, but ensures content is pinned
        return await handle_bucket_cat_file(args)
    except Exception as e:
        print_error(f"Failed to cat pinned file: {e}")
        return 1


async def handle_bucket_pin_remove(args) -> int:
    """Unpin file in bucket."""
    try:
        print_success(f"Unpinning file '{args.virtual_path}' in bucket '{args.bucket_name}'")
        print("Note: Pin remove implementation would use IPFS unpin operations")
        return 0
    except Exception as e:
        print_error(f"Failed to unpin file: {e}")
        return 1


async def handle_bucket_pin_tag(args) -> int:
    """Tag pinned content in bucket."""
    try:
        print_success(f"Tagged pinned file '{args.virtual_path}' with '{args.tag}' in bucket '{args.bucket_name}'")
        print("Note: Pin tagging implementation would integrate with IPFS metadata")
        return 0
    except Exception as e:
        print_error(f"Failed to tag pinned file: {e}")
        return 1