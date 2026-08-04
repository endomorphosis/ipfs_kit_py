# High-Level API (`IPFSSimpleAPI`)

The high-level API is the recommended in-process Python surface for common IPFS Kit operations. This guide documents **imports that resolve on the current tree**, construction and configuration, lazy/degraded behavior, return and error shapes, and how the dual-path implementation is wired.

Cross-references: [API Reference](api_reference.md), [Runtime and entry points](../architecture/RUNTIME_AND_ENTRYPOINTS.md), [Compatibility layers](../architecture/COMPATIBILITY_LAYERS.md) (C-HLA / C-EXPORT), [API stability](../api_stability.md).

---

## Status snapshot

| Surface | Status | Notes |
|--------|--------|--------|
| Import name `ipfs_kit_py.high_level_api` | **Canonical import name** | Resolves to package directory `ipfs_kit_py/high_level_api/` |
| Package export `IPFSSimpleAPI` | **Canonical constructor name** | Stub/proxy that lazy-loads the full implementation on first instantiation |
| Sibling file `ipfs_kit_py/high_level_api.py` | **Compatibility implementation body** | Loaded under `sys.modules` name `ipfs_kit_py._high_level_api_impl` so it does not clobber the package |
| Package-only stub when load fails | **Degraded mode** | Sets `available = False`; unknown methods return `{success: False, warning: ...}` |
| Root `from ipfs_kit_py import IPFSSimpleAPI` | **Lazy proxy** (not in `__all__`) | `_IPFSSimpleAPIProxy`; raises `ImportError` if the feature cannot load |
| Root `PluginBase` | **Not a usable root export** | Package root assigns `PluginBase = None`; do not import it from `ipfs_kit_py` |
| Draft files (`high_level_api.py.fixed`, `*_improved.py`, etc.) | **Inactive** | Not import targets |

Long-term shape of the dual path (**C-HLA** / **U-03**) remains unresolved in architecture docs. This guide describes **current** behavior only.

---

## Supported imports

### Preferred: package import

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()
# When the Compatibility implementation loaded: full methods.
# When only the stub is active: api.available is False.
```

Package `__all__` for `ipfs_kit_py.high_level_api` always includes `IPFSSimpleAPI`. Optional helpers may also appear when present:

- `WebRTCBenchmarkIntegration`
- `WebRTCBenchmarkIntegrationAnyIO`
- `HAVE_ANYIO_BENCHMARK`

### Root lazy proxy (not listed in package `__all__`)

```python
from ipfs_kit_py import IPFSSimpleAPI  # _IPFSSimpleAPIProxy instance

api = IPFSSimpleAPI()  # resolves class via get_high_level_api(); may raise ImportError
```

`IPFSSimpleAPI` is **not** listed in `ipfs_kit_py.__all__` (**C-EXPORT**). Prefer the package import for explicitness. There is **no** process-wide singleton instance of the API for library callers: each call constructs a new object.

### Explicit lazy getter

```python
from ipfs_kit_py import get_high_level_api

IPFSSimpleAPI_cls, _plugin_base = get_high_level_api()
if IPFSSimpleAPI_cls is None:
    raise RuntimeError("high_level_api feature unavailable")
api = IPFSSimpleAPI_cls()
```

`_plugin_base` is typically `None` because the package surface does not re-export `PluginBase` (see [Plugin architecture](#plugin-architecture-and-extensions)).

### Related kit orchestrator (not the high-level API)

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit  # class name is lowercase ipfs_kit

# Or lazy package proxy (callable class proxy, not a pre-built instance):
from ipfs_kit_py import ipfs_kit, get_ipfs_kit

kit = ipfs_kit(resources=None, metadata={"role": "leecher"}, auto_start_daemons=False)
# Factory:
kit = ipfs_kit.create(role="leecher", auto_start_daemons=False)
```

There is **no** public class named `IPFSKit`. Do not assume a root singleton kit instance.

### Client families (do not conflate)

Three different `ipfs_py` classes exist; only the kit orchestrator client is the default under `ipfs_kit`:

