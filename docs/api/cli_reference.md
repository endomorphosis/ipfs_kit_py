# Command-Line Interface (CLI) Reference

This reference is derived from the **live argument parsers** shipped with `ipfs_kit_py`:

| Surface | Source | Console entry |
| --- | --- | --- |
| Primary kit CLI | `ipfs_kit_py/cli.py` (`FastCLI`) + command trees from `ipfs_kit_py/unified_cli_dispatcher.py` | `ipfs-kit` → `ipfs_kit_py.cli:sync_main` |
| Module invocation | same | `python -m ipfs_kit_py.cli` |
| MCP tool mirror | `ipfs_kit_py/mcp_server/cli.py` | `ipfs-kit-mcp-tools` |
| MCP server process | `ipfs_kit_py/mcp_server/server.py` | `ipfs-kit-mcp` |
| Iroh sidecar install | `ipfs_kit_py/iroh_install_cli.py` | `ipfs-kit-iroh` |
| Iroh operator CLI | `ipfs_kit_py/iroh/cli.py` | `ipfs-kit-iroh-ops` |
| Iroh diagnostics | `ipfs_kit_py/iroh/diagnostics_cli.py` | `ipfs-kit-iroh-diagnostics` |
| Iroh manifest tools | `ipfs_kit_py/iroh/manifest_cli.py` | `ipfs-kit-iroh-manifest` |
| Iroh multi-node interop | `ipfs_kit_py/iroh/multinode.py` | `ipfs-kit-iroh-interop` |

**Out of scope for the primary `ipfs-kit` parser:** generic IPFS HTTP client commands (`add`, `cat`, `get`, `swarm`, `name`, cluster pin APIs, AI/ML subcommands), a global `--format` / `--profile` flag set, and standalone P2P workflow CLIs. Those are not registered on the live `FastCLI` tree. Use the IPFS daemon itself, MCP tools, or the separate scripts listed above.

There are **no argparse aliases** on the primary tree: each command and subcommand name is exact as listed below.

---

## Prerequisites

1. **Python package installed** so console scripts resolve, or run via module form:

   ```bash
   pip install -e .
   # or without install:
   PYTHONPATH=. python -m ipfs_kit_py.cli --help
   ```

2. **Optional runtime pieces** (only when you use the related commands):

   | Command family | Prerequisite |
   | --- | --- |
   | `mcp start` | Dashboard/server module discoverable (packaged under `ipfs_kit_py/mcp/dashboard/…`, or `--server-path` / `IPFS_KIT_SERVER_FILE`) |
   | `daemon start` | Daemon package path importable (`ipfs_kit_py.mcp.ipfs_kit.daemon…`) |
   | `services` | Local IPFS and/or Lotus tooling used by `EnhancedDaemonManager` / `lotus_daemon` |
   | `autoheal` | Writable `~/.ipfs_kit/`; GitHub token + repo for issue creation |
   | `bucket` / `vfs` / `wal` / `pin` / `backend` / `journal` / `state` | Corresponding handler modules and configured backends (handlers live in `bucket_vfs_cli`, `vfs_version_cli`, `wal_cli`, `simple_pin_cli`, `backend_cli`, `fs_journal_cli`, `state_cli`) |
   | Iroh console scripts | Optional Iroh sidecar/binary; install via `ipfs-kit-iroh` |

3. **Default data directory:** `~/.ipfs_kit` (expanded from `Path.home() / ".ipfs_kit"`).

This document intentionally describes the parser without starting long-running services.

---

## Invocation

```bash
ipfs-kit <COMMAND> ...
# equivalent:
python -m ipfs_kit_py.cli <COMMAND> ...
```

Top-level help:

```bash
ipfs-kit --help
# or
python -m ipfs_kit_py.cli --help
```

Root usage (live parser):

```text
usage: cli.py [-h]
              {mcp,daemon,services,autoheal,bucket,vfs,wal,pin,backend,journal,state}
              ...
```

