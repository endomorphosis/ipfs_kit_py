# Offline documentation validation and quality gates

| Field | Value |
|---|---|
| Document class | **Canonical** (maintainer / agent validation contract) |
| Status | active |
| Last verified | 2026-08-04 |
| Owner / task | **KDOC-053** / KDOC-G060 |
| Track | quality |
| Authority class | Program quality contract (not product user guidance; not Generated inventory) |
| Depends on | KDOC-005 (lifecycle/evidence), KDOC-029 / ADR-0009 (toolchain non-claims), KDOC-043 (generated drift gates **G-***) |
| Exclusive write target | `docs/development/DOCUMENTATION_VALIDATION.md` only |
| Downstream consumers | KDOC-054 maintenance workflow, FINAL_DOCUMENTATION_SCORECARD, PR/agent review checklists |
| Scope | Offline, reproducible documentation quality gates for authored, generated, historical, and external trees under `docs/` |
| Non-goals | Implementing CI workflows or generator scripts (separately authorized); choosing Sphinx/MkDocs; claiming a full site build works; editing protected plan/board/objectives files |

This document is the **canonical specification** for how maintainers and agents validate documentation **without network access**, without side-effectful imports, and without treating file presence as proof of accuracy. It defines gate families, severity (release blocker vs warning), offline reproduction commands, a focused subsystem test matrix, and the hard limits of presence-only checks used elsewhere in the program.

> **Offline contract:** All gates in this document MUST be runnable on a clean checkout with no network egress, no binary auto-install, no submodule fetch, and no live daemon. Prefer static file and AST inspection over Python imports.

---

## 1. Purpose and non-goals

### 1.1 Purpose

1. Define **reproducible Offline** documentation quality gates that any contributor can re-run from a checkout.
2. Distinguish **release blockers** from **warnings** so scorecards and PR review do not collapse all findings into one green/red bit.
3. Forbid **import-time side effects** (daemon start, binary download, network) during documentation validation.
4. Explain the **limitations of presence-only tests** (`test -s`, task `rg -q` vocabulary checks, “✓ doc exists” suites) so they are never treated as accuracy proof.
5. Catalog canonical checks for: links/anchors, referenced paths/symbols/entry points, safe snippet and CLI help surfaces, duplicate titles and archive isolation, generated drift, sensitive-data scans, provenance/status metadata, and focused subsystem tests.
6. Wire authored-doc gates to generated-doc gates (**G-*** from [`docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md`](../audits/GENERATED_DOCUMENTATION_CONTRACT.md)) without re-owning generator implementation.

### 1.2 Non-goals

| Non-goal | Owner / note |
|---|---|
| Writing or editing `.github/workflows/*` | Separately authorized follow-up (plan §11) |
| Implementing `tools/generate_api_docs_inventory.py --mode check` | Generator work (KDOC-046 + authorized scripts) |
| Choosing MkDocs vs Sphinx vs Markdown-only site | ADR-0009 / KDOC-029 (**Proposed**; neither site path is reproducible today) |
| Hand-editing `docs/api_generated/**` bodies | Generated exclusive; regenerate only |
| Initializing empty external gitlinks | Forbidden for validation (KDOC-044) |
| Full-suite pytest as a documentation gate | Prefer focused default-discovery tests (§9) |
| Treating task-level `rg` acceptance as product accuracy | Presence-only; see §11 |

### 1.3 Relationship to adjacent contracts

| Document | Role relative to this spec |
|---|---|
| [`DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) | Lifecycle, authority classes, evidence ranking, provenance fields |
| [`GENERATED_DOCUMENTATION_CONTRACT.md`](../audits/GENERATED_DOCUMENTATION_CONTRACT.md) | Normative **G-*** drift gates for `docs/api_generated/` |
| [`DOCUMENTATION_IMPACT_MAP.md`](DOCUMENTATION_IMPACT_MAP.md) | Change → docs blast radius → focused checks |
| [`testing_guide.md`](testing_guide.md) | Pytest discovery, offline expectations, presence ≠ accuracy |
| [`SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md) | Per-subsystem focused tests and candidate authorities |
| [`EXTERNAL_DOCUMENTATION_SOURCES.md`](../reference/EXTERNAL_DOCUMENTATION_SOURCES.md) | Empty gitlinks are success for “pin present, content absent” |
| [`documentation-maintenance.md`](../workflows/documentation-maintenance.md) | Operational workflow; **must not** promise a nonexistent Sphinx/MkDocs build (KDOC-054 ownership) |

