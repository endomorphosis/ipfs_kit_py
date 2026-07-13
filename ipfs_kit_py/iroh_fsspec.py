"""Fsspec registration and file-handle foundation for Iroh storage.

``iroh://`` exposes mutable namespace manifests while ``iroh+blob://`` exposes
immutable BLAKE3-addressed blobs.  Both protocols intentionally resolve to one
filesystem class: fsspec's URL machinery supplies the protocol hint that lets
an instance distinguish a bare namespace identifier from a bare blob hash.

Importing this module is side-effect free with respect to the managed Iroh
service.  Registry updates are in-process metadata only; runtime clients and
storage adapters are accepted through dependency injection and are never
created or started merely by importing or constructing the filesystem.
"""

from __future__ import annotations

import io
import inspect
import asyncio
import glob as globlib
import json
import math
import os
import re
import tempfile
import threading
import unicodedata
from collections import OrderedDict, defaultdict, deque
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, Callable, ClassVar, Mapping
from urllib.parse import unquote_to_bytes, urlsplit

try:  # Prefer the user's fsspec installation when the optional extra exists.
    import fsspec as _fsspec
    from fsspec.spec import AbstractBufferedFile, AbstractFileSystem

    USING_VENDORED_FSSPEC = False
except (ImportError, ModuleNotFoundError):  # pragma: no cover - exercised in isolation tests
    from ipfs_kit_py._vendor import fsspec as _fsspec
    from ipfs_kit_py._vendor.fsspec.spec import AbstractBufferedFile, AbstractFileSystem

    USING_VENDORED_FSSPEC = True

from .iroh.errors import (
    IrohAlreadyExistsError,
    IrohConflictError,
    IrohError,
    IrohIOError,
    IrohInvalidHashError,
    IrohInvalidManifestError,
    IrohInvalidPathError,
    IrohInvalidURLError,
    IrohIntegrityError,
    IrohIsDirectoryError,
    IrohNotDirectoryError,
    IrohNotEmptyError,
    IrohNotFoundError,
    IrohPermissionDeniedError,
    IrohUnavailableError,
    IrohUnsupportedOperationError,
)

IROH_PROTOCOL = "iroh"
IROH_BLOB_PROTOCOL = "iroh+blob"
IROH_PROTOCOLS = (IROH_PROTOCOL, IROH_BLOB_PROTOCOL)
DEFAULT_BLOCK_SIZE = 1024 * 1024
DEFAULT_MAX_CONCURRENCY = 8
DEFAULT_MAX_PENDING_OPERATIONS = 64
DEFAULT_RANGE_CACHE_SIZE = 16 * DEFAULT_BLOCK_SIZE
DEFAULT_MULTIPART_THRESHOLD = 8 * DEFAULT_BLOCK_SIZE
DEFAULT_MULTIPART_PART_SIZE = 4 * DEFAULT_BLOCK_SIZE

_HEX_32 = re.compile(r"^[0-9a-f]{64}$")
_BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_ENCODED_SEPARATOR_OR_CONTROL = re.compile(r"%(?:2[fF]|5[cC]|0[0-9A-Fa-f]|1[0-9A-Fa-f]|7[fF])")


@dataclass(frozen=True, slots=True)
class IrohPath:
    """A validated, credential-free Iroh filesystem address."""

    protocol: str
    namespace_id: str | None = None
    path: str = ""
    blob_hash: str | None = None

    def __post_init__(self) -> None:
        selected = _validate_protocol(self.protocol)
        object.__setattr__(self, "protocol", selected)
        if selected == IROH_BLOB_PROTOCOL:
            if self.namespace_id is not None or self.path:
                raise IrohInvalidURLError(
                    "immutable blob addresses cannot contain a namespace path",
                    operation="filesystem.parse_url",
                )
            object.__setattr__(self, "blob_hash", _validate_hash(self.blob_hash))
            return
        if self.blob_hash is not None:
            raise IrohInvalidURLError(
                "namespace addresses cannot contain a blob hash",
                operation="filesystem.parse_url",
            )
        object.__setattr__(self, "namespace_id", _validate_namespace(self.namespace_id))
        object.__setattr__(self, "path", _validate_manifest_path(self.path))

    @property
    def is_blob(self) -> bool:
        return self.protocol == IROH_BLOB_PROTOCOL

    @property
    def canonical_url(self) -> str:
        if self.is_blob:
            return f"{IROH_BLOB_PROTOCOL}://{self.blob_hash}"
        suffix = "" if not self.path else _quote_path(self.path)
        return f"{IROH_PROTOCOL}://{self.namespace_id}/{suffix}"

    @property
    def stripped_path(self) -> str:
        if self.is_blob:
            return str(self.blob_hash)
        return str(self.namespace_id) + (f"/{self.path}" if self.path else "")


@dataclass(frozen=True, slots=True)
class _ManifestView:
    """One validated-enough, immutable view of a manifest head."""

    namespace_id: str
    revision: int | None
    entries: Mapping[str, Mapping[str, Any]]

    def entry(self, path: str) -> Mapping[str, Any]:
        try:
            return self.entries[path]
        except KeyError:
            raise IrohNotFoundError(
                "Iroh namespace path was not found",
                operation="filesystem.lookup",
            ) from None


@dataclass(frozen=True, slots=True)
class _ManifestSnapshot:
    """A mutable-operation snapshot and its compare-and-swap token."""

    view: _ManifestView
    manifest: Mapping[str, Any]
    head: str


@dataclass(slots=True)
class _Mutation:
    """One prevalidated operation waiting for a single manifest commit."""

    kind: str
    namespace_id: str
    path: str
    destination: str | None = None
    source: Any = None
    overwrite: bool = True
    recursive: bool = False
    create_parents: bool = False
    exist_ok: bool = False
    mode: int | None = None
    metadata: Mapping[str, Any] | None = None
    expected: _ManifestSnapshot | None = None


class _RangeCache:
    """A small, thread-safe LRU for verified immutable blob ranges.

    Cache keys include the content hash, so namespace head changes cannot make
    a cached range stale.  Entries larger than the configured byte budget are
    deliberately not retained.  The cache owns immutable ``bytes`` values and
    therefore never exposes partially filled buffers to concurrent readers.
    """

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self._values: OrderedDict[tuple[str, int, int], bytes] = OrderedDict()
        self._bytes = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._lock = threading.RLock()

    def get(self, key: tuple[str, int, int]) -> bytes | None:
        with self._lock:
            value = self._values.get(key)
            if value is None:
                self._misses += 1
                return None
            self._values.move_to_end(key)
            self._hits += 1
            return value

    def put(self, key: tuple[str, int, int], value: bytes) -> None:
        if self.max_bytes == 0 or len(value) > self.max_bytes:
            return
        with self._lock:
            previous = self._values.pop(key, None)
            if previous is not None:
                self._bytes -= len(previous)
            self._values[key] = value
            self._bytes += len(value)
            while self._bytes > self.max_bytes and self._values:
                _old_key, old_value = self._values.popitem(last=False)
                self._bytes -= len(old_value)
                self._evictions += 1

    def clear(self) -> None:
        with self._lock:
            self._values.clear()
            self._bytes = 0

    def info(self) -> dict[str, int]:
        with self._lock:
            return {
                "entries": len(self._values),
                "bytes": self._bytes,
                "max_bytes": self.max_bytes,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
            }


class IrohTransaction:
    """An fsspec transaction that publishes all mutations in one CAS.

    The upstream fsspec transaction commits each file independently.  That is
    insufficient for an immutable manifest backend, where a transaction must
    result in exactly one namespace revision.  This coordinator retains
    private writer staging handles and submits their operations as one batch.
    """

    def __init__(self, fs: "IrohFileSystem", **kwargs: Any) -> None:
        del kwargs
        self.fs: IrohFileSystem | None = fs
        self.files: deque[IrohBufferedFile] = deque()
        self.actions: list[_Mutation] = []
        self.snapshot: _ManifestSnapshot | None = None
        self.namespace_id: str | None = None

    def __enter__(self) -> "IrohTransaction":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: BaseException | None, traceback: Any) -> bool:
        del exc, traceback
        self.complete(commit=exc_type is None)
        return False

    def start(self) -> None:
        if self.fs is None:
            raise RuntimeError("Iroh transaction is no longer active")
        self.files.clear()
        self.actions.clear()
        self.snapshot = None
        self.namespace_id = None
        self.fs._intrans = True

    def add_action(self, action: _Mutation) -> None:
        if self.fs is None:
            raise RuntimeError("Iroh transaction is no longer active")
        if self.namespace_id is not None and self.namespace_id != action.namespace_id:
            raise IrohUnsupportedOperationError(
                "an Iroh transaction cannot span namespaces",
                operation="filesystem.transaction",
            )
        self.namespace_id = action.namespace_id
        if self.snapshot is None:
            self.snapshot = action.expected or self.fs._load_manifest_snapshot(
                action.namespace_id
            )
        elif action.expected is not None and action.expected.head != self.snapshot.head:
            raise IrohConflictError(
                "Iroh namespace changed while assembling the transaction",
                operation="filesystem.transaction",
            )
        action.expected = self.snapshot
        self.actions.append(action)

    def complete(self, commit: bool = True) -> None:
        fs = self.fs
        if fs is None:
            return
        try:
            if commit and self.actions:
                fs._commit_actions(self.actions, expected=self.snapshot)
                for handle in list(self.files):
                    handle._finish_transaction(committed=True)
            else:
                for handle in list(self.files):
                    handle._finish_transaction(committed=False)
        except BaseException:
            for handle in list(self.files):
                handle._finish_transaction(committed=False)
            raise
        finally:
            self.files.clear()
            self.actions.clear()
            fs._intrans = False
            fs._transaction = None
            self.fs = None


def parse_iroh_path(value: str | os.PathLike[str], *, protocol: str | None = None) -> IrohPath:
    """Parse a full Iroh URL or an fsspec-stripped path.

    A protocol hint disambiguates stripped paths because a 64-character value
    is valid as both a namespace identifier and a blob hash; without one the
    mutable namespace protocol is used. Fully qualified URLs are
    self-describing and must agree with any supplied hint.
    """

    raw = os.fspath(value)
    if not isinstance(raw, str):
        raise IrohInvalidURLError("Iroh paths must be text", operation="filesystem.parse_url")

    if "://" in raw:
        parsed = urlsplit(raw)
        scheme = parsed.scheme.lower()
        if scheme not in IROH_PROTOCOLS:
            raise IrohInvalidURLError(
                "unsupported Iroh URL scheme", operation="filesystem.parse_url"
            )
        if protocol is not None and _validate_protocol(protocol) != scheme:
            raise IrohInvalidURLError(
                "Iroh URL protocol does not match the filesystem",
                operation="filesystem.parse_url",
            )
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise IrohInvalidURLError(
                "Iroh URLs cannot contain credentials, queries, or fragments",
                operation="filesystem.parse_url",
            )
        try:
            port = parsed.port
        except ValueError as exc:
            raise IrohInvalidURLError(
                "Iroh URL contains an invalid authority", operation="filesystem.parse_url"
            ) from exc
        if port is not None:
            raise IrohInvalidURLError(
                "Iroh URLs cannot contain a port", operation="filesystem.parse_url"
            )

        if scheme == IROH_BLOB_PROTOCOL:
            if parsed.path:
                raise IrohInvalidURLError(
                    "immutable blob URLs cannot contain a path",
                    operation="filesystem.parse_url",
                )
            return IrohPath(scheme, blob_hash=_validate_hash(parsed.netloc))

        namespace_id = _validate_namespace(parsed.netloc)
        return IrohPath(scheme, namespace_id=namespace_id, path=_decode_url_path(parsed.path))

    selected = _validate_protocol(protocol) if protocol is not None else IROH_PROTOCOL
    if selected == IROH_BLOB_PROTOCOL:
        if "/" in raw or not raw:
            raise IrohInvalidURLError(
                "immutable blob paths contain only a blob hash",
                operation="filesystem.parse_url",
            )
        return IrohPath(selected, blob_hash=_validate_hash(raw))

    namespace_id, separator, manifest_path = raw.partition("/")
    namespace_id = _validate_namespace(namespace_id)
    normalized = _validate_manifest_path(manifest_path) if separator else ""
    return IrohPath(selected, namespace_id=namespace_id, path=normalized)


