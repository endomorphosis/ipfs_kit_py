# Iroh service configuration and state

The managed Iroh sidecar uses a closed, versioned JSON document. The current
version is `1`; unknown fields, missing fields, malformed versions, remote RPC
addresses, and inline credentials are rejected before any state is created.
[`config/iroh-service.example.json`](../../config/iroh-service.example.json) is
a complete disabled example.

Loading a document has no filesystem or credential side effects. Call
`ensure_state_layout(config)` only when preparing to start the named service.

## Named state layout

The default state root is
`$IPFS_KIT_IROH_STATE_DIR`, then `$XDG_STATE_HOME/ipfs-kit/iroh`, then
`~/.local/state/ipfs-kit/iroh`, in that order. An instance named `primary`
owns only the following tree:

```text
<state-root>/instances/primary/
├── .instance.json
├── config.json
├── data/
├── staging/
├── run/
│   ├── sidecar.sock
│   ├── sidecar.pid
│   └── service.lock
├── logs/
│   └── sidecar.log
└── receipts/
    ├── health.json
    └── crash.json
```

Instance names contain only lowercase ASCII letters, digits, `_`, and `-` and
are at most 64 characters. Every directory is owner-only (`0700`) and every
managed metadata/configuration file is `0600`. Existing symlinks, public state
directories, non-directories, and ownership markers for a different instance
fail closed. `validate_instance_isolation()` rejects duplicate names,
overlapping enabled state paths, repeated RPC endpoints, and conflicting
fixed listener binds. Port `0` is intentionally treated as an OS-assigned,
non-reserved listener.

## Network and identity policy

The RPC endpoint is derived from the instance layout and cannot be overridden:
an absolute Unix socket URI is used on Unix and a local named pipe on Windows.
Iroh transport listeners use `host:port` strings. Relay policy is `default`,
`disabled`, or `custom`; custom relays require one or more credential-free
HTTPS URLs. Discovery policy is `disabled`, `local`, `dns`, or `all`.

`identity.node_identity_ref` is an opaque reference of the form
`credential://iroh/<identifier>`. The referenced node identity is resolved by
the service boundary at startup and is never persisted by this module. Fields
that could contain a key, password, token, ticket, secret, or capability are
recursively rejected.

## Safe persistence and migration

`atomic_write_config()` validates and canonicalizes the entire document,
writes and `fsync`s a private temporary file in the destination directory,
atomically replaces the destination, and `fsync`s the directory. A failed
validation or replacement leaves the prior file intact.

`migrate_config()` is a pure conversion for the legacy version-0 fields:

| Version 0 | Version 1 |
| --- | --- |
| `name` / `instance` | `instance` |
| `state_dir` | `state_root` and derived paths |
| `node_identity_ref` / `node_key_ref` | `identity.node_identity_ref` |
| `bind` / `endpoint_bind` | `network.endpoint_bind` |
| `relay_mode`, `relay_url` | `network.relay` |
| `discovery` | `network.discovery.policy` |
| `resource_limits` | `resources` |
| `uid`, `gid` | `ownership` |

Migration requires an existing credential reference and never converts raw key
material to a reference. `migrate_config_file(path, backup=True)` validates the
converted document before creating an exclusive `*.v0.bak`, then uses the same
atomic replacement path. If conversion fails, the source bytes are unchanged.
