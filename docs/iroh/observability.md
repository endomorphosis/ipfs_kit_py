# Iroh health and diagnostics

IPFS Kit exposes a safe operational snapshot for each isolated Iroh instance.
The snapshot reports liveness separately from readiness, along with the public
node ID, runtime version and uptime, direct and relay connectivity, peer count,
storage usage, transfer totals, failures, latency, manifest conflicts, and GC
state.

The sidecar response is treated as untrusted. Health receipts use an explicit
field allowlist and never copy tickets, credentials, private keys, paths, peer
lists, error strings, or arbitrary nested values. Metrics use fixed names and
only the bounded labels `instance`, `path`, `result`, and `direction`.

## CLI

```console
ipfs-kit-iroh-diagnostics --instance default --format json
ipfs-kit-iroh-diagnostics --instance default --format prometheus
```

By default, collection atomically updates the owner-only receipt at
`receipts/health.json` under the instance state directory. Use `--no-persist`
for a read-only probe. `--config` selects an existing service configuration;
`--state-root` overrides the platform state root.

Exit status `0` means a receipt was produced. Invalid configuration or CLI
arguments return `2`; unexpected diagnostic failures return `1`. Exception
details are intentionally omitted because transport errors can contain private
paths, peer IDs, or request data.

## Python

```python
from ipfs_kit_py.iroh import IrohObservability, IrohServiceConfig

config = IrohServiceConfig.default("default", enabled=True)
observer = IrohObservability(config)
receipt = await observer.diagnostics()
metrics = await observer.metrics(persist=False)
prometheus = await observer.prometheus(persist=False)
```

`IrohObservability` can also receive an `IrohService` to incorporate process
ownership/lifecycle state, or an injected runtime client for embedding and
tests. Failure to reach the sidecar yields a safe not-ready receipt rather than
reflecting transport exception data.

## MCP

The `iroh_diagnostics` tool accepts:

- `instance`: isolated instance name (default `default`)
- `format`: `health`, `metrics`, or `prometheus`
- `persist`: whether to update the private receipt (default `true`)

Unknown fields are rejected without echoing their names or values. The tool is
registered in both the compatibility MCP server and the canonical hierarchical
MCP++ registry under the `iroh_tools` category.
