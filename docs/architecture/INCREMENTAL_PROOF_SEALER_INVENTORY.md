# IncrementalProofSealer kit inventory (IPS-003)

Static source inventory of `ipfs_kit_py` proof transport, CID, Merkle, WAL,
CAS, recovery, Profile-D, MCP++/Iroh release, and baseline-reference surfaces
at the receipt-tested nested revision. This document is a companion to
`docs/architecture/incremental_proof_sealer_inventory.json`.

## Revisions

| Field | Value |
| --- | --- |
| `planning_revision` | `5a7a2df8181cfdc33bc19be09989df7ff83f2d4e` |
| `inventory_worktree_parent_revision` | `b2c8e625b184c41fa865d906e0037915e3fb9179` |

`inventory_worktree_parent_revision` is immutable and equals the receipt-tested
kit source revision. Final nested/outer/status commits come from supervisor
completion evidence and are not self-embedded here.

## Baseline evidence (reference only)

Operator-captured process observation only. This inventory does not restate
command lines, outcome tallies, logs, or execution claims.

| Field | Value |
| --- | --- |
| path | `artifacts/agent_supervisor/incremental_proof_sealer/baseline_receipts/kit.json` |
| receipt_digest | `sha256:22d4f9663e3346fd2264efb38538cbedead642c3ba7fe403b5c7b9fc6545f982` |
| required_command_ids | `kit-proof-certificate`, `kit-reuse-capabilities`, `kit-profile-d`, `kit-coordination`, `kit-modern-wal`, `kit-proof-reuse-bootstrap`, `kit-agent-receipts`, `kit-iroh-release`, `kit-release-receipt` |
| evidence_origin | `operator_capture` |
| assurance | `process_observed_only` |
| nonclaim | `pytest_execution_not_cryptographically_proven` |

The protected closed suite registry and validator independently recompute suite
preimages, argv, controlled-offline environment, digests, log sizes, counts,
and incomplete-collection evidence nodes. Providers only reference the pin above.

## Inspection method

- classification_method: static source inventory
- Static scans report `surfaces_found` only; they never assert suite outcomes
- Static inspection is not pytest execution and is not cryptographic proof
- Controlled-offline capture disables auto-install and live daemons; the receipt
  reference does not establish new real proving

## Explicit nonclaims

1. `proof_certificate_store` is **exact-byte CID transport** only; it does not
   verify cryptography or decide reuse.
2. Event-DAG default certificates are **hash commitments**, explicitly
   **non-ZK**.
3. No inspected kit test performs **real proving** or **direct execution** proof.
4. Legacy WAL modules, `merkle_clock`, Event-DAG Merkle helpers, and
   `ipfs_multiformats` testing **pseudo-CIDs** are **not** proof-seal authorities.
5. MCP++ artifact receipts may leave `signatures` empty; **unsigned receipts
   remain unsigned**.
6. `install_lotus.download_params` is **opt-in** Filecoin proving-parameter
   download, not automatic proof setup.
7. Planned-but-absent `proof_seal_store` is **not** counted as current structure.
8. Recursive verifier status: **absent**. Direct-execution proving: **absent**.

## Surface families

### Strict CID transport

| Path | Role | Classification |
| --- | --- | --- |
| `ipfs_kit_py/proof_certificate_store.py` | exact-byte certificate transport | integrity_transport |
| `ipfs_kit_py/test_reuse_capabilities.py` | cold Kubo/Lotus/Iroh capability probe | structural_capability_probe |
| `ipfs_kit_py/ipfs_multiformats.py` | multiformats + testing pseudo-CIDs | pseudo_cid_not_authority |

### Profile D policy

| Path | Role | Classification |
| --- | --- | --- |
| `ipfs_kit_py/mcp/profile_d_policy.py` | MCP Profile D adapter (refuses when evaluator unavailable) | structural_policy_adapter |

### MCP++ artifacts, coordination, Event-DAG

| Path | Role | Classification |
| --- | --- | --- |
| `ipfs_kit_py/mcp_server/mcplusplus/artifacts.py` | CIDv1 intent/decision/receipt envelopes | integrity_cid_envelope |
| `ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py` | durable CID blocks + index rebuild | integrity_durable_block_store |
| `ipfs_kit_py/mcp_server/mcplusplus/event_dag.py` | Profile F retention + Merkle helpers | integrity_only_non_zk |

### Iroh / KITA release receipts

| Path | Role | Classification |
| --- | --- | --- |
| `ipfs_kit_py/iroh/release.py` | stage-aware readiness + packaged receipts | structural_release_evidence |

### Filecoin proving-parameter download

