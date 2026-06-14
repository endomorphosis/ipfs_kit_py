# VFS GraphRAG Indexing

VFS GraphRAG indexing stores searchable metadata for virtual filesystem
objects, derived text chunks, embedding metadata, graph entities, graph
relationships, snapshots, and checkpoints. The local implementation is designed
to work without live IPFS, vector database, LLM, or `ipfs_datasets_py`
services; optional adapters can add richer chunking, embeddings, and knowledge
graph extraction when those dependencies are installed.

This page documents the implemented user-facing workflow. The original design
plan is in [vfs_graphrag_indexing_plan.md](./vfs_graphrag_indexing_plan.md).

## What Gets Indexed

The canonical schema lives in `ipfs_kit_py/vfs_graphrag_schema.py` and includes:

- `VFSObjectRecord`: file, directory, dataset, content object, or tombstone
  metadata.
- `VFSChunkRecord`: searchable extracted text chunks with source offsets and
  hashes.
- `VFSEmbeddingRecord`: embedding metadata and vector-store identifiers. The
  local index stores vector metadata and can rank against vectors carried in
  record metadata.
- `VFSEntityRecord` and `VFSRelationshipRecord`: graph nodes and edges with
  provenance back to VFS records and chunks.
- `VFSSnapshotRecord` and `VFSCheckpointRecord`: snapshot and incremental
  indexing state.

All local records persist under the configured index root as JSONL by default.
`storage_format="parquet"` or `"auto"` can be used only when pandas and a
Parquet engine are available.

## Configuration

Manager-level indexing is enabled through `VFSManager`:

```python
from pathlib import Path
from ipfs_kit_py.vfs_manager import VFSManager

vfs = VFSManager(storage_path=Path("/srv/ipfs-kit-state"))

enabled = vfs.enable_graphrag_indexing_sync(
    index_path="/srv/ipfs-kit-state/.vfs_graphrag_index",
    namespace="research",
    storage_format="jsonl",
    use_mocks=True,
)
assert enabled["success"]
```

Important options:

- `index_path`: local directory for index artifacts. When omitted,
  `VFSManager` uses `.vfs_graphrag_index` under its `storage_path`, or under
  the current working directory.
- `namespace`: logical index partition, defaulting to `default`.
- `storage_format`: `jsonl`, `parquet`, or `auto`. JSONL is the portable
  default and has no optional dependency.
- `use_mocks`: default `True`. Mock adapters make chunking, embedding metadata,
  and graph extraction deterministic for local and test workflows.
- `indexer`: optional injected service object. If supplied, the manager
  delegates lifecycle, search, export, and import methods to that object.

For direct use, construct the local index:

```python
from ipfs_kit_py.vfs_graphrag_index import VFSGraphRAGIndex

index = VFSGraphRAGIndex(
    "/srv/ipfs-kit-state/.vfs_graphrag_index",
    namespace="research",
    storage_format="jsonl",
)
```

## Indexing Workflows

### Index One Path

```python
result = vfs.index_path_sync(
    "/data/reports/policy.md",
    namespace="research",
    backend="local",
    protocol="file",
    tags=["policy", "public"],
    metadata={"collection": "reports", "classification": "public"},
    extract_content=True,
)
```

`extract_content=True` reads bounded text from common text-like formats such as
Markdown, JSON, YAML, CSV, Python, JavaScript, TypeScript, and plain text. The
manager stores an object record and, when adapters are enabled, derived chunks,
embedding metadata, and graph records.

### Index A Namespace

```python
result = vfs.index_namespace_sync(
    "research",
    root_path="/data/reports",
    backend="local",
    protocol="file",
    recursive=True,
    metadata={"collection": "reports"},
)
```

If `root_path` is omitted, `VFSManager.storage_path` is used. If neither is set,
the operation succeeds with `indexed=0` and a warning.

### Index Through fsspec Hooks

`IndexedVFSFileSystem` can wrap a fsspec-compatible filesystem and emit
structured indexing events on writes, deletes, moves, listings, and optionally
read-through operations.

```python
import fsspec
from ipfs_kit_py.vfs_graphrag_fsspec import IndexedVFSFileSystem
from ipfs_kit_py.vfs_graphrag_index import VFSGraphRAGIndex

index = VFSGraphRAGIndex("/tmp/vfs-graphrag", namespace="research")
fs = IndexedVFSFileSystem(
    fsspec.filesystem("file"),
    indexer=index,
    namespace="research",
    backend="local",
    synchronous_indexing=True,
    index_read_through=False,
)

fs.pipe_file("/tmp/example.txt", b"GraphRAG-indexed content")
status = index.stats()
```

When `synchronous_indexing=False`, the wrapper retains events in
`fs.events` and sends them to an indexer queue when the indexer exposes
`enqueue`, `put`, or `append`.

## Search Examples