Only `-h` / `--help` exists as a root option. There is **no** global `--config`, `--api`, `--timeout`, `--verbose`, `--format`, or `--version` on this entry point.

If no command is given, the CLI prints help and exits with code **2**.

---

## Command tree overview

```text
ipfs-kit
├── mcp
│   ├── start
│   ├── stop
│   ├── status
│   └── deprecations
├── daemon
│   └── start
├── services
│   ├── start
│   ├── stop
│   ├── restart
│   └── status
├── autoheal
│   ├── enable
│   ├── disable
│   ├── status
│   └── config
├── bucket
│   ├── create | list | info | delete | upload | download | ls
├── vfs
│   ├── snapshot | versions | restore | diff
├── wal
│   ├── status | list | show | wait | cleanup
├── pin
│   ├── add | rm | ls | info
├── backend
│   ├── create | list | info | update | delete | test
├── journal
│   ├── status | list | replay | compact
└── state
    ├── show | export | import | reset
```

Unified handlers (`bucket` … `state`) are attached from `UnifiedCLIDispatcher` into `FastCLI`. The standalone unified dispatcher also defines `audit` and a fuller `daemon` (start/stop/status), but **those extra trees are not registered** on the live `ipfs-kit` entry point—only the commands above are.

---

## Configuration, paths, and environment

### Paths used by the primary CLI

| Path / value | Role |
| --- | --- |
| `~/.ipfs_kit` | Default `--data-dir` for MCP and daemon |
| `~/.ipfs_kit/mcp_<port>.pid` | MCP background PID file |
| `~/.ipfs_kit/dashboard.pid` | Fallback PID file for older dashboards |
| `~/.ipfs_kit/mcp_<port>.log` | Background MCP log |
| `~/.ipfs_kit/auto_heal_config.json` | Auto-heal configuration (`AutoHealConfig`) |
| `/tmp/ipfs_kit_config` | Default `--config-dir` for `daemon start` |

### Environment variables

| Variable | Used by | Purpose |
| --- | --- | --- |
| `IPFS_KIT_SERVER_FILE` | `mcp start` | Absolute path to dashboard/server module if not using `--server-path` |
| `IPFS_KIT_FAST_INIT` | `mcp start` | Propagated into background child; set automatically under pytest markers |
| `IPFS_KIT_AUTO_HEAL` | auto-heal config load | When `true`/`1`/`yes`, influences enablement via config defaults |
| `PYTHONPATH` | background MCP spawn | Parent process sets package root so the child can import `ipfs_kit_py` |
| `IPFS_KIT_BIN_DIR` | `ipfs-kit-iroh` | Default managed binary directory (`--bin-dir`) |

### Backend configuration

For non-MCP management commands, `FastCLI` attempts `initialize_backend_config(log_status=False)` before dispatch. MCP `start` / `stop` / `status` / `deprecations` **skip** that initialization for faster readiness checks.

### Auto-heal configuration keys

`ipfs-kit autoheal config` reads/writes attributes on `AutoHealConfig`, including:

- `enabled`, `github_repo`, `github_token` (token not printed in full)
- `max_log_lines`, `include_stack_trace`, `auto_create_issues`, `issue_labels`

Boolean keys accept `true`/`1`/`yes` (case-insensitive). `issue_labels` is a comma-separated list. `max_log_lines` is an integer.

---

## Output and error behavior

### Primary `ipfs-kit` exit codes

| Code | When |
| --- | --- |
| **0** | Command completed (including “already stopped” style success paths that only print a message) |
| **1** | Operational failure (e.g. MCP background launch failed, daemon import/start failed) |
| **2** | Usage / missing command / unknown command / MCP server file not found / unified command import failure |
| **3** | `mcp deprecations --fail-if-hits-over N` when any listed endpoint exceeds the hit threshold |
| **4** | `mcp deprecations --fail-if-missing-migration` when any deprecated endpoint lacks a migration mapping |
| **argparse non-zero** | Invalid options/arguments (argparse default error path) |

