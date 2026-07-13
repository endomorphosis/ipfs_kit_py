"""Offline conformance tests for the IROH-010 blob primitives."""

from __future__ import annotations

import asyncio
import base64
import errno
import io
import math
from pathlib import Path
from typing import Any

import blake3
import pytest

from ipfs_kit_py.iroh.blob_store import IrohBlobStore, validate_blob_hash
from ipfs_kit_py.iroh.errors import (
    IrohAlreadyExistsError,
    IrohCancelledError,
    IrohIOError,
    IrohIntegrityError,
    IrohInvalidHashError,
    IrohNotFoundError,
    IrohUnavailableError,
)


def digest(data: bytes) -> str:
    return blake3.blake3(data).hexdigest()


class MemoryBlobClient:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.disconnect_once_at: int | None = None
        self.corrupt_ranges = False
        self.remote_payload: bytes | None = None

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        del timeout
        params = dict(params or {})
        self.calls.append((method, params))
        if method == "blobs.stat":
            blob_hash = params["hash"]
            if blob_hash not in self.blobs:
                raise IrohNotFoundError("not found", operation=method)
            return {"hash": blob_hash, "size": len(self.blobs[blob_hash]), "complete": True}

        if method == "blobs.ingest":
            expected = params["expected_hash"]
            if "source_path" in params:
                payload = Path(params["source_path"]).read_bytes()
            elif self.remote_payload is not None:
                payload = self.remote_payload
            else:
                raise IrohUnavailableError("no provider", operation=method)
            actual = digest(payload)
            if actual != expected:
                raise IrohIntegrityError("wrong hash", operation=method)
            already_present = actual in self.blobs
            self.blobs[actual] = payload
            return {
                "hash": actual,
                "size": len(payload),
                "already_present": already_present,
                "resumed": "resume_offset" in params,
            }

        if method == "blobs.read_range":
            offset = params["offset"]
            if self.disconnect_once_at == offset:
                self.disconnect_once_at = None
                raise IrohUnavailableError("disconnected", operation=method)
            payload = self.blobs[params["hash"]][offset : offset + params["length"]]
            if self.corrupt_ranges and payload:
                payload = bytes([payload[0] ^ 1]) + payload[1:]
            return {
                "hash": params["hash"],
                "offset": offset,
                "length": len(payload),
                "verified": True,
                "data": base64.b64encode(payload).decode("ascii"),
            }

        raise AssertionError(f"unexpected method: {method}")


@pytest.mark.parametrize(
    "value",
    ["f" * 63, "F" * 64, "0x" + "f" * 64, "g" * 64, b"f" * 64],
)
def test_hash_validation_is_native_and_strict(value: Any) -> None:
    with pytest.raises(IrohInvalidHashError):
        validate_blob_hash(value)


@pytest.mark.asyncio
async def test_ingest_streams_verifies_and_deduplicates(tmp_path: Path) -> None:
    payload = b"streamed content\x00" * 700
    source = tmp_path / "source.bin"
    source.write_bytes(payload)
    client = MemoryBlobClient()
    progress = []
    store = IrohBlobStore(client, chunk_size=4096)

    result = await store.ingest(source, expected_hash=digest(payload), progress=progress.append)
    duplicate = await store.ingest(source)

    assert (result.blob_hash, result.size, result.deduplicated) == (
        digest(payload),
        len(payload),
        False,
    )
    assert duplicate.deduplicated is True
    assert client.blobs[result.blob_hash] == payload
    assert [method for method, _ in client.calls].count("blobs.ingest") == 1
    assert progress[-1].completed == len(payload)


@pytest.mark.asyncio
async def test_ingest_stream_uses_private_staging_and_cleans_it(tmp_path: Path) -> None:
    client = MemoryBlobClient()
    staging = tmp_path / "stage"
    store = IrohBlobStore(client, chunk_size=4096, staging_directory=staging)
    payload = b"from a binary stream"

    result = await store.ingest(io.BytesIO(payload))

    assert client.blobs[result.blob_hash] == payload
    assert list(staging.iterdir()) == []