---

## 2. Offline and reproducibility rules (normative)

### 2.1 Environment hard requirements

| Variable / constraint | Required value | Why |
|---|---|---|
| Network egress | **None required** for gates in this document | Reproducible CI and air-gapped agent runs |
| `IPFS_KIT_AUTO_INSTALL_BINARIES` | `0` | Prevents installers from downloading binaries during validation |
| External gitlinks under `docs/` | **Do not** `git submodule update` or fetch | KDOC-044; empty trees are expected |
| Live daemons (IPFS, Lotus, Iroh, MCP server) | **Not required** | Doc gates must not depend on process health |
| Site toolchain (Sphinx/MkDocs) | **Not required** for these gates | ADR-0009: committed configs absent; site workflows non-reproducible |
| Python floor (when running focused tests) | **≥3.12** per packaging | Ignore stale `minversion = 3.8` notes |

Recommended prefix for any shell session that runs documentation validation:

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
# Optional: make accidental network use fail loudly in restricted environments
# export http_proxy=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9
```

### 2.2 Reproducibility criteria

A gate is **reproducible** only if:

1. Two runs on the **same tree** (same commit, same uncommitted edits) produce the **same pass/fail** and the same normalized finding list.
2. Findings are **path- and rule-addressable** (file, line or section, gate ID), not free-form narrative alone.
3. The gate does **not** depend on wall-clock time, random seeds, or network availability.
4. Normalization (when comparing generated artifacts) follows the generated contract: LF newlines, optional provenance line placeholder, no trailing-whitespace noise.

### 2.3 Side-effect-free inspection (normative)

Documentation validation MUST prefer, in order:

| Preference | Technique | Allowed for |
|---|---|---|
| 1 | Filesystem presence, size, encoding, Markdown parse | All text docs |
| 2 | Regex / `rg` structural scans | Links, secrets patterns, provenance fields, headings |
| 3 | Static AST (`ast.parse`) of referenced Python paths | Symbol existence, public function names |
| 4 | Packaging metadata read (`pyproject.toml`, entry points) | Console scripts, extras, package name |
| 5 | Focused pytest under default discovery | Behavioral contracts the docs teach |
| 6 | Subprocess CLI **help / dry-run only** (`--help`, parser build) | CLI surface claims |
| **Forbidden** | Import modules that start daemons, download binaries, open network sockets, or write state roots | Any gate labeled offline |

When a symbol check would require importing a known side-effectful module, the gate MUST use AST or packaging metadata instead, and MUST record the module under **side-effect quarantine** (label only; do not execute).

Known high-risk import traps (non-exhaustive; see agent system map when present):

- Installer entry points that auto-fetch binaries when env is not forced off.
- Root package paths that construct live clients or start daemons at import time.
- Optional extras that probe network services on import.

---

## 3. Severity model: release blockers vs warnings

Every gate result is classified into exactly one severity. Scorecards and PR policies MUST preserve the distinction.

| Severity | Exit expectation for a **release gate suite** | Meaning | Examples |
|---|---|---|---|
| **Blocker** (release blocker) | Non-zero overall exit | Must be fixed or explicitly waived by a maintainer with a dated exception before treating docs as release-ready | Broken local link in Canonical guide; generated **G-*** high-severity drift; secrets in docs; missing required provenance on new Canonical architecture guides; generator wrote protected paths |
| **Warning** | Zero overall exit allowed if policy is “warn-only”; still listed in report | Should be fixed; does not alone stop a patch release when waived or backlog-tracked | Duplicate H1 titles across unrelated trees; missing “Last verified” on older Canonical docs being gradually migrated; external HTTP link unchecked offline; archive isolation advisory |
| **Info** | Never fails the suite | Context for humans (counts, coverage of gate families) | Number of Markdown files scanned; which gate families ran |
| **Skipped** | Documented skip with reason | Environment or scope excluded intentionally | External gitlink content absent; optional Sphinx build not claimed |

### 3.1 Severity assignment rules

1. **Accuracy and safety first:** broken Canonical local links, secret leakage, and high-severity generated drift are **Blockers**.
2. **Presence of a file alone is never a Blocker pass** — only a prerequisite for stronger checks.
3. **Historical / ARCHIVE** trees: broken links **inside** Historical material default to **Warning** unless a Canonical document links to them as current guidance (then the Canonical link is a Blocker).
4. **Proposed / ADR drafts:** missing “Accepted” status is **Info/Warning**, not a release blocker for product code.
5. **Waivers:** A Blocker may be waived only with (a) ticket/issue id, (b) owner, (c) expiry date, (d) residual risk sentence. Waivers are **not** silent.

### 3.2 Suite profiles

| Profile | Gate set | Typical use |
|---|---|---|
| **PR-docs** | Structural offline gates on changed paths + focused subsystem tests for touched surfaces | Pull requests that edit `docs/**` or public surfaces |
| **Release-docs** | Full offline catalog; Blockers fail the profile | Pre-release documentation sign-off |
| **Generated-only** | **G-*** family only (check mode) | After generator or packaging changes |
| **Report-only** | All gates emit Markdown/JSON; exit 0 | Audits and scorecard refresh |

Implementation of profiles in CI is **separately authorized**. This document defines the contract profiles must implement.

---

## 4. Gate catalog overview

Stable gate IDs for scorecards and tooling. Generated-doc drift IDs remain the **G-*** namespace owned by the generated documentation contract.

| Gate ID | Family | Default severity | Offline? | Side-effect free? |
|---|---|---|---|---|
| **V-ENV** | Environment precondition | Blocker if violated during a claimed offline run | Yes | Yes |
| **V-LINK** | Local Markdown link resolution | Blocker (Canonical); Warning (Historical) | Yes | Yes |
| **V-ANCH** | In-document / cross-doc anchors | Warning until full anchor inventory exists; Blocker for contracted runbooks | Yes | Yes |
| **V-PATH** | Referenced repo paths exist | Blocker when path is claimed as current authority | Yes | Yes |
| **V-SYM** | Referenced symbols / entry points | Blocker when claimed as public surface | Yes | AST preferred |
| **V-CLI** | CLI help / parser surface | Blocker for listed commands in contracted docs | Yes | Help-only |
| **V-SNIP** | Snippet hygiene (no TODO, no live secrets, fenced code) | Warning / Blocker (secrets → Blocker) | Yes | Yes |
| **V-DUP** | Duplicate titles / competing indexes | Warning (navigation exclusivity is KDOC-060) | Yes | Yes |
| **V-ARCH** | Archive / Historical isolation | Blocker if Historical posed as current in Canonical nav without label | Yes | Yes |
| **V-GEN** | Generated drift (invokes **G-***) | Per G-* defaults | Yes | Yes (static) |
| **V-SENS** | Sensitive-data scan | Blocker | Yes | Yes |
| **V-PROV** | Provenance / status / class metadata | Blocker for new program Canonical outputs; Warning for legacy migration | Yes | Yes |
| **V-SUB** | Focused subsystem test matrix | Blocker when the change class requires it | Yes (default discovery) | Tests may import package under offline env |
| **V-PRES** | Presence-only smoke (task `test -s` / `rg -q`) | **Info only** for accuracy claims | Yes | Yes |

---

## 5. Structural gates (links, anchors, paths, titles, archive)

### 5.1 **V-LINK** — Local Markdown link resolution

**Detects:** Relative Markdown links that do not resolve to an existing file in the tree.

**Rules:**

1. Parse targets of the form `[text](path)` and `[text](path#anchor)`.
2. Skip `http:`, `https:`, `mailto:`, and pure `#anchor` targets for **offline Blocker** classification (external URLs are **Warning / unchecked offline** unless a pin is required).
3. Resolve relative to the source file directory.
4. Empty external gitlink directories: do **not** fail solely because content is missing when the path is an authorized empty pin (see EXTERNAL_DOCUMENTATION_SOURCES). A Canonical doc that **requires** readable content there must label the dependency as External.

**Manual offline smoke:**

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
# List relative markdown links under docs/ (review; full resolver is proposed tooling)
rg -n --glob '*.md' '\[[^\]]+\]\(([^)]+)\)' docs/ | head -n 50
```

**Strong pattern (existing):** `tests/test_iroh_operations_docs.py` resolves local links for contracted Iroh runbooks offline without network.

### 5.2 **V-ANCH** — Anchors and headings

**Detects:** `#fragment` targets that do not match a heading slug in the destination file.

**Limitation:** Full GitHub-style slugification is not yet a single checked-in library in this repo. Until a shared resolver lands (separately authorized):

- Contracted runbooks (example: Iroh operations docs) treat required **heading strings** as Blockers.
- Repo-wide anchor resolution is **Warning** / best-effort.

### 5.3 **V-PATH** — Referenced repository paths

**Detects:** Backtick or prose paths like `ipfs_kit_py/cli.py`, `pyproject.toml`, `.github/workflows/…` claimed as existing authority when the path is missing or is a known excluded clutter path presented as supported API.

**Rules:**

1. Packaging and entry-point claims must match `pyproject.toml` / setuptools package find.
2. Paths under `backup/`, `archive/`, `*_fixed.py`, `*.broken` must not be recommended as current entry points without a **Historical / compatibility** label (aligns with **G-EXCL**).
3. Generated paths under `docs/api_generated/` may be cited as inventory only, not as conceptual authority.

```bash
# Example: packaging scripts still present
rg -n '\[project.scripts\]' -A 30 pyproject.toml
test -f ipfs_kit_py/cli.py
```

### 5.4 **V-DUP** — Duplicate titles and competing navigation

**Detects:** Multiple top-level documents claiming the same role (multiple “canonical indexes”, duplicate H1 product names without class labels).

**Default severity:** **Warning** until KDOC-060 exclusive navigation lands. After exclusive hierarchy is merged, competing present-tense indexes become **Blockers**.

**Related evidence:** Freshness findings on multi-index competition (`docs/index.md`, `docs/README.md`, `docs/DOCUMENTATION_INDEX.md`).

### 5.5 **V-ARCH** — Archive and Historical isolation

**Detects:**

1. Canonical navigation presenting `docs/ARCHIVE/**`, `docs/implementation/**`, or status-report trees as current product truth without Historical labels.
2. Generated or Canonical material that promotes backup/fixed variants as supported API.

**Rules:**

| Tree | May be linked as | Must not be |
|---|---|---|
| `docs/ARCHIVE/**` | Historical provenance | Current install/ops guidance |
| `docs/api_generated/**` | Generated inventory | Conceptual architecture authority |
| `docs/py-ipld-*`, empty gitlinks | External / pin | Package public API |
| `backup/`, `archive/` (repo root) | Never as user entry | Supported surface |

---

## 6. Symbol, entry-point, snippet, and CLI gates

### 6.1 **V-SYM** — Symbols and entry points

**Detects:** Docs that name modules, classes, functions, or console scripts that are not present in packaging or AST of the referenced file.

**Preferred algorithm (offline, side-effect free):**

```text
1. Collect claimed symbols / scripts from the doc under test (contract list or allowlist).
2. For console scripts: compare to [project.scripts] in pyproject.toml.
3. For Python objects: ast.parse the target file; look for FunctionDef/ClassDef/Assign names.
4. NEVER import the module solely to prove existence when AST suffices.
```

**Blocker** when a Canonical API/CLI/MCP guide claims a public entry point that packaging does not expose. **Warning** when a Historical report mentions removed APIs without a supersession banner.

### 6.2 **V-CLI** — Safe CLI help checks

**Detects:** Documented commands that do not expose the claimed subcommands or flags.

**Allowed offline invocations:**

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
# Help-only; do not start daemons or install binaries
python -m ipfs_kit_py.cli --help 2>/dev/null || true
# Prefer focused tests that build parsers without network:
# python -m pytest tests/test_cli_import_verification.py tests/unit/test_minimal_cli.py -q
```

**Forbidden:** Running install/update paths, connecting to live RPC, or any command that mutates machine state as part of a documentation gate.

### 6.3 **V-SNIP** — Snippet hygiene

**Detects:**

| Check | Severity |
|---|---|
| `TODO` / `FIXME` / `PLACEHOLDER` / `TBD` in contracted Canonical runbooks | Blocker (see Iroh pattern) |
| Same markers in draft Proposed docs | Warning |
| Unfenced secrets or credential literals | **V-SENS** Blocker |
| Snippets that require network without labeling | Warning |
| Snippets that import side-effectful installers without `IPFS_KIT_AUTO_INSTALL_BINARIES=0` guidance | Warning → Blocker for install guides |

---

## 7. Generated documentation drift (**V-GEN** → **G-***)

This family **does not redefine** generated gates. It requires validation suites to **invoke** the generated documentation contract.

| Gate | Detects | Default severity |
|---|---|---|
| **G-HDR** | Unevaluated `$(date` / shell templates in `docs/api_generated/` | Blocker |
| **G-MOD** | Stale module inventory | Blocker |
| **G-SIG** | Stale public signatures | Blocker when signatures are in contract |
| **G-DEP** | Stale dependency list vs `pyproject.toml` | Blocker |
| **G-EX** | Stale examples index | Blocker (medium in contract; treat as fail for release-docs) |
| **G-TOOL** | Stale MCP/JS tool manifest | Blocker |
| **G-EXCL** | Backup/archive/external presented as public API | Blocker |
| **G-AGENT** | Misleading agent entry points | Blocker |
| **G-OWN** | Generator wrote wrong trees / protected paths | Blocker (critical) |
| **G-PROV** | Missing generated provenance | Blocker after refresh ownership lands |

**Anti-patterns that do not pass V-GEN:**

- File exists and is non-empty under `docs/api_generated/`.
- Raw module counts in prose without allowlist + signature structure.
- “Weekly cron usually ran” without check-mode diff.

**Offline smoke (manual until check-mode script is authorized):**

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
rg -n '\$\(date|\$\(' docs/api_generated/ || true
head -n 5 docs/api_generated/module_structure.md
head -n 5 docs/api_generated/dependencies.md
head -n 5 docs/api_generated/doc_status.md
rg -n '\[project.scripts\]' -A 20 pyproject.toml
test -f ipfs_kit_py/mcp_server/js_sdk/tools-manifest.json
```

Full normative detail: [`docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md`](../audits/GENERATED_DOCUMENTATION_CONTRACT.md) §6–§9.

---

## 8. Sensitive-data scan (**V-SENS**)

**Detects:** Secrets, credentials, private keys, tokens, and machine-specific state embedded in documentation or example configs under `docs/`.

### 8.1 Patterns (minimum)

Treat hits as **Blocker** unless the match is clearly a placeholder (`YOUR_TOKEN`, `changeme`, `***`, redacted examples) or a documented fake.

| Pattern class | Examples (illustrative) |
|---|---|
| PEM / private keys | `BEGIN RSA PRIVATE KEY`, `BEGIN OPENSSH PRIVATE KEY` |
| Cloud / API tokens | Long `AKIA…`, `ghp_…`, `xox[baprs]-…` style tokens in cleartext |
| Connection strings with passwords | `password=`, `://user:pass@` in non-redacted samples |
| Local absolute home paths with secrets files | Hard-coded `/home/…/.ipfs-kit/*secret*` as copy-paste credentials |

### 8.2 Offline scan sketch

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
rg -n --glob '*.md' -e 'BEGIN (RSA |OPENSSH )?PRIVATE KEY' -e 'ghp_[A-Za-z0-9]{20,}' \
  -e 'AKIA[0-9A-Z]{16}' docs/ || true
```

Placeholders and redaction guidance belong in credential guides; cleartext live secrets in docs are never Warnings.

---

## 9. Provenance and status metadata (**V-PROV**)

Aligned with DOCUMENTATION_GUIDE §3.

### 9.1 Required fields (Canonical program outputs)

| Field | Required |
|---|---|
| Document class | Always |
| Status (`active`, `draft`, `needs-verification`, `superseded`, …) | Canonical / Proposed |
| Last verified (`YYYY-MM-DD`) | Canonical |
| Owner / task | Program outputs |
| Evidence paths | Architecture guides, audits, ADRs |

### 9.2 Severity

| Case | Severity |
|---|---|
| New KDOC Canonical output missing class/status | **Blocker** |
| Legacy Canonical guide missing “Last verified” during migration | **Warning** until the owning rewrite task lands |
| Generated file missing generator provenance after KDOC-046 | **Blocker** (**G-PROV**) |
| Historical doc without Historical label when linked from Canonical nav | **Blocker** (**V-ARCH**) |

### 9.3 Status vocabulary (must remain distinguishable)

`draft` · `review` · `active` · `needs-verification` · `superseded` · `deprecated`

Change-trigger policy: when code/packaging in the blast radius changes, set affected Canonical docs to **needs-verification** until re-checked (see DOCUMENTATION_IMPACT_MAP).

---

## 10. Focused subsystem test matrix (**V-SUB**)

Documentation claims about behavior are only as strong as the **focused tests** that pin them. Prefer **default pytest discovery** (`tests/`, `tests/unit/`). Paths under `tests/integration/` and `tests/archived_stale_tests/` are **opt-in** and are not implied by `python -m pytest` at repo root.

### 10.1 Matrix (representative)

| Doc / surface class | Representative offline tests / commands | Notes |
|---|---|---|
| Packaging / version / scripts | Inspect `pyproject.toml`; import-path tests | No network |
| Package import / exports | `tests/test_ipfs_kit_import.py`, `tests/test_import_paths_validation.py` | Set auto-install off |
| CLI | `tests/test_cli_import_verification.py`, `tests/unit/test_minimal_cli.py` | Parser/help oriented |
| MCP++ | `tests/test_mcp_jsonrpc_conformance.py`, `tests/test_mcp_initialization.py`, receipt tests as applicable | Prefer unit/conformance over live server |
| Backends | `tests/test_backend_enhancements.py`, `tests/unit/test_configured_backends.py` | Side-effect-free registry preferred |
| VFS / content / WAL | `tests/test_vfs_*.py`, contract tests listed in vfs-contract-gates | Strong contract pattern |
| Iroh docs contract | `tests/test_iroh_operations_docs.py` (+ other `tests/test_iroh_*.py` offline subset) | Headings, links, commands |
| Install policy | `tests/test_auto_install_binaries.py` | Proves offline disable works |
| Architecture support | `tests/test_architecture_support.py` | When present |
| Generated API inventory | Manual/check-mode **G-*** | Not presence of `api_generated/` alone |

### 10.2 Running the matrix offline

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
python -m pytest tests/test_iroh_operations_docs.py -q
python -m pytest tests/test_cli_import_verification.py tests/unit/test_minimal_cli.py -q
python -m pytest -m "not slow and not requires_network" -q
# Do NOT claim tests/integration green unless run explicitly:
# python -m pytest tests/integration -q
```

### 10.3 Mapping doc changes to tests

Use [`DOCUMENTATION_IMPACT_MAP.md`](DOCUMENTATION_IMPACT_MAP.md) §5: classify the change, open only the owning docs, run the focused checks for that class. Agents must not substitute a full-suite green bar for a missing focused gate.

---

## 11. Limitations of presence-only tests (normative)

Program and task automation often uses lightweight checks such as:

```bash
test -s docs/some/path.md && rg -q "RequiredPhrase" docs/some/path.md
```

These are **useful admission and vocabulary gates**. They are **not** documentation quality or accuracy proof.

### 11.1 What presence-only checks prove

| Check | Proves | Does not prove |
|---|---|---|
| `test -s FILE` | File exists and is non-empty | Correct content, current APIs, safe examples |
| `rg -q "word" FILE` | Substring present | Semantics, completeness, or non-contradiction |
| Header/string contains “Production Ready” | Phrase appears | Release readiness or test health |
| `hasattr` / bare import smoke | Symbol importable in that environment | Operator runbook correctness; may hide side effects |
| Task validation command green | Task output file met a string contract | Broader corpus quality |

### 11.2 What must not be concluded from presence-only results

1. **Accuracy** of behavioral claims (needs source + focused tests; evidence ranks 1–3).
2. **Freshness** of generated inventories (needs **G-*** check mode / regenerate-diff).
3. **Link integrity** across the corpus (needs **V-LINK** resolution).
4. **Safety** of examples (needs **V-SENS** and snippet policy).
5. **Navigation exclusivity** (needs **V-DUP** / KDOC-060).
6. **Site build health** (Sphinx/MkDocs are not reproducible from the committed tree today; ADR-0009).

### 11.3 Classification of known weak tools

| Artifact | Classification |
|---|---|
| Task-level `test -s` + `rg -q` acceptance | **V-PRES** / Info for accuracy; Blocker only for “declared output missing” |
| `tools/verify_documentation_updates.py` | Historical-style presence and banner checker; hard-coded absolute paths; **not** an offline quality authority |
| `tests/test_documentation_verification.py` | Import/smoke oriented; can exercise side-effectful installers; **not** a substitute for structural gates |
| Strong content contracts (e.g. `tests/test_iroh_operations_docs.py`) | Acceptable offline accuracy evidence **for the contracted docs only** |
| `docs/testing/*` “100% coverage” reports | Historical campaign snapshots; not current gates |

### 11.4 Rule for authors, agents, and scorecards

> **Never** mark documentation accuracy, release readiness, or KDOC-G060 quality acceptance complete solely because presence-only tests passed. Record which **Blocker** families (**V-LINK**, **V-GEN**/**G-***, **V-SENS**, **V-PROV**, **V-SUB**, …) ran, which were skipped, and residual Warnings.

