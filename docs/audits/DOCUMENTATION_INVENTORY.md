# Documentation Corpus Inventory

| Field | Value |
|---|---|
| Task | KDOC-001 — Inventory and classify the documentation corpus |
| Goal | KDOC-G011 |
| Track | evidence-corpus |
| Inventory date | 2026-08-03 |
| Tree baseline | Git commit `46fd3459c649d06c0602d5ab1aee529269cb5b57` (`docs: plan architecture documentation refresh`) |
| Scope | Entire `docs/` tree as present in the worktree |
| External content | **Not fetched.** All documentation gitlinks remain uninitialized empty working trees. |
| Method | Offline filesystem walk, `git ls-files -s` for mode-`160000` gitlinks, `.gitmodules` path/url inspection only |

This inventory records **reproducible counts**, **top-level families**, **authority-class proposals**, **freshness risk**, **owner/disposition**, and **evidence commands**. It does **not** move, rewrite, or reclassify files in place. Competing authority remains explicit.

---

## 1. Authority vocabulary (proposals only)

Authority-class proposals use the contract from `docs/documentation_plan.md` §3.1:

| Authority class | Meaning |
|---|---|
| **Canonical** | Current conceptual, task, operational, or reference guidance intended for active navigation |
| **Generated** | Deterministic output from code/packaging metadata; hand edits except generator templates are out of policy |
| **Historical** | Dated implementation report, migration record, result, or superseded design; provenance only |
| **External** | Vendored or gitlinked upstream material; not authored `ipfs_kit_py` documentation |
| **Proposed** | Design/ADR/program target not yet fully reflected as accepted current guidance |
| **Program-control** | Operator-protected plan/board/objectives inputs (read-only to workers) |
| **Mixed** | Family contains more than one of the above; sub-paths need later register work |

> **Note:** Labels below are **proposals** for Wave 0 evidence. They do not assert maintainer-accepted navigation decisions. File moves and banners belong to later KDOC history/navigation tasks.

### Freshness-risk scale

| Risk | Criteria |
|---|---|
| **Critical** | Competing indexes or high-traffic docs likely to mislead agents/users about current APIs |
| **High** | Large authored surface with completion-era claims, unproven against current source/tests |
| **Medium** | Useful material with partial drift risk or incomplete structure |
| **Low** | Stable contract, empty external placeholder, or clearly non-navigational historical store |
| **N/A (empty)** | Uninitialized gitlink / zero local content |

### Disposition vocabulary

| Disposition | Intent |
|---|---|
| **Retain-canonical** | Keep as active current guidance; refresh under owner tasks |
| **Retain-generated** | Keep generator-owned; refresh only via KDOC-046 / automation contract |
| **Retain-historical** | Keep for provenance; exclude from current recommendations |
| **Archive-candidate** | Likely move into `ARCHIVE/` or historical register (KDOC-040/045) |
| **External-boundary** | Document ownership/revision; never count as authored coverage |
| **Consolidate** | Merge/reconcile with siblings (indexes, duplicate guides) |
| **Protected-input** | Operator-owned; workers must not edit |
| **Create-under-program** | Target IA path not yet fully populated (e.g. `docs/audits/`) |

---

## 2. Method, exclusions, and non-goals

### 2.1 What was inspected

- Every top-level entry under `docs/` (directories and root files).
- File/markdown counts via `find` (local only).
- Gitlink presence via `git ls-files -s docs` mode `160000`.
- Submodule path/url mapping from local `.gitmodules` (no `git submodule update`, no clone, no network).
- Presence of documentation automation workflows under `.github/workflows/` as ownership hints only.

### 2.2 Explicit exclusions

