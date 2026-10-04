"""
Aria2 model for MCP server.

This module provides a model for interacting with Aria2 through the MCP server.
"""

import logging
import time

from ipfs_kit_py.aria2_kit import aria2_kit

# Import from ipfs_kit_py


# Configure logger
logger = logging.getLogger(__name__)


class Aria2Model:
    """Model for Aria2 operations in MCP server."""

    def __init__(self, aria2_kit_instance = None, cache_manager = None, credential_manager = None):
        """
        Initialize the Aria2 model.

        Args:
            aria2_kit_instance: Instance of aria2_kit to use
            cache_manager: MCP cache manager for caching results
            credential_manager: MCP credential manager for storing credentials
        """
        self.aria2_kit_instance = aria2_kit_instance
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager
        self.operation_stats = {
            "downloads_started": 0,
            "downloads_completed": 0,
            "bytes_downloaded": 0,
            "operation_count": 0,
            "error_count": 0,
        }

        # If no aria2_kit instance is provided, create one
        if self.aria2_kit_instance is None:
            # Try to get RPC credentials from credential manager
            resources = {}
            if self.credential_manager:
                try:
                    credentials = self.credential_manager.get_credential("aria2", "default")
                    if credentials and "rpc_secret" in credentials:
                        resources["rpc_secret"] = credentials["rpc_secret"]
                    if credentials and "rpc_url" in credentials:
                        resources["rpc_url"] = credentials["rpc_url"]
                except Exception as e:
                    logger.warning(f"Failed to get Aria2 credentials: {e}")

            # Create the aria2_kit instance with available resources
            self.aria2_kit = aria2_kit(resources=resources)
        else:
            self.aria2_kit = self.aria2_kit_instance

        logger.info("Aria2 model initialized")

    def add_uri(self, uris, filename = None, options = None):
        """
        Add a download by URI.

        Args:
            uris: URI or list of URIs to download
            filename: Optional filename for the download
            options: Optional advanced options for the download

        Returns:
            Result dictionary with download information
        """
        self.operation_stats["operation_count"] += 1

        # Call aria2_kit method
        result = self.aria2_kit.add_uri(uris=uris, filename=filename, options=options)

        # Update stats
        if result.get("success", False):
            self.operation_stats["downloads_started"] += 1
        else:
            self.operation_stats["error_count"] += 1

        return result

    def add_torrent(self, torrent, options = None):
        """
        Add a download by torrent file.

        Args:
            torrent: Path to torrent file or torrent file content
            options: Optional advanced options for the download

        Returns:
            Result dictionary with download information
        """
        self.operation_stats["operation_count"] += 1

        # Call aria2_kit method
        result = self.aria2_kit.add_torrent(torrent=torrent, options=options)

        # Update stats
        if result.get("success", False):
            self.operation_stats["downloads_started"] += 1
        else:
            self.operation_stats["error_count"] += 1

        return result

    def add_metalink(self, metalink, options = None):
        """
        Add a download by metalink file.

        Args:
            metalink: Path to metalink file or metalink content
            options: Optional advanced options for the download

        Returns:
            Result dictionary with download information
        """
        self.operation_stats["operation_count"] += 1

        # Call aria2_kit method
        result = self.aria2_kit.add_metalink(metalink=metalink, options=options)

        # Update stats
        if result.get("success", False):
            self.operation_stats["downloads_started"] += 1
        else:
            self.operation_stats["error_count"] += 1

        return result

    def remove_download(self, gid, force=False):
        """
        Remove a download.

        Args:
            gid: Download ID
            force: Whether to force removal

        Returns:
            Result dictionary with operation status
        """
        self.operation_stats["operation_count"] += 1

        # Call aria2_kit method
        result = self.aria2_kit.remove_download(gid=gid, force=force)

        # Update stats
        if not result.get("success", False):
            self.operation_stats["error_count"] += 1

        return result

    def pause_download(self, gid, force=False):
        """
        Pause a download.

        Args:
            gid: Download ID
            force: Whether to force pause

        Returns:
            Result dictionary with operation status
        """
        self.operation_stats["operation_count"] += 1

        # Call aria2_kit method
        result = self.aria2_kit.pause_download(gid=gid, force=force)

        # Update stats
        if not result.get("success", False):
            self.operation_stats["error_count"] += 1

        return result

    def resume_download(self, gid):
        """
        Resume a paused download.

        Args:
            gid: Download ID

        Returns:
            Result dictionary with operation status
        """
        self.operation_stats["operation_count"] += 1

        # Call aria2_kit method
        result = self.aria2_kit.resume_download(gid=gid)

        # Update stats
        if not result.get("success", False):
            self.operation_stats["error_count"] += 1

        return result

    def get_status(self, gid):
        """
        Get download status.

        Args:
            gid: Download ID

        Returns:
            Result dictionary with download status
        """
        self.operation_stats["operation_count"] += 1

        # Check cache first if available
        cache_key = f"aria2_status_{gid}"
        if self.cache_manager:
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                return cached_result

        # Call aria2_kit method
        result = self.aria2_kit.get_status(gid=gid)

        # Update stats
        if not result.get("success", False):
            self.operation_stats["error_count"] += 1
        else:
            # Check for completed downloads to update stats
            if result.get("state") == "complete" and result.get("total_length"):
                # Check if already counted using cache
                if self.cache_manager:
                    prev_result = self.cache_manager.get(cache_key)
                    if not prev_result or prev_result.get("state") != "complete":
                        self.operation_stats["downloads_completed"] += 1
                        self.operation_stats["bytes_downloaded"] += result.get("total_length", 0)
                else:
                    # Without cache, we might count it multiple times, but better than not counting
                    self.operation_stats["downloads_completed"] += 1
                    self.operation_stats["bytes_downloaded"] += result.get("total_length", 0)

        # Cache the result if available
        if self.cache_manager and result.get("success", False):
            # Short TTL for active downloads, longer for completed ones
            ttl = 300 if result.get("state") == "complete" else 10
            self.cache_manager.put(cache_key, result, ttl=ttl)

        return result

    def list_downloads(self):
        """
        List all downloads.

        Returns:
            Result dictionary with download list
        """
        self.operation_stats["operation_count"] += 1

        # Check cache first if available
        cache_key = "aria2_downloads_list"
        if self.cache_manager:
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                return cached_result

        # Call aria2_kit method
        result = self.aria2_kit.list_downloads()

        # Update stats
        if not result.get("success", False):
            self.operation_stats["error_count"] += 1

        # Cache the result if available
        if self.cache_manager and result.get("success", False):
            # Short TTL to ensure the list stays current
            self.cache_manager.put(cache_key, result, ttl=5)

        return result

    def purge_downloads(self):
        """
        Purge completed/error/removed downloads.

        Returns:
            Result dictionary with operation status
        """
        self.operation_stats["operation_count"] += 1

        # Call aria2_kit method
        result = self.aria2_kit.purge_downloads()

        # Update stats
        if not result.get("success", False):
            self.operation_stats["error_count"] += 1

        # Clear list cache if available
        if self.cache_manager:
            self.cache_manager.delete("aria2_downloads_list")

        return result

    def get_global_status(self):
        """
        Get global download statistics.

        Returns:
            Result dictionary with global statistics
        """
        self.operation_stats["operation_count"] += 1

        # Check cache first if available
        cache_key = "aria2_global_status"
        if self.cache_manager:
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                return cached_result

        # Call aria2_kit method
        result = self.aria2_kit.get_global_status()

        # Update stats
        if not result.get("success", False):
            self.operation_stats["error_count"] += 1

        # Cache the result if available
        if self.cache_manager and result.get("success", False):
            # Very short TTL to ensure statistics stay current
            self.cache_manager.put(cache_key, result, ttl=2)

        return result

    def start_daemon(self, options = None):
        """
        Start the Aria2 daemon.

        Args:
            options: Optional daemon configuration options

        Returns:
            Result dictionary with operation status
        """
        self.operation_stats["operation_count"] += 1

        # Call aria2_kit method
        result = self.aria2_kit.start_daemon(**(options or {}))

        # Update stats
        if not result.get("success", False):
            self.operation_stats["error_count"] += 1

        return result

    def stop_daemon(self):
        """
        Stop the Aria2 daemon.

        Returns:
            Result dictionary with operation status
        """
        self.operation_stats["operation_count"] += 1

        # Call aria2_kit method
        result = self.aria2_kit.stop_daemon()

        # Update stats
        if not result.get("success", False):
            self.operation_stats["error_count"] += 1

        return result

    def get_version(self):
        """
        Get Aria2 version information.

        Returns:
            Result dictionary with version information
        """
        self.operation_stats["operation_count"] += 1

        # Check cache first if available
        cache_key = "aria2_version"
        if self.cache_manager:
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                return cached_result

        # Call aria2_kit method
        result = self.aria2_kit.get_version()

        # Update stats
        if not result.get("success", False):
            self.operation_stats["error_count"] += 1

        # Cache the result if available (version rarely changes)
        if self.cache_manager and result.get("success", False):
            self.cache_manager.put(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def reset(self):
        """Reset model state."""
        # Reset operation stats
        self.operation_stats = {
            "downloads_started": 0,
            "downloads_completed": 0,
            "bytes_downloaded": 0,
            "operation_count": 0,
            "error_count": 0,
        }

        # Clear caches if available
        if self.cache_manager:
            # Clear all aria2-related caches
            keys_to_delete = []
            for key in self.cache_manager.get_keys():
                if key.startswith("aria2_"):
                    keys_to_delete.append(key)
            for key in keys_to_delete:
                self.cache_manager.delete(key)

        logger.info("Aria2 model reset")
        return {"success": True, "message": "Aria2 model reset"}

    def get_stats(self):
        """
        Get model statistics.

        Returns:
            Dictionary with model statistics
        """
        stats = {
            "operations": self.operation_stats,
            "status": "active",
            "timestamp": time.time(),
        }

        # Add daemon status if available
        try:
            daemon_status = self.aria2_kit.daemon_running
            stats["daemon_running"] = daemon_status
        except Exception:
            stats["daemon_running"] = False

        return stats
