"""KVFS-100: Canonical VFS authority and no-bypass mutation contracts.

Acceptance coverage:

* the ADR selects ``CanonicalVFSService`` as semantics authority;
* dispositions are recorded for VFSCore, VFSManager, legacy journals, Python,
  CLI, MCP, and future FUSE callers;
* storage, WAL, and cache cutover targets are named; and
* no advertised mutation bypasses the canonical service (adapter + service
  runtime proof).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import anyio
import pytest

from ipfs_kit_py.core.vfs.adapters import (
    LEGACY_VFS_OPERATION_KINDS,
    LegacyVFSAdapter,
)
from ipfs_kit_py.core.vfs.contracts import (
    MUTATING_OPERATIONS,
    VFSOperationKind,
)
from ipfs_kit_py.core.vfs.service import (
    CANONICAL_VFS_SERVICE_SCHEMA,
    CanonicalVFSService,
    CanonicalVFSService_V1,
    InMemoryVFSStorage,
    VFSExecuteRequest,
    VFSStorageBoundary,
    make_op,
)

# ---------------------------------------------------------------------------
# Paths / ADR loading
# ---------------------------------------------------------------------------

# test file: ipfs_kit_py/tests/kernel_vfs/contracts/test_authority.py
# parents[0]=contracts, [1]=kernel_vfs, [2]=tests, [3]=ipfs_kit_py package root
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
ADR_PATH = PACKAGE_ROOT / "docs" / "kernel_vfs" / "authority.md"

REQUIRED_DISPOSITIONS: dict[str, str] = {
    "CanonicalVFSService": "semantics_authority",
    "VFSCore": "compatibility_caller",
    "VFSManager": "compatibility_caller",
    "legacy_journals": "post_commit_recorder",
    "Python": "package_caller",
    "CLI": "compatibility_surface",
    "MCP": "compatibility_surface",
    "FUSE": "thin_callback_adapter",
}

REQUIRED_CUTOVERS: dict[str, str] = {
    "storage": "VFSStorageBoundary",
    "wal": "CanonicalWAL",
    "cache": "GenerationBoundARC",
}

# Human-facing surface names that must appear in the ADR prose/tables even if
# the machine ledger uses a slightly different key (legacy_journals).
REQUIRED_PROSE_SURFACES: tuple[str, ...] = (
    "CanonicalVFSService",
    "VFSCore",
    "VFSManager",
    "legacy journals",
    "Python",
    "CLI",
    "MCP",
    "FUSE",
)

LEDGER_FENCE_RE = re.compile(
    r"```authority-ledger\s*\n(?P<body>.*?)\n```",
    re.DOTALL,
)


def _load_adr_text() -> str:
    assert ADR_PATH.is_file(), f"authority ADR missing: {ADR_PATH}"
    return ADR_PATH.read_text(encoding="utf-8")


def _parse_authority_ledger(text: str) -> dict[str, str]:
    match = LEDGER_FENCE_RE.search(text)
    assert match is not None, "ADR must contain a fenced authority-ledger block"
    ledger: dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        assert ":" in line, f"malformed ledger line: {raw_line!r}"
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        assert key, f"empty ledger key in: {raw_line!r}"
        assert value, f"empty ledger value for key {key!r}"
        assert key not in ledger, f"duplicate ledger key: {key}"
        ledger[key] = value
    return ledger


# ---------------------------------------------------------------------------
# ADR selection and disposition
# ---------------------------------------------------------------------------


def test_adr_selects_canonical_vfs_service_as_semantics_authority() -> None:
    text = _load_adr_text()
    ledger = _parse_authority_ledger(text)

    assert ledger["decision_status"] == "Accepted"
    assert ledger["semantics_authority"] == "CanonicalVFSService"
    assert ledger["semantics_authority_alias"] == "CanonicalVFSService@1"
    assert ledger["semantics_authority_class"] == "CanonicalVFSService"
    assert ledger["semantics_authority_module"] == "ipfs_kit_py.core.vfs.service"

    # Prose must also state the selection (not only the machine block).
    assert "CanonicalVFSService is the sole semantics authority" in text
    assert "Decision status:** Accepted" in text or "**Status:** Accepted" in text


def test_adr_dispositions_for_all_required_surfaces() -> None:
    text = _load_adr_text()
    ledger = _parse_authority_ledger(text)

    for surface, disposition in REQUIRED_DISPOSITIONS.items():
        key = f"disposition.{surface}"
        assert key in ledger, f"missing disposition for {surface}"
        assert ledger[key] == disposition, (
            f"disposition for {surface}: expected {disposition}, got {ledger[key]}"
        )

    # Prose/table coverage for operator-facing names.
    lowered = text.lower()
    for surface in REQUIRED_PROSE_SURFACES:
        assert surface.lower() in lowered, f"ADR prose missing surface {surface!r}"

    # Disposition vocabulary must appear for the non-authority roles.
    for token in (
        "compatibility_caller",
        "compatibility_surface",
        "post_commit_recorder",
        "package_caller",
        "thin_callback_adapter",
        "semantics_authority",
    ):
        assert token in text


def test_adr_names_storage_wal_and_cache_cutover() -> None:
    text = _load_adr_text()
    ledger = _parse_authority_ledger(text)

    for layer, target in REQUIRED_CUTOVERS.items():
        key = f"cutover.{layer}"
        assert key in ledger, f"missing cutover for {layer}"
        assert ledger[key] == target
        # Named in prose as well as the ledger.
        assert target in text

    assert "storage" in text.lower()
    assert "wal" in text.lower()
    assert "cache" in text.lower()
    assert "GenerationBoundARC" in text
    assert "VFSStorageBoundary" in text
    assert "CanonicalWAL" in text


def test_adr_states_no_bypass_invariants() -> None:
    text = _load_adr_text()
    ledger = _parse_authority_ledger(text)

    assert ledger["invariant.no_advertised_mutation_bypass"] == "true"
    assert ledger["invariant.success_requires_observed_transition"] == "true"
    assert ledger["invariant.journal_is_not_mutation_authority"] == "true"
    assert ledger["invariant.fuse_is_not_second_vfs"] == "true"
    assert "No-bypass mutation invariant" in text
    assert "not a second VFS" in text or "never a second VFS" in text


# ---------------------------------------------------------------------------
# Runtime authority surface
# ---------------------------------------------------------------------------


def test_canonical_service_identity_matches_adr() -> None:
    ledger = _parse_authority_ledger(_load_adr_text())
    assert CanonicalVFSService.__name__ == ledger["semantics_authority_class"]
    assert CanonicalVFSService_V1 == CANONICAL_VFS_SERVICE_SCHEMA
    assert CanonicalVFSService_V1.endswith("@1")
    assert CanonicalVFSService.CONTRACT_VERSION == 1
    assert ledger["semantics_authority_alias"].startswith("CanonicalVFSService@")


def test_storage_cutover_type_is_the_only_service_side_effect_boundary() -> None:
    """Canonical service storage property is a VFSStorageBoundary."""
    storage = InMemoryVFSStorage()
    service = CanonicalVFSService(storage=storage, clock=lambda: 1_700_000_000_000)
    assert isinstance(service.storage, VFSStorageBoundary)
    assert service.storage is storage


class _CountingStorage:
    """Storage double that records every mutating boundary call."""

    def __init__(self, inner: InMemoryVFSStorage) -> None:
        self.inner = inner
        self.puts = 0
        self.deletes = 0
        self.renames = 0

    def get(self, path: str) -> Any:
        return self.inner.get(path)

    def put(self, path: str, entry: Any) -> None:
        self.puts += 1
        self.inner.put(path, entry)

    def delete(self, path: str) -> None:
        self.deletes += 1
        self.inner.delete(path)

    def children(self, path: str) -> tuple[str, ...]:
        return self.inner.children(path)

    def rename(self, source: str, target: str) -> None:
        self.renames += 1
        self.inner.rename(source, target)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return self.inner.snapshot()

    @property
    def generation(self) -> int:
        return self.inner.generation

    def bump_generation(self) -> int:
        return self.inner.bump_generation()

    def entry_count(self) -> int:
        return self.inner.entry_count()


class _SpyService(CanonicalVFSService):
    """Service that records every execute admission."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.execute_calls: list[tuple[VFSOperationKind, str]] = []

    def execute(self, operation: Any, request: Any = None) -> Any:  # type: ignore[override]
        self.execute_calls.append((operation.kind, operation.operation_id))
        return super().execute(operation, request)


