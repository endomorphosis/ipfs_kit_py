"""Immutable logical graph snapshots, traces, and transition history.

``ProgramGraphHistory@1`` persists datasets program-graph and transition
codecs through kit CID/block verification.  It does not mint a second CID
engine, decide semantic equivalence, admit operational transitions, or
publish a mutable current world-root pointer.

Authority rules (normative, fail-closed):

* Physical IPLD/Merkle blocks are immutable and acyclic.  Logical cycles
  (mutual recursion, cyclic imports, CFG/state loops, repeated states) are
  represented by independently hashed node/edge/event records.
* Every parent record is stored only after each referenced CID already
  exists as verified bytes (store-before-reference).
* Predictions remain proposal-only and cannot decode as observations or
  admissions.  Kit persists; it never accepts semantics.
* Append of identical identity bytes is idempotent.  Corrupt present blocks
  and missing references fail closed.
* Root current-pointer CAS belongs exclusively to SAWM-014.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Final, Iterable, Mapping, Sequence

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    ProgramGraphDelta,
    ProgramGraphEdge,
    ProgramGraphError,
    ProgramGraphNode,
    ProgramGraphSnapshot,
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
    ProgramGraphDeltaIdentity,
    ProgramGraphSnapshotIdentity,
    ProgramIdentityError,
    TransitionIdentity,
    decode_identity_record,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
    ProgramTransitionAdmission,
    ProgramTransitionCandidate,
    ProgramTransitionError,
    ProgramTransitionObservation,
    ProgramTransitionPrediction,
    ProgramTransitionQuery,
    ProgramTransitionReceipt,
    TransitionModelProfile,
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
    PRIVATE_FIELD_MARKERS,
    SemanticWorldArtifactAdmissionError,
    reject_private_raw_source,
)
from ipfs_kit_py.semantic_world_store.verified_store import (
    VERIFIED_SEMANTIC_STORE_INTERFACE,
    VerifiedSemanticBlockStore,
    VerifiedSemanticStoreIntegrityError,
    VerifiedSemanticStoreNotFound,
)


# ---------------------------------------------------------------------------
# Schema / interfaces
# ---------------------------------------------------------------------------

PROGRAM_GRAPH_HISTORY_INTERFACE: Final[str] = "ProgramGraphHistory@1"
HISTORY_BLOCK_INTERFACE: Final[str] = "SemanticWorldHistoryBlock@1"
HISTORY_BLOCK_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.history-block@1"
)
WORLD_SNAPSHOT_INTERFACE: Final[str] = "SemanticWorldSnapshot@1"
WORLD_SNAPSHOT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-snapshot@1"
)
LEAF_SUBROOT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.leaf-subroot@1"
)
TRANSITION_LOG_HEAD_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.transition-log-head@1"
)
HISTORY_INDEX_DB_NAME: Final[str] = "semantic_world_history_index.sqlite3"
HISTORY_SCHEMA_VERSION: Final[int] = 1
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1

_SEALED_FIELDS: Final[frozenset[str]] = frozenset(
    ("schema", "interface_id", "kind", "payload")
)
_SCORE_IDENTITY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "distance",
        "embedding_score",
        "knn",
        "nearest",
        "score",
        "scores",
        "similarity",
    }
)

_DATASETS_ERRORS: Final[tuple[type[BaseException], ...]] = (
    ProgramGraphError,
    ProgramIdentityError,
    ProgramTransitionError,
)


class GraphHistoryKind(str, Enum):
    """Closed storage-admission kinds for graph/transition/world history."""

    GRAPH_NODE = "graph_node"
    GRAPH_EDGE = "graph_edge"
    GRAPH_SNAPSHOT = "graph_snapshot"
    GRAPH_SNAPSHOT_IDENTITY = "graph_snapshot_identity"
    GRAPH_DELTA = "graph_delta"
    GRAPH_DELTA_IDENTITY = "graph_delta_identity"
    CANONICAL_PROGRAM_GRAPH = "canonical_program_graph"
    CALLSITE = "callsite"
    FUNCTION_SYMBOL = "function_symbol"
    CONTRACT_STATE = "contract_state"
    PROOF_OBLIGATION_GRAPH = "proof_obligation_graph"
    STATIC_SUCCESSOR_SET = "static_successor_set"
    DYNAMIC_FRONTIER = "dynamic_frontier"
    PROGRAM_EVENT = "program_event"
    EXECUTION_TRACE = "execution_trace"
    TRANSITION_QUERY = "transition_query"
    TRANSITION_CANDIDATE = "transition_candidate"
    TRANSITION_PREDICTION = "transition_prediction"
    TRANSITION_OBSERVATION = "transition_observation"
    TRANSITION_ADMISSION = "transition_admission"
    TRANSITION_RECEIPT = "transition_receipt"
    TRANSITION_MODEL_PROFILE = "transition_model_profile"
    TRANSITION_IDENTITY = "transition_identity"
    TRANSITION_LOG_HEAD = "transition_log_head"
    WORLD_SNAPSHOT = "world_snapshot"
    WORLD_ROOT_MANIFEST = "world_root_manifest"
    LEAF_SUBROOT = "leaf_subroot"


_KIND_CID_FIELDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        GraphHistoryKind.GRAPH_NODE.value: "program_graph_node_cid",
        GraphHistoryKind.GRAPH_EDGE.value: "program_graph_edge_cid",
        GraphHistoryKind.GRAPH_SNAPSHOT.value: "program_graph_snapshot_cid",
        GraphHistoryKind.GRAPH_SNAPSHOT_IDENTITY.value: "program_graph_snapshot_cid",
        GraphHistoryKind.GRAPH_DELTA.value: "program_graph_delta_cid",
        GraphHistoryKind.GRAPH_DELTA_IDENTITY.value: "program_graph_delta_cid",
        GraphHistoryKind.CANONICAL_PROGRAM_GRAPH.value: "canonical_program_graph_cid",
        GraphHistoryKind.CALLSITE.value: "callsite_record_cid",
        GraphHistoryKind.FUNCTION_SYMBOL.value: "function_symbol_record_cid",
        GraphHistoryKind.CONTRACT_STATE.value: "contract_state_record_cid",
        GraphHistoryKind.PROOF_OBLIGATION_GRAPH.value: "proof_obligation_graph_cid",
        GraphHistoryKind.STATIC_SUCCESSOR_SET.value: "static_successor_set_cid",
        GraphHistoryKind.DYNAMIC_FRONTIER.value: "dynamic_frontier_record_cid",
        GraphHistoryKind.PROGRAM_EVENT.value: "program_event_cid",
        GraphHistoryKind.EXECUTION_TRACE.value: "execution_trace_cid",
        GraphHistoryKind.TRANSITION_QUERY.value: "query_cid",
        GraphHistoryKind.TRANSITION_CANDIDATE.value: "candidate_cid",
        GraphHistoryKind.TRANSITION_PREDICTION.value: "prediction_cid",
        GraphHistoryKind.TRANSITION_OBSERVATION.value: "observation_cid",
        GraphHistoryKind.TRANSITION_ADMISSION.value: "admission_cid",
        GraphHistoryKind.TRANSITION_RECEIPT.value: "receipt_cid",
        GraphHistoryKind.TRANSITION_MODEL_PROFILE.value: "model_profile_cid",
        GraphHistoryKind.TRANSITION_IDENTITY.value: "transition_cid",
        GraphHistoryKind.TRANSITION_LOG_HEAD.value: "log_head_cid",
        GraphHistoryKind.WORLD_SNAPSHOT.value: "world_snapshot_cid",
        GraphHistoryKind.WORLD_ROOT_MANIFEST.value: "world_root_manifest_cid",
        GraphHistoryKind.LEAF_SUBROOT.value: "subroot_cid",
    }
)

_GRAPH_NODE_KINDS: Final[frozenset[str]] = frozenset(
    {GraphHistoryKind.GRAPH_NODE.value}
)
_GRAPH_EDGE_KINDS: Final[frozenset[str]] = frozenset(
    {GraphHistoryKind.GRAPH_EDGE.value}
)
_SNAPSHOT_KINDS: Final[frozenset[str]] = frozenset(
    {GraphHistoryKind.GRAPH_SNAPSHOT.value}
)
_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {GraphHistoryKind.PROGRAM_EVENT.value}
)
_PREDICTION_KINDS: Final[frozenset[str]] = frozenset(
    {GraphHistoryKind.TRANSITION_PREDICTION.value}
)
_OBSERVATION_KINDS: Final[frozenset[str]] = frozenset(
    {GraphHistoryKind.TRANSITION_OBSERVATION.value}
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GraphHistoryError(ValueError):
    """Base error for logical graph/transition history admission or retrieval."""

    reason_code: ClassVar[str] = "graph_history_error"


class GraphHistoryAdmissionError(GraphHistoryError):
    """Raised when a history write is rejected before durable mutation."""

    reason_code: ClassVar[str] = "graph_history_admission_error"


class GraphHistoryIntegrityError(GraphHistoryError):
    """Raised when stored bytes, CIDs, or kinds do not re-verify."""

    reason_code: ClassVar[str] = "graph_history_integrity_error"


class GraphHistoryNotFound(GraphHistoryError, KeyError):
    """Raised when a required history block is absent."""

    reason_code: ClassVar[str] = "graph_history_not_found"


class GraphHistoryConflictError(GraphHistoryError):
    """Raised when an identity or operation_id is rebound to different bytes."""

    reason_code: ClassVar[str] = "graph_history_conflict"


# ---------------------------------------------------------------------------
# Write result / world snapshot / log head
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GraphHistoryWriteResult:
    """Verified local history write; identity CID is the caller-facing address."""

    cid: str
    storage_cid: str
    kind: str
    created: bool
    local_durable: bool
    reason_code: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cid": self.cid,
            "storage_cid": self.storage_cid,
            "kind": self.kind,
            "created": self.created,
            "local_durable": self.local_durable,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class TransitionLogHead:
    """Immutable append-only log link.  Not a mutable current-pointer CAS."""

    receipt_cid: str
    previous_head_cid: str | None
    ordinal: int

    SCHEMA: ClassVar[str] = TRANSITION_LOG_HEAD_SCHEMA
    CID_FIELD: ClassVar[str] = "log_head_cid"

    def __post_init__(self) -> None:
        if type(self.receipt_cid) is not str or not self.receipt_cid:
            raise GraphHistoryAdmissionError("receipt_cid must be a CID")
        if self.previous_head_cid is not None and (
            type(self.previous_head_cid) is not str or not self.previous_head_cid
        ):
            raise GraphHistoryAdmissionError(
                "previous_head_cid must be a CID or None"
            )
        if type(self.ordinal) is not int or isinstance(self.ordinal, bool) or self.ordinal < 1:
            raise GraphHistoryAdmissionError("ordinal must be a positive integer")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "receipt_cid": self.receipt_cid,
            "previous_head_cid": self.previous_head_cid,
            "ordinal": self.ordinal,
        }

    @property
    def log_head_cid(self) -> str:
        return cid_for_artifact(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self.identity_payload()
        payload["log_head_cid"] = self.log_head_cid
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TransitionLogHead":
        if not isinstance(data, Mapping):
            raise GraphHistoryIntegrityError("transition log head must be a mapping")
        claimed = data.get("log_head_cid")
        result = cls(
            receipt_cid=str(data["receipt_cid"]),
            previous_head_cid=data.get("previous_head_cid"),
            ordinal=int(data["ordinal"]),
        )
        if type(claimed) is str and claimed and claimed != result.log_head_cid:
            raise GraphHistoryIntegrityError(
                "transition log head CID does not rehash"
            )
        return result


@dataclass(frozen=True, slots=True)
class SemanticWorldSnapshot:
    """Point-in-time bundle of graph, traces, and transition evidence."""

    program_graph_snapshot_cid: str
    program_graph_snapshot_identity_cid: str
    canonical_program_graph_cid: str
    domain_state_cid: str
    semantic_object_index_cid: str
    environment_binding_set_cid: str
    policy_cid: str
    analysis_limitation_index_cid: str
    execution_trace_cid: str | None = None
    event_cids: Sequence[str] = ()
    transition_receipt_cids: Sequence[str] = ()
    transition_log_head_cid: str | None = None

    SCHEMA: ClassVar[str] = WORLD_SNAPSHOT_SCHEMA
    INTERFACE: ClassVar[str] = WORLD_SNAPSHOT_INTERFACE
    CID_FIELD: ClassVar[str] = "world_snapshot_cid"

    def __post_init__(self) -> None:
        for name in (
            "program_graph_snapshot_cid",
            "program_graph_snapshot_identity_cid",
            "canonical_program_graph_cid",
            "domain_state_cid",
            "semantic_object_index_cid",
            "environment_binding_set_cid",
            "policy_cid",
            "analysis_limitation_index_cid",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise GraphHistoryAdmissionError(f"{name} must be a CID")
        for optional in ("execution_trace_cid", "transition_log_head_cid"):
            value = getattr(self, optional)
            if value is not None and (type(value) is not str or not value):
                raise GraphHistoryAdmissionError(f"{optional} must be a CID or None")
        object.__setattr__(self, "event_cids", tuple(self.event_cids))
        object.__setattr__(
            self, "transition_receipt_cids", tuple(self.transition_receipt_cids)
        )
        for cid in (*self.event_cids, *self.transition_receipt_cids):
            if type(cid) is not str or not cid:
                raise GraphHistoryAdmissionError(
                    "event and receipt identities must be CIDs"
                )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "interface_id": self.INTERFACE,
            "program_graph_snapshot_cid": self.program_graph_snapshot_cid,
            "program_graph_snapshot_identity_cid": (
                self.program_graph_snapshot_identity_cid
            ),
            "canonical_program_graph_cid": self.canonical_program_graph_cid,
            "domain_state_cid": self.domain_state_cid,
            "semantic_object_index_cid": self.semantic_object_index_cid,
            "environment_binding_set_cid": self.environment_binding_set_cid,
            "policy_cid": self.policy_cid,
            "analysis_limitation_index_cid": self.analysis_limitation_index_cid,
            "execution_trace_cid": self.execution_trace_cid,
            "event_cids": list(self.event_cids),
            "transition_receipt_cids": list(self.transition_receipt_cids),
            "transition_log_head_cid": self.transition_log_head_cid,
        }

    @property
    def world_snapshot_cid(self) -> str:
        return cid_for_artifact(self.identity_payload())

    def referenced_subroot_cids(self) -> tuple[str, ...]:
        cids = [
            self.program_graph_snapshot_cid,
            self.program_graph_snapshot_identity_cid,
            self.canonical_program_graph_cid,
            self.domain_state_cid,
            self.semantic_object_index_cid,
            self.environment_binding_set_cid,
            self.policy_cid,
            self.analysis_limitation_index_cid,
        ]
        if self.execution_trace_cid is not None:
            cids.append(self.execution_trace_cid)
        if self.transition_log_head_cid is not None:
            cids.append(self.transition_log_head_cid)
        cids.extend(self.event_cids)
        cids.extend(self.transition_receipt_cids)
        return tuple(sorted(set(cids)))

    def to_dict(self) -> dict[str, Any]:
        payload = self.identity_payload()
        payload["world_snapshot_cid"] = self.world_snapshot_cid
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SemanticWorldSnapshot":
        if not isinstance(data, Mapping):
            raise GraphHistoryIntegrityError("world snapshot must be a mapping")
        claimed = data.get("world_snapshot_cid")
        result = cls(
            program_graph_snapshot_cid=str(data["program_graph_snapshot_cid"]),
            program_graph_snapshot_identity_cid=str(
                data["program_graph_snapshot_identity_cid"]
            ),
            canonical_program_graph_cid=str(data["canonical_program_graph_cid"]),
            domain_state_cid=str(data["domain_state_cid"]),
            semantic_object_index_cid=str(data["semantic_object_index_cid"]),
            environment_binding_set_cid=str(data["environment_binding_set_cid"]),
            policy_cid=str(data["policy_cid"]),
            analysis_limitation_index_cid=str(data["analysis_limitation_index_cid"]),
            execution_trace_cid=data.get("execution_trace_cid"),
            event_cids=tuple(data.get("event_cids") or ()),
            transition_receipt_cids=tuple(data.get("transition_receipt_cids") or ()),
            transition_log_head_cid=data.get("transition_log_head_cid"),
        )
        if type(claimed) is str and claimed and claimed != result.world_snapshot_cid:
            raise GraphHistoryIntegrityError("world snapshot CID does not rehash")
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_kind(kind: GraphHistoryKind | str) -> GraphHistoryKind:
    if isinstance(kind, GraphHistoryKind):
        return kind
    if isinstance(kind, str):
        try:
            return GraphHistoryKind(kind)
        except ValueError as exc:
            raise GraphHistoryAdmissionError(
                f"unknown graph-history artifact kind: {kind!r}"
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
        raise GraphHistoryAdmissionError(
            f"history artifact is not canonical JSON: {exc}"
        ) from exc


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


def _reject_score_derived_identity(payload: Mapping[str, Any], *, path: str) -> None:
    extra = set(payload) & _SCORE_IDENTITY_FIELDS
    if extra:
        raise GraphHistoryAdmissionError(
            f"{path} rejects score-derived identity fields {sorted(extra)}"
        )


def _key_is_private(name: str) -> bool:
    lowered = name.lower()
    if lowered in PRIVATE_FIELD_MARKERS:
        return True
    return any(marker in lowered for marker in PRIVATE_FIELD_MARKERS)


def _identity_cid_from_payload(kind: GraphHistoryKind, payload: Mapping[str, Any]) -> str:
    field = _KIND_CID_FIELDS[kind.value]
    value = payload.get(field)
    try:
        return validate_verified_cid(value, field)
    except SemanticGovernorStoreContractError as exc:
        raise GraphHistoryIntegrityError(
            f"payload.{field} must be a canonical transport CID"
        ) from exc


def _record_cid(record: Any) -> str:
    field = getattr(type(record), "CID_FIELD", None)
    if type(field) is not str:
        raise GraphHistoryAdmissionError(
            f"{type(record).__name__} is missing CID_FIELD"
        )
    return str(getattr(record, field))


def _kind_for_record(record: Any) -> GraphHistoryKind:
    if isinstance(record, ProgramGraphNode):
        return GraphHistoryKind.GRAPH_NODE
    if isinstance(record, ProgramGraphEdge):
        return GraphHistoryKind.GRAPH_EDGE
    if isinstance(record, ProgramGraphSnapshot):
        return GraphHistoryKind.GRAPH_SNAPSHOT
    if isinstance(record, ProgramGraphDelta):
        return GraphHistoryKind.GRAPH_DELTA
    if isinstance(record, CanonicalProgramGraphIdentity):
        return GraphHistoryKind.CANONICAL_PROGRAM_GRAPH
    if isinstance(record, ProgramGraphSnapshotIdentity):
        return GraphHistoryKind.GRAPH_SNAPSHOT_IDENTITY
    if isinstance(record, ProgramGraphDeltaIdentity):
        return GraphHistoryKind.GRAPH_DELTA_IDENTITY
    if isinstance(record, ProgramEventIdentity):
        return GraphHistoryKind.PROGRAM_EVENT
    if isinstance(record, ExecutionTraceIdentity):
        return GraphHistoryKind.EXECUTION_TRACE
    if isinstance(record, ProgramTransitionQuery):
        return GraphHistoryKind.TRANSITION_QUERY
    if isinstance(record, ProgramTransitionCandidate):
        return GraphHistoryKind.TRANSITION_CANDIDATE
    if isinstance(record, ProgramTransitionPrediction):
        return GraphHistoryKind.TRANSITION_PREDICTION
    if isinstance(record, ProgramTransitionObservation):
        return GraphHistoryKind.TRANSITION_OBSERVATION
    if isinstance(record, ProgramTransitionAdmission):
        return GraphHistoryKind.TRANSITION_ADMISSION
    if isinstance(record, ProgramTransitionReceipt):
        return GraphHistoryKind.TRANSITION_RECEIPT
    if isinstance(record, TransitionModelProfile):
        return GraphHistoryKind.TRANSITION_MODEL_PROFILE
    if isinstance(record, TransitionIdentity):
        return GraphHistoryKind.TRANSITION_IDENTITY
    if isinstance(record, TransitionLogHead):
        return GraphHistoryKind.TRANSITION_LOG_HEAD
    if isinstance(record, SemanticWorldSnapshot):
        return GraphHistoryKind.WORLD_SNAPSHOT
    schema = getattr(record, "SCHEMA", None)
    name = type(record).__name__
    mapping = {
        "CallsiteRecord": GraphHistoryKind.CALLSITE,
        "FunctionSymbolRecord": GraphHistoryKind.FUNCTION_SYMBOL,
        "ContractStateRecord": GraphHistoryKind.CONTRACT_STATE,
        "ProofObligationGraph": GraphHistoryKind.PROOF_OBLIGATION_GRAPH,
        "StaticSuccessorSet": GraphHistoryKind.STATIC_SUCCESSOR_SET,
        "DynamicFrontierRecord": GraphHistoryKind.DYNAMIC_FRONTIER,
    }
    if name in mapping:
        return mapping[name]
    raise GraphHistoryAdmissionError(
        f"unsupported history record type {name} schema={schema!r}"
    )


def _decode_payload(kind: GraphHistoryKind, payload: Mapping[str, Any]) -> Any:
    if kind is GraphHistoryKind.TRANSITION_LOG_HEAD:
        return TransitionLogHead.from_dict(payload)
    if kind is GraphHistoryKind.WORLD_SNAPSHOT:
        return SemanticWorldSnapshot.from_dict(payload)
    if kind is GraphHistoryKind.LEAF_SUBROOT:
        return dict(payload)
    if kind is GraphHistoryKind.WORLD_ROOT_MANIFEST:
        from ipfs_kit_py.semantic_world_store.world_roots import (
            SemanticWorldRootManifest,
        )

        return SemanticWorldRootManifest.from_dict(payload)
    try:
        if kind in {
            GraphHistoryKind.GRAPH_NODE,
            GraphHistoryKind.GRAPH_EDGE,
            GraphHistoryKind.GRAPH_SNAPSHOT,
            GraphHistoryKind.GRAPH_DELTA,
            GraphHistoryKind.CALLSITE,
            GraphHistoryKind.FUNCTION_SYMBOL,
            GraphHistoryKind.CONTRACT_STATE,
            GraphHistoryKind.PROOF_OBLIGATION_GRAPH,
            GraphHistoryKind.STATIC_SUCCESSOR_SET,
            GraphHistoryKind.DYNAMIC_FRONTIER,
        }:
            return decode_program_graph_record(payload)
        if kind in {
            GraphHistoryKind.TRANSITION_QUERY,
            GraphHistoryKind.TRANSITION_CANDIDATE,
            GraphHistoryKind.TRANSITION_PREDICTION,
            GraphHistoryKind.TRANSITION_OBSERVATION,
            GraphHistoryKind.TRANSITION_ADMISSION,
            GraphHistoryKind.TRANSITION_RECEIPT,
            GraphHistoryKind.TRANSITION_MODEL_PROFILE,
        }:
            return decode_transition_record(payload)
        return decode_identity_record(payload)
    except _DATASETS_ERRORS as exc:
        raise GraphHistoryIntegrityError(str(exc)) from exc


def _is_verified_semantic_store(store: object) -> bool:
    if isinstance(store, VerifiedSemanticBlockStore):
        return True
    if getattr(store, "INTERFACE", None) != VERIFIED_SEMANTIC_STORE_INTERFACE:
        return False
    return callable(getattr(store, "get_verified_block", None))


# ---------------------------------------------------------------------------
# Identity / operation index
# ---------------------------------------------------------------------------


class _HistoryIdentityIndex:
    """Rebuildable identity/operation bindings next to the coordination root."""

    def __init__(self, store: DurableCoordinationStore) -> None:
        self._path = store.root / HISTORY_INDEX_DB_NAME
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

    def iter_identities(self) -> tuple[tuple[str, str, str], ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT identity_cid, storage_cid, kind FROM identity_bindings "
                "ORDER BY identity_cid"
            ).fetchall()
        return tuple(
            (str(row["identity_cid"]), str(row["storage_cid"]), str(row["kind"]))
            for row in rows
        )

    def bind_identity(self, identity_cid: str, storage_cid: str, kind: str) -> None:
        with self._lock:
            existing = self._connection.execute(
                "SELECT storage_cid, kind FROM identity_bindings WHERE identity_cid = ?",
                (identity_cid,),
            ).fetchone()
            if existing is not None:
                if str(existing["storage_cid"]) != storage_cid or str(existing["kind"]) != kind:
                    raise GraphHistoryConflictError(
                        f"identity {identity_cid!r} already bound to a different artifact"
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
                        f"operation_id {operation_id!r} already bound to a different artifact"
                    )
                return
            with self._connection:
                self._connection.execute(
                    "INSERT INTO history_operations"
                    "(operation_id, identity_cid, storage_cid, kind) VALUES(?,?,?,?)",
                    (operation_id, identity_cid, storage_cid, kind),
                )


# ---------------------------------------------------------------------------
# Sealed history-block store
# ---------------------------------------------------------------------------


def seal_history_block(
    kind: GraphHistoryKind | str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the closed, content-addressed storage envelope for a history payload."""

    artifact_kind = _coerce_kind(kind)
    if not isinstance(payload, Mapping):
        raise GraphHistoryAdmissionError("payload must be a mapping")
    body = dict(payload)
    _require_structured_json_value(body, path="payload")
    try:
        reject_private_raw_source(body, path="payload")
    except SemanticWorldArtifactAdmissionError as exc:
        raise GraphHistoryAdmissionError(str(exc)) from exc
    _reject_score_derived_identity(body, path="payload")
    sealed = {
        "schema": HISTORY_BLOCK_SCHEMA,
        "interface_id": HISTORY_BLOCK_INTERFACE,
        "kind": artifact_kind.value,
        "payload": body,
    }
    data = _canonical_bytes(sealed)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise GraphHistoryAdmissionError(
            f"history artifact exceeds MAX_ARTIFACT_BYTES "
            f"({len(data)} > {MAX_ARTIFACT_BYTES})"
        )
    return sealed


