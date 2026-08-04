# Generated Documentation Contract and Drift Gates

| Field | Value |
|---|---|
| Task | KDOC-043 — Specify the generated documentation contract and drift gates |
| Goal | KDOC-G060 — Repeatable freshness, generated-doc, and quality controls |
| Track | generated-docs |
| Authority class | **Program audit / contract** (not product user guidance; not generated output) |
| Contract date | 2026-08-04 |
| Tree baseline | Worktree evidence offline; re-measured package counts, packaging scripts, MCP tool registry, committed `docs/api_generated/` stamps |
| Depends on | KDOC-001 inventory, KDOC-003 freshness (F-007), KDOC-005 guide lifecycle, KDOC-029 toolchain ADR |
| Exclusive write target for this task | `docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md` only |
| Downstream exclusive owners | **KDOC-046** owns regeneration of `docs/api_generated/*`; **KDOC-052** owns broader offline documentation validation gates |

This document is the **machine-checkable contract** for generator-owned documentation under `docs/api_generated/` and for related **manifest drift** (module map, signatures, dependencies, examples, MCP/tool manifests). It does **not** regenerate outputs, edit workflows, or treat file presence as proof of freshness.

---

## 1. Purpose and non-goals

### 1.1 Purpose

1. Define what **Generated** authority means for this repository (plan §3.1).
2. Specify **deterministic** generation inputs, ordering, timestamps, and provenance headers so two offline runs on the same tree produce comparable artifacts.
3. Define **drift gates** that fail when module, signature, dependency, example, or tool manifests are stale relative to measured source/packaging evidence.
4. State **exclusions**: tracked backups, archive trees, broken/fixed variants, import-side-effect modules, and external/embedded snapshots are **never** public API and must not appear as supported surfaces in generated reference.
5. Record **current contradictions** in the weekly generator workflow and committed outputs so KDOC-046 / separately authorized workflow work can fix them without inventing maintainer site-toolchain decisions already reserved for ADR-0009.

### 1.2 Non-goals

| Non-goal | Owner / note |
|---|---|
| Hand-editing bodies under `docs/api_generated/` | Out of policy; regenerate only (KDOC-046) |
| Choosing MkDocs vs Sphinx vs no public site | ADR-0009 / KDOC-029 |
| Collapsing `docs/api/` vs `docs/api_generated/` | Unresolved owner decision (SOURCE_OF_TRUTH_MAP §10) |
| Fetching gitlinked or network documentation | Forbidden; see KDOC-044 external boundary |
| Claiming Sphinx/MkDocs config exists and works | F-008: dual workflows are not a durable offline site |
| Substituting generated inventories for conceptual guides | Plan §11 deliberate non-goal |
| Auto-merging generated PRs | Review required; fail-closed on drift, not silent overwrite of authored docs |

---

## 2. Authority model

### 2.1 Authority class: Generated

From `docs/documentation_plan.md` §3.1:

| Class | Meaning | Update rule |
|---|---|---|
| **Generated** | Deterministic output from code or packaging metadata | Never hand-maintained except generator templates; **drift must be detectable** |

Generated files are **reference inventories**, not canonical architecture, install, or operator guidance. Readers and agents must prefer:

1. executable behavior and focused tests;
2. packaging and entry-point metadata (`pyproject.toml`);
3. public source contracts, schemas, and docstrings;
4. accepted ADRs and current authored guides;

over raw module dumps or frozen tool counts printed in generated Markdown.

### 2.2 Ownership matrix

