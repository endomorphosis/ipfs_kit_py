#!/usr/bin/env python3
"""
Command-line interface for Filesystem Journal functionality.

This module adds filesystem journal commands to the IPFS Kit CLI.
"""

import argparse
import logging
from typing import Any, Dict, Optional, List, Union

# Set up logging
logger = logging.getLogger("ipfs_kit_cli.fs_journal")


def register_fs_journal_commands(subparsers):
    """
    Register filesystem journal commands with the CLI.
    
    Args:
        subparsers: Subparser group to add commands to
    """
    logger.debug("Registering filesystem journal commands")
    
    # Add top-level fs-journal command
    fs_journal_parser = subparsers.add_parser(
        "fs-journal", 
        help="Filesystem journal commands for transaction safety"
    )
    fs_journal_subparsers = fs_journal_parser.add_subparsers(
        dest="fs_journal_command",
        help="Filesystem journal subcommand",
        required=True
    )
    
    # Enable command
    enable_parser = fs_journal_subparsers.add_parser(
        "enable", 
        help="Enable filesystem journaling"
    )
    enable_parser.add_argument(
        "--journal-path", 
        type=str, 
        help="Path to store journal files"
    )
    enable_parser.add_argument(
        "--checkpoint-interval", 
        type=int, 
        default=50, 
        help="Number of operations between checkpoints"
    )
    enable_parser.add_argument(
        "--wal-enabled", 
        action="store_true", 
        help="Enable Write-Ahead Log integration"
    )
    enable_parser.set_defaults(func=handle_fs_journal_enable)
    
    # Status command
    status_parser = fs_journal_subparsers.add_parser(
        "status", 
        help="Get filesystem journal status"
    )
    status_parser.set_defaults(func=handle_fs_journal_status)
    
    # List transactions command
    list_parser = fs_journal_subparsers.add_parser(
        "list", 
        help="List journal transactions"
    )
    list_parser.add_argument(
        "--status", 
        type=str, 
        choices=["pending", "completed", "failed", "all"],
        default="all", 
        help="Filter by transaction status"
    )
    list_parser.add_argument(
        "--limit", 
        type=int, 
        default=10, 
        help="Maximum number of transactions to list"
    )
    list_parser.set_defaults(func=handle_fs_journal_list)
    
    # Create checkpoint command
    checkpoint_parser = fs_journal_subparsers.add_parser(
        "checkpoint", 
        help="Create a filesystem checkpoint"
    )
    checkpoint_parser.set_defaults(func=handle_fs_journal_checkpoint)
    
    # Recover command
    recover_parser = fs_journal_subparsers.add_parser(
        "recover", 
        help="Recover from journal to a consistent state"
    )
    recover_parser.add_argument(
        "--checkpoint-id", 
        type=str, 
        help="Specific checkpoint ID to recover from"
    )
    recover_parser.set_defaults(func=handle_fs_journal_recover)
    
    # Mount command
    mount_parser = fs_journal_subparsers.add_parser(
        "mount", 
        help="Mount a CID at a virtual path"
    )
    mount_parser.add_argument(
        "cid", 
        type=str, 
        help="CID to mount"
    )
    mount_parser.add_argument(
        "path", 
        type=str, 
        help="Virtual path to mount at"
    )
    mount_parser.set_defaults(func=handle_fs_journal_mount)
    
    # Create directory command
    mkdir_parser = fs_journal_subparsers.add_parser(
        "mkdir", 
        help="Create a directory in the virtual filesystem"
    )
    mkdir_parser.add_argument(
        "path", 
        type=str, 
        help="Path to create"
    )
    mkdir_parser.add_argument(
        "--parents", 
        "-p", 
        action="store_true", 
        help="Create parent directories as needed"
    )
    mkdir_parser.set_defaults(func=handle_fs_journal_mkdir)
    
    # Write file command
    write_parser = fs_journal_subparsers.add_parser(
        "write", 
        help="Write content to a file in the virtual filesystem"
    )
    write_parser.add_argument(
        "path", 
        type=str, 
        help="Path to write to"
    )
    write_parser.add_argument(
        "--content", 
        type=str, 
        help="Content to write (string)"
    )
    write_parser.add_argument(
        "--file", 
        type=str, 
        help="File to read content from"
    )
    write_parser.set_defaults(func=handle_fs_journal_write)
    
    # Read file command
    read_parser = fs_journal_subparsers.add_parser(
        "read", 
        help="Read a file from the virtual filesystem"
    )
    read_parser.add_argument(
        "path", 
        type=str, 
        help="Path to read"
    )
    read_parser.add_argument(
        "--output", 
        type=str, 
        help="Output file (if not specified, prints to stdout)"
    )
    read_parser.set_defaults(func=handle_fs_journal_read)
    
    # Remove command
    rm_parser = fs_journal_subparsers.add_parser(
        "rm", 
        help="Remove a file or directory from the virtual filesystem"
    )
    rm_parser.add_argument(
        "path", 
        type=str, 
        help="Path to remove"
    )
    rm_parser.add_argument(
        "--recursive", 
        "-r", 
        action="store_true", 
        help="Remove directories recursively"
    )
    rm_parser.set_defaults(func=handle_fs_journal_rm)
    
    # Move/rename command
    mv_parser = fs_journal_subparsers.add_parser(
        "mv", 
        help="Move or rename a file or directory"
    )
    mv_parser.add_argument(
        "source", 
        type=str, 
        help="Source path"
    )
    mv_parser.add_argument(
        "destination", 
        type=str, 
        help="Destination path"
    )
    mv_parser.set_defaults(func=handle_fs_journal_mv)
    
    # List files command (separate from IPFS ls)
    ls_parser = fs_journal_subparsers.add_parser(
        "ls", 
        help="List files in the virtual filesystem"
    )
    ls_parser.add_argument(
        "path", 
        type=str, 
        nargs="?",
        default="/",
        help="Path to list (defaults to root)"
    )
    ls_parser.add_argument(
        "--recursive", 
        "-r", 
        action="store_true", 
        help="List recursively"
    )
    ls_parser.set_defaults(func=handle_fs_journal_ls)
    
    # Export filesystem to CID command
    export_parser = fs_journal_subparsers.add_parser(
        "export", 
        help="Export virtual filesystem to a CID"
    )
    export_parser.add_argument(
        "--path", 
        type=str, 
        default="/",
        help="Path to export (defaults to root)"
    )
    export_parser.set_defaults(func=handle_fs_journal_export)
    
    logger.debug("Filesystem journal commands registered")


