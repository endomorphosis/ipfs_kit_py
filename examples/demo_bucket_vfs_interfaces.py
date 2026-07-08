#!/usr/bin/env python3
"""Dependency-light Bucket VFS interface demo for integration contracts.

This fixture mirrors the Bucket VFS contract exposed by ipfs_kit_py for
`external/ipfs_datasets` interoperability tests. It intentionally avoids live
IPFS, Kubo, DuckDB, or network calls; the tests only need parseable constants,
demo entrypoints, and scanner-visible CLI/MCP operation names.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
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
    """Small in-memory bucket record used by the static demo report."""

    name: str
    cid: str
    files: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_demo_report() -> dict[str, Any]:
    """Return deterministic Bucket VFS CLI/MCP coverage evidence."""

    bucket = DemoBucket(
        name="meta-wearables-dat-android-display-events",
        cid="bafy-demo-bucket-vfs-interface",
        files=("/wearables/meta/dat/android/display/events/latest.json",),
    )
    return {
        "bucket": bucket.as_dict(),
        "cli_commands": BUCKET_VFS_CLI_COMMANDS,
        "mcp_tools": BUCKET_VFS_MCP_TOOLS,
        "routes": {
            "bucket_export_car": "export Bucket VFS data as CAR",
            "bucket_cross_query": "query across Bucket VFS backends",
        },
    }


async def demo_cli_interface() -> dict[str, Any]:
    """Demonstrate the stable CLI command names without shelling out."""

    report = build_demo_report()
    return {
        "interface": "cli",
        "commands": report["cli_commands"],
        "example": "ipfs_kit_py bucket create meta-wearables-dat-android-display-events",
    }


async def demo_mcp_api() -> dict[str, Any]:
    """Demonstrate the stable MCP tool names without starting a server."""

    report = build_demo_report()
    return {
        "interface": "mcp",
        "tools": report["mcp_tools"],
        "example_tool": "bucket_cross_query",
    }


if __name__ == "__main__":
    print(build_demo_report())
