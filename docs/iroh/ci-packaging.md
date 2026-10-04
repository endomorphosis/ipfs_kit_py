# Iroh CI, Packaging, And Coverage Gates

IROH-026 is enforced by `.github/workflows/iroh-ci.yml`. All ordinary lanes are
offline with respect to Iroh: they must neither download nor discover a sidecar,
and `IPFS_KIT_AUTO_INSTALL_BINARIES` is disabled. A missing Iroh executable is a
supported package state, while storage operations still fail closed through the
typed runtime errors.

## Required lanes

| Lane | Required evidence |
| --- | --- |
| Unit | Backend, blob, manifest, GC, runtime, observability, performance, and VFS tests on Python 3.12 and 3.13. |
| fsspec conformance | Read, write, async, and registration tests on Linux, macOS, and Windows, once with external `fsspec` and once with the vendored fallback. |
| Async | Cancellation, concurrency, async file handle, blob, and RPC behavior. |
| Service | Configuration, lifecycle ownership, readiness, crash, and observability behavior. |
| Installer | Target detection, verified install, explicit CLI lifecycle, rollback, and missing-binary behavior. |
| Security | Supply-chain, path/manifest validation, secret rejection, redaction, permission, and GC safety vectors. |
| Platform/architecture | Frozen targets on Linux, macOS, and Windows; Linux AMD64 and ARM64 execute under native container semantics or QEMU. |
| Packaging | Two wheel/sdist builds, archive audit, metadata check, and clean-environment install smoke tests on Python 3.12/3.13 and all supported operating-system families. |
| Coverage | Branch coverage in terminal, XML, JSON, and HTML forms with a 70% aggregate floor over the Iroh implementation. |
| Multi-node | Explicitly dispatched, environment-protected real-node scenarios from IROH-025. It is never part of an offline pull-request run. |
| Release readiness | After all required offline, platform, distribution, and coverage jobs pass, validate the disabled-stage policy, receipt ledger, non-destructive rollback invariants, and release notes; upload `iroh-release-signoff`. |

No required job uses `continue-on-error`, and test commands do not mask their
exit status. The multi-node job requires the `iroh-interoperability` environment
and a self-hosted runner labeled `iroh-interop`. That environment supplies the
reviewed driver and current/previous executable paths. Relay configuration is a
secret and the resulting redacted evidence JSON is retained as a CI artifact.

## Distribution contract

Build with a fixed source epoch and audit the result:

```bash
export SOURCE_DATE_EPOCH="$(git log -1 --pretty=%ct)"
python -m build --outdir build/iroh-dist-a
python scripts/ci/verify_iroh_distributions.py build/iroh-dist-a/* \
  --report build/iroh-packaging-report.json
```

The audit requires the Iroh modules, JSON schemas/evidence, console scripts,
fsspec entry points, and conditional `iroh`/`fsspec` dependency metadata. It
rejects Python caches, runtime receipts, credentials, the managed binary
directory, and any bundled Iroh sidecar. Comparing two build directories also
requires identical normalized archive contents and reports whether their raw
container bytes are identical.

The install smoke script is run from fresh virtual environments against both a
wheel and an sdist. It checks resource loading and imports without the sidecar,
proves import does not create the managed binary directory, and exercises both
external and vendored fsspec selection. Run the local contract with:

```bash
python -m pytest -q tests/test_iroh_packaging.py
```

## Coverage report

CI uploads `iroh-coverage-report`, containing:

- `iroh-coverage.xml` for coverage services and release automation;
- `iroh-coverage.json` for machine-readable release evidence;
- `iroh-html/` for human review.

The report covers `ipfs_kit_py.iroh`, the fsspec/VFS adapters, installer and
installer CLI, and backend adapter. Network-only multi-node execution remains a
separate evidence artifact so offline coverage cannot silently claim a real
interoperability run.

## Release sign-off

The final required job runs `tests/test_iroh_release_readiness.py`, then invokes
`scripts/ci/verify_iroh_release_readiness.py --target-stage disabled`. It uploads
the machine readiness report, receipt ledger, generated verification summary,
and human release notes. This job approves only the disabled-by-default stage.
Experimental, canary, and supported promotion require a newly reviewed report;
the verifier fails closed when asked to approve an unsigned higher stage.
