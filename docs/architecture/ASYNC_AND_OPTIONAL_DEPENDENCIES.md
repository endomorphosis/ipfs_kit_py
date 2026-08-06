# Async boundaries, lazy imports, and optional capabilities

| Field | Value |
|---|---|
| **Document class** | Canonical (architecture guide) |
| **Status** | active |
| **Task** | KDOC-018 |
| **Goal** | KDOC-G025 |
| **Track** | arch-trust |
| **Last verified** | 2026-08-03 |
| **Tree baseline** | `dc3456db07ffbfc8a7d7c0107dd56f0897d30fa4` |
| **Evidence** | [SOURCE_OF_TRUTH_MAP §8](./SOURCE_OF_TRUTH_MAP.md), [RUNTIME_AND_ENTRYPOINTS](./RUNTIME_AND_ENTRYPOINTS.md), [MCP_CONTROL_PLANE](./MCP_CONTROL_PLANE.md), [SYSTEM_OVERVIEW](./SYSTEM_OVERVIEW.md), [FRESHNESS F-009](../audits/FRESHNESS_AND_CHANGE_AUDIT.md), packaging `pyproject.toml`, `ipfs_kit_py/__init__.py`, `kubo_runtime.py`, `jit_imports.py`, `deps_resolver.py`, `mcp_server/server.py`, `mcp_server/core_operations.py`, `mcp_server/tools/iroh_tools.py`, dual `*_anyio.py` modules, focused tests listed in §11 |
| **Related** | Planned [CONFIGURATION_STATE_AND_TRUST.md](./CONFIGURATION_STATE_AND_TRUST.md); historical (non-authoritative) `docs/ANYIO_MIGRATION.md`, `docs/development/async_architecture.md` (stale API table — see §4); unresolved U-14 and map §8 decisions |

## 1. Scope and non-goals

### 1.1 Scope

This guide is the **authoritative architecture narrative** for:

1. **Supported sync / async / AnyIO / Trio boundaries** across packaged entry points and library surfaces.
2. **Valid AnyIO APIs** used (or recommended) in this repository, replacing invalid mappings that appear in older development notes.
3. **Thread offload, cancellation, and context** rules that keep process-owned event loops cooperative.
4. **Lazy imports, JIT feature gates, and packaging extras** — how optional capabilities load and degrade.
5. **No import-time download / binary install intent** — why ordinary `import ipfs_kit_py` must stay offline by default.

It answers: *which surface owns the event loop, which async stack is legal there, how sync kit code is reached without nesting loops, and what happens when an optional extra or binary is missing?*

### 1.2 Explicit non-goals

- **Not** a claim of universal AnyIO migration. Dual `foo.py` / `foo_anyio.py` modules and deliberate `asyncio.run` sites remain (**U-14**). Filename counts and historical migration reports do **not** prove completion.
- **Not** an ADR. End-state (deliberate dual stack vs ongoing migration), default library backend outside MCP++, and global stub-vs-fail-closed policy for missing extras remain **unresolved** (map §8).
- **Not** a full API inventory of every dual module.
- **Not** operator secrets, state-path, or daemon lifecycle deep-dives (owned by the planned configuration/trust guide and [RUNTIME_AND_ENTRYPOINTS](./RUNTIME_AND_ENTRYPOINTS.md)).
- **Not** event-loop nesting recipes (`nest_asyncio`, `run_until_complete` on a running loop, recursive `asyncio.run` inside the same loop). Those are **out of policy** — see §5.4.

### 1.3 How this guide relates to other docs

| Document | Relationship |
|---|---|
| [RUNTIME_AND_ENTRYPOINTS](./RUNTIME_AND_ENTRYPOINTS.md) | Per-entry process and loop ownership tables; this guide owns the **async/optional matrix** and API policy |
| [MCP_CONTROL_PLANE](./MCP_CONTROL_PLANE.md) | Records MCP++ **trio** choice (I-ASYNC); defers detailed policy here |
| [SYSTEM_OVERVIEW](./SYSTEM_OVERVIEW.md) | High-level process models; points here for the full async matrix |
| `docs/ANYIO_MIGRATION.md`, `docs/COMPLETE_ANYIO_MIGRATION_SUMMARY.md` | **Historical** campaign notes — useful archaeology, **not** product authority |
| `docs/development/async_architecture.md` | **Stale** replacement table (F-009); superseded for API truth by §4 of this guide |

