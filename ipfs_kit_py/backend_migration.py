"""Command-line migration for versioned named backend documents."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence

from .backend_manager import BackendManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ipfs-kit-backend-migrate",
        description="Validate and migrate named IPFS Kit backend configurations",
    )
    parser.add_argument("names", nargs="*", help="backend names; omit to migrate every backend")
    parser.add_argument(
        "--root",
        default=os.path.expanduser("~/.ipfs_kit"),
        help="IPFS Kit state root (default: ~/.ipfs_kit)",
    )
    parser.add_argument("--no-backup", action="store_true", help="do not retain pre-v1 YAML backups")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = BackendManager(args.root)
    if args.names:
        results = {
            name: manager.migrate_backend(name, backup=not args.no_backup)
            for name in args.names
        }
        report = {
            "results": results,
            "total": len(results),
            "failed": sum("error" in result for result in results.values()),
        }
    else:
        report = manager.migrate_backends(backup=not args.no_backup)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