| Path / artifact | Role | Write policy | Drift owner |
|---|---|---|---|
| `docs/api_generated/README.md` | Generated index + provenance | Generator only | KDOC-046 + this contract |
| `docs/api_generated/module_structure.md` | Module / signature inventory | Generator only | Gate **G-MOD**, **G-SIG** |
| `docs/api_generated/dependencies.md` | Packaging dependency inventory | Generator only | Gate **G-DEP** |
| `docs/api_generated/examples_index.md` | Example path index | Generator only | Gate **G-EX** |
| `docs/api_generated/AGENT_GUIDE.md` | Compact agent reference derived from packaging + allowlist | Generator only | Gate **G-AGENT** |
| `docs/api_generated/doc_status.md` | Coverage metrics + run provenance | Generator only | Gate **G-STAT**, **G-HDR** |
| `docs/api/` | Hand-maintained API notes | Authors (not generator exclusive) | Must not be overwritten by `api_generated` workflow |
| `tools/generate_api_docs.py` | **Adjacent** MCP endpoint narrative generator | Separate contract; not owner of `api_generated/` | Do not conflate with weekly AST path |
| `.github/workflows/auto-doc-maintenance.yml` | Current weekly generator path | Workflow changes are **separately authorized** follow-ups | This contract records defects only |
| `.github/workflows/pages.yml` / `docs.yml` | Site / alternate API HTML paths | Not `api_generated` exclusive owners | ADR-0009 |
| `ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json` | Generated companion tool manifest | `python -m ipfs_kit_py.mcp_server.js_sdk.generate` | Gate **G-TOOL** (existing CI pattern in `mcp-server-ci.yml`) |
| `docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md` | This contract | KDOC-043 (this task) | Manual update when gates change |

### 2.3 What generated output is **not**

- Not a substitute for `docs/architecture/*` guides or ADRs.
- Not proof that a module is a supported public API merely because it was walked by `rglob('*.py')`.
- Not authority for version numbers (see surface matrix **C-VER**).
- Not authority for MCP tool totals when they disagree with live `TOOL_GROUPS` (matrix **C-MCP-TOOLS**).

---

## 3. Output set (required artifacts)

Every full regeneration (**mode: full**) MUST write or refresh the following paths under `docs/api_generated/`:

| Artifact | Primary inputs | Content obligations |
|---|---|---|
| `README.md` | Contract version, generator command, tree hash or commit if available | Must contain a line matching `Generated from` (KDOC-046 validation); list sibling artifacts; state **non-authority** of generated reference |
| `module_structure.md` | Active-module allowlist + static AST extract | Sorted packages/modules; public classes/functions with signatures; no unevaluated shell |
| `dependencies.md` | `pyproject.toml` `[project]` dependencies + optional-dependencies | Deterministic section order; version pins as declared; no invented “purpose” prose that contradicts packaging |
| `examples_index.md` | `examples/**/*.py` (and optional curated test demos) | Sorted relative paths; only existing files; exclude backups |
| `AGENT_GUIDE.md` | Console scripts, packaging name, allowlisted entry modules, measured MCP group list | Must cite packaging entry points; must **not** invent root-level launcher paths (F-001/F-002 class) |
| `doc_status.md` | Counts from the same run | Measured module/example/dep/tool counts; real ISO-8601 provenance; no literal `$(date …)` |

Optional HTML under `docs/api_generated/` produced by pdoc is **out of contract** for architecture program gates until ADR-0009 accepts a site toolchain. Prefer Markdown inventories as the durable committed surface.

---

## 4. Active-module allowlist and public-API scope

### 4.1 In-scope roots (default allowlist)

Generation that claims “package API” MUST start from packaging-discovered packages only:

| Include | Rationale |
|---|---|
| `ipfs_kit_py/` package tree as declared by setuptools (`[tool.setuptools.packages.find]`) | Distributed package authority |
| Public modules under that tree that parse as Python and are not excluded below | Inventory surface |

Packaging evidence (measured): console scripts in `pyproject.toml` include `ipfs-kit`, `ipfs-kit-mcp`, `ipfs-kit-mcp-tools`, `ipfs-kit-iroh`, `ipfs-kit-iroh-ops`, `ipfs-kit-iroh-diagnostics`, `ipfs-kit-iroh-manifest`, `ipfs-kit-iroh-interop`.

### 4.2 Hard exclusions (never public API in generated output)

The following MUST be excluded from module inventories, signature tables, agent “key entry points,” and example indexes labeled as supported API. Presence on disk is **not** support.

