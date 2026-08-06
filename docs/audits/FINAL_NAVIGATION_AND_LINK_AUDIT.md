# Final Navigation, Links, Examples, and Claim Audit

| Field | Value |
|---|---|
| **Task** | KDOC-061 |
| **Goal** | KDOC-G080 |
| **Track** | integration |
| **Audit date (UTC)** | 2026-08-04 |
| **Repository commit** | `2a3ce6f30a2c0710ef3b9e9675b78957645c3c2c` |
| **Tree id** | `c037328a49daf5a1df375e99821bf4eb76f6c0dd` |
| **Depends on** | KDOC-060 (exclusive navigation surfaces present and role-labeled) |
| **Conflict policy** | Audit merged tree only. This task **writes only** this report. Findings that need document edits are recorded as **repairs/follow-ups** for their owning task or document owner — they are not applied here. |
| **Package version (packaging)** | `0.3.0` (`pyproject.toml`) |
| **Package `__version__` (runtime)** | `0.2.0` (`ipfs_kit_py/__init__.py`) — known conflict **C-VER**; surfaced in Current install/quick-ref, not re-opened as a navigation block |
| **Scope** | Final static audit of exclusive documentation navigation, local links/anchors on those surfaces and first-hop Current targets, path/symbol/entry-point claims reachable from navigation, safe examples/help smoke, status/provenance labels, archive isolation, generated drift labels, sensitive-pattern scan on nav surfaces, and unresolved-decision visibility. |
| **Exclusions** | External HTTP(S) link liveness (no network fetch). Full corpus re-crawl of every historical/ARCHIVE Markdown file. Submodule/gitlink content not present in the worktree. Runtime install of optional extras or daemon bring-up. Marking backlog items complete. Editing product docs (out of edit policy for this task). |

## Blocking findings: 0

No blocking defects remain on the exclusive navigation surfaces against the evidence collected at the bound commit. Non-blocking warnings are listed in §6 with **owners**. Residual product-doc drift outside navigation is tracked as follow-up, not as a navigation gate failure.

---

## 1. Purpose and method

This report is the **KDOC-061** final gate for navigation, links, examples, and claim hygiene after exclusive navigation (KDOC-060). It answers:

1. Do the four exclusive navigation surfaces exist, declare non-competing roles, and resolve every local Markdown target?
2. Are install/start/entry-point claims on those surfaces and primary Current first hops consistent with packaging and the tree?
3. Are Historical / Generated / External / Proposed materials labeled and not promoted as how-to from navigation?
4. Are open owner decisions (`U-*`, `C-*`, **Proposed** ADRs) visible rather than hidden?
5. Do examples on primary Current paths avoid hardcoded secrets and known-stale entry scripts?
6. What warnings remain, who owns them, and what follow-ups exist before KDOC-062 scorecard / program close?

### 1.1 Severity definitions (this audit)

| Severity | Meaning | Gate impact |
|---|---|---|
| **Blocking** | Broken local link on an exclusive navigation surface; install/start command on a navigation surface that fails against the tree; competing start-here authority; ARCHIVE/COMPLETE promoted as Current how-to from navigation; hardcoded secrets in navigation or primary quick-start examples. | Must be **0** for acceptance. |
| **Warning** | Soft defects (anchor slug mismatch, first-hop internal anchor drift, known labeled version/runtime conflicts, residual claims **outside** exclusive nav, Proposed ADR majority). Document opens; operator is not given a false primary entry path. | Allowed if **owner** is named. |
| **Info** | Counts, role model confirmation, positive controls. | Informational only. |

### 1.2 Exclusive navigation surfaces (in scope)

| Surface | Role (as declared) | Class |
|---|---|---|
| `docs/index.md` | Sole concise start-here landing | Current (nav) |
| `docs/README.md` | Complete repository map (not a second landing) | Current (nav) |
| `docs/DOCUMENTATION_INDEX.md` | Structured catalog / lookup only | Current (nav catalog) |
| `docs/architecture/README.md` | Architecture + ADR reading order only | Current (nav) |

