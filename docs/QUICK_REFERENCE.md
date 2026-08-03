# IPFS Kit Python — Quick Reference

| Field | Value |
|---|---|
| Document class | **Canonical** current-user quick reference |
| Task | KDOC-030 — Refresh installation and quick-reference paths |
| Goal | KDOC-G041 |
| Packaging baseline | `pyproject.toml` **0.3.0**, Python **>=3.12** |
| Last verified | 2026-08-03 (static/offline against this tree) |
| Full install guide | [`installation_guide.md`](installation_guide.md) |

Fast lookup for install, first success, Python API, CLI, MCP, and common ops.
Examples use **verified** packaging entry points and `IPFSSimpleAPI` methods
present on this tree. Nonexistent scripts (for example `ipfs-kit-install`) are
intentionally omitted.

---

## Installation

**Requires Python 3.12+** (3.13 supported per packaging classifiers).

```bash
# Stay free of undeclared binary downloads
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

# From this repo (recommended for development)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .

# Common extras (optional)
pip install -e ".[api]"
pip install -e ".[fsspec]"
pip install -e ".[ai_ml]"
pip install -e ".[dev]"
pip install -e ".[full]"   # heavy umbrella; may pull VCS deps

# From an index (library consumers)
pip install "ipfs_kit_py>=0.3.0"
```

| Fact | Value |
|---|---|
| Release / packaging version | **0.3.0** (authoritative) |
| `import ipfs_kit_py; ipfs_kit_py.__version__` | May still report **0.2.0** (known drift) |
| Default binary auto-download | **Off** |

Full details: [`installation_guide.md`](installation_guide.md).

---

## First success (no daemon required)

```bash
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

python -c "import ipfs_kit_py; print('ok', getattr(ipfs_kit_py, '__version__', None))"
python -c "from ipfs_kit_py.high_level_api import IPFSSimpleAPI; print(IPFSSimpleAPI)"
python -c "from importlib.metadata import version; print(version('ipfs_kit_py'))"

ipfs-kit --help
# equivalent:
python -m ipfs_kit_py.cli --help
```

---

## Packaged entry points

| Command | Role |
|---|---|
| `ipfs-kit` | Operator CLI |
| `ipfs-kit-mcp` | MCP++ JSON-RPC server |
| `ipfs-kit-mcp-tools` | One-shot MCP tool CLI |
| `ipfs-kit-iroh` | Managed Iroh binary install/inspect/update/rollback (**downloads on `install`**) |
| `ipfs-kit-iroh-ops` | Iroh service operations |
| `ipfs-kit-iroh-diagnostics` | Iroh diagnostics |
| `ipfs-kit-iroh-manifest` | Manifest migrate/recover |
| `ipfs-kit-iroh-interop` | Multi-node interop harness |

---

## Python API — high-level

Preferred import:

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI()                    # optional config_path=, **kwargs (e.g. role=)
# api = IPFSSimpleAPI(role="master")
```

Also available as a lazy root proxy: `from ipfs_kit_py import IPFSSimpleAPI`.

### Content operations

```python
# Add (file path, str, bytes, or path-like). Returns a result dict (includes cid on success).
result = api.add("myfile.txt")           # pin=True by default
result = api.add(b"raw bytes")
result = api.add("myfile.txt", pin=True, wrap_with_directory=True)
cid = result.get("cid")

content = api.get(cid)
data = api.read(cid)
exists = api.exists(cid)

api.pin(cid)
pins = api.list_pins()

entries = api.ls(directory_cid, detail=True)
```

### IPNS

```python
published = api.publish(cid, key="self")   # key name; lifetime via kwargs when needed
resolved = api.resolve(ipns_name)
```

### Cluster helpers

```python
api = IPFSSimpleAPI(role="master")

result = api.cluster_add("myfile.txt", replication_factor=2)
api.cluster_pin(cid, replication_factor=2)
status = api.cluster_status(cid)
peers = api.cluster_peers()
```

Requires cluster-capable setup (binaries/services); not part of a bare core install.

### AI/ML helpers (optional; needs `[ai_ml]` / models)

Verified method names on `IPFSSimpleAPI` include:

```python
api.ai_model_add(...)
api.ai_model_get(...)
api.ai_dataset_add(...)
api.ai_dataset_get(...)
api.ai_list_models(...)
api.ai_register_model(...)
# plus embeddings, vector index, langchain/llama helpers — see high_level_api source
```

There is **no** `ai_metrics_visualize` method on the current class; use metrics /
dashboard docs for visualization paths.

### Live daemon note

Content methods typically need a reachable IPFS API (default local Kubo on
`127.0.0.1:5001`). Import and construction can succeed without a daemon.

---

## CLI — operator (`ipfs-kit`)

Top-level families wired on FastCLI:

```bash
ipfs-kit --help

# MCP dashboard control (compatibility dashboard stack; PID under ~/.ipfs_kit)
ipfs-kit mcp start --port 8004 --foreground
ipfs-kit mcp status --port 8004
ipfs-kit mcp stop --port 8004
ipfs-kit mcp deprecations --json

# Kit daemon API (legacy IPFSKitDaemon path)
ipfs-kit daemon start

# External filesystem services (IPFS / related managers)
ipfs-kit services start
ipfs-kit services status
ipfs-kit services stop

