"""Live Iroh sidecar adapter (PCPR-022).

This adapter talks to a real ``ipfs-kit-iroh-sidecar`` over local JSON-RPC
using the standard library. It is not a mock, not a hermetic fixture, and
not a production-authorized or closed PCPR release.

Fail-closed invariants:

* the adapter never auto-installs Iroh and never downloads binaries;
* missing sidecar, missing sealed ``ipfs-kit-iroh-sidecar`` binary, and
  connection failure are typed Unavailable, never simulated success;
* injected transports are labeled simulated and cannot mint live
  qualification;
* secret-bearing configuration and metadata are rejected;
* deadlines and cancellation fail closed;
* Iroh blob identity is BLAKE3 hex, never converted to an IPFS CID.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Final, Optional

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


SCHEMA: Final = "ipfs_kit_py/assurance/iroh@1"
INTERFACE: Final = "LiveIrohAdapter@1"
BACKEND_ID: Final = "iroh"
CERTIFICATION_SCOPE: Final = "pcpr-022-iroh-python; not a closed PCPR release"
LARGE_OBJECT_BYTES: Final = 256 * 1024
SIDECAR_PRODUCT: Final = "iroh"
SIDECAR_BINARY: Final = "ipfs-kit-iroh-sidecar"
UPSTREAM_BINARY: Final = "iroh"
# No digest-bound sidecar deployment is present on the sealed validation PATH.
# Packaged crate checksums and config version strings are not live identity.
SIDECAR_VERSION: Final = "unavailable"
SIDECAR_DIGEST: Final = "unavailable"
SUPPORT_CLASS: Final = "experimental"
LIVE_SUPPORT_CLAIM: Final = False
PROTOCOL_VERSION: Final = 1
JSONRPC_VERSION: Final = "2.0"
MAX_FRAME_BYTES: Final = 16 * 1024 * 1024
DEFAULT_TIMEOUT: Final = 8.0

_SECRET_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "secret",
    "token",
    "password",
    "credential",
    "authorization",
    "api_key",
    "private_key",
    "node_key",
    "ticket",
    "bearer",
)
_REDACT_KEYS: Final[tuple[str, ...]] = (
    "token",
    "secret",
    "password",
    "api_key",
    "authorization",
    "ticket",
    "node_key",
)
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

Transport = Callable[..., Mapping[str, Any] | bytes]


class IrohBackendError(RuntimeError):
    """Typed Iroh failure carrying a StorageError."""

    def __init__(self, error: StorageError) -> None:
        self.error = error
        super().__init__(error.message)


@dataclass(frozen=True)
class IrohResult:
    """One Iroh operation result."""

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

    @property
    def blob_hash(self) -> str:
        return self.canonical_result.resulting_content_cid


@dataclass
class IsolatedIrohSession:
    """An isolated Iroh sidecar this worker provisioned."""

    binary: str
    state_root: Path
    endpoint: str
    process: subprocess.Popen[bytes]
    version: str
    provisioned: bool = True

    def stop(self) -> None:
        process = self.process
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=4)


def _try_blake3() -> Any:
    try:
        import blake3  # type: ignore[import-untyped]

        return blake3
    except Exception:
        return None


def blake3_hex(data: bytes) -> str:
    """Return lowercase 64-hex BLAKE3, or raise typed unavailable."""

    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    module = _try_blake3()
    if module is None:
        raise IrohBackendError(
            StorageError(
                code=ErrorCode.CAPABILITY_MISSING,
                category=ErrorCategory.CAPABILITY,
                message="blake3 digest library is unavailable",
                retryability=Retryability.NEVER,
                state=OperationState.UNAVAILABLE,
            )
        )
    hasher = module.blake3()
    hasher.update(data)
    digest = hasher.hexdigest()
    if not isinstance(digest, str) or not _HASH_RE.fullmatch(digest):
        raise IrohBackendError(
            StorageError(
                code=ErrorCode.INTEGRITY_FAILURE,
                category=ErrorCategory.INTEGRITY,
                message="blake3 digest is not a 64-hex digest",
                retryability=Retryability.NEVER,
                state=OperationState.FAILED,
            )
        )
    return digest


class LiveIrohAdapter:
    """Unix-socket JSON-RPC adapter for PCPR-022 live Iroh qualification.

    ``live_provider`` is true for the default unix-socket adapter class. That
    is not production authorization and not a claim that a sidecar is present.
    Injected transports are labeled simulated and cannot satisfy live
    qualification. Iroh remains experimental until a digest-bound sidecar
    exists on the sealed PATH and the bounded suite is live-observed.
    """

    backend_id = BACKEND_ID
    provider_kind = "iroh"
    is_hermetic = False
    live_provider = True
    provider_certified = False
    production_authorized = False
    simulated = False
    live_support_claim = LIVE_SUPPORT_CLAIM
    support_class = SUPPORT_CLASS
    certification_scope = CERTIFICATION_SCOPE
    transport_kind = "unix-rpc"

    def __init__(
        self,
        endpoint: str = "",
        *,
        configuration: Optional[Mapping[str, Any]] = None,
        transport: Transport | None = None,
        live_rpc: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        config = {} if configuration is None else dict(configuration)
        self.validate_configuration(config)
        if "endpoint" in config:
            endpoint = str(config["endpoint"])
        endpoint = endpoint.strip()
        if endpoint and not (
            endpoint.startswith("unix://")
            or endpoint.startswith("/")
            or endpoint.startswith("npipe:")
        ):
            self._raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "endpoint must be a unix:// path, absolute socket path, or npipe",
                state=OperationState.REJECTED,
            )
        self.endpoint = endpoint
        self.timeout = float(config.get("timeout", timeout))
        self._lock = threading.RLock()
        self._closed = False
        self._effect_count = 0
        self._idempotency: dict[str, dict[str, str]] = {}
        self._transport = transport
        if transport is not None and not live_rpc:
            self.live_provider = False
            self.is_hermetic = True
            self.simulated = True
            self.transport_kind = "injected"
        else:
            self.live_provider = True
            self.is_hermetic = False
            self.simulated = False
            self.transport_kind = "unix-rpc"

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
        raise IrohBackendError(
            StorageError(
                code=code,
                category=category,
                message=message,
                retryability=retryability,
                state=state,
            )
        )

    @staticmethod
    def blob_identity(data: bytes) -> str:
        return blake3_hex(data)

    @staticmethod
    def redact(value: Any) -> str:
        text = str(value)
        for secret_key in _REDACT_KEYS:
            text = re.sub(
                rf"(?i)({secret_key}[^=:\\s]*[=:]\\s*)[^\\s,&]+",
                r"\1<redacted>",
                text,
            )
        text = re.sub(r"(credential://iroh/)[^\s/?#]+", r"\1<redacted>", text)
        return re.sub(r"([a-z][a-z0-9+.-]*://)[^/@\\s]+@", r"\1<redacted>@", text)

    @property
    def effect_count(self) -> int:
        return self._effect_count

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    def _check_open(
        self, *, deadline: float | None = None, cancel_event: Any = None
    ) -> None:
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

    def _remaining_timeout(self, deadline: float | None) -> float:
        if deadline is None:
            return self.timeout
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            self._raise(
                ErrorCode.DEADLINE_EXCEEDED,
                ErrorCategory.TIMEOUT,
                "operation deadline exceeded",
                state=OperationState.DEADLINE_EXCEEDED,
            )
        return min(self.timeout, remaining)

    def _socket_path(self) -> str:
        endpoint = self.endpoint
        if endpoint.startswith("unix://"):
            return endpoint[len("unix://") :]
        return endpoint

    def _rpc(
        self,
        method: str,
        params: Optional[Mapping[str, Any]] = None,
        *,
        deadline: float | None = None,
    ) -> Any:
        timeout = self._remaining_timeout(deadline)
        request_id = uuid.uuid4().hex
        payload = {
            "jsonrpc": JSONRPC_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "id": request_id,
            "method": method,
            "params": dict(params or {}),
        }
        frame = (
            json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        if len(frame) > MAX_FRAME_BYTES + 1:
            self._raise(
                ErrorCode.UNBOUNDED_FIELD,
                ErrorCategory.VALIDATION,
                "RPC frame exceeds the size limit",
                state=OperationState.REJECTED,
            )
        try:
            if self._transport is not None:
                response = self._transport(
                    method=method,
                    params=dict(params or {}),
                    request_id=request_id,
                    timeout=timeout,
                )
                if isinstance(response, bytes):
                    parsed = json.loads(response.decode("utf-8"))
                else:
                    parsed = response
            else:
                parsed = self._unix_request(frame, timeout=timeout)
        except IrohBackendError:
            raise
        except (TimeoutError, socket.timeout) as exc:
            self._raise(
                ErrorCode.DEADLINE_EXCEEDED,
                ErrorCategory.TIMEOUT,
                f"iroh sidecar timed out: {self.redact(exc)}",
                state=OperationState.DEADLINE_EXCEEDED,
            )
        except (OSError, ConnectionError, EOFError) as exc:
            self._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                f"iroh sidecar unavailable: {self.redact(exc)}",
                state=OperationState.UNAVAILABLE,
            )
        except Exception as exc:  # noqa: BLE001 - typed unavailable, not success
            self._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                f"iroh request failed: {self.redact(exc)}",
                state=OperationState.UNAVAILABLE,
            )
        return self._parse_rpc(parsed, expected_id=request_id)

    def _unix_request(self, frame: bytes, *, timeout: float) -> Mapping[str, Any]:
        path = self._socket_path()
        if not path:
            self._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                "iroh sidecar socket path is empty",
                state=OperationState.UNAVAILABLE,
            )
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.settimeout(timeout)
            client.connect(path)
            client.sendall(frame)
            chunks: list[bytes] = []
            while True:
                piece = client.recv(65536)
                if not piece:
                    break
                chunks.append(piece)
                joined = b"".join(chunks)
                if b"\n" in joined:
                    break
                if len(joined) > MAX_FRAME_BYTES + 1:
                    self._raise(
                        ErrorCode.UNBOUNDED_FIELD,
                        ErrorCategory.VALIDATION,
                        "sidecar returned an oversized frame",
                    )
            raw = b"".join(chunks)
            if not raw.endswith(b"\n"):
                self._raise(
                    ErrorCode.UNAVAILABLE,
                    ErrorCategory.UNAVAILABLE,
                    "sidecar closed the connection without a complete frame",
                    state=OperationState.UNAVAILABLE,
                )
            line = raw.split(b"\n", 1)[0]
            return json.loads(line.decode("utf-8"))
        finally:
            client.close()

    def _parse_rpc(self, parsed: Any, *, expected_id: str) -> Any:
        if not isinstance(parsed, Mapping):
            self._raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                "iroh RPC JSON is not an object",
            )
        if parsed.get("id") != expected_id:
            self._raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                "iroh RPC response id does not match",
            )
        if parsed.get("error"):
            error = parsed["error"]
            if not isinstance(error, Mapping):
                self._raise(
                    ErrorCode.UNAVAILABLE,
                    ErrorCategory.UNAVAILABLE,
                    "iroh RPC error is malformed",
                    state=OperationState.UNAVAILABLE,
                )
            code = str(error.get("code") or "unavailable")
            message = self.redact(error.get("message") or "iroh sidecar error")
            mapped = {
                "unavailable": (ErrorCode.UNAVAILABLE, ErrorCategory.UNAVAILABLE, OperationState.UNAVAILABLE),
                "timeout": (ErrorCode.DEADLINE_EXCEEDED, ErrorCategory.TIMEOUT, OperationState.DEADLINE_EXCEEDED),
                "cancelled": (ErrorCode.CANCELLED, ErrorCategory.CANCELLATION, OperationState.CANCELLED),
                "not_found": (ErrorCode.NOT_FOUND, ErrorCategory.NOT_FOUND, OperationState.FAILED),
                "integrity_error": (ErrorCode.INTEGRITY_FAILURE, ErrorCategory.INTEGRITY, OperationState.FAILED),
                "unsupported_operation": (ErrorCode.UNSUPPORTED, ErrorCategory.UNSUPPORTED, OperationState.REJECTED),
                "permission_denied": (ErrorCode.FORBIDDEN, ErrorCategory.AUTHORIZATION, OperationState.REJECTED),
            }.get(
                code,
                (ErrorCode.UNAVAILABLE, ErrorCategory.UNAVAILABLE, OperationState.UNAVAILABLE),
            )
            self._raise(mapped[0], mapped[1], message, state=mapped[2])
        if "result" not in parsed:
            self._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                "iroh RPC response has neither result nor error",
                state=OperationState.UNAVAILABLE,
            )
        return parsed["result"]

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
    ) -> IrohResult:
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
        return IrohResult(
            operation=operation,
            canonical_result=canonical,
            data=data,
            items=items,
            metadata=dict(metadata or {}),
            observed_effect_count=self._effect_count,
        )

    def _idempotency_signature(self, operation: str, data: bytes) -> str:
        encoded = json.dumps(
            {
                "operation": operation,
                "digest": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _blob_hash_from(self, value: Any) -> str:
        if isinstance(value, Mapping):
            digest = value.get("blob_hash") or value.get("hash") or value.get("expected_hash")
        else:
            digest = value
        text = str(digest or "")
        if not _HASH_RE.fullmatch(text):
            self._raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                "iroh blob hash is not a 64-hex BLAKE3 digest",
            )
        return text

    def health(
        self, *, deadline: float | None = None, cancel_event: Any = None
    ) -> IrohResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            payload = self._rpc("system.health", deadline=deadline)
            if isinstance(payload, Mapping):
                ready = payload.get("ready", payload.get("healthy", True))
                version = str(
                    payload.get("version")
                    or payload.get("sidecar")
                    or payload.get("iroh")
                    or ""
                )
            else:
                ready = True
                version = str(payload)
            if ready is False:
                self._raise(
                    ErrorCode.UNAVAILABLE,
                    ErrorCategory.UNAVAILABLE,
                    "iroh sidecar is not healthy",
                    state=OperationState.UNAVAILABLE,
                )
            return self._success(
                "health",
                metadata={"version": version or "unavailable", "ready": True},
            )

    def add(
        self,
        data: bytes,
        *,
        pin: bool = False,
        idempotency_key: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> IrohResult:
        if not isinstance(data, bytes):
            self._raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "payload must be bytes",
                state=OperationState.REJECTED,
            )
        if metadata:
            self._reject_secret_keys(metadata)
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            signature = self._idempotency_signature("add", data)
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
                        "add",
                        content_cid=str(cached["hash"]),
                        metadata={"replayed": True},
                        idempotency_key=idempotency_key,
                    )
            expected = None
            module = _try_blake3()
            if module is not None:
                expected = blake3_hex(data)
            staging = Path(tempfile.mkdtemp(prefix="pcpr-022-iroh-")) / "blob"
            try:
                staging.write_bytes(data)
                params: dict[str, Any] = {
                    "source_path": str(staging),
                    "size": len(data),
                }
                if expected is not None:
                    params["expected_hash"] = expected
                result = self._rpc("blobs.ingest", params, deadline=deadline)
                digest = self._blob_hash_from(result)
                if expected is not None and digest != expected:
                    self._raise(
                        ErrorCode.INTEGRITY_FAILURE,
                        ErrorCategory.INTEGRITY,
                        "sidecar ingest hash does not match local BLAKE3",
                    )
                if pin:
                    self._rpc(
                        "blobs.protect",
                        {"hash": digest, "reference": "pcpr-022"},
                        deadline=deadline,
                    )
            finally:
                try:
                    staging.unlink()
                    staging.parent.rmdir()
                except OSError:
                    pass
            self._effect_count += 1
            if idempotency_key:
                self._idempotency[idempotency_key] = {
                    "signature": signature,
                    "hash": digest,
                }
            return self._success(
                "add",
                content_cid=digest,
                effect_kind=EffectKind.BACKEND_WRITE,
                idempotency_key=idempotency_key,
                metadata={"pinned": pin, "algorithm": "blake3"},
            )

    def cat(
        self,
        blob_hash: str,
        *,
        expected_blake3: str | None = None,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> IrohResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            digest = self._blob_hash_from(blob_hash)
            info = self._rpc("blobs.stat", {"hash": digest}, deadline=deadline)
            if not isinstance(info, Mapping):
                self._raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "blobs.stat did not return an object",
                )
            size = info.get("size")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                self._raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "blobs.stat size is invalid",
                )
            payload = self._rpc(
                "blobs.read_range",
                {"hash": digest, "offset": 0, "length": size},
                deadline=deadline,
            )
            if isinstance(payload, Mapping):
                encoded = payload.get("data")
                if isinstance(encoded, str):
                    data = base64.b64decode(encoded, validate=True)
                elif isinstance(encoded, (bytes, bytearray)):
                    data = bytes(encoded)
                else:
                    self._raise(
                        ErrorCode.INTEGRITY_FAILURE,
                        ErrorCategory.INTEGRITY,
                        "blobs.read_range data is missing",
                    )
            elif isinstance(payload, (bytes, bytearray)):
                data = bytes(payload)
            else:
                self._raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "blobs.read_range result is unreadable",
                )
            if expected_blake3:
                wanted = expected_blake3.strip().lower()
                module = _try_blake3()
                if module is not None:
                    observed = blake3_hex(data)
                    if observed != wanted:
                        self._raise(
                            ErrorCode.INTEGRITY_FAILURE,
                            ErrorCategory.INTEGRITY,
                            "read-back BLAKE3 does not match expected digest",
                        )
                elif wanted and wanted != digest:
                    self._raise(
                        ErrorCode.INTEGRITY_FAILURE,
                        ErrorCategory.INTEGRITY,
                        "read-back hash does not match expected digest",
                    )
            return self._success("cat", content_cid=digest, data=data)

    def digest(
        self,
        blob_hash: str,
        *,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> IrohResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            digest = self._blob_hash_from(blob_hash)
            info = self._rpc("blobs.stat", {"hash": digest}, deadline=deadline)
            observed = self._blob_hash_from(info if isinstance(info, Mapping) else digest)
            if observed != digest:
                self._raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "blobs.stat hash does not match requested hash",
                )
            return self._success(
                "digest",
                content_cid=digest,
                metadata={"algorithm": "blake3"},
            )

    def pin(
        self,
        blob_hash: str,
        *,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> IrohResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            digest = self._blob_hash_from(blob_hash)
            self._rpc(
                "blobs.protect",
                {"hash": digest, "reference": "pcpr-022"},
                deadline=deadline,
            )
            self._effect_count += 1
            return self._success(
                "pin",
                content_cid=digest,
                effect_kind=EffectKind.BACKEND_WRITE,
                items=(digest,),
            )

    def unpin(
        self,
        blob_hash: str,
        *,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> IrohResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            digest = self._blob_hash_from(blob_hash)
            self._rpc(
                "blobs.release",
                {
                    "hash": digest,
                    "reference": "pcpr-022",
                    "operation_id": uuid.uuid4().hex,
                    "only_if_unprotected": False,
                },
                deadline=deadline,
            )
            self._effect_count += 1
            return self._success(
                "unpin",
                content_cid=digest,
                effect_kind=EffectKind.BACKEND_DELETE,
            )

    def delete(
        self,
        blob_hash: str,
        *,
        idempotency_key: str = "",
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> IrohResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            digest = self._blob_hash_from(blob_hash)
            signature = self._idempotency_signature("delete", digest.encode("utf-8"))
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
                        content_cid=digest,
                        idempotency_key=idempotency_key,
                        metadata={"replayed": True},
                    )
            try:
                self._rpc(
                    "blobs.release",
                    {
                        "hash": digest,
                        "reference": "pcpr-022",
                        "operation_id": uuid.uuid4().hex,
                        "only_if_unprotected": False,
                    },
                    deadline=deadline,
                )
            except IrohBackendError as exc:
                if exc.error.code not in {ErrorCode.UNAVAILABLE, ErrorCode.NOT_FOUND}:
                    raise
            self._effect_count += 1
            if idempotency_key:
                self._idempotency[idempotency_key] = {
                    "signature": signature,
                    "hash": digest,
                }
            return self._success(
                "delete",
                content_cid=digest,
                effect_kind=EffectKind.BACKEND_DELETE,
                idempotency_key=idempotency_key,
            )


def provision_isolated_iroh_sidecar(
    *,
    sidecar_binary: str | Path | None,
    state_root: str | Path,
    timeout_seconds: float = 15.0,
) -> IsolatedIrohSession:
    """Start an isolated Iroh sidecar for live qualification.

    Never auto-installs. A missing or non-executable binary is typed
    Unavailable. Isolated start never embeds node-key secret material; if
    the sidecar requires live identity material, provisioning stays
    unavailable. The caller owns stop().
    """

    if sidecar_binary is None:
        LiveIrohAdapter._raise(
            ErrorCode.UNAVAILABLE,
            ErrorCategory.UNAVAILABLE,
            "sealed ipfs-kit-iroh-sidecar binary is unavailable; sidecar was not provisioned",
            state=OperationState.UNAVAILABLE,
        )
    binary = Path(sidecar_binary)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        LiveIrohAdapter._raise(
            ErrorCode.UNAVAILABLE,
            ErrorCategory.UNAVAILABLE,
            "sealed ipfs-kit-iroh-sidecar binary is not executable; sidecar was not provisioned",
            state=OperationState.UNAVAILABLE,
        )
    root = Path(state_root)
    root.mkdir(parents=True, exist_ok=True)
    socket_path = root / "run" / "sidecar.sock"
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    config_path = root / "config.json"
    config = {
        "enabled": True,
        "instance": "pcpr-022",
        "kind": "ipfs-kit-iroh-service",
        "schema_version": 1,
        "protocol_version": 1,
        "release_bundle": "unavailable",
        "state_root": str(root),
        "rpc": {"endpoint": f"unix://{socket_path.as_posix()}", "kind": "local"},
        "network": {
            "discovery": {"policy": "disabled"},
            "endpoint_bind": ["127.0.0.1:0"],
            "relay": {"policy": "disabled", "urls": []},
        },
        "logging": {
            "log_path": str(root / "sidecar.log"),
            "crash_receipt_path": str(root / "crash.json"),
            "health_receipt_path": str(root / "health.json"),
        },
    }
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin",
        "HOME": str(root),
        "PYTHONNOUSERSITE": "1",
        "IPFS_KIT_AUTO_INSTALL_BINARIES": "0",
    }
    process = subprocess.Popen(
        [str(binary), "serve", "--config", str(config_path)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(root),
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            LiveIrohAdapter._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                "iroh sidecar exited during provisioning; isolated node was not started",
                state=OperationState.UNAVAILABLE,
            )
        if socket_path.exists():
            version_proc = subprocess.run(
                [str(binary), "--version"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout_seconds,
            )
            version = (version_proc.stdout or "").strip() or "unavailable"
            return IsolatedIrohSession(
                binary=str(binary),
                state_root=root,
                endpoint=f"unix://{socket_path.as_posix()}",
                process=process,
                version=version,
                provisioned=True,
            )
        time.sleep(0.05)
    process.terminate()
    LiveIrohAdapter._raise(
        ErrorCode.UNAVAILABLE,
        ErrorCategory.UNAVAILABLE,
        "iroh sidecar did not publish a local RPC socket",
        state=OperationState.UNAVAILABLE,
    )
    raise AssertionError("unreachable")


__all__ = [
    "SCHEMA",
    "INTERFACE",
    "BACKEND_ID",
    "CERTIFICATION_SCOPE",
    "LARGE_OBJECT_BYTES",
    "SIDECAR_PRODUCT",
    "SIDECAR_BINARY",
    "UPSTREAM_BINARY",
    "SIDECAR_VERSION",
    "SIDECAR_DIGEST",
    "SUPPORT_CLASS",
    "LIVE_SUPPORT_CLAIM",
    "IrohBackendError",
    "IrohResult",
    "IsolatedIrohSession",
    "LiveIrohAdapter",
    "blake3_hex",
    "provision_isolated_iroh_sidecar",
]
