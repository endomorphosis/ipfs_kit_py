"""Walrus HTTP storage client and response normalization helpers."""

from __future__ import annotations

import os
import json
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import httpx

WALRUS_INDEX_SCHEMA = "ipfs_kit_py.walrus.index.v1"


class WalrusConfigurationError(ValueError):
    """Raised when a requested Walrus operation is missing configuration."""


@dataclass(frozen=True)
class WalrusBlobInfo:
    """Normalized metadata returned by Walrus publisher responses."""

    blob_id: Optional[str] = None
    object_id: Optional[str] = None
    tx_digest: Optional[str] = None
    end_epoch: Optional[int] = None
    cost: Optional[int] = None
    size: Optional[int] = None
    gateway_url: Optional[str] = None
    raw_response: Optional[Mapping[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WalrusMetadataIndex:
    """Local JSON index mapping logical names to Walrus blob metadata."""

    def __init__(self, index_path: Optional[os.PathLike[str] | str] = None) -> None:
        self.path = Path(index_path).expanduser() if index_path else self.default_path()

    @staticmethod
    def default_path() -> Path:
        return Path.home() / ".cache" / "ipfs_kit_py" / "walrus" / "index.json"

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self._empty_index()

        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, dict):
            raise ValueError(f"Walrus index must be a JSON object: {self.path}")

        items = payload.get("items")
        if not isinstance(items, dict):
            items = {}

        return {
            "schema": payload.get("schema") or WALRUS_INDEX_SCHEMA,
            "items": items,
        }

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        item = self.load()["items"].get(self._normalize_name(name))
        return dict(item) if isinstance(item, Mapping) else None

    def list_items(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: dict(item)
            for name, item in self.load()["items"].items()
            if isinstance(item, Mapping)
        }

    def update(
        self,
        name: str,
        metadata: Mapping[str, Any] | WalrusBlobInfo,
        *,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        index = self.load()
        normalized_name = self._normalize_name(name)
        entry = self._entry_from_metadata(normalized_name, metadata, content_type=content_type)
        index["items"][normalized_name] = entry
        self._write(index)
        return dict(entry)

    def remove(self, name: str) -> Optional[Dict[str, Any]]:
        index = self.load()
        normalized_name = self._normalize_name(name)
        removed = index["items"].pop(normalized_name, None)
        self._write(index)
        return dict(removed) if isinstance(removed, Mapping) else removed

    @staticmethod
    def _empty_index() -> Dict[str, Any]:
        return {"schema": WALRUS_INDEX_SCHEMA, "items": {}}

    @staticmethod
    def _normalize_name(name: str) -> str:
        if name.startswith("walrus://"):
            name = name[len("walrus://") :]
        return name.lstrip("/")

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _entry_from_metadata(
        self,
        name: str,
        metadata: Mapping[str, Any] | WalrusBlobInfo,
        *,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        if isinstance(metadata, WalrusBlobInfo):
            payload = metadata.to_dict()
        else:
            payload = dict(metadata)

        entry: Dict[str, Any] = {
            "name": name,
            "created_at": payload.get("created_at") or self._utc_now(),
        }
        for key in (
            "blob_id",
            "object_id",
            "tx_digest",
            "end_epoch",
            "cost",
            "size",
            "content_type",
            "gateway_url",
        ):
            value = payload.get(key)
            if value is not None:
                entry[key] = value
        if content_type is not None:
            entry["content_type"] = content_type
        return entry

    def _write(self, index: Mapping[str, Any]) -> None:
        payload = {
            "schema": index.get("schema") or WALRUS_INDEX_SCHEMA,
            "items": index.get("items") if isinstance(index.get("items"), Mapping) else {},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_name: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_name = handle.name
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)


class WalrusStorageClient:
    """Small synchronous client for Walrus publisher, aggregator, and delete APIs."""

    def __init__(
        self,
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
    ) -> None:
        self.publisher_url = publisher_url or self._env_first(
            "WALRUS_PUBLISHER_URL",
            "ABBY_RUNTIME_WALRUS_PUBLISHER_URL",
            "VITE_WALRUS_STORAGE_PUBLISHER_URL",
        )
        self.aggregator_url = aggregator_url or self._env_first(
            "WALRUS_AGGREGATOR_URL",
            "ABBY_RUNTIME_WALRUS_AGGREGATOR_URL",
            "VITE_WALRUS_STORAGE_AGGREGATOR_URL",
        )
        self.delete_url = delete_url or self._env_first(
            "WALRUS_DELETE_URL",
            "ABBY_RUNTIME_WALRUS_DELETE_URL",
            "VITE_WALRUS_STORAGE_DELETE_URL",
        )
        self.client_token = client_token or self._env_first(
            "WALRUS_CLIENT_TOKEN",
            "ABBY_RUNTIME_WALRUS_CLIENT_TOKEN",
            "VITE_WALRUS_STORAGE_CLIENT_TOKEN",
        )

        env_epochs = self._env_first(
            "WALRUS_EPOCHS",
            "ABBY_RUNTIME_WALRUS_EPOCHS",
            "VITE_WALRUS_STORAGE_EPOCHS",
        )
        self.epochs = epochs if epochs is not None else self._int_or_none(env_epochs)

        env_deletable = self._env_first(
            "WALRUS_DELETABLE",
            "ABBY_RUNTIME_WALRUS_DELETABLE",
            "VITE_WALRUS_STORAGE_DELETABLE",
        )
        self.deletable = deletable if deletable is not None else self._bool_or_none(env_deletable)

        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        if self.client_token:
            request_headers["Authorization"] = f"Bearer {self.client_token}"

        self._client = httpx.Client(
            headers=request_headers,
            timeout=timeout,
            transport=transport,
        )
        self.index = WalrusMetadataIndex(index_path)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "WalrusStorageClient":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    @staticmethod
    def _env_first(*names: str) -> Optional[str]:
        for name in names:
            value = os.environ.get(name)
            if value:
                return value
        return None

    @staticmethod
    def _bool_or_none(value: Optional[str]) -> Optional[bool]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return None

    @staticmethod
    def _int_or_none(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _require_url(value: Optional[str], operation: str) -> str:
        if not value:
            raise WalrusConfigurationError(f"Walrus {operation} URL is not configured")
        return value

    @staticmethod
    def _with_blob_path(base_url: str, blob_id: Optional[str] = None) -> str:
        url = base_url.rstrip("/")
        if "{blobId}" in url or "{blob_id}" in url:
            if not blob_id:
                return url
            return url.replace("{blobId}", quote(blob_id, safe="")).replace(
                "{blob_id}", quote(blob_id, safe="")
            )

        path = urlsplit(url).path.rstrip("/")
        if path.endswith("/v1/blobs"):
            return f"{url}/{quote(blob_id, safe='')}" if blob_id else url
        return f"{url}/v1/blobs/{quote(blob_id, safe='')}" if blob_id else f"{url}/v1/blobs"

    @staticmethod
    def _add_query(url: str, params: Mapping[str, Any]) -> str:
        filtered = {key: value for key, value in params.items() if value is not None}
        if not filtered:
            return url

        split = urlsplit(url)
        existing = split.query
        query = urlencode(filtered)
        if existing:
            query = f"{existing}&{query}"
        return urlunsplit((split.scheme, split.netloc, split.path, query, split.fragment))

    @staticmethod
    def _format_bool(value: Optional[bool]) -> Optional[str]:
        if value is None:
            return None
        return "true" if value else "false"

    def resolve_publisher_blob_url(
        self,
        *,
        epochs: Optional[int] = None,
        deletable: Optional[bool] = None,
        permanent: Optional[bool] = None,
    ) -> str:
        base_url = self._require_url(self.publisher_url, "publisher")
        url = self._with_blob_path(base_url)
        selected_epochs = self.epochs if epochs is None else epochs
        selected_deletable = self.deletable if deletable is None else deletable
        return self._add_query(
            url,
            {
                "epochs": selected_epochs,
                "deletable": self._format_bool(selected_deletable),
                "permanent": self._format_bool(permanent),
            },
        )

    def resolve_aggregator_blob_url(self, blob_id: str) -> str:
        base_url = self._require_url(self.aggregator_url, "aggregator")
        return self._with_blob_path(base_url, blob_id)

    def resolve_delete_url(
        self,
        blob_id: str,
        object_id: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> str:
        base_url = self._require_url(self.delete_url, "delete")
        url = base_url.rstrip("/")
        replacements = {
            "{blobId}": quote(blob_id, safe=""),
            "{blob_id}": quote(blob_id, safe=""),
            "{objectId}": quote(object_id or "", safe=""),
            "{object_id}": quote(object_id or "", safe=""),
            "{recordId}": quote(record_id or "", safe=""),
            "{record_id}": quote(record_id or "", safe=""),
        }
        if any(token in url for token in replacements):
            for token, value in replacements.items():
                url = url.replace(token, value)
            return url

        url = self._with_blob_path(url, blob_id)
        return self._add_query(url, {"objectId": object_id, "recordId": record_id})

    def put_blob(
        self,
        data: bytes,
        content_type: Optional[str] = None,
        **options: Any,
    ) -> WalrusBlobInfo:
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type

        response = self._client.put(
            self.resolve_publisher_blob_url(
                epochs=options.get("epochs"),
                deletable=options.get("deletable"),
                permanent=options.get("permanent"),
            ),
            content=data,
            headers=headers,
        )
        response.raise_for_status()
        info = self.normalize_response(response.json())
        if info.size is None:
            info = WalrusBlobInfo(**{**info.to_dict(), "size": len(data)})
        return info

    def get_blob(
        self,
        blob_id: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> bytes:
        headers = {}
        if start is not None or end is not None:
            first = "" if start is None else str(start)
            last = "" if end is None else str(end - 1)
            headers["Range"] = f"bytes={first}-{last}"
        response = self._client.get(self.resolve_aggregator_blob_url(blob_id), headers=headers)
        response.raise_for_status()
        return response.content

    def head_blob(self, blob_id: str) -> Dict[str, Any]:
        response = self._client.head(self.resolve_aggregator_blob_url(blob_id))
        response.raise_for_status()
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content_length": self._int_or_none(response.headers.get("content-length")),
            "content_type": response.headers.get("content-type"),
        }

    def delete_blob(
        self,
        blob_id: str,
        object_id: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        response = self._client.delete(self.resolve_delete_url(blob_id, object_id, record_id))
        response.raise_for_status()
        if response.content:
            try:
                payload = response.json()
            except ValueError:
                payload = {"text": response.text}
        else:
            payload = {}
        return {"success": True, "status_code": response.status_code, **payload}

    def status(self) -> Dict[str, Any]:
        return {
            "publisher_configured": bool(self.publisher_url),
            "aggregator_configured": bool(self.aggregator_url),
            "delete_configured": bool(self.delete_url),
            "auth_configured": bool(self.client_token),
            "epochs": self.epochs,
            "deletable": self.deletable,
            "index_path": str(self.index.path),
        }

    def load_index(self) -> Dict[str, Any]:
        return self.index.load()

    def get_index_entry(self, name: str) -> Optional[Dict[str, Any]]:
        return self.index.get(name)

    def update_index(
        self,
        name: str,
        metadata: Mapping[str, Any] | WalrusBlobInfo,
        *,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.index.update(name, metadata, content_type=content_type)

    def remove_index_entry(self, name: str) -> Optional[Dict[str, Any]]:
        return self.index.remove(name)

    @classmethod
    def normalize_response(cls, payload: Mapping[str, Any]) -> WalrusBlobInfo:
        variant = cls._variant_payload(payload)
        storage = cls._first_mapping(
            variant,
            ("storage",),
            ("blobObject", "storage"),
            ("blob_object", "storage"),
        )

        blob_id = cls._first_value(
            payload,
            ("blobId",),
            ("blob_id",),
            ("walrusBlobId",),
            ("walrus_blob_id",),
            ("newlyCreated", "blobObject", "blobId"),
            ("newlyCreated", "blob_object", "blob_id"),
            ("alreadyCertified", "blobId"),
            ("alreadyCertified", "blob_id"),
        )
        object_id = cls._first_value(
            payload,
            ("objectId",),
            ("object_id",),
            ("blobObjectId",),
            ("blob_object_id",),
            ("suiObjectId",),
            ("sui_object_id",),
            ("newlyCreated", "blobObject", "id"),
            ("newlyCreated", "blobObject", "objectId"),
            ("newlyCreated", "blob_object", "id"),
            ("newlyCreated", "blob_object", "object_id"),
            ("alreadyCertified", "blobObjectId"),
            ("alreadyCertified", "blob_object_id"),
            ("alreadyCertified", "objectId"),
        )
        tx_digest = cls._first_value(
            payload,
            ("txDigest",),
            ("tx_digest",),
            ("digest",),
            ("newlyCreated", "event", "txDigest"),
            ("newlyCreated", "event", "tx_digest"),
            ("alreadyCertified", "event", "txDigest"),
            ("alreadyCertified", "event", "tx_digest"),
        )
        end_epoch = cls._int_or_none(
            cls._first_value(
                payload,
                ("endEpoch",),
                ("end_epoch",),
                ("storage", "endEpoch"),
                ("storage", "end_epoch"),
                ("newlyCreated", "blobObject", "storage", "endEpoch"),
                ("newlyCreated", "blobObject", "storage", "end_epoch"),
                ("newlyCreated", "blob_object", "storage", "end_epoch"),
                ("alreadyCertified", "storage", "endEpoch"),
                ("alreadyCertified", "storage", "end_epoch"),
            )
            or cls._mapping_get(storage, "endEpoch", "end_epoch")
        )
        cost = cls._int_or_none(
            cls._first_value(
                payload,
                ("cost",),
                ("storageCost",),
                ("storage_cost",),
                ("newlyCreated", "cost"),
                ("alreadyCertified", "cost"),
            )
        )
        size = cls._int_or_none(
            cls._first_value(
                payload,
                ("size",),
                ("blobSize",),
                ("blob_size",),
                ("newlyCreated", "blobObject", "size"),
                ("newlyCreated", "blob_object", "size"),
                ("alreadyCertified", "size"),
            )
        )
        gateway_url = cls._first_value(
            payload,
            ("gatewayUrl",),
            ("gateway_url",),
            ("url",),
            ("newlyCreated", "gatewayUrl"),
            ("alreadyCertified", "gatewayUrl"),
        )

        return WalrusBlobInfo(
            blob_id=str(blob_id) if blob_id is not None else None,
            object_id=str(object_id) if object_id is not None else None,
            tx_digest=str(tx_digest) if tx_digest is not None else None,
            end_epoch=end_epoch,
            cost=cost,
            size=size,
            gateway_url=str(gateway_url) if gateway_url is not None else None,
            raw_response=payload,
        )

    @staticmethod
    def _variant_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        for key in ("newlyCreated", "newly_created", "alreadyCertified", "already_certified"):
            value = payload.get(key)
            if isinstance(value, Mapping):
                return value
        return payload

    @classmethod
    def _first_mapping(cls, mapping: Mapping[str, Any], *paths: tuple[str, ...]) -> Mapping[str, Any]:
        for path in paths:
            value = cls._path_get(mapping, path)
            if isinstance(value, Mapping):
                return value
        return {}

    @classmethod
    def _first_value(cls, mapping: Mapping[str, Any], *paths: tuple[str, ...]) -> Any:
        for path in paths:
            value = cls._path_get(mapping, path)
            if value is not None:
                return value
        return None

    @staticmethod
    def _path_get(mapping: Mapping[str, Any], path: tuple[str, ...]) -> Any:
        current: Any = mapping
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                return None
            current = current[key]
        return current

    @staticmethod
    def _mapping_get(mapping: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            value = mapping.get(key)
            if value is not None:
                return value
        return None


__all__ = [
    "WALRUS_INDEX_SCHEMA",
    "WalrusBlobInfo",
    "WalrusConfigurationError",
    "WalrusMetadataIndex",
    "WalrusStorageClient",
]
