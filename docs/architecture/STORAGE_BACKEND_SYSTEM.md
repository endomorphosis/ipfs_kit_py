# Storage backend system

- Status: architecture guide (Wave 1)
- Task: KDOC-013
- Goal: KDOC-G022
- Authority class: Canonical (architecture; not a runtime contract)
- Baseline: repository inspection 2026-08-03
- Scope: configuration plugins, named backend documents, secret handling,
  capabilities/health, live adapters, and safe extension
- Non-goals: content/metadata/VFS/WAL durability paths (KDOC-014);
  Iroh network transport and normative service contracts (KDOC-016 /
  `docs/iroh/*`); MCP control-plane tool wiring (KDOC-017); exhaustive
  per-backend field catalogs (use schemas, fixtures, and reference docs)

This guide explains how IPFS Kit separates **backend type plugins** (side-effect-free
configuration behavior) from **named configuration documents** (persisted YAML)
and **live adapters** (runtime storage clients). Vocabulary follows
[GLOSSARY.md](./GLOSSARY.md) (**Backend**, **Adapter**, **Registry**). Candidate
authorities are mapped in [SOURCE_OF_TRUTH_MAP.md](./SOURCE_OF_TRUTH_MAP.md) §2.

---

## 1. Scope and non-goals

### In scope

| Concern | What this guide covers |
|---|---|
| Type discovery | `BackendTypeRegistry`, built-in legacy types, schema-validated plugins, optional entry points |
| Named documents | Atomic YAML under `~/.ipfs_kit/backends/`, validate/migrate/create/update/remove |
| Secrets | Secret references only for validated types; `redact_backend_config` on public results |
| Capabilities and health | Plugin methods vs optional live probes; non-probed defaults for legacy types |
| Live adapters | `backends/*` package, Iroh lazy filesystem construction, factory paths |
| Extension | How to add a schema-validated type without import-time side effects or secret leakage |

### Explicit non-goals

- Tracing bytes through caches, pins, buckets, VFS, indexes, WAL/CAR, or journals
  (owned by **KDOC-014** / `CONTENT_METADATA_VFS.md`).
- Rewriting normative Iroh contracts under `docs/iroh/` (filesystem contract,
  capability matrix, service lifecycle).
- Resolving multi-manager or multi-adapter authority conflicts into a single ADR
  (recorded as **unresolved** below; ADR work is separate).
- Inventorying every historical kit (`*Kit`), MCP storage manager, or archived
  `storage_manager` tree as production defaults.

---

## 2. Core distinction: plugin, document, adapter

Three objects are easy to conflate. Treat them as separate layers:

```text
┌──────────────────────────────────────────────────────────────────┐
│ BackendTypeRegistry  (type catalog / configuration plugins)      │
│  - discover & register plugins                                   │
│  - validate / migrate / describe / redact helpers                │
│  - MUST NOT start daemons, resolve credentials, or open I/O      │
└───────────────────────────────┬──────────────────────────────────┘
                                │ plugin.validate / migrate / schema
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Named backend document  (~/.ipfs_kit/backends/<name>.yaml)       │
│  - BackendManager CRUD, atomic write mode 0600                   │
│  - public API returns redact_backend_config(...) copies          │
│  - still configuration only until an adapter is requested        │
└───────────────────────────────┬──────────────────────────────────┘
                                │ get_backend_adapter / create_filesystem
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ Live adapter  (backends/*, IrohFileSystem, kit clients, …)       │
│  - connections, health probes that touch the network, pin sync   │
│  - constructed lazily after validation for schema-validated types│
└──────────────────────────────────────────────────────────────────┘
```

| Layer | Object | Authority path | Side effects allowed? |
|---|---|---|---|
| Type plugin | `BackendPlugin` | `ipfs_kit_py/backend_registry.py` (+ type-specific modules such as `ipfs_kit_py/iroh/backend.py`) | No — discovery and validation must stay inert |
| Named config | YAML document | `ipfs_kit_py/backend_manager.py` | Disk write of config only; no credential resolution into live sessions |
| Live adapter | Runtime client | `ipfs_kit_py/backends/`, `ipfs_kit_py/iroh_fsspec.py`, various kits | Yes — only after explicit construction |