| Exclusion class | Patterns / paths | Why |
|---|---|---|
| **Tracked backups** | Repo-root `backup/`, `backup/**` | Historical patches and clutter; not product API |
| **Archive trees** | Repo-root `archive/`, `docs/ARCHIVE/**` | Provenance only (Historical class) |
| **External / embedded snapshots** | `docs/py-ipld-*`, uninitialized gitlinks under `docs/`, vendored third-party trees outside packaging | External ownership (KDOC-044); not `ipfs_kit_py` public API |
| **Broken / fixed / legacy filename variants** | `*.broken`, `*.corrupted_backup`, `*.deprecated_backup`, `*_fixed.py`, `*_improved.py`, `*_updated.py`, `*_old.py`, `*.fixed`, `*.new` | Compatibility clutter (SOURCE_OF_TRUTH_MAP §11); matrix **C-HLA** |
| **Non-packaged parallel trees** | Repo-root `mcp/` shims, `servers/` standalone launchers, non-packaged `src/` | Not in setuptools package find; matrix **C-MCP-TREES**, packaging note on `src/` |
| **Caches and VCS noise** | `__pycache__/`, `*.pyc`, `.git/` | Non-source |
| **Import-side-effect modules** (label, do not “support”) | Modules whose import starts daemons, downloads binaries, or requires live network when executed at import time | Static AST extract only; never `import` during generation with `IPFS_KIT_AUTO_INSTALL_BINARIES=0` |
| **Test trees as API** | `tests/`, `**/tests/**`, `test_*.py` as module API rows | May appear only under a clearly labeled “test examples” section if indexed |
| **pdoc HTML side dumps** | Uncommitted or ad-hoc HTML beside Markdown contract files | Not a drift gate input unless site toolchain is accepted |

### 4.3 Compatibility layers (document, do not promote)

Compatibility modules **inside** `ipfs_kit_py/` (for example `compat.py`, lazy `__getattr__` shims, parallel `ipfs_kit_py/mcp/` vs `mcp_server/`) may appear in the module map with an explicit **status** column:

| Status label | Meaning |
|---|---|
| `canonical` | Packaging or accepted architecture default |
| `compatibility` | Supported alternate; not design center |
| `historical` | Retained for imports/tests; not recommended |
| `excluded` | Matched hard exclusion; must not be listed |

Generators MUST NOT flatten all paths into an undifferentiated “API” list that implies equal support. When status is unknown, label **unresolved** and cite the public surface matrix conflict id if any.

### 4.4 Active allowlist algorithm (normative)

```text
candidates = all *.py under packaging package roots
candidates -= hard exclusions (§4.2)
candidates -= paths matching exclusion globs
sort by POSIX relative path ascending
for each path:
  parse with ast.parse (no import)
  if parse fails: record failure; fail closed in check mode (§8)
  extract module docstring, public classes, public functions (name not starting with '_')
  attach status from allowlist table or default 'inventory'
emit module_structure.md in deterministic package order
```

Default package root for this repository: `ipfs_kit_py/`.

Do **not** walk repository root, `backup/`, `archive/`, `docs/`, `examples/` (except for the separate examples index), or external snapshots for the module/signature manifests.

---

## 5. Deterministic generation requirements

All of the following are **required** for contract-compliant generation. Current workflow defects that violate them are listed in §10.

### 5.1 Inputs (only these)

| Input | Use |
|---|---|
| Packaging package roots + allowlist | Module and signature inventory |
| `pyproject.toml` | Dependencies, optional extras, console scripts, package version for provenance |
| `examples/**/*.py` (sorted) | Examples index |
| `ipfs_kit_py/mcp_server/tools/__init__.py` `TOOL_GROUPS` (static parse or offline import of registry module only) | Tool counts for agent guide / status |
| `ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json` | Tool manifest drift comparison |
| Generator / contract version string | Provenance header |
| Optional: `git rev-parse HEAD` when `.git` present | Tree identity; omit rather than invent |

### 5.2 Deterministic ordering

| Artifact | Order rule |
|---|---|
| Modules | Relative path lexicographic (POSIX, `/` separators) |
| Packages in overview | Top-level segment lexicographic, then modules sorted |
| Classes / functions within a module | Source appearance order **or** name lexicographic — pick one and keep it stable; prefer **name lexicographic** for cross-run stability when line numbers shift without semantic change |
| Dependencies | Core list order as in `pyproject.toml`; optional-dependency groups sorted by group name, then requirement strings |
| Examples | Relative path lexicographic |
| Tools | Group name lexicographic, then tool name lexicographic |

