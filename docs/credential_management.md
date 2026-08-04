# Credential management

- Status: current operator/reference guide (KDOC-034)
- Authority class: Reference (implementation-aligned)
- Architecture: [CONFIGURATION_STATE_AND_TRUST.md](./architecture/CONFIGURATION_STATE_AND_TRUST.md)
- Backend documents & redaction: [reference/storage_backends.md](./reference/storage_backends.md)
- Iroh rotation runbook: [iroh/credential-rotation.md](./iroh/credential-rotation.md)

IPFS Kit components often need credentials for remote storage and services
(S3-compatible APIs, Storacha, Filecoin/Lotus, Hugging Face, IPFS Cluster
secrets, Iroh node keys and capabilities). This guide describes **where secrets
live**, **how references appear in configuration**, and **how to use APIs without
leaking material**.

> **Never show real credentials.** Documentation, tickets, CI logs, MCP tool
> output, and architecture diagrams must use placeholders or **references only**.
> Do not paste tokens, passwords, private keys, write capabilities, cluster
> secrets, or resolved `secretref` / `credential://` values into shared channels.

---

## 1. Mental model

| Layer | Purpose | Secret material allowed? |
|---|---|---|
| Named backend YAML (`~/.ipfs_kit/backends/*.yaml`) | Type + non-secret params | **Schema-validated Iroh:** references only. **Legacy:** avoid inline secrets; redaction applies if present |
| Credential / secret stores | Hold or resolve secret values | Yes (protected storage) |
| Environment variables | Operator injection | Yes, but short-lived preferred; names appear in docs, not values |
| Live adapters / kits | Use resolved secrets in memory | In process only — never re-persist resolved values into YAML |

**Hierarchy of preference** (operational recommendation; production backend choice
among stores remains multi-path — see trust guide U-13 / planned ADR work):

1. External secret manager / KMS with **references only** in config
2. OS keyring via `CredentialManager` (`credential_store=keyring`)
3. Enhanced encrypted secrets (`EnhancedSecretManager`, AES-256-GCM)
4. Secure config keyring (`SecureConfigManager`)
5. File credentials JSON at mode `0600` (convenient; higher disclosure risk)
6. Long-lived process environment (last resort on multi-tenant hosts)

---

## 2. Secret reference formats

### 2.1 Named-backend `secretref:` (Iroh closed schema)

Iroh validated documents accept credential fields only as:

```text
secretref:<provider>:<id>
```

| Provider | Typical resolution source |
|---|---|
| `secure-config` | Secure / encrypted configuration plane |
| `enhanced-secrets` | `EnhancedSecretManager` records under `~/.ipfs_kit/secrets/` |
| `credential-manager` | `CredentialManager` named entries |
| `environment` | Process environment variable named by `<id>` |

Example (from `config/iroh-backend.example.yaml` — **not** live secrets):

```yaml
credentials:
  node_key_ref: secretref:enhanced-secrets:iroh-primary-node-key
  write_capability_ref: secretref:enhanced-secrets:team-archive-write-capability
```

Public APIs (`show_backend`, create/update results, health/info) redact the
identifier portion:

```text
secretref:enhanced-secrets:<redacted>
```

Provider names may remain visible for diagnostics. On-disk YAML retains the full
reference string under mode `0600`; resolved material must never be written back.

### 2.2 Iroh service `credential://` references

Iroh **service** configuration (instance identity, separate from named-backend
YAML) uses opaque URIs of the form:

```text
credential://iroh/<opaque-name>
```

These appear in service config modules (`iroh/config.py`) and rotation runbooks.
Treat both the URI path and any resolved key material as secret metadata /
secrets respectively. See [iroh/security.md](./iroh/security.md) and
[iroh/credential-rotation.md](./iroh/credential-rotation.md).

---

## 3. `CredentialManager`

**Module:** `ipfs_kit_py/credential_manager.py`

Unified store for **named credential sets** per service (`s3`, `storacha`,
`filecoin`, `ipfs`, `ipfs_cluster`, …). Consumers include migration tools and
storage paths that request credentials by service + name.

### 3.1 Configuration

Default config keys (constructor `config` dict):

| Key | Default | Meaning |
|---|---|---|
| `credential_store` | `"keyring"` | `"keyring"` preferred; `"file"` fallback |
| `credential_file_path` | `~/.ipfs_kit/credentials.json` | File store path |
| `ipfs_credentials_path` | `~/.ipfs` | Source for optional IPFS identity / API / cluster_secret load |
| `encrypt_file_credentials` | `True` | Intended file encryption flag (operators must still enforce permissions) |
| `rotation_check_interval` | `86400` | Rotation check interval (seconds) |

If `credential_store=keyring` but the optional `keyring` package is missing, the
manager logs a warning and falls back to file storage.

### 3.2 Storage behavior

| Store | Behavior |
|---|---|
| **Keyring** | `keyring.set_password("ipfs_kit_py", "{service}_{name}", json_record)` |
| **File** | JSON map at `credential_file_path`; operators should `chmod 600` the file and restrict the parent directory |

Each stored record wraps:

