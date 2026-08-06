# API Reference

Python library and HTTP surfaces for IPFS Kit as they exist on the **current tree**. Every import and signature shown either resolves in-repo or is explicitly labeled **Compatibility** / **Proposed**. This reference does **not** claim an implicit process-wide singleton for library users, and it does not present unavailable root exports as public API.

For narrative construction, degraded-mode behavior, plugins, and dual-path detail, see [High-Level API](high_level_api.md). Architecture: [Runtime and entry points](../architecture/RUNTIME_AND_ENTRYPOINTS.md), [Compatibility layers](../architecture/COMPATIBILITY_LAYERS.md).

---

## 1. Import matrix

| Import | Status | Notes |
|--------|--------|--------|
| `from ipfs_kit_py.high_level_api import IPFSSimpleAPI` | **Canonical** | Package `ipfs_kit_py/high_level_api/`; constructor may return Compatibility impl or stub |
| `from ipfs_kit_py import IPFSSimpleAPI` | **Lazy proxy** | Not in `__all__` (**C-EXPORT**); `_IPFSSimpleAPIProxy`; may raise `ImportError` |
| `from ipfs_kit_py import get_high_level_api` | **Canonical helper** | Returns `(IPFSSimpleAPI_cls_or_None, PluginBase_or_None)` — PluginBase usually `None` from package |
| `from ipfs_kit_py.ipfs_kit import ipfs_kit` | **Canonical** | Lowercase class name; multi-role orchestrator |
| `from ipfs_kit_py import ipfs_kit` / `get_ipfs_kit()` | **Lazy proxy** | Callable class proxy, **not** a pre-constructed instance |
| `from ipfs_kit_py.api import run_server` | **Canonical** (optional FastAPI/uvicorn) | Starts HTTP API process using module-level server wiring |
| `from ipfs_kit_py.high_level_api import PluginBase` | **Unavailable** on package surface | See Compatibility note below |
| `from ipfs_kit_py import PluginBase` | **Unavailable** | Root binds `PluginBase = None` |
| `IPFSKit` (capitalized) | **Does not exist** | Use `ipfs_kit` |
| `high_level_api.py.fixed`, `*_improved.py`, … | **Inactive** | Not import targets |

### Compatibility: implementation module identity

| Path | Role |
|------|------|
| `ipfs_kit_py/high_level_api/` | Import package (canonical name) |
| `ipfs_kit_py/high_level_api.py` | **Compatibility** body; loaded as `ipfs_kit_py._high_level_api_impl` |
| Stub `IPFSSimpleAPI` in package | Used when Compatibility body fails to load; `available = False` |

---

## 2. High-level API (`IPFSSimpleAPI`)

