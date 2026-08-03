# IPFS Kit documentation and architecture objective heap

This file is the durable goal/subgoal hierarchy for the documentation program.
The human plan is [`../documentation_plan.md`](../documentation_plan.md). The
executable projection is
[`ipfs_kit_documentation.todo.md`](./ipfs_kit_documentation.todo.md).

Program invariants:

- Program namespace is `ipfs-kit-documentation-architecture-v2`.
- All delivered artifacts are under `docs/`; source and tests are read-only
  evidence for this program.
- Current behavior, focused tests, packaging metadata, and accepted decisions
  outrank existing prose.
- Canonical, compatibility, optional, experimental, generated, external, and
  historical surfaces are not conflated.
- Conflicting architectural authority is documented as unresolved. An agent
  may write a proposed ADR with alternatives, but may not invent an accepted
  maintainer decision.
- Every current-state guide records its source paths, validating tests,
  failure/degraded modes, and last-verified baseline.
- Parallel tasks honor `Outputs:`, `Bundle:`, and `Parallel lane:` ownership.
  Navigation and program-control files have exclusive owners.
- A task is complete only after its offline validation passes on the merged
  target branch; narrative confidence or lane-local status is insufficient.

## KDOC-G000 Trustworthy, current, rationale-rich IPFS Kit documentation

- Status: active
- Parent:
- Priority: P0
- Track: integration
- Goal: Deliver a coherent documentation system that accurately reflects the current `ipfs_kit_py` tree, teaches developers and agents how the bespoke system works, preserves design rationale without inventing history, and continuously distinguishes maintained guidance from generated, external, and historical material.
- Evidence: KDOC-G010, KDOC-G020, KDOC-G030, KDOC-G040, KDOC-G050, KDOC-G060, KDOC-G070, KDOC-G080
- Evidence criteria: Every child goal has current-tree evidence; canonical navigation covers supported surfaces; architecture guides and ADRs cite source/tests; stale high-severity claims are corrected or quarantined; final validation reports no broken canonical links or unclassified maintained documents.
- Evidence source policy: Root completion requires a merged-tree audit tied to a Git commit and the terminal task receipts. Task-board drainage, generated module counts, and prose assertions alone do not qualify.
- Outputs: docs/documentation_plan.md, docs/architecture/ipfs_kit_documentation.objectives.md, docs/architecture/ipfs_kit_documentation.todo.md, docs/audits/FINAL_DOCUMENTATION_SCORECARD.md
- Acceptance: A new contributor or agent can identify supported entry points, follow the major data/control flows, understand verified design trade-offs and unresolved choices, run current examples, and determine the authority/freshness of every navigable document.
- Gap task: Close the highest-priority incomplete child goal without weakening evidence or authority classification.
- Refinement: Keep program-control files protected; refine through reviewed board changes, never worker-side opportunistic edits.

## KDOC-G010 Evidence-backed baseline and documentation governance

- Status: active
- Parent: KDOC-G000
- Priority: P0
- Track: evidence
- Goal: Establish the inventory, change baseline, public-surface map, source-of-truth map, vocabulary, and claim/lifecycle rules that every later documentation task consumes.
- Evidence: KDOC-G011, KDOC-G012, KDOC-G013
- Evidence criteria: Inventories state scope and exclusions; public claims map to implementation/tests; conflicts and unknowns remain visible; generated/external/historical material is classified separately.
- Evidence source policy: Static repository inspection, CLI/parser inspection, packaging metadata, focused tests, and Git history qualify. Import-heavy discovery or existing documentation without corroboration does not.
- Outputs: docs/audits/DOCUMENTATION_INVENTORY.md, docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md, docs/audits/PUBLIC_SURFACE_MATRIX.md, docs/architecture/SOURCE_OF_TRUTH_MAP.md, docs/guides/DOCUMENTATION_GUIDE.md, docs/architecture/GLOSSARY.md
- Acceptance: All Wave 1 authors have an evidence packet and a shared status vocabulary; no unresolved authority conflict is hidden.
- Gap task: Complete one missing Wave 0 evidence artifact.
- Refinement: Wave 0 tasks are deliberately numbered across all four supervisor shards.