### 5.3 Timestamps and provenance headers

Every generated Markdown file MUST start with a provenance block that includes:

1. Title.
2. A single provenance line containing a **real** expanded timestamp in UTC ISO-8601 (example: `2026-08-04T12:00:00Z`), **or** a content-addressed generation id derived from sorted input hashes (preferred for bit-stable diffs).
3. Generator identity (workflow name or script path + contract version).
4. Explicit sentence that the file is **Generated** authority and not hand-edited.

**Forbidden:**

- Literal unevaluated shell fragments such as `$(date -u +"%Y-%m-%d %H:%M:%S UTC")` in committed output (freshness **F-007**).
- Wall-clock timestamps that differ on every run **without** a `--check` mode that ignores the timestamp field when comparing (if wall-clock is used, check mode must strip or normalize the provenance line before diff).

**Preferred deterministic approach:**

```text
content_digest = sha256(canonical serialization of extracted manifests)
header_time = SOURCE_DATE_EPOCH if set, else omit clock and print content_digest only
```

When `SOURCE_DATE_EPOCH` is set, format it as UTC ISO-8601. This keeps generation **deterministic** across machines for the same tree.

### 5.4 Environment constraints

| Variable / setting | Required value during generate/check |
|---|---|
| `IPFS_KIT_AUTO_INSTALL_BINARIES` | `0` |
| Network | Not required; generation must succeed offline |
| Python | `>=3.12` matching packaging |
| Working directory | Repository root |

### 5.5 Failure policy during generation

| Condition | Generate mode | Check mode |
|---|---|---|
| AST parse failure on allowlisted module | **Fail closed** (non-zero exit); list paths | Fail |
| Missing `pyproject.toml` | Fail | Fail |
| Zero modules discovered under allowlist | Fail (likely wrong cwd) | Fail |
| Optional tool registry unreadable | Emit `tools: unavailable` and fail **G-TOOL** if gate enabled | Fail if gate enabled |
| pdoc HTML generation fails | Must not block Markdown contract artifacts | N/A |

---

## 6. Manifest schemas (what “stale” means)

Drift gates compare **committed generated artifacts** (or companion manifests) to **freshly extracted expected manifests**. A gate fails when the normalized expected manifest ≠ normalized committed manifest.

### 6.1 Module manifest (`G-MOD`)

| Field | Source |
|---|---|
| `path` | Relative path under package root |
| `status` | allowlist / compatibility label |
| `has_docstring` | boolean |
| `class_names` | sorted public class names |
| `function_names` | sorted public function names |

**Stale when:** a module appears/disappears, or public class/function sets change, relative to `module_structure.md` headings/lists.

**Evidence commands (offline):**

```bash
find ipfs_kit_py -name '*.py' ! -path '*/__pycache__/*' | wc -l
# Measured baseline at contract date: 1111 paths under ipfs_kit_py (includes tests/variants;
# allowlisted API count will be lower after §4.2 filters).
test -s docs/api_generated/module_structure.md
head -n 5 docs/api_generated/module_structure.md
```

**Current defect:** header `Last updated: 2025-10-29T04:09:56.898549` (F-007); inventory claims under-count modules relative to 2026 tree.

### 6.2 Signature manifest (`G-SIG`)

| Field | Source |
|---|---|
| `qualname` | `module:Class.method` or `module:function` |
| `signature` | AST-derived parameter list (names, defaults presence, annotations as source strings when present) |
| `kind` | function / async function / method |

**Stale when:** public signature text for an allowlisted symbol changes but generated docs still show the old parameter list (or omit the symbol).

Implementation note: the 2025-10 workflow only listed names + docstring first lines. Contract-compliant regeneration (**KDOC-046**) MUST include **parameter signatures** for public functions/methods so `G-SIG` is enforceable. Until regeneration lands, `G-SIG` is defined here and reported as **not yet enforceable on committed output**.

### 6.3 Dependency manifest (`G-DEP`)

| Field | Source |
|---|---|
| `kind` | `core` or `optional:<extra>` |
| `requirement` | Exact PEP 508 string from `pyproject.toml` |

