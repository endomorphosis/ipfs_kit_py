# fsspec Backend Audit

Task: `fsspec-backends-001`

This audit covers the current fsspec-facing behavior in `ipfs_kit_py/ipfs_fsspec.py`
and `ipfs_kit_py/enhanced_fsspec.py`, plus the lower-level Synapse, Storacha,
Filecoin, and Filecoin Pin APIs that those files either use or should use.

## Summary

| Area | Current state |
| --- | --- |
| IPFS via `ipfs_fsspec.py` | Partially implemented and registered as `ipfs://`. It supports listing, metadata, reads, local uploads, removal/unpin, file-like reads/writes, metrics, and a test-focused VFS layer, but default construction can silently fall back to mock clients. |
| `enhanced_fsspec.py` | Multi-backend facade with `protocol = ["ipfs", "filecoin", "storacha", "synapse"]`. IPFS and Synapse have partial implementations; Filecoin and Storacha methods are mostly stubs/placeholders. Import-time registration maps all four protocols to the same class without protocol-specific backend selection. |
| Synapse | Lower-level `synapse_storage` has async store/retrieve/status/provider/payment APIs. `enhanced_fsspec.py` bridges some of them into sync fsspec methods. Tests mostly exercise mocked storage directly rather than the real fsspec methods. |
| Storacha | Lower-level `storacha_kit` exposes upload/list/read/remove-style APIs, but `enhanced_fsspec.py` does not call them. Several Storacha methods currently return mock/test data. |
| Filecoin | Lower-level `filecoin_storage` supports store/retrieve/deal/status APIs outside fsspec. `enhanced_fsspec.py` initializes `lotus_kit`, not `filecoin_storage`, and Filecoin fsspec operations are placeholders. |
| Filecoin Pin | `FilecoinPinBackend` supports mocked and API-backed add/get/remove/metadata/list behavior through the storage manager, but there is no dedicated fsspec adapter or registration path for it. |

## Protocols and Registration

- `ipfs_kit_py/ipfs_fsspec.py` registers only `ipfs` with fsspec and maps it to
  `IPFSFSSpecFileSystem`.
- `ipfs_kit_py/ipfs_fsspec.py` exports `IPFSFileSystem` as a function alias.
  The alias auto-creates an `IPFSFSSpecFileSystem` and fills missing
  `ipfs_client` and `tiered_cache_manager` arguments through `get_filesystem()`.
- `ipfs_kit_py/enhanced_fsspec.py` registers `ipfs`, `filecoin`, `storacha`,
  and `synapse` to one `IPFSFileSystem` class with `clobber=True`.
- The enhanced class defaults to `backend="ipfs"`. Because fsspec registration
  does not pass the protocol as `backend`, `fsspec.filesystem("synapse")`,
  `fsspec.filesystem("storacha")`, and `fsspec.filesystem("filecoin")` can
  instantiate the shared class with the IPFS default unless callers explicitly
  pass `backend=...`.
- `high_level_api.IPFSSimpleAPI.get_filesystem()` imports `IPFSFileSystem` from
  `ipfs_fsspec.py`, not `enhanced_fsspec.py`, so it currently targets the IPFS
  surface only.

## Method Status

### IPFS: `ipfs_kit_py/ipfs_fsspec.py`

| Method/API | Status | Notes |
| --- | --- | --- |
| `ls(path, detail=True)` | Implemented | Calls `ipfs_client.ipfs_ls_path`; returns fsspec-style `name`, `size`, `type`, and `cid`. |
| `info(path)` | Implemented with fallback | Uses `ipfs_ls_path` against the CID or parent path; falls back to size `0` file info for direct CIDs. |
| `open(path, mode="rb")` | Implemented | Returns `IPFSFSSpecFile`. Reads call `cat`; writes buffer data and upload on flush/close. |
| `cat(path, recursive=False, on_error="raise")` | Implemented | Uses cache first, then `ipfs_client.ipfs_cat(cid)`; does not preserve subpath semantics after extracting the root CID. |
| `put(lpath, rpath, recursive=False, ...)` | Implemented for local upload | Calls `ipfs_client.ipfs_add_path`; `rpath` is not used to create an MFS path. |
| `rm(path, recursive=False, ...)` | Implemented heuristically | CID-like paths call `ipfs_pin_rm`; other paths call `ipfs_remove_path`. |
| `get_performance_metrics()` | Implemented | Returns local counters if metrics are enabled. |
| Tier helpers | Partial | Integrity/replication/demotion helpers exist but depend on attributes such as `cache`, `ipfs_cluster`, or `cache_config` that are not consistently initialized by the constructor. |
| Synapse via `backend="synapse"` | Stub/ineffective | Constructor attempts to create `synapse_storage`, but core methods still use IPFS client paths and do not branch to Synapse. |
| Storacha/Lotus/Lassie/Arrow classes at file end | Stubs | Constructors raise `ImportError` or return minimal placeholder behavior. |

### Multi-Backend Facade: `ipfs_kit_py/enhanced_fsspec.py`