When only presence checks are available for a doc change, the evidence record MUST include:

```text
Gate: presence-only (V-PRES)
Commands: test -s <path> && rg -q '<phrase>' <path>
Result: exit 0
Limitation: does not prove accuracy, link integrity, freshness, or secret hygiene
Follow-up: run V-LINK smoke / focused V-SUB / G-* as applicable
```

---

## 12. Proposed offline validation recipe (manual today)

Until a unified checker is separately authorized, maintainers can approximate the **Release-docs** profile with the following **offline** recipe. All steps are read-only with respect to production state roots.

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
cd "$(git rev-parse --show-toplevel)"

# V-ENV / Python floor awareness
python -c 'import sys; assert sys.version_info >= (3,12), sys.version'

# V-GEN / G-HDR smoke
rg -n '\$\(date|\$\(' docs/api_generated/ && echo 'G-HDR suspect' || echo 'G-HDR smoke clean'

# V-SENS smoke
rg -n --glob '*.md' -e 'BEGIN (RSA |OPENSSH )?PRIVATE KEY' docs/ && echo 'V-SENS hit' || echo 'V-SENS smoke clean'

# V-PROV smoke on this contract and core governance docs
rg -q 'Document class|Last verified|Offline' docs/development/DOCUMENTATION_VALIDATION.md
rg -q 'Evidence ranking|Document class' docs/guides/DOCUMENTATION_GUIDE.md

