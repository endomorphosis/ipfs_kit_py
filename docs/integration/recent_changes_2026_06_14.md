# Recent Integration Changes - 2026-06-14

This page summarizes the `ipfs_kit_py` changes completed during the recent
supervised implementation and Walrus alignment work. It is intended as a quick
orientation for users upgrading from the previous package state.

## Status

All three supervised implementation tracks are complete:

| Track | Task board | Completed work |
| --- | --- | --- |
| Walrus fsspec backend | `TODO_WALRUS_FSSPEC.md` | 7 / 7 tasks complete |
| fsspec backend improvements | `TODO_FSSPEC_BACKENDS.md` | 8 / 8 tasks complete |
| VFS GraphRAG indexing | `TODO_VFS_GRAPHRAG_INDEXING.md` | 12 / 12 tasks complete |

The authoritative progress records are the state JSON files under
`data/agent_supervisor/ipfs_kit_todo/state/`. The markdown task boards have
also been updated to checked/completed state.

## Walrus Backend

Walrus support is now exposed as a normal fsspec backend through `walrus://`.

Implemented user-facing behavior:

- `WalrusStorageClient` handles publisher, aggregator, API spec, object reads,
  delete URL resolution, bearer auth, storage epochs, deletable/permanent
  flags, and Walrus response normalization.
- `WalrusFileSystem` supports `cat_file`, `pipe_file`, `put_file`, `get_file`,
  `open(..., "rb")`, `open(..., "wb")`, `info`, `exists`, `ls`, `rm`, and
  `ukey`.
- Direct blob-id reads work without an index entry when an aggregator URL is configured.
- Logical paths are backed by a local JSON index at `~/.cache/ipfs_kit_py/walrus/index.json` unless `index_path` is supplied.
- Listing is local-index backed; it does not enumerate every remote Walrus blob.
- `info()` and `ls(..., detail=False)` follow fsspec-native behavior and return protocol-less names such as `team/notes.txt`.

`ipfs_kit_py` now delegates the implementation to the standalone `walrus-fsspec` package while preserving:

- `ipfs_kit_py.walrus_storage` and `ipfs_kit_py.walrus_fsspec` import paths
- `WALRUS_*` environment variables
- `ABBY_RUNTIME_WALRUS_*` environment aliases
- `VITE_WALRUS_STORAGE_*` environment aliases
- the `~/.cache/ipfs_kit_py/walrus/index.json` default index path

Install metadata now declares `walrus-fsspec>=0.1.0` in the core dependencies,
the `walrus` extra, the `full` extra, `requirements.txt`, and the legacy
`setup.py` fallback dependency list. The lazy import feature metadata also
declares `walrus-fsspec` for first-use dependency recovery.

See `docs/integration/walrus_fsspec.md` for configuration, examples, and limitations.

## fsspec Backends

The enhanced fsspec layer now has clearer protocol registration and method coverage for:

| Protocol | Backend | Notes |
| --- | --- | --- |
| `ipfs://` | IPFS enhanced filesystem | CID-oriented IPFS operations |
| `synapse://` | Synapse filesystem | CommP-oriented reads, writes, listings, info/status |
| `storacha://` | Storacha filesystem | CID-oriented upload, read, list, delete, mock/live modes |
| `filecoin://` | Filecoin Pin filesystem | Pin/upload/status plus retrieval when cached or configured |
| `walrus://` | Walrus filesystem | Blob-id and index-backed logical path operations |

The backend work added shared helpers for protocol normalization, standard file
info dictionaries, backend capability reporting, and consistent
content-addressed alias behavior.

Important behavior to expect:

- These backends are content-addressed; upload paths are usually aliases, not mutable remote paths.
- Mocked unit tests cover default behavior without live credentials.
- Live tests are opt-in via backend-specific environment gates.
- Storacha and Filecoin Pin can fall back to mock clients unless `require_live` is set.

See `docs/integration/fsspec_integration.md` and `docs/integration/fsspec_backends.md` for the method matrix and examples.

## VFS GraphRAG Indexing

The VFS GraphRAG track added a local, exportable indexing layer for virtual
filesystem metadata, chunks, embeddings, knowledge graph records, snapshots,
and checkpoints.

Implemented capabilities include:

- canonical VFS GraphRAG schema records
- local index storage that does not require optional GraphRAG dependencies
- optional adapters for `ipfs_datasets_py` GraphRAG, embedding, vector, and
    knowledge graph components
- fsspec wrapper hooks for write, delete, move, listing, and optional read-through indexing
- `VFSManager` indexing lifecycle, status, search, export, and import APIs
- metadata, vector, hybrid, graph, and graph-expanded hybrid search
- export/import bundles for metadata and index state
- deterministic tests plus optional live integration gates

The default local index root used by feature adapters is
`~/.cache/ipfs_kit_py/vfs_graphrag_index` unless an `index_path` is supplied.

See `docs/integration/vfs_graphrag_indexing.md` for usage and limitations.

## Public Surfaces

The recent work is intentionally exposed across all main user surfaces.

Python imports:

```python
from ipfs_kit_py import (
    VFSGraphRAGIndex,
    WalrusFileSystem,
    WalrusStorageClient,
    create_walrus_filesystem,
    register_fsspec_implementations,
)
```

CLI commands:

```bash
ipfs-kit walrus status
ipfs-kit walrus ls
ipfs-kit walrus get walrus://example.txt
ipfs-kit walrus put walrus://example.txt --content "hello"
ipfs-kit walrus delete walrus://example.txt

ipfs-kit fsspec protocols
ipfs-kit fsspec status --protocol walrus
ipfs-kit fsspec read walrus://example.txt
ipfs-kit fsspec write walrus://example.txt --content "hello"

ipfs-kit graphrag status
ipfs-kit graphrag search "example query"
ipfs-kit graphrag export --output /tmp/vfs-graphrag-export.json
```

MCP tool names:

- `walrus_status`, `walrus_list`, `walrus_get`, `walrus_put`, `walrus_delete`
- `fsspec_list_protocols`, `fsspec_backend_status`, `fsspec_read`, `fsspec_write`
- `vfs_graphrag_status`, `vfs_graphrag_search`,
  `vfs_graphrag_metadata_search`, `vfs_graphrag_vector_search`,
  `vfs_graphrag_hybrid_search`, `vfs_graphrag_graph_search`,
  `vfs_graphrag_graph_hybrid_search`, `vfs_graphrag_export`

Browser dashboard SDK namespaces:

- `MCP.Walrus`
- `MCP.FSSpec`
- `MCP.VFSGraphRAG`

The shared `ipfs_kit_py.feature_exposure` module keeps these wrapper surfaces
aligned, and `tests/test_feature_exposure_surfaces.py` verifies the CLI, MCP
dashboard, browser SDK, and TypeScript declarations expose the expected feature
names.

## Validation Summary

Recent validation covered:

- Walrus storage and fsspec tests with mocked HTTP transports
- fsspec backend tests for Synapse, Storacha, Filecoin Pin, and shared helpers
- VFS GraphRAG schema, storage, adapter, fsspec hook, search, graph, export,
  manager, CLI, and feature exposure tests
- compile checks for touched Python modules
- live Walrus validation in the standalone `walrus-fsspec` repository,
  including HTTP, CLI owner-signed operations, and fsspec end-to-end filesystem
  operations

Live Walrus tests remain opt-in because they require public Testnet endpoints
and, for owner-signed delete behavior, a configured Sui/Walrus wallet. Do not
write wallet recovery material into docs, source files, shell history, or test
fixtures.