**Invariant:** importing `backend_registry`, constructing `BackendTypeRegistry`,
listing types, validating a document, or showing a redacted config must never
start a daemon, open an RPC connection, or materialize secret values.

---

## 3. Supported and compatibility surfaces

### Canonical surfaces (prefer for new work)

| Surface | Path / entry | Role |
|---|---|---|
| Type registry | `ipfs_kit_py.backend_registry.BackendTypeRegistry` | Side-effect-free type catalog |
| Entry-point group | `BACKEND_ENTRY_POINT_GROUP = "ipfs_kit.backends"` | Optional third-party plugin load |
| Named manager | `ipfs_kit_py.backend_manager.BackendManager` | Atomic YAML CRUD + plugin delegation |
| Schema-validated Iroh plugin | `ipfs_kit_py.iroh.backend.IrohBackendPlugin` | Closed schema, secret refs, lazy FS |
| Iroh named-backend guide | `docs/iroh/named-backends.md` | Operator-facing Iroh document contract |
| Example config | `config/iroh-backend.example.yaml` | Secret-free version-1 shape |
| JSON Schema resource | `ipfs_kit_py/resources/iroh-backend-config.schema.json` | Machine schema for Iroh documents |
| Live adapter package | `ipfs_kit_py/backends/` | Isomorphic `BackendAdapter` ABC + factories |
| Iroh runtime FS | `ipfs_kit_py.iroh_fsspec.IrohFileSystem` | Lazy client; preferred Iroh adapter |

### Compatibility / parallel surfaces (do not present as equal defaults)

| Surface | Notes |
|---|---|
| `LegacyBackendPlugin` for 21 built-in type names | JSON-compatible documents only; `schema_validated: False`; no closed schema |
| `ipfs_kit_py/backends/iroh_backend.py` | Re-exports plugin + `IrohFileSystem`; construction must still go through the manager |
| `backends.get_backend_adapter(type, name, manager)` | Package factory for `ipfs` / `filesystem` / `s3` (+ aliases); Iroh branch requires a manager |
| `EnhancedBackendManager` (`enhanced_backend_manager.py`) | Policy-oriented parallel manager; may seed sample YAML; **not** the schema-validation authority |
| `backend_schemas.py` | Dashboard-oriented field catalogs with password-style fields — **not** the Iroh closed schema |
| `backend_cli.py` handlers | Historical CLI wiring; several imports expect `get_backend_manager` which is **not** exported by current `backend_manager.py` (compatibility gap) |
| Top-level `ipfs_kit_py/ipfs_backend.py` | Parallel/historical IPFS adapter path vs `backends/ipfs_backend.py` |
| MCP-era storage managers | Control-plane wiring under `mcp/` and archived trees; not the named-config registry |

### Unresolved owner decisions (do not invent a winner)

1. **Live adapter factory authority** — callers of `backends/*`, routing, kits, or a single manager API?
2. **Top-level vs package IPFS adapter** — which module is supported for new work?
3. **`get_backend_manager` callers** — intelligent daemon / MCP tools / `backend_cli.py` expect a helper that current `backend_manager.py` does not export.
4. **When legacy types gain closed schemas** — migration story beyond Iroh is incomplete.

---

## 4. Component ownership and source-of-truth paths

### 4.1 `BackendTypeRegistry` (configuration plugins)

**Module:** `ipfs_kit_py/backend_registry.py`

Responsibilities:

- Register plugins implementing the `BackendPlugin` protocol:
  `type_name`, `schema_version`, `validate`, `migrate`, `capabilities`,
  `health`, `schema`.
- Seed **legacy** types via `LegacyBackendPlugin` for each name in
  `BackendTypeRegistry.LEGACY_TYPES` (21 names).
- Directly register `IrohBackendPlugin` so source checkouts work even when
  package metadata is not rebuilt — still without starting Iroh.
