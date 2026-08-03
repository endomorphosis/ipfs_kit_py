# Documentation lifecycle, evidence, and style guide

| Field | Value |
|---|---|
| Document class | **Canonical** (governance standard) |
| Task | KDOC-005 — Establish documentation lifecycle, evidence, and style rules |
| Goal | KDOC-G013 |
| Track | governance |
| Status | active |
| Last verified | 2026-08-03 |
| Plan authority | [`docs/documentation_plan.md`](../documentation_plan.md) §3 (Documentation contract) |
| Scope | All authored, generated, historical, external, and proposed material under `docs/` |
| Non-goals | Navigational rewrite of competing indexes; production-code changes; fetching external gitlinks |

This guide is the **documentation contract** consumed by every later KDOC task.
It defines how documents are classified, how claims are evidenced, how design
rationale is labeled for confidence, what sections architecture guides must
contain, and how humans and agents review documentation before merge.

> **Note:** Earlier versions of this file were an integration navigation hub.
> Navigation and product entry paths are owned by later exclusive-navigation
> tasks (for example KDOC-060). This file is the lifecycle and claim standard
> only; it does not re-home the documentation tree.

---

## 1. Purpose and audience

### 1.1 Purpose

- Keep documentation **trustworthy, current, and rationale-rich**.
- Distinguish **what is true of the current tree** from **history, proposals,
  generated output, and external material**.
- Prevent agents and authors from inventing architectural history or promoting
  inference to accepted fact.
- Provide mechanical and human review checklists so later tasks can be audited
  for authority, evidence, status, and maintenance metadata.

### 1.2 Audience

| Audience | Use of this guide |
|---|---|
| Human maintainers | Accept or reject claim labels, ADRs, and authority promotions |
| Documentation agents | Write and review docs under KDOC task contracts |
| Reviewers (PR / program) | Apply the human and agent checklists in §12 |
| Architecture / ADR authors | Required sections, rationale labels, evidence ranking |

---

## 2. Authority (document) classes

Every maintained document must make its **authority class** clear—in a
document header table, banner, or first-section status line. Authority class
describes the document as a whole (or a clearly marked section).

| Class | Meaning | Update rule | May recommend as current? |
|---|---|---|---|
| **Canonical** | Current conceptual, task, operational, or reference guidance | Must cite current source/tests and carry a verification date or baseline commit | Yes |
| **Generated** | Deterministic output from code or packaging metadata | Never hand-maintained except generator templates; drift must be detectable | Only as inventory/reference, not as conceptual authority |
| **Historical** | Dated implementation report, migration record, result, or superseded design | Retained for provenance; not rewritten into present tense as guidance | No |
| **External** | Vendored or gitlinked upstream material | Ownership and revision explicit; excluded from authored-doc coverage | Only when scoped as upstream contract |
| **Proposed** | Design, ADR, or program target not yet reflected in current behavior | Must not be written as an implemented capability | No (mark as proposal) |

### 2.1 Mixed and program-control material

| Label | When to use |
|---|---|
| **Mixed** | A directory or long document contains more than one class; sub-paths or sections must state class explicitly |
| **Program-control** | Operator-protected plan/board/objectives inputs (for example `docs/documentation_plan.md`, objective heap, task board). Workers never edit these as task outputs |

### 2.2 Class promotion and demotion

| Transition | Requires |
|---|---|
| Proposed → Canonical | Implementation evidence (source + tests or packaging), maintainer acceptance where the claim is architectural intent, verification date |
| Historical → Canonical | Re-verification against current tree; rewrite of present-tense claims; new evidence citations |
| Canonical → Historical | Supersession notice, date, and pointer to the replacement canonical doc |
| Hand edit of Generated | Forbidden except generator templates; regenerate instead |
| Inference → Accepted rationale | Evidence hierarchy §4 satisfied; label change only with source/history/ADR support |

Agents must **not** reclassify a document solely to make a task appear complete.

