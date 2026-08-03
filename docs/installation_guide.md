# Installation Guide

| Field | Value |
|---|---|
| Document class | **Canonical** current-user guide |
| Task | KDOC-030 — Refresh installation and quick-reference paths |
| Goal | KDOC-G041 |
| Packaging baseline | `pyproject.toml` version **0.3.0**, `requires-python = ">=3.12"` |
| Last verified | 2026-08-03 (static/offline against this tree) |
| Related | [`QUICK_REFERENCE.md`](QUICK_REFERENCE.md), [`architecture/RUNTIME_AND_ENTRYPOINTS.md`](architecture/RUNTIME_AND_ENTRYPOINTS.md), [`architecture/CONFIGURATION_STATE_AND_TRUST.md`](architecture/CONFIGURATION_STATE_AND_TRUST.md), [`audits/PUBLIC_SURFACE_MATRIX.md`](audits/PUBLIC_SURFACE_MATRIX.md) |

This guide covers installing **ipfs_kit_py**, verifying a first success without
surprise network side effects, optional daemon binaries, and choosing a public
interface. Commands and imports below were checked against packaging metadata
and importable surfaces on this tree.

---

## 1. Supported Python and version notes

### 1.1 Python runtime (required)

| Requirement | Authority |
|---|---|
| **Python 3.12 or newer** | `pyproject.toml` `requires-python = ">=3.12"` |
| Classifiers list **Python 3.12** and **Python 3.13** | `pyproject.toml` `Programming Language :: Python :: 3.12` / `3.13` |
| Tooling targets `py312` / `py313` | `tool.black` / `tool.ruff` / `tool.isort` |

**Ambiguity (do not paper over):**

| Signal | Value | Treat as |
|---|---|---|
| Packaging / release metadata | `0.3.0` | **Canonical** product version for installs and release notes |
| `ipfs_kit_py.__version__` | `0.2.0` | **Unresolved drift** vs packaging (conflict **C-VER**). Prefer packaging version for “what did I install?” |
| Non-packaged `src/__init__.py` | `3.0.0` | **Not distributed** — outside setuptools package discovery |
| Root `package.json` | `0.1.0` | Playwright harness only — **not** the Python package version |
| `pytest.ini` `minversion` | lower historical floor | **Not** the supported runtime; packaging floor wins |

```bash
python --version   # must report 3.12.x or 3.13.x (or newer when classifiers expand)
```

Python 3.11 and older are **unsupported** for this package as packaged today.

### 1.2 Platforms

Packaging classifies **Linux** and **macOS**. Windows is not advertised as a
primary platform for full daemon/binary workflows; library-only use may still
work where pure-Python dependencies resolve.

---

## 2. What a default install does **not** do

**Binary downloads are opt-in.** A normal package install or import must not
fetch Kubo, Lotus, Iroh, or other daemon binaries unless you explicitly enable
auto-install or run an installer API/CLI.

| Mechanism | Default | Downloads binaries? |
|---|---|---|
| `pip install ipfs_kit_py` / `pip install -e .` | Auto-install env unset/falsy | **No** (setup hook only runs when `IPFS_KIT_AUTO_INSTALL_BINARIES` is truthy) |
| `import ipfs_kit_py` | `_DOWNLOAD_BINARIES_AUTOMATICALLY = False` | **No** |
| `IPFS_KIT_AUTO_INSTALL_BINARIES=1` during setup/import | Opt-in | **Yes** (Kubo/Lotus/Iroh attempts; fail-soft with warnings) |
| Explicit installer call / `ipfs-kit-iroh install` | Caller-initiated | **Yes** (by design) |