| Exclusion | Reason |
|---|---|
| Contents of uninitialized gitlinks | Policy: do not fetch external documentation submodules |
| `archive/`, `backup/`, repo-root non-`docs/` trees | Outside declared docs corpus for this task |
| Implementation source under `ipfs_kit_py/`, `mcp/`, `tests/` | Read-only evidence for other Wave 0 tasks; not documentation inventory targets |
| Correctness of historical completion claims | Deferred to KDOC-003 freshness audit and KDOC-040 historical register |
| Choosing a single canonical index | Deferred to KDOC-060 exclusive navigation |

### 2.3 Master reproducible evidence commands

Run from the repository root with no network:

```bash
# Totals
find docs -type f | wc -l
find docs -type f -name '*.md' | wc -l
find docs -type d | wc -l
find docs -mindepth 1 -maxdepth 1 -type d | wc -l
find docs -mindepth 1 -maxdepth 1 -type f | wc -l
du -sh docs

# Top-level names
ls -1A docs | sort

# Per-directory file/md counts
for d in docs/*/; do
  printf '%s\tfiles=%s\tmd=%s\n' "$d" \
    "$(find "$d" -type f | wc -l)" \
    "$(find "$d" -type f -name '*.md' | wc -l)"
done | sort

# Gitlinks under docs (do not initialize)
git ls-files -s docs | awk '$1=="160000" {print}'

# Empty top-level dirs (uninitialized externals or placeholders)
for d in docs/*/; do
  [ -z "$(find "$d" -mindepth 1 -print -quit)" ] && echo "EMPTY $d"
done

# Baseline pin
git rev-parse HEAD
```

**Baseline results (this inventory):**

| Metric | Count / value |
|---|---:|
| Files under `docs/` | 452 |
| Markdown files | 398 |
| Directories | 75 |
| Top-level directories | 35 |
| Top-level files | 45 |
| Tree size | ~6.2M |
| Mode-`160000` gitlinks under `docs/` | 10 |
| Empty top-level directories | 10 |
| Git baseline | `46fd3459c649d06c0602d5ab1aee529269cb5b57` |

> Counts include empty gitlink directories (0 files each) and embedded `py-ipld-*` snapshots (source + tests vendored under `docs/`). They **exclude** any content that would appear only after submodule fetch.

---

## 3. Summary matrix — every top-level family

Every row includes the four acceptance fields: **Authority class**, **Freshness risk**, **Owner/disposition**, and **Evidence command**.

