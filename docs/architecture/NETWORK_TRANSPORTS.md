# Network transports: Kubo, Iroh, libp2p, routing, and P2P workflows

| Field | Value |
|---|---|
| **Document class** | Canonical (architecture guide) |
| **Status** | active |
| **Task** | KDOC-016 |
| **Goal** | KDOC-G023 |
| **Track** | arch-distributed |
| **Last verified** | 2026-08-03 |
| **Tree baseline** | `294271ade01e4e4c03a8b1693159fff8c99f3c34` |
| **Evidence** | [SOURCE_OF_TRUTH_MAP §5, §9](./SOURCE_OF_TRUTH_MAP.md), [PUBLIC_SURFACE_MATRIX](../audits/PUBLIC_SURFACE_MATRIX.md) (S09, S15–S18, S21), packaging `pyproject.toml`, `ipfs_kit_py/iroh/`, `ipfs_kit_py/libp2p/`, `ipfs_kit_py/routing/`, `ipfs_kit_py/kubo_runtime.py`, MCP++ tools and P2P transport, focused tests under `tests/test_iroh_*`, `tests/test_p2p_workflow.py`, `tests/test_simple_libp2p.py` |
| **Related** | Normative Iroh runbooks under [`docs/iroh/`](../iroh/) (do not treat this guide as a substitute); planned [CLUSTER_COORDINATION.md](./CLUSTER_COORDINATION.md), [STORAGE_BACKEND_SYSTEM.md](./STORAGE_BACKEND_SYSTEM.md), [MCP_CONTROL_PLANE.md](./MCP_CONTROL_PLANE.md); unresolved decisions U-09, U-10, U-12, U-16 |

## 1. Scope and non-goals

### 1.1 Scope

This guide answers how **content-plane and control-plane network roles** coexist in `ipfs_kit_py`:

1. **Kubo / IPFS** — managed or external Kubo daemon, HTTP/API clients, bitswap/swarm/pin data plane.
2. **Iroh** — package-owned sidecar, BLAKE3 blobs, manifests, local RPC, install and ops CLIs.
3. **libp2p** — optional Python peer stack for direct P2P, discovery, bitswap-style exchange, and MCP++ stream transport.
4. **Routing** — multi-backend *placement* selection (`ipfs_kit_py/routing/`), not DHT peer routing alone.
5. **P2P workflow coordination** — Merkle-clock task assignment for GitHub-Actions-style workflows across peers.

It maps **actual** CLI, MCP++, and Python exposure; transport, security, and lifecycle boundaries; interoperability limits; failure and degradation modes; and **why coexistence is used or still proposed**.

### 1.2 Explicit non-goals

- **Not** a rewrite of normative Iroh contracts in `docs/iroh/*` (filesystem contract, security, threat model, interoperability harness, lifecycle). This guide **links** them.
- **Not** selection of a single cluster control plane (owned by cluster architecture / ADR work; see U-08).
- **Not** resolution of MCP production authority among `mcp_server` vs legacy `mcp/` (U-11).
- **Not** a full API inventory of every method on `IPFSLibp2pPeer` or every Kubo HTTP route.
- **Not** upstream protocol tutorials for IPFS, Iroh, or libp2p.

### 1.3 Role separation (precondition for this guide)

Treat these as **separate roles**, even when code or docs blur the names:

| Role | What it is | What it is not |
|---|---|---|
| **Protocol stack** | Wire protocols and peer connectivity (libp2p, Iroh QUIC/relay, Kubo swarm) | A storage backend config document |
| **Storage backend** | Named, validated config + live adapter (IPFS, Iroh, S3, …) | A daemon lifecycle manager |
| **FSSpec filesystem** | Path-oriented data plane (`iroh://`, IPFS fsspec modules) | The MCP tool registry |
| **RPC sidecar** | Local Iroh sidecar over Unix socket / local RPC | Remote multi-tenant control plane |
| **Routing** | Choosing which *backend* holds content | Full multi-node membership consensus |
| **Workflow coordination** | Assigning CI-like tasks to peers | Content bitswap or blob transfer |

---

## 2. Why multiple transports coexist

### 2.1 Observed product shape

The repository **does not** collapse onto a single content network. Packaging and code deliberately expose:

| Transport family | Product posture | Evidence |
|---|---|---|
| **Kubo / IPFS** | Historical and still primary path for CID/pin/swarm operations, kit façade, most MCP IPFS tools | `ipfs_kit_py/ipfs.py`, `kubo_runtime.py`, MCP `ipfs_*` / `pin_*` / `swarm_*` / `bitswap_*` tools |
| **Iroh** | First-class optional backend with the **strongest in-tree normative contract suite** and dedicated console scripts | `ipfs_kit_py/iroh/*`, `docs/iroh/*`, scripts `ipfs-kit-iroh*` |
| **libp2p (Python)** | Optional extra for direct peer ops, cache-miss retrieval, and MCP++ Profile E stream transport | `extras.libp2p` tracks `py-libp2p@main`; `libp2p_peer.py`, `mcp_server/p2p_transport.py` |
| **Multi-backend routing** | Library (and optional HTTP) selection among backends by cost/latency/type | `routing/router.py`, `routing/routing_manager.py`; gRPC path **deprecated** |

