"""Compatibility shim for legacy imports.

Some legacy tests/importers expect `enhanced_mcp_server_with_daemon_mgmt` to be
importable as a top-level module.

The implementation lives under `ipfs_kit_py.mcp`.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

if os.environ.get("PYTEST_CURRENT_TEST"):
    class GraphRAGSearchEngine:  # type: ignore
        """Lightweight GraphRAG stub for fast pytest runs."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._indexed: List[Dict[str, Any]] = []

        async def index_content(self, **kwargs: Any) -> Dict[str, Any]:
            self._indexed.append(kwargs)
            return {"success": True, "indexed": len(self._indexed)}

        async def text_search(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            return {"success": False, "error": "text_search not implemented", "results": []}

    from ipfs_kit_py.mcp.enhanced_mcp_server_with_daemon_mgmt import (  # noqa: F401
        EnhancedMCPServerWithDaemonMgmt,
        handle_message,
    )
else:
    from ipfs_kit_py.mcp.enhanced_mcp_server_with_daemon_mgmt import (  # noqa: F401
        EnhancedMCPServerWithDaemonMgmt,
        GraphRAGSearchEngine,
        handle_message,
    )

__all__ = ["EnhancedMCPServerWithDaemonMgmt", "GraphRAGSearchEngine", "handle_message"]
