# Freshness and Implementation Change Audit

| Field | Value |
|---|---|
| **Task** | KDOC-003 |
| **Goal** | KDOC-G011 |
| **Audit date** | 2026-08-03 |
| **Repository commit** | `46fd3459` (`docs: plan architecture documentation refresh`) |
| **Tree id (supervisor)** | `46fd3459c649d06c0602d5ab1aee529269cb5b57` |
| **Package version (packaging)** | `0.3.0` (`pyproject.toml`, `setup.py`) |
| **Scope** | Static repository inspection only: docs tree, packaging metadata, source entry points, focused tests layout, Git history, and documentation workflows. No external network fetch. |
| **Conflict policy** | Audit only. Target documents are not modified in this task. |
| **Baselines compared** | (1) February 2026 documentation overhaul; (2) July 2026 DOC-KIT reachability campaign; (3) current tree at audit commit. |

## 1. Purpose and method

This register records **evidence-backed** documentation freshness failures and implementation changes that stale docs have not absorbed. Each finding names:

1. **Severity** (Critical / High / Medium / Low)
2. **Exact document path(s)**
3. **Contradicting source, test, packaging, workflow, or history evidence** (with paths, commands, or commit IDs)
4. **Recommended owner / follow-up task** from the architecture documentation program

### 1.1 Severity definitions

| Severity | Meaning |
|---|---|
| **Critical** | Install, start, or primary public-entry instructions that fail against the current tree, or primary-surface docs that present superseded/conflicting authorities as current. |
| **High** | Subsystem architecture, CLI/API, generated, or CI/docs toolchain claims that contradict current source or workflows and will mislead agents or operators. |
| **Medium** | Navigation, classification, or secondary claim drift that promotes historical material or incomplete inventories without immediately breaking a primary command. |
| **Low** | Local inconsistency with limited blast radius; still evidence-backed, not a vague "might be old" claim. |

### 1.2 What this audit does **not** claim

- It does not claim a measured line/branch coverage percentage for the whole package (no trustworthy current coverage totals were found in-tree at audit time).
- It does not re-run the full July link campaign or invent link counts without re-measurement.
- It does not mark any backlog item complete.
- It does not fetch gitlinked external documentation content (empty vendor directories are classified as empty/external placeholders only).

### 1.3 Reproducible evidence commands

```bash
# Corpus size at audit time
find docs -name '*.md' | wc -l          # expected ~398
find docs -type f | wc -l               # expected ~452

# Packaging surface
rg -n '^(version|requires-python)|\\[project\\.scripts\\]' pyproject.toml
rg -n "python_requires|version=" setup.py | head

# February overhaul commits
git log --oneline --since=2026-02-01 --until=2026-02-15 -- docs/ | head
git log -1 --format='%h %ci %s' -- docs/project/COMPREHENSIVE_DOCUMENTATION_OVERHAUL.md

# July reachability campaign
git log --oneline --since=2026-07-24 --until=2026-07-26 --grep=DOC-KIT | wc -l

# Generated-doc stamp
head -5 docs/api_generated/module_structure.md

# Public scripts
python3 -c "import tomllib; from pathlib import Path; print(tomllib.loads(Path('pyproject.toml').read_text())['project']['scripts'])"

# High-level API import authority
python3 -c "import importlib.util; s=importlib.util.find_spec('ipfs_kit_py.high_level_api'); print(s.origin)"
```

Counts and stamps above were collected on **2026-08-03** at commit `46fd3459`.

---

## 2. Baseline history (do not conflate)

### 2.1 February 2026 documentation overhaul

| Evidence | Detail |
|---|---|
| Primary summary | `docs/project/COMPREHENSIVE_DOCUMENTATION_OVERHAUL.md` (dated **February 2, 2026**, status COMPLETE) |
| Related audit | `docs/project/DOCUMENTATION_AUDIT_FINDINGS.md` (dated **February 2, 2026**) |
| Organizing commit | `4e0f2e8d` / follow-up `d4d8a0c9` (**2026-02-03**) — organize docs tree, rewrite root/docs READMEs |
| Character | File moves into `features/`, `deployment/`, `operations/`, `reference/`, `ARCHIVE/`; README expansion; partial accuracy audit |
| Residual from that audit | Phase 3–6 of the Feb audit checklist remain unchecked (critical fixes, broken links, README creation, final validation). Several Feb findings were **partially** fixed (e.g. Python 3.12 in `docs/installation_guide.md`) while **other navigation files retain the same class of defect** (see F-001). |

### 2.2 July 2026 reachability campaign

