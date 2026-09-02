"""Live local durable filesystem backend (PCPR-020).

This is the current-head local POSIX store used to requalify Kit local
durability. It is not a mock, not a hermetic reference, and not a
production-authorized or closed PCPR release.

Fail-closed invariants:

* objects and CID sidecars are published atomically after fsync;
* every get rehashes bytes against the persisted CID sidecar;
* process restart reconstructs state from disk, not from memory;
* secret-bearing configuration and metadata are rejected;
* deadlines and cancellation fail closed as typed Unavailable;
* hermetic/simulated adapters cannot be substituted for this backend.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Final, Optional

from ipfs_kit_py.core.operation_contracts import (
    DurabilityEvidence,
    DurabilityMode,
    EffectEvidence,
    EffectKind,
    ErrorCategory,
    ErrorCode,
    EvidenceKind,
    OperationResult,
    OperationState,
    Retryability,
    StorageError,
)


SCHEMA: Final[str] = "ipfs_kit_py/assurance/local-durable@1"
INTERFACE: Final[str] = "LiveLocalFilesystemAdapter@1"
MANIFEST_SCHEMA: Final[str] = "ipfs_kit_py/assurance/local-durable-manifest@1"
BACKEND_ID: Final[str] = "local_filesystem"
CERTIFICATION_SCOPE: Final[str] = (
    "pcpr-020-local-durable-python; not a closed PCPR release"
)
LARGE_OBJECT_BYTES: Final[int] = 1024 * 1024
_SECRET_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "secret",
    "token",
    "password",
    "credential",
    "authorization",
    "api_key",
    "private_key",
    "bearer",
)
_MANIFEST_NAME: Final[str] = "manifest.json"


class LiveLocalBackendError(RuntimeError):
    """Typed local-durable failure carrying a StorageError."""

    def __init__(self, error: StorageError) -> None:
        self.error = error
        super().__init__(error.message)


@dataclass(frozen=True)
class LiveLocalResult:
    """One durable local operation result."""

    operation: str
    canonical_result: OperationResult
    data: bytes = b""
    items: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    observed_effect_count: int = 0

    @property
    def success(self) -> bool:
        return self.canonical_result.success

    @property
    def state(self) -> OperationState:
        return self.canonical_result.state

    @property
    def resulting_content_cid(self) -> str:
        return self.canonical_result.resulting_content_cid


class LiveLocalFilesystemAdapter:
    """Restartable local POSIX store with CID sidecars and fsync publication.

    ``live_provider`` is true because the local filesystem is the live
    backend under test. That is not production authorization, not a
    hermetic fixture, and not a simulated success.
    """

    backend_id = BACKEND_ID
    provider_kind = "filesystem"
    is_hermetic = False
    live_provider = True
    provider_certified = False
    production_authorized = False
    simulated = False
    certification_scope = CERTIFICATION_SCOPE

    def __init__(
        self,
        root: str | Path,
        *,
        configuration: Optional[Mapping[str, Any]] = None,
        create: bool = True,
    ) -> None:
        self.validate_configuration({} if configuration is None else configuration)
        self.root = Path(root).resolve()
        self._objects_root = self.root / "objects"
        self._manifest_path = self.root / _MANIFEST_NAME
        self._lock = threading.RLock()
        self._closed = False
        self._effect_count = 0
        self._metadata: dict[str, dict[str, Any]] = {}
        self._idempotency: dict[str, dict[str, str]] = {}
        if create:
            self._objects_root.mkdir(parents=True, exist_ok=True)
            if not self._manifest_path.is_file():
                self._persist_manifest()
        self._load_manifest()

    @classmethod
    def reopen(
        cls,
        root: str | Path,
        *,
        configuration: Optional[Mapping[str, Any]] = None,
    ) -> "LiveLocalFilesystemAdapter":
        """Reconstruct the store from durable disk state after process loss."""

        adapter = cls(root, configuration=configuration, create=False)
        if not adapter._objects_root.is_dir() or not adapter._manifest_path.is_file():
            cls._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                "local durable store is missing on reopen",
                state=OperationState.UNAVAILABLE,
            )
        return adapter

    @property
    def effect_count(self) -> int:
        return self._effect_count

    @property
    def closed(self) -> bool:
        return self._closed

    @classmethod
    def validate_configuration(cls, configuration: Mapping[str, Any]) -> bool:
        if not isinstance(configuration, Mapping):
            cls._raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "configuration must be a mapping",
                state=OperationState.REJECTED,
            )
        cls._reject_secret_keys(configuration)
        return True

    @classmethod
    def _reject_secret_keys(cls, value: Any) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                normalized = str(key).casefold().replace("-", "_")
                if any(part in normalized for part in _SECRET_KEY_FRAGMENTS):
                    cls._raise(
                        ErrorCode.SECRET_MATERIAL,
                        ErrorCategory.AUTHORIZATION,
                        "secret-bearing configuration is forbidden",
                        state=OperationState.REJECTED,
                    )
                cls._reject_secret_keys(nested)
        elif isinstance(value, (list, tuple, set, frozenset)):
            for nested in value:
                cls._reject_secret_keys(nested)

    @staticmethod
    def _raise(
        code: ErrorCode,
        category: ErrorCategory,
        message: str,
        *,
        state: OperationState = OperationState.FAILED,
        retryability: Retryability = Retryability.NEVER,
    ) -> None:
        raise LiveLocalBackendError(
            StorageError(
                code=code,
                category=category,
                message=message,
                retryability=retryability,
                state=state,
            )
        )

    @staticmethod
    def content_cid(data: bytes) -> str:
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        multihash = b"\x01\x55\x12\x20" + hashlib.sha256(data).digest()
        return "b" + base64.b32encode(multihash).decode("ascii").rstrip("=").lower()

    def _logical_path(self, path: str) -> str:
        if not isinstance(path, str) or "\x00" in path or "\\" in path:
            self._raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "path is invalid",
                state=OperationState.REJECTED,
            )
        if not path:
            self._raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "path is required",
                state=OperationState.REJECTED,
            )
        pure = PurePosixPath(path)
        if pure.is_absolute() or any(part in {".", ".."} for part in pure.parts):
            self._raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "path escapes the local durable root",
                state=OperationState.REJECTED,
            )
        normalized = pure.as_posix()
        if normalized in {"", "."}:
            self._raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "path is required",
                state=OperationState.REJECTED,
            )
        return normalized

    def _target(self, logical_path: str) -> Path:
        target = self._objects_root.joinpath(*logical_path.split("/"))
        if not target.resolve().is_relative_to(self._objects_root.resolve()):
            self._raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "path escapes the local durable root",
                state=OperationState.REJECTED,
            )
        return target

    def _sidecar(self, target: Path) -> Path:
        return target.with_name(target.name + ".cid")

    def _check_open(self, *, deadline: float | None = None, cancel_event: Any = None) -> None:
        if self._closed:
            self._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                "adapter is closed",
                state=OperationState.UNAVAILABLE,
            )
        if cancel_event is not None and bool(cancel_event.is_set()):
            self._raise(
                ErrorCode.CANCELLED,
                ErrorCategory.CANCELLATION,
                "operation was cancelled",
                state=OperationState.CANCELLED,
            )
        if deadline is not None and time.monotonic() > deadline:
            self._raise(
                ErrorCode.DEADLINE_EXCEEDED,
                ErrorCategory.TIMEOUT,
                "operation deadline exceeded",
                state=OperationState.DEADLINE_EXCEEDED,
            )

    def _atomic_write_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _persist_manifest(self) -> None:
        payload = {
            "schema": MANIFEST_SCHEMA,
            "backend_id": self.backend_id,
            "effect_count": self._effect_count,
            "metadata": self._metadata,
            "idempotency": self._idempotency,
            "live_provider": True,
            "hermetic": False,
            "simulated": False,
            "production_authorized": False,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self._atomic_write_bytes(self._manifest_path, encoded)

    def _load_manifest(self) -> None:
        if not self._manifest_path.is_file():
            return
        payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            self._raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                "manifest is not an object",
            )
        self._effect_count = int(payload.get("effect_count", 0))
        metadata = payload.get("metadata") or {}
        idempotency = payload.get("idempotency") or {}
        if not isinstance(metadata, dict) or not isinstance(idempotency, dict):
            self._raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                "manifest maps are invalid",
            )
        self._metadata = {
            str(key): dict(value) for key, value in metadata.items() if isinstance(value, dict)
        }
        self._idempotency = {
            str(key): {str(k): str(v) for k, v in value.items()}
            for key, value in idempotency.items()
            if isinstance(value, dict)
        }

    def _read_verified(self, logical_path: str) -> tuple[bytes, str]:
        target = self._target(logical_path)
        sidecar = self._sidecar(target)
        if not target.is_file() or not sidecar.is_file():
            self._raise(
                ErrorCode.NOT_FOUND,
                ErrorCategory.NOT_FOUND,
                "content does not exist",
                state=OperationState.FAILED,
            )
        data = target.read_bytes()
        expected = sidecar.read_text(encoding="ascii").strip()
        actual = self.content_cid(data)
        if expected != actual:
            self._raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                "content integrity check failed",
                state=OperationState.FAILED,
            )
        return data, actual

    def _idempotency_signature(
        self,
        operation: str,
        path: str,
        data: bytes = b"",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> str:
        encoded = json.dumps(
            {
                "operation": operation,
                "path": path,
                "data": base64.b64encode(data).decode("ascii"),
                "metadata": dict(metadata or {}),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _success(
        self,
        operation: str,
        *,
        content_cid: str = "",
        data: bytes = b"",
        items: tuple[str, ...] = (),
        metadata: Optional[Mapping[str, Any]] = None,
        effect_kind: Optional[EffectKind] = None,
        idempotency_key: str = "",
    ) -> LiveLocalResult:
        evidence: tuple[EffectEvidence, ...] = ()
        durability = None
        state = OperationState.ACCEPTED
        if effect_kind is not None:
            effect_id = f"effect-{uuid.uuid4().hex}"
            acknowledgement = f"ack-{uuid.uuid4().hex}"
            evidence = (
                EffectEvidence(
                    evidence_id=effect_id,
                    kind=EvidenceKind.BACKEND_ACK,
                    effect_kind=effect_kind,
                    reference=acknowledgement,
                    backend_id=self.backend_id,
                ),
            )
            durability = DurabilityEvidence(
                mode=DurabilityMode.BACKEND_DURABLE,
                backend_ack_id=acknowledgement,
                effect_evidence_ids=(effect_id,),
            )
            state = OperationState.COMMITTED
        canonical = OperationResult(
            request_id=f"request-{uuid.uuid4().hex}",
            operation_id=f"operation-{uuid.uuid4().hex}",
            state=state,
            success=True,
            resulting_content_cid=content_cid,
            durability=durability,
            effect_evidence=evidence,
            backend_id=self.backend_id,
            idempotency_key=idempotency_key,
        )
        return LiveLocalResult(
            operation=operation,
            canonical_result=canonical,
            data=data,
            items=items,
            metadata=dict(metadata or {}),
            observed_effect_count=self._effect_count,
        )

    def health(
        self, *, deadline: float | None = None, cancel_event: Any = None
    ) -> LiveLocalResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            return self._success(
                "health",
                metadata={
                    "hermetic": False,
                    "live_provider": True,
                    "provider_certified": False,
                    "production_authorized": False,
                    "simulated": False,
                    "root": str(self.root),
                    "certification_scope": self.certification_scope,
                },
            )

    def put(
        self,
        path: str,
        data: bytes,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
        idempotency_key: str = "",
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> LiveLocalResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            logical_path = self._logical_path(path)
            if not isinstance(data, bytes):
                self._raise(
                    ErrorCode.INVALID_REQUEST,
                    ErrorCategory.VALIDATION,
                    "data must be bytes",
                    state=OperationState.REJECTED,
                )
            if metadata is not None and not isinstance(metadata, Mapping):
                self._raise(
                    ErrorCode.INVALID_REQUEST,
                    ErrorCategory.VALIDATION,
                    "metadata must be a mapping",
                    state=OperationState.REJECTED,
                )
            self._reject_secret_keys(metadata or {})
            signature = self._idempotency_signature("put", logical_path, data, metadata)
            if idempotency_key:
                cached = self._idempotency.get(idempotency_key)
                if cached is not None:
                    if cached.get("signature") != signature:
                        self._raise(
                            ErrorCode.CONFLICT,
                            ErrorCategory.CONFLICT,
                            "idempotency key was reused with different input",
                            state=OperationState.CONFLICT,
                        )
                    return self._success(
                        "put",
                        content_cid=cached["cid"],
                        metadata=self._metadata.get(logical_path, {}),
                        idempotency_key=idempotency_key,
                    )
            target = self._target(logical_path)
            content_cid = self.content_cid(data)
            self._atomic_write_bytes(target, data)
            self._atomic_write_bytes(self._sidecar(target), content_cid.encode("ascii"))
            self._metadata[logical_path] = dict(metadata or {})
            self._effect_count += 1
            if idempotency_key:
                self._idempotency[idempotency_key] = {
                    "signature": signature,
                    "cid": content_cid,
                    "operation": "put",
                    "path": logical_path,
                }
            self._persist_manifest()
            return self._success(
                "put",
                content_cid=content_cid,
                metadata=self._metadata[logical_path],
                effect_kind=EffectKind.BACKEND_WRITE,
                idempotency_key=idempotency_key,
            )

    def get(
        self,
        path: str,
        *,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> LiveLocalResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            logical_path = self._logical_path(path)
            data, content_cid = self._read_verified(logical_path)
            metadata = {"size": len(data), **self._metadata.get(logical_path, {})}
            return self._success(
                "get", content_cid=content_cid, data=data, metadata=metadata
            )

    def digest(
        self,
        path: str,
        *,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> LiveLocalResult:
        result = self.get(path, deadline=deadline, cancel_event=cancel_event)
        recomputed = self.content_cid(result.data)
        if recomputed != result.resulting_content_cid:
            self._raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                "digest mismatch",
                state=OperationState.FAILED,
            )
        return self._success(
            "digest",
            content_cid=recomputed,
            data=result.data,
            metadata={"algorithm": "cidv1-raw-sha2-256", "size": len(result.data)},
        )

    def delete(
        self,
        path: str,
        *,
        idempotency_key: str = "",
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> LiveLocalResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            logical_path = self._logical_path(path)
            signature = self._idempotency_signature("delete", logical_path)
            if idempotency_key:
                cached = self._idempotency.get(idempotency_key)
                if cached is not None:
                    if cached.get("signature") != signature:
                        self._raise(
                            ErrorCode.CONFLICT,
                            ErrorCategory.CONFLICT,
                            "idempotency key was reused with different input",
                            state=OperationState.CONFLICT,
                        )
                    return self._success(
                        "delete",
                        content_cid=cached.get("cid", ""),
                        idempotency_key=idempotency_key,
                    )
            target = self._target(logical_path)
            sidecar = self._sidecar(target)
            if not target.is_file():
                self._raise(
                    ErrorCode.NOT_FOUND,
                    ErrorCategory.NOT_FOUND,
                    "content does not exist",
                    state=OperationState.FAILED,
                )
            data, content_cid = self._read_verified(logical_path)
            del data
            target.unlink()
            if sidecar.exists():
                sidecar.unlink()
            self._metadata.pop(logical_path, None)
            self._effect_count += 1
            if idempotency_key:
                self._idempotency[idempotency_key] = {
                    "signature": signature,
                    "cid": content_cid,
                    "operation": "delete",
                    "path": logical_path,
                }
            self._persist_manifest()
            return self._success(
                "delete",
                content_cid=content_cid,
                effect_kind=EffectKind.BACKEND_DELETE,
                idempotency_key=idempotency_key,
            )

    def close(self) -> LiveLocalResult:
        with self._lock:
            self._closed = True
            self._persist_manifest()
            return self._success("close", metadata={"closed": True})

    def corrupt_for_test(self, path: str, data: bytes) -> None:
        """Overwrite object bytes without updating the CID sidecar."""

        with self._lock:
            logical_path = self._logical_path(path)
            target = self._target(logical_path)
            if not target.is_file() or not isinstance(data, bytes):
                self._raise(
                    ErrorCode.INVALID_REQUEST,
                    ErrorCategory.VALIDATION,
                    "invalid integrity fixture request",
                    state=OperationState.REJECTED,
                )
            target.write_bytes(data)


__all__ = [
    "SCHEMA",
    "INTERFACE",
    "MANIFEST_SCHEMA",
    "BACKEND_ID",
    "CERTIFICATION_SCOPE",
    "LARGE_OBJECT_BYTES",
    "LiveLocalBackendError",
    "LiveLocalResult",
    "LiveLocalFilesystemAdapter",
]
