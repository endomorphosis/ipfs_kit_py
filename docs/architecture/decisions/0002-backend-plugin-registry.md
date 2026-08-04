# ADR-0002: Backend configuration-plugin registry

> **Document class:** Canonical  
> **Decision status:** Accepted  
> **Date:** 2026-08-03  
> **Last verified:** 2026-08-03  
> **Evidence baseline:** current tree as of 2026-08-03 (`8e57e5c2` / tree `8e57e5c27dc25850dad239e1485dec4ff5d85ce9`)  
> **Authors:** KDOC-022 (agent-supervisor:implementation-daemon)  
> **Confirmation owner:** storage / configuration maintainers (for residual U-04 factory authority only)  
> **Supersedes:** none  
> **Superseded by:** none  
> **Related guides:** [`../STORAGE_BACKEND_SYSTEM.md`](../STORAGE_BACKEND_SYSTEM.md), [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §2, [`../CONFIGURATION_STATE_AND_TRUST.md`](../CONFIGURATION_STATE_AND_TRUST.md), [`../../iroh/named-backends.md`](../../iroh/named-backends.md)  
> **Related conflicts / U-IDs:** U-04 (live-adapter factory and dual `ipfs_backend` modules — open; not settled by this ADR)

Process contract:
[`README.md`](./README.md) · Claim standard:
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)

---

## 1. Context

IPFS Kit supports many named storage backend *types* (Iroh, IPFS, S3-compatible
object stores, local/SSHFS filesystems, and a long tail of compatibility names).
Callers must be able to:

1. Discover which types exist.
2. Validate, migrate, describe, and redact **configuration documents** without
   starting daemons or resolving credentials into live sessions.
3. Construct **live adapters** only when a consumer explicitly requests runtime
   I/O.

Without a recorded decision, documentation and new code easily conflate three
distinct objects—**type plugins**, **named YAML documents**, and **live
adapters**—or treat historical managers and dual IPFS adapter modules as equal
defaults.

This ADR records the architectural choice that is already implemented and
contract-tested: a **side-effect-free configuration-plugin registry** is the
authority for type discovery and document validation; live adapters live in a
separate layer and must not run during import, registry construction, or pure
validation.

**In scope:**

- `BackendTypeRegistry` / `BackendPlugin` / `LegacyBackendPlugin` contracts
- Entry-point group `ipfs_kit.backends` and built-in seeding (legacy + Iroh)
- Separation of configuration plugins from live adapters and named documents
- Redaction, unknown-type fail-closed behavior, and extension rules for new types
- Legacy open-JSON vs schema-validated trade-offs
- Security and trust implications of third-party plugins and secret references

**Out of scope:**

- Choosing a single production **live-adapter factory** among
  `BackendManager.get_backend_adapter`, `backends.get_backend_adapter`, kits, or
  top-level `ipfs_kit_py/ipfs_backend.py` (U-04 — remains open)
- Content/metadata/VFS/WAL durability paths (KDOC-014 /
  `CONTENT_METADATA_VFS.md`)
- MCP tool wiring and control-plane storage managers
- Per-field catalogs for every legacy type
- End-state secret-store composition (ADR-0007 / U-13)

---

## 2. Current behavior (evidence, not aspiration)

The repository implements a three-layer storage configuration model.

```text
BackendTypeRegistry  (type catalog / configuration plugins — no live I/O)
        │  validate / migrate / describe / redact
        ▼
Named backend document  (~/.ipfs_kit/backends/<name>.yaml)
        │  get_backend_adapter / create_filesystem (explicit)
        ▼
Live adapter  (backends/*, IrohFileSystem, kit clients, …)
```