| Family | Files / MD | Authority class (proposal) | Freshness risk | Owner / disposition | Evidence command |
|---|---:|---|---|---|---|
| `docs/` root files | 45 / 44 | **Mixed** (indexes, topics, historical reports, program-control) | **Critical** | Multiple owners; consolidate indexes (KDOC-060); historical register (KDOC-040); topic refresh (KDOC-030..039) | `find docs -maxdepth 1 -type f \| sort` |
| `api/` | 4 / 4 | **Canonical** (candidate) | **High** | KDOC-031/032 API/CLI refresh — Retain-canonical after verification | `find docs/api -type f \| sort` |
| `api_generated/` | 7 / 6 | **Generated** | **High** (stale generator markers) | KDOC-046 only — Retain-generated | `find docs/api_generated -type f \| sort; head -5 docs/api_generated/doc_status.md` |
| `architecture/` | 9 / 9 | **Mixed** (program-control + historical audits + Proposed IA) | **High** | Protected program files + KDOC-010..019 new guides — no mass rewrite of old audits here | `find docs/architecture -type f \| sort` |
| `ARCHIVE/` | 21 / 21 | **Historical** | **Low** | KDOC-040/045 — Retain-historical | `find docs/ARCHIVE -type f \| sort` |
| `ci-cd/` | 14 / 14 | **Mixed** (ops notes + status reports) | **High** | Split current runbook vs archive-candidate (KDOC-040, ops owners) | `find docs/ci-cd -type f \| sort` |
| `deployment/` | 35 / 35 | **Canonical** (candidate ops/deploy) | **High** | KDOC ops/deploy refresh — Retain-canonical after verification | `find docs/deployment -type f \| sort` |
| `development/` | 2 / 2 | **Canonical** (candidate) | **Medium** | KDOC development guides — Retain-canonical | `find docs/development -type f \| sort` |
| `features/` | 31 / 31 | **Mixed** (feature guides + completion notes) | **High** | Feature owners + historical register for `*_COMPLETE*` | `find docs/features -type f \| sort` |
| `filesystem_spec/` | 0 / 0 | **External** | **N/A (empty)** | External-boundary; pin only — do not fetch | `git ls-files -s docs/filesystem_spec; find docs/filesystem_spec -mindepth 1 \| wc -l` |
| `fixes/` | 14 / 14 | **Historical** | **Low** | Archive-candidate / Retain-historical (KDOC-040) | `find docs/fixes -type f \| sort` |
| `guides/` | 10 / 10 | **Canonical** (candidate) | **High** | KDOC-005 lifecycle + task guides — Retain-canonical | `find docs/guides -type f \| sort` |
| `implementation/` | 75 / 73 | **Historical** | **Medium** (volume noise) | Archive-candidate; largest historical bulk (KDOC-040/045) | `find docs/implementation -type f \| wc -l; find docs/implementation -type f -name '*.md' \| wc -l` |
| `integration/` | 22 / 22 | **Mixed** | **High** | Integration owners; plans/cheat-sheets need status labels | `find docs/integration -type f \| sort` |
| `ipfs-docs/` | 0 / 0 | **External** | **N/A (empty)** | External-boundary — do not fetch | `git ls-files -s docs/ipfs-docs; find docs/ipfs-docs -mindepth 1 \| wc -l` |
| `ipfs_cluster/` | 0 / 0 | **External** | **N/A (empty)** | External-boundary — do not fetch | `git ls-files -s docs/ipfs_cluster; find docs/ipfs_cluster -mindepth 1 \| wc -l` |
| `ipfsspec/` | 0 / 0 | **External** | **N/A (empty)** | External-boundary — do not fetch | `git ls-files -s docs/ipfsspec; find docs/ipfsspec -mindepth 1 \| wc -l` |
| `iroh/` | 19 / 19 | **Canonical** (normative Iroh contracts/runbooks) | **Medium** | Iroh subsystem owner / KDOC network tasks — Retain-canonical | `find docs/iroh -type f \| sort` |
| `lassie/` | 0 / 0 | **External** | **N/A (empty)** | External-boundary — do not fetch | `git ls-files -s docs/lassie; find docs/lassie -mindepth 1 \| wc -l` |
| `libp2p-universal-connectivity/` | 0 / 0 | **External** | **N/A (empty)** | External-boundary — do not fetch | `git ls-files -s docs/libp2p-universal-connectivity; find docs/libp2p-universal-connectivity -mindepth 1 \| wc -l` |
| `libp2p_docs/` | 0 / 0 | **External** | **N/A (empty)** | External-boundary — do not fetch | `git ls-files -s docs/libp2p_docs; find docs/libp2p_docs -mindepth 1 \| wc -l` |
| `libp2p_integration/` | 1 / 1 | **Mixed** / thin local stub | **Medium** | Reconcile with `docs/integration/*libp2p*` (KDOC-041) | `find docs/libp2p_integration -type f \| sort` |
| `lighthouse-python-sdk/` | 0 / 0 | **External** | **N/A (empty)** | External-boundary — do not fetch | `git ls-files -s docs/lighthouse-python-sdk; find docs/lighthouse-python-sdk -mindepth 1 \| wc -l` |
| `mcp-python-sdk/` | 0 / 0 | **External** | **N/A (empty)** | External-boundary — do not fetch | `git ls-files -s docs/mcp-python-sdk; find docs/mcp-python-sdk -mindepth 1 \| wc -l` |
| `migration/` | 8 / 8 | **Historical** | **Medium** | Retain-historical; AnyIO claims cross-check in KDOC-003 | `find docs/migration -type f \| sort` |
| `operations/` | 13 / 13 | **Canonical** (candidate) | **High** | Cluster/ops owners — Retain-canonical after verification | `find docs/operations -type f \| sort` |
| `project/` | 7 / 7 | **Historical** | **Low** | Archive-candidate / project completion provenance | `find docs/project -type f \| sort` |
| `py-ipld-car/` | 10 / 2 | **External** (embedded project snapshot) | **Low** | External-boundary; not authored kit docs | `find docs/py-ipld-car -type f \| sort; test -f docs/py-ipld-car/pyproject.toml` |
| `py-ipld-dag-pb/` | 19 / 2 | **External** (embedded project snapshot) | **Low** | External-boundary; not authored kit docs | `find docs/py-ipld-dag-pb -type f \| sort; test -f docs/py-ipld-dag-pb/README.md` |
| `py-ipld-unixfs/` | 27 / 2 | **External** (embedded project snapshot) | **Low** | External-boundary; not authored kit docs | `find docs/py-ipld-unixfs -type f \| sort; test -f docs/py-ipld-unixfs/pyproject.toml` |
| `reference/` | 13 / 13 | **Canonical** (candidate) | **High** | Reference owners — Retain-canonical; verify against source | `find docs/reference -type f \| sort` |
| `status_reports/` | 18 / 18 | **Historical** | **Low** | Retain-historical / Archive-candidate | `find docs/status_reports -type f \| sort` |
| `storacha_specs/` | 0 / 0 | **External** | **N/A (empty)** | External-boundary — do not fetch | `git ls-files -s docs/storacha_specs; find docs/storacha_specs -mindepth 1 \| wc -l` |
| `test_reports/` | 4 / 4 | **Historical** | **Low** | Retain-historical | `find docs/test_reports -type f \| sort` |
| `testing/` | 23 / 23 | **Mixed** (some process value + heavy coverage campaign reports) | **High** | Split health matrix vs archive coverage narratives (KDOC-040) | `find docs/testing -type f \| sort` |
| `workflows/` | 1 / 1 | **Canonical** (process) | **Medium** | Docs maintenance owners — Retain-canonical; align with `.github/workflows` | `find docs/workflows -type f \| sort` |
| `audits/` *(created by this program)* | ≥1 | **Canonical** (program evidence) | **Low** | Wave 0 evidence owners — Create-under-program | `find docs/audits -type f \| sort` |

