"""fsspec wrapper hooks for VFS GraphRAG indexing.

The wrapper in this module decorates an existing fsspec-compatible filesystem
without changing that backend class.  It emits lightweight indexing events for
mutating and discovery operations, and can synchronously upsert canonical
``VFSObjectRecord`` metadata into ``VFSGraphRAGIndex`` when requested.
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .vfs_graphrag_index import VFSGraphRAGIndex
from .vfs_graphrag_schema import DEFAULT_NAMESPACE, VFSObjectRecord, normalize_vfs_path, utc_now_iso


_WRITE_MODE_MARKERS = ("w", "a", "x", "+")


@dataclass
class VFSIndexingEvent:
    """Structured event emitted by ``IndexedVFSFileSystem`` hooks."""

    operation: str
    path: Optional[str] = None
    destination_path: Optional[str] = None
    namespace: str = DEFAULT_NAMESPACE
    backend: str = "fsspec"
    protocol: str = "file"
    timestamp: str = field(default_factory=utc_now_iso)
    info: Optional[Dict[str, Any]] = None
    content: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "path": self.path,
            "destination_path": self.destination_path,
            "namespace": self.namespace,
            "backend": self.backend,
            "protocol": self.protocol,
            "timestamp": self.timestamp,
            "info": self.info,
            "content": self.content,
            "metadata": dict(self.metadata),
        }


class IndexedVFSFileSystem:
    """Decorate any fsspec filesystem with VFS GraphRAG indexing hooks.

    Parameters:
        fs: Wrapped fsspec-compatible filesystem.
        indexer: Either an event queue/processor or ``VFSGraphRAGIndex``.
        namespace: Canonical namespace stored on emitted records and events.
        backend: Optional backend label.  Defaults to the wrapped protocol.
        synchronous_indexing: When true, perform lightweight metadata indexing
            immediately.  Otherwise, enqueue the event when the indexer exposes
            ``enqueue``/``put``/``append`` and always retain it in ``events``.
        index_read_through: Emit read-through events for ``cat_file`` and read
            handles returned from ``open``.
        enrich_listings: Attach matching index metadata to ``info``/``ls``
            dictionary results when a local ``VFSGraphRAGIndex`` is available.
    """

    def __init__(
        self,
        fs: Any,
        *,
        indexer: Optional[Any] = None,
        namespace: str = DEFAULT_NAMESPACE,
        backend: Optional[str] = None,
        synchronous_indexing: bool = False,
        index_read_through: bool = False,
        enrich_listings: bool = True,
    ) -> None:
        self.fs = fs
        self.indexer = indexer
        self.namespace = namespace
        self.protocol = _protocol_label(getattr(fs, "protocol", None))
        self.backend = backend or getattr(fs, "backend", None) or self.protocol or "fsspec"
        self.synchronous_indexing = synchronous_indexing
        self.index_read_through = index_read_through
        self.enrich_listings = enrich_listings
        self.events: List[VFSIndexingEvent] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.fs, name)

    def put_file(self, lpath: str, rpath: str, *args: Any, **kwargs: Any) -> Any:
        result = self.fs.put_file(lpath, rpath, *args, **kwargs)
        self._emit("write", rpath, metadata={"source_path": lpath, "method": "put_file"})
        return result

    def pipe_file(self, path: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        result = self.fs.pipe_file(path, value, *args, **kwargs)
        content = _coerce_bytes(value)
        self._emit("write", path, content=content, metadata={"method": "pipe_file"})
        return result

    def open(self, path: str, mode: str = "rb", *args: Any, **kwargs: Any) -> Any:
        handle = self.fs.open(path, mode=mode, *args, **kwargs)
        should_index_write = any(marker in mode for marker in _WRITE_MODE_MARKERS)
        should_index_read = self.index_read_through and "r" in mode and not should_index_write
        if not should_index_write and not should_index_read:
            return handle
        operation = "write" if should_index_write else "read"
        return _IndexedFileHandle(self, handle, path, operation, {"method": "open", "mode": mode})

    def rm(self, path: Any, *args: Any, **kwargs: Any) -> Any:
        result = self.fs.rm(path, *args, **kwargs)
        for item in _iter_paths(path):
            self._emit("delete", item, metadata={"method": "rm"})
        return result

    def rm_file(self, path: str, *args: Any, **kwargs: Any) -> Any:
        remover = getattr(self.fs, "rm_file", self.fs.rm)
        result = remover(path, *args, **kwargs)
        self._emit("delete", path, metadata={"method": "rm_file"})
        return result

    def delete(self, path: Any, *args: Any, **kwargs: Any) -> Any:
        deleter = getattr(self.fs, "delete", self.fs.rm)
        result = deleter(path, *args, **kwargs)
        for item in _iter_paths(path):
            self._emit("delete", item, metadata={"method": "delete"})
        return result

    def mv(self, path1: str, path2: str, *args: Any, **kwargs: Any) -> Any:
        result = self.fs.mv(path1, path2, *args, **kwargs)
        self._emit("move", path1, destination_path=path2, metadata={"method": "mv"})
        return result

    def info(self, path: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        result = self.fs.info(path, *args, **kwargs)
        self._emit("info", path, info=dict(result), metadata={"method": "info"})
        return self._enrich_info(dict(result))

    def ls(self, path: str, detail: bool = True, *args: Any, **kwargs: Any) -> Any:
        result = self.fs.ls(path, detail=detail, *args, **kwargs)
        entries = result if detail else [{"name": item} for item in result]
        self._emit("list", path, info={"entries": entries}, metadata={"method": "ls", "detail": detail})
        if not detail:
            return result
        return [self._enrich_info(dict(entry)) for entry in result]

    def cat_file(self, path: str, *args: Any, **kwargs: Any) -> Any:
        result = self.fs.cat_file(path, *args, **kwargs)
        if self.index_read_through:
            self._emit("read", path, content=_coerce_bytes(result), metadata={"method": "cat_file"})
        return result

    def drain_events(self) -> List[VFSIndexingEvent]:
        """Return and clear events retained by this wrapper."""

        events = list(self.events)
        self.events.clear()
        return events

    def _emit(
        self,
        operation: str,
        path: Optional[str],
        *,
        destination_path: Optional[str] = None,
        info: Optional[Dict[str, Any]] = None,
        content: Optional[bytes] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> VFSIndexingEvent:
        if info is None and path is not None:
            info = self._safe_info(path)
        event = VFSIndexingEvent(
            operation=operation,
            path=path,
            destination_path=destination_path,
            namespace=self.namespace,
            backend=str(self.backend),
            protocol=str(self.protocol or self.backend),
            info=info,
            content=content,
            metadata=dict(metadata or {}),
        )
        self.events.append(event)
        if self.synchronous_indexing:
            self._perform_indexing(event)
        else:
            self._enqueue(event)
        return event

    def _enqueue(self, event: VFSIndexingEvent) -> None:
        if self.indexer is None or isinstance(self.indexer, VFSGraphRAGIndex):
            return
        for name in ("enqueue", "put", "append"):
            method = getattr(self.indexer, name, None)
            if callable(method):
                method(event)
                return

    def _perform_indexing(self, event: VFSIndexingEvent) -> None:
        if self.indexer is None:
            return
        for name in ("index_event", "handle_event", "process_event"):
            method = getattr(self.indexer, name, None)
            if callable(method):
                method(event)
                return
        if isinstance(self.indexer, VFSGraphRAGIndex) or hasattr(self.indexer, "upsert_object"):
            self._upsert_event_records(event)

    def _upsert_event_records(self, event: VFSIndexingEvent) -> None:
        if event.operation == "move" and event.destination_path:
            destination_info = self._safe_info(event.destination_path)
            self._upsert_object(
                event.destination_path,
                destination_info,
                {"event": event.operation, "source_path": event.path, **event.metadata},
            )
            self._upsert_object(event.path, None, {"event": "delete", "destination_path": event.destination_path})
            return
        if event.operation == "delete":
            self._upsert_object(event.path, event.info, {"event": "delete", **event.metadata}, object_type="tombstone")
            return
        if event.operation in {"write", "read", "info", "list"} and event.path is not None:
            object_type = "directory" if event.operation == "list" else None
            self._upsert_object(event.path, event.info, {"event": event.operation, **event.metadata}, object_type=object_type)

    def _upsert_object(
        self,
        path: Optional[str],
        info: Optional[Mapping[str, Any]],
        metadata: Mapping[str, Any],
        *,
        object_type: Optional[str] = None,
    ) -> None:
        if path is None:
            return
        record = self._record_from_info(path, info, metadata=metadata, object_type=object_type)
        self.indexer.upsert_object(record)

    def _record_from_info(
        self,
        path: str,
        info: Optional[Mapping[str, Any]],
        *,
        metadata: Mapping[str, Any],
        object_type: Optional[str] = None,
    ) -> VFSObjectRecord:
        info = dict(info or {})
        record_path = str(info.get("name") or info.get("path") or path)
        size = info.get("size", 0) or 0
        content_id = _first_present(info, "content_id", "cid", "hash", "etag", "checksum")
        mime_type = info.get("mime_type") or info.get("content_type") or mimetypes.guess_type(record_path)[0]
        inferred_type = object_type or _object_type(info)
        merged_metadata = {"fsspec": info, **dict(metadata)}
        return VFSObjectRecord(
            namespace=self.namespace,
            backend=str(self.backend),
            protocol=str(self.protocol or self.backend),
            path=record_path,
            content_id=content_id,
            mime_type=mime_type or "application/octet-stream",
            size_bytes=int(size),
            object_type=inferred_type,
            modified_at=_string_or_none(_first_present(info, "mtime", "modified", "updated")),
            metadata=merged_metadata,
        )

    def _safe_info(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            return dict(self.fs.info(path))
        except Exception:
            return None

    def _enrich_info(self, info: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enrich_listings or not hasattr(self.indexer, "query_objects"):
            return info
        path = str(info.get("name") or info.get("path") or "")
        if not path:
            return info
        records = self.indexer.query_objects(
            namespace=self.namespace,
            backend=str(self.backend),
            normalized_path=normalize_vfs_path(path),
        )
        if records:
            info["graphrag_index"] = records[-1].to_dict()
        return info


class _IndexedFileHandle:
    """Proxy file object that emits an indexing event when closed."""

    def __init__(
        self,
        wrapper: IndexedVFSFileSystem,
        handle: Any,
        path: str,
        operation: str,
        metadata: Mapping[str, Any],
    ) -> None:
        self._wrapper = wrapper
        self._handle = handle
        self._path = path
        self._operation = operation
        self._metadata = dict(metadata)
        self._closed = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handle, name)

    def __enter__(self) -> "_IndexedFileHandle":
        enter = getattr(self._handle, "__enter__", None)
        if callable(enter):
            enter()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        exit_method = getattr(self._handle, "__exit__", None)
        if callable(exit_method):
            result = exit_method(exc_type, exc, tb)
        else:
            result = None
            self.close()
        self._emit_once()
        return result

    def __iter__(self) -> Iterable[Any]:
        return iter(self._handle)

    def close(self) -> Any:
        result = self._handle.close()
        self._emit_once()
        return result

    def _emit_once(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._wrapper._emit(self._operation, self._path, metadata=self._metadata)


def _protocol_label(protocol: Any) -> str:
    if isinstance(protocol, (tuple, list)):
        return str(protocol[0]) if protocol else "file"
    if protocol:
        return str(protocol)
    return "file"


def _iter_paths(path: Any) -> Iterable[str]:
    if isinstance(path, (list, tuple, set)):
        return [str(item) for item in path]
    return [str(path)]


def _coerce_bytes(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return None


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _object_type(info: Mapping[str, Any]) -> str:
    value = str(info.get("type") or "").lower()
    if value in {"directory", "dir"}:
        return "directory"
    return "file"


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


__all__ = ["IndexedVFSFileSystem", "VFSIndexingEvent"]
