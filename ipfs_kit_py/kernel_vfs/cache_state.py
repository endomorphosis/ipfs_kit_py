"""Post-recovery ARC persistence, corruption policy, and metrics (KVFS-403).

This module owns the *cache startup / persistence / metrics integration*
surface that sits on top of generation-bound range ARC (KVFS-400), committed
read-through (KVFS-401), and durable event-to-cache projection (KVFS-404):

* **WAL recovery precedes cache admission** — persisted entries are never
  admitted into the live ARC until recovery has been marked complete for the
  mount generation;
* **Persisted entries require compatible schema, revision, namespace,
  generation, and checksums** — any mismatch is a safe miss;
* **Stale or corrupt state never poisons live cache** — a failed load leaves
  the target untouched and counts as a miss;
* **Atomic persistence and bounded startup/shutdown work** — write via
  same-directory temp + fsync + replace; entry and byte ceilings bound work;
* **hits / misses / evictions / bytes / single-flight / invalidation** expose
  low-cardinality counters only (no high-cardinality labels).

Conflict policy (KVFS-403): own cache startup/persistence/metrics integration
only.  This module does not import fusepy, open host mounts, or perform
network I/O.

Interfaces (plan aliases): ``CacheState@1``, ``PostRecoveryAdmission@1``,
``CacheStateMetrics@1``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Final, Protocol, runtime_checkable

from ipfs_kit_py.cache.arc.contracts import MAX_SAFE_INTEGER, require_bounded_int
from ipfs_kit_py.cache.arc.range_bindings import (
    DEFAULT_GENERATION,
    DEFAULT_NAMESPACE,
    RangeBinding,
    RangeIdentityError,
)
from ipfs_kit_py.kernel_vfs.cache_coherence import CacheCoherence
from ipfs_kit_py.kernel_vfs.cached_storage import CachedStorage

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-403"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

CACHE_STATE_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/cache_state"

CACHE_STATE_SCHEMA: Final[str] = (
    f"{CACHE_STATE_NAMESPACE}/cache-state@{SCHEMA_MAJOR}"
)
POST_RECOVERY_ADMISSION_SCHEMA: Final[str] = (
    f"{CACHE_STATE_NAMESPACE}/post-recovery-admission@{SCHEMA_MAJOR}"
)
CACHE_STATE_METRICS_SCHEMA: Final[str] = (
    f"{CACHE_STATE_NAMESPACE}/cache-state-metrics@{SCHEMA_MAJOR}"
)
CACHE_STATE_RECEIPT_SCHEMA: Final[str] = (
    f"{CACHE_STATE_NAMESPACE}/cache-state-receipt@{SCHEMA_MAJOR}"
)
PERSISTENCE_SCHEMA: Final[str] = (
    f"{CACHE_STATE_NAMESPACE}/persistence@{SCHEMA_MAJOR}"
)
PERSISTENCE_REVISION: Final[int] = 1

# Public interface aliases.
CacheState_V1: Final[str] = CACHE_STATE_SCHEMA
PostRecoveryAdmission_V1: Final[str] = POST_RECOVERY_ADMISSION_SCHEMA
CacheStateMetrics_V1: Final[str] = CACHE_STATE_METRICS_SCHEMA

DEFAULT_STATE_FILENAME: Final[str] = "arc-cache-state.json"
DEFAULT_MOUNT_NAMESPACE: Final[str] = DEFAULT_NAMESPACE

# Bounds keep startup/shutdown work finite and the on-disk envelope small.
MAX_PERSISTENCE_BYTES: Final[int] = 16 * 1024 * 1024
MAX_PERSISTED_ENTRIES: Final[int] = 16_384
MAX_PERSISTED_VALUE_BYTES: Final[int] = 8 * 1024 * 1024
MAX_GENERATION_SCOPES: Final[int] = 65_536
MAX_IDENTITY_BYTES: Final[int] = 512
MAX_PATH_BYTES: Final[int] = 4_096
MAX_TEXT_BYTES: Final[int] = 4_096
DEFAULT_STARTUP_BUDGET_SECONDS: Final[float] = 30.0
DEFAULT_SHUTDOWN_BUDGET_SECONDS: Final[float] = 30.0

# Envelope field sets (closed shapes for fail-closed decode).
_ENVELOPE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "version",
        "revision",
        "namespace",
        "generation",
        "generations",
        "entries",
        "sha256",
    }
)
_ENTRY_FIELDS: Final[frozenset[str]] = frozenset(
    {"binding", "value", "sha256"}
)


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class CacheLifecyclePhase(str, Enum):
    """Ordered phases of post-recovery cache state management."""

    UNINITIALIZED = "uninitialized"
    AWAITING_WAL_RECOVERY = "awaiting_wal_recovery"
    WAL_RECOVERED = "wal_recovered"
    ADMITTING = "admitting"
    READY = "ready"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"
    FAILED = "failed"


class AdmissionDisposition(str, Enum):
    """Closed outcome of one post-recovery admission attempt."""

    ADMITTED = "admitted"
    EMPTY = "empty"
    SAFE_MISS = "safe_miss"
    SCHEMA_REJECTED = "schema_rejected"
    STALE_REJECTED = "stale_rejected"
    CORRUPT = "corrupt"
    BLOCKED_PRE_RECOVERY = "blocked_pre_recovery"
    BUDGET_EXCEEDED = "budget_exceeded"
    SKIPPED = "skipped"


class PersistenceDisposition(str, Enum):
    """Closed outcome of one atomic persistence attempt."""

    WRITTEN = "written"
    EMPTY = "empty"
    SKIPPED = "skipped"
    FAILED = "failed"
    BUDGET_EXCEEDED = "budget_exceeded"


class CorruptionPolicy(str, Enum):
    """How corrupt or stale persisted state is handled.

    Only the fail-closed policy is implemented: the whole snapshot is a safe
    miss and live ARC is never partially replaced by untrusted entries.
    """

    SAFE_MISS = "safe_miss"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CacheStateError(Exception):
    """Base class for cache-state integration failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "CACHE_STATE_ERROR",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "message": self.message,
            "code": self.code,
            "detail": dict(self.detail),
        }