| Backend | Implemented | Stubbed or placeholder |
| --- | --- | --- |
| IPFS | `_initialize_ipfs_backend`, `_ls_ipfs`, `_cat_file_ipfs`, `_put_file_ipfs`, `_get_file_ipfs`, `_exists_ipfs`, `_info_ipfs`, `get_backend_status` | Assumes client has `ipfs_ls_path`, `ipfs_cat_data`, `ipfs_add_data`, `ipfs_object_stat`, and `ipfs_id`. No file-like `_open`/`open` override is present beyond inherited fsspec behavior. |
| Synapse | `_initialize_synapse_backend`, `_ls_synapse`, `_cat_file_synapse`, `_put_file_synapse`, `_get_file_synapse`, `_exists_synapse`, `_info_synapse`, `get_backend_status`, `get_backend_config` | `get_backend_config` assumes `synapse_storage.get_configuration()`. Error handling often returns empty lists or falsey info, which can hide configuration failures. |
| Storacha | Initialization only | `ls` returns `[]`; `cat_file`, `put_file`, and `get_file` raise `NotImplementedError`; `exists` returns `False`; `info` returns unknown size/type; status returns `{"status": "connected"}` placeholder. |
| Filecoin | Initialization only | Same stub profile as Storacha. It initializes `lotus_kit`, while the repo's direct storage methods live in `filecoin_storage.py`; status returns a connected placeholder. |

### Lower-Level Backend APIs

| Backend module | Available behavior | fsspec gap |
| --- | --- | --- |
| `synapse_storage.py` | Async `synapse_store_data`, `synapse_store_file`, `synapse_retrieve_data`, `synapse_retrieve_file`, `synapse_get_piece_status`, proof-set, provider, cost, balance, deposit, approve, configuration, and status methods. | Only a subset is wired in `enhanced_fsspec.py`; no dedicated `SynapseFileSystem` protocol class exists. |
| `storacha_kit.py` | Space login/list/info, upload (`w3_up`, `upload_add`, `store_add`), retrieval (`w3_cat`, `store_get`), list (`w3_list`), remove (`w3_remove`), and batch helpers. | Not wired to fsspec. Current list/cat/remove methods are mock/test-oriented and do not provide a clear live-vs-mock fsspec contract. |
| `filecoin_storage.py` | Direct Filecoin storage and retrieval with Boost, Estuary, or API fallback; deal listing/check/cancel, metadata, stats, miner info, and miner recommendations. | Not wired to fsspec. `enhanced_fsspec.py` currently uses `lotus_kit` for Filecoin backend initialization instead. |
| `mcp/storage_manager/backends/filecoin_pin_backend.py` | Storage-manager backend with add, get, remove, metadata, and list pins. It has explicit mock mode when no API key is configured. | No `filecoin://` or `filecoin-pin://` fsspec class adapts these methods to `ls`, `cat_file`, `put_file`, `get_file`, `info`, or `exists`. |

## Test Coverage

| Test file | Covered today | Not covered |
| --- | --- | --- |
| `tests/integration/test_fsspec_simple.py` | A self-contained mock of `IPFSSimpleAPI.get_filesystem()` configuration and construction. | Real `ipfs_fsspec.py` import, fsspec registration, IPFS reads/writes/listing, and all non-IPFS backends. |
| `tests/integration/test_fsspec_integration.py` | `IPFSSimpleAPI.get_filesystem()` success, missing-fsspec, and constructor-exception paths with `IPFSFileSystem` patched. | Real fsspec operations, `enhanced_fsspec.py`, protocol-specific registration, and backend behavior. |
| `tests/test_synapse_fsspec.py` | Mock Synapse storage method names, mocked async store/retrieve/list/status metadata, and basic `IPFSFileSystem(backend="synapse")` construction when imports are available. | Real calls to `fs.ls`, `fs.cat_file`, `fs.put_file`, `fs.get_file`, `fs.exists`, `fs.info`, `open(..., "rb")`, fsspec protocol registration, and live Synapse behavior. Several tests call `MockSynapseStorage` directly instead of the fsspec adapter. |

Additional coverage exists elsewhere for raw IPFS, Storacha, Filecoin, and
Filecoin Pin modules, but the validation set for this task does not assert their
fsspec behavior.

## Live-Network vs Mock Behavior

- IPFS fsspec can use a real `ipfs_kit` client when available, but
  `get_filesystem()` falls back to `MagicMock` clients and cache managers on
  initialization failure. Tests in the validation set use mocks.
- Synapse lower-level storage is live-network capable through the JavaScript
  bridge and Synapse SDK configuration. The validation tests patch it with
  `MockSynapseStorage` and do not require live credentials.
- Storacha has endpoint discovery and API/CLI helpers, but some read/list/remove
  methods return generated mock content or success results. There is no fsspec
  mock/live switch yet because the fsspec methods are stubs.
- Direct Filecoin storage is live-network capable through Boost, Estuary, or API
  paths, but there is no fsspec adapter.
- Filecoin Pin has explicit mock mode when no API key is configured and API mode
  otherwise. That behavior is not exposed through fsspec.

## Acceptance Checklist

- IPFS fsspec methods are documented as implemented, partial, or stubbed.
- Synapse fsspec methods and mocked test coverage are documented.
- Storacha fsspec methods are documented as currently stubbed despite lower-level APIs.
- Filecoin and Filecoin Pin fsspec gaps are documented separately.
- `enhanced_fsspec.py` protocol registration and backend-selection risks are documented.
