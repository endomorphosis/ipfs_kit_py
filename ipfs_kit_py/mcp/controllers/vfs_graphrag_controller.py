"""MCP controller surface for VFS GraphRAG indexing, search, and bundles."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ipfs_kit_py.vfs_graphrag_export import VFSGraphRAGExportBundle
from ipfs_kit_py.vfs_graphrag_index import VFSGraphRAGIndex
from ipfs_kit_py.vfs_graphrag_schema import VFSObjectRecord, record_from_dict


JSONDict = Dict[str, Any]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items() if key != "index"}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class LocalVFSGraphRAGService:
    """Dependency-free local implementation used by CLI and default MCP wiring."""

    def __init__(
        self,
        *,
        index_root: str | Path,
        namespace: str = "default",
        storage_format: str = "jsonl",
    ) -> None:
        self.index = VFSGraphRAGIndex(index_root, namespace=namespace, storage_format=storage_format)

    def index_records(self, payload: Mapping[str, Any]) -> JSONDict:
        records = [record_from_dict(record) for record in payload.get("records", [])]
        if payload.get("path"):
            records.append(
                VFSObjectRecord(
                    namespace=str(payload.get("namespace") or self.index.namespace),
                    backend=str(payload.get("backend") or "ipfs"),
                    protocol=str(payload.get("protocol") or payload.get("backend") or "ipfs"),
                    path=str(payload["path"]),
                    content_id=payload.get("content_id"),
                    content_hash=payload.get("content_hash"),
                    mime_type=str(payload.get("mime_type") or "application/octet-stream"),
                    size_bytes=int(payload.get("size_bytes") or 0),
                    object_type=str(payload.get("object_type") or "file"),
                    tags=list(payload.get("tags") or []),
                    metadata=dict(payload.get("metadata") or {}),
                )
            )
        stored = self.index.put_records(records)
        return {"success": True, "indexed": len(stored), "records": stored, "status": self.index.stats()}

    def search(self, payload: Mapping[str, Any]) -> JSONDict:
        return self.index.search(
            query=str(payload.get("query") or ""),
            query_vector=payload.get("query_vector"),
            metadata_filters=payload.get("metadata_filters") or payload.get("filters"),
            namespaces=payload.get("namespaces"),
            backends=payload.get("backends"),
            protocols=payload.get("protocols"),
            top_k=int(payload.get("top_k") or 10),
            search_type=str(payload.get("search_type") or "hybrid"),
            facet_fields=payload.get("facet_fields"),
            hop_limit=payload.get("hop_limit"),
            entity_types=payload.get("entity_types"),
            graph_entity_ids=payload.get("graph_entity_ids"),
            relationship_predicates=payload.get("relationship_predicates"),
        )

    def status(self, payload: Optional[Mapping[str, Any]] = None) -> JSONDict:
        return {"success": True, **self.index.stats()}

    def export_index(self, payload: Mapping[str, Any]) -> JSONDict:
        manifest = VFSGraphRAGExportBundle(self.index).export_index(
            payload["output_path"],
            filesystem_map=payload.get("filesystem_map"),
            journal_entries=payload.get("journal_entries"),
            include_filesystem=bool(payload.get("include_filesystem", True)),
            include_journal=bool(payload.get("include_journal", True)),
            metadata=payload.get("metadata"),
        )
        return {"success": True, "output_path": str(payload["output_path"]), "manifest": manifest}

    def import_index(self, payload: Mapping[str, Any]) -> JSONDict:
        result = VFSGraphRAGExportBundle.import_index(
            payload["input_path"],
            self.index,
            mode=str(payload.get("mode") or "metadata-plus-indexes"),
            verify_checksums=bool(payload.get("verify_checksums", True)),
        )
        return {"success": True, **_jsonable(result), "status": self.index.stats()}


class VFSGraphRAGController:
    """JSON-friendly MCP controller for VFS GraphRAG operations."""

    def __init__(self, service: Any | None = None) -> None:
        self.service = service

    def _service(self, payload: Mapping[str, Any] | None) -> Any:
        payload = payload or {}
        if self.service is not None:
            return self.service
        index_root = payload.get("index_root") or payload.get("root_path")
        if not index_root:
            raise ValueError("index_root is required")
        return LocalVFSGraphRAGService(
            index_root=index_root,
            namespace=str(payload.get("namespace") or "default"),
            storage_format=str(payload.get("storage_format") or "jsonl"),
        )

    async def index(self, payload: Mapping[str, Any]) -> JSONDict:
        result = await _maybe_await(self._service(payload).index_records(dict(payload)))
        return _jsonable(result)

    async def search(self, payload: Mapping[str, Any]) -> JSONDict:
        result = await _maybe_await(self._service(payload).search(dict(payload)))
        return _jsonable(result)

    async def status(self, payload: Mapping[str, Any] | None = None) -> JSONDict:
        result = await _maybe_await(self._service(payload).status(dict(payload or {})))
        return _jsonable(result)

    async def export_index(self, payload: Mapping[str, Any]) -> JSONDict:
        result = await _maybe_await(self._service(payload).export_index(dict(payload)))
        return _jsonable(result)

    async def import_index(self, payload: Mapping[str, Any]) -> JSONDict:
        result = await _maybe_await(self._service(payload).import_index(dict(payload)))
        return _jsonable(result)

    def register_routes(self, router: Any) -> None:
        if not hasattr(router, "add_api_route"):
            return
        router.add_api_route("/api/vfs/graphrag/index", self.index, methods=["POST"])
        router.add_api_route("/api/vfs/graphrag/search", self.search, methods=["POST"])
        router.add_api_route("/api/vfs/graphrag/status", self.status, methods=["GET", "POST"])
        router.add_api_route("/api/vfs/graphrag/export", self.export_index, methods=["POST"])
        router.add_api_route("/api/vfs/graphrag/import", self.import_index, methods=["POST"])


def dumps_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(_jsonable(payload), indent=2, sort_keys=True)


__all__ = ["LocalVFSGraphRAGService", "VFSGraphRAGController", "dumps_json"]