---

## 3. Provenance and maintenance metadata

Canonical and Proposed authored documents carry a short header. Generated and
Historical documents use the subset that applies (at minimum class and date
or generator identity).

### 3.1 Required provenance fields

| Field | Required for | Description |
|---|---|---|
| **Document class** | All | Canonical, Generated, Historical, External, or Proposed |
| **Status** | Canonical, Proposed | e.g. `active`, `draft`, `superseded`, `deprecated` |
| **Last verified** | Canonical | ISO date (`YYYY-MM-DD`) when claims were checked against the tree |
| **Tree baseline** | Canonical (preferred) | Git commit SHA or tag used for verification |
| **Owner / task** | Authored program outputs | KDOC task id or human owner |
| **Evidence** | Architecture guides, ADRs, audits | Paths to source, tests, packaging, or prior audits |
| **Supersedes / superseded by** | When replacing docs | Explicit linkage so readers do not follow stale paths |

### 3.2 Recommended optional fields

| Field | Use |
|---|---|
| Goal id | Objective-heap id (e.g. `KDOC-G013`) |
| Track | Program track (`governance`, `architecture`, …) |
| Change triggers | What code/docs changes force a re-review (§11) |
| Related ADRs | Links to decision records with status preserved |
| Scope / non-goals | First-section bounds for architecture guides |

### 3.3 Example header (Canonical)

```markdown
| Field | Value |
|---|---|
| Document class | Canonical |
| Status | active |
| Last verified | 2026-08-03 |
| Tree baseline | `abc1234…` |
| Owner / task | KDOC-01x |
| Evidence | `ipfs_kit_py/…`, `tests/…` |
```

### 3.4 Example banner (Historical)

```markdown
> **Historical.** Completion report dated 2026-02. Not current guidance.
> See [current architecture map](../architecture/…) for present behavior.
```

### 3.5 Example banner (Proposed)

```markdown
> **Proposed.** Design intent only. Not implemented as described.
> Do not cite this document as production behavior.
```

---

## 4. Evidence ranking (source policy)

Claims about behavior, surfaces, and architecture are ordered by authority.
Higher ranks override lower ranks when they conflict. Conflicts must remain
**explicit**—do not silently discard the weaker claim without recording the
disagreement.

| Rank | Source | Typical use |
|---|---:|---|
| 1 | Executable behavior and focused tests | “What runs today” |
| 2 | Packaging and entry-point metadata | Console scripts, extras, package exports |
| 3 | Public source contracts, schemas, and docstrings | Interfaces, registries, config schemas |
| 4 | Git history and **accepted** decision records | Why a choice was made (when recorded) |
| 5 | Current documentation | Navigation and synthesis—never sole proof of novel facts |
| 6 | Inference | Plausible reading of code/docs without direct proof |

### 4.1 Evidence citation rules

- Prefer **paths** in the current tree (`ipfs_kit_py/…`, `tests/…`,
  `pyproject.toml`) over narrative “as everyone knows.”
- Prefer **focused tests** that assert the behavior over incidental coverage.
- For packaging claims, cite `pyproject.toml`, setup metadata, or console-script
  entry points—not only README prose.
- For history-only claims, cite commit, PR, or dated Historical document.
- If ranks conflict, state both sides and label the resolution status
  (`unresolved`, `compat-shim`, `deprecated path`, etc.).

### 4.2 What does **not** count as sufficient evidence

- Another undocumented claim in the same or adjacent Markdown file.
- Generated module counts or inventory size as proof of architectural intent.
- Passing a full pytest suite without a focused test or contract that pins the
  claim under discussion.
- Importing optional modules at runtime solely to inventory them when
  AST/static inspection is enough.
- Uninitialized external gitlinks or fetched upstream docs (do not initialize
  or fetch them for evidence in this program).

### 4.3 Offline and validation constraints

