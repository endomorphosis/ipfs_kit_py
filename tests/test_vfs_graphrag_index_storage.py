import importlib
import sys

from ipfs_kit_py.vfs_graphrag_index import VFSGraphRAGIndex
from ipfs_kit_py.vfs_graphrag_schema import (
    SCHEMA_VERSION,
    VFSCheckpointRecord,
    VFSChunkRecord,
    VFSEmbeddingRecord,
    VFSEntityRecord,
    VFSObjectRecord,
    VFSRelationshipRecord,
)


def test_local_index_persists_and_reloads_all_record_families(tmp_path):
    index = VFSGraphRAGIndex(tmp_path, namespace="research")
    obj = index.upsert_object(
        VFSObjectRecord(
            namespace="research",
            backend="ipfs",
            protocol="ipfs",
            path="/docs/report.md",
            content_id="bafyreport",
            content_hash="sha256:abc",
            mime_type="text/markdown",
            tags=["docs", "report"],
            metadata={"title": "Report"},
        )
    )
    chunk = index.upsert_chunk(
        VFSChunkRecord(
            parent_record_id=obj.record_id,
            namespace="research",
            path=obj.normalized_path,
            content_id=obj.content_id,
            chunk_index=0,
            text="IPFS stores content by CID.",
            extraction_method="plain_text",
            language="en",
        )
    )
    embedding = index.upsert_embedding(
        VFSEmbeddingRecord(
            chunk_id=chunk.chunk_id,
            parent_record_id=obj.record_id,
            model_id="sentence-transformers/test",
            dimension=384,
            vector_store_id="local:json",
            embedding_vector_id="vec-1",
        )
    )
    entity = index.upsert_entity(
        VFSEntityRecord(
            name="IPFS",
            entity_type="technology",
            source_record_ids=[obj.record_id],
            source_chunk_ids=[chunk.chunk_id],
        )
    )
    relationship = index.upsert_relationship(
        VFSRelationshipRecord(
            subject_id=entity.entity_id,
            predicate="mentioned_in",
            object_id=obj.record_id,
            source_chunk_ids=[chunk.chunk_id],
        )
    )
    checkpoint = index.checkpoint(
        namespace="research",
        backend="ipfs",
        checkpoint_type="journal",
        cursor={"sequence": 42},
        journal_entry_id="entry-42",
        journal_timestamp="2026-01-01T00:00:00+00:00",
        bucket_last_updated="2026-01-01T00:00:01+00:00",
        git_snapshot_id="git-snap-1",
    )

    reloaded = VFSGraphRAGIndex(tmp_path, namespace="research")

    assert reloaded.get_object(obj.record_id) == obj
    assert reloaded.query_objects(tags="docs") == [obj]
    assert reloaded.query_chunks(parent_record_id=obj.record_id) == [chunk]
    assert reloaded.query_embeddings(chunk_id=chunk.chunk_id) == [embedding]
    assert reloaded.query_graph_nodes(source_record_ids=obj.record_id) == [entity]
    assert reloaded.query_graph_edges(source_chunk_ids=chunk.chunk_id) == [relationship]
    assert reloaded.query_checkpoints(journal_entry_id="entry-42") == [checkpoint]
    assert reloaded.latest_checkpoint(
        namespace="research",
        backend="ipfs",
        checkpoint_type="journal",
    ) == checkpoint


def test_upserts_are_deterministic_and_replace_existing_records(tmp_path):
    index = VFSGraphRAGIndex(tmp_path)
    first = VFSObjectRecord(path="/same.txt", content_id="cid", metadata={"version": 1})
    second = VFSObjectRecord(path="/same.txt", content_id="cid", metadata={"version": 2})

    assert first.record_id == second.record_id

    index.upsert_object(first)
    index.upsert_object(second)
    reloaded = VFSGraphRAGIndex(tmp_path)

    assert reloaded.query_objects(path="/same.txt") == [second]
    assert reloaded.stats()["counts"]["objects"] == 1


def test_checkpoint_records_capture_required_cursors(tmp_path):
    index = VFSGraphRAGIndex(tmp_path, namespace="vfs")
    checkpoint = index.upsert_checkpoint(
        VFSCheckpointRecord(
            namespace="vfs",
            backend="git",
            checkpoint_type="snapshot",
            cursor={"journal_sequence": 7, "bucket_registry_generation": 3},
            journal_entry_id="journal-7",
            journal_timestamp="2026-02-01T10:00:00+00:00",
            bucket_last_updated="2026-02-01T10:01:00+00:00",
            git_snapshot_id="snapshot-7",
        )
    )

    reloaded = VFSGraphRAGIndex(tmp_path, namespace="vfs")
    stored = reloaded.latest_checkpoint(
        namespace="vfs",
        backend="git",
        checkpoint_type="snapshot",
    )

    assert stored == checkpoint
    assert stored.cursor["journal_sequence"] == 7
    assert stored.cursor["bucket_registry_generation"] == 3
    assert stored.git_snapshot_id == "snapshot-7"
    assert stored.metadata_schema_version == SCHEMA_VERSION


def test_index_import_does_not_require_optional_graphrag_dependencies(monkeypatch):
    blocked = {
        "graphrag",
        "ipfs_datasets_py",
        "llama_index",
        "langchain",
    }
    real_import = __import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in blocked:
            raise AssertionError(f"optional dependency imported: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)
    sys.modules.pop("ipfs_kit_py.vfs_graphrag_index", None)

    module = importlib.import_module("ipfs_kit_py.vfs_graphrag_index")

    assert module.VFSGraphRAGIndex
