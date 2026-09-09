"""Immutable logical graph snapshots, traces, and transition history.

``LogicalProgramGraphStore``, ``ProgramTransitionLog``, and
``SemanticWorldSnapshotStore`` persist datasets graph/transition/trace
records as sealed kit blocks over ``DurableCoordinationStore``.  Kit
stores bytes and verifies CIDs; it does not admit semantics, decide
prediction truth, or publish a mutable current root.

Authority rules (normative, fail-closed):

* Physical IPLD/Merkle identity is acyclic.  Logical cycles (mutual
  recursion, cyclic imports, CFG/state loops) are queryable immutable
  node/edge records whose identities are independently hashed.
* Every parent record is written only after each referenced child
  identity already exists as verified bytes (store-before-reference).
* Predictions and admitted observations are disjoint stored kinds.
  A prediction cannot decode as an observation and cannot self-admit.
* Repeated states keep distinct event/trace/receipt identities.
* Storage CIDs are minted only by ``coordination_storage.cid_for_bytes``
  / ``cid_for_artifact``.  This module never encodes CIDv1 itself.
* Immutable puts are idempotent: same identity + same bytes is a no-op.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Final, Mapping, Optional, Sequence

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_execution import (
    ExecutionTrace,
    ExecutionTraceSegment,
    ProgramEvent,
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
    ProgramGraphIndexManifest,
    ProgramGraphNode,
    ProgramGraphSnapshot,
    ProofObligationGraph,
    StaticSuccessorSet,
    assemble_program_graph_snapshot,
    assert_physical_dag_acyclic,
    decode_program_graph_record,
    delta_between_snapshots,
    directed_logical_cycles,
    verify_program_graph_catalog,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    CanonicalProgramGraphIdentity,
    ProgramIdentityError,
    SemanticWorldRootIdentity,
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
    TransitionCalibration,
    TransitionModelProfile,
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
    MAX_ARTIFACT_BYTES as _SHARED_MAX_ARTIFACT_BYTES,
    PRIVATE_FIELD_MARKERS,
    SemanticWorldArtifactStore,
    reject_private_raw_source,
)
from ipfs_kit_py.semantic_world_store.verified_store import VerifiedSemanticBlockStore


PROGRAM_GRAPH_HISTORY_INTERFACE: Final[str] = "ProgramGraphHistory@1"
GRAPH_HISTORY_MODULE_INTERFACE: Final[str] = PROGRAM_GRAPH_HISTORY_INTERFACE
GRAPH_HISTORY_STORED_INTERFACE: Final[str] = "SemanticWorldGraphHistoryRecord@1"
GRAPH_HISTORY_STORED_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.graph-history@1"
)
GRAPH_HISTORY_EVIDENCE: Final[str] = "sawm/graph-history@1"
SEMANTIC_WORLD_SNAPSHOT_INTERFACE: Final[str] = "SemanticWorldSnapshot@1"
SEMANTIC_WORLD_SNAPSHOT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-snapshot@1"
)
GRAPH_HISTORY_SCHEMA_VERSION: Final[int] = 1
MAX_HISTORY_BYTES: Final[int] = _SHARED_MAX_ARTIFACT_BYTES
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1

_OPS_DB_NAME: Final[str] = "semantic_world_graph_history.sqlite3"
_SEALED_FIELDS: Final[frozenset[str]] = frozenset(
    ("schema", "interface_id", "kind", "payload")
)

_TRANSITION_REFERENCE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "admission_cid",
        "allowed_operator_cids",
        "allowed_symbol_cids",
        "calibration_cid",
        "candidate_cids",
        "current_graph_cid",
        "current_source_cid",
        "current_state_cid",
        "current_subject_cid",
        "current_trace_cid",
        "environment_binding_cid",
        "evidence_cids",
        "limitation_cids",
        "model_profile_cid",
        "observation_cid",
        "observed_cid",
        "policy_cid",
        "prediction_cid",
        "query_cid",
        "selected_cid",
        "subject_cid",
        "validation_evidence_cids",
    }
)
_EXECUTION_REFERENCE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "end_event_cid",
        "event_cids",
        "exception_snapshot_cid",
        "handler_state_cid",
        "parent_trace_cid",
        "predecessor_event_cid",
        "raw_execution_state_cids",
        "segment_cids",
        "stack_frame_cids",
        "start_event_cid",
    }
)
_WORLD_REFERENCE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "analysis_limitation_index_cid",
        "canonical_program_graph_cid",
        "domain_state_cid",
        "environment_binding_set_cid",
        "execution_trace_cids",
        "observation_cids",
        "policy_cid",
        "prediction_cids",
        "previous_manifest_cid",
        "program_graph_snapshot_cid",
        "retained_subroot_cids",
        "semantic_object_index_cid",
        "semantic_world_root_cid",
        "subroot_cids",
        "transition_receipt_cids",
        "world_snapshot_cid",
    }
)
HISTORY_REFERENCE_FIELDS: Final[frozenset[str]] = (
    GRAPH_REFERENCE_FIELDS
    | _TRANSITION_REFERENCE_FIELDS
    | _EXECUTION_REFERENCE_FIELDS
    | _WORLD_REFERENCE_FIELDS
)


class GraphHistoryKind(str, Enum):
    """Closed taxonomy of graph-history storage admission kinds."""

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
    TRANSITION_MODEL_PROFILE = "transition_model_profile"
    TRANSITION_CALIBRATION = "transition_calibration"
    TRANSITION_QUERY = "program_transition_query"
    TRANSITION_CANDIDATE = "program_transition_candidate"
    TRANSITION_PREDICTION = "program_transition_prediction"
    TRANSITION_OBSERVATION = "program_transition_observation"
    TRANSITION_ADMISSION = "program_transition_admission"
    TRANSITION_RECEIPT = "program_transition_receipt"
    WORLD_SNAPSHOT = "semantic_world_snapshot"
    SEMANTIC_WORLD_ROOT_IDENTITY = "semantic_world_root_identity"
    WORLD_ROOT_MANIFEST = "semantic_world_root_manifest"


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
        GraphHistoryKind.PROGRAM_GRAPH_INDEX_MANIFEST: (
            "program_graph_index_manifest_cid"
        ),
        GraphHistoryKind.CANONICAL_PROGRAM_GRAPH: "canonical_program_graph_cid",
        GraphHistoryKind.PROGRAM_EVENT: "program_event_cid",
        GraphHistoryKind.EXECUTION_TRACE_SEGMENT: "execution_trace_segment_cid",
        GraphHistoryKind.EXECUTION_TRACE: "execution_trace_cid",
        GraphHistoryKind.TRANSITION_MODEL_PROFILE: "model_profile_cid",
        GraphHistoryKind.TRANSITION_CALIBRATION: "calibration_cid",
        GraphHistoryKind.TRANSITION_QUERY: "query_cid",
        GraphHistoryKind.TRANSITION_CANDIDATE: "candidate_cid",
        GraphHistoryKind.TRANSITION_PREDICTION: "prediction_cid",
        GraphHistoryKind.TRANSITION_OBSERVATION: "observation_cid",
        GraphHistoryKind.TRANSITION_ADMISSION: "admission_cid",
        GraphHistoryKind.TRANSITION_RECEIPT: "receipt_cid",
        GraphHistoryKind.WORLD_SNAPSHOT: "semantic_world_snapshot_cid",
        GraphHistoryKind.SEMANTIC_WORLD_ROOT_IDENTITY: "semantic_world_root_cid",
        GraphHistoryKind.WORLD_ROOT_MANIFEST: "world_root_manifest_cid",
    }
)

_CHILD_REFERENCE_FIELDS: Final[Mapping[GraphHistoryKind, tuple[str, ...]]] = (
    MappingProxyType(
        {
            GraphHistoryKind.PROGRAM_GRAPH_NODE: ("record_cid",),
            GraphHistoryKind.PROGRAM_GRAPH_EDGE: (
                "source_node_cid",
                "target_node_cid",
            ),
            GraphHistoryKind.PROGRAM_GRAPH_SNAPSHOT: (
                "canonical_program_graph_cid",
                "node_cids",
                "edge_cids",
                "callsite_cids",
                "function_symbol_cids",
                "contract_state_cids",
                "proof_obligation_graph_cids",
                "successor_set_cids",
                "frontier_cids",
                "retained_subroot_cids",
            ),
            GraphHistoryKind.PROGRAM_GRAPH_DELTA: (
                "previous_snapshot_cid",
                "added_node_cids",
                "added_edge_cids",
                "retained_subroot_cids",
            ),
            GraphHistoryKind.PROOF_OBLIGATION_GRAPH: (
                "root_obligation_cid",
                "obligation_node_cids",
                "obligation_edge_cids",
            ),
            GraphHistoryKind.STATIC_SUCCESSOR_SET: (
                "subject_node_cid",
                "successor_node_cids",
                "successor_edge_cids",
            ),
            GraphHistoryKind.DYNAMIC_FRONTIER_RECORD: (
                "unresolved_node_cids",
                "unresolved_edge_cids",
            ),
            GraphHistoryKind.PROGRAM_GRAPH_INDEX_MANIFEST: ("snapshot_cid",),
            GraphHistoryKind.PROGRAM_EVENT: (
                "predecessor_event_cid",
                "stack_frame_cids",
            ),
            GraphHistoryKind.EXECUTION_TRACE_SEGMENT: (
                "parent_trace_cid",
                "start_event_cid",
                "end_event_cid",
                "event_cids",
            ),
            GraphHistoryKind.EXECUTION_TRACE: (
                "event_cids",
                "segment_cids",
                "parent_trace_cid",
                "raw_execution_state_cids",
            ),
            GraphHistoryKind.TRANSITION_CALIBRATION: ("model_profile_cid",),
            GraphHistoryKind.TRANSITION_CANDIDATE: ("query_cid",),
            GraphHistoryKind.TRANSITION_PREDICTION: (
                "query_cid",
                "model_profile_cid",
                "candidate_cids",
                "calibration_cid",
            ),
            GraphHistoryKind.TRANSITION_OBSERVATION: ("query_cid",),
            GraphHistoryKind.TRANSITION_ADMISSION: (
                "query_cid",
                "prediction_cid",
                "observation_cid",
            ),
            GraphHistoryKind.TRANSITION_RECEIPT: (
                "query_cid",
                "admission_cid",
                "prediction_cid",
                "observation_cid",
            ),
            GraphHistoryKind.WORLD_SNAPSHOT: (
                "program_graph_snapshot_cid",
                "canonical_program_graph_cid",
                "execution_trace_cids",
                "transition_receipt_cids",
                "prediction_cids",
                "observation_cids",
                "retained_subroot_cids",
                "domain_state_cid",
                "semantic_object_index_cid",
                "environment_binding_set_cid",
                "policy_cid",
                "analysis_limitation_index_cid",
            ),
            GraphHistoryKind.SEMANTIC_WORLD_ROOT_IDENTITY: (
                "domain_state_cid",
                "canonical_program_graph_cid",
                "program_graph_snapshot_cid",
                "semantic_object_index_cid",
                "environment_binding_set_cid",
                "policy_cid",
                "analysis_limitation_index_cid",
            ),
            GraphHistoryKind.WORLD_ROOT_MANIFEST: (
                "semantic_world_root_cid",
                "world_snapshot_cid",
                "program_graph_snapshot_cid",
                "canonical_program_graph_cid",
                "previous_manifest_cid",
                "subroot_cids",
                "transition_receipt_cids",
                "execution_trace_cids",
                "domain_state_cid",
                "semantic_object_index_cid",
                "environment_binding_set_cid",
                "policy_cid",
                "analysis_limitation_index_cid",
            ),
        }
    )
)

_PREDICTION_KINDS: Final[frozenset[GraphHistoryKind]] = frozenset(
    {GraphHistoryKind.TRANSITION_PREDICTION}
)
_OBSERVATION_KINDS: Final[frozenset[GraphHistoryKind]] = frozenset(
    {GraphHistoryKind.TRANSITION_OBSERVATION}
)


class GraphHistoryError(ValueError):
    """Base error for graph-history admission or retrieval."""


class GraphHistoryAdmissionError(GraphHistoryError):
    """Raised when a write is rejected by closed admission policy."""


class GraphHistoryIntegrityError(GraphHistoryError):
    """Raised when bytes, CID, kind, or sealed shape do not verify."""


class GraphHistoryNotFound(GraphHistoryError, KeyError):
    """Raised when a required history block is absent."""


class GraphHistoryConflictError(GraphHistoryError):
    """Raised when an identity or operation_id is rebound to different bytes."""


class GraphHistoryMissingReference(GraphHistoryAdmissionError, GraphHistoryNotFound):
    """Raised when a parent record cites bytes that are not yet stored."""


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
            f"history record is not canonical JSON: {exc}"
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


def _reject_private(value: Any, *, path: str = "$") -> None:
    try:
        reject_private_raw_source(value, path=path)
    except Exception as exc:
        raise GraphHistoryAdmissionError(str(exc)) from exc


def _unique_sorted_cids(values: Sequence[str] | None, name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes, bytearray, memoryview)):
        raise GraphHistoryAdmissionError(f"{name} must be a sequence of CIDs")
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        if type(item) is not str or not item:
            raise GraphHistoryAdmissionError(f"{name} entries must be CIDs")
        try:
            validate_verified_cid(item, name)
        except SemanticGovernorStoreContractError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return tuple(sorted(ordered))


def _ordered_unique_cids(values: Sequence[str] | None, name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes, bytearray, memoryview)):
        raise GraphHistoryAdmissionError(f"{name} must be a sequence of CIDs")
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        if type(item) is not str or not item:
            raise GraphHistoryAdmissionError(f"{name} entries must be CIDs")
        try:
            validate_verified_cid(item, name)
        except SemanticGovernorStoreContractError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        if item in seen:
            raise GraphHistoryAdmissionError(f"{name} identities must be unique")
        seen.add(item)
        ordered.append(item)
    return tuple(ordered)


def _optional_cid(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    try:
        return validate_verified_cid(value, name)
    except SemanticGovernorStoreContractError as exc:
        raise GraphHistoryAdmissionError(str(exc)) from exc


def _cid(value: str, name: str) -> str:
    try:
        return validate_verified_cid(value, name)
    except SemanticGovernorStoreContractError as exc:
        raise GraphHistoryAdmissionError(str(exc)) from exc


def _record_cid(record: Any) -> str:
    field = getattr(record, "CID_FIELD", None)
    if type(field) is not str:
        raise GraphHistoryAdmissionError("record is missing CID_FIELD")
    return str(getattr(record, field))


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
    _reject_private(body, path="payload")
    sealed = {
        "schema": GRAPH_HISTORY_STORED_SCHEMA,
        "interface_id": GRAPH_HISTORY_STORED_INTERFACE,
        "kind": artifact_kind.value,
        "payload": body,
    }
    _reject_private(sealed, path="$")
    data = _canonical_bytes(sealed)
    if len(data) > MAX_HISTORY_BYTES:
        raise GraphHistoryAdmissionError(
            f"history record exceeds MAX_HISTORY_BYTES "
            f"({len(data)} > {MAX_HISTORY_BYTES})"
        )
    return sealed


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
    if record.get("schema") != GRAPH_HISTORY_STORED_SCHEMA:
        raise GraphHistoryIntegrityError("unknown sealed history schema")
    if record.get("interface_id") != GRAPH_HISTORY_STORED_INTERFACE:
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
        _reject_private(body, path="payload")
    except GraphHistoryAdmissionError as exc:
        raise GraphHistoryIntegrityError(str(exc)) from exc
    sealed = {
        "schema": GRAPH_HISTORY_STORED_SCHEMA,
        "interface_id": GRAPH_HISTORY_STORED_INTERFACE,
        "kind": kind.value,
        "payload": body,
    }
    data = _canonical_bytes(sealed)
    if len(data) > MAX_HISTORY_BYTES:
        raise GraphHistoryIntegrityError(
            f"history record exceeds MAX_HISTORY_BYTES "
            f"({len(data)} > {MAX_HISTORY_BYTES})"
        )
    if cid_for_artifact(dict(record)) != cid_for_artifact(sealed):
        raise GraphHistoryIntegrityError(
            "sealed history record is not in canonical form"
        )
    return sealed


def _identity_cid_from_payload(
    kind: GraphHistoryKind,
    payload: Mapping[str, Any],
) -> str:
    field = _KIND_CID_FIELD[kind]
    value = payload.get(field)
    try:
        return validate_verified_cid(value, field)
    except SemanticGovernorStoreContractError as exc:
        raise GraphHistoryIntegrityError(
            f"payload.{field} must be a canonical transport CID"
        ) from exc


def _child_cids(kind: GraphHistoryKind, payload: Mapping[str, Any]) -> tuple[str, ...]:
    fields = _CHILD_REFERENCE_FIELDS.get(kind, ())
    refs: list[str] = []
    for field in fields:
        value = payload.get(field)
        if value is None:
            continue
        if type(value) is str:
            refs.append(value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                if type(item) is str and item:
                    refs.append(item)
    return tuple(dict.fromkeys(refs))


def _wrap_domain_error(exc: Exception) -> GraphHistoryAdmissionError:
    return GraphHistoryAdmissionError(str(exc))


def _decode_payload(kind: GraphHistoryKind, payload: Mapping[str, Any]) -> Any:
    if kind is GraphHistoryKind.WORLD_SNAPSHOT:
        return SemanticWorldSnapshot.from_dict(payload)
    if kind is GraphHistoryKind.WORLD_ROOT_MANIFEST:
        from ipfs_kit_py.semantic_world_store.world_roots import (
            SemanticWorldRootManifest,
        )

        return SemanticWorldRootManifest.from_dict(payload)
    if kind is GraphHistoryKind.CANONICAL_PROGRAM_GRAPH:
        try:
            return CanonicalProgramGraphIdentity.from_dict(payload)
        except ProgramIdentityError as exc:
            raise _wrap_domain_error(exc) from exc
    if kind is GraphHistoryKind.SEMANTIC_WORLD_ROOT_IDENTITY:
        try:
            return SemanticWorldRootIdentity.from_dict(payload)
        except ProgramIdentityError as exc:
            raise _wrap_domain_error(exc) from exc
    if kind in _PREDICTION_KINDS:
        if payload.get("schema") == PROGRAM_TRANSITION_OBSERVATION_SCHEMA:
            raise GraphHistoryAdmissionError(
                "admitted observations cannot be stored as predictions"
            )
        try:
            return ProgramTransitionPrediction.from_dict(payload)
        except ProgramTransitionError as exc:
            raise _wrap_domain_error(exc) from exc
    if kind in _OBSERVATION_KINDS:
        try:
            return decode_transition_observation(payload)
        except ProgramTransitionError as exc:
            raise GraphHistoryAdmissionError(
                "predictions cannot decode as admitted observations"
            ) from exc
    try:
        if kind.value.startswith("program_graph") or kind.value in {
            "callsite_record",
            "function_symbol_record",
            "contract_state_record",
            "proof_obligation_graph",
            "static_successor_set",
            "dynamic_frontier_record",
        }:
            record = decode_program_graph_record(payload)
        elif kind.value.startswith("transition") or kind.value.startswith(
            "program_transition"
        ):
            record = decode_transition_record(payload)
        elif kind in {
            GraphHistoryKind.PROGRAM_EVENT,
            GraphHistoryKind.EXECUTION_TRACE,
            GraphHistoryKind.EXECUTION_TRACE_SEGMENT,
        }:
            record = decode_program_execution_record(payload)
        else:
            raise GraphHistoryAdmissionError(
                f"no decoder for graph-history kind {kind.value}"
            )
    except (
        ProgramGraphError,
        ProgramTransitionError,
        ProgramExecutionError,
        ProgramIdentityError,
    ) as exc:
        raise _wrap_domain_error(exc) from exc
    expected_field = _KIND_CID_FIELD[kind]
    if getattr(record, "CID_FIELD", None) != expected_field:
        raise GraphHistoryIntegrityError(
            f"decoded {type(record).__name__} CID field "
            f"{getattr(record, 'CID_FIELD', None)!r} does not match {expected_field}"
        )
    return record


def _payload_for_record(kind: GraphHistoryKind, record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        payload = dict(record)
    elif hasattr(record, "to_dict"):
        payload = dict(record.to_dict())
    else:
        raise GraphHistoryAdmissionError(
            f"{kind.value} must be a mapping or closed record"
        )
    decoded = _decode_payload(kind, payload)
    return dict(decoded.to_dict())


@dataclass(frozen=True, slots=True)
class SemanticWorldSnapshot:
    """Immutable world snapshot binding graph, traces, and transition history."""

    program_graph_snapshot_cid: str
    canonical_program_graph_cid: str
    domain_state_cid: str
    semantic_object_index_cid: str
    environment_binding_set_cid: str
    policy_cid: str
    analysis_limitation_index_cid: str
    execution_trace_cids: Sequence[str] = ()
    transition_receipt_cids: Sequence[str] = ()
    prediction_cids: Sequence[str] = ()
    observation_cids: Sequence[str] = ()
    retained_subroot_cids: Sequence[str] = ()

    SCHEMA: ClassVar[str] = SEMANTIC_WORLD_SNAPSHOT_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_SNAPSHOT_INTERFACE
    CID_FIELD: ClassVar[str] = "semantic_world_snapshot_cid"

    def __post_init__(self) -> None:
        for name in (
            "program_graph_snapshot_cid",
            "canonical_program_graph_cid",
            "domain_state_cid",
            "semantic_object_index_cid",
            "environment_binding_set_cid",
            "policy_cid",
            "analysis_limitation_index_cid",
        ):
            object.__setattr__(self, name, _cid(getattr(self, name), name))
        object.__setattr__(
            self,
            "execution_trace_cids",
            _ordered_unique_cids(self.execution_trace_cids, "execution_trace_cid"),
        )
        object.__setattr__(
            self,
            "transition_receipt_cids",
            _ordered_unique_cids(
                self.transition_receipt_cids, "transition_receipt_cid"
            ),
        )
        object.__setattr__(
            self,
            "prediction_cids",
            _unique_sorted_cids(self.prediction_cids, "prediction_cid"),
        )
        object.__setattr__(
            self,
            "observation_cids",
            _unique_sorted_cids(self.observation_cids, "observation_cid"),
        )
        object.__setattr__(
            self,
            "retained_subroot_cids",
            _unique_sorted_cids(self.retained_subroot_cids, "retained_subroot_cid"),
        )
        overlap = set(self.prediction_cids) & set(self.observation_cids)
        if overlap:
            raise GraphHistoryAdmissionError(
                "predictions and admitted observations must remain distinguishable"
            )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "program_graph_snapshot_cid": self.program_graph_snapshot_cid,
            "canonical_program_graph_cid": self.canonical_program_graph_cid,
            "domain_state_cid": self.domain_state_cid,
            "semantic_object_index_cid": self.semantic_object_index_cid,
            "environment_binding_set_cid": self.environment_binding_set_cid,
            "policy_cid": self.policy_cid,
            "analysis_limitation_index_cid": self.analysis_limitation_index_cid,
            "execution_trace_cids": list(self.execution_trace_cids),
            "transition_receipt_cids": list(self.transition_receipt_cids),
            "prediction_cids": list(self.prediction_cids),
            "observation_cids": list(self.observation_cids),
            "retained_subroot_cids": list(self.retained_subroot_cids),
        }

    @property
    def semantic_world_snapshot_cid(self) -> str:
        return cid_for_artifact(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        value = self.identity_payload()
        value["semantic_world_snapshot_cid"] = self.semantic_world_snapshot_cid
        return value

    def bound_subroot_cids(self) -> tuple[str, ...]:
        refs = [
            self.program_graph_snapshot_cid,
            self.canonical_program_graph_cid,
            self.domain_state_cid,
            self.semantic_object_index_cid,
            self.environment_binding_set_cid,
            self.policy_cid,
            self.analysis_limitation_index_cid,
            *self.execution_trace_cids,
            *self.transition_receipt_cids,
            *self.prediction_cids,
            *self.observation_cids,
            *self.retained_subroot_cids,
        ]
        return tuple(sorted(set(refs)))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SemanticWorldSnapshot":
        if not isinstance(data, Mapping):
            raise GraphHistoryAdmissionError("world snapshot must be a mapping")
        allowed = {
            "schema",
            "program_graph_snapshot_cid",
            "canonical_program_graph_cid",
            "domain_state_cid",
            "semantic_object_index_cid",
            "environment_binding_set_cid",
            "policy_cid",
            "analysis_limitation_index_cid",
            "execution_trace_cids",
            "transition_receipt_cids",
            "prediction_cids",
            "observation_cids",
            "retained_subroot_cids",
            "semantic_world_snapshot_cid",
        }
        actual = set(data)
        unknown = actual - allowed
        if unknown:
            raise GraphHistoryAdmissionError(
                f"world snapshot has unknown fields {sorted(unknown)}"
            )
        if data.get("schema") != cls.SCHEMA:
            raise GraphHistoryAdmissionError("unsupported SemanticWorldSnapshot schema")
        claimed = data.get("semantic_world_snapshot_cid")
        snapshot = cls(
            program_graph_snapshot_cid=data["program_graph_snapshot_cid"],
            canonical_program_graph_cid=data["canonical_program_graph_cid"],
            domain_state_cid=data["domain_state_cid"],
            semantic_object_index_cid=data["semantic_object_index_cid"],
            environment_binding_set_cid=data["environment_binding_set_cid"],
            policy_cid=data["policy_cid"],
            analysis_limitation_index_cid=data["analysis_limitation_index_cid"],
            execution_trace_cids=data.get("execution_trace_cids") or (),
            transition_receipt_cids=data.get("transition_receipt_cids") or (),
            prediction_cids=data.get("prediction_cids") or (),
            observation_cids=data.get("observation_cids") or (),
            retained_subroot_cids=data.get("retained_subroot_cids") or (),
        )
        if claimed is not None and claimed != snapshot.semantic_world_snapshot_cid:
            raise GraphHistoryIntegrityError(
                f"claimed world snapshot CID does not rehash: "
                f"computed {snapshot.semantic_world_snapshot_cid}, claimed {claimed}"
            )
        return snapshot


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
                        f"operation_id {operation_id!r} already bound to a different artifact"
                    )
                return
            with self._connection:
                self._connection.execute(
                    "INSERT INTO artifact_operations"
                    "(operation_id, identity_cid, storage_cid, kind) VALUES(?,?,?,?)",
                    (operation_id, identity_cid, storage_cid, kind),
                )


class WorldHistoryBlockStore:
    """Sealed graph/transition/snapshot/root persistence over coordination CAS."""

    INTERFACE: Final[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(self, store: DurableCoordinationStore) -> None:
        if not isinstance(store, DurableCoordinationStore):
            raise TypeError("store must be a DurableCoordinationStore")
        self._store = store
        self._index = _IdentityIndex(store)
        self._rebuild_identity_index()

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    def close(self) -> None:
        self._index.close()

    def __enter__(self) -> "WorldHistoryBlockStore":
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
            if not isinstance(raw, Mapping) or raw.get("schema") != GRAPH_HISTORY_STORED_SCHEMA:
                continue
            try:
                sealed = admit_sealed_history_record(raw)
                kind = _coerce_kind(sealed["kind"])
                identity_cid = _identity_cid_from_payload(kind, sealed["payload"])
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
        return bool(self._store.has(cid))

    def require_stored(self, cid: str, *, path: str = "reference") -> str:
        try:
            cid = validate_verified_cid(cid, path)
        except SemanticGovernorStoreContractError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        if self.has_identity(cid):
            if self._index.lookup_identity(cid) is not None:
                storage_cid, _kind = self._index.lookup_identity(cid)  # type: ignore[misc]
                self._rehash_storage_bytes(storage_cid)
                return cid
            if self._index.lookup_storage(cid) is not None:
                self._rehash_storage_bytes(cid)
                return cid
            try:
                self._rehash_storage_bytes(cid)
            except GraphHistoryNotFound as exc:
                raise GraphHistoryMissingReference(
                    f"{path} {cid} is not stored before parent reference"
                ) from exc
            return cid
        raise GraphHistoryMissingReference(
            f"{path} {cid} is not stored before parent reference"
        )

    def _require_children(self, kind: GraphHistoryKind, payload: Mapping[str, Any]) -> None:
        for cid in _child_cids(kind, payload):
            self.require_stored(cid, path=f"{kind.value} child")

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
        record: Any,
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
        require_children: bool = True,
    ) -> GraphHistoryWriteResult:
        artifact_kind = _coerce_kind(kind)
        try:
            payload = _payload_for_record(artifact_kind, record)
        except GraphHistoryIntegrityError:
            raise
        sealed = seal_graph_history_record(artifact_kind, payload)
        identity_cid = _identity_cid_from_payload(artifact_kind, sealed["payload"])
        decoded = _decode_payload(artifact_kind, sealed["payload"])
        decoded_cid = _record_cid(decoded)
        if decoded_cid != identity_cid:
            raise GraphHistoryIntegrityError(
                f"payload identity CID {decoded_cid} does not match {identity_cid}"
            )
        if require_children:
            self._require_children(artifact_kind, sealed["payload"])
        return self._put_sealed(
            kind=artifact_kind,
            payload=sealed["payload"],
            identity_cid=identity_cid,
            expected_cid=expected_cid or identity_cid,
            operation_id=operation_id,
            replicate=replicate,
        )

    def _put_sealed(
        self,
        *,
        kind: GraphHistoryKind,
        payload: Mapping[str, Any],
        identity_cid: str,
        expected_cid: str | None,
        operation_id: str | None,
        replicate: bool,
    ) -> GraphHistoryWriteResult:
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

        sealed = seal_graph_history_record(kind, payload)
        storage_cid = cid_for_artifact(sealed)
        payload_identity = _identity_cid_from_payload(kind, sealed["payload"])
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
                    or prior_kind != kind.value
                ):
                    raise GraphHistoryConflictError(
                        f"operation_id {operation_id!r} already bound to a different artifact"
                    )

        prior = self._index.lookup_identity(identity_cid)
        if prior is not None:
            prior_storage, prior_kind = prior
            if prior_storage != storage_cid or prior_kind != kind.value:
                raise GraphHistoryConflictError(
                    f"identity {identity_cid!r} already bound to a different artifact"
                )
            self.get_verified_record(identity_cid, expected_kind=kind)
            if operation_id is not None:
                self._index.bind_operation(
                    operation_id, identity_cid, storage_cid, kind.value
                )
            return GraphHistoryWriteResult(
                identity_cid,
                storage_cid,
                kind,
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
        self._index.bind_identity(identity_cid, storage_cid, kind.value)
        if operation_id is not None:
            self._index.bind_operation(
                operation_id, identity_cid, storage_cid, kind.value
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
                    kind,
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
            kind,
            created,
            True,
            reason,
        )

    def get_verified_record(
        self,
        cid: str,
        *,
        expected_kind: Optional[GraphHistoryKind | str] = None,
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
        if raw.get("schema") != GRAPH_HISTORY_STORED_SCHEMA:
            raise GraphHistoryIntegrityError(
                f"{storage_cid} is not a graph-history record"
            )
        sealed = admit_sealed_history_record(raw)
        recomputed = cid_for_artifact(sealed)
        if recomputed != storage_cid:
            raise GraphHistoryIntegrityError(
                f"forged sealed history record: recomputed {recomputed}, "
                f"expected {storage_cid}"
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
                    f"wrong history kind: stored {kind.value}, expected {wanted.value}"
                )
        identity_cid = _identity_cid_from_payload(kind, sealed["payload"])
        decoded = _decode_payload(kind, sealed["payload"])
        if _record_cid(decoded) != identity_cid:
            raise GraphHistoryIntegrityError(
                "decoded record CID does not rehash claimed identity"
            )
        self._index.bind_identity(identity_cid, storage_cid, kind.value)
        return MappingProxyType(
            {
                "schema": sealed["schema"],
                "interface_id": sealed["interface_id"],
                "kind": kind.value,
                "payload": dict(sealed["payload"]),
                "cid": identity_cid,
                "storage_cid": storage_cid,
            }
        )

    def get_decoded(
        self,
        cid: str,
        *,
        expected_kind: GraphHistoryKind | str,
    ) -> Any:
        artifact = self.get_verified_record(cid, expected_kind=expected_kind)
        return _decode_payload(_coerce_kind(expected_kind), artifact["payload"])


def _as_coordination(
    store: DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | WorldHistoryBlockStore
    | "LogicalProgramGraphStore"
    | "ProgramTransitionLog"
    | "SemanticWorldSnapshotStore",
) -> DurableCoordinationStore:
    if isinstance(store, WorldHistoryBlockStore):
        return store.store
    if isinstance(store, (LogicalProgramGraphStore, ProgramTransitionLog, SemanticWorldSnapshotStore)):
        return store.blocks.store
    if isinstance(store, VerifiedSemanticBlockStore):
        return store.store
    if isinstance(store, SemanticWorldArtifactStore):
        return store.store
    if isinstance(store, DurableCoordinationStore):
        return store
    raise TypeError(
        "store must be a DurableCoordinationStore, SemanticWorldArtifactStore, "
        "VerifiedSemanticBlockStore, or graph-history facade"
    )


_BLOCK_STORES: dict[str, WorldHistoryBlockStore] = {}
_BLOCK_STORE_LOCK = threading.RLock()


def world_history_blocks(
    store: DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | WorldHistoryBlockStore
    | "LogicalProgramGraphStore"
    | "ProgramTransitionLog"
    | "SemanticWorldSnapshotStore",
) -> WorldHistoryBlockStore:
    """Return the shared history block store for a coordination root."""

    if isinstance(store, WorldHistoryBlockStore):
        return store
    if isinstance(store, (LogicalProgramGraphStore, ProgramTransitionLog, SemanticWorldSnapshotStore)):
        return store.blocks
    coordination = _as_coordination(store)
    key = str(coordination.root.resolve())
    with _BLOCK_STORE_LOCK:
        existing = _BLOCK_STORES.get(key)
        if existing is None or existing.store is not coordination:
            existing = WorldHistoryBlockStore(coordination)
            _BLOCK_STORES[key] = existing
        return existing


def _put_canonical_graph(
    blocks: WorldHistoryBlockStore,
    snapshot: ProgramGraphSnapshot,
    *,
    operation_id: str | None,
) -> GraphHistoryWriteResult:
    identity = CanonicalProgramGraphIdentity(
        language=snapshot.language,
        graph_kind=snapshot.graph_kind,
        node_cids=snapshot.node_cids,
        edge_cids=snapshot.edge_cids,
        environment_binding_set_cid=snapshot.environment_binding_set_cid,
        unavailable_dimensions=snapshot.unavailable_dimensions,
    )
    if identity.canonical_program_graph_cid != snapshot.canonical_program_graph_cid:
        raise GraphHistoryAdmissionError(
            "canonical_program_graph_cid does not rehash snapshot node/edge sets"
        )
    return blocks.put_record(
        GraphHistoryKind.CANONICAL_PROGRAM_GRAPH,
        identity,
        operation_id=None if operation_id is None else f"{operation_id}:canonical",
        require_children=False,
    )


class LogicalProgramGraphStore:
    """Persist immutable program-graph nodes, edges, snapshots, and deltas."""

    INTERFACE: Final[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | WorldHistoryBlockStore,
    ) -> None:
        self._blocks = world_history_blocks(store)

    @property
    def blocks(self) -> WorldHistoryBlockStore:
        return self._blocks

    @property
    def store(self) -> DurableCoordinationStore:
        return self._blocks.store

    def close(self) -> None:
        """Shared history blocks outlive a single facade."""

        return None

    def __enter__(self) -> "LogicalProgramGraphStore":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def put_node(
        self,
        node: ProgramGraphNode | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._blocks.put_record(
            GraphHistoryKind.PROGRAM_GRAPH_NODE, node, operation_id=operation_id
        )

    def put_edge(
        self,
        edge: ProgramGraphEdge | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._blocks.put_record(
            GraphHistoryKind.PROGRAM_GRAPH_EDGE, edge, operation_id=operation_id
        )

    def put_snapshot(
        self,
        snapshot: ProgramGraphSnapshot | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._blocks.put_record(
            GraphHistoryKind.PROGRAM_GRAPH_SNAPSHOT,
            snapshot,
            operation_id=operation_id,
        )

    def put_delta(
        self,
        delta: ProgramGraphDelta | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._blocks.put_record(
            GraphHistoryKind.PROGRAM_GRAPH_DELTA, delta, operation_id=operation_id
        )

    def get_verified_node(self, cid: str) -> ProgramGraphNode:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.PROGRAM_GRAPH_NODE
        )

    def get_verified_edge(self, cid: str) -> ProgramGraphEdge:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.PROGRAM_GRAPH_EDGE
        )

    def get_verified_snapshot(self, cid: str) -> ProgramGraphSnapshot:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.PROGRAM_GRAPH_SNAPSHOT
        )

    def get_verified_delta(self, cid: str) -> ProgramGraphDelta:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.PROGRAM_GRAPH_DELTA
        )

    def query_logical_cycles(self, snapshot_cid: str) -> tuple[tuple[str, ...], ...]:
        snapshot = self.get_verified_snapshot(snapshot_cid)
        edges = [self.get_verified_edge(cid) for cid in snapshot.edge_cids]
        return directed_logical_cycles(edges)

    def physical_ipld_catalog(self, snapshot_cid: str) -> dict[str, dict[str, Any]]:
        snapshot = self.get_verified_snapshot(snapshot_cid)
        catalog: dict[str, dict[str, Any]] = {
            snapshot.program_graph_snapshot_cid: dict(snapshot.identity_payload())
        }

        def _add(kind: GraphHistoryKind, cid: str) -> Any:
            record = self._blocks.get_decoded(cid, expected_kind=kind)
            catalog[_record_cid(record)] = dict(record.identity_payload())
            return record

        for cid in snapshot.node_cids:
            _add(GraphHistoryKind.PROGRAM_GRAPH_NODE, cid)
        for cid in snapshot.edge_cids:
            _add(GraphHistoryKind.PROGRAM_GRAPH_EDGE, cid)
        for cid in snapshot.callsite_cids:
            _add(GraphHistoryKind.CALLSITE_RECORD, cid)
        for cid in snapshot.function_symbol_cids:
            _add(GraphHistoryKind.FUNCTION_SYMBOL_RECORD, cid)
        for cid in snapshot.contract_state_cids:
            _add(GraphHistoryKind.CONTRACT_STATE_RECORD, cid)
        for cid in snapshot.proof_obligation_graph_cids:
            _add(GraphHistoryKind.PROOF_OBLIGATION_GRAPH, cid)
        for cid in snapshot.successor_set_cids:
            _add(GraphHistoryKind.STATIC_SUCCESSOR_SET, cid)
        for cid in snapshot.frontier_cids:
            _add(GraphHistoryKind.DYNAMIC_FRONTIER_RECORD, cid)
        if self._blocks.has_identity(snapshot.canonical_program_graph_cid):
            _add(
                GraphHistoryKind.CANONICAL_PROGRAM_GRAPH,
                snapshot.canonical_program_graph_cid,
            )
        assert_physical_dag_acyclic(catalog)
        return catalog

    def append_program_graph_snapshot(
        self,
        snapshot: ProgramGraphSnapshot | None = None,
        *,
        nodes: Sequence[ProgramGraphNode] = (),
        edges: Sequence[ProgramGraphEdge] = (),
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
        previous_snapshot: ProgramGraphSnapshot | None = None,
        index_manifest: ProgramGraphIndexManifest | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        """Persist child records then the snapshot; optional delta retains subroots."""

        if snapshot is None:
            if environment_binding_set_cid is None or sealed_binding_cid is None:
                raise GraphHistoryAdmissionError(
                    "append_program_graph_snapshot requires bindings or a snapshot"
                )
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
        elif not isinstance(snapshot, ProgramGraphSnapshot):
            snapshot = ProgramGraphSnapshot.from_dict(snapshot)

        if nodes or edges or callsites or function_symbols or contract_states:
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

        prefix = None if operation_id is None else operation_id
        for index, record in enumerate(function_symbols):
            self._blocks.put_record(
                GraphHistoryKind.FUNCTION_SYMBOL_RECORD,
                record,
                operation_id=None if prefix is None else f"{prefix}:fn:{index}",
            )
        for index, record in enumerate(callsites):
            self._blocks.put_record(
                GraphHistoryKind.CALLSITE_RECORD,
                record,
                operation_id=None if prefix is None else f"{prefix}:call:{index}",
            )
        for index, record in enumerate(contract_states):
            self._blocks.put_record(
                GraphHistoryKind.CONTRACT_STATE_RECORD,
                record,
                operation_id=None if prefix is None else f"{prefix}:contract:{index}",
            )
        for index, record in enumerate(nodes):
            self._blocks.put_record(
                GraphHistoryKind.PROGRAM_GRAPH_NODE,
                record,
                operation_id=None if prefix is None else f"{prefix}:node:{index}",
            )
        for index, record in enumerate(edges):
            self._blocks.put_record(
                GraphHistoryKind.PROGRAM_GRAPH_EDGE,
                record,
                operation_id=None if prefix is None else f"{prefix}:edge:{index}",
            )
        for index, record in enumerate(proof_obligation_graphs):
            self._blocks.put_record(
                GraphHistoryKind.PROOF_OBLIGATION_GRAPH,
                record,
                operation_id=None if prefix is None else f"{prefix}:pog:{index}",
            )
        for index, record in enumerate(successor_sets):
            self._blocks.put_record(
                GraphHistoryKind.STATIC_SUCCESSOR_SET,
                record,
                operation_id=None if prefix is None else f"{prefix}:succ:{index}",
            )
        for index, record in enumerate(frontiers):
            self._blocks.put_record(
                GraphHistoryKind.DYNAMIC_FRONTIER_RECORD,
                record,
                operation_id=None if prefix is None else f"{prefix}:front:{index}",
            )
        _put_canonical_graph(self._blocks, snapshot, operation_id=prefix)
        if previous_snapshot is not None:
            if not isinstance(previous_snapshot, ProgramGraphSnapshot):
                previous_snapshot = ProgramGraphSnapshot.from_dict(previous_snapshot)
            self._blocks.require_stored(
                previous_snapshot.program_graph_snapshot_cid,
                path="previous_snapshot_cid",
            )
            delta = delta_between_snapshots(previous_snapshot, snapshot)
            self._blocks.put_record(
                GraphHistoryKind.PROGRAM_GRAPH_DELTA,
                delta,
                operation_id=None if prefix is None else f"{prefix}:delta",
            )
        result = self._blocks.put_record(
            GraphHistoryKind.PROGRAM_GRAPH_SNAPSHOT,
            snapshot,
            operation_id=prefix,
        )
        if index_manifest is not None:
            self._blocks.put_record(
                GraphHistoryKind.PROGRAM_GRAPH_INDEX_MANIFEST,
                index_manifest,
                operation_id=None if prefix is None else f"{prefix}:index",
            )
        self.physical_ipld_catalog(snapshot.program_graph_snapshot_cid)
        return result


class ProgramTransitionLog:
    """Append-only transition query/prediction/observation/admission/receipt log."""

    INTERFACE: Final[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | WorldHistoryBlockStore,
    ) -> None:
        self._blocks = world_history_blocks(store)

    @property
    def blocks(self) -> WorldHistoryBlockStore:
        return self._blocks

    @property
    def store(self) -> DurableCoordinationStore:
        return self._blocks.store

    def close(self) -> None:
        """Shared history blocks outlive a single facade."""

        return None

    def __enter__(self) -> "ProgramTransitionLog":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def put_prediction(
        self,
        prediction: ProgramTransitionPrediction | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._blocks.put_record(
            GraphHistoryKind.TRANSITION_PREDICTION,
            prediction,
            operation_id=operation_id,
        )

    def put_observation(
        self,
        observation: ProgramTransitionObservation | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if isinstance(observation, ProgramTransitionPrediction):
            raise GraphHistoryAdmissionError(
                "predictions cannot be stored as admitted observations"
            )
        if isinstance(observation, Mapping):
            if observation.get("schema") == PROGRAM_TRANSITION_PREDICTION_SCHEMA:
                raise GraphHistoryAdmissionError(
                    "predictions cannot be stored as admitted observations"
                )
        return self._blocks.put_record(
            GraphHistoryKind.TRANSITION_OBSERVATION,
            observation,
            operation_id=operation_id,
        )

    def get_verified_prediction(self, cid: str) -> ProgramTransitionPrediction:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.TRANSITION_PREDICTION
        )

    def get_verified_observation(self, cid: str) -> ProgramTransitionObservation:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.TRANSITION_OBSERVATION
        )

    def get_verified_receipt(self, cid: str) -> ProgramTransitionReceipt:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.TRANSITION_RECEIPT
        )

    def kind_of(self, cid: str) -> GraphHistoryKind:
        artifact = self._blocks.get_verified_record(cid)
        return GraphHistoryKind(artifact["kind"])

    def append_transition_receipt(
        self,
        receipt: ProgramTransitionReceipt | None = None,
        *,
        query: ProgramTransitionQuery | None = None,
        admission: ProgramTransitionAdmission | None = None,
        prediction: ProgramTransitionPrediction | None = None,
        observation: ProgramTransitionObservation | None = None,
        candidates: Sequence[ProgramTransitionCandidate] = (),
        model_profile: TransitionModelProfile | None = None,
        calibration: TransitionCalibration | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        """Persist referenced transition records, then the receipt."""

        if receipt is None:
            if query is None or admission is None:
                raise GraphHistoryAdmissionError(
                    "append_transition_receipt requires a receipt or query+admission"
                )
            receipt = issue_transition_receipt(
                query,
                admission,
                prediction=prediction,
                observation=observation,
            )
        elif not isinstance(receipt, ProgramTransitionReceipt):
            receipt = ProgramTransitionReceipt.from_dict(receipt)

        if prediction is not None and observation is not None:
            if prediction.prediction_cid == observation.observation_cid:
                raise GraphHistoryAdmissionError(
                    "predictions and admitted observations must remain distinguishable"
                )
        if receipt.prediction_cid is not None and receipt.observation_cid is not None:
            if receipt.prediction_cid == receipt.observation_cid:
                raise GraphHistoryAdmissionError(
                    "receipt cannot bind the same CID as prediction and observation"
                )

        prefix = operation_id
        if model_profile is not None:
            self._blocks.put_record(
                GraphHistoryKind.TRANSITION_MODEL_PROFILE,
                model_profile,
                operation_id=None if prefix is None else f"{prefix}:profile",
                require_children=False,
            )
        if calibration is not None:
            self._blocks.put_record(
                GraphHistoryKind.TRANSITION_CALIBRATION,
                calibration,
                operation_id=None if prefix is None else f"{prefix}:calibration",
            )
        if query is not None:
            self._blocks.put_record(
                GraphHistoryKind.TRANSITION_QUERY,
                query,
                operation_id=None if prefix is None else f"{prefix}:query",
                require_children=False,
            )
        for index, candidate in enumerate(candidates):
            self._blocks.put_record(
                GraphHistoryKind.TRANSITION_CANDIDATE,
                candidate,
                operation_id=None if prefix is None else f"{prefix}:cand:{index}",
            )
        if prediction is not None:
            self.put_prediction(
                prediction,
                operation_id=None if prefix is None else f"{prefix}:prediction",
            )
        if observation is not None:
            self.put_observation(
                observation,
                operation_id=None if prefix is None else f"{prefix}:observation",
            )
        if admission is not None:
            self._blocks.put_record(
                GraphHistoryKind.TRANSITION_ADMISSION,
                admission,
                operation_id=None if prefix is None else f"{prefix}:admission",
            )
        return self._blocks.put_record(
            GraphHistoryKind.TRANSITION_RECEIPT,
            receipt,
            operation_id=prefix,
        )


class SemanticWorldSnapshotStore:
    """Persist world snapshots that bind graph, traces, and transition history."""

    INTERFACE: Final[str] = SEMANTIC_WORLD_SNAPSHOT_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | WorldHistoryBlockStore,
    ) -> None:
        self._blocks = world_history_blocks(store)

    @property
    def blocks(self) -> WorldHistoryBlockStore:
        return self._blocks

    @property
    def store(self) -> DurableCoordinationStore:
        return self._blocks.store

    def close(self) -> None:
        """Shared history blocks outlive a single facade."""

        return None

    def __enter__(self) -> "SemanticWorldSnapshotStore":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def put_event(
        self,
        event: ProgramEvent | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._blocks.put_record(
            GraphHistoryKind.PROGRAM_EVENT,
            event,
            operation_id=operation_id,
        )

    def put_trace_segment(
        self,
        segment: ExecutionTraceSegment | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._blocks.put_record(
            GraphHistoryKind.EXECUTION_TRACE_SEGMENT,
            segment,
            operation_id=operation_id,
        )

    def put_trace(
        self,
        trace: ExecutionTrace | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._blocks.put_record(
            GraphHistoryKind.EXECUTION_TRACE,
            trace,
            operation_id=operation_id,
        )

    def get_verified_trace(self, cid: str) -> ExecutionTrace:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.EXECUTION_TRACE
        )

    def get_verified_event(self, cid: str) -> ProgramEvent:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.PROGRAM_EVENT
        )

    def get_verified_snapshot(self, cid: str) -> SemanticWorldSnapshot:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.WORLD_SNAPSHOT
        )

    def append_world_snapshot(
        self,
        snapshot: SemanticWorldSnapshot | Mapping[str, Any],
        *,
        events: Sequence[ProgramEvent] = (),
        segments: Sequence[ExecutionTraceSegment] = (),
        traces: Sequence[ExecutionTrace] = (),
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(snapshot, SemanticWorldSnapshot):
            snapshot = SemanticWorldSnapshot.from_dict(snapshot)
        prefix = operation_id
        for index, event in enumerate(events):
            self.put_event(
                event, operation_id=None if prefix is None else f"{prefix}:event:{index}"
            )
        for index, segment in enumerate(segments):
            self.put_trace_segment(
                segment,
                operation_id=None if prefix is None else f"{prefix}:seg:{index}",
            )
        for index, trace in enumerate(traces):
            self.put_trace(
                trace, operation_id=None if prefix is None else f"{prefix}:trace:{index}"
            )
        for cid in snapshot.prediction_cids:
            self._blocks.get_verified_record(
                cid, expected_kind=GraphHistoryKind.TRANSITION_PREDICTION
            )
        for cid in snapshot.observation_cids:
            self._blocks.get_verified_record(
                cid, expected_kind=GraphHistoryKind.TRANSITION_OBSERVATION
            )
        return self._blocks.put_record(
            GraphHistoryKind.WORLD_SNAPSHOT,
            snapshot,
            operation_id=prefix,
        )


def append_program_graph_snapshot(
    store: DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | WorldHistoryBlockStore
    | LogicalProgramGraphStore,
    snapshot: ProgramGraphSnapshot | None = None,
    **kwargs: Any,
) -> GraphHistoryWriteResult:
    """Public ProgramGraphHistory@1 append for a sealed graph snapshot."""

    if isinstance(store, LogicalProgramGraphStore):
        facade = store
    else:
        facade = LogicalProgramGraphStore(store)
    return facade.append_program_graph_snapshot(snapshot, **kwargs)


def append_transition_receipt(
    store: DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | WorldHistoryBlockStore
    | ProgramTransitionLog,
    receipt: ProgramTransitionReceipt | None = None,
    **kwargs: Any,
) -> GraphHistoryWriteResult:
    """Public ProgramGraphHistory@1 append for a transition receipt."""

    if isinstance(store, ProgramTransitionLog):
        log = store
    else:
        log = ProgramTransitionLog(store)
    return log.append_transition_receipt(receipt, **kwargs)


__all__ = [
    "GRAPH_HISTORY_EVIDENCE",
    "GRAPH_HISTORY_MODULE_INTERFACE",
    "GRAPH_HISTORY_STORED_INTERFACE",
    "GRAPH_HISTORY_STORED_SCHEMA",
    "HISTORY_REFERENCE_FIELDS",
    "MAX_HISTORY_BYTES",
    "PROGRAM_GRAPH_HISTORY_INTERFACE",
    "SEMANTIC_WORLD_SNAPSHOT_INTERFACE",
    "SEMANTIC_WORLD_SNAPSHOT_SCHEMA",
    "GraphHistoryAdmissionError",
    "GraphHistoryConflictError",
    "GraphHistoryError",
    "GraphHistoryIntegrityError",
    "GraphHistoryKind",
    "GraphHistoryMissingReference",
    "GraphHistoryNotFound",
    "GraphHistoryWriteResult",
    "LogicalProgramGraphStore",
    "ProgramTransitionLog",
    "SemanticWorldSnapshot",
    "SemanticWorldSnapshotStore",
    "WorldHistoryBlockStore",
    "admit_sealed_history_record",
    "append_program_graph_snapshot",
    "append_transition_receipt",
    "seal_graph_history_record",
    "world_history_blocks",
]
