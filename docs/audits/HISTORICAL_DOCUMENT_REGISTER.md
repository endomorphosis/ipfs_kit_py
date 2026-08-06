# Historical Document Register and Disposition Rules

| Field | Value |
|---|---|
| **Task** | KDOC-040 — Create the historical-document register and disposition rules |
| **Goal** | KDOC-G050 |
| **Track** | information-architecture |
| **Register date** | 2026-08-03 |
| **Tree baseline** | Git commit `52dc5a8211a54c1404dbbb5ff86306d8acaa79fc` (Wave 0 / documentation-supervisor worktree) |
| **Inventory baseline** | KDOC-001 — `docs/audits/DOCUMENTATION_INVENTORY.md` (corpus walk; counts 457 files / 403 markdown) |
| **Freshness baseline** | KDOC-003 — `docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md` (findings F-011, F-012, F-014 and family risk table §6) |
| **Lifecycle contract** | KDOC-005 — `docs/guides/DOCUMENTATION_GUIDE.md` (authority classes; Historical may not recommend as current) |
| **Scope** | Report-like, completion, status, fix, test-campaign, migration, roadmap, and already-archived documentation under `docs/` |
| **Non-goals** | File moves, mass banners, navigation rewrites, generated-doc contracts, external gitlink fetch |
| **Conflict policy** | **Register only.** No renames, ARCHIVE moves, or index edits in this task (KDOC-041/042/045 consume this register). |

This register is the **paper authority** for classifying dated implementation, status, fix, test, migration, roadmap, coverage, and completion material. It does **not** execute moves. Later tasks apply dispositions under explicit owner batches.

**Consumers**

| Downstream task | Use of this register |
|---|---|
| **KDOC-041** | Duplicate sets and competing paths among historical families |
| **KDOC-042** | Archive boundary README and “not current” reading guidance |
| **KDOC-045** | Curated ARCHIVE subtrees (`implementation/`, status-and-fixes) using reviewed dispositions |
| **KDOC-060** | Drop historical material from exclusive navigation |
| **KDOC-030..039** | Replacement targets for present-tense how-to content still living only in reports |

---

## 1. Disposition vocabulary

Every register row uses one **Disposition** (primary intent). Sub-notes may qualify split families.

| Disposition | Intent | Navigation treatment | Physical move? |
|---|---|---|---|
| **Retain-historical** | Keep in place (or under `ARCHIVE/`) as provenance; never present as current how-to | Drop from current recommendations; optional “history” section only | Optional later |
| **Archive** | Move into `docs/ARCHIVE/…` under KDOC-042/045 when replacements exist or links are redirected | Exclude from current indexes | Yes (later batch) |
| **Supersede** | Content is replaced by a named canonical/proposed guide; historical file becomes provenance only | Link to replacement; banner on historical file later | Prefer archive after banner |
| **Merge** | Multiple reports cover the same episode; consolidate narrative into one historical artifact or one current guide | Keep one survivor; others archive | Yes for non-survivors |
| **Drop-from-navigation** | Leave file path for now; remove from landing indexes, README maps, and agent start paths | Immediate nav exclusion (KDOC-060) | Not required for correctness |
| **Split** | Family is Mixed: keep some paths canonical/process; reclassify report-like children as historical | Per-path | Partial |
| **Retain-in-place (labeled)** | Useful migration or design history that should stay path-stable but must carry Historical labels | Labeled history only | No |

> **Rule:** A disposition is a **planning decision**, not a completed move. “Archive” means *scheduled for* KDOC-042/045, not “already moved.”

### 1.1 Move-risk scale

| Move risk | Meaning | When to use |
|---|---|---|
| **Critical** | High inbound link density from primary indexes / install paths; wrong move breaks agent workflows | Root reports linked from `docs/index.md`, `docs/README.md`, `DOCUMENTATION_INDEX.md` |
| **High** | Many cross-links from guides or competing indexes; needs redirect plan (KDOC-041) before mass move | `docs/implementation/`, large completion clusters |
| **Medium** | Moderate internal links; safe to batch-move after ARCHIVE README exists | `status_reports/`, `fixes/`, `project/`, testing campaigns |
| **Low** | Already quarantined, low discovery, or sparse inbound links | `docs/ARCHIVE/*`, `test_reports/`, most one-off fixes already under ARCHIVE |
| **None (do not move yet)** | Path is Mixed or still supplies unique process value until a replacement is written | Split families (`testing/` health matrix, `ci-cd/` runbooks, live architecture guides) |

### 1.2 Batch owners

Batch owners are **program task IDs** (and lane), not individual humans. They own execution order and conflict avoidance.

