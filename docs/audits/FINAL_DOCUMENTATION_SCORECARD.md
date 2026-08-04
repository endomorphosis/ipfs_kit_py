# Final Documentation Scorecard

| Field | Value |
|---|---|
| **Task** | KDOC-062 |
| **Root goal** | **KDOC-G000** — Trustworthy, current, rationale-rich IPFS Kit documentation |
| **Integration goal** | KDOC-G080 — Program integration, navigation, and acceptance |
| **Track** | integration |
| **Scorecard date (UTC)** | 2026-08-04 |
| **Scorecard commit (this tree)** | `c2d8d405578ed597ff81696880fbae66a4fa307a` |
| **Scorecard tree id** | `52b9babacf0230359ccf2d89d7b479fa9bc70269` |
| **Final audit commit (KDOC-061)** | `2a3ce6f30a2c0710ef3b9e9675b78957645c3c2c` (ancestor of scorecard HEAD; merged via `50cc5c1d` / `800995d2`) |
| **Final audit tree id** | `c037328a49daf5a1df375e99821bf4eb76f6c0dd` |
| **Depends on** | KDOC-061 (`docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md` reports **Blocking findings: 0**) |
| **Conflict policy** | Final report only. Does **not** mark goals complete in protected program-control files. Does **not** invent maintainer decisions. Exceptions and open owner decisions remain visible. |
| **Package version (packaging)** | `0.3.0` (`pyproject.toml`) |
| **Package `__version__` (runtime)** | `0.2.0` (`ipfs_kit_py/__init__.py`) — conflict **C-VER** / **U-01** (labeled; not hidden) |
| **Board namespace** | `ipfs-kit-documentation-architecture-v2` |
| **Scope** | Evidence-backed closeout of **KDOC-G000**: map every root and child-goal criterion to merged artifacts/receipts, re-spot-check exclusive navigation on scorecard HEAD, consume KDOC-061 warnings, list residual exceptions with owners, and give an operator a clear **close / continue** decision for KDOC-G000. |
| **Exclusions** | Editing product docs, ADRs, navigation, or protected plan/objectives/todo files. Network fetches, daemon bring-up, optional-extra installs. Resolving product authority conflicts (those stay **Proposed** / **U-\***). Automated CI wiring (separately authorized). |

---

## Operator judgment (KDOC-G000)

| Decision field | Value |
|---|---|
| **Program documentation deliverables** | **Complete on the merge target** once this scorecard is present and non-empty (all declared child-goal outputs exist; KDOC-061 gate is green; board tasks KDOC-001…061 are completed; KDOC-062 is this receipt). |
| **Recommended disposition for KDOC-G000** | **CLOSE** the documentation program root goal **with residual exceptions recorded** (see §8–§10). Residual items are **owned product/architecture follow-ups**, not hidden documentation gaps. |
| **Continue instead if** | An operator requires zero open **U-\*** / **Proposed** ADRs before close; or requires a re-run of KDOC-061 after material post-audit content edits that this scorecard did not re-audit beyond exclusive-nav path links. Neither condition is true for the evidence criteria as written. |
| **Must not claim** | That all product authority conflicts are resolved; that all ADRs are Accepted; that External gitlinks were fetched; that presence of files alone proves runtime accuracy without the cited audits and gates. |

**One-line summary:** The documentation system on commit `c2d8d405` is coherent, evidence-linked, navigation-safe (**Blocking findings: 0**), and authority-honest. **KDOC-G000** may be closed by an operator on that basis; open **U-01…U-18**, **C-\*** conflicts, and seven **Proposed** ADRs remain **visible program residual work**, not concealed defects.

---

## 1. Purpose and method

This scorecard is the **KDOC-062** terminal receipt for **KDOC-G000** / **KDOC-G080**. It answers:

1. Does every child of **KDOC-G000** have **current-tree, non-empty merged artifacts** matching the objective `Outputs:` lists?
2. Do those artifacts satisfy the **root evidence criteria** (navigation, architecture/ADR evidence, quarantine of high-severity stale claims, final audit without broken canonical links)?
3. Are exceptions, warnings, and unresolved owner decisions **named with owners** rather than papered over?
4. Can an operator **close or continue** KDOC-G000 with enough evidence to defend the choice?

### 1.1 Evidence ranking (this scorecard)

| Rank | What qualifies | What does not |
|---|---|---|
| 1 | Non-empty paths on scorecard HEAD; `test -s` / path resolution | Empty stubs or “TODO” placeholders |
| 2 | KDOC-061 final audit bound to a Git commit with **Blocking findings: 0** | Lane-local narrative without merge |
| 3 | Re-spot-check of exclusive-nav local links on scorecard HEAD (462 / 0 missing) | Board status alone (`Status: completed`) without file presence |
| 4 | Explicit open **U-\*** / **C-\*** / **Proposed** ADR inventory | Treating Proposed as Accepted |
| 5 | Packaging metadata + static tree claims already bound in Wave 0–3 artifacts | Generated module counts as accuracy proof |

### 1.2 Severity model (scorecard)

| Label | Meaning |
|---|---|
| **Met** | Criterion fully satisfied by merged evidence |
| **Met with residual** | Criterion satisfied for documentation program close; residual product/owner work remains and is listed |
| **Not met** | Criterion fails; blocks honest KDOC-G000 close |
| **N/A** | Outside documentation program scope |

