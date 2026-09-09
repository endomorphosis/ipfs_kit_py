"""Immutable logical graph snapshots, traces, and transition receipts.

``LogicalProgramGraphStore`` and ``ProgramTransitionLog`` implement
``ProgramGraphHistory@1``.  They persist datasets graph/transition/trace
codecs over ``DurableCoordinationStore``.  They do not mint datasets CIDs,
admit semantics, decide transitions, or publish a mutable current root.

Authority rules (normative, fail-closed):

* Physical IPLD/Merkle block graphs stay acyclic.  Logical cycles are
  independently hashed node/edge records and remain queryable.
* Every parent record is stored only after each referenced history record
  already exists as verified bytes.
* Predictions, observations, and admissions are disjoint stored kinds.
  A prediction cannot decode as an observation and cannot self-admit.
* Repeated states keep distinct event/trace identities.
* Appends are idempotent: same identity + same bytes is unchanged;
  same identity rebound to different bytes is a conflict.
* Kit persists; it never accepts semantics, never converts a prediction
  into an observation, and never CAS-publishes a current world root.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Final, Iterable, Mapping, Optional, Sequence

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_execution import (
    EXECUTION_TRACE_SCHEMA,
    EXECUTION_TRACE_SEGMENT_SCHEMA,
    PROGRAM_EVENT_SCHEMA,
    ExecutionTrace,
    ExecutionTraceSegment,
    ProgramEvent,
    ProgramExecutionError,
    decode_program_execution_record,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    PROGRAM_GRAPH_DELTA_SCHEMA,
    PROGRAM_GRAPH_EDGE_SCHEMA,
    PROGRAM_GRAPH_NODE_SCHEMA,
    PROGRAM_GRAPH_SNAPSHOT_SCHEMA,
    ProgramGraphDelta,
    ProgramGraphEdge,
    ProgramGraphError,
    ProgramGraphNode,
    ProgramGraphSnapshot,
    apply_program_graph_delta,
    assert_physical_dag_acyclic,
    decode_program_graph_record,
    directed_logical_cycles,
    verify_program_graph_catalog,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    CANONICAL_PROGRAM_GRAPH_IDENTITY_SCHEMA,
    EXECUTION_TRACE_IDENTITY_SCHEMA,
    PROGRAM_EVENT_IDENTITY_SCHEMA,
    PROGRAM_GRAPH_DELTA_IDENTITY_SCHEMA,
    PROGRAM_GRAPH_SNAPSHOT_IDENTITY_SCHEMA,
    TRANSITION_IDENTITY_SCHEMA,
    CanonicalProgramGraphIdentity,
    ExecutionTraceIdentity,
    ProgramEventIdentity,
    ProgramGraphDeltaIdentity,
    ProgramGraphSnapshotIdentity,
    ProgramIdentityError,
    TransitionIdentity,
    TransitionKind,
    decode_identity_record,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_transition import (
    PROGRAM_TRANSITION_ADMISSION_SCHEMA,
    PROGRAM_TRANSITION_OBSERVATION_SCHEMA,
    PROGRAM_TRANSITION_PREDICTION_SCHEMA,
    PROGRAM_TRANSITION_QUERY_SCHEMA,
    PROGRAM_TRANSITION_RECEIPT_SCHEMA,
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
GRAPH_HISTORY_ARTIFACT_INTERFACE: Final[str] = "SemanticWorldGraphHistoryArtifact@1"
GRAPH_HISTORY_ARTIFACT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.graph-history-artifact@1"
)
GRAPH_HISTORY_SCHEMA_VERSION: Final[int] = 1

_OPS_DB_NAME: Final[str] = "semantic_world_history_index.sqlite3"
_SCHEMA_VERSION_SUFFIX: Final[re.Pattern[str]] = re.compile(r"@(\d+)$")
_SEALED_FIELDS: Final[frozenset[str]] = frozenset(
    ("schema", "interface_id", "kind", "payload")
)
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1


class SemanticWorldHistoryKind(str, Enum):
    """Closed taxonomy of immutable graph-history storage kinds."""

    PROGRAM_GRAPH_NODE = "program_graph_node"
    PROGRAM_GRAPH_EDGE = "program_graph_edge"
    PROGRAM_GRAPH_SNAPSHOT = "program_graph_snapshot"
    PROGRAM_GRAPH_DELTA = "program_graph_delta"
    CANONICAL_PROGRAM_GRAPH = "canonical_program_graph"
    PROGRAM_EVENT = "program_event"
    EXECUTION_TRACE_SEGMENT = "execution_trace_segment"
    EXECUTION_TRACE = "execution_trace"
    TRANSITION_QUERY = "transition_query"
    TRANSITION_PREDICTION = "transition_prediction"
    TRANSITION_OBSERVATION = "transition_observation"
    TRANSITION_ADMISSION = "transition_admission"
    TRANSITION_RECEIPT = "transition_receipt"
    IMMUTABLE_SUBROOT = "immutable_subroot"
    WORLD_SNAPSHOT = "world_snapshot"
    WORLD_ROOT_MANIFEST = "world_root_manifest"


_KIND_CID_FIELD: Final[Mapping[SemanticWorldHistoryKind, str]] = MappingProxyType(
    {
        SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE: "program_graph_node_cid",
        SemanticWorldHistoryKind.PROGRAM_GRAPH_EDGE: "program_graph_edge_cid",
        SemanticWorldHistoryKind.PROGRAM_GRAPH_SNAPSHOT: "program_graph_snapshot_cid",
        SemanticWorldHistoryKind.PROGRAM_GRAPH_DELTA: "program_graph_delta_cid",
        SemanticWorldHistoryKind.CANONICAL_PROGRAM_GRAPH: "canonical_program_graph_cid",
        SemanticWorldHistoryKind.PROGRAM_EVENT: "program_event_cid",
        SemanticWorldHistoryKind.EXECUTION_TRACE_SEGMENT: "execution_trace_segment_cid",
        SemanticWorldHistoryKind.EXECUTION_TRACE: "execution_trace_cid",
        SemanticWorldHistoryKind.TRANSITION_QUERY: "query_cid",
        SemanticWorldHistoryKind.TRANSITION_PREDICTION: "prediction_cid",
        SemanticWorldHistoryKind.TRANSITION_OBSERVATION: "observation_cid",
        SemanticWorldHistoryKind.TRANSITION_ADMISSION: "admission_cid",
        SemanticWorldHistoryKind.TRANSITION_RECEIPT: "receipt_cid",
        SemanticWorldHistoryKind.IMMUTABLE_SUBROOT: "subroot_cid",
        SemanticWorldHistoryKind.WORLD_SNAPSHOT: "world_snapshot_cid",
        SemanticWorldHistoryKind.WORLD_ROOT_MANIFEST: "world_root_manifest_cid",
    }
)

_SCHEMA_TO_KIND: Final[Mapping[str, SemanticWorldHistoryKind]] = MappingProxyType(
    {
        PROGRAM_GRAPH_NODE_SCHEMA: SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE,
        PROGRAM_GRAPH_EDGE_SCHEMA: SemanticWorldHistoryKind.PROGRAM_GRAPH_EDGE,
        PROGRAM_GRAPH_SNAPSHOT_SCHEMA: SemanticWorldHistoryKind.PROGRAM_GRAPH_SNAPSHOT,
        PROGRAM_GRAPH_SNAPSHOT_IDENTITY_SCHEMA: SemanticWorldHistoryKind.PROGRAM_GRAPH_SNAPSHOT,
        PROGRAM_GRAPH_DELTA_SCHEMA: SemanticWorldHistoryKind.PROGRAM_GRAPH_DELTA,
        PROGRAM_GRAPH_DELTA_IDENTITY_SCHEMA: SemanticWorldHistoryKind.PROGRAM_GRAPH_DELTA,
        CANONICAL_PROGRAM_GRAPH_IDENTITY_SCHEMA: SemanticWorldHistoryKind.CANONICAL_PROGRAM_GRAPH,
        PROGRAM_EVENT_SCHEMA: SemanticWorldHistoryKind.PROGRAM_EVENT,
        PROGRAM_EVENT_IDENTITY_SCHEMA: SemanticWorldHistoryKind.PROGRAM_EVENT,
        EXECUTION_TRACE_SEGMENT_SCHEMA: SemanticWorldHistoryKind.EXECUTION_TRACE_SEGMENT,
        EXECUTION_TRACE_SCHEMA: SemanticWorldHistoryKind.EXECUTION_TRACE,
        EXECUTION_TRACE_IDENTITY_SCHEMA: SemanticWorldHistoryKind.EXECUTION_TRACE,
        PROGRAM_TRANSITION_QUERY_SCHEMA: SemanticWorldHistoryKind.TRANSITION_QUERY,
        PROGRAM_TRANSITION_PREDICTION_SCHEMA: SemanticWorldHistoryKind.TRANSITION_PREDICTION,
        PROGRAM_TRANSITION_OBSERVATION_SCHEMA: SemanticWorldHistoryKind.TRANSITION_OBSERVATION,
        PROGRAM_TRANSITION_ADMISSION_SCHEMA: SemanticWorldHistoryKind.TRANSITION_ADMISSION,
        PROGRAM_TRANSITION_RECEIPT_SCHEMA: SemanticWorldHistoryKind.TRANSITION_RECEIPT,
        TRANSITION_IDENTITY_SCHEMA: SemanticWorldHistoryKind.TRANSITION_QUERY,
    }
)

_TRANSITION_KIND_TO_HISTORY: Final[Mapping[str, SemanticWorldHistoryKind]] = MappingProxyType(
    {
        TransitionKind.QUERY.value: SemanticWorldHistoryKind.TRANSITION_QUERY,
        TransitionKind.PREDICTION.value: SemanticWorldHistoryKind.TRANSITION_PREDICTION,
        TransitionKind.OBSERVATION.value: SemanticWorldHistoryKind.TRANSITION_OBSERVATION,
        TransitionKind.ADMISSION.value: SemanticWorldHistoryKind.TRANSITION_ADMISSION,
        TransitionKind.ACCEPTED.value: SemanticWorldHistoryKind.TRANSITION_RECEIPT,
    }
)

PREDICTION_HISTORY_KIND: Final[str] = SemanticWorldHistoryKind.TRANSITION_PREDICTION.value
OBSERVATION_HISTORY_KIND: Final[str] = SemanticWorldHistoryKind.TRANSITION_OBSERVATION.value


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


@dataclass(frozen=True, slots=True)
class GraphHistoryWriteResult:
    """Verified local write; identity CID is the caller-facing address."""

    cid: str
    storage_cid: str
    kind: SemanticWorldHistoryKind
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


def _coerce_kind(
    kind: SemanticWorldHistoryKind | str,
) -> SemanticWorldHistoryKind:
    if isinstance(kind, SemanticWorldHistoryKind):
        return kind
    if isinstance(kind, str):
        try:
            return SemanticWorldHistoryKind(kind)
        except ValueError as exc:
            raise GraphHistoryAdmissionError(
                f"unknown graph-history artifact kind: {kind!r}"
            ) from exc
    raise GraphHistoryAdmissionError(
        "kind must be a SemanticWorldHistoryKind or its closed string value"
    )


def _schema_version(schema: str) -> int | None:
    match = _SCHEMA_VERSION_SUFFIX.search(schema)
    if match is None:
        return None
    return int(match.group(1))


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
            f"artifact is not canonical JSON: {exc}"
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


def validate_graph_history_schema(schema: object) -> str:
    if not isinstance(schema, str) or not schema:
        raise GraphHistoryAdmissionError("artifact schema must be a non-empty string")
    version = _schema_version(schema)
    if version is None:
        raise GraphHistoryAdmissionError(
            "artifact schema must declare a version suffix @N"
        )
    if version != GRAPH_HISTORY_SCHEMA_VERSION:
        raise GraphHistoryAdmissionError(
            f"unknown artifact schema version: expected @{GRAPH_HISTORY_SCHEMA_VERSION}, "
            f"got @{version}"
        )
    if schema != GRAPH_HISTORY_ARTIFACT_SCHEMA:
        raise GraphHistoryAdmissionError(f"unknown artifact schema: {schema!r}")
    return schema


def seal_graph_history_artifact(
    kind: SemanticWorldHistoryKind | str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
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
        "schema": GRAPH_HISTORY_ARTIFACT_SCHEMA,
        "interface_id": GRAPH_HISTORY_ARTIFACT_INTERFACE,
        "kind": artifact_kind.value,
        "payload": body,
    }
    try:
        reject_private_raw_source(sealed, path="$")
    except Exception as exc:
        raise GraphHistoryAdmissionError(str(exc)) from exc
    data = _canonical_bytes(sealed)
    if len(data) > MAX_ARTIFACT_BYTES:
        raise GraphHistoryAdmissionError(
            f"artifact exceeds MAX_ARTIFACT_BYTES ({len(data)} > {MAX_ARTIFACT_BYTES})"
        )
    return sealed


def cid_for_graph_history_artifact(
    kind: SemanticWorldHistoryKind | str,
    payload: Mapping[str, Any],
) -> str:
    return cid_for_artifact(seal_graph_history_artifact(kind, payload))


def admit_graph_history_record(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise GraphHistoryIntegrityError("sealed artifact must be a mapping")
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
            "sealed artifact has " + "; ".join(problems)
        )
    try:
        validate_graph_history_schema(record["schema"])
    except GraphHistoryAdmissionError as exc:
        raise GraphHistoryIntegrityError(str(exc)) from exc
    if record.get("interface_id") != GRAPH_HISTORY_ARTIFACT_INTERFACE:
        raise GraphHistoryIntegrityError("unknown sealed artifact interface_id")
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
    except Exception as exc:
        raise GraphHistoryIntegrityError(str(exc)) from exc
    sealed = {
        "schema": GRAPH_HISTORY_ARTIFACT_SCHEMA,
        "interface_id": GRAPH_HISTORY_ARTIFACT_INTERFACE,
        "kind": kind.value,
        "payload": body,
    }
    if cid_for_artifact(dict(record)) != cid_for_artifact(sealed):
        raise GraphHistoryIntegrityError("sealed artifact is not in canonical form")
    return sealed


def identity_cid_from_history_payload(
    kind: SemanticWorldHistoryKind | str,
    payload: Mapping[str, Any],
) -> str:
    artifact_kind = _coerce_kind(kind)
    field = _KIND_CID_FIELD[artifact_kind]
    value = payload.get(field)
    try:
        return validate_verified_cid(value, field)
    except SemanticGovernorStoreContractError as exc:
        raise GraphHistoryIntegrityError(
            f"payload.{field} must be a canonical transport CID"
        ) from exc


def _as_mapping(record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    to_dict = getattr(record, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, Mapping):
            return dict(payload)
    raise GraphHistoryAdmissionError(
        "history record must be a mapping or provide to_dict()"
    )


def _kind_for_payload(
    payload: Mapping[str, Any],
    *,
    default: SemanticWorldHistoryKind | None = None,
) -> SemanticWorldHistoryKind:
    schema = payload.get("schema")
    if type(schema) is str and schema == TRANSITION_IDENTITY_SCHEMA:
        transition_kind = payload.get("transition_kind")
        mapped = _TRANSITION_KIND_TO_HISTORY.get(str(transition_kind))
        if mapped is None:
            raise GraphHistoryAdmissionError(
                f"unsupported TransitionIdentity kind {transition_kind!r}"
            )
        return mapped
    if type(schema) is str and schema in _SCHEMA_TO_KIND:
        return _SCHEMA_TO_KIND[schema]
    if default is not None:
        return default
    raise GraphHistoryAdmissionError(
        f"unsupported history schema {schema!r}"
    )


def _unique_cids(values: Iterable[Any]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        if item is None:
            continue
        if type(item) is not str or not item:
            raise GraphHistoryAdmissionError("referenced CID must be a non-empty string")
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return tuple(sorted(ordered))


def _optional_cid_list(*groups: Any) -> tuple[str, ...]:
    collected: list[str] = []
    for group in groups:
        if group is None:
            continue
        if type(group) is str:
            collected.append(group)
            continue
        if isinstance(group, Sequence) and not isinstance(group, (str, bytes)):
            for item in group:
                if item is None:
                    continue
                collected.append(item)
            continue
        raise GraphHistoryAdmissionError("CID collection must be a string or sequence")
    return _unique_cids(collected)


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
            try:
                self._connection.close()
            except sqlite3.ProgrammingError:
                return

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


def _coordination_store(store: Any) -> DurableCoordinationStore:
    if isinstance(store, DurableCoordinationStore):
        return store
    if isinstance(store, SemanticWorldHistoryStore):
        return store.store
    if isinstance(store, SemanticWorldArtifactStore):
        return store.store
    if isinstance(store, VerifiedSemanticBlockStore):
        return store.store
    artifacts = getattr(store, "artifacts", None)
    if isinstance(artifacts, SemanticWorldArtifactStore):
        return artifacts.store
    inner = getattr(store, "store", None)
    if isinstance(inner, DurableCoordinationStore):
        return inner
    raise TypeError(
        "store must be a DurableCoordinationStore, SemanticWorldArtifactStore, "
        "VerifiedSemanticBlockStore, or SemanticWorldHistoryStore"
    )


class SemanticWorldHistoryStore:
    """Sealed identity-indexed block store for graph, transition, and root records."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | "SemanticWorldHistoryStore",
    ) -> None:
        if isinstance(store, SemanticWorldHistoryStore):
            self._store = store._store
            self._index = store._index
            self._owns_index = False
            return
        self._store = _coordination_store(store)
        self._index = _HistoryIndex(self._store)
        self._owns_index = True
        self._rebuild_identity_index()

    @property
    def store(self) -> DurableCoordinationStore:
        return self._store

    def close(self) -> None:
        if self._owns_index:
            self._index.close()
            self._owns_index = False

    def __enter__(self) -> "SemanticWorldHistoryStore":
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
            if not isinstance(raw, Mapping) or raw.get("schema") != GRAPH_HISTORY_ARTIFACT_SCHEMA:
                continue
            try:
                sealed = admit_graph_history_record(raw)
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
        return bool(self._store.has(cid))

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

    def require_stored(
        self,
        cid: str,
        *,
        field: str,
        expected_kind: SemanticWorldHistoryKind | None = None,
    ) -> Mapping[str, Any]:
        try:
            artifact = self.get_verified_artifact(cid, expected_kind=expected_kind)
        except GraphHistoryNotFound as exc:
            raise GraphHistoryAdmissionError(
                f"store-before-reference: {field} is not a stored history record"
            ) from exc
        except GraphHistoryIntegrityError as exc:
            raise GraphHistoryAdmissionError(
                f"corrupt/missing reference: {field} does not re-verify"
            ) from exc
        return artifact

    def put_artifact(
        self,
        kind: SemanticWorldHistoryKind | str,
        payload: Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> GraphHistoryWriteResult:
        artifact_kind = _coerce_kind(kind)
        sealed = seal_graph_history_artifact(artifact_kind, payload)
        identity_cid = identity_cid_from_history_payload(artifact_kind, sealed["payload"])
        return self._put_sealed(
            kind=artifact_kind,
            payload=sealed["payload"],
            identity_cid=identity_cid,
            expected_cid=expected_cid,
            operation_id=operation_id,
            replicate=replicate,
        )

    def _put_sealed(
        self,
        *,
        kind: SemanticWorldHistoryKind,
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
                f"forged or mismatched artifact CID: computed {identity_cid}, "
                f"expected {expected_cid}"
            )

        sealed = seal_graph_history_artifact(kind, payload)
        storage_cid = cid_for_artifact(sealed)
        payload_identity = identity_cid_from_history_payload(kind, sealed["payload"])
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
            self.get_verified_artifact(identity_cid, expected_kind=kind)
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

    def get_verified_artifact(
        self,
        cid: str,
        *,
        expected_kind: Optional[SemanticWorldHistoryKind | str] = None,
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
            raise GraphHistoryIntegrityError(
                f"{storage_cid} did not decode to a mapping"
            )
        sealed = admit_graph_history_record(raw)
        recomputed = cid_for_artifact(sealed)
        if recomputed != storage_cid:
            raise GraphHistoryIntegrityError(
                f"forged sealed artifact: recomputed {recomputed}, expected {storage_cid}"
            )
        kind = SemanticWorldHistoryKind(sealed["kind"])
        if indexed_kind is not None and indexed_kind != kind.value:
            raise GraphHistoryIntegrityError(
                f"index kind {indexed_kind} does not match stored {kind.value}"
            )
        if expected_kind is not None:
            wanted = _coerce_kind(expected_kind)
            if kind is not wanted:
                raise GraphHistoryIntegrityError(
                    f"wrong artifact kind: stored {kind.value}, "
                    f"expected {wanted.value}"
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


def _decode_graph_record(payload: Mapping[str, Any]) -> Any:
    schema = payload.get("schema")
    try:
        if schema in {
            PROGRAM_GRAPH_NODE_SCHEMA,
            PROGRAM_GRAPH_EDGE_SCHEMA,
            PROGRAM_GRAPH_SNAPSHOT_SCHEMA,
            PROGRAM_GRAPH_DELTA_SCHEMA,
        }:
            return decode_program_graph_record(payload)
        if schema in {
            CANONICAL_PROGRAM_GRAPH_IDENTITY_SCHEMA,
            PROGRAM_GRAPH_SNAPSHOT_IDENTITY_SCHEMA,
            PROGRAM_GRAPH_DELTA_IDENTITY_SCHEMA,
            PROGRAM_EVENT_IDENTITY_SCHEMA,
            EXECUTION_TRACE_IDENTITY_SCHEMA,
            TRANSITION_IDENTITY_SCHEMA,
        }:
            return decode_identity_record(payload)
        if schema in {PROGRAM_EVENT_SCHEMA, EXECUTION_TRACE_SCHEMA, EXECUTION_TRACE_SEGMENT_SCHEMA}:
            return decode_program_execution_record(payload)
        if schema in {
            PROGRAM_TRANSITION_QUERY_SCHEMA,
            PROGRAM_TRANSITION_PREDICTION_SCHEMA,
            PROGRAM_TRANSITION_OBSERVATION_SCHEMA,
            PROGRAM_TRANSITION_ADMISSION_SCHEMA,
            PROGRAM_TRANSITION_RECEIPT_SCHEMA,
        }:
            return decode_transition_record(payload)
    except (
        ProgramGraphError,
        ProgramIdentityError,
        ProgramExecutionError,
        ProgramTransitionError,
    ) as exc:
        raise GraphHistoryAdmissionError(str(exc)) from exc
    raise GraphHistoryAdmissionError(f"unsupported history schema {schema!r}")


def _history_refs_for(kind: SemanticWorldHistoryKind, payload: Mapping[str, Any]) -> dict[str, tuple[str, SemanticWorldHistoryKind | None]]:
    refs: dict[str, tuple[str, SemanticWorldHistoryKind | None]] = {}

    def add(
        field: str,
        value: Any,
        expected: SemanticWorldHistoryKind | None = None,
    ) -> None:
        if value is None:
            return
        if type(value) is str:
            refs[f"{field}:{value}"] = (value, expected)
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                if item is None:
                    continue
                if type(item) is not str:
                    raise GraphHistoryAdmissionError(
                        f"{field} must contain CID strings"
                    )
                refs[f"{field}:{item}"] = (item, expected)
            return

    if kind is SemanticWorldHistoryKind.PROGRAM_GRAPH_EDGE:
        add("source_node_cid", payload.get("source_node_cid"), SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE)
        add("target_node_cid", payload.get("target_node_cid"), SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE)
    elif kind is SemanticWorldHistoryKind.PROGRAM_GRAPH_SNAPSHOT:
        add("node_cids", payload.get("node_cids"), SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE)
        add("edge_cids", payload.get("edge_cids"), SemanticWorldHistoryKind.PROGRAM_GRAPH_EDGE)
        add(
            "canonical_program_graph_cid",
            payload.get("canonical_program_graph_cid"),
            SemanticWorldHistoryKind.CANONICAL_PROGRAM_GRAPH,
        )
        add("retained_subroot_cids", payload.get("retained_subroot_cids"), SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE)
    elif kind is SemanticWorldHistoryKind.PROGRAM_GRAPH_DELTA:
        add(
            "previous_snapshot_cid",
            payload.get("previous_snapshot_cid"),
            SemanticWorldHistoryKind.PROGRAM_GRAPH_SNAPSHOT,
        )
        add("added_node_cids", payload.get("added_node_cids"), SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE)
        add("added_edge_cids", payload.get("added_edge_cids"), SemanticWorldHistoryKind.PROGRAM_GRAPH_EDGE)
        add(
            "retained_subroot_cids",
            payload.get("retained_subroot_cids"),
            SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE,
        )
    elif kind is SemanticWorldHistoryKind.CANONICAL_PROGRAM_GRAPH:
        add("node_cids", payload.get("node_cids"), SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE)
        add("edge_cids", payload.get("edge_cids"), SemanticWorldHistoryKind.PROGRAM_GRAPH_EDGE)
    elif kind is SemanticWorldHistoryKind.PROGRAM_EVENT:
        add("predecessor_event_cid", payload.get("predecessor_event_cid"), SemanticWorldHistoryKind.PROGRAM_EVENT)
    elif kind is SemanticWorldHistoryKind.EXECUTION_TRACE_SEGMENT:
        add("parent_trace_cid", payload.get("parent_trace_cid"), SemanticWorldHistoryKind.EXECUTION_TRACE)
        add("event_cids", payload.get("event_cids"), SemanticWorldHistoryKind.PROGRAM_EVENT)
        add("start_event_cid", payload.get("start_event_cid"), SemanticWorldHistoryKind.PROGRAM_EVENT)
        add("end_event_cid", payload.get("end_event_cid"), SemanticWorldHistoryKind.PROGRAM_EVENT)
    elif kind is SemanticWorldHistoryKind.EXECUTION_TRACE:
        add("event_cids", payload.get("event_cids"), SemanticWorldHistoryKind.PROGRAM_EVENT)
        add(
            "segment_cids",
            payload.get("segment_cids"),
            SemanticWorldHistoryKind.EXECUTION_TRACE_SEGMENT,
        )
        add("parent_trace_cid", payload.get("parent_trace_cid"), SemanticWorldHistoryKind.EXECUTION_TRACE)
    elif kind is SemanticWorldHistoryKind.TRANSITION_PREDICTION:
        add("query_cid", payload.get("query_cid"), SemanticWorldHistoryKind.TRANSITION_QUERY)
    elif kind is SemanticWorldHistoryKind.TRANSITION_OBSERVATION:
        add("query_cid", payload.get("query_cid"), SemanticWorldHistoryKind.TRANSITION_QUERY)
    elif kind is SemanticWorldHistoryKind.TRANSITION_ADMISSION:
        add("query_cid", payload.get("query_cid"), SemanticWorldHistoryKind.TRANSITION_QUERY)
        add("prediction_cid", payload.get("prediction_cid"), SemanticWorldHistoryKind.TRANSITION_PREDICTION)
        add("observation_cid", payload.get("observation_cid"), SemanticWorldHistoryKind.TRANSITION_OBSERVATION)
    elif kind is SemanticWorldHistoryKind.TRANSITION_RECEIPT:
        add("query_cid", payload.get("query_cid"), SemanticWorldHistoryKind.TRANSITION_QUERY)
        add("admission_cid", payload.get("admission_cid"), SemanticWorldHistoryKind.TRANSITION_ADMISSION)
        add("prediction_cid", payload.get("prediction_cid"), SemanticWorldHistoryKind.TRANSITION_PREDICTION)
        add("observation_cid", payload.get("observation_cid"), SemanticWorldHistoryKind.TRANSITION_OBSERVATION)
    return refs


class LogicalProgramGraphStore:
    """Persist immutable node/edge sets, snapshots, deltas, and traces."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | SemanticWorldHistoryStore,
    ) -> None:
        self._history = (
            store if isinstance(store, SemanticWorldHistoryStore) else SemanticWorldHistoryStore(store)
        )

    @property
    def history(self) -> SemanticWorldHistoryStore:
        return self._history

    @property
    def store(self) -> DurableCoordinationStore:
        return self._history.store

    def close(self) -> None:
        self._history.close()

    def __enter__(self) -> "LogicalProgramGraphStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _put_typed(
        self,
        record: Any,
        *,
        default_kind: SemanticWorldHistoryKind,
        operation_id: str | None = None,
        expected_cid: str | None = None,
        require_refs: bool = True,
    ) -> GraphHistoryWriteResult:
        payload = _as_mapping(record)
        try:
            decoded = _decode_graph_record(payload)
            payload = decoded.to_dict() if hasattr(decoded, "to_dict") else payload
        except GraphHistoryAdmissionError:
            if "schema" in payload:
                raise
        kind = _kind_for_payload(payload, default=default_kind)
        if kind is not default_kind:
            raise GraphHistoryAdmissionError(
                f"record kind {kind.value} does not match {default_kind.value}"
            )
        if require_refs:
            self._assert_store_before_reference(kind, payload)
        return self._history.put_artifact(
            kind,
            payload,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def _assert_store_before_reference(
        self,
        kind: SemanticWorldHistoryKind,
        payload: Mapping[str, Any],
    ) -> None:
        refs = _history_refs_for(kind, payload)
        identity_field = _KIND_CID_FIELD[kind]
        own_cid = payload.get(identity_field)
        for _key, (cid, expected) in refs.items():
            if own_cid is not None and cid == own_cid:
                raise GraphHistoryAdmissionError(
                    "physical IPLD block graph must be acyclic"
                )
            field = _key.split(":", 1)[0]
            self._history.require_stored(cid, field=field, expected_kind=expected)

    def put_node(
        self,
        node: ProgramGraphNode | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._put_typed(
            node,
            default_kind=SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE,
            expected_cid=expected_cid,
            operation_id=operation_id,
            require_refs=False,
        )

    def put_edge(
        self,
        edge: ProgramGraphEdge | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._put_typed(
            edge,
            default_kind=SemanticWorldHistoryKind.PROGRAM_GRAPH_EDGE,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def put_canonical_graph(
        self,
        graph: CanonicalProgramGraphIdentity | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._put_typed(
            graph,
            default_kind=SemanticWorldHistoryKind.CANONICAL_PROGRAM_GRAPH,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def put_event(
        self,
        event: ProgramEvent | ProgramEventIdentity | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._put_typed(
            event,
            default_kind=SemanticWorldHistoryKind.PROGRAM_EVENT,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def put_trace_segment(
        self,
        segment: ExecutionTraceSegment | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._put_typed(
            segment,
            default_kind=SemanticWorldHistoryKind.EXECUTION_TRACE_SEGMENT,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def put_trace(
        self,
        trace: ExecutionTrace | ExecutionTraceIdentity | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        payload = _as_mapping(trace)
        kind = _kind_for_payload(
            payload, default=SemanticWorldHistoryKind.EXECUTION_TRACE
        )
        if kind is SemanticWorldHistoryKind.EXECUTION_TRACE_SEGMENT:
            raise GraphHistoryAdmissionError("trace segment cannot be stored as a trace")
        own_cid = payload.get("execution_trace_cid")
        parent = payload.get("parent_trace_cid")
        if own_cid is not None and parent == own_cid:
            raise GraphHistoryAdmissionError(
                "physical IPLD block graph must be acyclic"
            )
        for segment_cid in payload.get("segment_cids") or ():
            segment = self._history.require_stored(
                segment_cid,
                field="segment_cids",
                expected_kind=SemanticWorldHistoryKind.EXECUTION_TRACE_SEGMENT,
            )
            parent_of_segment = segment["payload"].get("parent_trace_cid")
            if own_cid is not None and parent_of_segment == own_cid:
                raise GraphHistoryAdmissionError(
                    "physical IPLD block graph must be acyclic"
                )
        return self._put_typed(
            payload,
            default_kind=SemanticWorldHistoryKind.EXECUTION_TRACE,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def append_program_graph_snapshot(
        self,
        snapshot: ProgramGraphSnapshot | Mapping[str, Any],
        *,
        nodes: Sequence[ProgramGraphNode | Mapping[str, Any]] = (),
        edges: Sequence[ProgramGraphEdge | Mapping[str, Any]] = (),
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        for index, node in enumerate(nodes):
            self.put_node(
                node,
                operation_id=None if operation_id is None else f"{operation_id}-node-{index}",
            )
        for index, edge in enumerate(edges):
            self.put_edge(
                edge,
                operation_id=None if operation_id is None else f"{operation_id}-edge-{index}",
            )

        payload = _as_mapping(snapshot)
        try:
            record = (
                snapshot
                if isinstance(snapshot, ProgramGraphSnapshot)
                else ProgramGraphSnapshot.from_dict(payload)
            )
        except ProgramGraphError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        payload = record.to_dict()

        stored_nodes: list[ProgramGraphNode] = []
        for node_cid in record.node_cids:
            try:
                stored_nodes.append(self.get_verified_node(node_cid))
            except GraphHistoryNotFound as exc:
                raise GraphHistoryAdmissionError(
                    "store-before-reference: node_cids is not a stored history record"
                ) from exc
            except GraphHistoryIntegrityError as exc:
                raise GraphHistoryAdmissionError(
                    "corrupt/missing reference: node_cids does not re-verify"
                ) from exc
        stored_edges: list[ProgramGraphEdge] = []
        for edge_cid in record.edge_cids:
            try:
                stored_edges.append(self.get_verified_edge(edge_cid))
            except GraphHistoryNotFound as exc:
                raise GraphHistoryAdmissionError(
                    "store-before-reference: edge_cids is not a stored history record"
                ) from exc
            except GraphHistoryIntegrityError as exc:
                raise GraphHistoryAdmissionError(
                    "corrupt/missing reference: edge_cids does not re-verify"
                ) from exc

        try:
            canonical = CanonicalProgramGraphIdentity(
                language=record.language,
                graph_kind=record.graph_kind,
                node_cids=record.node_cids,
                edge_cids=record.edge_cids,
                environment_binding_set_cid=record.environment_binding_set_cid,
                unavailable_dimensions=record.unavailable_dimensions,
            )
        except ProgramIdentityError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        if canonical.canonical_program_graph_cid != record.canonical_program_graph_cid:
            raise GraphHistoryAdmissionError("canonical_program_graph_cid does not verify")
        self.put_canonical_graph(canonical)

        try:
            verify_program_graph_catalog(record, nodes=stored_nodes, edges=stored_edges)
        except ProgramGraphError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc

        catalog: dict[str, Mapping[str, Any]] = {}
        for item in (*stored_nodes, *stored_edges, record):
            catalog[getattr(item, item.CID_FIELD)] = item.identity_payload()
        try:
            assert_physical_dag_acyclic(catalog)
        except ProgramGraphError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc

        return self._history.put_artifact(
            SemanticWorldHistoryKind.PROGRAM_GRAPH_SNAPSHOT,
            payload,
            expected_cid=expected_cid or record.program_graph_snapshot_cid,
            operation_id=operation_id,
        )

    def put_delta(
        self,
        delta: ProgramGraphDelta | ProgramGraphDeltaIdentity | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        payload = _as_mapping(delta)
        try:
            record = (
                delta
                if isinstance(delta, (ProgramGraphDelta, ProgramGraphDeltaIdentity))
                else ProgramGraphDelta.from_dict(payload)
                if payload.get("schema") == PROGRAM_GRAPH_DELTA_SCHEMA
                else ProgramGraphDeltaIdentity.from_dict(payload)
            )
        except (ProgramGraphError, ProgramIdentityError) as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        payload = record.to_dict()
        try:
            previous = self.get_verified_snapshot(record.previous_snapshot_cid)
        except GraphHistoryNotFound as exc:
            raise GraphHistoryAdmissionError(
                "store-before-reference: previous_snapshot_cid is not a stored history record"
            ) from exc
        if isinstance(record, ProgramGraphDelta):
            try:
                apply_program_graph_delta(previous, record)
            except ProgramGraphError as exc:
                raise GraphHistoryAdmissionError(str(exc)) from exc
        return self._put_typed(
            payload,
            default_kind=SemanticWorldHistoryKind.PROGRAM_GRAPH_DELTA,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def get_verified_node(self, cid: str) -> ProgramGraphNode:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.PROGRAM_GRAPH_NODE
        )
        try:
            node = ProgramGraphNode.from_dict(dict(artifact["payload"]))
        except ProgramGraphError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        if node.program_graph_node_cid != artifact["identity_cid"]:
            raise GraphHistoryIntegrityError("node CID does not rehash canonical identity bytes")
        return node

    def get_verified_edge(self, cid: str) -> ProgramGraphEdge:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.PROGRAM_GRAPH_EDGE
        )
        try:
            edge = ProgramGraphEdge.from_dict(dict(artifact["payload"]))
        except ProgramGraphError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        if edge.program_graph_edge_cid != artifact["identity_cid"]:
            raise GraphHistoryIntegrityError("edge CID does not rehash canonical identity bytes")
        return edge

    def get_verified_snapshot(self, cid: str) -> ProgramGraphSnapshot:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.PROGRAM_GRAPH_SNAPSHOT
        )
        payload = dict(artifact["payload"])
        try:
            snapshot = ProgramGraphSnapshot.from_dict(payload)
        except ProgramGraphError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        if snapshot.program_graph_snapshot_cid != artifact["identity_cid"]:
            raise GraphHistoryIntegrityError(
                "snapshot CID does not rehash canonical identity bytes"
            )
        nodes = [self.get_verified_node(node_cid) for node_cid in snapshot.node_cids]
        edges = [self.get_verified_edge(edge_cid) for edge_cid in snapshot.edge_cids]
        try:
            verify_program_graph_catalog(snapshot, nodes=nodes, edges=edges)
        except ProgramGraphError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        return snapshot

    def get_verified_delta(self, cid: str) -> ProgramGraphDelta:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.PROGRAM_GRAPH_DELTA
        )
        payload = dict(artifact["payload"])
        try:
            if payload.get("schema") == PROGRAM_GRAPH_DELTA_IDENTITY_SCHEMA:
                identity = ProgramGraphDeltaIdentity.from_dict(payload)
                delta = ProgramGraphDelta(
                    previous_snapshot_cid=identity.previous_snapshot_cid,
                    added_node_cids=identity.added_node_cids,
                    removed_node_cids=identity.removed_node_cids,
                    added_edge_cids=identity.added_edge_cids,
                    removed_edge_cids=identity.removed_edge_cids,
                    retained_subroot_cids=identity.retained_subroot_cids,
                )
            else:
                delta = ProgramGraphDelta.from_dict(payload)
        except (ProgramGraphError, ProgramIdentityError) as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        if delta.program_graph_delta_cid != artifact["identity_cid"]:
            raise GraphHistoryIntegrityError("delta CID does not rehash canonical identity bytes")
        previous = self.get_verified_snapshot(delta.previous_snapshot_cid)
        try:
            apply_program_graph_delta(previous, delta)
        except ProgramGraphError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        return delta

    def get_verified_event(self, cid: str) -> Mapping[str, Any]:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.PROGRAM_EVENT
        )
        payload = dict(artifact["payload"])
        if payload.get("program_event_cid") != artifact["identity_cid"]:
            raise GraphHistoryIntegrityError("event CID does not rehash canonical identity bytes")
        return MappingProxyType(payload)

    def get_verified_trace(self, cid: str) -> Mapping[str, Any]:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.EXECUTION_TRACE
        )
        payload = dict(artifact["payload"])
        if payload.get("execution_trace_cid") != artifact["identity_cid"]:
            raise GraphHistoryIntegrityError("trace CID does not rehash canonical identity bytes")
        for event_cid in payload.get("event_cids") or ():
            self.get_verified_event(event_cid)
        return MappingProxyType(payload)

    def query_logical_cycles(
        self, snapshot_cid: str
    ) -> tuple[tuple[str, ...], ...]:
        snapshot = self.get_verified_snapshot(snapshot_cid)
        edges = [self.get_verified_edge(cid) for cid in snapshot.edge_cids]
        return directed_logical_cycles(edges)

    def load_snapshot_catalog(
        self, snapshot_cid: str
    ) -> dict[str, Mapping[str, Any]]:
        snapshot = self.get_verified_snapshot(snapshot_cid)
        catalog: dict[str, Mapping[str, Any]] = {
            snapshot.program_graph_snapshot_cid: snapshot.identity_payload()
        }
        for node_cid in snapshot.node_cids:
            node = self.get_verified_node(node_cid)
            catalog[node.program_graph_node_cid] = node.identity_payload()
        for edge_cid in snapshot.edge_cids:
            edge = self.get_verified_edge(edge_cid)
            catalog[edge.program_graph_edge_cid] = edge.identity_payload()
        assert_physical_dag_acyclic(catalog)
        return catalog


class ProgramTransitionLog:
    """Append-only query/prediction/observation/admission/receipt log."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | SemanticWorldHistoryStore,
    ) -> None:
        self._history = (
            store if isinstance(store, SemanticWorldHistoryStore) else SemanticWorldHistoryStore(store)
        )

    @property
    def history(self) -> SemanticWorldHistoryStore:
        return self._history

    @property
    def store(self) -> DurableCoordinationStore:
        return self._history.store

    def close(self) -> None:
        self._history.close()

    def __enter__(self) -> "ProgramTransitionLog":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _put_transition(
        self,
        record: Any,
        *,
        default_kind: SemanticWorldHistoryKind,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        payload = _as_mapping(record)
        try:
            decoded = _decode_graph_record(payload)
            payload = decoded.to_dict()
        except GraphHistoryAdmissionError:
            if "schema" in payload:
                raise
        kind = _kind_for_payload(payload, default=default_kind)
        if kind is not default_kind:
            raise GraphHistoryAdmissionError(
                f"record kind {kind.value} does not match {default_kind.value}"
            )
        if kind is SemanticWorldHistoryKind.TRANSITION_PREDICTION:
            if payload.get("proposal_only") is not True:
                raise GraphHistoryAdmissionError("predictions are proposal-only")
            if payload.get("schema") == PROGRAM_TRANSITION_OBSERVATION_SCHEMA:
                raise GraphHistoryAdmissionError(
                    "observations cannot be stored as predictions"
                )
        if kind is SemanticWorldHistoryKind.TRANSITION_OBSERVATION:
            if payload.get("schema") == PROGRAM_TRANSITION_PREDICTION_SCHEMA:
                raise GraphHistoryAdmissionError(
                    "predictions cannot decode as observations"
                )
            if payload.get("proposal_only") is True:
                raise GraphHistoryAdmissionError("observations cannot be proposal-only")
        refs = _history_refs_for(kind, payload)
        for key, (cid, expected) in refs.items():
            field = key.split(":", 1)[0]
            self._history.require_stored(cid, field=field, expected_kind=expected)
        return self._history.put_artifact(
            kind,
            payload,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def put_query(
        self,
        query: ProgramTransitionQuery | TransitionIdentity | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._put_transition(
            query,
            default_kind=SemanticWorldHistoryKind.TRANSITION_QUERY,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def put_prediction(
        self,
        prediction: ProgramTransitionPrediction | TransitionIdentity | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._put_transition(
            prediction,
            default_kind=SemanticWorldHistoryKind.TRANSITION_PREDICTION,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def put_observation(
        self,
        observation: ProgramTransitionObservation | TransitionIdentity | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._put_transition(
            observation,
            default_kind=SemanticWorldHistoryKind.TRANSITION_OBSERVATION,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def put_admission(
        self,
        admission: ProgramTransitionAdmission | TransitionIdentity | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self._put_transition(
            admission,
            default_kind=SemanticWorldHistoryKind.TRANSITION_ADMISSION,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def append_transition_receipt(
        self,
        receipt: ProgramTransitionReceipt | Mapping[str, Any],
        *,
        query: ProgramTransitionQuery | Mapping[str, Any] | None = None,
        prediction: ProgramTransitionPrediction | Mapping[str, Any] | None = None,
        observation: ProgramTransitionObservation | Mapping[str, Any] | None = None,
        admission: ProgramTransitionAdmission | Mapping[str, Any] | None = None,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if query is not None:
            self.put_query(query)
        if prediction is not None:
            self.put_prediction(prediction)
        if observation is not None:
            self.put_observation(observation)
        if admission is not None:
            self.put_admission(admission)
        payload = _as_mapping(receipt)
        try:
            record = (
                receipt
                if isinstance(receipt, ProgramTransitionReceipt)
                else ProgramTransitionReceipt.from_dict(payload)
            )
        except ProgramTransitionError as exc:
            raise GraphHistoryAdmissionError(str(exc)) from exc
        if record.prediction_authoritative:
            raise GraphHistoryAdmissionError(
                "kit persists but never treats predictions as authoritative"
            )
        return self._put_transition(
            record.to_dict(),
            default_kind=SemanticWorldHistoryKind.TRANSITION_RECEIPT,
            expected_cid=expected_cid or record.receipt_cid,
            operation_id=operation_id,
        )

    def get_verified_query(self, cid: str) -> Mapping[str, Any]:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.TRANSITION_QUERY
        )
        return MappingProxyType(dict(artifact["payload"]))

    def get_verified_prediction(self, cid: str) -> ProgramTransitionPrediction | TransitionIdentity:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.TRANSITION_PREDICTION
        )
        payload = dict(artifact["payload"])
        if payload.get("schema") == PROGRAM_TRANSITION_OBSERVATION_SCHEMA:
            raise GraphHistoryIntegrityError("predictions cannot decode as observations")
        try:
            if payload.get("schema") == TRANSITION_IDENTITY_SCHEMA:
                record: Any = TransitionIdentity.from_dict(payload)
            else:
                record = ProgramTransitionPrediction.from_dict(payload)
        except (ProgramTransitionError, ProgramIdentityError) as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        return record

    def get_verified_observation(self, cid: str) -> ProgramTransitionObservation | TransitionIdentity:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.TRANSITION_OBSERVATION
        )
        payload = dict(artifact["payload"])
        try:
            decode_transition_observation(payload)
        except ProgramTransitionError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        try:
            if payload.get("schema") == TRANSITION_IDENTITY_SCHEMA:
                return TransitionIdentity.from_dict(payload)
            return ProgramTransitionObservation.from_dict(payload)
        except (ProgramTransitionError, ProgramIdentityError) as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc

    def get_verified_admission(self, cid: str) -> Mapping[str, Any]:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.TRANSITION_ADMISSION
        )
        return MappingProxyType(dict(artifact["payload"]))

    def get_verified_receipt(self, cid: str) -> ProgramTransitionReceipt:
        artifact = self._history.get_verified_artifact(
            cid, expected_kind=SemanticWorldHistoryKind.TRANSITION_RECEIPT
        )
        payload = dict(artifact["payload"])
        try:
            receipt = ProgramTransitionReceipt.from_dict(payload)
        except ProgramTransitionError as exc:
            raise GraphHistoryIntegrityError(str(exc)) from exc
        if receipt.receipt_cid != artifact["identity_cid"]:
            raise GraphHistoryIntegrityError(
                "receipt CID does not rehash canonical identity bytes"
            )
        self.get_verified_query(receipt.query_cid)
        self.get_verified_admission(receipt.admission_cid)
        if receipt.prediction_cid is not None:
            prediction = self.get_verified_prediction(receipt.prediction_cid)
            prediction_payload = (
                prediction.to_dict() if hasattr(prediction, "to_dict") else dict(prediction)
            )
            if prediction_payload.get("schema") == PROGRAM_TRANSITION_OBSERVATION_SCHEMA:
                raise GraphHistoryIntegrityError(
                    "predictions cannot decode as observations"
                )
        if receipt.observation_cid is not None:
            self.get_verified_observation(receipt.observation_cid)
        if receipt.prediction_authoritative:
            raise GraphHistoryIntegrityError(
                "stored receipt treats a prediction as authoritative"
            )
        return receipt

    def prediction_is_distinct_from_observation(
        self, prediction_cid: str, observation_cid: str
    ) -> bool:
        prediction = self._history.get_verified_artifact(
            prediction_cid, expected_kind=SemanticWorldHistoryKind.TRANSITION_PREDICTION
        )
        observation = self._history.get_verified_artifact(
            observation_cid, expected_kind=SemanticWorldHistoryKind.TRANSITION_OBSERVATION
        )
        if prediction["kind"] == observation["kind"]:
            return False
        if prediction["identity_cid"] == observation["identity_cid"]:
            return False
        try:
            decode_transition_observation(dict(prediction["payload"]))
        except ProgramTransitionError:
            return True
        return False


class ProgramGraphHistory:
    """ProgramGraphHistory@1 facade over logical graphs and transition receipts."""

    INTERFACE: ClassVar[str] = PROGRAM_GRAPH_HISTORY_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | SemanticWorldHistoryStore,
    ) -> None:
        self._history = (
            store if isinstance(store, SemanticWorldHistoryStore) else SemanticWorldHistoryStore(store)
        )
        self.graphs = LogicalProgramGraphStore(self._history)
        self.transitions = ProgramTransitionLog(self._history)

    @property
    def history(self) -> SemanticWorldHistoryStore:
        return self._history

    @property
    def store(self) -> DurableCoordinationStore:
        return self._history.store

    def close(self) -> None:
        self._history.close()

    def __enter__(self) -> "ProgramGraphHistory":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def append_program_graph_snapshot(
        self,
        snapshot: ProgramGraphSnapshot | Mapping[str, Any],
        *,
        nodes: Sequence[ProgramGraphNode | Mapping[str, Any]] = (),
        edges: Sequence[ProgramGraphEdge | Mapping[str, Any]] = (),
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self.graphs.append_program_graph_snapshot(
            snapshot,
            nodes=nodes,
            edges=edges,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )

    def append_transition_receipt(
        self,
        receipt: ProgramTransitionReceipt | Mapping[str, Any],
        *,
        query: ProgramTransitionQuery | Mapping[str, Any] | None = None,
        prediction: ProgramTransitionPrediction | Mapping[str, Any] | None = None,
        observation: ProgramTransitionObservation | Mapping[str, Any] | None = None,
        admission: ProgramTransitionAdmission | Mapping[str, Any] | None = None,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        return self.transitions.append_transition_receipt(
            receipt,
            query=query,
            prediction=prediction,
            observation=observation,
            admission=admission,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )


def append_program_graph_snapshot(
    store: Any,
    snapshot: ProgramGraphSnapshot | Mapping[str, Any],
    *,
    nodes: Sequence[ProgramGraphNode | Mapping[str, Any]] = (),
    edges: Sequence[ProgramGraphEdge | Mapping[str, Any]] = (),
    expected_cid: str | None = None,
    operation_id: str | None = None,
) -> GraphHistoryWriteResult:
    """Persist one sealed program-graph snapshot after its node/edge set."""

    if isinstance(store, LogicalProgramGraphStore):
        graphs = store
    elif isinstance(store, ProgramGraphHistory):
        graphs = store.graphs
    else:
        graphs = LogicalProgramGraphStore(store)
    return graphs.append_program_graph_snapshot(
        snapshot,
        nodes=nodes,
        edges=edges,
        expected_cid=expected_cid,
        operation_id=operation_id,
    )


def append_transition_receipt(
    store: Any,
    receipt: ProgramTransitionReceipt | Mapping[str, Any],
    *,
    query: ProgramTransitionQuery | Mapping[str, Any] | None = None,
    prediction: ProgramTransitionPrediction | Mapping[str, Any] | None = None,
    observation: ProgramTransitionObservation | Mapping[str, Any] | None = None,
    admission: ProgramTransitionAdmission | Mapping[str, Any] | None = None,
    expected_cid: str | None = None,
    operation_id: str | None = None,
) -> GraphHistoryWriteResult:
    """Persist one transition receipt after its query/evidence records."""

    if isinstance(store, ProgramTransitionLog):
        log = store
    elif isinstance(store, ProgramGraphHistory):
        log = store.transitions
    else:
        log = ProgramTransitionLog(store)
    return log.append_transition_receipt(
        receipt,
        query=query,
        prediction=prediction,
        observation=observation,
        admission=admission,
        expected_cid=expected_cid,
        operation_id=operation_id,
    )


__all__ = [
    "GRAPH_HISTORY_ARTIFACT_INTERFACE",
    "GRAPH_HISTORY_ARTIFACT_SCHEMA",
    "OBSERVATION_HISTORY_KIND",
    "PREDICTION_HISTORY_KIND",
    "PROGRAM_GRAPH_HISTORY_INTERFACE",
    "GraphHistoryAdmissionError",
    "GraphHistoryConflictError",
    "GraphHistoryError",
    "GraphHistoryIntegrityError",
    "GraphHistoryNotFound",
    "GraphHistoryWriteResult",
    "LogicalProgramGraphStore",
    "ProgramGraphHistory",
    "ProgramTransitionLog",
    "SemanticWorldHistoryKind",
    "SemanticWorldHistoryStore",
    "admit_graph_history_record",
    "append_program_graph_snapshot",
    "append_transition_receipt",
    "cid_for_graph_history_artifact",
    "seal_graph_history_artifact",
    "_as_mapping",
    "_unique_cids",
]
