# Migration and Rollback (KITA-046)

This document is the operator companion to the **release candidate** receipt
[`release_candidate_receipt.json`](release_candidate_receipt.json)
(`ReleaseCandidateReceipt@1`) and the validation suite
`tests/runtime_readiness/release/test_release_candidate.py`.

It freezes **compatibility migration**, **staged rollout**, and
**rollback / forward recovery** for the `ipfs-kit-runtime-readiness-v1`
program. Interfaces: `MigrationReceipt@1`, `RollbackReceipt@1`,
`ReleaseCandidateReceipt@1`.

## Authority

| Role | Location |
| --- | --- |
| Bucket registry migration | `ipfs_kit_py.core.buckets.adapters` |
| Replica policy migration | `ipfs_kit_py.backend_policies.migrate_legacy_replication_policy` |
| WAL legacy projection | `ipfs_kit_py.core.wal.compatibility` |
| ARC persistence | `ipfs_kit_py.cache.arc.persistence` / `GenerationBoundARC` |
| GraphRAG restart/rebuild | `ipfs_kit_py.graphrag.service.GraphRAGService` |
| Backend inventory | `ipfs_kit_py.backends.spec` (`BackendSpec@1`) |
| Support matrix (machine) | `docs/runtime_readiness/backend_support_manifest.json` |
| Support matrix (human) | `docs/runtime_readiness/backend_support_matrix.md` |
| Packaging / extras | `pyproject.toml` `[project]` / `[project.optional-dependencies]` |
| Validation suite | `tests/runtime_readiness/release/test_release_candidate.py` |
| Candidate receipt | `docs/runtime_readiness/release_candidate_receipt.json` |

## Policy (fail-closed)

| Rule | Statement |
| --- | --- |
| Idempotent supported migration | Supported old state may be re-applied; second application is a no-op with identical content, version, and policy semantics. |
| Preserve semantics | Content digests, content versions, and policy fields that the canonical contract can express must be preserved. |
| Unsupported fails before mutation | Unknown schemas, conflicting identities, and non-expressible policy fields raise before any publish, file replace, or catalog write. |
| No invented durability | Legacy WAL `completed` / `success` is **not** committed unless durability evidence is proven separately. |
| Presence ≠ support | Registry presence, optional extras, and import success do not promote backend tiers. |
| Stale receipt rejected | A soak receipt or any other task receipt cannot satisfy KITA-046. The candidate binds suite and migration-doc digests. |
| Zero acknowledged loss | Rollback and forward recovery must not drop committed content. Incomplete WAL effects are compensated. |

## Supported migration surfaces

### Buckets (legacy registry → catalog key schema v2)

- **API:** `migrate_legacy_bucket_registry`, `LegacyBucketAdapter.migrate_registry`
- **Supported:** entries with a resolvable `backend` / `backend_id` and bucket name
- **Preserved:** backend identity, bucket name, operator policy tags, content version fields carried in the registry object
- **Idempotent:** re-running on an already-migrated registry returns the same mapping
- **Unsupported:** missing backend, non-object entries, conflicting aliases that resolve to one catalog key — all raise `BucketMigrationError` without mutating the caller's map
- **Publish rollback:** if `publish` fails, the adapter restores the pre-migration registry

### Replica policy

- **API:** `migrate_legacy_replication_policy`
- **Supported subset:** `min_redundancy`, `max_redundancy`, `critical_redundancy`, preferred/excluded backends, simple strategy, enabled
- **Unsupported (fail closed):** `geo_distribution`, non-simple `strategy`, non-zero `replication_delay_seconds`, `enabled=false`, unknown fields — raise `LegacyPolicyMigrationError` with `unsupported_fields`

### WAL / journal status projection

- **API:** `map_legacy_status`, `project_legacy_operation`
- **Rule:** legacy `completed` maps to pre-commit `appended` unless `durability_proven=True`
- **Unknown tokens:** preserved explicitly; never treated as committed
- **Secrets / unsafe encodings:** rejected rather than projected

### ARC cache

- **API:** `GenerationBoundARC.persist` / `restore`
- **Schema:** `ipfs_kit_py/cache/arc/persistence@1`, version `1`
- **Preserved on restore:** content bytes, binding version, policy, generation, namespace
- **Corrupt / wrong version / stale generation:** restore returns false; resident cache is not mutated

### GraphRAG

- **API:** `GraphRAGService.apply`, `open`, `clean_rebuild`
- **Restart:** reopens durable ledger and restores projection identity, version history, and current content
- **Rebuild:** clean rebuild matches incremental projection identity for the same ledger
- **Corrupt projection:** rebuild from non-executable ledger without resurrecting tombstones

### VFS / bucket content plane

Canonical `BucketService` put/get preserves payload bytes under identity-bound policy. Compatibility wrappers (`LegacyVFSAdapter`) reject unknown legacy operations without manufacturing success.

