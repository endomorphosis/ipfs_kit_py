"""Command-line health and metrics diagnostics for managed Iroh instances."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from typing import Any

from .config import IrohServiceConfig, load_config
from .observability import IrohObservability


def build_parser(*, prog: str = "ipfs-kit-iroh-diagnostics") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    parser.add_argument("--instance", default="default", help="isolated Iroh instance name")
    parser.add_argument("--state-root", help="override the platform Iroh state root")
    parser.add_argument("--config", help="explicit service configuration file")
    parser.add_argument(
        "--format",
        choices=("json", "prometheus"),
        default="json",
        help="diagnostic output format",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="do not update the health receipt",
    )
    return parser


def _config(args: argparse.Namespace) -> IrohServiceConfig:
    if args.config:
        return load_config(args.config, state_root=args.state_root)
    return IrohServiceConfig.default(args.instance, state_root=args.state_root, enabled=True)


async def run(
    args: argparse.Namespace,
    *,
    observability_factory: Any = IrohObservability,
) -> str:
    observer = observability_factory(_config(args))
    if args.format == "prometheus":
        return await observer.prometheus(persist=not args.no_persist)
    value = await observer.diagnostics(persist=not args.no_persist)
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        output = asyncio.run(run(parser.parse_args(argv)))
    except (OSError, ValueError):
        parser.exit(2, "error: invalid Iroh diagnostics configuration\n")
    except Exception:
        # Diagnostics exceptions can contain tickets, paths, peer IDs, or RPC
        # request data, so never reflect them to the terminal.
        parser.exit(1, "error: Iroh diagnostics failed\n")
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through main
    raise SystemExit(main())