## KDOC-G011 Corpus inventory, freshness, and history classification

- Status: active
- Parent: KDOC-G010
- Priority: P0
- Track: evidence-corpus
- Goal: Inventory the documentation corpus, identify stale/duplicate/generated/external/report-like material, and record implementation changes since the last trusted documentation baseline.
- Evidence: docs tree, Git history, `.github/workflows/auto-doc-maintenance.yml`, `.github/workflows/docs.yml`, `.github/workflows/pages.yml`
- Evidence criteria: Counts are reproducible; known stale examples include exact paths; classification does not fetch external gitlinks; the previous February and July documentation campaigns are distinguished from current work.
- Outputs: docs/audits/DOCUMENTATION_INVENTORY.md, docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md
- Acceptance: Every top-level documentation family has a proposed authority class, owner, freshness risk, and disposition.
- Gap task: Resolve the largest unclassified document family.

## KDOC-G012 Public surfaces and architectural source-of-truth mapping

- Status: active
- Parent: KDOC-G010
- Priority: P0
- Track: evidence-surfaces
- Goal: Map supported packaging entry points, Python symbols, CLI commands, MCP surfaces, backend registries, services, state stores, and tests to authoritative or unresolved implementation paths.
- Evidence: pyproject.toml, setup.py, ipfs_kit_py/__init__.py, ipfs_kit_py/cli.py, ipfs_kit_py/unified_cli_dispatcher.py, ipfs_kit_py/mcp_server, ipfs_kit_py/mcp, backend and cluster modules, pytest.ini
- Evidence criteria: Version/public-export conflicts and competing MCP, IPFS client, high-level API, and cluster implementations are recorded rather than resolved by guesswork.
- Outputs: docs/audits/PUBLIC_SURFACE_MATRIX.md, docs/architecture/SOURCE_OF_TRUTH_MAP.md
- Acceptance: Each architecture guide can point to explicit canonical, compatibility, optional, historical, or unresolved sources and focused tests.
- Gap task: Map one remaining public surface or conflicting implementation family.

## KDOC-G013 Documentation lifecycle, style, vocabulary, and evidence standard

- Status: active
- Parent: KDOC-G010
- Priority: P0
- Track: governance
- Goal: Define document classes, required architecture sections, rationale confidence labels, diagram/accessibility rules, examples policy, provenance fields, and change triggers.
- Evidence: docs/guides/DOCUMENTATION_GUIDE.md, existing docs patterns, KDOC-G011 inventory risks
- Evidence criteria: The standard distinguishes accepted, proposed, inferred, and unknown rationale and forbids generated-file hand edits and secret-bearing examples.
- Outputs: docs/guides/DOCUMENTATION_GUIDE.md, docs/architecture/GLOSSARY.md
- Acceptance: Later tasks can be reviewed mechanically for authority, evidence, status, and maintenance metadata.
- Gap task: Document one missing lifecycle or claim-quality rule.

## KDOC-G020 Bespoke system architecture guide set

- Status: active
- Parent: KDOC-G000
- Priority: P0
- Track: architecture
- Goal: Explain the system's component boundaries, entry points, state and data flows, concurrency/lifecycle rules, trust boundaries, failure behavior, extension points, and verified or unresolved design rationale.
- Evidence: KDOC-G021, KDOC-G022, KDOC-G023, KDOC-G024, KDOC-G025
- Evidence criteria: Each guide follows the KDOC-G013 contract and cites current source/test paths; diagrams are consistent; unresolved authority choices remain explicit.
- Outputs: docs/architecture/SYSTEM_OVERVIEW.md, docs/architecture/RUNTIME_AND_ENTRYPOINTS.md, docs/architecture/STORAGE_BACKEND_SYSTEM.md, docs/architecture/CONTENT_METADATA_VFS.md, docs/architecture/CLUSTER_COORDINATION.md, docs/architecture/NETWORK_TRANSPORTS.md, docs/architecture/MCP_CONTROL_PLANE.md, docs/architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md, docs/architecture/CONFIGURATION_STATE_AND_TRUST.md, docs/architecture/COMPATIBILITY_LAYERS.md
- Acceptance: The guide set answers the eight program-outcome questions in the human plan and never presents parallel-looking implementations as equally authoritative without qualification.
- Gap task: Complete the highest-priority missing subsystem guide.

