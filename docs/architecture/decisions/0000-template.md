# ADR-0000: Title in sentence case (replace 0000 and this title)

> **Document class:** Proposed  
> **Decision status:** Proposed  
> <!-- One of: Proposed | Accepted | Rejected | Superseded | Deprecated | Unknown -->  
> **Date:** YYYY-MM-DD  
> **Last verified:** YYYY-MM-DD  
> **Evidence baseline:** &lt;commit SHA, release tag, or “current tree as of DATE”&gt;  
> **Authors:** &lt;agent task id and/or human&gt;  
> **Confirmation owner:** &lt;role or maintainer; required when Status is Proposed or Unknown&gt;  
> **Supersedes:** none | ADR-NNNN  
> **Superseded by:** none | ADR-NNNN  
> **Related guides:** &lt;paths under docs/architecture/ or docs/&gt;  
> **Related conflicts / U-IDs:** none | U-NN, C-…

**Instructions for authors (delete this block when filing a real ADR):**

1. Copy this file to `NNNN-short-kebab-title.md`. Never leave a filled decision
   as `0000-template.md`.
2. Set **Decision status** in the banner **and** in §3 so they match.
3. **Current behavior** describes the tree *as it is*, with evidence. **Decision**
   describes the choice or open options. Do not merge them.
4. Every material *why* claim must lead with
   `**Accepted:**`, `**Proposed:**`, `**Inferred:**`, or `**Unknown:**`.
5. **Inferred is not Accepted history.** Plausible explanations from code
   structure alone stay **Inferred** until rank-1–4 evidence and/or maintainer
   confirmation supports promotion.
6. Authority conflicts (MCP trees, cluster families, dual clients, etc.) start
   as **Proposed** and name a **Confirmation owner**. Agents must not invent
   acceptance.
7. Do not edit `docs/architecture/decisions/README.md` from a numbered ADR
   task; the index is framework-owned (KDOC-020).
8. No real credentials, tokens, private keys, or host-specific secret paths.

Process contract:
[`README.md`](./README.md) · Claim standard:
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)

---

## 1. Context

<!--
What problem, force, or ambiguity requires a recorded decision?
Which subsystems, packages, entry points, and users are in scope?
Explicit non-goals for this ADR (what you are not deciding).
-->

**In scope:**

- …

**Out of scope:**

- …

---

## 2. Current behavior (evidence, not aspiration)

<!--
Describe what the repository does today. Present tense only for rank-1–3
supported facts. List multiple competing implementations if they exist.
Do not describe the proposed future as if it already shipped.
-->

| Surface / path | Observed role | Evidence (source, test, packaging) | Status label |
|---|---|---|---|
| `path/or/entry` | e.g. active, compatibility, stub, experimental | e.g. `pkg/…`, `tests/…`, `pyproject.toml` | … |

Narrative (optional): …

---

## 3. Decision

**Status:** Proposed  
<!-- Must match the banner. Use Accepted only per README §3.1. -->

### 3.1 Decision statement

<!--
If Proposed: state the candidate decision clearly, or list ranked options
without selecting a winner when confirmation is required.

If Accepted: state the settled choice in present tense and point at evidence.

If Rejected / Deprecated / Superseded / Unknown: state that outcome explicitly.
-->

…

### 3.2 Options (required when Status is Proposed or when alternatives are material)

| Option | Summary | Fit / risk |
|---|---|---|
| A — … | … | … |
| B — … | … | … |
| Status quo | Leave competing surfaces as-is | … |

**Selected option (if any):** none yet — awaiting confirmation | Option …

---

## 4. Rationale (confidence-labeled)

<!--
Label EVERY material why-claim. Mixing unlabeled Accepted-sounding prose with
inference is a review failure.

Promoting Inferred → Accepted or Proposed → Accepted is a maintainer/ADR
action with evidence—not a side effect of rewriting this section.
-->