### 2.2 Rationale labels (confidence)

| Claim | Confidence | Notes |
|---|---|---|
| Kubo remains the default ecosystem path for **CID-addressed** IPFS content and swarm tooling | **Inferred** from MCP tool mix (28 of 29 tools are IPFS/CID-oriented; only `iroh_diagnostics` is Iroh-named) and kit client wiring | Does not prove operator default for *new* greenfield storage |
| Iroh is integrated as a **parallel blob/manifest backend**, not a drop-in CID replacement | **Accepted** (normative Iroh docs + code): BLAKE3 hashes must never be labeled as IPFS CIDs | See `docs/iroh/compatibility.md`, capability matrix |
| libp2p is **optional and fail-soft** when the extra is missing | **Accepted** from `HAS_LIBP2P` checks and MCP P2P transport `HAVE_LIBP2P` | Tracking upstream `main` is a known risk (U-10) |
| Coexistence is intentional for different trust, identity, and addressing models | **Inferred** from separate lifecycle, credentials, and address formats | Owner default among Kubo / Iroh / dual-write is **unresolved** (U-09) |
| Dual-write or automatic cross-network bridging is the production default | **Not claimed** | No accepted ADR; do not document as implemented |

**Unresolved (U-09):** Default content transport for new deployments — Kubo, Iroh, or dual-write — requires maintainer ADR (proposed slot noted in SOURCE_OF_TRUTH_MAP as ADR 0006). Until then, architecture prose must describe **parallel capabilities**, not a single “the network.”

### 2.3 Decision tree for content paths (current behavior)

```text
Need content-addressed bytes?
├── Identity is IPFS CID (CIDv0/v1, multihash)
│   ├── Live Kubo (or compatible) API available?
│   │   ├── Yes → kit client / MCP ipfs_* / pin_* / bitswap_*
│   │   └── No  → optional libp2p peer bitswap/DHT miss path (if extra installed)
│   └── System PATH vs package-managed Kubo: managed bin prepended when present
│
├── Identity is Iroh BLAKE3 blob / namespace manifest
│   ├── Sidecar installable and protocol 1 negotiated?
│   │   ├── Yes → Iroh backend / fsspec / ops CLIs
│   │   └── No  → fail closed (source-pinned release may be installable:false)
│   └── Never treat BLAKE3 as CID or vice versa
│
└── Choose among multiple configured backends (S3, IPFS, Iroh, …)
    └── routing.DataRouter / RoutingManager (library or HTTP; not gRPC)
```

---

## 3. Component ownership and source-of-truth paths

### 3.1 Candidate authorities

| Concern | Paths |
|---|---|
| Iroh service, protocol, backend plugin, blob store, manifest, security, multinode | `ipfs_kit_py/iroh/` (`service.py`, `client.py`, `backend.py`, `blob_store.py`, `manifest.py`, `protocol.py`, `security.py`, `multinode.py`, CLIs) |
| Iroh install / packaging | `ipfs_kit_py/iroh_install_cli.py`, `install_iroh.py`, `pyproject.toml` extras `iroh` and scripts `ipfs-kit-iroh*` |
| Iroh normative docs (retain) | `docs/iroh/*.md` |
| Iroh fsspec | `ipfs_kit_py/iroh_fsspec.py`; packaging `fsspec.specs` → `iroh`, `iroh+blob` |
| Live Iroh storage adapter | `ipfs_kit_py/backends/iroh_backend.py` |
| libp2p package integration | `ipfs_kit_py/libp2p/` (discovery, gossipsub, protocols, `p2p_integration.py`, `anyio_compat.py`) |
| Primary libp2p peer façade | `ipfs_kit_py/libp2p_peer.py` (`IPFSLibp2pPeer`) |
| MCP++ P2P stream transport | `ipfs_kit_py/mcp_server/p2p_transport.py` (`PROTOCOL_ID = /mcp+p2p/1.0.0`) |
| P2P workflow coordinator | `ipfs_kit_py/p2p_workflow_coordinator.py` |
| P2P workflow CLI module | `ipfs_kit_py/cli/p2p_workflow_cli.py` (**not** a packaging console script) |
| Multi-backend data routing | `ipfs_kit_py/routing/` (`router.py`, `routing_manager.py`, `http_server.py`) |
| Package-local Kubo binary | `ipfs_kit_py/kubo_runtime.py`, `install_ipfs.py` |
| Primary IPFS client (kit path) | `ipfs_kit_py/ipfs.py` (`class ipfs_py`) |
| Daemon managers (parallel) | `ipfs_daemon_manager.py`, `enhanced_daemon_manager.py`, `intelligent_daemon_manager.py`, cluster variants |

### 3.2 Compatibility / historical paths

