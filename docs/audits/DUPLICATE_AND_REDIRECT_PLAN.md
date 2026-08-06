# Duplicate and Redirect Plan

| Field | Value |
|---|---|
| **Task** | KDOC-041 — Reconcile duplicate and competing documents on paper |
| **Goal** | KDOC-G050 |
| **Track** | information-architecture |
| **Plan date** | 2026-08-04 |
| **Tree baseline** | Git commit `45be864b7e58effa71bb1c9e76ef51b5368349b7` (implementation worktree) |
| **Inventory baseline** | KDOC-001 — `docs/audits/DOCUMENTATION_INVENTORY.md` |
| **Freshness baseline** | KDOC-003 — `docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md` (F-003, F-011, F-012, F-014) |
| **Historical register** | KDOC-040 — `docs/audits/HISTORICAL_DOCUMENT_REGISTER.md` (H1–H15) |
| **Lifecycle contract** | KDOC-005 — `docs/guides/DOCUMENTATION_GUIDE.md` (Historical must not recommend as current) |
| **Scope** | Competing and near-duplicate documentation under `docs/` identified by KDOC-040 preconditions and corpus evidence |
| **Non-goals** | File moves, renames, banners, navigation rewrites, ARCHIVE intake, generated/external contracts |
| **Conflict policy** | **Plan only.** No renames or shared navigation edits (KDOC-042/045/060 consume this plan). |

This plan is the **paper authority** for selecting canonical survivors, archive targets, redirect/link strategy, inbound-link impact, and safe execution order among duplicate and competing document sets. It does **not** move files.

**Consumers**

| Downstream task | Use of this plan |
|---|---|
| **KDOC-042** | Archive boundary language; what “not current” means for redirected targets |
| **KDOC-045** | Physical ARCHIVE intake order using reviewed dispositions and redirect readiness |
| **KDOC-060** | Exclusive navigation targets; which paths drop from landing maps |
| **KDOC-030..039** | Replacement guides that must exist (or be labeled pending) before destructive moves |
| **KDOC-014 / ADR-0003** | MCP runtime authority supersession of migration-guide claims (F-003) |

---

## 1. Disposition and redirect vocabulary

### 1.1 Per-path disposition (extends KDOC-040)

| Disposition | Intent in this plan |
|---|---|
| **Canonical-survivor** | Preferred current (or candidate-current) path for the topic; keep in place and refresh under owner tasks |
| **Historical-survivor** | Preferred provenance artifact among duplicates; keep labeled Historical; others archive or redirect to it |
| **Archive-after-redirect** | Scheduled for `docs/ARCHIVE/…` only after redirect stub/banner or index unlink is ready |
| **Redirect-stub** | After move (or in-place supersession), leave a short markdown stub at the old path pointing to the survivor |
| **Drop-from-navigation** | Remove from landing indexes and agent start paths without requiring an immediate filesystem move |
| **Supersede** | Content authority moves to a named current guide; historical file must not remain linked as operator truth |
| **Merge-then-archive** | Fold unique facts into survivor (if any), then archive non-survivors |
| **Retain-split** | Directory is Mixed: named children are historical; others remain candidate-canonical |
| **No-move-yet** | Competing but replacement guide not stable; **do not** physically relocate until listed gate passes |

### 1.2 Redirect strategy types

| Redirect type | Mechanism | When to use |
|---|---|---|
| **Nav-unlink** | Remove links from `docs/index.md`, `docs/README.md`, `docs/DOCUMENTATION_INDEX.md`, `docs/QUICK_REFERENCE.md` | Always first for historical targets (KDOC-060) |
| **In-place banner** | Historical class banner + pointer to canonical path (lifecycle KDOC-005) | Survivors left at stable paths (`migration/`, some `project/`) |
| **Stub Redirect** | Replace body with 10–30 line stub: title, status Historical, link to survivor, optional ARCHIVE path | After physical move, or for exact path duplicates where one copy remains |
| **Merge Redirect** | Stub points to survivor; unique paragraphs captured in survivor or ARCHIVE note first | Near-duplicates with non-empty diff |
| **Index Redirect role** | Path keeps a permanent navigation role that is *not* a second full map (KDOC-060) | Competing indexes themselves |

> **Rule (acceptance):** No destructive move precedes a replacement/current guide. “Archive-after-redirect” is blocked until the **Replacement gate** for that set is **Open**.

### 1.3 Replacement gate states

| Gate | Meaning | May move files? |
|---|---|---|
| **Open** | Named canonical (or labeled historical survivor) already exists and is path-stable | Yes, under KDOC-045 with redirects |
| **Pending-task** | Named KDOC task will produce the replacement; until then Drop-from-navigation only | **No** |
| **Nav-only** | Competition is among indexes; exclusive-nav task rewrites roles without archiving the index files | N/A (do not archive indexes) |
| **Authority-ADR** | Content authority blocked on maintainer/ADR decision; paper plan records interim ranking | **No** physical move of disputed “current” claims |

### 1.4 Move-risk (same scale as KDOC-040)

| Move risk | Meaning |
|---|---|
| **Critical** | High inbound link density from primary indexes; wrong move breaks agent workflows |
| **High** | Many cross-links; needs Stub Redirect plan before mass move |
| **Medium** | Moderate links; batch-move after ARCHIVE README (KDOC-042) |
| **Low** | Already quarantined or sparse discovery |
| **None** | Do not move until replacement gate opens |

---

## 2. Hard ordering constraints

These constraints implement the acceptance criterion *“no destructive move precedes a replacement/current guide.”*

1. **Paper first (this task):** every duplicate set has evidence, survivor, non-survivors, redirect type, inbound impact, gate, and batch owner.
2. **Boundary README next (KDOC-042):** `docs/ARCHIVE/README.md` states material is **not current** before new bulk intake.
3. **Nav-unlink before or with ARCHIVE intake (KDOC-060 coordination):** historical targets lose “start here” links before or as paths move.
4. **Replacement guides before bulk archive of present-tense content:** especially testing (KDOC-039), MCP control plane (KDOC-014), async architecture (KDOC-016).
5. **Physical moves last (KDOC-045):** only sets with gate **Open**, redirects planned, and ARCHIVE boundary present.
6. **Never archive competing indexes** as historical bulk; re-role them under KDOC-060 (DS-01).
7. **Never invent a fake canonical path** when no replacement exists — use **Pending-task** + Drop-from-navigation.

**Forbidden sequences**

| Forbidden | Why |
|---|---|
| `mv docs/implementation/* → ARCHIVE/` before architecture guides stable for linked topics | Breaks agents that treat COMPLETE reports as API proof (F-011) |
| Delete root MCP migration guide before packaging + MCP_CONTROL_PLANE are the sole linked authority | Leaves F-003 false “canonical runtime” as only survivor if wrong copy kept |
| Collapse indexes by deleting `DOCUMENTATION_INDEX.md` without Redirect role | Critical link graph (F-012) |
| Move `docs/testing/TEST_HEALTH_MATRIX.md` with coverage campaigns | Split family — process retain vs campaign archive |

---

## 3. Master matrix — every duplicate set