def admit_history_block(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a retrieved sealed history envelope."""

    if not isinstance(record, Mapping):
        raise GraphHistoryIntegrityError("sealed history artifact must be a mapping")
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
            "sealed history artifact has " + "; ".join(problems)
        )
    if record.get("schema") != HISTORY_BLOCK_SCHEMA:
        raise GraphHistoryIntegrityError("unknown history artifact schema")
    if record.get("interface_id") != HISTORY_BLOCK_INTERFACE:
        raise GraphHistoryIntegrityError("unknown history artifact interface_id")
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
    except (GraphHistoryAdmissionError, SemanticWorldArtifactAdmissionError) as exc:
        raise GraphHistoryIntegrityError(str(exc)) from exc
    sealed = {
        "schema": HISTORY_BLOCK_SCHEMA,
        "interface_id": HISTORY_BLOCK_INTERFACE,
        "kind": kind.value,
        "payload": body,
    }
    if cid_for_artifact(dict(record)) != cid_for_artifact(sealed):
        raise GraphHistoryIntegrityError("sealed history artifact is not canonical")
    return sealed


class SemanticWorldHistoryBlockStore:
    """Typed immutable history blocks over ``DurableCoordinationStore``."""

    def __init__(
        self,
        store: DurableCoordinationStore | VerifiedSemanticBlockStore,
    ) -> None:
        if _is_verified_semantic_store(store):
            self._verified: VerifiedSemanticBlockStore | None = store  # type: ignore[assignment]
            self._store = store.store  # type: ignore[union-attr]
            self._owns_verified = False
        elif isinstance(store, DurableCoordinationStore):
            self._store = store
            self._verified = VerifiedSemanticBlockStore(store)
            self._owns_verified = True
        else:
            raise TypeError(
                "store must be a DurableCoordinationStore or VerifiedSemanticBlockStore"
            )
        self._index = _HistoryIdentityIndex(self._store)
        self._rebuild_identity_index()

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    @property
    def verified(self) -> VerifiedSemanticBlockStore | None:
        return self._verified

    def close(self) -> None:
        self._index.close()
        if self._owns_verified and self._verified is not None:
            self._verified.close()

    def __enter__(self) -> "SemanticWorldHistoryBlockStore":
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
            if not isinstance(raw, Mapping) or raw.get("schema") != HISTORY_BLOCK_SCHEMA:
                continue
            try:
                sealed = admit_history_block(raw)
                kind = _coerce_kind(sealed["kind"])
                identity_cid = _identity_cid_from_payload(kind, sealed["payload"])
                self._index.bind_identity(identity_cid, storage_cid, kind.value)
            except (GraphHistoryError, SemanticGovernorStoreContractError):
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

    def lookup_kind(self, cid: str) -> str | None:
        bound = self._index.lookup_identity(cid)
        if bound is not None:
            return bound[1]
        storage = self._index.lookup_storage(cid)
        if storage is not None:
            return storage[1]
        return None

    def has_identity(self, cid: str) -> bool:
        return self._index.lookup_identity(cid) is not None

    def is_stored(self, cid: str) -> bool:
        """True when CID is a stored history identity, storage CID, or verified block."""

        try:
            cid = validate_verified_cid(cid, "cid")
        except SemanticGovernorStoreContractError:
            return False
        if self._index.lookup_identity(cid) is not None:
            return True
        if self._index.lookup_storage(cid) is not None:
            return True
        if self._store.has(cid):
            return True
        if self._verified is not None:
            try:
                self._verified.get_verified_block(cid)
                return True
            except VerifiedSemanticStoreNotFound:
                return False
            except VerifiedSemanticStoreIntegrityError:
                raise
        return False

    def require_stored(
        self,
        cid: str,
        *,
        kinds: Iterable[str] | None = None,
        field: str = "cid",
    ) -> None:
        if type(cid) is not str or not cid:
            raise GraphHistoryAdmissionError(
                f"store-before-reference: {field} is not a stored CID"
            )
        bound = self._index.lookup_identity(cid)
        if bound is not None:
            if kinds is not None and bound[1] not in set(kinds):
                raise GraphHistoryAdmissionError(
                    f"store-before-reference: {field} has kind {bound[1]!r}, "
                    f"expected one of {sorted(set(kinds))}"
                )
            return
        if kinds is not None:
            raise GraphHistoryAdmissionError(
                f"store-before-reference: {field} is not a stored {sorted(set(kinds))} record"
            )
        if self.is_stored(cid):
            return
        raise GraphHistoryAdmissionError(
            f"store-before-reference: {field} is not stored"
        )

    def put_payload(
        self,
        kind: GraphHistoryKind | str,
        payload: Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> GraphHistoryWriteResult:
        artifact_kind = _coerce_kind(kind)
        sealed = seal_history_block(artifact_kind, payload)
        identity_cid = _identity_cid_from_payload(artifact_kind, sealed["payload"])
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
                        f"operation_id {operation_id!r} already bound to a different artifact"
                    )
        prior = self._index.lookup_identity(identity_cid)
        if prior is not None:
            prior_storage, prior_kind = prior
            if prior_storage != storage_cid or prior_kind != artifact_kind.value:
                raise GraphHistoryConflictError(
                    f"identity {identity_cid!r} already bound to a different artifact"
                )
            self.get_verified_payload(identity_cid, expected_kind=artifact_kind)
            if operation_id is not None:
                self._index.bind_operation(
                    operation_id, identity_cid, storage_cid, artifact_kind.value
                )
            return GraphHistoryWriteResult(
                identity_cid,
                storage_cid,
                artifact_kind.value,
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
                return GraphHistoryWriteResult(
                    identity_cid,
                    storage_cid,
                    artifact_kind.value,
                    created,
                    True,
                    "provider_failed",
                )
        reason = "stored" if created else "unchanged"
        if replicate and self._store.backend is None:
            reason = "provider_unavailable"
        return GraphHistoryWriteResult(
            identity_cid,
            storage_cid,
            artifact_kind.value,
            created,
            True,
            reason,
        )

    def get_verified_payload(
        self,
        cid: str,
        *,
        expected_kind: GraphHistoryKind | str | None = None,
    ) -> Mapping[str, Any]:
        try:
            cid = validate_verified_cid(cid, "cid")
        except SemanticGovernorStoreContractError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        bound = self._index.lookup_identity(cid)
        indexed_kind: str | None = None
        if bound is not None:
            storage_cid, indexed_kind = bound
        else:
            storage_bound = self._index.lookup_storage(cid)
            if storage_bound is not None:
                storage_cid = cid
                indexed_kind = storage_bound[1]
            elif self._store.has(cid):
                storage_cid = cid
            else:
                raise GraphHistoryNotFound(cid)
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
        sealed = admit_history_block(raw)
        recomputed = cid_for_artifact(sealed)
        if recomputed != storage_cid:
            raise GraphHistoryIntegrityError(
                f"forged sealed history artifact: recomputed {recomputed}, "
                f"expected {storage_cid}"
            )
        kind = _coerce_kind(sealed["kind"])
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
        identity_cid = _identity_cid_from_payload(kind, sealed["payload"])
        self._index.bind_identity(identity_cid, storage_cid, kind.value)
        return MappingProxyType(
            {
                "schema": sealed["schema"],
                "interface_id": sealed["interface_id"],
                "kind": kind.value,
                "payload": MappingProxyType(dict(sealed["payload"])),
                "storage_cid": storage_cid,
                "identity_cid": identity_cid,
            }
        )

    def get_verified_record(
        self,
        cid: str,
        *,
        expected_kind: GraphHistoryKind | str | None = None,
    ) -> Any:
        artifact = self.get_verified_payload(cid, expected_kind=expected_kind)
        record = _decode_payload(_coerce_kind(artifact["kind"]), dict(artifact["payload"]))
        if artifact["kind"] != GraphHistoryKind.LEAF_SUBROOT.value:
            computed = _record_cid(record)
            if computed != artifact["identity_cid"]:
                raise GraphHistoryIntegrityError(
                    "history record CID does not rehash canonical identity bytes"
                )
        return record


def as_history_store(
    store: SemanticWorldHistoryBlockStore
    | DurableCoordinationStore
    | VerifiedSemanticBlockStore
    | "LogicalProgramGraphStore"
    | "ProgramTransitionLog"
    | "ProgramGraphHistory",
) -> SemanticWorldHistoryBlockStore:
    if isinstance(store, SemanticWorldHistoryBlockStore):
        return store
    blocks = getattr(store, "blocks", None)
    if isinstance(blocks, SemanticWorldHistoryBlockStore):
        return blocks
    history = getattr(store, "history", None)
    if isinstance(history, SemanticWorldHistoryBlockStore):
        return history
    if isinstance(store, (DurableCoordinationStore, VerifiedSemanticBlockStore)) or (
        _is_verified_semantic_store(store)
    ):
        return SemanticWorldHistoryBlockStore(store)
    raise TypeError(
        "store must provide a DurableCoordinationStore, VerifiedSemanticBlockStore, "
        "or SemanticWorldHistoryBlockStore"
    )


# ---------------------------------------------------------------------------
# Logical program graph store
# ---------------------------------------------------------------------------


class LogicalProgramGraphStore:
    """Persist immutable node/edge/snapshot/delta records with store-before-reference."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: SemanticWorldHistoryBlockStore
        | DurableCoordinationStore
        | VerifiedSemanticBlockStore,
    ) -> None:
        self._blocks = as_history_store(store)

    @property
    def blocks(self) -> SemanticWorldHistoryBlockStore:
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

    def _put_record(
        self,
        record: Any,
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        kind = _kind_for_record(record)
        payload = record.to_dict()
        return self._blocks.put_payload(
            kind, payload, expected_cid=_record_cid(record), operation_id=operation_id
        )

    def put_node(
        self, node: ProgramGraphNode | Mapping[str, Any], *, operation_id: str | None = None
    ) -> GraphHistoryWriteResult:
        if not isinstance(node, ProgramGraphNode):
            try:
                node = ProgramGraphNode.from_dict(node)
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        if node.record_cid is not None:
            self._blocks.require_stored(node.record_cid, field="record_cid")
        if node.subject_cid is not None:
            self._blocks.require_stored(node.subject_cid, field="subject_cid")
        return self._put_record(node, operation_id=operation_id)

    def put_edge(
        self, edge: ProgramGraphEdge | Mapping[str, Any], *, operation_id: str | None = None
    ) -> GraphHistoryWriteResult:
        if not isinstance(edge, ProgramGraphEdge):
            try:
                edge = ProgramGraphEdge.from_dict(edge)
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        self._blocks.require_stored(
            edge.source_node_cid, kinds=_GRAPH_NODE_KINDS, field="source_node_cid"
        )
        self._blocks.require_stored(
            edge.target_node_cid, kinds=_GRAPH_NODE_KINDS, field="target_node_cid"
        )
        return self._put_record(edge, operation_id=operation_id)

    def put_canonical_graph(
        self,
        identity: CanonicalProgramGraphIdentity | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(identity, CanonicalProgramGraphIdentity):
            try:
                identity = CanonicalProgramGraphIdentity.from_dict(identity)
            except ProgramIdentityError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        for cid in identity.node_cids:
            self._blocks.require_stored(cid, kinds=_GRAPH_NODE_KINDS, field="node_cids")
        for cid in identity.edge_cids:
            self._blocks.require_stored(cid, kinds=_GRAPH_EDGE_KINDS, field="edge_cids")
        if identity.environment_binding_set_cid is not None:
            self._blocks.require_stored(
                identity.environment_binding_set_cid,
                field="environment_binding_set_cid",
            )
        return self._put_record(identity, operation_id=operation_id)

    def put_snapshot(
        self,
        snapshot: ProgramGraphSnapshot | Mapping[str, Any],
        *,
        nodes: Sequence[ProgramGraphNode] = (),
        edges: Sequence[ProgramGraphEdge] = (),
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(snapshot, ProgramGraphSnapshot):
            try:
                snapshot = ProgramGraphSnapshot.from_dict(snapshot)
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        if nodes or edges:
            try:
                verify_program_graph_catalog(snapshot, nodes=nodes, edges=edges)
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        for cid in snapshot.node_cids:
            self._blocks.require_stored(cid, kinds=_GRAPH_NODE_KINDS, field="node_cids")
        for cid in snapshot.edge_cids:
            self._blocks.require_stored(cid, kinds=_GRAPH_EDGE_KINDS, field="edge_cids")
        self._blocks.require_stored(
            snapshot.canonical_program_graph_cid,
            kinds={GraphHistoryKind.CANONICAL_PROGRAM_GRAPH.value},
            field="canonical_program_graph_cid",
        )
        self._blocks.require_stored(
            snapshot.environment_binding_set_cid, field="environment_binding_set_cid"
        )
        self._blocks.require_stored(
            snapshot.sealed_binding_cid, field="sealed_binding_cid"
        )
        for cid in snapshot.retained_subroot_cids:
            self._blocks.require_stored(
                cid, kinds=_GRAPH_NODE_KINDS, field="retained_subroot_cids"
            )
        for field_name, values in (
            ("callsite_cids", snapshot.callsite_cids),
            ("function_symbol_cids", snapshot.function_symbol_cids),
            ("contract_state_cids", snapshot.contract_state_cids),
            ("proof_obligation_graph_cids", snapshot.proof_obligation_graph_cids),
            ("successor_set_cids", snapshot.successor_set_cids),
            ("frontier_cids", snapshot.frontier_cids),
        ):
            for cid in values:
                self._blocks.require_stored(cid, field=field_name)
        identity = ProgramGraphSnapshotIdentity.from_dict(snapshot.to_identity_record())
        self._put_record(identity)
        catalog = self._physical_catalog()
        catalog[snapshot.program_graph_snapshot_cid] = snapshot.identity_payload()
        try:
            assert_physical_dag_acyclic(catalog)
        except ProgramGraphError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        return self._put_record(snapshot, operation_id=operation_id)

    def put_delta(
        self,
        delta: ProgramGraphDelta | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(delta, ProgramGraphDelta):
            try:
                delta = ProgramGraphDelta.from_dict(delta)
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        self._blocks.require_stored(
            delta.previous_snapshot_cid,
            kinds=_SNAPSHOT_KINDS,
            field="previous_snapshot_cid",
        )
        for cid in delta.added_node_cids:
            self._blocks.require_stored(
                cid, kinds=_GRAPH_NODE_KINDS, field="added_node_cids"
            )
        for cid in delta.added_edge_cids:
            self._blocks.require_stored(
                cid, kinds=_GRAPH_EDGE_KINDS, field="added_edge_cids"
            )
        for cid in delta.retained_subroot_cids:
            self._blocks.require_stored(
                cid, kinds=_GRAPH_NODE_KINDS, field="retained_subroot_cids"
            )
        identity = ProgramGraphDeltaIdentity.from_dict(delta.to_identity_record())
        self._put_record(identity)
        return self._put_record(delta, operation_id=operation_id)

    def append_snapshot(
        self,
        snapshot: ProgramGraphSnapshot | Mapping[str, Any] | None = None,
        *,
        nodes: Sequence[ProgramGraphNode] = (),
        edges: Sequence[ProgramGraphEdge] = (),
        previous_snapshot: ProgramGraphSnapshot | None = None,
        specialized: Sequence[Any] = (),
        environment_binding_set_cid: str | None = None,
        sealed_binding_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        """Store nodes, edges, canonical graph, snapshot, and optional delta."""

        for record in specialized:
            self._put_record(record)
        node_records = list(nodes)
        edge_records = list(edges)
        for node in node_records:
            self.put_node(node)
        for edge in edge_records:
            self.put_edge(edge)
        if snapshot is None:
            if not node_records:
                raise GraphHistoryAdmissionError(
                    "append_program_graph_snapshot requires nodes or a snapshot"
                )
            if environment_binding_set_cid is None or sealed_binding_cid is None:
                raise GraphHistoryAdmissionError(
                    "assembling a snapshot requires environment and sealed binding CIDs"
                )
            try:
                snapshot = assemble_program_graph_snapshot(
                    nodes=node_records,
                    edges=edge_records,
                    environment_binding_set_cid=environment_binding_set_cid,
                    sealed_binding_cid=sealed_binding_cid,
                )
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        elif not isinstance(snapshot, ProgramGraphSnapshot):
            try:
                snapshot = ProgramGraphSnapshot.from_dict(snapshot)
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
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
                "canonical_program_graph_cid does not rehash snapshot node/edge sets"
            )
        self.put_canonical_graph(canonical)
        result = self.put_snapshot(
            snapshot, nodes=node_records, edges=edge_records, operation_id=operation_id
        )
        if previous_snapshot is not None:
            try:
                delta = delta_between_snapshots(previous_snapshot, snapshot)
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
            self.put_delta(delta)
        return result

    def get_node(self, cid: str) -> ProgramGraphNode:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.GRAPH_NODE
        )
        if not isinstance(record, ProgramGraphNode):
            raise GraphHistoryIntegrityError("stored graph_node did not decode")
        return record

    def get_edge(self, cid: str) -> ProgramGraphEdge:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.GRAPH_EDGE
        )
        if not isinstance(record, ProgramGraphEdge):
            raise GraphHistoryIntegrityError("stored graph_edge did not decode")
        return record

    def get_snapshot(self, cid: str) -> ProgramGraphSnapshot:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.GRAPH_SNAPSHOT
        )
        if not isinstance(record, ProgramGraphSnapshot):
            raise GraphHistoryIntegrityError("stored graph_snapshot did not decode")
        return record

    def get_delta(self, cid: str) -> ProgramGraphDelta:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.GRAPH_DELTA
        )
        if not isinstance(record, ProgramGraphDelta):
            raise GraphHistoryIntegrityError("stored graph_delta did not decode")
        return record

    def load_snapshot_edges(self, snapshot: ProgramGraphSnapshot) -> tuple[ProgramGraphEdge, ...]:
        return tuple(self.get_edge(cid) for cid in snapshot.edge_cids)

    def load_snapshot_nodes(self, snapshot: ProgramGraphSnapshot) -> tuple[ProgramGraphNode, ...]:
        return tuple(self.get_node(cid) for cid in snapshot.node_cids)

    def query_logical_cycles(
        self, snapshot: ProgramGraphSnapshot | str
    ) -> tuple[tuple[str, ...], ...]:
        """Return directed logical cycles; physical IPLD remains acyclic."""

        if isinstance(snapshot, str):
            snapshot = self.get_snapshot(snapshot)
        edges = self.load_snapshot_edges(snapshot)
        catalog = {
            node.program_graph_node_cid: node.identity_payload()
            for node in self.load_snapshot_nodes(snapshot)
        }
        for edge in edges:
            catalog[edge.program_graph_edge_cid] = edge.identity_payload()
        catalog[snapshot.program_graph_snapshot_cid] = snapshot.identity_payload()
        try:
            assert_physical_dag_acyclic(catalog)
        except ProgramGraphError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        return directed_logical_cycles(edges)

    def _physical_catalog(self) -> dict[str, Mapping[str, Any]]:
        catalog: dict[str, Mapping[str, Any]] = {}
        for identity_cid, _storage_cid, kind in self._blocks._index.iter_identities():
            if kind not in {
                GraphHistoryKind.GRAPH_NODE.value,
                GraphHistoryKind.GRAPH_EDGE.value,
                GraphHistoryKind.GRAPH_SNAPSHOT.value,
                GraphHistoryKind.GRAPH_DELTA.value,
                GraphHistoryKind.CANONICAL_PROGRAM_GRAPH.value,
            }:
                continue
            artifact = self._blocks.get_verified_payload(identity_cid)
            catalog[identity_cid] = dict(artifact["payload"])
        return catalog

    def assert_physical_ipld_acyclic(self) -> None:
        try:
            assert_physical_dag_acyclic(self._physical_catalog())
        except ProgramGraphError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Transition log