| Path | Notes |
|---|---|
| `libp2p` extra → `git+…/py-libp2p.git@main` | Moving target; not a pinned contract (U-10) |
| `libp2p_mocks.py`, test doubles | Non-production |
| Routing gRPC (`grpc_*.py`, `standalone_grpc_server.py`, backups) | **Deprecated** (protobuf conflicts with libp2p/env); see `routing/GRPC_DEPRECATION_NOTICE.md` |
| Parallel `ipfs_py` definitions | `ipfs.py` (kit), `ipfs_client.py`, `ipfs/ipfs_py.py` — **unresolved** canonical client (U-12) |
| Multiple daemon managers | **Unresolved** single lifecycle authority (U-16) |
| Legacy MCP libp2p controllers/models | `ipfs_kit_py/mcp/controllers/libp2p_*`, `mcp/models/libp2p_model.py` — compatibility stack, not MCP++ packaging default |
| Root/package P2P workflow docs claiming `ipfs-kit p2p …` | **Aspirational** relative to packaged `cli.py` FastCLI (no `p2p` subcommand mount observed) |

---

## 4. Actual surface exposure (CLI / MCP / Python)

Claims below are measured against packaging and import wiring on the verification baseline—not marketing feature lists.

### 4.1 Packaged console scripts (network-related)

| Script | Target | Role |
|---|---|---|
| `ipfs-kit` | `ipfs_kit_py.cli:sync_main` | Operator CLI: selective mounts (`bucket`, `vfs`, `wal`, `pin`, `backend`, `journal`, `state`) plus native `mcp`, `daemon`, `services`, `autoheal`. **No packaged `p2p` subcommand.** |
| `ipfs-kit-mcp` | `mcp_server.server:main` | MCP++ control plane; `--transport {stdio,http,p2p}` |
| `ipfs-kit-mcp-tools` | `mcp_server.cli:main` | Tool listing/invocation CLI over the same registry |
| `ipfs-kit-iroh` | `iroh_install_cli:main` | Install / inspect managed Iroh sidecar |
| `ipfs-kit-iroh-ops` | `iroh.cli:main` | Iroh operations |
| `ipfs-kit-iroh-diagnostics` | `iroh.diagnostics_cli:main` | Diagnostics |
| `ipfs-kit-iroh-manifest` | `iroh.manifest_cli:main` | Manifest ops |
| `ipfs-kit-iroh-interop` | `iroh.multinode:main` | Interoperability harness / evidence check |

fsspec entry points: `iroh` and `iroh+blob` → `IrohFileSystem` only (IPFS fsspec is **not** in packaging entry points; authority unresolved C-FSSPEC).

### 4.2 MCP++ tool registry (network-facing)

Single write-path registry: `TOOL_GROUPS` in `ipfs_kit_py/mcp_server/tools/__init__.py` (**29** tools measured on this baseline).

| Group | Tools | Transport dependency |
|---|---|---|
| `ipfs_tools` | `ipfs_add`, `ipfs_cat`, `ipfs_ls` | Kubo/IPFS API |
| `pin_tools` | `pin_add`, `pin_ls`, `pin_rm`, `get_pinset` | Kubo/IPFS |
| `dag_tools` | `dag_get`, `dag_put` | Kubo/IPFS |
| `mfs_tools` | `files_*` | Kubo MFS |
| `swarm_tools` | `node_id`, `swarm_peers` | Kubo swarm / identity |
| `name_tools` | `name_publish`, `name_resolve` | IPNS |
| `block_tools` | `block_put`, `block_get`, `block_stat` | Block API |
| `bitswap_tools` | `bitswap_stat`, `bitswap_wantlist` | Bitswap stats |
| `stats_tools` | `stats_bw`, `stats_repo` | Repo/bandwidth |
| `car_tools` | `create_car` | CAR packaging |
| `cluster_tools` | `cluster_status` | Cluster (not full transport stack) |
| `iroh_tools` | `iroh_diagnostics` | Iroh diagnostics only |

**Exposure notes:**

- There is **no** MCP++ tool group that runs Iroh blob ingest/read as first-class tools comparable to `ipfs_add`/`ipfs_cat`. Iroh data-plane is primarily Python/fsspec/backend + dedicated Iroh CLIs.
- `iroh_diagnostics` is in the registry but has been observed missing from the JS SDK tools manifest (**C-MCP-TOOLS** / U-18)—do not assume SDK parity.
- Legacy `mcp/p2p_workflow_tools.py` and libp2p controllers are **not** the packaged MCP++ registry.

### 4.3 MCP++ transports

| Transport | Default | Requirements | Behavior when unavailable |
|---|---|---|---|
| **stdio** | Yes (`--transport stdio`) | None beyond server deps | N/A (default) |
| **HTTP** | Bind `127.0.0.1:8004` | Hypercorn + anyio trio backend | Do not select HTTP without deps |
| **P2P** | Opt-in `--transport p2p` | `libp2p` extra; protocol `/mcp+p2p/1.0.0` | `HAVE_LIBP2P` false → RuntimeError if forced; stdio/HTTP remain |

P2P transport serves the **same JSON-RPC tool handler** over a libp2p stream; it is a **control-plane** carriage, not a content-replication protocol.

### 4.4 Python package exposure

