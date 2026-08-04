"""Canonical operation, result, error, state, and evidence contracts (KITA-002).

This module is an inert, closed, versioned contract surface shared by all later
runtime-readiness tasks.  It defines finite, content-addressed records for:

* operation requests and identity bindings;
* acknowledgement / lifecycle states (accepted → committed → verified →
  converged, plus every failure and partial-effect disposition);
* storage errors with retryability and taxonomy projections;
* state-transition receipts; and
* bounded effect / durability evidence references.

Rules (fail-closed):

* identities are derived from canonical JSON and cannot be forged;
* secrets, source bodies, cycles, non-finite values, and unbounded fields
  are rejected at construction;
* type, resource, and memory facets remain distinct and never promote across
  kinds;
* success states that imply durability, integrity, or convergence require the
  matching evidence; and
* adapters may only project these records to exit codes / JSON-RPC / MCP —
  they cannot translate semantic failure into success.

No optional storage providers or live subsystems are imported here.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Final, TypeVar

# ---------------------------------------------------------------------------
# Schema / version / bounds
# ---------------------------------------------------------------------------

CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

OPERATION_CONTRACTS_NAMESPACE: Final[str] = "ipfs_kit_py/core/operation-contracts"

OPERATION_REQUEST_SCHEMA: Final[str] = f"{OPERATION_CONTRACTS_NAMESPACE}/operation-request@{SCHEMA_MAJOR}"
OPERATION_RESULT_SCHEMA: Final[str] = f"{OPERATION_CONTRACTS_NAMESPACE}/operation-result@{SCHEMA_MAJOR}"
STORAGE_ERROR_SCHEMA: Final[str] = f"{OPERATION_CONTRACTS_NAMESPACE}/storage-error@{SCHEMA_MAJOR}"
STATE_TRANSITION_RECEIPT_SCHEMA: Final[str] = (
    f"{OPERATION_CONTRACTS_NAMESPACE}/state-transition-receipt@{SCHEMA_MAJOR}"
)
IDENTITY_BINDINGS_SCHEMA: Final[str] = (
    f"{OPERATION_CONTRACTS_NAMESPACE}/identity-bindings@{SCHEMA_MAJOR}"
)
PARTIAL_EFFECT_SCHEMA: Final[str] = f"{OPERATION_CONTRACTS_NAMESPACE}/partial-effect@{SCHEMA_MAJOR}"
EFFECT_EVIDENCE_SCHEMA: Final[str] = f"{OPERATION_CONTRACTS_NAMESPACE}/effect-evidence@{SCHEMA_MAJOR}"
DURABILITY_EVIDENCE_SCHEMA: Final[str] = (
    f"{OPERATION_CONTRACTS_NAMESPACE}/durability-evidence@{SCHEMA_MAJOR}"
)
PAYLOAD_REFERENCE_SCHEMA: Final[str] = (
    f"{OPERATION_CONTRACTS_NAMESPACE}/payload-reference@{SCHEMA_MAJOR}"
)
FACET_REF_SCHEMA: Final[str] = f"{OPERATION_CONTRACTS_NAMESPACE}/facet-ref@{SCHEMA_MAJOR}"
TIMING_BOUNDS_SCHEMA: Final[str] = f"{OPERATION_CONTRACTS_NAMESPACE}/timing-bounds@{SCHEMA_MAJOR}"

# Public interface aliases (plan: OperationRequest@1, …).
OperationRequest_V1: Final[str] = OPERATION_REQUEST_SCHEMA
OperationResult_V1: Final[str] = OPERATION_RESULT_SCHEMA
StorageError_V1: Final[str] = STORAGE_ERROR_SCHEMA
StateTransitionReceipt_V1: Final[str] = STATE_TRANSITION_RECEIPT_SCHEMA

MAX_RECORD_BYTES: Final[int] = 262_144
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_IDENTIFIER_BYTES: Final[int] = 512
MAX_PATH_BYTES: Final[int] = 1_024
MAX_REFERENCE_COUNT: Final[int] = 256
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
MAX_TIMING_MS: Final[int] = 7 * 24 * 60 * 60 * 1000  # one week
MAX_PAYLOAD_BYTES_BOUND: Final[int] = 1 << 40  # declared bound, not a body

_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$"
)
_CID_LIKE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(b[a-z2-7]{20,}|Qm[1-9A-HJ-NP-Za-km-z]{44}|baguqeer[a-z0-9]{50,}|sha256:[0-9a-f]{64})$"
)

TEnum = TypeVar("TEnum", bound=Enum)


# ---------------------------------------------------------------------------
# Closed vocabularies — acknowledgement / lifecycle states
# ---------------------------------------------------------------------------


class OperationState(str, Enum):
    """Closed lifecycle / acknowledgement states for storage operations.

    Durability ladder (non-failure):

    * ``accepted`` — admitted; not durable.
    * ``queued`` — scheduled; not durable / not executed.
    * ``pending`` / ``processing`` — in flight; not durable.
    * ``committed`` — survives the declared WAL/backend crash model.
    * ``verified`` — integrity / version verification complete.
    * ``converged`` — replica / cache / index projections match committed state.

    Failure and partial-effect dispositions are first-class and never silently
    upgraded to success.
    """

    ACCEPTED = "accepted"
    QUEUED = "queued"
    PENDING = "pending"
    PROCESSING = "processing"
    COMMITTED = "committed"
    VERIFIED = "verified"
    CONVERGED = "converged"
    PARTIAL_EFFECT = "partial_effect"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ABORTED = "aborted"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    CONFLICT = "conflict"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    BACKPRESSURE = "backpressure"
    COMPENSATING = "compensating"
    ROLLED_BACK = "rolled_back"
    PRECONDITION_FAILED = "precondition_failed"
    AUTHORIZATION_DENIED = "authorization_denied"


# States that may appear on a successful OperationResult (no error required).
SUCCESS_STATES: Final[frozenset[OperationState]] = frozenset(
    {
        OperationState.ACCEPTED,
        OperationState.QUEUED,
        OperationState.PENDING,
        OperationState.PROCESSING,
        OperationState.COMMITTED,
        OperationState.VERIFIED,
        OperationState.CONVERGED,
    }
)

# States that require a StorageError (or explicit partial-effect + error).
FAILURE_STATES: Final[frozenset[OperationState]] = frozenset(
    {
        OperationState.FAILED,
        OperationState.REJECTED,
        OperationState.CANCELLED,
        OperationState.TIMED_OUT,
        OperationState.ABORTED,
        OperationState.UNSUPPORTED,
        OperationState.UNAVAILABLE,
        OperationState.CONFLICT,
        OperationState.DEADLINE_EXCEEDED,
        OperationState.BACKPRESSURE,
        OperationState.PRECONDITION_FAILED,
        OperationState.AUTHORIZATION_DENIED,
        OperationState.ROLLED_BACK,
    }
)

# Intermediate states that may carry partial effects without full success.
PARTIAL_STATES: Final[frozenset[OperationState]] = frozenset(
    {
        OperationState.PARTIAL_EFFECT,
        OperationState.COMPENSATING,
    }
)

# States that claim durability past mere acceptance.
DURABLE_STATES: Final[frozenset[OperationState]] = frozenset(
    {
        OperationState.COMMITTED,
        OperationState.VERIFIED,
        OperationState.CONVERGED,
    }
)

# States that claim integrity verification.
VERIFIED_STATES: Final[frozenset[OperationState]] = frozenset(
    {
        OperationState.VERIFIED,
        OperationState.CONVERGED,
    }
)

# States that claim cross-component convergence.
CONVERGED_STATES: Final[frozenset[OperationState]] = frozenset(
    {
        OperationState.CONVERGED,
    }
)

# Legal directed transitions (from → frozenset of allowed next).
_LEGAL_TRANSITIONS: Final[Mapping[OperationState, frozenset[OperationState]]] = {
    OperationState.ACCEPTED: frozenset(
        {
            OperationState.QUEUED,
            OperationState.PENDING,
            OperationState.PROCESSING,
            OperationState.COMMITTED,
            OperationState.PARTIAL_EFFECT,
            OperationState.FAILED,
            OperationState.REJECTED,
            OperationState.CANCELLED,
            OperationState.TIMED_OUT,
            OperationState.ABORTED,
            OperationState.UNSUPPORTED,
            OperationState.UNAVAILABLE,
            OperationState.CONFLICT,
            OperationState.DEADLINE_EXCEEDED,
            OperationState.BACKPRESSURE,
            OperationState.PRECONDITION_FAILED,
            OperationState.AUTHORIZATION_DENIED,
            OperationState.ROLLED_BACK,
        }
    ),
    OperationState.QUEUED: frozenset(
        {
            OperationState.PENDING,
            OperationState.PROCESSING,
            OperationState.CANCELLED,
            OperationState.TIMED_OUT,
            OperationState.DEADLINE_EXCEEDED,
            OperationState.BACKPRESSURE,
            OperationState.FAILED,
            OperationState.REJECTED,
            OperationState.UNAVAILABLE,
            OperationState.UNSUPPORTED,
            OperationState.ABORTED,
        }
    ),
    OperationState.PENDING: frozenset(
        {
            OperationState.PROCESSING,
            OperationState.COMMITTED,
            OperationState.PARTIAL_EFFECT,
            OperationState.FAILED,
            OperationState.CANCELLED,
            OperationState.TIMED_OUT,
            OperationState.DEADLINE_EXCEEDED,
            OperationState.ABORTED,
            OperationState.CONFLICT,
            OperationState.UNAVAILABLE,
            OperationState.BACKPRESSURE,
            OperationState.PRECONDITION_FAILED,
            OperationState.AUTHORIZATION_DENIED,
            OperationState.ROLLED_BACK,
        }
    ),
    OperationState.PROCESSING: frozenset(
        {
            OperationState.COMMITTED,
            OperationState.PARTIAL_EFFECT,
            OperationState.COMPENSATING,
            OperationState.FAILED,
            OperationState.CANCELLED,
            OperationState.TIMED_OUT,
            OperationState.DEADLINE_EXCEEDED,
            OperationState.ABORTED,
            OperationState.CONFLICT,
            OperationState.UNAVAILABLE,
            OperationState.PRECONDITION_FAILED,
            OperationState.ROLLED_BACK,
        }
    ),
    OperationState.COMMITTED: frozenset(
        {
            OperationState.VERIFIED,
            OperationState.CONVERGED,
            OperationState.PARTIAL_EFFECT,  # post-commit projection lag/failure
            OperationState.COMPENSATING,
            OperationState.FAILED,  # verification failure after commit
        }
    ),
    OperationState.VERIFIED: frozenset(
        {
            OperationState.CONVERGED,
            OperationState.PARTIAL_EFFECT,
            OperationState.FAILED,
        }
    ),
    OperationState.CONVERGED: frozenset(),  # terminal success
    OperationState.PARTIAL_EFFECT: frozenset(
        {
            OperationState.COMPENSATING,
            OperationState.COMMITTED,
            OperationState.FAILED,
            OperationState.ROLLED_BACK,
            OperationState.ABORTED,
            OperationState.CANCELLED,
        }
    ),
    OperationState.COMPENSATING: frozenset(
        {
            OperationState.ROLLED_BACK,
            OperationState.FAILED,
            OperationState.COMMITTED,
            OperationState.ABORTED,
        }
    ),
    OperationState.FAILED: frozenset(),
    OperationState.REJECTED: frozenset(),
    OperationState.CANCELLED: frozenset(),
    OperationState.TIMED_OUT: frozenset(),
    OperationState.ABORTED: frozenset(),
    OperationState.UNSUPPORTED: frozenset(),
    OperationState.UNAVAILABLE: frozenset(),
    OperationState.CONFLICT: frozenset(),
    OperationState.DEADLINE_EXCEEDED: frozenset(),
    OperationState.BACKPRESSURE: frozenset(),
    OperationState.PRECONDITION_FAILED: frozenset(),
    OperationState.AUTHORIZATION_DENIED: frozenset(),
    OperationState.ROLLED_BACK: frozenset(),
}


def is_legal_transition(from_state: OperationState, to_state: OperationState) -> bool:
    """Return whether ``from_state → to_state`` is an admitted transition."""

    if from_state is to_state:
        return True
    allowed = _LEGAL_TRANSITIONS.get(from_state, frozenset())
    return to_state in allowed


class ConsistencyRequirement(str, Enum):
    """Requested consistency / isolation semantics for an operation."""

    EVENTUAL = "eventual"
    READ_YOUR_WRITES = "read_your_writes"
    BOUNDED_STALENESS = "bounded_staleness"
    STRONG = "strong"
    LINEARIZABLE = "linearizable"
    SNAPSHOT = "snapshot"
    CAUSAL = "causal"


class DurabilityMode(str, Enum):
    """Declared durability / acknowledgement mode.

    ``ACCEPTED_ONLY`` and ``QUEUED`` must never be reported as committed.
    """

    ACCEPTED_ONLY = "accepted_only"
    QUEUED = "queued"
    WAL_APPENDED = "wal_appended"
    WAL_FSYNC = "wal_fsync"
    BACKEND_DURABLE = "backend_durable"
    REPLICATED = "replicated"
    GROUP_COMMIT = "group_commit"


class Retryability(str, Enum):
    """Whether a failed operation may safely be retried."""

    NEVER = "never"
    IDEMPOTENT_SAFE = "idempotent_safe"
    AFTER_RECONCILE = "after_reconcile"
    CALLER_DECIDES = "caller_decides"
    UNKNOWN = "unknown"


class FallbackPolicy(str, Enum):
    """Explicit backend fallback disposition (no silent substitution)."""

    NONE = "none"
    REQUIRE_EXACT = "require_exact"
    ALLOW_DECLARED_ALTERNATES = "allow_declared_alternates"
    REJECT_IF_UNAVAILABLE = "reject_if_unavailable"


class ErrorCategory(str, Enum):
    """Closed error taxonomy; transport projections map onto these codes."""

    VALIDATION = "validation"
    AUTHORIZATION = "authorization"
    AUTHENTICATION = "authentication"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PRECONDITION = "precondition"
    TIMEOUT = "timeout"
    CANCELLATION = "cancellation"
    BACKPRESSURE = "backpressure"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    CAPABILITY = "capability"
    STORAGE = "storage"
    DURABILITY = "durability"
    INTEGRITY = "integrity"
    REPLICATION = "replication"
    NETWORK = "network"
    INTERNAL = "internal"
    PARTIAL_EFFECT = "partial_effect"
    UNKNOWN = "unknown"


class ErrorCode(str, Enum):
    """Stable, transport-independent error codes."""

    INVALID_REQUEST = "E_INVALID_REQUEST"
    FORGED_IDENTITY = "E_FORGED_IDENTITY"
    SECRET_MATERIAL = "E_SECRET_MATERIAL"
    BODY_REJECTED = "E_BODY_REJECTED"
    UNBOUNDED_FIELD = "E_UNBOUNDED_FIELD"
    NON_FINITE = "E_NON_FINITE"
    CYCLE_DETECTED = "E_CYCLE_DETECTED"
    INCONSISTENT_STATE = "E_INCONSISTENT_STATE"
    MISSING_EVIDENCE = "E_MISSING_EVIDENCE"
    UNAUTHORIZED = "E_UNAUTHORIZED"
    FORBIDDEN = "E_FORBIDDEN"
    NOT_FOUND = "E_NOT_FOUND"
    ALREADY_EXISTS = "E_ALREADY_EXISTS"
    CONFLICT = "E_CONFLICT"
    PRECONDITION_FAILED = "E_PRECONDITION_FAILED"
    DEADLINE_EXCEEDED = "E_DEADLINE_EXCEEDED"
    CANCELLED = "E_CANCELLED"
    BACKPRESSURE = "E_BACKPRESSURE"
    UNAVAILABLE = "E_UNAVAILABLE"
    UNSUPPORTED = "E_UNSUPPORTED"
    CAPABILITY_MISSING = "E_CAPABILITY_MISSING"
    STORAGE_FAILURE = "E_STORAGE_FAILURE"
    DURABILITY_FAILURE = "E_DURABILITY_FAILURE"
    INTEGRITY_FAILURE = "E_INTEGRITY_FAILURE"
    REPLICATION_FAILURE = "E_REPLICATION_FAILURE"
    PARTIAL_EFFECT = "E_PARTIAL_EFFECT"
    INTERNAL = "E_INTERNAL"
    UNKNOWN = "E_UNKNOWN"


class EffectKind(str, Enum):
    """Kinds of external or durable effects an operation may produce."""

    NONE = "none"
    WAL_APPEND = "wal_append"
    WAL_COMMIT = "wal_commit"
    BACKEND_WRITE = "backend_write"
    BACKEND_DELETE = "backend_delete"
    BACKEND_RENAME = "backend_rename"
    CACHE_ADMIT = "cache_admit"
    CACHE_INVALIDATE = "cache_invalidate"
    INDEX_UPDATE = "index_update"
    INDEX_PUBLISH = "index_publish"
    REPLICA_COPY = "replica_copy"
    REPLICA_REMOVE = "replica_remove"
    CATALOG_MUTATE = "catalog_mutate"
    METADATA_MUTATE = "metadata_mutate"
    EXTERNAL_NOTIFY = "external_notify"
    UNKNOWN = "unknown"


class EvidenceKind(str, Enum):
    """Kinds of effect / durability evidence references (never raw bodies)."""

    WAL_RECORD = "wal_record"
    WAL_FSYNC = "wal_fsync"
    BACKEND_ACK = "backend_ack"
    CONTENT_CID = "content_cid"
    VERSION_CID = "version_cid"
    INTEGRITY_PROOF = "integrity_proof"
    REPLICA_RECEIPT = "replica_receipt"
    CACHE_GENERATION = "cache_generation"
    INDEX_GENERATION = "index_generation"
    CATALOG_GENERATION = "catalog_generation"
    TRANSACTION_COMMIT = "transaction_commit"
    COMPENSATION = "compensation"
    TRACE = "trace"


class FacetKind(str, Enum):
    """Closed facet kinds; type, resource, and memory remain distinct."""

    TYPE = "type"
    RESOURCE = "resource"
    MEMORY = "memory"
    EFFECT = "effect"
    AUTHORIZATION = "authorization"
    STATE = "state"
    SCHEMA = "schema"
    TEMPORAL = "temporal"
    CONSISTENCY = "consistency"
    DURABILITY = "durability"


class PayloadKind(str, Enum):
    """How a payload is referenced (never inlined unbounded bodies)."""

    CONTENT_CID = "content_cid"
    STREAM_DESCRIPTOR = "stream_descriptor"
    BYTE_RANGE = "byte_range"
    EMPTY = "empty"
    INLINE_BOUNDED = "inline_bounded"  # only when size ≤ MAX_TEXT_BYTES


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OperationContractError(ValueError):
    """Base class for operation-contract schema failures."""


class OperationContractBoundsError(OperationContractError):
    """A record exceeded its declared compactness bounds."""


class ForgedIdentityError(OperationContractError):
    """A stored content identity did not match the canonical preimage."""


class InconsistentStateError(OperationContractError):
    """State, success flag, evidence, or transition invariants disagree."""


class SecretMaterialError(OperationContractError):
    """Secret or credential material was present in a public record."""


class BodyRejectedError(OperationContractError):
    """An unbounded source body or payload was smuggled into a record."""


class CycleDetectedError(OperationContractError):
    """A reference graph contained a cycle."""


# ---------------------------------------------------------------------------
# Secret / body / canonical value guards
# ---------------------------------------------------------------------------

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
        # Bare "token" is too broad (matches cancellation_token_id); use
        # exact/compound forms only.
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
        # Bare "code"/"source" are legitimate schema field names (ErrorCode,
        # source_path); only compound body keys are rejected.
        "raw_code",
        "raw_ast",
        "ast_body",
        "payload_bytes",
        "raw_payload",
        "request_body",
        "response_body",
        "proof_script",
        "prompt_body",
    }
)


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def _key_looks_secret(key: str) -> bool:
    """Return True for secret-bearing field names (exact / compound only)."""

    if key in _SECRET_KEY_MARKERS:
        return True
    # Compound forms: foo_password, api_key_value, private_key_pem, …
    for marker in _SECRET_KEY_MARKERS:
        if key.endswith("_" + marker) or key.startswith(marker + "_"):
            return True
        # Multi-segment containment only for multi-word markers (≥ 2 parts).
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
    """Recursively reject secret keys/values and body-like fields."""

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


def _canonical_value(value: Any, *, _seen: set[int] | None = None) -> Any:
    """Return a DAG-JSON-compatible value or fail closed.

    Rejects floats/NaN/Inf, host objects, and reference cycles.
    """

    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if value < -MAX_SAFE_INTEGER or value > MAX_SAFE_INTEGER:
            raise OperationContractBoundsError(
                "integer outside the safe finite bound"
            )
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise OperationContractError("non-finite floating values are rejected")
        raise OperationContractError(
            "canonical operation contracts cannot contain floats; "
            "use explicit integer units"
        )
    if isinstance(value, Enum):
        return _canonical_value(value.value, _seen=_seen)
    if isinstance(value, CanonicalContract):
        return value.to_dict()
    if isinstance(value, Mapping):
        obj_id = id(value)
        if _seen is None:
            _seen = set()
        if obj_id in _seen:
            raise CycleDetectedError("cycle detected in mapping structure")
        _seen.add(obj_id)
        try:
            if not all(isinstance(k, str) for k in value):
                raise OperationContractError("object keys must be strings")
            result: dict[str, Any] = {}
            for raw_key in sorted(value):
                result[raw_key] = _canonical_value(value[raw_key], _seen=_seen)
            return result
        finally:
            _seen.discard(obj_id)
    if isinstance(value, (list, tuple)):
        obj_id = id(value)
        if _seen is None:
            _seen = set()
        if obj_id in _seen:
            raise CycleDetectedError("cycle detected in sequence structure")
        _seen.add(obj_id)
        try:
            return [_canonical_value(item, _seen=_seen) for item in value]
        finally:
            _seen.discard(obj_id)
    if isinstance(value, (set, frozenset)):
        items = [_canonical_value(item, _seen=_seen) for item in value]
        return sorted(items, key=lambda item: canonical_json_bytes(item))
    raise OperationContractError(
        f"unsupported canonical value type: {type(value).__name__}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Encode deterministic DAG-JSON-compatible UTF-8 bytes."""

    normalized = _canonical_value(value)
    _contains_secret_or_body(normalized)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_json(value: Any) -> str:
    """Encode canonical JSON text."""

    return canonical_json_bytes(value).decode("utf-8")