| Batch owner ID | Scope | Executes under |
|---|---|---|
| **BATCH-HIST-IMPL** | `docs/implementation/**` completion bulk | KDOC-045 (+ KDOC-041 for duplicates) |
| **BATCH-HIST-STATUS** | `docs/status_reports/**`, root status/PR summaries | KDOC-045 |
| **BATCH-HIST-FIX** | `docs/fixes/**` | KDOC-045 |
| **BATCH-HIST-PROJECT** | `docs/project/**` Feb overhaul / completion | KDOC-045 / KDOC-041 |
| **BATCH-HIST-MIG** | `docs/migration/**` + root AnyIO/MCP migration echoes | KDOC-041 then label/retain or archive |
| **BATCH-HIST-TEST** | Coverage campaigns under `docs/testing/` + root `TEST_COVERAGE_*` / `PHASE*` / `PATH_TO_*` / `100_PERCENT_*` | KDOC-041 + KDOC-039 (replacement testing guide) + KDOC-045 |
| **BATCH-HIST-ROOT** | Root-level report/roadmap/migration loose files | KDOC-041, KDOC-060, KDOC-045 |
| **BATCH-HIST-CICD** | Report-like subset of `docs/ci-cd/` | Ops retain + KDOC-045 for reports |
| **BATCH-HIST-FEAT** | Feature-tree `*COMPLETE*` / `*SUMMARY*` reports mixed into guides | Feature owners + KDOC-041 |
| **BATCH-HIST-ARCH** | Pre-program architecture audits (not Wave 0 evidence guides) | KDOC-010..019 supersession, then KDOC-045 optional archive |
| **BATCH-HIST-ARCHIVE** | Material already under `docs/ARCHIVE/` | KDOC-042 boundary README only |
| **BATCH-HIST-TESTREP** | `docs/test_reports/**` | KDOC-045 / Retain-historical |

---

## 2. Classification decision rules

Apply rules in order. First matching rule wins for a given path.

1. **Already under `docs/ARCHIVE/`** → **Retain-historical** (move risk **Low**). Boundary narrative is KDOC-042.
2. **Authority class Canonical/Generated/External/Program-control** (inventory) and not report-like → **out of scope** for this register (do not disposition as historical).
3. **Name or content is completion/status/fix/PR/coverage campaign** (`*COMPLETE*`, `*SUMMARY*`, `*FINAL*`, `*STATUS*`, phase/coverage roadmaps, dated results) **and** not the sole current guide for a subsystem → **Archive** or **Drop-from-navigation** (prefer Archive after KDOC-041 redirects).
4. **Migration batch / test result dumps with dates** → **Retain-in-place (labeled)** or **Archive**; never present as current async/MCP authority (see F-003, F-009).
5. **Duplicate episode coverage** (same refactoring told 2+ times) → **Merge** survivor + **Archive** others (KDOC-041 picks survivor).
6. **Report co-located with a still-useful guide family** (`features/`, `testing/`, `ci-cd/`, `architecture/`) → **Split**: register only the report-like children; retain process docs under their current owners.
7. **Present-tense claims that contradict packaging/source** (F-003, F-005, F-011, F-014, F-020) → **Supersede** with the named current guide/ADR task; historical file must not remain linked as operator truth.
8. When uncertain → **Drop-from-navigation** first (safe), defer physical **Archive** until KDOC-041 records redirects.

### 2.1 What “current authority” means in this register

| Value | Meaning |
|---|---|
| **Historical (provenance only)** | File/family is not an accepted current guide |
| **Mixed — see split** | Some children remain candidate-canonical; listed children are historical |
| **Canonical (replacement target)** | Named path is (or will be) the current guide; historical rows point here |
| **Unresolved / program** | Wave 0 evidence or protected program files; not historical bulk |

### 2.2 Replacement / link policy

- Prefer **future architecture / user-doc task outputs** when they already exist or are scheduled (KDOC-010..019, KDOC-030..039).
- If no replacement exists yet, set replacement to **“none yet — Drop-from-navigation until &lt;task&gt;”** rather than inventing a fake canonical path.
- Root competing indexes (`docs/index.md`, `docs/README.md`, `docs/DOCUMENTATION_INDEX.md`) are **not** replacements for historical reports; they are navigation surfaces that must **stop promoting** them (KDOC-060).

---

## 3. High-risk family register (acceptance matrix)

Every **high-risk family** appears below with the six required fields: **source path**, **date/baseline if known**, **current authority**, **replacement/link**, **move risk**, and **batch owner**, plus an explicit **Disposition**.

“High-risk” here means: inventory/freshness **Critical** or **High** when treated as current guidance, or large historical bulk that pollutes navigation (F-011/F-014), including already-quarantined material that still needs register rows for complete history-boundary coverage.

