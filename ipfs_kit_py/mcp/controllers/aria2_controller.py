"""
Aria2 controller for MCP server.

This module provides a FastAPI controller for Aria2 operations through the MCP server.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Set, Union

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ipfs_kit_py.mcp.models.aria2_model import Aria2Model

# Import our model


# Configure logger
logger = logging.getLogger(__name__)


# Pydantic models for request validation
class URIListModel(BaseModel):
    """
import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

Model for URI list for downloads."""

    uris: Union[List[str], str] = Field(..., description="URI or list of URIs to download")
    filename: Optional[str] = Field(None, description="Optional filename for the download")
    options: Optional[Dict[str, Any]] = Field(
        None, description="Optional advanced options for the download"
    )


class DownloadIDModel(BaseModel):
    """Model for download ID."""

    gid: str = Field(..., description="Download ID")
    force: Optional[bool] = Field(False, description="Whether to force the operation")


class DaemonOptionsModel(BaseModel):
    """Model for daemon options."""

    options: Optional[Dict[str, Any]] = Field(
        None, description="Optional daemon configuration options"
    )


class MetalinkFileModel(BaseModel):
    """Model for metalink file creation."""

    files: List[Dict[str, Any]] = Field(..., description="List of files to include in the metalink")


class Aria2Controller:
    """Controller for Aria2 operations in MCP server."""

    def __init__(self, aria2_model: Aria2Model):
        """
        Initialize the Aria2 controller.

        Args:
            aria2_model: Aria2 model instance
        """
        self.aria2_model = aria2_model
        self.initialized_endpoints: Set[str] = set()
        logger.info("Aria2 controller initialized")

    def register_routes(self, router: APIRouter):
        """
        Register routes with the API router.

        Args:
            router: FastAPI router to register routes with
        """
        # Register health endpoint
        if "/aria2/health" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/health",
                self.health_check,
                methods=["GET"],
                summary="Check Aria2 health",
                description="Check if Aria2 is available and get version information",
            )
            self.initialized_endpoints.add("/aria2/health")

        # Register version endpoint
        if "/aria2/version" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/version",
                self.get_version,
                methods=["GET"],
                summary="Get Aria2 version",
                description="Get detailed version information about Aria2",
            )
            self.initialized_endpoints.add("/aria2/version")

        # Register download endpoints
        if "/aria2/add" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/add",
                self.add_uri,
                methods=["POST"],
                summary="Add download by URI",
                description="Add a new download by URI or list of URIs",
            )
            self.initialized_endpoints.add("/aria2/add")

        if "/aria2/add-torrent" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/add-torrent",
                self.add_torrent,
                methods=["POST"],
                summary="Add download by torrent",
                description="Add a new download using a torrent file",
            )
            self.initialized_endpoints.add("/aria2/add-torrent")

        if "/aria2/add-metalink" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/add-metalink",
                self.add_metalink,
                methods=["POST"],
                summary="Add download by metalink",
                description="Add a new download using a metalink file",
            )
            self.initialized_endpoints.add("/aria2/add-metalink")

        if "/aria2/create-metalink" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/create-metalink",
                self.create_metalink,
                methods=["POST"],
                summary="Create metalink file",
                description="Create a metalink file for multiple sources",
            )
            self.initialized_endpoints.add("/aria2/create-metalink")

        # Register management endpoints
        if "/aria2/remove" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/remove",
                self.remove_download,
                methods=["POST"],
                summary="Remove download",
                description="Remove a download by ID",
            )
            self.initialized_endpoints.add("/aria2/remove")

        if "/aria2/pause" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/pause",
                self.pause_download,
                methods=["POST"],
                summary="Pause download",
                description="Pause a download by ID",
            )
            self.initialized_endpoints.add("/aria2/pause")

        if "/aria2/resume" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/resume",
                self.resume_download,
                methods=["POST"],
                summary="Resume download",
                description="Resume a paused download by ID",
            )
            self.initialized_endpoints.add("/aria2/resume")

        # Register status endpoints
        if "/aria2/status/{gid}" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/status/{gid}",
                self.get_status,
                methods=["GET"],
                summary="Get download status",
                description="Get detailed status of a download by ID",
            )
            self.initialized_endpoints.add("/aria2/status/{gid}")

        if "/aria2/list" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/list",
                self.list_downloads,
                methods=["GET"],
                summary="List downloads",
                description="List all downloads with their status",
            )
            self.initialized_endpoints.add("/aria2/list")

        if "/aria2/purge" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/purge",
                self.purge_downloads,
                methods=["POST"],
                summary="Purge downloads",
                description="Purge completed/error/removed downloads",
            )
            self.initialized_endpoints.add("/aria2/purge")

        if "/aria2/global-stats" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/global-stats",
                self.get_global_status,
                methods=["GET"],
                summary="Get global statistics",
                description="Get global download statistics",
            )
            self.initialized_endpoints.add("/aria2/global-stats")

        # Register daemon endpoints
        if "/aria2/daemon/start" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/daemon/start",
                self.start_daemon,
                methods=["POST"],
                summary="Start Aria2 daemon",
                description="Start the Aria2 daemon with optional configuration",
            )
            self.initialized_endpoints.add("/aria2/daemon/start")

        if "/aria2/daemon/stop" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/daemon/stop",
                self.stop_daemon,
                methods=["POST"],
                summary="Stop Aria2 daemon",
                description="Stop the Aria2 daemon",
            )
            self.initialized_endpoints.add("/aria2/daemon/stop")

        logger.info(f"Registered {len(self.initialized_endpoints)} Aria2 endpoints")

    async def health_check(self):
        """
        Check Aria2 health status.

        Returns:
            Dictionary with health status
        """
        try:
            # Get version to check if Aria2 is available
            version_result = self.aria2_model.get_version()

            # Prepare health status
            health_status = {
                "success": version_result.get("success", False),
                "status": "healthy" if version_result.get("success", False) else "unavailable",
                "version": version_result.get("version", {}).get("version", "unknown"),
                "timestamp": time.time(),
                "features": {
                    "bittorrent": False,
                    "metalink": False,
                    "websocket": False,
                },
            }

            # Add features if available
            if version_result.get("success", False) and "version" in version_result:
                features = version_result["version"].get("enabledFeatures", [])
                health_status["features"] = {
                    "bittorrent": "BitTorrent" in features,
                    "metalink": "Metalink" in features,
                    "websocket": "WebSocket" in features,
                }

            # Check daemon status
            try:
                daemon_running = getattr(self.aria2_model.aria2_kit, "daemon_running", False)
                health_status["daemon_running"] = daemon_running
            except Exception:
                health_status["daemon_running"] = False

            # Add operation stats
            health_status["stats"] = self.aria2_model.operation_stats

            return health_status
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "timestamp": time.time(),
            }

    async def get_version(self):
        """
        Get Aria2 version.

        Returns:
            Result from aria2_model.get_version()
        """
        result = self.aria2_model.get_version()
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override=f"Aria2 not available: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result

    async def add_uri(self, uri_data: URIListModel):
        """
        Add download by URI.

        Args:
            uri_data: URI data from request

        Returns:
            Result from aria2_model.add_uri()
        """
        result = self.aria2_model.add_uri(
            uris=uri_data.uris, filename=uri_data.filename, options=uri_data.options
        )
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to add download: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result

    async def add_torrent(self, torrent_file: UploadFile = File(...), options: str = Form(None)):
        """
        Add download by torrent file.

        Args:
            torrent_file: Uploaded torrent file
            options: JSON string with options

        Returns:
            Result from aria2_model.add_torrent()
        """
        try:
            # Read torrent file
            torrent_content = await torrent_file.read()

            # Parse options if provided
            parsed_options = {}
            if options:
                import json

                parsed_options = json.loads(options)

            # Add torrent
            result = self.aria2_model.add_torrent(torrent=torrent_content, options=parsed_options)

            if not result.get("success", False):
                mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to add torrent: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
                )

            return result

        except json.JSONDecodeError:
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override="Invalid options format. Must be valid JSON."
            ,
        endpoint="/api/v0/aria2",
        doc_category="api"
    )
        except Exception as e:
            logger.error(f"Error in add_torrent: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Error processing torrent: {str(e,
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}")

    async def add_metalink(self, metalink_file: UploadFile = File(...), options: str = Form(None)):
        """
        Add download by metalink file.

        Args:
            metalink_file: Uploaded metalink file
            options: JSON string with options

        Returns:
            Result from aria2_model.add_metalink()
        """
        try:
            # Read metalink file
            metalink_content = await metalink_file.read()

            # Parse options if provided
            parsed_options = {}
            if options:
                import json

                parsed_options = json.loads(options)

            # Add metalink
            result = self.aria2_model.add_metalink(
                metalink=metalink_content, options=parsed_options
            )

            if not result.get("success", False):
                mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to add metalink: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
                )

            return result

        except json.JSONDecodeError:
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override="Invalid options format. Must be valid JSON."
            ,
        endpoint="/api/v0/aria2",
        doc_category="api"
    )
        except Exception as e:
            logger.error(f"Error in add_metalink: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Error processing metalink: {str(e,
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}")

    async def create_metalink(self, files_data: MetalinkFileModel):
        """
        Create a metalink file.

        Args:
            files_data: Data for metalink creation

        Returns:
            Result with metalink content
        """
        try:
            # Call create_metalink on aria2_kit
            result = self.aria2_model.aria2_kit.create_metalink(file_data=files_data.files)

            if not result.get("success", False):
                mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to create metalink: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
                )

            # Return metalink content
            return {
                "success": True,
                "metalink_content": result.get("metalink_content"),
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Error in create_metalink: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Error creating metalink: {str(e,
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}")

    async def remove_download(self, download: DownloadIDModel):
        """
        Remove a download.

        Args:
            download: Download ID and options

        Returns:
            Result from aria2_model.remove_download()
        """
        result = self.aria2_model.remove_download(gid=download.gid, force=download.force)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to remove download: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result

    async def pause_download(self, download: DownloadIDModel):
        """
        Pause a download.

        Args:
            download: Download ID and options

        Returns:
            Result from aria2_model.pause_download()
        """
        result = self.aria2_model.pause_download(gid=download.gid, force=download.force)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to pause download: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result

    async def resume_download(self, download: DownloadIDModel):
        """
        Resume a download.

        Args:
            download: Download ID and options

        Returns:
            Result from aria2_model.resume_download()
        """
        result = self.aria2_model.resume_download(gid=download.gid)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to resume download: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result

    async def get_status(self, gid: str):
        """
        Get download status.

        Args:
            gid: Download ID

        Returns:
            Result from aria2_model.get_status()
        """
        result = self.aria2_model.get_status(gid=gid)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="CONTENT_NOT_FOUND",
        message_override=f"Download not found: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result

    async def list_downloads(self):
        """
        List all downloads.

        Returns:
            Result from aria2_model.list_downloads()
        """
        result = self.aria2_model.list_downloads()
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="SERVICE_UNAVAILABLE",
        message_override=f"Failed to list downloads: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result

    async def purge_downloads(self):
        """
        Purge completed/error/removed downloads.

        Returns:
            Result from aria2_model.purge_downloads()
        """
        result = self.aria2_model.purge_downloads()
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to purge downloads: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result

    async def get_global_status(self):
        """
        Get global download statistics.

        Returns:
            Result from aria2_model.get_global_status()
        """
        result = self.aria2_model.get_global_status()
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="SERVICE_UNAVAILABLE",
        message_override=f"Failed to get global status: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result

    async def start_daemon(self, options: DaemonOptionsModel = Body(None)):
        """
        Start Aria2 daemon.

        Args:
            options: Optional daemon configuration options

        Returns:
            Result from aria2_model.start_daemon()
        """
        # Extract options if provided
        daemon_options = options.options if options else None

        result = self.aria2_model.start_daemon(options=daemon_options)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="DAEMON_ERROR",
        message_override=f"Failed to start daemon: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result

    async def stop_daemon(self):
        """
        Stop Aria2 daemon.

        Returns:
            Result from aria2_model.stop_daemon()
        """
        result = self.aria2_model.stop_daemon()
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="DAEMON_ERROR",
        message_override=f"Failed to stop daemon: {result.get('error',
        endpoint="/api/v0/aria2",
        doc_category="api"
    )}",
            )
        return result
