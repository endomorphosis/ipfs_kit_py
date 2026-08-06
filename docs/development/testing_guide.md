# Testing and contribution guidance

- **Status**: Current contributor guidance (KDOC-039 / KDOC-G042)
- **Authority class**: Canonical (how to run and interpret tests)
- **Baseline**: Repository inspection of root `pytest.ini`, `pyproject.toml`,
  `tests/`, and selected GitHub workflows (2026-08-03)
- **Scope**: Default pytest discovery, known config mismatches, focused vs
  full vs integration vs e2e gates, optional extras/services, markers, offline
  expectations, failure triage, documentation duties, and evidence recording
- **Non-goals**: Changing pytest configuration; fixing broken suites;
  treating historical coverage or completion reports as live proof of health
- **Related**:
  [`docs/architecture/SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md),
  [`docs/guides/DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md),
  [`tests/README_TESTING.md`](../../tests/README_TESTING.md) (backend-focused
  deep dive), workflow files under `.github/workflows/`

This guide is the **contributor entry point** for testing. Prefer it over
dated banners under `docs/testing/` and over any claim that “the suite is
green” without naming the gate that was run.

---

## 1. What “default pytest” actually runs

Authoritative config when you run from the **repository root** is root
**`pytest.ini`** (not `config/pytest.ini` — see §3).

| Setting | Value | Meaning for contributors |
|---|---|---|
| `testpaths` | `tests` | Discovery starts under `tests/` |
| `python_files` / functions | `test_*.py` / `test_*` | Standard pytest naming |
| `pythonpath` | `.` | Repo root on path |
| `addopts` | `-q --strict-markers -ra --tb=short` | Quiet, strict markers, short TB |
| `norecursedirs` | `tests/integration` **and** `tests/archived_stale_tests` | Those trees are **not** collected by a plain `pytest` / `python -m pytest` |
| Markers | `integration`, `unit`, `slow`, `requires_network`, `timeout` | Registered; unknown markers fail |
| Async | `anyio_mode = auto`; `asyncio_default_fixture_loop_scope = function` | AnyIO-friendly; do not assume trio-only |
| `minversion` | `3.8` | **Stale relative to packaging** (see §3) |

### Explicit exclusions (read this first)

```ini
# From root pytest.ini — default discovery deliberately skips:
norecursedirs = tests/integration tests/archived_stale_tests
```

Consequences:

1. **`python -m pytest` does not prove** anything under `tests/integration/`.
2. **`tests/archived_stale_tests/` is historical** and excluded; do not treat
   it as a release gate or revive files without an explicit plan.
3. Many files **outside** `tests/integration/` still exercise integration-like
   behavior (for example `tests/test_vfs_mcp_integration.py`). Those **are**
   in default discovery unless you ignore or deselect them yourself.
4. Nested trees such as `tests/unit/`, `tests/performance/`, and much of
   `tests/test/` remain discoverable under `testpaths = tests` unless also
   excluded by name or path filters.

### Confirm what you will collect

```bash
# What default discovery would run (no execution)
python -m pytest --collect-only -q

# Prove integration tree is out of default recursion
python -m pytest --collect-only -q 2>&1 | rg 'tests/integration' || echo "integration not in default collect (expected)"

# Explicit opt-in collect for integration
python -m pytest tests/integration --collect-only -q
```

---

## 2. Test topology (how to choose a surface)

```
tests/
├── conftest.py                 # Root fixtures, path hygiene, daemon helpers
├── unit/                       # Prefer for fast, offline-friendly unit work
├── integration/                # EXCLUDED from default discovery (opt-in)
├── archived_stale_tests/       # EXCLUDED; historical / stale
├── e2e/                        # Browser / Playwright-style e2e (extra setup)
├── performance/                # Load / benchmark style tests
├── test/                       # Older nested layout; still under discovery
├── mocks/, fixtures/           # Shared helpers (not a gate by themselves)
└── test_*.py                   # Large default-discovery surface at suite root
```