# ---------------------------------------------------------------------------


class ProgramTransitionLog:
    """Append-only prediction/observation/admission/receipt history."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: SemanticWorldHistoryBlockStore
        | DurableCoordinationStore
        | VerifiedSemanticBlockStore
        | LogicalProgramGraphStore,
    ) -> None:
        self._blocks = as_history_store(store)

    @property
    def blocks(self) -> SemanticWorldHistoryBlockStore:
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

    def _put_record(
        self, record: Any, *, operation_id: str | None = None
    ) -> GraphHistoryWriteResult:
        kind = _kind_for_record(record)
        return self._blocks.put_payload(
            kind,
            record.to_dict(),
            expected_cid=_record_cid(record),
            operation_id=operation_id,
        )

    def put_event(
        self, event: ProgramEventIdentity | Mapping[str, Any], *, operation_id: str | None = None
    ) -> GraphHistoryWriteResult:
        if not isinstance(event, ProgramEventIdentity):
            try:
                event = ProgramEventIdentity.from_dict(event)
            except ProgramIdentityError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        self._blocks.require_stored(event.subject_cid, field="subject_cid")
        if event.predecessor_event_cid is not None:
            self._blocks.require_stored(
                event.predecessor_event_cid,
                kinds=_EVENT_KINDS,
                field="predecessor_event_cid",
            )
        return self._put_record(event, operation_id=operation_id)

    def put_trace(
        self,
        trace: ExecutionTraceIdentity | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(trace, ExecutionTraceIdentity):
            try:
                trace = ExecutionTraceIdentity.from_dict(trace)
            except ProgramIdentityError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        for cid in trace.event_cids:
            self._blocks.require_stored(cid, kinds=_EVENT_KINDS, field="event_cids")
        for cid in trace.segment_cids:
            self._blocks.require_stored(cid, field="segment_cids")
        for cid in trace.raw_execution_state_cids:
            self._blocks.require_stored(cid, field="raw_execution_state_cids")
        return self._put_record(trace, operation_id=operation_id)

    def put_query(
        self,
        query: ProgramTransitionQuery | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(query, ProgramTransitionQuery):
            try:
                query = ProgramTransitionQuery.from_dict(query)
            except ProgramTransitionError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        for field_name in (
            "subject_cid",
            "current_source_cid",
            "environment_binding_cid",
            "policy_cid",
        ):
            self._blocks.require_stored(getattr(query, field_name), field=field_name)
        for optional in (
            "current_graph_cid",
            "current_state_cid",
            "current_trace_cid",
            "abstraction_profile_cid",
        ):
            value = getattr(query, optional)
            if value is not None:
                self._blocks.require_stored(value, field=optional)
        result = self._put_record(query, operation_id=operation_id)
        self._put_record(TransitionIdentity.from_dict(query.to_identity_record()))
        return result

    def put_model_profile(
        self,
        profile: TransitionModelProfile | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(profile, TransitionModelProfile):
            try:
                profile = TransitionModelProfile.from_dict(profile)
            except ProgramTransitionError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        if not profile.proposal_only:
            raise GraphHistoryAdmissionError("model profiles are proposal-only")
        return self._put_record(profile, operation_id=operation_id)

    def put_candidate(
        self,
        candidate: ProgramTransitionCandidate | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(candidate, ProgramTransitionCandidate):
            try:
                candidate = ProgramTransitionCandidate.from_dict(candidate)
            except ProgramTransitionError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        self._blocks.require_stored(
            candidate.query_cid,
            kinds={GraphHistoryKind.TRANSITION_QUERY.value},
            field="query_cid",
        )
        return self._put_record(candidate, operation_id=operation_id)

    def put_prediction(
        self,
        prediction: ProgramTransitionPrediction | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(prediction, ProgramTransitionPrediction):
            try:
                prediction = ProgramTransitionPrediction.from_dict(prediction)
            except ProgramTransitionError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        if not prediction.proposal_only:
            raise GraphHistoryAdmissionError("predictions are proposal-only")
        if prediction.establishes_observation or prediction.self_admitted:
            raise GraphHistoryAdmissionError(
                "predictions cannot establish observation or self-admit"
            )
        self._blocks.require_stored(
            prediction.query_cid,
            kinds={GraphHistoryKind.TRANSITION_QUERY.value},
            field="query_cid",
        )
        self._blocks.require_stored(
            prediction.model_profile_cid,
            kinds={GraphHistoryKind.TRANSITION_MODEL_PROFILE.value},
            field="model_profile_cid",
        )
        for cid in prediction.candidate_cids:
            self._blocks.require_stored(
                cid,
                kinds={GraphHistoryKind.TRANSITION_CANDIDATE.value},
                field="candidate_cids",
            )
        result = self._put_record(prediction, operation_id=operation_id)
        self._put_record(TransitionIdentity.from_dict(prediction.to_identity_record()))
        return result

    def put_observation(
        self,
        observation: ProgramTransitionObservation | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(observation, ProgramTransitionObservation):
            try:
                observation = decode_transition_observation(observation)
            except ProgramTransitionError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        if observation.proposal_only:
            raise GraphHistoryAdmissionError("observations cannot be proposal-only")
        self._blocks.require_stored(
            observation.query_cid,
            kinds={GraphHistoryKind.TRANSITION_QUERY.value},
            field="query_cid",
        )
        self._blocks.require_stored(observation.observed_cid, field="observed_cid")
        result = self._put_record(observation, operation_id=operation_id)
        self._put_record(TransitionIdentity.from_dict(observation.to_identity_record()))
        return result

    def put_admission(
        self,
        admission: ProgramTransitionAdmission | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(admission, ProgramTransitionAdmission):
            try:
                admission = ProgramTransitionAdmission.from_dict(admission)
            except ProgramTransitionError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        self._blocks.require_stored(
            admission.query_cid,
            kinds={GraphHistoryKind.TRANSITION_QUERY.value},
            field="query_cid",
        )
        self._blocks.require_stored(admission.policy_cid, field="policy_cid")
        if admission.prediction_cid is not None:
            self._blocks.require_stored(
                admission.prediction_cid,
                kinds=_PREDICTION_KINDS,
                field="prediction_cid",
            )
        if admission.observation_cid is not None:
            self._blocks.require_stored(
                admission.observation_cid,
                kinds=_OBSERVATION_KINDS,
                field="observation_cid",
            )
        result = self._put_record(admission, operation_id=operation_id)
        self._put_record(TransitionIdentity.from_dict(admission.to_identity_record()))
        return result

    def put_receipt(
        self,
        receipt: ProgramTransitionReceipt | Mapping[str, Any],
        *,
        previous_head_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(receipt, ProgramTransitionReceipt):
            try:
                receipt = ProgramTransitionReceipt.from_dict(receipt)
            except ProgramTransitionError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        if receipt.prediction_authoritative:
            raise GraphHistoryAdmissionError(
                "receipts cannot treat predictions as authoritative"
            )
        self._blocks.require_stored(
            receipt.query_cid,
            kinds={GraphHistoryKind.TRANSITION_QUERY.value},
            field="query_cid",
        )
        self._blocks.require_stored(
            receipt.admission_cid,
            kinds={GraphHistoryKind.TRANSITION_ADMISSION.value},
            field="admission_cid",
        )
        if receipt.prediction_cid is not None:
            self._blocks.require_stored(
                receipt.prediction_cid,
                kinds=_PREDICTION_KINDS,
                field="prediction_cid",
            )
            prediction = self.get_prediction(receipt.prediction_cid)
            if not prediction.proposal_only:
                raise GraphHistoryIntegrityError("stored prediction lost proposal-only")
        if receipt.observation_cid is not None:
            self._blocks.require_stored(
                receipt.observation_cid,
                kinds=_OBSERVATION_KINDS,
                field="observation_cid",
            )
            observation = self.get_observation(receipt.observation_cid)
            if observation.proposal_only:
                raise GraphHistoryIntegrityError("stored observation is proposal-only")
        if (
            receipt.prediction_cid is not None
            and receipt.observation_cid is not None
            and receipt.prediction_cid == receipt.observation_cid
        ):
            raise GraphHistoryAdmissionError(
                "predictions are distinguishable from admitted observations"
            )
        result = self._put_record(receipt, operation_id=operation_id)
        ordinal = 1
        if previous_head_cid is not None:
            previous = self.get_log_head(previous_head_cid)
            ordinal = previous.ordinal + 1
            self._blocks.require_stored(
                previous_head_cid,
                kinds={GraphHistoryKind.TRANSITION_LOG_HEAD.value},
                field="previous_head_cid",
            )
        head = TransitionLogHead(
            receipt_cid=receipt.receipt_cid,
            previous_head_cid=previous_head_cid,
            ordinal=ordinal,
        )
        self._put_record(head)
        return result

    def get_prediction(self, cid: str) -> ProgramTransitionPrediction:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.TRANSITION_PREDICTION
        )
        if not isinstance(record, ProgramTransitionPrediction):
            raise GraphHistoryIntegrityError("stored prediction did not decode")
        return record

    def get_observation(self, cid: str) -> ProgramTransitionObservation:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.TRANSITION_OBSERVATION
        )
        if not isinstance(record, ProgramTransitionObservation):
            raise GraphHistoryIntegrityError("stored observation did not decode")
        return record

    def get_receipt(self, cid: str) -> ProgramTransitionReceipt:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.TRANSITION_RECEIPT
        )
        if not isinstance(record, ProgramTransitionReceipt):
            raise GraphHistoryIntegrityError("stored receipt did not decode")
        return record

    def get_log_head(self, cid: str) -> TransitionLogHead:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.TRANSITION_LOG_HEAD
        )
        if not isinstance(record, TransitionLogHead):
            raise GraphHistoryIntegrityError("stored log head did not decode")
        return record

    def get_event(self, cid: str) -> ProgramEventIdentity:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.PROGRAM_EVENT
        )
        if not isinstance(record, ProgramEventIdentity):
            raise GraphHistoryIntegrityError("stored program event did not decode")
        return record

    def get_trace(self, cid: str) -> ExecutionTraceIdentity:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.EXECUTION_TRACE
        )
        if not isinstance(record, ExecutionTraceIdentity):
            raise GraphHistoryIntegrityError("stored execution trace did not decode")
        return record

    def get_transition_identity(self, cid: str) -> TransitionIdentity:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.TRANSITION_IDENTITY
        )
        if not isinstance(record, TransitionIdentity):
            raise GraphHistoryIntegrityError("stored transition identity did not decode")
        return record

    def head_for_receipt(self, receipt_cid: str) -> TransitionLogHead:
        """Return the highest-ordinal immutable log head that cites this receipt."""

        matches: list[TransitionLogHead] = []
        for identity_cid, _storage_cid, kind in self._blocks._index.iter_identities():
            if kind != GraphHistoryKind.TRANSITION_LOG_HEAD.value:
                continue
            head = self.get_log_head(identity_cid)
            if head.receipt_cid == receipt_cid:
                matches.append(head)
        if not matches:
            raise GraphHistoryNotFound(receipt_cid)
        return max(matches, key=lambda item: item.ordinal)

    def iter_receipt_history(self, head_cid: str) -> tuple[ProgramTransitionReceipt, ...]:
        """Walk the immutable log from head to genesis; order is oldest-first."""

        receipts: list[ProgramTransitionReceipt] = []
        current: str | None = head_cid
        seen: set[str] = set()
        while current is not None:
            if current in seen:
                raise GraphHistoryIntegrityError(
                    "physical IPLD block graph must be acyclic"
                )
            seen.add(current)
            head = self.get_log_head(current)
            receipts.append(self.get_receipt(head.receipt_cid))
            current = head.previous_head_cid
        receipts.reverse()
        return tuple(receipts)


# ---------------------------------------------------------------------------
# World snapshot store
# ---------------------------------------------------------------------------


class SemanticWorldSnapshotStore:
    """Persist world snapshots that bind graph, traces, and transition evidence."""

    INTERFACE: ClassVar[str] = WORLD_SNAPSHOT_INTERFACE

    def __init__(
        self,
        store: SemanticWorldHistoryBlockStore
        | DurableCoordinationStore
        | VerifiedSemanticBlockStore
        | LogicalProgramGraphStore
        | ProgramTransitionLog,
    ) -> None:
        self._blocks = as_history_store(store)

    @property
    def blocks(self) -> SemanticWorldHistoryBlockStore:
        return self._blocks

    def close(self) -> None:
        self._blocks.close()

    def put_leaf_subroot(
        self,
        kind: str,
        body: Mapping[str, Any] | None = None,
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if type(kind) is not str or not kind:
            raise GraphHistoryAdmissionError("leaf subroot kind must be a nonempty string")
        payload = {
            "schema": LEAF_SUBROOT_SCHEMA,
            "kind": kind,
            "body": dict(body or {}),
        }
        payload["subroot_cid"] = cid_for_artifact(
            {key: value for key, value in payload.items() if key != "subroot_cid"}
        )
        return self._blocks.put_payload(
            GraphHistoryKind.LEAF_SUBROOT,
            payload,
            expected_cid=payload["subroot_cid"],
            operation_id=operation_id,
        )

    def put_snapshot(
        self,
        snapshot: SemanticWorldSnapshot | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(snapshot, SemanticWorldSnapshot):
            snapshot = SemanticWorldSnapshot.from_dict(snapshot)
        for cid in snapshot.referenced_subroot_cids():
            self._blocks.require_stored(cid, field="world_snapshot_subroot")
        return self._blocks.put_payload(
            GraphHistoryKind.WORLD_SNAPSHOT,
            snapshot.to_dict(),
            expected_cid=snapshot.world_snapshot_cid,
            operation_id=operation_id,
        )

    def get_snapshot(self, cid: str) -> SemanticWorldSnapshot:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.WORLD_SNAPSHOT
        )
        if not isinstance(record, SemanticWorldSnapshot):
            raise GraphHistoryIntegrityError("stored world snapshot did not decode")
        return record


# ---------------------------------------------------------------------------
# Facade and public interfaces
# ---------------------------------------------------------------------------


class ProgramGraphHistory:
    """ProgramGraphHistory@1: logical snapshots, traces, and transition log."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: SemanticWorldHistoryBlockStore
        | DurableCoordinationStore
        | VerifiedSemanticBlockStore
        | LogicalProgramGraphStore
        | ProgramTransitionLog,
    ) -> None:
        self._blocks = as_history_store(store)
        self.graphs = LogicalProgramGraphStore(self._blocks)
        self.transitions = ProgramTransitionLog(self._blocks)
        self.world_snapshots = SemanticWorldSnapshotStore(self._blocks)

    @property
    def blocks(self) -> SemanticWorldHistoryBlockStore:
        return self._blocks

    @property
    def store(self) -> DurableCoordinationStore:
        return self._blocks.store

    def close(self) -> None:
        self._blocks.close()

    def __enter__(self) -> "ProgramGraphHistory":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def _as_program_graph_history(
    store: ProgramGraphHistory
    | LogicalProgramGraphStore
    | ProgramTransitionLog
    | SemanticWorldHistoryBlockStore
    | DurableCoordinationStore
    | VerifiedSemanticBlockStore,
) -> ProgramGraphHistory:
    if isinstance(store, ProgramGraphHistory):
        return store
    return ProgramGraphHistory(as_history_store(store))