---

## 2. Runtime models at a glance

```text
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Process / loop ownership                                             │
  ├──────────────────┬───────────────────┬───────────────────────────────┤
  │ Short-lived CLI  │ Long-lived MCP++  │ In-process library / fsspec   │
  │ ipfs-kit         │ ipfs-kit-mcp      │ import ipfs_kit_py            │
  │ anyio default    │ anyio + trio      │ Caller owns process + loop    │
  │ (typically aio)  │ Hypercorn trio    │ No new loop at import         │
  └────────┬─────────┴─────────┬─────────┴──────────────┬────────────────┘
           │                   │                        │
           ▼                   ▼                        ▼
     Domain ops          TOOL_GROUPS +            Sync kit / HLA /
     via anyio           core_operations          dual *_anyio modules
     handlers            to_thread → sync kit     on first use (JIT)
           │                   │
           └─────────┬─────────┘
                     ▼
           ┌─────────────────────┐     ┌──────────────────────────┐
           │ External daemons    │     │ Optional extras / bins   │
           │ Kubo / Iroh / Lotus │     │ fail-soft or fail-closed │
           │ separate OS procs   │     │ never forced at import   │
           └─────────────────────┘     └──────────────────────────┘
```

**Composition rules**

1. **One process, one loop owner.** Packaged CLIs and MCP++ create a loop for their lifetime; libraries never steal the caller’s loop at import time.
2. **Sync kit under async hosts runs in worker threads** (`anyio.to_thread.run_sync`), not by nesting a second event loop on the same thread.
3. **Backend is surface-specific.** MCP++ and `ipfs-kit-mcp-tools` pin **trio**. Operator `ipfs-kit` uses AnyIO’s **default** backend. Several Iroh CLIs use deliberate **`asyncio.run`**. Library callers inherit whatever they already run.
4. **Optional capability = packaging extra and/or feature flag**, not silent network install.
5. **Import is offline by default.** `_DOWNLOAD_BINARIES_AUTOMATICALLY = False`; `IPFS_KIT_AUTO_INSTALL_BINARIES` defaults off.

---

## 3. Supported sync / async boundary matrix

Statuses use the same vocabulary as the public surface matrix where applicable (`canonical`, `optional`, etc.). “Loop owner” is who creates and drives the event loop for that surface.

| Surface | Identity | Loop owner | Runtime stack | Sync / async boundary | Notes |
|---|---|---|---|---|---|
| Package import | `import ipfs_kit_py` | None (caller) | Sync import path | Sync only at import; heavy work deferred | JIT + lazy proxies; no binary download by default |
| Kit orchestrator | `ipfs_kit` / `get_ipfs_kit()` | Caller | Sync methods (typical) | Sync API; callers may wrap with threads if they own async | Daemon start is explicit opt-in |
| High-level API | `IPFSSimpleAPI` (package path) | Caller | Sync façade; some dual anyio helpers | Prefer sync methods from sync callers | Package may stub if legacy load fails (**C-HLA** / U-03) |
| Operator CLI | `ipfs-kit` → `cli:sync_main` | CLI process | **AnyIO** via `anyio.run(main)` (default backend) | Async handlers; blocking work via `anyio.to_thread.run_sync` where used | Short-lived process per command (except background MCP child) |
| MCP++ server | `ipfs-kit-mcp` → `mcp_server.server:main` | Server process | **AnyIO + trio** (`anyio.run(..., backend="trio")`) | Async tools; kit via `core_operations._call` → `to_thread.run_sync` | Hypercorn **trio** worker for HTTP; stdio / P2P same backend |
| MCP tools CLI | `ipfs-kit-mcp-tools` | Process per call | **AnyIO + trio** | `anyio.run(tm.dispatch, …, backend="trio")` | One-shot; exit on tool failure |
| FastMCP / JS SDK host | Host process | Host | Host-defined | Host must not assume kit-owned loop | Registry shared; runtime not kit-owned |
| Iroh install CLI | `ipfs-kit-iroh` | Process | **Sync** | Sync install lifecycle | Explicit binary management |
| Iroh ops / diagnostics / interop | `ipfs-kit-iroh-ops`, `-diagnostics`, `-interop` | Process | **`asyncio.run`** | Deliberate asyncio boundary | Do not re-enter with nested loops |
| Iroh manifest CLI | `ipfs-kit-iroh-manifest` | Process | Sync / asyncio (command-dependent) | See runtime guide entry tables | |
| fsspec `iroh` / `iroh+blob` | fsspec open | **Caller** process | Sync fsspec API (async helpers if any under dual modules) | Caller owns loop | Packaging entry points only for these protocols |
| Dual library modules | `foo.py` + `foo_anyio.py` (~46 files) | Caller | Sync and/or AnyIO twin | Import the twin that matches **your** stack | Not every domain has a twin; do not invent universality |
| External daemons | Kubo, managed Iroh, Lotus | Separate OS processes | N/A (native / own runtimes) | Kit managers start/stop/status only | Not co-scheduled on kit event loops |

