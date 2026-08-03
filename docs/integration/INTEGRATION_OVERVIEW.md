# Integration overview and boundary contracts

| Field | Value |
|---|---|
| Document class | Product integration landing guide |
| Status | active |
| Last verified | 2026-08-03 |
| Task | KDOC-038 |
| Goal id | KDOC-G042 |
| Track | current-integration |
| Packaging baseline | `pyproject.toml` **0.3.0**, `requires-python >=3.12` |
| Evidence | Packaging extras, `docs/audits/PUBLIC_SURFACE_MATRIX.md`, architecture guides, focused tests under `tests/` |
| Related | [INTEGRATION_QUICK_START.md](./INTEGRATION_QUICK_START.md), [SYSTEM_OVERVIEW.md](../architecture/SYSTEM_OVERVIEW.md), [ASYNC_AND_OPTIONAL_DEPENDENCIES.md](../architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md), specialized guides in this directory |

This document is the **boundary map** for optional and external integrations that attach to `ipfs_kit_py`. It answers: *what is core, what is an optional extra or external system, who owns the adapter, what surfaces are supported, where trust and data leave the kit, which focused test or example to use, and how mature the integration is today?*

It **does not** claim that optional packages are required for a working install. Base `pip install ipfs_kit_py` (or editable install without extras) is the core product path. Integrations below are **opt-in** unless packaging marks them as hard dependencies.

---

## 1. Scope and non-goals

### 1.1 Scope

| In scope | Why |
|---|---|
| Optional packaging extras and external packages | Distinguish install surface from core |
| In-repo adapters vs externally owned systems | Ownership and trust boundaries |
| Supported product surfaces (library, CLI, fsspec, MCP, daemons) | Avoid documenting every historical import path as equal |
| Data plane vs control plane hand-offs | Where content, credentials, and network trust change |
| Focused tests and examples | Evidence for each contract |
| Honest maturity | Prevent marketing-grade “production ready” claims for optional stacks |

### 1.2 Non-goals

| Out of scope | Owner / pointer |
|---|---|
| Full API inventories | Specialized guides (`fsspec_integration.md`, `libp2p_integration.md`, …) |
| Resolving open architecture conflicts (C-*, U-*) | Architecture guides and ADR track |
| Historical marketing summaries of “N integrations complete” | `docs/status_reports/` — not product authority |
| Installer binary download policy depth | [RUNTIME_AND_ENTRYPOINTS](../architecture/RUNTIME_AND_ENTRYPOINTS.md), async/optional guide |
| Editing specialized integration deep-dives | Conflict policy: this pair of landing guides only |

### 1.3 Core vs optional (hard rule)

| Layer | What it is | Install |
|---|---|---|
| **Core package** | `ipfs_kit_py` library, packaged CLI (`ipfs-kit`), packaged MCP++ (`ipfs-kit-mcp`), kit state under `~/.ipfs_kit` | `pip install ipfs_kit_py` — no ML, cloud, or peer extras required |
| **Optional extra** | Declared in `pyproject.toml` `[project.optional-dependencies]` | `pip install 'ipfs_kit_py[<extra>]'` |
| **External system** | Process or SaaS outside the Python package (Kubo, Iroh binary, Lotus, S3, Storacha, agent host) | Separate install/credentials; kit adapters call them |
| **External Python package** | Separate distribution (e.g. `ipfs_datasets_py`, `langchain`) | Own install; kit provides adapters with graceful absence |

**Rule:** Missing optional code must fail soft or skip—not break core import, default CLI, or default MCP++ unless the operator explicitly requires that capability.

---

## 2. How to read each contract

Every integration below uses the same fields:

| Field | Meaning |
|---|---|
| **Ownership** | Who owns the *adapter* in this repo vs the *external system/package* |
| **Install extra** | Packaging extra name, or “none (manual / external)” |
| **Supported surface** | Canonical product paths (library / CLI / fsspec / MCP / daemon) — not every historical module |
| **Data / trust boundary** | What data leaves the kit process, credential domain, and trust assumption |
| **Focused test / example** | Preferred proof path; may skip when deps missing |
| **Maturity** | Honest status vocabulary (below) |

### Maturity vocabulary

| Label | Meaning |
|---|---|
| **core-adjacent** | Shipped with default product paths; still may need external daemons |
| **optional-stable** | Extra + focused tests; expected for production *when installed and configured* |
| **optional-experimental** | Present and exercised, but dual paths, moving deps, or incomplete product defaults |
| **compatibility** | Alternate/legacy path; not the design center |
| **external-service** | Correctness depends on third-party network service availability and credentials |
| **unresolved** | Competing authorities remain open; do not pick a single “true” path in docs |

