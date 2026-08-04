# ADR-0004: AnyIO, Trio, asyncio, and sync boundaries

> **Document class:** Proposed  
> **Decision status:** Proposed  
> **Date:** 2026-08-04  
> **Last verified:** 2026-08-04  
> **Evidence baseline:** tree `57ae7a4c8ad1638d8b623f8cb560d4dac8b4b686` (current workspace HEAD); architecture guide KDOC-018 ([`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../ASYNC_AND_OPTIONAL_DEPENDENCIES.md)); map §8  
> **Authors:** KDOC-024 (implementation daemon)  
> **Confirmation owner:** async / runtime maintainers (AnyIO end-state and library default backend); documentation maintainers for status-honest guide cross-links  
> **Supersedes:** none  
> **Superseded by:** none  
> **Related guides:** [`../ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../ASYNC_AND_OPTIONAL_DEPENDENCIES.md), [`../RUNTIME_AND_ENTRYPOINTS.md`](../RUNTIME_AND_ENTRYPOINTS.md), [`../MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md), [`../SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md), [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §8  
> **Related conflicts / U-IDs:** U-14 (AnyIO end-state; shared with ADR-0001 for missing-extra degradation policy)

Process contract:
[`README.md`](./README.md) · Claim standard:
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)

---

## 1. Context

ipfs-kit is a multi-surface Python product: library import, operator CLI, packaged
MCP++ server and tools CLI, Iroh CLIs, fsspec protocols, dual library modules,
and legacy MCP trees. These surfaces do **not** share one event-loop stack.

Forces that require a recorded decision:

1. **Mixed runtime is real** — AnyIO (default and trio-pinned), deliberate
   `asyncio.run` entry points, sync kit APIs, and dual `foo.py` /
   `foo_anyio.py` twins coexist in the same tree.
2. **Portable AnyIO/Trio goals** for long-lived MCP++ conflict with
   asyncio-contract subsystems (notably managed Iroh clients) unless boundaries
   are explicit.
3. **Sync ↔ async bridging** is easy to get wrong: nested loops, `nest_asyncio`,
   and blocking kit calls on the event-loop thread break Cancellation,
   cooperativeness, and backend neutrality.
4. **Migration reports overclaim** — historical `docs/ANYIO_MIGRATION.md` and
   related summaries must not be treated as proof of universal conversion
   (KDOC-G025 / map §8 / U-14).
5. **Owner decisions remain open** for AnyIO end-state and the default library
   backend outside MCP++. Agents must not invent acceptance.

**In scope:**

- Observed AnyIO / Trio / asyncio / sync roles by surface (current behavior).
- Portable AnyIO and structured-concurrency goals where already implemented.
- Deliberate sync and asyncio compatibility boundaries (including thread offload
  and process-thread isolation).
- Cancellation and thread-offload consequences across those boundaries.
- Rejected claim of universal AnyIO conversion as product fact.
- Options and confirmation requests for unresolved end-state policy (U-14).

**Out of scope:**

- Lazy import / packaging-extra degradation end-state detail owned by
  [ADR-0001](./0001-imports-and-optional-dependencies.md) (U-14 remainder for
  stub-vs-fail-closed is shared but not re-decided here).
- MCP production **tree** authority (which package is sole production MCP) —
  [ADR-0003](./0003-mcp-runtime-authority.md) / U-11. This ADR only records the
  **async stack** of packaged MCP++ as implemented.
- Cluster family choice (ADR-0008), HLA module authority (C-HLA / U-03) except
  as it affects which async helpers are “the” high-level path.
- Rewriting historical migration docs or deleting dual modules.
- Editing [`README.md`](./README.md) (framework-owned; KDOC-020).

---

## 2. Current behavior (evidence, not aspiration)

Present tense describes the tree as measured. It does **not** assert that the
mixed stack is the permanent product end-state.

### 2.1 Surface matrix (observed)

| Surface / path | Observed role | Evidence (source, test, packaging) | Status label |
|---|---|---|---|
| Package import `import ipfs_kit_py` | Sync, side-effect-light; no process-owned loop | `ipfs_kit_py/__init__.py`; ADR-0001; JIT/lazy load | **Active** — caller owns any later loop |
| Kit / HLA sync APIs | Synchronous methods typical; async helpers optional | `ipfs_kit`, `IPFSSimpleAPI` paths; dual helpers under `high_level_api/*_anyio.py` | **Active** sync-first library |
| Operator CLI `ipfs-kit` | Process-owned AnyIO via `anyio.run(main)` / `sync_main` | `pyproject.toml` → `ipfs_kit_py.cli:sync_main`; `cli.py` | **AnyIO default backend** (not trio-pinned) |
| MCP++ server `ipfs-kit-mcp` | Process-owned **AnyIO + trio**; stdio / HTTP / P2P | `mcp_server/server.py`: `anyio.run(..., backend="trio")`; Hypercorn trio for HTTP | **Packaged long-lived** trio pin |
| MCP++ tools CLI `ipfs-kit-mcp-tools` | One-shot **AnyIO + trio** dispatch | `mcp_server/cli.py`: `anyio.run(tm.dispatch, …, backend="trio")` | **Packaged** trio pin |
| MCP++ → sync kit | Blocking kit offloaded off the loop thread | `mcp_server/core_operations.py`: `await anyio.to_thread.run_sync(...)` | **Implemented boundary** |
| MCP++ → Iroh asyncio client | Foreign asyncio stack in worker thread | `mcp_server/tools/iroh_tools.py`: `to_thread.run_sync(lambda: asyncio.run(...))` | **Deliberate isolation** |
| Iroh ops / diagnostics / interop CLIs | Process-owned **`asyncio.run`** | `iroh/cli.py`, `diagnostics_cli.py`, `multinode.py`, `service.py`, … | **Deliberate asyncio** |
| Dual library modules | ~46 `*_anyio.py` twins under `ipfs_kit_py/` (each with a sync twin) | e.g. `cluster_state_anyio.py`, `arrow_metadata_index_anyio.py`, WAL telemetry `*_anyio.py`, many `mcp/controllers/*_anyio.py` | **Active mixed dual stack** |
| Packaging deps | `anyio>=3.7.0`, `trio>=0.22.0` declared | `pyproject.toml`, `requirements.txt` | **Declared** |
| Test harness | `anyio_mode = auto`; pytest-asyncio + pytest-trio | `pytest.ini`; `tests/test_anyio_migration.py` (both backends) | **Active** |
| Historical migration notes | Campaign reports, bulk refactor tool | `docs/ANYIO_MIGRATION.md`, `docs/COMPLETE_ANYIO_MIGRATION_SUMMARY.md`, `tools/asyncio_to_anyio_bulk_refactor.py` | **Non-authoritative archaeology** |
| Stale API mapping | Invented AnyIO names | `docs/development/async_architecture.md` (F-009); corrected in async guide §4 | **Not product policy** |

### 2.2 Scale snapshot (package tree, approximate)

Measured under `ipfs_kit_py/` at the evidence baseline (counts aid honesty; they
are **not** a completion metric):

| Observation | Approx. count / fact |
|---|---|
| Modules importing AnyIO | ~310 |
| Modules importing asyncio (often Iroh-focused) | ~12 (several asyncio-only) |
| Dual `*_anyio.py` files | 46 (all have a corresponding non-`_anyio` twin) |
| Direct `import trio` in production package | Rare (AnyIO selects trio via `backend="trio"`) |

**Narrative:**

1. **AnyIO is the dominant portable async façade** for packaged CLI and MCP++
   and for many library twins.
2. **Trio is required on packaged MCP++ surfaces**, not as a global library
   default.
3. **asyncio remains deliberate** for Iroh-facing process entries and for the
   worker-thread isolation pattern under MCP++.
4. **Sync kit remains first-class**; async hosts reach it through
   `anyio.to_thread.run_sync`, not by pretending kit methods are awaitables.
5. **Dual modules are partial by design of history**, not proof of finished
   migration. Callers must import the twin that matches their stack.
6. **No universal “fully AnyIO” claim is supportable** from migration filenames
   or dual-module counts alone (U-14).

### 2.3 Cancellation and offload (observed primitives)

| Context | Cancellation / timeout primitive | Thread / loop boundary |
|---|---|---|
| AnyIO task groups | `async with anyio.create_task_group()`; `tg.cancel_scope.cancel()` | Structured concurrency under the process loop |
| Hard timeout | `with anyio.fail_after(t):` → built-in `TimeoutError` | Used in dual modules, API anyio, WAL websocket, libp2p helpers |
| Soft timeout | `with anyio.move_on_after(t):` | Cancel quietly; resume without always raising |
| Backend-correct cancel catch | `except anyio.get_cancelled_exc_class():` | e.g. `api_anyio.py`, `cache/async_operations_anyio.py`, `pin_metadata_index.py` |
| Asyncio-native cancel | `asyncio.CancelledError` | Iroh service / multinode / blob paths under asyncio |
| Shielded sections | `anyio.CancelScope(shield=True)` | e.g. `api_anyio.py` cleanup paths |
| Async → sync blocking | `await anyio.to_thread.run_sync(fn, …)` | MCP++ core_operations; dual modules (Arrow index, cache, …) |
| Sync worker → async | `anyio.from_thread.run(...)` | Present in examples/wrappers; not the MCP++ kit default |
| Foreign asyncio under trio | `to_thread` + fresh `asyncio.run` | `iroh_tools.py` — **not** nested on the trio thread |

Cancellation **does not** reliably abort native blocking I/O already running
inside a worker thread. External daemons (Kubo, Iroh, Lotus) cancel via process
managers and OS signals, independent of Python cancel scopes.

---

## 3. Decision

**Status:** Proposed  

### 3.1 Decision statement

This ADR records **implemented constraints** (honest mixed runtime) and
**open end-state options** that still need owner confirmation.

#### A. Implemented constraints (record as verified current policy; not “end-state accepted”)

Until a future revision promotes or amends them with maintainer confirmation,
architecture and new code **must respect** the following as **observed product
constraints**:

1. **Backend is surface-specific.**
   - Packaged MCP++ server and tools CLI run under **AnyIO with `backend="trio"`**.
   - Operator `ipfs-kit` runs under **AnyIO with the default backend** (not
     trio-pinned in `sync_main`).
   - Several Iroh process entries use deliberate **`asyncio.run`**.
   - Library embedders **own** their process and loop; package import does not
     create one.

2. **Portable AnyIO is the preferred façade for new async library and dual-module
   work** that must run under both asyncio and trio backends (MCP++ requires
   trio-compatible APIs). Prefer `anyio.sleep`, task groups, `fail_after` /
   `move_on_after`, `to_thread.run_sync`, and `get_cancelled_exc_class()` over
   asyncio-only primitives on shared hot paths.

3. **Sync kit under async hosts is offloaded**, not nested:
   - Prefer `await anyio.to_thread.run_sync(...)` for blocking kit / disk / CPU
     work on the loop thread (MCP++ `core_operations._call` is the reference).
   - **Do not** nest event loops on one thread (`run_until_complete` on a running
     loop, recursive `asyncio.run` inside the same loop, `nest_asyncio`).

4. **Foreign asyncio stacks under trio hosts use process-thread isolation**
   (worker thread + own `asyncio.run`), as in `iroh_tools.py` — not
   cross-backend re-entrancy on the trio thread.

5. **Dual `foo` / `foo_anyio` modules are a deliberate compatibility pattern in
   the current tree**, not evidence of completed universal migration. Import the
   twin that matches the caller; do not assume API parity without reading the
   module and tests.

6. **Universal AnyIO conversion is rejected as a claim about the current
   product.** Migration reports and bulk refactor tools are historical. Guides
   and ADRs must describe the mixed runtime honestly (U-14).

7. **Valid AnyIO API set** for docs and new code excludes invented names
   (`anyio.gather`, `anyio.create_task`, `anyio.TimeoutError`). Use the mapping
   in [`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../ASYNC_AND_OPTIONAL_DEPENDENCIES.md)
   §4 (F-009 correction).

#### B. Open product decisions (require confirmation — U-14)

The following are **not** accepted by this ADR:

| Open decision | Why open |
|---|---|
| **AnyIO end-state** | Deliberate long-term dual stack vs continued migration toward AnyIO-only (or another single stack) |
| **Default library backend** | Whether library examples / embedder defaults should prefer asyncio, trio, or “caller-defined only” outside MCP++ |
| **Sunset policy for dual modules** | Whether `*_anyio.py` twins remain permanent, get merged, or get deprecated on a schedule |
| **Global optional-extra degradation** | Owned primarily with ADR-0001; remains per-subsystem until confirmed |

### 3.2 Options (required while Status is Proposed)

#### End-state for async stack (U-14 primary)

| Option | Summary | Fit / risk |
|---|---|---|
| **A — Deliberate dual stack (long-term)** | Keep sync kit + dual anyio twins + surface-specific backends; document boundaries permanently | Lowest migration cost; ongoing dual-maintenance and agent confusion if docs slip |
| **B — Continued migration to AnyIO façade** | New code AnyIO-only; shrink dual modules and asyncio-only paths over time; keep deliberate asyncio only where contracts force it (Iroh) | Aligns with MCP++ trio + portable tests; multi-release effort; must not claim completion early |
| **C — Single-backend product (asyncio-only or trio-only)** | Pick one backend for all packaged surfaces and library defaults | Breaks either MCP++ trio pin or Iroh asyncio contracts without large rewrites |
| **Status quo without end-state** | Describe mixed reality; no sunset or migration target | Matches today; U-14 stays open; agents may re-litigate |

**Selected option (if any):** none yet — awaiting confirmation.  
**Leading Proposed direction for new code (not Accepted end-state):** behave as
**B for new work** (AnyIO façade, trio-compatible on MCP paths) while
**A describes current tree structure** until maintainers choose A, B, or C
explicitly.

#### Library default backend (outside MCP++)

| Option | Summary |
|---|---|
| **L1** | Caller-defined only; docs never pin a library default |
| **L2** | Prefer asyncio for library examples (AnyIO default backend) |
| **L3** | Prefer trio for library examples (align with MCP++) |

**Selected:** none yet — awaiting confirmation. Observed packaging and operator
CLI behavior are closer to **L2** for short-lived processes and **L1** for
embeds; MCP++ remains trio regardless.

---

## 4. Rationale (confidence-labeled)

**Accepted:**

- Packaged MCP++ pins trio: `mcp_server/server.py` and `mcp_server/cli.py` call
  `anyio.run(..., backend="trio")`; HTTP uses Hypercorn’s trio worker. This is
  implemented runtime, not aspirational prose (also recorded as I-ASYNC in
  MCP control-plane guide).
- Sync kit under MCP++ is offloaded via `anyio.to_thread.run_sync` in
  `core_operations.py`.
- Operator CLI entry `ipfs_kit_py.cli:sync_main` drives work with `anyio.run`
  without a trio pin in that entry path.
- Dual `*_anyio.py` modules exist in volume (~46) with matching sync twins;
  asyncio-native Iroh modules remain.
- Packaging declares both `anyio` and `trio`; pytest is configured with
  `anyio_mode = auto`.
- Nesting event loops is out of architecture policy per the KDOC-018 guide and
  is not a supported product pattern.

**Proposed:**

- Long-term AnyIO end-state is **Option B for new code** (portable AnyIO façade,
  deliberate asyncio only at forced contracts) while retaining dual modules until
  a confirmed sunset plan exists.
- Library default backend remains **caller-defined** in embeds (**L1**), with
  short-lived CLI examples free to use AnyIO default (**L2**), without forcing
  trio on non-MCP library paths.
- Cancellation and offload rules in §3.1 and §6 should be treated as the
  **recommended** contract for new code once this ADR is accepted; they already
  match MCP++ and the architecture guide.

**Inferred:**

- Dual modules arose from incremental AnyIO migration campaigns rather than a
  single up-front dual-stack product design. Filename-level migration summaries
  support a campaign narrative but not a complete conversion.
- Iroh’s asyncio boundary is driven by client/transport contracts and CLI
  isolation needs, not by a global preference for asyncio over AnyIO.

**Unknown:**

- Whether maintainers will freeze the dual-stack pattern permanently or fund a
  multi-release consolidation — unknown / maintainer confirmation needed.
- Whether any non-MCP packaged entry will be trio-pinned in the future —
  unknown / maintainer confirmation needed.
- Exact cancellation SLAs for kit work abandoned at the thread boundary under
  client disconnect — unknown / maintainer confirmation needed.
- Global missing-extra degradation (stub vs fail-closed) — see ADR-0001 / U-14;
  unknown as a single product rule.

---

## 5. Evidence

| Rank | Claim | Citation |
|---|---|---|
| 1 | MCP++ runs AnyIO with trio backend on all transports | `ipfs_kit_py/mcp_server/server.py` (`anyio.run(..., backend="trio")`); Hypercorn trio import for HTTP |
| 1 | MCP tools CLI pins trio | `ipfs_kit_py/mcp_server/cli.py` |
| 1 | Sync kit offload under MCP++ | `ipfs_kit_py/mcp_server/core_operations.py` (`to_thread.run_sync`) |
| 1 | Iroh asyncio isolated under trio MCP++ | `ipfs_kit_py/mcp_server/tools/iroh_tools.py` |
| 1 | Operator CLI AnyIO entry | `ipfs_kit_py/cli.py` (`sync_main` → `anyio.run`); console script in `pyproject.toml` |
| 1 | Backend-portable AnyIO tests | `tests/test_anyio_migration.py`; `@pytest.mark.anyio` usage elsewhere |
| 1 | Cancellation primitives in dual modules | `anyio.fail_after` / `move_on_after` / `CancelScope` / `get_cancelled_exc_class` across `api_anyio.py`, `cache/async_operations_anyio.py`, `wal_websocket.py`, etc. |
| 2 | Dependencies and scripts | `pyproject.toml` (`anyio`, `trio`, console scripts); `requirements.txt` |
| 2 | pytest AnyIO mode | `pytest.ini` `anyio_mode = auto` |
| 3 | Dual-module public surfaces | 46 `*_anyio.py` under `ipfs_kit_py/`; map §8 dual-module note |
| 3 | Architecture narrative (supporting, not sole proof) | [`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../ASYNC_AND_OPTIONAL_DEPENDENCIES.md) §§2–5, §9–10 |
| 4 | Shared open decision U-14 | [`SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §8; ADR-0001 banner; this ADR |
| 5 | Historical migration reports | `docs/ANYIO_MIGRATION.md`, `docs/COMPLETE_ANYIO_MIGRATION_SUMMARY.md` — **not** acceptance of universal conversion |
| 5 | MCP control-plane I-ASYNC | [`MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md) |

**Evidence that is explicitly insufficient for Accepted end-state status:**

- Migration doc titles or “anyio migration complete” checkboxes in roadmaps.
- Raw counts of `import anyio` vs `import asyncio`.
- Presence of dual modules without an owner-confirmed sunset or permanence policy.
- Agent inference that “MCP++ uses trio, therefore the whole product is trio.”

---

## 6. Consequences

### 6.1 Positive

- Operators and agents can **choose the correct boundary** per entry point
  without inventing a single global stack.
- MCP++ keeps a **single cooperative trio loop** while still calling sync kit
  and asyncio-bound Iroh tools safely.
- Portable AnyIO APIs improve **backend-neutral tests** (`anyio_mode = auto`).
- Explicit rejection of universal-conversion claims reduces documentation drift
  and false “fully migrated” narratives.

### 6.2 Negative / costs

- Dual modules and mixed backends increase **review and onboarding cost**.
- Thread offload means Cancellation of an MCP request may leave kit work
  finishing (or stuck) in a worker thread until the underlying I/O returns.
- Contributors must learn **three mental models** (sync, AnyIO/trio, asyncio)
  and the isolation patterns between them.
- Incomplete dual twins create **parity traps** when only one side is updated.

### 6.3 Migration and compatibility

- **No forced mass conversion** is authorized by this ADR.
- New async code on shared paths should use **valid AnyIO APIs** (§3.1 / guide §4).
- Existing asyncio Iroh CLIs and dual modules remain supported as **current**
  surfaces until an accepted end-state option says otherwise.
- Historical `docs/ANYIO_MIGRATION.md` stays non-authoritative; link the
  architecture guide and this ADR instead.

### 6.4 Security and trust

- Blocking the MCP++ trio thread with long sync I/O is an availability hazard
  (denial of cooperative scheduling); offload is a reliability control, not
  only a style preference.
- Worker threads running kit or `asyncio.run` inherit process credentials; do
  not treat thread isolation as a security sandbox.
- Credentials: none in this ADR.

### 6.5 Testing and verification

- Backend-portable library tests: `@pytest.mark.anyio` with auto mode; avoid
  hard trio-only assumptions unless the test is MCP++-specific.
- MCP++ paths: exercise trio pin and `to_thread` offload (see
  `mcp_server/tests_e2e_interop.py` and related).
- Focused smoke: `tests/test_anyio_migration.py`.
- Doc validation for this task: file non-empty and contains **Cancellation**
  discussion (this section and §2.3).

Suggested maintainer re-check commands:

```bash
rg -n 'anyio\.run|backend=.trio.|hypercorn' ipfs_kit_py/mcp_server/server.py ipfs_kit_py/mcp_server/cli.py
rg -n 'to_thread\.run_sync' ipfs_kit_py/mcp_server/core_operations.py
rg -n 'asyncio\.run' ipfs_kit_py/mcp_server/tools/iroh_tools.py
rg -n 'anyio\.run' ipfs_kit_py/cli.py
find ipfs_kit_py -name '*_anyio.py' | wc -l
```

---

## 7. Alternatives considered

| Alternative | Why considered | Why rejected / deferred | Confidence |
|---|---|---|---|
| Claim universal AnyIO migration complete | Matches some roadmap checkboxes and migration report titles | Contradicts dual modules, deliberate asyncio Iroh paths, and U-14 / KDOC-G025 | **Accepted** rejection of the *claim* |
| Force trio on all packaged CLIs and library defaults | Align everything with MCP++ | Breaks or burdens asyncio Iroh contracts and short-lived CLI simplicity; no evidence of product decision | **Proposed** reject unless confirmed as Option C |
| Force asyncio everywhere; drop trio | Simpler mental model for some contributors | Contradicts packaged MCP++ trio pin and Hypercorn trio worker | **Proposed** reject unless MCP++ is reworked under a new ADR |
| Nest event loops / `nest_asyncio` for sync façades | Appears in historical demos | Breaks Cancellation, backends, and maintenance; out of architecture policy | **Accepted** rejection as product policy |
| Delete all dual modules immediately | Reduce dual maintenance | High breakage; no confirmed sunset plan | **Deferred** until end-state Option B/C accepted with plan |
| Status quo silence (no ADR) | Lowest writing cost | Re-litigation; agents invent “fully AnyIO” or “always trio” | **Rejected** as documentation strategy |

At least status quo and universal-conversion claim are explicitly handled.

---

## 8. Unknowns and owner confirmation

| Field | Value |
|---|---|
| **Confirmation owner** | Async / runtime maintainers (primary); documentation maintainers for guide status language; packaging maintainers if entry-point backend pins change |
| **Confirmation question** | (1) Is the long-term AnyIO end-state **deliberate dual stack (A)**, **continued migration to AnyIO façade (B)**, or **single-backend (C)**? (2) Outside MCP++, is the library default backend **caller-only (L1)**, **asyncio-preferring (L2)**, or **trio-preferring (L3)**? |
| **What “Accepted” requires** | Explicit maintainer answer to the questions above **and** (for any sunset) a dual-module / asyncio-entry migration or permanence note with rank-1–4 evidence; update §3 selected options and this section |
| **Blocking for** | Claiming a single product async stack; dual-module deletion programs; changing MCP++ off trio; library “default backend” mandates in embedder docs |
| **Related U-IDs / conflicts** | U-14; map §8 items 1–2; shared degradation policy with ADR-0001; C-HLA / U-03 (which HLA async helpers are canonical) |

**Open unknowns:**

1. AnyIO end-state (A / B / C) — unknown / maintainer confirmation needed.  
2. Library default backend (L1 / L2 / L3) — unknown / maintainer confirmation needed.  
3. Dual-module sunset schedule or permanence — unknown / maintainer confirmation needed.  
4. Cancellation SLA for in-flight `to_thread` kit work after client disconnect — unknown / maintainer confirmation needed.  
5. Whether any additional packaged entry points will pin trio — unknown / maintainer confirmation needed.

---

## 9. Supersession and relationships

| Relation | ADR / doc |
|---|---|
| Supersedes | none |
| Superseded by | none |
| Related ADRs | [ADR-0001](./0001-imports-and-optional-dependencies.md) (lazy imports / extras; shared U-14 degradation); [ADR-0003](./0003-mcp-runtime-authority.md) (MCP tree authority; trio stack is separate) |
| Architecture guides | [`ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../ASYNC_AND_OPTIONAL_DEPENDENCIES.md) (authoritative narrative; this ADR is the decision record), [`RUNTIME_AND_ENTRYPOINTS.md`](../RUNTIME_AND_ENTRYPOINTS.md), [`MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md), [`SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md) |
| Source-of-truth map | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §8 |
| Historical (non-authority) | `docs/ANYIO_MIGRATION.md`, `docs/COMPLETE_ANYIO_MIGRATION_SUMMARY.md`, `docs/development/async_architecture.md` (stale) |

---

## 10. Follow-up actions

| Action | Owner | Notes |
|---|---|---|
| Confirm end-state option A/B/C and library default L1/L2/L3 | Async / runtime maintainers | Promote this ADR Proposed → Accepted (or amend options) |
| Keep architecture guide and this ADR status-aligned | Documentation maintainers | Guide describes current mixed reality; must not claim Accepted end-state early |
| Prefer valid AnyIO APIs on new shared async paths | Contributors | Guide §4 mapping; no invented AnyIO names |
| Preserve MCP++ trio pin unless a new ADR changes it | MCP maintainers | Coupled to Hypercorn trio and tool offload design |
| Do not mass-delete dual modules without accepted sunset | All | Option A vs B decision first |
| Optional: index README row status when framework task allows | KDOC-020 owner | Numbered ADR tasks must not edit `decisions/README.md` |

---

## 11. Review checklist (authors)

- [x] Filename is `0004-anyio-and-sync-boundaries.md` (not left as 0000)
- [x] Banner **Decision status** matches §3 **Status** (Proposed)
- [x] **Current behavior** is evidence-backed and separate from open end-state options
- [x] No present-tense “the system is fully AnyIO” for Proposed-only intent
- [x] Every material *why* uses **Accepted / Proposed / Inferred / Unknown**
- [x] No Inferred or Unknown claim is written as Accepted end-state history
- [x] Evidence table prefers ranks 1–4 for implemented constraints
- [x] Alternatives include status quo and rejected universal-conversion claim
- [x] Confirmation owner and questions filled (Proposed)
- [x] No secrets, live tokens, or host-specific credential paths
- [x] `docs/architecture/decisions/README.md` was **not** edited by this task
- [x] Related architecture guide can cite this ADR with status-honest language
- [x] **Cancellation** and thread-offload consequences are recorded (§2.3, §6)

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
- Proposed end-state → Accepted default in guides  
- Documentation-only claim → Accepted production behavior  
- Migration report titles → Accepted “fully AnyIO” product fact  

See [`README.md`](./README.md) §§3–4 for full promotion rules.

---

## Appendix B — Quick boundary chooser (non-normative summary)

```text
Packaged MCP++ (server or tools CLI)?
  → AnyIO + trio; kit via to_thread; Iroh via worker-thread asyncio.run

Operator ipfs-kit CLI?
  → anyio.run, default backend; short-lived process

Iroh ops/diagnostics/interop CLI?
  → deliberate asyncio.run; do not nest

Library embed (caller owns process)?
  → sync kit/HLA for sync hosts;
    AnyIO APIs + to_thread for AnyIO hosts;
    do not start a second loop on the caller thread

Need both trio host and asyncio client?
  → isolate asyncio in a worker thread (or child process), never same-thread re-entry
```

This appendix restates §2–3 for operators; the decision and confirmation tables
above remain authoritative for status.