### 3.1 Decision tree (choose a boundary)

```text
Are you writing a packaged entry point?
├─ Yes → use the stack already pinned for that entry (table above).
│        Do not switch MCP++ off trio without an ADR.
└─ No (library / app embed)
   ├─ Caller is sync only → use sync kit / HLA / sync dual modules.
   ├─ Caller is already on AnyIO (any backend) → prefer AnyIO APIs (§4);
   │    offload blocking kit calls with anyio.to_thread.run_sync.
   ├─ Caller is pure asyncio and you need an asyncio-native path →
   │    use deliberate asyncio surfaces (Iroh clients, dual modules that
   │    are asyncio-compatible on the asyncio backend) — do not nest loops.
   └─ Need MCP-style tools from async host → call async tool functions
        or run a dedicated MCP++ process; do not start a second loop in-thread.
```

### 3.2 What is **not** a supported boundary

| Anti-pattern | Why unsupported |
|---|---|
| `loop.run_until_complete(...)` while a loop is already running | Nested loop; breaks cancellation and backend neutrality |
| `asyncio.run(...)` **inside** an already-running asyncio loop | Runtime error / nested loop |
| `nest_asyncio` or similar patches | Paper over design bugs; not a product dependency or policy |
| Calling sync kit methods directly on the trio event-loop thread for long I/O | Blocks the MCP++ loop; use `to_thread.run_sync` |
| Assuming every `*_anyio.py` twin is complete and equivalent | Dual stack is partial; check imports and tests |
| Claiming “the codebase is fully AnyIO” from migration report filenames | Forbidden by KDOC-G025 / U-14 |

---

## 4. Valid AnyIO usage (replaces invalid examples)

### 4.1 Why a replacement section exists

The older development note `docs/development/async_architecture.md` maps several **asyncio** names onto **AnyIO APIs that do not exist**. Freshness audit **F-009** verified on an environment with AnyIO installed:

| Claimed AnyIO name | Actual |
|---|---|
| `anyio.gather` | **Missing** |
| `anyio.create_task` | **Missing** |
| `anyio.TimeoutError` | **Missing** (use built-in `TimeoutError`) |

That table must **not** be copied into new architecture or operator docs. This section is the replacement.

### 4.2 Correct mapping (asyncio → AnyIO)

Use this table for new code and for reviewing dual modules. Names reflect public AnyIO APIs present in the project dependency (`anyio>=3.7.0`).

| asyncio (conceptual) | AnyIO (correct) | Notes |
|---|---|---|
| `asyncio.sleep` | `anyio.sleep` | Backend-neutral |
| `asyncio.run` | `anyio.run` | Pass `backend="trio"` only when the surface requires trio (MCP++) |
| `asyncio.create_task` + `asyncio.gather` | `async with anyio.create_task_group() as tg:` + `tg.start_soon(...)` | Structured concurrency; no `anyio.gather` / `anyio.create_task` |
| `asyncio.wait_for(coro, timeout)` | `with anyio.fail_after(timeout):` or `with anyio.move_on_after(timeout):` | `fail_after` raises; `move_on_after` cancels quietly |
| `asyncio.TimeoutError` | built-in **`TimeoutError`** | Do not write `anyio.TimeoutError` |
| `asyncio.to_thread` / executors for blocking call | `await anyio.to_thread.run_sync(fn, ...)` | Preferred offload under AnyIO hosts |
| Call async from worker thread | `anyio.from_thread.run(...)` | Only when a loop already runs in another thread |
| Cancellation type check | `except anyio.get_cancelled_exc_class():` | Backend-correct cancelled exception |
| Current task introspection | `anyio.get_current_task()` | Exists; prefer task groups over ad-hoc task handles |

