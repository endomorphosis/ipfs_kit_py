"""Safety, recovery, and audit coverage for Iroh reference collection."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.iroh.errors import IrohConflictError, IrohIntegrityError
from ipfs_kit_py.iroh.gc import (
    GCPolicy,
    IrohGarbageCollector,
    ReferenceTracker,
    verify_gc_receipt,
)
from ipfs_kit_py.iroh.manifest import DirectoryManifest, ManifestEntry, ParentRevision

NAMESPACE_A = "a" * 64
NAMESPACE_B = "b" * 64
WRITER = "c" * 64
BLOB_A = "d" * 64
BLOB_B = "e" * 64
NOW = "2026-07-13T12:00:00Z"


class Clock:
    def __init__(self) -> None:
        self.value = 1_784_000_000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def make_manifest(
    namespace: str,
    revision: int,
    files: dict[str, tuple[str, int]],
    *,
    parent_hash: str | None = None,
) -> DirectoryManifest:
    entries = [ManifestEntry.root(mtime=NOW)]
    entries.extend(
        ManifestEntry(path, "file", False, 0o644, NOW, {}, digest, size)
        for path, (digest, size) in files.items()
    )
    return DirectoryManifest.create(
        namespace,
        WRITER,
        revision,
        entries,
        parent_revision=(
            None if revision == 0 else ParentRevision(revision - 1, parent_hash or "0" * 64)
        ),
        created_at=NOW,
    )


@pytest.mark.asyncio
async def test_default_retention_never_deletes_newly_unreferenced_data() -> None:
    clock = Clock()
    index = ReferenceTracker(clock=clock)
    index.register_blob(BLOB_A, 10)
    deleted: list[str] = []
    collector = IrohGarbageCollector(index, delete_blob=lambda digest: deleted.append(digest))

    receipt = await collector.collect(dry_run=False)

    assert receipt.deleted == ()
    assert deleted == []
    clock.advance(24 * 60 * 60 + 1)
    receipt = await collector.collect(dry_run=False)
    assert receipt.deleted == (BLOB_A,)
    assert receipt.reclaimed_bytes == 10


@pytest.mark.asyncio
async def test_revisions_namespaces_and_leases_are_all_gc_roots() -> None:
    clock = Clock()
    index = ReferenceTracker(clock=clock)
    first = make_manifest(NAMESPACE_A, 0, {"old": (BLOB_A, 10)})
    second = make_manifest(NAMESPACE_A, 1, {"new": (BLOB_B, 10)}, parent_hash=first.manifest_hash)
    index.track_manifest(first)
    index.track_manifest(second)
    index.track_manifest(make_manifest(NAMESPACE_B, 0, {"shared": (BLOB_A, 10)}))
    index.retire_revision(NAMESPACE_A, 0, retain_for=0)
    collector = IrohGarbageCollector(index)

    assert (await collector.mark(GCPolicy(0))).candidates == ()
    index.retire_revision(NAMESPACE_B, 0, retain_for=0)
    mark = await collector.mark(GCPolicy(0))
    assert tuple(item.blob_hash for item in mark.candidates) == (BLOB_A,)

    # A reader/writer lease is renewable and works as both a sync and async
    # context manager. It protects the blob independently of manifest state.
    with index.acquire_lease(BLOB_A, ttl_seconds=10, owner="reader") as lease:
        assert (await collector.mark(GCPolicy(0))).candidates == ()
        lease.renew(20)
    after_release = await collector.mark(GCPolicy(0))
    assert tuple(item.blob_hash for item in after_release.candidates) == (BLOB_A,)


@pytest.mark.asyncio
async def test_reference_added_between_mark_and_sweep_wins() -> None:
    clock = Clock()
    index = ReferenceTracker(clock=clock)
    index.register_blob(BLOB_A, 10)
    calls: list[str] = []
    collector = IrohGarbageCollector(index, delete_blob=lambda digest: calls.append(digest))
    mark = await collector.mark(GCPolicy(0), dry_run=False)

    index.track_manifest(make_manifest(NAMESPACE_A, 0, {"new": (BLOB_A, 10)}))
    receipt = await collector.sweep(mark, dry_run=False)

    assert receipt.deleted == ()
    assert receipt.skipped == (BLOB_A,)
    assert calls == []


@pytest.mark.asyncio
async def test_quota_and_sweep_limits_never_override_references() -> None:
    index = ReferenceTracker(clock=Clock())
    index.track_manifest(make_manifest(NAMESPACE_A, 0, {"live": (BLOB_A, 10)}))
    index.register_blob(BLOB_B, 20)
    index.set_quota(NAMESPACE_A, 10)
    assert index.enforce_quota(NAMESPACE_A).allowed
    with pytest.raises(IrohConflictError):
        index.enforce_quota(NAMESPACE_A, additional_bytes=1)

    collector = IrohGarbageCollector(index)
    mark = await collector.mark(
        GCPolicy(0, max_delete_bytes=20, max_delete_count=1, quota_bytes=10)
    )
    assert tuple(item.blob_hash for item in mark.candidates) == (BLOB_B,)
    assert BLOB_A not in {item.blob_hash for item in mark.candidates}


@pytest.mark.asyncio
async def test_interrupted_sweep_resumes_with_idempotent_operation_id() -> None:
    index = ReferenceTracker(clock=Clock())
    index.register_blob(BLOB_A, 10)
    calls: list[tuple[str, str]] = []

    async def release(digest: str, operation_id: str) -> None:
        calls.append((digest, operation_id))
        if len(calls) == 1:
            raise asyncio.CancelledError

    collector = IrohGarbageCollector(index, delete_blob=release)
    mark = await collector.mark(GCPolicy(0), dry_run=False, run_id="recoverable")
    with pytest.raises(asyncio.CancelledError):
        await collector.sweep(mark)
    receipt = await collector.resume(mark.run_id)

    assert receipt.deleted == (BLOB_A,)
    assert calls[0] == calls[1]
    clock = collector.clock
    assert isinstance(clock, Clock)
    clock.advance(60)
    assert await collector.resume(mark.run_id) == receipt
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_dry_run_receipt_is_private_and_tamper_evident(tmp_path: Path) -> None:
    index = ReferenceTracker(tmp_path / "references.duckdb", clock=Clock())
    index.register_blob(BLOB_A, 10)
    receipt = await IrohGarbageCollector(index).collect(
        dry_run=True, policy=GCPolicy(retention_seconds=0)
    )
    path = receipt.write(tmp_path / "receipts" / "gc.json")

    assert path.stat().st_mode & 0o777 == 0o600
    assert verify_gc_receipt(path) == receipt
    damaged: dict[str, Any] = json.loads(path.read_text())
    damaged["reclaimed_bytes"] = 1
    with pytest.raises(IrohIntegrityError):
        verify_gc_receipt(damaged)


def test_repair_is_dry_run_by_default_and_reports_missing_inventory() -> None:
    index = ReferenceTracker(clock=Clock())
    value = make_manifest(NAMESPACE_A, 0, {"file": (BLOB_A, 10)})
    receipt = index.repair([value], [(BLOB_B, 10)])
    assert receipt.dry_run is True
    assert receipt.references_added == 1
    assert receipt.missing_blobs == (BLOB_A,)
    assert index.quota_usage() == 0

    applied = index.repair([value], [(BLOB_A, 10)], dry_run=False)
    assert applied.dry_run is False
    assert index.quota_usage(NAMESPACE_A) == 10