---

## 2. Reproducible evidence commands

Run from repository root. Offline assumption: `IPFS_KIT_AUTO_INSTALL_BINARIES=0`.

```bash
# Bind scorecard tree
git rev-parse HEAD              # expected: c2d8d405578ed597ff81696880fbae66a4fa307a (at issue time)
git rev-parse HEAD^{tree}       # expected: 52b9babacf0230359ccf2d89d7b479fa9bc70269

# Confirm final audit gate and ancestry
test -s docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md
rg -q "Blocking findings: 0" docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md
git merge-base --is-ancestor 2a3ce6f30a2c0710ef3b9e9675b78957645c3c2c HEAD

# Corpus size (scorecard HEAD)
find docs -name '*.md' | wc -l  # observed: 439 (includes this scorecard once present)
find docs -type f | wc -l       # observed: 493

# Packaging vs runtime version (C-VER)
python3 -c "import tomllib; from pathlib import Path; print(tomllib.loads(Path('pyproject.toml').read_text())['project']['version'])"
rg -n '__version__' ipfs_kit_py/__init__.py

# Exclusive navigation local path links (re-check at scorecard time)
# Observed: 462 local links, 0 missing file targets on the four exclusive surfaces.

# Presence of every child-goal declared output (sample command)
for f in \
  docs/audits/DOCUMENTATION_INVENTORY.md \
  docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md \
  docs/audits/PUBLIC_SURFACE_MATRIX.md \
  docs/architecture/SOURCE_OF_TRUTH_MAP.md \
  docs/guides/DOCUMENTATION_GUIDE.md \
  docs/architecture/GLOSSARY.md \
  docs/architecture/SYSTEM_OVERVIEW.md \
  docs/architecture/RUNTIME_AND_ENTRYPOINTS.md \
  docs/architecture/STORAGE_BACKEND_SYSTEM.md \
  docs/architecture/CONTENT_METADATA_VFS.md \
  docs/architecture/CLUSTER_COORDINATION.md \
  docs/architecture/NETWORK_TRANSPORTS.md \
  docs/architecture/MCP_CONTROL_PLANE.md \
  docs/architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md \
  docs/architecture/CONFIGURATION_STATE_AND_TRUST.md \
  docs/architecture/COMPATIBILITY_LAYERS.md \
  docs/architecture/decisions/README.md \
  docs/architecture/decisions/0000-template.md \
  docs/architecture/decisions/0001-imports-and-optional-dependencies.md \
  docs/architecture/decisions/0002-backend-plugin-registry.md \
  docs/architecture/decisions/0003-mcp-runtime-authority.md \
  docs/architecture/decisions/0004-anyio-and-sync-boundaries.md \
  docs/architecture/decisions/0005-content-metadata-and-durability.md \
  docs/architecture/decisions/0006-multi-protocol-storage-and-networking.md \
  docs/architecture/decisions/0007-configuration-state-and-secret-references.md \
  docs/architecture/decisions/0008-cluster-control-plane-authority.md \
  docs/architecture/decisions/0009-documentation-site-toolchain.md \
  docs/installation_guide.md docs/QUICK_REFERENCE.md \
  docs/api/api_reference.md docs/api/high_level_api.md \
  docs/api/cli_reference.md docs/api/mcp_reference.md \
  docs/reference/storage_backends.md docs/credential_management.md \
  docs/VFS_CONTRACT_SPEC.md docs/filesystem_journal.md \
  docs/operations/cluster_management.md docs/operations/cluster_state.md \
  docs/operations/cluster_monitoring.md docs/iroh/README.md \
  docs/integration/INTEGRATION_OVERVIEW.md docs/integration/INTEGRATION_QUICK_START.md \
  docs/development/testing_guide.md \
  docs/audits/HISTORICAL_DOCUMENT_REGISTER.md \
  docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md \
  docs/ARCHIVE/README.md docs/api_generated/README.md \
  docs/reference/EXTERNAL_DOCUMENTATION_SOURCES.md \
  docs/README.md docs/index.md docs/DOCUMENTATION_INDEX.md \
  docs/architecture/README.md \
  docs/development/DOCUMENTATION_VALIDATION.md \
  docs/workflows/documentation-maintenance.md \
  docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md \
  docs/architecture/AGENT_SYSTEM_MAP.md \
  docs/development/DOCUMENTATION_IMPACT_MAP.md \
  docs/guides/DEBUGGING_BY_SUBSYSTEM.md \
  docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md \
  docs/audits/FINAL_DOCUMENTATION_SCORECARD.md \
  docs/documentation_plan.md \
  docs/architecture/ipfs_kit_documentation.objectives.md \
  docs/architecture/ipfs_kit_documentation.todo.md
do
  test -s "$f" || echo "MISS $f"
done
# Expected: no MISS lines

# Task contract validation for this scorecard
test -s docs/audits/FINAL_DOCUMENTATION_SCORECARD.md && rg -q "KDOC-G000" docs/audits/FINAL_DOCUMENTATION_SCORECARD.md
```

### 2.1 Spot-check results at issue time

