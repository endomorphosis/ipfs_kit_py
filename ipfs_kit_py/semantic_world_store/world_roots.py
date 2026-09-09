"""Generation-bearing immutable semantic world-root manifests.

``SemanticWorldRootManifest`` and ``build_world_root_manifest`` bind every
referenced immutable subroot into a deterministic, content-addressed kit
record.  Kit persists and verifies; it never accepts semantics, mutates a
current root pointer, or performs operational CAS (SAWM-014).

Authority rules (normative, fail-closed):

* Datasets ``SemanticWorldRootIdentity@1`` remains the semantic identity and
  excludes generation, projections, and operational CAS fields.
* The kit manifest is generation-bearing and append-only.  Generation 1 has
  no predecessor; each successor cites the previous manifest CID.
* ``subroot_cids`` is the sorted unique set of every referenced immutable
  identity.  Missing or corrupt subroots fail closed.
* Storage CIDs are minted only by ``coordination_storage.cid_for_artifact``.
  This module never encodes CIDv1 itself.
* Immutable puts are idempotent: same identity + same bytes is a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Final, Mapping, Sequence

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
    GRAPH_HISTORY_EVIDENCE,
    GraphHistoryAdmissionError,
    GraphHistoryError,
    GraphHistoryIntegrityError,
    GraphHistoryKind,
    GraphHistoryWriteResult,
    LogicalProgramGraphStore,
    ProgramTransitionLog,
    SemanticWorldSnapshot,
    SemanticWorldSnapshotStore,
    WorldHistoryBlockStore,
    world_history_blocks,
)
from ipfs_kit_py.semantic_world_store.verified_store import VerifiedSemanticBlockStore


SEMANTIC_WORLD_ROOT_INTERFACE: Final[str] = "SemanticWorldRoot@1"
WORLD_ROOT_MANIFEST_INTERFACE: Final[str] = "SemanticWorldRootManifest@1"
WORLD_ROOT_MANIFEST_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-root-manifest@1"
)
WORLD_ROOT_HISTORY_EVIDENCE: Final[str] = "sawm/world-root-history@1"
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


class WorldRootError(GraphHistoryError):
    """Base error for world-root manifest admission or retrieval."""


class WorldRootAdmissionError(WorldRootError, GraphHistoryAdmissionError):
    """Raised when a world-root manifest is rejected before durable write."""


class WorldRootIntegrityError(WorldRootError, GraphHistoryIntegrityError):
    """Raised when a stored world-root manifest fails claimed-CID rehash."""


def _cid(value: str, name: str) -> str:
    try:
        return validate_verified_cid(value, name)
    except SemanticGovernorStoreContractError as exc:
        raise WorldRootAdmissionError(str(exc)) from exc


def _optional_cid(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    return _cid(value, name)


def _unique_sorted_cids(values: Sequence[str] | None, name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes, bytearray, memoryview)):
        raise WorldRootAdmissionError(f"{name} must be a sequence of CIDs")
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        cid = _cid(item, name)
        if cid in seen:
            continue
        seen.add(cid)
        ordered.append(cid)
    return tuple(sorted(ordered))


def _ordered_unique_cids(values: Sequence[str] | None, name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes, bytearray, memoryview)):
        raise WorldRootAdmissionError(f"{name} must be a sequence of CIDs")
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        cid = _cid(item, name)
        if cid in seen:
            raise WorldRootAdmissionError(f"{name} identities must be unique")
        seen.add(cid)
        ordered.append(cid)
    return tuple(ordered)


def _generation(value: object) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise WorldRootAdmissionError("generation must be a positive integer")
    if value < 1 or value > MAX_SAFE_INTEGER:
        raise WorldRootAdmissionError(
            f"generation must be an integer in 1..{MAX_SAFE_INTEGER}"
        )
    return value


def _as_world_snapshot(
    value: SemanticWorldSnapshot | Mapping[str, Any] | None,
) -> SemanticWorldSnapshot | None:
    if value is None:
        return None
    if isinstance(value, SemanticWorldSnapshot):
        return value
    if isinstance(value, Mapping):
        return SemanticWorldSnapshot.from_dict(value)
    raise WorldRootAdmissionError(
        "world_snapshot must be a SemanticWorldSnapshot or mapping"
    )


def _as_identity(
    value: SemanticWorldRootIdentity | Mapping[str, Any] | None,
    *,
    domain_state_cid: str | None,
    canonical_program_graph_cid: str | None,
    program_graph_snapshot_cid: str | None,
    semantic_object_index_cid: str | None,
    environment_binding_set_cid: str | None,
    policy_cid: str | None,
    analysis_limitation_index_cid: str | None,
) -> SemanticWorldRootIdentity:
    if isinstance(value, SemanticWorldRootIdentity):
        identity = value
    elif isinstance(value, Mapping):
        try:
            identity = SemanticWorldRootIdentity.from_dict(value)
        except ProgramIdentityError as exc:
            raise WorldRootAdmissionError(str(exc)) from exc
    else:
        missing = [
            name
            for name, item in (
                ("domain_state_cid", domain_state_cid),
                ("canonical_program_graph_cid", canonical_program_graph_cid),
                ("program_graph_snapshot_cid", program_graph_snapshot_cid),
                ("semantic_object_index_cid", semantic_object_index_cid),
                ("environment_binding_set_cid", environment_binding_set_cid),
                ("policy_cid", policy_cid),
                ("analysis_limitation_index_cid", analysis_limitation_index_cid),
            )
            if item is None
        ]
        if missing:
            raise WorldRootAdmissionError(
                "build_world_root_manifest requires SemanticWorldRootIdentity "
                f"fields {missing}"
            )
        try:
            identity = SemanticWorldRootIdentity(
                domain_state_cid=domain_state_cid,
                canonical_program_graph_cid=canonical_program_graph_cid,
                program_graph_snapshot_cid=program_graph_snapshot_cid,
                semantic_object_index_cid=semantic_object_index_cid,
                environment_binding_set_cid=environment_binding_set_cid,
                policy_cid=policy_cid,
                analysis_limitation_index_cid=analysis_limitation_index_cid,
            )
        except ProgramIdentityError as exc:
            raise WorldRootAdmissionError(str(exc)) from exc
    bindings = {
        "domain_state_cid": domain_state_cid,
        "canonical_program_graph_cid": canonical_program_graph_cid,
        "program_graph_snapshot_cid": program_graph_snapshot_cid,
        "semantic_object_index_cid": semantic_object_index_cid,
        "environment_binding_set_cid": environment_binding_set_cid,
        "policy_cid": policy_cid,
        "analysis_limitation_index_cid": analysis_limitation_index_cid,
    }
    for name, supplied in bindings.items():
        if supplied is None:
            continue
        actual = getattr(identity, name)
        if actual != _cid(supplied, name):
            raise WorldRootAdmissionError(
                f"identity.{name} does not match supplied {name}"
            )
    return identity


def collect_world_root_subroots(
    identity: SemanticWorldRootIdentity,
    *,
    world_snapshot: SemanticWorldSnapshot | None = None,
    previous_manifest: "SemanticWorldRootManifest" | None = None,
    transition_receipt_cids: Sequence[str] = (),
    execution_trace_cids: Sequence[str] = (),
    extra_subroot_cids: Sequence[str] = (),
    world_snapshot_cid: str | None = None,
) -> tuple[str, ...]:
    """Return the sorted unique CID set bound by a generation-bearing root."""

    refs: list[str] = [getattr(identity, name) for name in _IDENTITY_SUBROOT_FIELDS]
    refs.append(identity.semantic_world_root_cid)
    if world_snapshot is not None:
        refs.append(world_snapshot.semantic_world_snapshot_cid)
        refs.extend(world_snapshot.bound_subroot_cids())
    if world_snapshot_cid is not None:
        refs.append(_cid(world_snapshot_cid, "world_snapshot_cid"))
    if previous_manifest is not None:
        refs.append(previous_manifest.world_root_manifest_cid)
        refs.extend(previous_manifest.subroot_cids)
    refs.extend(_ordered_unique_cids(transition_receipt_cids, "transition_receipt_cid"))
    refs.extend(_ordered_unique_cids(execution_trace_cids, "execution_trace_cid"))
    refs.extend(_unique_sorted_cids(extra_subroot_cids, "extra_subroot_cid"))
    return tuple(sorted(set(refs)))


@dataclass(frozen=True, slots=True)
class SemanticWorldRootManifest:
    """Generation-bearing kit manifest binding every immutable subroot CID."""

    generation: int
    semantic_world_root_cid: str
    domain_state_cid: str
    canonical_program_graph_cid: str
    program_graph_snapshot_cid: str
    semantic_object_index_cid: str
    environment_binding_set_cid: str
    policy_cid: str
    analysis_limitation_index_cid: str
    subroot_cids: Sequence[str]
    world_snapshot_cid: str | None = None
    previous_manifest_cid: str | None = None
    transition_receipt_cids: Sequence[str] = ()
    execution_trace_cids: Sequence[str] = ()

    SCHEMA: ClassVar[str] = WORLD_ROOT_MANIFEST_SCHEMA
    INTERFACE: ClassVar[str] = WORLD_ROOT_MANIFEST_INTERFACE
    CID_FIELD: ClassVar[str] = "world_root_manifest_cid"

    def __post_init__(self) -> None:
        object.__setattr__(self, "generation", _generation(self.generation))
        for name in (
            "semantic_world_root_cid",
            *_IDENTITY_SUBROOT_FIELDS,
        ):
            object.__setattr__(self, name, _cid(getattr(self, name), name))
        object.__setattr__(
            self,
            "world_snapshot_cid",
            _optional_cid(self.world_snapshot_cid, "world_snapshot_cid"),
        )
        object.__setattr__(
            self,
            "previous_manifest_cid",
            _optional_cid(self.previous_manifest_cid, "previous_manifest_cid"),
        )
        object.__setattr__(
            self,
            "subroot_cids",
            _unique_sorted_cids(self.subroot_cids, "subroot_cid"),
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
            "execution_trace_cids",
            _ordered_unique_cids(self.execution_trace_cids, "execution_trace_cid"),
        )
        if self.generation == 1 and self.previous_manifest_cid is not None:
            raise WorldRootAdmissionError(
                "generation 1 world-root manifests cannot cite a predecessor"
            )
        if self.generation > 1 and self.previous_manifest_cid is None:
            raise WorldRootAdmissionError(
                "successor world-root manifests must cite previous_manifest_cid"
            )
        required = {
            self.semantic_world_root_cid,
            self.domain_state_cid,
            self.canonical_program_graph_cid,
            self.program_graph_snapshot_cid,
            self.semantic_object_index_cid,
            self.environment_binding_set_cid,
            self.policy_cid,
            self.analysis_limitation_index_cid,
            *self.transition_receipt_cids,
            *self.execution_trace_cids,
        }
        if self.world_snapshot_cid is not None:
            required.add(self.world_snapshot_cid)
        if self.previous_manifest_cid is not None:
            required.add(self.previous_manifest_cid)
        missing = required - set(self.subroot_cids)
        if missing:
            raise WorldRootAdmissionError(
                "world-root manifest subroot_cids omit referenced identities "
                f"{sorted(missing)}"
            )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "generation": self.generation,
            "semantic_world_root_cid": self.semantic_world_root_cid,
            "domain_state_cid": self.domain_state_cid,
            "canonical_program_graph_cid": self.canonical_program_graph_cid,
            "program_graph_snapshot_cid": self.program_graph_snapshot_cid,
            "semantic_object_index_cid": self.semantic_object_index_cid,
            "environment_binding_set_cid": self.environment_binding_set_cid,
            "policy_cid": self.policy_cid,
            "analysis_limitation_index_cid": self.analysis_limitation_index_cid,
            "subroot_cids": list(self.subroot_cids),
            "world_snapshot_cid": self.world_snapshot_cid,
            "previous_manifest_cid": self.previous_manifest_cid,
            "transition_receipt_cids": list(self.transition_receipt_cids),
            "execution_trace_cids": list(self.execution_trace_cids),
        }

    @property
    def world_root_manifest_cid(self) -> str:
        return cid_for_artifact(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        value = self.identity_payload()
        value["world_root_manifest_cid"] = self.world_root_manifest_cid
        return value

    def to_semantic_identity(self) -> SemanticWorldRootIdentity:
        try:
            return SemanticWorldRootIdentity(
                domain_state_cid=self.domain_state_cid,
                canonical_program_graph_cid=self.canonical_program_graph_cid,
                program_graph_snapshot_cid=self.program_graph_snapshot_cid,
                semantic_object_index_cid=self.semantic_object_index_cid,
                environment_binding_set_cid=self.environment_binding_set_cid,
                policy_cid=self.policy_cid,
                analysis_limitation_index_cid=self.analysis_limitation_index_cid,
            )
        except ProgramIdentityError as exc:
            raise WorldRootIntegrityError(str(exc)) from exc

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SemanticWorldRootManifest":
        if not isinstance(data, Mapping):
            raise WorldRootAdmissionError("world-root manifest must be a mapping")
        allowed = {
            "schema",
            "generation",
            "semantic_world_root_cid",
            "domain_state_cid",
            "canonical_program_graph_cid",
            "program_graph_snapshot_cid",
            "semantic_object_index_cid",
            "environment_binding_set_cid",
            "policy_cid",
            "analysis_limitation_index_cid",
            "subroot_cids",
            "world_snapshot_cid",
            "previous_manifest_cid",
            "transition_receipt_cids",
            "execution_trace_cids",
            "world_root_manifest_cid",
        }
        unknown = set(data) - allowed
        if unknown:
            raise WorldRootAdmissionError(
                f"world-root manifest has unknown fields {sorted(unknown)}"
            )
        if data.get("schema") != cls.SCHEMA:
            raise WorldRootAdmissionError(
                "unsupported SemanticWorldRootManifest schema"
            )
        claimed = data.get("world_root_manifest_cid")
        manifest = cls(
            generation=data["generation"],
            semantic_world_root_cid=data["semantic_world_root_cid"],
            domain_state_cid=data["domain_state_cid"],
            canonical_program_graph_cid=data["canonical_program_graph_cid"],
            program_graph_snapshot_cid=data["program_graph_snapshot_cid"],
            semantic_object_index_cid=data["semantic_object_index_cid"],
            environment_binding_set_cid=data["environment_binding_set_cid"],
            policy_cid=data["policy_cid"],
            analysis_limitation_index_cid=data["analysis_limitation_index_cid"],
            subroot_cids=data.get("subroot_cids") or (),
            world_snapshot_cid=data.get("world_snapshot_cid"),
            previous_manifest_cid=data.get("previous_manifest_cid"),
            transition_receipt_cids=data.get("transition_receipt_cids") or (),
            execution_trace_cids=data.get("execution_trace_cids") or (),
        )
        if claimed is not None and claimed != manifest.world_root_manifest_cid:
            raise WorldRootIntegrityError(
                f"claimed world-root manifest CID does not rehash: "
                f"computed {manifest.world_root_manifest_cid}, claimed {claimed}"
            )
        identity = manifest.to_semantic_identity()
        if identity.semantic_world_root_cid != manifest.semantic_world_root_cid:
            raise WorldRootIntegrityError(
                "semantic_world_root_cid does not rehash identity bindings"
            )
        return manifest


def build_world_root_manifest(
    *,
    identity: SemanticWorldRootIdentity | Mapping[str, Any] | None = None,
    domain_state_cid: str | None = None,
    canonical_program_graph_cid: str | None = None,
    program_graph_snapshot_cid: str | None = None,
    semantic_object_index_cid: str | None = None,
    environment_binding_set_cid: str | None = None,
    policy_cid: str | None = None,
    analysis_limitation_index_cid: str | None = None,
    world_snapshot: SemanticWorldSnapshot | Mapping[str, Any] | None = None,
    world_snapshot_cid: str | None = None,
    previous_manifest: SemanticWorldRootManifest | Mapping[str, Any] | None = None,
    generation: int | None = None,
    transition_receipt_cids: Sequence[str] = (),
    execution_trace_cids: Sequence[str] = (),
    extra_subroot_cids: Sequence[str] = (),
    store: DurableCoordinationStore
    | SemanticWorldArtifactStore
    | VerifiedSemanticBlockStore
    | WorldHistoryBlockStore
    | LogicalProgramGraphStore
    | ProgramTransitionLog
    | SemanticWorldSnapshotStore
    | None = None,
) -> SemanticWorldRootManifest:
    """Build a generation-bearing manifest that binds every referenced subroot.

    When ``store`` is supplied, every bound CID must already exist as verified
    bytes.  This function never publishes a mutable current-root pointer.
    """

    resolved_identity = _as_identity(
        identity,
        domain_state_cid=domain_state_cid,
        canonical_program_graph_cid=canonical_program_graph_cid,
        program_graph_snapshot_cid=program_graph_snapshot_cid,
        semantic_object_index_cid=semantic_object_index_cid,
        environment_binding_set_cid=environment_binding_set_cid,
        policy_cid=policy_cid,
        analysis_limitation_index_cid=analysis_limitation_index_cid,
    )
    snapshot = _as_world_snapshot(world_snapshot)
    predecessor: SemanticWorldRootManifest | None
    if previous_manifest is None:
        predecessor = None
    elif isinstance(previous_manifest, SemanticWorldRootManifest):
        predecessor = previous_manifest
    elif isinstance(previous_manifest, Mapping):
        predecessor = SemanticWorldRootManifest.from_dict(previous_manifest)
    else:
        raise WorldRootAdmissionError(
            "previous_manifest must be a SemanticWorldRootManifest or mapping"
        )

    if snapshot is not None:
        if (
            snapshot.program_graph_snapshot_cid
            != resolved_identity.program_graph_snapshot_cid
        ):
            raise WorldRootAdmissionError(
                "world snapshot program_graph_snapshot_cid does not match identity"
            )
        if (
            snapshot.canonical_program_graph_cid
            != resolved_identity.canonical_program_graph_cid
        ):
            raise WorldRootAdmissionError(
                "world snapshot canonical_program_graph_cid does not match identity"
            )
        if world_snapshot_cid is None:
            world_snapshot_cid = snapshot.semantic_world_snapshot_cid
        elif world_snapshot_cid != snapshot.semantic_world_snapshot_cid:
            raise WorldRootAdmissionError(
                "world_snapshot_cid does not match the supplied snapshot"
            )
        if not transition_receipt_cids:
            transition_receipt_cids = snapshot.transition_receipt_cids
        if not execution_trace_cids:
            execution_trace_cids = snapshot.execution_trace_cids

    if predecessor is None:
        resolved_generation = 1 if generation is None else _generation(generation)
        if resolved_generation != 1:
            raise WorldRootAdmissionError(
                "a first world-root manifest must use generation 1"
            )
        previous_cid = None
    else:
        resolved_generation = predecessor.generation + 1
        if generation is not None and _generation(generation) != resolved_generation:
            raise WorldRootAdmissionError(
                "generation must be exactly previous_manifest.generation + 1"
            )
        previous_cid = predecessor.world_root_manifest_cid

    subroots = collect_world_root_subroots(
        resolved_identity,
        world_snapshot=snapshot,
        previous_manifest=predecessor,
        transition_receipt_cids=transition_receipt_cids,
        execution_trace_cids=execution_trace_cids,
        extra_subroot_cids=extra_subroot_cids,
        world_snapshot_cid=world_snapshot_cid,
    )
    manifest = SemanticWorldRootManifest(
        generation=resolved_generation,
        semantic_world_root_cid=resolved_identity.semantic_world_root_cid,
        domain_state_cid=resolved_identity.domain_state_cid,
        canonical_program_graph_cid=resolved_identity.canonical_program_graph_cid,
        program_graph_snapshot_cid=resolved_identity.program_graph_snapshot_cid,
        semantic_object_index_cid=resolved_identity.semantic_object_index_cid,
        environment_binding_set_cid=resolved_identity.environment_binding_set_cid,
        policy_cid=resolved_identity.policy_cid,
        analysis_limitation_index_cid=resolved_identity.analysis_limitation_index_cid,
        subroot_cids=subroots,
        world_snapshot_cid=world_snapshot_cid,
        previous_manifest_cid=previous_cid,
        transition_receipt_cids=transition_receipt_cids,
        execution_trace_cids=execution_trace_cids,
    )
    if store is not None:
        blocks = world_history_blocks(store)
        derived = {manifest.semantic_world_root_cid}
        for cid in manifest.subroot_cids:
            if cid in derived:
                continue
            blocks.require_stored(cid, path="world-root subroot")
        if snapshot is not None:
            loaded = blocks.get_decoded(
                snapshot.semantic_world_snapshot_cid,
                expected_kind=GraphHistoryKind.WORLD_SNAPSHOT,
            )
            if loaded.semantic_world_snapshot_cid != snapshot.semantic_world_snapshot_cid:
                raise WorldRootIntegrityError(
                    "stored world snapshot CID does not match the supplied snapshot"
                )
    return manifest


class SemanticWorldRootHistory:
    """Append-only history of generation-bearing world-root manifests."""

    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_INTERFACE

    def __init__(
        self,
        store: DurableCoordinationStore
        | SemanticWorldArtifactStore
        | VerifiedSemanticBlockStore
        | WorldHistoryBlockStore
        | LogicalProgramGraphStore
        | ProgramTransitionLog
        | SemanticWorldSnapshotStore,
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

    def __enter__(self) -> "SemanticWorldRootHistory":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def get_verified_manifest(self, cid: str) -> SemanticWorldRootManifest:
        return self._blocks.get_decoded(
            cid, expected_kind=GraphHistoryKind.WORLD_ROOT_MANIFEST
        )

    def append_manifest(
        self,
        manifest: SemanticWorldRootManifest | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(manifest, SemanticWorldRootManifest):
            manifest = SemanticWorldRootManifest.from_dict(manifest)
        self._blocks.put_record(
            GraphHistoryKind.SEMANTIC_WORLD_ROOT_IDENTITY,
            manifest.to_semantic_identity(),
            operation_id=None if operation_id is None else f"{operation_id}:identity",
        )
        for cid in manifest.subroot_cids:
            self._blocks.require_stored(cid, path="world-root subroot")
        return self._blocks.put_record(
            GraphHistoryKind.WORLD_ROOT_MANIFEST,
            manifest,
            operation_id=operation_id,
        )


__all__ = [
    "GRAPH_HISTORY_EVIDENCE",
    "SEMANTIC_WORLD_ROOT_INTERFACE",
    "WORLD_ROOT_HISTORY_EVIDENCE",
    "WORLD_ROOT_MANIFEST_INTERFACE",
    "WORLD_ROOT_MANIFEST_SCHEMA",
    "SemanticWorldRootHistory",
    "SemanticWorldRootManifest",
    "WorldRootAdmissionError",
    "WorldRootError",
    "WorldRootIntegrityError",
    "build_world_root_manifest",
    "collect_world_root_subroots",
]