Recommended for CI, docs validation, and air-gapped first installs:

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
```

There is **no** packaging console script named `ipfs-kit-install`. Use the
Python installers or the packaged Iroh CLI (see [§6](#6-optional-daemon-binaries-opt-in)).

---

## 3. Prerequisites

### 3.1 Always required

* **Python 3.12+** with `pip` (and preferably a virtual environment)
* Network access **only** for resolving Python packages from your index (PyPI or private mirror)
* Disk for the virtualenv and package tree

### 3.2 Optional (feature-dependent)

| Need | When |
|---|---|
| Local **Kubo** (`ipfs`) daemon | Add/get/pin against a local node; many HLA paths talk to the API |
| **IPFS Cluster** binaries | Cluster pin/replication operator workflows |
| **Iroh** managed sidecar | Iroh backend / `ipfs-kit-iroh*` tooling |
| **Lotus** | Filecoin features |
| Extra Python deps (`[api]`, `[ai_ml]`, `[fsspec]`, …) | Matching optional features |
| Docker / Kubernetes | Container deployment guides under `docs/deployment/` |

### 3.3 State paths (do not conflate)

| Path | Role |
|---|---|
| `~/.ipfs_kit` | Kit state root (config, MCP PIDs/logs, backends) — override with CLI `--data-dir` / operator env where wired |
| `~/.ipfs` (`IPFS_PATH`) | **Kubo** repository — separate from kit state |
| `IPFS_KIT_BIN_DIR` or managed bin dir | Optional managed daemon binaries |

---

## 4. Install the Python package

Prefer a virtual environment.

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
```

### 4.1 From this repository (development / source)

Canonical for contributors working on this tree:

```bash
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py

# Ensure auto binary install stays off unless you want it
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

# Editable install — core dependencies from pyproject.toml
pip install -e .

# Common optional sets (choose what you need)
pip install -e ".[dev]"      # tests, linters, build tools
pip install -e ".[api]"      # FastAPI / uvicorn MCP HTTP stack helpers
pip install -e ".[fsspec]"   # filesystem protocol helpers
pip install -e ".[ai_ml]"    # torch / numpy / sklearn / faiss-cpu stack
pip install -e ".[full]"     # large umbrella extra (heavy; may pull VCS deps such as py-libp2p)
```

**Notes on `requirements.txt`:** the repo-root `requirements.txt` is a **broad
developer pin set** (core + many optional stacks + pytest). Prefer
`pip install -e .` plus selective extras for reproducible product installs.
Use `requirements.txt` only when you intentionally want that wider lock-like set.

