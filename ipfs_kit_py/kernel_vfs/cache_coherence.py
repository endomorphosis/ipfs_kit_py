"""Drive exact ARC invalidation/generation advance from mutation and replay (KVFS-404).

This module owns the *durable event-to-cache projection* that connects committed
VFS mutations (and recovery replay of those commits) to generation-bound range
ARC state:

* **Committed** create / replace / write / truncate / unlink / rename events
  advance or invalidate *exactly* the affected bindings **before** new
  admission is allowed for those scopes;
* **Recovery replay** of committed effects uses the same projection so a
  restarted mount cannot serve pre-crash bytes;
* **Aborted / failed / rejected** effects never publish — they leave ARC and
  generation fences unchanged;
* **Unrelated** content scopes and non-overlapping ranges remain live; and
* Concurrent interleavings cannot return a stale committed byte under a prior
  generation once a commit has been projected.

Conflict policy (KVFS-404): own durable event-to-cache projection only; do not
modify core mutation ordering (KVFS-309).  This module does not import fusepy,
open host mounts, or perform network I/O.

Interfaces (plan aliases): ``CacheCoherence@1``, ``CoherenceProjector@1``,
``GenerationAdvance@1``.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Final, Protocol, runtime_checkable

from ipfs_kit_py.cache.arc.contracts import MAX_SAFE_INTEGER, require_bounded_int
from ipfs_kit_py.cache.arc.range_bindings import (
    DEFAULT_GENERATION,
    DEFAULT_NAMESPACE,
    DEFAULT_POLICY,
    DEFAULT_SERIALIZER,
    RangeBinding,
    RangeExtentError,
    ranges_overlap,
    validate_offset,
)
from ipfs_kit_py.kernel_vfs.cached_storage import CachedStorage, DirtyScope

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-404"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

COHERENCE_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/cache_coherence"

CACHE_COHERENCE_SCHEMA: Final[str] = (
    f"{COHERENCE_NAMESPACE}/cache-coherence@{SCHEMA_MAJOR}"
)
COHERENCE_PROJECTOR_SCHEMA: Final[str] = (
    f"{COHERENCE_NAMESPACE}/coherence-projector@{SCHEMA_MAJOR}"
)
COHERENCE_EVENT_SCHEMA: Final[str] = (
    f"{COHERENCE_NAMESPACE}/coherence-event@{SCHEMA_MAJOR}"
)
COHERENCE_RECEIPT_SCHEMA: Final[str] = (
    f"{COHERENCE_NAMESPACE}/coherence-receipt@{SCHEMA_MAJOR}"
)
COHERENCE_METRICS_SCHEMA: Final[str] = (
    f"{COHERENCE_NAMESPACE}/coherence-metrics@{SCHEMA_MAJOR}"
)
GENERATION_ADVANCE_SCHEMA: Final[str] = (
    f"{COHERENCE_NAMESPACE}/generation-advance@{SCHEMA_MAJOR}"
)

# Public interface aliases.
CacheCoherence_V1: Final[str] = CACHE_COHERENCE_SCHEMA
CoherenceProjector_V1: Final[str] = COHERENCE_PROJECTOR_SCHEMA
GenerationAdvance_V1: Final[str] = GENERATION_ADVANCE_SCHEMA

MAX_TRACKED_BINDINGS: Final[int] = 65_536
MAX_GENERATION_SCOPES: Final[int] = 65_536
MAX_PATH_BYTES: Final[int] = 4_096
MAX_IDENTITY_BYTES: Final[int] = 512
MAX_PUBLISH_FENCES: Final[int] = 16_384
DEFAULT_CONTENT_PREFIX: Final[str] = "path:"


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class CoherenceMutationKind(str, Enum):
    """Closed mutation vocabulary that projects into ARC coherence actions.

    Includes ``replace`` (create-overwrite / write-replace semantics) in
    addition to the durable-mutation façade kinds so recovery and VFS
    operation traces can name the effect exactly.
    """

    CREATE = "create"
    REPLACE = "replace"
    WRITE = "write"
    TRUNCATE = "truncate"
    UNLINK = "unlink"
    RENAME = "rename"


class CoherenceDisposition(str, Enum):
    """Terminal disposition of the durable effect feeding the projector."""

    COMMITTED = "committed"
    ABORTED = "aborted"
    FAILED = "failed"
    REJECTED = "rejected"
    COMPENSATED = "compensated"
    PARTIAL = "partial"
    CRASHED = "crashed"


class CoherenceAction(str, Enum):
    """Closed set of projection actions applied to ARC state."""

    NONE = "none"
    INVALIDATE = "invalidate"
    ADVANCE_GENERATION = "advance_generation"
    INVALIDATE_AND_ADVANCE = "invalidate_and_advance"
    SUPPRESSED = "suppressed"  # non-committed effect — no publish


class CoherenceSource(str, Enum):
    """Origin of a coherence event."""

    MUTATION = "mutation"
    RECOVERY_REPLAY = "recovery_replay"
    BACKEND_RECONCILE = "backend_reconcile"
    EXPLICIT = "explicit"


# Dispositions that must never publish into ARC.
_NON_PUBLISHING: Final[frozenset[CoherenceDisposition]] = frozenset(
    {
        CoherenceDisposition.ABORTED,
        CoherenceDisposition.FAILED,
        CoherenceDisposition.REJECTED,
        CoherenceDisposition.COMPENSATED,
        CoherenceDisposition.PARTIAL,
        CoherenceDisposition.CRASHED,
    }
)

# Kinds that always touch the whole content scope (not a byte sub-range).
_WHOLE_SCOPE_KINDS: Final[frozenset[CoherenceMutationKind]] = frozenset(
    {
        CoherenceMutationKind.CREATE,
        CoherenceMutationKind.REPLACE,
        CoherenceMutationKind.UNLINK,
        CoherenceMutationKind.RENAME,
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CoherenceError(Exception):
    """Base class for cache-coherence projection failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "COHERENCE_ERROR",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = dict(detail or {})


class CoherenceValidationError(CoherenceError):
    def __init__(
        self,
        message: str = "coherence event validation failed",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code=kwargs.pop("code", "COHERENCE_VALIDATION"), **kwargs)


