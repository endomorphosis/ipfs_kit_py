# Backend Support Matrix (KITA-042)

This document is the human-readable companion to
[`backend_support_manifest.json`](backend_support_manifest.json)
(`BackendSupportManifest@1`). Together they publish the **joined backend
support matrix and all-interface certification** for the
`ipfs-kit-runtime-readiness-v1` program.

## Authority

BackendSpec@1 (ipfs_kit_py.backends.spec) is the inventory authority. This joined matrix projects every registry and documented name exactly once with canonical name, aliases, schema, factory, capabilities, tier, limitations, evidence CIDs and freshness. Live storage selection requires current external/service evidence and a repository-owned canonical factory. Stale or missing external evidence demotes or blocks rather than silently passing. Routing never selects unsupported capabilities or hidden fallbacks. Python/CLI/MCP/MCP++ surfaces project the same advertised operations under AllInterfaceParityPolicy@1.

| Role | Location |
| --- | --- |
| Inventory | `ipfs_kit_py.backends.spec` (`BackendSpec@1`) |
| Registry | `ipfs_kit_py.backend_registry` |
| Schemas | `ipfs_kit_py.backend_schemas` |
| Classification | `ipfs_kit_py.backends.provider_adapters` |
| Interface parity | `docs/runtime_readiness/interface_manifest.json` |
| External receipts | `docs/runtime_readiness/backend_external_receipts` |
| Service receipts | `docs/runtime_readiness/backend_service_receipts` |
| Machine matrix | `docs/runtime_readiness/backend_support_manifest.json` |
| Validation suite | `tests/runtime_readiness/backends/test_joined_backend_matrix.py` |

## Policy (fail-closed)

| Rule | Statement |
| --- | --- |
| Presence ≠ support | Registry/schema presence does not imply storage readiness. |
| Evidence demotion | Stale or missing external evidence **demotes or blocks**; it never silently passes. |
| No hidden fallback | Service unavailability issues a blocked receipt; no local/mock substitute. |
| Routing honesty | Routing selects only runtime-ready storage with current evidence and declared capability. |
| Interface parity | Advertised operations pass Python/CLI/MCP/MCP++ semantic parity. |
| Secrets | Credentials only via authorized secret references; never in receipts/logs/status. |

Production requires: `live_conformance_receipt`, `complete_required_operations`, `current_tree_evidence`, `current_external_or_service_receipt`, `canonical_runtime_factory`, `no_open_p0_defect_on_required_path`.

## Summary

| Metric | Value |
| --- | --- |
| Canonical backends | 27 |
| Public name spellings | 37 |
| Inventory production | 0 |
| Live production | 0 |
| Storage-selectable now | 0 |

### By inventory tier

| Tier | Count |
| --- | ---: |
| `conditional` | 1 |
| `configuration-only` | 22 |
| `unsupported` | 4 |

### By disposition (joined live)

| Disposition | Count |
| --- | ---: |
| `conditional-receipt-required` | 1 |
| `configuration-only` | 22 |
| `unsupported` | 4 |

## Evidence authority

- Observation time (UTC): `2026-08-03T12:00:00Z`
- External receipt index CID: `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`
- Active external receipts: **0** (empty authority is explicit, not production evidence)
- MCP default manager service status: **blocked** (CID `bafkreibsxswhkrf3cydetszd3l4sf5b7nucywzfys26htufulavi4qr5ni`)

## Subsystem joins

The matrix joins backend-family evidence with current subsystem receipts (interfaces, auth/MCP++, WAL, replication, GraphRAG, ARC, VFS, buckets). Dependency tasks: `KITA-013`, `KITA-017`, `KITA-021`, `KITA-025`, `KITA-029`, `KITA-033`, `KITA-037`, `KITA-040`, `KITA-041`.

