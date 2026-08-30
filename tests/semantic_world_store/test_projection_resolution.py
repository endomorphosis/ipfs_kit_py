"""Fail-closed vectors for projection indexes and exact resolution."""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    ProjectionIdentity,
    ProjectionIndexManifestIdentity,
    SemanticObjectEnvelope,
    SemanticObjectKind,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_bytes,
)
from ipfs_kit_py.semantic_world_store.artifacts import (
    CanonicalVectorBytes,
    pack_canonical_vector,
)
from ipfs_kit_py.semantic_world_store.projections import (
    ADVISORY_LIMITATIONS,
    PROJECTION_CANDIDATE_INTERFACE,
    PROJECTION_INDEX_INTERFACE,
    ProjectionBackendUnavailable,
    ProjectionCandidate,
    ProjectionIndex,
    ProjectionIndexAdmissionError,
    ProjectionIndexBackendArtifact,
    ProjectionIndexUnavailable,
    ProjectionModelUnavailable,
    native_ann_available,
    probe_projection_backends,
    rebuild_projection_index,
    search_projection_index,
    snapshot_cid_for,
    unpack_canonical_vector,
)
from ipfs_kit_py.semantic_world_store.resolver import (
    PROJECTION_RESOLVER_INTERFACE,
    RESOLVED_PROJECTION_CANDIDATE_INTERFACE,
    ExactProjectionResolver,
    ProjectionCandidateCorrupt,
    ProjectionCandidateMissing,
    ProjectionCandidateStale,
    ProjectionSearchResponse,
    ResolvedProjectionCandidate,
    resolve_projection_candidate,
)
from ipfs_kit_py.semantic_world_store.verified_store import (
    PROJECTION_INDEX_MANIFEST_INTERFACE,
    ProjectionIndexManifest,
    ProjectionRecord,
    VerifiedSemanticBlockStore,
    VerifiedSemanticStoreIntegrityError,
)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _source_cid(label: str) -> str:
    return cid_for_bytes(label.encode("utf-8"), "raw")


def _envelope(**overrides: Any) -> SemanticObjectEnvelope:
    fields: dict[str, Any] = {
        "kind": SemanticObjectKind.SYMBOL,
        "language": "python",
        "repository_id": "repo:example",
        "logical_name": "pkg.mod.answer",
        "declaration_cid": _source_cid("declaration"),
        "source_cid": _source_cid("source"),
        "environment_binding_cid": _source_cid("env-binding"),
        "metadata": {"domain_state_cid": _source_cid("domain-state")},
    }
    fields.update(overrides)
    return SemanticObjectEnvelope(**fields)


def _vector_values(dimension: int = 4, offset: float = 0.0) -> list[float]:
    return [float(index + 1) + offset for index in range(dimension)]


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "semantic-world-store"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def verified(coordination: DurableCoordinationStore) -> VerifiedSemanticBlockStore:
    store = VerifiedSemanticBlockStore(coordination)
    yield store
    store.close()


def _put_subject_and_vector(
    verified: VerifiedSemanticBlockStore,
    *,
    logical_name: str = "pkg.mod.answer",
    dimension: int = 4,
    values: list[Any] | None = None,
    operation_suffix: str = "1",
) -> tuple[SemanticObjectEnvelope, CanonicalVectorBytes]:
    envelope = _envelope(logical_name=logical_name)
    verified.put_semantic_object(envelope, operation_id=f"op-subject-{operation_suffix}")
    packed = verified.put_vector_bytes(
        values if values is not None else _vector_values(dimension),
        dtype="float32",
        byte_order="little",
        dimension=dimension,
        operation_id=f"op-vector-{operation_suffix}",
    )
    vector = verified.get_verified_vector(packed.cid)
    return envelope, vector


def _projection_record(
    envelope: SemanticObjectEnvelope,
    vector: CanonicalVectorBytes,
    **overrides: Any,
) -> ProjectionRecord:
    fields: dict[str, Any] = {
        "subject_cid": envelope.semantic_object_cid,
        "subject_kind": "semantic_object",
        "projection_kind": "embedding",
        "model_cid": _source_cid("model-a"),
        "tokenizer_cid": _source_cid("tokenizer-a"),
        "preprocessing_profile_cid": _source_cid("preproc-a"),
        "normalization_profile_cid": _source_cid("norm-a"),
        "dimension": vector.dimension,
        "metric": "cosine",
        "dtype": vector.dtype,
        "byte_order": vector.byte_order,
        "quantization_profile_cid": None,
        "vector_cid": vector.bytes_cid,
        "privacy_class": "internal",
        "availability_policy": "available",
        "authoritative": False,
    }
    fields.update(overrides)
    return ProjectionRecord.from_payload(ProjectionIdentity(**fields).to_dict())