Unhandled exceptions in non-MCP-fast-path commands may be captured by auto-heal (GitHub issue creation when configured) and are then re-raised so the process still fails.

### Output shapes

| Area | Default output |
| --- | --- |
| Most commands | Human-readable text or `print(...)` status lines |
| `mcp status` | Pretty-printed JSON (`pidFile`, `pid`, optional `http` probe of `/api/mcp/status`) |
| `mcp deprecations` | Text lines ` - endpoint | remove_in=… | note`; with `--json`, raw JSON array (and stdout is scrubbed so only the final JSON line is emitted) |
| `mcp deprecations --report-json PATH` | File report with `report_version` (`1.0.0`), `generated_at`, `deprecated`, `summary`, `policy`, … |
| `services *` | JSON object keyed by service name (`ipfs` / `lotus`) |
| `services status` | JSON whether or not `--json` is set (flag accepted for consistency) |
| `autoheal status` | Human summary, or JSON with `--json` |
| Unified commands | Handler-defined (often structured text/JSON from the specialized CLI modules) |

There is **no** global `--format {json,text,table}` switch on the primary parser. Prefer command-local `--json` where provided.

### Unified command routing errors

When a unified command’s handler is missing, the CLI prints `❌ Command '<name>' is not available` (or `missing dependencies`) and exits **2** (import failure at FastCLI) or returns **1** from the dispatcher.

---

## Primary commands

Defaults below match the live parser (`~` expands to the invoking user’s home directory).

### `mcp` — MCP server and dashboard

```bash
ipfs-kit mcp {start,stop,status,deprecations} ...
```

#### `mcp start`

| Option | Default | Description |
| --- | --- | --- |
| `--port` | `8004` | Listen port |
| `--host` | `127.0.0.1` | Bind host |
| `--debug` | off | Debug mode for the dashboard |
| `--foreground` | off | Run in the current process instead of detaching |
| `--data-dir` | `~/.ipfs_kit` | PID/log/data directory |
| `--server-path` | unset | Explicit dashboard module path |

Server resolution order: `--server-path` → `IPFS_KIT_SERVER_FILE` → packaged dashboard candidates under `ipfs_kit_py/mcp/…` → repo-local dashboard filenames. Missing server → exit **2**.

Background mode re-execs `python -m ipfs_kit_py.cli mcp start … --foreground` with `IPFS_KIT_SERVER_FILE` set, writes `mcp_<port>.pid`, and logs to `mcp_<port>.log`.

#### `mcp stop`

| Option | Default |
| --- | --- |
| `--port` | `8004` |
| `--data-dir` | `~/.ipfs_kit` |

Sends `SIGTERM` (or Windows interrupt/term) to the PID file process; removes the PID file when finished.

#### `mcp status`

| Option | Default |
| --- | --- |
| `--port` | `8004` |
| `--host` | `127.0.0.1` |
| `--data-dir` | `~/.ipfs_kit` |

Prints JSON status; HTTP probe targets `http://{host}:{port}/api/mcp/status` (best-effort).

#### `mcp deprecations`

| Option | Default | Description |
| --- | --- | --- |
| `--port` | `8004` | |
| `--host` | `127.0.0.1` | |
| `--json` | off | Emit JSON array on stdout |
| `--fail-if-missing-migration` | off | Exit **4** on migration gaps |
| `--fail-if-hits-over N` | unset | Exit **3** if any hit count > N |
| `--report-json PATH` | unset | Write schema `1.0.0` report file |
| `--sort` | unset | Only `hits` supported |
| `--min-hits N` | unset | Drop entries below threshold |

Fetches `http://{host}:{port}/api/system/deprecations`. If the server is down, still produces empty/error-shaped data so report generation can succeed offline.

---

### `daemon` — IPFS-Kit daemon API server

Live tree exposes **only** `start` (not stop/status on the primary entry).

#### `daemon start`

