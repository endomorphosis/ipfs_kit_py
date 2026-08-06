# ADR-0005: Content metadata, WAL, and journal durability

> **Document class:** Proposed  
> **Decision status:** Proposed  
> **Date:** 2026-08-03  
> **Last verified:** 2026-08-03  
> **Evidence baseline:** current tree as of 2026-08-03 (`8e57e5c27dc25850dad239e1485dec4ff5d85ce9`); architecture guide KDOC-014 (`CONTENT_METADATA_VFS.md`)  
> **Authors:** KDOC-025 (agent-supervisor implementation)  
> **Confirmation owner:** storage / VFS maintainers (durability SLAs and metadata authority)  
> **Supersedes:** none  
> **Superseded by:** none  
> **Related guides:** [`../CONTENT_METADATA_VFS.md`](../CONTENT_METADATA_VFS.md), [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md), [`../GLOSSARY.md`](../GLOSSARY.md), [`../../VFS_CONTRACT_SPEC.md`](../../VFS_CONTRACT_SPEC.md), [`../../filesystem_journal.md`](../../filesystem_journal.md)  
> **Related conflicts / U-IDs:** U-06, U-07 (also adjacent: U-05 bucket/VFS manager authority, U-02 CLI composition)

Process contract:
[`README.md`](./README.md) · Claim standard:
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)

---

## 1. Context

ipfs-kit stores and serves **content-addressed bytes**, **mutable path namespaces**, **retention metadata (pins)**, **query indexes**, and **durability logs**. These concerns are implemented across parallel modules rather than a single storage engine:

| Concern | Primary modules (observed) |
|---|---|
| Content identity and bytes | Backend adapters, CAR payloads, CID/multihash helpers |
| Path / VFS structure | `bucket_vfs_manager.py`, `vfs_manager.py`, `ipfs_fsspec.py` (`VFSCore`), journal `fs_state` |
| Retention | `pins.py`, `pin_manager.py`, `pin_metadata_index.py` |
| Metadata indexes | `arrow_metadata_index.py`, `metadata_manager.py`, `metadata_sync_handler.py` |
| Storage operation intent (WAL) | `storage_wal.py`, `wal.py`, `enhanced_wal_durability.py`, `car_wal_manager.py`, `pin_wal.py` |
| Filesystem journal | `filesystem_journal.py`, `fs_journal_integration.py`, `fs_journal_backends.py`, `fs_journal_replication.py` |
| Cache | `tiered_cache_manager.py`, `cache/`, ARC helpers |

Without a recorded decision, guides risk:

1. Treating **Arrow/Parquet indexes** as pinset or content authority (U-07).  
2. Claiming a **universal WAL + journal mandate** for every backend write when integrations are optional (U-06).  
3. Conflating **WAL** (backend operation queue) with **filesystem journal** (path-metadata transactions).  
4. Omitting **failure recovery order** across journal, WAL, CAR, pins, and rebuildable indexes.

This ADR records **observed design choices** with confidence labels, states **durability/consistency consequences** and **failure recovery**, lists **alternatives**, and keeps open owner decisions **Proposed** until confirmation.

**In scope:**

- Separation of immutable content-addressed facts vs mutable path/manifest state vs rebuildable indexes  
- WAL intent logging families and CAR packaging role  
- Filesystem journal history, checkpoints, and recovery semantics  
- Authoritative vs rebuildable classification and cross-plane consistency limits  
- Failure recovery ordering and operational consequences  
- Alternatives considered for durability layering and metadata authority  

**Out of scope:**

- Backend plugin registry vs live adapters (ADR-0002 / KDOC-013)  
- MCP runtime authority (ADR-0003)  
- Cluster control-plane / CRDT state identity (ADR-0008)  
- Network transport defaults Kubo vs Iroh (ADR-0006)  
- Selecting a single production bucket/VFS manager (U-05; architecture guide only)  
- Secret/config directory composition (ADR-0007)  

---

## 2. Current behavior (evidence, not aspiration)

### 2.1 Surface inventory