def _manifest_for(
    envelope: SemanticObjectEnvelope,
    vector: CanonicalVectorBytes,
    **overrides: Any,
) -> ProjectionIndexManifest:
    fields: dict[str, Any] = {
        "projection_kind": "embedding",
        "model_cid": _source_cid("model-a"),
        "tokenizer_cid": _source_cid("tokenizer-a"),
        "preprocessing_profile_cid": _source_cid("preproc-a"),
        "dimension": vector.dimension,
        "metric": "cosine",
        "dtype": vector.dtype,
        "byte_order": vector.byte_order,
        "source_cid": envelope.semantic_object_cid,
        "schema_ids": ["program-identity@1"],
    }
    fields.update(overrides)
    return ProjectionIndexManifest.from_identity(ProjectionIndexManifestIdentity(**fields))


def _seed_index(
    verified: VerifiedSemanticBlockStore,
    *,
    backend: str = "exact",
    artifact_dir: Path | None = None,
    count: int = 2,
    label: str = "default",
) -> tuple[ProjectionIndex, list[ProjectionRecord], CanonicalVectorBytes]:
    records: list[ProjectionRecord] = []
    query_vector: CanonicalVectorBytes | None = None
    first_envelope: SemanticObjectEnvelope | None = None
    first_vector: CanonicalVectorBytes | None = None
    for index in range(count):
        envelope, vector = _put_subject_and_vector(
            verified,
            logical_name=f"pkg.mod.{label}_symbol_{index}",
            values=_vector_values(4, offset=float(index)),
            operation_suffix=f"{label}-{index + 1}",
        )
        record = _projection_record(envelope, vector)
        verified.put_projection_record(record, operation_id=f"op-proj-{label}-{index + 1}")
        records.append(record)
        if index == 0:
            first_envelope = envelope
            first_vector = vector
            query_vector = vector
    assert first_envelope is not None and first_vector is not None and query_vector is not None
    manifest = _manifest_for(first_envelope, first_vector)
    verified.put_projection_index_manifest(manifest, operation_id=f"op-manifest-{label}")
    index = ProjectionIndex(
        verified, manifest, backend=backend, artifact_dir=artifact_dir
    )
    rebuild_projection_index(
        index, [item.projection_cid for item in records]
    )
    return index, records, query_vector


# ---------------------------------------------------------------------------
# Cold import, interfaces, wrap GraphRAG, no second CID engine
# ---------------------------------------------------------------------------


def test_cold_import_of_declared_modules() -> None:
    saved = {
        name: module
        for name, module in sys.modules.items()
        if "semantic_world_store" in name
    }
    try:
        for name in saved:
            del sys.modules[name]
        projections_mod = importlib.import_module(
            "ipfs_kit_py.semantic_world_store.projections"
        )
        resolver_mod = importlib.import_module(
            "ipfs_kit_py.semantic_world_store.resolver"
        )
        assert projections_mod.PROJECTION_INDEX_INTERFACE == "ProjectionIndex@1"
        assert projections_mod.ProjectionIndex.__name__ == "ProjectionIndex"
        assert projections_mod.ProjectionCandidate.__name__ == "ProjectionCandidate"
        assert resolver_mod.ExactProjectionResolver.__name__ == "ExactProjectionResolver"
        assert resolver_mod.ResolvedProjectionCandidate.__name__ == "ResolvedProjectionCandidate"
        assert callable(projections_mod.search_projection_index)
        assert callable(projections_mod.rebuild_projection_index)
        assert callable(resolver_mod.resolve_projection_candidate)
    finally:
        for name in list(sys.modules):
            if "semantic_world_store" in name:
                del sys.modules[name]
        sys.modules.update(saved)


