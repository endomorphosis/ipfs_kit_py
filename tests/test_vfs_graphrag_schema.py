import json

import pytest

from ipfs_kit_py.vfs_graphrag_schema import (
    CHECKPOINT_SCHEMA,
    CHUNK_SCHEMA,
    EMBEDDING_SCHEMA,
    ENTITY_SCHEMA,
    EXPORT_MANIFEST_SCHEMA,
    OBJECT_SCHEMA,
    RECORD_TYPES,
    RELATIONSHIP_SCHEMA,
    SCHEMA_VERSION,
    SNAPSHOT_SCHEMA,
    VFSCheckpointRecord,
    VFSChunkRecord,
    VFSEmbeddingRecord,
    VFSEntityRecord,
    VFSExportManifest,
    VFSObjectRecord,
    VFSRelationshipRecord,
    VFSSnapshotRecord,
    normalize_vfs_path,
    record_from_dict,
    record_from_json,
    records_from_jsonl,
    register_schema_migration,
    to_jsonl,
)


def test_canonical_record_types_are_registered():
    assert RECORD_TYPES == {
        OBJECT_SCHEMA: VFSObjectRecord,
        CHUNK_SCHEMA: VFSChunkRecord,
        EMBEDDING_SCHEMA: VFSEmbeddingRecord,
        ENTITY_SCHEMA: VFSEntityRecord,
        RELATIONSHIP_SCHEMA: VFSRelationshipRecord,
        SNAPSHOT_SCHEMA: VFSSnapshotRecord,
        CHECKPOINT_SCHEMA: VFSCheckpointRecord,
        EXPORT_MANIFEST_SCHEMA: VFSExportManifest,
    }


def test_object_record_contains_required_vfs_metadata_and_stable_id():
    record = VFSObjectRecord(
        namespace="research",
        backend="storacha",
        protocol="storacha",
        path="storacha://bucket//docs/readme.md",
        content_id="bafybeigdyrzt",
        content_hash="sha256:abc",
        mime_type="text/markdown",
        size_bytes=512,
        tags=["docs"],
        lineage={"source": "journal"},
        security={"encrypted": False, "policy": "public"},
        export={"bundle": "car"},
        metadata={"title": "README"},
    )
    duplicate = VFSObjectRecord(
        namespace="research",
        backend="storacha",
        protocol="storacha",
        path="storacha://bucket/docs/readme.md",
        content_id="bafybeigdyrzt",
        content_hash="sha256:abc",
    )

    data = record.to_dict()
    assert data["schema"] == OBJECT_SCHEMA
    assert data["record_id"].startswith("vfsrec:")
    assert data["record_id"] == duplicate.record_id
    assert data["normalized_path"] == "storacha://bucket/docs/readme.md"
    assert data["content_id"] == "bafybeigdyrzt"
    assert data["content_hash"] == "sha256:abc"
    assert data["security"]["policy"] == "public"
    assert data["export"]["bundle"] == "car"