| Path | Role | Classification |
| --- | --- | --- |
| `ipfs_kit_py/install_lotus.py` | Lotus install + opt-in `download_params` | opt_in_download_surface |

### Modern WAL (durability base)

| Path | Role | Classification |
| --- | --- | --- |
| `ipfs_kit_py/core/wal/contracts.py` | closed WAL contracts | integrity_durability_contract |
| `ipfs_kit_py/core/wal/writer.py` | group-commit writer | integrity_durability |
| `ipfs_kit_py/core/wal/coordinator.py` | transaction coordinator | integrity_durability |
| `ipfs_kit_py/core/wal/checkpoint.py` | exact-identity checkpoints | integrity_durability |
| `ipfs_kit_py/core/wal/recovery.py` | committed-only replay / corruption | integrity_corruption_recovery |
| `ipfs_kit_py/core/wal/segments.py` | segment durability primitives | integrity_durability |
| `ipfs_kit_py/core/wal/compatibility.py` | migration bridge | structural |

### CAS candidates

| Path | Role | Classification |
| --- | --- | --- |
| `ipfs_kit_py/mcp_server/mcplusplus/coordination_storage.py` | local-first block CAS | integrity_durable_block_store |
| `ipfs_kit_py/core/vfs/storage.py` | ranged VFS staged storage boundary | integrity_storage_boundary |
| `ipfs_kit_py/proof_certificate_store.py` | opt-in local/IPFS certificate CAS | integrity_transport |
| `ipfs_kit_py.proof_seal_store` | proposed current-seal store | **planned_absent** |

### Legacy / non-authority surfaces

| Path | Role | Classification |
| --- | --- | --- |
| `ipfs_kit_py/wal.py` | legacy operation WAL | legacy_not_proof_seal_authority |
| `ipfs_kit_py/storage_wal.py` | legacy storage WAL | legacy_not_proof_seal_authority |
| `ipfs_kit_py/enhanced_wal_durability.py` | legacy DurableWAL | legacy_not_proof_seal_authority |
| `ipfs_kit_py/merkle_clock.py` | P2P workflow Merkle clock | structural_not_proof_seal_authority |

## Focused tests (repository-relative)

| Command id (operator pin only) | Path | Classification |
| --- | --- | --- |
| kit-proof-certificate | `tests/test_proof_certificate_store.py` | integrity_only |
| kit-reuse-capabilities | `tests/test_reuse_capabilities.py` | structural |
| kit-profile-d | `tests/test_profile_d_policy.py` | structural |
| kit-coordination | `tests/test_coordination_storage.py` | integrity_only |
| kit-modern-wal | `tests/runtime_readiness/wal/test_wal_contracts.py`, `test_wal_recovery.py`, `test_wal_writer.py`, `test_joined_crash_matrix.py` | integrity_corruption_recovery |
| kit-proof-reuse-bootstrap | `tests/test_proof_reuse_bootstrap.py` | structural_optional_plugin |
| kit-agent-receipts | `tests/test_agent_supervisor_receipts.py` | structural |
| kit-iroh-release | `tests/test_iroh_release_readiness.py` | structural_release_evidence |
| kit-release-receipt | `tests/runtime_readiness/release/test_joined_release_receipt.py` | structural_release_evidence |

Each focused test is labeled integrity/structural/mock/real from source shape.
Kit has **no** real-proving suite and **no** cryptographically signed execution receipt
in the inspected surfaces.

## Corruption and recovery behavior (static)

- Modern WAL recovery replays only fully committed transactions and raises on
  irreconcilable segment/record corruption.
- Coordination storage fails closed on CID mismatch and can rebuild indexes from
  immutable blocks without deleting content-addressed artifacts.
- Certificate transport rejects hash mismatches, symlinks, path escape, and
  oversize responses as typed misses or integrity rejections.

## Recursion, keys, and download status

| Concern | Static status |
| --- | --- |
| Recursive verifier | absent |
| Direct-execution proving | absent |
| Cryptographically signed execution receipts | absent |
| Filecoin proving-parameter download | opt-in via `install_lotus.download_params` |
| Auto-install Lotus deps default | false |

## Ownership candidates

Kit remains the storage authority for strict CID transport, modern WAL
durability, hermetic local store candidates, and (when implemented) seal-store
CAS. Proposed package for incremental seal storage:

`ipfs_kit_py.proof_seal_store` (**planned-but-absent**)

Datasets remains semantic acceptance authority; accelerate remains proving
orchestration authority. This inventory does not invent a second proof-cache
acceptance path inside kit.

## Machine-readable companion

See `incremental_proof_sealer_inventory.json` in this directory for the full
classification list with `surfaces_found` counts and the exact
`baseline_evidence` reference-only projection.
