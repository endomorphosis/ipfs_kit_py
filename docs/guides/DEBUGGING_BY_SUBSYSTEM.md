# Debugging by subsystem

| Field | Value |
|---|---|
| Document class | **Canonical** (agent / operator diagnostic map) |
| Status | active |
| Last verified | 2026-08-04 |
| Owner / task | KDOC-052 / KDOC-G070 |
| Track | agent-docs |
| Authority class | Compact diagnostic routing map (not a full operations runbook or ADR) |
| Evidence | Architecture guides KDOC-010..019, ADRs under `docs/architecture/decisions/`, [`AGENT_SYSTEM_MAP.md`](../architecture/AGENT_SYSTEM_MAP.md), [`CONFIGURATION_STATE_AND_TRUST.md`](../architecture/CONFIGURATION_STATE_AND_TRUST.md), [`SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md) |
| Scope | Route runtime symptoms to the right subsystem; run **safe/read-only** checks first; locate state and logs without leaking secrets; classify **Retryable** / **Degraded** / **Blocked**; link recovery authority |
| Non-goals | Duplicate full WAL/journal/Iroh recovery runbooks; invent maintainer decisions for open `U-*` / `C-*`; start daemons or mutate state as the first diagnostic step; edit protected program-control files |

This guide answers: *given a symptom, which subsystem owns diagnosis, which read-only checks are safe first, where are state and logs, is the condition retryable/degraded/blocked, and which document owns recovery?*

**Sibling agent maps**

| Map | Use for |
|---|---|
| [`AGENT_SYSTEM_MAP.md`](../architecture/AGENT_SYSTEM_MAP.md) | Task → subsystem routing before *changing* code |
| [`DOCUMENTATION_IMPACT_MAP.md`](../development/DOCUMENTATION_IMPACT_MAP.md) | Docs blast radius after a code change |
| **This file** | Runtime diagnosis by subsystem |
| [`CONFIGURATION_STATE_AND_TRUST.md`](../architecture/CONFIGURATION_STATE_AND_TRUST.md) | State roots, secrets, redaction, safe diagnostic runbook |
| [`SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md) | Candidate code authority, focused tests, open `U-*` |

**Conflict policy:** Own compact diagnostic routing only. **Link** recovery procedures in architecture and Iroh ops docs; do not fork them here.

---

## 1. Diagnostic principles (always)

### 1.1 Safe / read-only first

Before any start, stop, reinstall, WAL drain, journal recover, or secret rotation:

1. **Freeze auto-install.** Keep `IPFS_KIT_AUTO_INSTALL_BINARIES` unset or falsy so diagnosis does not download binaries.
2. **Identify roots only.** Note which of kit state (`~/.ipfs_kit` or `--data-dir`), Kubo repo (`IPFS_PATH` / `~/.ipfs`), Iroh instance root, and binary dir are in use—**list names and sizes**, do not dump contents.
3. **Map expected processes.** CLI, MCP++, Kubo, Iroh sidecar, optional cluster service—check liveness and readiness separately.
4. **Prefer redacted APIs.** Backend `list`/`show`/`health` with default redaction; credential **name** lists; tool status codes—not raw YAML, env dumps, or `get_credential` output.
5. **Scrub logs before attach.** Assume logs may contain tokens if someone misconfigured logging; scrub sensitive keys.
6. **Escalate with redacted bundles only.** Never paste `identity`, `cluster_secret`, tickets, write capabilities, master keys, or decrypted secrets into tickets.