def test_advertised_mutations_only_touch_storage_through_canonical_execute() -> None:
    inner = InMemoryVFSStorage()
    storage = _CountingStorage(inner)
    service = _SpyService(storage=storage, clock=lambda: 1_700_000_000_000)  # type: ignore[arg-type]

    baseline_puts = storage.puts
    # Direct storage writes are possible only if a caller holds the boundary;
    # advertised mutations must go through execute, which is what we prove next.
    mkdir = service.execute(
        make_op(VFSOperationKind.MKDIR, operation_id="op:mkdir-a", path="a")
    )
    assert mkdir.success is True
    assert storage.puts > baseline_puts
    assert service.execute_calls[-1] == (VFSOperationKind.MKDIR, "op:mkdir-a")

    create = service.execute(
        make_op(VFSOperationKind.CREATE, operation_id="op:create-a-f", path="a/f"),
        VFSExecuteRequest(payload=b"payload"),
    )
    assert create.success is True
    assert create.result.observed_transition is not None
    assert create.result.observed_transition.observation_id

    # Failed mutation must not emit success or leave a success event.
    missing = service.execute(
        make_op(VFSOperationKind.DELETE, operation_id="op:del-missing", path="nope")
    )
    assert missing.success is False
    assert all(event.kind.value != "success" for event in missing.events)


