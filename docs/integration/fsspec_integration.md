# fsspec Integration

`ipfs_kit_py` exposes fsspec-compatible filesystems for content-addressed
storage. The enhanced adapter in `ipfs_kit_py.enhanced_fsspec` registers these
protocols:

| Protocol | Backend class | Durable identifier |
| --- | --- | --- |
| `ipfs://` | `EnhancedIPFSFileSystem` | CID |
| `synapse://` | `SynapseFileSystem` | CommP |
| `storacha://` | `StorachaFileSystem` | CID |
| `filecoin://` | `FilecoinFileSystem` / `FilecoinPinFileSystem` | CID / pin request metadata |

For the 2026-06-14 implementation summary covering the completed fsspec backend
tasks, Walrus delegation to the standalone `walrus-fsspec` package, VFS GraphRAG
indexing, and public CLI/MCP/dashboard SDK exposure, see
[recent_changes_2026_06_14.md](recent_changes_2026_06_14.md).

For the detailed capability matrix, credential requirements, mock/live behavior,
and per-method support, see [fsspec_backends.md](fsspec_backends.md).

- **Filesystem Interface**: Standard file operations on content-addressed storage
- **Tiered Caching**: Multi-level caching (memory, disk) with intelligent data movement using Adaptive Replacement Cache (ARC). ([See Docs](../reference/tiered_cache.md))
- **Memory-mapping**: Zero-copy access for large files via `mmap`.
- **Data Science Integration**: Works seamlessly with Pandas, PyArrow, Dask, and other tools that leverage `fsspec`.
- **Performance Metrics**: Built-in collection and analysis of latency, bandwidth, and cache performance.
- **Unix Socket Support**: Faster local daemon communication on Linux/macOS.
- **Gateway Fallback**: Optionally use public HTTP gateways if the local daemon is unavailable.
- **Additional Protocol Backends**: The completed backend work registers and tests `walrus://`, `synapse://`, `storacha://`, and `filecoin://` surfaces alongside `ipfs://`.
- **Standalone Walrus Delegation**: `ipfs_kit_py.walrus_storage` and
    `ipfs_kit_py.walrus_fsspec` now wrap the standalone `walrus-fsspec` package
    while preserving `ipfs_kit_py` defaults and environment aliases.
- **Lazy Dependency Recovery**: Declared fsspec backend dependencies can be installed automatically at first lazy use unless `IPFS_KIT_AUTO_INSTALL_LAZY_DEPS=0` is set.

Install fsspec support:

```bash
pip install -e ".[fsspec]"
```

1. **IPFSFileSystem**: Main class implementing the Abstract Filesystem interface
2. **WalrusFileSystem**: fsspec backend for Walrus blob reads/writes with direct blob-id reads and local logical-path indexing
3. **SynapseFileSystem / StorachaFileSystem / FilecoinPinFileSystem**: protocol-specific fsspec surfaces for non-IPFS persistence backends
4. **TieredCacheManager**: Manages content across memory and disk tiers
5. **ARCache**: Adaptive Replacement Cache for memory-tier optimization
6. **DiskCache**: Persistent storage with metadata

```bash
pip install -e ".[fsspec,filecoin_pin]"
```

Import the enhanced module before relying on fsspec protocol dispatch:

```python
import fsspec
import ipfs_kit_py.enhanced_fsspec

fs = fsspec.filesystem("ipfs")
```

Import `ipfs_kit_py.walrus_fsspec` when you need to force-register `walrus://`
in a development checkout before fsspec entry point discovery has run.

## Instantiation

Use fsspec protocol dispatch:

```python
import fsspec
import ipfs_kit_py.enhanced_fsspec

ipfs = fsspec.filesystem("ipfs")
synapse = fsspec.filesystem("synapse", metadata={"network": "calibration"})
storacha = fsspec.filesystem("storacha", metadata={"api_key": "..."})
filecoin = fsspec.filesystem("filecoin", metadata={"api_key": "..."})
```

Or instantiate the exported classes/helpers directly:

```python
from ipfs_kit_py.enhanced_fsspec import (
    FilecoinFileSystem,
    StorachaFileSystem,
    SynapseFileSystem,
    create_ipfs_filesystem,
)

ipfs = create_ipfs_filesystem()
synapse = SynapseFileSystem(metadata={"network": "calibration"})
storacha = StorachaFileSystem(metadata={"api_key": "..."})
filecoin = FilecoinFileSystem(metadata={"api_key": "..."})
```

## Content Addressing and Aliases

These backends are not path-mutable filesystems. Upload methods accept a target
path because fsspec expects one, but the storage service returns a content
identifier:

```python
fs.pipe_file("storacha://reports/latest.json", b'{"ok": true}')
info = fs.info("storacha://reports/latest.json")

print(info["name"])  # storacha://bafy...
print(info["alias"]) # storacha://reports/latest.json
```