| Surface / path | Observed role | Evidence (source, test, packaging) | Status label |
|---|---|---|---|
| `ipfs_kit_py/backend_registry.py` | Side-effect-free type catalog; module docstring states registry holds configuration behavior, not live instances | Module docstring; `BackendTypeRegistry`, `BACKEND_ENTRY_POINT_GROUP = "ipfs_kit.backends"` | Active / canonical for type plugins |
| `BackendPlugin` protocol | `type_name`, `schema_version`, `validate`, `migrate`, `capabilities`, `health`, `schema` | `backend_registry.py` `@runtime_checkable` Protocol | Active contract |
| `LegacyBackendPlugin` | Open JSON-compatible documents for 21 built-in type names; `schema_version is None` → `schema_validated: False` | `LEGACY_TYPES` tuple; `tests/test_iroh_backend_manager.py::test_legacy_non_iroh_backend_documents_remain_compatible` | Compatibility / active |
| `IrohBackendPlugin` | Schema-validated type (`schema_version: 1`); direct register so source checkouts work without rebuilt metadata | `iroh/backend.py`; registry `__init__` comment; `test_iroh_is_a_registered_versioned_backend_without_startup` | Active / preferred pattern for new types |
| `get_backend_type_registry()` | Process-wide lazy singleton | `backend_registry.py` | Active |
| `BackendRegistry` alias | Compatibility spelling for callers that do not need type-vs-live naming | Same module | Compatibility |
| `ipfs_kit_py/backend_manager.py` | Named document CRUD, atomic 0600 writes, public redaction, delegates validate/migrate/capabilities/health to plugins | Manager + Iroh manager tests | Active / canonical for named docs |
| `ipfs_kit_py/backends/` | Live adapter package (`BackendAdapter` ABC, IPFS/filesystem/S3 factories); Iroh branch requires a manager | `backends/__init__.py` `BACKEND_ADAPTERS` / `get_backend_adapter` | Active live layer (distinct from type registry) |
| `backends/iroh_backend.py` | Compatibility re-exports of Iroh plugin + filesystem | Package layout | Compatibility |
| Top-level `ipfs_kit_py/ipfs_backend.py` | Parallel/historical IPFS adapter path vs package module | Map U-04 / `SOURCE_OF_TRUTH_MAP.md` | Compatibility / unresolved default |
| `EnhancedBackendManager` / `backend_schemas.py` | Policy/dashboard-oriented parallel surfaces; not closed secret-ref authority | Guide §3–4 | Compatibility / non-authority for validation |
| Entry points `ipfs_kit.backends` | Optional third-party load; broken plugins skipped | `load_entry_points()` | Active extension mechanism |

**Built-in inventory (baseline 2026-08-03, `load_entry_points=False`):**

- **Schema-validated:** `iroh` (`schema_version: 1`).
- **Legacy names (`LEGACY_TYPES`, 21):** `cluster`, `digitalocean`, `estuary`,
  `filecoin`, `filecoin_pin`, `filesystem`, `ftp`, `gdrive`, `github`,
  `huggingface`, `ipfs`, `ipfs_cluster`, `lassie`, `local`, `local_fs`,
  `local_storage`, `minio`, `parquet`, `s3`, `sshfs`, `storacha`.
- **Total:** 22 registered types in a clean registry; installed environments may
  add more via entry points.

**Invariants observed in code and tests:**

1. Importing the registry module and constructing `BackendTypeRegistry` does not
   start storage services (`test_iroh_is_a_registered_versioned_backend_without_startup`).
2. Public manager results pass through `redact_backend_config`.
3. Invalid Iroh documents fail closed without partial YAML files.
4. Iroh live adapter construction is lazy (`client is None` until first I/O).
5. Unknown types raise `UnknownBackendTypeError` / `code: unknown_backend_type`.
6. Broken third-party entry points are skipped so built-ins remain usable.

---

## 3. Decision

**Status:** Accepted

### 3.1 Decision statement

**IPFS Kit keeps a dedicated, side-effect-free backend *configuration-plugin*
registry as the authority for backend *type* discovery, document validation,
migration hooks, capabilities/health *defaults*, schema metadata, and public
redaction helpers.**

Concretely:

1. **`BackendTypeRegistry`** (module `ipfs_kit_py.backend_registry`) is the
   canonical type catalog. It registers plugins implementing the
   **`BackendPlugin`** protocol and must not start daemons, open storage
   network connections, or resolve credentials for live sessions during
   discovery, `validate`, `migrate`, `describe`, or redaction.
2. **Named backend documents** (managed by `BackendManager` under the kit state
   root) are configuration only until an adapter is explicitly requested.
3. **Live adapters** (`ipfs_kit_py/backends/*`, `IrohFileSystem`, kit clients)
   are a **separate layer**. Constructing them is the first intentional
   side-effect boundary for storage I/O. Documentation and APIs must label live
   adapters distinctly from configuration plugins (including stub, lazy, or
   not-probed health states).