def append_program_graph_snapshot(
    store: ProgramGraphHistory
    | LogicalProgramGraphStore
    | SemanticWorldHistoryBlockStore
    | DurableCoordinationStore
    | VerifiedSemanticBlockStore,
    snapshot: ProgramGraphSnapshot | Mapping[str, Any] | None = None,
    *,
    nodes: Sequence[ProgramGraphNode] = (),
    edges: Sequence[ProgramGraphEdge] = (),
    previous_snapshot: ProgramGraphSnapshot | None = None,
    specialized: Sequence[Any] = (),
    environment_binding_set_cid: str | None = None,
    sealed_binding_cid: str | None = None,
    operation_id: str | None = None,
) -> GraphHistoryWriteResult:
    """Persist an immutable logical graph snapshot after its node/edge bytes."""

    history = _as_program_graph_history(store)
    return history.graphs.append_snapshot(
        snapshot,
        nodes=nodes,
        edges=edges,
        previous_snapshot=previous_snapshot,
        specialized=specialized,
        environment_binding_set_cid=environment_binding_set_cid,
        sealed_binding_cid=sealed_binding_cid,
        operation_id=operation_id,
    )


def append_transition_receipt(
    store: ProgramGraphHistory
    | ProgramTransitionLog
    | SemanticWorldHistoryBlockStore
    | DurableCoordinationStore
    | VerifiedSemanticBlockStore,
    receipt: ProgramTransitionReceipt | Mapping[str, Any],
    *,
    query: ProgramTransitionQuery | Mapping[str, Any] | None = None,
    prediction: ProgramTransitionPrediction | Mapping[str, Any] | None = None,
    observation: ProgramTransitionObservation | Mapping[str, Any] | None = None,
    admission: ProgramTransitionAdmission | Mapping[str, Any] | None = None,
    previous_head_cid: str | None = None,
    operation_id: str | None = None,
) -> GraphHistoryWriteResult:
    """Persist a transition receipt after query/prediction/observation/admission."""

    history = _as_program_graph_history(store)
    log = history.transitions
    if query is not None:
        log.put_query(query)
    if prediction is not None:
        log.put_prediction(prediction)
    if observation is not None:
        log.put_observation(observation)
    if admission is not None:
        log.put_admission(admission)
    return log.put_receipt(
        receipt, previous_head_cid=previous_head_cid, operation_id=operation_id
    )


__all__ = [
    "HISTORY_BLOCK_INTERFACE",
    "HISTORY_BLOCK_SCHEMA",
    "PROGRAM_GRAPH_HISTORY_INTERFACE",
    "WORLD_SNAPSHOT_INTERFACE",
    "WORLD_SNAPSHOT_SCHEMA",
    "GraphHistoryAdmissionError",
    "GraphHistoryConflictError",
    "GraphHistoryError",
    "GraphHistoryIntegrityError",
    "GraphHistoryKind",
    "GraphHistoryNotFound",
    "GraphHistoryWriteResult",
    "LogicalProgramGraphStore",
    "ProgramGraphHistory",
    "ProgramTransitionLog",
    "SemanticWorldHistoryBlockStore",
    "SemanticWorldSnapshot",
    "SemanticWorldSnapshotStore",
    "TransitionLogHead",
    "admit_history_block",
    "append_program_graph_snapshot",
    "append_transition_receipt",
    "as_history_store",
    "seal_history_block",
]