### Construction

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()
api = IPFSSimpleAPI(config_path="~/.ipfs_kit/config.yaml", role="worker")
api = IPFSSimpleAPI(role="master", resources={"max_memory": "2GB"}, enable_metrics=True)
```

| Item | Detail |
|------|--------|
| Signature | `IPFSSimpleAPI(config_path: Optional[str] = None, **kwargs)` |
| Default role | `"leecher"` when not set in config/kwargs (full impl) |
| Kit wiring | Full impl builds `self.kit = ipfs_kit(resources=..., metadata=...)` |
| Degraded | If only stub: `available is False`; methods return `{success: False, warning: ...}` |
| Singleton | **None for library callers** — each call constructs a new instance |

### Method call interface

```python
api.add("example.txt")
api("add", "example.txt")                 # __call__(method_name, *args, **kwargs)
api.call_extension("ext_name", *args)     # registered extension by single name
api.register_extension(name, func, overwrite=True)
```

### Content operations

| Method | Signature (essentials) | Returns |
|--------|------------------------|---------|
| `add` | `add(content, pin=True, wrap_with_directory=False, chunker="size-262144", hash="sha2-256", **kwargs)` | `dict` with `success`, `cid`, size/name metadata |
| `get` | `get(cid, timeout=None, **kwargs)` | `bytes` |
| `cat` | `cat(cid)` | `bytes` |
| `pin` | `pin(cid, recursive=True, timeout=None, **kwargs)` | `dict` (`success`, `cid`, …) |
| `unpin` | `unpin(cid, recursive=True, timeout=None, **kwargs)` | `dict` |
| `list_pins` | `list_pins(type="all", quiet=False, timeout=None, **kwargs)` | `dict` (`pins`, `count`, …) |
| `pin_ls` | `pin_ls(cid=None, type="all", quiet=False, timeout=None, type_filter=None, **kwargs)` | `dict` |
| `pins` | `pins(type=None, quiet=None, verify=None, **kwargs)` | `dict` |
| `add_json` | `add_json(data, indent=2, sort_keys=True, pin=True, wrap_with_directory=False, filename=None, allow_simulation=True, **kwargs)` | `dict` |

### Filesystem-like operations

| Method | Signature (essentials) | Returns |
|--------|------------------------|---------|
| `open` | `open(path, mode="rb", cache=True, size_hint=None, **kwargs)` | File-like |
| `read` | `read(path, cache=True, timeout=None, **kwargs)` | `bytes` |
| `exists` | `exists(path, timeout=None, **kwargs)` | `bool` |
| `ls` | `ls(path, detail=True, timeout=None, **kwargs)` | List / detailed entries |
| `open_file` | `open_file(path, mode="rb", buffer_size=None, cache_type=None, compression=None, encoding=None, errors=None, **kwargs)` | File-like |
| `read_file` / `read_text` | See implementation | Bytes / text |
| `get_filesystem` | `get_filesystem(gateway_urls=None, use_gateway_fallback=None, gateway_only=None, cache_config=None, enable_metrics=None, return_mock=False, **kwargs)` | fsspec-style FS or mock |

### IPNS and peers

| Method | Signature (essentials) | Returns |
|--------|------------------------|---------|
| `publish` | `publish(cid, key="self", lifetime="24h", ttl="1h", timeout=None, **kwargs)` | `dict` |
| `resolve` | `resolve(name, recursive=True, timeout=None, **kwargs)` | `dict` (parameter is `name`) |
| `connect` | `connect(peer, timeout=None, **kwargs)` | `dict` (parameter is `peer` multiaddress) |
| `peers` | `peers(verbose=False, latency=False, direction=False, timeout=None, **kwargs)` | `dict` |
| `register_peer` / `unregister_peer` | `register_peer(peer_id, peer_address, capabilities=None)` | `dict` |

### Cluster operations

Require cluster-capable role and components. Defaults below match the Compatibility implementation.

| Method | Signature (essentials) | Returns |
|--------|------------------------|---------|
| `cluster_add` | `cluster_add(content, replication_factor=-1, name=None, timeout=None, **kwargs)` | `dict` |
| `cluster_pin` | `cluster_pin(cid, replication_factor=-1, name=None, timeout=None, **kwargs)` | `dict` |
| `cluster_status` | `cluster_status(cid=None, local=False, timeout=None, **kwargs)` | `dict` |
| `cluster_peers` | `cluster_peers(timeout=None, **kwargs)` | `dict` |

### Streaming (sync and async)

| Method | Signature (essentials) | Notes |
|--------|------------------------|-------|
| `stream_media` | `stream_media(path, chunk_size=..., mime_type=None, start_byte=None, end_byte=None, cache=True, timeout=None, **kwargs)` | Sync generator |
| `stream_media_async` | Same params, `async` | Async |
| `stream_to_ipfs` | `stream_to_ipfs(content_iterator, filename=None, mime_type=None, chunk_size=..., progress_callback=None, timeout=None, metadata=None, **kwargs)` | Marked beta in source |
| `stream_to_ipfs_async` | Async counterpart | |
| `handle_websocket_media_stream` | `async handle_websocket_media_stream(websocket, path, ...)` | ASGI WebSocket |
| `handle_websocket_upload_stream` | `async handle_websocket_upload_stream(websocket, ...)` | |
| `handle_websocket_bidirectional_stream` | `async handle_websocket_bidirectional_stream(websocket, ...)` | |
| `handle_webrtc_streaming` | `async handle_webrtc_streaming(websocket, **kwargs)` | |
| `track_streaming_operation` | Metrics helper | |

### Configuration, SDK, health, extensions

| Method | Signature | Returns |
|--------|-----------|---------|
| `save_config` | `save_config(config_path)` | `dict` |
| `generate_sdk` | `generate_sdk(language, output_dir, **kwargs)` | `dict` (`output_dir` required) |
| `run_health_check` | `run_health_check(**kwargs)` | `dict` |
| `register_extension` | `register_extension(name, func, overwrite=True)` | `dict` (full impl) |
| `call_extension` | `call_extension(extension_name, *args, **kwargs)` | Extension return value |
| `__call__` | `__call__(method_name, *args, **kwargs)` | Method/extension result |

### AI / ML (optional extras; methods present on Compatibility class)

| Method | Signature (essentials) |
|--------|------------------------|
| `ai_model_add` | `ai_model_add(model, metadata=None, pin=True, replicate=False, framework=None, version=None, timeout=None, **kwargs)` |
| `ai_model_get` | `ai_model_get(model_id, local_only=False, load_to_memory=True, timeout=None, **kwargs)` |
| `ai_dataset_add` | `ai_dataset_add(dataset, metadata=None, pin=True, replicate=False, format=None, chunk_size=None, timeout=None, **kwargs)` |
| `ai_dataset_get` | `ai_dataset_get(dataset_id, decode=True, return_path=False, target_path=None, version=None, timeout=None, **kwargs)` |
| `ai_register_model` | `ai_register_model(model_cid, metadata, allow_simulation=True, **kwargs)` |
| `ai_register_dataset` | `ai_register_dataset(dataset_cid, metadata, pin=True, add_to_index=True, overwrite=False, ...)` |
| `ai_list_models` | `ai_list_models(framework=None, model_type=None, limit=100, offset=0, ...)` |
| `ai_data_loader` | `ai_data_loader(dataset_cid, batch_size=32, shuffle=True, prefetch=2, ...)` |
| `ai_test_inference` | `ai_test_inference(model_cid, test_data_cid, batch_size=32, ..., allow_simulation=True, **kwargs)` |
| `ai_deploy_model` | `ai_deploy_model(model_cid, deployment_config, environment="production", ...)` |
| `ai_update_deployment` | `ai_update_deployment(deployment_id, model_cid=None, config=None, allow_simulation=True, **kwargs)` |
| `ai_get_endpoint_status` | `ai_get_endpoint_status(endpoint_id, allow_simulation=True, **kwargs)` |
| `ai_optimize_model` | `ai_optimize_model(model_cid, target_platform="cpu", optimization_level="O1", quantization=False, ...)` |
| `ai_benchmark_model` | `ai_benchmark_model(model_cid, benchmark_type="inference", batch_sizes=[1, 8, 32], ...)` |
| `ai_create_embeddings` | `ai_create_embeddings(docs_cid, embedding_model="default", ...)` |
| `ai_create_vector_index` | `ai_create_vector_index(embedding_cid, index_type="hnsw", ...)` |
| `ai_hybrid_search` | `ai_hybrid_search(query, vector_index_cid, keyword_index_cid=None, ...)` |
| `ai_langchain_create_vectorstore` | `ai_langchain_create_vectorstore(documents, embedding_model=None, collection_name=None, ...)` |
| `ai_langchain_load_documents` | `ai_langchain_load_documents(path_or_cid, ...)` |
| `ai_langchain_query` | `ai_langchain_query(vectorstore_cid, query, top_k=5, allow_simulation=True, **kwargs)` |
| `ai_llama_index_create_index` | `ai_llama_index_create_index(documents, index_type="vector_store", ...)` |
| `ai_llama_index_load_documents` | `ai_llama_index_load_documents(path_or_cid, ...)` |
| `ai_llama_index_query` | `ai_llama_index_query(index_cid, query, response_mode="default", ...)` |
| `ai_create_knowledge_graph` | `ai_create_knowledge_graph(source_data_cid, graph_name="knowledge_graph", ...)` |
| `ai_query_knowledge_graph` | `ai_query_knowledge_graph(graph_cid, query, query_type="cypher", ...)` |
| `ai_calculate_graph_metrics` / `ai_expand_knowledge_graph` | See implementation |
| `ai_distributed_training_submit_job` | `ai_distributed_training_submit_job(config, num_workers=None, priority="normal", ..., allow_simulation=True, **kwargs)` |
| `ai_distributed_training_get_status` | `ai_distributed_training_get_status(job_id, ...)` |
| `ai_distributed_training_aggregate_results` | `ai_distributed_training_aggregate_results(job_id, aggregation_method="best_model", ...)` |
| `ai_distributed_training_cancel_job` | `ai_distributed_training_cancel_job(job_id, force=False, allow_simulation=True, **kwargs)` |

#### Not on the current class (do not use without a Proposed label)

| Name | Status |
|------|--------|
| `ai_metrics_visualize`, `ai_metrics_export` | **Absent** |
| `ai_langchain_store_chain`, `ai_langchain_load_chain` | **Absent** |
| `ai_llama_index_store_index`, `ai_llama_index_load_index` | **Absent** |

### Integrated search

| Method | Signature (essentials) |
|--------|------------------------|
| `hybrid_search` | `hybrid_search(query_text=None, query_vector=None, metadata_filters=None, entity_types=None, hop_count=1, top_k=10, similarity_threshold=0.0, search_mode="hybrid", ...)` |
| `load_embedding_model` | `load_embedding_model(model_name="sentence-transformers/all-MiniLM-L6-v2", model_type="sentence-transformer", ...)` |
| `generate_embeddings` | `generate_embeddings(texts, model=None, model_name=None, batch_size=32, ...)` |
| `create_search_connector` | `create_search_connector(model_registry=None, dataset_manager=None, embedding_model=None, ...)` |
| `create_search_benchmark` | `create_search_benchmark(output_dir=None, search_connector=None, ...)` |
| `run_search_benchmark` | `run_search_benchmark(benchmark_type="full", num_runs=5, ...)` |

### WAL, journal, resources, metadata (feature-dependent)

| Group | Methods |
|-------|---------|
| WAL | `wal_get_status`, `wal_list_pending_operations(limit=20)`, `wal_list_failed_operations(limit=20)`, `wal_get_statistics(hours=24)`, `wal_health_check`, `wal_get_operation(operation_id)` |
| FS journal | `enable_filesystem_journaling(journal_base_path="~/.ipfs_kit/journal", auto_recovery=True, **kwargs)`, `fs_journal_get_status`, `fs_journal_list_recent_operations`, `fs_journal_list_failed_operations`, `fs_journal_list_virtual_files`, `fs_journal_get_file_info`, `fs_journal_get_statistics`, `fs_journal_health_check` |
| Resources | `resource_get_usage_summary`, `resource_get_usage_details`, `resource_get_backend_status`, `resource_track_bandwidth_upload`, `resource_track_bandwidth_download`, `resource_track_storage_usage`, `resource_track_api_call`, `resource_update_backend_status` |
| Metadata | `store_metadata`, `get_metadata`, `verify_metadata_replication` |

### Return and error conventions

| Pattern | When |
|---------|------|
| `dict` with `success` | Most management/mutation methods |
| `bytes` | `get`, `cat`, many `read*` paths |
| Stub failure dict | Package stub only: `success=False`, `warning=...` |
| Raised `IPFS*` errors | Full impl on connection/timeout/validation failures (see method docstrings) |

---

## 3. Kit orchestrator (`ipfs_kit`)

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

kit = ipfs_kit(
    resources=None,
    metadata=None,
    enable_libp2p=False,
    enable_cluster_management=False,
    enable_metadata_index=False,
    auto_start_daemons=True,  # prefer False for library embeds
)

kit = ipfs_kit.create(role="leecher", auto_start_daemons=False)
kit.initialize(start_daemons=False)
kit.stop_daemons()
```