| Surface / path | Observed role | Evidence (source, test, packaging) | Status label |
|---|---|---|---|
| Content bytes + CID | Payload truth and cryptographic identity | Backend adapters; CAR import/export; glossary CID; VFS path→CID maps | Active / authoritative |
| `FilesystemJournal` / `FilesystemJournalManager` | Transactional FS metadata journal; checkpoint + `recover()` | `ipfs_kit_py/filesystem_journal.py`; `tests/unit/test_filesystem_journal_comprehensive.py` | Active candidate durability |
| `StorageWriteAheadLog` | Multi-backend op queue; Parquet partitions under kit WAL path | `ipfs_kit_py/storage_wal.py`; CLI `wal` helpers | Active candidate durability |
| `WAL` (`wal.py`) | JSON-oriented WAL; stalled-op recovery | `ipfs_kit_py/wal.py` | Active compatibility family |
| `DurableWAL` | Segmented log, fsync modes, sequence checkpoints, integrity recovery | `ipfs_kit_py/enhanced_wal_durability.py`; `tests/unit/test_enhanced_wal_durability.py` | Active enhanced durability |
| `CARWALManager` | Stage content as CAR/IPLD (JSON fallback without IPLD deps) | `ipfs_kit_py/car_wal_manager.py`; CAR tool tests | Active content staging |
| `ArrowMetadataIndex` (+ anyio twin) | Columnar content metadata store + optional pubsub sync | `arrow_metadata_index.py`, `metadata_sync_handler.py`; datasets metadata contract tests | Active secondary index (U-07 open) |
| Pins / pin metadata | Retention intent separate from path maps | `pins.py`, `pin_manager.py`, `pin_metadata_index.py` | Active retention plane |
| `TieredCacheManager` / ARC / VFS cache | Read-path acceleration only | `tiered_cache_manager.py`, `cache/` | Rebuildable / non-authority |
| `VFSCore` sync lineage | Path sync state, snapshots by CID, conflict policy env | `ipfs_fsspec.py`; `docs/VFS_CONTRACT_SPEC.md`; `tests/test_vfs_contract_hardening.py` | Active contract surface |
| Dual/parallel WAL & bucket stacks | Multiple overlapping implementations | Map §3; CONTENT_METADATA_VFS §2.2 | Compatibility / unresolved (U-05, U-06) |

### 2.2 Observed state-kind separation

| Kind | Examples | Authoritative? | Rebuildable? |
|---|---|---|---|
| **Content bytes** | Blocks in IPFS/Iroh/S3/local; CAR payloads | **Yes** | Via re-fetch / re-add from origin |
| **Content identity** | CID, multihash | **Yes** (content-addressed stores) | Recomputed from bytes |
| **Retention intent** | Pins, pin metadata | **Yes** for “must keep” once recorded in pin plane | Pin *index tables* may rebuild from pinset + enrichment |
| **Path / FS structure** | VFS path→CID, bucket entries, journal `fs_state` | **Yes** after committed journal/VFS state | Checkpoints + completed journal entries rebuild `fs_state` |
| **Operation intent log** | WAL ops, DurableWAL segments, CAR WAL entries | **Yes until** completed/archived | N/A (the log *is* the intent authority) |
| **Metadata index** | Arrow/Parquet, DuckDB views | **Usually secondary** (U-07 open) | **Yes** — rebuild from content + pins + VFS indexes |
| **Cache** | Memory/disk/mmap/VFS cache | **No** | **Yes** always on miss |
| **Sync lineage** | VFS sync state, snapshot CIDs, `operation_id` chain | **Yes** once persisted | Partially (re-export if transport allows) |

### 2.3 Observed recovery and consistency behavior

**Journal recovery (implemented):** `FilesystemJournal.recover` loads the newest valid checkpoint (checksum-aware), then applies journal files with timestamp ≥ checkpoint, oldest first. Only **completed** journal entries are applied; incomplete transactions are skipped. Recovery can rebuild `fs_state` from checkpoint + completed history.

**WAL recovery (implemented, multi-family):**

- `DurableWAL.recover()`: from checkpoint sequence, scan segments with checksum verification; caller re-applies recovered ops.  
- `StorageWriteAheadLog`: background processor drains `pending`/`retrying`; partitions under `~/.ipfs_kit/wal/`.  
- `WAL.recover_stalled_operations`: stuck `processing` ops.  
- `CARWALManager.process_all_wal_entries`: reprocess unprocessed `wal_*.car`, move to `processed/`.

**Cross-plane atomicity (observed absence):** There is no single distributed transaction manager that atomically commits journal + WAL + pin index + backend + cache together. Callers compose planes and use compensating actions.

