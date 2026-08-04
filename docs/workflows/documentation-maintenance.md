# Documentation maintenance workflow

| Field | Value |
|---|---|
| Document class | **Canonical** (maintainer / agent operational workflow) |
| Status | active |
| Last verified | 2026-08-04 |
| Owner / task | **KDOC-054** / KDOC-G060 |
| Track | quality |
| Authority class | Program quality contract (not product user guidance; not Generated inventory) |
| Depends on | KDOC-043 (generated contract), KDOC-046 (generated refresh), KDOC-051 (impact map), KDOC-053 (validation gates) |
| Exclusive write target | `docs/workflows/documentation-maintenance.md` only |
| Scope | How maintainers and agents keep `docs/` accurate: ownership, cadence, change triggers, regeneration, ADRs, archival, dependency notes, failure triage, and automation backlog |
| Non-goals | Editing `.github/workflows/*`; implementing generator scripts; choosing Sphinx/MkDocs; claiming a reproducible site build from the committed tree |

This guide is the **operational maintenance playbook** for the documentation program. It describes what is true of the tree today, which commands you can run offline, and which tooling is still **Proposed**.

> **Site toolchain (normative non-claim):** There is **no** committed, reproducible Sphinx or MkDocs site build from a clean checkout. `docs/conf.py`, root `mkdocs.yml`, and `docs/mkdocs.yml` are **absent**. Dual CI workflows (`.github/workflows/docs.yml` Sphinx, `.github/workflows/pages.yml` MkDocs) are **non-reproducible** as of ADR-0009. Do **not** treat `sphinx-build`, `mkdocs build`, or `cd docs && make html` as supported maintainer commands until ADR-0009 is Accepted and a committed config lands. See [§8](#8-site-toolchain-status-adr-0009--proposed).

---

## 1. Purpose and relationship to other contracts

### 1.1 Purpose

1. Name **owners** for authored, generated, historical, external, validation, and workflow surfaces.
2. Define **review cadence** and **change triggers** so docs stay aligned with code and packaging.
3. Document **real** regeneration and validation commands available offline today.
4. Separate **current** generator/workflow behavior from **Proposed** automation and site tooling.
5. Cover **ADR handling**, **archival**, **dependency-doc updates**, and **failure triage**.
6. List a **separately authorized** automation backlog (this guide does not implement it).

### 1.2 Adjacent contracts (do not re-own)

| Document | Role |
|---|---|
| [`docs/guides/DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) | Lifecycle, authority classes, evidence ranking, review checklists |
| [`docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md`](../audits/GENERATED_DOCUMENTATION_CONTRACT.md) | Normative **G-*** drift gates for `docs/api_generated/` |
| [`docs/development/DOCUMENTATION_VALIDATION.md`](../development/DOCUMENTATION_VALIDATION.md) | Offline **V-*** gates, severity, PR/release profiles |
| [`docs/development/DOCUMENTATION_IMPACT_MAP.md`](../development/DOCUMENTATION_IMPACT_MAP.md) | Change → docs blast radius → focused checks |
| [`docs/architecture/decisions/0009-documentation-site-toolchain.md`](../architecture/decisions/0009-documentation-site-toolchain.md) | **Proposed** site toolchain / publish decision (U-15) |
| [`docs/api_generated/README.md`](../api_generated/README.md) | Generated inventory index + provenance (generator-owned) |
| [`docs/ARCHIVE/README.md`](../ARCHIVE/README.md) | Historical archive boundary and reading rules |
| [`docs/reference/EXTERNAL_DOCUMENTATION_SOURCES.md`](../reference/EXTERNAL_DOCUMENTATION_SOURCES.md) | External gitlink pins; do not fetch for validation |

---

## 2. Ownership

Every documentation surface has a write policy and a human/program owner. Agents must respect exclusive write targets and protected plan/board paths.

### 2.1 Ownership matrix

| Surface | Authority class | Write policy | Primary owner |
|---|---|---|---|
| This guide (`docs/workflows/documentation-maintenance.md`) | Canonical | KDOC-054 exclusive | Docs / quality maintainers |
| Authored guides under `docs/architecture/`, `docs/guides/`, ops, reference (non-generated) | Canonical (or Mixed) | Subsystem KDOC task or maintainer PR | Guide owners per impact map |
| `docs/api/*.md` | Authored API notes | Authors only; **must not** be overwritten by `api_generated` generators | API doc maintainers; exclusivity vs site CI is ADR-0009 |
| `docs/api_generated/**` | **Generated** | **Never hand-edit bodies**; regenerate under contract | KDOC-046 + generated contract (KDOC-043) |
| Validation gate specification | Program contract | KDOC-053 exclusive | Docs / quality maintainers |
| Generated drift gate definitions | Program audit | KDOC-043 exclusive | Generated-docs track |
| ADR bodies `docs/architecture/decisions/NNNN-*.md` | Proposed / Accepted / … | One ADR file per task; index README is separate | Confirmation owner listed in each ADR |
| ADR index `docs/architecture/decisions/README.md` | Canonical process | Maintainer / process tasks only | Documentation maintainers |
| `docs/ARCHIVE/**` | Historical | Intake with Historical banner; not present-tense guidance | Archive / IA owners (KDOC-042+) |
| External pins under `docs/` (gitlinks) | External | Pin only; **do not** `git submodule update` for validation | External sources contract (KDOC-044) |
| `.github/workflows/auto-doc-maintenance.yml` | CI automation | **Separately authorized** workflow PRs | CI + docs maintainers |
| `.github/workflows/docs.yml` / `pages.yml` | CI site paths (non-reproducible) | **Separately authorized**; policy under ADR-0009 | CI + DX maintainers |
| Program plan / objectives / todo board | Program-control | **Operator-protected** — workers never edit | Operator only |
| Navigation indexes (`docs/index.md`, `docs/README.md`, …) | Canonical nav | **KDOC-060** exclusive when scheduled | Navigation owner |

### 2.2 Protected paths (never edit from maintenance tasks)

Unless the operator explicitly expands scope, maintainers and agents **must not** create, modify, rename, delete, replace, or regenerate:

- `docs/documentation_plan.md`
- `docs/architecture/ipfs_kit_documentation.objectives.md`
- `docs/architecture/ipfs_kit_documentation.todo.md`

### 2.3 Hand-edit policy for Generated material

1. Do **not** hand-edit `docs/api_generated/*.md` bodies to “fix” counts, dates, or entry points.
2. Regenerate from packaging + static AST (contract KDOC-043 / refresh KDOC-046).
3. Review generator output in a PR; do not silent-push to `main` without review.
4. Authored claims that need conceptual explanation belong in Canonical guides, not in generated inventories.

---

## 3. Current automation surfaces (evidence, not aspiration)

### 3.1 Inventory of workflows that touch documentation

| Workflow | Path | Observed role | Maintainer status |
|---|---|---|---|
| Automated Documentation Maintenance | `.github/workflows/auto-doc-maintenance.yml` | Weekly cron (`0 9 * * 1`) + `workflow_dispatch`; writes `docs/api_generated/`; opens PR if staged diff | **Active generator path** with known defects **D-1–D-8** (contract §10); not fully contract-compliant |
| Documentation (Sphinx) | `.github/workflows/docs.yml` | Runs `cd docs && sphinx-build -b html . _build/html` | **Non-reproducible** — no `docs/conf.py` / Sphinx project in tree |
| GitHub Pages (MkDocs) | `.github/workflows/pages.yml` | Installs MkDocs Material; synthesizes `mkdocs.yml` via heredoc; generates into `docs/api/`; deploys Pages | **Non-reproducible / conflicting** — no committed `mkdocs.yml`; collides with hand `docs/api/` |
| MCP server CI (tool manifest) | `.github/workflows/mcp-server-ci.yml` | Regenerate-and-`git diff --exit-code` for JS tools manifest | **Real** fail-closed pattern for **G-TOOL** companion |

### 3.2 What the weekly workflow actually does

From `.github/workflows/auto-doc-maintenance.yml` (read the YAML for exact steps):

1. Checkout (full history), Python 3.12, `pip install -e .` plus `pdoc3`, `pydoc-markdown`, `sphinx`, themes.
2. Run `python -m pdoc --html` into `docs/api_generated/` (HTML side path; **out of** Markdown contract for gates until site toolchain is Accepted).
3. Inline AST extract script → `docs/api_generated/module_structure.md`.
4. Inline TOML read → `dependencies.md`; `find` → `examples_index.md`; metrics → `doc_status.md`; static agent template → `AGENT_GUIDE.md`; index → `README.md`.
5. `git add docs/api_generated/`; if staged changes, `peter-evans/create-pull-request` on branch `automated-docs-update`.

**Manual dispatch inputs** (GitHub Actions UI): `full` (default), `api-only`, `structure-only` — note that the current YAML does **not** branch on `update_type` for distinct job paths; treat those choices as **aspirational UI labels** until the workflow is fixed under a separately authorized PR.

### 3.3 Known defects (do not paper over)

| ID | Issue | Operational impact |
|---|---|---|
| **D-1 / D-2** | Stale or unexpanded `$(date …)` stamps in older commits | Freshness risk; **G-HDR** |
| **D-4** | Wall-clock `datetime.now()` in inline extract | Non-deterministic headers |
| **D-5** | Weak exclusion filters | May inventory clutter; **G-EXCL** |
| **D-6** | Competing writers (`api_generated` vs `pages.yml` → `docs/api/` vs `tools/generate_api_docs.py`) | Ownership confusion |
| **D-8** | No checked-in `--mode check` for `api_generated` | Drift is manual until **Proposed** inventory script lands |

Contract-compliant offline regeneration (KDOC-046) produces provenance headers and content digests; prefer those artifacts over unreviewed weekly HTML dumps.

---

## 4. Review cadence

Cadence is for **maintainers and agents**, not a promise that CI already enforces every gate.

| Event | Minimum actions | Gates / references |
|---|---|---|
| PR touching `docs/**` only | Review authority class, links on changed files, secrets, provenance on new Canonical files | **V-LINK**, **V-SENS**, **V-PROV**, **V-PRES** (info only) |
| PR touching public Python / packaging / entry points | Impact-map blast radius; focused subsystem tests; regenerate generated inventories if packaging/API surface changed | Impact map; **V-SUB**; **V-GEN** / **G-*** if inventories affected |
| Weekly generator run / generated PR | Review PR as pure generator output; refuse hand-mixed authored edits in the same PR | Contract review cadence; **G-HDR**, **G-MOD**, **G-DEP**, **G-EX**, **G-AGENT** |
| ADR status change | Update linked architecture guides; mark old claims **needs-verification** | DOCUMENTATION_GUIDE §11; ADR README process |
| Pre-release | Full offline documentation profile; zero unwaived Blockers | **Release-docs** profile in validation spec |
| Archive intake | Historical banner; no Canonical nav promotion without labels | ARCHIVE README; **V-ARCH** |

**Presence-only checks** (`test -s`, task `rg -q`) prove a file exists or contains a string. They are **never** accuracy proof (validation **V-PRES** = Info for accuracy claims).

---

## 5. Change-trigger process

When code, packaging, or workflow changes, treat documentation as part of the change—not a follow-up hope.

### 5.1 Process (normative)

1. **Identify the trigger** using the impact map and DOCUMENTATION_GUIDE §11.1 (exports, CLI, MCP tools, backends, auth/config, async boundaries, generator schema, ADR status, evidence-test removal).
2. **List blast-radius docs** (architecture owner + user/reference + generated).
3. **Mark Canonical docs needs-verification** (header note or PR checklist) until claims are re-checked against the tree.
4. **Regenerate** `docs/api_generated/` when packaging, public signatures, examples, or MCP tool registry change (see [§6](#6-regeneration-and-review)).
5. **Run offline validation** commands from [§10](#10-offline-commands-that-work-today) and focused tests required by the impact map.
6. **Open or update PRs** that separate authored claim edits from pure generator output when practical.
7. **Do not** “fix” truth by editing Generated files or by claiming a site build that the tree cannot run.

### 5.2 High-severity trigger examples

| Trigger | Regenerated / reviewed surfaces | Typical severity |
|---|---|---|
| `pyproject.toml` version, scripts, or dependencies | `dependencies.md`, `AGENT_GUIDE.md`, install/quickref claims | P0 |
| Public allowlisted module signatures | `module_structure.md` (**G-SIG** / **G-MOD**) | P0 |
| `examples/**/*.py` add/remove | `examples_index.md` (**G-EX**) | P1 |
| `TOOL_GROUPS` / JS tools manifest | Tool counts; `python -m ipfs_kit_py.mcp_server.js_sdk.generate` + diff CI | P0 |
| Docs workflow or Docker “documentation” stage | This guide + ADR-0009; **do not** invent Accepted site commands | P1 |

Full matrices: [`DOCUMENTATION_IMPACT_MAP.md`](../development/DOCUMENTATION_IMPACT_MAP.md).

---

## 6. Regeneration and review

### 6.1 Authority of generated output

- **Generated** inventories under `docs/api_generated/` are machine-owned reference material.
- Prefer packaging, focused tests, accepted ADRs, and Canonical guides when they conflict with inventories.
- Optional pdoc HTML is **out of contract** for architecture gates until ADR-0009 accepts a site path.

### 6.2 Current offline regeneration posture

| Path | Status | Notes |
|---|---|---|
| Committed artifacts under `docs/api_generated/` after KDOC-046 | **Current** generator-owned Markdown set | Headers cite generator `kdoc-046-offline-ast-inventory`, contract date, content digest, tree hash |
| Versioned `tools/generate_api_docs_inventory.py --mode check\|generate` | **Proposed tooling** (not present in tree) | Recommended CLI in contract §7.1; follow-up for check-mode CI |
| `.github/workflows/auto-doc-maintenance.yml` weekly job | **Current CI path**, incomplete vs contract | Use for PR automation only after human review of defects |
| `tools/generate_api_docs.py` | **Adjacent** MCP endpoint narrative generator | **Not** owner of `docs/api_generated/` |
| `python -m ipfs_kit_py.mcp_server.js_sdk.generate` | **Current** for JS tools manifest | Existing regenerate-diff CI pattern |

### 6.3 Environment for any generation or validation run

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
# Optional: fail loud on accidental network in restricted environments
# export http_proxy=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9
# Optional deterministic timestamps when a generator honors them:
# export SOURCE_DATE_EPOCH=0
```

- **Do not** `git submodule update` or fetch external documentation gitlinks for validation.
- Prefer static AST / packaging reads over importing modules that start daemons or download binaries.
- Python floor for package work is **≥3.12** per packaging (ignore stale lower minversion notes elsewhere).

### 6.4 Review checklist for a generated PR

- [ ] Diff is limited to generator-owned paths under `docs/api_generated/` (or an explicitly authorized companion manifest).
- [ ] Provenance headers present; no literal unexpanded `$(date` / `$(` shell templates (**G-HDR**).
- [ ] Module / dependency / example inventories look consistent with a spot-check of `pyproject.toml` and a few modules (**G-MOD**, **G-DEP**, **G-EX**).
- [ ] Agent guide entry points ⊆ packaging scripts + allowlisted modules; no phantom root launchers (**G-AGENT**).
- [ ] No promotion of `backup/`, `archive/`, `docs/ARCHIVE/`, `docs/py-ipld-*`, `*_fixed.py`, `*.broken` as supported API (**G-EXCL**).
- [ ] Generator did not write `docs/api/**` or protected plan paths (**G-OWN**).
- [ ] No silent mix of unrelated authored guide rewrites in the same automated PR.

### 6.5 What maintainers should **not** run as “the docs build”

The following appear in older agent templates or CI YAML but are **not** supported reproducible maintainer commands against the committed tree:

```bash
# NOT supported today — missing Sphinx project (no docs/conf.py)
# cd docs && sphinx-build -b html . _build/html

# NOT supported today — no committed mkdocs.yml
# mkdocs build --site-dir public

# NOT supported today — no docs/Makefile html target as a durable site
# cd docs && make html
```

Label any future site command **Proposed** until ADR-0009 is Accepted and config is committed.

---

## 7. ADR handling

### 7.1 Process summary

1. Copy [`docs/architecture/decisions/0000-template.md`](../architecture/decisions/0000-template.md); never leave a filled decision as `0000`.
2. Filename `NNNN-short-kebab-title.md`; title `# ADR-NNNN: …`.
3. Declare exactly one **decision status**: Proposed, Accepted, Rejected, Superseded, Deprecated, or Unknown.
4. Separate **current behavior (evidence)** from **target decision**.
5. Label rationale **Accepted / Proposed / Inferred / Unknown**.
6. List confirmation owner and question while Proposed; do not flip to Accepted without maintainer confirmation or strong implemented-invariant evidence (ADR README §3).
7. On status change: update linked guides, impact map references, and this maintenance guide if operational commands change.

Full process: [`docs/architecture/decisions/README.md`](../architecture/decisions/README.md).

### 7.2 Documentation-toolchain ADR (blocking for site claims)

| Field | Value |
|---|---|
| ADR | [ADR-0009](../architecture/decisions/0009-documentation-site-toolchain.md) |
| Status | **Proposed** |
| Blocks | Contributor “build the docs site” commands; sole publish path; Docker documentation stage as production-aligned |
| Maintainer action while Proposed | Keep guides honest; use offline Markdown + generated contracts; do not promise Sphinx/MkDocs |

### 7.3 Structural checks that still hold while ADR-0009 is Proposed

```bash
test -s docs/architecture/decisions/0009-documentation-site-toolchain.md \
  && rg -q "Status: Proposed" docs/architecture/decisions/0009-documentation-site-toolchain.md

# Site project files still absent (non-reproducibility evidence)
test ! -f docs/conf.py
test ! -f mkdocs.yml
test ! -f docs/mkdocs.yml

# Dual site workflows still present as competing surfaces
test -f .github/workflows/docs.yml
test -f .github/workflows/pages.yml
```

---

## 8. Site toolchain status (ADR-0009 — Proposed)

| Claim | Reality in tree |
|---|---|
| “Sphinx docs build works from main” | **False** for a clean checkout — `docs.yml` invokes `sphinx-build` without committed `conf.py` |
| “MkDocs site is reproducible” | **False** — `pages.yml` / Docker synthesize ephemeral `mkdocs.yml` and may overwrite authored paths |
| “Primary documentation store” | **True** — Markdown under `docs/` is the human/agent corpus |
| “Generated inventories are authoritative conceptual guides” | **False** — inventories only; Canonical guides and packaging win conflicts |
| “Validation requires a site build” | **False** — offline **V-*** / **G-*** gates require **no** Sphinx/MkDocs |

Until an option in ADR-0009 §3.2 is Accepted (committed MkDocs, committed Sphinx, validation-only, generated-reference primary, or hybrid), maintenance is **Markdown-first + generator contract + offline gates**.

---

## 9. Archival

### 9.1 Rules

1. Dated campaign reports, COMPLETE/SUMMARY dumps, and fix write-ups that are not current guidance belong under **Historical** class — preferably `docs/ARCHIVE/` with the archive boundary rules.
2. Do **not** operationalize ARCHIVE install steps, ports, or “production ready” banners without re-verification against source and Canonical guides.
3. Canonical navigation must not promote Historical material as current without an explicit Historical label (**V-ARCH**).
4. Physical moves and stub redirects are owned by archive/IA tasks (e.g. KDOC-042/045); this guide does not re-home trees.
5. Generated regeneration must **exclude** archive/backup/external snapshots from supported-API inventories (**G-EXCL**).

Boundary document: [`docs/ARCHIVE/README.md`](../ARCHIVE/README.md).

### 9.2 When a Canonical doc becomes Historical

1. Add supersession notice, date, and pointer to the replacement Canonical doc.
2. Stop using present-tense “how to operate today” language without labels.
3. Update inbound links from Canonical docs so they do not present the old path as current authority.
4. Prefer archive intake process over deleting history that still has provenance value.

---

## 10. Offline commands that work today

All commands below are intended for a clean checkout **without** network, submodule fetch, or site toolchain. Prefix sessions with `export IPFS_KIT_AUTO_INSTALL_BINARIES=0`.

### 10.1 Admission / presence (Info only for accuracy)

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

test -s docs/workflows/documentation-maintenance.md
test -s docs/development/DOCUMENTATION_VALIDATION.md
test -s docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md
test -s docs/api_generated/README.md
test -s docs/guides/DOCUMENTATION_GUIDE.md
```

### 10.2 Generated drift smoke (manual contract checks)

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

# Headers must not contain unevaluated shell
rg -n '\$\(date|\$\(' docs/api_generated/ || true

# Provenance / age of key artifacts
head -n 8 docs/api_generated/README.md
head -n 8 docs/api_generated/module_structure.md
head -n 8 docs/api_generated/dependencies.md
head -n 8 docs/api_generated/doc_status.md

# Packaging scripts still match agent-facing claims after refresh
rg -n '\[project.scripts\]' -A 30 pyproject.toml

# Tool manifest companion present
test -f ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json

# Exclusion smoke: backups/externals must not appear as supported API paths
rg -n 'backup/|archive/|docs/ARCHIVE/|docs/py-ipld-' \
  docs/api_generated/module_structure.md \
  docs/api_generated/AGENT_GUIDE.md \
  docs/api_generated/examples_index.md && exit 1 || true
```

### 10.3 Authored-doc structural smoke

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

# Sample relative Markdown links (full resolver is Proposed tooling — see §12)
rg -n --glob '*.md' '\[[^\]]+\]\(([^)]+)\)' docs/ | head -n 50

# Example path authority checks
test -f ipfs_kit_py/cli.py
test -f .github/workflows/auto-doc-maintenance.yml
```

### 10.4 MCP tools manifest regenerate-diff pattern (existing CI)

When MCP tools change, use the same fail-closed approach as `.github/workflows/mcp-server-ci.yml`:

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
python -m ipfs_kit_py.mcp_server.js_sdk.generate
git diff --exit-code -- ipfs_kit_py/mcp_server/js_sdk/
```

(Exact paths and flags should match the workflow in the tree you are on.)

### 10.5 Focused tests (when the impact map requires them)

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
# Example: contracted Iroh documentation link checks (exists in tree)
pytest tests/test_iroh_operations_docs.py -q
```

Prefer **focused** default-discovery tests over full-suite pytest as a documentation gate. See [`DOCUMENTATION_VALIDATION.md`](../development/DOCUMENTATION_VALIDATION.md) §9 and the impact map.

### 10.6 Workflow existence checks (not “green CI means site works”)

```bash
test -f .github/workflows/auto-doc-maintenance.yml
test -f .github/workflows/docs.yml
test -f .github/workflows/pages.yml
# Reminder: existence of YAML ≠ reproducible Sphinx/MkDocs site
```

---

## 11. Dependency and packaging documentation updates

| Change in packaging | Doc actions |
|---|---|
| Core or optional dependency list | Regenerate `docs/api_generated/dependencies.md`; update install guides if user-facing extras change |
| Console scripts / entry points | Regenerate `AGENT_GUIDE.md`; update CLI/runtime Canonical docs; check QUICK_REFERENCE |
| Package version | Align README badges / install notes with `pyproject.toml` (matrix **C-VER**); regenerate status metrics |
| Python floor | Installation and development guides; ignore stale lower bounds elsewhere |
| New optional extra | Document prerequisites; mark network/daemon needs; do not invent default secret storage |

**Real inspection commands:**

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
rg -n '\[project\]|dependencies|optional-dependencies|\[project.scripts\]' -A 5 pyproject.toml | head -n 80
head -n 40 docs/api_generated/dependencies.md
```

Do not invent dependency “purpose” prose that contradicts packaging metadata.

---

## 12. Proposed tooling (clearly labeled — not available as checked-in defaults)

Items below are **Proposed**. Do not document them as if they already ship.

| Proposed tool / automation | Intent | Status |
|---|---|---|
| `tools/generate_api_docs_inventory.py --mode check\|generate` | Deterministic inventory + offline drift gate for `docs/api_generated/` | **Proposed** — recommended in contract §7.1; **not** present as a versioned script path at last verification |
| Unified `tools/docs_validate.py` with `--profile` and JSON report | Implement **V-*** gate IDs from the validation spec | **Proposed** — validation §14.3 |
| CI job running offline profiles with `IPFS_KIT_AUTO_INSTALL_BINARIES=0` | Enforce PR-docs / Release-docs / Generated-only profiles | **Proposed** — separately authorized |
| Shared Markdown link+anchor resolver | Corpus-wide **V-LINK** / **V-ANCH** | **Proposed** |
| Contract-compliant rewrite of `auto-doc-maintenance.yml` | Fix D-1–D-5, honor allowlists, PR-only mutation, optional check mode | **Proposed** — workflow PR separately authorized |
| Committed `mkdocs.yml` **or** `docs/conf.py` + single publisher | Reproducible site (ADR-0009 options A/B/E) | **Proposed** — **not** selected |
| Validation-only CI without full static site (ADR-0009 option C) | Honest gates without false site confidence | **Proposed** |
| Retirement/quarantine of weak presence tools (e.g. `tools/verify_documentation_updates.py` as authority) | Stop agents treating presence scripts as accuracy proof | **Proposed** |
| Auto-merge of generated PRs | Convenience | **Rejected for now** — review required; fail-closed on drift |

When mentioning Proposed tooling in other docs, keep the **Proposed** label and link here or to the owning contract.

---

## 13. Failure triage

### 13.1 Generated PR not opened / empty diff

| Check | Action |
|---|---|
| Workflow completed with “No documentation changes detected” | Expected if inventories already match sources; still run manual **G-*** smoke after large package changes |
| Workflow failed mid-job | Open Actions logs for the run; common causes: Python syntax in walked modules (AST extract should fail closed), missing deps, permissions |
| PR opened but content is wrong | Reject or fix via **regeneration**, not hand-edit; file workflow defects as separately authorized follow-ups |

### 13.2 Drift / freshness failures

| Symptom | Likely gate | Triage |
|---|---|---|
| Literal `$(date` in generated files | **G-HDR** | Do not ship; regenerate with Python/`SOURCE_DATE_EPOCH` timestamps |
| Module map missing new public modules | **G-MOD** | Regenerate; verify allowlist/exclusions |
| Dependencies disagree with `pyproject.toml` | **G-DEP** | Regenerate dependencies artifact |
| Examples index missing/extra paths | **G-EX** | Regenerate examples index |
| Agent guide invents launchers | **G-AGENT** | Regenerate from packaging; fix generator templates if needed |
| Backup/archive paths as API | **G-EXCL** | Fix generator filters; do not document clutter as supported |

### 13.3 Site / Pages / Sphinx job failures

| Symptom | Interpretation | Action |
|---|---|---|
| `sphinx-build` fails missing `conf.py` | Expected non-reproducible path | **Do not** “fix” by promising local Sphinx; track under ADR-0009 |
| MkDocs job rewrites `docs/index.md` or `docs/api/` | Conflicting writer | Treat as ownership incident; do not merge destructive site diffs into authored trees without an Accepted toolchain decision |
| Docker `documentation` stage creates default `mkdocs.yml` | Ephemeral config pattern | Label experimental; not production publish authority |

### 13.4 Authored-doc validation failures

| Symptom | Gate family | Action |
|---|---|---|
| Broken local relative links in Canonical docs | **V-LINK** | Fix paths or remove claim; Historical internals may be Warning |
| Missing provenance on new program Canonical outputs | **V-PROV** | Add header fields per DOCUMENTATION_GUIDE §3 |
| Secrets / tokens in examples | **V-SENS** | Redact immediately; rotate if real credentials leaked |
| Historical posed as current in Canonical nav | **V-ARCH** | Relabel or re-link to Canonical replacement |
| Focused subsystem test red | **V-SUB** | Fix code or doc claim; do not drop the only rank-1 evidence without replacement |

### 13.5 Permission and process failures

- Generated workflow needs `contents: write` and `pull-requests: write` — permission errors are repo settings, not doc content bugs.
- Agents hitting protected plan/board paths must stop and leave those files untouched.
- Scope creep (editing workflows from a docs-only task) is out of policy for this guide’s exclusive target.

---

## 14. Separately authorized automation backlog

The following require **explicit authorization** outside this document’s exclusive write target. Listing them here does not schedule or implement them.

1. Land versioned `tools/generate_api_docs_inventory.py` with `--mode check|generate|report` implementing **G-*** (contract §7).
2. Repair `.github/workflows/auto-doc-maintenance.yml`: deterministic timestamps, exclusion filters, optional `update_type` behavior, no destructive writes outside `docs/api_generated/`.
3. Implement offline CI profiles (**PR-docs**, **Release-docs**, **Generated-only**) from the validation specification.
4. Accept ADR-0009 (or a refinement) and either commit one site config **or** deliberately choose validation-only; retire or demote the non-chosen publisher.
5. Stop `pages.yml` (or Docker) from overwriting authored `docs/api/` and `docs/index.md` unless that overwrite is the Accepted design.
6. Align JS `tools-manifest.json` leaf count with `TOOL_GROUPS` when they drift.
7. Shared link/anchor checker and retirement of presence-only “documentation verification” scripts as authority.
8. Scorecard / final documentation scorecard wiring to consume gate IDs without collapsing warnings into blockers.

---

## 15. Improving documentation quality (authoring side)

Automation does not replace Canonical authorship.

1. **Add accurate docstrings** on public modules (generators extract them; they are not a substitute for architecture guides).
2. **Update Canonical guides** when behavior or packaging changes—use evidence ranking and change triggers.
3. **Add examples** under `examples/` when demonstrating supported usage (feeds `examples_index.md` after regeneration).
4. **Prefer focused tests** as rank-1 evidence for behavioral claims.
5. **Never** embed live secrets; mark network/daemon prerequisites explicitly.
6. **Label** Proposed, Historical, Generated, and External material so agents do not promote them to current authority.

---

## 16. Manual trigger of the weekly GitHub workflow

When you intentionally run the existing automation (knowing its defects):

1. Open the repository Actions tab.
2. Select **Automated Documentation Maintenance** (`.github/workflows/auto-doc-maintenance.yml`).
3. **Run workflow** → optional `update_type` (`full` / `api-only` / `structure-only` — see [§3.2](#32-what-the-weekly-workflow-actually-does) on limited implementation).
4. If a PR opens, apply [§6.4](#64-review-checklist-for-a-generated-pr) before merge.
5. If no PR opens, confirm whether inventories truly match sources via [§10.2](#102-generated-drift-smoke-manual-contract-checks).

Workflow edits remain **separately authorized**; do not treat this guide as permission to change YAML.

---

## 17. Benefits of this maintenance model

| Benefit | How it is achieved |
|---|---|
| Honesty | No false Sphinx/MkDocs reproducibility claim |
| Ownership clarity | Explicit matrix and protected paths |
| Drift detection | **G-*** / **V-*** contracts + real offline smokes |
| Reviewability | Generated PRs; no auto-merge requirement |
| Agent safety | Offline env, no external fetch, AST preferred over side-effect imports |
| Forward path | Proposed tooling and ADR-0009 backlog without inventing acceptance |

---

## 18. Document control

| Field | Value |
|---|---|
| Authoring task | KDOC-054 |
| Goal | KDOC-G060 — Repeatable freshness, generated-doc, and quality controls |
| Edit policy | Update when ownership, cadence, real commands, or toolchain non-claims change |
| Conflict policy | Own this guide only; describe workflow gaps rather than editing `.github` |
| Protected paths | Must never modify plan/objectives/todo board files |
| Acceptance (task) | Real current commands where available; Proposed tooling labeled; no promise of a nonexistent reproducible Sphinx/MkDocs build |
| Companion evidence | Generated contract, validation spec, impact map, DOCUMENTATION_GUIDE, ADR-0009, `docs/api_generated/README.md` |
)
