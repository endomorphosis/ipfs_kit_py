# Kernel VFS Operations Guide

> **Document class:** Operator runbook (kernel VFS release terminal)
> **Task:** KVFS-811
> **Board namespace:** `ipfs-kit-kernel-vfs-fuse-v1`
> **Schema companion:** `support_matrix.json`, `release_receipt.json`, `migration.md`
> **Superproject plan (not shipped in this package repository):** `docs/architecture/IPFS_KIT_FUSE_VFS_PLAN.md` §§3.6–3.8, 6–8
> **CLI authority:** `ipfs_kit_py.cli.kernel_vfs` (`KernelVFSCLI@1`, task KVFS-702)
> **Status schema:** `ipfs_kit_py/kernel_vfs/status@1` (`KernelVFSStatus@1`)
> **Last verified:** 2026-08-10

This guide is the production operator surface for the kernel-mounted durable
cached VFS. It covers install, doctor, Linux/Windows/container
mount/unmount/status, options, limitations, monitoring, and backup/recovery.
Migration, downgrade, and rollback procedures live in
[`migration.md`](migration.md). Claim honesty (hermetic vs conditional vs live)
is machine-readable in [`support_matrix.json`](support_matrix.json). The
joined release decision is bound in [`release_receipt.json`](release_receipt.json).

---

## 1. Architecture (operator view)

```text
Linux VFS syscalls                     Windows file APIs
        |                                      |
 Linux FUSE kernel + libfuse2           WinFsp FSD + FUSE 2.8 layer
        |                                      |
        +----------- fusepy callbacks --------+
                            |
                 KernelVFSOperations
                            |
         path / errno / metadata / handle contracts
                            |
               DurableCachedVFSRuntime
                  /          |          \
       CanonicalVFSService   WAL   GenerationBoundARC
                  \          |          /
             injected ranged storage boundary
```

- **Semantics authority:** `CanonicalVFSService` (never fusepy / WinFsp).
- **Durability authority:** `CanonicalWAL` for every acknowledged mutation.
- **Cache authority:** `GenerationBoundARC` (committed generation-bound data only).
- **CLI entry point:** `ipfs-kit-kernel-vfs` → `ipfs_kit_py.cli.kernel_vfs:main`.
- **Default import is inert:** core import never loads fusepy, libfuse, or WinFsp.

---

## 2. Install

### 2.1 Prerequisites

| Item | Requirement |
| --- | --- |
| Python | 3.12 or 3.13 (`requires-python >=3.12`) |
| Package | `ipfs_kit_py==0.3.0` (or current tree equivalent) |
| Optional extra | `[fuse]` pins `fusepy==3.0.1` (binding only) |
| Linux native | libfuse2 (`libfuse.so.2`), `/dev/fuse`, `fusermount` |
| Windows native | Pinned WinFsp install + matching `winfsp-x64.dll` / `winfsp-x86.dll` |
| Container | Dedicated profile only; `/dev/fuse` + `SYS_ADMIN`; **never** `--privileged` |

### 2.2 Default wheel (inert)

```bash
python -m pip install ipfs_kit_py
# or from a checkout:
python -m pip install -e .
```

Default installs must remain inert:

- no fusepy in core dependencies;
- no libfuse / WinFsp side effects on import;
- mount CLI script is discoverable without loading a native library.

Verify:

```bash
python -c "import ipfs_kit_py.kernel_vfs.platform as p; assert p.is_binding_loaded() is False"
ipfs-kit-kernel-vfs --help
```

### 2.3 Optional FUSE binding

```bash
python -m pip install 'ipfs_kit_py[fuse]'
# exact pin required by packaging policy:
# fusepy==3.0.1
```

The `[fuse]` extra installs the **Python binding only**. Host drivers remain
operator-managed:

| Platform | Host driver / ABI |
| --- | --- |
| Linux | libfuse2 soname `libfuse.so.2` + kernel FUSE + fusermount helper |
| Windows | WinFsp service/driver + architecture-matched FUSE-compat DLL |

### 2.4 Packaging policy reference

Declared in `pyproject.toml`:

```toml
[project.optional-dependencies]
fuse = ["fusepy==3.0.1"]

[project.scripts]
ipfs-kit-kernel-vfs = "ipfs_kit_py.cli.kernel_vfs:main"

[tool.ipfs_kit_py.kernel_vfs.packaging]
fuse_extra = "fuse"
fuse_binding_requirement = "fusepy==3.0.1"
mount_cli_script = "ipfs-kit-kernel-vfs"
import_is_not_capability = true
default_wheel_inert = true
windows_classifier_policy = "live_gate_receipt"
```

**Presence is not support.** Import success and optional extras never promote a
live support claim. Windows OS classifier advertisement is gated by
`IPFS_KIT_KERNEL_VFS_WINDOWS_LIVE_GATE` and a current live WinFsp receipt.

---

## 3. Doctor (capability probe)

Doctor never mounts. Budget hard-ceiling is **5 seconds**. Missing capability
emits a typed receipt (`support_claim=capability_unavailable` or equivalent);
it never leaves a task running and never claims live readiness.

### 3.1 Commands

```bash
# Human summary
ipfs-kit-kernel-vfs doctor

# Machine JSON
ipfs-kit-kernel-vfs doctor --json

# Optional path hints (still no mount)
ipfs-kit-kernel-vfs doctor --mountpoint /mnt/ipfs-kit-vfs \
  --state-dir /var/lib/ipfs-kit-vfs/state --json

# Explicit budget clamp (hard max 5s)
ipfs-kit-kernel-vfs doctor --budget-seconds 5 --json
```

Environment overrides:

| Variable | Role |
| --- | --- |
| `IPFS_KIT_KERNEL_VFS_MOUNTPOINT` | Optional mountpoint for separation checks |
| `IPFS_KIT_KERNEL_VFS_STATE_DIR` | Optional state dir for separation checks |
| `IPFS_KIT_KERNEL_VFS_CAPABILITY_BUDGET_SECONDS` | Probe budget (clamped to ≤5s) |
| `FUSE_LIBRARY_PATH` | Explicit libfuse / WinFsp FUSE DLL override |

### 3.2 Linux doctor checks (KVFS-503)

Schema: `KernelVFSLinuxDoctorReport@1`

| Check | Pass condition |
| --- | --- |
| `os_architecture` | Supported Linux arch (x86_64 / aarch64) |
| `python_binding` | fusepy importable when probing (not at package import) |
| `libfuse2_abi` | `libfuse.so.2` resolvable |
| `dev_fuse` | `/dev/fuse` present and usable |
| `fusermount_helper` | `fusermount` on PATH |
| `permissions` | Caller may access device/helper as required |
| `mountpoint_state_separation` | Paths distinct; state not nested under mount |
| `actionable_absence` | Typed list of missing prerequisites |

### 3.3 Windows doctor checks (KVFS-608)

Schema: `KernelVFSWindowsDoctorReport@1`

| Check | Pass condition |
| --- | --- |
| `os_architecture` | Windows + Python pointer width |
| `python_binding` | fusepy importable when probing |
| `winfsp_dll` | Matching `winfsp-x64.dll` / `winfsp-x86.dll` via `FUSE_LIBRARY_PATH` or registry `InstallDir` |
| `winfsp_service` | WinFsp service probe (never started by doctor) |
| `winfsp_driver` | Driver identity probe |
| `winfsp_version` | Pinned / compatible WinFsp version identity |
| `architecture_agreement` | Python pointer width matches DLL architecture |
| `drive_directory_prerequisites` | Drive-letter / directory mount prerequisites |
| `actionable_absence` | Typed list of missing prerequisites |
| `mountpoint_state_separation` | Same separation rules as Linux (when paths supplied) |

Loader resolution order (deterministic):

1. Explicit `FUSE_LIBRARY_PATH`
2. Validated WinFsp registry `InstallDir` (`HKLM\SOFTWARE\WinFsp` then `WOW6432Node`) for architecture-matched DLL

### 3.4 Interpreting doctor output

| Field | Meaning |
| --- | --- |
| `ok` / `native_capability_ready` | Host can attempt a native mount |
| `support_claim` | `probe_passed` vs `capability_unavailable` |
| `mounted` | Always `false` for doctor |
| `checks.*.available` | Per-check boolean |
| `actionable_absence` | Operator remediation list |

