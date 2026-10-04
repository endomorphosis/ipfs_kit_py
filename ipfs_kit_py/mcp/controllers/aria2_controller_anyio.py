import logging
import time
import warnings

import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling


import anyio
import sniffio

#!/usr/bin/env python3
"""
Aria2 controller for MCP server with AnyIO support.

This module provides a FastAPI controller for Aria2 operations through the MCP server
using AnyIO for backend-agnostic async operations.
"""

# AnyIO import


# Try to import FastAPI components
try:
    from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
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

    def Query(*args, **kwargs):
        return None

    def File(*args, **kwargs):
        return None

    def UploadFile(*args, **kwargs):
        return None

    def Form(*args, **kwargs):
        return None

    def Body(*args, **kwargs):
        return None

    def Field(*args, **kwargs):
        return None


# Import our model
try:
    from ipfs_kit_py.mcp.controllers.aria2_controller import (
        Aria2Controller,
        DaemonOptionsModel,
        DownloadIDModel,
        MetalinkFileModel,
        URIListModel,
    )
    from ipfs_kit_py.mcp.models.aria2_model import Aria2Model
except ImportError:
    # For testing without the actual model
    class Aria2Model:
        pass

    class Aria2Controller:
        pass

    class URIListModel(BaseModel):
        pass

    class DownloadIDModel(BaseModel):
        pass

    class DaemonOptionsModel(BaseModel):
        pass

    class MetalinkFileModel(BaseModel):
        pass


# Configure logger
logger = logging.getLogger(__name__)