Every **duplicate set (DS)** below has: members, evidence, survivor(s), disposition, redirect strategy, inbound impact, replacement gate, move risk, batch owner, and execution phase.

| ID | Duplicate set (topic) | Members (count) | Survivor | Non-survivors disposition | Redirect strategy | Gate | Move risk | Batch / owner | Phase |
|---|---|---|---|---|---|---|---|---|---|
| **DS-01** | Competing root indexes | 4 | Role split under KDOC-060 | None archived as bulk | Index Redirect role + Nav-unlink of historical *targets* | **Nav-only** | **Critical** | KDOC-060 + BATCH-HIST-ROOT | P0 |
| **DS-02** | AnyIO migration multi-path | 7+ | `docs/migration/ANYIO_MIGRATION_COMPLETE.md` (historical survivor) | Root echoes → Archive-after-redirect; batch summaries stay labeled | Merge Redirect + in-place banner | **Open** (historical) / async guide **Pending** for present-tense | **High** | BATCH-HIST-MIG | P1 |
| **DS-03** | MCP migration dual + false runtime | 2 + status echoes | Packaging + `docs/architecture/MCP_CONTROL_PLANE.md` (canonical authority) | Both migration guides → Historical; prefer migration/ tree | Supersede + Stub Redirect; **do not** promote either as production runtime | **Authority-ADR** / KDOC-014 **Open** for control-plane | **High** | BATCH-HIST-MIG + KDOC-014 | P1 |
| **DS-04** | Coverage / 100% campaign pile | 20+ | None as coverage %; process → KDOC-039 testing guide | All campaign reports → Archive-after-redirect | Nav-unlink + Stub Redirect optional | **Pending-task** KDOC-039 then **Open** for archive | **Critical** (index-linked) | BATCH-HIST-TEST / ROOT | P1–P2 |
| **DS-05** | Auto-healing multi-home reports | 10+ | Guides: `docs/features/auto-healing/AUTO_HEALING.md` + workflows; **one** quick-start | Summaries → Archive; ARCHIVE copy already quarantined | Merge Redirect into ARCHIVE/implementation-summaries | **Open** for reports; guides **No-move-yet** | **Medium** | BATCH-HIST-FEAT | P2 |
| **DS-06** | MCP refactoring dual status reports | 2 | Neither current; optional merge into one ARCHIVE note | Both → Archive-after-redirect | Stub Redirect → MCP_CONTROL_PLANE + ARCHIVE | **Open** (historical) | **Medium** | BATCH-HIST-STATUS | P2 |
| **DS-07** | Refactoring-complete duals (project/status/ARCHIVE) | 4+ | `docs/project/` Feb set as historical survivor for tree overhaul episode | status_reports + ARCHIVE summaries as provenance only | Drop-from-navigation; optional Merge | **Open** (historical) | **Medium** | BATCH-HIST-PROJECT / STATUS | P2 |
| **DS-08** | libp2p path competition | 4 + empty gitlinks | `docs/integration/libp2p_integration.md` (candidate guide) | README under `libp2p_integration/` merge or redirect; COMPLETE archive; plan → Proposed | Stub Redirect; external gitlinks out of scope (KDOC-044) | **Pending** network docs refresh | **High** (name collision) | BATCH-HIST-FEAT + integration owner | P1 |
| **DS-09** | Observability / monitoring multi-home | 6+ | Split by scope (not one file) | Implementation summary → Archive; do not collapse iroh vs ops | Cross-link table; no mass merge | **Open** for summary archive; guides **Retain-split** | **Medium** | Ops / Iroh owners | P2 |
| **DS-10** | WAL telemetry dual | 2+ | `docs/reference/wal_telemetry_*.md` family | Root `telemetry_api.md` → Redirect-stub or merge into reference | Stub Redirect | **Open** after reference verified | **Medium** | Reference owner | P2 |
| **DS-11** | IPFS datasets dual guides | 2 | Prefer comprehensive after verify **or** merge unique sections | Non-survivor → Redirect-stub | Merge Redirect | **Pending** integration refresh (KDOC-038-class) | **Medium** | Integration owner | P2 |
| **DS-12** | Implementation COMPLETE bulk vs architecture | 73 md | Architecture + subsystem guides (KDOC-010..019 / features) | Entire `docs/implementation/` completion bulk → Archive | Nav-unlink first; directory-level Redirect note in ARCHIVE README | **Pending** until topic guides cover linked claims; interim Drop-from-nav | **High** | BATCH-HIST-IMPL | P2–P3 |
| **DS-13** | Architecture pre-program audits vs Wave 0 guides | 6 audits | Wave 0 + new guides listed in H14 | Audits → Supersede; optional later Archive | In-place banner; **No-move-yet** | **No-move-yet** until KDOC-010..019 stable | **None** | BATCH-HIST-ARCH | P3 |
| **DS-14** | CLI/MCP integration dual | 2 | Neither sole authority; point to packaging + MCP_CONTROL_PLANE + CLI docs | Plan/summary → Historical | Supersede + Drop-from-navigation | **Pending** KDOC-032 / KDOC-014 | **Medium** | Integration + MCP | P2 |
| **DS-15** | Root PR / phase final reports | 5+ | None as current status | Archive-after-redirect | Nav-unlink | **Open** (historical) | **Critical** if index-linked | BATCH-HIST-ROOT | P1 |
| **DS-16** | Project overhaul vs live audits | 7 project md | Live: `docs/audits/*` + protected plan | Project completion language → Historical only (F-015) | Drop-from-navigation; retain-in-place labeled optional | **Open** | **Medium** | BATCH-HIST-PROJECT | P2 |
| **DS-17** | CI-CD report vs runbook near-duplicates | 14 family | Runbooks after verify; reports archive | Report subset → Archive | Split (H12); no Redirect among runbooks until deduped titles | **Open** for reports | **Medium** | BATCH-HIST-CICD | P2 |
| **DS-18** | Auto-healing QUICK_START vs QUICKSTART | 2 | `AUTO_HEALING_QUICK_START.md` (longer; 211 lines) | `AUTO_HEALING_QUICKSTART.md` → Merge Redirect or stub | Stub Redirect (filename collision) | **Open** after content merge check | **Medium** | BATCH-HIST-FEAT | P1 |
| **DS-19** | Root feature roadmaps | 2 | None as implemented | Drop-from-navigation; label Proposed or archive | Nav-unlink | **Open** | **Medium** | BATCH-HIST-ROOT | P1 |
| **DS-20** | Status reports vs ARCHIVE status | 18 + ARCHIVE | Family-level Archive intake | All status_reports → Archive-after-redirect | Directory Redirect via ARCHIVE README | **Open** after KDOC-042 | **Medium** | BATCH-HIST-STATUS | P2 |
| **DS-21** | Fixes tree vs ARCHIVE/fixes | 14 + ARCHIVE | ARCHIVE intake | All fixes → Archive-after-redirect | Low Stub need | **Open** after KDOC-042 | **Medium** | BATCH-HIST-FIX | P2 |
| **DS-22** | Integration hub trio | 3 | Complementary roles after refresh | Not full duplicates | Cross-link only; no archive of hub set | **Pending** KDOC integration refresh | **None** | Integration owner | P3 |
| **DS-23** | Deployment auto-healing triple summaries | 3 | None as runbook; feature guides own how-to | All three → Archive-after-redirect | Merge Redirect into ARCHIVE auto-healing set | **Open** | **Medium** | BATCH-HIST-FEAT | P2 |

