# IPFS Kit Runtime Surface Inventory (KITA-001)

This document freezes the **repository, capability, backend, and test-gate
inventory** for the `KITA-` runtime-readiness program. It is the human-readable
companion to
[`capability_manifest.json`](capability_manifest.json)
(`CapabilityManifest@1`).

## Inventory policy (checked-in)

| Rule | Statement |
| --- | --- |
| Presence ≠ support | Registry registration, import success, dashboard schema forms, optional extras, and test file existence do **not** prove correctness or production readiness. |
| Closed support tiers | Every advertised item is one of: `production`, `conditional`, `configuration-only`, `experimental`, `unsupported`, `unknown-pending-proof`. |
| Production bar | Requires complete required operations **and** live current-tree conformance evidence. No item is marked `production` in this freeze. |
| Exhaustiveness | Scope is the checked-in policy in the manifest (`policy.exhaustiveness_scope`). Findings supersede historical notes when revisions change. |

Machine-readable authority: `capability_manifest.json` → `policy`.

## Repository forest

| Repository | Role | Planning-bound revision | Observed at inventory | Match |
| --- | --- | --- | --- | --- |
| `ipfs_kit_py` | Primary storage runtime | `f6a574375febbcf9a46fcd24bbc7bc5cfb551de5` | `06cd826431cf8fb6f155942fa1345e69b9fb3100` | No |
| `ipfs_datasets_py` | Datasets / GraphRAG / logic provider | `7415adc5100192ee35676778f1018f6b072378f9` | same | Yes |
| `ipfs_accelerate_py` | Parent accelerator / supervisor | `f25e5719cb738a50fb96bac4bea3f66ebca9800b` | `26b8e4e0375428e11f1490b0c57ab33f9f67213b` | No |

A changed revision **invalidates** historical findings and requires a fresh
inventory; it is not automatically a failure.

## Version identity drift

| Source | Value |
| --- | --- |
| `ipfs_kit_py.__version__` | `0.2.0` |
| `pyproject.toml` `[project].version` | `0.3.0` |
| `setup.py` version | `0.3.0` |

**Disposition:** recorded under
`defect:lazy-import-dependency-version-drift`. Metadata and runtime disagree.

## Confirmed baseline defects (must remain explicit)

These are **observations**, not fixes. Content-addressed repair evidence is
owned by later `KITA-` tasks.

| Defect ID | Title | Severity |
| --- | --- | --- |
| `defect:vfs-noop-rename-journal-mismatch` | VFS `rename_item`/`move_item` report success without mutation; call `filesystem_journal.log_operation` which does not exist (`record_operation` does) | P0 |
| `defect:overlapping-bucket-planes` | Multiple overlapping bucket managers/indexes/tiering planes without a single saga/rollback protocol | P0 |
| `defect:wal-transaction-protocol` | Divergent WAL/journal variants; mock/random handlers on `storage_wal` production path; incomplete durability/checkpoint semantics | P0 |
| `defect:arc-accounting-concurrency` | ARC byte accounting / ghost-hit staleness; concurrent list mutation risk | P0 |
| `defect:shadowed-replica-methods` | Later `ensure_replication` shadows earlier copying implementation in `tiered_cache_manager` | P0 |
| `defect:backend-registry-factory-fracture` | Type registry vs dashboard schemas vs adapter map diverge; `get_backend_adapter` needs `create_filesystem` missing on legacy plugins | P0 |
| `defect:mcplusplus-construction-failure` | `mcp_server/server.py` constructs `EventDAGStore` without import | P0 |
| `defect:mcplusplus-policy-route` | Policy routed to permissive evaluator; Profile D / UCAN not fail-closed before dispatch | P0 |
| `defect:graphrag-persistence-safety-drift` | Pickle load, brute-force embeddings, non-rehydrated graph views, history bug, multi-schema drift | P0 |
| `defect:lazy-import-dependency-version-drift` | Version/export/dependency projection drift; eager MCP/root import surfaces | P0 |
| `defect:default-test-exclusions` | Default `pytest.ini` `norecursedirs` excludes `tests/integration` (WAL/ARC/replica/backend mass coverage) | P0 |

## Storage backend inventory

### Live type registry (`BackendTypeRegistry`)

