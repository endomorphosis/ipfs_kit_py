# External Agent Fabric kit authority surface

Status: reviewed binding for EAAEF-004
Campaign: ExternalAgentAutonomousExecutionFabric
Integration root: `2564aea1ae35061f2165872aff91e8a40801ab7e` (tree `98ab8d00f79ec542032dbbb21a1ea416b983a845`)

This document binds the reusable `ipfs_kit_py` surfaces that the External Agent
Autonomous Execution Fabric may consume. It does not mint a new authority
family, coordinator, or production control plane.

## Bound reusable surfaces

| Surface | Package | Production role |
|---|---|---|
| Artifact store | `ipfs_kit_py.adversarial_assurance_store` | Immutable assurance artifacts, campaign receipts, Merkle roots, and policy CAS over DurableCoordinationStore. Kit stores bytes and CIDs; it does not redefine datasets identity or signatures. |
| Semantic-root store | `ipfs_kit_py.semantic_governor_store` | Durable semantic-governor artifacts, histories, and promotion CAS. Callers supply verified CIDs; the store is not a second receipt hierarchy. |
| Proof sealer | `ipfs_kit_py.proof_seal_store` | Hermetic storage of proof-seal artifacts, cache candidates, and current-seal pointers. Kit never decides proof validity, execution success, or reuse acceptance. |
| MCP++ adapter | `ipfs_kit_py.mcp_server.mcplusplus` | Spec-owned MCP++ profiles, durable state-root facade, coordination storage, and envelope adapters. Durable state roots are a thin facade over an injected coordination store. |

Exact origin/main already contains these lineages. Unmerged historical proof-API
restorations, subprocess wrappers, and dirty coordination-CAS overlays remain
classified as non-production and must not be merged wholesale.

## Profile-G coordinator exclusion

`ipfs_kit_py.mcp_server.mcplusplus.profile_g` is an in-process
`RuntimeProfileG@1` fencing helper for claim leases, logical epochs, and stale
completion rejection. It is a demo/validator coordination adapter.

It is **not** production authority for:

- current claims, leases, fences, or merge decisions
- opening or owning the authoritative DuckDB file
- substituting for the fenced authenticated Quack owner/service
- DuckLake history/analytics projections used as live coordination

Mutable coordination remains DuckDB transactional records plus one fenced
authenticated Quack file owner. DuckLake, Parquet, IPLD, CAR, and optional IPFS
projections are immutable history only.

## Prohibited substitutions

- Do not treat `profile_g.py` or `profile_g_transport.py` as the EAAEF control plane.
- Do not import stale proof-sealer restoration branches as current reuse authority.
- Do not overwrite the preserved dirty `coordination_storage.py` overlay.
- Do not invent a second in-process Profile-G production coordinator.
