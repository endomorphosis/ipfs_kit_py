"""Exact projection resolver: rehash ANN candidates before use.

``ExactProjectionResolver`` consumes advisory ``ProjectionCandidate`` hits and
returns ``ResolvedProjectionCandidate`` values only after the full
manifest → projection → vector → object → domain → freshness → environment
chain re-verifies against current immutable blocks.

Authority rules (normative, fail-closed):

* Similarity never becomes authority or exact reuse.
* Score is ranking metadata and is excluded from identity.
* Corrupt present blocks fail closed and never surface as resolved hits.
* Missing or stale candidates are rejected, not used.
* The resolver does not decide semantic relations, admission, or completion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar, Final, Iterable, Mapping, NoReturn, Sequence

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    SemanticObjectEnvelope,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    cid_for_bytes,
)
from ipfs_kit_py.semantic_world_store.artifacts import CanonicalVectorBytes
from ipfs_kit_py.semantic_world_store.projections import (
    ADVISORY_LIMITATIONS,
    PROJECTION_INDEX_INTERFACE,
    ProjectionCandidate,
    ProjectionIndex,
    ProjectionIndexAdmissionError,
    ProjectionIndexError,
    ProjectionIndexIntegrityError,
    ProjectionIndexUnavailable,
)
from ipfs_kit_py.semantic_world_store.verified_store import (
    ProjectionIndexManifest,
    ProjectionRecord,
    VerifiedSemanticBlockStore,
    VerifiedSemanticStoreError,
    VerifiedSemanticStoreIntegrityError,
    VerifiedSemanticStoreNotFound,
)

_VERIFIED_STORE_INTERFACE: Final[str] = "VerifiedSemanticStore@1"
_VERIFIED_STORE_METHODS: Final[tuple[str, ...]] = (
    "get_verified_projection_record",
    "get_verified_vector",
    "get_verified_semantic_object",
    "get_verified_projection_index_manifest",
)
_MISSING_STORE_ERRORS: Final[frozenset[str]] = frozenset(
    {
        "VerifiedSemanticStoreNotFound",
        "SemanticWorldArtifactNotFound",
    }
)
_INTEGRITY_STORE_ERRORS: Final[frozenset[str]] = frozenset(
    {
        "VerifiedSemanticStoreIntegrityError",
        "SemanticWorldArtifactIntegrityError",
        "ProjectionIndexIntegrityError",
    }
)


PROJECTION_RESOLVER_INTERFACE: Final[str] = "ProjectionResolver@1"
RESOLVED_PROJECTION_CANDIDATE_INTERFACE: Final[str] = "ResolvedProjectionCandidate@1"

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


class ProjectionResolverError(ProjectionIndexError):
    """Base error for exact projection resolution."""

    reason_code: ClassVar[str] = "projection_resolver_error"


class ProjectionResolverAdmissionError(
    ProjectionResolverError, ProjectionIndexAdmissionError
):
    """Raised when a candidate cannot be admitted for resolution."""

    reason_code: ClassVar[str] = "projection_resolver_admission_error"


class ProjectionCandidateStale(ProjectionResolverError):
    """Candidate no longer matches the current manifest/store generation."""

    reason_code: ClassVar[str] = "stale_projection_candidate"


class ProjectionCandidateMissing(ProjectionResolverError):
    """Candidate CID is absent from verified storage."""

    reason_code: ClassVar[str] = "missing_projection_candidate"


class ProjectionCandidateCorrupt(ProjectionResolverError, ProjectionIndexIntegrityError):
    """Present candidate bytes do not rehash.  Fail closed."""

    reason_code: ClassVar[str] = "corrupt_projection_candidate"


def _is_verified_semantic_store(store: object) -> bool:
    """True for ``VerifiedSemanticBlockStore``, including after module reload."""

    if isinstance(store, VerifiedSemanticBlockStore):
        return True
    if getattr(store, "INTERFACE", None) != _VERIFIED_STORE_INTERFACE:
        return False
    return all(callable(getattr(store, name, None)) for name in _VERIFIED_STORE_METHODS)


def _reraise_verified_lookup(exc: BaseException, *, cid: str, kind: str) -> NoReturn:
    """Map store lookup failures across module-identity boundaries."""

    if isinstance(exc, (ProjectionCandidateMissing, ProjectionCandidateCorrupt)):
        raise exc
    name = type(exc).__name__
    if isinstance(exc, VerifiedSemanticStoreNotFound) or name in _MISSING_STORE_ERRORS:
        if kind == "projection":
            raise ProjectionCandidateMissing(
                f"missing_projection_candidate: {cid}"
            ) from exc
        raise ProjectionCandidateMissing(
            f"missing_projection_candidate: {kind} {cid}"
        ) from exc
    if (
        isinstance(exc, VerifiedSemanticStoreIntegrityError)
        or name in _INTEGRITY_STORE_ERRORS
    ):
        raise ProjectionCandidateCorrupt(
            f"corrupt_projection_candidate: {kind} {cid} does not rehash"
        ) from exc
    raise exc


def _reject_score_or_document_identity(payload: Mapping[str, Any], *, path: str) -> None:
    extra = set(payload) & _SCORE_IDENTITY_FIELDS
    if extra:
        raise ProjectionResolverAdmissionError(
            f"{path} rejects score-derived identity fields {sorted(extra)}"
        )
    extra_docs = set(payload) & _MUTABLE_DOCUMENT_FIELDS
    if extra_docs:
        raise ProjectionResolverAdmissionError(
            f"{path} rejects mutable unresolved document identity {sorted(extra_docs)}"
        )


@dataclass(frozen=True, slots=True)
class ProjectionResolutionRejection:
    """Typed rejection of an ANN hit that must not be used."""

    projection_cid: str
    reason_code: str
    detail: str
    authoritative: bool = False
    exact_reuse: bool = False

    def __post_init__(self) -> None:
        if self.authoritative is not False or self.exact_reuse is not False:
            raise ProjectionResolverAdmissionError(
                "rejections cannot confer authority or exact reuse"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_cid": self.projection_cid,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "authoritative": False,
            "exact_reuse": False,
        }


@dataclass(frozen=True, slots=True)
class ResolvedProjectionCandidate:
    """ResolvedProjectionCandidate@1: rehashed, still non-authoritative hit.

    Identity is the resolved semantic/state CID plus the verified projection
    and manifest profiles.  ``score`` is advisory ranking only.
    """

    projection_cid: str
    resolved_subject_cid: str
    score: float
    manifest_cid: str
    model_cid: str
    tokenizer_cid: str
    preprocessing_profile_cid: str
    normalization_profile_cid: str
    vector_cid: str
    domain: Mapping[str, Any]
    freshness: Mapping[str, Any]
    environment_binding_cid: str | None
    resolution_chain: Mapping[str, Any]
    limitations: tuple[str, ...] = ADVISORY_LIMITATIONS
    authoritative: bool = False
    exact_reuse: bool = False
    resolved: bool = True

    SCHEMA: ClassVar[str] = (
        "ipfs-kit.semantic-world-store.resolved-projection-candidate@1"
    )
    INTERFACE: ClassVar[str] = RESOLVED_PROJECTION_CANDIDATE_INTERFACE

    def __post_init__(self) -> None:
        for name in (
            "projection_cid",
            "resolved_subject_cid",
            "manifest_cid",
            "model_cid",
            "tokenizer_cid",
            "preprocessing_profile_cid",
            "normalization_profile_cid",
            "vector_cid",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise ProjectionResolverAdmissionError(
                    f"{name} must be a non-empty string"
                )
        if self.environment_binding_cid is not None and (
            type(self.environment_binding_cid) is not str
            or not self.environment_binding_cid
        ):
            raise ProjectionResolverAdmissionError(
                "environment_binding_cid must be a CID or None"
            )
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise ProjectionResolverAdmissionError("score must be a finite number")
        if not math.isfinite(float(self.score)):
            raise ProjectionResolverAdmissionError("score must be a finite number")
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "limitations", tuple(self.limitations))
        object.__setattr__(self, "domain", MappingProxyType(dict(self.domain)))
        object.__setattr__(self, "freshness", MappingProxyType(dict(self.freshness)))
        object.__setattr__(
            self, "resolution_chain", MappingProxyType(dict(self.resolution_chain))
        )
        if self.authoritative is not False:
            raise ProjectionResolverAdmissionError(
                "resolved ANN candidates are non-authoritative; "
                "similarity never becomes authority"
            )
        if self.exact_reuse is not False:
            raise ProjectionResolverAdmissionError(
                "similarity never becomes exact reuse"
            )
        if self.resolved is not True:
            raise ProjectionResolverAdmissionError(
                "ResolvedProjectionCandidate must be marked resolved"
            )
        if not self.limitations:
            raise ProjectionResolverAdmissionError(
                "resolved candidates must declare limitations"
            )
        _reject_score_or_document_identity(self.domain, path="domain")
        _reject_score_or_document_identity(self.freshness, path="freshness")
        _reject_score_or_document_identity(
            self.resolution_chain, path="resolution_chain"
        )

    def identity_payload(self) -> dict[str, Any]:
        """Canonical identity: no score, rank, or similarity fields."""

        payload = {
            "schema": self.SCHEMA,
            "projection_cid": self.projection_cid,
            "resolved_subject_cid": self.resolved_subject_cid,
            "manifest_cid": self.manifest_cid,
            "model_cid": self.model_cid,
            "tokenizer_cid": self.tokenizer_cid,
            "preprocessing_profile_cid": self.preprocessing_profile_cid,
            "normalization_profile_cid": self.normalization_profile_cid,
            "vector_cid": self.vector_cid,
            "domain": dict(self.domain),
            "freshness": dict(self.freshness),
            "environment_binding_cid": self.environment_binding_cid,
            "authoritative": False,
            "exact_reuse": False,
            "resolved": True,
        }
        _reject_score_or_document_identity(payload, path="resolved_projection_candidate")
        return payload

    def to_dict(self) -> dict[str, Any]:
        payload = self.identity_payload()
        payload["score"] = self.score
        payload["limitations"] = list(self.limitations)
        payload["resolution_chain"] = dict(self.resolution_chain)
        return payload


@dataclass(frozen=True, slots=True)
class ProjectionSearchResponse:
    """Search results after every ANN candidate has been resolved or rejected."""

    results: tuple[ResolvedProjectionCandidate, ...]
    rejected: tuple[ProjectionResolutionRejection, ...]
    manifest_cid: str
    snapshot_cid: str | None
    backend_kind: str
    limitations: tuple[str, ...] = ADVISORY_LIMITATIONS
    authoritative: bool = False
    exact_reuse: bool = False
    exact_raw_source_fallback_permitted: bool = True
    reason_code: str = "ok"

    INTERFACE: ClassVar[str] = PROJECTION_RESOLVER_INTERFACE

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", tuple(self.results))
        object.__setattr__(self, "rejected", tuple(self.rejected))
        object.__setattr__(self, "limitations", tuple(self.limitations))
        if self.authoritative is not False:
            raise ProjectionResolverAdmissionError(
                "search responses are non-authoritative"
            )
        if self.exact_reuse is not False:
            raise ProjectionResolverAdmissionError(
                "search responses are not exact reuse"
            )
        if any(item.authoritative is not False for item in self.results):
            raise ProjectionResolverAdmissionError(
                "resolved hits cannot claim authority"
            )
        if any(item.exact_reuse is not False for item in self.results):
            raise ProjectionResolverAdmissionError(
                "resolved hits cannot claim exact reuse"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [item.to_dict() for item in self.results],
            "rejected": [item.to_dict() for item in self.rejected],
            "manifest_cid": self.manifest_cid,
            "snapshot_cid": self.snapshot_cid,
            "backend_kind": self.backend_kind,
            "limitations": list(self.limitations),
            "authoritative": False,
            "exact_reuse": False,
            "exact_raw_source_fallback_permitted": True,
            "reason_code": self.reason_code,
        }


def _domain_from_object(envelope: SemanticObjectEnvelope) -> dict[str, Any]:
    domain: dict[str, Any] = {
        "repository_id": envelope.repository_id,
        "language": envelope.language,
        "kind": envelope.kind,
        "logical_name": envelope.logical_name,
        "source_cid": envelope.source_cid,
        "declaration_cid": envelope.declaration_cid,
    }
    metadata = dict(envelope.metadata)
    _reject_score_or_document_identity(metadata, path="semantic_object.metadata")
    domain_state_cid = metadata.get("domain_state_cid")
    if type(domain_state_cid) is str and domain_state_cid:
        domain["domain_state_cid"] = domain_state_cid
    return domain


def _freshness_from_record(
    record: ProjectionRecord,
    *,
    snapshot_cid: str | None,
    in_current_generation: bool,
) -> dict[str, Any]:
    policy = record.identity.availability_policy
    available = policy == "available" and in_current_generation
    return {
        "availability_policy": policy,
        "privacy_class": record.identity.privacy_class,
        "in_current_index_generation": in_current_generation,
        "index_snapshot_cid": snapshot_cid,
        "fresh": available,
        "stale": not in_current_generation,
    }


class ExactProjectionResolver:
    """ProjectionResolver@1: exact CID resolution of advisory ANN candidates."""

    INTERFACE: ClassVar[str] = PROJECTION_RESOLVER_INTERFACE

    def __init__(
        self,
        store: VerifiedSemanticBlockStore,
        *,
        index: ProjectionIndex | None = None,
        manifest: ProjectionIndexManifest | None = None,
    ) -> None:
        if not _is_verified_semantic_store(store):
            raise TypeError("store must be a VerifiedSemanticBlockStore")
        self._store = store
        self._index = index
        if manifest is not None:
            self._manifest = manifest
        elif index is not None:
            self._manifest = index.manifest
        else:
            self._manifest = None

    @property
    def store(self) -> VerifiedSemanticBlockStore:
        return self._store

    @property
    def index(self) -> ProjectionIndex | None:
        return self._index

    @property
    def interface_id(self) -> str:
        return self.INTERFACE

    def _current_manifest(
        self, candidate: ProjectionCandidate
    ) -> ProjectionIndexManifest:
        if self._manifest is not None:
            if self._manifest.projection_index_manifest_cid != candidate.manifest_cid:
                raise ProjectionCandidateStale(
                    "stale_projection_candidate: candidate manifest_cid does not "
                    "match the resolver index generation"
                )
        try:
            return self._store.get_verified_projection_index_manifest(
                candidate.manifest_cid
            )
        except Exception as exc:
            _reraise_verified_lookup(
                exc, cid=candidate.manifest_cid, kind="manifest"
            )

    def _load_projection(self, projection_cid: str) -> ProjectionRecord:
        try:
            record = self._store.get_verified_projection_record(projection_cid)
        except Exception as exc:
            _reraise_verified_lookup(exc, cid=projection_cid, kind="projection")
        if record.projection_cid != projection_cid:
            raise ProjectionCandidateCorrupt(
                "corrupt_projection_candidate: projection CID does not rehash"
            )
        if record.identity.authoritative:
            raise ProjectionResolverAdmissionError(
                "projections are non-authoritative"
            )
        return record

    def _load_vector(self, vector_cid: str) -> CanonicalVectorBytes:
        try:
            vector = self._store.get_verified_vector(vector_cid)
        except Exception as exc:
            _reraise_verified_lookup(exc, cid=vector_cid, kind="vector")
        recomputed = cid_for_bytes(vector.packed_bytes, "raw")
        if vector.bytes_cid != vector_cid or recomputed != vector_cid:
            raise ProjectionCandidateCorrupt(
                "corrupt_projection_candidate: vector CID does not rehash packed bytes"
            )
        return vector

    def _load_object(self, subject_cid: str) -> SemanticObjectEnvelope:
        try:
            envelope = self._store.get_verified_semantic_object(subject_cid)
        except Exception as exc:
            _reraise_verified_lookup(exc, cid=subject_cid, kind="subject")
        if envelope.semantic_object_cid != subject_cid:
            raise ProjectionCandidateCorrupt(
                "corrupt_projection_candidate: subject CID does not rehash"
            )
        return envelope

    def resolve(
        self,
        candidate: ProjectionCandidate | Mapping[str, Any] | str,
        *,
        score: float | None = None,
    ) -> ResolvedProjectionCandidate:
        """Resolve one ANN candidate: load, rehash, bind profiles, refuse authority."""

        if isinstance(candidate, str):
            if self._manifest is None:
                raise ProjectionResolverAdmissionError(
                    "resolving a projection CID requires a bound index manifest"
                )
            record = self._load_projection(candidate)
            bound_score = 0.0 if score is None else float(score)
            candidate = ProjectionCandidate(
                projection_cid=record.projection_cid,
                score=bound_score,
                manifest_cid=self._manifest.projection_index_manifest_cid,
                model_cid=record.identity.model_cid,
                tokenizer_cid=record.identity.tokenizer_cid,
                preprocessing_profile_cid=record.identity.preprocessing_profile_cid,
                vector_cid=record.identity.vector_cid,
                claimed_subject_cid=record.identity.subject_cid,
                backend_kind=(
                    self._index.backend_kind if self._index is not None else "exact"
                ),
            )
        elif isinstance(candidate, Mapping):
            _reject_score_or_document_identity(
                {key: value for key, value in candidate.items() if key != "score"},
                path="projection_candidate",
            )
            candidate = ProjectionCandidate(
                projection_cid=str(candidate["projection_cid"]),
                score=float(candidate["score"]),
                manifest_cid=str(candidate["manifest_cid"]),
                model_cid=str(candidate["model_cid"]),
                tokenizer_cid=str(candidate["tokenizer_cid"]),
                preprocessing_profile_cid=str(candidate["preprocessing_profile_cid"]),
                vector_cid=str(candidate["vector_cid"]),
                claimed_subject_cid=str(candidate["claimed_subject_cid"]),
                backend_kind=str(candidate.get("backend_kind", "exact")),
            )
        elif not isinstance(candidate, ProjectionCandidate):
            if getattr(type(candidate), "__name__", "") != "ProjectionCandidate":
                raise ProjectionResolverAdmissionError(
                    "candidate must be a ProjectionCandidate, mapping, or CID"
                )
            candidate = ProjectionCandidate(
                projection_cid=str(candidate.projection_cid),
                score=float(candidate.score if score is None else score),
                manifest_cid=str(candidate.manifest_cid),
                model_cid=str(candidate.model_cid),
                tokenizer_cid=str(candidate.tokenizer_cid),
                preprocessing_profile_cid=str(candidate.preprocessing_profile_cid),
                vector_cid=str(candidate.vector_cid),
                claimed_subject_cid=str(candidate.claimed_subject_cid),
                backend_kind=str(getattr(candidate, "backend_kind", "exact")),
                authoritative=bool(getattr(candidate, "authoritative", False)),
                resolved=bool(getattr(candidate, "resolved", False)),
            )

        if candidate.authoritative is not False or candidate.resolved is not False:
            raise ProjectionResolverAdmissionError(
                "candidate is not an advisory unresolved ANN hit"
            )

        manifest = self._current_manifest(candidate)
        if manifest.projection_index_manifest_cid != candidate.manifest_cid:
            raise ProjectionCandidateCorrupt(
                "corrupt_projection_candidate: manifest CID does not rehash"
            )
        if manifest.identity.authoritative:
            raise ProjectionResolverAdmissionError("index manifests are non-authoritative")
        if not manifest.identity.rebuildable:
            raise ProjectionResolverAdmissionError("index manifests must be rebuildable")

        record = self._load_projection(candidate.projection_cid)
        if record.projection_cid != candidate.projection_cid:
            raise ProjectionCandidateCorrupt(
                "corrupt_projection_candidate: projection CID does not rehash"
            )
        if record.identity.model_cid != candidate.model_cid:
            raise ProjectionCandidateStale(
                "stale_projection_candidate: model_cid does not match stored projection"
            )
        if record.identity.tokenizer_cid != candidate.tokenizer_cid:
            raise ProjectionCandidateStale(
                "stale_projection_candidate: tokenizer_cid does not match stored projection"
            )
        if record.identity.preprocessing_profile_cid != candidate.preprocessing_profile_cid:
            raise ProjectionCandidateStale(
                "stale_projection_candidate: preprocessor does not match stored projection"
            )
        if record.identity.vector_cid != candidate.vector_cid:
            raise ProjectionCandidateStale(
                "stale_projection_candidate: vector_cid does not match stored projection"
            )
        if record.identity.subject_cid != candidate.claimed_subject_cid:
            raise ProjectionCandidateStale(
                "stale_projection_candidate: subject_cid does not match stored projection"
            )
        if (
            record.identity.model_cid != manifest.identity.model_cid
            or record.identity.tokenizer_cid != manifest.identity.tokenizer_cid
            or record.identity.preprocessing_profile_cid
            != manifest.identity.preprocessing_profile_cid
            or record.identity.projection_kind != manifest.identity.projection_kind
            or record.identity.dimension != manifest.identity.dimension
            or record.identity.metric != manifest.identity.metric
            or record.identity.dtype != manifest.identity.dtype
            or record.identity.byte_order != manifest.identity.byte_order
        ):
            raise ProjectionCandidateStale(
                "stale_projection_candidate: projection no longer matches index manifest"
            )

        vector = self._load_vector(record.identity.vector_cid)
        if (
            vector.dimension != record.identity.dimension
            or vector.dtype != record.identity.dtype
            or vector.byte_order != record.identity.byte_order
        ):
            raise ProjectionCandidateCorrupt(
                "corrupt_projection_candidate: stored vector profile does not match projection"
            )

        envelope = self._load_object(record.identity.subject_cid)
        domain = _domain_from_object(envelope)
        in_generation = True
        snapshot_cid = None
        if self._index is not None:
            snapshot_cid = self._index.snapshot_cid
            if self._index.built:
                in_generation = candidate.projection_cid in self._index.projection_cids
            if not in_generation:
                raise ProjectionCandidateStale(
                    "stale_projection_candidate: not in the current index generation"
                )
        freshness = _freshness_from_record(
            record,
            snapshot_cid=snapshot_cid,
            in_current_generation=in_generation,
        )
        chain = {
            "manifest_cid": manifest.projection_index_manifest_cid,
            "projection_cid": record.projection_cid,
            "vector_cid": vector.bytes_cid,
            "object_cid": envelope.semantic_object_cid,
            "domain": dict(domain),
            "freshness": dict(freshness),
            "environment_binding_cid": envelope.environment_binding_cid,
        }
        _reject_score_or_document_identity(chain, path="resolution_chain")
        return ResolvedProjectionCandidate(
            projection_cid=record.projection_cid,
            resolved_subject_cid=envelope.semantic_object_cid,
            score=candidate.score,
            manifest_cid=manifest.projection_index_manifest_cid,
            model_cid=record.identity.model_cid,
            tokenizer_cid=record.identity.tokenizer_cid,
            preprocessing_profile_cid=record.identity.preprocessing_profile_cid,
            normalization_profile_cid=record.identity.normalization_profile_cid,
            vector_cid=vector.bytes_cid,
            domain=domain,
            freshness=freshness,
            environment_binding_cid=envelope.environment_binding_cid,
            resolution_chain=chain,
        )

    def resolve_many(
        self, candidates: Iterable[ProjectionCandidate | Mapping[str, Any] | str]
    ) -> tuple[tuple[ResolvedProjectionCandidate, ...], tuple[ProjectionResolutionRejection, ...]]:
        """Resolve a batch.  Corrupt present-blocks fail closed; missing/stale reject."""

        resolved: list[ResolvedProjectionCandidate] = []
        rejected: list[ProjectionResolutionRejection] = []
        for candidate in candidates:
            cid = (
                candidate.projection_cid
                if isinstance(candidate, ProjectionCandidate)
                or getattr(type(candidate), "__name__", "") == "ProjectionCandidate"
                else candidate.get("projection_cid")
                if isinstance(candidate, Mapping)
                else str(candidate)
            )
            try:
                resolved.append(self.resolve(candidate))
            except ProjectionCandidateCorrupt:
                raise
            except VerifiedSemanticStoreIntegrityError as exc:
                raise ProjectionCandidateCorrupt(str(exc)) from exc
            except (
                ProjectionCandidateStale,
                ProjectionCandidateMissing,
                ProjectionResolverAdmissionError,
                VerifiedSemanticStoreError,
            ) as exc:
                reason = getattr(exc, "reason_code", "rejected_projection_candidate")
                rejected.append(
                    ProjectionResolutionRejection(
                        projection_cid=str(cid),
                        reason_code=str(reason),
                        detail=str(exc),
                    )
                )
        return tuple(resolved), tuple(rejected)


def resolve_projection_candidate(
    resolver: ExactProjectionResolver | VerifiedSemanticBlockStore,
    candidate: ProjectionCandidate | Mapping[str, Any] | str,
    *,
    index: ProjectionIndex | None = None,
    score: float | None = None,
) -> ResolvedProjectionCandidate:
    """Public exact-resolution entry point.  Rehashes before the candidate may be used."""

    if _is_verified_semantic_store(resolver):
        active = ExactProjectionResolver(resolver, index=index)
    elif isinstance(resolver, ExactProjectionResolver) or getattr(
        type(resolver), "__name__", ""
    ) == "ExactProjectionResolver":
        active = resolver
    else:
        raise ProjectionResolverAdmissionError(
            "resolver must be ExactProjectionResolver or VerifiedSemanticBlockStore"
        )
    return active.resolve(candidate, score=score)


def resolve_projection_hits(
    resolver: ExactProjectionResolver,
    hits: Sequence[ProjectionCandidate],
    *,
    index: ProjectionIndex | None = None,
) -> ProjectionSearchResponse:
    """Resolve every ANN hit.  Only rehashed candidates are returned for use."""

    if not isinstance(resolver, ExactProjectionResolver) and getattr(
        type(resolver), "__name__", ""
    ) != "ExactProjectionResolver":
        raise ProjectionResolverAdmissionError(
            "resolver must be ExactProjectionResolver"
        )
    bound_index = index if index is not None else resolver.index
    results, rejected = resolver.resolve_many(hits)
    manifest_cid = ""
    snapshot_cid = None
    backend_kind = "exact"
    if bound_index is not None:
        manifest_cid = bound_index.manifest_cid
        snapshot_cid = bound_index.snapshot_cid
        backend_kind = bound_index.backend_kind
    elif results:
        manifest_cid = results[0].manifest_cid
    elif hits:
        manifest_cid = hits[0].manifest_cid
        backend_kind = hits[0].backend_kind
    return ProjectionSearchResponse(
        results=results,
        rejected=rejected,
        manifest_cid=manifest_cid,
        snapshot_cid=snapshot_cid,
        backend_kind=backend_kind,
        exact_raw_source_fallback_permitted=True,
        reason_code="ok",
    )


__all__ = [
    "PROJECTION_INDEX_INTERFACE",
    "PROJECTION_RESOLVER_INTERFACE",
    "RESOLVED_PROJECTION_CANDIDATE_INTERFACE",
    "ExactProjectionResolver",
    "ProjectionCandidateCorrupt",
    "ProjectionCandidateMissing",
    "ProjectionCandidateStale",
    "ProjectionResolutionRejection",
    "ProjectionResolverAdmissionError",
    "ProjectionResolverError",
    "ProjectionSearchResponse",
    "ResolvedProjectionCandidate",
    "resolve_projection_candidate",
    "resolve_projection_hits",
    "ProjectionIndexUnavailable",
]
