"""Deterministic resource and performance baseline checks for IROH-016."""

from __future__ import annotations

import copy
from typing import Any

import anyio
import blake3
import pytest

from ipfs_kit_py.iroh_fsspec import IrohAsyncFileSystem, IrohFileSystem
from ipfs_kit_py.iroh_performance import (
    IrohPerformanceSample,
    benchmark_async_filesystem,
    evaluate_sample,
    load_iroh_performance_baseline,
)


NAMESPACE = "b" * 64
HEAD = "e" * 64


def digest(value: bytes) -> str:
    return blake3.blake3(value).hexdigest()


class ManifestStore:
    def __init__(self, value: bytes) -> None:
        self.manifest = {
            "namespace_id": NAMESPACE,
            "revision": 1,
            "entries": [
                {"path": "", "kind": "directory", "mode": 0o755},
                {
                    "path": "payload.bin",
                    "kind": "file",
                    "blob_hash": digest(value),
                    "size": len(value),
                    "mode": 0o644,
                },
            ],
        }

    async def read_head(self, namespace_id: str) -> dict[str, Any]:
        assert namespace_id == NAMESPACE
        return {"manifest": copy.deepcopy(self.manifest), "head": HEAD}

    async def compare_and_swap(
        self, namespace_id: str, expected_head: str, new_manifest: dict[str, Any]
    ) -> dict[str, Any]:
        self.manifest = copy.deepcopy(new_manifest)
        return {"committed": True}


class MeasuredBlobStore:
    def __init__(self, value: bytes) -> None:
        self.values = {digest(value): value}
        self.ranges: list[int] = []
        self.parts: list[int] = []

    async def stat(self, blob_hash: str) -> dict[str, Any]:
        return {"size": len(self.values[blob_hash]), "complete": True}

    async def read_range(self, blob_hash: str, *, start: int, end: int) -> bytes:
        self.ranges.append(end - start)
        return self.values[blob_hash][start:end]

    def ingest_parts(
        self, parts: Any, *, total_size: int, part_size: int
    ) -> dict[str, Any]:
        collected = []
        for part in parts:
            self.parts.append(len(part))
            assert len(part) <= part_size
            collected.append(part)
        value = b"".join(collected)
        assert len(value) == total_size
        blob_hash = digest(value)
        self.values[blob_hash] = value
        return {"blob_hash": blob_hash, "size": len(value)}

    async def ingest(self, source: Any) -> dict[str, Any]:
        value = source.read()
        blob_hash = digest(value)
        self.values[blob_hash] = value
        return {"blob_hash": blob_hash, "size": len(value)}


def test_packaged_baseline_has_explicit_latency_throughput_and_memory_budgets() -> None:
    baseline = load_iroh_performance_baseline()
    budgets = baseline["budgets"]
    assert baseline["schema_version"] == 1
    assert budgets["metadata_p95_ms"] > 0
    assert budgets["sequential_read_min_mib_s"] > 0
    assert budgets["parallel_read_min_mib_s"] > 0
    assert budgets["retained_cache_max_bytes"] == 16 * 1024 * 1024
    assert evaluate_sample(
        IrohPerformanceSample(1, 1, 100, 100, 1024, 1024, 2), baseline
    ) == []
    assert "retained_cache_bytes" in evaluate_sample(
        IrohPerformanceSample(1, 1, 100, 100, 32 * 1024 * 1024), baseline
    )


@pytest.mark.anyio
async def test_benchmark_runner_meets_in_memory_latency_and_throughput_floor() -> None:
    value = bytes(range(256)) * 4096  # 1 MiB
    blobs = MeasuredBlobStore(value)
    fs = IrohAsyncFileSystem(
        manifest_store=ManifestStore(value),
        blob_store=blobs,
        read_ahead_size=64 * 1024,
        range_cache_size=2 * 1024 * 1024,
    )
    sample = await benchmark_async_filesystem(
        fs,
        f"iroh://{NAMESPACE}/payload.bin",
        payload_bytes=len(value),
        range_bytes=64 * 1024,
        iterations=5,
        parallelism=4,
    )
    assert sample.metadata_p95_ms < 50
    assert sample.warm_range_p95_ms < 10
    assert sample.sequential_read_mib_s >= 20
    assert sample.parallel_read_mib_s >= 40
    assert sample.retained_cache_bytes <= 2 * 1024 * 1024
    assert max(blobs.ranges) <= 64 * 1024


def test_range_cache_and_multipart_staging_remain_bounded() -> None:
    value = bytes(range(256)) * 4096
    manifests = ManifestStore(value)
    blobs = MeasuredBlobStore(value)
    fs = IrohFileSystem(
        manifest_store=manifests,
        blob_store=blobs,
        block_size=32 * 1024,
        read_ahead_size=64 * 1024,
        range_cache_size=128 * 1024,
        multipart_threshold=64 * 1024,
        multipart_part_size=32 * 1024,
    )
    path = f"iroh://{NAMESPACE}/payload.bin"
    for start in range(0, len(value), 64 * 1024):
        assert fs.cat_file(path, start, start + 1) == value[start : start + 1]
    assert fs.cache_info()["bytes"] <= 128 * 1024
    assert fs.cache_info()["evictions"] > 0
    assert max(blobs.ranges) <= 64 * 1024

    with fs.open(f"iroh://{NAMESPACE}/replacement.bin", "wb") as handle:
        handle.write(value)
        assert getattr(handle._staging, "_rolled", True) is True
    assert blobs.parts
    assert max(blobs.parts) <= 32 * 1024
    assert sum(blobs.parts) == len(value)