| Surface | In default `pytest`? | Typical use | Offline? |
|---|---|---|---|
| `tests/unit/` | Yes | Fast, mocked unit behavior | Usually yes |
| Top-level `tests/test_*.py` | Yes (unless ignored) | Mixed unit / contract / light integration | Mixed |
| `tests/integration/` | **No** (`norecursedirs`) | External services, heavier MCP/backend stacks | Often no |
| `tests/archived_stale_tests/` | **No** | Archaeology only | N/A |
| `tests/e2e/` | Path-dependent; needs Playwright extras | UI / browser flows | No (browser stack) |
| `tests/performance/` | Yes if matched | Benchmarks / stress | Often local-only |

Backend-oriented layout and mock-mode notes live in
[`tests/README_TESTING.md`](../../tests/README_TESTING.md).

---

## 3. Python and config mismatches (explicit)

Do **not** assume every config file agrees. Treat the following as known drift
until a separate, authorized change reconciles them. **This guide does not
change configuration.**

| Source | Claim | Contributor action |
|---|---|---|
| `pyproject.toml` `[project]` | `requires-python = ">=3.12"`; classifiers **3.12** and **3.13** | **Authoritative runtime floor** for the package |
| `setup.py` | `python_requires='>=3.12'` | Aligns with packaging |
| Root `pytest.ini` | `minversion = 3.8` | Stale; still the active pytest file for markers/`norecursedirs`, but **do not** use it as a Python support promise |
| `config/pytest.ini` | Alternate markers, `testpaths = test tests`, no `norecursedirs` for integration | **Not** the default root config; do not run from assumptions based only on this file |
| `config/tox.ini` | `envlist = py38, py39, py310, py311, ...` and `pytest {posargs:test}` | Stale relative to `>=3.12` and `tests/` layout |
| CI (e.g. `.github/workflows/run-tests.yml`, `python-package.yml`) | Matrix **3.12** and **3.13** | Matches packaging intent for active workflows |
| `docs/testing/*` completion / coverage reports | Often dated campaign snapshots | **Historical**; never cite as live coverage proof |

**Practical rule:** develop and gate on **Python 3.12+** (prefer matching CI:
3.12 and 3.13). If a doc or secondary config mentions 3.8–3.11, treat that as
out of date unless packaging changes.

---

## 4. Install and environment

```bash
# Editable install with test tooling (recommended for contributors)
python -m pip install -e ".[dev]"

# Broader optional stacks when your change needs them (examples)
python -m pip install -e ".[dev,fsspec,arrow]"
python -m pip install -e ".[dev,iroh]"
python -m pip install -e ".[dev,api,webrtc]"   # heavier; only if needed
```

| Extra / surface | When you need it | Notes |
|---|---|---|
| `dev` | Almost all pytest work | pytest, pytest-cov, pytest-asyncio, pytest-trio, pytest-timeout, playwright packages listed |
| `iroh` | Iroh-focused tests / workflows | See `.github/workflows/iroh-ci.yml` |
| `fsspec`, `arrow` | Filesystem / Arrow tests | Optional at runtime |
| `api` | FastAPI/MCP HTTP surfaces | |
| `webrtc`, `ai_ml`, `ipfs_accelerate`, … | Specialty suites | Expect skips or import errors without extras |
| System binaries (ipfs, lotus, …) | Real-daemon integration | Opt-in; many tests skip or mock when absent |

Useful environment knobs (non-exhaustive; see `tests/conftest.py` and CLI docs):

| Variable | Role |
|---|---|
| `IPFS_PATH` / `IPFS_API_URL` | Point tests at a repo or API when daemons are involved |
| `IPFS_KIT_FAST_INIT` | Skip heavy init on some MCP/CLI paths (often set under pytest) |
| `IPFS_KIT_AUTO_INSTALL_BINARIES` | Binary auto-install (default off for doc/CI-safe paths) |
| `MCP_TEST_MOCK` | Used by some integration runners for mock mode |
| Backend mock flags (e.g. `SSHFS_MOCK_MODE`) | Backend unit suites; see `tests/README_TESTING.md` |

---

## 5. Gate matrix: fast → focused → full → integration → e2e

Choose the **narrowest authoritative gate** that covers your change. A green
default collect does **not** replace a workflow-specific or path-specific gate.

### 5.1 Fast (local smoke)

