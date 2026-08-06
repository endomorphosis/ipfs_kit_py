# System context and end-to-end overview

| Field | Value |
|---|---|
| Document class | **Canonical** |
| Status | active |
| Last verified | 2026-08-03 |
| Tree baseline | `6fc55f0918a0f45e04b37727b45c1a1f5aaf9322` |
| Owner / task | KDOC-010 |
| Goal id | KDOC-G021 |
| Track | arch-runtime |
| Authority class | Canonical architecture guide (system context; not an accepted ADR for disputed authorities) |
| Evidence map | [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md) §1, §9, §11 (primary); cross-links §2–§8 |
| Surface matrix | [`docs/audits/PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md) |
| Vocabulary | [`GLOSSARY.md`](./GLOSSARY.md) |
| Contract | [`docs/guides/DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) |
| Packaging baseline | `pyproject.toml` version **0.3.0** (see **C-VER** / **U-01** for `__init__.__version__` drift) |
| Change triggers | See [§12 Change triggers](#12-change-triggers-and-last-verified-baseline) |

This guide answers: *what is the system in context, who talks to it, which package and process containers exist, how storage **data plane** work differs from multi-interface **control plane** work, where trust and failure boundaries sit, and which architecture document to open next?*

It **links** to subsystem guides rather than re-documenting their internals. Disputed authorities remain open (conflict IDs `C-*` / decision IDs `U-*` from Wave 0 evidence).

**Sibling guides (reading order in [§13](#13-reading-order-and-navigation))**

| Guide | Status at baseline | Owns |
|---|---|---|
| [`RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md) | **Present** (KDOC-011) | Process ownership, packaging scripts, init/shutdown per entry |
| `COMPATIBILITY_LAYERS.md` | **Planned** (KDOC-012) | Shims, backups, historical trees |
| `STORAGE_BACKEND_SYSTEM.md` | **Planned** (KDOC-013) | Backend config plugins vs live adapters |
| [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md) | **Present** (KDOC-014) | Content bytes, CIDs, buckets/VFS, WAL/journal data plane |
| `CLUSTER_COORDINATION.md` | **Planned** (KDOC-015) | Bespoke cluster vs Kubo Cluster wrappers |
| `NETWORK_TRANSPORTS.md` | **Planned** (KDOC-016) | Iroh, libp2p, routing, P2P |
| `MCP_CONTROL_PLANE.md` | **Planned** (KDOC-017) | MCP++ registry, surfaces, receipts, legacy trees |
| `ASYNC_AND_OPTIONAL_DEPENDENCIES.md` | **Planned** (KDOC-018) | AnyIO/asyncio boundaries, extras degradation |
| `CONFIGURATION_STATE_AND_TRUST.md` | **Planned** (KDOC-019) | Config precedence, state roots, credentials, trust |

---

## 1. Scope and explicit non-goals

### 1.1 Scope

| In scope | Why |
|---|---|
| External actors and systems | System-context boundary for humans, agents, and daemons |
| Package and runtime containers | What is installed vs what runs as a process |
| Primary data-plane and control-plane flows | End-to-end story without subsystem depth |
| Trust boundaries and sensitive-data edges | Safety map for operators and agents |
| Supported deployment shapes | Library-only through multi-service nodes |
| Failure domains | What fails independently |
| Architecture reading order | Navigation into Wave 1 guides |
| Explicit open conflicts | Prevent false single-story narratives |

### 1.2 Non-goals

| Out of scope | Owner / pointer |
|---|---|
| Per-entry init/shutdown matrices | [`RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md) |
| Backend plugin schemas and adapter factories | Planned `STORAGE_BACKEND_SYSTEM.md` (map §2) |
| WAL/journal recovery sequences and VFS contracts | [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md) |
| Cluster CRDT / role / Kubo Cluster API detail | Planned `CLUSTER_COORDINATION.md` (map §4) |
| Transport security, Iroh threat model, libp2p pins | Planned `NETWORK_TRANSPORTS.md`; normative `docs/iroh/` |
| Tool schema inventories and FastMCP/JS drift | Planned `MCP_CONTROL_PLANE.md` (map §6) |
| Resolving `U-*` / ADR outcomes | ADR track (KDOC-G030); do not invent closures here |
| User install/quick-start tutorials | Current-doc wave (KDOC-030+) |
| Editing protected program-control files | Operator policy |

---

## 2. Supported surfaces and compatibility status

Status labels match the public surface matrix and glossary. **Candidate / packaged** means “default product path from packaging,” not “accepted ADR that retires every sibling.”

### 2.1 Canonical (prefer for new work)

| Surface | Entry | Role |
|---|---|---|
| Packaging metadata | `pyproject.toml` `0.3.0`, `requires-python >=3.12` | Name, scripts, extras, fsspec entry points |
| Operator CLI | `ipfs-kit` → `ipfs_kit_py.cli:sync_main` | Short-lived operator commands (FastCLI + selective unified mounts) |
| MCP++ control plane | `ipfs-kit-mcp` → `mcp_server.server:main` | Long-lived JSON-RPC / MCP++ server (stdio, HTTP, P2P) |
| MCP tools one-shot | `ipfs-kit-mcp-tools` | Same `TOOL_GROUPS` registry without a server process |
| Library façade | `import ipfs_kit_py`, `ipfs_kit`, lazy HLA | In-process orchestration; no process ownership |
| Iroh ops family | `ipfs-kit-iroh*`, `iroh/` service modules | Managed binary lifecycle and service ops |
| Packaged fsspec | `iroh`, `iroh+blob` → `IrohFileSystem` | Only fsspec protocols declared in packaging |
| Backend *type* registry | `backend_registry.py` / `backend_manager.py` | Side-effect-free named backend documents under `~/.ipfs_kit/backends/` |
| Kit state root | `~/.ipfs_kit` | Backend YAML, MCP PID/logs, buckets, StateService (distinct from Kubo `~/.ipfs`) |

### 2.2 Compatibility / historical / unresolved (do not treat as equal defaults)

| Path / claim | Status note | Conflict |
|---|---|---|
| `ipfs_kit_py/__init__.py` `__version__ = "0.2.0"` | Diverges from packaging `0.3.0` | **C-VER** / **U-01** |
| `ipfs_kit_py/mcp/`, root `mcp/`, `servers/*` | Legacy / alternate MCP stacks still importable | **C-MCP-TREES** / **U-11** |
| `ipfs-kit mcp start` dashboard path | Operator CLI dashboard, **not** packaged MCP++ | **C-MCP-TREES** |
| `ipfs-kit daemon start` → legacy `mcp` daemon | Packaged CLI reaches historical tree | **U-16** |
| Dual HLA (`high_level_api/` + `high_level_api.py`) | Package name vs legacy body | **C-HLA** / **U-03** |
| Multiple `ipfs_py` classes | Kit uses `ipfs.py`; siblings exist | **C-IPFS-CLIENT** / **U-12** |
| `enhanced_fsspec` / in-tree `ipfs_fsspec` | Runtime registration; not packaging entry points | **C-FSSPEC** / **U-17** |
| Parallel bucket/VFS managers | Candidate stacks coexist | **U-05** |
| Bespoke cluster vs Kubo Cluster wrappers | Distinct families | **U-08** |
| `archive/`, `backup/`, `*.fixed`, `*_old.py` | Historical / non-default | Map §11 |

### 2.3 Measured control-plane registry (baseline)

At verification baseline, packaged MCP++ exposes **`TOOL_GROUPS` = 12 groups / 29 tools** in `ipfs_kit_py/mcp_server/tools/__init__.py`. The committed JS SDK manifest may lag (**C-MCP-TOOLS** / **U-18**). Treat the Python registry as the candidate write path for new tools until an ADR freezes the published count.

---

## 3. Actors, external systems, and package containers

### 3.1 Actors

| Actor | How they reach the system | Typical plane |
|---|---|---|
| **Human operator** | `ipfs-kit` CLI, Iroh CLIs, config under `~/.ipfs_kit` | Control + ops; occasional data-plane verbs (`bucket`, `vfs`, `pin`, `wal`) |
| **Application developer** | `import ipfs_kit_py`, `IPFSSimpleAPI` / `ipfs_kit`, fsspec | In-process library; data plane via adapters and VFS |
| **AI / automation agent** | `ipfs-kit-mcp` stdio/HTTP/P2P JSON-RPC; receipts | Control plane (tools over storage/network backends) |
| **Host process (caller)** | Library or fsspec in another Python process | Caller owns the event loop and process lifetime |
| **CI / packaging** | `pyproject.toml` extras, installers with `IPFS_KIT_AUTO_INSTALL_BINARIES` | Build/install; must not force binary download by default |

### 3.2 External systems (outside the Python package boundary)

| External system | Relationship | Notes |
|---|---|---|
| **Kubo / IPFS daemon** | Content and pin data plane; optional child process | Repo typically `~/.ipfs`; managed via `kubo_runtime` / daemon managers; **not** kit state root |
| **Iroh binary / service** | Content and namespace data plane | Install/ops via `ipfs-kit-iroh*`; normative contracts under `docs/iroh/` |
| **Lotus / Filecoin** (optional) | Storage backend and daemon | `ipfs-kit services` Lotus path; optional extras/binaries |
| **Object stores / remote backends** (S3, Storacha, …) | Adapter targets | Config plugins + live adapters; credentials redacted in registry |
| **libp2p network** (optional) | P2P transport and MCP P2P mode | Moving-target optional extra (**U-10**) |
| **Kubo IPFS Cluster** (optional) | Distinct multi-node family | Wrappers under `ipfs_cluster_*` — **not** the same as bespoke `cluster/` stack |
| **Agent host / IDE** | Pipes stdio to `ipfs-kit-mcp` | Trust: local process boundary by default |
| **HTTP clients** | MCP++ HTTP (`127.0.0.1:8004` default) | Network trust edge when bind address is expanded |

### 3.3 Package and runtime containers

```text
┌──────────────────────────────────────────────────────────────────────────┐
│  Distribution container: PyPI / source install (pyproject.toml 0.3.0)    │
│  Packages: ipfs_kit_py* (+ optional extras: iroh, fsspec, libp2p, …)     │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ install
     ┌───────────────────────────┼───────────────────────────┐
     ▼                           ▼                           ▼
┌─────────────┐         ┌─────────────────┐         ┌──────────────────┐
│ Console     │         │ Library import  │         │ fsspec entry     │
│ scripts     │         │ (caller process)│         │ points (iroh*)   │
└──────┬──────┘         └────────┬────────┘         └────────┬─────────┘
       │                         │                           │
       │  short- or long-lived   │  no new OS process        │  in-caller
       ▼                         ▼                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Shared library core (lazy / JIT): ipfs_kit, HLA, backends, WAL, VFS,    │
│  daemon managers, mcp_server tools, iroh modules                         │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ may start (opt-in)
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  External service processes: Kubo, Iroh, Lotus, (optional) IPFS Cluster  │
└──────────────────────────────────────────────────────────────────────────┘
```

*Caption: package install yields scripts, in-process library use, and optional external daemons—three nested containers, not one monolith.*

---

## 4. Component ownership and source-of-truth paths

Ownership is summarized here; subsystem guides and the evidence map own detail.

| Concern | Candidate authority (code) | Architecture owner doc |
|---|---|---|
| Packaging / scripts | `pyproject.toml` | This overview + runtime guide |
| Import / JIT / optional features | `ipfs_kit_py/__init__.py`, `core/`, `jit_imports.py`, `deps_resolver.py` | Runtime + async/deps guides |
| Operator CLI | `cli.py` (`FastCLI`), selective `unified_cli_dispatcher.py` | Runtime guide |
| MCP++ control plane | `mcp_server/server.py`, `hierarchical_tool_manager.py`, `tools/__init__.py` (`TOOL_GROUPS`) | Planned MCP guide |
| Kit orchestrator | `ipfs_kit.py` + `ipfs.py` client | Runtime + client family (map §9) |
| Backend config | `backend_registry.py`, `backend_manager.py` | Planned storage-backend guide |
| Live storage adapters | `backends/` | Planned storage-backend guide |
| Content / VFS / durability | bucket/VFS modules, `storage_wal.py`, `filesystem_journal.py`, pins, Arrow index | [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md) |
| Cluster (bespoke) | `cluster/`, `cluster_state.py`, `p2p_workflow_coordinator.py` | Planned cluster guide |
| Kubo Cluster wrappers | `ipfs_cluster_*.py` | Planned cluster guide (separate family) |
| Network / Iroh | `iroh/`, `libp2p/`, `routing/` | Planned network guide; `docs/iroh/` |
| Config / secrets / trust | `config*.py`, `credential_manager.py`, `iroh/security.py` | Planned trust guide |
| Compatibility / archive | `compat.py`, `archive/`, backup siblings | Planned compatibility guide |

**Evidence ranks** (program policy): executable behavior and focused tests → packaging entry points → public source contracts → git history → current prose. Conflicts stay explicit.

---

## 5. Data plane vs control plane

The single most important structural distinction in this overview:

| Plane | What it is | Typical entry points | Durable artifacts |
|---|---|---|---|
| **Storage data plane** | Content bytes, CIDs, pins, buckets/VFS paths, caches, WAL/journal intent, backend adapter I/O | Library APIs, CLI domain verbs (`bucket`, `vfs`, `pin`, `wal`, `journal`), fsspec, live adapters, Kubo/Iroh daemons | Blocks, pins, bucket metadata, journals, CAR/WAL segments, backend stores |
| **Control plane** | Multi-interface command/tool orchestration, JSON-RPC/MCP sessions, tool registry, coordination receipts, operator lifecycle | `ipfs-kit-mcp`, `ipfs-kit-mcp-tools`, FastMCP registrar, CLI `mcp`/`services`/`daemon`, MCP++ profiles | Tool schemas, event-DAG / coordination store entries, agent receipts, PID/log files |

Control-plane tools **invoke** data-plane backends; they are not a second content store. Legacy MCP trees may blur the line—prefer packaged MCP++ for new agent integrations (**U-11** open).

### 5.1 Bounded system-context diagram

```text
                 ┌──────────────┐   ┌──────────────┐   ┌─────────────┐
                 │  Operator    │   │  Dev / app    │   │  Agent host │
                 │  (CLI)       │   │  (import)     │   │  (stdio/HTTP│
                 └──────┬───────┘   └──────┬───────┘   └──────┬──────┘
                        │                  │                  │
                        ▼                  ▼                  ▼
              ┌──────────────────────────────────────────────────────┐
              │              CONTROL PLANE (interfaces)              │
              │  FastCLI · MCP++ MCPServer · TOOL_GROUPS · tools CLI │
              │  StateService / coordination receipts (MCP++ path)   │
              └──────────────────────────┬───────────────────────────┘
                                         │ tool / API calls
                                         ▼
              ┌──────────────────────────────────────────────────────┐
              │           STORAGE DATA PLANE (content path)          │
              │  ipfs_kit · adapters · VFS/buckets · pins · WAL/jnl  │
              │  tiered cache · Arrow metadata (often rebuildable)   │
              └──────────────────────────┬───────────────────────────┘
                                         │ network / local I/O
                                         ▼
              ┌──────────────────────────────────────────────────────┐
              │  EXTERNAL DATA SERVICES                              │
              │  Kubo · Iroh · Lotus · S3/remote backends · Cluster  │
              └──────────────────────────────────────────────────────┘
```

*Caption: actors enter through the control plane (or library façades); durable content lives in the storage data plane and external services.*

### 5.2 Primary end-to-end flows (overview only)

#### A. Agent tool call (control → data)

1. Host starts `ipfs-kit-mcp` (stdio default) or connects HTTP/P2P.
2. `MCPServer` initializes `HierarchicalToolManager` over `TOOL_GROUPS`.
3. JSON-RPC `tools/call` dispatches to a tool module (e.g. pin, CAR, Iroh).
4. Tool exercises data-plane libraries / adapters / optional daemons.
5. Optional MCP++ receipts / coordination store record verified outcomes (fail-closed reads on receipt paths).

Detail: planned `MCP_CONTROL_PLANE.md`; entry lifecycle: [`RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md) §5.

#### B. Operator content path (CLI → data plane)

1. Operator runs `ipfs-kit bucket|vfs|pin|wal|journal|backend …`.
2. FastCLI mounts unified dispatcher families (partial mount—**C-CLI** / **U-02**).
3. Handlers use backend documents, VFS/bucket managers, and durability layers.
4. Bytes and retention state land in adapters / Kubo / Iroh; indexes may be secondary.

Detail: [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md); storage backends: planned `STORAGE_BACKEND_SYSTEM.md`.

#### C. In-process library use

1. Application imports `ipfs_kit_py` (lazy JIT; no auto binary install by default).
2. Constructs `ipfs_kit` and/or `IPFSSimpleAPI` (HLA dual path **C-HLA**).
3. Optionally starts external daemons when requested; otherwise fails soft/hard per feature.
4. Same data-plane modules as CLI; caller owns process and any event loop.

Detail: [`RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md) §3.

#### D. fsspec open (packaged path)

1. Consumer opens `iroh://` or `iroh+blob://` via packaging entry points.
2. `IrohFileSystem` bridges sync fsspec API to Iroh client/service state.
3. Non-packaged `ipfs` fsspec paths require explicit import-time registration (**C-FSSPEC**).

### 5.3 Control-plane fan-out (single registry ideal)

```text
                    TOOL_GROUPS (mcp_server/tools)
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   HierarchicalTool     ipfs-kit-mcp-tools    FastMCP / JS SDK
   Manager + MCPServer  (one-shot CLI)        (registrar / manifest)
```

*Caption: one candidate tool registry fans out to server, CLI, and SDK surfaces; count drift is tracked as **C-MCP-TOOLS**, not as multiple authorities.*

---

## 6. Invariants and consistency guarantees

These are **working invariants** from packaging and focused tests—not ADR-accepted product law.

| Invariant | Evidence posture |
|---|---|
| **Packaging is the product map** for console scripts and fsspec protocols | `pyproject.toml` `[project.scripts]` / `fsspec.specs` |
| **Backend config validation is side-effect-free** | Registry must not open storage sessions or start daemons during type validation |
| **Content identity ≠ path ≠ metadata index** | CIDs address bytes; VFS paths map; Arrow/pin indexes are often secondary (**U-07** open) |
| **Control plane does not replace content stores** | Tools call into adapters/daemons; receipts prove work, not bytes |
| **Binary auto-install defaults off** | `IPFS_KIT_AUTO_INSTALL_BINARIES` falsy unless opted in |
| **Kit state root ≠ Kubo repo** | `~/.ipfs_kit` vs `~/.ipfs` |
| **Parallel modules are not equal defaults** | Compatibility paths labeled; unresolved IDs listed in map aggregate |
| **Fail-closed agent receipts** on MCP++ receipt resolver paths | `agent_supervisor_receipts.py` + focused tests |

Ordering and durability requirements for multi-writer VFS remain subsystem-owned (**U-06**).

---

## 7. Process, async, and lifecycle boundaries

| Runtime model | Examples | Event loop / process |
|---|---|---|
| Short-lived CLI | `ipfs-kit`, `ipfs-kit-mcp-tools`, most Iroh CLIs | Process-owned anyio/asyncio for command duration |
| Long-lived MCP++ | `ipfs-kit-mcp` | Process-owned `anyio` **trio** backend |
| In-process library | `import ipfs_kit_py`, fsspec | **Caller** owns process and loop |
| Background child | `ipfs-kit mcp start` (non-foreground) | Parent spawns child; PID under `~/.ipfs_kit` |
| External daemon | Kubo, Iroh service, Lotus | Separate OS processes; kit managers start/stop/status |

There is **no** universal AnyIO migration claim (**U-14**). Dual `foo` / `foo_anyio` modules remain. Full matrix: planned `ASYNC_AND_OPTIONAL_DEPENDENCIES.md`; per-entry tables: runtime guide.

---

## 8. Trust boundaries and sensitive-data handling

### 8.1 Trust domains

```text
  [Untrusted network peers / remote HTTP clients]
              │
              │  optional bind beyond loopback · P2P · remote backends
              ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  Host trust boundary (operator machine / agent container)   │
  │  ┌─────────────────────┐   ┌──────────────────────────────┐ │
  │  │ Control interfaces  │   │ Local state                  │ │
  │  │ MCP++ / CLI / lib   │──▶│ ~/.ipfs_kit backends, PIDs,  │ │
  │  │                     │   │ buckets, coordination, logs  │ │
  │  └─────────┬───────────┘   └──────────────────────────────┘ │
  │            │ may hold credential refs / decrypted secrets   │
  │            ▼                                                │
  │  ┌─────────────────────┐   ┌──────────────────────────────┐ │
  │  │ Data-plane adapters │──▶│ External services (Kubo/Iroh │ │
  │  │                     │   │ / S3 / Cluster)              │ │
  │  └─────────────────────┘   └──────────────────────────────┘ │
  └─────────────────────────────────────────────────────────────┘
```

*Caption: default MCP++ HTTP binds loopback; expanding exposure expands the attack surface. Credentials live in host state and remote backend auth—not in docs or logs.*

### 8.2 Sensitive-data rules (overview)

| Concern | Working rule | Pointer |
|---|---|---|
| Backend documents | Sensitive keys redacted via registry helpers | `backend_registry` redaction; map §7 |
| Credentials | Prefer references / encrypted managers over plaintext examples | `credential_manager.py`, `docs/credential_management.md` |
| Iroh security | Normative threat model and rotation in `docs/iroh/` | Planned network + trust guides |
| Agent receipts | Integrity-checked, fail-closed on read | `agent_supervisor_receipts.py` |
| Doc examples | No live tokens, keys, or host secrets | Documentation contract §10 |
| MCP HTTP | Default `127.0.0.1:8004`; authn/z for non-local bind **unresolved** | **U-13** / trust guide |
| Cluster auth | Present in code; trust story incomplete in prose | Map §4 gaps |

Subsystem-level trust deep-dives belong in planned `CONFIGURATION_STATE_AND_TRUST.md` and Iroh security docs—not duplicated here.

---

## 9. Deployment shapes and failure domains

### 9.1 Supported deployment shapes

| Shape | Components | When to use |
|---|---|---|
| **Library-only** | Import path; no long-lived kit process; optional attach to existing Kubo/Iroh | Embed in apps/tests; offline unit work |
| **Operator CLI workstation** | `ipfs-kit` + local `~/.ipfs_kit`; optional services | Day-2 ops, backend config, VFS verbs |
| **Agent control plane (stdio)** | `ipfs-kit-mcp` piped from host | IDE/agent local tooling (default trust model) |
| **Agent control plane (HTTP)** | `ipfs-kit-mcp --transport http` | Local multi-client; treat non-loopback as elevated risk |
| **Iroh-centric node** | Iroh binary + ops CLIs + fsspec `iroh://` | Namespace/blob workflows under Iroh contracts |
| **Kubo-centric node** | Managed/system Kubo + kit library/CLI | Classic IPFS content/pin workflows |
| **Multi-service node** | Kit + Kubo and/or Iroh + optional Lotus/Cluster | Full stack; higher failure-domain count |
| **Multi-node / cluster** | Bespoke cluster **or** Kubo Cluster wrappers (**U-08**) | Only with explicit role/transport choices |

### 9.2 Failure domains

| Domain | Failure examples | Isolation notes |
|---|---|---|
| **Control-plane process** | MCP++ crash, CLI exit, tool registry error | Does not by itself erase content stores |
| **Library caller process** | App crash mid-write | Durability depends on WAL/journal/backend commit |
| **Kubo daemon / repo** | Daemon down, lockfile, corrupt repo | Pins/blocks unavailable until recovery |
| **Iroh service / binary** | Missing binary, bad manifest, auth failure | fsspec/Iroh tools fail; Kubo path may still work |
| **Remote backend** | S3 auth/network errors | Other backends and local VFS may continue |
| **Optional extra missing** | No `libp2p` / `fsspec` / Arrow | Feature degrades or stubs; not always process-fatal |
| **Coordination / receipt store** | Fail-closed read on bad receipt | Agent verification fails closed rather than trust garbage |
| **Cluster peer** | Peer loss, state divergence | Model depends on bespoke vs Kubo Cluster (**U-08**) |

### 9.3 Expected degraded modes (summary)

| Condition | Typical behavior |
|---|---|
| Optional extra absent | Lazy import error or stub (`available = False` for HLA stub path) |
| Auto-install binaries off | Installers/setup skip downloads; status reports missing binary |
| Daemon not running | Tools/ops return structured failure; MCP++ process may stay up |
| Legacy MCP tree used | May work for historical dashboards; **not** packaging default for agents |
| JS SDK manifest lag | Python registry remains candidate authority (**C-MCP-TOOLS**) |

Observability: CLI status commands, Iroh diagnostics (`ipfs-kit-iroh-diagnostics`), MCP initialization/handshake tests, WAL/journal recovery paths (content guide). Deep telemetry is operations-owned.

---

## 10. Extension points and safe modification guidance

| Extension | Safe entry | Avoid |
|---|---|---|
| New MCP tool | Register in `TOOL_GROUPS` + hierarchical manager consumers | Second write-path registry; only patching JS manifest |
| New storage backend **type** | Plugin via `ipfs_kit.backends` / registry patterns | Side effects at import/validation; secrets in examples |
| New live adapter behavior | `backends/` adapter contracts | Treating config YAML as an open connection |
| New CLI verb | Unified dispatcher + FastCLI mount policy (**U-02**) | Adding only a satellite `*_cli.py` without packaging story |
| New fsspec protocol | Packaging entry points if product-facing | Import-time-only registration for “supported” claims |
| New cluster feature | Explicit family (bespoke vs Kubo wrappers) | Assuming one control plane without ADR |
| Docs for architecture | Subsystem guide + evidence map update | Resolving `U-*` without ADR / maintainer |

**Compatibility rule:** label shims and backups; do not present `*.fixed` / `archive/` as production defaults ([planned `COMPATIBILITY_LAYERS.md`](./COMPATIBILITY_LAYERS.md)).

---

## 11. Design rationale, trade-offs, and open decisions

Rationale confidence labels follow the documentation contract: **Accepted** (evidence-backed current tree), **Proposed** (ADR/intent only), **Inferred** (strong static evidence, not maintainer-signed), **Unknown**.

| Topic | Label | Notes |
|---|---|---|
| Packaging scripts as installable product map | **Accepted** (packaging evidence) | Console scripts and fsspec specs are measurable |
| Lazy import / JIT to keep import light | **Inferred** | Package root design + import tests |
| Single MCP tool registry ideal | **Inferred** / partial | `TOOL_GROUPS` is candidate; legacy trees and count drift open |
| Opt-in binary install | **Accepted** in code defaults | Older docs may still imply auto-install |
| Data plane vs control plane separation | **Accepted** as documentation structure | Matches map sections and glossary |
| Sole production MCP runtime | **Unknown** / open ADR | **U-11** — do not close here |
| Default content transport (Kubo vs Iroh) | **Unknown** | **U-09** |
| Canonical CLI composition end-state | **Unknown** | **U-02** |
| Version string single source | **Unknown** | **U-01** |

**Rejected alternatives (inferred from tree shape, not formal ADRs):** treating all MCP trees as equal product entries; documenting import-time binary download as default; equating bespoke cluster with Kubo Cluster wrappers; using generated API inventories as sole conceptual architecture.

Aggregate open list: [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md) **U-01..U-18** and matrix **C-*** IDs.

---

## 12. Tests, fixtures, and change triggers

### 12.1 Rank-1 tests that anchor this overview

Prefer default pytest discovery (`tests/`, `tests/unit/`; not `tests/integration/` / archived).

| Area | Representative tests |
|---|---|
| Import / package | `tests/test_ipfs_kit_import.py`, `tests/test_import_paths_validation.py`, `tests/test_architecture_support.py` |
| CLI | `tests/test_cli_import_verification.py`, `tests/test_cli_integration.py`, `tests/unit/test_minimal_cli.py` |
| MCP++ | `tests/test_mcp_jsonrpc_conformance.py`, `tests/test_mcp_server_integration.py`, `tests/test_mcp_initialization.py`, `tests/test_agent_supervisor_receipts.py` |
| Backends | `tests/test_backend_enhancements.py`, `tests/test_enhanced_backend_manager.py`, `tests/unit/test_configured_backends.py` |
| VFS / content | `tests/test_vfs_*.py`, `tests/test_bucket_*.py`, `tests/unit/test_filesystem_journal_comprehensive.py` |
| Iroh | `tests/test_iroh_*.py` (install, fsspec, security, packaging subset) |
| Install policy | `tests/test_auto_install_binaries.py`, `tests/test_installers.py` |

### 12.2 Change triggers and last-verified baseline

Re-verify this overview when any of the following change:

- `pyproject.toml` scripts, fsspec entry points, version, or Python floor
- Packaged MCP++ entry, `TOOL_GROUPS` layout, or receipt/coordination defaults
- Default state roots or binary install env policy
- Introduction or retirement of a major packaging entry path
- Resolution (ADR acceptance) of **U-01**, **U-09**, **U-11**, or **U-13**
- Material rewrite of sibling architecture guides that this document links as authority

**Last verified:** 2026-08-03 against tree `6fc55f0918a0f45e04b37727b45c1a1f5aaf9322`, using Wave 0 evidence maps and present sibling guides (`RUNTIME_AND_ENTRYPOINTS.md`, `CONTENT_METADATA_VFS.md`). Documentation validation policy: `IPFS_KIT_AUTO_INSTALL_BINARIES=0`.

**Offline validation for this document**

```bash
test -s docs/architecture/SYSTEM_OVERVIEW.md && rg -q "Trust boundaries" docs/architecture/SYSTEM_OVERVIEW.md
rg -n "data plane|control plane|Trust boundaries" docs/architecture/SYSTEM_OVERVIEW.md
```

---

## 13. Reading order and navigation

Recommended path for a new contributor or agent:

1. **This document** — system context, planes, trust, deployment shapes.
2. [`GLOSSARY.md`](./GLOSSARY.md) — shared terms (backend vs adapter, VFS, WAL, receipt).
3. [`RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md) — pick a supported entry and its lifecycle.
4. **Data plane:** [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md) → planned `STORAGE_BACKEND_SYSTEM.md`.
5. **Control plane:** planned `MCP_CONTROL_PLANE.md` (until present: runtime guide §5 + map §6).
6. **Distributed / network:** planned `CLUSTER_COORDINATION.md` + `NETWORK_TRANSPORTS.md` (+ `docs/iroh/`).
7. **Cross-cutting:** planned async/deps, configuration/trust, compatibility guides.
8. **Decisions:** `docs/architecture/decisions/` when ADRs exist for open `U-*` items.
9. **Evidence refresh:** [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md), [`PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md).

Historical audits under `docs/architecture/*AUDIT*` and campaign reports at `docs/` root are **not** the primary current architecture path.

---

## 14. Acceptance checklist (KDOC-010)

| Criterion | Met |
|---|---|
| Actors and external systems described | Yes (§3) |
| Package/runtime containers described | Yes (§3.3) |
| Primary data and control flows described | Yes (§5) |
| Storage **data plane** distinguished from **control plane** | Yes (§5) |
| Trust boundaries section present | Yes (§8 — includes required phrase for validation) |
| Deployment shapes and failure domains | Yes (§9) |
| Reading order provided | Yes (§13) |
| Evidence-linked (source/tests/maps) | Yes (header, §4, §11–§12) |
| Bounded diagrams with captions | Yes (§3.3, §5.1, §5.3, §8.1) |
| Links instead of duplicating subsystem detail | Yes (sibling table + non-goals) |
| Unresolved authorities left open | Yes (§2.2, §11) |
| Validation: non-empty file + `Trust boundaries` | Yes |

*End of SYSTEM_OVERVIEW.md — KDOC-010 architecture guide.*