### Metadata Search

```python
results = vfs.search_sync(
    "housing",
    namespaces=["research"],
    backends=["local"],
    metadata_filters={"collection": "reports", "classification": "public"},
    search_type="metadata",
    top_k=20,
)
```

Metadata filters match top-level record fields first, then keys inside the
record `metadata` dictionary.

### Vector Search

```python
from ipfs_kit_py.vfs_graphrag_schema import (
    VFSChunkRecord,
    VFSEmbeddingRecord,
    VFSObjectRecord,
)

record = index.upsert_object(
    VFSObjectRecord(
        namespace="research",
        backend="local",
        protocol="file",
        path="/data/reports/policy.md",
        metadata={"classification": "public"},
    )
)
chunk = index.upsert_chunk(
    VFSChunkRecord(
        parent_record_id=record.record_id,
        namespace="research",
        path=record.path,
        text="housing assistance policy and eligibility",
    )
)
index.upsert_embedding(
    VFSEmbeddingRecord(
        chunk_id=chunk.chunk_id,
        parent_record_id=record.record_id,
        model_id="demo",
        dimension=3,
        metadata={"vector": [0.1, 0.3, 0.9]},
    )
)

results = index.search(
    query_vector=[0.1, 0.2, 0.8],
    search_type="vector",
    top_k=5,
)
```

The dependency-free vector ranking reads vector-like arrays from embedding or
chunk metadata keys such as `vector` or `embedding`. Production deployments can
store vectors in FAISS, Qdrant, Elasticsearch, or another service through an
injected adapter, but the local index does not manage those external stores.

### Hybrid Search

```python
results = index.search(
    query="eligibility",
    query_vector=[0.1, 0.2, 0.8],
    metadata_filters={"classification": "public"},
    namespaces=["research"],
    search_type="hybrid",
    top_k=10,
    facet_fields=["backend", "mime_type"],
)
```

Hybrid search applies metadata filters first, then combines metadata, text, and
vector score parts.

### Graph-Expanded Search

```python
index.extract_graph_for_object(record, chunks=[chunk], include_topology=True)

results = index.search(
    "policy",
    namespaces=["research"],
    search_type="hybrid",
    graph_hops=1,
    relationship_predicates=["contains", "links_to", "same_content_as"],
    top_k=10,
)
```

Graph expansion uses stored entity and relationship provenance. The built-in
topology extractor creates relationships such as `stored_on`, `links_to`,
`same_content_as`, `belongs_to_bucket`, `contains`, `derived_from`, and
`pinned_by` from path and metadata fields. Domain-specific entities and
relationships can be inserted with `add_graph_records`.

## CLI Usage

The CLI uses the same local MCP controller service as the default MCP routes.
Every command requires an index root.

```bash
python -m ipfs_kit_py.cli vfs index \
  --index-root /tmp/vfs-graphrag \
  --namespace research \
  --path /data/reports/policy.md \
  --backend local \
  --protocol file \
  --mime-type text/markdown \
  --tag policy \
  --metadata-json '{"collection":"reports","classification":"public"}'
```

```bash
python -m ipfs_kit_py.cli vfs search "housing policy" \
  --index-root /tmp/vfs-graphrag \
  --namespace research \
  --type hybrid \
  --filters-json '{"classification":"public"}' \
  --top-k 10
```

```bash
python -m ipfs_kit_py.cli vfs search \
  --index-root /tmp/vfs-graphrag \
  --namespace research \
  --type vector \
  --query-vector '[0.1, 0.2, 0.8]'
```

```bash
python -m ipfs_kit_py.cli vfs search "policy" \
  --index-root /tmp/vfs-graphrag \
  --namespace research \
  --type graph \
  --hop-limit 2 \
  --entity-type vfs_object
```

```bash
python -m ipfs_kit_py.cli vfs graphrag-status \
  --index-root /tmp/vfs-graphrag \
  --namespace research
```

MCP routes are available on controllers that register
`VFSGraphRAGController`:

- `POST /api/vfs/graphrag/index`
- `POST /api/vfs/graphrag/search`
- `GET|POST /api/vfs/graphrag/status`
- `POST /api/vfs/graphrag/export`
- `POST /api/vfs/graphrag/import`

## Export And Import Bundles

`VFSGraphRAGExportBundle` writes portable directory bundles with a
`manifest.json` and deterministic JSONL artifacts:

- `metadata.jsonl`
- `chunks.jsonl`
- `embeddings.jsonl`
- `graph.nodes.jsonl`
- `graph.edges.jsonl`
- `snapshots.jsonl`
- `checkpoints.jsonl`
- `filesystem.json`, when included
- `journal.jsonl`, when included

Each manifest artifact records schema, count, byte length, SHA-256 checksum,
and whether the artifact is required. The manifest also records a bundle
checksum and capability flags.

