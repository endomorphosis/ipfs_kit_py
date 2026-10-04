# Iroh staged release readiness and sign-off

Decision: **GO for the `disabled` stage only** (IROH-027, 2026-07-13).

The Iroh filesystem backend ships with `iroh.enabled=false`. This decision does
not approve experimental, canary, or supported production operation. Promotion
is manual and requires a new immutable evidence set and named sign-off. The
canonical machine report is
`ipfs_kit_py/resources/iroh-release-readiness.json`; test, benchmark, security,
operations, packaging, and interoperability receipts are in
`ipfs_kit_py/resources/iroh-release-receipts.json`. Both validate against the
adjacent Draft 2020-12 schemas and the base-installation validator in
`ipfs_kit_py.iroh.release`.

## Current gate result

| Gate | Result | Meaning |
| --- | --- | --- |
| Default safety | Pass | The service and named backend configuration default to disabled. Import and non-Iroh operation do not require a sidecar. |
| Offline tests | Pass | Contract, fsspec, async, service, installer, packaging, and policy lanes are required CI gates. |
| Deterministic benchmark | Pass | The in-memory latency/throughput/resource floor passes; it makes no WAN or relay performance claim. |
| Security | Pass | No unresolved critical or high findings are recorded. Integrity, input bounds, redaction, permissions, provenance, GC, and rollback controls are covered. |
| Sidecar distribution | Conditional | The pinned sidecar is `source-pinned`; no platform is currently marked installable. |
| Real multi-node | Not run | The checked-in evidence honestly records `not_run`; protected Linux and macOS runs are required before canary. |
| Disabled-stage decision | GO | Release is permitted only while Iroh remains disabled by default. |

The conditional and not-run receipts are visible blockers, not waivers. Run:

```bash
python scripts/ci/verify_iroh_release_readiness.py
python -m pytest -q tests/test_iroh_release_readiness.py
```

The verifier exits nonzero for schema drift, missing receipts, a default-on
configuration, destructive rollback, or any unresolved critical/high finding.

## Rollout stages

1. **Disabled.** This is the approved release stage. Every installation sees
   `iroh.enabled=false`; Iroh requires explicit operator action.
2. **Experimental opt-in.** Restricted to development or disposable test
   environments. Operators rehearse backup, verified export, recovery, and
   disablement on representative data. There is no production durability SLA.
3. **Canary.** At most 5% of production backends, with a named on-call owner and
   fallback. Requires passing real-node direct, relay, NAT-like, interruption,
   version-skew, key-rotation, and large-data receipts on Linux and macOS,
   immutable attested binaries, and a successful rollback drill.
4. **Supported.** Requires 30 consecutive canary days within every SLO, no
   severity-1/2 incident, a passing portability rehearsal, current runbooks,
   and release-manager plus storage-on-call sign-off.

There is no automatic promotion. A successful lower-stage release never
implies approval for a higher stage.

## SLOs and rollback triggers

All verified reads must pass their expected BLAKE3 hash (100%) and recovery may
lose zero committed manifest revisions. Experimental local metadata p95 is at
most 50 ms. From canary onward, successful storage operations must be at least
99.9% over 30 days, unexpected operation errors at most 0.1% over 24 hours, and
service recovery at most 30 minutes. The report contains the exact metric IDs,
operators, units, windows, and stage applicability.

Immediately disable and roll back for any hash mismatch, committed-manifest
loss, credential disclosure, critical/high finding, unrecoverable divergence,
recovery failure, or exhausted canary/supported error budget. Two consecutive
latency breach windows also roll back a canary.

## Non-destructive rollback

1. Freeze writes and set `iroh.enabled=false`.
2. Capture redacted health, version, manifest-head, and operation receipts.
3. Stop only the managed sidecar. Preserve the state directory, all blobs and
   manifests, identity backup, and the pre-migration snapshot. Do not run GC.
4. Restore the previously attested binary/configuration. If a storage format
   changed, restore the snapshot; never point an old binary at migrated live
   data unless that exact downgrade was proven on a copy.
5. Start read-only in isolation. Compare namespace IDs, revisions, heads,
   canonical manifest hashes, referenced blob availability/BLAKE3 hashes, and
   representative byte-identical exports with the pre-change inventory.
6. Reopen only with storage-owner sign-off. Otherwise route to the fallback
   backend and retain both state copies for recovery.

Uninstall and rollback are separate operations. Neither authorizes deletion of
state, manifests, blobs, identity backups, or exports.

## Compatibility, migration, and deprecation

The compatibility window covers the current and immediately previous supported
bundle for at least 90 days after replacement, on Python 3.12 and 3.13. Unknown
RPC protocols fail before storage access. A passing real-node version-skew
receipt is required before canary.

Migration is never automatic: inventory and portable export first, stop writes,
snapshot, migrate a copy, verify it, and atomically select the new bundle. A
failed migration disables Iroh and restores the retained binary/snapshot.

Deprecation receives at least 90 days' notice in `CHANGELOG.md`, the Iroh
release notes, and runtime diagnostics. Notice identifies the affected bundle
or capability, last support date, replacement, export steps, and support
contact. End of support never authorizes data deletion.

## Data portability and ownership

Every namespace can be exported non-destructively as a byte-identical file
tree, canonical JSON manifest inventory, and BLAKE3 checksum inventory. Export
does not require a running sidecar, verifies every file, and never relabels an
Iroh hash as an IPFS CID.

IPFS Kit storage maintainers own rollout, recovery, and SLO response. IPFS Kit
security maintainers own finding triage and credential incidents. Integrity,
data-loss, credential, or supported-stage SLO incidents page the storage
on-call through the project issue process; tickets include only redacted
receipts, release/platform identity, last known-good manifest revision, and
rollback status.

## Promotion checklist

- Publish and verify immutable sidecar digests and GitHub attestations for each
  supported platform; update the compatibility record from `source-pinned`.
- Attach passing protected-lane Linux and macOS interoperability evidence.
- Confirm zero unresolved critical/high findings and resolve or explicitly
  disposition lower-severity findings with owner and date.
- Complete representative backup/export/restore and non-destructive rollback.
- Attach the required 14-day experimental or 30-day canary SLO observation.
- Record the target stage, receipt IDs, release manager, storage on-call, date,
  and explicit decision in a new signed readiness report.