- Optionally load third-party plugins from entry-point group
  `ipfs_kit.backends` (`load_entry_points=True` by default). Broken third-party
  plugins are skipped so built-ins remain usable.
- Expose `describe()` metadata including `schema_validated`
  (`plugin.schema_version is not None`).
- Provide `validate_backend_name`, `ensure_json_compatible`, and
  `redact_backend_config`.

Default process-wide accessor: `get_backend_type_registry()` (lazy singleton).
Alias: `BackendRegistry = BackendTypeRegistry` for callers that do not need the
“type registry vs live-instance registry” naming distinction.

### 4.2 Schema-validated versus legacy plugins

| Property | Schema-validated (Iroh today) | Legacy (`LegacyBackendPlugin`) |
|---|---|---|
| `schema_version` | Integer (Iroh: `1`) | `None` |
| `describe()["schema_validated"]` | `True` | `False` |
| Validation | Closed field sets, typed constraints, secret-ref rules | JSON-compatible object + `name` + matching `type` |
| `schema()` | JSON Schema document | `None` |
| `capabilities()` | Reflects access mode, protocols, sync flags | `{"named": True, "schema_validated": False}` |
| Default `health()` | Structured status (e.g. endpoint reachability **without** RPC) | `{"healthy": None, "status": "not-probed", "enabled": ...}` |
| `create_filesystem` / adapter factory | Present on Iroh plugin; lazy client | Not part of the legacy plugin |

**Built-in inventory (baseline 2026-08-03, `load_entry_points=False`):**

- **Schema-validated:** `iroh` (`schema_version: 1`).
- **Legacy type names** (`LEGACY_TYPES`):  
  `cluster`, `digitalocean`, `estuary`, `filecoin`, `filecoin_pin`,
  `filesystem`, `ftp`, `gdrive`, `github`, `huggingface`, `ipfs`,
  `ipfs_cluster`, `lassie`, `local`, `local_fs`, `local_storage`, `minio`,
  `parquet`, `s3`, `sshfs`, `storacha`.

Total registered types in a clean registry: **22** (21 legacy + Iroh).
Installed environments may add more via `ipfs_kit.backends` entry points.

### 4.3 Named configuration (`BackendManager`)

**Module:** `ipfs_kit_py/backend_manager.py`

| Behavior | Implementation detail |
|---|---|
| Root | `~/.ipfs_kit` by default (`ipfs_kit_path`) |
| Documents | `backends/<name>.yaml` where `name` matches `^[a-z0-9][a-z0-9_-]{0,63}$` |
| Create / update | Plugin `validate` then atomic write (`mkstemp` → `fsync` → `os.replace`, mode `0o600`) |
| Show / list / info | Public results pass through `redact_backend_config` |
| Internal unredacted read | `get_backend_config(name, redact=False)` for last-moment secret resolution |
| Capabilities | `plugin.capabilities(config)` using unredacted config in-process |
| Health | Optional `health_probes[type](config)` injection; else `plugin.health(config)`; results redacted |
| Migrate | `plugin.migrate`; rewrite only when changed; keeps owner-only `.bak` |
| Iroh normalize on read | `_normalize` uses `migrate` for `type == "iroh"` so flat legacy YAML is readable in memory without silent rewrite |
| Adapter construction | `get_backend_adapter(name)` → unredacted config → `plugin.create_filesystem(...)` |

Failed validation **must not** leave a partial file (create) or replace a valid
document (update). This is contract-tested for Iroh.

CLI migration entry: `ipfs_kit_py/backend_migration.py` (`ipfs-kit-backend-migrate`).
Iroh operator CLI groups under `ipfs_kit_py/iroh/cli.py` also use `BackendManager`
and redaction helpers.

### 4.4 Live adapters (`backends/`)

**Package:** `ipfs_kit_py/backends/`

