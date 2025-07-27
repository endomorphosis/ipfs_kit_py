#!/usr/bin/env python3
"""
Bucket VFS CLI Integration for IPFS Kit.

This module provides CLI commands for managing multi-bucket virtual filesystems
with S3-like semantics, IPLD compatibility, and cross-platform data export.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import bucket VFS components
try:
    from .bucket_vfs_manager import get_global_bucket_manager, BucketType, VFSStructureType
    from .error import create_result_dict, handle_error
    BUCKET_VFS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Bucket VFS not available: {e}")
    BUCKET_VFS_AVAILABLE = False

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

async def handle_bucket_create(args) -> int:
    """Handle bucket create command."""
    if not BUCKET_VFS_AVAILABLE:
        print_error("Bucket VFS system not available")
        return 1
    
    try:
        # Initialize bucket manager
        bucket_manager = get_global_bucket_manager(
            storage_path=args.storage_path or "/tmp/ipfs_kit_buckets",
            ipfs_client=None  # CLI mode doesn't require IPFS client
        )
        
        # Convert string enums
        try:
            bucket_type = BucketType(args.type)
            vfs_structure = VFSStructureType(args.structure)
        except ValueError as e:
            print_error(f"Invalid enum value: {e}")
            return 1
        
        # Parse metadata if provided
        metadata = {}
        if args.metadata:
            try:
                metadata = json.loads(args.metadata)
            except json.JSONDecodeError as e:
                print_error(f"Invalid JSON metadata: {e}")
                return 1
        
        # Create bucket
        result = await bucket_manager.create_bucket(
            bucket_name=args.name,
            bucket_type=bucket_type,
            vfs_structure=vfs_structure,
            metadata=metadata
        )
        
        if result["success"]:
            data = result.get("data", {})
            print_success(f"Created bucket '{args.name}'")
            print(f"  Type: {data.get('bucket_type')}")
            print(f"  Structure: {data.get('vfs_structure')}")
            print(f"  Root CID: {data.get('cid')}")
            print(f"  Created: {data.get('created_at')}")
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
        # Initialize bucket manager
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
            storage_path=args.storage_path or "/tmp/ipfs_kit_buckets",
            ipfs_client=None
        )
        
        # Confirm deletion if not forced
        if not args.force:
            print_warning(f"This will permanently delete bucket '{args.name}' and all its contents.")
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
    """Handle adding a file to a bucket."""
    if not BUCKET_VFS_AVAILABLE:
        print_error("Bucket VFS system not available")
        return 1
    
    try:
        # Initialize bucket manager
        bucket_manager = get_global_bucket_manager(
            storage_path=args.storage_path or "/tmp/ipfs_kit_buckets",
            ipfs_client=None
        )
        
        # Get bucket
        bucket = await bucket_manager.get_bucket(args.bucket)
        if not bucket:
            print_error(f"Bucket '{args.bucket}' not found")
            return 1
        
        # Read file content
        if os.path.exists(args.source):
            with open(args.source, 'rb') as f:
                content = f.read()
        else:
            # Treat as literal content
            content = args.source.encode('utf-8')
        
        # Parse metadata if provided
        metadata = {}
        if args.metadata:
            try:
                metadata = json.loads(args.metadata)
            except json.JSONDecodeError as e:
                print_error(f"Invalid JSON metadata: {e}")
                return 1
        
        # Add file to bucket
        result = await bucket.add_file(args.path, content, metadata)
        
        if result["success"]:
            data = result.get("data", {})
            print_success(f"Added file '{args.path}' to bucket '{args.bucket}'")
            print(f"  Size: {data.get('size')} bytes")
            print(f"  CID: {data.get('cid')}")
            print(f"  Local Path: {data.get('local_path')}")
            return 0
        else:
            print_error(f"Failed to add file: {result.get('error')}")
            return 1
            
    except Exception as e:
        print_error(f"Error adding file: {e}")
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
        # Initialize bucket manager
        bucket_manager = get_global_bucket_manager(
            storage_path=args.storage_path or "/tmp/ipfs_kit_buckets",
            ipfs_client=None
        )
        
        # Parse bucket filter if provided
        bucket_filter = None
        if args.buckets:
            bucket_filter = args.buckets.split(',')
        
        # Execute query
        result = await bucket_manager.cross_bucket_query(
            args.query,
            bucket_filter=bucket_filter
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

def register_bucket_commands(subparsers) -> None:
    """Register bucket VFS commands with the CLI."""
    if not BUCKET_VFS_AVAILABLE:
        logger.debug("Bucket VFS not available, skipping command registration")
        return
    
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
        func=lambda args: asyncio.run(handle_bucket_create(args))
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
        func=lambda args: asyncio.run(handle_bucket_list(args))
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
        func=lambda args: asyncio.run(handle_bucket_delete(args))
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
        func=lambda args: asyncio.run(handle_bucket_add_file(args))
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
        func=lambda args: asyncio.run(handle_bucket_export(args))
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
        func=lambda args: asyncio.run(handle_bucket_query(args))
    )
    
    # Set the main bucket command handler
    bucket_parser.set_defaults(
        func=lambda args: args.func(args) if hasattr(args, 'func') else bucket_parser.print_help()
    )

def handle_bucket_command(api, args, kwargs):
    """Handle bucket commands."""
    # This is called when args.func is set
    if hasattr(args, 'func') and callable(args.func):
        return args.func(args)
    else:
        print_error("No bucket subcommand specified")
        return 1