| Symbol / module | How obtained | Status |
|---|---|---|
| `P2PWorkflowCoordinator`, `WorkflowStatus`, `WorkflowTask`, related helpers | Lazy getters and names in package `__all__` (`get_p2p_workflow_coordinator`, etc.) | **Exported** prominently; **not** a console script |
| `P2PWorkflowTools` | `get_p2p_workflow_tools()` → legacy `mcp.p2p_workflow_tools` | Compatibility / optional |
| `IPFSLibp2pPeer` | `ipfs_kit_py.libp2p_peer` | Requires `libp2p` extra |
| `ipfs_kit_py.libp2p` | Package with `HAS_LIBP2P`, dependency checks | Fail-soft import |
| `ipfs_kit_py.iroh.*` | Direct imports; ops via CLIs | Optional `iroh` extra + sidecar |
| `IrohFileSystem` | fsspec / `iroh_fsspec` | Packaged protocol brands |
| `ipfs_py` (primary kit path) | `from ipfs_kit_py.ipfs import ipfs_py` via kit façade | Parallel clients exist (U-12) |
| `RoutingManager` / `DataRouter` | `ipfs_kit_py.routing` | Library API; optional FastAPI registration |
| Daemon managers | Various `*daemon_manager*` modules | CLI `ipfs-kit … services` path uses `EnhancedDaemonManager` in current `cli.py` handlers |

### 4.5 P2P workflow CLI — documented vs packaged

`cli/p2p_workflow_cli.py` documents usage as:

```text
ipfs-kit p2p workflow submit …
ipfs-kit p2p peer list
…
```

**Measured packaging fact:** `pyproject.toml` does not define an `ipfs-kit-p2p` script, and packaged `ipfs_kit_py/cli.py` FastCLI does not mount a `p2p` subcommand family. The module is invokable as a library (`P2PWorkflowCLI`) or via `python -m`-style `__main__` of that file in a source checkout.

| Surface | Status |
|---|---|
| Python `P2PWorkflowCoordinator` | Present; unit-tested (`tests/test_p2p_workflow.py`) |
| Module CLI | Present under `cli/p2p_workflow_cli.py` |
| Packaged `ipfs-kit p2p …` | **Not wired** as of this baseline — treat feature docs that claim it as **aspirational / drift** until CLI composition (U-02) mounts it |
| MCP++ tools for workflow submit/assign | **Not** in `TOOL_GROUPS` |

---

## 5. Transport families in depth

### 5.1 Kubo / IPFS

#### Role

Content-addressed block and DAG storage using **IPFS CIDs**, pin retention, swarm peer connectivity, bitswap exchange, IPNS, and MFS—typically via a **Kubo** (go-ipfs) process exposing an HTTP API (commonly `localhost:5001`) and optional CLI `ipfs`.

#### Lifecycle

| Mechanism | Path | Notes |
|---|---|---|
| Package-managed binary | `kubo_runtime.ensure_kubo_binary` | Install/upgrade **off by default**; `IPFS_KIT_AUTO_INSTALL_BINARIES=1` opts in; managed dir prepended to `PATH` |
| Installer | `install_ipfs.py` | Used when install is enabled |
| Daemon managers | Multiple classes (U-16) | CLI service handlers currently import `EnhancedDaemonManager` for start/stop/status |
| Client | `ipfs_py` in `ipfs.py` | Subprocess and/or API-oriented operations; daemon fallbacks exist |

**Doc validation policy:** set `IPFS_KIT_AUTO_INSTALL_BINARIES=0` so documentation and offline checks do not pull binaries.

#### Security / trust boundaries

- Kubo API ports and gateway ports are **host trust boundaries**. Binding beyond loopback expands attack surface.
- Swarm connects to **untrusted peers** on the public IPFS network unless restricted (private swarm keys / bootstrap policy are Kubo configuration concerns).
- Pins and repo paths under `IPFS_PATH` are durable state; treat as sensitive data stores.
- Auto-install writes into package or `IPFS_KIT_BIN_DIR` managed locations—verify digests/source of installers in production.

#### Failure modes

| Failure | Symptom | Degraded mode |
|---|---|---|
| No Kubo binary | Client/daemon ops fail | Managed install only if explicitly enabled |
| Daemon not running / API down | Timeouts, connection errors | WAL/retry paths may queue storage ops; libp2p miss path may help content get only if configured |
| Swarm isolated | Content not findable remotely | Local repo still serves local pins |
| Competing `ipfs_py` import path | Subtle behavioral drift | Name the import path in new code; U-12 open |

### 5.2 Iroh

#### Role

Parallel **blob and namespace** stack: immutable **BLAKE3** content, versioned **manifests**, docs/gossip sync, local **sidecar RPC** (`system`, `blobs`, `manifests`, `sync` capability groups). Product binary identity is `ipfs-kit-iroh-sidecar`, not a generic upstream CLI.

Normative detail: [`docs/iroh/compatibility.md`](../iroh/compatibility.md), [`filesystem-contract.md`](../iroh/filesystem-contract.md), [`capability-matrix.md`](../iroh/capability-matrix.md), [`security.md`](../iroh/security.md), [`service-lifecycle.md`](../iroh/service-lifecycle.md), [`interoperability.md`](../iroh/interoperability.md), [`threat-model.md`](../iroh/threat-model.md).