| Evidence | Detail |
|---|---|
| Window | **2026-07-24** through **2026-07-25** (local timestamps on DOC-KIT commits) |
| Volume | **164** commits matching `DOC-KIT` in that window; **109** with subject containing `unreachable` |
| Representative change | `fecfe72f` (2026-07-25) — *DOC-KIT-973: Maintained document unreachable in docs/implementation/FILECOIN_PIN_IMPLEMENTATION_SUMMARY.md* |
| Actual diff pattern | Adds Markdown links into `README.md`, `docs/README.md`, `docs/index.md`, and/or `docs/guides/DOCUMENTATION_GUIDE.md` so previously unlinked completion reports become reachable |
| Character | **Link-only / navigation density increase**, not claim verification against source |
| Program stance | `docs/documentation_plan.md` §1.1 explicitly states this architecture refresh **does not repeat** that link-only campaign |

### 2.3 Implementation change since those baselines (high-signal)

These implementation surfaces are present in the current tree and are **under-documented or contradicted** by still-current navigation and feature docs:

| Surface | Current authority (source/packaging) | Doc posture at audit |
|---|---|---|
| Package scripts | `pyproject.toml` `[project.scripts]`: `ipfs-kit`, `ipfs-kit-mcp`, `ipfs-kit-mcp-tools`, `ipfs-kit-iroh*` | Root/`__init__` and several guides still advertise root `final_mcp_server_enhanced.py` |
| MCP++ server package | `ipfs_kit_py/mcp_server/` (`server.py:main`, `cli.py:main`, `fastmcp_app.py`) | Competing `ipfs_kit_py/mcp/` (~619 `.py` files), root `mcp/`, and `servers/*` variants coexist; docs rarely rank them |
| Backend type registry | `ipfs_kit_py/backend_registry.py` (`BackendTypeRegistry`, Iroh plugin, entry-point group `ipfs_kit.backends`) | `docs/reference/storage_backends.md` freezes "6 backends" and omits Iroh registry model |
| Iroh subsystem | `ipfs_kit_py/iroh*`, `docs/iroh/*` (19 files), CHANGELOG Unreleased Iroh contracts | Not integrated into primary `docs/index.md` production overview |
| Unified CLI dispatcher | `ipfs_kit_py/cli.py` + `ipfs_kit_py/unified_cli_dispatcher.py` (registers `wal`, `journal`, `bucket`, `vfs`, `pin`, `backend`, `state`) | `docs/api/cli_reference.md` describes a Kubo-like command set; `docs/implementation/WAL_FS_JOURNAL_REMOVAL_COMPLETE.md` claims WAL/FS-journal CLI removal that is **false** for current dispatcher |
| High-level API layout | Package dir `ipfs_kit_py/high_level_api/` + large module file `ipfs_kit_py/high_level_api.py` (~553KB) with deferred load | API docs point at a single simple class path without the package/stub/load contract |
| AnyIO migration corpus | Large `*_anyio.py` pair set; migration reports under `docs/migration/` and root completion summaries | `docs/development/async_architecture.md` still documents non-existent AnyIO APIs |
| Docs workflows | `.github/workflows/docs.yml` (Sphinx), `pages.yml` (MkDocs), `auto-doc-maintenance.yml` (weekly generator) | No `docs/conf.py`; `pages.yml` generates into `docs/api/`; generated stamps are October 2025 or unexpanded shell templates |

---

## 3. Findings

### F-001 — Critical — Nonexistent root cluster launcher in primary index

| Field | Value |
|---|---|
| **Severity** | Critical |
| **Exact document(s)** | `docs/index.md` (lines advertising `python start_3_node_cluster.py` in the status banner, Quick Start, Production Deploy, and health-check sections) |
| **Stale claim** | Immediate deployment via `python start_3_node_cluster.py` at repository root; health checks at `http://localhost:8998/health` after that command |
| **Contradicting evidence** | (1) Root path absent: only `tools/start_3_node_cluster.py` and an archive copy under `archive/reorganization_backup_root/` exist. (2) `docs/installation_guide.md` and root `README.md` already use `python tools/start_3_node_cluster.py` — proving the correct path is known elsewhere. (3) `docs/documentation_plan.md` §1.1 cites this exact defect as a planning example. (4) Feb audit `docs/project/DOCUMENTATION_AUDIT_FINDINGS.md` Critical #2 recorded the same class of error. |
| **Why still open** | Feb overhaul fixed `installation_guide.md` but left `docs/index.md` uncorrected; July campaign added more links into `docs/index.md` without repairing the launcher path. |
| **Recommended owner / task** | KDOC-060 / navigation integration owner; interim fix also in scope for KDOC-030 (installation/quick-start refresh) if navigation is not yet unlocked — **do not leave Critical run instructions in the primary index**. |

