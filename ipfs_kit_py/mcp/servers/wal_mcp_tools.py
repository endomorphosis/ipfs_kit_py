#!/usr/bin/env python3
"""
MCP Tools for Write-Ahead Log (WAL) Management.

Provides MCP server tools for managing IPFS Kit's Write-Ahead Log operations,
following the architecture pattern:
  Core Module (storage_wal.py) → MCP Integration → MCP Server → JS SDK → Dashboard
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Define MCP tools for WAL management
WAL_MCP_TOOLS = [
    {
        "name": "wal_status",
        "description": "Get Write-Ahead Log status and statistics",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "wal_list_operations",
        "description": "List WAL operations with optional filtering",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "processing", "completed", "failed", "all"],
                    "description": "Filter operations by status",
                    "default": "pending"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of operations to return",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 1000
                },
                "backend": {
                    "type": "string",
                    "enum": ["ipfs", "s3", "storacha", "all"],
                    "description": "Filter operations by backend type",
                    "default": "all"
                }
            },
            "required": []
        }
    },
    {
        "name": "wal_get_operation",
        "description": "Get detailed information about a specific WAL operation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation_id": {
                    "type": "string",
                    "description": "ID of the operation to retrieve"
                }
            },
            "required": ["operation_id"]
        }
    },
    {
        "name": "wal_wait_for_operation",
        "description": "Wait for a WAL operation to complete",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation_id": {
                    "type": "string",
                    "description": "ID of the operation to wait for"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum time to wait in seconds",
                    "default": 60,
                    "minimum": 1,
                    "maximum": 3600
                }
            },
            "required": ["operation_id"]
        }
    },
    {
        "name": "wal_cleanup",
        "description": "Clean up old completed or failed operations from the WAL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "age_days": {
                    "type": "integer",
                    "description": "Remove operations older than this many days",
                    "default": 7,
                    "minimum": 1,
                    "maximum": 365
                },
                "status": {
                    "type": "string",
                    "enum": ["completed", "failed", "all"],
                    "description": "Status of operations to clean up",
                    "default": "completed"
                }
            },
            "required": []
        }
    },
    {
        "name": "wal_retry_operation",
        "description": "Retry a failed WAL operation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation_id": {
                    "type": "string",
                    "description": "ID of the operation to retry"
                }
            },
            "required": ["operation_id"]
        }
    },
    {
        "name": "wal_cancel_operation",
        "description": "Cancel a pending or processing WAL operation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation_id": {
                    "type": "string",
                    "description": "ID of the operation to cancel"
                }
            },
            "required": ["operation_id"]
        }
    },
    {
        "name": "wal_add_operation",
        "description": "Add a new operation to the WAL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation_type": {
                    "type": "string",
                    "enum": ["add", "get", "pin", "unpin", "rm", "cat", "list", "mkdir", "copy", "move", "upload", "download"],
                    "description": "Type of operation to add"
                },
                "backend": {
                    "type": "string",
                    "enum": ["ipfs", "s3", "storacha", "local"],
                    "description": "Backend type for the operation"
                },
                "params": {
                    "type": "object",
                    "description": "Operation-specific parameters",
                    "additionalProperties": True
                },
                "priority": {
                    "type": "integer",
                    "description": "Operation priority (higher = more urgent)",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": ["operation_type", "backend", "params"]
        }
    }
]


async def handle_wal_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle wal_status MCP tool call."""
    try:
        from ipfs_kit_py.storage_wal import get_global_wal
        
        wal = get_global_wal()
        if not wal:
            return {
                "success": False,
                "error": "WAL not initialized"
            }
        
        stats = wal.get_statistics()
        return {
            "success": True,
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting WAL status: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_wal_list_operations(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle wal_list_operations MCP tool call."""
    try:
        from ipfs_kit_py.storage_wal import get_global_wal, OperationStatus
        
        wal = get_global_wal()
        if not wal:
            return {
                "success": False,
                "error": "WAL not initialized"
            }
        
        status = arguments.get("status", "pending")
        limit = arguments.get("limit", 50)
        backend = arguments.get("backend", "all")
        
        # Convert status string to enum if needed
        if status != "all":
            try:
                status_enum = OperationStatus[status.upper()]
            except KeyError:
                status_enum = None
        else:
            status_enum = None
        
        # Get operations
        operations = wal.list_operations(
            status=status_enum,
            limit=limit,
            backend=backend if backend != "all" else None
        )
        
        return {
            "success": True,
            "operations": operations,
            "count": len(operations)
        }
    except Exception as e:
        logger.error(f"Error listing WAL operations: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_wal_get_operation(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle wal_get_operation MCP tool call."""
    try:
        from ipfs_kit_py.storage_wal import get_global_wal
        
        wal = get_global_wal()
        if not wal:
            return {
                "success": False,
                "error": "WAL not initialized"
            }
        
        operation_id = arguments.get("operation_id")
        if not operation_id:
            return {
                "success": False,
                "error": "operation_id is required"
            }
        
        operation = wal.get_operation(operation_id)
        if not operation:
            return {
                "success": False,
                "error": f"Operation {operation_id} not found"
            }
        
        return {
            "success": True,
            "operation": operation
        }
    except Exception as e:
        logger.error(f"Error getting WAL operation: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_wal_wait_for_operation(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle wal_wait_for_operation MCP tool call."""
    try:
        from ipfs_kit_py.storage_wal import get_global_wal
        
        wal = get_global_wal()
        if not wal:
            return {
                "success": False,
                "error": "WAL not initialized"
            }
        
        operation_id = arguments.get("operation_id")
        timeout = arguments.get("timeout", 60)
        
        if not operation_id:
            return {
                "success": False,
                "error": "operation_id is required"
            }
        
        result = await wal.wait_for_operation(operation_id, timeout=timeout)
        return {
            "success": True,
            "completed": result.get("completed", False),
            "status": result.get("status"),
            "result": result.get("result"),
            "error": result.get("error")
        }
    except Exception as e:
        logger.error(f"Error waiting for WAL operation: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_wal_cleanup(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle wal_cleanup MCP tool call."""
    try:
        from ipfs_kit_py.storage_wal import get_global_wal
        
        wal = get_global_wal()
        if not wal:
            return {
                "success": False,
                "error": "WAL not initialized"
            }
        
        age_days = arguments.get("age_days", 7)
        status = arguments.get("status", "completed")
        
        removed_count = wal.cleanup_old_operations(
            age_days=age_days,
            status=status
        )
        
        return {
            "success": True,
            "removed_count": removed_count,
            "message": f"Cleaned up {removed_count} operations"
        }
    except Exception as e:
        logger.error(f"Error cleaning up WAL: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_wal_retry_operation(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle wal_retry_operation MCP tool call."""
    try:
        from ipfs_kit_py.storage_wal import get_global_wal
        
        wal = get_global_wal()
        if not wal:
            return {
                "success": False,
                "error": "WAL not initialized"
            }
        
        operation_id = arguments.get("operation_id")
        if not operation_id:
            return {
                "success": False,
                "error": "operation_id is required"
            }
        
        result = wal.retry_operation(operation_id)
        return {
            "success": True,
            "retry_scheduled": result,
            "message": "Operation retry scheduled" if result else "Operation retry failed"
        }
    except Exception as e:
        logger.error(f"Error retrying WAL operation: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_wal_cancel_operation(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle wal_cancel_operation MCP tool call."""
    try:
        from ipfs_kit_py.storage_wal import get_global_wal
        
        wal = get_global_wal()
        if not wal:
            return {
                "success": False,
                "error": "WAL not initialized"
            }
        
        operation_id = arguments.get("operation_id")
        if not operation_id:
            return {
                "success": False,
                "error": "operation_id is required"
            }
        
        result = wal.cancel_operation(operation_id)
        return {
            "success": True,
            "cancelled": result,
            "message": "Operation cancelled" if result else "Operation cancellation failed"
        }
    except Exception as e:
        logger.error(f"Error cancelling WAL operation: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def handle_wal_add_operation(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle wal_add_operation MCP tool call."""
    try:
        from ipfs_kit_py.storage_wal import get_global_wal, OperationType, BackendType
        
        wal = get_global_wal()
        if not wal:
            return {
                "success": False,
                "error": "WAL not initialized"
            }
        
        operation_type = arguments.get("operation_type")
        backend = arguments.get("backend")
        params = arguments.get("params", {})
        priority = arguments.get("priority", 5)
        
        if not operation_type or not backend:
            return {
                "success": False,
                "error": "operation_type and backend are required"
            }
        
        # Convert strings to enums
        try:
            op_type_enum = OperationType[operation_type.upper()]
            backend_enum = BackendType[backend.upper()]
        except KeyError as e:
            return {
                "success": False,
                "error": f"Invalid operation_type or backend: {e}"
            }
        
        operation_id = wal.add_operation(
            operation_type=op_type_enum,
            backend=backend_enum,
            params=params,
            priority=priority
        )
        
        return {
            "success": True,
            "operation_id": operation_id,
            "message": f"Operation {operation_id} added to WAL"
        }
    except Exception as e:
        logger.error(f"Error adding WAL operation: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


# Handler mapping for MCP server
WAL_TOOL_HANDLERS = {
    "wal_status": handle_wal_status,
    "wal_list_operations": handle_wal_list_operations,
    "wal_get_operation": handle_wal_get_operation,
    "wal_wait_for_operation": handle_wal_wait_for_operation,
    "wal_cleanup": handle_wal_cleanup,
    "wal_retry_operation": handle_wal_retry_operation,
    "wal_cancel_operation": handle_wal_cancel_operation,
    "wal_add_operation": handle_wal_add_operation,
}
