#!/usr/bin/env python3
"""
Backend CLI handlers for IPFS Kit.

Provides CLI commands for managing backend configurations and pin mappings.
"""

try:
    import anyio
    HAS_ANYIO = True
except ImportError:
    HAS_ANYIO = False
    import asyncio

import asyncio
import json
from typing import Optional

# Simple Args class for CLI compatibility
class Args:
    def __init__(self):
        pass


async def handle_backend_create(args) -> int:
    """Handle backend create command."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        
        # Get backend configuration from args
        backend_name = getattr(args, 'name', None)
        backend_type = getattr(args, 'type', None)
        
        if not backend_name or not backend_type:
            print("❌ Backend name and type are required")
            return 1
        
        # Build configuration from args
        config = {}
        
        # Common backend configuration fields
        if hasattr(args, 'endpoint') and args.endpoint:
            config['endpoint'] = args.endpoint
        if hasattr(args, 'access_key') and args.access_key:
            config['access_key'] = args.access_key
        if hasattr(args, 'secret_key') and args.secret_key:
            config['secret_key'] = args.secret_key
        if hasattr(args, 'token') and args.token:
            config['token'] = args.token
        if hasattr(args, 'bucket') and args.bucket:
            config['bucket'] = args.bucket
        if hasattr(args, 'region') and args.region:
            config['region'] = args.region
        
        # Create backend configuration
        result = await backend_manager.create_backend_config(
            backend_name=backend_name,
            backend_type=backend_type,
            config=config
        )
        
        if result['success']:
            data = result['data']
            print(f"✅ Backend '{backend_name}' created successfully")
            print(f"   Type: {backend_type}")
            print(f"   Config file: {data['config_file']}")
            print(f"   Index directory: {data['index_dir']}")
            return 0
        else:
            print(f"❌ Failed to create backend: {result['error']}")
            return 1
            
    except Exception as e:
        print(f"❌ Error creating backend: {e}")
        return 1


async def handle_backend_list(args) -> int:
    """Handle backend list command."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        
        result = await backend_manager.list_backend_configs()
        
        if result['success']:
            backends = result['data']['backends']
            
            if not backends:
                print("📭 No backends configured")
                print("💡 Use 'ipfs-kit backend create' to add a backend")
                return 0
            
            print(f"🔧 Configured Backends ({len(backends)} backends):")
            print("─" * 100)
            print(f"{'Name':<20} {'Type':<15} {'Status':<10} {'Has Index':<10} {'Created':<20}")
            print("─" * 100)
            
            for backend in backends:
                status = "✅ Enabled" if backend['enabled'] else "❌ Disabled"
                has_index = "✅ Yes" if backend['has_index'] else "❌ No"
                created = backend['created_at'][:19] if backend['created_at'] else 'Unknown'
                
                print(f"{backend['name']:<20} {backend['type']:<15} {status:<10} {has_index:<10} {created:<20}")
            
            print("─" * 100)
            print(f"✅ Total: {len(backends)} backend(s)")
            
            return 0
        else:
            print(f"❌ Failed to list backends: {result['error']}")
            return 1
            
    except Exception as e:
        print(f"❌ Error listing backends: {e}")
        return 1


async def handle_backend_show(args) -> int:
    """Handle backend show command."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        backend_name = getattr(args, 'name', None)
        
        if not backend_name:
            print("❌ Backend name is required")
            return 1
        
        result = await backend_manager.get_backend_config(backend_name)
        
        if result['success']:
            config = result['data']['backend_config']
            
            print(f"🔧 Backend Configuration: {backend_name}")
            print("═" * 60)
            print(f"Name: {config.get('name', 'Unknown')}")
            print(f"Type: {config.get('type', 'Unknown')}")
            print(f"Status: {'✅ Enabled' if config.get('enabled', True) else '❌ Disabled'}")
            print(f"Created: {config.get('created_at', 'Unknown')}")
            print(f"Updated: {config.get('updated_at', 'Unknown')}")
            
            print(f"\n📋 Configuration:")
            backend_config = config.get('config', {})
            for key, value in backend_config.items():
                # Hide sensitive values
                if any(sensitive in key.lower() for sensitive in ['key', 'secret', 'token', 'password']):
                    value = f"{'*' * min(8, len(str(value)))}"
                print(f"   {key}: {value}")
            
            # Show pin mapping stats
            mapping_result = await backend_manager.list_pin_mappings(backend_name)
            if mapping_result['success']:
                total_pins = mapping_result['data']['total_mappings']
                print(f"\n📌 Pin Mappings: {total_pins} pin(s)")
            
            return 0
        else:
            print(f"❌ Backend '{backend_name}' not found: {result['error']}")
            return 1
            
    except Exception as e:
        print(f"❌ Error showing backend: {e}")
        return 1


async def handle_backend_update(args) -> int:
    """Handle backend update command."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        backend_name = getattr(args, 'name', None)
        
        if not backend_name:
            print("❌ Backend name is required")
            return 1
        
        # Build updates from args
        updates = {}
        config_updates = {}
        
        if hasattr(args, 'enabled') and args.enabled is not None:
            updates['enabled'] = args.enabled
        if hasattr(args, 'endpoint') and args.endpoint:
            config_updates['endpoint'] = args.endpoint
        if hasattr(args, 'token') and args.token:
            config_updates['token'] = args.token
        if hasattr(args, 'bucket') and args.bucket:
            config_updates['bucket'] = args.bucket
        if hasattr(args, 'region') and args.region:
            config_updates['region'] = args.region
        
        if config_updates:
            updates['config'] = config_updates
        
        if not updates:
            print("❌ No updates specified")
            return 1
        
        result = await backend_manager.update_backend_config(backend_name, updates)
        
        if result['success']:
            print(f"✅ Backend '{backend_name}' updated successfully")
            print(f"   Updated at: {result['data']['updated_at']}")
            return 0
        else:
            print(f"❌ Failed to update backend: {result['error']}")
            return 1
            
    except Exception as e:
        print(f"❌ Error updating backend: {e}")
        return 1