**Accepted:**  
<!-- Maintainer-accepted or strongly evidenced design intent (implementation +
tests/history). Cite rank-1–4 evidence. Leave empty if none yet. -->

…

**Proposed:**  
<!-- Intentional direction not yet accepted or not yet reflected in behavior. -->

…

**Inferred:**  
<!-- Plausible explanation from structure/code without maintainer record.
Never narrate as “we chose X because…” historical fact. -->

…

**Unknown:**  
<!-- Use: unknown / maintainer confirmation needed. Prefer this over invention. -->

…

---

## 5. Evidence

<!--
Order citations by program source policy:
1. executable behavior and focused tests
2. packaging and entry-point metadata
3. public source contracts, schemas, docstrings
4. Git history and accepted ADRs
5. current documentation (supporting only)
6. inference (must be labeled Inferred in §4, not listed as proof of Accepted)
-->

| Rank | Claim | Citation |
|---|---|---|
| 1 | … | `tests/…`, observed behavior in `…` |
| 2 | … | `pyproject.toml`, entry points |
| 3 | … | public module/API contract |
| 4 | … | git history / accepted ADR-NNNN |
| 5 | … | `docs/…` (supporting) |

**Evidence that is explicitly insufficient for Accepted status:** …

---

## 6. Consequences

### 6.1 Positive

- …

### 6.2 Negative / costs

- …

### 6.3 Migration and compatibility

- …

### 6.4 Security and trust

- …  
- Credentials: none in this ADR; use placeholders only if examples are required.

### 6.5 Testing and verification

- Tests that must pass or be added: …
- Commands or fixtures that encode the decision: …

---

## 7. Alternatives considered

| Alternative | Why considered | Why rejected / deferred | Confidence |
|---|---|---|---|
| … | … | … | Accepted / Proposed / Inferred / Unknown |

At least one alternative (including “do nothing / keep status quo”) is required.

---

## 8. Unknowns and owner confirmation

<!--
Required when Decision status is Proposed or Unknown, or when any §4 Unknown
blocks architecture guidance.
-->

| Field | Value |
|---|---|
| **Confirmation owner** | … |
| **Confirmation question** | Single, answerable decision request |
| **What “Accepted” requires** | Evidence and/or explicit maintainer statement |
| **Blocking for** | Guides, releases, or tasks waiting on this ADR |
| **Related U-IDs / conflicts** | e.g. U-11, C-MCP-TREES |

**Open unknowns:**

1. … — unknown / maintainer confirmation needed

---

## 9. Supersession and relationships

| Relation | ADR / doc |
|---|---|
| Supersedes | none |
| Superseded by | none |
| Related ADRs | … |
| Architecture guides | … |
| Source-of-truth map | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) |

---

## 10. Follow-up actions

| Action | Owner | Notes |
|---|---|---|
| … | … | … |

---

## 11. Review checklist (authors)

- [ ] Filename is `NNNN-short-kebab-title.md` (not left as 0000 for a real decision)
- [ ] Banner **Decision status** matches §3 **Status**
- [ ] **Current behavior** is evidence-backed and separate from the proposal
- [ ] No present-tense “the system does X” for Proposed-only intent
- [ ] Every material *why* uses **Accepted / Proposed / Inferred / Unknown**
- [ ] No Inferred or Unknown claim is written as Accepted history
- [ ] Evidence table prefers ranks 1–4 for Accepted claims
- [ ] Alternatives include status quo or an explicit reject
- [ ] Confirmation owner and question filled when status is Proposed/Unknown
- [ ] No secrets, live tokens, or host-specific credential paths
- [ ] `docs/architecture/decisions/README.md` was **not** edited by this task
- [ ] Related architecture guide will cite this ADR with status-honest language

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

**Forbidden promotion paths without evidence + confirmation rules:**

- Inferred rationale → Accepted decision narrative  
- Proposed authority → Accepted default in guides  
- Documentation-only claim → Accepted production behavior  

See [`README.md`](./README.md) §§3–4 for full promotion rules.