---

## 3. Integration catalog (boundary contracts)

### 3.1 IPFS Datasets (`ipfs_datasets_py`)

| Field | Contract |
|---|---|
| **Ownership** | **In-repo adapter:** `ipfs_kit_py/ipfs_datasets_integration.py`, `ipfs_datasets_search.py`, JIT accessor `get_ipfs_datasets()`. **External package:** `ipfs_datasets_py` (separate distribution / stack). Kit does not own upstream dataset APIs. |
| **Install extra** | `ipfs_datasets` → pulls `ipfs_datasets_py`, HuggingFace `datasets`, `boto3`. Also included in the composite `full` extra. **Not** a core dependency. |
| **Supported surface** | Library: `get_ipfs_datasets_manager` / `get_ipfs_datasets()`. Optional hooks in audit, WAL telemetry, Arrow index, VFS/bucket paths when `enable_dataset_storage=True`. Not a packaged console script. |
| **Data / trust boundary** | Operation metadata and dataset payloads may be content-addressed and/or written to IPFS/local stores the datasets stack configures. Treat as **opt-in telemetry/provenance**, not a second authority for pins or kit state. Credentials for remote dataset backends belong to the datasets stack / operator env, not core kit config by default. |
| **Focused test / example** | Tests: `tests/test_ipfs_datasets_integration.py`, `tests/test_ipfs_datasets_search.py`, `tests/test_ipfs_datasets_comprehensive_integration.py`, `tests/test_ipfs_datasets_mcp_integration.py`. Example pattern: enable storage only after `manager.is_available()`. |
| **Maturity** | **optional-stable** for graceful import and manager API; end-to-end distributed dataset features require the external package and often a live IPFS path. Do not present as core storage. |

Deep dive: [IPFS_DATASETS_INTEGRATION.md](./IPFS_DATASETS_INTEGRATION.md), [IPFS_DATASETS_COMPREHENSIVE_INTEGRATION.md](./IPFS_DATASETS_COMPREHENSIVE_INTEGRATION.md).

---

### 3.2 IPFS Accelerate (`ipfs_accelerate_py`)

| Field | Contract |
|---|---|
| **Ownership** | **In-repo adapter:** JIT `get_ipfs_accelerate()`, AI framework hooks under `ipfs_kit_py/mcp/ai/`, `transformers_integration.py` (deprecated path notes accelerate patching). **External package:** `ipfs_accelerate_py` and its heavy ML stack. Kit owns only the glue. |
| **Install extra** | `ipfs_accelerate` — heavy stack (`torch`, `transformers`, OpenVINO family, related packages). **Not** core. Historical submodule paths under `external/` are compatibility, not the preferred packaging story. |
| **Supported surface** | Library / MCP AI paths when acceleration is enabled; optional compute layer flags on some VFS/index modules. Not required for CLI or MCP++ core tools. |
| **Data / trust boundary** | Model weights, prompts, and inference outputs stay in the **caller process** and any accelerate-managed caches. Network trust expands if models are pulled from HuggingFace or remote endpoints. Kit must not imply accelerate is always on. |
| **Focused test / example** | Test: `tests/test_ipfs_accelerate_integration.py`. Example: `examples/ai_ml_integration_example.py`, `examples/high_level_api_ai_ml_example.py`. Check availability before enabling `enable_compute_layer`. |
| **Maturity** | **optional-experimental** for full acceleration claims (large moving dependency graph). Graceful absence is **optional-stable**. Marketing “2–5x always” is not a packaging guarantee. |

---

### 3.3 FSSpec (filesystem protocols)

