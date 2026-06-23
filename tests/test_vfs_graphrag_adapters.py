import importlib
import os

import pytest

from ipfs_kit_py.vfs_graphrag_index import (
    VFSEmbeddingAdapter,
    VFSGraphRAGAdapterConfig,
    VFSGraphRAGAdapters,
    VFSGraphRAGDependencyError,
    VFSGraphRAGIndex,
    VFSGraphRAGProcessorAdapter,
    VFSKnowledgeGraphAdapter,
    VFSQueryOptimizerAdapter,
    VFSVectorStoreAdapter,
    create_vfs_graphrag_adapters,
)
from ipfs_kit_py.vfs_graphrag_schema import VFSObjectRecord


def test_mock_adapter_bundle_normalizes_all_outputs_and_persists_records(tmp_path):
    adapters = create_vfs_graphrag_adapters(
        VFSGraphRAGAdapterConfig(
            namespace="research",
            use_mocks=True,
            chunk_size=12,
            embedding_model_id="mock/model",
        )
    )
    index = VFSGraphRAGIndex(tmp_path, namespace="research")
    obj = index.upsert_object(VFSObjectRecord(namespace="research", path="/notes/ipfs.txt", content_id="bafy"))

    chunks = adapters.chunking.chunk_text(
        "IPFS stores GraphRAG metadata.",
        parent_record_id=obj.record_id,
        path=obj.normalized_path,
        content_id=obj.content_id,
    )
    embeddings, vectors = adapters.embeddings.embed_chunks(chunks, vector_store_id="faiss:mock")
    stored_embeddings = adapters.vector_store.add_embeddings(embeddings, vectors)
    entities, relationships = adapters.knowledge_graph.extract(
        "IPFS stores GraphRAG metadata.",
        source_record_ids=[obj.record_id],
        source_chunk_ids=[chunks[0].chunk_id],
    )
    optimized = adapters.query_optimizer.optimize("  GraphRAG metadata  ")
    result = adapters.processor.query("GraphRAG metadata")

    index.put_records([*chunks, *stored_embeddings, *entities, *relationships])

    assert chunks[0].namespace == "research"
    assert chunks[0].parent_record_id == obj.record_id
    assert stored_embeddings[0].model_id == "mock/model"
    assert stored_embeddings[0].vector_store_id == "faiss:mock"
    assert stored_embeddings[0].embedding_vector_id == stored_embeddings[0].embedding_id
    assert entities[0].source_record_ids == [obj.record_id]
    assert relationships
    assert optimized["optimized_query"] == "GraphRAG metadata"
    assert result["metadata"]["mock"] is True
    assert VFSGraphRAGIndex(tmp_path).query_chunks(parent_record_id=obj.record_id) == chunks


def test_injected_backend_components_are_called_and_normalized():
    class Processor:
        def __init__(self):
            self.called = False

        def process(self, query, **kwargs):
            self.called = True
            return {
                "answer": f"answer:{query}",
                "results": [{"id": "chunk-1", "content": "hit", "similarity": 0.75}],
                "metadata": {"limit": kwargs["limit"]},
            }

    class Embedder:
        def __init__(self):
            self.texts = None

        def embed_documents(self, texts):
            self.texts = texts
            return [[1.0, 2.0, 3.0] for _ in texts]

    processor = Processor()
    processor_adapter = VFSGraphRAGProcessorAdapter(processor)
    processor_result = processor_adapter.query("ipfs", limit=3)

    chunks = create_vfs_graphrag_adapters(
        VFSGraphRAGAdapterConfig(use_mocks=True, chunk_size=100)
    ).chunking.chunk_text("hello world", parent_record_id="record-1")
    embedder = Embedder()
    embedding_adapter = VFSEmbeddingAdapter(embedder, model_id="fake/model")
    embedding_records, vectors = embedding_adapter.embed_chunks(chunks)

    assert processor.called is True
    assert processor_result == {
        "answer": "answer:ipfs",
        "results": [
            {
                "record_id": None,
                "chunk_id": "chunk-1",
                "text": "hit",
                "score": 0.75,
                "metadata": {},
            }
        ],
        "metadata": {"limit": 3},
    }
    assert embedder.texts == ["hello world"]
    assert vectors == [[1.0, 2.0, 3.0]]
    assert embedding_records[0].dimension == 3
    assert embedding_records[0].embedding_checksum