**Stale when:** `dependencies.md` omits/adds/changes a requirement string vs packaging.

```bash
# Core dependency lines must be reconstructible from pyproject.toml
python3 - <<'PY'
import tomllib
from pathlib import Path
data = tomllib.loads(Path("pyproject.toml").read_text())
for req in data["project"]["dependencies"]:
    print(req)
for name in sorted(data["project"].get("optional-dependencies", {})):
    print(f"[{name}]")
    for req in data["project"]["optional-dependencies"][name]:
        print(req)
PY
```

### 6.4 Example manifest (`G-EX`)

| Field | Source |
|---|---|
| `path` | Repo-relative path under `examples/` |
| `exists` | boolean |

**Stale when:** index lists missing files, omits existing examples, or includes backup/archive paths.

```bash
find examples -name '*.py' | sort
# Measured: 148 top-level-recursive example scripts at contract baseline (use find for full set).
rg -n '\$\(date' docs/api_generated/examples_index.md || true
```

**Current defect:** `examples_index.md` contains literal `$(date -u +"%Y-%m-%d %H:%M:%S UTC")` (F-007).

### 6.5 Tool manifest (`G-TOOL`)

| Field | Source of truth (priority) |
|---|---|
| Runtime tool set | `TOOL_GROUPS` leaf names in `ipfs_kit_py/mcp_server/tools/__init__.py` |
| Committed JS/SDK companion | `ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json` |
| Generated agent/status claims | Any tool count embedded in `AGENT_GUIDE.md` / `doc_status.md` |

**Stale when:**

1. `tools-manifest.json` ≠ regenerate output of `python -m ipfs_kit_py.mcp_server.js_sdk.generate` (existing CI gate in `.github/workflows/mcp-server-ci.yml`), or
2. Generated docs hard-code a tool total that disagrees with measured `TOOL_GROUPS` leaf count, or
3. Docs claim a fixed historical count (21 / 28) as authoritative without citing the registry.

**Measured conflict (matrix C-MCP-TOOLS / F-019):** runtime **29** tools / 12 groups; JS manifest **28**; README framing **21**. Generated docs MUST cite **measured registry** or say “see TOOL_GROUPS,” never freeze a false total.

```bash
# Prefer static inspection; live import only if safe offline
rg -n "TOOL_GROUPS" ipfs_kit_py/mcp_server/tools/__init__.py | head
python3 - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path("ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json").read_text())
tools = manifest["tools"] if isinstance(manifest, dict) else manifest
print("manifest_tool_count", len(tools))
PY
```

### 6.6 Status / header manifest (`G-STAT`, `G-HDR`)

| Check | Pass criteria |
|---|---|
| **G-HDR** | No committed file under `docs/api_generated/` matches `\$\(date` or other unevaluated `$(` shell templates |
| **G-STAT** | Counts in `doc_status.md` equal counts from the same generator run’s manifests (not hand-waved “747 modules / 80 docs”) |
| **G-PROV** | README contains `Generated from` (or equivalent provenance) after KDOC-046 refresh |

**Current defect:** `doc_status.md` claims **747** Python modules and **80** documentation files; tree measures **1111** `ipfs_kit_py` `*.py` files and **400+** docs Markdown files (F-007).

---

## 7. Drift gate catalog (normative)

Gates are designed for offline CI or maintainer checks. Names are stable identifiers for KDOC-052 / scorecard wiring.

| Gate ID | Detects | Compare | Default severity |
|---|---|---|---|
| **G-HDR** | Non-deterministic / unevaluated timestamps | Regex scan of `docs/api_generated/**` | High (fail) |
| **G-MOD** | Stale module inventory | Fresh module manifest vs `module_structure.md` | High (fail) |
| **G-SIG** | Stale public signatures | Fresh signature manifest vs generated signatures | High (fail when signatures present) |
| **G-DEP** | Stale dependency list | `pyproject.toml` vs `dependencies.md` | High (fail) |
| **G-EX** | Stale example index | `examples/**/*.py` vs `examples_index.md` | Medium (fail) |
| **G-TOOL** | Stale tool / SDK manifest | Registry + `js_sdk.generate` diff + doc counts | High (fail) |
| **G-EXCL** | Public-API pollution | Generated files must not present `backup/`, `archive/`, `docs/py-ipld-*`, `*_fixed.py`, `*.broken`, etc. as supported API | High (fail) |
| **G-AGENT** | Misleading agent entry points | `AGENT_GUIDE.md` entry points ⊆ packaging scripts + allowlisted modules; no root phantom launchers | High (fail) |
| **G-OWN** | Wrong tree mutation | Generator must not write `docs/api/**` or protected plan paths | Critical (fail) |
| **G-PROV** | Missing provenance | README / headers per §5.3 | Medium (fail after KDOC-046) |