The alias is stored in the current filesystem object. It is useful for the
current process, but durable references should use the canonical CID or CommP.

## Read Examples

Read by CID from IPFS:

```python
import fsspec
import ipfs_kit_py.enhanced_fsspec

fs = fsspec.filesystem("ipfs")
data = fs.cat_file("ipfs://bafy...")
```

Read by CommP from Synapse:

```python
import fsspec
import ipfs_kit_py.enhanced_fsspec

with fsspec.open("synapse://baga6ea4...", "rb") as handle:
    payload = handle.read()
```

Read from Storacha:

```python
from ipfs_kit_py.enhanced_fsspec import StorachaFileSystem

fs = StorachaFileSystem()
fs.pipe_file("storacha://scratch/data.bin", b"payload")

payload = fs.cat_file("storacha://scratch/data.bin")
```

Read from Filecoin Pin when retrieval is configured:

```python
from ipfs_kit_py.enhanced_fsspec import FilecoinFileSystem

fs = FilecoinFileSystem(
    metadata={
        "api_key": "...",
        "retrieval_enabled": True,
        "retrieval_gateway": "https://example-gateway.invalid/ipfs/",
    }
)

payload = fs.cat_file("filecoin://bafy...")
```

Without cached bytes or retrieval metadata, `filecoin://` reads raise
`NotImplementedError` because a pin record alone is not a retrieval path.

## Write Examples

Upload a local file to Synapse:

```python
from ipfs_kit_py.enhanced_fsspec import SynapseFileSystem

fs = SynapseFileSystem(metadata={"network": "calibration"})
fs.put_file("model.bin", "synapse://models/model.bin")

info = fs.info("synapse://models/model.bin")
print(info["commp"])
```

Upload bytes to Storacha:

```python
from ipfs_kit_py.enhanced_fsspec import StorachaFileSystem

fs = StorachaFileSystem(metadata={"api_key": "..."})
fs.pipe_file("storacha://uploads/readme.txt", b"hello")

cid = fs.info("storacha://uploads/readme.txt")["cid"]
```

Create a Filecoin Pin record:

```python
from ipfs_kit_py.enhanced_fsspec import FilecoinFileSystem

fs = FilecoinFileSystem(metadata={"api_key": "..."})
fs.pipe_file(
    "filecoin://datasets/sample.bin",
    b"sample",
    metadata={"replication": 3},
)

pin = fs.info("filecoin://datasets/sample.bin")
print(pin["cid"], pin["status"], pin.get("deal_ids"))
```

## Supported Method Surface

| Method | IPFS | Synapse | Storacha | Filecoin Pin |
| --- | --- | --- | --- | --- |
| `ls` | Yes | Yes | Yes | Yes |
| `cat_file` | Yes | Yes | Yes | Yes, only with cached bytes or retrieval configured |
| `pipe_file` | Base fsspec behavior | Yes | Yes | Yes |
| `put_file` | Yes | Yes | Yes | Yes |
| `get_file` | Yes | Yes | Yes | Yes, only with cached bytes or retrieval configured |
| `exists` | Yes | Yes | Yes | Yes |
| `info` | Yes | Yes | Yes | Yes |
| `open(..., "rb")` | Base fsspec behavior | Yes | Yes | Yes, only with retrieval available |
| `open(..., "wb")` | Not an enhanced backend API | No | No | No |
| `rm` / `rm_file` | Not implemented by enhanced backend | No | Yes | No |

## Mock and Live Modes

Storacha defaults to in-memory mock mode when no API key is configured. Filecoin
Pin falls back to an in-memory mock when the live backend dependency is missing
and `require_live` is not set. Synapse and IPFS do not provide automatic
enhanced mock clients in this layer.

Set `metadata={"require_live": True}` for Storacha or Filecoin Pin when tests
or applications should fail instead of silently using mock mode.

Live smoke tests are explicitly gated by environment variables:

| Backend | Gate | Common credential/config |
| --- | --- | --- |
| Synapse | `IPFS_KIT_LIVE_SYNAPSE=1` | `SYNAPSE_NETWORK`, `SYNAPSE_PRIVATE_KEY` |
| Storacha | `IPFS_KIT_LIVE_STORACHA=1` | `STORACHA_API_KEY` |
| Filecoin Pin | `IPFS_KIT_LIVE_FILECOIN_PIN=1` | `FILECOIN_PIN_API_KEY` |

## Data Science Use

Once a protocol is registered, libraries that accept fsspec filesystems can read
content-addressed paths:

```python
import fsspec
import pandas as pd
import ipfs_kit_py.enhanced_fsspec

fs = fsspec.filesystem("ipfs")

with fs.open("ipfs://bafy.../table.csv", "rb") as handle:
    df = pd.read_csv(handle)
```

Prefer canonical CIDs or CommPs in persisted datasets, manifests, and pipeline
metadata. Local write aliases are process-local conveniences, not durable
namespace entries.