- `credentials` — service-specific fields
- `metadata` — `added_at`, `last_used`, `use_count`, `id` (UUID)

### 3.3 IPFS material auto-load

On init, if present under `ipfs_credentials_path` (default `~/.ipfs`):

| File | Service / name | Sensitivity |
|---|---|---|
| `identity` | `ipfs` / `identity` | **Secret** (node private identity material) |
| `api` | `ipfs` / `api` | Multiaddr string (treat as sensitive in shared hosts) |
| `cluster_secret` | `ipfs_cluster` / `secret` | **Secret** |

Never export these into tickets or docs.

### 3.4 API surface

| Method | Role |
|---|---|
| `add_credential(service, name, credentials)` | Generic upsert |
| `get_credential(service, name="default")` | Returns credential **values** (handle carefully) |
| `list_credentials(service=None)` | **Metadata only** — no secret fields |
| `remove_credential(service, name)` | Delete from keyring and/or file |
| `add_s3_credentials` / `get_s3_credentials` | S3-shaped helpers |
| `add_storacha_credentials` / `get_storacha_credentials` | Storacha/W3 token helpers |
| `add_filecoin_credentials` / `get_filecoin_credentials` | Filecoin API helpers |
| `get_ipfs_credentials` | IPFS-named entries |

Helper field shapes (for implementers — **do not put real values in docs or VCS**):

| Helper | Fields stored under `credentials` |
|---|---|
| S3 | `type=s3`, `aws_access_key_id`, `aws_secret_access_key`, optional `endpoint_url`, `region` |
| Storacha | `type=storacha`, `api_token`, optional `space_did` |
| Filecoin | `type=filecoin`, `api_key`, optional `api_secret`, `wallet_address`, `provider` |

### 3.5 Safe usage examples

Examples use **placeholders** and print only presence / redacted prefixes.

```python
from ipfs_kit_py.credential_manager import CredentialManager

# Prefer keyring when the optional dependency is installed.
cred_manager = CredentialManager(
    config={
        "credential_store": "keyring",  # falls back to file if keyring unavailable
        # "credential_file_path": "~/.ipfs_kit/credentials.json",
    }
)

# --- Add (values come from your secret process, not from this file) ---
# Supply real values only from env, stdin, or a secret manager — never hardcode.

import os

access_key = os.environ.get("AWS_ACCESS_KEY_ID")
secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
if access_key and secret_key:
    cred_manager.add_s3_credentials(
        name="default",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region=os.environ.get("AWS_DEFAULT_REGION"),
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL"),
    )

storacha_token = os.environ.get("STORACHA_API_KEY") or os.environ.get("W3_STORE_TOKEN")
if storacha_token:
    cred_manager.add_storacha_credentials(
        name="default",
        api_token=storacha_token,
        space_did=os.environ.get("STORACHA_SPACE_DID"),  # optional
    )

# --- List (safe for diagnostics) ---
for info in cred_manager.list_credentials():
    print(f"service={info['service']} name={info['name']} type={info.get('credential_type')}")

# --- Retrieve (unsafe to log) ---
s3 = cred_manager.get_s3_credentials("default")
if s3:
    key_id = s3.get("aws_access_key_id") or ""
    print(f"S3 key id present: {bool(key_id)}; prefix={key_id[:4]}…" if key_id else "missing")
    # Use with boto3/session in-process; do not print secret_key.

# --- Remove ---
cred_manager.remove_credential(service="filecoin", name="lab")
```

**Do:**

- Use `list_credentials` for “is it configured?” checks.
- Pass values from environment or a secret manager into `add_*`.
- Restrict file permissions when using the file store:  
  `chmod 600 ~/.ipfs_kit/credentials.json`

**Do not:**

- Log or serialize `get_credential` results to shared logs.
- Commit `credentials.json` or keyring exports.
- Embed tokens in backend YAML when a reference form exists.

---

## 4. Related secret planes

These are **adjacent** systems; choose one primary store per secret class to
avoid split-brain rotation.

### 4.1 Enhanced secrets manager

**Module:** `ipfs_kit_py/enhanced_secrets_manager.py`  
**Location:** `~/.ipfs_kit/secrets/` (`secrets.enc.json`, `metadata.json`, `audit.log`)

- Prefer **AES-256-GCM** (`cryptography` present); XOR path is legacy / not
  production-ready.
- Files intended mode `0600`.
- Suitable provider target for `secretref:enhanced-secrets:<id>`.
- Diagnostics: counts, types, rotation ages, audit **event kinds** — never
  decrypted values.

Migration helper: root `migrate_secrets.py` (XOR → AES). Use dry-run where
available.

### 4.2 Secure configuration manager

**Modules:** `secure_config.py`, `cli_secure_config.py`  
**Location:** kit `data_dir` (default `~/.ipfs_kit`) with `.keyring/` master key material

- Encrypts sensitive fields in configuration documents.
- Keyring directory should be `0700`; keys `0600`.
- Target for `secretref:secure-config:<id>` style references when wired.

### 4.3 Environment variables

Common patterns used by kits and guides (names only):