def test_legacy_adapter_advertised_mutations_cannot_bypass_canonical_service() -> None:
    inner = InMemoryVFSStorage()
    storage = _CountingStorage(inner)
    service = _SpyService(storage=storage, clock=lambda: 1_700_000_000_000)  # type: ignore[arg-type]
    adapter = LegacyVFSAdapter(service=service)

    # Closed vocabulary only — unknown names never become success or mutate.
    unsupported = anyio.run(
        lambda: adapter.execute("provider_only_mutation", path="x", data=b"y")
    )
    assert unsupported["success"] is False
    assert unsupported["code"] == "unsupported_legacy_operation"
    assert service.execute_calls == []
    assert storage.puts == 0
    assert storage.deletes == 0
    assert storage.renames == 0

    mkdir = anyio.run(lambda: adapter.execute("mkdir", path="docs"))
    assert mkdir["success"] is True
    assert service.execute_calls, "mkdir must enter CanonicalVFSService.execute"
    assert service.execute_calls[-1][0] is VFSOperationKind.MKDIR
    assert storage.puts >= 1

    write = anyio.run(
        lambda: adapter.execute("write", path="docs/readme", data=b"hello")
    )
    # Legacy "write" maps to REPLACE; path must exist for replace in canonical
    # service, so create first if needed.
    if write["success"] is not True:
        # Prefer create via replace only when parent exists; seed via service.
        created = service.execute(
            make_op(VFSOperationKind.CREATE, operation_id="op:seed", path="docs/readme"),
            VFSExecuteRequest(payload=b"seed"),
        )
        assert created.success is True
        write = anyio.run(
            lambda: adapter.execute("write", path="docs/readme", data=b"hello")
        )
    assert write["success"] is True
    assert any(kind is VFSOperationKind.REPLACE for kind, _ in service.execute_calls)

    # Failed canonical result never becomes adapter success.
    missing = anyio.run(lambda: adapter.execute("rm", path="does-not-exist"))
    assert missing["success"] is False
    assert missing.get("result", {}).get("success") is False