def content_identity(value: Any) -> str:
    """Return a CIDv1-style dag-json/sha2-256 identity for ``value``."""

    digest = hashlib.sha256(canonical_json_bytes(value)).digest()
    # CIDv1 + dag-json (0x0129 as two-byte varint 0xa9 0x02) + sha2-256 multihash.
    raw = b"\x01\xa9\x02\x12\x20" + digest
    return "b" + base64.b32encode(raw).decode("ascii").rstrip("=").lower()


# ---------------------------------------------------------------------------
# Field codecs
# ---------------------------------------------------------------------------


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
        raise OperationContractError(f"{field_name} must be a string")
    else:
        normalized = value.strip()
    if required and not normalized:
        raise OperationContractError(f"{field_name} is required")
    if not allow_empty and not normalized:
        raise OperationContractError(f"{field_name} must not be empty")
    if len(normalized.encode("utf-8")) > limit:
        raise OperationContractBoundsError(f"{field_name} exceeds its byte bound")
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
        raise OperationContractError(
            f"{field_name} must be an opaque compact identifier"
        )
    if not _ID_RE.match(text):
        raise OperationContractError(
            f"{field_name} has an invalid identifier shape"
        )
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
        raise OperationContractError(f"{field_name} must be a finite integer")
    if value < minimum or value > maximum:
        raise OperationContractBoundsError(
            f"{field_name} is outside the supported bound"
        )
    return value