#### Lifecycle

- `IrohService` (`iroh/service.py`): async `start` / `stop` / `restart` / `status` / `health_check`; PID **ownership receipts**; crash-loop protection; managed-child vs foreground modes.
- Install: `ipfs-kit-iroh` + `install_iroh.IrohInstaller` against `resources/iroh-releases.json`.
- **Source-pinned / fail-closed:** when platforms are `installable: false`, installers and discovery must not pretend a binary exists ([compatibility.md](../iroh/compatibility.md)).

#### Security / trust boundaries

Summarized from normative security docs (do not weaken here):

| Asset | Handling |
|---|---|
| Node private identity | Credential store / secretref; not logs or URLs |
| Write capability / read tickets | Bearer authority; resolve only at RPC boundary |
| Local RPC socket | Host-local, least privilege; not a remote multi-tenant API |
| Config | Opaque `secretref:` / `credential://` only; reject inline secrets |

Python config plugin: `IrohBackendPlugin` in `iroh/backend.py` (validation, migration, redaction, health without starting storage sessions at config time).

#### Interoperability limits

- **BLAKE3 ≠ CID.** Interop with Kubo is **not** native content addressing equivalence.
- Multi-node scenarios (direct LAN, relay, NAT, resume, version skew, key rotation, large data) are defined by the **interop harness**; checked-in evidence may be `not_run` until a release lane runs real nodes.
- Upstream `iroh-relay` / DNS servers are infrastructure; they are **not** the kit filesystem sidecar.

#### Failure modes

| Failure | Stable / expected behavior |
|---|---|
| Missing/incompatible sidecar | Fail closed; no silent fallback to Kubo for Iroh URLs |
| Protocol/version mismatch | Negotiation failure before storage ops |
| Integrity mismatch | `IROH_INTEGRITY_ERROR` (and related codes)—reject content |
| Manifest CAS conflict | `IROH_CONFLICT`; no partial published revision |
| Unsupported FS op (e.g. append) | `IROH_UNSUPPORTED_OPERATION` |
| Crash loop | Persistent protection until operator clear while stopped |

### 5.3 libp2p (Python)

#### Role

Optional **in-process** peer stack for:

- Direct connections, DHT/mDNS discovery, pubsub (gossipsub when available)
- Protocol handlers including bitswap-style content exchange (`IPFSLibp2pPeer`)
- Integration hooks for cache miss → P2P fetch (`libp2p/p2p_integration.py`, kit integration modules)
- MCP++ control-plane stream transport (`/mcp+p2p/1.0.0`)

#### Lifecycle / dependency

- Extra: `libp2p` in `pyproject.toml` (pulls `libp2p @ git+https://github.com/libp2p/py-libp2p.git@main` plus multiaddr/cryptography/protobuf constraints).
- `ipfs_kit_py.libp2p.check_dependencies()` / `HAS_LIBP2P`; peer construction attempts install only under controlled paths—prefer explicit extras in production images.
- Many submodules degrade individually (pubsub, kademlia, streams) with warnings rather than hard import failure of the whole package.

#### Security / trust boundaries

- Peer identity keys and multiaddrs are sensitive; do not log private keys.
- Connecting to arbitrary multiaddrs is a **network trust** decision; there is no Iroh-style ticket ACL on the MCP P2P stream by itself—MCP auth/policy layers (if enabled via MCP++ extras) are separate.
- Tracking upstream `main` means **protocol and API skew** is a first-class operational risk (U-10).

#### Interoperability limits

- Compatibility with go-libp2p / Kubo swarm is a **goal** of enhanced modules, not a fully certified matrix in this repository’s Iroh-style contract suite.
- Test depth is **thinner** than Iroh (`tests/test_simple_libp2p.py`, unit health tests) relative to the large `libp2p/` tree.
- Not a substitute for Kubo’s full DHT provider record ecosystem unless the peer is correctly bootstrapped and protocols match.

#### Failure modes

| Failure | Behavior |
|---|---|
| Extra not installed | `HAS_LIBP2P` / `HAVE_LIBP2P` false; P2P MCP transport refuses start; peer features limited |
| Partial submodule import | Specific features (pubsub, DHT, streams) disabled with warnings |
| Upstream main break | Import or runtime errors; pin policy unresolved (U-10) |
| NAT without relay/DCUtR success | Peer reachable only on local/direct paths |

### 5.4 Multi-backend routing

#### Role

**Application-level** selection of a **storage backend id** (IPFS, Filecoin, S3, Iroh, …) based on content type, performance, cost, geography, and load—not “find providers for a CID on the DHT” alone (that lives under libp2p/Kubo).

Primary types: `DataRouter`, `RoutingStrategy`, `RoutingManager`, `RoutingManagerSettings` in `routing/router.py` and `routing/routing_manager.py`.

#### Control path status