### F-002 — Critical — Package `__init__` and generated module map advertise missing root MCP server script

| Field | Value |
|---|---|
| **Severity** | Critical |
| **Exact document(s)** | `ipfs_kit_py/__init__.py` (module docstring Quick Start / MCP sections); `docs/api_generated/module_structure.md` (propagates the same start command when generated from package docstrings); historical echoes in `docs/ARCHIVE/status-reports/MCP_DEVELOPMENT_STATUS.md`, `docs/migration/MCP_SERVER_MIGRATION_GUIDE.md` |
| **Stale claim** | `python final_mcp_server_enhanced.py --host 0.0.0.0 --port 9998` as the production MCP start path |
| **Contradicting evidence** | (1) No `final_mcp_server_enhanced.py` at repository root. (2) Copies exist under non-entry locations: `servers/final_mcp_server_enhanced.py`, `scripts/validation/final_mcp_server_enhanced.py`, plus `backup/` and `archive/` variants. (3) **Canonical packaging entry points** in `pyproject.toml`: `ipfs-kit-mcp = "ipfs_kit_py.mcp_server.server:main"` and `ipfs-kit-mcp-tools = "ipfs_kit_py.mcp_server.cli:main"`. (4) `ipfs_kit_py/mcp_server/server.py` defines `main()`. |
| **Recommended owner / task** | KDOC-002 (public surface matrix) + KDOC-014/KDOC-033 (MCP architecture / MCP user docs); packaging docstring fix is a code change outside this audit's edit scope but must be tracked as a doc-trigger for generators. |

### F-003 — Critical — Competing MCP implementation families presented without authority ranking

| Field | Value |
|---|---|
| **Severity** | Critical |
| **Exact document(s)** | `docs/index.md` (Production MCP Server framing); `docs/architecture/MCP_INTEGRATION_ARCHITECTURE.md`; `docs/architecture/CLI_MCP_ARCHITECTURE_AUDIT.md`; `docs/mcp`/`docs/migration/MCP_SERVER_MIGRATION_GUIDE.md`; dashboard/server docs under `docs/features/mcp/`, `docs/deployment/SYSTEMD_MCP_SERVICE_SETUP.md` |
| **Stale / unsafe claim pattern** | Single "production MCP server" narrative without distinguishing package entry points from legacy trees |
| **Contradicting evidence** | At least four coexisting trees: (a) `ipfs_kit_py/mcp_server/` (~34 `.py`, script entry `ipfs-kit-mcp`); (b) `ipfs_kit_py/mcp/` (~619 `.py`, controllers/dashboard/servers); (c) top-level `mcp/` tool shims; (d) `servers/*.py` standalone launchers. Packaging only registers (a). |
| **Recommended owner / task** | KDOC-004 (`SOURCE_OF_TRUTH_MAP.md`) and KDOC-014 (MCP/control-plane architecture); ADR follow-up KDOC-02x for MCP authority if ambiguity remains. |

### F-004 — High — CLI reference documents a Kubo-mirror CLI that does not match `cli.py`

| Field | Value |
|---|---|
| **Severity** | High |
| **Exact document(s)** | `docs/api/cli_reference.md` |
| **Stale claims** | (1) `ipfs-kit --version` as verify-install step. (2) Core commands `add`, `cat`, `get`, `ls`, `pin`, `swarm`, `name`, `cluster`, `ai …` as the primary CLI surface. (3) Package name wording `ipfs-kit-py` mixed with install identity `ipfs_kit_py`. |
| **Contradicting evidence** | (1) `ipfs_kit_py/cli.py` builds subparsers for `mcp`, `daemon`, `services`, `autoheal`, then delegates unified commands via `unified_cli_dispatcher.py` (`bucket`, `vfs`, `wal`, `pin`, `backend`, `journal`, `state`). No `add_argument('--version')` / `action='version'` in `cli.py`. (2) Console script is `ipfs-kit = "ipfs_kit_py.cli:sync_main"` in `pyproject.toml`. (3) Distribution name in packaging is `ipfs_kit_py` (`setup.py` `name='ipfs_kit_py'`, `pyproject.toml` project name). |
| **Recommended owner / task** | KDOC-032 (CLI documentation refresh); cross-check with KDOC-002 surface matrix. |

### F-005 — High — WAL / FS-journal "CLI removal complete" contradicts live dispatcher

