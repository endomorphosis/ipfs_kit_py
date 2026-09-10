"""Immutable generation-bearing semantic world-root manifests.

``SemanticWorldRoot@1`` binds every referenced immutable subroot into a
deterministic kit manifest.  Datasets ``SemanticWorldRootIdentity`` remains
the semantic identity and excludes generation, CAS pointers, projections,
and operational clocks.

Authority rules (normative, fail-closed):

* Kit persists and rehashes; it never accepts semantics.
* Every referenced CID must already be stored (store-before-reference).
* Unchanged subroots keep their prior CIDs across deltas.
* Manifest construction is deterministic: subroot bindings are sorted by
  name, then CID.
* This module does not compare-and-swap a mutable current pointer.
  Generation-bearing root CAS belongs exclusively to SAWM-014.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar, Final, Mapping, Sequence

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    ProgramIdentityError,
    SemanticWorldRootIdentity,
    SEMANTIC_IDENTITY_EXCLUDED_FIELDS,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.semantic_world_store.graph_history import (
    GraphHistoryAdmissionError,
    GraphHistoryIntegrityError,
    GraphHistoryKind,
    GraphHistoryWriteResult,
    LogicalProgramGraphStore,
    ProgramGraphHistory,
    ProgramTransitionLog,
    SemanticWorldHistoryBlockStore,
    SemanticWorldSnapshot,
    SemanticWorldSnapshotStore,
    as_history_store,
)
from ipfs_kit_py.semantic_world_store.verified_store import (
    VerifiedSemanticBlockStore,
)


SEMANTIC_WORLD_ROOT_INTERFACE: Final[str] = "SemanticWorldRoot@1"
SEMANTIC_WORLD_ROOT_MANIFEST_INTERFACE: Final[str] = "SemanticWorldRootManifest@1"
SEMANTIC_WORLD_ROOT_MANIFEST_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.world-root-manifest@1"
)

WORLD_ROOT_SUBROOT_NAMES: Final[tuple[str, ...]] = (
    "domain_state_cid",
    "canonical_program_graph_cid",
    "program_graph_snapshot_cid",
    "semantic_object_index_cid",
    "environment_binding_set_cid",
    "policy_cid",
    "analysis_limitation_index_cid",
)

_MANIFEST_OPTIONAL_SUBROOTS: Final[tuple[str, ...]] = (
    "world_snapshot_cid",
    "transition_log_head_cid",
    "previous_manifest_cid",
)


def _require_cid(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise GraphHistoryAdmissionError(f"{name} must be a CID")
    return value


def _optional_cid(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _require_cid(value, name)


def _require_generation(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 1:
        raise GraphHistoryAdmissionError(
            "world-root manifest generation must be a positive integer"
        )
    return value


def _sorted_unique_cids(values: Sequence[str], name: str) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        cid = _require_cid(item, name)
        if cid in seen:
            continue
        seen.add(cid)
        ordered.append(cid)
    return tuple(sorted(ordered))


def _sorted_bindings(
    bindings: Sequence[Mapping[str, Any]] | Sequence[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    normalized: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for item in bindings:
        if isinstance(item, Mapping):
            name = item.get("name")
            cid = item.get("cid")
        else:
            if len(item) != 2:
                raise GraphHistoryAdmissionError(
                    "subroot bindings must be (name, cid) pairs"
                )
            name, cid = item
        if type(name) is not str or not name:
            raise GraphHistoryAdmissionError("subroot binding name must be a string")
        cid = _require_cid(cid, name)
        if name in seen_names:
            raise GraphHistoryAdmissionError(
                f"duplicate subroot binding name {name!r}"
            )
        seen_names.add(name)
        normalized.append((name, cid))
    return tuple(sorted(normalized, key=lambda pair: (pair[0], pair[1])))


def _identity_from_bindings(
    *,
    domain_state_cid: str,
    canonical_program_graph_cid: str,
    program_graph_snapshot_cid: str,
    semantic_object_index_cid: str,
    environment_binding_set_cid: str,
    policy_cid: str,
    analysis_limitation_index_cid: str,
) -> SemanticWorldRootIdentity:
    try:
        return SemanticWorldRootIdentity(
            domain_state_cid=domain_state_cid,
            canonical_program_graph_cid=canonical_program_graph_cid,
            program_graph_snapshot_cid=program_graph_snapshot_cid,
            semantic_object_index_cid=semantic_object_index_cid,
            environment_binding_set_cid=environment_binding_set_cid,
            policy_cid=policy_cid,
            analysis_limitation_index_cid=analysis_limitation_index_cid,
        )
    except ProgramIdentityError as exc:
        raise GraphHistoryAdmissionError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class SemanticWorldRootManifest:
    """Generation-bearing immutable root; not a mutable current pointer.

    Semantic identity is ``SemanticWorldRootIdentity`` and excludes
    generation.  Kit ``world_root_manifest_cid`` includes generation and the
    complete deterministic subroot binding list so two generations that bind
    the same semantic identity remain distinct history records.
    """

    identity: SemanticWorldRootIdentity
    generation: int
    subroot_bindings: Sequence[tuple[str, str]]
    unchanged_subroot_cids: Sequence[str] = ()
    world_snapshot_cid: str | None = None
    transition_log_head_cid: str | None = None
    previous_manifest_cid: str | None = None

    SCHEMA: ClassVar[str] = SEMANTIC_WORLD_ROOT_MANIFEST_SCHEMA
    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_MANIFEST_INTERFACE
    CID_FIELD: ClassVar[str] = "world_root_manifest_cid"

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SemanticWorldRootIdentity):
            raise GraphHistoryAdmissionError(
                "SemanticWorldRootManifest.identity must be SemanticWorldRootIdentity"
            )
        object.__setattr__(self, "generation", _require_generation(self.generation))
        object.__setattr__(
            self, "subroot_bindings", _sorted_bindings(self.subroot_bindings)
        )
        object.__setattr__(
            self,
            "unchanged_subroot_cids",
            _sorted_unique_cids(self.unchanged_subroot_cids, "unchanged_subroot_cid"),
        )
        object.__setattr__(
            self,
            "world_snapshot_cid",
            _optional_cid(self.world_snapshot_cid, "world_snapshot_cid"),
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
        bound = {name: cid for name, cid in self.subroot_bindings}
        for name in WORLD_ROOT_SUBROOT_NAMES:
            expected = getattr(self.identity, name)
            if name not in bound:
                raise GraphHistoryAdmissionError(
                    f"root manifest missing required subroot binding {name}"
                )
            if bound[name] != expected:
                raise GraphHistoryAdmissionError(
                    f"root manifest {name} does not match semantic identity"
                )
        for name in _MANIFEST_OPTIONAL_SUBROOTS:
            value = getattr(self, name)
            if value is None:
                continue
            if name not in bound or bound[name] != value:
                raise GraphHistoryAdmissionError(
                    f"root manifest missing optional subroot binding {name}"
                )
        bound_cids = {cid for _name, cid in self.subroot_bindings}
        extra_unchanged = set(self.unchanged_subroot_cids) - bound_cids
        if extra_unchanged:
            raise GraphHistoryAdmissionError(
                "unchanged subroots must be CIDs bound by this manifest"
            )
        identity_payload = self.identity.to_dict()
        forbidden = SEMANTIC_IDENTITY_EXCLUDED_FIELDS.intersection(identity_payload)
        if forbidden:
            raise GraphHistoryAdmissionError(
                f"semantic world-root identity rejects excluded fields {sorted(forbidden)}"
            )

    @property
    def semantic_world_root_cid(self) -> str:
        return self.identity.semantic_world_root_cid

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "interface_id": self.INTERFACE,
            "generation": self.generation,
            "semantic_world_root_cid": self.semantic_world_root_cid,
            "domain_state_cid": self.identity.domain_state_cid,
            "canonical_program_graph_cid": self.identity.canonical_program_graph_cid,
            "program_graph_snapshot_cid": self.identity.program_graph_snapshot_cid,
            "semantic_object_index_cid": self.identity.semantic_object_index_cid,
            "environment_binding_set_cid": self.identity.environment_binding_set_cid,
            "policy_cid": self.identity.policy_cid,
            "analysis_limitation_index_cid": self.identity.analysis_limitation_index_cid,
            "world_snapshot_cid": self.world_snapshot_cid,
            "transition_log_head_cid": self.transition_log_head_cid,
            "previous_manifest_cid": self.previous_manifest_cid,
            "unchanged_subroot_cids": list(self.unchanged_subroot_cids),
            "subroot_bindings": [
                {"name": name, "cid": cid} for name, cid in self.subroot_bindings
            ],
        }

    @property
    def world_root_manifest_cid(self) -> str:
        return cid_for_artifact(self.identity_payload())

    def referenced_subroot_cids(self) -> tuple[str, ...]:
        return tuple(sorted({cid for _name, cid in self.subroot_bindings}))

    def binding_map(self) -> Mapping[str, str]:
        return MappingProxyType({name: cid for name, cid in self.subroot_bindings})

    def to_dict(self) -> dict[str, Any]:
        payload = self.identity_payload()
        payload["world_root_manifest_cid"] = self.world_root_manifest_cid
        payload["semantic_identity"] = self.identity.to_dict()
        return payload

    @classmethod
    def from_identity(
        cls,
        identity: SemanticWorldRootIdentity,
        *,
        generation: int,
        world_snapshot_cid: str | None = None,
        transition_log_head_cid: str | None = None,
        previous_manifest_cid: str | None = None,
        unchanged_subroot_cids: Sequence[str] = (),
        extra_bindings: Sequence[tuple[str, str]] = (),
    ) -> "SemanticWorldRootManifest":
        bindings: list[tuple[str, str]] = [
            (name, getattr(identity, name)) for name in WORLD_ROOT_SUBROOT_NAMES
        ]
        if world_snapshot_cid is not None:
            bindings.append(("world_snapshot_cid", world_snapshot_cid))
        if transition_log_head_cid is not None:
            bindings.append(("transition_log_head_cid", transition_log_head_cid))
        if previous_manifest_cid is not None:
            bindings.append(("previous_manifest_cid", previous_manifest_cid))
        bindings.extend(extra_bindings)
        return cls(
            identity=identity,
            generation=generation,
            subroot_bindings=bindings,
            unchanged_subroot_cids=unchanged_subroot_cids,
            world_snapshot_cid=world_snapshot_cid,
            transition_log_head_cid=transition_log_head_cid,
            previous_manifest_cid=previous_manifest_cid,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SemanticWorldRootManifest":
        if not isinstance(data, Mapping):
            raise GraphHistoryIntegrityError("world-root manifest must be a mapping")
        forbidden = SEMANTIC_IDENTITY_EXCLUDED_FIELDS.intersection(data)
        # Generation is kit operational metadata and is admitted on the
        # manifest, but it is excluded from datasets semantic identity.
        forbidden = forbidden - {"generation"}
        if forbidden:
            raise GraphHistoryAdmissionError(
                f"world-root manifest rejects excluded semantic fields {sorted(forbidden)}"
            )
        semantic = data.get("semantic_identity")
        if isinstance(semantic, Mapping):
            try:
                identity = SemanticWorldRootIdentity.from_dict(semantic)
            except ProgramIdentityError as exc:
                raise GraphHistoryIntegrityError(str(exc)) from exc
        else:
            identity = _identity_from_bindings(
                domain_state_cid=str(data["domain_state_cid"]),
                canonical_program_graph_cid=str(data["canonical_program_graph_cid"]),
                program_graph_snapshot_cid=str(data["program_graph_snapshot_cid"]),
                semantic_object_index_cid=str(data["semantic_object_index_cid"]),
                environment_binding_set_cid=str(data["environment_binding_set_cid"]),
                policy_cid=str(data["policy_cid"]),
                analysis_limitation_index_cid=str(data["analysis_limitation_index_cid"]),
            )
        claimed_semantic = data.get("semantic_world_root_cid")
        if (
            type(claimed_semantic) is str
            and claimed_semantic
            and claimed_semantic != identity.semantic_world_root_cid
        ):
            raise GraphHistoryIntegrityError(
                "semantic_world_root_cid does not rehash identity bytes"
            )
        raw_bindings = data.get("subroot_bindings") or ()
        bindings: list[tuple[str, str]] = []
        for item in raw_bindings:
            if isinstance(item, Mapping):
                bindings.append((str(item["name"]), str(item["cid"])))
            else:
                bindings.append((str(item[0]), str(item[1])))
        result = cls(
            identity=identity,
            generation=int(data["generation"]),
            subroot_bindings=bindings,
            unchanged_subroot_cids=tuple(data.get("unchanged_subroot_cids") or ()),
            world_snapshot_cid=data.get("world_snapshot_cid"),
            transition_log_head_cid=data.get("transition_log_head_cid"),
            previous_manifest_cid=data.get("previous_manifest_cid"),
        )
        claimed = data.get("world_root_manifest_cid")
        if type(claimed) is str and claimed and claimed != result.world_root_manifest_cid:
            raise GraphHistoryIntegrityError(
                "world_root_manifest_cid does not rehash canonical identity bytes"
            )
        return result


def _unchanged_subroots(
    previous: SemanticWorldRootManifest | None,
    bindings: Sequence[tuple[str, str]],
) -> tuple[str, ...]:
    if previous is None:
        return ()
    prior = previous.binding_map()
    unchanged: list[str] = []
    for name, cid in bindings:
        if prior.get(name) == cid:
            unchanged.append(cid)
    return tuple(sorted(set(unchanged)))


def _as_root_store(
    store: SemanticWorldHistoryBlockStore
    | DurableCoordinationStore
    | VerifiedSemanticBlockStore
    | LogicalProgramGraphStore
    | ProgramTransitionLog
    | ProgramGraphHistory
    | SemanticWorldSnapshotStore
    | "SemanticWorldRootStore",
) -> SemanticWorldHistoryBlockStore:
    blocks = getattr(store, "blocks", None)
    if isinstance(blocks, SemanticWorldHistoryBlockStore):
        return blocks
    return as_history_store(store)


class SemanticWorldRootStore:
    """Persist immutable world-root manifests.  No current-pointer CAS."""

    INTERFACE: ClassVar[str] = SEMANTIC_WORLD_ROOT_INTERFACE

    def __init__(
        self,
        store: SemanticWorldHistoryBlockStore
        | DurableCoordinationStore
        | VerifiedSemanticBlockStore
        | LogicalProgramGraphStore
        | ProgramGraphHistory,
    ) -> None:
        self._blocks = _as_root_store(store)
        self.world_snapshots = SemanticWorldSnapshotStore(self._blocks)

    @property
    def blocks(self) -> SemanticWorldHistoryBlockStore:
        return self._blocks

    @property
    def store(self) -> DurableCoordinationStore:
        return self._blocks.store

    def close(self) -> None:
        self._blocks.close()

    def __enter__(self) -> "SemanticWorldRootStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def put_manifest(
        self,
        manifest: SemanticWorldRootManifest | Mapping[str, Any],
        *,
        operation_id: str | None = None,
    ) -> GraphHistoryWriteResult:
        if not isinstance(manifest, SemanticWorldRootManifest):
            manifest = SemanticWorldRootManifest.from_dict(manifest)
        for name, cid in manifest.subroot_bindings:
            self._blocks.require_stored(cid, field=name)
        return self._blocks.put_payload(
            GraphHistoryKind.WORLD_ROOT_MANIFEST,
            manifest.to_dict(),
            expected_cid=manifest.world_root_manifest_cid,
            operation_id=operation_id,
        )

    def get_manifest(self, cid: str) -> SemanticWorldRootManifest:
        record = self._blocks.get_verified_record(
            cid, expected_kind=GraphHistoryKind.WORLD_ROOT_MANIFEST
        )
        if not isinstance(record, SemanticWorldRootManifest):
            raise GraphHistoryIntegrityError("stored world-root manifest did not decode")
        for name, bound_cid in record.subroot_bindings:
            self._blocks.require_stored(bound_cid, field=name)
        return record

    def build_manifest(
        self,
        *,
        generation: int,
        domain_state_cid: str,
        canonical_program_graph_cid: str,
        program_graph_snapshot_cid: str,
        semantic_object_index_cid: str,
        environment_binding_set_cid: str,
        policy_cid: str,
        analysis_limitation_index_cid: str,
        world_snapshot_cid: str | None = None,
        transition_log_head_cid: str | None = None,
        previous_manifest: SemanticWorldRootManifest | str | None = None,
        extra_bindings: Sequence[tuple[str, str]] = (),
        operation_id: str | None = None,
        persist: bool = True,
    ) -> SemanticWorldRootManifest:
        """Construct a deterministic manifest that binds every referenced subroot.

        Does not CAS-publish a current pointer.
        """

        identity = _identity_from_bindings(
            domain_state_cid=domain_state_cid,
            canonical_program_graph_cid=canonical_program_graph_cid,
            program_graph_snapshot_cid=program_graph_snapshot_cid,
            semantic_object_index_cid=semantic_object_index_cid,
            environment_binding_set_cid=environment_binding_set_cid,
            policy_cid=policy_cid,
            analysis_limitation_index_cid=analysis_limitation_index_cid,
        )
        previous: SemanticWorldRootManifest | None
        if isinstance(previous_manifest, str):
            previous = self.get_manifest(previous_manifest)
        else:
            previous = previous_manifest
        previous_cid = None if previous is None else previous.world_root_manifest_cid
        bindings: list[tuple[str, str]] = [
            (name, getattr(identity, name)) for name in WORLD_ROOT_SUBROOT_NAMES
        ]
        if world_snapshot_cid is not None:
            bindings.append(("world_snapshot_cid", world_snapshot_cid))
        if transition_log_head_cid is not None:
            bindings.append(("transition_log_head_cid", transition_log_head_cid))
        if previous_cid is not None:
            bindings.append(("previous_manifest_cid", previous_cid))
        bindings.extend(extra_bindings)
        sorted_bindings = _sorted_bindings(bindings)
        for name, cid in sorted_bindings:
            self._blocks.require_stored(cid, field=name)
        unchanged = _unchanged_subroots(previous, sorted_bindings)
        if previous is not None:
            prior = previous.binding_map()
            for name, cid in sorted_bindings:
                if name in prior and prior[name] == cid and cid not in unchanged:
                    raise GraphHistoryAdmissionError(
                        f"unchanged subroot {name} must retain CID {cid}"
                    )
        manifest = SemanticWorldRootManifest(
            identity=identity,
            generation=generation,
            subroot_bindings=sorted_bindings,
            unchanged_subroot_cids=unchanged,
            world_snapshot_cid=world_snapshot_cid,
            transition_log_head_cid=transition_log_head_cid,
            previous_manifest_cid=previous_cid,
        )
        first = SemanticWorldRootManifest.from_dict(manifest.to_dict())
        if first.world_root_manifest_cid != manifest.world_root_manifest_cid:
            raise GraphHistoryIntegrityError(
                "world-root manifest construction is not deterministic"
            )
        if persist:
            self.put_manifest(manifest, operation_id=operation_id)
        return manifest


def build_world_root_manifest(
    store: SemanticWorldRootStore
    | ProgramGraphHistory
    | SemanticWorldHistoryBlockStore
    | DurableCoordinationStore
    | VerifiedSemanticBlockStore,
    *,
    generation: int,
    domain_state_cid: str,
    canonical_program_graph_cid: str,
    program_graph_snapshot_cid: str,
    semantic_object_index_cid: str,
    environment_binding_set_cid: str,
    policy_cid: str,
    analysis_limitation_index_cid: str,
    world_snapshot_cid: str | None = None,
    transition_log_head_cid: str | None = None,
    previous_manifest: SemanticWorldRootManifest | str | None = None,
    extra_bindings: Sequence[tuple[str, str]] = (),
    operation_id: str | None = None,
    persist: bool = True,
) -> SemanticWorldRootManifest:
    """Public constructor for a generation-bearing immutable world-root manifest."""

    if isinstance(store, SemanticWorldRootStore):
        roots = store
    else:
        roots = SemanticWorldRootStore(_as_root_store(store))
    return roots.build_manifest(
        generation=generation,
        domain_state_cid=domain_state_cid,
        canonical_program_graph_cid=canonical_program_graph_cid,
        program_graph_snapshot_cid=program_graph_snapshot_cid,
        semantic_object_index_cid=semantic_object_index_cid,
        environment_binding_set_cid=environment_binding_set_cid,
        policy_cid=policy_cid,
        analysis_limitation_index_cid=analysis_limitation_index_cid,
        world_snapshot_cid=world_snapshot_cid,
        transition_log_head_cid=transition_log_head_cid,
        previous_manifest=previous_manifest,
        extra_bindings=extra_bindings,
        operation_id=operation_id,
        persist=persist,
    )


SemanticWorldRoot = SemanticWorldRootManifest


__all__ = [
    "SEMANTIC_WORLD_ROOT_INTERFACE",
    "SEMANTIC_WORLD_ROOT_MANIFEST_INTERFACE",
    "SEMANTIC_WORLD_ROOT_MANIFEST_SCHEMA",
    "WORLD_ROOT_SUBROOT_NAMES",
    "SemanticWorldRoot",
    "SemanticWorldRootManifest",
    "SemanticWorldRootStore",
    "SemanticWorldSnapshot",
    "build_world_root_manifest",
]