| Path | Status |
|---|---|
| In-process `RoutingManager.select_backend` / `select_optimal_backend` | Supported library path |
| HTTP server (`routing/http_server.py`) | Present; may be registered with FastAPI |
| gRPC server/client | **Deprecated** — protobuf version conflicts with libp2p stack; do not use for new work |

#### Failure modes

| Failure | Behavior |
|---|---|
| No backends registered | Selection fails or falls back per settings |
| Metrics collection errors | Insights degrade; simple selection may remain |
| Calling deprecated gRPC | Import/runtime validation failures — migrate to HTTP/library |

### 5.5 P2P workflow coordination

#### Role

Distribute **workflow tasks** (GitHub Actions–like YAML tagged `p2p-workflow` / `offline-workflow`) across peers using:

- **Merkle clock** consensus helpers (`merkle_clock`)
- **Hamming distance** owner selection
- **Fibonacci heap** priority queue

State directory default: `~/.ipfs_kit/p2p_workflows`.

This is **orchestration**, not content transport. Completing a workflow may *use* Kubo/Iroh/libp2p, but the coordinator itself tracks assignment and status.

#### Exposure recap

Python-first; CLI module exists; **not** packaged as `ipfs-kit p2p`; **not** in MCP++ `TOOL_GROUPS`.

#### Failure modes

| Failure | Behavior |
|---|---|
| Empty peer list | Tasks assign only to self or remain pending per logic |
| State file corruption | Load/save errors; local state may reset |
| Peer partition | Local clocks diverge; no full CAP guarantee documented as linearizable cluster consensus |
| Confusion with MCP P2P transport | Different layer—do not mix protocol IDs or expectations |

---

## 6. Data and control flow

### 6.1 Layered view

```text
┌──────────────────────────────────────────────────────────────────┐
│  Surfaces: Python API · ipfs-kit CLI · ipfs-kit-mcp (stdio/HTTP/P2P) │
│            ipfs-kit-iroh* · fsspec (iroh://) · optional module CLIs  │
└───────────────┬───────────────────────────┬──────────────────────┘
                │ control                   │ data intents
                ▼                           ▼
┌───────────────────────────┐   ┌──────────────────────────────────┐
│ MCP++ TOOL_GROUPS         │   │ Backends / clients / filesystems │
│ (mostly IPFS tools +      │   │  ipfs_py · IPFS adapter          │
│  iroh_diagnostics)        │   │  Iroh client/sidecar · fsspec    │
└───────────────┬───────────┘   │  libp2p peer (optional miss path)│
                │               │  RoutingManager → backend pick   │
                │               └───────────────┬──────────────────┘
                │                               │
        ┌───────▼────────┐            ┌─────────▼──────────┐
        │ MCP P2P stream │            │ Wire / process     │
        │ /mcp+p2p/1.0.0 │            │ Kubo swarm/API     │
        │ (libp2p)       │            │ Iroh RPC + net     │
        └────────────────┘            │ libp2p protocols   │
                                      └────────────────────┘

Side plane: P2PWorkflowCoordinator (task assignment state, not blob bytes)
```

### 6.2 Content plane comparison

| Concern | Kubo / IPFS | Iroh | libp2p peer |
|---|---|---|---|
| Content ID | CID | BLAKE3 hex | Usually CID-oriented handlers |
| Process model | External daemon common | Managed sidecar + local RPC | In-process host |
| Auth model | API auth / swarm | Tickets, capabilities, ACL, secretrefs | Peer keys; app-level policy |
| Pin / retention | Pins | protect/release + manifest live set | Application-defined |
| Primary kit exposure | MCP tools + kit client | CLIs + fsspec + backend plugin | Optional Python + MCP transport |

### 6.3 Invariants

1. **Address family isolation:** Do not cast Iroh BLAKE3 identifiers as IPFS CIDs or present CIDs as Iroh blob hashes ([compatibility](../iroh/compatibility.md)).
2. **Config vs live connection:** Backend type registry validation must remain side-effect-free (no daemon start at import/validate time).
3. **MCP tool write path:** Production MCP++ tools register only through `TOOL_GROUPS` / hierarchical manager—not parallel ad-hoc registries.
4. **Iroh integrity:** Accepted blob bytes match declared digest and size before cache/export trust.
5. **Optional stacks degrade:** Missing `libp2p` or unpublishable Iroh artifacts must fail closed or skip—not fabricate success (interop evidence rules reinforce this).
6. **Routing gRPC is not the future control path** for multi-backend selection.

---

## 7. Process, async, and lifecycle boundaries

| Component | Process ownership | Async notes |
|---|---|---|
| Kubo | Separate OS process; kit managers start/stop/status | Client calls often sync wrappers; daemon managers mix sync/async |
| Iroh sidecar | Separate process; `IrohService` ownership receipts | Lifecycle APIs are async; fsspec/sync bridges exist in product code |
| libp2p host | In-process with the Python runtime that started it | anyio/trio used by MCP server; peer has sync/async helpers (`_run_async_from_sync`) |
| MCP++ server | Own process via `ipfs-kit-mcp`; trio backend | Transports mutually chosen at startup |
| Routing manager | In-process; optional background metrics tasks | `async` select/metrics APIs |
| P2P workflow | In-process coordinator; file-backed state | Sync coordinator API; anyio imported for future/async use |

