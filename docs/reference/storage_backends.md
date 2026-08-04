# Storage backends reference

- Status: current operator/reference guide (KDOC-034)
- Authority class: Reference (implementation-aligned; not a normative runtime contract)
- Architecture guide: [STORAGE_BACKEND_SYSTEM.md](../architecture/STORAGE_BACKEND_SYSTEM.md)
- Trust / secrets guide: [CONFIGURATION_STATE_AND_TRUST.md](../architecture/CONFIGURATION_STATE_AND_TRUST.md)
- Iroh named backends: [named-backends.md](../iroh/named-backends.md)
- Baseline: code inspection of `backend_registry.py`, `backend_manager.py`,
  `iroh/backend.py`, and `backends/`

This page catalogs **what is registered today**, how **schema-validated** types
differ from **legacy** types, how named configuration is stored, and which live
adapters exist. It replaces older marketing-style claims (for example “six
production backends fully operational”) with inventory grounded in the type
registry and package adapters.

> **Security:** Never put live tokens, keys, passwords, node identities, or write
> capabilities into docs, tickets, or examples. Prefer
> `secretref:<provider>:<id>` or environment-variable *names*. Placeholders such
> as `YOUR_TOKEN` are intentionally invalid.

---

## 1. Three layers (do not conflate)

| Layer | What it is | Primary modules | Side effects? |
|---|---|---|---|
| **Type plugin** | Configuration behavior for a backend *type* | `ipfs_kit_py/backend_registry.py`, type-specific plugins (e.g. `ipfs_kit_py/iroh/backend.py`) | No — discovery, validate, migrate, describe, redact must stay inert |
| **Named document** | Persisted YAML for one operator-named backend | `ipfs_kit_py/backend_manager.py` → `~/.ipfs_kit/backends/<name>.yaml` | Disk write of config only; no secret resolution into live sessions |
| **Live adapter** | Runtime client that performs storage I/O | `ipfs_kit_py/backends/*`, `iroh_fsspec.IrohFileSystem`, various `*_kit` modules | Yes — only after explicit construction |

```text
BackendTypeRegistry  →  named YAML document  →  live adapter / filesystem
   (plugins)               (BackendManager)        (backends/*, Iroh FS, kits)
```

**Invariant:** importing the registry, listing types, validating a document, or
showing a redacted config must never start a daemon, open an RPC session, or
materialize secret values.

Vocabulary: [GLOSSARY.md](../architecture/GLOSSARY.md) (**Backend**, **Adapter**,
**Registry**). Candidate authorities: [SOURCE_OF_TRUTH_MAP.md](../architecture/SOURCE_OF_TRUTH_MAP.md) §2.

---

## 2. Schema-validated vs legacy plugins

Every registered type is a `BackendPlugin`. The registry’s `describe()` marks
`schema_validated: True` when `plugin.schema_version is not None`.

| Property | Schema-validated | Legacy (`LegacyBackendPlugin`) |
|---|---|---|
| Built-in types today | **`iroh` only** (`schema_version: 1`) | 21 names in `BackendTypeRegistry.LEGACY_TYPES` |
| Closed field set | Yes (unknown keys rejected) | No — JSON-compatible object + `name` + matching `type` |
| `schema()` | JSON Schema resource | `None` |
| Secret policy in YAML | Approved `secretref:…` only (Iroh) | May historically contain inline fields; **redacted** on public APIs |
| Default `capabilities()` | Reflects document (access, protocols, sync) | `{"named": True, "schema_validated": False}` |
| Default `health()` | Structured (Iroh: local endpoint existence without full RPC) | `{"healthy": None, "status": "not-probed", "enabled": …}` |
| Adapter factory on plugin | Iroh: lazy `create_filesystem` | Not part of the legacy plugin |

**Registration facts (built-in, `load_entry_points=False`):**

- Total types: **22** (21 legacy + `iroh`).
- Entry-point group for third-party plugins: `ipfs_kit.backends`
  (`BACKEND_ENTRY_POINT_GROUP`). Broken third-party loaders are skipped so
  built-ins remain usable.
- Installed environments may show additional types via entry points; always
  check `BackendTypeRegistry.types()` / `describe()` at runtime.

---

## 3. Registered type inventory

### 3.1 Schema-validated: `iroh`

| Field | Value |
|---|---|
| Plugin | `ipfs_kit_py.iroh.backend.IrohBackendPlugin` |
| Schema version | `1` |
| Machine schema | `ipfs_kit_py/resources/iroh-backend-config.schema.json` |
| Secret-free example | `config/iroh-backend.example.yaml` |
| Runtime FS | `ipfs_kit_py.iroh_fsspec.IrohFileSystem` (lazy client) |
| Operator guide | [docs/iroh/named-backends.md](../iroh/named-backends.md) |

