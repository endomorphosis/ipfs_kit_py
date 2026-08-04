# IPFS Kit documentation and architecture task board

Executable projection of
[`ipfs_kit_documentation.objectives.md`](./ipfs_kit_documentation.objectives.md)
and [`../documentation_plan.md`](../documentation_plan.md).

This is the sole active board for program namespace
`ipfs-kit-documentation-architecture-v2`.

## Execution policy

- Task headings use prefix `## KDOC-` and end in a numeric identifier. With
  four strict shards, the trailing number modulo four assigns the lane.
- All implementation outputs are under `docs/`. Source, tests, workflows, and
  packaging files are read-only evidence unless a later, separately authorized
  program expands scope.
- `docs/documentation_plan.md`, this board, and the companion objective heap
  are protected operator inputs and are never task outputs.
- Every worker reads the human plan, the relevant goal, current source, focused
  tests, and nearby docs before writing.
- Existing prose is not proof. Conflicts are recorded as unresolved and linked
  to proposed ADRs; agents do not invent maintainer decisions.
- `IPFS_KIT_AUTO_INSTALL_BINARIES=0` applies to all checks. Do not fetch
  external documentation submodules or require live network services.
- Shared navigation is changed only by KDOC-060. Generated API output is owned
  only by KDOC-046. Historical source families are curated only by KDOC-045.
- Validation is run on the candidate worktree and again on the merged target.

## Parallel waves

```text
Wave 0  KDOC-001..006  evidence, authority, standard, vocabulary
Wave 1  KDOC-010..019  architecture guides (parallel subsystem ownership)
        KDOC-030..039  current user/operator docs (parallel file ownership)
        KDOC-040..044  history/generated/external classification
Wave 2  KDOC-020..029  ADRs (parallel, after supporting guide/evidence)
        KDOC-045..046  curated history + generated refresh
Wave 3  KDOC-050..054  agent guidance + repeatable maintenance/validation
Wave 4  KDOC-060..062  exclusive navigation, final audit, scorecard
```

## KDOC-001 Inventory and classify the documentation corpus

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: evidence-corpus
- Depends on:
- Goal id: KDOC-G011
- Outputs: docs/audits/DOCUMENTATION_INVENTORY.md
- Validation: test -s docs/audits/DOCUMENTATION_INVENTORY.md && rg -q "Authority class" docs/audits/DOCUMENTATION_INVENTORY.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/evidence-corpus
- Parallel lane: kdoc-evidence-corpus
- Resource class: io-static-analysis
- Token class: medium
- Estimated tokens: 10000
- Predicted files: docs/audits/DOCUMENTATION_INVENTORY.md
- Allow concurrent with: KDOC-002, KDOC-003, KDOC-004, KDOC-005, KDOC-006
- Conflict policy: Own only the inventory; do not move or rewrite inventoried files.
- Preconditions: Current docs tree is readable; external gitlinks remain uninitialized.
- Effects: Record reproducible counts, top-level families, maintained/generated/historical/external candidates, competing indexes, embedded projects, and exclusions.
- Acceptance: Every top-level docs family has an authority-class proposal, freshness risk, owner/disposition, and reproducible evidence command; no external content is fetched.

## KDOC-002 Map public interfaces, entry points, and exposed capabilities

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: evidence-surfaces
- Depends on:
- Goal id: KDOC-G012
- Outputs: docs/audits/PUBLIC_SURFACE_MATRIX.md
- Validation: test -s docs/audits/PUBLIC_SURFACE_MATRIX.md && rg -q "pyproject.toml" docs/audits/PUBLIC_SURFACE_MATRIX.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/evidence-surfaces
- Parallel lane: kdoc-evidence-surfaces
- Resource class: cpu-static-analysis
- Token class: large
- Estimated tokens: 14000
- Predicted files: docs/audits/PUBLIC_SURFACE_MATRIX.md
- Allow concurrent with: KDOC-001, KDOC-003, KDOC-004, KDOC-005, KDOC-006
- Conflict policy: Read source/tests; write only the matrix.
- Preconditions: Inspect packaging metadata, root exports, parsers, registries, and focused tests without installing optional services.
- Effects: Map Python exports, console scripts, CLI commands, MCP/JSON-RPC/FastMCP/SDK surfaces, filesystem protocols, backend plugins, and daemon/service entry points.
- Acceptance: Each surface lists entry path, implementation authority/status, optional requirements, focused tests, known drift, and documentation owner; version/export/tool-count conflicts remain explicit.

## KDOC-003 Audit freshness and implementation change since prior documentation

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: evidence-corpus
- Depends on:
- Goal id: KDOC-G011
- Outputs: docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md
- Validation: test -s docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md && rg -q "2026-08-03" docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/evidence-freshness
- Parallel lane: kdoc-evidence-freshness
- Resource class: io-git-analysis
- Token class: large
- Estimated tokens: 14000
- Predicted files: docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md
- Allow concurrent with: KDOC-001, KDOC-002, KDOC-004, KDOC-005, KDOC-006
- Conflict policy: Audit only; do not fix target documents in this task.
- Preconditions: Compare current source/docs/history with the February 2026 overhaul and July 2026 reachability campaign.
- Effects: Prioritize stale claims, missing architecture topics, invalid commands/APIs, generated drift, workflow contradictions, and documentation change triggers.
- Acceptance: Findings include severity, exact document, contradicting source/test/history evidence, recommended owner/task, and no vague unsupported freshness claims.

## KDOC-004 Build the architectural source-of-truth and test map

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: evidence-surfaces
- Depends on:
- Goal id: KDOC-G012
- Outputs: docs/architecture/SOURCE_OF_TRUTH_MAP.md
- Validation: test -s docs/architecture/SOURCE_OF_TRUTH_MAP.md && rg -q "Unresolved" docs/architecture/SOURCE_OF_TRUTH_MAP.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/evidence-architecture
- Parallel lane: kdoc-evidence-architecture
- Resource class: cpu-static-analysis
- Token class: large
- Estimated tokens: 16000
- Predicted files: docs/architecture/SOURCE_OF_TRUTH_MAP.md
- Allow concurrent with: KDOC-001, KDOC-002, KDOC-003, KDOC-005, KDOC-006
- Conflict policy: Own only the source map; do not decide disputed authority.
- Preconditions: Inspect canonical-looking and parallel implementation families plus focused tests/workflows.
- Effects: Map runtime/import, storage/backend, content/VFS/durability, cluster/network, MCP/control-plane, configuration/security, and generated-doc evidence.
- Acceptance: Each subsystem lists candidate authority, compatibility/historical paths, focused tests, current docs, gaps, and unresolved owner decisions.

## KDOC-005 Establish documentation lifecycle, evidence, and style rules

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: governance
- Depends on:
- Goal id: KDOC-G013
- Outputs: docs/guides/DOCUMENTATION_GUIDE.md
- Validation: test -s docs/guides/DOCUMENTATION_GUIDE.md && rg -q "Proposed" docs/guides/DOCUMENTATION_GUIDE.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/governance
- Parallel lane: kdoc-governance
- Resource class: cpu-small
- Token class: medium
- Estimated tokens: 10000
- Predicted files: docs/guides/DOCUMENTATION_GUIDE.md
- Allow concurrent with: KDOC-001, KDOC-002, KDOC-003, KDOC-004, KDOC-006
- Conflict policy: Replace/update only the documentation guide; do not edit navigation.
- Preconditions: Human plan contract is authoritative.
- Effects: Define current/generated/historical/external/proposed classes, provenance fields, evidence ranking, rationale confidence, required architecture sections, examples, diagrams, links, accessibility, security, and review triggers.
- Acceptance: The guide makes accepted, proposed, inferred, and unknown rationale distinguishable and provides review checklists for humans and agents.

## KDOC-006 Create the shared architecture glossary

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: governance
- Depends on:
- Goal id: KDOC-G013
- Outputs: docs/architecture/GLOSSARY.md
- Validation: test -s docs/architecture/GLOSSARY.md && rg -q "content address" docs/architecture/GLOSSARY.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/vocabulary
- Parallel lane: kdoc-vocabulary
- Resource class: cpu-small
- Token class: medium
- Estimated tokens: 8000
- Predicted files: docs/architecture/GLOSSARY.md
- Allow concurrent with: KDOC-001, KDOC-002, KDOC-003, KDOC-004, KDOC-005
- Conflict policy: Own glossary only; flag ambiguous terms instead of redefining implementation contracts.
- Preconditions: Inspect source names and existing normative Iroh/VFS/coordination docs.
- Effects: Define backend, adapter, service, daemon, node role, CID, manifest, bucket, VFS, WAL, journal, index, registry, tool surface, receipt, authoritative state, rebuildable state, and compatibility layer.
- Acceptance: Terms are implementation-linked, distinguish commonly conflated concepts, and identify unresolved vocabulary.

