# VFS GraphRAG Indexing TODO

This task board converts the VFS GraphRAG indexing implementation plan into a
queue compatible with the `ipfs_accelerate_py` todo daemon and supervisor.

The checkbox section is compatible with the generic todo daemon in
`ipfs_accelerate_py.agent_supervisor.todo_daemon`. The detailed
`## vfs-graphrag-*` blocks are compatible with the implementation daemon parser
when invoked with `task_header_prefix="## vfs-graphrag-"`.

## Daemon Task Board

<!-- vfs-graphrag-daemon-task-board:start -->
- [x] Task checkbox-1: Audit VFS metadata and GraphRAG integration surfaces.
- [x] Task checkbox-2: Define canonical VFS GraphRAG metadata schemas.
- [x] Task checkbox-3: Implement local VFS GraphRAG index storage.
- [x] Task checkbox-4: Build `ipfs_datasets_py` GraphRAG adapter layer.
- [x] Task checkbox-5: Add fsspec wrapper hooks for indexing VFS operations.
- [x] Task checkbox-6: Add `VFSManager` indexing lifecycle and search APIs.
- [x] Task checkbox-7: Implement vector, metadata, and hybrid search.
- [x] Task checkbox-8: Implement knowledge graph extraction and graph search.
- [x] Task checkbox-9: Implement export/import bundles for filesystem metadata and indexes.
- [x] Task checkbox-10: Add CLI and MCP surfaces for indexing, search, and export.
- [x] Task checkbox-11: Add deterministic tests and optional live integration gates.
- [x] Task checkbox-12: Document VFS GraphRAG indexing usage and limitations.
<!-- vfs-graphrag-daemon-task-board:end -->

## vfs-graphrag-001 Audit VFS metadata and GraphRAG integration surfaces.

- status: completed
- completion: automatic
- priority: P0
- track: audit
- depends on:
- outputs: docs/integration/vfs_graphrag_audit.md
- validation: python -m compileall ipfs_kit_py/vfs_manager.py ipfs_kit_py/integrated_search.py
- acceptance: The audit identifies VFS metadata sources, journal events, fsspec backends, `ipfs_datasets_py` GraphRAG APIs, vector stores, knowledge graph extractors, and export/import gaps.

Implementation notes:

- Inspect `vfs_manager.py`, `fs_journal_integration.py`,
  `parquet_vfs_integration.py`, `git_vfs_translator.py`, `ipfs_fsspec.py`,
  `enhanced_fsspec.py`, `integrated_search.py`, `arrow_metadata_index.py`, and
  `pin_metadata_index.py`.
- Inspect top-level `ipfs_datasets_py` exports for GraphRAG, embeddings, vector
  stores, chunking, knowledge graph extraction, and query optimization.

## vfs-graphrag-002 Define canonical VFS GraphRAG metadata schemas.

- status: completed
- completion: automatic
- priority: P0
- track: schema
- depends on: vfs-graphrag-001
- outputs: ipfs_kit_py/vfs_graphrag_schema.py, tests/test_vfs_graphrag_schema.py
- validation: pytest tests/test_vfs_graphrag_schema.py -q
- acceptance: Dataclasses or typed dictionaries define canonical records for VFS objects, chunks, embeddings, entities, relationships, snapshots, checkpoints, and export manifests.

Implementation notes:

- Include backend, protocol, namespace, path, normalized path, content id,
  content hash, MIME type, size, timestamps, tags, lineage, security metadata,
  and export metadata.
- Provide serialization helpers for JSON, JSONL, and Arrow/Parquet-friendly
  dictionaries.
- Include schema version constants and migration hooks.

## vfs-graphrag-003 Implement local VFS GraphRAG index storage.

- status: completed
- completion: automatic
- priority: P0
- track: index
- depends on: vfs-graphrag-002
- outputs: ipfs_kit_py/vfs_graphrag_index.py, tests/test_vfs_graphrag_index_storage.py
- validation: pytest tests/test_vfs_graphrag_index_storage.py -q
- acceptance: A local index can persist and query metadata records, chunk records, embedding metadata, graph node/edge records, and checkpoints without requiring optional GraphRAG dependencies.

Implementation notes:

- Store lightweight metadata as JSONL or Parquet depending on available
  dependencies.
