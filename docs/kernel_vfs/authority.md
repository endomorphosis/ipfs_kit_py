# KVFS-100: Canonical VFS Authority and Compatibility Disposition

> **Document class:** Architecture Decision Record (kernel VFS foundation)  
> **Decision status:** Accepted  
> **Task:** KVFS-100  
> **Board namespace:** `ipfs-kit-kernel-vfs-fuse-v1`  
> **Date:** 2026-08-09  
> **Last verified:** 2026-08-09  
> **Authors:** agent-supervisor implementation (KVFS-100)  
> **Related plan:** `docs/architecture/IPFS_KIT_FUSE_VFS_PLAN.md` §3.1  
> **Related objective:** KVFS-G100  

---

## 1. Context

The repository currently exposes multiple VFS-shaped surfaces:

- `CanonicalVFSService` (`ipfs_kit_py.core.vfs.service`) — closed operation
  vocabulary, observed-state-transition success rules, injected storage
  boundary only.
- `VFSCore` (`ipfs_kit_py.ipfs_fsspec`) — path-plane contract surface with real
  backend reach, simple dictionary cache, whole-file semantics.
- `VFSManager` (`ipfs_kit_py.vfs_manager` and MCP `VFSManager`) — higher-level
  managers used by CLI/MCP, already bridged through `LegacyVFSAdapter`.
- Legacy journals (`FilesystemJournal` and related monitors/replication) —
  change recording and recovery helpers, historically treated as if they owned
  mutation ordering.
- Python, CLI, and MCP entry points that call one or more of the above.
- Planned FUSE/WinFsp host adapters that must not become a second VFS.

Without a single semantics authority, host mounts, package callers, and control
planes can diverge on path policy, error codes, durability acknowledgement,
and cache coherence. KVFS-100 freezes that authority and the disposition of
every advertised caller surface.

**In scope:**

- Selection of the sole VFS *semantics* authority for admitted mutations.
- Compatibility disposition for `VFSCore`, `VFSManager`, legacy journals,
  Python, CLI, MCP, and future FUSE callers.
- Naming of the storage, WAL, and cache cutover targets that compose with that
  authority under `DurableCachedVFSRuntime`.
- Executable invariants that no advertised mutation path bypasses the
  authority.

**Out of scope:**

- Implementing ranged storage adapters, host callbacks, or FUSE loaders
  (later KVFS tasks).
- Removing legacy modules in this change.
- Changing MCP process-runtime authority (ADR-0003 remains separate).

---

## 2. Decision

**Status:** Accepted

### 2.1 Semantics authority

**CanonicalVFSService is the sole semantics authority** for admitted VFS
operations in the kernel-mounted durable cached VFS program.

It owns:

| Concern | Authority |
|---|---|
| Path normalization and root confinement | `CanonicalVFSService` + `VFSPathPolicy` |
| Operation vocabulary and request validation | `CanonicalVFSService` + `VFSOperationKind` |
| Result / error / errno projection inputs | `CanonicalVFSService` outcomes |
| Version preconditions and CAS | `CanonicalVFSService` |
| Transaction / observed-state-transition success | `CanonicalVFSService` |
| Side effects | Only through the injected `VFSStorageBoundary` |

Interface alias: **`CanonicalVFSService@1`**  
Schema: `ipfs_kit_py/core/vfs/service/canonical@1`

No other surface may invent a successful admitted mutation, translate a
canonical failure into success, or claim durability/cache coherence without
crossing this service (and, for acknowledged durable mutations, the canonical
WAL cutover named below).

### 2.2 Compatibility dispositions

Every advertised caller surface has exactly one disposition:

| Surface | Disposition | Mutation rule |
|---|---|---|
| `CanonicalVFSService` | `semantics_authority` | Direct `execute`; sole admitted mutator of VFS namespace state |
| `VFSCore` | `compatibility_caller` | May remain for path-plane envelopes; **must not** bypass canonical mutation/durability/cache rules. Admitted durable mutations either delegate into `CanonicalVFSService` or are explicitly unsupported |
| `VFSManager` | `compatibility_caller` | Routes admitted operations through `LegacyVFSAdapter` → `CanonicalVFSService`; never a parallel authority |
| Legacy journals (`FilesystemJournal`, monitors, replication helpers) | `post_commit_recorder` | Record **only after** a committed canonical mutation; journals are not mutation or durability authorities |
| Python API callers | `package_caller` | Call `CanonicalVFSService` directly or via `LegacyVFSAdapter`; no private backend mutation shortcuts for advertised ops |
| CLI | `compatibility_surface` | Projects argv/domain verbs onto the canonical service (directly or via manager/adapter); no CLI-local success for failed canonical results |
| MCP / MCP++ VFS tools | `compatibility_surface` | Project tool calls onto the canonical service (or manager/adapter over it); no tool-local success for failed canonical results |
| Future FUSE / WinFsp callers | `thin_callback_adapter` | `KernelVFSOperations` → path/errno/handle contracts → `DurableCachedVFSRuntime` → `CanonicalVFSService`; fusepy/WinFsp are never a second VFS implementation |

Disposition vocabulary (closed):

- `semantics_authority` — defines and enforces semantics.
- `compatibility_caller` — existing library surface; must delegate or fail closed.
- `compatibility_surface` — process/entry surface over the same authority.
- `post_commit_recorder` — observes committed effects only.
- `package_caller` — in-process package consumer of the authority.
- `thin_callback_adapter` — host kernel callback projection only.

### 2.3 Storage, WAL, and cache cutover

The production composition is:

```text
Host / package / CLI / MCP / FUSE callers
                |
        (adapters / contracts only)
                |
        DurableCachedVFSRuntime
           /          |          \
 CanonicalVFSService  WAL   GenerationBoundARC
           \          |          /
        injected VFSStorageBoundary
                |
     memory / local / IPFS / Iroh adapters
```

Named cutover targets:

| Layer | Cutover target | Role after cutover |
|---|---|---|
| **storage** | `VFSStorageBoundary` | Sole injected storage side-effect surface for the authority; ranged memory/local/IPFS/Iroh adapters implement this boundary. Direct backend writes from compatibility callers are out of authority. |
| **wal** | `CanonicalWAL` (`ipfs_kit_py.core.wal`) | Ordering and durability source of truth for every **acknowledged** mutation. Intent append and decision/effect identity precede callback success for durable modes. Legacy journals may mirror post-commit; they do not replace the WAL. |
| **cache** | `GenerationBoundARC` | Shared cache holds **only** generation/version-bound committed data. Dirty extents stay in per-handle staging. Invalidation/advance follows canonical commit and WAL recovery. `VFSCore`'s unbounded dictionary cache is not the production coherence authority. |

Cutover machine names (stable for tests and follow-on tasks):

| Layer | Machine name |
|---|---|
| storage | `VFSStorageBoundary` |
| wal | `CanonicalWAL` |
| cache | `GenerationBoundARC` |

### 2.4 No-bypass mutation invariant

An **advertised mutation** is any operation that:

1. is in the closed mutating vocabulary (`MUTATING_OPERATIONS` /
   `VFSOperationKind` create/replace/mkdir/rmdir/rename/move/delete/cas_write/
   mount/unmount), or
2. is projected from a legacy/manager/CLI/MCP name that maps onto that
   vocabulary (for example `write` → replace, `rm` → delete, `mkdir` → mkdir).

For every advertised mutation:

1. **Admission** happens only through `CanonicalVFSService.execute` (or a
   closed adapter that exclusively calls it).
2. **Success** requires an observed admitted state transition on the injected
   `VFSStorageBoundary`; success without observation is a contract failure.
3. **Failure** never emits a success event and never becomes a compatibility
   success envelope.
4. **Journals** may record only after commit; journal absence or failure must
   not rewrite the canonical result to success.
5. **Cache** may serve only committed generation-bound data; a cache hit is
   never an authorization or mutation bypass.
6. **FUSE/host adapters** translate callbacks to canonical operations; they do
   not apply namespace mutations themselves.

---

## 3. Rationale

**Accepted:**

- The sealed program plan states that `CanonicalVFSService` remains the
  operation and error authority, that fusepy is a thin adapter, that every
  acknowledged mutation is ordered through the canonical WAL, and that ARC
  contains only version/generation-bound committed data
  (`IPFS_KIT_FUSE_VFS_PLAN.md` §§1, 3.1, 3.4, 3.5).
- Runtime-readiness already implements `CanonicalVFSService@1`, closed
  `LegacyVFSAdapter` dispatch, and generation-bound ARC predicates.