| Field | Contract |
|---|---|
| **Ownership** | **Packaged entry points (canonical):** `iroh` / `iroh+blob` → `ipfs_kit_py.iroh_fsspec:IrohFileSystem` in `pyproject.toml`. **In-tree adapters:** `iroh_fsspec.py`, `ipfs_fsspec.py`, `enhanced_fsspec.py` (runtime multi-protocol registration). **External:** `fsspec` library (extra). Conflict **C-FSSPEC** / U-17 remains open for IPFS protocol authority. |
| **Install extra** | `fsspec` (`fsspec`, `requests-unixsocket`). Iroh paths also need the `iroh` extra and/or Iroh binary/service. Vendored fsspec may exist for constrained envs — prefer the packaging extra for product use. |
| **Supported surface** | **Canonical packaging:** `iroh://`, `iroh+blob://`. **In-tree / compatibility:** `ipfs://` and multi-protocol registration via modules — **not** declared packaging entry points. Library `IPFSFileSystem` / HLA open helpers. |
| **Data / trust boundary** | fsspec runs **in the caller process**. Content bytes flow through daemon APIs (Kubo/Iroh) or gateways. Gateway fallback expands trust to public HTTP. Unix sockets are local process trust only. |
| **Focused test / example** | Tests: `tests/test_iroh_fsspec_*.py`, `tests/test_iroh_fsspec_registration.py`, `tests/test_synapse_fsspec.py`, integration suites under `tests/integration/test_fsspec*` / `test_ipfs_fsspec*` (note default pytest may exclude some integration trees). Example: `examples/fsspec_example.py`. Deep dive: [fsspec_integration.md](./fsspec_integration.md). |
| **Maturity** | **optional-stable** for packaged Iroh protocols when service is up. **unresolved** for which IPFS fsspec implementation is the single product default. Do not document `ipfs://` as a packaging entry point. |

---

### 3.4 IPLD (CAR, DAG-PB, UnixFS helpers)

| Field | Contract |
|---|---|
| **Ownership** | **In-repo:** `ipfs_kit_py/ipld/`, `ipld_extension.py`, `ipld_knowledge_graph.py`, `parquet_ipld_bridge.py`, CAR WAL paths. **External packages:** `ipld-car`, `ipld-dag-pb`, `dag-cbor`, optional GitHub-only `ipld-unixfs` via `ipld-github`. |
| **Install extra** | `ipld` (PyPI set); `ipld-github` for UnixFS GitHub install; related: `car_files`, `enhanced_ipfs`. Without extras, some paths degrade to JSON/mock CAR behavior. |
| **Supported surface** | Library CAR/DAG helpers; WAL/CAR staging; knowledge-graph and GraphRAG-adjacent structures; MCP IPLD tools where registered. Not a standalone console script family. |
| **Data / trust boundary** | IPLD blocks are content-addressed **data plane**. Encoding/decoding is local; persistence trust follows the backend (IPFS, local CAR files, S3, …). Knowledge-graph indexes may store embeddings metadata separately from raw blocks. |
| **Focused test / example** | Tests: `tests/test_ipld_complete.py`, `tests/test_ipld_mcp_integration.py`. Deep dive: [ipld_integration.md](./ipld_integration.md), [arrow_metadata_integration.md](./arrow_metadata_integration.md). |
| **Maturity** | **optional-stable** for core CAR/DAG-PB paths with `ipld` extra. UnixFS via `ipld-github` is **optional-experimental** (VCS pin). Dual parquet-IPLD bridge files exist — prefer non-backup modules. |

---

### 3.5 AI / ML (in-tree)

| Field | Contract |
|---|---|
| **Ownership** | **In-repo:** `ai_ml_integration.py`, metrics/visualization modules, `mcp/ai/*`, model registry hooks. **External:** PyTorch / sklearn / FAISS / HuggingFace stacks via extras — not owned by kit. |
| **Install extra** | `ai_ml` (`torch`, `numpy`, `scikit-learn`, `faiss-cpu`, `mmh3`); `transformers` / `huggingface` for model hub paths. Accelerate is a **separate** extra (§3.2). |
| **Supported surface** | Library HLA/AI attributes when deps present; MCP AI controllers in legacy/enhanced MCP trees; examples under `examples/ai_ml_*.py`. Packaged MCP++ tool groups are **not** primarily an ML training plane. |
| **Data / trust boundary** | Models, datasets, and embeddings may leave the process to hub downloads or remote APIs. Local cache often under `~/.ipfs_kit/` subdirs. Treat model providers as **external trust domains**. |
| **Focused test / example** | Tests: `tests/integration/test_high_level_api_ai_ml.py` (when suite is run), accelerate/datasets tests above. Examples: `examples/ai_ml_integration_example.py`, `examples/ai_ml_distributed_training_example.py`. Deep dive: [ai-ml/](./ai-ml/). |
| **Maturity** | **optional-experimental** overall (large surface, dual HLA paths **C-HLA**). Individual helpers may be solid; do not mark AI/ML as core kit capability. |

---

### 3.6 LangChain and LlamaIndex

