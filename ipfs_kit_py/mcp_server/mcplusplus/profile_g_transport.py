"""Profile G provider binding shared by IPFS Kit HTTP and Profile E services."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any, Callable

PROFILE = "mcp++/risk-scheduling"
PREFIXES = ("mcp++/goals/", "mcp++/tasks/", "mcp++/risk/", "mcp++/neighborhood/", "mcp++/schedule/")
METHODS = (
    "mcp++/risk/profile", "mcp++/goals/create", "mcp++/goals/get", "mcp++/goals/list",
    "mcp++/goals/decompose", "mcp++/goals/select", "mcp++/tasks/create", "mcp++/tasks/get",
    "mcp++/tasks/list", "mcp++/tasks/ready", "mcp++/risk/assess", "mcp++/risk/evidence",
    "mcp++/risk/history", "mcp++/neighborhood/query", "mcp++/neighborhood/attest",
    "mcp++/schedule/frontier", "mcp++/schedule/status", "mcp++/schedule/propose",
    "mcp++/schedule/claim", "mcp++/schedule/renew", "mcp++/schedule/release",
    "mcp++/schedule/resolve", "mcp++/schedule/reconcile",
)
ERROR_NUMBERS = {
    "G_INVALID_ARTIFACT": -32602, "G_CAPABILITY_NOT_NEGOTIATED": -32040,
    "G_CID_MISMATCH": -32041, "G_AUTHORITY_DENIED": -32042, "G_POLICY_DENIED": -32043,
    "G_NOT_READY": -32044, "G_IDEMPOTENCY_CONFLICT": -32045, "G_CLAIM_CONFLICT": -32046,
    "G_LEASE_EXPIRED": -32047, "G_QUORUM_UNAVAILABLE": -32049, "G_LIMIT_EXCEEDED": -32050,
    "G_PROVIDER_UNAVAILABLE": -32051, "G_EVIDENCE_INVALID": -32052, "G_REDACTED": -32053,
}


class ProfileGError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable
        self.details = dict(details or {})

    def data(self) -> dict[str, Any]:
        result = {"code": self.code, "message": self.message, "retryable": self.retryable}
        if self.details:
            result["details"] = self.details
        return result


class ProfileGDispatcher:
    def __init__(self, backend: Callable[[str, Mapping[str, Any]], Any] | None = None):
        self.backend = backend

    @property
    def metadata(self) -> dict[str, Any]:
        return {"version": "1.0", "artifact_schema_major": 1, "provider": "ipfs_kit_py",
                "transports": ["jsonrpc-http", "mcp+p2p"], "methods": list(METHODS)}

    def dispatch(self, method: str, params: Mapping[str, Any]) -> Any:
        if method not in METHODS or not isinstance(params, Mapping):
            raise ProfileGError("G_INVALID_ARTIFACT", "invalid Profile G method or params")
        backend = self.backend
        if backend is None:
            try:
                from ipfs_datasets_py.mcp_server.profile_g_service import get_profile_g_service
                backend = get_profile_g_service().dispatch
            except (ImportError, ModuleNotFoundError):
                backend = None
        if backend is None:
            if method == "mcp++/risk/profile":
                return self.metadata
            raise ProfileGError("G_PROVIDER_UNAVAILABLE", "Profile G provider is unavailable", retryable=True, details={"method": method})
        try:
            return backend(method, dict(params))
        except ProfileGError:
            raise
        except Exception as error:
            code = str(getattr(error, "code", "G_PROVIDER_UNAVAILABLE"))
            if code not in ERROR_NUMBERS:
                code = "G_PROVIDER_UNAVAILABLE"
            raise ProfileGError(code, str(getattr(error, "message", str(error))),
                                retryable=bool(getattr(error, "retryable", False)),
                                details=getattr(error, "details", None)) from error


_LOCK = threading.Lock()
_DISPATCHER: ProfileGDispatcher | None = None


def get_dispatcher() -> ProfileGDispatcher:
    global _DISPATCHER
    if _DISPATCHER is None:
        with _LOCK:
            if _DISPATCHER is None:
                _DISPATCHER = ProfileGDispatcher()
    return _DISPATCHER


def configure_dispatcher(dispatcher: ProfileGDispatcher) -> None:
    global _DISPATCHER
    with _LOCK:
        _DISPATCHER = dispatcher


__all__ = ["ERROR_NUMBERS", "METHODS", "PREFIXES", "PROFILE", "ProfileGDispatcher", "ProfileGError", "configure_dispatcher", "get_dispatcher"]
