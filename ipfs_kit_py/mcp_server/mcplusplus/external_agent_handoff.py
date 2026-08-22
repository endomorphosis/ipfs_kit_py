"""Bind external-agent handoff onto existing MCP++ profiles (EAAEF-113).

No new MCP++ profile is created. Storage, secret, proof-key and merge
authority are never granted by this binder. DurableExecutor is used only
when the admitted runtime configuration already includes it.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final


HANDOFF_PROFILE_BIND_SCHEMA: Final[str] = (
    "ipfs_kit_py/mcp_server/mcplusplus/external-agent-handoff@1"
)

ADMITTED_PROFILES: Final[frozenset[str]] = frozenset(
    {
        "interface",
        "mcp-idl",
        "profile-a",
        "artifact",
        "cid-native",
        "profile-b",
        "delegation",
        "ucan",
        "profile-c",
        "runtime",
        "execution-envelope",
        "event",
        "event-dag",
        "profile-f",
        "fencing",
        "durable-executor",
    }
)

STORAGE_AUTHORITY_EFFECTS: Final[frozenset[str]] = frozenset(
    {
        "storage",
        "backend",
        "object_store",
        "secret",
        "proof_key",
        "merge",
    }
)

HANDOFF_OPERATIONS: Final[tuple[str, ...]] = (
    "handoff",
    "preview",
    "attach",
    "status",
    "follow",
    "steer",
    "pause",
    "resume",
    "approve",
    "reject",
    "cancel",
    "explain",
    "doctor",
    "report",
    "export",
)


class ExternalAgentHandoffBindError(ValueError):
    """Unknown profile, storage grant, or unconfigured DurableExecutor."""

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def bind_handoff_operation(
    operation: str,
    *,
    profiles: Mapping[str, str] | None = None,
    effects: tuple[str, ...] = (),
    durable_executor_configured: bool = False,
    runtime_method: str | None = None,
) -> Mapping[str, Any]:
    """Map one handoff operation onto admitted MCP++ profile identifiers."""

    op = str(operation or "").strip()
    if op not in HANDOFF_OPERATIONS:
        raise ExternalAgentHandoffBindError(
            f"unknown handoff operation: {op}",
            reason_code="unknown_operation",
        )
    bound: dict[str, str] = {}
    for name, ident in dict(profiles or {}).items():
        key = str(name).strip().lower()
        if key not in ADMITTED_PROFILES:
            raise ExternalAgentHandoffBindError(
                f"unknown MCP++ profile: {name}",
                reason_code="unknown_profile",
            )
        if str(ident).strip().lower() in {"profile-i", "profile-j", "external-agent"}:
            raise ExternalAgentHandoffBindError(
                "new MCP++ profiles are not admitted",
                reason_code="new_profile_forbidden",
            )
        bound[key] = str(ident)
    forbidden = [effect for effect in effects if str(effect) in STORAGE_AUTHORITY_EFFECTS]
    if forbidden:
        raise ExternalAgentHandoffBindError(
            "storage and backend authority are not granted",
            reason_code="storage_authority_forbidden",
        )
    if runtime_method and not durable_executor_configured:
        raise ExternalAgentHandoffBindError(
            "DurableExecutor is not configured",
            reason_code="durable_executor_unconfigured",
        )
    return MappingProxyType(
        {
            "schema": HANDOFF_PROFILE_BIND_SCHEMA,
            "operation": op,
            "profiles": dict(bound),
            "durable_executor_configured": bool(durable_executor_configured),
            "storage_authority": False,
            "new_profile": False,
            "live_runtime_invoked": False,
            "preview_is_handoff": False,
        }
    )