**VFS sync conflict policy (implemented):** `IPFS_KIT_SYNC_CONFLICT_POLICY` ∈ {`overwrite` (default), `skip`, `strict`}; unknown values fail closed at startup. Evidence: contract + `tests/test_vfs_contract_hardening.py`.

**Cache invariant (implemented practice):** Cache hits accelerate reads; correctness after miss comes from backend/content plane. Cache is never the recovery source of truth.

### 2.4 Narrative summary

The tree implements **layered best-effort composition**: content-addressed bytes and CIDs are payload identity; paths and pins are separate mutable concerns; WAL families record *backend operation intent*; the filesystem journal records *path-metadata transactions*; Arrow indexes and caches are **rebuildable** projections. Multiple WAL implementations coexist without a single enforced stack for all mutating VFS backends (U-06). Arrow authority remains an open owner decision (U-07); guides treat indexes as secondary/rebuildable by default inference.

---

## 3. Decision

**Status:** Proposed  

### 3.1 Decision statement

Until maintainer confirmation promotes the open mandates (U-06, U-07), this ADR **records and freezes the following design posture** as the documentation and integration baseline. Items marked **Accepted (observed invariant)** are strongly evidenced and may be cited as current behavior. Items marked **Proposed (owner decision)** must not be cited as production SLA or sole authority without confirmation.

#### D1 — Separate state kinds by authority and rebuildability (**Accepted observed invariant**)

1. **Immutable content-addressed facts:** bytes behind a CID (or equivalent content hash) are payload truth; identity is recomputable from bytes under the same codec/hash parameters.  
2. **Mutable path / manifest / FS structure:** path→CID maps and journal `fs_state` are authoritative for the *namespace* after commit, not for content bytes.  
3. **Retention (pins):** pin records are authoritative for “must keep” policy in the pin plane; deleting a path does **not** imply unpin.  
4. **Rebuildable indexes:** Arrow/Parquet content metadata, DuckDB views, and similar projections are **secondary** unless U-07 is confirmed otherwise; loss degrades query features, not payload identity, when content and pins remain.  
5. **Caches:** always rebuildable; never authoritative.

#### D2 — WAL records storage operation intent; journal records FS metadata history (**Accepted observed invariant**)

| Log | Records | Does not replace |
|---|---|---|
| WAL families | Intended backend ops (add, pin, upload, …) and status | Path namespace or content bytes |
| Filesystem journal | FS structure ops (create, delete, rename, write metadata, …) and transactions | Backend reachability queue |
| CAR WAL | Content staged as CAR/IPLD for processing | Completed backend pinset |

WAL and journal are **complementary**, not interchangeable (see glossary WAL vs journal).

#### D3 — Durability layering is optional composition today; mandate is **Proposed** (U-06)

**Current behavior (Accepted as description):** Journal and WAL integrations are **hooks**, not a single mandatory pipeline for every backend write.

**Proposed owner decision (not accepted):** Whether `storage_wal` + `filesystem_journal` (or a named equivalent composition) is **required** for all mutating VFS ops, or some backends remain exempt.

#### D4 — Metadata index role is secondary/rebuildable by default; sole authority is **Proposed** (U-07)

**Working documentation rule (Inferred → Proposed for confirmation):** Treat Arrow metadata as **rebuildable from** content bytes, pins, and VFS indexes. Do not use Arrow alone as GC/delete authority.

**Proposed owner decision:** Confirm whether Arrow is authoritative, secondary, or rebuildable-from-pins/content for production SLAs.

#### D5 — Failure recovery is per-plane with a recommended order (**Accepted observed recovery model**)

Recommended crash recovery order (operational, not a global 2PC):

1. `FilesystemJournal.recover` → restore path metadata (`fs_state`).  
2. DurableWAL / Storage WAL drain / CAR `process_all` → finish intent logs.  
3. Reconcile pins vs path maps (policy/operator; not fully automatic).  
4. **Rebuild** Arrow/VFS indexes if checksum or drift detected.  
5. Warm caches opportunistically (never required for correctness).

#### D6 — Reject global cross-plane ACID as the implemented model (**Accepted by absence of enforcement**)

The system does **not** implement one ACID transaction across cache, index, pin, WAL, journal, and backend. Document **layered composition + per-plane recovery** instead.

### 3.2 Options (required: Proposed status and material alternatives)