**There is no** `anyio.gather`, `anyio.create_task`, or `anyio.TimeoutError` in supported AnyIO versions used here. Code or docs that introduce them are incorrect.

### 4.3 Valid patterns (copy-safe examples)

#### Task group (replaces gather / create_task)

```python
import anyio

async def fetch_all(urls):
    results = []

    async def one(url):
        results.append(await fetch(url))

    async with anyio.create_task_group() as tg:
        for url in urls:
            tg.start_soon(one, url)
    return results
```

#### Timeouts

```python
import anyio

async def with_deadline(operation):
    try:
        with anyio.fail_after(5.0):
            return await operation()
    except TimeoutError:
        return {"status": "error", "error": "timeout"}
```

#### Blocking sync work under an AnyIO host (MCP++ / CLI)

```python
import functools
import anyio

async def call_sync_kit(method, **kwargs):
    fn = getattr(kit, method)
    return await anyio.to_thread.run_sync(functools.partial(fn, **kwargs))
```

This matches `ipfs_kit_py/mcp_server/core_operations.py`: the synchronous `ipfs_kit` orchestrator is never awaited as if it were async; it is offloaded so the trio loop stays cooperative.

#### Process entry (MCP++ trio pin)

```python
import anyio

def main():
    # Packaged MCP++ surfaces pin trio explicitly.
    anyio.run(serve_stdio, backend="trio")
```

Operator CLI uses `anyio.run(main)` **without** forcing trio (default backend).

### 4.4 Patterns that appear in-tree but are not “universal policy”

| Pattern | Where | Interpretation |
|---|---|---|
| `anyio.run(..., backend="trio")` | `mcp_server/server.py`, `mcp_server/cli.py` | **Required** for packaged MCP++ |
| `anyio.run(main)` default backend | `cli.py` (`sync_main`) | Operator CLI |
| `asyncio.run(...)` | Iroh CLIs (`iroh/cli.py`, diagnostics, multinode, …) | **Deliberate** asyncio boundary for those entries |
| `await anyio.to_thread.run_sync(lambda: asyncio.run(...))` | `mcp_server/tools/iroh_tools.py` | Isolates an asyncio-contract client **in a worker thread** with its **own** loop — not nested on the trio thread |
| Dual `*_anyio.py` modules | WAL telemetry, arc cache, cluster state, … | Optional twin; import explicitly; do not assume parity |

The Iroh diagnostics tool documents the isolation intent in-source: managed Iroh uses an asyncio transport contract while MCP++ runs on trio; the probe runs in a worker thread with a **fresh** `asyncio.run`, so each runtime keeps its own cancellation rules. That is **process-thread isolation**, not event-loop nesting.

---

## 5. Cancellation, context, and thread-offload matrix

### 5.1 Who cancels what

| Context | Cancellation primitive | Propagation expectation |
|---|---|---|
| AnyIO task group | Leaving `async with create_task_group` / cancel scope | Child tasks cancelled; exceptions grouped per AnyIO rules |
| Soft timeout | `anyio.move_on_after` | Work cancelled; control resumes without necessarily raising |
| Hard timeout | `anyio.fail_after` → `TimeoutError` | Caller handles timeout envelope |
| MCP++ tool dispatch | Request lifetime under server task group / transport | Tool should respect cancellation; kit work in threads may complete or be abandoned at thread boundary |
| Sync kit in `to_thread` | Thread offload; cancellation may not abort native blocking I/O instantly | Design long-running kit ops with timeouts at the kit/HTTP layer where possible |
| External daemon | OS process signals via managers | Independent of Python cancel scopes |

### 5.2 Thread offload rules

| Direction | API | When to use |
|---|---|---|
| Async → sync blocking | `await anyio.to_thread.run_sync(fn, *args)` | Kit methods, disk/network libs that block, CPU-heavy pure Python |
| Sync worker → async | `anyio.from_thread.run(async_fn, *args)` | Rare; only when a loop already owns the process and a worker must schedule async work |
| Never | `run_until_complete` on the running loop from async code | Nested loop |
| Never | Start trio and asyncio loops on the **same** thread | Cross-backend re-entrancy |

