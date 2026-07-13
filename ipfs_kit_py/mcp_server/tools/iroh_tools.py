"""Managed Iroh diagnostic operations for the canonical MCP++ registry."""

from __future__ import annotations

import asyncio
from typing import Any

import anyio

from ipfs_kit_py.mcp.servers.iroh_mcp_tools import handle_iroh_diagnostics


async def iroh_diagnostics(
    instance: str = "default",
    format: str = "health",
    persist: bool = True,
) -> dict[str, Any]:
    """Return a redacted Iroh health receipt or bounded-label metrics."""

    arguments = {"instance": instance, "format": format, "persist": persist}
    # The managed Iroh client has an explicit asyncio transport contract while
    # the canonical MCP++ server runs on Trio. Isolate the probe in its own
    # asyncio loop so both runtimes retain their cancellation/event-loop rules.
    return await anyio.to_thread.run_sync(lambda: asyncio.run(handle_iroh_diagnostics(arguments)))


__all__ = ["iroh_diagnostics"]
