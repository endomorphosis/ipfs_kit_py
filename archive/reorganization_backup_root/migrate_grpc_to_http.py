#!/usr/bin/env python3
"""
Migration Script: gRPC to HTTP API

This script helps migrate from deprecated gRPC routing to HTTP API.
"""

import re
import os
import sys
from pathlib import Path

# Migration patterns
MIGRATION_PATTERNS = [
    # gRPC client to HTTP requests
    (
        r'from ipfs_kit_py\.routing\.grpc_client import RoutingClient',
        'import aiohttp  # Use HTTP client instead of gRPC'
    ),
    (
        r'client = await RoutingClient\.create\("([^"]+)"\)',
        r'# Use HTTP endpoint: http:///api/v1/'
    ),
    (
        r'await client\.select_backend\(',
        'async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:8080/api/v1/select-backend", json={'
    ),
    
    # gRPC server to HTTP server
    (
        r'from ipfs_kit_py\.routing\.grpc_server import GRPCServer',
        'from ipfs_kit_py.routing.http_server import HTTPRoutingServer'
    ),
    (
        r'GRPCServer\(',
        'HTTPRoutingServer('
    ),
    (
        r'port=50051',
        'port=8080  # HTTP instead of gRPC'
    )
]

def migrate_file(file_path: str) -> bool:
    """Migrate a single file from gRPC to HTTP API."""
    
    if not os.path.exists(file_path):
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Apply migration patterns
        for pattern, replacement in MIGRATION_PATTERNS:
            content = re.sub(pattern, replacement, content)
        
        # Check if changes were made
        if content != original_content:
            # Create backup
            backup_path = file_path + '.grpc_migration_backup'
            with open(backup_path, 'w') as f:
                f.write(original_content)
            
            # Write migrated content
            with open(file_path, 'w') as f:
                f.write(content)
            
            print(f"✅ Migrated {file_path} (backup: {backup_path})")
            return True
        else:
            print(f"ℹ️  No gRPC patterns found in {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error migrating {file_path}: {e}")
        return False

def main():
    """Main migration function."""
    
    print("🔄 gRPC to HTTP API Migration Tool")
    print("=" * 40)
    
    if len(sys.argv) > 1:
        # Migrate specific files
        files_to_migrate = sys.argv[1:]
    else:
        # Find Python files that might contain gRPC usage
        files_to_migrate = []
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    
                    # Check if file contains gRPC imports
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            if 'grpc' in content.lower():
                                files_to_migrate.append(file_path)
                    except:
                        pass
    
    if not files_to_migrate:
        print("ℹ️  No files found that need migration")
        return
    
    print(f"📁 Found {len(files_to_migrate)} files to migrate:")
    for file_path in files_to_migrate:
        print(f"  - {file_path}")
    
    print("\n🔄 Starting migration...")
    
    migrated_count = 0
    for file_path in files_to_migrate:
        if migrate_file(file_path):
            migrated_count += 1
    
    print(f"\n✅ Migration complete: {migrated_count}/{len(files_to_migrate)} files migrated")
    
    if migrated_count > 0:
        print("\n📝 Next steps:")
        print("1. Test your application with the HTTP API")
        print("2. Update any hardcoded gRPC endpoints")
        print("3. Install aiohttp if not already available: pip install aiohttp")
        print("4. Start HTTP server: python -m ipfs_kit_py.routing.http_server")

if __name__ == "__main__":
    main()