| Subsystem | Status | Evidence CID |
| --- | --- | --- |
| `arc` | joined (`current-tree-artifact`) · `docs/runtime_readiness/arc_conformance.json` | `bafkreid5kc2oqzya6ffqclq7p7duk77q4pwafezuvq7tpzhm63g4udpp5y` |
| `auth_mcplusplus` | joined (`current-tree-artifact`) · `docs/runtime_readiness/mcplusplus_conformance.json` | `bafkreiaz7tixetqwzqdpz77kvynnqc6tgcqwcurme2nu2k6mdg2w3skbry` |
| `buckets` | joined (`current-tree-artifact`) · `docs/runtime_readiness/bucket_conformance.json` | `bafkreiflkg2g77v5syyvrxeustuq7e4cyqjxqb62wcr6dnvbpfxj4awwu4` |
| `graphrag` | joined (`current-tree-artifact`) · `docs/runtime_readiness/graphrag_conformance.json` | `bafkreiagc5qryxx2r36amgeopysnd7yejsbkezsmdohfq53ogx65hm6tfe` |
| `interfaces` | joined (`current-tree-artifact`) · `docs/runtime_readiness/interface_manifest.json` | `bafkreiabyiflhfavqvd227kcf4ep36yyk57pvssowvrxu4tqxzwpt5ht6q` |
| `replication` | joined (`current-tree-artifact`) · `docs/runtime_readiness/replica_conformance.json` | `bafkreigfuxblflzhx3apqk672kyzzu6iqhtypaqmomu4k4dtofaazcrcxq` |
| `vfs` | joined (`current-tree-artifact`) · `docs/runtime_readiness/vfs_conformance.json` | `bafkreifs3h73e77axtqbqdzlijyrysrib6kbgpd46spu4frdqvlk3kj3si` |
| `wal` | referenced (`joined-by-dependency-task`) · `dependency-suite` | `—` |

## Joined backend matrix

Every registry/documented name appears **exactly once** as a canonical row. Aliases are listed on that row only.

| Canonical | Aliases | Factory | Capabilities | Inventory tier | Live tier | Disposition | Evidence freshness | Storage selectable | Evidence CIDs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `arrow` | — | — | — | `unsupported` | `unsupported` | `unsupported` | `not-applicable` | no | — |
| `cluster` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `digitalocean` | `digital-ocean` | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `estuary` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `filecoin` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `filecoin_pin` | `filecoin-pin` | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `filesystem` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `ftp` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `gdrive` | `g-drive`, `google-drive`, `google_drive` | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `github` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `huggingface` | `hugging-face` | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `ipfs` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `ipfs_cluster` | `ipfs-cluster` | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `ipfs_cluster_follow` | `ipfs-cluster-follow` | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `iroh` | — | `create_filesystem` | `configuration`, `health`, `runtime_factory`, `storage` | `conditional` | `conditional` | `conditional-receipt-required` | `missing` | no | `bafkreiagzzvmwpn…` |
| `lassie` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `local` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `local_fs` | `local-fs` | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `local_storage` | `local-storage` | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `lotus` | — | — | — | `unsupported` | `unsupported` | `unsupported` | `not-applicable` | no | — |
| `minio` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `parquet` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `s3` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `saturn` | — | — | — | `unsupported` | `unsupported` | `unsupported` | `not-applicable` | no | — |
| `sshfs` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `storacha` | — | — | `configuration`, `health` | `configuration-only` | `configuration-only` | `configuration-only` | `not-required-for-configuration-only` | no | `bafkreiagzzvmwpn…` |
| `synapse` | — | — | — | `unsupported` | `unsupported` | `unsupported` | `not-applicable` | no | — |

## Limitations and certification receipts

### `arrow`

- **Aliases:** none
- **Schema type:** `arrow` (available=False, health=`not-available`)
- **Factory:** none
- **Capabilities:** none
- **Secret fields:** none
- **Advertised operations:** none (unsupported)
- **Interface names (CLI/MCP/docs):** `arrow`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`unsupported`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-arrow` · status=`excluded` · availability=`unsupported`
- **Limitations:**
  - A dashboard schema existed, but no backend plugin or runtime factory is registered.
  - No backend plugin or runtime factory is registered.
  - All storage operations reject as typed unsupported before side effects.
  - Routing must never select this type for storage.
- **Evidence CIDs:** none (freshness=`not-applicable`)

### `cluster`

- **Aliases:** none
- **Schema type:** `cluster` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `cluster`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-cluster` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `digitalocean`

- **Aliases:** `digital-ocean`
- **Schema type:** `digitalocean` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `token`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `digitalocean`, `digital-ocean`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-digitalocean` · status=`configuration-only` · availability=`configuration-only`
- **Service family:** `s3-compatible` via `ipfs_kit_py.backends.s3_backend.S3BackendAdapter` · status=`service-gated`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `estuary`

- **Aliases:** none
- **Schema type:** `estuary` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `api_key`, `token`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `estuary`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-estuary` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `filecoin`

