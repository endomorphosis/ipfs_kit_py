# ADR-0003: MCP runtime authority and single registry

> **Document class:** Proposed  
> **Decision status:** Proposed  
> Status: Proposed  
> **Date:** 2026-08-03  
> **Last verified:** 2026-08-03  
> **Evidence baseline:** tree `ddf1c8608c93332e17b3f0243a46d7f50f88ab1b`; control-plane guide baseline `294271ade01e4e4c03a8b1693159fff8c99f3c34` (see [`MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md))  
> **Authors:** KDOC-023 (agent-supervisor implementation)  
> **Confirmation owner:** MCP / control-plane maintainers (production runtime authority); documentation maintainers for status-honest guide cross-links  
> **Supersedes:** none  
> **Superseded by:** none  
> **Related guides:** [`../MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md), [`../RUNTIME_AND_ENTRYPOINTS.md`](../RUNTIME_AND_ENTRYPOINTS.md), [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §6, [`../../MCP_SERVER_MIGRATION_GUIDE.md`](../../MCP_SERVER_MIGRATION_GUIDE.md)  
> **Related conflicts / U-IDs:** U-11, C-MCP-TREES, C-MCP-TOOLS  

Process contract:
[`README.md`](./README.md) · Claim standard:
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)

---

## 1. Context

The repository currently ships **multiple MCP-related trees** and narratives:

- Packaged **MCP++** under `ipfs_kit_py/mcp_server/` (console scripts `ipfs-kit-mcp`, `ipfs-kit-mcp-tools`)
- Large prior-generation stack under `ipfs_kit_py/mcp/` (controllers, dashboards, many servers)
- Root `mcp/` shims and alternate servers
- Root `servers/` unpackaged alternate servers
- Migration and VFS docs that still center `ipfs_kit_py.mcp.servers.unified_mcp_server` as “production”

Architecture Wave 0 maps this as conflict **C-MCP-TREES** / unresolved owner decision **U-11**. Agents and operators need a recorded decision for **which runtime is sole production authority** for new deployments, while documentation must not invent maintainer acceptance.

Separately, MCP++ implements a **one-registry / multiple-surface** design: `TOOL_GROUPS` is the write-path registry for kit IPFS-family tools, consumed by the hierarchical manager, native server, tools CLI, FastMCP bridge, and JS SDK generator. That invariant is **implemented behavior** and must be recorded distinctly from the still-open **production runtime authority** choice. Published tool counts still drift (**C-MCP-TOOLS**).

**In scope:**

- Production MCP runtime authority among competing trees (options only while Proposed)
- Single-registry / multi-surface invariant for MCP++ tool declaration and dispatch
- Migration and compatibility consequences of each authority option
- Confirmation owner and acceptance criteria for promoting this ADR

**Out of scope:**

- Accepting or rejecting this decision without maintainer confirmation (forbidden by index and KDOC-023 conflict policy)
- Cluster control-plane family choice (ADR-0008 / U-08)
- Regenerating JS SDK manifests or changing code registries
- Resolving receipt-store deployment defaults or legacy dashboard lifecycle in isolation
- Rewriting disputed docs (`MCP_SERVER_MIGRATION_GUIDE.md`, VFS contract claims, etc.) as if this ADR were Accepted

---

## 2. Current behavior (evidence, not aspiration)

Present tense below describes the tree as measured. It does **not** assert a sole production policy.

| Surface / path | Observed role | Evidence (source, test, packaging) | Status label |
|---|---|---|---|
| `ipfs_kit_py/mcp_server/server.py` | MCP++ JSON-RPC server; stdio default; HTTP/P2P optional | Console script `ipfs-kit-mcp` → `ipfs_kit_py.mcp_server.server:main` in `pyproject.toml` | **Packaged current** |
| `ipfs_kit_py/mcp_server/cli.py` | Tools CLI over same manager/registry | Console script `ipfs-kit-mcp-tools` → `ipfs_kit_py.mcp_server.cli:main` | **Packaged current** |
| `ipfs_kit_py/mcp_server/tools/__init__.py` (`TOOL_GROUPS`) | Single write-path registry: category → tool → callable | Module docstring; consumed by `HierarchicalToolManager` | **Implemented registry** |
| `hierarchical_tool_manager.py`, `fastmcp_app.py`, `js_sdk/generate.py` | Multi-surface consumers of `TOOL_GROUPS` | Source imports `TOOL_GROUPS`; FastMCP re-registers from manager | **Same registry, multiple surfaces** |
| Measured registry | **12 groups / 29 tools** (includes `iroh_diagnostics`) | `tools/__init__.py`; map §6; control-plane guide §2.3 | **Measured** |
| `js_sdk/tools-manifest.json` | Generated companion | **28** tools; missing `iroh_diagnostics` | **Drift (C-MCP-TOOLS)** |
| `ipfs_kit_py/mcp/` | Large legacy stack (controllers, dashboard, auth, HA, many servers) | Importable package tree; extensive `tests/test_mcp_*` coverage | **Compatibility / historical (C-MCP-TREES)** |
| `ipfs_kit_py/mcp/servers/unified_mcp_server.py` | “Unified” server still cited as production in some docs | [`docs/MCP_SERVER_MIGRATION_GUIDE.md`](../../MCP_SERVER_MIGRATION_GUIDE.md); VFS contract prose | **Competing claim** vs packaging |
| Other `ipfs_kit_py/mcp/servers/*` | Enhanced/VFS/standalone legacy servers | Env guards: `IPFS_KIT_MCP_MODE=production` blocks unless `IPFS_KIT_ALLOW_LEGACY_MCP=1` | **Deprecated within legacy tree when production mode set** |
| Root `mcp/*_mcp_tools.py`, root alternate servers | Shims / older layouts | Root `mcp/` package | **Compatibility shims** |
| Root `servers/*.py` | Unpackaged alternate servers | Not in `[project.scripts]` | **Historical / experimental** |
| `ipfs_kit_py/mcp.py` | Minimal peer/server stub | Distinct module; not MCP++ | **Not** control-plane authority |
| Packaged CLI daemon path | Some FastCLI / daemon paths still import legacy `mcp/` classes | Map §6 “CLI daemon path” unknown | **Coupling packaged entry → historical tree** |

Narrative:

1. **Packaging** points new operators at MCP++ (`ipfs-kit-mcp` / `ipfs-kit-mcp-tools`).
2. **Legacy trees remain importable** and heavily tested; they are not removed.
3. **Docs disagree:** migration/VFS material may still name `unified_mcp_server` as production; architecture guides label that as competing / unresolved (**Proposed** ADR territory).
4. **MCP++ registry invariant holds in code:** kit tools are declared once in `TOOL_GROUPS` and shared across surfaces; published counts and some tests/README prose have not fully caught up (**C-MCP-TOOLS**).
5. **Sole production authority is not settled** by packaging alone; U-11 remains open until this ADR is confirmed.

---

## 3. Decision

**Status: Proposed**

### 3.1 Decision statement

This ADR records **two related but separable matters**:

**A. Production MCP runtime authority (open — requires confirmation)**

Candidate decision (not accepted):

> For **new** production deployments and agent hosts, the sole supported MCP runtime is the packaged **MCP++** stack under `ipfs_kit_py.mcp_server` (entry points `ipfs-kit-mcp` and `ipfs-kit-mcp-tools`). Trees under `ipfs_kit_py.mcp`, root `mcp/`, and root `servers/` are **compatibility / historical / experimental** only—not recommended production servers—unless an explicit temporary override (e.g. `IPFS_KIT_ALLOW_LEGACY_MCP=1` for legacy in-tree servers) is documented for a defined window.

Until a maintainer confirms an option in §3.2, architecture guides must continue to describe **packaged current** vs **compatibility** surfaces without treating sole authority as Accepted.

**B. One registry, multiple surfaces (implemented invariant — record, do not re-litigate as authority)**

Within MCP++, kit IPFS-family tools for the packaged surfaces are declared only in `TOOL_GROUPS` and dispatched via `HierarchicalToolManager`. Native JSON-RPC server, tools CLI, FastMCP registrar, Python imports, and JS SDK generator are designed as **surfaces over that registry**, not parallel write-path registries. This is **current implemented design intent** (registry module docstring + consumers). Confirming that no second production write-path registry remains outside this model, and which tool count is the published contract, is still open under **C-MCP-TOOLS**.

### 3.2 Options (required while Status is Proposed)

| Option | Summary | Fit / risk |
|---|---|---|
| **A — MCP++ sole production** | `mcp_server` only for new deploys; legacy trees compatibility-only with sunset policy | Aligns with packaging scripts and control-plane guide; requires honest doc/test migration for migration-guide and VFS claims |
| **B — Dual support** | Both `mcp_server` and a named legacy path (e.g. `unified_mcp_server`) remain supported production runtimes | Higher ops/docs burden; freezes C-MCP-TREES indefinitely |
| **C — Legacy unified sole production** | Treat `ipfs_kit_py.mcp.servers.unified_mcp_server` as sole production; demote MCP++ packaging | Contradicts current console scripts and MCP++ investment; high rework |
| **Status quo** | Leave competing trees and conflicting docs without an accepted authority | Lowest immediate change; highest ongoing confusion for agents and operators |

**Selected option (if any):** none yet — awaiting confirmation (candidate narrative above is Option A as the **leading Proposed** direction, not Accepted policy).

**Registry sub-options (C-MCP-TOOLS; may confirm with A or separately):**

| Sub-option | Summary |
|---|---|
| **R1** | Published contract = live `TOOL_GROUPS` count (currently 29); regenerate JS/manifest/tests to match |
| **R2** | Published contract = committed JS manifest; registry must not ship tools absent from manifest without bump |
| **R3** | Explicit dual-count contract (registry vs generated surface) with documented delta rules |

---

## 4. Rationale (confidence-labeled)

**Accepted:**  

- Packaged console scripts launch MCP++: `ipfs-kit-mcp` → `mcp_server.server:main`, `ipfs-kit-mcp-tools` → `mcp_server.cli:main` (`pyproject.toml`).  
- `TOOL_GROUPS` is the in-code single registry for MCP++ kit tools and is consumed by hierarchical manager, CLI, FastMCP, and JS generator (module docstring + imports).  
- Fail-closed agent-supervisor receipt reads and graceful MCP++ extras degradation are implemented behavior under `mcp_server` (see control-plane guide; not re-decided here).

**Proposed:**  

- Sole production runtime for new deployments should be MCP++ (`mcp_server`), with `ipfs_kit_py.mcp`, root `mcp/`, and `servers/` labeled strictly compatibility/historical/experimental.  
- Migration docs and VFS prose that name `unified_mcp_server` as production should be updated **after** confirmation—not treated as already resolved by this draft.  
- Published tool-count contract should track an explicit choice among R1–R3 under **C-MCP-TOOLS**.

**Inferred:**  

- Competing trees were retained to support migration, dashboards, and large existing test corpora rather than as intentional long-term dual production authorities.  
- Hierarchical categories exist to avoid flooding clients with dozens of top-level tools (manager module comments / control-plane rationale table).  
- Legacy env guards (`IPFS_KIT_MCP_MODE` / `IPFS_KIT_ALLOW_LEGACY_MCP`) encode a historical preference to block non-unified legacy servers in “production” mode within the **legacy** tree—not a maintainer acceptance of MCP++ sole authority across the whole repository.

**Unknown:**  

- Whether maintainers accept Option A, B, C, or a time-boxed dual-support plan — **unknown / maintainer confirmation needed**.  
- Final disposition of legacy dashboards, CLI daemon imports into `mcp/`, and receipt-store multi-node defaults — **unknown / maintainer confirmation needed** (listed in map §6; not closed here).  
- Which published count (29 vs 28 vs stale README 21/7) is contractual until R1–R3 is chosen.

---

## 5. Evidence

| Rank | Claim | Citation |
|---|---|---|
| 1 | MCP++ multi-surface e2e over hierarchical manager | `ipfs_kit_py/mcp_server/tests_e2e_interop.py` |
| 1 | JSON-RPC / init / tools tests (mix of MCP++ and legacy targets—filter carefully) | `tests/test_mcp_jsonrpc_conformance.py`, `tests/test_mcp_initialization.py`, `tests/test_mcp_tools_*.py`, `tests/test_agent_supervisor_receipts.py` |
| 1 | Legacy servers enforce production-mode legacy block | e.g. `ipfs_kit_py/mcp/servers/enhanced_mcp_server_with_daemon_mgmt.py` (`IPFS_KIT_MCP_MODE`, `IPFS_KIT_ALLOW_LEGACY_MCP`) |
| 2 | Packaged entry points | `pyproject.toml` `[project.scripts]`: `ipfs-kit-mcp`, `ipfs-kit-mcp-tools` |
| 3 | Single registry contract and tool list | `ipfs_kit_py/mcp_server/tools/__init__.py` (`TOOL_GROUPS`); `hierarchical_tool_manager.py`; `fastmcp_app.py` |
| 3 | MCP++ server protocol / transports | `ipfs_kit_py/mcp_server/server.py` |
| 5 | Control-plane architecture (status-honest; does not accept this ADR) | [`../MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md) |
| 5 | Wave 0 map U-11 / C-MCP-TREES / C-MCP-TOOLS | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §6 |
| 5 | Competing migration narrative | [`../../MCP_SERVER_MIGRATION_GUIDE.md`](../../MCP_SERVER_MIGRATION_GUIDE.md); VFS contract prose citing `unified_mcp_server` |

**Evidence that is explicitly insufficient for Accepted status:** packaging scripts alone; architecture guide prose; migration guide claims; inferred migration intent; presence of tests against legacy trees; agent-authored “sounds right” promotion of Option A.

---

## 6. Consequences

### 6.1 Positive

- **If Option A is later Accepted:** operators and agent hosts get one packaged production path; docs can demote competing servers without ambiguity.  
- Recording the **one-registry / multi-surface** invariant reduces schema/name drift across CLI, MCP, FastMCP, and SDK.  
- Keeping status **Proposed** until confirmation prevents silent authority invention in dependent tasks (KDOC guides, API reference, audits).

### 6.2 Negative / costs

- Dual-tree maintenance cost continues until authority is accepted and migration policy lands.  
- Test and CI surface remains large (legacy + MCP++ workflows).  
- Tool-count drift (**C-MCP-TOOLS**) continues to confuse published contracts until R1–R3 is fixed.  
- Doc debt: migration guide, VFS contract, and some README counts conflict with packaging narrative.

### 6.3 Migration and compatibility

| Area | Consequence while Proposed | Consequence if Option A Accepted | Consequence if dual (B) or legacy sole (C) |
|---|---|---|---|
| New deployments | Prefer documenting `ipfs-kit-mcp` as **packaged current**, not sole Accepted authority | Document MCP++ only; mark other trees non-production | Explicit dual matrix or re-center on legacy unified |
| Existing `unified_mcp_server` / `mcp/` imports | Remain valid import paths; not deleted by this ADR | Compatibility window + deprecation warnings; optional `IPFS_KIT_ALLOW_LEGACY_MCP` for named legacy servers | Retain or elevate those imports |
| Root `mcp/` and `servers/` | Historical / experimental labels | Sunset or archive plan; no packaging scripts | May remain supported if chosen |
| `TOOL_GROUPS` surfaces | Keep single write path; regenerate JS on tool adds | Same; fix count contract (R1–R3) | Registry model still MCP++-local unless authority shifts |
| Migration / VFS docs | **Do not rewrite as resolved** by this draft | Update claims to MCP++ with status-honest language | Align to chosen dual/legacy authority |
| Tests | Continue covering both stacks as present | Migrate or quarantine legacy suites under compatibility labels | Keep dual coverage as first-class |
| CLI daemon → legacy `mcp/` | Coupling remains open (map §6) | Follow-on decision: re-bind or keep compatibility import | May reinforce legacy coupling |

**Compatibility policy draft (Proposed only — not active Accepted policy):**

1. Do not remove importable legacy modules solely because this ADR exists.  
2. Do not cite this ADR as “we decided MCP++ only” in guides until status is Accepted.  
3. Temporary legacy production use, if any, should be explicit (env override, documented window)—not implied by silent dual defaults.  
4. New tools for packaged MCP++ surfaces land only in `TOOL_GROUPS` (implemented rule); do not invent a second MCP++ write-path list.

### 6.4 Security and trust

- Production authority choice affects which auth/HA/dashboard stacks operators trust (`mcp/` auth vs MCP++ receipts/coordination).  
- Fail-closed receipts remain an implemented MCP++ invariant regardless of sole-runtime acceptance.  
- Credentials: none in this ADR; use placeholders only if examples are required.  
- Non-loopback HTTP MCP transport remains elevated risk (see control-plane / system overview trust notes).

### 6.5 Testing and verification

- Tests that encode multi-surface registry behavior: `ipfs_kit_py/mcp_server/tests_e2e_interop.py` (note hard-assert/tool-count drift).  
- Packaging verification: `rg -n 'ipfs-kit-mcp|TOOL_GROUPS' pyproject.toml ipfs_kit_py/mcp_server/`.  
- Registry measurement (offline): control-plane guide §2.3 Python snippet with `IPFS_KIT_AUTO_INSTALL_BINARIES=0`.  
- Legacy production guard smoke: import paths under `ipfs_kit_py/mcp/servers/` with `IPFS_KIT_MCP_MODE=production` and without allow flag.  
- After acceptance: add or retarget CI so “production recommended path” matches the confirmed option; quarantine or relabel dual-stack suites.

---

## 7. Alternatives considered

| Alternative | Why considered | Why rejected / deferred | Confidence |
|---|---|---|---|
| Accept Option A in this draft without maintainer confirmation | Packaging already points at MCP++ | Forbidden: competing trees + U-11 require confirmation; index requires Proposed | **Accepted** process rule |
| Declare dual production forever (Option B) as default | Large legacy tests/docs | Defers conflict permanently; not evidenced as intentional dual product | **Inferred** cost |
| Promote migration-guide unified server as sole authority (Option C) | Many docs/tests still center it | Conflicts with packaged console scripts and MCP++ stack | **Inferred** |
| Collapse registry invariant into “authority Accepted” | Single ADR title covers both | Authority is open; registry is implemented—must stay labeled separately | **Accepted** evidence split |
| Invent tool-count contract as 29 without regenerating artifacts | Matches registry | Leaves JS/manifest/tests wrong; C-MCP-TOOLS stays live | **Proposed** fix path R1 later |
| Do nothing / omit ADR body | Slot pre-registered | Blocks honest control-plane guidance and agent confirmation workflow | Rejected for this task |

At least one alternative (including status quo) is required — status quo is Option “Status quo” in §3.2.

---

## 8. Unknowns and owner confirmation

| Field | Value |
|---|---|
| **Confirmation owner** | **MCP / control-plane maintainers** for production runtime authority and tool-registry published contract; documentation maintainers for post-decision guide/migration doc alignment |
| **Confirmation question** | Is `ipfs_kit_py.mcp_server` (MCP++, `ipfs-kit-mcp` / `ipfs-kit-mcp-tools`) the **sole supported production MCP runtime** for new deployments, with `ipfs_kit_py.mcp`, root `mcp/`, and `servers/` strictly compatibility/historical/experimental—and is the published tool contract live `TOOL_GROUPS` (R1), JS manifest (R2), or an explicit dual-count rule (R3)? |
| **What “Accepted” requires** | Explicit maintainer statement selecting Option A/B/C (and R1–R3 as needed) **plus** rank-1–4 alignment (packaging, tests, and status-honest doc updates); update this ADR header and §3 Status; do not promote from guide rewrites alone |
| **Blocking for** | Closing U-11 / C-MCP-TREES in architecture guides as settled; treating migration/VFS “production runtime” claims as resolved; KDOC follow-ons that depend on sole-runtime language (e.g. later authority-sensitive API and audit tasks) |
| **Related U-IDs / conflicts** | U-11, C-MCP-TREES, C-MCP-TOOLS |

**Open unknowns:**

1. Sole production runtime among competing trees — unknown / maintainer confirmation needed (U-11).  
2. Published tool-count contract among 29 / 28 / stale README — unknown / maintainer confirmation needed (C-MCP-TOOLS).  
3. Legacy dashboard lifecycle (maintain, archive, re-bind) — unknown / maintainer confirmation needed.  
4. Whether packaged `ipfs-kit daemon` (or equivalent) should keep importing legacy `mcp/` daemon classes — unknown / maintainer confirmation needed.  
5. Receipt / coordination store multi-node defaults — unknown / maintainer confirmation needed (map §6; not closed by runtime choice alone).

---

## 9. Supersession and relationships

| Relation | ADR / doc |
|---|---|
| Supersedes | none |
| Superseded by | none |
| Related ADRs | ADR-0008 (cluster control-plane authority — separate family choice); ADR-0004 (AnyIO/sync boundaries may affect server runtime); ADR-0009 (doc toolchain, not runtime) |
| Architecture guides | [`../MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md), [`../RUNTIME_AND_ENTRYPOINTS.md`](../RUNTIME_AND_ENTRYPOINTS.md), [`../SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md), [`../GLOSSARY.md`](../GLOSSARY.md) |
| Source-of-truth map | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §6 |
| Competing / historical narrative (not acceptance) | [`../../MCP_SERVER_MIGRATION_GUIDE.md`](../../MCP_SERVER_MIGRATION_GUIDE.md) |

---

## 10. Follow-up actions

| Action | Owner | Notes |
|---|---|---|
| Confirm Option A/B/C (+ R1–R3) | MCP / control-plane maintainers | Only then promote Status → Accepted or Rejected |
| Keep guides status-honest (Proposed, not Accepted) | Documentation maintainers | Control-plane guide already links this ADR as Proposed |
| After acceptance: align migration guide + VFS production claims | Documentation maintainers | Do **not** do this as a silent side effect of drafting this ADR |
| Regenerate JS manifest / fix e2e hard-assert vs registry | MCP maintainers | Clears C-MCP-TOOLS when counts agree |
| Decide CLI daemon → legacy `mcp/` coupling | MCP / CLI maintainers | Map §6 open item |
| Index row refresh when status changes | Framework / KDOC-020 owners | Body task must not silently rewrite `decisions/README.md` under conflict policy |

---

## 11. Review checklist (authors)

- [x] Filename is `0003-mcp-runtime-authority.md` (not left as 0000)
- [x] Banner **Decision status** matches §3 **Status** (`Proposed`)
- [x] **Current behavior** is evidence-backed and separate from the proposal
- [x] No present-tense “the system does X” for Proposed-only sole-authority intent
- [x] Every material *why* uses **Accepted / Proposed / Inferred / Unknown**
- [x] No Inferred or Unknown claim is written as Accepted history
- [x] Evidence table prefers ranks 1–4 for Accepted claims
- [x] Alternatives include status quo or an explicit reject
- [x] Confirmation owner and question filled (Proposed)
- [x] No secrets, live tokens, or host-specific credential paths
- [x] `docs/architecture/decisions/README.md` was **not** edited by this task
- [x] Related architecture guide already cites this ADR with status-honest language (MCP_CONTROL_PLANE)

---

## Appendix A — Measurement snapshot (supporting)

Offline measurement pattern (re-run when registry changes):

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
# See MCP_CONTROL_PLANE.md §2.3 for the TOOL_GROUPS / JS manifest count script.
rg -n 'ipfs-kit-mcp|TOOL_GROUPS|HierarchicalToolManager|register_fastmcp' \
  pyproject.toml ipfs_kit_py/mcp_server/
```

Baseline cited by control-plane guide at last verification of that doc: **12 groups / 29 `TOOL_GROUPS` tools; 28 JS manifest tools; registry-only `iroh_diagnostics`**.

## Appendix B — Disputed documentation (must not be treated as resolved)

| Document / claim | Why disputed | Treatment while this ADR is Proposed |
|---|---|---|
| `docs/MCP_SERVER_MIGRATION_GUIDE.md` — unified_mcp_server as canonical production import | Conflicts with packaging → `mcp_server` | Historical / competing narrative; cite as conflict, do not “fix” by ADR draft alone |
| VFS contract / audits naming `mcp.servers.unified_mcp_server` as production runtime | Same C-MCP-TREES conflict | Leave open; align only after confirmation |
| `mcp_server/README.md` tool counts (21 / 7 in places) | Stale vs measured 29 | Ignore for contracts; regenerate/fix after R1–R3 |
| Architecture guides describing packaged MCP++ | Correct for packaging; **not** sole-authority acceptance | Keep “packaged current” + link this Proposed ADR |

---

## Appendix C — Status and confidence cheat sheet

**Decision status (header / §3):** `Proposed` (required until confirmation)

**Rationale confidence (§4 markers):** `Accepted` · `Proposed` · `Inferred` · `Unknown`

**Forbidden without evidence + confirmation:**

- Inferred rationale → Accepted decision narrative  
- Proposed authority → Accepted default in guides  
- Documentation-only claim → Accepted production behavior  
- Treating disputed migration/VFS docs as resolved by authorship of this file  

See [`README.md`](./README.md) §§3–4 for full promotion rules.