4. **Two plugin fidelity tiers are intentional:**
   - **Schema-validated** plugins set an integer `schema_version` (Iroh today),
     expose closed schemas, prefer secret *references* in persisted YAML, and
     may offer lazy adapter factories (`create_filesystem`).
   - **Legacy** plugins (`LegacyBackendPlugin` for `LEGACY_TYPES`) accept
     JSON-compatible documents without a closed schema so existing named YAML
     and type strings remain creatable without a big-bang migration.
5. **Extension** for new production types must prefer the schema-validated
   pattern and may register in-process or via packaging entry-point group
   **`ipfs_kit.backends`**. Broken third-party plugins must not disable built-ins.
6. **Unknown types fail closed** (`UnknownBackendTypeError`); there is no silent
   fallback to a default backend type.

**Not decided here (still open):** which code path is the sole production
factory for non-Iroh live adapters, and whether top-level `ipfs_backend.py` or
`backends/ipfs_backend.py` is preferred for new work (U-04). Guides must not
present those surfaces as interchangeable settled defaults.

### 3.2 Options (evaluated; selected option is A)

| Option | Summary | Fit / risk |
|---|---|---|
| **A — Side-effect-free type registry + separate live adapters** | Config plugins validate/migrate/redact only; live I/O after explicit construction | Matches implementation and tests; lowest import-time risk; clear trust boundary |
| B — Unified “backend object” that validates by connecting | Type registration and connection share one lifecycle | Couples config UX to network; pulls credentials early; breaks offline CLI/list |
| C — Documents only, no type plugins | Free-form YAML without registry protocol | Loses typed validation, migration, describe, entry-point extension |
| D — Schema-validated only (drop legacy names immediately) | Force closed schemas for all 21 legacy type strings | High migration cost; breaks existing named documents |
| Status quo without recorded decision | Behavior exists but docs conflate plugins/adapters | Recurring U-04 confusion; unsafe extension patterns |

**Selected option:** **A** — implemented and accepted as the architectural
invariant for the configuration-plugin registry.

---

## 4. Rationale (confidence-labeled)

**Accepted:**

- Discovery and configuration validation must stay inert so import, CLI
  list/show, and test isolation never start daemons or open storage RPC by
  accident. The module docstring and
  `test_iroh_is_a_registered_versioned_backend_without_startup` lock this
  contract.
- Public surfaces must redact sensitive keys and secretref identifiers
  (`redact_backend_config`, manager create/show/list/info/health tests) so CLI,
  MCP, and dashboard responses do not leak credentials.
- Iroh is the reference schema-validated type: closed schema version 1, secret
  refs only, lazy `create_filesystem` (`test_adapter_construction_is_lazy`,
  reject-without-partial-file tests).
- Legacy open-JSON plugins remain so non-Iroh named documents stay creatable
  (`test_legacy_non_iroh_backend_documents_remain_compatible`) while
  `describe()["schema_validated"]` truthfully reports `False`.
- Direct registration of `IrohBackendPlugin` keeps source checkouts working when
  package metadata is not rebuilt, without requiring entry-point load for the
  first-class type.
- Skipping broken entry-point plugins preserves built-in availability
  (`load_entry_points` try/continue).

**Proposed:**

- Future legacy type names should gain closed schemas and secret-ref rules
  incrementally (same pattern as Iroh), not via a single cutover. Migration
  ownership and schedule need product prioritization.
- A single documented live-adapter factory authority for non-Iroh types (U-04)
  should eventually be recorded in a follow-up ADR or amendment once maintainers
  confirm.

**Inferred:**

- Silent skip of broken entry points prioritizes availability over fail-fast
  observability for optional plugins; operators must inspect `types()` /
  `describe()` when a third-party type is missing.
- Dual IPFS adapter modules and parallel managers remain because historical
  dashboard/MCP call sites still import them, not because both are intended
  long-term defaults.

**Unknown:**

- Whether every `LEGACY_TYPES` name has a complete, supported live adapter path
  today — unknown / maintainer confirmation needed per type inventory.
- Preferred resolution of U-04 (manager vs package factory vs top-level
  `ipfs_backend`) — unknown / maintainer confirmation needed.
- Default `health_probes` set for legacy types beyond `not-probed` —
  unknown / incomplete in tree.