### 7.1 Check mode vs write mode

| Mode | Behavior |
|---|---|
| **generate / write** | Extract manifests; write all required artifacts; exit non-zero on extract failure |
| **check / drift** | Extract expected manifests; normalize (strip volatile provenance line if policy allows); diff against committed files; exit non-zero on any enabled gate failure; **do not** write |
| **report** | Same as check but exit zero and emit a Markdown/JSON report (for audits) |

Recommended CLI shape (to be implemented under separately authorized generator work; not created by this task):

```text
python tools/generate_api_docs_inventory.py --mode check
python tools/generate_api_docs_inventory.py --mode generate
```

Until that script exists, maintainers use the evidence commands in §6 and §9 as the manual contract.

### 7.2 Normalization before diff

To keep checks **deterministic**:

1. Normalize newlines to `\n`.
2. Optionally replace the single provenance timestamp line with the placeholder `<PROVENANCE>`.
3. Do not sort away semantic list differences.
4. Ignore trailing whitespace.

### 7.3 What does **not** pass a gate

| Anti-pattern | Why it fails the contract |
|---|---|
| File exists and is non-empty | Presence ≠ freshness (plan acceptance for KDOC-G060) |
| Raw `find … \| wc -l` equals a number in prose | Counts without allowlist filters and without signature/dependency structure |
| Weekly cron “usually ran” | No proof committed tree matches current source |
| pdoc HTML generated once | Not the Markdown contract set |

---

## 8. Exclusion gate detail (`G-EXCL`) — backups and external snapshots

Acceptance for KDOC-043 requires that the contract **does not treat tracked backups or external snapshots as public API**.

### 8.1 Rules

1. **Module map:** no `####` / path entry whose path is under `backup/`, `archive/`, `docs/ARCHIVE/`, or `docs/py-ipld-*`.
2. **Agent guide:** no “Key Entry Points” or “Main Classes” pointing at backup, archive, or external snapshot modules.
3. **Examples index:** no paths under `backup/` or `archive/`.
4. **Dependencies:** do not invent package dependencies from embedded `docs/py-ipld-*/pyproject.toml`; only root packaging `pyproject.toml`.
5. **Navigation:** generated README must state that external/embedded projects are documented under `docs/reference/EXTERNAL_DOCUMENTATION_SOURCES.md` (KDOC-044), not as package API.

### 8.2 Detection commands

```bash
# Fail if generated reference mentions backup/archive trees as module paths
rg -n 'backup/|archive/|docs/ARCHIVE/|docs/py-ipld-' docs/api_generated/module_structure.md \
  docs/api_generated/AGENT_GUIDE.md docs/api_generated/examples_index.md && exit 1 || true

# Fail if fixed/broken variants are listed as first-class API without status label
rg -n '_fixed\.py|\.broken|_old\.py|_updated\.py' docs/api_generated/module_structure.md || true
```

Any hit in supported-API sections is a **G-EXCL** failure unless the line is inside an explicit “Excluded from public API” appendix.

---

## 9. Reproduction and validation commands

### 9.1 Contract file validation (this task)

```bash
test -s docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md \
  && rg -q "deterministic" docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md
```

### 9.2 Manual drift smoke (offline, no network)

```bash
# Headers must not contain unevaluated shell
rg -n '\$\(date|\$\(' docs/api_generated/ || true

# Provenance / age of module map
head -n 5 docs/api_generated/module_structure.md
head -n 5 docs/api_generated/dependencies.md
head -n 5 docs/api_generated/doc_status.md

# Packaging scripts still match agent-facing claims after refresh
rg -n '\[project.scripts\]' -A 20 pyproject.toml

# Tool manifest companion present
test -f ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json

# Exclusions: backups/externals are not package roots for generation
test -d backup && test -d docs/py-ipld-car
```

