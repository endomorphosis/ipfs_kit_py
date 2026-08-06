# Configuration, local state, credentials, trust, and process lifecycle

| Field | Value |
|---|---|
| Document class | **Canonical** architecture guide |
| Status | active |
| Last verified | 2026-08-03 |
| Tree baseline | `5a2d23561ae515c732f47534e3afba3af636284f` |
| Owner / task | KDOC-019 |
| Goal id | KDOC-G025 |
| Track | arch-trust |
| Authority class | Canonical architecture guide for configuration/state/trust; not an accepted ADR for disputed composition decisions (**U-13**, planned ADR-0007) |
| Evidence map | [`SOURCE_OF_TRUTH_MAP.md`](./SOURCE_OF_TRUTH_MAP.md) §1, §2, §7 |
| Surface matrix | [`docs/audits/PUBLIC_SURFACE_MATRIX.md`](../audits/PUBLIC_SURFACE_MATRIX.md) |
| Vocabulary | [`GLOSSARY.md`](./GLOSSARY.md) |
| Contract | [`docs/guides/DOCUMENTATION_GUIDE.md`](../guides/DOCUMENTATION_GUIDE.md) |
| Packaging baseline | `pyproject.toml` version **0.3.0** |
| Change triggers | See [§13](#13-change-triggers-and-last-verified-baseline) |

This guide answers: *where does configuration come from, who owns each mutable or sensitive state family, what permissions and lifecycle apply, what fails closed versus soft, how processes and binaries start and stop, and how to diagnose problems without leaking secrets?*

It **links** subsystem guides rather than re-documenting content-plane recovery, MCP tool registries, or Iroh threat-model depth.

**Sibling guides**

| Guide | Owns |
|---|---|
| [`SYSTEM_OVERVIEW.md`](./SYSTEM_OVERVIEW.md) | System context, high-level trust domains, deployment shapes |
| [`RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md) | Per-entry process/event-loop ownership, init/shutdown |
| [`MCP_CONTROL_PLANE.md`](./MCP_CONTROL_PLANE.md) | MCP++ surfaces, receipts, control-plane trust edges |
| [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md) | Bytes vs metadata, WAL/journal durability and recovery |
| Planned `STORAGE_BACKEND_SYSTEM.md` | Backend plugins vs live adapters |
| Planned `ASYNC_AND_OPTIONAL_DEPENDENCIES.md` | AnyIO/extras degradation |
| Planned `NETWORK_TRANSPORTS.md` | Transport security boundaries |
| Normative `docs/iroh/*` | Iroh security, install/service lifecycle, credential rotation |
| Planned ADR-0007 | Configuration/state/secret-reference composition decisions |

---

## 1. Scope and explicit non-goals

### 1.1 Scope

| In scope | Why |
|---|---|
| Configuration sources and **precedence** | Operators and agents need a single merge story |
| Kit state root vs Kubo repo vs Iroh instance trees | Prevent mixed-path corruption and wrong cleanup |
| **Every sensitive or mutable state family** | Owner, location rule, permissions, lifecycle, failure behavior, safe diagnostics |
| Credentials, secret stores, redaction, secret references | Stop logs, docs, and support bundles from carrying live secrets |
| Trust boundaries (host, loopback control, network, peer) | Know what expands attack surface |
| Process and binary lifecycle ownership | Who starts/stops what; readiness vs liveness |
| Explicit **opt-in** binary installation | Default must never download or mutate binaries at import/setup |
| Health, observability, and recovery hooks that are safe to share | Offline diagnosis first |

### 1.2 Non-goals

| Out of scope | Owner / pointer |
|---|---|
| Resolving a single canonical config API among managers | **U-13** / planned ADR-0007 |
| Choosing production MCP runtime among competing trees | [`MCP_CONTROL_PLANE.md`](./MCP_CONTROL_PLANE.md); ADR-0003 |
| Full WAL/journal recovery sequences | [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md) |
| Full Iroh threat model and rotation runbooks | `docs/iroh/security.md`, `threat-model.md`, `credential-rotation.md` |
| User install tutorials and example credentials | Current-doc wave; never put live tokens in docs |
| Editing protected program-control files | Operator policy |

### 1.3 Status vocabulary

| Label | Meaning here |
|---|---|
| **canonical (packaged)** | Default product path evidenced by packaging and current kit modules |
| **candidate** | Implemented and preferred for new work until ADR confirmation |
| **compatibility / historical** | Still importable; do not treat as equal default |
| **unresolved** | Composition or authority decision open (**U-***) |

---

## 2. How to read each state family

Acceptance for KDOC-019 requires every sensitive or mutable family to document:

| Field | Meaning |
|---|---|
| **Owner** | Module(s) and process/role that create, mutate, and delete the state |
| **Location rule** | Default path, override env/flags, and what must never share a tree |
| **Permissions** | Directory/file modes and isolation expectations |
| **Lifecycle** | Create → use → rotate/migrate → stop/archive |
| **Failure behavior** | Fail-closed vs fail-soft; corruption and partial-write handling |
| **Safe diagnostics** | What to inspect/log/export without revealing secrets |

**Secret** material (keys, tokens, tickets, capabilities, encryption master keys, cluster secrets, node identities) must never appear in documentation examples, architecture tables, support dumps, or routine logs. Prefer `secretref:<provider>:<id>` or `credential://…` references and redacted output.

---

## 3. Configuration sources and precedence

Configuration is **fragmented across managers** by design today. There is no single super-config object that owns every subsystem (**U-13**). Operators should treat each surface’s precedence rules as authoritative for that surface, and keep secrets out of shared YAML when a dedicated credential/secret store exists.

### 3.1 Surfaces that load configuration

| Surface | Primary modules | What it configures |
|---|---|---|
| Thin kit config | `ipfs_kit_py/config.py` | `~/.ipfs_kit/config.yaml` read/write helpers (dashboard-oriented) |
| High-level API / client | `high_level_api.py` (`IPFSSimpleAPI` load paths) | Role, cache, timeouts, logging, fsspec kwargs |
| Named backend documents | `backend_manager.py` + `backend_registry.py` | Per-backend YAML under `~/.ipfs_kit/backends/` |
| Daemon orchestration | `daemon_config_manager.py` | Kubo/Cluster/Lotus paths, ports, install gates |
| Secure encrypted config | `secure_config.py`, `cli_secure_config.py` | Sensitive field encryption under kit state + `.keyring/` |
| Credential manager | `credential_manager.py` | Service credentials (keyring preferred, file fallback) |
| Enhanced secrets | `enhanced_secrets_manager.py`, `aes_encryption.py` | Encrypted secret records + audit log |
| Iroh service config | `iroh/config.py`, `iroh/security.py` | Instance roots, RPC, credential **references** only |
| MCP++ profiles | `mcp_server/` | Transport bind, coordination stores, tool backends |
| Operator CLI | `cli.py` (`--data-dir`, MCP/daemon flags) | Data dir, ports, server path, fast-init |

### 3.2 Precedence rules (evidence-backed)

**High-level API / filesystem kwargs** (`high_level_api.py`):

1. Explicit method parameters  
2. `kwargs`  
3. Values from loaded config  
4. Built-in defaults (e.g. role `leecher`, mmap on)

**HLA file discovery** when no `config_path` is passed (first existing wins):

1. `./ipfs_config.yaml` / `./ipfs_config.json`  
2. `~/.ipfs_kit/config.yaml` / `~/.ipfs_kit/config.json`  
3. `/etc/ipfs_kit/config.yaml` / `/etc/ipfs_kit/config.json`  

Loaded file values override built-in defaults; missing file yields defaults only (warn on parse error, do not crash).

**Thin `config.py`**: fixed path `Path.home() / '.ipfs_kit' / 'config.yaml'` — no env override inside this module.

**Named backends**: on-disk YAML is the authority for each named document after schema validation/migration. API responses use `redact_backend_config` by default.

**Environment variables** (selected; not exhaustive):

| Variable | Default / behavior | Affects |
|---|---|---|
| `IPFS_KIT_AUTO_INSTALL_BINARIES` | **Off** / falsy | setup.py, `kubo_runtime`, daemon installers, Iroh package install narrative |
| `IPFS_KIT_AUTO_UPGRADE_KUBO` | On **when** install path runs | Kubo upgrade during managed install |
| `IPFS_KIT_BIN_DIR` | Package `ipfs_kit_py/bin` (Kubo); Iroh docs also use `~/.local/share/ipfs_kit_py/bin` | Managed binary directory |
| `IPFS_PATH` | `~/.ipfs` | Kubo repo (distinct from kit state root) |
| `IPFS_KIT_FAST_INIT` | Unset; set under pytest for MCP | Skip heavy init paths |
| `IPFS_KIT_SERVER_FILE` | Unset | Dashboard script for `ipfs-kit mcp start` |
| CLI `--data-dir` | `~/.ipfs_kit` | MCP PID/logs, StateService-oriented CLI paths |

README also documents operator-facing vars such as `IPFS_KIT_CONFIG`, `IPFS_KIT_DATA_DIR`, `IPFS_KIT_CACHE_DIR`, and backend credential env names. Treat those as **operator contract** where modules still read them; prefer secret stores over long-lived env secrets in multi-tenant hosts.

### 3.3 Composition rules for multi-service nodes

| Rule | Rationale |
|---|---|
| One **kit state root** per node identity (`~/.ipfs_kit` or explicit `--data-dir`) | Avoids interleaved PID files, backend docs, and lightweight JSON stores |
| Kubo repo stays under `IPFS_PATH` (`~/.ipfs`) | Content-addressed Kubo state must not be deleted as “kit cache” |
| Iroh instances own private `data/`, `staging/`, `run/`, `logs/`, `receipts/` trees | Normative Iroh security: no multi-writer shared instance dirs |
| Backend YAML holds **types and non-secret params**; credentials use refs or secret managers | Redaction and fail-safe logging depend on this split |
| Do not start daemons during backend **type validation** | Side-effect-free registry invariant |
| Binary install remains **explicit opt-in** | See [§8](#8-binary-install-policy-explicit-opt-in) |

---

## 4. State roots and directory map

```text
  Host filesystem
  ├── ~/.ipfs_kit/                          # Kit state root (default)
  │   ├── config.yaml                       # Thin / dashboard config
  │   ├── backends/<name>.yaml              # Named backend documents (0o600)
  │   ├── credentials.json                  # CredentialManager file store (if used)
  │   ├── secrets/                          # EnhancedSecretManager
  │   │   ├── secrets.enc.json              # Encrypted Secret payload (0o600)
  │   │   ├── metadata.json                 # Secret metadata (0o600)
  │   │   └── audit.log                     # Access audit (restricted)
  │   ├── .keyring/                         # SecureConfigManager (0o700)
  │   │   ├── master.key                    # Fernet key material (0o600)
  │   │   └── salt                          # PBKDF2 salt (0o600)
  │   ├── backend_configs/                  # StateService lightweight configs
  │   ├── buckets.json / pins.json          # StateService operational JSON
  │   ├── cache/                            # Default HLA disk cache path
  │   ├── journal/                          # Filesystem journal default base
  │   ├── bucket_tiering.duckdb             # Optional tiering state
  │   ├── mcp_<port>.pid / mcp_<port>.log   # CLI dashboard MCP child
  │   └── dashboard.pid                     # Compatibility PID name
  ├── ~/.ipfs/                              # Kubo repo (IPFS_PATH) — NOT kit root
  │   ├── identity                          # Node identity (Secret)
  │   ├── config                            # Kubo config
  │   └── cluster_secret                    # Cluster shared secret if present
  ├── $IPFS_KIT_BIN_DIR or package bin/     # Managed Kubo (and related) binaries
  └── Iroh instance root (configured)       # data/, staging/, run/, logs/, receipts/
      └── .ipfs-kit-iroh-install.json       # Install receipt (with binary)
```

**Critical separation:** `~/.ipfs_kit` ≠ `~/.ipfs`. Backup, wipe, and migration tools must treat them as independent failure domains.

---

## 5. State family catalog

Each subsection satisfies the six required fields.

### 5.1 Kit state root

| Field | Detail |
|---|---|
| **Owner** | Operator and kit processes (`cli.py`, `BackendManager`, `StateService`, MCP dashboard child). No single exclusive lock across all subtrees. |
| **Location rule** | Default `~/.ipfs_kit`. Override with CLI `--data-dir` (and operator env such as `IPFS_KIT_DATA_DIR` where wired). Do not point at `IPFS_PATH`. |
| **Permissions** | Prefer directory mode `0700` on multi-user hosts; individual secret files `0600`. Root creation often uses `mkdir(parents=True, exist_ok=True)` without tightening — operators should harden. |
| **Lifecycle** | Created on first write (config, backend, MCP start, StateService). Survives process exit. Destroy only with explicit operator action after stopping daemons and rotating credentials. |
| **Failure behavior** | Missing root is recreated on demand. Shared multi-writer mounts are unsupported for concurrent mutators. |
| **Safe diagnostics** | List top-level names and sizes; report `data_dir_exists` via `StateService.get_system_status()`. Never `cat` credentials, secrets, keyring, or raw backend YAML into tickets. |

### 5.2 Main configuration document (`config.yaml`)

| Field | Detail |
|---|---|
| **Owner** | `ipfs_kit_py/config.py` (`get_config` / `save_config`); HLA may load the same path among discovery candidates; dashboard JSON helpers. |
| **Location rule** | `~/.ipfs_kit/config.yaml` for thin API; HLA also probes cwd and `/etc/ipfs_kit/`. |
| **Permissions** | Not always chmod’d by thin `config.py`. If the file holds secrets, use `SecureConfigManager` (0o600) or move secrets out. |
| **Lifecycle** | Optional; empty/missing → defaults. Update via API/dashboard; prefer backup before bulk replace. |
| **Failure behavior** | HLA: parse errors → warning + defaults. Thin save creates parent dir. No transactional multi-file commit with backends. |
| **Safe diagnostics** | Dump non-secret keys only; use redacting loaders. Prefer schema/key lists over full file paste. |

### 5.3 Named backend documents

| Field | Detail |
|---|---|
| **Owner** | `BackendManager` (`backend_manager.py`) + type plugins in `BackendTypeRegistry` (`backend_registry.py`). CLI `backend` family and MCP backend handlers call this plane. |
| **Location rule** | `{ipfs_kit_path}/backends/{name}.yaml` with `ipfs_kit_path` default `~/.ipfs_kit`. Name validation via `validate_backend_name`. |
| **Permissions** | Atomic write: temp file `fchmod 0o600`, `os.replace`, then `chmod 0o600` on final and `.bak` after migrate. |
| **Lifecycle** | `create_backend` → `update_backend` / `migrate_backend` (backup `.bak`) → `remove_backend`. Validation/migration is side-effect-free (no daemon start). Live adapters created only via `get_backend_adapter` / filesystem factory. |
| **Failure behavior** | Structured `{error, code}` for exists/unknown type/invalid document. Partial temp files cleaned on write exception. Health probes receive unredacted config in-process but return redacted results. |
| **Safe diagnostics** | `list_backends` / `show_backend` / `get_backend_info` with default **redaction**. Sensitive keys match `_SENSITIVE_RE` (secret, token, ticket, password, private key, write capability, credential, authorization, api/access key). Secret refs become `secretref:<provider>:<redacted>`. |

### 5.4 Credential store (`CredentialManager`)

| Field | Detail |
|---|---|
| **Owner** | `credential_manager.py`; consumers include migration tools and storage backends that request named credentials. |
| **Location rule** | Default file path `~/.ipfs_kit/credentials.json` when `credential_store=file`. Preferred store is OS **keyring** (`credential_store=keyring`); falls back to file if `keyring` package missing. Also reads Kubo identity/cluster material from `ipfs_credentials_path` default `~/.ipfs`. |
| **Permissions** | File store directory created as needed; operators must `chmod 600` on credential files (documented requirement; not always enforced in every write path). Keyring entries inherit OS secret-service ACLs. |
| **Lifecycle** | `add_*` / `get_*` / `list_credentials` (metadata without secrets) / `remove_credential`. Optional rotation interval config. Loads IPFS identity and cluster secret into the store when present on disk. |
| **Failure behavior** | Missing credential → `None` / empty list. Keyring import failure → file fallback with warning. Load errors logged without re-raising plaintext. |
| **Safe diagnostics** | Use `list_credentials` for service/name presence only. Never print `get_credential` results to shared logs. Rotate via re-add + remove; treat cluster secret and IPFS identity as **Secret** material. |

### 5.5 Enhanced secrets store

| Field | Detail |
|---|---|
| **Owner** | `EnhancedSecretManager` in `enhanced_secrets_manager.py` (+ `aes_encryption.py`). Root `migrate_secrets.py` for XOR→AES migration. |
| **Location rule** | Default `~/.ipfs_kit/secrets/` with `secrets.enc.json`, `metadata.json`, `audit.log`. |
| **Permissions** | Secrets and metadata files set to **0o600** on save. Restrict audit log to operator/security roles. |
| **Lifecycle** | `store_secret` (typed validation) → `retrieve_secret` (decrypt in memory) → rotation / migrate → delete. Prefer **AES-256-GCM**; XOR is legacy and not production-ready. |
| **Failure behavior** | Invalid type/format raises; load failures log and may leave empty store. Missing `cryptography` falls back to XOR with warnings. |
| **Safe diagnostics** | Inspect **counts**, secret types, rotation ages, and audit **event kinds** — never decrypted values. Use dry-run migration. Redact `secret_id` if it embeds service context that is sensitive in your threat model. |

### 5.6 Secure configuration keyring

| Field | Detail |
|---|---|
| **Owner** | `SecureConfigManager` (`secure_config.py`), CLI helpers in `cli_secure_config.py`. |
| **Location rule** | Config files under `data_dir` (default `~/.ipfs_kit`); key material under `data_dir/.keyring/` (`master.key`, `salt`). |
| **Permissions** | Keyring directory **0o700**; key/salt/config files **0o600**. |
| **Lifecycle** | Create cipher → encrypt sensitive fields on save → decrypt on load → `migrate_to_encrypted` → `rotate_key` (old key retained with 0o600). |
| **Failure behavior** | Without `cryptography`, encryption disabled with warning. Decrypt failures may return encrypted blobs as-is for non-destructive handling — treat as degraded, not as plaintext-safe. |
| **Safe diagnostics** | `get_encryption_status()`; confirm modes and presence of key files **without** dumping key bytes. |

### 5.7 StateService operational JSON

| Field | Detail |
|---|---|
| **Owner** | `services/state_service.py` — lightweight CLI/MCP parity façade (not the full content-plane authority). |
| **Location rule** | `data_dir` default `~/.ipfs_kit`: `backend_configs/`, `buckets.json`, `pins.json`. Distinct from `BackendManager`’s `backends/*.yaml` (two backend config layouts coexist — **U-13**). |
| **Permissions** | Directory created with default umask; tighten on multi-user hosts. JSON writes are simple `write_text` (not the same atomic 0o600 path as backend YAML). |
| **Lifecycle** | Ensure structure → list/create buckets and pins → service list/control for daemons via detectors. |
| **Failure behavior** | Missing JSON → defaults; service control failures return structured messages. Daemon start may depend on external binaries (subject to install policy). |
| **Safe diagnostics** | `get_system_status` / `get_system_overview` (disk usage, data_dir existence, service summaries). Avoid dumping full backend_configs if they embed credentials. |

### 5.8 MCP dashboard PID and logs (CLI `ipfs-kit mcp`)

| Field | Detail |
|---|---|
| **Owner** | `cli.py` FastCLI MCP start/stop/status — **not** the packaged `ipfs-kit-mcp` MCP++ server process model. |
| **Location rule** | `{data_dir}/mcp_{port}.pid`, `mcp_{port}.log`; compatibility `dashboard.pid`. Default data_dir `~/.ipfs_kit`. Port default **8004**. |
| **Permissions** | PID/log files inherit process umask; protect data_dir. |
| **Lifecycle** | Start writes PID (foreground or detached child re-entry); stop signals PID and unlinks file; status reads PID. |
| **Failure behavior** | Missing PID → not running; stale PID may need manual cleanup after crash. |
| **Safe diagnostics** | Report pid, port, log path tail with **secret scrubbing**. Do not attach full logs from environments that print tokens. |

### 5.9 Packaged MCP++ process state

| Field | Detail |
|---|---|
| **Owner** | `ipfs-kit-mcp` → `mcp_server.server:main`; process **is** the server (no separate PID file by default). Coordination/receipt stores per MCP++ profile modules. |
| **Location rule** | Transport defaults: stdio or HTTP `127.0.0.1:8004`. Durable coordination paths are profile-configured (see MCP control-plane guide). |
| **Permissions** | Host-local stdio is the default trust model; HTTP bind beyond loopback expands trust boundary (**U-13** / MCP guide). |
| **Lifecycle** | Process start owns Trio event loop; shutdown on signal/stdin close. Receipts fail-closed on integrity errors. |
| **Failure behavior** | Tool/backend absence degrades per tool; receipt read failures do not invent success. |
| **Safe diagnostics** | Tool registry health, transport bind, redacted error codes. Never log credential arguments from tools. |

### 5.10 Kubo repository (`IPFS_PATH`)

| Field | Detail |
|---|---|
| **Owner** | Kubo `ipfs` process; kit managers (`kubo_runtime.py`, `daemon_config_manager.py`, `ipfs_daemon_manager.py`) start/stop/status. |
| **Location rule** | Default `~/.ipfs`; override `IPFS_PATH`. **Never** place kit backends or secrets here as the primary kit root. |
| **Permissions** | Kubo-managed; identity and private keys are **Secret**. Cluster secret file is **Secret**. |
| **Lifecycle** | `ipfs init` / managed install → daemon run → optional upgrade (gated) → stop. Repo survives kit uninstall. |
| **Failure behavior** | Missing binary with install disabled → no auto-download; operations fail with clear missing-binary errors. Corrupt repo is Kubo’s recovery domain. |
| **Safe diagnostics** | `ipfs id` public peer id, repo stat, API reachability. Do not export `identity` or `cluster_secret`. |

### 5.11 Managed binary directory

| Field | Detail |
|---|---|
| **Owner** | `kubo_runtime.managed_bin_dir`, installers (`install_ipfs`, Lotus/Storacha/Iroh install CLIs), `setup.py` gated helper. |
| **Location rule** | `IPFS_KIT_BIN_DIR` if set; else package-local `ipfs_kit_py/bin` for Kubo resolution. Iroh install lifecycle documents default `~/.local/share/ipfs_kit_py/bin` with `--bin-dir` override. |
| **Permissions** | Writable by installing user; executables executable by owner. |
| **Lifecycle** | **Opt-in install/update** → inspect/digest check → rollback (Iroh) → optional removal. Import must not download. |
| **Failure behavior** | Install disabled → return existing binary or `None`. Install errors logged as warnings; callers degrade. Concurrent Iroh updates refused by lock file. |
| **Safe diagnostics** | Path, version, digest/receipt checks (`ipfs-kit-iroh inspect --check`). Never run an arbitrary PATH binary without receipt verification for managed Iroh. |

### 5.12 Iroh instance trees and install receipts

| Field | Detail |
|---|---|
| **Owner** | Iroh service supervisor (`iroh` service modules), `ipfs-kit-iroh*` CLIs; normative contracts under `docs/iroh/`. |
| **Location rule** | Configured instance root with private `data/`, `staging/`, `run/` (PID receipt JSON), `logs/`, `receipts/`. Install receipt `.ipfs-kit-iroh-install.json` beside managed binary. |
| **Permissions** | Directories **0700**, managed files **0600** per Iroh security baseline. Dedicated unprivileged service account recommended. |
| **Lifecycle** | Verified install → start (idempotent, readiness probe) → stop/restart → update with single previous generation → rollback → crash-loop clear only when stopped. |
| **Failure behavior** | Foreign PID never signalled; crash-loop protection after repeated startup failures; atomic restore on failed update. |
| **Safe diagnostics** | `status()` liveness/readiness, digests, redacted crash receipts, readiness probes. No tickets, write capabilities, or node private identity in dumps. See `docs/iroh/security.md`. |

### 5.13 Filesystem journal and cache

| Field | Detail |
|---|---|
| **Owner** | `filesystem_journal.py` (default base `~/.ipfs_kit/journal`); HLA/cache managers (default cache under `~/.ipfs_kit/cache`). Content/WAL authority: content-metadata guide. |
| **Location rule** | Under kit state root unless overridden. Keep on local filesystem with free space. |
| **Permissions** | Operator-controlled; treat journal as integrity-sensitive, not world-readable. |
| **Lifecycle** | Init journal → append operations → checkpoint → recovery on restart. Cache is rebuildable/evictable. |
| **Failure behavior** | Journal exists to make partial VFS mutations recoverable; details in [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md). |
| **Safe diagnostics** | Journal ids, sizes, last checkpoint time — not full entry payloads if they embed paths tied to secret content. |

### 5.14 Cluster coordination state and secrets

| Field | Detail |
|---|---|
| **Owner** | Cluster modules (`cluster_state*.py`, cluster daemon managers); secrets may appear via `cluster_secret` under Kubo path and `DaemonConfigManager` config. |
| **Location rule** | Bespoke cluster state paths vary by stack (**U-08** / cluster guide). Cluster secret often `IPFS_PATH/cluster_secret`. |
| **Permissions** | Cluster secret is **Secret** — 0600, never commit. |
| **Lifecycle** | Membership/role updates, state sync, secret rotation (operational procedure). |
| **Failure behavior** | Partition/recovery per cluster guide; auth failures must fail closed for privileged ops. |
| **Safe diagnostics** | Peer ids, role, health — never raw cluster secret or mTLS private keys. |

### 5.15 Daemon configuration artifacts

| Field | Detail |
|---|---|
| **Owner** | `DaemonConfigManager` (`daemon_config_manager.py`); CLI daemon/services commands; legacy `IPFSKitDaemon` config_dir default `/tmp/ipfs_kit_config` on `ipfs-kit daemon start` (compatibility — do not use tmp for production secrets). |
| **Location rule** | Uses `IPFS_PATH`, `IPFS_KIT_BIN_DIR`, and kit instance linkage. Legacy daemon config_dir is a separate historical path. |
| **Permissions** | Production daemon config must not live on shared `/tmp` with secrets. |
| **Lifecycle** | `check_daemon_configuration` → `configure_daemon` → `start_daemon` / stop via managers. Auto-install only if `IPFS_KIT_AUTO_INSTALL_BINARIES` truthy. |
| **Failure behavior** | Missing binary without opt-in → configuration check fails soft with actionable message. |
| **Safe diagnostics** | Ports, binary path presence, API reachability; redact `cluster_secret` fields in dumps. |

### 5.16 Agent-supervisor / coordination receipts

| Field | Detail |
|---|---|
| **Owner** | MCP++ receipt modules (`agent_supervisor_receipts` and related durable stores). |
| **Location rule** | Profile-configured durable paths; integrity-checked blobs. |
| **Permissions** | Restrict to control-plane operator account. |
| **Lifecycle** | Write on coordination events → fail-closed read → retention per ops policy. |
| **Failure behavior** | Corrupt/missing integrity → fail closed (no synthetic success). |
| **Safe diagnostics** | Receipt ids, status codes, hashes — not embedded secrets or full untrusted payloads. |

---

## 6. Credentials, secret references, and redaction

### 6.1 Preferred storage hierarchy

| Preference | Mechanism | Notes |
|---|---|---|
| 1 (best) | External secret manager / KMS with **references only** in config | Iroh: `credential://iroh/<id>`, backends: `secretref:<provider>:<id>` |
| 2 | OS keyring via `CredentialManager` | Avoids long-lived plaintext files |
| 3 | `EnhancedSecretManager` AES-GCM under `~/.ipfs_kit/secrets` | Encrypted at rest; audit log |
| 4 | `SecureConfigManager` encrypted fields | For config documents that still embed sensitive keys |
| 5 (last resort) | File credentials JSON with **0o600** | Convenient; higher disclosure risk |
| Avoid | Inline secrets in git, docs, examples, process titles, URLs, crash reports | Documentation contract |

Production credential-backend choice among these options remains **unresolved** at the ADR level (**U-13** / planned ADR-0007). The hierarchy above is the operational recommendation consistent with code and Iroh security docs.

### 6.2 Secret reference rules

1. Persist **references**, not resolved values, in backend YAML and Iroh service config.  
2. Resolve only at the adapter/service boundary immediately before use.  
3. Never write resolved secrets back to config, receipts, recovery manifests, or logs.  
4. Redaction keeps `secretref` **provider** visible for diagnostics but redacts the identifier: `secretref:<provider>:<redacted>`.  
5. Separate node identity, write capability, and read ticket authorities (Iroh). Rotating one does not rotate others.

### 6.3 What counts as a Secret

Treat as **Secret** (non-exhaustive): API tokens, access/secret keys, passwords, bearer tokens, private keys, Iroh tickets and write capabilities, Kubo identity private material, cluster secrets, Fernet/AES master keys, encryption salts when combined with keys, OAuth client secrets.

Safe to log when policy allows: public peer/node ids, namespace ids used as public aliases, backend **type** and non-sensitive options, redacted health structs, binary digests, ports, bind addresses.

### 6.4 Logging and support-bundle rules

| Allowed | Forbidden |
|---|---|
| Redacted backend documents | Raw `credentials.json` / `secrets.enc.json` contents |
| Encryption status flags | `master.key` bytes |
| Service up/down and PIDs | Cluster secret, IPFS identity file |
| Exception types and codes | Exception messages that echo tokens |
| Install receipts (version, digest, path) | Pasting live tickets into chat/tickets |

---

## 7. Trust boundaries

```text
  [Untrusted network peers / remote HTTP clients / public relays]
              │
              │  expand only with authn/z + hardened bind
              ▼
  ┌──────────────────────── Host trust boundary ────────────────────────┐
  │  Control plane          Local state                 Secret plane      │
  │  CLI / MCP++ / lib  →   ~/.ipfs_kit trees      →   keyring/secrets    │
  │  (stdio default)        backends, PIDs, logs        credential stores │
  │         │                        │                         │          │
  │         └──────── resolve refs ──┴── in-memory only ───────┘          │
  │                              │                                        │
  │                              ▼                                        │
  │                     Data-plane adapters                               │
  │                     Kubo / Iroh / S3 / Cluster                        │
  └───────────────────────────────────────────────────────────────────────┘
```

| Boundary | Default posture | Elevation risk |
|---|---|---|
| Import / library | No network install; no daemon start unless asked | Caller grants filesystem/network via its process |
| MCP stdio | Trusted local agent host | Compromised agent = full tool authority |
| MCP HTTP loopback | Local multi-client | Other local users/processes |
| MCP HTTP non-loopback | **Unresolved** production authn/z (**U-13**) | Internet exposure without auth is unsafe |
| P2P / remote backends | Untrusted peers / third-party stores | Capability and credential scope must be least privilege |
| Multi-tenant shared state root | Unsupported | Cross-user secret disclosure |

---

## 8. Binary install policy (explicit opt-in)

**Invariant:** Binary installation is an **explicit opt-in**. Importing `ipfs_kit_py`, running ordinary CLI commands, and default package setup must **not** download Kubo/Iroh/Lotus binaries unless the operator enables installation.

| Control | Default | Source |
|---|---|---|
| `IPFS_KIT_AUTO_INSTALL_BINARIES` | **Off** (falsy) | `setup.py`, `kubo_runtime.ensure_kubo_binary`, `daemon_config_manager`, package `__init__` narrative |
| `IPFS_KIT_AUTO_UPGRADE_KUBO` | On only when install path is already enabled | `kubo_runtime.py` |
| Iroh CLI install/update | Explicit `ipfs-kit-iroh install|update` | `docs/iroh/install-lifecycle.md` |
| Documentation / CI validation | Set `IPFS_KIT_AUTO_INSTALL_BINARIES=0` | Documentation plan |

**Operator enablement (example):**

```bash
# Opt in only when you intend package-managed downloads
export IPFS_KIT_AUTO_INSTALL_BINARIES=1
export IPFS_KIT_BIN_DIR="$HOME/.local/share/ipfs_kit_py/bin"

# Or use explicit Iroh lifecycle without global auto-install
ipfs-kit-iroh install --version <pinned> --check
```

**Failure when not opted in:** managers return missing binary / skip install; features that require the binary degrade or error with an actionable message. They must not hang on network download.

Older docstrings or historical guides that imply import-time install are **stale** relative to this policy (see source-of-truth map gap on install narrative).

---

## 9. Process lifecycle ownership

| Process / resource | Owner | Start | Readiness | Stop / update |
|---|---|---|---|---|
| Short-lived CLI | `ipfs-kit` process | `sync_main` / anyio command | Command completes | Process exit |
| MCP++ server | `ipfs-kit-mcp` process | `anyio.run` trio backend | Transport accept / tool registry loaded | Signal / stdin EOF |
| CLI dashboard MCP child | Parent CLI + child Python | `mcp start` writes PID | HTTP listen on port | `mcp stop` / signal PID |
| Library in caller | Caller process | Import lazy; kit construct | Caller-defined | Caller calls stop/teardown |
| Kubo daemon | External OS process | Daemon managers / `ipfs daemon` | API endpoint | `ipfs shutdown` / manager stop |
| Iroh sidecar | `IrohService` supervisor | Idempotent start + RPC probe | `ready` vs `running` | Graceful then forced; crash-loop guard |
| Managed binaries | Install CLIs / opt-in setup | Explicit install | Digest + `--version` | Update/rollback with locks |

Detailed per-entry matrices live in [`RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md). Iroh-specific lifecycle: `docs/iroh/service-lifecycle.md`, `install-lifecycle.md`.

### 9.1 Health and observability

| Signal | Safe to expose | Notes |
|---|---|---|
| Process liveness (PID alive) | Yes | May be live but not ready (Iroh) |
| Readiness (RPC/API up) | Yes | Prefer for routing |
| Backend `health()` redacted | Yes | Uses redaction helper |
| Disk free on data_dir | Yes | `StateService.get_system_status` |
| Secret rotation due flags | Metadata only | No secret values |
| Full config / env dumps | **No** by default | High leak risk |

---

## 10. Failure behavior and recovery (operator summary)

| Scenario | Behavior | Recovery guidance |
|---|---|---|
| Missing kit state root | Recreated on demand | Safe; re-add backends/credentials |
| Corrupt backend YAML | Validation error codes | Restore `.bak` if present; re-validate |
| Missing credential | Operation fails for that backend | Re-add via CredentialManager/env; do not “guess” from logs |
| Lost encryption master key | Cannot decrypt secure config/secrets | Restore key from offline backup or re-provision secrets |
| Stale MCP PID file | Stop/status confusing | Confirm process; delete PID if dead |
| Missing Kubo binary, install off | No download | Install OS package or opt-in managed install |
| Iroh crash loop | Starts refused | Clear only when stopped; inspect `receipts/crash.json` redacted |
| Partial journal write | Content-plane recovery path | Follow [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md) |
| Receipt integrity failure | Fail closed | Do not trust partial coordination state |

---

## 11. Safe diagnostic runbook

Use this sequence offline first (`IPFS_KIT_AUTO_INSTALL_BINARIES=0`).

1. **Identify state roots** in use: kit `--data-dir` / `~/.ipfs_kit`, `IPFS_PATH`, Iroh instance root, `IPFS_KIT_BIN_DIR`.  
2. **Process map:** which of CLI, MCP++, Kubo, Iroh are expected; check PIDs and readiness separately.  
3. **Backend plane:** `list`/`show` backends with redaction; validate schemas without starting daemons.  
4. **Credential plane:** list **names** only; verify keyring/file mode `600` where file-based.  
5. **Secret plane:** encryption method AES vs XOR; audit log presence; never decrypt into shared notes.  
6. **Binary plane:** path exists, executable bit, Iroh receipt digest match.  
7. **Logs:** scrub with sensitive-key awareness before attach.  
8. **Escalate** with redacted bundles only.

**Do not** run undocumented “dump everything under `~/.ipfs_kit`” scripts into tickets.

---

## 12. Unresolved owner decisions

| ID | Topic | Why open | Follow-up |
|---|---|---|---|
| **U-13** | Config/state directory composition and MCP HTTP authn/z | Multiple managers and state layouts coexist | ADR-0007 + MCP/ops hardening |
| **U-08** | Cluster control-plane authority | Parallel cluster stacks | Cluster guide + ADR-0008 |
| Credential backend production default | Keyring vs encrypted file vs external KMS | All exist; no single enforced default | ADR-0007 |
| Dual backend config trees | `backends/*.yaml` vs `backend_configs/` | StateService vs BackendManager | Storage + trust ADR follow-up |
| Legacy daemon `/tmp` config | Historical CLI path | Unsafe for secrets | Compatibility layers + CLI cleanup (code task) |

This guide does **not** close these decisions.

---

## 13. Change triggers and last-verified baseline

Re-verify this document when any of the following change:

- Default paths or permissions for kit root, backends, secrets, keyring, journal, cache  
- `IPFS_KIT_AUTO_INSTALL_BINARIES` / `kubo_runtime` / setup install gates  
- `redact_backend_config` / `_SENSITIVE_RE` semantics  
- Credential or enhanced secret storage formats  
- MCP PID layout or MCP++ default bind  
- Iroh security/install/service lifecycle contracts  
- HLA config discovery order or precedence  

**Baseline:** repository inspection 2026-08-03; tree `5a2d23561ae515c732f47534e3afba3af636284f`; packaging `0.3.0`.

---

## 14. Tests and evidence anchors

| Area | Paths / tests |
|---|---|
| Backend atomic write + redaction | `backend_manager.py`, `backend_registry.py`; backend unit tests |
| Secure config | `tests/test_secure_config.py`, `tests/unit/test_secure_config.py`, `tests/unit/test_config_save.py` |
| Daemon config | `tests/test_daemon_config*.py`, `tests/test_enhanced_daemon_config.py` |
| AES / secrets | `tests/unit/test_aes_encryption.py`; enhanced secrets manager + `migrate_secrets.py` |
| Iroh security/config | `tests/test_iroh_security.py`, `tests/test_iroh_config.py`, install lifecycle tests |
| Service configuration | `tests/test_service_configuration.py` |
| Import / no surprise install | `tests/test_ipfs_kit_import.py` and packaging narratives with auto-install off |
| Operator docs (non-architecture) | `docs/credential_management.md`, `docs/guides/SECURE_CREDENTIALS_GUIDE.md`, `docs/features/ENCRYPTED_CONFIG_GUIDE.md`, `docs/iroh/*` |

Offline validation for this task:

```bash
test -s docs/architecture/CONFIGURATION_STATE_AND_TRUST.md && rg -q "Secret" docs/architecture/CONFIGURATION_STATE_AND_TRUST.md
```

---

## 15. Related reading order

1. [`SYSTEM_OVERVIEW.md`](./SYSTEM_OVERVIEW.md) — context and trust overview  
2. **This guide** — state families, secrets, install policy  
3. [`RUNTIME_AND_ENTRYPOINTS.md`](./RUNTIME_AND_ENTRYPOINTS.md) — process ownership detail  
4. [`CONTENT_METADATA_VFS.md`](./CONTENT_METADATA_VFS.md) — durable content-plane state  
5. [`MCP_CONTROL_PLANE.md`](./MCP_CONTROL_PLANE.md) — control-plane receipts and surfaces  
6. `docs/iroh/security.md` + lifecycle runbooks — Iroh production hardening  
7. Planned ADR-0007 — formal configuration/secret composition decision  

---

*End of KDOC-019 configuration, state, credentials, trust, and process lifecycle guide.*
