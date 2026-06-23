# Walrus fsspec Backend Implementation Plan

This plan describes how to add a Python fsspec-compatible Walrus backend to
`ipfs_kit_py`, reusing the Walrus storage behavior already prototyped in the
wallet interface while matching the filesystem patterns that already exist in
this repository.

## Goals

- Add a first-class `walrus://` filesystem implementation for Python fsspec.
- Keep the implementation in `ipfs_kit_py`, where the current fsspec backends
  and integration docs live.
- Reuse the existing Walrus publisher, aggregator, deletion, and response
  normalization semantics from the wallet UI prototype.
- Support both direct blob-id access and optional path-like names through a
  local metadata index.
- Register the backend so `fsspec.filesystem("walrus")` and
  `fsspec.open("walrus://...")` work after installation.
- Provide a mocked test suite that does not require a live Walrus/Sui network.

## Existing Code To Reuse

The current Python fsspec implementation surface is split across two files:

- `ipfs_kit_py/ipfs_fsspec.py` contains the most complete local pattern. It
  defines `IPFSFSSpecFileSystem`, `IPFSFSSpecFile`, import-time protocol
  registration, metrics, cache integration, `open`, `cat`, `put`, `rm`, `ls`,
  and `info` behavior.
- `ipfs_kit_py/enhanced_fsspec.py` contains a newer multi-backend facade that
  registers `ipfs`, `filecoin`, `storacha`, and `synapse`, but the Storacha and
  Filecoin paths are placeholders. It is useful as a signpost, not as the best
  place to add Walrus behavior.

The embedded `ipfsspec` reference under `docs/ipfsspec` provides a cleaner
architecture for remote read-only content stores:

- `docs/ipfsspec/ipfsspec/async_ipfs.py` implements an async-first filesystem
  by inheriting from `fsspec.asyn.AsyncFileSystem`.
- It separates gateway/client behavior from filesystem behavior.
- It exposes sync methods via fsspec wrappers.
- Its package metadata registers protocols through the
  `[project.entry-points."fsspec.specs"]` group.

The Walrus-specific prototype is in the wallet UI:

- `wallet_interface/ui/src/services/walrusStorage.ts` resolves publisher,
  aggregator, and delete URLs; applies bearer auth; handles `epochs` and
  `deletable`/`permanent` query flags; parses nested Walrus response shapes;
  and builds blob gateway URLs.
- `wallet_interface/ui/src/lib/runtimeConfig.ts` and
  `wallet_interface/deploy/runtime-config.template.json` document the runtime
  configuration fields already used by the application.

## Recommended Architecture

Create two new Python modules:

```text
ipfs_kit_py/walrus_storage.py
ipfs_kit_py/walrus_fsspec.py
```

`walrus_storage.py` should contain protocol-specific HTTP logic and response
normalization. `walrus_fsspec.py` should contain the fsspec filesystem class and
optional file-like wrapper behavior. This keeps the client reusable by MCP,
storage manager, and higher-level APIs without tying everything to fsspec.

### WalrusStorageClient

Implement a small HTTP client around `httpx`.

Constructor inputs:

- `publisher_url`
- `aggregator_url`
- `delete_url`
- `client_token`
- `epochs`
- `deletable`
- `timeout`
- `headers`
- `index_path`

Environment fallback order should support concise backend variables first and
then project-specific aliases:

- `WALRUS_PUBLISHER_URL`
- `WALRUS_AGGREGATOR_URL`
- `WALRUS_DELETE_URL`
- `WALRUS_CLIENT_TOKEN`
- `WALRUS_EPOCHS`
- `WALRUS_DELETABLE`
- `ABBY_RUNTIME_WALRUS_PUBLISHER_URL`
- `ABBY_RUNTIME_WALRUS_AGGREGATOR_URL`
- `ABBY_RUNTIME_WALRUS_DELETE_URL`
- `ABBY_RUNTIME_WALRUS_CLIENT_TOKEN`
- `VITE_WALRUS_STORAGE_PUBLISHER_URL`
- `VITE_WALRUS_STORAGE_AGGREGATOR_URL`
- `VITE_WALRUS_STORAGE_DELETE_URL`
- `VITE_WALRUS_STORAGE_CLIENT_TOKEN`