| # | Source path (family) | Date / baseline if known | Current authority | Replacement / link | Move risk | Batch owner | Disposition |
|---|---|---|---|---|---|---|---|
| H1 | `docs/implementation/` (75 files / 73 md) | Mostly pre–Wave 0; sample `EXECUTIVE_SUMMARY.md` dated **2025-10-22**; July 2026 DOC-KIT link campaign elevated discoverability | **Historical (provenance only)** | Architecture: `docs/architecture/*` (KDOC-010..019); subsystem guides under `features/`, `operations/`, `reference/`; never cite `*_COMPLETE.md` as live API proof (F-005/F-011) | **High** | **BATCH-HIST-IMPL** | **Archive** (bulk) after redirects; interim **Drop-from-navigation** |
| H2 | `docs/` root — coverage / phase / PR report cluster | Feb 2026 overhaul era + later coverage campaigns; F-014 set dated relative to Feb 2, 2026 project docs | **Historical (provenance only)** | Testing process: `docs/development/testing_guide.md` (KDOC-039); do not use as live coverage % | **Critical** (index-linked) | **BATCH-HIST-ROOT** / **BATCH-HIST-TEST** | **Archive** + **Drop-from-navigation** |
| H3 | `docs/` root — AnyIO / MCP migration echoes | AnyIO complete claim **2026-01-24** (`migration/ANYIO_MIGRATION_COMPLETE.md`); MCP migration guide undated, authority conflict F-003 | **Historical / Mixed (must not rank MCP runtime)** | Async: KDOC-016 / `docs/development/async_architecture.md` (after fix); MCP: packaging `ipfs-kit-mcp` + KDOC-014 / `MCP_CONTROL_PLANE.md` | **High** | **BATCH-HIST-MIG** / **BATCH-HIST-ROOT** | **Supersede** (authority) + **Merge** with `docs/migration/` then **Archive** duplicates |
| H4 | `docs/` root — feature roadmaps | Undated / mixed with open checklists (`ROADMAP_FEATURES.md`, `performance_optimization_roadmap.md`) | **Proposed / Historical** (not implemented-as-stated) | Label as Proposed; current feature truth from source + `docs/features/` verified guides | **Medium** | **BATCH-HIST-ROOT** | **Drop-from-navigation**; retain labeled or archive after KDOC-041 |
| H5 | `docs/status_reports/` (18 md) | Pre–Wave 0 refactoring/integration summaries (undated headers common) | **Historical (provenance only)** | Architecture + subsystem guides; MCP status → KDOC-014 materials, not ARCHIVE MCP status as “current” (F-017) | **Medium** | **BATCH-HIST-STATUS** | **Archive** |
| H6 | `docs/fixes/` (14 md) | One-off fix write-ups; undated / campaign-era | **Historical (provenance only)** | None as guides; track product fixes in CHANGELOG / issues | **Medium** | **BATCH-HIST-FIX** | **Archive** |
| H7 | `docs/project/` (7 md) | **February 2, 2026** overhaul & completion set (`COMPREHENSIVE_DOCUMENTATION_OVERHAUL.md`, `DOCUMENTATION_AUDIT_FINDINGS.md`, completion summaries) | **Historical (provenance only)** | Program plan: `docs/documentation_plan.md` (protected); inventory/freshness audits replace audit findings as live evidence | **Medium** | **BATCH-HIST-PROJECT** | **Retain-historical** or **Archive**; **never** cite as live verification receipt (F-015) |
| H8 | `docs/migration/` (8 md) | AnyIO batches through **2026-01-24** complete; MCP + secrets guides | **Historical (Retain-in-place labeled)** | Current async/MCP/secrets guidance from architecture + operator docs after refresh; packaging ranks MCP entry | **Medium** | **BATCH-HIST-MIG** | **Retain-in-place (labeled)**; **Supersede** false “canonical runtime” claims (F-003) |
| H9 | `docs/testing/` — coverage campaign subset | **2026-02-02** (`FINAL_100_PERCENT_COVERAGE_STATUS.md`); Path C / 100% initiative cluster | **Mixed — campaigns Historical** | **Canonical retain:** `TEST_HEALTH_MATRIX.md`, process notes feeding KDOC-039; campaigns → Archive | **Medium** | **BATCH-HIST-TEST** | **Split**: Archive campaigns; retain health/process |
| H10 | `docs/test_reports/` (4 md) | Dated CLI/cluster/MCP result dumps | **Historical (provenance only)** | Focused pytest + CI as live evidence; not these dumps | **Low** | **BATCH-HIST-TESTREP** | **Retain-historical** (or Archive under test-reports) |
| H11 | `docs/ARCHIVE/` (21 md) | Quarantined; sample `MCP_DEVELOPMENT_STATUS.md` **2025-07-10**; Feb 2026 tree organization | **Historical (already quarantined)** | None as current; KDOC-042 README must state **not current** | **Low** | **BATCH-HIST-ARCHIVE** | **Retain-historical** |
| H12 | `docs/ci-cd/` — report/status subset | Campaign-era runner/workflow status reports | **Mixed — reports Historical** | **Canonical retain:** `CI_CD_VALIDATION_GUIDE.md`, `RUNNER_*` how-tos after verify; reports → Archive | **Medium** | **BATCH-HIST-CICD** | **Split** |
| H13 | `docs/features/` — report-like children | e.g. `STORAGE_FEATURES_DOCUMENTATION_COMPLETE.md` **2026-02-02**; auto-healing `*_SUMMARY.md` | **Mixed — reports Historical** | Feature guides in same tree after KDOC feature refresh; architecture storage/MCP guides | **Medium** | **BATCH-HIST-FEAT** | **Split** / **Archive** reports only |
| H14 | `docs/architecture/` — pre-program audits & summaries | Pre-MCP++ / pre-Iroh era audits; co-located with Wave 0 maps and new guides | **Mixed — audits Historical / evidence** | Wave 0: `SOURCE_OF_TRUTH_MAP.md`, `GLOSSARY.md`; new guides: `SYSTEM_OVERVIEW.md`, `RUNTIME_AND_ENTRYPOINTS.md`, `COMPATIBILITY_LAYERS.md`, `MCP_CONTROL_PLANE.md`, etc. (KDOC-010..019) | **None (do not move yet)** until guides stable | **BATCH-HIST-ARCH** | **Supersede** by new guides; optional later Archive of pure audits |
| H15 | Competing root **indexes** promoting history (not content families) | July 2026 DOC-KIT; inventory §4.1 Critical | **Mixed / navigation defect** | Exclusive landing: KDOC-060 (`docs/index.md` sole current map) | **Critical** (link graph) | **BATCH-HIST-ROOT** + KDOC-060 | **Drop-from-navigation** for historical targets; indexes themselves are **not** archived here |

