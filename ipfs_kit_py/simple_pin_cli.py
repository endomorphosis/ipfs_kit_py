#!/usr/bin/env python3
"""
Simplified PIN CLI handlers.

This implements PIN CLI commands using the simplified PIN manager
that follows the correct architecture (like bucket system).
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def print_pin_table(pins: list):
    """Print pins in a formatted table."""
    if not pins:
        print("📭 No pins found")
        return
    
    print(f"\n📌 Pins ({len(pins)} pins):")
    print("─" * 120)
    print(f"{'Name':<25} {'CID':<25} {'Size':<12} {'Recursive':<10} {'Created':<20} {'Status':<10}")
    print("─" * 120)
    
    for pin_info in pins:
        name = pin_info.get('name', 'unknown')[:24]
        cid = pin_info.get('cid', 'unknown')[:24]
        file_size = pin_info.get('file_size', 0)
        recursive = 'Yes' if pin_info.get('recursive', False) else 'No'
        created = pin_info.get('created_at', 'unknown')[:19]
        status = pin_info.get('status', 'unknown')[:9]
        
        # Format size
        if file_size < 1024:
            size_str = f"{file_size}B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size/1024:.1f}KB"
        elif file_size < 1024 * 1024 * 1024:
            size_str = f"{file_size/(1024*1024):.1f}MB"
        else:
            size_str = f"{file_size/(1024*1024*1024):.1f}GB"
        
        print(f"{name:<25} {cid:<25} {size_str:<12} {recursive:<10} {created:<20} {status:<10}")


def print_pending_operations_table(operations: list):
    """Print pending operations in a formatted table."""
    if not operations:
        print("📭 No pending operations")
        return
    
    print(f"\n⏳ Pending Operations ({len(operations)} operations):")
    print("─" * 130)
    print(f"{'Operation':<15} {'Name':<20} {'CID':<25} {'Type':<10} {'Size':<12} {'Created':<20} {'Status':<10}")
    print("─" * 130)
    
    for op_info in operations:
        operation_id = op_info.get('operation_id', 'unknown')[:14]
        name = op_info.get('pin_name', 'unknown')[:19]
        cid = op_info.get('target_cid', 'unknown')[:24]
        op_type = op_info.get('operation_type', 'unknown')[:9]
        content_size = op_info.get('content_size', 0)
        created = op_info.get('created_at', 'unknown')[:19]
        status = op_info.get('status', 'unknown')[:9]
        
        # Format size
        if content_size < 1024:
            size_str = f"{content_size}B"
        elif content_size < 1024 * 1024:
            size_str = f"{content_size/1024:.1f}KB"
        elif content_size < 1024 * 1024 * 1024:
            size_str = f"{content_size/(1024*1024):.1f}MB"
        else:
            size_str = f"{content_size/(1024*1024*1024):.1f}GB"
        
        print(f"{operation_id:<15} {name:<20} {cid:<25} {op_type:<10} {size_str:<12} {created:<20} {status:<10}")


async def handle_pin_add(args) -> int:
    """Handle pin add command."""
    cid_or_file = args.cid_or_file
    name = getattr(args, 'name', None)
    recursive = getattr(args, 'recursive', True)
    
    # Check if it's a file
    is_file = Path(cid_or_file).exists()
    
    if is_file:
        print(f"📤 Adding file PIN...")
        print(f"   Source: {cid_or_file}")
    else:
        print(f"📤 Adding CID PIN...")
        print(f"   CID: {cid_or_file}")
    
    print(f"   Name: {name or 'auto-generated'}")
    print(f"   Recursive: {recursive}")
    
    try:
        from .simple_pin_manager import get_simple_pin_manager
        
        pin_manager = get_simple_pin_manager()
        result = await pin_manager.add_pin_operation(
            cid_or_file=cid_or_file,
            name=name,
            recursive=recursive,
            metadata={}
        )
        
        if result['success']:
            data = result['data']
            print(f"✅ PIN operation added successfully")
            print(f"   📌 CID: {data['cid']}")
            print(f"   📄 Name: {data['name']}")
            if data.get('source_file'):
                print(f"   📁 Source: {data['source_file']}")
            print(f"   📊 Size: {data['file_size']} bytes")
            print(f"   🔄 Recursive: {data['recursive']}")
            print(f"   💾 WAL stored: {data['wal_stored']}")
            
            print(f"\n💡 Operation queued in WAL for daemon processing")
            print(f"💡 Use 'ipfs-kit pin pending' to view queued operations")
            print(f"💡 Use 'ipfs-kit pin list' to view all pins")
            return 0
        else:
            print(f"❌ Failed to add PIN: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in handle_pin_add: {e}")
        print(f"❌ Error adding PIN: {e}")
        return 1


async def handle_pin_list(args) -> int:
    """Handle pin list command."""
    limit = getattr(args, 'limit', None)
    
    print("📌 Listing pins...")
    if limit:
        print(f"   Limit: {limit}")
    
    try:
        from .simple_pin_manager import get_simple_pin_manager
        
        pin_manager = get_simple_pin_manager()
        result = await pin_manager.list_pins(limit=limit)
        
        if result['success']:
            pins = result['data']['pins']
            print_pin_table(pins)
            
            if pins:
                print(f"\n✅ Total: {len(pins)} pin(s)")
                print("💡 Use 'ipfs-kit pin pending' to see pending operations")
            else:
                print("💡 Use 'ipfs-kit pin add <cid_or_file>' to add your first pin")
            
            return 0
        else:
            print(f"❌ Failed to list pins: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in handle_pin_list: {e}")
        print(f"❌ Error listing pins: {e}")
        return 1


async def handle_pin_pending(args) -> int:
    """Handle pin pending command."""
    limit = getattr(args, 'limit', None)
    show_metadata = getattr(args, 'metadata', False)
    
    print("⏳ Listing pending PIN operations...")
    if limit:
        print(f"   Limit: {limit}")
    print(f"   Show metadata: {show_metadata}")
    
    try:
        from .simple_pin_manager import get_simple_pin_manager
        
        pin_manager = get_simple_pin_manager()
        result = await pin_manager.get_pending_operations(limit=limit)
        
        if result['success']:
            operations = result['data']['operations']
            print_pending_operations_table(operations)
            
            if operations:
                print(f"\n✅ Total: {len(operations)} pending operation(s)")
                
                if show_metadata:
                    print(f"\n📋 Operation Details:")
                    for op in operations[:5]:  # Show details for first 5
                        print(f"\n🔧 {op.get('operation_id', 'unknown')}")
                        print(f"   Type: {op.get('operation_type')}")
                        print(f"   CID: {op.get('target_cid')}")
                        print(f"   Source: {op.get('source_file', 'N/A')}")
                        print(f"   WAL File: {op.get('wal_file')}")
                
                print(f"\n💡 These operations will be processed by the daemon")
            else:
                print("💡 Use 'ipfs-kit pin add <cid_or_file>' to queue new operations")
            
            return 0
        else:
            print(f"❌ Failed to list pending operations: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in handle_pin_pending: {e}")
        print(f"❌ Error listing pending operations: {e}")
        return 1


async def handle_pin_remove(args) -> int:
    """Handle pin remove command."""
    cid = args.cid
    
    print(f"🗑️ Removing PIN...")
    print(f"   CID: {cid}")
    
    try:
        from .simple_pin_manager import get_simple_pin_manager
        
        pin_manager = get_simple_pin_manager()
        result = await pin_manager.remove_pin(cid)
        
        if result['success']:
            print(f"✅ PIN removed successfully")
            print(f"   📌 CID: {cid}")
            print(f"   🕒 Removed at: {result['data']['removed_at']}")
            return 0
        else:
            print(f"❌ Failed to remove PIN: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error in handle_pin_remove: {e}")
        print(f"❌ Error removing PIN: {e}")
        return 1


async def handle_pin_status(args) -> int:
    """Handle pin status command."""
    print("📊 PIN system status...")
    
    try:
        from .simple_pin_manager import get_simple_pin_manager
        
        pin_manager = get_simple_pin_manager()
        
        # Get pins and pending operations
        pins_result = await pin_manager.list_pins()
        pending_result = await pin_manager.get_pending_operations()
        
        if pins_result['success'] and pending_result['success']:
            total_pins = len(pins_result['data']['pins'])
            total_pending = len(pending_result['data']['operations'])
            
            print(f"\n📈 PIN System Status:")
            print(f"   📌 Total pins: {total_pins}")
            print(f"   ⏳ Pending operations: {total_pending}")
            print(f"   📂 PIN index: {pin_manager.pin_metadata_dir / 'pins.parquet'}")
            print(f"   📁 WAL directory: {pin_manager.wal_dir}")
            
            # Check if directories exist
            pin_index_exists = (pin_manager.pin_metadata_dir / 'pins.parquet').exists()
            wal_dir_exists = pin_manager.wal_dir.exists()
            
            print(f"\n📁 File System Status:")
            print(f"   PIN index exists: {'✅' if pin_index_exists else '❌'}")
            print(f"   WAL directory exists: {'✅' if wal_dir_exists else '❌'}")
            
            if wal_dir_exists:
                wal_files = list(pin_manager.wal_dir.glob('*.parquet'))
                content_files = list(pin_manager.wal_dir.glob('*.content'))
                print(f"   WAL parquet files: {len(wal_files)}")
                print(f"   WAL content files: {len(content_files)}")
            
            return 0
        else:
            print(f"❌ Failed to get PIN status")
            return 1
            
    except Exception as e:
        logger.error(f"Error in handle_pin_status: {e}")
        print(f"❌ Error getting PIN status: {e}")
        return 1