- Keep deterministic record ids and chunk ids.
- Add checkpoint support for journal timestamps, bucket registry updates, Git
  VFS snapshots, and metadata schema version.
- Make storage paths configurable with a default under `~/.ipfs_kit/graphrag_index`.

## vfs-graphrag-004 Build `ipfs_datasets_py` GraphRAG adapter layer.

- status: completed
- completion: automatic
- priority: P0
- track: adapter
- depends on: vfs-graphrag-002, vfs-graphrag-003
- outputs: ipfs_kit_py/vfs_graphrag_index.py, tests/test_vfs_graphrag_adapters.py
- validation: pytest tests/test_vfs_graphrag_adapters.py -q
- acceptance: Optional adapters can call or mock `UnifiedGraphRAGProcessor`, embeddings, chunking, vector stores, knowledge graph extraction, and query optimizers from `ipfs_datasets_py`.

Implementation notes:

- Use optional imports with clear dependency errors.
- Provide mock adapters for default tests.
- Normalize adapter outputs into the canonical schema rather than leaking
  backend-specific result shapes.
- Keep vector store selection configurable: FAISS local default, Qdrant or
  Elasticsearch when configured.

## vfs-graphrag-005 Add fsspec wrapper hooks for indexing VFS operations.

- status: completed
- completion: automatic
- priority: P0
- track: fsspec
- depends on: vfs-graphrag-003, vfs-graphrag-004
- outputs: ipfs_kit_py/vfs_graphrag_fsspec.py, tests/test_vfs_graphrag_fsspec.py
- validation: pytest tests/test_vfs_graphrag_fsspec.py -q
- acceptance: `IndexedVFSFileSystem` can wrap a filesystem and enqueue or perform indexing on write, delete, move, listing, and optional read-through operations.

Implementation notes:

- Hook `put_file`, `pipe_file`, writes, `rm`, `mv`, `info`, `ls`, and optionally
  `cat_file`.
- Do not block ordinary filesystem writes on expensive embeddings unless
  synchronous indexing is explicitly requested.
- Support namespace and backend labels on wrapped filesystems.

## vfs-graphrag-006 Add `VFSManager` indexing lifecycle and search APIs.

- status: completed
- completion: automatic
- priority: P0
- track: vfs-manager
- depends on: vfs-graphrag-003, vfs-graphrag-005
- outputs: ipfs_kit_py/vfs_manager.py, tests/test_vfs_manager_graphrag.py
- validation: pytest tests/test_vfs_manager_graphrag.py -q
- acceptance: `VFSManager` exposes `enable_graphrag_indexing`, `index_path`, `index_namespace`, `search`, `export_index`, `import_index`, and `get_index_status` with mocked indexers.

Implementation notes:

- Integrate with existing pin metadata, Arrow metadata, filesystem journal, and
  dataset manager initialization paths.
- Make indexing optional and dependency-gated.
- Support async methods with sync-safe bridges consistent with existing
  `VFSManager` style.

## vfs-graphrag-007 Implement vector, metadata, and hybrid search.

- status: completed
- completion: automatic
- priority: P0
- track: search
- depends on: vfs-graphrag-004, vfs-graphrag-006
- outputs: ipfs_kit_py/vfs_graphrag_index.py, tests/test_vfs_graphrag_search.py
- validation: pytest tests/test_vfs_graphrag_search.py -q
- acceptance: Search supports metadata-only filters, vector-only similarity, and hybrid metadata-plus-vector ranking with facets and explainable score parts.

Implementation notes:

- Reuse concepts from `integrated_search.MetadataEnhancedGraphRAG`.
- Return VFS-aware result fields: record id, path, backend, protocol, content id,
  score, score parts, snippet, metadata, chunks, and facets.
- Keep deterministic tests with fake embeddings and in-memory vector stores.

## vfs-graphrag-008 Implement knowledge graph extraction and graph search.

- status: completed
- completion: automatic
- priority: P1
- track: graph
- depends on: vfs-graphrag-004, vfs-graphrag-007
- outputs: ipfs_kit_py/vfs_graphrag_index.py, tests/test_vfs_graphrag_graph.py
- validation: pytest tests/test_vfs_graphrag_graph.py -q
- acceptance: The indexer extracts or accepts entities and relationships, stores graph records with provenance, and supports graph-only and graph-expanded hybrid search.

