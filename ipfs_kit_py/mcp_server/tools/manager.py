"""Registry-backed MCP tool manager facade (package and stdio surfaces)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Mapping, Optional

from ...core.operation_registry import OperationRegistry
from ...core.service_router import DispatchContext, ServiceRouter
from .operation_adapter import (
    MCPPlusPlusToolAdapter,
    MCPToolAdapter,
    assert_no_competing_tool_registration,
    build_mcp_plusplus_tool_adapter,
    build_mcp_tool_adapter,
)


def _tool_groups() -> dict:
    # Local import avoids a circular dependency with tools/__init__.py.
    from . import TOOL_GROUPS

    return TOOL_GROUPS


def _hierarchical_tool_names() -> tuple[str, ...]:
    from . import hierarchical_tool_names

    return hierarchical_tool_names()

logger = logging.getLogger(__name__)


class MCPToolManager:
    """Registry-backed MCP tool manager used by package and stdio surfaces.

    When constructed with a registry and router, every tool list/call goes
    through the canonical adapters.  Without them the manager remains empty
    and rejects calls (fail-closed) rather than inventing a second tool set.
    """

    def __init__(
        self,
        registry: OperationRegistry | None = None,
        router: ServiceRouter | None = None,
        *,
        include_mcpp: bool = True,
    ) -> None:
        logger.info("Initializing MCPToolManager (registry-backed)...")
        self._registry = registry
        self._router = router
        self._mcp: MCPToolAdapter | None = None
        self._mcpp: MCPPlusPlusToolAdapter | None = None
        if registry is not None and router is not None:
            self.bind(registry, router, include_mcpp=include_mcpp)
        logger.info("✓ MCPToolManager initialized.")

    def bind(
        self,
        registry: OperationRegistry,
        router: ServiceRouter,
        *,
        include_mcpp: bool = True,
    ) -> None:
        """Bind (or re-bind) the manager to a registry/router pair."""

        self._registry = registry
        self._router = router
        self._mcp = build_mcp_tool_adapter(registry, router)
        self._mcpp = (
            build_mcp_plusplus_tool_adapter(registry, router) if include_mcpp else None
        )
        adapters = [self._mcp]
        if self._mcpp is not None:
            adapters.append(self._mcpp)
        assert_no_competing_tool_registration(
            *adapters,
            legacy_names=_hierarchical_tool_names(),
        )

    @property
    def mcp_adapter(self) -> MCPToolAdapter | None:
        return self._mcp

    @property
    def mcpp_adapter(self) -> MCPPlusPlusToolAdapter | None:
        return self._mcpp

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return MCP tool descriptors for ``tools/list``."""

        if self._mcp is None:
            return []
        return self._mcp.list_tools()

    def get_mcpp_tools(self) -> List[Dict[str, Any]]:
        if self._mcpp is None:
            return []
        return self._mcpp.list_tools()

    def metadata(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema": "ipfs_kit_py/interfaces/mcp-tool-manager@1",
            "bound": self._mcp is not None,
            "legacy_hierarchical_groups": sorted(_tool_groups().keys()),
            "legacy_hierarchical_tool_count": sum(
                len(tools) for tools in _tool_groups().values()
            ),
        }
        if self._mcp is not None:
            payload["mcp"] = self._mcp.metadata()
        if self._mcpp is not None:
            payload["mcpp"] = self._mcpp.metadata()
        return payload

    async def handle_tool_request(
        self,
        tool_name: str,
        arguments: Optional[Mapping[str, Any]] = None,
        *,
        context: DispatchContext | None = None,
        surface: str = "mcp",
    ) -> Dict[str, Any]:
        """Dispatch a tool call through the bound adapter.

        Missing adapters and unknown tools reject with a structured error; they
        never succeed as a silent no-op.
        """

        arguments = arguments or {}
        adapter: MCPToolAdapter | MCPPlusPlusToolAdapter | None
        if surface in {"mcpp", "mcp++", "mcp-plusplus"}:
            adapter = self._mcpp
        else:
            adapter = self._mcp
        if adapter is None:
            return {
                "success": False,
                "error": {
                    "code": "E_UNAVAILABLE",
                    "message": (
                        "MCP tool manager is not bound to an operation registry; "
                        "call bind(registry, router) before tools/call"
                    ),
                },
            }
        response = await adapter.call_async(
            tool_name, arguments, context=context
        )
        return response.to_dict()

    def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Mapping[str, Any]] = None,
        *,
        context: DispatchContext | None = None,
        surface: str = "mcp",
    ) -> Dict[str, Any]:
        """Synchronous tool call (stdio/package fixture helper)."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.handle_tool_request(
                    tool_name, arguments, context=context, surface=surface
                )
            )
        raise RuntimeError(
            "call_tool cannot run inside an event loop; use handle_tool_request"
        )

    def cleanup(self) -> None:
        """Release adapter references. No external resources are held."""

        logger.info("Cleaning up MCPToolManager...")
        self._mcp = None
        self._mcpp = None
        self._registry = None
        self._router = None
        logger.info("✓ MCPToolManager cleaned up.")


def build_tool_manager(
    registry: OperationRegistry,
    router: ServiceRouter,
    *,
    include_mcpp: bool = True,
) -> MCPToolManager:
    """Construct a bound manager; registration conflicts raise immediately."""

    return MCPToolManager(registry, router, include_mcpp=include_mcpp)


__all__ = [
    "MCPToolManager",
    "build_tool_manager",
]
