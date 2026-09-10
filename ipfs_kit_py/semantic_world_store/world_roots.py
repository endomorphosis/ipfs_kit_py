"""Immutable generation-bearing semantic world-root manifests.

``SemanticWorldRootManifest`` and ``build_world_root_manifest`` implement
``SemanticWorldRoot@1``.  They bind datasets ``SemanticWorldRootIdentity``
together with every referenced immutable subroot.  They do not publish a
mutable current pointer, perform CAS, recover WAL, or accept semantics
(SAWM-014).

Authority rules (normative, fail-closed):

* Generation is kit-owned and excluded from datasets semantic identity.
* Every referenced subroot CID is stored before the parent manifest.
* Manifest CID order is deterministic: set-like CID collections are sorted.
* Unchanged subroots retain their prior CIDs across a delta.
* ``previous_manifest_cid`` is a physical back-edge; the IPLD catalog stays
  acyclic.
* Kit persists; datasets defines world identity.  Storage success is not
  semantic or operational admission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Final, Iterable, Mapping, Sequence

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    ProgramIdentityError,
    SemanticWorldRootIdentity,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    SemanticGovernorStoreContractError,
    validate_verified_cid,
)
from ipfs_kit_py.semantic_world_store.artifacts import SemanticWorldArtifactStore
from ipfs_kit_py.semantic_world_store.graph_history import (
    GraphHistoryAdmissionError,
    GraphHistoryBlockStore,
    GraphHistoryIntegrityError,
    GraphHistoryKind,
    GraphHistoryWriteResult,
    LogicalProgramGraphStore,
    SemanticWorldSnapshotStore,
)
from ipfs_kit_py.semantic_world_store.verified_store import VerifiedSemanticBlockStore


SEMANTIC_WORLD_ROOT_INTERFACE: Final[str] = "SemanticWorldRoot@1"
WORLD_ROOT_MANIFEST_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-root-manifest@1"
)
WORLD_ROOT_HISTORY_INTERFACE: Final[str] = "SemanticWorldRootHistory@1"
MAX_SAFE_INTEGER: Final[int] = (1 << 53) - 1

_IDENTITY_SUBROOT_FIELDS: Final[tuple[str, ...]] = (
    "domain_state_cid",
    "canonical_program_graph_cid",
    "program_graph_snapshot_cid",
    "semantic_object_index_cid",
    "environment_binding_set_cid",
    "policy_cid",
    "analysis_limitation_index_cid",
)


class WorldRootError(GraphHistoryAdmissionError):
    """Base error for immutable world-root manifest admission."""


class WorldRootIntegrityError(GraphHistoryIntegrityError):
    """Raised when a stored world-root manifest fails verification."""


def _require_cid(value: Any, name: str) -> str:
    try:
        return validate_verified_cid(value, name)
    except SemanticGovernorStoreContractError as exc:
        raise WorldRootError(str(exc)) from exc


def _optional_cid(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _require_cid(value, name)


def _unique_sorted_cids(values: Iterable[Any], name: str) -> tuple[str, ...]:
    items = [_require_cid(value, name) for value in values]
    ordered = tuple(sorted(items))
    if len(ordered) != len(set(ordered)):
        raise WorldRootError(f"{name} must not contain duplicates")
    return ordered


def _require_generation(value: Any, name: str = "generation") -> int:
    if type(value) is not int or isinstance(value, bool) or value < 1:
        raise WorldRootError(f"{name} must be a positive integer")
    if value > MAX_SAFE_INTEGER:
        raise WorldRootError(f"{name} exceeds the safe JSON integer range")
    return value


def _as_identity(
    value: SemanticWorldRootIdentity | Mapping[str, Any],
) -> SemanticWorldRootIdentity:
    if isinstance(value, SemanticWorldRootIdentity):
        return value
    if not isinstance(value, Mapping):
        raise WorldRootError(
            "identity must be a SemanticWorldRootIdentity or mapping"
        )
    try:
        return SemanticWorldRootIdentity.from_dict(value)
    except ProgramIdentityError as exc:
        raise WorldRootError(str(exc)) from exc


def _sorted_unique(cids: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(cids)))


def collect_world_root_subroots(
    identity: SemanticWorldRootIdentity,
    *,
    world_snapshot_cid: str | None = None,
    graph_history_entry_cid: str | None = None,
    transition_log_entry_cid: str | None = None,
    transition_receipt_cids: Sequence[str] = (),
    execution_trace_cids: Sequence[str] = (),
) -> tuple[str, ...]:
    """Return the deterministically ordered set of bound immutable subroots."""

    refs: list[str] = [
        getattr(identity, field) for field in _IDENTITY_SUBROOT_FIELDS
    ]
    for optional in (
        world_snapshot_cid,
        graph_history_entry_cid,
        transition_log_entry_cid,
    ):
        if optional is not None:
            refs.append(optional)
    refs.extend(transition_receipt_cids)
    refs.extend(execution_trace_cids)
    return _sorted_unique(refs)


@dataclass(frozen=True, slots=True)
class SemanticWorldRootManifest:
    """Generation-bearing immutable world-root manifest.

    Datasets ``semantic_world_root_cid`` excludes generation.  The kit
    ``world_root_manifest_cid`` includes generation, previous-manifest
    identity, and the complete sorted subroot catalog.
    """

    generation: int
    identity: SemanticWorldRootIdentity
    previous_manifest_cid: str | None = None
    world_snapshot_cid: str | None = None
    graph_history_entry_cid: str | None = None
    transition_log_entry_cid: str | None = None
    transition_receipt_cids: Sequence[str] = ()
    execution_trace_cids: Sequence[str] = ()
    subroot_cids: Sequence[str] = ()
    retained_subroot_cids: Sequence[str] = ()

    SCHEMA: ClassVar[str] = WORLD_ROOT_MANIFEST_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_INTERFACE
    CID_FIELD: ClassVar[str] = "world_root_manifest_cid"
    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema",
            "generation",
            "identity",
            "previous_manifest_cid",
            "world_snapshot_cid",
            "graph_history_entry_cid",
            "transition_log_entry_cid",
            "transition_receipt_cids",
            "execution_trace_cids",
            "subroot_cids",
            "retained_subroot_cids",
            "world_root_manifest_cid",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generation", _require_generation(self.generation))
        identity = _as_identity(self.identity)
        object.__setattr__(self, "identity", identity)
        object.__setattr__(
            self,
            "previous_manifest_cid",
            _optional_cid(self.previous_manifest_cid, "previous_manifest_cid"),
        )
        object.__setattr__(
            self,
            "world_snapshot_cid",
            _optional_cid(self.world_snapshot_cid, "world_snapshot_cid"),
        )
        object.__setattr__(
            self,
            "graph_history_entry_cid",
            _optional_cid(self.graph_history_entry_cid, "graph_history_entry_cid"),
        )
        object.__setattr__(
            self,
            "transition_log_entry_cid",
            _optional_cid(self.transition_log_entry_cid, "transition_log_entry_cid"),
        )
        object.__setattr__(
            self,
            "transition_receipt_cids",
            _unique_sorted_cids(self.transition_receipt_cids, "transition_receipt_cid"),
        )
        object.__setattr__(
            self,
            "execution_trace_cids",
            _unique_sorted_cids(self.execution_trace_cids, "execution_trace_cid"),
        )
        expected = collect_world_root_subroots(
            identity,
            world_snapshot_cid=self.world_snapshot_cid,
            graph_history_entry_cid=self.graph_history_entry_cid,
            transition_log_entry_cid=self.transition_log_entry_cid,
            transition_receipt_cids=self.transition_receipt_cids,
            execution_trace_cids=self.execution_trace_cids,
        )
        supplied = _unique_sorted_cids(self.subroot_cids, "subroot_cid")
        if supplied and supplied != expected:
            raise WorldRootError(
                "subroot_cids must be the deterministic catalog of every referenced immutable subroot"
            )
        object.__setattr__(self, "subroot_cids", expected)
        retained = _unique_sorted_cids(
            self.retained_subroot_cids, "retained_subroot_cid"
        )
        extra = set(retained) - set(expected)
        if extra:
            raise WorldRootError("retained subroots must be bound in this manifest")
        object.__setattr__(self, "retained_subroot_cids", retained)
        if self.generation == 1 and self.previous_manifest_cid is not None:
            raise WorldRootError("generation-1 manifests cannot cite a previous manifest")
        if self.generation > 1 and self.previous_manifest_cid is None:
            raise WorldRootError("non-initial manifests require previous_manifest_cid")

    @property
    def semantic_world_root_cid(self) -> str:
        return self.identity.semantic_world_root_cid

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "generation": self.generation,
            "identity": self.identity.to_dict(),
            "previous_manifest_cid": self.previous_manifest_cid,
            "world_snapshot_cid": self.world_snapshot_cid,
            "graph_history_entry_cid": self.graph_history_entry_cid,
            "transition_log_entry_cid": self.transition_log_entry_cid,
            "transition_receipt_cids": list(self.transition_receipt_cids),
            "execution_trace_cids": list(self.execution_trace_cids),
            "subroot_cids": list(self.subroot_cids),
            "retained_subroot_cids": list(self.retained_subroot_cids),
        }

    @property
    def world_root_manifest_cid(self) -> str:
        return cid_for_artifact(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        value = self.identity_payload()
        value["world_root_manifest_cid"] = self.world_root_manifest_cid
        return value

    def referenced_cids(self) -> tuple[str, ...]:
        refs = list(self.subroot_cids)
        if self.previous_manifest_cid is not None:
            refs.append(self.previous_manifest_cid)
        return _sorted_unique(refs)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SemanticWorldRootManifest":
        if not isinstance(data, Mapping):
            raise WorldRootIntegrityError("SemanticWorldRootManifest must be a mapping")
        actual = frozenset(data)
        if actual != cls._FIELDS:
            missing = sorted(cls._FIELDS - actual)
            unknown = sorted(actual - cls._FIELDS)
            problems: list[str] = []
            if missing:
                problems.append(f"missing {', '.join(missing)}")
            if unknown:
                problems.append(f"unknown {', '.join(unknown)}")
            raise WorldRootIntegrityError(
                "SemanticWorldRootManifest has " + "; ".join(problems)
            )
        payload = dict(data)
        claimed = payload.pop("world_root_manifest_cid")
        if payload.pop("schema") != cls.SCHEMA:
            raise WorldRootIntegrityError(
                "unsupported SemanticWorldRootManifest schema version"
            )
        try:
            claimed = validate_verified_cid(claimed, "world_root_manifest_cid")
        except SemanticGovernorStoreContractError as exc:
            raise WorldRootIntegrityError(str(exc)) from exc
        result = cls(
            generation=payload["generation"],
            identity=payload["identity"],
            previous_manifest_cid=payload["previous_manifest_cid"],
            world_snapshot_cid=payload["world_snapshot_cid"],
            graph_history_entry_cid=payload["graph_history_entry_cid"],
            transition_log_entry_cid=payload["transition_log_entry_cid"],
            transition_receipt_cids=payload["transition_receipt_cids"],
            execution_trace_cids=payload["execution_trace_cids"],
            subroot_cids=payload["subroot_cids"],
            retained_subroot_cids=payload["retained_subroot_cids"],
        )
        if result.world_root_manifest_cid != claimed:
            raise WorldRootIntegrityError(
                "world-root manifest CID does not rehash canonical identity bytes"
            )
        return result


def _blocks_from(
    store: GraphHistoryBlockStore
    | LogicalProgramGraphStore
    | SemanticWorldSnapshotStore
    | DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore,
) -> GraphHistoryBlockStore:
    if isinstance(store, GraphHistoryBlockStore):
        return store
    if isinstance(store, (LogicalProgramGraphStore, SemanticWorldSnapshotStore)):
        return store.blocks
    return GraphHistoryBlockStore(store)


def _assert_manifest_chain_acyclic(
    blocks: GraphHistoryBlockStore,
    previous_manifest_cid: str,
    new_identity: str,
) -> None:
    seen: set[str] = set()
    current: str | None = previous_manifest_cid
    while current is not None:
        if current == new_identity or current in seen:
            raise WorldRootError("physical IPLD block graph must be acyclic")
        seen.add(current)
        artifact = blocks.get_verified_record(
            current, expected_kind=GraphHistoryKind.WORLD_ROOT_MANIFEST
        )
        prior = SemanticWorldRootManifest.from_dict(dict(artifact["payload"]))
        current = prior.previous_manifest_cid


def build_world_root_manifest(
    store: GraphHistoryBlockStore
    | LogicalProgramGraphStore
    | SemanticWorldSnapshotStore
    | DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | None,
    *,
    identity: SemanticWorldRootIdentity | Mapping[str, Any],
    generation: int | None = None,
    previous_manifest: SemanticWorldRootManifest | Mapping[str, Any] | None = None,
    previous_manifest_cid: str | None = None,
    world_snapshot_cid: str | None = None,
    graph_history_entry_cid: str | None = None,
    transition_log_entry_cid: str | None = None,
    transition_receipt_cids: Sequence[str] = (),
    execution_trace_cids: Sequence[str] = (),
    operation_id: str | None = None,
    persist: bool = True,
) -> SemanticWorldRootManifest:
    """Build (and optionally persist) one deterministic world-root manifest.

    Every referenced immutable subroot must already be stored when
    ``persist`` is true.  This function never compare-and-swaps a current
    root pointer.
    """

    bound_identity = _as_identity(identity)
    prior: SemanticWorldRootManifest | None = None
    if previous_manifest is not None:
        prior = (
            previous_manifest
            if isinstance(previous_manifest, SemanticWorldRootManifest)
            else SemanticWorldRootManifest.from_dict(previous_manifest)
        )
        if previous_manifest_cid is None:
            previous_manifest_cid = prior.world_root_manifest_cid
        elif previous_manifest_cid != prior.world_root_manifest_cid:
            raise WorldRootError(
                "previous_manifest_cid does not match the supplied previous manifest"
            )
    if generation is None:
        generation = 1 if prior is None else prior.generation + 1
    generation = _require_generation(generation)
    if prior is not None and generation != prior.generation + 1:
        raise WorldRootError("manifest generation must be exactly one greater than previous")
    if prior is None and generation != 1:
        raise WorldRootError("initial manifests must be generation 1")

    subroots = collect_world_root_subroots(
        bound_identity,
        world_snapshot_cid=world_snapshot_cid,
        graph_history_entry_cid=graph_history_entry_cid,
        transition_log_entry_cid=transition_log_entry_cid,
        transition_receipt_cids=transition_receipt_cids,
        execution_trace_cids=execution_trace_cids,
    )
    retained: tuple[str, ...] = ()
    if prior is not None:
        retained = tuple(sorted(set(prior.subroot_cids) & set(subroots)))

    manifest = SemanticWorldRootManifest(
        generation=generation,
        identity=bound_identity,
        previous_manifest_cid=previous_manifest_cid,
        world_snapshot_cid=world_snapshot_cid,
        graph_history_entry_cid=graph_history_entry_cid,
        transition_log_entry_cid=transition_log_entry_cid,
        transition_receipt_cids=transition_receipt_cids,
        execution_trace_cids=execution_trace_cids,
        subroot_cids=subroots,
        retained_subroot_cids=retained,
    )
    if persist:
        if store is None:
            raise WorldRootError("persisting a world-root manifest requires a store")
        persist_world_root_manifest(store, manifest, operation_id=operation_id)
    return manifest


def persist_world_root_manifest(
    store: GraphHistoryBlockStore
    | LogicalProgramGraphStore
    | SemanticWorldSnapshotStore
    | DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore,
    manifest: SemanticWorldRootManifest,
    *,
    operation_id: str | None = None,
) -> GraphHistoryWriteResult:
    """Store one sealed world-root manifest after every referenced subroot."""

    blocks = _blocks_from(store)
    for cid in manifest.subroot_cids:
        blocks.require_stored(cid, name="subroot_cid")
    if manifest.previous_manifest_cid is not None:
        blocks.require_stored(manifest.previous_manifest_cid, name="previous_manifest_cid")
        _assert_manifest_chain_acyclic(
            blocks,
            manifest.previous_manifest_cid,
            manifest.world_root_manifest_cid,
        )
    if manifest.world_snapshot_cid is not None:
        blocks.get_verified_record(
            manifest.world_snapshot_cid,
            expected_kind=GraphHistoryKind.WORLD_SNAPSHOT,
        )
    if manifest.graph_history_entry_cid is not None:
        blocks.get_verified_record(
            manifest.graph_history_entry_cid,
            expected_kind=GraphHistoryKind.GRAPH_HISTORY_ENTRY,
        )
    if manifest.transition_log_entry_cid is not None:
        blocks.get_verified_record(
            manifest.transition_log_entry_cid,
            expected_kind=GraphHistoryKind.TRANSITION_LOG_ENTRY,
        )
    for receipt_cid in manifest.transition_receipt_cids:
        blocks.get_verified_record(
            receipt_cid,
            expected_kind=GraphHistoryKind.PROGRAM_TRANSITION_RECEIPT,
        )
    blocks.get_verified_record(
        manifest.identity.program_graph_snapshot_cid,
        expected_kind=GraphHistoryKind.PROGRAM_GRAPH_SNAPSHOT,
    )
    blocks.get_verified_record(
        manifest.identity.canonical_program_graph_cid,
        expected_kind=GraphHistoryKind.CANONICAL_PROGRAM_GRAPH,
    )
    return blocks.put_record(
        GraphHistoryKind.WORLD_ROOT_MANIFEST,
        manifest.to_dict(),
        expected_cid=manifest.world_root_manifest_cid,
        operation_id=operation_id,
    )


def get_verified_world_root_manifest(
    store: GraphHistoryBlockStore
    | LogicalProgramGraphStore
    | SemanticWorldSnapshotStore
    | DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore,
    cid: str,
) -> SemanticWorldRootManifest:
    """Load a world-root manifest and re-verify identity, subroots, and CID."""

    blocks = _blocks_from(store)
    artifact = blocks.get_verified_record(
        cid, expected_kind=GraphHistoryKind.WORLD_ROOT_MANIFEST
    )
    manifest = SemanticWorldRootManifest.from_dict(dict(artifact["payload"]))
    if manifest.world_root_manifest_cid != artifact["identity_cid"]:
        raise WorldRootIntegrityError(
            "world-root manifest CID does not rehash canonical identity bytes"
        )
    for subroot in manifest.subroot_cids:
        if not blocks.has_identity(subroot):
            raise WorldRootIntegrityError(
                f"stored world-root manifest references missing subroot {subroot}"
            )
    return manifest


__all__ = [
    "SEMANTIC_WORLD_ROOT_INTERFACE",
    "WORLD_ROOT_HISTORY_INTERFACE",
    "WORLD_ROOT_MANIFEST_SCHEMA",
    "SemanticWorldRootManifest",
    "WorldRootError",
    "WorldRootIntegrityError",
    "build_world_root_manifest",
    "collect_world_root_subroots",
    "get_verified_world_root_manifest",
    "persist_world_root_manifest",
]
