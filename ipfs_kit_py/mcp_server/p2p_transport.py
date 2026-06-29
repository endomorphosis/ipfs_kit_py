"""Optional libp2p P2P transport for the MCP++ server (graceful).

Serves the same JSON-RPC handler over a libp2p stream protocol when py-libp2p is
installed, so peers can call tools over /mcp+p2p/1.0.0 (MCP++ Profile E). When
libp2p is unavailable, ``HAVE_LIBP2P`` is False and the server stays HTTP/stdio.
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

PROTOCOL_ID = "/mcp+p2p/1.0.0"
HAVE_LIBP2P = False

try:  # py-libp2p is an optional extra
    import libp2p  # type: ignore  # noqa: F401
    HAVE_LIBP2P = True
except Exception:  # pragma: no cover
    libp2p = None  # type: ignore


async def handle_stream_message(raw: bytes, handler: Callable[[dict], Awaitable[dict]]) -> bytes:
    """Decode a JSON-RPC request, dispatch it, encode the response.

    Pure framing logic shared by the libp2p stream handler; testable without a
    live peer so Profile E round-trips can be exercised in CI.
    """
    resp = await handler(json.loads(raw))
    return json.dumps(resp).encode()


async def serve_p2p(handler: Callable[[dict], Awaitable[dict]]) -> None:
    """Serve the MCP handler over libp2p. Raises if libp2p is unavailable."""
    if not HAVE_LIBP2P:  # pragma: no cover
        raise RuntimeError("libp2p transport requires the 'libp2p' extra")
    from libp2p import new_host  # type: ignore

    host = new_host()

    async def _stream(stream):  # pragma: no cover - needs live libp2p
        data = await stream.read()
        await stream.write(await handle_stream_message(data, handler))
        await stream.close()

    host.set_stream_handler(PROTOCOL_ID, _stream)
    import anyio
    await anyio.sleep_forever()