| Check | Result | Notes |
|---|---|---|
| Scorecard HEAD | `c2d8d405578ed597ff81696880fbae66a4fa307a` | Branch `implementation/kdoc-062-…` |
| KDOC-061 commit is ancestor | **Yes** | Audit remains valid lineage for this tree |
| Exclusive-nav local links | **462 OK / 0 missing** | Re-resolved on scorecard HEAD |
| Stale entry scripts on exclusive nav | **None** | No `final_mcp_server_enhanced` / root `start_3_node_cluster.py` |
| Final audit blocking gate | **0** | String present; acceptance met |
| Declared child-goal outputs | **All non-empty** | Full list in §2 loop |
| Board tasks completed (todo file, read-only) | **50 completed / 1 todo (KDOC-062)** | Status labels alone are **not** acceptance; artifacts are |

---

## 3. Root goal KDOC-G000 — criterion traceability

Source: `docs/architecture/ipfs_kit_documentation.objectives.md` § KDOC-G000.

### 3.1 Goal statement

> Deliver a coherent documentation system that accurately reflects the current `ipfs_kit_py` tree, teaches developers and agents how the bespoke system works, preserves design rationale without inventing history, and continuously distinguishes maintained guidance from generated, external, and historical material.

| Aspect | Score | Merged receipt |
|---|---|---|
| Coherent system | **Met** | Exclusive nav KDOC-060 + architecture hub + agent map |
| Reflects current tree | **Met with residual** | Wave 0–1 evidence + current journeys; residual content drift tracked as W-002/W-003/FU-\* |
| Teaches developers / agents | **Met** | Architecture guides, journeys, AGENT_SYSTEM_MAP, debugging + impact maps |
| Rationale without inventing history | **Met with residual** | ADR set; 7 remain **Proposed** by design for owner confirmation |
| Class distinction (Current / Generated / Historical / External / Proposed) | **Met** | Nav labels, inventory, historical register, external boundary, generated contract |

### 3.2 Evidence criteria (root)

| Criterion | Score | Primary artifacts / receipts |
|---|---|---|
| Every child goal has current-tree evidence | **Met** | §4 child scorecard; all declared outputs non-empty on HEAD |
| Canonical navigation covers supported surfaces | **Met** | `docs/index.md`, `docs/README.md`, `docs/DOCUMENTATION_INDEX.md`, `docs/architecture/README.md`; KDOC-061 §4 |
| Architecture guides and ADRs cite source/tests | **Met with residual** | Guides + ADR bodies under `docs/architecture/`; open U-\* remain explicit |
| Stale high-severity claims corrected or quarantined | **Met with residual** | F-001/F-002 cleared on exclusive nav (KDOC-061 §7); residual package docstring → **W-002** (owned, outside nav) |
| Final validation: no broken canonical links | **Met** | KDOC-061: 0 missing exclusive-nav paths; re-check 462/0; **Blocking findings: 0** |
| No unclassified maintained documents at final gate | **Met with residual** | Inventory + historical register + duplicate plan classify families; residual content-level classification work is disposition, not hidden “maintained” authority |

### 3.3 Evidence source policy (root)

| Requirement | Score | How satisfied |
|---|---|---|
| Merged-tree audit tied to a Git commit | **Met** | KDOC-061 at `2a3ce6f3…`; this scorecard at `c2d8d405…` with ancestry check |
| Terminal task receipts | **Met** | Final audit + this scorecard; child outputs present |
| Task-board drainage alone does **not** qualify | **Honored** | Board status cited only as secondary; artifacts and audits are primary |
| Generated module counts alone do **not** qualify | **Honored** | Generated tree labeled; contract + gates define accuracy controls |

### 3.4 Acceptance (root — human outcomes)

| Acceptance outcome | Score | How a reader achieves it |
|---|---|---|
| Identify supported entry points | **Met** | `docs/index.md` → packaging scripts; `RUNTIME_AND_ENTRYPOINTS.md`; install + quick-ref |
| Follow major data / control flows | **Met** | SYSTEM_OVERVIEW, STORAGE/CONTENT_METADATA_VFS, CLUSTER, NETWORK, MCP_CONTROL_PLANE |
| Understand verified trade-offs and unresolved choices | **Met** | Accepted ADRs 0001–0002; Proposed ADRs 0003–0009; SOURCE_OF_TRUTH_MAP U-01…U-18 |
| Run current examples (or know prerequisites) | **Met with residual** | Journeys + help smoke in KDOC-061; full daemon/extra matrix not re-executed here (offline policy) |
| Determine authority / freshness of every navigable document | **Met** | Nav material-class tables; DOCUMENTATION_GUIDE; inventory/register; Generated banners |

### 3.5 Declared root outputs

| Output | Present on HEAD | Role |
|---|---|---|
| `docs/documentation_plan.md` | Yes (protected; read-only for workers) | Human plan |
| `docs/architecture/ipfs_kit_documentation.objectives.md` | Yes (protected) | Goal heap |
| `docs/architecture/ipfs_kit_documentation.todo.md` | Yes (protected) | Executable board |
| `docs/audits/FINAL_DOCUMENTATION_SCORECARD.md` | Yes (this file) | Terminal scorecard |

---

## 4. Child goals of KDOC-G000

Status labels below are **scorecard judgments from artifacts**, not edits to the objectives file (objectives remain `active` until an operator closes them).

