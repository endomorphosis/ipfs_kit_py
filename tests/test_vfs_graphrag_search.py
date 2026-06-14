import pytest

from ipfs_kit_py.vfs_graphrag_index import VFSGraphRAGIndex
from ipfs_kit_py.vfs_graphrag_schema import VFSChunkRecord, VFSEmbeddingRecord, VFSObjectRecord


def _populate_index(index):
    quantum = index.upsert_object(
        VFSObjectRecord(
            namespace="research",
            backend="ipfs",
            protocol="ipfs",
            path="/papers/quantum.md",
            content_id="bafy-quantum",
            mime_type="text/markdown",
            tags=["physics", "paper"],
            metadata={"project": "atlas", "year": 2026, "author": "Ada"},
        )
    )
    graph = index.upsert_object(
        VFSObjectRecord(
            namespace="research",
            backend="s3",
            protocol="s3",
            path="/papers/graph.md",
            content_id="s3://bucket/graph.md",
            mime_type="text/markdown",
            tags=["graph", "paper"],
            metadata={"project": "atlas", "year": 2025, "author": "Grace"},
        )
    )
    notes = index.upsert_object(
        VFSObjectRecord(
            namespace="ops",
            backend="git",
            protocol="file",
            path="/notes/runbook.txt",
            content_id="git:runbook",
            mime_type="text/plain",
            tags=["ops"],
            metadata={"project": "ops", "year": 2026, "author": "Ada"},
        )
    )

    quantum_chunk = index.upsert_chunk(
        VFSChunkRecord(
            parent_record_id=quantum.record_id,
            namespace=quantum.namespace,
            path=quantum.normalized_path,
            content_id=quantum.content_id,
            chunk_index=0,
            text="Quantum storage notes for vector search.",
        )
    )
    graph_chunk = index.upsert_chunk(
        VFSChunkRecord(
            parent_record_id=graph.record_id,
            namespace=graph.namespace,
            path=graph.normalized_path,
            content_id=graph.content_id,
            chunk_index=0,
            text="GraphRAG metadata and vector retrieval.",
        )
    )
    notes_chunk = index.upsert_chunk(
        VFSChunkRecord(
            parent_record_id=notes.record_id,
            namespace=notes.namespace,
            path=notes.normalized_path,
            content_id=notes.content_id,
            chunk_index=0,
            text="Operational runbook.",
        )
    )

    index.upsert_embedding(
        VFSEmbeddingRecord(
            chunk_id=quantum_chunk.chunk_id,
            parent_record_id=quantum.record_id,
            model_id="fake",
            dimension=3,
            metadata={"vector": [1.0, 0.0, 0.0]},
        )
    )
    index.upsert_embedding(
        VFSEmbeddingRecord(
            chunk_id=graph_chunk.chunk_id,
            parent_record_id=graph.record_id,
            model_id="fake",
            dimension=3,
            metadata={"vector": [0.0, 1.0, 0.0]},
        )
    )
    index.upsert_embedding(
        VFSEmbeddingRecord(
            chunk_id=notes_chunk.chunk_id,
            parent_record_id=notes.record_id,
            model_id="fake",
            dimension=3,
            metadata={"vector": [0.7, 0.7, 0.0]},
        )
    )
    return quantum, graph, notes


def test_metadata_only_search_filters_and_returns_facets(tmp_path):
    index = VFSGraphRAGIndex(tmp_path, namespace="research")
    quantum, graph, _notes = _populate_index(index)

    result = index.metadata_search(
        metadata_filters={"metadata.project": "atlas", "backend": {"$in": ["ipfs", "s3"]}},
        top_k=10,
    )

    assert result["success"] is True
    assert [item["record_id"] for item in result["results"]] == [graph.record_id, quantum.record_id]
    assert result["facets"]["backend"] == {"ipfs": 1, "s3": 1}
    assert result["facets"]["tags"]["paper"] == 2
    first = result["results"][0]
    assert {
        "record_id",
        "path",
        "backend",
        "protocol",
        "content_id",
        "score",
        "score_parts",
        "snippet",
        "metadata",
        "chunks",
        "facets",
    }.issubset(first)
    assert first["score_parts"]["metadata_filter"] == 1.0
    assert first["score_parts"]["vector_similarity"] == 0.0


def test_vector_only_search_ranks_by_cosine_similarity(tmp_path):
    index = VFSGraphRAGIndex(tmp_path)
    _quantum, graph, notes = _populate_index(index)

    result = index.vector_search(query_vector=[0.0, 1.0, 0.0], top_k=2)

    assert [item["record_id"] for item in result["results"]] == [graph.record_id, notes.record_id]
    assert result["results"][0]["score"] == pytest.approx(1.0)
    assert result["results"][0]["score_parts"]["vector_similarity"] == pytest.approx(1.0)
    assert "GraphRAG metadata" in result["results"][0]["snippet"]


def test_hybrid_search_filters_then_ranks_with_explainable_score_parts(tmp_path):
    index = VFSGraphRAGIndex(tmp_path)
    quantum, graph, notes = _populate_index(index)

    result = index.hybrid_search(
        query="vector",
        query_vector=[0.8, 0.2, 0.0],
        metadata_filters={"metadata.year": {"$gte": 2026}},
        top_k=5,
    )

    assert [item["record_id"] for item in result["results"]] == [quantum.record_id, notes.record_id]
    assert graph.record_id not in [item["record_id"] for item in result["results"]]
    top = result["results"][0]
    assert top["record_id"] == quantum.record_id
    assert top["score_parts"]["metadata_filter"] == 1.0
    assert top["score_parts"]["vector_similarity"] == pytest.approx(0.9701425)
    assert top["score_parts"]["text_match"] == 1.0
    assert top["score"] > result["results"][1]["score"]


def test_search_supports_namespace_backend_and_custom_facet_fields(tmp_path):
    index = VFSGraphRAGIndex(tmp_path)
    quantum, _graph, _notes = _populate_index(index)

    result = index.search(
        metadata_filters={"author": "Ada"},
        namespaces=["research"],
        backends=["ipfs"],
        facet_fields=["metadata.author", "backend"],
    )

    assert result["total"] == 1
    assert result["results"][0]["record_id"] == quantum.record_id
    assert result["facets"] == {"metadata.author": {"Ada": 1}, "backend": {"ipfs": 1}}