def test_module_interfaces_are_versioned() -> None:
    assert PROJECTION_INDEX_INTERFACE == "ProjectionIndex@1"
    assert PROJECTION_CANDIDATE_INTERFACE == "ProjectionCandidate@1"
    assert PROJECTION_RESOLVER_INTERFACE == "ProjectionResolver@1"
    assert RESOLVED_PROJECTION_CANDIDATE_INTERFACE == "ResolvedProjectionCandidate@1"
    assert PROJECTION_INDEX_MANIFEST_INTERFACE == "ProjectionIndexManifest@1"
    assert ProjectionIndex.INTERFACE == "ProjectionIndex@1"
    assert ExactProjectionResolver.INTERFACE == "ProjectionResolver@1"
    assert ProjectionCandidate.INTERFACE == "ProjectionCandidate@1"
    assert ResolvedProjectionCandidate.INTERFACE == "ResolvedProjectionCandidate@1"


def test_wraps_landed_graphrag_backends_not_a_second_engine() -> None:
    projections_source = Path(inspect.getsourcefile(ProjectionIndex)).read_text(
        encoding="utf-8"
    )
    resolver_source = Path(inspect.getsourcefile(ExactProjectionResolver)).read_text(
        encoding="utf-8"
    )
    assert "from ipfs_kit_py.graphrag.vector_index import" in projections_source
    assert "ExactVectorIndex" in projections_source
    assert "ANNVectorIndex" in projections_source
    assert "HybridRetriever" in projections_source
    for source in (projections_source, resolver_source):
        assert "from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import" in source
        assert "def _varint" not in source
        assert "base64.b32encode" not in source
        assert "multihash.digest" not in source
        assert "hashlib.sha256" not in source
    assert "cid_for_artifact" in projections_source
    assert "cid_for_bytes" in projections_source


def test_capability_probe_types_native_ann_without_importing_it() -> None:
    capabilities = {item.kind: item for item in probe_projection_backends()}
    for kind in ("exact", "ann", "hybrid", "graph"):
        assert capabilities[kind].available is True
        assert capabilities[kind].authoritative is False
        assert capabilities[kind].rebuildable is True
        assert capabilities[kind].canonical_graph is False
    for kind in ("faiss", "hnswlib", "annoy"):
        assert kind in capabilities
        if not capabilities[kind].available:
            assert capabilities[kind].reason_code == "native_ann_unavailable"
    assert native_ann_available() is any(
        capabilities[kind].available for kind in ("faiss", "hnswlib", "annoy")
    )


# ---------------------------------------------------------------------------
# Rebuild + search + resolve happy path
# ---------------------------------------------------------------------------


def test_rebuild_is_deterministic_and_backend_is_rebuildable(
    verified: VerifiedSemanticBlockStore, tmp_path: Path
) -> None:
    artifact_dir = tmp_path / "index-artifacts"
    index, records, _query = _seed_index(
        verified, artifact_dir=artifact_dir
    )
    first = index.snapshot_cid
    assert first is not None
    recomputed = snapshot_cid_for(
        manifest_cid=index.manifest_cid,
        projection_cids=index.projection_cids,
        vector_cids=tuple(
            next(
                record.identity.vector_cid
                for record in records
                if record.projection_cid == cid
            )
            for cid in index.projection_cids
        ),
    )
    assert first == recomputed
    sidecar = artifact_dir / f"projection-index-{index.manifest_cid}.rebuildable.json"
    assert sidecar.is_file()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["rebuildable"] is True
    assert payload["authoritative"] is False
    assert payload["canonical_graph"] is False
    assert payload["snapshot_cid"] == first

    second = rebuild_projection_index(
        index, [item.projection_cid for item in records]
    )
    assert second.snapshot_cid == first
    assert second.backend.rebuildable is True
    assert second.backend.authoritative is False
    assert second.backend.canonical_graph is False
    assert second.authoritative is False

    index.drop_backend()
    assert index.built is False
    assert not sidecar.is_file()
    restored = rebuild_projection_index(
        index, [item.projection_cid for item in records]
    )
    assert restored.snapshot_cid == first