Primary first-hop Current companions also inspected for entry claims and example safety (not exclusive-nav rewrite targets): `docs/installation_guide.md`, `docs/QUICK_REFERENCE.md`, `docs/guides/DOCUMENTATION_GUIDE.md`, `docs/architecture/RUNTIME_AND_ENTRYPOINTS.md`, `docs/architecture/SOURCE_OF_TRUTH_MAP.md`, `docs/api/*` references linked from nav, `docs/api_generated/README.md` (Generated boundary).

---

## 2. Reproducible evidence commands

Commands below were run on **2026-08-04** against commit `2a3ce6f30a2c0710ef3b9e9675b78957645c3c2c`. Offline assumption: `IPFS_KIT_AUTO_INSTALL_BINARIES=0` for doc checks (no binary fetch required for this audit).

```bash
# Bind commit / tree
git rev-parse HEAD              # 2a3ce6f30a2c0710ef3b9e9675b78957645c3c2c
git rev-parse HEAD^{tree}       # c037328a49daf5a1df375e99821bf4eb76f6c0dd

# Corpus size
find docs -name '*.md' | wc -l  # observed: 438
find docs -type f | wc -l       # observed: 492

# Packaging authority
python3 -c "import tomllib; from pathlib import Path; d=tomllib.loads(Path('pyproject.toml').read_text()); print(d['project']['version']); print(d['project']['scripts']); print(d['project'].get('requires-python'))"
# version 0.3.0; requires-python >=3.12; scripts include ipfs-kit, ipfs-kit-mcp, ipfs-kit-mcp-tools, ipfs-kit-iroh*

# Runtime version drift (C-VER)
rg -n '__version__' ipfs_kit_py/__init__.py   # __version__ = "0.2.0"

# Entry files
test ! -f start_3_node_cluster.py && echo ROOT_CLUSTER_ABSENT
test -f tools/start_3_node_cluster.py && echo TOOLS_CLUSTER_OK
test ! -f final_mcp_server_enhanced.py && echo ROOT_MCP_SCRIPT_ABSENT
test -f ipfs_kit_py/cli.py && test -f ipfs_kit_py/mcp_server/server.py && echo PACKAGE_ENTRIES_OK

# Stale entry patterns must be absent from exclusive nav
rg -n 'final_mcp_server_enhanced|start_3_node_cluster\.py' \
  docs/index.md docs/README.md docs/DOCUMENTATION_INDEX.md docs/architecture/README.md \
  || echo 'NONE on nav'

# Console help smoke (importable CLI)
ipfs-kit --help
python3 -c "import ipfs_kit_py.cli, ipfs_kit_py.mcp_server.server, ipfs_kit_py.mcp_server.cli; print('imports_ok')"

# Local link check (logic used for this report): parse Markdown links [text](href)
# on the four nav surfaces; resolve relative to the source file; require target path exists.
# Observed: 462 local links on nav surfaces; 0 missing file targets.

# Generated stamps
head -8 docs/api_generated/README.md
head -8 docs/api_generated/module_structure.md
head -8 docs/api_generated/doc_status.md

# Open authorities visibility
rg -n 'U-[0-9]+|C-[A-Z]+|Proposed' docs/architecture/SOURCE_OF_TRUTH_MAP.md | head
rg -n 'Decision status' docs/architecture/decisions/*.md | head
```

---

## 3. Counts