## KDOC-010 Write the system context and end-to-end overview

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: arch-runtime
- Depends on: KDOC-002, KDOC-004, KDOC-005, KDOC-006
- Goal id: KDOC-G021
- Outputs: docs/architecture/SYSTEM_OVERVIEW.md
- Validation: test -s docs/architecture/SYSTEM_OVERVIEW.md && rg -q "Trust boundaries" docs/architecture/SYSTEM_OVERVIEW.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/arch-runtime
- Parallel lane: kdoc-arch-runtime
- Resource class: cpu-analysis
- Token class: large
- Estimated tokens: 16000
- Predicted files: docs/architecture/SYSTEM_OVERVIEW.md
- Allow concurrent with: KDOC-013, KDOC-014, KDOC-015, KDOC-016, KDOC-017, KDOC-018, KDOC-019
- Conflict policy: Own system overview only; subsystem details remain with their guide owners.
- Preconditions: Evidence maps and documentation contract complete.
- Effects: Describe actors, external systems, package/runtime containers, primary data/control flows, trust boundaries, supported deployment shapes, failure domains, and reading order.
- Acceptance: Overview is evidence-linked, uses bounded diagrams, distinguishes storage data plane from control plane, and links instead of duplicating subsystem detail.

## KDOC-011 Document runtime composition and entry points

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: arch-runtime
- Depends on: KDOC-002, KDOC-004, KDOC-005
- Goal id: KDOC-G021
- Outputs: docs/architecture/RUNTIME_AND_ENTRYPOINTS.md
- Validation: test -s docs/architecture/RUNTIME_AND_ENTRYPOINTS.md && rg -q "ipfs-kit-mcp" docs/architecture/RUNTIME_AND_ENTRYPOINTS.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/arch-entrypoints
- Parallel lane: kdoc-arch-runtime
- Resource class: cpu-analysis
- Token class: large
- Estimated tokens: 14000
- Predicted files: docs/architecture/RUNTIME_AND_ENTRYPOINTS.md
- Allow concurrent with: KDOC-010, KDOC-013, KDOC-014, KDOC-015, KDOC-016, KDOC-017, KDOC-018, KDOC-019
- Conflict policy: Own runtime/entrypoint guide; do not resolve disputed MCP/API authority.
- Preconditions: Public surface matrix identifies every installed console script and major Python entry path.
- Effects: Trace import, Python API, CLI dispatcher, service/daemon, MCP++, FastMCP, JSON-RPC, SDK, FSSpec, and installer startup/lifecycle.
- Acceptance: For each entry point, document process/event-loop ownership, initialization, state/config dependencies, optional degradation, shutdown, and source/tests.

## KDOC-012 Classify canonical, compatibility, experimental, and historical code paths

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: arch-runtime
- Depends on: KDOC-001, KDOC-002, KDOC-003, KDOC-004, KDOC-005
- Goal id: KDOC-G021
- Outputs: docs/architecture/COMPATIBILITY_LAYERS.md
- Validation: test -s docs/architecture/COMPATIBILITY_LAYERS.md && rg -q "Unresolved authority" docs/architecture/COMPATIBILITY_LAYERS.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/arch-compatibility
- Parallel lane: kdoc-arch-runtime
- Resource class: cpu-static-analysis
- Token class: large
- Estimated tokens: 16000
- Predicted files: docs/architecture/COMPATIBILITY_LAYERS.md
- Allow concurrent with: KDOC-010, KDOC-013, KDOC-014, KDOC-015, KDOC-016, KDOC-017, KDOC-018, KDOC-019
- Conflict policy: Classification only; do not delete, rename, or promote code.
- Preconditions: Inventories include backup/fixed/new/broken and competing package/module forms.
- Effects: Provide an allowlist-oriented map for docs generation and human/agent navigation.
- Acceptance: Root exports, high-level APIs, three IPFS client families, MCP stacks, cluster families, AnyIO variants, and tracked inactive artifacts have status/evidence or an explicit unresolved owner decision.

## KDOC-013 Document backend plugins, named configuration, and live adapters

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: arch-storage
- Depends on: KDOC-002, KDOC-004, KDOC-005, KDOC-006
- Goal id: KDOC-G022
- Outputs: docs/architecture/STORAGE_BACKEND_SYSTEM.md
- Validation: test -s docs/architecture/STORAGE_BACKEND_SYSTEM.md && rg -q "BackendTypeRegistry" docs/architecture/STORAGE_BACKEND_SYSTEM.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/arch-storage-backends
- Parallel lane: kdoc-arch-storage
- Resource class: cpu-analysis
- Token class: large
- Estimated tokens: 16000
- Predicted files: docs/architecture/STORAGE_BACKEND_SYSTEM.md
- Allow concurrent with: KDOC-010, KDOC-014, KDOC-015, KDOC-016, KDOC-017, KDOC-018, KDOC-019
- Conflict policy: Own backend architecture guide; Iroh/network transport detail belongs to KDOC-016.
- Preconditions: Distinguish registry configuration plugins from live storage adapter instances.
- Effects: Explain discovery, validation/migration, atomic config, capabilities/health, redaction, adapter creation, extension points, and degraded/unknown backend behavior.
- Acceptance: Guide prevents import-time side effects and secret leakage, identifies schema-validated versus legacy plugins, and includes a safe extension walkthrough grounded in tests.

## KDOC-014 Document content, metadata, cache, bucket, VFS, WAL, and journal flow

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: arch-storage
- Depends on: KDOC-004, KDOC-005, KDOC-006
- Goal id: KDOC-G022
- Outputs: docs/architecture/CONTENT_METADATA_VFS.md
- Validation: test -s docs/architecture/CONTENT_METADATA_VFS.md && rg -q "Recovery" docs/architecture/CONTENT_METADATA_VFS.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/arch-content-vfs
- Parallel lane: kdoc-arch-storage
- Resource class: cpu-analysis
- Token class: xlarge
- Estimated tokens: 20000
- Predicted files: docs/architecture/CONTENT_METADATA_VFS.md
- Allow concurrent with: KDOC-010, KDOC-013, KDOC-015, KDOC-016, KDOC-017, KDOC-018, KDOC-019
- Conflict policy: Own content/VFS architecture guide only.
- Preconditions: Inspect content manager, pin/bucket/VFS APIs, cache tiers, Arrow/Parquet indexes, storage WAL, CAR WAL, filesystem journal/replication, and VFS contract tests.
- Effects: Trace write/read/mutate/delete/recovery paths and distinguish bytes, content identity, metadata, indexes, intent logs, journals, and replicas.
- Acceptance: Authoritative versus rebuildable state, ordering/atomicity, conflict policy, sync lineage, cache behavior, failure modes, and extension points are explicit and test-linked.

## KDOC-015 Document cluster roles, coordination, consistency, and replication

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: arch-distributed
- Depends on: KDOC-002, KDOC-004, KDOC-005, KDOC-006
- Goal id: KDOC-G023
- Outputs: docs/architecture/CLUSTER_COORDINATION.md
- Validation: test -s docs/architecture/CLUSTER_COORDINATION.md && rg -q "Consistency" docs/architecture/CLUSTER_COORDINATION.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/arch-cluster
- Parallel lane: kdoc-arch-distributed
- Resource class: cpu-analysis
- Token class: xlarge
- Estimated tokens: 20000
- Predicted files: docs/architecture/CLUSTER_COORDINATION.md
- Allow concurrent with: KDOC-010, KDOC-013, KDOC-014, KDOC-016, KDOC-017, KDOC-018, KDOC-019
- Conflict policy: Own cluster guide; proposed authority decision belongs to KDOC-028.
- Preconditions: Compare cluster/ and top-level cluster/coordinator/state implementations, Kubo Cluster wrappers, role managers, and tests.
- Effects: Explain roles/capabilities, membership, leader/task/state flow, Arrow snapshots, vector-clock/CRDT-like paths, replication, health, partition/recovery behavior, and unresolved inconsistencies.
- Acceptance: Guide does not select a canonical cluster control plane without evidence and documents the observed API mismatch as a decision/follow-up.