| Module | Role |
|---|---|
| `base_adapter.py` | `BackendAdapter` ABC: health, pin sync, bucket/metadata backup surface |
| `ipfs_backend.py` | IPFS adapter |
| `filesystem_backend.py` | Local / SSHFS-style filesystem adapter |
| `s3_backend.py` | S3-compatible adapter |
| `real_api_storage_backends.py` | Additional real-API storage helpers |
| `iroh_backend.py` | Compatibility imports for Iroh plugin + filesystem (not a second manager) |
| `__init__.py` | `BACKEND_ADAPTERS` map + `get_backend_adapter(type, name, config_manager)` |

Package factory map (non-exhaustive of registry types):

| Type key | Adapter class |
|---|---|
| `ipfs` | `IPFSBackendAdapter` |
| `filesystem`, `sshfs` | `FilesystemBackendAdapter` |
| `s3`, `minio`, `digitalocean` | `S3BackendAdapter` |
| `iroh` | Delegates to `config_manager.get_backend_adapter(name)` — manager required |

**Iroh construction path (canonical):**

1. Validate / load named document via `BackendManager`.
2. `IrohBackendPlugin.create_filesystem` builds `IrohFileSystem` with
   `client=None` and a `client_factory` that only connects on first I/O.
3. Connection remains lazy — creating the adapter does not start the service.

### 4.5 Related modules (adjacent, not primary)

| Module | Role relative to this system |
|---|---|
| `backend_policies.py` / `EnhancedBackendManager` | Quotas, replication, retention, cache policies for dashboard-oriented management |
| `backend_config.py` | Broader backend configuration initialization used by some CLI paths |
| `backend_schemas.py` | UI field schemas (password fields); **not** closed secret-ref validation |
| `routing/` | Content routing across backends (HTTP preferred after gRPC deprecation) |
| `tiered_cache_manager.py`, `cache/` | Caching layers above storage adapters |
| MCP storage controllers / archived managers | Historical control-plane integrations |

---

## 5. Data flow and control flow

### 5.1 Discover types (no side effects)

```text
Caller
  → BackendTypeRegistry(load_entry_points=?)
      → register LegacyBackendPlugin × LEGACY_TYPES
      → register IrohBackendPlugin()     # import is inert
      → optional importlib.metadata entry points (group ipfs_kit.backends)
  → types() / describe() / get(type_name)
```

Tests construct `BackendTypeRegistry(load_entry_points=False)` to isolate
built-ins from environment entry points.

### 5.2 Create or update a named document

```text
create_backend(name, type, config)
  → registry.get(type).validate(document)
  → atomic YAML write (0600)
  → return redact_backend_config(normalized)

update_backend(name, **kwargs)
  → read raw → normalize → merge → validate → write
  → on validation failure: original file bytes unchanged
```

### 5.3 Introspect without connecting

```text
show_backend / list_backends / get_backend_info
  → normalized config
  → redacted for external consumers
  → capabilities from plugin (config-derived; not a live probe unless plugin does so carefully)
  → health from optional probe or plugin.health (Iroh: local socket existence only)
```

### 5.4 Construct a live adapter (side effects start here)

```text
# Schema-validated Iroh (preferred)
BackendManager.get_backend_adapter(name)
  → get_backend_config(name, redact=False)
  → IrohBackendPlugin.create_filesystem(config)
  → IrohFileSystem(client=None, client_factory=..., read_only=...)

# Package factory for non-Iroh adapter types
backends.get_backend_adapter("s3", "my_s3", manager)
  → S3BackendAdapter(name, manager)

# Package factory for Iroh (requires manager)
backends.get_backend_adapter("iroh", "team_archive", manager)
  → manager.get_backend_adapter("team_archive")
```

### 5.5 Migration

```text
migrate_backend(name)
  → plugin.migrate(raw)
  → if unchanged: report changed=False
  → else: write .bak (0600), atomic replace with migrated document, redact result
```

Iroh accepts a historical **flat** field shape and rewrites to nested
schema version 1. Migration never resolves or invents credential material;
inline secrets are rejected.

---

## 6. Invariants

1. **Import-time inertness.** Loading the registry module and constructing the
   registry must not start daemons, open network sockets for storage I/O, or
   resolve secrets into process memory for connection use.
2. **Validation before persistence.** Invalid documents are rejected with
   `BackendConfigError` / structured `{error, code}` results; no partial YAML.