@pytest.mark.asyncio
async def test_ingest_rejects_corrupt_expected_payload_before_rpc(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"actual")
    client = MemoryBlobClient()
    store = IrohBlobStore(client, chunk_size=4096)

    with pytest.raises(IrohIntegrityError):
        await store.ingest(source, expected_hash=digest(b"expected"))

    assert all(method != "blobs.ingest" for method, _ in client.calls)


@pytest.mark.asyncio
async def test_range_read_clamps_boundaries_and_resumes_disconnect() -> None:
    payload = bytes(range(256)) * 40
    blob_hash = digest(payload)
    client = MemoryBlobClient()
    client.blobs[blob_hash] = payload
    client.disconnect_once_at = 0
    store = IrohBlobStore(client, chunk_size=4096, resume_attempts=1)

    result = await store.read_range(blob_hash, start=-5000, end=None)

    assert result == payload[-5000:]
    zero_offset_calls = [
        params
        for method, params in client.calls
        if method == "blobs.read_range" and params["offset"] == len(payload) - 5000
    ]
    # The injected disconnect targets zero, so this negative range does not retry.
    assert len(zero_offset_calls) == 1

    client.disconnect_once_at = 0
    assert await store.read_range(blob_hash) == payload
    assert len([m for m, _ in client.calls if m == "blobs.read_range"]) >= 4


@pytest.mark.asyncio
async def test_full_range_and_export_reject_corruption(tmp_path: Path) -> None:
    payload = b"verified payload" * 1000
    blob_hash = digest(payload)
    client = MemoryBlobClient()
    client.blobs[blob_hash] = payload
    client.corrupt_ranges = True
    store = IrohBlobStore(client, chunk_size=4096)
    destination = tmp_path / "out"
    destination.write_bytes(b"previous")

    with pytest.raises(IrohIntegrityError):
        await store.read_range(blob_hash)
    with pytest.raises(IrohIntegrityError):
        await store.export(blob_hash, destination)

    assert destination.read_bytes() == b"previous"
    assert list(tmp_path.glob(".out.iroh-*.tmp")) == []


@pytest.mark.asyncio
async def test_export_is_atomic_and_resumes_range_disconnect(tmp_path: Path) -> None:
    payload = b"a" * 9000
    blob_hash = digest(payload)
    client = MemoryBlobClient()
    client.blobs[blob_hash] = payload
    client.disconnect_once_at = 4096
    store = IrohBlobStore(client, chunk_size=4096, resume_attempts=2)
    destination = tmp_path / "export.bin"
    destination.write_bytes(b"old")

    result = await store.export(blob_hash, destination)

    assert destination.read_bytes() == payload
    assert result.resumed is True
    assert result.destination == destination
    assert list(tmp_path.glob(".export.bin.iroh-*.tmp")) == []


@pytest.mark.asyncio
async def test_disk_full_keeps_destination_and_removes_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"content" * 1000
    blob_hash = digest(payload)
    client = MemoryBlobClient()
    client.blobs[blob_hash] = payload
    store = IrohBlobStore(client, chunk_size=4096)
    destination = tmp_path / "export.bin"
    destination.write_bytes(b"old")

    def fail_write(_handle: Any, _data: bytes) -> None:
        raise OSError(errno.ENOSPC, "secret path must not leak")

    monkeypatch.setattr("ipfs_kit_py.iroh.blob_store._write_all", fail_write)
    with pytest.raises(IrohIOError) as caught:
        await store.export(blob_hash, destination)

    assert caught.value.metadata == {"errno": errno.ENOSPC}
    assert "secret" not in str(caught.value)
    assert destination.read_bytes() == b"old"
    assert list(tmp_path.glob(".export.bin.iroh-*.tmp")) == []


@pytest.mark.asyncio
async def test_cancellation_removes_partial_and_preserves_destination(tmp_path: Path) -> None:
    payload = b"content" * 2000
    blob_hash = digest(payload)
    client = MemoryBlobClient()
    client.blobs[blob_hash] = payload
    store = IrohBlobStore(client, chunk_size=4096)
    destination = tmp_path / "export.bin"
    destination.write_bytes(b"old")
    cancelled = asyncio.Event()

    def on_progress(event: Any) -> None:
        if event.completed >= 4096:
            cancelled.set()

    with pytest.raises(IrohCancelledError):
        await store.export(
            blob_hash,
            destination,
            progress=on_progress,
            cancellation_event=cancelled,
        )

    assert destination.read_bytes() == b"old"
    assert list(tmp_path.glob(".export.bin.iroh-*.tmp")) == []