- Set `IPFS_KIT_AUTO_INSTALL_BINARIES=0` for documentation validation runs.
- Prefer static/AST inspection over import-heavy discovery.
- Do not initialize or fetch external documentation gitlinks.
- Validation that only checks file existence is insufficient for claim quality;
  task-level `rg` gates prove presence of required vocabulary, not truth of
  every sentence—authors remain responsible for evidence ranking.

---

## 5. Rationale confidence labels

Design rationale answers *why* a structure, boundary, or trade-off exists.
**Rationale confidence is independent of document authority class.** A
Canonical guide may still contain Inferred or Unknown rationale paragraphs.

### 5.1 Distinguishing the four labels

These four labels must remain **distinguishable in prose and in review**.
Authors use the exact lead-in words (or equivalent bold markers) so humans and
agents can scan for confidence.

| Label | Marker (use in prose) | Meaning | Allowed actions |
|---|---|---|---|
| **Accepted** | `**Accepted:**` | Maintainer-accepted or strongly evidenced design intent (implementation + tests/history/ADR) | Cite as design basis; link accepted ADR when one exists |
| **Proposed** | `**Proposed:**` | Intentional design direction not yet accepted or not yet reflected in current behavior | Discuss trade-offs; must not be written as shipped behavior |
| **Inferred** | `**Inferred:**` | Plausible explanation from code/structure without maintainer record | Help readers orient; never promote to Accepted without new evidence |
| **Unknown** | `**Unknown:**` / `unknown / maintainer confirmation needed` | No reliable basis for *why* | Record the gap; ask for confirmation; do not invent history |

### 5.2 Rules of use

1. An **Inferred** rationale must be labeled **Inferred**. Do not narrate it as
   historical fact (“was chosen because…” without evidence).
2. An **Unknown** rationale is recorded as **unknown / maintainer confirmation
   needed**. Leaving a confident-sounding vacuum is worse than an explicit gap.
3. A **Proposed** rationale or design must not be phrased as an implemented
   capability (“the system does X” when only a design doc says it should).
4. An **Accepted** rationale requires rank-1–4 evidence (§4), not rank-5–6 alone.
5. Agents must not turn a plausible explanation into historical fact.
6. Promoting **Inferred → Accepted** or **Proposed → Accepted** is a
   maintainer/ADR action with evidence—not a side effect of rewriting a guide.

### 5.3 Worked examples

**Accepted**

```markdown
**Accepted:** Optional dependencies are imported lazily so importing
`ipfs_kit_py` does not require every extra to be installed. Evidence:
lazy import sites in `ipfs_kit_py/…`, packaging extras in `pyproject.toml`,
and focused tests under `tests/…`.
```

**Proposed**

```markdown
**Proposed:** A single documentation landing page should replace the three
competing indexes. This is program intent (KDOC navigation wave), not the
current tree layout.
```

**Inferred**

```markdown
**Inferred:** The dual async/sync surfaces appear to exist for gradual
migration and caller compatibility. No accepted ADR yet records the original
decision; treat as inference pending maintainer confirmation.
```

**Unknown**

```markdown
**Unknown:** Why the legacy module path remains exported alongside the
registry-based path is unknown / maintainer confirmation needed. Document
both paths and their tests; do not invent a retirement timeline.
```

### 5.4 Anti-patterns (fail review)

| Anti-pattern | Correction |
|---|---|
| “We chose X for performance” with no tests, history, or ADR | Label **Inferred** or **Unknown**; cite what is known |
| Writing a Proposed ADR body in present tense as production behavior | Use **Proposed** markers; separate “current behavior” section |
| Promoting inference to Accepted because the prose “sounds right” | Keep **Inferred** until evidence exists |
| Omitting rationale entirely for a major boundary | Add **Unknown** + confirmation request |
| Mixing Accepted and Proposed claims in one unlabeled paragraph | Split sentences; label each |

---

## 6. Document lifecycle

### 6.1 Lifecycle states

