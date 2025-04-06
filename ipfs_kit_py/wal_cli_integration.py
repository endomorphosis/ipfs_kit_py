#!/usr/bin/env python3
"""
Integration module for WAL CLI with the main IPFS Kit CLI.

This module provides functions to integrate the WAL commands
with the main CLI interface.
"""

import argparse
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from .high_level_api import IPFSSimpleAPI

# Configure logging
logger = logging.getLogger(__name__)

def register_wal_commands(subparsers):
    """
    Register WAL-related commands with the CLI parser.
    
    Args:
        subparsers: Subparser object from argparse
    """
    # WAL command group
    wal_parser = subparsers.add_parser(
        "wal",
        help="WAL (Write-Ahead Log) management commands",
    )
    wal_subparsers = wal_parser.add_subparsers(dest="wal_command", help="WAL command to execute")
    
    # WAL status command
    status_parser = wal_subparsers.add_parser(
        "status",
        help="Show WAL status and statistics",
    )
    
    # WAL list command
    list_parser = wal_subparsers.add_parser(
        "list",
        help="List WAL operations",
    )
    list_parser.add_argument(
        "operation_type",
        choices=["pending", "processing", "completed", "failed", "all"],
        help="Type of operations to list",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of operations to show",
    )
    list_parser.add_argument(
        "--backend",
        choices=["ipfs", "s3", "storacha", "all"],
        default="all",
        help="Filter by backend",
    )
    
    # WAL show command
    show_parser = wal_subparsers.add_parser(
        "show",
        help="Show WAL operation details",
    )
    show_parser.add_argument(
        "operation_id",
        help="ID of the operation to show",
    )
    
    # WAL wait command
    wait_parser = wal_subparsers.add_parser(
        "wait",
        help="Wait for WAL operation to complete",
    )
    wait_parser.add_argument(
        "operation_id",
        help="ID of the operation to wait for",
    )
    wait_parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Maximum time to wait in seconds",
    )
    
    # WAL cleanup command
    cleanup_parser = wal_subparsers.add_parser(
        "cleanup",
        help="Clean up old WAL operations",
    )
    
    # WAL health command
    health_parser = wal_subparsers.add_parser(
        "health",
        help="Show WAL backend health status",
    )
    health_parser.add_argument(
        "--backend",
        choices=["ipfs", "s3", "storacha", "all"],
        default="all",
        help="Filter by backend",
    )
    
    # WAL retry command
    retry_parser = wal_subparsers.add_parser(
        "retry",
        help="Retry a failed WAL operation",
    )
    retry_parser.add_argument(
        "operation_id",
        help="ID of the operation to retry",
    )
    
    # WAL process command
    process_parser = wal_subparsers.add_parser(
        "process",
        help="Process pending WAL operations",
    )
    process_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of operations to process",
    )
    process_parser.add_argument(
        "--backend",
        choices=["ipfs", "s3", "storacha", "all"],
        default="all",
        help="Filter by backend",
    )
    
    # WAL metrics command
    metrics_parser = wal_subparsers.add_parser(
        "metrics",
        help="Show WAL metrics and performance statistics",
    )
    metrics_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed metrics",
    )
    
    # WAL config command
    config_parser = wal_subparsers.add_parser(
        "config",
        help="View or update WAL configuration",
    )
    config_parser.add_argument(
        "--set",
        action="append",
        help="Set configuration parameter in format key=value",
        metavar="KEY=VALUE",
    )


