# fsspec Backend Capabilities

For the 2026-06-14 summary of completed backend work and public exposure
updates, see [recent_changes_2026_06_14.md](recent_changes_2026_06_14.md).

This page documents the enhanced fsspec adapter in
`ipfs_kit_py.enhanced_fsspec`. It registers `ipfs://`, `synapse://`,
`storacha://`, and `filecoin://` and exposes protocol-specific filesystem
classes for each backend.

All four backends are content-addressed. A path such as
`storacha://reports/latest.json` or `filecoin://uploads/model.bin` is a local
write alias recorded by the filesystem instance after upload. The durable
identifier returned by the backend is the CID or CommP shown in `info()["cid"]`
or `info()["commp"]`. Re-opening a new filesystem instance should use the
content identifier unless an external index stores the alias mapping.

## Installation and Registration

Install the base fsspec support with:

```bash
pip install -e ".[fsspec]"
```

Filecoin Pin API support also uses the `filecoin_pin` extra:

```bash
pip install -e ".[fsspec,filecoin_pin]"
```

Importing `ipfs_kit_py.enhanced_fsspec` registers all enhanced protocols with
fsspec:

```python
import fsspec
import ipfs_kit_py.enhanced_fsspec  # registers ipfs, synapse, storacha, filecoin

fs = fsspec.filesystem("storacha")
```

The compatibility modules also register and export specific backends:

```python
from ipfs_kit_py.storacha_fsspec import StorachaFileSystem
from ipfs_kit_py.filecoin_pin_fsspec import FilecoinFileSystem
```

## Capability Matrix

| Backend | Protocol | Read | Write | List | Info/exists | Delete | `open()` | Path mutability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IPFS | `ipfs://` | `cat_file`, `get_file` | `put_file` | `ls` | `info`, `exists` | Not implemented by enhanced backend | Falls back to base fsspec behavior | Content-addressed CID paths; uploads return new content, not mutable paths |
| Synapse | `synapse://` | `cat_file`, `get_file`, `open(..., "rb")` | `put_file`, `pipe_file` | `ls` | `info`, `exists` | Not supported | Binary read only | Content-addressed CommP; aliases are local to the filesystem instance |
| Storacha | `storacha://` | `cat_file`, `get_file`, `open(..., "rb")` | `put_file`, `pipe_file` | `ls` | `info`, `exists` | `rm` / `rm_file` | Binary read only | Content-addressed CID; aliases are local and are not remote mutable paths |
| Filecoin Pin | `filecoin://` | Cached reads, or CID retrieval when configured | `put_file`, `pipe_file` | `ls` | `info`, `exists` | Not supported | Binary read only when retrieval is available | Content-addressed CID pin records; aliases are local and do not rename pinned content |

Unsupported write modes are explicit for Synapse, Storacha, and Filecoin:
`open(path, "wb")` raises `NotImplementedError`. Use `pipe_file()` for bytes or
`put_file()` for local files.

## Backend Details

### IPFS

Instantiate with fsspec, the convenience helper, or the class directly:

```python
import fsspec
from ipfs_kit_py.enhanced_fsspec import create_ipfs_filesystem

fs = fsspec.filesystem("ipfs")
fs = create_ipfs_filesystem()
```

Configuration is passed through `metadata` and `resources` to
`ipfs_kit_py.ipfs_kit.ipfs_kit`.

```python
fs = create_ipfs_filesystem(
    metadata={"role": "worker"},
    resources={"ipfs_path": "~/.ipfs"},
)
```

Required runtime configuration:

| Mode | Requirements |
| --- | --- |
| Live | Importable `ipfs_kit_py.ipfs_kit` and a configured IPFS client/daemon matching that client configuration. |
| Mock | No enhanced in-memory mock is provided by this backend; tests should inject or patch the IPFS client. |

Supported methods:

| Method | Behavior |
| --- | --- |
| `ls(path, detail=True)` | Calls `ipfs_ls_path` and returns fsspec dictionaries with `name`, `type`, `size`, `cid`, and `path`. |
| `cat_file(path, start=None, end=None)` | Calls `ipfs_cat_data`; byte ranges are sliced client-side. |
| `put_file(lpath, rpath)` | Adds local file bytes with `ipfs_add_data`; `rpath` is not a mutable destination path. |
| `get_file(rpath, lpath)` | Reads by CID/path and writes bytes to a local file. |
| `exists(path)` | Uses `ipfs_object_stat`. |
| `info(path)` | Uses `ipfs_object_stat` and returns CID-oriented metadata. |
| `get_backend_status()` | Calls `ipfs_id`. |

