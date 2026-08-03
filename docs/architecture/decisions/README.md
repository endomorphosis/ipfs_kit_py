# Architectural decision records (ADRs)

> **Document class:** Canonical  
> **Status:** active  
> **Last verified:** 2026-08-03  
> **Evidence baseline:** KDOC-G031 / KDOC-020; claim standard in
> [`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md);
> unresolved owner decisions in
> [`SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md)  
> **Owners:** documentation maintainers (process); decision owners listed per ADR

This directory is the **single index and process contract** for architectural
decision records in the ipfs-kit documentation program. It defines identifiers,
decision statuses, rationale confidence, evidence rules, supersession,
owner-confirmation workflow, and the planned ADR set.

Related standards:

- Claim ranking and rationale labels:
  [`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)
  §§3–5, §7.2
- Source policy and authority order:
  [`docs/documentation_plan.md`](../../documentation_plan.md) §3.2
- Architecture evidence and open owner decisions:
  [`SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md)

---

## 1. Purpose

ADRs record **choices, trade-offs, rejected alternatives, evidence, and
unresolved authority** behind the bespoke system. They are not marketing copy
and not a substitute for architecture guides.

| ADRs do | ADRs do not |
|---|---|
| Separate **current behavior** from **target decision** | Invent maintainer agreement |
| Label rationale confidence (**Accepted / Proposed / Inferred / Unknown**) | Promote inferred “why” to accepted history |
| Cite rank-1–4 evidence for accepted claims | Describe Proposed intent as shipped capability |
| Keep owner-confirmation gaps visible | Resolve competing runtimes without confirmation |
| Link superseding and superseded records | Edit this index from numbered ADR tasks |

---

## 2. Identifiers and file layout

| Rule | Detail |
|---|---|
| **Filename** | `NNNN-short-kebab-title.md` (four-digit zero-padded number) |
| **Template** | [`0000-template.md`](./0000-template.md) — copy, never leave filled as 0000 |
| **Title line** | `# ADR-NNNN: Short title` matching the filename stem after the number |
| **Stable ID** | `ADR-NNNN` in prose, indexes, and architecture guides |
| **Location** | Only under `docs/architecture/decisions/` |
| **Links** | Repository-relative from other docs (e.g. `docs/architecture/decisions/0003-mcp-runtime-authority.md`) |

Number allocation for this program is **pre-registered** in §8. Later ADR
tasks own only their numbered file and **must not edit this README**. New ADR
numbers outside 0001–0009 require a maintainer-approved index update (separate
task or operator edit).

---

## 3. Decision status vocabulary

Every ADR header **must** declare exactly one **decision status**. Status is
about the *decision record*, not about whether code exists.

| Status | Marker | Meaning | When to use |
|---|---|---|---|
| **Proposed** | `Status: Proposed` | Candidate decision or authority choice; not maintainer-accepted | Competing surfaces, migrations, toolchain choices awaiting owner confirmation |
| **Accepted** | `Status: Accepted` | Maintainer-accepted **or** strongly evidenced implemented invariant (rank-1–4) | Settled constraints with implementation + tests/history support |
| **Rejected** | `Status: Rejected` | Option considered and declined | Documented so the same alternative is not rediscovered silently |
| **Superseded** | `Status: Superseded` | Replaced by a later ADR | Must link `Superseded by: ADR-NNNN` |
| **Deprecated** | `Status: Deprecated` | Still historically true but no longer recommended | Compatibility windows, sunsetting paths |
| **Unknown** | `Status: Unknown` | Insufficient evidence to state a decision | Use when the *decision itself* is not knowable yet; prefer Proposed + explicit confirmation request when options are clear |

### 3.1 Status promotion and demotion

| Transition | Allowed when |
|---|---|
| Proposed → Accepted | Rank-1–4 evidence **and** maintainer confirmation **or** unambiguous implemented invariant with tests/history; update confirmation section |
| Proposed → Rejected | Explicit rejection of the option with rationale and evidence |
| Accepted → Superseded | New ADR records the replacement; both files cross-link |
| Accepted → Deprecated | Policy still true historically; new guidance prefers another path |
| Any → Unknown | Only if evidence was withdrawn or proven wrong; rare—prefer amending confidence labels |