class CoherenceAdmissionBlocked(CoherenceError):
    """Admission refused because a generation fence is active or stale."""

    def __init__(
        self,
        message: str = "admission blocked by coherence fence",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code=kwargs.pop("code", "COHERENCE_ADMISSION_BLOCKED"), **kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bounded_text(value: Any, name: str, *, maximum: int = MAX_IDENTITY_BYTES) -> str:
    if not isinstance(value, str):
        raise CoherenceValidationError(f"{name} must be str, got {type(value).__name__}")
    if not value:
        raise CoherenceValidationError(f"{name} must be non-empty")
    encoded = value.encode("utf-8", errors="strict")
    if len(encoded) > maximum:
        raise CoherenceValidationError(f"{name} exceeds {maximum} bytes")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise CoherenceValidationError(f"{name} must not contain control characters")
    if value.strip() != value or " " in value or "\t" in value:
        raise CoherenceValidationError(
            f"{name} must not contain surrounding or internal whitespace"
        )
    return value


def _bounded_path(value: Any, name: str = "path") -> str:
    if not isinstance(value, str):
        raise CoherenceValidationError(f"{name} must be str")
    text = value.strip()
    if not text or text == "/":
        raise CoherenceValidationError(f"{name} must not be empty or root-only")
    if "\x00" in text:
        raise CoherenceValidationError(f"{name} must not contain NUL")
    parts = [p for p in text.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise CoherenceValidationError(f"{name} must not contain parent segments")
    if not parts:
        raise CoherenceValidationError(f"{name} must not be empty after normalization")
    normalized = "/".join(parts)
    if len(normalized.encode("utf-8")) > MAX_PATH_BYTES:
        raise CoherenceValidationError(f"{name} exceeds MAX_PATH_BYTES")
    return normalized


def path_to_content_id(path: str, *, prefix: str = DEFAULT_CONTENT_PREFIX) -> str:
    """Project a VFS path into a stable ARC content identity."""

    normalized = _bounded_path(path)
    # Compact separators so the identity stays within identity bounds.
    compact = normalized.replace("/", ".")
    return _bounded_text(f"{prefix}{compact}", "content_id")


def next_generation(previous: str | None = None, *, effect_id: str = "") -> str:
    """Derive a deterministic successor generation token.

    Prefer embedding the durable effect identity so recovery replays of the
    same commit re-project to the same generation fence.
    """

    if effect_id:
        token = _bounded_text(effect_id, "effect_id", maximum=MAX_IDENTITY_BYTES)
        # Keep generation compact and control-char free.
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
        return f"g:{digest}"
    if previous is None or previous == DEFAULT_GENERATION:
        return "g:1"
    # Best-effort numeric successor for test/manual sequences ``g:N``.
    if previous.startswith("g:") and previous[2:].isdigit():
        return f"g:{int(previous[2:]) + 1}"
    digest = hashlib.sha256(previous.encode("utf-8")).hexdigest()[:16]
    return f"g:{digest}"


# ---------------------------------------------------------------------------
# Event / receipt / metrics records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoherenceEvent:
    """One durable mutation or recovery-replay observation for projection.

    Only events with :attr:`disposition` ``committed`` publish into ARC.
    Non-committed dispositions produce a suppressed receipt and leave state
    unchanged.
    """

    SCHEMA: ClassVar[str] = COHERENCE_EVENT_SCHEMA

    kind: CoherenceMutationKind
    disposition: CoherenceDisposition
    path: str
    content_id: str = ""
    namespace: str = DEFAULT_NAMESPACE
    generation: str = ""
    prior_generation: str = ""
    version: str = ""
    prior_version: str = ""
    offset: int | None = None
    length: int | None = None
    size: int | None = None  # truncate target size
    target_path: str = ""
    target_content_id: str = ""
    effect_id: str = ""
    transaction_id: str = ""
    source: CoherenceSource = CoherenceSource.MUTATION
    serializer: str = DEFAULT_SERIALIZER
    policy: str = DEFAULT_POLICY
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CoherenceMutationKind):
            object.__setattr__(self, "kind", CoherenceMutationKind(self.kind))
        if not isinstance(self.disposition, CoherenceDisposition):
            object.__setattr__(
                self, "disposition", CoherenceDisposition(self.disposition)
            )
        if not isinstance(self.source, CoherenceSource):
            object.__setattr__(self, "source", CoherenceSource(self.source))

        path = _bounded_path(self.path)
        object.__setattr__(self, "path", path)

        content_id = self.content_id
        if not content_id:
            content_id = path_to_content_id(path)
        else:
            content_id = _bounded_text(content_id, "content_id")
        object.__setattr__(self, "content_id", content_id)

        object.__setattr__(
            self, "namespace", _bounded_text(self.namespace, "namespace")
        )
        if self.generation:
            object.__setattr__(
                self, "generation", _bounded_text(self.generation, "generation")
            )
        if self.prior_generation:
            object.__setattr__(
                self,
                "prior_generation",
                _bounded_text(self.prior_generation, "prior_generation"),
            )
        if self.version:
            object.__setattr__(
                self, "version", _bounded_text(self.version, "version")
            )
        if self.prior_version:
            object.__setattr__(
                self,
                "prior_version",
                _bounded_text(self.prior_version, "prior_version"),
            )
        object.__setattr__(
            self, "serializer", _bounded_text(self.serializer, "serializer")
        )
        object.__setattr__(self, "policy", _bounded_text(self.policy, "policy"))

        if self.offset is not None:
            object.__setattr__(self, "offset", validate_offset(self.offset))
        if self.length is not None:
            object.__setattr__(
                self,
                "length",
                require_bounded_int(
                    self.length, name="length", minimum=0, maximum=MAX_SAFE_INTEGER
                ),
            )
        if self.size is not None:
            object.__setattr__(
                self,
                "size",
                require_bounded_int(
                    self.size, name="size", minimum=0, maximum=MAX_SAFE_INTEGER
                ),
            )

        if self.kind is CoherenceMutationKind.RENAME:
            if not self.target_path:
                raise CoherenceValidationError("rename requires target_path")
            target = _bounded_path(self.target_path, "target_path")
            object.__setattr__(self, "target_path", target)
            target_cid = self.target_content_id or path_to_content_id(target)
            object.__setattr__(
                self, "target_content_id", _bounded_text(target_cid, "target_content_id")
            )
        elif self.target_path:
            object.__setattr__(
                self, "target_path", _bounded_path(self.target_path, "target_path")
            )
            if self.target_content_id:
                object.__setattr__(
                    self,
                    "target_content_id",
                    _bounded_text(self.target_content_id, "target_content_id"),
                )

        if self.effect_id:
            object.__setattr__(
                self,
                "effect_id",
                _bounded_text(self.effect_id, "effect_id", maximum=MAX_IDENTITY_BYTES),
            )
        if self.transaction_id:
            object.__setattr__(
                self,
                "transaction_id",
                _bounded_text(
                    self.transaction_id, "transaction_id", maximum=MAX_IDENTITY_BYTES
                ),
            )

    @property
    def publishes(self) -> bool:
        return self.disposition is CoherenceDisposition.COMMITTED

    @property
    def is_recovery(self) -> bool:
        return self.source is CoherenceSource.RECOVERY_REPLAY

    def resolved_generation(self) -> str:
        """Generation fence to install for a publishing event."""

        if self.generation:
            return self.generation
        return next_generation(self.prior_generation or None, effect_id=self.effect_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind.value,
            "disposition": self.disposition.value,
            "path": self.path,
            "content_id": self.content_id,
            "namespace": self.namespace,
            "generation": self.generation,
            "prior_generation": self.prior_generation,
            "version": self.version,
            "prior_version": self.prior_version,
            "offset": self.offset,
            "length": self.length,
            "size": self.size,
            "target_path": self.target_path,
            "target_content_id": self.target_content_id,
            "effect_id": self.effect_id,
            "transaction_id": self.transaction_id,
            "source": self.source.value,
            "serializer": self.serializer,
            "policy": self.policy,
            "notes": self.notes,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CoherenceEvent":
        if not isinstance(value, Mapping):
            raise CoherenceValidationError("event must be a mapping")
        return cls(
            kind=CoherenceMutationKind(value["kind"]),
            disposition=CoherenceDisposition(value["disposition"]),
            path=str(value["path"]),
            content_id=str(value.get("content_id") or ""),
            namespace=str(value.get("namespace") or DEFAULT_NAMESPACE),
            generation=str(value.get("generation") or ""),
            prior_generation=str(value.get("prior_generation") or ""),
            version=str(value.get("version") or ""),
            prior_version=str(value.get("prior_version") or ""),
            offset=value.get("offset"),
            length=value.get("length"),
            size=value.get("size"),
            target_path=str(value.get("target_path") or ""),
            target_content_id=str(value.get("target_content_id") or ""),
            effect_id=str(value.get("effect_id") or ""),
            transaction_id=str(value.get("transaction_id") or ""),
            source=CoherenceSource(value.get("source") or CoherenceSource.MUTATION),
            serializer=str(value.get("serializer") or DEFAULT_SERIALIZER),
            policy=str(value.get("policy") or DEFAULT_POLICY),
            notes=str(value.get("notes") or ""),
        )

    @classmethod
    def from_mutation_result(
        cls,
        result: Any,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        content_id: str | None = None,
        target_content_id: str | None = None,
        generation: str = "",
        prior_generation: str = "",
        version: str = "",
        prior_version: str = "",
        offset: int | None = None,
        length: int | None = None,
        size: int | None = None,
        source: CoherenceSource = CoherenceSource.MUTATION,
        serializer: str = DEFAULT_SERIALIZER,
        policy: str = DEFAULT_POLICY,
    ) -> "CoherenceEvent":
        """Project a :class:`~ipfs_kit_py.kernel_vfs.durable_mutation.MutationResult`.

        Accepts duck-typed results so recovery receipts and lightweight test
        doubles work without importing the full durable-mutation façade at
        module import time for every call site.
        """

        kind_raw = getattr(result, "kind", None)
        if kind_raw is None and isinstance(result, Mapping):
            kind_raw = result.get("kind")
        kind_value = getattr(kind_raw, "value", kind_raw)
        # Durable mutation uses create for both exclusive create and replace;
        # callers may override via notes or we map create→create and let the
        # event kind be refined by exclusive flag when present.
        try:
            kind = CoherenceMutationKind(str(kind_value))
        except ValueError as exc:
            raise CoherenceValidationError(
                f"unsupported mutation kind for coherence: {kind_value!r}"
            ) from exc

        disp_raw = getattr(result, "disposition", None)
        if disp_raw is None and isinstance(result, Mapping):
            disp_raw = result.get("disposition")
        committed = bool(
            getattr(result, "committed", False)
            if not isinstance(result, Mapping)
            else result.get("committed", False)
        )
        if disp_raw is not None:
            disp_value = getattr(disp_raw, "value", disp_raw)
            try:
                disposition = CoherenceDisposition(str(disp_value))
            except ValueError:
                disposition = (
                    CoherenceDisposition.COMMITTED
                    if committed
                    else CoherenceDisposition.FAILED
                )
        else:
            disposition = (
                CoherenceDisposition.COMMITTED
                if committed
                else CoherenceDisposition.FAILED
            )

        def _field(name: str, default: str = "") -> str:
            if isinstance(result, Mapping):
                return str(result.get(name) or default)
            return str(getattr(result, name, default) or default)

        path = _field("path")
        target_path = _field("target_path")
        effect_id = _field("effect_id")
        transaction_id = _field("transaction_id")
        version_cid = version or _field("version_cid")
        content_cid = content_id or _field("content_cid") or None

        # Prefer explicit content identity; fall back to path projection.
        resolved_content_id = content_cid if content_cid else ""
        # content_cid from mutation is a content hash, not a stable inode — use
        # path-derived identity for scope tracking so rename/unlink stay stable.
        if not resolved_content_id or resolved_content_id.startswith("cid:"):
            resolved_content_id = path_to_content_id(path) if path else ""

        return cls(
            kind=kind,
            disposition=disposition,
            path=path,
            content_id=resolved_content_id,
            namespace=namespace,
            generation=generation,
            prior_generation=prior_generation,
            version=version_cid,
            prior_version=prior_version,
            offset=offset,
            length=length,
            size=size,
            target_path=target_path,
            target_content_id=target_content_id or (
                path_to_content_id(target_path) if target_path else ""
            ),
            effect_id=effect_id,
            transaction_id=transaction_id,
            source=source,
            serializer=serializer,
            policy=policy,
        )


@dataclass(frozen=True)
class CoherenceReceipt:
    """Immutable outcome of projecting one coherence event."""

    SCHEMA: ClassVar[str] = COHERENCE_RECEIPT_SCHEMA

    action: CoherenceAction
    published: bool
    kind: CoherenceMutationKind
    disposition: CoherenceDisposition
    path: str
    content_id: str
    namespace: str
    generation: str = ""
    prior_generation: str = ""
    bindings_invalidated: int = 0
    scopes_advanced: int = 0
    dirty_cleared: int = 0
    target_content_id: str = ""
    target_generation: str = ""
    effect_id: str = ""
    transaction_id: str = ""
    source: CoherenceSource = CoherenceSource.MUTATION
    suppressed_reason: str = ""
    invalidated_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "action": self.action.value,
            "published": self.published,
            "kind": self.kind.value,
            "disposition": self.disposition.value,
            "path": self.path,
            "content_id": self.content_id,
            "namespace": self.namespace,
            "generation": self.generation,
            "prior_generation": self.prior_generation,
            "bindings_invalidated": self.bindings_invalidated,
            "scopes_advanced": self.scopes_advanced,
            "dirty_cleared": self.dirty_cleared,
            "target_content_id": self.target_content_id,
            "target_generation": self.target_generation,
            "effect_id": self.effect_id,
            "transaction_id": self.transaction_id,
            "source": self.source.value,
            "suppressed_reason": self.suppressed_reason,
            "invalidated_key_count": len(self.invalidated_keys),
        }


@dataclass
class CoherenceMetrics:
    """Bounded counters for coherence diagnostics."""

    SCHEMA: ClassVar[str] = COHERENCE_METRICS_SCHEMA

    publishes: int = 0
    suppressed: int = 0
    recovery_replays: int = 0
    generation_advances: int = 0
    bindings_invalidated: int = 0
    dirty_cleared: int = 0
    admission_blocks: int = 0
    admission_allowed: int = 0
    stale_rejections: int = 0
    create_events: int = 0
    replace_events: int = 0
    write_events: int = 0
    truncate_events: int = 0
    unlink_events: int = 0
    rename_events: int = 0
    failed_non_publish: int = 0
    aborted_non_publish: int = 0

    def snapshot(self) -> "CoherenceMetrics":
        return CoherenceMetrics(
            publishes=self.publishes,
            suppressed=self.suppressed,
            recovery_replays=self.recovery_replays,
            generation_advances=self.generation_advances,
            bindings_invalidated=self.bindings_invalidated,
            dirty_cleared=self.dirty_cleared,
            admission_blocks=self.admission_blocks,
            admission_allowed=self.admission_allowed,
            stale_rejections=self.stale_rejections,
            create_events=self.create_events,
            replace_events=self.replace_events,
            write_events=self.write_events,
            truncate_events=self.truncate_events,
            unlink_events=self.unlink_events,
            rename_events=self.rename_events,
            failed_non_publish=self.failed_non_publish,
            aborted_non_publish=self.aborted_non_publish,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "publishes": self.publishes,
            "suppressed": self.suppressed,
            "recovery_replays": self.recovery_replays,
            "generation_advances": self.generation_advances,
            "bindings_invalidated": self.bindings_invalidated,
            "dirty_cleared": self.dirty_cleared,
            "admission_blocks": self.admission_blocks,
            "admission_allowed": self.admission_allowed,
            "stale_rejections": self.stale_rejections,
            "create_events": self.create_events,
            "replace_events": self.replace_events,
            "write_events": self.write_events,
            "truncate_events": self.truncate_events,
            "unlink_events": self.unlink_events,
            "rename_events": self.rename_events,
            "failed_non_publish": self.failed_non_publish,
            "aborted_non_publish": self.aborted_non_publish,
        }


# ---------------------------------------------------------------------------
# Optional ARC targets
# ---------------------------------------------------------------------------


@runtime_checkable
class SupportsBindingDelete(Protocol):
    def delete(self, binding: RangeBinding | Mapping[str, Any]) -> bool: ...


@runtime_checkable
class SupportsGenerationAdvance(Protocol):
    def advance_generation(
        self, content_id: str, generation: str, *, namespace: str = "default"
    ) -> int: ...


@runtime_checkable
class SupportsExactInvalidate(Protocol):
    def invalidate(
        self, binding: Any = None, **exact: str
    ) -> int: ...


# ---------------------------------------------------------------------------
# CacheCoherence
# ---------------------------------------------------------------------------


class CacheCoherence:
    """Project committed mutation/replay events into exact ARC coherence actions.

    Ordering guarantee for a publishing event (under the coherence lock):

    1. Install a publish fence on every affected scope (blocks new admission).
    2. Advance the active generation for each affected content identity.
    3. Invalidate exactly the affected live bindings (range-aware for write /
       truncate; whole-scope for create/replace/unlink/rename).
    4. Clear dirty marks on :class:`CachedStorage` for those scopes so post-
       commit admission can proceed under the new generation.
    5. Drop the publish fence and return a receipt.

    Non-committed dispositions short-circuit at step 0 and never touch ARC.
    """

    SCHEMA: ClassVar[str] = CACHE_COHERENCE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION
    INTERFACE: ClassVar[str] = CacheCoherence_V1

    def __init__(
        self,
        storage: CachedStorage | None = None,
        *,
        generation_arc: SupportsGenerationAdvance | None = None,
        invalidate_arc: SupportsExactInvalidate | None = None,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._storage = storage
        self._generation_arc = generation_arc
        self._invalidate_arc = invalidate_arc
        self._authorize = authorize
        self._consistent = consistent
        # Active generation per (namespace, content_id).
        self._generations: dict[tuple[str, str], str] = {}
        # Tracked admitted range bindings for exact invalidation.
        self._bindings: dict[str, RangeBinding] = {}
        # Scopes currently mid-publish (admission blocked).
        self._publish_fences: set[tuple[str, str]] = set()
        # Idempotency: effect_id → receipt for committed publishes.
        self._effect_receipts: dict[str, CoherenceReceipt] = {}
        self._metrics = CoherenceMetrics()
        # Condition so waiters can observe fence release (tests / optional).
        self._fence_changed = threading.Condition(self._lock)

    # --- properties --------------------------------------------------------

    @property
    def storage(self) -> CachedStorage | None:
        return self._storage

    def metrics(self) -> CoherenceMetrics:
        with self._lock:
            return self._metrics.snapshot()

    def tracked_binding_count(self) -> int:
        with self._lock:
            return len(self._bindings)

    def active_generation(
        self,
        content_id: str,
        *,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> str | None:
        content_id = _bounded_text(content_id, "content_id")
        namespace = _bounded_text(namespace, "namespace")
        with self._lock:
            return self._generations.get((namespace, content_id))

    def is_fenced(
        self,
        content_id: str,
        *,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> bool:
        content_id = _bounded_text(content_id, "content_id")
        namespace = _bounded_text(namespace, "namespace")
        with self._lock:
            return (namespace, content_id) in self._publish_fences

    # --- binding registry --------------------------------------------------

    def note_admitted(self, binding: RangeBinding | Mapping[str, Any]) -> None:
        """Record a live admitted binding so later commits can target it exactly."""

        identity = self._coerce_binding(binding)
        with self._lock:
            if (
                identity.cache_key not in self._bindings
                and len(self._bindings) >= MAX_TRACKED_BINDINGS
            ):
                # Drop arbitrary oldest-like entry (dict insertion order).
                self._bindings.pop(next(iter(self._bindings)))
            self._bindings[identity.cache_key] = identity
            # Seed generation map from first admission if unset.
            scope = (identity.namespace, identity.content_id)
            self._generations.setdefault(scope, identity.generation)

    def forget_binding(self, binding: RangeBinding | Mapping[str, Any]) -> bool:
        identity = self._coerce_binding(binding)
        with self._lock:
            return self._bindings.pop(identity.cache_key, None) is not None

    def tracked_bindings(
        self,
        *,
        namespace: str | None = None,
        content_id: str | None = None,
    ) -> list[RangeBinding]:
        with self._lock:
            out: list[RangeBinding] = []
            for binding in self._bindings.values():
                if namespace is not None and binding.namespace != namespace:
                    continue
                if content_id is not None and binding.content_id != content_id:
                    continue
                out.append(binding)
            return out

    # --- admission gate ----------------------------------------------------

    def may_admit(
        self,
        binding: RangeBinding | Mapping[str, Any],
        *,
        count: bool = True,
    ) -> bool:
        """Return True when the binding may enter shared ARC under current fences.

        Fail-closed when:

        * the content scope is mid-publish (fence installed before invalidation
          completes); or
        * an active generation is recorded and the binding's generation does
          not match it (stale committed byte prevention).
        """

        identity = self._coerce_binding(binding)
        with self._lock:
            scope = (identity.namespace, identity.content_id)
            if scope in self._publish_fences:
                if count:
                    self._metrics.admission_blocks += 1
                return False
            active = self._generations.get(scope)
            if active is not None and active != identity.generation:
                if count:
                    self._metrics.admission_blocks += 1
                    self._metrics.stale_rejections += 1
                return False
            if count:
                self._metrics.admission_allowed += 1
            return True

    def require_admit(self, binding: RangeBinding | Mapping[str, Any]) -> RangeBinding:
        """Like :meth:`may_admit` but raises on block."""

        identity = self._coerce_binding(binding)
        if not self.may_admit(identity, count=True):
            raise CoherenceAdmissionBlocked(
                detail={
                    "cache_key": identity.cache_key,
                    "content_id": identity.content_id,
                    "generation": identity.generation,
                    "active_generation": self.active_generation(
                        identity.content_id, namespace=identity.namespace
                    ),
                }
            )
        return identity

    def put_committed(
        self,
        binding: RangeBinding | Mapping[str, Any],
        value: bytes,
        *,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
    ) -> bool:
        """Admit committed bytes only after the coherence gate passes.

        When a :class:`CachedStorage` is configured, admission goes through it;
        the binding is tracked only on successful put.
        """

        identity = self.require_admit(binding)
        if self._storage is None:
            # Track-only mode (no storage target): still record for invalidation.
            if not isinstance(value, (bytes, bytearray, memoryview)):
                raise TypeError("value must be bytes-like")
            data = bytes(value)
            if len(data) != identity.length:
                raise RangeExtentError(
                    f"value length {len(data)} disagrees with binding length "
                    f"{identity.length}"
                )
            self.note_admitted(identity)
            return True

        auth = authorize if authorize is not None else self._authorize
        cons = consistent if consistent is not None else self._consistent
        admitted = self._storage.put_committed(
            identity, value, authorize=auth, consistent=cons
        )
        if admitted:
            self.note_admitted(identity)
        return admitted

    def get(
        self,
        binding: RangeBinding | Mapping[str, Any],
        *,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
    ) -> bytes | None:
        """Return a revalidated hit only when generation fence allows it.

        Stale-generation bindings are treated as misses and dropped from the
        tracked map / storage so they cannot resurface.
        """

        identity = self._coerce_binding(binding)
        with self._lock:
            scope = (identity.namespace, identity.content_id)
            if scope in self._publish_fences:
                self._metrics.admission_blocks += 1
                return None
            active = self._generations.get(scope)
            if active is not None and active != identity.generation:
                self._metrics.stale_rejections += 1
                self._drop_binding_locked(identity)
                return None

        if self._storage is None:
            return None
        auth = authorize if authorize is not None else self._authorize
        cons = consistent if consistent is not None else self._consistent
        return self._storage.get(identity, authorize=auth, consistent=cons)

    # --- publish / project -------------------------------------------------

    def publish(self, event: CoherenceEvent | Mapping[str, Any]) -> CoherenceReceipt:
        """Project one event into ARC.  Only committed dispositions publish."""

        if not isinstance(event, CoherenceEvent):
            event = CoherenceEvent.from_mapping(event)
        with self._lock:
            return self._publish_locked(event)

    def publish_many(
        self, events: Sequence[CoherenceEvent | Mapping[str, Any]]
    ) -> list[CoherenceReceipt]:
        """Project events in order under one lock (recovery batch)."""

        receipts: list[CoherenceReceipt] = []
        with self._lock:
            for item in events:
                event = (
                    item
                    if isinstance(item, CoherenceEvent)
                    else CoherenceEvent.from_mapping(item)
                )
                receipts.append(self._publish_locked(event))
        return receipts

    def publish_mutation_result(
        self,
        result: Any,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        content_id: str | None = None,
        target_content_id: str | None = None,
        generation: str = "",
        prior_generation: str = "",
        version: str = "",
        prior_version: str = "",
        offset: int | None = None,
        length: int | None = None,
        size: int | None = None,
        source: CoherenceSource = CoherenceSource.MUTATION,
        serializer: str = DEFAULT_SERIALIZER,
        policy: str = DEFAULT_POLICY,
    ) -> CoherenceReceipt:
        """Adapter: durable mutation result → coherence publish."""

        event = CoherenceEvent.from_mutation_result(
            result,
            namespace=namespace,
            content_id=content_id,
            target_content_id=target_content_id,
            generation=generation,
            prior_generation=prior_generation,
            version=version,
            prior_version=prior_version,
            offset=offset,
            length=length,
            size=size,
            source=source,
            serializer=serializer,
            policy=policy,
        )
        return self.publish(event)

    def publish_recovery_replay(
        self,
        events: Sequence[CoherenceEvent | Mapping[str, Any]],
    ) -> list[CoherenceReceipt]:
        """Project recovery-replay commits with source stamped as recovery."""

        stamped: list[CoherenceEvent] = []
        for item in events:
            event = (
                item
                if isinstance(item, CoherenceEvent)
                else CoherenceEvent.from_mapping(item)
            )
            if event.source is not CoherenceSource.RECOVERY_REPLAY:
                # Rebuild with recovery source while preserving fields.
                payload = event.to_dict()
                payload["source"] = CoherenceSource.RECOVERY_REPLAY.value
                event = CoherenceEvent.from_mapping(payload)
            stamped.append(event)
        return self.publish_many(stamped)

    def advance_generation(
        self,
        content_id: str,
        generation: str,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        version: str | None = None,
        serializer: str | None = None,
        policy: str | None = None,
    ) -> CoherenceReceipt:
        """Explicit generation advance for one content scope (backend reconcile)."""

        event = CoherenceEvent(
            kind=CoherenceMutationKind.REPLACE,
            disposition=CoherenceDisposition.COMMITTED,
            path=f"_explicit/{content_id}",
            content_id=content_id,
            namespace=namespace,
            generation=generation,
            version=version or "",
            serializer=serializer or DEFAULT_SERIALIZER,
            policy=policy or DEFAULT_POLICY,
            source=CoherenceSource.EXPLICIT,
            effect_id=f"explicit:{namespace}:{content_id}:{generation}",
        )
        return self.publish(event)

    def invalidate_binding(
        self, binding: RangeBinding | Mapping[str, Any]
    ) -> int:
        """Drop one exact binding from tracking and storage."""

        identity = self._coerce_binding(binding)
        with self._lock:
            removed = 1 if self._drop_binding_locked(identity) else 0
            if removed:
                self._metrics.bindings_invalidated += removed
            return removed

    # --- internal publish --------------------------------------------------

    def _publish_locked(self, event: CoherenceEvent) -> CoherenceReceipt:
        # Idempotent re-publish of the same committed effect.
        if event.effect_id and event.effect_id in self._effect_receipts:
            prior = self._effect_receipts[event.effect_id]
            if event.publishes:
                return prior

        if not event.publishes:
            self._metrics.suppressed += 1
            if event.disposition is CoherenceDisposition.FAILED:
                self._metrics.failed_non_publish += 1
            elif event.disposition is CoherenceDisposition.ABORTED:
                self._metrics.aborted_non_publish += 1
            return CoherenceReceipt(
                action=CoherenceAction.SUPPRESSED,
                published=False,
                kind=event.kind,
                disposition=event.disposition,
                path=event.path,
                content_id=event.content_id,
                namespace=event.namespace,
                effect_id=event.effect_id,
                transaction_id=event.transaction_id,
                source=event.source,
                suppressed_reason=f"disposition:{event.disposition.value}",
            )

        # --- publishing path: fence → advance → invalidate → unfence ------
        scopes = self._affected_scopes(event)
        if len(self._publish_fences) + len(scopes) > MAX_PUBLISH_FENCES:
            raise CoherenceError(
                "publish fence map exceeds bound",
                code="COHERENCE_FENCE_LIMIT",
            )

        for scope in scopes:
            self._publish_fences.add(scope)
        self._fence_changed.notify_all()

        try:
            generation = event.resolved_generation()
            prior_generations: dict[tuple[str, str], str | None] = {
                scope: self._generations.get(scope) for scope in scopes
            }

            # 1) Advance generation fences first so concurrent may_admit sees
            #    the new generation even before individual keys are deleted.
            scopes_advanced = 0
            target_generation = ""
            for scope in scopes:
                ns, cid = scope
                if len(self._generations) >= MAX_GENERATION_SCOPES and scope not in self._generations:
                    # Evict an unrelated scope if needed (should be rare).
                    victim = next(
                        (k for k in self._generations if k not in scopes),
                        None,
                    )
                    if victim is not None:
                        del self._generations[victim]
                # Rename target may use the same generation token; source
                # unlinks clear generation after invalidation below.
                if event.kind is CoherenceMutationKind.UNLINK and scope == (
                    event.namespace,
                    event.content_id,
                ):
                    # Unlink: invalidate then drop generation (no successor live).
                    continue
                if event.kind is CoherenceMutationKind.RENAME and scope == (
                    event.namespace,
                    event.content_id,
                ):
                    # Source of rename is removed; generation cleared after
                    # invalidation.
                    continue
                self._generations[scope] = generation
                scopes_advanced += 1
                if event.kind is CoherenceMutationKind.RENAME and scope == (
                    event.namespace,
                    event.target_content_id,
                ):
                    target_generation = generation
                if self._generation_arc is not None:
                    try:
                        self._generation_arc.advance_generation(
                            cid, generation, namespace=ns
                        )
                    except Exception:  # noqa: BLE001 — projection must finish
                        pass

            # 2) Exact invalidation of affected bindings.
            invalidated_keys, bindings_invalidated = self._invalidate_affected_locked(
                event, generation=generation
            )

            # 3) Unlink / rename source: clear generation after invalidation.
            if event.kind is CoherenceMutationKind.UNLINK:
                self._generations.pop((event.namespace, event.content_id), None)
            elif event.kind is CoherenceMutationKind.RENAME:
                self._generations.pop((event.namespace, event.content_id), None)

            # 4) Clear dirty marks so post-commit admission can proceed.
            dirty_cleared = self._clear_dirty_locked(event, scopes)

            self._metrics.publishes += 1
            self._metrics.bindings_invalidated += bindings_invalidated
            self._metrics.generation_advances += scopes_advanced
            self._metrics.dirty_cleared += dirty_cleared
            if event.source is CoherenceSource.RECOVERY_REPLAY:
                self._metrics.recovery_replays += 1
            self._count_kind_locked(event.kind)

            if scopes_advanced and bindings_invalidated:
                action = CoherenceAction.INVALIDATE_AND_ADVANCE
            elif scopes_advanced:
                action = CoherenceAction.ADVANCE_GENERATION
            elif bindings_invalidated:
                action = CoherenceAction.INVALIDATE
            else:
                # Empty cache still records a generation fence for the scope
                # (except unlink, which only invalidates).
                action = (
                    CoherenceAction.INVALIDATE
                    if event.kind is CoherenceMutationKind.UNLINK
                    else CoherenceAction.ADVANCE_GENERATION
                )

            primary_prior = prior_generations.get(
                (event.namespace, event.content_id)
            ) or event.prior_generation or ""

            if event.kind is CoherenceMutationKind.UNLINK:
                receipt_generation = ""
            elif event.kind is CoherenceMutationKind.RENAME:
                receipt_generation = self._generations.get(
                    (event.namespace, event.target_content_id), generation
                )
            else:
                receipt_generation = generation

            if not target_generation and event.target_content_id:
                target_generation = self._generations.get(
                    (event.namespace, event.target_content_id), ""
                )

            receipt = CoherenceReceipt(
                action=action,
                published=True,
                kind=event.kind,
                disposition=event.disposition,
                path=event.path,
                content_id=event.content_id,
                namespace=event.namespace,
                generation=receipt_generation,
                prior_generation=primary_prior,
                bindings_invalidated=bindings_invalidated,
                scopes_advanced=scopes_advanced,
                dirty_cleared=dirty_cleared,
                target_content_id=event.target_content_id,
                target_generation=target_generation,
                effect_id=event.effect_id,
                transaction_id=event.transaction_id,
                source=event.source,
                invalidated_keys=tuple(invalidated_keys),
            )

            if event.effect_id:
                if len(self._effect_receipts) >= MAX_TRACKED_BINDINGS:
                    self._effect_receipts.pop(next(iter(self._effect_receipts)))
                self._effect_receipts[event.effect_id] = receipt
            return receipt
        finally:
            for scope in scopes:
                self._publish_fences.discard(scope)
            self._fence_changed.notify_all()

    def _affected_scopes(
        self, event: CoherenceEvent
    ) -> list[tuple[str, str]]:
        scopes: list[tuple[str, str]] = [
            (event.namespace, event.content_id),
        ]
        if event.kind is CoherenceMutationKind.RENAME and event.target_content_id:
            target = (event.namespace, event.target_content_id)
            if target not in scopes:
                scopes.append(target)
        return scopes

    def _invalidate_affected_locked(
        self,
        event: CoherenceEvent,
        *,
        generation: str,
    ) -> tuple[list[str], int]:
        """Invalidate exactly the bindings affected by ``event``.

        * create / replace / unlink: all bindings for the content scope
        * rename: all bindings for source *and* target content scopes
        * write: bindings whose range overlaps ``[offset, offset+length)``
          under the content scope (or all if extent unspecified)
        * truncate: bindings that extend past the new size (or all if size
          is None)
        """

        keys_to_drop: list[str] = []

        def scope_match(binding: RangeBinding, content_id: str) -> bool:
            if binding.namespace != event.namespace:
                return False
            if binding.content_id != content_id:
                return False
            # Also drop any generation (including the new one pre-seeded) for
            # whole-scope mutations; for write/truncate prefer dropping stale
            # and overlapping live entries so post-commit admission under the
            # new generation starts clean.
            return True

        if event.kind is CoherenceMutationKind.WRITE:
            keys_to_drop.extend(
                self._select_write_keys_locked(event, generation=generation)
            )
        elif event.kind is CoherenceMutationKind.TRUNCATE:
            keys_to_drop.extend(
                self._select_truncate_keys_locked(event, generation=generation)
            )
        elif event.kind is CoherenceMutationKind.RENAME:
            for binding_key, binding in self._bindings.items():
                if scope_match(binding, event.content_id) or scope_match(
                    binding, event.target_content_id
                ):
                    keys_to_drop.append(binding_key)
        else:
            # create / replace / unlink — whole content scope
            for binding_key, binding in self._bindings.items():
                if scope_match(binding, event.content_id):
                    keys_to_drop.append(binding_key)

        # Also consult CachedStorage's side map when available so entries
        # admitted without note_admitted still get exact invalidation.
        if self._storage is not None:
            storage_bindings = getattr(self._storage, "_bindings", None)
            if isinstance(storage_bindings, dict):
                for binding_key, binding in list(storage_bindings.items()):
                    if not isinstance(binding, RangeBinding):
                        continue
                    if event.kind is CoherenceMutationKind.WRITE:
                        if self._write_affects(
                            event, binding, generation=generation
                        ):
                            keys_to_drop.append(binding_key)
                    elif event.kind is CoherenceMutationKind.TRUNCATE:
                        if self._truncate_affects(
                            event, binding, generation=generation
                        ):
                            keys_to_drop.append(binding_key)
                    elif event.kind is CoherenceMutationKind.RENAME:
                        if (
                            binding.namespace == event.namespace
                            and binding.content_id
                            in {event.content_id, event.target_content_id}
                        ):
                            keys_to_drop.append(binding_key)
                    else:
                        if (
                            binding.namespace == event.namespace
                            and binding.content_id == event.content_id
                        ):
                            keys_to_drop.append(binding_key)

        # Deduplicate while preserving order.
        seen: set[str] = set()
        unique_keys: list[str] = []
        for key in keys_to_drop:
            if key not in seen:
                seen.add(key)
                unique_keys.append(key)

        removed = 0
        invalidated_keys: list[str] = []
        for key in unique_keys:
            binding = self._bindings.get(key)
            if binding is None and self._storage is not None:
                storage_bindings = getattr(self._storage, "_bindings", None)
                if isinstance(storage_bindings, dict):
                    binding = storage_bindings.get(key)
            if binding is not None:
                if self._drop_binding_locked(binding):
                    removed += 1
                    invalidated_keys.append(key)
            else:
                # Best-effort: delete by cache key on the raw ARC if present.
                if self._storage is not None:
                    cache = getattr(self._storage, "cache", None)
                    if cache is not None and hasattr(cache, "delete"):
                        try:
                            if cache.delete(key):
                                removed += 1
                                invalidated_keys.append(key)
                        except Exception:  # noqa: BLE001
                            pass

        # Optional whole-object invalidate_arc for non-range facades.
        if self._invalidate_arc is not None and event.kind in _WHOLE_SCOPE_KINDS:
            try:
                extra = self._invalidate_arc.invalidate(
                    content_id=event.content_id, namespace=event.namespace
                )
                removed += int(extra or 0)
            except Exception:  # noqa: BLE001
                pass
            if event.kind is CoherenceMutationKind.RENAME and event.target_content_id:
                try:
                    extra = self._invalidate_arc.invalidate(
                        content_id=event.target_content_id,
                        namespace=event.namespace,
                    )
                    removed += int(extra or 0)
                except Exception:  # noqa: BLE001
                    pass

        return invalidated_keys, removed

    def _select_write_keys_locked(
        self, event: CoherenceEvent, *, generation: str
    ) -> list[str]:
        keys: list[str] = []
        for key, binding in self._bindings.items():
            if self._write_affects(event, binding, generation=generation):
                keys.append(key)
        return keys

    def _select_truncate_keys_locked(
        self, event: CoherenceEvent, *, generation: str
    ) -> list[str]:
        keys: list[str] = []
        for key, binding in self._bindings.items():
            if self._truncate_affects(event, binding, generation=generation):
                keys.append(key)
        return keys

    @staticmethod
    def _write_affects(
        event: CoherenceEvent,
        binding: RangeBinding,
        *,
        generation: str,
    ) -> bool:
        if binding.namespace != event.namespace:
            return False
        if binding.content_id != event.content_id:
            return False
        # Generation advance: every prior-generation binding for the scope is
        # stale and must not remain admitable.
        if binding.generation != generation:
            return True
        # Same generation (rare re-publish): range-aware exact invalidation.
        if event.offset is None or event.length is None or event.length == 0:
            return True
        try:
            return ranges_overlap(
                event.offset, max(event.length, 1), binding.offset, binding.length
            )
        except (RangeExtentError, ValueError):
            return True

    @staticmethod
    def _truncate_affects(
        event: CoherenceEvent,
        binding: RangeBinding,
        *,
        generation: str,
    ) -> bool:
        if binding.namespace != event.namespace:
            return False
        if binding.content_id != event.content_id:
            return False
        # Generation advance drops all prior-generation ranges.
        if binding.generation != generation:
            return True
        if event.size is None:
            return True
        # Same generation: only ranges past the new size are affected.
        return binding.end > event.size

    def _clear_dirty_locked(
        self,
        event: CoherenceEvent,
        scopes: Sequence[tuple[str, str]],
    ) -> int:
        if self._storage is None:
            return 0
        cleared = 0
        for namespace, content_id in scopes:
            try:
                if self._storage.clear_dirty(
                    namespace=namespace, content_id=content_id, version=None
                ):
                    cleared += 1
            except Exception:  # noqa: BLE001
                pass
            if event.version:
                try:
                    if self._storage.clear_dirty(
                        namespace=namespace,
                        content_id=content_id,
                        version=event.version,
                    ):
                        cleared += 1
                except Exception:  # noqa: BLE001
                    pass
            if event.prior_version:
                try:
                    if self._storage.clear_dirty(
                        namespace=namespace,
                        content_id=content_id,
                        version=event.prior_version,
                    ):
                        cleared += 1
                except Exception:  # noqa: BLE001
                    pass
        return cleared

    def _drop_binding_locked(self, binding: RangeBinding) -> bool:
        removed = False
        key = binding.cache_key
        if key in self._bindings:
            del self._bindings[key]
            removed = True
        if self._storage is not None:
            try:
                if self._storage.delete(binding):
                    removed = True
            except Exception:  # noqa: BLE001
                # Fall back to raw cache key delete.
                cache = getattr(self._storage, "cache", None)
                if cache is not None and hasattr(cache, "delete"):
                    try:
                        if cache.delete(key):
                            removed = True
                    except Exception:  # noqa: BLE001
                        pass
                storage_bindings = getattr(self._storage, "_bindings", None)
                if isinstance(storage_bindings, dict):
                    storage_bindings.pop(key, None)
        return removed

    def _count_kind_locked(self, kind: CoherenceMutationKind) -> None:
        if kind is CoherenceMutationKind.CREATE:
            self._metrics.create_events += 1
        elif kind is CoherenceMutationKind.REPLACE:
            self._metrics.replace_events += 1
        elif kind is CoherenceMutationKind.WRITE:
            self._metrics.write_events += 1
        elif kind is CoherenceMutationKind.TRUNCATE:
            self._metrics.truncate_events += 1
        elif kind is CoherenceMutationKind.UNLINK:
            self._metrics.unlink_events += 1
        elif kind is CoherenceMutationKind.RENAME:
            self._metrics.rename_events += 1

    @staticmethod
    def _coerce_binding(
        binding: RangeBinding | Mapping[str, Any],
    ) -> RangeBinding:
        if isinstance(binding, RangeBinding):
            return binding
        return RangeBinding.from_dict(binding)

    def assert_invariants(self) -> None:
        """Assert bookkeeping hygiene (for tests)."""

        with self._lock:
            for key, binding in self._bindings.items():
                assert key == binding.cache_key
            # No fence should linger outside a publish call.
            # (Callers may observe fences only during concurrent publish.)
            if self._storage is not None:
                self._storage.assert_invariants()


# Public aliases matching plan vocabulary.
CoherenceProjector = CacheCoherence
GenerationAdvance = CacheCoherence
DurableCacheCoherence = CacheCoherence


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "SCHEMA_MAJOR",
    "CACHE_COHERENCE_SCHEMA",
    "COHERENCE_PROJECTOR_SCHEMA",
    "COHERENCE_EVENT_SCHEMA",
    "COHERENCE_RECEIPT_SCHEMA",
    "COHERENCE_METRICS_SCHEMA",
    "GENERATION_ADVANCE_SCHEMA",
    "CacheCoherence_V1",
    "CoherenceProjector_V1",
    "GenerationAdvance_V1",
    "MAX_TRACKED_BINDINGS",
    "MAX_GENERATION_SCOPES",
    "DEFAULT_CONTENT_PREFIX",
    "CoherenceMutationKind",
    "CoherenceDisposition",
    "CoherenceAction",
    "CoherenceSource",
    "CoherenceError",
    "CoherenceValidationError",
    "CoherenceAdmissionBlocked",
    "path_to_content_id",
    "next_generation",
    "CoherenceEvent",
    "CoherenceReceipt",
    "CoherenceMetrics",
    "CacheCoherence",
    "CoherenceProjector",
    "GenerationAdvance",
    "DurableCacheCoherence",
    # Re-exports for call-site convenience.
    "RangeBinding",
    "CachedStorage",
    "DirtyScope",
]