**Acceptance field check:** every DS-01–DS-23 row includes disposition, redirect strategy, gate, and move risk. Detail sections below supply evidence commands and inbound impact.

---

## 4. Duplicate set detail (evidence-based)

### 4.1 DS-01 — Competing root indexes

| Field | Value |
|---|---|
| **Members** | `docs/index.md` (234 lines), `docs/README.md` (728), `docs/DOCUMENTATION_INDEX.md` (348), `docs/QUICK_REFERENCE.md` (347) |
| **Evidence** | Combined ~1,657 lines; freshness F-012; inventory §4.1 Critical; not identical content (e.g. F-001 cluster path defect present in `index.md` but not installation guide) |
| **Competition type** | Overlapping “start here” maps with inconsistent authority and stale deep links to COMPLETE reports (F-011) |
| **Canonical roles (planned KDOC-060)** | `index.md` = sole concise current landing; `README.md` = complete repository map; `DOCUMENTATION_INDEX.md` = structured catalog **or** Redirect role; `QUICK_REFERENCE.md` = cheatsheet, not second full index |
| **Disposition** | **Index Redirect role** for non-landing maps; **Drop-from-navigation** for historical *targets* they promote — **do not Archive indexes** |
| **Redirect strategy** | Nav-unlink historical targets first; then exclusive-nav rewrite (not a filesystem redirect of the index files themselves) |
| **Inbound impact** | Critical — `DOCUMENTATION_INDEX` ~9 md referrers; `QUICK_REFERENCE` ~22; README/index dense cross-links |
| **Replacement gate** | **Nav-only** (KDOC-060) |
| **Move risk** | **Critical** for wrong rewrites; **None** for archiving indexes (forbidden) |
| **Batch owner** | KDOC-060 + BATCH-HIST-ROOT (unlink lists from H1–H14) |

**Execution rule:** Treat DS-01 as a **navigation defect**, not a historical bulk family. Unlink lists come from this plan’s non-survivor tables and KDOC-040 H1–H15.

---

### 4.2 DS-02 — AnyIO migration multi-path

| Field | Value |
|---|---|
| **Members** | Root: `docs/ANYIO_MIGRATION.md`, `docs/COMPLETE_ANYIO_MIGRATION_SUMMARY.md`. Tree: `docs/migration/ANYIO_MIGRATION_COMPLETE.md` (dated **2026-01-24**), `ANYIO_MIGRATION_STATUS.md`, `ANYIO_MIGRATION_TEST_RESULTS.md`, `ANYIO_MIGRATION_BATCH6_SUMMARY.md`, `ANYIO_MIGRATION_BATCH7_SUMMARY.md`, `ANYIO_MIGRATION_BATCH8_9_SUMMARY.md` |
| **Evidence** | Same episode (asyncio→anyio) told at root and under `migration/`; COMPLETE claims “160 passing tests / 100% success”; register H3/H8 |
| **Historical-survivor** | `docs/migration/ANYIO_MIGRATION_COMPLETE.md` (dated completion anchor) + batch files as provenance |
| **Non-survivors** | Root `ANYIO_MIGRATION.md`, `COMPLETE_ANYIO_MIGRATION_SUMMARY.md` → **Archive-after-redirect** (or Merge into migration/ then archive root) |
| **Current how-to authority** | **Not** these files — `docs/development/async_architecture.md` / KDOC-016 after fix (present-tense) |
| **Redirect strategy** | Root paths: **Stub Redirect** → `docs/migration/ANYIO_MIGRATION_COMPLETE.md` + note “Historical; async how-to → async_architecture”. Migration tree: **in-place banner** Historical |
| **Inbound impact** | ~11 md files mention `ANYIO_MIGRATION`; root COMPLETE links to root guide and `index.md` |
| **Replacement gate** | Historical merge **Open**; present-tense async guide **Pending-task** (KDOC-016) — **do not** delete migration history before banner |
| **Move risk** | **High** |
| **Batch owner** | BATCH-HIST-MIG / BATCH-HIST-ROOT |
| **Phase** | P1 paper + banners; physical root archive only after Stub Redirect ready (KDOC-045) |

---

### 4.3 DS-03 — MCP migration dual paths and false “canonical runtime”

| Field | Value |
|---|---|
| **Members** | `docs/MCP_SERVER_MIGRATION_GUIDE.md` (45 lines; **Status: Active**; claims `Canonical Runtime: ipfs_kit_py.mcp.servers.unified_mcp_server`), `docs/migration/MCP_SERVER_MIGRATION_GUIDE.md` (354 lines; consolidation narrative). Related historical: status MCP refactoring (DS-06), ARCHIVE `MCP_DEVELOPMENT_STATUS.md` |
| **Evidence** | Files **differ** (md5 `85ea739e…` vs `fec00f45…`). Freshness **F-003**: packaging console script is `ipfs-kit-mcp = ipfs_kit_py.mcp_server.server:main`, not the migration guide’s unified server family. ADR-0003 / `MCP_CONTROL_PLANE.md` own authority mapping |
| **Canonical authority (current)** | Packaging entry + `docs/architecture/MCP_CONTROL_PLANE.md` (+ ADR-0003). **Neither** migration guide is production runtime truth |
| **Historical-survivor** | Prefer longer `docs/migration/MCP_SERVER_MIGRATION_GUIDE.md` as **migration episode provenance only**, after stripping or banner-disclaiming “canonical runtime” present-tense claims |
| **Non-survivors** | Root short guide → **Stub Redirect** to migration/ copy **or** directly to MCP_CONTROL_PLANE with “historical migration notes” link |
| **Disposition** | **Supersede** (authority) + **Merge-then-archive** root echo + **Retain-in-place (labeled)** for migration/ survivor until KDOC-045 |
| **Redirect strategy** | Root: Stub Redirect. Body of either guide must not remain linked as “Active / Canonical Runtime” from indexes (Nav-unlink + banner) |
| **Inbound impact** | ~11 md referrers for `MCP_SERVER_MIGRATION_GUIDE`; indexes may promote root path |
| **Replacement gate** | Control-plane guide **Open** for authority supersession; physical archive of guides **Pending** until banners applied and indexes unlinked |
| **Move risk** | **High** |
| **Batch owner** | BATCH-HIST-MIG + KDOC-014 |
| **Hard constraint** | Do **not** destroy root guide while it is still the only linked MCP narrative unless Stub Redirect already points at packaging-aligned authority |

---

### 4.4 DS-04 — Coverage / 100% campaign pile