**Forbidden:** rewriting a Proposed ADR to Accepted solely because prose “sounds
right,” because a guide was rewritten, or because an agent inferred intent from
code structure without tests/history/maintainer record.

### 3.2 Document class vs decision status

| Field | Role |
|---|---|
| **Document class** (Canonical / Proposed / …) | Lifecycle of the *file* as documentation |
| **Decision status** (Accepted / Proposed / …) | State of the *architectural choice* |

A file may be Canonical as a maintained record while its **decision status**
remains **Proposed** (e.g. MCP runtime authority). Guides must not cite a
Proposed ADR as settled production policy.

---

## 4. Rationale confidence (independent of decision status)

Rationale answers *why*. Confidence labels follow the claim standard and **must
not be collapsed into decision status**.

| Label | Marker | Meaning |
|---|---|---|
| **Accepted** | `**Accepted:**` | Maintainer-accepted or strongly evidenced design intent |
| **Proposed** | `**Proposed:**` | Intentional direction not yet accepted or not yet reflected in behavior |
| **Inferred** | `**Inferred:**` | Plausible explanation from code/structure without maintainer record |
| **Unknown** | `**Unknown:**` / `unknown / maintainer confirmation needed` | No reliable basis for *why* |

### 4.1 Hard rules (fail review)

1. **Inferred is not Accepted history.** Never write “we chose X because…” for
   an Inferred or Unknown rationale without the label.
2. **Unknown is preferred to invented narrative.** Record
   `unknown / maintainer confirmation needed` and name a confirmation owner.
3. **Proposed decisions stay Proposed** until promotion rules in §3.1 are met.
4. **Accepted rationale** requires source policy ranks 1–4 (executable behavior
   and tests; packaging/entry points; public contracts; Git history / accepted
   ADRs)—not documentation alone or pure inference.
5. Promoting **Inferred → Accepted** or **Proposed → Accepted** is a
   **maintainer/ADR action with evidence**, not a side effect of rewriting a
   guide.

---

## 5. Required ADR sections

Every ADR (after the template header) includes at least:

| Section | Required content |
|---|---|
| **Context** | Problem, forces, which subsystems and entry points are in scope |
| **Current behavior** | What the tree does *today* with evidence pointers (not aspirational) |
| **Decision** | The choice, or the open options if still Proposed |
| **Status** | One value from §3, plus date and last-verified baseline |
| **Rationale** | Why, with **Accepted / Proposed / Inferred / Unknown** labels on each material claim |
| **Evidence** | Ranked citations (source paths, tests, packaging, history, related guides) |
| **Consequences** | Positive, negative, migration, compatibility, security, testing impact |
| **Alternatives considered** | Options evaluated or rejected, with enough detail to avoid re-litigation |
| **Unknowns and confirmation** | Gaps, owner, what “accepted” would require |
| **Supersession** | Links to related, superseding, or superseded ADRs (or “none”) |
| **Follow-up** | Tasks, docs, tests, or owner actions remaining |

The authoritative skeleton lives in
[`0000-template.md`](./0000-template.md).

---

## 6. Evidence and source policy

Claims inside ADRs use the same authority order as the program plan:

1. Executable behavior and focused tests  
2. Packaging and entry-point metadata  
3. Public source contracts, schemas, and docstrings  
4. Git history and **accepted** decision records  
5. Current documentation  
6. Inference  

| Claim type | Minimum evidence |
|---|---|
| Present-tense production behavior | Rank 1–3 preferred; never rank 6 alone |
| Accepted decision / Accepted rationale | Rank 1–4; maintainer confirmation when authority is disputed |
| Proposed decision | Options + consequences + confirmation owner; no present-tense “the system does X” for the proposal |
| Inferred rationale | Explicit **Inferred** label; cite structural evidence only |
| Unknown | Explicit **Unknown**; do not fill with speculation |

---

## 7. Owner confirmation and review workflow

### 7.1 When confirmation is required

Owner confirmation is **mandatory** before **Accepted** status when:

- Multiple competing implementations or entry points exist (MCP trees, cluster
  families, dual clients, etc.)
