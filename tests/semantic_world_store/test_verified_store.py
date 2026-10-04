"""Fail-closed vectors for kit verified semantic and projection storage."""

from __future__ import annotations

import importlib
import inspect
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any

import pytest

from ipfs_datasets_py.logic.software_contracts.content import cid_for_bytes as datasets_cid_for_bytes
from ipfs_datasets_py.logic.software_contracts.semantic_state.program_identity import (
    PROJECTION_REQUIRED_FIELDS,
    ProgramIdentityError,
    ProjectionIdentity,
    ProjectionIndexManifestIdentity,
    SemanticObjectEnvelope,
    SemanticObjectKind,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes,
)
from ipfs_kit_py.semantic_world_store.artifacts import (
    ADMITTED_BYTE_ORDERS,
    ARTIFACT_MODULE_INTERFACE,
    ARTIFACT_SCHEMA_VERSION,
    MAX_ARTIFACT_BYTES,
    STORED_ARTIFACT_INTERFACE,
    STORED_ARTIFACT_SCHEMA,
    CanonicalVectorBytes,
    SemanticWorldArtifactAdmissionError,
    SemanticWorldArtifactConflictError,
    SemanticWorldArtifactIntegrityError,
    SemanticWorldArtifactKind,
    SemanticWorldArtifactStore,
    admit_sealed_record,
    cid_for_semantic_world_artifact,
    pack_canonical_vector,
    reject_private_raw_source,
    seal_semantic_world_artifact,
    validate_stored_artifact_schema,
)
from ipfs_kit_py.semantic_world_store.verified_store import (
    PROJECTION_INDEX_MANIFEST_INTERFACE,
    PROJECTION_RECORD_INTERFACE,
    VERIFIED_SEMANTIC_STORE_INTERFACE,
    ProjectionIndexManifest,
    ProjectionRecord,
    VerifiedSemanticBlockStore,
    VerifiedSemanticStore,
    VerifiedSemanticStoreAdmissionError,
    VerifiedSemanticStoreIntegrityError,
    VerifiedSemanticStoreNotFound,
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
        "environment_binding_cid": None,
        "metadata": {},
    }
    fields.update(overrides)
    return SemanticObjectEnvelope(**fields)


def _vector_values(dimension: int = 4) -> list[float]:
    return [float(index + 1) for index in range(dimension)]


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "semantic-world-store"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def artifacts(coordination: DurableCoordinationStore) -> SemanticWorldArtifactStore:
    store = SemanticWorldArtifactStore(coordination)
    yield store
    store.close()


@pytest.fixture()
def verified(artifacts: SemanticWorldArtifactStore) -> VerifiedSemanticBlockStore:
    store = VerifiedSemanticBlockStore(artifacts)
    yield store
    store.close()


