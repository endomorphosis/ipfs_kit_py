"""Deterministic proof-forest persistence and affected-branch updates (IPS-022).

Kit storage authority for immutable Merkle forest nodes and path indexes.
Semantic commitments are delegated entirely to the datasets forest codec
(IPS-011): this module never invents ordering or hash semantics.

Fail-closed guarantees:

* repository roots match datasets codec/vectors for identical inputs;
* identical replay is deterministic (same leaves/context -> same root);
* incremental updates recompute only affected category branches;
* equality witnesses prove every unaffected leaf survived;
* lost unaffected leaves, reordered/duplicate leaves, and old-root reuse
  with a changed manifest or aggregate fail closed;
* nodes and category/repository roots are stored as immutable
  ``merkle_node`` artifacts under an explicit root (no daemon path).

Interfaces: ``ProofForestStore``, ``persist_forest``,
``update_forest_branches``, ``verify_unaffected_leaves``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

from ipfs_datasets_py.logic.zkp.incremental_sealing.forest_codec import (
    ABSENCE_TOKEN,
    CANONICALIZATION_VERSION,
    CATEGORY_ROOT_SCHEMA,
    DOMAIN_BINARY,
    DOMAIN_CATEGORY,
    DOMAIN_EMPTY,
    DOMAIN_LEAF,
    DOMAIN_REPOSITORY,
    DOMAIN_UNARY,
    FOREST_CATEGORIES,
    FOREST_CODEC_SUBSET,
    FOREST_NAMESPACE,
    GENESIS_PARENT_SEAL,
    PROOF_FOREST_LEAF_SCHEMA,
    PROOF_SCHEMA_VERSION,
    REPOSITORY_PROOF_ROOT_SCHEMA,
    SCHEMA_MAJOR,
    CategoryRoot,
    ForestCodecError,
    ProofForestLeaf,
    RepositoryProofRoot,
    compute_category_root,
    compute_repository_root,
    encode_binary_node,
    encode_empty_node,
    encode_leaf_node,
    encode_unary_node,
    parse_forest_category,
)

from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ArtifactReference,
    ExplicitRootRequiredError,
    ProofSealStoreContractError,
    StoreRoot,
    validate_explicit_root_path,
)
from ipfs_kit_py.proof_seal_store.local_store import (
    HermeticProofSealStore,
    LocalStoreError,
)

EVIDENCE_SUBSET: Final[str] = "ips/proof-forest-store@1"
FOREST_STORE_SCHEMA: Final[str] = "ipfs_kit_py/proof_seal_store/forest@1"
FOREST_STORE_INTERFACE: Final[str] = "ProofForestStore@1"
FOREST_RECORD_SCHEMA: Final[str] = "ipfs_kit_py/proof_seal_store/forest-record@1"
CONTRACT_VERSION: Final[int] = 1

_FOREST_DIR: Final[str] = "forest"
_RECORDS_DIR: Final[str] = "records"
_RECORD_SUFFIX: Final[str] = ".json"
_MAX_RECORD_BYTES: Final[int] = 4 * 1024 * 1024
_SAFE_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._+\-]+$")

_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class ForestDisposition(str, Enum):
    """Closed outcomes for forest put/update/load operations."""

    STORED = "stored"
    ALREADY_EXISTS = "already_exists"
    UPDATED = "updated"
    VERIFIED = "verified"
    REJECTED = "rejected"
    ERROR = "error"
    HIT = "hit"
    MISS = "miss"


class ForestReason(str, Enum):
    """Closed diagnostic reasons for forest outcomes."""

    OK = "ok"
    ALREADY_EXISTS = "already_exists"
    NOT_FOUND = "not_found"
    MALFORMED = "malformed"
    DUPLICATE_LEAF = "duplicate_leaf"
    REORDERED_LEAVES = "reordered_leaves"
    LOST_UNAFFECTED_LEAF = "lost_unaffected_leaf"
    AFFECTED_MISMATCH = "affected_mismatch"
    OLD_AGGREGATE = "old_aggregate"
    MANIFEST_AGGREGATE_MISMATCH = "manifest_aggregate_mismatch"
    ROOT_MISMATCH = "root_mismatch"
    BRANCH_MISMATCH = "branch_mismatch"
    CODEC_REJECTED = "codec_rejected"
    CORRUPTED = "corrupted"
    OVER_BUDGET = "over_budget"
    IO_ERROR = "io_error"
    FSYNC_FAILED = "fsync_failed"
    SHORT_WRITE = "short_write"
    INTEGRITY_FAILED = "integrity_failed"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ForestStoreError(ProofSealStoreContractError):
    """A proof-forest store operation failed closed."""

    def __init__(
        self,
        message: str,
        *,
        reason: ForestReason = ForestReason.IO_ERROR,
        disposition: ForestDisposition | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.disposition = disposition


class ForestStoreIntegrityError(ForestStoreError):
    """Forest root, branch, or leaf integrity verification failed."""


class ForestStoreNotFoundError(ForestStoreError):
    """Requested forest record is absent."""


# ---------------------------------------------------------------------------
# Result records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnaffectedLeafVerification:
    """Equality-witness result for unaffected forest leaves."""

    disposition: ForestDisposition
    reason: ForestReason
    unaffected_categories: tuple[str, ...] = ()
    verified_leaf_count: int = 0
    lost_leaves: tuple[str, ...] = ()
    changed_leaves: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.disposition is ForestDisposition.VERIFIED

    @property
    def verified(self) -> bool:
        return bool(self)


@dataclass(frozen=True)
class ForestSnapshot:
    """Persisted forest state keyed by the datasets repository root CID."""

    root_cid: str
    repository_id: str
    revision: str
    source_root_cid: str
    manifest_root_cid: str
    environment_cid: str
    policy_cid: str
    proof_schema_version: str
    canonicalization_version: str
    dependency_graph_schema_version: str
    parent_seal_cid: str
    parent_revision_ids: tuple[str, ...]
    category_roots: Mapping[str, str]
    category_merkle_roots: Mapping[str, str]
    leaves: Mapping[str, tuple[ProofForestLeaf, ...]]
    node_cids: tuple[str, ...]
    branch_paths: Mapping[str, tuple[str, ...]]
    artifact_refs: Mapping[str, str]
    parent_forest_root_cid: str = ""
    touched_categories: tuple[str, ...] = ()

    def category_leaves_map(self) -> dict[str, tuple[ProofForestLeaf, ...]]:
        return {cat: self.leaves.get(cat, ()) for cat in FOREST_CATEGORIES}

    def to_repository_proof_root(self) -> RepositoryProofRoot:
        return RepositoryProofRoot(
            repository_id=self.repository_id,
            revision=self.revision,
            source_root_cid=self.source_root_cid,
            manifest_root_cid=self.manifest_root_cid,
            environment_cid=self.environment_cid,
            policy_cid=self.policy_cid,
            proof_schema_version=self.proof_schema_version,
            canonicalization_version=self.canonicalization_version,
            dependency_graph_schema_version=self.dependency_graph_schema_version,
            parent_seal_cid=self.parent_seal_cid,
            parent_revision_ids=self.parent_revision_ids,
            category_roots=dict(self.category_roots),
            root_cid=self.root_cid,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": FOREST_RECORD_SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "evidence_subset": EVIDENCE_SUBSET,
            "forest_codec_subset": FOREST_CODEC_SUBSET,
            "root_cid": self.root_cid,
            "repository_id": self.repository_id,
            "revision": self.revision,
            "source_root_cid": self.source_root_cid,
            "manifest_root_cid": self.manifest_root_cid,
            "environment_cid": self.environment_cid,
            "policy_cid": self.policy_cid,
            "proof_schema_version": self.proof_schema_version,
            "canonicalization_version": self.canonicalization_version,
            "dependency_graph_schema_version": self.dependency_graph_schema_version,
            "parent_seal_cid": self.parent_seal_cid,
            "parent_revision_ids": list(self.parent_revision_ids),
            "category_roots": {
                cat: self.category_roots[cat] for cat in FOREST_CATEGORIES
            },
            "category_merkle_roots": {
                cat: self.category_merkle_roots[cat] for cat in FOREST_CATEGORIES
            },
            "leaves": {
                cat: [leaf.to_canonical() for leaf in self.leaves.get(cat, ())]
                for cat in FOREST_CATEGORIES
            },
            "node_cids": list(self.node_cids),
            "branch_paths": {
                cat: list(self.branch_paths.get(cat, ()))
                for cat in FOREST_CATEGORIES
            },
            "artifact_refs": dict(self.artifact_refs),
            "parent_forest_root_cid": self.parent_forest_root_cid,
            "touched_categories": list(self.touched_categories),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ForestSnapshot:
        if not isinstance(payload, Mapping):
            raise ForestStoreError(
                "forest record must be a mapping",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.REJECTED,
            )
        if payload.get("schema", FOREST_RECORD_SCHEMA) != FOREST_RECORD_SCHEMA:
            raise ForestStoreError(
                "forest record schema mismatch",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.REJECTED,
            )
        raw_leaves = payload.get("leaves", {})
        if not isinstance(raw_leaves, Mapping):
            raise ForestStoreError(
                "forest record leaves must be a mapping",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.REJECTED,
            )
        leaves: dict[str, tuple[ProofForestLeaf, ...]] = {}
        for cat in FOREST_CATEGORIES:
            items = raw_leaves.get(cat, ())
            if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
                raise ForestStoreError(
                    f"leaves for {cat!r} must be a sequence",
                    reason=ForestReason.CORRUPTED,
                    disposition=ForestDisposition.REJECTED,
                )
            leaves[cat] = tuple(
                ProofForestLeaf.from_canonical(item) for item in items  # type: ignore[arg-type]
            )
        category_roots = payload.get("category_roots", {})
        category_merkle = payload.get("category_merkle_roots", {})
        branch_paths_raw = payload.get("branch_paths", {})
        artifact_refs = payload.get("artifact_refs", {})
        if not isinstance(category_roots, Mapping) or not isinstance(
            category_merkle, Mapping
        ):
            raise ForestStoreError(
                "category root maps must be mappings",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.REJECTED,
            )
        if not isinstance(branch_paths_raw, Mapping):
            raise ForestStoreError(
                "branch_paths must be a mapping",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.REJECTED,
            )
        if not isinstance(artifact_refs, Mapping):
            raise ForestStoreError(
                "artifact_refs must be a mapping",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.REJECTED,
            )
        parents = payload.get("parent_revision_ids", ())
        if not isinstance(parents, Sequence) or isinstance(parents, (str, bytes)):
            raise ForestStoreError(
                "parent_revision_ids must be a sequence",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.REJECTED,
            )
        node_cids = payload.get("node_cids", ())
        if not isinstance(node_cids, Sequence) or isinstance(node_cids, (str, bytes)):
            raise ForestStoreError(
                "node_cids must be a sequence",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.REJECTED,
            )
        touched = payload.get("touched_categories", ())
        if not isinstance(touched, Sequence) or isinstance(touched, (str, bytes)):
            raise ForestStoreError(
                "touched_categories must be a sequence",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.REJECTED,
            )
        return cls(
            root_cid=str(payload.get("root_cid") or ""),
            repository_id=str(payload.get("repository_id") or ""),
            revision=str(payload.get("revision") or ""),
            source_root_cid=str(payload.get("source_root_cid") or ""),
            manifest_root_cid=str(payload.get("manifest_root_cid") or ""),
            environment_cid=str(payload.get("environment_cid") or ""),
            policy_cid=str(payload.get("policy_cid") or ""),
            proof_schema_version=str(
                payload.get("proof_schema_version") or PROOF_SCHEMA_VERSION
            ),
            canonicalization_version=str(
                payload.get("canonicalization_version") or CANONICALIZATION_VERSION
            ),
            dependency_graph_schema_version=str(
                payload.get("dependency_graph_schema_version") or "graph@1"
            ),
            parent_seal_cid=str(
                payload.get("parent_seal_cid") or GENESIS_PARENT_SEAL
            ),
            parent_revision_ids=tuple(str(item) for item in parents),
            category_roots={
                cat: str(category_roots.get(cat) or "") for cat in FOREST_CATEGORIES
            },
            category_merkle_roots={
                cat: str(category_merkle.get(cat) or "") for cat in FOREST_CATEGORIES
            },
            leaves=leaves,
            node_cids=tuple(str(item) for item in node_cids),
            branch_paths={
                cat: tuple(str(item) for item in branch_paths_raw.get(cat, ()))
                for cat in FOREST_CATEGORIES
            },
            artifact_refs={str(k): str(v) for k, v in artifact_refs.items()},
            parent_forest_root_cid=str(payload.get("parent_forest_root_cid") or ""),
            touched_categories=tuple(str(item) for item in touched),
        )


@dataclass(frozen=True)
class ForestPersistResult:
    """Outcome of persisting a full forest."""

    disposition: ForestDisposition
    reason: ForestReason
    snapshot: ForestSnapshot | None = None
    root_cid: str = ""
    touched_categories: tuple[str, ...] = ()
    node_count: int = 0
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.disposition in {
            ForestDisposition.STORED,
            ForestDisposition.ALREADY_EXISTS,
        }

    @property
    def stored(self) -> bool:
        return bool(self)


@dataclass(frozen=True)
class ForestUpdateResult:
    """Outcome of an incremental affected-branch forest update."""

    disposition: ForestDisposition
    reason: ForestReason
    snapshot: ForestSnapshot | None = None
    root_cid: str = ""
    parent_root_cid: str = ""
    touched_categories: tuple[str, ...] = ()
    reused_categories: tuple[str, ...] = ()
    node_count: int = 0
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.disposition is ForestDisposition.UPDATED

    @property
    def updated(self) -> bool:
        return bool(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _thread_lock(root: Path) -> threading.RLock:
    key = os.path.abspath(os.fspath(root))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _path_safe_token(value: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ForestStoreError(
            "path token is malformed",
            reason=ForestReason.MALFORMED,
            disposition=ForestDisposition.REJECTED,
        )
    if "/" in value or "\\" in value or "\x00" in value or value in {".", ".."}:
        raise ForestStoreError(
            "path token contains separators or escape components",
            reason=ForestReason.MALFORMED,
            disposition=ForestDisposition.REJECTED,
        )
    token = value.replace(":", "_")
    if not _SAFE_TOKEN_RE.fullmatch(token) or ".." in token:
        raise ForestStoreError(
            "path token is not filesystem-safe",
            reason=ForestReason.MALFORMED,
            disposition=ForestDisposition.REJECTED,
        )
    return token


def _leaf_equality_key(leaf: ProofForestLeaf) -> tuple[str, str, str, int]:
    return (
        leaf.category,
        leaf.proof_unit_id,
        leaf.proof_object_cid,
        leaf.position,
    )


def _normalize_leaves_for_category(
    category: str, leaves: Sequence[Any]
) -> tuple[ProofForestLeaf, ...]:
    """Validate and normalize leaves via the datasets codec (fail-closed)."""

    try:
        return compute_category_root(category, leaves).leaves
    except ForestCodecError as exc:
        message = str(exc)
        reason = ForestReason.CODEC_REJECTED
        if "duplicate proof_unit_id" in message:
            reason = ForestReason.DUPLICATE_LEAF
        elif "canonical proof-unit ID byte order" in message:
            reason = ForestReason.REORDERED_LEAVES
        elif "duplicate leaf positions" in message or "positions must be" in message:
            reason = ForestReason.REORDERED_LEAVES
        raise ForestStoreError(
            message,
            reason=reason,
            disposition=ForestDisposition.REJECTED,
        ) from exc


def _category_root_payload(category_root: CategoryRoot) -> dict[str, Any]:
    return {
        "domain": DOMAIN_CATEGORY,
        "kind": "category",
        "category": category_root.category,
        "leaf_count": category_root.leaf_count,
        "leaf_ids": [leaf.proof_unit_id for leaf in category_root.leaves],
        "merkle_root": category_root.merkle_root,
        "schema": CATEGORY_ROOT_SCHEMA,
        "forest_codec_subset": FOREST_CODEC_SUBSET,
    }


def _repository_root_payload(repo: RepositoryProofRoot) -> dict[str, Any]:
    return {
        "domain": DOMAIN_REPOSITORY,
        "kind": "repository",
        "schema": REPOSITORY_PROOF_ROOT_SCHEMA,
        "forest_codec_subset": FOREST_CODEC_SUBSET,
        "repository_id": repo.repository_id,
        "revision": repo.revision,
        "source_root_cid": repo.source_root_cid,
        "manifest_root_cid": repo.manifest_root_cid,
        "environment_cid": repo.environment_cid,
        "policy_cid": repo.policy_cid,
        "proof_schema_version": repo.proof_schema_version,
        "canonicalization_version": repo.canonicalization_version,
        "dependency_graph_schema_version": repo.dependency_graph_schema_version,
        "parent_seal_cid": repo.parent_seal_cid,
        "parent_revision_ids": (
            list(repo.parent_revision_ids)
            if repo.parent_revision_ids
            else ABSENCE_TOKEN
        ),
        "category_roots": {
            cat: repo.category_roots[cat] for cat in FOREST_CATEGORIES
        },
        **{f"{cat}_root": repo.category_roots[cat] for cat in FOREST_CATEGORIES},
    }


def _collect_merkle_branch(
    category: str, leaves: Sequence[ProofForestLeaf]
) -> tuple[str, list[tuple[str, dict[str, Any]]]]:
    """Return (merkle_root, ordered node payloads) for one category branch.

    Node payloads mirror the datasets forest_codec encodings exactly so stored
    digests remain portable against IPS-011 vectors.
    """

    cat = parse_forest_category(category)
    nodes: list[tuple[str, dict[str, Any]]] = []
    if not leaves:
        payload = {
            "domain": DOMAIN_EMPTY,
            "kind": "empty",
            "category": cat,
            "schema": f"{FOREST_NAMESPACE}/empty@{SCHEMA_MAJOR}",
        }
        cid = encode_empty_node(category=cat)
        nodes.append((cid, payload))
        return cid, nodes

    level: list[str] = []
    for leaf in leaves:
        payload = {
            "domain": DOMAIN_LEAF,
            "kind": "leaf",
            "category": cat,
            "proof_unit_id": leaf.proof_unit_id,
            "proof_object_cid": leaf.proof_object_cid,
            "position": leaf.position,
            "schema": PROOF_FOREST_LEAF_SCHEMA,
        }
        cid = encode_leaf_node(
            category=cat,
            proof_unit_id=leaf.proof_unit_id,
            proof_object_cid=leaf.proof_object_cid,
            position=leaf.position,
        )
        nodes.append((cid, payload))
        level.append(cid)

    while len(level) > 1:
        next_level: list[str] = []
        index = 0
        while index < len(level):
            if index + 1 < len(level):
                left = level[index]
                right = level[index + 1]
                payload = {
                    "domain": DOMAIN_BINARY,
                    "kind": "binary",
                    "left_cid": left,
                    "right_cid": right,
                    "schema": f"{FOREST_NAMESPACE}/binary@{SCHEMA_MAJOR}",
                }
                cid = encode_binary_node(left_cid=left, right_cid=right)
                nodes.append((cid, payload))
                next_level.append(cid)
                index += 2
            else:
                child = level[index]
                payload = {
                    "domain": DOMAIN_UNARY,
                    "kind": "unary",
                    "child_cid": child,
                    "schema": f"{FOREST_NAMESPACE}/unary@{SCHEMA_MAJOR}",
                }
                cid = encode_unary_node(child_cid=child)
                nodes.append((cid, payload))
                next_level.append(cid)
                index += 1
        level = next_level
    return level[0], nodes


def verify_unaffected_leaves(
    parent_leaves: Mapping[str, Sequence[Any]],
    new_leaves: Mapping[str, Sequence[Any]],
    affected_categories: Sequence[str] | set[str] | frozenset[str],
) -> UnaffectedLeafVerification:
    """Prove by equality that every unaffected leaf survived an update.

    For each closed category outside ``affected_categories``, the multiset of
    ``(unit_id, proof_object_cid, position)`` keys must be identical between
    parent and new leaf sets.  Missing or altered leaves fail closed.
    """

    if not isinstance(parent_leaves, Mapping) or not isinstance(new_leaves, Mapping):
        return UnaffectedLeafVerification(
            disposition=ForestDisposition.REJECTED,
            reason=ForestReason.MALFORMED,
            diagnostics={"detail": "parent_leaves and new_leaves must be mappings"},
        )
    try:
        affected = frozenset(
            parse_forest_category(cat) for cat in affected_categories
        )
    except ForestCodecError as exc:
        return UnaffectedLeafVerification(
            disposition=ForestDisposition.REJECTED,
            reason=ForestReason.CODEC_REJECTED,
            diagnostics={"detail": str(exc)},
        )

    # Reject unknown categories in either map.
    try:
        parent_map: dict[str, tuple[ProofForestLeaf, ...]] = {}
        for key, value in parent_leaves.items():
            cat = parse_forest_category(key)
            parent_map[cat] = _normalize_leaves_for_category(cat, value)
        new_map: dict[str, tuple[ProofForestLeaf, ...]] = {}
        for key, value in new_leaves.items():
            cat = parse_forest_category(key)
            new_map[cat] = _normalize_leaves_for_category(cat, value)
    except ForestStoreError as exc:
        return UnaffectedLeafVerification(
            disposition=ForestDisposition.REJECTED,
            reason=exc.reason,
            diagnostics={"detail": str(exc)},
        )
    except ForestCodecError as exc:
        return UnaffectedLeafVerification(
            disposition=ForestDisposition.REJECTED,
            reason=ForestReason.CODEC_REJECTED,
            diagnostics={"detail": str(exc)},
        )

    lost: list[str] = []
    changed: list[str] = []
    verified = 0
    unaffected: list[str] = []
    for cat in FOREST_CATEGORIES:
        if cat in affected:
            continue
        unaffected.append(cat)
        parent_set = parent_map.get(cat, ())
        new_set = new_map.get(cat, ())
        parent_keys = [_leaf_equality_key(leaf) for leaf in parent_set]
        new_keys = [_leaf_equality_key(leaf) for leaf in new_set]
        if parent_keys != new_keys:
            parent_by_id = {leaf.proof_unit_id: leaf for leaf in parent_set}
            new_by_id = {leaf.proof_unit_id: leaf for leaf in new_set}
            for unit_id, leaf in parent_by_id.items():
                if unit_id not in new_by_id:
                    lost.append(f"{cat}:{unit_id}")
                elif _leaf_equality_key(leaf) != _leaf_equality_key(new_by_id[unit_id]):
                    changed.append(f"{cat}:{unit_id}")
            for unit_id in new_by_id:
                if unit_id not in parent_by_id:
                    # Unexpected leaf on an unaffected branch is a change.
                    changed.append(f"{cat}:{unit_id}")
            if not lost and not changed:
                # Order/position drift without id change.
                lost.append(f"{cat}:order")
        else:
            verified += len(parent_set)

    if lost or changed:
        return UnaffectedLeafVerification(
            disposition=ForestDisposition.REJECTED,
            reason=ForestReason.LOST_UNAFFECTED_LEAF,
            unaffected_categories=tuple(unaffected),
            verified_leaf_count=verified,
            lost_leaves=tuple(lost),
            changed_leaves=tuple(changed),
        )
    return UnaffectedLeafVerification(
        disposition=ForestDisposition.VERIFIED,
        reason=ForestReason.OK,
        unaffected_categories=tuple(unaffected),
        verified_leaf_count=verified,
    )


# ---------------------------------------------------------------------------
# ProofForestStore
# ---------------------------------------------------------------------------


class ProofForestStore:
    """Persist deterministic proof forests and update affected branches only.

    Construction requires an explicit store root.  Semantic roots are computed
    exclusively through the datasets forest codec.
    """

    __test__ = False

    def __init__(
        self,
        root: StoreRoot | str | Path | os.PathLike[str] | None,
        *,
        object_store: HermeticProofSealStore | None = None,
        create: bool = True,
    ) -> None:
        if root is None:
            raise ExplicitRootRequiredError(
                "ProofForestStore requires an explicit StoreRoot; "
                "no default user-state or daemon root exists"
            )
        if isinstance(root, StoreRoot):
            store_root = root
        else:
            store_root = StoreRoot.require(root)
        validate_explicit_root_path(store_root.root_path, field_name="root_path")

        self._root = store_root
        self._root_path = Path(store_root.root_path)
        self._lock = _thread_lock(self._root_path)
        if object_store is None:
            self._objects = HermeticProofSealStore(store_root, create=create)
        else:
            if not isinstance(object_store, HermeticProofSealStore):
                raise ProofSealStoreContractError(
                    "object_store must be a HermeticProofSealStore"
                )
            self._objects = object_store

        if self._root_path.exists() and self._root_path.is_symlink():
            raise ForestStoreError(
                "forest store root must not be a symlink",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.ERROR,
            )
        if create:
            self._ensure_layout()

    @property
    def root(self) -> StoreRoot:
        return self._root

    @property
    def root_path(self) -> Path:
        return self._root_path

    @property
    def object_store(self) -> HermeticProofSealStore:
        return self._objects

    def _ensure_layout(self) -> None:
        forest_dir = self._root_path / _FOREST_DIR
        records_dir = forest_dir / _RECORDS_DIR
        forest_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        records_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _record_path(self, root_cid: str) -> Path:
        token = _path_safe_token(root_cid)
        # Content-addressed secondary key avoids overly long path tokens.
        digest = hashlib.sha256(root_cid.encode("utf-8")).hexdigest()
        return (
            self._root_path
            / _FOREST_DIR
            / _RECORDS_DIR
            / f"{digest[:16]}_{token[:48]}{_RECORD_SUFFIX}"
        )

    def _atomic_write_path(self, path: Path, payload: Mapping[str, Any]) -> None:
        data = _canonical_json_bytes(payload)
        if len(data) > _MAX_RECORD_BYTES:
            raise ForestStoreError(
                "forest record exceeds byte budget",
                reason=ForestReason.OVER_BUDGET,
                disposition=ForestDisposition.REJECTED,
            )
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.is_symlink():
            raise ForestStoreError(
                "forest parent directory must not be a symlink",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.ERROR,
            )
        descriptor = -1
        temporary_name = ""
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
            )
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                written = stream.write(data)
                if written != len(data):
                    raise ForestStoreError(
                        f"short write: wrote {written} of {len(data)} bytes",
                        reason=ForestReason.SHORT_WRITE,
                        disposition=ForestDisposition.ERROR,
                    )
                stream.flush()
                try:
                    os.fsync(stream.fileno())
                except OSError as exc:
                    raise ForestStoreError(
                        f"fsync of forest record failed: {exc}",
                        reason=ForestReason.FSYNC_FAILED,
                        disposition=ForestDisposition.ERROR,
                    ) from exc
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, path)
            temporary_name = ""
            try:
                dir_fd = os.open(path.parent, os.O_RDONLY)
            except OSError as exc:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                raise ForestStoreError(
                    f"unable to open parent directory for fsync: {exc}",
                    reason=ForestReason.FSYNC_FAILED,
                    disposition=ForestDisposition.ERROR,
                ) from exc
            try:
                try:
                    os.fsync(dir_fd)
                except OSError as exc:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                    raise ForestStoreError(
                        f"fsync of parent directory failed: {exc}",
                        reason=ForestReason.FSYNC_FAILED,
                        disposition=ForestDisposition.ERROR,
                    ) from exc
            finally:
                os.close(dir_fd)
        except ForestStoreError:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary_name:
                try:
                    os.unlink(temporary_name)
                except OSError:
                    pass
            raise
        except OSError as exc:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary_name:
                try:
                    os.unlink(temporary_name)
                except OSError:
                    pass
            raise ForestStoreError(
                f"forest record write failed: {exc}",
                reason=ForestReason.IO_ERROR,
                disposition=ForestDisposition.ERROR,
            ) from exc

    def _put_node(self, forest_cid: str, payload: Mapping[str, Any]) -> ArtifactReference:
        data = _canonical_json_bytes(payload)
        try:
            return self._objects.put_immutable(ArtifactKind.MERKLE_NODE, data)
        except LocalStoreError as exc:
            raise ForestStoreError(
                f"failed to persist merkle node {forest_cid}: {exc}",
                reason=ForestReason.IO_ERROR,
                disposition=ForestDisposition.ERROR,
            ) from exc

    def _build_snapshot(
        self,
        *,
        repo: RepositoryProofRoot,
        category_roots: Mapping[str, CategoryRoot],
        parent_forest_root_cid: str = "",
        touched_categories: Sequence[str] = (),
    ) -> ForestSnapshot:
        node_cids: list[str] = []
        branch_paths: dict[str, tuple[str, ...]] = {}
        artifact_refs: dict[str, str] = {}
        leaves: dict[str, tuple[ProofForestLeaf, ...]] = {}
        category_merkle: dict[str, str] = {}
        category_root_cids: dict[str, str] = {}

        for cat in FOREST_CATEGORIES:
            cr = category_roots[cat]
            leaves[cat] = cr.leaves
            category_merkle[cat] = cr.merkle_root
            category_root_cids[cat] = cr.root_cid

            merkle, branch_nodes = _collect_merkle_branch(cat, cr.leaves)
            if merkle != cr.merkle_root:
                raise ForestStoreIntegrityError(
                    f"branch merkle mismatch for {cat}",
                    reason=ForestReason.BRANCH_MISMATCH,
                    disposition=ForestDisposition.REJECTED,
                )
            path_cids: list[str] = []
            for forest_cid, payload in branch_nodes:
                ref = self._put_node(forest_cid, payload)
                artifact_refs[forest_cid] = ref.cid
                node_cids.append(forest_cid)
                path_cids.append(forest_cid)

            cat_payload = _category_root_payload(cr)
            cat_ref = self._put_node(cr.root_cid, cat_payload)
            artifact_refs[cr.root_cid] = cat_ref.cid
            node_cids.append(cr.root_cid)
            path_cids.append(cr.root_cid)
            branch_paths[cat] = tuple(path_cids)

        repo_payload = _repository_root_payload(repo)
        repo_ref = self._put_node(repo.root_cid, repo_payload)
        artifact_refs[repo.root_cid] = repo_ref.cid
        node_cids.append(repo.root_cid)

        # Stable unique node list (first-seen order).
        seen: set[str] = set()
        unique_nodes: list[str] = []
        for cid in node_cids:
            if cid not in seen:
                seen.add(cid)
                unique_nodes.append(cid)

        return ForestSnapshot(
            root_cid=repo.root_cid,
            repository_id=repo.repository_id,
            revision=repo.revision,
            source_root_cid=repo.source_root_cid,
            manifest_root_cid=repo.manifest_root_cid,
            environment_cid=repo.environment_cid,
            policy_cid=repo.policy_cid,
            proof_schema_version=repo.proof_schema_version,
            canonicalization_version=repo.canonicalization_version,
            dependency_graph_schema_version=repo.dependency_graph_schema_version,
            parent_seal_cid=repo.parent_seal_cid,
            parent_revision_ids=repo.parent_revision_ids,
            category_roots=category_root_cids,
            category_merkle_roots=category_merkle,
            leaves=leaves,
            node_cids=tuple(unique_nodes),
            branch_paths=branch_paths,
            artifact_refs=artifact_refs,
            parent_forest_root_cid=parent_forest_root_cid,
            touched_categories=tuple(
                parse_forest_category(cat) for cat in touched_categories
            ),
        )

    def _write_snapshot(self, snapshot: ForestSnapshot) -> ForestDisposition:
        path = self._record_path(snapshot.root_cid)
        if path.exists() and not path.is_symlink():
            existing = self.load_forest(snapshot.root_cid)
            # Content-addressed: identical repository root_cid is a deterministic
            # replay of the same forest commitment (datasets codec authority).
            if existing.root_cid == snapshot.root_cid:
                if (
                    dict(existing.category_roots) != dict(snapshot.category_roots)
                    or existing.manifest_root_cid != snapshot.manifest_root_cid
                    or existing.source_root_cid != snapshot.source_root_cid
                    or existing.revision != snapshot.revision
                    or existing.repository_id != snapshot.repository_id
                ):
                    raise ForestStoreIntegrityError(
                        "forest root_cid collision with divergent record",
                        reason=ForestReason.ROOT_MISMATCH,
                        disposition=ForestDisposition.REJECTED,
                    )
                return ForestDisposition.ALREADY_EXISTS
        self._atomic_write_path(path, snapshot.to_dict())
        return ForestDisposition.STORED

    def load_forest(self, root_cid: str) -> ForestSnapshot:
        """Load a previously persisted forest snapshot by repository root CID."""

        if type(root_cid) is not str or not root_cid.strip():
            raise ForestStoreError(
                "root_cid must be a non-empty string",
                reason=ForestReason.MALFORMED,
                disposition=ForestDisposition.REJECTED,
            )
        path = self._record_path(root_cid.strip())
        if not path.exists():
            raise ForestStoreNotFoundError(
                f"forest root {root_cid!r} not found",
                reason=ForestReason.NOT_FOUND,
                disposition=ForestDisposition.MISS,
            )
        if path.is_symlink():
            raise ForestStoreError(
                "forest record path must not be a symlink",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.ERROR,
            )
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ForestStoreError(
                f"failed to read forest record: {exc}",
                reason=ForestReason.IO_ERROR,
                disposition=ForestDisposition.ERROR,
            ) from exc
        if len(data) > _MAX_RECORD_BYTES:
            raise ForestStoreError(
                "forest record exceeds byte budget",
                reason=ForestReason.OVER_BUDGET,
                disposition=ForestDisposition.REJECTED,
            )
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ForestStoreError(
                "forest record is corrupted",
                reason=ForestReason.CORRUPTED,
                disposition=ForestDisposition.REJECTED,
            ) from exc
        snapshot = ForestSnapshot.from_dict(payload)
        if snapshot.root_cid != root_cid.strip():
            raise ForestStoreIntegrityError(
                "forest record root_cid does not match lookup key",
                reason=ForestReason.ROOT_MISMATCH,
                disposition=ForestDisposition.REJECTED,
            )
        return snapshot

    def persist_forest(
        self,
        *,
        repository_id: str,
        revision: str,
        source_root_cid: str,
        manifest_root_cid: str,
        environment_cid: str,
        policy_cid: str,
        category_leaves: Mapping[str, Sequence[Any]] | None = None,
        proof_schema_version: str = PROOF_SCHEMA_VERSION,
        canonicalization_version: str = CANONICALIZATION_VERSION,
        dependency_graph_schema_version: str = "graph@1",
        parent_seal_cid: str = GENESIS_PARENT_SEAL,
        parent_revision_ids: Sequence[str] | str = (),
        claimed_root_cid: str | None = None,
    ) -> ForestPersistResult:
        """Compute, persist, and index a full deterministic proof forest."""

        with self._lock:
            try:
                return self._persist_forest_locked(
                    repository_id=repository_id,
                    revision=revision,
                    source_root_cid=source_root_cid,
                    manifest_root_cid=manifest_root_cid,
                    environment_cid=environment_cid,
                    policy_cid=policy_cid,
                    category_leaves=category_leaves,
                    proof_schema_version=proof_schema_version,
                    canonicalization_version=canonicalization_version,
                    dependency_graph_schema_version=dependency_graph_schema_version,
                    parent_seal_cid=parent_seal_cid,
                    parent_revision_ids=parent_revision_ids,
                    claimed_root_cid=claimed_root_cid,
                )
            except ForestStoreError as exc:
                return ForestPersistResult(
                    disposition=exc.disposition or ForestDisposition.REJECTED,
                    reason=exc.reason,
                    diagnostics={"detail": str(exc)},
                )

    def _persist_forest_locked(
        self,
        *,
        repository_id: str,
        revision: str,
        source_root_cid: str,
        manifest_root_cid: str,
        environment_cid: str,
        policy_cid: str,
        category_leaves: Mapping[str, Sequence[Any]] | None,
        proof_schema_version: str,
        canonicalization_version: str,
        dependency_graph_schema_version: str,
        parent_seal_cid: str,
        parent_revision_ids: Sequence[str] | str,
        claimed_root_cid: str | None,
    ) -> ForestPersistResult:
        leaves_map = category_leaves if category_leaves is not None else {}
        if not isinstance(leaves_map, Mapping):
            raise ForestStoreError(
                "category_leaves must be a mapping",
                reason=ForestReason.MALFORMED,
                disposition=ForestDisposition.REJECTED,
            )

        normalized: dict[str, tuple[ProofForestLeaf, ...]] = {
            cat: () for cat in FOREST_CATEGORIES
        }
        category_roots: dict[str, CategoryRoot] = {}
        try:
            for key, value in leaves_map.items():
                cat = parse_forest_category(key)
                normalized[cat] = _normalize_leaves_for_category(cat, value)
            for cat in FOREST_CATEGORIES:
                category_roots[cat] = compute_category_root(cat, normalized[cat])
            repo = compute_repository_root(
                repository_id=repository_id,
                revision=revision,
                source_root_cid=source_root_cid,
                manifest_root_cid=manifest_root_cid,
                environment_cid=environment_cid,
                policy_cid=policy_cid,
                category_roots={
                    cat: category_roots[cat].root_cid for cat in FOREST_CATEGORIES
                },
                proof_schema_version=proof_schema_version,
                canonicalization_version=canonicalization_version,
                dependency_graph_schema_version=dependency_graph_schema_version,
                parent_seal_cid=parent_seal_cid,
                parent_revision_ids=parent_revision_ids,
            )
        except ForestCodecError as exc:
            raise ForestStoreError(
                str(exc),
                reason=ForestReason.CODEC_REJECTED,
                disposition=ForestDisposition.REJECTED,
            ) from exc

        if claimed_root_cid is not None and claimed_root_cid != repo.root_cid:
            raise ForestStoreIntegrityError(
                "claimed_root_cid does not match computed repository root",
                reason=ForestReason.ROOT_MISMATCH,
                disposition=ForestDisposition.REJECTED,
            )

        non_empty = tuple(
            cat for cat in FOREST_CATEGORIES if category_roots[cat].leaf_count > 0
        )
        snapshot = self._build_snapshot(
            repo=repo,
            category_roots=category_roots,
            touched_categories=non_empty or FOREST_CATEGORIES,
        )
        disposition = self._write_snapshot(snapshot)
        reason = (
            ForestReason.ALREADY_EXISTS
            if disposition is ForestDisposition.ALREADY_EXISTS
            else ForestReason.OK
        )
        return ForestPersistResult(
            disposition=disposition,
            reason=reason,
            snapshot=snapshot,
            root_cid=snapshot.root_cid,
            touched_categories=snapshot.touched_categories,
            node_count=len(snapshot.node_cids),
        )

    def update_forest_branches(
        self,
        parent_root_cid: str,
        *,
        affected_category_leaves: Mapping[str, Sequence[Any]],
        revision: str | None = None,
        source_root_cid: str | None = None,
        manifest_root_cid: str | None = None,
        environment_cid: str | None = None,
        policy_cid: str | None = None,
        proof_schema_version: str | None = None,
        canonicalization_version: str | None = None,
        dependency_graph_schema_version: str | None = None,
        parent_seal_cid: str | None = None,
        parent_revision_ids: Sequence[str] | str | None = None,
        full_category_leaves: Mapping[str, Sequence[Any]] | None = None,
        claimed_repository_root_cid: str | None = None,
    ) -> ForestUpdateResult:
        """Recompute only affected category branches of a parent forest.

        Unaffected category roots and leaves are reused by equality.  When
        ``full_category_leaves`` is supplied, :func:`verify_unaffected_leaves`
        must pass.  A changed manifest paired with an old aggregate root, or
        any claimed old repository root after material change, is rejected.
        """

        with self._lock:
            try:
                return self._update_forest_branches_locked(
                    parent_root_cid=parent_root_cid,
                    affected_category_leaves=affected_category_leaves,
                    revision=revision,
                    source_root_cid=source_root_cid,
                    manifest_root_cid=manifest_root_cid,
                    environment_cid=environment_cid,
                    policy_cid=policy_cid,
                    proof_schema_version=proof_schema_version,
                    canonicalization_version=canonicalization_version,
                    dependency_graph_schema_version=dependency_graph_schema_version,
                    parent_seal_cid=parent_seal_cid,
                    parent_revision_ids=parent_revision_ids,
                    full_category_leaves=full_category_leaves,
                    claimed_repository_root_cid=claimed_repository_root_cid,
                )
            except ForestStoreError as exc:
                return ForestUpdateResult(
                    disposition=exc.disposition or ForestDisposition.REJECTED,
                    reason=exc.reason,
                    parent_root_cid=parent_root_cid,
                    diagnostics={"detail": str(exc)},
                )

    def _update_forest_branches_locked(
        self,
        *,
        parent_root_cid: str,
        affected_category_leaves: Mapping[str, Sequence[Any]],
        revision: str | None,
        source_root_cid: str | None,
        manifest_root_cid: str | None,
        environment_cid: str | None,
        policy_cid: str | None,
        proof_schema_version: str | None,
        canonicalization_version: str | None,
        dependency_graph_schema_version: str | None,
        parent_seal_cid: str | None,
        parent_revision_ids: Sequence[str] | str | None,
        full_category_leaves: Mapping[str, Sequence[Any]] | None,
        claimed_repository_root_cid: str | None,
    ) -> ForestUpdateResult:
        if type(parent_root_cid) is not str or not parent_root_cid.strip():
            raise ForestStoreError(
                "parent_root_cid must be a non-empty string",
                reason=ForestReason.MALFORMED,
                disposition=ForestDisposition.REJECTED,
            )
        if not isinstance(affected_category_leaves, Mapping):
            raise ForestStoreError(
                "affected_category_leaves must be a mapping",
                reason=ForestReason.MALFORMED,
                disposition=ForestDisposition.REJECTED,
            )
        if not affected_category_leaves and full_category_leaves is None:
            # Context-only updates (e.g. manifest change) are allowed with empty
            # affected map, but still require recomputing the repository root.
            pass

        parent = self.load_forest(parent_root_cid.strip())

        try:
            affected: dict[str, tuple[ProofForestLeaf, ...]] = {}
            for key, value in affected_category_leaves.items():
                cat = parse_forest_category(key)
                if cat in affected:
                    raise ForestStoreError(
                        f"duplicate affected category {cat!r}",
                        reason=ForestReason.MALFORMED,
                        disposition=ForestDisposition.REJECTED,
                    )
                affected[cat] = _normalize_leaves_for_category(cat, value)
        except ForestCodecError as exc:
            raise ForestStoreError(
                str(exc),
                reason=ForestReason.CODEC_REJECTED,
                disposition=ForestDisposition.REJECTED,
            ) from exc

        # Assemble the full new leaf map: affected overrides, others from parent.
        new_leaves: dict[str, tuple[ProofForestLeaf, ...]] = {
            cat: parent.leaves.get(cat, ()) for cat in FOREST_CATEGORIES
        }
        for cat, leaves in affected.items():
            new_leaves[cat] = leaves

        if full_category_leaves is not None:
            if not isinstance(full_category_leaves, Mapping):
                raise ForestStoreError(
                    "full_category_leaves must be a mapping",
                    reason=ForestReason.MALFORMED,
                    disposition=ForestDisposition.REJECTED,
                )
            try:
                provided: dict[str, tuple[ProofForestLeaf, ...]] = {
                    cat: () for cat in FOREST_CATEGORIES
                }
                for key, value in full_category_leaves.items():
                    cat = parse_forest_category(key)
                    provided[cat] = _normalize_leaves_for_category(cat, value)
            except ForestCodecError as exc:
                raise ForestStoreError(
                    str(exc),
                    reason=ForestReason.CODEC_REJECTED,
                    disposition=ForestDisposition.REJECTED,
                ) from exc

            # Affected leaves in the full map must match the declared updates.
            for cat, leaves in affected.items():
                if provided[cat] != leaves:
                    raise ForestStoreError(
                        f"full_category_leaves for affected {cat!r} "
                        "does not match affected_category_leaves",
                        reason=ForestReason.AFFECTED_MISMATCH,
                        disposition=ForestDisposition.REJECTED,
                    )

            witness = verify_unaffected_leaves(
                parent.category_leaves_map(),
                provided,
                set(affected),
            )
            if not witness.verified:
                raise ForestStoreError(
                    "unaffected leaf equality witness failed: "
                    f"lost={list(witness.lost_leaves)} "
                    f"changed={list(witness.changed_leaves)}",
                    reason=ForestReason.LOST_UNAFFECTED_LEAF,
                    disposition=ForestDisposition.REJECTED,
                )
            new_leaves = provided

        # Resolve new repository context (defaults preserve parent fields).
        new_revision = revision if revision is not None else parent.revision
        new_source = (
            source_root_cid if source_root_cid is not None else parent.source_root_cid
        )
        new_manifest = (
            manifest_root_cid
            if manifest_root_cid is not None
            else parent.manifest_root_cid
        )
        new_environment = (
            environment_cid if environment_cid is not None else parent.environment_cid
        )
        new_policy = policy_cid if policy_cid is not None else parent.policy_cid
        new_schema = (
            proof_schema_version
            if proof_schema_version is not None
            else parent.proof_schema_version
        )
        new_canon = (
            canonicalization_version
            if canonicalization_version is not None
            else parent.canonicalization_version
        )
        new_graph = (
            dependency_graph_schema_version
            if dependency_graph_schema_version is not None
            else parent.dependency_graph_schema_version
        )
        new_parent_seal = (
            parent_seal_cid if parent_seal_cid is not None else parent.parent_seal_cid
        )
        new_parent_revs: Sequence[str] | str
        if parent_revision_ids is None:
            new_parent_revs = parent.parent_revision_ids
        else:
            new_parent_revs = parent_revision_ids

        # Recompute only affected category roots; reuse others by CID equality.
        category_roots: dict[str, CategoryRoot] = {}
        touched: list[str] = []
        reused: list[str] = []
        try:
            for cat in FOREST_CATEGORIES:
                if cat in affected:
                    cr = compute_category_root(cat, new_leaves[cat])
                    category_roots[cat] = cr
                    if cr.root_cid != parent.category_roots[cat]:
                        touched.append(cat)
                    else:
                        # Declared affected but content-identical still counts
                        # as a touched branch for the update path.
                        touched.append(cat)
                else:
                    # Reuse parent branch: reconstruct CategoryRoot from parent.
                    cr = compute_category_root(cat, new_leaves[cat])
                    if cr.root_cid != parent.category_roots[cat]:
                        raise ForestStoreIntegrityError(
                            f"unaffected category {cat!r} root changed without "
                            "being declared affected",
                            reason=ForestReason.BRANCH_MISMATCH,
                            disposition=ForestDisposition.REJECTED,
                        )
                    category_roots[cat] = cr
                    reused.append(cat)

            repo = compute_repository_root(
                repository_id=parent.repository_id,
                revision=new_revision,
                source_root_cid=new_source,
                manifest_root_cid=new_manifest,
                environment_cid=new_environment,
                policy_cid=new_policy,
                category_roots={
                    cat: category_roots[cat].root_cid for cat in FOREST_CATEGORIES
                },
                proof_schema_version=new_schema,
                canonicalization_version=new_canon,
                dependency_graph_schema_version=new_graph,
                parent_seal_cid=new_parent_seal,
                parent_revision_ids=new_parent_revs,
            )
        except ForestCodecError as exc:
            raise ForestStoreError(
                str(exc),
                reason=ForestReason.CODEC_REJECTED,
                disposition=ForestDisposition.REJECTED,
            ) from exc

        material_change = repo.root_cid != parent.root_cid

        if claimed_repository_root_cid is not None:
            if (
                claimed_repository_root_cid == parent.root_cid
                and material_change
            ):
                reason = (
                    ForestReason.MANIFEST_AGGREGATE_MISMATCH
                    if new_manifest != parent.manifest_root_cid
                    else ForestReason.OLD_AGGREGATE
                )
                raise ForestStoreIntegrityError(
                    "claimed old repository aggregate root after material forest change",
                    reason=reason,
                    disposition=ForestDisposition.REJECTED,
                )
            if claimed_repository_root_cid != repo.root_cid:
                raise ForestStoreIntegrityError(
                    "claimed_repository_root_cid does not match computed root",
                    reason=ForestReason.ROOT_MISMATCH,
                    disposition=ForestDisposition.REJECTED,
                )

        # Changed manifest must not reuse the old aggregate root.
        if (
            new_manifest != parent.manifest_root_cid
            and not material_change
        ):
            raise ForestStoreIntegrityError(
                "manifest changed but repository aggregate root is unchanged",
                reason=ForestReason.MANIFEST_AGGREGATE_MISMATCH,
                disposition=ForestDisposition.REJECTED,
            )

        if affected and not material_change:
            # Defensive: leaf changes must propagate (codec guarantees this).
            raise ForestStoreIntegrityError(
                "affected branch update did not change repository root",
                reason=ForestReason.ROOT_MISMATCH,
                disposition=ForestDisposition.REJECTED,
            )

        snapshot = self._build_snapshot(
            repo=repo,
            category_roots=category_roots,
            parent_forest_root_cid=parent.root_cid,
            touched_categories=touched,
        )
        # Prefer reused parent branch artifact refs for untouched categories so
        # path indexes stay stable under identical replay.
        merged_refs = dict(parent.artifact_refs)
        merged_refs.update(snapshot.artifact_refs)
        merged_paths = dict(parent.branch_paths)
        for cat in touched:
            merged_paths[cat] = snapshot.branch_paths[cat]
        snapshot = ForestSnapshot(
            root_cid=snapshot.root_cid,
            repository_id=snapshot.repository_id,
            revision=snapshot.revision,
            source_root_cid=snapshot.source_root_cid,
            manifest_root_cid=snapshot.manifest_root_cid,
            environment_cid=snapshot.environment_cid,
            policy_cid=snapshot.policy_cid,
            proof_schema_version=snapshot.proof_schema_version,
            canonicalization_version=snapshot.canonicalization_version,
            dependency_graph_schema_version=snapshot.dependency_graph_schema_version,
            parent_seal_cid=snapshot.parent_seal_cid,
            parent_revision_ids=snapshot.parent_revision_ids,
            category_roots=snapshot.category_roots,
            category_merkle_roots=snapshot.category_merkle_roots,
            leaves=snapshot.leaves,
            node_cids=snapshot.node_cids,
            branch_paths={
                cat: tuple(merged_paths[cat]) for cat in FOREST_CATEGORIES
            },
            artifact_refs=merged_refs,
            parent_forest_root_cid=parent.root_cid,
            touched_categories=tuple(touched),
        )
        self._write_snapshot(snapshot)
        return ForestUpdateResult(
            disposition=ForestDisposition.UPDATED,
            reason=ForestReason.OK,
            snapshot=snapshot,
            root_cid=snapshot.root_cid,
            parent_root_cid=parent.root_cid,
            touched_categories=tuple(touched),
            reused_categories=tuple(reused),
            node_count=len(snapshot.node_cids),
            diagnostics={
                "material_change": material_change,
                "manifest_changed": new_manifest != parent.manifest_root_cid,
            },
        )

    def verify_unaffected_leaves(
        self,
        parent_leaves: Mapping[str, Sequence[Any]],
        new_leaves: Mapping[str, Sequence[Any]],
        affected_categories: Sequence[str] | set[str] | frozenset[str],
    ) -> UnaffectedLeafVerification:
        """Instance wrapper for :func:`verify_unaffected_leaves`."""

        return verify_unaffected_leaves(
            parent_leaves, new_leaves, affected_categories
        )


# ---------------------------------------------------------------------------
# Module-level interface aliases
# ---------------------------------------------------------------------------


def persist_forest(
    store: ProofForestStore,
    **kwargs: Any,
) -> ForestPersistResult:
    """Persist a full forest through ``store``."""

    if not isinstance(store, ProofForestStore):
        raise ProofSealStoreContractError("store must be a ProofForestStore")
    return store.persist_forest(**kwargs)


def update_forest_branches(
    store: ProofForestStore,
    parent_root_cid: str,
    **kwargs: Any,
) -> ForestUpdateResult:
    """Update affected forest branches through ``store``."""

    if not isinstance(store, ProofForestStore):
        raise ProofSealStoreContractError("store must be a ProofForestStore")
    return store.update_forest_branches(parent_root_cid, **kwargs)


__all__ = (
    "CONTRACT_VERSION",
    "EVIDENCE_SUBSET",
    "FOREST_RECORD_SCHEMA",
    "FOREST_STORE_INTERFACE",
    "FOREST_STORE_SCHEMA",
    "ForestDisposition",
    "ForestPersistResult",
    "ForestReason",
    "ForestSnapshot",
    "ForestStoreError",
    "ForestStoreIntegrityError",
    "ForestStoreNotFoundError",
    "ForestUpdateResult",
    "ProofForestStore",
    "UnaffectedLeafVerification",
    "persist_forest",
    "update_forest_branches",
    "verify_unaffected_leaves",
)