| Option | Summary | Fit / risk |
|---|---|---|
| **A — Recorded layered model (this ADR)** | Keep multi-plane separation; document rebuild rules; leave U-06/U-07 Proposed | Matches tree; needs owner follow-up for SLAs |
| **B — Mandate WAL + journal for all mutating VFS ops** | Single durability pipeline required in all write paths | Stronger consistency story; large migration; breaks optional backends |
| **C — Promote Arrow as authoritative metadata store** | Indexes become source of truth for queries and some retention | Performance for analytics; risk of drift from pinset/content if rebuild not enforced |
| **D — Collapse to one WAL implementation** | Deprecate `wal.py` / CAR / DurableWAL overlap | Reduces operator confusion; high compatibility cost |
| **Status quo undocumented** | Leave only guide prose without ADR | Re-litigation of authority; agents invent SLAs |

**Selected option (if any):** **Option A** for documentation and integration guidance. Options B–D remain available owner choices; none is Accepted as production policy in this record.

---

## 4. Rationale (confidence-labeled)

### 4.1 Content-addressed identity vs mutable paths

**Accepted:** Content-addressed identity (CID) separates immutable payload identity from mutable path names. Paths are a mutable namespace; CIDs are cryptographic content identity. Evidence: VFS path→CID maps; pin-by-CID APIs; `GLOSSARY.md` CID entry; `CONTENT_METADATA_VFS.md` §4–§5.

**Inferred:** Parallel simple JSON catalogs (`ContentManager`, simple `PinManager`) exist for lightweight kit-side catalogs and dashboards, not as substitutes for IPFS/Iroh blockstore or pinset authority.

### 4.2 WAL intent logging

**Accepted:** Write-ahead intent logging decouples “user requested op” from “backend currently reachable,” enabling retry when IPFS/S3/backends are down. Evidence: `StorageWriteAheadLog` pending processor; `WAL` stalled-op recovery; `DurableWAL` segments/fsync; durability unit tests.

**Inferred:** Multiple WAL families exist to cover different durability/format goals (JSON simplicity, Parquet analytics partitions, fsync durability, IPLD/CAR affinity) rather than a single finished abstraction—hence U-06 remains open.

**Unknown:** Whether maintainers intend long-term consolidation to one WAL family — unknown / maintainer confirmation needed.

### 4.3 Filesystem journal

**Accepted:** Journal checkpoints plus ordered replay rebuild path metadata after crash without applying incomplete transactions. Evidence: `FilesystemJournal.recover`; `tests/unit/test_filesystem_journal_comprehensive.py`; journal module design (transactions, `JournalEntryStatus`, checkpoints).

**Accepted:** Journal completed entries are the only ones applied on recovery (invariant in architecture guide §5.1).

### 4.4 Rebuildable indexes and cache

**Inferred:** Arrow metadata is optimized for query/analytics and cluster sync, not as the pinset of record—hence **rebuildable secondary** classification pending U-07 confirmation.

**Accepted:** Cache is never authority; miss path reloads from backend/content plane. Evidence: architecture guide invariants; cache manager role as acceleration tier.

**Proposed:** Documented rebuild procedure (from content + pins + VFS indexes) becomes the operator SLA for metadata index loss once U-07 is confirmed as secondary/rebuildable.

### 4.5 CAR packaging

**Accepted:** CAR is a portable content-addressed archive used for staging/import/export and WAL content packaging, not a separate storage-backend type. Evidence: `CARWALManager`; CAR tool tests; glossary CAR entry.

### 4.6 Consistency limits

**Accepted:** Cross-layer atomicity is not enforced by a single transaction manager; recovery is per-plane. Evidence: separate APIs and recovery entry points; absence of global coordinator in focused tests.

**Accepted:** VFS sync conflict policies are explicit and fail-closed for unknown values. Evidence: `IPFS_KIT_SYNC_CONFLICT_POLICY`; `tests/test_vfs_contract_hardening.py`.

**Unknown:** Global multi-writer locking across processes/hosts for bucket directories and journal files beyond per-process `RLock` — unknown / maintainer confirmation needed. Do not assume cross-host linearizability without cluster coordination (ADR-0008).

### 4.7 Durability mandate (U-06)

**Proposed:** Owners should decide and publish whether WAL + journal are required for every mutating VFS backend or which backends are exempt, with test gates.

**Unknown:** Historical product reason for leaving integrations optional — unknown / maintainer confirmation needed.

---

## 5. Evidence