**Do not** run the same Iroh instance under both systemd foreground mode and a second managed-child supervisor ([service-lifecycle](../iroh/service-lifecycle.md)).

**Do not** assume one “daemon manager” class is canonical (U-16).

---

## 8. Trust boundaries and sensitive data

| Boundary | Crosses | Must not leak |
|---|---|---|
| Operator host → Kubo API | HTTP/CLI to local or remote API | Unintended remote API exposure without auth |
| Operator host → Iroh RPC | Unix socket / local endpoint | Node keys, tickets, write caps, secretref values |
| Public network → swarm / Iroh peers | Encrypted transports + app auth | Private keys; treat peer content as untrusted until verified |
| MCP client → MCP server | stdio / loopback HTTP / libp2p stream | Tool arguments that embed secrets; receipts must stay fail-closed where applicable |
| Docs / logs / metrics | Observability pipelines | Tickets, keys, raw secretrefs, peer private material |

Iroh normative rules forbid secrets in argv, URLs, env diagnostics, exceptions, and support bundles—apply the same hygiene to Kubo and libp2p key material.

---

## 9. Expected failures, degraded modes, and observability

### 9.1 Cross-cutting degradation matrix

| Missing / broken | User-visible effect | Safe degraded mode |
|---|---|---|
| Kubo binary + auto-install off | IPFS tools/daemon fail | Document install path; do not auto-download in CI docs |
| Kubo up, swarm down | Local pin ops work; remote get fails | Cache / local-only |
| Iroh extra present, binary not installable | Installer fail-closed | Use Kubo/other backends; do not fake Iroh health |
| Iroh sidecar crash loop | `status` not ready | Clear crash loop only when stopped; fix config |
| `libp2p` extra absent | No in-process peer; MCP `--transport p2p` fails | stdio/HTTP MCP; Kubo-only content path |
| libp2p present, discovery fails | Empty peer set | Local-only P2P features |
| Routing misconfigured | Wrong/expensive backend | Explicit backend id in caller; check insights APIs |
| P2P workflow not on CLI | `ipfs-kit p2p` missing | Use Python API or module CLI until packaged |
| JS SDK manifest drift | Missing `iroh_diagnostics` in SDK | Call via Python MCP tools list from live server |

### 9.2 Observability hooks

| Stack | Hooks |
|---|---|
| Iroh | Diagnostics CLI, service `status`/`health_check`, observability module, normative [observability.md](../iroh/observability.md) |
| Kubo | `stats_*`, `bitswap_*`, `swarm_peers`, daemon manager status |
| libp2p | Logging; unit health API tests; limited structured product metrics |
| Routing | `get_routing_insights`, metrics collection task |
| P2P workflow | `get_stats()`, list/status on coordinator |

---

## 10. Extension points and safe modification guidance

| Extension | Do | Do not |
|---|---|---|
| New MCP network tool | Register in `TOOL_GROUPS`; add tests; update JS manifest generation inputs | Add only to legacy `mcp/` controllers and call it “MCP++” |
| New Iroh RPC method | Advance protocol version + `docs/iroh` contracts + release record together | Hand-edit interoperability evidence to `passed` |
| New libp2p protocol | Gate on `HAS_LIBP2P`; degrade cleanly; add focused tests | Require libp2p for core import of `ipfs_kit_py` |
| New backend in routing | Register backend ids with the manager; prefer library API | Revive gRPC routing stack |
| Wire P2P workflow into CLI | Mount under FastCLI / unified dispatcher; add packaging test | Only update markdown usage strings |
| Cross-transport bridge (CID ↔ BLAKE3) | Explicit conversion service with dual storage policy + ADR | Silent reencoding presented as the same identifier |

---

## 11. Design rationale, trade-offs, rejected or open alternatives

| Topic | Position | Confidence |
|---|---|---|
| Keep Kubo and Iroh as parallel systems | Matches addressing, lifecycle, and security models; strongest Iroh docs remain separate from IPFS | **Accepted** coexistence *as implemented*; **open** which is default (U-09) |
| Optional libp2p extra tracking `main` | Maximizes upstream features; risks breakages | **Accepted** packaging choice; pin policy **unresolved** (U-10) |
| MCP tools mostly IPFS-shaped | Reflects existing agent/tooling demand for CID ops | **Inferred** |
| Iroh data plane via CLIs/fsspec more than MCP tools | Keeps MCP surface smaller; Iroh ops highly specialized | **Inferred** |
| Deprecate routing gRPC | Resolves protobuf conflict with libp2p ecosystem | **Accepted** (deprecation notice) |
| P2P workflow as library-first | Coordination experiments without forcing console script | **Inferred**; packaging gap is **documented drift**, not a feature |
| Dual-write every object to Kubo and Iroh | Would simplify “one pipe” mental model | **Not implemented** as default; requires ADR if proposed |
| Replace Kubo entirely with Iroh | Rejected for now by continued Kubo client/tool investment | **Inferred** product direction—not a formal rejection ADR |