class IrohFileSystem(AbstractFileSystem):
    """Fsspec filesystem for mutable Iroh namespaces and immutable blobs.

    Runtime collaborators are deliberately opaque here.  Read, discovery, and
    mutation implementations can use ``client``, ``blob_store``, and
    ``manifest_store`` without tying registration to service lifecycle.  A
    ``client_factory`` is retained lazily and is called only by
    :meth:`get_runtime_client`, never during import or construction.
    """

    protocol: ClassVar[tuple[str, str]] = IROH_PROTOCOLS
    root_marker: ClassVar[str] = ""
    cachable: ClassVar[bool] = False
    async_impl: ClassVar[bool] = True
    mirror_sync_methods: ClassVar[bool] = False
    blocksize: ClassVar[int] = DEFAULT_BLOCK_SIZE
    transaction_type: ClassVar[type[IrohTransaction]] = IrohTransaction

    def __init__(
        self,
        *args: Any,
        protocol: str | None = None,
        _iroh_protocol: str | None = None,
        client: Any = None,
        client_factory: Callable[[], Any] | None = None,
        blob_store: Any = None,
        manifest_store: Any = None,
        block_size: int | None = None,
        auto_fetch: bool = True,
        offline: bool = False,
        fetch_options: Mapping[str, Any] | None = None,
        read_only: bool = False,
        writer_id: str | None = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        max_pending_operations: int = DEFAULT_MAX_PENDING_OPERATIONS,
        read_ahead_size: int | None = None,
        range_cache_size: int = DEFAULT_RANGE_CACHE_SIZE,
        multipart_threshold: int = DEFAULT_MULTIPART_THRESHOLD,
        multipart_part_size: int = DEFAULT_MULTIPART_PART_SIZE,
        asynchronous: bool = False,
        loop: Any = None,
        **storage_options: Any,
    ) -> None:
        del loop
        if protocol is not None and _iroh_protocol is not None and protocol != _iroh_protocol:
            raise ValueError("conflicting Iroh protocol hints")
        self._iroh_protocol = _validate_protocol(_iroh_protocol or protocol or IROH_PROTOCOL)
        if client_factory is not None and not callable(client_factory):
            raise TypeError("client_factory must be callable")
        if block_size is not None:
            if isinstance(block_size, bool) or not isinstance(block_size, int) or block_size <= 0:
                raise ValueError("block_size must be a positive integer")
            self.blocksize = block_size
        if not isinstance(auto_fetch, bool):
            raise TypeError("auto_fetch must be a boolean")
        if not isinstance(offline, bool):
            raise TypeError("offline must be a boolean")
        if fetch_options is not None and not isinstance(fetch_options, Mapping):
            raise TypeError("fetch_options must be a mapping")
        if not isinstance(read_only, bool):
            raise TypeError("read_only must be a boolean")
        if writer_id is not None:
            writer_id = _validate_hash(writer_id)
        max_concurrency = _positive_int(max_concurrency, "max_concurrency")
        max_pending_operations = _positive_int(
            max_pending_operations, "max_pending_operations"
        )
        if max_pending_operations < max_concurrency:
            raise ValueError("max_pending_operations must be at least max_concurrency")
        if read_ahead_size is None:
            read_ahead_size = self.blocksize
        read_ahead_size = _positive_int(read_ahead_size, "read_ahead_size")
        range_cache_size = _non_negative_int(range_cache_size, "range_cache_size")
        multipart_threshold = _positive_int(
            multipart_threshold, "multipart_threshold"
        )
        multipart_part_size = _positive_int(
            multipart_part_size, "multipart_part_size"
        )

        # These assignments are inert: none performs discovery, RPC, process
        # management, installation, or filesystem writes.
        self.client = client
        self.client_factory = client_factory
        self.blob_store = blob_store
        self.manifest_store = manifest_store
        self.auto_fetch = auto_fetch
        self.offline = offline
        self.fetch_options = dict(fetch_options or {})
        self.read_only = read_only
        self.writer_id = writer_id
        self.max_concurrency = max_concurrency
        self.max_pending_operations = max_pending_operations
        self.read_ahead_size = read_ahead_size
        self.range_cache_size = range_cache_size
        self.multipart_threshold = multipart_threshold
        self.multipart_part_size = multipart_part_size
        self.asynchronous = bool(asynchronous)
        self._loop = None
        self._range_cache = _RangeCache(range_cache_size)
        self._client_lock = threading.Lock()
        self._async_adapter: IrohAsyncFileSystem | None = None
        super().__init__(*args, **storage_options)
        # The vendored compatibility base intentionally has no transaction
        # support, so keep these fields explicit and identical in both modes.
        self._intrans = False
        self._transaction: IrohTransaction | None = None

    @property
    def transaction(self) -> IrohTransaction:
        if self._transaction is None:
            self._transaction = self.transaction_type(self)
        return self._transaction

    def start_transaction(self) -> IrohTransaction:
        transaction = self.transaction_type(self)
        self._transaction = transaction
        transaction.start()
        return transaction

    def end_transaction(self) -> None:
        if self._transaction is None:
            return
        self._transaction.complete(commit=True)

    @classmethod
    def _get_kwargs_from_urls(cls, path: str) -> dict[str, Any]:
        """Keep URL-created namespace and blob filesystem instances distinct."""

        if not isinstance(path, str) or "://" not in path:
            return {}
        scheme = urlsplit(path).scheme.lower()
        if scheme in IROH_PROTOCOLS:
            return {"_iroh_protocol": scheme}
        return {}

    @classmethod
    def _strip_protocol(cls, path: Any) -> Any:
        """Return fsspec's credential-free internal spelling for an Iroh URL."""

        if isinstance(path, (list, tuple)):
            return [cls._strip_protocol(item) for item in path]
        raw = os.fspath(path)
        if not isinstance(raw, str):
            return raw
        if "://" not in raw:
            return raw.rstrip("/")
        parsed = parse_iroh_path(raw)
        return parsed.stripped_path

    def unstrip_protocol(self, name: str) -> str:
        """Return the canonical URL for a path belonging to this instance."""

        return self.parse_path(name).canonical_url

    def parse_path(self, path: str | os.PathLike[str]) -> IrohPath:
        return parse_iroh_path(path, protocol=self._iroh_protocol)

    def get_runtime_client(self) -> Any:
        """Return the injected client, creating it lazily when configured."""

        if self.client is None and self.client_factory is not None:
            with self._client_lock:
                if self.client is None:
                    self.client = _sync_result(self.client_factory())
        return self.client

    def cache_info(self) -> dict[str, int]:
        """Return bounded range-cache counters without exposing cache keys."""

        return self._range_cache.info()

    def clear_range_cache(self) -> None:
        """Drop all cached immutable ranges while retaining statistics."""

        self._range_cache.clear()

    def as_async(self) -> "IrohAsyncFileSystem":
        """Return an AnyIO-compatible adapter sharing clients and range cache."""

        if isinstance(self, IrohAsyncFileSystem):
            return self
        if self._async_adapter is not None:
            return self._async_adapter
        adapter = IrohAsyncFileSystem(
            protocol=self._iroh_protocol,
            client=self.client,
            client_factory=self.client_factory,
            blob_store=self.blob_store,
            manifest_store=self.manifest_store,
            block_size=self.blocksize,
            auto_fetch=self.auto_fetch,
            offline=self.offline,
            fetch_options=self.fetch_options,
            read_only=self.read_only,
            writer_id=self.writer_id,
            max_concurrency=self.max_concurrency,
            max_pending_operations=self.max_pending_operations,
            read_ahead_size=self.read_ahead_size,
            range_cache_size=self.range_cache_size,
            multipart_threshold=self.multipart_threshold,
            multipart_part_size=self.multipart_part_size,
        )
        adapter._range_cache = self._range_cache
        self._async_adapter = adapter
        return adapter

    def get_blob_store(self) -> Any:
        """Return the injected blob store or lazily wrap the runtime client."""

        if self.blob_store is None:
            client = self.get_runtime_client()
            if client is None:
                raise IrohUnavailableError(
                    "an Iroh blob store or runtime client is required",
                    operation="filesystem.read",
                )
            from .iroh.blob_store import IrohBlobStore

            self.blob_store = IrohBlobStore(client)
        return self.blob_store

    def open(
        self,
        path: str,
        mode: str = "rb",
        block_size: int | None = None,
        cache_options: Mapping[str, Any] | None = None,
        compression: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Open an Iroh path with identical external and vendored behavior.

        The bundled fsspec compatibility base intentionally has no functional
        ``open`` implementation. Keeping this adapter here makes registered
        Iroh filesystems usable even when upstream fsspec is not installed.
        """

        stripped = self._strip_protocol(path)
        if "b" not in mode:
            binary_mode = mode.replace("t", "") + "b"
            text_options = {
                key: kwargs.pop(key)
                for key in ("encoding", "errors", "newline")
                if key in kwargs
            }
            binary = self.open(
                stripped,
                binary_mode,
                block_size=block_size,
                cache_options=cache_options,
                compression=compression,
                **kwargs,
            )
            try:
                return io.TextIOWrapper(binary, **text_options)
            except BaseException:
                binary.close()
                raise

        autocommit = kwargs.pop("autocommit", not getattr(self, "_intrans", False))
        handle: Any = self._open(
            stripped,
            mode=mode,
            block_size=block_size,
            autocommit=autocommit,
            cache_options=cache_options,
            **kwargs,
        )
        if not autocommit and "r" not in mode:
            transaction = self.transaction
            handle._register_transaction(transaction)
            transaction.files.append(handle)
        if compression is not None:
            try:
                from fsspec.compression import compr
                from fsspec.core import get_compression
            except (ImportError, ModuleNotFoundError):
                handle.close()
                raise IrohUnsupportedOperationError(
                    "compression wrappers require the optional fsspec dependency",
                    operation="filesystem.open",
                ) from None
            selected = get_compression(stripped, compression)
            handle = compr[selected](handle, mode=mode[0])
        return handle

    def _open(
        self,
        path: str,
        mode: str = "rb",
        block_size: int | None = None,
        autocommit: bool = True,
        cache_options: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> "IrohBufferedFile":
        parsed = self.parse_path(path)
        if mode.replace("t", "").replace("b", "") in {"w", "x"}:
            self._mutable_path(path, "filesystem.open")
        file_type: type[IrohBufferedFile]
        file_type = IrohBlobFile if parsed.is_blob else IrohFile
        return file_type(
            self,
            parsed,
            mode=mode,
            block_size=block_size or self.blocksize,
            autocommit=autocommit,
            cache_options=cache_options,
            **kwargs,
        )

    def pipe(
        self,
        path: str | Mapping[str, bytes],
        value: bytes | None = None,
        **kwargs: Any,
    ) -> None:
        """Write one value or atomically batch a same-namespace mapping."""

        if isinstance(path, str):
            if value is None:
                raise TypeError("value is required for a single path")
            self.pipe_file(path, value, **kwargs)
            return
        if not isinstance(path, Mapping):
            raise ValueError("path must be a string or a mapping")
        if self._intrans:
            for target, payload in path.items():
                self.pipe_file(target, payload, **kwargs)
            return
        with self.transaction:
            for target, payload in path.items():
                self.pipe_file(target, payload, **kwargs)

    def cat_file(
        self, path: str, start: int | None = None, end: int | None = None, **kwargs: Any
    ) -> bytes:
        """Read a verified half-open byte range from a file or immutable blob."""

        parsed = self.parse_path(path)
        blob_hash, size = self._resolve_blob(parsed, fetch_options=kwargs)
        begin, stop = _normalize_read_range(size, start, end)
        if begin == stop:
            return b""
        value = self._read_blob_cached(
            blob_hash,
            begin,
            stop,
            blob_size=size,
            fetch_options=kwargs,
        )
        return _validate_range_result(value, stop - begin, "filesystem.cat_file")

    def pipe_file(
        self,
        path: str,
        value: bytes | bytearray | memoryview,
        mode: str = "overwrite",
        **kwargs: Any,
    ) -> None:
        """Ingest bytes, then atomically create or replace one manifest entry."""

        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError("value must be bytes-like")
        overwrite = _overwrite_option(mode, kwargs.pop("overwrite", None))
        parsed = self._mutable_path(path, "filesystem.pipe_file")
        action = _Mutation(
            "write",
            str(parsed.namespace_id),
            parsed.path,
            source=io.BytesIO(bytes(value)),
            overwrite=overwrite,
            mode=kwargs.pop("file_mode", kwargs.pop("permissions", None)),
            metadata=kwargs.pop("metadata", None),
            expected=self._load_manifest_snapshot(str(parsed.namespace_id)),
        )
        self._defer_or_commit(action)

    def put_file(
        self,
        lpath: str | os.PathLike[str],
        rpath: str,
        callback: Any = None,
        mode: str = "overwrite",
        **kwargs: Any,
    ) -> None:
        """Stream a local file into Iroh without materializing it in memory."""

        source = Path(lpath)
        if source.is_dir():
            self.makedirs(rpath, exist_ok=True)
            return
        if not source.is_file():
            raise FileNotFoundError(os.fspath(source))
        overwrite = _overwrite_option(mode, kwargs.pop("overwrite", None))
        parsed = self._mutable_path(rpath, "filesystem.put_file")
        if callback is not None and hasattr(callback, "set_size"):
            callback.set_size(source.stat().st_size)
        action = _Mutation(
            "write",
            str(parsed.namespace_id),
            parsed.path,
            source=source,
            overwrite=overwrite,
            mode=kwargs.pop("file_mode", kwargs.pop("permissions", None)),
            metadata=kwargs.pop("metadata", None),
            expected=self._load_manifest_snapshot(str(parsed.namespace_id)),
        )
        self._defer_or_commit(action)
        if callback is not None and hasattr(callback, "relative_update"):
            callback.relative_update(source.stat().st_size)

    def mkdir(
        self,
        path: str,
        create_parents: bool = False,
        exist_ok: bool = False,
        **kwargs: Any,
    ) -> None:
        parsed = self._mutable_path(path, "filesystem.mkdir")
        action = _Mutation(
            "mkdir",
            str(parsed.namespace_id),
            parsed.path,
            create_parents=bool(create_parents),
            exist_ok=bool(exist_ok),
            mode=kwargs.pop("mode", None),
            expected=self._load_manifest_snapshot(str(parsed.namespace_id)),
        )
        self._defer_or_commit(action)

    def makedirs(self, path: str, exist_ok: bool = False) -> None:
        self.mkdir(path, create_parents=True, exist_ok=exist_ok)

    mkdirs = makedirs

    def rmdir(self, path: str) -> None:
        self.rm(path, recursive=False)

    def rm_file(self, path: str) -> None:
        self.rm(path, recursive=False)

    _rm = rm_file

    def rm(
        self,
        path: str | Sequence[str],
        recursive: bool = False,
        maxdepth: int | None = None,
        **kwargs: Any,
    ) -> None:
        del kwargs
        if maxdepth is not None:
            raise IrohUnsupportedOperationError(
                "bounded recursive removal is not supported",
                operation="filesystem.rm",
            )
        raw_paths = [path] if isinstance(path, (str, os.PathLike)) else list(path)
        if not raw_paths:
            return
        parsed_paths = [self._mutable_path(item, "filesystem.rm") for item in raw_paths]
        namespaces = {item.namespace_id for item in parsed_paths}
        if len(namespaces) != 1:
            raise IrohUnsupportedOperationError(
                "one atomic removal cannot span Iroh namespaces",
                operation="filesystem.rm",
            )
        namespace = str(parsed_paths[0].namespace_id)
        action = _Mutation(
            "rm",
            namespace,
            parsed_paths[0].path,
            source=[item.path for item in parsed_paths],
            recursive=bool(recursive),
            expected=self._load_manifest_snapshot(namespace),
        )
        self._defer_or_commit(action)

    def cp_file(self, path1: str, path2: str, **kwargs: Any) -> None:
        self.copy(path1, path2, recursive=False, **kwargs)

    def copy(
        self,
        path1: str,
        path2: str,
        recursive: bool = False,
        maxdepth: int | None = None,
        on_error: str | None = None,
        **kwargs: Any,
    ) -> None:
        del on_error
        if maxdepth is not None:
            raise IrohUnsupportedOperationError(
                "bounded recursive copy is not supported",
                operation="filesystem.copy",
            )
        source = self.parse_path(path1)
        destination = self._mutable_path(path2, "filesystem.copy")
        if source.is_blob:
            raise IrohUnsupportedOperationError(
                "immutable blob URLs cannot be namespace copy sources",
                operation="filesystem.copy",
            )
        overwrite = _overwrite_option(kwargs.pop("mode", "create"), kwargs.pop("overwrite", None))
        action = _Mutation(
            "copy",
            str(destination.namespace_id),
            str(source.path),
            destination=destination.path,
            source=source,
            overwrite=overwrite,
            recursive=bool(recursive),
            expected=self._load_manifest_snapshot(str(destination.namespace_id)),
        )
        self._defer_or_commit(action)

    cp = copy

    def mv(
        self,
        path1: str,
        path2: str,
        recursive: bool = False,
        maxdepth: int | None = None,
        **kwargs: Any,
    ) -> None:
        if maxdepth is not None:
            raise IrohUnsupportedOperationError(
                "bounded recursive moves are not supported",
                operation="filesystem.move",
            )
        source = self._mutable_path(path1, "filesystem.move")
        destination = self._mutable_path(path2, "filesystem.move")
        overwrite = _overwrite_option(kwargs.pop("mode", "create"), kwargs.pop("overwrite", None))
        if source.namespace_id != destination.namespace_id:
            if kwargs.pop("atomic", False):
                raise IrohUnsupportedOperationError(
                    "atomic cross-namespace moves are not supported",
                    operation="filesystem.move",
                )
            self.copy(path1, path2, recursive=recursive, overwrite=overwrite)
            self.rm(path1, recursive=recursive)
            return
        action = _Mutation(
            "move",
            str(source.namespace_id),
            source.path,
            destination=destination.path,
            overwrite=overwrite,
            recursive=bool(recursive),
            expected=self._load_manifest_snapshot(str(source.namespace_id)),
        )
        self._defer_or_commit(action)

    move = mv

    def chmod(self, path: str, mode: int) -> None:
        del path, mode
        raise IrohUnsupportedOperationError(
            "Iroh manifest modes cannot be changed in place", operation="filesystem.chmod"
        )

    def chown(self, path: str, uid: Any, gid: Any) -> None:
        del path, uid, gid
        raise IrohUnsupportedOperationError(
            "Iroh manifest ownership changes are unsupported", operation="filesystem.chown"
        )

    def touch(self, path: str, truncate: bool = True, **kwargs: Any) -> None:
        del truncate, kwargs
        if self.exists(path):
            raise IrohUnsupportedOperationError(
                "existing Iroh entries cannot be touched or truncated in place",
                operation="filesystem.touch",
            )
        self.pipe_file(path, b"", overwrite=False)

    def info(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """Return fsspec metadata for a current manifest entry or blob."""

        parsed = self.parse_path(path)
        if parsed.is_blob:
            size = self._blob_size(str(parsed.blob_hash), fetch_options=kwargs)
            return _blob_info(parsed, size)
        view = self._load_manifest(str(parsed.namespace_id))
        return self._entry_info(parsed, view.entry(parsed.path), view.revision)

    def ls(self, path: str, detail: bool = True, **kwargs: Any) -> list[Any]:
        """List a file itself or the immediate children of a directory."""

        parsed = self.parse_path(path)
        if parsed.is_blob:
            raise IrohUnsupportedOperationError(
                "immutable Iroh blobs do not provide directory listings",
                operation="filesystem.ls",
            )

        view = self._load_manifest(str(parsed.namespace_id))
        requested = view.entry(parsed.path)
        if requested.get("kind") == "file":
            result = [self._entry_info(parsed, requested, view.revision)]
        else:
            prefix = f"{parsed.path}/" if parsed.path else ""
            result = []
            for entry_path, entry in view.entries.items():
                if entry_path == parsed.path or not entry_path.startswith(prefix):
                    continue
                remainder = entry_path[len(prefix) :]
                if "/" not in remainder:
                    child = IrohPath(
                        IROH_PROTOCOL,
                        namespace_id=parsed.namespace_id,
                        path=entry_path,
                    )
                    result.append(self._entry_info(child, entry, view.revision))
            result.sort(key=lambda item: _name_sort_key(item["name"]))
        return result if detail else [item["name"] for item in result]

    def exists(self, path: str, **kwargs: Any) -> bool:
        try:
            self.info(path, **kwargs)
        except (FileNotFoundError, IrohNotFoundError):
            return False
        return True

    def isfile(self, path: str) -> bool:
        try:
            return self.info(path)["type"] == "file"
        except (FileNotFoundError, IrohNotFoundError):
            return False

    def isdir(self, path: str) -> bool:
        try:
            return self.info(path)["type"] == "directory"
        except (FileNotFoundError, IrohNotFoundError):
            return False

    def find(
        self,
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        detail: bool = False,
        **kwargs: Any,
    ) -> list[str] | dict[str, dict[str, Any]]:
        """Find descendants using one immutable manifest-head snapshot."""

        if maxdepth is not None and (
            isinstance(maxdepth, bool) or not isinstance(maxdepth, int) or maxdepth < 1
        ):
            raise ValueError("maxdepth must be at least 1")
        # fsspec's glob implementation passes a derived directory root with a
        # trailing separator. Full user URLs remain contract-validated by
        # ``_strip_protocol`` before this internal spelling is normalized.
        path = self._strip_protocol(path)
        parsed = self.parse_path(path)
        if parsed.is_blob:
            raise IrohUnsupportedOperationError(
                "immutable Iroh blobs do not provide directory discovery",
                operation="filesystem.find",
            )

        view = self._load_manifest(str(parsed.namespace_id))
        return self._find_in_view(parsed, view, maxdepth, withdirs, detail)

    def _find_in_view(
        self,
        parsed: IrohPath,
        view: _ManifestView,
        maxdepth: int | None,
        withdirs: bool,
        detail: bool,
    ) -> list[str] | dict[str, dict[str, Any]]:
        """Implement ``find`` against an already selected manifest head."""

        requested = view.entry(parsed.path)
        candidates: dict[str, dict[str, Any]] = {}
        if requested.get("kind") == "file":
            item = self._entry_info(parsed, requested, view.revision)
            candidates[item["name"]] = item
        else:
            prefix = f"{parsed.path}/" if parsed.path else ""
            if withdirs:
                item = self._entry_info(parsed, requested, view.revision)
                candidates[item["name"]] = item
            for entry_path, entry in view.entries.items():
                if entry_path == parsed.path or not entry_path.startswith(prefix):
                    continue
                relative = entry_path[len(prefix) :]
                depth = relative.count("/") + 1
                if maxdepth is not None and depth > maxdepth:
                    continue
                if entry.get("kind") != "file" and not withdirs:
                    continue
                child = IrohPath(
                    IROH_PROTOCOL,
                    namespace_id=parsed.namespace_id,
                    path=entry_path,
                )
                item = self._entry_info(child, entry, view.revision)
                candidates[item["name"]] = item
        names = sorted(candidates, key=_name_sort_key)
        return {name: candidates[name] for name in names} if detail else names

    def glob(
        self,
        path: str,
        maxdepth: int | None = None,
        **kwargs: Any,
    ) -> list[str] | dict[str, dict[str, Any]]:
        """Match live paths from one manifest snapshot using fsspec glob syntax."""

        if maxdepth is not None and (
            isinstance(maxdepth, bool) or not isinstance(maxdepth, int) or maxdepth < 1
        ):
            raise ValueError("maxdepth must be at least 1")
        detail = bool(kwargs.pop("detail", False))
        stripped = self._strip_protocol(path)
        if self._iroh_protocol == IROH_BLOB_PROTOCOL:
            raise IrohUnsupportedOperationError(
                "immutable Iroh blobs do not provide directory discovery",
                operation="filesystem.glob",
            )

        parsed_pattern = self.parse_path(stripped)
        view = self._load_manifest(str(parsed_pattern.namespace_id))
        return self._glob_in_view(stripped, parsed_pattern, view, maxdepth, detail)

    def _glob_in_view(
        self,
        stripped: str,
        parsed_pattern: IrohPath,
        view: _ManifestView,
        maxdepth: int | None,
        detail: bool,
    ) -> list[str] | dict[str, dict[str, Any]]:
        """Implement ``glob`` against an already selected manifest head."""

        if not globlib.has_magic(stripped):
            try:
                entry = view.entry(parsed_pattern.path)
            except IrohNotFoundError:
                return {} if detail else []
            item = self._entry_info(parsed_pattern, entry, view.revision)
            return {item["name"]: item} if detail else [item["name"]]

        matcher = re.compile(_glob_translate(stripped))
        pattern_parts = stripped.split("/")
        double_star = pattern_parts.index("**") if "**" in pattern_parts else None
        matches: list[tuple[str, dict[str, Any]]] = []
        for entry_path, entry in view.entries.items():
            candidate = str(parsed_pattern.namespace_id) + (
                f"/{entry_path}" if entry_path else ""
            )
            if matcher.match(candidate) is None:
                continue
            if maxdepth is not None and double_star is not None:
                # fsspec applies maxdepth to the complete candidate suffix
                # beginning at the first recursive component. A depth of one
                # therefore permits ``**`` to consume no directory before a
                # final filename, but not one nested directory.
                consumed = len(candidate.split("/")) - double_star
                if consumed > maxdepth:
                    continue
            candidate_path = IrohPath(
                IROH_PROTOCOL,
                namespace_id=parsed_pattern.namespace_id,
                path=entry_path,
            )
            matches.append((entry_path, self._entry_info(candidate_path, entry, view.revision)))
        matches.sort(key=lambda item: item[0].encode("utf-8"))
        if detail:
            return {item["name"]: item for _, item in matches}
        return [item["name"] for _, item in matches]

    def walk(
        self,
        path: str,
        maxdepth: int | None = None,
        topdown: bool = True,
        on_error: str | Callable[[OSError], Any] = "omit",
        **kwargs: Any,
    ) -> Iterator[tuple[str, Any, Any]]:
        """Walk a namespace tree with os.walk-compatible pruning behavior."""

        if maxdepth is not None and (
            isinstance(maxdepth, bool) or not isinstance(maxdepth, int) or maxdepth < 1
        ):
            raise ValueError("maxdepth must be at least 1")
        detail = bool(kwargs.pop("detail", False))
        try:
            parsed = self.parse_path(path)
            if parsed.is_blob:
                raise IrohUnsupportedOperationError(
                    "immutable Iroh blobs do not provide directory discovery",
                    operation="filesystem.walk",
                )
            view = self._load_manifest(str(parsed.namespace_id))
            root_entry = view.entry(parsed.path)
        except FileNotFoundError as exc:
            if on_error == "raise":
                raise
            if callable(on_error):
                on_error(exc)
            return

        root_name = parsed.canonical_url
        if root_entry.get("kind") == "file":
            item = self._entry_info(parsed, root_entry, view.revision)
            yield root_name, {} if detail else [], {"": item} if detail else [""]
            return

        children: dict[str, list[tuple[str, Mapping[str, Any]]]] = defaultdict(list)
        for entry_path, entry in view.entries.items():
            if entry_path == "":
                continue
            parent, _, basename = entry_path.rpartition("/")
            children[parent].append((basename, entry))
        for values in children.values():
            values.sort(key=lambda item: item[0].encode("utf-8"))

        def visit(current_path: str, current_name: str, depth: int) -> Iterator[tuple[str, Any, Any]]:
            directory_items: dict[str, dict[str, Any]] = {}
            file_items: dict[str, dict[str, Any]] = {}
            for basename, entry in children.get(current_path, []):
                child_path = basename if not current_path else f"{current_path}/{basename}"
                child = IrohPath(
                    IROH_PROTOCOL,
                    namespace_id=parsed.namespace_id,
                    path=child_path,
                )
                item = self._entry_info(child, entry, view.revision)
                target = directory_items if entry.get("kind") == "directory" else file_items
                target[basename] = item
            dirs: Any = directory_items if detail else list(directory_items)
            files: Any = file_items if detail else list(file_items)
            if topdown:
                yield current_name, dirs, files
            if maxdepth is None or depth < maxdepth:
                # Iterate the live object returned to the caller, so top-down
                # callers can prune by deleting names exactly like os.walk.
                selected = list(dirs) if topdown else list(directory_items)
                for basename in selected:
                    child_path = basename if not current_path else f"{current_path}/{basename}"
                    child_name = IrohPath(
                        IROH_PROTOCOL,
                        namespace_id=parsed.namespace_id,
                        path=child_path,
                    ).canonical_url
                    yield from visit(child_path, child_name, depth + 1)
            if not topdown:
                yield current_name, dirs, files

        yield from visit(parsed.path, root_name, 1)

    def get_file(
        self,
        rpath: str,
        lpath: str | os.PathLike[str] | Any,
        callback: Any = None,
        outfile: Any = None,
        **kwargs: Any,
    ) -> None:
        """Stream one file to a file-like object or atomically to a local path."""

        parsed = self.parse_path(rpath)
        if parsed.is_blob:
            blob_hash, size = self._resolve_blob(parsed, fetch_options=kwargs)
            info = _blob_info(parsed, size)
        else:
            view = self._load_manifest(str(parsed.namespace_id))
            manifest_entry = view.entry(parsed.path)
            info = self._entry_info(parsed, manifest_entry, view.revision)
            if manifest_entry.get("kind") == "file":
                blob_hash = str(manifest_entry["blob_hash"])
                size = int(manifest_entry["size"])
        if info["type"] == "directory":
            if not _is_filelike(lpath):
                os.makedirs(os.fspath(lpath), exist_ok=True)
            return None
        callback = callback or _NoOpCallback()
        if hasattr(callback, "set_size"):
            callback.set_size(info["size"])

        supplied = outfile if outfile is not None else (lpath if _is_filelike(lpath) else None)
        if supplied is not None:
            self._copy_blob_to_handle(blob_hash, size, supplied, callback, **kwargs)
            return None

        target = Path(os.fspath(lpath))
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.iroh-", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                self._copy_blob_to_handle(blob_hash, size, handle, callback, **kwargs)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
            raise
        return None

    def cat(
        self,
        path: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
        recursive: bool = False,
        on_error: str = "raise",
        **kwargs: Any,
    ) -> bytes | dict[str, bytes | Exception]:
        """Read one or many paths, recursively expanding directories to files."""

        if on_error not in {"raise", "omit", "return"}:
            raise ValueError("on_error must be 'raise', 'omit', or 'return'")
        maxdepth = kwargs.pop("maxdepth", None)
        if maxdepth is not None and (
            isinstance(maxdepth, bool) or not isinstance(maxdepth, int) or maxdepth < 1
        ):
            raise ValueError("maxdepth must be at least 1")
        is_many = isinstance(path, Sequence) and not isinstance(path, (str, bytes, os.PathLike))
        requested = list(path) if is_many else [path]  # type: ignore[list-item]
        expanded: set[str] = set()
        views: dict[str, _ManifestView] = {}

        def manifest_for(parsed: IrohPath) -> _ManifestView:
            namespace_id = str(parsed.namespace_id)
            if namespace_id not in views:
                views[namespace_id] = self._load_manifest(namespace_id)
            return views[namespace_id]

        was_expanded = False
        for raw in requested:
            stripped = self._strip_protocol(raw)
            if globlib.has_magic(stripped):
                parsed_pattern = self.parse_path(stripped)
                if parsed_pattern.is_blob:
                    raise IrohUnsupportedOperationError(
                        "immutable Iroh blobs do not provide directory discovery",
                        operation="filesystem.cat",
                    )
                matches = self._glob_in_view(
                    stripped,
                    parsed_pattern,
                    manifest_for(parsed_pattern),
                    maxdepth,
                    False,
                )
                was_expanded = True
                if not matches:
                    if on_error == "raise":
                        raise FileNotFoundError(stripped)
                    continue
            else:
                matches = [self.parse_path(stripped).canonical_url]
            for match in matches:
                parsed_match = self.parse_path(match)
                if recursive and not parsed_match.is_blob:
                    view = manifest_for(parsed_match)
                    try:
                        match_entry = view.entry(parsed_match.path)
                    except IrohNotFoundError:
                        # Preserve fsspec's behavior: missing literal paths are
                        # handled according to on_error during the read phase.
                        expanded.add(match)
                        continue
                    if match_entry.get("kind") == "directory":
                        found = self._find_in_view(
                            parsed_match, view, maxdepth, False, False
                        )
                        expanded.update(found)
                        was_expanded = True
                        continue
                expanded.add(match)

        names = sorted(expanded)
        return_mapping = is_many or was_expanded or len(names) != 1
        output: dict[str, bytes | Exception] = {}
        for name in names:
            try:
                parsed_name = self.parse_path(name)
                if parsed_name.is_blob:
                    output[name] = self.cat_file(name, **kwargs)
                else:
                    view = manifest_for(parsed_name)
                    entry = view.entry(parsed_name.path)
                    if entry.get("kind") != "file":
                        raise IsADirectoryError(parsed_name.canonical_url)
                    size = int(entry["size"])
                    value = self._read_blob_cached(
                        str(entry["blob_hash"]),
                        0,
                        size,
                        blob_size=size,
                        fetch_options=kwargs,
                    )
                    output[name] = _validate_range_result(
                        value, size, "filesystem.cat"
                    )
            except Exception as exc:
                if on_error == "raise":
                    raise
                if on_error == "return":
                    output[name] = exc
        if return_mapping:
            return output
        return output[names[0]]

    def _copy_to_handle(self, path: str, handle: Any, callback: Any, **kwargs: Any) -> None:
        parsed = self.parse_path(path)
        blob_hash, size = self._resolve_blob(parsed, fetch_options=kwargs)
        self._copy_blob_to_handle(blob_hash, size, handle, callback, **kwargs)

    def _copy_blob_to_handle(
        self,
        blob_hash: str,
        size: int,
        handle: Any,
        callback: Any,
        **kwargs: Any,
    ) -> None:
        """Copy one pinned immutable blob to a handle in bounded ranges."""

        position = 0
        while position < size:
            stop = min(position + self.blocksize, size)
            # Exports deliberately re-read each range.  A destination is an
            # integrity boundary of its own and must not conceal a newly
            # failing/corrupt collaborator behind an earlier process cache.
            value = self._read_blob_range(
                blob_hash, position, stop, fetch_options=kwargs
            )
            chunk = _validate_range_result(
                value, stop - position, "filesystem.get_file"
            )
            written = handle.write(chunk)
            if written is not None and written != len(chunk):
                raise OSError("short write while exporting Iroh file")
            position = stop
            if hasattr(callback, "relative_update"):
                callback.relative_update(len(chunk))

    def _load_manifest(self, namespace_id: str) -> _ManifestView:
        return self._load_manifest_snapshot(namespace_id).view

    def _load_manifest_snapshot(self, namespace_id: str) -> _ManifestSnapshot:
        store = self.manifest_store
        read_methods = (
            "read_head",
            "get_manifest",
            "load_manifest",
            "load",
            "read",
            "resolve",
            "get_current",
            "get_head",
            "get",
        )
        try:
            if store is None:
                client = self.get_runtime_client()
                request = getattr(client, "request", None)
                if not callable(request):
                    raise IrohUnavailableError(
                        "an Iroh manifest store or runtime client is required",
                        operation="filesystem.manifest",
                    )
                value = request("manifests.read", {"namespace_id": namespace_id})
            elif isinstance(store, Mapping):
                value = store if "entries" in store else store[namespace_id]
            elif any(callable(getattr(store, name, None)) for name in read_methods):
                value = _call_first(store, read_methods, namespace_id)
            else:
                value = store
            value = _sync_result(value)
        except KeyError:
            raise IrohNotFoundError(
                "Iroh namespace was not found", operation="filesystem.manifest"
            ) from None
        manifest = _unwrap_manifest(value)
        view = _manifest_view(namespace_id, manifest)
        head = _extract_manifest_head(value)
        if head is None:
            head = _manifest_digest(manifest)
        return _ManifestSnapshot(view, _manifest_mapping(manifest), head)

    def _entry_info(
        self,
        path: IrohPath,
        entry: Mapping[str, Any],
        revision: int | None,
    ) -> dict[str, Any]:
        kind = entry.get("kind")
        result: dict[str, Any] = {
            "name": path.canonical_url,
            "size": int(entry.get("size", 0)) if kind == "file" else 0,
            "type": kind,
            "mode": entry.get("mode"),
            "mtime": entry.get("mtime"),
            "metadata": dict(entry.get("metadata") or {}),
        }
        if revision is not None:
            result["revision"] = revision
        if kind == "file":
            result["blob_hash"] = entry["blob_hash"]
        return result

    def _resolve_blob(
        self, parsed: IrohPath, *, fetch_options: Mapping[str, Any]
    ) -> tuple[str, int]:
        if parsed.is_blob:
            digest = str(parsed.blob_hash)
            return digest, self._blob_size(digest, fetch_options=fetch_options)
        view = self._load_manifest(str(parsed.namespace_id))
        entry = view.entry(parsed.path)
        if entry.get("kind") != "file":
            raise IsADirectoryError(parsed.canonical_url)
        return str(entry["blob_hash"]), int(entry["size"])

    def _blob_size(self, blob_hash: str, *, fetch_options: Mapping[str, Any]) -> int:
        store = self.get_blob_store()
        stat_options = {
            key: fetch_options[key] for key in ("timeout",) if key in fetch_options
        }
        try:
            value = _sync_result(_call_required(store, "stat", blob_hash, **stat_options))
        except (FileNotFoundError, IrohNotFoundError):
            self._fetch_blob(blob_hash, fetch_options)
            value = _sync_result(_call_required(store, "stat", blob_hash, **stat_options))
        size = value.get("size") if isinstance(value, Mapping) else getattr(value, "size", None)
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise IrohIntegrityError(
                "Iroh blob store returned an invalid size", operation="filesystem.info"
            )
        complete = (
            value.get("complete", True)
            if isinstance(value, Mapping)
            else getattr(value, "complete", True)
        )
        if complete is not True:
            raise IrohIntegrityError(
                "Iroh blob store reported an incomplete blob", operation="filesystem.info"
            )
        return size

    def _read_blob_range(
        self,
        blob_hash: str,
        start: int,
        end: int,
        *,
        fetch_options: Mapping[str, Any],
    ) -> Any:
        store = self.get_blob_store()
        read_options = {
            key: fetch_options[key]
            for key in ("timeout", "progress", "cancel", "cancellation_event")
            if key in fetch_options
        }
        try:
            return _sync_result(
                _call_required(
                    store, "read_range", blob_hash, start=start, end=end, **read_options
                )
            )
        except (FileNotFoundError, IrohNotFoundError):
            self._fetch_blob(blob_hash, fetch_options)
            return _sync_result(
                _call_required(
                    store, "read_range", blob_hash, start=start, end=end, **read_options
                )
            )

    def _read_blob_cached(
        self,
        blob_hash: str,
        start: int,
        end: int,
        *,
        blob_size: int,
        fetch_options: Mapping[str, Any],
    ) -> bytes:
        """Read through aligned, bounded read-ahead blocks.

        The requested result may naturally be large (``cat_file`` promises a
        bytes object), but transport reads and retained cache memory remain
        bounded by ``read_ahead_size`` and ``range_cache_size`` respectively.
        """

        if start >= end:
            return b""
        chunks: list[bytes] = []
        position = start
        while position < end:
            block_start = (position // self.read_ahead_size) * self.read_ahead_size
            block_end = min(block_start + self.read_ahead_size, blob_size)
            key = (blob_hash, block_start, block_end)
            block = self._range_cache.get(key)
            if block is None:
                value = self._read_blob_range(
                    blob_hash,
                    block_start,
                    block_end,
                    fetch_options=fetch_options,
                )
                block = _validate_range_result(
                    value, block_end - block_start, "filesystem.read_ahead"
                )
                self._range_cache.put(key, block)
            take_start = position - block_start
            take_end = min(end, block_end) - block_start
            chunks.append(block[take_start:take_end])
            position = block_start + take_end
        return b"".join(chunks)

    def _fetch_blob(self, blob_hash: str, options: Mapping[str, Any]) -> None:
        if self.offline or not self.auto_fetch:
            raise IrohNotFoundError(
                "Iroh blob is not available in the local cache",
                operation="filesystem.read",
            )
        store = self.get_blob_store()
        fetch = getattr(store, "fetch", None)
        if not callable(fetch):
            raise IrohNotFoundError(
                "Iroh blob is not available and the store cannot fetch it",
                operation="filesystem.read",
            )
        allowed = {"provider", "ticket", "timeout", "progress", "cancel", "cancellation_event"}
        selected = dict(self.fetch_options)
        nested = options.get("fetch_options")
        if nested is not None:
            if not isinstance(nested, Mapping):
                raise TypeError("fetch_options must be a mapping")
            selected.update(nested)
        selected.update({key: options[key] for key in allowed if key in options})
        _sync_result(fetch(blob_hash, **selected))

    # -- mutation planning and commit -------------------------------------

    def _mutable_path(self, path: str | os.PathLike[str], operation: str) -> IrohPath:
        parsed = self.parse_path(path)
        if parsed.is_blob:
            raise IrohUnsupportedOperationError(
                "immutable Iroh blobs cannot be modified", operation=operation
            )
        if self.read_only:
            raise IrohPermissionDeniedError(
                "the Iroh namespace is mounted read-only", operation=operation
            )
        return parsed

    def _defer_or_commit(self, action: _Mutation) -> None:
        if self._intrans:
            transaction = self.transaction
            transaction.add_action(action)
            return
        self._commit_actions([action], expected=action.expected)

    def _commit_actions(
        self,
        actions: Sequence[_Mutation],
        *,
        expected: _ManifestSnapshot | None = None,
    ) -> None:
        """Apply a batch to one observed head and publish exactly one revision."""

        if not actions:
            return
        namespace_id = actions[0].namespace_id
        if any(action.namespace_id != namespace_id for action in actions):
            raise IrohUnsupportedOperationError(
                "an atomic Iroh mutation cannot span namespaces",
                operation="filesystem.transaction",
            )
        snapshot = expected or self._load_manifest_snapshot(namespace_id)
        if snapshot.view.namespace_id != namespace_id:
            raise IrohConflictError(
                "Iroh mutation snapshot belongs to a different namespace",
                operation="filesystem.commit",
            )
        for action in actions:
            if action.expected is not None and action.expected.head != snapshot.head:
                raise IrohConflictError(
                    "Iroh namespace changed before mutation commit",
                    operation="filesystem.commit",
                )

        entries = _all_manifest_entries(snapshot.manifest)
        original = {path: dict(entry) for path, entry in entries.items()}
        now = _utc_now()
        # Preflight the entire batch against a private tree before publishing
        # any content. This catches collisions, ancestry, ACL, mode, and
        # recursive-shape failures without leaving avoidable orphan blobs.
        preview = {path: dict(entry) for path, entry in entries.items()}
        for action in actions:
            self._apply_planned_action(preview, snapshot.manifest, action, now, preview=True)
        for action in actions:
            if action.kind == "write":
                digest, size = self._ingest_mutation_source(action.source)
                self._apply_write(entries, snapshot.manifest, action, digest, size, now)
            else:
                self._apply_planned_action(entries, snapshot.manifest, action, now)

        if entries == original:
            return
        manifest = self._next_manifest(snapshot, entries, now)
        self._compare_and_swap(namespace_id, snapshot.head, manifest)

    def _apply_planned_action(
        self,
        entries: dict[str, dict[str, Any]],
        manifest: Mapping[str, Any],
        action: _Mutation,
        now: str,
        *,
        preview: bool = False,
    ) -> None:
        if action.kind == "write":
            self._apply_write(entries, manifest, action, "0" * 64, 0, now)
        elif action.kind == "mkdir":
            self._apply_mkdir(entries, manifest, action, now)
        elif action.kind == "rm":
            self._apply_rm(entries, manifest, action, now)
        elif action.kind == "copy":
            self._apply_copy(entries, manifest, action)
        elif action.kind == "move":
            self._apply_move(entries, manifest, action, now)
        else:  # pragma: no cover - internal corruption guard
            raise RuntimeError(f"unknown Iroh mutation kind: {action.kind}")
        del preview

    def _ingest_mutation_source(self, source: Any) -> tuple[str, int]:
        if hasattr(source, "seek"):
            source.seek(0)
        store = self.get_blob_store()
        try:
            source_size = _source_size(source)
            multipart = next(
                (
                    getattr(store, name)
                    for name in ("ingest_parts", "ingest_multipart")
                    if callable(getattr(store, name, None))
                ),
                None,
            )
            if (
                multipart is not None
                and source_size is not None
                and source_size >= self.multipart_threshold
            ):
                parts = _iter_source_parts(source, self.multipart_part_size)
                result = _sync_result(
                    _call_ingest_parts(
                        multipart,
                        parts,
                        total_size=source_size,
                        part_size=self.multipart_part_size,
                    )
                )
            else:
                result = _sync_result(_call_required(store, "ingest", source))
        except OSError as exc:
            if isinstance(exc, IrohError):
                raise
            raise IrohIOError(
                "Iroh write staging or ingest failed", operation="filesystem.write"
            ) from exc
        digest = _result_field(result, "blob_hash", "hash")
        size = _result_field(result, "size")
        try:
            digest = _validate_hash(digest)
        except IrohInvalidHashError as exc:
            raise IrohIntegrityError(
                "Iroh blob ingest returned an invalid hash",
                operation="filesystem.write",
            ) from exc
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise IrohIntegrityError(
                "Iroh blob ingest returned an invalid size",
                operation="filesystem.write",
            )
        return digest, size

    def _apply_write(
        self,
        entries: dict[str, dict[str, Any]],
        manifest: Mapping[str, Any],
        action: _Mutation,
        digest: str,
        size: int,
        now: str,
    ) -> None:
        if action.path == "":
            raise IrohIsDirectoryError(
                "the Iroh namespace root is a directory", operation="filesystem.write"
            )
        parent = _require_parent(entries, action.path, "filesystem.write")
        self._require_manifest_write(manifest, parent, "filesystem.write")
        existing = _live_entry(entries, action.path)
        if existing is not None:
            if existing.get("kind") == "directory":
                raise IrohIsDirectoryError(
                    "Iroh write target is a directory", operation="filesystem.write"
                )
            if not action.overwrite:
                raise IrohAlreadyExistsError(
                    "Iroh write target already exists", operation="filesystem.write"
                )
            self._require_entry_write(existing, "filesystem.write")
        if existing is not None and action.mode is not None and action.mode != existing.get("mode"):
            raise IrohUnsupportedOperationError(
                "whole-file replacement cannot change an Iroh manifest mode",
                operation="filesystem.write",
            )
        file_mode = _validate_creation_mode(
            existing.get("mode") if existing is not None and action.mode is None else action.mode,
            kind="file",
        )
        metadata = _validate_metadata(
            existing.get("metadata") if existing is not None and action.metadata is None else action.metadata
        )
        entries[action.path] = {
            "path": action.path,
            "kind": "file",
            "tombstone": False,
            "blob_hash": digest,
            "size": size,
            "mode": file_mode,
            "mtime": now,
            "metadata": metadata,
        }

    def _apply_mkdir(
        self,
        entries: dict[str, dict[str, Any]],
        manifest: Mapping[str, Any],
        action: _Mutation,
        now: str,
    ) -> None:
        existing = _live_entry(entries, action.path)
        if existing is not None:
            if existing.get("kind") == "file" or not action.exist_ok:
                raise IrohAlreadyExistsError(
                    "Iroh directory target already exists", operation="filesystem.mkdir"
                )
            return
        if action.path == "":
            if action.exist_ok:
                return
            raise IrohAlreadyExistsError(
                "the Iroh namespace root already exists", operation="filesystem.mkdir"
            )
        segments = action.path.split("/")
        paths = ["/".join(segments[:index]) for index in range(1, len(segments) + 1)]
        if not action.create_parents:
            paths = paths[-1:]
        directory_mode = _validate_creation_mode(action.mode, kind="directory")
        for target in paths:
            current = _live_entry(entries, target)
            if current is not None:
                if current.get("kind") != "directory":
                    raise IrohNotDirectoryError(
                        "an Iroh directory path traverses a file",
                        operation="filesystem.mkdir",
                    )
                continue
            parent = _require_parent(entries, target, "filesystem.mkdir")
            self._require_manifest_write(manifest, parent, "filesystem.mkdir")
            entries[target] = {
                "path": target,
                "kind": "directory",
                "tombstone": False,
                "mode": directory_mode,
                "mtime": now,
                "metadata": {},
            }

    def _apply_rm(
        self,
        entries: dict[str, dict[str, Any]],
        manifest: Mapping[str, Any],
        action: _Mutation,
        now: str,
    ) -> None:
        requested = list(dict.fromkeys(action.source or [action.path]))
        planned: set[str] = set()
        for target in requested:
            if target == "":
                raise IrohPermissionDeniedError(
                    "the Iroh namespace root cannot be removed", operation="filesystem.rm"
                )
            entry = _live_entry(entries, target)
            if entry is None:
                raise IrohNotFoundError(
                    "Iroh removal target was not found", operation="filesystem.rm"
                )
            children = [
                path for path, candidate in entries.items()
                if _entry_is_live(candidate) and path.startswith(target + "/")
            ]
            if entry.get("kind") == "directory" and children and not action.recursive:
                raise IrohNotEmptyError(
                    "Iroh directory is not empty", operation="filesystem.rm"
                )
            planned.add(target)
            if action.recursive:
                planned.update(children)
        for target in sorted(planned, key=lambda item: (-item.count("/"), item.encode("utf-8"))):
            entry = entries[target]
            parent = _require_parent(entries, target, "filesystem.rm", planned=planned)
            self._require_manifest_write(manifest, parent, "filesystem.rm")
            self._require_entry_write(entry, "filesystem.rm")
            entries[target] = _tombstone(entry, now)

    def _copy_entries(
        self,
        entries: dict[str, dict[str, Any]],
        manifest: Mapping[str, Any],
        action: _Mutation,
    ) -> list[tuple[str, dict[str, Any]]]:
        assert action.destination is not None
        source_path = action.path
        if action.source.namespace_id == action.namespace_id:
            source_entries = entries
            source_manifest = manifest
        else:
            source_snapshot = self._load_manifest_snapshot(str(action.source.namespace_id))
            source_entries = _all_manifest_entries(source_snapshot.manifest)
            source_manifest = source_snapshot.manifest
        del source_manifest
        source = _live_entry(source_entries, source_path)
        if source is None:
            raise IrohNotFoundError(
                "Iroh copy source was not found", operation="filesystem.copy"
            )
        if source.get("kind") == "directory" and not action.recursive:
            raise IrohIsDirectoryError(
                "recursive mode is required to copy an Iroh directory",
                operation="filesystem.copy",
            )
        if source.get("kind") == "directory" and (
            source_path == ""
            or action.destination == source_path
            or action.destination.startswith(source_path + "/")
        ) and action.source.namespace_id == action.namespace_id:
            raise IrohInvalidPathError(
                "an Iroh directory cannot be copied below itself",
                operation="filesystem.copy",
            )
        selected = [(source_path, source)]
        if source.get("kind") == "directory":
            selected.extend(
                (path, entry)
                for path, entry in source_entries.items()
                if _entry_is_live(entry) and path.startswith(source_path + "/")
            )
        selected.sort(key=lambda item: item[0].encode("utf-8"))
        if action.source.namespace_id != action.namespace_id:
            for _path, entry in selected:
                if entry.get("kind") != "file":
                    continue
                size = self._blob_size(str(entry["blob_hash"]), fetch_options={})
                if size != entry.get("size"):
                    raise IrohIntegrityError(
                        "cross-namespace copy source has inconsistent blob metadata",
                        operation="filesystem.copy",
                    )
        planned: list[tuple[str, dict[str, Any]]] = []
        for old_path, entry in selected:
            suffix = old_path[len(source_path) :]
            new_path = action.destination + suffix
            _validate_manifest_path(new_path)
            planned.append((new_path, dict(entry)))
        return planned

    def _apply_copy(
        self,
        entries: dict[str, dict[str, Any]],
        manifest: Mapping[str, Any],
        action: _Mutation,
    ) -> None:
        planned = self._copy_entries(entries, manifest, action)
        assert action.destination is not None
        destination_existing = _live_entry(entries, action.destination)
        source_root = planned[0][1]
        if destination_existing is not None:
            if (
                not action.overwrite
                or destination_existing.get("kind") != "file"
                or source_root.get("kind") != "file"
            ):
                raise IrohAlreadyExistsError(
                    "Iroh copy destination already exists", operation="filesystem.copy"
                )
            self._require_entry_write(destination_existing, "filesystem.copy")
        for new_path, _entry in planned:
            collision = _live_entry(entries, new_path)
            if collision is not None and new_path != action.destination:
                raise IrohAlreadyExistsError(
                    "Iroh copy destination subtree collides with an existing entry",
                    operation="filesystem.copy",
                )
        parent = _require_parent(entries, action.destination, "filesystem.copy")
        self._require_manifest_write(manifest, parent, "filesystem.copy")
        for new_path, entry in planned:
            copied = dict(entry)
            copied["path"] = new_path
            entries[new_path] = copied

    def _apply_move(
        self,
        entries: dict[str, dict[str, Any]],
        manifest: Mapping[str, Any],
        action: _Mutation,
        now: str,
    ) -> None:
        if action.path == "":
            raise IrohPermissionDeniedError(
                "the Iroh namespace root cannot be moved", operation="filesystem.move"
            )
        if action.destination == action.path:
            return
        action.source = IrohPath(IROH_PROTOCOL, namespace_id=action.namespace_id, path=action.path)
        planned = self._copy_entries(entries, manifest, action)
        source_paths = [
            path for path, entry in entries.items()
            if _entry_is_live(entry)
            and (path == action.path or path.startswith(action.path + "/"))
        ]
        assert action.destination is not None
        destination_existing = _live_entry(entries, action.destination)
        if destination_existing is not None:
            if (
                not action.overwrite
                or destination_existing.get("kind") != "file"
                or planned[0][1].get("kind") != "file"
            ):
                raise IrohAlreadyExistsError(
                    "Iroh move destination already exists", operation="filesystem.move"
                )
        parent = _require_parent(entries, action.destination, "filesystem.move")
        self._require_manifest_write(manifest, parent, "filesystem.move")
        for new_path, _entry in planned:
            if new_path not in source_paths and _live_entry(entries, new_path) is not None:
                raise IrohAlreadyExistsError(
                    "Iroh move destination subtree collides with an existing entry",
                    operation="filesystem.move",
                )
        for new_path, entry in planned:
            moved = dict(entry)
            moved["path"] = new_path
            entries[new_path] = moved
        for old_path in sorted(source_paths, key=lambda value: -value.count("/")):
            self._require_entry_write(entries[old_path], "filesystem.move")
            entries[old_path] = _tombstone(entries[old_path], now)

    def _require_manifest_write(
        self, manifest: Mapping[str, Any], directory: Mapping[str, Any], operation: str
    ) -> None:
        permissions = manifest.get("permissions")
        if isinstance(permissions, Mapping):
            writer = self.writer_id or manifest.get("writer_id")
            writers = permissions.get("writers", ())
            owner = permissions.get("owner")
            if writer is None or (writer != owner and writer not in writers):
                raise IrohPermissionDeniedError(
                    "Iroh manifest ACL denies mutation", operation=operation
                )
        self._require_entry_write(directory, operation)

    @staticmethod
    def _require_entry_write(entry: Mapping[str, Any], operation: str) -> None:
        mode = entry.get("mode")
        if mode is not None and (not isinstance(mode, int) or mode & 0o200 == 0):
            raise IrohPermissionDeniedError(
                "Iroh manifest mode denies mutation", operation=operation
            )

    def _next_manifest(
        self,
        snapshot: _ManifestSnapshot,
        entries: Mapping[str, Mapping[str, Any]],
        now: str,
    ) -> dict[str, Any]:
        revision = snapshot.view.revision
        revision = 0 if revision is None else revision
        if revision >= 2**63 - 1:
            raise IrohConflictError(
                "Iroh manifest revision cannot be incremented",
                operation="filesystem.commit",
            )
        permissions = snapshot.manifest.get("permissions")
        if not isinstance(permissions, Mapping):
            identity = self.writer_id or snapshot.manifest.get("writer_id") or snapshot.view.namespace_id
            permissions = {
                "owner": identity,
                "public_read": False,
                "readers": [],
                "writers": [identity],
            }
        writer = self.writer_id or snapshot.manifest.get("writer_id") or permissions.get("owner")
        return {
            "schema_version": 1,
            "namespace_id": snapshot.view.namespace_id,
            "revision": revision + 1,
            "parent_revision": {"revision": revision, "manifest_hash": snapshot.head},
            "created_at": now,
            "writer_id": writer,
            "permissions": dict(permissions),
            "entries": [
                _complete_entry(dict(entries[path]), now)
                for path in sorted(entries, key=lambda item: item.encode("utf-8"))
            ],
        }

    def _compare_and_swap(
        self, namespace_id: str, expected_head: str, manifest: Mapping[str, Any]
    ) -> None:
        store = self.manifest_store
        methods = ("compare_and_swap", "cas_head", "commit_manifest", "publish_manifest")
        method = next((getattr(store, name, None) for name in methods if callable(getattr(store, name, None))), None)
        if method is not None:
            try:
                result = _sync_result(
                    _call_manifest_cas(method, namespace_id, expected_head, dict(manifest))
                )
            except OSError as exc:
                if isinstance(exc, IrohError):
                    raise
                raise IrohIOError(
                    "Iroh manifest commit result is unknown",
                    operation="filesystem.commit",
                ) from exc
        else:
            client = self.get_runtime_client()
            request = getattr(client, "request", None)
            if not callable(request):
                raise IrohUnavailableError(
                    "Iroh manifest store has no compare-and-swap operation",
                    operation="filesystem.commit",
                )
            try:
                result = _sync_result(
                    request(
                        "manifests.compare_and_swap",
                        {
                            "namespace_id": namespace_id,
                            "expected_head": expected_head,
                            "manifest": dict(manifest),
                        },
                    )
                )
            except OSError as exc:
                if isinstance(exc, IrohError):
                    raise
                raise IrohIOError(
                    "Iroh manifest commit result is unknown",
                    operation="filesystem.commit",
                ) from exc
        if result is False or (
            isinstance(result, Mapping)
            and any(result.get(key) is False for key in ("success", "committed", "swapped", "ok"))
        ):
            raise IrohConflictError(
                "Iroh namespace head compare-and-swap failed",
                operation="filesystem.commit",
            )

    # Fsspec's async protocol is also available from a registered
    # ``IrohFileSystem(asynchronous=True)`` instance.  Keeping these thin
    # proxies on the registered class preserves the mature synchronous public
    # surface while routing awaitable calls through one cached AnyIO adapter.
    async def _info(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.as_async()._info(path, **kwargs)

    async def _ls(self, path: str, detail: bool = True, **kwargs: Any) -> list[Any]:
        return await self.as_async()._ls(path, detail=detail, **kwargs)

    async def _exists(self, path: str, **kwargs: Any) -> bool:
        return await self.as_async()._exists(path, **kwargs)

    async def _isfile(self, path: str) -> bool:
        return await self.as_async()._isfile(path)

    async def _isdir(self, path: str) -> bool:
        return await self.as_async()._isdir(path)

    async def _find(self, path: str, **kwargs: Any) -> Any:
        return await self.as_async()._find(path, **kwargs)

    async def _glob(self, path: str, **kwargs: Any) -> Any:
        return await self.as_async()._glob(path, **kwargs)

    async def _cat_file(
        self,
        path: str,
        start: int | None = None,
        end: int | None = None,
        **kwargs: Any,
    ) -> bytes:
        return await self.as_async()._cat_file(
            path, start=start, end=end, **kwargs
        )

    async def _cat(self, path: Any, **kwargs: Any) -> Any:
        return await self.as_async()._cat(path, **kwargs)

    async def _cat_ranges(self, paths: Any, starts: Any, ends: Any, **kwargs: Any) -> Any:
        return await self.as_async()._cat_ranges(paths, starts, ends, **kwargs)

    async def _get_file(self, rpath: str, lpath: Any, **kwargs: Any) -> None:
        await self.as_async()._get_file(rpath, lpath, **kwargs)

    async def _pipe_file(self, path: str, value: Any, **kwargs: Any) -> None:
        await self.as_async()._pipe_file(path, value, **kwargs)

    async def _pipe(self, path: Any, value: bytes | None = None, **kwargs: Any) -> None:
        await self.as_async()._pipe(path, value, **kwargs)

    async def _put_file(self, lpath: Any, rpath: str, **kwargs: Any) -> None:
        await self.as_async()._put_file(lpath, rpath, **kwargs)

    async def _mkdir(self, path: str, **kwargs: Any) -> None:
        await self.as_async()._mkdir(path, **kwargs)

    async def _makedirs(self, path: str, exist_ok: bool = False) -> None:
        await self.as_async()._makedirs(path, exist_ok=exist_ok)

    async def _rm_file(self, path: str, **kwargs: Any) -> None:
        await self.as_async()._rm_file(path, **kwargs)

    async def _rm(self, path: Any, recursive: bool = False, **kwargs: Any) -> None:
        await self.as_async()._rm(path, recursive=recursive, **kwargs)

    async def _cp_file(self, path1: str, path2: str, **kwargs: Any) -> None:
        await self.as_async()._cp_file(path1, path2, **kwargs)

    async def _copy(
        self, path1: str, path2: str, recursive: bool = False, **kwargs: Any
    ) -> None:
        await self.as_async()._copy(path1, path2, recursive=recursive, **kwargs)

    async def _mv(
        self, path1: str, path2: str, recursive: bool = False, **kwargs: Any
    ) -> None:
        await self.as_async()._mv(path1, path2, recursive=recursive, **kwargs)

    async def open_async(
        self, path: str, mode: str = "rb", **kwargs: Any
    ) -> "IrohAsyncFile":
        return await self.as_async().open_async(path, mode=mode, **kwargs)


def _manifest_mapping(manifest: Any) -> dict[str, Any]:
    if isinstance(manifest, Mapping):
        return dict(manifest)
    fields = (
        "schema_version",
        "namespace_id",
        "revision",
        "parent_revision",
        "created_at",
        "writer_id",
        "permissions",
        "entries",
    )
    return {name: getattr(manifest, name) for name in fields if hasattr(manifest, name)}


def _extract_manifest_head(value: Any) -> str | None:
    candidates: list[Any] = []
    if isinstance(value, Mapping):
        candidates.extend(value.get(key) for key in ("head", "manifest_hash", "etag", "token"))
    else:
        candidates.extend(getattr(value, key, None) for key in ("head", "manifest_hash", "etag", "token"))
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            candidate = candidate.get("hash") or candidate.get("manifest_hash")
        if isinstance(candidate, str):
            try:
                return _validate_hash(candidate)
            except IrohInvalidHashError as exc:
                raise IrohIntegrityError(
                    "Iroh manifest store returned an invalid head token",
                    operation="filesystem.manifest",
                ) from exc
    return None


def _manifest_digest(manifest: Any) -> str:
    try:
        import blake3
    except (ImportError, ModuleNotFoundError):  # pragma: no cover - iroh extra is required
        raise IrohUnavailableError(
            "the Iroh filesystem requires the blake3 package",
            operation="filesystem.manifest",
        ) from None
    encoded = json.dumps(
        _manifest_mapping(manifest),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return blake3.blake3(encoded).hexdigest()


def _all_manifest_entries(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_entries = manifest.get("entries")
    if isinstance(raw_entries, Mapping):
        values: Sequence[Any] = [
            {"path": path, **_entry_mapping(entry)} for path, entry in raw_entries.items()
        ]
    elif isinstance(raw_entries, Sequence) and not isinstance(raw_entries, (str, bytes, bytearray)):
        values = raw_entries
    else:
        raise IrohInvalidManifestError(
            "manifest entries must be a sequence", operation="filesystem.manifest"
        )
    result: dict[str, dict[str, Any]] = {}
    for raw in values:
        entry = _entry_mapping(raw)
        path = entry.get("path")
        if not isinstance(path, str) or path in result:
            raise IrohInvalidManifestError(
                "manifest contains duplicate or invalid paths",
                operation="filesystem.manifest",
            )
        result[path] = entry
    return result


def _entry_is_live(entry: Mapping[str, Any] | None) -> bool:
    return entry is not None and entry.get("tombstone") is not True


def _live_entry(
    entries: Mapping[str, Mapping[str, Any]], path: str
) -> Mapping[str, Any] | None:
    entry = entries.get(path)
    return entry if _entry_is_live(entry) else None


def _require_parent(
    entries: Mapping[str, Mapping[str, Any]],
    path: str,
    operation: str,
    *,
    planned: set[str] | None = None,
) -> Mapping[str, Any]:
    del planned
    parent_path = path.rpartition("/")[0]
    parent = _live_entry(entries, parent_path)
    if parent is None:
        segments = path.split("/")[:-1]
        for index in range(1, len(segments) + 1):
            ancestor = _live_entry(entries, "/".join(segments[:index]))
            if ancestor is not None and ancestor.get("kind") != "directory":
                raise IrohNotDirectoryError(
                    "an Iroh path traverses a file", operation=operation
                )
        raise IrohNotFoundError(
            "Iroh parent directory was not found", operation=operation
        )
    if parent.get("kind") != "directory":
        raise IrohNotDirectoryError(
            "Iroh parent path is not a directory", operation=operation
        )
    return parent


def _validate_creation_mode(value: Any, *, kind: str) -> int:
    default = 0o755 if kind == "directory" else 0o644
    if value is None:
        return default
    allowed = {0o500, 0o555, 0o700, 0o755} if kind == "directory" else {
        0o400,
        0o444,
        0o600,
        0o644,
    }
    if isinstance(value, bool) or not isinstance(value, int) or value not in allowed:
        raise ValueError(f"unsupported Iroh {kind} mode")
    return value


def _validate_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("metadata must be a mapping")
    if len(value) > 64:
        raise ValueError("Iroh metadata has too many properties")
    forbidden = re.compile(
        r"(?:^|[_.-])(?:secret|token|ticket|password|credential|private_key|node_key)(?:$|[_.-])"
    )
    result: dict[str, Any] = {}
    for key, item in value.items():
        if (
            not isinstance(key, str)
            or re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", key) is None
            or forbidden.search(key)
        ):
            raise ValueError("Iroh metadata contains an invalid key")
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError("Iroh metadata values must be scalar")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Iroh metadata numbers must be finite")
        if isinstance(item, str) and len(item) > 4096:
            raise ValueError("Iroh metadata value is too long")
        result[key] = item
    return result


def _complete_entry(entry: dict[str, Any], now: str) -> dict[str, Any]:
    kind = entry.get("kind")
    entry.setdefault("tombstone", False)
    entry.setdefault("mode", 0o755 if kind == "directory" else 0o644)
    entry.setdefault("mtime", now)
    entry["metadata"] = _validate_metadata(entry.get("metadata"))
    if entry.get("tombstone") is True:
        entry.setdefault("deleted_at", now)
        entry.pop("blob_hash", None)
        entry.pop("size", None)
    else:
        entry.pop("deleted_at", None)
    return entry


def _tombstone(entry: Mapping[str, Any], now: str) -> dict[str, Any]:
    result = dict(entry)
    result["tombstone"] = True
    result["deleted_at"] = now
    result.pop("blob_hash", None)
    result.pop("size", None)
    return result


def _result_field(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _source_size(source: Any) -> int | None:
    """Return a staged source size without reading its contents."""

    if isinstance(source, (str, os.PathLike, Path)):
        try:
            return Path(source).stat().st_size
        except OSError:
            return None
    if not all(hasattr(source, name) for name in ("tell", "seek")):
        return None
    try:
        position = source.tell()
        source.seek(0, os.SEEK_END)
        size = source.tell()
        source.seek(position, os.SEEK_SET)
    except (OSError, ValueError, TypeError):
        return None
    return size if isinstance(size, int) and size >= 0 else None


def _iter_source_parts(source: Any, part_size: int) -> Iterator[bytes]:
    """Yield at most one upload part at a time to enforce producer backpressure."""

    handle = None
    if isinstance(source, (str, os.PathLike, Path)):
        handle = Path(source).open("rb")
        source = handle
    elif hasattr(source, "seek"):
        source.seek(0)
    try:
        while True:
            part = source.read(part_size)
            if not part:
                return
            if not isinstance(part, (bytes, bytearray, memoryview)):
                raise IrohIOError(
                    "Iroh multipart source returned non-bytes data",
                    operation="filesystem.write",
                )
            yield bytes(part)
    finally:
        if handle is not None:
            handle.close()


def _call_ingest_parts(
    method: Callable[..., Any],
    parts: Iterator[bytes],
    *,
    total_size: int,
    part_size: int,
) -> Any:
    """Call the common bounded-part ingest shapes without masking body errors."""

    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return method(parts)
    aliases = {
        "parts": parts,
        "chunks": parts,
        "source": parts,
        "total_size": total_size,
        "size": total_size,
        "part_size": part_size,
        "chunk_size": part_size,
    }
    kwargs = {name: aliases[name] for name in signature.parameters if name in aliases}
    try:
        signature.bind(**kwargs)
    except TypeError:
        return method(parts)
    return method(**kwargs)


def _call_manifest_cas(
    method: Callable[..., Any],
    namespace_id: str,
    expected_head: str,
    manifest: dict[str, Any],
) -> Any:
    """Call common manifest-store CAS spellings without masking body errors."""

    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return method(namespace_id, expected_head, manifest)
    aliases = {
        "namespace_id": namespace_id,
        "namespace": namespace_id,
        "expected_head": expected_head,
        "expected": expected_head,
        "head": expected_head,
        "manifest": manifest,
        "new_manifest": manifest,
        "value": manifest,
    }
    kwargs = {
        name: aliases[name]
        for name in signature.parameters
        if name in aliases
    }
    try:
        signature.bind(**kwargs)
    except TypeError:
        try:
            signature.bind(namespace_id, expected_head, manifest)
        except TypeError as exc:
            raise IrohUnavailableError(
                "Iroh manifest store has an incompatible compare-and-swap operation",
                operation="filesystem.commit",
            ) from exc
        return method(namespace_id, expected_head, manifest)
    else:
        return method(**kwargs)


def _overwrite_option(mode: Any, overwrite: Any) -> bool:
    if overwrite is not None:
        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean")
        return overwrite
    if mode in ("overwrite", "w", True):
        return True
    if mode in ("create", "exclusive", "x", False):
        return False
    raise ValueError("mode must be 'overwrite' or 'create'")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class _NoOpCallback:
    def set_size(self, size: int | None) -> None:
        del size

    def relative_update(self, size: int) -> None:
        del size


def _is_filelike(value: Any) -> bool:
    return hasattr(value, "write") and callable(value.write)


def _call_required(target: Any, name: str, *args: Any, **kwargs: Any) -> Any:
    method = getattr(target, name, None)
    if not callable(method):
        raise IrohUnavailableError(
            f"Iroh collaborator does not implement {name}",
            operation="filesystem.read",
        )
    return method(*args, **kwargs)


def _call_first(target: Any, names: Sequence[str], *args: Any) -> Any:
    for name in names:
        method = getattr(target, name, None)
        if callable(method):
            return method(*args)
    raise IrohUnavailableError(
        "Iroh manifest store has no head-read operation",
        operation="filesystem.manifest",
    )


async def _await_result(value: Any) -> Any:
    return await value


_FALLBACK_LOOP: asyncio.AbstractEventLoop | None = None
_FALLBACK_LOOP_LOCK = threading.Lock()


def _sync_result(value: Any) -> Any:
    """Resolve an optional awaitable on a stable background event loop."""

    if not inspect.isawaitable(value):
        return value
    try:
        from fsspec.asyn import get_loop, sync
    except (ImportError, ModuleNotFoundError):
        loop = _fallback_loop()
        return asyncio.run_coroutine_threadsafe(_await_result(value), loop).result()
    return sync(get_loop(), _await_result, value)


def _fallback_loop() -> asyncio.AbstractEventLoop:
    global _FALLBACK_LOOP
    with _FALLBACK_LOOP_LOCK:
        if _FALLBACK_LOOP is not None and _FALLBACK_LOOP.is_running():
            return _FALLBACK_LOOP
        ready = threading.Event()

        def run() -> None:
            global _FALLBACK_LOOP
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _FALLBACK_LOOP = loop
            ready.set()
            loop.run_forever()

        threading.Thread(target=run, name="iroh-fsspec-sync", daemon=True).start()
        ready.wait()
        assert _FALLBACK_LOOP is not None
        return _FALLBACK_LOOP


def _unwrap_manifest(value: Any) -> Any:
    """Accept manifest snapshots returned by the versioned-store public shapes."""

    if isinstance(value, Mapping):
        if "entries" in value:
            return value
        for key in ("manifest", "snapshot", "value"):
            if key in value:
                return _unwrap_manifest(value[key])
    if hasattr(value, "entries"):
        return value
    for attribute in ("manifest", "snapshot", "value"):
        nested = getattr(value, attribute, None)
        if nested is not None and nested is not value:
            try:
                return _unwrap_manifest(nested)
            except IrohInvalidManifestError:
                pass
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            try:
                return _unwrap_manifest(item)
            except IrohInvalidManifestError:
                continue
    raise IrohInvalidManifestError(
        "manifest store returned no directory manifest",
        operation="filesystem.manifest",
    )


def _manifest_field(manifest: Any, name: str, default: Any = None) -> Any:
    return manifest.get(name, default) if isinstance(manifest, Mapping) else getattr(
        manifest, name, default
    )


def _entry_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    fields = (
        "path",
        "kind",
        "tombstone",
        "blob_hash",
        "size",
        "mode",
        "mtime",
        "metadata",
        "deleted_at",
    )
    result = {name: getattr(value, name) for name in fields if hasattr(value, name)}
    if not result:
        raise IrohInvalidManifestError(
            "manifest contains a non-entry value", operation="filesystem.manifest"
        )
    return result


def _manifest_view(namespace_id: str, manifest: Any) -> _ManifestView:
    declared_namespace = _manifest_field(manifest, "namespace_id")
    if declared_namespace is not None and declared_namespace != namespace_id:
        raise IrohInvalidManifestError(
            "manifest namespace does not match the requested namespace",
            operation="filesystem.manifest",
        )
    revision = _manifest_field(manifest, "revision")
    if revision is not None and (
        isinstance(revision, bool) or not isinstance(revision, int) or revision < 0
    ):
        raise IrohInvalidManifestError(
            "manifest revision is invalid", operation="filesystem.manifest"
        )
    raw_entries = _manifest_field(manifest, "entries")
    if isinstance(raw_entries, Mapping):
        normalized_entries: list[Any] = []
        for entry_path, raw_entry in raw_entries.items():
            entry = _entry_mapping(raw_entry)
            entry.setdefault("path", entry_path)
            normalized_entries.append(entry)
        raw_entries = normalized_entries
    if not isinstance(raw_entries, Sequence) or isinstance(
        raw_entries, (str, bytes, bytearray)
    ):
        raise IrohInvalidManifestError(
            "manifest entries must be a sequence", operation="filesystem.manifest"
        )

    entries: dict[str, Mapping[str, Any]] = {}
    seen_paths: set[str] = set()
    for raw_entry in raw_entries:
        entry = _entry_mapping(raw_entry)
        path = entry.get("path")
        if not isinstance(path, str):
            raise IrohInvalidManifestError(
                "manifest contains an invalid entry path", operation="filesystem.manifest"
            )
        try:
            path = _validate_manifest_path(path)
        except IrohInvalidPathError as exc:
            raise IrohInvalidManifestError(
                "manifest contains an invalid entry path", operation="filesystem.manifest"
            ) from exc
        if path in seen_paths:
            raise IrohInvalidManifestError(
                "manifest contains duplicate paths", operation="filesystem.manifest"
            )
        seen_paths.add(path)
        kind = entry.get("kind")
        if kind not in {"file", "directory"}:
            raise IrohInvalidManifestError(
                "manifest entry has an invalid kind", operation="filesystem.manifest"
            )
        if entry.get("tombstone") is True:
            continue
        metadata = entry.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise IrohInvalidManifestError(
                "manifest entry metadata is invalid", operation="filesystem.manifest"
            )
        if kind == "file":
            try:
                entry["blob_hash"] = _validate_hash(entry.get("blob_hash"))
            except IrohInvalidHashError as exc:
                raise IrohInvalidManifestError(
                    "manifest file has an invalid blob hash", operation="filesystem.manifest"
                ) from exc
            size = entry.get("size")
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                raise IrohInvalidManifestError(
                    "manifest file has an invalid size", operation="filesystem.manifest"
                )
        entries[path] = entry

    root = entries.get("")
    if root is None or root.get("kind") != "directory":
        raise IrohInvalidManifestError(
            "manifest has no live root directory", operation="filesystem.manifest"
        )
    for path in entries:
        if not path:
            continue
        parent = path.rpartition("/")[0]
        if parent not in entries or entries[parent].get("kind") != "directory":
            raise IrohInvalidManifestError(
                "manifest contains an entry without a live directory parent",
                operation="filesystem.manifest",
            )
    return _ManifestView(namespace_id, revision, entries)


def _normalize_read_range(size: int, start: int | None, end: int | None) -> tuple[int, int]:
    for name, value in (("start", start), ("end", end)):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise TypeError(f"{name} must be an integer or None")
    begin = 0 if start is None else start
    stop = size if end is None else end
    if begin < 0:
        begin += size
    if stop < 0:
        stop += size
    begin = min(max(begin, 0), size)
    stop = min(max(stop, 0), size)
    return (begin, begin) if stop <= begin else (begin, stop)


def _validate_range_result(value: Any, expected: int, operation: str) -> bytes:
    """Accept only bytes-like, exactly sized results from a verified reader."""

    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise IrohIntegrityError(
            "Iroh blob reader returned non-bytes content",
            operation=operation,
        )
    result = bytes(value)
    if len(result) != expected:
        raise IrohIntegrityError(
            "Iroh blob reader returned an inconsistent range length",
            operation=operation,
        )
    return result


def _name_sort_key(name: str) -> bytes:
    parsed = parse_iroh_path(name)
    return (parsed.path if not parsed.is_blob else str(parsed.blob_hash)).encode("utf-8")


def _glob_translate(pattern: str) -> str:
    """Translate fsspec's slash-aware recursive glob grammar to a regex."""

    results: list[str] = []
    parts = pattern.split("/")
    last = len(parts) - 1
    for index, part in enumerate(parts):
        if part == "*":
            results.append("[^/]+" + ("/" if index < last else ""))
            continue
        if part == "**":
            results.append("(?:.+/)?" if index < last else ".*")
            continue
        if "**" in part:
            raise ValueError("Invalid pattern: '**' can only be an entire path component")
        results.extend(_translate_glob_component(part, "[^/]*", "[^/]"))
        if index < last:
            results.append("/")
    return rf"(?s:{''.join(results)})\Z"


def _translate_glob_component(pattern: str, star: str, question: str) -> list[str]:
    """Translate one shell-pattern component without allowing separators."""

    result: list[str] = []
    index, length = 0, len(pattern)
    while index < length:
        character = pattern[index]
        index += 1
        if character == "*":
            if not result or result[-1] != star:
                result.append(star)
        elif character == "?":
            result.append(question)
        elif character == "[":
            end = index
            if end < length and pattern[end] == "!":
                end += 1
            if end < length and pattern[end] == "]":
                end += 1
            while end < length and pattern[end] != "]":
                end += 1
            if end >= length:
                result.append(r"\[")
                continue
            content = pattern[index:end]
            index = end + 1
            if not content:
                result.append("(?!)")
                continue
            if content == "!":
                result.append(question)
                continue
            content = content.replace("\\", r"\\")
            content = re.sub(r"([&~|])", r"\\\1", content)
            if content.startswith("!"):
                content = "^" + content[1:]
            elif content.startswith(("^", "[")):
                content = "\\" + content
            result.append(f"[{content}]")
        else:
            result.append(re.escape(character))
    return result


def _blob_info(path: IrohPath, size: int) -> dict[str, Any]:
    digest = str(path.blob_hash)
    return {
        "name": path.canonical_url,
        "size": size,
        "type": "file",
        "blob_hash": digest,
    }


class IrohBufferedFile(AbstractBufferedFile):
    """Seekable fsspec handle backed by Iroh whole/ranged operation hooks.

    Reads are fetched on demand through ``cat_file``.  Writes use a private
    spooled staging file and publish only when the handle closes, matching the
    manifest commit model.  The actual storage operations live on the
    filesystem so sync and async implementations can share these mechanics.
    """

    _READ_MODES = frozenset({"rb"})
    _WRITE_MODES = frozenset({"wb", "xb"})

    def __init__(
        self,
        fs: IrohFileSystem,
        path: IrohPath | str,
        mode: str = "rb",
        block_size: int | None = None,
        autocommit: bool = True,
        cache_options: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        normalized_mode = mode if "b" in mode else mode + "b"
        if normalized_mode not in self._READ_MODES | self._WRITE_MODES:
            raise IrohUnsupportedOperationError(
                "Iroh files support only read, whole-file write, and exclusive-create modes",
                operation="filesystem.open",
            )
        self.fs = fs
        self._iroh_path = path if isinstance(path, IrohPath) else fs.parse_path(path)
        self.path = self._iroh_path.stripped_path
        self.mode = normalized_mode
        self.block_size = block_size or fs.blocksize
        # AbstractBufferedFile's line-oriented helpers use the historical
        # ``blocksize`` spelling. We deliberately do not call its constructor
        # because this reader has its own range and staging state.
        self.blocksize = self.block_size
        self.autocommit = bool(autocommit)
        self.cache_options = dict(cache_options or {})
        self.kwargs = dict(kwargs)
        self._closed = False
        self._position = 0
        self._size: int | None = None
        self._resolved_blob: str | None = None
        self._write_action: _Mutation | None = None
        self._transaction_registered = False
        self._staging = (
            tempfile.SpooledTemporaryFile(max_size=self.block_size, mode="w+b")
            if self.writable()
            else None
        )
        if self._staging is not None:
            namespace_id = str(self._iroh_path.namespace_id)
            try:
                self._write_action = _Mutation(
                    "write",
                    namespace_id,
                    self._iroh_path.path,
                    source=self._staging,
                    overwrite=self.mode != "xb",
                    mode=self.kwargs.pop("file_mode", self.kwargs.pop("permissions", None)),
                    metadata=self.kwargs.pop("metadata", None),
                    expected=fs._load_manifest_snapshot(namespace_id),
                )
            except BaseException:
                self._staging.close()
                self._closed = True
                raise
        has_read_backend = (
            fs.blob_store is not None
            or fs.client is not None
            or fs.client_factory is not None
        )
        if self.mode == "rb" and (
            (self._iroh_path.is_blob and has_read_backend)
            or (not self._iroh_path.is_blob and fs.manifest_store is not None)
        ):
            # Pin a namespace entry at open time. The selected immutable blob
            # remains stable even if the mutable head changes before read().
            self._resolve_reader()

    @property
    def name(self) -> str:
        return self._iroh_path.canonical_url

    @property
    def closed(self) -> bool:
        # AbstractBufferedFile.__del__ may inspect a partially initialized
        # object when mode validation rejected construction.
        return getattr(self, "_closed", True)

    @property
    def size(self) -> int:
        """Size of the snapshot addressed when this reader is first used."""

        self._check_open()
        return self._file_size()

    def readable(self) -> bool:
        return self.mode == "rb" and not self.closed

    def writable(self) -> bool:
        return self.mode in self._WRITE_MODES and not self.closed

    def seekable(self) -> bool:
        return not self.closed

    def tell(self) -> int:
        self._check_open()
        if self._staging is not None:
            return int(self._staging.tell())
        return self._position

    def read(self, size: int = -1) -> bytes:
        self._check_open()
        if not self.readable():
            raise io.UnsupportedOperation("file is not open for reading")
        blob_hash, file_size = self._resolve_reader()
        end = file_size if size is None or size < 0 else self._position + size
        begin, stop = _normalize_read_range(file_size, self._position, end)
        if begin == stop:
            return b""
        value = self.fs._read_blob_cached(
            blob_hash,
            begin,
            stop,
            blob_size=file_size,
            fetch_options=self.kwargs,
        )
        value = _validate_range_result(value, stop - begin, "filesystem.read")
        self._position += len(value)
        return value

    def readinto(self, buffer: Any) -> int:
        view = memoryview(buffer).cast("B")
        value = self.read(len(view))
        view[: len(value)] = value
        return len(value)

    def read1(self, size: int = -1) -> bytes:
        """Buffered-reader compatibility for text and compression wrappers."""

        return self.read(self.blocksize if size is None or size < 0 else size)

    def readall(self) -> bytes:
        return self.read()

    def readline(self, size: int = -1) -> bytes:
        """Read one line without materializing the remainder of the blob."""

        self._check_open()
        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("size must be an integer")
        if size == 0:
            return b""
        chunks: list[bytes] = []
        remaining = size
        while remaining != 0:
            amount = self.blocksize if remaining < 0 else min(self.blocksize, remaining)
            start = self.tell()
            chunk = self.read(amount)
            if not chunk:
                break
            newline = chunk.find(b"\n")
            if newline >= 0:
                used = newline + 1
                chunks.append(chunk[:used])
                if used < len(chunk):
                    self.seek(start + used)
                break
            chunks.append(chunk)
            if remaining > 0:
                remaining -= len(chunk)
        return b"".join(chunks)

    def readlines(self, hint: int = -1) -> list[bytes]:
        if isinstance(hint, bool) or not isinstance(hint, int):
            raise TypeError("hint must be an integer")
        lines: list[bytes] = []
        total = 0
        while True:
            line = self.readline()
            if not line:
                break
            lines.append(line)
            total += len(line)
            if hint > 0 and total >= hint:
                break
        return lines

    def __iter__(self) -> "IrohBufferedFile":
        return self

    def __next__(self) -> bytes:
        line = self.readline()
        if line:
            return line
        raise StopIteration

    def write(self, data: bytes | bytearray | memoryview) -> int:
        self._check_open()
        if not self.writable() or self._staging is None:
            raise io.UnsupportedOperation("file is not open for writing")
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("a bytes-like object is required")
        return int(self._staging.write(bytes(data)))

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        self._check_open()
        if not isinstance(offset, int) or isinstance(offset, bool):
            raise TypeError("offset must be an integer")
        if self._staging is not None:
            return int(self._staging.seek(offset, whence))
        if whence == os.SEEK_SET:
            target = offset
        elif whence == os.SEEK_CUR:
            target = self._position + offset
        elif whence == os.SEEK_END:
            target = self._file_size() + offset
        else:
            raise ValueError("invalid whence")
        if target < 0:
            raise ValueError("negative seek position")
        self._position = target
        return target

    def flush(self) -> None:
        self._check_open()
        if self._staging is not None:
            self._staging.flush()

    def close(self) -> None:
        if self.closed:
            return
        staging = self._staging
        try:
            if staging is not None and self.autocommit:
                staging.flush()
                assert self._write_action is not None
                self.fs._commit_actions(
                    [self._write_action], expected=self._write_action.expected
                )
        finally:
            if staging is not None and (self.autocommit or not self._transaction_registered):
                staging.close()
            self._closed = True

    def commit(self) -> None:
        """Commit a deferred writer (primarily for fsspec compatibility)."""

        if self._write_action is None:
            return
        if self._transaction_registered:
            return
        self.fs._commit_actions([self._write_action], expected=self._write_action.expected)
        self._finish_transaction(committed=True)

    def discard(self) -> None:
        """Close a staged writer without publishing it."""

        if self._staging is not None:
            self._staging.close()
        self._closed = True

    def _register_transaction(self, transaction: IrohTransaction) -> None:
        if self._write_action is None or self._transaction_registered:
            return
        transaction.add_action(self._write_action)
        self._transaction_registered = True

    def _finish_transaction(self, *, committed: bool) -> None:
        del committed
        if self._staging is not None and not self._staging.closed:
            self._staging.close()
        self._closed = True

    def __enter__(self) -> "IrohBufferedFile":
        self._check_open()
        return self

    def __exit__(self, exc_type: Any, exc: BaseException | None, traceback: Any) -> bool:
        if exc is not None and self.writable():
            self.discard()
        else:
            self.close()
        return False

    def _file_size(self) -> int:
        return self._resolve_reader()[1]

    def _resolve_reader(self) -> tuple[str, int]:
        if self._resolved_blob is None or self._size is None:
            self._resolved_blob, self._size = self.fs._resolve_blob(
                self._iroh_path, fetch_options=self.kwargs
            )
        return self._resolved_blob, self._size

    def _check_open(self) -> None:
        if self.closed:
            raise ValueError("I/O operation on closed file")


class IrohFile(IrohBufferedFile):
    """Buffered handle for a path in a mutable Iroh namespace."""

    def __init__(self, fs: IrohFileSystem, path: IrohPath | str, **kwargs: Any) -> None:
        parsed = path if isinstance(path, IrohPath) else fs.parse_path(path)
        if parsed.is_blob:
            raise IrohInvalidURLError(
                "namespace file handle requires an iroh path", operation="filesystem.open"
            )
        super().__init__(fs, parsed, **kwargs)


class IrohBlobFile(IrohBufferedFile):
    """Read-only buffered handle for an immutable Iroh blob."""

    def __init__(
        self,
        fs: IrohFileSystem,
        path: IrohPath | str,
        mode: str = "rb",
        **kwargs: Any,
    ) -> None:
        parsed = path if isinstance(path, IrohPath) else fs.parse_path(path)
        if not parsed.is_blob:
            raise IrohInvalidURLError(
                "blob file handle requires an iroh+blob path", operation="filesystem.open"
            )
        if mode not in {"r", "rb"}:
            raise IrohUnsupportedOperationError(
                "immutable Iroh blobs are read-only", operation="filesystem.open"
            )
        super().__init__(fs, parsed, mode="rb", **kwargs)


class IrohAsyncFileSystem(IrohFileSystem):
    """AnyIO-compatible fsspec adapter with bounded outstanding work.

    Fsspec's asynchronous convention uses underscore-prefixed coroutine
    methods.  This class implements those methods explicitly instead of
    relying on asyncio-only mirroring, so callers can use either asyncio or
    Trio through AnyIO.  Native async blob/manifest methods are awaited
    directly; synchronous collaborators and the shared mutation planner are
    moved to bounded worker threads.
    """

    async_impl: ClassVar[bool] = True
    mirror_sync_methods: ClassVar[bool] = False

    def __init__(
        self,
        *args: Any,
        asynchronous: bool = True,
        loop: Any = None,
        **kwargs: Any,
    ) -> None:
        del loop
        super().__init__(*args, **kwargs)
        self.asynchronous = bool(asynchronous)
        self._operation_limiter: Any = None
        self._pending_limiter: Any = None
        self._limiter_lock = threading.Lock()

    def _limiters(self) -> tuple[Any, Any]:
        # CapacityLimiterAdapter delays backend binding until first use.  The
        # lock only protects construction and is never held across an await.
        if self._operation_limiter is None or self._pending_limiter is None:
            with self._limiter_lock:
                if self._operation_limiter is None:
                    import anyio

                    self._operation_limiter = anyio.CapacityLimiter(
                        self.max_concurrency
                    )
                    self._pending_limiter = anyio.CapacityLimiter(
                        self.max_pending_operations
                    )
        return self._operation_limiter, self._pending_limiter

    async def _run_sync_call(
        self, function: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Run one blocking boundary with queue and execution backpressure."""

        import anyio

        operation_limiter, pending_limiter = self._limiters()
        call = partial(function, *args, **kwargs)
        async with pending_limiter:
            async with operation_limiter:
                return await anyio.to_thread.run_sync(call)

    async def _invoke_async(
        self, function: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Invoke a collaborator without blocking the active event-loop."""

        import anyio

        operation_limiter, pending_limiter = self._limiters()
        async with pending_limiter:
            async with operation_limiter:
                if inspect.iscoroutinefunction(function):
                    return await function(*args, **kwargs)
                value = await anyio.to_thread.run_sync(
                    partial(function, *args, **kwargs)
                )
                if inspect.isawaitable(value):
                    return await value
                return value

    async def _runtime_client_async(self) -> Any:
        return await self._run_sync_call(self.get_runtime_client)

    async def _blob_store_async(self) -> Any:
        return await self._run_sync_call(self.get_blob_store)

    async def _load_manifest_snapshot_async(
        self, namespace_id: str
    ) -> _ManifestSnapshot:
        store = self.manifest_store
        read_methods = (
            "read_head",
            "get_manifest",
            "load_manifest",
            "load",
            "read",
            "resolve",
            "get_current",
            "get_head",
            "get",
        )
        try:
            if store is None:
                client = await self._runtime_client_async()
                request = getattr(client, "request", None)
                if not callable(request):
                    raise IrohUnavailableError(
                        "an Iroh manifest store or runtime client is required",
                        operation="filesystem.manifest",
                    )
                value = await self._invoke_async(
                    request, "manifests.read", {"namespace_id": namespace_id}
                )
            elif isinstance(store, Mapping):
                value = store if "entries" in store else store[namespace_id]
            else:
                method = next(
                    (
                        getattr(store, name)
                        for name in read_methods
                        if callable(getattr(store, name, None))
                    ),
                    None,
                )
                if method is None:
                    value = store
                else:
                    value = await self._invoke_async(method, namespace_id)
        except KeyError:
            raise IrohNotFoundError(
                "Iroh namespace was not found", operation="filesystem.manifest"
            ) from None
        manifest = _unwrap_manifest(value)
        view = _manifest_view(namespace_id, manifest)
        head = _extract_manifest_head(value) or _manifest_digest(manifest)
        return _ManifestSnapshot(view, _manifest_mapping(manifest), head)

    async def _load_manifest_async(self, namespace_id: str) -> _ManifestView:
        return (await self._load_manifest_snapshot_async(namespace_id)).view

    async def _fetch_blob_async(
        self, blob_hash: str, options: Mapping[str, Any]
    ) -> None:
        if self.offline or not self.auto_fetch:
            raise IrohNotFoundError(
                "Iroh blob is not available in the local cache",
                operation="filesystem.read",
            )
        store = await self._blob_store_async()
        fetch = getattr(store, "fetch", None)
        if not callable(fetch):
            raise IrohNotFoundError(
                "Iroh blob is not available and the store cannot fetch it",
                operation="filesystem.read",
            )
        allowed = {
            "provider",
            "ticket",
            "timeout",
            "progress",
            "cancel",
            "cancellation_event",
        }
        selected = dict(self.fetch_options)
        nested = options.get("fetch_options")
        if nested is not None:
            if not isinstance(nested, Mapping):
                raise TypeError("fetch_options must be a mapping")
            selected.update(nested)
        selected.update({key: options[key] for key in allowed if key in options})
        await self._invoke_async(fetch, blob_hash, **selected)

    async def _blob_size_async(
        self, blob_hash: str, *, fetch_options: Mapping[str, Any]
    ) -> int:
        store = await self._blob_store_async()
        method = getattr(store, "stat", None)
        if not callable(method):
            raise IrohUnavailableError(
                "Iroh collaborator does not implement stat",
                operation="filesystem.read",
            )
        stat_options = {
            key: fetch_options[key] for key in ("timeout",) if key in fetch_options
        }
        try:
            value = await self._invoke_async(method, blob_hash, **stat_options)
        except (FileNotFoundError, IrohNotFoundError):
            await self._fetch_blob_async(blob_hash, fetch_options)
            value = await self._invoke_async(method, blob_hash, **stat_options)
        size = value.get("size") if isinstance(value, Mapping) else getattr(value, "size", None)
        complete = (
            value.get("complete", True)
            if isinstance(value, Mapping)
            else getattr(value, "complete", True)
        )
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise IrohIntegrityError(
                "Iroh blob store returned an invalid size",
                operation="filesystem.info",
            )
        if complete is not True:
            raise IrohIntegrityError(
                "Iroh blob store reported an incomplete blob",
                operation="filesystem.info",
            )
        return size

    async def _read_blob_range_async(
        self,
        blob_hash: str,
        start: int,
        end: int,
        *,
        fetch_options: Mapping[str, Any],
    ) -> Any:
        store = await self._blob_store_async()
        method = getattr(store, "read_range", None)
        if not callable(method):
            raise IrohUnavailableError(
                "Iroh collaborator does not implement read_range",
                operation="filesystem.read",
            )
        read_options = {
            key: fetch_options[key]
            for key in ("timeout", "progress", "cancel", "cancellation_event")
            if key in fetch_options
        }
        try:
            return await self._invoke_async(
                method, blob_hash, start=start, end=end, **read_options
            )
        except (FileNotFoundError, IrohNotFoundError):
            await self._fetch_blob_async(blob_hash, fetch_options)
            return await self._invoke_async(
                method, blob_hash, start=start, end=end, **read_options
            )

    async def _read_blob_cached_async(
        self,
        blob_hash: str,
        start: int,
        end: int,
        *,
        blob_size: int,
        fetch_options: Mapping[str, Any],
    ) -> bytes:
        if start >= end:
            return b""
        chunks: list[bytes] = []
        position = start
        while position < end:
            block_start = (position // self.read_ahead_size) * self.read_ahead_size
            block_end = min(block_start + self.read_ahead_size, blob_size)
            key = (blob_hash, block_start, block_end)
            block = self._range_cache.get(key)
            if block is None:
                value = await self._read_blob_range_async(
                    blob_hash,
                    block_start,
                    block_end,
                    fetch_options=fetch_options,
                )
                block = _validate_range_result(
                    value, block_end - block_start, "filesystem.read_ahead"
                )
                self._range_cache.put(key, block)
            take_start = position - block_start
            take_end = min(end, block_end) - block_start
            chunks.append(block[take_start:take_end])
            position = block_start + take_end
        return b"".join(chunks)

    async def _resolve_blob_async(
        self, parsed: IrohPath, *, fetch_options: Mapping[str, Any]
    ) -> tuple[str, int]:
        if parsed.is_blob:
            digest = str(parsed.blob_hash)
            return digest, await self._blob_size_async(
                digest, fetch_options=fetch_options
            )
        view = await self._load_manifest_async(str(parsed.namespace_id))
        entry = view.entry(parsed.path)
        if entry.get("kind") != "file":
            raise IsADirectoryError(parsed.canonical_url)
        return str(entry["blob_hash"]), int(entry["size"])

    async def _info(self, path: str, **kwargs: Any) -> dict[str, Any]:
        parsed = self.parse_path(path)
        if parsed.is_blob:
            size = await self._blob_size_async(
                str(parsed.blob_hash), fetch_options=kwargs
            )
            return _blob_info(parsed, size)
        view = await self._load_manifest_async(str(parsed.namespace_id))
        return self._entry_info(parsed, view.entry(parsed.path), view.revision)

    async def _ls(
        self, path: str, detail: bool = True, **kwargs: Any
    ) -> list[Any]:
        del kwargs
        parsed = self.parse_path(path)
        if parsed.is_blob:
            raise IrohUnsupportedOperationError(
                "immutable Iroh blobs do not provide directory listings",
                operation="filesystem.ls",
            )
        view = await self._load_manifest_async(str(parsed.namespace_id))
        requested = view.entry(parsed.path)
        if requested.get("kind") == "file":
            result = [self._entry_info(parsed, requested, view.revision)]
        else:
            prefix = f"{parsed.path}/" if parsed.path else ""
            result = []
            for entry_path, entry in view.entries.items():
                if entry_path == parsed.path or not entry_path.startswith(prefix):
                    continue
                if "/" in entry_path[len(prefix) :]:
                    continue
                child = IrohPath(
                    IROH_PROTOCOL,
                    namespace_id=parsed.namespace_id,
                    path=entry_path,
                )
                result.append(self._entry_info(child, entry, view.revision))
            result.sort(key=lambda item: _name_sort_key(item["name"]))
        return result if detail else [item["name"] for item in result]

    async def _exists(self, path: str, **kwargs: Any) -> bool:
        try:
            await self._info(path, **kwargs)
        except (FileNotFoundError, IrohNotFoundError):
            return False
        return True

    async def _isfile(self, path: str) -> bool:
        try:
            return (await self._info(path))["type"] == "file"
        except (FileNotFoundError, IrohNotFoundError):
            return False

    async def _isdir(self, path: str) -> bool:
        try:
            return (await self._info(path))["type"] == "directory"
        except (FileNotFoundError, IrohNotFoundError):
            return False

    async def _find(
        self,
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        detail: bool = False,
        **kwargs: Any,
    ) -> list[str] | dict[str, dict[str, Any]]:
        del kwargs
        if maxdepth is not None and (
            isinstance(maxdepth, bool) or not isinstance(maxdepth, int) or maxdepth < 1
        ):
            raise ValueError("maxdepth must be at least 1")
        parsed = self.parse_path(self._strip_protocol(path))
        if parsed.is_blob:
            raise IrohUnsupportedOperationError(
                "immutable Iroh blobs do not provide directory discovery",
                operation="filesystem.find",
            )
        view = await self._load_manifest_async(str(parsed.namespace_id))
        return self._find_in_view(parsed, view, maxdepth, withdirs, detail)

    async def _glob(
        self, path: str, maxdepth: int | None = None, **kwargs: Any
    ) -> list[str] | dict[str, dict[str, Any]]:
        if maxdepth is not None and (
            isinstance(maxdepth, bool) or not isinstance(maxdepth, int) or maxdepth < 1
        ):
            raise ValueError("maxdepth must be at least 1")
        detail = bool(kwargs.pop("detail", False))
        stripped = self._strip_protocol(path)
        parsed = self.parse_path(stripped)
        if parsed.is_blob:
            raise IrohUnsupportedOperationError(
                "immutable Iroh blobs do not provide directory discovery",
                operation="filesystem.glob",
            )
        view = await self._load_manifest_async(str(parsed.namespace_id))
        return self._glob_in_view(stripped, parsed, view, maxdepth, detail)

    async def _cat_file(
        self,
        path: str,
        start: int | None = None,
        end: int | None = None,
        **kwargs: Any,
    ) -> bytes:
        parsed = self.parse_path(path)
        blob_hash, size = await self._resolve_blob_async(
            parsed, fetch_options=kwargs
        )
        begin, stop = _normalize_read_range(size, start, end)
        value = await self._read_blob_cached_async(
            blob_hash,
            begin,
            stop,
            blob_size=size,
            fetch_options=kwargs,
        )
        return _validate_range_result(
            value, stop - begin, "filesystem.cat_file"
        )

    async def _gather_ordered(
        self, calls: Sequence[Callable[[], Any]], *, return_exceptions: bool = False
    ) -> list[Any]:
        import anyio

        results: list[Any] = [None] * len(calls)

        async def run(index: int, call: Callable[[], Any]) -> None:
            try:
                results[index] = await call()
            except Exception as exc:
                if not return_exceptions:
                    raise
                results[index] = exc

        async with anyio.create_task_group() as group:
            for index, call in enumerate(calls):
                group.start_soon(run, index, call)
        return results

    async def _cat(
        self,
        path: str | Sequence[str],
        recursive: bool = False,
        on_error: str = "raise",
        **kwargs: Any,
    ) -> bytes | dict[str, bytes | Exception]:
        if on_error not in {"raise", "omit", "return"}:
            raise ValueError("on_error must be 'raise', 'omit', or 'return'")
        if recursive or (isinstance(path, str) and globlib.has_magic(path)):
            return await self._run_sync_call(
                IrohFileSystem.cat,
                self,
                path,
                recursive=recursive,
                on_error=on_error,
                **kwargs,
            )
        if isinstance(path, str):
            return await self._cat_file(path, **kwargs)
        names = list(path)
        calls = [partial(self._cat_file, name, **kwargs) for name in names]
        values = await self._gather_ordered(calls, return_exceptions=True)
        output: dict[str, bytes | Exception] = {}
        for name, value in zip(names, values):
            if isinstance(value, Exception):
                if on_error == "raise":
                    raise value
                if on_error == "omit":
                    continue
            output[self.parse_path(name).canonical_url] = value
        return output

    async def _cat_ranges(
        self,
        paths: Sequence[str],
        starts: Sequence[int | None] | int | None,
        ends: Sequence[int | None] | int | None,
        **kwargs: Any,
    ) -> list[Any]:
        if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)):
            raise TypeError("paths must be a sequence")
        starts_list = (
            list(starts)
            if isinstance(starts, Sequence) and not isinstance(starts, (str, bytes))
            else [starts] * len(paths)
        )
        ends_list = (
            list(ends)
            if isinstance(ends, Sequence) and not isinstance(ends, (str, bytes))
            else [ends] * len(paths)
        )
        if len(starts_list) != len(paths) or len(ends_list) != len(paths):
            raise ValueError("range lists must have the same length as paths")
        calls = [
            partial(self._cat_file, path, start=start, end=end, **kwargs)
            for path, start, end in zip(paths, starts_list, ends_list)
        ]
        return await self._gather_ordered(calls, return_exceptions=True)

    async def _get_file(self, rpath: str, lpath: Any, **kwargs: Any) -> None:
        await self._run_sync_call(
            IrohFileSystem.get_file, self, rpath, lpath, **kwargs
        )

    async def _pipe_file(self, path: str, value: Any, **kwargs: Any) -> None:
        await self._run_sync_call(
            IrohFileSystem.pipe_file, self, path, value, **kwargs
        )

    async def _pipe(
        self, path: str | Mapping[str, bytes], value: bytes | None = None, **kwargs: Any
    ) -> None:
        # A mapping intentionally crosses the worker boundary as one call: the
        # synchronous planner stages all blobs and publishes one manifest CAS.
        await self._run_sync_call(
            IrohFileSystem.pipe, self, path, value, **kwargs
        )

    async def _put_file(self, lpath: Any, rpath: str, **kwargs: Any) -> None:
        await self._run_sync_call(
            IrohFileSystem.put_file, self, lpath, rpath, **kwargs
        )

    async def _mkdir(self, path: str, **kwargs: Any) -> None:
        await self._run_sync_call(IrohFileSystem.mkdir, self, path, **kwargs)

    async def _makedirs(self, path: str, exist_ok: bool = False) -> None:
        await self._run_sync_call(
            IrohFileSystem.makedirs, self, path, exist_ok=exist_ok
        )

    async def _rm_file(self, path: str, **kwargs: Any) -> None:
        await self._run_sync_call(
            IrohFileSystem.rm, self, path, recursive=False, **kwargs
        )

    async def _rm(
        self, path: str | Sequence[str], recursive: bool = False, **kwargs: Any
    ) -> None:
        await self._run_sync_call(
            IrohFileSystem.rm, self, path, recursive=recursive, **kwargs
        )

    async def _cp_file(self, path1: str, path2: str, **kwargs: Any) -> None:
        await self._run_sync_call(
            IrohFileSystem.cp_file, self, path1, path2, **kwargs
        )

    async def _copy(
        self, path1: str, path2: str, recursive: bool = False, **kwargs: Any
    ) -> None:
        await self._run_sync_call(
            IrohFileSystem.copy,
            self,
            path1,
            path2,
            recursive=recursive,
            **kwargs,
        )

    async def _mv(
        self, path1: str, path2: str, recursive: bool = False, **kwargs: Any
    ) -> None:
        await self._run_sync_call(
            IrohFileSystem.mv,
            self,
            path1,
            path2,
            recursive=recursive,
            **kwargs,
        )

    async def open_async(
        self, path: str, mode: str = "rb", **kwargs: Any
    ) -> "IrohAsyncFile":
        return await IrohAsyncFile.create(self, path, mode=mode, **kwargs)


class IrohAsyncFile:
    """Seekable asynchronous Iroh reader and staged whole-file writer."""

    def __init__(
        self,
        fs: IrohAsyncFileSystem,
        path: IrohPath,
        mode: str,
        block_size: int,
        kwargs: Mapping[str, Any],
    ) -> None:
        self.fs = fs
        self._iroh_path = path
        self.path = path.stripped_path
        self.name = path.canonical_url
        self.mode = mode
        self.blocksize = block_size
        self.kwargs = dict(kwargs)
        self._position = 0
        self._resolved_blob: str | None = None
        self._size: int | None = None
        self._staging: Any = None
        self._write_action: _Mutation | None = None
        self.closed = False

    @classmethod
    async def create(
        cls,
        fs: IrohAsyncFileSystem,
        path: str,
        *,
        mode: str = "rb",
        block_size: int | None = None,
        **kwargs: Any,
    ) -> "IrohAsyncFile":
        normalized = mode if "b" in mode else mode + "b"
        if normalized not in {"rb", "wb", "xb"}:
            raise IrohUnsupportedOperationError(
                "Iroh files support only read, whole-file write, and exclusive-create modes",
                operation="filesystem.open",
            )
        parsed = fs.parse_path(path)
        if parsed.is_blob and normalized != "rb":
            raise IrohUnsupportedOperationError(
                "immutable Iroh blobs are read-only", operation="filesystem.open"
            )
        handle = cls(fs, parsed, normalized, block_size or fs.blocksize, kwargs)
        if normalized == "rb":
            handle._resolved_blob, handle._size = await fs._resolve_blob_async(
                parsed, fetch_options=handle.kwargs
            )
        else:
            fs._mutable_path(path, "filesystem.open")
            import anyio

            handle._staging = await anyio.to_thread.run_sync(
                partial(
                    tempfile.SpooledTemporaryFile,
                    max_size=handle.blocksize,
                    mode="w+b",
                )
            )
            try:
                snapshot = await fs._load_manifest_snapshot_async(
                    str(parsed.namespace_id)
                )
                handle._write_action = _Mutation(
                    "write",
                    str(parsed.namespace_id),
                    parsed.path,
                    source=handle._staging,
                    overwrite=normalized != "xb",
                    mode=handle.kwargs.pop(
                        "file_mode", handle.kwargs.pop("permissions", None)
                    ),
                    metadata=handle.kwargs.pop("metadata", None),
                    expected=snapshot,
                )
            except BaseException:
                await anyio.to_thread.run_sync(handle._staging.close)
                handle.closed = True
                raise
        return handle

    @property
    def size(self) -> int:
        if self._size is None:
            raise ValueError("writer handles do not have a committed size")
        return self._size

    def readable(self) -> bool:
        return self.mode == "rb" and not self.closed

    def writable(self) -> bool:
        return self.mode in {"wb", "xb"} and not self.closed

    def tell(self) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        if self._staging is not None:
            return int(self._staging.tell())
        return self._position

    async def read(self, size: int = -1) -> bytes:
        if not self.readable():
            raise io.UnsupportedOperation("file is not open for reading")
        assert self._resolved_blob is not None and self._size is not None
        end = self._size if size is None or size < 0 else self._position + size
        begin, stop = _normalize_read_range(self._size, self._position, end)
        value = await self.fs._read_blob_cached_async(
            self._resolved_blob,
            begin,
            stop,
            blob_size=self._size,
            fetch_options=self.kwargs,
        )
        self._position += len(value)
        return value

    async def write(self, data: bytes | bytearray | memoryview) -> int:
        if not self.writable() or self._staging is None:
            raise io.UnsupportedOperation("file is not open for writing")
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("a bytes-like object is required")
        return int(await self.fs._run_sync_call(self._staging.write, data))

    async def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("offset must be an integer")
        if self._staging is not None:
            return int(
                await self.fs._run_sync_call(self._staging.seek, offset, whence)
            )
        if whence == os.SEEK_SET:
            target = offset
        elif whence == os.SEEK_CUR:
            target = self._position + offset
        elif whence == os.SEEK_END:
            assert self._size is not None
            target = self._size + offset
        else:
            raise ValueError("invalid whence")
        if target < 0:
            raise ValueError("negative seek position")
        self._position = target
        return target

    async def flush(self) -> None:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        if self._staging is not None:
            await self.fs._run_sync_call(self._staging.flush)

    async def discard(self) -> None:
        if self._staging is not None and not self._staging.closed:
            await self.fs._run_sync_call(self._staging.close)
        self.closed = True

    async def close(self) -> None:
        if self.closed:
            return
        if self._staging is None:
            self.closed = True
            return
        import anyio

        try:
            await self.flush()
            assert self._write_action is not None
            # Once CAS starts, wait for its known result before reporting
            # cancellation; this avoids an apparently cancelled committed write.
            with anyio.CancelScope(shield=True):
                await self.fs._run_sync_call(
                    self.fs._commit_actions,
                    [self._write_action],
                    expected=self._write_action.expected,
                )
        finally:
            if not self._staging.closed:
                await self.fs._run_sync_call(self._staging.close)
            self.closed = True

    async def __aenter__(self) -> "IrohAsyncFile":
        if self.closed:
            raise ValueError("I/O operation on closed file")
        return self

    async def __aexit__(
        self, exc_type: Any, exc: BaseException | None, traceback: Any
    ) -> bool:
        del exc_type, traceback
        if exc is not None and self.writable():
            await self.discard()
        else:
            await self.close()
        return False


def register_iroh_filesystems() -> tuple[str, str]:
    """Register both protocols with active and vendored fsspec registries.

    Registration is idempotent.  Supporting the vendored registry even when
    external fsspec is installed keeps explicit fallback consumers consistent
    and does not import, configure, or start the Iroh sidecar.
    """

    registries: list[Any] = [_fsspec]
    try:
        from ipfs_kit_py._vendor import fsspec as vendored_fsspec
    except (ImportError, ModuleNotFoundError):  # pragma: no cover - package corruption only
        vendored_fsspec = None
    if vendored_fsspec is not None and vendored_fsspec is not _fsspec:
        registries.append(vendored_fsspec)

    for registry in registries:
        for name in IROH_PROTOCOLS:
            _register_implementation(registry, name, IrohFileSystem)
    return IROH_PROTOCOLS


def _register_implementation(registry: Any, name: str, implementation: type[Any]) -> None:
    register = registry.register_implementation
    try:
        register(name, implementation, clobber=True)
    except TypeError:
        # The bundled compatibility registry intentionally implements an older
        # two-argument fsspec API.
        try:
            existing = registry.get_filesystem_class(name)
        except KeyError:
            register(name, implementation)
        else:
            if existing is not implementation:
                raise ValueError(f"filesystem protocol {name!r} is already registered")


def _validate_protocol(value: str) -> str:
    if not isinstance(value, str) or value.lower() not in IROH_PROTOCOLS:
        raise ValueError(f"protocol must be one of {IROH_PROTOCOLS!r}")
    return value.lower()


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _validate_namespace(value: str) -> str:
    if not isinstance(value, str) or _HEX_32.fullmatch(value) is None:
        raise IrohInvalidURLError(
            "Iroh namespace identifier must be exactly 64 lowercase hexadecimal characters",
            operation="filesystem.parse_url",
        )
    return value


def _validate_hash(value: str) -> str:
    if not isinstance(value, str) or _HEX_32.fullmatch(value) is None:
        raise IrohInvalidHashError(
            "Iroh blob hash must be exactly 64 lowercase hexadecimal characters",
            operation="filesystem.parse_url",
        )
    return value


def _decode_url_path(raw_path: str) -> str:
    if not raw_path.startswith("/"):
        raise IrohInvalidURLError(
            "Iroh namespace URLs require a slash after the authority",
            operation="filesystem.parse_url",
        )
    encoded = raw_path[1:]
    if not encoded:
        return ""
    if encoded.endswith("/") or _BAD_PERCENT.search(encoded):
        raise IrohInvalidPathError(
            "Iroh URL contains an invalid path", operation="filesystem.parse_url"
        )

    segments: list[str] = []
    for encoded_segment in encoded.split("/"):
        if not encoded_segment or _ENCODED_SEPARATOR_OR_CONTROL.search(encoded_segment):
            raise IrohInvalidPathError(
                "Iroh URL contains an invalid path segment", operation="filesystem.parse_url"
            )
        try:
            segment = unquote_to_bytes(encoded_segment).decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise IrohInvalidPathError(
                "Iroh URL path is not valid UTF-8", operation="filesystem.parse_url"
            ) from exc
        _validate_segment(segment)
        segments.append(segment)
    return _validate_manifest_path("/".join(segments))


def _validate_manifest_path(path: str) -> str:
    if not path:
        return ""
    if path.startswith("/") or path.endswith("/"):
        raise IrohInvalidPathError(
            "Iroh manifest paths are relative", operation="filesystem.parse_url"
        )
    segments = path.split("/")
    for segment in segments:
        _validate_segment(segment)
    if len(path.encode("utf-8")) > 4096:
        raise IrohInvalidPathError(
            "Iroh manifest path exceeds 4096 UTF-8 bytes", operation="filesystem.parse_url"
        )
    return path


def _validate_segment(segment: str) -> None:
    if (
        not segment
        or segment in {".", ".."}
        or unicodedata.normalize("NFC", segment) != segment
        or "/" in segment
        or "\\" in segment
        or any(ord(character) < 32 or ord(character) == 127 for character in segment)
        or any(0xD800 <= ord(character) <= 0xDFFF for character in segment)
        or len(segment.encode("utf-8")) > 255
    ):
        raise IrohInvalidPathError(
            "Iroh URL contains an invalid path segment", operation="filesystem.parse_url"
        )


def _quote_path(path: str) -> str:
    unreserved = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    encoded: list[str] = []
    for byte in path.encode("utf-8"):
        if byte in unreserved or byte == ord("/"):
            encoded.append(chr(byte))
        else:
            encoded.append(f"%{byte:02X}")
    return "".join(encoded)


# Source checkouts do not have installed entry-point metadata, so perform the
# same harmless in-process registration on import.  Installed distributions
# also advertise both protocols through ``fsspec.specs`` entry points.
register_iroh_filesystems()


__all__ = [
    "IROH_PROTOCOL",
    "IROH_BLOB_PROTOCOL",
    "IROH_PROTOCOLS",
    "DEFAULT_BLOCK_SIZE",
    "DEFAULT_MAX_CONCURRENCY",
    "DEFAULT_MAX_PENDING_OPERATIONS",
    "DEFAULT_RANGE_CACHE_SIZE",
    "DEFAULT_MULTIPART_THRESHOLD",
    "DEFAULT_MULTIPART_PART_SIZE",
    "USING_VENDORED_FSSPEC",
    "IrohPath",
    "parse_iroh_path",
    "IrohFileSystem",
    "IrohBufferedFile",
    "IrohFile",
    "IrohBlobFile",
    "IrohAsyncFileSystem",
    "IrohAsyncFile",
    "register_iroh_filesystems",
]