### 4.2 From a package index (library consumers)

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0
pip install "ipfs_kit_py>=0.3.0"
# or with extras, e.g.:
pip install "ipfs_kit_py[api]"
pip install "ipfs_kit_py[fsspec]"
pip install "ipfs_kit_py[ai_ml]"
pip install "ipfs_kit_py[full]"
```

If your index lags packaging version, install from a git tag or this checkout
with `pip install -e .` as above.

### 4.3 Optional extras (packaging inventory)

Declared under `[project.optional-dependencies]` in `pyproject.toml`. Install
only what you use:

| Extra | Purpose (summary) |
|---|---|
| `api` | FastAPI, uvicorn, multipart, jinja2 |
| `fsspec` | fsspec + unix socket requests |
| `arrow` | pyarrow, pandas |
| `ai_ml` | torch, numpy, scikit-learn, faiss-cpu, mmh3 |
| `libp2p` | py-libp2p (VCS) + crypto stack |
| `iroh` | blake3, duckdb helpers for Iroh paths |
| `webrtc` | aiortc / av / opencv media stack |
| `s3` | boto3 |
| `ipld` / `ipld-github` | CAR/DAG-PB codecs; GitHub-only unixfs on `ipld-github` |
| `ipfs_datasets` / `ipfs_accelerate` | Large external integration stacks |
| `transformers` / `huggingface` | HF model hub tooling |
| `dev` | pytest, coverage, black, mypy, playwright, … |
| `full` | Broad umbrella of common optional deps (still not every extra) |

Extras such as `libp2p`, `ipld-github`, and `ipfs_accelerate` may require **git**
or additional system libraries. They are never implied by a bare core install.

### 4.4 Packaged console scripts

After a successful install, these entry points are available (from
`[project.scripts]`):

| Script | Target | Role |
|---|---|---|
| `ipfs-kit` | `ipfs_kit_py.cli:sync_main` | Operator CLI (MCP dashboard control, services, unified domain commands) |
| `ipfs-kit-mcp` | `ipfs_kit_py.mcp_server.server:main` | MCP++ JSON-RPC server (stdio / HTTP / P2P) |
| `ipfs-kit-mcp-tools` | `ipfs_kit_py.mcp_server.cli:main` | One-shot tool CLI over the same registry |
| `ipfs-kit-iroh` | `ipfs_kit_py.iroh_install_cli:main` | Managed Iroh binary lifecycle (**downloads when you run `install`**) |
| `ipfs-kit-iroh-ops` | `ipfs_kit_py.iroh.cli:main` | Iroh service operations |
| `ipfs-kit-iroh-diagnostics` | `ipfs_kit_py.iroh.diagnostics_cli:main` | Iroh diagnostics dump |
| `ipfs-kit-iroh-manifest` | `ipfs_kit_py.iroh.manifest_cli:main` | Manifest migrate / recover |
| `ipfs-kit-iroh-interop` | `ipfs_kit_py.iroh.multinode:main` | Opt-in multi-node interop harness |

Equivalent module forms work without relying on PATH scripts:

```bash
python -m ipfs_kit_py.cli --help
```

---

## 5. Safe first-success checks (offline / no daemon)

These checks verify the **Python package** without starting daemons or
downloading binaries.

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

# 1) Import package root
python -c "import ipfs_kit_py; print('import_ok', getattr(ipfs_kit_py, '__version__', None))"

# 2) High-level API surface (lazy; construction may not need a live daemon)
python -c "from ipfs_kit_py.high_level_api import IPFSSimpleAPI; print('hla_ok', IPFSSimpleAPI)"

# 3) CLI module import (does not start services)
python -c "from ipfs_kit_py.cli import sync_main; print('cli_ok', callable(sync_main))"

# 4) Console script help (after pip install -e .)
ipfs-kit --help
```

**Version reporting tip:** packaging metadata is authoritative for release
identity:

```bash
python -c "from importlib.metadata import version; print(version('ipfs_kit_py'))"
```

`ipfs_kit_py.__version__` may still print `0.2.0` until that drift is resolved.

### 5.1 Optional: live daemon smoke (requires Kubo)

Only after you have a reachable IPFS API (default `127.0.0.1:5001`):

```bash
# If Kubo is already installed and configured on PATH:
ipfs daemon   # separate terminal

python - <<'PY'
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()  # accepts config_path= and **kwargs overrides (e.g. role=)
result = api.add(b"hello from ipfs_kit_py install check")
print(result)  # expect dict with success/cid fields when daemon is healthy
PY
```

If no daemon is running, expect connection-oriented failures from methods that
call the API — that does **not** mean the library install failed.

---

## 6. Optional daemon binaries (opt-in)

Use these only when you need local daemons. **Each path downloads or mutates
binaries when invoked.**

### 6.1 Policy environment variables

| Variable | Default | Effect |
|---|---|---|
| `IPFS_KIT_AUTO_INSTALL_BINARIES` | off / falsy | When truthy, setup/import hooks may attempt Kubo/Lotus/Iroh install |
| `IPFS_KIT_BIN_DIR` | platform/package default | Directory for managed binaries |
| `IPFS_PATH` | `~/.ipfs` | Kubo repository location |
| `IPFS_KIT_SKIP_LOTUS_CHECK` | unset | Skip Debian package preflight for Lotus deps in `setup.py` |
| `IPFS_KIT_AUTO_UPGRADE_KUBO` | on **when** managed install path runs | Kubo upgrade behavior during install |

### 6.2 Kubo / cluster via Python installer (explicit)

There is no `ipfs-kit-install` console script. Use the library installer:

```python
# WARNING: downloads Kubo (and related) artifacts when methods run
from ipfs_kit_py import install_ipfs

installer = install_ipfs(metadata={"bin_dir": "/path/to/bin"})  # optional bin_dir
installer.install_ipfs_daemon()
# Optional cluster components (separate downloads):
# installer.install_ipfs_cluster_service()
# installer.install_ipfs_cluster_ctl()
# installer.install_ipfs_cluster_follow()
```

Repo-root `install_ipfs.py` is a thin wrapper around the same package module.

After binaries exist:

```bash
ipfs init          # once per repo if not already initialized
ipfs daemon        # long-running process
ipfs --version
```

### 6.3 Iroh managed install (packaged CLI)

```bash
# Describes / installs the managed Iroh sidecar — install command downloads
ipfs-kit-iroh install --dry-run    # no mutation
ipfs-kit-iroh install              # downloads when not dry-run
ipfs-kit-iroh inspect --check
ipfs-kit-iroh update --dry-run
ipfs-kit-iroh rollback --dry-run
```

### 6.4 Manual OS packages / dist.ipfs.tech

You may install Kubo and IPFS Cluster from official distribution channels and
put them on `PATH`. The kit will use existing binaries when present; it does
not require package-managed copies.

### 6.5 Auto-install during `pip` (discouraged for most users)

```bash
# Explicit opt-in only — undeclared if omitted from your runbook
export IPFS_KIT_AUTO_INSTALL_BINARIES=1
export IPFS_KIT_BIN_DIR="$HOME/.local/share/ipfs_kit_py/bin"
pip install -e .
```

Leave this **unset** or `0` unless you intentionally want setup-time downloads.

---

## 7. Choose an interface after install

| Interface | How to start / import | Needs daemon? | Notes |
|---|---|---|---|
| **High-level Python API** | `from ipfs_kit_py.high_level_api import IPFSSimpleAPI` | For content ops: usually yes (local or remote API) | Preferred library surface for add/get/pin/IPNS/cluster helpers |
| **Package root lazy proxies** | `from ipfs_kit_py import IPFSSimpleAPI` | Same | Root `__all__` is P2P/JIT-centric; popular names are lazy proxies not listed in `__all__` |
| **Operator CLI** | `ipfs-kit …` or `python -m ipfs_kit_py.cli …` | Depends on subcommand | `mcp`, `daemon`, `services`, `autoheal`, plus unified `bucket` / `vfs` / `wal` / `pin` / `backend` / `journal` / `state` |
| **MCP++ server** | `ipfs-kit-mcp` (default transport stdio) | Tools often need live IPFS/Iroh | Canonical packaged MCP entry |
| **MCP tools one-shot** | `ipfs-kit-mcp-tools …` | Per tool | Same registry as MCP++ |
| **Dashboard MCP path** | `ipfs-kit mcp start` | Dashboard stack | Compatibility/legacy dashboard discovery under package `mcp/dashboard/` — distinct from `ipfs-kit-mcp` |
| **Repo helper scripts** | e.g. `tools/start_3_node_cluster.py`, `servers/*` | Varies | **In-repo utilities**, not packaging entry points; treat as experimental/local unless you own that workflow |

Minimal CLI examples (no undeclared downloads):

```bash
ipfs-kit --help
ipfs-kit mcp status --port 8004
ipfs-kit-mcp --help
```

HTTP MCP++ example (binds loopback by default when using HTTP transport):

```bash
ipfs-kit-mcp --transport http --host 127.0.0.1 --port 8004
```

---

## 8. Configuration sketch