**Acceptance field check:** every H1–H15 row includes source path, date/baseline, current authority, replacement/link, move risk, batch owner, and Disposition.

---

## 4. Family detail — high-risk historical bulk

### 4.1 H1 — `docs/implementation/` (largest historical bulk)

| Field | Value |
|---|---|
| **Source path** | `docs/implementation/` |
| **Scale** | 75 files / 73 markdown (KDOC-001) |
| **Date / baseline** | Implementation-campaign era through mid-2025–2026; example `EXECUTIVE_SUMMARY.md` **2025-10-22**; last DOC-KIT touch wave July 2026 elevated links without re-authoring as architecture |
| **Current authority** | **Historical (provenance only)** — not subsystem architecture |
| **Replacement / link** | Per-topic: VFS/bucket → KDOC-015 / `CONTENT_METADATA_VFS.md` + feature VFS docs; cluster → KDOC-013 / operations; MCP → KDOC-014; storage backends → KDOC-012; pins/WAL → reference guides. **Do not** use `WAL_FS_JOURNAL_REMOVAL_COMPLETE.md`-class files as CLI truth (freshness §5). |
| **Move risk** | **High** — dense `*COMPLETE*` / `*SUMMARY*` linkage from indexes (F-011; ~134 COMPLETE/SUMMARY paths corpus-wide) |
| **Batch owner** | **BATCH-HIST-IMPL** (KDOC-045 primary) |
| **Disposition** | **Archive** under future `docs/ARCHIVE/implementation/` (KDOC-045 output); until then **Drop-from-navigation** |

**Representative members (not exhaustive):**

| Path pattern | Notes |
|---|---|
| `*_COMPLETE.md`, `*_IMPLEMENTATION_COMPLETE.md` | Phase completion banners |
| `*_SUMMARY.md`, `EXECUTIVE_SUMMARY.md`, `FINAL_IMPLEMENTATION_*` | Executive / final narratives |
| `FILECOIN_PIN_*`, `CLUSTER_*`, `DAEMON_*`, `ENHANCED_VFS_*` | Subsystem episodes — extract claims only via current source+tests |
| `BATCH7_VERIFICATION.txt`, `COMPLETION_SUMMARY.txt` | Non-md provenance dumps |

**Evidence:**

```bash
find docs/implementation -type f | wc -l
find docs/implementation -type f -name '*.md' | wc -l
find docs/implementation -type f -name '*COMPLETE*' | wc -l
```

---

### 4.2 H2 / H3 / H4 — Root loose-file historical clusters

Root `docs/*.md` is **Mixed** (inventory §4.9). Only report-like / migration / roadmap clusters are in-scope here. Program-control and live topic guides are **excluded**.

#### H2 — Coverage, phase, and PR reports

| Field | Value |
|---|---|
| **Source path** | Root files: `100_PERCENT_COVERAGE_ROADMAP.md`, `PATH_TO_100_PERCENT_COVERAGE.md`, `PHASE5_FINAL_REPORT.md`, `PHASE6_COMPLETE_COVERAGE_REPORT.md`, `PHASE6_FINAL_SUMMARY.md`, `PHASE6_TESTING_GUIDE.md`, `TEST_COVERAGE_EXTENSION.md`, `TEST_COVERAGE_FINAL.md`, `TEST_COVERAGE_IMPROVEMENTS.md`, `TEST_COVERAGE_PHASE3.md`, `FINAL_TEST_COVERAGE_REPORT.md`, `FINAL_COMPREHENSIVE_PR_SUMMARY.md`, `COMPLETE_PR_SUMMARY.md` |
| **Date / baseline** | Coverage initiative docs align with **Feb 2026** project wave; F-014 records internal conflict (~63% overall language vs “100% complete” banners) |
| **Current authority** | **Historical** — not live coverage proof |
| **Replacement / link** | `docs/development/testing_guide.md` (KDOC-039); CI workflows + `pytest.ini` as process authority |
| **Move risk** | **Critical** if linked from primary indexes |
| **Batch owner** | **BATCH-HIST-ROOT** + **BATCH-HIST-TEST** |
| **Disposition** | **Archive** + **Drop-from-navigation** |

#### H3 — Root migration echoes