| Variable (examples) | Typical consumer |
|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `AWS_ENDPOINT_URL` | S3 / boto3 paths |
| `STORACHA_API_KEY`, `STORACHA_API_URL`, `W3_STORE_TOKEN` | Storacha / w3 clients |
| `HF_TOKEN`, `HUGGINGFACE_TOKEN` | Hugging Face kits |
| `IPFS_KIT_*` service-prefixed vars | Various kit/MCP secure-config loaders |

For Iroh named backends, prefer:

```text
secretref:environment:MY_ENV_VAR_NAME
```

so documents stay free of values. Rotate by changing the environment / secret
store and restarting processes that already resolved the old value.

### 4.4 MCP credential controllers

HTTP/MCP controllers (`mcp/controllers/credential_controller*.py`) expose add
endpoints for S3, Storacha, and Filecoin that delegate to `CredentialManager`.
Treat those endpoints as **highly privileged**: authenticate, audit, and never
echo secrets in responses or logs.

---

## 5. Binding credentials to backends

| Backend maturity | Recommended pattern |
|---|---|
| **Iroh (schema-validated)** | Only `secretref:…` fields under `credentials` in YAML; resolve at adapter/service boundary |
| **Legacy named YAML** | Non-secret fields in YAML; resolve keys via env / `CredentialManager` / enhanced secrets at kit or adapter init |
| **Kit metadata init** (older APIs) | May accept metadata dict keys or env fallbacks — still use placeholders in examples |
| **MCP storage managers** | Often read `~/.ipfs_kit/credentials.json` or env; separate from `BackendManager` documents |

**Redaction on backend documents** is owned by `redact_backend_config` in
`backend_registry.py`. Public list/show/info paths default to redacted copies.
Internal `get_backend_config(name, redact=False)` is for last-moment resolution
only.

---

## 6. Rotation and recovery (summary)

| Secret class | Guidance |
|---|---|
| Iroh node identity / write capability / read ticket | Follow [iroh/credential-rotation.md](./iroh/credential-rotation.md); rotate provider records, then atomic ref update; dual-control for exports |
| S3 / cloud API keys | Re-`add_*` under same name (overwrite) or new name + cutover; revoke old keys at provider |
| Storacha / HF tokens | Same as above; update env or manager entries |
| IPFS Cluster secret | Treat as cluster-wide secret; coordinate all members; never log |
| File store compromise | Rotate **all** secrets that ever lived in the file; fix permissions; prefer keyring/KMS afterward |

After rotation, restart long-lived processes that may have cached credentials in
memory (`credential_cache` on `CredentialManager`, open SDK clients).

---

## 7. Safe diagnostics checklist

| Safe | Unsafe |
|---|---|
| `list_credentials()` service/name presence | Printing `get_credential` / `get_s3_credentials` dumps |
| Redacted `show_backend` / `get_backend_info` | `cat ~/.ipfs_kit/credentials.json` into tickets |
| Confirm file mode `0600` / keyring backend name | Pasting `secretref` **identifiers** into public issues if your threat model treats ids as sensitive |
| Encryption status helpers without key bytes | Committing example JSON that still contains “sample” tokens resembling real formats |

---

## 8. Integration map

```text
Operator / automation
        │
        ├─► CredentialManager (keyring | file)
        ├─► EnhancedSecretManager (AES store)
        ├─► SecureConfigManager (encrypted config fields)
        ├─► Environment variables
        └─► External KMS / secret manager
                │
                ▼  (references only for schema-validated backends)
        BackendManager YAML  ──validate/redact──► public CLI / MCP
                │
                ▼  (resolve once, in process)
        Live adapter / Iroh client / kit SDK
```

Related modules:

| Module | Role |
|---|---|
| `credential_manager.py` | Named multi-service credentials |
| `enhanced_secrets_manager.py` | Encrypted secret records + audit |
| `aes_encryption.py` | AES-GCM primitives |
| `cli_secure_config.py` / `secure_config.py` | Encrypted config keyring |
| `backend_registry.redact_backend_config` | Document redaction |
| `iroh/security.py` | Iroh secret/credential scrubbing patterns |
| `mcp/controllers/credential_controller*.py` | HTTP credential add/list surfaces |

---

## 9. Related documentation

| Doc | Role |
|---|---|
| [reference/storage_backends.md](./reference/storage_backends.md) | Backend types, schema maturity, secretref in YAML |
| [architecture/CONFIGURATION_STATE_AND_TRUST.md](./architecture/CONFIGURATION_STATE_AND_TRUST.md) | State roots, trust boundaries, process lifecycle |
| [architecture/STORAGE_BACKEND_SYSTEM.md](./architecture/STORAGE_BACKEND_SYSTEM.md) | Plugin vs document vs adapter |
| [iroh/named-backends.md](./iroh/named-backends.md) | Iroh document create/show/migrate |
| [iroh/credential-rotation.md](./iroh/credential-rotation.md) | Production rotation procedure |
| [guides/SECURE_CREDENTIALS_GUIDE.md](./guides/SECURE_CREDENTIALS_GUIDE.md) | Older MCP-oriented setup notes (qualify against this page for store defaults) |

---

*End of credential management reference (KDOC-034).*
