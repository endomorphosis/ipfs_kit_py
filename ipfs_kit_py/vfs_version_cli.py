"""
CLI interface for VFS version tracking system.

Provides Git-like commands for managing filesystem versions:
- vfs init: Initialize version tracking
- vfs status: Show current filesystem status
- vfs commit: Create version snapshot
- vfs log: Show version history
- vfs checkout: Checkout specific version
- vfs diff: Show changes between versions
"""

import argparse
import anyio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# VFS version tracker imports
try:
    from ipfs_kit_py.vfs_version_tracker import (
        get_global_vfs_tracker,
        auto_version_filesystem,
        get_vfs_status,
        get_vfs_history
    )
    VFS_TRACKER_AVAILABLE = True
except ImportError:
    VFS_TRACKER_AVAILABLE = False

# IPFS Kit imports
try:
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    IPFS_API_AVAILABLE = True
except ImportError:
    IPFS_API_AVAILABLE = False
    IPFSSimpleAPI = None

def create_result_dict(success: bool, **kwargs):
    return {"success": success, **kwargs}


class VFSVersionCLI:
    """CLI interface for VFS version tracking."""
    
    def __init__(self):
        """Initialize VFS version CLI."""
        self.vfs_tracker = None
        self.ipfs_client = None
    
    async def _ensure_tracker(self, vfs_root: Optional[str] = None):
        """Ensure VFS tracker is initialized."""
        if not VFS_TRACKER_AVAILABLE:
            print("ERROR: VFS version tracker not available")
            sys.exit(1)
        
        if not self.vfs_tracker:
            try:
                # Initialize IPFS client
                if not self.ipfs_client and IPFS_API_AVAILABLE:
                    try:
                        self.ipfs_client = IPFSSimpleAPI()
                    except Exception as e:
                        print(f"Warning: Could not initialize IPFS client: {e}")
                        self.ipfs_client = None
                
                # Initialize tracker
                self.vfs_tracker = get_global_vfs_tracker(
                    vfs_root=vfs_root,
                    ipfs_client=self.ipfs_client
                )
                
            except Exception as e:
                print(f"ERROR: Failed to initialize VFS tracker: {e}")
                sys.exit(1)
    
    async def cmd_init(self, args) -> int:
        """Initialize VFS version tracking in the specified directory."""
        print(f"Initializing VFS version tracking in {args.directory or '~/.ipfs_kit'}")
        
        try:
            await self._ensure_tracker(vfs_root=args.directory)
            
            # Get initial status
            status_result = await self.vfs_tracker.get_filesystem_status()
            
            if status_result["success"]:
                print(f"✓ VFS version tracking initialized")
                print(f"  - VFS root: {status_result['vfs_root']}")
                print(f"  - Current HEAD: {status_result['current_head'][:12]}...")
                print(f"  - Auto-versioning: {'enabled' if status_result['auto_versioning'] else 'disabled'}")
                
                # Create initial commit if filesystem has content
                if status_result.get("has_uncommitted_changes", False):
                    print("\nCreating initial commit...")
                    commit_result = await self.vfs_tracker.create_version_snapshot(
                        commit_message="Initial filesystem state",
                        author="VFS-CLI"
                    )
                    
                    if commit_result["success"]:
                        print(f"✓ Initial commit created: {commit_result['version_cid'][:12]}...")
                    else:
                        print(f"✗ Failed to create initial commit: {commit_result.get('error', 'Unknown error')}")
                
                return 0
            else:
                print(f"✗ Failed to initialize VFS tracking: {status_result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"✗ Error initializing VFS tracking: {e}")
            return 1
    
    async def cmd_status(self, args) -> int:
        """Show current VFS status."""
        try:
            await self._ensure_tracker(vfs_root=args.directory)
            
            print("VFS Status:")
            print("=" * 50)
            
            status_result = await self.vfs_tracker.get_filesystem_status()
            
            if status_result["success"]:
                print(f"VFS Root: {status_result['vfs_root']}")
                print(f"Current HEAD: {status_result['current_head'][:12]}...")
                print(f"Current Hash: {status_result['current_filesystem_hash'][:12]}...")
                
                if status_result.get("has_uncommitted_changes", False):
                    print("📝 Changes detected (use 'vfs commit' to create snapshot)")
                else:
                    print("✓ No changes detected")
                
                print(f"Auto-versioning: {'🟢 enabled' if status_result['auto_versioning'] else '🔴 disabled'}")
                
                # Show recent versions
                recent_versions = status_result.get("recent_versions", [])
                if recent_versions:
                    print(f"\nRecent Versions ({len(recent_versions)}):")
                    for i, version in enumerate(recent_versions[:5]):
                        created_at = version.get("created_at", "Unknown")
                        if isinstance(created_at, str):
                            try:
                                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
                            except:
                                pass
                        
                        print(f"  {version.get('version_cid', 'Unknown')[:12]}... - {created_at}")
                        print(f"    {version.get('commit_message', 'No message')} ({version.get('file_count', 0)} files)")
                        if i == 0:
                            print("    ^HEAD")
                
                return 0
            else:
                print(f"✗ Failed to get VFS status: {status_result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"✗ Error getting VFS status: {e}")
            return 1
    
    async def cmd_commit(self, args) -> int:
        """Create a new version snapshot."""
        try:
            await self._ensure_tracker(vfs_root=args.directory)
            
            message = args.message or "VFS CLI commit"
            author = args.author or "VFS-CLI"
            
            print(f"Creating version snapshot: {message}")
            
            commit_result = await self.vfs_tracker.create_version_snapshot(
                commit_message=message,
                author=author,
                force=args.force
            )
            
            if commit_result["success"]:
                print(f"✓ Version snapshot created")
                print(f"  - Version CID: {commit_result['version_cid']}")
                print(f"  - Parent CID: {commit_result['parent_cid']}")
                print(f"  - Files: {commit_result['file_count']}")
                print(f"  - Total Size: {commit_result['total_size']:,} bytes")
                print(f"  - CAR File: {commit_result['car_file_cid']}")
                return 0
            else:
                print(f"✗ Failed to create snapshot: {commit_result.get('error', 'Unknown error')}")
                if "No changes detected" in commit_result.get('message', ''):
                    print("  (Use --force to create snapshot anyway)")
                return 1
                
        except Exception as e:
            print(f"✗ Error creating version snapshot: {e}")
            return 1
    
    async def cmd_log(self, args) -> int:
        """Show version history."""
        try:
            await self._ensure_tracker(vfs_root=args.directory)
            
            print(f"VFS Version History (showing {args.limit} entries):")
            print("=" * 60)
            
            history_result = await self.vfs_tracker.get_version_history(limit=args.limit)
            
            if history_result["success"]:
                versions = history_result.get("versions", [])
                
                if not versions:
                    print("No versions found")
                    return 0
                
                for i, version in enumerate(versions):
                    # Format timestamp
                    created_at = version.get("created_at", "Unknown")
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            created_at = created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                        except:
                            pass
                    
                    print(f"Commit: {version.get('version_cid', 'Unknown')}")
                    print(f"Parent: {version.get('parent_cid', 'None')}")
                    print(f"Author: {version.get('author', 'Unknown')}")
                    print(f"Date:   {created_at}")
                    print(f"Files:  {version.get('file_count', 0)} ({version.get('total_size', 0):,} bytes)")
                    print(f"CAR:    {version.get('car_file_cid', 'None')}")
                    print(f"")
                    print(f"    {version.get('commit_message', 'No message')}")
                    
                    if i == 0:
                        print("    ^HEAD")
                    
                    print("")
                
                return 0
            else:
                print(f"✗ Failed to get version history: {history_result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"✗ Error getting version history: {e}")
            return 1
    
    async def cmd_checkout(self, args) -> int:
        """Checkout a specific version."""
        try:
            await self._ensure_tracker(vfs_root=args.directory)
            
            version_cid = args.version_cid
            print(f"Checking out version: {version_cid}")
            
            checkout_result = await self.vfs_tracker.checkout_version(version_cid)
            
            if checkout_result["success"]:
                print(f"✓ Checked out version {version_cid}")
                print(f"  - HEAD now points to: {checkout_result['version_cid']}")
                return 0
            else:
                print(f"✗ Failed to checkout version: {checkout_result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"✗ Error checking out version: {e}")
            return 1
    
    async def cmd_scan(self, args) -> int:
        """Scan filesystem and show what would be included in next commit."""
        try:
            await self._ensure_tracker(vfs_root=args.directory)
            
            print("Scanning filesystem...")
            
            filesystem_state = await self.vfs_tracker.scan_filesystem(
                include_buckets=not args.no_buckets,
                include_metadata=True
            )
            
            print(f"✓ Filesystem scan complete")
            print(f"  - Files found: {len(filesystem_state['files'])}")
            print(f"  - Buckets found: {len(filesystem_state['buckets'])}")
            print(f"  - Total size: {filesystem_state['metadata']['total_size']:,} bytes")
            
            if args.verbose:
                print("\nFiles by bucket:")
                bucket_files = {}
                for file_info in filesystem_state['files']:
                    bucket = file_info.get('bucket_name', 'unknown')
                    if bucket not in bucket_files:
                        bucket_files[bucket] = []
                    bucket_files[bucket].append(file_info)
                
                for bucket, files in bucket_files.items():
                    print(f"  {bucket}: {len(files)} files")
                    if args.verbose and len(files) <= 10:
                        for file_info in files[:10]:
                            print(f"    - {file_info['file_path']} ({file_info['file_size']} bytes)")
                        if len(files) > 10:
                            print(f"    ... and {len(files) - 10} more files")
            
            # Compute filesystem hash
            fs_hash = await self.vfs_tracker.compute_filesystem_hash(filesystem_state)
            print(f"  - Filesystem hash: {fs_hash}")
            
            return 0
            
        except Exception as e:
            print(f"✗ Error scanning filesystem: {e}")
            return 1
    
    async def cmd_auto_commit(self, args) -> int:
        """Automatically commit if changes are detected."""
        try:
            message = args.message or f"Auto-commit {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            print("Checking for changes and auto-committing...")
            
            result = await auto_version_filesystem(
                commit_message=message,
                force=args.force
            )
            
            if result["success"]:
                print(f"✓ Auto-commit successful")
                print(f"  - Version CID: {result['version_cid']}")
                print(f"  - Files: {result['file_count']}")
                return 0
            else:
                error_msg = result.get('error', result.get('message', 'Unknown error'))
                if "No changes detected" in error_msg:
                    print("✓ No changes detected - no commit needed")
                    return 0
                else:
                    print(f"✗ Auto-commit failed: {error_msg}")
                    return 1
                    
        except Exception as e:
            print(f"✗ Error during auto-commit: {e}")
            return 1


def create_vfs_version_parser(subparsers):
    """Create VFS version tracking CLI parser."""
    
    # VFS version main command
    vfs_parser = subparsers.add_parser(
        'vfs',
        help='VFS version tracking commands (Git-like)',
        description='Git-like version tracking for virtual filesystems using IPFS CIDs'
    )
    
    # Global VFS options
    vfs_parser.add_argument(
        '--directory', '-d',
        type=str,
        help='VFS root directory (default: ~/.ipfs_kit)'
    )
    
    # VFS subcommands
    vfs_subparsers = vfs_parser.add_subparsers(dest='vfs_command', help='VFS commands')
    
    # vfs init
    init_parser = vfs_subparsers.add_parser(
        'init',
        help='Initialize VFS version tracking'
    )
    init_parser.set_defaults(
        func=lambda args: anyio.run(handle_vfs_version_command(args))
    )
    
    # vfs status
    status_parser = vfs_subparsers.add_parser(
        'status',
        help='Show VFS status and recent history'
    )
    status_parser.set_defaults(
        func=lambda args: anyio.run(handle_vfs_version_command(args))
    )
    
    # vfs commit
    commit_parser = vfs_subparsers.add_parser(
        'commit',
        help='Create version snapshot'
    )
    commit_parser.add_argument(
        '--message', '-m',
        type=str,
        help='Commit message'
    )
    commit_parser.add_argument(
        '--author', '-a',
        type=str,
        help='Commit author'
    )
    commit_parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force commit even if no changes detected'
    )
    commit_parser.set_defaults(
        func=lambda args: anyio.run(handle_vfs_version_command(args))
    )
    
    # vfs log
    log_parser = vfs_subparsers.add_parser(
        'log',
        help='Show version history'
    )
    log_parser.add_argument(
        '--limit', '-n',
        type=int,
        default=10,
        help='Number of versions to show (default: 10)'
    )
    log_parser.set_defaults(
        func=lambda args: anyio.run(handle_vfs_version_command(args))
    )
    
    # vfs checkout
    checkout_parser = vfs_subparsers.add_parser(
        'checkout',
        help='Checkout specific version'
    )
    checkout_parser.add_argument(
        'version_cid',
        type=str,
        help='Version CID to checkout'
    )
    checkout_parser.set_defaults(
        func=lambda args: anyio.run(handle_vfs_version_command(args))
    )
    
    # vfs scan
    scan_parser = vfs_subparsers.add_parser(
        'scan',
        help='Scan filesystem and show what would be committed'
    )
    scan_parser.add_argument(
        '--no-buckets',
        action='store_true',
        help='Exclude bucket VFS from scan'
    )
    scan_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed file listing'
    )
    scan_parser.set_defaults(
        func=lambda args: anyio.run(handle_vfs_version_command(args))
    )
    
    # vfs auto-commit
    auto_commit_parser = vfs_subparsers.add_parser(
        'auto-commit',
        help='Automatically commit if changes are detected'
    )
    auto_commit_parser.add_argument(
        '--message', '-m',
        type=str,
        help='Commit message'
    )
    auto_commit_parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force commit even if no changes detected'
    )
    auto_commit_parser.set_defaults(
        func=lambda args: anyio.run(handle_vfs_version_command(args))
    )
    
    # Set default handler for main vfs command
    vfs_parser.set_defaults(
        func=lambda args: anyio.run(handle_vfs_version_command(args))
    )
    
    return vfs_parser


async def handle_vfs_version_command(args) -> int:
    """Handle VFS version tracking commands."""
    if not hasattr(args, 'vfs_command') or not args.vfs_command:
        print("Error: No VFS command specified. Use 'vfs --help' for available commands.")
        return 1
    
    cli = VFSVersionCLI()
    
    command_handlers = {
        'init': cli.cmd_init,
        'status': cli.cmd_status,
        'commit': cli.cmd_commit,
        'log': cli.cmd_log,
        'checkout': cli.cmd_checkout,
        'scan': cli.cmd_scan,
        'auto-commit': cli.cmd_auto_commit
    }
    
    handler = command_handlers.get(args.vfs_command)
    if not handler:
        print(f"Error: Unknown VFS command '{args.vfs_command}'")
        return 1
    
    try:
        return await handler(args)
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 130
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        logger.exception("Unexpected error in VFS command")
        return 1


# Standalone script support
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="VFS Version Tracking CLI")
    subparsers = parser.add_subparsers(dest='command')
    
    create_vfs_version_parser(subparsers)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'vfs':
        exit_code = anyio.run(handle_vfs_version_command(args))
        sys.exit(exit_code)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)
