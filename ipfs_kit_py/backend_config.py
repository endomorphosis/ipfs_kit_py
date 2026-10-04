"""Backend configuration loader for real API integrations."""

from __future__ import annotations

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def initialize_backend_config(log_status: bool = True) -> Dict[str, Any]:
    """Initialize backend configuration and environment variables.

    Loads config + credentials via real_api_storage_backends and optionally logs status.
    Returns a dict of backend status entries.
    """
    try:
        from ipfs_kit_py import real_api_storage_backends
    except Exception as exc:
        logger.warning(f"Failed to import real_api_storage_backends: {exc}")
        return {}

    try:
        statuses = real_api_storage_backends.get_all_backends_status()
    except Exception as exc:
        logger.warning(f"Failed to load backend status: {exc}")
        return {}

    if log_status:
        for backend, status in statuses.items():
            if status.get("exists"):
                if status.get("enabled"):
                    mode = "SIMULATION" if status.get("simulation") else "REAL"
                    creds = "✅" if status.get("has_credentials") else "❌"
                    logger.info(f"Backend {backend}: {mode} mode, Credentials: {creds}")
                else:
                    logger.info(f"Backend {backend}: DISABLED")
            else:
                logger.info(f"Backend {backend}: NOT FOUND")

    return statuses


def get_backend_statuses() -> Dict[str, Any]:
    """Return backend status without logging."""
    return initialize_backend_config(log_status=False)