def test_search_resolves_and_rehashes_before_use(
    verified: VerifiedSemanticBlockStore,
) -> None:
    index, records, query = _seed_index(verified)
    response = search_projection_index(index, query, k=2)
    assert isinstance(response, ProjectionSearchResponse)
    assert response.authoritative is False
    assert response.exact_reuse is False
    assert response.exact_raw_source_fallback_permitted is True
    assert response.reason_code == "ok"
    assert response.results
    top = response.results[0]
    assert top.projection_cid == records[0].projection_cid
    assert top.resolved_subject_cid == records[0].identity.subject_cid
    assert top.resolved is True
    assert top.authoritative is False
    assert top.exact_reuse is False
    assert top.manifest_cid == index.manifest_cid
    assert top.model_cid == records[0].identity.model_cid
    assert top.vector_cid == records[0].identity.vector_cid
    chain = top.resolution_chain
    for key in (
        "manifest_cid",
        "projection_cid",
        "vector_cid",
        "object_cid",
        "domain",
        "freshness",
        "environment_binding_cid",
    ):
        assert key in chain
    assert chain["object_cid"] == top.resolved_subject_cid
    assert chain["environment_binding_cid"] == _source_cid("env-binding")
    assert top.domain["repository_id"] == "repo:example"
    assert top.domain["domain_state_cid"] == _source_cid("domain-state")
    assert top.environment_binding_cid == _source_cid("env-binding")
    assert top.freshness["availability_policy"] == "available"
    assert top.freshness["fresh"] is True
    assert "score" not in top.identity_payload()
    assert all(item in top.limitations for item in ADVISORY_LIMITATIONS)


def test_advisory_flag_is_forced_on_candidates_and_responses(
    verified: VerifiedSemanticBlockStore,
) -> None:
    index, records, query = _seed_index(verified)
    hits = search_projection_index(index, query, k=2, resolve=False)
    assert hits
    for hit in hits:
        assert hit.authoritative is False
        assert hit.resolved is False
        assert "score" not in hit.identity_payload()
        with pytest.raises(ProjectionIndexAdmissionError, match="non-authoritative"):
            ProjectionCandidate(
                projection_cid=hit.projection_cid,
                score=hit.score,
                manifest_cid=hit.manifest_cid,
                model_cid=hit.model_cid,
                tokenizer_cid=hit.tokenizer_cid,
                preprocessing_profile_cid=hit.preprocessing_profile_cid,
                vector_cid=hit.vector_cid,
                claimed_subject_cid=hit.claimed_subject_cid,
                backend_kind=hit.backend_kind,
                authoritative=True,
            )
    resolved = resolve_projection_candidate(
        ExactProjectionResolver(verified, index=index), hits[0]
    )
    assert resolved.authoritative is False
    assert resolved.exact_reuse is False
    with pytest.raises(Exception, match="exact reuse|non-authoritative|authority"):
        ResolvedProjectionCandidate(
            projection_cid=resolved.projection_cid,
            resolved_subject_cid=resolved.resolved_subject_cid,
            score=resolved.score,
            manifest_cid=resolved.manifest_cid,
            model_cid=resolved.model_cid,
            tokenizer_cid=resolved.tokenizer_cid,
            preprocessing_profile_cid=resolved.preprocessing_profile_cid,
            normalization_profile_cid=resolved.normalization_profile_cid,
            vector_cid=resolved.vector_cid,
            domain=dict(resolved.domain),
            freshness=dict(resolved.freshness),
            environment_binding_cid=resolved.environment_binding_cid,
            resolution_chain=dict(resolved.resolution_chain),
            authoritative=True,
        )


def test_score_is_not_identity(verified: VerifiedSemanticBlockStore) -> None:
    index, records, query = _seed_index(verified, count=1)
    hit = search_projection_index(index, query, k=1, resolve=False)[0]
    other = ProjectionCandidate(
        projection_cid=hit.projection_cid,
        score=hit.score + 12.5,
        manifest_cid=hit.manifest_cid,
        model_cid=hit.model_cid,
        tokenizer_cid=hit.tokenizer_cid,
        preprocessing_profile_cid=hit.preprocessing_profile_cid,
        vector_cid=hit.vector_cid,
        claimed_subject_cid=hit.claimed_subject_cid,
        backend_kind=hit.backend_kind,
    )
    assert other.identity_payload() == hit.identity_payload()
    assert other.score != hit.score
    first = resolve_projection_candidate(
        ExactProjectionResolver(verified, index=index), hit
    )
    second = resolve_projection_candidate(
        ExactProjectionResolver(verified, index=index), other
    )
    assert first.identity_payload() == second.identity_payload()
    assert first.projection_cid == records[0].projection_cid
    assert "score" not in first.identity_payload()
    assert "similarity" not in first.identity_payload()


def test_ann_and_hybrid_backends_remain_advisory(
    verified: VerifiedSemanticBlockStore,
) -> None:
    for backend in ("ann", "hybrid"):
        index, _records, query = _seed_index(
            verified, backend=backend, count=2, label=backend
        )
        response = search_projection_index(index, query, k=2)
        assert response.backend_kind == backend
        assert response.authoritative is False
        assert response.results
        assert all(item.authoritative is False for item in response.results)
        assert all(item.exact_reuse is False for item in response.results)
        assert all(item.resolved is True for item in response.results)


