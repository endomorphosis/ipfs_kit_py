# KVFS-808: Kernel VFS Security Boundaries

> **Document class:** Security Policy Record (kernel VFS release)  
> **Decision status:** Accepted  
> **Task:** KVFS-808  
> **Board namespace:** `ipfs-kit-kernel-vfs-fuse-v1`  
> **Date:** 2026-08-10  
> **Last verified:** 2026-08-10  
> **Authors:** agent-supervisor implementation (KVFS-808)  
> **Related plan:** `docs/architecture/IPFS_KIT_FUSE_VFS_PLAN.md` §§3.6, 7  
> **Related objective:** KVFS-G800  
> **Depends on:** KVFS-500 (Linux lifecycle), KVFS-601 (Windows lifecycle)

---

## 1. Context

Kernel-mounted VFS surfaces accept untrusted path names, host mount options,
permission identities, state directories, and resource-bounded callbacks. An
attacker who can influence any of those inputs must not:

* escape admitted namespace roots (traversal, symlink, alias, reserved-name);
* widen mount authority (`allow_other`, option injection, permission confusion);
* corrupt or claim another mount's state (state/mount overlap, stale PID/lease);
* exhaust handle, WAL, or ARC capacity into undefined behavior;
* convert malformed native errors into false success;
* leak secrets into logs, status, heartbeat, or receipts; or
* leave side effects outside admitted roots after a rejected cleanup attack.

KVFS-808 freezes the fail-closed security profile and the executable adversarial
coverage that proves each attack class rejects with **zero side effect outside
admitted roots**.

**In scope:**

- Default Linux FUSE security profile (permission checking, `allow_other`, option
  allowlist).
- Path, Unicode, case, reserved-name, and symlink confinement.
- Mountpoint / state-directory separation and stale PID/lease detection.
- Permission projection and access checks.
- Resource exhaustion (handles, WAL records, ARC bindings).
- Exact errno / false-success policy for malformed native projections.
- Secret and log leakage rejection.
- Cleanup / unmount preservation of recovery state without external side effects.

**Out of scope:**

- Live kernel mount conformance (later lanes).
- Changing subsystem ownership of path policy, lifecycle, WAL, or ARC modules.
- Privileged container profiles (forbidden by plan; separate packaging task).

---

## 2. Decision

**Status:** Accepted

### 2.1 Default security profile

| Control | Default | Notes |
|---|---|---|
| Kernel permission checking (`default_permissions`) | **on** | Always admitted; never stripped by option injection |
| `allow_other` | **off** | Requires explicit operator opt-in **and** an operator-visible warning |
| `allow_root` | **off / rejected** | Never admitted |
| Arbitrary FUSE mount options | **rejected** | Closed allowlist only |
| Mount authority | mounting user only | No silent privilege expansion |
| Symlink policy | `REJECT` | Follow-within-root is opt-in and still root-confined |
| Path form | namespace-relative | Absolute OS, UNC, drive letters, `~`, `$VAR` rejected |
| Unicode | NFC required | Silent rewrite forbidden |
| Case | sensitive identity | Case-fold collisions fail closed on Windows |
| State vs mountpoint | strictly separated | Same path or state nested under mount is unavailable |
| Resource bounds | hard fail-closed | Exhaustion returns typed errors, never unbounded growth |
| Secrets in receipts/logs | rejected / redacted | Status and WAL records never carry secret material |

### 2.2 Closed FUSE option allowlist

Admitted option **names** (values still length-bounded):

- `default_permissions` (always present in the effective profile)
- `ro` / `rw`
- `fsname` / `subtype` (identifier-safe values only)
- `max_read` (bounded integer)
- `auto_unmount` (Linux helper convenience; optional)

All other option names are **injection attempts** and fail closed, including
but not limited to: `allow_other` (unless explicit opt-in), `allow_root`,
`suid`, `dev`, `exec` (when used as privilege-expansion options), `modules`,
`kernel_cache` with unreviewed side effects, and any option containing
separators, control characters, or environment expansion.

### 2.3 Fail-closed attack classes

| Attack class | Control surface | Failure mode |
|---|---|---|
| Path traversal (`..`, `.`, empty segments) | `VFSPathPolicy` / `normalize_vfs_path` | `VFSPathError` / reject; no mutation |
| Symlink escape | `evaluate_symlink` / default `REJECT` | `SYMLINK_REJECTED` or `SYMLINK_ESCAPE` |
| Unicode / case / reserved aliases | path policy + Windows name policy | typed reject; no silent rewrite |
| Mount-option injection | closed option allowlist | reject; mount not started |
| Unsafe `allow_other` | profile + explicit opt-in gate | reject unless explicit + warning |
| State / mount overlap | Linux doctor mountpoint/state separation | `available=false`; no mount |
| Stale PID / lease | lifecycle stale report + `StateLease` | report stale / lease held; no takeover |
| Permission confusion | metadata `access` / uid-gid policy | `EACCES` / fixed projection |
| Oversized request | path/IO/record bounds | bounds error; no partial admit |
| Handle / WAL / ARC exhaustion | hard capacity ceilings | typed pressure / bounds error |
| Malformed native error | `HostCallbackResult` success policy | false success forbidden |
| Secret / log leakage | WAL/status secret guards + redaction | reject or redact |
| Cleanup attacks | unmount preserves recovery only under state dir | no external side effects |