See the full offline sequence in [CONFIGURATION_STATE_AND_TRUST §11](../architecture/CONFIGURATION_STATE_AND_TRUST.md#11-safe-diagnostic-runbook).

### 1.2 Condition classes

Use these three labels on every diagnosis. They drive whether an operator may retry, continue in a limited mode, or must stop and escalate.

| Class | Meaning | Operator action | Examples |
|---|---|---|---|
| **Retryable** | Transient failure; same operation may succeed without config change | Back off and retry; drain queues when health returns; do not thrash restart loops | Backend briefly down → WAL `pending`/`retrying`; network blip; race on PID after clean stop |
| **Degraded** | Product partially works; optional surface, extra, binary, or peer path is unavailable | Continue with reduced capability; document which features are off; install extras/binaries when needed | Missing `libp2p` extra; Iroh sidecar not ready while Kubo works; legacy backend `health: not-probed`; PyArrow absent → limited WAL; MCP stub kit offline |
| **Blocked** | Fail-closed or integrity stop; continuing would invent success or corrupt trust | Stop the unsafe path; fix root cause or restore from trusted backup; do not force success | Receipt integrity fail; unknown backend type; missing encryption master key; strict `sync_conflict`; Iroh digest mismatch; crash-loop guard refusing start |

A single incident can mix classes (for example, **Degraded** MCP without Iroh while **Retryable** WAL drains for Kubo). Label each plane separately.

### 1.3 Five-minute diagnostic workflow

```text
  Symptom
     │
     ▼
  §2 condition classes ──► Retryable / Degraded / Blocked (per plane)
     │
     ▼
  §3 symptom → subsystem ──► open that section only
     │
     ▼
  §1.1 safe/read-only checks ──► roots, PIDs, redacted health, log tails
     │
     ▼
  §4 state/log map ──► confirm paths; never dump secrets
     │
     ▼
  §5 subsystem playbook ──► focused probes; stop if Blocked
     │
     ▼
  §6 recovery authority ──► link to guide/ADR; mutate only under that authority
```

---

## 2. Symptom → subsystem routing

Map the **operator-visible symptom** to one primary diagnostic section. Open that architecture guide for depth; use this guide for the first safe checks.

| Symptom (examples) | Primary section | Architecture authority |
|---|---|---|
| `ImportError`, missing extra, lazy attribute missing, version string confusion | [§5.1 Imports / dependencies](#51-imports-and-optional-dependencies) | [`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md), [`RUNTIME_AND_ENTRYPOINTS.md`](../architecture/RUNTIME_AND_ENTRYPOINTS.md) |
| Daemon will not start/stop; wrong process; PID stale; auto-install surprises | [§5.2 Daemon lifecycle](#52-daemon-lifecycle) | [`RUNTIME_AND_ENTRYPOINTS.md`](../architecture/RUNTIME_AND_ENTRYPOINTS.md), CONFIGURATION §9 |
| Backend create/update rejected; unknown type; health unhealthy / not-probed | [§5.3 Backend config / health](#53-backend-config-and-health) | [`STORAGE_BACKEND_SYSTEM.md`](../architecture/STORAGE_BACKEND_SYSTEM.md) |
| Content write lost; pin stuck; VFS path wrong; WAL backlog; journal incomplete | [§5.4 VFS / WAL / journal](#54-vfs-wal-and-journal) | [`CONTENT_METADATA_VFS.md`](../architecture/CONTENT_METADATA_VFS.md) |
| Slow reads; wrong CID/path resolution; incomplete search; tier stats odd | [§5.5 Cache / index](#55-cache-and-index) | CONTENT_METADATA_VFS; cache modules |
| Multi-node role/leader stuck; pinset/cluster binary fail; coordination store | [§5.6 Cluster](#56-cluster-coordination) | [`CLUSTER_COORDINATION.md`](../architecture/CLUSTER_COORDINATION.md) |
| Swarm/peer empty; P2P MCP fail; routing picks wrong backend | [§5.7 Network transports](#57-network-transports) | [`NETWORK_TRANSPORTS.md`](../architecture/NETWORK_TRANSPORTS.md) |
| MCP tool error; transport bind; circuit open; receipt unavailable | [§5.8 MCP / transport / receipts](#58-mcp-transport-and-receipts) | [`MCP_CONTROL_PLANE.md`](../architecture/MCP_CONTROL_PLANE.md) |
| Iroh install/sidecar/manifest/fsspec issues; BLAKE3 vs CID confusion | [§5.9 Iroh](#59-iroh) | [`NETWORK_TRANSPORTS.md`](../architecture/NETWORK_TRANSPORTS.md), `docs/iroh/*` |
| Pytest red; discovery misses integration tests; offline CI surprises | [§5.10 Test / build](#510-test-and-build-diagnostics) | `pytest.ini`, SOURCE_OF_TRUTH tests |
| Config/secret/trust ambiguity; which root to wipe | [§4 State and logs](#4-state-and-log-locations-secret-safe) first | CONFIGURATION_STATE_AND_TRUST |

---

## 3. Global safe probe checklist

Run these **read-only** probes in order when the subsystem is unclear. Prefer offline hosts.

| Step | Safe probe (read-only) | Do **not** |
|---|---|---|
| 1 | `echo` / inspect env for `IPFS_KIT_*`, `IPFS_PATH`, `MCPPLUSPLUS_COORDINATION_DIR` **names only**—not values that may embed secrets | Print full env to shared chat |
| 2 | Confirm kit root exists: `test -d "${IPFS_KIT_DATA_DIR:-$HOME/.ipfs_kit}"` and list **top-level names** | `cat` credentials, secrets, raw backend YAML |
| 3 | Confirm Kubo path separate: `test -d "${IPFS_PATH:-$HOME/.ipfs}"` | Treat `~/.ipfs` as kit cache or delete it as cleanup |
| 4 | Process map: `pgrep -af 'ipfs-kit|ipfs daemon|iroh'` (or platform equivalent) | `kill -9` before readiness diagnosis |
| 5 | Packaging identity: `python -c "import importlib.metadata as m; print(m.version('ipfs_kit_py'))"` when installed | Cite only `__init__.__version__` as release truth (**C-VER**) |
| 6 | Import smoke (no daemon start): `python -c "import ipfs_kit_py; print('ok')"` | Force heavy feature imports that trigger network install |
| 7 | Redacted backend list if CLI available: backend list/show paths that use redaction | Attach unredacted `~/.ipfs_kit/backends/*.yaml` |
| 8 | MCP tool list / health without credentials in argv | Pass tickets or API keys on the command line |
| 9 | Log **tail** with secret scrubbing (MCP `mcp_<port>.log`, Iroh `logs/`) | Attach full multi-MB logs from secret-bearing hosts |

If a probe requires network reachability or daemon start, label it **out-of-band** and run only after offline checks pass.

---

## 4. State and log locations (secret-safe)

**Critical separation:** kit state root `~/.ipfs_kit` (or `--data-dir`) is **not** the Kubo repo `~/.ipfs` (`IPFS_PATH`). Wipe/migration tools must treat them as independent failure domains.

### 4.1 Location map

| Family | Default location | Safe to report | Never put in tickets |
|---|---|---|---|
| Kit state root | `~/.ipfs_kit` or CLI `--data-dir` | Path, exists?, top-level names, disk free | Entire tree dump |
| Thin / HLA config | `~/.ipfs_kit/config.yaml` (also cwd, `/etc/ipfs_kit/`) | Non-secret key names | Full file if secrets present |
| Named backends | `~/.ipfs_kit/backends/{name}.yaml` | Redacted show/list; type; enabled | Inline tokens, tickets, passwords |
| StateService JSON | `~/.ipfs_kit` (`buckets.json`, `pins.json`, `backend_configs/`) | System status summaries | Credential-bearing configs |
| Credentials file | `~/.ipfs_kit/credentials.json` (or OS keyring) | Service/name **presence** only | `get_credential` values |
| Enhanced secrets | `~/.ipfs_kit/secrets/` (`secrets.enc.json`, `metadata.json`, `audit.log`) | Counts, types, audit event kinds | Decrypted secret bodies |
| Secure keyring | `data_dir/.keyring/` (`master.key`, `salt`) | Presence / encryption status | Key bytes |
| MCP dashboard PID/log | `~/.ipfs_kit/mcp_<port>.pid`, `mcp_<port>.log` | PID alive?, port, scrubbed log tail | Full logs with tokens |
| MCP++ coordination | `~/.local/share/ipfs_kit_py/mcppp_coordination` or `MCPPLUSPLUS_COORDINATION_DIR` | Receipt ids, status, hashes | Untrusted full payloads with secrets |
| Kubo repo | `~/.ipfs` (`IPFS_PATH`) | Peer id, repo stat, API reachability | `identity`, `cluster_secret` |
| Managed binaries | `IPFS_KIT_BIN_DIR` or package bin | Path, version, Iroh install receipt digest | Arbitrary binary from untrusted PATH |
| Iroh instance | Configured instance root: `data/`, `staging/`, `run/`, `logs/`, `receipts/` | Liveness/readiness, redacted crash receipts | Tickets, write caps, node private identity |
| Storage WAL | `~/.ipfs_kit/wal/partitions/`, `…/archives/` | Pending/failed counts, status fields | Op params if they ever embedded secrets |
| Base / Durable WAL | Configurable `base_path` (often under kit root); segments + checkpoints | Sequence, checkpoint stats | Full segment hex dumps in public tickets |
| CAR WAL | `~/.ipfs_kit/wal/car/`, `…/processed/` | Unprocessed file names/counts | Content that is itself secret |
| Filesystem journal | Often `~/.ipfs_kit/journal` + `checkpoints/` | Journal ids, sizes, last checkpoint time | Entry payloads tied to secret content paths |
| Content catalog | `~/.ipfs_kit/content.json` | Existence / entry counts | Assume public; still avoid bulk dump of sensitive paths |
| Cluster secrets | Under Kubo/cluster config paths | Role, peer ids, health | Raw cluster secret, mTLS private keys |

Full per-family permissions and failure behavior: [CONFIGURATION_STATE_AND_TRUST §5](../architecture/CONFIGURATION_STATE_AND_TRUST.md#5-state-family-catalog).

### 4.2 Logging hygiene

| Source | What to keep | Redaction note |
|---|---|---|
| Hierarchical tool manager | `request_id`, category, tool name, elapsed ms | No credential arguments |
| Backend manager health | Structured redacted dicts (`_SENSITIVE_RE`) | Secret refs → `secretref:<provider>:<redacted>` |
| Iroh observability | Status/readiness, digests | Normative ban on secrets in argv/URL/env diagnostics (`docs/iroh/security.md`) |
| Enhanced secret audit.log | Event kinds, rotation ages | Restrict to operator/security roles |
| Support bundles | Paths, versions, redacted health | Never “tar entire `.ipfs_kit`” |

---

## 5. Subsystem playbooks

Each playbook follows: **symptoms → safe checks → condition class → recovery authority**.

---

### 5.1 Imports and optional dependencies

**Authority:** [`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md), [`RUNTIME_AND_ENTRYPOINTS.md`](../architecture/RUNTIME_AND_ENTRYPOINTS.md) §3.1, ADR-0001 (imports/optional deps).

| | |
|---|---|
| **Typical symptoms** | `ImportError` / `ModuleNotFoundError`; feature silently no-ops; HLA `available = False`; dual `*_anyio` import confusion; “works in MCP but not library” |
| **State / logs** | No durable state required for import diagnosis; packaging extras in `pyproject.toml`; feature flags via `jit_imports` / `deps_resolver` / `core` JIT |
| **Safe checks first** | (1) `import ipfs_kit_py` only. (2) `pip show` / try import optional module. (3) Confirm packaging extra vs optional binary (Kubo/Iroh are not pip extras alone). (4) Do not set auto-install to “fix” imports. |
| **Retryable** | Transient filesystem or concurrent install lock during optional package install (rare); retry after lock clears |
| **Degraded** | Missing extra → `HAS_*` false, `optional_feature` fallback, limited WAL without PyArrow, no libp2p peer; HLA stub methods return structured failure dicts |
| **Blocked** | Product path that is fail-closed for missing integrity modules (for example MCP receipt integrity paths); do not invent stub success there |
| **Recovery authority** | Install the documented packaging extra; for binaries follow RUNTIME install policy (opt-in). Do not promote inactive `*.fixed` modules. Open `U-*` on global stub-vs-fail-closed policy remains open—document per-subsystem only. |

---

### 5.2 Daemon lifecycle

**Authority:** [`RUNTIME_AND_ENTRYPOINTS.md`](../architecture/RUNTIME_AND_ENTRYPOINTS.md), CONFIGURATION §9, NETWORK_TRANSPORTS §7 (U-16 multi-manager note).

| | |
|---|---|
| **Typical symptoms** | `ipfs-kit mcp start` vs `ipfs-kit-mcp` confusion; stale PID; daemon API down; auto-start surprises; multiple managers disagree |
| **State / logs** | MCP dashboard: `~/.ipfs_kit/mcp_<port>.pid` / `.log`; Kubo: `IPFS_PATH`; kit binary dir: `IPFS_KIT_BIN_DIR`; Iroh: instance `run/` + `receipts/` |
| **Safe checks first** | (1) Which **entry** was intended: packaged `ipfs-kit-mcp` (MCP++) vs CLI dashboard `mcp start` vs Kubo `ipfs daemon` vs Iroh sidecar. (2) PID file vs live process. (3) API/RPC readiness separate from PID liveness. (4) Confirm auto-install env is off during diagnosis. |
| **Retryable** | Stale PID after crash (confirm dead → remove PID); brief API bind race after restart |
| **Degraded** | Kit constructed with `auto_start_daemons=False` / MCP stub kit—control plane up without live IPFS; local-only Kubo without swarm |
| **Blocked** | Iroh crash-loop guard refusing start until cleared while stopped; missing binary with auto-install off (must install explicitly); dual supervisor fighting one Iroh instance |
| **Recovery authority** | Per-entry stop/start tables in RUNTIME; Iroh `docs/iroh/service-lifecycle.md` and `install-lifecycle.md`. Do not assume a single daemon manager class is canonical (**U-16**). |

**Common trap:** `ipfs-kit daemon` / dashboard MCP paths are **not** the packaged MCP++ server (`ipfs-kit-mcp`). See AGENT_SYSTEM_MAP trap **U-16** / CLI MCP notes.

---

### 5.3 Backend config and health

**Authority:** [`STORAGE_BACKEND_SYSTEM.md`](../architecture/STORAGE_BACKEND_SYSTEM.md) §9–10, CONFIGURATION §5.3, ADR-0002 (backend plugin registry).

| | |
|---|---|
| **Typical symptoms** | Create/update backend fails; unknown type; Iroh `disabled` / `unavailable`; secrets rejected inline; dual config trees confuse operators |
| **State / logs** | `~/.ipfs_kit/backends/*.yaml`; optional StateService `backend_configs/` (**U-13** dual layout); health returns are structured dicts |
| **Safe checks first** | (1) `list`/`show` with **default redaction**. (2) Schema validation without starting daemons. (3) Distinguish `healthy: None` / `status: not-probed` (no live probe) from `healthy: False`. (4) Confirm credentials via name presence, not value dump. |
| **Retryable** | Transient endpoint unavailability when a live probe is injected; re-probe after network recovery |
| **Degraded** | Legacy types without probes (`not-probed`); disabled backend (`ready: False`) while others work; broken third-party entry points skipped so built-ins remain |
| **Blocked** | Unknown backend type / failed validation (fail closed; no partial YAML left on create; failed update keeps previous bytes); inline secrets rejected by policy |
| **Recovery authority** | STORAGE_BACKEND_SYSTEM recovery of valid YAML / `.bak`; re-add credentials via CredentialManager; never “fix” health by editing secrets into docs. Dual trees remain open (**U-13**). |

---

### 5.4 VFS, WAL, and journal

**Authority:** [`CONTENT_METADATA_VFS.md`](../architecture/CONTENT_METADATA_VFS.md) §8, ADR-0005 (content/metadata/durability).

| | |
|---|---|
| **Typical symptoms** | Write “succeeded” but path missing; pin/add stuck; WAL pending depth growing; journal recovery skips entries; sync_conflict; CAR files left unprocessed |
| **State / logs** | WAL partitions `~/.ipfs_kit/wal/…`; DurableWAL segments/checkpoints; CAR `wal/car/`; journal + `checkpoints/`; VFS sync state files (caller paths) |
| **Safe checks first** | (1) Identify which durability stack is in use (base WAL / StorageWriteAheadLog / DurableWAL / CAR / journal)—they are **not** one pipeline (**U-06**). (2) Read status fields and counts only. (3) List unprocessed CAR names. (4) Inspect journal recovery counters if a recover already ran—do not re-run recover until you know the path. |
| **Retryable** | Backend down → ops `pending`/`retrying`; `recover_stalled_operations` after process crash mid-`processing`; re-drain when `BackendHealthMonitor` allows |
| **Degraded** | Optional deps missing → limited/JSON WAL modes; cache miss (normal); metadata index incomplete but rebuildable |
| **Blocked** | Strict sync conflict / integrity mismatch codes; missing sync state without prior `sync_to`; checkpoint corruption requiring trusted older checkpoint or empty rebuild policy |
| **Recovery authority** | CONTENT_METADATA_VFS §8.2 procedures (journal, DurableWAL, storage/base WAL, CAR, metadata replication, VFS sync). Sequence multi-plane recovery carefully—there is no single distributed transaction manager. |

**WAL status transitions (storage / base WAL):** `pending` → `processing` → `completed` | `failed` | `retrying`. Treat deep `failed` after retry budget as **Blocked** for that op until manual requeue policy is defined by the caller.

---

### 5.5 Cache and index

**Authority:** CONTENT_METADATA_VFS (cache tiers, metadata indexes); reference tiered cache docs under `docs/reference/` when present.

| | |
|---|---|
| **Typical symptoms** | Unexpected cache miss; stale metadata; incomplete catalog query; high latency after restart |
| **State / logs** | Tiered cache dirs under kit/cache config; content catalog `~/.ipfs_kit/content.json`; Arrow/metadata index paths when enabled |
| **Safe checks first** | (1) `get_stats` / size metrics if available. (2) Confirm whether the index is rebuildable vs source of truth (pins/IPFS blockstore win over local JSON catalogs). (3) Cold start after wipe is expected miss—not corruption. |
| **Retryable** | Transient backend fetch after eviction; retry read |
| **Degraded** | Index missing entries → incomplete queries; optional analytics/index extras absent |
| **Blocked** | Treating local JSON catalog as authority over pinset/blockstore for durability decisions |
| **Recovery authority** | Rebuild rebuildable indexes from pins/content; CONTENT_METADATA_VFS for metadata plane; do not delete Kubo repo to “clear kit cache.” |

---

### 5.6 Cluster coordination

**Authority:** [`CLUSTER_COORDINATION.md`](../architecture/CLUSTER_COORDINATION.md) §7, ADR-0008 (Proposed—cluster control-plane authority **U-08**).

| | |
|---|---|
| **Typical symptoms** | Leader election thrash; role mismatch; Kubo Cluster binary fail; MCP coordination store corrupt; package `ClusterManager` construct errors |
| **State / logs** | Family A in-process state / Arrow paths; Family B external cluster service state; Family C `DurableCoordinationStore` blocks + SQLite under MCP++ coordination dir |
| **Safe checks first** | (1) **Name the family** (A bespoke kit / B Kubo Cluster wrappers / C MCP++ store)—do not merge APIs. (2) Peer ids, role, health only—no cluster secret. (3) For Family C: blocks present vs empty index. (4) Expect constructor mismatches in package ClusterManager as known rank-1 gaps—not “user error” alone. |
| **Retryable** | Brief leader re-election after timeout; lease expiry then reclaim under Family C fencing rules |
| **Degraded** | Multi-region endpoint `degraded`/`unavailable` routing helper; Plasma shared memory disabled; package heartbeat send stubbed (local view only) |
| **Blocked** | Family C receipt/CID integrity fail (fail-closed); unrecoverable secret loss for cluster join; treating Family A process memory as durable multi-host consensus |
| **Recovery authority** | CLUSTER_COORDINATION §7.3 per-family recovery order. No repo-wide orchestrator for A+B+C. Do not invent a single production default while **U-08** is open. |

---

### 5.7 Network transports

**Authority:** [`NETWORK_TRANSPORTS.md`](../architecture/NETWORK_TRANSPORTS.md) §9, ADR-0006 (Proposed—multi-protocol storage/networking **U-09**).

| | |
|---|---|
| **Typical symptoms** | Empty peer set; bitswap/get fail; MCP `--transport p2p` fails; routing picks expensive backend; identity family mix-up (CID vs BLAKE3) |
| **State / logs** | Kubo swarm via daemon; libp2p in-process; Iroh RPC socket; routing insights APIs |
| **Safe checks first** | (1) Which transport plane failed (Kubo / Iroh / libp2p / MCP P2P). (2) Extra installed vs binary present. (3) Local pin/API vs remote swarm. (4) Never log tickets or peer private keys. |
| **Retryable** | Transient peer disconnect; temporary relay failure |
| **Degraded** | `libp2p` absent → no in-process peer / no MCP P2P; Kubo up without swarm → local-only; routing insights warn without forcing dual-write |
| **Blocked** | Casting Iroh BLAKE3 as IPFS CID (or reverse); Iroh install fail-closed when artifact unpublishable; fabricating peer success without discovery |
| **Recovery authority** | NETWORK_TRANSPORTS degradation matrix §9.1; Iroh normative `docs/iroh/compatibility.md`, `security.md`. Default content transport remains open (**U-09**). |

---

### 5.8 MCP, transport, and receipts

**Authority:** [`MCP_CONTROL_PLANE.md`](../architecture/MCP_CONTROL_PLANE.md) §4.4 / §8, ADR-0003 (Proposed—MCP runtime authority).

| | |
|---|---|
| **Typical symptoms** | Tool `status: error`; circuit open; stdio/HTTP/P2P bind issues; receipt `unavailable`; stub CIDs in offline tests mistaken for production; tool count drift vs JS SDK |
| **State / logs** | Process logs on hierarchical_tool_manager; coordination store dir; optional mcplusplus profile state; do not confuse with dashboard MCP PID under kit root |
| **Safe checks first** | (1) Confirm **packaged** entry `ipfs-kit-mcp` / `ipfs-kit-mcp-tools` and tree `ipfs_kit_py/mcp_server/`—not `ipfs_kit_py/mcp/`, root `mcp/`, or `servers/`. (2) Transport mode (stdio / HTTP / P2P). (3) Tool registry loaded (`TOOL_GROUPS` + receipt descriptor). (4) Read receipt status codes only—never invent success for missing CID. |
| **Retryable** | Transient tool backend error when data plane recovers; request-scoped timeout then client retry with same `request_id` correlation |
| **Degraded** | `_StubKit` when live IPFS/import fails (deterministic offline stubs); missing libp2p → P2P capability false; mcplusplus accelerate extras missing while base tools run |
| **Blocked** | Receipt integrity / missing receipt (fail-closed); category circuit open (no tool execution); corrupt coordination index until rebuild from blocks |
| **Recovery authority** | MCP_CONTROL_PLANE §8; coordination `recover(rebuild=…)` when blocks authoritative; keep fail-closed receipt semantics. Measure tools from live registry—not stale README counts (**C-MCP-TOOLS** / **U-18**). |

---

### 5.9 Iroh

**Authority:** NETWORK_TRANSPORTS; normative suite under [`docs/iroh/`](../iroh/) (`service-lifecycle.md`, `observability.md`, `recovery.md`, `security.md`, `install-lifecycle.md`).

| | |
|---|---|
| **Typical symptoms** | Install inspect fails digest; sidecar not ready; fsspec `iroh://` errors; MCP only exposes `iroh_diagnostics`; crash loop |
| **State / logs** | Instance `data/`, `staging/`, `run/`, `logs/`, `receipts/` (including redacted crash receipts); install receipt beside binary |
| **Safe checks first** | (1) `ipfs-kit-iroh-diagnostics` / service `status` readiness vs running. (2) Install receipt digest check. (3) Backend plugin health (local socket existence by default—no surprise daemon start). (4) Scrub tickets and write capabilities from any dump. |
| **Retryable** | Brief RPC readiness lag after clean start |
| **Degraded** | Iroh optional while Kubo/other backends serve content; diagnostics-only MCP exposure without full blob tool parity |
| **Blocked** | Crash-loop guard; digest/size integrity failure; secrets in argv/env diagnostics; dual supervisors on one instance |
| **Recovery authority** | `docs/iroh/recovery.md`, `service-lifecycle.md`, `install-lifecycle.md`. Prefer Iroh CLIs for data-plane ops; do not treat BLAKE3 as CID. |

---

### 5.10 Test and build diagnostics

**Authority:** `pytest.ini`, SOURCE_OF_TRUTH focused tests per subsystem, ASYNC_AND_OPTIONAL_DEPENDENCIES §11.

| | |
|---|---|
| **Typical symptoms** | “Integration tests disappeared”; offline CI green while live daemon tests never ran; import side effects in collection; trio/asyncio mix failures |
| **State / logs** | Local pytest cache; env `IPFS_KIT_FAST_INIT` under CLI/pytest MCP paths; no production secrets in fixtures |
| **Safe checks first** | (1) Default discovery: `testpaths = tests` with `norecursedirs = tests/integration tests/archived_stale_tests`—integration is **excluded** by default. (2) Prefer unit paths listed in architecture guides. (3) Confirm extras/binaries only when a marked test requires them. (4) Avoid collection that starts daemons or downloads binaries. |
| **Retryable** | Flaky network-marked tests when network returns; file lock contention on parallel runs |
| **Degraded** | Suite runs without optional extras; MCP tests use fast-init/stub paths—green does not prove live Kubo/Iroh |
| **Blocked** | Treating presence-only or excluded integration trees as release proof; inventing “pytest green ⇒ production health” for daemon/receipt paths |
| **Recovery authority** | Re-run focused tests from SOURCE_OF_TRUTH / guide § tests tables; opt into integration explicitly when authorized. Documentation validation gates are a separate task (KDOC-053)—do not claim a Sphinx/MkDocs site build as the unit-test gate. |

**Minimal offline-friendly example (read-only intent):**

```bash
# Default discovery only (does not recurse tests/integration)
pytest -q tests/unit -k 'not requires_network' --collect-only
```

Do not set `IPFS_KIT_AUTO_INSTALL_BINARIES=1` to make tests green.

---

## 6. Recovery authority index

When a check leaves the read-only phase, **mutate only under the linked authority**. This guide does not own recovery procedures.

| Plane | Recovery authority | Related ADR (status may be Proposed) |
|---|---|---|
| Imports / extras / async boundaries | [`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md) | ADR-0001 |
| Process entries, CLI, MCP++ lifecycle | [`RUNTIME_AND_ENTRYPOINTS.md`](../architecture/RUNTIME_AND_ENTRYPOINTS.md) | — |
| Config, secrets, state roots, redaction | [`CONFIGURATION_STATE_AND_TRUST.md`](../architecture/CONFIGURATION_STATE_AND_TRUST.md) §10–11 | ADR-0007 |
| Backend documents and health | [`STORAGE_BACKEND_SYSTEM.md`](../architecture/STORAGE_BACKEND_SYSTEM.md) | ADR-0002 |
| VFS, WAL, journal, cache, metadata | [`CONTENT_METADATA_VFS.md`](../architecture/CONTENT_METADATA_VFS.md) §8 | ADR-0005 |
| Cluster families A/B/C | [`CLUSTER_COORDINATION.md`](../architecture/CLUSTER_COORDINATION.md) §7 | ADR-0008 |
| Kubo / Iroh / libp2p / routing | [`NETWORK_TRANSPORTS.md`](../architecture/NETWORK_TRANSPORTS.md); `docs/iroh/*` | ADR-0006 |
| MCP tools, transports, receipts | [`MCP_CONTROL_PLANE.md`](../architecture/MCP_CONTROL_PLANE.md) | ADR-0003 |
| Compatibility / wrong tree | [`COMPATIBILITY_LAYERS.md`](../architecture/COMPATIBILITY_LAYERS.md), [`AGENT_SYSTEM_MAP.md`](../architecture/AGENT_SYSTEM_MAP.md) §2 / §5 | — |
| Open owner decisions | [`SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md) `U-*` | Matching ADR only—do not invent Accepted |

---

## 7. Cross-cutting decision table

| If you see… | Class | First move | Escalate to |
|---|---|---|---|
| WAL `retrying` / backend blip | **Retryable** | Wait for health; drain pending | CONTENT_METADATA_VFS if budget exhausted |
| Optional extra missing; feature off | **Degraded** | Document gap; install extra if required | ASYNC_AND_OPTIONAL_DEPENDENCIES |
| Receipt / integrity / unknown type | **Blocked** | Stop; preserve artifacts | MCP or STORAGE guide + fail-closed path |
| Stale MCP PID | **Retryable** (after confirm dead) | Remove PID; restart under correct entry | RUNTIME |
| `healthy: not-probed` | **Degraded** (info) | Inject probe or accept offline default | STORAGE_BACKEND_SYSTEM |
| Crash-loop Iroh | **Blocked** | Do not force start; inspect redacted crash receipt | `docs/iroh/recovery.md` |
| Integration tests “missing” | **Degraded** coverage | Expect default discovery exclusion | §5.10; authorize integration run |
| Cluster API constructor TypeError | **Blocked** for that Family A path | Do not paper over; cite CLUSTER §8 mismatches | U-08 / ADR-0008 owners |
| Secrets in a log paste | **Blocked** for sharing | Scrub; rotate if exposure confirmed | CONFIGURATION §6 |

---

## 8. What this guide will not do

- Start daemons, install binaries, or rewrite config as the first step.
- Provide real secret values, sample cluster secrets, or live tickets in examples.
- Select production defaults among open conflicts (`U-08` cluster, `U-09` transport, `U-13` config composition, `U-16` daemon manager, dual WAL stacks `U-06`).
- Replace normative Iroh runbooks or full operations manuals.
- Mark protected board files complete or edit `docs/documentation_plan.md`, `docs/architecture/ipfs_kit_documentation.objectives.md`, or `docs/architecture/ipfs_kit_documentation.todo.md`.

---

## 9. Change triggers

Re-verify this document when any of the following change:

- Default state roots, PID/log layouts, or redaction rules  
- Packaged console scripts or MCP transport matrix  
- WAL/journal recovery APIs or status vocabularies  
- Backend health probe defaults  
- Receipt fail-closed semantics or coordination store paths  
- pytest discovery / `norecursedirs`  
- Iroh lifecycle/security contracts  
- Closure of a listed `U-*` that changes diagnostic routing  

**Baseline:** repository inspection for KDOC-052; architecture guides active as of 2026-08-04.

---

## 10. Related reading order

1. This file (symptom → class → safe check).  
2. [`CONFIGURATION_STATE_AND_TRUST.md`](../architecture/CONFIGURATION_STATE_AND_TRUST.md) safe runbook and state catalog.  
3. Subsystem architecture guide from §5.  
4. Normative Iroh docs when the Iroh plane is involved.  
5. Matching ADR if an owner decision is required—do not invent acceptance.  
6. [`AGENT_SYSTEM_MAP.md`](../architecture/AGENT_SYSTEM_MAP.md) if the fix becomes a code change.  
7. [`DOCUMENTATION_IMPACT_MAP.md`](../development/DOCUMENTATION_IMPACT_MAP.md) if docs must update after the fix.