def test_graph_backend_is_typed_unavailable_not_similarity_authority(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope, vector = _put_subject_and_vector(verified)
    record = _projection_record(envelope, vector)
    verified.put_projection_record(record)
    manifest = _manifest_for(envelope, vector)
    verified.put_projection_index_manifest(manifest)
    index = ProjectionIndex(verified, manifest, backend="graph")
    with pytest.raises(ProjectionBackendUnavailable, match="index_unavailable"):
        rebuild_projection_index(index, [record.projection_cid])
    with pytest.raises(ProjectionBackendUnavailable, match="exact/raw-source fallback"):
        search_projection_index(index, vector, k=1)
    assert index.exact_raw_source_fallback_permitted is True
    loaded = verified.get_verified_semantic_object(envelope.semantic_object_cid)
    assert loaded.semantic_object_cid == envelope.semantic_object_cid


# ---------------------------------------------------------------------------
# Unavailable / stale / corrupt / missing
# ---------------------------------------------------------------------------


def test_unbuilt_index_is_typed_unavailable(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope, vector = _put_subject_and_vector(verified)
    record = _projection_record(envelope, vector)
    verified.put_projection_record(record)
    manifest = _manifest_for(envelope, vector)
    verified.put_projection_index_manifest(manifest)
    index = ProjectionIndex(verified, manifest)
    assert index.built is False
    with pytest.raises(ProjectionIndexUnavailable, match="index_unavailable"):
        search_projection_index(index, vector, k=1)
    assert index.exact_raw_source_fallback_permitted is True
    exact = verified.get_verified_projection_record(record.projection_cid)
    assert exact.projection_cid == record.projection_cid


def test_model_mismatch_is_typed_unavailable(
    verified: VerifiedSemanticBlockStore,
) -> None:
    index, _records, query = _seed_index(verified, count=1)
    with pytest.raises(ProjectionModelUnavailable, match="model_unavailable"):
        search_projection_index(
            index, query, k=1, model_cid=_source_cid("some-other-model")
        )


def test_missing_candidate_is_rejected_not_used(
    verified: VerifiedSemanticBlockStore,
) -> None:
    index, records, query = _seed_index(verified, count=1)
    ghost = ProjectionCandidate(
        projection_cid=_source_cid("missing-projection"),
        score=0.99,
        manifest_cid=index.manifest_cid,
        model_cid=records[0].identity.model_cid,
        tokenizer_cid=records[0].identity.tokenizer_cid,
        preprocessing_profile_cid=records[0].identity.preprocessing_profile_cid,
        vector_cid=records[0].identity.vector_cid,
        claimed_subject_cid=records[0].identity.subject_cid,
        backend_kind="exact",
    )
    resolver = ExactProjectionResolver(verified, index=index)
    with pytest.raises(ProjectionCandidateMissing, match="missing_projection_candidate"):
        resolver.resolve(ghost)
    response = resolver.resolve_many([ghost])
    assert response[0] == ()
    assert response[1][0].reason_code == "missing_projection_candidate"
    assert response[1][0].authoritative is False
    assert response[1][0].exact_reuse is False
    live = search_projection_index(index, query, k=1)
    assert live.results[0].projection_cid == records[0].projection_cid


def test_stale_candidate_is_rejected(
    verified: VerifiedSemanticBlockStore,
) -> None:
    index, records, query = _seed_index(verified, count=2)
    omitted = records[1]
    rebuild_projection_index(index, [records[0].projection_cid])
    stale = ProjectionCandidate(
        projection_cid=omitted.projection_cid,
        score=0.5,
        manifest_cid=index.manifest_cid,
        model_cid=omitted.identity.model_cid,
        tokenizer_cid=omitted.identity.tokenizer_cid,
        preprocessing_profile_cid=omitted.identity.preprocessing_profile_cid,
        vector_cid=omitted.identity.vector_cid,
        claimed_subject_cid=omitted.identity.subject_cid,
        backend_kind="exact",
    )
    resolver = ExactProjectionResolver(verified, index=index)
    with pytest.raises(ProjectionCandidateStale, match="stale_projection_candidate"):
        resolver.resolve(stale)
    live = search_projection_index(index, query, k=2)
    assert [item.projection_cid for item in live.results] == [records[0].projection_cid]


def test_corrupt_present_candidate_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    index, records, query = _seed_index(verified, count=1)
    stored = verified.get_verified_block(records[0].projection_cid)
    path = verified.store._block_path(stored["storage_cid"])
    path.write_bytes(b'{"schema":"tampered","kind":"projection_record","payload":{}}')
    hits = index.search_hits(query, k=1)
    assert hits
    resolver = ExactProjectionResolver(verified, index=index)
    with pytest.raises((ProjectionCandidateCorrupt, VerifiedSemanticStoreIntegrityError)):
        resolver.resolve(hits[0])
    with pytest.raises((ProjectionCandidateCorrupt, VerifiedSemanticStoreIntegrityError)):
        resolver.resolve_many(hits)


def test_similarity_never_becomes_authority_or_exact_reuse(
    verified: VerifiedSemanticBlockStore,
) -> None:
    index, records, query = _seed_index(verified, count=2)
    response = search_projection_index(index, query, k=2)
    assert response.authoritative is False
    assert response.exact_reuse is False
    for item in response.results:
        assert item.authoritative is False
        assert item.exact_reuse is False
        payload = item.identity_payload()
        assert payload["authoritative"] is False
        assert payload["exact_reuse"] is False
        assert payload["resolved_subject_cid"] == item.resolved_subject_cid
        assert item.score != item.resolved_subject_cid
        assert item.score != item.projection_cid
    near = response.results[0]
    far = response.results[-1]
    assert near.projection_cid != far.projection_cid or len(response.results) == 1
    assert near.identity_payload()["projection_cid"] == records[0].projection_cid


def test_backend_artifact_rejects_canonical_or_authoritative_claims() -> None:
    snapshot = cid_for_bytes(b"snapshot", "raw")
    with pytest.raises(ProjectionIndexAdmissionError, match="canonical graph"):
        ProjectionIndexBackendArtifact(
            kind="ann",
            snapshot_cid=snapshot,
            canonical_graph=True,
        )
    with pytest.raises(ProjectionIndexAdmissionError, match="non-authoritative"):
        ProjectionIndexBackendArtifact(
            kind="ann",
            snapshot_cid=snapshot,
            authoritative=True,
        )
    with pytest.raises(ProjectionIndexAdmissionError, match="rebuildable"):
        ProjectionIndexBackendArtifact(
            kind="ann",
            snapshot_cid=snapshot,
            rebuildable=False,
        )


def test_unpack_rehashes_canonical_bytes() -> None:
    vector = pack_canonical_vector(
        [1.0, 2.0, 3.0, 4.0], dtype="float32", byte_order="little", dimension=4
    )
    values = unpack_canonical_vector(vector)
    assert values == pytest.approx((1.0, 2.0, 3.0, 4.0))
    forged = CanonicalVectorBytes(
        dtype=vector.dtype,
        byte_order=vector.byte_order,
        dimension=vector.dimension,
        packed_bytes=vector.packed_bytes,
    )
    # CanonicalVectorBytes recomputes bytes_cid from packed bytes, so a
    # matching payload still rehashes.  Identity remains the raw CID.
    assert forged.bytes_cid == vector.bytes_cid == cid_for_bytes(vector.packed_bytes, "raw")


def test_public_resolve_function_rehashes(
    verified: VerifiedSemanticBlockStore,
) -> None:
    index, records, query = _seed_index(verified, count=1)
    hit = search_projection_index(index, query, k=1, resolve=False)[0]
    resolved = resolve_projection_candidate(verified, hit, index=index)
    assert resolved.projection_cid == records[0].projection_cid
    assert resolved.resolved_subject_cid == records[0].identity.subject_cid
    again = resolve_projection_candidate(
        ExactProjectionResolver(verified, index=index),
        records[0].projection_cid,
        score=hit.score,
    )
    assert again.identity_payload()["projection_cid"] == resolved.projection_cid


def test_query_vector_cid_is_rehashed_before_search(
    verified: VerifiedSemanticBlockStore,
) -> None:
    index, records, query = _seed_index(verified, count=1)
    response = search_projection_index(index, query.bytes_cid, k=1)
    assert response.results[0].projection_cid == records[0].projection_cid
    missing = cid_for_bytes(b"absent-query-vector", "raw")
    with pytest.raises(Exception):
        search_projection_index(index, missing, k=1)