| Field | Value |
|---|---|
| **Root members** | `100_PERCENT_COVERAGE_ROADMAP.md`, `PATH_TO_100_PERCENT_COVERAGE.md`, `TEST_COVERAGE_EXTENSION.md`, `TEST_COVERAGE_FINAL.md`, `TEST_COVERAGE_IMPROVEMENTS.md`, `TEST_COVERAGE_PHASE3.md`, `FINAL_TEST_COVERAGE_REPORT.md`, `PHASE5_FINAL_REPORT.md`, `PHASE6_COMPLETE_COVERAGE_REPORT.md`, `PHASE6_FINAL_SUMMARY.md`, `PHASE6_TESTING_GUIDE.md` |
| **testing/ members** | `100_PERCENT_COVERAGE_INITIATIVE.md`, `ROADMAP_TO_100_PERCENT_COVERAGE.md`, `FINAL_100_PERCENT_COVERAGE_STATUS.md` (**2026-02-02**), `COVERAGE_*`, `TEST_COVERAGE_*`, `PATH_C_*`, plus related campaign summaries |
| **Evidence** | F-014 conflicting coverage language; inventory Historical; register H2/H9 Split |
| **Survivor (process)** | `docs/development/testing_guide.md` (KDOC-039) + `docs/testing/TEST_HEALTH_MATRIX.md` (retain until absorbed) |
| **Survivor (coverage %)** | **None** — live CI / pytest are evidence, not markdown banners |
| **Non-survivors** | All campaign files above → **Archive-after-redirect** under future `docs/ARCHIVE/` testing-campaigns (KDOC-045) |
| **Retain-split (do not archive with campaigns)** | `TEST_HEALTH_MATRIX.md`, process notes feeding KDOC-039 (register H9) |
| **Redirect strategy** | Nav-unlink all campaign paths from indexes; optional Stub Redirect from highest-linked root files → testing_guide |
| **Inbound impact** | `100_PERCENT` ~10 referrers; Critical if primary indexes deep-link |
| **Replacement gate** | **Pending-task** KDOC-039 for process replacement; campaign archive gate **Open** only for pure result dumps after Nav-unlink |
| **Move risk** | **Critical** (index-linked root set) |
| **Batch owner** | BATCH-HIST-TEST + BATCH-HIST-ROOT |
| **Phase** | P1 Nav-unlink; P2 archive campaigns; never move health matrix with them |

---

### 4.5 DS-05 / DS-18 / DS-23 — Auto-healing multi-home (guides vs summaries)

| Field | Value |
|---|---|
| **Guide candidates (retain)** | `docs/features/auto-healing/AUTO_HEALING.md`, `AUTO_HEALING_WORKFLOWS.md`, `AUTO_HEALING_EXAMPLES.md`, `MCP_AUTO_HEALING.md`, copilot setup/guide/quick-ref under `features/copilot/` |
| **Quick-start collision (DS-18)** | `AUTO_HEALING_QUICK_START.md` (211 lines) vs `AUTO_HEALING_QUICKSTART.md` (103 lines) — **differ**; survivor = **QUICK_START** (longer); non-survivor → Stub Redirect after merge of unique steps |
| **Report / summary duplicates** | `features/auto-healing/AUTO_HEALING_IMPLEMENTATION_SUMMARY.md` (420 lines), `ARCHIVE/implementation-summaries/AUTO_HEALING_IMPLEMENTATION_SUMMARY.md` (437 lines, **differ** md5), `features/copilot/COPILOT_AUTO_HEALING_IMPLEMENTATION_SUMMARY.md`, deployment triple (DS-23): `deployment/ci-cd/AUTO_HEALING_COMPLETE.md`, `COMPLETE_AUTO_HEALING_SUMMARY.md`, `FINAL_AUTO_HEALING_SUMMARY.md` |
| **Evidence** | Same product story across features, deployment/ci-cd, copilot, and ARCHIVE; COMPLETE/SUMMARY density corpus-wide **134** paths (F-011 class) |
| **Disposition** | **Retain-split** guides; **Archive-after-redirect** all implementation summaries; ARCHIVE copy already **Retain-historical** |
| **Redirect strategy** | Summaries → Stub or Nav-unlink to `AUTO_HEALING.md` + ARCHIVE survivor note; QUICKSTART → Redirect to QUICK_START |
| **Inbound impact** | `AUTO_HEALING` ~21 md referrers |
| **Replacement gate** | Guides **Open** as how-to survivors; report archive **Open** after KDOC-042 |
| **Move risk** | **Medium** |
| **Batch owner** | BATCH-HIST-FEAT |
| **Hard constraint** | Do not archive `AUTO_HEALING.md` / workflows with the summary pile |

---

### 4.6 DS-06 — MCP refactoring dual status reports

| Field | Value |
|---|---|
| **Members** | `docs/status_reports/MCP_REFACTORING_SUMMARY.md` (139 lines; root `mcp/` → `ipfs_kit_py/mcp/`), `docs/status_reports/MCP_SERVER_REFACTORING_SUMMARY.md` (210 lines; `mcp_server/` → `mcp/server/` narrative) |
| **Evidence** | Adjacent episode; different move stories; both present-tense “Successfully…”; packaging still exposes `mcp_server` entry (F-003 tension) |
| **Survivor** | Neither as current architecture; optional single ARCHIVE merge note under status-and-fixes |
| **Disposition** | **Merge-then-archive** both → `docs/ARCHIVE/status-and-fixes/` (KDOC-045) |
| **Redirect strategy** | Stub or directory-level note → `MCP_CONTROL_PLANE.md` + ADR-0003 |
| **Inbound impact** | Medium within status_reports / indexes |
| **Replacement gate** | **Open** (historical) once KDOC-042 exists |
| **Move risk** | **Medium** |
| **Batch owner** | BATCH-HIST-STATUS |

---

### 4.7 DS-07 — Refactoring-complete duals

| Field | Value |
|---|---|
| **Members** | `docs/project/REFACTORING_COMPLETE_SUMMARY.md` (**2026-02-02**, tree overhaul), `docs/status_reports/REFACTORING_COMPLETE_SUMMARY.md` (package consolidation, **differ**), `docs/project/COMPREHENSIVE_REFACTORING_COMPLETE.md` (632 lines, six-phase), `docs/ARCHIVE/summaries/REFACTORING_SUCCESS_SUMMARY.md`, phase files under `docs/implementation/phases/COMPREHENSIVE_REFACTORING_PHASE*.md` |
| **Evidence** | Same “refactoring complete” title family across three trees; project dated Feb 2026 overhaul; status_reports undated package move narrative |
| **Historical-survivor** | `docs/project/` Feb set for **documentation tree** episode; status_reports copy for **package layout** episode (different facts — do not force single merge without reading) |
| **Disposition** | **Drop-from-navigation** all; **Archive** status_reports + implementation phases with H1/H5; project retain-labeled or archive after KDOC-041 (register H7) |
| **Redirect strategy** | Nav-unlink; optional pointers to `docs/architecture/SYSTEM_OVERVIEW.md` + `COMPATIBILITY_LAYERS.md` |
| **Inbound impact** | `REFACTORING_COMPLETE` ~7 referrers |
| **Replacement gate** | **Open** for archive of status/impl; project path **Open** for Drop-from-nav |
| **Move risk** | **Medium** |
| **Batch owner** | BATCH-HIST-PROJECT / STATUS / IMPL |

