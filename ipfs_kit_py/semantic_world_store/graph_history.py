"""Immutable logical graph snapshots, traces, and transition-log history.

``LogicalProgramGraphStore`` and ``ProgramTransitionLog`` implement
``ProgramGraphHistory@1``.  They persist datasets graph/transition/trace
codecs over ``DurableCoordinationStore`` without minting a second CID
engine or deciding semantic admission.

Authority rules (normative, fail-closed):

* Physical IPLD/Merkle blocks are immutable and acyclic.  Logical cycles
  (mutual recursion, cyclic imports, CFG/state loops) stay queryable as
  independently hashed node/edge records.
* Every parent record is admitted only after referenced bytes already
  exist (store-before-reference).  Missing or corrupt references fail.
* Predictions and observations are disjoint kinds and schemas.  A stored
  prediction cannot decode as an observation and cannot self-admit.
* Repeated states preserve distinct event history via predecessor-linked
  events and ordered traces.
* Kit persists records; it never accepts semantics, publishes a mutable
  current root, or performs generation CAS (SAWM-014).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Final, Iterable, Mapping, Optional, Sequence

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_execution import (
    ExecutionTrace as ProgramExecutionTrace,
    ExecutionTraceSegment,
    ProgramEvent as ProgramExecutionEvent,
    ProgramExecutionError,
    decode_program_execution_record,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    GRAPH_REFERENCE_FIELDS,
    CallsiteRecord,
    ContractStateRecord,
    DynamicFrontierRecord,
    FunctionSymbolRecord,
    ProgramGraphDelta,
    ProgramGraphEdge,
    ProgramGraphError,
    ProgramGraphNode,
    ProgramGraphSnapshot,
    ProofObligationGraph,
    StaticSuccessorSet,
    apply_program_graph_delta,
    assemble_program_graph_snapshot,
    assert_physical_dag_acyclic,
    decode_program_graph_record,
    delta_between_snapshots,
    directed_logical_cycles,
    verify_program_graph_catalog,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    CanonicalProgramGraphIdentity,
    ExecutionTraceIdentity,
    ProgramEventIdentity,
    ProgramIdentityError,
    RawExecutionStateIdentity,
    SemanticWorldRootIdentity,
    decode_identity_record,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
    PROGRAM_TRANSITION_OBSERVATION_SCHEMA,
    PROGRAM_TRANSITION_PREDICTION_SCHEMA,
    ProgramTransitionAdmission,
    ProgramTransitionCandidate,
    ProgramTransitionError,
    ProgramTransitionObservation,
    ProgramTransitionPrediction,
    ProgramTransitionQuery,
    ProgramTransitionReceipt,
    decode_transition_observation,
    decode_transition_record,
    issue_transition_receipt,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes,
    validate_transport_cid,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    SemanticGovernorStoreContractError,
    validate_operation_id,
    validate_verified_cid,
)
from ipfs_kit_py.semantic_world_store.artifacts import (
    MAX_ARTIFACT_BYTES,
    SemanticWorldArtifactStore,
    reject_private_raw_source,
)
from ipfs_kit_py.semantic_world_store.verified_store import VerifiedSemanticBlockStore


# ---------------------------------------------------------------------------
# Schema / limits
# ---------------------------------------------------------------------------

PROGRAM_GRAPH_HISTORY_INTERFACE: Final[str] = "ProgramGraphHistory@1"
STORED_HISTORY_INTERFACE: Final[str] = "SemanticWorldHistoryRecord@1"
STORED_HISTORY_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.history-record@1"
)
GRAPH_HISTORY_ENTRY_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.graph-history-entry@1"
)
GRAPH_HISTORY_ENTRY_INTERFACE: Final[str] = "GraphHistoryEntry@1"
TRANSITION_LOG_ENTRY_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.transition-log-entry@1"
)
TRANSITION_LOG_ENTRY_INTERFACE: Final[str] = "TransitionLogEntry@1"
OPAQUE_SUBROOT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.opaque-subroot@1"
)
HISTORY_SCHEMA_VERSION: Final[int] = 1
MAX_HISTORY_BYTES: Final[int] = MAX_ARTIFACT_BYTES
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1
_CLASSVAR_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {"SCHEMA", "INTERFACE", "CID_FIELD", "_FIELDS"}
)
GRAPH_HISTORY_ENTRY_PAYLOAD_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface",
        "snapshot_cid",
        "sequence",
        "previous_entry_cid",
        "delta_cid",
        "trace_cid",
    }
)
TRANSITION_LOG_ENTRY_PAYLOAD_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface",
        "receipt_cid",
        "query_cid",
        "admission_cid",
        "verdict",
        "sequence",
        "previous_entry_cid",
        "prediction_cid",
        "observation_cid",
    }
)

_OPS_DB_NAME: Final[str] = "semantic_world_history_index.sqlite3"
_SEALED_FIELDS: Final[frozenset[str]] = frozenset(
    ("schema", "interface_id", "kind", "payload")
)

HISTORY_REFERENCE_FIELDS: Final[frozenset[str]] = GRAPH_REFERENCE_FIELDS | frozenset(
    {
        "admission_cid",
        "analysis_limitation_index_cid",
        "canonical_program_graph_cid",
        "current_environment_binding_cid",
        "current_graph_cid",
        "current_source_cid",
        "current_state_cid",
        "current_subject_cid",
        "current_trace_cid",
        "delta_cid",
        "domain_state_cid",
        "end_event_cid",
        "environment_binding_set_cid",
        "event_cids",
        "execution_trace_cids",
        "graph_history_head_cid",
        "model_profile_cid",
        "observation_cid",
        "parent_trace_cid",
        "policy_cid",
        "predecessor_event_cid",
        "prediction_cid",
        "previous_entry_cid",
        "previous_manifest_cid",
        "query_cid",
        "raw_execution_state_cids",
        "receipt_cid",
        "segment_cids",
        "semantic_object_index_cid",
        "semantic_world_root_cid",
        "start_event_cid",
        "subject_cid",
        "trace_cid",
        "transition_log_head_cid",
        "transition_receipt_cids",
        "world_snapshot_cid",
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GraphHistoryError(ValueError):
    """Base error for logical graph history and transition-log persistence."""


class GraphHistoryAdmissionError(GraphHistoryError):
    """Raised when a history write is rejected by closed admission policy."""


class GraphHistoryIntegrityError(GraphHistoryError):
    """Raised when bytes, CID, kind, or sealed shape do not verify."""


class GraphHistoryNotFound(GraphHistoryError, KeyError):
    """Raised when no verified history block exists for a CID."""


class GraphHistoryConflictError(GraphHistoryError):
    """Raised when an identity or operation_id is rebound to different bytes."""


# ---------------------------------------------------------------------------
# Closed kinds / write result
# ---------------------------------------------------------------------------


class HistoryRecordKind(str, Enum):
    """Closed taxonomy of semantic-world history admission kinds."""

    PROGRAM_GRAPH_NODE = "program_graph_node"
    PROGRAM_GRAPH_EDGE = "program_graph_edge"
    PROGRAM_GRAPH_SNAPSHOT = "program_graph_snapshot"
    PROGRAM_GRAPH_DELTA = "program_graph_delta"
    CALLSITE_RECORD = "callsite_record"
    FUNCTION_SYMBOL_RECORD = "function_symbol_record"
    CONTRACT_STATE_RECORD = "contract_state_record"
    PROOF_OBLIGATION_GRAPH = "proof_obligation_graph"
    STATIC_SUCCESSOR_SET = "static_successor_set"
    DYNAMIC_FRONTIER_RECORD = "dynamic_frontier_record"
    CANONICAL_PROGRAM_GRAPH = "canonical_program_graph"
    PROGRAM_EVENT = "program_event"
    EXECUTION_TRACE = "execution_trace"
    EXECUTION_TRACE_SEGMENT = "execution_trace_segment"
    RAW_EXECUTION_STATE = "raw_execution_state"
    GRAPH_HISTORY_ENTRY = "graph_history_entry"
    TRANSITION_QUERY = "transition_query"
    TRANSITION_CANDIDATE = "transition_candidate"
    TRANSITION_PREDICTION = "transition_prediction"
    TRANSITION_OBSERVATION = "transition_observation"
    TRANSITION_ADMISSION = "transition_admission"
    TRANSITION_RECEIPT = "transition_receipt"
    TRANSITION_LOG_ENTRY = "transition_log_entry"
    WORLD_SNAPSHOT = "world_snapshot"
    WORLD_ROOT_MANIFEST = "world_root_manifest"
    SEMANTIC_WORLD_ROOT_IDENTITY = "semantic_world_root_identity"
    OPAQUE_SUBROOT = "opaque_subroot"


_DATASETS_CID_FIELDS: Final[Mapping[HistoryRecordKind, str]] = MappingProxyType(
    {
        HistoryRecordKind.PROGRAM_GRAPH_NODE: "program_graph_node_cid",
        HistoryRecordKind.PROGRAM_GRAPH_EDGE: "program_graph_edge_cid",
        HistoryRecordKind.PROGRAM_GRAPH_SNAPSHOT: "program_graph_snapshot_cid",
        HistoryRecordKind.PROGRAM_GRAPH_DELTA: "program_graph_delta_cid",
        HistoryRecordKind.CALLSITE_RECORD: "callsite_record_cid",
        HistoryRecordKind.FUNCTION_SYMBOL_RECORD: "function_symbol_record_cid",
        HistoryRecordKind.CONTRACT_STATE_RECORD: "contract_state_record_cid",
        HistoryRecordKind.PROOF_OBLIGATION_GRAPH: "proof_obligation_graph_cid",
        HistoryRecordKind.STATIC_SUCCESSOR_SET: "static_successor_set_cid",
        HistoryRecordKind.DYNAMIC_FRONTIER_RECORD: "dynamic_frontier_record_cid",
        HistoryRecordKind.CANONICAL_PROGRAM_GRAPH: "canonical_program_graph_cid",
        HistoryRecordKind.PROGRAM_EVENT: "program_event_cid",
        HistoryRecordKind.EXECUTION_TRACE: "execution_trace_cid",
        HistoryRecordKind.EXECUTION_TRACE_SEGMENT: "execution_trace_segment_cid",
        HistoryRecordKind.RAW_EXECUTION_STATE: "raw_execution_state_cid",
        HistoryRecordKind.TRANSITION_QUERY: "query_cid",
        HistoryRecordKind.TRANSITION_CANDIDATE: "candidate_cid",
        HistoryRecordKind.TRANSITION_PREDICTION: "prediction_cid",
        HistoryRecordKind.TRANSITION_OBSERVATION: "observation_cid",
        HistoryRecordKind.TRANSITION_ADMISSION: "admission_cid",
        HistoryRecordKind.TRANSITION_RECEIPT: "receipt_cid",
        HistoryRecordKind.SEMANTIC_WORLD_ROOT_IDENTITY: "semantic_world_root_cid",
    }
)

_KIT_OWNED_KINDS: Final[frozenset[HistoryRecordKind]] = frozenset(
    {
        HistoryRecordKind.GRAPH_HISTORY_ENTRY,
        HistoryRecordKind.TRANSITION_LOG_ENTRY,
        HistoryRecordKind.WORLD_SNAPSHOT,
        HistoryRecordKind.WORLD_ROOT_MANIFEST,
        HistoryRecordKind.OPAQUE_SUBROOT,
    }
)


@dataclass(frozen=True, slots=True)
class HistoryWriteResult:
    """Verified local history write; identity CID is the caller-facing address."""

    cid: str
    storage_cid: str
    kind: HistoryRecordKind
    created: bool
    local_durable: bool
    reason_code: str
    delta_cid: str | None = None
    history_entry_cid: str | None = None
    log_entry_cid: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cid": self.cid,
            "storage_cid": self.storage_cid,
            "kind": self.kind.value,
            "created": self.created,
            "local_durable": self.local_durable,
            "reason_code": self.reason_code,
            "delta_cid": self.delta_cid,
            "history_entry_cid": self.history_entry_cid,
            "log_entry_cid": self.log_entry_cid,
        }


@dataclass(frozen=True, slots=True)
class GraphHistoryEntry:
    """Immutable snapshot-append record; repeated snapshots keep distinct entries."""

    snapshot_cid: str
    sequence: int
    previous_entry_cid: str | None = None
    delta_cid: str | None = None
    trace_cid: str | None = None

    SCHEMA: ClassVar[str] = GRAPH_HISTORY_ENTRY_SCHEMA
    INTERFACE: ClassVar[str] = GRAPH_HISTORY_ENTRY_INTERFACE

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "snapshot_cid", _require_cid(self.snapshot_cid, "snapshot_cid")
        )
        object.__setattr__(self, "sequence", _require_generation(self.sequence, "sequence"))
        object.__setattr__(
            self,
            "previous_entry_cid",
            _optional_cid(self.previous_entry_cid, "previous_entry_cid"),
        )
        object.__setattr__(self, "delta_cid", _optional_cid(self.delta_cid, "delta_cid"))
        object.__setattr__(self, "trace_cid", _optional_cid(self.trace_cid, "trace_cid"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "interface": self.INTERFACE,
            "snapshot_cid": self.snapshot_cid,
            "sequence": self.sequence,
            "previous_entry_cid": self.previous_entry_cid,
            "delta_cid": self.delta_cid,
            "trace_cid": self.trace_cid,
        }

    @classmethod
    def from_payload(cls, data: Mapping[str, Any]) -> "GraphHistoryEntry":
        payload = _closed_payload(data, cls, GRAPH_HISTORY_ENTRY_PAYLOAD_FIELDS)
        if payload.pop("schema") != cls.SCHEMA:
            raise GraphHistoryIntegrityError("unsupported graph-history-entry schema")
        if payload.pop("interface") != cls.INTERFACE:
            raise GraphHistoryIntegrityError("unsupported graph-history-entry interface")
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class TransitionLogEntry:
    """Immutable receipt-append record that preserves prediction/observation split."""

    receipt_cid: str
    query_cid: str
    admission_cid: str
    verdict: str
    sequence: int
    previous_entry_cid: str | None = None
    prediction_cid: str | None = None
    observation_cid: str | None = None

    SCHEMA: ClassVar[str] = TRANSITION_LOG_ENTRY_SCHEMA
    INTERFACE: ClassVar[str] = TRANSITION_LOG_ENTRY_INTERFACE

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "receipt_cid", _require_cid(self.receipt_cid, "receipt_cid")
        )
        object.__setattr__(self, "query_cid", _require_cid(self.query_cid, "query_cid"))
        object.__setattr__(
            self, "admission_cid", _require_cid(self.admission_cid, "admission_cid")
        )
        if type(self.verdict) is not str or not self.verdict:
            raise GraphHistoryAdmissionError("verdict must be a nonempty string")
        object.__setattr__(self, "verdict", self.verdict)
        object.__setattr__(self, "sequence", _require_generation(self.sequence, "sequence"))
        object.__setattr__(
            self,
            "previous_entry_cid",
            _optional_cid(self.previous_entry_cid, "previous_entry_cid"),
        )
        object.__setattr__(
            self, "prediction_cid", _optional_cid(self.prediction_cid, "prediction_cid")
        )
        object.__setattr__(
            self,
            "observation_cid",
            _optional_cid(self.observation_cid, "observation_cid"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "interface": self.INTERFACE,
            "receipt_cid": self.receipt_cid,
            "query_cid": self.query_cid,
            "admission_cid": self.admission_cid,
            "verdict": self.verdict,
            "sequence": self.sequence,
            "previous_entry_cid": self.previous_entry_cid,
            "prediction_cid": self.prediction_cid,
            "observation_cid": self.observation_cid,
        }

    @classmethod
    def from_payload(cls, data: Mapping[str, Any]) -> "TransitionLogEntry":
        payload = _closed_payload(data, cls, TRANSITION_LOG_ENTRY_PAYLOAD_FIELDS)
        if payload.pop("schema") != cls.SCHEMA:
            raise GraphHistoryIntegrityError("unsupported transition-log-entry schema")
        if payload.pop("interface") != cls.INTERFACE:
            raise GraphHistoryIntegrityError("unsupported transition-log-entry interface")
        return cls(**payload)


# ---------------------------------------------------------------------------
# Primitive validators
# ---------------------------------------------------------------------------


def _coerce_kind(kind: HistoryRecordKind | str) -> HistoryRecordKind:
    if isinstance(kind, HistoryRecordKind):
        return kind
    if isinstance(kind, str):
        try:
            return HistoryRecordKind(kind)
        except ValueError as exc:
            raise GraphHistoryAdmissionError(
                f"unknown semantic-world history kind: {kind!r}"
            ) from exc
    raise GraphHistoryAdmissionError(
        "kind must be a HistoryRecordKind or its closed string value"
    )


def _require_cid(value: object, name: str) -> str:
    try:
        return validate_verified_cid(value, name)
    except SemanticGovernorStoreContractError as exc:
        raise GraphHistoryAdmissionError(str(exc)) from exc


def _optional_cid(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _require_cid(value, name)


def _require_generation(value: object, name: str = "generation") -> int:
    if type(value) is not int or isinstance(value, bool) or value < 1:
        raise GraphHistoryAdmissionError(f"{name} must be a positive integer")
    if value > MAX_SAFE_INTEGER:
        raise GraphHistoryAdmissionError(f"{name} exceeds the safe JSON integer range")
    return value


def _payload_field_names(cls: type[Any]) -> frozenset[str]:
    declared = cls.__dict__.get("_FIELDS")
    if isinstance(declared, frozenset):
        return declared
    names: set[str] = {"schema"}
    for name, spec in getattr(cls, "__dataclass_fields__", {}).items():
        if name in _CLASSVAR_FIELD_NAMES or not getattr(spec, "init", True):
            continue
        type_hint = getattr(spec, "type", None)
        if type_hint is ClassVar or getattr(type_hint, "__origin__", None) is ClassVar:
            continue
        if isinstance(type_hint, str) and (
            type_hint == "ClassVar" or type_hint.startswith("ClassVar[")
        ):
            continue
        names.add(name)
    return frozenset(names)


def _closed_payload(
    data: Mapping[str, Any],
    cls: type[Any],
    fields: frozenset[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise GraphHistoryIntegrityError(f"{cls.__name__} must be a mapping")
    expected = fields if fields is not None else _payload_field_names(cls)
    actual = frozenset(data)
    extra = actual - expected
    missing = expected - actual
    if extra or missing:
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(sorted(missing))}")
        if extra:
            problems.append(f"unknown {', '.join(sorted(extra))}")
        raise GraphHistoryIntegrityError(
            f"{cls.__name__} has " + "; ".join(problems)
        )
    return dict(data)


def _require_structured_json_value(value: Any, *, path: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if value < -MAX_SAFE_INTEGER or value > MAX_SAFE_INTEGER:
            raise GraphHistoryAdmissionError(
                f"{path} integer is outside the safe JSON range"
            )
        return
    if isinstance(value, str):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _require_structured_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise GraphHistoryAdmissionError(
                    f"{path} map keys must be str, got {type(key).__name__}"
                )
            _require_structured_json_value(item, path=f"{path}.{key}")
        return
    raise GraphHistoryAdmissionError(
        f"{path} must be strict DAG-JSON (no floats, bytes, or host types); "
        f"got {type(value).__name__}"
    )


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GraphHistoryAdmissionError(
            f"history record is not canonical JSON: {exc}"
        ) from exc


def seal_history_record(
    kind: HistoryRecordKind | str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the closed, content-addressed storage envelope for a payload."""

    record_kind = _coerce_kind(kind)
    if not isinstance(payload, Mapping):
        raise GraphHistoryAdmissionError("payload must be a mapping")
    body = dict(payload)
    _require_structured_json_value(body, path="payload")
    reject_private_raw_source(body, path="payload")
    sealed = {
        "schema": STORED_HISTORY_SCHEMA,
        "interface_id": STORED_HISTORY_INTERFACE,
        "kind": record_kind.value,
        "payload": body,
    }
    reject_private_raw_source(sealed, path="$")
    data = _canonical_bytes(sealed)
    if len(data) > MAX_HISTORY_BYTES:
        raise GraphHistoryAdmissionError(
            f"history record exceeds MAX_HISTORY_BYTES ({len(data)} > {MAX_HISTORY_BYTES})"
        )
    return sealed