## KDOC-G021 System context, runtime composition, and compatibility boundaries

- Status: active
- Parent: KDOC-G020
- Priority: P0
- Track: arch-runtime
- Goal: Document external actors/systems, package layers, supported entry points, runtime processes, canonical-versus-compatibility boundaries, and initialization/degradation behavior.
- Evidence: ipfs_kit_py/__init__.py, core, jit_imports.py, deps_resolver.py, ipfs_kit.py, high_level_api.py and high_level_api/, cli.py, unified_cli_dispatcher.py, daemon managers, packaging scripts
- Evidence criteria: The 0.2.0/0.3.0 version conflict, public export mismatch, competing IPFS clients, and legacy/fixed/backup modules are explicitly classified or marked unresolved.
- Outputs: docs/architecture/SYSTEM_OVERVIEW.md, docs/architecture/RUNTIME_AND_ENTRYPOINTS.md, docs/architecture/COMPATIBILITY_LAYERS.md
- Acceptance: Readers can select a supported entry point and understand which compatibility layers it crosses and which optional capabilities may degrade.
- Gap task: Clarify one unresolved runtime or compatibility boundary with evidence.

## KDOC-G022 Storage backend, content, metadata, VFS, and durability architecture

- Status: active
- Parent: KDOC-G020
- Priority: P0
- Track: arch-storage
- Goal: Explain the distinction between backend configuration plugins and live adapters, then trace content and metadata through caches, pins, buckets, VFS, indexes, WAL/CAR, journals, remote backends, and replication.
- Evidence: backend_registry.py, backend_manager.py, backends/, tiered_cache_manager.py, cache/, arrow_metadata_index.py, metadata_sync_handler.py, bucket and VFS modules, storage_wal.py, car_wal_manager.py, filesystem_journal.py, focused tests
- Evidence criteria: Content bytes and metadata/index state are not conflated; authoritative versus rebuildable state, ordering, recovery, and optional dependency behavior are explicit.
- Outputs: docs/architecture/STORAGE_BACKEND_SYSTEM.md, docs/architecture/CONTENT_METADATA_VFS.md
- Acceptance: A developer can trace add/read/update/delete and recovery paths and safely add a backend or VFS feature without bypassing validation or durability boundaries.
- Gap task: Document one untraced persistence or recovery edge.

## KDOC-G023 Cluster, coordination, routing, replication, and network architecture

- Status: active
- Parent: KDOC-G020
- Priority: P0
- Track: arch-distributed
- Goal: Explain bespoke cluster roles and coordination separately from Kubo Cluster wrappers, plus Iroh, libp2p, routing, P2P workflow, and replication boundaries.
- Evidence: cluster/, top-level cluster modules, cluster_state.py, merkle_clock.py, p2p_workflow_coordinator.py, routing/, libp2p/, iroh/, ipfs_cluster_* modules, tests and Iroh contracts
- Evidence criteria: Competing cluster consistency models and constructor/API mismatches are marked unresolved; actual exposed P2P surfaces are distinguished from stale CLI claims.
- Outputs: docs/architecture/CLUSTER_COORDINATION.md, docs/architecture/NETWORK_TRANSPORTS.md
- Acceptance: Readers understand role/capability selection, task/state coordination, transport/backend responsibilities, consistency limits, and failure/recovery boundaries.
- Gap task: Clarify one unresolved cluster or transport authority boundary.

## KDOC-G024 MCP++, MCP compatibility, and multi-interface control plane