## KDOC-016 Document Kubo, Iroh, libp2p, routing, and P2P workflow boundaries

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: arch-distributed
- Depends on: KDOC-002, KDOC-004, KDOC-005, KDOC-006
- Goal id: KDOC-G023
- Outputs: docs/architecture/NETWORK_TRANSPORTS.md
- Validation: test -s docs/architecture/NETWORK_TRANSPORTS.md && rg -q "Iroh" docs/architecture/NETWORK_TRANSPORTS.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/arch-network
- Parallel lane: kdoc-arch-distributed
- Resource class: cpu-analysis
- Token class: large
- Estimated tokens: 18000
- Predicted files: docs/architecture/NETWORK_TRANSPORTS.md
- Allow concurrent with: KDOC-010, KDOC-013, KDOC-014, KDOC-015, KDOC-017, KDOC-018, KDOC-019
- Conflict policy: Own network architecture guide; do not rewrite normative docs/iroh contracts.
- Preconditions: Treat protocol, storage backend, FSSpec, RPC sidecar, routing, and workflow coordination as separate roles.
- Effects: Map Kubo/IPFS clients and managed runtime, Iroh blob/manifest/service/GC/tiering, libp2p protocols, routing, and P2P workflow exposure.
- Acceptance: Guide states actual CLI/MCP/Python exposure, transport/security/lifecycle boundaries, interoperability limits, failure modes, and why coexistence is used or still proposed.

## KDOC-017 Document MCP++ and the multi-interface control plane

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: arch-control
- Depends on: KDOC-002, KDOC-004, KDOC-005, KDOC-006
- Goal id: KDOC-G024
- Outputs: docs/architecture/MCP_CONTROL_PLANE.md
- Validation: test -s docs/architecture/MCP_CONTROL_PLANE.md && rg -q "TOOL_GROUPS" docs/architecture/MCP_CONTROL_PLANE.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/arch-mcp
- Parallel lane: kdoc-arch-control
- Resource class: cpu-analysis
- Token class: xlarge
- Estimated tokens: 20000
- Predicted files: docs/architecture/MCP_CONTROL_PLANE.md
- Allow concurrent with: KDOC-010, KDOC-013, KDOC-014, KDOC-015, KDOC-016, KDOC-018, KDOC-019
- Conflict policy: Own MCP architecture guide; do not change registries/SDK code or decide legacy authority.
- Preconditions: Inspect mcp_server and legacy mcp stacks, packaging entry points, registry/manifests, transports, coordination blocks/indexes, receipts, and conformance tests.
- Effects: Explain one registry/multiple surfaces, schema/dispatch flow, meta-tools, request IDs/circuit breakers, Trio transport, immutable DAG-JSON plus rebuildable SQLite indexes, fail-closed receipts, degradation, and SDK drift.
- Acceptance: Current and compatibility stacks are explicit, measured tool counts replace prose counts, and the proposed MCP authority ADR is linked.

## KDOC-018 Document async boundaries, lazy imports, and optional capabilities

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: arch-trust
- Depends on: KDOC-002, KDOC-004, KDOC-005, KDOC-006
- Goal id: KDOC-G025
- Outputs: docs/architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md
- Validation: test -s docs/architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md && rg -q "AnyIO" docs/architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/arch-async-deps
- Parallel lane: kdoc-arch-trust
- Resource class: cpu-static-analysis
- Token class: large
- Estimated tokens: 18000
- Predicted files: docs/architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md
- Allow concurrent with: KDOC-010, KDOC-013, KDOC-014, KDOC-015, KDOC-016, KDOC-017, KDOC-019
- Conflict policy: Own async/dependency guide; do not claim migration completion from filename counts.
- Preconditions: Inspect AnyIO, Trio, deliberate asyncio.run sites, sync wrappers/thread offload, lazy loaders, extras, and import-safety tests.
- Effects: Publish runtime/cancellation/context/thread-offload matrix and capability detection/degraded behavior.
- Acceptance: Guide replaces invalid AnyIO examples, identifies supported sync/async boundaries, avoids event-loop nesting advice, and explains no-import-time-download intent.

## KDOC-019 Document configuration, state, credentials, trust, and process lifecycle

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: arch-trust
- Depends on: KDOC-002, KDOC-004, KDOC-005, KDOC-006
- Goal id: KDOC-G025
- Outputs: docs/architecture/CONFIGURATION_STATE_AND_TRUST.md
- Validation: test -s docs/architecture/CONFIGURATION_STATE_AND_TRUST.md && rg -q "Secret" docs/architecture/CONFIGURATION_STATE_AND_TRUST.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/arch-config-trust
- Parallel lane: kdoc-arch-trust
- Resource class: cpu-analysis
- Token class: xlarge
- Estimated tokens: 20000
- Predicted files: docs/architecture/CONFIGURATION_STATE_AND_TRUST.md
- Allow concurrent with: KDOC-010, KDOC-013, KDOC-014, KDOC-015, KDOC-016, KDOC-017, KDOC-018
- Conflict policy: Own config/state/trust guide; never expose actual local credentials.
- Preconditions: Inspect configuration managers, backend atomic writes/redaction, credential/secret references, installers, managed/system daemons, readiness/locks, telemetry and Iroh security/lifecycle contracts.
- Effects: Map precedence, directories, schemas, permissions, redaction, trust boundaries, process ownership, start/readiness/stop/update, health, logs, and recovery.
- Acceptance: Every sensitive or mutable state family has owner, location rule, permissions, lifecycle, failure behavior, and safe diagnostic guidance; binary install remains explicit opt-in.

## KDOC-020 Create the ADR process, template, and index

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: decisions-framework
- Depends on: KDOC-005
- Goal id: KDOC-G031
- Outputs: docs/architecture/decisions/README.md, docs/architecture/decisions/0000-template.md
- Validation: test -s docs/architecture/decisions/README.md && test -s docs/architecture/decisions/0000-template.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/adrs-framework
- Parallel lane: kdoc-adrs
- Resource class: cpu-small
- Token class: medium
- Estimated tokens: 8000
- Predicted files: docs/architecture/decisions/README.md, docs/architecture/decisions/0000-template.md
- Allow concurrent with: current-document tasks with satisfied prerequisites
- Conflict policy: Own ADR framework/index and pre-register every planned ADR link; later ADR tasks own only their numbered files and must not edit the index.
- Preconditions: Documentation evidence/status vocabulary exists.
- Effects: Define proposed, accepted, rejected, superseded, deprecated, and unknown statuses plus evidence/confidence, consequences, alternatives, confirmation, supersession, and review rules.
- Acceptance: Template prevents inferred rationale from masquerading as accepted history and index can expose unresolved owner decisions.

## KDOC-021 Record the lazy import and optional dependency decision

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: decisions
- Depends on: KDOC-018, KDOC-020
- Goal id: KDOC-G032
- Outputs: docs/architecture/decisions/0001-imports-and-optional-dependencies.md
- Validation: test -s docs/architecture/decisions/0001-imports-and-optional-dependencies.md && rg -q "Consequences" docs/architecture/decisions/0001-imports-and-optional-dependencies.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/adr-0001
- Parallel lane: kdoc-adrs
- Resource class: cpu-analysis
- Token class: medium
- Estimated tokens: 9000
- Predicted files: docs/architecture/decisions/0001-imports-and-optional-dependencies.md
- Allow concurrent with: KDOC-022, KDOC-023, KDOC-024, KDOC-025, KDOC-026, KDOC-027, KDOC-028, KDOC-029
- Conflict policy: Own ADR 0001 only.
- Preconditions: Async/dependency guide and ADR template complete.
- Effects: Record evidence for lazy proxies, import safety, capability detection, stubs/degradation, no implicit binary download, and accepted trade-offs or unknown rationale.
- Acceptance: ADR distinguishes verified constraints from inferred intent and names rejected/evaluated alternatives and testing consequences.

