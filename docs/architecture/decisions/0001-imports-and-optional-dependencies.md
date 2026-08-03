# ADR-0001: Lazy imports and optional dependencies

> **Document class:** Canonical  
> **Decision status:** Accepted  
> **Date:** 2026-08-03  
> **Last verified:** 2026-08-03  
> **Evidence baseline:** tree `ddf1c8608c93332e17b3f0243a46d7f50f88ab1b` (current workspace HEAD)  
> **Authors:** KDOC-021 (implementation daemon)  
> **Confirmation owner:** documentation / packaging maintainers (global degradation end-state only; see §8)  
> **Supersedes:** none  
> **Superseded by:** none  
> **Related guides:** [`../ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../ASYNC_AND_OPTIONAL_DEPENDENCIES.md), [`../RUNTIME_AND_ENTRYPOINTS.md`](../RUNTIME_AND_ENTRYPOINTS.md), [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §8  
> **Related conflicts / U-IDs:** U-14 (AnyIO end-state and missing-extra degradation policy; shared with ADR-0004)

Process contract:
[`README.md`](./README.md) · Claim standard:
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)

---

## 1. Context

IPFS Kit is a multi-surface Python package: library import, operator CLI, MCP++
server/tools, fsspec backends, and several binary/installer paths. Optional
capabilities (Arrow indexes, libp2p, FastAPI, ML stacks, Iroh extras, managed
binaries) must not force every consumer to install the full dependency and
binary set at `import ipfs_kit_py` time.

Forces that require a recorded decision:

1. **Import-time cost and reliability** — heavy scientific/ML/installer stacks
   and optional peer stacks must not make ordinary import fail or hang on
   network access.
2. **Air-gapped / CI / agent environments** — read-only and offline hosts must
   be able to import and run focused tests without package-managed downloads.
3. **Capability discovery** — call sites need a consistent way to detect
   whether a feature is present before invoking it.
4. **Degradation honesty** — missing extras currently fail soft, stub, or
   fail-closed depending on subsystem; architecture must not invent a single
   global policy without maintainer confirmation (map §8 #3 / U-14).

**In scope:**

- Lazy / JIT import mechanisms (`jit_imports.py`, core `jit_manager`,
  `_LazyCallableProxy`, deferred getters in package root).
- Packaging extras under `[project.optional-dependencies]`.
- Capability detection flags (`HAS_*`, `*_AVAILABLE`, feature checks).
- No import-time binary download / install intent and the
  `IPFS_KIT_AUTO_INSTALL_BINARIES` opt-in.
- Testing and verification consequences of the above.

**Out of scope:**

- AnyIO / Trio / asyncio **runtime boundary** end-state (owned by
  ADR-0004; this ADR only notes that dual modules and lazy load interact).
- MCP production runtime authority (ADR-0003).
- Which high-level API module is canonical (C-HLA / U-03).
- Exact pin policy for moving-target extras such as `libp2p @ main`
  (product packaging concern; noted as risk only).

---

## 2. Current behavior (evidence, not aspiration)

| Surface / path | Observed role | Evidence (source, test, packaging) | Status label |
|---|---|---|---|
| `ipfs_kit_py/__init__.py` | Package root: lazy proxies, installer availability flags, hard-coded offline bulk download | `_DOWNLOAD_BINARIES_AUTOMATICALLY = False`; `_LazyCallableProxy`; `IPFS_KIT_AUTO_INSTALL_BINARIES` gate around `ensure_kubo_binary` | Active canonical import path |
| `ipfs_kit_py/jit_imports.py` | Central JIT registry: feature definitions, module lists, caches, metrics | `JITImports`, `is_feature_available`, `lazy_import` decorator | Active |
| `ipfs_kit_py/core` (`jit_manager`, `require_feature`, `optional_feature`) | Feature gates with hard (`require`) vs soft (`optional` + fallback) decorators | `ipfs_kit_py/core/__init__.py` | Active (with mock fallbacks if core partial) |
| `ipfs_kit_py/deps_resolver.py` | Optional pip-module resolve + injection helpers | `resolve_module`, `deps_get` / `deps_set` | Active helper |
| `pyproject.toml` `[project.optional-dependencies]` | Declared extras: `iroh`, `fsspec`, `arrow`, `libp2p`, `api`, `ai_ml`, `full`, `dev`, … | Packaging metadata | Active contract |
| Module-local `try/except ImportError` | `HAS_*` / `*_AVAILABLE` capability bits | Widespread (Arrow, libp2p, HuggingFace, installers, …) | Active pattern |
| `kubo_runtime.ensure_kubo_binary` | Managed Kubo path resolve; install only when env opt-in | `__init__.py` + `kubo_runtime.py`; `tests/test_auto_install_binaries.py` | Active |
| MCP `_StubKit` / tool errors | Degraded kit when daemon/kit unavailable | MCP control-plane docs + server paths | Subsystem-specific |
| Dual `foo.py` / `foo_anyio.py` | Optional AnyIO twins loaded on explicit import / first use | ~46 `*_anyio.py` modules under `ipfs_kit_py/` | Active mixed stack |

Narrative: Ordinary `import ipfs_kit_py` resolves a light package surface.
Heavy modules (`ipfs_kit`, WAL, storage kits, filesystem, API app, sibling
project submodules) load through lazy getters or proxies on first attribute
access. Binary installers are exported as callables/flags but bulk
`download_binaries()` does not run at import because
`_DOWNLOAD_BINARIES_AUTOMATICALLY` is `False`. Kubo ensure-with-install runs
only when `IPFS_KIT_AUTO_INSTALL_BINARIES` is a truthy value (`1`, `true`,
`yes`, `on`).

---

## 3. Decision

**Status:** Accepted  

### 3.1 Decision statement

The project **accepts** the following implemented invariants for imports and
optional dependencies:

1. **Lazy / JIT loading is the default for heavy optional and core-heavy
   surfaces.** Package import must remain side-effect-light: defer heavy
   modules via JIT feature gates, `deps_resolver`, deferred getters, and
   `_LazyCallableProxy` (or equivalent).
2. **Optional Python capabilities are packaging extras** declared under
   `[project.optional-dependencies]`, not silent ambient installs. Missing
   extras degrade at feature check or first use, not by crashing every import.
3. **Capability detection is explicit** via feature managers
   (`jit_manager.check_feature` / `is_feature_available`), decorators
   (`require_feature` / `optional_feature`), and module-level
   `HAS_*` / `*_AVAILABLE` flags.
4. **No import-time download or binary install by default.** Ordinary import
   must not download, install, or upgrade executables or pull large installer
   payloads over the network. Bulk `download_binaries()` and package-managed
   Kubo install are **explicit opt-in** (function call and/or
   `IPFS_KIT_AUTO_INSTALL_BINARIES`).
5. **Degradation policy is per-subsystem until a future ADR amends it.** Soft
   fallback, stub, skip, or fail-closed are all in use; there is **no** single
   product-wide “always stub” or “always fail-closed” rule accepted here
   (U-14 remainder).

These are **verified constraints** backed by packaging, source, and focused
tests (§5). Motivations for *why* the tree evolved this way that lack
maintainer record stay **Inferred** or **Unknown** in §4 and must not be
narrated as historical fact.

### 3.2 Options (evaluated)

| Option | Summary | Fit / risk |
|---|---|---|
| **A — Lazy import + packaging extras + offline-by-default install (selected)** | Heavy/optional work deferred; extras declare optional deps; binaries opt-in | Matches current tree, CI/agent safety, multi-surface product |
| **B — Eager import of all optional stacks** | Import always loads Arrow, ML, libp2p, FastAPI, installers | Breaks minimal installs; slow/fragile import; fails CI without full extras |
| **C — Fail-closed at import for any missing optional dep** | Import raises if any optional module absent | Incompatible with optional-extra design; forces monolithic installs |
| **D — Silent network install on import** | Auto-download binaries/deps when missing | Supply-chain and air-gap hazard; rejected by current flags and tests |
| **Status quo without ADR** | Behavior exists but is undocumented as a decision | Re-litigation risk; docs drift (older install narratives) |

**Selected option:** **A** — accepted as the implemented product constraint set.

---

## 4. Rationale (confidence-labeled)

**Accepted:**

- Ordinary package import is engineered to avoid bulk binary download:
  `_DOWNLOAD_BINARIES_AUTOMATICALLY = False` gates the import-time download
  block; `download_binaries()` remains an explicit API (decorated with
  `optional_feature('installer_dependencies', …)`).
- Kubo package-managed install is env-gated:
  `IPFS_KIT_AUTO_INSTALL_BINARIES` must be truthy before
  `ensure_kubo_binary(install=True)`; otherwise only an already-present
  managed binary may be resolved.
- Optional third-party capabilities are expressed as packaging extras in
  `pyproject.toml` (`iroh`, `fsspec`, `arrow`, `libp2p`, `api`, `ai_ml`, …).
- JIT / lazy infrastructure exists as first-class code:
  `JITImports`, core `jit_manager`, `require_feature` / `optional_feature`,
  `deps_resolver.resolve_module`, and `_LazyCallableProxy` on the package root.
- Focused tests encode opt-in install behavior
  (`tests/test_auto_install_binaries.py`) and optional-dependency fallbacks
  (`tests/integration/test_optional_dependencies.py`).

**Proposed:**

- A future maintainer decision may adopt a **documented global degradation
  matrix** (which extras soft-fail vs fail-closed). Until then, architecture
  guides must describe **subsystem** behavior only.
- Aligning all historical docstrings/Quick Start fragments that still *imply*
  ambient install with the offline-import invariant (documentation hygiene;
  does not change the accepted runtime constraint).

**Inferred:**

- Lazy loading and JIT metrics were introduced primarily to keep import fast
  and to support partial feature sets in multi-role deployments (comment in
  `__init__.py`: “Changed to False for JIT optimization”; structure of
  feature-group checks). This is a **plausible structural explanation**, not a
  maintainer-signed history of intent.
- Soft `optional_feature` fallbacks exist to keep host processes (CLI/MCP)
  alive when analytics/installer hooks are absent — inferred from decorator
  semantics and MCP stub patterns, not from a separate product policy memo.

**Unknown:**

- Whether maintainers will ever require a **single** stub-vs-fail-closed rule
  for every optional extra — **unknown / maintainer confirmation needed**
  (U-14 / map §8 #3).
- Preferred long-term story for dual `*_anyio` modules relative to lazy import
  (deliberate dual stack vs migration) — deferred to ADR-0004.
- Whether `libp2p` will remain a moving-target optional extra tracking
  upstream `main` — packaging policy unknown here.

---

## 5. Evidence

| Rank | Claim | Citation |
|---|---|---|
| 1 | Auto-install of binaries is off unless env opt-in | `tests/test_auto_install_binaries.py` (`test_auto_install_ipfs_opt_in` expects `False` when env unset); related Lotus paths in same module |
| 1 | Optional dependency fallbacks allow code paths without full extras | `tests/integration/test_optional_dependencies.py` (e.g. AI/ML paths without pandas) |
| 1 | Import / path safety exercised | `tests/test_ipfs_kit_import.py`, `tests/test_import_paths_validation.py`, `tests/test_cli_import_verification.py` |
| 2 | Optional extras declared in packaging | `pyproject.toml` → `[project.optional-dependencies]` |
| 2 | No default bulk download on import | `ipfs_kit_py/__init__.py`: `_DOWNLOAD_BINARIES_AUTOMATICALLY = False`; conditional `if _DOWNLOAD_BINARIES_AUTOMATICALLY:` block |
| 2 | Kubo ensure-install gated by env | `ipfs_kit_py/__init__.py` reading `IPFS_KIT_AUTO_INSTALL_BINARIES`; `kubo_runtime.ensure_kubo_binary` |
| 3 | Public lazy/JIT contracts | `ipfs_kit_py/jit_imports.py` (`JITImports`, feature checks); `ipfs_kit_py/core/__init__.py` (`require_feature`, `optional_feature`, `jit_manager`); `_LazyCallableProxy` and deferred getters in package root |
| 3 | Optional module resolution helper | `ipfs_kit_py/deps_resolver.py` (`resolve_module`) |
| 4 | Architecture narrative and open owner decisions | [`../ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../ASYNC_AND_OPTIONAL_DEPENDENCIES.md) §§6–8, §10; [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §8; U-14 |
| 5 | Supporting operator/install docs (non-authoritative alone) | `docs/installation_guide.md`, historical phase/coverage notes mentioning optional deps |

**Evidence that is explicitly insufficient for Accepted status:**

- Historical migration reports (`docs/ANYIO_MIGRATION.md`,
  `docs/COMPLETE_ANYIO_MIGRATION_SUMMARY.md`) do not prove universal AnyIO
  completion or a global optional-dep policy.
- Documentation-only claims of “always degrade gracefully” without pointing at
  a specific subsystem’s flag or test.
- Pure inference about *why* a particular extra uses soft vs hard failure.

---

## 6. Consequences

### 6.1 Positive

- Minimal and CI installs can `import ipfs_kit_py` without network or full
  optional stacks.
- Features can be added behind extras and feature flags without bloating the
  core dependency set.
- Operators have an explicit, auditable opt-in (`IPFS_KIT_AUTO_INSTALL_BINARIES`
  and explicit installer APIs/CLIs) for package-managed binaries.
- Agents and air-gapped hosts get a predictable offline-import default.

### 6.2 Negative / costs

- Call sites must check capability flags or catch import/use-time errors;
  “it imported” ≠ “feature works”.
- Multiple parallel mechanisms (JIT manager, local `HAS_*`, try/except,
  stubs) increase cognitive load for contributors.
- Incomplete extras produce subsystem-specific messages; diagnosis requires the
  matrix in the async/optional guide rather than one error type.
- Lazy proxies can obscure import-time failures until first use (harder
  debugging than eager import).

### 6.3 Migration and compatibility

- New optional third-party deps **should** land as a packaging extra plus lazy
  gate; do not add them to core dependencies without an explicit product
  decision.
- Existing eager imports inside leaf modules may remain; prefer converting to
  lazy/JIT when they threaten package-import cost or optional-extra purity.
- Public symbols historically available on the package root should keep lazy
  proxies or documented deferred getters for backward compatibility
  (`ipfs_kit`, installers, WAL helpers, etc.).
- Doc updates that describe install-on-import as default are **incorrect** and
  should be corrected to opt-in language (does not change runtime).

### 6.4 Security and trust

- Offline-by-default import reduces surprise network egress and supply-chain
  exposure during `import`.
- Installers that write under package `bin/` and mutate `PATH` remain powerful;
  they require explicit operator intent.
- Credentials: none in this ADR; do not embed tokens or host-specific secret
  paths in import/installer examples.

### 6.5 Testing and verification

Tests and commands that **encode** this decision:

| Concern | Tests / commands |
|---|---|
| Auto-install off by default | `tests/test_auto_install_binaries.py` (env unset → no install attempt) |
| Auto-install opt-in path | Same module with `IPFS_KIT_AUTO_INSTALL_BINARIES=1` |
| Optional dependency fallbacks | `tests/integration/test_optional_dependencies.py` |
| Import path safety | `tests/test_ipfs_kit_import.py`, `tests/test_import_paths_validation.py`, `tests/test_cli_import_verification.py` |
| Packaging extras presence | `tests/test_iroh_packaging.py` and related packaging tests; inspect `pyproject.toml` |
| Source anchors (smoke) | `rg -n '_DOWNLOAD_BINARIES_AUTOMATICALLY\|IPFS_KIT_AUTO_INSTALL_BINARIES' ipfs_kit_py/__init__.py ipfs_kit_py/kubo_runtime.py` |

**Rules for new tests:**

- Prefer `pytest.importorskip` or feature flags for optional stacks; do not
  require full `[full]` extras for the default suite.
- Never assert that import alone downloads binaries.
- When adding an optional capability, add at least one test that runs **without**
  the extra (skip/fallback) and one that runs **with** it when CI provides the
  extra.
- MCP and daemon tests must not rely on ambient `IPFS_KIT_AUTO_INSTALL_BINARIES`
  unless the test explicitly sets the env and mocks network/install.

---

## 7. Alternatives considered

| Alternative | Why considered | Why rejected / deferred | Confidence |
|---|---|---|---|
| **Eager import of all optional stacks** | Simpler mental model; fail fast at import | Breaks minimal installs; slow import; contradicts extras design and current lazy proxies | Accepted rejection (incompatible with tree) |
| **Fail import if any optional module missing** | Strong guarantee that “import success ⇒ full feature set” | Optional-by-design product; CI/agents would need every extra always | Accepted rejection |
| **Silent / automatic binary download on import** | Convenience for new users | Air-gap, CI, supply-chain, and reproducibility hazards; flags and tests force opt-in | Accepted rejection |
| **Single global “always stub missing extras” policy** | Uniform DX | Not implemented; receipt/integrity and some tools need fail-closed; needs maintainer matrix | Deferred (Unknown / U-14) |
| **Single global “always fail-closed” policy** | Safer semantics for production APIs | Would break soft analytics/installer hooks and many tests that skip extras | Deferred (Unknown / U-14) |
| **Vendoring all optional deps into core** | Fewer extras to document | Package size, license, and conflict risk (e.g. protobuf / transformers) | Rejected as default approach (Inferred product trade-off) |
| **Status quo without ADR** | Avoid process overhead | Architecture guides need a citable decision; index slot ADR-0001 pre-registered | Rejected for documentation program |

At least the status-quo-without-record and silent-install alternatives are
explicitly rejected so they are not rediscovered without reading this ADR.

---

## 8. Unknowns and owner confirmation

| Field | Value |
|---|---|
| **Confirmation owner** | Packaging / core maintainers (for global degradation matrix); async runtime end-state co-owned with ADR-0004 |
| **Confirmation question** | For each packaging extra (or extra class), should missing capability **soft-fallback/stub**, **skip**, or **fail-closed** at the public API boundary? |
| **What “Accepted” already covers** | Lazy/JIT import, packaging extras, capability detection, offline-by-default binary install — no further confirmation required to treat these as product constraints |
| **What full U-14 closure requires** | Explicit degradation matrix **and** AnyIO end-state (latter primarily ADR-0004) with maintainer statement or rank-1–4 evidence of a single policy |
| **Blocking for** | Claims of a universal optional-dependency degradation policy in architecture or operator guides |
| **Related U-IDs / conflicts** | U-14; map §8 unresolved items 1–3; C-HLA / U-03 only as adjacent import-surface note |

**Open unknowns:**

1. Global stub vs fail-closed matrix for missing extras — unknown / maintainer confirmation needed.  
2. Whether documentation default wording in older install guides is fully aligned — process/docs task, not a runtime change.  
3. libp2p extra pin vs `main` tracking — packaging policy unknown here.

---

## 9. Supersession and relationships

| Relation | ADR / doc |
|---|---|
| Supersedes | none |
| Superseded by | none |
| Related ADRs | ADR-0004 (AnyIO/sync boundaries; shares U-14); ADR-0003 (MCP authority, stub kit context only) |
| Architecture guides | [`../ASYNC_AND_OPTIONAL_DEPENDENCIES.md`](../ASYNC_AND_OPTIONAL_DEPENDENCIES.md) (authoritative narrative for mechanisms); [`../RUNTIME_AND_ENTRYPOINTS.md`](../RUNTIME_AND_ENTRYPOINTS.md); [`../MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md) for stub-kit degradation examples |
| Source-of-truth map | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §8 |

---

## 10. Follow-up actions

| Action | Owner | Notes |
|---|---|---|
| Keep architecture guide §§6–8 aligned with this ADR’s Accepted constraints | Docs / KDOC-018 maintainers | Guide already describes mechanisms; cite ADR-0001 with Accepted status for offline import + lazy/extras |
| Do not cite this ADR as settling global stub-vs-fail-closed | All authors | Remain per-subsystem until confirmation |
| ADR-0004 records async end-state options | KDOC-024 | Cross-link U-14 remainder |
| Index row for ADR-0001 may be updated to Accepted | KDOC-020 / framework owner only | Numbered ADR tasks must not edit `README.md` |
| Correct any remaining “installs on import” prose in non-protected docs | Docs follow-ups | Runtime already opt-in |

---

## 11. Review checklist (authors)

- [x] Filename is `0001-imports-and-optional-dependencies.md` (not left as 0000)
- [x] Banner **Decision status** matches §3 **Status** (`Accepted`)
- [x] **Current behavior** is evidence-backed and separate from the proposal
- [x] No present-tense “the system does X” for Proposed-only intent (global degradation remains open)
- [x] Every material *why* uses **Accepted / Proposed / Inferred / Unknown**
- [x] No Inferred or Unknown claim is written as Accepted history
- [x] Evidence table prefers ranks 1–4 for Accepted claims
- [x] Alternatives include status quo and explicit rejects (eager import, silent install, global policies)
- [x] Confirmation owner and question filled for remaining Unknown (U-14 degradation matrix)
- [x] No secrets, live tokens, or host-specific credential paths
- [x] `docs/architecture/decisions/README.md` was **not** edited by this task
- [x] Related architecture guide can cite this ADR with status-honest language

---

## Appendix A — Verified constraints vs inferred intent (summary)

| Statement | Label | Use in docs |
|---|---|---|
| Import does not bulk-download binaries by default | **Verified / Accepted** | State as product constraint |
| `IPFS_KIT_AUTO_INSTALL_BINARIES` is required for package-managed Kubo install-on-import | **Verified / Accepted** | State as operator contract |
| Optional features use packaging extras + lazy/JIT/flags | **Verified / Accepted** | State as extension rule |
| Soft vs hard degradation is uniform product-wide | **Not verified** | Forbidden; describe per subsystem |
| Lazy design chosen “for performance” as historical fact | **Inferred only** | Label if used; do not present as accepted history |
| Universal AnyIO migration completed | **Not this ADR** | See ADR-0004 / U-14; do not claim here |

---

## Appendix B — Contributor quick rules

1. New optional pip dependency → add a **packaging extra** (or justify core).  
2. Gate use with **lazy import** + feature flag / `HAS_*`.  
3. Default import path stays **offline** (no network install side effects).  
4. Document **this subsystem’s** missing-extra behavior; do not invent a global policy.  
5. Tests: one path without the extra (skip/fallback), one with it when available.  
6. Binary install: explicit API/CLI or `IPFS_KIT_AUTO_INSTALL_BINARIES` only.
