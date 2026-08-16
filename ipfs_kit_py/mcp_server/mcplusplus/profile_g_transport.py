"""Profile G provider binding shared by IPFS Kit HTTP and Profile E services.

Binds the local RuntimeProfileG@1 fencing runtime for schedule methods when no
external datasets/accelerate provider is configured, so stale fenced completions
are rejected fail-closed with normative ``G_STALE_FENCE`` wire codes (MCPP-069).
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any, Callable

from .profile_g import (
    ERROR_NUMBERS as PROFILE_G_ERROR_NUMBERS,
    INTERFACE,
    RuntimeProfileG,
    configure_runtime,
    get_runtime,
)

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

# Wire map includes G_STALE_FENCE so fencing denials are not remapped to
# G_PROVIDER_UNAVAILABLE when the local runtime is the active backend.
ERROR_NUMBERS = {
    "G_INVALID_ARTIFACT": -32602,
    "G_CAPABILITY_NOT_NEGOTIATED": -32040,
    "G_CID_MISMATCH": -32041,
    "G_AUTHORITY_DENIED": -32042,
    "G_POLICY_DENIED": -32043,
    "G_NOT_READY": -32044,
    "G_IDEMPOTENCY_CONFLICT": -32045,
    "G_CLAIM_CONFLICT": -32046,
    "G_LEASE_EXPIRED": -32047,
    "G_STALE_FENCE": -32048,
    "G_QUORUM_UNAVAILABLE": -32049,
    "G_LIMIT_EXCEEDED": -32050,
    "G_PROVIDER_UNAVAILABLE": -32051,
    "G_EVIDENCE_INVALID": -32052,
    "G_REDACTED": -32053,
    "G_NOT_FOUND": -32044,
    "G_COMPLETION_CONFLICT": -32046,
    "G_COORDINATION_UNAVAILABLE": -32049,
}
# Keep transport map aligned with the runtime module constants.
ERROR_NUMBERS.update(PROFILE_G_ERROR_NUMBERS)

_LOCAL_RUNTIME_METHODS = frozenset({
    "mcp++/risk/profile",
    "mcp++/schedule/status",
    "mcp++/schedule/resolve",
    "mcp++/schedule/renew",
    "mcp++/schedule/release",
    "mcp++/schedule/reconcile",
})


class ProfileGError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable
        self.details = dict(details or {})

    def data(self) -> dict[str, Any]:
        result = {"code": self.code, "message": self.message, "retryable": self.retryable}
        if self.details:
            result["details"] = self.details
        return result


class ProfileGDispatcher:
    """Dispatch Profile G methods to an injected backend or the local runtime."""

    def __init__(
        self,
        backend: Callable[[str, Mapping[str, Any]], Any] | None = None,
        *,
        runtime: RuntimeProfileG | None = None,
    ):
        self.backend = backend
        self._runtime = runtime

    @property
    def runtime(self) -> RuntimeProfileG:
        return self._runtime if self._runtime is not None else get_runtime()

    @property
    def metadata(self) -> dict[str, Any]:
        meta = {
            "version": "1.0",
            "artifact_schema_major": 1,
            "provider": "ipfs_kit_py",
            "interface": INTERFACE,
            "transports": ["jsonrpc-http", "mcp+p2p"],
            "methods": list(METHODS),
        }
        meta.update(self.runtime.metadata())
        meta["provider"] = "ipfs_kit_py"
        meta["methods"] = list(METHODS)
        return meta

    def _local_backend(self, method: str, params: Mapping[str, Any]) -> Any:
        return self.runtime.dispatch(method, params)

    def _wrap_backend_error(self, error: BaseException) -> ProfileGError:
        code = str(getattr(error, "code", "G_PROVIDER_UNAVAILABLE"))
        if code not in ERROR_NUMBERS:
            code = "G_PROVIDER_UNAVAILABLE"
        details = getattr(error, "details", None)
        return ProfileGError(
            code,
            str(getattr(error, "message", str(error))),
            retryable=bool(getattr(error, "retryable", False)),
            details=details if isinstance(details, Mapping) else None,
        )

    def dispatch(self, method: str, params: Mapping[str, Any]) -> Any:
        if method not in METHODS or not isinstance(params, Mapping):
            raise ProfileGError("G_INVALID_ARTIFACT", "invalid Profile G method or params")

        # Fencing-critical schedule methods are owned by RuntimeProfileG@1 on
        # kit (datasets only implements goals/tasks/risk advisory paths).
        if method in _LOCAL_RUNTIME_METHODS and self.backend is None:
            try:
                return self._local_backend(method, dict(params))
            except ProfileGError:
                raise
            except Exception as error:
                raise self._wrap_backend_error(error) from error

        backend = self.backend
        if backend is None:
            try:
                from ipfs_datasets_py.mcp_server.profile_g_service import get_profile_g_service
                backend = get_profile_g_service().dispatch
            except (ImportError, ModuleNotFoundError):
                backend = None
        if backend is None:
            if method in _LOCAL_RUNTIME_METHODS:
                try:
                    return self._local_backend(method, dict(params))
                except ProfileGError:
                    raise
                except Exception as error:
                    raise self._wrap_backend_error(error) from error
            raise ProfileGError(
                "G_PROVIDER_UNAVAILABLE",
                "Profile G provider is unavailable",
                retryable=True,
                details={"method": method},
            )
        try:
            return backend(method, dict(params))
        except ProfileGError:
            raise
        except Exception as error:
            # Datasets returns G_PROVIDER_UNAVAILABLE for lease/fencing methods;
            # fall back to the bound kit runtime so completions stay fenced.
            code = str(getattr(error, "code", ""))
            if code == "G_PROVIDER_UNAVAILABLE" and method in _LOCAL_RUNTIME_METHODS:
                try:
                    return self._local_backend(method, dict(params))
                except ProfileGError:
                    raise
                except Exception as local_error:
                    raise self._wrap_backend_error(local_error) from local_error
            raise self._wrap_backend_error(error) from error


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


__all__ = [
    "ERROR_NUMBERS",
    "INTERFACE",
    "METHODS",
    "PREFIXES",
    "PROFILE",
    "ProfileGDispatcher",
    "ProfileGError",
    "RuntimeProfileG",
    "configure_dispatcher",
    "configure_runtime",
    "get_dispatcher",
    "get_runtime",
]
