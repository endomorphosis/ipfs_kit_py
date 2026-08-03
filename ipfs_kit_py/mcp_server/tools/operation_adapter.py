"""Registry-derived MCP and MCP++ tool adapters (KITA-037).

The operation registry owns names, schemas, capabilities, and authorization.
:class:`ServiceRouter` owns admission and execution.  These adapters own only
transport projection: MCP ``tools/list`` / ``tools/call`` schemas and the
stdio / HTTP / P2P framing fixtures used for all-interface parity.

Competing registrations never win silently: a second registration of the same
tool name for a transport raises :class:`DuplicateToolRegistrationError`.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

from ...core.operation_contracts import (
    ErrorCategory,
    ErrorCode,
    OperationResult,
    OperationState,
    Retryability,
    StorageError,
    canonical_json,
)
from ...core.operation_registry import (
    AuthorizationClass,
    OperationRegistry,
    UnknownOperationError,
    UnsupportedOperationError,
)
from ...core.service_router import (
    AsyncDispatchRequiredError,
    AuthorizationDeniedError,
    CapabilityUnavailableError,
    DispatchContext,
    HandlerBindingError,
    HandlerNotBoundError,
    ServiceRouter,
    ServiceRouterError,
)
from ...high_level_api.operation_adapter import (
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_RESPONSE_SCHEMA,
    EXIT_CODES,
    AdapterOperationProjection,
    AdapterResponse,
    _canonical_result,
    _failure,
    _run_async_synchronously,
)


# ---------------------------------------------------------------------------
# Schema / transport constants
# ---------------------------------------------------------------------------

MCP_ADAPTER_SCHEMA: Final[str] = "ipfs_kit_py/interfaces/mcp-tool-adapter@1"
MCP_PLUSPLUS_ADAPTER_SCHEMA: Final[str] = (
    "ipfs_kit_py/interfaces/mcp-plusplus-tool-adapter@1"
)
MCP_TOOL_SCHEMA: Final[str] = "ipfs_kit_py/interfaces/mcp-tool@1"
MCP_TRANSPORT: Final[str] = "mcp"
MCPP_TRANSPORT: Final[str] = "mcpp"
MCP_STDIO_TRANSPORT: Final[str] = "mcp-stdio"
MCP_HTTP_TRANSPORT: Final[str] = "mcp-http"
MCP_P2P_TRANSPORT: Final[str] = "mcp-p2p"

MCPToolAdapter_V1: Final[str] = MCP_ADAPTER_SCHEMA
MCPPlusPlusToolAdapter_V1: Final[str] = MCP_PLUSPLUS_ADAPTER_SCHEMA

# Framing identifiers for MCP++ parity fixtures.  Framing never changes the
# admitted operation, authorization decision, or semantic result payload.
MCPP_FRAMINGS: Final[tuple[str, ...]] = ("stdio", "http", "p2p")
FRAMING_TRANSPORTS: Final[Mapping[str, str]] = {
    "stdio": MCP_STDIO_TRANSPORT,
    "http": MCP_HTTP_TRANSPORT,
    "p2p": MCP_P2P_TRANSPORT,
}

# Fields that may differ across transports without constituting a semantic
# parity failure.  Everything else in the adapter response must match.
TRANSPORT_ONLY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "request_id",
        "related_request_id",
        "timing",
        "elapsed_ms",
        "duration_ms",
        "started_at_ms",
        "finished_at_ms",
        "timestamp",
        "wall_time_ms",
        "transport",
        "framing",
        "jsonrpc",
        "id",
        "content_id",
        "http_status",
        "protocol_id",
        "stream_id",
    }
)


class MCPToolAdapterError(ValueError):
    """Fail-closed MCP adapter failures."""


class DuplicateToolRegistrationError(MCPToolAdapterError):
    """Two tools claim the same public name for one transport."""


class UnknownToolError(MCPToolAdapterError):
    """No projected tool owns the supplied public name."""


# ---------------------------------------------------------------------------
# Semantic normalization
# ---------------------------------------------------------------------------


def strip_transport_fields(value: Any) -> Any:
    """Remove request IDs, timings, and other transport-only fields.

    Used by all-interface parity: after stripping, package / Python / CLI /
    MCP stdio / HTTP / P2P payloads must be identical for the same fixture.
    """

    if isinstance(value, Mapping):
        return {
            key: strip_transport_fields(item)
            for key, item in value.items()
            if key not in TRANSPORT_ONLY_KEYS
        }
    if isinstance(value, list):
        return [strip_transport_fields(item) for item in value]
    if isinstance(value, tuple):
        return [strip_transport_fields(item) for item in value]
    return value


def semantic_payload(response: AdapterResponse | Mapping[str, Any]) -> dict[str, Any]:
    """Return the transport-independent comparison record for a response."""

    if isinstance(response, AdapterResponse):
        payload = response.to_dict()
    else:
        payload = dict(response)
    return strip_transport_fields(payload)


# ---------------------------------------------------------------------------
# Tool descriptor projection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPToolDescriptor:
    """One MCP/MCP++ tool derived solely from a registry transport projection."""

    projection: AdapterOperationProjection
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        if not self.projection.applicable or self.projection.name is None:
            raise ValueError("non-applicable operations do not have MCP tool descriptors")
        name = self.projection.name
        description = self.description or (
            f"Canonical registry operation {self.projection.operation_id}"
        )
        return {
            "schema": MCP_TOOL_SCHEMA,
            "contract_version": ADAPTER_CONTRACT_VERSION,
            "name": name,
            "description": description,
            "operation_id": self.projection.operation_id,
            "version": self.projection.version,
            "request_schema": self.projection.request_schema,
            "result_schema": self.projection.result_schema,
            "error_schema": self.projection.error_schema,
            "capability": self.projection.capability,
            "support_tier": self.projection.support_tier,
            "access_requirement": dict(self.projection.authorization),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request": {
                        "description": "Canonical operation request body",
                        "schema": self.projection.request_schema,
                    },
                    "principal": {
                        "type": "string",
                        "description": "Optional dispatch principal",
                        "schema": "ipfs_kit_py/interfaces/principal@1",
                    },
                    "context": {
                        "type": "object",
                        "description": "Optional dispatch context attributes",
                        "default": {},
                        "schema": "ipfs_kit_py/interfaces/dispatch-context-attributes@1",
                    },
                },
                "required": ["request"],
            },
            "response_schema": ADAPTER_RESPONSE_SCHEMA,
            "exit_codes": {code.value: value for code, value in EXIT_CODES.items()},
        }


class _ToolRegistrationTable:
    """Fail-closed map of public tool names → operation ids for one transport.

    The table is populated only from registry projections (or explicit
    ``register`` calls during tests).  A second claim on a name raises rather
    than overwriting the first winner.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, str] = {}
        self._by_operation: dict[str, str] = {}

    def register(self, name: str, operation_id: str) -> None:
        if not isinstance(name, str) or not name:
            raise MCPToolAdapterError("tool name must be a non-empty string")
        if not isinstance(operation_id, str) or not operation_id:
            raise MCPToolAdapterError("operation_id must be a non-empty string")
        existing = self._by_name.get(name)
        if existing is not None and existing != operation_id:
            raise DuplicateToolRegistrationError(
                f"tool name {name!r} is already registered for operation "
                f"{existing!r}; refusing silent overwrite by {operation_id!r}"
            )
        prior_name = self._by_operation.get(operation_id)
        if prior_name is not None and prior_name != name:
            raise DuplicateToolRegistrationError(
                f"operation {operation_id!r} already projects as tool "
                f"{prior_name!r}; refusing competing name {name!r}"
            )
        self._by_name[name] = operation_id
        self._by_operation[operation_id] = name

    def resolve(self, name: str) -> str:
        try:
            return self._by_name[name]
        except KeyError as error:
            raise UnknownToolError(f"unknown tool {name!r}") from error

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_name))

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._by_name

    def __len__(self) -> int:
        return len(self._by_name)