def admit_history_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a retrieved or candidate sealed envelope and return a plain dict."""

    if not isinstance(record, Mapping):
        raise GraphHistoryIntegrityError("sealed history record must be a mapping")
    actual = frozenset(record)
    if actual != _SEALED_FIELDS:
        missing = sorted(_SEALED_FIELDS - actual)
        unknown = sorted(actual - _SEALED_FIELDS)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise GraphHistoryIntegrityError(
            "sealed history record has " + "; ".join(problems)
        )
    if record.get("schema") != STORED_HISTORY_SCHEMA:
        raise GraphHistoryIntegrityError(
            f"unknown history schema: {record.get('schema')!r}"
        )
    if record.get("interface_id") != STORED_HISTORY_INTERFACE:
        raise GraphHistoryIntegrityError("unknown sealed history interface_id")
    try:
        kind = _coerce_kind(record["kind"])
    except GraphHistoryAdmissionError as exc:
        raise GraphHistoryIntegrityError(str(exc)) from exc
    payload = record["payload"]
    if not isinstance(payload, Mapping):
        raise GraphHistoryIntegrityError("payload must be a mapping")
    body = dict(payload)
    try:
        _require_structured_json_value(body, path="payload")
        reject_private_raw_source(body, path="payload")
    except GraphHistoryAdmissionError as exc:
        raise GraphHistoryIntegrityError(str(exc)) from exc
    sealed = {
        "schema": STORED_HISTORY_SCHEMA,
        "interface_id": STORED_HISTORY_INTERFACE,
        "kind": kind.value,
        "payload": body,
    }
    data = _canonical_bytes(sealed)
    if len(data) > MAX_HISTORY_BYTES:
        raise GraphHistoryIntegrityError(
            f"history record exceeds MAX_HISTORY_BYTES ({len(data)} > {MAX_HISTORY_BYTES})"
        )
    if cid_for_artifact(dict(record)) != cid_for_artifact(sealed):
        raise GraphHistoryIntegrityError("sealed history record is not in canonical form")
    return sealed


def identity_cid_from_history_payload(
    kind: HistoryRecordKind | str,
    payload: Mapping[str, Any],
    *,
    storage_cid: str | None = None,
) -> str:
    """Return the caller-facing identity CID bound inside a sealed payload."""

    record_kind = _coerce_kind(kind)
    field = _DATASETS_CID_FIELDS.get(record_kind)
    if field is None:
        if storage_cid is None:
            raise GraphHistoryIntegrityError(
                f"{record_kind.value} identity requires a storage CID"
            )
        return storage_cid
    value = payload.get(field)
    try:
        return validate_verified_cid(value, field)
    except SemanticGovernorStoreContractError as exc:
        raise GraphHistoryIntegrityError(
            f"payload.{field} must be a canonical transport CID"
        ) from exc


def _payload_refs(payload: Mapping[str, Any], catalog: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, Mapping):
            for key, value in obj.items():
                if key in HISTORY_REFERENCE_FIELDS:
                    if type(value) is str and value in catalog:
                        refs.append(value)
                    elif isinstance(value, list):
                        for item in value:
                            if type(item) is str and item in catalog:
                                refs.append(item)
                else:
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload)
    return tuple(refs)


def assert_history_physical_dag_acyclic(
    cid_to_payload: Mapping[str, Mapping[str, Any]],
) -> None:
    """Fail closed if assembled history blocks form a physical CID cycle."""

    if not isinstance(cid_to_payload, Mapping):
        raise GraphHistoryIntegrityError("physical DAG catalog must be a mapping")
    catalog = dict(cid_to_payload)
    adjacency = {
        cid: _payload_refs(payload, catalog) for cid, payload in catalog.items()
    }
    white, gray, black = 0, 1, 2
    color = {cid: white for cid in catalog}

    def dfs(node: str) -> None:
        color[node] = gray
        for nxt in adjacency[node]:
            state = color.get(nxt, black)
            if state == gray:
                raise GraphHistoryIntegrityError(
                    "physical IPLD block graph must be acyclic"
                )
            if state == white:
                dfs(nxt)
        color[node] = black

    for cid in catalog:
        if color[cid] == white:
            dfs(cid)


def _record_cid(record: Any) -> str:
    field = getattr(record, "CID_FIELD", None)
    if type(field) is not str:
        raise GraphHistoryAdmissionError("record does not declare CID_FIELD")
    return str(getattr(record, field))


def _as_mapping_payload(record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    to_dict = getattr(record, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if not isinstance(payload, Mapping):
            raise GraphHistoryAdmissionError("record.to_dict() must return a mapping")
        return dict(payload)
    to_payload = getattr(record, "to_payload", None)
    if callable(to_payload):
        payload = to_payload()
        if not isinstance(payload, Mapping):
            raise GraphHistoryAdmissionError("record.to_payload() must return a mapping")
        return dict(payload)
    raise GraphHistoryAdmissionError("record must be a mapping or codec object")


# ---------------------------------------------------------------------------
# Identity / operation index (rebuildable; blocks remain authoritative)
# ---------------------------------------------------------------------------


class _HistoryIndex:
    """Local identity/operation bindings next to the coordination store root."""

    def __init__(self, store: DurableCoordinationStore) -> None:
        self._path = store.root / _OPS_DB_NAME
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self._path), timeout=30, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS identity_bindings (
              identity_cid TEXT PRIMARY KEY,
              storage_cid TEXT NOT NULL,
              kind TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS identity_bindings_storage
              ON identity_bindings(storage_cid);
            CREATE TABLE IF NOT EXISTS history_operations (
              operation_id TEXT PRIMARY KEY,
              identity_cid TEXT NOT NULL,
              storage_cid TEXT NOT NULL,
              kind TEXT NOT NULL
            );
            """
        )
        self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def lookup_identity(self, identity_cid: str) -> tuple[str, str] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT storage_cid, kind FROM identity_bindings WHERE identity_cid = ?",
                (identity_cid,),
            ).fetchone()
        if row is None:
            return None
        return str(row["storage_cid"]), str(row["kind"])

    def lookup_storage(self, storage_cid: str) -> tuple[str, str] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT identity_cid, kind FROM identity_bindings WHERE storage_cid = ?",
                (storage_cid,),
            ).fetchone()
        if row is None:
            return None
        return str(row["identity_cid"]), str(row["kind"])

    def lookup_operation(self, operation_id: str) -> tuple[str, str, str] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT identity_cid, storage_cid, kind FROM history_operations "
                "WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["identity_cid"]), str(row["storage_cid"]), str(row["kind"])

    def bind_identity(self, identity_cid: str, storage_cid: str, kind: str) -> None:
        with self._lock:
            existing = self._connection.execute(
                "SELECT storage_cid, kind FROM identity_bindings WHERE identity_cid = ?",
                (identity_cid,),
            ).fetchone()
            if existing is not None:
                if str(existing["storage_cid"]) != storage_cid or str(existing["kind"]) != kind:
                    raise GraphHistoryConflictError(
                        f"identity {identity_cid!r} already bound to a different record"
                    )
                return
            with self._connection:
                self._connection.execute(
                    "INSERT INTO identity_bindings(identity_cid, storage_cid, kind) "
                    "VALUES(?,?,?)",
                    (identity_cid, storage_cid, kind),
                )

    def bind_operation(
        self,
        operation_id: str,
        identity_cid: str,
        storage_cid: str,
        kind: str,
    ) -> None:
        with self._lock:
            existing = self._connection.execute(
                "SELECT identity_cid, storage_cid, kind FROM history_operations "
                "WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["identity_cid"]) != identity_cid
                    or str(existing["storage_cid"]) != storage_cid
                    or str(existing["kind"]) != kind
                ):
                    raise GraphHistoryConflictError(
                        f"operation_id {operation_id!r} already bound to a different record"
                    )
                return
            with self._connection:
                self._connection.execute(
                    "INSERT INTO history_operations"
                    "(operation_id, identity_cid, storage_cid, kind) VALUES(?,?,?,?)",
                    (operation_id, identity_cid, storage_cid, kind),
                )