---

## 5. Evidence

| Rank | Claim | Citation |
|---|---|---|
| 1 | Registry construction and Iroh registration do not start services | `tests/test_iroh_backend_manager.py::test_iroh_is_a_registered_versioned_backend_without_startup` |
| 1 | Public create/show paths redact secrets; disk keeps secretref ids at 0600 | `test_create_persists_refs_owner_only_and_redacts_all_public_results` |
| 1 | Invalid Iroh settings leave no partial file; failed update preserves prior YAML | `test_invalid_or_unknown_iroh_settings_are_rejected_without_a_partial_file`, `test_failed_update_does_not_replace_valid_configuration` |
| 1 | Unknown backend type rejected; validation API raises | `test_validation_api_raises_and_unknown_backend_type_is_rejected` |
| 1 | Iroh live adapter is lazy (`client is None`, callable `client_factory`) | `test_adapter_construction_is_lazy` |
| 1 | Legacy non-Iroh documents remain creatable | `test_legacy_non_iroh_backend_documents_remain_compatible` |
| 1 | Capabilities/health structured and redacted | `test_capabilities_reflect_access_and_health_is_structured_and_redacted` |
| 3 | Type registry is configuration-only, not live instances | `ipfs_kit_py/backend_registry.py` module docstring and `BackendTypeRegistry` |
| 3 | Plugin protocol, redaction, unknown-type error codes | `BackendPlugin`, `redact_backend_config`, `UnknownBackendTypeError` |
| 3 | Live adapters are a separate package/factory map | `ipfs_kit_py/backends/__init__.py` (`BACKEND_ADAPTERS`, `get_backend_adapter`) |
| 3 | Iroh schema-validated plugin + lazy FS factory | `ipfs_kit_py/iroh/backend.py` (`IrohBackendPlugin`, `create_filesystem`) |
| 3 | Named document manager delegates to plugins | `ipfs_kit_py/backend_manager.py` |
| 5 | Architecture narrative and extension walkthrough | `docs/architecture/STORAGE_BACKEND_SYSTEM.md` (KDOC-013) |
| 5 | Candidate authorities and U-04 | `docs/architecture/SOURCE_OF_TRUTH_MAP.md` §2 |

**Evidence that is explicitly insufficient for Accepted status on U-04:**
documentation tables alone, historical visual summaries, and parallel adapter
modules without a maintainer-chosen single factory path. U-04 stays open and is
**not** promoted by this ADR.

---

## 6. Consequences

### 6.1 Positive

- Safe offline discovery: listing types, validating YAML, and redacting configs
  does not require network or daemon lifecycle.
- Clear vocabulary for guides and agents: **plugin ≠ document ≠ live adapter**.
- Extension path for third parties (`ipfs_kit.backends`) without forking core.
- Iroh-grade security model (secret refs, closed schema, lazy connect) can be
  copied for new types while legacy names continue to work.
- Fail-closed unknown types prevent silent misrouting of storage operations.

### 6.2 Negative / costs

- Two fidelity tiers (`schema_validated` true/false) must be explained in every
  operator and developer surface that lists types.
- Live-adapter coverage is uneven across legacy names; registration does not
  imply a full adapter implementation.
- Silent entry-point load failures can hide misconfigured third-party plugins.
- Parallel historical managers/adapters still exist and can confuse newcomers
  until U-04 is resolved.

### 6.3 Migration and compatibility

- Existing named YAML for legacy types remains valid under
  `LegacyBackendPlugin` validation (JSON-compatible + name/type match).
- Iroh flat legacy field shapes migrate via plugin `migrate` (atomic rewrite +
  `.bak` when changed); migration never invents secrets.
- New types should not be added as open-JSON legacy names without an explicit
  compatibility plan; prefer `schema_version` ≥ 1.
- Alias `BackendRegistry = BackendTypeRegistry` remains for older call sites.

### 6.4 Security and trust

- **Trust expands** when loading third-party entry-point plugins: validation
  code runs in-process with the same privileges as the kit.
- **Persisted documents** must prefer `secretref:<provider>:<id>` forms for
  schema-validated types; inline secrets are rejected for Iroh and must not be
  reintroduced in new closed schemas.