**Row count check:** 35 pre-existing top-level directories + root-files row + `audits/` program family = full top-level coverage for this corpus.

---

## 4. Family detail notes

### 4.1 Competing indexes and navigation (Critical)

| Path | Role observed | Proposal |
|---|---|---|
| `docs/index.md` | Landing-style index; target IA canonical landing | **Canonical** candidate; exclusive owner KDOC-060 |
| `docs/README.md` | Large “complete documentation” map | Competing index — Consolidate |
| `docs/DOCUMENTATION_INDEX.md` | Topic catalog | Competing index — Consolidate |
| `docs/QUICK_REFERENCE.md` | Short-cut list | Likely retain as auxiliary, not primary index |

**Evidence:**

```bash
wc -c docs/index.md docs/README.md docs/DOCUMENTATION_INDEX.md docs/QUICK_REFERENCE.md
head -n 8 docs/index.md docs/README.md docs/DOCUMENTATION_INDEX.md
```

Agents and humans currently have **four** root navigation entry points without an exclusive ownership rule. Freshness risk is **Critical** because stale links or status banners here amplify into every other family.

### 4.2 Program-control files (Protected)

| Path | Authority class | Disposition |
|---|---|---|
| `docs/documentation_plan.md` | **Program-control** | Protected-input (never worker output) |
| `docs/architecture/ipfs_kit_documentation.objectives.md` | **Program-control** | Protected-input |
| `docs/architecture/ipfs_kit_documentation.todo.md` | **Program-control** | Protected-input |