```text
draft ──► review ──► active (Canonical or Proposed)
                       │
                       ├──► needs-verification (trigger fired)
                       │         │
                       │         └──► active (re-verified) or Historical
                       │
                       └──► superseded ──► Historical
```

| State | Meaning |
|---|---|
| **draft** | Work in progress; not linked as current guidance |
| **review** | Awaiting human or agent checklist pass |
| **active** | Published under its authority class |
| **needs-verification** | Change trigger fired; claims may be stale |
| **superseded** | Replacement exists; retain for provenance as Historical |

### 6.2 Create

1. Confirm the owning KDOC task (or human owner) and declared output path.
2. Set authority class and provenance fields before substantial prose.
3. Inspect implementation, packaging, and focused tests before writing claims.
4. Prefer stable concepts over exhaustive inventories in authored guides;
   put exhaustive signatures and module listings in Generated/reference material.

### 6.3 Update

1. Re-open evidence paths; do not copy claims from older docs without
   re-checking ranks 1–3.
2. Update **Last verified** and tree baseline when material claims change.
3. Preserve Historical reports; do not “fix” them into present tense in place.
4. When behavior changes, update Canonical guides and ADRs; add a Historical
   note only if a dated record is useful.

### 6.4 Verify

1. Walk claims against source/tests (or packaging) offline.
2. Confirm links among Canonical docs resolve (broken links are defects).
3. Confirm rationale labels still match available evidence.
4. Record verification date even when no prose change was required.

### 6.5 Supersede and archive

1. Add `superseded by` to the old document and point readers to the new path.
2. Reclassify as **Historical** when the document is no longer current guidance.
3. Mass moves of Historical material are owned by dedicated history tasks;
   do not casually relocate large trees from an unrelated task.

### 6.6 Generated documents

- Live under generator-owned paths (for example `docs/api_generated/`).
- Refresh only via generators or the program’s generated-doc refresh task.
- Drift detection (generation date, module coverage, hash/CID if used) must be
  possible without reading every line by hand.
- Authored conceptual guidance must not be hand-edited into Generated files.

---

## 7. Required architecture-guide sections

Every **Canonical** architecture guide under `docs/architecture/` (and any
document that claims to be a subsystem architecture guide) contains the
following sections. Order may vary slightly; content must not be omitted
without an explicit “N/A with reason” note.

| # | Section | Intent |
|---|---|---|
| 1 | Scope and explicit non-goals | Bounds the guide; prevents scope creep |
| 2 | Supported/canonical surfaces and compatibility status | Distinguishes primary paths from shims |
| 3 | Component ownership and source-of-truth paths | Who owns what; where code lives |
| 4 | Data flow and control flow | With a small diagram where useful (§9) |
| 5 | Invariants and consistency or ordering guarantees | What must always hold |
| 6 | Process, async, and lifecycle boundaries | Threads, processes, AnyIO/asyncio/sync |
| 7 | Trust boundaries and sensitive-data handling | Secrets, auth, multi-tenant edges |
| 8 | Expected failures, degraded modes, and observability | Failure is documented, not omitted |
| 9 | Extension points and safe modification guidance | How to extend without breaking invariants |
| 10 | Design rationale, trade-offs, and rejected alternatives | With **Accepted / Proposed / Inferred / Unknown** labels |
| 11 | Tests or fixtures that verify the behavior | Rank-1 evidence pointers |
| 12 | Change triggers and last-verified baseline | Maintenance contract (§11) |

### 7.1 Task-oriented guides and operations docs

Task guides (`docs/guides/`), operations runbooks (`docs/operations/`), and
integration docs adapt the list:

- Always: scope, current procedure or behavior, prerequisites, evidence or
  verification steps, security constraints for examples.
- Include rationale sections when the guide asserts *why*, not only *how*.
- Mark optional/daemon/network prerequisites explicitly.

### 7.2 ADRs

