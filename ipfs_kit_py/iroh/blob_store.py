"""Verified streaming primitives for the managed Iroh blob store.

The sidecar owns the durable Iroh store and peer transport.  This module owns
the Python-facing safety properties around that boundary: native hash
validation, bounded RPC frames, streaming disk I/O, resumable reads, and
atomic destination replacement.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import inspect
import math
import os
import re
import tempfile
from collections.abc import AsyncIterable, Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol, runtime_checkable

from .errors import (
    IrohAlreadyExistsError,
    IrohCancelledError,
    IrohIOError,
    IrohIntegrityError,
    IrohInvalidHashError,
    IrohNotFoundError,
    IrohProtocolError,
    IrohUnavailableError,
)

DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_RESUME_ATTEMPTS = 3
MIN_CHUNK_SIZE = 4 * 1024
MAX_CHUNK_SIZE = 8 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 60 * 60

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


@runtime_checkable
class BlobRuntimeClient(Protocol):
    """The small runtime-client surface consumed by :class:`IrohBlobStore`."""

    async def request(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class BlobInfo:
    """Verified public metadata for one immutable Iroh blob."""

    blob_hash: str
    size: int
    complete: bool = True

    @property
    def hash(self) -> str:
        """Compatibility spelling used by lower-level Iroh APIs."""

        return self.blob_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "blob_hash": self.blob_hash,
            "size": self.size,
            "complete": self.complete,
        }


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Receipt for a local ingest or remote import."""

    blob_hash: str
    size: int
    deduplicated: bool = False
    resumed: bool = False

    @property
    def hash(self) -> str:
        return self.blob_hash

    @property
    def already_present(self) -> bool:
        return self.deduplicated

    def to_dict(self) -> dict[str, Any]:
        return {
            "blob_hash": self.blob_hash,
            "size": self.size,
            "deduplicated": self.deduplicated,
            "resumed": self.resumed,
        }


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Receipt for an atomically completed blob export."""

    blob_hash: str
    size: int
    destination: Path
    resumed: bool = False

    @property
    def hash(self) -> str:
        return self.blob_hash

    @property
    def path(self) -> Path:
        return self.destination

    def to_dict(self) -> dict[str, Any]:
        return {
            "blob_hash": self.blob_hash,
            "size": self.size,
            "destination": os.fspath(self.destination),
            "resumed": self.resumed,
        }


@dataclass(frozen=True, slots=True)
class TransferProgress:
    """Secret-free progress snapshot delivered at chunk boundaries."""

    operation: str
    completed: int
    total: int | None
    blob_hash: str | None = None
    resumed: bool = False


ProgressCallback = Callable[[TransferProgress], Awaitable[None] | None]
CancellationCheck = asyncio.Event | Callable[[], bool | Awaitable[bool]]
BlobSource = str | os.PathLike[str] | BinaryIO | AsyncIterable[bytes]


class IrohBlobStore:
    """High-level, integrity-checked access to protocol-1 blob RPC methods.

    ``client`` is normally :class:`~ipfs_kit_py.iroh.client.IrohRuntimeClient`,
    but the structural interface deliberately keeps this layer straightforward
    to test and usable with supervised-client wrappers.
    """

    def __init__(
        self,
        client: BlobRuntimeClient,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        resume_attempts: int = DEFAULT_RESUME_ATTEMPTS,
        staging_directory: str | os.PathLike[str] | None = None,
        timeout: float | None = None,
    ) -> None:
        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
            raise ValueError("chunk_size must be an integer")
        if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
            raise ValueError(f"chunk_size must be between {MIN_CHUNK_SIZE} and {MAX_CHUNK_SIZE}")
        if (
            not isinstance(resume_attempts, int)
            or isinstance(resume_attempts, bool)
            or resume_attempts < 0
        ):
            raise ValueError("resume_attempts must be a non-negative integer")
        if timeout is not None:
            timeout = _validate_timeout(timeout)

        self.client = client
        self.chunk_size = chunk_size
        self.resume_attempts = resume_attempts
        self.staging_directory = None if staging_directory is None else Path(staging_directory)
        self.timeout = timeout

    async def stat(self, blob_hash: str, *, timeout: float | None = None) -> BlobInfo:
        """Return validated blob metadata from the sidecar."""

        digest = validate_blob_hash(blob_hash)
        value = await self._request("blobs.stat", {"hash": digest}, timeout=timeout)
        return _parse_blob_info(value, expected_hash=digest, operation="blobs.stat")

    async def ingest(
        self,
        source: BlobSource,
        *,
        expected_hash: str | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancellationCheck | None = None,
        cancellation_event: CancellationCheck | None = None,
        timeout: float | None = None,
    ) -> IngestResult:
        """Stream a file or byte stream into the local immutable blob store.

        File paths are hashed in bounded chunks and passed directly to the
        supervised local sidecar.  File-like and async iterable inputs are
        first copied to a private, mode-0600 staging file so they never need to
        be held fully in memory.  Every ingest supplies an expected hash to the
        sidecar, closing the path mutation race between local hashing and RPC.
        """

        cancellation = _coalesce_cancellation(cancel, cancellation_event)
        wanted = None if expected_hash is None else validate_blob_hash(expected_hash)
        staging_path: Path | None = None
        try:
            await _check_cancelled(cancellation, "blobs.ingest")
            if isinstance(source, (str, os.PathLike)):
                source_path = Path(source)
                digest, size = await self._hash_path(
                    source_path,
                    progress=progress,
                    cancellation=cancellation,
                    operation="ingest",
                )
            else:
                staging_path, digest, size = await self._stage_source(
                    source,
                    progress=progress,
                    cancellation=cancellation,
                )
                source_path = staging_path

            if wanted is not None and digest != wanted:
                raise IrohIntegrityError(
                    "source does not match the expected Iroh blob hash",
                    operation="blobs.ingest",
                )

            await _check_cancelled(cancellation, "blobs.ingest")
            existing = await self._stat_if_present(digest, timeout=timeout)
            if existing is not None:
                if not existing.complete or existing.size != size:
                    raise IrohIntegrityError(
                        "existing Iroh blob metadata does not match the source",
                        operation="blobs.ingest",
                    )
                await _report_progress(
                    progress,
                    TransferProgress("ingest", size, size, digest),
                )
                return IngestResult(digest, size, deduplicated=True)

            value = await self._request(
                "blobs.ingest",
                {
                    "source_path": os.fspath(source_path.absolute()),
                    "expected_hash": digest,
                    "size": size,
                },
                timeout=timeout,
            )
            result = _parse_ingest_result(
                value,
                expected_hash=digest,
                expected_size=size,
                operation="blobs.ingest",
            )
            await _check_cancelled(cancellation, "blobs.ingest")
            await _report_progress(
                progress,
                TransferProgress("ingest", size, size, digest),
            )
            return result
        except asyncio.CancelledError:
            raise IrohCancelledError(
                "Iroh blob ingest was cancelled", operation="blobs.ingest"
            ) from None
        except OSError as exc:
            raise _io_error("Iroh blob staging failed", "blobs.ingest", exc) from None
        finally:
            if staging_path is not None:
                await _unlink(staging_path)

    async def fetch(
        self,
        blob_hash: str,
        *,
        provider: str | None = None,
        ticket: str | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancellationCheck | None = None,
        cancellation_event: CancellationCheck | None = None,
        timeout: float | None = None,
    ) -> IngestResult:
        """Ensure a blob is local, importing it from a provider or read ticket.

        Provider and ticket values are sent only in the protected RPC payload.
        They are intentionally absent from receipts, progress, and errors.
        When a transient disconnect reports a safe byte offset, the next
        request asks the sidecar to resume from that offset.
        """

        digest = validate_blob_hash(blob_hash)
        _validate_remote_source(provider, ticket)
        cancellation = _coalesce_cancellation(cancel, cancellation_event)
        await _check_cancelled(cancellation, "blobs.ingest")

        existing = await self._stat_if_present(digest, timeout=timeout)
        if existing is not None and existing.complete:
            await _report_progress(
                progress,
                TransferProgress("fetch", existing.size, existing.size, digest),
            )
            return IngestResult(digest, existing.size, deduplicated=True)

        params: dict[str, Any] = {"expected_hash": digest}
        if provider is not None:
            params["provider"] = provider
        if ticket is not None:
            params["ticket"] = ticket

        resumed = False
        attempts = 0
        while True:
            await _check_cancelled(cancellation, "blobs.ingest")
            try:
                value = await self._request("blobs.ingest", params, timeout=timeout)
                break
            except IrohUnavailableError as exc:
                offset = _safe_resume_offset(exc.metadata.get("offset"))
                if attempts >= self.resume_attempts:
                    raise
                attempts += 1
                if offset is not None:
                    resumed = True
                    params["resume_offset"] = offset
                    await _report_progress(
                        progress,
                        TransferProgress("fetch", offset, None, digest, True),
                    )

        result = _parse_ingest_result(
            value,
            expected_hash=digest,
            expected_size=None,
            operation="blobs.ingest",
        )
        info = await self.stat(digest, timeout=timeout)
        if not info.complete or info.size != result.size:
            raise IrohIntegrityError(
                "imported Iroh blob is incomplete or has the wrong size",
                operation="blobs.ingest",
            )
        await _check_cancelled(cancellation, "blobs.ingest")
        await _report_progress(
            progress,
            TransferProgress("fetch", info.size, info.size, digest, resumed),
        )
        return IngestResult(
            digest,
            info.size,
            deduplicated=result.deduplicated,
            resumed=resumed or result.resumed,
        )

    async def import_ticket(
        self,
        ticket: str,
        *,
        expected_hash: str,
        progress: ProgressCallback | None = None,
        cancel: CancellationCheck | None = None,
        cancellation_event: CancellationCheck | None = None,
        timeout: float | None = None,
    ) -> IngestResult:
        """Convenience wrapper for a verified read-ticket import."""

        return await self.fetch(
            expected_hash,
            ticket=ticket,
            progress=progress,
            cancel=cancel,
            cancellation_event=cancellation_event,
            timeout=timeout,
        )

    async def read_range(
        self,
        blob_hash: str,
        offset: int = 0,
        length: int | None = None,
        *,
        start: int | None = None,
        end: int | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancellationCheck | None = None,
        cancellation_event: CancellationCheck | None = None,
        timeout: float | None = None,
    ) -> bytes:
        """Read a verified half-open range, resuming transient disconnects.

        ``offset``/``length`` is the native spelling.  ``start``/``end`` is
        accepted for callers that naturally express the half-open interval.
        Negative boundaries are resolved relative to the verified blob size.
        """

        digest = validate_blob_hash(blob_hash)
        cancellation = _coalesce_cancellation(cancel, cancellation_event)
        await _check_cancelled(cancellation, "blobs.read_range")
        info = await self.stat(digest, timeout=timeout)
        _require_complete_blob(info, "blobs.read_range")
        begin, stop = _normalize_range(
            info.size, offset=offset, length=length, start=start, end=end
        )
        total = stop - begin
        if total == 0:
            return b""

        output = bytearray()
        current = begin
        resumed = False
        while current < stop:
            await _check_cancelled(cancellation, "blobs.read_range")
            requested = min(self.chunk_size, stop - current)
            chunk, did_resume = await self._read_chunk_with_resume(
                digest,
                current,
                requested,
                cancellation=cancellation,
                timeout=timeout,
            )
            resumed = resumed or did_resume
            output.extend(chunk)
            current += len(chunk)
            await _report_progress(
                progress,
                TransferProgress("read_range", current - begin, total, digest, resumed),
            )

        result = bytes(output)
        if begin == 0 and stop == info.size and _hash_bytes(result) != digest:
            raise IrohIntegrityError(
                "Iroh sidecar returned corrupt blob content",
                operation="blobs.read_range",
            )
        return result

    async def export(
        self,
        blob_hash: str,
        destination: str | os.PathLike[str],
        *,
        overwrite: bool = True,
        mode: int = 0o600,
        progress: ProgressCallback | None = None,
        cancel: CancellationCheck | None = None,
        cancellation_event: CancellationCheck | None = None,
        timeout: float | None = None,
    ) -> ExportResult:
        """Stream a blob to a same-directory temp file and atomically replace.

        The destination is never opened until the complete byte count and
        BLAKE3 digest have been verified.  Cancellation, corruption, disk-full,
        and sidecar failures remove the private temporary file.
        """

        digest = validate_blob_hash(blob_hash)
        target = Path(destination)
        _validate_export_mode(mode)
        cancellation = _coalesce_cancellation(cancel, cancellation_event)
        await _check_cancelled(cancellation, "blobs.export")
        info = await self.stat(digest, timeout=timeout)
        _require_complete_blob(info, "blobs.export")

        if not overwrite and await asyncio.to_thread(target.exists):
            raise IrohAlreadyExistsError(
                "blob export destination already exists", operation="blobs.export"
            )

        temporary: Path | None = None
        handle: BinaryIO | None = None
        resumed = False
        try:
            temporary, handle = await asyncio.to_thread(_open_atomic_temporary, target, mode)
            hasher = _new_hasher()
            completed = 0
            while completed < info.size:
                await _check_cancelled(cancellation, "blobs.export")
                requested = min(self.chunk_size, info.size - completed)
                chunk, did_resume = await self._read_chunk_with_resume(
                    digest,
                    completed,
                    requested,
                    cancellation=cancellation,
                    timeout=timeout,
                )
                resumed = resumed or did_resume
                await asyncio.to_thread(_write_all, handle, chunk)
                hasher.update(chunk)
                completed += len(chunk)
                await _report_progress(
                    progress,
                    TransferProgress("export", completed, info.size, digest, resumed),
                )

            if completed != info.size or hasher.hexdigest() != digest:
                raise IrohIntegrityError(
                    "Iroh sidecar returned corrupt blob content",
                    operation="blobs.export",
                )
            if info.size == 0:
                await _report_progress(
                    progress,
                    TransferProgress("export", 0, 0, digest, resumed),
                )
            await _check_cancelled(cancellation, "blobs.export")
            await asyncio.to_thread(
                _commit_atomic_temporary,
                handle,
                temporary,
                target,
                overwrite=overwrite,
            )
            handle = None
            temporary = None
            return ExportResult(digest, info.size, target, resumed=resumed)
        except asyncio.CancelledError:
            raise IrohCancelledError(
                "Iroh blob export was cancelled", operation="blobs.export"
            ) from None
        except FileExistsError:
            if not overwrite:
                raise IrohAlreadyExistsError(
                    "blob export destination already exists",
                    operation="blobs.export",
                ) from None
            raise
        except OSError as exc:
            raise _io_error("Iroh blob export failed", "blobs.export", exc) from None
        finally:
            if handle is not None:
                await asyncio.to_thread(_close_quietly, handle)
            if temporary is not None:
                await _unlink(temporary)

    async def _hash_path(
        self,
        path: Path,
        *,
        progress: ProgressCallback | None,
        cancellation: CancellationCheck | None,
        operation: str,
    ) -> tuple[str, int]:
        try:
            if not await asyncio.to_thread(path.is_file):
                raise IrohIOError("blob source is not a regular file", operation="blobs.ingest")
            total = (await asyncio.to_thread(path.stat)).st_size
            handle = await asyncio.to_thread(path.open, "rb")
            try:
                hasher = _new_hasher()
                completed = 0
                while True:
                    await _check_cancelled(cancellation, "blobs.ingest")
                    chunk = await asyncio.to_thread(handle.read, self.chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    completed += len(chunk)
                    await _report_progress(
                        progress,
                        TransferProgress(operation, completed, total),
                    )
                return hasher.hexdigest(), completed
            finally:
                await asyncio.to_thread(_close_quietly, handle)
        except asyncio.CancelledError:
            raise
        except IrohIOError:
            raise
        except OSError as exc:
            raise _io_error("could not read blob source", "blobs.ingest", exc) from None

    async def _stage_source(
        self,
        source: BinaryIO | AsyncIterable[bytes],
        *,
        progress: ProgressCallback | None,
        cancellation: CancellationCheck | None,
    ) -> tuple[Path, str, int]:
        path, handle = await asyncio.to_thread(_open_staging_temporary, self.staging_directory)
        hasher = _new_hasher()
        completed = 0
        try:
            async for chunk in _iter_source(source, self.chunk_size):
                await _check_cancelled(cancellation, "blobs.ingest")
                if not isinstance(chunk, bytes):
                    chunk = bytes(chunk)
                if not chunk:
                    continue
                await asyncio.to_thread(_write_all, handle, chunk)
                hasher.update(chunk)
                completed += len(chunk)
                await _report_progress(
                    progress,
                    TransferProgress("ingest", completed, None),
                )
            await asyncio.to_thread(_finish_staging, handle)
            return path, hasher.hexdigest(), completed
        except BaseException:
            await asyncio.to_thread(_close_quietly, handle)
            await _unlink(path)
            raise

    async def _stat_if_present(self, blob_hash: str, *, timeout: float | None) -> BlobInfo | None:
        try:
            return await self.stat(blob_hash, timeout=timeout)
        except IrohNotFoundError:
            return None

    async def _read_chunk_with_resume(
        self,
        blob_hash: str,
        offset: int,
        length: int,
        *,
        cancellation: CancellationCheck | None,
        timeout: float | None,
    ) -> tuple[bytes, bool]:
        attempts = 0
        while True:
            await _check_cancelled(cancellation, "blobs.read_range")
            try:
                value = await self._request(
                    "blobs.read_range",
                    {"hash": blob_hash, "offset": offset, "length": length},
                    timeout=timeout,
                )
                return (
                    _parse_range_result(
                        value,
                        expected_hash=blob_hash,
                        expected_offset=offset,
                        expected_length=length,
                    ),
                    attempts > 0,
                )
            except IrohUnavailableError:
                if attempts >= self.resume_attempts:
                    raise
                attempts += 1

    async def _request(
        self,
        method: str,
        params: Mapping[str, Any],
        *,
        timeout: float | None,
    ) -> Any:
        deadline = self.timeout if timeout is None else _validate_timeout(timeout)
        return await self.client.request(method, params, timeout=deadline)


async def _iter_source(
    source: BinaryIO | AsyncIterable[bytes], chunk_size: int
) -> AsyncIterable[bytes]:
    if hasattr(source, "__aiter__"):
        async for chunk in source:  # type: ignore[union-attr]
            if not isinstance(chunk, (bytes, bytearray, memoryview)):
                raise TypeError("async blob source must yield bytes")
            yield bytes(chunk)
        return

    read = getattr(source, "read", None)
    if not callable(read):
        raise TypeError("blob source must be a path, binary stream, or async iterable")
    while True:
        value = await asyncio.to_thread(read, chunk_size)
        if inspect.isawaitable(value):
            value = await value
        if not value:
            break
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError("binary blob source read() must return bytes")
        yield bytes(value)


def validate_blob_hash(value: str) -> str:
    """Validate and return a canonical native Iroh BLAKE3-256 hash."""

    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise IrohInvalidHashError(
            "Iroh blob hash must be exactly 64 lowercase hexadecimal characters",
            operation="blobs.validate_hash",
        )
    return value


def _parse_blob_info(value: Any, *, expected_hash: str, operation: str) -> BlobInfo:
    obj = _mapping(value, operation)
    digest = obj.get("hash", obj.get("blob_hash"))
    size = obj.get("size")
    complete = obj.get("complete", True)
    if digest != expected_hash:
        raise IrohIntegrityError(
            "Iroh sidecar returned metadata for a different blob",
            operation=operation,
        )
    if not _valid_size(size) or not isinstance(complete, bool):
        raise IrohProtocolError("Iroh sidecar returned invalid blob metadata", operation=operation)
    return BlobInfo(digest, size, complete)


def _parse_ingest_result(
    value: Any,
    *,
    expected_hash: str,
    expected_size: int | None,
    operation: str,
) -> IngestResult:
    obj = _mapping(value, operation)
    digest = obj.get("hash", obj.get("blob_hash"))
    size = obj.get("size")
    deduplicated = obj.get("deduplicated", obj.get("already_present", False))
    resumed = obj.get("resumed", False)
    if digest != expected_hash or (expected_size is not None and size != expected_size):
        raise IrohIntegrityError(
            "Iroh sidecar ingest receipt does not match the expected blob",
            operation=operation,
        )
    if not _valid_size(size) or not isinstance(deduplicated, bool) or not isinstance(resumed, bool):
        raise IrohProtocolError(
            "Iroh sidecar returned an invalid ingest receipt", operation=operation
        )
    return IngestResult(digest, size, deduplicated, resumed)


def _parse_range_result(
    value: Any,
    *,
    expected_hash: str,
    expected_offset: int,
    expected_length: int,
) -> bytes:
    obj = _mapping(value, "blobs.read_range")
    digest = obj.get("hash", obj.get("blob_hash"))
    offset = obj.get("offset")
    verified = obj.get("verified")
    encoded = obj.get("data")
    if (
        digest != expected_hash
        or not _valid_size(offset)
        or offset != expected_offset
        or verified is not True
    ):
        raise IrohIntegrityError(
            "Iroh sidecar returned an unverified or mismatched blob range",
            operation="blobs.read_range",
        )
    if isinstance(encoded, str):
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise IrohProtocolError(
                "Iroh sidecar returned invalid base64 blob data",
                operation="blobs.read_range",
            ) from None
    elif isinstance(encoded, (bytes, bytearray, memoryview)):
        # Binary is useful for in-process adapters; JSON adapters necessarily
        # use the canonical base64 string form.
        data = bytes(encoded)
    else:
        raise IrohProtocolError(
            "Iroh sidecar returned invalid blob range data",
            operation="blobs.read_range",
        )
    if len(data) != expected_length:
        raise IrohIntegrityError(
            "Iroh sidecar returned a truncated blob range",
            operation="blobs.read_range",
        )
    declared_length = obj.get("length")
    if not _valid_size(declared_length) or declared_length != len(data):
        raise IrohIntegrityError(
            "Iroh sidecar returned an inconsistent blob range length",
            operation="blobs.read_range",
        )
    return data


def _normalize_range(
    size: int,
    *,
    offset: int,
    length: int | None,
    start: int | None,
    end: int | None,
) -> tuple[int, int]:
    for name, value in (("offset", offset), ("length", length), ("start", start), ("end", end)):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise TypeError(f"{name} must be an integer or None")
    if start is not None or end is not None:
        if offset != 0 or length is not None:
            raise ValueError("use either offset/length or start/end range arguments")
        begin = 0 if start is None else start
        stop = size if end is None else end
    else:
        begin = offset
        if length is not None and length < 0:
            raise ValueError("length must be non-negative")
        stop = size if length is None else begin + length

    if begin < 0:
        begin += size
    if stop < 0:
        stop += size
    begin = min(max(begin, 0), size)
    stop = min(max(stop, 0), size)
    if stop <= begin:
        return begin, begin
    return begin, stop


def _mapping(value: Any, operation: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IrohProtocolError("Iroh sidecar result must be an object", operation=operation)
    return value


def _valid_size(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _require_complete_blob(info: BlobInfo, operation: str) -> None:
    if not info.complete:
        raise IrohIntegrityError(
            "Iroh blob is incomplete",
            operation=operation,
        )


def _validate_timeout(value: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
        or value > MAX_TIMEOUT_SECONDS
    ):
        raise ValueError(
            f"timeout must be finite, positive, and at most {MAX_TIMEOUT_SECONDS} seconds"
        )
    return float(value)


def _validate_remote_source(provider: str | None, ticket: str | None) -> None:
    if provider is not None and (not isinstance(provider, str) or not provider):
        raise ValueError("provider must be a non-empty string")
    if ticket is not None and (not isinstance(ticket, str) or not ticket):
        raise ValueError("ticket must be a non-empty string")
    if provider is not None and ticket is not None:
        raise ValueError("provide only one of provider or ticket")


def _validate_export_mode(mode: int) -> None:
    if not isinstance(mode, int) or isinstance(mode, bool) or mode < 0 or mode > 0o777:
        raise ValueError("mode must be an integer from 0o000 through 0o777")


def _coalesce_cancellation(
    first: CancellationCheck | None, second: CancellationCheck | None
) -> CancellationCheck | None:
    if first is not None and second is not None:
        raise ValueError("provide only one cancellation signal")
    return first if first is not None else second


async def _check_cancelled(cancellation: CancellationCheck | None, operation: str) -> None:
    if cancellation is None:
        return
    if isinstance(cancellation, asyncio.Event):
        cancelled = cancellation.is_set()
    elif callable(cancellation):
        cancelled = cancellation()
        if inspect.isawaitable(cancelled):
            cancelled = await cancelled
    else:
        raise TypeError("cancellation signal must be an asyncio.Event or callable")
    if cancelled:
        raise IrohCancelledError("Iroh blob operation was cancelled", operation=operation)


async def _report_progress(callback: ProgressCallback | None, event: TransferProgress) -> None:
    if callback is None:
        return
    result = callback(event)
    if inspect.isawaitable(result):
        await result


def _safe_resume_offset(value: Any) -> int | None:
    return value if _valid_size(value) else None


def _new_hasher() -> Any:
    try:
        import blake3
    except ImportError:
        raise IrohUnavailableError(
            "BLAKE3 support is required for verified Iroh blob operations",
            operation="blobs.hash",
        ) from None
    return blake3.blake3()


def _hash_bytes(value: bytes) -> str:
    hasher = _new_hasher()
    hasher.update(value)
    return hasher.hexdigest()


def _open_staging_temporary(
    directory: Path | None,
) -> tuple[Path, BinaryIO]:
    if directory is not None:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, name = tempfile.mkstemp(prefix=".iroh-ingest-", suffix=".tmp", dir=directory)
    os.chmod(descriptor, 0o600)
    return Path(name), os.fdopen(descriptor, "wb")


def _open_atomic_temporary(target: Path, mode: int) -> tuple[Path, BinaryIO]:
    parent = target.parent
    if not parent.exists() or not parent.is_dir():
        raise FileNotFoundError("blob export parent directory does not exist")
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.iroh-", suffix=".tmp", dir=parent)
    os.chmod(descriptor, mode)
    return Path(name), os.fdopen(descriptor, "wb")


def _write_all(handle: BinaryIO, data: bytes) -> None:
    view = memoryview(data)
    completed = 0
    while completed < len(view):
        written = handle.write(view[completed:])
        if not isinstance(written, int) or isinstance(written, bool) or written <= 0:
            raise OSError("short write while exporting Iroh blob")
        completed += written


def _finish_staging(handle: BinaryIO) -> None:
    handle.flush()
    os.fsync(handle.fileno())
    handle.close()


def _commit_atomic_temporary(
    handle: BinaryIO,
    temporary: Path,
    target: Path,
    *,
    overwrite: bool,
) -> None:
    _finish_staging(handle)
    if overwrite:
        os.replace(temporary, target)
    else:
        # A preflight exists() check is useful for avoiding a download, but it
        # cannot enforce exclusive creation.  A same-directory hard link is an
        # atomic no-replace publication on every supported desktop platform.
        # The temporary name is then removed while the destination keeps the
        # fully flushed inode alive.
        os.link(temporary, target)
        try:
            os.unlink(temporary)
        except OSError:
            # Publication has committed.  Leaving a private temporary hard
            # link is preferable to reporting that the destination was not
            # created; the caller/finally cleanup gets a second opportunity.
            pass
    # Persist the directory entry where the platform permits directory fsync.
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(target.parent, flags)
        os.fsync(descriptor)
    except OSError:
        # Some supported filesystems/platforms do not permit directory fsync;
        # the data file itself was still flushed before atomic replacement.
        pass
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _close_quietly(handle: BinaryIO) -> None:
    try:
        handle.close()
    except OSError:
        pass


async def _unlink(path: Path) -> None:
    try:
        await asyncio.to_thread(path.unlink, missing_ok=True)
    except OSError:
        # Cleanup is best effort and must not hide the primary typed failure.
        pass


def _io_error(message: str, operation: str, cause: OSError) -> IrohIOError:
    metadata: dict[str, Any] = {}
    if isinstance(cause.errno, int):
        metadata["errno"] = cause.errno
    return IrohIOError(message, operation=operation, metadata=metadata)


BlobStore = IrohBlobStore
BlobIngestResult = IngestResult
BlobExportResult = ExportResult


__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_RESUME_ATTEMPTS",
    "MIN_CHUNK_SIZE",
    "MAX_CHUNK_SIZE",
    "MAX_TIMEOUT_SECONDS",
    "BlobRuntimeClient",
    "BlobInfo",
    "IngestResult",
    "ExportResult",
    "TransferProgress",
    "ProgressCallback",
    "CancellationCheck",
    "IrohBlobStore",
    "BlobStore",
    "BlobIngestResult",
    "BlobExportResult",
    "validate_blob_hash",
]