## KDOC-022 Record the backend configuration-plugin registry decision

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: decisions
- Depends on: KDOC-013, KDOC-020
- Goal id: KDOC-G032
- Outputs: docs/architecture/decisions/0002-backend-plugin-registry.md
- Validation: test -s docs/architecture/decisions/0002-backend-plugin-registry.md && rg -q "live" docs/architecture/decisions/0002-backend-plugin-registry.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/adr-0002
- Parallel lane: kdoc-adrs
- Resource class: cpu-analysis
- Token class: medium
- Estimated tokens: 9000
- Predicted files: docs/architecture/decisions/0002-backend-plugin-registry.md
- Allow concurrent with: KDOC-021, KDOC-023, KDOC-024, KDOC-025, KDOC-026, KDOC-027, KDOC-028, KDOC-029
- Conflict policy: Own ADR 0002 only.
- Preconditions: Backend architecture guide and ADR template complete.
- Effects: Record why discovery/config validation is side-effect-free and separate from live adapter instances, including legacy plugin trade-offs.
- Acceptance: ADR covers context, evidence, alternatives, consequences, extension/security implications, and status confidence.

## KDOC-023 Draft the MCP runtime authority and single-registry decision

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: decisions
- Depends on: KDOC-017, KDOC-020
- Goal id: KDOC-G032
- Outputs: docs/architecture/decisions/0003-mcp-runtime-authority.md
- Validation: test -s docs/architecture/decisions/0003-mcp-runtime-authority.md && rg -q "Status: Proposed" docs/architecture/decisions/0003-mcp-runtime-authority.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/adr-0003
- Parallel lane: kdoc-adrs
- Resource class: cpu-analysis
- Token class: large
- Estimated tokens: 12000
- Predicted files: docs/architecture/decisions/0003-mcp-runtime-authority.md
- Allow concurrent with: KDOC-021, KDOC-022, KDOC-024, KDOC-025, KDOC-026, KDOC-027, KDOC-028, KDOC-029
- Conflict policy: Own ADR 0003 only; do not promote proposed authority without maintainer confirmation.
- Preconditions: MCP guide documents packaging/runtime/doc conflicts.
- Effects: Present evidence and options for mcp_server/MCP++ versus legacy mcp authority while separately recording the implemented one-registry/multiple-surface invariant.
- Acceptance: ADR remains proposed, lists migration/compatibility consequences and a confirmation owner, and does not rewrite disputed docs as resolved.

## KDOC-024 Record AnyIO, Trio, asyncio, and sync boundary decisions

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: decisions
- Depends on: KDOC-018, KDOC-020
- Goal id: KDOC-G032
- Outputs: docs/architecture/decisions/0004-anyio-and-sync-boundaries.md
- Validation: test -s docs/architecture/decisions/0004-anyio-and-sync-boundaries.md && rg -q "Cancellation" docs/architecture/decisions/0004-anyio-and-sync-boundaries.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/adr-0004
- Parallel lane: kdoc-adrs
- Resource class: cpu-analysis
- Token class: medium
- Estimated tokens: 10000
- Predicted files: docs/architecture/decisions/0004-anyio-and-sync-boundaries.md
- Allow concurrent with: KDOC-021, KDOC-022, KDOC-023, KDOC-025, KDOC-026, KDOC-027, KDOC-028, KDOC-029
- Conflict policy: Own ADR 0004 only.
- Preconditions: Runtime matrix is evidence-backed.
- Effects: Record portable AnyIO/Trio goals and deliberate sync/asyncio compatibility boundaries, cancellation/thread-offload consequences, and rejected universal-conversion claims.
- Acceptance: ADR reflects current mixed runtime honestly and identifies decisions still needing owner confirmation.

## KDOC-025 Record content-addressed state, metadata indexes, WAL, and journal decisions

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: decisions
- Depends on: KDOC-014, KDOC-020
- Goal id: KDOC-G032
- Outputs: docs/architecture/decisions/0005-content-metadata-and-durability.md
- Validation: test -s docs/architecture/decisions/0005-content-metadata-and-durability.md && rg -q "rebuild" docs/architecture/decisions/0005-content-metadata-and-durability.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/adr-0005
- Parallel lane: kdoc-adrs
- Resource class: cpu-analysis
- Token class: large
- Estimated tokens: 12000
- Predicted files: docs/architecture/decisions/0005-content-metadata-and-durability.md
- Allow concurrent with: KDOC-021, KDOC-022, KDOC-023, KDOC-024, KDOC-026, KDOC-027, KDOC-028, KDOC-029
- Conflict policy: Own ADR 0005 only.
- Preconditions: Data lifecycle guide establishes observed authority and ordering.
- Effects: Record the separation of immutable/content-addressed facts, mutable manifests/state, rebuildable indexes, WAL intent, filesystem journal history, and CAR packaging.
- Acceptance: ADR states durability/consistency consequences, failure recovery, alternatives, and confidence for each observed design choice.

## KDOC-026 Record multi-protocol storage and networking coexistence

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: decisions
- Depends on: KDOC-016, KDOC-020
- Goal id: KDOC-G032
- Outputs: docs/architecture/decisions/0006-multi-protocol-storage-and-networking.md
- Validation: test -s docs/architecture/decisions/0006-multi-protocol-storage-and-networking.md && rg -q "Iroh" docs/architecture/decisions/0006-multi-protocol-storage-and-networking.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/adr-0006
- Parallel lane: kdoc-adrs
- Resource class: cpu-analysis
- Token class: medium
- Estimated tokens: 10000
- Predicted files: docs/architecture/decisions/0006-multi-protocol-storage-and-networking.md
- Allow concurrent with: KDOC-021, KDOC-022, KDOC-023, KDOC-024, KDOC-025, KDOC-027, KDOC-028, KDOC-029
- Conflict policy: Own ADR 0006 only.
- Preconditions: Network architecture guide distinguishes storage, transport, routing, and workflow roles.
- Effects: Record evidence and trade-offs for Kubo/IPFS, Iroh sidecar/blob, libp2p, and remote-backend coexistence rather than one universal backend.
- Acceptance: ADR identifies capability/consistency/security/lifecycle trade-offs and labels inferred motivations.

## KDOC-027 Record local atomic configuration and secret-reference decisions

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: decisions
- Depends on: KDOC-019, KDOC-020
- Goal id: KDOC-G032
- Outputs: docs/architecture/decisions/0007-configuration-state-and-secret-references.md
- Validation: test -s docs/architecture/decisions/0007-configuration-state-and-secret-references.md && rg -q "redact" docs/architecture/decisions/0007-configuration-state-and-secret-references.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/adr-0007
- Parallel lane: kdoc-adrs
- Resource class: cpu-analysis
- Token class: medium
- Estimated tokens: 10000
- Predicted files: docs/architecture/decisions/0007-configuration-state-and-secret-references.md
- Allow concurrent with: KDOC-021, KDOC-022, KDOC-023, KDOC-024, KDOC-025, KDOC-026, KDOC-028, KDOC-029
- Conflict policy: Own ADR 0007 only.
- Preconditions: Config/trust guide maps actual atomic write, permissions, backup, reference, and redaction behavior.
- Effects: Record configuration locality/precedence, JSON-compatible validation, atomic replace, mode 0600, backup/migration, and secret-reference/redaction choices.
- Acceptance: ADR includes threats, consequences, alternatives, limitations, and no credential examples.

## KDOC-028 Draft the cluster control-plane authority decision

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: decisions
- Depends on: KDOC-015, KDOC-020
- Goal id: KDOC-G032
- Outputs: docs/architecture/decisions/0008-cluster-control-plane-authority.md
- Validation: test -s docs/architecture/decisions/0008-cluster-control-plane-authority.md && rg -q "Status: Proposed" docs/architecture/decisions/0008-cluster-control-plane-authority.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/adr-0008
- Parallel lane: kdoc-adrs
- Resource class: cpu-analysis
- Token class: large
- Estimated tokens: 12000
- Predicted files: docs/architecture/decisions/0008-cluster-control-plane-authority.md
- Allow concurrent with: KDOC-021, KDOC-022, KDOC-023, KDOC-024, KDOC-025, KDOC-026, KDOC-027, KDOC-029
- Conflict policy: Own ADR 0008 only; do not choose among competing cluster families.
- Preconditions: Cluster guide records competing implementations, consistency models, entry points, and mismatch evidence.
- Effects: Present authority options, compatibility/migration consequences, required tests, and owner decision request.
- Acceptance: ADR remains proposed and provides enough evidence for a maintainer decision without hiding current ambiguity.