class CacheStateValidationError(CacheStateError):
    """Input validation failure for cache-state configuration or payloads."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="CACHE_STATE_VALIDATION", detail=detail)


class CacheAdmissionBlocked(CacheStateError):
    """Admission requested before WAL recovery completed."""

    def __init__(
        self,
        message: str = "cache admission blocked until WAL recovery completes",
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="CACHE_ADMISSION_BLOCKED",
            detail=detail,
        )


class CacheStateBudgetError(CacheStateError):
    """Startup or shutdown work exceeded the declared bound."""

    def __init__(
        self,
        message: str = "cache-state work exceeded declared budget",
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="CACHE_STATE_BUDGET",
            detail=detail,
        )


class CacheStatePersistenceError(CacheStateError):
    """Atomic persistence write misuse (not a safe-miss path)."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="CACHE_STATE_PERSISTENCE",
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bounded_text(
    value: Any,
    name: str,
    *,
    limit: int = MAX_IDENTITY_BYTES,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise CacheStateValidationError(
            f"{name} must be a str",
            detail={"field": name, "type": type(value).__name__},
        )
    if not allow_empty and not value:
        raise CacheStateValidationError(
            f"{name} must be a non-empty str",
            detail={"field": name},
        )
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise CacheStateValidationError(
            f"{name} must not contain control characters",
            detail={"field": name},
        )
    encoded = value.encode("utf-8")
    if len(encoded) > limit:
        raise CacheStateValidationError(
            f"{name} exceeds {limit} bytes",
            detail={"field": name, "bytes": len(encoded)},
        )
    return value


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _value_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path(value: str | os.PathLike[str] | Path, name: str = "path") -> Path:
    try:
        path = Path(value)
    except (TypeError, ValueError) as exc:
        raise CacheStateValidationError(
            f"{name} is not a valid path",
            detail={"field": name, "value": repr(value)},
        ) from exc
    text = str(path)
    if len(text.encode("utf-8", errors="replace")) > MAX_PATH_BYTES:
        raise CacheStateValidationError(
            f"{name} exceeds {MAX_PATH_BYTES} bytes",
            detail={"field": name},
        )
    return path


# ---------------------------------------------------------------------------
# Metrics / receipts
# ---------------------------------------------------------------------------


@dataclass
class CacheStateMetrics:
    """Low-cardinality counters for post-recovery cache integration.

    Only closed counter names are exposed — no content ids, paths, or other
    high-cardinality labels.  Callers may scrape :meth:`to_dict` directly.
    """

    SCHEMA: ClassVar[str] = CACHE_STATE_METRICS_SCHEMA

    # Access / residency (low cardinality).
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    bytes_resident: int = 0
    bytes_served: int = 0
    bytes_admitted: int = 0
    bytes_persisted: int = 0

    # Single-flight coordination.
    single_flight_leads: int = 0
    single_flight_joins: int = 0
    single_flight_failures: int = 0
    single_flight_cancels: int = 0

    # Invalidation / coherence projection.
    invalidations: int = 0
    generation_advances: int = 0

    # Persistence / corruption policy.
    persistence_writes: int = 0
    persistence_loads: int = 0
    persistence_corrupt: int = 0
    persistence_schema_rejections: int = 0
    persistence_stale_rejections: int = 0
    persistence_checksum_rejections: int = 0
    persistence_namespace_rejections: int = 0
    persistence_revision_rejections: int = 0

    # Startup / recovery gate.
    wal_recovery_notes: int = 0
    admission_before_recovery_blocks: int = 0
    entries_admitted: int = 0
    entries_skipped: int = 0
    startups: int = 0
    shutdowns: int = 0
    safe_misses: int = 0

    def snapshot(self) -> "CacheStateMetrics":
        return CacheStateMetrics(
            hits=self.hits,
            misses=self.misses,
            evictions=self.evictions,
            bytes_resident=self.bytes_resident,
            bytes_served=self.bytes_served,
            bytes_admitted=self.bytes_admitted,
            bytes_persisted=self.bytes_persisted,
            single_flight_leads=self.single_flight_leads,
            single_flight_joins=self.single_flight_joins,
            single_flight_failures=self.single_flight_failures,
            single_flight_cancels=self.single_flight_cancels,
            invalidations=self.invalidations,
            generation_advances=self.generation_advances,
            persistence_writes=self.persistence_writes,
            persistence_loads=self.persistence_loads,
            persistence_corrupt=self.persistence_corrupt,
            persistence_schema_rejections=self.persistence_schema_rejections,
            persistence_stale_rejections=self.persistence_stale_rejections,
            persistence_checksum_rejections=self.persistence_checksum_rejections,
            persistence_namespace_rejections=self.persistence_namespace_rejections,
            persistence_revision_rejections=self.persistence_revision_rejections,
            wal_recovery_notes=self.wal_recovery_notes,
            admission_before_recovery_blocks=self.admission_before_recovery_blocks,
            entries_admitted=self.entries_admitted,
            entries_skipped=self.entries_skipped,
            startups=self.startups,
            shutdowns=self.shutdowns,
            safe_misses=self.safe_misses,
        )

    def to_dict(self) -> dict[str, int]:
        """Return a flat low-cardinality counter map."""

        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "bytes_resident": self.bytes_resident,
            "bytes_served": self.bytes_served,
            "bytes_admitted": self.bytes_admitted,
            "bytes_persisted": self.bytes_persisted,
            "single_flight_leads": self.single_flight_leads,
            "single_flight_joins": self.single_flight_joins,
            "single_flight_failures": self.single_flight_failures,
            "single_flight_cancels": self.single_flight_cancels,
            "invalidations": self.invalidations,
            "generation_advances": self.generation_advances,
            "persistence_writes": self.persistence_writes,
            "persistence_loads": self.persistence_loads,
            "persistence_corrupt": self.persistence_corrupt,
            "persistence_schema_rejections": self.persistence_schema_rejections,
            "persistence_stale_rejections": self.persistence_stale_rejections,
            "persistence_checksum_rejections": self.persistence_checksum_rejections,
            "persistence_namespace_rejections": self.persistence_namespace_rejections,
            "persistence_revision_rejections": self.persistence_revision_rejections,
            "wal_recovery_notes": self.wal_recovery_notes,
            "admission_before_recovery_blocks": self.admission_before_recovery_blocks,
            "entries_admitted": self.entries_admitted,
            "entries_skipped": self.entries_skipped,
            "startups": self.startups,
            "shutdowns": self.shutdowns,
            "safe_misses": self.safe_misses,
        }


# Closed metric name set for observe_* helpers (fail-closed).
_METRIC_NAMES: Final[frozenset[str]] = frozenset(CacheStateMetrics().to_dict())


@dataclass(frozen=True)
class CacheStateReceipt:
    """Immutable receipt for one startup, admission, or shutdown step."""

    SCHEMA: ClassVar[str] = CACHE_STATE_RECEIPT_SCHEMA

    phase: CacheLifecyclePhase
    disposition: str
    wal_recovered: bool = False
    mount_generation: str = ""
    namespace: str = ""
    entries_considered: int = 0
    entries_admitted: int = 0
    entries_skipped: int = 0
    bytes_admitted: int = 0
    bytes_persisted: int = 0
    path: str = ""
    reason: str = ""
    elapsed_seconds: float = 0.0
    corruption_policy: str = CorruptionPolicy.SAFE_MISS.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "phase": self.phase.value,
            "disposition": self.disposition,
            "wal_recovered": self.wal_recovered,
            "mount_generation": self.mount_generation,
            "namespace": self.namespace,
            "entries_considered": self.entries_considered,
            "entries_admitted": self.entries_admitted,
            "entries_skipped": self.entries_skipped,
            "bytes_admitted": self.bytes_admitted,
            "bytes_persisted": self.bytes_persisted,
            "path": self.path,
            "reason": self.reason,
            "elapsed_seconds": self.elapsed_seconds,
            "corruption_policy": self.corruption_policy,
        }


# ---------------------------------------------------------------------------
# Optional storage / coherence surfaces
# ---------------------------------------------------------------------------


