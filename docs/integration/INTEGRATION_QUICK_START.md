# Integration quick start

| Field | Value |
|---|---|
| Document class | Product integration quick start |
| Status | active |
| Last verified | 2026-08-03 |
| Task | KDOC-038 |
| Companion | [INTEGRATION_OVERVIEW.md](./INTEGRATION_OVERVIEW.md) (ownership, trust, maturity contracts) |
| Packaging baseline | `pyproject.toml` **0.3.0**, Python **≥ 3.12** |

Get a **working optional integration** without treating optional packages as core. For full boundary contracts (ownership, trust, maturity), use the overview. For deep APIs, use the specialized guide linked on each path.

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.12 | Packaging floor; older docs saying 3.8 are stale |
| Core package | `pip install ipfs_kit_py` **or** editable `pip install -e .` from a clone |
| Optional extras | Only what you need (see recipes below) |
| External services | Only for paths that need them (Kubo, Iroh, S3, Storacha, …) |

**Core installs cleanly without** `ipfs_datasets_py`, `ipfs_accelerate_py`, LangChain, torch, boto3, or libp2p. Those are opt-in.

---

## 2. Choose a path

| Goal | Extra / install | Service needed? | Jump to |
|---|---|---|---|
| Filesystem API over Iroh | `fsspec` + `iroh` | Iroh binary/service | [§4.1](#41-fsspec-iroh-packaged-path) |
| Columnar metadata / Arrow | `arrow` | No remote | [§4.2](#42-arrow-metadata) |
| IPLD CAR helpers | `ipld` | Optional IPFS for persistence | [§4.3](#43-ipld) |
| Dataset provenance hooks | `ipfs_datasets` | Optional IPFS | [§4.4](#44-ipfs-datasets) |
| ML acceleration glue | `ipfs_accelerate` | GPU/CPU ML env | [§4.5](#45-ipfs-accelerate) |
| S3-compatible backend | `s3` | Bucket credentials | [§4.6](#46-s3) |
| Storacha / Filecoin pin | env token / `filecoin_pin` | Account or Lotus | [§4.7](#47-storacha--filecoin) |
| GraphRAG over VFS | `ai_ml` (+ often datasets) | Models/IPFS as used | [§4.8](#48-graphrag) |
| LangChain / LlamaIndex | manual `langchain` / `llama-index` | API keys for models | [§4.9](#49-langchain--llamaindex) |
| libp2p peer features | `libp2p` | Network | [§4.10](#410-libp2p-network) |

Always read **Ownership**, **Data / trust boundary**, and **Maturity** for that row in [INTEGRATION_OVERVIEW.md](./INTEGRATION_OVERVIEW.md).

---

## 3. Install recipes

```bash
# Core only — sufficient for library + packaged CLI/MCP++ without optional integrations
pip install ipfs_kit_py

# From a clone (development)
pip install -e .
pip install -e '.[dev]'   # tests/lint only; not a runtime integration extra
```

```bash
# Common integration extras (install only what you use)
pip install 'ipfs_kit_py[fsspec]'
pip install 'ipfs_kit_py[iroh]'
pip install 'ipfs_kit_py[arrow]'
pip install 'ipfs_kit_py[ipld]'
pip install 'ipfs_kit_py[s3]'
pip install 'ipfs_kit_py[ipfs_datasets]'
pip install 'ipfs_kit_py[ai_ml]'
pip install 'ipfs_kit_py[libp2p]'          # tracks py-libp2p git main; moving target
pip install 'ipfs_kit_py[ipfs_accelerate]' # heavy ML stack — optional, not core
```

```bash
# LangChain / LlamaIndex are NOT packaging extras
pip install langchain          # versions change; pin for production
# pip install llama-index
```

```bash
# Composite optional bundle (still not "core")
pip install 'ipfs_kit_py[full]'
# Note: full does not replace every specialized extra (e.g. full accelerate stack).
```

Verify import without assuming extras:

```python
import ipfs_kit_py
print("core import ok", getattr(ipfs_kit_py, "__version__", "see packaging 0.3.0"))
```

---

## 4. First successful paths

### 4.1 FSSpec Iroh (packaged path)

**Install extra:** `fsspec`, `iroh`  
**Ownership:** kit owns `IrohFileSystem`; Iroh binary is external.  
**Trust:** caller process + local Iroh RPC; not multi-tenant by default.

```bash
pip install 'ipfs_kit_py[fsspec,iroh]'
# Ensure Iroh service/binary is installed and running per docs/iroh/
```

```python
import fsspec

# Packaging entry points: iroh, iroh+blob only
fs = fsspec.filesystem("iroh")
# Use paths appropriate to your Iroh ticket/namespace setup
print(fs)
```

**Focused tests:** `tests/test_iroh_fsspec_registration.py`, `tests/test_iroh_fsspec_reads.py`.  
**Note:** In-tree `ipfs://` registration via `ipfs_fsspec` / `enhanced_fsspec` is **not** a packaging entry point (see overview **C-FSSPEC**). Prefer packaged Iroh protocols for greenfield work.

---

### 4.2 Arrow metadata

**Install extra:** `arrow`  
**Ownership:** kit owns `arrow_metadata_index`; PyArrow is external.

```bash
pip install 'ipfs_kit_py[arrow]'
```

```python
import pyarrow  # noqa: F401 — proves extra present
from ipfs_kit_py.arrow_metadata_index import ArrowMetadataIndex

# Construct with paths under your kit state; dataset storage remains opt-in
index = ArrowMetadataIndex(
    enable_dataset_storage=False,  # keep core path; optional datasets separate
    enable_compute_layer=False,
)
print("index ready", index is not None)
```

**Guide:** [arrow_metadata_integration.md](./arrow_metadata_integration.md).

---

### 4.3 IPLD

**Install extra:** `ipld` (use `ipld-github` only if you need GitHub UnixFS package)

```bash
pip install 'ipfs_kit_py[ipld]'
```

```python
from ipfs_kit_py.ipld import car  # package layout under ipfs_kit_py/ipld/

# Encode/decode locally; persistence still goes through your chosen backend
print("IPLD helpers importable", car is not None)
```

**Focused tests:** `tests/test_ipld_complete.py`.  
**Guide:** [ipld_integration.md](./ipld_integration.md).

---

### 4.4 IPFS Datasets

**Install extra:** `ipfs_datasets`  
**Ownership:** kit adapter + external `ipfs_datasets_py`.  
**Maturity:** optional-stable import; full distributed features need the package.

```bash
pip install 'ipfs_kit_py[ipfs_datasets]'
```

```python
from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager

manager = get_ipfs_datasets_manager(enable=True)
if not manager.is_available():
    print("datasets package not available — core kit still fine; install extra or disable feature")
else:
    # Opt-in only: store/query via manager APIs when available
    print("datasets integration available")
```

**Focused tests:** `tests/test_ipfs_datasets_integration.py` (skips gracefully if missing).  
**Do not** enable dataset storage in production modules without the extra and a retention plan.

---

### 4.5 IPFS Accelerate

**Install extra:** `ipfs_accelerate` (heavy)  
**Ownership:** kit glue only.  
**Maturity:** optional-experimental for performance claims.

```bash
pip install 'ipfs_kit_py[ipfs_accelerate]'
```

```python
from ipfs_kit_py import get_ipfs_accelerate

mod = get_ipfs_accelerate()
if mod is None:
    print("accelerate not installed — inference uses standard paths")
else:
    print("accelerate module available:", mod)
```

**Focused test:** `tests/test_ipfs_accelerate_integration.py`.  
**Example:** `examples/ai_ml_integration_example.py`.

---

### 4.6 S3

**Install extra:** `s3`  
**Trust boundary:** AWS-style credentials leave kit trust domain.

```bash
pip install 'ipfs_kit_py[s3]'
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
# region/endpoint as required by your provider
```

```python
# Prefer backend registry / s3_kit patterns used by your deployment.
# Minimal smoke: import adapter surface after extra install.
from ipfs_kit_py.backends import s3_backend  # noqa: F401
print("S3 backend module importable")
```

**Focused tests:** `tests/test_s3_gateway_*.py` (many are unit/mock oriented).  
**Reference:** [storage_backends.md](../reference/storage_backends.md).

---

### 4.7 Storacha / Filecoin

**Install:** credentials / `filecoin_pin` extra / Lotus binary as applicable  
**Trust:** third-party account or chain; secrets via env/config.

```bash
# Filecoin pin helpers
pip install 'ipfs_kit_py[filecoin_pin]'

# Storacha / Web3.Storage style token (example env name used in docs/code)
export W3_STORE_TOKEN=...
```

```python
# Adapter ownership is in-repo; service is external
from ipfs_kit_py import storacha_kit  # module presence; configure before live calls
print("storacha adapter importable", storacha_kit is not None)
```

**Focused tests:** `tests/test_storacha_integration.py`, `tests/test_filecoin_pin_integration.py`.  
Live network tests require real credentials — do not assume CI has them.

---

### 4.8 GraphRAG

**Install:** typically `ai_ml`, and often `ipfs_datasets` / embedding deps  
**Maturity:** optional-experimental.

```bash
pip install 'ipfs_kit_py[ai_ml]'
# add datasets/accelerate only if your GraphRAG path routes embeddings there
```

```python
from ipfs_kit_py import graphrag

# GraphRAG needs models and content sources; check dependency flags inside module
print("graphrag module:", graphrag)
```

**Focused tests:** `tests/test_vfs_bucket_graphrag_integration.py`, `tests/test_graphrag_improvements.py`.  
**Architecture:** [VFS_BUCKET_GRAPHRAG_INTEGRATION.md](../features/graphrag/VFS_BUCKET_GRAPHRAG_INTEGRATION.md).

---

### 4.9 LangChain / LlamaIndex

**Install extra:** none — install frameworks yourself.  
**Trust:** LLM/embedding provider API keys.

```bash
pip install langchain
# optional embeddings providers, e.g. openai, sentence-transformers
```

```python
from ipfs_kit_py.ai_ml_integration import LangchainIntegration

# Requires an IPFS-capable kit client in real use; availability is explicit
class _StubClient:
    pass

integration = LangchainIntegration(ipfs_client=_StubClient())
status = integration.check_availability()
print(status)
if not status.get("langchain_available"):
    print("Install langchain before using IPFS document/vector helpers")
```

**Guides:** [langchain_integration.md](./langchain_integration.md), [llamaindex_integration.md](./llamaindex_integration.md).  
There is no packaging guarantee that every LangChain major version works unpinned.

---

### 4.10 libp2p network

**Install extra:** `libp2p`  
**Maturity:** optional-experimental (upstream git main).

```bash
pip install 'ipfs_kit_py[libp2p]'
```

```python
# Peer features degrade when HAS_LIBP2P is false
try:
    from ipfs_kit_py.libp2p import libp2p_peer  # layout may expose peer helpers
    print("libp2p peer surface import attempted", libp2p_peer)
except Exception as exc:
    print("libp2p not usable in this env:", type(exc).__name__, exc)
```

**Focused test:** `tests/test_simple_libp2p.py`.  
**Examples:** `examples/libp2p_example.py`.  
**Architecture:** [NETWORK_TRANSPORTS.md](../architecture/NETWORK_TRANSPORTS.md).

---

## 5. Enable-by-flag pattern (datasets / compute)

Many modules accept opt-in flags. Defaults keep optional packages off:

```python
# Pattern only — replace Manager with the concrete class you use
manager = Manager(
    enable_dataset_storage=False,  # requires ipfs_datasets extra + package
    enable_compute_layer=False,    # requires ipfs_accelerate extra + package
    dataset_batch_size=100,
)
```

Enable only after:

1. Extra installed  
2. Availability check passes  
3. You accept the **data / trust boundary** in the overview  

Manual flush when a module buffers dataset operations:

```python
if getattr(manager, "enable_dataset_storage", False):
    flush = getattr(manager, "flush_to_dataset", None)
    if callable(flush):
        flush()
```

---

## 6. Focused validation (not full suite)

Default pytest may exclude large integration trees. Prefer **focused** commands:

```bash
# Datasets / accelerate (skip if optional packages absent)
python -m pytest tests/test_ipfs_datasets_integration.py -q
python -m pytest tests/test_ipfs_accelerate_integration.py -q

# FSSpec Iroh
python -m pytest tests/test_iroh_fsspec_registration.py -q

# IPLD / storage / GraphRAG / libp2p
python -m pytest tests/test_ipld_complete.py -q
python -m pytest tests/test_storacha_integration.py -q
python -m pytest tests/test_vfs_bucket_graphrag_integration.py -q
python -m pytest tests/test_simple_libp2p.py -q
```

Missing optional deps should **skip or fail soft** in tests, not force CI red for core. If a test hard-requires an optional package without a skip, treat that as a bug.

---

## 7. Troubleshooting

| Symptom | Check | Action |
|---|---|---|
| `ImportError` for optional package | Extra installed? | Install the matching extra; do not add to core deps |
| Feature silent no-op | Enable flag still false? | Set flag only after `is_available()` |
| fsspec protocol not found | Using `ipfs://` vs packaged `iroh://` | Prefer packaging entry points; see overview C-FSSPEC |
| S3/Storacha auth errors | Env/credentials | Configure provider secrets; redacted logs |
| libp2p install brittle | Extra tracks git `main` | Pin carefully; expect breakage (U-10) |
| Accelerate “not faster” | Module None or flag off | Confirm `get_ipfs_accelerate()` and enable path |
| Python version errors | Runtime &lt; 3.12 | Upgrade; packaging requires ≥ 3.12 |

---

## 8. Best practices

1. **Start core-only** — prove CLI/library/MCP++ without extras.  
2. **Add one extra at a time** — isolate trust and failures.  
3. **Read maturity** — experimental paths need pins and focused tests before production.  
4. **Never document optional packages as required** for a basic install.  
5. **Keep secrets outside the repo** — env or secured config.  
6. **Prefer packaged surfaces** over historical dual modules when both exist.  
7. **Record which extras a deployment uses** — operators need a bill of materials.

---

## 9. Next reading

| Document | Use when |
|---|---|
| [INTEGRATION_OVERVIEW.md](./INTEGRATION_OVERVIEW.md) | Ownership, trust, maturity per integration |
| [installation_guide.md](../installation_guide.md) | General install and binaries |
| [ASYNC_AND_OPTIONAL_DEPENDENCIES.md](../architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | Lazy import and async policy |
| [PUBLIC_SURFACE_MATRIX.md](../audits/PUBLIC_SURFACE_MATRIX.md) | Public entry evidence |
| Specialized files in `docs/integration/` | Deep API for one family |

---

**Reminder:** Optional extras and external packages are **integrations**, not core. A successful core install does not imply datasets, accelerate, cloud, or peer stacks are present.
