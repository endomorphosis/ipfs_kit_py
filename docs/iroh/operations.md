# Iroh deployment and operations

- Runbook: IROH-023
- Safe operator CLI: IROH-021
- Applies to: release bundle `iroh-1.0.2-ipfs-kit.1`, protocol 1
- Related: [service configuration](service-configuration.md),
  [service lifecycle](service-lifecycle.md), [observability](observability.md),
  [security](security.md), and [recovery](recovery.md)

This runbook covers a managed IPFS Kit Iroh sidecar. Treat a named instance,
its credential records, and every backend bound to it as one deployment unit.
Examples use `primary`, `/etc/ipfs-kit/iroh-primary.json`, and a dedicated
`ipfs-kit` account. Substitute site-specific absolute paths and never put a
resolved key, capability, or ticket in a command line or environment dump.

## Deployment checklist

Before changing a host:

1. Record the desired release bundle, protocol version, instance name, service
   account UID/GID, state root, credential references, namespace IDs, relay
   policy, listener binds, and storage/resource limits.
2. Confirm that the pinned release manifest has a published, checksum-pinned
   artifact for the host. Installation fails closed when it does not.
3. Provision the node identity in the approved credential provider under the
   configured `credential://iroh/...` reference. Do not place its value in the
   JSON configuration.
4. Create an encrypted backup and a tested recovery point as described in
   [recovery.md](recovery.md). An upgrade is not a backup.
5. Verify disk headroom for `data/`, private staging, one retained binary, and
   the backup/export destination. Verify clock synchronization and DNS when
   relay or DNS discovery is enabled.