---

### 4.8 DS-08 — libp2p path competition

| Field | Value |
|---|---|
| **Members** | `docs/integration/libp2p_integration.md` (707 lines), `docs/libp2p_integration/README.md` (289 lines), `docs/integration/LIBP2P_IMPLEMENTATION_PLAN.md` (864 lines, Proposed/plan), `docs/implementation/LIBP2P_INTEGRATION_COMPLETE.md` (114 lines, COMPLETE banner). Empty externals: `docs/libp2p_docs/`, `docs/libp2p-universal-connectivity/` (KDOC-044) |
| **Evidence** | Inventory §4.10 names collision; three authored narratives + completion report; external gitlinks empty |
| **Canonical-survivor (candidate)** | `docs/integration/libp2p_integration.md` after verification against source |
| **Non-survivors** | `libp2p_integration/README.md` → Merge unique content then **Stub Redirect** to integration path; COMPLETE → Archive; IMPLEMENTATION_PLAN → **Proposed** label, Drop-from-navigation as “done” |
| **Redirect strategy** | Directory README becomes Redirect stub; COMPLETE archived with H1 |
| **Inbound impact** | `libp2p_integration` ~10 referrers; name collision confuses agents |
| **Replacement gate** | **Pending** network/integration refresh before deleting README body; **No-move** of integration guide |
| **Move risk** | **High** (collision) / **None** for external empties |
| **Batch owner** | Integration owner + BATCH-HIST-FEAT / IMPL |

---

### 4.9 DS-09 — Observability / monitoring multi-home

| Field | Value |
|---|---|
| **Members** | `docs/operations/observability.md` (Prometheus/Grafana, 791 lines), `docs/iroh/observability.md` (Iroh health snapshot, 58 lines), `docs/operations/cluster_monitoring.md` (cluster dashboard), `docs/features/MONITORING_GUIDE.md` (GitHub Actions/install monitoring), `docs/implementation/MONITORING_IMPLEMENTATION_SUMMARY.md`, arm64 monitoring trio under `deployment/arm64/` |
| **Evidence** | Shared “observability/monitoring” vocabulary but **different scopes**; not byte-duplicates |
| **Disposition** | **Retain-split** by scope — **do not merge** iroh vs ops vs CI monitoring into one file |
| **Canonical scope map** | Ops metrics → `operations/observability.md`; Iroh node health → `iroh/observability.md`; cluster → `cluster_monitoring.md`; CI/install → `features/MONITORING_GUIDE.md` (verify) |
| **Non-survivors** | `MONITORING_IMPLEMENTATION_SUMMARY.md` → Archive; arm64 implementation notes vs quick-ref split like H12 |
| **Redirect strategy** | Cross-link table in each retained guide (content task); summary → Stub Redirect to ops observability |
| **Inbound impact** | `observability` ~37 referrers (string-wide); `MONITORING_GUIDE` ~8 |
| **Replacement gate** | Summary archive **Open**; guide collapse **forbidden** |
| **Move risk** | **Medium** (summary) / **None** (guides) |
| **Batch owner** | Ops / Iroh / feature owners |

---

### 4.10 DS-10 — WAL telemetry dual

| Field | Value |
|---|---|
| **Members** | Root `docs/telemetry_api.md` (338 lines, REST API), `docs/reference/wal_telemetry_api.md` (445 lines, HLA integration), plus `wal_telemetry_cli.md`, `wal_telemetry_client.md`, `wal_telemetry_tracing.md`, `wal_telemetry_ai_ml.md`, artifact `wal_telemetry_grafana_dashboard.json` |
| **Evidence** | Overlapping WAL telemetry topic; reference family is the structured home |
| **Canonical-survivor** | `docs/reference/wal_telemetry_*.md` set after owner verification |
| **Non-survivors** | Root `telemetry_api.md` → **Stub Redirect** to `reference/wal_telemetry_api.md` (or merge unique REST-only sections first) |
| **Redirect strategy** | Stub Redirect at root path; keep JSON artifact with reference/telemetry docs |
| **Inbound impact** | `wal_telemetry` ~18; `telemetry_api` ~7 |
| **Replacement gate** | **Open** after reference pages verified current |
| **Move risk** | **Medium** |
| **Batch owner** | Reference owner |

---

### 4.11 DS-11 — IPFS datasets dual guides

| Field | Value |
|---|---|
| **Members** | `docs/integration/IPFS_DATASETS_INTEGRATION.md` (518 lines), `docs/integration/IPFS_DATASETS_COMPREHENSIVE_INTEGRATION.md` (710 lines) |
| **Evidence** | Same integration topic; comprehensive is longer architecture-style guide; shorter is feature-oriented |
| **Disposition** | **Merge Redirect**: verify both against source; keep one survivor (prefer comprehensive if still accurate) and stub the other **or** explicitly role-split (overview vs deep) with mutual links — **no silent dual maintenance** |
| **Default paper choice** | Survivor = `IPFS_DATASETS_COMPREHENSIVE_INTEGRATION.md` pending owner verify; non-survivor stub → survivor |
| **Replacement gate** | **Pending** integration owner refresh |
| **Move risk** | **Medium** |
| **Batch owner** | Integration owner |
| **Hard constraint** | Do not delete either until merge checklist (unique API names, examples) recorded |

---

### 4.12 DS-12 — Implementation COMPLETE bulk vs architecture

| Field | Value |
|---|---|
| **Members** | `docs/implementation/` — **75 files / 73 markdown** including dense `*_COMPLETE.md` / `*_SUMMARY.md` |
| **Evidence** | Register H1; F-011; sample `EXECUTIVE_SUMMARY.md` dated **2025-10-22** |
| **Canonical replacements** | Per-topic architecture and feature guides (KDOC-010..019, operations, reference) — **not** a single file |
| **Disposition** | Bulk **Archive-after-redirect** → future `docs/ARCHIVE/implementation/`; interim **Drop-from-navigation** |
| **Redirect strategy** | Nav-unlink all implementation COMPLETE links from indexes; ARCHIVE README lists topic → current guide map (KDOC-042/045); optional root `docs/implementation/README.md` becomes Redirect index to ARCHIVE + architecture |
| **Inbound impact** | High discoverability via July DOC-KIT links; ~12 md mention `implementation/` path patterns |
| **Replacement gate** | **Pending-task** for present-tense claims still only in reports; **Drop-from-navigation is allowed now** without move |
| **Move risk** | **High** |
| **Batch owner** | BATCH-HIST-IMPL (KDOC-045) |
| **Hard constraint** | No bulk `mv` until KDOC-042 README exists and Nav-unlink list applied |

---

### 4.13 DS-13 — Architecture pre-program audits vs Wave 0 / new guides

