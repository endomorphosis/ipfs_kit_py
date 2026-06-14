# Walrus fsspec Backend TODO

This task board is intentionally compatible with the generic todo daemon in
`ipfs_accelerate_py.agent_supervisor.todo_daemon`: the checkbox list is the
daemon-selectable queue. The detailed `## walrus-fsspec-*` blocks below are
also compatible with the implementation-daemon parser, which reads task blocks
with `status`, `priority`, `track`, `depends on`, `outputs`, `validation`, and
`acceptance` metadata.

## Daemon Task Board

<!-- walrus-fsspec-daemon-task-board:start -->
- [x] Task checkbox-1: Implement Walrus storage client and response normalization.
- [x] Task checkbox-2: Add local Walrus metadata index for fsspec path semantics.
- [x] Task checkbox-3: Implement `WalrusFileSystem` fsspec backend.
- [x] Task checkbox-4: Register the `walrus` fsspec protocol and package extras.
- [x] Task checkbox-5: Add high-level API and VFS registry integration.
- [x] Task checkbox-6: Add mocked unit tests for client and filesystem behavior.
- [x] Task checkbox-7: Document usage examples, config, and limitations.
<!-- walrus-fsspec-daemon-task-board:end -->

## walrus-fsspec-001 Implement Walrus storage client and response normalization.

- status: completed
- completion: automatic
- priority: P0
- track: storage
- depends on:
- outputs: ipfs_kit_py/walrus_storage.py, tests/test_walrus_storage.py
- validation: pytest tests/test_walrus_storage.py -q
- acceptance: `WalrusStorageClient` can resolve publisher, aggregator, and delete URLs; upload, retrieve, delete, and normalize Walrus response payloads using mocked HTTP responses.

Implementation notes:

- Port URL behavior from `wallet_interface/ui/src/services/walrusStorage.ts`.
- Support bearer auth, `epochs`, and `deletable`/`permanent` query flags.
- Normalize top-level, `newlyCreated`, and `alreadyCertified` response variants.
- Prefer concise `WALRUS_*` environment variables, with `ABBY_RUNTIME_*` and
  `VITE_WALRUS_STORAGE_*` aliases as fallbacks.

## walrus-fsspec-002 Add local Walrus metadata index for fsspec path semantics.

- status: completed
- completion: automatic
- priority: P0
- track: storage
- depends on: walrus-fsspec-001
- outputs: ipfs_kit_py/walrus_storage.py, tests/test_walrus_storage.py
- validation: pytest tests/test_walrus_storage.py -q
- acceptance: A JSON index maps logical names to Walrus blob metadata and supports atomic load/update/remove operations.

Implementation notes:

- Default to `~/.cache/ipfs_kit_py/walrus/index.json` unless `index_path` is
  supplied.
- Include `schema`, `items`, `blob_id`, `object_id`, `tx_digest`, `end_epoch`,
  `cost`, `size`, `content_type`, `created_at`, and `gateway_url` where known.
- Use atomic temporary-file replacement for writes.

## walrus-fsspec-003 Implement `WalrusFileSystem` fsspec backend.

- status: completed
- completion: automatic
- priority: P0
- track: fsspec
- depends on: walrus-fsspec-001, walrus-fsspec-002
- outputs: ipfs_kit_py/walrus_fsspec.py, tests/test_walrus_fsspec.py
- validation: pytest tests/test_walrus_fsspec.py -q
- acceptance: `fsspec.filesystem("walrus")`, `cat_file`, `pipe_file`, `put_file`, `get_file`, `open(..., "rb")`, `info`, `exists`, `ls`, `rm`, and `ukey` work against mocked Walrus HTTP responses and the local index.

Implementation notes:

- Follow the async-first shape from `docs/ipfsspec/ipfsspec/async_ipfs.py`.
- Keep direct blob-id paths working without an index entry.
- Make `ls("walrus://")` index-backed; do not imply global Walrus listing.
- Return clear configuration errors when publisher, aggregator, or delete
  operations are requested without the required URL.

## walrus-fsspec-004 Register the `walrus` fsspec protocol and package extras.

- status: completed
- completion: automatic
- priority: P1
- track: packaging
- depends on: walrus-fsspec-003
- outputs: pyproject.toml, ipfs_kit_py/walrus_fsspec.py
- validation: python -c "import fsspec, ipfs_kit_py.walrus_fsspec; print(fsspec.filesystem('walrus', skip_instance_cache=True))"
- acceptance: Editable installs and packaged installs can discover `walrus://` through fsspec entry points or module import-time registration.

Implementation notes:

- Add a `walrus` optional dependency group with `fsspec` and `httpx`.
- Add `[project.entry-points."fsspec.specs"] walrus = "ipfs_kit_py.walrus_fsspec.WalrusFileSystem"`.
- Use `fsspec.register_implementation("walrus", WalrusFileSystem, clobber=True)`
  during module import for development reloads.

## walrus-fsspec-005 Add high-level API and VFS registry integration.

- status: completed
- completion: automatic
- priority: P1
- track: api
- depends on: walrus-fsspec-003, walrus-fsspec-004
- outputs: ipfs_kit_py/high_level_api.py, ipfs_kit_py/ipfs_fsspec.py, tests/integration/test_fsspec_integration.py
- validation: pytest tests/integration/test_fsspec_integration.py tests/test_walrus_fsspec.py -q
- acceptance: The high-level API can create a Walrus filesystem from config or explicit keyword arguments, and the lightweight VFS registry reports `walrus` as an available backend when dependencies are present.

Implementation notes:

- Add `create_walrus_filesystem(**kwargs)` or equivalent helper.
- Preserve existing config precedence: explicit arguments, kwargs, config, then
  environment defaults.
- Avoid breaking `IPFSFileSystem` compatibility aliases.

## walrus-fsspec-006 Add mocked unit tests for client and filesystem behavior.

- status: completed
- completion: automatic
- priority: P0
- track: tests
- depends on: walrus-fsspec-001, walrus-fsspec-002, walrus-fsspec-003
- outputs: tests/test_walrus_storage.py, tests/test_walrus_fsspec.py
- validation: pytest tests/test_walrus_storage.py tests/test_walrus_fsspec.py -q
- acceptance: Tests cover successful uploads/downloads/deletes, error extraction, index-backed listing, direct blob-id access, and missing configuration failures without requiring a live Walrus network.

Implementation notes:

- Use mocked `httpx` transports or monkeypatch client methods.
- Keep live network tests opt-in via environment variables only.
- Include response fixtures for `newlyCreated`, `alreadyCertified`, and flat
  response payloads.

## walrus-fsspec-007 Document usage examples, config, and limitations.

- status: completed
- completion: automatic
- priority: P1
- track: docs
- depends on: walrus-fsspec-003, walrus-fsspec-004
- outputs: docs/integration/walrus_fsspec.md, README.md
- validation: python -m compileall ipfs_kit_py/walrus_storage.py ipfs_kit_py/walrus_fsspec.py
- acceptance: Documentation shows `fsspec.open`, `fs.pipe_file`, direct blob-id reads, index-backed logical paths, required environment variables, and listing/deletion limitations.

Implementation notes:

- Link back to `docs/integration/walrus_fsspec_implementation_plan.md`.
- Include examples with `WALRUS_PUBLISHER_URL`, `WALRUS_AGGREGATOR_URL`, and
  optional `WALRUS_DELETE_URL`.
- Explain that `ls` is local-index-backed until a real remote listing API is
  integrated.