6. Open only the transport paths listed in [Network policy](#network-policy).
   The RPC endpoint must remain host-local.

## Safe operator CLI

`ipfs-kit-iroh-ops` is the JSON-only operator interface. The established
`ipfs-kit-iroh` command remains the compatibility interface for the verified
binary installer described below; keeping the entry points distinct avoids
silently changing existing installation automation. Every successful ops
invocation writes exactly one JSON object to stdout; every operational failure
writes exactly one redacted JSON object to stderr. Human help is the only
non-JSON output. Use `--compact` before the command group for JSON Lines
consumers. For convenience, the ops entry point accepts top-level `inspect`,
`install`, `update`, and `rollback` as aliases for its explicit `binary` group.

The complete command groups are:

| Group | Safe operations | Mutating operations |
| --- | --- | --- |
| `binary` | `inspect` | `install`, `update`, `rollback` |
| `service` | `status` | `start`, `stop`, `restart` |
| `backend` | `list`, `show`, `health`, `capabilities`, `validate` | `create`, `remove` |
| `namespace` | `info`, `history`, `recover` (audit is the default) | `create`, `recover --apply` |
| `blob` | `stat`, all `--dry-run` previews | `add`, `fetch`, `export` |
| `ticket` | `import --dry-run` | `import` from a private file or stdin |
| `mount` | `list`, `add/remove --dry-run` | `add`, `remove` |
| `sync` | `status`, `run --dry-run` | `run` |
| `gc` | `plan`, `run --dry-run` | `run --apply`, `resume` |

Inspect help at both levels before an operation, for example
`ipfs-kit-iroh-ops sync run --help`. Typical safe previews are:

```console
ipfs-kit-iroh-ops binary update --bin-dir /opt/ipfs-kit/libexec --dry-run
ipfs-kit-iroh-ops service restart --config /etc/ipfs-kit/iroh-primary.json --dry-run
ipfs-kit-iroh-ops backend validate --file /etc/ipfs-kit/backends/archive.json
ipfs-kit-iroh-ops mount add /archive --backend archive --mount-state /var/lib/ipfs-kit/vfs-mounts.json --dry-run
ipfs-kit-iroh-ops sync run --file /var/lib/ipfs-kit/changes/sync-request.json --state-dir /var/lib/ipfs-kit/sync --dry-run
ipfs-kit-iroh-ops gc plan --config /etc/ipfs-kit/iroh-primary.json --index /var/lib/ipfs-kit/iroh/references.duckdb
```

Dry runs validate inputs and avoid the requested external mutation. Some
previews (backend lookup, sync checkpointing, and GC planning) necessarily
read or persist their own control/audit state; they never release data or
change the requested backend object. A destructive preview includes the exact
`confirmation_phrase`. An attended operator can omit confirmation and type
that phrase at the terminal. Automation must pass either the exact phrase via
`--confirm` or the terser `--yes` only after change-control approval. The CLI
refuses non-interactive destructive work without one of those flags. Stop,
restart, backend removal, namespace repair, unmount, export overwrite, sync
deletes/source-wins/local overwrite, binary rollback, live GC, and GC resume
are confirmation-gated. Mount addition refuses to replace an existing mount;
remove the old mount explicitly first. Live GC additionally requires
`--apply`; plain `gc run` remains a dry run.

Do not pass a bearer ticket as an argument. Put it in an owner-only (`0600`)
regular file supplied by a credential broker, or pipe it without shell tracing:

```console
ipfs-kit-iroh-ops ticket import 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  --ticket-file /run/credentials/iroh-read-ticket --config /etc/ipfs-kit/iroh-primary.json --dry-run
credential-broker read iroh/archive | ipfs-kit-iroh-ops ticket import \
  0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  --ticket-stdin --config /etc/ipfs-kit/iroh-primary.json
```

Ticket material is never included in the success receipt or an error. Backend
credential references are provider-visible but record names are redacted.
Unexpected RPC, filesystem, or sidecar exception text is replaced by a fixed
public error, so a path, peer value, or ticket embedded in an exception cannot
reach the terminal. Preserve stderr privately for incident correlation, but
do not treat redaction as permission to publish operational records.

Exit codes are stable for automation:

| Code | Meaning |
| ---: | --- |
| `0` | Operation or dry run succeeded |
| `2` | Command-line usage error |
| `3` | Confirmation missing or mismatched |
| `4` | Invalid input or configuration |
| `5` | Requested resource not found |
| `6` | State or compare-and-swap conflict |
| `7` | Sidecar, IPFS, or required service unavailable/timeout |
| `8` | Hash, receipt, or integrity verification failed |
| `9` | Permission or unsafe credential-file mode |
| `10` | Other operational failure |
| `130` | Interrupted by the operator |

The JSON `ok` field is authoritative. Do not infer success from the presence
of a receipt: synchronization may return a `partial` status and GC receipts
may contain per-blob failures that require operator review.

## Install the verified sidecar

Install the Python package by the site's normal locked-package process. Merely
importing IPFS Kit does not download or execute Iroh. Keep
`IPFS_KIT_AUTO_INSTALL_BINARIES` unset in production and make binary changes an
explicit operator action.

The managed binary directory defaults to
`~/.local/share/ipfs_kit_py/bin` for the invoking account. A system service
should use a dedicated absolute directory and the same value for every
lifecycle operation:

```console
ipfs-kit-iroh install --bin-dir /opt/ipfs-kit/libexec --dry-run
ipfs-kit-iroh install --bin-dir /opt/ipfs-kit/libexec --check
ipfs-kit-iroh inspect --bin-dir /opt/ipfs-kit/libexec --check
```

`--dry-run` validates selection without taking the update lock or changing
files. On `install`, `--check` verifies the result after installation by
checking the executable SHA-256 and invoking its side-effect-free `--version`.
Save the JSON output in the change record. The receipt
`/opt/ipfs-kit/libexec/.ipfs-kit-iroh-install.json` is evidence, not a
substitute for verification.

If the release manifest reports that the sidecar is not published or the host
is not installable, stop. Do not fetch an unpinned binary or bypass checksum,
archive-path, or version-output checks.

## Configure a named instance

Start from [`config/iroh-service.example.json`](../../config/iroh-service.example.json).
Give each instance a unique lowercase name and non-overlapping state and fixed
listener paths. The JSON document is closed: unknown fields, inline secrets,
remote RPC endpoints, and unsupported versions are errors.

Use a configuration deployment mechanism that writes atomically with mode
`0600`, owned by the service account. Validate it without creating state:

```console
python - /etc/ipfs-kit/iroh-primary.json <<'PY'
import sys
from ipfs_kit_py.iroh import load_config

config = load_config(sys.argv[1])
print(config.instance, config.release_bundle, config.rpc_endpoint)
PY
```

The configured state root resolves to this private instance tree:

```text
<state-root>/instances/primary/
├── .instance.json             ownership marker
├── config.json                canonical active configuration
├── data/                      durable sidecar data and namespace state
├── staging/                   incomplete private transfers
├── run/                       socket, PID receipt, and service lock
├── logs/sidecar.log
└── receipts/                  health and crash receipts
```

All directories must be `0700`; managed files must be `0600`. The service
refuses symlinks, public state directories, conflicting ownership markers, and
state belonging to another instance. Do not share a state directory between
containers, hosts, service accounts, or simultaneous supervisors.

Use the foreground command under systemd or launchd, as shown in
[service-lifecycle.md](service-lifecycle.md). Do not run managed-child mode at
the same time. Keep the service manager's stop timeout greater than both Iroh
shutdown timeouts combined.

## Network policy

The `rpc.endpoint` is derived from the instance and is an absolute Unix socket
or Windows named pipe. It is never TCP or HTTP. Limit access to the service
account and applications that are authorized to exercise its capabilities.

`network.endpoint_bind` controls Iroh transport listeners. Port `0` asks the
OS for an ephemeral port; a fixed port makes firewalling and monitoring more
predictable. Inventory the actual sockets after every restart. Apply the
following least-privilege policy at both host and perimeter firewalls:

| Flow | Allow when | Policy |
| --- | --- | --- |
| Local RPC | Always | Unix socket/named pipe only; never expose through a TCP proxy |
| Direct Iroh transport | Direct peer connectivity is required | Allow the configured inbound/outbound transport address and port (Iroh uses QUIC over UDP); restrict source ranges where the peer set is known |
| HTTPS relay | Relay policy is `default` or `custom` | Allow outbound TCP/TLS to only the approved relay host and port; custom URLs must be credential-free HTTPS URLs |
| DNS | Discovery is `dns` or `all`, or relay names need resolution | Allow only the site's resolvers; log failures without query payloads |
| Local discovery | Discovery is `local` or `all` | Scope multicast/broadcast traffic to the intended trusted segment; disable it on untrusted networks |

With relay policy `disabled`, operations that require peers outside direct
reachability may remain unavailable; that is not permission to open RPC.
With `custom`, approve relay certificate/DNS ownership and egress before
deployment. Never embed relay credentials in the URL. A relay can observe
connection metadata even though application content remains protected, so
select it according to the deployment's metadata policy.

After applying firewall rules, test both the expected path and the denied path:
direct-only, relay fallback, DNS/local discovery as configured, and rejection
of remote access to the RPC socket.

## Start and verify

Start through exactly one supervisor, then collect an operator-safe receipt:

```console
systemctl start ipfs-kit-iroh-primary.service
ipfs-kit-iroh-diagnostics --config /etc/ipfs-kit/iroh-primary.json --format json
ipfs-kit-iroh-diagnostics --config /etc/ipfs-kit/iroh-primary.json --format prometheus --no-persist
```

A successful diagnostics exit means a receipt was produced, not necessarily
that the service is ready. Gate traffic on `ready`, and alert separately on
`running=false`, `ready=false`, crash-loop state, release/protocol mismatch,
relay/direct connectivity loss, storage pressure, transfer failures, manifest
conflicts, and GC failures. The default persisted health receipt is private and
atomic under `receipts/health.json`.

Verify a deployment in this order:

1. `ipfs-kit-iroh inspect --check` matches the approved receipt and bundle.
2. The service PID receipt proves process ownership and status is running and
   ready.
3. The public node ID is the expected value for the credential record.
4. Direct/relay/discovery behavior matches policy from a permitted peer and a
   denied network.
5. A canary namespace can publish, read, and export a blob with its BLAKE3 hash
   verified. A read-only binding must reject mutation.
6. Backup monitoring, storage alerts, and log collection work without exposing
   paths, peer lists, ticket references, or secrets.

## Upgrade and rollback

Upgrades retain exactly one previous verified binary. They do not migrate or
copy service data automatically.

1. Read the compatibility notes, create a recovery point, pause new writes and
   transfers, and stop the service cleanly.
2. Preview and apply the pinned update:

   ```console
   ipfs-kit-iroh update --bin-dir /opt/ipfs-kit/libexec --dry-run
   ipfs-kit-iroh update --bin-dir /opt/ipfs-kit/libexec --check
   ipfs-kit-iroh update --bin-dir /opt/ipfs-kit/libexec
   ipfs-kit-iroh inspect --bin-dir /opt/ipfs-kit/libexec --check
   ```

   `update --check` is read-only: it verifies the current installation and
   reports whether the pinned version is newer. The plain `update` performs
   the change and automatically verifies the installed result. Do not omit or
   reorder the service stop merely because the lifecycle command can replace
   an idle binary atomically.

3. Start the service and repeat all checks in
   [Start and verify](#start-and-verify), including a canary read and write.
   Preserve the update receipt.

If validation fails, stop the new binary before rollback:

```console
ipfs-kit-iroh rollback --bin-dir /opt/ipfs-kit/libexec --dry-run --check
ipfs-kit-iroh rollback --bin-dir /opt/ipfs-kit/libexec --check
```

Rollback swaps only the current and retained binary/receipts. It does not
reverse configuration, namespace heads, data formats, sync mappings, or data
written after the upgrade. Restore compatible configuration/data from the
pre-upgrade recovery point when release notes require it. Never start an old
binary against state it cannot read merely because binary rollback succeeded.

## Namespace sharing

A namespace ID is public and grants no write access. A write capability and a
read ticket are bearer authority. Share the least authority required:

1. Confirm the namespace ID, recipient, purpose, expiry/review date, and read
   versus write role out of band.
2. Generate the capability through an authenticated application boundary.
   Store it immediately in the recipient's approved credential provider.
3. Persist only an opaque `secretref:...` or `credential://iroh/...` reference,
   as required by that configuration surface. Never place a raw ticket in a
   URL, shell history, configuration, chat, log, metric, trace, or issue.
4. For read-only access use an `iroh+ticket://<ticket-ref>/...` lookup name;
   the name is local and non-secret, and resolves to the raw ticket only at the
   protected RPC boundary. Bind it to the expected namespace ID.
5. Test from the recipient context and audit the public namespace/operation
   identity, not the secret. Remove temporary transfer material.

Tickets that have escaped must be treated as compromised bearer credentials.
Deleting a local reference does not retract copies. Follow the capability
rotation procedure in [security.md](security.md#rotate-namespace-capabilities-and-tickets).

## Data export and IPFS synchronization

For a logical filesystem export, first pin one verified manifest revision.
Export every live file by its `blob_hash` using
`IrohBlobStore.export()`. That method streams to a same-directory private
temporary file and publishes the destination only after exact size and BLAKE3
verification. Preserve the canonical manifest beside the files and record its
namespace ID, revision, manifest hash, export time, and software bundle. Do not
export tombstones as files.

For transfer to IPFS, local storage, or another Iroh namespace, use the
explicit synchronization adapter in `ipfs_kit_py.iroh_sync`. Its mapping keeps
`cid` and `iroh_hash` in distinct fields, checkpoints after each object, and
emits a reconciliation receipt. Back up the sync state directory containing
`mappings.json`, `checkpoints/`, and `receipts.jsonl`. Resume with the identical
request; a different request must use a new checkpoint. Never relabel an Iroh
hash as a CID or silently fall back between storage systems.

## Garbage collection

GC releases immutable blobs only after durable manifest references, retained
revisions, and active leases no longer protect them. The default unreferenced
retention is 24 hours. Quota pressure never overrides a reference or lease.

Operational policy:

1. Back up the reference-tracker DuckDB with the instance recovery point.
2. Reconcile the tracker against verified manifests and sidecar inventory;
   inspect `RepairReceipt.missing_blobs` before applying a repair.
3. Run `IrohGarbageCollector.collect(dry_run=True, policy=...)`, save its
   digest-bearing `0600` receipt, and review candidate count/bytes. Store its
   digest in an authenticated audit system if independent tamper evidence is
   required.
4. Ensure no backup, export, reader, writer, or sync job depends on candidates.
   Such work must hold renewable leases.
5. Run the same policy with `dry_run=False`. Keep the receipt and alert on
   failures or interruption. Resume an interrupted live run by its `run_id`;
   stable operation IDs make release replay idempotent.

Never set `retention_seconds=0` merely to cure disk pressure. Reduce ingestion,
extend capacity, or repair references first. A dry-run mark cannot be promoted
by `resume`; start an explicitly live run after review.

## Complete uninstall without data loss

Uninstall is a staged retirement, not `rm -rf`:

1. Disable new writes, synchronization, mounts, schedulers, and API routing.
2. Record final diagnostics and wait for transfers to finish. Stop the one
   owning supervisor cleanly and verify the PID is absent. Do not signal a
   process reported as `foreign`.
3. Export every required namespace and verify every file hash. Create and
   independently verify an encrypted recovery bundle containing the complete
   instance state, manifests, backend/service configurations, GC and sync
   state, receipts, and a provider-native export of the node identity and
   namespace capabilities. See [recovery.md](recovery.md#backup-procedure).
4. Restore that bundle into an isolated test location and prove a manifest and
   blob can be read. Record the retention owner and expiry.
5. Disable/remove the systemd or launchd unit and remove named backend bindings.
   Uninstall the Python package and managed binary only after no other instance
   uses them. Removing the binary does not remove state or credentials.
6. Retain the state root and credential records, inaccessible to the retired
   service account, through the approved recovery window. At this point the
   software is completely uninstalled without data loss.
7. Only after written backup acceptance and retention expiry may a separately
   authorized purge delete the state directory, backups, capabilities, and
   credential records. Secure deletion depends on the storage and key-management
   system; ordinary file deletion is not a cryptographic erase.

Reinstallation reverses steps 5 and 1, restores the exact identity and state
under their original ownership, validates the configuration, and completes the
restore verification in [recovery.md](recovery.md#restore-procedure).