### 5.3 Context and backend constraints

- Code under MCP++ must remain **trio-compatible**: prefer AnyIO APIs; avoid asyncio-only objects (e.g. raw `asyncio.Lock`) on the hot path.
- Library dual modules that call `anyio.from_thread` / `to_thread` assume an AnyIO-managed loop is already running in the process when used from async entry points.
- pytest uses `anyio_mode = auto` (`pytest.ini`); tests marked `@pytest.mark.anyio` may run on available backends — do not hard-code trio-only assumptions in shared library tests unless the test is MCP++-specific.

### 5.4 Explicit non-advice: event-loop nesting

This repository’s architecture policy is:

1. **Do not nest event loops** on one thread.
2. **Do not recommend** `nest_asyncio`, patched `get_event_loop().run_until_complete`, or “run async from sync mid-request” hacks.
3. **Do** choose one of the supported boundaries in §3:
   - stay sync;
   - offload blocking work with `to_thread.run_sync`;
   - isolate a foreign async stack in a **worker thread** with its own `asyncio.run` (Iroh tool pattern) or a **child process**;
   - or call into a long-lived server that already owns the correct backend.

Historical demos under `scripts/dev/` that discuss nested-loop “fixes” are **not** architecture authority.

---

## 6. Lazy imports and JIT feature gates

### 6.1 Intent

Ordinary package import must stay **fast and side-effect-light**:

- Heavy scientific / ML / installer stacks load **on first use**.
- Missing optional modules degrade through feature checks and decorators rather than crashing every import.
- CLI, daemon, and MCP paths share the same JIT/cache concepts where wired (`jit_imports.py`, `core` JIT manager, `deps_resolver.py`).

### 6.2 Mechanisms

| Mechanism | Path | Role |
|---|---|---|
| Core JIT manager | `ipfs_kit_py.core` (`jit_manager`, `require_feature`, `optional_feature`) | Feature checks and on-demand module load; mock fallbacks if core unavailable |
| Central JIT registry | `ipfs_kit_py/jit_imports.py` | Feature definitions, module/pip package lists, metrics, caches |
| Dependency resolver | `ipfs_kit_py/deps_resolver.py` | `resolve_module`, injection + cache helpers for optional pip modules |
| Package lazy proxies | `ipfs_kit_py/__init__.py` | Deferred getters for kits, installers, HLA-related symbols |
| Try/except import flags | Widespread `HAS_*` / `*_AVAILABLE` / `HAVE_*` | Module-local capability bits (Arrow, libp2p, HuggingFace, …) |

Illustrative usage (matches package docstring patterns):

```python
from ipfs_kit_py.core import jit_manager, require_feature, optional_feature

if jit_manager.check_feature("enhanced_features"):
    mod = jit_manager.get_module("enhanced_pin_index")

@require_feature("daemon")
def start_daemon():
    ...

@optional_feature("analytics", fallback_result={})
def get_analytics():
    return complex_analytics()
```

### 6.3 Capability detection vs degradation

| Detection style | Typical behavior when missing | Examples |
|---|---|---|
| **`optional_feature` / soft flag** | Return fallback or no-op; continue | Analytics, some installer hooks |
| **`require_feature` / hard gate** | Skip or error at call site when feature absent | Daemon-gated operations |
| **Module-level `try/except ImportError`** | Set `HAS_X = False`; later branches disable feature | `ARROW_AVAILABLE`, `HAS_LIBP2P`, `HUGGINGFACE_HUB_AVAILABLE` |
| **Stub object** | Provide deterministic fake results for tests / offline | MCP `_StubKit` when kit/daemon unavailable |
| **Fail-closed** | Error envelope; no fake success | MCP++ receipt integrity paths (control-plane docs); not universal for all extras |