def _put_subject_and_vector(
    verified: VerifiedSemanticBlockStore,
    *,
    dimension: int = 4,
    dtype: str = "float32",
    byte_order: str = "little",
    values: list[Any] | None = None,
) -> tuple[SemanticObjectEnvelope, CanonicalVectorBytes]:
    envelope = _envelope()
    verified.put_semantic_object(envelope, operation_id="op-subject-1")
    packed = verified.put_vector_bytes(
        values if values is not None else _vector_values(dimension),
        dtype=dtype,
        byte_order=byte_order,
        dimension=dimension,
        operation_id="op-vector-1",
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


# ---------------------------------------------------------------------------
# Cold import, interfaces, no second CID/engine
# ---------------------------------------------------------------------------


def test_cold_import_of_declared_modules() -> None:
    for name in list(sys.modules):
        if "semantic_world_store" in name:
            del sys.modules[name]
    artifacts_mod = importlib.import_module(
        "ipfs_kit_py.semantic_world_store.artifacts"
    )
    verified_mod = importlib.import_module(
        "ipfs_kit_py.semantic_world_store.verified_store"
    )
    assert artifacts_mod.ARTIFACT_MODULE_INTERFACE == "SemanticWorldArtifactStore@1"
    assert artifacts_mod.SemanticWorldArtifactStore.__name__ == "SemanticWorldArtifactStore"
    assert verified_mod.VERIFIED_SEMANTIC_STORE_INTERFACE == "VerifiedSemanticStore@1"
    assert verified_mod.VerifiedSemanticBlockStore.__name__ == "VerifiedSemanticBlockStore"
    assert verified_mod.ProjectionRecord.__name__ == "ProjectionRecord"
    assert verified_mod.ProjectionIndexManifest.__name__ == "ProjectionIndexManifest"
    assert verified_mod.VerifiedSemanticStore is verified_mod.VerifiedSemanticBlockStore
    assert verified_mod.PROJECTION_RECORD_INTERFACE == "ProjectionRecord@1"
    assert verified_mod.PROJECTION_INDEX_MANIFEST_INTERFACE == "ProjectionIndexManifest@1"


def test_module_interfaces_are_versioned() -> None:
    assert ARTIFACT_MODULE_INTERFACE == "SemanticWorldArtifactStore@1"
    assert VERIFIED_SEMANTIC_STORE_INTERFACE == "VerifiedSemanticStore@1"
    assert PROJECTION_RECORD_INTERFACE == "ProjectionRecord@1"
    assert PROJECTION_INDEX_MANIFEST_INTERFACE == "ProjectionIndexManifest@1"
    assert VerifiedSemanticBlockStore.INTERFACE == "VerifiedSemanticStore@1"
    assert STORED_ARTIFACT_INTERFACE == "SemanticWorldStoredArtifact@1"
    assert STORED_ARTIFACT_SCHEMA.endswith(f"@{ARTIFACT_SCHEMA_VERSION}")
    assert MAX_ARTIFACT_BYTES == 1_048_576
    assert VerifiedSemanticStore is VerifiedSemanticBlockStore


def test_no_second_cid_or_storage_engine() -> None:
    artifacts_source = Path(inspect.getsourcefile(SemanticWorldArtifactStore)).read_text(
        encoding="utf-8"
    )
    verified_source = Path(inspect.getsourcefile(VerifiedSemanticBlockStore)).read_text(
        encoding="utf-8"
    )
    for source in (artifacts_source, verified_source):
        assert "from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import" in source
        assert "DurableCoordinationStore" in source
        assert "def _varint" not in source
        assert "base64.b32encode" not in source
        assert "multihash.digest" not in source
        assert "hashlib.sha256" not in source
    assert "cid_for_bytes" in artifacts_source
    assert "cid_for_artifact" in artifacts_source
    assert "class SemanticWorldArtifactStore" in artifacts_source
    assert "sqlite3.connect" in artifacts_source
    assert _OPS_DB_IS_INDEX_ONLY(artifacts_source)
    assert "SemanticWorldArtifactStore" in verified_source
    assert "ProjectionIdentity" in verified_source


def _OPS_DB_IS_INDEX_ONLY(source: str) -> bool:
    return (
        "semantic_world_artifact_index.sqlite3" in source
        and "identity_bindings" in source
        and "CREATE TABLE IF NOT EXISTS artifacts" not in source
    )


def test_store_composes_injected_coordination_engine(
    coordination: DurableCoordinationStore,
    artifacts: SemanticWorldArtifactStore,
) -> None:
    assert artifacts.store is coordination
    vector = pack_canonical_vector(
        [1.0, 2.0], dtype="float32", byte_order="little", dimension=2
    )
    result = artifacts.put_vector_bytes(
        vector.packed_bytes,
        dtype="float32",
        byte_order="little",
        dimension=2,
    )
    assert coordination.has(result.storage_cid)
    assert cid_for_bytes(vector.packed_bytes, "raw") == result.cid
    sealed_path = coordination._block_path(result.storage_cid)
    assert sealed_path.is_file()
    raw = json.loads(sealed_path.read_text(encoding="utf-8"))
    assert raw["schema"] == STORED_ARTIFACT_SCHEMA
    assert raw["kind"] == SemanticWorldArtifactKind.VECTOR_BYTES.value
    assert cid_for_artifact(raw) == result.storage_cid


# ---------------------------------------------------------------------------
# Canonical vector byte vectors
# ---------------------------------------------------------------------------


def test_canonical_float32_little_endian_bytes() -> None:
    vector = pack_canonical_vector(
        [1.0, 2.0, 3.0, 4.0],
        dtype="float32",
        byte_order="little",
        dimension=4,
    )
    assert vector.packed_bytes == b"".join(
        struct.pack("<f", value) for value in (1.0, 2.0, 3.0, 4.0)
    )
    assert vector.bytes_cid == cid_for_bytes(vector.packed_bytes, "raw")
    assert vector.bytes_hex == vector.packed_bytes.hex()
    round_trip = pack_canonical_vector(
        vector.packed_bytes,
        dtype="float32",
        byte_order="little",
        dimension=4,
    )
    assert round_trip.packed_bytes == vector.packed_bytes
    assert round_trip.bytes_cid == vector.bytes_cid


def test_byte_order_changes_canonical_bytes_and_cid() -> None:
    little = pack_canonical_vector(
        [1.0], dtype="float32", byte_order="little", dimension=1
    )
    big = pack_canonical_vector(
        [1.0], dtype="float32", byte_order="big", dimension=1
    )
    assert little.packed_bytes != big.packed_bytes
    assert little.bytes_cid != big.bytes_cid
    assert little.packed_bytes == struct.pack("<f", 1.0)
    assert big.packed_bytes == struct.pack(">f", 1.0)
    assert ADMITTED_BYTE_ORDERS == frozenset({"little", "big"})


@pytest.mark.parametrize("dtype,width,fmt", [("int8", 1, "b"), ("uint8", 1, "B"), ("int32", 4, "i")])
def test_integer_dtypes_pack_deterministically(dtype: str, width: int, fmt: str) -> None:
    values = [1, 2, 3]
    vector = pack_canonical_vector(
        values, dtype=dtype, byte_order="little", dimension=3
    )
    assert len(vector.packed_bytes) == 3 * width
    assert vector.packed_bytes == b"".join(struct.pack("<" + fmt, item) for item in values)


def test_nan_is_rejected() -> None:
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="NaN"):
        pack_canonical_vector(
            [1.0, float("nan")], dtype="float32", byte_order="little", dimension=2
        )


