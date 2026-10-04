"""Atomic migration and authenticated recovery tools for Iroh manifests."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .manifest import IrohManifestStore, RecoveryReceipt, migrate_manifest_json


def migrate_file(
    source: str | os.PathLike[str],
    destination: str | os.PathLike[str] | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Validate/migrate a manifest and atomically install canonical v1 JSON.

    An in-place migration always replaces the source only after the complete
    legacy document has validated. A distinct destination is never replaced
    unless ``overwrite`` was explicitly requested.
    """

    source_path = Path(source)
    target = source_path if destination is None else Path(destination)
    if target != source_path and target.exists() and not overwrite:
        raise FileExistsError(target)
    canonical = migrate_manifest_json(source_path.read_bytes()) + b"\n"
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        if target != source_path and not overwrite:
            # Both paths are in the same directory. Linking the fully flushed
            # temporary inode installs it atomically and, unlike an existence
            # check followed by replace, can never clobber a concurrently
            # created destination.
            os.link(temporary, target)
            temporary.unlink()
        else:
            os.replace(temporary, target)
        os.chmod(target, 0o600)
        _fsync_directory(target.parent)
        return target
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


async def recover_namespace(
    client: Any,
    namespace_id: str,
    *,
    dry_run: bool = True,
    history_limit: int | None = None,
) -> RecoveryReceipt:
    """Audit history and optionally repair a namespace to its newest valid head."""

    return await IrohManifestStore(client).recover_head(
        namespace_id, dry_run=dry_run, history_limit=history_limit
    )


def build_parser(*, prog: str = "ipfs-kit-iroh-manifest") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    migration = commands.add_parser(
        "migrate", help="atomically convert an old manifest to canonical schema v1"
    )
    migration.add_argument("source", help="legacy or current manifest JSON")
    migration.add_argument("destination", nargs="?", help="output path; defaults to in-place")
    migration.add_argument(
        "--overwrite", action="store_true", help="replace an existing distinct destination"
    )

    recovery = commands.add_parser(
        "recover", help="verify history and select or restore the newest valid namespace head"
    )
    recovery.add_argument("namespace_id")
    recovery.add_argument(
        "--apply", action="store_true", help="commit the repair (the default is a dry run)"
    )
    recovery.add_argument("--history-limit", type=int)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[[], Any] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "migrate":
            result = migrate_file(args.source, args.destination, overwrite=args.overwrite)
            sys.stdout.write(json.dumps({"path": os.fspath(result), "schema_version": 1}) + "\n")
            return 0
        if client_factory is None:
            parser.error("recover must be invoked by an authenticated application runtime client")
        receipt = asyncio.run(
            recover_namespace(
                client_factory(),
                args.namespace_id,
                dry_run=not args.apply,
                history_limit=args.history_limit,
            )
        )
        sys.stdout.write(
            json.dumps(receipt.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
        )
        return 0
    except (OSError, ValueError):
        # Do not echo exception text: source paths and RPC failures may contain
        # values which do not belong in logs or shell history.
        parser.exit(1, "error: Iroh manifest operation failed\n")


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        # Windows cannot open a directory through this interface. The file was
        # still fully flushed before its atomic replacement.
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