## KDOC-029 Draft the canonical documentation site/toolchain decision

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: decisions
- Depends on: KDOC-003, KDOC-020
- Goal id: KDOC-G032
- Outputs: docs/architecture/decisions/0009-documentation-site-toolchain.md
- Validation: test -s docs/architecture/decisions/0009-documentation-site-toolchain.md && rg -q "Status: Proposed" docs/architecture/decisions/0009-documentation-site-toolchain.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/adr-0009
- Parallel lane: kdoc-adrs
- Resource class: cpu-analysis
- Token class: medium
- Estimated tokens: 9000
- Predicted files: docs/architecture/decisions/0009-documentation-site-toolchain.md
- Allow concurrent with: KDOC-021, KDOC-022, KDOC-023, KDOC-024, KDOC-025, KDOC-026, KDOC-027, KDOC-028
- Conflict policy: Own ADR 0009 only; repository workflow/config changes are out of scope.
- Preconditions: Freshness audit documents missing Sphinx config, ephemeral MkDocs behavior, and generator contracts.
- Effects: Compare committed MkDocs, Sphinx, lightweight Markdown validation, and generated-reference options plus migration/follow-up requirements.
- Acceptance: ADR remains proposed, names an owner decision, and does not claim either current docs workflow is reproducible.

## KDOC-030 Refresh installation and quick-reference paths

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: current-getting-started
- Depends on: KDOC-002, KDOC-003, KDOC-005, KDOC-011, KDOC-012
- Goal id: KDOC-G041
- Outputs: docs/installation_guide.md, docs/QUICK_REFERENCE.md
- Validation: test -s docs/installation_guide.md && test -s docs/QUICK_REFERENCE.md && rg -q "Python 3.12" docs/installation_guide.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/current-getting-started
- Parallel lane: kdoc-current-api
- Resource class: cpu-doc-validation
- Token class: large
- Estimated tokens: 14000
- Predicted files: docs/installation_guide.md, docs/QUICK_REFERENCE.md
- Allow concurrent with: KDOC-031, KDOC-032, KDOC-033, KDOC-034, KDOC-035, KDOC-036, KDOC-037, KDOC-038, KDOC-039
- Conflict policy: Own only installation and quick reference; do not edit root/navigation files.
- Preconditions: Use package metadata and verified entry points; binary installation remains opt-in.
- Effects: Provide supported base/extras installation, safe first-success checks, daemon/network prerequisites, interface choices, and troubleshooting without nonexistent scripts.
- Acceptance: Commands/imports are statically or offline verified, supported Python/version ambiguity is called out, and no install step triggers an undeclared binary download.

## KDOC-031 Refresh Python and high-level API documentation

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: current-python-api
- Depends on: KDOC-002, KDOC-005, KDOC-011, KDOC-012
- Goal id: KDOC-G041
- Outputs: docs/api/api_reference.md, docs/api/high_level_api.md
- Validation: test -s docs/api/api_reference.md && test -s docs/api/high_level_api.md && rg -q "Compatibility" docs/api/high_level_api.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/current-python-api
- Parallel lane: kdoc-current-api
- Resource class: cpu-static-analysis
- Token class: large
- Estimated tokens: 16000
- Predicted files: docs/api/api_reference.md, docs/api/high_level_api.md
- Allow concurrent with: KDOC-030, KDOC-032, KDOC-033, KDOC-034, KDOC-035, KDOC-036, KDOC-037, KDOC-038, KDOC-039
- Conflict policy: Own two API guides; generated inventory belongs to KDOC-046.
- Preconditions: Public matrix resolves or explicitly records root exports, `ipfs_kit`/`IPFSKit`, `IPFSSimpleAPI`, and client families.
- Effects: Document supported imports, construction, dependency injection, lazy/degraded behavior, sync/async use, return/error shapes, and stability/status.
- Acceptance: Every shown import and signature exists on the current tree or is labeled compatibility/proposed; no implicit singleton or unavailable root export is claimed.

## KDOC-032 Refresh the CLI reference from the live parser

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: current-cli
- Depends on: KDOC-002, KDOC-005, KDOC-011
- Goal id: KDOC-G041
- Outputs: docs/api/cli_reference.md
- Validation: test -s docs/api/cli_reference.md && rg -q "backend" docs/api/cli_reference.md && rg -q "journal" docs/api/cli_reference.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/current-cli
- Parallel lane: kdoc-current-api
- Resource class: cpu-doc-validation
- Token class: large
- Estimated tokens: 14000
- Predicted files: docs/api/cli_reference.md
- Allow concurrent with: KDOC-030, KDOC-031, KDOC-033, KDOC-034, KDOC-035, KDOC-036, KDOC-037, KDOC-038, KDOC-039
- Conflict policy: Own CLI reference only.
- Preconditions: Derive commands/options from cli.py and unified_cli_dispatcher.py without starting services.
- Effects: Cover mcp, daemon, services, autoheal, bucket, vfs, wal, pin, backend, journal, state and installed Iroh console scripts; remove unsupported generic/p2p claims or label separate surfaces.
- Acceptance: Command tree, aliases, configuration, output/error behavior, prerequisites, and help-based verification agree with the live parser.

## KDOC-033 Create a current MCP/MCP++ reference

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: current-mcp
- Depends on: KDOC-017, KDOC-023
- Goal id: KDOC-G041
- Outputs: docs/api/mcp_reference.md
- Validation: test -s docs/api/mcp_reference.md && rg -q "MCP++" docs/api/mcp_reference.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/current-mcp
- Parallel lane: kdoc-current-api
- Resource class: cpu-static-analysis
- Token class: large
- Estimated tokens: 16000
- Predicted files: docs/api/mcp_reference.md
- Allow concurrent with: KDOC-030, KDOC-031, KDOC-032, KDOC-034, KDOC-035, KDOC-036, KDOC-037, KDOC-038, KDOC-039
- Conflict policy: Own MCP reference only; proposed authority remains visibly proposed.
- Preconditions: MCP architecture and ADR describe current/legacy conflict.
- Effects: Document installed entry point, transports, discovery/schema/dispatch, measured tool groups, FastMCP and SDK surfaces, error/degraded semantics, security and conformance checks.
- Acceptance: Reference never hard-codes stale tool counts without generation evidence and gives compatibility guidance without declaring the authority ADR accepted.

## KDOC-034 Refresh backend, configuration, and credential reference

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: current-storage
- Depends on: KDOC-013, KDOC-019, KDOC-022
- Goal id: KDOC-G041
- Outputs: docs/reference/storage_backends.md, docs/credential_management.md
- Validation: test -s docs/reference/storage_backends.md && test -s docs/credential_management.md && rg -q "iroh" docs/reference/storage_backends.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/current-backend-config
- Parallel lane: kdoc-current-storage
- Resource class: cpu-static-analysis
- Token class: large
- Estimated tokens: 16000
- Predicted files: docs/reference/storage_backends.md, docs/credential_management.md
- Allow concurrent with: KDOC-030, KDOC-031, KDOC-032, KDOC-033, KDOC-035, KDOC-036, KDOC-037, KDOC-038, KDOC-039
- Conflict policy: Own backend/credential references only.
- Preconditions: Backend/config guides establish config plugin versus adapter and redaction boundaries.
- Effects: Publish actual types, schema maturity, extras, config fields, secret references, capabilities/health semantics, atomic storage, and safe examples.
- Acceptance: Legacy and schema-validated backends are distinguished; real credentials are never shown; unsupported claimed backends/capabilities are removed or qualified.

## KDOC-035 Refresh VFS, bucket, and filesystem-journal contracts

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: current-storage
- Depends on: KDOC-014, KDOC-025
- Goal id: KDOC-G041
- Outputs: docs/VFS_CONTRACT_SPEC.md, docs/filesystem_journal.md
- Validation: test -s docs/VFS_CONTRACT_SPEC.md && test -s docs/filesystem_journal.md && rg -q "Ordering" docs/VFS_CONTRACT_SPEC.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/current-vfs
- Parallel lane: kdoc-current-storage
- Resource class: cpu-doc-validation
- Token class: xlarge
- Estimated tokens: 18000
- Predicted files: docs/VFS_CONTRACT_SPEC.md, docs/filesystem_journal.md
- Allow concurrent with: KDOC-030, KDOC-031, KDOC-032, KDOC-033, KDOC-034, KDOC-036, KDOC-037, KDOC-038, KDOC-039
- Conflict policy: Own canonical VFS/journal docs; do not edit implementation summaries.
- Preconditions: Use authoritative workflow tests and document MCP authority conflict explicitly.
- Effects: Align request/response, bucket/VFS identities, mutation ordering, WAL/journal roles, sync/conflict, recovery, security, and adapter surfaces with current tests.
- Acceptance: Contract claims are test-linked, current versus compatibility adapters are explicit, and failure/partial/retry semantics are unambiguous.