ADR framework details are owned by the decisions track (KDOC-G030/G031). This
guide requires every ADR to:

- State status (`Proposed`, `Accepted`, `Deprecated`, `Superseded`, …).
- Separate current behavior from target behavior when they differ.
- Label rationale confidence per §5.
- Cite evidence per §4.
- Never present a Proposed decision as Accepted.

---

## 8. Writing style and claim hygiene

### 8.1 Voice and tense

- Use present tense for **current** behavior only when rank-1–3 evidence supports
  it.
- Use future or explicit **Proposed** markers for intended work.
- Use past tense for Historical reports and migration narratives.
- Prefer short, direct sentences; avoid marketing tone in architecture docs.

### 8.2 Claim hygiene

| Rule | Detail |
|---|---|
| No silent aspirations | Do not describe stubs, fallbacks, archived files, or optional adapters as production defaults without evidence |
| No secret material | Never put real credentials, live tokens, private keys, or host-specific secret paths in examples |
| No host-specific secrets as defaults | Use placeholders (`$API_TOKEN`, `/path/to/…`) |
| Stable concepts over inventories | Authored guides teach structure; Generated docs list modules/signatures |
| Compatibility is labeled | Shims, deprecated paths, and dual implementations are named as such |
| Conflicts stay visible | Unresolved authority is better than a false single story |

### 8.3 Agent writing rules (from program contract)

- Inspect implementation and focused tests before editing a claim.
- Prefer static inspection over importing optional modules to inventory them.
- Set `IPFS_KIT_AUTO_INSTALL_BINARIES=0` for documentation validation.
- Do not initialize or fetch external documentation gitlinks.
- Use runnable, offline examples by default; mark daemon, credential, network,
  or platform prerequisites explicitly.
- Record code defects discovered during documentation work as documentation
  gaps or follow-ups—do not silently “fix” production code in a docs-only task
  unless a separately authorized program expands scope.

### 8.4 Terminology

- Prefer glossary terms once `docs/architecture/GLOSSARY.md` exists (KDOC-006).
- Do not redefine implementation contracts in prose when a normative schema or
  glossary entry exists—link instead.
- Flag ambiguous terms rather than inventing competing definitions.

---

## 9. Diagrams, links, accessibility

### 9.1 Diagrams

- Prefer small, bounded diagrams (ASCII or fenced text is fine) over large
  unmaintained graphics.
- Every diagram has a one-line caption stating what is in scope.
- Diagram notation must match prose labels (same component names as source
  paths or glossary terms).
- Do not imply a single process or trust domain when multiple exist.
- When uncertain, a list of components and edges is better than a decorative
  but wrong box diagram.

### 9.2 Links

- Prefer repository-relative links that work in GitHub and offline clones.
- Link to Canonical docs for current guidance; link to Historical docs only
  with Historical context.
- Do not deep-link into Generated files as the sole conceptual explanation.
- When a target is Proposed or missing, say so instead of linking as if live.

### 9.3 Accessibility and readability

- Use descriptive headings; avoid heading-only emphasis without body text.
- Put meaning in text, not only in color or emoji.
- Tables need clear headers; wide tables should still be scannable in plain
  text.
- Code blocks declare a language when applicable.
- Alt-style descriptions: if a diagram is non-textual later, provide an
  equivalent textual structure list.

---

## 10. Examples and security

### 10.1 Examples policy

| Preference | Rule |
|---|---|
| Offline first | Examples run without network when possible |
| Runnable | Copy-paste paths and module names match the tree |
| Prerequisites explicit | Daemon, credentials, platform, extras called out up front |
| Minimal surface | Show the stable API, not every optional parameter |
| Failure paths | At least note common errors when documenting operations |

### 10.2 Security policy

- **Never** embed real credentials, tokens, session cookies, or private keys.
- **Never** document production secret values “for convenience.”
- Redact logs and sample configs (`Authorization: Bearer <redacted>`).
- State trust boundaries when examples cross process, network, or user
  boundaries.
