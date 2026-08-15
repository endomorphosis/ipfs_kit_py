"""Optional injected IPFS transport for public proof-seal artifacts (IPS-020).

This adapter is deliberately optional.  Unit tests and ordinary import never
require a daemon, network, or ``~/.ipfs``.  Callers inject an already-created
client or explicit get/put callables.

Safety properties:

* only closed public artifact kinds may be replicated or fetched;
* proving-key and witness material is rejected at the public boundary;
* every response is bounded by byte budget and wall-clock timeout;
* every successful fetch/replicate rehashes exact bytes against the content
  identity (strict CID or ``sha256:``);
* corrupt, oversized, wrong-kind, and malformed backend responses fail closed;
* backend ambiguity is recorded as a typed disposition and never treated as
  success;
* local committed hermetic-store bytes remain reconcilable after remote faults.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final, Protocol, runtime_checkable

from ipfs_kit_py.proof_seal_store.contracts import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    MAX_ARTIFACT_BYTES_BOUND,
    ArtifactKind,
    ArtifactKindError,
    ArtifactReference,
    ForbiddenArtifactError,
    ProofSealStoreContractError,
    StoreGetDisposition,
    StorePutDisposition,
    coerce_artifact_kind,
    is_forbidden_artifact_kind,
)
from ipfs_kit_py.proof_seal_store.local_store import (
    HermeticProofSealStore,
    LocalGetResult,
    LocalStoreReason,
    content_cid_for_bytes,
    verify_content_identity,
)

EVIDENCE_SUBSET: Final[str] = "ips/ipfs-proof-transport@1"
IPFS_TRANSPORT_SCHEMA: Final[str] = (
    "ipfs_kit_py/proof_seal_store/ipfs-transport@1"
)
IPFS_TRANSPORT_INTERFACE: Final[str] = "IpfsProofArtifactTransport@1"

DEFAULT_TIMEOUT_SECONDS: Final[float] = 30.0
MAX_TIMEOUT_SECONDS: Final[float] = 600.0
MAX_DIAGNOSTIC_ENTRIES: Final[int] = 32
MAX_DIAGNOSTIC_TEXT_BYTES: Final[int] = 512

# Closed public kinds eligible for optional remote replication/retrieval.
PUBLIC_ARTIFACT_KINDS: Final[frozenset[ArtifactKind]] = frozenset(ArtifactKind)


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class TransportDisposition(str, Enum):
    """Closed outcomes for optional IPFS transport operations."""

    OK = "ok"
    HIT = "hit"
    MISS = "miss"
    REJECTED = "rejected"
    ERROR = "error"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


class TransportReason(str, Enum):
    """Closed diagnostic reasons for transport outcomes."""

    OK = "ok"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"
    OVER_BUDGET = "over_budget"
    CID_MISMATCH = "cid_mismatch"
    KIND_MISMATCH = "kind_mismatch"
    NOT_FOUND = "not_found"
    INTEGRITY_FAILED = "integrity_failed"
    CORRUPTED = "corrupted"
    FORBIDDEN_KIND = "forbidden_kind"
    IPFS_ERROR = "ipfs_error"
    IPFS_RESPONSE_INVALID = "ipfs_response_invalid"
    TIMEOUT = "timeout"
    AMBIGUOUS = "ambiguous"
    LOCAL_MISS = "local_miss"
    LOCAL_INTEGRITY_FAILED = "local_integrity_failed"
    LOCAL_STORED = "local_stored"
    ALREADY_EXISTS = "already_exists"
    WRONG_KIND = "wrong_kind"
    BACKEND_AMBIGUOUS = "backend_ambiguous"


class TransportSource(str, Enum):
    """Where verified bytes were obtained."""

    NONE = "none"
    LOCAL = "local"
    IPFS = "ipfs"
    LOCAL_AND_IPFS = "local_and_ipfs"


class IpfsTransportError(ProofSealStoreContractError):
    """A transport operation or configuration violates the closed contract."""

    def __init__(
        self,
        message: str,
        *,
        reason: TransportReason = TransportReason.IPFS_ERROR,
        disposition: TransportDisposition | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.disposition = disposition


class IpfsTransportUnavailableError(IpfsTransportError):
    """No injected IPFS client/callable is available."""

    def __init__(self, message: str = "IPFS transport is unavailable") -> None:
        super().__init__(
            message,
            reason=TransportReason.UNAVAILABLE,
            disposition=TransportDisposition.UNAVAILABLE,
        )


class IpfsTransportAmbiguousError(IpfsTransportError):
    """Backend outcome is ambiguous and must not be treated as success."""

    def __init__(self, message: str = "IPFS backend outcome is ambiguous") -> None:
        super().__init__(
            message,
            reason=TransportReason.BACKEND_AMBIGUOUS,
            disposition=TransportDisposition.AMBIGUOUS,
        )


# ---------------------------------------------------------------------------
# Result records
# ---------------------------------------------------------------------------


def _bounded_diagnostics(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    out: dict[str, Any] = {}
    for index, (key, value) in enumerate(payload.items()):
        if index >= MAX_DIAGNOSTIC_ENTRIES:
            out["_truncated"] = True
            break
        if type(key) is not str or not key or len(key) > 64:
            continue
        if type(value) is bool:
            out[key] = value
        elif type(value) is int:
            out[key] = value
        elif type(value) is float:
            out[key] = value
        elif type(value) is str:
            encoded = value.encode("utf-8", errors="replace")
            if len(encoded) > MAX_DIAGNOSTIC_TEXT_BYTES:
                out[key] = encoded[:MAX_DIAGNOSTIC_TEXT_BYTES].decode(
                    "utf-8", errors="replace"
                ) + "…"
            else:
                out[key] = value
        elif value is None:
            out[key] = None
        else:
            text = repr(value)
            if len(text) > MAX_DIAGNOSTIC_TEXT_BYTES:
                text = text[:MAX_DIAGNOSTIC_TEXT_BYTES] + "…"
            out[key] = text
    return out


@dataclass(frozen=True)
class TransportAmbiguityRecord:
    """Recorded backend ambiguity that must never be treated as success."""

    reason: TransportReason
    message: str
    cid: str = ""
    kind: str = ""
    local_ok: bool | None = None
    remote_ok: bool | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.reason, TransportReason):
            object.__setattr__(self, "reason", TransportReason(self.reason))
        if type(self.message) is not str or not self.message.strip():
            raise IpfsTransportError(
                "ambiguity message must be a non-empty string",
                reason=TransportReason.MALFORMED,
            )
        object.__setattr__(
            self, "diagnostics", _bounded_diagnostics(dict(self.diagnostics))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason.value,
            "message": self.message,
            "cid": self.cid,
            "kind": self.kind,
            "local_ok": self.local_ok,
            "remote_ok": self.remote_ok,
            "diagnostics": dict(self.diagnostics),
        }


@dataclass(frozen=True)
class TransportReplicateResult:
    """Outcome of an optional public-artifact replication attempt."""

    disposition: TransportDisposition
    reason: TransportReason
    reference: ArtifactReference | None = None
    cid: str = ""
    byte_length: int = 0
    local_reconciled: bool = False
    ipfs_stored: bool = False
    ambiguity: TransportAmbiguityRecord | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.succeeded

    @property
    def succeeded(self) -> bool:
        return (
            self.disposition is TransportDisposition.OK
            and self.ipfs_stored
            and self.ambiguity is None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "reason": self.reason.value,
            "reference": (
                self.reference.to_dict() if self.reference is not None else None
            ),
            "cid": self.cid,
            "byte_length": self.byte_length,
            "local_reconciled": self.local_reconciled,
            "ipfs_stored": self.ipfs_stored,
            "ambiguity": (
                self.ambiguity.to_dict() if self.ambiguity is not None else None
            ),
            "diagnostics": dict(self.diagnostics),
        }


@dataclass(frozen=True)
class TransportFetchResult:
    """Outcome of an optional public-artifact fetch attempt."""

    disposition: TransportDisposition
    reason: TransportReason
    data: bytes | None = None
    reference: ArtifactReference | None = None
    cid: str = ""
    byte_length: int = 0
    source: TransportSource = TransportSource.NONE
    local_reconciled: bool = False
    ambiguity: TransportAmbiguityRecord | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.hit

    @property
    def hit(self) -> bool:
        return (
            self.disposition is TransportDisposition.HIT
            and self.data is not None
            and self.ambiguity is None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "reason": self.reason.value,
            "cid": self.cid,
            "byte_length": self.byte_length,
            "source": self.source.value,
            "local_reconciled": self.local_reconciled,
            "has_data": self.data is not None,
            "reference": (
                self.reference.to_dict() if self.reference is not None else None
            ),
            "ambiguity": (
                self.ambiguity.to_dict() if self.ambiguity is not None else None
            ),
            "diagnostics": dict(self.diagnostics),
        }


# ---------------------------------------------------------------------------
# Injected backend protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class InjectedIpfsBackend(Protocol):
    """Minimal injected IPFS surface used by the transport adapter."""

    def block_get(self, cid: str) -> Any:  # pragma: no cover - protocol
        ...

    def block_put(self, data: bytes) -> Any:  # pragma: no cover - protocol
        ...


def _client_method(client: Any | None, names: Sequence[str]) -> Callable[..., Any] | None:
    if client is None:
        return None
    for name in names:
        method = getattr(client, name, None)
        if callable(method):
            return method
    return None


def _extract_ipfs_cid(value: Any) -> str | None:
    if type(value) is str and value:
        return value
    if isinstance(value, Mapping):
        for key in ("cid", "CID", "Hash", "Key", "Cid"):
            candidate = value.get(key)
            if type(candidate) is str and candidate:
                return candidate
            if isinstance(candidate, Mapping) and type(candidate.get("/")) is str:
                text = candidate["/"]
                if text:
                    return text
    return None


def _extract_ipfs_bytes(value: Any, *, maximum: int) -> tuple[bytes | None, TransportReason | None]:
    """Extract bounded exact bytes; oversized payloads are typed failures."""

    if type(value) is bytes:
        if len(value) > maximum:
            return None, TransportReason.OVER_BUDGET
        return value, None
    if isinstance(value, bytearray):
        if len(value) > maximum:
            return None, TransportReason.OVER_BUDGET
        return bytes(value), None
    if isinstance(value, memoryview):
        if value.nbytes > maximum:
            return None, TransportReason.OVER_BUDGET
        return value.tobytes(), None
    if hasattr(value, "read") and callable(value.read):
        try:
            data = value.read(maximum + 1)
        except BaseException:
            return None, TransportReason.IPFS_RESPONSE_INVALID
        if type(data) is not bytes:
            return None, TransportReason.IPFS_RESPONSE_INVALID
        if len(data) > maximum:
            return None, TransportReason.OVER_BUDGET
        return data, None
    return None, TransportReason.IPFS_RESPONSE_INVALID


def _is_timeout_exception(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    if "timeout" in name or "timedout" in name:
        return True
    text = str(exc).lower()
    return "timeout" in text or "timed out" in text


def _is_public_kind(kind: ArtifactKind) -> bool:
    return kind in PUBLIC_ARTIFACT_KINDS


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


class IpfsProofArtifactTransport:
    """Optional injected IPFS transport for public proof-seal artifacts.

    Construction never starts a daemon and never discovers ``~/.ipfs``.
    Without an injected client or get/put callable the transport reports
    ``UNAVAILABLE`` for remote operations while local reconciliation against
    an optional :class:`HermeticProofSealStore` remains available.
    """

    __test__ = False

    def __init__(
        self,
        *,
        local_store: HermeticProofSealStore | None = None,
        ipfs_client: Any | None = None,
        ipfs_get: Callable[[str], Any] | None = None,
        ipfs_put: Callable[[bytes], Any] | None = None,
        max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        cache_remote_reads: bool = True,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if local_store is not None and not isinstance(local_store, HermeticProofSealStore):
            raise IpfsTransportError(
                "local_store must be a HermeticProofSealStore or None",
                reason=TransportReason.MALFORMED,
            )
        if ipfs_get is not None and not callable(ipfs_get):
            raise TypeError("ipfs_get must be callable")
        if ipfs_put is not None and not callable(ipfs_put):
            raise TypeError("ipfs_put must be callable")
        if (
            isinstance(max_artifact_bytes, bool)
            or not isinstance(max_artifact_bytes, int)
            or max_artifact_bytes <= 0
            or max_artifact_bytes > MAX_ARTIFACT_BYTES_BOUND
        ):
            raise ProofSealStoreContractError(
                "max_artifact_bytes must be a positive integer within the declared bound"
            )
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or timeout_seconds <= 0
            or float(timeout_seconds) > MAX_TIMEOUT_SECONDS
        ):
            raise ProofSealStoreContractError(
                "timeout_seconds must be a positive number within the declared bound"
            )
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")

        self._local = local_store
        self.max_artifact_bytes = max_artifact_bytes
        self.timeout_seconds = float(timeout_seconds)
        self.cache_remote_reads = bool(cache_remote_reads)
        self._clock: Callable[[], float] = clock or time.monotonic
        self._ipfs_get = ipfs_get or _client_method(
            ipfs_client, ("block_get", "get_block", "cat", "get")
        )
        self._ipfs_put = ipfs_put or _client_method(
            ipfs_client, ("block_put", "put_block", "add_bytes", "add")
        )
        self._ambiguities: list[TransportAmbiguityRecord] = []

    # -- capability surface -------------------------------------------------

    @property
    def local_store(self) -> HermeticProofSealStore | None:
        return self._local

    @property
    def ipfs_read_enabled(self) -> bool:
        return self._ipfs_get is not None

    @property
    def ipfs_write_enabled(self) -> bool:
        return self._ipfs_put is not None

    @property
    def available(self) -> bool:
        """Return whether any remote operation can be attempted."""

        return self.ipfs_read_enabled or self.ipfs_write_enabled

    @property
    def ambiguities(self) -> tuple[TransportAmbiguityRecord, ...]:
        """Return recorded backend ambiguity records (newest last)."""

        return tuple(self._ambiguities)

    def clear_ambiguities(self) -> None:
        self._ambiguities.clear()

    # -- public API ---------------------------------------------------------

    def replicate_public_artifact(
        self,
        kind: ArtifactKind | str | ArtifactReference | None = None,
        data: bytes | None = None,
        *,
        reference: ArtifactReference | None = None,
        claimed_cid: str | None = None,
    ) -> TransportReplicateResult:
        """Replicate a public closed-kind artifact through the injected backend.

        Prefer supplying a local :class:`ArtifactReference` so committed hermetic
        bytes are rehashed before any remote put.  Direct ``(kind, data)`` puts
        are accepted for callers that already hold verified public bytes.
        """

        resolved = self._resolve_replicate_payload(
            kind=kind,
            data=data,
            reference=reference,
            claimed_cid=claimed_cid,
        )
        if isinstance(resolved, TransportReplicateResult):
            return resolved
        closed_kind, payload, target_cid, local_reconciled, ref = resolved

        if self._ipfs_put is None:
            return TransportReplicateResult(
                TransportDisposition.UNAVAILABLE,
                TransportReason.UNAVAILABLE,
                reference=ref,
                cid=target_cid,
                byte_length=len(payload),
                local_reconciled=local_reconciled,
                diagnostics={"ipfs_write_enabled": False},
            )

        started = self._clock()
        try:
            response = self._ipfs_put(payload)
        except BaseException as exc:
            if _is_timeout_exception(exc):
                return TransportReplicateResult(
                    TransportDisposition.ERROR,
                    TransportReason.TIMEOUT,
                    reference=ref,
                    cid=target_cid,
                    byte_length=len(payload),
                    local_reconciled=local_reconciled,
                    diagnostics={
                        "elapsed_seconds": self._elapsed(started),
                        "exception_type": type(exc).__name__,
                    },
                )
            return TransportReplicateResult(
                TransportDisposition.ERROR,
                TransportReason.IPFS_ERROR,
                reference=ref,
                cid=target_cid,
                byte_length=len(payload),
                local_reconciled=local_reconciled,
                diagnostics={
                    "elapsed_seconds": self._elapsed(started),
                    "exception_type": type(exc).__name__,
                },
            )

        elapsed = self._elapsed(started)
        if elapsed > self.timeout_seconds:
            ambiguity = self._record_ambiguity(
                TransportReason.TIMEOUT,
                "IPFS put exceeded timeout after returning a response",
                cid=target_cid,
                kind=closed_kind.value,
                local_ok=local_reconciled,
                remote_ok=None,
                diagnostics={"elapsed_seconds": elapsed},
            )
            return TransportReplicateResult(
                TransportDisposition.AMBIGUOUS,
                TransportReason.BACKEND_AMBIGUOUS,
                reference=ref,
                cid=target_cid,
                byte_length=len(payload),
                local_reconciled=local_reconciled,
                ambiguity=ambiguity,
                diagnostics={"elapsed_seconds": elapsed},
            )

        response_cid = _extract_ipfs_cid(response)
        if response_cid is None:
            # A put that returns no CID is ambiguous: the backend may or may
            # not have stored the block.  Local committed bytes stay usable.
            ambiguity = self._record_ambiguity(
                TransportReason.IPFS_RESPONSE_INVALID,
                "IPFS put response did not carry a CID; backend state is ambiguous",
                cid=target_cid,
                kind=closed_kind.value,
                local_ok=local_reconciled,
                remote_ok=None,
                diagnostics={"elapsed_seconds": elapsed},
            )
            return TransportReplicateResult(
                TransportDisposition.AMBIGUOUS,
                TransportReason.BACKEND_AMBIGUOUS,
                reference=ref,
                cid=target_cid,
                byte_length=len(payload),
                local_reconciled=local_reconciled,
                ambiguity=ambiguity,
                diagnostics={"elapsed_seconds": elapsed},
            )

        if not verify_content_identity(response_cid, payload):
            # Backend claimed a different content identity for the same put.
            ambiguity = self._record_ambiguity(
                TransportReason.CID_MISMATCH,
                "IPFS put response CID does not rehash the payload",
                cid=target_cid,
                kind=closed_kind.value,
                local_ok=local_reconciled,
                remote_ok=False,
                diagnostics={
                    "elapsed_seconds": elapsed,
                    "response_cid": response_cid,
                },
            )
            return TransportReplicateResult(
                TransportDisposition.AMBIGUOUS,
                TransportReason.BACKEND_AMBIGUOUS,
                reference=ref,
                cid=target_cid,
                byte_length=len(payload),
                local_reconciled=local_reconciled,
                ambiguity=ambiguity,
                diagnostics={
                    "elapsed_seconds": elapsed,
                    "response_cid": response_cid,
                },
            )

        # Prefer the locally admitted identity when it rehashes; require the
        # backend response to bind the same digest (checked above).
        admitted = ref or ArtifactReference(
            cid=target_cid,
            kind=closed_kind,
            byte_length=len(payload),
        )
        return TransportReplicateResult(
            TransportDisposition.OK,
            TransportReason.OK,
            reference=admitted,
            cid=admitted.cid,
            byte_length=len(payload),
            local_reconciled=local_reconciled,
            ipfs_stored=True,
            diagnostics={
                "elapsed_seconds": elapsed,
                "response_cid": response_cid,
            },
        )

    def fetch_public_artifact(
        self,
        reference: ArtifactReference | Mapping[str, Any] | str,
        *,
        kind: ArtifactKind | str | None = None,
        prefer_local: bool = True,
    ) -> TransportFetchResult:
        """Fetch and rehash a public artifact; fail closed on bad responses.

        Local committed bytes are preferred when present and reconcilable.
        Remote faults never mutate or discard already-admitted local objects.
        """

        ref_result = self._coerce_fetch_reference(reference, kind=kind)
        if isinstance(ref_result, TransportFetchResult):
            return ref_result
        ref = ref_result

        if ref.byte_length > self.max_artifact_bytes:
            return TransportFetchResult(
                TransportDisposition.REJECTED,
                TransportReason.OVER_BUDGET,
                reference=ref,
                cid=ref.cid,
                byte_length=ref.byte_length,
            )

        local_bytes: bytes | None = None
        local_ok: bool | None = None
        if prefer_local and self._local is not None:
            local = self._local.get_verified_bytes_result(ref)
            local_status = self._classify_local_get(local)
            if local_status == "hit" and local.data is not None:
                local_bytes = local.data
                local_ok = True
                return TransportFetchResult(
                    TransportDisposition.HIT,
                    TransportReason.OK,
                    data=local_bytes,
                    reference=ArtifactReference(
                        cid=ref.cid,
                        kind=ref.kind,
                        byte_length=len(local_bytes),
                    ),
                    cid=ref.cid,
                    byte_length=len(local_bytes),
                    source=TransportSource.LOCAL,
                    local_reconciled=True,
                )
            if local_status == "integrity":
                # Local corruption is reported; remote may still be attempted
                # for recovery, but any conflict is ambiguity.
                local_ok = False
            elif local_status == "miss":
                local_ok = None
            else:
                local_ok = False

        if self._ipfs_get is None:
            if local_ok is False:
                return TransportFetchResult(
                    TransportDisposition.ERROR,
                    TransportReason.LOCAL_INTEGRITY_FAILED,
                    reference=ref,
                    cid=ref.cid,
                    local_reconciled=False,
                    diagnostics={"ipfs_read_enabled": False},
                )
            return TransportFetchResult(
                TransportDisposition.UNAVAILABLE
                if self._local is None
                else TransportDisposition.MISS,
                TransportReason.UNAVAILABLE
                if self._local is None
                else TransportReason.NOT_FOUND,
                reference=ref,
                cid=ref.cid,
                diagnostics={"ipfs_read_enabled": False},
            )

        started = self._clock()
        try:
            response = self._ipfs_get(ref.cid)
        except BaseException as exc:
            if _is_timeout_exception(exc):
                return TransportFetchResult(
                    TransportDisposition.ERROR,
                    TransportReason.TIMEOUT,
                    reference=ref,
                    cid=ref.cid,
                    local_reconciled=bool(local_ok),
                    diagnostics={
                        "elapsed_seconds": self._elapsed(started),
                        "exception_type": type(exc).__name__,
                        "local_ok": local_ok,
                    },
                )
            return TransportFetchResult(
                TransportDisposition.ERROR,
                TransportReason.IPFS_ERROR,
                reference=ref,
                cid=ref.cid,
                local_reconciled=bool(local_ok),
                diagnostics={
                    "elapsed_seconds": self._elapsed(started),
                    "exception_type": type(exc).__name__,
                    "local_ok": local_ok,
                },
            )

        elapsed = self._elapsed(started)
        if elapsed > self.timeout_seconds:
            ambiguity = self._record_ambiguity(
                TransportReason.TIMEOUT,
                "IPFS get exceeded timeout after returning a response",
                cid=ref.cid,
                kind=ref.kind.value,
                local_ok=local_ok,
                remote_ok=None,
                diagnostics={"elapsed_seconds": elapsed},
            )
            return TransportFetchResult(
                TransportDisposition.AMBIGUOUS,
                TransportReason.BACKEND_AMBIGUOUS,
                reference=ref,
                cid=ref.cid,
                local_reconciled=bool(local_ok),
                ambiguity=ambiguity,
                diagnostics={"elapsed_seconds": elapsed},
            )

        # Some backends return {cid, data, kind} envelopes; reject wrong kind.
        envelope_kind, kind_error = self._extract_response_kind(response)
        if kind_error is not None:
            return TransportFetchResult(
                TransportDisposition.REJECTED,
                kind_error,
                reference=ref,
                cid=ref.cid,
                local_reconciled=bool(local_ok),
                diagnostics={
                    "elapsed_seconds": elapsed,
                    "expected_kind": ref.kind.value,
                },
            )
        if envelope_kind is not None and envelope_kind is not ref.kind:
            return TransportFetchResult(
                TransportDisposition.REJECTED,
                TransportReason.WRONG_KIND,
                reference=ref,
                cid=ref.cid,
                local_reconciled=bool(local_ok),
                diagnostics={
                    "elapsed_seconds": elapsed,
                    "response_kind": envelope_kind.value,
                    "expected_kind": ref.kind.value,
                },
            )

        data, extract_reason = _extract_ipfs_bytes(
            self._unwrap_response_payload(response),
            maximum=self.max_artifact_bytes,
        )
        if data is None:
            reason = extract_reason or TransportReason.IPFS_RESPONSE_INVALID
            # If local was corrupted and remote is also invalid, record ambiguity.
            if local_ok is False:
                ambiguity = self._record_ambiguity(
                    reason,
                    "local integrity failed and remote response is unusable",
                    cid=ref.cid,
                    kind=ref.kind.value,
                    local_ok=False,
                    remote_ok=False,
                    diagnostics={"elapsed_seconds": elapsed},
                )
                return TransportFetchResult(
                    TransportDisposition.AMBIGUOUS,
                    TransportReason.BACKEND_AMBIGUOUS,
                    reference=ref,
                    cid=ref.cid,
                    local_reconciled=False,
                    ambiguity=ambiguity,
                    diagnostics={"elapsed_seconds": elapsed, "extract_reason": reason.value},
                )
            return TransportFetchResult(
                TransportDisposition.REJECTED
                if reason is TransportReason.OVER_BUDGET
                else TransportDisposition.ERROR,
                reason,
                reference=ref,
                cid=ref.cid,
                local_reconciled=bool(local_ok),
                diagnostics={"elapsed_seconds": elapsed},
            )

        if not verify_content_identity(ref.cid, data):
            # Corrupt remote body: fail closed.  Local committed bytes that
            # still rehash remain independently reconcilable.
            local_still_ok = False
            if self._local is not None:
                local_check = self._local.get_verified_bytes_result(ref)
                local_still_ok = bool(local_check.hit)
            return TransportFetchResult(
                TransportDisposition.REJECTED,
                TransportReason.CORRUPTED,
                reference=ref,
                cid=ref.cid,
                byte_length=len(data),
                local_reconciled=local_still_ok,
                diagnostics={
                    "elapsed_seconds": elapsed,
                    "remote_byte_length": len(data),
                    "local_still_ok": local_still_ok,
                },
            )

        if ref.byte_length > 0 and len(data) != ref.byte_length:
            return TransportFetchResult(
                TransportDisposition.REJECTED,
                TransportReason.INTEGRITY_FAILED,
                reference=ref,
                cid=ref.cid,
                byte_length=len(data),
                local_reconciled=bool(local_ok),
                diagnostics={
                    "elapsed_seconds": elapsed,
                    "expected_byte_length": ref.byte_length,
                    "actual_byte_length": len(data),
                },
            )

        # If local was present but corrupted, and remote verifies, record that
        # recovery path without silently claiming local was fine.
        if local_ok is False:
            ambiguity = self._record_ambiguity(
                TransportReason.LOCAL_INTEGRITY_FAILED,
                "local bytes failed integrity while remote rehashed; "
                "backends disagree until local is repaired",
                cid=ref.cid,
                kind=ref.kind.value,
                local_ok=False,
                remote_ok=True,
                diagnostics={"elapsed_seconds": elapsed},
            )
            # Still return verified remote bytes, but mark ambiguous so callers
            # cannot treat the overall store state as clean success.
            return TransportFetchResult(
                TransportDisposition.AMBIGUOUS,
                TransportReason.BACKEND_AMBIGUOUS,
                data=data,
                reference=ArtifactReference(
                    cid=ref.cid, kind=ref.kind, byte_length=len(data)
                ),
                cid=ref.cid,
                byte_length=len(data),
                source=TransportSource.IPFS,
                local_reconciled=False,
                ambiguity=ambiguity,
                diagnostics={"elapsed_seconds": elapsed},
            )

        admitted = ArtifactReference(
            cid=ref.cid, kind=ref.kind, byte_length=len(data)
        )
        local_reconciled = False
        source = TransportSource.IPFS
        if self._local is not None and self.cache_remote_reads:
            put = self._local.put_immutable_result(
                ref.kind, data, claimed_cid=ref.cid
            )
            if put.stored:
                local_reconciled = True
                source = TransportSource.LOCAL_AND_IPFS
            elif put.reason not in {
                LocalStoreReason.ALREADY_EXISTS,
                LocalStoreReason.OK,
            }:
                # Remote verified but local admission failed — record ambiguity.
                ambiguity = self._record_ambiguity(
                    TransportReason.LOCAL_INTEGRITY_FAILED
                    if put.reason
                    in {
                        LocalStoreReason.CID_MISMATCH,
                        LocalStoreReason.CORRUPTED,
                        LocalStoreReason.INTEGRITY_FAILED,
                        LocalStoreReason.KIND_MISMATCH,
                    }
                    else TransportReason.IPFS_ERROR,
                    "remote bytes verified but local admission failed",
                    cid=ref.cid,
                    kind=ref.kind.value,
                    local_ok=False,
                    remote_ok=True,
                    diagnostics={
                        "elapsed_seconds": elapsed,
                        "local_reason": put.reason.value,
                    },
                )
                return TransportFetchResult(
                    TransportDisposition.AMBIGUOUS,
                    TransportReason.BACKEND_AMBIGUOUS,
                    data=data,
                    reference=admitted,
                    cid=ref.cid,
                    byte_length=len(data),
                    source=TransportSource.IPFS,
                    local_reconciled=False,
                    ambiguity=ambiguity,
                    diagnostics={
                        "elapsed_seconds": elapsed,
                        "local_reason": put.reason.value,
                    },
                )
            else:
                local_reconciled = True
                source = TransportSource.LOCAL_AND_IPFS

        return TransportFetchResult(
            TransportDisposition.HIT,
            TransportReason.OK,
            data=data,
            reference=admitted,
            cid=ref.cid,
            byte_length=len(data),
            source=source,
            local_reconciled=local_reconciled or bool(local_ok),
            diagnostics={"elapsed_seconds": elapsed},
        )

    def reconcile_local(
        self, reference: ArtifactReference | Mapping[str, Any]
    ) -> TransportFetchResult:
        """Rehash local committed bytes for ``reference`` without remote I/O."""

        ref_result = self._coerce_fetch_reference(reference, kind=None)
        if isinstance(ref_result, TransportFetchResult):
            return ref_result
        ref = ref_result
        if self._local is None:
            return TransportFetchResult(
                TransportDisposition.UNAVAILABLE,
                TransportReason.UNAVAILABLE,
                reference=ref,
                cid=ref.cid,
                diagnostics={"local_store": False},
            )
        local = self._local.get_verified_bytes_result(ref)
        if local.hit and local.data is not None:
            return TransportFetchResult(
                TransportDisposition.HIT,
                TransportReason.OK,
                data=local.data,
                reference=ArtifactReference(
                    cid=ref.cid, kind=ref.kind, byte_length=len(local.data)
                ),
                cid=ref.cid,
                byte_length=len(local.data),
                source=TransportSource.LOCAL,
                local_reconciled=True,
            )
        reason = self._local_reason_to_transport(local.reason)
        disposition = (
            TransportDisposition.MISS
            if local.disposition is StoreGetDisposition.MISS
            else TransportDisposition.REJECTED
            if local.disposition
            in {
                StoreGetDisposition.INTEGRITY_FAILED,
                StoreGetDisposition.KIND_MISMATCH,
                StoreGetDisposition.REJECTED,
            }
            else TransportDisposition.ERROR
        )
        return TransportFetchResult(
            disposition,
            reason,
            reference=ref,
            cid=ref.cid,
            byte_length=local.byte_length,
            local_reconciled=False,
        )

    # -- helpers ------------------------------------------------------------

    def _elapsed(self, started: float) -> float:
        try:
            return max(0.0, float(self._clock()) - float(started))
        except Exception:
            return 0.0

    def _record_ambiguity(
        self,
        reason: TransportReason,
        message: str,
        *,
        cid: str = "",
        kind: str = "",
        local_ok: bool | None = None,
        remote_ok: bool | None = None,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> TransportAmbiguityRecord:
        record = TransportAmbiguityRecord(
            reason=reason,
            message=message,
            cid=cid,
            kind=kind,
            local_ok=local_ok,
            remote_ok=remote_ok,
            diagnostics=diagnostics or {},
        )
        self._ambiguities.append(record)
        # Bound retained history.
        if len(self._ambiguities) > 64:
            self._ambiguities = self._ambiguities[-64:]
        return record

    def _resolve_replicate_payload(
        self,
        *,
        kind: ArtifactKind | str | ArtifactReference | None,
        data: bytes | None,
        reference: ArtifactReference | None,
        claimed_cid: str | None,
    ) -> (
        tuple[ArtifactKind, bytes, str, bool, ArtifactReference | None]
        | TransportReplicateResult
    ):
        ref = reference
        if isinstance(kind, ArtifactReference) and ref is None:
            ref = kind
            kind = None

        if ref is not None:
            if not isinstance(ref, ArtifactReference):
                try:
                    ref = ArtifactReference.from_dict(ref)  # type: ignore[arg-type]
                except (ProofSealStoreContractError, TypeError, ValueError):
                    return TransportReplicateResult(
                        TransportDisposition.REJECTED,
                        TransportReason.MALFORMED,
                    )
            if is_forbidden_artifact_kind(ref.kind):
                return TransportReplicateResult(
                    TransportDisposition.REJECTED,
                    TransportReason.FORBIDDEN_KIND,
                    cid=ref.cid,
                )
            if not _is_public_kind(ref.kind):
                return TransportReplicateResult(
                    TransportDisposition.REJECTED,
                    TransportReason.WRONG_KIND,
                    reference=ref,
                    cid=ref.cid,
                )
            if data is not None:
                if type(data) is not bytes:
                    return TransportReplicateResult(
                        TransportDisposition.REJECTED,
                        TransportReason.MALFORMED,
                        reference=ref,
                        cid=ref.cid,
                    )
                if len(data) > self.max_artifact_bytes:
                    return TransportReplicateResult(
                        TransportDisposition.REJECTED,
                        TransportReason.OVER_BUDGET,
                        reference=ref,
                        cid=ref.cid,
                        byte_length=len(data),
                    )
                if not verify_content_identity(ref.cid, data):
                    return TransportReplicateResult(
                        TransportDisposition.REJECTED,
                        TransportReason.CID_MISMATCH,
                        reference=ref,
                        cid=ref.cid,
                        byte_length=len(data),
                    )
                if ref.byte_length > 0 and len(data) != ref.byte_length:
                    return TransportReplicateResult(
                        TransportDisposition.REJECTED,
                        TransportReason.INTEGRITY_FAILED,
                        reference=ref,
                        cid=ref.cid,
                        byte_length=len(data),
                    )
                return ref.kind, data, ref.cid, False, ref

            if self._local is None:
                return TransportReplicateResult(
                    TransportDisposition.REJECTED,
                    TransportReason.LOCAL_MISS,
                    reference=ref,
                    cid=ref.cid,
                    diagnostics={"local_store": False},
                )
            local = self._local.get_verified_bytes_result(ref)
            if not local.hit or local.data is None:
                reason = self._local_reason_to_transport(local.reason)
                if reason is TransportReason.NOT_FOUND:
                    reason = TransportReason.LOCAL_MISS
                return TransportReplicateResult(
                    TransportDisposition.REJECTED
                    if local.disposition
                    in {
                        StoreGetDisposition.MISS,
                        StoreGetDisposition.REJECTED,
                        StoreGetDisposition.INTEGRITY_FAILED,
                        StoreGetDisposition.KIND_MISMATCH,
                    }
                    else TransportDisposition.ERROR,
                    reason,
                    reference=ref,
                    cid=ref.cid,
                    local_reconciled=False,
                )
            return ref.kind, local.data, ref.cid, True, ref

        # Direct kind + data path.
        try:
            if kind is None:
                raise ArtifactKindError("kind is required when reference is absent")
            closed_kind = coerce_artifact_kind(kind, field_name="kind")
        except ForbiddenArtifactError:
            return TransportReplicateResult(
                TransportDisposition.REJECTED,
                TransportReason.FORBIDDEN_KIND,
                cid=claimed_cid or "",
            )
        except ArtifactKindError:
            return TransportReplicateResult(
                TransportDisposition.REJECTED,
                TransportReason.MALFORMED,
                cid=claimed_cid or "",
            )

        if not _is_public_kind(closed_kind):
            return TransportReplicateResult(
                TransportDisposition.REJECTED,
                TransportReason.WRONG_KIND,
                cid=claimed_cid or "",
            )
        if type(data) is not bytes:
            return TransportReplicateResult(
                TransportDisposition.REJECTED,
                TransportReason.MALFORMED,
                cid=claimed_cid or "",
            )
        if len(data) > self.max_artifact_bytes:
            return TransportReplicateResult(
                TransportDisposition.REJECTED,
                TransportReason.OVER_BUDGET,
                cid=claimed_cid or "",
                byte_length=len(data),
            )

        computed = content_cid_for_bytes(data)
        if claimed_cid is not None:
            if type(claimed_cid) is not str or not claimed_cid:
                return TransportReplicateResult(
                    TransportDisposition.REJECTED,
                    TransportReason.MALFORMED,
                    byte_length=len(data),
                )
            if not verify_content_identity(claimed_cid, data):
                return TransportReplicateResult(
                    TransportDisposition.REJECTED,
                    TransportReason.CID_MISMATCH,
                    cid=claimed_cid,
                    byte_length=len(data),
                )
            target_cid = claimed_cid
        else:
            target_cid = computed

        ref_out = ArtifactReference(
            cid=target_cid, kind=closed_kind, byte_length=len(data)
        )
        local_reconciled = False
        if self._local is not None:
            # Ensure local admission when a store is attached so remote
            # replication cannot outrun local committed bytes.
            put = self._local.put_immutable_result(
                closed_kind, data, claimed_cid=target_cid
            )
            if put.stored or put.disposition is StorePutDisposition.ALREADY_EXISTS:
                local_reconciled = True
                if put.reference is not None:
                    ref_out = put.reference
            else:
                return TransportReplicateResult(
                    TransportDisposition.ERROR,
                    self._local_reason_to_transport(put.reason),
                    cid=target_cid,
                    byte_length=len(data),
                    local_reconciled=False,
                    diagnostics={"local_reason": put.reason.value},
                )

        return closed_kind, data, target_cid, local_reconciled, ref_out

    def _coerce_fetch_reference(
        self,
        reference: ArtifactReference | Mapping[str, Any] | str,
        *,
        kind: ArtifactKind | str | None,
    ) -> ArtifactReference | TransportFetchResult:
        if isinstance(reference, ArtifactReference):
            ref = reference
        elif isinstance(reference, Mapping):
            try:
                ref = ArtifactReference.from_dict(reference)
            except (ProofSealStoreContractError, TypeError, ValueError):
                return TransportFetchResult(
                    TransportDisposition.REJECTED,
                    TransportReason.MALFORMED,
                )
        elif type(reference) is str:
            if kind is None:
                return TransportFetchResult(
                    TransportDisposition.REJECTED,
                    TransportReason.MALFORMED,
                    cid=reference,
                    diagnostics={"missing_kind": True},
                )
            try:
                closed_kind = coerce_artifact_kind(kind, field_name="kind")
            except ForbiddenArtifactError:
                return TransportFetchResult(
                    TransportDisposition.REJECTED,
                    TransportReason.FORBIDDEN_KIND,
                    cid=reference,
                )
            except ArtifactKindError:
                return TransportFetchResult(
                    TransportDisposition.REJECTED,
                    TransportReason.WRONG_KIND
                    if not is_forbidden_artifact_kind(kind)
                    else TransportReason.FORBIDDEN_KIND,
                    cid=reference,
                )
            try:
                ref = ArtifactReference(cid=reference, kind=closed_kind)
            except ProofSealStoreContractError:
                return TransportFetchResult(
                    TransportDisposition.REJECTED,
                    TransportReason.MALFORMED,
                    cid=reference,
                )
        else:
            return TransportFetchResult(
                TransportDisposition.REJECTED,
                TransportReason.MALFORMED,
            )

        if is_forbidden_artifact_kind(ref.kind):
            return TransportFetchResult(
                TransportDisposition.REJECTED,
                TransportReason.FORBIDDEN_KIND,
                cid=ref.cid,
            )
        if not _is_public_kind(ref.kind):
            return TransportFetchResult(
                TransportDisposition.REJECTED,
                TransportReason.WRONG_KIND,
                reference=ref,
                cid=ref.cid,
            )
        if kind is not None:
            try:
                expected = coerce_artifact_kind(kind, field_name="kind")
            except ForbiddenArtifactError:
                return TransportFetchResult(
                    TransportDisposition.REJECTED,
                    TransportReason.FORBIDDEN_KIND,
                    reference=ref,
                    cid=ref.cid,
                )
            except ArtifactKindError:
                return TransportFetchResult(
                    TransportDisposition.REJECTED,
                    TransportReason.WRONG_KIND,
                    reference=ref,
                    cid=ref.cid,
                )
            if expected is not ref.kind:
                return TransportFetchResult(
                    TransportDisposition.REJECTED,
                    TransportReason.KIND_MISMATCH,
                    reference=ref,
                    cid=ref.cid,
                    diagnostics={
                        "expected_kind": expected.value,
                        "reference_kind": ref.kind.value,
                    },
                )
        return ref

    @staticmethod
    def _classify_local_get(result: LocalGetResult) -> str:
        if result.hit and result.data is not None:
            return "hit"
        if result.reason in {
            LocalStoreReason.NOT_FOUND,
        }:
            return "miss"
        if result.reason in {
            LocalStoreReason.CID_MISMATCH,
            LocalStoreReason.KIND_MISMATCH,
            LocalStoreReason.INTEGRITY_FAILED,
            LocalStoreReason.CORRUPTED,
        }:
            return "integrity"
        return "error"

    @staticmethod
    def _local_reason_to_transport(reason: LocalStoreReason) -> TransportReason:
        mapping = {
            LocalStoreReason.OK: TransportReason.OK,
            LocalStoreReason.ALREADY_EXISTS: TransportReason.ALREADY_EXISTS,
            LocalStoreReason.NOT_FOUND: TransportReason.NOT_FOUND,
            LocalStoreReason.MALFORMED: TransportReason.MALFORMED,
            LocalStoreReason.OVER_BUDGET: TransportReason.OVER_BUDGET,
            LocalStoreReason.CID_MISMATCH: TransportReason.CID_MISMATCH,
            LocalStoreReason.KIND_MISMATCH: TransportReason.KIND_MISMATCH,
            LocalStoreReason.INTEGRITY_FAILED: TransportReason.INTEGRITY_FAILED,
            LocalStoreReason.CORRUPTED: TransportReason.CORRUPTED,
            LocalStoreReason.FORBIDDEN_KIND: TransportReason.FORBIDDEN_KIND,
            LocalStoreReason.IO_ERROR: TransportReason.IPFS_ERROR,
            LocalStoreReason.UNSUPPORTED: TransportReason.MALFORMED,
            LocalStoreReason.SYMLINK_REJECTED: TransportReason.MALFORMED,
            LocalStoreReason.PATH_ESCAPE: TransportReason.MALFORMED,
            LocalStoreReason.SHORT_WRITE: TransportReason.IPFS_ERROR,
            LocalStoreReason.FSYNC_FAILED: TransportReason.IPFS_ERROR,
            LocalStoreReason.READBACK_FAILED: TransportReason.INTEGRITY_FAILED,
        }
        return mapping.get(reason, TransportReason.IPFS_ERROR)

    @staticmethod
    def _extract_response_kind(
        response: Any,
    ) -> tuple[ArtifactKind | None, TransportReason | None]:
        if not isinstance(response, Mapping):
            return None, None
        if "kind" not in response and "artifact_kind" not in response:
            return None, None
        raw = response.get("kind", response.get("artifact_kind"))
        if raw is None or raw == "":
            return None, None
        if is_forbidden_artifact_kind(raw):
            return None, TransportReason.FORBIDDEN_KIND
        try:
            return coerce_artifact_kind(raw, field_name="kind"), None
        except ForbiddenArtifactError:
            return None, TransportReason.FORBIDDEN_KIND
        except (ArtifactKindError, ProofSealStoreContractError):
            return None, TransportReason.WRONG_KIND

    @staticmethod
    def _unwrap_response_payload(response: Any) -> Any:
        if isinstance(response, Mapping):
            for key in ("data", "bytes", "payload", "content", "Body", "body"):
                if key in response:
                    return response[key]
        return response


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "EVIDENCE_SUBSET",
    "IPFS_TRANSPORT_INTERFACE",
    "IPFS_TRANSPORT_SCHEMA",
    "InjectedIpfsBackend",
    "IpfsProofArtifactTransport",
    "IpfsTransportAmbiguousError",
    "IpfsTransportError",
    "IpfsTransportUnavailableError",
    "MAX_TIMEOUT_SECONDS",
    "PUBLIC_ARTIFACT_KINDS",
    "TransportAmbiguityRecord",
    "TransportDisposition",
    "TransportFetchResult",
    "TransportReason",
    "TransportReplicateResult",
    "TransportSource",
]
