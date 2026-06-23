from ipfs_kit_py.vfs_graphrag_index import VFSGraphRAGIndex
from ipfs_kit_py.vfs_graphrag_schema import (
    VFSChunkRecord,
    VFSEmbeddingRecord,
    VFSEntityRecord,
    VFSObjectRecord,
    VFSRelationshipRecord,
)


def _record(index, path, content_id, *, bucket="atlas", vector=None, text=""):
    obj = index.upsert_object(
        VFSObjectRecord(
            namespace="research",
            backend="ipfs",
            protocol="ipfs",
            path=path,
            content_id=content_id,
            mime_type="text/markdown",
            tags=["graph"],
            metadata={"bucket": bucket},
        )
    )
    chunk = index.upsert_chunk(
        VFSChunkRecord(
            parent_record_id=obj.record_id,
            namespace=obj.namespace,
            path=obj.normalized_path,
            content_id=obj.content_id,
            chunk_index=0,
            text=text or f"Notes for {path}",
        )
    )
    if vector is not None:
        index.upsert_embedding(
            VFSEmbeddingRecord(
                chunk_id=chunk.chunk_id,
                parent_record_id=obj.record_id,
                model_id="fake",
                dimension=len(vector),
                metadata={"vector": vector},
            )
        )
    return obj, chunk


def test_extract_graph_accepts_entities_relationships_and_adds_provenance(tmp_path):
    index = VFSGraphRAGIndex(tmp_path)
    obj, chunk = _record(index, "/papers/quantum.md", "bafy-quantum")

    ada = VFSEntityRecord(name="Ada Lovelace", entity_type="person")
    project = VFSEntityRecord(name="Atlas", entity_type="project")
    result = index.extract_graph_for_object(
        obj,
        chunks=[chunk],
        entities=[ada, project],
        relationships=[
            VFSRelationshipRecord(
                subject_id=ada.entity_id,
                predicate="contributes_to",
                object_id=project.entity_id,
                relationship_type="semantic",
            )
        ],
    )

    stored_ada = index.get_entity(ada.entity_id)
    stored_relationship = next(
        rel for rel in result["relationships"] if rel.predicate == "contributes_to"
    )

    assert stored_ada is not None
    assert stored_ada.source_record_ids == [obj.record_id]
    assert stored_ada.source_chunk_ids == [chunk.chunk_id]
    assert stored_ada.provenance["extractor"] == "vfs_graph_topology"
    assert stored_relationship.source_record_ids == [obj.record_id]
    assert stored_relationship.source_chunk_ids == [chunk.chunk_id]


def test_topology_extraction_models_vfs_relationships(tmp_path):
    index = VFSGraphRAGIndex(tmp_path)
    first, chunk = _record(index, "/datasets/atlas/report.md", "bafy-shared", bucket="atlas")
    second, _ = _record(index, "/archive/report-copy.md", "bafy-shared", bucket="archive")

    result = index.extract_graph_for_object(
        first,
        chunks=[chunk],
        provenance={"source": "unit-test"},
    )

    predicates = {relationship.predicate for relationship in result["relationships"]}
    assert {"contains", "stored_on", "belongs_to_bucket", "links_to", "same_content_as"}.issubset(predicates)

    same_content_search = index.graph_search(
        query="/datasets/atlas/report.md",
        hop_limit=1,
        relationship_predicates=["same_content_as"],
    )
    related_ids = {item["record_id"] for item in same_content_search["results"]}
    assert first.record_id in related_ids
    assert second.record_id in related_ids


def test_graph_only_search_respects_hop_limits_and_entity_type_filters(tmp_path):
    index = VFSGraphRAGIndex(tmp_path)
    quantum, quantum_chunk = _record(index, "/papers/quantum.md", "bafy-quantum")
    graph, graph_chunk = _record(index, "/papers/graph.md", "bafy-graph")

    atlas = VFSEntityRecord(
        name="Atlas",
        entity_type="project",
        source_record_ids=[quantum.record_id],
        source_chunk_ids=[quantum_chunk.chunk_id],
    )
    protocol = VFSEntityRecord(
        name="GraphRAG Protocol",
        entity_type="concept",
        source_record_ids=[graph.record_id],
        source_chunk_ids=[graph_chunk.chunk_id],
    )
    index.add_graph_records(
        entities=[atlas, protocol],
        relationships=[
            VFSRelationshipRecord(
                subject_id=atlas.entity_id,
                predicate="uses",
                object_id=protocol.entity_id,
                source_record_ids=[quantum.record_id, graph.record_id],
                source_chunk_ids=[quantum_chunk.chunk_id, graph_chunk.chunk_id],
            )
        ],
    )

    one_hop = index.graph_search(query="Atlas", hop_limit=1, entity_types=["project"])
    zero_hop = index.graph_search(query="Atlas", hop_limit=0, entity_types=["project"])
    concept_only = index.graph_search(query="Atlas", hop_limit=1, entity_types=["concept"])

    one_hop_ids = {item["record_id"] for item in one_hop["results"]}
    zero_hop_ids = {item["record_id"] for item in zero_hop["results"]}

    assert quantum.record_id in zero_hop_ids
    assert graph.record_id not in zero_hop_ids
    assert {quantum.record_id, graph.record_id}.issubset(one_hop_ids)
    assert concept_only["results"] == []
    assert one_hop["results"][0]["score_parts"]["graph_match"] > 0


def test_graph_expanded_hybrid_search_adds_related_records(tmp_path):
    index = VFSGraphRAGIndex(tmp_path)
    seed, seed_chunk = _record(
        index,
        "/papers/vector.md",
        "bafy-vector",
        vector=[1.0, 0.0],
        text="Vector retrieval seed",
    )
    related, related_chunk = _record(
        index,
        "/papers/related.md",
        "bafy-related",
        text="Graph-only related context",
    )

    seed_entity = VFSEntityRecord(
        name="Vector Search",
        entity_type="concept",
        source_record_ids=[seed.record_id],
        source_chunk_ids=[seed_chunk.chunk_id],
    )
    related_entity = VFSEntityRecord(
        name="Graph Expansion",
        entity_type="concept",
        source_record_ids=[related.record_id],
        source_chunk_ids=[related_chunk.chunk_id],
    )
    index.add_graph_records(
        entities=[seed_entity, related_entity],
        relationships=[
            VFSRelationshipRecord(
                subject_id=seed_entity.entity_id,
                predicate="related_to",
                object_id=related_entity.entity_id,
                source_record_ids=[seed.record_id, related.record_id],
            )
        ],
    )

    vector_only = index.hybrid_search(query_vector=[1.0, 0.0], top_k=1)
    expanded = index.graph_hybrid_search(query_vector=[1.0, 0.0], graph_hops=1, top_k=5)

    assert [item["record_id"] for item in vector_only["results"]] == [seed.record_id]
    expanded_ids = {item["record_id"] for item in expanded["results"]}
    assert {seed.record_id, related.record_id}.issubset(expanded_ids)
    related_result = next(item for item in expanded["results"] if item["record_id"] == related.record_id)
    assert related_result["score_parts"]["graph_expansion"] > 0
    assert related_result["graph"]["entities"]