**Evidence:**

```bash
test -f docs/documentation_plan.md \
  && test -f docs/architecture/ipfs_kit_documentation.objectives.md \
  && test -f docs/architecture/ipfs_kit_documentation.todo.md \
  && rg -n "Authority classes|KDOC-001" docs/documentation_plan.md docs/architecture/ipfs_kit_documentation.todo.md | head
```

### 4.3 Generated API inventory

| Path | Notes |
|---|---|
| `docs/api_generated/README.md` | States auto-generated / weekly update ownership |
| `docs/api_generated/doc_status.md` | Contains unresolved template marker `$(date -u ...)` — generator drift signal |
| `docs/api_generated/module_structure.md` | Dominant size (~450 KB); inventory-style listing |
| `.github/workflows/auto-doc-maintenance.yml` | Automation owner hint for generation |

**Authority class:** **Generated**.  
**Owner/disposition:** KDOC-046 exclusive refresh; hand edits out of policy.  
**Freshness risk:** **High** until drift contract and last-good generation baseline are re-established.

**Evidence:**

```bash
find docs/api_generated -type f -printf '%s\t%P\n' | sort -n
head -n 20 docs/api_generated/README.md docs/api_generated/doc_status.md
test -f .github/workflows/auto-doc-maintenance.yml
```

### 4.4 Architecture family composition

Current contents are **not** yet the target guide set from the plan (`SYSTEM_OVERVIEW.md`, etc.). Observed mix:

| Group | Paths | Proposal |
|---|---|---|
| Program-control | `ipfs_kit_documentation.objectives.md`, `ipfs_kit_documentation.todo.md` | Protected-input |
| Prior architecture audits / reviews | e.g. `CLI_MCP_ARCHITECTURE_AUDIT.md`, `FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md`, `MCP_*` | Historical or Proposed inputs to new guides |
| Target guides (absent) | `SYSTEM_OVERVIEW.md`, `RUNTIME_AND_ENTRYPOINTS.md`, … | **Proposed** deliverables for KDOC-010..019 |

**Evidence:**

```bash
ls -1 docs/architecture
# Expected absence of new guides at this baseline:
test ! -f docs/architecture/SYSTEM_OVERVIEW.md
```

### 4.5 Historical / report-like families (high volume)

These families dominate corpus volume and should not appear as current how-to guidance without explicit status labels:

| Family | Files | Typical content | Disposition |
|---|---:|---|---|
| `implementation/` | 75 | `*_COMPLETE.md`, phase summaries | Archive-candidate |
| `status_reports/` | 18 | refactoring/integration summaries | Archive-candidate |
| `testing/` | 23 | 100% coverage campaign + some process docs | Mixed → split |
| `fixes/` | 14 | one-off fix write-ups | Archive-candidate |
| `project/` | 7 | project completion / overhaul notes | Archive-candidate |
| `migration/` | 8 | AnyIO/MCP/secrets migration batches | Retain-historical |
| `test_reports/` | 4 | dated test result dumps | Retain-historical |
| `ARCHIVE/` | 21 | already quarantined | Retain-historical |
| Root coverage/PR reports | many | `PHASE*`, `TEST_COVERAGE_*`, `COMPLETE_*`, `FINAL_*` | Archive-candidate |

**Evidence:**

```bash
find docs/implementation docs/status_reports docs/fixes docs/project docs/migration docs/test_reports docs/ARCHIVE docs/testing \
  -type f -name '*.md' | wc -l
find docs -maxdepth 1 -type f -name '*.md' | rg -i 'PHASE|TEST_COVERAGE|COMPLETE_|FINAL_|ROADMAP|PATH_TO' | sort
```

### 4.6 Maintained-candidate operational and user families