| Metric | Count | Notes |
|---|---:|---|
| Docs Markdown files (`find docs -name '*.md'`) | 438 | Includes ARCHIVE, audits, api_generated, architecture |
| Docs files all types | 492 | |
| Exclusive navigation surfaces | 4 | index, README, DOCUMENTATION_INDEX, architecture/README |
| Local Markdown links on exclusive nav (sum) | 462 | index 100 · README 153 · DOCUMENTATION_INDEX 108 · architecture/README 101 |
| Missing **file** targets on exclusive nav | **0** | All path parts resolve in-tree |
| External links on exclusive nav | 0 | No http(s) deps on nav surfaces |
| Unique existing local first-hop targets from nav | 98 | Distinct resolved paths |
| Expanded link sample (nav + first-hop md set) | 1812 links / 90 files | Broader sample; see §5.1 for non-nav noise |
| Missing file targets in broader sample (real) | 0 | Apparent “missing” were ellipsis / placeholder demo links (see §5.1) |
| Soft anchor mismatches (broader sample) | 12 | Warning class; one on catalog → map (§6 W-001) |
| Packaging console scripts declared | 8 | `ipfs-kit`, `ipfs-kit-mcp`, `ipfs-kit-mcp-tools`, four `ipfs-kit-iroh*`, etc. |
| ADR decision records (0001–0009) | 9 | 2 **Accepted**, 7 **Proposed** (plus template) |
| Open `U-*` ids in SOURCE_OF_TRUTH_MAP | 18 | U-01 … U-18 |
| Named conflicts `C-*` in SOURCE_OF_TRUTH_MAP | 6 | C-CLI, C-FSSPEC, C-HLA, C-INSTALL, C-MCP, C-VER |
| Blocking findings | **0** | Gate |
| Warnings with owners | 5 | §6 |

### 3.1 Per-surface link totals

| Surface | Local OK | Missing path | External |
|---|---:|---:|---:|
| `docs/index.md` | 100 | 0 | 0 |
| `docs/README.md` | 153 | 0 | 0 |
| `docs/DOCUMENTATION_INDEX.md` | 108 | 0 | 0 |
| `docs/architecture/README.md` | 101 | 0 | 0 |
| **Total** | **462** | **0** | **0** |

---

## 4. Check results by concern

### 4.1 Canonical links and anchors

| Check | Result | Evidence |
|---|---|---|
| All exclusive-nav path targets exist | **Pass** | 462/462 path resolutions |
| No stale root cluster launcher on nav | **Pass** | `rg` empty for `start_3_node_cluster.py` / `final_mcp_server_enhanced` on four surfaces |
| Prior Critical F-001 (root `start_3_node_cluster.py` on `docs/index.md`) | **Cleared on nav** | Index no longer advertises root launcher; install/quick-ref use `tools/start_3_node_cluster.py` as optional lab helper only |
| Catalog deep-link to map §2.3 | **Warning** | `DOCUMENTATION_INDEX.md` → `README.md#23-operator--sre`; GFM-style slug for heading `### 2.3 Operator / SRE` is `#23-operator-sre` (file still opens; scroll may miss). See **W-001** |

### 4.2 Duplicate / competing navigation

| Check | Result | Evidence |
|---|---|---|
| Single concise landing | **Pass** | `docs/index.md` declares sole start-here; others explicitly renounce landing authority |
| Map vs catalog vs architecture hub roles | **Pass** | Headers + “Navigation roles” / “Authority model” tables on all four surfaces |
| QUICK_REFERENCE not second index | **Pass** | Listed as cheatsheet; not “start here” |
| ARCHIVE not start-here how-to | **Pass** | Index/README/catalog label ARCHIVE **Historical** and “not current guidance” |

### 4.3 Path / symbol / entry-point references

| Claim surface | Claim ranking | Tree / packaging truth | Result |
|---|---|---|---|
| Exclusive nav | Packaging/`pyproject.toml` outranks narrative | Scripts: `ipfs-kit` → `ipfs_kit_py.cli:sync_main`; `ipfs-kit-mcp` → `ipfs_kit_py.mcp_server.server:main` | **Pass** — nav defers to packaging |
| `docs/installation_guide.md` | Python ≥3.12; console scripts; lab helper under `tools/` | `requires-python >=3.12`; `tools/start_3_node_cluster.py` exists; root script absent | **Pass** |
| `docs/QUICK_REFERENCE.md` | Documents C-VER; `tools/` cluster helper | Matches measured drift and path | **Pass** |
| `ipfs-kit --help` | Dispatcher groups present | `mcp,daemon,services,autoheal,bucket,vfs,wal,pin,backend,journal,state` | **Pass** (smoke) |
| Import paths for MCP packaging family | `ipfs_kit_py.mcp_server.server` / `.cli` | Importable from worktree | **Pass** |
| Residual `final_mcp_server_enhanced` in package docstring | Outside exclusive nav | Still present in `ipfs_kit_py/__init__.py` | **Warning W-002** (not a nav block) |

