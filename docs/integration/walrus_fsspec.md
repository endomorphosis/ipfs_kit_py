# Walrus fsspec Integration

The Walrus fsspec backend exposes Walrus blobs through the standard `fsspec`
filesystem interface. `ipfs_kit_py` uses the standalone `walrus-fsspec` package
as the canonical backend while preserving the historical `ipfs_kit_py` import
paths, environment variable aliases, and default cache location. It supports
direct blob-id reads and path-like logical names backed by a local JSON index.

Walrus itself is content-addressed blob storage. The path semantics in this
backend come from the local index at `~/.cache/ipfs_kit_py/walrus/index.json`
unless you pass a custom `index_path`.

## Requirements

Current package metadata installs the Walrus runtime dependencies used by this
backend during normal package installation: `walrus-fsspec`, `fsspec`, and
`httpx`. The `walrus` extra remains available for explicit installs and older
environments:

```bash
pip install "ipfs_kit_py[walrus]"
```

When code reaches Walrus through the lazy import helper or the high-level
`create_walrus_filesystem()` factory, missing declared feature dependencies are
installed automatically with pip at first use. Set
`IPFS_KIT_AUTO_INSTALL_LAZY_DEPS=0` to disable runtime installs, or set
`IPFS_KIT_LAZY_INSTALL_TIMEOUT` to change the default 300 second install
timeout.

Import the backend before using `fsspec.open` in environments where fsspec
entry point discovery has not loaded it yet:

```python
import ipfs_kit_py.walrus_fsspec  # registers walrus:// with fsspec
```

## Public Surfaces

Walrus is exposed through the Python package root, the CLI, MCP tools, and the
dashboard browser SDK:

```python
from ipfs_kit_py import WalrusFileSystem, WalrusStorageClient, create_walrus_filesystem
```

```bash
ipfs-kit walrus status
ipfs-kit walrus ls
ipfs-kit walrus get datasets/example.json
ipfs-kit walrus put datasets/example.json --content '{"ok": true}'
ipfs-kit walrus delete datasets/example.json
```

MCP clients can call `walrus_status`, `walrus_list`, `walrus_get`,
`walrus_put`, and `walrus_delete`. Browser dashboard clients can use
`MCP.Walrus.status()`, `MCP.Walrus.list()`, `MCP.Walrus.get()`,
`MCP.Walrus.put()`, and `MCP.Walrus.delete()` from `/mcp-client.js` or the
packaged `mcp-sdk.js` files.

The same exposure layer publishes fsspec helpers through `ipfs-kit fsspec`,
MCP `fsspec_*` tools, and `MCP.FSSpec`; VFS GraphRAG is available through
`ipfs-kit graphrag`, MCP `vfs_graphrag_*` tools, and `MCP.VFSGraphRAG`.

## Configuration

Configure the endpoints with environment variables or pass the same values
directly to `fsspec.filesystem("walrus", ...)` / `WalrusFileSystem(...)`.

| Setting | Required for | Environment variables |
|---------|--------------|-----------------------|
| Publisher URL | Writes with `fs.pipe_file`, `fs.open(..., "wb")`, and `fs.put_file` | `WALRUS_PUBLISHER_URL`, `ABBY_RUNTIME_WALRUS_PUBLISHER_URL`, `VITE_WALRUS_STORAGE_PUBLISHER_URL` |
| Aggregator URL | Reads with `fsspec.open`, `fs.cat_file`, `fs.info`, and direct blob-id access | `WALRUS_AGGREGATOR_URL`, `ABBY_RUNTIME_WALRUS_AGGREGATOR_URL`, `VITE_WALRUS_STORAGE_AGGREGATOR_URL` |
| Delete URL | Deletes with `fs.rm` | `WALRUS_DELETE_URL`, `ABBY_RUNTIME_WALRUS_DELETE_URL`, `VITE_WALRUS_STORAGE_DELETE_URL` |
| Client token | Bearer auth when required by the service | `WALRUS_CLIENT_TOKEN`, `ABBY_RUNTIME_WALRUS_CLIENT_TOKEN`, `VITE_WALRUS_STORAGE_CLIENT_TOKEN` |
| Epochs | Default storage duration for writes | `WALRUS_EPOCHS`, `ABBY_RUNTIME_WALRUS_EPOCHS`, `VITE_WALRUS_STORAGE_EPOCHS` |
| Deletable | Default deletable flag for writes | `WALRUS_DELETABLE`, `ABBY_RUNTIME_WALRUS_DELETABLE`, `VITE_WALRUS_STORAGE_DELETABLE` |

Example shell configuration:

```bash
export WALRUS_PUBLISHER_URL="https://publisher.example.com"
export WALRUS_AGGREGATOR_URL="https://aggregator.example.com"
export WALRUS_DELETE_URL="https://publisher.example.com"
export WALRUS_CLIENT_TOKEN="..."
export WALRUS_EPOCHS=5
export WALRUS_DELETABLE=true
```

Endpoint values can be base service URLs, URLs ending in `/v1/blobs`, or
templates containing `{blobId}` / `{blob_id}`. Delete URL templates can also use
`{objectId}`, `{object_id}`, `{recordId}`, or `{record_id}`.

## Basic Usage

### Read With `fsspec.open`

```python
import fsspec
import ipfs_kit_py.walrus_fsspec  # noqa: F401

with fsspec.open("walrus://example.txt", "rb") as handle:
    data = handle.read()
```

`example.txt` is resolved through the local index. If no index entry exists and
the path has no slash, the backend treats it as a direct Walrus blob id.

### Write With `fs.pipe_file`

```python
import fsspec
import ipfs_kit_py.walrus_fsspec  # noqa: F401

fs = fsspec.filesystem("walrus")

entry = fs.pipe_file(
    "walrus://datasets/example.json",
    b'{"ok": true}\n',
    content_type="application/json",
    epochs=3,
    deletable=True,
)

print(entry["blob_id"])
print(fs.info("walrus://datasets/example.json"))
```

Writes upload bytes to the configured publisher URL. The returned Walrus blob
metadata is stored in the local index under the logical path, so later reads can
use `walrus://datasets/example.json`.

### Buffered Writes With `fsspec.open`

```python
import fsspec
import ipfs_kit_py.walrus_fsspec  # noqa: F401

with fsspec.open("walrus://reports/run-001.txt", "wb") as handle:
    handle.write(b"run complete\n")
```

The backend buffers data in memory and uploads it when the write handle closes.

## Direct Blob-Id Reads

Use direct blob-id paths when you already know the immutable Walrus blob id and
do not need a logical name:

```python
import fsspec
import ipfs_kit_py.walrus_fsspec  # noqa: F401

blob_id = "0xabc123..."

with fsspec.open(f"walrus://{blob_id}", "rb") as handle:
    data = handle.read()

fs = fsspec.filesystem("walrus")
same_data = fs.cat_file(f"walrus://{blob_id}")
```

Direct blob-id reads require `WALRUS_AGGREGATOR_URL` or one of its aliases. They
do not require the local index.

## Index-Backed Logical Paths

Logical paths are local aliases for blob ids:

```python
import fsspec
import ipfs_kit_py.walrus_fsspec  # noqa: F401

fs = fsspec.filesystem("walrus", index_path="/tmp/walrus-index.json")

fs.pipe_file("walrus://team/notes.txt", b"hello\n", content_type="text/plain")

assert fs.exists("walrus://team/notes.txt")
print(fs.ukey("walrus://team/notes.txt"))  # immutable blob id
print(fs.cat_file("walrus://team/notes.txt"))
print(fs.ls("walrus://team", detail=False))
```

Like other fsspec filesystems, `fs.info()` and `fs.ls(..., detail=False)` return
protocol-less names such as `team/notes.txt`; callers may still pass either
`team/notes.txt` or `walrus://team/notes.txt` to filesystem operations.

The index file stores metadata returned by the publisher, including fields such
as `blob_id`, `object_id`, `tx_digest`, `end_epoch`, `cost`, `size`,
`content_type`, and `created_at`.

## Deletion

```python
import fsspec
import ipfs_kit_py.walrus_fsspec  # noqa: F401

fs = fsspec.filesystem("walrus")
fs.rm("walrus://team/notes.txt")
```

Deletion calls the configured delete URL. For index-backed paths, the backend
uses the indexed `blob_id` and, when available, `object_id` or `record_id`. The
local index entry is removed only after the delete request succeeds.

## Limitations

- Listing is index-backed only. `fs.ls("walrus://")` shows logical paths in the
  local index; it does not enumerate every blob in a Walrus account or service.
- Direct blob-id paths are not included in listings unless you previously stored
  them as logical paths in the index.
- Nested paths are logical prefixes in the local index, not remote directories.
- Deletion requires a configured delete URL. Without one, `fs.rm` raises a
  configuration error.
- Delete semantics depend on the Walrus service and whether the blob was stored
  with deletion support, such as `deletable=True`.
- Write handles buffer content in memory until close, so use `fs.pipe_file` or
  `fs.put_file` deliberately for large blobs.
- The local index is machine-local unless you place `index_path` on shared
  storage or synchronize it yourself.