## Wheel and Python matrix

| Item | Source of truth |
| --- | --- |
| Package name / version | `pyproject.toml` `[project]` and `ipfs_kit_py.__version__` |
| Requires-Python | `requires-python` (currently `>=3.12`) |
| Supported matrix | Classifiers `Programming Language :: Python :: 3.12` and `3.13` |
| Minimal core | `[project.dependencies]` ≡ `requirements.txt` |
| Optional extras | `[project.optional-dependencies]` — every extra is a non-empty install set |

**Hermetic CI profile:** validates packaging projection, version identity, core import on the running matrix member, and that each declared extra has a complete dependency list (including dedicated `graphrag` and `mcp` extras). Full multi-interpreter wheel builds remain an operator lane and must use the same `requires-python` and extra names; they do not invent additional Python versions.

Optional extra *presence* never proves backend or capability support.

## Staged rollout procedure

1. **Inventory** — confirm dependency lane receipts exist (VFS, buckets, GraphRAG, replicas, ARC, MCP++, interfaces, backend matrix, soak/chaos).
2. **Backup** — copy live state trees to a timestamped backup directory outside the live path; record content digests.
3. **Migrate** — run supported migrations surface-by-surface; refuse unsupported state before mutation.
4. **Verify** — re-run `tests/runtime_readiness/release/test_release_candidate.py`; confirm content/version/policy digests.
5. **Promote** — only after the release-candidate receipt acceptance flags are all true.
6. **Observe** — keep the pre-migration backup until the next successful candidate on the same tree.

## Rollback

Rollback restores an **executable prior state** from the pre-migration backup:

1. Stop writers against the live path.
2. Replace the live state tree with the pre-migration backup (file-level atomic replace where the platform allows).
3. Restart the prior package revision that produced that backup.
4. Confirm digests match the pre-migration record.
5. Re-run subsystem smoke tests (at minimum: import core, open services, read a known object).

The hermetic suite rehearses registry rollback (file restore) and WAL compensation after a simulated crash at `after_effect`. Second recovery is a pure no-op (`replayed=0`, `rolled_back=0`).

## Forward recovery (when rollback package is unavailable)

If the prior executable package cannot be restored, operators may **forward-recover** without acknowledged loss:

1. Keep the original and backup trees intact.
2. Repair only unsupported fields offline (do not mutate live state during diagnosis).
3. Re-apply supported migrations from the pre-migration backup onto a staging path.
4. Diff content digests, versions, and policies against the last known-good migrated snapshot.
5. Swap staging into live only after the release-candidate suite passes on the staging tree.

Forward recovery never claims success for unmigratable fields; those remain blocked with typed errors.

## Backup and recovery instructions (unsupported / pre-mutation failure)

When migration refuses state **before mutation**, operators must:

1. Leave the original state file(s) untouched after a pre-mutation failure.
2. Copy the original tree to a timestamped backup directory outside the live path.
3. Record the failing schema version, disposition, and content digests in the operator log.
4. Either restore the backup to resume the prior executable package, or follow the documented forward-recovery path after repairing the unsupported fields offline.
5. Re-run this release-candidate suite before promoting any repaired state.

## Support manifest and registry honesty

`backend_support_manifest.json` and `backend_support_matrix.md` must list every canonical name from `ACTIVE_BACKEND_SPECS ∪ EXCLUDED_BACKEND_SPECS` exactly once, with tiers drawn from `BackendSpec@1`. The release-candidate suite fails closed on any inventory/manifest/doc mismatch. Stale or missing external evidence continues to demote or block storage selection (see KITA-042); this task does not promote tiers.

## Required dependency lanes

A candidate is invalid if any of these evidence artifacts is missing or empty:

| Task | Evidence |
| --- | --- |
| KITA-009 | `vfs_conformance.json` |
| KITA-013 | `bucket_conformance.json` |
| KITA-017 | `graphrag_conformance.json` |
| KITA-021 | `replica_conformance.json` |
| KITA-025 | `arc_conformance.json` |
| KITA-029 / KITA-033 | `mcplusplus_conformance.json` |
| KITA-037 | `interface_manifest.json` |
| KITA-042 | `backend_support_manifest.json` |
| KITA-045 | `soak_chaos_receipt.json` |

`soak_chaos_receipt.json` (KITA-045) is a **dependency**, not a substitute for `release_candidate_receipt.json` (KITA-046).

## Validation

```bash
cd ipfs_kit_py && python -m pytest -q tests/runtime_readiness/release/test_release_candidate.py
```

Acceptance (all required):

- Supported old state migrates idempotently with preserved content/version/policy semantics
- Unsupported state fails before mutation with backup/recovery instructions
- Minimal core and each extra wheel pass the supported Python matrix
- Rollback restores executable prior state or documented forward recovery without acknowledged loss
- Support manifest and docs match the actual registry
- No required lane skips or stale receipt satisfies the candidate
