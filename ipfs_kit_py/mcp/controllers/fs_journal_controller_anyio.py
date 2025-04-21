import logging
import time
import sniffio
import anyio
from typing import Dict, Any, Optional

import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling


#!/usr/bin/env python3
"""
REST API controller for Filesystem Journal functionality with AnyIO support.

This module provides API endpoints for interacting with the Filesystem Journal
through the MCP server using AnyIO for backend-agnostic async operations.
"""

# AnyIO import


try:
    from fastapi import APIRouter, Depends, Query, Path, Body
    from pydantic import BaseModel, Field
except ImportError:
    # For testing without FastAPI
    class APIRouter:
        def add_api_route(self, *args, **kwargs):
            pass

    class HTTPException(Exception):
        pass

    class BaseModel:
        pass

    def Depends(x):
        return x

    def Query(*args, **kwargs):
        return None

    def Path(*args, **kwargs):
        return None

    def Body(*args, **kwargs):
        return None

    def Field(*args, **kwargs):
        return None


try:
    from ipfs_kit_py.filesystem_journal import JournalOperationType, JournalEntryStatus
except ImportError:
    # Mock enums for testing
    class JournalOperationType:
        CREATE = "create"
        DELETE = "delete"
        RENAME = "rename"
        WRITE = "write"
        TRUNCATE = "truncate"
        METADATA = "metadata"
        CHECKPOINT = "checkpoint"
        MOUNT = "mount"
        UNMOUNT = "unmount"

    class JournalEntryStatus:
        PENDING = "pending"
        COMPLETED = "completed"
        FAILED = "failed"
        ROLLED_BACK = "rolled_back"


# Set up logging
logger = logging.getLogger("mcp.controllers.fs_journal")


# Pydantic models for request/response
class EnableJournalingRequest(BaseModel):
    journal_path: Optional[str] = Field(None, description="Path to store journal files")
    checkpoint_interval: Optional[int] = Field(
        50, description="Number of operations between checkpoints"
    )
    wal_enabled: Optional[bool] = Field(False, description="Enable Write-Ahead Log integration")


class MountRequest(BaseModel):
    cid: str = Field(..., description="CID to mount")
    path: str = Field(..., description="Path to mount at")


class MkdirRequest(BaseModel):
    path: str = Field(..., description="Path to create")
    parents: Optional[bool] = Field(False, description="Create parent directories as needed")


class WriteRequest(BaseModel):
    path: str = Field(..., description="Path to write to")
    content: Optional[str] = Field(None, description="Content to write (as string)")
    content_bytes: Optional[bytes] = Field(None, description="Content to write (as bytes)")
    content_file: Optional[str] = Field(None, description="Path to file containing content")


class ReadRequest(BaseModel):
    path: str = Field(..., description="Path to read")


class RemoveRequest(BaseModel):
    path: str = Field(..., description="Path to remove")
    recursive: Optional[bool] = Field(False, description="Remove recursively")


class MoveRequest(BaseModel):
    source: str = Field(..., description="Source path")
    destination: str = Field(..., description="Destination path")


class ListDirectoryRequest(BaseModel):
    path: Optional[str] = Field("/", description="Path to list")
    recursive: Optional[bool] = Field(False, description="List recursively")


class ExportRequest(BaseModel):
    path: Optional[str] = Field("/", description="Path to export")


class TransactionListRequest(BaseModel):
    status: Optional[str] = Field("all", description="Transaction status filter")
    limit: Optional[int] = Field(10, description="Maximum transactions to return")