| Field | Value |
|---|---|
| **Historical / audit-style** | `ARCHITECTURE_MODULE_ORGANIZATION.md`, `BACKEND_ARCHITECTURE_VISUAL_SUMMARY.md`, `CLI_MCP_ARCHITECTURE_AUDIT.md`, `FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md`, `MCP_CONTROLLER_CONSOLIDATION.md`, `MCP_INTEGRATION_ARCHITECTURE.md`, `REFACTORED_ARCHITECTURE_README.md` |
| **Current / program** | `SYSTEM_OVERVIEW.md`, `RUNTIME_AND_ENTRYPOINTS.md`, `COMPATIBILITY_LAYERS.md`, `MCP_CONTROL_PLANE.md`, `CONTENT_METADATA_VFS.md`, `CLUSTER_COORDINATION.md`, `NETWORK_TRANSPORTS.md`, `SOURCE_OF_TRUTH_MAP.md`, `GLOSSARY.md`, ADRs under `decisions/` |
| **Disposition** | **Supersede** content first; physical Archive **optional later** |
| **Redirect strategy** | In-place banner on audits pointing to superseding guide (table in register H14); **No-move-yet** |
| **Replacement gate** | **No-move-yet** until KDOC-010..019 stable |
| **Move risk** | **None** |
| **Batch owner** | BATCH-HIST-ARCH |

**Supersession map (evidence from H14)**

| Audit / summary | Redirect / superseding guide |
|---|---|
| `ARCHITECTURE_MODULE_ORGANIZATION.md` | `SYSTEM_OVERVIEW.md`, `RUNTIME_AND_ENTRYPOINTS.md`, `COMPATIBILITY_LAYERS.md` |
| `BACKEND_ARCHITECTURE_VISUAL_SUMMARY.md` | Storage backend architecture (KDOC-012) + `docs/iroh/*` |
| `CLI_MCP_ARCHITECTURE_AUDIT.md` | `RUNTIME_AND_ENTRYPOINTS.md`, MCP control plane, CLI docs (KDOC-032) |
| `FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md` | KDOC-012 / KDOC-015 content-metadata-VFS |
| `MCP_CONTROLLER_CONSOLIDATION.md`, `MCP_INTEGRATION_ARCHITECTURE.md` | `MCP_CONTROL_PLANE.md` |
| `REFACTORED_ARCHITECTURE_README.md` | `SYSTEM_OVERVIEW.md` + exclusive nav (KDOC-060) |

---

### 4.14 DS-14 — CLI/MCP integration dual

| Field | Value |
|---|---|
| **Members** | `docs/integration/UNIFIED_CLI_MCP_INTEGRATION.md`, `docs/integration/CLI_MCP_IMPLEMENTATION_PLAN.md` |
| **Evidence** | Unified “complete integration guide” vs compliance/implementation summary; both assert architecture patterns that must yield to packaging + control plane |
| **Disposition** | **Supersede** present-tense authority → MCP_CONTROL_PLANE + CLI reference (KDOC-032); both files → Historical / Drop-from-navigation until rewritten |
| **Redirect strategy** | Nav-unlink; banner pointing to packaging scripts and control-plane guide |
| **Replacement gate** | **Pending** KDOC-032 / KDOC-014 |
| **Move risk** | **Medium** |
| **Batch owner** | Integration + MCP owners |

---

### 4.15 DS-15 — Root PR and phase final reports

| Field | Value |
|---|---|
| **Members** | `docs/COMPLETE_PR_SUMMARY.md`, `docs/FINAL_COMPREHENSIVE_PR_SUMMARY.md`, plus phase finals overlapping DS-04 (`PHASE5_*`, `PHASE6_*`) |
| **Disposition** | **Archive-after-redirect** + **Drop-from-navigation** |
| **Redirect strategy** | Nav-unlink; no current-status replacement (use git history / CI) |
| **Replacement gate** | **Open** (historical) after Nav-unlink |
| **Move risk** | **Critical** if index-linked |
| **Batch owner** | BATCH-HIST-ROOT |

---

### 4.16 DS-16 — Project overhaul vs live program evidence

| Field | Value |
|---|---|
| **Members** | `docs/project/*` including `COMPREHENSIVE_DOCUMENTATION_OVERHAUL.md`, `DOCUMENTATION_AUDIT_FINDINGS.md`, completion summaries (**2026-02-02**) |
| **Live replacements** | Protected `docs/documentation_plan.md`; live audits `docs/audits/*` (KDOC-001/003/040/041) |
| **Disposition** | **Retain-historical** or Archive; **never** treat checklist “fixed” rows as verification receipts (F-015) |
| **Redirect strategy** | Drop-from-navigation; optional banner → audits/ |
| **Replacement gate** | **Open** |
| **Move risk** | **Medium** |
| **Batch owner** | BATCH-HIST-PROJECT |

---

### 4.17 DS-17 — CI-CD reports vs runbooks

| Field | Value |
|---|---|
| **Report subset (archive)** | `CI_CD_VERIFICATION_REPORT.md`, `GITHUB_RUNNERS_STATUS_REPORT.md`, `GITHUB_RUNNER_SETUP_COMPLETE.md`, `WORKFLOW_FIXES_SUMMARY.md`, `WORKFLOW_STATUS_REPORT.md`, `WORKFLOW_TEST_FIXES.md`, `amd64/AMD64_WORKFLOW_IMPLEMENTATION_SUMMARY.md` |
| **Runbook candidates (retain after verify)** | `CI_CD_VALIDATION_GUIDE.md`, `RUNNER_QUICK_START.md`, `RUNNER_SCRIPTS_GUIDE.md`, `SETUP_RUNNER_NOW.md`, `START_RUNNER_HERE.md` |
| **Near-duplicate note** | `SETUP_RUNNER_NOW.md` vs `START_RUNNER_HERE.md` are title-competing runbooks — owner should Merge or role-split **before** promoting both as canonical |
| **Disposition** | **Retain-split** (H12) |
| **Redirect strategy** | Archive reports with Stub optional; runbook dedup is content task not mass history move |
| **Replacement gate** | Reports **Open**; runbook merge **Pending** ops owner |
| **Move risk** | **Medium** / **None** for verified runbooks |
| **Batch owner** | BATCH-HIST-CICD |

---

### 4.18 DS-19 — Root feature roadmaps

| Field | Value |
|---|---|
| **Members** | `docs/ROADMAP_FEATURES.md`, `docs/performance_optimization_roadmap.md` |
| **Disposition** | **Drop-from-navigation**; label **Proposed** or Archive after unlink |
| **Redirect strategy** | Nav-unlink; feature truth from source + verified `docs/features/*` guides |
| **Replacement gate** | **Open** for nav drop |
| **Move risk** | **Medium** |
| **Batch owner** | BATCH-HIST-ROOT |

---

### 4.19 DS-20 / DS-21 — Status reports and fixes bulk

| Field | Value |
|---|---|
| **Members** | `docs/status_reports/` (18 md), `docs/fixes/` (14 md); parallel already in `docs/ARCHIVE/status-reports/`, `docs/ARCHIVE/fixes/` |
| **Disposition** | **Archive-after-redirect** into curated `ARCHIVE/status-and-fixes/` (KDOC-045) |
| **Redirect strategy** | Directory-level guidance in ARCHIVE README; sparse Stub Redirect only for index-linked paths |
| **Replacement gate** | **Open** after KDOC-042 |
| **Move risk** | **Medium** |
| **Batch owner** | BATCH-HIST-STATUS / FIX |