| Field | Value |
|---|---|
| **Severity** | High |
| **Exact document(s)** | `docs/implementation/WAL_FS_JOURNAL_REMOVAL_COMPLETE.md` (title and body claim complete removal of `ipfs-kit wal` and `ipfs-kit fs-journal`); secondary confusion in `docs/architecture/CLI_MCP_ARCHITECTURE_AUDIT.md` (still lists `ipfs-kit wal`) |
| **Stale claim** | WAL and FS-journal commands were completely removed from the CLI interface |
| **Contradicting evidence** | `ipfs_kit_py/unified_cli_dispatcher.py` defines `_add_wal_commands` (`wal status|list|show|wait|cleanup`) and `_add_journal_commands` (`journal status|list|replay|compact`); `ipfs_kit_py/cli.py` calls both. Handler imports `wal_cli` and `fs_journal_cli`. Note: command name is `journal`, not `fs-journal` — the removal report is wrong on both presence and naming. |
| **History note** | Document is an implementation completion report; July campaign made many such reports more reachable from primary navigation, amplifying the contradiction. |
| **Recommended owner / task** | KDOC-041 (historical classification) to mark the removal report **Historical**; KDOC-032 to document current `wal` / `journal` commands from source. |

### F-006 — High — Storage backend docs freeze "6 backends" and omit Iroh registry model

| Field | Value |
|---|---|
| **Severity** | High |
| **Exact document(s)** | `docs/reference/storage_backends.md` (status banner: "6 integrated (IPFS, Filecoin, S3, Storacha, HuggingFace, Lassie)"); `docs/index.md` and `docs/README.md` (same six-backend production claim) |
| **Stale claim** | Exactly six operational backends; architecture diagram stops at Storacha/S3 tiers |
| **Contradicting evidence** | (1) `ipfs_kit_py/backend_registry.py` — plugin registry with `IrohBackendPlugin`, legacy plugins, and entry-point group `ipfs_kit.backends`. (2) `ipfs_kit_py/backends/` includes `iroh_backend.py`, `filesystem_backend.py`, `s3_backend.py`, `ipfs_backend.py`, `real_api_storage_backends.py`. (3) Removal report itself mentions **15 backends** for health/config choices. (4) `CHANGELOG.md` Unreleased section documents Iroh as disabled-by-default preview with explicit contracts. (5) `docs/iroh/` holds 19 operator/architecture files not linked from the six-backend narrative. |
| **Recommended owner / task** | KDOC-012 / KDOC-035 (storage architecture + storage user docs); KDOC-004 for backend registry authority. |

### F-007 — High — Generated documentation is stale and partially non-deterministic

| Field | Value |
|---|---|
| **Severity** | High |
| **Exact document(s)** | `docs/api_generated/module_structure.md`; `docs/api_generated/dependencies.md`; `docs/api_generated/doc_status.md`; `docs/api_generated/examples_index.md`; `docs/api_generated/README.md` |
| **Stale / broken claims** | (1) `module_structure.md` header: **Last updated: 2025-10-29T04:09:56.898549**. (2) `dependencies.md`: **2025-10-29 04:10:27 UTC**. (3) `doc_status.md` and `examples_index.md` contain the **literal** template string `$(date -u +"%Y-%m-%d %H:%M:%S UTC")` rather than an expanded timestamp. (4) `doc_status.md` claims **747** Python modules and **80** documentation files — both false for the current tree. (5) README claims weekly auto-maintenance produces current output. |
| **Contradicting evidence** | (1) `find ipfs_kit_py -name '*.py' \| wc -l` → **1111** at audit time. (2) `find docs -name '*.md' \| wc -l` → **398**. (3) `module_structure.md` has on the order of **~235** `###` section headers vs 1111 modules. (4) Generator workflow exists: `.github/workflows/auto-doc-maintenance.yml` (`cron: '0 9 * * 1'`, writes `module_structure.md` / `doc_status.md`). Committed outputs were not refreshed to 2026-08-03. (5) Planning doc already flagged October 2025 generation (`docs/documentation_plan.md` §1.1). |
| **Recommended owner / task** | KDOC-052 / KDOC-G060 generated-doc contract; KDOC-029 toolchain ADR for whether generated output is authoritative. |

### F-008 — High — Dual documentation site workflows are non-reproducible / mutually conflicting

| Field | Value |
|---|---|
| **Severity** | High |
| **Exact document(s)** | Workflows (behavior contracts): `.github/workflows/docs.yml`, `.github/workflows/pages.yml`; implied by `docs/api_generated/README.md` maintenance section and any "GitHub Pages docs" claims |
| **Stale / unsafe claim pattern** | That CI builds a durable Sphinx or MkDocs site from the committed docs tree |
| **Contradicting evidence** | (1) `docs.yml` runs `sphinx-build -b html . _build/html` after `cd docs`, but **`docs/conf.py` is absent** (and no `docs/index.rst`). (2) `pages.yml` installs MkDocs, then **writes generated API pages into `docs/api/`** via an inline Python script (`generate_api_docs('ipfs_kit_py', 'docs/api')`), which would collide with hand-maintained `docs/api/api_reference.md`, `cli_reference.md`, `core_concepts.md`, `high_level_api.md`. (3) No committed `mkdocs.yml` at repository root. (4) KDOC-029 preconditions explicitly call for this audit to record missing Sphinx config and ephemeral MkDocs behavior. |
| **Recommended owner / task** | KDOC-029 (`docs/architecture/decisions/0009-documentation-site-toolchain.md`). |

