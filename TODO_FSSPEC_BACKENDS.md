# fsspec Backend Improvement TODO

This board tracks improvements for the existing fsspec-related backends in
`ipfs_kit_py`: Synapse, Storacha, Filecoin pin, and the multi-backend
`enhanced_fsspec.py` facade.

The checkbox section is compatible with the generic todo daemon in
`ipfs_accelerate_py.agent_supervisor.todo_daemon`. The detailed
`## fsspec-backends-*` blocks are compatible with the implementation daemon
parser when invoked with `task_header_prefix="## fsspec-backends-"`.

## Daemon Task Board

<!-- fsspec-backends-daemon-task-board:start -->
- [x] Task checkbox-1: Audit current fsspec backend behavior and test coverage.
- [x] Task checkbox-2: Stabilize `enhanced_fsspec.py` backend selection and protocol registration.
- [x] Task checkbox-3: Complete Synapse fsspec read/write/status behavior.
- [x] Task checkbox-4: Implement Storacha fsspec list/read/write/delete behavior.
- [x] Task checkbox-5: Implement Filecoin pin fsspec upload/status/retrieval behavior.
- [x] Task checkbox-6: Add shared backend metadata and path normalization helpers.
- [x] Task checkbox-7: Add mocked backend test suites and optional live integration gates.
- [x] Task checkbox-8: Document backend capabilities, limitations, and examples.
<!-- fsspec-backends-daemon-task-board:end -->

## fsspec-backends-001 Audit current fsspec backend behavior and test coverage.

- status: completed
- completion: automatic
- priority: P0
- track: audit
- depends on:
- outputs: docs/integration/fsspec_backend_audit.md
- validation: pytest tests/integration/test_fsspec_simple.py tests/integration/test_fsspec_integration.py tests/test_synapse_fsspec.py -q
- acceptance: A concise audit documents which fsspec methods are implemented, stubbed, or untested for IPFS, Synapse, Storacha, Filecoin/Filecoin pin, and `enhanced_fsspec.py`.

Implementation notes:

- Inspect `ipfs_kit_py/ipfs_fsspec.py`, `ipfs_kit_py/enhanced_fsspec.py`,
  `ipfs_kit_py/storage_backends_api.py`, Synapse storage modules, and any
  Filecoin pin client modules.
- Identify protocol names, registration paths, constructor config, and expected
  return shapes.
- Mark live-network-only behavior separately from mocked behavior.

## fsspec-backends-002 Stabilize `enhanced_fsspec.py` backend selection and protocol registration.

- status: completed
- completion: automatic
- priority: P0
- track: fsspec
- depends on: fsspec-backends-001
- outputs: ipfs_kit_py/enhanced_fsspec.py, tests/test_enhanced_fsspec.py
- validation: pytest tests/test_enhanced_fsspec.py -q
- acceptance: `fsspec.filesystem("ipfs")`, `fsspec.filesystem("synapse")`, `fsspec.filesystem("storacha")`, and `fsspec.filesystem("filecoin")` instantiate the intended backend without clobbering each other or requiring unrelated dependencies.

Implementation notes:

- Avoid one class with ambiguous `backend="ipfs"` defaults for all protocols
  unless protocol-to-backend mapping is explicit and tested.
- Consider thin protocol-specific subclasses such as `SynapseFileSystem`,
  `StorachaFileSystem`, and `FilecoinPinFileSystem` that share helper mixins.
- Keep import-time registration tolerant of missing optional dependencies.
- Preserve current `IPFSFileSystem` compatibility for callers importing from
  `ipfs_kit_py.enhanced_fsspec`.

## fsspec-backends-003 Complete Synapse fsspec read/write/status behavior.

- status: completed
- completion: automatic
- priority: P0
- track: synapse
- depends on: fsspec-backends-001, fsspec-backends-002
- outputs: ipfs_kit_py/enhanced_fsspec.py, tests/test_synapse_fsspec.py
- validation: pytest tests/test_synapse_fsspec.py -q
- acceptance: Synapse fsspec supports `ls`, `cat_file`, `pipe_file`, `put_file`, `get_file`, `info`, `exists`, `open(..., "rb")`, and backend status using mocked Synapse storage.

Implementation notes:

- Reuse existing async bridge helpers where needed, but keep async/sync behavior
  deterministic under pytest.
- Normalize Synapse identifiers as `synapse://{commp}`.
- Ensure `info` returns fsspec-standard keys: `name`, `type`, `size`, plus
  Synapse-specific metadata such as `commp`, proof-set status, and provider.
- Make missing Synapse SDK/config failures actionable rather than silent empty
  listings.

## fsspec-backends-004 Implement Storacha fsspec list/read/write/delete behavior.