| Rank | Claim | Citation |
|---|---|---|
| 1 | Journal recover skips non-completed entries; checkpoint + replay rebuilds `fs_state` | `ipfs_kit_py/filesystem_journal.py` (`recover`, `create_checkpoint`); `tests/unit/test_filesystem_journal_comprehensive.py` |
| 1 | DurableWAL checkpoint + recovery with integrity handling | `ipfs_kit_py/enhanced_wal_durability.py`; `tests/unit/test_enhanced_wal_durability.py` (`test_recovery`, `test_checkpointing`) |
| 1 | VFS sync conflict policy and lineage fields | `docs/VFS_CONTRACT_SPEC.md`; `tests/test_vfs_contract_hardening.py`; `ipfs_kit_py/ipfs_fsspec.py` |
| 1 | CAR tooling and import paths exist | `tests/test_car_and_files_tools.py`, `tests/test_car_import_to_bucket.py` |
| 1 | Pin metadata index tests | `tests/test_enhanced_pin_metadata.py`, `tests/unit/test_pin_metadata_index.py` |
| 1 | Metadata index contract tests | `tests/test_datasets_metadata_index_contract.py` |
| 2 | Packaged CLI exposes `bucket`, `vfs`, `wal`, `pin`, `journal` composition | `ipfs_kit_py/cli.py` (FastCLI mounts); `unified_cli_dispatcher.py` |
| 3 | WAL vs journal public distinction | Module docstrings; `docs/architecture/GLOSSARY.md` |
| 3 | Storage WAL / journal / Arrow class contracts | `StorageWriteAheadLog`, `FilesystemJournal`, `ArrowMetadataIndex`, `CARWALManager` public APIs |
| 4 | Evidence map U-06 / U-07 and recovery gaps | `docs/architecture/SOURCE_OF_TRUTH_MAP.md` §3, aggregate unresolved list |
| 5 | End-to-end authority matrix and recovery order | `docs/architecture/CONTENT_METADATA_VFS.md` §§4–8, Appendix B, §14.4 |
| 5 | Older journal narrative | `docs/filesystem_journal.md` (supporting; prefer architecture guide for layering) |

**Evidence that is explicitly insufficient for Accepted status on U-06/U-07:**

- Guide inference alone that “indexes are secondary” without maintainer SLA.  
- Presence of four WAL families without tests proving a single required stack for all backends.  
- Integration tests under `tests/integration/` (excluded from default pytest discovery) as sole proof of production mandate.

---

## 6. Consequences

### 6.1 Positive

- **Clear authority model:** Operators and agents can classify state as content, path, pin, intent log, rebuildable index, or cache before designing recovery.  
- **Honest dual-WAL documentation:** Overlapping WAL families are named as compatibility reality, not hidden under a fictional single stack.  
- **Actionable recovery:** Per-plane recovery order reduces “restore everything from cache” mistakes.  
- **Safe index evolution:** Treating Arrow as rebuildable encourages schema backfill from authority instead of silent sole-source deletes.  
- **Glossary alignment:** WAL ≠ journal ≠ receipt ≠ pin is enforceable in reviews.

### 6.2 Negative / costs

- **No single durability SLA** until U-06 is confirmed—callers may omit journal/WAL and still appear “working” on happy paths.  
- **Operator complexity:** Multiple WAL directories (`wal/partitions`, segments, `wal/car`) require care not to mix families in one directory without a composition layer.  
- **Possible metadata drift:** If indexes are updated best-effort, query results can lag pins/content until rebuild.  
- **Incomplete automation:** Pin vs path reconciliation after crash is not fully automatic.  
- **Test discovery gap:** Deep WAL/journal integration tests live under `tests/integration/` and are excluded from default pytest—rank-1 claims lean on unit/comprehensive tests.

### 6.3 Durability and consistency consequences (by design choice)

| Design choice | Durability consequence | Consistency consequence |
|---|---|---|
| CID / content bytes as authority | Losing last replica of bytes is permanent data loss | All paths/pins referring to that CID are dangling until re-add |
| Journal for path metadata | Committed `fs_state` survives crash via checkpoint + completed entries | Incomplete transactions never become visible namespace state |
| WAL for backend ops | Intent survives backend outages; retry/drain restores progress | WAL “completed” does not by itself update path maps or pins |
| CAR staging | Content can be reprocessed after crash before backend success | Unprocessed CARs are pending intent, not published pinset |
| Rebuildable Arrow indexes | Index loss is performance/feature degradation if authority remains | Queries may be incomplete until rebuild; not GC authority by default |
| Cache non-authority | Cache wipe is safe | Stale cache possible until invalidation/eviction; miss path corrects |
| No global cross-plane ACID | Each plane recovers independently | Temporary divergence across journal/WAL/pins/indexes after crash |