def handle_fs_journal_enable(api, args, kwargs):
    """
    Handle the 'fs-journal enable' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "enable_filesystem_journaling"):
        return {
            "success": False,
            "error": "Filesystem journaling is not supported in this version"
        }
    
    # Extract options from args
    options = {}
    if hasattr(args, "journal_path") and args.journal_path:
        options["journal_path"] = args.journal_path
    if hasattr(args, "checkpoint_interval") and args.checkpoint_interval:
        options["checkpoint_interval"] = args.checkpoint_interval
    if hasattr(args, "wal_enabled") and args.wal_enabled:
        options["wal_enabled"] = args.wal_enabled
    
    # Update with any additional kwargs
    options.update(kwargs)
    
    # Enable journaling
    result = api.enable_filesystem_journaling(**options)
    
    return {
        "success": True,
        "message": "Filesystem journaling enabled",
        "options": options,
        "journal_info": result
    }


def handle_fs_journal_status(api, args, kwargs):
    """
    Handle the 'fs-journal status' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    # Get journal status through the API
    journal = api.filesystem_journal
    
    return {
        "success": True,
        "enabled": True,
        "journal_path": journal.journal_path,
        "checkpoint_interval": journal.checkpoint_interval,
        "wal_enabled": getattr(journal, "wal_enabled", False),
        "transaction_count": journal.get_transaction_count(),
        "last_checkpoint": journal.get_last_checkpoint_id(),
        "filesystem_state": {
            "directories": len(journal.get_directory_list()),
            "files": len(journal.get_file_list()),
            "mounts": len(journal.get_mount_points())
        }
    }


def handle_fs_journal_list(api, args, kwargs):
    """
    Handle the 'fs-journal list' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    status_filter = args.status.upper() if args.status != "all" else None
    
    # List transactions with the given filter
    transactions = journal.list_transactions(status=status_filter, limit=args.limit)
    
    return {
        "success": True,
        "transactions": transactions,
        "count": len(transactions),
        "filter": args.status
    }


def handle_fs_journal_checkpoint(api, args, kwargs):
    """
    Handle the 'fs-journal checkpoint' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    
    # Create checkpoint and get ID
    checkpoint_id = journal.create_checkpoint()
    
    return {
        "success": True,
        "checkpoint_id": checkpoint_id,
        "message": f"Checkpoint created with ID: {checkpoint_id}"
    }


