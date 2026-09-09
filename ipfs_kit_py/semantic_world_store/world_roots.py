"""Immutable generation-bearing semantic world-root manifests.

``SemanticWorldSnapshotStore`` implements ``SemanticWorldRoot@1`` persistence.
It binds every referenced immutable subroot into a deterministic manifest.
It does not admit semantics, decide transitions, or CAS-publish a mutable
current root (that belongs exclusively to SAWM-014).

Authority rules (normative, fail-closed):

* Datasets ``SemanticWorldRootIdentity@1`` remains the semantic identity.
  Kit generation is a storage-manifest field and is excluded from that
  identity payload.
* Every referenced subroot CID must already be stored and rehash before
  the parent snapshot or manifest may cite it.
* Unchanged subroots keep their prior CIDs.  Deltas cannot rewrite them.
* Manifest subroot lists are sorted by role then CID.
* Kit persists; it never accepts the world as current authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar, Final, Iterable, Mapping, Sequence

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    ProgramGraphError,
    apply_program_graph_delta,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    SEMANTIC_IDENTITY_EXCLUDED_FIELDS,
    SEMANTIC_WORLD_ROOT_IDENTITY_SCHEMA,
    ProgramIdentityError,
    SemanticWorldRootIdentity,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.semantic_world_store.graph_history import (
    PROGRAM_GRAPH_HISTORY_INTERFACE,
    GraphHistoryAdmissionError,
    GraphHistoryError,
    GraphHistoryIntegrityError,
    GraphHistoryNotFound,
    GraphHistoryWriteResult,
    LogicalProgramGraphStore,
    ProgramGraphHistory,
    ProgramTransitionLog,
    SemanticWorldHistoryKind,
    SemanticWorldHistoryStore,
    _as_mapping,
    _unique_cids,
)


SEMANTIC_WORLD_ROOT_INTERFACE: Final[str] = "SemanticWorldRoot@1"
SEMANTIC_WORLD_SNAPSHOT_INTERFACE: Final[str] = "SemanticWorldSnapshot@1"
WORLD_ROOT_MANIFEST_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-root-manifest@1"
)
WORLD_SNAPSHOT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-snapshot@1"
)
IMMUTABLE_SUBROOT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.immutable-subroot@1"
)

IDENTITY_SUBROOT_ROLES: Final[tuple[str, ...]] = (
    "analysis_limitation_index",
    "canonical_program_graph",
    "domain_state",
    "environment_binding_set",
    "policy",
    "program_graph_snapshot",
    "semantic_object_index",
)

_IDENTITY_ROLE_FIELDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "analysis_limitation_index": "analysis_limitation_index_cid",
        "canonical_program_graph": "canonical_program_graph_cid",
        "domain_state": "domain_state_cid",
        "environment_binding_set": "environment_binding_set_cid",
        "policy": "policy_cid",
        "program_graph_snapshot": "program_graph_snapshot_cid",
        "semantic_object_index": "semantic_object_index_cid",
    }
)

_MANIFEST_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface_id",
        "generation",
        "previous_manifest_cid",
        "world_snapshot_cid",
        "semantic_world_root_cid",
        "identity",
        "subroots",
        "retained_subroot_cids",
        "graph_delta_cid",
        "execution_trace_cids",
        "transition_receipt_cids",
        "world_root_manifest_cid",
    }
)


class WorldRootError(GraphHistoryError):
    """Base error for world-root manifest admission or retrieval."""


class WorldRootAdmissionError(WorldRootError, GraphHistoryAdmissionError):
    """Raised when a world-root write is rejected before mutation."""


class WorldRootIntegrityError(WorldRootError, GraphHistoryIntegrityError):
    """Raised when a stored world-root record does not re-verify."""


class WorldRootNotFound(WorldRootError, GraphHistoryNotFound):
    """Raised when a required world-root record is absent."""


def _closed(data: Mapping[str, Any], fields: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise WorldRootAdmissionError(f"{name} must be a mapping")
    actual = frozenset(data)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        problems: list[str] = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise WorldRootAdmissionError(f"{name} has " + "; ".join(problems))
    return dict(data)


def _require_generation(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise WorldRootAdmissionError("generation must be a non-negative integer")
    return value


def _optional_cid(value: object, name: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value:
        raise WorldRootAdmissionError(f"{name} must be a CID or null")
    return value


def _sorted_subroots(
    entries: Sequence[Mapping[str, Any]] | Iterable[tuple[str, str]],
) -> tuple[dict[str, str], ...]:
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in entries:
        if isinstance(item, Mapping):
            role = item.get("role")
            cid = item.get("cid")
        else:
            role, cid = item
        if type(role) is not str or not role:
            raise WorldRootAdmissionError("subroot role must be a non-empty string")
        if type(cid) is not str or not cid:
            raise WorldRootAdmissionError("subroot cid must be a canonical transport CID")
        key = (role, cid)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"role": role, "cid": cid})
    return tuple(sorted(normalized, key=lambda item: (item["role"], item["cid"])))


def _identity_subroots(identity: SemanticWorldRootIdentity) -> tuple[dict[str, str], ...]:
    entries = [
        (role, getattr(identity, field))
        for role, field in _IDENTITY_ROLE_FIELDS.items()
    ]
    return _sorted_subroots(entries)


def _reject_identity_exclusions(payload: Mapping[str, Any], *, path: str) -> None:
    forbidden = SEMANTIC_IDENTITY_EXCLUDED_FIELDS.intersection(payload)
    if forbidden:
        raise WorldRootAdmissionError(
            f"{path} must not contain excluded fields {sorted(forbidden)}"
        )


@dataclass(frozen=True, slots=True)
class SemanticWorldSnapshot:
    """Immutable world snapshot bound to datasets world-root identity."""

    identity: SemanticWorldRootIdentity
    execution_trace_cids: Sequence[str] = ()
    transition_receipt_cids: Sequence[str] = ()
    graph_delta_cid: str | None = None

    SCHEMA: ClassVar[str] = WORLD_SNAPSHOT_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_SNAPSHOT_INTERFACE
    CID_FIELD: ClassVar[str] = "world_snapshot_cid"

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SemanticWorldRootIdentity):
            raise WorldRootAdmissionError(
                "SemanticWorldSnapshot.identity must be a SemanticWorldRootIdentity"
            )
        object.__setattr__(
            self,
            "execution_trace_cids",
            _unique_cids(self.execution_trace_cids),
        )
        object.__setattr__(
            self,
            "transition_receipt_cids",
            _unique_cids(self.transition_receipt_cids),
        )
        object.__setattr__(
            self,
            "graph_delta_cid",
            _optional_cid(self.graph_delta_cid, "graph_delta_cid"),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "interface_id": self.INTERFACE,
            "semantic_world_root_cid": self.identity.semantic_world_root_cid,
            "identity": self.identity.to_dict(),
            "program_graph_snapshot_cid": self.identity.program_graph_snapshot_cid,
            "canonical_program_graph_cid": self.identity.canonical_program_graph_cid,
            "domain_state_cid": self.identity.domain_state_cid,
            "semantic_object_index_cid": self.identity.semantic_object_index_cid,
            "environment_binding_set_cid": self.identity.environment_binding_set_cid,
            "policy_cid": self.identity.policy_cid,
            "analysis_limitation_index_cid": self.identity.analysis_limitation_index_cid,
            "graph_delta_cid": self.graph_delta_cid,
            "execution_trace_cids": list(self.execution_trace_cids),
            "transition_receipt_cids": list(self.transition_receipt_cids),
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
        if not isinstance(data, Mapping):
            raise WorldRootAdmissionError("SemanticWorldSnapshot must be a mapping")
        payload = dict(data)
        claimed = payload.pop("world_snapshot_cid", None)
        identity_payload = payload.get("identity")
        try:
            identity = (
                identity_payload
                if isinstance(identity_payload, SemanticWorldRootIdentity)
                else SemanticWorldRootIdentity.from_dict(identity_payload)
            )
        except ProgramIdentityError as exc:
            raise WorldRootAdmissionError(str(exc)) from exc
        snapshot = cls(
            identity=identity,
            execution_trace_cids=payload.get("execution_trace_cids") or (),
            transition_receipt_cids=payload.get("transition_receipt_cids") or (),
            graph_delta_cid=payload.get("graph_delta_cid"),
        )
        if claimed is not None and claimed != snapshot.world_snapshot_cid:
            raise WorldRootIntegrityError(
                "claimed world_snapshot_cid does not rehash canonical bytes"
            )
        return snapshot


@dataclass(frozen=True, slots=True)
class SemanticWorldRootManifest:
    """Generation-bearing kit manifest that binds every immutable subroot."""

    generation: int
    identity: SemanticWorldRootIdentity
    world_snapshot_cid: str
    previous_manifest_cid: str | None = None
    subroots: Sequence[Mapping[str, str]] = ()
    retained_subroot_cids: Sequence[str] = ()
    graph_delta_cid: str | None = None
    execution_trace_cids: Sequence[str] = ()
    transition_receipt_cids: Sequence[str] = ()

    SCHEMA: ClassVar[str] = WORLD_ROOT_MANIFEST_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_INTERFACE
    CID_FIELD: ClassVar[str] = "world_root_manifest_cid"

    def __post_init__(self) -> None:
        object.__setattr__(self, "generation", _require_generation(self.generation))
        if not isinstance(self.identity, SemanticWorldRootIdentity):
            raise WorldRootAdmissionError(
                "SemanticWorldRootManifest.identity must be a SemanticWorldRootIdentity"
            )
        _reject_identity_exclusions(self.identity.to_dict(), path="identity")
        object.__setattr__(
            self,
            "world_snapshot_cid",
            _optional_cid(self.world_snapshot_cid, "world_snapshot_cid") or "",
        )
        if not self.world_snapshot_cid:
            raise WorldRootAdmissionError("world_snapshot_cid must be a CID")
        object.__setattr__(
            self,
            "previous_manifest_cid",
            _optional_cid(self.previous_manifest_cid, "previous_manifest_cid"),
        )
        object.__setattr__(self, "subroots", _sorted_subroots(self.subroots))
        object.__setattr__(
            self, "retained_subroot_cids", _unique_cids(self.retained_subroot_cids)
        )
        object.__setattr__(
            self, "graph_delta_cid", _optional_cid(self.graph_delta_cid, "graph_delta_cid")
        )
        object.__setattr__(
            self, "execution_trace_cids", _unique_cids(self.execution_trace_cids)
        )
        object.__setattr__(
            self,
            "transition_receipt_cids",
            _unique_cids(self.transition_receipt_cids),
        )
        if self.generation == 0 and self.previous_manifest_cid is not None:
            raise WorldRootAdmissionError(
                "generation-zero manifests must not have a previous manifest"
            )
        if self.generation > 0 and self.previous_manifest_cid is None:
            raise WorldRootAdmissionError(
                "non-zero generation requires previous_manifest_cid"
            )
        bound = {(item["role"], item["cid"]) for item in self.subroots}
        for role, field in _IDENTITY_ROLE_FIELDS.items():
            cid = getattr(self.identity, field)
            if (role, cid) not in bound:
                raise WorldRootAdmissionError(
                    f"manifest does not bind identity subroot {role}"
                )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "interface_id": self.INTERFACE,
            "generation": self.generation,
            "previous_manifest_cid": self.previous_manifest_cid,
            "world_snapshot_cid": self.world_snapshot_cid,
            "semantic_world_root_cid": self.identity.semantic_world_root_cid,
            "identity": self.identity.to_dict(),
            "subroots": [dict(item) for item in self.subroots],
            "retained_subroot_cids": list(self.retained_subroot_cids),
            "graph_delta_cid": self.graph_delta_cid,
            "execution_trace_cids": list(self.execution_trace_cids),
            "transition_receipt_cids": list(self.transition_receipt_cids),
        }

    @property
    def world_root_manifest_cid(self) -> str:
        return cid_for_artifact(self.identity_payload())

    def referenced_cids(self) -> tuple[str, ...]:
        cids = [
            self.world_snapshot_cid,
            self.identity.semantic_world_root_cid,
            *[item["cid"] for item in self.subroots],
            *self.retained_subroot_cids,
            *self.execution_trace_cids,
            *self.transition_receipt_cids,
        ]
        if self.previous_manifest_cid is not None:
            cids.append(self.previous_manifest_cid)
        if self.graph_delta_cid is not None:
            cids.append(self.graph_delta_cid)
        return _unique_cids(cids)

    def to_dict(self) -> dict[str, Any]:
        value = self.identity_payload()
        value["world_root_manifest_cid"] = self.world_root_manifest_cid
        return value

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SemanticWorldRootManifest":
        payload = _closed(data, _MANIFEST_FIELDS, "SemanticWorldRootManifest")
        claimed = payload.pop("world_root_manifest_cid")
        if payload.get("schema") != cls.SCHEMA:
            raise WorldRootAdmissionError("unsupported world-root manifest schema")
        if payload.get("interface_id") != cls.INTERFACE:
            raise WorldRootAdmissionError("unknown world-root manifest interface_id")
        try:
            identity = SemanticWorldRootIdentity.from_dict(payload["identity"])
        except ProgramIdentityError as exc:
            raise WorldRootAdmissionError(str(exc)) from exc
        if identity.semantic_world_root_cid != payload.get("semantic_world_root_cid"):
            raise WorldRootAdmissionError(
                "semantic_world_root_cid does not match identity"
            )
        manifest = cls(
            generation=payload["generation"],
            identity=identity,
            world_snapshot_cid=payload["world_snapshot_cid"],
            previous_manifest_cid=payload["previous_manifest_cid"],
            subroots=payload["subroots"],
            retained_subroot_cids=payload["retained_subroot_cids"],
            graph_delta_cid=payload["graph_delta_cid"],
            execution_trace_cids=payload["execution_trace_cids"],
            transition_receipt_cids=payload["transition_receipt_cids"],
        )
        if claimed != manifest.world_root_manifest_cid:
            raise WorldRootIntegrityError(
                "claimed world_root_manifest_cid does not rehash canonical bytes"
            )
        return manifest


def _as_identity(
    value: SemanticWorldRootIdentity | Mapping[str, Any],
) -> SemanticWorldRootIdentity:
    if isinstance(value, SemanticWorldRootIdentity):
        _reject_identity_exclusions(value.to_dict(), path="identity")
        return value
    if not isinstance(value, Mapping):
        raise WorldRootAdmissionError(
            "identity must be a SemanticWorldRootIdentity or mapping"
        )
    _reject_identity_exclusions(value, path="identity")
    try:
        return SemanticWorldRootIdentity.from_dict(value)
    except ProgramIdentityError as exc:
        raise WorldRootAdmissionError(str(exc)) from exc


class SemanticWorldSnapshotStore:
    """Persist world snapshots and generation-bearing root manifests.

    Composes ``DurableCoordinationStore`` through ``SemanticWorldHistoryStore``.
    """

    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_INTERFACE

    def __init__(
        self,
        store: Any,
    ) -> None:
        if isinstance(store, ProgramGraphHistory):
            self._history = store.history
            self.graphs = store.graphs
            self.transitions = store.transitions
        elif isinstance(store, SemanticWorldSnapshotStore):
            self._history = store._history
            self.graphs = store.graphs
            self.transitions = store.transitions
        elif isinstance(store, (SemanticWorldHistoryStore, DurableCoordinationStore)):
            self._history = (
                store
                if isinstance(store, SemanticWorldHistoryStore)
                else SemanticWorldHistoryStore(store)
            )
            self.graphs = LogicalProgramGraphStore(self._history)
            self.transitions = ProgramTransitionLog(self._history)
        else:
            self._history = SemanticWorldHistoryStore(store)
            self.graphs = LogicalProgramGraphStore(self._history)
            self.transitions = ProgramTransitionLog(self._history)

    @property
    def history(self) -> SemanticWorldHistoryStore:
        return self._history

    @property
    def store(self):
        return self._history.store

    def close(self) -> None:
        self._history.close()

    def __enter__(self) -> "SemanticWorldSnapshotStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def put_immutable_subroot(
        self,
        body: Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(body, Mapping):
            raise WorldRootAdmissionError("immutable subroot must be a mapping")
        payload = dict(body)
        if payload.get("schema") is None:
            payload["schema"] = IMMUTABLE_SUBROOT_SCHEMA
        claimed = payload.get("subroot_cid")
        identity_body = {key: value for key, value in payload.items() if key != "subroot_cid"}
        computed = cid_for_artifact(identity_body)
        if claimed is None:
            payload["subroot_cid"] = computed
        try:
            return self._history.put_artifact(
                SemanticWorldHistoryKind.IMMUTABLE_SUBROOT,
                payload,
                expected_cid=expected_cid or payload["subroot_cid"],
                operation_id=operation_id,
            )
        except GraphHistoryError as exc:
            raise self._translate(exc) from exc

    def _translate(self, exc: Exception) -> Exception:
        if isinstance(exc, WorldRootError):
            return exc
        if isinstance(exc, GraphHistoryNotFound):
            return WorldRootNotFound(str(exc))
        if isinstance(exc, GraphHistoryIntegrityError):
            return WorldRootIntegrityError(str(exc))
        if isinstance(exc, GraphHistoryAdmissionError):
            return WorldRootAdmissionError(str(exc))
        return exc

    def _require_history(
        self,
        cid: str,
        *,
        field: str,
        expected_kind: SemanticWorldHistoryKind | None = None,
    ) -> Mapping[str, Any]:
        try:
            return self._history.require_stored(
                cid, field=field, expected_kind=expected_kind
            )
        except GraphHistoryError as exc:
            raise self._translate(exc) from exc

    def _require_any_stored(self, cid: str, *, field: str) -> None:
        if self._history.has_identity(cid):
            try:
                self._history.get_verified_artifact(cid)
                return
            except GraphHistoryNotFound:
                pass
            except GraphHistoryIntegrityError as exc:
                raise WorldRootAdmissionError(
                    f"corrupt/missing reference: {field} does not re-verify"
                ) from exc
        raise WorldRootAdmissionError(
            f"store-before-reference: {field} is not a stored history record"
        )

    def _require_identity_subroots(self, identity: SemanticWorldRootIdentity) -> None:
        self._require_history(
            identity.program_graph_snapshot_cid,
            field="program_graph_snapshot_cid",
            expected_kind=SemanticWorldHistoryKind.PROGRAM_GRAPH_SNAPSHOT,
        )
        self._require_history(
            identity.canonical_program_graph_cid,
            field="canonical_program_graph_cid",
            expected_kind=SemanticWorldHistoryKind.CANONICAL_PROGRAM_GRAPH,
        )
        for role, field in _IDENTITY_ROLE_FIELDS.items():
            if role in {"program_graph_snapshot", "canonical_program_graph"}:
                continue
            self._require_any_stored(getattr(identity, field), field=field)

    def put_world_snapshot(
        self,
        snapshot: SemanticWorldSnapshot | Mapping[str, Any],
        *,
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        record = (
            snapshot
            if isinstance(snapshot, SemanticWorldSnapshot)
            else SemanticWorldSnapshot.from_dict(_as_mapping(snapshot))
        )
        self._require_identity_subroots(record.identity)
        for trace_cid in record.execution_trace_cids:
            self._require_history(
                trace_cid,
                field="execution_trace_cids",
                expected_kind=SemanticWorldHistoryKind.EXECUTION_TRACE,
            )
        for receipt_cid in record.transition_receipt_cids:
            self._require_history(
                receipt_cid,
                field="transition_receipt_cids",
                expected_kind=SemanticWorldHistoryKind.TRANSITION_RECEIPT,
            )
        if record.graph_delta_cid is not None:
            self._require_history(
                record.graph_delta_cid,
                field="graph_delta_cid",
                expected_kind=SemanticWorldHistoryKind.PROGRAM_GRAPH_DELTA,
            )
        try:
            return self._history.put_artifact(
                SemanticWorldHistoryKind.WORLD_SNAPSHOT,
                record.to_dict(),
                expected_cid=expected_cid or record.world_snapshot_cid,
                operation_id=operation_id,
            )
        except GraphHistoryError as exc:
            raise self._translate(exc) from exc

    def get_verified_snapshot(self, cid: str) -> SemanticWorldSnapshot:
        try:
            artifact = self._history.get_verified_artifact(
                cid, expected_kind=SemanticWorldHistoryKind.WORLD_SNAPSHOT
            )
        except GraphHistoryError as exc:
            raise self._translate(exc) from exc
        try:
            snapshot = SemanticWorldSnapshot.from_dict(dict(artifact["payload"]))
        except (WorldRootError, ProgramIdentityError) as exc:
            raise WorldRootIntegrityError(str(exc)) from exc
        if snapshot.world_snapshot_cid != artifact["identity_cid"]:
            raise WorldRootIntegrityError(
                "world snapshot CID does not rehash canonical identity bytes"
            )
        return snapshot

    def get_verified_manifest(self, cid: str) -> SemanticWorldRootManifest:
        try:
            artifact = self._history.get_verified_artifact(
                cid, expected_kind=SemanticWorldHistoryKind.WORLD_ROOT_MANIFEST
            )
        except GraphHistoryError as exc:
            raise self._translate(exc) from exc
        try:
            manifest = SemanticWorldRootManifest.from_dict(dict(artifact["payload"]))
        except (WorldRootError, ProgramIdentityError) as exc:
            raise WorldRootIntegrityError(str(exc)) from exc
        if manifest.world_root_manifest_cid != artifact["identity_cid"]:
            raise WorldRootIntegrityError(
                "world-root manifest CID does not rehash canonical identity bytes"
            )
        snapshot = self.get_verified_snapshot(manifest.world_snapshot_cid)
        if snapshot.identity.semantic_world_root_cid != manifest.identity.semantic_world_root_cid:
            raise WorldRootIntegrityError(
                "manifest identity does not match stored world snapshot"
            )
        for item in manifest.subroots:
            self._require_any_stored(item["cid"], field=f"subroots.{item['role']}")
        return manifest

    def build_world_root_manifest(
        self,
        identity: SemanticWorldRootIdentity | Mapping[str, Any],
        *,
        generation: int,
        previous_manifest_cid: str | None = None,
        execution_trace_cids: Sequence[str] = (),
        transition_receipt_cids: Sequence[str] = (),
        graph_delta_cid: str | None = None,
        extra_subroots: Sequence[Mapping[str, str]] | Iterable[tuple[str, str]] = (),
        expected_cid: str | None = None,
        operation_id: str | None = None,
    ) -> tuple[SemanticWorldRootManifest, GraphHistoryWriteResult]:
        return build_world_root_manifest(
            self,
            identity,
            generation=generation,
            previous_manifest_cid=previous_manifest_cid,
            execution_trace_cids=execution_trace_cids,
            transition_receipt_cids=transition_receipt_cids,
            graph_delta_cid=graph_delta_cid,
            extra_subroots=extra_subroots,
            expected_cid=expected_cid,
            operation_id=operation_id,
        )


def build_world_root_manifest(
    store: Any,
    identity: SemanticWorldRootIdentity | Mapping[str, Any],
    *,
    generation: int,
    previous_manifest_cid: str | None = None,
    execution_trace_cids: Sequence[str] = (),
    transition_receipt_cids: Sequence[str] = (),
    graph_delta_cid: str | None = None,
    extra_subroots: Sequence[Mapping[str, str]] | Iterable[tuple[str, str]] = (),
    expected_cid: str | None = None,
    operation_id: str | None = None,
) -> tuple[SemanticWorldRootManifest, GraphHistoryWriteResult]:
    """Persist a deterministic generation-bearing root that binds every subroot.

    This function never publishes a mutable current pointer.  CAS/recovery of
    the live root belongs exclusively to SAWM-014.
    """

    roots = (
        store
        if isinstance(store, SemanticWorldSnapshotStore)
        else SemanticWorldSnapshotStore(store)
    )
    record = _as_identity(identity)
    generation = _require_generation(generation)
    traces = _unique_cids(execution_trace_cids)
    receipts = _unique_cids(transition_receipt_cids)
    delta_cid = _optional_cid(graph_delta_cid, "graph_delta_cid")

    previous: SemanticWorldRootManifest | None = None
    if previous_manifest_cid is not None:
        previous = roots.get_verified_manifest(previous_manifest_cid)
        if generation != previous.generation + 1:
            raise WorldRootAdmissionError(
                "generation must be exactly one greater than the previous manifest"
            )
    elif generation != 0:
        raise WorldRootAdmissionError("first world-root manifest must use generation 0")

    snapshot = SemanticWorldSnapshot(
        identity=record,
        execution_trace_cids=traces,
        transition_receipt_cids=receipts,
        graph_delta_cid=delta_cid,
    )
    snapshot_result = roots.put_world_snapshot(
        snapshot,
        operation_id=None if operation_id is None else f"{operation_id}-snapshot",
    )

    if delta_cid is not None:
        delta = roots.graphs.get_verified_delta(delta_cid)
        current = roots.graphs.get_verified_snapshot(record.program_graph_snapshot_cid)
        if delta.previous_snapshot_cid == current.program_graph_snapshot_cid:
            raise WorldRootAdmissionError(
                "graph delta cannot cite the current snapshot as its previous snapshot"
            )
        previous_snapshot = roots.graphs.get_verified_snapshot(delta.previous_snapshot_cid)
        try:
            applied = apply_program_graph_delta(previous_snapshot, delta)
        except (ProgramGraphError, GraphHistoryError) as exc:
            raise WorldRootAdmissionError(str(exc)) from exc
        if set(applied["node_cids"]) != set(current.node_cids):
            raise WorldRootAdmissionError(
                "graph delta does not reconstruct the current snapshot node set"
            )
        unchanged = set(delta.retained_subroot_cids)
        if not unchanged <= set(previous_snapshot.node_cids):
            raise WorldRootAdmissionError("unchanged subroots must exist in the previous snapshot")
        if not unchanged <= set(current.node_cids):
            raise WorldRootAdmissionError("unchanged subroots must be preserved")

    previous_identity_cids: dict[str, str] = {}
    if previous is not None:
        previous_identity_cids = {
            role: getattr(previous.identity, field)
            for role, field in _IDENTITY_ROLE_FIELDS.items()
        }
    retained = []
    for role, field in _IDENTITY_ROLE_FIELDS.items():
        cid = getattr(record, field)
        if previous_identity_cids.get(role) == cid:
            retained.append(cid)
    if delta_cid is not None:
        retained.extend(delta.retained_subroot_cids)

    extra = _sorted_subroots(extra_subroots)
    for item in extra:
        roots._require_any_stored(item["cid"], field=f"subroots.{item['role']}")

    subroots = _sorted_subroots(
        [
            *_identity_subroots(record),
            *extra,
            *(("execution_trace", cid) for cid in traces),
            *(("transition_receipt", cid) for cid in receipts),
            *(("graph_delta", delta_cid),) if delta_cid is not None else (),
            ("world_snapshot", snapshot.world_snapshot_cid),
        ]
    )

    manifest = SemanticWorldRootManifest(
        generation=generation,
        identity=record,
        world_snapshot_cid=snapshot.world_snapshot_cid,
        previous_manifest_cid=previous_manifest_cid,
        subroots=subroots,
        retained_subroot_cids=_unique_cids(retained),
        graph_delta_cid=delta_cid,
        execution_trace_cids=traces,
        transition_receipt_cids=receipts,
    )
    if snapshot_result.cid != snapshot.world_snapshot_cid:
        raise WorldRootIntegrityError("stored world snapshot CID does not match manifest")
    for cid in manifest.referenced_cids():
        if cid == manifest.identity.semantic_world_root_cid:
            continue
        if cid == manifest.world_root_manifest_cid:
            continue
        roots._require_any_stored(cid, field="manifest.referenced_cids")

    try:
        result = roots.history.put_artifact(
            SemanticWorldHistoryKind.WORLD_ROOT_MANIFEST,
            manifest.to_dict(),
            expected_cid=expected_cid or manifest.world_root_manifest_cid,
            operation_id=operation_id,
        )
    except GraphHistoryError as exc:
        raise roots._translate(exc) from exc
    return manifest, result


__all__ = [
    "IDENTITY_SUBROOT_ROLES",
    "IMMUTABLE_SUBROOT_SCHEMA",
    "PROGRAM_GRAPH_HISTORY_INTERFACE",
    "SEMANTIC_WORLD_ROOT_INTERFACE",
    "SEMANTIC_WORLD_SNAPSHOT_INTERFACE",
    "WORLD_ROOT_MANIFEST_SCHEMA",
    "WORLD_SNAPSHOT_SCHEMA",
    "SemanticWorldRootManifest",
    "SemanticWorldSnapshot",
    "SemanticWorldSnapshotStore",
    "WorldRootAdmissionError",
    "WorldRootError",
    "WorldRootIntegrityError",
    "WorldRootNotFound",
    "build_world_root_manifest",
]