### 9.3 Related CI pattern (tool manifest only today)

`.github/workflows/mcp-server-ci.yml` already implements a fail-closed regenerate-and-`git diff --exit-code` pattern for `ipfs_kit_py/mcp_server/js_sdk`. **G-TOOL** should keep that behavior. **G-MOD/G-DEP/G-EX** should follow the same pattern for `docs/api_generated/` once a deterministic generator script is authorized.

### 9.4 Program validation environments

- `IPFS_KIT_AUTO_INSTALL_BINARIES=0`
- No `git submodule update`, no fetch of external documentation
- Validation may read source, tests, workflows, and packaging; this task writes only the contract file

---

## 10. Current workflow and output defects (evidence)

These are **observed** conditions the contract is designed to detect. Fixing generators/workflows is **not** in scope for KDOC-043; exclusive refresh is **KDOC-046**; workflow edits are separately authorized follow-ups (plan §11).

| ID | Defect | Evidence |
|---|---|---|
| **D-1** | Stale generation timestamps (2025-10-29) on module/dependency files | `module_structure.md`, `dependencies.md` headers; freshness **F-007** |
| **D-2** | Literal `$(date -u +"%Y-%m-%d %H:%M:%S UTC")` in committed docs | `doc_status.md`, `examples_index.md`; workflow heredocs in `auto-doc-maintenance.yml` use quoted heredocs that prevent expansion |
| **D-3** | False module/doc counts in `doc_status.md` (747 / 80) | Tree measures 1111 package `*.py`; docs Markdown ≫ 80 |
| **D-4** | Non-deterministic wall-clock via `datetime.now().isoformat()` in inline extract script | Workflow Python embed writes local-now timestamps |
| **D-5** | Incomplete exclusion filters | Workflow skips `__pycache__` and path substring `test` only; does not exclude `*_fixed.py`, `backup/`, external snapshots (if ever walked) |
| **D-6** | Competing generators | `auto-doc-maintenance.yml` → `docs/api_generated/`; `pages.yml` → `docs/api/`; `tools/generate_api_docs.py` → MCP narrative — ownership confusion (ADR-0009, map §10) |
| **D-7** | Agent guide hard-codes structure that may not match packaging entry points | Committed `AGENT_GUIDE.md` emphasizes `ipfs_kit_py/mcp/` and classes that may not match `pyproject.toml` scripts |
| **D-8** | No checked-in check mode for `api_generated` drift | SOURCE_OF_TRUTH_MAP §10 gap; only JS SDK has regenerate-diff CI |
| **D-9** | Tool count drift across registry / JS manifest / docs | **C-MCP-TOOLS**, **F-019** |

### 10.1 Workflow heredoc footgun (normative fix guidance)

In `.github/workflows/auto-doc-maintenance.yml`, patterns equivalent to:

```bash
cat > docs/api_generated/doc_status.md << 'EOF'
> Last updated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
EOF
```

commit the **literal** `$(date …)` string because the quoted heredoc delimiter disables expansion. Contract-compliant generators MUST write timestamps from Python/`SOURCE_DATE_EPOCH` (or content digests), never from unexpanded shell templates inside single-quoted heredocs.

---

## 11. Relationship to adjacent tasks

| Task | Relationship |
|---|---|
| **KDOC-001** | Inventory classifies `api_generated/` as Generated / High freshness risk |
| **KDOC-003** | F-007/F-008 supply severity and evidence for drift gates |
| **KDOC-005** | Documentation lifecycle: generator-owned paths are not hand-edited |
| **KDOC-029** / ADR-0009 | Site toolchain; this contract stays valid under options that keep generator-owned Markdown |
| **KDOC-044** | External sources excluded from package API and authored metrics |
| **KDOC-046** | Exclusive regeneration of `docs/api_generated/*` implementing this contract |
| **KDOC-052** | Broader documentation validation suite should invoke gates **G-*** |
| **KDOC-053/054** | Maintenance cadence and scorecard consume gate results |