@runtime_checkable
class SupportsCommittedPut(Protocol):
    def put_committed(
        self,
        binding: RangeBinding | Mapping[str, Any],
        value: bytes,
        *,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
    ) -> bool: ...

    def get(
        self,
        binding: RangeBinding | Mapping[str, Any],
        *,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
    ) -> bytes | None: ...

    def delete(self, binding: RangeBinding | Mapping[str, Any]) -> bool: ...


@runtime_checkable
class SupportsCoherenceNote(Protocol):
    def note_admitted(self, binding: RangeBinding | Mapping[str, Any]) -> None: ...

    def active_generation(
        self, content_id: str, *, namespace: str = DEFAULT_NAMESPACE
    ) -> str | None: ...


# ---------------------------------------------------------------------------
# Persistence encode / decode (range-aware, data-only)
# ---------------------------------------------------------------------------


def _encode_entry(binding: RangeBinding, value: bytes) -> dict[str, Any]:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise CacheStatePersistenceError(
            "persisted value must be bytes-like",
            detail={"type": type(value).__name__},
        )
    data = bytes(value)
    if len(data) > MAX_PERSISTED_VALUE_BYTES:
        raise CacheStatePersistenceError(
            "persisted value exceeds byte limit",
            detail={"bytes": len(data), "limit": MAX_PERSISTED_VALUE_BYTES},
        )
    if len(data) != binding.length:
        raise CacheStatePersistenceError(
            "value length disagrees with binding length",
            detail={"value_len": len(data), "binding_length": binding.length},
        )
    return {
        "binding": binding.to_dict(),
        "value": base64.b64encode(data).decode("ascii"),
        "sha256": _value_digest(data),
    }