Required methods:

- `resolve_publisher_blob_url(...) -> str`
- `resolve_aggregator_blob_url(blob_id: str) -> str`
- `resolve_delete_url(blob_id: str, object_id: str | None = None, record_id: str | None = None) -> str`
- `put_blob(data: bytes, content_type: str | None = None, **options) -> WalrusBlobInfo`
- `get_blob(blob_id: str, start: int | None = None, end: int | None = None) -> bytes`
- `head_blob(blob_id: str) -> dict`
- `delete_blob(blob_id: str, object_id: str | None = None, record_id: str | None = None) -> dict`
- `status() -> dict`

The response normalizer should extract at least:

- `blob_id`
- `object_id`
- `tx_digest`
- `end_epoch`
- `cost`
- `size`
- `gateway_url`
- `raw_response`

It must understand response variants already handled by the UI prototype:

- top-level `blobId`, `walrusBlobId`, `blobObjectId`, `suiObjectId`, `txDigest`
- `newlyCreated.blobObject.blobId`
- `newlyCreated.blob_object.blob_id`
- `alreadyCertified.blobId`
- `alreadyCertified.blob_id`
- `alreadyCertified.event.txDigest`
- nested `storage.endEpoch` and `storage.end_epoch`

### WalrusFileSystem

Implement `WalrusFileSystem` in `walrus_fsspec.py`.

Recommended base class:

```python
from fsspec.asyn import AsyncFileSystem, sync_wrapper
```

An async-first implementation follows the `ipfsspec` model and fits remote HTTP
storage better than a synchronous-only class. Sync wrappers can expose the usual
fsspec API.

Initial protocol support:

```python
protocol = "walrus"
```

Supported path forms:

- `walrus://{blob_id}` for direct content-addressed access.
- `walrus://{logical_name}` when a local index maps that path to a blob id.
- `walrus://` for root listing when an index is configured.

Required fsspec methods:

- `_strip_protocol(path)`
- `_cat_file(path, start=None, end=None, **kwargs)`
- `_pipe_file(path, value, **kwargs)`
- `_put_file(lpath, rpath, **kwargs)`
- `_get_file(rpath, lpath, **kwargs)`
- `_info(path, **kwargs)`
- `_exists(path, **kwargs)`
- `_rm_file(path, **kwargs)`
- `_ls(path, detail=True, **kwargs)`
- `open(path, mode="rb", ...)`
- `ukey(path)` returning the immutable blob id when known.

Read behavior:

- Resolve logical names through the index first.
- Fall back to treating the path as a blob id.
- Retrieve bytes from the configured aggregator URL.
- Support byte slicing locally at first. Add HTTP range requests later if the
  aggregator reliably supports them.

Write behavior:

- `pipe_file("walrus://name", b"...")` uploads bytes with the publisher.
- `put_file(local_path, "walrus://name")` uploads local file bytes.
- Store returned blob metadata in the local index when an index is enabled.
- Return or expose the new blob id through metadata and `info`.

Delete behavior:

- Use `delete_url` only when configured.
- Support URL templates containing `{blobId}`, `{objectId}`, and `{recordId}`.
- Remove local index entries after a successful delete.
- Raise a clear error when deletion is requested without delete backend config.

Listing behavior:

- Walrus blobs are not inherently hierarchical. `ls` should list local index
  entries when an index exists.
- Without an index, `ls("walrus://")` should return an empty list or a clear
  unsupported-listing result. It should not imply global account enumeration
  unless a real Walrus listing API is integrated later.

