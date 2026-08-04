# Filesystem Journal Contract

| Field | Value |
|---|---|
| Document class | **Canonical contract + operator guide** |
| Status | Active |
| Last verified | 2026-08-04 |
| Owner / task | KDOC-035 |
| Primary implementation | `ipfs_kit_py/filesystem_journal.py` |
| Integration façade | `ipfs_kit_py/fs_journal_integration.py` |
| Architecture parent | [`docs/architecture/CONTENT_METADATA_VFS.md`](architecture/CONTENT_METADATA_VFS.md) |
| VFS path-plane contract | [`docs/VFS_CONTRACT_SPEC.md`](VFS_CONTRACT_SPEC.md) |
| Vocabulary | [`docs/architecture/GLOSSARY.md`](architecture/GLOSSARY.md) (Journal vs WAL) |

This document is the **normative** description of filesystem-journal behavior: operation types, entry statuses, **ordering**, recovery, and failure/partial/retry semantics. Tutorial examples follow the contract sections; if an example disagrees with the contract tables, the tables win.

The keywords **MUST**, **MUST NOT**, **SHOULD**, and **MAY** apply to implementations that claim journal conformance.

---

## 1. Scope and non-goals

### 1.1 In scope

| Topic | Why |
|---|---|
| Journal entry types and statuses | Crash recovery correctness |
| Transaction boundaries and checkpoints | Atomicity unit for FS metadata |
| Recovery algorithm and counters | Operator-verifiable restore |
| Path → CID / `fs_state` rebuild rules | Authoritative path-plane metadata after restart |
| WAL co-existence (roles only) | Prevent conflating storage retry logs with FS structure |
| Current vs compatibility adapters (CLI/MCP/HLA) | Explicit ranking |
| Failure, partial apply, and retry rules | Unambiguous degraded modes |

### 1.2 Non-goals

| Out of scope | Owner |
|---|---|
| Declaring WAL + journal mandatory for every mutating backend (U-06) | ADR 0005 / architecture guide |
| Storage WAL operation schemas and partition formats | `storage_wal.py`, `wal.py`, DurableWAL docs |
| Iroh manifest CAS / tombstone grammar | [`docs/iroh/filesystem-contract.md`](iroh/filesystem-contract.md) |
| VFS request/response envelopes (`success`/`code` for `vfs_*`) | [`VFS_CONTRACT_SPEC.md`](VFS_CONTRACT_SPEC.md) |
| Cluster CRDT authority for multi-writer FS | Cluster architecture track |

---

## 2. What the journal is (and is not)

| | Filesystem journal | Write-ahead log (WAL families) |
|---|---|---|
| **Purpose** | Transactional **filesystem metadata / structure** durability | Durable **storage operation** intent and retry |
| **Typical ops** | create, delete, rename, write metadata, mount/unmount CID, checkpoint | add, pin, upload, get, backend RM |
| **Atomicity unit** | Transaction (`begin` → ops → `commit` / `rollback`) + checkpoints | Per operation record (status machine) |
| **Recovery** | Load newest valid checkpoint; replay **completed** journal entries only | Drain pending / recover stalled / segment scan |
| **Primary modules** | `filesystem_journal.py`, `fs_journal_integration.py`, `fs_journal_backends.py`, `fs_journal_replication.py` | `storage_wal.py`, `wal.py`, `enhanced_wal_durability.py`, `car_wal_manager.py` |

**Rule:** Enabling the journal does **not** enable a WAL, and vice versa. They are complementary planes.

Evidence: module docstrings; CONTENT_METADATA_VFS §5; `tests/unit/test_filesystem_journal_comprehensive.py`.

---

## 3. Current vs compatibility surfaces

### 3.1 Ranking table