def _decode_entry(raw: Any) -> tuple[RangeBinding, bytes] | None:
    """Decode one entry or return ``None`` for a per-entry safe miss."""

    if not isinstance(raw, dict) or set(raw) != _ENTRY_FIELDS:
        return None
    binding_raw, encoded, checksum = raw["binding"], raw["value"], raw["sha256"]
    if not isinstance(encoded, str) or not isinstance(checksum, str):
        return None
    if len(encoded) > (MAX_PERSISTED_VALUE_BYTES * 4 // 3) + 8:
        return None
    try:
        data = base64.b64decode(encoded.encode("ascii"), validate=True)
        identity = RangeBinding.from_dict(binding_raw)
    except (
        UnicodeEncodeError,
        ValueError,
        TypeError,
        RangeIdentityError,
        CacheStateValidationError,
    ):
        return None
    if len(data) > MAX_PERSISTED_VALUE_BYTES:
        return None
    if len(data) != identity.length:
        return None
    if _value_digest(data) != checksum:
        return None
    return identity, data


def build_persistence_envelope(
    entries: Sequence[tuple[RangeBinding, bytes]],
    *,
    namespace: str,
    generation: str,
    generations: Mapping[tuple[str, str], str] | None = None,
    revision: int = PERSISTENCE_REVISION,
) -> dict[str, Any]:
    """Build a canonical persistence envelope (without writing it)."""

    namespace = _bounded_text(namespace, "namespace")
    generation = _bounded_text(generation, "generation")
    revision = require_bounded_int(
        revision, name="revision", minimum=1, maximum=MAX_SAFE_INTEGER
    )
    if len(entries) > MAX_PERSISTED_ENTRIES:
        raise CacheStatePersistenceError(
            "too many cache entries for persistence envelope",
            detail={"count": len(entries), "limit": MAX_PERSISTED_ENTRIES},
        )
    encoded_entries: list[dict[str, Any]] = []
    for binding, value in entries:
        if not isinstance(binding, RangeBinding):
            raise CacheStatePersistenceError(
                "entry binding must be a RangeBinding",
            )
        encoded_entries.append(_encode_entry(binding, value))

    gen_map: dict[str, str] = {}
    if generations:
        if len(generations) > MAX_GENERATION_SCOPES:
            raise CacheStatePersistenceError(
                "too many generation scopes for persistence envelope",
                detail={"count": len(generations)},
            )
        for scope, gen in generations.items():
            if (
                not isinstance(scope, tuple)
                or len(scope) != 2
                or not isinstance(scope[0], str)
                or not isinstance(scope[1], str)
            ):
                raise CacheStatePersistenceError(
                    "generation scope must be (namespace, content_id)",
                )
            key = f"{scope[0]}\0{scope[1]}"
            gen_map[key] = _bounded_text(gen, "generation")

    payload = {
        "schema": PERSISTENCE_SCHEMA,
        "version": CONTRACT_VERSION,
        "revision": revision,
        "namespace": namespace,
        "generation": generation,
        "generations": gen_map,
        "entries": encoded_entries,
    }
    return {**payload, "sha256": _digest(payload)}


def atomic_write_envelope(
    path: str | os.PathLike[str] | Path,
    envelope: Mapping[str, Any],
) -> int:
    """Atomically write a persistence envelope; return encoded byte length."""

    destination = _path(path)
    encoded = _canonical_json(dict(envelope))
    if len(encoded) > MAX_PERSISTENCE_BYTES:
        raise CacheStatePersistenceError(
            "persistence envelope exceeds byte limit",
            detail={"bytes": len(encoded), "limit": MAX_PERSISTENCE_BYTES},
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        try:
            directory_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # Directory fsync is unavailable on some platforms; replacement
            # has still completed atomically on the local filesystem.
            pass
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return len(encoded)


def load_persistence_envelope(
    path: str | os.PathLike[str] | Path,
) -> dict[str, Any] | None:
    """Load and structurally validate an envelope, or return ``None``."""

    try:
        with _path(path).open("rb") as handle:
            data = handle.read(MAX_PERSISTENCE_BYTES + 1)
        if len(data) > MAX_PERSISTENCE_BYTES:
            return None
        decoded = json.loads(data.decode("utf-8"))
        if not isinstance(decoded, dict) or set(decoded) != _ENVELOPE_FIELDS:
            return None
        payload = {key: decoded[key] for key in (
            "schema",
            "version",
            "revision",
            "namespace",
            "generation",
            "generations",
            "entries",
        )}
        if not isinstance(decoded["sha256"], str) or _digest(payload) != decoded["sha256"]:
            return None
        return decoded
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
        RecursionError,
        CacheStateValidationError,
    ):
        return None


# ---------------------------------------------------------------------------
# CacheState
# ---------------------------------------------------------------------------


class CacheState:
    """Post-recovery ARC persistence coordinator with corruption policy.

    Lifecycle (happy path)::

        UNINITIALIZED
          -> begin_startup()           # AWAITING_WAL_RECOVERY
          -> note_wal_recovery(...)    # WAL_RECOVERED  (required gate)
          -> admit_persisted()         # ADMITTING -> READY
          ... live hits / misses / invalidations ...
          -> shutdown()                # SHUTTING_DOWN -> SHUTDOWN
             (atomic persist under budget)

    Admission of persisted entries, and of live committed puts through this
    façade, is blocked until :meth:`note_wal_recovery` has succeeded.
    """

    SCHEMA: ClassVar[str] = CACHE_STATE_SCHEMA
    CONTRACT_VERSION: ClassVar[int] = CONTRACT_VERSION
    INTERFACE: ClassVar[str] = CacheState_V1

    def __init__(
        self,
        storage: CachedStorage | SupportsCommittedPut | None = None,
        *,
        coherence: CacheCoherence | SupportsCoherenceNote | None = None,
        state_path: str | os.PathLike[str] | Path | None = None,
        namespace: str = DEFAULT_MOUNT_NAMESPACE,
        mount_generation: str = DEFAULT_GENERATION,
        corruption_policy: CorruptionPolicy | str = CorruptionPolicy.SAFE_MISS,
        startup_budget_seconds: float = DEFAULT_STARTUP_BUDGET_SECONDS,
        shutdown_budget_seconds: float = DEFAULT_SHUTDOWN_BUDGET_SECONDS,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
        auto_create_storage: bool = True,
        capacity_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        namespace = _bounded_text(namespace, "namespace")
        mount_generation = _bounded_text(mount_generation, "mount_generation")
        if not isinstance(corruption_policy, CorruptionPolicy):
            try:
                corruption_policy = CorruptionPolicy(corruption_policy)
            except (TypeError, ValueError) as exc:
                raise CacheStateValidationError(
                    f"unknown corruption_policy: {corruption_policy!r}",
                ) from exc
        if corruption_policy is not CorruptionPolicy.SAFE_MISS:
            raise CacheStateValidationError(
                "only CorruptionPolicy.SAFE_MISS is supported",
                detail={"policy": str(corruption_policy)},
            )
        startup_budget_seconds = float(startup_budget_seconds)
        shutdown_budget_seconds = float(shutdown_budget_seconds)
        if (
            startup_budget_seconds <= 0
            or shutdown_budget_seconds <= 0
            or startup_budget_seconds != startup_budget_seconds
            or shutdown_budget_seconds != shutdown_budget_seconds
        ):
            raise CacheStateValidationError(
                "startup/shutdown budgets must be positive finite seconds",
            )

        if storage is None and auto_create_storage:
            storage = CachedStorage(
                capacity_bytes=capacity_bytes,
                authorize=authorize or (lambda _b: True),
                consistent=consistent or (lambda _b: True),
            )

        self._lock = threading.RLock()
        self._storage = storage
        self._coherence = coherence
        self._state_path = (
            None if state_path is None else _path(state_path, "state_path")
        )
        self._namespace = namespace
        self._mount_generation = mount_generation
        self._corruption_policy = corruption_policy
        self._startup_budget_seconds = startup_budget_seconds
        self._shutdown_budget_seconds = shutdown_budget_seconds
        self._authorize = authorize
        self._consistent = consistent

        self._phase = CacheLifecyclePhase.UNINITIALIZED
        self._wal_recovered = False
        self._wal_recovery_generation = ""
        self._wal_recovery_detail: dict[str, Any] = {}
        # Active generation fences restored from persistence / coherence.
        self._generations: dict[tuple[str, str], str] = {}
        # Side map of admitted bindings for export on shutdown.
        self._bindings: dict[str, RangeBinding] = {}
        self._metrics = CacheStateMetrics()
        self._last_startup: CacheStateReceipt | None = None
        self._last_shutdown: CacheStateReceipt | None = None
        self._startup_deadline: float | None = None

    # --- properties --------------------------------------------------------

    @property
    def storage(self) -> CachedStorage | SupportsCommittedPut | None:
        return self._storage

    @property
    def coherence(self) -> CacheCoherence | SupportsCoherenceNote | None:
        return self._coherence

    @property
    def phase(self) -> CacheLifecyclePhase:
        with self._lock:
            return self._phase

    @property
    def wal_recovered(self) -> bool:
        with self._lock:
            return self._wal_recovered

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def mount_generation(self) -> str:
        with self._lock:
            return self._mount_generation

    @property
    def state_path(self) -> Path | None:
        return self._state_path

    @property
    def corruption_policy(self) -> CorruptionPolicy:
        return self._corruption_policy

    def metrics(self) -> CacheStateMetrics:
        with self._lock:
            return self._metrics.snapshot()

    def last_startup_receipt(self) -> CacheStateReceipt | None:
        with self._lock:
            return self._last_startup

    def last_shutdown_receipt(self) -> CacheStateReceipt | None:
        with self._lock:
            return self._last_shutdown

    def is_ready(self) -> bool:
        with self._lock:
            return self._phase is CacheLifecyclePhase.READY

    def may_admit(self) -> bool:
        """True when WAL recovery has completed and phase allows admission."""

        with self._lock:
            return self._may_admit_locked()

    def _may_admit_locked(self) -> bool:
        return self._wal_recovered and self._phase in {
            CacheLifecyclePhase.WAL_RECOVERED,
            CacheLifecyclePhase.ADMITTING,
            CacheLifecyclePhase.READY,
        }

    # --- lifecycle ---------------------------------------------------------

    def begin_startup(
        self,
        *,
        state_path: str | os.PathLike[str] | Path | None = None,
    ) -> CacheLifecyclePhase:
        """Enter the pre-recovery gate.  Does not admit any persisted entries."""

        with self._lock:
            if self._phase not in {
                CacheLifecyclePhase.UNINITIALIZED,
                CacheLifecyclePhase.SHUTDOWN,
                CacheLifecyclePhase.FAILED,
            }:
                raise CacheStateError(
                    f"cannot begin_startup from phase {self._phase.value}",
                    code="CACHE_STATE_PHASE",
                    detail={"phase": self._phase.value},
                )
            if state_path is not None:
                self._state_path = _path(state_path, "state_path")
            self._phase = CacheLifecyclePhase.AWAITING_WAL_RECOVERY
            self._wal_recovered = False
            self._wal_recovery_generation = ""
            self._wal_recovery_detail = {}
            self._startup_deadline = (
                time.monotonic() + self._startup_budget_seconds
            )
            return self._phase

    def note_wal_recovery(
        self,
        *,
        generation: str | None = None,
        receipt: Mapping[str, Any] | None = None,
        success: bool = True,
    ) -> CacheLifecyclePhase:
        """Record that WAL recovery completed.  Required before admission.

        ``success=False`` transitions to ``FAILED`` and never admits cache.
        """

        with self._lock:
            if self._phase is CacheLifecyclePhase.UNINITIALIZED:
                # Implicit begin for call sites that only note recovery.
                self._phase = CacheLifecyclePhase.AWAITING_WAL_RECOVERY
                self._startup_deadline = (
                    time.monotonic() + self._startup_budget_seconds
                )
            if self._phase not in {
                CacheLifecyclePhase.AWAITING_WAL_RECOVERY,
                CacheLifecyclePhase.WAL_RECOVERED,
            }:
                raise CacheStateError(
                    f"cannot note_wal_recovery from phase {self._phase.value}",
                    code="CACHE_STATE_PHASE",
                    detail={"phase": self._phase.value},
                )
            if not success:
                self._phase = CacheLifecyclePhase.FAILED
                self._wal_recovered = False
                self._metrics.wal_recovery_notes += 1
                return self._phase

            gen = generation
            if gen is None and receipt is not None:
                gen = (
                    receipt.get("generation")
                    or receipt.get("mount_generation")
                    or receipt.get("generation_id")
                    or ""
                )
            if not gen:
                gen = self._mount_generation
            gen = _bounded_text(gen, "generation")
            self._mount_generation = gen
            self._wal_recovery_generation = gen
            self._wal_recovered = True
            self._wal_recovery_detail = dict(receipt or {})
            self._phase = CacheLifecyclePhase.WAL_RECOVERED
            self._metrics.wal_recovery_notes += 1
            return self._phase

    def require_admission_allowed(self) -> None:
        """Raise :class:`CacheAdmissionBlocked` when the recovery gate is shut."""

        with self._lock:
            if not self._may_admit_locked():
                self._metrics.admission_before_recovery_blocks += 1
                raise CacheAdmissionBlocked(
                    detail={
                        "phase": self._phase.value,
                        "wal_recovered": self._wal_recovered,
                    }
                )

    def startup(
        self,
        *,
        state_path: str | os.PathLike[str] | Path | None = None,
        wal_generation: str | None = None,
        wal_receipt: Mapping[str, Any] | None = None,
        wal_recovered: bool = True,
    ) -> CacheStateReceipt:
        """Full startup: begin → note WAL recovery → admit persisted state.

        ``wal_recovered`` must be true (caller asserts recovery already ran).
        Passing ``wal_recovered=False`` fails closed without admission.
        """

        started = time.monotonic()
        self.begin_startup(state_path=state_path)
        if not wal_recovered:
            with self._lock:
                self._phase = CacheLifecyclePhase.FAILED
                self._metrics.admission_before_recovery_blocks += 1
                self._metrics.safe_misses += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.BLOCKED_PRE_RECOVERY.value,
                    wal_recovered=False,
                    mount_generation=self._mount_generation,
                    namespace=self._namespace,
                    path=str(self._state_path or ""),
                    reason="wal_recovery_incomplete",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt
        self.note_wal_recovery(
            generation=wal_generation,
            receipt=wal_receipt,
            success=True,
        )
        return self.admit_persisted()

    def admit_persisted(
        self,
        *,
        state_path: str | os.PathLike[str] | Path | None = None,
    ) -> CacheStateReceipt:
        """Admit a valid on-disk snapshot only after WAL recovery.

        Corrupt, stale, schema-mismatched, namespace-mismatched, or checksum-
        failing envelopes become a safe miss: the live cache is left empty of
        those entries and the phase still advances to ``READY`` so the mount
        can serve cold misses.
        """

        started = time.monotonic()
        with self._lock:
            if not self._wal_recovered:
                self._metrics.admission_before_recovery_blocks += 1
                self._metrics.safe_misses += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.BLOCKED_PRE_RECOVERY.value,
                    wal_recovered=False,
                    mount_generation=self._mount_generation,
                    namespace=self._namespace,
                    path=str(state_path or self._state_path or ""),
                    reason="wal_recovery_required",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt
            if self._phase not in {
                CacheLifecyclePhase.WAL_RECOVERED,
                CacheLifecyclePhase.READY,
            }:
                raise CacheStateError(
                    f"cannot admit_persisted from phase {self._phase.value}",
                    code="CACHE_STATE_PHASE",
                    detail={"phase": self._phase.value},
                )
            if state_path is not None:
                self._state_path = _path(state_path, "state_path")
            path = self._state_path
            self._phase = CacheLifecyclePhase.ADMITTING
            deadline = self._startup_deadline
            mount_gen = self._mount_generation
            namespace = self._namespace

        if path is None or not path.exists():
            with self._lock:
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.EMPTY.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path or ""),
                    reason="no_persisted_state",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

        if deadline is not None and time.monotonic() > deadline:
            with self._lock:
                self._phase = CacheLifecyclePhase.FAILED
                self._metrics.safe_misses += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.BUDGET_EXCEEDED.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="startup_budget_exceeded_before_load",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

        outcome = self._load_and_admit(path, started=started, deadline=deadline)
        return outcome

    def _load_and_admit(
        self,
        path: Path,
        *,
        started: float,
        deadline: float | None,
    ) -> CacheStateReceipt:
        envelope = load_persistence_envelope(path)
        with self._lock:
            namespace = self._namespace
            mount_gen = self._mount_generation

            if envelope is None:
                # Corrupt / unreadable — safe miss, still become READY.
                self._metrics.persistence_corrupt += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.CORRUPT.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="corrupt_or_unreadable_envelope",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            # Schema / revision / version.
            if (
                envelope.get("schema") != PERSISTENCE_SCHEMA
                or envelope.get("version") != CONTRACT_VERSION
            ):
                self._metrics.persistence_schema_rejections += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.SCHEMA_REJECTED.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="schema_or_version_mismatch",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            if envelope.get("revision") != PERSISTENCE_REVISION:
                self._metrics.persistence_revision_rejections += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.SCHEMA_REJECTED.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="revision_mismatch",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            if envelope.get("namespace") != namespace:
                self._metrics.persistence_namespace_rejections += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.STALE_REJECTED.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="namespace_mismatch",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            env_generation = envelope.get("generation")
            if not isinstance(env_generation, str) or not env_generation:
                self._metrics.persistence_corrupt += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.CORRUPT.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="missing_envelope_generation",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            # Mount generation fence: a snapshot from a different recovery
            # generation is stale relative to the just-recovered WAL.
            if env_generation != mount_gen:
                self._metrics.persistence_stale_rejections += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.STALE_REJECTED.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="mount_generation_mismatch",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            raw_entries = envelope.get("entries")
            if not isinstance(raw_entries, list):
                self._metrics.persistence_corrupt += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.CORRUPT.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="entries_not_a_list",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            if len(raw_entries) > MAX_PERSISTED_ENTRIES:
                self._metrics.persistence_corrupt += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.CORRUPT.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="entries_exceed_bound",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            # Decode *all* entries first (fail-closed atomic admission).
            decoded: list[tuple[RangeBinding, bytes]] = []
            checksum_failures = 0
            for raw in raw_entries:
                if deadline is not None and time.monotonic() > deadline:
                    self._metrics.safe_misses += 1
                    self._phase = CacheLifecyclePhase.FAILED
                    receipt = CacheStateReceipt(
                        phase=self._phase,
                        disposition=AdmissionDisposition.BUDGET_EXCEEDED.value,
                        wal_recovered=True,
                        mount_generation=mount_gen,
                        namespace=namespace,
                        path=str(path),
                        entries_considered=len(raw_entries),
                        reason="startup_budget_exceeded_during_decode",
                        elapsed_seconds=max(0.0, time.monotonic() - started),
                        corruption_policy=self._corruption_policy.value,
                    )
                    self._last_startup = receipt
                    return receipt
                item = _decode_entry(raw)
                if item is None:
                    checksum_failures += 1
                    continue
                decoded.append(item)

            if checksum_failures:
                # Any corrupt entry invalidates the whole snapshot (atomic).
                self._metrics.persistence_checksum_rejections += 1
                self._metrics.persistence_corrupt += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.CORRUPT.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    entries_considered=len(raw_entries),
                    entries_skipped=checksum_failures,
                    reason="entry_checksum_or_shape_failure",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            # Validate generation map and per-entry namespace / generation.
            raw_gens = envelope.get("generations")
            if not isinstance(raw_gens, dict):
                self._metrics.persistence_corrupt += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.CORRUPT.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="generations_not_a_mapping",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            candidate_gens: dict[tuple[str, str], str] = {}
            try:
                for key, gen in raw_gens.items():
                    if not isinstance(key, str) or "\0" not in key:
                        raise ValueError("bad generation key")
                    ns, cid = key.split("\0", 1)
                    ns = _bounded_text(ns, "generation.namespace")
                    cid = _bounded_text(cid, "generation.content_id")
                    gen_s = _bounded_text(gen, "generation.value")
                    candidate_gens[(ns, cid)] = gen_s
            except (CacheStateValidationError, ValueError, TypeError):
                self._metrics.persistence_corrupt += 1
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.CORRUPT.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="invalid_generation_map",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            # Cross-check entries against namespace and generation fences.
            for binding, _value in decoded:
                if binding.namespace != namespace:
                    self._metrics.persistence_namespace_rejections += 1
                    self._metrics.safe_misses += 1
                    self._phase = CacheLifecyclePhase.READY
                    self._metrics.startups += 1
                    receipt = CacheStateReceipt(
                        phase=self._phase,
                        disposition=AdmissionDisposition.STALE_REJECTED.value,
                        wal_recovered=True,
                        mount_generation=mount_gen,
                        namespace=namespace,
                        path=str(path),
                        entries_considered=len(decoded),
                        reason="entry_namespace_mismatch",
                        elapsed_seconds=max(0.0, time.monotonic() - started),
                        corruption_policy=self._corruption_policy.value,
                    )
                    self._last_startup = receipt
                    return receipt
                scope = (binding.namespace, binding.content_id)
                active = candidate_gens.get(scope)
                if active is not None and active != binding.generation:
                    self._metrics.persistence_stale_rejections += 1
                    self._metrics.safe_misses += 1
                    self._phase = CacheLifecyclePhase.READY
                    self._metrics.startups += 1
                    receipt = CacheStateReceipt(
                        phase=self._phase,
                        disposition=AdmissionDisposition.STALE_REJECTED.value,
                        wal_recovered=True,
                        mount_generation=mount_gen,
                        namespace=namespace,
                        path=str(path),
                        entries_considered=len(decoded),
                        reason="entry_generation_stale",
                        elapsed_seconds=max(0.0, time.monotonic() - started),
                        corruption_policy=self._corruption_policy.value,
                    )
                    self._last_startup = receipt
                    return receipt
                # Coherence fence: if live coherence already advanced past
                # the persisted generation, treat as stale.
                if self._coherence is not None:
                    try:
                        live_gen = self._coherence.active_generation(
                            binding.content_id, namespace=binding.namespace
                        )
                    except Exception:  # noqa: BLE001 — fail-closed
                        live_gen = None
                    if live_gen is not None and live_gen != binding.generation:
                        self._metrics.persistence_stale_rejections += 1
                        self._metrics.safe_misses += 1
                        self._phase = CacheLifecyclePhase.READY
                        self._metrics.startups += 1
                        receipt = CacheStateReceipt(
                            phase=self._phase,
                            disposition=AdmissionDisposition.STALE_REJECTED.value,
                            wal_recovered=True,
                            mount_generation=mount_gen,
                            namespace=namespace,
                            path=str(path),
                            entries_considered=len(decoded),
                            reason="coherence_generation_stale",
                            elapsed_seconds=max(
                                0.0, time.monotonic() - started
                            ),
                            corruption_policy=self._corruption_policy.value,
                        )
                        self._last_startup = receipt
                        return receipt

            if not decoded:
                self._metrics.persistence_loads += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.EMPTY.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    reason="empty_entries",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            # Atomic admission: all or nothing into storage.
            admitted = 0
            skipped = 0
            bytes_admitted = 0
            if self._storage is None:
                self._metrics.safe_misses += 1
                self._phase = CacheLifecyclePhase.READY
                self._metrics.startups += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=AdmissionDisposition.SKIPPED.value,
                    wal_recovered=True,
                    mount_generation=mount_gen,
                    namespace=namespace,
                    path=str(path),
                    entries_considered=len(decoded),
                    reason="no_storage_configured",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_startup = receipt
                return receipt

            # Stage into a temporary side-map; only commit bookkeeping after
            # every put succeeds so a capacity rejection is a full safe miss.
            staged: list[tuple[RangeBinding, bytes]] = []
            for binding, value in decoded:
                if deadline is not None and time.monotonic() > deadline:
                    self._metrics.safe_misses += 1
                    self._phase = CacheLifecyclePhase.FAILED
                    receipt = CacheStateReceipt(
                        phase=self._phase,
                        disposition=AdmissionDisposition.BUDGET_EXCEEDED.value,
                        wal_recovered=True,
                        mount_generation=mount_gen,
                        namespace=namespace,
                        path=str(path),
                        entries_considered=len(decoded),
                        reason="startup_budget_exceeded_during_admit",
                        elapsed_seconds=max(0.0, time.monotonic() - started),
                        corruption_policy=self._corruption_policy.value,
                    )
                    self._last_startup = receipt
                    return receipt
                try:
                    ok = self._storage.put_committed(
                        binding,
                        value,
                        authorize=self._authorize or (lambda _b: True),
                        consistent=self._consistent or (lambda _b: True),
                    )
                except Exception:  # noqa: BLE001 — safe miss
                    ok = False
                if not ok:
                    # Roll back any already-admitted entries from this batch.
                    for prior, _ in staged:
                        try:
                            self._storage.delete(prior)
                        except Exception:  # noqa: BLE001
                            pass
                        self._bindings.pop(prior.cache_key, None)
                    self._metrics.safe_misses += 1
                    self._metrics.entries_skipped += len(decoded)
                    self._phase = CacheLifecyclePhase.READY
                    self._metrics.startups += 1
                    receipt = CacheStateReceipt(
                        phase=self._phase,
                        disposition=AdmissionDisposition.SAFE_MISS.value,
                        wal_recovered=True,
                        mount_generation=mount_gen,
                        namespace=namespace,
                        path=str(path),
                        entries_considered=len(decoded),
                        entries_skipped=len(decoded),
                        reason="admission_rejected",
                        elapsed_seconds=max(0.0, time.monotonic() - started),
                        corruption_policy=self._corruption_policy.value,
                    )
                    self._last_startup = receipt
                    return receipt
                staged.append((binding, value))
                self._bindings[binding.cache_key] = binding
                if self._coherence is not None:
                    try:
                        self._coherence.note_admitted(binding)
                    except Exception:  # noqa: BLE001 — non-fatal
                        pass
                admitted += 1
                bytes_admitted += len(value)

            self._generations.update(candidate_gens)
            self._metrics.entries_admitted += admitted
            self._metrics.entries_skipped += skipped
            self._metrics.bytes_admitted += bytes_admitted
            self._metrics.bytes_resident = self._compute_bytes_resident_locked()
            self._metrics.persistence_loads += 1
            self._phase = CacheLifecyclePhase.READY
            self._metrics.startups += 1
            receipt = CacheStateReceipt(
                phase=self._phase,
                disposition=AdmissionDisposition.ADMITTED.value,
                wal_recovered=True,
                mount_generation=mount_gen,
                namespace=namespace,
                path=str(path),
                entries_considered=len(decoded),
                entries_admitted=admitted,
                entries_skipped=skipped,
                bytes_admitted=bytes_admitted,
                reason="admitted",
                elapsed_seconds=max(0.0, time.monotonic() - started),
                corruption_policy=self._corruption_policy.value,
            )
            self._last_startup = receipt
            return receipt

    # --- live get / put (gated) --------------------------------------------

    def put_committed(
        self,
        binding: RangeBinding | Mapping[str, Any],
        value: bytes,
        *,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
    ) -> bool:
        """Admit committed bytes only after WAL recovery."""

        self.require_admission_allowed()
        identity = self._coerce_binding(binding)
        if self._storage is None:
            return False
        auth = authorize if authorize is not None else self._authorize
        cons = consistent if consistent is not None else self._consistent
        ok = self._storage.put_committed(
            identity, value, authorize=auth, consistent=cons
        )
        if ok:
            with self._lock:
                self._bindings[identity.cache_key] = identity
                scope = (identity.namespace, identity.content_id)
                self._generations[scope] = identity.generation
                self._metrics.bytes_admitted += len(bytes(value))
                self._metrics.bytes_resident = (
                    self._compute_bytes_resident_locked()
                )
            if self._coherence is not None:
                try:
                    self._coherence.note_admitted(identity)
                except Exception:  # noqa: BLE001
                    pass
        else:
            with self._lock:
                self._metrics.misses += 1
        return ok

    def get(
        self,
        binding: RangeBinding | Mapping[str, Any],
        *,
        authorize: Callable[[RangeBinding], bool] | None = None,
        consistent: Callable[[RangeBinding], bool] | None = None,
    ) -> bytes | None:
        """Return a revalidated hit, counting low-cardinality hit/miss metrics.

        Pre-recovery gets are safe misses (never raise); they cannot bypass the
        recovery gate into a hit.
        """

        identity = self._coerce_binding(binding)
        with self._lock:
            if not self._may_admit_locked():
                self._metrics.admission_before_recovery_blocks += 1
                self._metrics.misses += 1
                self._metrics.safe_misses += 1
                return None
        if self._storage is None:
            with self._lock:
                self._metrics.misses += 1
            return None
        auth = authorize if authorize is not None else self._authorize
        cons = consistent if consistent is not None else self._consistent
        # Default fail-closed predicates when storage requires them.
        if auth is None:
            auth = lambda _b: True  # noqa: E731
        if cons is None:
            cons = lambda _b: True  # noqa: E731
        value = self._storage.get(identity, authorize=auth, consistent=cons)
        with self._lock:
            if value is None:
                self._metrics.misses += 1
            else:
                self._metrics.hits += 1
                self._metrics.bytes_served += len(value)
        return value

    def note_invalidation(self, count: int = 1) -> None:
        """Record low-cardinality invalidation events (from coherence)."""

        count = require_bounded_int(
            count, name="count", minimum=0, maximum=MAX_SAFE_INTEGER
        )
        with self._lock:
            self._metrics.invalidations += count

    def note_generation_advance(self, count: int = 1) -> None:
        count = require_bounded_int(
            count, name="count", minimum=0, maximum=MAX_SAFE_INTEGER
        )
        with self._lock:
            self._metrics.generation_advances += count

    def note_eviction(self, count: int = 1, *, bytes_evicted: int = 0) -> None:
        count = require_bounded_int(
            count, name="count", minimum=0, maximum=MAX_SAFE_INTEGER
        )
        bytes_evicted = require_bounded_int(
            bytes_evicted, name="bytes_evicted", minimum=0, maximum=MAX_SAFE_INTEGER
        )
        with self._lock:
            self._metrics.evictions += count
            if bytes_evicted:
                self._metrics.bytes_resident = max(
                    0, self._metrics.bytes_resident - bytes_evicted
                )

    def note_single_flight(
        self,
        *,
        lead: bool = False,
        join: bool = False,
        failure: bool = False,
        cancel: bool = False,
    ) -> None:
        """Record low-cardinality single-flight outcomes (no key labels)."""

        with self._lock:
            if lead:
                self._metrics.single_flight_leads += 1
            if join:
                self._metrics.single_flight_joins += 1
            if failure:
                self._metrics.single_flight_failures += 1
            if cancel:
                self._metrics.single_flight_cancels += 1

    def observe(self, name: str, count: int = 1) -> None:
        """Increment a named low-cardinality counter (fail-closed)."""

        if name not in _METRIC_NAMES:
            raise CacheStateValidationError(
                f"unknown cache-state metric: {name}",
                detail={"name": name},
            )
        count = require_bounded_int(
            count, name="count", minimum=0, maximum=MAX_SAFE_INTEGER
        )
        with self._lock:
            current = getattr(self._metrics, name)
            setattr(self._metrics, name, current + count)

    # --- persistence / shutdown --------------------------------------------

    def export_entries(self) -> list[tuple[RangeBinding, bytes]]:
        """Export live binding/value pairs for persistence (under lock)."""

        with self._lock:
            return self._export_entries_locked()

    def _export_entries_locked(self) -> list[tuple[RangeBinding, bytes]]:
        if self._storage is None:
            return []
        entries: list[tuple[RangeBinding, bytes]] = []
        auth = self._authorize or (lambda _b: True)
        cons = self._consistent or (lambda _b: True)
        for binding in tuple(self._bindings.values()):
            try:
                value = self._storage.get(
                    binding, authorize=auth, consistent=cons
                )
            except Exception:  # noqa: BLE001
                value = None
            if value is None:
                continue
            entries.append((binding, value))
            if len(entries) >= MAX_PERSISTED_ENTRIES:
                break
        return entries

    def persist(
        self,
        *,
        state_path: str | os.PathLike[str] | Path | None = None,
        generation: str | None = None,
    ) -> CacheStateReceipt:
        """Atomically persist the live set.  Bounded by entry/byte ceilings."""

        started = time.monotonic()
        with self._lock:
            if state_path is not None:
                self._state_path = _path(state_path, "state_path")
            path = self._state_path
            if path is None:
                raise CacheStatePersistenceError(
                    "state_path is required for persist",
                )
            namespace = self._namespace
            gen = generation or self._mount_generation
            gen = _bounded_text(gen, "generation")
            entries = self._export_entries_locked()
            generations = dict(self._generations)

        if not entries:
            with self._lock:
                self._metrics.persistence_writes += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=PersistenceDisposition.EMPTY.value,
                    wal_recovered=self._wal_recovered,
                    mount_generation=gen,
                    namespace=namespace,
                    path=str(path),
                    reason="no_live_entries",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
            # Still write an empty envelope so restarts observe a valid file.
            envelope = build_persistence_envelope(
                [],
                namespace=namespace,
                generation=gen,
                generations=generations,
            )
            nbytes = atomic_write_envelope(path, envelope)
            with self._lock:
                self._metrics.bytes_persisted += nbytes
            return receipt

        envelope = build_persistence_envelope(
            entries,
            namespace=namespace,
            generation=gen,
            generations=generations,
        )
        nbytes = atomic_write_envelope(path, envelope)
        with self._lock:
            self._metrics.persistence_writes += 1
            self._metrics.bytes_persisted += nbytes
            receipt = CacheStateReceipt(
                phase=self._phase,
                disposition=PersistenceDisposition.WRITTEN.value,
                wal_recovered=self._wal_recovered,
                mount_generation=gen,
                namespace=namespace,
                path=str(path),
                entries_considered=len(entries),
                entries_admitted=len(entries),
                bytes_persisted=nbytes,
                reason="written",
                elapsed_seconds=max(0.0, time.monotonic() - started),
                corruption_policy=self._corruption_policy.value,
            )
            return receipt

    def shutdown(
        self,
        *,
        state_path: str | os.PathLike[str] | Path | None = None,
        persist: bool = True,
    ) -> CacheStateReceipt:
        """Bounded shutdown: optional atomic persist, then mark SHUTDOWN."""

        started = time.monotonic()
        deadline = started + self._shutdown_budget_seconds
        with self._lock:
            if self._phase is CacheLifecyclePhase.SHUTDOWN:
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=PersistenceDisposition.SKIPPED.value,
                    wal_recovered=self._wal_recovered,
                    mount_generation=self._mount_generation,
                    namespace=self._namespace,
                    path=str(self._state_path or ""),
                    reason="already_shutdown",
                    elapsed_seconds=0.0,
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_shutdown = receipt
                return receipt
            self._phase = CacheLifecyclePhase.SHUTTING_DOWN
            if state_path is not None:
                self._state_path = _path(state_path, "state_path")

        if persist and self._state_path is not None:
            if time.monotonic() > deadline:
                with self._lock:
                    self._phase = CacheLifecyclePhase.FAILED
                    receipt = CacheStateReceipt(
                        phase=self._phase,
                        disposition=PersistenceDisposition.BUDGET_EXCEEDED.value,
                        wal_recovered=self._wal_recovered,
                        mount_generation=self._mount_generation,
                        namespace=self._namespace,
                        path=str(self._state_path or ""),
                        reason="shutdown_budget_exceeded",
                        elapsed_seconds=max(0.0, time.monotonic() - started),
                        corruption_policy=self._corruption_policy.value,
                    )
                    self._last_shutdown = receipt
                    return receipt
            try:
                written = self.persist()
            except CacheStatePersistenceError as exc:
                with self._lock:
                    self._phase = CacheLifecyclePhase.FAILED
                    receipt = CacheStateReceipt(
                        phase=self._phase,
                        disposition=PersistenceDisposition.FAILED.value,
                        wal_recovered=self._wal_recovered,
                        mount_generation=self._mount_generation,
                        namespace=self._namespace,
                        path=str(self._state_path or ""),
                        reason=exc.message,
                        elapsed_seconds=max(0.0, time.monotonic() - started),
                        corruption_policy=self._corruption_policy.value,
                    )
                    self._last_shutdown = receipt
                    return receipt
            with self._lock:
                self._phase = CacheLifecyclePhase.SHUTDOWN
                self._metrics.shutdowns += 1
                receipt = CacheStateReceipt(
                    phase=self._phase,
                    disposition=written.disposition,
                    wal_recovered=self._wal_recovered,
                    mount_generation=self._mount_generation,
                    namespace=self._namespace,
                    path=written.path,
                    entries_considered=written.entries_considered,
                    entries_admitted=written.entries_admitted,
                    bytes_persisted=written.bytes_persisted,
                    reason=written.reason or "shutdown",
                    elapsed_seconds=max(0.0, time.monotonic() - started),
                    corruption_policy=self._corruption_policy.value,
                )
                self._last_shutdown = receipt
                return receipt

        with self._lock:
            self._phase = CacheLifecyclePhase.SHUTDOWN
            self._metrics.shutdowns += 1
            receipt = CacheStateReceipt(
                phase=self._phase,
                disposition=PersistenceDisposition.SKIPPED.value,
                wal_recovered=self._wal_recovered,
                mount_generation=self._mount_generation,
                namespace=self._namespace,
                path=str(self._state_path or ""),
                reason="persist_disabled" if not persist else "no_state_path",
                elapsed_seconds=max(0.0, time.monotonic() - started),
                corruption_policy=self._corruption_policy.value,
            )
            self._last_shutdown = receipt
            return receipt

    # --- introspection -----------------------------------------------------

    def active_generation(
        self, content_id: str, *, namespace: str | None = None
    ) -> str | None:
        ns = self._namespace if namespace is None else _bounded_text(namespace, "namespace")
        content_id = _bounded_text(content_id, "content_id")
        with self._lock:
            return self._generations.get((ns, content_id))

    def tracked_binding_count(self) -> int:
        with self._lock:
            return len(self._bindings)

    def low_cardinality_metric_names(self) -> frozenset[str]:
        """Return the closed set of scrapeable counter names."""

        return _METRIC_NAMES

    def assert_invariants(self) -> None:
        with self._lock:
            for key, binding in self._bindings.items():
                assert key == binding.cache_key
                assert binding.namespace == self._namespace
            if self._phase is CacheLifecyclePhase.READY:
                assert self._wal_recovered is True
            if self._storage is not None and hasattr(
                self._storage, "assert_invariants"
            ):
                self._storage.assert_invariants()

    # --- internal ----------------------------------------------------------

    def _compute_bytes_resident_locked(self) -> int:
        total = 0
        for binding in self._bindings.values():
            total += binding.length
        return total

    @staticmethod
    def _coerce_binding(
        binding: RangeBinding | Mapping[str, Any],
    ) -> RangeBinding:
        if isinstance(binding, RangeBinding):
            return binding
        return RangeBinding.from_dict(binding)


# Public aliases matching plan vocabulary.
PostRecoveryAdmission = CacheState
CacheStateCoordinator = CacheState
DurableCacheState = CacheState


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "SCHEMA_MAJOR",
    "CACHE_STATE_SCHEMA",
    "POST_RECOVERY_ADMISSION_SCHEMA",
    "CACHE_STATE_METRICS_SCHEMA",
    "CACHE_STATE_RECEIPT_SCHEMA",
    "PERSISTENCE_SCHEMA",
    "PERSISTENCE_REVISION",
    "CacheState_V1",
    "PostRecoveryAdmission_V1",
    "CacheStateMetrics_V1",
    "DEFAULT_STATE_FILENAME",
    "DEFAULT_MOUNT_NAMESPACE",
    "MAX_PERSISTENCE_BYTES",
    "MAX_PERSISTED_ENTRIES",
    "MAX_PERSISTED_VALUE_BYTES",
    "DEFAULT_STARTUP_BUDGET_SECONDS",
    "DEFAULT_SHUTDOWN_BUDGET_SECONDS",
    "CacheLifecyclePhase",
    "AdmissionDisposition",
    "PersistenceDisposition",
    "CorruptionPolicy",
    "CacheStateError",
    "CacheStateValidationError",
    "CacheAdmissionBlocked",
    "CacheStateBudgetError",
    "CacheStatePersistenceError",
    "CacheStateMetrics",
    "CacheStateReceipt",
    "build_persistence_envelope",
    "atomic_write_envelope",
    "load_persistence_envelope",
    "CacheState",
    "PostRecoveryAdmission",
    "CacheStateCoordinator",
    "DurableCacheState",
    # Re-exports for call-site convenience.
    "RangeBinding",
    "CachedStorage",
    "CacheCoherence",
]
