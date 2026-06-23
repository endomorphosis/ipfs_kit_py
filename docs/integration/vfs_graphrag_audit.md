# VFS GraphRAG Integration Audit

Task: `vfs-graphrag-001`

This audit inventories the current metadata and search surfaces that a VFS
GraphRAG indexer can build on. It also records the gaps that should be closed
before indexing, vector search, graph extraction, and export/import can be made
canonical across VFS backends.

## Summary

`ipfs_kit_py` already has several independent metadata sources:

- `VFSManager` wires together pin metadata, Arrow metadata, filesystem
  journaling, optional dataset storage, and optional compute acceleration.
- `FilesystemJournal` records file, directory, mount, metadata, checkpoint, and
  dataset events with path-level state recovery.
- `IPFSFilesystemInterface` keeps path-to-CID, directory, mount, and
  in-memory path metadata maps for journal-protected VFS operations.
- `ParquetVirtualFileSystem` exposes dataset and dataset-metadata virtual paths.
- `GitVFSTranslator` persists Git-derived VFS file metadata, snapshots,
  content maps, mount metadata, and JSON exports under `.ipfs_kit/vfs_metadata`.
- `ArrowMetadataIndex` stores CID-centric metadata in Parquet partitions and
  supports metadata filters and text search.
- `PinMetadataIndex` stores pin, VFS path, storage tier, integrity, analytics,
  and VFS operation metadata in DuckDB and Parquet.
- `ipfs_fsspec.py` and `enhanced_fsspec.py` expose fsspec-compatible backends
  and local VFS mount helpers.
- `integrated_search.py` sketches a hybrid search layer that combines Arrow
  metadata filtering with graph/vector search, but it is not VFS-specific.

The missing integration layer is a canonical VFS GraphRAG schema and adapter
that normalizes these records into stable object, chunk, embedding, entity,
relationship, snapshot, and checkpoint records.

## VFS Metadata Sources

### `ipfs_kit_py/vfs_manager.py`

`VFSManager` is the highest-level lifecycle surface. It lazily initializes:

- `pin_index` from `get_global_pin_metadata_index`
- `arrow_metadata_index` from `ArrowMetadataIndex`
- `filesystem_journal` from `FilesystemJournal`
- `dataset_manager` from `ipfs_datasets_integration`
- optional `compute_layer` from `ipfs_accelerate_py`

It also keeps an `_operation_buffer`, metrics cache, and storage root. A
GraphRAG indexer should attach here for manager-level lifecycle and expose
search APIs here after lower-level indexing exists.

Gap: there is no VFS GraphRAG index lifecycle, no checkpoint handoff from
manager state, and no public VFS search method that routes to metadata, vector,
or graph search.

### `ipfs_kit_py/fs_journal_integration.py`

`IPFSFilesystemInterface` is a journal-facing adapter. It tracks:

- `path_to_cid`
- `cid_to_path`
- `directory_structure`
- `mount_points`
- `path_metadata`

It accepts metadata in `write_file`, `mkdir`, `update_metadata`, and `mount`,
and removes or moves metadata on delete, rmdir, move, and unmount paths.
`FilesystemJournalIntegration` wraps these methods through
`FilesystemJournalManager`.

Gap: path metadata is process-local in the interface and is not normalized into
the Arrow index, pin index, or a durable GraphRAG record.

### `ipfs_kit_py/filesystem_journal.py`

`JournalOperationType` currently covers:

- `create`
- `delete`
- `rename`
- `write`
- `truncate`
- `metadata`
- `checkpoint`
- `mount`
- `unmount`
- `dataset`

Journal entries contain `entry_id`, `timestamp`, `operation_type`, `path`,
operation `data`, entry `metadata`, `status`, and optional transaction id.
Recovered filesystem state stores path type, timestamps, metadata, CIDs, sizes,
and mount flags. Dataset methods record `dataset_store` and `dataset_version`
events with provenance metadata.

Gap: journal entries are the best incremental indexing trigger, but there is no
stable journal sequence cursor exposed for GraphRAG checkpoints beyond
timestamps, checkpoint ids, and entry ids.

### `ipfs_kit_py/parquet_vfs_integration.py`

`ParquetVirtualFileSystem` exposes an fsspec-compatible virtual tree:

- `/datasets/{cid}.parquet`
- `/metadata/{cid}.json`
- `/queries/...`

