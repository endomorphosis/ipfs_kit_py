# VFS, Bucket, and Path-Plane Contract Specification

| Field | Value |
|---|---|
| Document class | **Canonical contract** (request/response + adapter ranking) |
| Status | Active |
| Schema version | `2` (content-mutation integration envelope) |
| Last verified | 2026-08-04 |
| Owner / task | KDOC-035 |
| Architecture parent | [`docs/architecture/CONTENT_METADATA_VFS.md`](architecture/CONTENT_METADATA_VFS.md) (KDOC-014) |
| Related Iroh FS contract | [`docs/iroh/filesystem-contract.md`](iroh/filesystem-contract.md) |
| Related journal contract | [`docs/filesystem_journal.md`](filesystem_journal.md) |
| Vocabulary | [`docs/architecture/GLOSSARY.md`](architecture/GLOSSARY.md) |

The keywords **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are requirements for implementations that claim VFS-contract conformance. Architecture guides may describe candidate stacks; this document is the **normative** shape for `VFSCore` / `vfs_*` responses and the ranking of current vs compatibility adapters.

---

## 1. Scope and non-goals

### 1.1 In scope

| Topic | Why it is contract-owned |
|---|---|
| Request/response envelopes for `VFSCore` and module-level `vfs_*` helpers | Callers and MCP adapters share one shape |
| Content-mutation integration metadata (`schema_version` 2, `operation_id`, lineage) | Cross-plane correlation and observability |
| Mount lifecycle, path resolve, read/write, directory ops, sync_to / sync_from | Core path-plane verbs |
| Bucket identity relative to VFS paths (candidate managers) | Avoid conflating bucket namespaces with mount paths |
| **Ordering**, atomicity boundaries, sync conflict policy | Crash and multi-writer expectations |
| Failure, partial success, and retry semantics | No silent failures; no false “all green” |
| Current vs compatibility MCP/CLI/fsspec adapters | Rank surfaces; document packaging vs legacy conflict |
| Security-relevant path and secret rules for contract surfaces | Fail closed on path traversal and secret leakage |

### 1.2 Non-goals