class Aria2ControllerAnyIO(Aria2Controller):
    """Controller for Aria2 operations in MCP server with AnyIO support."""

    def __init__(self, aria2_model: Aria2Model):
        """
        Initialize the Aria2 controller with AnyIO support.

        Args:
            aria2_model: Aria2 model instance
        """
        super().__init__(aria2_model)
        logger.info("Aria2 controller with AnyIO initialized")

    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None

    def _warn_if_async_context(self, method_name):
        """Warn if called from async context without using async version."""
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
                stacklevel=3,
            )

    # Override synchronous methods to add warnings
    def health_check(self):
        """Check Aria2 health status with warning in async context."""
        self._warn_if_async_context("health_check")
        return super().health_check()

    def get_version(self):
        """Get Aria2 version with warning in async context."""
        self._warn_if_async_context("get_version")
        return super().get_version()

    def add_uri(self, uri_data):
        """Add download by URI with warning in async context."""
        self._warn_if_async_context("add_uri")
        return super().add_uri(uri_data)

    def add_torrent(self, torrent_file, options=None):
        """Add download by torrent with warning in async context."""
        self._warn_if_async_context("add_torrent")
        return super().add_torrent(torrent_file, options)

    def add_metalink(self, metalink_file, options=None):
        """Add download by metalink with warning in async context."""
        self._warn_if_async_context("add_metalink")
        return super().add_metalink(metalink_file, options)

    def create_metalink(self, files_data):
        """Create a metalink file with warning in async context."""
        self._warn_if_async_context("create_metalink")
        return super().create_metalink(files_data)

    def remove_download(self, download):
        """Remove a download with warning in async context."""
        self._warn_if_async_context("remove_download")
        return super().remove_download(download)

    def pause_download(self, download):
        """Pause a download with warning in async context."""
        self._warn_if_async_context("pause_download")
        return super().pause_download(download)

    def resume_download(self, download):
        """Resume a download with warning in async context."""
        self._warn_if_async_context("resume_download")
        return super().resume_download(download)

    def get_status(self, gid):
        """Get download status with warning in async context."""
        self._warn_if_async_context("get_status")
        return super().get_status(gid)

    def list_downloads(self):
        """List all downloads with warning in async context."""
        self._warn_if_async_context("list_downloads")
        return super().list_downloads()

    def purge_downloads(self):
        """Purge downloads with warning in async context."""
        self._warn_if_async_context("purge_downloads")
        return super().purge_downloads()

    def get_global_status(self):
        """Get global download statistics with warning in async context."""
        self._warn_if_async_context("get_global_status")
        return super().get_global_status()

    def start_daemon(self, options=None):
        """Start Aria2 daemon with warning in async context."""
        self._warn_if_async_context("start_daemon")
        return super().start_daemon(options)

    def stop_daemon(self):
        """Stop Aria2 daemon with warning in async context."""
        self._warn_if_async_context("stop_daemon")
        return super().stop_daemon()

    # Async implementation of methods
    async def health_check_async(self):
        """
        Check Aria2 health status asynchronously.

        Returns:
            Dictionary with health status
        """
        try:
            # Convert the synchronous model method to async using anyio
            version_result = await anyio.to_thread.run_sync(self.aria2_model.get_version)

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
                daemon_running = await anyio.to_thread.run_sync(
                    lambda: getattr(self.aria2_model.aria2_kit, "daemon_running", False)
                )
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

    async def get_version_async(self):
        """
        Get Aria2 version asynchronously.

        Returns:
            Result from aria2_model.get_version()
        """
        result = await anyio.to_thread.run_sync(self.aria2_model.get_version)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="EXTENSION_NOT_AVAILABLE",
        message_override=f"Aria2 not available: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    async def add_uri_async(self, uri_data: URIListModel):
        """
        Add download by URI asynchronously.

        Args:
            uri_data: URI data from request

        Returns:
            Result from aria2_model.add_uri()
        """
        result = await anyio.to_thread.run_sync(
            self.aria2_model.add_uri,
            uris=uri_data.uris,
            filename=uri_data.filename,
            options=uri_data.options,
        )
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to add download: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    async def add_torrent_async(
        self, torrent_file: UploadFile = File(...), options: str = Form(None)
    ):
        """
        Add download by torrent file asynchronously.

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
            result = await anyio.to_thread.run_sync(
                self.aria2_model.add_torrent,
                torrent=torrent_content,
                options=parsed_options,
            )

            if not result.get("success", False):
                mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to add torrent: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
                )

            return result

        except json.JSONDecodeError:
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override="Invalid options format. Must be valid JSON."
            ,
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )
        except Exception as e:
            logger.error(f"Error in add_torrent: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Error processing torrent: {str(e,
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}")

    async def add_metalink_async(
        self, metalink_file: UploadFile = File(...), options: str = Form(None)
    ):
        """
        Add download by metalink file asynchronously.

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
            result = await anyio.to_thread.run_sync(
                self.aria2_model.add_metalink,
                metalink=metalink_content,
                options=parsed_options,
            )

            if not result.get("success", False):
                mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to add metalink: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
                )

            return result

        except json.JSONDecodeError:
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override="Invalid options format. Must be valid JSON."
            ,
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )
        except Exception as e:
            logger.error(f"Error in add_metalink: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=f"Error processing metalink: {str(e,
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}")

    async def create_metalink_async(self, files_data: MetalinkFileModel):
        """
        Create a metalink file asynchronously.

        Args:
            files_data: Data for metalink creation

        Returns:
            Result with metalink content
        """
        try:
            # Call create_metalink on aria2_kit
            result = await anyio.to_thread.run_sync(
                self.aria2_model.aria2_kit.create_metalink, file_data=files_data.files
            )

            if not result.get("success", False):
                mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to create metalink: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
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
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}")

    async def remove_download_async(self, download: DownloadIDModel):
        """
        Remove a download asynchronously.

        Args:
            download: Download ID and options

        Returns:
            Result from aria2_model.remove_download()
        """
        result = await anyio.to_thread.run_sync(
            self.aria2_model.remove_download, gid=download.gid, force=download.force
        )
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to remove download: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    async def pause_download_async(self, download: DownloadIDModel):
        """
        Pause a download asynchronously.

        Args:
            download: Download ID and options

        Returns:
            Result from aria2_model.pause_download()
        """
        result = await anyio.to_thread.run_sync(
            self.aria2_model.pause_download, gid=download.gid, force=download.force
        )
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to pause download: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    async def resume_download_async(self, download: DownloadIDModel):
        """
        Resume a download asynchronously.

        Args:
            download: Download ID and options

        Returns:
            Result from aria2_model.resume_download()
        """
        result = await anyio.to_thread.run_sync(self.aria2_model.resume_download, gid=download.gid)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to resume download: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    async def get_status_async(self, gid: str):
        """
        Get download status asynchronously.

        Args:
            gid: Download ID

        Returns:
            Result from aria2_model.get_status()
        """
        result = await anyio.to_thread.run_sync(self.aria2_model.get_status, gid=gid)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="CONTENT_NOT_FOUND",
        message_override=f"Download not found: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    async def list_downloads_async(self):
        """
        List all downloads asynchronously.

        Returns:
            Result from aria2_model.list_downloads()
        """
        result = await anyio.to_thread.run_sync(self.aria2_model.list_downloads)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="SERVICE_UNAVAILABLE",
        message_override=f"Failed to list downloads: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    async def purge_downloads_async(self):
        """
        Purge completed/error/removed downloads asynchronously.

        Returns:
            Result from aria2_model.purge_downloads()
        """
        result = await anyio.to_thread.run_sync(self.aria2_model.purge_downloads)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="INVALID_REQUEST",
        message_override=f"Failed to purge downloads: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    async def get_global_status_async(self):
        """
        Get global download statistics asynchronously.

        Returns:
            Result from aria2_model.get_global_status()
        """
        result = await anyio.to_thread.run_sync(self.aria2_model.get_global_status)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="SERVICE_UNAVAILABLE",
        message_override=f"Failed to get global status: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    async def start_daemon_async(self, options: DaemonOptionsModel = Body(None)):
        """
        Start Aria2 daemon asynchronously.

        Args:
            options: Optional daemon configuration options

        Returns:
            Result from aria2_model.start_daemon()
        """
        # Extract options if provided
        daemon_options = options.options if options else None

        result = await anyio.to_thread.run_sync(
            self.aria2_model.start_daemon, options=daemon_options
        )
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="DAEMON_ERROR",
        message_override=f"Failed to start daemon: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    async def stop_daemon_async(self):
        """
        Stop Aria2 daemon asynchronously.

        Returns:
            Result from aria2_model.stop_daemon()
        """
        result = await anyio.to_thread.run_sync(self.aria2_model.stop_daemon)
        if not result.get("success", False):
            mcp_error_handling.raise_http_exception(
        code="DAEMON_ERROR",
        message_override=f"Failed to stop daemon: {result.get('error',
        endpoint="/api/v0/aria2_anyio",
        doc_category="api"
    )}",
            )
        return result

    def register_routes(self, router: APIRouter):
        """
        Register routes with the API router. Overrides base method to use async versions.

        Args:
            router: FastAPI router to register routes with
        """
        # Register health endpoint
        if "/aria2/health" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/health",
                self.health_check_async,
                methods=["GET"],
                summary="Check Aria2 health",
                description="Check if Aria2 is available and get version information",
            )
            self.initialized_endpoints.add("/aria2/health")

        # Register version endpoint
        if "/aria2/version" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/version",
                self.get_version_async,
                methods=["GET"],
                summary="Get Aria2 version",
                description="Get detailed version information about Aria2",
            )
            self.initialized_endpoints.add("/aria2/version")

        # Register download endpoints
        if "/aria2/add" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/add",
                self.add_uri_async,
                methods=["POST"],
                summary="Add download by URI",
                description="Add a new download by URI or list of URIs",
            )
            self.initialized_endpoints.add("/aria2/add")

        if "/aria2/add-torrent" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/add-torrent",
                self.add_torrent_async,
                methods=["POST"],
                summary="Add download by torrent",
                description="Add a new download using a torrent file",
            )
            self.initialized_endpoints.add("/aria2/add-torrent")

        if "/aria2/add-metalink" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/add-metalink",
                self.add_metalink_async,
                methods=["POST"],
                summary="Add download by metalink",
                description="Add a new download using a metalink file",
            )
            self.initialized_endpoints.add("/aria2/add-metalink")

        if "/aria2/create-metalink" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/create-metalink",
                self.create_metalink_async,
                methods=["POST"],
                summary="Create metalink file",
                description="Create a metalink file for multiple sources",
            )
            self.initialized_endpoints.add("/aria2/create-metalink")

        # Register management endpoints
        if "/aria2/remove" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/remove",
                self.remove_download_async,
                methods=["POST"],
                summary="Remove download",
                description="Remove a download by ID",
            )
            self.initialized_endpoints.add("/aria2/remove")

        if "/aria2/pause" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/pause",
                self.pause_download_async,
                methods=["POST"],
                summary="Pause download",
                description="Pause a download by ID",
            )
            self.initialized_endpoints.add("/aria2/pause")

        if "/aria2/resume" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/resume",
                self.resume_download_async,
                methods=["POST"],
                summary="Resume download",
                description="Resume a paused download by ID",
            )
            self.initialized_endpoints.add("/aria2/resume")

        # Register status endpoints
        if "/aria2/status/{gid}" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/status/{gid}",
                self.get_status_async,
                methods=["GET"],
                summary="Get download status",
                description="Get detailed status of a download by ID",
            )
            self.initialized_endpoints.add("/aria2/status/{gid}")

        if "/aria2/list" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/list",
                self.list_downloads_async,
                methods=["GET"],
                summary="List downloads",
                description="List all downloads with their status",
            )
            self.initialized_endpoints.add("/aria2/list")

        if "/aria2/purge" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/purge",
                self.purge_downloads_async,
                methods=["POST"],
                summary="Purge downloads",
                description="Purge completed/error/removed downloads",
            )
            self.initialized_endpoints.add("/aria2/purge")

        if "/aria2/global-stats" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/global-stats",
                self.get_global_status_async,
                methods=["GET"],
                summary="Get global statistics",
                description="Get global download statistics",
            )
            self.initialized_endpoints.add("/aria2/global-stats")

        # Register daemon endpoints
        if "/aria2/daemon/start" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/daemon/start",
                self.start_daemon_async,
                methods=["POST"],
                summary="Start Aria2 daemon",
                description="Start the Aria2 daemon with optional configuration",
            )
            self.initialized_endpoints.add("/aria2/daemon/start")

        if "/aria2/daemon/stop" not in self.initialized_endpoints:
            router.add_api_route(
                "/aria2/daemon/stop",
                self.stop_daemon_async,
                methods=["POST"],
                summary="Stop Aria2 daemon",
                description="Stop the Aria2 daemon",
            )
            self.initialized_endpoints.add("/aria2/daemon/stop")

        logger.info(
            f"Registered {len(self.initialized_endpoints)} Aria2 endpoints with AnyIO support"
        )