| Family | Path | Status |
|--------|------|--------|
| A — kit client | `ipfs_kit_py/ipfs.py` | **Canonical** for `ipfs_kit` |
| B — simplified client | `ipfs_kit_py/ipfs_client.py` | **Compatibility** / experimental |
| C — nested package client | `ipfs_kit_py/ipfs/ipfs_py.py` | **Compatibility** / historical |

See [Compatibility layers](../architecture/COMPATIBILITY_LAYERS.md) §4 (**C-IPFS-CLIENT**).

---

## Compatibility dual path (C-HLA)

What happens on `IPFSSimpleAPI(...)`:

1. Package class `__new__` calls `_try_load_ipfs_simple_api()`.
2. If sibling `ipfs_kit_py/high_level_api.py` loads, the **Compatibility** implementation class is used and an instance of that class is returned.
3. If load fails (missing optional deps such as `fastapi` after auto-ensure attempts, import errors, etc.), the **stub** instance is used:
   - `self.available = False`
   - Attribute access yields callables that return structured failure dicts, for example  
     `{"success": False, "warning": "IPFSSimpleAPI.<name> not available (using stub implementation)"}`.

Check degraded mode before relying on results:

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()
if getattr(api, "available", True) is False:
    raise RuntimeError("IPFSSimpleAPI stub active; full Compatibility implementation did not load")
```

When the full implementation is active, the object typically exposes:

- `api.kit` — underlying `ipfs_kit` orchestrator instance
- `api.config` — merged configuration dict
- `api.role` — role string (`leecher` default unless overridden)
- `api.plugins`, `api.extensions` — plugin/extension registries
- `api.fs` — filesystem handle from `get_filesystem()` when fsspec path is available

---

## Construction and configuration

### Signature

```text
IPFSSimpleAPI(config_path: Optional[str] = None, **kwargs)
```

- `config_path`: optional path to a YAML or JSON file.
- `**kwargs`: merged into configuration after file load (override file values). Common keys include `role`, `resources`, `metadata`, `disabled_components`, `plugins`, `enable_metrics`, timeouts/cache settings as present in the config schema.

Full-implementation construction (when Compatibility body loads):

1. Load config via `_load_config(config_path)`.
2. Update with `kwargs`.
3. Build `ipfs_kit(resources=..., metadata={..., "role": role, "disabled_components": ...})`.
4. Optionally apply libp2p class integration, metrics, fsspec filesystem, metadata replication, and plugins from config.

### Examples

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Defaults (role typically "leecher" from config/defaults)
api = IPFSSimpleAPI()

# Config file + overrides
api = IPFSSimpleAPI(
    config_path="~/.ipfs_kit/config.yaml",
    role="worker",
    timeouts={"api": 60, "gateway": 180},
)

# Explicit role and resource hints (passed through config/kwargs into kit metadata)
api = IPFSSimpleAPI(
    role="master",
    resources={"max_memory": "2GB", "max_storage": "100GB"},
    enable_metrics=True,
)
```

### Configuration layering

Precedence observed in the full implementation:

1. Built-in defaults from `_load_config`
2. Values from `config_path` (if provided)
3. Initialization `**kwargs` (override file)

Environment variables used elsewhere in the stack (for example `IPFS_KIT_CONFIG_PATH` for the HTTP server, `IPFS_KIT_ROLE` in ops docs) are not a substitute for passing `config_path` / kwargs into the library constructor unless your config loader also reads them.

### Saving configuration

```python
api.save_config(config_path)  # parameter name is config_path (not file_path)
```

Returns a result dict with at least a success indicator when the Compatibility implementation is active.

### Dependency injection and the kit

The high-level API constructs its own `ipfs_kit` from config. Callers who need explicit daemon policy on the kit should prefer constructing `ipfs_kit` / `ipfs_kit.create(..., auto_start_daemons=False)` directly, or ensure config/metadata sets safe defaults. The HLA does not accept an external kit instance as a constructor argument in the current signature.

---

## Return and error shapes

### Structured success dictionaries

Most mutating / management methods return a `dict` that includes:

| Key | Meaning |
|-----|---------|
| `success` | Boolean outcome |
| Method-specific fields | e.g. `cid`, `pins`, `count`, `timestamp` |
| Error fields on failure | Often `error`, sometimes `error_type` |

Example documented shape for `add` (full implementation):