### 2.4 Zero side-effect invariant

For every rejected adversarial input:

1. No file, directory, handle, WAL record, or ARC entry is created **outside**
   the explicitly admitted roots (namespace root, mountpoint, state directory).
2. No successful host callback result is emitted for a failed policy check.
3. No secret material appears in status, heartbeat, readiness, unmount receipts,
   or WAL durable records.
4. Cleanup / unmount may only release leases and preserve recovery under the
   admitted state directory; it never deletes foreign trees.

---

## 3. Rationale

**Accepted:**

- The sealed program plan requires path traversal, symlink escape, and
  reserved-name alias escape floors of **zero**, and a default profile with
  kernel permission checking, `allow_other` off, and rejection of arbitrary
  mount options (`IPFS_KIT_FUSE_VFS_PLAN.md` §§3.6, 7).
- Existing contracts already implement fail-closed path policy, handle/WAL/ARC
  bounds, host false-success guards, mountpoint/state separation, and stale
  mount reporting. KVFS-808 binds those controls into one adversarial suite.
- Operator-visible `allow_other` opt-in prevents accidental multi-user exposure
  while still permitting reviewed multi-tenant deployments.

**Rejected alternatives:**

| Alternative | Why rejected |
|---|---|
| Silent path normalization / Unicode rewrite | Identity confusion and alias escape |
| Default `allow_other` | Privilege expansion beyond mounting user |
| Open-ended FUSE option passthrough | Option injection / suid / modules risk |
| Co-locating WAL/state on the mountpoint | Lost recovery on unmount; overlap attacks |
| Soft resource limits without typed errors | Unbounded memory / false readiness |

---

## 4. Consequences

### 4.1 Positive

- One security profile for Linux fusepy mounts and hermetic adversarial tests.
- Executable proof that every listed attack class fails closed.
- Clear operator rule for `allow_other` with an explicit warning requirement.

### 4.2 Costs

- Some convenience FUSE options require an allowlist amendment and review.
- Multi-user mounts need an explicit configuration change.

### 4.3 Testing

Adversarial tests live in
`ipfs_kit_py/tests/kernel_vfs/security/test_security_boundaries.py`.

Validation:

```bash
cd ipfs_kit_py && python -m pytest -q tests/kernel_vfs/security/test_security_boundaries.py
```

---

## 5. Machine-readable security ledger

The following fenced block is normative for automated security-boundary tests.
Keys and values are case-sensitive.

```security-ledger
task: KVFS-808
decision_status: Accepted
security_profile: default_fail_closed
default_permissions: on
allow_other: off
allow_other_requires_explicit_opt_in: true
allow_other_requires_operator_warning: true
allow_root: rejected
mount_option_policy: closed_allowlist
admitted_options: default_permissions,ro,rw,fsname,subtype,max_read,auto_unmount
symlink_policy_default: reject
path_form: namespace_relative
unicode_policy: nfc_required
case_policy: case_sensitive
state_mount_separation: required
stale_pid_lease_policy: report_and_fence
permission_projection: fixed_or_caller_explicit
resource_exhaustion: fail_closed_typed
false_success: forbidden
secret_log_policy: reject_or_redact
cleanup_side_effects: admitted_roots_only
invariant.zero_side_effect_outside_roots: true
invariant.traversal_escape_count: 0
invariant.symlink_escape_count: 0
invariant.reserved_alias_escape_count: 0
attack.path_traversal: fail_closed
attack.symlink_escape: fail_closed
attack.unicode_case_reserved_alias: fail_closed
attack.mount_option_injection: fail_closed
attack.unsafe_allow_other: fail_closed
attack.state_mount_overlap: fail_closed
attack.stale_pid_lease: fail_closed
attack.permission_confusion: fail_closed
attack.oversized_request: fail_closed
attack.handle_wal_arc_exhaustion: fail_closed
attack.malformed_native_error: fail_closed
attack.secret_log_leakage: fail_closed
attack.cleanup: fail_closed
```

---

## 6. References

| Artifact | Role |
|---|---|
| `ipfs_kit_py/core/vfs/contracts.py` | Path policy, symlink evaluation, bounds |
| `ipfs_kit_py/core/vfs/host_contracts.py` | Host errno / false-success policy |
| `ipfs_kit_py/core/vfs/metadata.py` | Access and uid/gid projection |
| `ipfs_kit_py/core/vfs/handles.py` | Handle exhaustion and pressure |
| `ipfs_kit_py/core/wal/vfs_records.py` | WAL secret rejection and bounds |
| `ipfs_kit_py/cache/arc/contracts.py` | ARC capacity and key bounds |
| `ipfs_kit_py/kernel_vfs/platform.py` | Mountpoint/state separation doctor |
| `ipfs_kit_py/kernel_vfs/linux.py` | Lifecycle, stale PID report, unmount |
| `ipfs_kit_py/kernel_vfs/wal_recovery.py` | State lease fencing |
| `ipfs_kit_py/kernel_vfs/windows_semantics.py` | Reserved names / case collisions |
| `docs/architecture/IPFS_KIT_FUSE_VFS_PLAN.md` | Program security floors |
| `ipfs_kit_py/tests/kernel_vfs/security/test_security_boundaries.py` | Executable adversarial suite |