def test_infinity_is_rejected() -> None:
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="infinity"):
        pack_canonical_vector(
            [1.0, float("inf")], dtype="float32", byte_order="little", dimension=2
        )
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="infinity"):
        pack_canonical_vector(
            [float("-inf")], dtype="float16", byte_order="big", dimension=1
        )


def test_dimension_mismatch_is_rejected() -> None:
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="dimension mismatch"):
        pack_canonical_vector(
            [1.0, 2.0], dtype="float32", byte_order="little", dimension=3
        )
    packed = struct.pack("<ff", 1.0, 2.0)
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="dimension mismatch"):
        pack_canonical_vector(
            packed, dtype="float32", byte_order="little", dimension=3
        )


def test_unspecified_byte_order_is_rejected() -> None:
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="unspecified byte order"):
        pack_canonical_vector([1.0], dtype="float32", byte_order="", dimension=1)
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="byte_order"):
        pack_canonical_vector([1.0], dtype="float32", byte_order="native", dimension=1)


def test_bfloat16_rejects_nonfinite_and_packs_truncated_float32() -> None:
    vector = pack_canonical_vector(
        [1.0], dtype="bfloat16", byte_order="little", dimension=1
    )
    assert len(vector.packed_bytes) == 2
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="NaN"):
        pack_canonical_vector(
            [float("nan")], dtype="bfloat16", byte_order="little", dimension=1
        )


# ---------------------------------------------------------------------------
# Semantic object + projection round trip
# ---------------------------------------------------------------------------


