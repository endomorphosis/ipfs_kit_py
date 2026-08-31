"""Rebuildable, non-authoritative projection indexes over verified storage.

``ProjectionIndex`` wraps landed GraphRAG vector/hybrid/graph backends as
rebuildable artifacts.  ANN files and in-memory indexes are never the canonical
graph, never mint semantic identity, and never authorize exact reuse.

Authority rules (normative, fail-closed):

* Search proposes similarity only.  Every hit is a ``ProjectionCandidate`` that
  must be resolved and rehashed before use.
* Results always carry ``authoritative=false``, manifest/model profiles,
  limitations, and exact-resolution data.
* Backend files are rebuildable artifacts bound to an immutable index manifest
  and verified projection records.  They may be discarded and rebuilt.
* Unavailable index, model, or native ANN backend is a typed outcome.  Absence
  of an index never suppresses exact/raw-source fallback.
* Score, rank, and nearest-neighbor position are not identity.
* Cyclic ANN structures are not admitted as the canonical program graph.
"""

from __future__ import annotations

import importlib.util
import json
import math
import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar, Final, Iterable, Mapping, Sequence

from ipfs_kit_py.graphrag.projections import GraphProjection
from ipfs_kit_py.graphrag.retrieval import (
    HybridRetrievalError,
    HybridRetriever,
    HybridSearchResponse,
)
from ipfs_kit_py.graphrag.vector_index import (
    ANNBackend,
    ANNVectorIndex,
    ExactVectorIndex,
    VectorIdentityMismatchError,
    VectorIndex,
    VectorIndexError,
    VectorIndexIdentity,
    VectorRecord,
    VectorSearchResult,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    cid_for_artifact,
    cid_for_bytes,
)
from ipfs_kit_py.semantic_world_store.artifacts import (
    CanonicalVectorBytes,
    SemanticWorldArtifactAdmissionError,
    SemanticWorldArtifactError,
    pack_canonical_vector,
)
from ipfs_kit_py.semantic_world_store.verified_store import (
    PROJECTION_INDEX_MANIFEST_INTERFACE,
    VERIFIED_SEMANTIC_STORE_INTERFACE,
    ProjectionIndexManifest,
    ProjectionRecord,
    VerifiedSemanticBlockStore,
    VerifiedSemanticStoreAdmissionError,
    VerifiedSemanticStoreError,
    VerifiedSemanticStoreIntegrityError,
    VerifiedSemanticStoreNotFound,
)


PROJECTION_INDEX_INTERFACE: Final[str] = "ProjectionIndex@1"
PROJECTION_CANDIDATE_INTERFACE: Final[str] = "ProjectionCandidate@1"
PROJECTION_INDEX_SNAPSHOT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.projection-index-snapshot@1"
)
PROJECTION_INDEX_ARTIFACT_SCHEMA: Final[str] = (
    "ipfs-kit.semantic-world-store.projection-index-backend-artifact@1"
)
DEFAULT_QUERY_K: Final[int] = 10
MAX_QUERY_K: Final[int] = 1_000

ADVISORY_LIMITATIONS: Final[tuple[str, ...]] = (
    "advisory_similarity_only",
    "not_authority",
    "not_exact_reuse",
    "backend_profile_scoped",
    "index_absence_does_not_suppress_exact_raw_source_fallback",
    "backend_files_are_rebuildable_artifacts_only",
)

