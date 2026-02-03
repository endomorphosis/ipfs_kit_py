"""
Filesystem Journal MCP Tools

This module provides MCP tools for filesystem journal operations, exposing
filesystem journal functionality to the MCP server for Dashboard integration.

Follows the standard architecture pattern:
    Core (filesystem_journal.py) → MCP Integration (this file) → Shim (mcp/) → Server → Dashboard
"""

from typing import Dict, Any, Optional, List
import logging

# Import core journal functionality
try:
    from ipfs_kit_py.filesystem_journal import FilesystemJournal, JournalOperationType, JournalEntryStatus
except ImportError:
    from filesystem_journal import FilesystemJournal, JournalOperationType, JournalEntryStatus

logger = logging.getLogger(__name__)

# Global journal instance (will be initialized when needed)
_journal_instance: Optional[FilesystemJournal] = None


def get_journal() -> Optional[FilesystemJournal]:
    """Return the current journal instance without creating one."""
    return _journal_instance


def _get_journal() -> FilesystemJournal:
    """Get or create the global journal instance."""
    global _journal_instance
    if _journal_instance is None:
        _journal_instance = FilesystemJournal()
    return _journal_instance


def journal_enable(
    journal_path: Optional[str] = None,
    sync_interval: int = 5,
    checkpoint_interval: int = 60,
    auto_recovery: bool = True
) -> Dict[str, Any]:
    """
    Enable filesystem journaling.
    
    Args:
        journal_path: Path to store journal files (default: ~/.ipfs_kit/journal)
        sync_interval: Interval in seconds for syncing journal to disk
        checkpoint_interval: Interval in seconds for creating checkpoints
        auto_recovery: Enable automatic recovery on startup
    
    Returns:
        Dictionary with enable status and journal info
    """
    try:
        global _journal_instance
        
        # Create new journal instance with specified config
        if journal_path:
            _journal_instance = FilesystemJournal(
                base_path=journal_path,
                sync_interval=sync_interval,
                checkpoint_interval=checkpoint_interval,
                auto_recovery=auto_recovery
            )
        else:
            _journal_instance = FilesystemJournal(
                sync_interval=sync_interval,
                checkpoint_interval=checkpoint_interval,
                auto_recovery=auto_recovery
            )
        
        return {
            "success": True,
            "message": "Filesystem journaling enabled",
            "journal_path": _journal_instance.base_path,
            "config": {
                "sync_interval": sync_interval,
                "checkpoint_interval": checkpoint_interval,
                "auto_recovery": auto_recovery
            }
        }
    except Exception as e:
        logger.error(f"Error enabling journal: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_status() -> Dict[str, Any]:
    """
    Get filesystem journal status and statistics.
    
    Returns:
        Dictionary with journal status, entry counts, and statistics
    """
    try:
        journal = get_journal()
        if journal is None:
            return {
                "success": True,
                "enabled": False
            }
        
        if hasattr(journal, 'get_status'):
            stats = journal.get_status()
            stats["enabled"] = True
        else:
            # Get current statistics
            stats = {
                "enabled": journal is not None,
                "journal_path": journal.base_path if journal else None,
                "current_journal_id": journal.current_journal_id if journal else None,
                "entry_count": journal.entry_count if journal else 0,
                "pending_entries": 0,
                "completed_entries": 0,
                "failed_entries": 0
            }
            
            # Count entries by status
            if journal and hasattr(journal, 'journal_entries'):
                for entry in journal.journal_entries:
                    status = entry.get('status', '')
                    if status == 'pending':
                        stats['pending_entries'] += 1
                    elif status == 'completed':
                        stats['completed_entries'] += 1
                    elif status == 'failed':
                        stats['failed_entries'] += 1
        
        return {
            "success": True,
            "status": stats
        }
    except Exception as e:
        logger.error(f"Error getting journal status: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_list_entries(
    status: str = "all",
    operation_type: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    List journal entries with filtering.
    
    Args:
        status: Filter by status (pending/completed/failed/all)
        operation_type: Filter by operation type (create/delete/write/etc.)
        limit: Maximum number of entries to return
    
    Returns:
        Dictionary with list of journal entries
    """
    try:
        journal = get_journal() or _get_journal()
        
        if hasattr(journal, 'get_entries'):
            entries = journal.get_entries(status=status if status != "all" else None,
                                          operation_type=operation_type,
                                          limit=limit)
            return {
                "success": True,
                "entries": entries,
                "total": len(entries),
                "filtered_by": {
                    "status": status,
                    "operation_type": operation_type,
                    "limit": limit
                }
            }

        if not hasattr(journal, 'journal_entries'):
            return {
                "success": True,
                "entries": [],
                "total": 0
            }
        
        entries = []
        for entry in journal.journal_entries:
            # Filter by status
            if status != "all" and entry.get('status') != status:
                continue
            
            # Filter by operation type
            if operation_type and entry.get('operation_type') != operation_type:
                continue
            
            entries.append(entry)
            
            if len(entries) >= limit:
                break
        
        return {
            "success": True,
            "entries": entries,
            "total": len(entries),
            "filtered_by": {
                "status": status,
                "operation_type": operation_type,
                "limit": limit
            }
        }
    except Exception as e:
        logger.error(f"Error listing journal entries: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_checkpoint(description: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a filesystem checkpoint.
    
    Args:
        description: Optional description for the checkpoint
    
    Returns:
        Dictionary with checkpoint info
    """
    try:
        journal = get_journal()
        if journal is None:
            return {
                "success": False,
                "error": "Journal not enabled"
            }
        
        checkpoint_id = journal.create_checkpoint()
        
        return {
            "success": True,
            "message": "Checkpoint created successfully",
            "checkpoint_id": checkpoint_id,
            "description": description
        }
    except Exception as e:
        logger.error(f"Error creating checkpoint: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_recover(checkpoint_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Recover from journal to a consistent state.
    
    Args:
        checkpoint_id: Specific checkpoint ID to recover from (or latest if not specified)
    
    Returns:
        Dictionary with recovery status
    """
    try:
        journal = get_journal()
        if journal is None:
            return {
                "success": False,
                "error": "Journal not enabled"
            }
        
        # Perform recovery
        recovered_count = journal.recover()
        
        return {
            "success": True,
            "message": "Recovery completed successfully",
            "recovered_entries": recovered_count,
            "checkpoint_id": checkpoint_id or "latest"
        }
    except Exception as e:
        logger.error(f"Error during recovery: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_mount(cid: str, path: str) -> Dict[str, Any]:
    """
    Mount a CID at a virtual path.
    
    Args:
        cid: IPFS CID to mount
        path: Virtual path to mount at
    
    Returns:
        Dictionary with mount status
    """
    try:
        journal = get_journal()
        if journal is None:
            return {
                "success": False,
                "error": "Journal not enabled"
            }
        
        entry_id = journal.record_operation(
            operation_type=JournalOperationType.MOUNT,
            path=path,
            details={"cid": cid}
        )
        journal.mark_completed(entry_id)
        
        return {
            "success": True,
            "message": f"Mounted {cid} at {path}",
            "entry_id": entry_id
        }
    except Exception as e:
        logger.error(f"Error mounting CID: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_mkdir(path: str, parents: bool = False) -> Dict[str, Any]:
    """
    Create a directory in the virtual filesystem.
    
    Args:
        path: Path to create
        parents: Create parent directories if needed
    
    Returns:
        Dictionary with operation status
    """
    try:
        journal = get_journal()
        if journal is None:
            return {"success": False, "error": "Journal not enabled"}
        
        entry_id = journal.record_operation(
            operation_type=JournalOperationType.CREATE,
            path=path,
            details={"type": "directory", "parents": parents}
        )
        journal.mark_completed(entry_id)
        
        return {
            "success": True,
            "message": f"Created directory {path}",
            "entry_id": entry_id
        }
    except Exception as e:
        logger.error(f"Error creating directory: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_write(path: str, content: str) -> Dict[str, Any]:
    """
    Write content to a file in the virtual filesystem.
    
    Args:
        path: Path to write to
        content: Content to write
    
    Returns:
        Dictionary with operation status
    """
    try:
        journal = get_journal()
        if journal is None:
            return {"success": False, "error": "Journal not enabled"}
        
        entry_id = journal.record_operation(
            operation_type=JournalOperationType.WRITE,
            path=path,
            details={"content": content, "size": len(content)}
        )
        journal.mark_completed(entry_id)
        
        return {
            "success": True,
            "message": f"Wrote {len(content)} bytes to {path}",
            "entry_id": entry_id
        }
    except Exception as e:
        logger.error(f"Error writing file: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_read(path: str) -> Dict[str, Any]:
    """
    Read a file from the virtual filesystem.
    
    Args:
        path: Path to read
    
    Returns:
        Dictionary with file content
    """
    try:
        journal = get_journal()
        if journal is None:
            return {"success": False, "error": "Journal not enabled"}
        
        if hasattr(journal, 'read_file') and callable(journal.read_file):
            content = journal.read_file(path)
        elif isinstance(getattr(journal, 'fs_state', None), dict) and path in journal.fs_state:
            content = journal.fs_state[path].get('content', '')
        else:
            content = ""
        
        return {
            "success": True,
            "path": path,
            "content": content,
            "size": len(content)
        }
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_rm(path: str, recursive: bool = False) -> Dict[str, Any]:
    """
    Remove a file or directory from the virtual filesystem.
    
    Args:
        path: Path to remove
        recursive: Remove directories recursively
    
    Returns:
        Dictionary with operation status
    """
    try:
        journal = get_journal()
        if journal is None:
            return {"success": False, "error": "Journal not enabled"}
        
        entry_id = journal.record_operation(
            operation_type=JournalOperationType.DELETE,
            path=path,
            details={"recursive": recursive}
        )
        journal.mark_completed(entry_id)
        
        return {
            "success": True,
            "message": f"Removed {path}",
            "entry_id": entry_id
        }
    except Exception as e:
        logger.error(f"Error removing path: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_mv(
    src_path: Optional[str] = None,
    dest_path: Optional[str] = None,
    source: Optional[str] = None,
    destination: Optional[str] = None
) -> Dict[str, Any]:
    """
    Move or rename a file or directory.
    
    Args:
        src_path: Source path
        dest_path: Destination path
    
    Returns:
        Dictionary with operation status
    """
    try:
        journal = get_journal()
        if journal is None:
            return {"success": False, "error": "Journal not enabled"}
        
        src_path = src_path or source
        dest_path = dest_path or destination
        if not src_path or not dest_path:
            return {"success": False, "error": "source and destination are required"}

        entry_id = journal.record_operation(
            operation_type=JournalOperationType.RENAME,
            path=src_path,
            details={"dest_path": dest_path}
        )
        journal.mark_completed(entry_id)
        
        return {
            "success": True,
            "message": f"Moved {src_path} to {dest_path}",
            "entry_id": entry_id
        }
    except Exception as e:
        logger.error(f"Error moving path: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def journal_ls(path: str = "/") -> Dict[str, Any]:
    """
    List directory contents in the virtual filesystem.
    
    Args:
        path: Path to list
    
    Returns:
        Dictionary with directory contents
    """
    try:
        journal = get_journal()
        if journal is None:
            return {"success": False, "error": "Journal not enabled"}
        
        if hasattr(journal, 'list_directory') and callable(journal.list_directory):
            entries = journal.list_directory(path)
        else:
            entries = []
            fs_state = getattr(journal, 'fs_state', None)
            if isinstance(fs_state, dict):
                for entry_path, entry_data in fs_state.items():
                    if entry_path.startswith(path.rstrip('/') + '/'):
                        relative_path = entry_path[len(path.rstrip('/') + '/'):] 
                        if '/' not in relative_path:
                            entries.append({
                                "name": relative_path,
                                "path": entry_path,
                                "type": entry_data.get('type', 'file'),
                                "size": entry_data.get('size', 0)
                            })
        
        return {
            "success": True,
            "path": path,
            "entries": entries,
            "total": len(entries)
        }
    except Exception as e:
        logger.error(f"Error listing directory: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# MCP tool definitions for export
MCP_TOOLS = [
    {
        "name": "journal_enable",
        "description": "Enable filesystem journaling for transaction safety",
        "parameters": {
            "type": "object",
            "properties": {
                "journal_path": {
                    "type": "string",
                    "description": "Path to store journal files (default: ~/.ipfs_kit/journal)"
                },
                "sync_interval": {
                    "type": "integer",
                    "description": "Interval in seconds for syncing journal to disk",
                    "default": 5
                },
                "checkpoint_interval": {
                    "type": "integer",
                    "description": "Interval in seconds for creating checkpoints",
                    "default": 60
                },
                "auto_recovery": {
                    "type": "boolean",
                    "description": "Enable automatic recovery on startup",
                    "default": True
                }
            }
        },
        "handler": journal_enable
    },
    {
        "name": "journal_status",
        "description": "Get filesystem journal status and statistics",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "handler": journal_status
    },
    {
        "name": "journal_list_entries",
        "description": "List journal entries with filtering by status and operation type",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["all", "pending", "completed", "failed"],
                    "description": "Filter by entry status",
                    "default": "all"
                },
                "operation_type": {
                    "type": "string",
                    "description": "Filter by operation type (create, delete, write, etc.)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entries to return",
                    "default": 100
                }
            }
        },
        "handler": journal_list_entries
    },
    {
        "name": "journal_checkpoint",
        "description": "Create a filesystem checkpoint for recovery",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Optional description for the checkpoint"
                }
            }
        },
        "handler": journal_checkpoint
    },
    {
        "name": "journal_recover",
        "description": "Recover from journal to a consistent state",
        "parameters": {
            "type": "object",
            "properties": {
                "checkpoint_id": {
                    "type": "string",
                    "description": "Specific checkpoint ID to recover from (or latest if not specified)"
                }
            }
        },
        "handler": journal_recover
    },
    {
        "name": "journal_mount",
        "description": "Mount an IPFS CID at a virtual path in the filesystem",
        "parameters": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "IPFS CID to mount"
                },
                "path": {
                    "type": "string",
                    "description": "Virtual path to mount at"
                }
            },
            "required": ["cid", "path"]
        },
        "handler": journal_mount
    },
    {
        "name": "journal_mkdir",
        "description": "Create a directory in the virtual filesystem",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to create"
                },
                "parents": {
                    "type": "boolean",
                    "description": "Create parent directories if needed",
                    "default": False
                }
            },
            "required": ["path"]
        },
        "handler": journal_mkdir
    },
    {
        "name": "journal_write",
        "description": "Write content to a file in the virtual filesystem",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to write to"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        },
        "handler": journal_write
    },
    {
        "name": "journal_read",
        "description": "Read a file from the virtual filesystem",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to read"
                }
            },
            "required": ["path"]
        },
        "handler": journal_read
    },
    {
        "name": "journal_rm",
        "description": "Remove a file or directory from the virtual filesystem",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to remove"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Remove directories recursively",
                    "default": False
                }
            },
            "required": ["path"]
        },
        "handler": journal_rm
    },
    {
        "name": "journal_mv",
        "description": "Move or rename a file or directory in the virtual filesystem",
        "parameters": {
            "type": "object",
            "properties": {
                "src_path": {
                    "type": "string",
                    "description": "Source path"
                },
                "dest_path": {
                    "type": "string",
                    "description": "Destination path"
                }
            },
            "required": ["src_path", "dest_path"]
        },
        "handler": journal_mv
    },
    {
        "name": "journal_ls",
        "description": "List directory contents in the virtual filesystem",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to list",
                    "default": "/"
                }
            }
        },
        "handler": journal_ls
    }
]