## KDOC-036 Refresh cluster operations and state guidance

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: current-operations
- Depends on: KDOC-015, KDOC-019, KDOC-028
- Goal id: KDOC-G042
- Outputs: docs/operations/cluster_management.md, docs/operations/cluster_state.md, docs/operations/cluster_monitoring.md
- Validation: test -s docs/operations/cluster_management.md && test -s docs/operations/cluster_state.md && test -s docs/operations/cluster_monitoring.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/current-cluster-ops
- Parallel lane: kdoc-current-operations
- Resource class: cpu-doc-validation
- Token class: xlarge
- Estimated tokens: 18000
- Predicted files: docs/operations/cluster_management.md, docs/operations/cluster_state.md, docs/operations/cluster_monitoring.md
- Allow concurrent with: KDOC-030, KDOC-031, KDOC-032, KDOC-033, KDOC-034, KDOC-035, KDOC-037, KDOC-038, KDOC-039
- Conflict policy: Own three cluster operations docs; retain proposed control-plane authority.
- Preconditions: Cluster architecture and authority ADR enumerate competing paths.
- Effects: Provide role-aware setup, state inspection, health/metrics, partition/degradation/recovery, and scoped validation for confirmed paths.
- Acceptance: Operational commands/APIs identify their implementation family and prerequisites; unresolved authority is never converted into a production recommendation.

## KDOC-037 Add a maintained Iroh documentation entry point and reconciliation map

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: current-operations
- Depends on: KDOC-016, KDOC-019, KDOC-026
- Goal id: KDOC-G042
- Outputs: docs/iroh/README.md
- Validation: test -s docs/iroh/README.md && rg -q "filesystem-contract" docs/iroh/README.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/current-iroh
- Parallel lane: kdoc-current-operations
- Resource class: cpu-doc-validation
- Token class: medium
- Estimated tokens: 10000
- Predicted files: docs/iroh/README.md
- Allow concurrent with: KDOC-030, KDOC-031, KDOC-032, KDOC-033, KDOC-034, KDOC-035, KDOC-036, KDOC-038, KDOC-039
- Conflict policy: Own Iroh index only; do not rewrite the strong normative Iroh contract/runbook set.
- Preconditions: Map code, packaging entry points, extras, workflows, and existing Iroh docs.
- Effects: Provide status, reading paths by audience, source/test/workflow map, lifecycle/security prerequisites, and inconsistencies needing later focused updates.
- Acceptance: All maintained Iroh docs are reachable and classified; duplicates with general operations/observability docs are explained rather than copied.

## KDOC-038 Refresh integration overview and boundary contracts

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: current-integration
- Depends on: KDOC-002, KDOC-003, KDOC-005
- Goal id: KDOC-G042
- Outputs: docs/integration/INTEGRATION_OVERVIEW.md, docs/integration/INTEGRATION_QUICK_START.md
- Validation: test -s docs/integration/INTEGRATION_OVERVIEW.md && test -s docs/integration/INTEGRATION_QUICK_START.md && rg -q "Ownership" docs/integration/INTEGRATION_OVERVIEW.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/current-integrations
- Parallel lane: kdoc-current-integration
- Resource class: cpu-static-analysis
- Token class: large
- Estimated tokens: 14000
- Predicted files: docs/integration/INTEGRATION_OVERVIEW.md, docs/integration/INTEGRATION_QUICK_START.md
- Allow concurrent with: KDOC-030, KDOC-031, KDOC-032, KDOC-033, KDOC-034, KDOC-035, KDOC-036, KDOC-037, KDOC-039
- Conflict policy: Own the two integration landing guides; specialized integration docs remain unchanged.
- Preconditions: Inventory packages/extras and distinguish in-repo adapters from externally owned systems.
- Effects: Map IPFS Datasets, Accelerate, FSSpec, IPLD, AI/ML, LangChain/LlamaIndex, Filecoin/Storacha/S3, GraphRAG, and network integration boundaries with maturity/prerequisites.
- Acceptance: Each integration lists ownership, install extra, supported surface, data/trust boundary, focused test/example, and honest maturity; no optional package is presented as core.

## KDOC-039 Refresh testing and contribution guidance

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: current-development
- Depends on: KDOC-003, KDOC-005
- Goal id: KDOC-G042
- Outputs: docs/development/testing_guide.md
- Validation: test -s docs/development/testing_guide.md && rg -q "tests/integration" docs/development/testing_guide.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/current-testing
- Parallel lane: kdoc-current-development
- Resource class: cpu-doc-validation
- Token class: large
- Estimated tokens: 14000
- Predicted files: docs/development/testing_guide.md
- Allow concurrent with: KDOC-030, KDOC-031, KDOC-032, KDOC-033, KDOC-034, KDOC-035, KDOC-036, KDOC-037, KDOC-038
- Conflict policy: Own testing guide only; do not change pytest configuration.
- Preconditions: Audit pytest.ini, archived suites, explicit integration exclusions, workflow-specific gates, optional-service tests, and docs verification weaknesses.
- Effects: Document fast/focused/full/integration/e2e matrices, extras/services, markers, offline expectations, failure triage, documentation update duties, and evidence recording.
- Acceptance: Default pytest exclusions and Python/config mismatches are explicit; contributors can choose authoritative focused gates without assuming presence-only documentation tests prove accuracy.

## KDOC-040 Create the historical-document register and disposition rules

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: information-architecture
- Depends on: KDOC-001, KDOC-003, KDOC-005
- Goal id: KDOC-G050
- Outputs: docs/audits/HISTORICAL_DOCUMENT_REGISTER.md
- Validation: test -s docs/audits/HISTORICAL_DOCUMENT_REGISTER.md && rg -q "Disposition" docs/audits/HISTORICAL_DOCUMENT_REGISTER.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/history-analysis
- Parallel lane: kdoc-history
- Resource class: io-static-analysis
- Token class: large
- Estimated tokens: 14000
- Predicted files: docs/audits/HISTORICAL_DOCUMENT_REGISTER.md
- Allow concurrent with: KDOC-043, KDOC-044
- Conflict policy: Register only; no file moves or mass banners.
- Preconditions: Corpus and freshness audits complete.
- Effects: Classify dated implementation, status, fix, test, migration, roadmap, coverage, and completion material as retain/archive/supersede/merge/drop-from-navigation.
- Acceptance: Register includes source path, date/baseline if known, current authority, replacement/link, move risk, and batch owner for every high-risk family.

## KDOC-041 Reconcile duplicate and competing documents on paper

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: information-architecture
- Depends on: KDOC-001, KDOC-003, KDOC-040
- Goal id: KDOC-G050
- Outputs: docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md
- Validation: test -s docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md && rg -q "Redirect" docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/dedup-analysis
- Parallel lane: kdoc-history
- Resource class: io-static-analysis
- Token class: medium
- Estimated tokens: 10000
- Predicted files: docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md
- Allow concurrent with: KDOC-043, KDOC-044
- Conflict policy: Plan only; no renames or shared navigation edits.
- Preconditions: History register identifies migration, auto-healing, refactoring, observability, MCP, coverage, and index duplicates.
- Effects: Select canonical replacements, archive targets, redirect/link strategy, inbound-link impact, and execution order.
- Acceptance: Every duplicate set has evidence-based disposition and no destructive move precedes a replacement/current guide.