- `success`, `cid`, `size`, `name`, `hash`, `timestamp`

### Byte-returning methods

- `get(cid, timeout=None, **kwargs)` → `bytes` on success
- `cat(cid)` → `bytes` (content retrieval helper)
- `read(path, ...)` → content bytes

### Stub / degraded returns

Stub mode does **not** raise for arbitrary method names; it returns:

```python
{"success": False, "warning": "IPFSSimpleAPI.<name> not available (using stub implementation)"}
```

### Exceptions (full implementation)

Docstrings on core methods reference exception types such as:

- `IPFSError`, `IPFSConnectionError`, `IPFSTimeoutError`
- `IPFSContentNotFoundError`, `IPFSValidationError`
- `IPFSAddError`, `IPFSPinningError`, cluster-specific errors

Always check `success` when the return type is a dict; catch IPFS errors when calling byte-returning or raising paths.

---

## Sync vs async

| Style | Methods | Notes |
|-------|---------|--------|
| Sync (primary) | `add`, `get`, `pin`, `publish`, `cluster_*`, most AI helpers | Call from ordinary Python code |
| Async | `stream_media_async`, `stream_to_ipfs_async`, `handle_websocket_*`, `handle_webrtc_streaming` | Require an event loop / ASGI WebSocket context |
| Callable dispatch | `api(method_name, *args, **kwargs)` | Sync dispatch to a method or registered extension |

There is no separate “async IPFSSimpleAPI” class on the package surface. AnyIO dual helpers for WebRTC benchmarks live as optional package exports (`WebRTCBenchmarkIntegrationAnyIO`) when importable.

---

## Core operations (verified signatures)

Signatures below are taken from the Compatibility implementation class in `ipfs_kit_py/high_level_api.py` (loaded as `_high_level_api_impl`). They exist as public methods on the full class.

### Content

```python
result = api.add(
    content,
    pin=True,
    wrap_with_directory=False,
    chunker="size-262144",
    hash="sha2-256",
    **kwargs,
)
# content: path str, text, bytes, Path, or binary file-like

data = api.get(cid, timeout=None, **kwargs)   # bytes
data = api.cat(cid)                           # bytes

result = api.pin(cid, recursive=True, timeout=None, **kwargs)
result = api.unpin(cid, recursive=True, timeout=None, **kwargs)
result = api.list_pins(type="all", quiet=False, timeout=None, **kwargs)
# Related: pin_ls(...), pins(...)
```

### Filesystem-like

```python
fh = api.open(path, mode="rb", cache=True, size_hint=None, **kwargs)
data = api.read(path, cache=True, timeout=None, **kwargs)
ok = api.exists(path, timeout=None, **kwargs)
entries = api.ls(path, detail=True, timeout=None, **kwargs)

# Additional helpers:
api.open_file(...); api.read_file(...); api.read_text(...)
api.add_json(data, indent=2, sort_keys=True, pin=True, ...)
```

`path` may be a raw CID or an `/ipfs/...` path.

### IPNS and peers

```python
result = api.publish(cid, key="self", lifetime="24h", ttl="1h", timeout=None, **kwargs)
result = api.resolve(name, recursive=True, timeout=None, **kwargs)  # param is name

result = api.connect(peer, timeout=None, **kwargs)  # multiaddress string
result = api.peers(verbose=False, latency=False, direction=False, timeout=None, **kwargs)
```

### Cluster (role-dependent; needs cluster components)

```python
# Default replication_factor is -1 in the implementation (not 1).
result = api.cluster_add(content, replication_factor=-1, name=None, timeout=None, **kwargs)
result = api.cluster_pin(cid, replication_factor=-1, name=None, timeout=None, **kwargs)
result = api.cluster_status(cid=None, local=False, timeout=None, **kwargs)
result = api.cluster_peers(timeout=None, **kwargs)
```

### Streaming

```python
# Sync stream out
for chunk in api.stream_media(
    path, chunk_size=..., mime_type=None,
    start_byte=None, end_byte=None, cache=True, timeout=None, **kwargs
):
    ...

# Sync stream in
result = api.stream_to_ipfs(
    content_iterator, filename=None, mime_type=None,
    chunk_size=..., progress_callback=None, timeout=None, metadata=None, **kwargs
)

# Async counterparts: stream_media_async, stream_to_ipfs_async
# WebSocket/WebRTC handlers: handle_websocket_media_stream, handle_websocket_upload_stream,
#   handle_websocket_bidirectional_stream, handle_webrtc_streaming
```

