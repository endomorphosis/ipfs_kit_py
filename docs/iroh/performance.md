# Iroh filesystem performance baseline

IROH-016 establishes a deterministic in-memory regression floor in
`ipfs_kit_py/resources/iroh-performance-baseline.json`. It measures metadata
and warm-range p95 latency, sequential and bounded-parallel read throughput,
transport range size, retained cache bytes, staged-write memory, and peak
active operations. These budgets are CI guardrails; they do not represent WAN
or relay performance.

The async adapter admits at most `max_pending_operations` calls and executes at
most `max_concurrency` collaborator operations. Sync collaborators run in
AnyIO worker threads. Async collaborators are awaited directly. Both paths
reuse the filesystem's lazily-created runtime client.

Reads use immutable-hash-keyed, aligned read-ahead blocks. The LRU retains no
more than `range_cache_size` bytes and never caches a short or invalid range.
File exports bypass the process range cache so every destination creation is a
fresh integrity boundary. Writes use a spooled staging file and, when the blob
store advertises `ingest_parts` or `ingest_multipart`, feed one bounded part at
a time before the single manifest compare-and-swap.

Use `benchmark_async_filesystem` from `ipfs_kit_py.iroh_performance` to produce
a sample and `evaluate_sample` to compare it with the packaged baseline. A real
sidecar baseline must additionally record Iroh version, host, transport,
topology, payload sizes, cache state, and whether direct or relay transfer was
used; it must not record tickets, peers' sensitive addresses, or capabilities.