## Metadata Index

Add an optional JSON index to bridge Walrus blob IDs into fsspec path semantics.

Default path:

```text
~/.cache/ipfs_kit_py/walrus/index.json
```

Index entry shape:

```json
{
  "schema": "ipfs_kit_py.walrus.index.v1",
  "items": {
    "example.txt": {
      "name": "example.txt",
      "blob_id": "...",
      "object_id": "...",
      "tx_digest": "...",
      "end_epoch": 123,
      "cost": 1000,
      "size": 12,
      "content_type": "text/plain",
      "created_at": "2026-06-13T00:00:00Z",
      "gateway_url": "https://.../v1/blobs/..."
    }
  }
}
```

The first implementation can use a simple atomic JSON rewrite. A later version
can add file locking if concurrent writers become common.

## Package Integration

Update `pyproject.toml`:

```toml
[project.optional-dependencies]
walrus = [
  "fsspec>=2023.3.0",
  "httpx>=0.24.0",
]

[project.entry-points."fsspec.specs"]
walrus = "ipfs_kit_py.walrus_fsspec.WalrusFileSystem"
```

Also register during module import for editable installs and local development:

```python
try:
    import fsspec
    fsspec.register_implementation("walrus", WalrusFileSystem, clobber=True)
except Exception:
    logger.debug("Walrus fsspec registration skipped", exc_info=True)
```

Add a convenience constructor:

```python
def create_walrus_filesystem(**kwargs) -> WalrusFileSystem:
    return WalrusFileSystem(**kwargs)
```

Optionally add `walrus` to the lightweight `VFSBackendRegistry` in
`ipfs_fsspec.py` once the core filesystem is tested.

## Test Plan

Create `tests/test_walrus_storage.py`:

- URL resolution appends `/v1/blobs` when needed.
- `epochs` and `deletable`/`permanent` query flags are applied.
- Aggregator blob URLs are escaped correctly.
- Delete URL templates resolve `{blobId}`, `{objectId}`, and `{recordId}`.
- Authorization header is added only when a client token is configured.
- Error messages are extracted from text, `message`, `error`, and nested error
  objects.
- Response normalization handles top-level, `newlyCreated`, and
  `alreadyCertified` variants.

Create `tests/test_walrus_fsspec.py`:

- `fsspec.filesystem("walrus", ...)` can instantiate the class.
- `fs.pipe_file("walrus://example.txt", b"hello")` uploads and records index
  metadata.
- `fs.cat_file("walrus://example.txt")` resolves through the index.
- `fs.cat_file("walrus://{blob_id}")` works without an index entry.
- `fs.open("walrus://example.txt", "rb").read()` returns bytes.
- `fs.info(...)`, `fs.exists(...)`, and `fs.ls("walrus://")` work from the
  local index.
- `fs.rm(...)` calls the delete backend and removes index metadata.
- Missing publisher/aggregator config produces actionable exceptions.

Use mocked `httpx` transports so tests do not require a live Walrus/Sui network.

## Implementation Phases

1. Add `WalrusStorageClient`, URL helpers, response normalization, and mocked
   storage-client tests.
2. Add `WalrusFileSystem` with read, write, info, exists, delete, and local-index
   behavior.
3. Register the `walrus` protocol through entry points and import-time fsspec
   registration.
4. Add high-level helpers and optional VFS registry wiring.
5. Add docs and examples for environment config, direct blob access, path-indexed
   access, and limitations around global listing.
6. Run focused tests, then run the broader fsspec-related test subset.

## Known Constraints

- Walrus is blob-addressed, not naturally path-addressed. The fsspec path layer
  should be explicit about its optional local index.
- Listing should initially be index-backed only.
- Deletion depends on deployment-specific delete support and should fail clearly
  when `delete_url` is absent.
- Live integration tests should be opt-in and skipped unless real Walrus
  publisher/aggregator environment variables are configured.
