"""Legacy WAL / journal compatibility mappings (KITA-018).

Maps status and kind strings from existing observed implementations
(``wal``, ``storage_wal``, ``filesystem_journal``, ``enhanced_wal_durability``,
``pin_wal``, ``car_wal_manager``) onto the canonical contracts in
:mod:`ipfs_kit_py.core.wal.contracts`.

Rules (fail-closed):

* unknown or unrecognised legacy values are **preserved explicitly** as
  ``UNKNOWN_PRESERVED`` with the original token retained — they are never
  silently upgraded to committed/durable;
* legacy ``completed`` is mapped to a *pre-commit* canonical state unless a
  durability-evidence projection proves commit (``completed`` in the old
  WALs meant "handler finished", not "fsync + parent durable");
* secrets and unsafe executable encodings reject rather than map; and
* adapters must not invent generation/sequence identities.

This module performs no I/O and does not import live WAL implementations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

from ipfs_kit_py.core.operation_contracts import (
    BodyRejectedError,
    InconsistentStateError,
    SecretMaterialError,
)
from ipfs_kit_py.core.wal.contracts import (
    WALAcknowledgementMode,
    WALRecordKind,
    WALRecordState,
    WALSegmentState,
    WALTransactionState,
    WALUnsafeEncodingError,
    _assert_safe_encoding,
    ack_requirements_for,
)

# ---------------------------------------------------------------------------
# Disposition & projection results
# ---------------------------------------------------------------------------


class CompatibilityDisposition(str, Enum):
    """How a legacy value was projected onto the canonical vocabulary."""

    CANONICAL = "canonical"
    """Input was already a canonical token."""

    LEGACY_MAPPED = "legacy_mapped"
    """Recognised legacy token mapped to a canonical state/kind."""

    UNKNOWN_PRESERVED = "unknown_preserved"
    """Unrecognised token retained; never promoted to durable success."""

    UNSAFE_REJECTED = "unsafe_rejected"
    """Secret or unsafe executable encoding rejected."""

    EXPLICIT_LEGACY = "explicit_legacy"
    """Known legacy token kept as non-canonical observation only."""


class LegacyWALSource(str, Enum):
    """Observed legacy modules (inventory / KITA-001 surfaces)."""

    WAL = "wal"
    STORAGE_WAL = "storage_wal"
    FILESYSTEM_JOURNAL = "filesystem_journal"
    ENHANCED_WAL_DURABILITY = "enhanced_wal_durability"
    PIN_WAL = "pin_wal"
    CAR_WAL = "car_wal_manager"
    UNKNOWN = "unknown"
    CANONICAL = "canonical"


@dataclass(frozen=True)
class StateMappingResult:
    """Result of projecting a legacy status/state token."""

    disposition: CompatibilityDisposition
    legacy_source: str
    legacy_value: str
    canonical_state: WALRecordState | None
    """Canonical state when mapped; ``None`` when unknown/preserved only."""

    preserves_unknown: bool
    """True when the legacy value was retained without inventing durability."""

    may_claim_committed: bool
    """False unless the mapping explicitly admits a committed claim."""

    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "legacy_source": self.legacy_source,
            "legacy_value": self.legacy_value,
            "canonical_state": (
                self.canonical_state.value if self.canonical_state is not None else None
            ),
            "preserves_unknown": self.preserves_unknown,
            "may_claim_committed": self.may_claim_committed,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class KindMappingResult:
    """Result of projecting a legacy operation/entry type."""

    disposition: CompatibilityDisposition
    legacy_source: str
    legacy_value: str
    canonical_kind: WALRecordKind | None
    preserves_unknown: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "legacy_source": self.legacy_source,
            "legacy_value": self.legacy_value,
            "canonical_kind": (
                self.canonical_kind.value if self.canonical_kind is not None else None
            ),
            "preserves_unknown": self.preserves_unknown,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class AckModeMappingResult:
    """Result of projecting a legacy fsync / durability mode string."""

    disposition: CompatibilityDisposition
    legacy_source: str
    legacy_value: str
    canonical_mode: WALAcknowledgementMode | None
    preserves_unknown: bool
    requires_file_fsync: bool
    requires_parent_directory_fsync: bool
    requires_backend_effect: bool
    may_claim_committed: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "legacy_source": self.legacy_source,
            "legacy_value": self.legacy_value,
            "canonical_mode": (
                self.canonical_mode.value if self.canonical_mode is not None else None
            ),
            "preserves_unknown": self.preserves_unknown,
            "requires_file_fsync": self.requires_file_fsync,
            "requires_parent_directory_fsync": self.requires_parent_directory_fsync,
            "requires_backend_effect": self.requires_backend_effect,
            "may_claim_committed": self.may_claim_committed,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Closed legacy → canonical tables
# ---------------------------------------------------------------------------

# OperationStatus from wal.py / storage_wal.py:
#   pending, processing, completed, failed, retrying
# JournalEntryStatus from filesystem_journal.py:
#   pending, completed, failed, rolled_back
#
# Critical: legacy "completed" is NOT committed/durable — it only means the
# handler returned success.  Map to APPENDED (pre-commit media progress) so
# callers must still satisfy ack mode before claiming commit.

_LEGACY_STATUS_TO_STATE: Final[Mapping[str, WALRecordState]] = {
    # Canonical passthrough
    "buffered": WALRecordState.BUFFERED,
    "queued": WALRecordState.QUEUED,
    "appending": WALRecordState.APPENDING,
    "appended": WALRecordState.APPENDED,
    "file_synced": WALRecordState.FILE_SYNCED,
    "parent_synced": WALRecordState.PARENT_SYNCED,
    "prepared": WALRecordState.PREPARED,
    "committed": WALRecordState.COMMITTED,
    "aborted": WALRecordState.ABORTED,
    "archived": WALRecordState.ARCHIVED,
    "replayed": WALRecordState.REPLAYED,
    "failed": WALRecordState.FAILED,
    "rejected": WALRecordState.REJECTED,
    "cancelled": WALRecordState.CANCELLED,
    "corrupt": WALRecordState.CORRUPT,
    "poisoned": WALRecordState.POISONED,
    # Legacy wal / storage_wal OperationStatus
    "pending": WALRecordState.QUEUED,
    "processing": WALRecordState.APPENDING,
    "completed": WALRecordState.APPENDED,  # NOT committed — see notes
    "retrying": WALRecordState.QUEUED,
    # Legacy filesystem_journal JournalEntryStatus
    "rolled_back": WALRecordState.ABORTED,
    "rolledback": WALRecordState.ABORTED,
    # Common aliases observed in telemetry / APIs
    "success": WALRecordState.APPENDED,  # not committed
    "ok": WALRecordState.APPENDED,
    "done": WALRecordState.APPENDED,
    "error": WALRecordState.FAILED,
    "timeout": WALRecordState.FAILED,
    "canceled": WALRecordState.CANCELLED,  # US spelling
    "in_progress": WALRecordState.APPENDING,
    "running": WALRecordState.APPENDING,
    "accepted": WALRecordState.QUEUED,
    "begin": WALRecordState.BUFFERED,
    "prepare": WALRecordState.PREPARED,
    "commit": WALRecordState.COMMITTED,
    "abort": WALRecordState.ABORTED,
}

# Statuses that are *already* canonical (exact enum values).
_CANONICAL_STATE_VALUES: Final[frozenset[str]] = frozenset(
    state.value for state in WALRecordState
)

# Statuses that may *never* be treated as committed without extra evidence.
_NON_COMMIT_LEGACY: Final[frozenset[str]] = frozenset(
    {
        "pending",
        "processing",
        "retrying",
        "completed",
        "success",
        "ok",
        "done",
        "accepted",
        "queued",
        "buffered",
        "appending",
        "appended",
        "in_progress",
        "running",
        "begin",
    }
)

_LEGACY_KIND_TO_CANONICAL: Final[Mapping[str, WALRecordKind]] = {
    # Canonical
    "begin": WALRecordKind.BEGIN,
    "prepare": WALRecordKind.PREPARE,
    "commit": WALRecordKind.COMMIT,
    "abort": WALRecordKind.ABORT,
    "mutate": WALRecordKind.MUTATE,
    "intent": WALRecordKind.INTENT,
    "fsync_marker": WALRecordKind.FSYNC_MARKER,
    "segment_seal": WALRecordKind.SEGMENT_SEAL,
    "checkpoint_marker": WALRecordKind.CHECKPOINT_MARKER,
    "archive_marker": WALRecordKind.ARCHIVE_MARKER,
    "compaction_marker": WALRecordKind.COMPACTION_MARKER,
    "corruption_report": WALRecordKind.CORRUPTION_REPORT,
    "poison": WALRecordKind.POISON,
    "heartbeat": WALRecordKind.HEARTBEAT,
    "unknown": WALRecordKind.UNKNOWN,
    # Legacy OperationType / JournalOperationType
    "add": WALRecordKind.MUTATE,
    "get": WALRecordKind.MUTATE,
    "pin": WALRecordKind.MUTATE,
    "unpin": WALRecordKind.MUTATE,
    "rm": WALRecordKind.MUTATE,
    "cat": WALRecordKind.MUTATE,
    "list": WALRecordKind.MUTATE,
    "mkdir": WALRecordKind.MUTATE,
    "copy": WALRecordKind.MUTATE,
    "move": WALRecordKind.MUTATE,
    "upload": WALRecordKind.MUTATE,
    "download": WALRecordKind.MUTATE,
    "custom": WALRecordKind.MUTATE,
    "backup": WALRecordKind.MUTATE,
    "restore": WALRecordKind.MUTATE,
    "create": WALRecordKind.MUTATE,
    "delete": WALRecordKind.MUTATE,
    "rename": WALRecordKind.MUTATE,
    "write": WALRecordKind.MUTATE,
    "truncate": WALRecordKind.MUTATE,
    "metadata": WALRecordKind.MUTATE,
    "checkpoint": WALRecordKind.CHECKPOINT_MARKER,
    "mount": WALRecordKind.MUTATE,
    "unmount": WALRecordKind.MUTATE,
    "dataset": WALRecordKind.MUTATE,
}

_CANONICAL_KIND_VALUES: Final[frozenset[str]] = frozenset(
    kind.value for kind in WALRecordKind
)

# enhanced_wal_durability fsync_mode: always | batch | periodic
_LEGACY_FSYNC_MODE_TO_ACK: Final[Mapping[str, WALAcknowledgementMode]] = {
    "buffered": WALAcknowledgementMode.BUFFERED,
    "queued": WALAcknowledgementMode.QUEUED,
    "wal_appended": WALAcknowledgementMode.WAL_APPENDED,
    "appended": WALAcknowledgementMode.WAL_APPENDED,
    "wal_fsync": WALAcknowledgementMode.WAL_FSYNC,
    "fsync": WALAcknowledgementMode.WAL_FSYNC,
    "always": WALAcknowledgementMode.WAL_FSYNC,
    "batch": WALAcknowledgementMode.GROUP_COMMIT,
    "periodic": WALAcknowledgementMode.WAL_FSYNC,
    "wal_fsync_parent": WALAcknowledgementMode.WAL_FSYNC_PARENT,
    "fsync_parent": WALAcknowledgementMode.WAL_FSYNC_PARENT,
    "parent": WALAcknowledgementMode.WAL_FSYNC_PARENT,
    "group_commit": WALAcknowledgementMode.GROUP_COMMIT,
    "backend_effect": WALAcknowledgementMode.BACKEND_EFFECT,
    "backend_durable": WALAcknowledgementMode.BACKEND_DURABLE,
    "none": WALAcknowledgementMode.BUFFERED,
    "never": WALAcknowledgementMode.BUFFERED,
}

_CANONICAL_ACK_VALUES: Final[frozenset[str]] = frozenset(
    mode.value for mode in WALAcknowledgementMode
)

_LEGACY_SEGMENT_STATE: Final[Mapping[str, WALSegmentState]] = {
    "open": WALSegmentState.OPEN,
    "sealing": WALSegmentState.SEALING,
    "sealed": WALSegmentState.SEALED,
    "checkpointed": WALSegmentState.CHECKPOINTED,
    "archived": WALSegmentState.ARCHIVED,
    "corrupt": WALSegmentState.CORRUPT,
    "abandoned": WALSegmentState.ABANDONED,
    "active": WALSegmentState.OPEN,
    "closed": WALSegmentState.SEALED,
    "current": WALSegmentState.OPEN,
}

_LEGACY_TXN_STATE: Final[Mapping[str, WALTransactionState]] = {
    "open": WALTransactionState.OPEN,
    "preparing": WALTransactionState.PREPARING,
    "prepared": WALTransactionState.PREPARED,
    "committing": WALTransactionState.COMMITTING,
    "committed": WALTransactionState.COMMITTED,
    "aborting": WALTransactionState.ABORTING,
    "aborted": WALTransactionState.ABORTED,
    "failed": WALTransactionState.FAILED,
    "cancelled": WALTransactionState.CANCELLED,
    "canceled": WALTransactionState.CANCELLED,
    "pending": WALTransactionState.OPEN,
    "active": WALTransactionState.OPEN,
    "completed": WALTransactionState.OPEN,  # legacy completed ≠ committed
    "rolled_back": WALTransactionState.ABORTED,
}


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def _normalize_token(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        value = value.value
    if not isinstance(value, str):
        value = str(value)
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _source_name(source: LegacyWALSource | str | None) -> str:
    if source is None:
        return LegacyWALSource.UNKNOWN.value
    if isinstance(source, LegacyWALSource):
        return source.value
    return _normalize_token(source) or LegacyWALSource.UNKNOWN.value


# ---------------------------------------------------------------------------
# Public mapping API
# ---------------------------------------------------------------------------


def map_legacy_status(
    value: Any,
    *,
    source: LegacyWALSource | str | None = None,
    durability_proven: bool = False,
) -> StateMappingResult:
    """Map a legacy operation/journal status onto :class:`WALRecordState`.

    Parameters
    ----------
    value:
        Legacy status string or enum.
    source:
        Optional originating module name for diagnostics.
    durability_proven:
        When True and the legacy token is ``completed``/``success``/…, elevate
        the mapping to ``COMMITTED``.  Callers must only set this when fsync /
        parent-directory / backend evidence for the selected ack mode has been
        verified.  Default is False (fail-closed).
    """

    source_name = _source_name(source)
    raw = "" if value is None else (value.value if isinstance(value, Enum) else str(value))
    token = _normalize_token(value)
    if not token:
        return StateMappingResult(
            disposition=CompatibilityDisposition.UNKNOWN_PRESERVED,
            legacy_source=source_name,
            legacy_value=raw,
            canonical_state=None,
            preserves_unknown=True,
            may_claim_committed=False,
            notes="empty legacy status preserved; not durable",
        )

    if token in _CANONICAL_STATE_VALUES:
        state = WALRecordState(token)
        return StateMappingResult(
            disposition=CompatibilityDisposition.CANONICAL,
            legacy_source=source_name or LegacyWALSource.CANONICAL.value,
            legacy_value=raw,
            canonical_state=state,
            preserves_unknown=False,
            may_claim_committed=state in {
                WALRecordState.COMMITTED,
                WALRecordState.ARCHIVED,
                WALRecordState.REPLAYED,
            },
            notes="already canonical",
        )

    mapped = _LEGACY_STATUS_TO_STATE.get(token)
    if mapped is None:
        return StateMappingResult(
            disposition=CompatibilityDisposition.UNKNOWN_PRESERVED,
            legacy_source=source_name,
            legacy_value=raw,
            canonical_state=None,
            preserves_unknown=True,
            may_claim_committed=False,
            notes=(
                f"unrecognised legacy status {raw!r} preserved explicitly; "
                "must not be treated as committed/durable"
            ),
        )

    # Optional elevation of legacy "completed" when durability is proven.
    if durability_proven and token in {
        "completed",
        "success",
        "ok",
        "done",
    }:
        return StateMappingResult(
            disposition=CompatibilityDisposition.LEGACY_MAPPED,
            legacy_source=source_name,
            legacy_value=raw,
            canonical_state=WALRecordState.COMMITTED,
            preserves_unknown=False,
            may_claim_committed=True,
            notes=(
                "legacy completed elevated to committed because durability_proven=True"
            ),
        )

    may_commit = mapped in {
        WALRecordState.COMMITTED,
        WALRecordState.ARCHIVED,
        WALRecordState.REPLAYED,
    } and token not in _NON_COMMIT_LEGACY

    notes = "legacy status mapped"
    if token in _NON_COMMIT_LEGACY:
        notes = (
            f"legacy {raw!r} mapped to {mapped.value}; "
            "not committed/durable without separate evidence"
        )

    return StateMappingResult(
        disposition=CompatibilityDisposition.LEGACY_MAPPED,
        legacy_source=source_name,
        legacy_value=raw,
        canonical_state=mapped,
        preserves_unknown=False,
        may_claim_committed=may_commit,
        notes=notes,
    )


def map_legacy_kind(
    value: Any,
    *,
    source: LegacyWALSource | str | None = None,
) -> KindMappingResult:
    """Map a legacy operation/entry type onto :class:`WALRecordKind`."""

    source_name = _source_name(source)
    raw = "" if value is None else (value.value if isinstance(value, Enum) else str(value))
    token = _normalize_token(value)
    if not token:
        return KindMappingResult(
            disposition=CompatibilityDisposition.UNKNOWN_PRESERVED,
            legacy_source=source_name,
            legacy_value=raw,
            canonical_kind=None,
            preserves_unknown=True,
            notes="empty legacy kind preserved",
        )

    if token in _CANONICAL_KIND_VALUES:
        return KindMappingResult(
            disposition=CompatibilityDisposition.CANONICAL,
            legacy_source=source_name or LegacyWALSource.CANONICAL.value,
            legacy_value=raw,
            canonical_kind=WALRecordKind(token),
            preserves_unknown=False,
            notes="already canonical",
        )

    mapped = _LEGACY_KIND_TO_CANONICAL.get(token)
    if mapped is None:
        return KindMappingResult(
            disposition=CompatibilityDisposition.UNKNOWN_PRESERVED,
            legacy_source=source_name,
            legacy_value=raw,
            canonical_kind=WALRecordKind.UNKNOWN,
            preserves_unknown=True,
            notes=(
                f"unrecognised legacy kind {raw!r} preserved as UNKNOWN; "
                "original token retained in legacy_value"
            ),
        )

    return KindMappingResult(
        disposition=CompatibilityDisposition.LEGACY_MAPPED,
        legacy_source=source_name,
        legacy_value=raw,
        canonical_kind=mapped,
        preserves_unknown=False,
        notes="legacy kind mapped",
    )


def map_legacy_ack_mode(
    value: Any,
    *,
    source: LegacyWALSource | str | None = None,
) -> AckModeMappingResult:
    """Map a legacy fsync/durability mode onto :class:`WALAcknowledgementMode`.

    Unknown modes are preserved and default to non-committable buffered
    requirements so they cannot silently claim durability.
    """

    source_name = _source_name(source)
    raw = "" if value is None else (value.value if isinstance(value, Enum) else str(value))
    token = _normalize_token(value)
    if not token:
        return AckModeMappingResult(
            disposition=CompatibilityDisposition.UNKNOWN_PRESERVED,
            legacy_source=source_name,
            legacy_value=raw,
            canonical_mode=None,
            preserves_unknown=True,
            requires_file_fsync=False,
            requires_parent_directory_fsync=False,
            requires_backend_effect=False,
            may_claim_committed=False,
            notes="empty ack mode preserved; not durable",
        )

    if token in _CANONICAL_ACK_VALUES:
        mode = WALAcknowledgementMode(token)
        req = ack_requirements_for(mode)
        return AckModeMappingResult(
            disposition=CompatibilityDisposition.CANONICAL,
            legacy_source=source_name or LegacyWALSource.CANONICAL.value,
            legacy_value=raw,
            canonical_mode=mode,
            preserves_unknown=False,
            requires_file_fsync=req.requires_file_fsync,
            requires_parent_directory_fsync=req.requires_parent_directory_fsync,
            requires_backend_effect=req.requires_backend_effect,
            may_claim_committed=req.may_claim_committed,
            notes="already canonical",
        )

    mapped = _LEGACY_FSYNC_MODE_TO_ACK.get(token)
    if mapped is None:
        return AckModeMappingResult(
            disposition=CompatibilityDisposition.UNKNOWN_PRESERVED,
            legacy_source=source_name,
            legacy_value=raw,
            canonical_mode=None,
            preserves_unknown=True,
            requires_file_fsync=False,
            requires_parent_directory_fsync=False,
            requires_backend_effect=False,
            may_claim_committed=False,
            notes=(
                f"unrecognised legacy fsync/ack mode {raw!r} preserved; "
                "treated as non-committable"
            ),
        )

    req = ack_requirements_for(mapped)
    return AckModeMappingResult(
        disposition=CompatibilityDisposition.LEGACY_MAPPED,
        legacy_source=source_name,
        legacy_value=raw,
        canonical_mode=mapped,
        preserves_unknown=False,
        requires_file_fsync=req.requires_file_fsync,
        requires_parent_directory_fsync=req.requires_parent_directory_fsync,
        requires_backend_effect=req.requires_backend_effect,
        may_claim_committed=req.may_claim_committed,
        notes="legacy fsync/ack mode mapped",
    )


def map_legacy_segment_state(
    value: Any,
    *,
    source: LegacyWALSource | str | None = None,
) -> tuple[CompatibilityDisposition, WALSegmentState | None, str]:
    """Map a legacy segment state; unknown values are preserved as ``None``."""

    token = _normalize_token(value)
    raw = "" if value is None else str(value)
    if token in {s.value for s in WALSegmentState}:
        return CompatibilityDisposition.CANONICAL, WALSegmentState(token), raw
    mapped = _LEGACY_SEGMENT_STATE.get(token)
    if mapped is None:
        return CompatibilityDisposition.UNKNOWN_PRESERVED, None, raw
    return CompatibilityDisposition.LEGACY_MAPPED, mapped, raw


def map_legacy_transaction_state(
    value: Any,
    *,
    source: LegacyWALSource | str | None = None,
) -> tuple[CompatibilityDisposition, WALTransactionState | None, str]:
    """Map a legacy transaction state; unknown values are preserved as ``None``."""

    token = _normalize_token(value)
    raw = "" if value is None else str(value)
    if token in {s.value for s in WALTransactionState}:
        return CompatibilityDisposition.CANONICAL, WALTransactionState(token), raw
    mapped = _LEGACY_TXN_STATE.get(token)
    if mapped is None:
        return CompatibilityDisposition.UNKNOWN_PRESERVED, None, raw
    return CompatibilityDisposition.LEGACY_MAPPED, mapped, raw


def project_legacy_operation(
    operation: Mapping[str, Any],
    *,
    source: LegacyWALSource | str | None = None,
    durability_proven: bool = False,
) -> dict[str, Any]:
    """Project a legacy operation dict into a bounded compatibility envelope.

    The envelope always retains the original status/type tokens under
    ``legacy`` so unknown values are never lost.  It never elevates
    buffered/queued/completed to committed unless ``durability_proven``.
    """

    if not isinstance(operation, Mapping):
        raise TypeError("operation must be a mapping")

    # Reject secrets / bodies / unsafe encodings in the projection surface.
    for key in operation:
        lowered = str(key).strip().lower().replace("-", "_")
        if lowered in {
            "password",
            "secret",
            "api_key",
            "private_key",
            "authorization",
            "access_token",
            "client_secret",
        }:
            raise SecretMaterialError(f"legacy operation contains secret field {key!r}")
        if lowered in {
            "body",
            "payload_bytes",
            "content_bytes",
            "file_bytes",
            "source_body",
            "pickle_bytes",
        }:
            raise BodyRejectedError(f"legacy operation smuggles body field {key!r}")

    encoding = operation.get("encoding") or operation.get("content_type") or ""
    if encoding:
        try:
            _assert_safe_encoding(str(encoding), "encoding")
        except WALUnsafeEncodingError:
            return {
                "disposition": CompatibilityDisposition.UNSAFE_REJECTED.value,
                "legacy_source": _source_name(source),
                "legacy": {
                    "status": operation.get("status"),
                    "type": operation.get("type") or operation.get("operation_type"),
                    "encoding": encoding,
                },
                "canonical_state": None,
                "canonical_kind": None,
                "may_claim_committed": False,
                "preserves_unknown": True,
                "notes": "unsafe executable encoding rejected",
            }

    status_result = map_legacy_status(
        operation.get("status"),
        source=source,
        durability_proven=durability_proven,
    )
    kind_result = map_legacy_kind(
        operation.get("type") or operation.get("operation_type") or operation.get("kind"),
        source=source,
    )

    return {
        "disposition": status_result.disposition.value,
        "legacy_source": _source_name(source),
        "legacy": {
            "status": status_result.legacy_value,
            "type": kind_result.legacy_value,
            "operation_id": operation.get("operation_id") or operation.get("id") or "",
            "encoding": encoding,
        },
        "canonical_state": (
            status_result.canonical_state.value
            if status_result.canonical_state is not None
            else None
        ),
        "canonical_kind": (
            kind_result.canonical_kind.value
            if kind_result.canonical_kind is not None
            else None
        ),
        "may_claim_committed": status_result.may_claim_committed,
        "preserves_unknown": (
            status_result.preserves_unknown or kind_result.preserves_unknown
        ),
        "status_mapping": status_result.to_dict(),
        "kind_mapping": kind_result.to_dict(),
        "notes": status_result.notes,
    }


def assert_not_silently_committed(result: StateMappingResult | Mapping[str, Any]) -> None:
    """Raise if a mapping incorrectly claims commit for a non-durable legacy value."""

    if isinstance(result, StateMappingResult):
        legacy = _normalize_token(result.legacy_value)
        if result.may_claim_committed and legacy in _NON_COMMIT_LEGACY:
            raise InconsistentStateError(
                f"legacy status {result.legacy_value!r} must not claim committed"
            )
        if result.preserves_unknown and result.may_claim_committed:
            raise InconsistentStateError(
                "unknown-preserved mappings cannot claim committed"
            )
        return

    legacy = _normalize_token(result.get("legacy", {}).get("status", ""))
    if result.get("may_claim_committed") and legacy in _NON_COMMIT_LEGACY:
        raise InconsistentStateError(
            f"legacy status {legacy!r} must not claim committed"
        )
    if result.get("preserves_unknown") and result.get("may_claim_committed"):
        raise InconsistentStateError(
            "unknown-preserved mappings cannot claim committed"
        )


def legacy_status_catalog() -> dict[str, str]:
    """Return the closed legacy-status → canonical-state table (values only)."""

    return {key: state.value for key, state in _LEGACY_STATUS_TO_STATE.items()}


def legacy_kind_catalog() -> dict[str, str]:
    """Return the closed legacy-kind → canonical-kind table (values only)."""

    return {key: kind.value for key, kind in _LEGACY_KIND_TO_CANONICAL.items()}


def legacy_ack_mode_catalog() -> dict[str, str]:
    """Return the closed legacy-ack → canonical-mode table (values only)."""

    return {key: mode.value for key, mode in _LEGACY_FSYNC_MODE_TO_ACK.items()}


__all__ = [
    "CompatibilityDisposition",
    "LegacyWALSource",
    "StateMappingResult",
    "KindMappingResult",
    "AckModeMappingResult",
    "map_legacy_status",
    "map_legacy_kind",
    "map_legacy_ack_mode",
    "map_legacy_segment_state",
    "map_legacy_transaction_state",
    "project_legacy_operation",
    "assert_not_silently_committed",
    "legacy_status_catalog",
    "legacy_kind_catalog",
    "legacy_ack_mode_catalog",
]