- status: completed
- completion: automatic
- priority: P0
- track: storacha
- depends on: fsspec-backends-001, fsspec-backends-002
- outputs: ipfs_kit_py/enhanced_fsspec.py, ipfs_kit_py/storacha_fsspec.py, tests/test_storacha_fsspec.py
- validation: pytest tests/test_storacha_fsspec.py -q
- acceptance: Storacha fsspec supports blob listing, blob info, upload, retrieval, delete, `open(..., "rb")`, and clear mock-mode behavior without requiring live credentials.

Implementation notes:

- Reuse existing `storacha_storage` or `enhanced_storacha_storage` methods when
  present instead of inventing a parallel API.
- Map `storacha://{digest_or_cid}` to blob retrieval and metadata lookup.
- Use existing endpoint fallback behavior from `mcp/extensions/storacha.py` as
  configuration guidance.
- Make `ls` reflect `list_blobs` results when available; otherwise document and
  test the unsupported-listing fallback.

## fsspec-backends-005 Implement Filecoin pin fsspec upload/status/retrieval behavior.

- status: completed
- completion: automatic
- priority: P0
- track: filecoin
- depends on: fsspec-backends-001, fsspec-backends-002
- outputs: ipfs_kit_py/filecoin_pin_fsspec.py, ipfs_kit_py/enhanced_fsspec.py, tests/test_filecoin_pin_fsspec.py
- validation: pytest tests/test_filecoin_pin_fsspec.py -q
- acceptance: Filecoin pin fsspec can upload local bytes/files, expose pin request metadata through `info`, check persistence/status through `exists`, retrieve by CID when a retrieval path is configured, and fail clearly when retrieval is unavailable.

Implementation notes:

- Treat Filecoin pin as a persistence backend over content identifiers, not as a
  fully mutable hierarchical filesystem.
- Support paths such as `filecoin://{cid}` and optional logical names through a
  local index if upload responses need path mapping.
- Integrate with any existing Filecoin pin client used by wallet storage code or
  `storage_backends_api.py`.
- Keep live pinning tests opt-in behind credentials and endpoint environment
  variables.

## fsspec-backends-006 Add shared backend metadata and path normalization helpers.

- status: completed
- completion: automatic
- priority: P1
- track: shared
- depends on: fsspec-backends-003, fsspec-backends-004, fsspec-backends-005
- outputs: ipfs_kit_py/fsspec_utils.py, tests/test_fsspec_utils.py
- validation: pytest tests/test_fsspec_utils.py tests/test_synapse_fsspec.py tests/test_storacha_fsspec.py tests/test_filecoin_pin_fsspec.py -q
- acceptance: Shared helpers normalize protocol paths, metadata dictionaries, optional local indexes, backend capability reports, and consistent fsspec error behavior across Synapse, Storacha, Filecoin pin, and Walrus.

Implementation notes:

- Provide helpers for `_strip_protocol`, `ensure_protocol`, `is_content_id`,
  `standard_file_info`, and optional JSON index read/write.
- Keep helpers small and dependency-light.
- Avoid moving stable IPFS code until backend tests protect behavior.

## fsspec-backends-007 Add mocked backend test suites and optional live integration gates.

- status: completed
- completion: automatic
- priority: P0
- track: tests
- depends on: fsspec-backends-003, fsspec-backends-004, fsspec-backends-005
- outputs: tests/test_enhanced_fsspec.py, tests/test_synapse_fsspec.py, tests/test_storacha_fsspec.py, tests/test_filecoin_pin_fsspec.py
- validation: pytest tests/test_enhanced_fsspec.py tests/test_synapse_fsspec.py tests/test_storacha_fsspec.py tests/test_filecoin_pin_fsspec.py -q
- acceptance: All fsspec backend behavior is covered by deterministic mocked tests, and live tests are skipped unless explicit backend-specific environment variables are set.

Implementation notes:

- Use fake clients or mocked HTTP transports for default CI tests.
- Cover dependency-missing paths and mock-mode behavior.
- Add protocol registration tests for fsspec discovery.
- Include a small compatibility matrix in test names or parametrized fixtures.

## fsspec-backends-008 Document backend capabilities, limitations, and examples.

- status: completed
- completion: automatic
- priority: P1
- track: docs
- depends on: fsspec-backends-003, fsspec-backends-004, fsspec-backends-005, fsspec-backends-007
- outputs: docs/integration/fsspec_backends.md, docs/integration/fsspec_integration.md
- validation: python -m compileall ipfs_kit_py/enhanced_fsspec.py
- acceptance: Documentation explains how to instantiate each backend, which fsspec methods are supported, what credentials/config are required, and which operations are content-addressed rather than path-mutable.

Implementation notes:

- Include examples for `synapse://`, `storacha://`, `filecoin://`, and `ipfs://`.
- Clearly label mock mode, live mode, and optional dependency groups.
- Document limitations around global listing, deletion, mutation, retrieval, and
  local index usage.
