#!/usr/bin/env python3
"""
Root entrypoint for the MCP Dashboard used by tests.
This file is a thin wrapper that imports and exposes the packaged
implementation to avoid divergence and corruption.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict

# Prefer the packaged implementation (stable server variant)
try:
    from ipfs_kit_py.mcp.dashboard.consolidated_server import ConsolidatedMCPDashboard  # type: ignore
except Exception as e:  # pragma: no cover
    # If the packaged dashboard cannot be imported, surface a helpful error
    raise RuntimeError(
        "Failed to import packaged dashboard implementation. "
        "Please ensure the package is installed and importable.\n" + str(e)
    )


def build_app(config: Dict[str, Any] | None = None):
    d = ConsolidatedMCPDashboard(config or {})
    return d.app


# Expose `app` WSGI/ASGI-style for uvicorn
app = build_app()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IPFS Kit MCP Dashboard (root wrapper)")
    # Prefer MCP_HOST/MCP_PORT when present (used by tests), fallback to HOST/PORT, then defaults
    default_host = os.environ.get("MCP_HOST") or os.environ.get("HOST") or "127.0.0.1"
    default_port = int(os.environ.get("MCP_PORT") or os.environ.get("PORT") or "8081")
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--api-token", dest="api_token", default=os.environ.get("MCP_API_TOKEN"))
    parser.add_argument("--data-dir", dest="data_dir", default=os.environ.get("IPFS_KIT_DATA_DIR"))
    args = parser.parse_args(argv)

    cfg: Dict[str, Any] = {
        "host": args.host,
        "port": args.port,
        "debug": bool(args.debug),
    }
    if args.api_token:
        cfg["api_token"] = args.api_token
    if args.data_dir:
        cfg["data_dir"] = args.data_dir

    dash = ConsolidatedMCPDashboard(cfg)

    # Prefer sync wrapper to match previous behavior in tests
    try:
        dash.run_sync()
        return 0
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":
    sys.exit(main())