**Count:** **22** registered types = `LEGACY_TYPES` (21) + `iroh`.

Planning/objective notes mentioned “23 backend types.” This inventory uses the
**live** registry count and does not invent a twenty-third type.

| Type | Plugin | `create_filesystem` | Adapter registry | Dashboard schema | Support tier |
| --- | --- | --- | --- | --- | --- |
| `cluster` | Legacy | no | — | — | configuration-only |
| `digitalocean` | Legacy | no | `S3BackendAdapter` | — | experimental |
| `estuary` | Legacy | no | — | — | configuration-only |
| `filecoin` | Legacy | no | — | yes | configuration-only |
| `filecoin_pin` | Legacy | no | — | — | configuration-only |
| `filesystem` | Legacy | no | `FilesystemBackendAdapter` | — | experimental |
| `ftp` | Legacy | no | — | yes | configuration-only |
| `gdrive` | Legacy | no | — | yes | configuration-only |
| `github` | Legacy | no | — | yes | configuration-only |
| `huggingface` | Legacy | no | — | yes | configuration-only |
| `ipfs` | Legacy | no | `IPFSBackendAdapter` | yes | experimental |
| `ipfs_cluster` | Legacy | no | — | alias `ipfs-cluster` | configuration-only |
| `iroh` | `IrohBackendPlugin` | **yes** | special-case via manager | plugin schema | **conditional** |
| `lassie` | Legacy | no | — | yes | configuration-only |
| `local` | Legacy | no | — | — | configuration-only |
| `local_fs` | Legacy | no | — | — | configuration-only |
| `local_storage` | Legacy | no | — | — | configuration-only |
| `minio` | Legacy | no | `S3BackendAdapter` | — | experimental |
| `parquet` | Legacy | no | — | yes | configuration-only |
| `s3` | Legacy | no | `S3BackendAdapter` | yes | experimental |
| `sshfs` | Legacy | no | `FilesystemBackendAdapter` | yes | experimental |
| `storacha` | Legacy | no | — | yes | configuration-only |

**Production backends at freeze:** **0**.

### Schema-only advertisements (not in type registry)

| Schema key | Support tier | Note |
| --- | --- | --- |
| `lotus` | unsupported | Dashboard form only |
| `arrow` | unsupported | Dashboard form only |
| `ipfs-cluster-follow` | unsupported | Dashboard form only |

### Factory fracture (summary)

1. **`BackendManager.get_backend_adapter`** → `plugin.create_filesystem(...)`.
2. **`LegacyBackendPlugin`** has no `create_filesystem` → unsupported runtime path for 21 types.
3. **`backends.BACKEND_ADAPTERS`** is a separate, smaller map (6 keys + iroh special-case).
4. **`backend_schemas.SCHEMAS`** is a third surface (15 keys) with aliases and non-registry types.

## Capability surfaces

| Capability | Primary modules (representative) | Support tier |
| --- | --- | --- |
| VFS namespace/file ops | `vfs_manager`, MCP vfs, `iroh_vfs`, bucket VFS managers | unknown-pending-proof |
| Virtual buckets | multiple `*bucket*` managers + Iroh tiering | unknown-pending-proof |
| WAL / journal | `wal`, `storage_wal`, `filesystem_journal`, CAR/enhanced variants | unknown-pending-proof |
| ARC cache | `arc_cache`, `arc_cache_anyio`, `tiered_cache_manager` | unknown-pending-proof |
| Replica policy | `tiered_cache_manager.ensure_replication` (shadowed) | unknown-pending-proof |
| GraphRAG | `graphrag`, MCP graphrag, vfs-bucket integration | experimental |
| MCP++ UCAN / Profile D | `mcp_server.server`, mcplusplus | unsupported |
| Backend conformance | registry + manager + adapters + schemas | unknown-pending-proof |
| Interface/package parity | package root, CLI, MCP/MCP++ | unknown-pending-proof |

## Public Python / CLI / MCP surfaces

### Package exports (`__all__`)

Exports emphasize workflow/JIT helpers (`MerkleClock`, `jit_manager`,
`require_feature`, backend status helpers, optional sibling package proxies).
They are **not** a complete map of storage semantics; storage entry points are
scattered across modules listed in the manifest.

