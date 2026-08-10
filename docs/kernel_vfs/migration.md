# Kernel VFS Migration, Downgrade, and Rollback

> **Document class:** Migration and rollback guide (kernel VFS release terminal)
> **Task:** KVFS-811
> **Board namespace:** `ipfs-kit-kernel-vfs-fuse-v1`
> **Companion:** [`operations.md`](operations.md), [`support_matrix.json`](support_matrix.json), [`release_receipt.json`](release_receipt.json)
> **Authority ADR:** [`authority.md`](authority.md) (KVFS-100)
> **Superproject plan (not shipped in this package repository):** `docs/architecture/IPFS_KIT_FUSE_VFS_PLAN.md` §§3.1, 8
> **Last verified:** 2026-08-10

This document freezes **VFSCore / compatibility-surface migration**, **staged
cutover**, **downgrade**, and **rollback / forward recovery** for the
kernel-mounted durable cached VFS. It aggregates immutable evidence only; it
does not weaken security, durability, or performance floors.

---

## 1. Authority and dispositions

| Surface | Disposition | Mutation rule after cutover |
| --- | --- | --- |
| `CanonicalVFSService` | `semantics_authority` | Sole admitted mutator of VFS namespace state |
| `VFSCore` (`ipfs_kit_py.ipfs_fsspec`) | `compatibility_caller` | Path-plane envelopes only; must not bypass durability/cache rules |
| `VFSManager` | `compatibility_caller` | Routes through `LegacyVFSAdapter` → `CanonicalVFSService` |
| Legacy journals | `post_commit_recorder` | Record only after committed canonical mutation |
| Python API | `package_caller` | Call canonical service or closed adapter |
| CLI / MCP | `compatibility_surface` | Project verbs onto canonical service; no local success for failed results |
| FUSE / WinFsp | `thin_callback_adapter` | `KernelVFSOperations` → contracts → durable runtime → canonical service |

**Invariant:** no advertised mutation bypasses `CanonicalVFSService`. Journals,
caches, and host adapters never invent success.

Named cutover targets:

| Layer | Machine name | Role |
| --- | --- | --- |
| storage | `VFSStorageBoundary` | Sole injected storage side-effect surface |
| wal | `CanonicalWAL` | Ordering and durability for acknowledged mutations |
| cache | `GenerationBoundARC` | Shared cache holds only generation/version-bound committed data |

---

## 2. Policy (fail-closed)

| Rule | Statement |
| --- | --- |
| Idempotent supported migration | Re-applying a supported migration is a no-op with identical content, version, and policy semantics |
| Preserve semantics | Content digests, content versions, and expressible policy fields must be preserved |
| Unsupported fails before mutation | Unknown schemas, conflicting identities, and non-expressible fields raise before any write |
| No invented durability | Legacy “completed/success” is not committed without separate durability evidence |
| Presence ≠ support | Registry presence, optional extras, and import success do not promote support tiers |
| Zero acknowledged loss | Rollback and forward recovery must not drop committed content |
| Cache nonportability | ARC working sets may be discarded on downgrade; recovery must not require them |
| State/mount separation | Migration never co-locates WAL/state under the mountpoint |

---

## 3. VFSCore migration

### 3.1 Why migrate

Historical dual authority:

- `VFSCore` reached real backends with a simple unbounded dictionary cache and
  whole-file semantics;
- `CanonicalVFSService` had stronger contracts but was not always composed for
  host mounts.

Production kernel mounts bind the **canonical** path, not the old cache.

### 3.2 Caller cutover map

| Before | After | Notes |
| --- | --- | --- |
| Direct `VFSCore` durable writes | `CanonicalVFSService.execute` or `LegacyVFSAdapter` | Unsupported shortcuts fail closed |
| `VFSCore` dictionary cache hits as coherence proof | `GenerationBoundARC` generation-bound keys | Dirty extents stay per-handle |
| Manager-local success envelopes | Adapter projection of canonical results | No success on canonical failure |
| Journal-first mutation | WAL intent → effect → journal post-commit | Journals are recorders only |
| In-process FUSE loops as authority | `KernelVFSOperations` thin adapter | fusepy never a second VFS |

### 3.3 Supported migration surfaces

#### A. Package / Python callers

1. Inventory call sites that mutate through `VFSCore`, `VFSManager`, or private
   backend writes.
2. Route admitted mutations through `CanonicalVFSService` or
   `LegacyVFSAdapter` (`ipfs_kit_py.core.vfs.adapters`).
3. Replace unbounded whole-file cache assumptions with generation-bound ARC
   reads after commit.
4. Re-run hermetic differential suite (`tests/kernel_vfs/test_differential.py`)
   so model / service / host operations stay identity-aligned.

#### B. CLI and MCP

1. Confirm domain verbs map onto the closed operation vocabulary
   (`VFSOperationKind` / host callbacks).
2. Reject unknown legacy names with typed errors (never silent success).
3. Project errno/result from canonical outcomes only.

#### C. On-disk mount state