**Version-1 document shape (conceptual; use the example file for copy-paste):**

| Section | Role |
|---|---|
| `schema_version`, `name`, `type`, `enabled` | Identity and enablement (`type` must be `iroh`) |
| `namespace.id` | Lowercase 32-byte hex Iroh namespace ID |
| `namespace.access` | `read-only` or `read-write` |
| `service.instance` | Named Iroh instance id |
| `service.managed` | Whether kit manages the service lifecycle |
| `service.rpc_endpoint` | **Local only**: absolute `unix:///…` socket or Windows named pipe |
| `credentials.*_ref` | Secret **references** only (see §5) |
| `timeouts.*` | Connect / operation / shutdown seconds (finite, ≤ 3600) |
| `sync.*` | Sync enablement, on-open, `local`/`synchronized` reads, `conflict_policy: fail` |

**Credentials fields (refs only):**

- Required: `node_key_ref`
- Required when `access` is `read-write`: `write_capability_ref`
- Optional: `read_ticket_ref`

Approved reference form:

```text
secretref:<provider>:<id>
```

Providers accepted by Iroh validation:

- `secure-config`
- `enhanced-secrets`
- `credential-manager`
- `environment`

**Capabilities (config-derived, not a network probe):** protocols
`iroh` / `iroh+blob`; `read` always; `write` / `delete` / `copy` / `move` /
`transactions` when access is read-write; `async`, `immutable_blobs`; `sync`
from the document’s sync block.

**Default health:** if disabled → `status: disabled`, `ready: False`; else
checks local Unix socket existence (named-pipe path is conservative on Windows).
Does **not** start the Iroh service.

**Migration:** flat legacy Iroh fields (`namespace_id`, `rpc_endpoint`,
`node_key_ref`, …) migrate to nested v1. Migration never invents secrets and
rejects inline secret material. CLI: `ipfs-kit-backend-migrate` (see
`backend_migration.py`).

### 3.2 Legacy type names

Registered for named-document compatibility. **Being listed does not imply** a
complete live adapter, closed schema, production SLA, or every historical kit
capability.

| Type | Typical intent | Live adapter in `backends/` package factory? | Notes |
|---|---|---|---|
| `ipfs` | Kubo / IPFS API endpoint | Yes → `IPFSBackendAdapter` | Parallel top-level `ipfs_backend.py` also exists (compatibility; factory authority unresolved) |
| `filesystem` | Local filesystem paths | Yes → `FilesystemBackendAdapter` | |
| `sshfs` | Remote FS via SSHFS-style config | Alias → `FilesystemBackendAdapter` | Also has dashboard fields in `backend_schemas.py` |
| `s3` | S3-compatible object storage | Yes → `S3BackendAdapter` | Common archival tier; kits may use env/`CredentialManager` |
| `minio` | MinIO (S3 API) | Alias → `S3BackendAdapter` | |
| `digitalocean` | DigitalOcean Spaces (S3 API) | Alias → `S3BackendAdapter` | |
| `storacha` | Web3.Storage / Storacha | **No** package factory entry | Kit modules (`storacha_kit`, enhanced kits) and MCP-era managers exist; prefer env/secret stores over YAML secrets |
| `filecoin` | Filecoin / Lotus-oriented storage | **No** | Often pairs with Lotus RPC; credentials via manager/env |
| `filecoin_pin` | Filecoin pin-oriented path | **No** | Compatibility name |
| `huggingface` | Hugging Face Hub datasets/models | **No** | Token via env (`HF_TOKEN` / `HUGGINGFACE_TOKEN`) or secret store |
| `lassie` | Retrieval client (Lassie) | **No** | Often retrieval-only; no secret fields in dashboard schema |
| `ipfs_cluster` | IPFS Cluster API | **No** | Cluster secret is highly sensitive — never log |
| `cluster` | Generic/cluster alias | **No** | Distinct name from `ipfs_cluster` |
| `github` | GitHub-backed backup/sync (policy examples) | **No** | Token must not be committed |
| `gdrive` | Google Drive | **No** | Usually credentials **path** or OAuth store, not inline secrets in docs |
| `ftp` | FTP/FTPS archive | **No** | Prefer secret refs if adding a closed schema later |
| `parquet` | Columnar local/object layouts | **No** | More data-format oriented than network storage |
| `local`, `local_fs`, `local_storage` | Local path variants | Overlap with `filesystem` | Prefer `filesystem` for new named docs unless tooling requires a specific name |
| `estuary` | Historical Estuary API name | **No** | **Qualify:** Estuary service landscape has changed; treat as compatibility/legacy name, not a guaranteed live product integration |

**Dashboard field catalogs** (`backend_schemas.py`) list UI form fields for many
of the above (including password-style widgets). Those schemas are **not** the
Iroh closed schema and do **not** enforce secretref-only storage.

### 3.3 What this reference does *not* claim