_SCORE_IDENTITY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "distance",
        "embedding_score",
        "knn",
        "nearest",
        "rank",
        "score",
        "scores",
        "similarity",
    }
)
_MUTABLE_DOCUMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "document_id",
        "doc_id",
        "mutable_id",
        "row_id",
        "unresolved_id",
    }
)
_NATIVE_ANN_MODULES: Final[tuple[str, ...]] = ("faiss", "hnswlib", "annoy")
_DTYPE_WIDTH: Final[Mapping[str, int]] = MappingProxyType(
    {
        "float32": 4,
        "float16": 2,
        "bfloat16": 2,
        "int8": 1,
        "uint8": 1,
        "int32": 4,
    }
)
_CLOSED_BACKENDS: Final[frozenset[str]] = frozenset(
    {"exact", "ann", "hybrid", "graph"}
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProjectionIndexError(VerifiedSemanticStoreError):
    """Base error for rebuildable projection-index operations."""

    reason_code: ClassVar[str] = "projection_index_error"


class ProjectionIndexAdmissionError(ProjectionIndexError, VerifiedSemanticStoreAdmissionError):
    """Raised when an index write, rebuild, or query is rejected."""

    reason_code: ClassVar[str] = "projection_index_admission_error"


class ProjectionIndexIntegrityError(ProjectionIndexError, VerifiedSemanticStoreIntegrityError):
    """Raised when index bytes, CIDs, or backend artifacts fail rehash."""

    reason_code: ClassVar[str] = "projection_index_integrity_error"


class ProjectionIndexUnavailable(ProjectionIndexError):
    """Typed unavailability: no rebuildable index is present for search."""

    reason_code: ClassVar[str] = "index_unavailable"


class ProjectionModelUnavailable(ProjectionIndexError):
    """Typed unavailability: query model/profile is not pinned to this index."""

    reason_code: ClassVar[str] = "model_unavailable"


class ProjectionBackendUnavailable(ProjectionIndexError):
    """Typed unavailability: requested native/graph backend cannot be used."""

    reason_code: ClassVar[str] = "index_unavailable"


# ---------------------------------------------------------------------------
# Capability probe (no install, no model load)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProjectionBackendCapability:
    """Result of a local capability probe for one index backend."""

    kind: str
    available: bool
    reason_code: str
    module: str | None = None
    rebuildable: bool = True
    authoritative: bool = False
    canonical_graph: bool = False

    def __post_init__(self) -> None:
        if self.authoritative is not False:
            raise ProjectionIndexAdmissionError(
                "projection backends are non-authoritative"
            )
        if self.canonical_graph is not False:
            raise ProjectionIndexAdmissionError(
                "ANN/graph backend files are not the canonical graph"
            )
        if self.rebuildable is not True:
            raise ProjectionIndexAdmissionError(
                "projection backends must be rebuildable artifacts"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "available": self.available,
            "reason_code": self.reason_code,
            "module": self.module,
            "rebuildable": self.rebuildable,
            "authoritative": False,
            "canonical_graph": False,
        }


def probe_projection_backends() -> tuple[ProjectionBackendCapability, ...]:
    """Probe vector/hybrid/graph/GraphRAG and optional native ANN backends.

    Uses ``importlib.util.find_spec`` only.  Missing native libraries are typed
    unavailable; GraphRAG exact/ANN/hybrid wrappers remain available as the
    deterministic rebuildable fallback.
    """

    capabilities: list[ProjectionBackendCapability] = [
        ProjectionBackendCapability(
            kind="exact",
            available=True,
            reason_code="available",
            module="ipfs_kit_py.graphrag.vector_index.ExactVectorIndex",
        ),
        ProjectionBackendCapability(
            kind="ann",
            available=True,
            reason_code="available",
            module="ipfs_kit_py.graphrag.vector_index.ANNVectorIndex",
        ),
        ProjectionBackendCapability(
            kind="hybrid",
            available=True,
            reason_code="available",
            module="ipfs_kit_py.graphrag.retrieval.HybridRetriever",
        ),
        ProjectionBackendCapability(
            kind="graph",
            available=True,
            reason_code="available",
            module="ipfs_kit_py.graphrag.projections.GraphProjection",
        ),
    ]
    for name in _NATIVE_ANN_MODULES:
        spec = importlib.util.find_spec(name)
        capabilities.append(
            ProjectionBackendCapability(
                kind=name,
                available=spec is not None,
                reason_code="available" if spec is not None else "native_ann_unavailable",
                module=name if spec is not None else None,
            )
        )
    return tuple(capabilities)


def native_ann_available() -> bool:
    """True when any optional native ANN library is importable in this process."""

    return any(
        item.available and item.kind in _NATIVE_ANN_MODULES
        for item in probe_projection_backends()
    )


# ---------------------------------------------------------------------------
# Vector unpack (rehash packed bytes; no second CID engine)
# ---------------------------------------------------------------------------


def unpack_canonical_vector(vector: CanonicalVectorBytes) -> tuple[float | int, ...]:
    """Unpack admitted vector bytes after re-verifying the claimed raw CID."""

    if not isinstance(vector, CanonicalVectorBytes):
        raise ProjectionIndexAdmissionError(
            "vector must be CanonicalVectorBytes"
        )
    admitted = pack_canonical_vector(
        vector.packed_bytes,
        dtype=vector.dtype,
        byte_order=vector.byte_order,
        dimension=vector.dimension,
    )
    if admitted.bytes_cid != vector.bytes_cid:
        raise ProjectionIndexIntegrityError(
            "vector CID does not rehash packed bytes"
        )
    width = _DTYPE_WIDTH[admitted.dtype]
    values: list[float | int] = []
    for index in range(admitted.dimension):
        chunk = admitted.packed_bytes[index * width : (index + 1) * width]
        if admitted.dtype == "bfloat16":
            bits = chunk[::-1] if admitted.byte_order == "little" else chunk
            number = float(struct.unpack(">f", bits + b"\x00\x00")[0])
            if not math.isfinite(number):
                raise ProjectionIndexAdmissionError(
                    f"NaN or infinity at vector index {index}"
                )
            values.append(number)
            continue
        endian = "<" if admitted.byte_order == "little" else ">"
        if admitted.dtype == "float32":
            number = float(struct.unpack(endian + "f", chunk)[0])
        elif admitted.dtype == "float16":
            number = float(struct.unpack(endian + "e", chunk)[0])
        elif admitted.dtype == "int8":
            number = int(struct.unpack(endian + "b", chunk)[0])
        elif admitted.dtype == "uint8":
            number = int(struct.unpack(endian + "B", chunk)[0])
        else:
            number = int(struct.unpack(endian + "i", chunk)[0])
        if isinstance(number, float) and not math.isfinite(number):
            raise ProjectionIndexAdmissionError(
                f"NaN or infinity at vector index {index}"
            )
        values.append(number)
    return tuple(values)


def vector_as_floats(vector: CanonicalVectorBytes) -> tuple[float, ...]:
    """Return finite floats suitable for GraphRAG scoring."""

    return tuple(float(item) for item in unpack_canonical_vector(vector))


def _reject_score_or_document_identity(payload: Mapping[str, Any], *, path: str) -> None:
    extra = set(payload) & _SCORE_IDENTITY_FIELDS
    if extra:
        raise ProjectionIndexAdmissionError(
            f"{path} rejects score-derived identity fields {sorted(extra)}"
        )
    extra_docs = set(payload) & _MUTABLE_DOCUMENT_FIELDS
    if extra_docs:
        raise ProjectionIndexAdmissionError(
            f"{path} rejects mutable unresolved document identity {sorted(extra_docs)}"
        )


# ---------------------------------------------------------------------------
# Advisory candidate (unresolved; not for use)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProjectionCandidate:
    """ProjectionCandidate@1: advisory ANN hit that is not yet resolved.

    ``score`` is ranking metadata only.  It is excluded from identity.  Callers
    must pass this value through ``resolve_projection_candidate`` before use.
    """

    projection_cid: str
    score: float
    manifest_cid: str
    model_cid: str
    tokenizer_cid: str
    preprocessing_profile_cid: str
    vector_cid: str
    claimed_subject_cid: str
    backend_kind: str
    limitations: tuple[str, ...] = ADVISORY_LIMITATIONS
    authoritative: bool = False
    resolved: bool = False

    SCHEMA: ClassVar[str] = (
        "ipfs-kit.semantic-world-store.projection-candidate@1"
    )
    INTERFACE: ClassVar[str] = PROJECTION_CANDIDATE_INTERFACE

    def __post_init__(self) -> None:
        for name in (
            "projection_cid",
            "manifest_cid",
            "model_cid",
            "tokenizer_cid",
            "preprocessing_profile_cid",
            "vector_cid",
            "claimed_subject_cid",
            "backend_kind",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise ProjectionIndexAdmissionError(
                    f"{name} must be a non-empty string"
                )
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise ProjectionIndexAdmissionError("score must be a finite number")
        if not math.isfinite(float(self.score)):
            raise ProjectionIndexAdmissionError("score must be a finite number")
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "limitations", tuple(self.limitations))
        if self.authoritative is not False:
            raise ProjectionIndexAdmissionError(
                "ANN candidates are non-authoritative; similarity is not authority"
            )
        if self.resolved is not False:
            raise ProjectionIndexAdmissionError(
                "ProjectionCandidate is unresolved; use ExactProjectionResolver"
            )
        if not self.limitations:
            raise ProjectionIndexAdmissionError(
                "projection candidates must declare limitations"
            )

    def identity_payload(self) -> dict[str, Any]:
        """Identity excludes score, rank, and other similarity material."""

        payload = {
            "schema": self.SCHEMA,
            "projection_cid": self.projection_cid,
            "manifest_cid": self.manifest_cid,
            "model_cid": self.model_cid,
            "tokenizer_cid": self.tokenizer_cid,
            "preprocessing_profile_cid": self.preprocessing_profile_cid,
            "vector_cid": self.vector_cid,
            "claimed_subject_cid": self.claimed_subject_cid,
            "backend_kind": self.backend_kind,
            "authoritative": False,
            "resolved": False,
        }
        _reject_score_or_document_identity(payload, path="projection_candidate")
        return payload

    def to_dict(self) -> dict[str, Any]:
        payload = self.identity_payload()
        payload["score"] = self.score
        payload["limitations"] = list(self.limitations)
        payload["exact_reuse"] = False
        return payload


@dataclass(frozen=True, slots=True)
class ProjectionIndexBackendArtifact:
    """Rebuildable backend sidecar.  Never a canonical graph or identity."""

    kind: str
    snapshot_cid: str
    rebuildable: bool = True
    authoritative: bool = False
    canonical_graph: bool = False
    path: str | None = None
    native_module: str | None = None

    SCHEMA: ClassVar[str] = PROJECTION_INDEX_ARTIFACT_SCHEMA

    def __post_init__(self) -> None:
        if type(self.kind) is not str or self.kind not in _CLOSED_BACKENDS | set(
            _NATIVE_ANN_MODULES
        ):
            raise ProjectionIndexAdmissionError(
                f"unknown projection backend kind: {self.kind!r}"
            )
        if type(self.snapshot_cid) is not str or not self.snapshot_cid:
            raise ProjectionIndexAdmissionError("snapshot_cid must be a CID")
        if self.rebuildable is not True:
            raise ProjectionIndexAdmissionError(
                "backend files are rebuildable artifacts only"
            )
        if self.authoritative is not False:
            raise ProjectionIndexAdmissionError(
                "backend files are non-authoritative"
            )
        if self.canonical_graph is not False:
            raise ProjectionIndexAdmissionError(
                "cyclic ANN/backend files are not the canonical graph"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "kind": self.kind,
            "snapshot_cid": self.snapshot_cid,
            "rebuildable": True,
            "authoritative": False,
            "canonical_graph": False,
            "path": self.path,
            "native_module": self.native_module,
        }


@dataclass(frozen=True, slots=True)
class ProjectionIndexRebuildReceipt:
    """Deterministic rebuild receipt.  Not completion or reuse authority."""

    snapshot_cid: str
    manifest_cid: str
    projection_cids: tuple[str, ...]
    vector_cids: tuple[str, ...]
    backend: ProjectionIndexBackendArtifact
    created: bool
    reason_code: str
    authoritative: bool = False

    def __post_init__(self) -> None:
        if self.authoritative is not False:
            raise ProjectionIndexAdmissionError(
                "index rebuilds are non-authoritative"
            )
        object.__setattr__(self, "projection_cids", tuple(self.projection_cids))
        object.__setattr__(self, "vector_cids", tuple(self.vector_cids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_cid": self.snapshot_cid,
            "manifest_cid": self.manifest_cid,
            "projection_cids": list(self.projection_cids),
            "vector_cids": list(self.vector_cids),
            "backend": self.backend.to_dict(),
            "created": self.created,
            "reason_code": self.reason_code,
            "authoritative": False,
            "rebuildable": True,
        }


@dataclass(frozen=True, slots=True)
class ProjectionSearchHit:
    """Internal ANN/exact hit prior to exact resolution."""

    candidate: ProjectionCandidate
    raw_score: float


# ---------------------------------------------------------------------------
# Index implementation
# ---------------------------------------------------------------------------


def _is_verified_semantic_store(store: object) -> bool:
    """True for ``VerifiedSemanticBlockStore``, including after module reload."""

    if isinstance(store, VerifiedSemanticBlockStore):
        return True
    if getattr(store, "INTERFACE", None) != VERIFIED_SEMANTIC_STORE_INTERFACE:
        return False
    return all(
        callable(getattr(store, name, None))
        for name in (
            "get_verified_projection_record",
            "get_verified_vector",
            "get_verified_semantic_object",
            "get_verified_projection_index_manifest",
        )
    )


def _as_manifest(
    store: VerifiedSemanticBlockStore,
    value: ProjectionIndexManifest | Mapping[str, Any] | str,
) -> ProjectionIndexManifest:
    if isinstance(value, ProjectionIndexManifest):
        return value
    if isinstance(value, str):
        return store.get_verified_projection_index_manifest(value)
    if isinstance(value, Mapping):
        return ProjectionIndexManifest.from_payload(value)
    raise ProjectionIndexAdmissionError(
        "manifest must be a ProjectionIndexManifest, mapping, or CID"
    )


def _vector_index_identity(manifest: ProjectionIndexManifest) -> VectorIndexIdentity:
    identity = manifest.identity
    return VectorIndexIdentity(
        index_id=manifest.projection_index_manifest_cid,
        model_id=identity.model_cid,
        tokenizer_id=identity.tokenizer_cid,
        dimension=identity.dimension,
        metric=identity.metric,
        source_id=identity.source_cid,
        source_version="projection-index-manifest@1",
        schema_version="vector-index@1",
    )


def projection_matches_manifest(
    record: ProjectionRecord, manifest: ProjectionIndexManifest
) -> bool:
    """True when a verified projection belongs to this index generation profile."""

    left = record.identity
    right = manifest.identity
    return (
        left.projection_kind == right.projection_kind
        and left.model_cid == right.model_cid
        and left.tokenizer_cid == right.tokenizer_cid
        and left.preprocessing_profile_cid == right.preprocessing_profile_cid
        and left.dimension == right.dimension
        and left.metric == right.metric
        and left.dtype == right.dtype
        and left.byte_order == right.byte_order
    )


def snapshot_cid_for(
    *,
    manifest_cid: str,
    projection_cids: Sequence[str],
    vector_cids: Sequence[str],
) -> str:
    """Content-address the rebuildable snapshot using the kit CID engine."""

    payload = {
        "schema": PROJECTION_INDEX_SNAPSHOT_SCHEMA,
        "interface_id": PROJECTION_INDEX_INTERFACE,
        "manifest_cid": manifest_cid,
        "projection_cids": list(projection_cids),
        "vector_cids": list(vector_cids),
        "rebuildable": True,
        "authoritative": False,
        "canonical_graph": False,
    }
    return cid_for_artifact(payload)


def _coerce_backend_kind(value: object) -> str:
    if isinstance(value, Enum):
        value = value.value
    if type(value) is not str or value not in _CLOSED_BACKENDS:
        raise ProjectionIndexAdmissionError(
            "backend must be exact, ann, hybrid, or graph"
        )
    return value


class ProjectionIndex:
    """ProjectionIndex@1: rebuildable ANN/exact wrapper over verified records.

    The GraphRAG ``ExactVectorIndex`` / ``ANNVectorIndex`` / ``HybridRetriever``
    surfaces are the search engines.  Verified projection records and the index
    manifest remain the identity authority.  Backend state can be dropped and
    rebuilt from those records.
    """

    INTERFACE: ClassVar[str] = PROJECTION_INDEX_INTERFACE

    def __init__(
        self,
        store: VerifiedSemanticBlockStore,
        manifest: ProjectionIndexManifest | Mapping[str, Any] | str,
        *,
        backend: str = "exact",
        ann_backend: ANNBackend | None = None,
        artifact_dir: Path | str | None = None,
        lexical_search: Any | None = None,
    ) -> None:
        if not _is_verified_semantic_store(store):
            raise TypeError("store must be a VerifiedSemanticBlockStore")
        self._store = store
        self._manifest = _as_manifest(store, manifest)
        if not self._manifest.identity.rebuildable:
            raise ProjectionIndexAdmissionError("index manifests must be rebuildable")
        if self._manifest.identity.authoritative:
            raise ProjectionIndexAdmissionError("index manifests are non-authoritative")
        self._backend_kind = _coerce_backend_kind(backend)
        self._ann_backend = ann_backend
        self._artifact_dir = Path(artifact_dir) if artifact_dir is not None else None
        self._lexical_search = lexical_search
        self._vector_identity = _vector_index_identity(self._manifest)
        self._engine: VectorIndex | None = None
        self._hybrid: HybridRetriever | None = None
        self._records: dict[str, tuple[ProjectionRecord, CanonicalVectorBytes]] = {}
        self._projection_cids: tuple[str, ...] = ()
        self._vector_cids: tuple[str, ...] = ()
        self._snapshot_cid: str | None = None
        self._built = False
        self._native_module: str | None = None
        self._capabilities = probe_projection_backends()
        self._graph_projection_type: type[GraphProjection] | None = None
        if self._backend_kind == "graph":
            # GraphRAG graph projections are wrap-only rebuildable artifacts.
            # They are never a similarity authority and never the canonical graph.
            self._graph_projection_type = GraphProjection
            self._engine = None
        elif self._backend_kind == "ann":
            self._engine = ANNVectorIndex(
                self._vector_identity, backend=ann_backend
            )
        else:
            self._engine = ExactVectorIndex(self._vector_identity)
        if self._backend_kind == "hybrid":
            if self._engine is None:
                raise ProjectionIndexAdmissionError(
                    "hybrid backend requires a vector engine"
                )
            self._hybrid = HybridRetriever(
                self._engine, lexical_search=lexical_search
            )

    @property
    def store(self) -> VerifiedSemanticBlockStore:
        return self._store

    @property
    def manifest(self) -> ProjectionIndexManifest:
        return self._manifest

    @property
    def manifest_cid(self) -> str:
        return self._manifest.projection_index_manifest_cid

    @property
    def backend_kind(self) -> str:
        return self._backend_kind

    @property
    def built(self) -> bool:
        return self._built

    @property
    def snapshot_cid(self) -> str | None:
        return self._snapshot_cid

    @property
    def projection_cids(self) -> tuple[str, ...]:
        return self._projection_cids

    @property
    def vector_cids(self) -> tuple[str, ...]:
        return self._vector_cids

    @property
    def capabilities(self) -> tuple[ProjectionBackendCapability, ...]:
        return self._capabilities

    @property
    def exact_raw_source_fallback_permitted(self) -> bool:
        return True

    @property
    def authoritative(self) -> bool:
        return False

    @property
    def rebuildable(self) -> bool:
        return True

    def backend_artifact(self) -> ProjectionIndexBackendArtifact:
        snapshot = self._snapshot_cid or cid_for_bytes(b"unbuilt-projection-index", "raw")
        path = None
        if self._artifact_dir is not None:
            path = str(self._artifact_path())
        return ProjectionIndexBackendArtifact(
            kind=self._backend_kind,
            snapshot_cid=snapshot,
            path=path,
            native_module=self._native_module,
        )

    def _artifact_path(self) -> Path:
        if self._artifact_dir is None:
            raise ProjectionIndexAdmissionError("no artifact_dir configured")
        return (
            self._artifact_dir
            / f"projection-index-{self.manifest_cid}.rebuildable.json"
        )

    def _require_profile(
        self,
        *,
        model_cid: str | None,
        tokenizer_cid: str | None = None,
        preprocessing_profile_cid: str | None = None,
        dimension: int | None = None,
        dtype: str | None = None,
        byte_order: str | None = None,
        metric: str | None = None,
    ) -> None:
        identity = self._manifest.identity
        if model_cid is not None and model_cid != identity.model_cid:
            raise ProjectionModelUnavailable(
                "model_unavailable: query model_cid is not pinned to this index"
            )
        if tokenizer_cid is not None and tokenizer_cid != identity.tokenizer_cid:
            raise ProjectionModelUnavailable(
                "model_unavailable: query tokenizer_cid is not pinned to this index"
            )
        if (
            preprocessing_profile_cid is not None
            and preprocessing_profile_cid != identity.preprocessing_profile_cid
        ):
            raise ProjectionModelUnavailable(
                "model_unavailable: query preprocessor is not pinned to this index"
            )
        if dimension is not None and dimension != identity.dimension:
            raise ProjectionIndexAdmissionError(
                "dimension mismatch against index manifest"
            )
        if dtype is not None and dtype != identity.dtype:
            raise ProjectionIndexAdmissionError("dtype mismatch against index manifest")
        if byte_order is not None and byte_order != identity.byte_order:
            raise ProjectionIndexAdmissionError(
                "byte_order mismatch against index manifest"
            )
        if metric is not None and metric != identity.metric:
            raise ProjectionIndexAdmissionError("metric mismatch against index manifest")

    def _iter_matching_records(
        self, projection_cids: Sequence[str] | None
    ) -> tuple[ProjectionRecord, ...]:
        wanted: set[str] | None = None
        if projection_cids is not None:
            wanted = set(projection_cids)
        found: list[ProjectionRecord] = []
        seen: set[str] = set()
        if wanted is not None:
            for cid in projection_cids or ():
                record = self._store.get_verified_projection_record(cid)
                if not projection_matches_manifest(record, self._manifest):
                    raise ProjectionIndexAdmissionError(
                        "projection does not match index manifest profile"
                    )
                if record.projection_cid in seen:
                    continue
                seen.add(record.projection_cid)
                found.append(record)
            missing = wanted - seen
            if missing:
                raise VerifiedSemanticStoreNotFound(
                    f"rebuild projection_cids are not stored: {sorted(missing)}"
                )
            return tuple(sorted(found, key=lambda item: item.projection_cid))

        blocks_dir = self._store.store.blocks_dir
        if not blocks_dir.is_dir():
            return ()
        for path in sorted(blocks_dir.glob("*/*.json")):
            storage_cid = path.stem
            try:
                block = self._store.get_verified_block(storage_cid)
            except VerifiedSemanticStoreError:
                continue
            if block.get("kind") != "projection_record":
                continue
            try:
                record = self._store.get_verified_projection_record(
                    str(block["identity_cid"])
                )
            except VerifiedSemanticStoreError:
                continue
            if not projection_matches_manifest(record, self._manifest):
                continue
            if record.projection_cid in seen:
                continue
            seen.add(record.projection_cid)
            found.append(record)
        return tuple(sorted(found, key=lambda item: item.projection_cid))

    def _write_rebuildable_artifact(
        self,
        *,
        snapshot_cid: str,
        projection_cids: Sequence[str],
        vector_cids: Sequence[str],
    ) -> Path | None:
        if self._artifact_dir is None:
            return None
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": PROJECTION_INDEX_ARTIFACT_SCHEMA,
            "interface_id": PROJECTION_INDEX_INTERFACE,
            "manifest_cid": self.manifest_cid,
            "snapshot_cid": snapshot_cid,
            "projection_cids": list(projection_cids),
            "vector_cids": list(vector_cids),
            "backend_kind": self._backend_kind,
            "rebuildable": True,
            "authoritative": False,
            "canonical_graph": False,
        }
        path = self._artifact_path()
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(encoded)
        tmp.replace(path)
        return path

    def rebuild(
        self,
        projection_cids: Sequence[str] | None = None,
        *,
        records: Sequence[ProjectionRecord] | None = None,
    ) -> ProjectionIndexRebuildReceipt:
        """Rebuild the search artifact from verified projection records.

        Backend files/state are discarded and reconstructed.  The canonical
        identity remains the stored projection records plus the index manifest.
        """

        if self._backend_kind == "graph":
            if self._graph_projection_type is not GraphProjection:
                raise ProjectionBackendUnavailable(
                    "index_unavailable: graph backend wrap is missing; "
                    "exact/raw-source fallback is permitted"
                )
            raise ProjectionBackendUnavailable(
                "index_unavailable: graph backend is a rebuildable wrap only and "
                "cannot serve similarity search; exact/raw-source fallback is permitted"
            )
        if records is not None:
            admitted: list[ProjectionRecord] = []
            seen: set[str] = set()
            for record in records:
                if not isinstance(record, ProjectionRecord):
                    raise ProjectionIndexAdmissionError(
                        "rebuild records must be ProjectionRecord values"
                    )
                loaded = self._store.get_verified_projection_record(record.projection_cid)
                if loaded.projection_cid != record.projection_cid:
                    raise ProjectionIndexIntegrityError(
                        "rebuild record CID does not rehash"
                    )
                if not projection_matches_manifest(loaded, self._manifest):
                    raise ProjectionIndexAdmissionError(
                        "projection does not match index manifest profile"
                    )
                if loaded.projection_cid in seen:
                    continue
                seen.add(loaded.projection_cid)
                admitted.append(loaded)
            matching = tuple(sorted(admitted, key=lambda item: item.projection_cid))
        else:
            matching = self._iter_matching_records(projection_cids)

        staged: dict[str, tuple[ProjectionRecord, CanonicalVectorBytes]] = {}
        vector_records: list[VectorRecord] = []
        projection_ids: list[str] = []
        vector_ids: list[str] = []
        for record in matching:
            vector = self._store.get_verified_vector(record.identity.vector_cid)
            if vector.bytes_cid != record.identity.vector_cid:
                raise ProjectionIndexIntegrityError(
                    "projection vector_cid does not rehash stored packed bytes"
                )
            if (
                vector.dimension != record.identity.dimension
                or vector.dtype != record.identity.dtype
                or vector.byte_order != record.identity.byte_order
            ):
                raise ProjectionIndexAdmissionError(
                    "stored vector profile does not match projection identity"
                )
            floats = vector_as_floats(vector)
            metadata = {
                "projection_cid": record.projection_cid,
                "vector_cid": vector.bytes_cid,
                "subject_cid": record.identity.subject_cid,
            }
            _reject_score_or_document_identity(metadata, path="index_record")
            vector_records.append(
                VectorRecord(
                    record_id=record.projection_cid,
                    vector=floats,
                    metadata=metadata,
                    identity=self._vector_identity,
                )
            )
            staged[record.projection_cid] = (record, vector)
            projection_ids.append(record.projection_cid)
            vector_ids.append(vector.bytes_cid)

        if self._engine is None:
            raise ProjectionBackendUnavailable(
                "index_unavailable: no rebuildable vector backend is bound"
            )
        try:
            self._engine.rebuild(vector_records, identity=self._vector_identity)
        except VectorIdentityMismatchError as exc:
            raise ProjectionModelUnavailable(
                f"model_unavailable: vector engine identity mismatch: {exc}"
            ) from exc
        except VectorIndexError as exc:
            raise ProjectionIndexAdmissionError(str(exc)) from exc
        if self._hybrid is not None:
            self._hybrid = HybridRetriever(
                self._engine, lexical_search=self._lexical_search
            )

        snapshot = snapshot_cid_for(
            manifest_cid=self.manifest_cid,
            projection_cids=projection_ids,
            vector_cids=vector_ids,
        )
        path = self._write_rebuildable_artifact(
            snapshot_cid=snapshot,
            projection_cids=projection_ids,
            vector_cids=vector_ids,
        )
        self._records = staged
        self._projection_cids = tuple(projection_ids)
        self._vector_cids = tuple(vector_ids)
        self._snapshot_cid = snapshot
        self._built = True
        backend = ProjectionIndexBackendArtifact(
            kind=self._backend_kind,
            snapshot_cid=snapshot,
            path=None if path is None else str(path),
            native_module=self._native_module,
        )
        return ProjectionIndexRebuildReceipt(
            snapshot_cid=snapshot,
            manifest_cid=self.manifest_cid,
            projection_cids=self._projection_cids,
            vector_cids=self._vector_cids,
            backend=backend,
            created=True,
            reason_code="rebuilt",
        )

    def drop_backend(self) -> None:
        """Discard rebuildable backend state.  Verified records remain."""

        engine_error: Exception | None = None
        if self._engine is not None:
            try:
                self._engine.rebuild((), identity=self._vector_identity)
            except VectorIndexError as exc:
                engine_error = exc
        self._records = {}
        self._projection_cids = ()
        self._vector_cids = ()
        self._snapshot_cid = None
        self._built = False
        if self._artifact_dir is not None:
            path = self._artifact_path()
            if path.is_file():
                path.unlink()
        if engine_error is not None:
            raise ProjectionIndexAdmissionError(str(engine_error)) from engine_error

    def _admit_query(
        self,
        query: CanonicalVectorBytes | Sequence[Any] | str,
        *,
        model_cid: str | None,
        tokenizer_cid: str | None = None,
        preprocessing_profile_cid: str | None = None,
        k: int,
    ) -> tuple[tuple[float, ...], CanonicalVectorBytes]:
        if self._backend_kind == "graph":
            raise ProjectionBackendUnavailable(
                "index_unavailable: graph backend cannot serve similarity search; "
                "exact/raw-source fallback is permitted"
            )
        if not self._built or self._engine is None:
            raise ProjectionIndexUnavailable(
                "index_unavailable: projection index has not been rebuilt; "
                "exact/raw-source fallback is permitted"
            )
        if type(k) is not int or isinstance(k, bool) or k < 1 or k > MAX_QUERY_K:
            raise ProjectionIndexAdmissionError(
                f"k must be an integer in 1..{MAX_QUERY_K}"
            )
        identity = self._manifest.identity
        try:
            if isinstance(query, str):
                vector = self._store.get_verified_vector(query)
            elif isinstance(query, CanonicalVectorBytes):
                vector = pack_canonical_vector(
                    query.packed_bytes,
                    dtype=query.dtype,
                    byte_order=query.byte_order,
                    dimension=query.dimension,
                )
                if vector.bytes_cid != query.bytes_cid:
                    raise ProjectionIndexIntegrityError(
                        "query vector CID does not rehash packed bytes"
                    )
            else:
                vector = pack_canonical_vector(
                    query,
                    dtype=identity.dtype,
                    byte_order=identity.byte_order,
                    dimension=identity.dimension,
                )
        except ProjectionIndexError:
            raise
        except SemanticWorldArtifactAdmissionError as exc:
            raise ProjectionIndexAdmissionError(str(exc)) from exc
        except VerifiedSemanticStoreNotFound as exc:
            raise ProjectionIndexError(
                f"query vector is not stored; exact/raw-source fallback is permitted: {exc}"
            ) from exc
        except VerifiedSemanticStoreIntegrityError as exc:
            raise ProjectionIndexIntegrityError(
                f"query vector CID does not rehash: {exc}"
            ) from exc
        except SemanticWorldArtifactError as exc:
            raise ProjectionIndexError(str(exc)) from exc
        self._require_profile(
            model_cid=model_cid,
            tokenizer_cid=tokenizer_cid,
            preprocessing_profile_cid=preprocessing_profile_cid,
            dimension=vector.dimension,
            dtype=vector.dtype,
            byte_order=vector.byte_order,
        )
        return vector_as_floats(vector), vector

    def search_hits(
        self,
        query: CanonicalVectorBytes | Sequence[Any] | str,
        *,
        k: int = DEFAULT_QUERY_K,
        model_cid: str | None = None,
        tokenizer_cid: str | None = None,
        preprocessing_profile_cid: str | None = None,
        text_query: str = "",
        filters: Mapping[str, Any] | None = None,
    ) -> tuple[ProjectionCandidate, ...]:
        """Return unresolved advisory hits.  Not for use until resolved."""

        floats, _query_vector = self._admit_query(
            query,
            model_cid=model_cid,
            tokenizer_cid=tokenizer_cid,
            preprocessing_profile_cid=preprocessing_profile_cid,
            k=k,
        )
        hits: Sequence[VectorSearchResult]
        try:
            if self._backend_kind == "hybrid" and self._hybrid is not None:
                response: HybridSearchResponse = self._hybrid.search(
                    floats,
                    text_query=text_query,
                    k=k,
                    filters=filters,
                    identity=self._vector_identity,
                )
                if response.authoritative is not False:
                    raise ProjectionIndexIntegrityError(
                        "hybrid retrieval claimed authority"
                    )
                ordered: list[VectorSearchResult] = []
                for item in response.results:
                    if item.authoritative is not False:
                        raise ProjectionIndexIntegrityError(
                            "hybrid retrieval claimed authority"
                        )
                    record = self._records.get(item.document_id)
                    if record is None:
                        continue
                    ordered.append(
                        VectorSearchResult(
                            item.document_id,
                            item.score,
                            {
                                "projection_cid": record[0].projection_cid,
                                "vector_cid": record[0].identity.vector_cid,
                                "subject_cid": record[0].identity.subject_cid,
                            },
                        )
                    )
                hits = tuple(ordered)
            else:
                if self._engine is None:
                    raise ProjectionBackendUnavailable(
                        "index_unavailable: no rebuildable vector backend is bound; "
                        "exact/raw-source fallback is permitted"
                    )
                hits = self._engine.search(
                    floats, k, filters=filters, identity=self._vector_identity
                )
        except ProjectionIndexError:
            raise
        except VectorIdentityMismatchError as exc:
            raise ProjectionModelUnavailable(
                f"model_unavailable: query identity is not pinned to this index: {exc}"
            ) from exc
        except (VectorIndexError, HybridRetrievalError) as exc:
            raise ProjectionIndexError(str(exc)) from exc

        candidates: list[ProjectionCandidate] = []
        for hit in hits:
            record_pair = self._records.get(hit.record_id)
            if record_pair is None:
                continue
            record, vector = record_pair
            candidates.append(
                ProjectionCandidate(
                    projection_cid=record.projection_cid,
                    score=hit.score,
                    manifest_cid=self.manifest_cid,
                    model_cid=record.identity.model_cid,
                    tokenizer_cid=record.identity.tokenizer_cid,
                    preprocessing_profile_cid=record.identity.preprocessing_profile_cid,
                    vector_cid=vector.bytes_cid,
                    claimed_subject_cid=record.identity.subject_cid,
                    backend_kind=self._backend_kind,
                )
            )
        return tuple(candidates)

    def search(
        self,
        query: CanonicalVectorBytes | Sequence[Any] | str,
        *,
        k: int = DEFAULT_QUERY_K,
        model_cid: str | None = None,
        tokenizer_cid: str | None = None,
        preprocessing_profile_cid: str | None = None,
        text_query: str = "",
        filters: Mapping[str, Any] | None = None,
        resolver: Any | None = None,
        resolve: bool = True,
    ) -> Any:
        """Search this rebuildable index.  Hits are resolved before use by default."""

        return search_projection_index(
            self,
            query,
            k=k,
            model_cid=model_cid,
            tokenizer_cid=tokenizer_cid,
            preprocessing_profile_cid=preprocessing_profile_cid,
            text_query=text_query,
            filters=filters,
            resolver=resolver,
            resolve=resolve,
        )


def rebuild_projection_index(
    index: ProjectionIndex,
    projection_cids: Sequence[str] | None = None,
    *,
    records: Sequence[ProjectionRecord] | None = None,
) -> ProjectionIndexRebuildReceipt:
    """Public rebuild entry point.  Backend artifacts remain non-authoritative."""

    if not isinstance(index, ProjectionIndex) and getattr(
        type(index), "__name__", ""
    ) != "ProjectionIndex":
        raise ProjectionIndexAdmissionError("index must be a ProjectionIndex")
    return index.rebuild(projection_cids, records=records)


def search_projection_index(
    index: ProjectionIndex,
    query: CanonicalVectorBytes | Sequence[Any] | str,
    *,
    k: int = DEFAULT_QUERY_K,
    model_cid: str | None = None,
    tokenizer_cid: str | None = None,
    preprocessing_profile_cid: str | None = None,
    text_query: str = "",
    filters: Mapping[str, Any] | None = None,
    resolver: Any | None = None,
    resolve: bool = True,
) -> Any:
    """Search a rebuildable index and, by default, resolve every hit before use.

    Unresolved candidates are never returned as usable results when
    ``resolve=True`` (the default).  Similarity scores remain advisory.
    """

    if not isinstance(index, ProjectionIndex) and getattr(
        type(index), "__name__", ""
    ) != "ProjectionIndex":
        raise ProjectionIndexAdmissionError("index must be a ProjectionIndex")
    hits = index.search_hits(
        query,
        k=k,
        model_cid=model_cid,
        tokenizer_cid=tokenizer_cid,
        preprocessing_profile_cid=preprocessing_profile_cid,
        text_query=text_query,
        filters=filters,
    )
    if not resolve:
        return hits
    from ipfs_kit_py.semantic_world_store.resolver import (
        ExactProjectionResolver,
        resolve_projection_hits,
    )

    active = resolver
    if active is None:
        active = ExactProjectionResolver(index.store, index=index)
    return resolve_projection_hits(active, hits, index=index)


__all__ = [
    "ADVISORY_LIMITATIONS",
    "PROJECTION_CANDIDATE_INTERFACE",
    "PROJECTION_INDEX_INTERFACE",
    "PROJECTION_INDEX_MANIFEST_INTERFACE",
    "ProjectionBackendCapability",
    "ProjectionBackendUnavailable",
    "ProjectionCandidate",
    "ProjectionIndex",
    "ProjectionIndexAdmissionError",
    "ProjectionIndexBackendArtifact",
    "ProjectionIndexError",
    "ProjectionIndexIntegrityError",
    "ProjectionIndexRebuildReceipt",
    "ProjectionIndexUnavailable",
    "ProjectionModelUnavailable",
    "native_ann_available",
    "probe_projection_backends",
    "projection_matches_manifest",
    "rebuild_projection_index",
    "search_projection_index",
    "snapshot_cid_for",
    "unpack_canonical_vector",
    "vector_as_floats",
]
