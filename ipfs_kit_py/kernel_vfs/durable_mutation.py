"""Bind staged VFS mutation effects to the WAL coordinator (KVFS-309).

This module owns the *mutation ordering façade* that composes:

* **validate → authorize → lock** before any durable intent is recorded;
* **intent durability** before the canonical VFS effect is applied;
* **decision + effect identity durability** before a committed acknowledgement
  is returned to the caller; and
* **idempotent apply / compensate** for ``create`` / ``write`` / ``truncate`` /
  ``unlink`` / ``rename`` with **exact partial-effect receipts**.

Default ordering (plan §3.4):

```text
validate + authorize
  -> acquire deterministic path locks
  -> append recoverable WAL intent (+ payload/reference)
  -> meet configured intent durability boundary
  -> apply canonical VFS transaction/backend effect
  -> append decision/effect identity
  -> return committed acknowledgement
```

ARC invalidation is deliberately out of scope (KVFS-404).  This module does not
import fusepy, open host mounts, or perform network I/O.

Interfaces (plan aliases): ``DurableMutationFacade@1``,
``DurableMutationCoordinator@1``, ``PartialEffectReceipt@1``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final

from ipfs_kit_py.core.operation_contracts import (
    EffectKind,
    OperationState,
    PartialEffectRecord,
)
from ipfs_kit_py.core.vfs.contracts import VFSEntryKind, VFSOperationKind
from ipfs_kit_py.core.vfs.host_concurrency import (
    HostLockKey,
    HostLockManager,
    HostLockRequest,
    LockMode,
    ordered_lock_requests,
)
from ipfs_kit_py.core.vfs.service import (
    CanonicalVFSService,
    InMemoryVFSStorage,
    VFSExecuteRequest,
    VFSStoredEntry,
    content_cid_for_bytes,
    make_op,
    version_cid_for,
)
from ipfs_kit_py.core.wal.coordinator import (
    TransactionResult,
    WALTransactionCoordinator,
    WALTransactionCrash,
    WALTransactionError,
)
from ipfs_kit_py.core.wal.contracts import WALAcknowledgementMode
from ipfs_kit_py.core.wal.vfs_records import (
    VFSWALAcknowledgement,
    VFSWALContent,
    VFSWALDecision,
    VFSWALDurableData,
    VFSWALIntentKind,
    VFSWALPrecondition,
    make_durable_data,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-309"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

DURABLE_MUTATION_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/durable_mutation"

DURABLE_MUTATION_FACADE_SCHEMA: Final[str] = (
    f"{DURABLE_MUTATION_NAMESPACE}/durable-mutation-facade@{SCHEMA_MAJOR}"
)
DURABLE_MUTATION_COORDINATOR_SCHEMA: Final[str] = (
    f"{DURABLE_MUTATION_NAMESPACE}/durable-mutation-coordinator@{SCHEMA_MAJOR}"
)
MUTATION_REQUEST_SCHEMA: Final[str] = (
    f"{DURABLE_MUTATION_NAMESPACE}/mutation-request@{SCHEMA_MAJOR}"
)
MUTATION_RESULT_SCHEMA: Final[str] = (
    f"{DURABLE_MUTATION_NAMESPACE}/mutation-result@{SCHEMA_MAJOR}"
)
PARTIAL_EFFECT_RECEIPT_SCHEMA: Final[str] = (
    f"{DURABLE_MUTATION_NAMESPACE}/partial-effect-receipt@{SCHEMA_MAJOR}"
)
MUTATION_PHASE_TRACE_SCHEMA: Final[str] = (
    f"{DURABLE_MUTATION_NAMESPACE}/mutation-phase-trace@{SCHEMA_MAJOR}"
)
EFFECT_LEDGER_SCHEMA: Final[str] = (
    f"{DURABLE_MUTATION_NAMESPACE}/effect-ledger@{SCHEMA_MAJOR}"
)

# Public interface aliases.
DurableMutationFacade_V1: Final[str] = DURABLE_MUTATION_FACADE_SCHEMA
DurableMutationCoordinator_V1: Final[str] = DURABLE_MUTATION_COORDINATOR_SCHEMA
PartialEffectReceipt_V1: Final[str] = PARTIAL_EFFECT_RECEIPT_SCHEMA

MAX_PATH_BYTES: Final[int] = 4_096
MAX_PAYLOAD_BYTES: Final[int] = 1_048_576
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
MAX_TRACE_STEPS: Final[int] = 4_096
MAX_EFFECT_LEDGER: Final[int] = 16_384
MAX_PARTIAL_RECEIPTS: Final[int] = 1_024
MAX_TEXT_BYTES: Final[int] = 4_096
DEFAULT_GENERATION_ID: Final[str] = "wal-gen:durable-mutation-1"
DEFAULT_MOUNT_ID: Final[str] = "mount:default"


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class MutationKind(str, Enum):
    """Closed mutation vocabulary bound to WAL intents (KVFS-309 acceptance)."""

    CREATE = "create"
    WRITE = "write"
    TRUNCATE = "truncate"
    UNLINK = "unlink"
    RENAME = "rename"


class MutationPhase(str, Enum):
    """Ordered protocol phases for one durable mutation."""

    VALIDATE = "validate"
    AUTHORIZE = "authorize"
    LOCK = "lock"
    INTENT = "intent"
    EFFECT = "effect"
    DECISION = "decision"
    ACK = "ack"
    COMPENSATE = "compensate"
    REJECT = "reject"


class MutationDisposition(str, Enum):
    """Terminal disposition of a mutation attempt."""

    COMMITTED = "committed"
    ABORTED = "aborted"
    COMPENSATED = "compensated"
    REJECTED = "rejected"
    FAILED = "failed"
    PARTIAL = "partial"
    CRASHED = "crashed"


class PartialEffectKind(str, Enum):
    """Exact partial-effect classifications for mutation receipts."""

    NONE = "none"
    EFFECT_APPLIED_PRE_COMMIT = "effect_applied_pre_commit"
    EFFECT_FAILED_MID_APPLY = "effect_failed_mid_apply"
    COMPENSATION_REQUIRED = "compensation_required"
    COMPENSATION_APPLIED = "compensation_applied"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    IDEMPOTENT_COMPENSATE = "idempotent_compensate"
    INTENT_ONLY = "intent_only"
    DECISION_PENDING = "decision_pending"


class MutationErrorCode(str, Enum):
    """Stable error codes for the durable mutation façade."""

    VALIDATION = "MUTATION_VALIDATION"
    AUTHORIZATION = "MUTATION_AUTHORIZATION"
    LOCK = "MUTATION_LOCK"
    INTENT = "MUTATION_INTENT"
    EFFECT = "MUTATION_EFFECT"
    DECISION = "MUTATION_DECISION"
    PARTIAL = "MUTATION_PARTIAL"
    PROTOCOL = "MUTATION_PROTOCOL"
    NOT_FOUND = "MUTATION_NOT_FOUND"
    ALREADY_EXISTS = "MUTATION_ALREADY_EXISTS"
    CONFLICT = "MUTATION_CONFLICT"
    INTERNAL = "MUTATION_INTERNAL"


_MUTATION_TO_WAL_INTENT: Final[Mapping[MutationKind, VFSWALIntentKind]] = {
    MutationKind.CREATE: VFSWALIntentKind.CREATE,
    MutationKind.WRITE: VFSWALIntentKind.WRITE,
    MutationKind.TRUNCATE: VFSWALIntentKind.TRUNCATE,
    MutationKind.UNLINK: VFSWALIntentKind.UNLINK,
    MutationKind.RENAME: VFSWALIntentKind.RENAME,
}

_MUTATION_TO_EFFECT_KIND: Final[Mapping[MutationKind, EffectKind]] = {
    MutationKind.CREATE: EffectKind.BACKEND_WRITE,
    MutationKind.WRITE: EffectKind.BACKEND_WRITE,
    MutationKind.TRUNCATE: EffectKind.BACKEND_WRITE,
    MutationKind.UNLINK: EffectKind.BACKEND_DELETE,
    MutationKind.RENAME: EffectKind.BACKEND_RENAME,
}

# Must complete before durable intent.
PRE_INTENT_PHASES: Final[tuple[MutationPhase, ...]] = (
    MutationPhase.VALIDATE,
    MutationPhase.AUTHORIZE,
    MutationPhase.LOCK,
)
_PRE_INTENT_PHASE_VALUES: Final[tuple[MutationPhase, ...]] = PRE_INTENT_PHASES


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DurableMutationError(Exception):
    """Base class for durable mutation failures."""

    def __init__(
        self,
        message: str,
        *,
        code: MutationErrorCode = MutationErrorCode.INTERNAL,
        phase: MutationPhase | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.phase = phase
        self.detail = dict(detail or {})


class MutationValidationError(DurableMutationError):
    def __init__(
        self,
        message: str = "mutation validation failed",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            code=kwargs.pop("code", MutationErrorCode.VALIDATION),
            phase=kwargs.pop("phase", MutationPhase.VALIDATE),
            **kwargs,
        )


class MutationAuthorizationError(DurableMutationError):
    def __init__(
        self,
        message: str = "mutation not authorized",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            code=kwargs.pop("code", MutationErrorCode.AUTHORIZATION),
            phase=kwargs.pop("phase", MutationPhase.AUTHORIZE),
            **kwargs,
        )


class MutationLockError(DurableMutationError):
    def __init__(
        self,
        message: str = "mutation lock acquisition failed",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            code=kwargs.pop("code", MutationErrorCode.LOCK),
            phase=kwargs.pop("phase", MutationPhase.LOCK),
            **kwargs,
        )


class MutationProtocolError(DurableMutationError):
    def __init__(
        self,
        message: str = "mutation protocol ordering violated",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            code=kwargs.pop("code", MutationErrorCode.PROTOCOL),
            phase=kwargs.pop("phase", None),
            **kwargs,
        )


class MutationEffectError(DurableMutationError):
    def __init__(
        self,
        message: str = "mutation effect failed",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            code=kwargs.pop("code", MutationErrorCode.EFFECT),
            phase=kwargs.pop("phase", MutationPhase.EFFECT),
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Path / content helpers
# ---------------------------------------------------------------------------


def _normalize_vfs_path(path: str) -> str:
    """Normalize a host path into the canonical VFS storage key form."""

    if path is None:
        raise MutationValidationError("path is required")
    if not isinstance(path, str):
        raise MutationValidationError("path must be a string")
    text = path.strip()
    if not text or text == "/":
        raise MutationValidationError("path must not be empty or root-only")
    if "\x00" in text:
        raise MutationValidationError("path must not contain NUL")
    # Strip leading/trailing slashes; reject ``.`` / ``..`` segments.
    parts = [p for p in text.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise MutationValidationError("path must not contain parent segments")
    if not parts:
        raise MutationValidationError("path must not be empty after normalization")
    normalized = "/".join(parts)
    if len(normalized.encode("utf-8")) > MAX_PATH_BYTES:
        raise MutationValidationError("path exceeds MAX_PATH_BYTES")
    return normalized


def path_to_ref(path: str) -> str:
    """Project a VFS path into a compact WAL path_ref identifier."""

    # Identifiers disallow whitespace; keep path separators and alnum.
    compact = path.replace("/", ".")
    return f"path:{compact}"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def _content_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _bounded_int(
    value: Any,
    field_name: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_SAFE_INTEGER,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MutationValidationError(f"{field_name} must be a finite integer")
    if value < minimum or value > maximum:
        raise MutationValidationError(f"{field_name} is outside supported bounds")
    return value


# ---------------------------------------------------------------------------
# Request / result / receipt records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MutationRequest:
    """One staged VFS mutation request admitted by the façade."""

    SCHEMA: ClassVar[str] = MUTATION_REQUEST_SCHEMA

    kind: MutationKind
    path: str
    target_path: str = ""
    content: bytes = b""
    offset: int = 0
    size: int = 0  # truncate size; write length when content empty
    exclusive: bool = True
    principal_id: str = ""
    operation_id: str = ""
    effect_id: str = ""
    transaction_id: str = ""
    generation_id: str = DEFAULT_GENERATION_ID
    preconditions: tuple[VFSWALPrecondition, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, MutationKind):
            object.__setattr__(self, "kind", MutationKind(self.kind))
        path = _normalize_vfs_path(self.path)
        object.__setattr__(self, "path", path)
        if self.kind is MutationKind.RENAME:
            if not self.target_path:
                raise MutationValidationError("rename requires target_path")
            object.__setattr__(
                self, "target_path", _normalize_vfs_path(self.target_path)
            )
        elif self.target_path:
            object.__setattr__(
                self, "target_path", _normalize_vfs_path(self.target_path)
            )
        if not isinstance(self.content, (bytes, bytearray)):
            raise MutationValidationError("content must be bytes")
        content = bytes(self.content)
        if len(content) > MAX_PAYLOAD_BYTES:
            raise MutationValidationError("content exceeds MAX_PAYLOAD_BYTES")
        object.__setattr__(self, "content", content)
        object.__setattr__(
            self, "offset", _bounded_int(self.offset, "offset", minimum=0)
        )
        object.__setattr__(
            self, "size", _bounded_int(self.size, "size", minimum=0)
        )
        if self.kind is MutationKind.TRUNCATE and self.size < 0:
            raise MutationValidationError("truncate size must be non-negative")
        if not isinstance(self.exclusive, bool):
            raise MutationValidationError("exclusive must be a boolean")
        if self.principal_id and any(c.isspace() for c in self.principal_id):
            raise MutationValidationError("principal_id must be compact")

    @property
    def lock_paths(self) -> tuple[str, ...]:
        if self.kind is MutationKind.RENAME:
            return tuple(
                sorted({self.path, self.target_path}, key=lambda p: p.encode("utf-8"))
            )
        return (self.path,)

    def intent_detail(
        self, *, prior_snapshots: Sequence[Mapping[str, Any]] | None = None
    ) -> dict[str, Any]:
        detail: dict[str, Any] = {
            "kind": self.kind.value,
            "path": self.path,
            "offset": self.offset,
            "size": self.size,
            "exclusive": self.exclusive,
            "content_digest": _content_digest(self.content) if self.content else "",
            "content_b64": _b64(self.content) if self.content else "",
            "content_len": len(self.content),
        }
        if self.target_path:
            detail["target_path"] = self.target_path
        if prior_snapshots:
            # Bounded prior-state evidence so recovery can compensate without
            # an in-memory effect ledger after process restart.
            detail["prior_snapshots"] = [dict(item) for item in prior_snapshots]
        return detail

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value,
            "path": self.path,
            "target_path": self.target_path,
            "content_len": len(self.content),
            "content_digest": _content_digest(self.content) if self.content else "",
            "offset": self.offset,
            "size": self.size,
            "exclusive": self.exclusive,
            "principal_id": self.principal_id,
            "operation_id": self.operation_id,
            "effect_id": self.effect_id,
            "transaction_id": self.transaction_id,
            "generation_id": self.generation_id,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class PartialEffectReceipt:
    """Exact partial-effect receipt for one mutation attempt.

    Never claims terminal success.  Lists applied and pending evidence ids so
    recovery can compensate precisely without inventing durability.
    """

    SCHEMA: ClassVar[str] = PARTIAL_EFFECT_RECEIPT_SCHEMA

    partial_id: str
    kind: PartialEffectKind
    effect_id: str
    transaction_id: str
    mutation_kind: MutationKind
    path: str
    applied_evidence_ids: tuple[str, ...] = ()
    pending_evidence_ids: tuple[str, ...] = ()
    compensation_required: bool = False
    compensation_evidence_id: str = ""
    description: str = ""
    state: OperationState = OperationState.PARTIAL_EFFECT
    backend_id: str = "backend:memory"
    target_path: str = ""
    prior_snapshot_digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PartialEffectKind):
            object.__setattr__(self, "kind", PartialEffectKind(self.kind))
        if not isinstance(self.mutation_kind, MutationKind):
            object.__setattr__(
                self, "mutation_kind", MutationKind(self.mutation_kind)
            )
        if not isinstance(self.state, OperationState):
            object.__setattr__(self, "state", OperationState(self.state))
        # Fail closed: partial receipts cannot claim committed/verified.
        if self.state in (
            OperationState.COMMITTED,
            OperationState.VERIFIED,
            OperationState.CONVERGED,
        ):
            raise MutationProtocolError(
                "partial-effect receipt cannot claim terminal success state",
                detail={"state": self.state.value},
            )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "partial_id": self.partial_id,
            "kind": self.kind.value,
            "effect_id": self.effect_id,
            "transaction_id": self.transaction_id,
            "mutation_kind": self.mutation_kind.value,
            "path": self.path,
            "target_path": self.target_path,
            "applied_evidence_ids": list(self.applied_evidence_ids),
            "pending_evidence_ids": list(self.pending_evidence_ids),
            "compensation_required": self.compensation_required,
            "compensation_evidence_id": self.compensation_evidence_id,
            "description": self.description,
            "state": self.state.value,
            "backend_id": self.backend_id,
            "prior_snapshot_digest": self.prior_snapshot_digest,
        }

    def to_partial_effect_record(self) -> PartialEffectRecord:
        """Project into the shared operation-contracts PartialEffectRecord."""

        return PartialEffectRecord(
            partial_id=self.partial_id,
            effect_kind=_MUTATION_TO_EFFECT_KIND[self.mutation_kind],
            state=self.state,
            description=self.description or self.kind.value,
            applied_evidence_ids=self.applied_evidence_ids,
            pending_evidence_ids=self.pending_evidence_ids,
            compensation_required=self.compensation_required,
            compensation_evidence_id=self.compensation_evidence_id,
            backend_id=self.backend_id,
        )


@dataclass(frozen=True)
class MutationPhaseStep:
    """One ordered protocol phase observation."""

    SCHEMA: ClassVar[str] = MUTATION_PHASE_TRACE_SCHEMA

    phase: MutationPhase
    success: bool
    seq: int
    effect_id: str = ""
    transaction_id: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "phase": self.phase.value,
            "success": self.success,
            "seq": self.seq,
            "effect_id": self.effect_id,
            "transaction_id": self.transaction_id,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class MutationResult:
    """Result of one durable mutation attempt."""

    SCHEMA: ClassVar[str] = MUTATION_RESULT_SCHEMA

    disposition: MutationDisposition
    kind: MutationKind
    path: str
    transaction_id: str
    operation_id: str
    effect_id: str
    committed: bool = False
    decision: VFSWALDecision = VFSWALDecision.REJECTED
    durable_ack: bool = False
    content_cid: str = ""
    version_cid: str = ""
    bytes_affected: int = 0
    target_path: str = ""
    phases: tuple[MutationPhaseStep, ...] = ()
    partial_receipts: tuple[PartialEffectReceipt, ...] = ()
    durable_data: VFSWALDurableData | None = None
    error_code: MutationErrorCode | None = None
    error_message: str = ""
    intent_durable: bool = False
    decision_durable: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "disposition": self.disposition.value,
            "kind": self.kind.value,
            "path": self.path,
            "target_path": self.target_path,
            "transaction_id": self.transaction_id,
            "operation_id": self.operation_id,
            "effect_id": self.effect_id,
            "committed": self.committed,
            "decision": self.decision.value,
            "durable_ack": self.durable_ack,
            "content_cid": self.content_cid,
            "version_cid": self.version_cid,
            "bytes_affected": self.bytes_affected,
            "phases": [p.to_record() for p in self.phases],
            "partial_receipts": [r.to_record() for r in self.partial_receipts],
            "error_code": self.error_code.value if self.error_code else "",
            "error_message": self.error_message,
            "intent_durable": self.intent_durable,
            "decision_durable": self.decision_durable,
            "durable_data_content_id": (
                self.durable_data.content_id if self.durable_data is not None else ""
            ),
        }


# ---------------------------------------------------------------------------
# Effect ledger (idempotent apply / compensate)
# ---------------------------------------------------------------------------


@dataclass
class _PathSnapshot:
    """Prior state of one path for compensation."""

    path: str
    existed: bool
    kind: str = VFSEntryKind.FILE.value
    content: bytes = b""
    content_cid: str = ""
    version_cid: str = ""
    target: str = ""
    mount_id: str = DEFAULT_MOUNT_ID

    def digest(self) -> str:
        preimage = {
            "path": self.path,
            "existed": self.existed,
            "kind": self.kind,
            "content_cid": self.content_cid or _content_digest(self.content),
            "version_cid": self.version_cid,
            "target": self.target,
            "size": len(self.content),
        }
        return "sha256:" + hashlib.sha256(
            json.dumps(preimage, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def to_intent_record(self, *, max_inline: int = 512) -> dict[str, Any]:
        """JSON-safe prior-state record embedded in durable intent.

        Large prior bodies are represented by content_cid only so intent_detail
        stays within WAL compactness bounds.
        """

        if self.content and len(self.content) <= max_inline:
            content_b64 = _b64(self.content)
        else:
            content_b64 = ""
        return {
            "path": self.path,
            "existed": self.existed,
            "kind": self.kind,
            "content_b64": content_b64,
            "content_len": len(self.content),
            "content_cid": self.content_cid or (
                _content_digest(self.content) if self.content else ""
            ),
            "version_cid": self.version_cid,
            "target": self.target,
            "mount_id": self.mount_id,
            "digest": self.digest(),
        }

    @classmethod
    def from_intent_record(cls, payload: Mapping[str, Any]) -> "_PathSnapshot":
        content_b64 = str(payload.get("content_b64") or "")
        content = _unb64(content_b64) if content_b64 else b""
        return cls(
            path=str(payload.get("path") or ""),
            existed=bool(payload.get("existed")),
            kind=str(payload.get("kind") or VFSEntryKind.FILE.value),
            content=content,
            content_cid=str(payload.get("content_cid") or ""),
            version_cid=str(payload.get("version_cid") or ""),
            target=str(payload.get("target") or ""),
            mount_id=str(payload.get("mount_id") or DEFAULT_MOUNT_ID),
        )


@dataclass
class _EffectLedgerEntry:
    """One applied effect with exact prior-state evidence for compensation."""

    SCHEMA: ClassVar[str] = EFFECT_LEDGER_SCHEMA

    effect_id: str
    kind: MutationKind
    path: str
    target_path: str
    snapshots: tuple[_PathSnapshot, ...]
    applied_evidence_ids: tuple[str, ...]
    content_cid: str = ""
    version_cid: str = ""
    bytes_affected: int = 0
    apply_count: int = 1
    compensate_count: int = 0
    compensated: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "effect_id": self.effect_id,
            "kind": self.kind.value,
            "path": self.path,
            "target_path": self.target_path,
            "applied_evidence_ids": list(self.applied_evidence_ids),
            "content_cid": self.content_cid,
            "version_cid": self.version_cid,
            "bytes_affected": self.bytes_affected,
            "apply_count": self.apply_count,
            "compensate_count": self.compensate_count,
            "compensated": self.compensated,
            "snapshot_digests": [s.digest() for s in self.snapshots],
        }


class MutationEffectBackend:
    """Idempotent apply/compensate backend over CanonicalVFSService storage.

    Each ``effect_id`` is an idempotency key: re-applying a recorded effect is a
    no-op that returns an ``IDEMPOTENT_REPLAY`` receipt; re-compensating a
    already-compensated effect is a no-op that returns
    ``IDEMPOTENT_COMPENSATE``.
    """

    def __init__(
        self,
        service: CanonicalVFSService | None = None,
        *,
        storage: InMemoryVFSStorage | None = None,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._storage = storage or InMemoryVFSStorage()
        self._service = service or CanonicalVFSService(
            storage=self._storage, clock=clock or (lambda: 0)
        )
        self._lock = threading.RLock()
        self._ledger: dict[str, _EffectLedgerEntry] = {}
        self._seq = 0

    @property
    def service(self) -> CanonicalVFSService:
        return self._service

    @property
    def storage(self) -> InMemoryVFSStorage:
        return self._storage

    def ledger_record(self, effect_id: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._ledger.get(effect_id)
            return entry.to_record() if entry is not None else None

    def is_applied(self, effect_id: str) -> bool:
        with self._lock:
            entry = self._ledger.get(effect_id)
            return entry is not None and not entry.compensated

    def snapshot_path(self, path: str) -> _PathSnapshot:
        entry = self._storage.get(path)
        if entry is None:
            return _PathSnapshot(path=path, existed=False)
        return _PathSnapshot(
            path=path,
            existed=True,
            kind=entry.kind.value,
            content=bytes(entry.content),
            content_cid=entry.content_cid,
            version_cid=entry.version_cid,
            target=entry.target,
            mount_id=entry.mount_id,
        )

    def _restore_snapshot(self, snap: _PathSnapshot) -> None:
        if not snap.existed:
            if self._storage.get(snap.path) is not None:
                self._storage.delete(snap.path)
            return
        kind = VFSEntryKind(snap.kind)
        content = bytes(snap.content)
        content_cid = snap.content_cid or content_cid_for_bytes(content)
        gen = self._storage.bump_generation()
        version = snap.version_cid or version_cid_for(
            snap.path,
            kind=kind,
            content_cid=content_cid,
            generation=gen,
            target=snap.target,
        )
        self._ensure_parents(snap.path)
        self._storage.put(
            snap.path,
            VFSStoredEntry(
                kind=kind,
                content=content if kind is VFSEntryKind.FILE else b"",
                content_cid=content_cid,
                version_cid=version,
                target=snap.target,
                mount_id=snap.mount_id or DEFAULT_MOUNT_ID,
            ),
        )

    def _ensure_parents(self, path: str) -> None:
        """Materialize missing parent directories for nested mutation paths."""

        if not path or "/" not in path:
            return
        parts = path.split("/")
        acc: list[str] = []
        for part in parts[:-1]:
            acc.append(part)
            parent = "/".join(acc)
            existing = self._storage.get(parent)
            if existing is None:
                gen = self._storage.bump_generation()
                cid = content_cid_for_bytes(b"")
                self._storage.put(
                    parent,
                    VFSStoredEntry(
                        kind=VFSEntryKind.DIRECTORY,
                        content=b"",
                        content_cid=cid,
                        version_cid=version_cid_for(
                            parent,
                            kind=VFSEntryKind.DIRECTORY,
                            content_cid=cid,
                            generation=gen,
                        ),
                        mount_id=DEFAULT_MOUNT_ID,
                    ),
                )
            elif existing.kind is not VFSEntryKind.DIRECTORY:
                raise MutationEffectError(
                    f"parent path is not a directory: {parent}",
                    code=MutationErrorCode.CONFLICT,
                )

    def apply(
        self, request: MutationRequest, *, effect_id: str
    ) -> tuple[dict[str, Any], PartialEffectReceipt | None]:
        """Apply ``request`` under ``effect_id`` idempotently.

        Returns ``(effect_meta, optional_idempotent_receipt)``.
        """

        with self._lock:
            existing = self._ledger.get(effect_id)
            if existing is not None and not existing.compensated:
                existing.apply_count += 1
                receipt = PartialEffectReceipt(
                    partial_id=f"partial:replay:{effect_id}:{existing.apply_count}",
                    kind=PartialEffectKind.IDEMPOTENT_REPLAY,
                    effect_id=effect_id,
                    transaction_id=request.transaction_id or "",
                    mutation_kind=request.kind,
                    path=request.path,
                    target_path=request.target_path,
                    applied_evidence_ids=existing.applied_evidence_ids,
                    pending_evidence_ids=(),
                    compensation_required=False,
                    description=(
                        f"idempotent re-apply of {request.kind.value} "
                        f"effect {effect_id}"
                    ),
                    state=OperationState.PROCESSING,
                    prior_snapshot_digest=(
                        existing.snapshots[0].digest() if existing.snapshots else ""
                    ),
                )
                return (
                    {
                        "content_cid": existing.content_cid,
                        "version_cid": existing.version_cid,
                        "bytes_affected": existing.bytes_affected,
                        "idempotent": True,
                    },
                    receipt,
                )

            # Capture prior state for exact compensation.
            paths = list(request.lock_paths)
            snapshots = tuple(self.snapshot_path(p) for p in paths)
            prior_digest = snapshots[0].digest() if snapshots else ""

            applied_ids: list[str] = []
            content_cid = ""
            version_cid = ""
            bytes_affected = 0

            try:
                if request.kind is MutationKind.CREATE:
                    content_cid, version_cid, bytes_affected, applied_ids = (
                        self._apply_create(request, effect_id)
                    )
                elif request.kind is MutationKind.WRITE:
                    content_cid, version_cid, bytes_affected, applied_ids = (
                        self._apply_write(request, effect_id)
                    )
                elif request.kind is MutationKind.TRUNCATE:
                    content_cid, version_cid, bytes_affected, applied_ids = (
                        self._apply_truncate(request, effect_id)
                    )
                elif request.kind is MutationKind.UNLINK:
                    content_cid, version_cid, bytes_affected, applied_ids = (
                        self._apply_unlink(request, effect_id)
                    )
                elif request.kind is MutationKind.RENAME:
                    content_cid, version_cid, bytes_affected, applied_ids = (
                        self._apply_rename(request, effect_id)
                    )
                else:  # pragma: no cover - closed enum
                    raise MutationEffectError(f"unsupported mutation kind: {request.kind}")
            except Exception as exc:
                # Mid-apply failure: restore any partial changes and emit exact receipt.
                for snap in snapshots:
                    self._restore_snapshot(snap)
                raise MutationEffectError(
                    f"effect {effect_id} failed mid-apply: {exc}",
                    detail={
                        "effect_id": effect_id,
                        "kind": request.kind.value,
                        "path": request.path,
                        "prior_snapshot_digest": prior_digest,
                        "partial_kind": PartialEffectKind.EFFECT_FAILED_MID_APPLY.value,
                    },
                ) from exc

            entry = _EffectLedgerEntry(
                effect_id=effect_id,
                kind=request.kind,
                path=request.path,
                target_path=request.target_path,
                snapshots=snapshots,
                applied_evidence_ids=tuple(applied_ids),
                content_cid=content_cid,
                version_cid=version_cid,
                bytes_affected=bytes_affected,
            )
            if len(self._ledger) >= MAX_EFFECT_LEDGER and effect_id not in self._ledger:
                # Drop compensated entries first.
                for key, val in list(self._ledger.items()):
                    if val.compensated:
                        del self._ledger[key]
                        if len(self._ledger) < MAX_EFFECT_LEDGER:
                            break
            self._ledger[effect_id] = entry
            return (
                {
                    "content_cid": content_cid,
                    "version_cid": version_cid,
                    "bytes_affected": bytes_affected,
                    "idempotent": False,
                    "applied_evidence_ids": tuple(applied_ids),
                    "prior_snapshot_digest": prior_digest,
                },
                None,
            )

    def compensate(
        self,
        effect_id: str,
        *,
        transaction_id: str = "",
        request: MutationRequest | None = None,
        prior_snapshots: Sequence[_PathSnapshot] | None = None,
    ) -> PartialEffectReceipt:
        """Compensate a previously applied effect (idempotent).

        After process restart the in-memory ledger may be empty.  Callers may
        supply ``prior_snapshots`` reconstructed from durable intent so
        compensation remains exact.
        """

        with self._lock:
            entry = self._ledger.get(effect_id)
            if entry is not None and entry.compensated:
                entry.compensate_count += 1
                return PartialEffectReceipt(
                    partial_id=f"partial:idempotent-compensate:{effect_id}",
                    kind=PartialEffectKind.IDEMPOTENT_COMPENSATE,
                    effect_id=effect_id,
                    transaction_id=transaction_id,
                    mutation_kind=entry.kind,
                    path=entry.path,
                    target_path=entry.target_path,
                    applied_evidence_ids=(),
                    pending_evidence_ids=(),
                    compensation_required=False,
                    compensation_evidence_id=f"compensate:{effect_id}:noop",
                    description=f"idempotent re-compensate of effect {effect_id}",
                    state=OperationState.PROCESSING,
                )

            snapshots: tuple[_PathSnapshot, ...]
            kind: MutationKind
            path: str
            target: str
            applied_ids: tuple[str, ...]

            if entry is not None:
                snapshots = entry.snapshots
                kind = entry.kind
                path = entry.path
                target = entry.target_path
                applied_ids = entry.applied_evidence_ids
            elif prior_snapshots:
                snapshots = tuple(prior_snapshots)
                kind = request.kind if request is not None else MutationKind.WRITE
                path = request.path if request is not None else (
                    snapshots[0].path if snapshots else "unknown"
                )
                target = request.target_path if request is not None else ""
                applied_ids = (f"apply:recovered:{effect_id}",)
            elif request is not None:
                # Intent-only or effect never made durable prior state: derive
                # a best-effort reverse from the mutation kind.
                snapshots = self._inferred_compensate_snapshots(request)
                kind = request.kind
                path = request.path
                target = request.target_path
                applied_ids = ()
                # If storage already matches pre-image (effect never applied),
                # this is an idempotent no-op.
                if self._already_at_snapshots(snapshots):
                    return PartialEffectReceipt(
                        partial_id=f"partial:idempotent-compensate:{effect_id}",
                        kind=PartialEffectKind.IDEMPOTENT_COMPENSATE,
                        effect_id=effect_id,
                        transaction_id=transaction_id,
                        mutation_kind=kind,
                        path=path,
                        target_path=target,
                        compensation_required=False,
                        compensation_evidence_id=f"compensate:{effect_id}:noop",
                        description=(
                            f"idempotent re-compensate of effect {effect_id} "
                            "(storage already at prior state)"
                        ),
                        state=OperationState.PROCESSING,
                    )
            else:
                return PartialEffectReceipt(
                    partial_id=f"partial:idempotent-compensate:{effect_id}",
                    kind=PartialEffectKind.IDEMPOTENT_COMPENSATE,
                    effect_id=effect_id,
                    transaction_id=transaction_id,
                    mutation_kind=MutationKind.WRITE,
                    path="unknown",
                    compensation_required=False,
                    compensation_evidence_id=f"compensate:{effect_id}:noop",
                    description=f"idempotent re-compensate of unknown effect {effect_id}",
                    state=OperationState.PROCESSING,
                )

            # Restore prior snapshots in reverse path order for rename safety.
            for snap in reversed(snapshots):
                self._restore_snapshot(snap)

            if entry is not None:
                entry.compensated = True
                entry.compensate_count += 1
                count = entry.compensate_count
            else:
                # Record compensated ledger entry so subsequent recovers no-op.
                self._ledger[effect_id] = _EffectLedgerEntry(
                    effect_id=effect_id,
                    kind=kind,
                    path=path,
                    target_path=target,
                    snapshots=snapshots,
                    applied_evidence_ids=applied_ids,
                    compensate_count=1,
                    compensated=True,
                )
                count = 1

            evidence = f"compensate:{effect_id}:{count}"
            return PartialEffectReceipt(
                partial_id=f"partial:compensated:{effect_id}",
                kind=PartialEffectKind.COMPENSATION_APPLIED,
                effect_id=effect_id,
                transaction_id=transaction_id,
                mutation_kind=kind,
                path=path,
                target_path=target,
                applied_evidence_ids=applied_ids,
                pending_evidence_ids=(),
                compensation_required=False,
                compensation_evidence_id=evidence,
                description=f"compensated {kind.value} effect {effect_id}",
                state=OperationState.FAILED,
                prior_snapshot_digest=(snapshots[0].digest() if snapshots else ""),
            )

    def _already_at_snapshots(self, snapshots: Sequence[_PathSnapshot]) -> bool:
        for snap in snapshots:
            current = self.snapshot_path(snap.path)
            if current.existed != snap.existed:
                return False
            if snap.existed and current.content != snap.content:
                return False
        return True

    def _inferred_compensate_snapshots(
        self, request: MutationRequest
    ) -> tuple[_PathSnapshot, ...]:
        """Infer reverse snapshots when durable prior state is unavailable.

        Used only as a last resort; prefer intent-embedded prior_snapshots.
        """

        if request.kind is MutationKind.CREATE:
            return (_PathSnapshot(path=request.path, existed=False),)
        if request.kind is MutationKind.UNLINK:
            # Without prior bytes we cannot resurrect content; leave tombstone
            # reverse as "existed with empty" only if currently missing.
            return (
                _PathSnapshot(
                    path=request.path,
                    existed=True,
                    content=request.content,
                    content_cid=_content_digest(request.content)
                    if request.content
                    else "",
                ),
            )
        if request.kind is MutationKind.RENAME:
            return (
                _PathSnapshot(path=request.path, existed=True, content=request.content),
                _PathSnapshot(path=request.target_path, existed=False),
            )
        # write / truncate: restore is incomplete without prior; no-op markers.
        return (self.snapshot_path(request.path),)

    # -- per-kind apply -----------------------------------------------------

    def _apply_create(
        self, request: MutationRequest, effect_id: str
    ) -> tuple[str, str, int, list[str]]:
        self._ensure_parents(request.path)
        existing = self._storage.get(request.path)
        payload = request.content
        # Recovery / replay: path already holding the intended bytes is an
        # idempotent success even when the in-memory ledger was lost.
        if existing is not None and bytes(existing.content) == payload:
            evidence = [
                f"apply:create:{effect_id}",
                f"path:{request.path}",
                "idempotent:content-match",
            ]
            return existing.content_cid, existing.version_cid, len(payload), evidence
        if existing is not None and request.exclusive:
            raise MutationEffectError(
                f"create target already exists: {request.path}",
                code=MutationErrorCode.ALREADY_EXISTS,
            )
        if existing is not None:
            op_kind = VFSOperationKind.REPLACE
        else:
            op_kind = VFSOperationKind.CREATE
        outcome = self._service.execute(
            make_op(
                op_kind,
                operation_id=request.operation_id or f"op:{effect_id}",
                path=request.path,
                idempotency_key=effect_id,
            ),
            VFSExecuteRequest(payload=payload),
        )
        if not outcome.success:
            raise MutationEffectError(
                f"create failed: {outcome.result.error}",
                detail={"path": request.path},
            )
        entry = self._storage.get(request.path)
        assert entry is not None
        evidence = [f"apply:create:{effect_id}", f"path:{request.path}"]
        return entry.content_cid, entry.version_cid, len(payload), evidence

    def _apply_write(
        self, request: MutationRequest, effect_id: str
    ) -> tuple[str, str, int, list[str]]:
        self._ensure_parents(request.path)
        existing = self._storage.get(request.path)
        if existing is None:
            # Implicit create on write when the path is absent.
            base = b""
            was_create = True
        else:
            if existing.kind is not VFSEntryKind.FILE:
                raise MutationEffectError(
                    f"write target is not a file: {request.path}",
                    code=MutationErrorCode.CONFLICT,
                )
            base = bytes(existing.content)
            was_create = False
        offset = request.offset
        data = request.content
        if offset > len(base):
            # Sparse hole: pad with zeroes (exact partial extent semantics).
            base = base + (b"\x00" * (offset - len(base)))
        end = offset + len(data)
        new_content = base[:offset] + data + base[end:]
        op_kind = VFSOperationKind.CREATE if was_create else VFSOperationKind.REPLACE
        outcome = self._service.execute(
            make_op(
                op_kind,
                operation_id=request.operation_id or f"op:{effect_id}",
                path=request.path,
                idempotency_key=effect_id,
            ),
            VFSExecuteRequest(payload=new_content),
        )
        if not outcome.success:
            raise MutationEffectError(
                f"write failed: {outcome.result.error}",
                detail={"path": request.path, "offset": offset},
            )
        entry = self._storage.get(request.path)
        assert entry is not None
        evidence = [
            f"apply:write:{effect_id}",
            f"path:{request.path}",
            f"offset:{offset}",
            f"length:{len(data)}",
        ]
        return entry.content_cid, entry.version_cid, len(data), evidence

    def _apply_truncate(
        self, request: MutationRequest, effect_id: str
    ) -> tuple[str, str, int, list[str]]:
        existing = self._storage.get(request.path)
        if existing is None:
            raise MutationEffectError(
                f"truncate target missing: {request.path}",
                code=MutationErrorCode.NOT_FOUND,
            )
        if existing.kind is not VFSEntryKind.FILE:
            raise MutationEffectError(
                f"truncate target is not a file: {request.path}",
                code=MutationErrorCode.CONFLICT,
            )
        size = request.size
        current = bytes(existing.content)
        if size < len(current):
            new_content = current[:size]
        elif size > len(current):
            new_content = current + (b"\x00" * (size - len(current)))
        else:
            new_content = current
        outcome = self._service.execute(
            make_op(
                VFSOperationKind.REPLACE,
                operation_id=request.operation_id or f"op:{effect_id}",
                path=request.path,
                idempotency_key=effect_id,
            ),
            VFSExecuteRequest(payload=new_content),
        )
        if not outcome.success:
            raise MutationEffectError(
                f"truncate failed: {outcome.result.error}",
                detail={"path": request.path, "size": size},
            )
        entry = self._storage.get(request.path)
        assert entry is not None
        evidence = [
            f"apply:truncate:{effect_id}",
            f"path:{request.path}",
            f"size:{size}",
        ]
        return entry.content_cid, entry.version_cid, size, evidence

    def _apply_unlink(
        self, request: MutationRequest, effect_id: str
    ) -> tuple[str, str, int, list[str]]:
        existing = self._storage.get(request.path)
        if existing is None:
            # Already unlinked — idempotent recovery success.
            evidence = [
                f"apply:unlink:{effect_id}",
                f"path:{request.path}",
                "idempotent:already-absent",
            ]
            return "", "", 0, evidence
        prior_cid = existing.content_cid
        prior_ver = existing.version_cid
        prior_size = len(existing.content)
        outcome = self._service.execute(
            make_op(
                VFSOperationKind.DELETE,
                operation_id=request.operation_id or f"op:{effect_id}",
                path=request.path,
                idempotency_key=effect_id,
            )
        )
        if not outcome.success:
            raise MutationEffectError(
                f"unlink failed: {outcome.result.error}",
                detail={"path": request.path},
            )
        evidence = [f"apply:unlink:{effect_id}", f"path:{request.path}"]
        return prior_cid, prior_ver, prior_size, evidence

    def _apply_rename(
        self, request: MutationRequest, effect_id: str
    ) -> tuple[str, str, int, list[str]]:
        self._ensure_parents(request.target_path)
        source = self._storage.get(request.path)
        target = self._storage.get(request.target_path)
        if source is None and target is not None:
            # Already renamed — idempotent recovery success.
            evidence = [
                f"apply:rename:{effect_id}",
                f"path:{request.path}",
                f"target:{request.target_path}",
                "idempotent:already-renamed",
            ]
            return target.content_cid, target.version_cid, len(target.content), evidence
        if source is None:
            raise MutationEffectError(
                f"rename source missing: {request.path}",
                code=MutationErrorCode.NOT_FOUND,
            )
        outcome = self._service.execute(
            make_op(
                VFSOperationKind.RENAME,
                operation_id=request.operation_id or f"op:{effect_id}",
                path=request.path,
                source_path=request.path,
                target_path=request.target_path,
                idempotency_key=effect_id,
            )
        )
        if not outcome.success:
            raise MutationEffectError(
                f"rename failed: {outcome.result.error}",
                detail={
                    "path": request.path,
                    "target_path": request.target_path,
                },
            )
        entry = self._storage.get(request.target_path)
        content_cid = entry.content_cid if entry is not None else source.content_cid
        version_cid = entry.version_cid if entry is not None else source.version_cid
        evidence = [
            f"apply:rename:{effect_id}",
            f"path:{request.path}",
            f"target:{request.target_path}",
        ]
        return content_cid, version_cid, len(source.content), evidence


# ---------------------------------------------------------------------------
# Phase trace
# ---------------------------------------------------------------------------


class MutationPhaseTrace:
    """Bounded ordered phase log used to prove protocol ordering."""

    def __init__(self, *, max_steps: int = MAX_TRACE_STEPS) -> None:
        self._max = max(1, int(max_steps))
        self._steps: list[MutationPhaseStep] = []
        self._seq = 0
        self._lock = threading.Lock()

    def record(
        self,
        phase: MutationPhase,
        *,
        success: bool = True,
        effect_id: str = "",
        transaction_id: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> MutationPhaseStep:
        with self._lock:
            self._seq += 1
            step = MutationPhaseStep(
                phase=phase,
                success=success,
                seq=self._seq,
                effect_id=effect_id,
                transaction_id=transaction_id,
                detail=dict(detail or {}),
            )
            self._steps.append(step)
            if len(self._steps) > self._max:
                self._steps = self._steps[-self._max :]
            return step

    def steps(self) -> tuple[MutationPhaseStep, ...]:
        with self._lock:
            return tuple(self._steps)

    def phases(self) -> list[str]:
        return [s.phase.value for s in self.steps()]

    def clear(self) -> None:
        with self._lock:
            self._steps.clear()
            self._seq = 0

    def assert_pre_intent_order(self) -> None:
        """Fail closed if validate/authorize/lock did not precede intent."""

        phases = self.phases()
        if MutationPhase.INTENT.value not in phases:
            return
        intent_idx = phases.index(MutationPhase.INTENT.value)
        for required in _PRE_INTENT_PHASE_VALUES:
            if required.value not in phases[:intent_idx]:
                raise MutationProtocolError(
                    f"{required.value} must precede durable intent",
                    detail={"phases": phases},
                )
            if phases.index(required.value) >= intent_idx:
                raise MutationProtocolError(
                    f"{required.value} must precede durable intent",
                    detail={"phases": phases},
                )


# ---------------------------------------------------------------------------
# Durable mutation façade / coordinator
# ---------------------------------------------------------------------------


AuthorizePredicate = Callable[[MutationRequest], bool]
CrashInjector = Callable[..., Any]


class DurableMutationCoordinator:
    """Mutation ordering façade bound to :class:`WALTransactionCoordinator`.

    Production entry point for staged VFS mutations that must observe the
    durable intent/effect/decision protocol.
    """

    SCHEMA: ClassVar[str] = DURABLE_MUTATION_COORDINATOR_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION

    CRASH_BOUNDARIES: Final[tuple[str, ...]] = (
        "before_validate",
        "after_validate",
        "before_authorize",
        "after_authorize",
        "before_lock",
        "after_lock",
        "before_intent",
        "after_intent",
        "before_effect",
        "after_effect",
        "before_decision",
        "after_decision",
        "before_ack",
        "after_ack",
    )

    def __init__(
        self,
        directory: str | Path,
        *,
        wal: WALTransactionCoordinator | None = None,
        backend: MutationEffectBackend | None = None,
        locks: HostLockManager | None = None,
        authorize: AuthorizePredicate | None = None,
        crash_injector: CrashInjector | None = None,
        generation_id: str = DEFAULT_GENERATION_ID,
        require_intent_durability: bool = True,
    ) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._owns_wal = wal is None
        # Façade owns named crash boundaries (validate/authorize/lock/intent/
        # effect/decision/ack).  The WAL coordinator is left without a crash
        # injector so boundaries are not double-fired.
        self._wal = wal or WALTransactionCoordinator(self.directory / "wal")
        self._backend = backend or MutationEffectBackend()
        self._locks = locks or HostLockManager()
        self._authorize = authorize or (lambda _req: True)
        self._crash_injector = crash_injector
        self._generation_id = generation_id
        self._require_intent_durability = require_intent_durability
        self._trace = MutationPhaseTrace()
        self._lock = threading.RLock()
        self._partial_receipts: list[PartialEffectReceipt] = []
        self._last_result: MutationResult | None = None
        self._active_transaction_id: str = ""
        self._active_effect_id: str = ""

    # -- properties ---------------------------------------------------------

    @property
    def wal(self) -> WALTransactionCoordinator:
        return self._wal

    @property
    def backend(self) -> MutationEffectBackend:
        return self._backend

    @property
    def locks(self) -> HostLockManager:
        return self._locks

    @property
    def trace(self) -> MutationPhaseTrace:
        return self._trace

    @property
    def partial_receipts(self) -> tuple[PartialEffectReceipt, ...]:
        with self._lock:
            return tuple(self._partial_receipts)

    @property
    def last_result(self) -> MutationResult | None:
        return self._last_result

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        if self._owns_wal:
            self._wal.close()

    def __enter__(self) -> "DurableMutationCoordinator":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # -- crash injection ----------------------------------------------------

    def _boundary(self, name: str, transaction_id: str) -> None:
        if self._crash_injector is None:
            return
        try:
            self._crash_injector(name, transaction_id)
        except TypeError:
            self._crash_injector(name)

    # -- authorization / validation / locks ---------------------------------

    def _validate(self, request: MutationRequest) -> MutationRequest:
        # Construction already validates shape; re-check closed kind set.
        if not isinstance(request.kind, MutationKind):
            raise MutationValidationError(f"unsupported mutation kind: {request.kind}")
        if request.kind is MutationKind.RENAME and request.path == request.target_path:
            raise MutationValidationError("rename source and target must differ")
        if request.kind is MutationKind.WRITE and not request.content and request.size:
            # size-only write without content is invalid (use truncate).
            raise MutationValidationError(
                "write requires content bytes; use truncate to change size only"
            )
        return request

    def _check_authorize(self, request: MutationRequest) -> None:
        try:
            allowed = bool(self._authorize(request))
        except DurableMutationError:
            raise
        except Exception as exc:
            raise MutationAuthorizationError(
                f"authorize predicate failed: {exc}",
                detail={"path": request.path, "kind": request.kind.value},
            ) from exc
        if not allowed:
            raise MutationAuthorizationError(
                f"principal not authorized for {request.kind.value} on {request.path}",
                detail={
                    "path": request.path,
                    "kind": request.kind.value,
                    "principal_id": request.principal_id,
                },
            )

    def _acquire_locks(self, request: MutationRequest, owner_id: str) -> tuple[str, ...]:
        reqs = [
            HostLockRequest(HostLockKey.for_path(p), LockMode.EXCLUSIVE)
            for p in request.lock_paths
        ]
        try:
            ordered = ordered_lock_requests(reqs)
            acquired = self._locks.acquire(owner_id, ordered, nonblocking=True)
            return tuple(str(k) for k in acquired)
        except DurableMutationError:
            raise
        except Exception as exc:
            raise MutationLockError(
                f"failed to acquire path locks: {exc}",
                detail={"paths": list(request.lock_paths), "owner_id": owner_id},
            ) from exc

    def _release_locks(self, owner_id: str) -> None:
        try:
            self._locks.release_all(owner_id)
        except Exception:
            pass

    # -- durable data construction ------------------------------------------

    def _build_content(self, request: MutationRequest) -> VFSWALContent:
        if not request.content:
            return VFSWALContent.empty()
        # Prefer staged reference for large bodies; inline for small UTF-8-safe.
        if len(request.content) > 512:
            return VFSWALContent.staged(
                _content_digest(request.content),
                size_bytes=len(request.content),
                media_type="application/octet-stream",
                staging_path_ref=f"stage:{path_to_ref(request.path)}",
            )
        # Inline as base64 text so binary-safe and bounded.
        return VFSWALContent.inline(
            _b64(request.content),
            media_type="application/vnd.ipfs-kit.b64-payload",
        )

    def _build_durable_data(
        self,
        request: MutationRequest,
        *,
        transaction_id: str,
        operation_id: str,
        effect_id: str,
        decision: VFSWALDecision,
        acknowledgement: VFSWALAcknowledgement | None = None,
    ) -> VFSWALDurableData:
        content = self._build_content(request)
        detail = request.intent_detail()
        return make_durable_data(
            transaction_id=transaction_id,
            operation_id=operation_id,
            effect_id=effect_id,
            intent=_MUTATION_TO_WAL_INTENT[request.kind],
            content=content,
            preconditions=request.preconditions,
            decision=decision,
            acknowledgement=acknowledgement,
            intent_detail=detail,
            path_ref=path_to_ref(request.path),
            target_path_ref=(
                path_to_ref(request.target_path) if request.target_path else ""
            ),
            generation_id=request.generation_id or self._generation_id,
            principal_id=request.principal_id or "",
            notes=request.notes or f"kvfs-309:{request.kind.value}",
        )

    def _capture_prior_snapshots(
        self, request: MutationRequest
    ) -> tuple[_PathSnapshot, ...]:
        return tuple(
            self._backend.snapshot_path(path) for path in request.lock_paths
        )

    def _intent_mapping(
        self,
        request: MutationRequest,
        *,
        transaction_id: str,
        operation_id: str,
        effect_id: str,
        prior_snapshots: Sequence[_PathSnapshot] = (),
    ) -> dict[str, Any]:
        prior_records = [snap.to_intent_record() for snap in prior_snapshots]
        # Rebuild durable data with prior snapshots embedded in intent_detail.
        content = self._build_content(request)
        detail = request.intent_detail(prior_snapshots=prior_records)
        durable = make_durable_data(
            transaction_id=transaction_id,
            operation_id=operation_id,
            effect_id=effect_id,
            intent=_MUTATION_TO_WAL_INTENT[request.kind],
            content=content,
            preconditions=request.preconditions,
            decision=VFSWALDecision.INTENT_RECORDED,
            intent_detail=detail,
            path_ref=path_to_ref(request.path),
            target_path_ref=(
                path_to_ref(request.target_path) if request.target_path else ""
            ),
            generation_id=request.generation_id or self._generation_id,
            principal_id=request.principal_id or "",
            notes=request.notes or f"kvfs-309:{request.kind.value}",
        )
        # Compact JSON-serialisable intent for the WAL coordinator.
        return {
            "schema": getattr(VFSWALDurableData, "SCHEMA", ""),
            "transaction_id": transaction_id,
            "operation_id": operation_id,
            "effect_id": effect_id,
            "intent": durable.intent.value,
            "path": request.path,
            "target_path": request.target_path,
            "path_ref": durable.path_ref,
            "target_path_ref": durable.target_path_ref,
            "checksum": durable.checksum,
            "content": durable.content._payload(),
            "intent_detail": durable.intent_detail,
            "decision": VFSWALDecision.INTENT_RECORDED.value,
            "generation_id": durable.generation_id,
            "principal_id": durable.principal_id,
            "kind": request.kind.value,
            "prior_snapshots": prior_records,
        }

    # -- partial receipt bookkeeping ----------------------------------------

    def _remember_partial(self, receipt: PartialEffectReceipt) -> PartialEffectReceipt:
        with self._lock:
            self._partial_receipts.append(receipt)
            if len(self._partial_receipts) > MAX_PARTIAL_RECEIPTS:
                self._partial_receipts = self._partial_receipts[-MAX_PARTIAL_RECEIPTS:]
        return receipt

    # -- public mutation API ------------------------------------------------

    def mutate(self, request: MutationRequest) -> MutationResult:
        """Execute one mutation under the durable ordering protocol.

        Committed acknowledgement is returned only after decision and effect
        identity are durable.  Pre-intent failures never record intent.
        """

        with self._lock:
            return self._mutate_locked(request)

    def _mutate_locked(self, request: MutationRequest) -> MutationResult:
        self._trace.clear()
        transaction_id = request.transaction_id or f"txn:{uuid.uuid4().hex}"
        operation_id = request.operation_id or f"op:{uuid.uuid4().hex}"
        effect_id = request.effect_id or f"effect:{uuid.uuid4().hex}"
        owner_id = f"mutation:{transaction_id}"
        self._active_transaction_id = transaction_id
        self._active_effect_id = effect_id

        phases: list[MutationPhaseStep] = []
        partials: list[PartialEffectReceipt] = []
        intent_durable = False
        decision_durable = False
        locks_held = False
        wal_begun = False
        effect_applied = False
        content_cid = ""
        version_cid = ""
        bytes_affected = 0
        durable_data: VFSWALDurableData | None = None

        def step(
            phase: MutationPhase,
            *,
            success: bool = True,
            detail: Mapping[str, Any] | None = None,
        ) -> MutationPhaseStep:
            recorded = self._trace.record(
                phase,
                success=success,
                effect_id=effect_id,
                transaction_id=transaction_id,
                detail=detail,
            )
            phases.append(recorded)
            return recorded

        def finish(
            *,
            disposition: MutationDisposition,
            committed: bool,
            decision: VFSWALDecision,
            durable_ack: bool = False,
            error_code: MutationErrorCode | None = None,
            error_message: str = "",
        ) -> MutationResult:
            result = MutationResult(
                disposition=disposition,
                kind=request.kind,
                path=request.path,
                target_path=request.target_path,
                transaction_id=transaction_id,
                operation_id=operation_id,
                effect_id=effect_id,
                committed=committed,
                decision=decision,
                durable_ack=durable_ack,
                content_cid=content_cid,
                version_cid=version_cid,
                bytes_affected=bytes_affected,
                phases=tuple(phases),
                partial_receipts=tuple(partials),
                durable_data=durable_data,
                error_code=error_code,
                error_message=error_message,
                intent_durable=intent_durable,
                decision_durable=decision_durable,
            )
            self._last_result = result
            return result

        try:
            # ---- VALIDATE -------------------------------------------------
            self._boundary("before_validate", transaction_id)
            try:
                request = self._validate(request)
                # Rebind identity fields after validation.
                request = MutationRequest(
                    kind=request.kind,
                    path=request.path,
                    target_path=request.target_path,
                    content=request.content,
                    offset=request.offset,
                    size=request.size,
                    exclusive=request.exclusive,
                    principal_id=request.principal_id,
                    operation_id=operation_id,
                    effect_id=effect_id,
                    transaction_id=transaction_id,
                    generation_id=request.generation_id or self._generation_id,
                    preconditions=request.preconditions,
                    notes=request.notes,
                )
            except DurableMutationError as exc:
                step(MutationPhase.VALIDATE, success=False, detail={"error": str(exc)})
                step(MutationPhase.REJECT, success=True, detail={"reason": "validation"})
                return finish(
                    disposition=MutationDisposition.REJECTED,
                    committed=False,
                    decision=VFSWALDecision.REJECTED,
                    error_code=exc.code,
                    error_message=exc.message,
                )
            step(MutationPhase.VALIDATE, success=True)
            self._boundary("after_validate", transaction_id)

            # ---- AUTHORIZE ------------------------------------------------
            self._boundary("before_authorize", transaction_id)
            try:
                self._check_authorize(request)
            except DurableMutationError as exc:
                step(MutationPhase.AUTHORIZE, success=False, detail={"error": str(exc)})
                step(MutationPhase.REJECT, success=True, detail={"reason": "authorize"})
                return finish(
                    disposition=MutationDisposition.REJECTED,
                    committed=False,
                    decision=VFSWALDecision.REJECTED,
                    error_code=exc.code,
                    error_message=exc.message,
                )
            step(MutationPhase.AUTHORIZE, success=True)
            self._boundary("after_authorize", transaction_id)

            # ---- LOCK -----------------------------------------------------
            self._boundary("before_lock", transaction_id)
            try:
                acquired = self._acquire_locks(request, owner_id)
                locks_held = True
            except DurableMutationError as exc:
                step(MutationPhase.LOCK, success=False, detail={"error": str(exc)})
                step(MutationPhase.REJECT, success=True, detail={"reason": "lock"})
                return finish(
                    disposition=MutationDisposition.REJECTED,
                    committed=False,
                    decision=VFSWALDecision.REJECTED,
                    error_code=exc.code,
                    error_message=exc.message,
                )
            step(
                MutationPhase.LOCK,
                success=True,
                detail={"acquired": list(acquired), "paths": list(request.lock_paths)},
            )
            self._boundary("after_lock", transaction_id)

            # Prove pre-intent order before recording intent.
            self._trace.assert_pre_intent_order()  # intent not yet present — no-op
            pre_intent = self._trace.phases()
            for required in ("validate", "authorize", "lock"):
                if required not in pre_intent:
                    raise MutationProtocolError(
                        f"missing required pre-intent phase: {required}",
                        detail={"phases": pre_intent},
                    )

            # ---- BEGIN + INTENT (durable) ---------------------------------
            # Capture prior state under locks so recovery can compensate after
            # process restart without an in-memory effect ledger.
            prior_snapshots = self._capture_prior_snapshots(request)
            self._boundary("before_intent", transaction_id)
            self._wal.begin(transaction_id)
            wal_begun = True
            intent = self._intent_mapping(
                request,
                transaction_id=transaction_id,
                operation_id=operation_id,
                effect_id=effect_id,
                prior_snapshots=prior_snapshots,
            )
            recorded_effect_id = self._wal.record_intent(
                transaction_id, intent, effect_id=effect_id
            )
            if recorded_effect_id != effect_id:
                raise MutationProtocolError(
                    "WAL coordinator returned a different effect identity",
                    detail={
                        "expected": effect_id,
                        "observed": recorded_effect_id,
                    },
                )
            intent_durable = True
            durable_data = self._build_durable_data(
                request,
                transaction_id=transaction_id,
                operation_id=operation_id,
                effect_id=effect_id,
                decision=VFSWALDecision.INTENT_RECORDED,
            )
            step(
                MutationPhase.INTENT,
                success=True,
                detail={
                    "effect_id": effect_id,
                    "checksum": durable_data.checksum,
                    "durable": True,
                },
            )
            self._trace.assert_pre_intent_order()
            self._boundary("after_intent", transaction_id)

            if self._require_intent_durability and not intent_durable:
                raise MutationProtocolError(
                    "effect cannot run without durable intent",
                    phase=MutationPhase.INTENT,
                )

            # ---- EFFECT ---------------------------------------------------
            self._boundary("before_effect", transaction_id)

            def effect() -> Any:
                nonlocal content_cid, version_cid, bytes_affected, effect_applied
                meta, idempotent_receipt = self._backend.apply(
                    request, effect_id=effect_id
                )
                content_cid = str(meta.get("content_cid") or "")
                version_cid = str(meta.get("version_cid") or "")
                bytes_affected = int(meta.get("bytes_affected") or 0)
                effect_applied = True
                if idempotent_receipt is not None:
                    partials.append(self._remember_partial(idempotent_receipt))
                return meta

            def compensate() -> Any:
                receipt = self._backend.compensate(
                    effect_id,
                    transaction_id=transaction_id,
                    request=request,
                )
                partials.append(self._remember_partial(receipt))
                step(
                    MutationPhase.COMPENSATE,
                    success=True,
                    detail=receipt.to_record(),
                )
                return True

            # Intent already recorded; run effect and register compensation
            # without double-recording intent.
            try:
                effect_meta = effect()
            except MutationEffectError as exc:
                step(
                    MutationPhase.EFFECT,
                    success=False,
                    detail=dict(exc.detail) | {"error": exc.message},
                )
                receipt = PartialEffectReceipt(
                    partial_id=f"partial:mid-apply:{effect_id}",
                    kind=PartialEffectKind.EFFECT_FAILED_MID_APPLY,
                    effect_id=effect_id,
                    transaction_id=transaction_id,
                    mutation_kind=request.kind,
                    path=request.path,
                    target_path=request.target_path,
                    applied_evidence_ids=(),
                    pending_evidence_ids=(f"pending:effect:{effect_id}",),
                    compensation_required=True,
                    description=exc.message,
                    state=OperationState.FAILED,
                    prior_snapshot_digest=str(
                        (exc.detail or {}).get("prior_snapshot_digest") or ""
                    ),
                )
                partials.append(self._remember_partial(receipt))
                self._wal.abort(transaction_id)
                wal_begun = False
                return finish(
                    disposition=MutationDisposition.FAILED,
                    committed=False,
                    decision=VFSWALDecision.FAILED,
                    error_code=exc.code,
                    error_message=exc.message,
                )

            # Register compensation with the active transaction.
            with self._wal._lock:  # type: ignore[attr-defined]
                txn = self._wal._transactions.get(transaction_id)  # type: ignore[attr-defined]
                if txn is None:
                    raise MutationProtocolError(
                        "transaction missing after intent; cannot register compensate"
                    )
                txn.compensations.append(compensate)

            step(
                MutationPhase.EFFECT,
                success=True,
                detail={
                    "content_cid": content_cid,
                    "version_cid": version_cid,
                    "bytes_affected": bytes_affected,
                    "meta": effect_meta,
                },
            )
            self._boundary("after_effect", transaction_id)

            # Pre-commit partial receipt: effect applied, decision not yet durable.
            pre_commit_receipt = PartialEffectReceipt(
                partial_id=f"partial:pre-commit:{effect_id}",
                kind=PartialEffectKind.EFFECT_APPLIED_PRE_COMMIT,
                effect_id=effect_id,
                transaction_id=transaction_id,
                mutation_kind=request.kind,
                path=request.path,
                target_path=request.target_path,
                applied_evidence_ids=tuple(
                    effect_meta.get("applied_evidence_ids") or ()
                ),
                pending_evidence_ids=(f"pending:decision:{effect_id}",),
                compensation_required=True,
                description=(
                    f"{request.kind.value} effect applied; decision not yet durable"
                ),
                state=OperationState.PROCESSING,
                prior_snapshot_digest=str(
                    effect_meta.get("prior_snapshot_digest") or ""
                ),
            )
            partials.append(self._remember_partial(pre_commit_receipt))

            # ---- DECISION (durable commit + effect identity) --------------
            self._boundary("before_decision", transaction_id)
            commit_result: TransactionResult = self._wal.commit(transaction_id)
            wal_begun = False
            if not commit_result.committed:
                raise MutationProtocolError(
                    "WAL commit returned without durable commitment",
                    phase=MutationPhase.DECISION,
                )
            if commit_result.effect_id and commit_result.effect_id != effect_id:
                # Multi-intent edge: require our effect identity to be present.
                raise MutationProtocolError(
                    "committed effect identity mismatch",
                    phase=MutationPhase.DECISION,
                    detail={
                        "expected": effect_id,
                        "observed": commit_result.effect_id,
                    },
                )
            decision_durable = True
            durable_data = self._build_durable_data(
                request,
                transaction_id=transaction_id,
                operation_id=operation_id,
                effect_id=effect_id,
                decision=VFSWALDecision.COMMITTED,
                acknowledgement=VFSWALAcknowledgement(
                    mode=WALAcknowledgementMode.WAL_FSYNC_PARENT,
                    durable=True,
                    fsync_receipt_id=f"fsync:{effect_id}",
                    file_fsync=True,
                    parent_directory_fsync=True,
                    backend_effect_id=effect_id,
                ),
            )
            step(
                MutationPhase.DECISION,
                success=True,
                detail={
                    "effect_id": effect_id,
                    "decision": VFSWALDecision.COMMITTED.value,
                    "durable": True,
                },
            )
            self._boundary("after_decision", transaction_id)

            # ---- ACK (only after decision + effect identity durable) ------
            self._boundary("before_ack", transaction_id)
            if not decision_durable or not intent_durable:
                raise MutationProtocolError(
                    "committed acknowledgement requires durable decision "
                    "and effect identity",
                    phase=MutationPhase.ACK,
                )
            if durable_data is None or durable_data.effect_id != effect_id:
                raise MutationProtocolError(
                    "committed acknowledgement missing durable effect identity",
                    phase=MutationPhase.ACK,
                )
            if not durable_data.acknowledgement.durable:
                raise MutationProtocolError(
                    "committed acknowledgement requires durable ack evidence",
                    phase=MutationPhase.ACK,
                )
            step(
                MutationPhase.ACK,
                success=True,
                detail={
                    "effect_id": effect_id,
                    "decision_durable": True,
                    "intent_durable": True,
                },
            )
            # after_ack is process-death *after* durable acknowledgement: the
            # mutation is already committed.  Return success so callers observe
            # the completed ack; recovery still sees a durable committed effect.
            try:
                self._boundary("after_ack", transaction_id)
            except WALTransactionCrash:
                pass

            return finish(
                disposition=MutationDisposition.COMMITTED,
                committed=True,
                decision=VFSWALDecision.COMMITTED,
                durable_ack=True,
            )

        except WALTransactionCrash:
            # Process-like crash: leave durable state for recovery; do not
            # invent a normal abort.  Emit exact partial receipt.
            if effect_applied and not decision_durable:
                receipt = PartialEffectReceipt(
                    partial_id=f"partial:crash-pre-commit:{effect_id}",
                    kind=PartialEffectKind.COMPENSATION_REQUIRED,
                    effect_id=effect_id,
                    transaction_id=transaction_id,
                    mutation_kind=request.kind,
                    path=request.path,
                    target_path=request.target_path,
                    applied_evidence_ids=(f"apply:{request.kind.value}:{effect_id}",),
                    pending_evidence_ids=(f"pending:decision:{effect_id}",),
                    compensation_required=True,
                    description=(
                        "crash after effect, before durable decision; "
                        "compensation required on recovery"
                    ),
                    state=OperationState.FAILED,
                )
                partials.append(self._remember_partial(receipt))
            elif intent_durable and not effect_applied:
                receipt = PartialEffectReceipt(
                    partial_id=f"partial:crash-intent-only:{effect_id}",
                    kind=PartialEffectKind.INTENT_ONLY,
                    effect_id=effect_id,
                    transaction_id=transaction_id,
                    mutation_kind=request.kind,
                    path=request.path,
                    target_path=request.target_path,
                    applied_evidence_ids=(),
                    pending_evidence_ids=(f"pending:effect:{effect_id}",),
                    compensation_required=False,
                    description="crash after durable intent, before effect",
                    state=OperationState.PENDING,
                )
                partials.append(self._remember_partial(receipt))
            # Re-raise so callers / tests observe the crash boundary.
            self._last_result = MutationResult(
                disposition=MutationDisposition.CRASHED,
                kind=request.kind,
                path=request.path,
                target_path=request.target_path,
                transaction_id=transaction_id,
                operation_id=operation_id,
                effect_id=effect_id,
                committed=False,
                decision=VFSWALDecision.FAILED,
                phases=tuple(phases),
                partial_receipts=tuple(partials),
                durable_data=durable_data,
                intent_durable=intent_durable,
                decision_durable=decision_durable,
                error_code=MutationErrorCode.INTERNAL,
                error_message="WAL transaction crash boundary",
            )
            raise

        except DurableMutationError as exc:
            if wal_begun:
                try:
                    self._wal.abort(transaction_id)
                except Exception:
                    pass
                wal_begun = False
            return finish(
                disposition=MutationDisposition.FAILED,
                committed=False,
                decision=VFSWALDecision.FAILED,
                error_code=exc.code,
                error_message=exc.message,
            )

        except WALTransactionError as exc:
            if wal_begun:
                try:
                    self._wal.abort(transaction_id)
                except Exception:
                    pass
            return finish(
                disposition=MutationDisposition.FAILED,
                committed=False,
                decision=VFSWALDecision.FAILED,
                error_code=MutationErrorCode.DECISION,
                error_message=str(exc),
            )

        except Exception as exc:
            if wal_begun:
                try:
                    self._wal.abort(transaction_id)
                except Exception:
                    pass
            return finish(
                disposition=MutationDisposition.FAILED,
                committed=False,
                decision=VFSWALDecision.FAILED,
                error_code=MutationErrorCode.INTERNAL,
                error_message=str(exc),
            )

        finally:
            if locks_held:
                self._release_locks(owner_id)
            self._active_transaction_id = ""
            self._active_effect_id = ""

    # -- convenience mutators -----------------------------------------------

    def create(
        self,
        path: str,
        content: bytes = b"",
        *,
        exclusive: bool = True,
        principal_id: str = "",
        effect_id: str = "",
        transaction_id: str = "",
    ) -> MutationResult:
        return self.mutate(
            MutationRequest(
                kind=MutationKind.CREATE,
                path=path,
                content=content,
                exclusive=exclusive,
                principal_id=principal_id,
                effect_id=effect_id,
                transaction_id=transaction_id,
            )
        )

    def write(
        self,
        path: str,
        content: bytes,
        *,
        offset: int = 0,
        principal_id: str = "",
        effect_id: str = "",
        transaction_id: str = "",
    ) -> MutationResult:
        return self.mutate(
            MutationRequest(
                kind=MutationKind.WRITE,
                path=path,
                content=content,
                offset=offset,
                principal_id=principal_id,
                effect_id=effect_id,
                transaction_id=transaction_id,
            )
        )

    def truncate(
        self,
        path: str,
        size: int,
        *,
        principal_id: str = "",
        effect_id: str = "",
        transaction_id: str = "",
    ) -> MutationResult:
        return self.mutate(
            MutationRequest(
                kind=MutationKind.TRUNCATE,
                path=path,
                size=size,
                principal_id=principal_id,
                effect_id=effect_id,
                transaction_id=transaction_id,
            )
        )

    def unlink(
        self,
        path: str,
        *,
        principal_id: str = "",
        effect_id: str = "",
        transaction_id: str = "",
    ) -> MutationResult:
        return self.mutate(
            MutationRequest(
                kind=MutationKind.UNLINK,
                path=path,
                principal_id=principal_id,
                effect_id=effect_id,
                transaction_id=transaction_id,
            )
        )

    def rename(
        self,
        source: str,
        target: str,
        *,
        principal_id: str = "",
        effect_id: str = "",
        transaction_id: str = "",
    ) -> MutationResult:
        return self.mutate(
            MutationRequest(
                kind=MutationKind.RENAME,
                path=source,
                target_path=target,
                principal_id=principal_id,
                effect_id=effect_id,
                transaction_id=transaction_id,
            )
        )

    # -- recovery -----------------------------------------------------------

    def recover(self) -> dict[str, int]:
        """Replay committed effects and compensate durable non-committed intents.

        Apply and compensate are idempotent under effect identity.
        """

        def replay(intent: Mapping[str, Any], effect_id: str) -> Any:
            request = _request_from_intent(intent, effect_id=effect_id)
            meta, receipt = self._backend.apply(request, effect_id=effect_id)
            if receipt is not None:
                self._remember_partial(receipt)
            return meta

        def rollback(intent: Mapping[str, Any], effect_id: str) -> Any:
            request = _request_from_intent(intent, effect_id=effect_id)
            prior = _prior_snapshots_from_intent(intent)
            # Always attempt exact compensate from durable prior snapshots.
            # If the effect never applied, storage already matches prior and
            # compensate returns an idempotent receipt.
            receipt = self._backend.compensate(
                effect_id,
                transaction_id=str(intent.get("transaction_id") or ""),
                request=request,
                prior_snapshots=prior or None,
            )
            self._remember_partial(receipt)
            return True

        return self._wal.recover(replay_effect=replay, rollback_effect=rollback)


# Plan alias.
DurableMutationFacade = DurableMutationCoordinator


def _request_from_intent(
    intent: Mapping[str, Any], *, effect_id: str
) -> MutationRequest:
    """Rebuild a MutationRequest from a durable intent mapping."""

    kind_raw = intent.get("kind") or intent.get("intent") or MutationKind.WRITE.value
    try:
        kind = MutationKind(str(kind_raw))
    except ValueError:
        # Map WAL intent vocabulary.
        kind = {
            "create": MutationKind.CREATE,
            "write": MutationKind.WRITE,
            "truncate": MutationKind.TRUNCATE,
            "unlink": MutationKind.UNLINK,
            "rename": MutationKind.RENAME,
        }.get(str(kind_raw), MutationKind.WRITE)

    detail = intent.get("intent_detail") or {}
    if not isinstance(detail, Mapping):
        detail = {}
    path = str(intent.get("path") or detail.get("path") or "unknown")
    target = str(intent.get("target_path") or detail.get("target_path") or "")
    content_b64 = str(detail.get("content_b64") or "")
    content = _unb64(content_b64) if content_b64 else b""
    offset = int(detail.get("offset") or 0)
    size = int(detail.get("size") or 0)
    exclusive = bool(detail.get("exclusive") if "exclusive" in detail else True)
    return MutationRequest(
        kind=kind,
        path=path,
        target_path=target,
        content=content,
        offset=offset,
        size=size,
        exclusive=exclusive,
        effect_id=effect_id,
        transaction_id=str(intent.get("transaction_id") or ""),
        operation_id=str(intent.get("operation_id") or ""),
        generation_id=str(intent.get("generation_id") or DEFAULT_GENERATION_ID),
        principal_id=str(intent.get("principal_id") or ""),
    )


def _prior_snapshots_from_intent(
    intent: Mapping[str, Any],
) -> tuple[_PathSnapshot, ...]:
    """Extract prior-state snapshots embedded in a durable intent."""

    raw_list: Any = intent.get("prior_snapshots")
    if not raw_list:
        detail = intent.get("intent_detail") or {}
        if isinstance(detail, Mapping):
            raw_list = detail.get("prior_snapshots")
    if not isinstance(raw_list, Sequence) or isinstance(raw_list, (str, bytes)):
        return ()
    out: list[_PathSnapshot] = []
    for item in raw_list:
        if isinstance(item, Mapping):
            out.append(_PathSnapshot.from_intent_record(item))
    return tuple(out)


def ensure_pre_intent_phases(phases: Sequence[str]) -> None:
    """Public helper: require validate/authorize/lock before intent."""

    phase_list = list(phases)
    if "intent" not in phase_list:
        return
    intent_idx = phase_list.index("intent")
    for required in ("validate", "authorize", "lock"):
        if required not in phase_list[:intent_idx]:
            raise MutationProtocolError(
                f"{required} must precede durable intent",
                detail={"phases": phase_list},
            )


def mutation_kinds() -> tuple[str, ...]:
    """Closed mutation vocabulary for create/write/truncate/unlink/rename."""

    return tuple(kind.value for kind in MutationKind)


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "PRE_INTENT_PHASES",
    "DurableMutationFacade_V1",
    "DurableMutationCoordinator_V1",
    "PartialEffectReceipt_V1",
    "MutationKind",
    "MutationPhase",
    "MutationDisposition",
    "PartialEffectKind",
    "MutationErrorCode",
    "DurableMutationError",
    "MutationValidationError",
    "MutationAuthorizationError",
    "MutationLockError",
    "MutationProtocolError",
    "MutationEffectError",
    "MutationRequest",
    "MutationResult",
    "MutationPhaseStep",
    "PartialEffectReceipt",
    "MutationPhaseTrace",
    "MutationEffectBackend",
    "DurableMutationCoordinator",
    "DurableMutationFacade",
    "ensure_pre_intent_phases",
    "mutation_kinds",
    "path_to_ref",
]