| Rank | Surface | Path | Role |
|---|---|---|---|
| **Current (core)** | `FilesystemJournal` | `ipfs_kit_py/filesystem_journal.py` | Journal files, checkpoints, recover, transactions |
| **Current (manager)** | `FilesystemJournalManager` | same module | Higher-level create/delete/write/mount that records + applies ops |
| **Current (HLA façade)** | `FilesystemJournalIntegration` / `enable_filesystem_journaling` | `fs_journal_integration.py`; `IPFSSimpleAPI.enable_filesystem_journaling` | Path adapter (`IPFSFilesystemInterface`) + journal manager wiring |
| **Current (optional backends)** | Tiered journal backends | `fs_journal_backends.py` | Pluggable journal storage tiers |
| **Current (optional replication)** | Metadata replication | `fs_journal_replication.py` | Checkpoint/journal metadata copy; default conflict **LWW** |
| **Current (CLI candidate)** | Journal verbs on packaged CLI | `ipfs-kit journal …` via FastCLI / unified dispatcher helpers; `fs_journal_cli.py` | Operator entry; CLI composition authority still open (U-02) |
| **Compatibility (MCP tools)** | Journal MCP tool modules | `ipfs_kit_py/mcp/servers/fs_journal_mcp_tools.py`, root shims | Legacy MCP tree; not packaging MCP++ default |
| **Compatibility (monitor extras)** | Health / visualization | `fs_journal_monitor.py` | Observability helpers; not required for core recover |
| **Supplementary tests** | Integration suite | `tests/integration/test_filesystem_journal.py`, `test_fs_journal_*.py` | **Excluded** from default pytest discovery (`norecursedirs`) |

### 3.2 Adapter rules

1. **Core recovery semantics** are defined by `FilesystemJournal.recover` — façades **MUST NOT** redefine “completed means applied.”
2. MCP journal tools **SHOULD** expose status/list/recover operations without inventing a second journal format.
3. HLA `enable_filesystem_journaling` **MUST** pass the configured `base_path` / intervals through to `FilesystemJournal` (or manager) so recovery finds the same directories after restart.

Evidence: `tests/unit/test_filesystem_journal_comprehensive.py`; `tests/unit/test_fs_journal_mcp_tools_comprehensive.py` (MCP tool unit coverage when present).

---

## 4. On-disk layout (actual)

Default base path: `~/.ipfs_kit/journal` (expanduser).

| Path under base | Contents |
|---|---|
| `journals/` | `journal_<timestamp>.json` files — ordered entry lists |
| `checkpoints/` | `checkpoint_*.json` — serialized `fs_state` + optional checksum |
| `temp/` | Temporary files during atomic writes |

**Note:** Older prose that referred to a single `journal.log` or top-level `transactions/` / `recovery/` directories is **stale** relative to the current implementation. Treat the table above as authoritative.

Constructor knobs (core):

| Parameter | Default | Meaning |
|---|---|---|
| `base_path` | `~/.ipfs_kit/journal` | Journal root |
| `sync_interval` | `5` | Seconds between journal syncs to disk |
| `checkpoint_interval` | `60` | Seconds between automatic checkpoints |
| `max_journal_size` | `1000` | Entries before forcing a checkpoint |
| `auto_recovery` | `True` | Run `recover()` on init |
| `wal` | `None` | Optional WAL instance for co-integration |
| `enable_ipfs_datasets` | `False` | Optional datasets integration when deps available |

Evidence: `FilesystemJournal.__init__` in `filesystem_journal.py`; init tests in the comprehensive unit suite.

---

## 5. Operation types and entry statuses

### 5.1 `JournalOperationType`

| Value | Meaning |
|---|---|
| `create` | Create a file or directory |
| `delete` | Delete a file or directory |
| `rename` | Rename or move |
| `write` | Write file bytes (metadata plane records the op; content may be referenced) |
| `truncate` | Truncate a file |
| `metadata` | Update metadata / attributes |
| `checkpoint` | Checkpoint marker / transaction boundary record |
| `mount` | Mount a CID at a path |
| `unmount` | Unmount a path |
| `dataset` | Dataset-oriented journaled op (store/version hooks when enabled) |

### 5.2 `JournalEntryStatus`

| Value | Meaning | Applied on recovery? |
|---|---|---|
| `pending` | Recorded, not completed | **No** |
| `completed` | Finished successfully | **Yes** |
| `failed` | Failed | **No** |
| `rolled_back` | Explicitly rolled back | **No** |

**Invariant:** Recovery **MUST** apply only entries with `status == completed`. Pending, failed, and rolled_back entries **MUST NOT** mutate rebuilt `fs_state`.

Evidence: `FilesystemJournal.recover` skip branch; CONTENT_METADATA_VFS §5.1 invariant 3; unit recovery tests.

---

## 6. Ordering and atomicity

### 6.1 Ordering guarantees