---

### 4.20 DS-22 — Integration hub trio (not true duplicates)

| Field | Value |
|---|---|
| **Members** | `docs/integration/INTEGRATION_OVERVIEW.md`, `INTEGRATION_QUICK_START.md`, `INTEGRATION_CHEAT_SHEET.md` |
| **Evidence** | Complementary roles (overview / quick start / cheat sheet) — inventory Mixed |
| **Disposition** | **Retain-split**; refresh under integration owner (KDOC integration tasks); **not** archive as duplicates |
| **Redirect strategy** | Cross-link only; ensure single “start” pointer from exclusive nav |
| **Replacement gate** | **Pending** refresh |
| **Move risk** | **None** |
| **Batch owner** | Integration owner |

---

## 5. Redirect implementation patterns (for later tasks)

These patterns are **specifications** for KDOC-042/045/060. This task does not apply them.

### 5.1 Stub Redirect template

```markdown
# [Original title] (redirect)

| Field | Value |
|---|---|
| Document class | **Historical** (redirect stub) |
| Status | Superseded — do not use as current guidance |
| Canonical / survivor | [relative path to survivor] |
| Archived copy | [docs/ARCHIVE/... if moved] |

This path is retained so old links do not 404. Content lived here as a
campaign or duplicate report. Read the survivor for current guidance, or the
archived copy for provenance only.
```

### 5.2 Nav-unlink checklist (per path)

1. Remove from `docs/index.md` “start here” / feature lists if marked current.
2. Remove or demote in `docs/README.md` maps.
3. Remove or mark Historical in `docs/DOCUMENTATION_INDEX.md`.
4. Remove from `docs/QUICK_REFERENCE.md` if presented as live procedure.
5. Leave audit/register links (this file, inventory, freshness) intact.

### 5.3 In-place Historical banner (migration / project survivors)

```markdown
> **Historical:** This document records a past migration or campaign.
> It must not be used as current operator or runtime authority.
> Current guidance: [link]. See docs/guides/DOCUMENTATION_GUIDE.md authority classes.
```

### 5.4 When to use each Redirect type

| Situation | Redirect type |
|---|---|
| Exact path duplicate after merge | Stub Redirect |
| Root echo of migration/ tree | Stub Redirect → migration survivor |
| COMPLETE report linked from index | Nav-unlink first; Stub optional |
| False MCP runtime claim | Supersede banner + Nav-unlink (authority) before any delete |
| Competing indexes | Index Redirect role (KDOC-060), not ARCHIVE |
| Split Mixed directories | No Redirect for retained children; archive children only |

---

## 6. Inbound-link impact summary

Approximate **markdown referrer counts** from `docs/` (string match; planning signal, not a full link graph):

| Pattern | ~Referrers | Sets | Impact |
|---|---|---|---|
| `observability` | 37 | DS-09 | Cross-link carefully; do not mass-rename |
| `QUICK_REFERENCE` | 22 | DS-01 | Critical nav surface |
| `AUTO_HEALING` | 21 | DS-05/18/23 | Many summary links |
| `wal_telemetry` | 18 | DS-10 | Prefer reference/ home |
| `implementation/` | 12 | DS-12 | High COMPLETE pollution |
| `MCP_SERVER_MIGRATION_GUIDE` | 11 | DS-03 | Authority-sensitive |
| `ANYIO_MIGRATION` | 11 | DS-02 | Root + migration |
| `100_PERCENT` | 10 | DS-04 | Coverage campaign |
| `libp2p_integration` | 10 | DS-08 | Path collision |
| `IPFS_DATASETS` | 10 | DS-11 | Dual guides |
| `DOCUMENTATION_INDEX` | 9 | DS-01 | Critical |
| `MONITORING_GUIDE` | 8 | DS-09 | Scope-specific |
| `status_reports/` | 8 | DS-20 | Medium |
| `REFACTORING_COMPLETE` | 7 | DS-07 | Dual trees |
| `telemetry_api` | 7 | DS-10 | Root dual |

**Impact rule:** Critical/High impact sets (DS-01, DS-03, DS-04, DS-08, DS-12) require Stub Redirect or Nav-unlink **before** filesystem moves. Low-impact ARCHIVE-internal duplicates may move with directory README alone.

---

## 7. Execution order (phased; paper schedule)

### Phase P0 — Navigation safety (no file moves)

| Step | Action | Sets | Owner task |
|---|---|---|---|
| P0.1 | Publish this plan (done in KDOC-041) | all | KDOC-041 |
| P0.2 | Publish ARCHIVE boundary README (“not current”) | enables later moves | KDOC-042 |
| P0.3 | Define exclusive index roles; do not archive indexes | DS-01 | KDOC-060 (plan alignment) |

### Phase P1 — Authority and high-risk unlink (still no bulk moves)

| Step | Action | Sets | Gate required |
|---|---|---|---|
| P1.1 | Banner/supersede MCP migration false runtime; Nav-unlink | DS-03 | MCP_CONTROL_PLANE + packaging |
| P1.2 | Merge decision for AnyIO root echoes; Stub plan | DS-02 | Historical survivor chosen |
| P1.3 | Nav-unlink coverage/PR/roadmap historical targets from indexes | DS-04, DS-15, DS-19 | Drop-from-nav allowed now |
| P1.4 | Resolve QUICK_START vs QUICKSTART | DS-18 | Merge checklist |
| P1.5 | libp2p survivor designation + README Redirect plan | DS-08 | Integration verify pending |

### Phase P2 — Archive intake with redirects (KDOC-045)

| Step | Action | Sets | Prerequisite |
|---|---|---|---|
| P2.1 | Archive status_reports + fixes | DS-20, DS-21, DS-06 | KDOC-042 |
| P2.2 | Archive auto-healing / deployment summaries | DS-05, DS-23 | Guides retained |
| P2.3 | Archive CI-CD report subset | DS-17 | Runbooks retained |
| P2.4 | Archive testing campaigns (not health matrix) | DS-04 campaigns | KDOC-039 progress preferred |
| P2.5 | Archive root migration echoes + PR reports | DS-02 root, DS-15 | Stubs in place |
| P2.6 | WAL root telemetry Redirect | DS-10 | reference verified |
| P2.7 | IPFS datasets merge/stub | DS-11 | owner merge |
| P2.8 | Project labeled or archived | DS-07, DS-16 | audits remain live |

### Phase P3 — Deferred / replacement-gated

| Step | Action | Sets | Prerequisite |
|---|---|---|---|
| P3.1 | Bulk `docs/implementation/` → ARCHIVE/implementation | DS-12 | Nav-unlink + topic replacements for linked claims |
| P3.2 | Optional archive of architecture audits | DS-13 | KDOC-010..019 stable |
| P3.3 | Integration hub refresh (no archive) | DS-22, DS-14 | owner tasks |
| P3.4 | Exclusive navigation rewrite | DS-01 | KDOC-060 |

### Phase dependency diagram (text)