3. **Atomic durable writes.** Config files use temp file + fsync + replace and
   mode `0o600`.
4. **Public redaction.** Create/update/show/list/info/health public payloads
   pass through `redact_backend_config`. Secret reference **providers** may
   remain visible; record / env identifiers and sensitive values become
   `<redacted>` (e.g. `secretref:environment:<redacted>`).
5. **Secret material never in validated Iroh YAML.** Only approved
   `secretref:<provider>:<id>` strings under credential keys; keys matching the
   secret key regex without an approved ref are rejected.
6. **Lazy adapter connection for Iroh.** `create_filesystem` returns an inert
   filesystem; `client` stays `None` until first I/O via `client_factory`.
7. **Unknown types fail closed.** `UnknownBackendTypeError` /
   `code: unknown_backend_type` — no silent fallback to a default backend.
8. **Broken third-party entry points do not disable built-ins.** Load failures
   are skipped.
9. **Legacy compatibility.** Non-schema types remain creatable as JSON-compatible
   documents; migration is a no-op when the document is already current for
   that plugin.
10. **Do not write resolved secrets back.** Unredacted config is for in-process
    resolution only; persisted documents keep references.

---

## 7. Process, async, and lifecycle boundaries

| Boundary | Rule |
|---|---|
| Process import | Registry/plugin import is configuration-only |
| Manager construction | Binds paths and optional `health_probes`; does not open backends |
| Config I/O | Synchronous filesystem operations on YAML |
| Adapter construction | Explicit call; may allocate clients but Iroh keeps them lazy |
| Health probes | Optional callables injected into the manager; default plugin health avoids full RPC where possible |
| Service lifecycle | Starting/stopping Iroh or IPFS daemons is **service** ownership, not registry ownership (see GLOSSARY **Service** / **Daemon**) |
| Async adapters | `BackendAdapter` methods are async (`anyio`); Iroh FS may expose async capabilities in capability maps — do not assume the manager itself is async |

---

## 8. Trust boundaries and sensitive-data handling

### 8.1 What is trusted

- On-disk named documents under the kit state root (operator-controlled).
- Plugin validation code (in-tree or entry-point loaded — third-party plugins
  expand trust).
- Secret **reference** strings naming external providers
  (`secure-config`, `enhanced-secrets`, `credential-manager`, `environment`).

### 8.2 What must never appear in logs, CLI output, or API responses

- Inline tokens, passwords, node keys, write capabilities, API keys.
- Unredacted secretref **identifiers** in external-facing payloads
  (provider may remain for diagnostics).

### 8.3 Redaction implementation

`redact_backend_config` walks mappings/lists and redacts values whose keys match
a sensitive-name regex (`secret`, `token`, `password`, `api_key`,
`write_capability`, `credential`, etc.). For string values that look like
`secretref:provider:id`, the id portion is replaced with `<redacted>`.

Legacy documents may still contain inline credential fields; redaction protects
those keys when documents are shown. Prefer migrating toward reference-only
shapes when adding new schema-validated types.

### 8.4 Operator guidance

- Use `config/iroh-backend.example.yaml` as a secret-free template.
- Prefer `docs/iroh/named-backends.md` for Iroh create/show/migrate workflows.
- Never paste live credentials into fixtures, docs, or architecture examples.
- Set `IPFS_KIT_AUTO_INSTALL_BINARIES=0` when validating documentation offline.

---

## 9. Expected failures, degraded modes, and observability

| Condition | Behavior | Operator signal |
|---|---|---|
| Unknown type | `UnknownBackendTypeError` / `code: unknown_backend_type` | Create rejected |
| Invalid schema / unknown fields (Iroh) | `BackendConfigError` / `invalid_backend_config` | No partial file |
| Duplicate name | `code: backend_exists` | Create rejected |
| Missing document | `FileNotFoundError` or error envelope from show/remove | List omits broken files that error on show |
| Failed update validation | Error result; previous YAML bytes preserved | Compare file mtime/content |
| Disabled Iroh backend | Plugin health `status: disabled`, `ready: False` | Capabilities still describe access |
| Unreachable local RPC socket | Iroh health `healthy: False`, `status: unavailable` | No automatic daemon start |
| Legacy type health without probe | `healthy: None`, `status: not-probed` | Inject `health_probes` for real checks |
| Broken entry-point plugin | Skipped at load | Type absent from `types()` |
| Adapter type unsupported by package factory | `ValueError` listing supported adapter keys | Use manager path or implement adapter |