Listings and `info()` return dataset size, type, content type, and dataset
metadata. Metadata JSON includes CID, dataset name, path, and bridge metadata.
`create_parquet_vfs_integration` can register the `parquet-ipfs` protocol.

Gap: dataset schema summaries, column statistics, sampled rows, and query files
are not normalized as chunkable text or graph facts.

### `ipfs_kit_py/git_vfs_translator.py`

`VFSFileMetadata` contains content hash, size, mime type, created/modified time,
Git blob hash, VFS block size, block links, and arbitrary metadata. `VFSSnapshot`
groups file changes by Git commit and parent VFS snapshots.
`GitVFSTranslator` stores:

- `.ipfs_kit/vfs_metadata/vfs_index.json`
- `.ipfs_kit/vfs_metadata/VFS_HEAD`
- `.ipfs_kit/vfs_metadata/snapshots/*.json`

The index includes snapshots, filesystem mounts, a content map, and a metadata
schema version. `export_vfs_metadata()` writes a JSON bundle with index and
snapshots.

Gap: this is the strongest snapshot/export surface, but imports are not paired
with the export, and content hashes are SHA-256 placeholders rather than
canonical IPFS CIDs when content has not been added to IPFS.

### `ipfs_kit_py/arrow_metadata_index.py`

`ArrowMetadataIndex` stores CID records in Parquet partitions. Its schema has:

- content identifiers: `cid`, `cid_version`, `multihash_type`
- basic metadata: `size_bytes`, `blocks`, `links`, `mime_type`
- storage status: `local`, `pinned`, `pin_types`, `replication`
- timestamps and access stats
- organization: `path`, `filename`, `extension`
- tags, structured metadata, and properties
- embedding flags: `embedding_available`, `embedding_type`,
  `embedding_dimensions`
- indexing metadata: `indexed_at`, `index_version`, `indexer_node_id`

The index supports `add`, `get_by_cid`, `update_stats`, `delete_by_cid`,
`query`, `search_text`, partition sync, Arrow C Data Interface export, and
metadata index DAG publishing.

Gap: embeddings are metadata flags only. There is no vector payload location,
chunk id, VFS namespace, backend protocol, security metadata, or graph
provenance field.

### `ipfs_kit_py/pin_metadata_index.py`

`EnhancedPinMetadata` tracks CID, size, type, name, timestamps, VFS path,
mount point, directory flag, storage tiers, primary tier, replication factor,
content hash, verification status, access pattern, hotness score, and predicted
access time.

`PinMetadataIndex` stores DuckDB tables for pins, traffic analytics, tier
analytics, and VFS operations. It exports pins to Parquet and can sync pin
metadata from journal operations through `_sync_pin_from_journal`. The
`get_parquet_info()` method explicitly notes that CAR export is not implemented
there.

Gap: Parquet export is pin-only, not a full VFS metadata/index bundle, and the
journal callback path is a stub pending journal callback support.

## fsspec Backends and Hook Points

### `ipfs_kit_py/ipfs_fsspec.py`

The primary fsspec class is `IPFSFSSpecFileSystem` with protocol `ipfs`.
It implements `ls`, `info`, `open`, `cat`, `put`, `rm`, metrics, tier checks,
replication-policy helpers, and `IPFSFSSpecFile` buffered reads/writes.
The module registers `ipfs` with fsspec and also provides:

- `get_filesystem`
- `VFSBackendRegistry`
- `VFSCacheManager`
- `VFSCore`
- `VFSReplicationManager`
- dual sync/async helpers such as `vfs_mount`, `vfs_write`, `vfs_read`,
  `vfs_ls`, `vfs_stat`, `vfs_copy`, and `vfs_move`
- placeholder filesystem classes for Storacha, Lotus, Lassie, and Arrow

Indexing hook points: `ls`, `info`, `cat`, `put`, `rm`, `IPFSFSSpecFile.flush`,
and VFSCore `mount`, `write`, `read`, `copy`, `move`, and `rmdir`.

Gap: hook points do not emit canonical indexing events or journal entries.

### `ipfs_kit_py/enhanced_fsspec.py`

The multi-backend `IPFSFileSystem` registers protocols:

- `ipfs`
- `filecoin`
- `storacha`
- `synapse`

It routes `ls`, `cat_file`, `put_file`, `get_file`, `exists`, and `info` based
on a `backend` value and stores backend configuration in `metadata`. IPFS and
Synapse have partial implementations. Filecoin and Storacha are mostly
`NotImplementedError` or existence placeholders.