def test_put_and_get_verified_semantic_object(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope = _envelope()
    result = verified.put_semantic_object(envelope, operation_id="op-object-1")
    assert result.cid == envelope.semantic_object_cid
    assert result.local_durable is True
    loaded = verified.get_verified_semantic_object(envelope.semantic_object_cid)
    assert loaded.to_dict() == envelope.to_dict()
    block = verified.get_verified_block(result.storage_cid)
    assert block["kind"] == "semantic_object"
    assert block["identity_cid"] == envelope.semantic_object_cid


def test_projection_identity_binds_required_fields(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope, vector = _put_subject_and_vector(verified)
    record = _projection_record(envelope, vector, quantization_profile_cid=_source_cid("q8"))
    payload = record.to_dict()
    for field in PROJECTION_REQUIRED_FIELDS:
        assert field in payload
    for field in (
        "model_cid",
        "tokenizer_cid",
        "preprocessing_profile_cid",
        "metric",
        "dtype",
        "quantization_profile_cid",
        "privacy_class",
    ):
        assert payload[field]
    assert payload["quantization_profile_cid"] == _source_cid("q8")
    result = verified.put_projection_record(record, operation_id="op-proj-1")
    assert result.cid == record.projection_cid
    loaded = verified.get_verified_projection_record(record.projection_cid)
    assert loaded.projection_cid == record.projection_cid
    assert loaded.identity.model_cid == record.identity.model_cid
    assert loaded.identity.tokenizer_cid == record.identity.tokenizer_cid
    assert loaded.identity.preprocessing_profile_cid == record.identity.preprocessing_profile_cid
    assert loaded.identity.metric == "cosine"
    assert loaded.identity.dtype == "float32"
    assert loaded.identity.quantization_profile_cid == _source_cid("q8")
    assert loaded.identity.privacy_class == "internal"
    assert loaded.identity.authoritative is False


def test_null_quantization_is_still_bound(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope, vector = _put_subject_and_vector(verified)
    record = _projection_record(envelope, vector, quantization_profile_cid=None)
    assert "quantization_profile_cid" in record.to_dict()
    assert record.to_dict()["quantization_profile_cid"] is None
    verified.put_projection_record(record)
    loaded = verified.get_verified_projection_record(record.projection_cid)
    assert loaded.identity.quantization_profile_cid is None


def test_model_change_changes_projection_identity_only(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope, vector = _put_subject_and_vector(verified)
    first = _projection_record(envelope, vector)
    second = _projection_record(envelope, vector, model_cid=_source_cid("model-b"))
    assert first.identity.subject_cid == second.identity.subject_cid
    assert first.projection_cid != second.projection_cid
    verified.put_projection_record(first)
    verified.put_projection_record(second)
    assert (
        verified.get_verified_semantic_object(envelope.semantic_object_cid).semantic_object_cid
        == envelope.semantic_object_cid
    )


def test_projection_index_manifest_round_trip(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope, vector = _put_subject_and_vector(verified)
    identity = ProjectionIndexManifestIdentity(
        projection_kind="embedding",
        model_cid=_source_cid("model-a"),
        tokenizer_cid=_source_cid("tokenizer-a"),
        preprocessing_profile_cid=_source_cid("preproc-a"),
        dimension=vector.dimension,
        metric="cosine",
        dtype=vector.dtype,
        byte_order=vector.byte_order,
        source_cid=envelope.semantic_object_cid,
        schema_ids=["program-identity@1"],
    )
    manifest = ProjectionIndexManifest.from_identity(identity)
    result = verified.put_projection_index_manifest(manifest, operation_id="op-manifest-1")
    assert result.cid == manifest.projection_index_manifest_cid
    loaded = verified.get_verified_projection_index_manifest(result.cid)
    assert loaded.identity.model_cid == identity.model_cid
    assert loaded.identity.rebuildable is True
    assert loaded.identity.authoritative is False


# ---------------------------------------------------------------------------
# Store-before-reference
# ---------------------------------------------------------------------------


def test_projection_without_stored_vector_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope = _envelope()
    verified.put_semantic_object(envelope)
    ghost = pack_canonical_vector(
        _vector_values(4), dtype="float32", byte_order="little", dimension=4
    )
    record = _projection_record(envelope, ghost)
    with pytest.raises(
        VerifiedSemanticStoreAdmissionError, match="store-before-reference: vector_cid"
    ):
        verified.put_projection_record(record)


def test_projection_without_stored_subject_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope = _envelope()
    vector_result = verified.put_vector_bytes(
        _vector_values(4), dtype="float32", byte_order="little", dimension=4
    )
    vector = verified.get_verified_vector(vector_result.cid)
    record = _projection_record(envelope, vector)
    with pytest.raises(
        VerifiedSemanticStoreAdmissionError, match="store-before-reference: subject_cid"
    ):
        verified.put_projection_record(record)


def test_index_manifest_without_stored_source_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope = _envelope()
    identity = ProjectionIndexManifestIdentity(
        projection_kind="embedding",
        model_cid=_source_cid("model-a"),
        tokenizer_cid=_source_cid("tokenizer-a"),
        preprocessing_profile_cid=_source_cid("preproc-a"),
        dimension=4,
        metric="cosine",
        dtype="float32",
        byte_order="little",
        source_cid=envelope.semantic_object_cid,
    )
    with pytest.raises(
        VerifiedSemanticStoreAdmissionError, match="store-before-reference: source_cid"
    ):
        verified.put_projection_index_manifest(identity)


def test_projection_dimension_mismatch_against_stored_vector_fails(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope, vector = _put_subject_and_vector(verified, dimension=4)
    record = _projection_record(envelope, vector)
    mutated = dict(record.to_dict())
    mutated["dimension"] = 8
    mutated.pop("projection_cid")
    with pytest.raises(ProgramIdentityError):
        # Changing dimension without recomputing CID is a datasets identity failure.
        ProjectionIdentity.from_dict({**mutated, "projection_cid": record.projection_cid})
    rebuilt = ProjectionIdentity(
        **{key: value for key, value in mutated.items() if key != "schema"}
    )
    with pytest.raises(VerifiedSemanticStoreAdmissionError, match="dimension mismatch"):
        verified.put_projection_record(ProjectionRecord.from_identity(rebuilt))


# ---------------------------------------------------------------------------
# Claimed-CID rehash, corruption, idempotency
# ---------------------------------------------------------------------------


def test_forged_expected_cid_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope = _envelope()
    forged = cid_for_bytes(b"not-the-object", "raw")
    with pytest.raises(VerifiedSemanticStoreIntegrityError, match="forged|mismatched"):
        verified.put_semantic_object(envelope, expected_cid=forged)
    with pytest.raises(VerifiedSemanticStoreNotFound):
        verified.get_verified_semantic_object(forged)


def test_claimed_vector_cid_rehash(
    artifacts: SemanticWorldArtifactStore,
) -> None:
    vector = pack_canonical_vector(
        [1.0, -2.5], dtype="float32", byte_order="little", dimension=2
    )
    result = artifacts.put_vector_bytes(
        vector.packed_bytes,
        dtype=vector.dtype,
        byte_order=vector.byte_order,
        dimension=vector.dimension,
        expected_cid=vector.bytes_cid,
    )
    loaded = artifacts.get_verified_vector(result.cid)
    assert loaded.bytes_cid == vector.bytes_cid
    assert loaded.bytes_cid == cid_for_bytes(loaded.packed_bytes, "raw")
    forged = dict(vector.payload())
    forged["bytes_cid"] = cid_for_bytes(b"other", "raw")
    with pytest.raises(SemanticWorldArtifactIntegrityError, match="does not rehash"):
        artifacts.put_artifact(SemanticWorldArtifactKind.VECTOR_BYTES, forged)


def test_corrupt_present_block_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope = _envelope()
    result = verified.put_semantic_object(envelope, operation_id="op-corrupt")
    path = verified.store._block_path(result.storage_cid)
    path.write_bytes(b'{"schema":"tampered","kind":"semantic_object","payload":{}}')
    with pytest.raises(VerifiedSemanticStoreIntegrityError):
        verified.get_verified_semantic_object(envelope.semantic_object_cid)
    with pytest.raises(VerifiedSemanticStoreIntegrityError):
        verified.get_verified_block(result.storage_cid)


def test_idempotent_immutable_puts(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope = _envelope()
    first = verified.put_semantic_object(envelope, operation_id="op-idempotent")
    second = verified.put_semantic_object(envelope, operation_id="op-idempotent")
    assert first.cid == second.cid == envelope.semantic_object_cid
    assert second.reason_code == "unchanged"
    assert second.created is False
    third = verified.put_semantic_object(envelope)
    assert third.cid == first.cid
    assert third.reason_code == "unchanged"


def test_operation_id_conflict_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    first = _envelope(logical_name="pkg.mod.first")
    second = _envelope(logical_name="pkg.mod.second")
    verified.put_semantic_object(first, operation_id="op-shared")
    with pytest.raises(
        (VerifiedSemanticStoreAdmissionError, SemanticWorldArtifactConflictError)
    ):
        verified.put_semantic_object(second, operation_id="op-shared")


def test_restart_rereads_and_reverifies_immutable_blocks(store_dir: Path) -> None:
    envelope = _envelope()
    values = [1.0, 2.0, 3.0, 4.0]
    with DurableCoordinationStore(store_dir) as coordination:
        with VerifiedSemanticBlockStore(coordination) as store:
            store.put_semantic_object(envelope, operation_id="op-reopen-object")
            vector_put = store.put_vector_bytes(
                values, dtype="float32", byte_order="little", dimension=4
            )
            record = _projection_record(envelope, store.get_verified_vector(vector_put.cid))
            store.put_projection_record(record, operation_id="op-reopen-proj")
            projection_cid = record.projection_cid
    with DurableCoordinationStore(store_dir) as coordination:
        with VerifiedSemanticBlockStore(coordination) as store:
            loaded_object = store.get_verified_semantic_object(envelope.semantic_object_cid)
            loaded_proj = store.get_verified_projection_record(projection_cid)
            loaded_vector = store.get_verified_vector(vector_put.cid)
            assert loaded_object.to_dict() == envelope.to_dict()
            assert loaded_proj.projection_cid == projection_cid
            assert loaded_vector.bytes_cid == vector_put.cid


def test_missing_cid_fails_closed(verified: VerifiedSemanticBlockStore) -> None:
    missing = cid_for_bytes(b"absent-semantic-world-artifact", "raw")
    with pytest.raises(VerifiedSemanticStoreNotFound):
        verified.get_verified_semantic_object(missing)
    with pytest.raises(VerifiedSemanticStoreNotFound):
        verified.get_verified_block(missing)


# ---------------------------------------------------------------------------
# Profile / privacy / score-derived identity rejection
# ---------------------------------------------------------------------------


def test_unpinned_model_or_preprocessor_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope, vector = _put_subject_and_vector(verified)
    with pytest.raises((ProgramIdentityError, VerifiedSemanticStoreAdmissionError)):
        _projection_record(envelope, vector, model_cid="")
    with pytest.raises((ProgramIdentityError, VerifiedSemanticStoreAdmissionError)):
        ProjectionRecord.from_payload(
            {
                **_projection_record(envelope, vector).to_dict(),
                "tokenizer_cid": "bert-base-uncased",
            }
        )


def test_authoritative_projection_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope, vector = _put_subject_and_vector(verified)
    with pytest.raises((ProgramIdentityError, VerifiedSemanticStoreAdmissionError)):
        _projection_record(envelope, vector, authoritative=True)


def test_score_derived_identity_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope, vector = _put_subject_and_vector(verified)
    payload = dict(_projection_record(envelope, vector).to_dict())
    payload["score"] = 0.9
    with pytest.raises(VerifiedSemanticStoreAdmissionError, match="score-derived"):
        ProjectionRecord.from_payload(payload)
    object_payload = dict(_envelope().to_dict())
    object_payload["similarity"] = 1
    with pytest.raises(VerifiedSemanticStoreAdmissionError, match="score-derived"):
        verified.put_semantic_object(object_payload)


def test_mutable_document_identity_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    payload = dict(_envelope().to_dict())
    payload["document_id"] = "row-12"
    with pytest.raises(
        VerifiedSemanticStoreAdmissionError, match="mutable unresolved document"
    ):
        verified.put_semantic_object(payload)


def test_private_raw_source_fails_closed(
    artifacts: SemanticWorldArtifactStore,
) -> None:
    payload = {"semantic_object_cid": _source_cid("x"), "secret": "CLASSIFIED"}
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="private"):
        reject_private_raw_source(payload)
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="private"):
        artifacts.put_artifact(
            SemanticWorldArtifactKind.SEMANTIC_OBJECT,
            payload,
            expected_cid=_source_cid("x"),
        )


def test_unknown_schema_version_fails_closed() -> None:
    validate_stored_artifact_schema(STORED_ARTIFACT_SCHEMA)
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="unknown artifact schema version"):
        validate_stored_artifact_schema("ipfs-kit.semantic-world-store.artifact@2")
    with pytest.raises(SemanticWorldArtifactIntegrityError, match="unknown artifact schema version"):
        admit_sealed_record(
            {
                "schema": "ipfs-kit.semantic-world-store.artifact@99",
                "interface_id": STORED_ARTIFACT_INTERFACE,
                "kind": "semantic_object",
                "payload": {"semantic_object_cid": _source_cid("x")},
            }
        )


def test_wrong_kind_on_get_fails_closed(
    verified: VerifiedSemanticBlockStore,
) -> None:
    envelope = _envelope()
    verified.put_semantic_object(envelope)
    with pytest.raises(VerifiedSemanticStoreIntegrityError, match="wrong artifact kind"):
        verified.get_verified_projection_record(envelope.semantic_object_cid)
    with pytest.raises(SemanticWorldArtifactIntegrityError, match="wrong artifact kind"):
        verified.artifacts.get_verified_artifact(
            envelope.semantic_object_cid,
            expected_kind=SemanticWorldArtifactKind.PROJECTION_RECORD,
        )


def test_non_dag_json_types_fail_closed(
    artifacts: SemanticWorldArtifactStore,
) -> None:
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="DAG-JSON"):
        artifacts.put_artifact(
            SemanticWorldArtifactKind.SEMANTIC_OBJECT,
            {"semantic_object_cid": _source_cid("x"), "ratio": 1.5},
        )


def test_seal_and_storage_cid_are_deterministic() -> None:
    payload = {"semantic_object_cid": _source_cid("seal")}
    sealed_a = seal_semantic_world_artifact(
        SemanticWorldArtifactKind.SEMANTIC_OBJECT, payload
    )
    sealed_b = seal_semantic_world_artifact("semantic_object", dict(payload))
    assert sealed_a == sealed_b
    assert cid_for_semantic_world_artifact(
        SemanticWorldArtifactKind.SEMANTIC_OBJECT, payload
    ) == cid_for_artifact(sealed_a)


def test_kit_raw_cid_is_accepted_as_vector_identity() -> None:
    packed = pack_canonical_vector(
        [1.0], dtype="float32", byte_order="little", dimension=1
    )
    kit_cid = cid_for_bytes(packed.packed_bytes, "raw")
    datasets_cid = datasets_cid_for_bytes(packed.packed_bytes)
    assert kit_cid == packed.bytes_cid
    assert kit_cid == datasets_cid
    envelope = _envelope()
    identity = ProjectionIdentity(
        subject_cid=envelope.semantic_object_cid,
        subject_kind="semantic_object",
        projection_kind="embedding",
        model_cid=_source_cid("model-a"),
        tokenizer_cid=_source_cid("tokenizer-a"),
        preprocessing_profile_cid=_source_cid("preproc-a"),
        normalization_profile_cid=_source_cid("norm-a"),
        dimension=1,
        metric="cosine",
        dtype="float32",
        byte_order="little",
        vector_cid=kit_cid,
        privacy_class="internal",
        availability_policy="available",
        authoritative=False,
    )
    assert identity.vector_cid == kit_cid


def test_verified_store_accepts_coordination_store_directly(store_dir: Path) -> None:
    envelope = _envelope()
    with DurableCoordinationStore(store_dir) as coordination:
        with VerifiedSemanticBlockStore(coordination) as store:
            store.put_semantic_object(envelope)
            loaded = store.get_verified_semantic_object(envelope.semantic_object_cid)
            assert loaded.logical_name == envelope.logical_name


def test_oversized_artifact_fails_closed(
    artifacts: SemanticWorldArtifactStore,
) -> None:
    huge = "x" * (MAX_ARTIFACT_BYTES + 64)
    payload = {"semantic_object_cid": _source_cid("huge"), "blob": huge}
    with pytest.raises(SemanticWorldArtifactAdmissionError, match="MAX_ARTIFACT_BYTES"):
        seal_semantic_world_artifact(SemanticWorldArtifactKind.SEMANTIC_OBJECT, payload)


def test_json_nan_constant_cannot_enter_vector_payload() -> None:
    assert not math.isfinite(float("nan"))
    with pytest.raises(SemanticWorldArtifactAdmissionError):
        pack_canonical_vector(
            [float("nan")], dtype="float32", byte_order="little", dimension=1
        )