- Credential *references* (env var names, config keys) are fine; values are not.
- Threat-relevant defaults (bind addresses, auth off/on) must match real
  packaging/docs evidence—or be labeled Proposed/Inferred.

### 10.3 Example marker block

```markdown
**Prerequisites:** local package install; `IPFS_KIT_AUTO_INSTALL_BINARIES=0`.
**Network:** none.
**Secrets:** none (uses placeholder `API_TOKEN` from the environment).
```

---

## 11. Change triggers and review cadence

### 11.1 Triggers that force documentation review

Any of the following should set affected Canonical docs to
**needs-verification** (or open a follow-up task):

| Trigger | Typical docs impact |
|---|---|
| Public Python export or package entry-point change | API, runtime, integration guides |
| CLI parser / command surface change | CLI reference, quick starts |
| MCP/tool registry or server entry change | MCP control-plane guides |
| Backend plugin registry or storage contract change | Storage, VFS, operations |
| Auth, credential, or config precedence change | Trust, configuration, security runbooks |
| Async/sync boundary or lifecycle ownership change | Async architecture, operations |
| Generator output schema or module coverage change | `api_generated/` drift process |
| ADR acceptance, deprecation, or supersession | Linked architecture guides |
| Test removal that was the sole rank-1 evidence for a claim | Claim must be re-evidenced or downgraded |

### 11.2 Cadence expectations

- Program tasks re-verify when they touch a claim.
- Generated docs follow automation schedule; authored Canonical docs do not
  rely on that schedule alone.
- A verification date older than a major surface change is a freshness risk
  even if the prose still “looks fine.”

---

## 12. Review checklists

Use these checklists before marking a documentation task complete or approving
a documentation PR. **Both** human judgment (intent, product truth) and agent
mechanics (labels, evidence, metadata) are required for architecture and ADR
content.

### 12.1 Human reviewer checklist

- [ ] **Authority class** is correct for the document (Canonical / Generated /
      Historical / External / Proposed); banners match class.
- [ ] **Present-tense behavior** claims match what maintainers believe the
      product actually does—not only what a model inferred.
- [ ] **Rationale labels** are honest:
  - Accepted claims have real acceptance or strong multi-source evidence.
  - Proposed work is not sold as shipped.
  - Inferred explanations are not phrased as history.
  - Unknowns are explicit where intent is missing.
- [ ] **Trade-offs and rejected alternatives** are credible; nothing important
      is papered over to force a single narrative.
- [ ] **Security**: no secrets, no dangerous copy-paste defaults without
      warnings; trust boundaries are understandable.
- [ ] **Audience fit**: a new contributor or operator can act on the doc
      without reverse-engineering the whole repo.
- [ ] **Supersession**: if this replaces another doc, the old path is clearly
      Historical or redirected.
- [ ] **Program scope**: docs-only tasks did not silently “fix” unrelated
      production code or protected plan/board/objectives files.

### 12.2 Agent reviewer checklist

- [ ] **Declared output path** matches the task contract; no undeclared path
      edits outside allowed trees.
- [ ] **Protected paths** untouched (`docs/documentation_plan.md`, objective
      heap, task board, and any operator-protected files).
- [ ] **Provenance header** present for Canonical/Proposed authored docs
      (class, status, last verified, evidence or baseline as applicable).
- [ ] **Evidence ranking** respected: novel behavioral claims cite source
      and/or focused tests (or packaging); inference is labeled.
- [ ] **Rationale vocabulary** present and distinguishable where rationale
      appears: **Accepted**, **Proposed**, **Inferred**, **Unknown** (or
      `unknown / maintainer confirmation needed`).
- [ ] **Architecture section set** complete for architecture guides (§7), or
      explicit N/A with reason.