### Configuration, health, SDK

```python
api.save_config(config_path)
api.generate_sdk(language, output_dir, **kwargs)  # output_dir is required (no default in signature)
api.run_health_check(**kwargs)
```

### Extensions and callable interface

```python
api.register_extension(name, func, overwrite=True)  # returns result dict in full impl
api.call_extension(extension_name, *args, **kwargs)  # single name, not (name, method_name)

# Equivalent dynamic dispatch:
api("add", "hello.txt")
api("my_extension_name", arg1, key=value)
```

There is **no** overload of `register_extension` that accepts a plugin instance object alone; plugins are loaded from config (path + class name) or methods are registered as callables.

---

## AI / ML and search methods

These methods exist on the full Compatibility class. Many accept `allow_simulation=True` and degrade when optional extras or backends are missing. Treat them as **optional-feature** surfaces; install relevant extras before expecting real model I/O.

**Present (examples):**

- Registry / models: `ai_model_add`, `ai_model_get`, `ai_register_model`, `ai_list_models`, `ai_dataset_add`, `ai_dataset_get`, `ai_register_dataset`, `ai_data_loader`
- Inference / deploy: `ai_test_inference`, `ai_deploy_model`, `ai_update_deployment`, `ai_get_endpoint_status`, `ai_optimize_model`, `ai_benchmark_model`
- Embeddings / indexes: `ai_create_embeddings`, `ai_create_vector_index`, `ai_hybrid_search`, `load_embedding_model`, `generate_embeddings`
- LangChain / LlamaIndex (subset present): `ai_langchain_create_vectorstore`, `ai_langchain_load_documents`, `ai_langchain_query`, `ai_llama_index_create_index`, `ai_llama_index_load_documents`, `ai_llama_index_query`
- Graphs / training: `ai_create_knowledge_graph`, `ai_query_knowledge_graph`, `ai_calculate_graph_metrics`, `ai_expand_knowledge_graph`, `ai_distributed_training_submit_job`, `ai_distributed_training_get_status`, `ai_distributed_training_aggregate_results`, `ai_distributed_training_cancel_job`
- Integrated search: `hybrid_search`, `create_search_connector`, `create_search_benchmark`, `run_search_benchmark`

**Not present on the current class** (do not document as available without a Proposed label):

- `ai_metrics_visualize`, `ai_metrics_export`
- `ai_langchain_store_chain`, `ai_langchain_load_chain`
- `ai_llama_index_store_index`, `ai_llama_index_load_index`

Full parameter tables: [API Reference](api_reference.md).

---

## WAL, filesystem journal, resources, metadata

Also present on the full class (feature-dependent):

| Group | Methods |
|-------|---------|
| WAL | `wal_get_status`, `wal_list_pending_operations`, `wal_list_failed_operations`, `wal_get_statistics`, `wal_health_check`, `wal_get_operation` |
| FS journal | `enable_filesystem_journaling`, `fs_journal_get_status`, `fs_journal_list_recent_operations`, `fs_journal_list_failed_operations`, `fs_journal_list_virtual_files`, `fs_journal_get_file_info`, `fs_journal_get_statistics`, `fs_journal_health_check` |
| Resources | `resource_get_usage_summary`, `resource_get_usage_details`, `resource_get_backend_status`, `resource_track_*`, `resource_update_backend_status` |
| Metadata | `store_metadata`, `get_metadata`, `verify_metadata_replication` |
| Peer helpers | `register_peer`, `unregister_peer`, `find_peers_websocket`, `connect_to_websocket_peer`, `find_libp2p_peers`, `connect_to_libp2p_peer`, … |

---

## Plugin architecture and extensions

### Supported path: register callables

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()

def my_status():
    return {"success": True, "status": "ok"}