| Field | Contract |
|---|---|
| **Ownership** | **In-repo adapter:** `LangchainIntegration` / LlamaIndex availability checks inside `ai_ml_integration.py`. **External:** `langchain`, `llama_index` (and embedding providers). **No dedicated packaging extra** for LangChain/LlamaIndex names — install those packages yourself. |
| **Install extra** | None named. Typically combine manual `pip install langchain …` (and/or `llama-index`) with kit core + optional `ai_ml` / `transformers` / `ipfs_datasets` as needed. |
| **Supported surface** | Library: document loaders, IPFS-backed vector store helpers, chain store/load when LangChain is importable. Docs: [langchain_integration.md](./langchain_integration.md), [llamaindex_integration.md](./llamaindex_integration.md). Not packaged CLI/MCP default tools. |
| **Data / trust boundary** | Documents and chains stored on IPFS are content-addressed data plane. **Embedding/LLM API keys** (e.g. OpenAI) are external secrets — never kit-core credentials. Vector indexes may cache under kit state paths. |
| **Focused test / example** | No single dedicated `tests/test_langchain_*.py` in the default suite; rely on `ai_ml_integration` availability checks and the markdown examples. Prefer writing focused tests when enabling in production. |
| **Maturity** | **optional-experimental** / framework-version-sensitive. Presence of adapter code ≠ supported production stack for every LangChain major version. |

---

### 3.7 Filecoin, Storacha, and S3 (object / remote storage)

| Field | Contract |
|---|---|
| **Ownership** | **In-repo adapters:** `storacha_kit.py` / `enhanced_storacha_kit.py`, `filecoin_storage.py`, `advanced_filecoin_client.py`, `filecoin_pin_*`, `s3_kit.py`, `s3_gateway.py`, `backends/s3_backend.py`, migration tools under `migration_tools/`. **External systems:** Storacha/Web3.Storage APIs, Lotus/Filecoin network, S3-compatible object stores. **Registry:** backend type names in `backend_registry` / manager (config documents under `~/.ipfs_kit/backends/`). |
| **Install extra** | `s3` → `boto3`. `filecoin_pin` → HTTP/multiformats helpers. Storacha often uses tokens/env (`W3_STORE_TOKEN` / kit metadata) more than a unique extra; Lotus/Filecoin daemons are **binary/service** installs, not pure pip. `full` pulls `boto3` among other deps. |
| **Supported surface** | Library kits and backend adapters; CLI/service paths for Lotus where present; optional fsspec protocols via **enhanced** registration (not packaging entry points). WAL health may monitor IPFS/S3/Storacha. |
| **Data / trust boundary** | **Credentials and account trust leave the kit** (AWS keys, Storacha tokens, Lotus wallet/auth). Remote backends are independent failure domains. Content may be re-addressed (CID vs bucket keys). Redact secrets in logs/registry. |
| **Focused test / example** | Tests: `tests/test_storacha_integration.py`, `tests/test_filecoin_pin_implementation.py`, `tests/test_filecoin_pin_integration.py`, `tests/test_s3_gateway_*.py`, `tests/test_phase6_s3_gateway_comprehensive.py`. Reference: [storage_backends.md](../reference/storage_backends.md). |
| **Maturity** | **external-service** + **optional-stable** adapters when credentials and services are real. Unit tests may mock; live network tests are environment-dependent. Do not claim all cloud backends are identically production-hardened. |

---

### 3.8 GraphRAG (VFS / knowledge search)

| Field | Contract |
|---|---|
| **Ownership** | **In-repo:** `graphrag.py`, `vfs_bucket_graphrag_integration.py`, IPLD knowledge graph helpers, search paths in `integrated_search.py` / `ipfs_datasets_search.py`. Optional MCP GraphRAG modules under historical trees. Embeddings may route through datasets/accelerate when present. |
| **Install extra** | No single `graphrag` extra. Practical stack: `ai_ml` and/or `ipfs_datasets` / `ipfs_accelerate`, often `arrow`, plus optional sentence-transformers (pulled by accelerate extra or manual install). Core kit runs without GraphRAG. |
| **Supported surface** | Library search/index APIs over VFS/bucket content; integration with bucket VFS managers. Architecture note: [VFS_BUCKET_GRAPHRAG_INTEGRATION.md](../features/graphrag/VFS_BUCKET_GRAPHRAG_INTEGRATION.md). |
| **Data / trust boundary** | Indexes and embeddings are **derived data** (rebuildable); content bytes remain backend authority. Model downloads and remote embedding APIs expand trust. SQLite/pickle/cache files are local kit-side state, not IPFS pin authority. |
| **Focused test / example** | Tests: `tests/test_graphrag_improvements.py`, `tests/test_graphrag_100_coverage.py`, `tests/test_vfs_bucket_graphrag_integration.py`. |
| **Maturity** | **optional-experimental** — feature-rich in-tree, dependency-heavy, overlapping search stacks. Useful for research and advanced operators; not a core install default. |

