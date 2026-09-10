"""Immutable logical-graph snapshots, traces, and transition logs.

``LogicalProgramGraphStore``, ``ProgramTransitionLog``, and
``SemanticWorldSnapshotStore`` implement ``ProgramGraphHistory@1``.  They
persist datasets graph/transition/trace records through kit CID verification.
They do not accept semantics, mint datasets identity, decide prediction truth,
or publish a mutable current world root (SAWM-014).

Authority rules (normative, fail-closed):

* Physical IPLD/Merkle catalogs remain acyclic.  Logical cycles (mutual
  recursion, cyclic imports, CFG/state loops) are immutable node/edge records
  and stay queryable.
* Every parent record is stored only after each referenced graph/transition/
  trace identity is already durable (store-before-reference).
* Predictions and observations are disjoint kinds.  A prediction cannot be
  read as an observation or as an admitted receipt.
* Repeated states keep distinct event-history identities.
* Kit persists; datasets defines meaning.  This module never treats storage
  success as semantic admission.
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
    ExecutionTrace,
    ExecutionTraceSegment,
    ProgramEvent,
    ProgramExecutionError,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    CallsiteRecord,
    ContractStateRecord,
    DynamicFrontierRecord,
    FunctionSymbolRecord,
    ProgramGraphDelta,
    ProgramGraphEdge,
    ProgramGraphError,
    ProgramGraphIndexManifest,
    ProgramGraphNode,
    ProgramGraphSnapshot,
    ProofObligationGraph,
    StaticSuccessorSet,
    apply_program_graph_delta,
    assert_physical_dag_acyclic,
    decode_program_graph_record,
    delta_between_snapshots,
    directed_logical_cycles,
    verify_program_graph_catalog,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    CanonicalProgramGraphIdentity,
    ProgramIdentityError,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
    ProgramTransitionAdmission,
    ProgramTransitionError,
    ProgramTransitionObservation,
    ProgramTransitionPrediction,
    ProgramTransitionQuery,
    ProgramTransitionReceipt,
    decode_transition_observation,
    decode_transition_record,
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


PROGRAM_GRAPH_HISTORY_INTERFACE: Final[str] = "ProgramGraphHistory@1"
GRAPH_HISTORY_RECORD_INTERFACE: Final[str] = "ProgramGraphHistoryRecord@1"
GRAPH_HISTORY_RECORD_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.graph-history-record@1"
)
GRAPH_HISTORY_ENTRY_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.graph-history-entry@1"
)
TRANSITION_LOG_ENTRY_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.transition-log-entry@1"
)
WORLD_SNAPSHOT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-snapshot@1"
)
OPAQUE_SUBROOT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.opaque-subroot@1"
)
GRAPH_HISTORY_RECORD_SCHEMA_VERSION: Final[int] = 1
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1

_OPS_DB_NAME: Final[str] = "semantic_world_graph_history_index.sqlite3"
_SEALED_FIELDS: Final[frozenset[str]] = frozenset(
    ("schema", "interface_id", "kind", "payload")
)

# Parent-record CID fields that must already be durable.  Leaf content hashes
# (source_cid, declaration_cid, policy_cid, model_cid, …) are not graph-history
# identities and are not required here.
STORE_BEFORE_REFERENCE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "added_edge_cids",
        "added_node_cids",
        "admission_cid",
        "callsite_cids",
        "contract_state_cids",
        "delta_cid",
        "edge_cids",
        "end_event_cid",
        "event_cids",
        "event_history_cids",
        "execution_trace_cids",
        "frontier_cids",
        "function_symbol_cids",
        "graph_history_entry_cid",
        "node_cids",
        "observation_cid",
        "obligation_edge_cids",
        "obligation_node_cids",
        "parent_trace_cid",
        "predecessor_event_cid",
        "prediction_cid",
        "previous_entry_cid",
        "previous_manifest_cid",
        "previous_snapshot_cid",
        "program_graph_snapshot_cid",
        "subroot_cids",
        "proof_obligation_graph_cids",
        "query_cid",
        "receipt_cid",
        "record_cid",
        "removed_edge_cids",
        "removed_node_cids",
        "retained_subroot_cids",
        "root_obligation_cid",
        "segment_cids",
        "snapshot_cid",
        "source_node_cid",
        "start_event_cid",
        "subject_node_cid",
        "successor_edge_cids",
        "successor_node_cids",
        "successor_set_cids",
        "target_node_cid",
        "transition_log_entry_cid",
        "transition_receipt_cids",
        "unresolved_edge_cids",
        "unresolved_node_cids",
        "world_snapshot_cid",
    }
)


class GraphHistoryError(ValueError):
    """Base error for immutable graph-history admission or retrieval."""


class GraphHistoryAdmissionError(GraphHistoryError):
    """Raised when a write is rejected by closed admission policy."""


class GraphHistoryIntegrityError(GraphHistoryError):
    """Raised when bytes, CID, kind, or sealed shape do not verify."""


class GraphHistoryNotFound(GraphHistoryError, KeyError):
    """Raised when no verified history block exists for a CID."""


class GraphHistoryConflictError(GraphHistoryError):
    """Raised when an identity or operation_id is rebound to different bytes."""


class GraphHistoryKind(str, Enum):
    """Closed taxonomy of graph-history storage kinds."""

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
    PROGRAM_GRAPH_INDEX_MANIFEST = "program_graph_index_manifest"
    CANONICAL_PROGRAM_GRAPH = "canonical_program_graph"
    PROGRAM_EVENT = "program_event"
    EXECUTION_TRACE_SEGMENT = "execution_trace_segment"
    EXECUTION_TRACE = "execution_trace"
    PROGRAM_TRANSITION_QUERY = "program_transition_query"
    PROGRAM_TRANSITION_PREDICTION = "program_transition_prediction"
    PROGRAM_TRANSITION_OBSERVATION = "program_transition_observation"
    PROGRAM_TRANSITION_ADMISSION = "program_transition_admission"
    PROGRAM_TRANSITION_RECEIPT = "program_transition_receipt"
    GRAPH_HISTORY_ENTRY = "graph_history_entry"
    TRANSITION_LOG_ENTRY = "transition_log_entry"
    WORLD_SNAPSHOT = "world_snapshot"
    WORLD_ROOT_MANIFEST = "world_root_manifest"
    OPAQUE_SUBROOT = "opaque_subroot"


_KIND_CID_FIELD: Final[Mapping[GraphHistoryKind, str]] = MappingProxyType(
    {
        GraphHistoryKind.PROGRAM_GRAPH_NODE: "program_graph_node_cid",
        GraphHistoryKind.PROGRAM_GRAPH_EDGE: "program_graph_edge_cid",
        GraphHistoryKind.PROGRAM_GRAPH_SNAPSHOT: "program_graph_snapshot_cid",
        GraphHistoryKind.PROGRAM_GRAPH_DELTA: "program_graph_delta_cid",
        GraphHistoryKind.CALLSITE_RECORD: "callsite_record_cid",
        GraphHistoryKind.FUNCTION_SYMBOL_RECORD: "function_symbol_record_cid",
        GraphHistoryKind.CONTRACT_STATE_RECORD: "contract_state_record_cid",
        GraphHistoryKind.PROOF_OBLIGATION_GRAPH: "proof_obligation_graph_cid",
        GraphHistoryKind.STATIC_SUCCESSOR_SET: "static_successor_set_cid",
        GraphHistoryKind.DYNAMIC_FRONTIER_RECORD: "dynamic_frontier_record_cid",
        GraphHistoryKind.PROGRAM_GRAPH_INDEX_MANIFEST: "program_graph_index_manifest_cid",
        GraphHistoryKind.CANONICAL_PROGRAM_GRAPH: "canonical_program_graph_cid",
        GraphHistoryKind.PROGRAM_EVENT: "program_event_cid",
        GraphHistoryKind.EXECUTION_TRACE_SEGMENT: "execution_trace_segment_cid",
        GraphHistoryKind.EXECUTION_TRACE: "execution_trace_cid",
        GraphHistoryKind.PROGRAM_TRANSITION_QUERY: "query_cid",
        GraphHistoryKind.PROGRAM_TRANSITION_PREDICTION: "prediction_cid",
        GraphHistoryKind.PROGRAM_TRANSITION_OBSERVATION: "observation_cid",
        GraphHistoryKind.PROGRAM_TRANSITION_ADMISSION: "admission_cid",
        GraphHistoryKind.PROGRAM_TRANSITION_RECEIPT: "receipt_cid",
        GraphHistoryKind.GRAPH_HISTORY_ENTRY: "graph_history_entry_cid",
        GraphHistoryKind.TRANSITION_LOG_ENTRY: "transition_log_entry_cid",
        GraphHistoryKind.WORLD_SNAPSHOT: "world_snapshot_cid",
        GraphHistoryKind.WORLD_ROOT_MANIFEST: "world_root_manifest_cid",
        GraphHistoryKind.OPAQUE_SUBROOT: "subroot_cid",
    }
)

_DATASETS_DECODERS: Final[Mapping[GraphHistoryKind, Any]] = MappingProxyType(
    {
        GraphHistoryKind.PROGRAM_GRAPH_NODE: decode_program_graph_record,
        GraphHistoryKind.PROGRAM_GRAPH_EDGE: decode_program_graph_record,
        GraphHistoryKind.PROGRAM_GRAPH_SNAPSHOT: decode_program_graph_record,
        GraphHistoryKind.PROGRAM_GRAPH_DELTA: decode_program_graph_record,
        GraphHistoryKind.CALLSITE_RECORD: decode_program_graph_record,
        GraphHistoryKind.FUNCTION_SYMBOL_RECORD: decode_program_graph_record,
        GraphHistoryKind.CONTRACT_STATE_RECORD: decode_program_graph_record,
        GraphHistoryKind.PROOF_OBLIGATION_GRAPH: decode_program_graph_record,
        GraphHistoryKind.STATIC_SUCCESSOR_SET: decode_program_graph_record,
        GraphHistoryKind.DYNAMIC_FRONTIER_RECORD: decode_program_graph_record,
        GraphHistoryKind.PROGRAM_GRAPH_INDEX_MANIFEST: decode_program_graph_record,
        GraphHistoryKind.CANONICAL_PROGRAM_GRAPH: CanonicalProgramGraphIdentity.from_dict,
        GraphHistoryKind.PROGRAM_EVENT: ProgramEvent.from_dict,
        GraphHistoryKind.EXECUTION_TRACE_SEGMENT: ExecutionTraceSegment.from_dict,
        GraphHistoryKind.EXECUTION_TRACE: ExecutionTrace.from_dict,
        GraphHistoryKind.PROGRAM_TRANSITION_QUERY: decode_transition_record,
        GraphHistoryKind.PROGRAM_TRANSITION_PREDICTION: decode_transition_record,
        GraphHistoryKind.PROGRAM_TRANSITION_OBSERVATION: decode_transition_record,
        GraphHistoryKind.PROGRAM_TRANSITION_ADMISSION: decode_transition_record,
        GraphHistoryKind.PROGRAM_TRANSITION_RECEIPT: decode_transition_record,
    }
)

_RECORD_KIND: Final[Mapping[type, GraphHistoryKind]] = MappingProxyType(
    {
        ProgramGraphNode: GraphHistoryKind.PROGRAM_GRAPH_NODE,
        ProgramGraphEdge: GraphHistoryKind.PROGRAM_GRAPH_EDGE,
        ProgramGraphSnapshot: GraphHistoryKind.PROGRAM_GRAPH_SNAPSHOT,
        ProgramGraphDelta: GraphHistoryKind.PROGRAM_GRAPH_DELTA,
        CallsiteRecord: GraphHistoryKind.CALLSITE_RECORD,
        FunctionSymbolRecord: GraphHistoryKind.FUNCTION_SYMBOL_RECORD,
        ContractStateRecord: GraphHistoryKind.CONTRACT_STATE_RECORD,
        ProofObligationGraph: GraphHistoryKind.PROOF_OBLIGATION_GRAPH,
        StaticSuccessorSet: GraphHistoryKind.STATIC_SUCCESSOR_SET,
        DynamicFrontierRecord: GraphHistoryKind.DYNAMIC_FRONTIER_RECORD,
        ProgramGraphIndexManifest: GraphHistoryKind.PROGRAM_GRAPH_INDEX_MANIFEST,
        CanonicalProgramGraphIdentity: GraphHistoryKind.CANONICAL_PROGRAM_GRAPH,
        ProgramEvent: GraphHistoryKind.PROGRAM_EVENT,
        ExecutionTraceSegment: GraphHistoryKind.EXECUTION_TRACE_SEGMENT,
        ExecutionTrace: GraphHistoryKind.EXECUTION_TRACE,
        ProgramTransitionQuery: GraphHistoryKind.PROGRAM_TRANSITION_QUERY,
        ProgramTransitionPrediction: GraphHistoryKind.PROGRAM_TRANSITION_PREDICTION,
        ProgramTransitionObservation: GraphHistoryKind.PROGRAM_TRANSITION_OBSERVATION,
        ProgramTransitionAdmission: GraphHistoryKind.PROGRAM_TRANSITION_ADMISSION,
        ProgramTransitionReceipt: GraphHistoryKind.PROGRAM_TRANSITION_RECEIPT,
    }
)


@dataclass(frozen=True, slots=True)
class GraphHistoryWriteResult:
    """Verified local write; identity CID is the caller-facing address."""

    cid: str
    storage_cid: str
    kind: GraphHistoryKind
    created: bool
    local_durable: bool
    reason_code: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cid": self.cid,
            "storage_cid": self.storage_cid,
            "kind": self.kind.value,
            "created": self.created,
            "local_durable": self.local_durable,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class GraphSnapshotAppendResult:
    """Immutable snapshot append; no mutable current pointer is published."""

    snapshot_cid: str
    storage_cid: str
    history_entry_cid: str
    delta_cid: str | None
    canonical_program_graph_cid: str
    created: bool
    reason_code: str
    logical_cycle_edge_cids: tuple[tuple[str, ...], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_cid": self.snapshot_cid,
            "storage_cid": self.storage_cid,
            "history_entry_cid": self.history_entry_cid,
            "delta_cid": self.delta_cid,
            "canonical_program_graph_cid": self.canonical_program_graph_cid,
            "created": self.created,
            "reason_code": self.reason_code,
            "logical_cycle_edge_cids": [list(item) for item in self.logical_cycle_edge_cids],
        }


@dataclass(frozen=True, slots=True)
class TransitionReceiptAppendResult:
    """Immutable transition-log append; predictions remain proposal-only."""

    receipt_cid: str
    storage_cid: str
    log_entry_cid: str
    query_cid: str
    admission_cid: str
    prediction_cid: str | None
    observation_cid: str | None
    verdict: str
    created: bool
    reason_code: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_cid": self.receipt_cid,
            "storage_cid": self.storage_cid,
            "log_entry_cid": self.log_entry_cid,
            "query_cid": self.query_cid,
            "admission_cid": self.admission_cid,
            "prediction_cid": self.prediction_cid,
            "observation_cid": self.observation_cid,
            "verdict": self.verdict,
            "created": self.created,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class GraphHistoryEntry:
    """Append-only snapshot history node; previous CID is a physical back-edge."""

    snapshot_cid: str
    previous_entry_cid: str | None = None
    delta_cid: str | None = None

    SCHEMA: ClassVar[str] = GRAPH_HISTORY_ENTRY_SCHEMA
    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE
    CID_FIELD: ClassVar[str] = "graph_history_entry_cid"
    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema",
            "snapshot_cid",
            "previous_entry_cid",
            "delta_cid",
            "graph_history_entry_cid",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "snapshot_cid", _require_cid(self.snapshot_cid, "snapshot_cid")
        )
        object.__setattr__(
            self,
            "previous_entry_cid",
            _optional_cid(self.previous_entry_cid, "previous_entry_cid"),
        )
        object.__setattr__(self, "delta_cid", _optional_cid(self.delta_cid, "delta_cid"))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "snapshot_cid": self.snapshot_cid,
            "previous_entry_cid": self.previous_entry_cid,
            "delta_cid": self.delta_cid,
        }

    @property
    def graph_history_entry_cid(self) -> str:
        return cid_for_artifact(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        value = self.identity_payload()
        value["graph_history_entry_cid"] = self.graph_history_entry_cid
        return value

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GraphHistoryEntry":
        payload = _closed_kit_record(data, cls)
        claimed = payload.pop("graph_history_entry_cid")
        result = cls(
            snapshot_cid=payload["snapshot_cid"],
            previous_entry_cid=payload["previous_entry_cid"],
            delta_cid=payload["delta_cid"],
        )
        if result.graph_history_entry_cid != claimed:
            raise GraphHistoryIntegrityError(
                "graph history entry CID does not rehash canonical identity bytes"
            )
        return result


@dataclass(frozen=True, slots=True)
class TransitionLogEntry:
    """Append-only transition-log node; previous CID is a physical back-edge."""

    receipt_cid: str
    previous_entry_cid: str | None = None

    SCHEMA: ClassVar[str] = TRANSITION_LOG_ENTRY_SCHEMA
    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE
    CID_FIELD: ClassVar[str] = "transition_log_entry_cid"
    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema",
            "receipt_cid",
            "previous_entry_cid",
            "transition_log_entry_cid",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "receipt_cid", _require_cid(self.receipt_cid, "receipt_cid")
        )
        object.__setattr__(
            self,
            "previous_entry_cid",
            _optional_cid(self.previous_entry_cid, "previous_entry_cid"),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "receipt_cid": self.receipt_cid,
            "previous_entry_cid": self.previous_entry_cid,
        }

    @property
    def transition_log_entry_cid(self) -> str:
        return cid_for_artifact(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        value = self.identity_payload()
        value["transition_log_entry_cid"] = self.transition_log_entry_cid
        return value

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TransitionLogEntry":
        payload = _closed_kit_record(data, cls)
        claimed = payload.pop("transition_log_entry_cid")
        result = cls(
            receipt_cid=payload["receipt_cid"],
            previous_entry_cid=payload["previous_entry_cid"],
        )
        if result.transition_log_entry_cid != claimed:
            raise GraphHistoryIntegrityError(
                "transition log entry CID does not rehash canonical identity bytes"
            )
        return result


@dataclass(frozen=True, slots=True)
class SemanticWorldSnapshot:
    """Immutable world snapshot; repeated states keep distinct event histories."""

    program_graph_snapshot_cid: str
    domain_state_cid: str
    environment_binding_set_cid: str
    execution_trace_cids: Sequence[str] = ()
    transition_receipt_cids: Sequence[str] = ()
    event_history_cids: Sequence[str] = ()

    SCHEMA: ClassVar[str] = WORLD_SNAPSHOT_SCHEMA
    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE
    CID_FIELD: ClassVar[str] = "world_snapshot_cid"
    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema",
            "program_graph_snapshot_cid",
            "domain_state_cid",
            "environment_binding_set_cid",
            "execution_trace_cids",
            "transition_receipt_cids",
            "event_history_cids",
            "world_snapshot_cid",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "program_graph_snapshot_cid",
            _require_cid(self.program_graph_snapshot_cid, "program_graph_snapshot_cid"),
        )
        object.__setattr__(
            self, "domain_state_cid", _require_cid(self.domain_state_cid, "domain_state_cid")
        )
        object.__setattr__(
            self,
            "environment_binding_set_cid",
            _require_cid(
                self.environment_binding_set_cid, "environment_binding_set_cid"
            ),
        )
        object.__setattr__(
            self,
            "execution_trace_cids",
            _unique_sorted_cids(self.execution_trace_cids, "execution_trace_cid"),
        )
        object.__setattr__(
            self,
            "transition_receipt_cids",
            _unique_sorted_cids(self.transition_receipt_cids, "transition_receipt_cid"),
        )
        object.__setattr__(
            self,
            "event_history_cids",
            _ordered_cids(self.event_history_cids, "event_history_cid"),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "program_graph_snapshot_cid": self.program_graph_snapshot_cid,
            "domain_state_cid": self.domain_state_cid,
            "environment_binding_set_cid": self.environment_binding_set_cid,
            "execution_trace_cids": list(self.execution_trace_cids),
            "transition_receipt_cids": list(self.transition_receipt_cids),
            "event_history_cids": list(self.event_history_cids),
        }

    @property
    def world_snapshot_cid(self) -> str:
        return cid_for_artifact(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        value = self.identity_payload()
        value["world_snapshot_cid"] = self.world_snapshot_cid
        return value

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SemanticWorldSnapshot":
        payload = _closed_kit_record(data, cls)
        claimed = payload.pop("world_snapshot_cid")
        result = cls(
            program_graph_snapshot_cid=payload["program_graph_snapshot_cid"],
            domain_state_cid=payload["domain_state_cid"],
            environment_binding_set_cid=payload["environment_binding_set_cid"],
            execution_trace_cids=payload["execution_trace_cids"],
            transition_receipt_cids=payload["transition_receipt_cids"],
            event_history_cids=payload["event_history_cids"],
        )
        if result.world_snapshot_cid != claimed:
            raise GraphHistoryIntegrityError(
                "world snapshot CID does not rehash canonical identity bytes"
            )
        return result


def _closed_kit_record(data: Mapping[str, Any], cls: type) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise GraphHistoryIntegrityError(f"{cls.__name__} must be a mapping")
    fields = getattr(cls, "_FIELDS")
    actual = frozenset(data)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise GraphHistoryIntegrityError(
            f"{cls.__name__} has " + "; ".join(problems)
        )
    payload = dict(data)
    if payload.get("schema") != getattr(cls, "SCHEMA"):
        raise GraphHistoryIntegrityError(f"unsupported {cls.__name__} schema version")
    return payload


def _require_cid(value: Any, name: str) -> str:
    try:
        return validate_verified_cid(value, name)
    except SemanticGovernorStoreContractError as exc:
        raise GraphHistoryAdmissionError(str(exc)) from exc


def _optional_cid(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _require_cid(value, name)


def _unique_sorted_cids(values: Iterable[Any], name: str) -> tuple[str, ...]:
    items = [_require_cid(value, name) for value in values]
    ordered = tuple(sorted(items))
    if len(ordered) != len(set(ordered)):
        raise GraphHistoryAdmissionError(f"{name} must not contain duplicates")
    return ordered


def _ordered_cids(values: Iterable[Any], name: str) -> tuple[str, ...]:
    items = tuple(_require_cid(value, name) for value in values)
    if len(items) != len(set(items)):
        raise GraphHistoryAdmissionError(f"{name} must not contain duplicates")
    return items


def _coerce_kind(kind: GraphHistoryKind | str) -> GraphHistoryKind:
    if isinstance(kind, GraphHistoryKind):
        return kind
    if isinstance(kind, str):
        try:
            return GraphHistoryKind(kind)
        except ValueError as exc:
            raise GraphHistoryAdmissionError(
                f"unknown graph-history kind: {kind!r}"
            ) from exc
    raise GraphHistoryAdmissionError(
        "kind must be a GraphHistoryKind or its closed string value"
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
        raise GraphHistoryAdmissionError(f"record is not canonical JSON: {exc}") from exc


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


def seal_graph_history_record(
    kind: GraphHistoryKind | str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the closed, content-addressed storage envelope for a payload."""

    artifact_kind = _coerce_kind(kind)
    if not isinstance(payload, Mapping):
        raise GraphHistoryAdmissionError("payload must be a mapping")
    body = dict(payload)
    _require_structured_json_value(body, path="payload")
    try:
        reject_private_raw_source(body, path="payload")
    except Exception as exc:
        raise GraphHistoryAdmissionError(str(exc)) from exc
    sealed = {
        "schema": GRAPH_HISTORY_RECORD_SCHEMA,
        "interface_id": GRAPH_HISTORY_RECORD_INTERFACE,
        "kind": artifact_kind.value,
        "payload": body,
    }
    data = _canonical_bytes(sealed)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise GraphHistoryAdmissionError(
            f"record exceeds MAX_ARTIFACT_BYTES ({len(data)} > {MAX_ARTIFACT_BYTES})"
        )
    return sealed