# V-SUB samples (extend per change class)
python -m pytest tests/test_iroh_operations_docs.py -q

# V-PRES (admission only — not accuracy)
test -s docs/development/DOCUMENTATION_VALIDATION.md \
  && rg -q "Offline" docs/development/DOCUMENTATION_VALIDATION.md
```

Label every step’s result as **Blocker**, **Warning**, **Info**, or **Skipped** when filing a scorecard.

---

## 13. Reporting format (for scorecards and PR evidence)

A machine- or human-readable gate report SHOULD include:

```text
profile: release-docs | pr-docs | generated-only | report-only
tree: <git sha or "dirty worktree">
env:
  IPFS_KIT_AUTO_INSTALL_BINARIES: "0"
  network: offline-assumed
results:
  - id: V-LINK
    severity: blocker|warning|info|skipped
    status: pass|fail|skip
    findings: [<path>:<detail>]
  - id: G-MOD
    ...
summary:
  blockers: N
  warnings: M
  presence_only_used_for_accuracy: false   # must remain false for acceptance
```

**Fail-closed rule:** If a profile claims offline validation but **V-ENV** is violated (auto-install left on, network-required step run without label), the profile result is **failed** regardless of other greens.

---

## 14. Ownership, cadence, and separately authorized follow-ups

### 14.1 Ownership

| Concern | Owner |
|---|---|
| This validation specification | **KDOC-053** (this document) |
| Generated drift gate definitions | KDOC-043 contract; refresh KDOC-046 |
| Lifecycle / evidence ranking | KDOC-005 DOCUMENTATION_GUIDE |
| Maintenance workflow prose | KDOC-054 |
| Site toolchain decision | ADR-0009 / KDOC-029 |
| Navigation exclusivity | KDOC-060 |
| CI wiring / unified checker script | Separately authorized (not this task) |

### 14.2 Suggested cadence (consumers: KDOC-054 / scorecard)

| Event | Minimum gates |
|---|---|
| PR touching `docs/**` only | **V-LINK** on changed files, **V-SENS**, **V-PROV** on new Canonical files, **V-PRES** admission |
| PR touching public Python / packaging | **V-SUB** focused + impact map; **V-GEN** if inventories affected |
| Weekly generator run | **V-GEN** check mode before merge of generated PR |
| Pre-release | Full **Release-docs** profile; zero unwaived Blockers |

### 14.3 Separately authorized follow-ups

1. Versioned `tools/docs_validate.py` (or equivalent) implementing gate IDs with `--profile` and JSON report.
2. CI job that runs offline profiles without network and with `IPFS_KIT_AUTO_INSTALL_BINARIES=0`.
3. Shared Markdown link+anchor resolver used by both Iroh-style contracts and corpus-wide **V-LINK**.
4. Generator `--mode check` for **G-*** parity with JS SDK regenerate-diff CI.
5. Retirement or quarantine of weak presence tools (`tools/verify_documentation_updates.py`) so agents do not treat them as authority.

---

## 15. Acceptance mapping (KDOC-053)

| Acceptance criterion | How this document satisfies it |
|---|---|
| Gates are **reproducible / offline** | §2 Offline rules; §12 recipe; no network/daemon/site-build requirement |
| Distinguish **warnings** from **release blockers** | §3 severity model; per-gate defaults in §4–§10 |
| **Avoid imports with side effects** | §2.3 preference order; AST over import; auto-install disabled; CLI help-only |
| Explain limitations of **presence-only** tests | §11 full normative treatment; **V-PRES** Info-only for accuracy |
| Link/anchor, path/symbol/CLI, duplicate/archive, generated drift, sensitive data, provenance, subsystem matrix | §5–§10 gate families |
| Single declared output | This file only |
| Does not edit workflows/scripts | Spec only; §14.3 follow-ups |

---

## 16. Glossary

| Term | Meaning |
|---|---|
| **Blocker** | Release-blocking gate failure unless explicitly waived |
| **Warning** | Non-blocking finding that must still appear in reports |
| **Offline** | No required network, submodule fetch, binary download, or live daemon |
| **Presence-only** | Existence or substring checks without structural or behavioral proof |
| **Check mode** | Drift detection without writing generated artifacts |
| **Side-effect quarantine** | Modules that must not be imported during validation; inspect via AST/packaging only |
| **Focused test** | Default-discovery pytest (or named contract test) that pins a specific claim |
| **G-*** | Generated documentation drift gates (KDOC-043) |
| **V-*** | Authored/corpus validation gates defined in this document |

---

## 17. Document control

| Field | Value |
|---|---|
| Authoring task | KDOC-053 |
| Goal | KDOC-G060 — Repeatable freshness, generated-doc, and quality controls |
| Edit policy | Update when gate IDs, severity rules, or offline constraints change |
| Protected paths | Must never modify `docs/documentation_plan.md`, `docs/architecture/ipfs_kit_documentation.objectives.md`, `docs/architecture/ipfs_kit_documentation.todo.md` |
| Companion evidence | `docs/guides/DOCUMENTATION_GUIDE.md`, `docs/audits/GENERATED_DOCUMENTATION_CONTRACT.md`, `docs/development/testing_guide.md`, `docs/development/DOCUMENTATION_IMPACT_MAP.md`, `docs/architecture/decisions/0009-documentation-site-toolchain.md`, `tests/test_iroh_operations_docs.py` |
| Validation (this task) | `test -s docs/development/DOCUMENTATION_VALIDATION.md && rg -q "Offline" docs/development/DOCUMENTATION_VALIDATION.md` |