| Field | Value |
|---|---|
| **Source path** | `docs/ANYIO_MIGRATION.md`, `docs/COMPLETE_ANYIO_MIGRATION_SUMMARY.md`, `docs/MCP_SERVER_MIGRATION_GUIDE.md` |
| **Date / baseline** | Pair with `docs/migration/*` (**AnyIO complete 2026-01-24**); MCP guide conflicts packaging entry (F-003) |
| **Current authority** | **Historical**; MCP guide must not rank `unified_mcp_server` as sole production runtime |
| **Replacement / link** | Merge into `docs/migration/` historical set; MCP operator truth → KDOC-014 / packaging `ipfs-kit-mcp`; async → KDOC-016 |
| **Move risk** | **High** |
| **Batch owner** | **BATCH-HIST-MIG** / **BATCH-HIST-ROOT** |
| **Disposition** | **Merge** + **Supersede** + **Archive** non-survivors |

#### H4 — Root roadmaps (proposed / historical)

| Field | Value |
|---|---|
| **Source path** | `docs/ROADMAP_FEATURES.md`, `docs/performance_optimization_roadmap.md` |
| **Date / baseline** | Mixed / open checklists (not a closed baseline) |
| **Current authority** | **Proposed** or stale roadmap — not implemented-as-stated |
| **Replacement / link** | Feature owners; CHANGELOG; verified `docs/features/*` guides |
| **Move risk** | **Medium** |
| **Batch owner** | **BATCH-HIST-ROOT** |
| **Disposition** | **Drop-from-navigation**; label Proposed or Archive after KDOC-041 |

**Evidence:**

```bash
find docs -maxdepth 1 -type f -name '*.md' | rg -i 'PHASE|TEST_COVERAGE|COMPLETE_|FINAL_|ROADMAP|PATH_TO|100_PERCENT|ANYIO|MIGRATION' | sort
```

---

### 4.3 H5 — `docs/status_reports/`

| Field | Value |
|---|---|
| **Source path** | `docs/status_reports/` |
| **Scale** | 18 markdown |
| **Date / baseline** | Refactoring / integration campaign era; headers often undated |
| **Current authority** | **Historical (provenance only)** |
| **Replacement / link** | Architecture guides + subsystem runbooks; do not deep-link ARCHIVE/status as “implementation status” from current pages (F-017) |
| **Move risk** | **Medium** |
| **Batch owner** | **BATCH-HIST-STATUS** |
| **Disposition** | **Archive** → future `docs/ARCHIVE/status-and-fixes/` (KDOC-045) |

**Members:** `MCP_REFACTORING_SUMMARY.md`, `MCP_SERVER_REFACTORING_SUMMARY.md`, `REFACTORING_COMPLETE_SUMMARY.md`, `PRIORITY_*_SUMMARY.md`, `*_INTEGRATION_SUMMARY.md`, backend review notes, GitHub CLI caching series, folder reorganization summaries.

---

### 4.4 H6 — `docs/fixes/`

| Field | Value |
|---|---|
| **Source path** | `docs/fixes/` |
| **Scale** | 14 markdown |
| **Date / baseline** | One-off fix campaigns (undated) |
| **Current authority** | **Historical** |
| **Replacement / link** | None as guides; product CHANGELOG / issues |
| **Move risk** | **Medium** (some may be linked from old indexes) |
| **Batch owner** | **BATCH-HIST-FIX** |
| **Disposition** | **Archive** (pair with ARCHIVE/fixes already present) |

---

### 4.5 H7 — `docs/project/`

| Field | Value |
|---|---|
| **Source path** | `docs/project/` |
| **Scale** | 7 markdown |
| **Date / baseline** | **February 2, 2026** — `COMPREHENSIVE_DOCUMENTATION_OVERHAUL.md`, `DOCUMENTATION_AUDIT_FINDINGS.md`; completion summaries same wave |
| **Current authority** | **Historical** provenance for Feb tree organization |
| **Replacement / link** | Live program: protected `docs/documentation_plan.md`; live evidence: `docs/audits/*` (KDOC-001/003); completion language must not override open roadmaps (F-014) |
| **Move risk** | **Medium** |
| **Batch owner** | **BATCH-HIST-PROJECT** |
| **Disposition** | **Retain-historical** in place *or* **Archive** after KDOC-041; **never** treat checklist “fixed” rows as current verification (F-015) |

---

### 4.6 H8 — `docs/migration/`

| Field | Value |
|---|---|
| **Source path** | `docs/migration/` |
| **Scale** | 8 markdown |
| **Date / baseline** | AnyIO batch summaries; **Migration Completed: 2026-01-24** in `ANYIO_MIGRATION_COMPLETE.md`; MCP + secrets guides |
| **Current authority** | **Historical — Retain-in-place (labeled)** |
| **Replacement / link** | Operator async/MCP/secrets docs after KDOC-016/014/security refresh; packaging for MCP entry points |
| **Move risk** | **Medium** (path stability useful for git archaeology) |
| **Batch owner** | **BATCH-HIST-MIG** |
| **Disposition** | **Retain-in-place (labeled)**; **Supersede** any present-tense “canonical server” ranking that contradicts `pyproject.toml` (F-003); **Merge** root migration echoes here before archive |

**Members:** `ANYIO_MIGRATION_BATCH6_SUMMARY.md` … `BATCH8_9`, `ANYIO_MIGRATION_COMPLETE.md`, `ANYIO_MIGRATION_STATUS.md`, `ANYIO_MIGRATION_TEST_RESULTS.md`, `MCP_SERVER_MIGRATION_GUIDE.md`, `SECRETS_MIGRATION_GUIDE.md`.