Implementation notes:

- Model filesystem topology relationships such as `contains`, `stored_on`,
  `belongs_to_bucket`, `derived_from`, `same_content_as`, `pinned_by`, and
  `links_to`.
- Link every graph entity and relationship to source records and chunks.
- Support graph hop limits and entity-type filters.

## vfs-graphrag-009 Implement export/import bundles for filesystem metadata and indexes.

- status: completed
- completion: automatic
- priority: P0
- track: export
- depends on: vfs-graphrag-003, vfs-graphrag-007, vfs-graphrag-008
- outputs: ipfs_kit_py/vfs_graphrag_export.py, tests/test_vfs_graphrag_export.py
- validation: pytest tests/test_vfs_graphrag_export.py -q
- acceptance: Export/import round trips preserve metadata records, chunks, vector metadata, graph nodes/edges, checkpoints, filesystem maps, and manifest checksums for a small virtual filesystem.

Implementation notes:

- Export `manifest.json`, `metadata.parquet` or JSONL, `chunks.parquet`,
  embeddings metadata, graph nodes/edges, journal slices, and filesystem maps.
- Support metadata-only, metadata-plus-indexes, and full-snapshot import modes.
- Record checksums and schema versions for every artifact.

## vfs-graphrag-010 Add CLI and MCP surfaces for indexing, search, and export.

- status: completed
- completion: automatic
- priority: P1
- track: cli-mcp
- depends on: vfs-graphrag-006, vfs-graphrag-009
- outputs: ipfs_kit_py/cli.py, ipfs_kit_py/mcp/controllers, tests/test_vfs_graphrag_cli.py
- validation: pytest tests/test_vfs_graphrag_cli.py -q
- acceptance: Users can run index, search, status, export, and import operations from CLI and MCP surfaces using mocked VFS GraphRAG services.

Implementation notes:

- Add commands such as `ipfs-kit vfs index`, `ipfs-kit vfs search`,
  `ipfs-kit vfs graphrag-status`, `ipfs-kit vfs export-index`, and
  `ipfs-kit vfs import-index`.
- Keep payloads JSON-friendly for daemon and dashboard integration.

## vfs-graphrag-011 Add deterministic tests and optional live integration gates.

- status: completed
- completion: automatic
- priority: P0
- track: tests
- depends on: vfs-graphrag-005, vfs-graphrag-006, vfs-graphrag-007, vfs-graphrag-008, vfs-graphrag-009
- outputs: tests/test_vfs_graphrag_*.py
- validation: pytest tests/test_vfs_graphrag_schema.py tests/test_vfs_graphrag_index_storage.py tests/test_vfs_graphrag_adapters.py tests/test_vfs_graphrag_fsspec.py tests/test_vfs_manager_graphrag.py tests/test_vfs_graphrag_search.py tests/test_vfs_graphrag_graph.py tests/test_vfs_graphrag_export.py -q
- acceptance: The VFS GraphRAG suite runs without live IPFS, vector database, or LLM services; live tests are opt-in through explicit environment variables and pytest markers.

Implementation notes:

- Use fake embeddings, mock graph extraction, and in-memory vector stores for
  default tests.
- Cover dependency-missing and mock-mode behavior.
- Add tiny fixture files for text, JSON, Markdown, and Parquet-like metadata.

## vfs-graphrag-012 Document VFS GraphRAG indexing usage and limitations.

- status: completed
- completion: automatic
- priority: P1
- track: docs
- depends on: vfs-graphrag-006, vfs-graphrag-009, vfs-graphrag-010
- outputs: docs/integration/vfs_graphrag_indexing.md, README.md
- validation: python -m compileall ipfs_kit_py/vfs_graphrag_schema.py ipfs_kit_py/vfs_graphrag_index.py ipfs_kit_py/vfs_graphrag_export.py ipfs_kit_py/vfs_graphrag_fsspec.py
- acceptance: Documentation explains configuration, indexing workflows, search examples, export/import bundles, privacy controls, dependency requirements, and backend limitations.

Implementation notes:

- Link to `docs/integration/vfs_graphrag_indexing_plan.md`.
- Include examples for indexing a namespace, searching with metadata and vector
  filters, graph-expanded search, and exporting a searchable VFS snapshot.
- Clearly mark optional dependencies and live-service requirements.
