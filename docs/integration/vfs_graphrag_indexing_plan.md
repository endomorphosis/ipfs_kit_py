# VFS GraphRAG Indexing Integration Plan

This plan describes how to integrate `ipfs_datasets_py` GraphRAG, vector search,
knowledge graph extraction, and dataset metadata tools into the `ipfs_kit_py`
virtual filesystem layer. The goal is to make every supported virtual
filesystem searchable by metadata, embeddings, and graph relationships while
keeping metadata exportable and reproducible.

## Goals

- Index virtual filesystem content from IPFS, Synapse, Storacha, Filecoin pin,
  Walrus, Parquet VFS, Git VFS, local VFS buckets, and future fsspec backends.
- Maintain a canonical VFS metadata record for every indexed file, directory,
  content object, dataset, and derived chunk.
- Generate text chunks and embeddings for vector search.
- Extract entities and relationships for knowledge graph search.
- Support hybrid search across vector similarity, metadata filters, and graph
  traversal.
- Store indexing state in a durable, exportable format so a VFS can be copied,
  audited, restored, or shared with its search metadata intact.
- Keep live indexing optional and dependency-gated so existing filesystem
  behavior remains lightweight.

## Existing Components To Build On

### `ipfs_kit_py` VFS and Metadata Surfaces

- `ipfs_kit_py/vfs_manager.py` already centralizes VFS operations and lazily
  initializes pin metadata, Arrow metadata, filesystem journal, dataset storage,
  and optional acceleration components.
- `ipfs_kit_py/fs_journal_integration.py` maps virtual paths to CIDs, tracks
  directories, and stores path metadata around filesystem writes.
- `ipfs_kit_py/parquet_vfs_integration.py` exposes Parquet datasets through an
  fsspec-compatible VFS with `/datasets`, `/metadata`, and `/queries` virtual
  paths.
- `ipfs_kit_py/git_vfs_translator.py` defines VFS file metadata, snapshots,
  content maps, mount metadata, and exportable `.ipfs_kit/vfs_metadata` state.
- `ipfs_kit_py/integrated_search.py` already sketches
  `MetadataEnhancedGraphRAG`, combining Arrow metadata filtering with graph and
  vector search.
- `ipfs_kit_py/arrow_metadata_index.py`, `pin_metadata_index.py`, and
  `metadata_sync_handler.py` provide indexing and synchronization anchors.
- `ipfs_kit_py/ipfs_fsspec.py` and `enhanced_fsspec.py` provide fsspec-facing
  filesystems that can be wrapped with indexing hooks.

### `ipfs_datasets_py` GraphRAG and Search Surfaces

`ipfs_datasets_py` exports these capabilities from its top-level package when
dependencies are available:

- `UnifiedGraphRAGProcessor`, `GraphRAGConfiguration`, `GraphRAGResult`
- `GraphRAGProcessor` and `MockGraphRAGProcessor` legacy compatibility classes
- `GraphRAGQueryOptimizer`, `UnifiedGraphRAGQueryOptimizer`, `QueryRewriter`,
  and `QueryBudgetManager`
- `KnowledgeGraph`, `KnowledgeGraphExtractor`, `Entity`, and `Relationship`
- `IPFSEmbeddings`, `EmbeddingModel`, `EmbeddingRequest`, `EmbeddingResponse`,
  `Chunker`, and `ChunkingStrategy`
- `BaseVectorStore`, `QdrantVectorStore`, `ElasticsearchVectorStore`, and
  `FAISSVectorStore`
- `IPFSKnnIndex`

These should be treated as optional imports. The VFS should still function when
GraphRAG dependencies are absent, but search/index APIs should return clear
dependency errors or mock-mode results when explicitly requested.

## Proposed Architecture

Add a new indexing layer under `ipfs_kit_py`:

```text
ipfs_kit_py/vfs_graphrag_index.py
ipfs_kit_py/vfs_graphrag_schema.py
ipfs_kit_py/vfs_graphrag_export.py
ipfs_kit_py/vfs_graphrag_fsspec.py
```

The modules should remain small and separable:

- `vfs_graphrag_schema.py`: dataclasses and schema helpers for canonical
  metadata records, chunks, embeddings, entities, relationships, and manifests.
- `vfs_graphrag_index.py`: indexing orchestration and adapters to
  `ipfs_datasets_py` GraphRAG, embeddings, vector stores, and knowledge graph
  extraction.
- `vfs_graphrag_export.py`: import/export of VFS metadata, vectors, graph data,
  manifests, and filesystem snapshots.
- `vfs_graphrag_fsspec.py`: fsspec wrappers/hooks that can index reads, writes,
  and listings without modifying every backend class by hand.

## Canonical Metadata Model

Every indexed object should have a canonical metadata record.

Required fields:

```json
{
  "schema": "ipfs_kit_py.vfs.graphrag.record.v1",
  "record_id": "vfsrec:...",
  "namespace": "default",
  "backend": "ipfs",
  "protocol": "ipfs",
  "path": "ipfs://...",
  "normalized_path": "/...",
  "content_id": "...",
  "content_hash": "...",
  "size_bytes": 0,
  "mime_type": "application/octet-stream",
  "type": "file",
  "created_at": "...",
  "modified_at": "...",
  "indexed_at": "...",
  "metadata": {},
  "tags": [],
  "lineage": {},
  "security": {},
  "export": {}
}
```

Derived records:

- Chunk records: stable chunk id, parent record id, byte offsets, text offsets,
  chunk text hash, extraction method, and language.
- Embedding records: chunk id, model id, dimension, vector store id, embedding
  checksum, and creation time.
- Knowledge graph records: entity id, entity type, aliases, source chunk ids,
  relationship id, subject, predicate, object, confidence, and provenance.
- Filesystem snapshot records: namespace, backend bindings, root paths, index
  CIDs, metadata CIDs, vector index CIDs, graph export CIDs, and journal range.

This model should map cleanly into:

- Arrow/Parquet tables for metadata export and fast filtering.
- JSONL for portable manifests and audit trails.
- CAR/IPLD for content-addressed bundles.
- Vector store documents for semantic search.
- Knowledge graph triples or property-graph nodes/edges.

## Indexing Pipeline

### 1. Discovery

The indexer should discover objects from multiple inputs:

- fsspec listings from `ipfs://`, `synapse://`, `storacha://`, `filecoin://`,
  `walrus://`, and `parquet-ipfs://`.
- `VFSManager` indexes and bucket registries.
- Filesystem journal entries since a checkpoint.
- Git VFS snapshots and `.ipfs_kit/vfs_metadata` files.
- Pin metadata index records.

Discovery produces canonical records without downloading full content unless
content extraction is requested.

### 2. Metadata Normalization

Normalize backend-specific fields into common keys:

- `cid`, `commp`, `blob_id`, `digest`, `pin_request_id`, and `sui_object_id`
  become explicit backend metadata while `content_id` stores the primary lookup
  id.
- `path`, `protocol`, `backend`, `namespace`, and `mount_id` establish VFS
  identity.
- `size`, `mime_type`, `mtime`, tags, encryption flags, policy data, proof data,
  and replication data become searchable metadata.

### 3. Content Extraction

For supported file types, extract searchable text:

- Plain text, Markdown, JSON, YAML, CSV, and source code by default.
- PDF, audio, images, HTML, and office documents through optional
  `ipfs_datasets_py` content discovery or extraction tools when available.
- Parquet and Arrow datasets through schema summaries, column statistics, and
  sampled row text.

Extraction should be bounded by policy:

- maximum file size
- maximum bytes per file
- allowed MIME types
- excluded paths
- privacy/encryption flags
- sampling rate

### 4. Chunking and Embeddings

Use `ipfs_datasets_py` chunking and embedding abstractions when available:

- Generate chunks using stable chunk ids based on record id, byte/text offsets,
  and chunk hash.
- Generate embeddings through configured `EmbeddingModel` or `IPFSEmbeddings`.
- Store vectors in a pluggable vector store: FAISS for local default, Qdrant or
  Elasticsearch for service-backed deployments, and `IPFSKnnIndex` where useful.
- Keep enough metadata with every vector to reconstruct path, backend, content
  id, chunk offsets, and source record.

### 5. Knowledge Graph Extraction

Use `KnowledgeGraphExtractor` or `UnifiedGraphRAGProcessor` to extract:

- entities from file content, file paths, metadata, dataset schemas, commit
  messages, and directory structure
- relationships such as `contains`, `links_to`, `derived_from`, `same_content_as`,
  `pinned_by`, `stored_on`, `belongs_to_bucket`, `mentions`, and domain-specific
  relationships extracted from text
- provenance links back to record ids and chunk ids

The graph should support both content relationships and filesystem topology.

### 6. Incremental Updates

Incremental indexing should use checkpoints:

- journal sequence or timestamp
- bucket registry `last_updated`
- Git VFS snapshot id
- pin metadata update time
- content hash/checksum
- metadata schema version

On write/delete/move operations, fsspec wrappers and `VFSManager` hooks should
enqueue indexing events rather than blocking filesystem operations on expensive
embedding or graph extraction work.

## Search APIs

Add a high-level search interface:

```python
searcher = VFSGraphRAGIndex.from_vfs_manager(vfs_manager)

searcher.search(
    query="housing assistance policy",
    namespaces=["wallet", "datasets"],
    backends=["ipfs", "walrus"],
    metadata_filters=[("mime_type", "=", "text/markdown")],
    graph_hops=2,
    top_k=20,
)
```

Search modes:

- metadata-only filtering
- vector-only similarity
- graph-only traversal
- hybrid metadata plus vector search
- hybrid vector plus graph expansion
- filesystem-topology search: directory, mount, bucket, backend, and snapshot
  constraints

Return shape:

```json
{
  "query": "...",
  "results": [
    {
      "record_id": "...",
      "path": "ipfs://...",
      "backend": "ipfs",
      "content_id": "...",
      "score": 0.92,
      "score_parts": {
        "vector": 0.8,
        "metadata": 0.1,
        "graph": 0.02
      },
      "snippet": "...",
      "metadata": {},
      "graph_context": [],
      "chunks": []
    }
  ],
  "facets": {},
  "explain": {}
}
```