A green hermetic test suite does **not** imply `native_capability_ready`.

---

## 4. Mount / unmount / status

### 4.1 Shared rules

| Rule | Value |
| --- | --- |
| Readiness handshake | ≤ 15 seconds (hard bound) |
| Stop / unmount timeout | default 5s, max 30s |
| Per-case live test timeout | 60 seconds |
| State vs mountpoint | Strictly separated (fail closed on overlap/nesting) |
| WAL / cache / recovery | Under state tree (or linked dedicated roots) |
| Secrets | Never in status, heartbeat, readiness, or WAL durable records |
| Hermetic default | CLI mount defaults to hermetic plane; use `--native` for live |

State layout prepared by the CLI:

```text
<state-dir>/
  wal/            # durable mutation log (or symlink to --wal-dir)
  cache/          # ARC working set (or symlink to --cache-dir)
  recovery/       # recovery receipts / leases
  ready.json
  heartbeat.json
  status.json
  child.pid
  cli-mount-options.json
```

### 4.2 Linux mount

```bash
# Hermetic plane (default; no live FUSE loop required for CLI wiring tests)
ipfs-kit-kernel-vfs mount \
  --mountpoint /mnt/ipfs-kit-vfs \
  --state-dir /var/lib/ipfs-kit-vfs/state \
  --wal-dir /var/lib/ipfs-kit-vfs/wal \
  --cache-dir /var/lib/ipfs-kit-vfs/cache \
  --foreground \
  --readiness \
  --json

# Native plane (requires doctor native_capability_ready)
ipfs-kit-kernel-vfs mount \
  --mountpoint /mnt/ipfs-kit-vfs \
  --state-dir /var/lib/ipfs-kit-vfs/state \
  --native \
  --foreground \
  --readiness \
  -o ro \
  -o fsname=ipfs-kit \
  --json
```

Notes:

- Foreground mode is the production default for daemons and containers.
- Readiness waits for recovery completion **before** advertising ready.
- Child mount processes publish heartbeat/status under the state directory.
- Workers never run a blocking FUSE loop in the supervisor process itself.

### 4.3 Windows mount

```powershell
# Directory mount (preferred for automation)
ipfs-kit-kernel-vfs mount `
  --mountpoint C:\Mounts\ipfs-kit-vfs `
  --state-dir C:\ProgramData\ipfs-kit-vfs\state `
  --native `
  --foreground `
  --readiness `
  --json

# Drive-letter mounts use the same CLI with a drive root path when the
# Windows lifecycle admits a free letter (see live harness receipts).
```

Windows-specific operator constraints:

- Case-fold collisions fail closed; display spelling is preserved.
- Reserved device names, trailing dots/spaces, and ambiguous UTF-8/UTF-16
  conversions are rejected by the Windows semantics contract.
- ACL / ADS / reparse points are **not** claimed as fully supported.
- Live support is advertised only after a current WinFsp live receipt.

### 4.4 Container mount (Linux Docker profile)

Dedicated artifacts (do not use the normal unprivileged image):

| Artifact | Path |
| --- | --- |
| Dockerfile | `ipfs_kit_py/docker/kernel-vfs.Dockerfile` |
| Compose profile | `ipfs_kit_py/docker-compose.kernel-vfs.yml` |

```bash
cd ipfs_kit_py
docker compose -f docker-compose.kernel-vfs.yml --profile kernel-vfs up --build
```

Contract (fail-closed):

| Control | Requirement |
| --- | --- |
| Device | `/dev/fuse` |
| Capability | `SYS_ADMIN` only (`cap_add`) |
| Privileged | **forbidden** (`privileged: false`) |
| Volumes | Separate named volumes for state, WAL, cache |
| Mount mode | Foreground + readiness |
| Missing input | Fail within **5 seconds** |
| Host propagation | **Not claimed** for Docker Desktop; in-container vs host-visible are separate claims |
| Windows containers | Conditional / experimental only |

Environment variables used by the image/CLI:

| Variable | Default in Compose |
| --- | --- |
| `IPFS_KIT_KERNEL_VFS_MOUNTPOINT` | `/mnt/ipfs-kit-vfs` |
| `IPFS_KIT_KERNEL_VFS_STATE_DIR` | `/var/lib/ipfs-kit-vfs/state` |
| `IPFS_KIT_KERNEL_VFS_WAL_DIR` | `/var/lib/ipfs-kit-vfs/wal` |
| `IPFS_KIT_KERNEL_VFS_CACHE_DIR` | `/var/lib/ipfs-kit-vfs/cache` |
| `IPFS_KIT_KERNEL_VFS_READY_DIR` | `/var/run/ipfs-kit-vfs` |
| `IPFS_KIT_KERNEL_VFS_FOREGROUND` | `1` |
| `IPFS_KIT_KERNEL_VFS_READINESS` | `1` |
| `IPFS_KIT_KERNEL_VFS_CAPABILITY_BUDGET_SECONDS` | `5` |

Useful overrides:

```bash
docker compose -f docker-compose.kernel-vfs.yml run --rm kernel-vfs doctor --json
docker compose -f docker-compose.kernel-vfs.yml run --rm kernel-vfs preflight
```

### 4.5 Status

```bash
ipfs-kit-kernel-vfs status --state-dir /var/lib/ipfs-kit-vfs/state
ipfs-kit-kernel-vfs status --state-dir /var/lib/ipfs-kit-vfs/state --json
```

`KernelVFSStatus@1` always exposes these closed sections:

| Section | Contents (bounded, secret-free) |
| --- | --- |
| `platform` | OS, arch, binding/ABI probe summary |
| `mount` | mount_id, mountpoint, pid, ready, hermetic/native plane |
| `recovery` | recovery complete, last replay counts (no payload secrets) |
| `wal` | queue depth, last committed identity, durability mode |
| `arc` | hit/miss ratios, generation, capacity pressure |
| `handles` | open/peak/released counts (no path tables) |
| `errors` | bounded recent error codes (≤16 entries) |
| `heartbeat` | liveness timestamp / sequence |

Status never emits:

- passwords, tokens, credentials, private keys;
- high-cardinality path lists, inode lists, or open-handle path tables.

### 4.6 Unmount

```bash
ipfs-kit-kernel-vfs unmount \
  --state-dir /var/lib/ipfs-kit-vfs/state \
  --stop-timeout 5 \
  --json
```

Unmount policy:

1. Validate PID / state lease before signalling.
2. Stop accepting new handles; drain or abort bounded callbacks.
3. fsync / record current WAL position; preserve recovery data.
4. Release mount, drive letter, child process, and lease.
5. **Idempotent:** second unmount is success with no-op cleanup.
6. **Never auto-delete** WAL/state recovery trees.

---

## 5. Options

### 5.1 Closed FUSE option allowlist

Admitted option **names** (values still length-bounded):

| Option | Notes |
| --- | --- |
| `default_permissions` | Always present in the effective profile |
| `ro` / `rw` | Mutually exclusive; last wins |
| `fsname` / `subtype` | Identifier-safe values only (`[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}`) |
| `max_read` | Integer 1 … 2^20 |
| `auto_unmount` | Linux helper convenience; optional |