async def handle_backend_remove(args) -> int:
    """Handle backend remove command."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        backend_name = getattr(args, 'name', None)
        
        if not backend_name:
            print("❌ Backend name is required")
            return 1
        
        # Confirm removal
        force = getattr(args, 'force', False)
        if not force:
            print(f"⚠️  This will remove backend '{backend_name}' and all its pin mappings.")
            response = input("Continue? (y/N): ")
            if response.lower() != 'y':
                print("❌ Removal cancelled")
                return 1
        
        result = await backend_manager.remove_backend_config(backend_name)
        
        if result['success']:
            print(f"✅ Backend '{backend_name}' removed successfully")
            print(f"   Removed at: {result['data']['removed_at']}")
            return 0
        else:
            print(f"❌ Failed to remove backend: {result['error']}")
            return 1
            
    except Exception as e:
        print(f"❌ Error removing backend: {e}")
        return 1


async def handle_backend_pin_add(args) -> int:
    """Handle backend pin add command."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        backend_name = getattr(args, 'backend', None)
        cid = getattr(args, 'cid', None)
        car_file_path = getattr(args, 'car_path', None)
        
        if not backend_name or not cid or not car_file_path:
            print("❌ Backend name, CID, and CAR file path are required")
            return 1
        
        # Optional metadata
        metadata = {}
        if hasattr(args, 'name') and args.name:
            metadata['name'] = args.name
        if hasattr(args, 'description') and args.description:
            metadata['description'] = args.description
        
        result = await backend_manager.add_pin_mapping(
            backend_name=backend_name,
            cid=cid,
            car_file_path=car_file_path,
            metadata=metadata
        )
        
        if result['success']:
            data = result['data']
            print(f"✅ Pin mapping added successfully")
            print(f"   CID: {data['cid']}")
            print(f"   Backend: {data['backend_name']}")
            print(f"   CAR file: {data['car_file_path']}")
            return 0
        else:
            print(f"❌ Failed to add pin mapping: {result['error']}")
            return 1
            
    except Exception as e:
        print(f"❌ Error adding pin mapping: {e}")
        return 1


async def handle_backend_pin_list(args) -> int:
    """Handle backend pin list command."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        backend_name = getattr(args, 'backend', None)
        limit = getattr(args, 'limit', None)
        
        if not backend_name:
            print("❌ Backend name is required")
            return 1
        
        result = await backend_manager.list_pin_mappings(backend_name, limit)
        
        if result['success']:
            mappings = result['data']['mappings']
            
            if not mappings:
                print(f"📭 No pin mappings found for backend '{backend_name}'")
                return 0
            
            print(f"📌 Pin Mappings for '{backend_name}' ({len(mappings)} pins):")
            print("─" * 120)
            print(f"{'CID':<20} {'CAR File Path':<50} {'Status':<10} {'Created':<20}")
            print("─" * 120)
            
            for mapping in mappings:
                cid_short = mapping['cid'][:18] + '...' if len(mapping['cid']) > 20 else mapping['cid']
                car_path_short = mapping['car_file_path'][:48] + '...' if len(mapping['car_file_path']) > 50 else mapping['car_file_path']
                created = mapping['created_at'][:19] if mapping['created_at'] else 'Unknown'
                status = mapping.get('status', 'unknown')
                
                print(f"{cid_short:<20} {car_path_short:<50} {status:<10} {created:<20}")
            
            print("─" * 120)
            print(f"✅ Total: {len(mappings)} pin mapping(s)")
            
            return 0
        else:
            print(f"❌ Failed to list pin mappings: {result['error']}")
            return 1
            
    except Exception as e:
        print(f"❌ Error listing pin mappings: {e}")
        return 1


async def handle_backend_pin_find(args) -> int:
    """Handle backend pin find command."""
    try:
        from ipfs_kit_py.backend_manager import get_backend_manager
        
        backend_manager = get_backend_manager()
        cid = getattr(args, 'cid', None)
        
        if not cid:
            print("❌ CID is required")
            return 1
        
        result = await backend_manager.find_pin_on_backends(cid)
        
        if result['success']:
            locations = result['data']['backend_locations']
            
            if not locations:
                print(f"📭 Pin '{cid}' not found on any configured backends")
                return 0
            
            print(f"📌 Pin '{cid}' found on {len(locations)} backend(s):")
            print("─" * 100)
            print(f"{'Backend':<20} {'CAR File Path':<50} {'Status':<10} {'Created':<20}")
            print("─" * 100)
            
            for location in locations:
                backend_name = location['backend_name']
                car_path_short = location['car_file_path'][:48] + '...' if len(location['car_file_path']) > 50 else location['car_file_path']
                status = location.get('status', 'unknown')
                created = location['created_at'][:19] if location['created_at'] else 'Unknown'
                
                print(f"{backend_name:<20} {car_path_short:<50} {status:<10} {created:<20}")
            
            print("─" * 100)
            print(f"✅ Total: {len(locations)} location(s)")
            
            return 0
        else:
            print(f"❌ Failed to find pin: {result['error']}")
            return 1
            
    except Exception as e:
        print(f"❌ Error finding pin: {e}")
        return 1