| Family | Why candidate-canonical | Primary risks |
|---|---|---|
| `api/` | Public API/CLI/core concept docs | Export/version drift (KDOC-002/031/032) |
| `guides/` | Task-oriented how-to | Needs lifecycle metadata (KDOC-005) |
| `operations/` | Cluster/ops/metrics | Parallel cluster implementations unresolved |
| `deployment/` | Docker/k8s/arm64/ci deploy | Platform matrix staleness |
| `development/` | Async + testing contributor docs | Thin coverage of contributing surface |
| `reference/` | Backends, WAL, telemetry facts | Signature/config drift |
| `features/` | Feature guides (VFS, MCP, pins, etc.) | Completion reports mixed into guides |
| `integration/` | Datasets, fsspec, LangChain, etc. | Plans vs implemented status conflation |
| `iroh/` | Explicit normative contracts/runbooks | Keep separate from empty external gitlinks |
| `workflows/` | Documentation maintenance process | Must match real GitHub workflows |

### 4.7 Embedded `py-ipld-*` snapshots

These are **full mini-projects** (Python packages, tests, CI workflow files) checked into `docs/` as regular tree content (mode `100644`), not mode-`160000` gitlinks at this path:

| Path | Files | Signal |
|---|---:|---|
| `docs/py-ipld-car/` | 10 | `pyproject.toml`, package + tests |
| `docs/py-ipld-dag-pb/` | 19 | package + proto + tests |
| `docs/py-ipld-unixfs/` | 27 | package + tests |

`.gitmodules` also lists **root-level** `py-ipld-*` submodule URLs (separate from the `docs/` snapshots). This inventory does not resolve that dual-path relationship beyond noting the boundary.

**Authority class:** **External** (embedded upstream/project snapshot).  
**Disposition:** External-boundary — **not counted as authored `ipfs_kit_py` documentation** (per plan §4).  
**Evidence:**

```bash
for d in docs/py-ipld-car docs/py-ipld-dag-pb docs/py-ipld-unixfs; do
  echo "== $d =="; find "$d" -maxdepth 2 -type f | head
  git ls-files -s "$d" | awk '{print $1}' | sort -u
done
```

### 4.8 External documentation gitlinks (uninitialized)

Local `.gitmodules` maps the following paths under `docs/`. Working trees are **empty** in this baseline. Content was **not** fetched.

| Path | Recorded upstream (from local `.gitmodules`) | Recorded gitlink SHA (short) | Local files |
|---|---|---|---:|
| `docs/filesystem_spec` | `https://github.com/fsspec/filesystem_spec.git` | `fec09b04ad62` | 0 |
| `docs/ipfs-docs` | `https://github.com/ipfs/ipfs-docs.git` | `4cf83720b597` | 0 |
| `docs/ipfs_cluster` | `https://github.com/ipfs-cluster/ipfs-cluster-website.git` | `c7ca8b5f87b4` | 0 |
| `docs/ipfsspec` | `https://github.com/fsspec/ipfsspec.git` | `03f5199b9bf5` | 0 |
| `docs/lassie` | `https://github.com/filecoin-project/lassie.git` | `c6ba777810d0` | 0 |
| `docs/libp2p-universal-connectivity` | `https://github.com/libp2p/universal-connectivity.git` | `e18a6de9c020` | 0 |
| `docs/libp2p_docs` | `https://github.com/libp2p/docs.git` | `17cee4a43879` | 0 |
| `docs/lighthouse-python-sdk` | `https://github.com/lighthouse-web3/lighthouse-python-sdk.git` | `6b2c86693090` | 0 |
| `docs/mcp-python-sdk` | `https://github.com/modelcontextprotocol/python-sdk.git` | `d3133ae6ce73` | 0 |
| `docs/storacha_specs` | `https://github.com/storacha/specs.git` | `3b6791869635` | 0 |

Also listed in `.gitmodules` but **not** present as a top-level `docs/` entry in this worktree:

| Path in `.gitmodules` | Notes |
|---|---|
| `docs/filecoin-address-python` | No corresponding empty dir observed at inventory time |

**Authority class:** **External** for all rows.  
**Owner/disposition:** External-boundary; revision pins are the gitlink SHAs; exclude from authored coverage metrics.  
**Policy reminder:** `IPFS_KIT_AUTO_INSTALL_BINARIES=0`; do not initialize these for documentation tasks.

**Evidence (safe, offline):**

```bash
# Paths and SHAs only — no fetch
git ls-files -s docs | awk '$1=="160000" {print}'
rg -n '\[submodule "docs/' .gitmodules
for d in docs/filesystem_spec docs/ipfs-docs docs/ipfs_cluster docs/ipfsspec \
         docs/lassie docs/libp2p-universal-connectivity docs/libp2p_docs \
         docs/lighthouse-python-sdk docs/mcp-python-sdk docs/storacha_specs; do
  printf '%s local_entries=%s\n' "$d" "$(find "$d" -mindepth 1 2>/dev/null | wc -l)"
done
```

### 4.9 Root loose-file clusters

Root `docs/*.md` (44) + `docs/wal_telemetry_grafana_dashboard.json` (1) form a **Mixed** family that later tasks should not treat as a single authority.

| Cluster | Example paths | Proposed class | Disposition |
|---|---|---|---|
| Program-control | `documentation_plan.md` | Program-control | Protected-input |
| Navigation | `index.md`, `README.md`, `DOCUMENTATION_INDEX.md`, `QUICK_REFERENCE.md` | Mixed / competing | Consolidate (KDOC-060) |
| Topic / feature deep-dives | `knowledge_graph.md`, `ipfs_dataloader.md`, `filesystem_journal.md`, `containerization.md`, `integrated_search.md`, `GRAPHRAG_AND_BUCKET_EXPORT.md`, … | Canonical candidate or Mixed | Per-topic owner verify |
| Specs / contracts | `VFS_CONTRACT_SPEC.md`, `api_stability.md` | Canonical candidate | Retain + verify |
| Install / release | `installation_guide.md`, `INSTALLER_DOCUMENTATION.md`, `pypi_release.md`, `RELEASE_CHECKLIST_SUBMODULE_SCOPE.md` | Mixed | Refresh install path; keep release checklist |
| Coverage / phase / PR reports | `PHASE*`, `TEST_COVERAGE_*`, `PATH_TO_*`, `COMPLETE_*`, `FINAL_*`, `100_PERCENT_*` | Historical | Archive-candidate |
| Migration echoes | `ANYIO_MIGRATION.md`, `MCP_SERVER_MIGRATION_GUIDE.md`, `COMPLETE_ANYIO_MIGRATION_SUMMARY.md` | Historical | Align with `migration/` |
| Roadmaps | `ROADMAP_FEATURES.md`, `performance_optimization_roadmap.md` | Mixed / Proposed | Label status; do not present as implemented |
| Artifact | `wal_telemetry_grafana_dashboard.json` | Reference artifact | Keep with telemetry docs or move under `reference/` later |

**Evidence:**

```bash
find docs -maxdepth 1 -type f -printf '%s\t%f\n' | sort -n
```

### 4.10 Thin / sparse non-external families

| Path | Content | Note |
|---|---|---|
| `docs/libp2p_integration/` | Single `README.md` | Overlaps naming with `docs/integration/libp2p_integration.md` and empty external `libp2p_*` gitlinks — reconciliation needed (KDOC-041) |
| `docs/workflows/` | `documentation-maintenance.md` only | Pair with `.github/workflows/docs.yml`, `pages.yml`, `auto-doc-maintenance.yml` |
| `docs/development/` | 2 guides | Target IA expects broader contributor surface |

---

## 5. Classification roll-up (proposal counts)

Approximate **primary** class of each top-level family (Mixed counted once as Mixed; root files as Mixed; audits as Canonical evidence):