Observability hooks today are structured dict returns (capabilities, health,
info) rather than a single metrics subsystem. Policy/dashboard managers may
add separate analytics; do not confuse those with registry health.

---

## 10. Extension points and safe modification guidance

### 10.1 Prefer schema-validated plugins for new types

New storage types should:

1. Implement the `BackendPlugin` protocol (class or instance).
2. Set `schema_version` to an integer so `describe()` marks
   `schema_validated: True`.
3. Keep module import and `validate` free of network I/O and secret resolution.
4. Accept only secret references (or no secrets) in persisted documents.
5. Provide `migrate` that is idempotent and never manufactures secrets.
6. Optionally implement `create_filesystem` / adapter factory that stays lazy.
7. Register either:
   - in-process via `registry.register(MyPlugin())` (tests, source checkouts), or
   - via packaging entry point group `ipfs_kit.backends` (installed plugins).

### 10.2 Safe extension walkthrough (grounded in tests)

The Iroh contract tests in `tests/test_iroh_backend_manager.py` are the
executable specification for a safe plugin. Mirror these steps when adding a
type.

**Step A — Register without startup**

```python
from ipfs_kit_py.backend_registry import BackendTypeRegistry

registry = BackendTypeRegistry(load_entry_points=False)
plugin = registry.get("iroh")
assert plugin.schema_version == 1
# No service state directory is created by registry or schema fetch alone.
```

Grounded by: `test_iroh_is_a_registered_versioned_backend_without_startup`.

**Step B — Persist refs only; redact public results**

```python
from ipfs_kit_py.backend_manager import BackendManager

manager = BackendManager(tmp_path, registry=registry)
result = manager.create_backend(name, "iroh", config=document_without_name_type)
# result["backend"] credentials show secretref:<provider>:<redacted>
# on-disk YAML retains full secretref identifiers, mode 0o600
```

Grounded by: `test_create_persists_refs_owner_only_and_redacts_all_public_results`.

**Step C — Reject bad documents without partial files**

Unknown fields, inline secrets, non-local RPC endpoints, and impossible
policy combinations must fail closed with `invalid_backend_config` and leave
no `backends/<name>.yaml`.

Grounded by: `test_invalid_or_unknown_iroh_settings_are_rejected_without_a_partial_file`,
`test_failed_update_does_not_replace_valid_configuration`.

**Step D — Capabilities and redacted health**

Capabilities are derived from the document (e.g. read-only vs read-write).
Health probes may receive unredacted config in-process but **must** return
through redaction before crossing trust boundaries.

Grounded by: `test_capabilities_reflect_access_and_health_is_structured_and_redacted`.

**Step E — Lazy adapter construction**

```python
filesystem = manager.get_backend_adapter("team_archive")
assert filesystem.client is None
assert callable(filesystem.client_factory)
```

Grounded by: `test_adapter_construction_is_lazy`.

**Step F — Keep legacy documents working**

Non-schema backends (e.g. `s3` with simple fields) remain creatable;
`migrate_backend` reports `changed: False` when already current.

Grounded by: `test_legacy_non_iroh_backend_documents_remain_compatible`.

### 10.3 Minimal custom plugin sketch (offline / inert)