| Scope | Guarantee |
|---|---|
| Within a transaction | Entries recorded after `begin_transaction` are associated with that transaction until `commit_transaction` or `rollback_transaction` |
| Commit | Marks the transaction complete; subsequent recovery treats completed entries as apply-eligible |
| Checkpoint | Captures a consistent `fs_state` snapshot; used as the recovery base |
| Recovery journal scan | Among journals with timestamp ≥ checkpoint time, process **oldest first** |
| Recovery entry scan | Within a journal file, apply completed entries in file order |
| Checkpoint selection | Prefer **newest** checkpoint files first; skip checksum failures and try older |

### 6.2 Atomicity unit

The atomicity unit is:

```text
begin_transaction → record/apply operations → commit_transaction
                 ↘ rollback_transaction (no completed apply for abandoned work)
```

Checkpoints are consistency snapshots, not multi-journal distributed transactions.

**Cross-plane note:** A committed journal transaction does **not** atomically complete a WAL upload or pin. Callers needing multi-plane atomicity must sequence compensating actions (see VFS contract §6.3).

---

## 7. Transaction and recovery flows

### 7.1 Happy-path mutation (manager)

```text
Caller op (create/write/delete/…)
    │
    ▼
record_operation (status=pending)  ──► durable journal intent
    │
    ▼
apply to live fs_state / filesystem interface
    │
    ▼
mark_completed  (status=completed)
    │
    ▼
periodic or explicit create_checkpoint
```

If the process crashes after `record` but before `mark_completed`, recovery **skips** the incomplete entry — the path plane does not gain a half-applied completed record.

### 7.2 Recovery algorithm (`FilesystemJournal.recover`)

Result dictionary shape (fields **MUST** be present on return):

| Field | Type | Meaning |
|---|---|---|
| `success` | `bool` | Overall recovery attempt completed without hard abort |
| `checkpoints_loaded` | `int` | Valid checkpoints loaded (0 or 1 in normal path after first success) |
| `journals_processed` | `int` | Journal files scanned |
| `entries_processed` | `int` | Entries seen |
| `entries_applied` | `int` | Completed entries applied to `fs_state` |
| `errors` | `list` | Checksum mismatches, I/O errors, bad filenames |

Steps:

1. List `checkpoint_*.json`; sort newest first.
2. For each checkpoint until one loads: verify checksum when present; load `fs_state`.
3. List `journal_*.json`; keep those with timestamp ≥ checkpoint time; sort oldest first.
4. For each entry: if `status != completed`, skip; else `_apply_journal_entry`.
5. Open a new journal for subsequent ops.
6. Set `success=true` if the procedure finished (errors may still be listed for partial degradation).

Evidence: `recover` implementation; `TestFilesystemJournalRecovery` in `tests/unit/test_filesystem_journal_comprehensive.py`.

### 7.3 Apply semantics by operation type

On recovery apply (`_apply_journal_entry`):

| Op | Effect on `fs_state` (summary) |
|---|---|
| `create` | Ensure path entry exists (file/dir metadata) |
| `delete` | Remove path entry |
| `rename` | Move path entry |
| `write` / `truncate` | Update file entry size/content references as recorded |
| `metadata` | Merge metadata fields |
| `mount` / `unmount` | Attach/detach CID mapping at path |
| `checkpoint` | Boundary no-op for tree mutation |
| `dataset` | Dataset-related state updates when recorded |

Unknown historical op types **SHOULD** be logged and counted as errors rather than guessed.

---

## 8. Failure, partial, and retry semantics

### 8.1 Failure modes

| Failure | Observed behavior | Operator action |
|---|---|---|
| Process crash mid-transaction | Pending entries not completed → skipped on recovery | Re-issue intended ops if still required |
| Checkpoint checksum mismatch | Checkpoint skipped; try older; error string recorded | Investigate disk corruption; keep older checkpoints |
| Corrupt journal file | Journal errors appended; other journals still processed | Restore from last good checkpoint + healthy journals |
| Op execution failure at runtime | `mark_failed(entry_id, reason=…)` | Inspect reason; fix backend/FS; do not expect auto-apply |
| Rollback | Entries marked `rolled_back` | Not applied on recovery |
| Missing optional datasets deps | Datasets integration disabled; local journal continues | Install extras only if needed |
| Concurrent multi-process writers | **No** cross-process linearizability claimed; in-process `RLock` only | Use single writer or external coordination |

### 8.2 Partial success

| Situation | Meaning |
|---|---|
| `recover().success == true` with non-empty `errors` | Recovery finished but some checkpoints/journals failed — inspect `entries_applied` vs `entries_processed` |
| `entries_applied < entries_processed` | Expected when pending/failed entries exist — **not** by itself a hard failure |
| Checkpoint loaded but zero journals | Healthy idle system or all ops already checkpointed |
| Manager op returns failure after journal record | Entry should be `failed`; path may be unchanged — check status APIs |