### F-009 — High — Async architecture guide documents AnyIO APIs that do not exist

| Field | Value |
|---|---|
| **Severity** | High |
| **Exact document(s)** | `docs/development/async_architecture.md` (Direct Replacements table and examples) |
| **Stale claims** | Maps `async_io.gather` → `anyio.gather`, `async_io.create_task` → `anyio.create_task`, `async_io.TimeoutError` → `anyio.TimeoutError` |
| **Contradicting evidence** | On the audit environment with AnyIO importable: `getattr(anyio, 'gather')`, `getattr(anyio, 'create_task')`, and `getattr(anyio, 'TimeoutError')` are all **missing**. Present APIs include `anyio.create_task_group`, `anyio.fail_after`, `anyio.sleep`, `anyio.run`, `anyio.get_current_task`, `anyio.to_thread.run_sync`. Planning doc §1.1 already cites this file for recommending APIs AnyIO does not provide. |
| **Recommended owner / task** | KDOC-016 / async & optional-dependency architecture guide; examples must be checked against installed AnyIO. |

### F-010 — High — High-level API docs omit package/stub vs large-module load contract

| Field | Value |
|---|---|
| **Severity** | High |
| **Exact document(s)** | `docs/api/high_level_api.md`; `docs/api/core_concepts.md`; root `README.md` examples using `from ipfs_kit_py.high_level_api import IPFSSimpleAPI` |
| **Stale claim pattern** | Single file `ipfs_kit_py/high_level_api.py` is the straightforward home of a full `IPFSSimpleAPI` |
| **Contradicting evidence** | (1) `importlib.util.find_spec('ipfs_kit_py.high_level_api').origin` resolves to **`ipfs_kit_py/high_level_api/__init__.py`** (package), not the sibling `high_level_api.py`. (2) Package `IPFSSimpleAPI` is a deferred-load wrapper that may fall back to a stub with `available = False` if legacy load fails (`high_level_api/__init__.py`). (3) Orphaned/parallel files remain: `high_level_api.py` (~553KB, 132 methods on class), `high_level_api_updated.py`, `high_level_api_improved.py`, `high_level_api_fixed.py`, `fixed_high_level_api.py`, plus `*.new` / `*.fixed` variants. |
| **Recommended owner / task** | KDOC-031 (Python / high-level API docs) + KDOC-004 (mark canonical vs compatibility modules). |

### F-011 — Medium — Primary navigation still promotes historical completion reports as current guidance

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Exact document(s)** | `docs/index.md`; `docs/README.md`; `docs/DOCUMENTATION_INDEX.md`; `docs/guides/DOCUMENTATION_GUIDE.md` |
| **Stale claim pattern** | Large sets of `*COMPLETE*`, `*SUMMARY*`, `*FINAL*` implementation reports linked as if they were current architecture or operator guides |
| **Contradicting evidence** | (1) July DOC-KIT campaign systematically linked `docs/implementation/*` completion reports into those four surfaces (example commit `fecfe72f`). (2) `find docs \( -name '*COMPLETE*' -o -name '*SUMMARY*' \)` → **134** paths. (3) `docs/implementation/` alone holds **67** Markdown files, overwhelmingly phase/completion reports. (4) Authority model in `docs/documentation_plan.md` §3.1 requires Historical material to be excluded from current recommendations. |
| **Recommended owner / task** | KDOC-041 (history boundary) then KDOC-060 (single navigation path). |

### F-012 — Medium — Competing documentation indexes with divergent quick-start truth

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Exact document(s)** | `docs/index.md` (234 lines); `docs/README.md` (728 lines); `docs/DOCUMENTATION_INDEX.md` (348 lines); `docs/guides/DOCUMENTATION_GUIDE.md` (311 lines) |
| **Stale claim pattern** | Multiple "start here" authorities; e.g. `docs/README.md` routes new users to `QUICK_REFERENCE.md` while `docs/index.md` routes to a broken cluster launcher; `DOCUMENTATION_INDEX.md` catalogs project completion reports first |
| **Contradicting evidence** | Combined ~1,621 lines across four indexes (planning estimate ~1,400 already noted in `docs/documentation_plan.md` §1.1). Content is not merely duplicated: **F-001** exists in `docs/index.md` but not in root `README.md` / `installation_guide.md`. |
| **Recommended owner / task** | KDOC-060; inventory support from KDOC-001. |

