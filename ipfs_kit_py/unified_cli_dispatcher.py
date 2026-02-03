#!/usr/bin/env python3
"""
Unified CLI Dispatcher for IPFS Kit.

This module provides a unified command-line interface that integrates
all standalone CLI tools following the architecture pattern:
  Core Module → CLI Integration → Unified CLI Command

Architecture:
  ipfs_kit_py/module.py (core)
      ↓
  ipfs_kit_py/module_cli.py (CLI handlers)
      ↓
  ipfs-kit <subcommand> (unified entry point)
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class UnifiedCLIDispatcher:
    """Unified CLI dispatcher integrating all IPFS Kit CLI tools."""
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create the unified argument parser with all subcommands."""
        parser = argparse.ArgumentParser(
            prog="ipfs-kit",
            description="IPFS Kit - Unified CLI for IPFS operations",
            formatter_class=argparse.RawTextHelpFormatter
        )
        
        subparsers = parser.add_subparsers(dest="command", help="Available commands")
        
        # Add all subcommand parsers
        self._add_bucket_commands(subparsers)
        self._add_vfs_commands(subparsers)
        self._add_wal_commands(subparsers)
        self._add_pin_commands(subparsers)
        self._add_backend_commands(subparsers)
        self._add_journal_commands(subparsers)
        self._add_state_commands(subparsers)
        self._add_daemon_commands(subparsers)
        
        return parser
    
    def _add_bucket_commands(self, subparsers):
        """Add bucket VFS management commands."""
        bucket = subparsers.add_parser(
            "bucket",
            help="Manage multi-bucket virtual filesystems"
        )
        bucket_sub = bucket.add_subparsers(dest="bucket_action")
        
        # Create bucket
        create = bucket_sub.add_parser("create", help="Create a new bucket")
        create.add_argument("name", help="Bucket name")
        create.add_argument("--type", choices=["general", "dataset", "knowledge", "media", "archive", "temp"],
                          default="general", help="Bucket type")
        create.add_argument("--structure", choices=["flat", "hierarchical", "temporal", "categorical"],
                          default="hierarchical", help="VFS structure type")
        
        # List buckets
        bucket_sub.add_parser("list", help="List all buckets")
        
        # Get bucket info
        info = bucket_sub.add_parser("info", help="Get bucket information")
        info.add_argument("name", help="Bucket name")
        
        # Delete bucket
        delete = bucket_sub.add_parser("delete", help="Delete a bucket")
        delete.add_argument("name", help="Bucket name")
        delete.add_argument("--force", action="store_true", help="Force delete non-empty bucket")
        
        # Upload to bucket
        upload = bucket_sub.add_parser("upload", help="Upload file to bucket")
        upload.add_argument("bucket", help="Bucket name")
        upload.add_argument("source", help="Source file path")
        upload.add_argument("--dest", help="Destination path in bucket")
        
        # Download from bucket
        download = bucket_sub.add_parser("download", help="Download file from bucket")
        download.add_argument("bucket", help="Bucket name")
        download.add_argument("source", help="Source path in bucket")
        download.add_argument("--dest", help="Destination file path")
        
        # List bucket contents
        ls = bucket_sub.add_parser("ls", help="List bucket contents")
        ls.add_argument("bucket", help="Bucket name")
        ls.add_argument("--path", default="/", help="Path within bucket")
    
    def _add_vfs_commands(self, subparsers):
        """Add VFS versioning commands."""
        vfs = subparsers.add_parser(
            "vfs",
            help="Manage VFS versioning and snapshots"
        )
        vfs_sub = vfs.add_subparsers(dest="vfs_action")
        
        # Create snapshot
        snapshot = vfs_sub.add_parser("snapshot", help="Create VFS snapshot")
        snapshot.add_argument("bucket", help="Bucket name")
        snapshot.add_argument("--message", help="Snapshot description")
        
        # List versions
        versions = vfs_sub.add_parser("versions", help="List VFS versions")
        versions.add_argument("bucket", help="Bucket name")
        
        # Restore version
        restore = vfs_sub.add_parser("restore", help="Restore VFS version")
        restore.add_argument("bucket", help="Bucket name")
        restore.add_argument("version", help="Version ID or tag")
        
        # Compare versions
        diff = vfs_sub.add_parser("diff", help="Compare VFS versions")
        diff.add_argument("bucket", help="Bucket name")
        diff.add_argument("version1", help="First version ID")
        diff.add_argument("version2", help="Second version ID")
    
    def _add_wal_commands(self, subparsers):
        """Add Write-Ahead Log management commands."""
        wal = subparsers.add_parser(
            "wal",
            help="Manage Write-Ahead Log operations"
        )
        wal_sub = wal.add_subparsers(dest="wal_action")
        
        # WAL status
        wal_sub.add_parser("status", help="Show WAL statistics")
        
        # List operations
        list_ops = wal_sub.add_parser("list", help="List WAL operations")
        list_ops.add_argument("--status", choices=["pending", "completed", "failed", "all"],
                            default="pending", help="Filter by status")
        list_ops.add_argument("--limit", type=int, default=50, help="Maximum number of operations")
        
        # Show operation details
        show = wal_sub.add_parser("show", help="Show operation details")
        show.add_argument("operation_id", help="Operation ID")
        
        # Wait for operation
        wait = wal_sub.add_parser("wait", help="Wait for operation completion")
        wait.add_argument("operation_id", help="Operation ID")
        wait.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
        
        # Cleanup old operations
        cleanup = wal_sub.add_parser("cleanup", help="Clean up old operations")
        cleanup.add_argument("--age", type=int, default=7, help="Age in days")
    
    def _add_pin_commands(self, subparsers):
        """Add pin management commands."""
        pin = subparsers.add_parser(
            "pin",
            help="Manage IPFS pins"
        )
        pin_sub = pin.add_subparsers(dest="pin_action")
        
        # Add pin
        add = pin_sub.add_parser("add", help="Add a new pin")
        add.add_argument("cid", help="Content ID to pin")
        add.add_argument("--name", help="Pin name")
        add.add_argument("--recursive", action="store_true", help="Recursive pin")
        
        # Remove pin
        rm = pin_sub.add_parser("rm", help="Remove a pin")
        rm.add_argument("cid", help="Content ID to unpin")
        
        # List pins
        ls = pin_sub.add_parser("ls", help="List pins")
        ls.add_argument("--type", choices=["direct", "recursive", "indirect", "all"],
                       default="all", help="Pin type filter")
        
        # Pin info
        info = pin_sub.add_parser("info", help="Get pin information")
        info.add_argument("cid", help="Content ID")
    
    def _add_backend_commands(self, subparsers):
        """Add backend management commands."""
        backend = subparsers.add_parser(
            "backend",
            help="Manage storage backends"
        )
        backend_sub = backend.add_subparsers(dest="backend_action")
        
        # Create backend
        create = backend_sub.add_parser("create", help="Create a backend")
        create.add_argument("name", help="Backend name")
        create.add_argument("type", help="Backend type (s3, ipfs, storj, etc.)")
        create.add_argument("--endpoint", help="Backend endpoint URL")
        create.add_argument("--access-key", help="Access key")
        create.add_argument("--secret-key", help="Secret key")
        create.add_argument("--bucket", help="Bucket name")
        create.add_argument("--region", help="Region")
        
        # List backends
        backend_sub.add_parser("list", help="List all backends")
        
        # Get backend info
        info = backend_sub.add_parser("info", help="Get backend information")
        info.add_argument("name", help="Backend name")
        
        # Update backend
        update = backend_sub.add_parser("update", help="Update backend configuration")
        update.add_argument("name", help="Backend name")
        update.add_argument("--endpoint", help="Backend endpoint URL")
        update.add_argument("--access-key", help="Access key")
        update.add_argument("--secret-key", help="Secret key")
        
        # Delete backend
        delete = backend_sub.add_parser("delete", help="Delete a backend")
        delete.add_argument("name", help="Backend name")
        
        # Test backend
        test = backend_sub.add_parser("test", help="Test backend connection")
        test.add_argument("name", help="Backend name")
    
    def _add_journal_commands(self, subparsers):
        """Add filesystem journal commands."""
        journal = subparsers.add_parser(
            "journal",
            help="Manage filesystem journal"
        )
        journal_sub = journal.add_subparsers(dest="journal_action")
        
        # Show journal status
        journal_sub.add_parser("status", help="Show journal status")
        
        # List journal entries
        list_entries = journal_sub.add_parser("list", help="List journal entries")
        list_entries.add_argument("--limit", type=int, default=50, help="Maximum entries")
        list_entries.add_argument("--operation", help="Filter by operation type")
        
        # Replay journal
        replay = journal_sub.add_parser("replay", help="Replay journal entries")
        replay.add_argument("--from-seq", type=int, help="Start sequence number")
        replay.add_argument("--to-seq", type=int, help="End sequence number")
        
        # Compact journal
        compact = journal_sub.add_parser("compact", help="Compact journal")
        compact.add_argument("--keep-days", type=int, default=30, help="Days to keep")
    
    def _add_state_commands(self, subparsers):
        """Add state management commands."""
        state = subparsers.add_parser(
            "state",
            help="Manage IPFS Kit state"
        )
        state_sub = state.add_subparsers(dest="state_action")
        
        # Show state
        state_sub.add_parser("show", help="Show current state")
        
        # Export state
        export = state_sub.add_parser("export", help="Export state")
        export.add_argument("output", help="Output file path")
        export.add_argument("--format", choices=["json", "yaml"], default="json")
        
        # Import state
        import_cmd = state_sub.add_parser("import", help="Import state")
        import_cmd.add_argument("input", help="Input file path")
        
        # Reset state
        reset = state_sub.add_parser("reset", help="Reset state")
        reset.add_argument("--confirm", action="store_true", help="Confirm reset")
    
    def _add_daemon_commands(self, subparsers):
        """Add daemon management commands."""
        daemon = subparsers.add_parser(
            "daemon",
            help="Manage IPFS Kit daemon"
        )
        daemon_sub = daemon.add_subparsers(dest="daemon_action")
        
        # Start daemon
        start = daemon_sub.add_parser("start", help="Start daemon")
        start.add_argument("--port", type=int, default=9999, help="Daemon port")
        start.add_argument("--host", default="0.0.0.0", help="Daemon host")
        start.add_argument("--debug", action="store_true", help="Debug mode")
        
        # Stop daemon
        stop = daemon_sub.add_parser("stop", help="Stop daemon")
        stop.add_argument("--port", type=int, default=9999, help="Daemon port")
        
        # Daemon status
        status = daemon_sub.add_parser("status", help="Show daemon status")
        status.add_argument("--port", type=int, default=9999, help="Daemon port")
    
    async def dispatch(self, args):
        """Dispatch command to appropriate handler."""
        if not args.command:
            self.parser.print_help()
            return 0  # Displaying help is not an error
        
        # Route to appropriate handler
        command = args.command
        action = getattr(args, f"{command}_action", None)
        
        if not action:
            print(f"❌ No action specified for {command}")
            return 1
        
        # Import and call the appropriate handler
        try:
            if command == "bucket":
                from ipfs_kit_py import bucket_vfs_cli
                return await bucket_vfs_cli.handle_cli_command(args)
            elif command == "vfs":
                from ipfs_kit_py import vfs_version_cli
                return await vfs_version_cli.handle_cli_command(args)
            elif command == "wal":
                from ipfs_kit_py import wal_cli
                cli = wal_cli.WALCommandLine()
                return await cli.handle_command(args)
            elif command == "pin":
                from ipfs_kit_py import simple_pin_cli
                return await simple_pin_cli.handle_cli_command(args)
            elif command == "backend":
                from ipfs_kit_py import backend_cli
                handler_name = f"handle_backend_{action}"
                handler = getattr(backend_cli, handler_name, None)
                if handler:
                    return await handler(args)
                else:
                    print(f"❌ Unknown backend action: {action}")
                    return 1
            elif command == "journal":
                from ipfs_kit_py import fs_journal_cli
                return await fs_journal_cli.handle_cli_command(args)
            elif command == "state":
                from ipfs_kit_py import state_cli
                return await state_cli.handle_cli_command(args)
            elif command == "daemon":
                from ipfs_kit_py import daemon_cli
                return await daemon_cli.handle_cli_command(args)
            else:
                print(f"❌ Unknown command: {command}")
                return 1
        except ImportError as e:
            logger.error(f"Failed to import handler for {command}: {e}")
            print(f"❌ Command '{command}' is not available (missing dependencies)")
            return 1
        except Exception as e:
            logger.error(f"Error executing {command} {action}: {e}", exc_info=True)
            print(f"❌ Error: {e}")
            return 1
    
    async def run(self):
        """Parse arguments and run the dispatcher."""
        args = self.parser.parse_args()
        return await self.dispatch(args)


def main():
    """Main entry point for unified CLI."""
    dispatcher = UnifiedCLIDispatcher()
    return asyncio.run(dispatcher.run())


if __name__ == "__main__":
    sys.exit(main())