### 4.4 Safe examples / help

| Check | Result | Evidence |
|---|---|---|
| Code fences on exclusive nav | **N/A / Pass** | Zero fenced command blocks on the four nav files (navigation only) |
| Sensitive pattern scan on exclusive nav | **Pass** | No AWS keys, PEM blocks, or `password=` / `api_key=` literal assignments |
| Install + quick-ref secret scan | **Pass** | Mentions of “secrets” are architecture/credential **guide links**, not embedded credentials |
| Stale entry scripts in install/quick-ref fences | **Pass** | No `final_mcp_server_enhanced`; cluster helper correctly under `tools/` |
| `ipfs-kit --help` | **Pass** | Exit 0; usage text coherent |

### 4.5 Status / provenance labels

| Check | Result | Evidence |
|---|---|---|
| Material class tables on all four nav surfaces | **Pass** | Current / Generated / Historical / External / Proposed defined consistently |
| Generated targets labeled when linked | **Pass** | `api_generated/*` linked as **Generated**; contract pointer to `audits/GENERATED_DOCUMENTATION_CONTRACT.md` |
| COMPLETE / campaign paths not recommended as Current | **Pass** | Explicit “Do not treat … COMPLETE … as production status” on index; catalog § Historical |

### 4.6 Archive isolation

| Check | Result | Evidence |
|---|---|---|
| ARCHIVE reachable only as Historical boundary | **Pass** | Links go to `ARCHIVE/README.md` or category dirs with **Historical** label |
| Implementation COMPLETE trees not start-here | **Pass** | Labeled Historical in map/catalog; not in “Start here (Current)” tables |

### 4.7 Generated drift

| Check | Result | Evidence |
|---|---|---|
| Generated tree carries contract banner | **Pass** | `docs/api_generated/*.md` headers: **Generated** authority; `Generated at: 2026-08-04T00:24:53Z`; contract KDOC-043 / GENERATED_DOCUMENTATION_CONTRACT |
| Navigation does not treat Generated as how-to authority | **Pass** | Role tables say reference only |
| Prior F-007 unexpanded `$(date …)` stamps | **Cleared in generated tree at this commit** | Current generator output uses expanded ISO timestamps (spot-check README, module_structure, doc_status) |

> Note: Generated inventories can still drift after the next code change; the **contract** and nav labels are the control. Regeneration remains an owning-task concern (KDOC-046 / maintenance), not a navigation blocking defect.

### 4.8 Unresolved decision visibility

| Check | Result | Evidence |
|---|---|---|
| Nav points to SOURCE_OF_TRUTH_MAP and ADRs | **Pass** | All four surfaces link open authorities / decisions |
| `U-*` / `C-*` inventory exists | **Pass** | 18 unknowns, 6 named conflicts including **C-VER**, **C-MCP** |
| ADR **Proposed** not hidden | **Pass** | architecture/README states Proposed must not be cited as settled production policy; 7 of 9 ADRs remain Proposed |
| Program-control files not product how-to | **Pass** | index notes plan/objectives/todo as operator-protected, not navigation targets |

---

## 5. Broader sample notes (non-blocking)

A first-hop expansion over ~90 Markdown files (1812 links) was used to catch navigation-adjacent defects.

### 5.1 False-positive “missing” targets

These are **documentation examples of link syntax** or typographic ellipsis, not broken product links:

| Source | href | Classification |
|---|---|---|
| `docs/guides/DOCUMENTATION_GUIDE.md` | `../architecture/…` | Ellipsis placeholder in prose |
| `docs/architecture/STORAGE_BACKEND_SYSTEM.md` | `config` | Inline example fragment |
| `docs/development/DOCUMENTATION_VALIDATION.md` | `path`, `path#anchor` | Validation guide examples |

### 5.2 First-hop internal anchor soft misses (owners on content docs)