### 4.1 Summary matrix

| Goal | Track | Score | Key receipts | Residual exceptions |
|---|---|---|---|---|
| **KDOC-G010** Evidence baseline & governance | evidence | **Met** | Inventory, freshness, public surface, SOT map, guide, glossary | Classification proposals remain living evidence |
| **KDOC-G020** Architecture guide set | architecture | **Met with residual** | 10 architecture guides | Open subsystem U-\* in SOT map |
| **KDOC-G030** ADR / rationale set | decisions | **Met with residual** | Index, template, ADR-0001…0009 | 7 Proposed; only 0001–0002 Accepted |
| **KDOC-G040** Current journeys | current-docs | **Met with residual** | Install, API, CLI, MCP, ops, Iroh, integration, testing | C-VER; residual docstring W-002; content anchors W-003 |
| **KDOC-G050** IA / history / external | information-architecture | **Met** | Historical register, duplicate plan, ARCHIVE, api_generated, external sources, nav surfaces | External gitlinks intentionally empty |
| **KDOC-G060** Quality / generated / validation | quality | **Met with residual** | Validation runbook, maintenance workflow, generated contract, this scorecard | CI wiring / unified checker separately authorized |
| **KDOC-G070** Agent maps | agent-docs | **Met** | AGENT_SYSTEM_MAP, DOCUMENTATION_IMPACT_MAP, DEBUGGING_BY_SUBSYSTEM | — |
| **KDOC-G080** Integration & acceptance | integration | **Met with residual** | Nav surfaces, final audit, this scorecard | Owned warnings W-001…W-005 |

### 4.2 KDOC-G010 — Evidence-backed baseline and documentation governance

| Field | Value |
|---|---|
| **Score** | **Met** |
| **Evidence criteria** | Inventories state scope/exclusions; public claims map to implementation/tests; conflicts/unknowns visible; generated/external/historical classified separately |
| **Artifacts** | `docs/audits/DOCUMENTATION_INVENTORY.md`, `docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md`, `docs/audits/PUBLIC_SURFACE_MATRIX.md`, `docs/architecture/SOURCE_OF_TRUTH_MAP.md`, `docs/guides/DOCUMENTATION_GUIDE.md`, `docs/architecture/GLOSSARY.md` |
| **Tasks (receipts)** | KDOC-001…006 completed with those outputs |
| **Exceptions** | None that hide authority conflicts; **C-\*** / **U-\*** are part of the evidence packet |

### 4.3 KDOC-G020 — Bespoke system architecture guide set

| Field | Value |
|---|---|
| **Score** | **Met with residual** |
| **Artifacts** | `SYSTEM_OVERVIEW.md`, `RUNTIME_AND_ENTRYPOINTS.md`, `STORAGE_BACKEND_SYSTEM.md`, `CONTENT_METADATA_VFS.md`, `CLUSTER_COORDINATION.md`, `NETWORK_TRANSPORTS.md`, `MCP_CONTROL_PLANE.md`, `ASYNC_AND_OPTIONAL_DEPENDENCIES.md`, `CONFIGURATION_STATE_AND_TRUST.md`, `COMPATIBILITY_LAYERS.md` (all under `docs/architecture/`) |
| **Tasks** | KDOC-010…019 |
| **Exceptions** | Unresolved subsystem authorities remain in SOURCE_OF_TRUTH_MAP (U-04…U-16, etc.); guides must not be read as resolving Proposed ADRs |

### 4.4 KDOC-G030 — Architectural decision records and rationale

| Field | Value |
|---|---|
| **Score** | **Met with residual** |
| **Artifacts** | `docs/architecture/decisions/README.md`, `0000-template.md`, `0001`…`0009` |
| **Tasks** | KDOC-020…029 |
| **Decision status table** | See §5.2 |
| **Exceptions** | **Accepted:** ADR-0001, ADR-0002 only. **Proposed (intentional):** ADR-0003…0009. Do not cite Proposed as production policy. |

### 4.5 KDOC-G040 — Refreshed developer, user, integration, and operator journeys

| Field | Value |
|---|---|
| **Score** | **Met with residual** |
| **Artifacts** | `installation_guide.md`, `QUICK_REFERENCE.md`, `api/*` references, `reference/storage_backends.md`, `credential_management.md`, `VFS_CONTRACT_SPEC.md`, `filesystem_journal.md`, `operations/cluster_*.md`, `iroh/README.md`, `integration/INTEGRATION_*.md`, `development/testing_guide.md` |
| **Tasks** | KDOC-030…039 |
| **Exceptions** | **C-VER** labeled in install/quick-ref; residual `final_mcp_server_enhanced` in package docstring (**W-002**, product code — outside docs-only repair); some first-hop anchors soft-miss (**W-003**) |

### 4.6 KDOC-G050 — Information architecture, history, generated, and external boundaries

| Field | Value |
|---|---|
| **Score** | **Met** |
| **Artifacts** | `HISTORICAL_DOCUMENT_REGISTER.md`, `DUPLICATE_AND_REDIRECT_PLAN.md`, `ARCHIVE/README.md`, `api_generated/README.md`, `reference/EXTERNAL_DOCUMENTATION_SOURCES.md`, exclusive nav surfaces |
| **Tasks** | KDOC-040…046, KDOC-060 |
| **Exceptions** | External gitlinks remain **unfetched empty trees** by policy (not a documentation defect) |