def handle_fs_journal_recover(api, args, kwargs):
    """
    Handle the 'fs-journal recover' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    checkpoint_id = args.checkpoint_id if hasattr(args, "checkpoint_id") else None
    
    # Perform recovery
    result = journal.recover(checkpoint_id=checkpoint_id)
    
    return {
        "success": True,
        "recovered_from_checkpoint": result.get("checkpoint_id"),
        "transactions_replayed": result.get("transactions_replayed", 0),
        "transactions_rolled_back": result.get("transactions_rolled_back", 0),
        "new_checkpoint_id": result.get("new_checkpoint_id")
    }


def handle_fs_journal_mount(api, args, kwargs):
    """
    Handle the 'fs-journal mount' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    
    # Mount CID at path
    result = journal.mount(args.cid, args.path)
    
    return {
        "success": True,
        "path": args.path,
        "cid": args.cid,
        "transaction_id": result.get("transaction_id")
    }


def handle_fs_journal_mkdir(api, args, kwargs):
    """
    Handle the 'fs-journal mkdir' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    parents = args.parents if hasattr(args, "parents") else False
    
    # Create directory
    result = journal.mkdir(args.path, parents=parents)
    
    return {
        "success": True,
        "path": args.path,
        "transaction_id": result.get("transaction_id")
    }


def handle_fs_journal_write(api, args, kwargs):
    """
    Handle the 'fs-journal write' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    
    # Get content from file or command line
    content = None
    if hasattr(args, "content") and args.content:
        content = args.content
    elif hasattr(args, "file") and args.file:
        with open(args.file, "rb") as f:
            content = f.read()
    else:
        return {
            "success": False,
            "error": "Either --content or --file must be specified"
        }
    
    # Write to file
    result = journal.write(args.path, content)
    
    return {
        "success": True,
        "path": args.path,
        "size": len(content) if content else 0,
        "transaction_id": result.get("transaction_id")
    }


def handle_fs_journal_read(api, args, kwargs):
    """
    Handle the 'fs-journal read' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    
    # Read from file
    content = journal.read(args.path)
    
    # Write to output file if specified
    if hasattr(args, "output") and args.output:
        if isinstance(content, str):
            with open(args.output, "w") as f:
                f.write(content)
        else:
            with open(args.output, "wb") as f:
                f.write(content)
        
        return {
            "success": True,
            "path": args.path,
            "size": len(content),
            "output": args.output
        }
    
    # Return content directly
    return content


def handle_fs_journal_rm(api, args, kwargs):
    """
    Handle the 'fs-journal rm' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    recursive = args.recursive if hasattr(args, "recursive") else False
    
    # Remove file or directory
    result = journal.remove(args.path, recursive=recursive)
    
    return {
        "success": True,
        "path": args.path,
        "recursive": recursive,
        "transaction_id": result.get("transaction_id")
    }


def handle_fs_journal_mv(api, args, kwargs):
    """
    Handle the 'fs-journal mv' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    
    # Move/rename file or directory
    result = journal.move(args.source, args.destination)
    
    return {
        "success": True,
        "source": args.source,
        "destination": args.destination,
        "transaction_id": result.get("transaction_id")
    }


def handle_fs_journal_ls(api, args, kwargs):
    """
    Handle the 'fs-journal ls' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    recursive = args.recursive if hasattr(args, "recursive") else False
    
    # List directory
    result = journal.list_directory(args.path, recursive=recursive)
    
    return {
        "success": True,
        "path": args.path,
        "entries": result.get("entries", [])
    }


def handle_fs_journal_export(api, args, kwargs):
    """
    Handle the 'fs-journal export' command.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result
    """
    if not hasattr(api, "filesystem_journal"):
        return {
            "success": False,
            "error": "Filesystem journaling is not enabled"
        }
    
    journal = api.filesystem_journal
    path = args.path if hasattr(args, "path") else "/"
    
    # Export filesystem to CID
    result = journal.export(path)
    
    return {
        "success": True,
        "path": path,
        "cid": result.get("cid"),
        "size": result.get("size")
    }