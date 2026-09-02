"""Live pinned IPFS (Kubo) backend adapter (PCPR-021).

This adapter talks to a real Kubo HTTP API using the standard library.
It is not a mock, not a hermetic fixture, and not a production-authorized
or closed PCPR release.

Fail-closed invariants:

* the adapter never auto-installs Kubo and never downloads binaries;
* missing daemon, missing sealed ``ipfs`` binary, and connection failure
  are typed Unavailable, never simulated success;
* injected transports are labeled simulated and cannot mint live
  qualification;
* secret-bearing configuration and metadata are rejected;
* deadlines and cancellation fail closed;
* digest equality uses raw CIDv1 sha2-256 against ``block/put`` +
  ``block/get`` bytes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
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


SCHEMA: Final = "ipfs_kit_py/assurance/pinned-ipfs@1"
INTERFACE: Final = "LivePinnedIpfsAdapter@1"
BACKEND_ID: Final = "pinned_ipfs"
SUPPORT_CLASS: Final = "unavailable"
LIVE_SUPPORT_CLAIM: Final = False
CERTIFICATION_SCOPE: Final = (
    "pcpr-021-pinned-ipfs-python; not a closed PCPR release"
)
LARGE_OBJECT_BYTES: Final = 256 * 1024
DEFAULT_API_URL: Final = "http://127.0.0.1:5001"
PINNED_DAEMON_PRODUCT: Final = "kubo"
PINNED_DAEMON_BINARY: Final = "ipfs"
# No digest-bound Kubo deployment is present in the sealed validation PATH.
# A version string here would be a configuration claim, not live identity.
PINNED_DAEMON_VERSION: Final = "unavailable"
PINNED_DAEMON_DIGEST: Final = "unavailable"
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
_REDACT_KEYS: Final[tuple[str, ...]] = (
    "token",
    "secret",
    "password",
    "api_key",
    "authorization",
)

Transport = Callable[..., tuple[int, bytes]]


class PinnedIpfsBackendError(RuntimeError):
    """Typed pinned-IPFS failure carrying a StorageError."""

    def __init__(self, error: StorageError) -> None:
        self.error = error
        super().__init__(error.message)


@dataclass(frozen=True)
class PinnedIpfsResult:
    """One pinned-IPFS operation result."""

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


@dataclass
class IsolatedDaemonSession:
    """An isolated offline Kubo daemon this worker provisioned."""

    binary: str
    repo: Path
    api_url: str
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


class LivePinnedIpfsAdapter:
    """Kubo HTTP adapter for PCPR-021 live pinned-IPFS qualification.

    ``live_provider`` is true for the default HTTP adapter class. That is
    not production authorization and not a claim that a daemon is present.
    Injected transports are labeled simulated and cannot satisfy live
    qualification.
    """

    backend_id = BACKEND_ID
    provider_kind = "ipfs"
    is_hermetic = False
    live_provider = True
    provider_certified = False
    production_authorized = False
    simulated = False
    certification_scope = CERTIFICATION_SCOPE
    transport_kind = "http"

    def __init__(
        self,
        api_url: str = DEFAULT_API_URL,
        *,
        configuration: Optional[Mapping[str, Any]] = None,
        transport: Transport | None = None,
        live_http: bool = False,
        timeout: float = 8.0,
    ) -> None:
        config = {} if configuration is None else dict(configuration)
        self.validate_configuration(config)
        if "api_url" in config:
            api_url = str(config["api_url"])
        if not isinstance(api_url, str) or not api_url.strip():
            self._raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "api_url must be a non-empty string",
                state=OperationState.REJECTED,
            )
        normalized = api_url.strip().rstrip("/")
        if not normalized.startswith("http://") and not normalized.startswith(
            "https://"
        ):
            self._raise(
                ErrorCode.INVALID_REQUEST,
                ErrorCategory.VALIDATION,
                "api_url must be http or https",
                state=OperationState.REJECTED,
            )
        self.api_url = normalized
        self.timeout = float(config.get("timeout", timeout))
        self._lock = threading.RLock()
        self._closed = False
        self._effect_count = 0
        self._idempotency: dict[str, dict[str, str]] = {}
        self._transport = transport
        if transport is not None and not live_http:
            self.live_provider = False
            self.is_hermetic = True
            self.simulated = True
            self.transport_kind = "injected"
        else:
            self.live_provider = True
            self.is_hermetic = False
            self.simulated = False
            self.transport_kind = "http"

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
        raise PinnedIpfsBackendError(
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
        # CIDv1 + raw (0x55) + sha2-256.
        multihash = b"\x01\x55\x12\x20" + hashlib.sha256(data).digest()
        return "b" + base64.b32encode(multihash).decode("ascii").rstrip("=").lower()

    @staticmethod
    def redact(value: Any) -> str:
        text = str(value)
        for secret_key in _REDACT_KEYS:
            text = re.sub(
                rf"(?i)({secret_key}[^=:\\s]*[=:]\\s*)[^\\s,&]+",
                r"\1<redacted>",
                text,
            )
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

    def _request(
        self,
        path: str,
        *,
        query: Optional[Mapping[str, str]] = None,
        body: bytes = b"",
        content_type: str | None = None,
        deadline: float | None = None,
        expect_json: bool = True,
    ) -> Any:
        timeout = self._remaining_timeout(deadline)
        encoded_query = urllib.parse.urlencode(query or {})
        target = f"{self.api_url}{path}"
        if encoded_query:
            target = f"{target}?{encoded_query}"
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        try:
            if self._transport is not None:
                status, payload = self._transport(
                    method="POST",
                    path=path,
                    query=dict(query or {}),
                    body=body,
                    headers=headers,
                    timeout=timeout,
                )
            else:
                request = urllib.request.Request(
                    target,
                    data=body if body else None,
                    method="POST",
                    headers=headers,
                )
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    status = int(getattr(response, "status", 200) or 200)
                    payload = response.read()
        except PinnedIpfsBackendError:
            raise
        except urllib.error.HTTPError as exc:
            detail = self.redact(exc.read().decode("utf-8", "replace") if exc.fp else exc)
            self._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                f"ipfs API HTTP {exc.code}: {detail}",
                state=OperationState.UNAVAILABLE,
            )
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            self._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                f"ipfs daemon unavailable: {self.redact(exc)}",
                state=OperationState.UNAVAILABLE,
            )
        except Exception as exc:  # noqa: BLE001 - typed unavailable, not success
            self._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                f"ipfs request failed: {self.redact(exc)}",
                state=OperationState.UNAVAILABLE,
            )
        if status >= 400:
            self._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                f"ipfs API HTTP {status}: {self.redact(payload[:200])}",
                state=OperationState.UNAVAILABLE,
            )
        if not expect_json:
            return payload
        if not payload:
            return {}
        try:
            text = payload.decode("utf-8")
            # Kubo may emit NDJSON; take the last object.
            last = [line for line in text.splitlines() if line.strip()][-1]
            parsed = json.loads(last)
        except Exception as exc:  # noqa: BLE001
            self._raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                f"ipfs API returned non-JSON: {self.redact(exc)}",
            )
        if not isinstance(parsed, Mapping):
            self._raise(
                ErrorCode.INTEGRITY_FAILURE,
                ErrorCategory.INTEGRITY,
                "ipfs API JSON is not an object",
            )
        return parsed

    def _multipart(self, data: bytes, field: str = "file") -> tuple[bytes, str]:
        boundary = f"----pcpr021{uuid.uuid4().hex}"
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="payload"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("ascii")
        body = header + data + f"\r\n--{boundary}--\r\n".encode("ascii")
        return body, f"multipart/form-data; boundary={boundary}"

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
    ) -> PinnedIpfsResult:
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
        return PinnedIpfsResult(
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

    def health(
        self, *, deadline: float | None = None, cancel_event: Any = None
    ) -> PinnedIpfsResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            payload = self._request("/api/v0/version", deadline=deadline)
            version = str(payload.get("Version") or payload.get("version") or "")
            if not version:
                self._raise(
                    ErrorCode.UNAVAILABLE,
                    ErrorCategory.UNAVAILABLE,
                    "ipfs daemon version is missing",
                    state=OperationState.UNAVAILABLE,
                )
            return self._success(
                "health",
                metadata={
                    "hermetic": self.is_hermetic,
                    "live_provider": self.live_provider,
                    "provider_certified": False,
                    "production_authorized": False,
                    "simulated": self.simulated,
                    "api_url": self.api_url,
                    "version": version,
                    "product": PINNED_DAEMON_PRODUCT,
                    "certification_scope": self.certification_scope,
                    "transport_kind": self.transport_kind,
                },
            )

    def add(
        self,
        data: bytes,
        *,
        pin: bool = True,
        idempotency_key: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> PinnedIpfsResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            if not isinstance(data, bytes):
                self._raise(
                    ErrorCode.INVALID_REQUEST,
                    ErrorCategory.VALIDATION,
                    "data must be bytes",
                    state=OperationState.REJECTED,
                )
            self._reject_secret_keys(metadata or {})
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
                        content_cid=cached["cid"],
                        data=data,
                        idempotency_key=idempotency_key,
                        metadata={"replayed": True},
                    )
            expected = self.content_cid(data)
            body, content_type = self._multipart(data)
            payload = self._request(
                "/api/v0/block/put",
                query={"cid-codec": "raw", "mhtype": "sha2-256", "pin": "true" if pin else "false"},
                body=body,
                content_type=content_type,
                deadline=deadline,
            )
            cid = str(payload.get("Key") or payload.get("Hash") or payload.get("Cid") or "")
            if not cid:
                self._raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "ipfs block/put returned no CID",
                )
            if cid != expected:
                self._raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "ipfs CID does not equal local raw CIDv1 sha2-256",
                )
            if pin:
                self._request(
                    "/api/v0/pin/add",
                    query={"arg": cid},
                    deadline=deadline,
                )
            self._effect_count += 1
            if idempotency_key:
                self._idempotency[idempotency_key] = {
                    "signature": signature,
                    "cid": cid,
                }
            return self._success(
                "add",
                content_cid=cid,
                data=data,
                effect_kind=EffectKind.BACKEND_WRITE,
                idempotency_key=idempotency_key,
                metadata={"pinned": pin, "bytes": str(len(data))},
            )

    def cat(
        self,
        cid: str,
        *,
        expected_sha256: str | None = None,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> PinnedIpfsResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            if not isinstance(cid, str) or not cid.strip():
                self._raise(
                    ErrorCode.INVALID_REQUEST,
                    ErrorCategory.VALIDATION,
                    "cid must be a non-empty string",
                    state=OperationState.REJECTED,
                )
            payload = self._request(
                "/api/v0/block/get",
                query={"arg": cid.strip()},
                deadline=deadline,
                expect_json=False,
            )
            if not isinstance(payload, bytes):
                self._raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "ipfs block/get did not return bytes",
                )
            actual_cid = self.content_cid(payload)
            if actual_cid != cid.strip():
                self._raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "read-back CID does not match requested CID",
                )
            digest = hashlib.sha256(payload).hexdigest()
            if expected_sha256 and digest != expected_sha256:
                self._raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "read-back SHA-256 does not match expected digest",
                )
            return self._success(
                "cat",
                content_cid=actual_cid,
                data=payload,
                metadata={"sha256": digest},
            )

    def digest(
        self,
        cid: str,
        *,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> PinnedIpfsResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            payload = self._request(
                "/api/v0/block/stat",
                query={"arg": cid},
                deadline=deadline,
            )
            key = str(payload.get("Key") or payload.get("Hash") or cid)
            if key != cid:
                self._raise(
                    ErrorCode.INTEGRITY_FAILURE,
                    ErrorCategory.INTEGRITY,
                    "block/stat CID does not match requested CID",
                )
            return self._success(
                "digest",
                content_cid=key,
                metadata={
                    "algorithm": "cidv1-raw-sha2-256",
                    "size": str(payload.get("Size", "")),
                },
            )

    def pin(
        self,
        cid: str,
        *,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> PinnedIpfsResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            self._request("/api/v0/pin/add", query={"arg": cid}, deadline=deadline)
            listing = self._request(
                "/api/v0/pin/ls", query={"arg": cid, "type": "all"}, deadline=deadline
            )
            keys = listing.get("Keys") or {}
            if cid not in keys:
                self._raise(
                    ErrorCode.DURABILITY_FAILURE,
                    ErrorCategory.DURABILITY,
                    "cid is not present in pin listing after pin/add",
                )
            self._effect_count += 1
            return self._success(
                "pin",
                content_cid=cid,
                effect_kind=EffectKind.BACKEND_WRITE,
                items=(cid,),
            )

    def unpin(
        self,
        cid: str,
        *,
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> PinnedIpfsResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            self._request("/api/v0/pin/rm", query={"arg": cid}, deadline=deadline)
            listing = self._request(
                "/api/v0/pin/ls", query={"type": "all"}, deadline=deadline
            )
            keys = listing.get("Keys") or {}
            if cid in keys:
                self._raise(
                    ErrorCode.DURABILITY_FAILURE,
                    ErrorCategory.DURABILITY,
                    "cid remains pinned after pin/rm",
                )
            self._effect_count += 1
            return self._success(
                "unpin",
                content_cid=cid,
                effect_kind=EffectKind.BACKEND_DELETE,
            )

    def delete(
        self,
        cid: str,
        *,
        idempotency_key: str = "",
        deadline: float | None = None,
        cancel_event: Any = None,
    ) -> PinnedIpfsResult:
        with self._lock:
            self._check_open(deadline=deadline, cancel_event=cancel_event)
            signature = self._idempotency_signature("delete", cid.encode("utf-8"))
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
                        content_cid=cid,
                        idempotency_key=idempotency_key,
                        metadata={"replayed": True},
                    )
            try:
                self._request("/api/v0/pin/rm", query={"arg": cid}, deadline=deadline)
            except PinnedIpfsBackendError as exc:
                if exc.error.code is not ErrorCode.UNAVAILABLE:
                    # Missing pin is delete-safe.
                    if "not pinned" not in str(exc).casefold():
                        raise
            try:
                self._request(
                    "/api/v0/block/rm",
                    query={"arg": cid, "force": "true"},
                    deadline=deadline,
                )
            except PinnedIpfsBackendError:
                # Unpinned absence is acceptable after pin/rm.
                pass
            self._effect_count += 1
            if idempotency_key:
                self._idempotency[idempotency_key] = {
                    "signature": signature,
                    "cid": cid,
                }
            return self._success(
                "delete",
                content_cid=cid,
                effect_kind=EffectKind.BACKEND_DELETE,
                idempotency_key=idempotency_key,
            )


def _parse_api_multiaddr(text: str) -> str:
    match = re.search(r"/ip4/([^/]+)/tcp/(\d+)", text)
    if match is None:
        raise PinnedIpfsBackendError(
            StorageError(
                code=ErrorCode.UNAVAILABLE,
                category=ErrorCategory.UNAVAILABLE,
                message="ipfs api multiaddr is unreadable",
                retryability=Retryability.NEVER,
                state=OperationState.UNAVAILABLE,
            )
        )
    return f"http://{match.group(1)}:{match.group(2)}"


def provision_isolated_pinned_daemon(
    *,
    ipfs_binary: str | Path | None,
    repo: str | Path,
    timeout_seconds: float = 15.0,
) -> IsolatedDaemonSession:
    """Start an isolated offline Kubo daemon for live qualification.

    Never auto-installs. A missing or non-executable binary is typed
    Unavailable. The caller owns stop().
    """

    if ipfs_binary is None:
        LivePinnedIpfsAdapter._raise(
            ErrorCode.UNAVAILABLE,
            ErrorCategory.UNAVAILABLE,
            "sealed ipfs binary is unavailable; daemon was not provisioned",
            state=OperationState.UNAVAILABLE,
        )
    binary = Path(ipfs_binary)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        LivePinnedIpfsAdapter._raise(
            ErrorCode.UNAVAILABLE,
            ErrorCategory.UNAVAILABLE,
            "sealed ipfs binary is not executable; daemon was not provisioned",
            state=OperationState.UNAVAILABLE,
        )
    repo_path = Path(repo)
    repo_path.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin",
        "IPFS_PATH": str(repo_path),
        "HOME": str(repo_path),
        "PYTHONNOUSERSITE": "1",
    }
    init = subprocess.run(
        [str(binary), "init", "--profile=test"],
        check=False,
        capture_output=True,
        env=env,
        timeout=timeout_seconds,
    )
    if init.returncode != 0 and b"already" not in (init.stderr or b"").lower():
        LivePinnedIpfsAdapter._raise(
            ErrorCode.UNAVAILABLE,
            ErrorCategory.UNAVAILABLE,
            "ipfs init failed; isolated daemon was not provisioned",
            state=OperationState.UNAVAILABLE,
        )
    for args in (
        ["config", "Addresses.API", "/ip4/127.0.0.1/tcp/0"],
        ["config", "Addresses.Gateway", "/ip4/127.0.0.1/tcp/0"],
        ["config", "Addresses.Swarm", "--json", "[]"],
    ):
        subprocess.run(
            [str(binary), *args],
            check=False,
            capture_output=True,
            env=env,
            timeout=timeout_seconds,
        )
    process = subprocess.Popen(
        [str(binary), "daemon", "--offline", "--migrate=false"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    api_file = repo_path / "api"
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            LivePinnedIpfsAdapter._raise(
                ErrorCode.UNAVAILABLE,
                ErrorCategory.UNAVAILABLE,
                "ipfs daemon exited during provisioning",
                state=OperationState.UNAVAILABLE,
            )
        if api_file.is_file():
            api_url = _parse_api_multiaddr(api_file.read_text(encoding="utf-8"))
            version_proc = subprocess.run(
                [str(binary), "version", "--offline"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout_seconds,
            )
            version = (version_proc.stdout or "").strip() or "unavailable"
            return IsolatedDaemonSession(
                binary=str(binary),
                repo=repo_path,
                api_url=api_url,
                process=process,
                version=version,
                provisioned=True,
            )
        time.sleep(0.05)
    process.terminate()
    LivePinnedIpfsAdapter._raise(
        ErrorCode.UNAVAILABLE,
        ErrorCategory.UNAVAILABLE,
        "ipfs daemon did not publish an API address",
        state=OperationState.UNAVAILABLE,
    )
    raise AssertionError("unreachable")


__all__ = [
    "SCHEMA",
    "INTERFACE",
    "BACKEND_ID",
    "CERTIFICATION_SCOPE",
    "LARGE_OBJECT_BYTES",
    "PINNED_DAEMON_PRODUCT",
    "PINNED_DAEMON_BINARY",
    "PINNED_DAEMON_VERSION",
    "PINNED_DAEMON_DIGEST",
    "PinnedIpfsBackendError",
    "PinnedIpfsResult",
    "IsolatedDaemonSession",
    "LivePinnedIpfsAdapter",
    "provision_isolated_pinned_daemon",
]