Examples observed (file opens; fragment may not scroll): glossary self-anchors with `content-address--…` vs heading slug; `SYSTEM_OVERVIEW` / `CONTENT_METADATA_VFS` references to a missing “change triggers” fragment; integration quick-start section ids; streaming guide SSE fragment; maintenance workflow ADR fragment. **Not exclusive-nav path breaks.** Tracked under **W-003**.

---

## 6. Findings

### 6.1 Blocking findings

**None.**

**Blocking findings: 0**

### 6.2 Warnings (each has an owner)

#### W-001 — Medium — Catalog deep-link slug for Operator / SRE

| Field | Value |
|---|---|
| **Severity** | Warning (Medium) |
| **Where** | `docs/DOCUMENTATION_INDEX.md` → `[README.md §2.3](README.md#23-operator--sre)` |
| **Issue** | Heading in `docs/README.md` is `### 2.3 Operator / SRE`. Common GFM slugization yields `#23-operator-sre` (punctuation stripped, spaces → `-`). The catalog uses `#23-operator--sre` (double hyphen). The **file** target resolves; in-page navigation may land at top of file. |
| **Why not blocking** | Path-level link works; section is still discoverable via map TOC; no install/start failure. |
| **Owner** | Exclusive navigation owner (**KDOC-060** residual / docs navigation maintainer). Fix: align fragment to `#23-operator-sre` on next nav touch. |
| **Follow-up** | FU-001 |

#### W-002 — Medium — Residual package docstring advertises missing root MCP script

| Field | Value |
|---|---|
| **Severity** | Warning (Medium) — residual of freshness **F-002** |
| **Where** | `ipfs_kit_py/__init__.py` (module docstring still contains `final_mcp_server_enhanced`) |
| **Issue** | Packaging entry is `ipfs-kit-mcp` → `ipfs_kit_py.mcp_server.server:main`. Root script `final_mcp_server_enhanced.py` is **absent**. Exclusive navigation and install guide do **not** advertise the stale path. |
| **Why not blocking** | Outside exclusive navigation surfaces and outside this task’s edit policy; nav correctly defers to `pyproject.toml`. |
| **Owner** | Package docstring / public surface owner (**KDOC-031** / API surface maintainers; conflict **C-MCP**). |
| **Follow-up** | FU-002 |

#### W-003 — Low — First-hop internal anchor drift in non-nav Current docs

| Field | Value |
|---|---|
| **Severity** | Warning (Low) |
| **Where** | Sample: `docs/architecture/GLOSSARY.md`, `SYSTEM_OVERVIEW.md`, `CONTENT_METADATA_VFS.md`, `docs/integration/INTEGRATION_QUICK_START.md`, `docs/reference/streaming_guide.md`, `docs/workflows/documentation-maintenance.md` |
| **Issue** | In-page or cross-heading fragments that do not match generated heading slugs (≈12 in the 90-file sample). |
| **Why not blocking** | Not exclusive-nav path failures; content remains reachable by file path. |
| **Owner** | Owning content document authors (architecture / integration / reference / workflows). Prefer fixing when those docs are next edited. |
| **Follow-up** | FU-003 |

#### W-004 — Info/Warning — Packaging vs runtime version conflict (C-VER)

| Field | Value |
|---|---|
| **Severity** | Warning (known conflict; labeled) |
| **Where** | `pyproject.toml` `0.3.0` vs `ipfs_kit_py.__version__` `0.2.0` |
| **Issue** | Agents may cite either number. |
| **Why not blocking** | Explicitly documented in `installation_guide.md` and `QUICK_REFERENCE.md`; tracked as **C-VER** in SOURCE_OF_TRUTH_MAP; nav does not invent a single false version. |
| **Owner** | Release / packaging owner (conflict **C-VER**; SOURCE_OF_TRUTH_MAP). |
| **Follow-up** | FU-004 |

#### W-005 — Info — Majority of ADRs remain Proposed

| Field | Value |
|---|---|
| **Severity** | Info / Warning (visibility, not a defect) |
| **Where** | `docs/architecture/decisions/0003`–`0009` **Proposed**; `0001`–`0002` **Accepted** |
| **Issue** | Many architecture authorities are intentionally undecided. |
| **Why not blocking** | Visible from architecture hub and SOURCE_OF_TRUTH_MAP; nav forbids treating Proposed as production policy. |
| **Owner** | Architecture decision owners / program operators (ADR authors; open `U-*` items). |
| **Follow-up** | FU-005 (acceptance path, not a nav repair) |