api.register_extension("my_status", my_status)
print(api("my_status"))
print(api.call_extension("my_status"))
```

### Config-driven plugins

Full implementation loads plugins from configuration entries with:

- `name` — attribute name of the class on the imported module
- `path` — import path (absolute or package-relative starting with `.`)
- `enabled` — default `True`
- `config` — dict passed to the constructor as `config=`

Constructor expected by the loader: `plugin_class(ipfs_kit=self.kit, config=...)`. Public methods are registered as extensions named `{plugin_name}.{method_name}`.

### Compatibility: `PluginBase`

`PluginBase` is defined on the Compatibility implementation module (`ipfs_kit_py/high_level_api.py` → `_high_level_api_impl`). It is **not** exported by:

- `ipfs_kit_py.high_level_api` package `__all__`
- package root as a working class (`PluginBase = None` in `ipfs_kit_py/__init__.py`)

Do **not** write:

```python
from ipfs_kit_py.high_level_api import PluginBase  # not on package surface
from ipfs_kit_py import PluginBase                 # is None
```

**Compatibility access** after the full implementation has been loaded once:

```python
import sys
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

_ = IPFSSimpleAPI()  # triggers Compatibility body load when possible
impl = sys.modules.get("ipfs_kit_py._high_level_api_impl")
if impl is None or not hasattr(impl, "PluginBase"):
    raise RuntimeError("PluginBase unavailable (implementation not loaded)")
PluginBase = impl.PluginBase
```

Prefer plain callables + `register_extension` for portable extensions.

---

## SDK generation

```python
result = api.generate_sdk("python", output_dir="./sdk")
# language also supports generators implemented in the Compatibility body
# (python, javascript, rust, and additional generators if present)
```

`output_dir` is a required positional argument in the current signature.

---

## Complete minimal example

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI(role="leecher")

if getattr(api, "available", True) is False:
    raise SystemExit("High-level API stub active; install optional deps / check logs")

add_result = api.add(b"hello from IPFSSimpleAPI", pin=True)
if not add_result.get("success", True) and "cid" not in add_result:
    raise SystemExit(f"add failed: {add_result}")

cid = add_result["cid"]
content = api.get(cid)
print(content)

pin_result = api.pin(cid)
print(pin_result)

# Dynamic dispatch
print(api("list_pins", type="all"))
```

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Methods always return `success: False` with stub warning | Compatibility implementation failed to load | Inspect logs for `_high_level_api_impl` / `fastapi` import errors; check `api.available` |
| `from ipfs_kit_py import IPFSSimpleAPI` raises `ImportError` | Root proxy could not load feature | Use package import; verify install and JIT feature `high_level_api` |
| `PluginBase` import fails | Not on package/`__all__` surface | Use `register_extension` or Compatibility access via `_high_level_api_impl` |
| Cluster methods fail | Role/components/binaries missing | Confirm role and cluster services; see operations docs |
| AI methods simulate or fail soft | Optional extras / backends missing | Install AI extras; check `allow_simulation` behavior |
| Surprise daemons | Kit auto-start defaults | Prefer `auto_start_daemons=False` on direct `ipfs_kit` construction for library embeds |

### Debugging

```python
import logging
logging.getLogger("ipfs_kit_py").setLevel(logging.DEBUG)

from ipfs_kit_py.high_level_api import IPFSSimpleAPI
api = IPFSSimpleAPI()
print("available", getattr(api, "available", True))
print("role", getattr(api, "role", None))
print("config keys", list(getattr(api, "config", {}) or {})[:20])
```

---

## Stability

Stability levels (`@stable_api`, `@beta_api`, `@experimental_api`) are defined in [API stability](../api_stability.md). Not every method on the large Compatibility class is decorated; treat undocumented stability as **unspecified** and prefer methods you have tested in your environment.

Packaging version is `0.3.0` (`pyproject.toml`); `ipfs_kit_py.__version__` may still report `0.2.0` (**C-VER**). Do not treat the module string alone as release authority.

---

## See also

- [API Reference](api_reference.md) — compact tables for HLA methods and HTTP server surface
- [CLI Reference](cli_reference.md) — `ipfs-kit` operator CLI
- [Compatibility layers](../architecture/COMPATIBILITY_LAYERS.md) — dual paths and inactive artifacts
- [Runtime and entry points](../architecture/RUNTIME_AND_ENTRYPOINTS.md) — process ownership and daemons