Content addressing: IPFS paths should be CIDs or CID subpaths. Uploading creates
new content. The enhanced backend does not implement MFS-style path mutation.

### Synapse

Instantiate with:

```python
import fsspec
from ipfs_kit_py.enhanced_fsspec import SynapseFileSystem, create_synapse_filesystem

fs = fsspec.filesystem("synapse", metadata={"network": "calibration"})
fs = SynapseFileSystem(metadata={"network": "calibration"})
fs = create_synapse_filesystem(metadata={"network": "calibration"})
```

Required runtime configuration:

| Mode | Requirements |
| --- | --- |
| Live | Importable `ipfs_kit_py.synapse_storage` plus Synapse SDK configuration accepted by `synapse_storage`, such as `network` and any wallet/private-key/provider settings required by the lower-level Synapse bridge. Live smoke tests are gated by `IPFS_KIT_LIVE_SYNAPSE=1`; `SYNAPSE_NETWORK` and `SYNAPSE_PRIVATE_KEY` may be used by tests. |
| Mock | No automatic in-memory fallback. Tests patch `ipfs_kit_py.synapse_storage.synapse_storage` with a mock. Missing dependency raises `ImportError`. |

Supported methods:

| Method | Behavior |
| --- | --- |
| `ls("synapse://", detail=True)` | Calls `synapse_list_stored_data`; names are normalized as `synapse://<commp>`. |
| `cat_file(path, start=None, end=None)` | Resolves a local alias to CommP when available, then calls `synapse_retrieve_data`; byte ranges are sliced client-side. |
| `pipe_file(path, value, mode="overwrite")` | Stores bytes with `synapse_store_data`; records the returned CommP against the requested alias. |
| `put_file(lpath, rpath)` | Calls `synapse_store_file`; records the returned CommP against `rpath`. |
| `get_file(rpath, lpath)` | Calls `synapse_retrieve_file` by CommP or local alias. |
| `exists(path)` | Checks the local alias index first, then `synapse_get_piece_status`. |
| `info(path)` | Returns CommP, size, provider, proof-set, and challenge-window metadata when available. |
| `open(path, "rb")` | Returns a `BytesIO` over `cat_file`. |
| `get_backend_status()` | Normalizes `synapse_storage.get_status()` and reports connection/configuration fields. |
| `get_backend_config()` | Returns `synapse_storage.get_configuration()`. |

Content addressing: Synapse retrieval is by CommP. Aliases passed to
`pipe_file()` or `put_file()` are in-memory conveniences and are not mutable
remote paths.

### Storacha

Instantiate with:

```python
import fsspec
from ipfs_kit_py.enhanced_fsspec import StorachaFileSystem, create_storacha_filesystem

fs = fsspec.filesystem("storacha")
fs = StorachaFileSystem(metadata={"api_key": "...", "space": "..."})
fs = create_storacha_filesystem(metadata={"api_key": "..."})
```

Required runtime configuration:

| Mode | Requirements |
| --- | --- |
| Mock | Default when no `metadata["api_key"]` and no `STORACHA_API_KEY` are present. The adapter uses an in-memory Storacha-compatible client with `mock_mode=True`. |
| Live | Provide `metadata["api_key"]` or `STORACHA_API_KEY`. Set `metadata={"require_live": True}` when missing credentials or imports should fail instead of using mock mode. Other metadata is passed to `storacha_kit`, including space or endpoint settings supported by that lower layer. Live smoke tests are gated by `IPFS_KIT_LIVE_STORACHA=1` and `STORACHA_API_KEY`. |

Supported methods:

| Method | Behavior |
| --- | --- |
| `ls("storacha://", detail=True)` | Calls `w3_list`; also includes aliases written by the current filesystem instance. |
| `cat_file(path, start=None, end=None)` | Resolves alias to CID, then reads cached bytes or calls `w3_cat`; byte ranges are sliced client-side. |
| `pipe_file(path, value, mode="overwrite")` | Writes bytes through a temporary file and calls `w3_up`; records the returned CID and alias. |
| `put_file(lpath, rpath)` | Calls `w3_up` for a local file; records the returned CID and alias. |
| `get_file(rpath, lpath)` | Reads with `cat_file` and writes bytes locally. |
| `exists(path)` | Checks local alias/data indexes, then listed uploads. |
| `info(path)` | Returns CID, size, filename, content type, creation fields, and mock status when available. |
| `open(path, "rb")` | Returns a `BytesIO` over `cat_file`. |
| `rm(path)` / `rm_file(path)` | Calls `w3_remove` and removes local alias/data records. |
| `get_backend_status()` | Reports protocol, content-addressed capabilities, mock mode, API URL, and space. |