class _MCPBaseAdapter:
    """Shared projection, admission, and serialization for MCP tool adapters."""

    TRANSPORT: str = MCP_TRANSPORT
    SCHEMA: str = MCP_ADAPTER_SCHEMA

    def __init__(self, registry: OperationRegistry, router: ServiceRouter) -> None:
        if not isinstance(registry, OperationRegistry):
            raise TypeError("registry must be an OperationRegistry")
        if not isinstance(router, ServiceRouter):
            raise TypeError("router must be a ServiceRouter")
        if router.registry is not registry:
            raise ValueError("router must be bound to the supplied registry")
        self.registry = registry
        self.router = router
        self._registrations = _ToolRegistrationTable()
        self._seed_registrations()

    def _seed_registrations(self) -> None:
        for projection in self.registry.transport_projection(self.TRANSPORT):
            self._registrations.register(projection.name, projection.operation_id)

    def operation_projections(self) -> tuple[AdapterOperationProjection, ...]:
        projected = {
            item.operation_id: AdapterOperationProjection.from_transport_projection(item)
            for item in self.registry.transport_projection(self.TRANSPORT)
        }
        records: list[AdapterOperationProjection] = []
        for definition in self.registry.operations():
            record = projected.get(definition.operation_id)
            if record is None:
                authorization: dict[str, str] = {
                    "classification": definition.authorization.classification.value,
                }
                if definition.authorization.resource is not None:
                    authorization["resource"] = definition.authorization.resource
                    authorization["ability"] = definition.authorization.ability or ""
                record = AdapterOperationProjection(
                    transport=self.TRANSPORT,
                    operation_id=definition.operation_id,
                    version=definition.version,
                    applicable=False,
                    reason=(
                        f"operation does not advertise a {self.TRANSPORT} transport name"
                    ),
                    name=None,
                    request_schema=definition.request_schema,
                    result_schema=definition.result_schema,
                    error_schema=definition.error_schema,
                    capability=definition.capability,
                    support_tier=definition.support_tier.value,
                    authorization=authorization,
                )
            records.append(record)
        return tuple(records)

    projections = operation_projections

    def tools(self) -> tuple[MCPToolDescriptor, ...]:
        return tuple(
            MCPToolDescriptor(projection)
            for projection in self.operation_projections()
            if projection.applicable
        )

    tool_descriptors = tools

    def list_tools(self) -> list[dict[str, Any]]:
        """MCP ``tools/list`` payload projected from the registry."""

        return [tool.to_dict() for tool in self.tools()]

    def metadata(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": ADAPTER_CONTRACT_VERSION,
            "transport": self.TRANSPORT,
            "operations": [item.to_dict() for item in self.operation_projections()],
            "tools": self.list_tools(),
            "response_schema": ADAPTER_RESPONSE_SCHEMA,
            "exit_codes": {code.value: value for code, value in EXIT_CODES.items()},
            "transport_only_fields": sorted(TRANSPORT_ONLY_KEYS),
        }

    def _projection_for_name(self, name: str) -> AdapterOperationProjection:
        definition = self.registry.resolve_transport(self.TRANSPORT, name)
        for projection in self.operation_projections():
            if projection.operation_id == definition.operation_id:
                return projection
        raise UnknownToolError(
            f"tool {name!r} has no {self.TRANSPORT} adapter projection"
        )

    def _response_for_value(
        self,
        projection: AdapterOperationProjection,
        value: Any,
    ) -> AdapterResponse:
        """Mirror the Python/CLI serializer so semantic payloads match."""

        if isinstance(value, StorageError):
            return AdapterResponse(operation=projection, error=value)
        result = _canonical_result(value)
        if isinstance(value, OperationResult) and not value.success:
            return AdapterResponse(
                operation=projection,
                result=result,
                error=value.error
                or _failure(RuntimeError("operation returned a failed result"), projection),
            )
        return AdapterResponse(operation=projection, result=result)

    def _input_error(self, message: str = "tool request was rejected") -> AdapterResponse:
        return AdapterResponse(
            operation=None,
            error=StorageError(
                code=ErrorCode.INVALID_REQUEST,
                category=ErrorCategory.VALIDATION,
                message=message,
                retryability=Retryability.NEVER,
                state=OperationState.REJECTED,
            ),
        )

    def _parse_arguments(
        self, arguments: Any
    ) -> tuple[Any, str | None, Mapping[str, Any]]:
        if arguments is None:
            return {}, None, {}
        if not isinstance(arguments, Mapping):
            raise MCPToolAdapterError("tool arguments must be an object")
        if "request" in arguments:
            request = arguments["request"]
            principal = arguments.get("principal")
            context = arguments.get("context") or {}
        else:
            # Bare argument object is the request body; reserved keys stay out.
            request = {
                key: value
                for key, value in arguments.items()
                if key not in {"principal", "context", "_mcppp_envelope"}
            }
            principal = arguments.get("principal")
            context = arguments.get("context") or {}
        if principal is not None and (not isinstance(principal, str) or not principal):
            raise MCPToolAdapterError("principal must be a non-empty string when provided")
        if not isinstance(context, Mapping):
            raise MCPToolAdapterError("context must be an object")
        return request, principal, context

    async def call_async(
        self,
        name: str,
        arguments: Any = None,
        *,
        context: DispatchContext | None = None,
    ) -> AdapterResponse:
        projection: AdapterOperationProjection | None = None
        try:
            if not isinstance(name, str) or not name:
                raise MCPToolAdapterError("tool name must be a non-empty string")
            projection = self._projection_for_name(name)
            request, principal, attributes = self._parse_arguments(arguments)
            if context is None:
                context = DispatchContext(principal=principal, attributes=attributes)
            value = await self.router.dispatch_async(
                projection.operation_id, request, context=context
            )
            return self._response_for_value(projection, value)
        except asyncio.CancelledError as error:
            return AdapterResponse(operation=projection, error=_failure(error, projection))
        except (
            MCPToolAdapterError,
            UnknownToolError,
            UnknownOperationError,
        ) as error:
            if projection is None:
                return self._input_error(str(error) or "tool request was rejected")
            return AdapterResponse(operation=projection, error=_failure(error, projection))
        except Exception as error:
            return AdapterResponse(operation=projection, error=_failure(error, projection))

    def call(
        self,
        name: str,
        arguments: Any = None,
        *,
        context: DispatchContext | None = None,
    ) -> AdapterResponse:
        return _run_async_synchronously(
            lambda: self.call_async(name, arguments, context=context)
        )

    invoke = call
    execute = call