| Item | Detail |
|------|--------|
| Class name | `ipfs_kit` (not `IPFSKit`) |
| Client used | Family A: `ipfs_kit_py.ipfs.ipfs_py` |
| Factory | `create(role="leecher", auto_start_daemons=True, **kwargs)` runs `initialize` when auto-start is true |
| Singleton | **No** library singleton; `from ipfs_kit_py import ipfs_kit` is a lazy **class** proxy |

IPFS client families B/C are **Compatibility** / historical — see [Compatibility layers](../architecture/COMPATIBILITY_LAYERS.md) §4.

---

## 4. HTTP API server (`ipfs_kit_py.api`)

### Starting the server

```python
from ipfs_kit_py.api import run_server

run_server()  # host="127.0.0.1", port=8000, reload=False, workers=1, ...

run_server(
    host="0.0.0.0",
    port=8000,
    reload=False,
    workers=1,
    config_path="config.yaml",
    log_level="info",
    auth_enabled=False,
    cors_origins=None,  # env wiring; see function for feature flags
    enable_libp2p=None,
    enable_webrtc=None,
    enable_wal=None,
    enable_fs_journal=None,
    enable_benchmarking=None,
    enable_observability=None,
    enable_metadata_index=None,
    storage_backends=None,
)
```

CLI equivalent: `python -m ipfs_kit_py.api` / module `__main__` argparse (`--host`, `--port`, `--config`, …).