```bash
# Import / tiny surface
python -m pytest tests/unit/ -q --maxfail=5

# Or a single file you own
python -m pytest tests/test_vfs_contract_hardening.py -q
```

**Use when:** iterating on a single module; offline laptop work.

### 5.2 Focused (authoritative for a subsystem)

Prefer **named files or workflow command lines** over “run everything.”

| Concern | Example focused command | CI mirror |
|---|---|---|
| VFS contracts | `pytest tests/test_vfs_contract_hardening.py tests/test_datasets_metadata_index_contract.py tests/test_mcp_vfs_adapter_contract.py -q` | `.github/workflows/vfs-contract-gates.yml` |
| VFS + MCP tools | `pytest tests/test_vfs_jsonrpc.py tests/test_vfs_mcp_tools.py -q` | same workflow |
| VFS MCP integration (default-discovery file, not under `tests/integration/`) | `pytest tests/test_vfs_mcp_integration.py -q` | same workflow |
| Cluster unit-ish | `pytest tests/test_cluster_services.py -q` | `.github/workflows/cluster-tests.yml` |
| Cluster-related HTTP/VFS | `pytest tests/test_vfs_integration.py tests/test_http_api_integration.py -q` | cluster-tests.yml |
| Iroh packaging / install smoke | `pytest tests/test_iroh_compatibility_record.py tests/test_install_iroh.py -q` | `.github/workflows/iroh-ci.yml` |
| Iroh release readiness | `pytest tests/test_iroh_release_readiness.py -q` | iroh-ci.yml |
| CLI deprecations | `pytest tests/test_cli_deprecations_*.py -q` | local / package CI subsets |
| Deprecation / policy surfaces | Prefer the specific `tests/test_*deprecat*` or policy files you changed | — |

Architecture maps list subsystem-focused tests in
[`SOURCE_OF_TRUTH_MAP.md`](../architecture/SOURCE_OF_TRUTH_MAP.md). Prefer
**default-discovery** paths there for offline claims.

### 5.3 Full default discovery

```bash
# Makefile target → python -m pytest
make test

# Equivalent
python -m pytest

# With coverage (still subject to norecursedirs exclusions)
python -m pytest --cov=ipfs_kit_py --cov-report=term --cov-report=html
```

**Meaning:** exercises the large default surface under `tests/` **except**
`tests/integration/` and `tests/archived_stale_tests/`. CI’s
`.github/workflows/run-tests.yml` additionally **ignores** several known-broken
modules and may continue on failure — do not treat a noisy CI log as a
strict release certificate without reading the workflow.

### 5.4 Integration (`tests/integration/` opt-in)

```bash
# Entire integration tree (heavy; may need services, network, extras)
python -m pytest tests/integration -q

# Subtrees
python -m pytest tests/integration/backends -q
python -m pytest tests/integration/streaming -q

# Marker filter when tests are marked (not all are)
python -m pytest tests/integration -m integration -q

# Legacy helper (unittest-oriented MCP runner; opt-in mock mode)
python tests/run_integration_tests.py --mock
```

**Expectations:**

- Default offline PR review **should not** require this tree unless the change
  owns integration behavior.
- External services (IPFS daemon, S3, Filecoin, WebRTC, etc.) may force skips
  or failures; prefer mock modes when the suite supports them.
- Passing only presence/import checks inside integration helpers is not
  product accuracy proof.

### 5.5 End-to-end (`tests/e2e/`)

```bash
# Requires Playwright / browser stack from dev extras where applicable
python -m pytest tests/e2e -q
# Or follow package scripts if the e2e tree documents npm/Playwright steps
```

**Use when:** UI, dashboard, or browser contracts change. Not part of the
default offline gate.

---

## 6. Markers and selection

Registered in root `pytest.ini`:

| Marker | Intent |
|---|---|
| `unit` | Isolated unit behavior |
| `integration` | Needs broader stack or services (marker ≠ path; path `tests/integration/` is also excluded by recursion) |
| `slow` | Long-running; deselect for fast loops |
| `requires_network` | Needs network egress |
| `timeout` | Per-test timeout (pytest-timeout) |

```bash
python -m pytest -m "not slow and not requires_network" -q
python -m pytest -m "unit" tests/unit -q
python -m pytest -m "integration" tests/integration -q   # still need explicit path
```