---

## 7. Disposition of prior freshness Criticals (navigation-relevant)

| Prior id | Topic | Status at this commit (nav gate) |
|---|---|---|
| F-001 | Root `start_3_node_cluster.py` on primary index | **Cleared on exclusive nav** — index/map do not use root path; tools path only in install/quick-ref as lab helper |
| F-002 | `final_mcp_server_enhanced` as MCP start | **Cleared on exclusive nav**; residual in package docstring → **W-002** |
| F-003 | Competing MCP families without ranking | **Nav-safe** — nav points at packaging + MCP architecture + ADR-0003 (**Proposed**); open **C-MCP** remains visible in SOURCE_OF_TRUTH_MAP |
| F-007 | Generated stamp / template drift | **Generated tree regenerated** with 2026-08-04 banners at this commit; nav labels Generated correctly |
| F-012 / competing indexes | Four indexes without exclusive roles | **Cleared by KDOC-060** role model; re-verified here |

Non-navigation content drift (CLI narrative vs dispatcher detail, storage backend counts, VFS runtime path prose, AnyIO guide APIs) remains **content-task / ADR** territory. It does not reopen the navigation gate when surfaces defer to packaging and label open conflicts.

---

## 8. Repairs and follow-ups

This task **does not** modify product documents (edit policy: `docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md` only). Recommended follow-ups:

| ID | Action | Owner | Priority | Blocks KDOC-061? |
|---|---|---|---|---|
| FU-001 | Fix catalog fragment to `README.md#23-operator-sre` (or add explicit HTML anchor on the map heading) | Navigation maintainer (KDOC-060 family) | P2 | No |
| FU-002 | Remove or rewrite `final_mcp_server_enhanced` from `ipfs_kit_py/__init__.py` docstring; align with `ipfs-kit-mcp` | API / package surface owner | P1 | No |
| FU-003 | Repair first-hop heading anchors listed in W-003 when those docs are next edited | Content owners | P3 | No |
| FU-004 | Resolve **C-VER** (`__version__` vs packaging) in a release change | Packaging / release owner | P1 | No |
| FU-005 | Advance **Proposed** ADRs (esp. MCP, site toolchain, cluster) via owner decisions | Architecture owners | P1 program | No |
| FU-006 | KDOC-062 final scorecard consumes this report’s commit binding and warning list | KDOC-062 | P0 next | No |

No in-scope repair was required to reach **Blocking findings: 0**.

---

## 9. Acceptance checklist (KDOC-061)

| Criterion | Met? |
|---|---|
| Report binds **commit** | Yes — `2a3ce6f30a2c0710ef3b9e9675b78957645c3c2c` |
| Report binds **commands** | Yes — §2 |
| Report binds **scope / exclusions** | Yes — header table + §1 |
| Report binds **counts** | Yes — §3 |
| Report binds **findings** | Yes — §6 |
| Report binds **repairs / follow-ups** | Yes — §8 |
| States **`Blocking findings: 0`** | Yes — header callout + §6.1 |
| Warnings have **owners** | Yes — W-001…W-005 |
| Output path | `docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md` |

### Validation commands (task contract)

```bash
test -s docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md && rg -q "Blocking findings: 0" docs/audits/FINAL_NAVIGATION_AND_LINK_AUDIT.md
```

---

## 10. Summary judgment

Exclusive navigation delivered by KDOC-060 is **coherent** at commit `2a3ce6f3`: four surfaces, non-competing roles, zero broken local path links, packaging-first entry ranking, Historical/Generated/Proposed isolation, and visible open decisions. Primary install/quick-ref paths no longer carry the February/July critical launcher defect on the landing page. Remaining issues are **owned warnings** (anchor slug, package docstring residual, content-level anchors, version conflict, Proposed ADRs) and are explicit inputs to **KDOC-062** rather than hidden blockers.

**Blocking findings: 0**
