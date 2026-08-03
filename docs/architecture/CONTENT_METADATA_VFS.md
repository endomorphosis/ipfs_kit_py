# Content, metadata, cache, bucket, VFS, WAL, and journal architecture

| Field | Value |
|---|---|
| Document class | **Canonical** |
| Status | active |
| Last verified | 2026-08-03 |
| Tree baseline | `a8d75c1e7b15152a49341e03d922402c4e11d09c` |
| Owner / task | KDOC-014 |
| Goal id | KDOC-G022 |
| Track | arch-storage |
| Evidence map | [`SOURCE_OF_TRUTH_MAP.md`](SOURCE_OF_TRUTH_MAP.md) §3 |
| Related contracts | [`docs/VFS_CONTRACT_SPEC.md`](../VFS_CONTRACT_SPEC.md), [`docs/iroh/filesystem-contract.md`](../iroh/filesystem-contract.md) |
| Related ADRs | Planned: `docs/architecture/decisions/0005-content-metadata-and-durability.md` (not yet authored) |
| Change triggers | See [§12 Change triggers](#12-change-triggers-and-last-verified-baseline) |

This guide traces **content bytes**, **content identity (CIDs)**, **metadata and indexes**, **caches**, **buckets/VFS**, and **durability layers (WAL, CAR WAL, filesystem journal)** through write, read, mutate, delete, and recovery paths. It does **not** select a single production bucket manager or declare Arrow metadata authoritative when the tree still has parallel stacks—those remain [unresolved owner decisions](#11-unresolved-owner-decisions).

Vocabulary: see [`GLOSSARY.md`](GLOSSARY.md) for CID, VFS, WAL, and journal terms.

---

## 1. Scope and explicit non-goals

### 1.1 Scope

| In scope | Why |
|---|---|
| Content identity vs payload vs path mapping | Prevent conflating bytes, CIDs, and VFS paths |
| Pins and pin/metadata indexes | Retention and query surfaces over content |
| Arrow/Parquet metadata indexes and sync handlers | Secondary/rebuildable metadata plane |
| Tiered/ARC cache and VFS-local cache | Read-path acceleration (not authority) |
| Bucket managers and VFS managers (candidate + compatibility) | Storage organization and path APIs |
| fsspec surfaces (`VFSCore`, Iroh packaging entries, in-tree IPFS/enhanced) | Operator and library access paths |
| Storage WAL, base WAL, enhanced DurableWAL, CAR WAL | Intent logs for backend operations and content staging |
| Filesystem journal, journal backends, journal replication | FS metadata atomicity and multi-node metadata copy |
| Ordering, atomicity, conflict policy, sync lineage, recovery | KDOC-014 acceptance criteria |
| Focused tests under default pytest discovery | Rank-1 evidence |

### 1.2 Non-goals

| Out of scope | Owner / pointer |
|---|---|
| Backend *configuration* plugins vs live adapters | KDOC-013 → `STORAGE_BACKEND_SYSTEM.md` |
| Cluster control-plane authority and CRDT state identity | KDOC-015 → `CLUSTER_COORDINATION.md` |
| Kubo/Iroh/libp2p transport security and lifecycle | KDOC-016 → `NETWORK_TRANSPORTS.md` |
| MCP tool registry layout and control plane | KDOC-017 → `MCP_CONTROL_PLANE.md` |
| Resolving U-05/U-06/U-07 by inventing an ADR outcome | ADR track (KDOC-G030 / ADR 0005) |
| Exhaustive method inventories | Generated/reference docs; this guide teaches structure |
| Editing protected program-control files | Operator policy |

---

## 2. Supported surfaces and compatibility status

Status labels follow the program evidence map ([`SOURCE_OF_TRUTH_MAP.md`](SOURCE_OF_TRUTH_MAP.md) §3). **Candidate authority** means “looks primary from static inspection,” not “accepted ADR.”

### 2.1 Candidate authority (prefer for new work *until* ADR 0005)

| Surface | Module path(s) | Role |
|---|---|---|
| Bucket VFS core | `ipfs_kit_py/bucket_vfs_manager.py`, `bucket_vfs_api.py`, `bucket_manager.py` | Multi-bucket VFS with UnixFS-style layout, optional Arrow/DuckDB indexes |
| Unified bucket interface | `ipfs_kit_py/unified_bucket_interface.py`, `unified_bucket_cli.py` | Cross-backend bucket + pin composition under `~/.ipfs_kit/buckets/` |
| Shared VFS manager | `ipfs_kit_py/vfs_manager.py`, `vfs_bucket_manager.py`, `vfs_version_tracker.py` | Shared ops, version chains, Parquet VFS index helpers |
| Contract VFS core | `ipfs_kit_py/ipfs_fsspec.py` (`VFSCore`, `vfs_*` helpers) | Normative request/response shapes in `docs/VFS_CONTRACT_SPEC.md` |
| Packaged fsspec | `ipfs_kit_py/iroh_fsspec.py` (`IrohFileSystem`) | Only fsspec protocols declared in `pyproject.toml`: `iroh`, `iroh+blob` |
| Metadata index | `ipfs_kit_py/arrow_metadata_index.py` (+ `arrow_metadata_index_anyio.py`), `metadata_manager.py`, `metadata_sync_handler.py` | Columnar metadata store + pubsub sync |
| Pins | `ipfs_kit_py/pins.py`, `pin_metadata_index.py`, `pin_manager.py`, `simple_pin_manager.py`, `cli/enhanced_pin_cli.py` | Pin retention + enhanced pin metadata |
| Content catalog (local JSON) | `ipfs_kit_py/content_manager.py` | Lightweight `~/.ipfs_kit/content.json` catalog (not IPFS block store) |
| Storage WAL (Arrow/Parquet partitions) | `ipfs_kit_py/storage_wal.py` (`StorageWriteAheadLog`) | Queued multi-backend ops with background processor |
| Base WAL | `ipfs_kit_py/wal.py` (`WAL`) | JSON-oriented WAL with stalled-op recovery |
| Enhanced durability WAL | `ipfs_kit_py/enhanced_wal_durability.py` (`DurableWAL`) | fsync modes, segments, checkpoints, integrity recovery |
| CAR WAL | `ipfs_kit_py/car_wal_manager.py` (`CARWALManager`) | Content staged as CAR/IPLD (JSON fallback without IPLD deps) |
| Filesystem journal | `ipfs_kit_py/filesystem_journal.py` (`FilesystemJournal`, `FilesystemJournalManager`) | Transactional FS metadata journal + checkpoint recovery |
| Journal backends / replication | `ipfs_kit_py/fs_journal_backends.py`, `fs_journal_replication.py`, `fs_journal_integration.py` | Tiered journal backends; metadata replication with LWW default |
| Tiered cache | `ipfs_kit_py/tiered_cache_manager.py`, `ipfs_kit_py/cache/`, `arc_cache.py`, `cache_manager.py` | Hierarchical content cache (memory/disk/mmap/Parquet CID cache) |

### 2.2 Compatibility / historical / dual paths (do not treat as equal defaults)

| Path | Status note |
|---|---|
| `simple_bucket_manager.py`, `simplified_bucket_manager.py`, `simple_bucket_cli.py`, `clean_bucket_cli.py` | Simplified / alternate bucket stacks |
| `enhanced_bucket_index.py` / `enhanced_bucket_index_fixed.py` | Parallel index implementations |
| Multiple VFS CLI modules (`bucket_vfs_cli.py`, `vfs_version_cli.py`, `cli/bucket_cli.py`) | Not all mounted on packaged `ipfs-kit` FastCLI |
| `enhanced_fsspec.py` runtime registration of `ipfs`/`filecoin`/`storacha`/`synapse` | Import-time registration; **not** packaging entry points (**C-FSSPEC** / U-17) |
| `ipfs_fsspec.py` IPFS filesystem classes | In-tree; not declared in `pyproject.toml` fsspec entry points |
| Empty/stub pin index paths referenced by JIT | Must not be documented as production defaults |
| Dual WAL families (`wal.py` vs `storage_wal.py` vs `DurableWAL` vs CAR) | Overlapping intent; no single enforced stack (U-06) |
| Integration-only WAL/journal tests under `tests/integration/` | Excluded from default pytest discovery (`pytest.ini` `norecursedirs`) |

### 2.3 Operator entry points (CLI composition)

Packaged CLI is `ipfs-kit` → `ipfs_kit_py.cli:sync_main`. FastCLI selectively mounts unified helpers for `bucket`, `vfs`, `wal`, `pin`, `journal` (and others). Full subcommand families also live on `unified_cli_dispatcher.py`. CLI composition authority remains open (**U-02**); this guide only records that storage-data-plane verbs exist on those surfaces.

---

## 3. Component ownership and source-of-truth paths

### 3.1 Layered ownership

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  Access surfaces: CLI / MCP tools / Python API / fsspec                 │
├─────────────────────────────────────────────────────────────────────────┤
│  Path plane: VFSCore, BucketVFS, UnifiedBucketInterface, VFS managers   │
├─────────────────────────────────────────────────────────────────────────┤
│  Identity & retention: CIDs, pins, pin metadata indexes                 │
├─────────────────────────────────────────────────────────────────────────┤
│  Metadata plane: ArrowMetadataIndex, MetadataManager, sync handler      │
├─────────────────────────────────────────────────────────────────────────┤
│  Cache plane: TieredCacheManager / ARC / VFSCacheManager (rebuildable)  │
├─────────────────────────────────────────────────────────────────────────┤
│  Durability plane: WAL intent logs · CAR staging · FS journal           │
├─────────────────────────────────────────────────────────────────────────┤
│  Backend adapters (bytes sink/source) — see STORAGE_BACKEND_SYSTEM.md   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Ownership table

| Concern | Primary modules | Local durable paths (typical) |
|---|---|---|
| Content catalog | `content_manager.py` | `~/.ipfs_kit/content.json` |
| Simple pins | `pin_manager.py` | `~/.ipfs_kit/pins.json` |
| Enhanced pins / pin metadata | `pins.py`, `pin_metadata_index.py` | Parquet/Arrow under kit state (implementation-specific) |
| Buckets | `bucket_vfs_manager.py`, `unified_bucket_interface.py` | `~/.ipfs_kit/buckets/` (unified layout: `buckets/<name>/` or backend-prefixed variants) |
| VFS version index | `vfs_version_tracker.py` | `~/.ipfs_kit/` Parquet/JSON version chain + optional CAR snapshots |
| Storage WAL partitions | `storage_wal.py` | `~/.ipfs_kit/wal/partitions/`, `…/archives/` |
| Base WAL | `wal.py` | Configurable `base_path` (docs often `~/.ipfs_kit/wal`) |
| DurableWAL | `enhanced_wal_durability.py` | `{base_path}/segments/`, `{base_path}/checkpoints/` |
| CAR WAL | `car_wal_manager.py` | default `~/.ipfs_kit/wal/car/`, `…/processed/` |
| Filesystem journal | `filesystem_journal.py` | journal dir + `checkpoints/` (caller-configured; often `~/.ipfs_kit/journal`) |
| Metadata replication checkpoints | `fs_journal_replication.py` | `{base_path}/checkpoints/` |
| Arrow metadata | `arrow_metadata_index.py` | Parquet partitions under configured index path |
| Tiered cache | `tiered_cache_manager.py` | memory + configured disk cache dir |

**Inferred:** Local JSON managers (`ContentManager`, simple `PinManager`) are lightweight kit-side catalogs and are **not** substitutes for IPFS pinset or blockstore authority. Evidence: small JSON load/save implementations without backend adapters.

---

## 4. Data flow and control flow

### 4.1 Conceptual state kinds

Distinguish these kinds on every path (acceptance criterion: **authoritative versus rebuildable**).

| Kind | Examples | Authoritative? | Rebuildable? |
|---|---|---|---|
| **Content bytes** | Blocks in IPFS/Iroh/S3/local FS; CAR payloads | **Yes** — bytes behind a CID (or backend key) are the payload truth | Via re-fetch / re-add from origin |
| **Content identity** | CID, multihash | **Yes** for content-addressed stores | Recomputed from bytes |
| **Retention intent** | Pins, pin metadata | **Yes** for “must keep” policy once recorded in pin plane | Pin index tables may be rebuilt from pinset + enrichment sources |
| **Path / FS structure** | VFS path → CID map, bucket file entries, `fs_state` in journal | **Yes** for the path namespace once committed | Journal checkpoints + completed journal entries rebuild `fs_state` |
| **Operation intent log** | WAL ops, DurableWAL segments, CAR WAL entries | **Yes** until completed/archived | N/A (is the log) |
| **Metadata index** | Arrow/Parquet content metadata, DuckDB views | **Usually secondary** | **Yes** from content + pins + VFS indexes (U-07 open) |
| **Cache entries** | ARC memory, disk cache, mmap, VFSCacheManager | **No** | **Yes** always; miss path reloads from authority |
| **Sync lineage / snapshots** | VFS sync state by path, snapshots by CID, operation_id chain | **Yes** for restore lineage once persisted | Snapshots may be re-derived if transport can re-export |

### 4.2 Write path (happy path)

```text
Caller (CLI/API/MCP/fsspec)
    │
    ▼
Path plane (VFS / Bucket write)
    │  1) optional: journal begin + journal entry (metadata plane intent)
    │  2) optional: WAL add_operation (backend op intent)
    ▼
Bytes sink (backend adapter / memory mount / local bucket dir)
    │  content-address → CID
    ▼
Retention (pin add) ──► pin metadata index update
    │
    ▼
Rebuildable indexes: Arrow metadata · VFS Parquet index · version tracker
    │
    ▼
Caches: put into TieredCacheManager / VFS cache (non-authoritative)
    │
    ▼
Commit journal transaction · mark WAL op completed · archive/process CAR
```

**Accepted (implementation + tests):** VFS mutation responses under the VFS contract include integration metadata (`schema_version`, `operation_id`, path, optional lineage fields). Evidence: `docs/VFS_CONTRACT_SPEC.md`; `tests/test_vfs_contract_hardening.py`.

**Inferred:** Not every backend write path wires journal + storage WAL + CAR together; integrations are optional hooks rather than a single mandatory pipeline (U-06).

### 4.3 Read path

```text
Caller read(path or cid)
    │
    ├─► VFS resolve path → CID / backend key
    │
    ▼
Cache get (memory → disk → mmap / VFS cache)
    │ hit: return bytes (rebuildable)
    │ miss
    ▼
Backend / blockstore / bucket storage get
    │
    ▼
Optional: populate cache; record access stats for ARC promotion
```

### 4.4 Mutate / rename / delete

| Operation class | Path plane | Durability | Index impact |
|---|---|---|---|
| Overwrite write | VFS write / bucket `add_file` | Journal WRITE/TRUNCATE; WAL ADD/UPLOAD | Path→CID updates; old CID may remain pinned until GC policy |
| Rename/move | VFS move; journal RENAME | Journal transaction | Path map only if CID unchanged |
| Delete/rm | VFS rmdir/rm; bucket delete | Journal DELETE; WAL RM/UNPIN | Remove path entry; pin removal is separate retention decision |
| Unpin | pin APIs | WAL UNPIN | Pin metadata removal; content may remain if other pins/refs exist |

### 4.5 Sync lineage (VFS ↔ content-addressed snapshot)

`VFSCore` in `ipfs_kit_py/ipfs_fsspec.py` implements durable sync state:

| Direction | Method | Lineage produced / consumed |
|---|---|---|
| Local → IPFS snapshot | `sync_to_ipfs(path)` | Persists sync state by path; creates snapshot keyed by CID; optional transport via datasets manager when `IPFS_KIT_SYNC_TRANSPORT=auto` |
| Snapshot → local | `sync_from_ipfs(path)` | Loads sync state; restores from snapshot or transport; applies **conflict policy** |

Lineage fields (contract SHOULD/MUST): `cid`, `source_cid`, `source_operation_id`, `operation_id`, `schema_version`.  
Evidence: `docs/VFS_CONTRACT_SPEC.md` (Sync Durability + Global Response Contract); `tests/test_vfs_contract_hardening.py`.

Transport modes (`IPFS_KIT_SYNC_TRANSPORT`):

| Value | Behavior |
|---|---|
| `auto` (default) | Best-effort real transport; fallback deterministic snapshot |
| `deterministic` | Deterministic-only snapshot path |

### 4.6 Version lineage (VFS version tracker)

`VFSVersionTracker` builds Git-like version chains using CIDs, optional CAR snapshots, and Parquet/JSON indexes under the kit root. This is a **version history lineage** orthogonal to per-path sync state, but both use content addressing as the link key.

Evidence: `ipfs_kit_py/vfs_version_tracker.py`; `tests/unit/test_vfs_version_tracking.py`.

---

## 5. Invariants, ordering, atomicity, and conflict policy

### 5.1 Invariants (must hold)

1. **Cache is never authority.** A cache hit may return stale data only if invalidation/eviction policy allowed it; correctness after miss must come from backend/content plane.
2. **Path maps and pin records are distinct.** Deleting a path does not imply unpin unless an explicit retention API is invoked.
3. **Journal completed entries are the only ones applied on recovery.** Incomplete transactions are not applied as committed FS state (`FilesystemJournal.recover` skips non-`COMPLETED` entries).
4. **WAL pending ops remain pending until backend success or permanent failure/retry budget exhaustion.** Status transitions: `pending` → `processing` → `completed` | `failed` | `retrying`.
5. **VFS contract responses carry `success` and stable failure `code`s** for integration surfaces under `VFSCore` / `vfs_*`.
6. **Unknown sync conflict policy fails closed at startup** (`ValueError` for invalid `IPFS_KIT_SYNC_CONFLICT_POLICY`).

### 5.2 Ordering and atomicity

| Mechanism | Ordering guarantee | Atomicity unit |
|---|---|---|
| `FilesystemJournal` transactions | Ops within a transaction ordered; commit marks transaction complete; checkpoints capture consistent `fs_state` | `begin_transaction` → ops → `commit_transaction` / `rollback_transaction` |
| `FilesystemJournal.recover` | Newest valid checkpoint first; then journal files with timestamp ≥ checkpoint, oldest first; completed entries applied in file order | Recovery rebuilds `fs_state`; incomplete entries skipped |
| `StorageWriteAheadLog` | Background processor drains pending ops; partitions are Parquet append-oriented batches | Single operation record; not multi-op FS transactions |
| `WAL` (`wal.py`) | Sequential processing; `recover_stalled_operations` for stuck work | Per operation |
| `DurableWAL` | Sequence numbers; recovery from checkpoint sequence then segment scan with checksum verification | Segment write + optional fsync (`always` / `batch` / `periodic`) |
| `CARWALManager` | Timestamped CAR files; `process_all_wal_entries` processes pending CARs; moves to `processed/` | Per CAR content entry |
| `MetadataReplicationManager` | Checkpoint interval; progressive tier copy; peer replication | Checkpoint + journal entry replication; default conflict resolution **LWW** |

**Inferred:** Cross-layer atomicity (journal commit **and** WAL complete **and** pin index update as one transaction) is **not** enforced by a single distributed transaction manager in-tree. Callers that need multi-plane atomicity must sequence operations and define compensating actions.

### 5.3 Conflict policy

#### VFS sync-from conflict policy

Environment: `IPFS_KIT_SYNC_CONFLICT_POLICY` (default **`overwrite`**).

| Policy | On local ≠ incoming | Evidence |
|---|---|---|
| `overwrite` | Local content replaced by snapshot/transport | `VFSCore._should_overwrite_content`; contract |
| `skip` | Conflicting files left unchanged; counted in `skipped_count` | same |
| `strict` | Fail with `code=sync_conflict` (or integrity mismatch codes under strict restore) | `tests/test_vfs_contract_hardening.py` |

Related failure codes: `missing_sync_state`, `snapshot_not_found`, `sync_conflict`, `strict_restore_integrity_mismatch`.

#### Metadata replication conflict policy

`MetadataReplicationManager` default config includes `"conflict_resolution": "lww"` (last-write-wins). Vector-clock / CRDT helpers are imported from cluster sync modules when available; detailed cluster CRDT authority is owned by KDOC-015.

#### Concurrent writers

**Unknown:** Global multi-writer locking across processes for bucket directories and journal files is unknown / maintainer confirmation needed beyond per-process locks (`threading.RLock` in journal/WAL). Do not assume cross-host linearizability without cluster coordination.

---

## 6. Process, async, and lifecycle boundaries

| Component | Concurrency model | Lifecycle notes |
|---|---|---|
| `StorageWriteAheadLog` | Background thread + queue; `RLock` | Starts processing on init; stop via internal stop event |
| `DurableWAL` | Thread-safe segment writes; optional batch thread behavior for fsync modes | Recovery on demand via `recover()` |
| `FilesystemJournal` | `RLock`; optional auto-recovery on startup when configured | `atexit` hooks may flush; checkpoints periodic/manual |
| `MetadataReplicationManager` | Checkpoint background thread; peer/tier replication | `auto_recovery` config default true |
| `BucketVFSManager` / `UnifiedBucketInterface` / `VFSVersionTracker` | **async** (`anyio` / `async def` APIs) | Callers must own event loop (CLI/MCP adapters bridge sync↔async) |
| `VFSCore` | Sync Python API | Sync state persisted with atomic write + safe-load fallback |
| `ArrowMetadataIndex` | Sync (+ `arrow_metadata_index_anyio` twin) | Optional deps: PyArrow |
| `TieredCacheManager` | Sync; prefetch may spawn helper threads | Prefetch threads cleaned opportunistically |
| `MetadataSyncHandler` | Thread for periodic sync; pubsub callbacks | Requires IPFS client pubsub |

Optional dependency gates: PyArrow (`ARROW_AVAILABLE`), DuckDB, IPLD (`dag_cbor`/`multiformats`), `ipfs_datasets_py`. Missing deps degrade to limited modes (JSON fallback for CAR WAL; limited storage WAL without Parquet).

---

## 7. Trust boundaries and sensitive-data handling

| Boundary | Guidance |
|---|---|
| Local kit state under `~/.ipfs_kit/` | May contain path names, metadata, and cached content; protect host ACLs; do not commit kit state into source control |
| Backend credentials | Live in backend config plane (`backend_manager` / secure config)—not in WAL operation parameters as long-lived secrets. Prefer secret references (see future CONFIGURATION_STATE_AND_TRUST guide) |
| Pubsub metadata sync | `MetadataSyncHandler` propagates index messages; treat cluster/pubsub as a trust domain boundary (auth is cluster concern) |
| Multi-tenant MCP | VFS/bucket tools inherit MCP auth; this guide does not define RBAC |
| Examples | Use placeholders only; offline defaults; set `IPFS_KIT_AUTO_INSTALL_BINARIES=0` for doc validation |

**Accepted:** Production VFS contract runtime guidance says production MCP must use `unified_mcp_server` and blocks legacy MCP unless `IPFS_KIT_ALLOW_LEGACY_MCP=1`. Evidence: `docs/VFS_CONTRACT_SPEC.md` Runtime Policy. Full MCP authority remains U-11 / ADR 0003.

---

## 8. Expected failures, degraded modes, observability, and Recovery

### 8.1 Failure modes by plane

| Plane | Failure | Observed behavior | Recovery posture |
|---|---|---|---|
| Backend unavailable | IPFS/S3 down during add/pin | WAL records `pending`/`retrying`; `BackendHealthMonitor` may gate processing | Drain WAL when healthy; `WAL.recover_stalled_operations` |
| Process crash mid-write | Journal transaction open | On restart, `FilesystemJournal.recover`: load checkpoint, replay completed journal entries only | Incomplete txn not applied |
| Process crash mid-WAL | Op logged but not completed | DurableWAL `recover()` from checkpoint sequence + segment scan; checksum mismatch skips/repairs path | Re-process recovered ops |
| CAR WAL unprocessed | Crash after CAR write | `list_wal_entries` / `process_all_wal_entries` reprocesses `wal_*.car` | Move to `processed/` after success |
| Checkpoint corruption | Bad journal checkpoint checksum | Skip checkpoint; try older; errors list populated | Fall back to earlier checkpoint or empty + journals |
| Sync without prior state | `sync_from_ipfs` without `sync_to_ipfs` | Explicit failure (`missing_sync_state` class) | Run sync_to first or restore state |
| Sync conflict (strict) | Local diverged | `code=sync_conflict` | Operator chooses overwrite/skip or manual merge |
| Strict integrity mismatch | Manifest hash tampered | `strict_restore_integrity_mismatch` | Restore from trusted snapshot |
| Optional deps missing | No PyArrow / IPLD | Limited WAL; JSON mock CAR; degraded indexes | Install extras; features remain optional |
| Cache miss / eviction | Cold content | Fetch from backend | Normal; not an error |
| Metadata index drift | Index missing entries | Queries incomplete | Rebuild from pins/content (rebuildable plane) |

### 8.2 Recovery procedures (operational summary)

#### Filesystem journal Recovery

1. Ensure journal and checkpoint directories are intact.
2. Construct `FilesystemJournal` / manager with same base path; enable `auto_recovery` or call `recover()`.
3. Confirm result counters: `checkpoints_loaded`, `journals_processed`, `entries_applied`, `errors`.
4. Optionally `create_checkpoint` after clean recovery.

Evidence: `FilesystemJournal.recover` in `ipfs_kit_py/filesystem_journal.py`; `tests/unit/test_filesystem_journal_comprehensive.py`.

#### DurableWAL Recovery

1. Instantiate `DurableWAL(base_path=…)`.
2. Call `recover()` or `recover(from_checkpoint=…)`.
3. Re-apply returned operations to backends as required by the caller.
4. Verify `fsync_mode` and checkpoint stats after healthy operation.

Evidence: `tests/unit/test_enhanced_wal_durability.py` (`test_recovery`, `test_checkpointing`).

#### Storage WAL / base WAL Recovery

1. Restart process with same `~/.ipfs_kit/wal` partitions path.
2. Allow `process_pending_operations` / background processor to drain.
3. Use status queries (`get_operations_by_status`) for `pending`/`failed`.
4. For base `WAL`, call `recover_stalled_operations` when ops stick in `processing`.

#### CAR WAL Recovery

1. Inspect `~/.ipfs_kit/wal/car/` for unprocessed `wal_*.car`.
2. `process_all_wal_entries()` or `process_wal_entry` per file.
3. Confirm files under `processed/`.

Evidence: `ipfs_kit_py/car_wal_manager.py`; CAR tool tests `tests/test_car_and_files_tools.py`, `tests/test_car_import_to_bucket.py`.

#### Metadata replication Recovery

1. `MetadataReplicationManager.recover_from_checkpoint(checkpoint_id=None)` loads distributed/local checkpoints.
2. Peer gossip and progressive tier replication repopulate redundancy.

Evidence: `ipfs_kit_py/fs_journal_replication.py`; related `tests/test_vfs_replication.py`.

#### VFS sync Recovery

1. Persist sync state is loaded with corruption-safe fallback to empty.
2. Re-run `sync_from_ipfs` with appropriate conflict policy.
3. If snapshot missing, transport restore path may still succeed when transport data exists.

Evidence: `tests/test_vfs_contract_hardening.py`.

### 8.3 Observability

| Signal source | What it covers |
|---|---|
| WAL status fields / partitions | Pending depth, failures, retries |
| DurableWAL stats | Checkpoints, fsync mode, sequence |
| Journal recovery result dict | Applied/skipped/error lists |
| TieredCacheManager `get_stats` | Hit rates, tier sizes, prefetch metrics |
| WAL telemetry stack | Optional REST/metrics (see `docs/telemetry_api.md` / reference WAL telemetry docs)—control-plane adjacent |
| VFS contract responses | `success`, `code`, lineage fields, `cached` on reads |

---

## 9. Extension points and safe modification guidance

### 9.1 Safe extension points

| Extension | How | Safety rules |
|---|---|---|
| New VFS backend mount type | Register via `VFSBackendRegistry` / backend adapter; expose through `VFSCore.mount` | Do not bypass conflict policy or sync-state atomic write helpers |
| New bucket type | Extend `BucketType` / backend enum paths carefully; prefer existing manager APIs | Keep path→CID index updates and optional journal hooks |
| New WAL operation type | Extend `OperationType` in the **same** WAL family you integrate with | Persist schema-compatible records; handle unknown types on recovery as failed/skip with log |
| New journal op type | Extend `JournalOperationType` **and** `_apply_journal_entry` | Recovery must understand historical ops; version journal entries if needed |
| Metadata fields | Add Arrow schema columns via index evolution helpers | Treat index as rebuildable; provide backfill from authority |
| Cache tier / prefetch strategy | `TieredCacheManager` config; `cache/read_ahead_prefetching.py` strategies | Cache-only; never make eviction authoritative |
| CAR content staging | `CARWALManager.store_content_to_wal` | Preserve processed/ vs pending directory invariant |
| Replication policy | Config keys on `MetadataReplicationManager` (`conflict_resolution`, tier progression) | Document deviation from LWW; tests required |

### 9.2 Unsafe modifications (avoid)

- Writing content only to cache without backend/journal when durability is required.
- Treating Arrow metadata or Parquet VFS indexes as sole source of truth for deletes/GC.
- Silently changing default `IPFS_KIT_SYNC_CONFLICT_POLICY` semantics without updating contract tests.
- Mixing `wal.py`, `storage_wal.py`, `DurableWAL`, and CAR WAL records in one directory without a composition layer.
- Promoting simplified/historical bucket managers to “the” API without resolving U-05.

### 9.3 Recommended integration order for a new mutating feature

1. Define authority: which plane is source of truth for the new state?
2. Persist intent (journal and/or WAL) **before** external side effects when crash safety matters.
3. Apply backend mutation.
4. Update retention (pins) if content must survive GC.
5. Update rebuildable indexes and invalidate/update caches.
6. Add focused tests for success, crash/recovery, and conflict paths.

---

## 10. Design rationale, trade-offs, and rejected alternatives

**Accepted:** Content-addressed identity (CID) separates immutable payload identity from mutable path names. Paths are a mutable namespace; CIDs are cryptographic content identity. Evidence: VFS path→CID maps; pin-by-CID APIs; glossary CID entry.

**Accepted:** Write-ahead intent logging (WAL) decouples “user requested op” from “backend currently reachable,” enabling retry when IPFS/S3 are down. Evidence: `StorageWriteAheadLog` docstring and pending processor; `WAL` module docstring; durability tests.

**Accepted:** Filesystem journal checkpoints + ordered replay rebuild path metadata after crash without replaying incomplete transactions. Evidence: `FilesystemJournal.recover` implementation; unit tests.

**Accepted:** VFS sync conflict policies are explicit and fail-closed for unknown values; strict mode surfaces machine-readable `sync_conflict`. Evidence: contract + `tests/test_vfs_contract_hardening.py`.

**Inferred:** Multiple WAL implementations exist to cover different durability/format goals (JSON simplicity, Parquet analytics partitions, fsync durability, IPLD/CAR affinity) rather than a single finished abstraction. No accepted ADR yet consolidates them (U-06).

**Inferred:** Arrow metadata is optimized for query/analytics and cluster sync, not as the pinset of record—hence rebuildable classification pending U-07 confirmation.

**Proposed:** ADR 0005 (`content-metadata-and-durability`) should pick: (1) required durability layering per mutating API, (2) metadata authority vs rebuild rules, (3) single recommended bucket/VFS manager for new features. Status: **not accepted** in-tree as of this baseline.

**Unknown:** Why simple JSON `ContentManager` / `PinManager` remain alongside enhanced pin indexes is unknown / maintainer confirmation needed (compat for dashboards vs permanent dual stack).

**Rejected alternative (observed by absence of enforcement):** “Every write is one global ACID transaction across cache, index, pin, WAL, and backend.” The tree implements **layered best-effort composition** with per-plane recovery instead.

---

## 11. Unresolved owner decisions

Carried from [`SOURCE_OF_TRUTH_MAP.md`](SOURCE_OF_TRUTH_MAP.md) aggregate list; this guide must not invent outcomes.

| ID | Topic | Impact on this guide |
|---|---|---|
| **U-05** | Bucket/VFS manager authority among parallel stacks | Readers must use “candidate” language; new features should not assume a sole API |
| **U-06** | WAL/journal durability requirements per backend | Some backends may omit journal/WAL; not documented as universal mandate |
| **U-07** | Arrow metadata authoritative vs rebuildable | Guide treats indexes as **rebuildable secondary** by default inference |
| **U-17** | fsspec supported protocol set beyond packaged Iroh entries | Only `iroh` / `iroh+blob` are packaging-backed; other protocols need import-side registration |
| **U-02** | CLI composition authority | Which CLI path is operator-default for `bucket`/`vfs`/`wal`/`journal` |

---

## 12. Tests and fixtures that verify the behavior

Prefer **default pytest discovery** (`tests/`, `tests/unit/`). Paths under `tests/integration/` are supplementary and excluded by `norecursedirs`.

### 12.1 Test map (rank-1 evidence)

| Concern | Focused tests |
|---|---|
| VFS contract, conflict policy, sync lineage, Recovery of sync state | `tests/test_vfs_contract_hardening.py` |
| VFS architecture / mounts | `tests/test_vfs_architecture.py`, `tests/test_vfs_*.py` |
| Bucket + VFS integration | `tests/test_final_vfs_bucket_integration.py`, `tests/test_unified_bucket_api.py`, `tests/test_bucket_*.py` |
| Iroh filesystem contract | `tests/test_iroh_filesystem_contract.py`, `tests/test_iroh_fsspec_*.py`, `tests/test_iroh_vfs_integration.py` |
| VFS version tracking | `tests/unit/test_vfs_version_tracking.py` |
| VFS replication | `tests/test_vfs_replication.py` |
| Filesystem journal (comprehensive unit) | `tests/unit/test_filesystem_journal_comprehensive.py` |
| DurableWAL checkpoint + Recovery | `tests/unit/test_enhanced_wal_durability.py` |
| CAR tooling | `tests/test_car_and_files_tools.py`, `tests/test_car_import_to_bucket.py`, `tests/test_phase3_car_files.py` |
| Pin metadata | `tests/test_enhanced_pin_metadata.py`, `tests/unit/test_pin_metadata_index.py`, `tests/unit/test_duckdb_pin_metadata.py` |
| Metadata index contract | `tests/test_datasets_metadata_index_contract.py` |
| Journal MCP tools (unit) | `tests/unit/test_fs_journal_mcp_tools_comprehensive.py` |

### 12.2 Supplementary (non-default discovery)

- `tests/integration/test_filesystem_journal.py`
- `tests/integration/test_fs_journal_*.py`
- `tests/integration/test_wal_*.py`

Use these for deeper end-to-end scenarios when explicitly selected; architecture claims in this guide are grounded first in default-discovery tests above.

### 12.3 Offline validation for this document

```bash
test -s docs/architecture/CONTENT_METADATA_VFS.md \
  && rg -q "Recovery" docs/architecture/CONTENT_METADATA_VFS.md
```

Broader claim re-check (optional):

```bash
# Candidate modules still present
rg -n "class (StorageWriteAheadLog|FilesystemJournal|DurableWAL|CARWALManager|VFSCore|TieredCacheManager|ArrowMetadataIndex|BucketVFSManager)" \
  ipfs_kit_py/storage_wal.py ipfs_kit_py/filesystem_journal.py \
  ipfs_kit_py/enhanced_wal_durability.py ipfs_kit_py/car_wal_manager.py \
  ipfs_kit_py/ipfs_fsspec.py ipfs_kit_py/tiered_cache_manager.py \
  ipfs_kit_py/arrow_metadata_index.py ipfs_kit_py/bucket_vfs_manager.py

# Conflict policy still fail-closed
rg -n "IPFS_KIT_SYNC_CONFLICT_POLICY|sync_conflict" ipfs_kit_py/ipfs_fsspec.py tests/test_vfs_contract_hardening.py
```

---

## 13. Change triggers and last-verified baseline

Re-verify this guide when any of the following change:

| Trigger | Sections to re-check |
|---|---|
| `FilesystemJournal.recover` / checkpoint format | §5, §8 Recovery |
| WAL family APIs or default paths (`storage_wal`, `wal`, `DurableWAL`, CAR) | §3–§6, §8–§9 |
| `VFSCore` sync/conflict/env vars or `docs/VFS_CONTRACT_SPEC.md` | §4.5, §5.3, §8 |
| Bucket/VFS manager consolidation or deletion of parallel stacks | §2, §11 U-05 |
| Arrow metadata schema or sync handler semantics | §4.1, U-07 |
| Tiered cache eviction/promotion policy | §4.3, §5.1 invariant 1 |
| Packaging fsspec entry points | §2.2 U-17 |
| Removal/rename of focused tests listed in §12 | Re-evidence or downgrade claims |
| Acceptance of ADR 0005 | Rewrite unresolved sections as Accepted |

| Baseline field | Value |
|---|---|
| Last verified | 2026-08-03 |
| Tree baseline | `a8d75c1e7b15152a49341e03d922402c4e11d09c` |
| Evidence sources | Static inspection of modules in §2–§3; default-discovery tests in §12; `SOURCE_OF_TRUTH_MAP.md` §3; `VFS_CONTRACT_SPEC.md` |

---

## 14. End-to-end path cheat sheet

### 14.1 Add file to bucket and make it durable (recommended composition)

```text
1. BucketVFS / UnifiedBucketInterface.add_*  → local path + content
2. Content-address → CID (backend or multihash helpers)
3. Optional: DurableWAL / StorageWriteAheadLog.add_operation(ADD/UPLOAD)
4. Optional: FilesystemJournal WRITE/CREATE within transaction → commit
5. Pin CID if retention required
6. Update Arrow / VFS Parquet indexes (rebuildable)
7. TieredCacheManager.put(cid, bytes) (optional acceleration)
```

### 14.2 Read by path

```text
1. Resolve path → CID (VFS/bucket index; journal fs_state if used)
2. TieredCacheManager.get / VFS cache
3. On miss: backend get → fill cache
```

### 14.3 Delete path without losing shared content

```text
1. Journal DELETE + remove path map entry
2. Do not UNPIN if other paths/pins reference CID
3. Invalidate cache entries for path; CID cache may remain until unpin/GC
```

### 14.4 Crash Recovery order of operations

```text
1. FilesystemJournal.recover  → restore path metadata (fs_state)
2. DurableWAL.recover / Storage WAL drain / CAR process_all → finish intent logs
3. Reconcile pins vs path maps (operator/policy; not fully automatic)
4. Rebuild Arrow/VFS indexes if checksum or drift detected
5. Warm caches opportunistically (never required for correctness)
```

---

## 15. Related documents

| Document | Relationship |
|---|---|
| [`SOURCE_OF_TRUTH_MAP.md`](SOURCE_OF_TRUTH_MAP.md) §3 | Evidence map this guide expands |
| [`docs/VFS_CONTRACT_SPEC.md`](../VFS_CONTRACT_SPEC.md) | Normative VFS request/response + sync policy |
| [`docs/iroh/filesystem-contract.md`](../iroh/filesystem-contract.md) | Iroh VFS normative contract |
| [`docs/filesystem_journal.md`](../filesystem_journal.md) | Older operational journal narrative (prefer this architecture guide for authority layering) |
| [`docs/metadata_replication.md`](../metadata_replication.md) | Replication usage notes |
| [`docs/reference/tiered_cache.md`](../reference/tiered_cache.md) | Cache reference detail |
| [`docs/reference/metadata_index.md`](../reference/metadata_index.md) | Metadata index reference |
| [`docs/simplified_bucket_architecture.md`](../simplified_bucket_architecture.md) | Design notes; not sole production authority |
| Future `STORAGE_BACKEND_SYSTEM.md` | Backend plugins vs adapters (KDOC-013) |
| Future ADR 0005 | Durability and metadata authority decisions |

---

## Appendix A: Operation type quick reference

### Storage / base WAL (`OperationType`)

`ADD`, `GET`, `PIN`, `UNPIN`, `RM`, (`CAT`, `LIST`, `MKDIR`, `COPY`, `MOVE`, `UPLOAD`, `DOWNLOAD` in storage WAL), `BACKUP`/`RESTORE` (base WAL), `CUSTOM`.

### Journal (`JournalOperationType`)

`CREATE`, `DELETE`, `RENAME`, `WRITE`, `TRUNCATE`, `METADATA`, `CHECKPOINT`, plus mount-oriented types in higher-level docs (`MOUNT`/`UNMOUNT` where integrated).

### WAL / journal status

| WAL (`OperationStatus`) | Journal (`JournalEntryStatus`) |
|---|---|
| `pending`, `processing`, `completed`, `failed`, `retrying` | Includes completed (applied on Recovery); non-completed skipped |

### DurableWAL fsync modes

| Mode | Semantics |
|---|---|
| `always` | fsync on critical writes (strongest durability, higher latency) |
| `batch` | fsync on batch boundaries |
| `periodic` | fsync on timer/interval policy |

---

## Appendix B: Authoritative vs rebuildable checklist (acceptance)

| State | Authoritative | Rebuildable | Primary modules | Primary tests |
|---|---|---|---|---|
| Content bytes | Yes | From origin | backends, CAR payloads | CAR + backend tests |
| CID identity | Yes | From bytes | multiformats / IPFS add | Iroh/IPFS contract tests |
| Pins / retention | Yes (pin plane) | Index from pinset | `pins.py`, `pin_manager.py` | pin metadata unit tests |
| VFS path map / fs_state | Yes (after commit) | From journal+checkpoints | `filesystem_journal.py`, VFS managers | journal unit + VFS tests |
| WAL / CAR intent | Yes until done | N/A | `storage_wal.py`, `wal.py`, `enhanced_wal_durability.py`, `car_wal_manager.py` | DurableWAL recovery tests |
| Arrow / Parquet metadata | Secondary (U-07) | Yes | `arrow_metadata_index.py` | datasets metadata contract |
| Cache | No | Yes | `tiered_cache_manager.py`, `cache/` | cache-focused tests where present |
| Sync lineage / snapshots | Yes once persisted | Partially | `VFSCore` sync state | `test_vfs_contract_hardening.py` |

This table is the explicit acceptance matrix for KDOC-014: authoritative versus rebuildable state, ordering/atomicity (§5), conflict policy (§5.3), sync lineage (§4.5), cache behavior (§4.3, §5.1), failure modes and Recovery (§8), and extension points (§9) are test-linked in §12.