# Auto-heal toggles
ipfs-kit autoheal status
```

Unified domain commands (when mounted): `bucket`, `vfs`, `wal`, `pin`, `backend`,
`journal`, `state` — run `ipfs-kit <name> --help` for subcommands.

---

## MCP++ (packaged)

```bash
# Agent stdio (default)
ipfs-kit-mcp

# HTTP on loopback
ipfs-kit-mcp --transport http --host 127.0.0.1 --port 8004

# One-shot tools CLI
ipfs-kit-mcp-tools --help
```

Prefer **`ipfs-kit-mcp`** for agent JSON-RPC / MCP++. Prefer **`ipfs-kit mcp …`**
only for the dashboard control path (distinct stack).

---

## Optional binaries (explicit opt-in)

```bash
# Never set this in CI/docs unless you intend downloads
export IPFS_KIT_AUTO_INSTALL_BINARIES=0

# Kubo via Python installer (downloads when methods run)
python - <<'PY'
from ipfs_kit_py import install_ipfs
install_ipfs().install_ipfs_daemon()
PY

# Iroh managed sidecar
ipfs-kit-iroh install --dry-run
ipfs-kit-iroh install
ipfs-kit-iroh inspect --check
```

Manual Kubo:

```bash
ipfs init
ipfs daemon
ipfs --version
curl -s -X POST "http://127.0.0.1:5001/api/v0/id"
```

---

## State and environment

| Item | Default / notes |
|---|---|
| Kit state root | `~/.ipfs_kit` (`--data-dir` on MCP CLI) |
| Kubo repo | `~/.ipfs` via `IPFS_PATH` |
| Managed binaries | `IPFS_KIT_BIN_DIR` or package/platform default |
| Auto binary install | `IPFS_KIT_AUTO_INSTALL_BINARIES` (default **off**) |
| MCP dashboard server file | `IPFS_KIT_SERVER_FILE` / `--server-path` |
| Fast init (tests/CLI) | `IPFS_KIT_FAST_INIT` |

```text
~/.ipfs_kit/          # kit state (config, PIDs, backends) — not the Kubo repo
~/.ipfs/              # Kubo repository (IPFS_PATH)
```

---

## Configuration sketch

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI(
    # config_path="~/.ipfs_kit/config.yaml",
    role="leecher",
)
```

YAML under `~/.ipfs_kit/config.yaml` is used by thin/dashboard helpers; HLA also
accepts path + kwargs. Precedence and credentials:
[`architecture/CONFIGURATION_STATE_AND_TRUST.md`](architecture/CONFIGURATION_STATE_AND_TRUST.md).

Example shape (illustrative):

```yaml
# ~/.ipfs_kit/config.yaml
role: leecher

ipfs:
  api_host: 127.0.0.1
  api_port: 5001
```

---

## Common issues

| Symptom | Check |
|---|---|
| Install rejected | Python &lt; 3.12 → upgrade runtime |
| Import OK, ops fail | `ipfs id` / API `5001` reachable? |
| Binary download in CI | Ensure `IPFS_KIT_AUTO_INSTALL_BINARIES` is unset/`0` |
| `ipfs-kit` not found | Activate venv; or `python -m ipfs_kit_py.cli` |
| Wrong “version” string | Use `importlib.metadata.version("ipfs_kit_py")` (packaging), not only `__version__` |
| Missing optional feature | Install matching extra (`[api]`, `[ai_ml]`, …) |

```bash
# Connection
ipfs id
curl -s -X POST "http://127.0.0.1:5001/api/v0/id"

# Package
python -c "import ipfs_kit_py; print(ipfs_kit_py.__version__)"
python -c "from importlib.metadata import version; print(version('ipfs_kit_py'))"
```

---

## Repo helpers (not packaging entry points)

| Path | Notes |
|---|---|
| `tools/start_3_node_cluster.py` | Local multi-port lab helper (8998–9000); optional, not a console script |
| `servers/*` | Historical/variant MCP server files; packaged MCP is `ipfs-kit-mcp` |

```bash
# Lab only — not required for a normal install
python tools/start_3_node_cluster.py
```

---

## Getting help

```bash
ipfs-kit --help
ipfs-kit mcp --help
ipfs-kit-mcp --help
ipfs-kit-iroh --help

python -c "from ipfs_kit_py.high_level_api import IPFSSimpleAPI; help(IPFSSimpleAPI.add)"
```

---

## Related documentation

| Doc | Topic |
|---|---|
| [`installation_guide.md`](installation_guide.md) | Full install, extras, binary policy |
| [`api/high_level_api.md`](api/high_level_api.md) | HLA reference (KDOC-031) |
| [`api/cli_reference.md`](api/cli_reference.md) | CLI tree (KDOC-032) |
| [`architecture/RUNTIME_AND_ENTRYPOINTS.md`](architecture/RUNTIME_AND_ENTRYPOINTS.md) | Entry process ownership |
| [`architecture/CONFIGURATION_STATE_AND_TRUST.md`](architecture/CONFIGURATION_STATE_AND_TRUST.md) | Config / secrets / state |
| [`audits/PUBLIC_SURFACE_MATRIX.md`](audits/PUBLIC_SURFACE_MATRIX.md) | Surface evidence and conflicts |
| [`README.md`](README.md) | Docs index |

---

**Note:** Prefer packaging metadata and this guide over older status reports under
`docs/ARCHIVE/`. Binary installation remains **opt-in** for every documented path.