## KDOC-042 Establish the archive boundary and historical reading guidance

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: information-architecture
- Depends on: KDOC-040, KDOC-041
- Goal id: KDOC-G050
- Outputs: docs/ARCHIVE/README.md
- Validation: test -s docs/ARCHIVE/README.md && rg -q "not current" docs/ARCHIVE/README.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/archive-boundary
- Parallel lane: kdoc-history
- Resource class: cpu-small
- Token class: medium
- Estimated tokens: 8000
- Predicted files: docs/ARCHIVE/README.md
- Allow concurrent with: KDOC-043, KDOC-044
- Conflict policy: Own archive landing page only.
- Preconditions: Register and redirect plan complete.
- Effects: Explain historical authority, provenance, caveats, how to find current replacements, and rules for future archival.
- Acceptance: Archived reports remain discoverable but cannot reasonably be mistaken for current API, operations, or architecture guidance.

## KDOC-043 Specify the generated documentation contract and drift gates

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: generated-docs
- Depends on: KDOC-001, KDOC-003, KDOC-005, KDOC-029
- Goal id: KDOC-G060
- Outputs: docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md
- Validation: test -s docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md && rg -q "deterministic" docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/generated-contract
- Parallel lane: kdoc-generated
- Resource class: cpu-static-analysis
- Token class: large
- Estimated tokens: 12000
- Predicted files: docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md
- Allow concurrent with: KDOC-040, KDOC-041, KDOC-042, KDOC-044
- Conflict policy: Own contract audit only; do not hand-edit generated output.
- Preconditions: Audit current inline generators, pdoc invocation, stale counts, literal shell expression, SDK manifests, and conflicting workflows.
- Effects: Define active-module allowlist, deterministic inputs/order/timestamps, exclusions, command/check mode, provenance header, failure policy, and separately authorized workflow/generator follow-ups.
- Acceptance: Contract can detect stale module/signature/dependency/example/tool manifests and does not treat tracked backups or external snapshots as public API.

## KDOC-044 Document external gitlinks and embedded project ownership

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: information-architecture
- Depends on: KDOC-001, KDOC-004, KDOC-005
- Goal id: KDOC-G050
- Outputs: docs/reference/EXTERNAL_DOCUMENTATION_SOURCES.md
- Validation: test -s docs/reference/EXTERNAL_DOCUMENTATION_SOURCES.md && rg -q "py-ipld" docs/reference/EXTERNAL_DOCUMENTATION_SOURCES.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/external-boundary
- Parallel lane: kdoc-external
- Resource class: io-static-analysis
- Token class: medium
- Estimated tokens: 9000
- Predicted files: docs/reference/EXTERNAL_DOCUMENTATION_SOURCES.md
- Allow concurrent with: KDOC-040, KDOC-041, KDOC-042, KDOC-043
- Conflict policy: Own external-source reference only; never fetch or modify external content.
- Preconditions: Inventory gitlinks and embedded py-ipld-car/dag-pb/unixfs project snapshots.
- Effects: Record origin/revision/availability/ownership/license/navigation/build/coverage treatment and update policy.
- Acceptance: External and embedded projects are excluded from authored package docs metrics and readers know when upstream material may be absent.

## KDOC-045 Curate report-like history using the reviewed register

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P2
- Track: information-architecture
- Depends on: KDOC-030, KDOC-031, KDOC-032, KDOC-033, KDOC-034, KDOC-035, KDOC-036, KDOC-037, KDOC-038, KDOC-039, KDOC-040, KDOC-041, KDOC-042
- Goal id: KDOC-G050
- Outputs: docs/ARCHIVE/implementation/README.md, docs/ARCHIVE/status-and-fixes/README.md
- Validation: test -s docs/ARCHIVE/implementation/README.md && test -s docs/ARCHIVE/status-and-fixes/README.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/history-curation
- Parallel lane: kdoc-history-exclusive
- Resource class: io-reorganization
- Token class: xlarge
- Estimated tokens: 22000
- Predicted files: docs/implementation, docs/status_reports, docs/fixes, docs/test_reports, docs/ARCHIVE/implementation, docs/ARCHIVE/status-and-fixes
- Allow concurrent with: KDOC-046 only when generated paths do not overlap
- Conflict policy: Exclusive owner of historical source/destination families; preserve Git history, redirects/indexes, and current replacements; do not touch navigation files.
- Preconditions: Current replacement docs exist and redirect plan is reviewed; working tree is clean except this task.
- Effects: Move or label the register-approved dated reports in bounded batches, retain provenance, create category indexes, and repair only links within owned history families.
- Acceptance: No maintained current guide is archived, no inbound canonical link is knowingly broken, and moved reports carry original context plus current replacement links.

## KDOC-046 Refresh generated API/agent/dependency/example output from current evidence

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: generated-docs
- Depends on: KDOC-002, KDOC-012, KDOC-043
- Goal id: KDOC-G060
- Outputs: docs/api_generated/README.md, docs/api_generated/module_structure.md, docs/api_generated/dependencies.md, docs/api_generated/examples_index.md, docs/api_generated/AGENT_GUIDE.md, docs/api_generated/doc_status.md
- Validation: test -s docs/api_generated/module_structure.md && test -s docs/api_generated/AGENT_GUIDE.md && rg -q "Generated from" docs/api_generated/README.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/generated-output
- Parallel lane: kdoc-generated-exclusive
- Resource class: cpu-generation
- Token class: xlarge
- Estimated tokens: 18000
- Predicted files: docs/api_generated
- Allow concurrent with: KDOC-045
- Conflict policy: Exclusive owner of api_generated; use deterministic/static generation and do not include external snapshots, backups, broken/fixed variants, or import-side-effect modules as supported API.
- Preconditions: Generated contract and active/compatibility allowlist complete; network disabled.
- Effects: Regenerate current inventories and agent guide with provenance, exclusions, measured counts, real commands, and explicit non-authority status.
- Acceptance: Output has no literal unevaluated shell fragments, nonexistent docs build commands, stale MCP/tool/API claims, or unexplained generated drift; regeneration limitations become follow-ups.

## KDOC-050 Create an agent-oriented canonical system map

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: agent-docs
- Depends on: KDOC-010, KDOC-011, KDOC-012, KDOC-013, KDOC-014, KDOC-015, KDOC-016, KDOC-017, KDOC-018, KDOC-019, KDOC-021, KDOC-022, KDOC-023, KDOC-024, KDOC-025, KDOC-026, KDOC-027, KDOC-028
- Goal id: KDOC-G070
- Outputs: docs/architecture/AGENT_SYSTEM_MAP.md
- Validation: test -s docs/architecture/AGENT_SYSTEM_MAP.md && rg -q "Do not" docs/architecture/AGENT_SYSTEM_MAP.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/agent-system-map
- Parallel lane: kdoc-agent
- Resource class: cpu-synthesis
- Token class: large
- Estimated tokens: 14000
- Predicted files: docs/architecture/AGENT_SYSTEM_MAP.md
- Allow concurrent with: KDOC-051
- Conflict policy: Own compact agent map; link to canonical guides instead of copying them.
- Preconditions: Subsystem guides and core ADRs exist.
- Effects: Provide task-to-subsystem routing, canonical/read-only/historical/generated paths, high-risk imports, state/process boundaries, focused tests, ADRs, and common false assumptions.
- Acceptance: An agent can choose where to read/edit/test for a scoped task and avoid legacy/fixed/backup/generated surfaces unless explicitly required.

## KDOC-051 Create the documentation change-impact map

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: agent-docs
- Depends on: KDOC-002, KDOC-010, KDOC-011, KDOC-012, KDOC-013, KDOC-014, KDOC-015, KDOC-016, KDOC-017, KDOC-018, KDOC-019
- Goal id: KDOC-G070
- Outputs: docs/development/DOCUMENTATION_IMPACT_MAP.md
- Validation: test -s docs/development/DOCUMENTATION_IMPACT_MAP.md && rg -q "Change trigger" docs/development/DOCUMENTATION_IMPACT_MAP.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/agent-impact-map
- Parallel lane: kdoc-agent
- Resource class: cpu-synthesis
- Token class: large
- Estimated tokens: 12000
- Predicted files: docs/development/DOCUMENTATION_IMPACT_MAP.md
- Allow concurrent with: KDOC-050
- Conflict policy: Own impact map only.
- Preconditions: Public surfaces and architecture guide ownership are known.
- Effects: Map source/package/workflow/schema/CLI/tool/state changes to required authored, reference, generated, ADR, migration, and operations updates plus focused checks.
- Acceptance: Maintainers and agents can identify documentation blast radius without scanning all 440 files, including triggers for version/export/tool-manifest and compatibility changes.