---

## 12. Review cadence and ownership after refresh

| Event | Required action |
|---|---|
| Change to public function signature in allowlisted module | Regenerate; **G-SIG** / **G-MOD** must pass |
| Change to `pyproject.toml` dependencies or scripts | Regenerate dependencies + agent guide |
| Add/remove `examples/*.py` | Regenerate examples index |
| Change `TOOL_GROUPS` or MCP tool modules | Regenerate JS SDK manifest; update any generated tool counts |
| Weekly cron | Allowed only if check mode is green on clean tree or opens a reviewable PR (no silent main mutation without review) |
| Hand PR touching `docs/api_generated/**` | Reject unless PR is pure generator output |

---

## 13. Separately authorized follow-ups (out of band)

This program’s docs-only scope does not modify workflows or packaging. Maintainers should authorize separately:

1. Extract inline `/tmp/extract_docs.py` from `auto-doc-maintenance.yml` into a versioned repo script with `--mode check|generate`.
2. Fix heredoc timestamp expansion / switch to content-digest provenance.
3. Wire **G-MOD**, **G-DEP**, **G-EX**, **G-HDR**, **G-EXCL** into CI analogously to `mcp-server-ci.yml` JS SDK drift.
4. Resolve ADR-0009 so `pages.yml` cannot overwrite authored `docs/api/` without an exclusivity rule.
5. Align JS `tools-manifest.json` and tests with `TOOL_GROUPS` leaf set (product fix; docs only report measured truth).

---

## 14. Acceptance mapping (KDOC-043)

| Acceptance criterion | How this contract satisfies it |
|---|---|
| Detect stale **module** manifests | **G-MOD** + §6.1 schema + allowlist algorithm |
| Detect stale **signature** manifests | **G-SIG** + §6.2 (required in KDOC-046 output) |
| Detect stale **dependency** manifests | **G-DEP** + `pyproject.toml` reconstruction |
| Detect stale **example** manifests | **G-EX** + sorted `examples/**/*.py` |
| Detect stale **tool** manifests | **G-TOOL** + registry vs JS SDK generate-diff + doc count rules |
| Does **not** treat tracked **backups** as public API | §4.2, §8 **G-EXCL** |
| Does **not** treat **external snapshots** as public API | §4.2, §8, KDOC-044 pointer |
| Deterministic generation | §5 ordering, `SOURCE_DATE_EPOCH` / content digest, check-mode normalization |
| Offline / no network | §5.4, §9 |
| Single declared output | This file only |

---

## 15. Glossary

| Term | Meaning |
|---|---|
| **Allowlist** | Explicit set of package paths eligible for public generated API inventory |
| **Check mode** | Drift detection without writing artifacts |
| **Content digest** | Hash of canonical manifest serialization used instead of wall-clock stamps |
| **Deterministic** | Same tree + same contract version ⇒ same normalized manifests (timestamps normalized or content-addressed) |
| **Drift** | Committed generated artifact disagrees with freshly extracted expected manifest |
| **Fail closed** | On extract or gate failure, exit non-zero; do not publish partial success |
| **Generated authority** | Plan §3.1 class; machine-owned reference only |
| **Public API (generated sense)** | Allowlisted, non-excluded modules and packaging entry points — **not** every file on disk |
| **Tool manifest** | MCP/JS SDK enumerated tools; runtime authority is `TOOL_GROUPS` |

---

## 16. Document control

| Field | Value |
|---|---|
| Authoring task | KDOC-043 |
| Edit policy | Update when gate IDs, allowlist rules, or required artifacts change |
| Protected paths | Must never modify `docs/documentation_plan.md`, `docs/architecture/ipfs_kit_documentation.objectives.md`, `docs/architecture/ipfs_kit_documentation.todo.md` |
| Companion evidence | `docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md` (F-007, F-008, F-019), `docs/audits/PUBLIC_SURFACE_MATRIX.md`, `docs/architecture/SOURCE_OF_TRUTH_MAP.md` §10–11, `docs/architecture/decisions/0009-documentation-site-toolchain.md`, `docs/api_generated/*` (read-only for this task) |
)