def parse_wal_kwargs(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Parse WAL command-specific keyword arguments from command-line arguments.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Dictionary of keyword arguments
    """
    kwargs = {}
    
    # Parse WAL command arguments
    if not hasattr(args, "wal_command") or not args.wal_command:
        return kwargs
    
    if args.wal_command == "list":
        kwargs.update({
            "operation_type": args.operation_type,
            "limit": args.limit,
            "backend": args.backend,
        })
    elif args.wal_command == "wait":
        kwargs.update({
            "timeout": args.timeout,
        })
    elif args.wal_command == "health":
        kwargs.update({
            "backend": args.backend,
        })
    elif args.wal_command == "process":
        kwargs.update({
            "limit": args.limit,
            "backend": args.backend,
        })
    elif args.wal_command == "metrics":
        kwargs.update({
            "detailed": args.detailed,
        })
    elif args.wal_command == "config" and args.set:
        config_values = {}
        for kv in args.set:
            if "=" in kv:
                key, value = kv.split("=", 1)
                # Try to convert values to appropriate types
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                elif value.isdigit():
                    value = int(value)
                config_values[key] = value
        kwargs["config_values"] = config_values
    
    return kwargs


def handle_wal_command(client: IPFSSimpleAPI, args: argparse.Namespace) -> Any:
    """
    Handle WAL command execution.
    
    Args:
        client: IPFS Simple API client
        args: Parsed command-line arguments
        
    Returns:
        Command result
    """
    # Check if WAL is available
    if not hasattr(client, "wal") or not client.wal:
        raise ValueError("WAL functionality is not available. Check your configuration.")
    
    # Parse WAL-specific parameters
    kwargs = parse_wal_kwargs(args)
    
    # Execute WAL command
    if args.wal_command == "status":
        # Get WAL status and statistics
        result = client.get_wal_stats()
        
        # Format result for display
        if result.get("success", False):
            stats = result.get("stats", {})
            return {
                "Total operations": stats.get("total_operations", 0),
                "Pending": stats.get("pending", 0),
                "Processing": stats.get("processing", 0),
                "Completed": stats.get("completed", 0),
                "Failed": stats.get("failed", 0),
                "Retrying": stats.get("retrying", 0),
                "Partitions": stats.get("partitions", 0),
                "Archives": stats.get("archives", 0),
                "Processing active": stats.get("processing_active", False),
            }
        return result
    
    elif args.wal_command == "list":
        operation_type = args.operation_type
        
        if operation_type == "pending":
            return client.get_pending_operations(limit=args.limit)
        elif operation_type == "processing":
            return client.get_processing_operations(limit=args.limit)
        elif operation_type == "completed":
            return client.get_completed_operations(limit=args.limit)
        elif operation_type == "failed":
            return client.get_failed_operations(limit=args.limit)
        else:  # "all"
            return client.get_all_operations(limit=args.limit)
    
    elif args.wal_command == "show":
        # Get operation details
        return client.get_wal_status(args.operation_id)
    
    elif args.wal_command == "wait":
        # Wait for operation to complete
        return client.wait_for_operation(
            args.operation_id,
            timeout=args.timeout,
            check_interval=1
        )
    
    elif args.wal_command == "cleanup":
        # Clean up old operations
        return client.cleanup_wal()
    
    elif args.wal_command == "health":
        # Get backend health status
        backend = args.backend
        if backend == "all":
            return client.get_backend_health()
        else:
            return client.get_backend_health(backend=backend)
    
    elif args.wal_command == "retry":
        # Retry a failed operation
        return client.retry_operation(args.operation_id)
    
    elif args.wal_command == "process":
        # Process pending operations
        return client.process_pending_operations(
            limit=args.limit,
            backend=args.backend if args.backend != "all" else None
        )
    
    elif args.wal_command == "metrics":
        # Get WAL metrics
        metrics = client.get_wal_metrics(detailed=args.detailed)
        
        # Format metrics for display
        if metrics.get("success", False):
            return metrics.get("metrics", {})
        return metrics
    
    elif args.wal_command == "config":
        if hasattr(args, "set") and args.set:
            # Update configuration
            return client.update_wal_config(kwargs.get("config_values", {}))
        else:
            # Get current configuration
            return client.get_wal_config()
    
    else:
        raise ValueError(f"Unknown WAL command: {args.wal_command}")