- Status: active
- Parent: KDOC-G020
- Priority: P0
- Track: arch-control
- Goal: Document the new `mcp_server` MCP++ runtime, its single tool registry and multiple surfaces, durability/receipt coordination, and its relationship to the legacy `mcp/` stack and CLI/Python/SDK interfaces.
- Evidence: pyproject entry points, mcp_server/server.py, hierarchical_tool_manager.py, tools/, fastmcp_app.py, js_sdk/, p2p_transport.py, mcplusplus/, agent_supervisor_receipts.py, legacy mcp/, conformance tests
- Evidence criteria: Tool counts are generated or measured; degraded/stub semantics and fail-closed receipt reads are explicit; the unresolved production-authority conflict is linked to a proposed ADR.
- Outputs: docs/architecture/MCP_CONTROL_PLANE.md
- Acceptance: A developer can add or invoke a tool through the intended registry without maintaining divergent schemas or confusing current and compatibility servers.
- Gap task: Reconcile one uncharted MCP surface or registry drift issue.

## KDOC-G025 Async, optional dependencies, configuration, state, trust, and lifecycle

- Status: active
- Parent: KDOC-G020
- Priority: P0
- Track: arch-trust
- Goal: Explain AnyIO/Trio and deliberate asyncio/sync boundaries, lazy imports and optional dependency degradation, binary/service lifecycle ownership, configuration precedence, local state paths, credential references, trust boundaries, health, and observability.
- Evidence: anyio/asyncio modules and tests, setup.py, pyproject extras, installers, kubo_runtime.py, daemon managers, config.py/config_manager.py/backend_manager.py, credential modules, Iroh security/lifecycle docs
- Evidence criteria: No claim of a universal AnyIO migration; opt-in binary installation and import-time side-effect constraints are accurate; secrets are redacted and state ownership is explicit.
- Outputs: docs/architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md, docs/architecture/CONFIGURATION_STATE_AND_TRUST.md
- Acceptance: Readers can choose the correct async boundary, diagnose missing capabilities, and understand who owns each process, state file, and credential.
- Gap task: Document one missing lifecycle or trust boundary.

## KDOC-G030 Architectural decision records and rationale

- Status: active
- Parent: KDOC-G000
- Priority: P0
- Track: decisions
- Goal: Establish an ADR framework and record the important choices, trade-offs, rejected alternatives, evidence, and unresolved authority decisions behind the bespoke system.
- Evidence: KDOC-G031, KDOC-G032
- Evidence criteria: ADR status is explicit; proposed decisions remain proposed; inferred historical rationale is labeled; accepted decisions cite implementation/history/tests.
- Outputs: docs/architecture/decisions/README.md, docs/architecture/decisions/0000-template.md, docs/architecture/decisions/0001-imports-and-optional-dependencies.md, docs/architecture/decisions/0002-backend-plugin-registry.md, docs/architecture/decisions/0003-mcp-runtime-authority.md, docs/architecture/decisions/0004-anyio-and-sync-boundaries.md, docs/architecture/decisions/0005-content-metadata-and-durability.md, docs/architecture/decisions/0006-multi-protocol-storage-and-networking.md, docs/architecture/decisions/0007-configuration-state-and-secret-references.md, docs/architecture/decisions/0008-cluster-control-plane-authority.md, docs/architecture/decisions/0009-documentation-site-toolchain.md
- Acceptance: Every architecture guide links relevant ADRs, and decision status never overstates maintainer agreement.
- Gap task: Add the highest-value missing or unresolved decision record.

## KDOC-G031 ADR process, index, and template

- Status: active
- Parent: KDOC-G030
- Priority: P0
- Track: decisions-framework
- Goal: Define ADR identifiers, statuses, evidence/rationale confidence, consequences, alternatives, supersession, and owner-confirmation workflow.
- Evidence: KDOC-G013 claim standard and current architecture conflicts
- Outputs: docs/architecture/decisions/README.md, docs/architecture/decisions/0000-template.md
- Acceptance: An agent can draft a proposed ADR without accidentally asserting an accepted decision.
- Gap task: Complete the ADR template or decision index contract.

## KDOC-G032 Evidence-backed subsystem and authority decisions

