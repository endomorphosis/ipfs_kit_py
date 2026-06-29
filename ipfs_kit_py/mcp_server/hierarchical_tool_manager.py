"""Hierarchical Tool Manager for the ipfs_kit_py MCP++ server.

Mirrors the ipfs_datasets_py manager: exposes meta-tools (list_categories,
list_tools, get_schema, dispatch) instead of flooding the top level, with a
per-category circuit breaker and structured per-request tracing.
"""
from __future__ import annotations

import inspect
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from .exceptions import CategoryNotFoundError, ToolExecutionError, ToolNotFoundError
from .tool_metadata import build_input_schema
from .tools import TOOL_GROUPS

logger = logging.getLogger(__name__)


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> str:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            if time.monotonic() - self._opened_at >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def on_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def on_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()


class HierarchicalToolManager:
    def __init__(self) -> None:
        self._groups = TOOL_GROUPS
        self._breakers: Dict[str, CircuitBreaker] = {}

    def list_categories(self) -> List[Dict[str, Any]]:
        return [{"name": c, "tool_count": len(t)} for c, t in self._groups.items()]

    def list_tools(self, category: str) -> List[str]:
        if category not in self._groups:
            raise CategoryNotFoundError(category)
        return list(self._groups[category].keys())

    def get_schema(self, category: str, tool: str) -> Dict[str, Any]:
        fn = self._lookup(category, tool)
        meta = getattr(fn, "_mcp_metadata", None)
        return {
            "name": tool,
            "description": getattr(meta, "summary", "") or (fn.__doc__ or "").strip(),
            "inputSchema": build_input_schema(fn),
            "tags": getattr(meta, "tags", []),
            "deprecated": getattr(meta, "deprecated", False),
        }

    def all_tool_schemas(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for cat, tools in self._groups.items():
            for tool in tools:
                s = self.get_schema(cat, tool)
                s["category"] = cat
                out.append(s)
        return out

    def _lookup(self, category: str, tool: str) -> Callable:
        if category not in self._groups:
            raise CategoryNotFoundError(category)
        if tool not in self._groups[category]:
            raise ToolNotFoundError(category, tool)
        return self._groups[category][tool]

    async def dispatch(self, category: str, tool: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        request_id = str(uuid.uuid4())
        t0 = time.monotonic()
        breaker = self._breakers.setdefault(category, CircuitBreaker(category))
        if breaker.state == CircuitState.OPEN:
            return {"status": "error", "error": f"circuit '{category}' open", "request_id": request_id}
        fn = self._lookup(category, tool)
        params = params or {}
        sig = inspect.signature(fn)
        filtered = {k: v for k, v in params.items() if k in sig.parameters}
        try:
            result = await fn(**filtered) if inspect.iscoroutinefunction(fn) else fn(**filtered)
            breaker.on_success()
            result.setdefault("request_id", request_id)
            logger.info("dispatch ok request_id=%s tool=%s/%s ms=%.1f", request_id, category, tool, (time.monotonic() - t0) * 1000)
            return result
        except Exception as e:
            breaker.on_failure()
            logger.error("dispatch err request_id=%s tool=%s/%s err=%s", request_id, category, tool, e)
            return {"status": "error", "error": str(e), "category": category, "tool": tool, "request_id": request_id}