### 4.7 KDOC-G060 — Repeatable freshness, generated-doc, and quality controls

| Field | Value |
|---|---|
| **Score** | **Met with residual** |
| **Artifacts** | `docs/development/DOCUMENTATION_VALIDATION.md`, `docs/workflows/documentation-maintenance.md`, `docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md`, this scorecard |
| **Tasks** | KDOC-043, KDOC-053, KDOC-054, KDOC-062 |
| **Exceptions** | Versioned unified `tools/docs_validate.py`, CI offline profiles, and generator `--mode check` are **separately authorized** (listed in maintenance §14); absence does not void offline gate specifications already written |

### 4.8 KDOC-G070 — Agent-oriented system map and change guidance

| Field | Value |
|---|---|
| **Score** | **Met** |
| **Artifacts** | `docs/architecture/AGENT_SYSTEM_MAP.md`, `docs/development/DOCUMENTATION_IMPACT_MAP.md`, `docs/guides/DEBUGGING_BY_SUBSYSTEM.md` |
| **Tasks** | KDOC-050…052 |
| **Exceptions** | None material |

### 4.9 KDOC-G080 — Program integration, navigation, and acceptance

| Field | Value |
|---|---|
| **Score** | **Met with residual** |
| **Artifacts** | Exclusive nav surfaces; `FINAL_NAVIGATION_AND_LINK_AUDIT.md`; this scorecard |
| **Tasks** | KDOC-060…062 |
| **Evidence criteria** | Final checks on merge target; exceptions enumerated; no lane-local substitute |
| **Acceptance** | Canonical navigation coherent; final audits pass; unresolved owner decisions visible; KDOC-G000 closeable without **hidden** stale claims |
| **Exceptions** | Owned warnings **W-001…W-005** / follow-ups **FU-001…FU-005** from KDOC-061 (carried in §8) |

---

## 5. Delivered coverage summaries

### 5.1 Architecture guides (KDOC-G020)

| Guide | Path | Present |
|---|---|---|
| System overview | `docs/architecture/SYSTEM_OVERVIEW.md` | Yes |
| Runtime & entry points | `docs/architecture/RUNTIME_AND_ENTRYPOINTS.md` | Yes |
| Storage backends | `docs/architecture/STORAGE_BACKEND_SYSTEM.md` | Yes |
| Content / metadata / VFS | `docs/architecture/CONTENT_METADATA_VFS.md` | Yes |
| Cluster coordination | `docs/architecture/CLUSTER_COORDINATION.md` | Yes |
| Network transports | `docs/architecture/NETWORK_TRANSPORTS.md` | Yes |
| MCP control plane | `docs/architecture/MCP_CONTROL_PLANE.md` | Yes |
| Async & optional deps | `docs/architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md` | Yes |
| Config / state / trust | `docs/architecture/CONFIGURATION_STATE_AND_TRUST.md` | Yes |
| Compatibility layers | `docs/architecture/COMPATIBILITY_LAYERS.md` | Yes |
| Architecture hub | `docs/architecture/README.md` | Yes |
| Glossary | `docs/architecture/GLOSSARY.md` | Yes |
| Source-of-truth map | `docs/architecture/SOURCE_OF_TRUTH_MAP.md` | Yes |
| Agent system map | `docs/architecture/AGENT_SYSTEM_MAP.md` | Yes |

### 5.2 ADR decision records (KDOC-G030)

| ADR | Title (short) | Decision status |
|---|---|---|
| 0000 | Template | Process (not a product decision) |
| 0001 | Lazy imports & optional dependencies | **Accepted** |
| 0002 | Backend configuration-plugin registry | **Accepted** |
| 0003 | MCP runtime authority | **Proposed** |
| 0004 | AnyIO / Trio / asyncio / sync boundaries | **Proposed** |
| 0005 | Content, metadata, durability | **Proposed** |
| 0006 | Multi-protocol storage & networking | **Proposed** |
| 0007 | Configuration, state, secret references | **Proposed** |
| 0008 | Cluster control-plane authority | **Proposed** |
| 0009 | Documentation site / toolchain | **Proposed** |

**Honest count:** 2 Accepted · 7 Proposed · 0 Rejected/Superseded. Majority-Proposed is **expected** for authority conflicts pending owner confirmation; architecture README forbids treating Proposed as settled production policy (KDOC-061 §4.8).

### 5.3 Current journeys & references (KDOC-G040)

Primary Current surfaces present: installation, quick reference, API / HLA / CLI / MCP references, storage backends, credentials, VFS contract, filesystem journal, cluster operations/state/monitoring, Iroh entry, integration overview/quick-start, testing guide.

### 5.4 History, generated, external (KDOC-G050)

| Boundary | Receipt | Control |
|---|---|---|
| Historical register | `docs/audits/HISTORICAL_DOCUMENT_REGISTER.md` | Disposition rules |
| Duplicate / redirect plan | `docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md` | Paper reconciliation before moves |
| Archive boundary | `docs/ARCHIVE/README.md` | Historical only |
| Generated contract | `docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md` + `docs/api_generated/*` | **Generated** banners; KDOC-046 refresh |
| External ownership | `docs/reference/EXTERNAL_DOCUMENTATION_SOURCES.md` | Gitlinks not fetched |

