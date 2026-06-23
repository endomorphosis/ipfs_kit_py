import json

import pytest

from ipfs_kit_py.vfs_graphrag_export import (
    VFSGraphRAGBundleError,
    export_index,
    import_index,
    load_manifest,
    verify_manifest,
)
from ipfs_kit_py.vfs_graphrag_index import VFSGraphRAGIndex
from ipfs_kit_py.vfs_graphrag_schema import (
    EXPORT_MANIFEST_SCHEMA,
    VFSChunkRecord,
    VFSEmbeddingRecord,
    VFSEntityRecord,
    VFSObjectRecord,
    VFSRelationshipRecord,
    VFSSnapshotRecord,
)


def _populate_small_vfs(index):
    readme = index.upsert_object(
        VFSObjectRecord(
            namespace="research",
            backend="ipfs",
            protocol="ipfs",
            path="/docs/readme.md",
            content_id="bafy-readme",
            content_hash="sha256:readme",
            mime_type="text/markdown",
            tags=["docs"],
            metadata={"bucket": "atlas", "title": "Readme"},
        )
    )
    data = index.upsert_object(
        VFSObjectRecord(
            namespace="research",
            backend="walrus",
            protocol="walrus",
            path="/data/table.json",
            content_id="walrus-table",
            content_hash="sha256:table",
            mime_type="application/json",
            tags=["data"],
            metadata={"bucket": "atlas", "rows": 2},
        )
    )
    chunk = index.upsert_chunk(
        VFSChunkRecord(
            parent_record_id=readme.record_id,
            namespace=readme.namespace,
            path=readme.normalized_path,
            content_id=readme.content_id,
            chunk_index=0,
            text="Atlas readme mentions vector metadata.",
            extraction_method="plain_text",
            language="en",
        )
    )
    embedding = index.upsert_embedding(
        VFSEmbeddingRecord(
            chunk_id=chunk.chunk_id,
            parent_record_id=readme.record_id,
            model_id="fake",
            dimension=3,
            vector_store_id="local:json",
            embedding_vector_id="vec-readme",
            metadata={"vector": [1.0, 0.0, 0.5], "path": readme.normalized_path},
        )
    )
    entity = index.upsert_entity(
        VFSEntityRecord(
            name="Atlas",
            entity_type="project",
            source_record_ids=[readme.record_id],
            source_chunk_ids=[chunk.chunk_id],
            metadata={"record_id": readme.record_id},
        )
    )
    relationship = index.upsert_relationship(
        VFSRelationshipRecord(
            subject_id=entity.entity_id,
            predicate="describes",
            object_id=readme.record_id,
            source_record_ids=[readme.record_id],
            source_chunk_ids=[chunk.chunk_id],
        )
    )
    snapshot = index.upsert_snapshot(
        VFSSnapshotRecord(
            namespace="research",
            backend_bindings={"ipfs": {"root": "/docs"}, "walrus": {"root": "/data"}},
            root_paths=["/docs", "/data"],
            index_cids={"metadata": "bafy-index"},
            metadata_cids={"objects": "bafy-meta"},
            vector_index_cids={"fake": "bafy-vector"},
            graph_export_cids={"kg": "bafy-graph"},
            journal_range={"from": 1, "to": 2},
        )
    )
    checkpoint = index.checkpoint(
        namespace="research",
        backend="ipfs",
        checkpoint_type="journal",
        cursor={"sequence": 2},
        journal_entry_id="entry-2",
        journal_timestamp="2026-03-01T00:00:00+00:00",
        metadata={"source": "unit-test"},
    )
    return {
        "objects": [readme, data],
        "chunk": chunk,
        "embedding": embedding,
        "entity": entity,
        "relationship": relationship,
        "snapshot": snapshot,
        "checkpoint": checkpoint,
    }


