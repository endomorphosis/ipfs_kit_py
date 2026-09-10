"""Immutable world snapshots and generation-bearing root manifests.

``SemanticWorldSnapshotStore`` and ``SemanticWorldRootManifest`` implement
``SemanticWorldRoot@1``.  They bind every referenced immutable subroot into a
deterministic, generation-bearing manifest.  Kit persists; it never accepts
semantics or mutates a current-root pointer (SAWM-014 owns CAS/recovery).

Authority rules (normative, fail-closed):

* ``SemanticWorldRootIdentity`` remains datasets-owned and excludes
  generation, projections, and operational CAS fields.
* The kit manifest binds generation and every referenced subroot CID.
  Manifest identity is the sealed storage CID and is independent of input
  order.
* Store-before-reference: a snapshot or manifest is refused unless every
  referenced CID already resolves to stored bytes.
* Unchanged graph subroots stay bound by CID.  Missing or corrupt
  references fail closed.
* No mutable current root, compare-and-swap, WAL replay, or replication
  adapter lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Final, Iterable, Mapping, Sequence

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_graph import (
    ProgramGraphSnapshot,
)
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    SEMANTIC_IDENTITY_EXCLUDED_FIELDS,
    CanonicalProgramGraphIdentity,
    ProgramIdentityError,
    SemanticWorldRootIdentity,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.semantic_world_store.artifacts import SemanticWorldArtifactStore
from ipfs_kit_py.semantic_world_store.graph_history import (
    PROGRAM_GRAPH_HISTORY_INTERFACE,
    GraphHistoryAdmissionError,
    GraphHistoryError,
    GraphHistoryIntegrityError,
    GraphHistoryNotFound,
    HistoryBlockStore,
    HistoryRecordKind,
    HistoryWriteResult,
    LogicalProgramGraphStore,
    ProgramTransitionLog,
    assert_history_physical_dag_acyclic,
    history_block_store,
    seal_history_record,
)
from ipfs_kit_py.semantic_world_store.verified_store import VerifiedSemanticBlockStore


SEMANTIC_WORLD_ROOT_INTERFACE: Final[str] = "SemanticWorldRoot@1"
SEMANTIC_WORLD_SNAPSHOT_INTERFACE: Final[str] = "SemanticWorldSnapshot@1"
SEMANTIC_WORLD_ROOT_MANIFEST_INTERFACE: Final[str] = "SemanticWorldRootManifest@1"
WORLD_SNAPSHOT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-snapshot@1"
)
WORLD_ROOT_MANIFEST_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-root-manifest@1"
)

class WorldRootError(GraphHistoryError):
    """Base error for immutable world snapshots and root manifests."""


class WorldRootAdmissionError(WorldRootError, GraphHistoryAdmissionError):
    """Raised when a world snapshot or root manifest is refused."""


class WorldRootIntegrityError(WorldRootError, GraphHistoryIntegrityError):
    """Raised when a stored world snapshot or manifest fails rehash."""


class WorldRootNotFound(WorldRootError, GraphHistoryNotFound):
    """Raised when a required world snapshot or manifest is absent."""


def _unique_sorted_cids(values: Iterable[Any], name: str) -> tuple[str, ...]:
    from ipfs_kit_py.semantic_world_store.graph_history import _require_cid

    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        cid = _require_cid(value, name)
        if cid in seen:
            continue
        seen.add(cid)
        items.append(cid)
    return tuple(sorted(items))


def _optional_sorted_cids(values: Sequence[Any] | None, name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        raise WorldRootAdmissionError(f"{name} must be a sequence of CIDs")
    return _unique_sorted_cids(values, name)


def _reject_excluded_identity_fields(payload: Mapping[str, Any], *, path: str) -> None:
    forbidden = SEMANTIC_IDENTITY_EXCLUDED_FIELDS.intersection(payload)
    if forbidden:
        raise WorldRootAdmissionError(
            f"{path} rejects excluded semantic-identity fields {sorted(forbidden)}"
        )


def compute_referenced_subroots(
    *,
    identity: SemanticWorldRootIdentity,
    world_snapshot_cid: str | None = None,
    graph_history_head_cid: str | None = None,
    transition_log_head_cid: str | None = None,
    previous_manifest_cid: str | None = None,
    execution_trace_cids: Sequence[str] = (),
    transition_receipt_cids: Sequence[str] = (),
) -> tuple[str, ...]:
    """Return the sorted unique CID set a root must bind."""

    refs: list[str] = [
        identity.semantic_world_root_cid,
        identity.domain_state_cid,
        identity.canonical_program_graph_cid,
        identity.program_graph_snapshot_cid,
        identity.semantic_object_index_cid,
        identity.environment_binding_set_cid,
        identity.policy_cid,
        identity.analysis_limitation_index_cid,
    ]
    for value in (
        world_snapshot_cid,
        graph_history_head_cid,
        transition_log_head_cid,
        previous_manifest_cid,
    ):
        if value is not None:
            refs.append(value)
    refs.extend(execution_trace_cids)
    refs.extend(transition_receipt_cids)
    return _unique_sorted_cids(refs, "referenced_subroot_cid")


@dataclass(frozen=True, slots=True)
class SemanticWorldSnapshot:
    """Immutable world snapshot binding graph, traces, and transition evidence."""

    identity: SemanticWorldRootIdentity
    execution_trace_cids: Sequence[str] = ()
    transition_receipt_cids: Sequence[str] = ()
    graph_history_head_cid: str | None = None
    transition_log_head_cid: str | None = None

    SCHEMA: ClassVar[str] = WORLD_SNAPSHOT_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_SNAPSHOT_INTERFACE

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SemanticWorldRootIdentity):
            raise WorldRootAdmissionError(
                "SemanticWorldSnapshot.identity must be a SemanticWorldRootIdentity"
            )
        _reject_excluded_identity_fields(self.identity.to_dict(), path="identity")
        object.__setattr__(
            self,
            "execution_trace_cids",
            _optional_sorted_cids(self.execution_trace_cids, "execution_trace_cid"),
        )
        object.__setattr__(
            self,
            "transition_receipt_cids",
            _optional_sorted_cids(
                self.transition_receipt_cids, "transition_receipt_cid"
            ),
        )
        from ipfs_kit_py.semantic_world_store.graph_history import _optional_cid

        object.__setattr__(
            self,
            "graph_history_head_cid",
            _optional_cid(self.graph_history_head_cid, "graph_history_head_cid"),
        )
        object.__setattr__(
            self,
            "transition_log_head_cid",
            _optional_cid(self.transition_log_head_cid, "transition_log_head_cid"),
        )

    @property
    def semantic_world_root_cid(self) -> str:
        return self.identity.semantic_world_root_cid

    @property
    def referenced_subroot_cids(self) -> tuple[str, ...]:
        return compute_referenced_subroots(
            identity=self.identity,
            graph_history_head_cid=self.graph_history_head_cid,
            transition_log_head_cid=self.transition_log_head_cid,
            execution_trace_cids=self.execution_trace_cids,
            transition_receipt_cids=self.transition_receipt_cids,
        )

    def to_payload(self) -> dict[str, Any]:
        identity = self.identity.to_dict()
        _reject_excluded_identity_fields(identity, path="identity")
        return {
            "schema": self.SCHEMA,
            "interface": self.INTERFACE,
            "identity": identity,
            "execution_trace_cids": list(self.execution_trace_cids),
            "transition_receipt_cids": list(self.transition_receipt_cids),
            "graph_history_head_cid": self.graph_history_head_cid,
            "transition_log_head_cid": self.transition_log_head_cid,
            "referenced_subroot_cids": list(self.referenced_subroot_cids),
        }

    @property
    def world_snapshot_cid(self) -> str:
        sealed = seal_history_record(
            HistoryRecordKind.WORLD_SNAPSHOT, self.to_payload()
        )
        return cid_for_artifact(sealed)

    @classmethod
    def from_payload(cls, data: Mapping[str, Any]) -> "SemanticWorldSnapshot":
        if not isinstance(data, Mapping):
            raise WorldRootIntegrityError("world snapshot must be a mapping")
        expected = frozenset(
            {
                "schema",
                "interface",
                "identity",
                "execution_trace_cids",
                "transition_receipt_cids",
                "graph_history_head_cid",
                "transition_log_head_cid",
                "referenced_subroot_cids",
            }
        )
        actual = frozenset(data)
        if actual != expected:
            missing = sorted(expected - actual)
            unknown = sorted(actual - expected)
            problems: list[str] = []
            if missing:
                problems.append(f"missing {', '.join(missing)}")
            if unknown:
                problems.append(f"unknown {', '.join(unknown)}")
            raise WorldRootIntegrityError(
                "world snapshot has " + "; ".join(problems)
            )
        if data["schema"] != cls.SCHEMA:
            raise WorldRootIntegrityError("unsupported world-snapshot schema")
        if data["interface"] != cls.INTERFACE:
            raise WorldRootIntegrityError("unsupported world-snapshot interface")
        identity_payload = data["identity"]
        if not isinstance(identity_payload, Mapping):
            raise WorldRootIntegrityError("world snapshot identity must be a mapping")
        _reject_excluded_identity_fields(identity_payload, path="identity")
        try:
            identity = SemanticWorldRootIdentity.from_dict(identity_payload)
        except ProgramIdentityError as exc:
            raise WorldRootIntegrityError(str(exc)) from exc
        snapshot = cls(
            identity=identity,
            execution_trace_cids=data["execution_trace_cids"],
            transition_receipt_cids=data["transition_receipt_cids"],
            graph_history_head_cid=data["graph_history_head_cid"],
            transition_log_head_cid=data["transition_log_head_cid"],
        )
        claimed = data["referenced_subroot_cids"]
        if tuple(claimed) != snapshot.referenced_subroot_cids:
            raise WorldRootIntegrityError(
                "world snapshot referenced_subroot_cids are not the deterministic binding"
            )
        return snapshot


@dataclass(frozen=True, slots=True)
class SemanticWorldRootManifest:
    """Generation-bearing immutable root; not a mutable current pointer."""

    generation: int
    identity: SemanticWorldRootIdentity
    world_snapshot_cid: str | None = None
    graph_history_head_cid: str | None = None
    transition_log_head_cid: str | None = None
    previous_manifest_cid: str | None = None
    execution_trace_cids: Sequence[str] = ()
    transition_receipt_cids: Sequence[str] = ()

    SCHEMA: ClassVar[str] = WORLD_ROOT_MANIFEST_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_MANIFEST_INTERFACE

    def __post_init__(self) -> None:
        from ipfs_kit_py.semantic_world_store.graph_history import (
            _optional_cid,
            _require_generation,
        )

        if not isinstance(self.identity, SemanticWorldRootIdentity):
            raise WorldRootAdmissionError(
                "SemanticWorldRootManifest.identity must be a SemanticWorldRootIdentity"
            )
        _reject_excluded_identity_fields(self.identity.to_dict(), path="identity")
        object.__setattr__(
            self, "generation", _require_generation(self.generation, "generation")
        )
        object.__setattr__(
            self,
            "world_snapshot_cid",
            _optional_cid(self.world_snapshot_cid, "world_snapshot_cid"),
        )
        object.__setattr__(
            self,
            "graph_history_head_cid",
            _optional_cid(self.graph_history_head_cid, "graph_history_head_cid"),
        )
        object.__setattr__(
            self,
            "transition_log_head_cid",
            _optional_cid(self.transition_log_head_cid, "transition_log_head_cid"),
        )
        object.__setattr__(
            self,
            "previous_manifest_cid",
            _optional_cid(self.previous_manifest_cid, "previous_manifest_cid"),
        )
        object.__setattr__(
            self,
            "execution_trace_cids",
            _optional_sorted_cids(self.execution_trace_cids, "execution_trace_cid"),
        )
        object.__setattr__(
            self,
            "transition_receipt_cids",
            _optional_sorted_cids(
                self.transition_receipt_cids, "transition_receipt_cid"
            ),
        )

    @property
    def semantic_world_root_cid(self) -> str:
        return self.identity.semantic_world_root_cid

    @property
    def referenced_subroot_cids(self) -> tuple[str, ...]:
        return compute_referenced_subroots(
            identity=self.identity,
            world_snapshot_cid=self.world_snapshot_cid,
            graph_history_head_cid=self.graph_history_head_cid,
            transition_log_head_cid=self.transition_log_head_cid,
            previous_manifest_cid=self.previous_manifest_cid,
            execution_trace_cids=self.execution_trace_cids,
            transition_receipt_cids=self.transition_receipt_cids,
        )

    def to_payload(self) -> dict[str, Any]:
        identity = self.identity.to_dict()
        _reject_excluded_identity_fields(identity, path="identity")
        if "generation" in identity:
            raise WorldRootAdmissionError(
                "semantic world-root identity must not contain generation"
            )
        return {
            "schema": self.SCHEMA,
            "interface": self.INTERFACE,
            "generation": self.generation,
            "identity": identity,
            "semantic_world_root_cid": self.semantic_world_root_cid,
            "world_snapshot_cid": self.world_snapshot_cid,
            "graph_history_head_cid": self.graph_history_head_cid,
            "transition_log_head_cid": self.transition_log_head_cid,
            "previous_manifest_cid": self.previous_manifest_cid,
            "execution_trace_cids": list(self.execution_trace_cids),
            "transition_receipt_cids": list(self.transition_receipt_cids),
            "referenced_subroot_cids": list(self.referenced_subroot_cids),
        }

    @property
    def world_root_manifest_cid(self) -> str:
        sealed = seal_history_record(
            HistoryRecordKind.WORLD_ROOT_MANIFEST, self.to_payload()
        )
        return cid_for_artifact(sealed)

    def to_dict(self) -> dict[str, Any]:
        value = self.to_payload()
        value["world_root_manifest_cid"] = self.world_root_manifest_cid
        return value

    @classmethod
    def from_payload(cls, data: Mapping[str, Any]) -> "SemanticWorldRootManifest":
        if not isinstance(data, Mapping):
            raise WorldRootIntegrityError("world-root manifest must be a mapping")
        expected = frozenset(
            {
                "schema",
                "interface",
                "generation",
                "identity",
                "semantic_world_root_cid",
                "world_snapshot_cid",
                "graph_history_head_cid",
                "transition_log_head_cid",
                "previous_manifest_cid",
                "execution_trace_cids",
                "transition_receipt_cids",
                "referenced_subroot_cids",
            }
        )
        actual = frozenset(data)
        extra_allowed = actual - expected
        if extra_allowed == {"world_root_manifest_cid"}:
            data = {key: value for key, value in data.items() if key != "world_root_manifest_cid"}
            actual = frozenset(data)
        if actual != expected:
            missing = sorted(expected - actual)
            unknown = sorted(actual - expected)
            problems: list[str] = []
            if missing:
                problems.append(f"missing {', '.join(missing)}")
            if unknown:
                problems.append(f"unknown {', '.join(unknown)}")
            raise WorldRootIntegrityError(
                "world-root manifest has " + "; ".join(problems)
            )
        if data["schema"] != cls.SCHEMA:
            raise WorldRootIntegrityError("unsupported world-root-manifest schema")
        if data["interface"] != cls.INTERFACE:
            raise WorldRootIntegrityError("unsupported world-root-manifest interface")
        identity_payload = data["identity"]
        if not isinstance(identity_payload, Mapping):
            raise WorldRootIntegrityError("world-root identity must be a mapping")
        _reject_excluded_identity_fields(identity_payload, path="identity")
        try:
            identity = SemanticWorldRootIdentity.from_dict(identity_payload)
        except ProgramIdentityError as exc:
            raise WorldRootIntegrityError(str(exc)) from exc
        if identity.semantic_world_root_cid != data["semantic_world_root_cid"]:
            raise WorldRootIntegrityError(
                "semantic_world_root_cid does not rehash identity payload"
            )
        manifest = cls(
            generation=data["generation"],
            identity=identity,
            world_snapshot_cid=data["world_snapshot_cid"],
            graph_history_head_cid=data["graph_history_head_cid"],
            transition_log_head_cid=data["transition_log_head_cid"],
            previous_manifest_cid=data["previous_manifest_cid"],
            execution_trace_cids=data["execution_trace_cids"],
            transition_receipt_cids=data["transition_receipt_cids"],
        )
        if tuple(data["referenced_subroot_cids"]) != manifest.referenced_subroot_cids:
            raise WorldRootIntegrityError(
                "root manifest referenced_subroot_cids are not the deterministic binding"
            )
        return manifest


def _require_every_subroot(blocks: HistoryBlockStore, cids: Sequence[str]) -> None:
    for cid in cids:
        try:
            blocks.require_stored(cid, field="referenced_subroot_cid")
        except GraphHistoryAdmissionError as exc:
            raise WorldRootAdmissionError(str(exc)) from exc


def _verify_graph_bindings(
    blocks: HistoryBlockStore,
    identity: SemanticWorldRootIdentity,
    *,
    graph_store: LogicalProgramGraphStore | None,
) -> ProgramGraphSnapshot:
    try:
        if graph_store is None:
            graph_store = LogicalProgramGraphStore(blocks)
        snapshot = graph_store.get_verified_snapshot(identity.program_graph_snapshot_cid)
    except GraphHistoryNotFound as exc:
        raise WorldRootAdmissionError(
            "store-before-reference: program_graph_snapshot_cid"
        ) from exc
    except GraphHistoryError as exc:
        raise WorldRootAdmissionError(str(exc)) from exc
    if snapshot.canonical_program_graph_cid != identity.canonical_program_graph_cid:
        raise WorldRootIntegrityError(
            "canonical_program_graph_cid does not match the stored snapshot"
        )
    if snapshot.environment_binding_set_cid != identity.environment_binding_set_cid:
        raise WorldRootIntegrityError(
            "environment_binding_set_cid does not match the stored snapshot"
        )
    try:
        canonical = graph_store.get_verified_record(
            identity.canonical_program_graph_cid,
            expected_kind=HistoryRecordKind.CANONICAL_PROGRAM_GRAPH,
        )
    except GraphHistoryError as exc:
        raise WorldRootAdmissionError(
            "store-before-reference: canonical_program_graph_cid"
        ) from exc
    if not isinstance(canonical, CanonicalProgramGraphIdentity):
        raise WorldRootIntegrityError("canonical program graph did not rehash")
    if canonical.canonical_program_graph_cid != identity.canonical_program_graph_cid:
        raise WorldRootIntegrityError(
            "canonical program graph CID does not rehash stored identity"
        )
    return snapshot


class SemanticWorldSnapshotStore:
    """Persist immutable world snapshots and generation-bearing root manifests."""

    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | HistoryBlockStore
        | LogicalProgramGraphStore
        | ProgramTransitionLog,
        *,
        graph_store: LogicalProgramGraphStore | None = None,
        transition_log: ProgramTransitionLog | None = None,
    ) -> None:
        self._blocks = history_block_store(store)
        self._graph = graph_store or LogicalProgramGraphStore(self._blocks)
        self._transitions = transition_log or ProgramTransitionLog(self._blocks)

    @property
    def blocks(self) -> HistoryBlockStore:
        return self._blocks

    @property
    def store(self) -> DurableCoordinationStore:
        return self._blocks.store

    @property
    def graph_store(self) -> LogicalProgramGraphStore:
        return self._graph

    @property
    def transition_log(self) -> ProgramTransitionLog:
        return self._transitions

    def close(self) -> None:
        self._blocks.close()

    def __enter__(self) -> "SemanticWorldSnapshotStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _require_optional_kind(
        self,
        cid: str | None,
        *,
        field: str,
        expected_kind: HistoryRecordKind,
    ) -> None:
        if cid is None:
            return
        try:
            self._blocks.require_stored(cid, field=field)
            self._blocks.get_verified_record(cid, expected_kind=expected_kind)
        except GraphHistoryAdmissionError as exc:
            raise WorldRootAdmissionError(str(exc)) from exc
        except GraphHistoryNotFound as exc:
            raise WorldRootAdmissionError(f"store-before-reference: {field}") from exc
        except GraphHistoryError as exc:
            raise WorldRootAdmissionError(str(exc)) from exc

    def put_world_snapshot(
        self,
        snapshot: SemanticWorldSnapshot,
        *,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> HistoryWriteResult:
        if not isinstance(snapshot, SemanticWorldSnapshot):
            raise WorldRootAdmissionError(
                "snapshot must be a SemanticWorldSnapshot"
            )
        _verify_graph_bindings(self._blocks, snapshot.identity, graph_store=self._graph)
        try:
            self._graph.put_record(snapshot.identity)
        except GraphHistoryError as exc:
            raise WorldRootAdmissionError(str(exc)) from exc
        _require_every_subroot(self._blocks, snapshot.referenced_subroot_cids)
        self._require_optional_kind(
            snapshot.graph_history_head_cid,
            field="graph_history_head_cid",
            expected_kind=HistoryRecordKind.GRAPH_HISTORY_ENTRY,
        )
        self._require_optional_kind(
            snapshot.transition_log_head_cid,
            field="transition_log_head_cid",
            expected_kind=HistoryRecordKind.TRANSITION_LOG_ENTRY,
        )
        for index, cid in enumerate(snapshot.execution_trace_cids):
            try:
                self._blocks.require_stored(cid, field=f"execution_trace_cids[{index}]")
            except GraphHistoryAdmissionError as exc:
                raise WorldRootAdmissionError(str(exc)) from exc
        for index, cid in enumerate(snapshot.transition_receipt_cids):
            try:
                self._blocks.require_stored(
                    cid, field=f"transition_receipt_cids[{index}]"
                )
                self._transitions.get_verified_receipt(cid)
            except GraphHistoryError as exc:
                raise WorldRootAdmissionError(str(exc)) from exc
        result = self._blocks.put_payload(
            HistoryRecordKind.WORLD_SNAPSHOT,
            snapshot.to_payload(),
            expected_cid=snapshot.world_snapshot_cid,
            operation_id=operation_id,
            replicate=replicate,
        )
        catalog = {
            result.cid: snapshot.to_payload(),
            snapshot.identity.program_graph_snapshot_cid: self._graph.get_verified_snapshot(
                snapshot.identity.program_graph_snapshot_cid
            ).identity_payload(),
        }
        assert_history_physical_dag_acyclic(catalog)
        return result

    def get_verified_snapshot(self, cid: str) -> SemanticWorldSnapshot:
        try:
            artifact = self._blocks.get_verified_record(
                cid, expected_kind=HistoryRecordKind.WORLD_SNAPSHOT
            )
        except GraphHistoryNotFound as exc:
            raise WorldRootNotFound(str(exc)) from exc
        except GraphHistoryError as exc:
            raise WorldRootIntegrityError(str(exc)) from exc
        snapshot = SemanticWorldSnapshot.from_payload(dict(artifact["payload"]))
        if snapshot.world_snapshot_cid != artifact["identity_cid"]:
            raise WorldRootIntegrityError(
                "world snapshot CID does not rehash canonical payload"
            )
        return snapshot

    def put_world_root_manifest(
        self,
        manifest: SemanticWorldRootManifest,
        *,
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> HistoryWriteResult:
        if not isinstance(manifest, SemanticWorldRootManifest):
            raise WorldRootAdmissionError(
                "manifest must be a SemanticWorldRootManifest"
            )
        _verify_graph_bindings(self._blocks, manifest.identity, graph_store=self._graph)
        try:
            self._graph.put_record(manifest.identity)
        except GraphHistoryError as exc:
            raise WorldRootAdmissionError(str(exc)) from exc
        if manifest.world_snapshot_cid is not None:
            snapshot = self.get_verified_snapshot(manifest.world_snapshot_cid)
            if snapshot.identity.semantic_world_root_cid != manifest.semantic_world_root_cid:
                raise WorldRootIntegrityError(
                    "world snapshot identity does not match the root manifest"
                )
        if manifest.previous_manifest_cid is not None:
            previous = self.get_verified_manifest(manifest.previous_manifest_cid)
            if manifest.generation != previous.generation + 1:
                raise WorldRootAdmissionError(
                    "generation-bearing manifest must be the sole successor of its predecessor"
                )
        _require_every_subroot(self._blocks, manifest.referenced_subroot_cids)
        self._require_optional_kind(
            manifest.graph_history_head_cid,
            field="graph_history_head_cid",
            expected_kind=HistoryRecordKind.GRAPH_HISTORY_ENTRY,
        )
        self._require_optional_kind(
            manifest.transition_log_head_cid,
            field="transition_log_head_cid",
            expected_kind=HistoryRecordKind.TRANSITION_LOG_ENTRY,
        )
        result = self._blocks.put_payload(
            HistoryRecordKind.WORLD_ROOT_MANIFEST,
            manifest.to_payload(),
            expected_cid=manifest.world_root_manifest_cid,
            operation_id=operation_id,
            replicate=replicate,
        )
        catalog = {result.cid: manifest.to_payload()}
        catalog[manifest.identity.program_graph_snapshot_cid] = (
            self._graph.get_verified_snapshot(
                manifest.identity.program_graph_snapshot_cid
            ).identity_payload()
        )
        assert_history_physical_dag_acyclic(catalog)
        return result

    def get_verified_manifest(self, cid: str) -> SemanticWorldRootManifest:
        try:
            artifact = self._blocks.get_verified_record(
                cid, expected_kind=HistoryRecordKind.WORLD_ROOT_MANIFEST
            )
        except GraphHistoryNotFound as exc:
            raise WorldRootNotFound(str(exc)) from exc
        except GraphHistoryError as exc:
            raise WorldRootIntegrityError(str(exc)) from exc
        manifest = SemanticWorldRootManifest.from_payload(dict(artifact["payload"]))
        if manifest.world_root_manifest_cid != artifact["identity_cid"]:
            raise WorldRootIntegrityError(
                "world-root manifest CID does not rehash canonical payload"
            )
        return manifest

    def build_world_root_manifest(
        self,
        *,
        generation: int | None = None,
        identity: SemanticWorldRootIdentity | Mapping[str, Any] | None = None,
        snapshot: SemanticWorldSnapshot | None = None,
        domain_state_cid: str | None = None,
        canonical_program_graph_cid: str | None = None,
        program_graph_snapshot_cid: str | None = None,
        semantic_object_index_cid: str | None = None,
        environment_binding_set_cid: str | None = None,
        policy_cid: str | None = None,
        analysis_limitation_index_cid: str | None = None,
        world_snapshot_cid: str | None = None,
        graph_history_head_cid: str | None = None,
        transition_log_head_cid: str | None = None,
        previous_manifest_cid: str | None = None,
        execution_trace_cids: Sequence[str] = (),
        transition_receipt_cids: Sequence[str] = (),
        operation_id: str | None = None,
        replicate: bool = False,
    ) -> SemanticWorldRootManifest:
        """Build, bind, and persist one generation-bearing root manifest."""

        if snapshot is not None and not isinstance(snapshot, SemanticWorldSnapshot):
            raise WorldRootAdmissionError(
                "snapshot must be a SemanticWorldSnapshot when supplied"
            )
        if snapshot is not None:
            snap_result = self.put_world_snapshot(snapshot)
            world_snapshot_cid = snap_result.cid
            identity = snapshot.identity
            if not graph_history_head_cid:
                graph_history_head_cid = snapshot.graph_history_head_cid
            if not transition_log_head_cid:
                transition_log_head_cid = snapshot.transition_log_head_cid
            if not execution_trace_cids:
                execution_trace_cids = snapshot.execution_trace_cids
            if not transition_receipt_cids:
                transition_receipt_cids = snapshot.transition_receipt_cids

        if identity is None:
            required = {
                "domain_state_cid": domain_state_cid,
                "canonical_program_graph_cid": canonical_program_graph_cid,
                "program_graph_snapshot_cid": program_graph_snapshot_cid,
                "semantic_object_index_cid": semantic_object_index_cid,
                "environment_binding_set_cid": environment_binding_set_cid,
                "policy_cid": policy_cid,
                "analysis_limitation_index_cid": analysis_limitation_index_cid,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise WorldRootAdmissionError(
                    f"world-root identity missing required fields {missing}"
                )
            try:
                identity = SemanticWorldRootIdentity(**required)  # type: ignore[arg-type]
            except ProgramIdentityError as exc:
                raise WorldRootAdmissionError(str(exc)) from exc
        elif isinstance(identity, Mapping):
            _reject_excluded_identity_fields(identity, path="identity")
            try:
                identity = SemanticWorldRootIdentity.from_dict(identity)
            except ProgramIdentityError as exc:
                raise WorldRootAdmissionError(str(exc)) from exc
        elif not isinstance(identity, SemanticWorldRootIdentity):
            raise WorldRootAdmissionError(
                "identity must be a SemanticWorldRootIdentity or mapping"
            )
        else:
            _reject_excluded_identity_fields(identity.to_dict(), path="identity")

        if previous_manifest_cid is not None:
            previous = self.get_verified_manifest(previous_manifest_cid)
            expected_generation = previous.generation + 1
            if generation is None:
                generation = expected_generation
            elif generation != expected_generation:
                raise WorldRootAdmissionError(
                    "generation-bearing manifest must be the sole successor of its predecessor"
                )
        elif generation is None:
            generation = 1

        manifest = SemanticWorldRootManifest(
            generation=generation,
            identity=identity,
            world_snapshot_cid=world_snapshot_cid,
            graph_history_head_cid=graph_history_head_cid,
            transition_log_head_cid=transition_log_head_cid,
            previous_manifest_cid=previous_manifest_cid,
            execution_trace_cids=execution_trace_cids,
            transition_receipt_cids=transition_receipt_cids,
        )
        self.put_world_root_manifest(
            manifest, operation_id=operation_id, replicate=replicate
        )
        return manifest


def build_world_root_manifest(
    store: SemanticWorldSnapshotStore
    | LogicalProgramGraphStore
    | ProgramTransitionLog
    | DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | HistoryBlockStore,
    **fields: Any,
) -> SemanticWorldRootManifest:
    """Build and persist a generation-bearing world-root manifest."""

    roots = (
        store
        if isinstance(store, SemanticWorldSnapshotStore)
        else SemanticWorldSnapshotStore(store)
    )
    return roots.build_world_root_manifest(**fields)


__all__ = [
    "PROGRAM_GRAPH_HISTORY_INTERFACE",
    "SEMANTIC_WORLD_ROOT_INTERFACE",
    "SEMANTIC_WORLD_ROOT_MANIFEST_INTERFACE",
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
    "compute_referenced_subroots",
]