class TransactionRequest(BaseModel):
    """Request model for creating a journal transaction."""
    operation_type: str = Field(..., description="Type of operation (create, delete, etc.)")
    path: str = Field(..., description="Filesystem path for the operation")
    data: Optional[Dict[str, Any]] = Field(None, description="Operation-specific data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class RecoverRequest(BaseModel):
    checkpoint_id: Optional[str] = Field(None, description="Checkpoint ID to recover from")


class JournalMonitorRequest(BaseModel):
    check_interval: Optional[int] = Field(60, description="How often to check health (seconds)")
    stats_dir: Optional[str] = Field(
        "~/.ipfs_kit/journal_stats", description="Directory to store statistics"
    )


class JournalVisualizationRequest(BaseModel):
    output_dir: Optional[str] = Field(
        "~/.ipfs_kit/journal_visualizations",
        description="Directory to save visualizations",
    )
    use_monitor: Optional[bool] = Field(
        True, description="Whether to use the existing monitor if available"
    )


class JournalDashboardRequest(BaseModel):
    timeframe_hours: Optional[int] = Field(24, description="Number of hours of data to include")
    output_dir: Optional[str] = Field(None, description="Directory to save dashboard")


class FsJournalControllerAnyIO:
    """Controller for Filesystem Journal operations with AnyIO support."""
    def __init__(self, ipfs_model):
        """
        Initialize the Filesystem Journal controller.

        Args:
            ipfs_model: IPFS model for core operations
        """
        self.ipfs_model = ipfs_model
        logger.info("Filesystem Journal controller with AnyIO initialized")

    def register_routes(self, router: APIRouter):
        """
        Register routes with the API router.

        Args:
            router: FastAPI router
        """
        # Group all routes under /fs-journal prefix for organization
        fs_journal_router = APIRouter(prefix="/fs-journal", tags=["fs-journal"])

        # Enable journaling
        fs_journal_router.add_api_route(
            "/enable",
            self.enable_journaling,
            methods=["POST"],
            summary="Enable filesystem journaling",
            description="Enables transaction-based journaling for the virtual filesystem",
        )

        # Get status
        fs_journal_router.add_api_route(
            "/status",
            self.get_status,
            methods=["GET"],
            summary="Get filesystem journal status",
            description="Returns status information about the filesystem journal",
        )

        # List transactions
        fs_journal_router.add_api_route(
            "/transactions",
            self.list_transactions,
            methods=["GET"],
            summary="List journal transactions",
            description="Lists transactions in the filesystem journal",
        )

        # Add transaction (needed for the comprehensive test)
        fs_journal_router.add_api_route(
            "/transactions",
            self.add_transaction,
            methods=["POST"],
            summary="Add a journal transaction",
            description="Adds a new transaction to the filesystem journal",
        )

        # Create checkpoint
        fs_journal_router.add_api_route(
            "/checkpoint",
            self.create_checkpoint,
            methods=["POST"],
            summary="Create filesystem checkpoint",
            description="Creates a checkpoint of the current filesystem state",
        )

        # Recover
        fs_journal_router.add_api_route(
            "/recover",
            self.recover,
            methods=["POST"],
            summary="Recover filesystem state",
            description="Recovers the filesystem state from a checkpoint",
        )

        # Mount
        fs_journal_router.add_api_route(
            "/mount",
            self.mount,
            methods=["POST"],
            summary="Mount CID at path",
            description="Mounts a CID at a virtual filesystem path",
        )

        # Mkdir
        fs_journal_router.add_api_route(
            "/mkdir",
            self.mkdir,
            methods=["POST"],
            summary="Create directory",
            description="Creates a directory in the virtual filesystem",
        )

        # Write
        fs_journal_router.add_api_route(
            "/write",
            self.write,
            methods=["POST"],
            summary="Write to file",
            description="Writes content to a file in the virtual filesystem",
        )

        # Read
        fs_journal_router.add_api_route(
            "/read",
            self.read,
            methods=["GET"],
            summary="Read file content",
            description="Reads content from a file in the virtual filesystem",
        )

        # Remove
        fs_journal_router.add_api_route(
            "/remove",
            self.remove,
            methods=["POST"],
            summary="Remove file or directory",
            description="Removes a file or directory from the virtual filesystem",
        )

        # Move
        fs_journal_router.add_api_route(
            "/move",
            self.move,
            methods=["POST"],
            summary="Move or rename file/directory",
            description="Moves or renames a file or directory in the virtual filesystem",
        )

        # List directory
        fs_journal_router.add_api_route(
            "/ls",
            self.list_directory,
            methods=["GET"],
            summary="List directory contents",
            description="Lists contents of a directory in the virtual filesystem",
        )

        # Export
        fs_journal_router.add_api_route(
            "/export",
            self.export,
            methods=["POST"],
            summary="Export filesystem to CID",
            description="Exports the virtual filesystem (or part of it) as a CID",
        )

        # Journal Monitoring Routes

        # Create journal monitor
        fs_journal_router.add_api_route(
            "/monitor/create",
            self.create_journal_monitor,
            methods=["POST"],
            summary="Create journal health monitor",
            description="Creates a monitor for tracking journal health metrics",
        )

        # Get journal health status
        fs_journal_router.add_api_route(
            "/monitor/health",
            self.get_journal_health_status,
            methods=["GET"],
            summary="Get journal health status",
            description="Returns the current health status of the journal",
        )

        # Create journal visualization
        fs_journal_router.add_api_route(
            "/visualization/create",
            self.create_journal_visualization,
            methods=["POST"],
            summary="Create journal visualization tools",
            description="Creates visualization tools for the journal",
        )

        # Generate journal dashboard
        fs_journal_router.add_api_route(
            "/visualization/dashboard",
            self.generate_journal_dashboard,
            methods=["POST"],
            summary="Generate journal dashboard",
            description="Generates a comprehensive dashboard for the journal",
        )

        # Include all fs-journal routes in the main router
        router.include_router(fs_journal_router)

        logger.info(f"Registered {len(fs_journal_router.routes)} Filesystem Journal routes")

    async def enable_journaling(self, request: EnableJournalingRequest):
        """
        Enable filesystem journaling.

        Args:
            request: Configuration parameters

        Returns:
            Status of the operation
        """
        try:
            # Access the API object through the model
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "enable_filesystem_journaling"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not supported in this version",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            # Convert request to kwargs
            options = {}
            if request.journal_path is not None:
                options["journal_path"] = request.journal_path
            if request.checkpoint_interval is not None:
                options["checkpoint_interval"] = request.checkpoint_interval
            if request.wal_enabled is not None:
                options["wal_enabled"] = request.wal_enabled

            # Enable journaling
            # Use anyio.to_thread.run_sync if the method is synchronous
            if hasattr(api.enable_filesystem_journaling, "__await__"):
                # Method is already async
                result = await api.enable_filesystem_journaling(**options)
            else:
                # Method is synchronous, run it in a thread
                result = await anyio.to_thread.run_sync(api.enable_filesystem_journaling, **options)

            return {
                "success": True,
                "message": "Filesystem journaling enabled",
                "options": options,
                "journal_info": result,
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error enabling filesystem journaling: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to enable filesystem journaling: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def get_status(self):
        """
        Get filesystem journal status.

        Returns:
            Journal status information
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal

            # Use anyio for any potentially blocking operations
            # This example assumes these are all synchronous methods that might block
            # Adjust as needed if they're already async methods
            transaction_count = await anyio.to_thread.run_sync(journal.get_transaction_count)
            last_checkpoint = await anyio.to_thread.run_sync(journal.get_last_checkpoint_id)
            directory_list = await anyio.to_thread.run_sync(journal.get_directory_list)
            file_list = await anyio.to_thread.run_sync(journal.get_file_list)
            mount_points = await anyio.to_thread.run_sync(journal.get_mount_points)

            return {
                "success": True,
                "enabled": True,
                "journal_path": journal.journal_path,
                "checkpoint_interval": journal.checkpoint_interval,
                "wal_enabled": getattr(journal, "wal_enabled", False),
                "transaction_count": transaction_count,
                "last_checkpoint": last_checkpoint,
                "filesystem_state": {
                    "directories": len(directory_list),
                    "files": len(file_list),
                    "mounts": len(mount_points),
                },
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error getting filesystem journal status: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to get filesystem journal status: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def list_transactions(
        self,
        status: str = Query("all", description="Transaction status filter"),
        limit: int = Query(10, description="Maximum transactions to return"),
    ):
        """
        List journal transactions.

        Args:
            status: Transaction status filter
            limit: Maximum transactions to return

        Returns:
            List of transactions
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal
            status_filter = status.upper() if status != "all" else None

            # Use anyio for potentially blocking operation
            transactions = await anyio.to_thread.run_sync(
                journal.list_transactions, status=status_filter, limit=limit
            )

            return {
                "success": True,
                "transactions": transactions,
                "count": len(transactions),
                "filter": status,
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error listing transactions: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to list transactions: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def add_transaction(self, request: TransactionRequest):
        """
        Add a journal transaction.

        Args:
            request: Transaction parameters

        Returns:
            Transaction creation result
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal

            # Check if operation type is valid
            valid_operations = [op.value for op in JournalOperationType]

            # Try to convert operation type string to enum (case-insensitive)
            operation_type = request.operation_type.upper()

            if operation_type not in valid_operations:
                # Try to find a matching operation by case-insensitive comparison
                found_match = False
                for valid_op in valid_operations:
                    if valid_op.upper() == operation_type:
                        operation_type = valid_op
                        found_match = True
                        break

                if not found_match:
                    mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Invalid operation type: {request.operation_type}. Must be one of: {', '.join(valid_operations)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            # Use anyio for these potentially blocking operations
            async with anyio.create_task_group() as tg:
                # Begin a transaction in a separate task
                transaction_id_result = {}

                async def begin_transaction_task():
                    transaction_id_result["id"] = await anyio.to_thread.run_sync(
                        journal.begin_transaction
                    )

                tg.start_soon(begin_transaction_task)

            transaction_id = transaction_id_result["id"]

            # Add the journal entry
            entry = await anyio.to_thread.run_sync(
                journal.add_journal_entry,
                operation_type=operation_type,
                path=request.path,
                data=request.data or {},
                metadata=request.metadata or {},
                status=JournalEntryStatus.PENDING,
            )

            # For testing, we'll mark it as completed immediately
            # In a real implementation, this would be done when the actual operation completes
            await anyio.to_thread.run_sync(
                journal.update_entry_status,
                entry_id=entry["entry_id"],
                status=JournalEntryStatus.COMPLETED,
            )

            # Commit the transaction
            await anyio.to_thread.run_sync(journal.commit_transaction)

            return {
                "success": True,
                "transaction_id": transaction_id,
                "entry_id": entry["entry_id"],
                "operation_type": operation_type,
                "path": request.path,
                "timestamp": entry.get("timestamp", time.time()),
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error adding transaction: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to add transaction: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def create_checkpoint(self):
        """
        Create a filesystem checkpoint.

        Returns:
            Checkpoint creation result
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal
            checkpoint_id = await anyio.to_thread.run_sync(journal.create_checkpoint)

            return {
                "success": True,
                "checkpoint_id": checkpoint_id,
                "message": f"Checkpoint created with ID: {checkpoint_id}",
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error creating checkpoint: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to create checkpoint: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def recover(self, request: RecoverRequest):
        """
        Recover filesystem state from a checkpoint.

        Args:
            request: Recovery parameters

        Returns:
            Recovery result
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal
            result = await anyio.to_thread.run_sync(
                journal.recover, checkpoint_id=request.checkpoint_id
            )

            return {
                "success": True,
                "recovered_from_checkpoint": result.get("checkpoint_id"),
                "transactions_replayed": result.get("transactions_replayed", 0),
                "transactions_rolled_back": result.get("transactions_rolled_back", 0),
                "new_checkpoint_id": result.get("new_checkpoint_id"),
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error recovering filesystem state: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to recover filesystem state: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def mount(self, request: MountRequest):
        """
        Mount a CID at a virtual path.

        Args:
            request: Mount parameters

        Returns:
            Mount operation result
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal
            result = await anyio.to_thread.run_sync(
                journal.mount, cid=request.cid, path=request.path
            )

            return {
                "success": True,
                "path": request.path,
                "cid": request.cid,
                "transaction_id": result.get("transaction_id"),
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error mounting CID: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to mount CID: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def mkdir(self, request: MkdirRequest):
        """
        Create a directory in the virtual filesystem.

        Args:
            request: Directory creation parameters

        Returns:
            Directory creation result
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal
            result = await anyio.to_thread.run_sync(
                journal.mkdir, path=request.path, parents=request.parents
            )

            return {
                "success": True,
                "path": request.path,
                "transaction_id": result.get("transaction_id"),
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error creating directory: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to create directory: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def write(self, request: WriteRequest):
        """
        Write content to a file in the virtual filesystem.

        Args:
            request: Write parameters

        Returns:
            Write operation result
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal

            # Determine the content to write
            content = None
            if request.content is not None:
                content = request.content
            elif request.content_bytes is not None:
                content = request.content_bytes
            elif request.content_file is not None:
                try:
                    # Read file with anyio to avoid blocking
                    async with await anyio.open_file(request.content_file, "rb") as f:
                        content = await f.read()
                except Exception as e:
                    mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to read content file: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )
            else:
                mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override="No content provided",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            # Write the content
            result = await anyio.to_thread.run_sync(journal.write, request.path, content)

            return {
                "success": True,
                "path": request.path,
                "size": len(content) if content else 0,
                "transaction_id": result.get("transaction_id"),
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error writing to file: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to write to file: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def read(self, path: str = Query(..., description="Path to read")):
        """
        Read content from a file in the virtual filesystem.

        Args:
            path: Path to read

        Returns:
            File content
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal
            content = await anyio.to_thread.run_sync(journal.read, path)

            return {
                "success": True,
                "path": path,
                "content": content,
                "size": len(content) if content else 0,
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error reading file: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to read file: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def remove(self, request: RemoveRequest):
        """
        Remove a file or directory from the virtual filesystem.

        Args:
            request: Remove parameters

        Returns:
            Remove operation result
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal
            result = await anyio.to_thread.run_sync(
                journal.remove, request.path, recursive=request.recursive
            )

            return {
                "success": True,
                "path": request.path,
                "recursive": request.recursive,
                "transaction_id": result.get("transaction_id"),
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error removing file/directory: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to remove file/directory: {str(e)}",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

    async def move(self, request: MoveRequest):
        """
        Move or rename a file or directory.

        Args:
            request: Move parameters

        Returns:
            Move operation result
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal
            result = await anyio.to_thread.run_sync(
                journal.move, request.source, request.destination
            )

            return {
                "success": True,
                "source": request.source,
                "destination": request.destination,
                "transaction_id": result.get("transaction_id"),
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error moving file/directory: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to move file/directory: {str(e,
        endpoint="/fs-journal",
        doc_category="extensions"
    )}")

    async def list_directory(
        self,
        path: str = Query("/", description="Path to list"),
        recursive: bool = Query(False, description="List recursively"),
    ):
        """
        List contents of a directory in the virtual filesystem.

        Args:
            path: Path to list
            recursive: List recursively

        Returns:
            Directory listing
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal
            result = await anyio.to_thread.run_sync(
                journal.list_directory, path, recursive=recursive
            )

            return {"success": True, "path": path, "entries": result.get("entries", [])}

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error listing directory: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to list directory: {str(e,
        endpoint="/fs-journal",
        doc_category="extensions"
    )}")

    async def export(self, request: ExportRequest):
        """
        Export virtual filesystem to a CID.

        Args:
            request: Export parameters

        Returns:
            Export operation result
        """
        try:
            api = self.ipfs_model.ipfs_kit

            if not hasattr(api, "filesystem_journal"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Filesystem journaling is not enabled",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            journal = api.filesystem_journal
            result = await anyio.to_thread.run_sync(journal.export, request.path)

            return {
                "success": True,
                "path": request.path,
                "cid": result.get("cid"),
                "size": result.get("size"),
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error exporting filesystem: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to export filesystem: {str(e,
        endpoint="/fs-journal",
        doc_category="extensions"
    )}")

    async def create_journal_monitor(self, request: JournalMonitorRequest):
        """
        Create a health monitor for the filesystem journal.

        Args:
            request: Monitor configuration parameters

        Returns:
            Success status and monitor info
        """
        try:
            # Access the API object through the model
            api = self.ipfs_model.ipfs_kit

            # Check if the method is available
            if not hasattr(api, "create_journal_monitor"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Journal monitoring is not supported in this version",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            # Convert request to kwargs
            options = {}
            if request.check_interval is not None:
                options["check_interval"] = request.check_interval
            if request.stats_dir is not None:
                options["stats_dir"] = request.stats_dir

            # Create the monitor using anyio for potentially blocking operation
            result = await anyio.to_thread.run_sync(api.create_journal_monitor, **options)

            if not result["success"]:
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to create journal monitor: {result.get('error',
        endpoint="/fs-journal",
        doc_category="extensions"
    )}",
                )

            return {
                "success": True,
                "message": "Journal health monitor created",
                "options": options,
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error creating journal monitor: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to create journal monitor: {str(e,
        endpoint="/fs-journal",
        doc_category="extensions"
    )}"
            )

    async def get_journal_health_status(self):
        """
        Get the current health status of the filesystem journal.

        Returns:
            Health status information
        """
        try:
            # Access the API object through the model
            api = self.ipfs_model.ipfs_kit

            # Check if the method is available
            if not hasattr(api, "get_journal_health_status"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Journal health monitoring is not supported in this version",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            # Get health status
            result = await anyio.to_thread.run_sync(api.get_journal_health_status)

            if not result["success"]:
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to get journal health status: {result.get('error',
        endpoint="/fs-journal",
        doc_category="extensions"
    )}",
                )

            return {
                "success": True,
                "status": result.get("status", "unknown"),
                "issues": result.get("issues", []),
                "threshold_values": result.get("threshold_values", {}),
                "active_transactions": result.get("active_transactions", 0),
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error getting journal health status: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to get journal health status: {str(e,
        endpoint="/fs-journal",
        doc_category="extensions"
    )}"
            )

    async def create_journal_visualization(self, request: JournalVisualizationRequest):
        """
        Create visualization tools for the filesystem journal.

        Args:
            request: Visualization configuration parameters

        Returns:
            Success status and visualization info
        """
        try:
            # Access the API object through the model
            api = self.ipfs_model.ipfs_kit

            # Check if the method is available
            if not hasattr(api, "create_journal_visualization"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Journal visualization is not supported in this version",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            # Convert request to kwargs
            options = {}
            if request.output_dir is not None:
                options["output_dir"] = request.output_dir
            if request.use_monitor is not None:
                options["use_monitor"] = request.use_monitor

            # Create the visualization
            result = await anyio.to_thread.run_sync(api.create_journal_visualization, **options)

            if not result["success"]:
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to create journal visualization: {result.get('error',
        endpoint="/fs-journal",
        doc_category="extensions"
    )}",
                )

            return {
                "success": True,
                "message": "Journal visualization tools created",
                "options": options,
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error creating journal visualization: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to create journal visualization: {str(e,
        endpoint="/fs-journal",
        doc_category="extensions"
    )}",
            )

    async def generate_journal_dashboard(self, request: JournalDashboardRequest):
        """
        Generate a comprehensive dashboard for the filesystem journal.

        Args:
            request: Dashboard generation parameters

        Returns:
            Success status and dashboard paths
        """
        try:
            # Access the API object through the model
            api = self.ipfs_model.ipfs_kit

            # Check if the method is available
            if not hasattr(api, "generate_journal_dashboard"):
                mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override="Journal dashboard generation is not supported in this version",
        endpoint="/fs-journal",
        doc_category="extensions"
    )

            # Convert request to kwargs
            options = {}
            if request.timeframe_hours is not None:
                options["timeframe_hours"] = request.timeframe_hours
            if request.output_dir is not None:
                options["output_dir"] = request.output_dir

            # Generate the dashboard
            result = await anyio.to_thread.run_sync(api.generate_journal_dashboard, **options)

            if not result["success"]:
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to generate journal dashboard: {result.get('error',
        endpoint="/fs-journal",
        doc_category="extensions"
    )}",
                )

            return {
                "success": True,
                "message": "Journal dashboard generated",
                "dashboard_path": result.get("dashboard_path"),
                "plots": result.get("plots", {}),
            }

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error generating journal dashboard: {str(e)}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Failed to generate journal dashboard: {str(e,
        endpoint="/fs-journal",
        doc_category="extensions"
    )}",
            )

    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