- Status: active
- Parent: KDOC-G030
- Priority: P1
- Track: decisions
- Goal: Record decisions for optional/lazy imports, backend plugins, MCP authority, concurrency, content/metadata durability, multi-protocol support, configuration/secrets, cluster authority, and docs tooling.
- Evidence: KDOC-G020 guides, Git history, focused tests, packaging/workflow configuration
- Evidence criteria: MCP, cluster, public API, and docs-tool conflicts stay proposed until owner confirmation; implemented invariants may be accepted only with strong evidence.
- Outputs: docs/architecture/decisions/0001-imports-and-optional-dependencies.md, docs/architecture/decisions/0002-backend-plugin-registry.md, docs/architecture/decisions/0003-mcp-runtime-authority.md, docs/architecture/decisions/0004-anyio-and-sync-boundaries.md, docs/architecture/decisions/0005-content-metadata-and-durability.md, docs/architecture/decisions/0006-multi-protocol-storage-and-networking.md, docs/architecture/decisions/0007-configuration-state-and-secret-references.md, docs/architecture/decisions/0008-cluster-control-plane-authority.md, docs/architecture/decisions/0009-documentation-site-toolchain.md
- Acceptance: Each ADR has context, decision/status, evidence, consequences, alternatives, unknowns, and follow-up owner.
- Gap task: Draft one missing ADR from the reviewed architecture evidence.

## KDOC-G040 Refreshed developer, user, integration, and operator journeys

- Status: active
- Parent: KDOC-G000
- Priority: P0
- Track: current-docs
- Goal: Bring installation, quick-start, public API, CLI, MCP, backend, VFS, cluster, Iroh, integration, testing, and contribution guidance into agreement with the current tree.
- Evidence: KDOC-G041, KDOC-G042
- Evidence criteria: Commands and imports are checked; prerequisites and network/daemon requirements are explicit; stale capabilities are removed or labeled.
- Outputs: docs/installation_guide.md, docs/QUICK_REFERENCE.md, docs/api/api_reference.md, docs/api/high_level_api.md, docs/api/cli_reference.md, docs/api/mcp_reference.md, docs/reference/storage_backends.md, docs/credential_management.md, docs/VFS_CONTRACT_SPEC.md, docs/filesystem_journal.md, docs/operations/cluster_management.md, docs/operations/cluster_state.md, docs/operations/cluster_monitoring.md, docs/iroh/README.md, docs/integration/INTEGRATION_OVERVIEW.md, docs/integration/INTEGRATION_QUICK_START.md, docs/development/testing_guide.md
- Acceptance: Primary user and operator journeys work from a clean supported environment or clearly state why an external service is required.
- Gap task: Refresh the highest-severity stale current guide.

## KDOC-G041 Getting started and public interface accuracy

- Status: active
- Parent: KDOC-G040
- Priority: P0
- Track: current-api
- Goal: Verify install, first success, Python exports/high-level API, CLI command tree, MCP usage, configuration, backend capabilities, and VFS behavior.
- Evidence: pyproject.toml, package exports, entry points, parser construction, backend registry, VFS contracts, focused import/CLI/MCP/VFS tests
- Evidence criteria: Version/export/command conflicts are not papered over; examples target confirmed public surfaces.
- Outputs: docs/installation_guide.md, docs/QUICK_REFERENCE.md, docs/api/api_reference.md, docs/api/high_level_api.md, docs/api/cli_reference.md, docs/api/mcp_reference.md, docs/reference/storage_backends.md, docs/credential_management.md, docs/VFS_CONTRACT_SPEC.md, docs/filesystem_journal.md
- Acceptance: A new user can install, verify, and choose an interface without following a nonexistent script, command, or export.
- Gap task: Correct one unsupported public-interface claim.

## KDOC-G042 Distributed operations, integrations, testing, and contribution

- Status: active
- Parent: KDOC-G040
- Priority: P1
- Track: current-operations
- Goal: Refresh cluster and Iroh operations, integration boundaries, test topology, and contribution guidance.
- Evidence: cluster and Iroh tests/workflows, integration packages, pytest.ini, tests/integration exclusions, repository tooling
- Evidence criteria: Default versus explicit integration gates are clear; Iroh's strong normative docs are reconciled rather than wholesale rewritten.
- Outputs: docs/operations/cluster_management.md, docs/operations/cluster_state.md, docs/operations/cluster_monitoring.md, docs/iroh/README.md, docs/integration/INTEGRATION_OVERVIEW.md, docs/integration/INTEGRATION_QUICK_START.md, docs/development/testing_guide.md
- Acceptance: Operators and contributors can run the intended focused validations and understand external-system ownership.
- Gap task: Refresh one missing operations or contribution journey.