**Process note:** Importing `ipfs_kit_py.api` constructs a **module-level** `IPFSSimpleAPI` for request handlers (`ipfs_api = IPFSSimpleAPI(config_path=...)`). That is an HTTP-server process detail, **not** a library-wide singleton for `import ipfs_kit_py` users.

### Core routes registered in `api.py`

| Endpoint | Method | Role |
|----------|--------|------|
| `/health` | GET | Health check |
| `/api/openapi` | GET | OpenAPI schema helper |
| `/api/{method_name}` | POST | **Primary dispatcher** — calls `api(method_name, *args, **kwargs)` on the process HLA instance |
| `/api/upload` | POST | Upload helper |
| `/api/download/{cid}` | GET | Download helper |
| `/api/config` | GET | Config exposure |
| `/api/methods` | GET | Method listing |
| `/api/error_method`, `/api/unexpected_error`, `/api/binary_method`, `/api/test_method` | POST | Test/error harness endpoints |

Request body for the generic dispatcher uses `args` / `kwargs` fields (see `APIRequest` model in `api.py`). Binary results may be base64-encoded with `encoding: "base64"`.

### Optional feature routers (included when deps flag true)

| Prefix / surface | Condition |
|------------------|-----------|
| `/api/v0/fs-journal/*` | Filesystem journal available |
| `/api/v0/metadata/*` | Metadata index available |
| `/api/v0/benchmark/*` | Benchmark router |
| `/api/v0/webrtc`, `/api/v0/wal`, `/api/v0/enhanced-pins`, `/api/v0/storage`, `/api/v0/observability` | Feature modules importable |
| GraphQL router | When GraphQL stack available (log message references `/graphql`) |