---

### 3.9 Network integrations (Kubo, Iroh, libp2p)

| Field | Contract |
|---|---|
| **Ownership** | **Kubo:** kit client + `kubo_runtime` managers; **daemon process** is external. **Iroh:** `ipfs_kit_py/iroh/*`, install/ops CLIs (`ipfs-kit-iroh*`); sidecar binary external. **libp2p:** `ipfs_kit_py/libp2p/*`, peer helpers; stack from optional `libp2p` extra (tracks `py-libp2p` git `main` — moving target **U-10**). Architecture owner: [NETWORK_TRANSPORTS.md](../architecture/NETWORK_TRANSPORTS.md), normative Iroh under `docs/iroh/`. |
| **Install extra** | `iroh` (blake3, duckdb helpers); `libp2p` (heavy git dependency). Kubo is **not** an extra — binary/PATH/service. Multiaddr/multiformats appear in core deps for addressing; full peer stack still optional. |
| **Supported surface** | Packaged: Iroh CLI family + fsspec Iroh protocols; MCP++ P2P profile when libp2p present; library kit swarm/pin/CID paths for Kubo. Cluster coordination is a **separate** family (bespoke `cluster/` vs Kubo Cluster wrappers). |
| **Data / trust boundary** | Peer networks expand trust beyond localhost. Iroh tickets/RPC, libp2p peer IDs, and Kubo API multiaddrs are distinct identity models — **do not conflate**. HTTP MCP bind addresses are a separate control-plane trust edge. |
| **Focused test / example** | Tests: extensive `tests/test_iroh_*.py`, `tests/test_simple_libp2p.py`, P2P workflow tests. Examples: `examples/libp2p_*.py`. Deep dive: [libp2p_integration.md](./libp2p_integration.md). |
| **Maturity** | Kubo path: **core-adjacent** (still needs daemon). Iroh: **optional-stable** with strongest in-tree contracts. libp2p: **optional-experimental** (upstream main pin). Default content transport among Kubo/Iroh remains **unresolved** (U-09). |

---

### 3.10 Arrow / metadata index (supporting data-plane extra)

| Field | Contract |
|---|---|
| **Ownership** | **In-repo:** `arrow_metadata_index.py` (+ anyio twin), cluster state helpers using Arrow. **External:** PyArrow/pandas via `arrow` extra. |
| **Install extra** | `arrow`. |
| **Supported surface** | Metadata indexes, WAL partitions, analytics paths that expect columnar storage. Degrades when PyArrow missing. |
| **Data / trust boundary** | Local columnar files under kit state; optional pubsub sync is a **cluster trust domain**. Not a remote multi-tenant DB. |
| **Focused test / example** | Integration and index tests across VFS/WAL; guide [arrow_metadata_integration.md](./arrow_metadata_integration.md). |
| **Maturity** | **optional-stable** for features that declare Arrow requirements. |

---

## 4. Extras quick map (packaging)

Declared optional-dependencies (complete list from `pyproject.toml`):

| Extra | Typical integration use |
|---|---|
| `iroh` | Iroh service helpers, fsspec Iroh |
| `fsspec` | Non-vendored fsspec + unix socket support |
| `arrow` | PyArrow / pandas metadata & WAL |
| `ipld` / `ipld-github` / `car_files` / `enhanced_ipfs` | IPLD / CAR / UnixFS |
| `libp2p` | Python peer stack, MCP P2P |
| `ai_ml` / `transformers` / `huggingface` | In-tree AI/ML and hub clients |
| `ipfs_datasets` | Datasets package integration |
| `ipfs_accelerate` | Accelerate / heavy ML stack |
| `s3` / `filecoin_pin` / `saturn` / `ipni` | Cloud / Filecoin-adjacent clients |
| `api` / `webrtc` / `graphql` / `performance` | Specialized surfaces |
| `dev` | Test and lint tooling |
| `full` | **Large optional bundle** — still not “core”; installs many but not all specialized stacks (e.g. may omit full accelerate) |

