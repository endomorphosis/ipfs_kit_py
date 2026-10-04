"""Async conformance for the bounded Iroh fsspec adapter."""

from __future__ import annotations

import copy
import threading
import time
from typing import Any

import anyio
import blake3
import pytest

from ipfs_kit_py.iroh_fsspec import IrohAsyncFileSystem


NAMESPACE = "a" * 64
HEAD = "f" * 64


def digest(value: bytes) -> str:
    return blake3.blake3(value).hexdigest()


def url(path: str) -> str:
    return f"iroh://{NAMESPACE}/{path}"


class ManifestStore:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.manifest = {
            "namespace_id": NAMESPACE,
            "revision": 1,
            "entries": [
                {"path": "", "kind": "directory", "mode": 0o755},
                *[
                    {
                        "path": name,
                        "kind": "file",
                        "blob_hash": digest(value),
                        "size": len(value),
                        "mode": 0o644,
                    }
                    for name, value in payloads.items()
                ],
            ],
        }
        self.cas_calls = 0

    async def read_head(self, namespace_id: str) -> dict[str, Any]:
        assert namespace_id == NAMESPACE
        return {"manifest": copy.deepcopy(self.manifest), "head": HEAD}

    async def compare_and_swap(
        self, namespace_id: str, expected_head: str, new_manifest: dict[str, Any]
    ) -> dict[str, Any]:
        assert namespace_id == NAMESPACE and expected_head == HEAD
        self.cas_calls += 1
        self.manifest = copy.deepcopy(new_manifest)
        return {"committed": True}


class BlobStore:
    def __init__(self, payloads: dict[str, bytes], *, delay: float = 0.0) -> None:
        self.values = {digest(value): value for value in payloads.values()}
        self.delay = delay
        self.ranges: list[tuple[int, int]] = []
        self.active = 0
        self.peak_active = 0
        self._lock = threading.Lock()

    async def stat(self, blob_hash: str) -> dict[str, Any]:
        return {"size": len(self.values[blob_hash]), "complete": True}

    async def read_range(self, blob_hash: str, *, start: int, end: int) -> bytes:
        with self._lock:
            self.active += 1
            self.peak_active = max(self.peak_active, self.active)
        try:
            if self.delay:
                await anyio.sleep(self.delay)
            self.ranges.append((start, end))
            return self.values[blob_hash][start:end]
        finally:
            with self._lock:
                self.active -= 1

    async def ingest(self, source: Any) -> dict[str, Any]:
        source.seek(0)
        value = source.read()
        blob_hash = digest(value)
        self.values[blob_hash] = value
        return {"blob_hash": blob_hash, "size": len(value)}


@pytest.mark.anyio
async def test_async_read_discovery_open_and_range_cache_parity() -> None:
    payload = bytes(range(128))
    manifests = ManifestStore({"value.bin": payload})
    blobs = BlobStore({"value.bin": payload})
    fs = IrohAsyncFileSystem(
        manifest_store=manifests,
        blob_store=blobs,
        block_size=8,
        read_ahead_size=16,
        range_cache_size=32,
    )

    assert (await fs._info(url("value.bin")))["size"] == len(payload)
    assert await fs._ls(f"iroh://{NAMESPACE}/", detail=False) == [url("value.bin")]
    assert await fs._find(f"iroh://{NAMESPACE}/") == [url("value.bin")]
    assert await fs._glob(url("*.bin")) == [url("value.bin")]
    assert await fs._exists(url("missing")) is False

    async with await fs.open_async(url("value.bin"), "rb") as handle:
        assert await handle.read(5) == payload[:5]
        assert await handle.read(5) == payload[5:10]
        assert await handle.seek(-4, 2) == len(payload) - 4
        assert await handle.read() == payload[-4:]

    # Two adjacent small reads share one aligned transport request.
    assert blobs.ranges.count((0, 16)) == 1
    cache = fs.cache_info()
    assert cache["hits"] >= 1
    assert cache["bytes"] <= cache["max_bytes"] == 32


@pytest.mark.anyio
async def test_parallel_ranges_are_bounded_and_cancellation_is_cooperative() -> None:
    payloads = {f"{index}.bin": bytes([index]) * 64 for index in range(12)}
    blobs = BlobStore(payloads, delay=0.02)
    fs = IrohAsyncFileSystem(
        manifest_store=ManifestStore(payloads),
        blob_store=blobs,
        max_concurrency=3,
        max_pending_operations=6,
        read_ahead_size=8,
        range_cache_size=0,
    )

    values = await fs._cat_ranges(
        [url(name) for name in payloads], [0] * len(payloads), [8] * len(payloads)
    )
    assert values == [value[:8] for value in payloads.values()]
    assert 1 < blobs.peak_active <= 3

    with anyio.move_on_after(0.005) as scope:
        await fs._cat_file(url("0.bin"), 16, 24)
    assert scope.cancel_called
    await anyio.sleep(0)
    assert blobs.active == 0


@pytest.mark.anyio
async def test_sync_collaborators_yield_and_client_factory_is_reused() -> None:
    payload = b"x" * 32
    manifests = ManifestStore({"value.bin": payload})

    class BlockingBlobs(BlobStore):
        def read_range(self, blob_hash: str, *, start: int, end: int) -> bytes:  # type: ignore[override]
            time.sleep(0.03)
            return self.values[blob_hash][start:end]

    created = 0
    client = object()

    def factory() -> object:
        nonlocal created
        time.sleep(0.01)
        created += 1
        return client

    fs = IrohAsyncFileSystem(
        manifest_store=manifests,
        blob_store=BlockingBlobs({"value.bin": payload}),
        client_factory=factory,
        read_ahead_size=8,
        range_cache_size=0,
    )
    heartbeat = False

    async def read() -> None:
        assert await fs._cat_file(url("value.bin"), 0, 8) == payload[:8]

    async def tick() -> None:
        nonlocal heartbeat
        await anyio.sleep(0.005)
        heartbeat = True

    async with anyio.create_task_group() as group:
        group.start_soon(read)
        group.start_soon(tick)
    assert heartbeat

    results: list[Any] = []

    async def get_client() -> None:
        results.append(await fs._runtime_client_async())

    async with anyio.create_task_group() as group:
        for _ in range(8):
            group.start_soon(get_client)
    assert results == [client] * 8
    assert created == 1


@pytest.mark.anyio
async def test_async_staged_write_commits_before_close_returns() -> None:
    manifests = ManifestStore({})
    blobs = BlobStore({})
    fs = IrohAsyncFileSystem(manifest_store=manifests, blob_store=blobs, block_size=8)

    async with await fs.open_async(url("new.bin"), "wb") as handle:
        assert await handle.write(b"new payload") == len(b"new payload")
        await handle.flush()
        assert manifests.cas_calls == 0

    assert manifests.cas_calls == 1
    assert await fs._cat_file(url("new.bin")) == b"new payload"


@pytest.mark.anyio(backend="trio")
async def test_async_adapter_runs_on_trio() -> None:
    payload = b"trio"
    fs = IrohAsyncFileSystem(
        manifest_store=ManifestStore({"value.bin": payload}),
        blob_store=BlobStore({"value.bin": payload}),
    )
    assert await fs._cat_file(url("value.bin")) == payload
