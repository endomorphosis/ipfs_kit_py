#!/usr/bin/env python3
"""
Filecoin Pin CLI - Command-line interface for Filecoin Pin operations.

This module provides CLI commands for interacting with the Filecoin Pin backend,
including pinning, unpinning, listing, and checking pin status.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def print_pin_table(pins: list):
    """Print pins in a formatted table."""
    if not pins:
        print("📭 No pins found")
        return
    
    print(f"\n📌 Filecoin Pins ({len(pins)} pins):")
    print("─" * 130)
    print(f"{'CID':<50} {'Name':<25} {'Status':<12} {'Size':<12} {'Deals':<8} {'Created':<20}")
    print("─" * 130)
    
    for pin_info in pins:
        cid = pin_info.get('cid', 'unknown')[:49]
        name = pin_info.get('name', 'unknown')[:24]
        status = pin_info.get('status', 'unknown')[:11]
        size = pin_info.get('size', 0)
        deals = len(pin_info.get('deals', []))
        created = pin_info.get('created', 'unknown')[:19]
        
        # Format size
        if size < 1024:
            size_str = f"{size}B"
        elif size < 1024 * 1024:
            size_str = f"{size/1024:.1f}KB"
        elif size < 1024 * 1024 * 1024:
            size_str = f"{size/(1024*1024):.1f}MB"
        else:
            size_str = f"{size/(1024*1024*1024):.1f}GB"
        
        # Add emoji for status
        if status == 'pinned':
            status_icon = '✅'
        elif status == 'pinning':
            status_icon = '⏳'
        elif status == 'queued':
            status_icon = '📋'
        elif status == 'failed':
            status_icon = '❌'
        else:
            status_icon = '❓'
        
        print(f"{cid:<50} {name:<25} {status_icon} {status:<10} {size_str:<12} {deals:<8} {created:<20}")
    
    print("─" * 130)


async def handle_filecoin_pin_add(args) -> int:
    """Handle filecoin pin add command."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
        
        # Get API key from environment or args
        api_key = args.api_key or os.getenv('FILECOIN_PIN_API_KEY')
        
        # Initialize backend
        resources = {
            "api_key": api_key,
            "api_endpoint": args.endpoint if hasattr(args, 'endpoint') else None,
            "timeout": args.timeout if hasattr(args, 'timeout') else 60
        }
        
        metadata = {
            "default_replication": args.replication if hasattr(args, 'replication') else 3,
            "auto_renew": True,
            "deal_duration_days": 540
        }
        
        backend = FilecoinPinBackend(resources, metadata)
        
        # Determine if input is file or CID
        input_path = args.content
        is_file = Path(input_path).exists()
        
        if is_file:
            print(f"📤 Pinning file to Filecoin Pin: {input_path}")
            content = input_path
        else:
            print(f"📤 Pinning CID to Filecoin Pin: {input_path}")
            # Note: For CID-based pinning, Filecoin Pin service fetches content from IPFS network
            # We encode CID as bytes here - the backend will handle the actual IPFS retrieval
            print("⚠️  Note: Pinning by CID requires the content to be already available on IPFS")
            content = input_path.encode('utf-8')  # CID reference - backend handles IPFS fetch
        
        # Pin content
        pin_metadata = {
            "name": args.name if args.name else f"pin-{os.path.basename(input_path) if is_file else input_path[:12]}",
            "description": args.description if hasattr(args, 'description') else "",
            "tags": args.tags.split(',') if hasattr(args, 'tags') and args.tags else [],
            "replication": args.replication if hasattr(args, 'replication') else metadata["default_replication"]
        }
        
        result = backend.add_content(content, pin_metadata)
        
        if result.get('success'):
            print(f"\n✅ Successfully pinned to Filecoin Pin!")
            print(f"   CID: {result['cid']}")
            print(f"   Status: {result['status']}")
            print(f"   Request ID: {result.get('request_id', 'N/A')}")
            print(f"   Size: {result.get('size', 0)} bytes")
            print(f"   Replication: {result.get('replication', 0)}")
            
            if result.get('deal_ids'):
                print(f"   Deal IDs: {', '.join(result['deal_ids'])}")
            
            if result.get('mock'):
                print("\n⚠️  Running in MOCK mode (no API key provided)")
            
            return 0
        else:
            print(f"\n❌ Failed to pin content: {result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        logger.error(f"Error pinning content: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1


async def handle_filecoin_pin_ls(args) -> int:
    """Handle filecoin pin ls command."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        # Get API key
        api_key = args.api_key or os.getenv('FILECOIN_PIN_API_KEY')
        
        # Initialize backend
        resources = {"api_key": api_key}
        metadata = {}
        
        backend = FilecoinPinBackend(resources, metadata)
        
        # List pins
        status_filter = args.status if hasattr(args, 'status') else None
        limit = args.limit if hasattr(args, 'limit') else 100
        
        result = backend.list_pins(status=status_filter, limit=limit)
        
        if result.get('success'):
            pins = result.get('pins', [])
            
            if not pins:
                print("📭 No pins found")
                if result.get('mock'):
                    print("\n⚠️  Running in MOCK mode (no API key provided)")
                return 0
            
            print_pin_table(pins)
            
            if result.get('mock'):
                print("\n⚠️  Running in MOCK mode (no API key provided)")
            
            return 0
        else:
            print(f"❌ Failed to list pins: {result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        logger.error(f"Error listing pins: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1


async def handle_filecoin_pin_status(args) -> int:
    """Handle filecoin pin status command."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        # Get API key
        api_key = args.api_key or os.getenv('FILECOIN_PIN_API_KEY')
        
        # Initialize backend
        resources = {"api_key": api_key}
        metadata = {}
        
        backend = FilecoinPinBackend(resources, metadata)
        
        # Get metadata
        cid = args.cid
        result = backend.get_metadata(cid)
        
        if result.get('success'):
            print(f"\n📊 Pin Status for {cid}")
            print("─" * 80)
            print(f"Status: {result.get('status', 'unknown')}")
            print(f"Size: {result.get('size', 0)} bytes")
            print(f"Replication: {result.get('replication', 0)}")
            print(f"Created: {result.get('created', 'N/A')}")
            
            deals = result.get('deals', [])
            if deals:
                print(f"\nFilecoin Deals ({len(deals)}):")
                for i, deal in enumerate(deals, 1):
                    print(f"  {i}. Deal ID: {deal.get('id', 'N/A')}")
                    if 'provider' in deal:
                        print(f"     Provider: {deal['provider']}")
            else:
                print("\nFilecoin Deals: None yet (pinning in progress)")
            
            if result.get('mock'):
                print("\n⚠️  Running in MOCK mode (no API key provided)")
            
            return 0
        else:
            print(f"❌ Failed to get pin status: {result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        logger.error(f"Error getting pin status: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1


async def handle_filecoin_pin_rm(args) -> int:
    """Handle filecoin pin rm command."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        # Get API key
        api_key = args.api_key or os.getenv('FILECOIN_PIN_API_KEY')
        
        # Initialize backend
        resources = {"api_key": api_key}
        metadata = {}
        
        backend = FilecoinPinBackend(resources, metadata)
        
        # Remove pin
        cid = args.cid
        
        # Confirm if not forced
        if not args.force:
            response = input(f"⚠️  Are you sure you want to unpin {cid}? (y/N): ")
            if response.lower() != 'y':
                print("❌ Unpin cancelled")
                return 1
        
        result = backend.remove_content(cid)
        
        if result.get('success'):
            print(f"✅ Successfully unpinned {cid}")
            
            if result.get('mock'):
                print("\n⚠️  Running in MOCK mode (no API key provided)")
            
            return 0
        else:
            print(f"❌ Failed to unpin content: {result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        logger.error(f"Error unpinning content: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1


async def handle_filecoin_pin_get(args) -> int:
    """Handle filecoin pin get command."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        # Get API key
        api_key = args.api_key or os.getenv('FILECOIN_PIN_API_KEY')
        
        # Initialize backend
        resources = {"api_key": api_key}
        metadata = {}
        
        backend = FilecoinPinBackend(resources, metadata)
        
        # Get content
        cid = args.cid
        output_path = args.output if hasattr(args, 'output') else None
        
        print(f"📥 Retrieving content from Filecoin Pin: {cid}")
        
        result = backend.get_content(cid)
        
        if result.get('success'):
            content = result.get('data', b'')
            
            if output_path:
                # Write to file
                with open(output_path, 'wb') as f:
                    f.write(content)
                print(f"✅ Content saved to: {output_path}")
            else:
                # Print to stdout (if text) or save to default file
                try:
                    text = content.decode('utf-8')
                    print(f"\n{text}")
                except UnicodeDecodeError:
                    # Binary content - save to file
                    default_name = f"{cid[:12]}.bin"
                    with open(default_name, 'wb') as f:
                        f.write(content)
                    print(f"✅ Binary content saved to: {default_name}")
            
            print(f"   Size: {result.get('size', 0)} bytes")
            print(f"   Source: {result.get('source', 'unknown')}")
            
            if result.get('mock'):
                print("\n⚠️  Running in MOCK mode (no API key provided)")
            
            return 0
        else:
            print(f"❌ Failed to retrieve content: {result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        logger.error(f"Error retrieving content: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1


def setup_filecoin_pin_parser(subparsers):
    """Set up the filecoin-pin CLI parser."""
    
    # Create filecoin-pin subcommand
    filecoin_parser = subparsers.add_parser(
        'filecoin-pin',
        help='Filecoin Pin operations (unified IPFS + Filecoin storage)',
        description='Manage content pinning with Filecoin Pin service'
    )
    
    filecoin_subparsers = filecoin_parser.add_subparsers(
        dest='filecoin_command',
        help='Filecoin Pin commands'
    )
    
    # filecoin-pin add
    add_parser = filecoin_subparsers.add_parser(
        'add',
        help='Pin content to Filecoin Pin',
        description='Pin a file or CID to Filecoin Pin service'
    )
    add_parser.add_argument(
        'content',
        help='File path or CID to pin'
    )
    add_parser.add_argument(
        '--name', '-n',
        help='Human-readable name for the pin'
    )
    add_parser.add_argument(
        '--description', '-d',
        help='Description for the pin'
    )
    add_parser.add_argument(
        '--tags', '-t',
        help='Comma-separated tags for categorization'
    )
    add_parser.add_argument(
        '--replication', '-r',
        type=int,
        default=3,
        help='Number of replicas (default: 3)'
    )
    add_parser.add_argument(
        '--api-key',
        help='Filecoin Pin API key (or set FILECOIN_PIN_API_KEY env var)'
    )
    add_parser.add_argument(
        '--endpoint',
        help='API endpoint URL (default: https://api.filecoin.cloud/v1)'
    )
    add_parser.add_argument(
        '--timeout',
        type=int,
        default=60,
        help='Request timeout in seconds (default: 60)'
    )
    add_parser.set_defaults(func=handle_filecoin_pin_add)
    
    # filecoin-pin ls
    ls_parser = filecoin_subparsers.add_parser(
        'ls',
        help='List pins',
        description='List all pins on Filecoin Pin service'
    )
    ls_parser.add_argument(
        '--status', '-s',
        choices=['queued', 'pinning', 'pinned', 'failed'],
        help='Filter by pin status'
    )
    ls_parser.add_argument(
        '--limit', '-l',
        type=int,
        default=100,
        help='Maximum number of results (default: 100)'
    )
    ls_parser.add_argument(
        '--api-key',
        help='Filecoin Pin API key (or set FILECOIN_PIN_API_KEY env var)'
    )
    ls_parser.set_defaults(func=handle_filecoin_pin_ls)
    
    # filecoin-pin status
    status_parser = filecoin_subparsers.add_parser(
        'status',
        help='Check pin status',
        description='Get detailed status information for a pin'
    )
    status_parser.add_argument(
        'cid',
        help='Content ID to check'
    )
    status_parser.add_argument(
        '--api-key',
        help='Filecoin Pin API key (or set FILECOIN_PIN_API_KEY env var)'
    )
    status_parser.set_defaults(func=handle_filecoin_pin_status)
    
    # filecoin-pin rm
    rm_parser = filecoin_subparsers.add_parser(
        'rm',
        help='Unpin content',
        description='Remove a pin from Filecoin Pin service'
    )
    rm_parser.add_argument(
        'cid',
        help='Content ID to unpin'
    )
    rm_parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Skip confirmation prompt'
    )
    rm_parser.add_argument(
        '--api-key',
        help='Filecoin Pin API key (or set FILECOIN_PIN_API_KEY env var)'
    )
    rm_parser.set_defaults(func=handle_filecoin_pin_rm)
    
    # filecoin-pin get
    get_parser = filecoin_subparsers.add_parser(
        'get',
        help='Retrieve pinned content',
        description='Download content from Filecoin Pin via gateways'
    )
    get_parser.add_argument(
        'cid',
        help='Content ID to retrieve'
    )
    get_parser.add_argument(
        '--output', '-o',
        help='Output file path (default: print to stdout or auto-generate)'
    )
    get_parser.add_argument(
        '--api-key',
        help='Filecoin Pin API key (or set FILECOIN_PIN_API_KEY env var)'
    )
    get_parser.set_defaults(func=handle_filecoin_pin_get)
    
    return filecoin_parser


async def main_cli():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='IPFS Kit - Filecoin Pin CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands'
    )
    
    # Setup filecoin-pin commands
    setup_filecoin_pin_parser(subparsers)
    
    args = parser.parse_args()
    
    # Execute command
    if hasattr(args, 'func'):
        return await args.func(args)
    else:
        parser.print_help()
        return 1


def main():
    """Synchronous entry point."""
    try:
        return asyncio.run(main_cli())
    except KeyboardInterrupt:
        print("\n❌ Interrupted by user")
        return 130


if __name__ == '__main__':
    sys.exit(main())