@pytest.mark.asyncio
async def test_ticket_import_is_verified_deduplicated_and_not_in_receipt() -> None:
    payload = b"remote"
    blob_hash = digest(payload)
    ticket = "raw-secret-ticket-material"
    client = MemoryBlobClient()
    client.remote_payload = payload
    store = IrohBlobStore(client, chunk_size=4096)

    result = await store.import_ticket(ticket, expected_hash=blob_hash)
    duplicate = await store.import_ticket(ticket, expected_hash=blob_hash)

    assert result.blob_hash == blob_hash
    assert ticket not in repr(result)
    assert duplicate.deduplicated is True
    ingest_params = next(params for method, params in client.calls if method == "blobs.ingest")
    assert ingest_params["ticket"] == ticket


@pytest.mark.asyncio
async def test_exhausted_resume_attempts_propagate_typed_unavailable() -> None:
    payload = b"payload"
    blob_hash = digest(payload)
    client = MemoryBlobClient()
    client.blobs[blob_hash] = payload
    client.disconnect_once_at = 0
    store = IrohBlobStore(client, chunk_size=4096, resume_attempts=0)

    with pytest.raises(IrohUnavailableError):
        await store.read_range(blob_hash)


@pytest.mark.parametrize("timeout", [0, -1, math.inf, -math.inf, math.nan, True, 3601])
def test_timeout_must_be_finite_positive_and_bounded(timeout: Any) -> None:
    with pytest.raises(ValueError):
        IrohBlobStore(MemoryBlobClient(), timeout=timeout)


@pytest.mark.asyncio
async def test_incomplete_blob_cannot_be_read_or_exported(tmp_path: Path) -> None:
    payload = b"partial"
    blob_hash = digest(payload)

    class IncompleteClient(MemoryBlobClient):
        async def request(
            self,
            method: str,
            params: dict[str, Any] | None = None,
            *,
            timeout: float | None = None,
        ) -> Any:
            if method == "blobs.stat":
                return {"hash": blob_hash, "size": len(payload), "complete": False}
            return await super().request(method, params, timeout=timeout)

    store = IrohBlobStore(IncompleteClient(), chunk_size=4096)
    with pytest.raises(IrohIntegrityError):
        await store.read_range(blob_hash)
    with pytest.raises(IrohIntegrityError):
        await store.export(blob_hash, tmp_path / "output")


@pytest.mark.asyncio
async def test_range_receipt_requires_explicit_verification_fields() -> None:
    payload = b"payload"
    blob_hash = digest(payload)

    class MissingVerificationClient(MemoryBlobClient):
        async def request(
            self,
            method: str,
            params: dict[str, Any] | None = None,
            *,
            timeout: float | None = None,
        ) -> Any:
            result = await super().request(method, params, timeout=timeout)
            if method == "blobs.read_range":
                result.pop("verified")
            return result

    client = MissingVerificationClient()
    client.blobs[blob_hash] = payload
    store = IrohBlobStore(client, chunk_size=4096)
    with pytest.raises(IrohIntegrityError):
        await store.read_range(blob_hash)


@pytest.mark.asyncio
async def test_export_no_overwrite_is_race_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"new payload"
    blob_hash = digest(payload)
    client = MemoryBlobClient()
    client.blobs[blob_hash] = payload
    store = IrohBlobStore(client, chunk_size=4096)
    destination = tmp_path / "output"
    original_commit = __import__(
        "ipfs_kit_py.iroh.blob_store", fromlist=["_commit_atomic_temporary"]
    )._commit_atomic_temporary

    def race_commit(handle: Any, temporary: Path, target: Path, *, overwrite: bool) -> None:
        target.write_bytes(b"racing writer")
        original_commit(handle, temporary, target, overwrite=overwrite)

    monkeypatch.setattr("ipfs_kit_py.iroh.blob_store._commit_atomic_temporary", race_commit)
    with pytest.raises(IrohAlreadyExistsError):
        await store.export(blob_hash, destination, overwrite=False)
    assert destination.read_bytes() == b"racing writer"
