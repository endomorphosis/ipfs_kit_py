# Iroh multi-node interoperability

IROH-025 provides a deterministic harness for real sidecar interoperability
runs. Ordinary pytest runs only validate the harness, scenario matrix,
resource limits, evidence schema, and checked-in evidence. They never start a
daemon, pull an image, create a container, or access a network.

The selected Iroh release is currently `source-pinned`: the release record
does not advertise an installable sidecar artifact. The checked-in
`ipfs_kit_py/resources/iroh-interoperability-evidence.json` therefore has the
honest status `not_run`. A Linux or macOS release lane replaces that record in
its artifacts with the JSON produced by a successful real-node run. A skipped
or not-run record is not release evidence.

## Required matrix

Every passing record contains these scenarios in order:

| Scenario | Nodes | Required observation |
| --- | ---: | --- |
| `direct_lan` | 2 | Direct transfer between isolated node state directories. |
| `relay_fallback` | 3 | Direct reachability is blocked and the observed transfer uses the relay. |
| `nat_container` | 3 | Source and target occupy isolated NAT-like container networks and transfer through the relay. |
| `interruption_resume` | 2 | The source or link is interrupted halfway through transfer and resumes from a non-zero offset. |
| `version_skew` | 2 | Current and previous supported bundles transfer over their shared protocol. |
| `key_rotation` | 2 | Source identity changes, the old identity is rejected, and transfer succeeds after rediscovery. |
| `large_data` | 2 | A deterministic 32 MiB payload transfers with bounded chunks, concurrency, elapsed time, and aggregate node RSS. |

All transfers must verify the native lowercase BLAKE3 digest. The harness
limits each scenario to 180 seconds, aggregate peak RSS to 768 MiB, transfer
chunks to 1 MiB, active transfers to four, nodes to four, and driver output to
1 MiB. The evidence validator refuses a `passed` result when an expected
transport, scenario-specific assertion, content hash, or resource bound is
missing.

## Real-driver contract

The harness invokes one driver process per scenario and sends exactly one JSON
object on stdin. The object contains:

- `contract_version: 1`;
- the closed scenario plan and resource bounds;
- an owner-only scenario workspace and deterministic payload path, size, and
  BLAKE3 digest;
- absolute current/previous sidecar binary paths;
- whether a relay was configured and its URL.

The driver owns the real platform topology. Linux release lanes should use
separate network namespaces or containers for `nat_container`; macOS lanes
should use their CI provider's VM/container network isolation. The driver must
not simulate success, replace the supplied binaries, share node data
directories, or report a requested transport as an observed transport.

The process exits zero, writes no stderr, and writes one JSON observation on
stdout. Its accepted fields are enforced by
`ipfs_kit_py.iroh.multinode.validate_observation`. Required common assertions
are `isolated_state`, `hash_verified`, and `bounded_resources`. Metrics are
`duration_ms`, aggregate `peak_rss_bytes`, `max_transfer_chunk_bytes`,
`max_active_transfers`, and `reconnect_count`. Scenario-specific assertions
are shown in the table and sent in the plan. Stable `failure_code` and
`skip_code` values are allowed; raw exception text is not.

Tickets, capabilities, credential references, private keys, peer IDs,
addresses, endpoints, relay URLs, and driver stderr are never copied into
evidence. The schema contains no fields for them and the Python validator also
recursively rejects sensitive field names.

## Running a platform lane

Supply a reviewed driver and immutable binaries explicitly:

```bash
export IPFS_KIT_IROH_INTEROP=1
export IPFS_KIT_IROH_INTEROP_DRIVER='/opt/ipfs-kit/bin/iroh-interop-driver'
export IPFS_KIT_IROH_INTEROP_BINARY='/opt/ipfs-kit/bin/ipfs-kit-iroh-sidecar'
export IPFS_KIT_IROH_INTEROP_PREVIOUS_BINARY='/opt/ipfs-kit/previous/ipfs-kit-iroh-sidecar'
export IPFS_KIT_IROH_INTEROP_RELAY_URL='https://relay.test.invalid'
export IPFS_KIT_IROH_INTEROP_EVIDENCE="$PWD/iroh-interoperability-evidence.json"
python -m pytest -q tests/test_iroh_multinode.py
```

The environment switch alone is insufficient: missing driver, current binary,
previous binary, or relay configuration produces an error or explicit skipped
scenario, never a passing record. Validate an archived record independently:

```bash
ipfs-kit-iroh-interop --check-evidence iroh-interoperability-evidence.json
```

Publish the JSON alongside binary digests and CI provenance. Do not hand-edit
results or replace a platform record with the checked-in not-run template.
