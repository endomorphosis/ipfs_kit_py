#!/usr/bin/env python3
"""Dependency-light Bucket VFS interface demo.

This file is intentionally import-safe for integration scanners. It records the
CLI commands and MCP tools exposed by the Bucket VFS surface without requiring a
running IPFS daemon, DuckDB, Kubo, or external storage backend.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


BUCKET_VFS_CLI_COMMANDS = (
    "create",
    "list",
    "delete",
    "add-file",
    "export",
    "query",
)

BUCKET_VFS_MCP_TOOLS = (
    "bucket_create",
    "bucket_list",
    "bucket_delete",
    "bucket_add_file",
    "bucket_export_car",
    "bucket_cross_query",
    "bucket_get_info",
    "bucket_status",
)


@dataclass(frozen=True)
class DemoBucket:
    """Serializable Bucket VFS demo bucket."""

    name: str
    bucket_type: str = "DATASET"
    vfs_structure: str = "HYBRID"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def demo_cli_interface() -> dict[str, Any]:
    """Return the Bucket VFS CLI command contract."""

    return {
        "binary": "ipfs-kit bucket-vfs",
        "commands": list(BUCKET_VFS_CLI_COMMANDS),
        "examples": {
            "create": "ipfs-kit bucket-vfs create meta-display-events",
            "list": "ipfs-kit bucket-vfs list",
            "delete": "ipfs-kit bucket-vfs delete meta-display-events",
            "add-file": "ipfs-kit bucket-vfs add-file meta-display-events latest.json",
            "export": "ipfs-kit bucket-vfs export meta-display-events --format car",
            "query": "ipfs-kit bucket-vfs query meta-display-events --sql SELECT",
        },
    }


def demo_mcp_api() -> dict[str, Any]:
    """Return the Bucket VFS MCP API contract."""

    return {
        "server": "ipfs_kit.bucket_vfs",
        "tools": list(BUCKET_VFS_MCP_TOOLS),
        "handoff_tools": [
            "bucket_create",
            "bucket_add_file",
            "bucket_export_car",
            "bucket_cross_query",
        ],
    }


def bucket_export_car(bucket: DemoBucket) -> dict[str, str]:
    """Build a deterministic CAR export descriptor for a demo bucket."""

    return {
        "bucket": bucket.name,
        "operation": "bucket_export_car",
        "format": "car",
        "content_cid": f"sha256:{bucket.name}",
    }


def bucket_cross_query(bucket: DemoBucket, query: str = "SELECT * FROM pins") -> dict[str, str]:
    """Build a deterministic cross-bucket query descriptor."""

    return {
        "bucket": bucket.name,
        "operation": "bucket_cross_query",
        "query": query,
    }


def build_demo_report() -> dict[str, Any]:
    """Return a scanner-visible demo report for Bucket VFS interop tests."""

    bucket = DemoBucket("meta-wearables-dat-android-display-events")
    return {
        "bucket": bucket.as_dict(),
        "cli": demo_cli_interface(),
        "mcp": demo_mcp_api(),
        "export": bucket_export_car(bucket),
        "query": bucket_cross_query(bucket),
    }


if __name__ == "__main__":
    print(build_demo_report())
