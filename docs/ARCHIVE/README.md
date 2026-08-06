# Documentation archive boundary

| Field | Value |
|---|---|
| **Document class** | Historical (boundary / reading guidance) |
| **Authority class** | Historical — this tree is **not current** guidance |
| **Status** | active (archive landing page) |
| **Owner / task** | KDOC-042 |
| **Goal id** | KDOC-G050 |
| **Track** | information-architecture |
| **Last verified** | 2026-08-04 |
| **Evidence** | [`docs/audits/HISTORICAL_DOCUMENT_REGISTER.md`](../audits/HISTORICAL_DOCUMENT_REGISTER.md) (H11, BATCH-HIST-ARCHIVE); [`docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md`](../audits/DUPLICATE_AND_REDIRECT_PLAN.md); [`docs/guides/DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) §2 |
| **Scope** | All material under `docs/ARCHIVE/` (existing and future intake) |
| **Non-goals** | Physical moves (KDOC-045); navigation rewrites (KDOC-060); generated or external contracts |

> **Stop — historical material only.**  
> Everything under `docs/ARCHIVE/` is **not current** API, operations, architecture, installation, or MCP/CLI guidance.  
> Treat these files as **provenance and campaign history**. Do **not** follow them as how-to, production status, coverage proof, or runtime authority.  
> Prefer packaging metadata, focused tests, and the current guides linked in [§4](#4-where-to-go-instead-current-replacements).

---

## 1. Purpose of this tree

`docs/ARCHIVE/` is the **explicit non-current** home for dated implementation reports, status write-ups, fix notes, completion summaries, and test-campaign dumps that must remain **discoverable** for archaeology without posing as maintained documentation.

This landing page is the **archive boundary**:

| In scope here | Out of scope (do not treat ARCHIVE as) |
|---|---|
| Provenance for completed campaigns and refactors | Current API reference |
| Snapshot status at a past date | Live deployment / operator runbooks |
| Episode narratives (`*COMPLETE*`, `*SUMMARY*`, fix write-ups) | Architecture authority for the present tree |
| Redirect targets after KDOC-045 bulk intake | Coverage percentages or “production ready” claims |
| Evidence that something *was* attempted or reported | Packaging entry points or MCP runtime selection |

**Acceptance intent (KDOC-042):** archived reports stay findable via this index and directory listing, but a careful reader cannot reasonably mistake them for current API, operations, or architecture guidance.

---

## 2. Authority class and reading rules

### 2.1 Authority

| Rule | Meaning |
|---|---|
| **Document class** | **Historical** (lifecycle contract KDOC-005) |
| **May recommend as current?** | **No** |
| **Evidence rank** | Lowest for present behavior: executable code, packaging, and focused tests outrank every ARCHIVE claim |
| **Present-tense language** | Many files still say “current,” “production ready,” or “authoritative.” That wording is **historical rhetoric**, not a live endorsement |
| **Dates** | Prefer any embedded “Last Updated” / campaign date over the file path. Absence of a date does **not** make content current |

### 2.2 How to read an archived document

1. **Assume staleness.** Claims about APIs, ports, entry points, coverage %, and “complete” migrations may contradict the tree you are on.
2. **Do not operationalize.** Do not copy install steps, CLI flags, MCP server paths, or cluster topologies from ARCHIVE into production runbooks without re-verifying against source and current guides.
3. **Extract questions, not answers.** Use reports to discover *which subsystem was touched*; resolve *how it works now* from current architecture, API, and ops docs.
4. **Prefer higher ranks.** Order of authority for behavior: packaging/`pyproject.toml` → public source contracts → focused tests → accepted ADRs / canonical architecture → current guides → Git history → **this ARCHIVE last**.
5. **Never cite ARCHIVE as verification.** Completion banners and status reports are **not** acceptance evidence for the documentation program (see freshness findings on COMPLETE-report pollution).
6. **Watch for false “primary reference” links.** Older indexes (e.g. historical MCP status under `status-reports/`) may still *claim* to be authoritative. Under this boundary they are **not current**.

### 2.3 Recommended banner (for individual files)

When editing or intake-moving a report, add a short banner (lifecycle guide example):

```markdown
> **Historical.** Campaign report — **not current** guidance.
> See [docs/ARCHIVE/README.md](../ARCHIVE/README.md) for reading rules and current replacements.
```

---

## 3. What lives here today

Material already under `docs/ARCHIVE/` is classified **Retain-historical** (register family **H11**, batch **BATCH-HIST-ARCHIVE**). Paths below are the quarantine layout as of this boundary task.

| Subdirectory | Role | Example contents |
|---|---|---|
| [`fixes/`](fixes/) | One-off fix analyses and integration notes | Daemon manager attribute fix; pin index analysis; Arrow IPC fix |
| [`implementation-summaries/`](implementation-summaries/) | Feature implementation episode summaries | Auto-healing implementation summary |
| [`status-reports/`](status-reports/) | Point-in-time status and “mission complete” narratives | MCP development status (**2025-07-10** sample); modular server status |
| [`summaries/`](summaries/) | CLI, dashboard, daemon, and refactoring summaries | CLI clean-structure / integration summaries; dashboard cluster notes |
| [`test-reports/`](test-reports/) | Dated test-campaign dumps | CLI features test report |

**Scale note:** inventory baseline recorded ~21 markdown files in this tree. Counts change only via reviewed intake (KDOC-045) or explicit batch owners—not ad-hoc drops.

### 3.1 Illustrative non-authority (do not promote)

| Archived path | Why it is **not current** |
|---|---|
| [`status-reports/MCP_DEVELOPMENT_STATUS.md`](status-reports/MCP_DEVELOPMENT_STATUS.md) | Dated **2025-07-10**; older navigation once called it a “primary” MCP status doc. Runtime authority is packaging (`ipfs-kit-mcp`) + [`docs/architecture/MCP_CONTROL_PLANE.md`](../architecture/MCP_CONTROL_PLANE.md) |
| [`implementation-summaries/AUTO_HEALING_IMPLEMENTATION_SUMMARY.md`](implementation-summaries/AUTO_HEALING_IMPLEMENTATION_SUMMARY.md) | Episode summary; feature how-to belongs under `docs/features/auto-healing/` when maintained |
| [`summaries/*CLI*`](summaries/) | Pre-program CLI structure narratives; CLI truth is [`docs/api/cli_reference.md`](../api/cli_reference.md) + packaged `ipfs-kit` entry |

---

## 4. Where to go instead (current replacements)

Use this map when an ARCHIVE document mentions a topic. Prefer the **replacement** column for any present-tense work.

| Topic | Prefer (current / maintained) | Do not use ARCHIVE as |
|---|---|---|
| **System architecture** | [`docs/architecture/SYSTEM_OVERVIEW.md`](../architecture/SYSTEM_OVERVIEW.md), [`RUNTIME_AND_ENTRYPOINTS.md`](../architecture/RUNTIME_AND_ENTRYPOINTS.md), [`SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md) | Subsystem design authority |
| **MCP / control plane** | Packaging scripts + [`MCP_CONTROL_PLANE.md`](../architecture/MCP_CONTROL_PLANE.md); CLI/MCP surface matrix in audits | Production MCP “status” or alternate server paths |
| **Storage / VFS / content** | [`STORAGE_BACKEND_SYSTEM.md`](../architecture/STORAGE_BACKEND_SYSTEM.md), [`CONTENT_METADATA_VFS.md`](../architecture/CONTENT_METADATA_VFS.md), `docs/features/`, `docs/reference/` | Backend inventory from completion reports |
| **Cluster / network** | [`CLUSTER_COORDINATION.md`](../architecture/CLUSTER_COORDINATION.md), [`NETWORK_TRANSPORTS.md`](../architecture/NETWORK_TRANSPORTS.md), `docs/operations/` | Historical multi-node status tables |
| **Async / optional deps** | [`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../architecture/ASYNC_AND_OPTIONAL_DEPENDENCIES.md), [`docs/development/async_architecture.md`](../development/async_architecture.md) | AnyIO “100% complete” campaign claims |
| **Configuration / trust** | [`CONFIGURATION_STATE_AND_TRUST.md`](../architecture/CONFIGURATION_STATE_AND_TRUST.md) | Ad-hoc fix notes as security policy |
| **Python / CLI / install** | [`docs/api/high_level_api.md`](../api/high_level_api.md), [`cli_reference.md`](../api/cli_reference.md), [`docs/installation_guide.md`](../installation_guide.md), [`docs/QUICK_REFERENCE.md`](../QUICK_REFERENCE.md) | Archive CLI summaries or installer digressions |
| **Testing process** | [`docs/development/testing_guide.md`](../development/testing_guide.md), `pytest.ini`, CI workflows | Coverage roadmaps and phase final reports |
| **Documentation program** | [`docs/documentation_plan.md`](../documentation_plan.md) (protected), Wave 0 `docs/audits/*` | Feb overhaul / project completion checklists as live verification |
| **Vocabulary / lifecycle** | [`docs/architecture/GLOSSARY.md`](../architecture/GLOSSARY.md), [`docs/guides/DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) | Informal status language in reports |

**Still labeled Historical but not yet under ARCHIVE** (retain-in-place or pending move): `docs/implementation/`, `docs/status_reports/`, `docs/fixes/`, `docs/migration/`, root `*COMPLETE*` / coverage reports. Those families are planned for redirect/archive under KDOC-041 dispositions and KDOC-045 intake; they share the **same reading rules** as this tree even before physical move.

---

## 5. Provenance and discovery

### 5.1 How to find archived material

| Method | Use |
|---|---|
| This README | Category index and replacement map |
| Directory listing | `docs/ARCHIVE/<category>/` |
| Historical register | [`docs/audits/HISTORICAL_DOCUMENT_REGISTER.md`](../audits/HISTORICAL_DOCUMENT_REGISTER.md) — disposition, move risk, batch owner |
| Duplicate / redirect plan | [`docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md`](../audits/DUPLICATE_AND_REDIRECT_PLAN.md) — survivors vs ARCHIVE targets |
| Corpus inventory | [`docs/audits/DOCUMENTATION_INVENTORY.md`](../audits/DOCUMENTATION_INVENTORY.md) — classification baseline |

Discovery must **not** depend on primary “start here” navigation. Landing indexes (KDOC-060) must not promote ARCHIVE paths as current guidance. Links *into* ARCHIVE from current docs should be rare and explicitly labeled historical.

### 5.2 Provenance expectations for archived files

When material is moved here (or authored as archive-only), retain or record:

| Field | Expectation |
|---|---|
| Original campaign context | Title, approximate date, what work episode it closed |
| Source path (if moved) | Prior path under `docs/` when known (stub redirect or register row) |
| Replacement pointer | Link to current guide or “none — Drop-from-navigation until &lt;task&gt;” |
| Authority banner | Historical / **not current** language at top of file when practical |

Do **not** rewrite archived prose into present tense to “refresh” it. Refresh happens by updating **canonical** guides against the tree, not by polishing ARCHIVE.

---

## 6. Rules for future archival (intake)

Physical bulk moves are owned by **KDOC-045** (and related batch IDs). This boundary README is a **precondition** for new intake (duplicate plan §2).

### 6.1 Hard constraints

1. **Boundary first.** Do not expand ARCHIVE bulk without this README stating material is **not current**.
2. **No destructive move before replacement.** Gate states from KDOC-041: **Open** required for filesystem moves of present-tense content; **Pending-task** → Drop-from-navigation only.
3. **Nav-unlink before or with move.** Remove “start here” / primary-index links (KDOC-060) so ARCHIVE never becomes the default click path.
4. **Redirect stubs when paths break.** After a move, leave a short stub at the old path (title, Historical status, link to survivor or ARCHIVE path) per the redirect plan.
5. **Preserve Git history** where tools allow (`git mv`). Do not invent dates or “completed” claims during move.
6. **Never archive competing indexes** (`docs/index.md`, `docs/README.md`, `docs/DOCUMENTATION_INDEX.md`) as historical bulk—re-role them under exclusive navigation.
7. **Never invent a fake canonical path.** If no replacement exists, register “none yet” and keep the report out of current recommendations.

### 6.2 Planned destination families (KDOC-045)

| Future / planned path | Source families (register) | Notes |
|---|---|---|
| `docs/ARCHIVE/implementation/` | H1 `docs/implementation/` bulk | Directory-level redirect note; high link density |
| `docs/ARCHIVE/status-and-fixes/` | H5 `status_reports/`, H6 `fixes/` | Merge with existing `status-reports/` / `fixes/` as owners decide |
| Existing categories above | Root PR/phase reports, campaign test dumps, feature `*SUMMARY*` children | Only after topic replacements or Drop-from-navigation |

### 6.3 What must never enter ARCHIVE as “current”

- Wave 0 evidence maps and audits under `docs/audits/` (those are program evidence, not campaign dumps).
- Protected program files (`docs/documentation_plan.md`, objective heap, task board).
- Generated API trees (`docs/api_generated/`) — separate generated contract (KDOC-043).
- External / embedded project snapshots — external sources register (KDOC-044).
- Maintained process docs that are Split-retain (e.g. testing health matrix, verified CI runbooks) until explicitly reclassified.

---

## 7. Agent and human checklist

Before citing or linking anything under `docs/ARCHIVE/`:

- [ ] Is my task asking for **history/provenance**, not how to operate the system today?
- [ ] Have I checked packaging, source, or a **Canonical** guide for the same claim?
- [ ] Am I avoiding ARCHIVE language that says “current,” “authoritative,” or “production ready” as if it still applies?
- [ ] If I must link here from a current doc, is the link labeled **Historical** / **not current**?
- [ ] Am I about to *move* files? If yes, stop and use KDOC-041 gates + KDOC-045 ownership—not this README alone.

---

## 8. Related program artifacts

| Artifact | Role |
|---|---|
| [`docs/guides/DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) | Authority classes; Historical may not recommend as current |
| [`docs/audits/HISTORICAL_DOCUMENT_REGISTER.md`](../audits/HISTORICAL_DOCUMENT_REGISTER.md) | Per-family disposition, replacements, batch owners |
| [`docs/audits/DUPLICATE_AND_REDIRECT_PLAN.md`](../audits/DUPLICATE_AND_REDIRECT_PLAN.md) | Survivor selection, redirect types, replacement gates |
| [`docs/audits/FRESHNESS_AND_CHANGE_AUDIT.md`](../audits/FRESHNESS_AND_CHANGE_AUDIT.md) | Why COMPLETE/status pollution is high severity |
| [`docs/architecture/SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md) | Compatibility / historical implementation paths (code, not only docs) |
| KDOC-045 (planned) | Curated ARCHIVE intake and category indexes |
| KDOC-060 (planned) | Exclusive navigation that keeps ARCHIVE off the default path |

---

**Bottom line:** `docs/ARCHIVE/` keeps history **discoverable** and **quarantined**. Every file here is **not current** guidance. For API, operations, and architecture of the tree you are on, leave this directory and use the replacements in [§4](#4-where-to-go-instead-current-replacements).
