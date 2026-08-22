"""Short-lived opaque secret broker for leased workers (EAAEF-124).

Handles never appear as secret bytes in events. Resolve is bound to the
current lease/task/policy. Revocation at checkpoint/terminal fails later
resolves. No live KMS is required.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final
from uuid import uuid4


BROKER_SCHEMA: Final[str] = "ipfs_kit_py/secret-broker/external-worker@1"


class SecretBrokerError(ValueError):
    """Opaque handle could not be resolved under the current lease."""

    def __init__(self, message: str, *, reason_code: str = "denied") -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class OpaqueHandle:
    handle_id: str
    lease_id: str
    task_id: str
    policy_id: str

    def as_event_field(self) -> str:
        return self.handle_id

    def to_event(self) -> Mapping[str, str]:
        return MappingProxyType(
            {
                "handle_id": self.handle_id,
                "lease_id": self.lease_id,
                "task_id": self.task_id,
                "policy_id": self.policy_id,
            }
        )


class SecretBroker:
    """In-memory broker. Secret material is never copied into events."""

    def __init__(self, root: Path | str | None = None) -> None:
        self._root = Path(root) if root is not None else None
        if self._root is not None:
            self._root.mkdir(parents=True, exist_ok=True)
        self._secrets: dict[str, str] = {}
        self._meta: dict[str, OpaqueHandle] = {}
        self._revoked: set[str] = set()

    def issue(
        self,
        secret: str,
        *,
        lease_id: str,
        task_id: str,
        policy_id: str,
    ) -> OpaqueHandle:
        handle = OpaqueHandle(
            handle_id=f"opaque:{uuid4().hex}",
            lease_id=lease_id,
            task_id=task_id,
            policy_id=policy_id,
        )
        self._secrets[handle.handle_id] = secret
        self._meta[handle.handle_id] = handle
        return handle

    def resolve(
        self,
        handle: OpaqueHandle | str,
        lease_id: str | None = None,
        task_id: str | None = None,
        policy_id: str | None = None,
        **kwargs: str,
    ) -> str:
        lease_id = kwargs.get("lease_id", lease_id)
        task_id = kwargs.get("task_id", task_id)
        policy_id = kwargs.get("policy_id", policy_id)
        handle_id = handle.handle_id if isinstance(handle, OpaqueHandle) else str(handle)
        if handle_id in self._revoked:
            raise SecretBrokerError("handle is revoked", reason_code="revoked")
        meta = self._meta.get(handle_id)
        if meta is None:
            raise SecretBrokerError("unknown handle", reason_code="unknown_handle")
        if lease_id != meta.lease_id or task_id != meta.task_id or policy_id != meta.policy_id:
            raise SecretBrokerError(
                "handle is not bound to this lease/task/policy",
                reason_code="lease_mismatch",
            )
        return self._secrets[handle_id]

    def redact(self, event: Mapping[str, Any]) -> Mapping[str, Any]:
        redacted: dict[str, Any] = {}
        secret_values = set(self._secrets.values())
        for key, value in event.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in ("secret", "token", "password", "api_key")):
                redacted[key] = "[redacted]"
            elif isinstance(value, str) and value in secret_values:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = value
        return MappingProxyType(redacted)

    def revoke(self, handle: OpaqueHandle | str) -> None:
        handle_id = handle.handle_id if isinstance(handle, OpaqueHandle) else str(handle)
        self._revoked.add(handle_id)
        self._secrets.pop(handle_id, None)