```python
from collections.abc import Mapping
from typing import Any

from ipfs_kit_py.backend_registry import (
    BackendConfigError,
    BackendTypeRegistry,
    ensure_json_compatible,
    validate_backend_name,
)


class ExampleBackendPlugin:
    """Illustrative schema-validated plugin — keep validate() side-effect free."""

    type_name = "example"
    schema_version = 1

    def validate(self, config: Mapping[str, Any]) -> dict[str, Any]:
        value = ensure_json_compatible(config)
        validate_backend_name(value.get("name"))
        if value.get("type") != self.type_name:
            raise BackendConfigError("backend type must be 'example'")
        if value.get("schema_version") != 1:
            raise BackendConfigError("schema_version must be 1")
        # Reject inline secrets; require secretref: forms if credentials exist.
        return value

    def migrate(self, config: Mapping[str, Any]) -> dict[str, Any]:
        return self.validate(config)

    def capabilities(self, config: Mapping[str, Any]) -> dict[str, Any]:
        return {"named": True, "schema_validated": True, "schema_version": 1}

    def health(self, config: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "healthy": None,
            "status": "not-probed",
            "enabled": bool(config.get("enabled", True)),
        }

    def schema(self) -> dict[str, Any] | None:
        return {
            "type": "object",
            "properties": {
                "type": {"const": "example"},
                "schema_version": {"const": 1},
            },
        }


def register_example(registry: BackendTypeRegistry | None = None) -> BackendTypeRegistry:
    registry = registry or BackendTypeRegistry(load_entry_points=False)
    registry.register(ExampleBackendPlugin(), replace=False)
    return registry
```

**Do not** in `validate` or module import:

- Call credential providers to resolve secrets.
- Open TCP/HTTP/S3 clients.
- Start subprocess daemons.
- Write outside the manager’s atomic YAML path.

**Do** in adapter construction (separate method/module):

- Accept already-validated config.
- Defer client creation until first I/O when possible.
- Resolve secret references at the last responsible moment and never persist
  resolved values.

### 10.4 Packaging entry points

Third-party packages may advertise:

```toml
[project.entry-points."ipfs_kit.backends"]
example = "mypkg.backends:ExampleBackendPlugin"
```

The registry loads the object (class or instance), calls a class to instantiate
it, and registers it. Prefer the same type object on re-registration (duplicate
same-class entry points are ignored).

---

## 11. Design rationale, trade-offs, and rejected alternatives

| Decision | Rationale | Confidence |
|---|---|---|
| Split type registry from live adapters | Prevents import-time daemon/credential side effects; matches test contracts | High — explicit in `backend_registry` module docstring and Iroh tests |
| Legacy plugins with open JSON documents | Preserves existing named YAML for many backend type strings without a big-bang migration | High for compatibility; medium that every legacy name has a complete live adapter |
| Closed schema + secret refs for Iroh first | Highest risk backend (local RPC + capabilities) needs fail-closed validation | High — dedicated schema, fixture, and tests |
| Redact by default on manager public APIs | Stops secret leakage through CLI/MCP/dashboard responses | High |
| Skip broken entry points | Availability of built-ins over fail-fast for optional plugins | Medium — failures are silent; operators must inspect `types()` |
| Optional `health_probes` injection | Keeps default plugin health offline-friendly while allowing live probes | High for mechanism; default probe set is incomplete for legacy types |
| Multiple historical managers/adapters retained | Avoids breaking dashboard/MCP call sites during migration | Working but **unresolved** which path is production-default for non-Iroh |

**Rejected / avoided approaches**

- Validating by opening a live connection (would couple config UX to network and
  leak credentials into early failure paths).
- Storing resolved secrets in YAML (breaks redaction model and multi-user host
  safety).
- Treating `backend_schemas.py` password fields as the security model for new
  types (dashboard convenience ≠ secret-ref policy).
- Presenting Layer A/B/C historical diagrams in
  `BACKEND_ARCHITECTURE_VISUAL_SUMMARY.md` as the current canonical design
  without the plugin/document/adapter split above.

---

## 12. Tests and fixtures that verify behavior