- [ ] **No Generated hand-edits** outside generator templates.
- [ ] **Examples** offline-default, prerequisites marked, no live secrets.
- [ ] **Links** repository-relative and not asserting missing targets as live.
- [ ] **Change triggers** section present or inherited for Canonical
      architecture material.
- [ ] **Validation commands** from the task definition pass on the worktree.
- [ ] **Conflicts** with other docs/source are recorded, not deleted to force
      green narrative.
- [ ] **Environment**: validation considered `IPFS_KIT_AUTO_INSTALL_BINARIES=0`;
      no external gitlink fetch.

### 12.3 Quick pre-merge gate (both)

| Check | Pass criterion |
|---|---|
| Class | One clear authority class (or Mixed with section labels) |
| Evidence | Rank-1–3 for behavioral claims; else labeled weaker |
| Rationale | Four-way labels distinguishable; no silent promotion |
| Safety | No secrets; prerequisites explicit |
| Maintenance | Last verified / baseline / triggers for Canonical guides |
| Scope | Only declared outputs modified |

---

## 13. Status and vocabulary quick reference

### 13.1 Authority classes

`Canonical` · `Generated` · `Historical` · `External` · `Proposed`
(+ `Mixed`, `Program-control` where needed)

### 13.2 Rationale confidence

`Accepted` · `Proposed` · `Inferred` · `Unknown`
(`unknown / maintainer confirmation needed`)

### 13.3 Lifecycle states

`draft` · `review` · `active` · `needs-verification` · `superseded`

### 13.4 Evidence ranks (high → low)

1. Tests / executable behavior  
2. Packaging / entry points  
3. Public source contracts  
4. Git history / accepted ADRs  
5. Current documentation  
6. Inference  

---

## 14. Relationship to other program artifacts

| Artifact | Role relative to this guide |
|---|---|
| `docs/documentation_plan.md` | Human plan; §3 is the normative contract this guide expands for day-to-day use |
| `docs/architecture/ipfs_kit_documentation.objectives.md` | Goal heap (KDOC-G013 and children) |
| `docs/architecture/ipfs_kit_documentation.todo.md` | Executable task board (KDOC-005 outputs this file) |
| `docs/audits/DOCUMENTATION_INVENTORY.md` | Corpus classification proposals (consumes authority vocabulary) |
| `docs/architecture/SOURCE_OF_TRUTH_MAP.md` | Subsystem authority candidates and tests |
| `docs/architecture/GLOSSARY.md` | Shared terms (KDOC-006); style here defers to glossary once present |
| `docs/architecture/decisions/*` | ADRs; must obey rationale and status rules herein |
| `docs/api_generated/*` | Generator-owned; hand edits out of policy |
| `docs/workflows/documentation-maintenance.md` | Automation notes for generated refresh—not a substitute for this claim standard |

---

## 15. Deliberate non-goals of this guide

- Replacing or reconciling competing navigation indexes (`docs/README.md`,
  `docs/index.md`, `docs/DOCUMENTATION_INDEX.md`)—owned by later navigation
  tasks.
- Authoring subsystem architecture content or ADRs (later KDOC waves).
- Moving Historical trees into `docs/ARCHIVE/` (history owner tasks).
- Changing CI hosting or non-`docs/` workflows except as separately authorized
  follow-ups.
- Promoting inferred rationale to accepted ADRs without evidence.

---

## 16. Acceptance (KDOC-005)

This guide satisfies KDOC-005 when:

1. Authority classes for documents are defined with update rules.
2. Provenance fields and evidence ranking are defined.
3. **Accepted**, **Proposed**, **Inferred**, and **Unknown** rationale are
   distinguishable with markers, rules, examples, and anti-patterns.
4. Required architecture sections, examples, diagrams, links, accessibility,
   and security rules are specified.
5. Change triggers and lifecycle states support maintenance.
6. **Human** (§12.1) and **agent** (§12.2) review checklists are present.

---

*End of documentation lifecycle, evidence, and style guide (KDOC-005 / KDOC-G013).*