`--strict-markers` means undeclared custom markers fail collection. Register
new markers in root `pytest.ini` (separate change from documentation).

Async tests: suite uses **AnyIO** (`anyio_mode = auto`). Prefer
`@pytest.mark.anyio` patterns already used in the tree; avoid hard-coding a
single backend unless the test is intentionally backend-specific.

---

## 7. Offline expectations

| Claim type | Offline-friendly evidence |
|---|---|
| Import / public export | Focused pytest or `python -c` import against installed package |
| CLI parser surface | Tests that build parsers without starting daemons |
| VFS / contract text | Contract tests listed in vfs-contract-gates |
| Architecture doc claim | Cite default-discovery tests + source paths (see documentation guide) |
| “Integration green” | Explicit path under `tests/integration/` plus service inventory — **not** default pytest |
| “Docs accurate” | Content/link/contract tests or manual evidence — **not** file-existence alone |

Avoid side-effectful imports in validation snippets (no auto-install of
binaries, no network) when documenting offline gates.

---

## 8. Documentation tests: presence is not accuracy

Contributors and agents often over-trust “documentation tests.” Distinguish:

| Kind | What it proves | What it does **not** prove |
|---|---|---|
| File exists / non-empty | Path present | Correct content, current APIs, or runnable examples |
| Heading or string contains | Phrase present | Behavioral correctness |
| `hasattr` / import smoke | Symbol importable | Semantics, CLI flags, or operator runbooks |
| Strong doc contract tests (example: `tests/test_iroh_operations_docs.py`) | Required headings, commands, local links for **that** contract | Unrelated docs elsewhere |
| Historical `docs/testing/*` “100% coverage” reports | Snapshot of a past campaign | Current coverage or suite health |

Examples of **weak** gates for accuracy claims:

- `test -s some.md && rg -q "keyword" some.md` (useful as a task validation
  string; **not** product proof)
- Suites that only print “✓ doc exists” style checks
- Completion banners in status reports

Examples of **stronger** doc-related evidence:

- Focused behavioral tests that assert the same contract the doc teaches
- Doc tests that walk required sections, forbid TODO/FIXME, and resolve local
  Markdown links (pattern used for Iroh operator docs)
- Manual or scripted example runs recorded as evidence (§10)

**Rule:** Never assume that presence-only documentation tests prove accuracy.
When a PR updates docs, either update a real focused gate or record explicit
manual verification commands and results.

---

## 9. Failure triage

1. **Collection errors** — missing optional extra, bad import path, or marker
   not registered. Install the relevant extra; fix imports; do not silence
   with broad ignores in docs.
2. **Skips** — often “daemon not available” or optional service. Distinguish
   skip (environment) from fail (regression).
3. **Failures only in `tests/integration/`** — confirm you opted in
   deliberately; check service/mock flags before filing product bugs.
4. **CI green but local red (or inverse)** — compare Python version (3.12+),
   root vs `config/pytest.ini`, and workflow `--ignore` lists in
   `run-tests.yml`.
5. **EBADF / teardown noise** — `tests/conftest.py` hardens some handler close
   races; re-run with `-q --tb=short` before deep-diving.
6. **PyArrow / MagicMock schema issues** — prefer shared fixtures; Python 3.12+
   schema objects are stricter than older notes in archived docs.
7. **Stale absolute claims** — if a failure is “test expects removed API,”
   update the test with the change; do not cite old coverage matrices as
   authority.

Debug aids:

```bash
python -m pytest path/to/test_file.py -vv -s --tb=long
python -m pytest path/to/test_file.py --pdb
python -m pytest --collect-only path/to/test_file.py -q
```

---

## 10. Contribution duties when you change code or docs

### Code change

1. Identify the **subsystem** (see architecture source map).
2. Run the **focused gate** for that subsystem (or add one if none exists —
   test code changes are separate from this guide).
3. Run a **fast** default or unit subset before broad full-suite waits.
4. If you touch integration-only behavior under `tests/integration/`, run that
   path **explicitly** and note services required.
5. Do not claim “all tests pass” without naming commands.

### Documentation change