```
KDOC-041 (this plan)
    → KDOC-042 (ARCHIVE README)
        → KDOC-045 (physical moves for gate-Open sets)
    → KDOC-030..039 (replacements; unlock Pending gates)
    → KDOC-060 (exclusive nav; DS-01 + unlink lists)
Hard rule: KDOC-045 step for a set requires that set's Replacement gate Open
           AND (Stub Redirect or Nav-unlink) recorded for Critical/High risk.
```

---

## 8. Batch owner checklist (execution handoff)

| Batch owner | Duplicate sets | First allowed action | Blocked until |
|---|---|---|---|
| **BATCH-HIST-ROOT** | DS-01 targets, DS-04 root, DS-15, DS-19 | Nav-unlink lists | Index role rewrite is KDOC-060 |
| **BATCH-HIST-MIG** | DS-02, DS-03 | Banners + Stub plans | Destroying MCP guides before supersession |
| **BATCH-HIST-TEST** | DS-04 testing campaigns | Archive campaigns | Moving TEST_HEALTH_MATRIX |
| **BATCH-HIST-FEAT** | DS-05, DS-18, DS-23 | Archive summaries | Archiving AUTO_HEALING.md guides |
| **BATCH-HIST-STATUS** | DS-06, DS-07 status, DS-20 | Archive after KDOC-042 | — |
| **BATCH-HIST-FIX** | DS-21 | Archive after KDOC-042 | — |
| **BATCH-HIST-IMPL** | DS-12, libp2p COMPLETE | Drop-from-nav now; move later | Bulk move before architecture coverage |
| **BATCH-HIST-PROJECT** | DS-07 project, DS-16 | Drop-from-nav / label | Citing as live verification |
| **BATCH-HIST-CICD** | DS-17 | Archive reports | Archiving verified runbooks |
| **BATCH-HIST-ARCH** | DS-13 | Banners only | Physical move |
| **BATCH-HIST-ARCHIVE** | Already quarantined copies | Boundary README only | Re-litigating already-moved files as current |
| **Integration / Ops / Iroh / Reference** | DS-08–11, DS-14, DS-22 | Content merge & verify | — |

---

## 9. Out of scope (do not treat as duplicate sets here)

| Family | Why |
|---|---|
| `docs/api_generated/` | Generated — KDOC-046 |
| Empty external gitlinks + `docs/py-ipld-*` | External — KDOC-043/044 |
| Protected program files | Never worker-edited; not historical bulk |
| Candidate-canonical trees without report wrappers (`api/`, `guides/`, `operations/`, `iroh/` contracts, etc.) | Refresh in place; only report-like children enter history batches |
| Wave 0 audits themselves | Program evidence; this plan is one of them |

---

## 10. Reproducible evidence commands

```bash
# Baseline
git rev-parse HEAD

# Scale of historical bulk (align with KDOC-040)
for d in docs/implementation docs/status_reports docs/fixes docs/project \
         docs/migration docs/test_reports docs/ARCHIVE docs/testing docs/ci-cd; do
  printf '%s\tfiles=%s\tmd=%s\n' "$d" \
    "$(find "$d" -type f | wc -l)" \
    "$(find "$d" -type f -name '*.md' | wc -l)"
done

# Root report / migration / coverage cluster
find docs -maxdepth 1 -type f -name '*.md' \
  | rg -i 'PHASE|TEST_COVERAGE|COMPLETE_|FINAL_|ROADMAP|PATH_TO|100_PERCENT|ANYIO|MIGRATION|telemetry' \
  | sort

# COMPLETE/SUMMARY density (F-011 class)
find docs \( -name '*COMPLETE*' -o -name '*SUMMARY*' \) | wc -l

# Exact duals
md5sum docs/MCP_SERVER_MIGRATION_GUIDE.md docs/migration/MCP_SERVER_MIGRATION_GUIDE.md
md5sum docs/features/auto-healing/AUTO_HEALING_IMPLEMENTATION_SUMMARY.md \
       docs/ARCHIVE/implementation-summaries/AUTO_HEALING_IMPLEMENTATION_SUMMARY.md
md5sum docs/project/REFACTORING_COMPLETE_SUMMARY.md \
       docs/status_reports/REFACTORING_COMPLETE_SUMMARY.md
wc -l docs/features/auto-healing/AUTO_HEALING_QUICK_START.md \
      docs/features/auto-healing/AUTO_HEALING_QUICKSTART.md

# Index competition
wc -l docs/index.md docs/README.md docs/DOCUMENTATION_INDEX.md docs/QUICK_REFERENCE.md

# libp2p / datasets / observability candidates
find docs -iname '*libp2p*' | sort
ls docs/integration/IPFS_DATASETS*.md
ls docs/operations/observability.md docs/iroh/observability.md docs/features/MONITORING_GUIDE.md

# Validation for this task
test -s docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md \
  && rg -q "Redirect" docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md
```

---

## 11. Acceptance self-check (KDOC-041)

| Acceptance criterion | Status |
|---|---|
| Output path `docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md` | This file |
| Every duplicate set has **evidence-based disposition** | Yes — DS-01..DS-23 matrix §3 + detail §4 |
| **Canonical replacements** selected (or explicitly Pending) | Yes — per-set survivor and gate |
| **Archive targets** identified | Yes — non-survivors and bulk families |
| **Redirect / link strategy** recorded | Yes — vocabulary §1.2, patterns §5, per-set rows |
| **Inbound-link impact** recorded | Yes — §6 + per-set fields |
| **Execution order** recorded | Yes — §2 hard constraints + §7 phases |
| **No destructive move precedes a replacement/current guide** | Yes — gates + forbidden sequences §2; Phase P2/P3 blocked on Open gates |
| Conflict policy: plan only, no renames/nav edits | Yes |
| Validation string `Redirect` present | Yes (section titles, strategies, stub template) |
| Depends on KDOC-001, KDOC-003, KDOC-040 consumed | Yes — inventory, freshness, historical register H1–H15 |

**Validation commands:**

```bash
test -s docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md && rg -q "Redirect" docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md
```

---

## 12. Relationship to sibling artifacts

| Artifact | Role relative to this plan |
|---|---|
| `docs/audits/DOCUMENTATION_INVENTORY.md` | Family-level authority; this plan deepens **duplicate** competition inside families |
| `docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md` | Evidence that competing indexes and migration claims mislead (F-003/F-011/F-012/F-014) |
| `docs/audits/HISTORICAL_DOCUMENT_REGISTER.md` | Family dispositions H1–H15; this plan is the **redirect and survivor** layer for KDOC-040 rule 5 (“KDOC-041 picks survivor”) |
| `docs/guides/DOCUMENTATION_GUIDE.md` | Historical class must not recommend as current; banners/stubs must honor it |
| `docs/architecture/MCP_CONTROL_PLANE.md` / ADR-0003 | Authority target for DS-03 supersession |
| Future `docs/ARCHIVE/README.md` | Boundary language; must restate that redirected ARCHIVE material is **not current** |

---

*End of KDOC-041 Duplicate and Redirect Plan. No files were moved. Downstream tasks must keep Replacement gates closed until listed survivors exist and Critical/High sets have Nav-unlink or Stub Redirect ready.*