### 8.3 Retry semantics

| Layer | Retry? |
|---|---|
| Journal core | **No** automatic multi-attempt retry of failed FS ops inside `recover` |
| `mark_failed` | Terminal for that entry id |
| Caller / HLA | **MAY** re-drive operations after fixing root cause |
| Optional custom error handlers (integration) | Integration-specific; not part of core `recover` |
| WAL co-plane | Independent retry budget (`pending`/`retrying`) — do not conflate with journal statuses |

**Rule:** Journal recovery is **replay of completed history**, not a job queue. Retry is a **caller** concern.

---

## 9. Relationship to VFS and buckets

| Plane | Journal role |
|---|---|
| `VFSCore` path ops | May run **without** journal; journal is optional composition |
| Bucket managers | May maintain their own indexes under `~/.ipfs_kit/buckets/`; journal is not automatically the bucket index |
| Path → CID map | Journal `fs_state` is authoritative for the **journaled** virtual tree after recovery; caches remain rebuildable |

Deleting a journaled path **does not** unpin content unless a separate retention API runs.

See [`VFS_CONTRACT_SPEC.md`](VFS_CONTRACT_SPEC.md) for path-plane response shapes and sync conflict policy (orthogonal to journal entry status).

---

## 10. Security and trust

| Concern | Guidance |
|---|---|
| Journal directory contents | May contain paths, CIDs, and metadata — protect with host ACLs; do not commit kit state to source control |
| Checksums | Treat checkpoint checksum mismatch as integrity failure for that file; do not “force load” corrupt state in production automation without audit |
| Multi-tenant | Journal base paths should be isolated per tenant when MCP multi-tenancy is used |
| Secrets | **MUST NOT** store raw credentials in journal metadata fields |

---

## 11. Test map (rank-1 evidence)

| Concern | Tests |
|---|---|
| Init defaults, custom intervals, directory creation | `tests/unit/test_filesystem_journal_comprehensive.py` (`TestFilesystemJournalInitialization`) |
| Record create/delete/write/mount | `TestFilesystemJournalOperations` |
| `mark_completed` / `mark_failed` / status | `TestFilesystemJournalStatus` |
| Checkpoints list/create | `TestFilesystemJournalCheckpointing` |
| Auto + manual recovery | `TestFilesystemJournalRecovery` |
| Cleanup / close | `TestFilesystemJournalCleanup` |
| MCP journal tools (unit) | `tests/unit/test_fs_journal_mcp_tools_comprehensive.py` |
| Supplementary integration (non-default discovery) | `tests/integration/test_filesystem_journal.py`, `tests/integration/test_fs_journal_*.py` |

---

## 12. Operator usage guide

### 12.1 Enable via high-level API

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()

# Optional: attach a WAL for storage-op durability (separate plane)
# from ipfs_kit_py.wal import WAL
# api.wal = WAL(base_path="~/.ipfs_kit/wal")

journaled_fs = api.enable_filesystem_journaling(
    journal_base_path="~/.ipfs_kit/journal",
    auto_recovery=True,
    sync_interval=5,
    checkpoint_interval=60,
)

journaled_fs.create_directory("/virtual_fs", metadata={"description": "root"})
journaled_fs.create_file(
    "/virtual_fs/readme.txt",
    b"hello",
    metadata={"type": "text"},
)
journaled_fs.create_checkpoint()
stats = journaled_fs.get_journal_stats()
journaled_fs.close()
```

### 12.2 Core class direct use

```python
from ipfs_kit_py.filesystem_journal import (
    FilesystemJournal,
    JournalOperationType,
)

journal = FilesystemJournal(
    base_path="~/.ipfs_kit/journal",
    auto_recovery=True,
)

entry_id = journal.record_operation(
    operation_type=JournalOperationType.CREATE,
    path="/virtual_fs/item.txt",
    data={"is_directory": False},
)
journal.mark_completed(entry_id)
result = journal.recover()
assert "entries_applied" in result
journal.close()
```

### 12.3 Transactions

Prefer the integration/manager transaction APIs when available:

```python
# Pattern A: context manager (integration surface when provided)
with journaled_fs.transaction() as txn:
    txn.create_directory("/virtual_fs/project")
    txn.write_file("/virtual_fs/project/a.txt", b"a")
    # commit on clean exit; rollback on exception