def test_export_import_round_trip_preserves_index_records_filesystem_maps_and_checksums(tmp_path):
    source = VFSGraphRAGIndex(tmp_path / "source", namespace="research")
    records = _populate_small_vfs(source)
    filesystem_map = {
        "namespace": "research",
        "mounts": {"ipfs": "/docs", "walrus": "/data"},
        "path_map": {
            "/docs/readme.md": {"record_id": records["objects"][0].record_id, "content_id": "bafy-readme"},
            "/data/table.json": {"record_id": records["objects"][1].record_id, "content_id": "walrus-table"},
        },
    }
    journal_entries = [
        {"sequence": 1, "operation": "write", "path": "/docs/readme.md", "cid": "bafy-readme"},
        {"sequence": 2, "operation": "write", "path": "/data/table.json", "cid": "walrus-table"},
    ]

    manifest = export_index(
        source,
        tmp_path / "bundle",
        filesystem_map=filesystem_map,
        journal_entries=journal_entries,
        metadata={"reason": "round-trip-test"},
    )

    assert manifest["schema"] == EXPORT_MANIFEST_SCHEMA
    assert manifest["counts"] == {
        "metadata": 2,
        "chunks": 1,
        "embeddings": 1,
        "graph_nodes": 1,
        "graph_edges": 1,
        "snapshots": 1,
        "checkpoints": 1,
    }
    assert set(manifest["artifacts"]).issuperset(
        {
            "metadata",
            "chunks",
            "embeddings",
            "graph_nodes",
            "graph_edges",
            "snapshots",
            "checkpoints",
            "filesystem",
            "journal",
        }
    )
    for artifact in manifest["artifacts"].values():
        assert artifact["checksum"].startswith("sha256:")
        assert artifact["bytes"] >= 0
    assert verify_manifest(tmp_path / "bundle") is True

    target = VFSGraphRAGIndex(tmp_path / "target", namespace="research")
    result = import_index(tmp_path / "bundle", target, mode="full-snapshot")

    assert result["success"] is True
    assert result["filesystem_map"] == filesystem_map
    assert result["journal_entries"] == journal_entries
    assert target.query_objects() == source.query_objects()
    assert target.query_chunks() == source.query_chunks()
    assert target.query_embeddings() == source.query_embeddings()
    assert target.query_graph_nodes() == source.query_graph_nodes()
    assert target.query_graph_edges() == source.query_graph_edges()
    assert target.query_snapshots() == source.query_snapshots()
    assert target.query_checkpoints() == source.query_checkpoints()
    assert load_manifest(tmp_path / "bundle" / "manifest.json")["bundle_checksum"] == manifest["bundle_checksum"]


def test_import_modes_scope_restored_artifacts(tmp_path):
    source = VFSGraphRAGIndex(tmp_path / "source", namespace="research")
    _populate_small_vfs(source)
    export_index(source, tmp_path / "bundle")

    metadata_only = VFSGraphRAGIndex(tmp_path / "metadata-only", namespace="research")
    import_index(tmp_path / "bundle", metadata_only, mode="metadata-only")

    assert len(metadata_only.query_objects()) == 2
    assert len(metadata_only.query_checkpoints()) == 1
    assert metadata_only.query_chunks() == []
    assert metadata_only.query_embeddings() == []
    assert metadata_only.query_graph_nodes() == []
    assert metadata_only.query_graph_edges() == []

    metadata_plus_indexes = import_index(
        tmp_path / "bundle",
        tmp_path / "metadata-plus-indexes",
        mode="metadata-plus-indexes",
    )["index"]

    assert len(metadata_plus_indexes.query_objects()) == 2
    assert len(metadata_plus_indexes.query_chunks()) == 1
    assert len(metadata_plus_indexes.query_embeddings()) == 1
    assert len(metadata_plus_indexes.query_graph_nodes()) == 1
    assert len(metadata_plus_indexes.query_graph_edges()) == 1
    assert len(metadata_plus_indexes.query_snapshots()) == 1
    assert len(metadata_plus_indexes.query_checkpoints()) == 1


def test_manifest_verification_detects_tampered_artifacts(tmp_path):
    source = VFSGraphRAGIndex(tmp_path / "source", namespace="research")
    _populate_small_vfs(source)
    export_index(source, tmp_path / "bundle")

    metadata_path = tmp_path / "bundle" / "metadata.jsonl"
    rows = metadata_path.read_text(encoding="utf-8")
    metadata_path.write_text(rows + json.dumps({"tampered": True}) + "\n", encoding="utf-8")

    with pytest.raises(VFSGraphRAGBundleError, match="Checksum mismatch"):
        verify_manifest(tmp_path / "bundle")

    with pytest.raises(VFSGraphRAGBundleError, match="Checksum mismatch"):
        import_index(tmp_path / "bundle", tmp_path / "target")