- **Public APIs** must return `redact_backend_config` copies; unredacted config
  is for last-moment in-process resolution only and must not be written back.
- **Health probes** may receive unredacted config in-process but must redact
  before crossing CLI/MCP/log boundaries.
- **No credentials, tokens, private keys, or host-specific secret paths** belong
  in this ADR or in fixtures/docs; use placeholders and example templates such as
  `config/iroh-backend.example.yaml`.
- Import-time inertness is a security control: it prevents accidental secret
  resolution and connection attempts during mere package import or type listing.

### 6.5 Extension implications

Safe extension (mirrors KDOC-013 §10 and Iroh tests):

1. Implement `BackendPlugin` with integer `schema_version`.
2. Keep module import and `validate` free of network I/O and credential
   resolution.
3. Accept secret references only (or no secrets) in persisted documents.
4. Provide idempotent `migrate` that never manufactures secrets.
5. Offer lazy adapter construction if a live client is needed.
6. Register via `registry.register(...)` (tests/source) and/or
   `[project.entry-points."ipfs_kit.backends"]` for installed packages.
7. Do not use `backend_schemas.py` password-style UI fields as the security model
   for new types.

### 6.6 Testing and verification

- **Must keep green for this decision:** `tests/test_iroh_backend_manager.py`
  (registration without startup, redaction, reject partial files, legacy
  compatibility, lazy adapter).
- Supporting: unit adapter tests under `tests/unit/test_backend_adapter_*.py`,
  package factory coverage in intelligent-daemon tests where present.
- Offline smoke (no network):

```bash
IPFS_KIT_AUTO_INSTALL_BINARIES=0 python - <<'PY'
from ipfs_kit_py.backend_registry import BackendTypeRegistry, redact_backend_config
r = BackendTypeRegistry(load_entry_points=False)
assert "iroh" in r.types()
assert r.describe()["iroh"]["schema_validated"] is True
assert r.describe()["s3"]["schema_validated"] is False
print(redact_backend_config({"name": "demo", "type": "s3", "api_key": "x"}))
PY
```

---

## 7. Alternatives considered

| Alternative | Why considered | Why rejected / deferred | Confidence |
|---|---|---|---|
| Validate config by opening a live connection | Ensures “config works” before save | Couples UX to network; early credential use; breaks offline list/create; rejected by Iroh lazy-adapter and no-startup tests | **Accepted** rejection |
| Store resolved secrets in YAML | Simpler local demos | Breaks redaction model and multi-user host safety; rejected for schema-validated path | **Accepted** rejection |
| Drop all legacy type names immediately | Single schema fidelity | Breaks existing named documents; high migration cost; deferred to incremental schema adoption | **Accepted** deferral |
| Treat `backend_schemas.py` / Enhanced manager as validation authority | Dashboard already lists fields | Password-style UI catalogs are not closed secret-ref policy; not the type-registry contract | **Accepted** rejection for authority |
| Single monolithic backend class (plugin + live client) | Fewer objects to learn | Import and discovery would inherit connection lifecycle; conflicts with inert registry invariant | **Accepted** rejection |
| Do nothing / leave undocumented | Avoid ADR overhead | Recurring conflation of plugins vs live adapters in docs and new code; fails program goals KDOC-G022 / KDOC-G032 | **Accepted** rejection of silence |
| Resolve U-04 factory authority in this ADR | One ADR for all backend authority | Insufficient maintainer evidence; dual modules remain; keep open | **Unknown** / deferred |

At least status quo and live-validation alternatives are recorded so the split
is not re-litigated without new evidence.

---

## 8. Unknowns and owner confirmation

Core registry split is **Accepted** from rank-1–3 evidence. Residual gaps do not
block citing this ADR for “plugins vs live adapters” guidance, but they block
claiming a single live-factory default.

| Field | Value |
|---|---|
| **Confirmation owner** | Storage / configuration maintainers (U-04); documentation maintainers for guide citations |
| **Confirmation question** | For non-Iroh types, is `BackendManager` + plugin factory, `backends.get_backend_adapter`, or another path the sole supported live-adapter construction entry for new work? |
| **What “Accepted” for U-04 requires** | Maintainer statement plus tests/docs pointing at one factory; resolution of top-level vs `backends/ipfs_backend.py` |
| **Blocking for** | Absolute “one true adapter API” language in guides; deletion of parallel modules |
| **Related U-IDs / conflicts** | U-04 |