1. Prefer claims backed by **source + focused tests** (documentation guide
   rank-1 evidence).
2. Update or add focused tests when docs assert behavior.
3. Do not rely on presence-only checks to close accuracy work.
4. Mark Historical material clearly; do not promote completion reports into
   current guidance (see freshness audit / historical register work).

### Evidence recording (PRs, tasks, agent runs)

Record enough for another contributor to reproduce offline when possible:

```text
Gate: VFS contract (focused)
Commands:
  python -m pytest tests/test_vfs_contract_hardening.py \
    tests/test_datasets_metadata_index_contract.py \
    tests/test_mcp_vfs_adapter_contract.py -q
Python: 3.12.x
Result: exit 0 (N passed, M skipped)
Not run: tests/integration (excluded by default; not in change scope)
```

For documentation-only edits:

```text
Gate: content contract / manual
Commands:
  rg -n 'expected heading|command' docs/path.md
  # or: python -m pytest tests/test_<doc_contract>.py -q
Limitation: presence checks only prove existence unless a contract test ran
```

---

## 11. Common contributor recipes

```bash
# 1) Default discovery (integration + archived excluded)
python -m pytest -q

# 2) Unit-only loop
python -m pytest tests/unit -q

# 3) Opt-in integration tree
python -m pytest tests/integration -q

# 4) One integration file without enabling whole tree recursion defaults
python -m pytest tests/integration/test_api.py -q

# 5) Deselect slow/network when markers are applied
python -m pytest -m "not slow and not requires_network" -q

# 6) Coverage on default discovery only
python -m pytest --cov=ipfs_kit_py --cov-report=term-missing -q

# 7) Match Makefile
make test
make coverage
```

---

## 12. What not to do

- Do **not** treat `tests/integration/` as covered by default pytest.
- Do **not** treat `tests/archived_stale_tests/` as a gate.
- Do **not** cite `pytest.ini` `minversion = 3.8` or `config/tox.ini` py38–py311
  as supported runtimes; packaging is **≥3.12**.
- Do **not** assume `config/pytest.ini` is active at repo root.
- Do **not** use presence-only documentation tests as accuracy proof.
- Do **not** cite `docs/testing/*` completion or “100% coverage” banners as
  current health.
- Do **not** change pytest configuration in a documentation-only task
  (conflict policy for this guide: document, do not reconfigure).

---

## 13. Related references

| Document / path | Role |
|---|---|
| Root `pytest.ini` | Default discovery, markers, `norecursedirs` |
| `pyproject.toml` | Python floor, extras, `[tool.pytest.ini_options]` subset |
| `tests/conftest.py` | Shared fixtures and path safety |
| `tests/README_TESTING.md` | Backend unit/integration deep dive |
| `.github/workflows/vfs-contract-gates.yml` | Authoritative VFS focused gate |
| `.github/workflows/iroh-ci.yml` | Iroh matrices and focused paths |
| `.github/workflows/cluster-tests.yml` | Cluster-oriented focused paths |
| `.github/workflows/run-tests.yml` | Broad CI with explicit ignores |
| `docs/architecture/SOURCE_OF_TRUTH_MAP.md` | Per-subsystem focused tests |
| `docs/guides/DOCUMENTATION_GUIDE.md` | Evidence ranks and doc duties |
| `docs/testing/*` | Mostly **historical** campaign reports — not this guide’s authority |

---

## 14. Quick decision chart

```
Change type?
├─ Pure unit / pure library logic
│    → tests/unit or owning test_*.py  (fast → focused)
├─ VFS / MCP adapter / metadata contract
│    → vfs-contract-gates file list
├─ Cluster / HTTP API around cluster
│    → cluster-tests.yml file list
├─ Iroh install / fsspec / release readiness
│    → iroh-ci.yml file list
├─ Docs only
│    → content/contract test if present; else recorded manual evidence
│       (never presence-only as accuracy)
└─ External service / multi-backend live stack
     → explicit: python -m pytest tests/integration ...
        (not implied by default pytest)
```

When in doubt, name the gate, the Python version, and whether
`tests/integration` was intentionally included. That is enough for another
contributor to trust or challenge your result without assuming silent full-suite
coverage or documentation presence tests.