**Unresolved (map §8 #3):** There is no single product-wide “always stub” or “always fail-closed” rule for every optional extra. Document subsystem behavior; do not invent a global policy.

### 6.4 Dual module pattern (`foo` / `foo_anyio`)

Approximately **46** `*_anyio.py` modules exist under `ipfs_kit_py/` (WAL telemetry family, caches, cluster state, peer websocket, high_level_api helpers, legacy `mcp/server_anyio.py`, etc.).

| Rule | Guidance |
|---|---|
| Prefer explicit imports | `from ipfs_kit_py.arc_cache_anyio import ...` when you need the AnyIO twin |
| Do not equate filename with readiness | Presence of `*_anyio.py` ≠ full feature parity or universal migration |
| Sync callers stay on sync modules | Avoid pulling AnyIO twins into pure sync scripts without need |
| Tests | Prefer focused tests (`tests/test_anyio_migration.py`, subsystem async tests) over migration summary markdown |

---

## 7. Optional packaging extras and degraded capabilities

### 7.1 Declared extras

Extras live under `[project.optional-dependencies]` in `pyproject.toml`. Install examples:

```bash
pip install -e ".[iroh]"
pip install -e ".[fsspec,libp2p,arrow]"
pip install -e ".[dev]"   # test/tooling stack
```

Representative extras (not exhaustive of every transitive pin):

| Extra | Primary capability | Degraded behavior when absent (typical) |
|---|---|---|
| `iroh` | BLAKE3 / DuckDB-related Iroh support surface | Iroh-backed paths unavailable; install/ops CLIs may still manage binary lifecycle |
| `fsspec` | fsspec + unix socket helpers | `iroh://` filesystem usage requires the extra + entry points |
| `libp2p` | Optional peer stack (`py-libp2p@main` tracking) | `HAS_LIBP2P` / `HAVE_LIBP2P` false; P2P features fail-soft |
| `arrow` | PyArrow / pandas analytics indexes | Arrow indexes disabled via `ARROW_AVAILABLE`-style flags |
| `api` | FastAPI / Uvicorn | HTTP API modules not importable |
| `ai_ml`, `transformers`, `huggingface` | ML / HF stacks | Integrations skip or raise at first use |
| `ipfs_accelerate`, `ipfs_datasets` | Heavy sibling projects | Optional integrations stay unloaded |
| `ipld`, `ipld-github`, `car_files`, `enhanced_ipfs` | IPLD/CAR codecs | Codec paths unavailable |
| `webrtc`, `graphql`, `s3`, `saturn`, `ipni`, `filecoin_pin`, `performance`, `full`, `dev` | Specialized or meta extras | Feature-off at import or first use |

**Core runtime deps** already include `anyio` and `trio` in the base project dependencies — MCP++ trio is not gated behind an optional extra.

### 7.2 Optional binary / service capabilities (not pip extras)

| Capability | Default | Opt-in | Notes |
|---|---|---|---|
| Package-managed Kubo binary ensure/install | **Off** | `IPFS_KIT_AUTO_INSTALL_BINARIES=1` (truthy) | `kubo_runtime.ensure_kubo_binary`; see §8 |
| Kubo / Lotus / Lassie / Storacha bulk `download_binaries()` | **Off** | Explicit call or legacy `_DOWNLOAD_BINARIES_AUTOMATICALLY` (hard-coded **False**) | Must not run on ordinary import |
| Managed Iroh binary | Explicit CLI / installer | `ipfs-kit-iroh` and related | Separate from Kubo env flag |
| External daemons running | Not started solely by import | CLI services / managers / explicit kit flags | MCP++ `get_kit` uses `auto_start_daemons=False` |

### 7.3 Diagnosing missing capabilities

```text
1. Confirm packaging extra: pip show / try import the optional module.
2. Check feature flags: HAS_*, *_AVAILABLE, jit_manager.check_feature(...).
3. For binaries: which ipfs; IPFS_KIT_BIN_DIR; never assume auto-download.
4. For MCP tools: tool error envelope / stub kit vs live daemon.
5. Prefer focused tests under tests/ over historical COMPLETE_* reports.
```

---

## 8. No import-time download intent

### 8.1 Policy statement

**Ordinary package import must not download, install, or upgrade executables or pull large dependency installers over the network.** Binary and heavy installer work is **explicit opt-in**.

Rationale:

- CI, air-gapped hosts, and read-only agent environments must be able to `import ipfs_kit_py` safely.
- Surprise network access on import breaks supply-chain review and reproducibility.
- Installers are powerful (write under `bin/`, mutate `PATH`); they require operator intent.

### 8.2 Implementation anchors

| Control | Location | Default behavior |
|---|---|---|
| `_DOWNLOAD_BINARIES_AUTOMATICALLY` | `ipfs_kit_py/__init__.py` | **`False`** — import-time bulk download block does not run |
| `download_binaries()` | same | Available as an explicit function; JIT-loads installers only when called |
| `IPFS_KIT_AUTO_INSTALL_BINARIES` | env; read in `__init__.py` and `kubo_runtime.py` | Falsy → do **not** call `ensure_kubo_binary(install=True)`; may still resolve an already-present managed binary |
| Daemon config auto-install helpers | `daemon_config_manager` paths covered by tests | Attempt install only when env opt-in is set |
| Package docstring | `__init__.py` module doc | Documents opt-in and offline import intent |

Truth table for Kubo ensure-on-import:

| `IPFS_KIT_AUTO_INSTALL_BINARIES` | Behavior |
|---|---|
| unset / `0` / empty / other non-truthy | No install; `KUBO_BINARY` set only if a managed binary already exists and is executable |
| `1` / `true` / `yes` / `on` | `ensure_kubo_binary(install=True)` may download/install |

Focused tests: `tests/test_auto_install_binaries.py`, related Lotus install tests, Iroh packaging tests that force `IPFS_KIT_AUTO_INSTALL_BINARIES=0`.

### 8.3 What “import-safe” does **not** guarantee

- Import may still touch local filesystem for package resources and may probe paths.
- First **use** of a feature may import heavy optional Python modules (still no binary download unless that feature’s code path explicitly installs).
- Historical or compatibility entry points outside packaging may differ; prefer packaged scripts and documented library APIs.
- Docstring “Quick Start” fragments that show installers are **usage** examples, not import side effects — call installers explicitly.

### 8.4 Operator checklist

```bash
# Safe default for CI / agents
unset IPFS_KIT_AUTO_INSTALL_BINARIES   # or export IPFS_KIT_AUTO_INSTALL_BINARIES=0

# Explicit opt-in only when you intend package-managed Kubo setup
export IPFS_KIT_AUTO_INSTALL_BINARIES=1

# Prefer explicit installers / CLIs over ambient import magic
ipfs-kit-iroh --help
python -c "from ipfs_kit_py import download_binaries  # call only if you mean it"
```

---

## 9. Entry-point runtime / offload summary

| Entry / surface | Backend | Cancellation / context | Thread offload | Optional degradation |
|---|---|---|---|---|
| `import ipfs_kit_py` | None | N/A | N/A | Missing extras → lazy failure at use |
| `ipfs-kit` | AnyIO default | Command-scoped tasks | Used for some blocking ops | Optional CLI mounts skipped |
| `ipfs-kit-mcp` | **trio** | Server-scoped AnyIO tasks; Hypercorn trio | **Required** for sync kit (`core_operations`) | Stub kit / tool errors; process stays up |
| `ipfs-kit-mcp-tools` | **trio** | Single dispatch | Via same tool stack | Exit non-zero on failure |
| Iroh asyncio CLIs | asyncio | Process-scoped `asyncio.run` | Internal to those modules | Structured error envelopes |
| fsspec Iroh | Caller | Caller | Caller | Call-time errors if extra/backend missing |
| Dual `*_anyio` libs | Caller AnyIO | Caller cancel scopes | Module-specific `to_thread` / task groups | ImportError or feature flags |

---

## 10. Unresolved decisions (do not paper over)

Recorded for ADR / maintainer follow-up (map §8, U-14):

1. **AnyIO end-state** — deliberate long-term dual stack vs continued migration. This guide describes **current** mixed reality only.
2. **Default async backend for library callers** outside MCP++ (asyncio vs trio).
3. **Global stub vs fail-closed policy** when optional extras are missing (today: per-subsystem).
4. **HLA package vs large-module authority** (C-HLA / U-03) — affects which async helpers are “the” high-level path.

Until ADRs accept otherwise, architecture prose must not claim a single async stack or universal optional-dependency policy.

---

## 11. Evidence and focused tests

### 11.1 Primary source anchors

```bash
# MCP++ trio pin and transports
rg -n 'anyio\.run|backend=.trio.|hypercorn' ipfs_kit_py/mcp_server/server.py ipfs_kit_py/mcp_server/cli.py

# Sync kit offload under AnyIO
rg -n 'to_thread\.run_sync' ipfs_kit_py/mcp_server/core_operations.py

# Iroh asyncio isolation under trio MCP++
rg -n 'asyncio\.run' ipfs_kit_py/mcp_server/tools/iroh_tools.py

# No import-time download controls
rg -n '_DOWNLOAD_BINARIES_AUTOMATICALLY|IPFS_KIT_AUTO_INSTALL_BINARIES' \
  ipfs_kit_py/__init__.py ipfs_kit_py/kubo_runtime.py

# Dual modules
find ipfs_kit_py -name '*_anyio.py' | wc -l

# Invalid API absence (smoke)
python -c "import anyio; assert not hasattr(anyio,'gather'); assert not hasattr(anyio,'create_task')"
```

### 11.2 Tests and config

| Area | Paths |
|---|---|
| AnyIO migration / async smoke | `tests/test_anyio_migration.py`, `tests/test_iroh_fsspec_async.py` |
| Import safety / paths | `tests/test_ipfs_kit_import.py`, `tests/test_import_paths_validation.py`, `tests/test_cli_import_verification.py` |
| Optional dependencies | `tests/integration/test_optional_dependencies.py` |
| Auto-install opt-in | `tests/test_auto_install_binaries.py`, `tests/test_lotus_daemon_auto_install.py` |
| Packaging extras | `tests/test_iroh_packaging.py` (and related packaging tests) |
| pytest AnyIO mode | `pytest.ini` → `anyio_mode = auto` |

### 11.3 Historical docs (non-authoritative)

- `docs/ANYIO_MIGRATION.md`, `docs/COMPLETE_ANYIO_MIGRATION_SUMMARY.md`, `docs/migration/ANYIO_*`
- `docs/development/async_architecture.md` — **do not trust** its Direct Replacements table (F-009); use §4 here instead
- Bulk refactor tool `tools/asyncio_to_anyio_bulk_refactor.py` — historical aid only

---

## 12. Practical checklists

### 12.1 Adding async code

1. Identify the **surface** (§3). Inherit its backend; do not invent a second loop.
2. Use **valid AnyIO APIs** only (§4.2). Prefer task groups and `fail_after` / `move_on_after`.
3. Offload blocking kit or disk work with **`anyio.to_thread.run_sync`**.
4. Handle cancellation via **`anyio.get_cancelled_exc_class()`** when catching cancel failures.
5. Add or extend a **focused test**; do not update historical COMPLETE reports as proof.

### 12.2 Adding an optional capability

1. Prefer a **packaging extra** when new third-party deps are required.
2. Gate with **lazy import** + feature flag; keep default import offline.
3. Document degraded behavior (skip / stub / error) at the call site — do not assume global policy.
4. Never download binaries from import side effects; use env opt-in or explicit installer APIs (§8).

### 12.3 Reviewing docs and PRs

| Check | Pass criterion |
|---|---|
| AnyIO examples | No `anyio.gather` / `anyio.create_task` / `anyio.TimeoutError` |
| Nesting | No nest_asyncio or run_until_complete-on-running-loop guidance |
| Migration claims | No “100% AnyIO” without subsystem evidence |
| Import safety | Import path does not require network or auto-install |
| MCP++ backend | trio remains the packaged server/tools CLI backend |

---

## 13. Summary

| Topic | Architecture position |
|---|---|
| **AnyIO** | First-class for CLI and many library twins; **required with trio** for packaged MCP++ |
| **asyncio** | Deliberate on several Iroh CLIs and isolated tool bridges — not deprecated by filename |
| **Sync kit** | Still primary orchestrator; async hosts reach it via **thread offload** |
| **Invalid examples** | Superseded by §4; F-009 stale table must not be re-copied |
| **Nesting** | Unsupported; isolate foreign runtimes in threads/processes instead |
| **Lazy imports** | JIT + flags keep import light; capabilities degrade per subsystem |
| **Optional extras** | Declared in `pyproject.toml`; missing extras fail soft or closed by feature |
| **Binaries** | **No import-time download** by default; `IPFS_KIT_AUTO_INSTALL_BINARIES` is explicit opt-in |

This guide is the KDOC-018 deliverable for async boundaries, lazy imports, and optional capabilities. Link subsystem guides here for policy; keep historical migration notes out of the recommendation path.
`)