1. Unmount cleanly (see [`operations.md`](operations.md) §4.6).
2. Back up `state` + `wal` (+ optional `cache`) outside the live tree.
3. Install the new package revision and `[fuse]` extra as required.
4. Run `ipfs-kit-kernel-vfs doctor --json` on each host.
5. Mount with readiness; recovery must complete before ready.
6. Verify a known object read/write and `status --json` sections.

#### D. WAL / recovery records

- Canonical WAL records are the recoverable transaction source of truth.
- Legacy journal files may remain as post-commit mirrors; they do not replace
  WAL recovery.
- Corrupt or schema-mismatched ARC persistence is a **safe miss**, not a live
  truth admission.

#### E. Container profiles

- Migrate to the dedicated `docker-compose.kernel-vfs.yml` profile.
- Preserve separate volumes for state, WAL, and cache.
- Refuse any rollout that enables blanket `privileged: true`.

### 3.4 Explicitly unsupported during migration

| Input | Behavior |
| --- | --- |
| Unknown legacy operation names | Fail before mutation |
| Silent Unicode rewrite / case-fold aliasing | Reject (NFC required; Windows collisions fail closed) |
| Co-located state under mountpoint | Doctor/mount fail closed |
| Treating hermetic receipts as live promotion | Support matrix demotes; receipt blocks broader claims |
| Manufacturing durability from flush/release alone | Forbidden by durability contract |

### 3.5 Migration rehearsal (hermetic)

Minimum acceptance rehearsal before production cutover:

```bash
cd ipfs_kit_py
python -m pytest -q tests/kernel_vfs/test_differential.py
python -m pytest -q tests/kernel_vfs/wal
python -m pytest -q tests/kernel_vfs/arc
python -m pytest -q tests/kernel_vfs/cli/test_cli.py
python benchmarks/kernel_vfs/run.py --check-reviewed-floors
```

Optional live lanes (capability-gated, never skip-pass):

```bash
python -m pytest -q tests/kernel_vfs/linux/test_live_mount.py
python -m pytest -q tests/kernel_vfs/windows/test_live_winfsp.py
python -m pytest -q tests/kernel_vfs/container/test_live_container.py
```

Missing capability must emit `capability_unavailable` (or equivalent) and must
**not** promote the live support tier.

---

## 4. Staged rollout procedure

1. **Inventory** — confirm dependency task evidence exists for soak (KVFS-501),
   WinFsp conformance (KVFS-603), container (KVFS-700), CLI (KVFS-702), security
   (KVFS-808), differential (KVFS-800), CI (KVFS-802), floors (KVFS-801).
2. **Backup** — copy live state/WAL trees; record digests and package/ABI IDs.
3. **Hermetic gate** — full `tests/kernel_vfs` + reviewed floors check green.
4. **Doctor** — native hosts report actionable absences only; no silent pass.
5. **Shadow** — read-only then writable temporary mounts on Linux; Windows
   hermetic then labeled live runner.
6. **Beta** — explicit CLI opt-in / container profile; observe status and
   safety counters.
7. **Promote** — only when [`release_receipt.json`](release_receipt.json)
   acceptance flags are satisfied for the intended claim class.
8. **Retain backup** until the next successful receipt on the same tree.

---

## 5. Downgrade

Downgrade moves from a newer kernel-VFS package revision to a prior
**compatible** runtime that can still read the preserved WAL/state.

### 5.1 When to downgrade

- New revision fails doctor or readiness on production hosts.
- Safety floor counter becomes non-zero under chaos/soak.
- Live receipt is stale/missing while a broader claim was attempted.
- Packaging/ABI mismatch (wrong fusepy pin, libfuse soname, WinFsp arch).

### 5.2 Downgrade steps

1. **Stop writers** and unmount with PID/lease validation
   (`ipfs-kit-kernel-vfs unmount --state-dir … --json`).
2. **Preserve** state and WAL trees; do not delete recovery data.
3. **Invalidate nonportable ARC** (delete or ignore `cache/` working set if the
   prior runtime cannot admit it). Prefer safe miss over poisoned hits.
4. **Install prior package revision** (exact version recorded at backup) and the
   matching `[fuse]` pin when native mounts are required (`fusepy==3.0.1`).
5. **Reinstall host drivers only if the prior revision required a different
   pinned ABI** — never auto-downgrade kernel modules without change control.
6. **Doctor** on the prior revision (`ipfs-kit-kernel-vfs doctor --json`).
7. **Mount** with readiness; confirm recovery completes; verify known objects.
8. **Record** a downgrade receipt: package version, Python version, libfuse /
   WinFsp identity, WAL head digest, state lease digest, doctor claim, operator.
9. **Re-check floors** before re-promotion:
   `python benchmarks/kernel_vfs/run.py --check-reviewed-floors`.

### 5.3 Compatibility window

| Artifact | Downgrade rule |
| --- | --- |
| WAL segments written by current schema | Only prior runtimes that declare the same WAL record schema may open them |
| Status files (`KernelVFSStatus@1`) | Prior CLI may ignore newer optional fields; required sections stay stable |
| CLI options | Newer option names may be rejected by older CLI — use closed allowlist intersection |
| Container image labels | Rebuild prior image from prior Dockerfile pins |