| Option | Default |
| --- | --- |
| `--port` | `9999` |
| `--host` | `0.0.0.0` |
| `--debug` | off |
| `--config-dir` | `/tmp/ipfs_kit_config` |
| `--data-dir` | `~/.ipfs_kit` |

Import or start failure → exit **1**.

---

### `services` — filesystem service control

```bash
ipfs-kit services {start,stop,restart,status} [--service {ipfs,lotus,all}] ...
```

| Subcommand | Options |
| --- | --- |
| `start` | `--service` (default `all`), `--detach` (IPFS only) |
| `stop` | `--service`, `--force` (Lotus) |
| `restart` | `--service`, `--detach`, `--force` |
| `status` | `--service`, `--json` |

Resolves `all` → `["ipfs", "lotus"]`. Results are printed as JSON.

---

### `autoheal` — GitHub-backed error auto-healing

```bash
ipfs-kit autoheal {enable,disable,status,config} ...
```

| Subcommand | Options |
| --- | --- |
| `enable` | `--github-token`, `--github-repo` (`owner/repo`) |
| `disable` | (none) |
| `status` | `--json` |
| `config` | `--set KEY VALUE`, `--get KEY`, or no args to list |

Config file: `~/.ipfs_kit/auto_heal_config.json`.

---

### `bucket` — multi-bucket virtual filesystems

```bash
ipfs-kit bucket {create,list,info,delete,upload,download,ls} ...
```

| Subcommand | Arguments / options |
| --- | --- |
| `create` | `name`; `--type` ∈ `{general,dataset,knowledge,media,archive,temp}` (default `general`); `--structure` ∈ `{flat,hierarchical,temporal,categorical}` (default `hierarchical`) |
| `list` | (none) |
| `info` | `name` |
| `delete` | `name`; `--force` |
| `upload` | `bucket` `source`; `--dest` |
| `download` | `bucket` `source`; `--dest` |
| `ls` | `bucket`; `--path` (default `/`) |

---

### `vfs` — VFS versioning and snapshots

```bash
ipfs-kit vfs {snapshot,versions,restore,diff} ...
```

| Subcommand | Arguments / options |
| --- | --- |
| `snapshot` | `bucket`; `--message` |
| `versions` | `bucket` |
| `restore` | `bucket` `version` |
| `diff` | `bucket` `version1` `version2` |

---

### `wal` — Write-Ahead Log operations

```bash
ipfs-kit wal {status,list,show,wait,cleanup} ...
```

| Subcommand | Arguments / options |
| --- | --- |
| `status` | (none) |
| `list` | `--status` ∈ `{pending,completed,failed,all}` (default `pending`); `--limit` (default `50`) |
| `show` | `operation_id` |
| `wait` | `operation_id`; `--timeout` seconds (default `300`) |
| `cleanup` | `--age` days (default `7`) |

---

### `pin` — IPFS pins

```bash
ipfs-kit pin {add,rm,ls,info} ...
```

| Subcommand | Arguments / options |
| --- | --- |
| `add` | `cid`; `--name`; `--recursive` |
| `rm` | `cid` |
| `ls` | `--type` ∈ `{direct,recursive,indirect,all}` (default `all`) |
| `info` | `cid` |

---

### `backend` — storage backends

```bash
ipfs-kit backend {create,list,info,update,delete,test} ...
```

| Subcommand | Arguments / options |
| --- | --- |
| `create` | `name` `type` (e.g. `s3`, `ipfs`, `storj`); `--endpoint`, `--access-key`, `--secret-key`, `--bucket`, `--region` |
| `list` | (none) |
| `info` | `name` |
| `update` | `name`; `--endpoint`, `--access-key`, `--secret-key` |
| `delete` | `name` |
| `test` | `name` |

---

### `journal` — filesystem journal

```bash
ipfs-kit journal {status,list,replay,compact} ...
```

| Subcommand | Arguments / options |
| --- | --- |
| `status` | (none) |
| `list` | `--limit` (default `50`); `--operation` filter |
| `replay` | `--from-seq`, `--to-seq` |
| `compact` | `--keep-days` (default `30`) |