---

### 4.7 H9 — `docs/testing/` (split)

| Field | Value |
|---|---|
| **Source path** | `docs/testing/` |
| **Scale** | 23 markdown |
| **Date / baseline** | Coverage initiative **2026-02-02**; Path C session reports |
| **Current authority** | **Mixed** |
| **Replacement / link** | KDOC-039 testing guide; `pytest.ini` + workflows |
| **Move risk** | **Medium** (campaigns); **None** for retained process docs until replacement lands |
| **Batch owner** | **BATCH-HIST-TEST** |
| **Disposition** | **Split** |

| Subset | Paths (representative) | Disposition |
|---|---|---|
| **Campaign / Historical** | `100_PERCENT_COVERAGE_INITIATIVE.md`, `FINAL_100_PERCENT_COVERAGE_STATUS.md`, `ROADMAP_TO_100_PERCENT_COVERAGE.md`, `PATH_C_*`, `COVERAGE_*`, `TEST_COVERAGE_*`, `TESTING_PROJECT_COMPLETE_SUMMARY.md`, `TEST_MIGRATION_*`, `TEST_STABILIZATION_SUMMARY.md`, backend testing project summaries/reviews | **Archive** |
| **Retain-candidate process** | `TEST_HEALTH_MATRIX.md`, `ARCHIVED_TESTS_CLEANUP_ANALYSIS.md`, `TEST_ARCHITECTURE_COMPATIBILITY_REVIEW.md` | **Retain** until absorbed by KDOC-039; then re-evaluate |

---

### 4.8 H10 — `docs/test_reports/`

| Field | Value |
|---|---|
| **Source path** | `docs/test_reports/` |
| **Scale** | 4 markdown |
| **Date / baseline** | Dated result dumps (CLI VFS, cluster, MCP) |
| **Current authority** | **Historical** |
| **Replacement / link** | Live CI / focused pytest |
| **Move risk** | **Low** |
| **Batch owner** | **BATCH-HIST-TESTREP** |
| **Disposition** | **Retain-historical** or soft **Archive** under ARCHIVE/test-reports |

---

### 4.9 H11 — `docs/ARCHIVE/` (already quarantined)

| Field | Value |
|---|---|
| **Source path** | `docs/ARCHIVE/` (`fixes/`, `implementation-summaries/`, `status-reports/`, `summaries/`, `test-reports/`) |
| **Scale** | 21 markdown |
| **Date / baseline** | Mixed; e.g. `status-reports/MCP_DEVELOPMENT_STATUS.md` **2025-07-10**; tree organization **2026-02** (`d4d8a0c9` era per KDOC-003) |
| **Current authority** | **Historical** — already non-canonical location |
| **Replacement / link** | KDOC-042 `docs/ARCHIVE/README.md` (“not current”); never primary nav |
| **Move risk** | **Low** (already moved) |
| **Batch owner** | **BATCH-HIST-ARCHIVE** |
| **Disposition** | **Retain-historical**; expand only via KDOC-045 curated intake |

---

### 4.10 H12 — `docs/ci-cd/` (split)

| Field | Value |
|---|---|
| **Source path** | `docs/ci-cd/` |
| **Scale** | 14 markdown (+ platform subdirs) |
| **Date / baseline** | Runner/workflow campaign era |
| **Current authority** | **Mixed** |
| **Replacement / link** | `.github/workflows/*` as automation truth; retain verified runbooks |
| **Move risk** | **Medium** for reports; **None** for active runbooks until verified |
| **Batch owner** | **BATCH-HIST-CICD** |
| **Disposition** | **Split** |

| Subset | Paths (representative) | Disposition |
|---|---|---|
| **Report / Historical** | `CI_CD_VERIFICATION_REPORT.md`, `GITHUB_RUNNERS_STATUS_REPORT.md`, `GITHUB_RUNNER_SETUP_COMPLETE.md`, `WORKFLOW_FIXES_SUMMARY.md`, `WORKFLOW_STATUS_REPORT.md`, `WORKFLOW_TEST_FIXES.md`, `amd64/AMD64_WORKFLOW_IMPLEMENTATION_SUMMARY.md` | **Archive** |
| **Runbook candidates** | `CI_CD_VALIDATION_GUIDE.md`, `RUNNER_QUICK_START.md`, `RUNNER_SCRIPTS_GUIDE.md`, `SETUP_RUNNER_NOW.md`, `START_RUNNER_HERE.md` | **Retain-canonical after verification** (ops owners; not historical bulk) |

---

### 4.11 H13 — `docs/features/` report-like children (split)

| Field | Value |
|---|---|
| **Source path** | Report-like files under `docs/features/` (family otherwise candidate-canonical) |
| **Date / baseline** | e.g. `STORAGE_FEATURES_DOCUMENTATION_COMPLETE.md` **2026-02-02** |
| **Current authority** | **Mixed** — guides may be canonical candidates; completion wrappers are Historical |
| **Replacement / link** | Same-directory feature guides after owner refresh; storage architecture KDOC-012 |
| **Move risk** | **Medium** |
| **Batch owner** | **BATCH-HIST-FEAT** |
| **Disposition** | **Split** / **Archive** reports only |