def _bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise OperationContractError(f"{field_name} must be a boolean")
    return value


def _enum(value: Any, enum: type[TEnum], field_name: str) -> TEnum:
    try:
        if isinstance(value, enum):
            return value
        return enum(value)  # type: ignore[call-arg]
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum)
        raise OperationContractError(
            f"{field_name} must be one of: {allowed}"
        ) from exc


def _ids(
    values: Any,
    field_name: str,
    *,
    required: bool = False,
    limit: int = MAX_REFERENCE_COUNT,
    preserve_order: bool = True,
) -> tuple[str, ...]:
    if values is None:
        items: Sequence[Any] = ()
    elif isinstance(values, str):
        items = (values,)
    elif isinstance(values, Sequence) and not isinstance(values, (bytes, bytearray)):
        items = values
    else:
        raise OperationContractError(f"{field_name} must be a sequence of identifiers")
    if len(items) > limit:
        raise OperationContractBoundsError(f"{field_name} exceeds reference count bound")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _identifier(item, field_name)
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    if required and not normalized:
        raise OperationContractError(f"{field_name} must not be empty")
    if not preserve_order:
        normalized = sorted(normalized)
    return tuple(normalized)


def _optional_cid(value: Any, field_name: str) -> str:
    text = _text(value, field_name, required=False, limit=MAX_IDENTIFIER_BYTES)
    if not text:
        return ""
    if not _CID_LIKE_RE.match(text) and not text.startswith(
        ("cid:", "baguqeer", "bafy", "bafk", "Qm", "sha256:")
    ):
        # Allow compact namespaced refs used by internal bindings.
        if not _ID_RE.match(text):
            raise OperationContractError(f"{field_name} is not a valid content identity")
    return text


def _reject_unknown_fields(
    payload: Mapping[str, Any],
    allowed: Iterable[str],
    *,
    artifact_name: str,
) -> None:
    if set(payload).difference(set(allowed) | {"schema", "content_id", "contract_version"}):
        raise OperationContractError(
            f"{artifact_name} contains unsupported fields; rebuild its canonical payload"
        )


def _schema(payload: Mapping[str, Any], expected: str) -> None:
    if not isinstance(payload, Mapping):
        raise OperationContractError("contract payload must be an object")
    supplied = payload.get("schema")
    if supplied not in (None, "", expected):
        raise OperationContractError(f"unsupported contract schema; use {expected}")


def _contract_version(payload: Mapping[str, Any]) -> None:
    supplied = payload.get("contract_version")
    if supplied not in (None, CONTRACT_VERSION):
        raise OperationContractError(
            "unsupported operation contract version; rebuild with the current contract"
        )


def _bounded_record(record: "CanonicalContract", name: str) -> None:
    size = len(record.canonical_bytes())
    if size > MAX_RECORD_BYTES:
        raise OperationContractBoundsError(
            f"{name} exceeds MAX_RECORD_BYTES ({size} > {MAX_RECORD_BYTES})"
        )


def _verify_identity(payload: Mapping[str, Any], record: "CanonicalContract") -> None:
    supplied = payload.get("content_id")
    if supplied is None:
        return
    if not isinstance(supplied, str) or not supplied:
        raise ForgedIdentityError("content_id must be a non-empty string when present")
    expected = record.content_id
    if supplied != expected:
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
        raise OperationContractError(f"{artifact_name} payload must be an object")
    _schema(payload, schema)
    _contract_version(payload)
    _reject_unknown_fields(payload, fields, artifact_name=artifact_name)
    _contains_secret_or_body(payload, path=artifact_name)
    return {name: payload.get(name) for name in fields if name in payload or True}


# ---------------------------------------------------------------------------
# CanonicalContract base
# ---------------------------------------------------------------------------


class CanonicalContract:
    """Immutable, content-addressed contract mixin."""

    SCHEMA: ClassVar[str] = ""

    def _payload(self) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def schema(self) -> str:
        return self.SCHEMA

    @property
    def schema_version(self) -> str:
        return SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _canonical_value(
            {
                "schema": self.SCHEMA,
                "contract_version": CONTRACT_VERSION,
                **self._payload(),
            }
        )

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def canonical_json(self) -> str:
        return self.to_json()

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @property
    def content_id(self) -> str:
        return content_identity(self.to_dict())

    @property
    def cid(self) -> str:
        return self.content_id

    @property
    def identity(self) -> str:
        return self.content_id

    def to_record(self) -> dict[str, Any]:
        return {**self.to_dict(), "content_id": self.content_id}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CanonicalContract):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __hash__(self) -> int:
        return hash(self.content_id)