Concrete handlers under those prefixes are defined in the corresponding modules/routers, not as a full Kubo clone inside empty `v0_router`.

### Proposed / module-doc-only paths (not registered as dedicated routes on `v0_router`)

The module docstring for `api.py` lists Kubo-style paths such as `/api/v0/add`, `/api/v0/cat`, `/api/v0/pin/*`, `/api/v0/swarm/*`, `/api/v0/name/*`, `/api/v0/cluster/*`, `/api/v0/ai/*`. On the current tree, `v0_router = APIRouter(prefix="/api/v0")` is created and included **without** those dedicated handlers attached in `api.py`. Prefer:

- **In-process:** `IPFSSimpleAPI` methods
- **HTTP:** `POST /api/{method_name}` with JSON `args`/`kwargs`

Treat dedicated `/api/v0/add`-style REST as **Proposed** unless a feature router or future change registers them.

### Example: generic method dispatch

```python
import requests

# Call HLA add via HTTP dispatcher
r = requests.post(
    "http://127.0.0.1:8000/api/add",
    json={"args": ["Hello from HTTP"], "kwargs": {"pin": True}},
)
print(r.json())
```

### Error envelope (typical)

```json
{
  "success": false,
  "error": "…",
  "error_type": "IPFSError",
  "status_code": 400
}
```

---

## 5. Root package exports (declared `__all__`)

Declared `ipfs_kit_py.__all__` is P2P/JIT-centric. It includes names such as:

- P2P workflow: `MerkleClock`, `FibonacciHeap`, `WorkflowPriorityQueue`, `P2PWorkflowCoordinator`, `WorkflowStatus`, `WorkflowTask`, helpers, `P2PWorkflowTools`
- JIT: `jit_manager`, `require_feature`, `optional_feature`
- Backend helpers: `initialize_backend_config`, `get_backend_statuses`
- Optional getters: `get_ipfs_datasets`, `get_ipfs_accelerate`, `get_ipfs_transformers`, related module names

Popular symbols `IPFSSimpleAPI` and `ipfs_kit` are available via lazy proxies but are **not** members of `__all__` (**C-EXPORT**). Version: packaging `0.3.0` vs possible `ipfs_kit_py.__version__ == "0.2.0"` (**C-VER**).

Binary installers are opt-in (`IPFS_KIT_AUTO_INSTALL_BINARIES`); ordinary imports do not download executables by default.

---

## 6. Stability

See [API stability](../api_stability.md). Decorators `@stable_api` / `@beta_api` / `@experimental_api` appear on some Compatibility-body methods (for example `stream_to_ipfs` is beta). Undecorated public methods have **unspecified** stability; pin versions and test before relying on them in production.

---

## 7. Related documents

| Document | Topic |
|----------|--------|
| [high_level_api.md](high_level_api.md) | Construction, Compatibility dual path, plugins, troubleshooting |
| [cli_reference.md](cli_reference.md) | `ipfs-kit` CLI |
| [core_concepts.md](core_concepts.md) | Conceptual model |
| [COMPATIBILITY_LAYERS.md](../architecture/COMPATIBILITY_LAYERS.md) | Dual paths, inactive artifacts |
| [RUNTIME_AND_ENTRYPOINTS.md](../architecture/RUNTIME_AND_ENTRYPOINTS.md) | Entry points and process ownership |