def cid_for_graph_history_record(
    kind: GraphHistoryKind | str,
    payload: Mapping[str, Any],
) -> str:
    """Return the dag-json CIDv1 of the sealed storage envelope."""

    return cid_for_artifact(seal_graph_history_record(kind, payload))


def admit_sealed_history_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a retrieved sealed envelope and return a plain dict."""

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
    if record.get("schema") != GRAPH_HISTORY_RECORD_SCHEMA:
        raise GraphHistoryIntegrityError("unknown graph-history record schema")
    if record.get("interface_id") != GRAPH_HISTORY_RECORD_INTERFACE:
        raise GraphHistoryIntegrityError("unknown graph-history record interface_id")
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
    except (GraphHistoryAdmissionError, Exception) as exc:
        raise GraphHistoryIntegrityError(str(exc)) from exc
    sealed = {
        "schema": GRAPH_HISTORY_RECORD_SCHEMA,
        "interface_id": GRAPH_HISTORY_RECORD_INTERFACE,
        "kind": kind.value,
        "payload": body,
    }
    if cid_for_artifact(dict(record)) != cid_for_artifact(sealed):
        raise GraphHistoryIntegrityError("sealed history record is not in canonical form")
    return sealed


def identity_cid_from_history_payload(
    kind: GraphHistoryKind | str,
    payload: Mapping[str, Any],
) -> str:
    """Return the caller-facing identity CID bound inside a sealed payload."""

    artifact_kind = _coerce_kind(kind)
    field = _KIND_CID_FIELD[artifact_kind]
    value = payload.get(field)
    try:
        return validate_verified_cid(value, field)
    except SemanticGovernorStoreContractError as exc:
        raise GraphHistoryIntegrityError(
            f"payload.{field} must be a canonical transport CID"
        ) from exc


def referenced_identity_cids(
    payload: Mapping[str, Any],
    *,
    skip_fields: frozenset[str] | None = None,
) -> tuple[str, ...]:
    """Collect store-before-reference identity CIDs from a payload.

    The record's own claimed CID field is not a parent reference.
    """

    ignored = skip_fields or frozenset()
    refs: list[str] = []

    def walk(obj: Any, key: str | None = None) -> None:
        if isinstance(obj, Mapping):
            for child_key, item in obj.items():
                if type(child_key) is not str:
                    continue
                walk(item, child_key)
            return
        if isinstance(obj, list):
            for item in obj:
                walk(item, key)
            return
        if (
            key in STORE_BEFORE_REFERENCE_FIELDS
            and key not in ignored
            and type(obj) is str
            and obj
        ):
            refs.append(obj)

    walk(payload)
    unique: list[str] = []
    seen: set[str] = set()
    for cid in refs:
        if cid not in seen:
            seen.add(cid)
            unique.append(cid)
    return tuple(unique)


def _coordination_from(
    store: DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | "GraphHistoryBlockStore",
) -> DurableCoordinationStore:
    if isinstance(store, DurableCoordinationStore):
        return store
    if isinstance(store, SemanticWorldArtifactStore):
        return store.store
    if isinstance(store, VerifiedSemanticBlockStore):
        return store.store
    if isinstance(store, GraphHistoryBlockStore):
        return store.store
    raise TypeError(
        "store must be a DurableCoordinationStore, SemanticWorldArtifactStore, "
        "VerifiedSemanticBlockStore, or GraphHistoryBlockStore"
    )


class _IdentityIndex:
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
            CREATE TABLE IF NOT EXISTS artifact_operations (
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
                "SELECT identity_cid, storage_cid, kind FROM artifact_operations "
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
                "SELECT identity_cid, storage_cid, kind FROM artifact_operations "
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
                    "INSERT INTO artifact_operations"
                    "(operation_id, identity_cid, storage_cid, kind) VALUES(?,?,?,?)",
                    (operation_id, identity_cid, storage_cid, kind),
                )


class GraphHistoryBlockStore:
    """Shared immutable block layer for graph history, traces, and world snapshots."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | "GraphHistoryBlockStore",
    ) -> None:
        if isinstance(store, GraphHistoryBlockStore):
            self._store = store._store
            self._index = store._index
            self._owns_index = False
            return
        self._store = _coordination_from(store)
        self._index = _IdentityIndex(self._store)
        self._owns_index = True
        self._rebuild_identity_index()

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    def close(self) -> None:
        if self._owns_index:
            self._index.close()

    def __enter__(self) -> "GraphHistoryBlockStore":
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
            if not isinstance(raw, Mapping) or raw.get("schema") != GRAPH_HISTORY_RECORD_SCHEMA:
                continue
            try:
                sealed = admit_sealed_history_record(raw)
                kind = _coerce_kind(sealed["kind"])
                identity_cid = identity_cid_from_history_payload(kind, sealed["payload"])
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

    def require_stored(self, cid: str, *, name: str) -> str:
        try:
            cid = validate_verified_cid(cid, name)
        except SemanticGovernorStoreContractError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        if not self.has_identity(cid):
            raise GraphHistoryAdmissionError(
                f"store-before-reference: {name} is not stored"
            )
        return cid

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

    def put_record(
        self,
        kind: GraphHistoryKind | str,
        payload: Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        require_references: bool = True,
    ) -> GraphHistoryWriteResult:
        artifact_kind = _coerce_kind(kind)
        if not isinstance(payload, Mapping):
            raise GraphHistoryAdmissionError("payload must be a mapping")
        body = dict(payload)
        sealed = seal_graph_history_record(artifact_kind, body)
        identity_cid = identity_cid_from_history_payload(artifact_kind, sealed["payload"])
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
        if require_references:
            own_field = _KIND_CID_FIELD[artifact_kind]
            for ref in referenced_identity_cids(
                sealed["payload"], skip_fields=frozenset({own_field})
            ):
                if ref == identity_cid:
                    raise GraphHistoryAdmissionError(
                        "physical IPLD block graph must be acyclic"
                    )
                self.require_stored(ref, name="referenced_cid")

        storage_cid = cid_for_artifact(sealed)
        if operation_id is not None:
            prior_op = self._index.lookup_operation(operation_id)
            if prior_op is not None:
                prior_identity, prior_storage, prior_kind = prior_op
                if (
                    prior_identity != identity_cid
                    or prior_storage != storage_cid
                    or prior_kind != artifact_kind.value
                ):
                    raise GraphHistoryConflictError(
                        f"operation_id {operation_id!r} already bound to a different record"
                    )

        prior = self._index.lookup_identity(identity_cid)
        if prior is not None:
            prior_storage, prior_kind = prior
            if prior_storage != storage_cid or prior_kind != artifact_kind.value:
                raise GraphHistoryConflictError(
                    f"identity {identity_cid!r} already bound to a different record"
                )
            self.get_verified_record(identity_cid, expected_kind=artifact_kind)
            if operation_id is not None:
                self._index.bind_operation(
                    operation_id, identity_cid, storage_cid, artifact_kind.value
                )
            return GraphHistoryWriteResult(
                identity_cid,
                storage_cid,
                artifact_kind,
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
        self._index.bind_identity(identity_cid, storage_cid, artifact_kind.value)
        if operation_id is not None:
            self._index.bind_operation(
                operation_id, identity_cid, storage_cid, artifact_kind.value
            )
        created = bool(local.get("created", True))
        return GraphHistoryWriteResult(
            identity_cid,
            storage_cid,
            artifact_kind,
            created,
            True,
            "stored" if created else "unchanged",
        )

    def get_verified_record(
        self,
        cid: str,
        *,
        expected_kind: GraphHistoryKind | str | None = None,
    ) -> Mapping[str, Any]:
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
        sealed = admit_sealed_history_record(raw)
        recomputed = cid_for_artifact(sealed)
        if recomputed != storage_cid:
            raise GraphHistoryIntegrityError(
                f"forged sealed history record: recomputed {recomputed}, expected {storage_cid}"
            )
        kind = GraphHistoryKind(sealed["kind"])
        if indexed_kind is not None and indexed_kind != kind.value:
            raise GraphHistoryIntegrityError(
                f"index kind {indexed_kind} does not match stored {kind.value}"
            )
        if expected_kind is not None:
            wanted = _coerce_kind(expected_kind)
            if kind is not wanted:
                raise GraphHistoryIntegrityError(
                    f"wrong artifact kind: stored {kind.value}, expected {wanted.value}"
                )
        identity_cid = identity_cid_from_history_payload(kind, sealed["payload"])
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

    def admit_subroot(
        self,
        cid: str,
        *,
        role: str,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        """Persist an opaque immutable subroot so a parent may reference it."""

        cid = _require_cid(cid, "subroot_cid")
        if type(role) is not str or not role or role != role.strip():
            raise GraphHistoryAdmissionError("role must be a nonempty string")
        payload = {
            "schema": OPAQUE_SUBROOT_SCHEMA,
            "subroot_cid": cid,
            "role": role,
        }
        return self.put_record(
            GraphHistoryKind.OPAQUE_SUBROOT,
            payload,
            expected_cid=cid,
            operation_id=operation_id,
            require_references=False,
        )


def _wrap_contract_error(exc: Exception) -> GraphHistoryAdmissionError:
    return GraphHistoryAdmissionError(str(exc))


def _put_datasets_record(
    blocks: GraphHistoryBlockStore,
    record: Any,
    *,
    operation_id: str | None = None,
    require_references: bool = True,
) -> GraphHistoryWriteResult:
    kind = _RECORD_KIND.get(type(record))
    if kind is None:
        raise GraphHistoryAdmissionError(
            f"unsupported graph-history record type {type(record).__name__}"
        )
    payload = record.to_dict()
    claimed = getattr(record, record.CID_FIELD)
    try:
        return blocks.put_record(
            kind,
            payload,
            expected_cid=claimed,
            operation_id=operation_id,
            require_references=require_references,
        )
    except (ProgramGraphError, ProgramTransitionError, ProgramExecutionError, ProgramIdentityError) as exc:
        raise _wrap_contract_error(exc) from exc


def _load_datasets_record(
    blocks: GraphHistoryBlockStore,
    cid: str,
    expected_kind: GraphHistoryKind,
) -> Any:
    artifact = blocks.get_verified_record(cid, expected_kind=expected_kind)
    payload = dict(artifact["payload"])
    decoder = _DATASETS_DECODERS.get(expected_kind)
    if decoder is None:
        raise GraphHistoryIntegrityError(
            f"kind {expected_kind.value} is not a datasets record"
        )
    try:
        record = decoder(payload)
    except (
        ProgramGraphError,
        ProgramTransitionError,
        ProgramExecutionError,
        ProgramIdentityError,
    ) as exc:
        raise GraphHistoryIntegrityError(str(exc)) from exc
    claimed = getattr(record, record.CID_FIELD)
    if claimed != artifact["identity_cid"]:
        raise GraphHistoryIntegrityError(
            "stored record CID does not rehash canonical identity bytes"
        )
    return record


class LogicalProgramGraphStore:
    """Persist immutable node/edge sets, snapshots, and deltas."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | GraphHistoryBlockStore,
    ) -> None:
        self._blocks = (
            store if isinstance(store, GraphHistoryBlockStore) else GraphHistoryBlockStore(store)
        )

    @property
    def blocks(self) -> GraphHistoryBlockStore:
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

    def put_node(
        self,
        node: ProgramGraphNode | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        record = node if isinstance(node, ProgramGraphNode) else ProgramGraphNode.from_dict(node)
        return _put_datasets_record(self._blocks, record, operation_id=operation_id)

    def put_edge(
        self,
        edge: ProgramGraphEdge | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        record = edge if isinstance(edge, ProgramGraphEdge) else ProgramGraphEdge.from_dict(edge)
        return _put_datasets_record(self._blocks, record, operation_id=operation_id)

    def get_verified_node(self, cid: str) -> ProgramGraphNode:
        return _load_datasets_record(
            self._blocks, cid, GraphHistoryKind.PROGRAM_GRAPH_NODE
        )

    def get_verified_edge(self, cid: str) -> ProgramGraphEdge:
        return _load_datasets_record(
            self._blocks, cid, GraphHistoryKind.PROGRAM_GRAPH_EDGE
        )

    def get_verified_snapshot(self, cid: str) -> ProgramGraphSnapshot:
        snapshot = _load_datasets_record(
            self._blocks, cid, GraphHistoryKind.PROGRAM_GRAPH_SNAPSHOT
        )
        nodes = [self.get_verified_node(item) for item in snapshot.node_cids]
        edges = [self.get_verified_edge(item) for item in snapshot.edge_cids]
        callsites = [
            _load_datasets_record(self._blocks, item, GraphHistoryKind.CALLSITE_RECORD)
            for item in snapshot.callsite_cids
        ]
        function_symbols = [
            _load_datasets_record(
                self._blocks, item, GraphHistoryKind.FUNCTION_SYMBOL_RECORD
            )
            for item in snapshot.function_symbol_cids
        ]
        contract_states = [
            _load_datasets_record(
                self._blocks, item, GraphHistoryKind.CONTRACT_STATE_RECORD
            )
            for item in snapshot.contract_state_cids
        ]
        proof_obligation_graphs = [
            _load_datasets_record(
                self._blocks, item, GraphHistoryKind.PROOF_OBLIGATION_GRAPH
            )
            for item in snapshot.proof_obligation_graph_cids
        ]
        successor_sets = [
            _load_datasets_record(
                self._blocks, item, GraphHistoryKind.STATIC_SUCCESSOR_SET
            )
            for item in snapshot.successor_set_cids
        ]
        frontiers = [
            _load_datasets_record(
                self._blocks, item, GraphHistoryKind.DYNAMIC_FRONTIER_RECORD
            )
            for item in snapshot.frontier_cids
        ]
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
            raise GraphHistoryIntegrityError(str(exc)) from exc
        return snapshot

    def query_logical_cycles(
        self, snapshot_cid: str
    ) -> tuple[tuple[str, ...], ...]:
        snapshot = self.get_verified_snapshot(snapshot_cid)
        edges = [self.get_verified_edge(item) for item in snapshot.edge_cids]
        return directed_logical_cycles(edges)

    def get_verified_delta(self, cid: str) -> ProgramGraphDelta:
        return _load_datasets_record(
            self._blocks, cid, GraphHistoryKind.PROGRAM_GRAPH_DELTA
        )

    def get_verified_history_entry(self, cid: str) -> GraphHistoryEntry:
        artifact = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.GRAPH_HISTORY_ENTRY
        )
        return GraphHistoryEntry.from_dict(dict(artifact["payload"]))

    def append_program_graph_snapshot(
        self,
        snapshot: ProgramGraphSnapshot,
        *,
        nodes: Sequence[ProgramGraphNode],
        edges: Sequence[ProgramGraphEdge],
        callsites: Sequence[CallsiteRecord] = (),
        function_symbols: Sequence[FunctionSymbolRecord] = (),
        contract_states: Sequence[ContractStateRecord] = (),
        proof_obligation_graphs: Sequence[ProofObligationGraph] = (),
        successor_sets: Sequence[StaticSuccessorSet] = (),
        frontiers: Sequence[DynamicFrontierRecord] = (),
        previous_snapshot: ProgramGraphSnapshot | None = None,
        previous_entry_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphSnapshotAppendResult:
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
            raise _wrap_contract_error(exc) from exc

        for record in (
            *function_symbols,
            *callsites,
            *contract_states,
        ):
            _put_datasets_record(self._blocks, record)
        for node in nodes:
            _put_datasets_record(self._blocks, node)
        for edge in edges:
            _put_datasets_record(self._blocks, edge)
        for record in (*proof_obligation_graphs, *successor_sets, *frontiers):
            _put_datasets_record(self._blocks, record)

        canonical = CanonicalProgramGraphIdentity(
            language=snapshot.language,
            graph_kind=snapshot.graph_kind,
            node_cids=snapshot.node_cids,
            edge_cids=snapshot.edge_cids,
            environment_binding_set_cid=snapshot.environment_binding_set_cid,
            unavailable_dimensions=snapshot.unavailable_dimensions,
        )
        if canonical.canonical_program_graph_cid != snapshot.canonical_program_graph_cid:
            raise GraphHistoryAdmissionError(
                "canonical_program_graph_cid does not verify against stored node/edge sets"
            )
        _put_datasets_record(self._blocks, canonical)

        delta_cid: str | None = None
        if previous_snapshot is not None:
            self._blocks.require_stored(
                previous_snapshot.program_graph_snapshot_cid,
                name="previous_snapshot_cid",
            )
            try:
                delta = delta_between_snapshots(previous_snapshot, snapshot)
                apply_program_graph_delta(previous_snapshot, delta)
            except ProgramGraphError as exc:
                raise _wrap_contract_error(exc) from exc
            delta_put = _put_datasets_record(self._blocks, delta)
            delta_cid = delta_put.cid

        snapshot_put = _put_datasets_record(
            self._blocks,
            snapshot,
            operation_id=None if operation_id is None else f"{operation_id}:snapshot",
        )
        if previous_entry_cid is not None:
            self._blocks.require_stored(previous_entry_cid, name="previous_entry_cid")
            self._assert_history_acyclic(previous_entry_cid, snapshot_put.cid)

        entry = GraphHistoryEntry(
            snapshot_cid=snapshot.program_graph_snapshot_cid,
            previous_entry_cid=previous_entry_cid,
            delta_cid=delta_cid,
        )
        entry_put = self._blocks.put_record(
            GraphHistoryKind.GRAPH_HISTORY_ENTRY,
            entry.to_dict(),
            expected_cid=entry.graph_history_entry_cid,
            operation_id=operation_id,
        )
        cycles = directed_logical_cycles(list(edges))
        return GraphSnapshotAppendResult(
            snapshot_cid=snapshot_put.cid,
            storage_cid=snapshot_put.storage_cid,
            history_entry_cid=entry_put.cid,
            delta_cid=delta_cid,
            canonical_program_graph_cid=canonical.canonical_program_graph_cid,
            created=snapshot_put.created or entry_put.created,
            reason_code=entry_put.reason_code if not entry_put.created else snapshot_put.reason_code,
            logical_cycle_edge_cids=cycles,
        )

    def _assert_history_acyclic(self, previous_entry_cid: str, new_identity: str) -> None:
        seen: set[str] = set()
        current: str | None = previous_entry_cid
        while current is not None:
            if current == new_identity or current in seen:
                raise GraphHistoryAdmissionError(
                    "physical IPLD block graph must be acyclic"
                )
            seen.add(current)
            entry = self.get_verified_history_entry(current)
            current = entry.previous_entry_cid


class ProgramTransitionLog:
    """Persist queries, predictions, observations, admissions, and receipts."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | GraphHistoryBlockStore,
    ) -> None:
        self._blocks = (
            store if isinstance(store, GraphHistoryBlockStore) else GraphHistoryBlockStore(store)
        )

    @property
    def blocks(self) -> GraphHistoryBlockStore:
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

    def put_query(
        self,
        query: ProgramTransitionQuery | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        record = (
            query
            if isinstance(query, ProgramTransitionQuery)
            else ProgramTransitionQuery.from_dict(query)
        )
        return _put_datasets_record(
            self._blocks, record, operation_id=operation_id, require_references=False
        )

    def put_prediction(
        self,
        prediction: ProgramTransitionPrediction | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        record = (
            prediction
            if isinstance(prediction, ProgramTransitionPrediction)
            else ProgramTransitionPrediction.from_dict(prediction)
        )
        if not record.proposal_only:
            raise GraphHistoryAdmissionError("predictions are proposal-only")
        return _put_datasets_record(self._blocks, record, operation_id=operation_id)

    def put_observation(
        self,
        observation: ProgramTransitionObservation | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if isinstance(observation, Mapping):
            try:
                decode_transition_observation(observation)
            except ProgramTransitionError as exc:
                raise _wrap_contract_error(exc) from exc
            record = ProgramTransitionObservation.from_dict(observation)
        else:
            record = observation
        if record.proposal_only:
            raise GraphHistoryAdmissionError("observations cannot be proposal-only")
        return _put_datasets_record(self._blocks, record, operation_id=operation_id)

    def get_verified_prediction(self, cid: str) -> ProgramTransitionPrediction:
        return _load_datasets_record(
            self._blocks, cid, GraphHistoryKind.PROGRAM_TRANSITION_PREDICTION
        )

    def get_verified_observation(self, cid: str) -> ProgramTransitionObservation:
        artifact = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.PROGRAM_TRANSITION_OBSERVATION
        )
        try:
            return decode_transition_observation(dict(artifact["payload"]))
        except ProgramTransitionError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc

    def get_verified_admission(self, cid: str) -> ProgramTransitionAdmission:
        return _load_datasets_record(
            self._blocks, cid, GraphHistoryKind.PROGRAM_TRANSITION_ADMISSION
        )

    def get_verified_receipt(self, cid: str) -> ProgramTransitionReceipt:
        return _load_datasets_record(
            self._blocks, cid, GraphHistoryKind.PROGRAM_TRANSITION_RECEIPT
        )

    def get_verified_log_entry(self, cid: str) -> TransitionLogEntry:
        artifact = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.TRANSITION_LOG_ENTRY
        )
        return TransitionLogEntry.from_dict(dict(artifact["payload"]))

    def append_transition_receipt(
        self,
        receipt: ProgramTransitionReceipt,
        *,
        query: ProgramTransitionQuery,
        admission: ProgramTransitionAdmission,
        prediction: ProgramTransitionPrediction | None = None,
        observation: ProgramTransitionObservation | None = None,
        previous_entry_cid: str | None = None,
        operation_id: str | None = None,
    ) -> TransitionReceiptAppendResult:
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
        if receipt.prediction_authoritative:
            raise GraphHistoryAdmissionError(
                "receipts cannot treat predictions as authoritative"
            )
        if (
            receipt.may_influence_planning
            and receipt.observation_cid is None
        ):
            raise GraphHistoryAdmissionError(
                "planning influence requires an independent observation"
            )

        self.put_query(query)
        if prediction is not None:
            self.put_prediction(prediction)
        if observation is not None:
            self.put_observation(observation)
        _put_datasets_record(self._blocks, admission)
        receipt_put = _put_datasets_record(
            self._blocks,
            receipt,
            operation_id=None if operation_id is None else f"{operation_id}:receipt",
        )
        if previous_entry_cid is not None:
            self._blocks.require_stored(previous_entry_cid, name="previous_entry_cid")
        entry = TransitionLogEntry(
            receipt_cid=receipt.receipt_cid,
            previous_entry_cid=previous_entry_cid,
        )
        entry_put = self._blocks.put_record(
            GraphHistoryKind.TRANSITION_LOG_ENTRY,
            entry.to_dict(),
            expected_cid=entry.transition_log_entry_cid,
            operation_id=operation_id,
        )
        return TransitionReceiptAppendResult(
            receipt_cid=receipt_put.cid,
            storage_cid=receipt_put.storage_cid,
            log_entry_cid=entry_put.cid,
            query_cid=query.query_cid,
            admission_cid=admission.admission_cid,
            prediction_cid=receipt.prediction_cid,
            observation_cid=receipt.observation_cid,
            verdict=str(receipt.verdict),
            created=receipt_put.created or entry_put.created,
            reason_code=entry_put.reason_code if not entry_put.created else receipt_put.reason_code,
        )


class SemanticWorldSnapshotStore:
    """Persist traces and world snapshots while preserving distinct histories."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | GraphHistoryBlockStore,
    ) -> None:
        self._blocks = (
            store if isinstance(store, GraphHistoryBlockStore) else GraphHistoryBlockStore(store)
        )

    @property
    def blocks(self) -> GraphHistoryBlockStore:
        return self._blocks

    @property
    def store(self) -> DurableCoordinationStore:
        return self._blocks.store

    def close(self) -> None:
        self._blocks.close()

    def __enter__(self) -> "SemanticWorldSnapshotStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def put_event(
        self,
        event: ProgramEvent | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        record = event if isinstance(event, ProgramEvent) else ProgramEvent.from_dict(event)
        return _put_datasets_record(self._blocks, record, operation_id=operation_id)

    def put_trace_segment(
        self,
        segment: ExecutionTraceSegment | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        record = (
            segment
            if isinstance(segment, ExecutionTraceSegment)
            else ExecutionTraceSegment.from_dict(segment)
        )
        return _put_datasets_record(self._blocks, record, operation_id=operation_id)

    def put_trace(
        self,
        trace: ExecutionTrace | Mapping[str, Any],
        *,
        events: Sequence[ProgramEvent] = (),
        segments: Sequence[ExecutionTraceSegment] = (),
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        record = (
            trace if isinstance(trace, ExecutionTrace) else ExecutionTrace.from_dict(trace)
        )
        for event in events:
            self.put_event(event)
        for segment in segments:
            self.put_trace_segment(segment)
        return _put_datasets_record(self._blocks, record, operation_id=operation_id)

    def get_verified_trace(self, cid: str) -> ExecutionTrace:
        return _load_datasets_record(self._blocks, cid, GraphHistoryKind.EXECUTION_TRACE)

    def get_verified_world_snapshot(self, cid: str) -> SemanticWorldSnapshot:
        artifact = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.WORLD_SNAPSHOT
        )
        snapshot = SemanticWorldSnapshot.from_dict(dict(artifact["payload"]))
        self._blocks.require_stored(
            snapshot.program_graph_snapshot_cid, name="program_graph_snapshot_cid"
        )
        for trace_cid in snapshot.execution_trace_cids:
            self.get_verified_trace(trace_cid)
        for receipt_cid in snapshot.transition_receipt_cids:
            _load_datasets_record(
                self._blocks, receipt_cid, GraphHistoryKind.PROGRAM_TRANSITION_RECEIPT
            )
        return snapshot

    def append_world_snapshot(
        self,
        snapshot: SemanticWorldSnapshot,
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._blocks.put_record(
            GraphHistoryKind.WORLD_SNAPSHOT,
            snapshot.to_dict(),
            expected_cid=snapshot.world_snapshot_cid,
            operation_id=operation_id,
        )


def append_program_graph_snapshot(
    store: LogicalProgramGraphStore
    | GraphHistoryBlockStore
    | DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore,
    snapshot: ProgramGraphSnapshot,
    *,
    nodes: Sequence[ProgramGraphNode],
    edges: Sequence[ProgramGraphEdge],
    callsites: Sequence[CallsiteRecord] = (),
    function_symbols: Sequence[FunctionSymbolRecord] = (),
    contract_states: Sequence[ContractStateRecord] = (),
    proof_obligation_graphs: Sequence[ProofObligationGraph] = (),
    successor_sets: Sequence[StaticSuccessorSet] = (),
    frontiers: Sequence[DynamicFrontierRecord] = (),
    previous_snapshot: ProgramGraphSnapshot | None = None,
    previous_entry_cid: str | None = None,
    operation_id: str | None = None,
) -> GraphSnapshotAppendResult:
    """Persist one sealed program-graph snapshot after its referenced records."""

    graphs = (
        store
        if isinstance(store, LogicalProgramGraphStore)
        else LogicalProgramGraphStore(store)
    )
    return graphs.append_program_graph_snapshot(
        snapshot,
        nodes=nodes,
        edges=edges,
        callsites=callsites,
        function_symbols=function_symbols,
        contract_states=contract_states,
        proof_obligation_graphs=proof_obligation_graphs,
        successor_sets=successor_sets,
        frontiers=frontiers,
        previous_snapshot=previous_snapshot,
        previous_entry_cid=previous_entry_cid,
        operation_id=operation_id,
    )


def append_transition_receipt(
    store: ProgramTransitionLog
    | GraphHistoryBlockStore
    | DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore,
    receipt: ProgramTransitionReceipt,
    *,
    query: ProgramTransitionQuery,
    admission: ProgramTransitionAdmission,
    prediction: ProgramTransitionPrediction | None = None,
    observation: ProgramTransitionObservation | None = None,
    previous_entry_cid: str | None = None,
    operation_id: str | None = None,
) -> TransitionReceiptAppendResult:
    """Persist one transition receipt after query/prediction/observation/admission."""

    log = (
        store if isinstance(store, ProgramTransitionLog) else ProgramTransitionLog(store)
    )
    return log.append_transition_receipt(
        receipt,
        query=query,
        admission=admission,
        prediction=prediction,
        observation=observation,
        previous_entry_cid=previous_entry_cid,
        operation_id=operation_id,
    )


__all__ = [
    "GRAPH_HISTORY_ENTRY_SCHEMA",
    "GRAPH_HISTORY_RECORD_INTERFACE",
    "GRAPH_HISTORY_RECORD_SCHEMA",
    "OPAQUE_SUBROOT_SCHEMA",
    "PROGRAM_GRAPH_HISTORY_INTERFACE",
    "STORE_BEFORE_REFERENCE_FIELDS",
    "TRANSITION_LOG_ENTRY_SCHEMA",
    "WORLD_SNAPSHOT_SCHEMA",
    "GraphHistoryAdmissionError",
    "GraphHistoryBlockStore",
    "GraphHistoryConflictError",
    "GraphHistoryEntry",
    "GraphHistoryError",
    "GraphHistoryIntegrityError",
    "GraphHistoryKind",
    "GraphHistoryNotFound",
    "GraphHistoryWriteResult",
    "GraphSnapshotAppendResult",
    "LogicalProgramGraphStore",
    "ProgramTransitionLog",
    "SemanticWorldSnapshot",
    "SemanticWorldSnapshotStore",
    "TransitionLogEntry",
    "TransitionReceiptAppendResult",
    "admit_sealed_history_record",
    "append_program_graph_snapshot",
    "append_transition_receipt",
    "cid_for_graph_history_record",
    "identity_cid_from_history_payload",
    "referenced_identity_cids",
    "seal_graph_history_record",
]