- **Aliases:** none
- **Schema type:** `filecoin` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `filecoin`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-filecoin` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `filecoin_pin`

- **Aliases:** `filecoin-pin`
- **Schema type:** `filecoin_pin` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `api_key`, `token`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `filecoin_pin`, `filecoin-pin`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-filecoin_pin` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `filesystem`

- **Aliases:** none
- **Schema type:** `filesystem` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `filesystem`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-filesystem` · status=`configuration-only` · availability=`configuration-only`
- **Hermetic reference:** `ipfs_kit_py.backends.filesystem_backend.HermeticFilesystemAdapter` · scope=`local-hermetic-reference-only` · live_provider=False
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `ftp`

- **Aliases:** none
- **Schema type:** `ftp` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `password`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `ftp`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-ftp` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `gdrive`

- **Aliases:** `g-drive`, `google-drive`, `google_drive`
- **Schema type:** `gdrive` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `token`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `gdrive`, `g-drive`, `google-drive`, `google_drive`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-gdrive` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `github`

- **Aliases:** none
- **Schema type:** `github` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `token`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `github`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-github` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `huggingface`

- **Aliases:** `hugging-face`
- **Schema type:** `huggingface` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `token`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `huggingface`, `hugging-face`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-huggingface` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `ipfs`

- **Aliases:** none
- **Schema type:** `ipfs` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `ipfs`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-ipfs` · status=`configuration-only` · availability=`configuration-only`
- **Hermetic reference:** `ipfs_kit_py.backends.ipfs_backend.HermeticIPFSFixtureAdapter` · scope=`fixture-only; not live IPFS provider certification` · live_provider=False
- **Service family:** `kubo-ipfs` via `ipfs_kit_py.backends.ipfs_backend.IPFSBackendAdapter` · status=`blocked`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `ipfs_cluster`

- **Aliases:** `ipfs-cluster`
- **Schema type:** `ipfs_cluster` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `ipfs_cluster`, `ipfs-cluster`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-ipfs_cluster` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `ipfs_cluster_follow`

- **Aliases:** `ipfs-cluster-follow`
- **Schema type:** `ipfs_cluster_follow` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `ipfs_cluster_follow`, `ipfs-cluster-follow`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-ipfs_cluster_follow` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `iroh`

- **Aliases:** none
- **Schema type:** `iroh` (available=True, health=`structured`)
- **Factory:** `create_filesystem`
- **Capabilities:** `configuration`, `health`, `runtime_factory`, `storage`
- **Secret fields:** `token`
- **Advertised operations:** `health`, `put`, `get`, `stream`, `read_range`, `list`, `get_metadata`, `set_metadata`, `delete`
- **Interface names (CLI/MCP/docs):** `iroh`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_CAPABILITY_MISSING`
- **Semantics:** durability=`receipt-gated; mutating ops require idempotency keys; no silent partial success`; integrity=`content CID verification on read; integrity failure is typed and non-promoting`
- **Certification receipt:** `kita-042-iroh` · status=`blocked` · availability=`receipt-required`
- **Service family:** `iroh` via `ipfs_kit_py.iroh.backend.IrohBackendPlugin` · status=`service-gated`
- **Limitations:**
  - Runtime factory and storage are declared but require a current external provider receipt.
  - Missing or stale external evidence demotes storage selection to blocked.
  - No hidden local/mock fallback when evidence is absent.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `lassie`

- **Aliases:** none
- **Schema type:** `lassie` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `lassie`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-lassie` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `local`

- **Aliases:** none
- **Schema type:** `local` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `local`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-local` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `local_fs`

- **Aliases:** `local-fs`
- **Schema type:** `local_fs` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `local_fs`, `local-fs`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-local_fs` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `local_storage`

- **Aliases:** `local-storage`
- **Schema type:** `local_storage` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `local_storage`, `local-storage`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-local_storage` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `lotus`

- **Aliases:** none
- **Schema type:** `lotus` (available=False, health=`not-available`)
- **Factory:** none
- **Capabilities:** none
- **Secret fields:** none
- **Advertised operations:** none (unsupported)
- **Interface names (CLI/MCP/docs):** `lotus`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`unsupported`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-lotus` · status=`excluded` · availability=`unsupported`
- **Limitations:**
  - A dashboard schema existed, but no backend plugin or runtime factory is registered.
  - No backend plugin or runtime factory is registered.
  - All storage operations reject as typed unsupported before side effects.
  - Routing must never select this type for storage.