```python
from ipfs_kit_py.vfs_graphrag_export import VFSGraphRAGExportBundle

manifest = VFSGraphRAGExportBundle(index).export_index(
    "/tmp/vfs-snapshot",
    filesystem_map={"roots": ["/data/reports"]},
    journal_entries=[{"sequence": 1, "op": "write", "path": "/data/reports/policy.md"}],
    include_filesystem=True,
    include_journal=True,
    metadata={"purpose": "searchable VFS snapshot"},
)
```

```python
from ipfs_kit_py.vfs_graphrag_export import VFSGraphRAGExportBundle
from ipfs_kit_py.vfs_graphrag_index import VFSGraphRAGIndex

restored = VFSGraphRAGIndex("/tmp/restored-vfs-graphrag", namespace="research")
result = VFSGraphRAGExportBundle.import_index(
    "/tmp/vfs-snapshot",
    restored,
    mode="metadata-plus-indexes",
    verify_checksums=True,
)
```

CLI equivalents:

```bash
python -m ipfs_kit_py.cli vfs export-index \
  --index-root /tmp/vfs-graphrag \
  --namespace research \
  --output /tmp/vfs-snapshot

python -m ipfs_kit_py.cli vfs import-index \
  --index-root /tmp/restored-vfs-graphrag \
  --namespace research \
  --input /tmp/vfs-snapshot \
  --mode metadata-plus-indexes
```

Import modes:

- `metadata-only`: imports object metadata and checkpoints.
- `metadata-plus-indexes`: imports metadata, chunks, embedding metadata, graph
  records, snapshots, and checkpoints.
- `full-snapshot`: also returns `filesystem.json` and `journal.jsonl` payloads
  to the caller. It does not automatically recreate backend mounts or fetch
  referenced content.

## Privacy Controls

The schema includes `security`, `export`, `metadata`, and `tags` fields so
callers can record access-control policy, sensitivity labels, and export rules.
The local implementation does not enforce a policy engine by itself; callers
must apply their own filtering before indexing, search result display, and
export.

Recommended controls:

- Do not index encrypted or private files unless the caller has explicit
  authorization and the `security` metadata records that policy.
- Set `metadata` or `security` labels such as `classification`, `tenant`,
  `owner`, `redaction`, or `contains_pii` and use `metadata_filters` in
  user-facing search.
- Avoid storing sensitive snippets in `VFSChunkRecord.text` when only metadata
  search is required.
- Treat embeddings as derived content. Exclude them from bundles or store only
  non-sensitive embedding metadata when privacy policy requires it.
- Review `manifest.json`, `metadata.jsonl`, chunks, graph nodes, graph edges,
  `filesystem.json`, and `journal.jsonl` before sharing an exported bundle.
- Use `include_filesystem=False` and `include_journal=False` when path maps or
  journal entries reveal sensitive filesystem structure.

## Dependency Requirements

Required for the local index, CLI, MCP controller, and JSONL bundles:

- Python standard library.
- `ipfs_kit_py` schema, index, export, and controller modules.

Optional:

- `anyio` for `VFSManager` async/sync wrappers, already used elsewhere in the
  project.
- `fsspec` when wrapping external filesystems with `IndexedVFSFileSystem`.
- `pandas` plus a Parquet engine when using `storage_format="parquet"` or
  `"auto"` with Parquet available.
- `ipfs_datasets_py` GraphRAG, embeddings, chunking, vector store, and knowledge
  graph packages for production-quality extraction and retrieval adapters.
- Vector databases or local vector libraries such as FAISS, Qdrant, or
  Elasticsearch when an injected adapter manages live vector storage.

The dependency-free local path is suitable for deterministic tests, metadata
search, portable bundles, and simple vector/graph examples. It is not a
replacement for a production semantic retrieval stack.

## Backend Limitations

- The local index records VFS metadata; it does not pin, fetch, decrypt, or
  replicate content from IPFS, Filecoin, Storacha, Synapse, Walrus, Git, or
  other backends.
- Manager indexing of local paths uses filesystem metadata and bounded text
  extraction. Backend-specific discovery needs the corresponding VFS or fsspec
  integration to supply paths, CIDs, content IDs, and metadata.
- The fsspec wrapper observes operations performed through the wrapper. Changes
  made directly against the underlying backend are not captured unless another
  journal or indexer feeds them into the index.
- Delete and move operations create tombstone or replacement metadata records;
  they do not delete underlying backend objects.
- Graph search traverses stored graph records. Without extracted or inserted
  entities and relationships, graph search can only use topology records that
  have been generated.
- Local vector search ranks against vectors stored in record metadata. It does
  not build or persist an approximate nearest-neighbor index by itself.
- Export bundles are metadata and index snapshots. A `full-snapshot` import
  returns filesystem and journal payloads, but callers must restore actual
  mounts, path maps, credentials, and content separately.