# ---------------------------------------------------------------------------
# Facet references (type / resource / memory remain distinct)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FacetRef(CanonicalContract):
    """Typed facet pointer; type/resource/memory never promote across kinds."""

    SCHEMA: ClassVar[str] = FACET_REF_SCHEMA

    facet_id: str
    kind: FacetKind
    subject_id: str
    contract_ref: str = ""
    unsupported: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "facet_id", _identifier(self.facet_id, "facet_id"))
        object.__setattr__(self, "kind", _enum(self.kind, FacetKind, "kind"))
        object.__setattr__(self, "subject_id", _identifier(self.subject_id, "subject_id"))
        object.__setattr__(
            self, "contract_ref", _text(self.contract_ref, "contract_ref")
        )
        object.__setattr__(self, "unsupported", _bool(self.unsupported, "unsupported"))
        ref = self.contract_ref
        kind = self.kind
        if kind is FacetKind.TYPE and ref.startswith(("memory:", "resource:")):
            raise InconsistentStateError(
                "type facets cannot bind memory or resource contracts"
            )
        if kind is FacetKind.RESOURCE and ref.startswith(("memory:", "type:")):
            raise InconsistentStateError(
                "resource facets cannot bind memory or type contracts"
            )
        if kind is FacetKind.MEMORY and ref.startswith(("resource:", "type:")):
            raise InconsistentStateError(
                "memory facets cannot bind resource or type contracts"
            )
        _bounded_record(self, "facet ref")

    def _payload(self) -> dict[str, Any]:
        return {
            "facet_id": self.facet_id,
            "kind": self.kind.value,
            "subject_id": self.subject_id,
            "contract_ref": self.contract_ref,
            "unsupported": self.unsupported,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FacetRef":
        fields = ("facet_id", "kind", "subject_id", "contract_ref", "unsupported")
        raw = _decode_fields(payload, cls.SCHEMA, fields, "facet ref")
        value = cls(
            facet_id=raw["facet_id"] or "",
            kind=raw["kind"] if raw["kind"] is not None else FacetKind.TYPE,
            subject_id=raw["subject_id"] or "",
            contract_ref=raw.get("contract_ref") or "",
            unsupported=bool(raw.get("unsupported") or False),
        )
        _verify_identity(payload, value)
        return value


# ---------------------------------------------------------------------------
# Timing, payload reference, evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimingBounds(CanonicalContract):
    """Bounded operation timings in integer milliseconds."""

    SCHEMA: ClassVar[str] = TIMING_BOUNDS_SCHEMA

    deadline_unix_ms: int = 0
    timeout_ms: int = 0
    enqueued_at_unix_ms: int = 0
    started_at_unix_ms: int = 0
    finished_at_unix_ms: int = 0
    duration_ms: int = 0

    def __post_init__(self) -> None:
        for name in (
            "deadline_unix_ms",
            "timeout_ms",
            "enqueued_at_unix_ms",
            "started_at_unix_ms",
            "finished_at_unix_ms",
            "duration_ms",
        ):
            object.__setattr__(
                self,
                name,
                _bounded_int(getattr(self, name), name, maximum=MAX_SAFE_INTEGER),
            )
        if self.timeout_ms > MAX_TIMING_MS:
            raise OperationContractBoundsError("timeout_ms exceeds MAX_TIMING_MS")
        if self.duration_ms > MAX_TIMING_MS:
            raise OperationContractBoundsError("duration_ms exceeds MAX_TIMING_MS")
        if (
            self.started_at_unix_ms
            and self.finished_at_unix_ms
            and self.finished_at_unix_ms < self.started_at_unix_ms
        ):
            raise InconsistentStateError(
                "finished_at_unix_ms cannot precede started_at_unix_ms"
            )
        _bounded_record(self, "timing bounds")

    def _payload(self) -> dict[str, Any]:
        return {
            "deadline_unix_ms": self.deadline_unix_ms,
            "timeout_ms": self.timeout_ms,
            "enqueued_at_unix_ms": self.enqueued_at_unix_ms,
            "started_at_unix_ms": self.started_at_unix_ms,
            "finished_at_unix_ms": self.finished_at_unix_ms,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TimingBounds":
        fields = (
            "deadline_unix_ms",
            "timeout_ms",
            "enqueued_at_unix_ms",
            "started_at_unix_ms",
            "finished_at_unix_ms",
            "duration_ms",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "timing bounds")
        value = cls(**{name: int(raw[name] or 0) for name in fields})
        _verify_identity(payload, value)
        return value


@dataclass(frozen=True)
class PayloadReference(CanonicalContract):
    """Bounded payload reference / stream descriptor — never an unbounded body."""

    SCHEMA: ClassVar[str] = PAYLOAD_REFERENCE_SCHEMA

    kind: PayloadKind
    content_cid: str = ""
    stream_id: str = ""
    media_type: str = ""
    size_bytes: int = 0
    offset_bytes: int = 0
    length_bytes: int = 0
    inline_utf8: str = ""  # only for INLINE_BOUNDED, ≤ MAX_TEXT_BYTES

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _enum(self.kind, PayloadKind, "kind"))
        object.__setattr__(
            self, "content_cid", _optional_cid(self.content_cid, "content_cid")
        )
        object.__setattr__(
            self, "stream_id", _optional_identifier(self.stream_id, "stream_id")
        )
        object.__setattr__(
            self,
            "media_type",
            _text(self.media_type, "media_type", limit=256),
        )
        object.__setattr__(
            self,
            "size_bytes",
            _bounded_int(self.size_bytes, "size_bytes", maximum=MAX_PAYLOAD_BYTES_BOUND),
        )
        object.__setattr__(
            self,
            "offset_bytes",
            _bounded_int(
                self.offset_bytes, "offset_bytes", maximum=MAX_PAYLOAD_BYTES_BOUND
            ),
        )
        object.__setattr__(
            self,
            "length_bytes",
            _bounded_int(
                self.length_bytes, "length_bytes", maximum=MAX_PAYLOAD_BYTES_BOUND
            ),
        )
        object.__setattr__(
            self,
            "inline_utf8",
            _text(self.inline_utf8, "inline_utf8", limit=MAX_TEXT_BYTES),
        )
        kind = self.kind
        if kind is PayloadKind.EMPTY:
            if self.content_cid or self.stream_id or self.inline_utf8 or self.size_bytes:
                raise InconsistentStateError("empty payload must not carry content")
        elif kind is PayloadKind.CONTENT_CID:
            if not self.content_cid:
                raise OperationContractError("content_cid payload requires content_cid")
            if self.inline_utf8:
                raise BodyRejectedError("content_cid payload cannot carry inline body")
        elif kind is PayloadKind.STREAM_DESCRIPTOR:
            if not self.stream_id:
                raise OperationContractError("stream descriptor requires stream_id")
            if self.inline_utf8:
                raise BodyRejectedError("stream descriptor cannot carry inline body")
        elif kind is PayloadKind.BYTE_RANGE:
            if not self.content_cid and not self.stream_id:
                raise OperationContractError(
                    "byte_range requires content_cid or stream_id"
                )
            if self.inline_utf8:
                raise BodyRejectedError("byte_range cannot carry inline body")
        elif kind is PayloadKind.INLINE_BOUNDED:
            if not self.inline_utf8 and self.size_bytes != 0:
                raise OperationContractError(
                    "inline_bounded requires inline_utf8 or zero size"
                )
            if len(self.inline_utf8.encode("utf-8")) > MAX_TEXT_BYTES:
                raise OperationContractBoundsError("inline_utf8 exceeds bound")
        _bounded_record(self, "payload reference")

    def _payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "content_cid": self.content_cid,
            "stream_id": self.stream_id,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "offset_bytes": self.offset_bytes,
            "length_bytes": self.length_bytes,
            "inline_utf8": self.inline_utf8,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PayloadReference":
        fields = (
            "kind",
            "content_cid",
            "stream_id",
            "media_type",
            "size_bytes",
            "offset_bytes",
            "length_bytes",
            "inline_utf8",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "payload reference")
        value = cls(
            kind=raw["kind"] if raw["kind"] is not None else PayloadKind.EMPTY,
            content_cid=raw.get("content_cid") or "",
            stream_id=raw.get("stream_id") or "",
            media_type=raw.get("media_type") or "",
            size_bytes=int(raw.get("size_bytes") or 0),
            offset_bytes=int(raw.get("offset_bytes") or 0),
            length_bytes=int(raw.get("length_bytes") or 0),
            inline_utf8=raw.get("inline_utf8") or "",
        )
        _verify_identity(payload, value)
        return value


@dataclass(frozen=True)
class EffectEvidence(CanonicalContract):
    """Bounded reference to an observed effect (never embeds effect bodies)."""

    SCHEMA: ClassVar[str] = EFFECT_EVIDENCE_SCHEMA

    evidence_id: str
    kind: EvidenceKind
    effect_kind: EffectKind
    reference: str
    backend_id: str = ""
    generation_id: str = ""
    observed: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _identifier(self.evidence_id, "evidence_id")
        )
        object.__setattr__(self, "kind", _enum(self.kind, EvidenceKind, "kind"))
        object.__setattr__(
            self, "effect_kind", _enum(self.effect_kind, EffectKind, "effect_kind")
        )
        object.__setattr__(
            self, "reference", _identifier(self.reference, "reference")
        )
        object.__setattr__(
            self, "backend_id", _optional_identifier(self.backend_id, "backend_id")
        )
        object.__setattr__(
            self,
            "generation_id",
            _optional_identifier(self.generation_id, "generation_id"),
        )
        object.__setattr__(self, "observed", _bool(self.observed, "observed"))
        _bounded_record(self, "effect evidence")

    def _payload(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind.value,
            "effect_kind": self.effect_kind.value,
            "reference": self.reference,
            "backend_id": self.backend_id,
            "generation_id": self.generation_id,
            "observed": self.observed,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EffectEvidence":
        fields = (
            "evidence_id",
            "kind",
            "effect_kind",
            "reference",
            "backend_id",
            "generation_id",
            "observed",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "effect evidence")
        value = cls(
            evidence_id=raw["evidence_id"] or "",
            kind=raw["kind"] if raw["kind"] is not None else EvidenceKind.TRACE,
            effect_kind=(
                raw["effect_kind"]
                if raw["effect_kind"] is not None
                else EffectKind.NONE
            ),
            reference=raw["reference"] or "",
            backend_id=raw.get("backend_id") or "",
            generation_id=raw.get("generation_id") or "",
            observed=bool(raw["observed"]) if raw.get("observed") is not None else True,
        )
        _verify_identity(payload, value)
        return value


@dataclass(frozen=True)
class DurabilityEvidence(CanonicalContract):
    """Evidence required before a result may claim committed/verified/converged."""

    SCHEMA: ClassVar[str] = DURABILITY_EVIDENCE_SCHEMA

    mode: DurabilityMode
    wal_record_id: str = ""
    wal_generation_id: str = ""
    fsync_receipt_id: str = ""
    backend_ack_id: str = ""
    transaction_commit_id: str = ""
    integrity_proof_id: str = ""
    replica_receipt_ids: tuple[str, ...] = ()
    cache_generation_id: str = ""
    index_generation_id: str = ""
    effect_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _enum(self.mode, DurabilityMode, "mode"))
        object.__setattr__(
            self,
            "wal_record_id",
            _optional_identifier(self.wal_record_id, "wal_record_id"),
        )
        object.__setattr__(
            self,
            "wal_generation_id",
            _optional_identifier(self.wal_generation_id, "wal_generation_id"),
        )
        object.__setattr__(
            self,
            "fsync_receipt_id",
            _optional_identifier(self.fsync_receipt_id, "fsync_receipt_id"),
        )
        object.__setattr__(
            self,
            "backend_ack_id",
            _optional_identifier(self.backend_ack_id, "backend_ack_id"),
        )
        object.__setattr__(
            self,
            "transaction_commit_id",
            _optional_identifier(self.transaction_commit_id, "transaction_commit_id"),
        )
        object.__setattr__(
            self,
            "integrity_proof_id",
            _optional_identifier(self.integrity_proof_id, "integrity_proof_id"),
        )
        object.__setattr__(
            self,
            "replica_receipt_ids",
            _ids(self.replica_receipt_ids, "replica_receipt_ids"),
        )
        object.__setattr__(
            self,
            "cache_generation_id",
            _optional_identifier(self.cache_generation_id, "cache_generation_id"),
        )
        object.__setattr__(
            self,
            "index_generation_id",
            _optional_identifier(self.index_generation_id, "index_generation_id"),
        )
        object.__setattr__(
            self,
            "effect_evidence_ids",
            _ids(self.effect_evidence_ids, "effect_evidence_ids"),
        )
        _bounded_record(self, "durability evidence")

    def supports_committed(self) -> bool:
        """Whether this evidence is sufficient for a committed acknowledgement."""

        if self.mode in (DurabilityMode.ACCEPTED_ONLY, DurabilityMode.QUEUED):
            return False
        if self.mode is DurabilityMode.WAL_APPENDED:
            return bool(self.wal_record_id)
        if self.mode is DurabilityMode.WAL_FSYNC:
            return bool(self.wal_record_id and self.fsync_receipt_id)
        if self.mode is DurabilityMode.GROUP_COMMIT:
            return bool(self.wal_record_id and self.transaction_commit_id)
        if self.mode is DurabilityMode.BACKEND_DURABLE:
            return bool(self.backend_ack_id or self.transaction_commit_id)
        if self.mode is DurabilityMode.REPLICATED:
            return bool(self.backend_ack_id and self.replica_receipt_ids)
        return False

    def supports_verified(self) -> bool:
        return self.supports_committed() and bool(self.integrity_proof_id)

    def supports_converged(self) -> bool:
        return self.supports_verified() and bool(
            self.replica_receipt_ids
            or self.cache_generation_id
            or self.index_generation_id
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "wal_record_id": self.wal_record_id,
            "wal_generation_id": self.wal_generation_id,
            "fsync_receipt_id": self.fsync_receipt_id,
            "backend_ack_id": self.backend_ack_id,
            "transaction_commit_id": self.transaction_commit_id,
            "integrity_proof_id": self.integrity_proof_id,
            "replica_receipt_ids": list(self.replica_receipt_ids),
            "cache_generation_id": self.cache_generation_id,
            "index_generation_id": self.index_generation_id,
            "effect_evidence_ids": list(self.effect_evidence_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DurabilityEvidence":
        fields = (
            "mode",
            "wal_record_id",
            "wal_generation_id",
            "fsync_receipt_id",
            "backend_ack_id",
            "transaction_commit_id",
            "integrity_proof_id",
            "replica_receipt_ids",
            "cache_generation_id",
            "index_generation_id",
            "effect_evidence_ids",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "durability evidence")
        value = cls(
            mode=raw["mode"] if raw["mode"] is not None else DurabilityMode.ACCEPTED_ONLY,
            wal_record_id=raw.get("wal_record_id") or "",
            wal_generation_id=raw.get("wal_generation_id") or "",
            fsync_receipt_id=raw.get("fsync_receipt_id") or "",
            backend_ack_id=raw.get("backend_ack_id") or "",
            transaction_commit_id=raw.get("transaction_commit_id") or "",
            integrity_proof_id=raw.get("integrity_proof_id") or "",
            replica_receipt_ids=tuple(raw.get("replica_receipt_ids") or ()),
            cache_generation_id=raw.get("cache_generation_id") or "",
            index_generation_id=raw.get("index_generation_id") or "",
            effect_evidence_ids=tuple(raw.get("effect_evidence_ids") or ()),
        )
        _verify_identity(payload, value)
        return value


@dataclass(frozen=True)
class PartialEffectRecord(CanonicalContract):
    """Records a non-atomic or incomplete effect that must not be called success."""

    SCHEMA: ClassVar[str] = PARTIAL_EFFECT_SCHEMA

    partial_id: str
    effect_kind: EffectKind
    state: OperationState
    description: str
    applied_evidence_ids: tuple[str, ...] = ()
    pending_evidence_ids: tuple[str, ...] = ()
    compensation_required: bool = True
    compensation_evidence_id: str = ""
    backend_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "partial_id", _identifier(self.partial_id, "partial_id")
        )
        object.__setattr__(
            self, "effect_kind", _enum(self.effect_kind, EffectKind, "effect_kind")
        )
        object.__setattr__(self, "state", _enum(self.state, OperationState, "state"))
        object.__setattr__(
            self,
            "description",
            _text(self.description, "description", required=True, limit=MAX_TEXT_BYTES),
        )
        object.__setattr__(
            self,
            "applied_evidence_ids",
            _ids(self.applied_evidence_ids, "applied_evidence_ids"),
        )
        object.__setattr__(
            self,
            "pending_evidence_ids",
            _ids(self.pending_evidence_ids, "pending_evidence_ids"),
        )
        object.__setattr__(
            self,
            "compensation_required",
            _bool(self.compensation_required, "compensation_required"),
        )
        object.__setattr__(
            self,
            "compensation_evidence_id",
            _optional_identifier(
                self.compensation_evidence_id, "compensation_evidence_id"
            ),
        )
        object.__setattr__(
            self, "backend_id", _optional_identifier(self.backend_id, "backend_id")
        )
        if self.state not in PARTIAL_STATES | FAILURE_STATES | {
            OperationState.PROCESSING,
            OperationState.PENDING,
        }:
            raise InconsistentStateError(
                "partial effect cannot claim a terminal success state"
            )
        if self.state in DURABLE_STATES:
            raise InconsistentStateError(
                "partial effect cannot claim committed/verified/converged"
            )
        _bounded_record(self, "partial effect")

    def _payload(self) -> dict[str, Any]:
        return {
            "partial_id": self.partial_id,
            "effect_kind": self.effect_kind.value,
            "state": self.state.value,
            "description": self.description,
            "applied_evidence_ids": list(self.applied_evidence_ids),
            "pending_evidence_ids": list(self.pending_evidence_ids),
            "compensation_required": self.compensation_required,
            "compensation_evidence_id": self.compensation_evidence_id,
            "backend_id": self.backend_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PartialEffectRecord":
        fields = (
            "partial_id",
            "effect_kind",
            "state",
            "description",
            "applied_evidence_ids",
            "pending_evidence_ids",
            "compensation_required",
            "compensation_evidence_id",
            "backend_id",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "partial effect")
        value = cls(
            partial_id=raw["partial_id"] or "",
            effect_kind=(
                raw["effect_kind"]
                if raw["effect_kind"] is not None
                else EffectKind.UNKNOWN
            ),
            state=(
                raw["state"]
                if raw["state"] is not None
                else OperationState.PARTIAL_EFFECT
            ),
            description=raw["description"] or "",
            applied_evidence_ids=tuple(raw.get("applied_evidence_ids") or ()),
            pending_evidence_ids=tuple(raw.get("pending_evidence_ids") or ()),
            compensation_required=(
                bool(raw["compensation_required"])
                if raw.get("compensation_required") is not None
                else True
            ),
            compensation_evidence_id=raw.get("compensation_evidence_id") or "",
            backend_id=raw.get("backend_id") or "",
        )
        _verify_identity(payload, value)
        return value


# ---------------------------------------------------------------------------
# Identity bindings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentityBindings(CanonicalContract):
    """Request / principal / policy / backend / WAL / cache / index / replica / env.

    Every field is an opaque compact identifier.  Empty strings mean "not
    applicable for this operation"; they are not wildcards.
    """

    SCHEMA: ClassVar[str] = IDENTITY_BINDINGS_SCHEMA

    request_id: str
    operation_id: str
    idempotency_key: str = ""
    principal_id: str = ""
    tenant_id: str = ""
    policy_id: str = ""
    policy_decision_cid: str = ""
    backend_id: str = ""
    backend_capability_id: str = ""
    wal_generation_id: str = ""
    wal_segment_id: str = ""
    cache_generation_id: str = ""
    index_generation_id: str = ""
    replica_policy_id: str = ""
    environment_id: str = ""
    transaction_id: str = ""
    bucket_id: str = ""
    catalog_generation_id: str = ""
    graphrag_generation_id: str = ""
    trace_id: str = ""
    cancellation_token_id: str = ""
    ucan_resource: str = ""
    ucan_ability: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _identifier(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        for name in (
            "idempotency_key",
            "principal_id",
            "tenant_id",
            "policy_id",
            "backend_id",
            "backend_capability_id",
            "wal_generation_id",
            "wal_segment_id",
            "cache_generation_id",
            "index_generation_id",
            "replica_policy_id",
            "environment_id",
            "transaction_id",
            "bucket_id",
            "catalog_generation_id",
            "graphrag_generation_id",
            "trace_id",
            "cancellation_token_id",
            "ucan_resource",
            "ucan_ability",
        ):
            object.__setattr__(
                self, name, _optional_identifier(getattr(self, name), name)
            )
        object.__setattr__(
            self,
            "policy_decision_cid",
            _optional_cid(self.policy_decision_cid, "policy_decision_cid"),
        )
        _bounded_record(self, "identity bindings")

    def _payload(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "operation_id": self.operation_id,
            "idempotency_key": self.idempotency_key,
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "policy_id": self.policy_id,
            "policy_decision_cid": self.policy_decision_cid,
            "backend_id": self.backend_id,
            "backend_capability_id": self.backend_capability_id,
            "wal_generation_id": self.wal_generation_id,
            "wal_segment_id": self.wal_segment_id,
            "cache_generation_id": self.cache_generation_id,
            "index_generation_id": self.index_generation_id,
            "replica_policy_id": self.replica_policy_id,
            "environment_id": self.environment_id,
            "transaction_id": self.transaction_id,
            "bucket_id": self.bucket_id,
            "catalog_generation_id": self.catalog_generation_id,
            "graphrag_generation_id": self.graphrag_generation_id,
            "trace_id": self.trace_id,
            "cancellation_token_id": self.cancellation_token_id,
            "ucan_resource": self.ucan_resource,
            "ucan_ability": self.ucan_ability,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "IdentityBindings":
        fields = (
            "request_id",
            "operation_id",
            "idempotency_key",
            "principal_id",
            "tenant_id",
            "policy_id",
            "policy_decision_cid",
            "backend_id",
            "backend_capability_id",
            "wal_generation_id",
            "wal_segment_id",
            "cache_generation_id",
            "index_generation_id",
            "replica_policy_id",
            "environment_id",
            "transaction_id",
            "bucket_id",
            "catalog_generation_id",
            "graphrag_generation_id",
            "trace_id",
            "cancellation_token_id",
            "ucan_resource",
            "ucan_ability",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "identity bindings")
        value = cls(**{name: (raw.get(name) or "") for name in fields})
        _verify_identity(payload, value)
        return value


# ---------------------------------------------------------------------------
# StorageError
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StorageError(CanonicalContract):
    """Canonical storage error; exit codes / JSON-RPC / MCP project from this."""

    SCHEMA: ClassVar[str] = STORAGE_ERROR_SCHEMA

    code: ErrorCode
    category: ErrorCategory
    message: str
    retryability: Retryability = Retryability.UNKNOWN
    state: OperationState = OperationState.FAILED
    details_ref: str = ""
    related_request_id: str = ""
    related_operation_id: str = ""
    partial_effect_ids: tuple[str, ...] = ()
    http_status_hint: int = 0
    exit_code_hint: int = 0
    json_rpc_code_hint: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _enum(self.code, ErrorCode, "code"))
        object.__setattr__(
            self, "category", _enum(self.category, ErrorCategory, "category")
        )
        object.__setattr__(
            self,
            "message",
            _text(self.message, "message", required=True, limit=MAX_TEXT_BYTES),
        )
        object.__setattr__(
            self,
            "retryability",
            _enum(self.retryability, Retryability, "retryability"),
        )
        object.__setattr__(self, "state", _enum(self.state, OperationState, "state"))
        object.__setattr__(
            self, "details_ref", _optional_identifier(self.details_ref, "details_ref")
        )
        object.__setattr__(
            self,
            "related_request_id",
            _optional_identifier(self.related_request_id, "related_request_id"),
        )
        object.__setattr__(
            self,
            "related_operation_id",
            _optional_identifier(self.related_operation_id, "related_operation_id"),
        )
        object.__setattr__(
            self,
            "partial_effect_ids",
            _ids(self.partial_effect_ids, "partial_effect_ids"),
        )
        object.__setattr__(
            self,
            "http_status_hint",
            _bounded_int(self.http_status_hint, "http_status_hint", maximum=999),
        )
        object.__setattr__(
            self,
            "exit_code_hint",
            _bounded_int(self.exit_code_hint, "exit_code_hint", maximum=255),
        )
        object.__setattr__(
            self,
            "json_rpc_code_hint",
            _bounded_int(
                self.json_rpc_code_hint,
                "json_rpc_code_hint",
                minimum=-MAX_SAFE_INTEGER,
                maximum=MAX_SAFE_INTEGER,
            ),
        )
        if self.state in SUCCESS_STATES:
            raise InconsistentStateError(
                "StorageError cannot carry a success acknowledgement state"
            )
        if self.state not in FAILURE_STATES | PARTIAL_STATES:
            raise InconsistentStateError(
                f"StorageError state {self.state.value} is not a failure/partial disposition"
            )
        _bounded_record(self, "storage error")

    def _payload(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "category": self.category.value,
            "message": self.message,
            "retryability": self.retryability.value,
            "state": self.state.value,
            "details_ref": self.details_ref,
            "related_request_id": self.related_request_id,
            "related_operation_id": self.related_operation_id,
            "partial_effect_ids": list(self.partial_effect_ids),
            "http_status_hint": self.http_status_hint,
            "exit_code_hint": self.exit_code_hint,
            "json_rpc_code_hint": self.json_rpc_code_hint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StorageError":
        fields = (
            "code",
            "category",
            "message",
            "retryability",
            "state",
            "details_ref",
            "related_request_id",
            "related_operation_id",
            "partial_effect_ids",
            "http_status_hint",
            "exit_code_hint",
            "json_rpc_code_hint",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "storage error")
        value = cls(
            code=raw["code"] if raw["code"] is not None else ErrorCode.UNKNOWN,
            category=(
                raw["category"]
                if raw["category"] is not None
                else ErrorCategory.UNKNOWN
            ),
            message=raw["message"] or "",
            retryability=(
                raw["retryability"]
                if raw["retryability"] is not None
                else Retryability.UNKNOWN
            ),
            state=(
                raw["state"] if raw["state"] is not None else OperationState.FAILED
            ),
            details_ref=raw.get("details_ref") or "",
            related_request_id=raw.get("related_request_id") or "",
            related_operation_id=raw.get("related_operation_id") or "",
            partial_effect_ids=tuple(raw.get("partial_effect_ids") or ()),
            http_status_hint=int(raw.get("http_status_hint") or 0),
            exit_code_hint=int(raw.get("exit_code_hint") or 0),
            json_rpc_code_hint=int(raw.get("json_rpc_code_hint") or 0),
        )
        _verify_identity(payload, value)
        return value

    def as_transport_projection(self) -> dict[str, Any]:
        """Return a transport-only projection (no semantic upgrade)."""

        return {
            "error": True,
            "code": self.code.value,
            "category": self.category.value,
            "message": self.message,
            "retryability": self.retryability.value,
            "state": self.state.value,
            "http_status": self.http_status_hint or None,
            "exit_code": self.exit_code_hint or None,
            "json_rpc_code": self.json_rpc_code_hint or None,
            "content_id": self.content_id,
        }


# ---------------------------------------------------------------------------
# OperationRequest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationRequest(CanonicalContract):
    """Canonical operation request (OperationRequest@1)."""

    SCHEMA: ClassVar[str] = OPERATION_REQUEST_SCHEMA

    identities: IdentityBindings
    operation_name: str
    consistency: ConsistencyRequirement = ConsistencyRequirement.STRONG
    durability: DurabilityMode = DurabilityMode.WAL_FSYNC
    fallback_policy: FallbackPolicy = FallbackPolicy.REJECT_IF_UNAVAILABLE
    path: str = ""
    key: str = ""
    source_path: str = ""
    target_path: str = ""
    precondition_version_cid: str = ""
    precondition_content_cid: str = ""
    payload: PayloadReference | None = None
    backend_requirements: tuple[str, ...] = ()
    alternate_backend_ids: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    facets: tuple[FacetRef, ...] = ()
    timing: TimingBounds | None = None
    metadata_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.identities, IdentityBindings):
            if isinstance(self.identities, Mapping):
                object.__setattr__(
                    self, "identities", IdentityBindings.from_dict(self.identities)
                )
            else:
                raise OperationContractError("identities must be IdentityBindings")
        object.__setattr__(
            self,
            "operation_name",
            _identifier(self.operation_name, "operation_name"),
        )
        object.__setattr__(
            self,
            "consistency",
            _enum(self.consistency, ConsistencyRequirement, "consistency"),
        )
        object.__setattr__(
            self, "durability", _enum(self.durability, DurabilityMode, "durability")
        )
        object.__setattr__(
            self,
            "fallback_policy",
            _enum(self.fallback_policy, FallbackPolicy, "fallback_policy"),
        )
        object.__setattr__(
            self, "path", _text(self.path, "path", limit=MAX_PATH_BYTES)
        )
        object.__setattr__(self, "key", _text(self.key, "key", limit=MAX_PATH_BYTES))
        object.__setattr__(
            self,
            "source_path",
            _text(self.source_path, "source_path", limit=MAX_PATH_BYTES),
        )
        object.__setattr__(
            self,
            "target_path",
            _text(self.target_path, "target_path", limit=MAX_PATH_BYTES),
        )
        object.__setattr__(
            self,
            "precondition_version_cid",
            _optional_cid(self.precondition_version_cid, "precondition_version_cid"),
        )
        object.__setattr__(
            self,
            "precondition_content_cid",
            _optional_cid(self.precondition_content_cid, "precondition_content_cid"),
        )
        payload = self.payload
        if payload is not None and not isinstance(payload, PayloadReference):
            if isinstance(payload, Mapping):
                payload = PayloadReference.from_dict(payload)
            else:
                raise OperationContractError("payload must be PayloadReference or null")
            object.__setattr__(self, "payload", payload)
        timing = self.timing
        if timing is not None and not isinstance(timing, TimingBounds):
            if isinstance(timing, Mapping):
                timing = TimingBounds.from_dict(timing)
            else:
                raise OperationContractError("timing must be TimingBounds or null")
            object.__setattr__(self, "timing", timing)
        object.__setattr__(
            self,
            "backend_requirements",
            _ids(self.backend_requirements, "backend_requirements"),
        )
        object.__setattr__(
            self,
            "alternate_backend_ids",
            _ids(self.alternate_backend_ids, "alternate_backend_ids"),
        )
        object.__setattr__(
            self,
            "required_capabilities",
            _ids(self.required_capabilities, "required_capabilities"),
        )
        facets = _coerce_facet_tuple(self.facets)
        object.__setattr__(self, "facets", facets)
        _assert_facets_distinct(facets)
        object.__setattr__(
            self, "metadata_refs", _ids(self.metadata_refs, "metadata_refs")
        )
        object.__setattr__(
            self, "evidence_refs", _ids(self.evidence_refs, "evidence_refs")
        )
        if (
            self.fallback_policy is FallbackPolicy.NONE
            or self.fallback_policy is FallbackPolicy.REQUIRE_EXACT
            or self.fallback_policy is FallbackPolicy.REJECT_IF_UNAVAILABLE
        ) and self.alternate_backend_ids:
            # Alternates may be declared for allow_declared_alternates only.
            if self.fallback_policy is not FallbackPolicy.ALLOW_DECLARED_ALTERNATES:
                raise InconsistentStateError(
                    "alternate_backend_ids require fallback_policy="
                    "allow_declared_alternates"
                )
        _bounded_record(self, "operation request")

    def _payload(self) -> dict[str, Any]:
        return {
            "identities": self.identities.to_dict(),
            "operation_name": self.operation_name,
            "consistency": self.consistency.value,
            "durability": self.durability.value,
            "fallback_policy": self.fallback_policy.value,
            "path": self.path,
            "key": self.key,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "precondition_version_cid": self.precondition_version_cid,
            "precondition_content_cid": self.precondition_content_cid,
            "payload": None if self.payload is None else self.payload.to_dict(),
            "backend_requirements": list(self.backend_requirements),
            "alternate_backend_ids": list(self.alternate_backend_ids),
            "required_capabilities": list(self.required_capabilities),
            "facets": [facet.to_dict() for facet in self.facets],
            "timing": None if self.timing is None else self.timing.to_dict(),
            "metadata_refs": list(self.metadata_refs),
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OperationRequest":
        fields = (
            "identities",
            "operation_name",
            "consistency",
            "durability",
            "fallback_policy",
            "path",
            "key",
            "source_path",
            "target_path",
            "precondition_version_cid",
            "precondition_content_cid",
            "payload",
            "backend_requirements",
            "alternate_backend_ids",
            "required_capabilities",
            "facets",
            "timing",
            "metadata_refs",
            "evidence_refs",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "operation request")
        identities = raw["identities"]
        if isinstance(identities, Mapping):
            identities = IdentityBindings.from_dict(identities)
        facets_raw = raw.get("facets") or ()
        facets = tuple(
            FacetRef.from_dict(item) if isinstance(item, Mapping) else item
            for item in facets_raw
        )
        payload_ref = raw.get("payload")
        if isinstance(payload_ref, Mapping):
            payload_ref = PayloadReference.from_dict(payload_ref)
        timing = raw.get("timing")
        if isinstance(timing, Mapping):
            timing = TimingBounds.from_dict(timing)
        value = cls(
            identities=identities,
            operation_name=raw["operation_name"] or "",
            consistency=(
                raw["consistency"]
                if raw["consistency"] is not None
                else ConsistencyRequirement.STRONG
            ),
            durability=(
                raw["durability"]
                if raw["durability"] is not None
                else DurabilityMode.WAL_FSYNC
            ),
            fallback_policy=(
                raw["fallback_policy"]
                if raw["fallback_policy"] is not None
                else FallbackPolicy.REJECT_IF_UNAVAILABLE
            ),
            path=raw.get("path") or "",
            key=raw.get("key") or "",
            source_path=raw.get("source_path") or "",
            target_path=raw.get("target_path") or "",
            precondition_version_cid=raw.get("precondition_version_cid") or "",
            precondition_content_cid=raw.get("precondition_content_cid") or "",
            payload=payload_ref,
            backend_requirements=tuple(raw.get("backend_requirements") or ()),
            alternate_backend_ids=tuple(raw.get("alternate_backend_ids") or ()),
            required_capabilities=tuple(raw.get("required_capabilities") or ()),
            facets=facets,
            timing=timing,
            metadata_refs=tuple(raw.get("metadata_refs") or ()),
            evidence_refs=tuple(raw.get("evidence_refs") or ()),
        )
        _verify_identity(payload, value)
        return value


# ---------------------------------------------------------------------------
# OperationResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationResult(CanonicalContract):
    """Canonical operation result (OperationResult@1).

    Success is never implied by the absence of an error alone: ``state`` must
    be a success acknowledgement and durable/verified/converged claims require
    matching evidence.
    """

    SCHEMA: ClassVar[str] = OPERATION_RESULT_SCHEMA

    request_id: str
    operation_id: str
    state: OperationState
    success: bool
    error: StorageError | None = None
    resulting_content_cid: str = ""
    resulting_version_cid: str = ""
    durability: DurabilityEvidence | None = None
    effect_evidence: tuple[EffectEvidence, ...] = ()
    partial_effects: tuple[PartialEffectRecord, ...] = ()
    timing: TimingBounds | None = None
    backend_id: str = ""
    wal_generation_id: str = ""
    cache_generation_id: str = ""
    index_generation_id: str = ""
    replica_policy_id: str = ""
    environment_id: str = ""
    evidence_refs: tuple[str, ...] = ()
    facets: tuple[FacetRef, ...] = ()
    idempotency_key: str = ""
    principal_id: str = ""
    policy_decision_cid: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _identifier(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        object.__setattr__(self, "state", _enum(self.state, OperationState, "state"))
        object.__setattr__(self, "success", _bool(self.success, "success"))
        error = self.error
        if error is not None and not isinstance(error, StorageError):
            if isinstance(error, Mapping):
                error = StorageError.from_dict(error)
            else:
                raise OperationContractError("error must be StorageError or null")
            object.__setattr__(self, "error", error)
        durability = self.durability
        if durability is not None and not isinstance(durability, DurabilityEvidence):
            if isinstance(durability, Mapping):
                durability = DurabilityEvidence.from_dict(durability)
            else:
                raise OperationContractError(
                    "durability must be DurabilityEvidence or null"
                )
            object.__setattr__(self, "durability", durability)
        timing = self.timing
        if timing is not None and not isinstance(timing, TimingBounds):
            if isinstance(timing, Mapping):
                timing = TimingBounds.from_dict(timing)
            else:
                raise OperationContractError("timing must be TimingBounds or null")
            object.__setattr__(self, "timing", timing)
        object.__setattr__(
            self,
            "resulting_content_cid",
            _optional_cid(self.resulting_content_cid, "resulting_content_cid"),
        )
        object.__setattr__(
            self,
            "resulting_version_cid",
            _optional_cid(self.resulting_version_cid, "resulting_version_cid"),
        )
        effects = _coerce_effect_tuple(self.effect_evidence)
        object.__setattr__(self, "effect_evidence", effects)
        partials = _coerce_partial_tuple(self.partial_effects)
        object.__setattr__(self, "partial_effects", partials)
        for name in (
            "backend_id",
            "wal_generation_id",
            "cache_generation_id",
            "index_generation_id",
            "replica_policy_id",
            "environment_id",
            "idempotency_key",
            "principal_id",
        ):
            object.__setattr__(
                self, name, _optional_identifier(getattr(self, name), name)
            )
        object.__setattr__(
            self,
            "policy_decision_cid",
            _optional_cid(self.policy_decision_cid, "policy_decision_cid"),
        )
        object.__setattr__(
            self, "evidence_refs", _ids(self.evidence_refs, "evidence_refs")
        )
        facets = _coerce_facet_tuple(self.facets)
        object.__setattr__(self, "facets", facets)
        _assert_facets_distinct(facets)
        _validate_result_invariants(self)
        _bounded_record(self, "operation result")

    def _payload(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "operation_id": self.operation_id,
            "state": self.state.value,
            "success": self.success,
            "error": None if self.error is None else self.error.to_dict(),
            "resulting_content_cid": self.resulting_content_cid,
            "resulting_version_cid": self.resulting_version_cid,
            "durability": None if self.durability is None else self.durability.to_dict(),
            "effect_evidence": [item.to_dict() for item in self.effect_evidence],
            "partial_effects": [item.to_dict() for item in self.partial_effects],
            "timing": None if self.timing is None else self.timing.to_dict(),
            "backend_id": self.backend_id,
            "wal_generation_id": self.wal_generation_id,
            "cache_generation_id": self.cache_generation_id,
            "index_generation_id": self.index_generation_id,
            "replica_policy_id": self.replica_policy_id,
            "environment_id": self.environment_id,
            "evidence_refs": list(self.evidence_refs),
            "facets": [facet.to_dict() for facet in self.facets],
            "idempotency_key": self.idempotency_key,
            "principal_id": self.principal_id,
            "policy_decision_cid": self.policy_decision_cid,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OperationResult":
        fields = (
            "request_id",
            "operation_id",
            "state",
            "success",
            "error",
            "resulting_content_cid",
            "resulting_version_cid",
            "durability",
            "effect_evidence",
            "partial_effects",
            "timing",
            "backend_id",
            "wal_generation_id",
            "cache_generation_id",
            "index_generation_id",
            "replica_policy_id",
            "environment_id",
            "evidence_refs",
            "facets",
            "idempotency_key",
            "principal_id",
            "policy_decision_cid",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "operation result")
        error = raw.get("error")
        if isinstance(error, Mapping):
            error = StorageError.from_dict(error)
        durability = raw.get("durability")
        if isinstance(durability, Mapping):
            durability = DurabilityEvidence.from_dict(durability)
        timing = raw.get("timing")
        if isinstance(timing, Mapping):
            timing = TimingBounds.from_dict(timing)
        effects = tuple(
            EffectEvidence.from_dict(item) if isinstance(item, Mapping) else item
            for item in (raw.get("effect_evidence") or ())
        )
        partials = tuple(
            PartialEffectRecord.from_dict(item) if isinstance(item, Mapping) else item
            for item in (raw.get("partial_effects") or ())
        )
        facets = tuple(
            FacetRef.from_dict(item) if isinstance(item, Mapping) else item
            for item in (raw.get("facets") or ())
        )
        value = cls(
            request_id=raw["request_id"] or "",
            operation_id=raw["operation_id"] or "",
            state=raw["state"] if raw["state"] is not None else OperationState.FAILED,
            success=bool(raw["success"]) if raw.get("success") is not None else False,
            error=error,
            resulting_content_cid=raw.get("resulting_content_cid") or "",
            resulting_version_cid=raw.get("resulting_version_cid") or "",
            durability=durability,
            effect_evidence=effects,
            partial_effects=partials,
            timing=timing,
            backend_id=raw.get("backend_id") or "",
            wal_generation_id=raw.get("wal_generation_id") or "",
            cache_generation_id=raw.get("cache_generation_id") or "",
            index_generation_id=raw.get("index_generation_id") or "",
            replica_policy_id=raw.get("replica_policy_id") or "",
            environment_id=raw.get("environment_id") or "",
            evidence_refs=tuple(raw.get("evidence_refs") or ()),
            facets=facets,
            idempotency_key=raw.get("idempotency_key") or "",
            principal_id=raw.get("principal_id") or "",
            policy_decision_cid=raw.get("policy_decision_cid") or "",
        )
        _verify_identity(payload, value)
        return value


def _validate_result_invariants(result: OperationResult) -> None:
    """Enforce success/state/evidence consistency (fail-closed)."""

    state = result.state
    success = result.success
    error = result.error
    durability = result.durability

    if success and state in FAILURE_STATES:
        raise InconsistentStateError(
            f"success=True is inconsistent with failure state {state.value}"
        )
    if success and state in PARTIAL_STATES:
        raise InconsistentStateError(
            f"success=True is inconsistent with partial state {state.value}"
        )
    if not success and state in SUCCESS_STATES and state not in {
        OperationState.ACCEPTED,
        OperationState.QUEUED,
        OperationState.PENDING,
        OperationState.PROCESSING,
    }:
        # Non-durable progress states may be success=False only if rejected mid-flight;
        # durable claims require success.
        if state in DURABLE_STATES:
            raise InconsistentStateError(
                f"success=False is inconsistent with durable state {state.value}"
            )
    if success and error is not None:
        raise InconsistentStateError("successful results cannot carry StorageError")
    if not success and error is None and state not in {
        OperationState.ACCEPTED,
        OperationState.QUEUED,
        OperationState.PENDING,
        OperationState.PROCESSING,
        OperationState.PARTIAL_EFFECT,
        OperationState.COMPENSATING,
    }:
        raise InconsistentStateError(
            f"failure state {state.value} requires a StorageError"
        )
    if state is OperationState.PARTIAL_EFFECT and not result.partial_effects:
        raise InconsistentStateError(
            "partial_effect state requires PartialEffectRecord entries"
        )
    if state in DURABLE_STATES:
        if durability is None:
            raise InconsistentStateError(
                f"state {state.value} requires DurabilityEvidence"
            )
        if state is OperationState.COMMITTED and not durability.supports_committed():
            raise InconsistentStateError(
                "committed state lacks required durability evidence for mode "
                f"{durability.mode.value}"
            )
        if state is OperationState.VERIFIED and not durability.supports_verified():
            raise InconsistentStateError(
                "verified state requires integrity proof plus committed evidence"
            )
        if state is OperationState.CONVERGED and not durability.supports_converged():
            raise InconsistentStateError(
                "converged state requires verified evidence plus "
                "replica/cache/index generation bindings"
            )
        if not result.effect_evidence and not durability.effect_evidence_ids:
            raise InconsistentStateError(
                f"state {state.value} requires effect evidence references"
            )
    # accepted/queued with durability mode that is accepted_only is fine without evidence
    if durability is not None and state in DURABLE_STATES:
        if durability.mode in (DurabilityMode.ACCEPTED_ONLY, DurabilityMode.QUEUED):
            raise InconsistentStateError(
                "durability mode accepted_only/queued cannot back a durable state"
            )


# ---------------------------------------------------------------------------
# StateTransitionReceipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StateTransitionReceipt(CanonicalContract):
    """Receipt for one admitted state transition (StateTransitionReceipt@1)."""

    SCHEMA: ClassVar[str] = STATE_TRANSITION_RECEIPT_SCHEMA

    receipt_id: str
    request_id: str
    operation_id: str
    from_state: OperationState
    to_state: OperationState
    at_unix_ms: int
    reason: str = ""
    actor_id: str = ""
    evidence_refs: tuple[str, ...] = ()
    durability: DurabilityEvidence | None = None
    error: StorageError | None = None
    backend_id: str = ""
    wal_generation_id: str = ""
    environment_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "receipt_id", _identifier(self.receipt_id, "receipt_id")
        )
        object.__setattr__(
            self, "request_id", _identifier(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "operation_id", _identifier(self.operation_id, "operation_id")
        )
        object.__setattr__(
            self, "from_state", _enum(self.from_state, OperationState, "from_state")
        )
        object.__setattr__(
            self, "to_state", _enum(self.to_state, OperationState, "to_state")
        )
        object.__setattr__(
            self,
            "at_unix_ms",
            _bounded_int(self.at_unix_ms, "at_unix_ms", minimum=0),
        )
        object.__setattr__(
            self, "reason", _text(self.reason, "reason", limit=MAX_TEXT_BYTES)
        )
        object.__setattr__(
            self, "actor_id", _optional_identifier(self.actor_id, "actor_id")
        )
        object.__setattr__(
            self, "evidence_refs", _ids(self.evidence_refs, "evidence_refs")
        )
        durability = self.durability
        if durability is not None and not isinstance(durability, DurabilityEvidence):
            if isinstance(durability, Mapping):
                durability = DurabilityEvidence.from_dict(durability)
            else:
                raise OperationContractError(
                    "durability must be DurabilityEvidence or null"
                )
            object.__setattr__(self, "durability", durability)
        error = self.error
        if error is not None and not isinstance(error, StorageError):
            if isinstance(error, Mapping):
                error = StorageError.from_dict(error)
            else:
                raise OperationContractError("error must be StorageError or null")
            object.__setattr__(self, "error", error)
        for name in ("backend_id", "wal_generation_id", "environment_id"):
            object.__setattr__(
                self, name, _optional_identifier(getattr(self, name), name)
            )
        if not is_legal_transition(self.from_state, self.to_state):
            raise InconsistentStateError(
                f"illegal state transition {self.from_state.value} → {self.to_state.value}"
            )
        if self.to_state in DURABLE_STATES:
            if self.durability is None or not self._durability_ok_for(self.to_state):
                raise InconsistentStateError(
                    f"transition to {self.to_state.value} requires matching durability evidence"
                )
        if self.to_state in FAILURE_STATES and self.error is None:
            raise InconsistentStateError(
                f"transition to {self.to_state.value} requires StorageError"
            )
        if self.to_state in SUCCESS_STATES and self.error is not None:
            raise InconsistentStateError(
                "success transition cannot carry StorageError"
            )
        _bounded_record(self, "state transition receipt")

    def _durability_ok_for(self, state: OperationState) -> bool:
        evidence = self.durability
        if evidence is None:
            return False
        if state is OperationState.COMMITTED:
            return evidence.supports_committed()
        if state is OperationState.VERIFIED:
            return evidence.supports_verified()
        if state is OperationState.CONVERGED:
            return evidence.supports_converged()
        return False

    def _payload(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "operation_id": self.operation_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "at_unix_ms": self.at_unix_ms,
            "reason": self.reason,
            "actor_id": self.actor_id,
            "evidence_refs": list(self.evidence_refs),
            "durability": None if self.durability is None else self.durability.to_dict(),
            "error": None if self.error is None else self.error.to_dict(),
            "backend_id": self.backend_id,
            "wal_generation_id": self.wal_generation_id,
            "environment_id": self.environment_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StateTransitionReceipt":
        fields = (
            "receipt_id",
            "request_id",
            "operation_id",
            "from_state",
            "to_state",
            "at_unix_ms",
            "reason",
            "actor_id",
            "evidence_refs",
            "durability",
            "error",
            "backend_id",
            "wal_generation_id",
            "environment_id",
        )
        raw = _decode_fields(payload, cls.SCHEMA, fields, "state transition receipt")
        durability = raw.get("durability")
        if isinstance(durability, Mapping):
            durability = DurabilityEvidence.from_dict(durability)
        error = raw.get("error")
        if isinstance(error, Mapping):
            error = StorageError.from_dict(error)
        value = cls(
            receipt_id=raw["receipt_id"] or "",
            request_id=raw["request_id"] or "",
            operation_id=raw["operation_id"] or "",
            from_state=(
                raw["from_state"]
                if raw["from_state"] is not None
                else OperationState.ACCEPTED
            ),
            to_state=(
                raw["to_state"]
                if raw["to_state"] is not None
                else OperationState.FAILED
            ),
            at_unix_ms=int(raw.get("at_unix_ms") or 0),
            reason=raw.get("reason") or "",
            actor_id=raw.get("actor_id") or "",
            evidence_refs=tuple(raw.get("evidence_refs") or ()),
            durability=durability,
            error=error,
            backend_id=raw.get("backend_id") or "",
            wal_generation_id=raw.get("wal_generation_id") or "",
            environment_id=raw.get("environment_id") or "",
        )
        _verify_identity(payload, value)
        return value


# ---------------------------------------------------------------------------
# Helpers for nested collections and cycle checks
# ---------------------------------------------------------------------------


def _coerce_facet_tuple(values: Any) -> tuple[FacetRef, ...]:
    if values is None:
        return ()
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise OperationContractError("facets must be a sequence of FacetRef")
    if len(values) > MAX_REFERENCE_COUNT:
        raise OperationContractBoundsError("facets exceed reference count bound")
    out: list[FacetRef] = []
    for item in values:
        if isinstance(item, FacetRef):
            out.append(item)
        elif isinstance(item, Mapping):
            out.append(FacetRef.from_dict(item))
        else:
            raise OperationContractError("facet entries must be FacetRef")
    return tuple(out)


def _coerce_effect_tuple(values: Any) -> tuple[EffectEvidence, ...]:
    if values is None:
        return ()
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise OperationContractError("effect_evidence must be a sequence")
    if len(values) > MAX_REFERENCE_COUNT:
        raise OperationContractBoundsError(
            "effect_evidence exceeds reference count bound"
        )
    out: list[EffectEvidence] = []
    for item in values:
        if isinstance(item, EffectEvidence):
            out.append(item)
        elif isinstance(item, Mapping):
            out.append(EffectEvidence.from_dict(item))
        else:
            raise OperationContractError("effect_evidence entries must be EffectEvidence")
    return tuple(out)


def _coerce_partial_tuple(values: Any) -> tuple[PartialEffectRecord, ...]:
    if values is None:
        return ()
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise OperationContractError("partial_effects must be a sequence")
    if len(values) > MAX_REFERENCE_COUNT:
        raise OperationContractBoundsError(
            "partial_effects exceeds reference count bound"
        )
    out: list[PartialEffectRecord] = []
    for item in values:
        if isinstance(item, PartialEffectRecord):
            out.append(item)
        elif isinstance(item, Mapping):
            out.append(PartialEffectRecord.from_dict(item))
        else:
            raise OperationContractError(
                "partial_effects entries must be PartialEffectRecord"
            )
    return tuple(out)


def _assert_facets_distinct(facets: Sequence[FacetRef]) -> None:
    """Ensure type/resource/memory facets remain distinct by kind and ref prefix."""

    seen_ids: set[str] = set()
    for facet in facets:
        if facet.facet_id in seen_ids:
            raise InconsistentStateError(
                f"duplicate facet_id {facet.facet_id}"
            )
        seen_ids.add(facet.facet_id)
    # Cross-kind promotion already rejected in FacetRef; re-check pairs.
    by_kind: dict[FacetKind, list[FacetRef]] = {}
    for facet in facets:
        by_kind.setdefault(facet.kind, []).append(facet)
    type_refs = {f.contract_ref for f in by_kind.get(FacetKind.TYPE, ()) if f.contract_ref}
    resource_refs = {
        f.contract_ref for f in by_kind.get(FacetKind.RESOURCE, ()) if f.contract_ref
    }
    memory_refs = {
        f.contract_ref for f in by_kind.get(FacetKind.MEMORY, ()) if f.contract_ref
    }
    if type_refs & resource_refs or type_refs & memory_refs or resource_refs & memory_refs:
        raise InconsistentStateError(
            "type/resource/memory facet contract_ref sets must remain disjoint"
        )


def assert_acyclic_evidence_refs(
    edges: Mapping[str, Sequence[str]],
) -> None:
    """Reject cycles in an evidence-reference graph (id → dependents)."""

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            raise CycleDetectedError(f"cycle detected at evidence ref {node}")
        visiting.add(node)
        for child in edges.get(node, ()):
            if not isinstance(child, str):
                raise OperationContractError("evidence graph edges must be strings")
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for root in edges:
        visit(root)


def assert_acyclic_state_chain(
    transitions: Sequence[StateTransitionReceipt],
) -> None:
    """Reject impossible chains (illegal edges or cycles via repeated from/to)."""

    if not transitions:
        return
    # Pairwise legality
    for receipt in transitions:
        if not is_legal_transition(receipt.from_state, receipt.to_state):
            raise InconsistentStateError(
                f"illegal transition in chain: {receipt.from_state.value} → "
                f"{receipt.to_state.value}"
            )
    # Contiguity: each subsequent from_state must equal previous to_state
    for left, right in zip(transitions, transitions[1:]):
        if left.to_state is not right.from_state:
            raise InconsistentStateError(
                "state transition chain is not contiguous: "
                f"{left.to_state.value} then {right.from_state.value}"
            )
        if left.operation_id != right.operation_id:
            raise InconsistentStateError(
                "state transition chain mixes operation identities"
            )
    # Detect simple cycles in the path of states
    path = [transitions[0].from_state]
    path.extend(item.to_state for item in transitions)
    seen_positions: dict[OperationState, int] = {}
    for index, state in enumerate(path):
        if state in seen_positions and index - seen_positions[state] > 0:
            # Allow re-visiting only if it is a self-loop no-op already filtered.
            # Any longer cycle is rejected.
            if path[seen_positions[state] : index + 1].count(state) > 1:
                # Standard cycle detection on the state sequence
                pass
        seen_positions[state] = index
    # Graph cycle: if any state appears twice with a non-empty intermediate path
    # that returns, reject.  Terminal failure/success re-entry is already illegal
    # via transition table; this catches longer loops.
    first_seen: dict[OperationState, int] = {}
    for index, state in enumerate(path):
        if state in first_seen:
            if index - first_seen[state] > 1 or (
                index - first_seen[state] == 1 and path[first_seen[state]] is not state
            ):
                # Reappearance of a state after leaving it is a cycle.
                if any(s is not state for s in path[first_seen[state] + 1 : index]):
                    raise CycleDetectedError(
                        f"state chain cycles through {state.value}"
                    )
        else:
            first_seen[state] = index


# ---------------------------------------------------------------------------
# Factory helpers for common durable success evidence
# ---------------------------------------------------------------------------


def durability_for_wal_fsync(
    *,
    wal_record_id: str,
    fsync_receipt_id: str,
    wal_generation_id: str = "",
    transaction_commit_id: str = "",
    effect_evidence_ids: Sequence[str] = (),
) -> DurabilityEvidence:
    """Build durability evidence sufficient for a committed acknowledgement."""

    return DurabilityEvidence(
        mode=DurabilityMode.WAL_FSYNC,
        wal_record_id=wal_record_id,
        fsync_receipt_id=fsync_receipt_id,
        wal_generation_id=wal_generation_id,
        transaction_commit_id=transaction_commit_id,
        effect_evidence_ids=tuple(effect_evidence_ids),
    )


def durability_for_verified(
    *,
    base: DurabilityEvidence,
    integrity_proof_id: str,
) -> DurabilityEvidence:
    """Extend committed evidence with an integrity proof for verified state."""

    return DurabilityEvidence(
        mode=base.mode,
        wal_record_id=base.wal_record_id,
        wal_generation_id=base.wal_generation_id,
        fsync_receipt_id=base.fsync_receipt_id,
        backend_ack_id=base.backend_ack_id,
        transaction_commit_id=base.transaction_commit_id,
        integrity_proof_id=integrity_proof_id,
        replica_receipt_ids=base.replica_receipt_ids,
        cache_generation_id=base.cache_generation_id,
        index_generation_id=base.index_generation_id,
        effect_evidence_ids=base.effect_evidence_ids,
    )


def durability_for_converged(
    *,
    base: DurabilityEvidence,
    replica_receipt_ids: Sequence[str] = (),
    cache_generation_id: str = "",
    index_generation_id: str = "",
) -> DurabilityEvidence:
    """Extend verified evidence with convergence bindings."""

    if not base.integrity_proof_id:
        raise InconsistentStateError(
            "converged durability requires a prior integrity proof"
        )
    replicas = tuple(replica_receipt_ids) or base.replica_receipt_ids
    cache = cache_generation_id or base.cache_generation_id
    index = index_generation_id or base.index_generation_id
    if not (replicas or cache or index):
        raise InconsistentStateError(
            "converged durability requires replica, cache, or index generation evidence"
        )
    return DurabilityEvidence(
        mode=base.mode,
        wal_record_id=base.wal_record_id,
        wal_generation_id=base.wal_generation_id,
        fsync_receipt_id=base.fsync_receipt_id,
        backend_ack_id=base.backend_ack_id,
        transaction_commit_id=base.transaction_commit_id,
        integrity_proof_id=base.integrity_proof_id,
        replica_receipt_ids=replicas,
        cache_generation_id=cache,
        index_generation_id=index,
        effect_evidence_ids=base.effect_evidence_ids,
    )


__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "OPERATION_REQUEST_SCHEMA",
    "OPERATION_RESULT_SCHEMA",
    "STORAGE_ERROR_SCHEMA",
    "STATE_TRANSITION_RECEIPT_SCHEMA",
    "MAX_RECORD_BYTES",
    "MAX_TEXT_BYTES",
    "MAX_REFERENCE_COUNT",
    "SUCCESS_STATES",
    "FAILURE_STATES",
    "PARTIAL_STATES",
    "DURABLE_STATES",
    "VERIFIED_STATES",
    "CONVERGED_STATES",
    "OperationState",
    "ConsistencyRequirement",
    "DurabilityMode",
    "Retryability",
    "FallbackPolicy",
    "ErrorCategory",
    "ErrorCode",
    "EffectKind",
    "EvidenceKind",
    "FacetKind",
    "PayloadKind",
    "OperationContractError",
    "OperationContractBoundsError",
    "ForgedIdentityError",
    "InconsistentStateError",
    "SecretMaterialError",
    "BodyRejectedError",
    "CycleDetectedError",
    "CanonicalContract",
    "FacetRef",
    "TimingBounds",
    "PayloadReference",
    "EffectEvidence",
    "DurabilityEvidence",
    "PartialEffectRecord",
    "IdentityBindings",
    "StorageError",
    "OperationRequest",
    "OperationResult",
    "StateTransitionReceipt",
    "canonical_json",
    "canonical_json_bytes",
    "content_identity",
    "is_legal_transition",
    "assert_acyclic_evidence_refs",
    "assert_acyclic_state_chain",
    "durability_for_wal_fsync",
    "durability_for_verified",
    "durability_for_converged",
]