- **Evidence CIDs:** none (freshness=`not-applicable`)

### `minio`

- **Aliases:** none
- **Schema type:** `minio` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `access_key`, `secret_key`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `minio`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-minio` · status=`configuration-only` · availability=`configuration-only`
- **Service family:** `s3-compatible` via `ipfs_kit_py.backends.s3_backend.S3BackendAdapter` · status=`service-gated`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `parquet`

- **Aliases:** none
- **Schema type:** `parquet` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** none
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `parquet`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-parquet` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `s3`

- **Aliases:** none
- **Schema type:** `s3` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `access_key`, `secret_key`, `session_token`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `s3`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-s3` · status=`configuration-only` · availability=`configuration-only`
- **Service family:** `s3-compatible` via `ipfs_kit_py.backends.s3_backend.S3BackendAdapter` · status=`service-gated`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `saturn`

- **Aliases:** none
- **Schema type:** `saturn` (available=False, health=`not-available`)
- **Factory:** none
- **Capabilities:** none
- **Secret fields:** none
- **Advertised operations:** none (unsupported)
- **Interface names (CLI/MCP/docs):** `saturn`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`unsupported`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-saturn` · status=`excluded` · availability=`unsupported`
- **Limitations:**
  - No implementation is integrated with the backend registry.
  - No backend plugin or runtime factory is registered.
  - All storage operations reject as typed unsupported before side effects.
  - Routing must never select this type for storage.
- **Evidence CIDs:** none (freshness=`not-applicable`)

### `sshfs`

- **Aliases:** none
- **Schema type:** `sshfs` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `password`, `private_key`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `sshfs`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-sshfs` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `storacha`

- **Aliases:** none
- **Schema type:** `storacha` (available=True, health=`not-probed`)
- **Factory:** none
- **Capabilities:** `configuration`, `health`
- **Secret fields:** `token`, `private_key`
- **Advertised operations:** `configuration`, `health`
- **Interface names (CLI/MCP/docs):** `storacha`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`configuration-only`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-storacha` · status=`configuration-only` · availability=`configuration-only`
- **Limitations:**
  - Validated configuration and health discovery only.
  - No declared runtime factory or storage capability.
  - Provider receipts cannot promote this entry to storage.
  - Credentials must use authorized secret references only.
- **Evidence CIDs:**
  - `bafkreiagzzvmwpneyncz275e4icyrw24yjblpwdkrfl2b5oiybxekv6cda`

### `synapse`

- **Aliases:** none
- **Schema type:** `synapse` (available=False, health=`not-available`)
- **Factory:** none
- **Capabilities:** none
- **Secret fields:** none
- **Advertised operations:** none (unsupported)
- **Interface names (CLI/MCP/docs):** `synapse`
- **Routing:** storage_selectable=False; fallback=`none`; rejection=`E_UNSUPPORTED`
- **Semantics:** durability=`unsupported`; integrity=`not-applicable`
- **Certification receipt:** `kita-042-synapse` · status=`excluded` · availability=`unsupported`
- **Limitations:**
  - No implementation is integrated with the backend registry.
  - No backend plugin or runtime factory is registered.
  - All storage operations reject as typed unsupported before side effects.
  - Routing must never select this type for storage.
- **Evidence CIDs:** none (freshness=`not-applicable`)

## Interface certification

Policy: `AllInterfaceParityPolicy@1` across transports: `python`, `cli`, `mcp`, `mcpp`.

- Advertised operations on configuration-only entries are configuration and health only.
- Storage operations may be advertised only when the inventory declares storage capability.
- Invoking storage on non-runtime-ready backends yields typed rejection on every transport.
- Semantic payloads match across Python/CLI/MCP/MCP++ after transport-only field strip.
- Authorization, durability, and integrity meanings are preserved across transports.

## Routing policy

Fallback: **none**. On reject: typed error before side effects; no alternate backend substitution.

Select storage only when all of:
- live_tier in {production, conditional}
- routing.storage_selectable is true
- evidence freshness is current
- disposition is runtime-ready
- capability storage is declared

Never select when any of:
- disposition is unsupported or configuration-only
- evidence freshness is missing or stale
- availability is receipt-required or canonical-adapter-missing
- requested capability is not in declared capabilities

## Validation

```bash
cd ipfs_kit_py && python -m pytest -q tests/runtime_readiness/backends/test_joined_backend_matrix.py
```

Mandatory in default CI: `True`.