Programmatic override (verified constructor: `config_path` + `**kwargs`):

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI(
    # config_path="~/.ipfs_kit/config.yaml",  # optional file
    role="leecher",  # or master / worker when using role-aware features
)
```

Kit vs Kubo paths remain separate (see [§3.3](#33-state-paths-do-not-conflate)).
Detailed precedence, credentials, and trust boundaries live in
[`architecture/CONFIGURATION_STATE_AND_TRUST.md`](architecture/CONFIGURATION_STATE_AND_TRUST.md).

---

## 9. Troubleshooting

### 9.1 Wrong Python version

```text
ERROR: Package 'ipfs_kit_py' requires a different Python: ... not in '>=3.12'
```

Install Python 3.12+ and recreate the venv. Do not rely on `pytest.ini`
`minversion` as the support floor.

### 9.2 Import works but content ops fail

Usually no daemon or wrong API endpoint:

```bash
ipfs id
curl -s -X POST "http://127.0.0.1:5001/api/v0/id"
```

Start or point configuration at a reachable API. Install success ≠ daemon
health.

### 9.3 Unexpected binary download

1. Check `echo $IPFS_KIT_AUTO_INSTALL_BINARIES` — must be empty/`0` for no auto-install.
2. Do not run `install_*` methods or `ipfs-kit-iroh install` in restricted environments.
3. Prefer `pip install -e .` without setting auto-install.

### 9.4 Console script not found

Ensure the venv is active and the package was installed with setuptools entry
points (`pip install -e .`). Fallback: `python -m ipfs_kit_py.cli …`.

### 9.5 Optional extra import errors

Install the matching extra (for example `pip install -e ".[api]"`). Missing
extras should degrade feature use, not block core import when auto-install is
off.

### 9.6 Cluster / multi-node scripts

`tools/start_3_node_cluster.py` exists in this repository as a **local test
helper** (ports 8998–9000). It is not a packaging entry point and may require
additional services or environment. Prefer documented CLI/API paths for
production; treat the script as optional lab tooling.

### 9.7 Historical MCP server files under `servers/`

Files such as `servers/streamlined_mcp_server.py` are **in-repo server variants**.
Packaged MCP++ is `ipfs-kit-mcp`. Do not treat archive/root server shims as the
default install target.

---

## 10. Verification checklist

| Step | Command / check | Pass criteria |
|---|---|---|
| Python floor | `python --version` | 3.12+ |
| Install without binary side effects | `IPFS_KIT_AUTO_INSTALL_BINARIES=0 pip install -e .` | Completes without daemon binary fetch |
| Import | `python -c "import ipfs_kit_py"` | Exit 0 |
| HLA import | `python -c "from ipfs_kit_py.high_level_api import IPFSSimpleAPI"` | Exit 0 |
| CLI | `ipfs-kit --help` or `python -m ipfs_kit_py.cli --help` | Help text |
| Packaging version | `python -c "from importlib.metadata import version; print(version('ipfs_kit_py'))"` | Matches installed metadata (expect **0.3.0** on this baseline) |
| Optional live API | `api.add(...)` with running Kubo | Dict with success/CID when API healthy |

---

## 11. Related documentation

| Doc | Use |
|---|---|
| [`QUICK_REFERENCE.md`](QUICK_REFERENCE.md) | Short commands and API snippets |
| [`architecture/RUNTIME_AND_ENTRYPOINTS.md`](architecture/RUNTIME_AND_ENTRYPOINTS.md) | Process ownership per entry point |
| [`architecture/CONFIGURATION_STATE_AND_TRUST.md`](architecture/CONFIGURATION_STATE_AND_TRUST.md) | Config precedence, secrets, state roots |
| [`architecture/COMPATIBILITY_LAYERS.md`](architecture/COMPATIBILITY_LAYERS.md) | Canonical vs compatibility paths |
| [`audits/PUBLIC_SURFACE_MATRIX.md`](audits/PUBLIC_SURFACE_MATRIX.md) | Evidence matrix for surfaces and conflicts |
| [`api/cli_reference.md`](api/cli_reference.md) | Full CLI reference (when refreshed under KDOC-032) |
| [`api/high_level_api.md`](api/high_level_api.md) | HLA depth (KDOC-031) |
| [`INSTALLER_DOCUMENTATION.md`](INSTALLER_DOCUMENTATION.md) | Installer overview (optional binaries) |

---

**Summary:** Install the Python package with **Python 3.12+**, keep
`IPFS_KIT_AUTO_INSTALL_BINARIES` off unless you want downloads, verify import/CLI
offline, then add daemons and extras only for the features you use.
