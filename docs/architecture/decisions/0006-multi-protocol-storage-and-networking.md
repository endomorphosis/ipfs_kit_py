# ADR-0006: Multi-protocol storage and networking coexistence

> **Document class:** Proposed  
> **Decision status:** Proposed  
> **Date:** 2026-08-04  
> **Last verified:** 2026-08-04  
> **Evidence baseline:** current tree as of 2026-08-04 (`c3641f4103c970c6e754c8d5e2a8d70c8318d38c`); architecture guide KDOC-016 (`NETWORK_TRANSPORTS.md`); storage guide KDOC-013 (`STORAGE_BACKEND_SYSTEM.md`)  
> **Authors:** KDOC-026 (agent-supervisor implementation)  
> **Confirmation owner:** network / storage maintainers (default content transport and libp2p pin policy); documentation maintainers may not accept this ADR alone  
> **Supersedes:** none  
> **Superseded by:** none  
> **Related guides:** [`../NETWORK_TRANSPORTS.md`](../NETWORK_TRANSPORTS.md), [`../STORAGE_BACKEND_SYSTEM.md`](../STORAGE_BACKEND_SYSTEM.md), [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §5, [`../SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md), [`../GLOSSARY.md`](../GLOSSARY.md), normative [`../../iroh/`](../../iroh/)  
> **Related conflicts / U-IDs:** U-09, U-10 (also adjacent: U-12 dual `ipfs_py`, U-16 daemon managers, U-02 CLI composition, C-FSSPEC, U-18 MCP tool/SDK parity)

Process contract:
[`README.md`](./README.md) · Claim standard:
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)

---

## 1. Context

ipfs-kit does **not** present a single universal content network or storage backend. Packaging, library APIs, MCP tools, fsspec entry points, and optional extras expose **parallel** stacks:

| Family | Role (summary) |
|---|---|
| **Kubo / IPFS** | CID-addressed blocks/DAGs, pins, swarm, bitswap; kit client + MCP majority tools |
| **Iroh** | BLAKE3 blobs, manifests, managed sidecar RPC, schema-validated backend + packaged fsspec |
| **libp2p (Python)** | Optional in-process peer (discovery, bitswap-style exchange) and MCP++ P2P *control* transport |
| **Multi-backend routing** | Application placement among named backends (IPFS, Iroh, S3, …)—not DHT-only |
| **Remote / object backends** | S3, Storacha, Filecoin, local FS, and other registry types as live adapters |
| **P2P workflow coordination** | Task assignment across peers (orchestration), not blob transfer |

Without a recorded decision, guides and agents risk:

1. Declaring a **single default transport** (Kubo *or* Iroh *or* dual-write) without maintainer confirmation (**U-09**).  
2. Treating **BLAKE3** and **CID** as interchangeable identifiers.  
3. Collapsing **storage backend**, **protocol stack**, **fsspec filesystem**, **daemon lifecycle**, and **routing** into one concept.  
4. Presenting **libp2p tracking `main`** as a stable pin (**U-10**) or as required for core install.  
5. Documenting **silent cross-network bridging** or dual-write as implemented production defaults.

This ADR records **observed coexistence** with confidence labels, states **capability / consistency / security / lifecycle trade-offs**, labels **inferred motivations**, lists **alternatives**, and keeps open owner decisions **Proposed** until confirmation.

**In scope:**

- Parallel content-plane families (Kubo/IPFS, Iroh, optional libp2p) and how they coexist with remote backends and routing  
- Address-family isolation (CID vs BLAKE3) and interoperability limits  
- Capability, consistency, security, and lifecycle trade-offs of multi-protocol design  
- Default transport options under **U-09** (without selecting a winner)  
- libp2p dependency posture under **U-10** (options only)  
- Evidence, consequences, alternatives, and confirmation criteria  

**Out of scope:**

- Backend plugin registry vs live adapter factories as a sole authority (**ADR-0002** / U-04)  
- Content metadata / WAL / journal durability (**ADR-0005** / U-06, U-07)  
- MCP production runtime tree (**ADR-0003** / U-11)  
- Cluster control-plane family (**ADR-0008** / U-08)  
- Config/state directory composition (**ADR-0007** / U-13)  
- Rewriting normative Iroh contracts under `docs/iroh/*`  
- Implementing dual-write bridges, consolidating daemon managers, or packaging CLI mounts (code tasks after acceptance)

**Non-goal of this draft:** Selecting Kubo, Iroh, or dual-write as *the* production default. Conflict policy and the ADR index require this record to **remain Proposed** for U-09/U-10 until confirmation.

---

## 2. Current behavior (evidence, not aspiration)

Present-tense claims describe the tree **as observed**. They do **not** assert a chosen deployment default.

### 2.1 Role separation (precondition)

| Role | What it is | What it is not |
|---|---|---|
| **Protocol stack** | Wire protocols and peer connectivity (libp2p, Iroh QUIC/relay, Kubo swarm) | A named backend YAML document |
| **Storage backend** | Named, validated config + live adapter (IPFS, Iroh, S3, …) | A daemon lifecycle manager alone |
| **FSSpec filesystem** | Path-oriented data plane (`iroh://`, in-tree IPFS fsspec modules) | The MCP tool registry |
| **RPC sidecar** | Local Iroh sidecar over Unix socket / local RPC | Remote multi-tenant control plane |
| **Routing** | Choosing which *backend id* holds content | Full multi-node membership consensus |
| **Workflow coordination** | Assigning CI-like tasks to peers | Content bitswap or blob transfer |

### 2.2 Surface inventory

| Surface / path | Observed role | Evidence (source, test, packaging) | Status label |
|---|---|---|---|
| `ipfs_kit_py/ipfs.py` (`ipfs_py`) | Primary kit IPFS client path | Source; MCP IPFS tools; parallel clients exist (U-12) | Active / candidate client |
| `kubo_runtime.py`, `install_ipfs.py` | Package-managed Kubo binary; install **off by default** | `IPFS_KIT_AUTO_INSTALL_BINARIES` opt-in | Active lifecycle helper |
| Daemon managers (`enhanced_*`, `intelligent_*`, cluster-enhanced, legacy) | Start/stop/status for external daemons | CLI service handlers import `EnhancedDaemonManager` | Parallel / unresolved authority (U-16) |
| `ipfs_kit_py/iroh/*` | Service, client, backend plugin, blob store, manifest, protocol, security, multinode, CLIs | Strong `tests/test_iroh_*.py` suite; `docs/iroh/*` | Active first-class optional stack |
| `iroh_install_cli.py`, scripts `ipfs-kit-iroh*` | Managed Iroh binary install/ops/diagnostics/manifest/interop | `pyproject.toml` scripts | Active packaged ops surface |
| `iroh_fsspec.IrohFileSystem` | Packaged fsspec for `iroh`, `iroh+blob` | `pyproject.toml` `[project.entry-points."fsspec.specs"]` | Active packaged FSSpec |
| `backends/iroh_backend.py`, `iroh/backend.py` | Live adapter re-export + schema-validated `IrohBackendPlugin` | Backend registry + named-backends docs | Active schema-validated type |
| `ipfs_kit_py/libp2p/`, `libp2p_peer.py` | Optional peer stack; `HAS_LIBP2P` fail-soft | Extra tracks `py-libp2p@main`; thinner tests than Iroh | Optional / experimental pin risk (U-10) |
| `mcp_server/p2p_transport.py` | MCP++ control-plane stream `/mcp+p2p/1.0.0` | Requires libp2p extra; not content replication | Optional MCP transport |
| MCP++ `TOOL_GROUPS` | **29** tools; **28** IPFS/CID-shaped + `iroh_diagnostics` | `mcp_server/tools/__init__.py` | Active control plane (IPFS-heavy) |
| `routing/` (`DataRouter`, `RoutingManager`) | Multi-backend placement selection | Library + optional HTTP; gRPC **deprecated** | Active library path |
| Remote backends (S3, Storacha, Filecoin, local, …) | Named documents + live adapters | `backend_registry` LEGACY_TYPES; `backends/*` | Active multi-backend catalog |
| `enhanced_fsspec.py` | Runtime registration of `ipfs`, `filecoin`, `storacha`, `synapse` | Import-time `fsspec.register_implementation` | Compatibility / not packaging entry points (C-FSSPEC) |
| `p2p_workflow_coordinator.py`, `cli/p2p_workflow_cli.py` | Merkle-clock task assignment | `tests/test_p2p_workflow.py`; **not** packaged `ipfs-kit p2p` | Library-first; CLI packaging gap (U-02) |

### 2.3 Content-plane comparison (observed)

| Concern | Kubo / IPFS | Iroh | libp2p peer (optional) | Remote object backends |
|---|---|---|---|---|
| Content ID | IPFS CID (CIDv0/v1, multihash) | BLAKE3 hex / blob + manifests | Usually CID-oriented handlers | Backend-native keys / URLs |
| Process model | External daemon common | Managed sidecar + local RPC | In-process with Python host | Cloud/API or local path |
| Auth model | API auth / swarm policy | Tickets, capabilities, ACL, secretrefs | Peer keys; app-level policy | Cloud credentials via secretrefs |
| Retention | Pins | protect/release + manifest live set | Application-defined | Bucket lifecycle / backend policy |
| Primary kit exposure | MCP tools + kit client | CLIs + fsspec + backend plugin | Optional Python + MCP P2P transport | Backend manager + adapters |
| Identity crosswalk | N/A native | **Never** label BLAKE3 as CID | Not a certified go-libp2p matrix | Not content-addressed unless layered |

### 2.4 Decision tree for content paths (current behavior)

```text
Need content-addressed or stored bytes?
├── Identity is IPFS CID
│   ├── Live Kubo (or compatible) API available?
│   │   ├── Yes → kit client / MCP ipfs_* / pin_* / bitswap_*
│   │   └── No  → optional libp2p peer miss path (if extra installed)
│   └── System PATH vs package-managed Kubo: managed bin prepended when present
│
├── Identity is Iroh BLAKE3 blob / namespace manifest
│   ├── Sidecar installable and protocol negotiated?
│   │   ├── Yes → Iroh backend / fsspec / ops CLIs
│   │   └── No  → fail closed (source-pinned release may be installable:false)
│   └── Never treat BLAKE3 as CID or vice versa
│
└── Choose among multiple configured backends (S3, IPFS, Iroh, …)
    └── routing.DataRouter / RoutingManager (library or HTTP; not gRPC)
```

### 2.5 Observed invariants (implementation-backed)

1. **Address-family isolation:** Iroh BLAKE3 identifiers must not be cast as IPFS CIDs (and reverse); normative Iroh compatibility docs enforce this.  
2. **Config vs live connection:** Backend type registry validation must remain side-effect-free (no daemon start at import/validate time).  
3. **Optional stacks degrade:** Missing `libp2p` or unpublishable Iroh artifacts fail closed or skip—do not fabricate health/success.  
4. **Iroh integrity:** Accepted blob bytes match declared digest and size before cache/export trust.  
5. **Routing gRPC is deprecated** for multi-backend selection (protobuf conflict with libp2p ecosystem).  
6. **Binary auto-install is opt-in** (`IPFS_KIT_AUTO_INSTALL_BINARIES` default off) for Kubo/Lotus/Iroh paths used by docs/CI.  
7. **Dual-write / automatic CID↔BLAKE3 bridge is not a production default** in-tree.

### 2.6 Narrative summary

The repository ships **parallel capabilities**: Kubo/IPFS remains the dominant MCP and kit-client content path; Iroh is a first-class optional blob/manifest stack with the strongest in-tree normative contracts and dedicated console scripts; libp2p is an optional extra for peer features and MCP P2P control carriage; routing selects among backends including remote object stores. Coexistence is **implemented**; a single greenfield **default** among Kubo / Iroh / dual-write remains an **open owner decision (U-09)**.

---

## 3. Decision

**Status:** Proposed  

### 3.1 Decision statement

Until maintainer confirmation promotes U-09 and U-10, this ADR **records and freezes the following design posture** as the documentation and integration baseline. Items marked **Accepted (observed invariant)** are strongly evidenced and may be cited as current behavior. Items marked **Proposed (owner decision)** must not be cited as production defaults without confirmation.

#### D1 — Multi-protocol coexistence is intentional product shape (**Accepted observed invariant**)

The system supports **parallel** content and control network families rather than collapsing to one universal backend or transport. Guides, examples, and agents must describe **parallel capabilities** and name the family in use—not “the network” as a single abstraction.

#### D2 — Address families remain isolated (**Accepted observed invariant**)

| Identity family | Use for | Do not |
|---|---|---|
| IPFS CID | Kubo/IPFS pins, bitswap, MCP IPFS tools | Present as Iroh blob hash |
| Iroh BLAKE3 / manifest | Iroh sidecar, `iroh://` / `iroh+blob://`, Iroh backend | Present as IPFS CID |
| Backend-native keys | S3/object/path backends | Imply content-addressed equivalence without an explicit bridge |

Any cross-network bridge (dual storage, conversion service) requires an **explicit policy and ADR/promotion**—not silent reencoding.

#### D3 — Separate roles: protocol vs backend vs fsspec vs lifecycle vs routing vs workflow (**Accepted observed invariant**)

Documentation and APIs must keep the §2.1 roles distinct. Conflating them produces false authority claims (e.g. treating fsspec packaging as transport default, or MCP P2P as content replication).

#### D4 — Default content transport for new deployments is **Proposed** (U-09)

**Current behavior (Accepted as description):** No maintainer-accepted single default among:

| Option | Summary |
|---|---|
| **Kubo-first** | Greenfield defaults to CID/Kubo path; Iroh optional |
| **Iroh-first** | Greenfield defaults to Iroh blob/manifest; Kubo optional for IPFS interop |
| **Dual-write / dual-read** | Write (and optionally read) both planes under an explicit policy |
| **Caller-selected only** | No product default; every deployment names backends/transports |

**Proposed owner decision (not accepted):** Which option (or multi-track matrix by workload) is the production recommendation for getting-started and deployment guides.

#### D5 — libp2p remains optional; pin/track policy is **Proposed** (U-10)

**Current behavior (Accepted as description):** `libp2p` extra is optional; `HAS_LIBP2P` / `HAVE_LIBP2P` degrade peer and MCP `--transport p2p` features; packaging tracks upstream `main`.

**Proposed owner decision:** Pin commit/tag vs continue tracking `main`; whether MCP P2P transport stays forever optional or becomes required for some profiles.

#### D6 — MCP tool surface remains IPFS-heavy; Iroh data plane is CLI/fsspec/backend-first (**Accepted observed exposure**)

MCP++ registers predominantly IPFS/CID tools plus `iroh_diagnostics`. Full Iroh ingest/read is **not** mirrored as a first-class MCP tool group comparable to `ipfs_add`/`ipfs_cat` on the measured baseline. Do not document parity that packaging does not provide.

#### D7 — Remote backends and routing coexist with P2P families (**Accepted observed architecture**)

Multi-backend routing and remote object stores are **first-class placement and durability options** alongside peer networks. They are not “legacy fallbacks only.” Routing selects backend ids; it does not replace Kubo DHT or Iroh sync.

#### D8 — Reject inventing a universal single-stack default in docs (**Accepted documentation policy while Proposed**)

Until U-09 is confirmed, architecture prose, ADRs, and agents **must not** invent “ipfs-kit always uses X” for content transport. Status-honest language: parallel capabilities; operator selects stack.

### 3.2 Options (required: Proposed status and material alternatives)

| Option | Summary | Fit / risk |
|---|---|---|
| **A — Recorded multi-protocol coexistence (this ADR)** | Keep parallel families; document trade-offs; leave U-09/U-10 Proposed | Matches tree; needs owner follow-up for defaults |
| **B — Kubo-only product default** | Deprecate or demote Iroh/libp2p to experimental | Simplifies mental model; discards strong Iroh contract investment |
| **C — Iroh-only product default** | Kubo becomes interop-only / optional | Stronger modern blob story; breaks CID/MCP-majority expectations |
| **D — Dual-write default** | Every object lands in both planes | Consistency and cost complexity; not implemented as default |
| **E — Require libp2p for all installs** | Peer features always available | Heavy dependency; upstream `main` risk (U-10) |
| **Status quo undocumented** | Guide prose only; no ADR | Agents invent defaults; re-litigation of U-09 |

**Selected option (if any):** **Option A** for documentation and integration guidance. Options B–E remain available owner choices; none is Accepted as production policy in this record.

---

## 4. Rationale (confidence-labeled)

### 4.1 Why multiple transports coexist

**Accepted:** The tree implements and packages multiple content/control stacks with distinct identity models, entry points, and test contracts (Kubo client/MCP tools; Iroh suite + normative `docs/iroh/`; optional libp2p; routing + remote backends). Evidence: packaging scripts/extras/fsspec entries; `TOOL_GROUPS`; `NETWORK_TRANSPORTS.md` measured surfaces; focused tests.

**Inferred:** Coexistence exists to serve **different trust, identity, and addressing models** (public IPFS swarm + CID ecosystem vs local-capability Iroh tickets/BLAKE3 vs optional in-process libp2p vs cloud object stores) rather than incomplete migration from one stack to another.

**Inferred:** Iroh was integrated as a **parallel blob/manifest backend**, not as a drop-in CID replacement—hence separate lifecycle, credentials, address formats, and fail-closed install posture.

**Unknown:** Whether long-term product strategy intends eventual consolidation to one content plane — unknown / maintainer confirmation needed (overlaps U-09).

### 4.2 Capability trade-offs (why not one stack)

**Accepted:** Different stacks expose different **capabilities**:

| Stack | Strengths (observed) | Gaps (observed) |
|---|---|---|
| Kubo/IPFS | CID ecosystem, pins, swarm, bitswap, IPNS, MFS; majority MCP tools | External daemon ops; public swarm trust model unless restricted |
| Iroh | Normative contracts, BLAKE3 integrity, tickets/capabilities, managed sidecar, packaged fsspec | Not CID-native; MCP data-plane tools thin; install may be fail-closed per platform |
| libp2p | In-process peer; MCP P2P control carriage; cache-miss hooks | Optional extra; thinner tests; upstream `main` skew |
| Routing + remote backends | Cost/latency/type placement; cloud durability options | Not a peer network; gRPC path deprecated |
| P2P workflow | Task orchestration across peers | Not content transport; CLI packaging incomplete |

**Inferred:** MCP tools remain IPFS-shaped because agent/tooling demand still centers on CID operations; Iroh ops stay specialized behind dedicated CLIs/fsspec.

**Inferred:** Routing gRPC was deprecated to resolve protobuf conflicts with the libp2p dependency graph—library/HTTP remains the supported control path for placement.

### 4.3 Consistency trade-offs

**Accepted:** There is **no** implemented default dual-write or automatic cross-network consistency between Kubo pinsets and Iroh blobs. Consistency is **per plane**.

**Accepted:** Address-family isolation prevents false equivalence of identifiers; integrity checks on Iroh reject mismatched digests.

**Inferred:** Leaving planes separate avoids a false global consistency story that the code does not enforce—at the cost of operator responsibility for which plane is authoritative for a workload.

**Proposed:** If dual-write is ever selected (U-09 Option D), owners must define consistency class (eventual dual success, primary+async replica, read-your-writes rules) and failure semantics—not claim ACID across planes.

**Unknown:** Target consistency SLA for multi-backend routing selections under concurrent writers — unknown / maintainer confirmation needed (may interact with ADR-0005 / ADR-0008).

### 4.4 Security trade-offs

**Accepted:** Each family has a distinct trust boundary:

| Boundary | Risk if blurred |
|---|---|
| Host → Kubo API | Unintended remote API exposure; swarm to untrusted peers |
| Host → Iroh local RPC | Leak of node keys, tickets, write caps, secretrefs |
| Public peers (swarm / Iroh / libp2p) | Untrusted content until verified; private key leakage in logs |
| MCP client → server (stdio/HTTP/P2P) | Secrets in tool args; receipts must stay fail-closed where applicable |
| Docs/logs/metrics | Tickets, keys, raw secretrefs must not appear |

**Accepted:** Iroh config uses opaque secret references; inline secrets are rejected in the normative security posture. Backend registry redaction applies to public config results.

**Inferred:** Parallel security models are retained because collapsing to one ACL (e.g. swarm-only or ticket-only) would either weaken Iroh capability security or break IPFS public-network use cases.

**Proposed:** Production profiles should document which ports, sockets, and peer policies are allowed per deployment class (loopback-only API, private swarm, Iroh ticket ACL, MCP auth extras)—without inventing a single shared policy here.

### 4.5 Lifecycle trade-offs

**Accepted:** Lifecycle ownership differs by stack:

| Component | Process ownership | Install posture |
|---|---|---|
| Kubo | Separate OS process; multiple daemon manager candidates (U-16) | Auto-install opt-in |
| Iroh sidecar | Separate process; `IrohService` ownership receipts; crash-loop protection | Managed install CLI; fail-closed when not installable |
| libp2p host | In-process with the Python runtime | Optional extra; no separate binary |
| MCP++ server | Own process; transport chosen at startup | Packaged `ipfs-kit-mcp` |
| Routing manager | In-process; optional metrics tasks | Library/HTTP |

**Accepted:** Do not run the same Iroh instance under both systemd foreground mode and a second managed-child supervisor (normative service-lifecycle).

**Inferred:** Separate lifecycles reduce blast radius (Iroh crash ≠ Kubo pin loss and vice versa) at the cost of multi-process operations complexity.

**Unknown:** Single daemon-manager authority among enhanced/intelligent/cluster-enhanced/legacy (U-16) — unknown / maintainer confirmation needed; orthogonal but adjacent to transport defaults.

### 4.6 Motivations summary (label discipline)

| Motivation claim | Label |
|---|---|
| Parallel stacks are implemented and packaged on purpose | **Accepted** (behavior) |
| Different identity/trust models drive coexistence | **Inferred** |
| Iroh is parallel, not CID drop-in | **Accepted** (contracts + code) |
| MCP remains IPFS-heavy due to agent demand | **Inferred** |
| Dual-write is production default | **Not claimed** (false if asserted) |
| libp2p tracks `main` for latest features despite risk | **Inferred** packaging motive; policy **Proposed** (U-10) |
| One greenfield default is already chosen | **Unknown** / open **U-09** |

---

## 5. Evidence

| Rank | Claim | Citation |
|---|---|---|
| 1 | Iroh service/backend/fsspec/security/multinode behavior and fail-closed patterns | `ipfs_kit_py/iroh/*`; `tests/test_iroh_*.py`; fixtures under `tests/fixtures/iroh/` |
| 1 | libp2p optional degradation and peer health | `ipfs_kit_py/libp2p/`; `tests/test_simple_libp2p.py`; `tests/unit/test_libp2p_health_api.py` |
| 1 | P2P workflow coordinator unit behavior | `tests/test_p2p_workflow.py` |
| 1 | MCP++ tool registry membership (IPFS-heavy + `iroh_diagnostics`) | `ipfs_kit_py/mcp_server/tools/__init__.py` (`TOOL_GROUPS`); MCP P2P `PROTOCOL_ID` in `p2p_transport.py` |
| 1 | Daemon manager unit coverage | `tests/unit/test_daemon_manager.py`, `test_daemon_startup.py`, `test_enhanced_daemon_mgmt.py` |
| 2 | Packaged console scripts for Iroh family and MCP | `pyproject.toml` `[project.scripts]`: `ipfs-kit-iroh*`, `ipfs-kit-mcp` |
| 2 | Packaged fsspec only `iroh` / `iroh+blob` | `pyproject.toml` `fsspec.specs` → `IrohFileSystem` |
| 2 | `libp2p` and `iroh` extras; libp2p tracks upstream main | `pyproject.toml` optional dependencies |
| 2 | Kubo/Iroh auto-install opt-in default | `kubo_runtime.py`, installers; env `IPFS_KIT_AUTO_INSTALL_BINARIES` |
| 3 | Iroh normative address isolation, security, lifecycle, interoperability | `docs/iroh/compatibility.md`, `security.md`, `service-lifecycle.md`, `filesystem-contract.md`, `threat-model.md` |
| 3 | Routing gRPC deprecation | `ipfs_kit_py/routing/GRPC_DEPRECATION_NOTICE.md` |
| 3 | Backend registry types include IPFS, Iroh plugin, remote backends | `backend_registry.py`; `iroh/backend.py`; `STORAGE_BACKEND_SYSTEM.md` |
| 4 | Unresolved U-09 / U-10 and ADR slot | `SOURCE_OF_TRUTH_MAP.md` §5, aggregate U-09/U-10; this ADR pre-registered in `decisions/README.md` §8 |
| 5 | Measured exposure and trade-off narrative | `NETWORK_TRANSPORTS.md` (KDOC-016) |
| 5 | System overview plane separation | `SYSTEM_OVERVIEW.md` |

**Evidence that is explicitly insufficient for Accepted status on U-09/U-10:**

- Inference that “MCP is IPFS-shaped therefore Kubo is the only default.”  
- Presence of strong Iroh docs alone as proof Iroh is the greenfield default.  
- Marketing keywords or high-level package description without packaging/test confirmation of a single transport.  
- Aspirational docs claiming packaged `ipfs-kit p2p …` when FastCLI does not mount it.

---

## 6. Consequences

### 6.1 Positive

- **Honest product shape:** Operators and agents stop inventing a single network when four+ planes exist.  
- **Safer identity handling:** CID vs BLAKE3 isolation prevents silent data-plane mistakes.  
- **Composable storage:** Routing and remote backends remain valid without forcing everything through P2P.  
- **Degraded modes are documentable:** Missing libp2p or unpublishable Iroh binaries have clear fail-closed stories.  
- **Reviewable defaults later:** U-09/U-10 confirmation has a fixed options table and acceptance criteria.

### 6.2 Negative / costs

- **Operator cognitive load:** Multiple installers, state directories, CLIs, and trust models.  
- **No single getting-started path** until U-09 is accepted—docs must present choice trees.  
- **Test depth asymmetry:** Iroh suite is deep; libp2p and some Kubo interop paths are thinner.  
- **Packaging drift risks:** fsspec packaging vs runtime multi-protocol registration (C-FSSPEC); MCP tool vs JS SDK parity (U-18).  
- **libp2p `main` pin risk:** Optional features may break on upstream changes (U-10).

### 6.3 Capability / consistency / security / lifecycle trade-off matrix

Acceptance for KDOC-026 requires explicit trade-offs across these four axes:

| Axis | Multi-protocol choice (current posture) | Trade-off (gain vs cost) | Confidence |
|---|---|---|---|
| **Capability** | Keep Kubo CID ops, Iroh blobs, optional libp2p, remote backends, routing | **Gain:** full feature coverage across ecosystems. **Cost:** no one API covers all; MCP does not mirror full Iroh data plane | **Accepted** (exposure) / **Inferred** (MCP shape motive) |
| **Consistency** | Per-plane authority; no default dual-write | **Gain:** no false global consistency. **Cost:** operators must know which plane is SoT per workload; cross-plane queries need explicit design | **Accepted** |
| **Security** | Separate trust boundaries and auth models per family | **Gain:** least-privilege fits each stack (tickets vs swarm vs cloud IAM). **Cost:** multiple secret stores and leak surfaces; more operator policy work | **Accepted** |
| **Lifecycle** | Separate processes for Kubo/Iroh; in-process libp2p; opt-in binary install | **Gain:** isolation and fail-soft installs for docs/CI. **Cost:** multi-manager ambiguity (U-16); multi-service ops; crash-loop and PATH rules per stack | **Accepted** (behavior) / **Unknown** (single manager authority) |

### 6.4 Migration and compatibility

- New features must declare **which identity family and stack** they target; do not silently span CID and BLAKE3.  
- Prefer library routing / HTTP over deprecated routing gRPC.  
- Cross-transport bridges require explicit conversion policy + tests + ADR promotion—not guide-only claims.  
- Architecture guides must cite this ADR with **status-honest** language (`Proposed` for U-09/U-10 defaults; `Accepted observed` for coexistence and isolation).  
- Normative Iroh docs under `docs/iroh/` remain authoritative for Iroh contracts; this ADR does not supersede them.

### 6.5 Security and trust

- Never log or document live tickets, node private keys, swarm keys, or resolved secretref values.  
- Treat peer-sourced content as untrusted until integrity verification (CID/multihash or BLAKE3) succeeds.  
- Loopback-bind control APIs by default in examples; expanding bind addresses is an operator security decision.  
- Credentials: none in this ADR; examples use placeholders only.

### 6.6 Testing and verification

Tests that encode or protect the decision surface:

| Concern | Focused tests / hooks (prefer default discovery) |
|---|---|
| Iroh stack | `tests/test_iroh_*.py` (backend, blob, CLI, config, fsspec, install, MCP API, multinode, security, service, packaging, …) |
| Iroh CI | `.github/workflows/iroh-ci.yml` |
| libp2p | `tests/test_simple_libp2p.py`, `tests/unit/test_enhanced_libp2p.py`, `tests/unit/test_libp2p_health_api.py` |
| P2P workflow | `tests/test_p2p_workflow.py` |
| Daemon / Kubo lifecycle | `tests/unit/test_daemon_manager.py`, `test_daemon_startup.py`, `test_enhanced_daemon_mgmt.py` |
| Offline docs policy | `IPFS_KIT_AUTO_INSTALL_BINARIES=0` (no forced binary download) |

Commands that re-check this ADR body:

```bash
test -s docs/architecture/decisions/0006-multi-protocol-storage-and-networking.md \
  && rg -q "Iroh" docs/architecture/decisions/0006-multi-protocol-storage-and-networking.md
```

Supporting surface checks (optional; not this task’s sole gate):

```bash
rg -n 'ipfs-kit-iroh|libp2p|fsspec.specs' pyproject.toml
rg -n 'TOOL_GROUPS|iroh_diagnostics|PROTOCOL_ID' \
  ipfs_kit_py/mcp_server/tools/__init__.py \
  ipfs_kit_py/mcp_server/p2p_transport.py
```

---

## 7. Alternatives considered

| Alternative | Why considered | Why rejected / deferred | Confidence |
|---|---|---|---|
| Single universal backend/transport for all content | Simplest mental model | Contradicts packaging, MCP tool mix, Iroh contracts, remote backends, and routing | **Accepted** (rejected as current product shape) |
| Kubo-only; remove or hide Iroh | Reduce dual identity complexity | Discards strongest normative transport suite and packaged Iroh scripts/fsspec | **Inferred** (deferred / not product direction today) |
| Iroh-only; demote Kubo to legacy | Modern blob/ticket model | Breaks CID ecosystem path and majority MCP tools; no accepted migration plan | **Inferred** (deferred) |
| Dual-write every object to Kubo and Iroh by default | One pipe for users | Not implemented; consistency/cost/lifecycle complexity; needs U-09 Option D design | **Accepted** (not implemented) / **Proposed** if owners choose later |
| Silent CID↔BLAKE3 casting | Convenience for agents | Violates integrity and compatibility contracts; data-loss risk | **Accepted** (rejected) |
| Require libp2p for core install | Always-on P2P | Heavy/unstable extra (`main`); fail-soft optional is current design | **Accepted** (optional today) / **Proposed** (U-10 may revisit) |
| Revive routing gRPC as primary | Familiar RPC for placement | Deprecated for protobuf conflicts with libp2p | **Accepted** (rejected for new work) |
| Document status quo only in guides, no ADR | Faster authoring | Agents invent U-09 defaults; trade-offs unowned | **Accepted** (rejected for this program) |
| Claim packaged `ipfs-kit p2p` workflow CLI as shipped | Matches some feature docs | FastCLI does not mount `p2p`; packaging gap (U-02) | **Accepted** (aspirational only until wired) |
| Do nothing / leave U-09 invisible | Avoid ADR work | Map and network guide already flag the gap | **Accepted** (rejected) |

At least one alternative (status quo undocumented / invent a single stack) is explicitly rejected above.

---

## 8. Unknowns and owner confirmation

| Field | Value |
|---|---|
| **Confirmation owner** | Network and storage maintainers (default content transport, libp2p pin policy); packaging maintainers for extra pins; documentation maintainers for guide cross-links only after owner decision |
| **Confirmation question** | (1) For **new deployments**, is the recommended content transport **Kubo-first**, **Iroh-first**, **dual-write**, or **caller-selected only** (U-09)? (2) Should the `libp2p` extra **track `main`**, **pin a commit/tag**, and remain **optional** for MCP P2P forever or become **required** for named profiles (U-10)? |
| **What “Accepted” requires** | Explicit maintainer statement on U-09 (and U-10 if packaging policy is in scope) **and** rank-1–4 evidence or published deployment policy; update §3 status, this section, and deployment guide language |
| **Blocking for** | Getting-started defaults; deployment guides that name “the” network; any claim that dual-write or Iroh-only/Kubo-only is production policy; packaging pin policy for libp2p |
| **Related U-IDs / conflicts** | **U-09**, **U-10**; adjacent **U-12** (`ipfs_py` clients), **U-16** (daemon managers), **U-02** (CLI `p2p` mount), **C-FSSPEC**, **U-18** (MCP/JS tool parity) |

**Open unknowns:**

1. Default content transport for greenfield deployments (U-09) — unknown / maintainer confirmation needed.  
2. libp2p pin/track and required-vs-optional policy (U-10) — unknown / maintainer confirmation needed.  
3. Canonical `ipfs_py` among parallel definitions (U-12) — unknown / maintainer confirmation needed.  
4. Daemon manager authority (U-16) — unknown / maintainer confirmation needed.  
5. Whether long-term strategy consolidates content planes — unknown / maintainer confirmation needed.  
6. Historical product reason MCP exposes only `iroh_diagnostics` rather than full Iroh data-plane tools — unknown / maintainer confirmation needed (**Inferred** demand narrative above is not history).

---

## 9. Supersession and relationships

| Relation | ADR / doc |
|---|---|
| Supersedes | none |
| Superseded by | none |
| Related ADRs | ADR-0002 (backend plugins/adapters); ADR-0003 (MCP runtime/tools); ADR-0005 (content durability planes); ADR-0007 (config/state/secrets); ADR-0008 (cluster control plane—not transport default) |
| Architecture guides | [`../NETWORK_TRANSPORTS.md`](../NETWORK_TRANSPORTS.md) (KDOC-016), [`../STORAGE_BACKEND_SYSTEM.md`](../STORAGE_BACKEND_SYSTEM.md) (KDOC-013), [`../SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md), [`../GLOSSARY.md`](../GLOSSARY.md) |
| Normative Iroh | [`../../iroh/`](../../iroh/) (compatibility, security, lifecycle, filesystem contract, threat model) |
| Source-of-truth map | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §5 (U-09, U-10, U-12, U-16) |

---

## 10. Follow-up actions

| Action | Owner | Notes |
|---|---|---|
| Confirm U-09 default content transport | Network / storage maintainers | May promote §3 D4 Proposed → Accepted with chosen option (B/C/D/caller-selected) |
| Confirm U-10 libp2p pin and optionality | Packaging + MCP maintainers | Pin commit/tag vs `main`; optional vs required profiles |
| Update `NETWORK_TRANSPORTS.md` unresolved section when confirmed | Docs (separate task) | Keep status-honest citations while Proposed |
| Index owner updates ADR registry row for 0006 | Framework / KDOC-020 owners | Body authors do not edit `decisions/README.md` |
| Resolve adjacent U-12 / U-16 if defaults depend on them | Engineering | Client and lifecycle authority affect “Kubo-first” ops story |
| Optionally wire P2P workflow under FastCLI (U-02) | CLI maintainers | Closes aspirational CLI drift; separate from transport default |
| If dual-write chosen later | Engineering + this ADR amend | Design consistency class, failure modes, tests, bridge service—no silent casting |

---

## 11. Review checklist (authors)

- [x] Filename is `0006-multi-protocol-storage-and-networking.md` (not left as 0000)
- [x] Banner **Decision status** matches §3 **Status** (`Proposed`)
- [x] **Current behavior** is evidence-backed and separate from the proposal
- [x] No present-tense “the system default transport is X” for Proposed-only U-09
- [x] Every material *why* uses **Accepted / Proposed / Inferred / Unknown**
- [x] No Inferred or Unknown claim is written as Accepted history
- [x] Capability / consistency / security / lifecycle trade-offs are explicit (§6.3)
- [x] Evidence table prefers ranks 1–4 for Accepted claims
- [x] Alternatives include status quo and explicit rejects
- [x] Confirmation owner and question filled (Proposed)
- [x] No secrets, live tokens, or host-specific credential paths
- [x] `docs/architecture/decisions/README.md` was **not** edited by this task
- [x] Related architecture guide already points at this ADR slot with unresolved honesty

---

## Appendix A — Design-choice confidence matrix

Quick scan of observed choices required by KDOC-026 acceptance (trade-offs and labeled motivations).

| # | Observed design choice | Confidence | Capability | Consistency | Security | Lifecycle | Alternative (summary) |
|---|---|---|---|---|---|---|---|
| 1 | Parallel Kubo + Iroh + optional libp2p + remote backends | **Accepted** | Multi-ecosystem features | Per-plane SoT | Separate trust models | Multi-process ops | Single stack (rejected) |
| 2 | CID ≠ BLAKE3 isolation | **Accepted** | Correct APIs per family | No false cross-id equality | Integrity per plane | N/A | Silent cast (rejected) |
| 3 | Iroh parallel blob/manifest backend | **Accepted** | Strong contracts + fsspec | Own retention model | Tickets/secretrefs | Sidecar receipts | CID drop-in (rejected) |
| 4 | MCP tools mostly IPFS-shaped | **Accepted** (exposure) / **Inferred** (motive) | Agent CID ops | N/A | MCP arg hygiene | MCP process separate | Full Iroh MCP parity (not shipped) |
| 5 | libp2p optional + track `main` | **Accepted** (optional) / **Proposed** (pin policy U-10) | Peer + MCP P2P | N/A | Peer key risk | In-process host | Required libp2p (deferred) |
| 6 | Routing selects backends; gRPC deprecated | **Accepted** | Placement by cost/type | Placement ≠ consensus | Config redaction | In-process/HTTP | gRPC routing (rejected) |
| 7 | No default dual-write | **Accepted** | Simpler ops today | No cross-plane SLA | Fewer dual leak paths | Fewer dual lifecycles | Dual-write default (U-09 open) |
| 8 | Auto-install binaries opt-in | **Accepted** | Offline docs/CI safe | N/A | Supply-chain control | Explicit install steps | Always auto-install (rejected for docs) |
| 9 | Packaged fsspec is Iroh-only | **Accepted** | Clear packaging contract | N/A | N/A | Lazy FS construction | Multi-protocol packaging (C-FSSPEC open) |
| 10 | Greenfield default transport | **Proposed** (U-09) | Getting-started clarity blocked | Depends on choice | Depends on choice | Depends on choice | Caller-selected only until confirmed |
| 11 | P2P workflow library-first | **Accepted** (lib) / gap (CLI) | Orchestration without content mix-up | Local workflow state | Local state dir ACL | Not a daemon transport | Packaged CLI (U-02) |
| 12 | Daemon manager multiplicity | **Accepted** (behavior) / **Unknown** (authority U-16) | Multiple ops styles | N/A | N/A | Ambiguous canonical manager | Single manager (deferred) |

---

## Appendix B — Glossary anchors (non-normative)

| Term | ADR usage |
|---|---|
| **Content transport** | How content-addressed or blob bytes move (Kubo swarm/API, Iroh net/RPC, libp2p protocols)—not routing placement alone |
| **Default content transport** | Owner-chosen greenfield recommendation among Kubo / Iroh / dual / caller-selected (U-09) |
| **Address family** | Identifier namespace: IPFS CID vs Iroh BLAKE3 vs backend-native keys |
| **Dual-write** | Policy that persists the same logical object into two planes; not implemented as default |
| **Routing** | Application selection of a backend id; not DHT provider discovery alone |
| **MCP P2P transport** | Control-plane JSON-RPC over libp2p stream; not content replication |
| **Sidecar** | Managed local Iroh process with ownership receipts and local RPC |
| **Fail-closed** | Refuse operation or install rather than pretend success (Iroh installable:false, missing libp2p for forced P2P MCP) |