## Export and Import

Add export bundles that can preserve the filesystem and search state together.

Export formats:

- `manifest.json`: schema version, root records, backends, checkpoints,
  capabilities, and export options.
- `metadata.parquet`: canonical VFS records.
- `chunks.parquet`: extracted chunks.
- `embeddings.parquet` or vector-store native export.
- `graph.nodes.parquet` and `graph.edges.parquet` or JSONL equivalents.
- `journal.jsonl`: optional filesystem journal slice.
- `filesystem.json`: VFS namespace, mount table, bucket registry, path maps, and
  backend binding metadata.
- optional CAR files for content-addressed export.

Import modes:

- metadata-only: restore search metadata without content.
- metadata-plus-indexes: restore vector and graph indexes.
- full snapshot: restore metadata, indexes, journal, path maps, and referenced
  content bundles when present.

Exports should be content-addressable where possible. The export manifest should
record checksums for each artifact.

## VFS Integration Points

### `VFSManager`

Add indexing lifecycle methods:

- `enable_graphrag_indexing(config=None)`
- `index_path(path, backend=None, recursive=False, **options)`
- `index_namespace(namespace, **options)`
- `search(query=None, metadata_filters=None, graph_filters=None, **options)`
- `export_index(output_path, format="directory", **options)`
- `import_index(input_path, mode="metadata-plus-indexes", **options)`
- `get_index_status()`

### fsspec Wrappers

Add a wrapper that can decorate any filesystem:

```python
indexed_fs = IndexedVFSFileSystem(fs, indexer=indexer, namespace="default")
```

The wrapper should hook:

- `put_file`, `pipe_file`, and writes to enqueue indexing
- `rm`, `mv`, and delete operations to tombstone metadata
- `info` and `ls` to enrich results with index metadata when requested
- `cat_file` and reads optionally for read-through extraction/indexing

### Journaling

Filesystem journal entries should become indexing events. This avoids missing
changes made through APIs that do not directly call the fsspec wrapper.

## Configuration

Example config:

```yaml
graphrag_indexing:
  enabled: true
  namespace: default
  index_root: ~/.ipfs_kit/graphrag_index
  vector_store:
    type: faiss
    path: ~/.ipfs_kit/graphrag_index/faiss
  knowledge_graph:
    type: local
    path: ~/.ipfs_kit/graphrag_index/kg
  extraction:
    max_file_size_mb: 25
    max_text_bytes: 1048576
    include_mime_types:
      - text/*
      - application/json
      - application/yaml
      - application/pdf
    exclude_globs:
      - "**/.git/**"
      - "**/node_modules/**"
  embeddings:
    model: sentence-transformers/all-MiniLM-L6-v2
    batch_size: 32
  incremental:
    use_journal: true
    checkpoint_interval_seconds: 60
  export:
    include_vectors: true
    include_graph: true
    include_journal: true
```

## Security and Privacy

- Do not index encrypted/private files unless explicitly allowed by policy.
- Preserve access-control metadata in search results.
- Support redaction filters for export.
- Record whether snippets or embeddings were derived from sensitive content.
- Keep live retrieval optional for content-addressed records that may require
  credentials or private gateways.

## Testing Strategy

- Unit-test schema normalization without optional heavy dependencies.
- Mock `ipfs_datasets_py` GraphRAG, embedding, vector store, and KG components.
- Test VFS indexing against in-memory/mock fsspec filesystems.
- Test journal-driven incremental updates.
- Test export/import round trips on a tiny virtual filesystem.
- Add optional live tests guarded by environment variables and explicit pytest
  markers.

## Implementation Phases

1. Audit and schema design: document current VFS metadata, GraphRAG APIs, and
   canonical record schema.
2. Build `vfs_graphrag_schema.py` and local index storage for metadata, chunks,
   embeddings, and graph records.
3. Build `VFSGraphRAGIndex` orchestration with optional `ipfs_datasets_py`
   adapters and mock fallbacks.
4. Add fsspec wrapper hooks and `VFSManager` lifecycle/search methods.
5. Implement vector search and metadata-filtered hybrid search.
6. Implement knowledge graph extraction, traversal, and graph-expanded search.
7. Implement export/import bundles for metadata, vector indexes, graph records,
   journals, and filesystem maps.
8. Add tests, docs, CLI/MCP endpoints, and daemon-supervised implementation
   tasks.

## Deliverables

- `ipfs_kit_py/vfs_graphrag_schema.py`
- `ipfs_kit_py/vfs_graphrag_index.py`
- `ipfs_kit_py/vfs_graphrag_export.py`
- `ipfs_kit_py/vfs_graphrag_fsspec.py`
- `docs/integration/vfs_graphrag_indexing.md`
- tests for schema, indexing, search, fsspec wrappers, export/import, and VFS
  manager integration
- optional CLI/MCP commands for indexing, search, status, export, and import
