# Iroh documentation entry point and reconciliation map

| Field | Value |
|---|---|
| **Document class** | Maintained product entry point (index + reconciliation map) |
| **Status** | active |
| **Task** | KDOC-037 |
| **Goal** | KDOC-G042 |
| **Track** | current-operations |
| **Last verified** | 2026-08-04 |
| **Scope authority** | This file owns the **Iroh index only**. Normative contracts and runbooks under `docs/iroh/*.md` remain authoritative; this document **links and classifies** them and does not rewrite them. |
| **Related architecture** | [`NETWORK_TRANSPORTS.md`](../architecture/NETWORK_TRANSPORTS.md) (Kubo / Iroh / libp2p coexistence), [`STORAGE_BACKEND_SYSTEM.md`](../architecture/STORAGE_BACKEND_SYSTEM.md), [`SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md), ADR [`0006-multi-protocol-storage-and-networking.md`](../architecture/decisions/0006-multi-protocol-storage-and-networking.md) |
| **Related product docs** | [`installation_guide.md`](../installation_guide.md), [`api/cli_reference.md`](../api/cli_reference.md), [`reference/storage_backends.md`](../reference/storage_backends.md), [`VFS_CONTRACT_SPEC.md`](../VFS_CONTRACT_SPEC.md), [`integration/INTEGRATION_OVERVIEW.md`](../integration/INTEGRATION_OVERVIEW.md) |

This directory is the **strongest in-tree normative contract suite** for the managed Iroh sidecar, BLAKE3 blob/manifest backend, fsspec/`IrohFileSystem` surface, operator CLIs, security model, and release gates. Use this README to choose the right document by audience, authority class, and lifecycle stage—not as a substitute for the linked contracts.

**Default product posture:** Iroh is an **optional**, **disabled-by-default** parallel storage path. BLAKE3 hashes are never IPFS CIDs. Ordinary package import and non-Iroh backends must not require a sidecar. Binary distribution may be `source-pinned` / not installable until the release record says otherwise—see [compatibility.md](compatibility.md) and [release-readiness.md](release-readiness.md).

---

## 1. Purpose and non-goals

### 1.1 Purpose

| Goal | How this document satisfies it |
|---|---|
| Single maintained entry point | Catalog every maintained file under `docs/iroh/` with classification and one-line role |
| Audience reading paths | Ordered sequences for operators, integrators, security reviewers, and release engineers |
| Source / test / workflow map | Pointers into `ipfs_kit_py/iroh*`, packaging scripts, schemas, fixtures, tests, and CI |
| Lifecycle and security prerequisites | What must be true before install, enablement, or production-like use |
| Reconciliation | Explain overlap with general ops/observability/VFS docs **without copying** them |
| Later work queue | Surface inconsistencies that need focused follow-up (not silent rewrites here) |

### 1.2 Non-goals

| Out of scope | Owner |
|---|---|
| Rewriting IROH-00x contracts or IROH-023/024 runbooks | Individual normative files below |
| Choosing default content transport (Kubo vs Iroh vs dual-write) | ADR / U-09; see NETWORK_TRANSPORTS |
| Full Kubo, libp2p, or multi-backend routing tutorials | NETWORK_TRANSPORTS, routing modules, integration guides |
| Generic Prometheus/Grafana stack docs | [`docs/operations/observability.md`](../operations/observability.md) |
| Generic kit performance APIs | [`docs/operations/performance_metrics.md`](../operations/performance_metrics.md) |
| MCP VFS JSON envelope contract (IPFS fsspec path) | [`docs/VFS_CONTRACT_SPEC.md`](../VFS_CONTRACT_SPEC.md) |

---

## 2. Status snapshot

| Dimension | Current reading | Authority |
|---|---|---|
| Release bundle | `iroh-1.0.2-ipfs-kit.1` | [compatibility.md](compatibility.md), `ipfs_kit_py/resources/iroh-releases.json` |
| Sidecar RPC protocol | `1` | [compatibility.md](compatibility.md), protocol modules |
| Filesystem / capability contracts | **Frozen** version 1 | [filesystem-contract.md](filesystem-contract.md), [capability-matrix.md](capability-matrix.md) |
| Default enablement | **Disabled** (`iroh.enabled=false`) | [release-readiness.md](release-readiness.md), [release-notes.md](release-notes.md) |
| Sidecar distribution | **Source-pinned**; platforms may be `installable: false` | [compatibility.md](compatibility.md), [install-lifecycle.md](install-lifecycle.md) |
| Real multi-node interop evidence | Checked-in status may be `not_run` until protected lanes run | [interoperability.md](interoperability.md) |
| Production support claim | **Not** a supported production storage backend until readiness promotes stages | [release-readiness.md](release-readiness.md), [release-notes.md](release-notes.md) |

Treat marketing language elsewhere in the tree as non-authoritative when it conflicts with this suite.

---

## 3. Classification vocabulary

Every maintained document below has exactly one **class**:

| Class | Meaning | Edit discipline |
|---|---|---|
| **Normative decision** | Frozen or accepted IROH decision (MUST/SHOULD language, machine records) | Change only with versioned contract work and tests |
| **Normative contract** | Behavioral boundary for callers, adapters, or schemas | Same; fixtures and schemas co-move |
| **Operator runbook** | Production procedure for a named release bundle | Keep command-safe (no secrets in argv); link security |
| **Operator guide** | How-to for config, lifecycle, backends, or diagnostics | Prefer examples with redaction and dry-run |
| **Security model** | Threat model, trust boundaries, rotation authority | Align with security tests and vector fixtures |
| **Release / CI gate** | Packaging, coverage, readiness, interop evidence | Co-maintain with workflow and resource JSON |
| **Product note** | Human-facing release summary | Must not contradict readiness/compatibility |

**Authority order when documents disagree:** machine records (`ipfs_kit_py/resources/iroh-*.json` + schemas) and frozen IROH decisions → operator runbooks for the same bundle → this index → broader architecture guides → historical status reports.

---

## 4. Maintained document catalog

All paths are relative to this directory. **Every maintained Iroh doc is listed once.**

### 4.1 Normative decisions and contracts

| Document | Class | Role |
|---|---|---|
| [compatibility.md](compatibility.md) | Normative decision (IROH-001) | Upstream crate pin, sidecar identity, installability, BLAKE3 ≠ CID |
| [filesystem-contract.md](filesystem-contract.md) | Normative contract (IROH-002) | Caller / manifest / backend / sidecar boundary; URL, errors, schemas |
| [capability-matrix.md](capability-matrix.md) | Normative contract (IROH-003) | fsspec/VFS operation classification: `native` / `emulated` / `unsupported` |

### 4.2 Backend, VFS, and tiering

| Document | Class | Role |
|---|---|---|
| [named-backends.md](named-backends.md) | Operator guide | Registry-side `iroh` backend create/show/migrate; secret-free documents |
| [bucket-tiering.md](bucket-tiering.md) | Operator guide | Virtual buckets; primary/replica/cache/archive bindings; quotas |
| [filesystem-contract.md](filesystem-contract.md) | Normative contract | See §4.1 — path/URL and manifest authority for filesystem semantics |
| [capability-matrix.md](capability-matrix.md) | Normative contract | See §4.1 — which operations ship in v1 |

### 4.3 Install, service configuration, and lifecycle

| Document | Class | Role |
|---|---|---|
| [install-lifecycle.md](install-lifecycle.md) | Operator guide | `ipfs-kit-iroh` install/inspect/update/rollback; no download on import |
| [service-configuration.md](service-configuration.md) | Operator guide | Versioned service JSON, state layout, closed schema |
| [service-lifecycle.md](service-lifecycle.md) | Operator guide | `IrohService` start/stop/restart, PID ownership, crash-loop protection |

### 4.4 Deployment, recovery, and day-2 operations

| Document | Class | Role |
|---|---|---|
| [operations.md](operations.md) | Operator runbook (IROH-023) | Deployment checklist, network policy, upgrade/rollback, safe ops CLI |
| [recovery.md](recovery.md) | Operator runbook (IROH-023) | Backup sets, RPO/RTO, identity vs content recovery |
| [observability.md](observability.md) | Operator guide | Per-instance health/metrics/prometheus; redacted receipts |
| [performance.md](performance.md) | Release / CI gate (IROH-016) | Deterministic in-memory baseline; not WAN claims |

### 4.5 Security

| Document | Class | Role |
|---|---|---|
| [threat-model.md](threat-model.md) | Security model (IROH-024) | Assets, boundaries, STRIDE-style abuse cases |
| [security.md](security.md) | Operator runbook (IROH-023) | Deployment security baseline for enabled instances |
| [credential-rotation.md](credential-rotation.md) | Operator runbook (IROH-024) | Node identity, write capabilities, and read-ticket rotation |

### 4.6 Interoperability, packaging, and release

| Document | Class | Role |
|---|---|---|
| [interoperability.md](interoperability.md) | Release / CI gate (IROH-025) | Multi-node harness; offline vs real-node evidence |
| [ci-packaging.md](ci-packaging.md) | Release / CI gate (IROH-026) | Required offline lanes, coverage floor, multi-node dispatch |
| [release-readiness.md](release-readiness.md) | Release / CI gate | Disabled-stage policy, receipt ledger, promotion gates |
| [release-notes.md](release-notes.md) | Product note | Human summary of preview/disabled posture and compatibility |

---

## 5. Reading paths by audience

### 5.1 Operator enabling a managed sidecar (first time)

1. [release-notes.md](release-notes.md) + [release-readiness.md](release-readiness.md) — confirm **disabled-by-default** and whether install is even allowed for your platform  
2. [compatibility.md](compatibility.md) — pin, protocol, installability  
3. [threat-model.md](threat-model.md) → [security.md](security.md) — trust model before exposure  
4. [install-lifecycle.md](install-lifecycle.md) — verified binary lifecycle (`--dry-run` first)  
5. [service-configuration.md](service-configuration.md) + [service-lifecycle.md](service-lifecycle.md)  
6. [operations.md](operations.md) — network policy, start/verify, upgrade  
7. [named-backends.md](named-backends.md) — bind a secret-free backend document  
8. [observability.md](observability.md) — health and redacted diagnostics  
9. [recovery.md](recovery.md) — backups **before** treating data as durable  
10. [credential-rotation.md](credential-rotation.md) — plan rotation before sharing tickets  

### 5.2 Integrator / application developer (fsspec or library)

1. [compatibility.md](compatibility.md) — addressing model (BLAKE3, not CID)  
2. [filesystem-contract.md](filesystem-contract.md) — URLs, errors, schemas  
3. [capability-matrix.md](capability-matrix.md) — supported vs unsupported operations  
4. [named-backends.md](named-backends.md) and optional [bucket-tiering.md](bucket-tiering.md)  
5. Packaging: extra `iroh`; fsspec protocols `iroh` / `iroh+blob` (see §6)  
6. Architecture context only: [NETWORK_TRANSPORTS.md](../architecture/NETWORK_TRANSPORTS.md)  

Do **not** use [VFS_CONTRACT_SPEC.md](../VFS_CONTRACT_SPEC.md) as the Iroh filesystem authority; that document covers the IPFS/MCP VFS envelope. Iroh path semantics live in **filesystem-contract** and **capability-matrix**.

### 5.3 Security reviewer

1. [threat-model.md](threat-model.md)  
2. [security.md](security.md)  
3. [credential-rotation.md](credential-rotation.md)  
4. [filesystem-contract.md](filesystem-contract.md) (permission and integrity rules)  
5. [operations.md](operations.md) (network policy, local RPC)  
6. [recovery.md](recovery.md) (identity vs content)  
7. Evidence: `ipfs_kit_py/resources/iroh-security-vectors.json`, `tests/test_iroh_security.py`  

### 5.4 Release engineer / CI maintainer

1. [ci-packaging.md](ci-packaging.md) — offline lanes and coverage  
2. [interoperability.md](interoperability.md) — when multi-node may run  
3. [release-readiness.md](release-readiness.md) + machine reports under `ipfs_kit_py/resources/iroh-release-*.json`  
4. [performance.md](performance.md) — budget floors only  
5. [compatibility.md](compatibility.md) — installable flags and bundle identity  
6. Workflow: `.github/workflows/iroh-ci.yml`  

### 5.5 Architect comparing transports

Start with [NETWORK_TRANSPORTS.md](../architecture/NETWORK_TRANSPORTS.md) and ADR-0006, then return here for **normative Iroh depth**. Do not treat the architecture guide as a substitute for this suite.

---

## 6. Source, packaging, test, and workflow map

### 6.1 Primary code and packaging

| Concern | Location |
|---|---|
| Iroh package modules | `ipfs_kit_py/iroh/` (`service`, `client`, `backend`, `blob_store`, `manifest`, `protocol`, `security`, `observability`, `gc`, `multinode`, CLIs) |
| Install CLI | `ipfs_kit_py/iroh_install_cli.py`, `install_iroh.py` |
| fsspec filesystem | `ipfs_kit_py/iroh_fsspec.py` (`IrohFileSystem`); packaging entry points `iroh`, `iroh+blob` |
| Live storage adapter | `ipfs_kit_py/backends/iroh_backend.py` |
| Optional extra | `pyproject.toml` → `[project.optional-dependencies]` name `iroh` |
| Console scripts | `ipfs-kit-iroh`, `ipfs-kit-iroh-ops`, `ipfs-kit-iroh-diagnostics`, `ipfs-kit-iroh-manifest`, `ipfs-kit-iroh-interop` |
| Example configs | `config/iroh-service.example.json`, `config/iroh-backend.example.yaml` |
| Machine records & schemas | `ipfs_kit_py/resources/iroh-*.json` (+ matching `*.schema.json`) |
| Contract fixtures | `tests/fixtures/iroh/` |

CLI depth lives in [`docs/api/cli_reference.md`](../api/cli_reference.md); install policy in [`docs/installation_guide.md`](../installation_guide.md). This index does not duplicate command tables.

### 6.2 Focused tests (representative)

| Area | Tests (pattern) |
|---|---|
| Contracts / compatibility | `tests/test_iroh_filesystem_contract.py`, `tests/test_iroh_capability_matrix.py`, `tests/test_iroh_compatibility_record.py` |
| Backend / blob / manifest / GC | `tests/test_iroh_backend_manager.py`, `tests/test_iroh_blob_store.py`, `tests/test_iroh_manifest.py`, `tests/test_iroh_gc.py`, `tests/test_iroh_bucket_tiering.py` |
| fsspec / VFS | `tests/test_iroh_fsspec_*.py`, `tests/test_iroh_vfs_integration.py` |
| Service / config / install | `tests/test_iroh_service.py`, `tests/test_iroh_config.py`, `tests/test_iroh_install_cli.py`, `tests/test_iroh_runtime_client.py` |
| Security / observability / CLI | `tests/test_iroh_security.py`, `tests/test_iroh_observability.py`, `tests/test_iroh_cli.py`, `tests/test_iroh_cli_gates.py` |
| Packaging / release / interop | `tests/test_iroh_packaging.py`, `tests/test_iroh_release_readiness.py`, `tests/test_iroh_multinode.py`, `tests/test_iroh_performance.py` |
| Ops doc offline gates | `tests/test_iroh_operations_docs.py` (IROH-023 operations/security/recovery) |
| MCP | `tests/test_iroh_mcp_api.py` (`iroh_diagnostics` tool) |

### 6.3 CI workflow

| Artifact | Role |
|---|---|
| `.github/workflows/iroh-ci.yml` | IROH-026 lanes: unit, fsspec, async, service, installer, security, platform, packaging, coverage, protected multi-node, release readiness |
| Offline PR default | No sidecar download/discovery; missing binary is a supported state; storage ops fail closed |
| Multi-node | Explicit environment + self-hosted labels; not part of ordinary offline PR runs |

---

## 7. Lifecycle and security prerequisites

Before treating Iroh as more than a disabled optional path, confirm:

| Prerequisite | Why | Docs |
|---|---|---|
| Release record allows install for your OS/arch | Installers fail closed when `installable: false` | [compatibility.md](compatibility.md), [install-lifecycle.md](install-lifecycle.md) |
| Explicit enablement (not package default) | Default is disabled; import must not pull binaries | [release-readiness.md](release-readiness.md), [install-lifecycle.md](install-lifecycle.md) |
| Credential references only (no inline secrets) | Config and backends reject inline credentials | [service-configuration.md](service-configuration.md), [named-backends.md](named-backends.md), [security.md](security.md) |
| Local RPC only | Remote RPC endpoints are rejected | [service-configuration.md](service-configuration.md), [operations.md](operations.md) |
| Network policy understood | Direct QUIC, relay HTTPS, DNS discovery are optional openings | [operations.md](operations.md) network policy |
| Backup of identity **and** content defined | Either alone is incomplete recovery | [recovery.md](recovery.md) |
| Rotation procedure owned | Tickets and write capabilities are bearer authority | [credential-rotation.md](credential-rotation.md), [threat-model.md](threat-model.md) |
| Observability path ready | Health ≠ readiness; receipts are allowlisted | [observability.md](observability.md) |

**Hard rules carried from the suite (summary only):**

- Do not label BLAKE3 hashes as IPFS CIDs (or the reverse).  
- Do not put bearer tickets, keys, or resolved credentials in argv, logs, tickets-as-config, or evidence JSON.  
- Do not run `ipfs-kit-iroh install` (or auto-install env) in restricted CI without an explicit, audited exception.  
- Ordinary pytest must not start real multi-node Iroh daemons; that is opt-in interop.

---

## 8. Reconciliation map (duplicates explained, not copied)

Iroh topics appear in general documentation. Prefer **one authority** and **link** elsewhere.

| Topic | Iroh-local authority | General / parallel doc | Reconciliation rule |
|---|---|---|---|
| Network role of Iroh among Kubo/libp2p | This suite for contracts; depth starts at [compatibility.md](compatibility.md) | [NETWORK_TRANSPORTS.md](../architecture/NETWORK_TRANSPORTS.md) | Architecture describes coexistence; **does not** replace Iroh contracts |
| Named storage backends | [named-backends.md](named-backends.md) | [STORAGE_BACKEND_SYSTEM.md](../architecture/STORAGE_BACKEND_SYSTEM.md), [reference/storage_backends.md](../reference/storage_backends.md) | General guides list Iroh as one backend type; Iroh document shapes and migration live here |
| Filesystem / VFS semantics | [filesystem-contract.md](filesystem-contract.md), [capability-matrix.md](capability-matrix.md) | [VFS_CONTRACT_SPEC.md](../VFS_CONTRACT_SPEC.md), [CONTENT_METADATA_VFS.md](../architecture/CONTENT_METADATA_VFS.md) | VFS_CONTRACT_SPEC is **IPFS/MCP VFS envelope** oriented; Iroh fsspec semantics are **this suite** |
| Install / console scripts | [install-lifecycle.md](install-lifecycle.md), [operations.md](operations.md) | [installation_guide.md](../installation_guide.md), [QUICK_REFERENCE.md](../QUICK_REFERENCE.md), [api/cli_reference.md](../api/cli_reference.md) | Product CLI tables stay in CLI/install docs; Iroh runbooks own safe ops sequencing and network policy |
| Day-2 operations | [operations.md](operations.md), [recovery.md](recovery.md) | [docs/operations/cluster_*.md](../operations/) (cluster plane) | Cluster docs are **not** Iroh sidecar ops; do not merge runbooks |
| Observability / metrics | [observability.md](observability.md) | [docs/operations/observability.md](../operations/observability.md), [performance_metrics.md](../operations/performance_metrics.md) | General stack is kit-wide Prometheus/Grafana and IPFS metrics APIs; Iroh doc is **instance-scoped, redacted** diagnostics (`IrohObservability`, `ipfs-kit-iroh-diagnostics`) |
| Performance claims | [performance.md](performance.md) | [operations/performance_metrics.md](../operations/performance_metrics.md) | Iroh baseline is **CI regression floor** in-memory; general guide is broader kit benchmarking—do not equate |
| Credentials / secrets | [security.md](security.md), [credential-rotation.md](credential-rotation.md) | [credential_management.md](../credential_management.md), [CONFIGURATION_STATE_AND_TRUST.md](../architecture/CONFIGURATION_STATE_AND_TRUST.md) | Kit-wide secret-reference patterns apply; Iroh-specific assets (node identity, tickets, write caps) are detailed here |
| Integration maturity | This README + [release-readiness.md](release-readiness.md) | [integration/INTEGRATION_OVERVIEW.md](../integration/INTEGRATION_OVERVIEW.md) | Integration overview classifies optional systems; Iroh enablement/readiness remains this suite |
| Glossary terms | Linked contracts | [GLOSSARY.md](../architecture/GLOSSARY.md) | Glossary points at implementation; definitions of manifest/CAS/errors stay in filesystem-contract |

**Do not copy** large sections from general operations or observability docs into this directory. If a general doc must mention Iroh, it should link here (or to a specific Iroh file) rather than restating runbooks.

---

## 9. Known inconsistencies and follow-up work

These are **honest gaps** for later focused tasks—not instructions to expand this index into a rewrite of contracts.

| Item | Observation | Suggested follow-up |
|---|---|---|
| Installability vs preview feature set | Code and docs describe a full v1 surface while platforms may remain `installable: false` | Keep release-readiness and compatibility as gate; avoid “production ready” wording outside those gates |
| Multi-node evidence | Interop record may honestly be `not_run` | Do not invent passed multi-node status in architecture or marketing docs |
| VFS_CONTRACT_SPEC freshness | Still oriented to legacy unified MCP server paths; parallel to Iroh contracts | VFS refresh task should **link** filesystem-contract rather than merge authorities |
| General ops observability | `docs/operations/observability.md` is Prometheus/Grafana kit-wide and does not model Iroh receipt redaction | Leave separate; optionally add a one-line cross-link from the general doc in a later ops task |
| Open transport default (U-09) | No accepted default among Kubo / Iroh / dual-write | ADR-0006 / owner decision; this suite stays Iroh-local |
| Historical status reports | Older “N backends complete” language may overstate Iroh production readiness | Prefer this index + release-readiness over `docs/status_reports/` |

---

## 10. Quick links (alphabetical)

| File | Class |
|---|---|
| [bucket-tiering.md](bucket-tiering.md) | Operator guide |
| [capability-matrix.md](capability-matrix.md) | Normative contract (IROH-003) |
| [ci-packaging.md](ci-packaging.md) | Release / CI gate (IROH-026) |
| [compatibility.md](compatibility.md) | Normative decision (IROH-001) |
| [credential-rotation.md](credential-rotation.md) | Operator runbook (IROH-024) |
| [filesystem-contract.md](filesystem-contract.md) | Normative contract (IROH-002) |
| [install-lifecycle.md](install-lifecycle.md) | Operator guide |
| [interoperability.md](interoperability.md) | Release / CI gate (IROH-025) |
| [named-backends.md](named-backends.md) | Operator guide |
| [observability.md](observability.md) | Operator guide |
| [operations.md](operations.md) | Operator runbook (IROH-023) |
| [performance.md](performance.md) | Release / CI gate (IROH-016) |
| [recovery.md](recovery.md) | Operator runbook (IROH-023) |
| [release-notes.md](release-notes.md) | Product note |
| [release-readiness.md](release-readiness.md) | Release / CI gate |
| [security.md](security.md) | Operator runbook (IROH-023) |
| [service-configuration.md](service-configuration.md) | Operator guide |
| [service-lifecycle.md](service-lifecycle.md) | Operator guide |
| [threat-model.md](threat-model.md) | Security model (IROH-024) |

---

## 11. Maintenance note

When adding a new Iroh document:

1. Place it under `docs/iroh/`.  
2. Add it to **§4** (correct class) and **§10**.  
3. Extend the relevant audience path in **§5** if operators or integrators need it.  
4. Update **§8** if it overlaps a general ops/architecture doc.  
5. Prefer linking machine records and tests over duplicating tables.  
6. Keep this README free of secrets, long command dumps already owned by runbooks, and rewrites of frozen IROH decisions.