# Pattern B: explicit core API
tx_id = journal.begin_transaction()
try:
    # record + apply ops while in_transaction
    journal.commit_transaction()
except Exception:
    journal.rollback_transaction()
    raise
```

If a process dies before commit, incomplete work remains non-`completed` and is skipped on recovery.

### 12.4 Recovery after crash

```python
journaled_fs = api.enable_filesystem_journaling(
    journal_base_path="~/.ipfs_kit/journal",
    auto_recovery=True,  # recover() on init
)

# Or force:
result = journaled_fs.recover()
print(result["checkpoints_loaded"], result["entries_applied"], result["errors"])
journaled_fs.create_checkpoint()
```

### 12.5 Mount by CID

```python
journaled_fs.mount(
    "/virtual_fs/mounted",
    cid="QmExample",
    is_directory=False,
    metadata={"source": "external"},
)
journaled_fs.unmount("/virtual_fs/mounted")
```

### 12.6 Example scripts

Repository examples (illustrative; not rank-1 tests):

- `examples/fs_journal_example.py`
- `examples/fs_journal_integration_example.py`
- `examples/fs_journal_monitor_example.py`

```bash
python -m ipfs_kit_py.examples.fs_journal_example
```

### 12.7 Configuration via environment (when honored by caller)

Callers and wrappers **MAY** map environment variables into constructor arguments. Common names used in operator docs:

| Variable | Maps to |
|---|---|
| `IPFS_KIT_JOURNAL_PATH` | `base_path` / `journal_base_path` |
| `IPFS_KIT_JOURNAL_AUTO_RECOVERY` | `auto_recovery` |
| `IPFS_KIT_JOURNAL_SYNC_INTERVAL` | `sync_interval` |
| `IPFS_KIT_JOURNAL_CHECKPOINT_INTERVAL` | `checkpoint_interval` |
| `IPFS_KIT_JOURNAL_MAX_SIZE` | `max_journal_size` |

Prefer explicit constructor arguments in production automation so recovery paths are not ambient.

### 12.8 WAL + journal together

```python
api = IPFSSimpleAPI(enable_wal=True)
journaled_fs = api.enable_filesystem_journaling()

# WAL: storage op durability (add/pin/upload retry)
# Journal: virtual tree consistency (create/mount/rename)

result = api.add(b"protected bytes")
# Mount the resulting CID into the journaled tree when add completes
```

| Concern | Use |
|---|---|
| Backend down during add/pin | WAL retry |
| Crash during multi-step directory setup | Journal transaction + recovery |
| Both | Enable both; still no single global ACID transaction |

---

## 13. Performance notes

1. Longer `sync_interval` reduces I/O but increases loss window for not-yet-synced entries.
2. More frequent checkpoints speed recovery but add write amplification.
3. Large transactions improve multi-op atomicity at the cost of memory and rollback cost.
4. Place `base_path` on durable, low-latency storage.
5. Journaling is optional — skip it only when crash consistency of the virtual tree is not required (document that choice).

---

## 14. Related documentation

| Document | Role |
|---|---|
| [`docs/VFS_CONTRACT_SPEC.md`](VFS_CONTRACT_SPEC.md) | Path-plane envelopes, sync conflict, adapters |
| [`docs/architecture/CONTENT_METADATA_VFS.md`](architecture/CONTENT_METADATA_VFS.md) | Layering, authority vs rebuildable, recovery catalog |
| [`docs/architecture/SOURCE_OF_TRUTH_MAP.md`](architecture/SOURCE_OF_TRUTH_MAP.md) | Evidence map |
| [`docs/architecture/GLOSSARY.md`](architecture/GLOSSARY.md) | Journal vs WAL vocabulary |
| [`docs/features/vfs/VFS_MANAGEMENT_CONSOLIDATION.md`](features/vfs/VFS_MANAGEMENT_CONSOLIDATION.md) | User-facing VFS management |

---

## 15. Change triggers

Update this document when:

- `JournalOperationType` or `JournalEntryStatus` values change
- `recover()` counters or apply rules change
- On-disk layout (`journals/`, `checkpoints/`) changes
- HLA `enable_filesystem_journaling` signature or recovery defaults change
- Rank-1 unit tests are renamed or removed
- U-06 durability mandate is resolved by ADR (then state whether journal is required)