class MCPToolAdapter(_MCPBaseAdapter):
    """Classic MCP ``tools/list`` / ``tools/call`` adapter (stdio-facing)."""

    TRANSPORT: Final[str] = MCP_TRANSPORT
    SCHEMA: Final[str] = MCP_ADAPTER_SCHEMA

    async def handle_jsonrpc(self, message: Mapping[str, Any]) -> dict[str, Any]:
        """Handle one MCP JSON-RPC request for stdio-style fixtures."""

        if not isinstance(message, Mapping):
            return _jsonrpc_error(None, -32600, "Invalid Request")
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": self.list_tools()},
            }
        if method == "tools/call":
            if not isinstance(params, Mapping):
                return _jsonrpc_error(request_id, -32602, "Invalid params")
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str):
                return _jsonrpc_error(request_id, -32602, "tool name is required")
            response = await self.call_async(name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "transport": self.TRANSPORT,
                    "framing": "stdio",
                    **response.to_dict(),
                },
            }
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "ipfs-kit-mcp-adapter", "version": "1"},
                    "capabilities": {"tools": {}},
                },
            }
        return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


class MCPPlusPlusToolAdapter(_MCPBaseAdapter):
    """MCP++ adapter with stdio, HTTP, and P2P framing fixtures.

    All three framings admit through the same registry transport (``mcpp``)
    and produce identical semantic payloads after transport-only fields are
    stripped.  Protected tools require the same
    :class:`DispatchContext`/authorizer decision regardless of framing.
    """

    TRANSPORT: Final[str] = MCPP_TRANSPORT
    SCHEMA: Final[str] = MCP_PLUSPLUS_ADAPTER_SCHEMA
    FRAMINGS: Final[tuple[str, ...]] = MCPP_FRAMINGS

    def metadata(self) -> dict[str, Any]:
        base = super().metadata()
        base["framings"] = list(self.FRAMINGS)
        base["framing_transports"] = dict(FRAMING_TRANSPORTS)
        return base

    async def call_framed(
        self,
        framing: str,
        name: str,
        arguments: Any = None,
        *,
        context: DispatchContext | None = None,
    ) -> dict[str, Any]:
        """Invoke a tool and attach framing metadata (stripped for parity)."""

        if framing not in self.FRAMINGS:
            raise MCPToolAdapterError(
                f"unknown MCP++ framing {framing!r}; expected one of {self.FRAMINGS}"
            )
        response = await self.call_async(name, arguments, context=context)
        payload = response.to_dict()
        return {
            "transport": FRAMING_TRANSPORTS[framing],
            "framing": framing,
            **payload,
        }

    def call_stdio(self, name: str, arguments: Any = None, **kwargs: Any) -> dict[str, Any]:
        # KITA-044: shared hot-path bound across MCP++ transport projections.
        from ipfs_kit_py.core.performance import HotPathGate

        with HotPathGate(payload_bytes=0, fairness_class="mcp-stdio"):
            return _run_async_synchronously(
                lambda: self.call_framed("stdio", name, arguments, **kwargs)
            )

    def call_http(self, name: str, arguments: Any = None, **kwargs: Any) -> dict[str, Any]:
        from ipfs_kit_py.core.performance import HotPathGate

        with HotPathGate(payload_bytes=0, fairness_class="mcp-http"):
            return _run_async_synchronously(
                lambda: self.call_framed("http", name, arguments, **kwargs)
            )

    def call_p2p(self, name: str, arguments: Any = None, **kwargs: Any) -> dict[str, Any]:
        from ipfs_kit_py.core.performance import HotPathGate

        with HotPathGate(payload_bytes=0, fairness_class="mcp-p2p"):
            return _run_async_synchronously(
                lambda: self.call_framed("p2p", name, arguments, **kwargs)
            )

    async def handle_stdio(self, message: Mapping[str, Any]) -> dict[str, Any]:
        """JSON-RPC over stdio (MCP++ Profile E compatible fixture)."""

        return await self._handle_jsonrpc(message, framing="stdio")

    async def handle_http(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Minimal HTTP fixture that maps to the same tool admission path."""

        body = body or {}
        if method.upper() == "GET" and path in {"/mcp/tools", "/tools"}:
            return {
                "http_status": 200,
                "transport": MCP_HTTP_TRANSPORT,
                "framing": "http",
                "tools": self.list_tools(),
            }
        if method.upper() == "POST" and path in {"/mcp/tools/call", "/tools/call", "/mcp"}:
            if "jsonrpc" in body or body.get("method"):
                return await self._handle_jsonrpc(body, framing="http")
            name = body.get("name")
            arguments = body.get("arguments") or body.get("params") or {}
            if not isinstance(name, str):
                return {
                    "http_status": 400,
                    "transport": MCP_HTTP_TRANSPORT,
                    "framing": "http",
                    **self._input_error("tool name is required").to_dict(),
                }
            framed = await self.call_framed("http", name, arguments)
            return {"http_status": 200 if framed.get("success") else 403, **framed}
        return {
            "http_status": 404,
            "transport": MCP_HTTP_TRANSPORT,
            "framing": "http",
            **self._input_error(f"unknown HTTP route {method} {path}").to_dict(),
        }

    async def handle_p2p(self, raw: bytes | Mapping[str, Any]) -> dict[str, Any]:
        """P2P stream fixture: decode JSON-RPC, dispatch, attach protocol id."""

        if isinstance(raw, (bytes, bytearray)):
            try:
                message = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {
                    "protocol_id": "/mcp+p2p/1.0.0",
                    "transport": MCP_P2P_TRANSPORT,
                    "framing": "p2p",
                    **self._input_error("p2p payload must be JSON-RPC").to_dict(),
                }
        else:
            message = raw
        result = await self._handle_jsonrpc(message, framing="p2p")
        result["protocol_id"] = "/mcp+p2p/1.0.0"
        return result

    async def _handle_jsonrpc(
        self, message: Mapping[str, Any], *, framing: str
    ) -> dict[str, Any]:
        if not isinstance(message, Mapping):
            return _jsonrpc_error(None, -32600, "Invalid Request", framing=framing)
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        transport = FRAMING_TRANSPORTS[framing]
        if method in {"tools/list", "mcp++/tools/list"}:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": self.list_tools(),
                    "transport": transport,
                    "framing": framing,
                },
            }
        if method in {"tools/call", "mcp++/tools/call"}:
            if not isinstance(params, Mapping):
                return _jsonrpc_error(request_id, -32602, "Invalid params", framing=framing)
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str):
                return _jsonrpc_error(
                    request_id, -32602, "tool name is required", framing=framing
                )
            framed = await self.call_framed(framing, name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": framed,
            }
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "ipfs-kit-mcp-plusplus-adapter",
                        "version": "1",
                    },
                    "capabilities": {
                        "tools": {},
                        "profiles": ["mcp++/interface-descriptors"],
                    },
                    "transport": transport,
                    "framing": framing,
                },
            }
        return _jsonrpc_error(
            request_id, -32601, f"Method not found: {method}", framing=framing
        )


def _jsonrpc_error(
    request_id: Any,
    code: int,
    message: str,
    *,
    framing: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    if framing is not None:
        payload["framing"] = framing
        payload["transport"] = FRAMING_TRANSPORTS.get(framing, framing)
    return payload


def assert_no_competing_tool_registration(
    *adapters: _MCPBaseAdapter,
    legacy_names: Sequence[str] = (),
) -> None:
    """Raise if any single transport has an ambiguous tool name claim.

    Distinct transports may reuse public names (stdio vs HTTP vs package).
    Within one transport, or between a registry projection and a legacy
    hierarchical tool name on the same surface, a second claim raises rather
    than overwriting.
    """

    by_transport: dict[str, dict[str, str]] = {}
    for adapter in adapters:
        surface = by_transport.setdefault(adapter.TRANSPORT, {})
        for tool in adapter.tools():
            name = tool.projection.name
            assert name is not None
            operation_id = tool.projection.operation_id
            prior = surface.get(name)
            if prior is not None and prior != operation_id:
                raise DuplicateToolRegistrationError(
                    f"competing registration for tool {name!r} on transport "
                    f"{adapter.TRANSPORT!r}: {prior!r} vs {operation_id!r}"
                )
            surface[name] = operation_id
            # Registration table must already know the name (no silent drop).
            adapter._registrations.resolve(name)
    # Legacy hierarchical names (category/tool) compete with the MCP transport.
    mcp_surface = by_transport.get(MCP_TRANSPORT, {})
    for legacy in legacy_names:
        if legacy in mcp_surface:
            raise DuplicateToolRegistrationError(
                f"legacy tool {legacy!r} collides with registry projection "
                f"{mcp_surface[legacy]!r} on transport {MCP_TRANSPORT!r}"
            )


def build_mcp_tool_adapter(
    registry: OperationRegistry, router: ServiceRouter
) -> MCPToolAdapter:
    return MCPToolAdapter(registry, router)


def build_mcp_plusplus_tool_adapter(
    registry: OperationRegistry, router: ServiceRouter
) -> MCPPlusPlusToolAdapter:
    return MCPPlusPlusToolAdapter(registry, router)


__all__ = [
    "ADAPTER_CONTRACT_VERSION",
    "ADAPTER_RESPONSE_SCHEMA",
    "DuplicateToolRegistrationError",
    "FRAMING_TRANSPORTS",
    "MCPP_FRAMINGS",
    "MCPP_TRANSPORT",
    "MCPPlusPlusToolAdapter",
    "MCPPlusPlusToolAdapter_V1",
    "MCPToolAdapter",
    "MCPToolAdapterError",
    "MCPToolAdapter_V1",
    "MCPToolDescriptor",
    "MCP_ADAPTER_SCHEMA",
    "MCP_HTTP_TRANSPORT",
    "MCP_P2P_TRANSPORT",
    "MCP_PLUSPLUS_ADAPTER_SCHEMA",
    "MCP_STDIO_TRANSPORT",
    "MCP_TOOL_SCHEMA",
    "MCP_TRANSPORT",
    "TRANSPORT_ONLY_KEYS",
    "UnknownToolError",
    "assert_no_competing_tool_registration",
    "build_mcp_plusplus_tool_adapter",
    "build_mcp_tool_adapter",
    "semantic_payload",
    "strip_transport_fields",
]