| Out of scope | Owner |
|---|---|
| Choosing a single production bucket manager among parallel stacks (U-05) | ADR track / maintainer decision |
| Mandating WAL + journal for every backend mutation (U-06) | ADR 0005 / content-metadata guide |
| Sole MCP runtime authority (packaging MCP++ vs `ipfs_kit_py.mcp`) | ADR-0003; see [§3](#3-mcp-and-adapter-surfaces-current-vs-compatibility) |
| Full Iroh manifest grammar and URL ABNF | [`docs/iroh/filesystem-contract.md`](iroh/filesystem-contract.md) |
| Exhaustive CLI flag inventories | CLI reference (KDOC-032) |
| Generated API dumps | Generated inventory track |

---

## 2. Authority ranking and evidence policy

1. **Executable behavior** in `ipfs_kit_py/ipfs_fsspec.py` (`VFSCore`, `vfs_*`) and focused tests under default pytest discovery outrank older prose.
2. **Packaging entry points** in `pyproject.toml` outrank undocumented import paths for “how operators start MCP.”
3. **Architecture guides** ([CONTENT_METADATA_VFS](architecture/CONTENT_METADATA_VFS.md), [SOURCE_OF_TRUTH_MAP](architecture/SOURCE_OF_TRUTH_MAP.md)) rank candidate vs compatibility modules; they do not invent ADR outcomes.
4. Claims in this document that state **Evidence** MUST name focused tests or implementation symbols. Untested narrative is labeled **Inferred** or **Unresolved**.

Primary implementation:

| Symbol | Module |
|---|---|
| `VFSCore` | `ipfs_kit_py/ipfs_fsspec.py` |
| `vfs_mount`, `vfs_unmount`, `vfs_list_mounts`, `vfs_resolve_path` | same |
| `vfs_read`, `vfs_write`, `vfs_ls`, `vfs_stat`, `vfs_mkdir`, `vfs_rmdir` | same |
| `vfs_copy`, `vfs_move` | same |
| `vfs_sync_to_ipfs`, `vfs_sync_from_ipfs` | same |
| `get_vfs()` singleton helper | same |

---

## 3. MCP and adapter surfaces (current vs compatibility)

### 3.1 Explicit ranking

| Rank | Surface | Path / entry | Role | Contract duty |
|---|---|---|---|---|
| **Current (packaged MCP)** | MCP++ JSON-RPC server | Console `ipfs-kit-mcp` → `ipfs_kit_py.mcp_server.server:main` | Packaging-default MCP control plane | Tool wrappers SHOULD map path-plane work through kit domain modules; not a second VFS implementation |
| **Current (contract core)** | `VFSCore` / `vfs_*` | `ipfs_kit_py/ipfs_fsspec.py` | Normative request/response shapes in this document | **MUST** implement schema v2 mutation envelopes and stable failure `code`s |
| **Current (candidate bucket path plane)** | Bucket VFS | `bucket_vfs_manager.py`, `bucket_vfs_api.py`, `bucket_manager.py` | Multi-bucket VFS with UnixFS-style layout | Async manager APIs; see [§7](#7-bucket-identity-relative-to-vfs) |
| **Current (candidate unified buckets)** | Unified bucket interface | `unified_bucket_interface.py`, `unified_bucket_cli.py` | Cross-backend bucket + pin composition under `~/.ipfs_kit/buckets/` | Parallel candidate; **not** declared sole default (U-05) |
| **Current (shared managers)** | VFS managers | `vfs_manager.py`, `vfs_bucket_manager.py`, `vfs_version_tracker.py` | Shared ops, version chains, Parquet VFS index helpers | Orthogonal version lineage vs per-path sync state |
| **Current (packaged fsspec)** | Iroh filesystem | `iroh_fsspec.py` (`IrohFileSystem`); `pyproject.toml` protocols `iroh`, `iroh+blob` | Only packaging-declared fsspec protocols | Bound by Iroh FS contract, not this schema v2 envelope |
| **Compatibility (legacy MCP tree)** | `unified_mcp_server` and siblings | `ipfs_kit_py/mcp/servers/unified_mcp_server.py`, `enhanced_mcp_server_with_vfs.py`, `standalone_vfs_mcp_server.py`, `enhanced_mcp_server_with_daemon_mgmt.py` | Historical / migration servers | **MUST** delegate canonical mount lifecycle ops to contract helpers when `HAS_CONTRACT_VFS`; **blocked** in production without override |
| **Compatibility (legacy MCP tool shims)** | Root / package tool modules | e.g. `bucket_vfs_mcp_tools.py`, `fs_journal_mcp_tools.py`, root `mcp/*` shims | Bridge older layouts | Do not document as packaging defaults |
| **Compatibility (simplified buckets)** | Simple / clean CLIs | `simple_bucket_manager.py`, `simplified_bucket_manager.py`, `simple_bucket_cli.py`, `clean_bucket_cli.py`, `cli/bucket_cli.py` | Alternate stacks | Not production defaults |
| **Compatibility (import-time fsspec)** | Enhanced fsspec registration | `enhanced_fsspec.py` (`ipfs` / `filecoin` / …) | Import-side registration | **Not** packaging entry points (U-17) |
| **Historical / dual** | Parallel indexes | `enhanced_bucket_index.py` / `enhanced_bucket_index_fixed.py` | Parallel index implementations | Do not treat as equal authority |

### 3.2 MCP authority conflict (explicit; unresolved for sole production)

| Claim class | Statement | Evidence |
|---|---|---|
| **Packaging current** | Operators who install console scripts get `ipfs-kit-mcp` → `ipfs_kit_py.mcp_server.server:main` (MCP++). | `pyproject.toml` `[project.scripts]`; [`MCP_CONTROL_PLANE.md`](architecture/MCP_CONTROL_PLANE.md) |
| **Legacy tree policy** | Under `IPFS_KIT_MCP_MODE=production`, legacy servers in `ipfs_kit_py/mcp/servers/*` (enhanced VFS, standalone VFS, daemon-mgmt) raise `RuntimeError` unless `IPFS_KIT_ALLOW_LEGACY_MCP=1`. | `tests/test_mcp_vfs_adapter_contract.py::test_legacy_servers_blocked_in_production_without_override` |
| **Migration prose conflict** | Older migration docs still advertise `ipfs_kit_py.mcp.servers.unified_mcp_server` as “Canonical Runtime.” That claim **competes** with packaging and is **not** elevated to sole production authority in this contract. | [`MCP_SERVER_MIGRATION_GUIDE.md`](MCP_SERVER_MIGRATION_GUIDE.md); freshness finding F-020; ADR-0003 proposed |
| **Contract core independence** | Path-plane response shapes are defined by `VFSCore` regardless of which MCP server hosts tools. Adapters MUST NOT invent alternate success/failure shapes for the same operation names. | `tests/test_mcp_vfs_adapter_contract.py` (adapters inject `operation` and delegate to `contract_vfs_*`) |

**Operator guidance:** Prefer packaged `ipfs-kit-mcp` for control-plane process management. Prefer `VFSCore` / `vfs_*` (or CLI domain verbs mounted on `ipfs-kit`) for data-plane path operations. Treat `unified_mcp_server` and enhanced/standalone VFS servers as **compatibility** unless a maintainer accepts ADR-0003 otherwise.

### 3.3 Adapter conformance rules

Compatibility MCP adapters **MUST**:

1. Delegate mount / unmount / list_mounts / resolve_path to the shared contract layer when available (`contract_vfs_*` / `HAS_CONTRACT_VFS`).
2. Include `operation` (string operation name) on MCP-surfaced results.
3. Preserve `success` and stable `code` fields from the core without rewriting them to free-form strings only.

Evidence: `tests/test_mcp_vfs_adapter_contract.py` (`test_enhanced_adapter_delegates_canonical_mount_ops`, `test_standalone_adapter_delegates_canonical_mount_ops`, `test_unified_mcp_dispatches_vfs_tools_and_exposes_resolve_path`).

---

## 4. Global response contract

### 4.1 Success and failure envelope

Every contract-facing VFS operation **MUST** return a JSON-serializable `dict` containing:

| Field | Type | Requirement |
|---|---|---|
| `success` | `bool` | **MUST** always be present |

When surfaced through MCP adapters or integration wrappers, responses **SHOULD** include:

| Field | Type | Requirement |
|---|---|---|
| `operation` | `string` | Operation name (e.g. `vfs_mount`) |

When `success` is `false`, responses **SHOULD** include:

| Field | Type | Requirement |
|---|---|---|
| `error` | `string` | Human-readable failure detail |
| `code` | `string` | Stable machine-readable failure key (see [§9](#9-failure-partial-and-retry-semantics)) |

Callers **MUST NOT** treat a missing `success` as success. Callers **MUST** prefer `code` over substring matching on `error` when both are present.

Evidence: `tests/test_vfs_contract_hardening.py` (mount/resolve/list/sync failure shapes); adapter tests assert `operation` + `success`.

### 4.2 Content-mutation integration metadata (schema version 2)

For **content mutation** operations (at least `write`, `copy`, `move`, and sync variants that attach integration payloads), when integrations run, the response **MUST** include an `integration` object:

```text
integration:
  dataset:   { attempted, success, adapter, fallback_order, reason?, ... }
  accelerate:{ attempted, success, adapter, fallback_order, reason?, ... }
  metadata:  { schema_version, operation_id, operation, path, backend?, mount_point?, timestamp, cid?, source_cid?, source_operation_id?, ... }
```

`integration.metadata` **MUST** include:

| Field | Constraint |
|---|---|
| `schema_version` | String `"2"` |
| `operation_id` | String starting with `op-` |
| `operation` | Mutation operation name |
| `path` | Target path |
| `timestamp` | ISO 8601 UTC |

Lineage fields **SHOULD** be present when available (always keyed; may be `null`):

| Field | Meaning |
|---|---|
| `cid` | Content identity after mutation when known |
| `source_cid` | Prior content identity for copy/move/sync lineage |
| `source_operation_id` | Prior `operation_id` for lineage chaining |

**Partial success rule (critical):** Top-level `success: true` means the **path-plane mutation** applied. Nested `integration.dataset.success` or `integration.accelerate.success` may be `false` without failing the write. Callers that require enrichment **MUST** inspect nested fields.

Evidence:

- Envelope construction: `VFSCore._run_content_mutation_integrations` in `ipfs_kit_py/ipfs_fsspec.py`
- Tests: `test_vfs_write_triggers_dataset_and_accelerate_hooks`, `test_vfs_write_graceful_when_accelerate_unavailable`, `test_vfs_write_accelerate_timeout_is_bounded`, `test_vfs_copy_and_move_emit_lineage_fields_in_metadata_envelope`

### 4.3 Observability snapshot (non-mutation)

`VFSCore.observability_snapshot()` **SHOULD** expose counters under `metrics` (e.g. `mount`, `resolve_path`, `dataset_events`, `accelerate_enrichment`, `accelerate_timeouts`) and sync retention state under `sync_state`.

Evidence: `test_vfs_observability_snapshot_tracks_operations`, `test_vfs_observability_snapshot_includes_sync_retention_state`.

---

## 5. Operation contracts

Unless noted, names below are both method names on `VFSCore` and module-level `vfs_*` helpers.

### 5.1 `vfs_mount`

| | |
|---|---|
| Purpose | Attach a backend at a mount point |
| Success | `success=true`, `mounted=true`, `mount_point`, `backend` (and related mount fields as implemented) |
| Failure | `success=false`; invalid backend must be explicit (error mentions unsupported backend); empty/malformed mount points fail closed |

Evidence: `test_vfs_mount_and_resolve_path_success`, `test_vfs_mount_invalid_backend_fails_explicitly`.

### 5.2 `vfs_unmount`

| | |
|---|---|
| Purpose | Detach a mount point |
| Success | `success=true`, `unmounted=true`, `mount_point` |
| Failure | Nonexistent mount → `success=false`, `unmounted=false` (**explicit**, not silent no-op success) |

Evidence: `test_vfs_unmount_nonexistent_is_explicit_failure`.

### 5.3 `vfs_list_mounts`

| | |
|---|---|
| Purpose | Enumerate active mounts |
| Success shape | `success`, `count` (int), `mounts` (list) |

Evidence: `test_vfs_list_mounts_shape`.

### 5.4 `vfs_resolve_path`

| | |
|---|---|
| Purpose | Map a local/VFS path to backend/source path |
| Success | `success=true`, `resolved=true`, `local_path`, `mount_point`, `backend`, `resolved_path` |
| Failure | `success=false`, `resolved=false`, `error` (and `code` when classified) |

Evidence: `test_vfs_mount_and_resolve_path_success`.

### 5.5 `vfs_read`

| | |
|---|---|
| Purpose | Read file content via resolved mount |
| Success | `success=true`, `path`, `content`, `cached` (bool when cache consulted) |

### 5.6 `vfs_write`

| | |
|---|---|
| Purpose | Write content at path |
| Success | `success=true`, `path`, plus `integration` per [§4.2](#42-content-mutation-integration-metadata-schema-version-2) when hooks run |
| Partial | Write may succeed while accelerate/dataset hooks degrade (see [§9.2](#92-partial-success)) |

Evidence: write integration tests listed in §4.2.

### 5.7 `vfs_copy`, `vfs_move`, `vfs_mkdir`, `vfs_rmdir`, `vfs_ls`, `vfs_stat`

| Operation | Success keys (minimum) |
|---|---|
| `vfs_ls` | `success`, listing keys (`entries` / `items` as implemented) |
| `vfs_stat` | `success`, existence/stat fields (`exists`, etc.) |
| `vfs_mkdir` / `vfs_rmdir` | `success`, `path` |
| `vfs_copy` / `vfs_move` | `success` + `integration.metadata` lineage (`source_operation_id`, `source_cid`, `cid` keys present) |

Evidence: `test_vfs_copy_and_move_emit_lineage_fields_in_metadata_envelope`.

### 5.8 `vfs_sync_to_ipfs`

| | |
|---|---|
| Purpose | Snapshot path tree to content-addressed sync state |
| Success | `success=true`, `path`, `cid`, `entry_count`, `changed` (bool when applicable), `transport_mode`, optional `integration` |
| Side effects | Persists sync state by path and snapshot by CID (atomic write + safe-load) |

Evidence: `test_vfs_sync_roundtrip_for_memory_mount`; durability helpers in `VFSCore`.

### 5.9 `vfs_sync_from_ipfs`

| | |
|---|---|
| Purpose | Restore last snapshot for path into local/memory mounts |
| Success | `success=true`, `path`, `cid`, `restored_count`, `skipped_count`, `policy` ∈ {`overwrite`,`skip`,`strict`}, optional `integration` |
| Failure codes | See [§9.1](#91-stable-failure-codes) |

Evidence: `test_vfs_sync_roundtrip_for_memory_mount`, `test_vfs_sync_from_ipfs_without_prior_sync_is_explicit_failure`, `test_vfs_sync_conflict_policy_strict_fails_on_conflict`, `test_vfs_sync_from_ipfs_strict_rejects_manifest_integrity_mismatch`, `test_vfs_sync_from_ipfs_restores_via_transport_when_snapshot_missing`.

---

## 6. Ordering, atomicity, and mutation sequencing

### 6.1 Ordering guarantees (path plane)

| Scope | Guarantee |
|---|---|
| Single `VFSCore` instance | Mutations on the same process instance are applied in call order for that instance’s in-memory mounts and sync maps; no cross-process linearizability is claimed |
| Mount table | A path resolves against the mount table **after** successful `mount` and **before** successful `unmount` of that point |
| Sync lineage | `sync_from_ipfs(path)` consumes the latest persisted sync state for that path produced by a prior successful `sync_to_ipfs(path)` (or restored state); without state → `missing_sync_state` |
| Integration hooks | Dataset notify then accelerate enrich run **after** the primary mutation path prepares metadata; hook failure does not roll back the write |
| Snapshot retention | Prune order prefers keeping newest snapshots up to max count/age; pruned CIDs drop associated path state |

Evidence: sync round-trip and retention tests; `_run_content_mutation_integrations` ordering in source.

### 6.2 Atomicity units

| Unit | Atomic? | Notes |
|---|---|---|
| Single `vfs_write` / `vfs_copy` / `vfs_move` call | Best-effort single operation | Not a multi-file transaction |
| `sync_to_ipfs` state persistence | Atomic file replace for sync state maps | Corruption-safe load falls back to empty state |
| Multi-file restore under `sync_from_ipfs` | **Not** all-or-nothing across files under `skip`/`overwrite` | Under `strict`, first conflict aborts with `sync_conflict` (partial files may already have been written depending on backend branch—callers **MUST** treat `success=false` as “do not trust full restore”) |
| Journal transaction (separate plane) | Transactional for FS metadata when using filesystem journal | See [`filesystem_journal.md`](filesystem_journal.md); **not** automatically wrapped around every `vfs_*` call |
| WAL operation (separate plane) | Per storage op with retry statuses | Complementary durability; not the same as VFS path transaction |

**Inferred:** Cross-plane atomicity (VFS write **and** journal commit **and** WAL complete **and** pin index update) is **not** a single distributed transaction. Callers that need multi-plane atomicity must sequence operations and define compensating actions. Parent: CONTENT_METADATA_VFS §5.2.

### 6.3 Recommended mutation ordering for durable features

When durability matters and journal/WAL are integrated by the caller:

1. Begin journal transaction (metadata plane intent) when using the journal.
2. Record WAL operation when backend reachability is uncertain.
3. Apply path-plane mutation (`vfs_write` / bucket `add_file` / …).
4. Update retention (pins) if content must survive GC.
5. Commit journal; mark WAL completed.
6. Update rebuildable indexes/caches (non-authoritative).

This ordering is **composition guidance**, not an automatic pipeline for every backend (U-06).

---

## 7. Bucket identity relative to VFS

### 7.1 Definitions

| Term | Meaning |
|---|---|
| **Bucket** | Named storage namespace / organization unit (often under `~/.ipfs_kit/buckets/`) holding objects, optional indexes, and policy |
| **VFS mount** | Runtime attachment of a backend at a path prefix (`mount_point` → `backend`) |
| **VFS path** | Mount-relative location in the path plane; may resolve to a CID or backend key |
| **CID** | Content identity; not a path |

Buckets are **not** backends and **not** mounts. A bucket may be exposed through a VFS manager or mounted into a path namespace; path delete does **not** imply unpin.

### 7.2 Candidate managers (no sole default)

| Manager | Module | Status |
|---|---|---|
| `BucketVFSManager` / `BucketVFS` | `bucket_vfs_manager.py` | Candidate authority for multi-bucket VFS |
| HTTP/API façade | `bucket_vfs_api.py` | REST/direct endpoints over manager |
| `UnifiedBucketInterface` | `unified_bucket_interface.py` | Candidate for cross-backend composition |
| Simplified managers / CLIs | `simple_bucket_*`, `clean_bucket_cli.py`, … | Compatibility |

**Unresolved (U-05):** Production-default manager among candidates remains open. New features SHOULD prefer candidate modules above but MUST NOT document simplified stacks as “the” API.

### 7.3 Identity rules

1. Bucket **name** is the operator-facing identity for bucket APIs (`create_bucket`, `list_buckets`, `add_file`).
2. Object keys inside a bucket are bucket-local; they become VFS paths only after an explicit mount/export/mapping step.
3. CAR export / GraphRAG export from buckets are **derived artifacts**, not authority for live path state.
4. Contract responses for pure bucket manager APIs MAY use their own shapes; when bucket ops are exposed as VFS tools, they **SHOULD** align with §4 (`success`, stable `code`).

Evidence (integration): `tests/test_final_vfs_bucket_integration.py`, `tests/test_unified_bucket_api.py`, `tests/test_bucket_*.py` (default discovery). Architecture: CONTENT_METADATA_VFS §2–3.

---

## 8. Sync durability, transport, and conflict policy

### 8.1 Persisted sync state

`VFSCore` **MUST** persist sync state across process restart using atomic writes and safe-load behavior:

| Store | Keying | On corruption |
|---|---|---|
| Sync state map | By normalized path | Fallback to empty state |
| Snapshots | By CID | Missing snapshot may restore via transport or fail `snapshot_not_found` |

Snapshot retention **MAY** prune by max count and max age (`_prune_sync_snapshots`).

Evidence: `test_vfs_sync_snapshot_retention_prunes_to_max_count`; sync round-trip tests.

### 8.2 Transport (`IPFS_KIT_SYNC_TRANSPORT`)

| Value | Behavior |
|---|---|
| `auto` (default) | Best-effort real transport through datasets manager; fallback deterministic snapshot CID |
| `deterministic` | Deterministic-only snapshot path (no external store) |

When an in-memory/local snapshot is missing after restart, transport restore **MAY** succeed if the datasets manager can `load` the CID.

Evidence: `test_vfs_sync_from_ipfs_restores_via_transport_when_snapshot_missing`.

### 8.3 Conflict policy (`IPFS_KIT_SYNC_CONFLICT_POLICY`)

Default: **`overwrite`**.

| Policy | On local bytes ≠ incoming snapshot bytes |
|---|---|
| `overwrite` | Local content replaced |
| `skip` | Leave local; increment `skipped_count` |
| `strict` | Fail with `code=sync_conflict` |

Unknown policy values **MUST** fail closed at `VFSCore` construction (`ValueError` matching `IPFS_KIT_SYNC_CONFLICT_POLICY`).

Evidence: `test_vfs_startup_rejects_unknown_sync_conflict_policy`, `test_vfs_sync_conflict_policy_strict_fails_on_conflict`, `test_vfs_sync_roundtrip_for_memory_mount`.

### 8.4 Integrity (strict restore)

Under strict policy, manifest/hash integrity failures **MUST** surface as `code=sync_integrity_mismatch` with `error=strict_restore_integrity_mismatch` (or equivalent stable pairing).

Evidence: `test_vfs_sync_from_ipfs_strict_rejects_manifest_integrity_mismatch`.

---

## 9. Failure, partial, and retry semantics

### 9.1 Stable failure codes

| `code` | When | Retry? |
|---|---|---|
| `mount_not_found` | No mount covers path (e.g. sync/read path plane) | No — fix mount table |
| `missing_sync_state` | `sync_from_ipfs` without prior state | No — run `sync_to_ipfs` first or restore state |
| `snapshot_not_found` | State exists but snapshot and transport restore both fail | Maybe — restore transport/data then retry |
| `sync_conflict` | Strict policy; local diverged from incoming | No automatic retry — operator chooses policy/merge |
| `sync_integrity_mismatch` | Strict integrity/manifest check failed | No — restore trusted snapshot |
| `mapping_failed` | Local path mapping failed | No — fix mount/backend config |
| *(message-only)* | Unsupported backend, invalid mount_point (`..`, NUL), etc. | No — fix inputs; prefer future stable codes |

Operations **MUST NOT** return `success=true` for these failure conditions.

### 9.2 Partial success

| Situation | Top-level `success` | Nested signals | Caller action |
|---|---|---|---|
| Write OK; accelerate unavailable | `true` | `accelerate.attempted=false`, `reason=ipfs_accelerate_unavailable` | Optional: install accelerate or ignore |
| Write OK; accelerate timeout | `true` | `accelerate.success=false`, `reason=accelerate_timeout` | Retry enrich only if required; write already durable in path plane |
| Write OK; accelerate disabled (`IPFS_KIT_VFS_ACCELERATE_MODE=disabled`) | `true` | `reason=vfs_accelerate_disabled` | Expected |
| Write OK; datasets owns async enrichment | `true` | `reason=datasets_async_enrichment_owner` | Do not double-run accelerate |
| Sync with `policy=skip` and conflicts | `true` if restore completed with skips | `skipped_count > 0` | Inspect skipped paths if completeness required |
| Sync strict conflict mid-tree | `false` | `code=sync_conflict` | Treat restore as incomplete; reconcile |

Evidence: accelerate/dataset partial tests in `test_vfs_contract_hardening.py`.

### 9.3 Retry semantics

| Layer | Retry model |
|---|---|
| `VFSCore` path ops | **No automatic multi-attempt retry loop** for mount/write/sync failures; return explicit failure |
| Integration hooks | Bounded timeout for accelerate (`_call_with_timeout`); timeout → nested failure, not hang |
| Storage WAL (separate) | `pending` → `processing` → `completed` \| `failed` \| `retrying` with processor drains | See content-metadata guide / WAL modules |
| Filesystem journal (separate) | Incomplete entries are **not** applied on recovery; no silent half-commit of `COMPLETED`-only replay | See [`filesystem_journal.md`](filesystem_journal.md) |

**Rule:** Path-plane contract failures are **terminal for that call**. Retry is a **caller** decision except where a separate durability plane (WAL) owns retry budgets.

### 9.4 Timeouts and fail-closed config

| Control | Behavior |
|---|---|
| Accelerate call timeout | Timed-out enrichment marks nested failure; top-level write may still succeed |
| Unknown `IPFS_KIT_SYNC_CONFLICT_POLICY` | Construction raises `ValueError` |
| Legacy MCP in production without `IPFS_KIT_ALLOW_LEGACY_MCP=1` | Server construction raises `RuntimeError` |

Evidence: `test_vfs_timeout_helper_returns_within_budget`, `test_vfs_write_accelerate_timeout_is_bounded`, production guard test.

---

## 10. Security and trust boundaries

| Rule | Requirement |
|---|---|
| Path traversal | Mount points and resolved paths **MUST NOT** accept `..` or NUL in mount_point validation paths |
| Secrets | Sync lineage, integration metadata, and observability snapshots **MUST NOT** embed raw backend credentials or Iroh tickets; use secret references where configuration requires credentials (see config/trust architecture) |
| Multi-tenant MCP | Auth/RBAC is owned by the MCP control plane; this contract only requires honest `success`/`code` surfaces |
| Cache | Cache hits are rebuildable; never sole authority for authorization decisions |
| Examples | Offline-safe; no undeclared binary downloads |

---

## 11. Relationship to WAL and filesystem journal

| Plane | Owns | Does not own |
|---|---|---|
| **VFS contract (`VFSCore`)** | Path mount table, path I/O shapes, sync lineage, integration envelopes | Backend byte durability across outages |
| **Filesystem journal** | FS metadata transactions, checkpoints, crash rebuild of `fs_state` | Backend upload/pin queues |
| **WAL families** | Storage operation intent and retry across backends | VFS directory atomicity |

They are **complementary**. Enabling one does not imply the others. Full layering discussion: CONTENT_METADATA_VFS §4–5; journal contract: [`filesystem_journal.md`](filesystem_journal.md).

---

## 12. Test map (rank-1 evidence)

Prefer default pytest discovery (`tests/`, `tests/unit/`). Paths under `tests/integration/` are supplementary (`norecursedirs`).

| Concern | Tests |
|---|---|
| Mount, resolve, list, unmount failures | `tests/test_vfs_contract_hardening.py` |
| Mutation integration envelope + partial hooks | same |
| Sync round-trip, conflict, integrity, transport, retention | same |
| Legacy MCP adapter delegation + production block | `tests/test_mcp_vfs_adapter_contract.py` |
| Broader VFS architecture / MCP tools | `tests/test_vfs_*.py`, `tests/test_mcp_vfs_*.py` |
| Bucket + VFS integration | `tests/test_final_vfs_bucket_integration.py`, `tests/test_unified_bucket_api.py`, `tests/test_bucket_*.py` |
| Iroh FS grammar (adjacent) | `tests/test_iroh_filesystem_contract.py` |
| Version lineage | `tests/unit/test_vfs_version_tracking.py` |
| Journal recovery (adjacent plane) | `tests/unit/test_filesystem_journal_comprehensive.py` |

---

## 13. Environment variables (contract-relevant)

| Variable | Default | Effect |
|---|---|---|
| `IPFS_KIT_SYNC_TRANSPORT` | `auto` | `auto` \| `deterministic` transport strategy |
| `IPFS_KIT_SYNC_CONFLICT_POLICY` | `overwrite` | `overwrite` \| `skip` \| `strict`; unknown → fail closed |
| `IPFS_KIT_VFS_ACCELERATE_MODE` | (enabled unless `disabled`) | `disabled` skips accelerate enrichment |
| `IPFS_KIT_MCP_MODE` | (unset) | `production` enables legacy MCP blocks |
| `IPFS_KIT_ALLOW_LEGACY_MCP` | unset | `1` allows legacy MCP servers in production mode |

---

## 14. Related documentation

| Document | Role |
|---|---|
| [`docs/architecture/CONTENT_METADATA_VFS.md`](architecture/CONTENT_METADATA_VFS.md) | Architecture: content, cache, WAL, journal layering |
| [`docs/filesystem_journal.md`](filesystem_journal.md) | Filesystem journal contract and recovery |
| [`docs/iroh/filesystem-contract.md`](iroh/filesystem-contract.md) | Iroh namespace/manifest contract |
| [`docs/architecture/MCP_CONTROL_PLANE.md`](architecture/MCP_CONTROL_PLANE.md) | Packaged MCP++ vs legacy trees |
| [`docs/MCP_SERVER_MIGRATION_GUIDE.md`](MCP_SERVER_MIGRATION_GUIDE.md) | Compatibility migration notes (may lag packaging) |
| [`docs/features/vfs/VFS_MANAGEMENT_CONSOLIDATION.md`](features/vfs/VFS_MANAGEMENT_CONSOLIDATION.md) | User-facing VFS management narrative |
| [`docs/architecture/SOURCE_OF_TRUTH_MAP.md`](architecture/SOURCE_OF_TRUTH_MAP.md) | Evidence map and unresolved decisions |

---

## 15. Change triggers

Update this document when any of the following change:

- `VFSCore` response keys, schema version, or stable `code` vocabulary
- Sync conflict/transport/env semantics
- Packaging MCP entry points or legacy production guards
- Bucket/VFS manager ranking after ADR-0005 / U-05 resolution
- Rank-1 tests in the map above are renamed or removed