def test_knowledge_graph_and_query_optimizer_normalize_backend_shapes():
    class Extractor:
        def extract_knowledge_graph(self, text):
            return {
                "nodes": [{"label": "IPFS", "type": "technology", "score": 0.9}],
                "edges": [{"source": "IPFS", "type": "stores", "target": "CID", "score": 0.8}],
            }

    class Optimizer:
        def rewrite(self, query):
            return {"rewritten_query": query.upper(), "plan": "hybrid"}

    entities, relationships = VFSKnowledgeGraphAdapter(Extractor()).extract(
        "IPFS stores CID",
        source_record_ids=["record-1"],
        source_chunk_ids=["chunk-1"],
    )
    optimized = VFSQueryOptimizerAdapter(Optimizer()).optimize("ipfs")

    assert entities[0].name == "IPFS"
    assert entities[0].entity_type == "technology"
    assert entities[0].confidence == 0.9
    assert entities[0].source_chunk_ids == ["chunk-1"]
    assert relationships[0].subject_id == "IPFS"
    assert relationships[0].predicate == "stores"
    assert relationships[0].object_id == "CID"
    assert optimized["optimized_query"] == "IPFS"
    assert optimized["strategy"] == "hybrid"


def test_vector_store_selection_is_configurable_and_search_results_are_normalized():
    class Store:
        def __init__(self):
            self.added = None

        def upsert(self, vectors, ids):
            self.added = list(zip(ids, vectors))
            return ["vec-1"]

        def query(self, query_vector, top_k):
            return [{"id": "vec-1", "chunk_id": "chunk-1", "score": 0.5, "metadata": {"top_k": top_k}}]

    store = Store()
    adapter = VFSVectorStoreAdapter(store, store_id="qdrant")
    chunks = create_vfs_graphrag_adapters(VFSGraphRAGAdapterConfig(use_mocks=True)).chunking.chunk_text(
        "hello",
        parent_record_id="record-1",
    )
    embeddings, vectors = VFSEmbeddingAdapter(type("E", (), {"embed": lambda self, texts: [[0.1, 0.2]]})()).embed_chunks(
        chunks
    )

    updated = adapter.add_embeddings(embeddings, vectors)
    search_results = adapter.search([0.1, 0.2], top_k=1)

    assert store.added == [(embeddings[0].embedding_id, [0.1, 0.2])]
    assert updated[0].vector_store_id == "qdrant"
    assert updated[0].embedding_vector_id == "vec-1"
    assert search_results == [
        {
            "embedding_vector_id": "vec-1",
            "chunk_id": "chunk-1",
            "score": 0.5,
            "metadata": {"top_k": 1},
        }
    ]


def test_optional_ipfs_datasets_imports_raise_clear_dependency_error(monkeypatch):
    real_import_module = importlib.import_module

    def blocked_import(name, *args, **kwargs):
        if name.startswith("ipfs_datasets_py"):
            raise ImportError("blocked for test")
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr("importlib.import_module", blocked_import)

    with pytest.raises(VFSGraphRAGDependencyError, match="UnifiedGraphRAGProcessor"):
        VFSGraphRAGAdapters.create(VFSGraphRAGAdapterConfig(use_mocks=False))


def test_live_graphrag_marker_is_registered(pytestconfig):
    markers = pytestconfig.getini("markers")

    assert any(marker.startswith("live_graphrag:") for marker in markers)
    assert "IPFS_KIT_VFS_GRAPHRAG_LIVE" in next(
        marker for marker in markers if marker.startswith("live_graphrag:")
    )


@pytest.mark.live_graphrag
@pytest.mark.skipif(
    os.environ.get("IPFS_KIT_VFS_GRAPHRAG_LIVE") != "1",
    reason="set IPFS_KIT_VFS_GRAPHRAG_LIVE=1 to run live VFS GraphRAG adapters",
)
def test_live_ipfs_datasets_adapters_are_explicit_opt_in():
    adapters = create_vfs_graphrag_adapters(VFSGraphRAGAdapterConfig(use_mocks=False))

    assert adapters.processor
    assert adapters.embeddings
    assert adapters.chunking
    assert adapters.vector_store
    assert adapters.knowledge_graph
    assert adapters.query_optimizer