**Scorecard rule (from inventory):** Generated / External / Historical **must not** be counted as maintained Canonical coverage.

### 5.5 Agent & quality (KDOC-G060 / G070)

| Artifact | Path |
|---|---|
| Agent system map | `docs/architecture/AGENT_SYSTEM_MAP.md` |
| Documentation impact map | `docs/development/DOCUMENTATION_IMPACT_MAP.md` |
| Debugging by subsystem | `docs/guides/DEBUGGING_BY_SUBSYSTEM.md` |
| Offline validation gates | `docs/development/DOCUMENTATION_VALIDATION.md` |
| Maintenance workflow | `docs/workflows/documentation-maintenance.md` |

### 5.6 Exclusive navigation (KDOC-G080 / KDOC-060)

| Surface | Role | Local path links (KDOC-061 + re-check) |
|---|---|---|
| `docs/index.md` | Sole concise start-here | 100 OK |
| `docs/README.md` | Complete repository map | 153 OK |
| `docs/DOCUMENTATION_INDEX.md` | Structured catalog | 108 OK |
| `docs/architecture/README.md` | Architecture + ADR reading order | 101 OK |
| **Total** | Non-competing roles | **462 OK / 0 missing** |

---

## 6. Task board receipt summary (read-only)

Source of status labels: `docs/architecture/ipfs_kit_documentation.todo.md` (protected; **not** modified by this task).

| Wave / range | Tasks | Board status at scorecard time | Artifact check |
|---|---|---|---|
| Wave 0 evidence | KDOC-001…006 | completed | Outputs present |
| Architecture | KDOC-010…019 | completed | Outputs present |
| ADRs | KDOC-020…029 | completed | Outputs present (Proposed where required by validation) |
| Current docs | KDOC-030…039 | completed | Outputs present |
| History / generated / external | KDOC-040…046 | completed | Outputs present |
| Agent / quality | KDOC-050…054 | completed | Outputs present |
| Integration | KDOC-060, KDOC-061 | completed | Nav + final audit present; audit **Blocking findings: 0** |
| Scorecard | **KDOC-062** | was `todo` | **This file is the completion receipt** |

**Policy reminder:** Board drainage is **insufficient** by itself (KDOC-G000 evidence source policy). This section only corroborates that declared outputs were produced; §3–§4 are authoritative for close.

---

## 7. Validation evidence and gate roll-up

### 7.1 Final integration gate (KDOC-061)

| Gate | Result | Binding |
|---|---|---|
| Exclusive-nav broken local path links | **0** | Audit §3 / re-check §2.1 |
| Competing start-here authority | **None** | Audit §4.2 |
| ARCHIVE promoted as Current how-to from nav | **No** | Audit §4.5–4.6 |
| Hardcoded secrets on nav / primary quick-start | **None found** | Audit §4.4 |
| Open decisions hidden | **No** | Audit §4.8 |
| **Blocking findings** | **0** | Required string present |

### 7.2 Gate ID mapping (from DOCUMENTATION_VALIDATION / generated contract)

This scorecard consumes audit outcomes rather than re-running every offline gate profile. Mapping for operators:

| Concern | Gate family (spec) | Evidence used here |
|---|---|---|
| Links / anchors (canonical nav) | **V-LINK** | KDOC-061 exclusive-nav + scorecard re-check |
| Sensitive patterns | **V-SENS** | KDOC-061 §4.4 |
| Provenance / class labels | **V-PROV** | Nav material-class tables; Generated banners |
| Generated drift controls | **G-*** / **V-GEN** | GENERATED_DOCUMENTATION_CONTRACT; 2026-08-04 stamps at audit commit |
| Subsystem / claim hygiene | **V-SUB** (partial) | Final audit entry-point/path claims; residual W-002 outside nav |
| Presence-only tools | **V-PRES** | Explicitly **not** used as accuracy authority |

**Fail-closed honesty:** Full automated **Release-docs** profile (unified checker script) is **not claimed**. Specifications exist; CI wiring is residual (§10).

### 7.3 Reporting envelope (scorecard fill)

```text
profile: report-only (final program scorecard)
tree: c2d8d405578ed597ff81696880fbae66a4fa307a
env:
  IPFS_KIT_AUTO_INSTALL_BINARIES: "0"
  network: offline-assumed
results:
  - id: KDOC-061-BLOCKERS
    severity: blocker
    status: pass
    findings: []
  - id: V-LINK-EXCLUSIVE-NAV
    severity: blocker
    status: pass
    findings: []   # 462 links, 0 missing paths at scorecard re-check
  - id: V-SENS-NAV
    severity: blocker
    status: pass
    findings: []
  - id: G000-CHILD-OUTPUTS
    severity: blocker
    status: pass
    findings: []   # all declared child outputs non-empty
  - id: ADR-PROPOSED-MAJORITY
    severity: warning
    status: pass   # visible, not hidden
    findings: ["7 of 9 ADRs Proposed (by design for owner confirmation)"]
  - id: C-VER
    severity: warning
    status: pass   # labeled in Current install/quick-ref + SOT map
    findings: ["packaging 0.3.0 vs __version__ 0.2.0"]
  - id: W-001..W-005
    severity: warning
    status: pass   # owned residuals from KDOC-061
    findings: ["see §8"]
summary:
  blockers: 0
  warnings: 5 (owned) + open U-01..U-18 (owner decisions)
  presence_only_used_for_accuracy: false
```