Older docs and status reports sometimes asserted that IPFS, Filecoin, S3,
Storacha, HuggingFace, and Lassie were equally “production ready” multi-backend
integrations. Current code distinguishes:

1. **Registry membership** (type can be named and lightly validated) — 22 built-ins.
2. **Closed schema + secret-ref enforcement** — **Iroh only** today.
3. **Package live adapters** (`BACKEND_ADAPTERS`) — `ipfs`, `filesystem`/`sshfs`,
   `s3`/`minio`/`digitalocean`, plus manager-backed `iroh`.
4. **Historical kit modules and MCP storage managers** — still present under
   `*_kit.py`, `mcp/storage_manager/`, and archives; useful compatibility paths
   but **not** the named-config registry authority.

Saturn and similar MCP-era backends may appear under control-plane trees; they
are **not** in `LEGACY_TYPES` / built-in registry inventory above.

---

## 4. Named configuration (`BackendManager`)

**Module:** `ipfs_kit_py.backend_manager.BackendManager`

| Behavior | Detail |
|---|---|
| Root | `~/.ipfs_kit` by default (`ipfs_kit_path`) |
| Documents | `backends/<name>.yaml` |
| Name rule | `^[a-z0-9][a-z0-9_-]{0,63}$` via `validate_backend_name` |
| Create / update | Plugin `validate` then atomic write (`mkstemp` → `fchmod 0o600` → `fsync` → `os.replace` → `chmod 0o600`) |
| Public read paths | `show_backend`, `list_backends`, create/update results, `get_backend_info` → `redact_backend_config` |
| Unredacted internal | `get_backend_config(name, redact=False)` for last-moment secret resolution only |
| Capabilities | `plugin.capabilities(config)` |
| Health | Optional `health_probes[type]`; else `plugin.health`; results redacted |
| Migrate | `plugin.migrate`; `.bak` at `0o600` when rewritten |
| Iroh on read | `_normalize` uses `migrate` for `type == "iroh"` so flat YAML is readable without silent rewrite |
| Adapter | `get_backend_adapter(name)` → unredacted config → `plugin.create_filesystem(...)` (Iroh) |

List registered types:

```python
from ipfs_kit_py.backend_manager import list_supported_backends
from ipfs_kit_py.backend_registry import get_backend_type_registry

print(list_supported_backends())
print(get_backend_type_registry().describe())
```

### 4.1 Schema-validated create example (Iroh, secret-free)

Use the checked-in example document — it contains only placeholders and refs:

```python
import yaml
from pathlib import Path
from ipfs_kit_py.backend_manager import BackendManager

manager = BackendManager()  # defaults to ~/.ipfs_kit
document = yaml.safe_load(
    Path("config/iroh-backend.example.yaml").read_text(encoding="utf-8")
)
name = document.pop("name")
type_name = document.pop("type")
result = manager.create_backend(name, type_name, config=document)
# Public result redacts secretref identifiers:
# credentials.node_key_ref → secretref:enhanced-secrets:<redacted>
print(result.get("status"), result.get("backend", {}).get("credentials"))
```

### 4.2 Legacy create example (minimal, no secrets in the document)

Legacy plugins only require a JSON-compatible document with `name` and matching
`type`. Prefer **non-secret** fields in YAML; bind credentials from env or
`CredentialManager` at adapter construction time.

```python
from ipfs_kit_py.backend_manager import BackendManager

manager = BackendManager()
result = manager.create_backend(
    "archive_s3",
    "s3",
    config={
        "name": "archive_s3",
        "type": "s3",
        "enabled": True,
        # Prefer bucket/region/endpoint here — not access keys.
        "bucket": "example-ipfs-archive",
        "region": "us-east-1",
        "endpoint": "https://s3.example.invalid",
    },
)
print(result)
```

### 4.3 Redaction rules

`redact_backend_config` walks documents and redacts values whose keys match a
sensitive-name regex (`secret`, `token`, `password`, `api_key`,
`write_capability`, `credential`, `authorization`, `access_key`, …).

For strings shaped like `secretref:provider:id`, public output becomes
`secretref:provider:<redacted>` (provider remains for diagnostics).

**Do not write resolved secrets back** into YAML after in-process resolution.

---

## 5. Live adapters

### 5.1 Package factory (`ipfs_kit_py.backends`)

| Type key | Adapter |
|---|---|
| `ipfs` | `IPFSBackendAdapter` |
| `filesystem`, `sshfs` | `FilesystemBackendAdapter` |
| `s3`, `minio`, `digitalocean` | `S3BackendAdapter` |
| `iroh` | Requires a manager: `config_manager.get_backend_adapter(name)` |