---

## 12. Tests and fixtures

Prefer default pytest discovery (`tests/integration` and archived suites are excluded by `pytest.ini` norecursedirs unless invoked explicitly).

| Area | Focused tests / fixtures |
|---|---|
| Iroh | `tests/test_iroh_*.py` (backend, blob, CLI, config, fsspec, install, MCP API, multinode, observability, packaging, performance, security, service, release, …); fixtures under `tests/fixtures/iroh/`; resources `ipfs_kit_py/resources/iroh-*.json` |
| Iroh interop | `tests/test_iroh_multinode.py`; evidence `resources/iroh-interoperability-evidence.json` (may be `not_run`) |
| libp2p | `tests/test_simple_libp2p.py`, `tests/unit/test_enhanced_libp2p.py`, `tests/unit/test_libp2p_health_api.py` |
| P2P workflow | `tests/test_p2p_workflow.py` |
| Daemon / Kubo lifecycle | `tests/unit/test_daemon_manager.py`, `test_daemon_startup.py`, `test_enhanced_daemon_mgmt.py`, install/auto-install tests |
| CI | `.github/workflows/iroh-ci.yml` (Iroh-focused) |

Offline documentation validation must not require live daemons, network, or `IPFS_KIT_AUTO_INSTALL_BINARIES=1`.

---

## 13. Unresolved owner decisions (do not invent outcomes)

| ID | Topic | Blocks |
|---|---|---|
| **U-09** | Default content transport: Kubo, Iroh, or dual-write | Deployment guides, getting-started defaults |
| **U-10** | libp2p pin/track policy; whether MCP P2P is optional forever or eventually required | Packaging, MCP ops |
| **U-12** | Canonical `ipfs_py` implementation among three definitions | Client docs, MCP backend wiring |
| **U-16** | Daemon manager authority among enhanced / intelligent / cluster-enhanced / legacy | Runtime and operations guides |
| **U-02** | CLI composition (mount P2P workflow under `ipfs-kit` or not) | Closing aspirational CLI drift |
| **U-18** | MCP tool count / JS manifest parity (`iroh_diagnostics`) | SDK release checklist |
| **C-FSSPEC** | IPFS fsspec packaging vs Iroh-only entry points | Storage/integration docs |

---

## 14. Change triggers

Re-verify this guide when any of the following change:

- `pyproject.toml` scripts, `iroh` / `libp2p` extras, or fsspec entry points
- `TOOL_GROUPS` membership or MCP transport set (`stdio` / `http` / `p2p`)
- Iroh protocol version, release JSON installability, or normative `docs/iroh/*` contracts
- `kubo_runtime` install defaults or daemon manager used by `cli.py`
- libp2p dependency pin policy or `PROTOCOL_ID` for MCP P2P
- Routing gRPC removal/replacement or HTTP routing API
- Packaging of `p2p_workflow_cli` under `ipfs-kit`
- Acceptance of ADR covering U-09 / U-10

---

## 15. Reading order

1. This document — boundaries and coexistence.
2. [`docs/iroh/`](../iroh/) — normative Iroh contracts and runbooks (when implementing or operating Iroh).
3. [SOURCE_OF_TRUTH_MAP §5, §9](./SOURCE_OF_TRUTH_MAP.md) — evidence inventory and open decisions.
4. [PUBLIC_SURFACE_MATRIX](../audits/PUBLIC_SURFACE_MATRIX.md) — surface IDs S09, S15–S18, S21.
5. Planned [CLUSTER_COORDINATION.md](./CLUSTER_COORDINATION.md) — membership, roles, replication (not transport selection alone).
6. Planned [MCP_CONTROL_PLANE.md](./MCP_CONTROL_PLANE.md) — tool registry, receipts, multi-interface control plane detail.
7. Planned [STORAGE_BACKEND_SYSTEM.md](./STORAGE_BACKEND_SYSTEM.md) — backend plugins vs live adapters.

---

## 16. Validation helpers

```bash
# Guide presence (KDOC-016 gate)
test -s docs/architecture/NETWORK_TRANSPORTS.md && rg -q "Iroh" docs/architecture/NETWORK_TRANSPORTS.md

# Packaging scripts and extras
rg -n 'ipfs-kit-iroh|libp2p|fsspec.specs' pyproject.toml

# MCP tool registry and P2P transport
rg -n 'TOOL_GROUPS|iroh_diagnostics|serve_p2p|PROTOCOL_ID' \
  ipfs_kit_py/mcp_server/tools/__init__.py \
  ipfs_kit_py/mcp_server/p2p_transport.py \
  ipfs_kit_py/mcp_server/server.py

# Kubo install defaults (must remain opt-in for docs envs)
rg -n 'IPFS_KIT_AUTO_INSTALL_BINARIES|ensure_kubo_binary' ipfs_kit_py/kubo_runtime.py

# Iroh fail-closed install posture
rg -n 'installable|source-pinned|protocol' docs/iroh/compatibility.md ipfs_kit_py/resources/iroh-releases.json
```