---

## 8. Known warnings and exceptions (honest)

Imported from KDOC-061 and re-confirmed as still applicable on scorecard HEAD (product code and anchor issues were not repaired by this docs-only task).

| ID | Severity | Issue | Owner | Blocks KDOC-G000 close? |
|---|---|---|---|---|
| **W-001** | Medium | Catalog deep-link slug `DOCUMENTATION_INDEX` → `README.md#23-operator--sre` vs GFM `#23-operator-sre` | Navigation maintainer | **No** (file opens; scroll may miss) |
| **W-002** | Medium | Residual `final_mcp_server_enhanced` in `ipfs_kit_py/__init__.py` docstring | API / package surface owner | **No** (cleared on exclusive nav; residual outside nav) |
| **W-003** | Low | First-hop internal anchor drift in some Current guides | Content owners | **No** |
| **W-004** | Warning | Packaging `0.3.0` vs runtime `__version__` `0.2.0` (**C-VER** / **U-01**) | Packaging / release owner | **No** (labeled in Current docs) |
| **W-005** | Info/Warning | 7/9 ADRs remain **Proposed** | Architecture decision owners | **No** (visibility requirement met) |

### 8.1 Follow-ups carried from KDOC-061

| ID | Action | Priority | Blocks scorecard? |
|---|---|---|---|
| FU-001 | Fix catalog fragment slug or add HTML anchor | P2 | No |
| FU-002 | Remove/rewrite package docstring stale MCP script | P1 | No |
| FU-003 | Repair first-hop heading anchors when docs next edited | P3 | No |
| FU-004 | Resolve **C-VER** in a release change | P1 | No |
| FU-005 | Advance **Proposed** ADRs via owner decisions | P1 program | No |
| FU-006 | This scorecard consumes audit commit binding and warning list | **Done** | — |

### 8.2 Prior criticals disposition (navigation-relevant)

| Prior | Topic | Status |
|---|---|---|
| F-001 | Root cluster launcher on index | **Cleared on exclusive nav** |
| F-002 | `final_mcp_server_enhanced` as MCP start on nav | **Cleared on exclusive nav**; residual → W-002 |
| F-003 | Competing MCP families without ranking | **Nav-safe**; **C-MCP-TREES** / ADR-0003 still open |
| F-007 | Generated stamp drift | **Cleared** in generated tree at audit commit |
| F-012 | Competing indexes | **Cleared** by KDOC-060 role model |

---

## 9. Unresolved owner decisions (must remain visible)

### 9.1 Aggregate unknowns (SOURCE_OF_TRUTH_MAP)

| ID | Topic | Related conflict | Primary docs |
|---|---|---|---|
| U-01 | Package version string `0.2.0` vs `0.3.0` | C-VER | Runtime overview, release docs |
| U-02 | Canonical CLI composition | C-CLI | Runtime, operator guides |
| U-03 | High-level API package stub vs legacy module | C-HLA | Python API docs |
| U-04 | Backend live-adapter factory / dual `ipfs_backend` | — | Storage guide |
| U-05 | Bucket/VFS manager authority | — | Content/VFS guide |
| U-06 | WAL/journal durability per backend | — | Content/VFS, ADR-0005 |
| U-07 | Arrow metadata authoritative vs rebuildable | — | Content/VFS, ADR-0005 |
| U-08 | Bespoke cluster vs Kubo Cluster vs MCP++ | — | Cluster guide, ADR-0008 |
| U-09 | Default content transport | — | Network guide, ADR-0006 |
| U-10 | libp2p pin/track and MCP P2P requirements | — | Network, MCP guides |
| U-11 | MCP production runtime authority | C-MCP-TREES | MCP guide, ADR-0003 |
| U-12 | Canonical `ipfs_py` client among three classes | — | Runtime, MCP, storage |
| U-13 | Config/state directory and credential composition | — | Trust guide, ADR-0007 |
| U-14 | AnyIO end-state and missing-extra degradation | — | Async guide, ADR-0001/0004 |
| U-15 | Generated-doc toolchain and nav exclusivity | — | ADR-0009, maintenance |
| U-16 | Daemon manager authority among parallel stacks | — | Runtime, operations |
| U-17 | fsspec supported protocol set | C-FSSPEC | Storage, integration |
| U-18 | MCP published tool count / JS manifest parity | C-MCP-TOOLS | MCP guide, SDK |

### 9.2 Named surface conflicts (illustrative)

| ID | Summary |
|---|---|
| **C-VER** | Packaging version ≠ `__version__` |
| **C-CLI** | FastCLI vs unified dispatcher composition |
| **C-HLA** | Dual high-level API module identity |
| **C-FSSPEC** | Packaged Iroh fsspec vs import-time multi-protocol registration |
| **C-MCP-TREES** | `mcp_server` vs legacy `mcp/` / root trees |
| **C-MCP-TOOLS** | Registry tool count vs JS manifest vs README claims |
| **C-INSTALL-DOC** | Package docstring / install narrative residuals |

