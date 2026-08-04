"""MCP GraphRAG wrapper (fail-closed) over the canonical package surface.

This module never returns success or a silent no-op when the package engine
cannot be imported or initialized.  All operations delegate to
``ipfs_kit_py.graphrag.dispatch`` so MCP request schemas and normalized
results/errors/CIDs stay byte-equivalent with package and CLI projections.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

logger = logging.getLogger(__name__)

try:
    from ipfs_kit_py import graphrag as _graphrag
except Exception as exc:  # pragma: no cover - import path is validated by tests
    # Fail closed at import time: do not leave a usable success-path stub.
    raise ImportError(
        "MCP GraphRAG wrapper cannot load the canonical package engine; "
        "import failure must not degrade to success/no-op"
    ) from exc

# Re-export the shared constants so MCP callers pin the same schemas.
GRAPHRAG_REQUEST_SCHEMA = _graphrag.GRAPHRAG_REQUEST_SCHEMA
GRAPHRAG_RESULT_SCHEMA = _graphrag.GRAPHRAG_RESULT_SCHEMA
GRAPHRAG_ERROR_SCHEMA = _graphrag.GRAPHRAG_ERROR_SCHEMA
GRAPHRAG_OPERATIONS = _graphrag.GRAPHRAG_OPERATIONS
MCPGraphRAGTools_V1 = _graphrag.MCPGraphRAGTools_V1


class GraphRAGEngineUnavailable(RuntimeError):
    """Raised when the MCP wrapper has no bound canonical engine."""


class GraphRAGSearchEngine:
    """MCP adapter that always delegates to the package interface.

    Unlike the historic wrapper, construction either binds a live package
    engine or raises.  Methods never invent a successful empty response when
    the engine is missing.
    """

    def __init__(self, **kwargs: Any) -> None:
        logger.info("MCP GraphRAGSearchEngine binding canonical package engine")
        try:
            self.engine = _graphrag.GraphRAGSearchEngine(**kwargs)
        except Exception as exc:
            logger.error("Failed to bind canonical GraphRAGSearchEngine: %s", exc, exc_info=True)
            self.engine = None
            raise GraphRAGEngineUnavailable(
                "GraphRAG engine failed to initialize; MCP refuses success/no-op"
            ) from exc
        if self.engine is None:
            raise GraphRAGEngineUnavailable(
                "GraphRAG engine is None after construction; MCP refuses success/no-op"
            )
        logger.info("MCP GraphRAGSearchEngine bound to package adapter")

    def _require_engine(self) -> Any:
        if self.engine is None:
            raise GraphRAGEngineUnavailable(
                "GraphRAG engine is not initialized; MCP refuses success/no-op"
            )
        return self.engine

    async def index_content(self, **kwargs: Any) -> dict[str, Any]:
        engine = self._require_engine()
        return await engine.index_content(**kwargs)

    async def search(self, **kwargs: Any) -> dict[str, Any]:
        engine = self._require_engine()
        return await engine.search(**kwargs)

    async def vector_search(self, **kwargs: Any) -> dict[str, Any]:
        engine = self._require_engine()
        return await engine.vector_search(**kwargs)

    async def hybrid_search(self, **kwargs: Any) -> dict[str, Any]:
        engine = self._require_engine()
        return await engine.hybrid_search(**kwargs)

    def dispatch(
        self,
        operation: str,
        request: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """MCP transport projection of the shared GraphRAG interface."""

        # Engine binding proves the package is loadable; dispatch is shared.
        self._require_engine()
        return _graphrag.mcp_call(operation, request, **kwargs)

    def cleanup(self) -> None:
        if self.engine is not None:
            logger.info("Cleaning up MCP GraphRAGSearchEngine wrapper")
            if hasattr(self.engine, "cleanup"):
                self.engine.cleanup()
            self.engine = None


def mcp_dispatch(
    operation: str,
    request: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Module-level MCP dispatch (no success path without package import)."""

    return _graphrag.mcp_call(operation, request, **kwargs)


def request_schemas() -> dict[str, dict[str, Any]]:
    return _graphrag.all_request_schemas()


__all__ = [
    "GraphRAGSearchEngine",
    "GraphRAGEngineUnavailable",
    "mcp_dispatch",
    "request_schemas",
    "GRAPHRAG_REQUEST_SCHEMA",
    "GRAPHRAG_RESULT_SCHEMA",
    "GRAPHRAG_ERROR_SCHEMA",
    "GRAPHRAG_OPERATIONS",
    "MCPGraphRAGTools_V1",
]