## KDOC-G050 Information architecture, history, generated, and external boundaries

- Status: active
- Parent: KDOC-G000
- Priority: P1
- Track: information-architecture
- Goal: Make one coherent navigation hierarchy and clearly separate maintained guidance from dated reports, generated output, embedded projects, and external gitlinks.
- Evidence: KDOC-G011 inventory, current indexes, generated workflow, external/submodule declarations
- Evidence criteria: No mass move precedes a reviewed classification/redirect plan; generated and external trees have explicit ownership; historical docs are excluded from current recommendations.
- Outputs: docs/audits/HISTORICAL_DOCUMENT_REGISTER.md, docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md, docs/ARCHIVE/README.md, docs/api_generated/README.md, docs/reference/EXTERNAL_DOCUMENTATION_SOURCES.md, docs/README.md, docs/index.md, docs/DOCUMENTATION_INDEX.md, docs/architecture/README.md
- Acceptance: Each navigable file has one role and a clear path from the canonical index; history remains discoverable without posing as current authority.
- Gap task: Classify or integrate the largest remaining ambiguous document family.

## KDOC-G060 Repeatable freshness, generated-doc, and quality controls

- Status: active
- Parent: KDOC-G000
- Priority: P1
- Track: quality
- Goal: Specify reproducible generated documentation, offline validation, example/symbol/link checking, ownership, review cadence, and drift evidence.
- Evidence: current documentation workflows and generators, KDOC-G011 findings, focused source/tests
- Evidence criteria: The contract identifies current workflow contradictions and proposes separately authorized non-doc changes; it does not claim nonexistent Sphinx/MkDocs configuration works.
- Outputs: docs/development/DOCUMENTATION_VALIDATION.md, docs/workflows/documentation-maintenance.md, docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md, docs/audits/FINAL_DOCUMENTATION_SCORECARD.md
- Acceptance: Maintainers know how to reproduce, review, and detect drift without trusting file presence or raw module counts alone.
- Gap task: Add one missing deterministic validation or ownership rule.

## KDOC-G070 Agent-oriented system map and change guidance

- Status: active
- Parent: KDOC-G000
- Priority: P1
- Track: agent-docs
- Goal: Give implementation and review agents a compact, evidence-linked map of canonical surfaces, change impact, subsystem diagnostics, unsafe assumptions, and documentation update triggers.
- Evidence: KDOC-G020 architecture guides, KDOC-G030 ADRs, KDOC-G040 current docs
- Evidence criteria: The guide favors canonical paths and explicitly warns about backup/fixed/legacy/generated trees and import side effects.
- Outputs: docs/architecture/AGENT_SYSTEM_MAP.md, docs/development/DOCUMENTATION_IMPACT_MAP.md, docs/guides/DEBUGGING_BY_SUBSYSTEM.md
- Acceptance: An agent can scope a change, find relevant tests/docs/ADRs, and avoid the most common wrong entry point or stale-guide traps.
- Gap task: Document one missing change-impact or diagnostic route.

## KDOC-G080 Program integration, navigation, and acceptance

- Status: active
- Parent: KDOC-G000
- Priority: P0
- Track: integration
- Goal: Integrate subsystem outputs, resolve navigation, verify links/examples/status/provenance on the merged tree, and issue the final evidence-backed scorecard.
- Evidence: all other KDOC goals and their merged outputs
- Evidence criteria: Final checks operate on the merge target and enumerate exceptions; no lane-local artifact or self-reported completion substitutes for inspection.
- Outputs: docs/architecture/README.md, docs/README.md, docs/index.md, docs/DOCUMENTATION_INDEX.md, docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md, docs/audits/FINAL_DOCUMENTATION_SCORECARD.md
- Acceptance: Canonical navigation is coherent, final audits pass, unresolved owner decisions are visible, and KDOC-G000 can be closed without hidden stale claims.
- Gap task: Repair the highest-severity final integration finding.