- The map lists an unresolved owner decision (`U-*` in
  [`SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md))
- Promotion would change what architecture guides treat as canonical
- Only rank-5–6 evidence supports the “why”

### 7.2 Confirmation fields (in each ADR)

| Field | Purpose |
|---|---|
| **Confirmation owner** | Role or named maintainer path (not an anonymous agent) |
| **Confirmation question** | Single decision request (e.g. “Is `mcp_server` the sole production runtime?”) |
| **Acceptance criteria** | What evidence or statement flips Proposed → Accepted |
| **Blocking for** | Guides/docs blocked on this decision |

### 7.3 Review triggers

Re-open or amend an ADR when:

- Linked tests, entry points, or packaging change  
- A superseding ADR is accepted  
- Owner confirmation arrives or is withdrawn  
- Architecture guides cite the ADR incorrectly as settled when it is Proposed  

### 7.4 Index ownership

| Actor | May edit |
|---|---|
| KDOC-020 / framework maintainers | This README (process + index rows) |
| Numbered ADR tasks (KDOC-021..029) | Only their `NNNN-….md` file |
| Navigation tasks | Links *to* ADRs from shared indexes; not ADR bodies unless separately owned |

---

## 8. Decision index

Statuses below are the **index contract** for planned work. Until a numbered
file exists, **Body** is “not yet authored”; **Decision status** defaults to
the intended initial status for that slot. Agents must not treat a missing body
as Accepted.

### 8.1 Registry (planned and delivered)

| ID | Title | File | Decision status | Confidence notes | Owner confirmation | Related conflicts / U-IDs |
|---|---|---|---|---|---|---|
| ADR-0000 | Template (not a decision) | [`0000-template.md`](./0000-template.md) | n/a | Template only | n/a | — |
| ADR-0001 | Lazy imports and optional dependencies | [`0001-imports-and-optional-dependencies.md`](./0001-imports-and-optional-dependencies.md) | *pending authorship* | Distinguish verified constraints from inferred intent | Maintainer if end-state AnyIO/degradation policy open | U-14 |
| ADR-0002 | Backend configuration-plugin registry | [`0002-backend-plugin-registry.md`](./0002-backend-plugin-registry.md) | *pending authorship* | Live vs stub adapters must stay labeled | Maintainer for dual `ipfs_backend` / live factory | U-04 |
| ADR-0003 | MCP runtime authority and single registry | [`0003-mcp-runtime-authority.md`](./0003-mcp-runtime-authority.md) | **Proposed** (required) | Must remain Proposed until confirmation | **Required** — production MCP authority | U-11, C-MCP-TREES |
| ADR-0004 | AnyIO, Trio, asyncio, and sync boundaries | [`0004-anyio-and-sync-boundaries.md`](./0004-anyio-and-sync-boundaries.md) | *pending authorship* | Mixed runtime honesty; confirmation for end-state | Maintainer for degradation policy | U-14 |
| ADR-0005 | Content metadata, WAL, and journal durability | [`0005-content-metadata-and-durability.md`](./0005-content-metadata-and-durability.md) | *pending authorship* | Rebuildable vs authoritative indexes | Maintainer for durability requirements | U-06, U-07 |
| ADR-0006 | Multi-protocol storage and networking | [`0006-multi-protocol-storage-and-networking.md`](./0006-multi-protocol-storage-and-networking.md) | *pending authorship* | Label inferred motivations for dual transports | Maintainer for default transport | U-09, U-10 |
| ADR-0007 | Configuration, state, and secret references | [`0007-configuration-state-and-secret-references.md`](./0007-configuration-state-and-secret-references.md) | *pending authorship* | No credential examples; redact threats | Maintainer for state directory composition | U-13 |
| ADR-0008 | Cluster control-plane authority | [`0008-cluster-control-plane-authority.md`](./0008-cluster-control-plane-authority.md) | **Proposed** (required) | Must remain Proposed; do not pick a family | **Required** — cluster authority | U-08 |
| ADR-0009 | Documentation site and toolchain | [`0009-documentation-site-toolchain.md`](./0009-documentation-site-toolchain.md) | **Proposed** (required) | Workflow/config changes out of scope for the ADR body alone | **Required** — generator/publish path | U-15 |

When a body file is authored, its header `Status:` line is authoritative for
that decision; this table should be updated only by a framework/index owner
(not by the ADR body task under the current conflict policy). Until then,
treat rows marked **Proposed (required)** as open owner decisions even if
guides link the slot.

### 8.2 Unresolved owner decisions (index view)

The following decisions **must remain visible** until confirmation. They are
pre-registered so agents and reviewers can scan open authority without reading
every guide. Full narrative lives in
[`SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) § “Aggregate unresolved
decisions”.

| Owner decision | ADR slot | Index status | Confirmation required |
|---|---|---|---|
| MCP production runtime authority (`mcp_server` vs `mcp` vs root `mcp/` / `servers/`) | ADR-0003 | Proposed / open | Yes — do not promote without maintainer |
| Cluster control-plane family (bespoke vs Kubo Cluster vs MCP++ coordination) | ADR-0008 | Proposed / open | Yes — do not choose among families in guides |
| Default content transport (Kubo / Iroh / dual) | ADR-0006 | Open until body + confirmation | Yes for default |
| WAL/journal durability and Arrow metadata authority | ADR-0005 | Open until body + confirmation | Yes for durability SLAs |
| Config/state directory and credential storage composition | ADR-0007 | Open until body + confirmation | Yes |
| AnyIO end-state and missing-extra degradation | ADR-0001 / ADR-0004 | Open until body + confirmation | Yes for end-state policy |
| Generated-doc toolchain and navigation exclusivity | ADR-0009 | Proposed / open | Yes — publish path |

**Rule for agents:** If this table or §8.1 marks confirmation required, citing
the ADR as “we decided X” is incorrect. Use **Proposed**, list options, and
link the confirmation owner.

### 8.3 How to add a row after delivery

When an ADR body lands (separate task):

1. Ensure the file matches its pre-registered path and title.  
2. Header `Status:` matches §3 (Proposed for authority conflicts until
   confirmed).  
3. Index owner updates Status / Confidence notes / Confirmation columns when
   policy allows an index edit; body authors do not silently rewrite this table
   under KDOC-021..029 conflict policy.  
4. Architecture guides link the ADR with status-accurate language.

---

## 9. How to draft a new ADR

1. Copy [`0000-template.md`](./0000-template.md) to the pre-registered filename
   (or obtain a new number via index ownership).  
2. Fill **Context** and **Current behavior** from source/tests first.  
3. Write **Decision** as Proposed if owner confirmation is required.  
4. Label every material *why* with **Accepted / Proposed / Inferred / Unknown**.  
5. Fill **Evidence**, **Consequences**, **Alternatives**, **Unknowns**.  
6. Name **Confirmation owner** when status is Proposed or Unknown.  
7. Run task validation; do not edit this README from a numbered-ADR task.  
8. Link from the relevant architecture guide only with status-honest wording.

### 9.1 Supersession procedure

1. Author the new ADR with `Status: Proposed` or `Accepted` as appropriate.  
2. Set `Supersedes: ADR-NNNN` on the new record.  
3. On the old record, set `Status: Superseded` and `Superseded by: ADR-MMMM`.  
4. Index owner updates §8.1 rows for both IDs.

---

## 10. Anti-patterns (fail review)

| Anti-pattern | Correction |
|---|---|
| Inferred “because performance” presented as historical fact | `**Inferred:**` or `**Unknown:**` + evidence of what is known |
| Proposed MCP/cluster authority written as production default | Keep `Status: Proposed`; separate current multi-tree behavior |
| Accepted without tests/history when surfaces conflict | Remain Proposed; list confirmation owner |
| Empty alternatives section | At least name the status-quo and one rejected option |
| Editing the index from ADR-0001..0009 tasks | Body only; index is framework-owned |
| Credential or live secret material in examples | Placeholders only; see trust/config ADR rules |
| Quoting this index row as Accepted when body is missing | “Slot reserved / pending authorship” |

---

## 11. Quick reference

**Decision statuses:** `Proposed` · `Accepted` · `Rejected` · `Superseded` ·
`Deprecated` · `Unknown`

**Rationale confidence:** `Accepted` · `Proposed` · `Inferred` · `Unknown`

**Template:** [`0000-template.md`](./0000-template.md)

**Program goal:** KDOC-G030 / KDOC-G031 · **Framework task:** KDOC-020

**Claim standard:**
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)