---

### `state` — IPFS Kit state

```bash
ipfs-kit state {show,export,import,reset} ...
```

| Subcommand | Arguments / options |
| --- | --- |
| `show` | (none) |
| `export` | `output`; `--format` ∈ `{json,yaml}` (default `json`) |
| `import` | `input` |
| `reset` | `--confirm` (required to actually reset) |

---

## Installed console scripts (separate surfaces)

These are **not** subcommands of `ipfs-kit`. They are independent entry points from `[project.scripts]` in `pyproject.toml`.

### `ipfs-kit-mcp`

Starts the packaged MCP server process (`ipfs_kit_py.mcp_server.server:main`).

### `ipfs-kit-mcp-tools`

Mirrors every MCP tool as a CLI command:

```bash
ipfs-kit-mcp-tools                 # list categories
ipfs-kit-mcp-tools list            # list tools per category
ipfs-kit-mcp-tools <category> <tool> [--key value ...]
```

Categories include (live manager listing): `ipfs_tools`, `pin_tools`, `dag_tools`, `mfs_tools`, `swarm_tools`, `name_tools`, `car_tools`, `cluster_tools`, `block_tools`, `bitswap_tools`, `stats_tools`, `iroh_tools`.

Exit **0** on success, **1** when the tool result status is not `success`, **2** on usage errors. Output is JSON.

### `ipfs-kit-iroh` — managed sidecar lifecycle

```bash
ipfs-kit-iroh [--bin-dir DIR] [--json] {install,inspect,update,rollback} ...
```

| Command | Notable options |
| --- | --- |
| `install` | `--version`, `--allow-prerelease`, `--dry-run`, `--check` |
| `inspect` | `--check` |
| `update` | `--version`, `--allow-prerelease`, `--dry-run`, `--check` |
| `rollback` | `--dry-run`, `--check` |

Global: `--bin-dir` (defaults via `IPFS_KIT_BIN_DIR`), `--json` for machine-readable output. Network/filesystem mutations occur only on install/update/rollback.

### `ipfs-kit-iroh-ops` — JSON-only Iroh operator CLI

Safe orchestration layer (`ipfs_kit_py.iroh.cli`). Emits structured JSON on stdout (success) or stderr (errors). Does not put bearer tickets in argv.

Global: `--compact` (one-line JSON).

```text
ipfs-kit-iroh-ops
├── binary   {install,update,inspect,rollback}
├── service  {status,start,stop,restart}
├── backend  {list,show,health,capabilities,validate,create,remove}
├── namespace {create,info,history,recover}
├── blob     {stat,add,fetch,export}
├── ticket   {import}
├── mount    {list,add,remove}
├── sync     {run,status}
└── gc       {plan,run,collect,resume}
```

**Legacy argv:** top-level `install` / `inspect` / `update` / `rollback` are rewritten to `binary <cmd>` for compatibility with older scripts.

Common option groups:

- **Instance / config:** `--instance` (default `default`), `--state-root`, `--config`, `--timeout`
- **Destructive actions:** `--dry-run`; mutual exclusion `--yes` | `--confirm PHRASE`
- **Tickets:** `--ticket-file` or `--ticket-stdin` (never a bare ticket argv)
- **Sync:** `--file` request JSON; `--conflict-policy` ∈ `{fail,source-wins,destination-wins,keep-both}`; `--continue-on-error` / `--no-continue-on-error`
- **GC:** retention/quota flags; `--apply` vs `--dry-run` (dry-run default for live GC)

Exit codes (Iroh ops):

