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
import anyio
import json
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
        self._add_walrus_commands(subparsers)
        self._add_fsspec_commands(subparsers)
        self._add_graphrag_commands(subparsers)
        self._add_journal_commands(subparsers)
        self._add_state_commands(subparsers)
        self._add_audit_commands(subparsers)
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
        """Add VFS versioning and GraphRAG indexing commands."""
        vfs = subparsers.add_parser(
            "vfs",
            help="Manage VFS versioning, snapshots, and GraphRAG indexes"
        )
        vfs_sub = vfs.add_subparsers(dest="vfs_action")

        common_index = argparse.ArgumentParser(add_help=False)
        common_index.add_argument("--index-root", required=True, help="VFS GraphRAG index root directory")
        common_index.add_argument("--namespace", default="default", help="VFS namespace")
        common_index.add_argument("--storage-format", default="jsonl", choices=["jsonl", "parquet", "auto"])

        index = vfs_sub.add_parser("index", parents=[common_index], help="Index VFS GraphRAG records")
        index.add_argument("--records", help="JSON or JSONL file containing canonical VFS GraphRAG records")
        index.add_argument("--path", help="VFS path to index as an object record")
        index.add_argument("--content-id", help="Content identifier for --path")
        index.add_argument("--content-hash", help="Content hash for --path")
        index.add_argument("--backend", default="ipfs", help="Storage backend for --path")
        index.add_argument("--protocol", help="Storage protocol for --path")
        index.add_argument("--mime-type", default="application/octet-stream")
        index.add_argument("--size-bytes", type=int, default=0)
        index.add_argument("--object-type", default="file")
        index.add_argument("--tag", dest="tags", action="append", default=[])
        index.add_argument("--metadata-json", default="{}", help="JSON object metadata for --path")

        search = vfs_sub.add_parser("search", parents=[common_index], help="Search a VFS GraphRAG index")
        search.add_argument("query", nargs="?", default="")
        search.add_argument("--type", dest="search_type", default="hybrid", choices=["metadata", "vector", "hybrid", "graph"])
        search.add_argument("--top-k", type=int, default=10)
        search.add_argument("--filters-json", default="{}", help="JSON metadata filter object")
        search.add_argument("--query-vector", help="JSON array or comma-separated numeric vector")
        search.add_argument("--namespace-filter", dest="namespaces", action="append", default=[])
        search.add_argument("--backend-filter", dest="backends", action="append", default=[])
        search.add_argument("--protocol-filter", dest="protocols", action="append", default=[])
        search.add_argument("--facet", dest="facet_fields", action="append", default=[])
        search.add_argument("--hop-limit", type=int)
        search.add_argument("--entity-type", dest="entity_types", action="append", default=[])

        vfs_sub.add_parser("graphrag-status", parents=[common_index], help="Show VFS GraphRAG index status")

        export = vfs_sub.add_parser("export-index", parents=[common_index], help="Export a VFS GraphRAG bundle")
        export.add_argument("--output", required=True, help="Output bundle directory")
        export.add_argument("--filesystem-map-json", help="Optional filesystem map JSON object")
        export.add_argument("--journal-jsonl", help="Optional journal slice JSONL file")
        export.add_argument("--no-filesystem", action="store_true", help="Omit filesystem map artifact")
        export.add_argument("--no-journal", action="store_true", help="Omit journal artifact")

        import_cmd = vfs_sub.add_parser("import-index", parents=[common_index], help="Import a VFS GraphRAG bundle")
        import_cmd.add_argument("--input", required=True, help="Input bundle directory or manifest path")
        import_cmd.add_argument(
            "--mode",
            default="metadata-plus-indexes",
            choices=["metadata-only", "metadata-plus-indexes", "full-snapshot"],
        )
        import_cmd.add_argument("--skip-checksums", action="store_true", help="Skip bundle checksum verification")
        
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

    def _add_walrus_commands(self, subparsers):
        """Add Walrus fsspec commands."""
        walrus = subparsers.add_parser("walrus", help="Use the Walrus fsspec backend")
        walrus_sub = walrus.add_subparsers(dest="walrus_action")

        status = walrus_sub.add_parser("status", help="Show Walrus backend status")
        status.add_argument("--index-path")
        status.add_argument("--publisher-url")
        status.add_argument("--aggregator-url")
        status.add_argument("--delete-url")

        ls = walrus_sub.add_parser("ls", help="List index-backed Walrus paths")
        ls.add_argument("path", nargs="?", default="walrus://")
        ls.add_argument("--index-path")
        ls.add_argument("--no-detail", action="store_true")

        get = walrus_sub.add_parser("get", help="Read a Walrus logical path or blob id")
        get.add_argument("path")
        get.add_argument("--encoding", choices=["text", "base64", "hex"], default="text")
        get.add_argument("--index-path")
        get.add_argument("--aggregator-url")

        put = walrus_sub.add_parser("put", help="Write content to Walrus")
        put.add_argument("path")
        put.add_argument("content")
        put.add_argument("--encoding", choices=["text", "base64", "hex"], default="text")
        put.add_argument("--content-type")
        put.add_argument("--index-path")
        put.add_argument("--publisher-url")
        put.add_argument("--aggregator-url")

        delete = walrus_sub.add_parser("delete", aliases=["rm"], help="Delete a Walrus logical path or blob id")
        delete.add_argument("path")
        delete.add_argument("--index-path")
        delete.add_argument("--delete-url")

    def _add_fsspec_commands(self, subparsers):
        """Add fsspec protocol utility commands."""
        fsspec_parser = subparsers.add_parser("fsspec", help="Inspect and use fsspec protocol backends")
        fsspec_sub = fsspec_parser.add_subparsers(dest="fsspec_action")

        fsspec_sub.add_parser("protocols", help="List available ipfs_kit fsspec protocols")

        status = fsspec_sub.add_parser("status", help="Show backend status for a protocol")
        status.add_argument("protocol", nargs="?", default="ipfs")

        read = fsspec_sub.add_parser("read", help="Read via fsspec.open")
        read.add_argument("url")
        read.add_argument("--encoding", choices=["text", "base64", "hex"], default="text")

        write = fsspec_sub.add_parser("write", help="Write via fsspec.open")
        write.add_argument("url")
        write.add_argument("content")
        write.add_argument("--encoding", choices=["text", "base64", "hex"], default="text")

    def _add_graphrag_commands(self, subparsers):
        """Add VFS GraphRAG index commands."""
        graphrag = subparsers.add_parser("graphrag", aliases=["vfs-graphrag"], help="Search VFS GraphRAG indexes")
        graphrag_sub = graphrag.add_subparsers(dest="graphrag_action")

        status = graphrag_sub.add_parser("status", help="Show VFS GraphRAG index status")
        status.add_argument("--index-path")
        status.add_argument("--namespace", default="default")

        search = graphrag_sub.add_parser("search", help="Search the VFS GraphRAG index")
        search.add_argument("query", nargs="?", default="")
        search.add_argument("--method", choices=["search", "metadata_search", "vector_search", "hybrid_search", "graph_search", "graph_hybrid_search"], default="search")
        search.add_argument("--top-k", type=int, default=10)
        search.add_argument("--index-path")
        search.add_argument("--namespace", default="default")
        search.add_argument("--filters-json", help="JSON object of metadata filters")

        export = graphrag_sub.add_parser("export", help="Export VFS GraphRAG index records")
        export.add_argument("--index-path")
        export.add_argument("--namespace", default="default")
        export.add_argument("--output")
    
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
    
    def _add_audit_commands(self, subparsers):
        """Add audit logging and querying commands."""
        audit = subparsers.add_parser(
            "audit",
            help="Audit logging and querying operations"
        )
        audit_sub = audit.add_subparsers(dest="audit_action")
        
        # View audit events
        view = audit_sub.add_parser("view", help="View recent audit events")
        view.add_argument("--limit", type=int, default=100, help="Maximum number of events")
        view.add_argument("--event-type", help="Filter by event type")
        view.add_argument("--action", help="Filter by action")
        view.add_argument("--user-id", help="Filter by user ID")
        view.add_argument("--status", help="Filter by status")
        view.add_argument("--hours", type=int, default=24, help="Show events from last N hours")
        view.add_argument("--json", action="store_true", help="Output as JSON")
        
        # Query audit events
        query = audit_sub.add_parser("query", help="Query audit log with advanced filtering")
        query.add_argument("--start-time", help="Start time (ISO format)")
        query.add_argument("--end-time", help="End time (ISO format)")
        query.add_argument("--event-types", help="Comma-separated list of event types")
        query.add_argument("--users", help="Comma-separated list of user IDs")
        query.add_argument("--resources", help="Comma-separated list of resource IDs")
        query.add_argument("--statuses", help="Comma-separated list of statuses")
        query.add_argument("--limit", type=int, default=1000, help="Maximum number of results")
        query.add_argument("--json", action="store_true", help="Output as JSON")
        
        # Export audit logs
        export = audit_sub.add_parser("export", help="Export audit logs to file")
        export.add_argument("--format", default="json", choices=["json", "jsonl", "csv"], help="Export format")
        export.add_argument("--output", "-o", help="Output file path")
        export.add_argument("--event-type", help="Filter by event type")
        export.add_argument("--hours", type=int, default=24, help="Export events from last N hours")
        
        # Generate audit reports
        report = audit_sub.add_parser("report", help="Generate audit reports")
        report.add_argument("--type", default="summary", 
                          choices=["summary", "security", "compliance", "user_activity"],
                          help="Report type")
        report.add_argument("--hours", type=int, default=24, help="Report for last N hours")
        report.add_argument("--group-by", help="Group results by field")
        
        # Audit statistics
        stats = audit_sub.add_parser("stats", help="Get audit statistics")
        stats.add_argument("--hours", type=int, default=24, help="Statistics for last N hours")
        stats.add_argument("--json", action="store_true", help="Output as JSON")
        
        # Track operations
        track = audit_sub.add_parser("track", help="Track operation in audit log")
        track.add_argument("resource_type", choices=["backend", "vfs"], help="Resource type")
        track.add_argument("resource_id", help="Resource ID")
        track.add_argument("operation", help="Operation performed")
        track.add_argument("--user-id", help="User ID")
        track.add_argument("--path", help="Path (for VFS operations)")
        track.add_argument("--details", help="Additional details (JSON string)")
        
        # Integrity check
        audit_sub.add_parser("integrity", help="Check audit log integrity")
        
        # Retention policy
        retention = audit_sub.add_parser("retention", help="Manage retention policy")
        retention.add_argument("action", choices=["get", "set"], help="Action to perform")
        retention.add_argument("--retention-days", type=int, help="Retention period in days")
        retention.add_argument("--auto-cleanup", type=lambda x: x.lower() == 'true', 
                             help="Enable auto-cleanup (true/false)")
    
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
                if action in {"index", "search", "graphrag-status", "export-index", "import-index"}:
                    from ipfs_kit_py.cli import handle_vfs_graphrag_command
                    return await handle_vfs_graphrag_command(args)
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
            elif command in {"walrus", "fsspec", "graphrag", "vfs-graphrag"}:
                return await self._handle_feature_command(command, action, args)
            elif command == "journal":
                from ipfs_kit_py import fs_journal_cli
                return await fs_journal_cli.handle_cli_command(args)
            elif command == "audit":
                from ipfs_kit_py import audit_cli
                # Call audit CLI directly (it's synchronous)
                import sys
                sys.argv = ["audit_cli.py", action] + [str(v) for k, v in vars(args).items() if k not in ['command', 'audit_action'] and v is not None]
                return audit_cli.main()
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

    async def _handle_feature_command(self, command: str, action: str, args) -> int:
        from ipfs_kit_py.feature_exposure import (
            fsspec_protocols,
            fsspec_read,
            fsspec_status,
            fsspec_write,
            vfs_graphrag_export,
            vfs_graphrag_search,
            vfs_graphrag_status,
            walrus_delete,
            walrus_get,
            walrus_list,
            walrus_put,
            walrus_status,
        )

        payload = {key: value for key, value in vars(args).items() if value is not None}
        if "filters_json" in payload:
            payload["filters"] = json.loads(payload.pop("filters_json"))
        if "no_detail" in payload:
            payload["detail"] = not payload.pop("no_detail")

        if command == "walrus":
            handlers = {"status": walrus_status, "ls": walrus_list, "get": walrus_get, "put": walrus_put, "delete": walrus_delete, "rm": walrus_delete}
        elif command == "fsspec":
            handlers = {"protocols": fsspec_protocols, "status": fsspec_status, "read": fsspec_read, "write": fsspec_write}
        else:
            handlers = {"status": vfs_graphrag_status, "search": vfs_graphrag_search, "export": vfs_graphrag_export}

        handler = handlers.get(action)
        if handler is None:
            print(f"❌ Unknown {command} action: {action}")
            return 1
        result = handler(payload)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    
    async def run(self):
        """Parse arguments and run the dispatcher."""
        args = self.parser.parse_args()
        return await self.dispatch(args)


def main():
    """Main entry point for unified CLI."""
    dispatcher = UnifiedCLIDispatcher()
    return anyio.run(dispatcher.run)


if __name__ == "__main__":
    sys.exit(main())