### F-013 — Medium — Empty external/vendor documentation directories remain in the corpus

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Exact document(s) / paths** | Empty directories (0 files each at audit): `docs/ipfs-docs/`, `docs/ipfs_cluster/`, `docs/ipfsspec/`, `docs/lassie/`, `docs/libp2p-universal-connectivity/`, `docs/libp2p_docs/`, `docs/lighthouse-python-sdk/`, `docs/mcp-python-sdk/`, `docs/storacha_specs/`, `docs/filesystem_spec/` |
| **Stale claim pattern** | Tree layout implies vendored or gitlinked upstream documentation is present |
| **Contradicting evidence** | `find <dir> -type f \| wc -l` is **0** for each path above. No external content was fetched (per evidence policy). |
| **Recommended owner / task** | KDOC-001 inventory classification + KDOC-046 external boundary; do not count these as authored product docs. |

### F-014 — Medium — Project completion / coverage milestone docs conflict with each other and with open roadmaps

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Exact document(s)** | `docs/project/FINAL_PROJECT_COMPLETION.md`; `docs/project/PROJECT_COMPLETION_SUMMARY.md`; `docs/PHASE6_FINAL_SUMMARY.md`; `docs/FINAL_TEST_COVERAGE_REPORT.md`; `docs/FINAL_COMPREHENSIVE_PR_SUMMARY.md`; `docs/100_PERCENT_COVERAGE_ROADMAP.md`; `docs/PATH_TO_100_PERCENT_COVERAGE.md` |
| **Stale claim pattern** | Simultaneous "project 100% complete" language and open "path to 100% coverage" roadmaps with feature coverage still listed well below 100% (e.g. S3 33%, GraphRAG 55% in roadmap tables) |
| **Contradicting evidence** | (1) `docs/FINAL_COMPREHENSIVE_PR_SUMMARY.md` itself records **~63% overall** and unchecked "100% coverage" milestones while also marketing production-ready completeness. (2) `docs/100_PERCENT_COVERAGE_ROADMAP.md` Milestone 8 "100% coverage" is unchecked. (3) `pytest.ini` still sets `minversion = 3.8` while packaging requires `>=3.12` — a process/doc/tooling skew. (4) No usable package-wide `coverage.json` totals were present at audit time; therefore this finding **does not invent a current coverage percent**. |
| **Recommended owner / task** | KDOC-041 classify completion reports as Historical; testing guides refreshed under KDOC-039; never cite completion banners as live coverage proof. |