| Authority class (primary) | Families (approx.) |
|---|---|
| External (empty gitlinks) | 10 |
| External (embedded `py-ipld-*`) | 3 |
| Historical | 6 (`ARCHIVE`, `fixes`, `implementation`, `migration`, `project`, `status_reports`, `test_reports` → 7 if counting `test_reports`) |
| Generated | 1 (`api_generated`) |
| Canonical (candidate) | `api`, `deployment`, `development`, `guides`, `iroh`, `operations`, `reference`, `workflows`, `audits` |
| Mixed | `architecture`, `ci-cd`, `features`, `integration`, `testing`, `libp2p_integration`, root files |

These are **planning labels** for downstream tasks, not coverage scorecard pass/fail.

---

## 6. Ownership map (downstream task hooks)

| Concern | Primary later owners | Inventory implication |
|---|---|---|
| Corpus freshness / stale claims | KDOC-003 | Use this inventory’s High/Critical families first |
| Historical register & dispositions | KDOC-040, KDOC-045 | `implementation/`, root reports, `status_reports/`, `fixes/`, `testing/` campaigns |
| Duplicate reconciliation | KDOC-041 | Competing indexes; libp2p paths; migration duplicates |
| Generated API contract | KDOC-046 | `api_generated/` exclusive |
| External/gitlink boundary record | KDOC-043/044 (history/external wave) | 10 empty gitlinks + `py-ipld-*` snapshots |
| Architecture guides | KDOC-010..019 | Replace/supersede ad-hoc architecture audits |
| Current user/operator docs | KDOC-030..039 | `api/`, `guides/`, `operations/`, `deployment/`, features |
| Navigation exclusivity | KDOC-060 | Single landing path among indexes |
| Final scorecard | KDOC-062 | Must not count External/Generated/Historical as maintained canonical |

---

## 7. Acceptance self-check (KDOC-001)

| Acceptance criterion | Status |
|---|---|
| Every top-level docs family has an **Authority class** proposal | Yes — §3 matrix |
| Every family has **freshness risk** | Yes — §3 matrix |
| Every family has **owner/disposition** | Yes — §3 matrix + §6 |
| Every family has a **reproducible evidence command** | Yes — §3 matrix + §2.3 |
| No external content fetched | Yes — gitlinks empty; only local `.gitmodules` / `git ls-files` used |
| Output path `docs/audits/DOCUMENTATION_INVENTORY.md` | This file |
| Validation string `Authority class` present | Yes |

**Validation commands:**

```bash
test -s docs/audits/DOCUMENTATION_INVENTORY.md && rg -q "Authority class" docs/audits/DOCUMENTATION_INVENTORY.md
```

---

## 8. Appendix — per-family one-liner evidence script

Copy-paste offline re-verification of counts used in this inventory:

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "HEAD=$(git rev-parse HEAD)"
echo "files=$(find docs -type f | wc -l) md=$(find docs -type f -name '*.md' | wc -l) dirs=$(find docs -type d | wc -l)"
echo "toplevel_dirs=$(find docs -mindepth 1 -maxdepth 1 -type d | wc -l) toplevel_files=$(find docs -mindepth 1 -maxdepth 1 -type f | wc -l)"
echo "gitlinks=$(git ls-files -s docs | awk '$1=="160000"' | wc -l)"
for d in docs/*/; do
  printf '%-42s files=%3s md=%3s empty=%s\n' "$d" \
    "$(find "$d" -type f | wc -l)" \
    "$(find "$d" -type f -name '*.md' | wc -l)" \
    "$( [ -z "$(find "$d" -mindepth 1 -print -quit)" ] && echo yes || echo no )"
done | sort
```

---

*End of KDOC-001 inventory. Subsequent evidence tasks (KDOC-002..006, KDOC-040..) consume this classification; they must not treat proposals as accepted maintainer decisions.*