**Documentation program stance:** Keeping these open and labeled **satisfies** KDOC-G000’s “do not invent history / do not hide conflicts” requirement. Closing product conflicts is **not** a prerequisite to close the documentation goal.

---

## 10. Maintenance handoff

| Concern | Owner / artifact | Cadence hint |
|---|---|---|
| Offline validation gates | `docs/development/DOCUMENTATION_VALIDATION.md` | PR / pre-release profiles when CI lands |
| Generated tree refresh | KDOC-043 contract; KDOC-046 procedure; maintenance workflow | After public surface / packaging changes |
| Navigation exclusivity | KDOC-060 surfaces; re-run KDOC-061 after nav edits | On nav PRs |
| Claim / lifecycle standard | `docs/guides/DOCUMENTATION_GUIDE.md` | Authoring-time |
| Agent change impact | `DOCUMENTATION_IMPACT_MAP.md` | Before docs-affecting code PRs |
| Separately authorized automation | Maintenance §14 (checker script, CI, workflow repairs) | Requires explicit authorization |
| This scorecard | Re-issue after material corpus or authority changes | Pre-release or major doc campaigns |

**Baseline commit for future freshness audits:** use scorecard HEAD `c2d8d405578ed597ff81696880fbae66a4fa307a` (or the merge commit that lands this file on the integration branch) as the new documentation campaign baseline unless an operator pins a later tag.

---

## 11. Operator decision checklist for KDOC-G000

Use this table to **close** or **continue**.

| # | Check | Result at issue time | Close if… |
|---|---|---|---|
| 1 | All child-goal declared outputs non-empty on merge target | **Yes** | Yes |
| 2 | Exclusive navigation coherent (roles non-competing) | **Yes** (KDOC-060 + 061) | Yes |
| 3 | Final navigation/link/claim audit **Blocking findings: 0** | **Yes** | Yes |
| 4 | Scorecard present, binds commits, traces root criteria | **Yes** (this file) | Yes |
| 5 | Unresolved owner decisions visible (not hidden) | **Yes** (§9) | Yes |
| 6 | High-severity stale nav claims corrected or quarantined | **Yes** (F-001/F-002 cleared on nav) | Yes |
| 7 | Exceptions owned with follow-ups | **Yes** (§8) | Yes |
| 8 | Operator accepts residual **Proposed** ADRs / **U-\*** as non-blockers | **Operator judgment** | Close if yes; **Continue** if product-authority freeze required first |

### 11.1 Recommended operator actions

**To CLOSE KDOC-G000 (recommended):**

1. Accept this scorecard and KDOC-061 as terminal documentation receipts on the integration branch.
2. Record residual **FU-001…FU-005** and **U-01…U-18** on the **product/architecture** backlog (outside the documentation program board if desired).
3. Update program-control status only through the **protected** objectives/todo process (not by worker agents under this edit policy).
4. Point future freshness baselines at the merge commit that includes this scorecard.

**To CONTINUE KDOC-G000 (alternative):**

1. Require re-run of KDOC-061 after landing FU-001 / content anchor repairs, or after resolving C-VER / MCP authority in code.
2. Do **not** treat missing product decisions as “undocumented” — they are documented as open.

---

## 12. Acceptance checklist (KDOC-062)

| Criterion | Met? |
|---|---|
| Scorecard traces every **KDOC-G000** root criterion to a merged artifact/receipt | **Yes** — §3 |
| Child goals G010–G080 traced with artifacts | **Yes** — §4 |
| Exceptions reported honestly with owners | **Yes** — §8–§9 |
| Enough evidence for operator to **close or continue** KDOC-G000 | **Yes** — Operator judgment + §11 |
| Binds Git commit(s) for final audit and scorecard tree | **Yes** — header |
| Does not mark goals complete in protected files | **Yes** — conflict policy |
| Output path | `docs/audits/FINAL_DOCUMENTATION_SCORECARD.md` |
| Mentions **KDOC-G000** (task validation) | **Yes** |

### Validation commands (task contract)

```bash
test -s docs/audits/FINAL_DOCUMENTATION_SCORECARD.md && rg -q "KDOC-G000" docs/audits/FINAL_DOCUMENTATION_SCORECARD.md
```

---

## 13. Summary judgment

| Dimension | Judgment |
|---|---|
| **Documentation program completeness** | **Complete** on the merge target for declared KDOC outputs through KDOC-062 |
| **Canonical navigation** | **Coherent**; 0 blocking link/claim findings |
| **Architecture & rationale** | **Delivered**; open decisions **visible** (2 Accepted ADRs, 7 Proposed) |
| **Current journeys** | **Delivered** with labeled version conflict and owned residuals |
| **History / Generated / External** | **Bounded and labeled**; not counted as Canonical |
| **Agent & quality controls** | **Delivered** as prose contracts; automation backlog separate |
| **KDOC-G000** | **Closeable** with residual product/owner follow-ups — **not** blocked by hidden documentation debt |

**Final recommendation:** Operators should **CLOSE KDOC-G000** as the documentation program root goal, retaining §8–§10 as the living residual register for packaging, MCP authority, ADR confirmation, and separately authorized CI tooling.

---

*End of KDOC-062 final documentation scorecard. Program namespace: `ipfs-kit-documentation-architecture-v2`.*