Install pattern:

```bash
# Core only — integrations optional and absent by design
pip install ipfs_kit_py

# One integration family
pip install 'ipfs_kit_py[fsspec]'
pip install 'ipfs_kit_py[ipfs_datasets]'
pip install 'ipfs_kit_py[s3]'
```

---

## 5. Shared patterns (adapters)

In-repo adapters should follow the same boundary hygiene:

1. **Lazy / guarded import** — never hard-fail core import when an optional package is missing.
2. **Explicit enable flags** — e.g. `enable_dataset_storage=False` by default.
3. **Availability probes** — `is_available()`, `check_dependencies()`, or `HAS_*` flags.
4. **Fail soft** — skip, degrade, or return structured errors; do not corrupt kit state.
5. **Secrets outside code** — env/config for S3, Storacha, LLM keys; redacted in logs.

Example shape (illustrative):

```python
from ipfs_kit_py import get_ipfs_datasets, get_ipfs_accelerate

datasets = get_ipfs_datasets()
accelerate = get_ipfs_accelerate()

# Core kit remains usable regardless of these results
print("datasets:", datasets is not None)
print("accelerate:", accelerate is not None)
```

---

## 6. Trust and data-plane summary

```text
┌─────────────────────────────────────────────────────────────┐
│ Caller / agent host process                                 │
│  library · CLI · fsspec · MCP++                             │
├─────────────────────────────────────────────────────────────┤
│ Kit adapters (in-repo ownership)                            │
│  optional extras load here · credentials loaded here        │
├───────────────┬─────────────────┬───────────────────────────┤
│ Local state   │ Content daemons │ Remote services           │
│ ~/.ipfs_kit   │ Kubo / Iroh /   │ S3 · Storacha · hubs ·    │
│ indexes/WAL   │ Lotus (opt)     │ LLM APIs · IPFS gateways  │
└───────────────┴─────────────────┴───────────────────────────┘
        kit trust              process boundary        account/network trust
```

| Boundary | Do | Do not |
|---|---|---|
| Optional Python package missing | Degrade / skip feature | Treat as core install failure |
| Remote storage / SaaS | Scope credentials; expect network failure | Assume same durability as local pins |
| Peer networks | Explicit enable; understand identity model | Bind control planes to `0.0.0.0` without auth review |
| Derived indexes (GraphRAG, Arrow) | Treat as rebuildable | Confuse with content-byte authority |

---

## 7. Documentation index (specialized)

| Guide | Owns |
|---|---|
| [INTEGRATION_QUICK_START.md](./INTEGRATION_QUICK_START.md) | Install recipes and first successful paths |
| [fsspec_integration.md](./fsspec_integration.md) | FSSpec usage detail |
| [ipld_integration.md](./ipld_integration.md) | IPLD detail |
| [libp2p_integration.md](./libp2p_integration.md) | libp2p detail |
| [langchain_integration.md](./langchain_integration.md) / [llamaindex_integration.md](./llamaindex_integration.md) | LLM framework adapters |
| [IPFS_DATASETS_*.md](./IPFS_DATASETS_INTEGRATION.md) | Datasets deep dives |
| [ai-ml/](./ai-ml/) | AI/ML guides |
| [../reference/storage_backends.md](../reference/storage_backends.md) | Backend operator reference |
| [../architecture/NETWORK_TRANSPORTS.md](../architecture/NETWORK_TRANSPORTS.md) | Network family architecture |
| [../architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md](../architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | Lazy import and async policy |
| [../audits/PUBLIC_SURFACE_MATRIX.md](../audits/PUBLIC_SURFACE_MATRIX.md) | Public surface evidence |

Status reports under `docs/status_reports/` may list historical integration campaigns; **this overview is the product boundary contract**.

---

## 8. Change triggers

Refresh this document when:

- `pyproject.toml` optional-dependencies change
- Packaging fsspec entry points or console scripts change
- A new external package is adapted as a first-class extra
- Maturity or ownership of a dual-path integration is resolved by ADR
- Focused test paths for an integration move or are deleted

---

**Status:** Boundary contracts documented for datasets, accelerate, fsspec, IPLD, AI/ML, LangChain/LlamaIndex, Filecoin/Storacha/S3, GraphRAG, and network families.  
**Core claim:** Optional packages are **not** core.  
**Evidence rank:** packaging → focused tests → architecture guides → specialized prose.