### 6.4 Failure recovery

| Failure | Recovery posture | Notes |
|---|---|---|
| Process crash mid-journal transaction | `FilesystemJournal.recover`; skip incomplete | Then create fresh checkpoint after clean recovery |
| Process crash mid-WAL | DurableWAL `recover` / storage WAL drain / stalled-op recovery | Re-apply ops to backends as status requires |
| Crash after CAR write, before process | `process_all_wal_entries` / per-entry process | Confirm move to `processed/` |
| Backend unavailable during add/pin | WAL `pending`/`retrying`; health monitor may gate | Drain when healthy |
| Checkpoint corruption | Try older checkpoints; fall back to empty + journals | Errors list populated |
| Metadata index drift or loss | **Rebuild** from pins/content/VFS indexes | Do not treat incomplete queries as missing content |
| Cache loss / eviction | Fetch from backend | Normal |
| Sync without prior state | Fail with missing-sync-state class | Run `sync_to` first or restore state |
| Sync conflict (strict) | `code=sync_conflict` | Operator chooses overwrite/skip or manual merge |
| Optional deps missing (PyArrow/IPLD) | Degraded WAL/index modes; JSON mock CAR | Install extras; features remain optional |

**Recommended recovery order** remains §3.1 D5. Do not rebuild indexes *before* journal/WAL recovery when path or intent logs still hold newer truth.

### 6.5 Migration and compatibility

- New features should declare which plane is authoritative for new state (guide §9.3 integration order).  
- Prefer **not** mixing `wal.py`, `storage_wal.py`, `DurableWAL`, and CAR WAL records in one directory without a composition layer.  
- Historical/simple bucket managers remain non-default (U-05); this ADR does not pick a winner.  
- Promoting this ADR’s U-06/U-07 Proposed clauses to Accepted requires maintainer confirmation **and** evidence (tests and/or explicit policy).  
- Architecture guides must cite this ADR with **status-honest** language (`Proposed` for mandates; `Accepted observed` for invariants).

### 6.6 Security and trust

- Local kit state under `~/.ipfs_kit/` may contain paths, metadata, and cached content—protect host ACLs; do not commit kit state into source control.  
- Backend credentials belong in the config/secret plane (ADR-0007), not as long-lived secrets inside WAL operation parameters.  
- Pubsub metadata sync (`MetadataSyncHandler`) crosses a trust domain; auth is a cluster concern.  
- Credentials: none in this ADR; examples use placeholders only.

### 6.7 Testing and verification

Tests that encode or protect the decision surface:

| Concern | Focused tests (prefer default discovery) |
|---|---|
| Filesystem journal recovery | `tests/unit/test_filesystem_journal_comprehensive.py` |
| DurableWAL recovery / checkpoints | `tests/unit/test_enhanced_wal_durability.py` |
| VFS contract, conflict, sync lineage | `tests/test_vfs_contract_hardening.py` |
| VFS version tracking | `tests/unit/test_vfs_version_tracking.py` |
| Pin metadata | `tests/test_enhanced_pin_metadata.py`, `tests/unit/test_pin_metadata_index.py` |
| Metadata index contract | `tests/test_datasets_metadata_index_contract.py` |
| CAR tools | `tests/test_car_and_files_tools.py`, `tests/test_car_import_to_bucket.py` |
| Journal MCP tools (unit) | `tests/unit/test_fs_journal_mcp_tools_comprehensive.py` |

Supplementary (non-default discovery): `tests/integration/test_filesystem_journal.py`, `tests/integration/test_fs_journal_*.py`, `tests/integration/test_wal_*.py`.

Commands that re-check this ADR body:

```bash
test -s docs/architecture/decisions/0005-content-metadata-and-durability.md \
  && rg -q "rebuild" docs/architecture/decisions/0005-content-metadata-and-durability.md
```

---

## 7. Alternatives considered