Indexing hook points: backend-specific `ls`, `cat_file`, `put_file`,
`get_file`, `exists`, and `info` methods plus `get_backend_status` and
`get_backend_config`.

Gap: backend metadata is configuration metadata only. Results are not normalized
across `cid`, `commp`, Filecoin deal/proof fields, Storacha IDs, or future
Walrus blob IDs.

## Existing Search and GraphRAG Surfaces

### `ipfs_kit_py/integrated_search.py`

`MetadataEnhancedGraphRAG` combines `IPLDGraphDB` with `IPFSArrowIndex` and
supports:

- `hybrid_search`
- metadata-only search through Arrow filters
- vector-only graph search
- combined metadata-first vector ranking
- optional distributed query planning through `DistributedQueryOptimizer`

`SearchConnector` adds model/dataset search helpers, LangChain/LlamaIndex
retriever adapters, and custom embedding model fallback logic. `SearchBenchmark`
benchmarks metadata, vector, and hybrid search.

Gap: this search layer assumes CID/entity ids and generic AI/ML metadata. It
does not understand VFS namespaces, backend protocols, paths, chunks, journal
checkpoints, VFS snapshots, or export manifests.

### `ipfs_kit_py/ipld_knowledge_graph.py`

`IPLDGraphDB` is the local graph/vector primitive used by
`integrated_search.py`. It provides graph entities, relationships, embedding
generation, vector search, and IPLD-oriented persistence patterns. It can be an
internal fallback when `ipfs_datasets_py` GraphRAG imports are unavailable.

Gap: there is no adapter that converts VFS records into graph nodes/edges such
as `contains`, `mounted_at`, `pinned_by`, `stored_on`, `same_content_as`, or
`derived_from`.

## `ipfs_datasets_py` GraphRAG APIs

The installed `ipfs_datasets_py` package is discoverable at:

`/home/barberb/.local/lib/python3.12/site-packages/ipfs_datasets_py/__init__.py`

Current top-level import status:

```text
ImportError: cannot import name 'VectorIndexPartitioner' from 'ipfs_datasets_py.rag_query_optimizer'
```

The package `__init__.py` attempts to export these relevant symbols:

- `IPLDStorage`, `IPLDSchema`
- `DatasetSerializer`, `GraphDataset`, `GraphNode`,
  `VectorAugmentedGraphDataset`
- `DataInterchangeUtils`
- `UnixFSHandler`, `FixedSizeChunker`, `RabinChunker`
- `IPFSKnnIndex`
- `GraphRAGQueryOptimizer`, `GraphRAGQueryStats`, `VectorIndexPartitioner`
- `KnowledgeGraph`, `KnowledgeGraphExtractor`, `Entity`, `Relationship`
- `LLMInterface`, `MockLLMInterface`, `LLMConfig`, `PromptTemplate`,
  `LLMInterfaceFactory`, `GraphRAGPromptTemplates`
- `GraphRAGLLMProcessor`, `ReasoningEnhancer`
- `enhance_dataset_with_llm`

Additional module-level surfaces exist even though the package import fails:

- `rag_query_optimizer.py`: `GraphRAGQueryOptimizer`,
  `UnifiedGraphRAGQueryOptimizer`, `GraphRAGQueryStats`
- `query_optimizer.py`: `QueryOptimizer`, `VectorIndexOptimizer`,
  `KnowledgeGraphQueryOptimizer`, `HybridQueryOptimizer`
- `knowledge_graph_extraction.py`: `KnowledgeGraph`,
  `KnowledgeGraphExtractor`, `KnowledgeGraphExtractorWithValidation`,
  `Entity`, `Relationship`
- `ipld/vector_store.py`: `IPLDVectorStore`, `SearchResult`
- `ipfs_knn_index.py`: `IPFSKnnIndex`
- `llm_graphrag.py`: `GraphRAGLLMProcessor`, `ReasoningEnhancer`
- `unixfs_integration.py`: `FixedSizeChunker`, `RabinChunker`
- `ipfs_embeddings_py/*`: embedding helpers including
  `MultiModelEmbeddingGenerator`

The task plan also names expected newer GraphRAG APIs:

- `UnifiedGraphRAGProcessor`
- `GraphRAGConfiguration`
- `GraphRAGResult`
- `GraphRAGProcessor`
- `MockGraphRAGProcessor`
- `UnifiedGraphRAGQueryOptimizer`
- `QueryRewriter`
- `QueryBudgetManager`
- `IPFSEmbeddings`
- `EmbeddingModel`, `EmbeddingRequest`, `EmbeddingResponse`
- `Chunker`, `ChunkingStrategy`
- `BaseVectorStore`, `QdrantVectorStore`, `ElasticsearchVectorStore`,
  `FAISSVectorStore`

Gap: those newer names are not exported by the installed top-level package
observed in this worktree. The VFS adapter should use optional imports, support
direct module imports where available, and provide clear dependency errors when
requested GraphRAG features cannot be loaded.

## Vector Stores

Current vector-related surfaces:

- `ArrowMetadataIndex` has embedding availability/type/dimension metadata but
  no vector payload storage.
- `integrated_search.py` can query graph vector search through `IPLDGraphDB`.
- `ipfs_datasets_py.ipld.vector_store.IPLDVectorStore` is available by module.
- `ipfs_datasets_py.ipfs_knn_index.IPFSKnnIndex` is exported by the installed
  package source.
- `ipfs_datasets_py.dataset_serialization.VectorAugmentedGraphDataset` can
  model graph datasets with vectors.
- Local examples and docs mention FAISS, but there is no canonical VFS vector
  store binding.

Gap: no VFS record links a file/path to chunk ids, embedding ids, model ids,
vector store ids, dimensions, checksums, or exportable vector index artifacts.
FAISS, Qdrant, and Elasticsearch should remain optional plugin/service choices
rather than hard dependencies.

## Knowledge Graph Extractors

Current graph extraction/search surfaces:

- `ipfs_datasets_py.knowledge_graph_extraction.KnowledgeGraphExtractor`
  extracts entities and relationships when its optional NLP dependencies are
  available.
- `KnowledgeGraphExtractorWithValidation` adds semantic validation paths.
- `KnowledgeGraph`, `Entity`, and `Relationship` provide the graph data model.
- `ipfs_kit_py.ipld_knowledge_graph.IPLDGraphDB` provides an internal graph DB
  and vector search substrate.
- `integrated_search.MetadataEnhancedGraphRAG` uses graph entities and Arrow
  metadata together.

Gap: no extractor currently receives VFS-specific signals such as directory
topology, mount relationships, pin/storage tier relationships, Git ancestry,
dataset schema relationships, or same-content relationships across backends.

## Export and Import Gaps

Existing export surfaces:

- `ArrowMetadataIndex` writes Parquet partitions and can publish a metadata
  index DAG.
- `ArrowMetadataIndex` can export an Arrow C Data Interface handle.
- `PinMetadataIndex.export_to_parquet()` writes pin metadata to Parquet.
- `PinMetadataIndex.get_parquet_info()` reports Parquet location and explicitly
  notes CAR export is not implemented there.
- `GitVFSTranslator.export_vfs_metadata()` writes JSON index and snapshot data.
- `ParquetVirtualFileSystem` exposes dataset metadata as virtual JSON files.

Missing export/import pieces:

- No canonical VFS GraphRAG manifest.
- No export of object records, chunk records, embeddings, graph nodes/edges,
  vector-store metadata, journal checkpoint ranges, and backend bindings as one
  reproducible bundle.
- No import path for Git VFS export JSON back into manager/index state.
- No import path for pin Parquet or Arrow partitions into canonical VFS records.
- No CAR/IPLD bundle that contains both filesystem metadata and derived indexes.
- No schema versioning or migrations for VFS GraphRAG metadata.
- No stable content-addressed identifiers for derived chunks, embeddings,
  entities, relationships, and snapshots.

## Recommended Next Surfaces

The next implementation tasks should add:

- `vfs_graphrag_schema.py` with canonical object, chunk, embedding, entity,
  relationship, snapshot, checkpoint, and manifest records.
- `vfs_graphrag_index.py` with dependency-gated adapters to
  `ipfs_datasets_py`, `IPLDGraphDB`, Arrow metadata, and pin metadata.
- fsspec wrapper hooks that emit lightweight indexing events for `ls`, `info`,
  reads, writes, deletes, moves, mounts, and flushes.
- checkpoint support keyed by journal entry id/timestamp, Git VFS snapshot id,
  pin index update time, Arrow partition metadata, and schema version.
- export/import bundle support for JSONL/Parquet records plus optional CAR/IPLD
  artifacts and vector store sidecars.
- clear optional dependency handling for unavailable `ipfs_datasets_py`
  top-level imports and missing vector store backends.