```python
from ipfs_kit_py.backends import get_backend_adapter, list_supported_backends
from ipfs_kit_py.backend_manager import BackendManager

print(list_supported_backends())  # includes iroh + BACKEND_ADAPTERS keys

manager = BackendManager()
# Iroh (lazy FS; client stays None until first I/O):
fs = get_backend_adapter("iroh", "team_archive", manager)

# S3-style adapter instance (does not by itself prove credentials are configured):
s3_adapter = get_backend_adapter("s3", "archive_s3", manager)
```

`BackendAdapter` (ABC) defines async health/sync/backup-style methods. Not every
registry type has an isomorphic adapter implementation in this package.

### 5.2 Canonical Iroh construction path

1. Persist/validate named document via `BackendManager`.
2. `IrohBackendPlugin.create_filesystem` builds `IrohFileSystem` with
   `client=None` and a `client_factory` that connects on first I/O.
3. Service start/stop remains **service** ownership, not registry ownership
   (see Iroh lifecycle docs under `docs/iroh/`).

### 5.3 Parallel / compatibility surfaces (not equal defaults)

| Surface | Qualification |
|---|---|
| `EnhancedBackendManager` | Policy/dashboard-oriented parallel manager; **not** schema-validation authority |
| `backend_schemas.py` | UI field catalogs with password widgets |
| `backend_cli.py` / some MCP tools | May expect helpers not exported by current `backend_manager.py` (compatibility gap; see architecture guide) |
| Top-level `ipfs_kit_py/ipfs_backend.py` | Parallel historical IPFS adapter vs `backends/ipfs_backend.py` |
| `mcp/storage_manager/backends/*` | Control-plane era backends (Storacha, Filecoin, HF, Lassie, Saturn, …) |
| Kit modules (`s3_kit`, `storacha_kit`, `lassie_kit`, …) | Direct service clients used by older APIs and tiered-cache integrations |

---

## 6. Capabilities and health semantics

| Call | Meaning |
|---|---|
| `get_backend_capabilities(name)` | Plugin-declared feature map from **config**, not a guarantee of live connectivity |
| `get_backend_health(name)` | Optional injected probe, else plugin default; **Iroh** probes local endpoint existence; **legacy** defaults to `not-probed` |
| `get_backend_info(name)` | Redacted config + capabilities + health |

Operators who need real connectivity checks should inject `health_probes` on
`BackendManager` or use backend-specific kit health endpoints — and still redact
results before logging.

---

## 7. Configuration extras and related systems

| Concern | Where | Relation to named backends |
|---|---|---|
| Policies (quota, replication, retention, cache) | `backend_policies.py`, policy CLI guides | Orthogonal policy plane; may reference backend names |
| Tiered cache / ARC | `tiered_cache_manager.py`, cache package | May call kit clients for S3/Storacha-style external tiers |
| Content routing | `routing/` | Routes across backends; gRPC stack partially deprecated |
| Bucket / VFS | Bucket managers, VFS contracts | Logical namespaces **mapped to** backends — not backend types themselves |
| Credentials | [credential_management.md](../credential_management.md) | Secret stores and env; schema-validated YAML uses refs only |

Example policy-oriented YAML (env **names** only, no secret values):
`config/enhanced_backend_examples.yaml`. Treat it as illustrative for enhanced
manager layouts, not as the Iroh closed schema.

---

## 8. Safe operator checklist

1. Prefer **schema-validated** types for new production backends (today: **Iroh**).
2. Keep secrets out of YAML: use `secretref:…` (Iroh) or env/secret managers.
3. Confirm type maturity with `describe()` before promising features to users.
4. Use `list_backends` / `show_backend` for diagnostics — never `cat` raw YAML
   that may contain legacy inline secrets into tickets.
5. Atomic files are mode `0600`; keep `~/.ipfs_kit` owner-only on multi-user hosts.
6. Do not assume registry name ⇒ package adapter ⇒ remote service product.
7. For Iroh create/show/migrate workflows, follow
   [named-backends.md](../iroh/named-backends.md) and
   [credential-rotation.md](../iroh/credential-rotation.md).

---

## 9. Related documentation

| Doc | Role |
|---|---|
| [STORAGE_BACKEND_SYSTEM.md](../architecture/STORAGE_BACKEND_SYSTEM.md) | Canonical architecture (plugins, documents, adapters, invariants) |
| [CONFIGURATION_STATE_AND_TRUST.md](../architecture/CONFIGURATION_STATE_AND_TRUST.md) | State roots, trust, redaction, process lifecycle |
| [credential_management.md](../credential_management.md) | CredentialManager, secretref providers, safe usage |
| [docs/iroh/*](../iroh/) | Normative Iroh service, security, and filesystem contracts |
| [SOURCE_OF_TRUTH_MAP.md](../architecture/SOURCE_OF_TRUTH_MAP.md) §2 | Candidate authorities and unresolved factory decisions |

---

*End of storage backends reference (KDOC-034).*