| Historical report paths | Disposition |
|---|---|
| `docs/features/STORAGE_FEATURES_DOCUMENTATION_COMPLETE.md` | **Archive** / Drop-from-navigation |
| `docs/features/BUCKET_SYSTEM_REVIEW_SUMMARY.md` | **Archive** |
| `docs/features/auto-healing/AUTO_HEALING_IMPLEMENTATION_SUMMARY.md` | **Archive** (merge with ARCHIVE auto-healing summary if duplicate — KDOC-041) |
| `docs/features/copilot/COPILOT_AUTO_HEALING_IMPLEMENTATION_SUMMARY.md` | **Archive** / **Merge** with auto-healing set |

---

### 4.12 H14 — Architecture pre-program audits (split; low move urgency)

Wave 0 and new architecture guides are **not** historical bulk. Only older audit/summary-style files are registered for supersession.

| Field | Value |
|---|---|
| **Source path** | Selected files under `docs/architecture/` |
| **Date / baseline** | Pre-MCP++ / pre-Iroh / pre-program; coexists with 2026-08-03 Wave 0 evidence |
| **Current authority** | **Mixed** — audits = Historical/evidence inputs; Wave 0 maps + new guides = Canonical/program evidence |
| **Replacement / link** | See table below |
| **Move risk** | **None (do not move yet)** — wait until KDOC-010..019 stable; then optional archive |
| **Batch owner** | **BATCH-HIST-ARCH** |
| **Disposition** | **Supersede** (content) first; physical Archive optional |

| Historical / audit-style path | Superseding / current authority link |
|---|---|
| `ARCHITECTURE_MODULE_ORGANIZATION.md` | `SYSTEM_OVERVIEW.md`, `RUNTIME_AND_ENTRYPOINTS.md`, `COMPATIBILITY_LAYERS.md` |
| `BACKEND_ARCHITECTURE_VISUAL_SUMMARY.md` | Storage backend architecture guide (KDOC-012) + `docs/iroh/*` |
| `CLI_MCP_ARCHITECTURE_AUDIT.md` | `RUNTIME_AND_ENTRYPOINTS.md`, MCP control-plane docs, KDOC-032 CLI docs |
| `FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md` | KDOC-012 / KDOC-015 content-metadata-VFS |
| `MCP_CONTROLLER_CONSOLIDATION.md`, `MCP_INTEGRATION_ARCHITECTURE.md` | `MCP_CONTROL_PLANE.md` (KDOC-014) |
| `REFACTORED_ARCHITECTURE_README.md` | `SYSTEM_OVERVIEW.md` + navigation (KDOC-060) |

**Not historical (do not disposition as archive bulk):**

| Path | Why excluded |
|---|---|
| `SOURCE_OF_TRUTH_MAP.md`, `GLOSSARY.md` | Wave 0 evidence / vocabulary (KDOC-004/006) |
| `SYSTEM_OVERVIEW.md`, `RUNTIME_AND_ENTRYPOINTS.md`, `COMPATIBILITY_LAYERS.md`, `CLUSTER_COORDINATION.md`, `CONTENT_METADATA_VFS.md`, `MCP_CONTROL_PLANE.md`, `NETWORK_TRANSPORTS.md` | Target/current architecture guides |
| `ipfs_kit_documentation.objectives.md`, `ipfs_kit_documentation.todo.md` | **Program-control** (protected) |
| `decisions/*` | ADR track (separate) |

---

### 4.13 H15 — Navigation surfaces that promote history

| Field | Value |
|---|---|
| **Source path** | `docs/index.md`, `docs/README.md`, `docs/DOCUMENTATION_INDEX.md` (and historically dense `docs/guides/DOCUMENTATION_GUIDE.md` nav inheritance — guide body is now lifecycle standard per KDOC-005) |
| **Date / baseline** | July 2026 DOC-KIT reachability campaign (F-011/F-012) |
| **Current authority** | **Mixed / competing** — not “historical documents” themselves |
| **Replacement / link** | KDOC-060 exclusive navigation; historical targets listed in H1–H14 must be unlinked from “start here” paths |
| **Move risk** | **Critical** for wrong rewrites; **do not archive indexes** in history batches |
| **Batch owner** | KDOC-060 (nav) with **BATCH-HIST-ROOT** supplying unlink lists |
| **Disposition** | **Drop-from-navigation** for historical *targets*; indexes remain until exclusive-nav task |

---

## 5. Execution order (no moves in this task)

Recommended order for downstream consumers (paper plan only):

1. **KDOC-041** — Resolve duplicates (migration echoes, auto-healing summaries, MCP refactoring double reports, coverage roadmap pile).
2. **KDOC-042** — Publish `docs/ARCHIVE/README.md` with “not current” boundary language.
3. **KDOC-030..039** — Ensure replacements exist for any present-tense content still only in reports (testing guide especially).
4. **KDOC-045** — Physical curation: `ARCHIVE/implementation/`, `ARCHIVE/status-and-fixes/`, intake from H1, H5, H6, H9 campaigns, H12 reports, H13 reports.
5. **KDOC-060** — Strip historical targets from exclusive navigation (H15 + all Drop-from-navigation rows).
6. **Optional** — Banner historical files left in place (migration, project) with lifecycle labels from KDOC-005 (not this task).