**Open unknowns:**

1. Live-adapter factory authority and dual `ipfs_backend` modules — unknown /
   maintainer confirmation needed (U-04).
2. Completeness of live adapters for each `LEGACY_TYPES` name — unknown /
   inventory needed.
3. When remaining legacy types receive closed schemas — unknown / prioritization
   needed.
4. Default health probe injection set for legacy types — unknown /
   under-documented.

---

## 9. Supersession and relationships

| Relation | ADR / doc |
|---|---|
| Supersedes | none |
| Superseded by | none |
| Related ADRs | ADR-0001 (optional/lazy imports — adjacent inertness culture); ADR-0007 (configuration/secrets composition, when authored); ADR-0006 (multi-protocol defaults, when authored) |
| Architecture guides | [`../STORAGE_BACKEND_SYSTEM.md`](../STORAGE_BACKEND_SYSTEM.md) (KDOC-013), [`../CONFIGURATION_STATE_AND_TRUST.md`](../CONFIGURATION_STATE_AND_TRUST.md), [`../GLOSSARY.md`](../GLOSSARY.md) (Backend / Adapter / Registry) |
| Operator contracts | [`../../iroh/named-backends.md`](../../iroh/named-backends.md) |
| Source-of-truth map | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §2, U-04 |

---

## 10. Follow-up actions

| Action | Owner | Notes |
|---|---|---|
| Keep guide citations status-honest: registry decision Accepted; U-04 open | Architecture / docs | Link this ADR from `STORAGE_BACKEND_SYSTEM.md` when index policy allows |
| Confirm live-adapter factory authority (U-04) | Storage maintainers | May amend this ADR or file a focused follow-up |
| Inventory legacy type → live adapter mapping | Storage maintainers | Document which `LEGACY_TYPES` have package adapters vs kit-only paths |
| Prefer schema-validated plugins for any new type | Contributors | Follow §6.5; do not expand open-JSON legacy without plan |
| Do not edit decisions index from this task | Agents | `README.md` is framework-owned (KDOC-020) |

---

## 11. Review checklist (authors)

- [x] Filename is `0002-backend-plugin-registry.md` (not left as 0000 for a real decision)
- [x] Banner **Decision status** matches §3 **Status** (`Accepted`)
- [x] **Current behavior** is evidence-backed and separate from residual proposals
- [x] No present-tense “the system does X” for Proposed-only factory authority (U-04 stays open)
- [x] Every material *why* uses **Accepted / Proposed / Inferred / Unknown**
- [x] No Inferred or Unknown claim is written as Accepted history
- [x] Evidence table prefers ranks 1–4 for Accepted claims
- [x] Alternatives include status quo and explicit rejects
- [x] Confirmation owner and question filled for residual U-04 unknowns
- [x] No secrets, live tokens, or host-specific credential paths
- [x] `docs/architecture/decisions/README.md` was **not** edited by this task
- [x] Related architecture guide (`STORAGE_BACKEND_SYSTEM.md`) already describes the split; this ADR records the decision with status confidence

---

## Appendix A — Status and confidence summary

| Topic | Decision status | Rationale confidence |
|---|---|---|
| Side-effect-free `BackendTypeRegistry` as type authority | **Accepted** | **Accepted** (code + tests) |
| Separation from **live** adapters and named documents | **Accepted** | **Accepted** |
| Legacy open-JSON + schema-validated Iroh tiers | **Accepted** | **Accepted** for mechanism; **Unknown** for full live coverage of every legacy name |
| Entry-point group `ipfs_kit.backends` with skip-on-error | **Accepted** | **Accepted** behavior; **Inferred** availability-over-fail-fast motive |
| Redaction + secretref model for validated types | **Accepted** | **Accepted** |
| Single live-adapter factory / dual `ipfs_backend` (U-04) | **Not decided** (open) | **Unknown** — confirmation required |

**Decision statuses (header / §3):**  
`Proposed` · `Accepted` · `Rejected` · `Superseded` · `Deprecated` · `Unknown`

**Rationale confidence (§4 markers):**

```markdown
**Accepted:** …
**Proposed:** …
**Inferred:** …
**Unknown:** … unknown / maintainer confirmation needed
```