def test_all_legacy_advertised_mutating_ops_route_through_service_execute() -> None:
    """Every legacy name that maps to a mutating kind must call execute."""
    mutating_legacy = {
        name: kind
        for name, kind in LEGACY_VFS_OPERATION_KINDS.items()
        if kind in MUTATING_OPERATIONS
    }
    assert mutating_legacy, "expected at least one mutating legacy mapping"

    for legacy_name, kind in sorted(mutating_legacy.items()):
        inner = InMemoryVFSStorage()
        service = _SpyService(storage=inner, clock=lambda: 1_700_000_000_000)
        adapter = LegacyVFSAdapter(service=service)

        kwargs: dict[str, Any] = {}
        if kind in {VFSOperationKind.RENAME, VFSOperationKind.MOVE}:
            # Seed a source so the request is well-formed even if the op fails.
            service.execute(
                make_op(VFSOperationKind.CREATE, operation_id="seed-src", path="src"),
                VFSExecuteRequest(payload=b"x"),
            )
            service.execute_calls.clear()
            kwargs = {"source_path": "src", "target_path": "dst"}
        elif kind is VFSOperationKind.REPLACE:
            service.execute(
                make_op(VFSOperationKind.CREATE, operation_id="seed-f", path="f"),
                VFSExecuteRequest(payload=b"old"),
            )
            service.execute_calls.clear()
            kwargs = {"path": "f", "data": b"new"}
        elif kind is VFSOperationKind.DELETE:
            service.execute(
                make_op(VFSOperationKind.CREATE, operation_id="seed-d", path="d"),
                VFSExecuteRequest(payload=b"z"),
            )
            service.execute_calls.clear()
            kwargs = {"path": "d"}
        elif kind is VFSOperationKind.MKDIR:
            kwargs = {"path": "dir"}
        elif kind is VFSOperationKind.RMDIR:
            service.execute(
                make_op(VFSOperationKind.MKDIR, operation_id="seed-dir", path="dir")
            )
            service.execute_calls.clear()
            kwargs = {"path": "dir"}
        else:
            kwargs = {"path": "p", "data": b"body"}

        result = anyio.run(lambda n=legacy_name, k=dict(kwargs): adapter.execute(n, **k))
        assert isinstance(result, Mapping)
        assert service.execute_calls, (
            f"legacy op {legacy_name!r} ({kind.value}) bypassed CanonicalVFSService.execute"
        )
        assert service.execute_calls[-1][0] is kind


def test_mutating_success_requires_observed_state_transition() -> None:
    service = CanonicalVFSService(
        storage=InMemoryVFSStorage(),
        clock=lambda: 1_700_000_000_000,
    )
    for index, kind in enumerate(
        sorted(MUTATING_OPERATIONS, key=lambda k: k.value),
        start=1,
    ):
        if kind in {VFSOperationKind.MOUNT, VFSOperationKind.UNMOUNT}:
            # Mount/unmount exercise a different path; still must not claim
            # unobserved success when they do succeed. Build a minimal mkdir
            # probe for the core mutation invariant instead for non-namespace
            # kinds when mount setup is out of scope here.
            continue
        if kind is VFSOperationKind.MKDIR:
            op = make_op(kind, operation_id=f"op:m-{index}", path=f"d{index}")
            req = None
        elif kind is VFSOperationKind.CREATE:
            op = make_op(kind, operation_id=f"op:m-{index}", path=f"f{index}")
            req = VFSExecuteRequest(payload=b"x")
        elif kind is VFSOperationKind.REPLACE:
            service.execute(
                make_op(VFSOperationKind.CREATE, operation_id=f"seed-{index}", path=f"r{index}"),
                VFSExecuteRequest(payload=b"old"),
            )
            op = make_op(kind, operation_id=f"op:m-{index}", path=f"r{index}")
            req = VFSExecuteRequest(payload=b"new")
        elif kind is VFSOperationKind.DELETE:
            service.execute(
                make_op(VFSOperationKind.CREATE, operation_id=f"seed-del-{index}", path=f"x{index}"),
                VFSExecuteRequest(payload=b"z"),
            )
            op = make_op(kind, operation_id=f"op:m-{index}", path=f"x{index}")
            req = None
        elif kind is VFSOperationKind.RMDIR:
            service.execute(
                make_op(VFSOperationKind.MKDIR, operation_id=f"seed-rd-{index}", path=f"rd{index}")
            )
            op = make_op(kind, operation_id=f"op:m-{index}", path=f"rd{index}")
            req = None
        elif kind in {VFSOperationKind.RENAME, VFSOperationKind.MOVE}:
            service.execute(
                make_op(
                    VFSOperationKind.CREATE,
                    operation_id=f"seed-rn-{index}",
                    path=f"src{index}",
                ),
                VFSExecuteRequest(payload=b"v"),
            )
            op = make_op(
                kind,
                operation_id=f"op:m-{index}",
                source_path=f"src{index}",
                target_path=f"dst{index}",
            )
            req = None
        elif kind is VFSOperationKind.CAS_WRITE:
            created = service.execute(
                make_op(
                    VFSOperationKind.CREATE,
                    operation_id=f"seed-cas-{index}",
                    path=f"c{index}",
                ),
                VFSExecuteRequest(payload=b"v1"),
            )
            assert created.success is True
            version = created.result.resulting_version_cid
            assert version, "create must yield a version identity for CAS"
            op = make_op(
                kind,
                operation_id=f"op:m-{index}",
                path=f"c{index}",
                precondition_version_cid=version,
            )
            req = VFSExecuteRequest(payload=b"v2")
        else:
            pytest.fail(f"unhandled mutating kind in authority test: {kind}")

        outcome = service.execute(op, req)
        if outcome.success:
            transition = outcome.result.observed_transition
            assert transition is not None
            assert transition.observation_id
            assert outcome.result.success is True
        else:
            # Even failures must not carry a success event.
            assert all(event.kind.value != "success" for event in outcome.events)


