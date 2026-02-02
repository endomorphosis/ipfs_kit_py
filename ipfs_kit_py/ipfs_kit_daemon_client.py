"""IPFS-Kit daemon client.

This module is intentionally lightweight and designed to be safe to import in
unit tests. It provides a client API for checking daemon status and simple
routing helpers.

Some legacy code imports the top-level module name `ipfs_kit_daemon_client`.
A small shim at repo root re-exports this implementation.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import anyio
import psutil

logger = logging.getLogger(__name__)


class DaemonClient:
    """Client for communicating with the IPFS-Kit daemon.

    Current implementation is file/PID based (sufficient for tests and local
    dev). A future daemon HTTP/IPC API can replace these internals while
    preserving the public surface.
    """

    def __init__(self, daemon_url: str = "http://localhost:8899", timeout: int = 30):
        self.daemon_url = daemon_url
        self.timeout = timeout
        self.pid_file = "/tmp/ipfs_kit_daemon.pid"

    async def is_daemon_running(self) -> bool:
        try:
            if not os.path.exists(self.pid_file):
                return False

            with open(self.pid_file, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())

            return psutil.pid_exists(pid)
        except Exception as exc:
            logger.debug("Error checking daemon status: %s", exc)
            return False

    async def get_daemon_status(self) -> Dict[str, Any]:
        if not await self.is_daemon_running():
            return {"running": False, "error": "Daemon not running"}

        try:
            status_file = "/tmp/ipfs_kit_daemon_status.json"
            if os.path.exists(status_file):
                with open(status_file, "r", encoding="utf-8") as f:
                    status = json.load(f)
                status["running"] = True
                return status

            return {"running": True, "status": "unknown", "note": "Status file not available"}
        except Exception as exc:
            return {"running": True, "error": f"Failed to get status: {exc}"}

    async def get_backend_health(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        status = await self.get_daemon_status()
        if not status.get("running"):
            return {"error": "Daemon not running"}

        backends = status.get("daemon", {}).get("backends", {})
        if backend_name:
            return backends.get(backend_name, {"error": f"Backend {backend_name} not found"})
        return backends

    async def restart_backend(self, backend_name: str) -> Dict[str, Any]:
        if not await self.is_daemon_running():
            return {"success": False, "error": "Daemon not running"}
        logger.info("Would request restart of backend: %s", backend_name)
        return {"success": True, "message": f"Restart requested for {backend_name}"}

    async def start_daemon(self, config_file: Optional[str] = None) -> Dict[str, Any]:
        if await self.is_daemon_running():
            return {"success": True, "message": "Daemon already running"}

        try:
            cmd = ["python3", "ipfs_kit_daemon.py"]
            if config_file:
                cmd.extend(["--config", config_file])

            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            await anyio.sleep(2)
            if await self.is_daemon_running():
                return {"success": True, "message": "Daemon started successfully"}
            return {"success": False, "error": "Daemon failed to start"}
        except Exception as exc:
            return {"success": False, "error": f"Failed to start daemon: {exc}"}

    async def stop_daemon(self) -> Dict[str, Any]:
        if not await self.is_daemon_running():
            return {"success": True, "message": "Daemon not running"}

        try:
            with open(self.pid_file, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())

            os.kill(pid, 15)  # SIGTERM

            for _ in range(10):
                await anyio.sleep(1)
                if not await self.is_daemon_running():
                    return {"success": True, "message": "Daemon stopped"}

            try:
                os.kill(pid, 9)  # SIGKILL
                return {"success": True, "message": "Daemon force stopped"}
            except ProcessLookupError:
                return {"success": True, "message": "Daemon stopped"}
        except Exception as exc:
            return {"success": False, "error": f"Failed to stop daemon: {exc}"}


class IPFSKitClientMixin:
    """Mixin for components that want daemon-client functionality."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.daemon_client = DaemonClient()
        self._daemon_status_cache: Dict[str, Any] = {}
        self._last_daemon_check = 0.0
        self._daemon_check_interval = 30.0

    async def ensure_daemon_running(self) -> bool:
        try:
            if not await self.daemon_client.is_daemon_running():
                logger.info("Starting IPFS-Kit daemon...")
                result = await self.daemon_client.start_daemon()
                if not result.get("success"):
                    logger.error("Failed to start daemon: %s", result.get("error"))
                    return False
            return True
        except Exception as exc:
            logger.error("Error ensuring daemon running: %s", exc)
            return False

    async def get_cached_daemon_status(self) -> Dict[str, Any]:
        now = time.time()
        if (now - self._last_daemon_check) > self._daemon_check_interval:
            try:
                self._daemon_status_cache = await self.daemon_client.get_daemon_status()
                self._last_daemon_check = now
            except Exception as exc:
                logger.error("Error getting daemon status: %s", exc)
                if not self._daemon_status_cache:
                    self._daemon_status_cache = {"error": str(exc)}
        return self._daemon_status_cache


class RouteReader:
    """Routing helper that reads parquet indexes if available."""

    def __init__(self, index_path: str = "/tmp/ipfs_kit_indexes"):
        self.index_path = Path(index_path)
        self.index_path.mkdir(exist_ok=True)
        self._cache: Dict[str, Any] = {}
        self._last_cache_update = 0.0
        self._cache_ttl = 60.0

    def read_pin_index(self) -> Any:
        try:
            index_file = self.index_path / "pin_index.parquet"
            if not index_file.exists():
                return {}

            now = time.time()
            if (now - self._last_cache_update) < self._cache_ttl and "pin_index" in self._cache:
                return self._cache["pin_index"]

            try:
                import pandas as pd  # optional

                df = pd.read_parquet(index_file)
                index_data = df.to_dict("records")
                self._cache["pin_index"] = index_data
                self._last_cache_update = now
                return index_data
            except ImportError:
                logger.warning("pandas not available, cannot read parquet index")
                return {}
        except Exception as exc:
            logger.error("Error reading pin index: %s", exc)
            return {}

    def find_backends_for_cid(self, cid: str) -> List[str]:
        pin_index = self.read_pin_index()
        backends: List[str] = []
        for entry in pin_index or []:
            if entry.get("cid") == cid:
                backend = entry.get("backend")
                if backend and backend not in backends:
                    backends.append(backend)
        return backends

    def suggest_backend_for_new_pin(self, size: int = 0) -> str:
        _ = size
        return "ipfs"


# Convenience globals
route_reader = RouteReader()


def find_backends_for_cid(cid: str) -> List[str]:
    return route_reader.find_backends_for_cid(cid)


def suggest_backend_for_pin(size: int = 0) -> str:
    return route_reader.suggest_backend_for_new_pin(size)
