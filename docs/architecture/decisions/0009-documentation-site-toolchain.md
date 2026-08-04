# ADR-0009: Documentation site and toolchain

> **Document class:** Proposed  
> **Decision status:** Proposed  
> Status: Proposed  
> **Date:** 2026-08-04  
> **Last verified:** 2026-08-04  
> **Evidence baseline:** current tree as of 2026-08-04 (`9f327af44b084e5df3fef34d7acc3d5c0013ed47`); freshness audit F-007 / F-008 in [`docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md`](../../audits/FRESHNESS_AND_CHANGE_AUDIT.md); map §10 in [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md)  
> **Authors:** KDOC-029 (agent-supervisor implementation)  
> **Confirmation owner:** documentation / developer-experience maintainers (generator contract, publish path, and site toolchain); packaging/CI maintainers for workflow landing; architecture agents must not accept this ADR alone  
> **Supersedes:** none  
> **Superseded by:** none  
> **Related guides:** [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §10, [`../../guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md), [`../../api_generated/README.md`](../../api_generated/README.md), [`../../audits/FRESHNESS_AND_CHANGE_AUDIT.md`](../../audits/FRESHNESS_AND_CHANGE_AUDIT.md)  
> **Related conflicts / U-IDs:** U-15 (generated-doc toolchain and navigation exclusivity); adjacent: KDOC-046 (generated refresh), KDOC-052 / KDOC-G060 (generated-doc contract), KDOC-060 (navigation exclusivity)

Process contract:
[`README.md`](./README.md) · Claim standard:
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)

---

## 1. Context

The repository maintains a large authored Markdown tree under `docs/`, generator-owned artifacts under `docs/api_generated/`, hand-maintained API notes under `docs/api/`, and **three** GitHub Actions paths that purport to build, publish, or refresh documentation. Freshness audit **F-008** and source-of-truth map **U-15** record that the dual site workflows are **not** a durable, reproducible documentation system from the committed tree.

| Force | Effect |
|---|---|
| Dual CI site builders (Sphinx in `docs.yml`, MkDocs in `pages.yml`) | Competing publish paths; neither is backed by a committed, complete site config in-repo |
| Missing Sphinx config | `docs.yml` invokes `sphinx-build` after `cd docs` with **no** `docs/conf.py` and **no** `docs/index.rst` |
| Ephemeral MkDocs config | `pages.yml` (and Docker documentation stage) **write** `mkdocs.yml` at build time; root has **no** committed `mkdocs.yml` |
| Generator vs hand-maintained API trees | `pages.yml` would write into `docs/api/`; weekly maintenance writes `docs/api_generated/`; hand files coexist without an exclusive owner contract |
| Stale / non-deterministic generated stamps | Committed `api_generated/` timestamps from 2025-10-29; some files retain unexpanded `$(date …)` templates (**F-007**) |
| Operator and agent demand for “how to build the docs” | Guides risk promising a reproducible Sphinx or MkDocs build that the tree does not support |

Without a recorded decision, contributor guides, CI claims, and Docker “documentation” stages will continue to over-promise. This ADR **compares options** and names the **owner decision** for the generator/publish path. It does **not** select a winner, and it does **not** claim that either current site workflow is reproducible.

**In scope:**

- Observed documentation build, publish, and generation surfaces (workflows, Docker stage, generators, output trees)
- Comparison of candidate toolchains: committed MkDocs, committed Sphinx, lightweight Markdown validation, and generated-reference-only approaches
- Publish destination policy framing (GitHub Pages vs in-repo artifacts only vs dual)
- Ownership boundaries among `docs/api/`, `docs/api_generated/`, and authored guides
- Confirmation owner, open options, migration/follow-up requirements after acceptance
- Explicit non-reproducibility of current Sphinx and MkDocs CI paths as of the evidence baseline

**Out of scope:**

- Editing `.github/workflows/*`, committing `mkdocs.yml` / `docs/conf.py`, or changing Dockerfile documentation stages (workflow/config changes require separate authorization; KDOC-029 conflict policy owns **this ADR body only**)
- Performing the generated-doc refresh itself (**KDOC-046**)
- Finalizing the generated-doc schema/contract tests (**KDOC-052** / **KDOC-G060**)
- Exclusive navigation index rewrite (**KDOC-060**)
- Accepting a toolchain by virtue of this draft (forbidden: index marks **Proposed (required)**)
- MCP runtime, cluster, or product-code authority decisions (other ADRs)

**Non-goal of this draft:** Declaring Sphinx or MkDocs “working,” choosing a publish host, or rewriting contributor commands as if a single durable site already ships.

---

## 2. Current behavior (evidence, not aspiration)

Present-tense claims describe the tree **as observed**. They assert **non-reproducibility** of the dual site workflows, not a chosen future toolchain.

### 2.1 Surface inventory

| Surface / path | Observed role | Evidence (source, test, packaging) | Status label |
|---|---|---|---|
| `.github/workflows/docs.yml` | Sphinx HTML build on `docs/**` / package changes; artifact + `gh-pages` deploy via JamesIves action | Workflow runs `cd docs && sphinx-build -b html . _build/html` after installing `sphinx`, `sphinx-rtd-theme`, `myst-parser` | **Non-reproducible site path** — no committed Sphinx project |
| `.github/workflows/pages.yml` | MkDocs Material site + Helm packaging; GitHub Pages deploy (`actions/deploy-pages`) | Workflow installs MkDocs plugins; **inline** Python writes `docs/api/*.md`; **`cat > mkdocs.yml`** creates ephemeral config; overwrites `docs/index.md` from root `README.md` | **Non-reproducible / conflicting site path** — no committed root `mkdocs.yml`; collides with hand-maintained `docs/api/` |
| `.github/workflows/auto-doc-maintenance.yml` | Weekly / dispatch generator for `docs/api_generated/` | Cron `0 9 * * 1`; uses pdoc + inline AST extractors; `contents: write` | **Active generator path** (output freshness separate) |
| `docs/conf.py` / `docs/index.rst` | Would be Sphinx project entry | **Absent** in tree (`test -f docs/conf.py` fails) | **Missing** |
| Root `mkdocs.yml` / `docs/mkdocs.yml` | Would be MkDocs project entry | **Absent** in tree | **Missing** (created only ephemerally in CI/Docker) |
| `docs/api/*.md` | Hand-maintained API / CLI / concepts notes | `api_reference.md`, `cli_reference.md`, `core_concepts.md`, `high_level_api.md` | **Authored** — risk of overwrite by `pages.yml` generation |
| `docs/api_generated/*` | Generator-owned module map, deps, status, agent guide | `module_structure.md` header **2025-10-29**; `doc_status.md` retains literal `$(date -u +"%Y-%m-%d %H:%M:%S UTC")`; README claims weekly maintenance | **Generated / stale relative to 2026 tree** (**F-007**) |
| `tools/generate_api_docs.py` | Separate MCP endpoint/doc generator (not the `api_generated` weekly path) | Script docstring: MCP server API docs | **Adjacent generator** — different contract |
| Dockerfile `documentation` stage + compose | Local MkDocs serve target | Dockerfile creates default `mkdocs.yml` **if missing**; `CMD mkdocs serve`; compose uses documentation target | **Ephemeral config pattern** (same class as `pages.yml`) |
| Authored Markdown tree `docs/**/*.md` | Primary human/agent documentation corpus | Inventory / plan treat Markdown as first-class; no default pytest asserts full-site build | **Primary content store** |
| Dual Pages deploy mechanisms | `docs.yml` → JamesIves `gh-pages` branch; `pages.yml` → `deploy-pages` artifact | Both workflows present and path-triggered on `docs/**` | **Competing publishers** |

### 2.2 Why neither current site workflow is reproducible

**Sphinx (`docs.yml`) — not reproducible from the committed tree:**

1. Build step assumes a Sphinx project rooted at `docs/` (`sphinx-build -b html . _build/html`).  
2. There is **no** `docs/conf.py` and **no** `docs/index.rst` (or equivalent checked-in Sphinx entry).  
3. Installing Sphinx packages does not create a project; a clean checkout cannot complete this build as written.  
4. Therefore CI claims of a durable Sphinx site from the committed docs tree are **unsafe**. This ADR **does not** claim the Sphinx workflow is reproducible.

**MkDocs (`pages.yml`) — not reproducible from the committed tree:**

1. There is **no** committed root `mkdocs.yml` (nor `docs/mkdocs.yml`).  
2. The workflow **synthesizes** `mkdocs.yml` in the job via heredoc, with a nav that does not match the real multi-hundred-file `docs/` layout.  
3. The job **generates** mkdocstrings stubs into `docs/api/` for every top-level `ipfs_kit_py/*.py`, which would **collide** with hand-maintained files already present under `docs/api/`.  
4. The job **overwrites** `docs/index.md` from root `README.md` and creates stub installation/quickstart pages, diverging from the maintained docs tree.  
5. Local Docker documentation stage repeats the “create default `mkdocs.yml` if missing” pattern rather than building a committed config.  
6. Therefore a clean checkout cannot reproduce the published site without re-running these destructive/synthetic steps. This ADR **does not** claim the MkDocs workflow is reproducible.

**Implication for guides and agents:** Until an option in §3.2 is accepted and landed in config, contributor docs must **not** promise `sphinx-build` or `mkdocs build` as working, durable commands against `main`. Label such tooling **Proposed** when mentioned.

### 2.3 Generated documentation posture

| Concern | Observed fact |
|---|---|
| Ownership intent | Map §10 and `DOCUMENTATION_GUIDE.md` treat `docs/api_generated/*` as generator-owned (hand edits out of policy) |
| Freshness | `module_structure.md` last updated **2025-10-29**; package module count and docs counts in `doc_status.md` do not match 2026 tree measurements cited in F-007 |
| Determinism | Unexpanded shell date templates in committed Markdown indicate broken generation heredocs |
| CI gate | No default offline pytest suite fails on generator drift for architecture-critical modules |
| Parallel API notes | `docs/api/` remains authored; relationship to `api_generated/` is an open owner sub-decision (map §10) |

### 2.4 Narrative summary

Documentation content is **primarily Markdown in-repo**. Site packaging attempts exist as **two incomplete CI workflows** plus a Docker stage, all of which depend on **missing or ephemeral** configuration. Generated inventories exist but are **stale** and not contract-tested. **No maintainer-accepted toolchain** currently defines a single reproducible site build or exclusive generator/publish path. Ambiguity is **U-15**; this ADR is the decision vehicle, not an acceptance.

---

## 3. Decision

**Status: Proposed**

### 3.1 Decision statement

**No documentation site toolchain or publish path is selected by this ADR.**

Maintainers must choose (or explicitly combine) options in §3.2 before:

- Contributor guides may treat a Sphinx or MkDocs build as the supported site command  
- CI may be described as producing a durable, reproducible docs site from the committed tree  
- `docs/api/` vs `docs/api_generated/` exclusivity and overwrite rules may be enforced as Accepted policy  
- Docker “documentation” stages may be documented as matching production publish  

Until promotion rules in [`README.md`](./README.md) §3.1 are met, all site toolchains remain **candidates**, and both current workflows remain **non-reproducible** as documented in §2.2.

Candidate decision framing for confirmation (not selected):

> The project’s canonical documentation toolchain shall be &lt;option id&gt;, with publish destination &lt;Pages / in-repo only / dual&gt;, generator output exclusivity &lt;api_generated policy&gt;, and migration steps for retiring or repairing non-chosen workflows.

### 3.2 Options (required — no winner selected)

Effects called for by KDOC-029: compare **committed MkDocs**, **Sphinx**, **lightweight Markdown validation**, and **generated-reference** approaches, plus migration/follow-up.

| Option | Summary | Fit / risk |
|---|---|---|
| **A — Committed MkDocs (Material) as canonical site** | Check in root `mkdocs.yml` (or agreed path) that reflects real `docs/` nav; remove ephemeral `cat > mkdocs.yml`; stop overwriting `docs/api/` and `docs/index.md` in CI; single Pages deploy; Docker stage uses the same committed config | Aligns with existing Material/Docker intent and plugin ecosystem (mkdocstrings, etc.); **migration cost**: rewrite nav for large tree, delete/repair `pages.yml` generators, reconcile or freeze hand `docs/api/`; dual-deploy race with `docs.yml` must end |
| **B — Committed Sphinx as canonical site** | Add `docs/conf.py` (+ index), Myst or rst entry, fix `docs.yml` as sole publisher; retire MkDocs Pages path or demote to experimental | Matches `docs.yml` naming; **high bootstrap cost** for a Markdown-first corpus; Myst config and toctree ownership required; still must resolve `api_generated` vs autodoc |
| **C — Lightweight Markdown validation (no full static site in CI)** | CI checks links, front-matter/class banners, forbidden stale claims, and optional markdownlint—**without** requiring Sphinx/MkDocs success; publish optional or manual | Lowest false-confidence risk; honest about Markdown-first tree; **no** pretty public site unless paired with D/E; agents still need clear “read `docs/`” guidance |
| **D — Generated-reference primary (`api_generated` + contract)** | Treat generator-owned reference as the machine-checked API surface; authored guides stay human; enforce refresh (KDOC-046) + schema/drift gates (KDOC-052); site theme optional later | Fixes F-007 class failures; clear ownership; **does not** alone replace navigation or user guides; requires exclusive write policy vs `docs/api/` |
| **E — Hybrid: Markdown validation + committed single site tool + generator contract** | Combine C + (A **or** B) + D: one committed site config, validation gates, generator exclusivity, one publish path | Highest long-term coherence; **largest** coordinated change set (workflows, Docker, generators, nav); must still pick A vs B for the site tool |
| **Status quo** | Leave dual non-reproducible workflows, stale generators, and competing `docs/api` / `api_generated` unlabeled as default | No false “we fixed docs CI” claim in this ADR body; **ongoing** contributor and agent confusion; F-007/F-008 remain High |

**Selected option (if any):** none yet — awaiting confirmation  

**Sub-decisions that must be answered with the selected option (may be deferred only if explicitly listed as follow-ups):**

1. **Publish destination:** GitHub Pages (which workflow/action), in-repo artifacts only, Read the Docs, or none.  
2. **API tree exclusivity:** keep both `docs/api/` and `docs/api_generated/` with roles; collapse one; or make `docs/api/` a thin stub (map §10 open item).  
3. **Overwrite policy:** forbid CI from writing into authored paths without a dedicated PR path.  
4. **Docker documentation stage:** track committed config or demote to “experimental local preview.”

---

## 4. Rationale (confidence-labeled)

**Accepted:**  

- The repository’s primary documentation corpus is Markdown under `docs/` (observed tree layout; program classification in the documentation plan / guide).  
- Packaging and product code do not substitute for a docs site config: site build is orthogonal to `pyproject.toml` console scripts.  
- ADR index and map register **U-15** / ADR-0009 as an open owner decision requiring confirmation (framework evidence, not a product runtime invariant).

**Proposed:**  

- A single **committed** site configuration (MkDocs **or** Sphinx, not both as peers) should eventually own public HTML publish, **or** the project should deliberately choose validation-only and stop advertising a site.  
- Generator output under `docs/api_generated/` should remain machine-owned with drift gates, independent of which site theme is chosen.  
- Competing Pages deployers (`docs.yml` vs `pages.yml`) should not both claim production publish after acceptance.  
- Hand-maintained `docs/api/` and generator trees need an exclusive ownership rule to prevent silent overwrite.

**Inferred:**  

- Ephemeral `mkdocs.yml` and missing `conf.py` are accidental incomplete migrations rather than intentional “config must be generated” design—structure suggests copy-paste CI without completing the project files.  
- Dual workflows likely accumulated across campaigns (Sphinx artifact path vs modern Pages action) without an explicit retirement.  
- Docker documentation stage defaults exist to make `docker compose` demos boot, not to define production docs authority.

**Unknown:**  

- Which public host (if any) maintainers want for the project site — unknown / maintainer confirmation needed.  
- Whether MkDocs Material is preferred over Sphinx for brand/nav reasons — unknown / maintainer confirmation needed.  
- Whether `docs/api/` hand notes should be rewritten into generators, stubs, or retained indefinitely — unknown / maintainer confirmation needed.  
- Acceptable CI cost/time for full site builds on every docs PR — unknown / maintainer confirmation needed.

---

## 5. Evidence

| Rank | Claim | Citation |
|---|---|---|
| 1 | Sphinx workflow invokes `sphinx-build` under `docs/` | `.github/workflows/docs.yml` (`Build documentation` step) |
| 1 | MkDocs workflow synthesizes config and generates into `docs/api/` | `.github/workflows/pages.yml` (`Build MkDocs site` step: `generate_api_docs`, `cat > mkdocs.yml`) |
| 1 | `docs/conf.py` absent; root `mkdocs.yml` absent | Workspace checks at evidence baseline; freshness audit **F-008** |
| 1 | Generated module structure stamp is 2025-10-29; status template unexpanded | `docs/api_generated/module_structure.md`, `docs/api_generated/doc_status.md`; audit **F-007** |
| 2 | Docker documentation stage creates default `mkdocs.yml` if missing | `Dockerfile` `documentation` stage |
| 3 | Generator-owned path policy for `api_generated/` | [`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md); [`docs/api_generated/README.md`](../../api_generated/README.md) |
| 4 | U-15 / ADR-0009 slot and Proposed requirement | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) aggregate table; [`README.md`](./README.md) §8.1 registry |
| 5 | Program task acceptance: remain Proposed; name owner; do not claim workflows reproducible | KDOC-029 in architecture todo (read-only for this task) |

**Evidence that is explicitly insufficient for Accepted status:** Existence of workflow YAML files; presence of MkDocs/Sphinx **dependency names** in CI or Docker; aspirational “GitHub Pages docs” prose in deployment guides; successful historical runs on a different tree shape (not re-verified here as green on current `main`).

---

## 6. Consequences

### 6.1 Positive

- Agents and guides gain a **single decision record** for toolchain/publish ambiguity (U-15).  
- Options A–E make migration work (KDOC-046, KDOC-052, KDOC-060, workflow PRs) attachable without inventing acceptance.  
- Explicit **non-reproducibility** of current Sphinx and MkDocs paths reduces false “docs build is green means site is real” conclusions.

### 6.2 Negative / costs

- Until acceptance, contributor onboarding still lacks one supported `build the site` command.  
- Dual workflows may continue to fail or produce misleading artifacts if left enabled.  
- Choosing any of A/B/E later implies non-trivial CI and nav maintenance cost.

### 6.3 Migration and compatibility

Migration is **not** performed by this ADR. After acceptance, expected follow-ups (illustrative, not scheduled here):

| If accepted… | Migration sketch |
|---|---|
| **A (MkDocs)** | Commit `mkdocs.yml`; rewrite nav or use awesome-pages/inclusion strategy; delete ephemeral generation in `pages.yml`; disable or delete Sphinx `docs.yml` deploy **or** demote it; align Docker stage; protect `docs/api/` from blind overwrite |
| **B (Sphinx)** | Add `conf.py` + index; configure Myst for Markdown; fix sole deploy workflow; retire MkDocs Pages path and Docker MkDocs defaults; map autodoc vs `api_generated` |
| **C (validation only)** | Add link/banner/lint jobs; mark site workflows experimental or remove deploy steps; update contributor guide commands to validation-only |
| **D (generated-reference)** | Land generator contract + refresh ownership; freeze hand edits; resolve `docs/api/` role; optional later site wrapper |
| **E (hybrid)** | Sequence: contract + validation first, then one committed site tool, then single publisher |
| **Status quo** | Keep candidate language; continue F-007/F-008 as open High findings |

Compatibility: authored Markdown remains valid under all options; only **packaging/publish** and **generator write paths** change.

### 6.4 Security and trust

- Docs CI with `contents: write` / Pages deploy tokens is a supply-chain surface; reducing dual publishers reduces accidental publish races.  
- Generators that import the package in CI must not require network install of unpinned tools beyond declared deps (policy to set at acceptance).  
- Credentials: none in this ADR; no host-specific secret paths.

### 6.5 Testing and verification

**While this ADR remains Proposed:**

```bash
# ADR body present and still Proposed
test -s docs/architecture/decisions/0009-documentation-site-toolchain.md \
  && rg -q "Status: Proposed" docs/architecture/decisions/0009-documentation-site-toolchain.md

# Structural non-reproducibility still holds (site project files absent)
test ! -f docs/conf.py
test ! -f mkdocs.yml
test ! -f docs/mkdocs.yml

# Dual site workflows still present as competing surfaces
test -f .github/workflows/docs.yml
test -f .github/workflows/pages.yml
```

**Tests / gates to require before Accepted (option-dependent):**

1. Clean-checkout command documented in the ADR and contributor guide produces the chosen artifact (site **or** validation report).  
2. CI job for the chosen path is green on a pristine tree without heredoc project synthesis.  
3. Generator exclusivity: no workflow writes into non-owned paths; drift gate for `api_generated` if D/E.  
4. Single publish description in operator/contributor docs; other path removed or clearly experimental.  
5. Docker documentation stage either matches committed config or is labeled non-production.

---

## 7. Alternatives considered

| Alternative | Why considered | Why rejected / deferred | Confidence |
|---|---|---|---|
| Claim current Sphinx workflow is reproducible | Workflow file exists and names sphinx-build | Missing `conf.py` / index; contradicts F-008 and acceptance criteria | **Accepted** as rejected claim |
| Claim current MkDocs workflow is reproducible | Workflow and Docker stage mention MkDocs | Ephemeral `mkdocs.yml`; destructive `docs/api/` generation; contradicts F-008 and acceptance criteria | **Accepted** as rejected claim |
| Agent-select Option A or B in this draft | Unblocks “how to build docs” wording | Violates KDOC-029 conflict policy, index **Proposed (required)**, and U-15 confirmation | **Accepted** as rejected for this task |
| Keep both Sphinx and MkDocs as peer production publishers | Avoid choosing | Dual non-reproducible paths amplify conflict; at most one should be production after acceptance | **Proposed** rejection of dual production publish |
| Delete all docs CI without a replacement decision | Stop failing jobs | Removes signal without defining validation or publish policy | **Proposed** deferral—status quo option covers temporary inaction with explicit costs |
| Treat `tools/generate_api_docs.py` as the site toolchain | Script exists | Targets MCP API narrative, not the full docs site or `api_generated` weekly contract | **Inferred** as wrong layer for U-15 |
| Status quo forever (no ADR body) | Avoid premature tooling choice | Leaves U-15 without a decision vehicle; index requires this file | **Proposed** rejection of permanent silence—this ADR records options instead |

---

## 8. Unknowns and owner confirmation

| Field | Value |
|---|---|
| **Confirmation owner** | Documentation / developer-experience maintainers for generator contract, publish path, and site toolchain choice; CI/packaging maintainers co-own workflow landing. Documentation agents may draft this record but **must not** flip status to Accepted without that confirmation (or an unambiguous implemented invariant meeting README §3.1). |
| **Confirmation question** | Which documentation toolchain policy is production authority: **A** (committed MkDocs site), **B** (committed Sphinx site), **C** (lightweight Markdown validation without a full static site), **D** (generated-reference primary with contract gates), or **E** (hybrid of validation + one committed site tool + generator contract)—and under that choice, what is the **sole** publish destination (or explicit “no public site”) and the **exclusivity rule** for `docs/api/` vs `docs/api_generated/`? |
| **What “Accepted” requires** | (1) Explicit maintainer selection of A/B/C/D/E (or a named refinement); (2) rank-1 evidence that the chosen path works from a clean checkout (committed config and/or validation commands green); (3) written migration for non-chosen workflows (disable, delete, or mark experimental); (4) generator overwrite/exclusivity policy; (5) update of this ADR status and confirmation section—not guide-only prose claiming a site build that the tree cannot run. |
| **Blocking for** | Contributor “build the docs” commands; any guide language that claims a reproducible Sphinx or MkDocs site from `main` as-is; exclusive generated refresh (**KDOC-046**); generated-doc contract (**KDOC-052**); navigation exclusivity (**KDOC-060**); Docker documentation stage as production-aligned; retirement of dual Pages publishers. |
| **Related U-IDs / conflicts** | **U-15** (this decision); map §10 generator/publish open items; F-007 / F-008; adjacent navigation exclusivity (KDOC-060). |

**Open unknowns:**

1. Preferred public documentation host (GitHub Pages vs none vs third party) — unknown / maintainer confirmation needed  
2. MkDocs vs Sphinx preference if a full site is desired — unknown / maintainer confirmation needed  
3. Long-term fate of hand-maintained `docs/api/*` — unknown / maintainer confirmation needed  
4. Whether weekly auto-commit generation should become PR-based or CI artifact-only — unknown / maintainer confirmation needed  
5. Whether validation-only (C) is acceptable mid-term while A/B config is authored — unknown / maintainer confirmation needed  
6. Resource budget for building the full docs tree on every PR — unknown / maintainer confirmation needed  

---

## 9. Supersession and relationships

| Relation | ADR / doc |
|---|---|
| Supersedes | none |
| Superseded by | none |
| Related ADRs | ADR-0003 (MCP runtime—orthogonal to docs toolchain); other subsystem ADRs may cite generated API docs but do not own publish path |
| Architecture guides | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §10; future contributor/docs build sections must stay status-honest while this remains Proposed |
| Program audits | [`../../audits/FRESHNESS_AND_CHANGE_AUDIT.md`](../../audits/FRESHNESS_AND_CHANGE_AUDIT.md) F-007, F-008 |
| Source-of-truth map | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) U-15 |
| Follow-on tasks (not this ADR’s edit scope) | KDOC-046 generated refresh; KDOC-052 generated contract; KDOC-060 navigation; separate workflow PRs after acceptance |

---

## 10. Follow-up actions

| Action | Owner | Notes |
|---|---|---|
| Maintainer selects A/B/C/D/E (+ publish + API exclusivity) | Confirmation owner (§8) | Required to leave Proposed |
| Land committed site config **or** validation-only CI | CI + docs maintainers | Only after selection; out of scope for KDOC-029 body |
| Retire or demote non-chosen site workflow | CI maintainers | Avoid dual production Pages deploys |
| Generator refresh + drift contract | KDOC-046 / KDOC-052 | Independent of theme choice; blocked on exclusivity policy for full “Accepted” generator story |
| Navigation exclusivity aligned with chosen publish tree | KDOC-060 | Do not invent site IA before toolchain choice if it hard-codes MkDocs/Sphinx assumptions |
| Update contributor guide build commands with status-honest language | Docs maintainers | While Proposed: do not promise reproducible Sphinx/MkDocs |
| Align Docker documentation stage with decision | Packaging maintainers | Match committed config or label experimental |
| Re-verify F-007 / F-008 after landing | Docs / audit owners | Close or downgrade only with clean-checkout evidence |

---

## 11. Review checklist (authors)

- [x] Filename is `0009-documentation-site-toolchain.md` (not left as 0000 for a real decision)
- [x] Banner **Decision status** matches §3 **Status** (`Proposed`)
- [x] **Current behavior** is evidence-backed and separate from the proposal
- [x] No present-tense “the system does X” for Proposed-only intent (site tool choice)
- [x] Every material *why* uses **Accepted / Proposed / Inferred / Unknown**
- [x] No Inferred or Unknown claim is written as Accepted history
- [x] Evidence table prefers ranks 1–4 for factual claims; acceptance blocked without confirmation
- [x] Alternatives include status quo and explicit rejection of “current workflows are reproducible”
- [x] Confirmation owner and question filled (Proposed)
- [x] No secrets, live tokens, or host-specific credential paths
- [x] `docs/architecture/decisions/README.md` was **not** edited by this task
- [x] Does **not** claim either current Sphinx (`docs.yml`) or MkDocs (`pages.yml`) workflow is reproducible
- [x] Names owner decision (generator/publish path / toolchain — U-15)
- [x] Compares committed MkDocs, Sphinx, lightweight Markdown validation, and generated-reference options plus migration/follow-up

---

## Appendix A — Status and confidence cheat sheet

**Decision status (header / §3):**  
`Proposed` · `Accepted` · `Rejected` · `Superseded` · `Deprecated` · `Unknown`

**Rationale confidence (§4 markers):**

```markdown
**Accepted:** …
**Proposed:** …
**Inferred:** …
**Unknown:** … unknown / maintainer confirmation needed
```

**Forbidden without confirmation + evidence:**

- Presenting ephemeral MkDocs or missing-config Sphinx as the supported contributor build  
- Declaring a sole publish path Accepted from workflow filenames alone  
- Hand-editing `docs/api_generated/` bodies as if they were authored canon  

See [`README.md`](./README.md) §§3–4 for full promotion rules.