# ---------------------------------------------------------------------------
# Block store
# ---------------------------------------------------------------------------


class HistoryBlockStore:
    """Sealed history-record persistence over ``DurableCoordinationStore``."""

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store
        self._index = _HistoryIndex(store)
        self._rebuild_identity_index()

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    def close(self) -> None:
        self._index.close()

    def __enter__(self) -> "HistoryBlockStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _rebuild_identity_index(self) -> None:
        for path in sorted(self._store.blocks_dir.glob("*/*.json")):
            storage_cid = path.stem
            try:
                validate_transport_cid(storage_cid)
                raw = self._store.get(storage_cid)
            except (
                ArtifactNotFound,
                ArtifactIntegrityError,
                TypeError,
                ValueError,
                UnicodeDecodeError,
                json.JSONDecodeError,
            ):
                continue
            if not isinstance(raw, Mapping) or raw.get("schema") != STORED_HISTORY_SCHEMA:
                continue
            try:
                sealed = admit_history_record(raw)
                kind = _coerce_kind(sealed["kind"])
                identity_cid = identity_cid_from_history_payload(
                    kind, sealed["payload"], storage_cid=storage_cid
                )
                self._index.bind_identity(identity_cid, storage_cid, kind.value)
            except (GraphHistoryError, SemanticGovernorStoreContractError, ArtifactIntegrityError):
                continue

    def _rehash_storage_bytes(self, cid: str) -> bytes:
        try:
            data = self._store.get_bytes(cid)
        except ArtifactNotFound as exc:
            raise GraphHistoryNotFound(cid) from exc
        except ArtifactIntegrityError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        codec = validate_transport_cid(cid)
        if cid_for_bytes(data, codec) != cid:
            raise GraphHistoryIntegrityError(f"local bytes do not match {cid}")
        return data

    def has_identity(self, cid: str) -> bool:
        try:
            cid = validate_verified_cid(cid, "cid")
        except SemanticGovernorStoreContractError:
            return False
        if self._index.lookup_identity(cid) is not None:
            return True
        if self._index.lookup_storage(cid) is not None:
            return True
        return self._store.has(cid)

    def require_stored(self, cid: str, *, field: str) -> str:
        """Fail closed unless ``cid`` already resolves to stored bytes."""

        try:
            cid = validate_verified_cid(cid, field)
        except SemanticGovernorStoreContractError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        if self.has_identity(cid):
            return cid
        raise GraphHistoryAdmissionError(f"store-before-reference: {field}")

    def put_payload(
        self,
        kind: HistoryRecordKind | str,
        payload: Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> HistoryWriteResult:
        record_kind = _coerce_kind(kind)
        sealed = seal_history_record(record_kind, payload)
        storage_cid = cid_for_artifact(sealed)
        identity_cid = identity_cid_from_history_payload(
            record_kind, sealed["payload"], storage_cid=storage_cid
        )
        try:
            identity_cid = validate_verified_cid(identity_cid, "identity_cid")
            if expected_cid is not None:
                expected_cid = validate_verified_cid(expected_cid, "expected_cid")
            if operation_id is not None:
                operation_id = validate_operation_id(operation_id)
        except SemanticGovernorStoreContractError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        if expected_cid is not None and expected_cid != identity_cid:
            raise GraphHistoryIntegrityError(
                f"forged or mismatched history CID: computed {identity_cid}, "
                f"expected {expected_cid}"
            )
        if record_kind not in _KIT_OWNED_KINDS:
            payload_identity = identity_cid_from_history_payload(
                record_kind, sealed["payload"], storage_cid=storage_cid
            )
            if payload_identity != identity_cid:
                raise GraphHistoryIntegrityError(
                    f"payload identity CID {payload_identity} does not match {identity_cid}"
                )

        if operation_id is not None:
            prior_op = self._index.lookup_operation(operation_id)
            if prior_op is not None:
                prior_identity, prior_storage, prior_kind = prior_op
                if (
                    prior_identity != identity_cid
                    or prior_storage != storage_cid
                    or prior_kind != record_kind.value
                ):
                    raise GraphHistoryConflictError(
                        f"operation_id {operation_id!r} already bound to a different record"
                    )

        prior = self._index.lookup_identity(identity_cid)
        if prior is not None:
            prior_storage, prior_kind = prior
            if prior_storage != storage_cid or prior_kind != record_kind.value:
                raise GraphHistoryConflictError(
                    f"identity {identity_cid!r} already bound to a different record"
                )
            self.get_verified_record(identity_cid, expected_kind=record_kind)
            if operation_id is not None:
                self._index.bind_operation(
                    operation_id, identity_cid, storage_cid, record_kind.value
                )
            return HistoryWriteResult(
                identity_cid,
                storage_cid,
                record_kind,
                False,
                True,
                "unchanged",
            )

        try:
            local = self._store.put(
                sealed,
                expected_cid=storage_cid,
                codec="dag-json",
                replicate=False,
            )
        except ArtifactIntegrityError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc

        returned = str(local["cid"])
        if returned != storage_cid:
            raise GraphHistoryIntegrityError(
                f"store returned unexpected CID {returned}, expected {storage_cid}"
            )
        self._rehash_storage_bytes(storage_cid)
        self._index.bind_identity(identity_cid, storage_cid, record_kind.value)
        if operation_id is not None:
            self._index.bind_operation(
                operation_id, identity_cid, storage_cid, record_kind.value
            )
        created = bool(local.get("created", True))
        if replicate and self._store.backend is not None:
            try:
                remote = self._store.put(
                    sealed,
                    expected_cid=storage_cid,
                    codec="dag-json",
                    replicate=True,
                )
            except Exception:
                remote = None
            if remote is None or remote.get("cid") != storage_cid:
                return HistoryWriteResult(
                    identity_cid,
                    storage_cid,
                    record_kind,
                    created,
                    True,
                    "provider_failed",
                )
        reason = "stored" if created else "unchanged"
        if replicate and self._store.backend is None:
            reason = "provider_unavailable"
        return HistoryWriteResult(
            identity_cid,
            storage_cid,
            record_kind,
            created,
            True,
            reason,
        )

    def _resolve_storage_cid(self, cid: str) -> tuple[str, str | None]:
        try:
            cid = validate_verified_cid(cid, "cid")
        except SemanticGovernorStoreContractError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        bound = self._index.lookup_identity(cid)
        if bound is not None:
            return bound[0], bound[1]
        storage_bound = self._index.lookup_storage(cid)
        if storage_bound is not None:
            return cid, storage_bound[1]
        if self._store.has(cid):
            return cid, None
        raise GraphHistoryNotFound(cid)

    def get_verified_record(
        self,
        cid: str,
        *,
        expected_kind: Optional[HistoryRecordKind | str] = None,
    ) -> Mapping[str, Any]:
        """Load and re-verify a sealed history record by identity or storage CID."""

        storage_cid, indexed_kind = self._resolve_storage_cid(cid)
        self._rehash_storage_bytes(storage_cid)
        try:
            raw = self._store.get(storage_cid)
        except ArtifactNotFound as exc:
            raise GraphHistoryNotFound(cid) from exc
        except ArtifactIntegrityError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        if not isinstance(raw, Mapping):
            raise GraphHistoryIntegrityError(f"{storage_cid} did not decode to a mapping")
        sealed = admit_history_record(raw)
        recomputed = cid_for_artifact(sealed)
        if recomputed != storage_cid:
            raise GraphHistoryIntegrityError(
                f"forged sealed history record: recomputed {recomputed}, expected {storage_cid}"
            )
        kind = HistoryRecordKind(sealed["kind"])
        if indexed_kind is not None and indexed_kind != kind.value:
            raise GraphHistoryIntegrityError(
                f"index kind {indexed_kind} does not match stored {kind.value}"
            )
        if expected_kind is not None:
            wanted = _coerce_kind(expected_kind)
            if kind is not wanted:
                raise GraphHistoryIntegrityError(
                    f"wrong history kind: stored {kind.value}, expected {wanted.value}"
                )
        identity_cid = identity_cid_from_history_payload(
            kind, sealed["payload"], storage_cid=storage_cid
        )
        self._index.bind_identity(identity_cid, storage_cid, kind.value)
        return MappingProxyType(
            {
                "schema": sealed["schema"],
                "interface_id": sealed["interface_id"],
                "kind": sealed["kind"],
                "payload": MappingProxyType(dict(sealed["payload"])),
                "storage_cid": storage_cid,
                "identity_cid": identity_cid,
            }
        )


def _coordination_store(
    store: DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | HistoryBlockStore
    | "LogicalProgramGraphStore"
    | "ProgramTransitionLog",
) -> DurableCoordinationStore:
    if isinstance(store, DurableCoordinationStore):
        return store
    inner = getattr(store, "store", None)
    if isinstance(inner, DurableCoordinationStore):
        return inner
    blocks = getattr(store, "blocks", None)
    if isinstance(blocks, HistoryBlockStore):
        return blocks.store
    raise TypeError(
        "store must be a DurableCoordinationStore, history store, or verified facade"
    )


def history_block_store(
    store: DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | HistoryBlockStore
    | "LogicalProgramGraphStore"
    | "ProgramTransitionLog",
) -> HistoryBlockStore:
    if isinstance(store, HistoryBlockStore):
        return store
    blocks = getattr(store, "blocks", None)
    if isinstance(blocks, HistoryBlockStore):
        return blocks
    return HistoryBlockStore(_coordination_store(store))


def _decode_datasets_payload(kind: HistoryRecordKind, payload: Mapping[str, Any]) -> Any:
    body = dict(payload)
    try:
        if kind in {
            HistoryRecordKind.PROGRAM_GRAPH_NODE,
            HistoryRecordKind.PROGRAM_GRAPH_EDGE,
            HistoryRecordKind.PROGRAM_GRAPH_SNAPSHOT,
            HistoryRecordKind.PROGRAM_GRAPH_DELTA,
            HistoryRecordKind.CALLSITE_RECORD,
            HistoryRecordKind.FUNCTION_SYMBOL_RECORD,
            HistoryRecordKind.CONTRACT_STATE_RECORD,
            HistoryRecordKind.PROOF_OBLIGATION_GRAPH,
            HistoryRecordKind.STATIC_SUCCESSOR_SET,
            HistoryRecordKind.DYNAMIC_FRONTIER_RECORD,
        }:
            return decode_program_graph_record(body)
        if kind in {
            HistoryRecordKind.TRANSITION_QUERY,
            HistoryRecordKind.TRANSITION_CANDIDATE,
            HistoryRecordKind.TRANSITION_PREDICTION,
            HistoryRecordKind.TRANSITION_OBSERVATION,
            HistoryRecordKind.TRANSITION_ADMISSION,
            HistoryRecordKind.TRANSITION_RECEIPT,
        }:
            return decode_transition_record(body)
        if kind in {
            HistoryRecordKind.CANONICAL_PROGRAM_GRAPH,
            HistoryRecordKind.RAW_EXECUTION_STATE,
            HistoryRecordKind.SEMANTIC_WORLD_ROOT_IDENTITY,
        }:
            return decode_identity_record(body)
        if kind is HistoryRecordKind.PROGRAM_EVENT:
            schema = body.get("schema")
            if schema == ProgramEventIdentity.SCHEMA:
                return ProgramEventIdentity.from_dict(body)
            return decode_program_execution_record(body)
        if kind is HistoryRecordKind.EXECUTION_TRACE:
            schema = body.get("schema")
            if schema == ExecutionTraceIdentity.SCHEMA:
                return ExecutionTraceIdentity.from_dict(body)
            return decode_program_execution_record(body)
        if kind is HistoryRecordKind.EXECUTION_TRACE_SEGMENT:
            return decode_program_execution_record(body)
        if kind is HistoryRecordKind.GRAPH_HISTORY_ENTRY:
            return GraphHistoryEntry.from_payload(body)
        if kind is HistoryRecordKind.TRANSITION_LOG_ENTRY:
            return TransitionLogEntry.from_payload(body)
    except (
        ProgramGraphError,
        ProgramTransitionError,
        ProgramIdentityError,
        ProgramExecutionError,
        GraphHistoryError,
    ) as exc:
        raise GraphHistoryIntegrityError(str(exc)) from exc
    raise GraphHistoryIntegrityError(f"cannot decode history kind {kind.value}")


def _kind_for_record(record: Any) -> HistoryRecordKind:
    if isinstance(record, ProgramGraphNode):
        return HistoryRecordKind.PROGRAM_GRAPH_NODE
    if isinstance(record, ProgramGraphEdge):
        return HistoryRecordKind.PROGRAM_GRAPH_EDGE
    if isinstance(record, ProgramGraphSnapshot):
        return HistoryRecordKind.PROGRAM_GRAPH_SNAPSHOT
    if isinstance(record, ProgramGraphDelta):
        return HistoryRecordKind.PROGRAM_GRAPH_DELTA
    if isinstance(record, CallsiteRecord):
        return HistoryRecordKind.CALLSITE_RECORD
    if isinstance(record, FunctionSymbolRecord):
        return HistoryRecordKind.FUNCTION_SYMBOL_RECORD
    if isinstance(record, ContractStateRecord):
        return HistoryRecordKind.CONTRACT_STATE_RECORD
    if isinstance(record, ProofObligationGraph):
        return HistoryRecordKind.PROOF_OBLIGATION_GRAPH
    if isinstance(record, StaticSuccessorSet):
        return HistoryRecordKind.STATIC_SUCCESSOR_SET
    if isinstance(record, DynamicFrontierRecord):
        return HistoryRecordKind.DYNAMIC_FRONTIER_RECORD
    if isinstance(record, CanonicalProgramGraphIdentity):
        return HistoryRecordKind.CANONICAL_PROGRAM_GRAPH
    if isinstance(record, SemanticWorldRootIdentity):
        return HistoryRecordKind.SEMANTIC_WORLD_ROOT_IDENTITY
    if isinstance(record, (ProgramEventIdentity, ProgramExecutionEvent)):
        return HistoryRecordKind.PROGRAM_EVENT
    if isinstance(record, (ExecutionTraceIdentity, ProgramExecutionTrace)):
        return HistoryRecordKind.EXECUTION_TRACE
    if isinstance(record, ExecutionTraceSegment):
        return HistoryRecordKind.EXECUTION_TRACE_SEGMENT
    if isinstance(record, RawExecutionStateIdentity):
        return HistoryRecordKind.RAW_EXECUTION_STATE
    if isinstance(record, ProgramTransitionQuery):
        return HistoryRecordKind.TRANSITION_QUERY
    if isinstance(record, ProgramTransitionCandidate):
        return HistoryRecordKind.TRANSITION_CANDIDATE
    if isinstance(record, ProgramTransitionPrediction):
        return HistoryRecordKind.TRANSITION_PREDICTION
    if isinstance(record, ProgramTransitionObservation):
        return HistoryRecordKind.TRANSITION_OBSERVATION
    if isinstance(record, ProgramTransitionAdmission):
        return HistoryRecordKind.TRANSITION_ADMISSION
    if isinstance(record, ProgramTransitionReceipt):
        return HistoryRecordKind.TRANSITION_RECEIPT
    if isinstance(record, GraphHistoryEntry):
        return HistoryRecordKind.GRAPH_HISTORY_ENTRY
    if isinstance(record, TransitionLogEntry):
        return HistoryRecordKind.TRANSITION_LOG_ENTRY
    raise GraphHistoryAdmissionError(
        f"unsupported history record type {type(record).__name__}"
    )


# ---------------------------------------------------------------------------
# Logical program graph store
# ---------------------------------------------------------------------------


class LogicalProgramGraphStore:
    """ProgramGraphHistory@1 persistence for snapshots, deltas, and traces."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | HistoryBlockStore,
    ) -> None:
        self._blocks = history_block_store(store)

    @property
    def blocks(self) -> HistoryBlockStore:
        return self._blocks

    @property
    def store(self) -> DurableCoordinationStore:
        return self._blocks.store

    def close(self) -> None:
        self._blocks.close()

    def __enter__(self) -> "LogicalProgramGraphStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def put_record(
        self,
        record: Any,
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> HistoryWriteResult:
        kind = _kind_for_record(record)
        self._require_record_references(record, kind)
        payload = (
            record.to_payload()
            if kind is HistoryRecordKind.GRAPH_HISTORY_ENTRY
            else _as_mapping_payload(record)
        )
        identity = None
        if kind not in _KIT_OWNED_KINDS:
            identity = _record_cid(record)
        return self._blocks.put_payload(
            kind,
            payload,
            expected_cid=expected_cid or identity,
            operation_id=operation_id,
            replicate=replicate,
        )

    def put_opaque_subroot(
        self,
        label: str,
        *,
        operation_id: str | None = None,
    ) -> HistoryWriteResult:
        if type(label) is not str or not label:
            raise GraphHistoryAdmissionError("opaque subroot label must be a nonempty string")
        return self._blocks.put_payload(
            HistoryRecordKind.OPAQUE_SUBROOT,
            {"schema": OPAQUE_SUBROOT_SCHEMA, "label": label},
            operation_id=operation_id,
        )

    def get_verified_record(
        self,
        cid: str,
        *,
        expected_kind: HistoryRecordKind | str | None = None,
    ) -> Any:
        artifact = self._blocks.get_verified_record(cid, expected_kind=expected_kind)
        kind = HistoryRecordKind(artifact["kind"])
        return _decode_datasets_payload(kind, dict(artifact["payload"]))

    def _require_record_references(self, record: Any, kind: HistoryRecordKind) -> None:
        cid = None if kind in _KIT_OWNED_KINDS else _record_cid(record)
        if kind is HistoryRecordKind.PROGRAM_GRAPH_EDGE:
            self._blocks.require_stored(record.source_node_cid, field="source_node_cid")
            self._blocks.require_stored(record.target_node_cid, field="target_node_cid")
        if kind is HistoryRecordKind.PROGRAM_GRAPH_NODE and record.record_cid is not None:
            self._blocks.require_stored(record.record_cid, field="record_cid")
        if kind is HistoryRecordKind.PROGRAM_GRAPH_SNAPSHOT:
            for field_name in (
                "node_cids",
                "edge_cids",
                "callsite_cids",
                "function_symbol_cids",
                "contract_state_cids",
                "proof_obligation_graph_cids",
                "successor_set_cids",
                "frontier_cids",
                "retained_subroot_cids",
            ):
                for index, ref in enumerate(getattr(record, field_name)):
                    self._blocks.require_stored(ref, field=f"{field_name}[{index}]")
        if kind is HistoryRecordKind.PROGRAM_EVENT:
            predecessor = getattr(record, "predecessor_event_cid", None)
            if predecessor is not None:
                self._blocks.require_stored(predecessor, field="predecessor_event_cid")
        if kind is HistoryRecordKind.EXECUTION_TRACE:
            for index, event_cid in enumerate(record.event_cids):
                self._blocks.require_stored(event_cid, field=f"event_cids[{index}]")
            for index, segment_cid in enumerate(getattr(record, "segment_cids", ())):
                self._blocks.require_stored(segment_cid, field=f"segment_cids[{index}]")
            for index, state_cid in enumerate(
                getattr(record, "raw_execution_state_cids", ())
            ):
                self._blocks.require_stored(
                    state_cid, field=f"raw_execution_state_cids[{index}]"
                )
            parent = getattr(record, "parent_trace_cid", None)
            if parent is not None:
                self._blocks.require_stored(parent, field="parent_trace_cid")
                if parent == cid:
                    raise GraphHistoryAdmissionError(
                        "physical IPLD block graph must be acyclic"
                    )
        if kind is HistoryRecordKind.EXECUTION_TRACE_SEGMENT:
            self._blocks.require_stored(record.parent_trace_cid, field="parent_trace_cid")
            if record.parent_trace_cid == cid:
                raise GraphHistoryAdmissionError(
                    "physical IPLD block graph must be acyclic"
                )
            for index, event_cid in enumerate(record.event_cids):
                self._blocks.require_stored(event_cid, field=f"event_cids[{index}]")
        if kind is HistoryRecordKind.SEMANTIC_WORLD_ROOT_IDENTITY:
            for field_name in (
                "domain_state_cid",
                "canonical_program_graph_cid",
                "program_graph_snapshot_cid",
                "semantic_object_index_cid",
                "environment_binding_set_cid",
                "policy_cid",
                "analysis_limitation_index_cid",
            ):
                self._blocks.require_stored(getattr(record, field_name), field=field_name)
        if kind is HistoryRecordKind.PROGRAM_GRAPH_DELTA:
            self._blocks.require_stored(
                record.previous_snapshot_cid, field="previous_snapshot_cid"
            )
            for index, node_cid in enumerate(record.added_node_cids):
                self._blocks.require_stored(node_cid, field=f"added_node_cids[{index}]")
            for index, edge_cid in enumerate(record.added_edge_cids):
                self._blocks.require_stored(edge_cid, field=f"added_edge_cids[{index}]")
            for index, node_cid in enumerate(record.retained_subroot_cids):
                self._blocks.require_stored(
                    node_cid, field=f"retained_subroot_cids[{index}]"
                )

    def _put_constituent(
        self,
        record: Any,
        *,
        operation_id: str | None = None,
    ) -> HistoryWriteResult:
        return self.put_record(record, operation_id=operation_id)

    def append_program_graph_snapshot(
        self,
        snapshot: ProgramGraphSnapshot | None = None,
        *,
        nodes: Sequence[ProgramGraphNode],
        edges: Sequence[ProgramGraphEdge],
        environment_binding_set_cid: str | None = None,
        sealed_binding_cid: str | None = None,
        callsites: Sequence[CallsiteRecord] = (),
        function_symbols: Sequence[FunctionSymbolRecord] = (),
        contract_states: Sequence[ContractStateRecord] = (),
        proof_obligation_graphs: Sequence[ProofObligationGraph] = (),
        successor_sets: Sequence[StaticSuccessorSet] = (),
        frontiers: Sequence[DynamicFrontierRecord] = (),
        retained_subroot_cids: Sequence[str] = (),
        unavailable_dimensions: Sequence[str] = (),
        previous_snapshot: ProgramGraphSnapshot | str | None = None,
        previous_entry_cid: str | None = None,
        trace_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> HistoryWriteResult:
        """Persist constituents then the snapshot; logical cycles stay queryable."""

        specialized_groups: tuple[tuple[str, Sequence[Any]], ...] = (
            ("callsites", callsites),
            ("function_symbols", function_symbols),
            ("contract_states", contract_states),
            ("proof_obligation_graphs", proof_obligation_graphs),
            ("successor_sets", successor_sets),
            ("frontiers", frontiers),
        )
        for _name, group in specialized_groups:
            for item in group:
                self._put_constituent(item)
        for node in nodes:
            self._put_constituent(node)
        for edge in edges:
            self._put_constituent(edge)

        if snapshot is None:
            if environment_binding_set_cid is None or sealed_binding_cid is None:
                raise GraphHistoryAdmissionError(
                    "snapshot assembly requires environment_binding_set_cid and "
                    "sealed_binding_cid"
                )
            try:
                snapshot = assemble_program_graph_snapshot(
                    nodes=nodes,
                    edges=edges,
                    environment_binding_set_cid=environment_binding_set_cid,
                    sealed_binding_cid=sealed_binding_cid,
                    callsites=callsites,
                    function_symbols=function_symbols,
                    contract_states=contract_states,
                    proof_obligation_graphs=proof_obligation_graphs,
                    successor_sets=successor_sets,
                    frontiers=frontiers,
                    retained_subroot_cids=retained_subroot_cids,
                    unavailable_dimensions=unavailable_dimensions,
                )
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        else:
            if not isinstance(snapshot, ProgramGraphSnapshot):
                raise GraphHistoryAdmissionError(
                    "snapshot must be a ProgramGraphSnapshot"
                )
            try:
                verify_program_graph_catalog(
                    snapshot,
                    nodes=nodes,
                    edges=edges,
                    callsites=callsites,
                    function_symbols=function_symbols,
                    contract_states=contract_states,
                    proof_obligation_graphs=proof_obligation_graphs,
                    successor_sets=successor_sets,
                    frontiers=frontiers,
                )
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc

        for field_name in (
            "node_cids",
            "edge_cids",
            "callsite_cids",
            "function_symbol_cids",
            "contract_state_cids",
            "proof_obligation_graph_cids",
            "successor_set_cids",
            "frontier_cids",
            "retained_subroot_cids",
        ):
            for index, cid in enumerate(getattr(snapshot, field_name)):
                self._blocks.require_stored(cid, field=f"{field_name}[{index}]")

        canonical = CanonicalProgramGraphIdentity(
            language=snapshot.language,
            graph_kind=snapshot.graph_kind,
            node_cids=snapshot.node_cids,
            edge_cids=snapshot.edge_cids,
            environment_binding_set_cid=snapshot.environment_binding_set_cid,
            unavailable_dimensions=snapshot.unavailable_dimensions,
        )
        if canonical.canonical_program_graph_cid != snapshot.canonical_program_graph_cid:
            raise GraphHistoryIntegrityError(
                "canonical_program_graph_cid does not rehash snapshot constituents"
            )
        self.put_record(
            canonical, expected_cid=canonical.canonical_program_graph_cid
        )

        snapshot_result = self.put_record(
            snapshot,
            expected_cid=snapshot.program_graph_snapshot_cid,
            operation_id=operation_id,
            replicate=replicate,
        )

        previous_record: ProgramGraphSnapshot | None = None
        if isinstance(previous_snapshot, ProgramGraphSnapshot):
            previous_record = previous_snapshot
            self._blocks.require_stored(
                previous_record.program_graph_snapshot_cid,
                field="previous_snapshot_cid",
            )
        elif type(previous_snapshot) is str:
            previous_record = self.get_verified_snapshot(previous_snapshot)

        delta_cid = None
        if previous_record is not None:
            try:
                delta = delta_between_snapshots(previous_record, snapshot)
                apply_program_graph_delta(previous_record, delta)
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
            for index, node_cid in enumerate(delta.retained_subroot_cids):
                self._blocks.require_stored(
                    node_cid, field=f"retained_subroot_cids[{index}]"
                )
            delta_result = self._put_constituent(delta)
            delta_cid = delta_result.cid

        if trace_cid is not None:
            self._blocks.require_stored(trace_cid, field="trace_cid")

        sequence = 1
        previous_entry = _optional_cid(previous_entry_cid, "previous_entry_cid")
        if previous_entry is not None:
            prior_entry = self.get_verified_history_entry(previous_entry)
            sequence = prior_entry.sequence + 1
        entry = GraphHistoryEntry(
            snapshot_cid=snapshot.program_graph_snapshot_cid,
            sequence=sequence,
            previous_entry_cid=previous_entry,
            delta_cid=delta_cid,
            trace_cid=trace_cid,
        )
        entry_result = self._blocks.put_payload(
            HistoryRecordKind.GRAPH_HISTORY_ENTRY, entry.to_payload()
        )

        catalog: dict[str, Mapping[str, Any]] = {
            snapshot.program_graph_snapshot_cid: snapshot.identity_payload(),
            canonical.canonical_program_graph_cid: canonical.identity_payload(),
        }
        for node in nodes:
            catalog[node.program_graph_node_cid] = node.identity_payload()
        for edge in edges:
            catalog[edge.program_graph_edge_cid] = edge.identity_payload()
        for _name, group in specialized_groups:
            for item in group:
                catalog[_record_cid(item)] = item.identity_payload()
        try:
            assert_physical_dag_acyclic(catalog)
        except ProgramGraphError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        catalog[entry_result.cid] = entry.to_payload()
        if delta_cid is not None:
            delta_record = self.get_verified_delta(delta_cid)
            catalog[delta_cid] = delta_record.identity_payload()
        assert_history_physical_dag_acyclic(catalog)

        return HistoryWriteResult(
            snapshot_result.cid,
            snapshot_result.storage_cid,
            snapshot_result.kind,
            snapshot_result.created,
            snapshot_result.local_durable,
            snapshot_result.reason_code,
            delta_cid=delta_cid,
            history_entry_cid=entry_result.cid,
        )

    def get_verified_snapshot(self, cid: str) -> ProgramGraphSnapshot:
        record = self.get_verified_record(
            cid, expected_kind=HistoryRecordKind.PROGRAM_GRAPH_SNAPSHOT
        )
        if not isinstance(record, ProgramGraphSnapshot):
            raise GraphHistoryIntegrityError("stored record is not a program-graph snapshot")
        return record

    def get_verified_delta(self, cid: str) -> ProgramGraphDelta:
        record = self.get_verified_record(
            cid, expected_kind=HistoryRecordKind.PROGRAM_GRAPH_DELTA
        )
        if not isinstance(record, ProgramGraphDelta):
            raise GraphHistoryIntegrityError("stored record is not a program-graph delta")
        return record

    def get_verified_node(self, cid: str) -> ProgramGraphNode:
        record = self.get_verified_record(
            cid, expected_kind=HistoryRecordKind.PROGRAM_GRAPH_NODE
        )
        if not isinstance(record, ProgramGraphNode):
            raise GraphHistoryIntegrityError("stored record is not a program-graph node")
        return record

    def get_verified_edge(self, cid: str) -> ProgramGraphEdge:
        record = self.get_verified_record(
            cid, expected_kind=HistoryRecordKind.PROGRAM_GRAPH_EDGE
        )
        if not isinstance(record, ProgramGraphEdge):
            raise GraphHistoryIntegrityError("stored record is not a program-graph edge")
        return record

    def get_verified_history_entry(self, cid: str) -> GraphHistoryEntry:
        record = self.get_verified_record(
            cid, expected_kind=HistoryRecordKind.GRAPH_HISTORY_ENTRY
        )
        if not isinstance(record, GraphHistoryEntry):
            raise GraphHistoryIntegrityError("stored record is not a graph-history entry")
        return record

    def query_logical_cycles(
        self, snapshot: ProgramGraphSnapshot | str
    ) -> tuple[tuple[str, ...], ...]:
        """Return directed logical-cycle edge-CID tuples for a stored snapshot."""

        if not isinstance(snapshot, ProgramGraphSnapshot):
            snapshot = self.get_verified_snapshot(snapshot)
        edges = [self.get_verified_edge(cid) for cid in snapshot.edge_cids]
        return directed_logical_cycles(edges)

    def physical_catalog_for_snapshot(
        self, snapshot: ProgramGraphSnapshot | str
    ) -> dict[str, dict[str, Any]]:
        if not isinstance(snapshot, ProgramGraphSnapshot):
            snapshot = self.get_verified_snapshot(snapshot)
        catalog: dict[str, dict[str, Any]] = {
            snapshot.program_graph_snapshot_cid: snapshot.identity_payload()
        }
        for cid in snapshot.node_cids:
            catalog[cid] = self.get_verified_node(cid).identity_payload()
        for cid in snapshot.edge_cids:
            catalog[cid] = self.get_verified_edge(cid).identity_payload()
        return catalog

    def put_event(
        self,
        event: ProgramEventIdentity | ProgramExecutionEvent,
        *,
        operation_id: str | None = None,
    ) -> HistoryWriteResult:
        return self._put_constituent(event, operation_id=operation_id)

    def put_trace(
        self,
        trace: ExecutionTraceIdentity | ProgramExecutionTrace,
        *,
        operation_id: str | None = None,
    ) -> HistoryWriteResult:
        return self._put_constituent(trace, operation_id=operation_id)

    def put_trace_segment(
        self,
        segment: ExecutionTraceSegment,
        *,
        operation_id: str | None = None,
    ) -> HistoryWriteResult:
        return self._put_constituent(segment, operation_id=operation_id)

    def put_raw_execution_state(
        self,
        state: RawExecutionStateIdentity,
        *,
        operation_id: str | None = None,
    ) -> HistoryWriteResult:
        return self._put_constituent(state, operation_id=operation_id)


# ---------------------------------------------------------------------------
# Transition log
# ---------------------------------------------------------------------------


class ProgramTransitionLog:
    """Append-only transition query/prediction/observation/admission/receipt log."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | HistoryBlockStore
        | LogicalProgramGraphStore,
    ) -> None:
        self._blocks = history_block_store(store)

    @property
    def blocks(self) -> HistoryBlockStore:
        return self._blocks

    @property
    def store(self) -> DurableCoordinationStore:
        return self._blocks.store

    def close(self) -> None:
        self._blocks.close()

    def __enter__(self) -> "ProgramTransitionLog":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _put(
        self,
        record: Any,
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> HistoryWriteResult:
        kind = _kind_for_record(record)
        payload = _as_mapping_payload(record)
        return self._blocks.put_payload(
            kind,
            payload,
            expected_cid=expected_cid or _record_cid(record),
            operation_id=operation_id,
            replicate=replicate,
        )

    def put_query(
        self, query: ProgramTransitionQuery, *, operation_id: str | None = None
    ) -> HistoryWriteResult:
        if not isinstance(query, ProgramTransitionQuery):
            raise GraphHistoryAdmissionError("query must be a ProgramTransitionQuery")
        return self._put(query, operation_id=operation_id)

    def put_candidate(
        self,
        candidate: ProgramTransitionCandidate,
        *,
        operation_id: str | None = None,
    ) -> HistoryWriteResult:
        if not isinstance(candidate, ProgramTransitionCandidate):
            raise GraphHistoryAdmissionError(
                "candidate must be a ProgramTransitionCandidate"
            )
        self._blocks.require_stored(candidate.query_cid, field="query_cid")
        return self._put(candidate, operation_id=operation_id)

    def put_prediction(
        self,
        prediction: ProgramTransitionPrediction,
        *,
        operation_id: str | None = None,
    ) -> HistoryWriteResult:
        if not isinstance(prediction, ProgramTransitionPrediction):
            raise GraphHistoryAdmissionError(
                "prediction must be a ProgramTransitionPrediction"
            )
        if not prediction.proposal_only:
            raise GraphHistoryAdmissionError("predictions are proposal-only")
        self._blocks.require_stored(prediction.query_cid, field="query_cid")
        for index, candidate_cid in enumerate(prediction.candidate_cids):
            self._blocks.require_stored(candidate_cid, field=f"candidate_cids[{index}]")
        return self._put(prediction, operation_id=operation_id)

    def put_observation(
        self,
        observation: ProgramTransitionObservation,
        *,
        operation_id: str | None = None,
    ) -> HistoryWriteResult:
        if not isinstance(observation, ProgramTransitionObservation):
            raise GraphHistoryAdmissionError(
                "observation must be a ProgramTransitionObservation"
            )
        if observation.proposal_only:
            raise GraphHistoryAdmissionError("observations cannot be proposal-only")
        self._blocks.require_stored(observation.query_cid, field="query_cid")
        return self._put(observation, operation_id=operation_id)

    def put_admission(
        self,
        admission: ProgramTransitionAdmission,
        *,
        operation_id: str | None = None,
    ) -> HistoryWriteResult:
        if not isinstance(admission, ProgramTransitionAdmission):
            raise GraphHistoryAdmissionError(
                "admission must be a ProgramTransitionAdmission"
            )
        self._blocks.require_stored(admission.query_cid, field="query_cid")
        if admission.prediction_cid is not None:
            self._blocks.require_stored(admission.prediction_cid, field="prediction_cid")
            prediction = self.get_verified_prediction(admission.prediction_cid)
            if prediction.SCHEMA == PROGRAM_TRANSITION_OBSERVATION_SCHEMA:
                raise GraphHistoryAdmissionError(
                    "predictions cannot decode as observations"
                )
        if admission.observation_cid is not None:
            self._blocks.require_stored(
                admission.observation_cid, field="observation_cid"
            )
            observation = self.get_verified_observation(admission.observation_cid)
            if observation.SCHEMA == PROGRAM_TRANSITION_PREDICTION_SCHEMA:
                raise GraphHistoryAdmissionError(
                    "predictions cannot decode as observations"
                )
        return self._put(admission, operation_id=operation_id)

    def append_transition_receipt(
        self,
        receipt: ProgramTransitionReceipt | None = None,
        *,
        query: ProgramTransitionQuery,
        admission: ProgramTransitionAdmission,
        prediction: ProgramTransitionPrediction | None = None,
        observation: ProgramTransitionObservation | None = None,
        candidates: Sequence[ProgramTransitionCandidate] = (),
        previous_entry_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> HistoryWriteResult:
        """Persist a closed query/prediction/observation/admission bundle."""

        self.put_query(query)
        for candidate in candidates:
            self.put_candidate(candidate)
        if prediction is not None:
            self.put_prediction(prediction)
        if observation is not None:
            self.put_observation(observation)
        self.put_admission(admission)
        if receipt is None:
            try:
                receipt = issue_transition_receipt(
                    query,
                    admission,
                    prediction=prediction,
                    observation=observation,
                )
            except ProgramTransitionError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        if not isinstance(receipt, ProgramTransitionReceipt):
            raise GraphHistoryAdmissionError(
                "receipt must be a ProgramTransitionReceipt"
            )
        if receipt.prediction_authoritative:
            raise GraphHistoryAdmissionError(
                "receipts cannot treat predictions as authoritative"
            )
        if receipt.query_cid != query.query_cid:
            raise GraphHistoryAdmissionError("receipt is not bound to the supplied query")
        if receipt.admission_cid != admission.admission_cid:
            raise GraphHistoryAdmissionError(
                "receipt is not bound to the supplied admission"
            )
        if prediction is not None and receipt.prediction_cid not in {
            None,
            prediction.prediction_cid,
        }:
            raise GraphHistoryAdmissionError("receipt prediction does not match prediction")
        if observation is not None and receipt.observation_cid not in {
            None,
            observation.observation_cid,
        }:
            raise GraphHistoryAdmissionError(
                "receipt observation does not match observation"
            )
        if receipt.prediction_cid is not None:
            stored_prediction = self.get_verified_prediction(receipt.prediction_cid)
            try:
                decode_transition_observation(stored_prediction.to_dict())
            except ProgramTransitionError:
                pass
            else:
                raise GraphHistoryAdmissionError(
                    "predictions cannot decode as observations"
                )
        if receipt.observation_cid is not None:
            stored_observation = self.get_verified_observation(receipt.observation_cid)
            if stored_observation.SCHEMA != PROGRAM_TRANSITION_OBSERVATION_SCHEMA:
                raise GraphHistoryAdmissionError(
                    "predictions cannot decode as observations"
                )

        result = self._put(
            receipt, operation_id=operation_id, replicate=replicate
        )
        sequence = 1
        previous_entry = _optional_cid(previous_entry_cid, "previous_entry_cid")
        if previous_entry is not None:
            prior_entry = self.get_verified_log_entry(previous_entry)
            sequence = prior_entry.sequence + 1
        entry = TransitionLogEntry(
            receipt_cid=receipt.receipt_cid,
            query_cid=receipt.query_cid,
            admission_cid=receipt.admission_cid,
            verdict=str(receipt.verdict),
            sequence=sequence,
            previous_entry_cid=previous_entry,
            prediction_cid=receipt.prediction_cid,
            observation_cid=receipt.observation_cid,
        )
        log_result = self._blocks.put_payload(
            HistoryRecordKind.TRANSITION_LOG_ENTRY, entry.to_payload()
        )
        catalog = {
            query.query_cid: query.identity_payload(),
            admission.admission_cid: admission.identity_payload(),
            receipt.receipt_cid: receipt.identity_payload(),
            log_result.cid: entry.to_payload(),
        }
        if prediction is not None:
            catalog[prediction.prediction_cid] = prediction.identity_payload()
        if observation is not None:
            catalog[observation.observation_cid] = observation.identity_payload()
        assert_history_physical_dag_acyclic(catalog)
        return HistoryWriteResult(
            result.cid,
            result.storage_cid,
            result.kind,
            result.created,
            result.local_durable,
            result.reason_code,
            log_entry_cid=log_result.cid,
        )

    def get_verified_query(self, cid: str) -> ProgramTransitionQuery:
        record = _decode_datasets_payload(
            HistoryRecordKind.TRANSITION_QUERY,
            dict(
                self._blocks.get_verified_record(
                    cid, expected_kind=HistoryRecordKind.TRANSITION_QUERY
                )["payload"]
            ),
        )
        if not isinstance(record, ProgramTransitionQuery):
            raise GraphHistoryIntegrityError("stored record is not a transition query")
        return record

    def get_verified_prediction(self, cid: str) -> ProgramTransitionPrediction:
        artifact = self._blocks.get_verified_record(
            cid, expected_kind=HistoryRecordKind.TRANSITION_PREDICTION
        )
        record = _decode_datasets_payload(
            HistoryRecordKind.TRANSITION_PREDICTION, dict(artifact["payload"])
        )
        if not isinstance(record, ProgramTransitionPrediction):
            raise GraphHistoryIntegrityError(
                "stored record is not a transition prediction"
            )
        if record.SCHEMA != PROGRAM_TRANSITION_PREDICTION_SCHEMA:
            raise GraphHistoryIntegrityError(
                "predictions cannot decode as observations"
            )
        return record

    def get_verified_observation(self, cid: str) -> ProgramTransitionObservation:
        artifact = self._blocks.get_verified_record(
            cid, expected_kind=HistoryRecordKind.TRANSITION_OBSERVATION
        )
        payload = dict(artifact["payload"])
        try:
            record = decode_transition_observation(payload)
        except ProgramTransitionError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        if record.SCHEMA != PROGRAM_TRANSITION_OBSERVATION_SCHEMA:
            raise GraphHistoryIntegrityError(
                "predictions cannot decode as observations"
            )
        return record

    def get_verified_admission(self, cid: str) -> ProgramTransitionAdmission:
        record = _decode_datasets_payload(
            HistoryRecordKind.TRANSITION_ADMISSION,
            dict(
                self._blocks.get_verified_record(
                    cid, expected_kind=HistoryRecordKind.TRANSITION_ADMISSION
                )["payload"]
            ),
        )
        if not isinstance(record, ProgramTransitionAdmission):
            raise GraphHistoryIntegrityError("stored record is not a transition admission")
        return record

    def get_verified_receipt(self, cid: str) -> ProgramTransitionReceipt:
        record = _decode_datasets_payload(
            HistoryRecordKind.TRANSITION_RECEIPT,
            dict(
                self._blocks.get_verified_record(
                    cid, expected_kind=HistoryRecordKind.TRANSITION_RECEIPT
                )["payload"]
            ),
        )
        if not isinstance(record, ProgramTransitionReceipt):
            raise GraphHistoryIntegrityError("stored record is not a transition receipt")
        return record

    def get_verified_log_entry(self, cid: str) -> TransitionLogEntry:
        record = _decode_datasets_payload(
            HistoryRecordKind.TRANSITION_LOG_ENTRY,
            dict(
                self._blocks.get_verified_record(
                    cid, expected_kind=HistoryRecordKind.TRANSITION_LOG_ENTRY
                )["payload"]
            ),
        )
        if not isinstance(record, TransitionLogEntry):
            raise GraphHistoryIntegrityError("stored record is not a transition-log entry")
        return record


def append_program_graph_snapshot(
    store: LogicalProgramGraphStore
    | DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | HistoryBlockStore,
    snapshot: ProgramGraphSnapshot | None = None,
    **fields: Any,
) -> HistoryWriteResult:
    """Persist one immutable program-graph snapshot and optional delta."""

    graph_store = (
        store if isinstance(store, LogicalProgramGraphStore) else LogicalProgramGraphStore(store)
    )
    return graph_store.append_program_graph_snapshot(snapshot, **fields)


def append_transition_receipt(
    store: ProgramTransitionLog
    | LogicalProgramGraphStore
    | DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | HistoryBlockStore,
    receipt: ProgramTransitionReceipt | None = None,
    **fields: Any,
) -> HistoryWriteResult:
    """Persist one immutable transition receipt and log entry."""

    log = store if isinstance(store, ProgramTransitionLog) else ProgramTransitionLog(store)
    return log.append_transition_receipt(receipt, **fields)


__all__ = [
    "GRAPH_HISTORY_ENTRY_INTERFACE",
    "GRAPH_HISTORY_ENTRY_SCHEMA",
    "HISTORY_SCHEMA_VERSION",
    "MAX_HISTORY_BYTES",
    "PROGRAM_GRAPH_HISTORY_INTERFACE",
    "STORED_HISTORY_INTERFACE",
    "STORED_HISTORY_SCHEMA",
    "TRANSITION_LOG_ENTRY_INTERFACE",
    "TRANSITION_LOG_ENTRY_SCHEMA",
    "GraphHistoryAdmissionError",
    "GraphHistoryConflictError",
    "GraphHistoryEntry",
    "GraphHistoryError",
    "GraphHistoryIntegrityError",
    "GraphHistoryNotFound",
    "HistoryBlockStore",
    "HistoryRecordKind",
    "HistoryWriteResult",
    "LogicalProgramGraphStore",
    "ProgramTransitionLog",
    "TransitionLogEntry",
    "admit_history_record",
    "append_program_graph_snapshot",
    "append_transition_receipt",
    "assert_history_physical_dag_acyclic",
    "history_block_store",
    "seal_history_record",
]
