#!/usr/bin/env python3
"""
Simple Bucket CLI handlers.
Uses the SimpleBucketManager for clean VFS index-based operations.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def print_bucket_table(buckets: List[Dict[str, Any]]):
    """Print buckets in a formatted table."""
    if not buckets:
        print("📭 No buckets found")
        return
    
    print(f"\n📦 Found {len(buckets)} bucket(s):")
    print("─" * 80)
    print(f"{'Name':<20} {'Type':<12} {'Files':<8} {'Size':<12} {'Created':<20}")
    print("─" * 80)
    
    for bucket in buckets:
        name = bucket.get('name', 'unknown')[:19]
        bucket_type = bucket.get('type', 'general')[:11]
        file_count = bucket.get('file_count', 0)
        size_bytes = bucket.get('size_bytes', 0)
        created = bucket.get('created_at', 'unknown')[:19]
        
        # Format size
        if size_bytes < 1024:
            size_str = f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes/1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            size_str = f"{size_bytes/(1024*1024):.1f}MB"
        else:
            size_str = f"{size_bytes/(1024*1024*1024):.1f}GB"
        
        print(f"{name:<20} {bucket_type:<12} {file_count:<8} {size_str:<12} {created:<20}")


def print_files_table(files: List[Dict[str, Any]], bucket_name: str):
    """Print files in a formatted table."""
    if not files:
        print(f"📭 No files in bucket '{bucket_name}'")
        return
    
    print(f"\n📄 Files in bucket '{bucket_name}' ({len(files)} files):")
    print("─" * 100)
    print(f"{'File Path':<30} {'CID':<25} {'Size':<12} {'Created':<20}")
    print("─" * 100)
    
    for file_info in files:
        file_path = file_info.get('file_path', 'unknown')[:29]
        file_cid = file_info.get('file_cid', 'unknown')[:24]
        file_size = file_info.get('file_size', 0)
        created = file_info.get('created_at', 'unknown')[:19]
        
        # Format size
        if file_size < 1024:
            size_str = f"{file_size}B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size/1024:.1f}KB"
        elif file_size < 1024 * 1024 * 1024:
            size_str = f"{file_size/(1024*1024):.1f}MB"
        else:
            size_str = f"{file_size/(1024*1024*1024):.1f}GB"
        
        print(f"{file_path:<30} {file_cid:<25} {size_str:<12} {created:<20}")


async def handle_bucket_list(args) -> int:
    """Handle bucket list command."""
    print("📦 Listing buckets...")
    
    try:
        from .simple_bucket_manager import get_simple_bucket_manager
        
        bucket_manager = get_simple_bucket_manager()
        result = await bucket_manager.list_buckets()
        
        if result['success']:
            buckets = result['data']['buckets']
            print_bucket_table(buckets)
            
            if buckets:
                print(f"\n✅ Total: {len(buckets)} bucket(s)")
                print("💡 Use 'ipfs-kit bucket files <name>' to see files in a bucket")
            else:
                print("💡 Use 'ipfs-kit bucket create <name>' to create your first bucket")
            
            return 0
        else:
            print(f"❌ Failed to list buckets: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in handle_bucket_list: {e}")
        print(f"❌ Error listing buckets: {e}")
        return 1


async def handle_bucket_create(args) -> int:
    """Handle bucket create command."""
    bucket_name = args.bucket_name
    bucket_type = getattr(args, 'type', 'general')
    
    print(f"🔨 Creating bucket '{bucket_name}'...")
    print(f"   Type: {bucket_type}")
    
    try:
        from .simple_bucket_manager import get_simple_bucket_manager
        
        bucket_manager = get_simple_bucket_manager()
        result = await bucket_manager.create_bucket(
            bucket_name=bucket_name,
            bucket_type=bucket_type
        )
        
        if result['success']:
            data = result['data']
            print(f"✅ Bucket '{bucket_name}' created successfully")
            print(f"   📂 VFS Index: {data['vfs_index_path']}")
            print(f"   📅 Created: {data['created_at']}")
            print(f"\n💡 Add files with: ipfs-kit bucket add {bucket_name} <file>")
            return 0
        else:
            print(f"❌ Failed to create bucket: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in handle_bucket_create: {e}")
        print(f"❌ Error creating bucket: {e}")
        return 1


async def handle_bucket_remove(args) -> int:
    """Handle bucket remove command."""
    bucket_name = args.bucket_name
    force = getattr(args, 'force', False)
    
    print(f"🗑️ Removing bucket '{bucket_name}'...")
    if force:
        print("   ⚠️ Force mode enabled")
    
    try:
        from .simple_bucket_manager import get_simple_bucket_manager
        
        bucket_manager = get_simple_bucket_manager()
        result = await bucket_manager.delete_bucket(bucket_name, force=force)
        
        if result['success']:
            print(f"✅ Bucket '{bucket_name}' removed successfully")
            return 0
        else:
            print(f"❌ Failed to remove bucket: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in handle_bucket_remove: {e}")
        print(f"❌ Error removing bucket: {e}")
        return 1


async def handle_bucket_add_file(args) -> int:
    """Handle bucket add file command."""
    bucket_name = args.bucket  # CLI uses 'bucket' not 'bucket_name'
    source_path = args.source  # CLI uses 'source'
    virtual_path = args.path   # CLI uses 'path' for virtual path
    
    # Check if source file exists
    source_file = Path(source_path)
    if not source_file.exists():
        print(f"❌ Source file not found: {source_path}")
        return 1
    
    print(f"📤 Adding file to bucket '{bucket_name}'...")
    print(f"   Source: {source_path}")
    print(f"   Virtual path: {virtual_path}")
    
    try:
        from .simple_bucket_manager import get_simple_bucket_manager
        
        bucket_manager = get_simple_bucket_manager()
        result = await bucket_manager.add_file_to_bucket(
            bucket_name=bucket_name,
            file_path=virtual_path,
            content_file=str(source_file)
        )
        
        if result['success']:
            data = result['data']
            print(f"✅ File added to bucket successfully")
            print(f"   📂 Bucket: {data['bucket_name']}")
            print(f"   📄 Virtual path: {data['file_path']}")
            print(f"   🔗 CID: {data['file_cid']}")
            print(f"   📊 Size: {data['file_size']} bytes")
            print(f"   💾 WAL stored: {data['wal_stored']}")
            return 0
        else:
            print(f"❌ Failed to add file: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in handle_bucket_add_file: {e}")
        print(f"❌ Error adding file: {e}")
        return 1


async def handle_bucket_files(args) -> int:
    """Handle bucket files command (list files in bucket)."""
    bucket_name = args.bucket_name
    limit = getattr(args, 'limit', None)
    
    print(f"📄 Listing files in bucket '{bucket_name}'...")
    if limit:
        print(f"   Limit: {limit}")
    
    try:
        from .simple_bucket_manager import get_simple_bucket_manager
        
        bucket_manager = get_simple_bucket_manager()
        result = await bucket_manager.get_bucket_files(bucket_name, limit=limit)
        
        if result['success']:
            files = result['data']['files']
            print_files_table(files, bucket_name)
            
            if files:
                print(f"\n✅ Total: {len(files)} file(s)")
                print("💡 Use 'ipfs-kit bucket cat <bucket> <file>' to view file content")
            else:
                print("💡 Use 'ipfs-kit bucket add <bucket> <file>' to add files")
            
            return 0
        else:
            print(f"❌ Failed to list bucket files: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in handle_bucket_files: {e}")
        print(f"❌ Error listing bucket files: {e}")
        return 1


# Stub handlers for other commands - these need to be implemented
async def handle_bucket_get_file(args) -> int:
    """Handle bucket get file command."""
    print("🚧 bucket get command not yet implemented in simple bucket manager")
    return 1

async def handle_bucket_cat_file(args) -> int:
    """Handle bucket cat file command."""
    print("🚧 bucket cat command not yet implemented in simple bucket manager")
    return 1

async def handle_bucket_remove_file(args) -> int:
    """Handle bucket remove file command."""
    print("🚧 bucket rm file command not yet implemented in simple bucket manager")
    return 1

async def handle_bucket_tag_file(args) -> int:
    """Handle bucket tag file command."""
    print("🚧 bucket tag command not yet implemented in simple bucket manager")
    return 1

# Pin operation stubs
async def handle_bucket_pin_list(args) -> int:
    """Handle bucket pin list command."""
    print("🚧 bucket pin ls command not yet implemented in simple bucket manager")
    return 1

async def handle_bucket_pin_add(args) -> int:
    """Handle bucket pin add command."""
    print("🚧 bucket pin add command not yet implemented in simple bucket manager")
    return 1

async def handle_bucket_pin_get(args) -> int:
    """Handle bucket pin get command."""
    print("🚧 bucket pin get command not yet implemented in simple bucket manager")
    return 1

async def handle_bucket_pin_cat(args) -> int:
    """Handle bucket pin cat command."""
    print("🚧 bucket pin cat command not yet implemented in simple bucket manager")
    return 1

async def handle_bucket_pin_remove(args) -> int:
    """Handle bucket pin remove command."""
    print("🚧 bucket pin rm command not yet implemented in simple bucket manager")
    return 1

async def handle_bucket_pin_tag(args) -> int:
    """Handle bucket pin tag command."""
    print("🚧 bucket pin tag command not yet implemented in simple bucket manager")
    return 1
