"""Canonical core operations — single source of truth.

Every MCP tool, CLI command, and JS SDK call ultimately routes through these
async functions. They wrap the synchronous ``ipfs_kit`` orchestrator (run in a
worker thread so we stay cooperative under trio/anyio) and normalise results to
the aligned ``{"status": ...}`` envelope shared with ipfs_datasets_py.
"""
from __future__ import annotations

import functools
import inspect
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

import anyio

_kit = None
_backend_binding: ContextVar[Any | None] = ContextVar(
    "ipfs_kit_mcp_core_backend",
    default=None,
)


class _UnavailableBackend:
    """Typed sentinel used when the legacy live-kit constructor is unavailable."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


def get_kit():
    """Return an explicit binding or lazily construct the live legacy kit.

    Construction failure never selects a successful fake backend.  Tests and
    embedders that need a hermetic implementation must bind one explicitly
    with :func:`use_core_backend`.
    """
    global _kit
    bound = _backend_binding.get()
    if bound is not None:
        return bound
    if _kit is None:
        try:
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            _kit = ipfs_kit.create(auto_start_daemons=False)
        except Exception as error:  # pragma: no cover - environment without package extras
            _kit = _UnavailableBackend(type(error).__name__)
    return _kit


@contextmanager
def use_core_backend(backend: Any):
    """Temporarily bind one explicit backend for the current context.

    The binding is context-local, so concurrent requests cannot overwrite one
    another's provider.  A backend may expose synchronous or asynchronous
    operation methods; it is still responsible for returning the canonical
    ``{"success": bool, ...}`` provider result.
    """

    if backend is None:
        raise TypeError("core backend binding cannot be None")
    token = _backend_binding.set(backend)
    try:
        yield backend
    finally:
        _backend_binding.reset(token)


def _unavailable_result(method: str, reason: str) -> dict[str, Any]:
    return {
        "status": "error",
        "result": {
            "success": False,
            "operation": method,
            "error": "backend operation is unavailable",
            "error_type": "unsupported_operation",
            "reason": reason,
            "recoverable": False,
        },
    }


async def _call(method: str, /, **kwargs) -> dict[str, Any]:
    kit = get_kit()
    fn = getattr(kit, method, None)
    if not callable(fn):
        reason = getattr(kit, "reason", type(kit).__name__)
        return _unavailable_result(method, str(reason))
    try:
        if inspect.iscoroutinefunction(fn):
            raw = await fn(**kwargs)
        else:
            raw = await anyio.to_thread.run_sync(functools.partial(fn, **kwargs))
            if inspect.isawaitable(raw):
                raw = await raw
    except Exception as error:
        return {
            "status": "error",
            "result": {
                "success": False,
                "operation": method,
                "error": "backend operation failed",
                "error_type": type(error).__name__,
                "recoverable": False,
            },
        }
    if not isinstance(raw, dict) or not isinstance(raw.get("success"), bool):
        return {
            "status": "error",
            "result": {
                "success": False,
                "operation": method,
                "error": "backend returned an invalid operation result",
                "error_type": "invalid_backend_result",
                "recoverable": False,
            },
        }
    ok = raw["success"]
    return {
        "status": "success" if ok else "error",
        "result": raw,
    }


__all__ = ["get_kit", "use_core_backend"]
