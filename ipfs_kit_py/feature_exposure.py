"""Shared thin adapters for exposing optional feature families.

These helpers keep CLI, MCP, dashboard, and SDK tool wrappers aligned without
moving the underlying Walrus, fsspec, or VFS GraphRAG implementations.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    if isinstance(value, bytes):
        return {"encoding": "base64", "data": base64.b64encode(value).decode("ascii")}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _decode_content(content: Any, encoding: str = "text") -> bytes:
    if isinstance(content, bytes):
        return content
    if content is None:
        return b""
    text = str(content)
    if encoding == "base64":
        return base64.b64decode(text)
    if encoding == "hex":
        return bytes.fromhex(text)
    return text.encode("utf-8")


def _encode_content(data: bytes, encoding: str = "text") -> Dict[str, Any]:
    if encoding == "base64":
        return {"encoding": "base64", "content": base64.b64encode(data).decode("ascii"), "size": len(data)}
    if encoding == "hex":
        return {"encoding": "hex", "content": data.hex(), "size": len(data)}
    return {"encoding": "text", "content": data.decode("utf-8", "replace"), "size": len(data)}


def _walrus_config(args: Mapping[str, Any]) -> Dict[str, Any]:
    keys = (
        "publisher_url",
        "aggregator_url",
        "delete_url",
        "client_token",
        "epochs",
        "deletable",
        "timeout",
        "index_path",
    )
    return {key: args[key] for key in keys if args.get(key) is not None}


def _create_walrus_fs(args: Mapping[str, Any]):
    from .high_level_api import create_walrus_filesystem

    return create_walrus_filesystem(**_walrus_config(args))


def walrus_status(args: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    args = args or {}
    status: Dict[str, Any] = {
        "success": True,
        "feature": "walrus",
        "protocol": "walrus://",
        "configured": False,
        "available": False,
    }
    try:
        from .jit_imports import get_jit_imports

        feature_status = get_jit_imports().get_feature_status().get("walrus_fsspec", {})
        status["jit_feature"] = feature_status
        status["available"] = bool(feature_status.get("available"))
    except Exception as exc:
        status["jit_feature_error"] = str(exc)

    try:
        from .walrus_storage import WalrusStorageClient

        client = WalrusStorageClient(**_walrus_config(args))
        status["configured"] = True
        status["index"] = {"path": str(client.index.path), "items": len(client.index.list_items())}
    except Exception as exc:
        status["configured"] = False
        status["configuration_error"] = str(exc)
    return status


def walrus_list(args: Mapping[str, Any]) -> Dict[str, Any]:
    fs = _create_walrus_fs(args)
    path = args.get("path") or "walrus://"
    detail = bool(args.get("detail", True))
    return {"success": True, "items": _jsonable(fs.ls(path, detail=detail))}


def walrus_get(args: Mapping[str, Any]) -> Dict[str, Any]:
    path = args.get("path") or args.get("blob_id")
    if not path:
        return {"success": False, "error": "path or blob_id is required"}
    fs = _create_walrus_fs(args)
    data = fs.cat_file(str(path))
    return {"success": True, "path": str(path), **_encode_content(data, str(args.get("encoding") or "text"))}


def walrus_put(args: Mapping[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    if not path:
        return {"success": False, "error": "path is required"}
    fs = _create_walrus_fs(args)
    data = _decode_content(args.get("content"), str(args.get("encoding") or "text"))
    result = fs.pipe_file(
        str(path),
        data,
        mode=str(args.get("mode") or "overwrite"),
        content_type=args.get("content_type"),
    )
    return {"success": True, "path": str(path), "result": _jsonable(result)}


def walrus_delete(args: Mapping[str, Any]) -> Dict[str, Any]:
    path = args.get("path") or args.get("blob_id")
    if not path:
        return {"success": False, "error": "path or blob_id is required"}
    fs = _create_walrus_fs(args)
    result = fs.rm(str(path))
    return {"success": True, "path": str(path), "result": _jsonable(result)}


def fsspec_protocols(args: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    del args
    protocols = ["ipfs", "synapse", "storacha", "filecoin", "walrus"]
    registered: Dict[str, bool] = {}
    try:
        import fsspec

        from .enhanced_fsspec import register_fsspec_implementations

        register_fsspec_implementations(clobber=False)
        for protocol in protocols:
            registered[protocol] = protocol in getattr(fsspec, "registry", {}) or protocol in getattr(fsspec, "known_implementations", {})
    except Exception as exc:
        return {"success": False, "protocols": protocols, "registered": registered, "error": str(exc)}
    return {"success": True, "protocols": protocols, "registered": registered}


def fsspec_status(args: Mapping[str, Any]) -> Dict[str, Any]:
    protocol = str(args.get("protocol") or args.get("backend") or "ipfs")
    if protocol == "walrus":
        return walrus_status(args)
    try:
        from .enhanced_fsspec import EnhancedIPFSFileSystem

        fs = EnhancedIPFSFileSystem(backend=protocol, **{k: v for k, v in args.items() if k not in {"protocol", "backend"}})
        return {"success": True, "protocol": protocol, "status": _jsonable(fs.get_backend_status())}
    except Exception as exc:
        return {"success": False, "protocol": protocol, "error": str(exc)}


def fsspec_read(args: Mapping[str, Any]) -> Dict[str, Any]:
    url = args.get("url") or args.get("path")
    if not url:
        return {"success": False, "error": "url or path is required"}
    try:
        import fsspec

        with fsspec.open(str(url), "rb", **dict(args.get("storage_options") or {})) as handle:
            data = handle.read()
        return {"success": True, "url": str(url), **_encode_content(data, str(args.get("encoding") or "text"))}
    except Exception as exc:
        return {"success": False, "url": str(url), "error": str(exc)}


def fsspec_write(args: Mapping[str, Any]) -> Dict[str, Any]:
    url = args.get("url") or args.get("path")
    if not url:
        return {"success": False, "error": "url or path is required"}
    try:
        import fsspec

        data = _decode_content(args.get("content"), str(args.get("encoding") or "text"))
        with fsspec.open(str(url), "wb", **dict(args.get("storage_options") or {})) as handle:
            handle.write(data)
        return {"success": True, "url": str(url), "size": len(data)}
    except Exception as exc:
        return {"success": False, "url": str(url), "error": str(exc)}


def _graphrag_index(args: Mapping[str, Any]):
    from .vfs_graphrag_index import VFSGraphRAGIndex

    root = args.get("index_path") or args.get("root_path") or str(Path.home() / ".cache" / "ipfs_kit_py" / "vfs_graphrag_index")
    return VFSGraphRAGIndex(root, namespace=str(args.get("namespace") or "default"), storage_format=str(args.get("storage_format") or "jsonl"))


def vfs_graphrag_status(args: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    args = args or {}
    try:
        index = _graphrag_index(args)
        return {"success": True, "status": _jsonable(index.stats())}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def vfs_graphrag_search(args: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        index = _graphrag_index(args)
        method_name = str(args.get("method") or args.get("search_type") or "search")
        method_map = {
            "search": index.search,
            "metadata": index.metadata_search,
            "metadata_search": index.metadata_search,
            "vector": index.vector_search,
            "vector_search": index.vector_search,
            "hybrid": index.hybrid_search,
            "hybrid_search": index.hybrid_search,
            "graph": index.graph_search,
            "graph_search": index.graph_search,
            "graph_hybrid": index.graph_hybrid_search,
            "graph_hybrid_search": index.graph_hybrid_search,
        }
        method = method_map.get(method_name)
        if method is None:
            return {"success": False, "error": f"unknown VFS GraphRAG search method: {method_name}"}
        call_args = dict(args)
        for key in ("index_path", "root_path", "namespace", "storage_format", "method"):
            call_args.pop(key, None)
        result = method(**call_args)
        return _jsonable(result)
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def vfs_graphrag_export(args: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        index = _graphrag_index(args)
        output = args.get("output")
        payload = index.stats()
        payload["records"] = {
            kind: [_jsonable(record) for record in index.query_records(kind)]
            for kind in ("objects", "chunks", "embeddings", "entities", "relationships", "snapshots", "checkpoints")
        }
        if output:
            Path(str(output)).parent.mkdir(parents=True, exist_ok=True)
            Path(str(output)).write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
        return {"success": True, "output": str(output) if output else None, "data": _jsonable(payload)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def dispatch_feature_tool(name: str, args: Optional[Mapping[str, Any]] = None) -> Optional[Dict[str, Any]]:
    args = args or {}
    handlers = {
        "walrus_status": walrus_status,
        "walrus_list": walrus_list,
        "walrus_get": walrus_get,
        "walrus_put": walrus_put,
        "walrus_delete": walrus_delete,
        "fsspec_list_protocols": fsspec_protocols,
        "fsspec_protocols": fsspec_protocols,
        "fsspec_backend_status": fsspec_status,
        "fsspec_status": fsspec_status,
        "fsspec_read": fsspec_read,
        "fsspec_write": fsspec_write,
        "vfs_graphrag_status": vfs_graphrag_status,
        "vfs_graphrag_search": vfs_graphrag_search,
        "vfs_graphrag_metadata_search": lambda a: vfs_graphrag_search({**a, "method": "metadata_search"}),
        "vfs_graphrag_vector_search": lambda a: vfs_graphrag_search({**a, "method": "vector_search"}),
        "vfs_graphrag_hybrid_search": lambda a: vfs_graphrag_search({**a, "method": "hybrid_search"}),
        "vfs_graphrag_graph_search": lambda a: vfs_graphrag_search({**a, "method": "graph_search"}),
        "vfs_graphrag_graph_hybrid_search": lambda a: vfs_graphrag_search({**a, "method": "graph_hybrid_search"}),
        "vfs_graphrag_export": vfs_graphrag_export,
    }
    handler = handlers.get(name)
    if handler is None:
        return None
    return handler(args)


def feature_tool_definitions() -> list[Dict[str, Any]]:
    return [
        {"name": "walrus_status", "description": "Show Walrus fsspec backend status", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "walrus_list", "description": "List index-backed Walrus logical paths", "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "default": "walrus://"}, "detail": {"type": "boolean", "default": True}}}},
        {"name": "walrus_get", "description": "Read a Walrus logical path or blob id", "inputSchema": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}, "encoding": {"type": "string", "enum": ["text", "base64", "hex"], "default": "text"}}}},
        {"name": "walrus_put", "description": "Write bytes/text to Walrus using a logical path", "inputSchema": {"type": "object", "required": ["path", "content"], "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "encoding": {"type": "string", "enum": ["text", "base64", "hex"], "default": "text"}, "content_type": {"type": "string"}}}},
        {"name": "walrus_delete", "description": "Delete a Walrus logical path or blob id", "inputSchema": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}}},
        {"name": "fsspec_list_protocols", "description": "List ipfs_kit fsspec protocols", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "fsspec_backend_status", "description": "Get status for an fsspec protocol backend", "inputSchema": {"type": "object", "properties": {"protocol": {"type": "string", "enum": ["ipfs", "synapse", "storacha", "filecoin", "walrus"]}}}},
        {"name": "fsspec_read", "description": "Read through fsspec.open", "inputSchema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}, "encoding": {"type": "string", "enum": ["text", "base64", "hex"], "default": "text"}}}},
        {"name": "fsspec_write", "description": "Write through fsspec.open", "inputSchema": {"type": "object", "required": ["url", "content"], "properties": {"url": {"type": "string"}, "content": {"type": "string"}, "encoding": {"type": "string", "enum": ["text", "base64", "hex"], "default": "text"}}}},
        {"name": "vfs_graphrag_status", "description": "Show VFS GraphRAG index status", "inputSchema": {"type": "object", "properties": {"index_path": {"type": "string"}}}},
        {"name": "vfs_graphrag_search", "description": "Search the VFS GraphRAG index", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "method": {"type": "string", "enum": ["search", "metadata_search", "vector_search", "hybrid_search", "graph_search", "graph_hybrid_search"], "default": "search"}, "top_k": {"type": "number", "default": 10}, "index_path": {"type": "string"}}}},
        {"name": "vfs_graphrag_metadata_search", "description": "Run metadata-only VFS GraphRAG search", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "filters": {"type": "object"}, "top_k": {"type": "number", "default": 10}, "index_path": {"type": "string"}}}},
        {"name": "vfs_graphrag_vector_search", "description": "Run vector VFS GraphRAG search", "inputSchema": {"type": "object", "properties": {"query_vector": {"type": "array", "items": {"type": "number"}}, "top_k": {"type": "number", "default": 10}, "index_path": {"type": "string"}}}},
        {"name": "vfs_graphrag_hybrid_search", "description": "Run hybrid VFS GraphRAG search", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "query_vector": {"type": "array", "items": {"type": "number"}}, "filters": {"type": "object"}, "top_k": {"type": "number", "default": 10}, "index_path": {"type": "string"}}}},
        {"name": "vfs_graphrag_graph_search", "description": "Run graph VFS GraphRAG search", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "entity_ids": {"type": "array", "items": {"type": "string"}}, "hop_limit": {"type": "number", "default": 1}, "top_k": {"type": "number", "default": 10}, "index_path": {"type": "string"}}}},
        {"name": "vfs_graphrag_graph_hybrid_search", "description": "Run graph-hybrid VFS GraphRAG search", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "query_vector": {"type": "array", "items": {"type": "number"}}, "entity_ids": {"type": "array", "items": {"type": "string"}}, "hop_limit": {"type": "number", "default": 1}, "top_k": {"type": "number", "default": 10}, "index_path": {"type": "string"}}}},
        {"name": "vfs_graphrag_export", "description": "Export VFS GraphRAG index records", "inputSchema": {"type": "object", "properties": {"index_path": {"type": "string"}, "output": {"type": "string"}}}},
    ]