| Code | Constant | Meaning |
| --- | --- | --- |
| 0 | `EXIT_SUCCESS` | Success |
| 2 | `EXIT_USAGE` | Invalid arguments (JSON error on stderr) |
| 3 | `EXIT_CONFIRMATION` | Confirmation required/mismatch |
| 4 | `EXIT_INVALID` | Invalid input/config |
| 5 | `EXIT_NOT_FOUND` | Missing resource |
| 6 | `EXIT_CONFLICT` | Conflict |
| 7 | `EXIT_UNAVAILABLE` | Service unavailable |
| 8 | `EXIT_INTEGRITY` | Integrity failure |
| 9 | `EXIT_PERMISSION` | Permission / unsafe ticket file mode |
| 10 | `EXIT_FAILED` | Partial/failed operation receipt |
| 130 | `EXIT_INTERRUPTED` | Keyboard interrupt |

Success envelope: `{"ok": true, "operation": "...", "result": ...}`. Failure: `{"ok": false, "error": {"code": "...", "message": "..."}}` (no raw exception text).

### `ipfs-kit-iroh-diagnostics`

```bash
ipfs-kit-iroh-diagnostics [--instance NAME] [--state-root PATH] [--config FILE]
                          [--format {json,prometheus}] [--no-persist]
```

Health/metrics for managed Iroh instances.

### `ipfs-kit-iroh-manifest`

```bash
ipfs-kit-iroh-manifest migrate [--overwrite] SOURCE [DESTINATION]
ipfs-kit-iroh-manifest recover [--apply] [--history-limit N] NAMESPACE_ID
```

Atomic schema migration and authenticated namespace head recovery (`recover` is dry-run unless `--apply`).

### `ipfs-kit-iroh-interop`

```bash
ipfs-kit-iroh-interop [--check-evidence PATH]
```

Opt-in real multi-node interoperability tests / evidence validation.

---

## Help-based verification

Run these against an installed package (or `PYTHONPATH=.`) to confirm the live tree matches this document. No daemons need to be running.

```bash
# Primary entry
python -m ipfs_kit_py.cli --help
python -m ipfs_kit_py.cli mcp --help
python -m ipfs_kit_py.cli mcp start --help
python -m ipfs_kit_py.cli mcp deprecations --help
python -m ipfs_kit_py.cli daemon start --help
python -m ipfs_kit_py.cli services --help
python -m ipfs_kit_py.cli autoheal --help
python -m ipfs_kit_py.cli bucket --help
python -m ipfs_kit_py.cli vfs --help
python -m ipfs_kit_py.cli wal --help
python -m ipfs_kit_py.cli pin --help
python -m ipfs_kit_py.cli backend --help
python -m ipfs_kit_py.cli journal --help
python -m ipfs_kit_py.cli state --help

# Expect top-level choices to include backend + journal among others:
python -m ipfs_kit_py.cli --help | rg -e 'backend|journal|bucket|vfs|wal|pin|mcp|daemon|services|autoheal|state'

# Separate surfaces
python -m ipfs_kit_py.iroh_install_cli --help
python -m ipfs_kit_py.iroh.cli --help
python -m ipfs_kit_py.iroh.diagnostics_cli --help
python -m ipfs_kit_py.iroh.manifest_cli --help
python -m ipfs_kit_py.mcp_server.cli --help
```

Example smoke checks:

```bash
# MCP status without a running server still returns JSON (pid may be null)
python -m ipfs_kit_py.cli mcp status --port 8004

# Deprecations policy flags accept help even offline
python -m ipfs_kit_py.cli mcp deprecations --help

# Auto-heal status is local-config only
python -m ipfs_kit_py.cli autoheal status --json
```

---

## Implementation map

| Concern | Module |
| --- | --- |
| Entry / MCP / daemon / services / autoheal parsers & handlers | `ipfs_kit_py/cli.py` |
| Bucket / VFS / WAL / pin / backend / journal / state parsers | `ipfs_kit_py/unified_cli_dispatcher.py` (methods `_add_*_commands`) |
| Console script wiring | `pyproject.toml` → `[project.scripts]` |
| Deprecations report schema version | `REPORT_SCHEMA_VERSION = "1.0.0"` in `cli.py` |

When extending the CLI, update the live parsers first, then re-run the help-based verification section and refresh this file so the command tree, defaults, exit codes, and separate surfaces stay in agreement.