- Objective heap invariant: “`CanonicalVFSService` is the sole semantic
  authority exposed to the host.”

**Proposed (implementation follow-ons, not re-opening authority):**

- Complete `VFSCore` cutover so remaining path-plane helpers either delegate
  into the canonical service for admitted mutations or are labeled unsupported.
- Compose `DurableCachedVFSRuntime` wiring storage + WAL + ARC for host mounts.

**Inferred:**

- Historical dual authority (`VFSCore` for backends vs canonical service for
  contracts) existed because components landed on different tracks; it is not
  a long-term dual-authority design.

---

## 4. Consequences

### 4.1 Positive

- One path/result/error/effect authority for package, CLI, MCP, and FUSE.
- Clear migration story for legacy managers and journals.
- Named cutover targets for storage, WAL, and cache workstreams.

### 4.2 Costs

- Compatibility callers must be audited so they do not retain private mutation
  paths.
- Documentation that still treats `VFSCore` as sole normative authority for
  durable mutations must be updated in later doc tasks.

### 4.3 Migration

| Surface | Near-term action |
|---|---|
| `VFSManager` / MCP managers | Keep `LegacyVFSAdapter` as the only bridge |
| `VFSCore` | Treat as compatibility; no new durable mutation features outside canonical service |
| Legacy journals | Post-commit record only; WAL cutover owns durability |
| FUSE | Implement only as thin callback adapter over the authority |

### 4.4 Testing

Contract tests in
`ipfs_kit_py/tests/kernel_vfs/contracts/test_authority.py` encode:

- ADR selection of `CanonicalVFSService` as semantics authority;
- dispositions for all named surfaces;
- storage / WAL / cache cutover names;
- runtime proof that advertised mutations cannot bypass the authority.

Validation:

```bash
cd ipfs_kit_py && python -m pytest -q tests/kernel_vfs/contracts/test_authority.py
```

---

## 5. Alternatives considered

| Alternative | Why rejected |
|---|---|
| Keep dual authority (`VFSCore` + `CanonicalVFSService`) | Divergent path/error/cache/durability semantics under FUSE |
| Elevate `VFSManager` as authority | Manager is a multi-feature facade; already a compatibility bridge |
| Elevate legacy journals as mutation authority | Journals record history; they do not own observed state transitions |
| Let FUSE implement its own VFS | Violates “mount is not a second VFS”; dual error and recovery models |

---

## 6. Machine-readable authority ledger

The following fenced block is normative for automated contract tests. Keys and
values are case-sensitive.

```authority-ledger
task: KVFS-100
decision_status: Accepted
semantics_authority: CanonicalVFSService
semantics_authority_alias: CanonicalVFSService@1
semantics_authority_module: ipfs_kit_py.core.vfs.service
semantics_authority_class: CanonicalVFSService

disposition.CanonicalVFSService: semantics_authority
disposition.VFSCore: compatibility_caller
disposition.VFSManager: compatibility_caller
disposition.legacy_journals: post_commit_recorder
disposition.Python: package_caller
disposition.CLI: compatibility_surface
disposition.MCP: compatibility_surface
disposition.FUSE: thin_callback_adapter

cutover.storage: VFSStorageBoundary
cutover.wal: CanonicalWAL
cutover.cache: GenerationBoundARC

invariant.no_advertised_mutation_bypass: true
invariant.success_requires_observed_transition: true
invariant.journal_is_not_mutation_authority: true
invariant.fuse_is_not_second_vfs: true
```

---

## 7. References

| Artifact | Role |
|---|---|
| `ipfs_kit_py/core/vfs/service.py` | `CanonicalVFSService` implementation |
| `ipfs_kit_py/core/vfs/contracts.py` | Closed operation vocabulary and observation rules |
| `ipfs_kit_py/core/vfs/adapters.py` | `LegacyVFSAdapter` closed bridge |
| `ipfs_kit_py/core/wal/` | Canonical WAL cutover package |
| `ipfs_kit_py/arc_cache.py` / `ipfs_kit_py/cache/arc/` | `GenerationBoundARC` cutover |
| `ipfs_kit_py/ipfs_fsspec.py` | `VFSCore` compatibility surface |
| `ipfs_kit_py/vfs_manager.py` | Package `VFSManager` compatibility caller |
| `docs/architecture/IPFS_KIT_FUSE_VFS_PLAN.md` | Program architecture |