| Alternative | Why considered | Why rejected / deferred | Confidence |
|---|---|---|---|
| Global ACID across cache, index, pin, WAL, journal, backend | Familiar DB mental model | Not implemented; would require new coordinator and rewrite of write paths | Accepted (rejected by absence of enforcement) |
| Treat Arrow metadata as sole GC/delete authority | Simplifies query-driven cleanup | Risk of permanent loss if index drifts; contradicts rebuildable posture pending U-07 | Proposed (deferred; dangerous without confirmation) |
| Mandate single WAL + journal for every backend now | Stronger durability story | Breaks optional/simple paths; no consolidated implementation or default-discovery tests proving universal wiring | Proposed (deferred as U-06) |
| Collapse all WAL families into one module immediately | Reduce operator confusion | High compatibility cost; distinct formats (JSON, Parquet, segments, CAR) serve different goals | Inferred (deferred) |
| Document status quo only in guides, no ADR | Faster authoring | Re-litigates authority; agents invent SLAs | Accepted (rejected for this program) |
| Make cache authoritative for reads after first fill | Latency | Violates content-addressed correctness and recovery | Accepted (rejected) |
| Equate WAL with filesystem journal | Simpler vocabulary | Different concerns, APIs, recovery semantics | Accepted (rejected) |
| Do nothing / leave U-06 U-07 invisible | Avoid ADR work | Map and guides already flag them; silence causes incorrect “Accepted” citations | Accepted (rejected) |

At least one alternative (status quo undocumented) is explicitly rejected above.

---

## 8. Unknowns and owner confirmation

| Field | Value |
|---|---|
| **Confirmation owner** | Storage / VFS maintainers (durability and metadata authority); documentation maintainers for guide cross-links |
| **Confirmation question** | (1) Is WAL + filesystem journal **required** for all mutating VFS/backend write paths, or which backends are exempt (U-06)? (2) Is Arrow metadata **authoritative**, **secondary**, or **rebuildable-from-pins/content** for production SLAs (U-07)? |
| **What “Accepted” requires** | Explicit maintainer statement on U-06 and U-07 **and** rank-1–4 evidence (required wiring tests and/or documented SLA); update §3 status and this section |
| **Blocking for** | Production durability SLAs; any guide language that declares universal WAL/journal mandate or Arrow as sole authority; operator runbooks that promise cross-plane ACID |
| **Related U-IDs / conflicts** | **U-06**, **U-07**; adjacent **U-05** (bucket/VFS manager), **U-02** (CLI composition) |

**Open unknowns:**

1. Universal durability layering mandate (U-06) — unknown / maintainer confirmation needed.  
2. Arrow metadata authority class (U-07) — unknown / maintainer confirmation needed.  
3. Long-term consolidation plan for WAL families — unknown / maintainer confirmation needed.  
4. Cross-process / cross-host locking guarantees for journal and bucket dirs — unknown / maintainer confirmation needed.  
5. Why simple JSON content/pin managers remain alongside enhanced indexes — unknown / maintainer confirmation needed.  

---

## 9. Supersession and relationships