Always rejected: `allow_root`, `suid`, `dev`, `exec` (privilege expansion),
`modules`, `nonempty`, unknown names, injection characters (`$`, `` ` ``, `;`,
`|`, newlines, commas).

### 5.2 `allow_other` (opt-in only)

Default **off**. Requires **both** explicit flags (passing only `-o allow_other`
is rejected):

```bash
ipfs-kit-kernel-vfs mount ... \
  --allow-other \
  --acknowledge-allow-other-warning
```

`--allow-other` injects the option into the admitted set. Operator warning
acknowledgement is mandatory: multi-user visibility expands beyond the mounting
user. Review ACLs before production use.

### 5.3 CLI timeout bounds

| Flag | Default | Hard max |
| --- | --- | --- |
| `--readiness-timeout` | 15s | 15s |
| `--stop-timeout` | 5s | 30s |
| doctor budget | 5s | 5s |
| option count | — | 32 |
| option length | — | 256 bytes |

### 5.4 Consistency and durability modes

Host callbacks follow the WAL acknowledgement pipeline (plan §3.4):

```text
validate + authorize
  -> acquire deterministic path/handle locks
  -> append recoverable WAL intent
  -> meet intent durability boundary
  -> apply CanonicalVFSService effect
  -> append decision/effect identity
  -> invalidate/advance ARC generation
  -> return callback result
```

- `fsync` succeeds only after WAL and selected backend durability receipts are current.
- `flush` may repeat; prior deferred write errors remain consistent.
- `release` is idempotent and never manufactures durability.

---

## 6. Limitations

| Area | Limitation | Claim class |
| --- | --- | --- |
| Default wheel | No native mount without `[fuse]` + host driver | hermetic |
| macOS | Not a production kernel-VFS mount target in this program | unsupported |
| Windows OS classifier | Advertised only after live WinFsp gate | conditional |
| Windows containers | Process isolation + host-started WinFsp; experimental | conditional |
| Docker Desktop host propagation | Not claimed | unsupported claim |
| Symlinks | Default `REJECT`; follow-within-root is opt-in and root-confined | hermetic-enforced |
| xattr / mknod / link | Stable `ENOSYS` / `EOPNOTSUPP` unless explicitly admitted | hermetic |
| ACL / ADS / reparse (Windows) | Not full NTFS feature parity | conditional |
| Network backends | Live IPFS/Iroh mounts require separate backend receipts | conditional |
| Performance claims | Bound to reviewed floors; cannot weaken correctness | hermetic floors + live promotion |

---

## 7. Monitoring

### 7.1 Primary signals

| Signal | Source | Alert when |
| --- | --- | --- |
| Ready | `ready.json` / status `mount.ready` | Missing after readiness window |
| Heartbeat | `heartbeat.json` | Stale beyond configured interval |
| Child PID | `child.pid` | Dead/zombie while status claims mounted |
| WAL queue | status `wal` | Depth above environment floor |
| ARC hit ratio | status `arc` | Sustained below warm floor (live env) |
| Handles | status `handles` | Growth after release > 0 |
| Errors | status `errors` | Rising false-success or escape codes (must be 0) |
| Doctor | `doctor --json` | `native_capability_ready=false` on prod hosts |

### 7.2 Container healthcheck

Compose healthcheck probes readiness file presence under
`IPFS_KIT_KERNEL_VFS_READY_DIR` (`ready.json`). Do not replace it with a
privileged shell that ignores mount leases.

### 7.3 Metrics not to scrape

- Per-path series, open-handle path tables, directory listings as metric labels.
- Secret-bearing configuration keys (redacted as `[REDACTED]` if ever projected).

### 7.4 Log / receipt hygiene

Status and WAL records reject or redact secret key fragments including
`password`, `secret`, `api_key`, `token`, `credential`, `private_key`, and
related forms. Operator logs must not reintroduce those fields.

---

## 8. Backup and recovery

### 8.1 What to back up

| Path role | Contents | Required for restore |
| --- | --- | --- |
| State directory | leases, readiness, child metadata, recovery receipts | yes |
| WAL directory | intent/decision segments, checkpoints | yes |
| Cache directory | generation-bound ARC; **nonportable across ABI/version without recovery** | optional |
| Mountpoint | ephemeral view only | no (never the durability root) |

**Never** co-locate WAL/state on the mountpoint. Unmount must not destroy recovery.

### 8.2 Backup procedure

1. Stop writers / unmount with a bounded stop timeout.
2. Confirm status shows recovery complete and no open handles.
3. Copy `state`, `wal`, and (optionally) `cache` to a timestamped backup **outside**
   the live tree. Record digests of WAL head and state lease files.
4. Record package version, Python version, libfuse/WinFsp identity, and
   `cli-mount-options.json`.
5. Resume only after doctor and a smoke status check.

### 8.3 Crash recovery

On next mount:

1. Lifecycle runs WAL recovery **before** readiness.
2. Incomplete intents are compensated or rejected; committed acks are preserved.
3. Corrupt/stale ARC is a safe miss (never admitted as live truth).
4. Second recovery is a pure no-op when state is already clean.
5. Stale PID / lease holders are fenced; no silent takeover.

### 8.4 Kill / chaos expectations

Safety floors (must remain exactly zero):

- acknowledged committed data loss;
- duplicate non-idempotent replay effects;
- stale ARC read after committed mutation/replay;
- path traversal / symlink / reserved-name alias escapes;
- false-success errno translation;
- leaked mount, drive letter, child process, handle, or state lease after test;
- unbounded startup/doctor/mount/unmount;
- core import requiring fusepy/libfuse/WinFsp;
- blanket privileged container profile.

Full floors: `benchmarks/kernel_vfs/reviewed_floors.json` and
[`release_receipt.json`](release_receipt.json).

### 8.5 ENOSPC / backpressure

Disk pressure and queue saturation fail closed:

- no acknowledged loss under ENOSPC;
- explicit rejection or wait under backpressure;
- queue/handle growth remains within ceilings;
- recovery remains time-bounded (≤60s for kill scenarios in reviewed floors).

---

## 9. Rollout stages (ops view)

1. **Hermetic** — callback/runtime tests, no native mount.
2. **Linux shadow** — read-only fixture mount, then writable temporary mount.
3. **Linux beta** — explicit CLI opt-in + container profile.
4. **Windows shadow** — hermetic contract on hosted runners; live WinFsp on labeled self-hosted.
5. **Windows beta** — explicit opt-in after current live receipt.
6. **Production** — terminal receipt binds source, dependency/ABI, live receipts, floors, migration, support matrix.

Do not skip claim classes: a hermetic green suite does not promote live Linux or Windows production.

---

## 10. Validation commands

Authoritative terminal gate (KVFS-811):

```bash
cd ipfs_kit_py && python -m pytest -q tests/kernel_vfs
cd ipfs_kit_py && python benchmarks/kernel_vfs/run.py --check-reviewed-floors
```

Collection notes:

- Linux and Windows suites share basenames (`test_loader_doctor.py`,
  `test_lifecycle.py`) under `tests/kernel_vfs/{linux,windows}/`.
- Platform package markers (`tests/kernel_vfs/linux/__init__.py` and
  `tests/kernel_vfs/windows/__init__.py`) give those tests distinct
  package-qualified module names under pytest's default import behavior.
- The host-contract inertness probe
  (`tests/kernel_vfs/contracts/test_host_contracts.py::test_module_is_inert_no_fusepy_dependency`)
  runs in a fresh subprocess, so it cannot replace enum or dataclass identities
  already imported in the shared pytest interpreter.
- No project-wide import-mode override is configured or required. If collection
  still reports a module `__file__` mismatch for those basenames:
  1. remove stale `__pycache__` / `.pyc` under `tests/kernel_vfs`;
  2. as a diagnostic only, re-run with an explicit path-unique import mode:
     `python -m pytest -q --import-mode=importlib tests/kernel_vfs`;
  3. do not substitute that diagnostic command for the authoritative default
     gate, and never treat a collection error as a green skip-pass.
- Live native suites (`linux/test_live_mount.py`, `windows/test_live_winfsp.py`,
  `container/test_live_container.py`) must emit `capability_unavailable` (or
  equivalent) when drivers/devices are absent; they must not promote live
  support from hermetic-only evidence.

Targeted suites:

```bash
python -m pytest -q tests/kernel_vfs/cli/test_cli.py
python -m pytest -q tests/kernel_vfs/security/test_security_boundaries.py
python -m pytest -q tests/kernel_vfs/test_ci_contract.py
python -m pytest -q tests/kernel_vfs/container/test_image_profile.py
python -m pytest -q tests/kernel_vfs/packaging/test_wheels.py
python -m pytest -q tests/kernel_vfs/test_chaos_floors.py
python -m pytest -q tests/kernel_vfs/test_differential.py
```

---

## 11. Related documents

| Document | Role |
| --- | --- |
| [`migration.md`](migration.md) | VFSCore cutover, downgrade, rollback |
| [`support_matrix.json`](support_matrix.json) | Hermetic / conditional / live claim matrix |
| [`release_receipt.json`](release_receipt.json) | Joined terminal release receipt |
| [`authority.md`](authority.md) | Semantics authority ADR (KVFS-100) |
| [`security.md`](security.md) | Security profile and attack ledger (KVFS-808) |
| `benchmarks/kernel_vfs/reviewed_floors.json` | Reviewed performance and safety floors |
