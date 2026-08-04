"""Canonical WAL records, durability states, and acknowledgement contracts (KITA-018).

This module is an inert, closed, versioned contract surface for write-ahead log
and journal variants.  It defines finite, content-addressed records for:

* record identities (generation + sequence) that are collision-safe and
  monotonic within a generation;
* durability / lifecycle states with a closed transition graph that keeps
  buffered/queued distinct from committed/durable;
* transaction boundaries (begin / prepare / commit / abort);
* segments and checkpoints;
* bounded payload references (never unbounded bodies); and
* acknowledgement modes that declare fsync, parent-directory durability, and
  backend-effect requirements.

Rules (fail-closed):

* identities are derived from canonical JSON and cannot be forged;
* secrets, source bodies, cycles, non-finite values, and unsafe executable
  encodings are rejected at construction;
* committed/durable acknowledgements require the declared fsync /
  parent-directory / backend-effect evidence for the selected mode; and
* adapters may only project these records — they cannot translate buffered or
  queued work into committed durability.

No optional storage providers, live filesystems, or network I/O are imported
here. Existing WAL/journal implementations remain observations until later
migration tasks.

Interfaces (plan aliases): ``WALRecord@1``, ``WALTransaction@1``,
``WALSegment@1``, ``WALCheckpoint@1``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Final, TypeVar

from ipfs_kit_py.core.operation_contracts import (
    BodyRejectedError,
    CanonicalContract,
    CycleDetectedError,
    ForgedIdentityError,
    InconsistentStateError,
    OperationContractBoundsError,
    OperationContractError,
    PayloadKind,
    PayloadReference,
    SecretMaterialError,
    canonical_json_bytes,
    content_identity,
)

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

WAL_CONTRACTS_NAMESPACE: Final[str] = "ipfs_kit_py/core/wal/contracts"

WAL_RECORD_SCHEMA: Final[str] = f"{WAL_CONTRACTS_NAMESPACE}/wal-record@{SCHEMA_MAJOR}"
WAL_TRANSACTION_SCHEMA: Final[str] = (
    f"{WAL_CONTRACTS_NAMESPACE}/wal-transaction@{SCHEMA_MAJOR}"
)
WAL_SEGMENT_SCHEMA: Final[str] = f"{WAL_CONTRACTS_NAMESPACE}/wal-segment@{SCHEMA_MAJOR}"
WAL_CHECKPOINT_SCHEMA: Final[str] = (
    f"{WAL_CONTRACTS_NAMESPACE}/wal-checkpoint@{SCHEMA_MAJOR}"
)
WAL_RECORD_IDENTITY_SCHEMA: Final[str] = (
    f"{WAL_CONTRACTS_NAMESPACE}/wal-record-identity@{SCHEMA_MAJOR}"
)
WAL_ACK_REQUIREMENTS_SCHEMA: Final[str] = (
    f"{WAL_CONTRACTS_NAMESPACE}/wal-ack-requirements@{SCHEMA_MAJOR}"
)
WAL_FSYNC_RECEIPT_SCHEMA: Final[str] = (
    f"{WAL_CONTRACTS_NAMESPACE}/wal-fsync-receipt@{SCHEMA_MAJOR}"
)

# Public interface aliases (plan: WALRecord@1, WALTransaction@1, …).
WALRecord_V1: Final[str] = WAL_RECORD_SCHEMA
WALTransaction_V1: Final[str] = WAL_TRANSACTION_SCHEMA
WALSegment_V1: Final[str] = WAL_SEGMENT_SCHEMA
WALCheckpoint_V1: Final[str] = WAL_CHECKPOINT_SCHEMA

MAX_RECORD_BYTES: Final[int] = 262_144
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_IDENTIFIER_BYTES: Final[int] = 512
MAX_REFERENCE_COUNT: Final[int] = 256
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
MAX_SEQUENCE: Final[int] = MAX_SAFE_INTEGER
MAX_PAYLOAD_BYTES_BOUND: Final[int] = 1 << 40
MAX_CHECKSUM_BYTES: Final[int] = 128

_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$"
)
_CID_LIKE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(b[a-z2-7]{20,}|Qm[1-9A-HJ-NP-Za-km-z]{44}|baguqeer[a-z0-9]{50,}|"
    r"sha256:[0-9a-f]{64})$"
)
_HEX_CHECKSUM_RE: Final[re.Pattern[str]] = re.compile(
    r"^(sha256:)?[0-9a-fA-F]{32,128}$"
)

# Encodings that must never appear as payload carriers (unsafe executable).
_UNSAFE_EXECUTABLE_ENCODINGS: Final[frozenset[str]] = frozenset(
    {
        "pickle",
        "cPickle",
        "application/python-pickle",
        "application/x-python-pickle",
        "application/x-pickle",
        "marshal",
        "application/python-marshal",
        "application/x-python-code",
        "application/x-bytecode",
        "text/x-python",
        "application/x-sh",
        "application/x-shellscript",
        "application/javascript",
        "text/javascript",
        "application/x-executable",
        "application/x-msdownload",
        "application/x-elf",
        "eval",
        "exec",
        "code_object",
        "dill",
        "cloudpickle",
        "joblib",
        "shelve",
    }
)

TEnum = TypeVar("TEnum", bound=Enum)


# ---------------------------------------------------------------------------
# Closed vocabularies — record kinds, durability states, ack modes
# ---------------------------------------------------------------------------


class WALRecordKind(str, Enum):
    """Closed kinds of framed WAL records."""

    BEGIN = "begin"
    PREPARE = "prepare"
    COMMIT = "commit"
    ABORT = "abort"
    MUTATE = "mutate"
    INTENT = "intent"
    FSYNC_MARKER = "fsync_marker"
    SEGMENT_SEAL = "segment_seal"
    CHECKPOINT_MARKER = "checkpoint_marker"
    ARCHIVE_MARKER = "archive_marker"
    COMPACTION_MARKER = "compaction_marker"
    CORRUPTION_REPORT = "corruption_report"
    POISON = "poison"
    HEARTBEAT = "heartbeat"
    UNKNOWN = "unknown"


class WALRecordState(str, Enum):
    """Closed durability / lifecycle states for WAL records and intents.

    Non-durable (buffered / queued ladder) — must never be reported as
    committed:

    * ``buffered`` — held in memory only.
    * ``queued`` — admitted to a writer queue; not on durable media.
    * ``appending`` — write in flight to a segment buffer.

    Pre-commit durable ladder (media progress without transaction commit):

    * ``appended`` — bytes present in an open segment buffer / file (no fsync).
    * ``file_synced`` — file ``fsync`` / ``fdatasync`` observed.
    * ``parent_synced`` — parent-directory durability observed.

    Transactional durable ladder:

    * ``prepared`` — prepare marker durable under the selected ack mode.
    * ``committed`` — commit marker durable; survives the declared crash model.
    * ``aborted`` — abort marker durable.
    * ``archived`` — transferred to confirmed archive media.
    * ``replayed`` — successfully applied during recovery (idempotent).

    Failure dispositions:

    * ``failed``, ``rejected``, ``cancelled``, ``corrupt``, ``poisoned``.
    """

    BUFFERED = "buffered"
    QUEUED = "queued"
    APPENDING = "appending"
    APPENDED = "appended"
    FILE_SYNCED = "file_synced"
    PARENT_SYNCED = "parent_synced"
    PREPARED = "prepared"
    COMMITTED = "committed"
    ABORTED = "aborted"
    ARCHIVED = "archived"
    REPLAYED = "replayed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    CORRUPT = "corrupt"
    POISONED = "poisoned"


# States that claim durability past mere buffering / queuing of intent.
# Note: ``appended`` alone is *not* committed; it may still be lost without
# fsync depending on the ack mode.
DURABLE_STATES: Final[frozenset[WALRecordState]] = frozenset(
    {
        WALRecordState.FILE_SYNCED,
        WALRecordState.PARENT_SYNCED,
        WALRecordState.PREPARED,
        WALRecordState.COMMITTED,
        WALRecordState.ABORTED,
        WALRecordState.ARCHIVED,
        WALRecordState.REPLAYED,
    }
)

# States that claim a committed transaction (strict).
COMMITTED_STATES: Final[frozenset[WALRecordState]] = frozenset(
    {
        WALRecordState.COMMITTED,
        WALRecordState.ARCHIVED,
        WALRecordState.REPLAYED,
    }
)

# Explicitly non-durable / buffered / queued — never interchangeable with commit.
BUFFERED_OR_QUEUED_STATES: Final[frozenset[WALRecordState]] = frozenset(
    {
        WALRecordState.BUFFERED,
        WALRecordState.QUEUED,
        WALRecordState.APPENDING,
    }
)

# Pre-commit media progress that is still not a transaction commit.
PRE_COMMIT_MEDIA_STATES: Final[frozenset[WALRecordState]] = frozenset(
    {
        WALRecordState.APPENDED,
        WALRecordState.FILE_SYNCED,
        WALRecordState.PARENT_SYNCED,
        WALRecordState.PREPARED,
    }
)

TERMINAL_FAILURE_STATES: Final[frozenset[WALRecordState]] = frozenset(
    {
        WALRecordState.FAILED,
        WALRecordState.REJECTED,
        WALRecordState.CANCELLED,
        WALRecordState.CORRUPT,
        WALRecordState.POISONED,
        WALRecordState.ABORTED,
    }
)

TERMINAL_SUCCESS_STATES: Final[frozenset[WALRecordState]] = frozenset(
    {
        WALRecordState.COMMITTED,
        WALRecordState.ARCHIVED,
        WALRecordState.REPLAYED,
    }
)

_LEGAL_RECORD_TRANSITIONS: Final[Mapping[WALRecordState, frozenset[WALRecordState]]] = {
    WALRecordState.BUFFERED: frozenset(
        {
            WALRecordState.QUEUED,
            WALRecordState.APPENDING,
            WALRecordState.APPENDED,
            WALRecordState.FAILED,
            WALRecordState.REJECTED,
            WALRecordState.CANCELLED,
        }
    ),
    WALRecordState.QUEUED: frozenset(
        {
            WALRecordState.APPENDING,
            WALRecordState.APPENDED,
            WALRecordState.FAILED,
            WALRecordState.REJECTED,
            WALRecordState.CANCELLED,
        }
    ),
    WALRecordState.APPENDING: frozenset(
        {
            WALRecordState.APPENDED,
            WALRecordState.FAILED,
            WALRecordState.CANCELLED,
            WALRecordState.CORRUPT,
        }
    ),
    WALRecordState.APPENDED: frozenset(
        {
            WALRecordState.FILE_SYNCED,
            WALRecordState.PARENT_SYNCED,  # rare: parent before file on some stacks
            WALRecordState.PREPARED,
            WALRecordState.COMMITTED,  # only legal when ack mode allows append-as-commit
            WALRecordState.ABORTED,
            WALRecordState.FAILED,
            WALRecordState.CANCELLED,
            WALRecordState.CORRUPT,
            WALRecordState.POISONED,
        }
    ),
    WALRecordState.FILE_SYNCED: frozenset(
        {
            WALRecordState.PARENT_SYNCED,
            WALRecordState.PREPARED,
            WALRecordState.COMMITTED,
            WALRecordState.ABORTED,
            WALRecordState.FAILED,
            WALRecordState.CORRUPT,
            WALRecordState.POISONED,
        }
    ),
    WALRecordState.PARENT_SYNCED: frozenset(
        {
            WALRecordState.PREPARED,
            WALRecordState.COMMITTED,
            WALRecordState.ABORTED,
            WALRecordState.FAILED,
            WALRecordState.CORRUPT,
            WALRecordState.POISONED,
        }
    ),
    WALRecordState.PREPARED: frozenset(
        {
            WALRecordState.COMMITTED,
            WALRecordState.ABORTED,
            WALRecordState.FAILED,
            WALRecordState.CORRUPT,
            WALRecordState.POISONED,
        }
    ),
    WALRecordState.COMMITTED: frozenset(
        {
            WALRecordState.ARCHIVED,
            WALRecordState.REPLAYED,
            WALRecordState.CORRUPT,  # post-commit detection of media damage
            WALRecordState.POISONED,
        }
    ),
    WALRecordState.ABORTED: frozenset(
        {
            WALRecordState.ARCHIVED,
            WALRecordState.REPLAYED,
        }
    ),
    WALRecordState.ARCHIVED: frozenset(),
    WALRecordState.REPLAYED: frozenset(
        {
            WALRecordState.ARCHIVED,
        }
    ),
    WALRecordState.FAILED: frozenset(),
    WALRecordState.REJECTED: frozenset(),
    WALRecordState.CANCELLED: frozenset(),
    WALRecordState.CORRUPT: frozenset(),
    WALRecordState.POISONED: frozenset(),
}


def is_legal_record_transition(
    from_state: WALRecordState, to_state: WALRecordState
) -> bool:
    """Return whether ``from_state → to_state`` is an admitted record transition."""

    if from_state is to_state:
        return True
    allowed = _LEGAL_RECORD_TRANSITIONS.get(from_state, frozenset())
    return to_state in allowed


def assert_legal_record_transition(
    from_state: WALRecordState, to_state: WALRecordState
) -> None:
    """Raise if the transition is not admitted."""

    if not is_legal_record_transition(from_state, to_state):
        raise InconsistentStateError(
            f"illegal WAL record transition {from_state.value!r} → {to_state.value!r}"
        )


class WALTransactionState(str, Enum):
    """Closed states for a multi-record WAL transaction."""

    OPEN = "open"
    PREPARING = "preparing"
    PREPARED = "prepared"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ABORTING = "aborting"
    ABORTED = "aborted"
    FAILED = "failed"
    CANCELLED = "cancelled"


_LEGAL_TXN_TRANSITIONS: Final[
    Mapping[WALTransactionState, frozenset[WALTransactionState]]
] = {
    WALTransactionState.OPEN: frozenset(
        {
            WALTransactionState.PREPARING,
            WALTransactionState.COMMITTING,  # single-phase commit
            WALTransactionState.ABORTING,
            WALTransactionState.ABORTED,
            WALTransactionState.FAILED,
            WALTransactionState.CANCELLED,
        }
    ),
    WALTransactionState.PREPARING: frozenset(
        {
            WALTransactionState.PREPARED,
            WALTransactionState.ABORTING,
            WALTransactionState.ABORTED,
            WALTransactionState.FAILED,
            WALTransactionState.CANCELLED,
        }
    ),
    WALTransactionState.PREPARED: frozenset(
        {
            WALTransactionState.COMMITTING,
            WALTransactionState.ABORTING,
            WALTransactionState.ABORTED,
            WALTransactionState.FAILED,
        }
    ),
    WALTransactionState.COMMITTING: frozenset(
        {
            WALTransactionState.COMMITTED,
            WALTransactionState.FAILED,
            WALTransactionState.ABORTING,
        }
    ),
    WALTransactionState.ABORTING: frozenset(
        {
            WALTransactionState.ABORTED,
            WALTransactionState.FAILED,
        }
    ),
    WALTransactionState.COMMITTED: frozenset(),
    WALTransactionState.ABORTED: frozenset(),
    WALTransactionState.FAILED: frozenset(),
    WALTransactionState.CANCELLED: frozenset(),
}


def is_legal_transaction_transition(
    from_state: WALTransactionState, to_state: WALTransactionState
) -> bool:
    if from_state is to_state:
        return True
    return to_state in _LEGAL_TXN_TRANSITIONS.get(from_state, frozenset())


def assert_legal_transaction_transition(
    from_state: WALTransactionState, to_state: WALTransactionState
) -> None:
    if not is_legal_transaction_transition(from_state, to_state):
        raise InconsistentStateError(
            f"illegal WAL transaction transition "
            f"{from_state.value!r} → {to_state.value!r}"
        )


class WALSegmentState(str, Enum):
    """Lifecycle of a WAL segment file."""

    OPEN = "open"
    SEALING = "sealing"
    SEALED = "sealed"
    CHECKPOINTED = "checkpointed"
    ARCHIVED = "archived"
    CORRUPT = "corrupt"
    ABANDONED = "abandoned"


_LEGAL_SEGMENT_TRANSITIONS: Final[
    Mapping[WALSegmentState, frozenset[WALSegmentState]]
] = {
    WALSegmentState.OPEN: frozenset(
        {
            WALSegmentState.SEALING,
            WALSegmentState.SEALED,
            WALSegmentState.CORRUPT,
            WALSegmentState.ABANDONED,
        }
    ),
    WALSegmentState.SEALING: frozenset(
        {
            WALSegmentState.SEALED,
            WALSegmentState.CORRUPT,
            WALSegmentState.ABANDONED,
        }
    ),
    WALSegmentState.SEALED: frozenset(
        {
            WALSegmentState.CHECKPOINTED,
            WALSegmentState.ARCHIVED,
            WALSegmentState.CORRUPT,
        }
    ),
    WALSegmentState.CHECKPOINTED: frozenset(
        {
            WALSegmentState.ARCHIVED,
            WALSegmentState.CORRUPT,
        }
    ),
    WALSegmentState.ARCHIVED: frozenset(),
    WALSegmentState.CORRUPT: frozenset(),
    WALSegmentState.ABANDONED: frozenset(),
}


def is_legal_segment_transition(
    from_state: WALSegmentState, to_state: WALSegmentState
) -> bool:
    if from_state is to_state:
        return True
    return to_state in _LEGAL_SEGMENT_TRANSITIONS.get(from_state, frozenset())


def assert_legal_segment_transition(
    from_state: WALSegmentState, to_state: WALSegmentState
) -> None:
    if not is_legal_segment_transition(from_state, to_state):
        raise InconsistentStateError(
            f"illegal WAL segment transition {from_state.value!r} → {to_state.value!r}"
        )


class WALCheckpointState(str, Enum):
    """Lifecycle of a WAL checkpoint publication."""

    PENDING = "pending"
    SEALING = "sealing"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    FAILED = "failed"
    SUPERSEDED = "superseded"


_LEGAL_CHECKPOINT_TRANSITIONS: Final[
    Mapping[WALCheckpointState, frozenset[WALCheckpointState]]
] = {
    WALCheckpointState.PENDING: frozenset(
        {
            WALCheckpointState.SEALING,
            WALCheckpointState.PUBLISHED,
            WALCheckpointState.FAILED,
        }
    ),
    WALCheckpointState.SEALING: frozenset(
        {
            WALCheckpointState.PUBLISHED,
            WALCheckpointState.FAILED,
        }
    ),
    WALCheckpointState.PUBLISHED: frozenset(
        {
            WALCheckpointState.ARCHIVED,
            WALCheckpointState.SUPERSEDED,
            WALCheckpointState.FAILED,
        }
    ),
    WALCheckpointState.ARCHIVED: frozenset(
        {
            WALCheckpointState.SUPERSEDED,
        }
    ),
    WALCheckpointState.FAILED: frozenset(),
    WALCheckpointState.SUPERSEDED: frozenset(),
}


def is_legal_checkpoint_transition(
    from_state: WALCheckpointState, to_state: WALCheckpointState
) -> bool:
    if from_state is to_state:
        return True
    return to_state in _LEGAL_CHECKPOINT_TRANSITIONS.get(from_state, frozenset())


def assert_legal_checkpoint_transition(
    from_state: WALCheckpointState, to_state: WALCheckpointState
) -> None:
    if not is_legal_checkpoint_transition(from_state, to_state):
        raise InconsistentStateError(
            f"illegal WAL checkpoint transition "
            f"{from_state.value!r} → {to_state.value!r}"
        )


class WALAcknowledgementMode(str, Enum):
    """Declared acknowledgement / durability mode for WAL writes.

    Modes that may claim ``committed`` require the matching evidence set
    described by :func:`ack_requirements_for`.  ``BUFFERED`` and ``QUEUED``
    must never be reported as committed.
    """

    BUFFERED = "buffered"
    QUEUED = "queued"
    WAL_APPENDED = "wal_appended"
    WAL_FSYNC = "wal_fsync"
    WAL_FSYNC_PARENT = "wal_fsync_parent"
    GROUP_COMMIT = "group_commit"
    BACKEND_EFFECT = "backend_effect"
    BACKEND_DURABLE = "backend_durable"


class WALCorruptionDisposition(str, Enum):
    """How a torn or corrupt tail is handled (valid prefix preserved)."""

    BOUND_AND_REPORT = "bound_and_report"
    TRUNCATE_TO_VALID_PREFIX = "truncate_to_valid_prefix"
    QUARANTINE_SEGMENT = "quarantine_segment"
    FAIL_CLOSED = "fail_closed"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WALContractError(OperationContractError):
    """Base class for WAL-contract schema failures."""


class WALContractBoundsError(OperationContractBoundsError, WALContractError):
    """A WAL record exceeded its declared compactness bounds."""


class WALSequenceError(WALContractError):
    """Sequence / generation identity invariant violated."""


class WALUnsafeEncodingError(WALContractError):
    """An unsafe executable payload encoding was rejected."""


class WALAcknowledgementError(InconsistentStateError, WALContractError):
    """Ack mode requirements are not satisfied for the claimed state."""


# ---------------------------------------------------------------------------
# Field codecs / secret / encoding guards
# ---------------------------------------------------------------------------


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


_SECRET_KEY_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "bearer",
        "client_secret",
        "cookie",
        "credential",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "secret_key",
        "session_token",
        "ssh_key",
        "auth_token",
        "bearer_token",
        "id_token",
    }
)

_SECRET_VALUE_MARKERS: Final[tuple[str, ...]] = (
    "api_key=",
    "apikey=",
    "password=",
    "secret=",
    "private_key",
    "authorization:",
    "bearer ",
    "-----begin",
    "client_secret=",
)

_BODY_KEY_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "body",
        "source_body",
        "source_text",
        "source_code",
        "contents",
        "content_bytes",
        "file_bytes",
        "file_text",
        "snippet",
        "raw_code",
        "raw_ast",
        "ast_body",
        "payload_bytes",
        "raw_payload",
        "request_body",
        "response_body",
        "proof_script",
        "prompt_body",
        "pickle_bytes",
        "marshalled",
        "executable_bytes",
    }
)


def _key_looks_secret(key: str) -> bool:
    if key in _SECRET_KEY_MARKERS:
        return True
    for marker in _SECRET_KEY_MARKERS:
        if key.endswith("_" + marker) or key.startswith(marker + "_"):
            return True
        if "_" in marker and marker in key:
            return True
    return False


def _key_looks_body(key: str) -> bool:
    return key in _BODY_KEY_MARKERS or any(
        key.endswith("_" + marker) for marker in _BODY_KEY_MARKERS
    )


def _assert_no_secret_text(value: str, field_name: str) -> None:
    lowered = value.lower()
    for marker in _SECRET_VALUE_MARKERS:
        if marker in lowered:
            raise SecretMaterialError(
                f"{field_name} contains secret material markers"
            )


def _contains_secret_or_body(value: Any, *, path: str = "record") -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = _normalize_key(raw_key)
            child = f"{path}.{key}"
            if _key_looks_secret(key):
                raise SecretMaterialError(f"{child} is secret material")
            if _key_looks_body(key):
                raise BodyRejectedError(f"{child} smuggles a body/payload")
            _contains_secret_or_body(item, path=child)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _contains_secret_or_body(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        _assert_no_secret_text(value, path)


def _assert_safe_encoding(encoding: str, field_name: str = "encoding") -> str:
    text = (encoding or "").strip().lower()
    if not text:
        return ""
    if text in _UNSAFE_EXECUTABLE_ENCODINGS:
        raise WALUnsafeEncodingError(
            f"{field_name} rejects unsafe executable encoding {encoding!r}"
        )
    # Compound forms: application/x-python-pickle; charset=…
    base = text.split(";", 1)[0].strip()
    if base in _UNSAFE_EXECUTABLE_ENCODINGS:
        raise WALUnsafeEncodingError(
            f"{field_name} rejects unsafe executable encoding {encoding!r}"
        )
    for banned in _UNSAFE_EXECUTABLE_ENCODINGS:
        if banned in base and banned not in {"eval", "exec"}:
            # Avoid over-matching short tokens; require full token or subtype.
            if base == banned or base.endswith("/" + banned) or base.endswith(
                "-" + banned
            ):
                raise WALUnsafeEncodingError(
                    f"{field_name} rejects unsafe executable encoding {encoding!r}"
                )
    if "pickle" in base or "marshal" in base or "cloudpickle" in base:
        raise WALUnsafeEncodingError(
            f"{field_name} rejects unsafe executable encoding {encoding!r}"
        )
    if len(text.encode("utf-8")) > 256:
        raise WALContractBoundsError(f"{field_name} exceeds encoding bound")
    return text


def _text(
    value: Any,
    field_name: str,
    *,
    required: bool = False,
    limit: int = MAX_TEXT_BYTES,
    allow_empty: bool = True,
) -> str:
    if value is None:
        normalized = ""
    elif not isinstance(value, str):
        raise WALContractError(f"{field_name} must be a string")
    else:
        normalized = value.strip()
    if required and not normalized:
        raise WALContractError(f"{field_name} is required")
    if not allow_empty and not normalized:
        raise WALContractError(f"{field_name} must not be empty")
    if len(normalized.encode("utf-8")) > limit:
        raise WALContractBoundsError(f"{field_name} exceeds its byte bound")
    _assert_no_secret_text(normalized, field_name)
    return normalized


def _identifier(value: Any, field_name: str, *, required: bool = True) -> str:
    text = _text(
        value,
        field_name,
        required=required,
        limit=MAX_IDENTIFIER_BYTES,
        allow_empty=not required,
    )
    if not text:
        return ""
    if any(char.isspace() for char in text):
        raise WALContractError(f"{field_name} must be an opaque compact identifier")
    if not _ID_RE.match(text):
        raise WALContractError(f"{field_name} has an invalid identifier shape")
    return text


def _optional_identifier(value: Any, field_name: str) -> str:
    return _identifier(value, field_name, required=False)


def _bounded_int(
    value: Any,
    field_name: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_SAFE_INTEGER,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise WALContractError(f"{field_name} must be a finite integer")
    if value < minimum or value > maximum:
        raise WALContractBoundsError(f"{field_name} is outside the supported bound")
    return value


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise WALContractError(f"{field_name} must be a boolean")
    return value


def _enum(value: Any, enum: type[TEnum], field_name: str) -> TEnum:
    try:
        if isinstance(value, enum):
            return value
        return enum(value)  # type: ignore[call-arg]
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum)
        raise WALContractError(f"{field_name} must be one of: {allowed}") from exc


def _ids(
    values: Any,
    field_name: str,
    *,
    required: bool = False,
    limit: int = MAX_REFERENCE_COUNT,
) -> tuple[str, ...]:
    if values is None:
        items: Sequence[Any] = ()
    elif isinstance(values, str):
        items = (values,)
    elif isinstance(values, Sequence) and not isinstance(values, (bytes, bytearray)):
        items = values
    else:
        raise WALContractError(f"{field_name} must be a sequence of identifiers")
    if len(items) > limit:
        raise WALContractBoundsError(f"{field_name} exceeds reference count bound")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _identifier(item, field_name)
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    if required and not normalized:
        raise WALContractError(f"{field_name} must not be empty")
    return tuple(normalized)


def _optional_cid(value: Any, field_name: str) -> str:
    text = _text(value, field_name, required=False, limit=MAX_IDENTIFIER_BYTES)
    if not text:
        return ""
    if not _CID_LIKE_RE.match(text) and not text.startswith(
        ("cid:", "baguqeer", "bafy", "bafk", "Qm", "sha256:")
    ):
        if not _ID_RE.match(text):
            raise WALContractError(f"{field_name} is not a valid content identity")
    return text


def _checksum(value: Any, field_name: str = "checksum") -> str:
    text = _text(value, field_name, required=False, limit=MAX_CHECKSUM_BYTES)
    if not text:
        return ""
    if not _HEX_CHECKSUM_RE.match(text) and not text.startswith("sha256:"):
        # Allow content-id style digests.
        if not _CID_LIKE_RE.match(text) and not _ID_RE.match(text):
            raise WALContractError(f"{field_name} is not a valid checksum digest")
    return text.lower() if text.startswith("sha256:") or all(
        c in "0123456789abcdef" for c in text.lower()
    ) else text


def _reject_unknown_fields(
    payload: Mapping[str, Any],
    allowed: Iterable[str],
    *,
    artifact_name: str,
) -> None:
    if set(payload).difference(set(allowed) | {"schema", "content_id", "contract_version"}):
        raise WALContractError(
            f"{artifact_name} contains unsupported fields; rebuild its canonical payload"
        )


def _schema(payload: Mapping[str, Any], expected: str) -> None:
    if not isinstance(payload, Mapping):
        raise WALContractError("contract payload must be an object")
    supplied = payload.get("schema")
    if supplied not in (None, "", expected):
        raise WALContractError(f"unsupported contract schema; use {expected}")


def _contract_version(payload: Mapping[str, Any]) -> None:
    supplied = payload.get("contract_version")
    if supplied not in (None, CONTRACT_VERSION):
        raise WALContractError(
            "unsupported WAL contract version; rebuild with the current contract"
        )


def _bounded_record(record: CanonicalContract, name: str) -> None:
    size = len(record.canonical_bytes())
    if size > MAX_RECORD_BYTES:
        raise WALContractBoundsError(
            f"{name} exceeds MAX_RECORD_BYTES ({size} > {MAX_RECORD_BYTES})"
        )


def _verify_identity(payload: Mapping[str, Any], record: CanonicalContract) -> None:
    supplied = payload.get("content_id")
    if supplied is None:
        return
    if not isinstance(supplied, str) or not supplied:
        raise ForgedIdentityError("content_id must be a non-empty string when present")
    if supplied != record.content_id:
        raise ForgedIdentityError(
            "stored content_id does not match the canonical preimage"
        )


def _decode_fields(
    payload: Mapping[str, Any],
    schema: str,
    fields: Sequence[str],
    artifact_name: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise WALContractError(f"{artifact_name} payload must be an object")
    _schema(payload, schema)
    _contract_version(payload)
    _reject_unknown_fields(payload, fields, artifact_name=artifact_name)
    _contains_secret_or_body(payload, path=artifact_name)
    return {name: payload.get(name) for name in fields}


def _payload_reference(value: Any) -> PayloadReference | None:
    if value is None or value == "" or value == {}:
        return None
    if isinstance(value, PayloadReference):
        return value
    if isinstance(value, Mapping):
        return PayloadReference.from_dict(value)
    raise WALContractError("payload must be a PayloadReference or mapping")


# ---------------------------------------------------------------------------
# Acknowledgement requirements (fsync / parent-dir / backend-effect)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WALAckRequirements(CanonicalContract):
    """Declared durability requirements for an acknowledgement mode.

    Every mode that may claim committed/durable must state whether file
    ``fsync``, parent-directory durability, and a backend effect are required.
    Buffered/queued modes set all three to false and ``may_claim_committed`` to
    false so callers cannot silently upgrade.
    """

    SCHEMA: ClassVar[str] = WAL_ACK_REQUIREMENTS_SCHEMA

    mode: WALAcknowledgementMode
    requires_file_fsync: bool
    requires_parent_directory_fsync: bool
    requires_backend_effect: bool
    may_claim_committed: bool
    may_claim_prepared: bool
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "mode", _enum(self.mode, WALAcknowledgementMode, "mode")
        )
        object.__setattr__(
            self,
            "requires_file_fsync",
            _bool(self.requires_file_fsync, "requires_file_fsync"),
        )
        object.__setattr__(
            self,
            "requires_parent_directory_fsync",
            _bool(
                self.requires_parent_directory_fsync,
                "requires_parent_directory_fsync",
            ),
        )
        object.__setattr__(
            self,
            "requires_backend_effect",
            _bool(self.requires_backend_effect, "requires_backend_effect"),
        )
        object.__setattr__(
            self,
            "may_claim_committed",
            _bool(self.may_claim_committed, "may_claim_committed"),
        )
        object.__setattr__(
            self,
            "may_claim_prepared",
            _bool(self.may_claim_prepared, "may_claim_prepared"),
        )
        object.__setattr__(
            self,
            "description",
            _text(self.description, "description", limit=MAX_TEXT_BYTES),
        )
        # Buffered/queued can never claim durable outcomes.
        if self.mode in (
            WALAcknowledgementMode.BUFFERED,
            WALAcknowledgementMode.QUEUED,
        ):
            if self.may_claim_committed or self.may_claim_prepared:
                raise WALAcknowledgementError(
                    f"{self.mode.value} must not claim prepared/committed"
                )
            if (
                self.requires_file_fsync
                or self.requires_parent_directory_fsync
                or self.requires_backend_effect
            ):
                raise WALAcknowledgementError(
                    f"{self.mode.value} cannot require durability evidence"
                )
        if self.may_claim_committed and not (
            self.requires_file_fsync
            or self.mode
            in (
                WALAcknowledgementMode.WAL_APPENDED,
                WALAcknowledgementMode.BACKEND_EFFECT,
                WALAcknowledgementMode.BACKEND_DURABLE,
            )
        ):
            # WAL_APPENDED is an explicit weak mode; still may_claim only with
            # append evidence (enforced at claim time).
            pass
        _bounded_record(self, "wal ack requirements")

    def _payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "requires_file_fsync": self.requires_file_fsync,
            "requires_parent_directory_fsync": self.requires_parent_directory_fsync,
            "requires_backend_effect": self.requires_backend_effect,
            "may_claim_committed": self.may_claim_committed,
            "may_claim_prepared": self.may_claim_prepared,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WALAckRequirements":
        fields = (
            "mode",
            "requires_file_fsync",
            "requires_parent_directory_fsync",
            "requires_backend_effect",
            "may_claim_committed",
            "may_claim_prepared",
            "description",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "wal ack requirements")
        value = cls(
            mode=raw["mode"]
            if raw["mode"] is not None
            else WALAcknowledgementMode.BUFFERED,
            requires_file_fsync=bool(raw.get("requires_file_fsync") or False),
            requires_parent_directory_fsync=bool(
                raw.get("requires_parent_directory_fsync") or False
            ),
            requires_backend_effect=bool(raw.get("requires_backend_effect") or False),
            may_claim_committed=bool(raw.get("may_claim_committed") or False),
            may_claim_prepared=bool(raw.get("may_claim_prepared") or False),
            description=raw.get("description") or "",
        )
        _verify_identity(payload, value)
        return value


_ACK_REQUIREMENTS_TABLE: Final[Mapping[WALAcknowledgementMode, WALAckRequirements]] = {
    WALAcknowledgementMode.BUFFERED: WALAckRequirements(
        mode=WALAcknowledgementMode.BUFFERED,
        requires_file_fsync=False,
        requires_parent_directory_fsync=False,
        requires_backend_effect=False,
        may_claim_committed=False,
        may_claim_prepared=False,
        description="In-memory only; never durable; never committed.",
    ),
    WALAcknowledgementMode.QUEUED: WALAckRequirements(
        mode=WALAcknowledgementMode.QUEUED,
        requires_file_fsync=False,
        requires_parent_directory_fsync=False,
        requires_backend_effect=False,
        may_claim_committed=False,
        may_claim_prepared=False,
        description="Queued for append; not on durable media; never committed.",
    ),
    WALAcknowledgementMode.WAL_APPENDED: WALAckRequirements(
        mode=WALAcknowledgementMode.WAL_APPENDED,
        requires_file_fsync=False,
        requires_parent_directory_fsync=False,
        requires_backend_effect=False,
        may_claim_committed=True,
        may_claim_prepared=True,
        description=(
            "Bytes present in open segment; crash may lose tail; "
            "commit claim requires append evidence only (weak mode)."
        ),
    ),
    WALAcknowledgementMode.WAL_FSYNC: WALAckRequirements(
        mode=WALAcknowledgementMode.WAL_FSYNC,
        requires_file_fsync=True,
        requires_parent_directory_fsync=False,
        requires_backend_effect=False,
        may_claim_committed=True,
        may_claim_prepared=True,
        description="File fsync required before prepared/committed claims.",
    ),
    WALAcknowledgementMode.WAL_FSYNC_PARENT: WALAckRequirements(
        mode=WALAcknowledgementMode.WAL_FSYNC_PARENT,
        requires_file_fsync=True,
        requires_parent_directory_fsync=True,
        requires_backend_effect=False,
        may_claim_committed=True,
        may_claim_prepared=True,
        description=(
            "File fsync and parent-directory durability required before "
            "prepared/committed claims."
        ),
    ),
    WALAcknowledgementMode.GROUP_COMMIT: WALAckRequirements(
        mode=WALAcknowledgementMode.GROUP_COMMIT,
        requires_file_fsync=True,
        requires_parent_directory_fsync=True,
        requires_backend_effect=False,
        may_claim_committed=True,
        may_claim_prepared=True,
        description=(
            "Group commit: file + parent-directory durability and a shared "
            "commit marker are required."
        ),
    ),
    WALAcknowledgementMode.BACKEND_EFFECT: WALAckRequirements(
        mode=WALAcknowledgementMode.BACKEND_EFFECT,
        requires_file_fsync=True,
        requires_parent_directory_fsync=False,
        requires_backend_effect=True,
        may_claim_committed=True,
        may_claim_prepared=True,
        description=(
            "WAL fsync plus an observed backend effect are required before "
            "committed claims."
        ),
    ),
    WALAcknowledgementMode.BACKEND_DURABLE: WALAckRequirements(
        mode=WALAcknowledgementMode.BACKEND_DURABLE,
        requires_file_fsync=True,
        requires_parent_directory_fsync=True,
        requires_backend_effect=True,
        may_claim_committed=True,
        may_claim_prepared=True,
        description=(
            "Full durability: file fsync, parent-directory durability, and "
            "backend durable acknowledgement."
        ),
    ),
}


def ack_requirements_for(mode: WALAcknowledgementMode | str) -> WALAckRequirements:
    """Return the declared fsync/parent-dir/backend requirements for ``mode``."""

    if not isinstance(mode, WALAcknowledgementMode):
        mode = _enum(mode, WALAcknowledgementMode, "mode")
    return _ACK_REQUIREMENTS_TABLE[mode]


def all_ack_requirements() -> tuple[WALAckRequirements, ...]:
    """Return requirements for every acknowledgement mode (stable order)."""

    return tuple(_ACK_REQUIREMENTS_TABLE[mode] for mode in WALAcknowledgementMode)


# ---------------------------------------------------------------------------
# Record identity (generation + sequence) — collision-safe & monotonic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WALRecordIdentity(CanonicalContract):
    """Collision-safe record identity within a WAL generation.

    Identity is the pair ``(generation_id, sequence_number)``.  Sequences are
    totally ordered and strictly monotonic within a generation.  Distinct
    generations never collide even if sequence numbers restart at zero.
    """

    SCHEMA: ClassVar[str] = WAL_RECORD_IDENTITY_SCHEMA

    generation_id: str
    sequence_number: int
    segment_id: str = ""
    record_key: str = ""  # optional stable external key; does not replace sequence

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "generation_id",
            _identifier(self.generation_id, "generation_id"),
        )
        object.__setattr__(
            self,
            "sequence_number",
            _bounded_int(
                self.sequence_number,
                "sequence_number",
                minimum=0,
                maximum=MAX_SEQUENCE,
            ),
        )
        object.__setattr__(
            self, "segment_id", _optional_identifier(self.segment_id, "segment_id")
        )
        object.__setattr__(
            self, "record_key", _optional_identifier(self.record_key, "record_key")
        )
        _bounded_record(self, "wal record identity")

    def _payload(self) -> dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "sequence_number": self.sequence_number,
            "segment_id": self.segment_id,
            "record_key": self.record_key,
        }

    @property
    def identity_tuple(self) -> tuple[str, int]:
        return (self.generation_id, self.sequence_number)

    @property
    def identity_key(self) -> str:
        """Opaque collision-safe key for maps and indexes."""

        return f"{self.generation_id}#{self.sequence_number}"

    def precedes(self, other: "WALRecordIdentity") -> bool:
        """Return True if this identity is strictly before ``other`` in-order.

        Cross-generation ordering is undefined; only same-generation pairs
        compare.  Different generations never collide.
        """

        if self.generation_id != other.generation_id:
            raise WALSequenceError(
                "cannot order record identities across generations"
            )
        return self.sequence_number < other.sequence_number

    def is_successor_of(self, other: "WALRecordIdentity") -> bool:
        """Return True if this is the immediate next sequence in the generation."""

        if self.generation_id != other.generation_id:
            return False
        return self.sequence_number == other.sequence_number + 1

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WALRecordIdentity":
        fields = ("generation_id", "sequence_number", "segment_id", "record_key")
        raw = _decode_fields(payload, cls.SCHEMA, fields, "wal record identity")
        value = cls(
            generation_id=raw["generation_id"] or "",
            sequence_number=int(raw["sequence_number"] or 0),
            segment_id=raw.get("segment_id") or "",
            record_key=raw.get("record_key") or "",
        )
        _verify_identity(payload, value)
        return value


def assert_sequence_monotonic(
    previous: WALRecordIdentity | None,
    current: WALRecordIdentity,
    *,
    allow_equal: bool = False,
) -> None:
    """Assert ``current`` is collision-safe and monotonic after ``previous``.

    * Same ``(generation_id, sequence_number)`` is always a collision error.
    * Within a generation, ``current.sequence_number`` must be greater than
      (or, if ``allow_equal``, not less than) ``previous.sequence_number``.
    * Across generations, ordering is not required; only collision-safety of
      the pair identity is enforced (always true when generation differs).
    """

    if previous is None:
        return
    if previous.identity_tuple == current.identity_tuple:
        raise WALSequenceError(
            f"collision: duplicate record identity {current.identity_key}"
        )
    if previous.generation_id != current.generation_id:
        return
    if allow_equal and current.sequence_number >= previous.sequence_number:
        return
    if current.sequence_number > previous.sequence_number:
        return
    raise WALSequenceError(
        f"sequence not monotonic within generation {current.generation_id}: "
        f"{previous.sequence_number} → {current.sequence_number}"
    )


def assert_sequence_chain(
    identities: Sequence[WALRecordIdentity],
    *,
    require_contiguous: bool = False,
) -> None:
    """Validate a sequence of identities for collisions and monotonicity."""

    seen: set[tuple[str, int]] = set()
    previous: WALRecordIdentity | None = None
    for identity in identities:
        key = identity.identity_tuple
        if key in seen:
            raise WALSequenceError(f"collision: duplicate record identity {identity.identity_key}")
        seen.add(key)
        if previous is not None and previous.generation_id == identity.generation_id:
            if identity.sequence_number <= previous.sequence_number:
                raise WALSequenceError(
                    f"sequence not monotonic: {previous.identity_key} → "
                    f"{identity.identity_key}"
                )
            if require_contiguous and not identity.is_successor_of(previous):
                raise WALSequenceError(
                    f"sequence gap within generation {identity.generation_id}: "
                    f"{previous.sequence_number} → {identity.sequence_number}"
                )
        previous = identity


# ---------------------------------------------------------------------------
# Fsync / durability receipts (bounded references)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WALFsyncReceipt(CanonicalContract):
    """Bounded receipt that a file and/or parent-directory fsync occurred."""

    SCHEMA: ClassVar[str] = WAL_FSYNC_RECEIPT_SCHEMA

    receipt_id: str
    generation_id: str
    sequence_number: int
    file_fsync_observed: bool
    parent_directory_fsync_observed: bool
    segment_id: str = ""
    path_ref: str = ""  # opaque path identity, not a host absolute body
    backend_effect_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "receipt_id", _identifier(self.receipt_id, "receipt_id")
        )
        object.__setattr__(
            self,
            "generation_id",
            _identifier(self.generation_id, "generation_id"),
        )
        object.__setattr__(
            self,
            "sequence_number",
            _bounded_int(self.sequence_number, "sequence_number", minimum=0),
        )
        object.__setattr__(
            self,
            "file_fsync_observed",
            _bool(self.file_fsync_observed, "file_fsync_observed"),
        )
        object.__setattr__(
            self,
            "parent_directory_fsync_observed",
            _bool(
                self.parent_directory_fsync_observed,
                "parent_directory_fsync_observed",
            ),
        )
        object.__setattr__(
            self, "segment_id", _optional_identifier(self.segment_id, "segment_id")
        )
        object.__setattr__(
            self, "path_ref", _optional_identifier(self.path_ref, "path_ref")
        )
        object.__setattr__(
            self,
            "backend_effect_id",
            _optional_identifier(self.backend_effect_id, "backend_effect_id"),
        )
        _bounded_record(self, "wal fsync receipt")

    def _payload(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "generation_id": self.generation_id,
            "sequence_number": self.sequence_number,
            "file_fsync_observed": self.file_fsync_observed,
            "parent_directory_fsync_observed": self.parent_directory_fsync_observed,
            "segment_id": self.segment_id,
            "path_ref": self.path_ref,
            "backend_effect_id": self.backend_effect_id,
        }

    def satisfies(self, requirements: WALAckRequirements) -> bool:
        if requirements.requires_file_fsync and not self.file_fsync_observed:
            return False
        if (
            requirements.requires_parent_directory_fsync
            and not self.parent_directory_fsync_observed
        ):
            return False
        if requirements.requires_backend_effect and not self.backend_effect_id:
            return False
        return True

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WALFsyncReceipt":
        fields = (
            "receipt_id",
            "generation_id",
            "sequence_number",
            "file_fsync_observed",
            "parent_directory_fsync_observed",
            "segment_id",
            "path_ref",
            "backend_effect_id",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "wal fsync receipt")
        value = cls(
            receipt_id=raw["receipt_id"] or "",
            generation_id=raw["generation_id"] or "",
            sequence_number=int(raw["sequence_number"] or 0),
            file_fsync_observed=bool(raw.get("file_fsync_observed") or False),
            parent_directory_fsync_observed=bool(
                raw.get("parent_directory_fsync_observed") or False
            ),
            segment_id=raw.get("segment_id") or "",
            path_ref=raw.get("path_ref") or "",
            backend_effect_id=raw.get("backend_effect_id") or "",
        )
        _verify_identity(payload, value)
        return value


def assert_ack_allows_state(
    mode: WALAcknowledgementMode | str,
    state: WALRecordState,
    *,
    fsync_receipt: WALFsyncReceipt | None = None,
    append_observed: bool = False,
) -> None:
    """Fail closed if ``state`` is not permitted under ``mode`` (+ evidence)."""

    requirements = ack_requirements_for(mode)
    if state in BUFFERED_OR_QUEUED_STATES:
        if state is WALRecordState.BUFFERED and requirements.mode is not (
            WALAcknowledgementMode.BUFFERED
        ):
            # Queued/other modes may still pass through buffered briefly.
            pass
        return

    if state in COMMITTED_STATES or state is WALRecordState.PREPARED:
        claiming_commit = state in COMMITTED_STATES
        claiming_prepare = state is WALRecordState.PREPARED
        if claiming_commit and not requirements.may_claim_committed:
            raise WALAcknowledgementError(
                f"mode {requirements.mode.value} cannot claim committed "
                f"(state={state.value})"
            )
        if claiming_prepare and not requirements.may_claim_prepared:
            raise WALAcknowledgementError(
                f"mode {requirements.mode.value} cannot claim prepared"
            )
        if requirements.mode is WALAcknowledgementMode.WAL_APPENDED:
            if not append_observed and fsync_receipt is None:
                raise WALAcknowledgementError(
                    "wal_appended commit/prepare requires append evidence"
                )
            return
        if fsync_receipt is None:
            if (
                requirements.requires_file_fsync
                or requirements.requires_parent_directory_fsync
                or requirements.requires_backend_effect
            ):
                raise WALAcknowledgementError(
                    f"mode {requirements.mode.value} requires fsync/backend "
                    f"receipt before {state.value}"
                )
            return
        if not fsync_receipt.satisfies(requirements):
            raise WALAcknowledgementError(
                f"fsync receipt does not satisfy mode {requirements.mode.value} "
                f"for state {state.value}"
            )


# ---------------------------------------------------------------------------
# Core records: WALRecord, WALTransaction, WALSegment, WALCheckpoint
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WALRecord(CanonicalContract):
    """Canonical framed WAL record (``WALRecord@1``).

    Payloads are bounded references only.  Record identity is the pair
    ``(generation_id, sequence_number)``.  State transitions are closed;
    buffered/queued never equals committed.
    """

    SCHEMA: ClassVar[str] = WAL_RECORD_SCHEMA

    generation_id: str
    sequence_number: int
    kind: WALRecordKind
    state: WALRecordState
    acknowledgement_mode: WALAcknowledgementMode
    transaction_id: str = ""
    segment_id: str = ""
    record_key: str = ""
    payload: PayloadReference | None = None
    payload_cid: str = ""
    checksum: str = ""
    previous_sequence: int = -1  # -1 means none / genesis
    encoding: str = ""  # media encoding of referenced payload; unsafe rejected
    fsync_receipt_id: str = ""
    backend_effect_id: str = ""
    operation_id: str = ""
    principal_id: str = ""
    created_at_unix_ms: int = 0
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "generation_id",
            _identifier(self.generation_id, "generation_id"),
        )
        object.__setattr__(
            self,
            "sequence_number",
            _bounded_int(self.sequence_number, "sequence_number", minimum=0),
        )
        object.__setattr__(self, "kind", _enum(self.kind, WALRecordKind, "kind"))
        object.__setattr__(self, "state", _enum(self.state, WALRecordState, "state"))
        object.__setattr__(
            self,
            "acknowledgement_mode",
            _enum(
                self.acknowledgement_mode,
                WALAcknowledgementMode,
                "acknowledgement_mode",
            ),
        )
        object.__setattr__(
            self,
            "transaction_id",
            _optional_identifier(self.transaction_id, "transaction_id"),
        )
        object.__setattr__(
            self, "segment_id", _optional_identifier(self.segment_id, "segment_id")
        )
        object.__setattr__(
            self, "record_key", _optional_identifier(self.record_key, "record_key")
        )
        payload = self.payload
        if payload is not None and not isinstance(payload, PayloadReference):
            payload = _payload_reference(payload)
            object.__setattr__(self, "payload", payload)
        object.__setattr__(
            self, "payload_cid", _optional_cid(self.payload_cid, "payload_cid")
        )
        if payload is not None and payload.content_cid and not self.payload_cid:
            object.__setattr__(self, "payload_cid", payload.content_cid)
        object.__setattr__(self, "checksum", _checksum(self.checksum, "checksum"))
        object.__setattr__(
            self,
            "previous_sequence",
            _bounded_int(
                self.previous_sequence,
                "previous_sequence",
                minimum=-1,
                maximum=MAX_SEQUENCE,
            ),
        )
        object.__setattr__(
            self, "encoding", _assert_safe_encoding(self.encoding or "", "encoding")
        )
        object.__setattr__(
            self,
            "fsync_receipt_id",
            _optional_identifier(self.fsync_receipt_id, "fsync_receipt_id"),
        )
        object.__setattr__(
            self,
            "backend_effect_id",
            _optional_identifier(self.backend_effect_id, "backend_effect_id"),
        )
        object.__setattr__(
            self,
            "operation_id",
            _optional_identifier(self.operation_id, "operation_id"),
        )
        object.__setattr__(
            self,
            "principal_id",
            _optional_identifier(self.principal_id, "principal_id"),
        )
        object.__setattr__(
            self,
            "created_at_unix_ms",
            _bounded_int(self.created_at_unix_ms, "created_at_unix_ms", minimum=0),
        )
        object.__setattr__(
            self, "notes", _text(self.notes, "notes", limit=MAX_TEXT_BYTES)
        )

        if self.previous_sequence >= 0 and self.previous_sequence >= self.sequence_number:
            raise WALSequenceError(
                "previous_sequence must be strictly less than sequence_number"
            )

        # Buffered/queued cannot claim durable modes' committed evidence.
        if self.state in BUFFERED_OR_QUEUED_STATES and self.state in COMMITTED_STATES:
            raise InconsistentStateError("state cannot be both buffered and committed")

        if self.state in COMMITTED_STATES or self.state is WALRecordState.PREPARED:
            requirements = ack_requirements_for(self.acknowledgement_mode)
            if self.state in COMMITTED_STATES and not requirements.may_claim_committed:
                raise WALAcknowledgementError(
                    f"state {self.state.value} forbidden under mode "
                    f"{self.acknowledgement_mode.value}"
                )
            if (
                self.state is WALRecordState.PREPARED
                and not requirements.may_claim_prepared
            ):
                raise WALAcknowledgementError(
                    f"prepared forbidden under mode {self.acknowledgement_mode.value}"
                )
            if requirements.requires_file_fsync and not self.fsync_receipt_id:
                raise WALAcknowledgementError(
                    f"mode {self.acknowledgement_mode.value} requires "
                    f"fsync_receipt_id for state {self.state.value}"
                )
            if requirements.requires_backend_effect and not self.backend_effect_id:
                raise WALAcknowledgementError(
                    f"mode {self.acknowledgement_mode.value} requires "
                    f"backend_effect_id for state {self.state.value}"
                )
            # Parent-directory requirement is declared on the mode; the fsync
            # receipt (when present) carries the observation.  At record
            # construction we require the receipt id when parent durability is
            # required so the observation is addressable.
            if (
                requirements.requires_parent_directory_fsync
                and not self.fsync_receipt_id
            ):
                raise WALAcknowledgementError(
                    f"mode {self.acknowledgement_mode.value} requires "
                    f"fsync_receipt_id (parent-directory durability) for "
                    f"state {self.state.value}"
                )

        # Commit/prepare/abort kinds should carry a transaction id.
        if self.kind in (
            WALRecordKind.BEGIN,
            WALRecordKind.PREPARE,
            WALRecordKind.COMMIT,
            WALRecordKind.ABORT,
        ) and not self.transaction_id:
            raise WALContractError(
                f"record kind {self.kind.value} requires transaction_id"
            )

        _bounded_record(self, "wal record")

    @property
    def identity(self) -> WALRecordIdentity:
        return WALRecordIdentity(
            generation_id=self.generation_id,
            sequence_number=self.sequence_number,
            segment_id=self.segment_id,
            record_key=self.record_key,
        )

    @property
    def identity_key(self) -> str:
        return self.identity.identity_key

    @property
    def is_durable(self) -> bool:
        return self.state in DURABLE_STATES

    @property
    def is_committed(self) -> bool:
        return self.state in COMMITTED_STATES

    @property
    def is_buffered_or_queued(self) -> bool:
        return self.state in BUFFERED_OR_QUEUED_STATES

    def _payload(self) -> dict[str, Any]:
        payload_dict: dict[str, Any] | None
        if self.payload is None:
            payload_dict = None
        else:
            payload_dict = self.payload.to_dict()
        return {
            "generation_id": self.generation_id,
            "sequence_number": self.sequence_number,
            "kind": self.kind.value,
            "state": self.state.value,
            "acknowledgement_mode": self.acknowledgement_mode.value,
            "transaction_id": self.transaction_id,
            "segment_id": self.segment_id,
            "record_key": self.record_key,
            "payload": payload_dict,
            "payload_cid": self.payload_cid,
            "checksum": self.checksum,
            "previous_sequence": self.previous_sequence,
            "encoding": self.encoding,
            "fsync_receipt_id": self.fsync_receipt_id,
            "backend_effect_id": self.backend_effect_id,
            "operation_id": self.operation_id,
            "principal_id": self.principal_id,
            "created_at_unix_ms": self.created_at_unix_ms,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WALRecord":
        fields = (
            "generation_id",
            "sequence_number",
            "kind",
            "state",
            "acknowledgement_mode",
            "transaction_id",
            "segment_id",
            "record_key",
            "payload",
            "payload_cid",
            "checksum",
            "previous_sequence",
            "encoding",
            "fsync_receipt_id",
            "backend_effect_id",
            "operation_id",
            "principal_id",
            "created_at_unix_ms",
            "notes",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "wal record")
        previous = raw.get("previous_sequence")
        if previous is None:
            previous_sequence = -1
        else:
            previous_sequence = int(previous)
        value = cls(
            generation_id=raw["generation_id"] or "",
            sequence_number=int(raw["sequence_number"] or 0),
            kind=raw["kind"] if raw["kind"] is not None else WALRecordKind.UNKNOWN,
            state=(
                raw["state"] if raw["state"] is not None else WALRecordState.BUFFERED
            ),
            acknowledgement_mode=(
                raw["acknowledgement_mode"]
                if raw["acknowledgement_mode"] is not None
                else WALAcknowledgementMode.BUFFERED
            ),
            transaction_id=raw.get("transaction_id") or "",
            segment_id=raw.get("segment_id") or "",
            record_key=raw.get("record_key") or "",
            payload=_payload_reference(raw.get("payload")),
            payload_cid=raw.get("payload_cid") or "",
            checksum=raw.get("checksum") or "",
            previous_sequence=previous_sequence,
            encoding=raw.get("encoding") or "",
            fsync_receipt_id=raw.get("fsync_receipt_id") or "",
            backend_effect_id=raw.get("backend_effect_id") or "",
            operation_id=raw.get("operation_id") or "",
            principal_id=raw.get("principal_id") or "",
            created_at_unix_ms=int(raw.get("created_at_unix_ms") or 0),
            notes=raw.get("notes") or "",
        )
        _verify_identity(payload, value)
        return value


@dataclass(frozen=True)
class WALTransaction(CanonicalContract):
    """Canonical multi-record WAL transaction (``WALTransaction@1``)."""

    SCHEMA: ClassVar[str] = WAL_TRANSACTION_SCHEMA

    transaction_id: str
    generation_id: str
    state: WALTransactionState
    acknowledgement_mode: WALAcknowledgementMode
    begin_sequence: int = -1
    prepare_sequence: int = -1
    commit_sequence: int = -1
    abort_sequence: int = -1
    record_sequences: tuple[int, ...] = ()
    operation_id: str = ""
    principal_id: str = ""
    fsync_receipt_id: str = ""
    backend_effect_id: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transaction_id",
            _identifier(self.transaction_id, "transaction_id"),
        )
        object.__setattr__(
            self,
            "generation_id",
            _identifier(self.generation_id, "generation_id"),
        )
        object.__setattr__(
            self, "state", _enum(self.state, WALTransactionState, "state")
        )
        object.__setattr__(
            self,
            "acknowledgement_mode",
            _enum(
                self.acknowledgement_mode,
                WALAcknowledgementMode,
                "acknowledgement_mode",
            ),
        )
        for name in (
            "begin_sequence",
            "prepare_sequence",
            "commit_sequence",
            "abort_sequence",
        ):
            object.__setattr__(
                self,
                name,
                _bounded_int(
                    getattr(self, name), name, minimum=-1, maximum=MAX_SEQUENCE
                ),
            )
        sequences = self.record_sequences
        if sequences is None:
            sequences = ()
        if isinstance(sequences, Sequence) and not isinstance(
            sequences, (str, bytes, bytearray)
        ):
            normalized_seqs: list[int] = []
            for item in sequences:
                normalized_seqs.append(
                    _bounded_int(item, "record_sequences", minimum=0)
                )
            if len(normalized_seqs) > MAX_REFERENCE_COUNT:
                raise WALContractBoundsError("record_sequences exceeds bound")
            # Must be strictly increasing (monotonic within generation).
            for index in range(1, len(normalized_seqs)):
                if normalized_seqs[index] <= normalized_seqs[index - 1]:
                    raise WALSequenceError(
                        "record_sequences must be strictly monotonic"
                    )
            object.__setattr__(self, "record_sequences", tuple(normalized_seqs))
        else:
            raise WALContractError("record_sequences must be a sequence of integers")

        object.__setattr__(
            self,
            "operation_id",
            _optional_identifier(self.operation_id, "operation_id"),
        )
        object.__setattr__(
            self,
            "principal_id",
            _optional_identifier(self.principal_id, "principal_id"),
        )
        object.__setattr__(
            self,
            "fsync_receipt_id",
            _optional_identifier(self.fsync_receipt_id, "fsync_receipt_id"),
        )
        object.__setattr__(
            self,
            "backend_effect_id",
            _optional_identifier(self.backend_effect_id, "backend_effect_id"),
        )
        object.__setattr__(
            self, "notes", _text(self.notes, "notes", limit=MAX_TEXT_BYTES)
        )

        requirements = ack_requirements_for(self.acknowledgement_mode)
        if self.state is WALTransactionState.COMMITTED:
            if not requirements.may_claim_committed:
                raise WALAcknowledgementError(
                    f"mode {self.acknowledgement_mode.value} cannot commit"
                )
            if self.commit_sequence < 0:
                raise InconsistentStateError(
                    "committed transaction requires commit_sequence"
                )
            if requirements.requires_file_fsync and not self.fsync_receipt_id:
                raise WALAcknowledgementError(
                    "committed transaction requires fsync_receipt_id"
                )
            if requirements.requires_parent_directory_fsync and not self.fsync_receipt_id:
                raise WALAcknowledgementError(
                    "committed transaction requires fsync_receipt_id "
                    "(parent-directory durability)"
                )
            if requirements.requires_backend_effect and not self.backend_effect_id:
                raise WALAcknowledgementError(
                    "committed transaction requires backend_effect_id"
                )
        if self.state is WALTransactionState.ABORTED and self.abort_sequence < 0:
            raise InconsistentStateError("aborted transaction requires abort_sequence")
        if self.state is WALTransactionState.PREPARED and self.prepare_sequence < 0:
            raise InconsistentStateError(
                "prepared transaction requires prepare_sequence"
            )
        if (
            self.commit_sequence >= 0
            and self.abort_sequence >= 0
            and self.state
            in (WALTransactionState.COMMITTED, WALTransactionState.ABORTED)
        ):
            # Both markers may exist historically; terminal state must pick one.
            if self.state is WALTransactionState.COMMITTED and self.abort_sequence > self.commit_sequence:
                raise InconsistentStateError(
                    "abort after commit is not a committed transaction"
                )

        _bounded_record(self, "wal transaction")

    @property
    def is_committed(self) -> bool:
        return self.state is WALTransactionState.COMMITTED

    def _payload(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "generation_id": self.generation_id,
            "state": self.state.value,
            "acknowledgement_mode": self.acknowledgement_mode.value,
            "begin_sequence": self.begin_sequence,
            "prepare_sequence": self.prepare_sequence,
            "commit_sequence": self.commit_sequence,
            "abort_sequence": self.abort_sequence,
            "record_sequences": list(self.record_sequences),
            "operation_id": self.operation_id,
            "principal_id": self.principal_id,
            "fsync_receipt_id": self.fsync_receipt_id,
            "backend_effect_id": self.backend_effect_id,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WALTransaction":
        fields = (
            "transaction_id",
            "generation_id",
            "state",
            "acknowledgement_mode",
            "begin_sequence",
            "prepare_sequence",
            "commit_sequence",
            "abort_sequence",
            "record_sequences",
            "operation_id",
            "principal_id",
            "fsync_receipt_id",
            "backend_effect_id",
            "notes",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "wal transaction")

        def _seq(name: str) -> int:
            value = raw.get(name)
            return -1 if value is None else int(value)

        value = cls(
            transaction_id=raw["transaction_id"] or "",
            generation_id=raw["generation_id"] or "",
            state=(
                raw["state"]
                if raw["state"] is not None
                else WALTransactionState.OPEN
            ),
            acknowledgement_mode=(
                raw["acknowledgement_mode"]
                if raw["acknowledgement_mode"] is not None
                else WALAcknowledgementMode.BUFFERED
            ),
            begin_sequence=_seq("begin_sequence"),
            prepare_sequence=_seq("prepare_sequence"),
            commit_sequence=_seq("commit_sequence"),
            abort_sequence=_seq("abort_sequence"),
            record_sequences=tuple(raw.get("record_sequences") or ()),
            operation_id=raw.get("operation_id") or "",
            principal_id=raw.get("principal_id") or "",
            fsync_receipt_id=raw.get("fsync_receipt_id") or "",
            backend_effect_id=raw.get("backend_effect_id") or "",
            notes=raw.get("notes") or "",
        )
        _verify_identity(payload, value)
        return value


@dataclass(frozen=True)
class WALSegment(CanonicalContract):
    """Canonical WAL segment descriptor (``WALSegment@1``)."""

    SCHEMA: ClassVar[str] = WAL_SEGMENT_SCHEMA

    segment_id: str
    generation_id: str
    state: WALSegmentState
    first_sequence: int
    last_sequence: int
    checksum: str = ""
    path_ref: str = ""
    sealed: bool = False
    checkpoint_id: str = ""
    archive_receipt_id: str = ""
    record_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "segment_id", _identifier(self.segment_id, "segment_id")
        )
        object.__setattr__(
            self,
            "generation_id",
            _identifier(self.generation_id, "generation_id"),
        )
        object.__setattr__(
            self, "state", _enum(self.state, WALSegmentState, "state")
        )
        object.__setattr__(
            self,
            "first_sequence",
            _bounded_int(self.first_sequence, "first_sequence", minimum=0),
        )
        object.__setattr__(
            self,
            "last_sequence",
            _bounded_int(self.last_sequence, "last_sequence", minimum=0),
        )
        if self.last_sequence < self.first_sequence:
            raise WALSequenceError(
                "last_sequence must be >= first_sequence within a segment"
            )
        object.__setattr__(self, "checksum", _checksum(self.checksum, "checksum"))
        object.__setattr__(
            self, "path_ref", _optional_identifier(self.path_ref, "path_ref")
        )
        object.__setattr__(self, "sealed", _bool(self.sealed, "sealed"))
        object.__setattr__(
            self,
            "checkpoint_id",
            _optional_identifier(self.checkpoint_id, "checkpoint_id"),
        )
        object.__setattr__(
            self,
            "archive_receipt_id",
            _optional_identifier(self.archive_receipt_id, "archive_receipt_id"),
        )
        object.__setattr__(
            self,
            "record_count",
            _bounded_int(self.record_count, "record_count", minimum=0),
        )
        if self.state in (
            WALSegmentState.SEALED,
            WALSegmentState.CHECKPOINTED,
            WALSegmentState.ARCHIVED,
        ):
            if not self.sealed:
                raise InconsistentStateError(
                    f"segment state {self.state.value} requires sealed=True"
                )
        if self.state is WALSegmentState.OPEN and self.sealed:
            raise InconsistentStateError("open segment cannot be sealed")
        if self.state is WALSegmentState.CHECKPOINTED and not self.checkpoint_id:
            raise InconsistentStateError(
                "checkpointed segment requires checkpoint_id"
            )
        if self.state is WALSegmentState.ARCHIVED and not self.archive_receipt_id:
            raise InconsistentStateError(
                "archived segment requires archive_receipt_id"
            )
        # Rotation rule: sealed/checkpointed segments must not accept appends
        # (expressed as sealed flag + non-open state).
        _bounded_record(self, "wal segment")

    @property
    def accepts_appends(self) -> bool:
        return self.state is WALSegmentState.OPEN and not self.sealed

    def _payload(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "generation_id": self.generation_id,
            "state": self.state.value,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "checksum": self.checksum,
            "path_ref": self.path_ref,
            "sealed": self.sealed,
            "checkpoint_id": self.checkpoint_id,
            "archive_receipt_id": self.archive_receipt_id,
            "record_count": self.record_count,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WALSegment":
        fields = (
            "segment_id",
            "generation_id",
            "state",
            "first_sequence",
            "last_sequence",
            "checksum",
            "path_ref",
            "sealed",
            "checkpoint_id",
            "archive_receipt_id",
            "record_count",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "wal segment")
        value = cls(
            segment_id=raw["segment_id"] or "",
            generation_id=raw["generation_id"] or "",
            state=(
                raw["state"] if raw["state"] is not None else WALSegmentState.OPEN
            ),
            first_sequence=int(raw["first_sequence"] or 0),
            last_sequence=int(raw["last_sequence"] or 0),
            checksum=raw.get("checksum") or "",
            path_ref=raw.get("path_ref") or "",
            sealed=bool(raw.get("sealed") or False),
            checkpoint_id=raw.get("checkpoint_id") or "",
            archive_receipt_id=raw.get("archive_receipt_id") or "",
            record_count=int(raw.get("record_count") or 0),
        )
        _verify_identity(payload, value)
        return value


@dataclass(frozen=True)
class WALCheckpoint(CanonicalContract):
    """Canonical WAL checkpoint publication (``WALCheckpoint@1``).

    Checkpoint identity covers the exact sealed segments up to
    ``through_sequence``.  Appends after the checkpoint cannot be skipped by
    recovery that only loads this checkpoint.
    """

    SCHEMA: ClassVar[str] = WAL_CHECKPOINT_SCHEMA

    checkpoint_id: str
    generation_id: str
    through_sequence: int
    state: WALCheckpointState
    sealed_segment_ids: tuple[str, ...]
    checksum: str = ""
    archive_receipt_id: str = ""
    previous_checkpoint_id: str = ""
    created_at_unix_ms: int = 0
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "checkpoint_id",
            _identifier(self.checkpoint_id, "checkpoint_id"),
        )
        object.__setattr__(
            self,
            "generation_id",
            _identifier(self.generation_id, "generation_id"),
        )
        object.__setattr__(
            self,
            "through_sequence",
            _bounded_int(self.through_sequence, "through_sequence", minimum=0),
        )
        object.__setattr__(
            self, "state", _enum(self.state, WALCheckpointState, "state")
        )
        object.__setattr__(
            self,
            "sealed_segment_ids",
            _ids(self.sealed_segment_ids, "sealed_segment_ids", required=False),
        )
        object.__setattr__(self, "checksum", _checksum(self.checksum, "checksum"))
        object.__setattr__(
            self,
            "archive_receipt_id",
            _optional_identifier(self.archive_receipt_id, "archive_receipt_id"),
        )
        object.__setattr__(
            self,
            "previous_checkpoint_id",
            _optional_identifier(
                self.previous_checkpoint_id, "previous_checkpoint_id"
            ),
        )
        object.__setattr__(
            self,
            "created_at_unix_ms",
            _bounded_int(self.created_at_unix_ms, "created_at_unix_ms", minimum=0),
        )
        object.__setattr__(
            self, "notes", _text(self.notes, "notes", limit=MAX_TEXT_BYTES)
        )
        if self.state in (
            WALCheckpointState.PUBLISHED,
            WALCheckpointState.ARCHIVED,
        ):
            if not self.sealed_segment_ids:
                raise InconsistentStateError(
                    "published/archived checkpoint requires sealed_segment_ids"
                )
            if not self.checksum:
                raise InconsistentStateError(
                    "published/archived checkpoint requires checksum"
                )
        if self.state is WALCheckpointState.ARCHIVED and not self.archive_receipt_id:
            raise InconsistentStateError(
                "archived checkpoint requires archive_receipt_id"
            )
        if (
            self.previous_checkpoint_id
            and self.previous_checkpoint_id == self.checkpoint_id
        ):
            raise CycleDetectedError("checkpoint cannot reference itself")
        _bounded_record(self, "wal checkpoint")

    def covers_sequence(self, sequence_number: int) -> bool:
        return 0 <= sequence_number <= self.through_sequence

    def _payload(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "generation_id": self.generation_id,
            "through_sequence": self.through_sequence,
            "state": self.state.value,
            "sealed_segment_ids": list(self.sealed_segment_ids),
            "checksum": self.checksum,
            "archive_receipt_id": self.archive_receipt_id,
            "previous_checkpoint_id": self.previous_checkpoint_id,
            "created_at_unix_ms": self.created_at_unix_ms,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WALCheckpoint":
        fields = (
            "checkpoint_id",
            "generation_id",
            "through_sequence",
            "state",
            "sealed_segment_ids",
            "checksum",
            "archive_receipt_id",
            "previous_checkpoint_id",
            "created_at_unix_ms",
            "notes",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "wal checkpoint")
        value = cls(
            checkpoint_id=raw["checkpoint_id"] or "",
            generation_id=raw["generation_id"] or "",
            through_sequence=int(raw["through_sequence"] or 0),
            state=(
                raw["state"]
                if raw["state"] is not None
                else WALCheckpointState.PENDING
            ),
            sealed_segment_ids=tuple(raw.get("sealed_segment_ids") or ()),
            checksum=raw.get("checksum") or "",
            archive_receipt_id=raw.get("archive_receipt_id") or "",
            previous_checkpoint_id=raw.get("previous_checkpoint_id") or "",
            created_at_unix_ms=int(raw.get("created_at_unix_ms") or 0),
            notes=raw.get("notes") or "",
        )
        _verify_identity(payload, value)
        return value


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_buffered_record(
    *,
    generation_id: str,
    sequence_number: int,
    kind: WALRecordKind = WALRecordKind.MUTATE,
    transaction_id: str = "",
    **kwargs: Any,
) -> WALRecord:
    """Build a non-durable buffered record (never committed)."""

    return WALRecord(
        generation_id=generation_id,
        sequence_number=sequence_number,
        kind=kind,
        state=WALRecordState.BUFFERED,
        acknowledgement_mode=WALAcknowledgementMode.BUFFERED,
        transaction_id=transaction_id,
        **kwargs,
    )


def make_committed_record(
    *,
    generation_id: str,
    sequence_number: int,
    kind: WALRecordKind = WALRecordKind.COMMIT,
    transaction_id: str,
    acknowledgement_mode: WALAcknowledgementMode = (
        WALAcknowledgementMode.WAL_FSYNC_PARENT
    ),
    fsync_receipt_id: str,
    backend_effect_id: str = "",
    **kwargs: Any,
) -> WALRecord:
    """Build a committed record under a durability-capable ack mode."""

    return WALRecord(
        generation_id=generation_id,
        sequence_number=sequence_number,
        kind=kind,
        state=WALRecordState.COMMITTED,
        acknowledgement_mode=acknowledgement_mode,
        transaction_id=transaction_id,
        fsync_receipt_id=fsync_receipt_id,
        backend_effect_id=backend_effect_id,
        **kwargs,
    )


def checksum_for_preimage(preimage: Mapping[str, Any] | str | bytes) -> str:
    """Return a sha256: hex checksum for a bounded preimage (not a body store)."""

    if isinstance(preimage, bytes):
        data = preimage
    elif isinstance(preimage, str):
        data = preimage.encode("utf-8")
    else:
        data = canonical_json_bytes(preimage)
    return "sha256:" + hashlib.sha256(data).hexdigest()


__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "WALRecord_V1",
    "WALTransaction_V1",
    "WALSegment_V1",
    "WALCheckpoint_V1",
    "WAL_RECORD_SCHEMA",
    "WAL_TRANSACTION_SCHEMA",
    "WAL_SEGMENT_SCHEMA",
    "WAL_CHECKPOINT_SCHEMA",
    "MAX_RECORD_BYTES",
    "DURABLE_STATES",
    "COMMITTED_STATES",
    "BUFFERED_OR_QUEUED_STATES",
    "PRE_COMMIT_MEDIA_STATES",
    "TERMINAL_FAILURE_STATES",
    "TERMINAL_SUCCESS_STATES",
    "WALRecordKind",
    "WALRecordState",
    "WALTransactionState",
    "WALSegmentState",
    "WALCheckpointState",
    "WALAcknowledgementMode",
    "WALCorruptionDisposition",
    "WALContractError",
    "WALContractBoundsError",
    "WALSequenceError",
    "WALUnsafeEncodingError",
    "WALAcknowledgementError",
    "WALAckRequirements",
    "WALRecordIdentity",
    "WALFsyncReceipt",
    "WALRecord",
    "WALTransaction",
    "WALSegment",
    "WALCheckpoint",
    "ack_requirements_for",
    "all_ack_requirements",
    "is_legal_record_transition",
    "assert_legal_record_transition",
    "is_legal_transaction_transition",
    "assert_legal_transaction_transition",
    "is_legal_segment_transition",
    "assert_legal_segment_transition",
    "is_legal_checkpoint_transition",
    "assert_legal_checkpoint_transition",
    "assert_sequence_monotonic",
    "assert_sequence_chain",
    "assert_ack_allows_state",
    "make_buffered_record",
    "make_committed_record",
    "checksum_for_preimage",
    "content_identity",
    "canonical_json_bytes",
    "PayloadReference",
    "PayloadKind",
    "SecretMaterialError",
    "BodyRejectedError",
    "ForgedIdentityError",
    "InconsistentStateError",
    "CycleDetectedError",
]