| Relation | ADR / doc |
|---|---|
| Supersedes | none |
| Superseded by | none |
| Related ADRs | ADR-0002 (backend registry); ADR-0003 (MCP tools may expose WAL/journal); ADR-0006 (transports that carry content); ADR-0007 (state dirs / secrets); ADR-0008 (cluster metadata replication / CRDT) |
| Architecture guides | [`../CONTENT_METADATA_VFS.md`](../CONTENT_METADATA_VFS.md) (KDOC-014), [`../SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md), [`../GLOSSARY.md`](../GLOSSARY.md) |
| Contracts | [`../../VFS_CONTRACT_SPEC.md`](../../VFS_CONTRACT_SPEC.md), [`../../filesystem_journal.md`](../../filesystem_journal.md) |
| Source-of-truth map | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §3 (U-06, U-07) |

---

## 10. Follow-up actions

| Action | Owner | Notes |
|---|---|---|
| Confirm U-06 durability mandate (required vs optional per backend) | Storage / VFS maintainers | May promote §3 D3 Proposed → Accepted or Rejected with exemptions table |
| Confirm U-07 Arrow authority class | Storage / metadata maintainers | If secondary/rebuildable, document rebuild recipes as SLA |
| Add default-discovery tests for any mandated composition path | Engineering | Do not rely only on `tests/integration/` if mandate is Accepted |
| Update `CONTENT_METADATA_VFS.md` unresolved section when this ADR is confirmed | Docs (separate task) | Keep status-honest citations while Proposed |
| Index owner updates ADR registry row for 0005 | Framework / KDOC-020 owners | Body authors do not edit `decisions/README.md` |
| Consider WAL family consolidation design | Engineering | Optional follow-on ADR if Option D is chosen |
| Clarify multi-writer locking story | Storage maintainers | May interact with ADR-0008 |

---

## 11. Review checklist (authors)

- [x] Filename is `0005-content-metadata-and-durability.md` (not left as 0000)
- [x] Banner **Decision status** matches §3 **Status** (`Proposed`)
- [x] **Current behavior** is evidence-backed and separate from the proposal
- [x] No present-tense “the system requires WAL+journal everywhere” for Proposed-only mandate
- [x] Every material *why* uses **Accepted / Proposed / Inferred / Unknown**
- [x] No Inferred or Unknown claim is written as Accepted history
- [x] Evidence table prefers ranks 1–4 for Accepted claims
- [x] Alternatives include status quo and explicit rejects
- [x] Confirmation owner and question filled (Proposed)
- [x] No secrets, live tokens, or host-specific credential paths
- [x] `docs/architecture/decisions/README.md` was **not** edited by this task
- [x] Related architecture guide already points at this ADR slot with unresolved honesty

---

## Appendix A — Design-choice confidence matrix

Quick scan of observed choices required by KDOC-025 acceptance (consequences, recovery, alternatives, and confidence per choice).

| # | Observed design choice | Confidence | Durability / consistency | Failure recovery | Alternative (summary) |
|---|---|---|---|---|---|
| 1 | Content bytes + CID are payload identity | **Accepted** | Permanent loss if last replica gone | Re-fetch/re-add from origin | Path-only identity (rejected) |
| 2 | Path/namespace separate from content | **Accepted** | Path delete ≠ content delete | Journal rebuild of `fs_state` | Collapse path into CID metadata only (deferred) |
| 3 | Pins separate from path maps | **Accepted** | Retention independent of VFS path | Reconcile pins vs paths after crash | Auto-unpin on path delete (rejected as default) |
| 4 | WAL = backend op intent log | **Accepted** | Survives backend outage | Drain / recover stalled / segment recover | Sync-only writes with no intent log (weaker) |
| 5 | Multiple WAL families coexist | **Accepted** (behavior) / **Proposed** (consolidation) | Format-specific durability | Per-family recovery APIs | Single WAL module (deferred) |
| 6 | Filesystem journal = FS metadata transactions | **Accepted** | Committed txn durability; incomplete skipped | Checkpoint + completed replay | Journal-only without WAL (incomplete for backend ops) |
| 7 | CAR packages content for staging | **Accepted** | Pending CAR is intent, not pinset | `process_all_wal_entries` | Always direct backend write only (less offline-friendly) |
| 8 | Arrow/metadata indexes rebuildable secondary | **Inferred** / **Proposed** (U-07) | Index loss ≠ content loss if authority remains | Rebuild from content+pins+VFS | Arrow as sole authority (deferred/dangerous) |
| 9 | Cache never authority | **Accepted** | Cache wipe safe | Miss → backend | Authoritative cache (rejected) |
| 10 | No global cross-plane ACID | **Accepted** | Temporary multi-plane divergence possible | Ordered per-plane recovery | Distributed 2PC (not implemented) |
| 11 | VFS sync conflict policies fail-closed | **Accepted** | Explicit overwrite/skip/strict | Operator policy on conflict | Silent last-writer without policy (rejected) |
| 12 | Universal WAL+journal mandate | **Proposed** (U-06 open) | SLA undefined until confirmed | N/A until mandate exists | Optional hooks (current behavior) |

---

## Appendix B — Glossary anchors (non-normative)

| Term | ADR usage |
|---|---|
| **Authoritative state** | Recovery source of truth for a concern if lost cannot be reconstructed without external input |
| **Rebuildable state** | Reconstructible from authority (indexes, caches); loss degrades features/performance |
| **WAL** | Storage operation intent queue across backends |
| **Journal** | Filesystem metadata/structure transaction log |
| **CAR** | Content-addressable archive packaging for blocks/roots |
| **CID** | Content identifier for content-addressed bytes |

Full definitions: [`../GLOSSARY.md`](../GLOSSARY.md).