### F-015 — Medium — Installation extras and installer paths are only partially aligned

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Exact document(s)** | `docs/installation_guide.md`; `docs/INSTALLER_DOCUMENTATION.md`; `docs/QUICK_REFERENCE.md` |
| **What is current** | Python **3.12+** requirement matches `pyproject.toml` `requires-python = ">=3.12"` and `setup.py` `python_requires='>=3.12'` (Feb Critical #1 is fixed here). Cluster script path uses `tools/`. Package import name `ipfs_kit_py` is used for pip examples. |
| **Residual risks** | (1) `install_ipfs.py` at repo root is a **compatibility shim** (300 bytes) redirecting to `ipfs_kit_py.install_ipfs` — docs that show only root script invocation should state opt-in binary install policy (`IPFS_KIT_AUTO_INSTALL_BINARIES` noted in package `__init__`). (2) `pytest.ini` `minversion = 3.8` can still mislead contributors about supported Python. (3) Feb audit marked several installation fixes complete in its checklist, but that checklist is itself historical and not a live verification receipt. |
| **Recommended owner / task** | KDOC-030 (installation + quick reference) with packaging metadata as authority. |

### F-016 — Low — `docs/api/cli_reference.md` package naming vs distribution name

| Field | Value |
|---|---|
| **Severity** | Low |
| **Exact document(s)** | `docs/api/cli_reference.md` (opening paragraphs use `ipfs-kit-py`) |
| **Contradicting evidence** | Packaging name is `ipfs_kit_py` (`pyproject.toml` / `setup.py`); console script is `ipfs-kit`. Hyphenated `ipfs-kit-py` is not the setuptools/project name in-tree. |
| **Recommended owner / task** | KDOC-032 when CLI docs are rewritten. |

### F-017 — Low — Status banners claiming "Production Ready" on mixed-maturity pages

| Field | Value |
|---|---|
| **Severity** | Low |
| **Exact document(s)** | Examples: `docs/index.md`, `docs/reference/storage_backends.md` status callouts |
| **Contradicting evidence** | Same pages link to ARCHIVE status reports for "current implementation status" (`docs/ARCHIVE/status-reports/MCP_DEVELOPMENT_STATUS.md`) and omit newer subsystems (Iroh preview flags in `CHANGELOG.md`). Banner language is not backed by a dated verification receipt on those pages. |
| **Recommended owner / task** | KDOC-005 / KDOC-006 lifecycle & claim standard (provenance and confidence labels). |

---

## 4. Prioritized remediation map (owners / tasks)

| Priority | Findings | Recommended task(s) | Outcome |
|---|---|---|---|
| P0 | F-001, F-002, F-003 | KDOC-002, KDOC-004, KDOC-014, KDOC-030, KDOC-060 | Correct primary entry commands; rank MCP authorities |
| P0 | F-004, F-005, F-010 | KDOC-031, KDOC-032, KDOC-004 | CLI/API docs match importable surfaces |
| P1 | F-006 | KDOC-012, KDOC-035, storage ADR if needed | Backend registry + Iroh in storage story |
| P1 | F-007, F-008 | KDOC-029, KDOC-052 / KDOC-G060 | Reproducible docs toolchain + generated-doc contract |
| P1 | F-009 | KDOC-016 | Async guide matches AnyIO |
| P2 | F-011, F-012, F-014 | KDOC-041, KDOC-060 | Historical boundary; single nav path |
| P2 | F-013, F-015 | KDOC-001, KDOC-046, KDOC-030 | External placeholders; install polish |
| P3 | F-016, F-017 | KDOC-005, KDOC-032 | Naming and claim-banner discipline |

---

## 5. Documentation change triggers (implementation → docs)

Use this table when source changes; it is derived from contradictions above, not from vague freshness windows.

| Implementation change | Docs that must be reviewed | Evidence hook |
|---|---|---|
| `[project.scripts]` or console entry points in `pyproject.toml` | Installation, CLI reference, MCP quick start, package `__init__` docstring | Packaging metadata |
| Add/remove CLI subparsers in `cli.py` / `unified_cli_dispatcher.py` | `docs/api/cli_reference.md`, operator quick reference | Parser registration |
| MCP server entry module moves | MCP guides, systemd units, deployment docs, generated module map | `ipfs_kit_py/mcp_server/server.py:main` |
| Backend plugin registration / `ipfs_kit.backends` entry points | `docs/reference/storage_backends.md`, storage architecture, Iroh docs | `backend_registry.py` |
| Iroh enablement stage changes | `docs/iroh/*`, CHANGELOG, storage overview, release notes | `iroh.enabled` / readiness ledger |
| High-level API package layout or stub load path | `docs/api/high_level_api.md`, README examples | `find_spec('ipfs_kit_py.high_level_api')` |
| AnyIO public usage patterns | `docs/development/async_architecture.md`, migration guides | Import check against installed AnyIO |
| WAL / journal CLI surface | CLI reference; **do not** trust `WAL_FS_JOURNAL_REMOVAL_COMPLETE.md` as current | Dispatcher `_add_wal_commands` / `_add_journal_commands` |
| Generated-doc workflow outputs | Entire `docs/api_generated/` | Header timestamps must be real ISO times on commit |
| Docs CI (Sphinx/MkDocs) config | Contributor docs, ADR 0009, Pages README claims | Presence of `docs/conf.py` / `mkdocs.yml` |
| Python version floor | Installation guide, `pytest.ini` minversion, badges | `requires-python` |

---

## 6. Family-level freshness risk summary

| Docs family | Approx. scale (audit) | Freshness risk | Proposed authority class (pending KDOC-001) | Notes |
|---|---|---|---|---|
| Root entry (`README.md`, `docs/index.md`, `docs/README.md`, indexes) | 4 major + badges | **Critical** | Canonical (must be single) | Conflicting quick starts; July link density |
| `docs/api/` | 4 hand-written | **High** | Canonical (after refresh) | CLI/API drift |
| `docs/api_generated/` | 5 + huge module map | **High** | Generated | Oct 2025 / template stamps |
| `docs/architecture/` | 9 | **High** | Mixed Canonical / Historical | Pre-MCP++ / pre-Iroh; audits useful as evidence only |
| `docs/iroh/` | 19 | **Medium** (content newer; integration weak) | Canonical (subsystem) | Underlinked from primary nav |
| `docs/implementation/` | 67 | **High** (as "current") | **Historical** | Completion reports |
| `docs/status_reports/`, `docs/fixes/`, `docs/ARCHIVE/` | large | **High** if linked as current | **Historical** | Provenance only |
| `docs/migration/` | 8 | **Medium** | Historical / migration | Useful with dates |
| `docs/features/`, `docs/operations/`, `docs/deployment/`, `docs/ci-cd/` | many | **Medium–High** | Mixed | Verify per command before promoting |
| `docs/integration/` | 15 | **Medium** | Mixed | Integration counts (e.g. "36") need surface-matrix proof |
| `docs/testing/`, coverage milestone docs | 23 + root coverage reports | **Medium** | Historical + testing Canonical | Do not treat milestone banners as live coverage |
| `docs/reference/` | 13 | **High** for backends | Canonical (after refresh) | F-006 |
| `docs/guides/` | 10 | **Medium** | Mixed | `DOCUMENTATION_GUIDE.md` still integration-centric |
| Empty external dirs | 10 dirs | **Medium** | External placeholders | Zero files |
| Embedded `docs/py-ipld-*` | 3 snapshots | **Low** (boundary) | External / snapshot | Not authored product docs |
| Program control (`documentation_plan.md`, objectives, todo) | 3 | **Current** | Program meta | Protected; not product user docs |

---

## 7. Relationship to sibling Wave 0 outputs

| Artifact | Role relative to this audit |
|---|---|
| `docs/audits/DOCUMENTATION_INVENTORY.md` (KDOC-001) | Full path inventory, owners, dispositions; this audit supplies **freshness risk evidence** for classification |
| `docs/audits/PUBLIC_SURFACE_MATRIX.md` (KDOC-002) | Must resolve F-002/F-003/F-004/F-010 with entry path × status rows |
| `docs/architecture/SOURCE_OF_TRUTH_MAP.md` (KDOC-004) | Must record competing MCP, API, backend, and cluster families as unresolved where evidence demands |
| Lifecycle / claim standards (KDOC-005/006) | Must ban undated "Production Ready" banners without verification receipts (F-017) |

---

## 8. Acceptance self-check (KDOC-003)

| Acceptance criterion | Status |
|---|---|
| Findings include **severity** | Yes — Critical / High / Medium / Low on F-001…F-017 |
| Findings include **exact document** paths | Yes |
| Findings include **contradicting source/test/history evidence** | Yes — packaging, source paths, Git commits, workflow files, import checks |
| Findings include **recommended owner/task** | Yes — KDOC task IDs |
| No vague unsupported freshness claims | Yes — every claim ties to a path, command result, or commit; no "probably outdated" without evidence |
| Audit date **2026-08-03** present | Yes (this document) |
| Output path `docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md` | Yes |

---

## 9. Appendix A — Evidence snapshot (2026-08-03)

```text
commit:            46fd3459
docs/**/*.md:      398
docs/** (files):   452
ipfs_kit_py/**/*.py: 1111
test_*.py (tests/ + ipfs_kit_py/tests): 874 files discovered by name
package version:   0.3.0
requires-python:   >=3.12
console scripts:   ipfs-kit, ipfs-kit-mcp, ipfs-kit-mcp-tools,
                   ipfs-kit-iroh, ipfs-kit-iroh-ops,
                   ipfs-kit-iroh-diagnostics, ipfs-kit-iroh-manifest,
                   ipfs-kit-iroh-interop
module_structure:  Last updated 2025-10-29T04:09:56.898549
Feb overhaul doc:  docs/project/COMPREHENSIVE_DOCUMENTATION_OVERHAUL.md (2026-02-02)
Feb audit doc:     docs/project/DOCUMENTATION_AUDIT_FINDINGS.md (2026-02-02)
July DOC-KIT:      164 commits (2026-07-24..2026-07-25), link-addition pattern
docs.yml:          sphinx-build without docs/conf.py
pages.yml:         mkdocs + generates into docs/api/
auto-doc-maintenance.yml: cron 0 9 * * 1 present
```

## 10. Appendix B — Explicit non-findings

The following were checked and are **not** filed as freshness defects:

- **Python 3.12 requirement in `docs/installation_guide.md`** — matches packaging (Feb Critical #1 resolved in that file).
- **Root `README.md` cluster path** — uses `tools/start_3_node_cluster.py` correctly (contrast F-001).
- **Iroh docs directory existence** — `docs/iroh/` is populated (19 Markdown files); the defect is integration into primary backend/nav narratives (F-006), not absence of the family.
- **Presence of `.github/workflows/auto-doc-maintenance.yml`, `docs.yml`, `pages.yml`** — workflows exist; defects are reproducibility and output freshness (F-007, F-008), not missing workflow files.

---

*End of KDOC-003 freshness and implementation-change audit — 2026-08-03.*
