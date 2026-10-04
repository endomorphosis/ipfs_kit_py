#!/usr/bin/env python3
"""Demonstrate Bucket VFS CLI and MCP interfaces.

This example is intentionally dependency-light so repository-level interop
tests can parse it as stable evidence for HAO-738 without starting an IPFS
daemon. The concrete tool names match the Bucket VFS implementation summary in
``docs/implementation/BUCKET_VFS_INTERFACES_COMPLETE.md`` and the MCP tool
surface in ``mcp/bucket_vfs_mcp_tools.py``.
"""

from __future__ import annotations

import argparse
import json
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
    """Small serializable bucket record used by the demo output."""

    name: str
    bucket_type: str
    vfs_structure: str
    file_count: int
    root_cid: str


def demo_cli_interface() -> list[str]:
    """Return example CLI commands for S3-like Bucket VFS semantics."""

    return [
        "python -m ipfs_kit_py.cli bucket create wearables-events --type dataset --structure hybrid",
        "python -m ipfs_kit_py.cli bucket list --detailed",
        (
            "python -m ipfs_kit_py.cli bucket add-file wearables-events "
            "display/latest.json '{\"state\":\"STARTED\"}'"
        ),
        "python -m ipfs_kit_py.cli bucket export wearables-events --include-indexes",
        (
            "python -m ipfs_kit_py.cli bucket query "
            "'SELECT bucket_name, file_path FROM files'"
        ),
    ]


def demo_mcp_api() -> dict[str, dict[str, Any]]:
    """Return example MCP calls for the Bucket VFS tool surface."""

    return {
        "bucket_create": {
            "name": "wearables-events",
            "bucket_type": "DATASET",
            "vfs_structure": "HYBRID",
        },
        "bucket_add_file": {
            "bucket": "wearables-events",
            "path": "display/latest.json",
            "content_type": "json",
        },
        "bucket_export_car": {
            "bucket": "wearables-events",
            "include_indexes": True,
        },
        "bucket_cross_query": {
            "query": "SELECT bucket_name, file_path, cid FROM files",
        },
        "bucket_get_info": {
            "bucket": "wearables-events",
        },
        "bucket_status": {
            "include_backends": True,
        },
    }


def build_demo_bucket() -> DemoBucket:
    """Build a deterministic example bucket record."""

    return DemoBucket(
        name="wearables-events",
        bucket_type="DATASET",
        vfs_structure="HYBRID",
        file_count=1,
        root_cid="sha256:demo-wearables-events-root",
    )


def build_demo_report() -> dict[str, Any]:
    """Build a parseable report covering CLI, MCP, CAR export, and SQL query evidence."""

    return {
        "description": "Bucket VFS CLI and MCP interface demo",
        "cli_commands": demo_cli_interface(),
        "mcp_tools": list(BUCKET_VFS_MCP_TOOLS),
        "mcp_examples": demo_mcp_api(),
        "bucket": asdict(build_demo_bucket()),
        "interface_consistency": {
            "shared_storage_backend": True,
            "s3_like_bucket_semantics": True,
            "ipld_compatibility": True,
            "analytics_integration": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the demo report as JSON")
    args = parser.parse_args(argv)

    report = build_demo_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Bucket VFS CLI commands:")
        for command in report["cli_commands"]:
            print(f"- {command}")
        print("Bucket VFS MCP tools:")
        for tool_name in report["mcp_tools"]:
            print(f"- {tool_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