def test_journal_recorder_cannot_manufacture_success_or_bypass_service() -> None:
    """post_commit_recorder disposition: journals only see committed results."""

    class ForbiddenJournal:
        def record_operation(self, *args: Any, **kwargs: Any) -> str:
            raise AssertionError("journal must not be consulted for failed mutations")

        def get_entries(self, *, limit: int = 100) -> list[dict[str, Any]]:
            del limit
            return []

    service = CanonicalVFSService(
        storage=InMemoryVFSStorage(),
        clock=lambda: 1_700_000_000_000,
    )
    adapter = LegacyVFSAdapter(service=service, journal=ForbiddenJournal())

    failed = anyio.run(lambda: adapter.execute("rm", path="missing-path"))
    assert failed["success"] is False
    # record_committed_operation must refuse non-committed results.
    assert adapter.record_committed_operation(failed, "rm", "missing-path") is None

    class RecordingJournal:
        def __init__(self) -> None:
            self.entries: list[dict[str, Any]] = []

        def record_operation(
            self,
            operation_type: str,
            path: str,
            details: dict[str, Any] | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> str:
            self.entries.append(
                {
                    "operation_type": operation_type,
                    "path": path,
                    "details": details or {},
                    "metadata": metadata or {},
                }
            )
            return f"j-{len(self.entries)}"

        def get_entries(self, *, limit: int = 100) -> list[dict[str, Any]]:
            return self.entries[:limit]

    journal = RecordingJournal()
    adapter.set_journal(journal)
    created = anyio.run(lambda: adapter.execute("mkdir", path="recorded"))
    assert created["success"] is True
    assert adapter.record_committed_operation(created, "mkdir", "recorded") == "j-1"
    assert journal.entries[0]["operation_type"] == "mkdir"
    # Journal entry is a recording, not a substitute for service.execute.
    assert service.storage.get("recorded") is not None


def test_adapter_service_property_exposes_semantics_authority() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    adapter = LegacyVFSAdapter(service=service)
    assert adapter.service is service
    assert isinstance(adapter.service, CanonicalVFSService)


def test_cutover_targets_are_importable_or_named_consistently() -> None:
    """Storage and cache cutover types exist; WAL package path is present."""
    from ipfs_kit_py.arc_cache import GenerationBoundARC
    from ipfs_kit_py.core.vfs.service import VFSStorageBoundary as StorageBoundary
    from ipfs_kit_py.core.wal import contracts as wal_contracts

    ledger = _parse_authority_ledger(_load_adr_text())
    assert ledger["cutover.storage"] == StorageBoundary.__name__
    assert ledger["cutover.cache"] == GenerationBoundARC.__name__
    assert ledger["cutover.wal"] == "CanonicalWAL"
    assert wal_contracts.CONTRACT_VERSION >= 1
    # Package path named in the ADR.
    text = _load_adr_text()
    assert "ipfs_kit_py.core.wal" in text or "ipfs_kit_py/core/wal" in text


def test_no_legacy_dynamic_dispatch_reopens_bypass() -> None:
    """Adapter must remain a closed map — no getattr-style provider escape."""
    assert "provider_only_operation" not in LEGACY_VFS_OPERATION_KINDS
    adapter = LegacyVFSAdapter()
    # Attribute discovery of arbitrary methods is not the mutation path.
    assert not hasattr(adapter, "provider_only_operation")
    result = anyio.run(lambda: adapter.execute("getattr_escape", path="/"))
    assert result["success"] is False
    assert result["code"] == "unsupported_legacy_operation"