## KDOC-052 Create subsystem-oriented debugging guidance

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: agent-docs
- Depends on: KDOC-010, KDOC-011, KDOC-013, KDOC-014, KDOC-015, KDOC-016, KDOC-017, KDOC-018, KDOC-019, KDOC-030, KDOC-032, KDOC-033, KDOC-034, KDOC-035, KDOC-036, KDOC-037
- Goal id: KDOC-G070
- Outputs: docs/guides/DEBUGGING_BY_SUBSYSTEM.md
- Validation: test -s docs/guides/DEBUGGING_BY_SUBSYSTEM.md && rg -q "Degraded" docs/guides/DEBUGGING_BY_SUBSYSTEM.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/agent-debugging
- Parallel lane: kdoc-agent
- Resource class: cpu-synthesis
- Token class: large
- Estimated tokens: 16000
- Predicted files: docs/guides/DEBUGGING_BY_SUBSYSTEM.md
- Allow concurrent with: KDOC-053
- Conflict policy: Own debugging guide; do not duplicate full operations runbooks.
- Preconditions: Current interface and subsystem docs expose failure/health paths.
- Effects: Route symptoms through imports/dependencies, daemon lifecycle, backend config/health, VFS/WAL/journal, cache/index, cluster/network, MCP/transport/receipt, Iroh, and test/build diagnostics.
- Acceptance: Checks are safe/read-only first, identify state/log locations without leaking secrets, distinguish retryable/degraded/blocked conditions, and link recovery authority.

## KDOC-053 Specify offline documentation validation and quality gates

- Status: completed
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: quality
- Depends on: KDOC-005, KDOC-029, KDOC-043
- Goal id: KDOC-G060
- Outputs: docs/development/DOCUMENTATION_VALIDATION.md
- Validation: test -s docs/development/DOCUMENTATION_VALIDATION.md && rg -q "Offline" docs/development/DOCUMENTATION_VALIDATION.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/quality-validation
- Parallel lane: kdoc-quality
- Resource class: cpu-analysis
- Token class: large
- Estimated tokens: 14000
- Predicted files: docs/development/DOCUMENTATION_VALIDATION.md
- Allow concurrent with: KDOC-050, KDOC-051, KDOC-052
- Conflict policy: Own validation spec only; workflow/script implementation is a separate authorization.
- Preconditions: Documentation and generated contracts exist.
- Effects: Define canonical link/anchor checks, referenced path/symbol/entry-point checks, safe snippet/CLI help checks, duplicate/title/archive isolation, generated drift, sensitive-data scan, provenance/status checks, and focused subsystem test matrix.
- Acceptance: Gates are reproducible/offline, distinguish warnings from release blockers, avoid imports with side effects, and explain limitations of current presence-only tests.

## KDOC-054 Refresh the documentation maintenance workflow guide

- Status: todo
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P1
- Track: quality
- Depends on: KDOC-043, KDOC-046, KDOC-051, KDOC-053
- Goal id: KDOC-G060
- Outputs: docs/workflows/documentation-maintenance.md
- Validation: test -s docs/workflows/documentation-maintenance.md && rg -q "Ownership" docs/workflows/documentation-maintenance.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/quality-maintenance
- Parallel lane: kdoc-quality
- Resource class: cpu-synthesis
- Token class: medium
- Estimated tokens: 10000
- Predicted files: docs/workflows/documentation-maintenance.md
- Allow concurrent with: KDOC-050, KDOC-052
- Conflict policy: Own maintenance guide only; describe workflow gaps rather than editing `.github`.
- Preconditions: Generated output and validation contract are current.
- Effects: Define owners, review cadence, change-trigger process, regeneration/review, ADR handling, archival, dependency updates, failure triage, and separately authorized automation backlog.
- Acceptance: Guide contains real current commands where available, clearly labels proposed tooling, and no longer promises a nonexistent reproducible Sphinx/MkDocs build.

## KDOC-060 Integrate one canonical navigation hierarchy

- Status: todo
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: integration
- Depends on: KDOC-010, KDOC-011, KDOC-012, KDOC-013, KDOC-014, KDOC-015, KDOC-016, KDOC-017, KDOC-018, KDOC-019, KDOC-021, KDOC-022, KDOC-023, KDOC-024, KDOC-025, KDOC-026, KDOC-027, KDOC-028, KDOC-029, KDOC-030, KDOC-031, KDOC-032, KDOC-033, KDOC-034, KDOC-035, KDOC-036, KDOC-037, KDOC-038, KDOC-039, KDOC-042, KDOC-044, KDOC-045, KDOC-046, KDOC-050, KDOC-051, KDOC-052, KDOC-053, KDOC-054
- Goal id: KDOC-G080
- Outputs: docs/index.md, docs/README.md, docs/DOCUMENTATION_INDEX.md, docs/architecture/README.md
- Validation: test -s docs/index.md && test -s docs/README.md && test -s docs/DOCUMENTATION_INDEX.md && test -s docs/architecture/README.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/navigation
- Parallel lane: kdoc-integration-exclusive
- Resource class: cpu-synthesis
- Token class: xlarge
- Estimated tokens: 20000
- Predicted files: docs/index.md, docs/README.md, docs/DOCUMENTATION_INDEX.md, docs/architecture/README.md
- Allow concurrent with:
- Conflict policy: Exclusive owner of all navigation surfaces; run after content/history/generated work settles.
- Preconditions: All canonical guides, indexes, archive/external boundaries, agent docs, and maintenance docs exist on merge target.
- Effects: Make index.md the concise canonical landing page, README.md the complete repository map, DOCUMENTATION_INDEX.md a generated/structured catalog or redirect, and architecture/README.md the architecture/ADR reading order.
- Acceptance: Navigation has no competing authority, supports role/task/system paths, labels current/generated/historical/external/proposed material, and contains no known broken local link.

## KDOC-061 Run the final navigation, links, examples, and claim audit

- Status: todo
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: integration
- Depends on: KDOC-060
- Goal id: KDOC-G080
- Outputs: docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md
- Validation: test -s docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md && rg -q "Blocking findings: 0" docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/final-audit
- Parallel lane: kdoc-integration-exclusive
- Resource class: cpu-validation
- Token class: large
- Estimated tokens: 16000
- Predicted files: docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md
- Allow concurrent with:
- Conflict policy: Audit merged tree only; repair findings only within their owning document or emit an explicit follow-up before rerun.
- Preconditions: Canonical navigation is merged and supervisor lanes have no active content task.
- Effects: Check canonical links/anchors, duplicate navigation, path/symbol/entry-point references, safe examples/help, status/provenance, archive isolation, generated drift, sensitive patterns, and unresolved decision visibility.
- Acceptance: Report binds commit, commands, scope/exclusions, counts, findings, repairs/follow-ups, and states `Blocking findings: 0`; warnings have owners.

## KDOC-062 Issue the final evidence-backed documentation scorecard

- Status: todo
- Completion: manual
- Is schedulable: true
- Review only: false
- Priority: P0
- Track: integration
- Depends on: KDOC-061
- Goal id: KDOC-G000, KDOC-G080
- Outputs: docs/audits/FINAL_DOCUMENTATION_SCORECARD.md
- Validation: test -s docs/audits/FINAL_DOCUMENTATION_SCORECARD.md && rg -q "KDOC-G000" docs/audits/FINAL_DOCUMENTATION_SCORECARD.md
- Board namespace: ipfs-kit-documentation-architecture-v2
- Bundle: kdoc/final-scorecard
- Parallel lane: kdoc-integration-exclusive
- Resource class: cpu-validation
- Token class: medium
- Estimated tokens: 10000
- Predicted files: docs/audits/FINAL_DOCUMENTATION_SCORECARD.md
- Allow concurrent with:
- Conflict policy: Final report only; do not mark goals complete without merged-tree evidence.
- Preconditions: Final audit has zero blocking findings and all task outputs are present on the merge target.
- Effects: Summarize goal/task completion, delivered architecture/ADR/current/history/generated/agent coverage, validation evidence, known warnings, unresolved owner decisions, maintenance handoff, and baseline commit.
- Acceptance: Scorecard traces every root-goal criterion to a merged artifact/receipt, reports exceptions honestly, and provides enough evidence for an operator to close or continue KDOC-G000.
