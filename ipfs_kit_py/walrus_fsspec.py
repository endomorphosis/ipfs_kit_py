"""fsspec backend for Walrus blob storage."""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import httpx

try:
    import fsspec
    from fsspec.asyn import AsyncFileSystem, mirror_sync_methods

    HAVE_FSSPEC = True
except Exception:  # pragma: no cover - exercised only without optional deps
    fsspec = None  # type: ignore[assignment]
    AsyncFileSystem = object  # type: ignore[assignment,misc]
    mirror_sync_methods = None  # type: ignore[assignment]
    HAVE_FSSPEC = False

from .walrus_storage import (
    WalrusConfigurationError,
    WalrusStorageClient,
)

logger = logging.getLogger(__name__)


class _WalrusWriteBuffer(io.BytesIO):
    """Upload buffered bytes when the fsspec write handle is closed."""

    def __init__(self, fs: "WalrusFileSystem", path: str, kwargs: Mapping[str, Any]) -> None:
        super().__init__()
        self.fs = fs
        self.path = path
        self.kwargs = dict(kwargs)
        self._committed = False

    def close(self) -> None:
        if not self._committed:
            self._committed = True
            self.fs.pipe_file(self.path, self.getvalue(), **self.kwargs)
        super().close()


class WalrusFileSystem(AsyncFileSystem):
    """Walrus fsspec filesystem backed by a local logical-name index."""

    protocol = "walrus"

    def __init__(
        self,
        *,
        client: Optional[WalrusStorageClient] = None,
        publisher_url: Optional[str] = None,
        aggregator_url: Optional[str] = None,
        delete_url: Optional[str] = None,
        client_token: Optional[str] = None,
        epochs: Optional[int] = None,
        deletable: Optional[bool] = None,
        timeout: float = 30.0,
        headers: Optional[Mapping[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
        index_path: Optional[os.PathLike[str] | str] = None,
        **kwargs: Any,
    ) -> None:
        if not HAVE_FSSPEC:
            raise ImportError("fsspec is required to use WalrusFileSystem")
        super().__init__(**kwargs)
        self.client = client or WalrusStorageClient(
            publisher_url=publisher_url,
            aggregator_url=aggregator_url,
            delete_url=delete_url,
            client_token=client_token,
            epochs=epochs,
            deletable=deletable,
            timeout=timeout,
            headers=headers,
            transport=transport,
            index_path=index_path,
        )

    @classmethod
    def _strip_protocol(cls, path: Any) -> Any:
        if isinstance(path, (list, tuple)):
            return type(path)(cls._strip_protocol(p) for p in path)
        if not isinstance(path, str):
            return path
        if path.startswith("walrus://"):
            path = path[len("walrus://") :]
        return path.lstrip("/")

    @staticmethod
    def _is_root(path: str) -> bool:
        return path in {"", "/", "walrus://"}

    @staticmethod
    def _display_name(name: str) -> str:
        return f"walrus://{name}" if name else "walrus://"

    def _entry_to_info(self, name: str, entry: Mapping[str, Any]) -> Dict[str, Any]:
        size = entry.get("size")
        return {
            "name": self._display_name(name),
            "type": "file",
            "size": int(size) if size is not None else None,
            "blob_id": entry.get("blob_id"),
            "object_id": entry.get("object_id"),
            "tx_digest": entry.get("tx_digest"),
            "end_epoch": entry.get("end_epoch"),
            "cost": entry.get("cost"),
            "content_type": entry.get("content_type"),
            "created_at": entry.get("created_at"),
            "gateway_url": entry.get("gateway_url"),
        }

    def _resolve_blob_id(self, path: str) -> str:
        normalized = self._strip_protocol(path)
        entry = self.client.get_index_entry(normalized)
        if entry and entry.get("blob_id"):
            return str(entry["blob_id"])
        if not normalized:
            raise FileNotFoundError(path)
        return normalized

    async def _cat_file(
        self,
        path: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        **kwargs: Any,
    ) -> bytes:
        blob_id = self._resolve_blob_id(path)
        return self.client.get_blob(blob_id, start=start, end=end)

    async def _pipe_file(
        self,
        path: str,
        value: bytes,
        mode: str = "overwrite",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        normalized = self._strip_protocol(path)
        if not normalized:
            raise ValueError("Walrus writes require a logical name or blob path")
        if mode == "create" and self.client.get_index_entry(normalized):
            raise FileExistsError(path)

        content_type = kwargs.pop("content_type", None)
        info = self.client.put_blob(bytes(value), content_type=content_type, **kwargs)
        if not info.blob_id:
            raise ValueError("Walrus publisher response did not include a blob id")
        return self.client.update_index(normalized, info, content_type=content_type)

    async def _put_file(
        self,
        lpath: str,
        rpath: str,
        mode: str = "overwrite",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        with open(lpath, "rb") as handle:
            data = handle.read()
        return await self._pipe_file(rpath, data, mode=mode, **kwargs)

    async def _get_file(self, rpath: str, lpath: str, **kwargs: Any) -> None:
        data = await self._cat_file(rpath, **kwargs)
        Path(lpath).parent.mkdir(parents=True, exist_ok=True)
        with open(lpath, "wb") as handle:
            handle.write(data)

    async def _info(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        normalized = self._strip_protocol(path)
        if self._is_root(normalized):
            return {"name": "walrus://", "type": "directory", "size": 0}

        entry = self.client.get_index_entry(normalized)
        if entry:
            return self._entry_to_info(normalized, entry)
        if "/" in normalized:
            raise FileNotFoundError(path)

        try:
            head = self.client.head_blob(normalized)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise FileNotFoundError(path) from exc
            raise
        size = head.get("content_length")
        return {
            "name": self._display_name(normalized),
            "type": "file",
            "size": int(size) if size is not None else None,
            "blob_id": normalized,
            "content_type": head.get("content_type"),
        }

    async def _exists(self, path: str, **kwargs: Any) -> bool:
        normalized = self._strip_protocol(path)
        if self._is_root(normalized):
            return True
        if self.client.get_index_entry(normalized):
            return True
        if "/" in normalized:
            return False
        try:
            await self._info(normalized, **kwargs)
        except (FileNotFoundError, WalrusConfigurationError, httpx.HTTPError):
            return False
        return True

    async def _ls(self, path: str, detail: bool = True, **kwargs: Any) -> list[Any]:
        normalized = self._strip_protocol(path)
        prefix = "" if self._is_root(normalized) else normalized.rstrip("/") + "/"
        items = []
        for name, entry in sorted(self.client.index.list_items().items()):
            if prefix and not name.startswith(prefix):
                continue
            info = self._entry_to_info(name, entry)
            items.append(info if detail else info["name"])
        return items

    async def _rm_file(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        normalized = self._strip_protocol(path)
        entry = self.client.get_index_entry(normalized)
        blob_id = str(entry.get("blob_id")) if entry and entry.get("blob_id") else normalized
        object_id = kwargs.pop("object_id", None) or (entry or {}).get("object_id")
        record_id = kwargs.pop("record_id", None) or (entry or {}).get("record_id")
        result = self.client.delete_blob(blob_id, object_id=object_id, record_id=record_id)
        if entry:
            self.client.remove_index_entry(normalized)
        return result

    async def _rm(
        self,
        path: str,
        recursive: bool = False,
        batch_size: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        await self._rm_file(path, **kwargs)

    def _open(
        self,
        path: str,
        mode: str = "rb",
        block_size: Optional[int] = None,
        autocommit: bool = True,
        cache_options: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> io.BytesIO:
        if "r" in mode:
            data = self.cat_file(path, **kwargs)
            handle = io.BytesIO(data)
            handle.size = len(data)  # type: ignore[attr-defined]
            return handle
        if any(flag in mode for flag in ("w", "a", "x")):
            if "x" in mode and self.exists(path):
                raise FileExistsError(path)
            return _WalrusWriteBuffer(self, path, kwargs)
        raise ValueError(f"unsupported Walrus file mode: {mode}")

    def ukey(self, path: str) -> str:
        return self._resolve_blob_id(path)

    def close(self) -> None:
        self.client.close()


if HAVE_FSSPEC:  # pragma: no branch
    mirror_sync_methods(WalrusFileSystem)
    try:
        fsspec.register_implementation("walrus", WalrusFileSystem, clobber=True)
    except Exception:  # pragma: no cover - defensive registration guard
        logger.debug("Walrus fsspec registration skipped", exc_info=True)


__all__ = ["HAVE_FSSPEC", "WalrusFileSystem"]
