"""Hypercorn-compatible native HTTP application for the kit Profile H seller."""

from __future__ import annotations

from typing import Any

from mcplusplus_profile_h import ProfileHHttpApp

from .profile_h import PaidKitService


def create_profile_h_http_app(service: PaidKitService) -> ProfileHHttpApp:
    """Return the ASGI payment control plane for one configured kit seller."""
    return ProfileHHttpApp(service.control_plane)


async def serve_profile_h_http(service: PaidKitService, host: str, port: int) -> None:
    """Serve a configured seller using Hypercorn; no FastAPI dependency is needed."""
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"{host}:{port}"]
    await serve(create_profile_h_http_app(service), config)


__all__ = ["create_profile_h_http_app", "serve_profile_h_http"]