**Hard constraints**

- No destructive move precedes a replacement/current guide (KDOC-041 acceptance).
- Generated (`api_generated/`) and External (`py-ipld-*`, empty gitlinks) are **out of scope** here (KDOC-043/044/046).
- Protected program files are never historical bulk and never edited by workers.

---

## 6. Out-of-scope families (explicit non-register)

Listed so agents do not over-archive:

| Family | Why out of scope for historical bulk moves |
|---|---|
| `docs/api/`, `docs/guides/`, `docs/operations/`, `docs/deployment/`, `docs/development/`, `docs/reference/`, `docs/iroh/`, `docs/workflows/` | Candidate-canonical; refresh in place under KDOC-030..039 |
| `docs/api_generated/` | **Generated** — KDOC-046 contract |
| Empty external gitlinks + `docs/py-ipld-*` | **External** — KDOC-044 |
| `docs/audits/` | Wave 0 **Canonical** program evidence (this file included) |
| `docs/documentation_plan.md` + architecture objectives/todo | **Program-control** protected |
| Integration/feature **guides** that are not `*COMPLETE*`/`*SUMMARY*` reports | Verify then retain; only report wrappers enter H13 |

---

## 7. Reproducible evidence commands

```bash
# Baseline
git rev-parse HEAD

# Historical bulk scales (align with KDOC-001)
for d in docs/implementation docs/status_reports docs/fixes docs/project \
         docs/migration docs/test_reports docs/ARCHIVE docs/testing docs/ci-cd; do
  printf '%s\tfiles=%s\tmd=%s\n' "$d" \
    "$(find "$d" -type f | wc -l)" \
    "$(find "$d" -type f -name '*.md' | wc -l)"
done

# Root report-like cluster
find docs -maxdepth 1 -type f -name '*.md' \
  | rg -i 'PHASE|TEST_COVERAGE|COMPLETE_|FINAL_|ROADMAP|PATH_TO|100_PERCENT|ANYIO|MIGRATION' \
  | sort

# COMPLETE/SUMMARY density (F-011 class)
find docs \( -name '*COMPLETE*' -o -name '*SUMMARY*' \) | wc -l

# Feature report wrappers
find docs/features -type f -name '*.md' | rg -i 'COMPLETE|SUMMARY|STATUS|REVIEW' | sort

# Already quarantined
find docs/ARCHIVE -type f | sort

# Validation for this task
test -s docs/audits/HISTORICAL_DOCUMENT_REGISTER.md \
  && rg -q "Disposition" docs/audits/HISTORICAL_DOCUMENT_REGISTER.md
```

---

## 8. Acceptance self-check (KDOC-040)

| Acceptance criterion | Status |
|---|---|
| Output path `docs/audits/HISTORICAL_DOCUMENT_REGISTER.md` | This file |
| Register includes **source path** for every high-risk family | Yes — §3 H1–H15 + §4 |
| Register includes **date/baseline if known** | Yes — per-row and family detail |
| Register includes **current authority** | Yes |
| Register includes **replacement/link** | Yes |
| Register includes **move risk** | Yes — vocabulary §1.1 + matrix |
| Register includes **batch owner** for every high-risk family | Yes — §1.2 + matrix |
| Disposition rules for retain/archive/supersede/merge/drop-from-navigation | Yes — §1 and §2 |
| No file moves or mass banners in this task | Yes — conflict policy honored |
| Validation string `Disposition` present | Yes |
| Depends on KDOC-001, KDOC-003, KDOC-005 consumed | Yes — inventory, freshness F-011/F-014, lifecycle Historical class |

**Validation commands:**

```bash
test -s docs/audits/HISTORICAL_DOCUMENT_REGISTER.md && rg -q "Disposition" docs/audits/HISTORICAL_DOCUMENT_REGISTER.md
```

---

## 9. Relationship to sibling artifacts

| Artifact | Role relative to this register |
|---|---|
| `docs/audits/DOCUMENTATION_INVENTORY.md` | Family authority/freshness/disposition proposals; this register **deepens** historical rows with move risk, batch owners, and replacement links |
| `docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md` | Evidence that completion reports and indexes mislead (F-011, F-012, F-014); remediation map points here |
| `docs/guides/DOCUMENTATION_GUIDE.md` | Historical class may **not** recommend as current; Canonical←Historical promotion rules |
| `docs/architecture/SOURCE_OF_TRUTH_MAP.md` | Compatibility/historical **code** paths; this register covers **documentation** history bulk |
| Future `docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md` | KDOC-041 — executes paper reconciliation using H* rows |
| Future `docs/ARCHIVE/README.md` | KDOC-042 — human-facing boundary for H11 + intake from Archive dispositions |

---

*End of KDOC-040 historical-document register. No files were moved. Downstream history tasks must treat dispositions as scheduled work, not completed filesystem state.*
