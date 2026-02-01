"""Compatibility shim for `mcp.bucket_vfs_mcp_tools`.

The canonical implementation lives under `ipfs_kit_py.mcp.servers.bucket_vfs_mcp_tools`.

Why this file exists:
- Some tests patch `mcp.bucket_vfs_mcp_tools.get_bucket_manager` and expect the
  patched value to be used by handler functions.
- A plain `from ... import *` would bind handlers to the *upstream module's*
  globals, so the patch would not take effect.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ipfs_kit_py.mcp.servers import bucket_vfs_mcp_tools as _impl

# Re-export key flags/types for compatibility
Tool = _impl.Tool
TextContent = _impl.TextContent
BUCKET_VFS_AVAILABLE = _impl.BUCKET_VFS_AVAILABLE
HAS_DATASETS = getattr(_impl, "HAS_DATASETS", False)
HAS_ACCELERATE = getattr(_impl, "HAS_ACCELERATE", False)
MCP_AVAILABLE = getattr(_impl, "MCP_AVAILABLE", False)


def create_bucket_tools() -> List[Tool]:
	return _impl.create_bucket_tools()


def get_bucket_manager(ipfs_client=None, storage_path: str = "/tmp/mcp_buckets"):
	"""Get or create the global bucket manager.

	This function is intentionally defined in this shim module so tests can
	patch it and have handler functions use the patched value.
	"""

	return _impl.get_bucket_manager(ipfs_client=ipfs_client, storage_path=storage_path)


def _text(payload: Dict[str, Any]) -> List[TextContent]:
	return [TextContent(type="text", text=json.dumps(payload))]


async def handle_bucket_create(arguments: Dict[str, Any]):
	bucket_name = arguments.get("bucket_name")
	if not bucket_name:
		return _text({"success": False, "error": "Missing required argument: bucket_name"})

	storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
	manager = get_bucket_manager(storage_path=storage_path)
	if manager is None:
		return _text({"success": False, "error": "Bucket manager not available"})

	result = await manager.create_bucket(
		bucket_name=bucket_name,
		bucket_type=arguments.get("bucket_type", "general"),
		vfs_structure=arguments.get("vfs_structure", "hybrid"),
		metadata=arguments.get("metadata") or {},
	)

	data = (result or {}).get("data") if isinstance(result, dict) else None
	return _text({"success": bool((result or {}).get("success")), "bucket": data or {}})


async def handle_bucket_list(arguments: Dict[str, Any]):
	storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
	manager = get_bucket_manager(storage_path=storage_path)
	if manager is None:
		return _text({"success": False, "error": "Bucket manager not available"})

	result = await manager.list_buckets(detailed=bool(arguments.get("detailed", False)))
	data = (result or {}).get("data", {}) if isinstance(result, dict) else {}
	buckets = data.get("buckets") or []
	total = data.get("total_count")
	if total is None:
		total = len(buckets)
	return _text({"success": bool((result or {}).get("success")), "buckets": buckets, "total_buckets": total})


async def handle_bucket_add_file(arguments: Dict[str, Any]):
	bucket_name = arguments.get("bucket_name")
	file_path = arguments.get("file_path")
	if not bucket_name or not file_path:
		return _text({"success": False, "error": "Missing required arguments: bucket_name, file_path"})

	storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
	manager = get_bucket_manager(storage_path=storage_path)
	if manager is None:
		return _text({"success": False, "error": "Bucket manager not available"})

	bucket = await manager.get_bucket(bucket_name)
	if bucket is None:
		return _text({"success": False, "error": f"Bucket not found: {bucket_name}"})

	result = await bucket.add_file(
		file_path=file_path,
		content=arguments.get("content"),
		content_type=arguments.get("content_type", "text"),
	)
	data = (result or {}).get("data") if isinstance(result, dict) else None
	return _text({"success": bool((result or {}).get("success")), "file": data or {}})


async def handle_bucket_cross_query(arguments: Dict[str, Any]):
	sql_query = arguments.get("sql_query")
	if not sql_query:
		return _text({"success": False, "error": "Missing required argument: sql_query"})

	storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
	manager = get_bucket_manager(storage_path=storage_path)
	if manager is None:
		return _text({"success": False, "error": "Bucket manager not available"})

	result = await manager.cross_bucket_query(sql_query=sql_query)
	if not isinstance(result, dict) or not result.get("success"):
		return _text({"success": False, "error": (result or {}).get("error", "Query failed")})

	data = result.get("data", {})
	columns = data.get("columns") or []
	rows = data.get("rows") or []

	# Normalize to list-of-dicts for JSON responses (what tests expect).
	results: List[Dict[str, Any]] = []
	for row in rows:
		try:
			results.append({columns[i]: row[i] for i in range(min(len(columns), len(row)))})
		except Exception:
			results.append({"row": row})

	return _text({"success": True, "results": results})


async def handle_bucket_export_car(arguments: Dict[str, Any]):
	bucket_name = arguments.get("bucket_name")
	if not bucket_name:
		return _text({"success": False, "error": "Missing required argument: bucket_name"})

	storage_path = arguments.get("storage_path", "/tmp/mcp_buckets")
	manager = get_bucket_manager(storage_path=storage_path)
	if manager is None:
		return _text({"success": False, "error": "Bucket manager not available"})

	result = await manager.export_bucket_to_car(
		bucket_name=bucket_name,
		include_indexes=bool(arguments.get("include_indexes", True)),
	)
	data = (result or {}).get("data") if isinstance(result, dict) else None
	return _text({"success": bool((result or {}).get("success")), "export": data or {}})


# Legacy API surface (rarely used by tests, but kept for compatibility)
def handle_bucket_tool(*args: Any, **kwargs: Any):
	return _impl.handle_bucket_tool(*args, **kwargs)


__all__ = [
	"Tool",
	"TextContent",
	"BUCKET_VFS_AVAILABLE",
	"HAS_DATASETS",
	"HAS_ACCELERATE",
	"MCP_AVAILABLE",
	"create_bucket_tools",
	"get_bucket_manager",
	"handle_bucket_tool",
	"handle_bucket_create",
	"handle_bucket_list",
	"handle_bucket_add_file",
	"handle_bucket_cross_query",
	"handle_bucket_export_car",
]