| Test / fixture | What it locks |
|---|---|
| `tests/test_iroh_backend_manager.py` | Registration without startup; redaction; reject unknown/inline secrets; atomic update failure; capabilities; health redaction; legacy flat migrate; non-Iroh legacy create; lazy adapter |
| `tests/fixtures/iroh/filesystem/backend-config-v1.json` | Canonical version-1 document shape for tests |
| `config/iroh-backend.example.yaml` | Operator-facing secret-free example |
| `tests/test_intelligent_daemon_system.py` | Package `get_backend_adapter` for filesystem/s3/ipfs (live-adapter factory path) |
| `tests/unit/test_backend_adapter_comprehensive.py` | Adapter interface coverage |
| `tests/unit/test_backend_error_handling.py` | Adapter error behavior |
| `tests/test_enhanced_backend_manager.py` | Policy-oriented enhanced manager (parallel path) |
| `tests/test_storage_backend_policies.py` | Policy structures for backends |
| `tests/test_bucket_backend_mapping.py` | Bucket ↔ backend mapping (boundary to KDOC-014) |
| `docs/iroh/named-backends.md` | Normative operator prose for Iroh named backends |

Focused offline verification of the registry (no network):

```bash
IPFS_KIT_AUTO_INSTALL_BINARIES=0 python - <<'PY'
from ipfs_kit_py.backend_registry import BackendTypeRegistry, redact_backend_config

registry = BackendTypeRegistry(load_entry_points=False)
assert "iroh" in registry.types()
assert registry.describe()["iroh"]["schema_validated"] is True
assert registry.describe()["s3"]["schema_validated"] is False
sample = {
    "name": "demo",
    "type": "s3",
    "api_key": "should_never_appear",
    "token_ref": "secretref:environment:DEMO_TOKEN",
}
print(redact_backend_config(sample))
PY
```

---

## 13. Relationship to older backend documentation

| Document | Use relative to this guide |
|---|---|
| [SOURCE_OF_TRUTH_MAP.md](./SOURCE_OF_TRUTH_MAP.md) §2 | Candidate authorities, gaps, unresolved decisions |
| [GLOSSARY.md](./GLOSSARY.md) | Shared terms: Backend, Adapter, Registry |
| [BACKEND_ARCHITECTURE_VISUAL_SUMMARY.md](./BACKEND_ARCHITECTURE_VISUAL_SUMMARY.md) | Historical multi-layer / multi-manager diagrams — not the plugin contract |
| [FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md](./FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md) | Deep review of filesystem-oriented backends |
| `docs/iroh/named-backends.md` | Iroh operator contract (normative for Iroh documents) |
| `docs/reference/storage_backends.md` | Feature-oriented reference; may lag registry inventory (e.g. “6 backends” claims) |
| Future `CONTENT_METADATA_VFS.md` (KDOC-014) | What happens to bytes/metadata after an adapter exists |

When prose conflicts, prefer **executable behavior + focused tests**, then this
architecture guide and `docs/iroh/*` contracts, then older status reports.

---

## 14. Change triggers and last-verified baseline

**Update this guide when any of the following change:**

- `BackendPlugin` protocol or `BackendTypeRegistry` construction/load rules
- `LEGACY_TYPES` membership or a new type gains `schema_version`
- Named document path layout, permissions, or atomic write algorithm
- Redaction regex or secretref provider allow-list
- Iroh schema version or migration rules
- Adapter factory authority (manager vs `backends.get_backend_adapter` vs kits)
- Resolution of unresolved multi-manager / multi-IPFS-adapter decisions

**Last verified:** 2026-08-03 against:

- `ipfs_kit_py/backend_registry.py` (`BackendTypeRegistry`, `LegacyBackendPlugin`,
  `redact_backend_config`, entry-point group `ipfs_kit.backends`)
- `ipfs_kit_py/backend_manager.py` (`BackendManager`)
- `ipfs_kit_py/iroh/backend.py` (`IrohBackendPlugin`, schema version 1)
- `ipfs_kit_py/backends/` package factory and adapters
- `tests/test_iroh_backend_manager.py` and Iroh fixtures/examples

**Validation for this document (task gate):**

```bash
test -s docs/architecture/STORAGE_BACKEND_SYSTEM.md \
  && rg -q "BackendTypeRegistry" docs/architecture/STORAGE_BACKEND_SYSTEM.md
```