### Console scripts (`pyproject.toml`)

| Script | Target | Tier |
| --- | --- | --- |
| `ipfs-kit` | `ipfs_kit_py.cli:sync_main` | unknown-pending-proof |
| `ipfs-kit-mcp` | `mcp_server.server:main` | unsupported (construction defect) |
| `ipfs-kit-mcp-tools` | `mcp_server.cli:main` | unknown-pending-proof |
| `ipfs-kit-iroh` | `iroh_install_cli:main` | conditional |
| `ipfs-kit-iroh-ops` | `iroh.cli:main` | conditional |
| `ipfs-kit-iroh-diagnostics` | `iroh.diagnostics_cli:main` | conditional |
| `ipfs-kit-iroh-manifest` | `iroh.manifest_cli:main` | conditional |
| `ipfs-kit-iroh-interop` | `iroh.multinode:main` | experimental |

### MCP / MCP++

- Legacy tool planes under `ipfs_kit_py/mcp/` (servers, controllers, tool
  registries) — **unknown-pending-proof**.
- Canonical MCP++ entry: `ipfs_kit_py.mcp_server` — **unsupported** until
  construction and Profile D / UCAN gates are repaired.

## Duplicate implementation planes

Recorded for later cutover (not refactored by this task):

- **VFS:** `vfs_manager`, MCP vfs, `iroh_vfs`, `bucket_vfs_manager`, `vfs_bucket_manager`
- **Buckets:** `bucket_manager`, simplified/simple/unified variants, Iroh tiering, enhanced indexes
- **WAL/journal:** `wal`, `storage_wal`, `filesystem_journal`, CAR/enhanced/pin variants
- **GraphRAG:** package root, MCP wrapper, VFS-bucket integration
- **Backend registries:** type registry, adapter map, dashboard schemas, storage backends API
- **CLI:** `cli.py`, `cli_commands.py`, `cli_old.py`, broken backup

## Optional dependencies

Source of truth: `pyproject.toml` `[project.optional-dependencies]`.

Extras (install sets only): `iroh`, `transformers`, `fsspec`, `arrow`,
`libp2p`, `ai_ml`, `huggingface`, `filecoin_pin`, `car_files`, `saturn`,
`ipni`, `enhanced_ipfs`, `ipld`, `ipfs_datasets`, `ipfs_accelerate`, `api`,
`webrtc`, `graphql`, `s3`, `performance`, `dev`, `full`.

**Rule:** installing an extra does not admit a backend or capability as
`production`.

## Test-gate inventory

### Default collection (`pytest.ini`)

```ini
testpaths = tests
norecursedirs = tests/integration tests/archived_stale_tests
```

**Effect:** the integration tree (≈426 modules) that holds most WAL, ARC,
replication, journal, and backend coverage is **not** part of the default
pytest gate.

### Related configs

| Config | Role |
| --- | --- |
| `pyproject.toml` `[tool.pytest.ini_options]` | `testpaths = ["tests"]`; does not restate norecursedirs |
| `config/pytest.ini` | Alternate `test`/`tests` paths; not package-root default |
| `tests/runtime_readiness/` | New KITA foundations lane (experimental relative to release) |

### Integration families excluded by default

Examples under `tests/integration/`: `test_storage_wal.py`, `test_wal_*.py`,
`test_filesystem_journal.py`, `test_fs_journal_*.py`,
`test_storage_backends*.py`, `test_replication_policy.py`, backend and MCP VFS
suites.

## Daemons and external providers

Ordinary imports must not download binaries or start daemons
(`IPFS_KIT_AUTO_INSTALL_BINARIES` is opt-in). Provider rows in the manifest are
`conditional` / `configuration-only` / `experimental` only—never `production`
without conformance receipts.

## How to use this freeze

1. **Do not** promote a tier to `production` without current live evidence.
2. **Do not** delete these defect IDs without superseding proof artifacts.
3. Later contract tasks (`KITA-002+`) consume this inventory as the closed set of
   advertised surfaces and known P0 blockers.
4. Regenerate or amend the JSON manifest when the repository forest or registry
   types change; keep this markdown aligned.

## Validation

```bash
cd ipfs_kit_py && python -m pytest -q tests/runtime_readiness/foundations/test_capability_manifest.py
```