def test_derived_records_cover_chunks_embeddings_graph_snapshot_checkpoint_manifest():
    obj = VFSObjectRecord(path="/notes/report.txt", content_id="cid")
    chunk = VFSChunkRecord(
        parent_record_id=obj.record_id,
        path=obj.normalized_path,
        content_id=obj.content_id,
        chunk_index=2,
        byte_start=10,
        byte_end=30,
        text_start=0,
        text_end=12,
        extraction_method="plain_text",
        language="en",
        text="hello world",
    )
    embedding = VFSEmbeddingRecord(
        chunk_id=chunk.chunk_id,
        parent_record_id=obj.record_id,
        model_id="sentence-transformers/test",
        dimension=384,
        vector_store_id="faiss:local",
        embedding_vector_id="vec-1",
        embedding_checksum="sha256:def",
    )
    entity = VFSEntityRecord(
        name="IPFS",
        entity_type="technology",
        aliases=["InterPlanetary File System"],
        source_record_ids=[obj.record_id],
        source_chunk_ids=[chunk.chunk_id],
        confidence=0.9,
    )
    relationship = VFSRelationshipRecord(
        subject_id=entity.entity_id,
        predicate="mentions",
        object_id=obj.record_id,
        relationship_type="semantic",
        source_chunk_ids=[chunk.chunk_id],
    )
    snapshot = VFSSnapshotRecord(
        namespace="research",
        backend_bindings={"ipfs": {"protocol": "ipfs"}},
        root_paths=["/notes"],
        index_cids={"objects": "bafyindex"},
        metadata_cids={"objects": "bafymeta"},
        vector_index_cids={"faiss": "bafyvec"},
        graph_export_cids={"kg": "bafygraph"},
        journal_range={"from": "entry-1", "to": "entry-9"},
    )
    checkpoint = VFSCheckpointRecord(
        namespace="research",
        backend="ipfs",
        checkpoint_type="journal",
        cursor={"sequence": 9},
        journal_entry_id="entry-9",
        journal_timestamp="2026-01-01T00:00:00+00:00",
        bucket_last_updated="2026-01-01T00:00:00+00:00",
        git_snapshot_id="snap-1",
    )
    manifest = VFSExportManifest(
        namespace="research",
        export_format="jsonl",
        object_count=1,
        chunk_count=1,
        embedding_count=1,
        entity_count=1,
        relationship_count=1,
        snapshot_count=1,
        checkpoint_count=1,
        files={"objects": "objects.jsonl"},
        root_cid="bafyroot",
        content_cids=["cid"],
    )

    assert chunk.text_hash
    assert chunk.chunk_id.startswith("vfschunk:")
    assert embedding.embedding_id.startswith("vfsemb:")
    assert entity.entity_id.startswith("vfsentity:")
    assert relationship.relationship_id.startswith("vfsrel:")
    assert snapshot.snapshot_id.startswith("vfssnap:")
    assert checkpoint.checkpoint_id.startswith("vfsckpt:")
    assert checkpoint.metadata_schema_version == SCHEMA_VERSION
    assert manifest.manifest_id.startswith("vfsmanifest:")


def test_json_and_jsonl_serialization_round_trip():
    record = VFSObjectRecord(path="/a/b.txt", metadata={"nested": {"ok": True}}, tags=["x"])
    payload = record.to_json()

    assert VFSObjectRecord.from_json(payload) == record
    assert record_from_json(payload) == record

    lines = to_jsonl([record])
    assert records_from_jsonl(lines, VFSObjectRecord) == [record]


def test_arrow_friendly_dict_flattens_nested_values():
    record = VFSObjectRecord(
        path="/a/b.txt",
        tags=["x", "y"],
        lineage={"parent": "root"},
        security={"encrypted": False},
        export={"manifest": "bundle"},
        metadata={"nested": {"value": 1}},
    )

    data = record.to_arrow_dict()
    assert data["schema"] == OBJECT_SCHEMA
    assert json.loads(data["tags"]) == ["x", "y"]
    assert json.loads(data["lineage"]) == {"parent": "root"}
    assert json.loads(data["metadata"]) == {"nested": {"value": 1}}


def test_schema_migration_hook_and_unknown_schema_handling():
    old_schema = "ipfs_kit_py.vfs.graphrag.object.v0"

    def migrate(data):
        data = dict(data)
        data["schema"] = OBJECT_SCHEMA
        data["object_type"] = data.pop("type")
        return data

    register_schema_migration(old_schema, migrate)

    migrated = record_from_dict(
        {
            "schema": old_schema,
            "type": "dataset",
            "path": "/datasets/example.parquet",
            "content_id": "cid",
        }
    )
    assert isinstance(migrated, VFSObjectRecord)
    assert migrated.object_type == "dataset"

    with pytest.raises(ValueError):
        record_from_dict({"schema": "unknown"})


def test_path_normalization():
    assert normalize_vfs_path("///tmp//file.txt") == "/tmp/file.txt"
    assert normalize_vfs_path("ipfs://bafy//path") == "ipfs://bafy/path"
    assert normalize_vfs_path("") == "/"