If the prior runtime **cannot** open the WAL schema, do not force-open. Use
forward recovery (§7) or restore the pre-upgrade backup (§6).

---

## 6. Rollback

Rollback restores an **executable prior state** from the pre-migration backup.

### 6.1 Rollback sequence

1. Unmount / stop writers; fence stale leases
   (`ipfs-kit-kernel-vfs unmount --state-dir … --stop-timeout 5 --json`).
2. Replace live `state` and `wal` trees with the pre-migration backup (atomic
   directory swap where the platform allows).
3. Optionally discard `cache/` (safe miss preferred).
4. Install the prior package revision that produced that backup (and matching
   `[fuse]` / host ABI pins).
5. Doctor → mount → readiness → smoke read of known content digests.
6. Confirm digests match the pre-migration record; fail closed on divergence.
7. Re-run hermetic smoke at minimum:
   ```bash
   python -m pytest -q tests/kernel_vfs/cli tests/kernel_vfs/security \
     tests/kernel_vfs/test_chaos_floors.py
   python benchmarks/kernel_vfs/run.py --check-reviewed-floors
   ```
8. Keep the failed-forward tree offline until digests and floors are green.

### 6.2 What rollback must not do

- Auto-delete recovery data “to free space”.
- Claim success if digests diverge.
- Promote live support from hermetic-only evidence.
- Re-enable `allow_other` or privileged containers as a convenience.

### 6.3 Idempotence

A second rollback onto an already-restored tree is a no-op if digests match.
WAL second recovery after a clean restore is a pure no-op (`replayed=0`
compensations when already consistent).

---

## 7. Forward recovery (prior package unavailable)

When the prior executable package cannot be restored:

1. Keep original and backup trees intact.
2. Diagnose unsupported fields **offline** (no live mutation during diagnosis).
3. Re-apply supported migrations from the pre-migration backup onto a **staging**
   path using a known-good current package.
4. Diff content digests, versions, and policy against the last known-good
   migrated snapshot.
5. Swap staging into live only after hermetic gates pass on the staging tree.
6. Never claim success for unmigratable fields; leave them blocked with typed
   errors.

Forward recovery preserves **zero acknowledged committed data loss**.

---

## 8. Backup and recovery instructions (pre-mutation failure)

When migration refuses state **before mutation**:

1. Leave original state file(s) untouched.
2. Copy the original tree to a timestamped backup outside the live path.
3. Record failing schema version, disposition, and content digests.
4. Either restore the backup under the prior package, or follow forward recovery
   after offline repair of unsupported fields.
5. Re-run the hermetic suite and reviewed floors check before any promotion.

---

## 9. Wheel and Python matrix

| Item | Source of truth |
| --- | --- |
| Package name / version | `pyproject.toml` `[project]` / `ipfs_kit_py.__version__` |
| Requires-Python | `>=3.12` |
| Supported interpreters | Python 3.12 and 3.13 |
| Minimal core | Default dependencies (inert w.r.t. FUSE) |
| FUSE extra | `[fuse]` → `fusepy==3.0.1` |
| Mount CLI | `ipfs-kit-kernel-vfs` |

Hermetic CI validates packaging projection and core import. Full multi-interpreter
wheel builds are operator lanes bound to the same `requires-python` and extra
names; they do not invent additional Python versions.

---

## 10. Evidence bindings

| Dependency task | Evidence role |
| --- | --- |
| KVFS-100 | Authority dispositions and cutover names |
| KVFS-501 | Linux ARM64 / mount soak receipts |
| KVFS-603 | WinFsp live conformance harness |
| KVFS-700 | Docker mount/restart/propagation tests |
| KVFS-702 | CLI + status schema |
| KVFS-800 | Differential model vs service vs host |
| KVFS-801 | Reviewed performance and safety floors |
| KVFS-802 | Mandatory CI path-trigger gates |
| KVFS-808 | Security boundaries and attack ledger |

Terminal join: this document + `operations.md` + `support_matrix.json` +
`release_receipt.json` (KVFS-811).

---

## 11. Validation

```bash
cd ipfs_kit_py && python -m pytest -q tests/kernel_vfs
cd ipfs_kit_py && python benchmarks/kernel_vfs/run.py --check-reviewed-floors
```

Full-suite collection uses package markers under
`tests/kernel_vfs/{linux,windows}/` so shared basenames
(`test_loader_doctor.py`, `test_lifecycle.py`) receive distinct
package-qualified module names under pytest's default import behavior. The
host-contract inertness probe runs in a fresh subprocess and therefore cannot
replace enum or dataclass identities in the shared pytest interpreter. No
project-wide import-mode override is configured or required. Never treat a
collection error as a green skip-pass; see [`operations.md`](operations.md)
§10 for the diagnostic-only fallback.

Acceptance (all required):

- Supported callers migrate to `CanonicalVFSService` without durability/cache bypass
- Unsupported legacy inputs fail before mutation with backup/recovery instructions
- Downgrade preserves WAL/state and discards nonportable ARC safely
- Rollback restores executable prior state or documents forward recovery without acknowledged loss
- Support matrix claim classes remain honest (hermetic ≠ live)
- Safety floors remain exactly zero
