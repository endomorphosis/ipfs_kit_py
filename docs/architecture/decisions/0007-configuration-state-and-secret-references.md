# ADR-0007: Configuration, state, and secret references

> **Document class:** Proposed  
> **Decision status:** Proposed  
> **Date:** 2026-08-04  
> **Last verified:** 2026-08-04  
> **Evidence baseline:** current tree as of 2026-08-04 (`b0a8b138c62cbb54d7afc583f0dee1feab65489b`); architecture guide KDOC-019 (`CONFIGURATION_STATE_AND_TRUST.md`)  
> **Authors:** KDOC-027 (agent-supervisor implementation)  
> **Confirmation owner:** platform / operations maintainers (config/state composition and production credential backend); documentation maintainers may not accept this ADR alone  
> **Supersedes:** none  
> **Superseded by:** none  
> **Related guides:** [`../CONFIGURATION_STATE_AND_TRUST.md`](../CONFIGURATION_STATE_AND_TRUST.md), [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) §1/§2/§7, [`../SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md), [`../GLOSSARY.md`](../GLOSSARY.md), normative [`../../iroh/security.md`](../../iroh/security.md), [`../../iroh/threat-model.md`](../../iroh/threat-model.md)  
> **Related conflicts / U-IDs:** U-13 (also adjacent: U-08 cluster secrets, U-11 MCP trees, U-16 daemon managers, C-MCP-TREES)

Process contract:
[`README.md`](./README.md) · Claim standard:
[`docs/guides/DOCUMENTATION_GUIDE.md`](../../guides/DOCUMENTATION_GUIDE.md)

---

## 1. Context

ipfs-kit persists **configuration**, **mutable operational state**, and **secret material** across several managers and directory trees rather than one super-config object. Operators, agents, and MCP tools must know:

1. **Where** each surface loads and writes config (locality and precedence).  
2. **How** durable writes are made safe (validation, atomic replace, modes, backups).  
3. **How** credentials are stored and referenced without leaking into logs, API responses, docs, or support bundles.  
4. **Which composition questions remain open** (U-13) so guides do not invent a single canonical config API.

Without a recorded decision, documentation and integrations risk:

1. Collapsing kit state root (`~/.ipfs_kit`), Kubo repo (`IPFS_PATH` / `~/.ipfs`), and Iroh instance trees into one cleanup domain.  
2. Treating plain `config.yaml` writes as equivalent to backend YAML atomic **0o600** paths.  
3. Embedding live secrets in YAML, env dumps, health probes, or architecture examples.  
4. Declaring a single production credential backend (keyring vs encrypted file vs external KMS) without maintainer confirmation.  
5. Ignoring dual backend layout trees (`backends/*.yaml` vs `backend_configs/`) or MCP HTTP bind/auth posture under U-13.

This ADR records **observed configuration locality, atomic persistence, secret-reference, and redaction posture** with confidence labels; states **threats, consequences, alternatives, and limitations**; and keeps owner composition decisions **Proposed** until confirmation.

**In scope:**

- Configuration sources, locality, and per-surface precedence  
- JSON/YAML-compatible validation before durable write  
- Atomic replace, mode **0o600** / directory **0o700**, backup/migration for sensitive documents  
- Secret reference forms (`secretref:…`, `credential://…`) vs inline secrets  
- Default redaction of external config/health surfaces  
- Preferred credential-store hierarchy (operational recommendation) and production-default options under **U-13**  
- Threats, consequences, alternatives, limitations, and confirmation criteria  

**Out of scope:**

- MCP production runtime tree selection (**ADR-0003** / U-11)  
- Cluster control-plane family (**ADR-0008** / U-08) beyond cluster-secret handling notes  
- Content WAL / journal durability (**ADR-0005**)  
- Multi-protocol transport defaults (**ADR-0006**)  
- Backend plugin registry vs live adapters as sole authority (**ADR-0002**)  
- Implementing a unified ConfigService or removing a manager (code tasks after acceptance)  
- Live credentials, tokens, private keys, or host-specific secret path dumps in this document  

**Non-goal of this draft:** Selecting one production credential backend or collapsing all managers into a single API. Conflict policy and the ADR index require U-13 composition questions to **remain Proposed** until confirmation.

---

## 2. Current behavior (evidence, not aspiration)

Present-tense claims describe the tree **as observed**. They do **not** assert a single canonical config API or accepted production credential default.

### 2.1 Role separation (precondition)

| Role | What it is | What it is not |
|---|---|---|
| **Config document** | Validated, usually YAML/JSON, non-secret-preferred params | Resolved credential values at rest |
| **State root** | Kit or service directory tree for PIDs, backends, caches, journals | Kubo `IPFS_PATH` content repo |
| **Secret plane** | Keyring, encrypted secrets, secure keyring files, OS secret service | Public health or list APIs |
| **Secret reference** | Opaque handle (`secretref:provider:id`, `credential://…`) stored in config | The resolved secret bytes |
| **Redaction** | Safe external copy of a document/health result | Authorization or encryption by itself |
| **Atomic replace** | Temp write + fsync + `os.replace` (+ mode) | Best-effort `write_text` without rename |

### 2.2 Surface inventory

| Surface / path | Observed role | Evidence (source, test, packaging) | Status label |
|---|---|---|---|
| `ipfs_kit_py/config.py` | Thin kit config read/write at `~/.ipfs_kit/config.yaml` | Source; no env override inside module | Active / dashboard-oriented |
| `high_level_api.py` config discovery | Precedence: params → kwargs → loaded file → defaults; discovery cwd → kit root → `/etc/ipfs_kit` | Source HLA load paths | Active library path |
| `BackendManager` (`backend_manager.py`) | Named backends under `{kit}/backends/{name}.yaml`; atomic write; migrate + `.bak` | Source; backend unit tests | Active candidate durable path |
| `backend_registry.py` | Schema/plugin validate; `redact_backend_config`; `_SENSITIVE_RE` | Source; redaction of `secretref` id | Active shared contract |
| `daemon_config_manager.py` | Kubo/Cluster/Lotus paths, ports, install gates | Daemon config tests | Active ops path |
| `secure_config.py` / `cli_secure_config.py` | Encrypted sensitive fields; `.keyring/` **0o700**, files **0o600** | `tests/test_secure_config.py`, unit tests | Active secure config path |
| `credential_manager.py` | Keyring preferred, file fallback (`credentials.json`); list without secret values | Source; credential docs | Active credential API |
| `enhanced_secrets_manager.py` | Encrypted secrets under `secrets/`; **0o600** on save; audit log | AES unit tests; migrate helper | Active encrypted store |
| `iroh/config.py` | Iroh instance config; `credential://iroh/…` refs only; `atomic_write_config` | Iroh config/security tests; normative docs | Active first-class stack |
| `iroh/security.py` | Offline gates; log/stream redaction of credential and secretref patterns | `tests/test_iroh_security.py` | Active security gates |
| `services/state_service.py` | Lightweight `backend_configs/`, `buckets.json`, `pins.json` under data_dir | StateService status APIs | Parallel layout (**U-13**) |
| MCP++ / CLI dashboard | Profile/transport bind; PID/logs under kit data_dir for CLI MCP child | MCP guide; `cli.py` | Active control plane |

### 2.3 Configuration locality and precedence (observed)

**There is no single super-config.** Each surface’s rules apply to that surface only.

| Surface | Locality (default) | Precedence (summary) |
|---|---|---|
| Thin `config.py` | `~/.ipfs_kit/config.yaml` | Fixed path; create parent on save |
| HLA / client | Discovery chain when no `config_path` | Explicit params → kwargs → loaded file → built-in defaults |
| Named backends | `{ipfs_kit_path}/backends/*.yaml` (default kit root `~/.ipfs_kit`) | On-disk document after schema validate/migrate is authority for that name |
| Secure config | Documents under `data_dir`; keys under `data_dir/.keyring/` | Decrypt on load; encrypt sensitive fields on save |
| Credentials | OS keyring or `~/.ipfs_kit/credentials.json` | Keyring preferred when package available; file fallback |
| Enhanced secrets | `~/.ipfs_kit/secrets/` | In-store records; not merged into backend YAML as plaintext |
| Iroh service | Configured instance root (`data/`, `staging/`, `run/`, …) | Instance-local; credential **references** only in config |
| Daemon / install | `IPFS_PATH`, `IPFS_KIT_BIN_DIR`, install env gates | Auto-install **off** unless `IPFS_KIT_AUTO_INSTALL_BINARIES` truthy |
| CLI data dir | `--data-dir` default `~/.ipfs_kit` | MCP PID/logs and StateService-oriented paths |

**Critical locality invariant:** kit state root ≠ Kubo repo. Default `~/.ipfs_kit` must not be treated as `IPFS_PATH` (`~/.ipfs`). Backup, wipe, and migration tools must treat them as independent failure domains. Iroh instance trees are a third private layout (no multi-writer shared instance dirs).

### 2.4 Validation, atomic replace, modes, backup (observed)

| Concern | Observed behavior | Primary evidence |
|---|---|---|
| **JSON/YAML-compatible validation** | Backend documents must be objects; type plugins `validate` / `migrate` before write; backend name regex; Iroh config validates credential reference shape | `BackendManager._read_raw` / `_normalize`; `backend_registry.validate_backend_name`; `iroh/config.py` |
| **Side-effect-free validation** | Type validation must not start daemons or open live network sessions | Registry invariant; CONFIGURATION_STATE_AND_TRUST guide |
| **Atomic replace** | Backend writes: temp in parent dir → `fchmod 0o600` → write + flush + fsync → `os.replace` → `chmod 0o600` on final; cleanup temp on failure. Iroh: `atomic_write_config` / `_atomic_write_json` with mode **0o600** | `backend_manager.py` `_write`; `iroh/config.py` |
| **Directory modes** | Secure keyring dir **0o700**; Iroh layout prefers **0700** dirs / **0600** files | `secure_config.py`; Iroh security baseline |
| **Backup / migration** | `migrate_backend` copies prior file to `{name}.yaml.bak` at **0o600** before rewrite; secure config supports `migrate_to_encrypted` / `rotate_key` | `BackendManager.migrate_backend`; `secure_config.py` |
| **Uneven enforcement** | Thin `config.py` and some StateService JSON paths use simpler writes without the same atomic **0o600** pipeline | Trust guide §5.2, §5.7 |

### 2.5 Secret references and redaction (observed)

**Preferred shapes (in config documents):**

| Form | Typical consumer | Rule |
|---|---|---|
| `secretref:<provider>:<id>` | Named backends / Iroh backend plugin | Persist reference only; resolve at adapter boundary |
| `credential://iroh/<id>` | Iroh service config | Inline secrets rejected; identity/capability refs separate |

**Redaction (external-safe copies):**

- `redact_backend_config` walks documents; keys matching `_SENSITIVE_RE` (secret, token, ticket, password, private key, write capability, credential, authorization, api/access key, …) become `<redacted>`.  
- For `secretref:` values, **provider remains visible** for diagnostics; the identifier becomes `<redacted>` → `secretref:<provider>:<redacted>`.  
- `BackendManager` returns redacted documents from create/update/list/show/info and redacts health probe results; in-process health may use unredacted config only inside the process boundary.  
- Iroh security modules scan streams/logs for credential and secretref patterns and produce redacted offline reports.

**Preferred storage hierarchy (operational recommendation — not a closed production default):**

1. External secret manager / KMS with references only in config  
2. OS keyring via `CredentialManager`  
3. `EnhancedSecretManager` AES-GCM under kit secrets tree  
4. `SecureConfigManager` encrypted fields  
5. File credentials JSON with **0o600** (last resort)  
6. **Avoid:** inline secrets in git, docs, process titles, URLs, crash reports  

Production choice among (1)–(5) as **the** enforced default remains **open under U-13**.

### 2.6 Observed invariants (implementation-backed)

1. **Fragmented managers:** Multiple config/state APIs coexist; no universal merge object.  
2. **State root separation:** Kit root, Kubo `IPFS_PATH`, and Iroh instance trees are distinct.  
3. **Validate then write** for named backends and Iroh service config.  
4. **Atomic replace + 0o600** for backend YAML (and Iroh private config/metadata) is the hardened write path.  
5. **References in durable config; resolve late; never re-persist resolved secrets** to YAML/receipts/logs.  
6. **External APIs default to redacted** backend documents and health.  
7. **Binary install remains opt-in** (`IPFS_KIT_AUTO_INSTALL_BINARIES` default off).  
8. **No credential examples** in architecture ADRs or guides — placeholders and reference shapes only.

---

## 3. Decision

**Status:** Proposed  

### 3.1 Decision statement

Until maintainer confirmation promotes U-13 composition items, this ADR **records and freezes the following design posture** as the documentation and integration baseline. Items marked **Accepted (observed invariant)** may be cited as current behavior. Items marked **Proposed (owner decision)** must not be cited as production defaults without confirmation.

#### D1 — Configuration is multi-surface and local to each manager (**Accepted observed invariant**)

Document and implement against **per-surface locality and precedence**, not a fictional single config file. New features must declare which surface owns their durable settings.

#### D2 — Kit state root, Kubo repo, and Iroh instance trees remain separate failure domains (**Accepted observed invariant**)

| Tree | Default locality | Must not |
|---|---|---|
| Kit state | `~/.ipfs_kit` or explicit `--data-dir` / operator data-dir env where wired | Be wiped as “Kubo cache” or share multi-tenant writers |
| Kubo repo | `IPFS_PATH` (default `~/.ipfs`) | Store primary kit backend YAML / secret stores as the kit root |
| Iroh instance | Configured private root with `data/`, `staging/`, `run/`, `logs/`, `receipts/` | Multi-writer shared instance directories |

#### D3 — Durable sensitive documents use validate → atomic replace → restrictive mode (**Accepted observed for hardened paths**)

For named backend YAML and Iroh private config:

1. **Validate** (schema/plugin/reference shape; JSON/YAML object structure).  
2. **Write temp** in the target directory with mode **0o600**.  
3. **fsync** then **`os.replace`** onto the final path.  
4. **chmod 0o600** on the final path (and on `.bak` after migration backup).  

Guides and new code **should not** regress these paths to unvalidated overwrite. Surfaces that still use weaker writes (thin config, some StateService JSON) are **documented limitations**, not the target pattern for secret-bearing files.

#### D4 — Persist secret references; resolve at use; never re-write resolved values (**Accepted observed design posture**)

| Do | Do not |
|---|---|
| Store `secretref:…` / `credential://…` in config | Embed live tokens, passwords, private keys in durable YAML as the happy path |
| Resolve only at adapter/service boundary | Log or return resolved secrets from list/show/health |
| Keep provider visible after redaction where designed | Paste live secrets into docs, tickets, or ADR examples |

#### D5 — External config and health surfaces redact by default (**Accepted observed invariant**)

Public and operator-facing results from backend list/show/create/update/health use `redact_backend_config` (or equivalent). Support bundles and architecture examples must use redacted shapes only.

#### D6 — Preferred credential hierarchy is operational guidance; production default is **Proposed** (U-13)

**Current behavior (Accepted as description):** Multiple stores coexist (keyring, encrypted file, secure config fields, external refs, last-resort file JSON). Iroh prefers credential references in config.

**Proposed owner decision (not accepted):** Which store (or ordered policy matrix by deployment class) is the **enforced production default**, and whether dual trees (`backends/*.yaml` vs `backend_configs/`) converge.

#### D7 — Multi-tenant shared state roots and unauthenticated non-loopback MCP HTTP are unsafe defaults (**Accepted risk posture; authn/z details Proposed**)

Shared multi-user mounts for a single kit secret root are **unsupported**. Expanding MCP HTTP beyond loopback without authn/z is an elevation risk; production HTTP authn/z remains tied to U-13 / MCP hardening and must not be documented as “already solved” without confirmation.

#### D8 — Reject inventing a single canonical config API in docs while U-13 is open (**Accepted documentation policy while Proposed**)

Until composition is confirmed, architecture prose **must not** claim “the config API is X only.” Status-honest language: fragmented managers; cite this ADR and the trust guide.

### 3.2 Options (required: Proposed status and material alternatives)

| Option | Summary | Fit / risk |
|---|---|---|
| **A — Record multi-surface + hardened secret paths (this ADR)** | Keep managers; mandate validate/atomic/0o600/refs/redact on sensitive paths; leave production credential default Proposed | Matches tree; needs owner follow-up for U-13 |
| **B — Single ConfigService super-object** | One API and directory schema for all subsystems | Simplifies mental model; large migration; breaks existing paths |
| **C — External-KMS-only production** | Forbid local encrypted files and keyring | Strong multi-tenant story; breaks air-gapped/dev defaults |
| **D — Keyring-only production** | OS secret service is the only allowed store | Good desktop/server hybrid; weak on headless CI without agents |
| **E — Encrypted-file-only production** | Kit secrets tree only | Portable; higher disk disclosure risk if modes fail |
| **F — Collapse dual backend trees now** | Delete StateService `backend_configs/` or BackendManager YAML | Clears U-13 layout dualism; requires code migration + consumer updates |
| **Status quo undocumented** | Guide prose only; no ADR | Agents invent “the” config path; secret examples creep in |

**Selected option (if any):** **Option A** for documentation and integration guidance. Options B–F remain available owner choices; none is Accepted as the sole production composition policy in this record.

---

## 4. Rationale (confidence-labeled)

### 4.1 Why multi-surface configuration

**Accepted:** The repository implements distinct managers for thin config, HLA discovery, named backends, daemon config, secure config, credentials, enhanced secrets, Iroh instance config, and StateService lightweight JSON. Evidence: module inventory in §2.2; trust guide KDOC-019; packaging/CLI entry points that touch different trees.

**Inferred:** Fragmentation grew because subsystems landed with different trust and lifecycle needs (dashboard config vs schema-validated backends vs OS keyring vs Iroh capability refs) rather than from a single incomplete migration.

**Unknown:** Whether long-term product strategy will converge on one ConfigService — unknown / maintainer confirmation needed (U-13).

### 4.2 Why atomic replace and mode 0600

**Accepted:** `BackendManager._write` and Iroh `atomic_write_config` implement temp + fsync + replace with restrictive modes so partial writes and world-readable secret-bearing files are less likely. Migration creates **0o600** `.bak` files before rewrite.

**Accepted:** SecureConfigManager sets keyring directory **0o700** and key/config files **0o600**.

**Inferred:** Atomic rename is preferred over in-place overwrite because crash mid-write would otherwise leave truncated YAML that fails closed on next load—or worse, mixes old and new fields.

**Proposed:** All new secret-bearing durable formats should adopt the same validate → atomic → **0o600** pattern (or stronger OS secret service) rather than plain `write_text`.

### 4.3 Why secret references and redaction

**Accepted:** Backend and Iroh paths prefer or require opaque references; `redact_backend_config` strips sensitive keys and secretref identifiers while leaving provider visible; Iroh security scanning redacts credential/secretref patterns in offline reports.

**Accepted:** Documentation and ADR process forbid live credential examples (template rule; trust guide; this ADR).

**Inferred:** Keeping provider visible after redaction balances supportability (which store to check) against not leaking the record id that might map to a vault path.

**Proposed:** Production profiles should define which providers are allowed (`secure-config`, `enhanced-secrets`, `credential-manager`, `environment`, external KMS adapters) per deployment class.

### 4.4 Threats (why these controls exist)

| Threat | Scenario | Mitigations in this posture | Residual risk |
|---|---|---|---|
| **T1 — Secret disclosure via API/logs** | List/show/health or crash logs emit tokens | Default **redact**; sensitive-key regex; Iroh log redaction; no secrets in ADR examples | Buggy callers with `redact=False`; exception messages echoing tokens |
| **T2 — World-readable secret files** | umask leaves `0644` on credentials or backend YAML | Atomic write **0o600**; keyring **0o700**; operator chmod guidance | Surfaces that still use simple writes; multi-user hosts if root not hardened |
| **T3 — Partial-write corruption** | Process crash mid-config update | Temp + fsync + `os.replace`; `.bak` on migrate | Non-atomic paths (thin config / some JSON) |
| **T4 — Inline secrets in git/docs** | Tokens committed or pasted into tickets | Reference-only rules; doc contract; fail closed on Iroh inline where enforced | Legacy documents may still hold inline fields; redaction must cover them |
| **T5 — Confused deputy / wrong tree wipe** | Operator deletes `~/.ipfs` thinking it is kit cache (or reverse) | Explicit locality separation (D2) | Human error if guides blur roots |
| **T6 — Multi-tenant shared root** | Two users share one kit state directory | Unsupported; prefer separate roots and OS isolation | Misconfigured shared mounts |
| **T7 — Unauthenticated MCP HTTP** | Bind beyond loopback without authn/z | Default trust model is local/stdio/loopback; document elevation | Production authn/z still **Proposed** (U-13) |
| **T8 — Resolved secrets re-persisted** | Adapter writes decrypted values back to YAML | Resolve-late rule; never write resolved secrets to config/receipts | Adapter bugs; recovery tooling that dumps memory |
| **T9 — Backup leakage** | `.bak` or support tarball includes secrets | **0o600** on `.bak`; redacted support bundles only | Operator “tar ~/.ipfs_kit” into public tickets |
| **T10 — Weak crypto fallback** | Missing `cryptography` falls back to weaker paths | Prefer AES-GCM; warn on XOR/legacy; treat as degraded | Environments without optional crypto extra |

### 4.5 Motivations summary (label discipline)

| Motivation claim | Label |
|---|---|
| Multiple config/state managers are implemented on purpose | **Accepted** (behavior) |
| Atomic **0o600** backend/Iroh writes reduce corruption and disclosure | **Accepted** (implementation) |
| Secret references + redaction are intentional leak controls | **Accepted** (implementation) |
| One production credential backend is already chosen | **Unknown** / open **U-13** |
| Dual backend directory trees will be merged | **Proposed** option only |
| Thin config is as hardened as BackendManager | **False if asserted** |

---

## 5. Evidence

| Rank | Claim | Citation |
|---|---|---|
| 1 | Backend atomic write (temp, fchmod **0o600**, fsync, `os.replace`, chmod) and redacted API returns | `ipfs_kit_py/backend_manager.py` |
| 1 | `redact_backend_config`, `_SENSITIVE_RE`, secretref provider-visible redaction | `ipfs_kit_py/backend_registry.py` |
| 1 | Secure config keyring **0o700** / files **0o600**, encrypt/decrypt lifecycle | `ipfs_kit_py/secure_config.py`; `tests/test_secure_config.py`; `tests/unit/test_secure_config.py`; `tests/unit/test_config_save.py` |
| 1 | Iroh atomic config write, `credential://iroh/…` validation, FILE_MODE **0o600** | `ipfs_kit_py/iroh/config.py`; `tests/test_iroh_config.py` |
| 1 | Iroh security log redaction and offline gates | `ipfs_kit_py/iroh/security.py`; `tests/test_iroh_security.py` |
| 1 | Iroh backend secretref approval patterns | `ipfs_kit_py/iroh/backend.py` |
| 1 | Credential manager keyring/file store and list-without-secrets | `ipfs_kit_py/credential_manager.py` |
| 1 | Enhanced secrets **0o600** and AES path | `ipfs_kit_py/enhanced_secrets_manager.py`; `tests/unit/test_aes_encryption.py` |
| 2 | Packaging / scripts that imply kit ops without auto-install | `pyproject.toml`; env `IPFS_KIT_AUTO_INSTALL_BINARIES` default off |
| 3 | Directory map, state families, secret hierarchy, trust boundaries | `docs/architecture/CONFIGURATION_STATE_AND_TRUST.md` (KDOC-019) |
| 3 | Iroh normative security and threat model | `docs/iroh/security.md`, `docs/iroh/threat-model.md`, credential-rotation runbooks |
| 4 | Unresolved U-13 and ADR slot | `SOURCE_OF_TRUTH_MAP.md` aggregate U-13; `decisions/README.md` §8 |
| 5 | Operator-facing credential guides (supporting; not authority for Accepted production default) | `docs/credential_management.md`, `docs/guides/SECURE_CREDENTIALS_GUIDE.md`, `docs/features/ENCRYPTED_CONFIG_GUIDE.md` |

**Evidence that is explicitly insufficient for Accepted status on U-13 composition:**

- Presence of a preferred hierarchy table as proof that keyring (or KMS) is the enforced production default.  
- Existence of both `backends/*.yaml` and `backend_configs/` as proof one is deprecated.  
- Documentation-only claims of a single “ConfigManager” without packaging and call-graph confirmation.  
- Examples that would require live credentials (forbidden; never promote via sample tokens).

---

## 6. Consequences

### 6.1 Positive

- **Honest locality:** Operators stop treating one path as universal config.  
- **Safer durable writes:** Validate + atomic replace + **0o600** reduces corruption and casual disclosure on hardened paths.  
- **Leak-resistant APIs:** Default redaction and secretref-shaped storage reduce accidental exposure in list/health/support flows.  
- **Clear threat framing:** T1–T10 give review and ops a shared language.  
- **Reviewable defaults later:** U-13 confirmation has fixed options (B–F) and acceptance criteria.

### 6.2 Negative / costs

- **Cognitive load:** Multiple managers, trees, and stores.  
- **Uneven hardness:** Not every write path is atomic **0o600** today—operators must know which surface holds secrets.  
- **No single getting-started credential story** until production default is Accepted.  
- **Dual backend trees** can confuse which document is authoritative for a given CLI/MCP path.  
- **Migration cost** if owners later choose B or F (unified service or tree collapse).

### 6.3 Limitations (explicit)

| Limitation | Impact |
|---|---|
| **L1 — No universal merge/precedence across all managers** | Operators must apply per-surface rules; agents must not invent a global overlay |
| **L2 — Redaction is not encryption** | Process memory and `redact=False` call sites can still see secrets |
| **L3 — File modes depend on correct write paths** | Legacy or third-party writers may still create world-readable files |
| **L4 — Keyring availability varies** | Headless/CI may fall back to files; file store has higher disclosure risk |
| **L5 — XOR/legacy crypto may appear if extras missing** | Degraded encryption is not production-ready |
| **L6 — MCP HTTP production authn/z not settled here** | Must not claim full remote multi-tenant safety from this ADR alone |
| **L7 — Cluster secret layout varies by stack (U-08)** | Cluster authority is ADR-0008; only secret-handling posture is in scope |
| **L8 — This ADR does not ship code changes** | Closing dual trees or unifying APIs requires follow-up implementation tasks |

### 6.4 Migration and compatibility

- New durable secret-bearing formats **must** use validate → atomic replace → **0o600** (or OS secret service / external KMS references).  
- Prefer storing **references** in backend/Iroh config; migrate inline legacy fields with backup (`.bak`) and rotation.  
- Architecture guides cite this ADR with **status-honest** language: observed invariants Accepted; production credential default and tree composition **Proposed**.  
- Do not break Iroh `credential://` or backend `secretref:` shapes without a migration ADR.  
- Support bundles: redacted only; never attach raw `credentials.json`, `secrets.enc.json`, or `.keyring/master.key`.

### 6.5 Security and trust

- **Threats:** see §4.4 (T1–T10).  
- Never log or document live tokens, passwords, private keys, cluster secrets, resolved secretref values, or Fernet/AES master key bytes.  
- Prefer `secretref:<provider>:<id>` / `credential://iroh/<id>` **shapes** in examples—never filled with real identifiers that map to production vault paths if those ids are sensitive in the threat model.  
- Credentials: **none in this ADR**; no sample tokens, keys, or host-specific secret paths.

### 6.6 Testing and verification

Tests and hooks that encode or protect the decision surface:

| Concern | Focused tests / hooks |
|---|---|
| Backend atomic write + redaction | Backend manager/registry unit tests; `backend_manager.py` / `backend_registry.py` |
| Secure config modes and encryption | `tests/test_secure_config.py`, `tests/unit/test_secure_config.py`, `tests/unit/test_config_save.py` |
| Iroh config atomic write + credential refs | `tests/test_iroh_config.py` |
| Iroh security redaction gates | `tests/test_iroh_security.py` |
| AES / secrets | `tests/unit/test_aes_encryption.py` |
| Daemon config | `tests/test_daemon_config*.py`, `tests/test_enhanced_daemon_config.py` |
| Offline install posture | Import/packaging tests with `IPFS_KIT_AUTO_INSTALL_BINARIES=0` |

Commands that re-check this ADR body:

```bash
test -s docs/architecture/decisions/0007-configuration-state-and-secret-references.md && rg -q "redact" docs/architecture/decisions/0007-configuration-state-and-secret-references.md
```

---

## 7. Alternatives considered

| Alternative | Why considered | Why rejected / deferred | Confidence |
|---|---|---|---|
| Status quo undocumented (no ADR) | Least writing | Agents invent canonical paths and paste credentials into examples | **Accepted** as insufficient |
| Single ConfigService now (Option B) | Simplifies mental model | Large migration; not implemented; would require Accepted U-13 | **Proposed** future only |
| External-KMS-only (Option C) | Strong multi-tenant posture | Breaks offline/dev; not enforced in code | **Proposed** / deferred |
| Keyring-only (Option D) | Avoids plaintext files | Weak on headless agents without secret service | **Proposed** / deferred |
| Encrypted-file-only (Option E) | Portable defaults | Higher disk disclosure if modes fail; weaker than KMS | **Proposed** / deferred |
| Collapse dual backend trees immediately (Option F) | Clears layout dualism | Consumers and StateService paths still use both; needs code task | **Proposed** / deferred |
| Allow inline secrets as first-class durable form | Easier demos | High leak risk; conflicts with Iroh and redaction design | **Rejected** as default |
| Document live credential examples “for clarity” | Teaching aid | Violates documentation contract and ADR template; amplifies T1/T4 | **Rejected** |
| Treat redaction as sufficient access control | Simpler ops story | Redaction does not authenticate callers (L2) | **Rejected** |

At least one alternative (including status quo) is required — satisfied above.

---

## 8. Unknowns and owner confirmation

| Field | Value |
|---|---|
| **Confirmation owner** | Platform / operations maintainers (config/state composition and production credential backend); MCP owners for HTTP authn/z adjacent items |
| **Confirmation question** | For production deployments, which credential backend (external KMS references, OS keyring, encrypted kit secrets, secure-config fields, or an ordered matrix by profile) is **enforced by default**, and should `backends/*.yaml` and `backend_configs/` converge to one layout? |
| **What “Accepted” requires** | Maintainer statement plus either packaging/runtime enforcement evidence or an explicit compatibility window; update this ADR banner/§3 and index row |
| **Blocking for** | Guides claiming a single config API; production credential SLAs; multi-tenant shared-host recipes |
| **Related U-IDs / conflicts** | **U-13**; adjacent U-08 (cluster secrets), U-11 (MCP trees), U-16 (daemon managers) |

**Open unknowns:**

1. Enforced production credential backend default — unknown / maintainer confirmation needed (U-13).  
2. Whether dual backend config trees remain permanent or converge — unknown / maintainer confirmation needed.  
3. Production MCP HTTP authentication/authorization standard beyond loopback — unknown / maintainer confirmation needed (U-13 / MCP hardening).  
4. Whether thin `config.py` and StateService JSON will be upgraded to the same atomic **0o600** pipeline — unknown / maintainer confirmation needed.  
5. Long-term single ConfigService product intent — unknown / maintainer confirmation needed.

---

## 9. Supersession and relationships

| Relation | ADR / doc |
|---|---|
| Supersedes | none |
| Superseded by | none |
| Related ADRs | ADR-0002 (backend registry validation); ADR-0003 (MCP runtime / bind trust); ADR-0005 (journal/WAL state under kit root); ADR-0006 (transport credential models); ADR-0008 (cluster secret authority) |
| Architecture guides | [`../CONFIGURATION_STATE_AND_TRUST.md`](../CONFIGURATION_STATE_AND_TRUST.md) (primary), [`../SYSTEM_OVERVIEW.md`](../SYSTEM_OVERVIEW.md), [`../MCP_CONTROL_PLANE.md`](../MCP_CONTROL_PLANE.md), [`../RUNTIME_AND_ENTRYPOINTS.md`](../RUNTIME_AND_ENTRYPOINTS.md) |
| Normative Iroh | `docs/iroh/security.md`, `threat-model.md`, `credential-rotation.md`, `install-lifecycle.md`, `service-lifecycle.md` |
| Source-of-truth map | [`../SOURCE_OF_TRUTH_MAP.md`](../SOURCE_OF_TRUTH_MAP.md) (U-13) |

---

## 10. Follow-up actions

| Action | Owner | Notes |
|---|---|---|
| Confirm production credential default and dual-tree policy | Platform / ops maintainers | Promote U-13 items; update §3 selected option |
| Keep architecture guide status-honest vs this ADR | Docs maintainers | Cite Proposed vs Accepted observed language |
| Align weaker write paths with atomic **0o600** where secrets may appear | Engineering (post-acceptance) | Thin config / StateService JSON audit |
| MCP HTTP production authn/z hardening | MCP maintainers | Adjacent U-13; do not claim solved here |
| Index row update when body lands | Framework/index owner (KDOC-020 policy) | This task must **not** edit `decisions/README.md` |
| Never add live credential examples to docs/ADRs | All contributors | Process invariant |

---

## 11. Review checklist (authors)

- [x] Filename is `0007-configuration-state-and-secret-references.md`  
- [x] Banner **Decision status** matches §3 **Status** (`Proposed`)  
- [x] **Current behavior** is evidence-backed and separate from the proposal  
- [x] No present-tense “the system always uses one config API” for Proposed-only intent  
- [x] Every material *why* uses **Accepted / Proposed / Inferred / Unknown**  
- [x] No Inferred or Unknown claim is written as Accepted history  
- [x] Evidence table prefers ranks 1–4 for Accepted claims  
- [x] Alternatives include status quo and explicit rejects  
- [x] Confirmation owner and question filled (Proposed)  
- [x] Threats, consequences, alternatives, and limitations included  
- [x] No secrets, live tokens, or host-specific credential paths  
- [x] `docs/architecture/decisions/README.md` was **not** edited by this task  
- [x] Related architecture guide will cite this ADR with status-honest language  

---

## Appendix A — Status and confidence cheat sheet

**Decision status (header / §3):**  
`Proposed` · `Accepted` · `Rejected` · `Superseded` · `Deprecated` · `Unknown`

**Rationale confidence (§4 markers):**

```markdown
**Accepted:** …
**Proposed:** …
**Inferred:** …
**Unknown:** … unknown / maintainer confirmation needed
```

**Forbidden promotion paths without evidence + confirmation rules:**

- Inferred rationale → Accepted decision narrative  
- Proposed production credential default → Accepted “we use keyring only” in guides  
- Documentation-only claim → Accepted universal config API  

See [`README.md`](./README.md) §§3–4 for full promotion rules.

---

## Appendix B — Quick operator checklist (no secrets)

1. Identify roots in use: kit data-dir, `IPFS_PATH`, Iroh instance root.  
2. Prefer secret **references** in backend/Iroh config; store material in keyring/KMS/encrypted store.  
3. Confirm sensitive files are mode **0600** and secret directories **0700** where applicable.  
4. Use list/show/health paths that **redact** by default before sharing output.  
5. After migrate, retain `.bak` only as long as policy allows; protect it as secret-bearing.  
6. Never paste raw credential files, keyring material, or unredacted backend YAML into tickets.

---

*End of ADR-0007 (KDOC-027). Decision status remains **Proposed** for U-13 owner composition until confirmation.*