Content addressing: Storacha writes return CIDs. The `rpath` argument is an
adapter alias only. Deleting by alias resolves to the CID known by that
filesystem instance.

### Filecoin Pin

The `filecoin://` backend adapts the repository's Filecoin Pin storage-manager
backend, not a mutable Filecoin filesystem.

Instantiate with:

```python
import fsspec
from ipfs_kit_py.enhanced_fsspec import FilecoinFileSystem, FilecoinPinFileSystem

fs = fsspec.filesystem("filecoin", metadata={"api_key": "..."})
fs = FilecoinFileSystem(metadata={"api_key": "..."})
fs = FilecoinPinFileSystem(metadata={"api_key": "..."})
```

Required runtime configuration:

| Mode | Requirements |
| --- | --- |
| Mock | Used when `FilecoinPinBackend` cannot be imported and `metadata["require_live"]` is not true. The in-memory client records pins and bytes for the current process. |
| Live | Install the Filecoin Pin dependencies with `pip install -e ".[filecoin_pin]"` and provide API configuration accepted by `FilecoinPinBackend`, usually `api_key` and optionally `api_endpoint`, `timeout`, and `max_retries` in `metadata` or `resources`. Set `metadata={"require_live": True}` to fail on missing dependencies. Live smoke tests are gated by `IPFS_KIT_LIVE_FILECOIN_PIN=1` and `FILECOIN_PIN_API_KEY`. |
| Retrieval | Reads by CID require bytes cached by the same filesystem instance or retrieval metadata such as `retrieval_enabled`, `retrieval_path`, `retrieval_gateway`, or `gateway_fallback`. |

Supported methods:

| Method | Behavior |
| --- | --- |
| `ls("filecoin://", detail=True)` | Calls `list_pins`; also includes aliases written by the current filesystem instance. |
| `cat_file(path, start=None, end=None)` | Reads cached bytes or calls `get_content` only when retrieval is configured; otherwise raises `NotImplementedError`. |
| `pipe_file(path, value, mode="overwrite")` | Calls `add_content` with optional metadata; records CID, status, request ID, deals, replication, and alias. |
| `put_file(lpath, rpath)` | Calls `add_content` for a local file; records pin metadata and cached bytes. |
| `get_file(rpath, lpath)` | Reads with `cat_file` and writes bytes locally. |
| `exists(path)` | Checks local alias index, then `get_metadata`. |
| `info(path)` | Returns CID, status, request ID, deal IDs, replication, filename, and mock status when available. |
| `open(path, "rb")` | Returns a `BytesIO` over `cat_file` when retrieval is available. |
| `get_backend_status()` | Reports `provider="filecoin_pin"`, mock mode, retrieval status, and API endpoint. |

Content addressing: Filecoin Pin stores or pins content and returns a CID/pin
request. The `filecoin://uploads/name.bin` path is only an alias in the adapter;
it does not rename or mutate Filecoin content.

## Common Examples

Write bytes and then use the canonical identifier:

```python
from ipfs_kit_py.enhanced_fsspec import StorachaFileSystem

fs = StorachaFileSystem()
fs.pipe_file("storacha://drafts/report.txt", b"hello")

info = fs.info("storacha://drafts/report.txt")
cid_path = info["name"]

assert cid_path.startswith("storacha://bafy")
assert fs.cat_file(cid_path) == b"hello"
```

Read Filecoin Pin content by CID from a separate filesystem instance:

```python
from ipfs_kit_py.enhanced_fsspec import FilecoinFileSystem

fs = FilecoinFileSystem(
    metadata={
        "api_key": "...",
        "retrieval_enabled": True,
        "retrieval_gateway": "https://example-gateway.invalid/ipfs/",
    }
)

data = fs.cat_file("filecoin://bafy...")
```

Use fsspec's protocol dispatch:

```python
import fsspec
import ipfs_kit_py.enhanced_fsspec

with fsspec.open("synapse://baga6ea4...", "rb") as handle:
    payload = handle.read()
```

