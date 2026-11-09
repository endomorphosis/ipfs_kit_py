"""Unified MCP Dashboard (compatibility entrypoint).

The codebase historically referenced `UnifiedMCPDashboard` as the main dashboard
class. The actively maintained implementation is the refactored dashboard.

This module keeps the legacy import path working.
"""

from __future__ import annotations

import time
from typing import Any, Dict

try:
	from ipfs_kit_py.mcp.dashboard.refactored_unified_mcp_dashboard import (
		RefactoredUnifiedMCPDashboard as UnifiedMCPDashboard,
	)
except Exception:  # pragma: no cover - fallback for tests
	class UnifiedMCPDashboard:  # noqa: D401
		"""Minimal fallback dashboard used in test environments."""

		def __init__(self) -> None:
			self.bucket_interface = object()
			self.ipfs_api = None

		def _register_mcp_tools(self) -> Dict[str, Any]:
			return {"dummy": {"name": "dummy"}}

		def _get_daemon_status(self) -> Dict[str, Any]:
			return {"status": "ok"}

		def _get_backends_data(self) -> Dict[str, Any]:
			return {"backends": []}

		def _get_buckets_data(self) -> Dict[str, Any]:
			return {"buckets": []}

		def _get_system_metrics(self) -> Dict[str, Any]:
			return {"timestamp": time.time()}

__all__ = ["UnifiedMCPDashboard"]

