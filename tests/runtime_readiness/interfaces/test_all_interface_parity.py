"""All-interface parity: package, Python, CLI, MCP stdio, HTTP, and P2P.

Authority: ``docs/runtime_readiness/interface_manifest.json`` (InterfaceManifest@1).
Adapters under test project the same operation registry; after transport-only
fields (request ID / timing / framing) are stripped, semantic payloads match.
"""

from __future__ import annotations

import asyncio
import json
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.cli.operation_adapter import CLIAdapter
from ipfs_kit_py.core.operation_contracts import (
    OPERATION_REQUEST_SCHEMA,
    OPERATION_RESULT_SCHEMA,
    STORAGE_ERROR_SCHEMA,
    ErrorCategory,
    ErrorCode,
    OperationResult,
    OperationState,
    Retryability,
    StorageError,
    canonical_json,
)
from ipfs_kit_py.core.operation_registry import (
    AuthorizationRequirement,
    CapabilityTier,
    DuplicateOperationIdentifierError,
    OperationDefinition,
    OperationRegistry,
)
from ipfs_kit_py.core.service_router import DispatchContext, ServiceRouter
from ipfs_kit_py.high_level_api.operation_adapter import (
    AsyncPythonAdapter,
    PythonAdapter,
)
from ipfs_kit_py.mcp_server.tools import (
    MCPP_FRAMINGS,
    MCPPlusPlusToolAdapter,
    MCPToolAdapter,
    MCPToolManager,
    MCP_ADAPTER_SCHEMA,
    MCP_PLUSPLUS_ADAPTER_SCHEMA,
    MCP_TRANSPORT,
    MCPP_TRANSPORT,
    TOOL_GROUPS,
    assert_no_competing_tool_registration,
    build_tool_manager,
    hierarchical_tool_names,
    semantic_payload,
    strip_transport_fields,
)
from ipfs_kit_py.mcp_server.tools.operation_adapter import (
    DuplicateToolRegistrationError,
    FRAMING_TRANSPORTS,
    TRANSPORT_ONLY_KEYS,
    _ToolRegistrationTable,
)


MANIFEST_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "runtime_readiness"
    / "interface_manifest.json"
)


def _operation(
    operation_id: str,
    *,
    transport_names: dict[str, str],
    authorization: AuthorizationRequirement | None = None,
    support_tier: CapabilityTier = CapabilityTier.PRODUCTION,
    capability: str | None = None,
) -> OperationDefinition:
    return OperationDefinition(
        operation_id=operation_id,
        version=1,
        request_schema=OPERATION_REQUEST_SCHEMA,
        result_schema=OPERATION_RESULT_SCHEMA,
        error_schema=STORAGE_ERROR_SCHEMA,
        capability=capability or operation_id,
        authorization=authorization or AuthorizationRequirement.public(),
        handler_route="fixture-service",
        transport_names=transport_names,
        support_tier=support_tier,
    )


def _fixture_transports(public_name: str) -> dict[str, str]:
    """Advertise the same public name on every parity surface transport."""

    return {
        "python": public_name,
        "cli": public_name,
        "mcp": public_name,
        "mcpp": public_name,
    }


def _router(
    handler: Any,
    *,
    definitions: tuple[OperationDefinition, ...] | None = None,
    authorizer: Any = None,
    capability_checker: Any = None,
) -> ServiceRouter:
    if definitions is None:
        definitions = (
            _operation(
                "storage.object.read",
                transport_names=_fixture_transports("object-read"),
            ),
            _operation(
                "storage.object.write",
                transport_names=_fixture_transports("object-write"),
                authorization=AuthorizationRequirement.protected(
                    "storage.object", "write"
                ),
            ),
            _operation(
                "storage.object.optional",
                transport_names=_fixture_transports("object-optional"),
                capability="storage.object.optional-feature",
                support_tier=CapabilityTier.CONDITIONAL,
            ),
            _operation(
                "storage.object.unsupported",
                transport_names=_fixture_transports("object-unsupported"),
                support_tier=CapabilityTier.UNSUPPORTED,
            ),
            _operation(
                "storage.object.mcp-only",
                transport_names={"mcp": "object-mcp-only", "mcpp": "object-mcp-only"},
            ),
            _operation(
                "storage.object.python-only",
                transport_names={"python": "object-python-only"},
            ),
        )
    registry = OperationRegistry(definitions)
    kwargs: dict[str, Any] = {}
    if authorizer is not None:
        kwargs["authorizer"] = authorizer
    if capability_checker is not None:
        kwargs["capability_checker"] = capability_checker
    router = ServiceRouter(registry, **kwargs)
    router.bind_handler(
        "fixture-service",
        handler,
        capabilities={definition.capability for definition in definitions},
    )
    return router


async def _success_handler(
    definition: OperationDefinition, request: Any, _context: DispatchContext
) -> OperationResult:
    return OperationResult(
        request_id="fixture-request",
        operation_id=definition.operation_id,
        state=OperationState.ACCEPTED,
        success=True,
        resulting_content_cid="cid:fixture-content",
        resulting_version_cid="cid:fixture-version",
    )


async def _partial_handler(
    definition: OperationDefinition, _request: Any, _context: DispatchContext
) -> OperationResult:
    error = StorageError(
        code=ErrorCode.PARTIAL_EFFECT,
        category=ErrorCategory.PARTIAL_EFFECT,
        message="partial effect observed",
        retryability=Retryability.AFTER_RECONCILE,
        state=OperationState.PARTIAL_EFFECT,
        related_operation_id=definition.operation_id,
    )
    # PARTIAL_EFFECT state requires PartialEffectRecord entries when constructed
    # as a full OperationResult success ladder; for adapter parity we return the
    # StorageError-bearing failed result the serializers already understand.
    return OperationResult(
        request_id="fixture-request",
        operation_id=definition.operation_id,
        state=OperationState.FAILED,
        success=False,
        error=error,
        resulting_content_cid="cid:partial-content",
    )


def _all_adapters(router: ServiceRouter) -> dict[str, Any]:
    registry = router.registry
    return {
        "package": PythonAdapter(registry, router),
        "python_sync": PythonAdapter(registry, router),
        "python_async": AsyncPythonAdapter(registry, router),
        "cli": CLIAdapter(registry, router),
        "mcp": MCPToolAdapter(registry, router),
        "mcpp": MCPPlusPlusToolAdapter(registry, router),
    }


# ---------------------------------------------------------------------------
# Manifest authority
# ---------------------------------------------------------------------------


def test_interface_manifest_matches_reviewed_adapter_schemas() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["schema"] == "InterfaceManifest@1"
    assert manifest["task_id"] == "KITA-037"
    assert "MCPToolAdapter@1" in manifest["interfaces"]
    assert "MCPPlusPlusToolAdapter@1" in manifest["interfaces"]

    mcp_meta = manifest["adapters"]["MCPToolAdapter@1"]
    mcpp_meta = manifest["adapters"]["MCPPlusPlusToolAdapter@1"]
    assert mcp_meta["schema"] == MCP_ADAPTER_SCHEMA
    assert mcpp_meta["schema"] == MCP_PLUSPLUS_ADAPTER_SCHEMA
    assert mcp_meta["transport"] == MCP_TRANSPORT
    assert mcpp_meta["transport"] == MCPP_TRANSPORT
    assert mcpp_meta["framings"] == list(MCPP_FRAMINGS)

    strip = set(manifest["parity_policy"]["strip_before_compare"])
    assert strip <= TRANSPORT_ONLY_KEYS or strip == set(TRANSPORT_ONLY_KEYS)
    # Manifest strip set must cover every transport-only key the adapters use.
    assert set(manifest["parity_policy"]["strip_before_compare"]) == set(
        TRANSPORT_ONLY_KEYS
    )

    surfaces = set(manifest["parity_policy"]["surfaces"])
    assert surfaces == {
        "package",
        "python",
        "cli",
        "mcp-stdio",
        "mcp-http",
        "mcp-p2p",
    }


def test_tool_sets_and_schemas_equal_manifest_projection() -> None:
    router = _router(_success_handler)
    mcp = MCPToolAdapter(router.registry, router)
    mcpp = MCPPlusPlusToolAdapter(router.registry, router)
    tools = mcp.list_tools()
    assert tools
    required = {
        "name",
        "description",
        "operation_id",
        "version",
        "request_schema",
        "result_schema",
        "error_schema",
        "capability",
        "support_tier",
        "access_requirement",
        "inputSchema",
        "response_schema",
    }
    for tool in tools:
        assert required <= set(tool)
        assert tool["inputSchema"]["required"] == ["request"]
        assert tool["inputSchema"]["properties"]["context"]["default"] == {}
        assert tool["request_schema"] == OPERATION_REQUEST_SCHEMA
        assert tool["result_schema"] == OPERATION_RESULT_SCHEMA
        assert tool["error_schema"] == STORAGE_ERROR_SCHEMA

    # MCP and MCP++ applicable tool names for the shared public names match.
    mcp_names = {t["name"] for t in tools}
    mcpp_names = {t["name"] for t in mcpp.list_tools()}
    assert "object-read" in mcp_names
    assert "object-read" in mcpp_names
    assert mcp_names == mcpp_names  # fixture advertises the same set on both


# ---------------------------------------------------------------------------
# Registration fail-closed
# ---------------------------------------------------------------------------


def test_duplicate_competing_registration_raises() -> None:
    table = _ToolRegistrationTable()
    table.register("object-read", "storage.object.read")
    with pytest.raises(DuplicateToolRegistrationError):
        table.register("object-read", "storage.object.other")

    with pytest.raises(DuplicateOperationIdentifierError):
        OperationRegistry(
            (
                _operation(
                    "storage.object.read",
                    transport_names={"mcp": "object-read"},
                ),
                _operation(
                    "storage.object.other",
                    transport_names={"mcp": "object-read"},
                ),
            )
        )


def test_legacy_hierarchical_names_do_not_silently_shadow_registry() -> None:
    # Pick a real hierarchical short name and try to project it as MCP.
    legacy = hierarchical_tool_names()
    assert "ipfs_add" in legacy or any(n.endswith("/ipfs_add") for n in legacy)

    definitions = (
        _operation(
            "storage.ipfs.add",
            transport_names={
                "mcp": "ipfs_add",
                "python": "ipfs-add",
                "cli": "ipfs-add",
            },
        ),
    )
    registry = OperationRegistry(definitions)
    router = ServiceRouter(registry)
    router.bind_handler(
        "fixture-service",
        _success_handler,
        capabilities={"storage.ipfs.add"},
    )
    mcp = MCPToolAdapter(registry, router)
    with pytest.raises(DuplicateToolRegistrationError):
        assert_no_competing_tool_registration(mcp, legacy_names=legacy)

    with pytest.raises(DuplicateToolRegistrationError):
        build_tool_manager(registry, router)


# ---------------------------------------------------------------------------
# Cross-surface semantic parity
# ---------------------------------------------------------------------------


def test_package_python_cli_mcp_stdio_http_p2p_semantic_parity() -> None:
    router = _router(_success_handler)
    adapters = _all_adapters(router)
    request = {"key": "fixture"}
    arguments = {"request": request}

    package = adapters["package"].call("object-read", request)
    python_sync = adapters["python_sync"].call("object-read", request)
    python_async = asyncio.run(adapters["python_async"].call("object-read", request))
    cli = asyncio.run(adapters["cli"].invoke("object-read", request))
    mcp = adapters["mcp"].call("object-read", arguments)
    mcpp_stdio = asyncio.run(
        adapters["mcpp"].call_framed("stdio", "object-read", arguments)
    )
    mcpp_http = asyncio.run(
        adapters["mcpp"].call_framed("http", "object-read", arguments)
    )
    mcpp_p2p = asyncio.run(
        adapters["mcpp"].call_framed("p2p", "object-read", arguments)
    )

    semantic = semantic_payload(package)
    assert semantic_payload(python_sync) == semantic
    assert semantic_payload(python_async) == semantic
    assert semantic_payload(cli) == semantic
    assert semantic_payload(mcp) == semantic
    assert strip_transport_fields(mcpp_stdio) == semantic
    assert strip_transport_fields(mcpp_http) == semantic
    assert strip_transport_fields(mcpp_p2p) == semantic

    # Content / version CIDs and empty effect evidence survive the strip.
    record = package.to_dict()["result"]["record"]
    assert record["resulting_content_cid"] == "cid:fixture-content"
    assert record["resulting_version_cid"] == "cid:fixture-version"
    assert record["effect_evidence"] == []
    assert package.success is True
    assert package.exit_code == 0

    # CLI stdout matches the package envelope (including content_id — same
    # request_id fixture keeps content identity stable before stripping).
    stdout, stderr = StringIO(), StringIO()
    assert (
        adapters["cli"].run(
            ["object-read", "--request-json", json.dumps(request)],
            stdout=stdout,
            stderr=stderr,
        )
        == 0
    )
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue()) == package.to_dict()

    # MCP stdio JSON-RPC and HTTP/P2P fixtures expose the same tool result.
    stdio_rpc = asyncio.run(
        adapters["mcp"].handle_jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "object-read", "arguments": arguments},
            }
        )
    )
    assert stdio_rpc["jsonrpc"] == "2.0"
    assert stdio_rpc["id"] == 7
    assert strip_transport_fields(stdio_rpc["result"]) == semantic

    http = asyncio.run(
        adapters["mcpp"].handle_http(
            "POST",
            "/mcp/tools/call",
            {"name": "object-read", "arguments": arguments},
        )
    )
    assert http["http_status"] == 200
    assert strip_transport_fields(http) == semantic

    p2p = asyncio.run(
        adapters["mcpp"].handle_p2p(
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {"name": "object-read", "arguments": arguments},
            }
        )
    )
    assert p2p["protocol_id"] == "/mcp+p2p/1.0.0"
    assert strip_transport_fields(p2p["result"]) == semantic


def test_error_retry_and_partial_effect_meanings_match() -> None:
    router = _router(_partial_handler)
    adapters = _all_adapters(router)
    request = {"key": "partial"}
    arguments = {"request": request}

    package = adapters["package"].call("object-read", request)
    cli = asyncio.run(adapters["cli"].invoke("object-read", request))
    mcp = adapters["mcp"].call("object-read", arguments)
    http = asyncio.run(
        adapters["mcpp"].call_framed("http", "object-read", arguments)
    )
    p2p = asyncio.run(
        adapters["mcpp"].call_framed("p2p", "object-read", arguments)
    )

    semantic = semantic_payload(package)
    assert package.success is False
    assert package.error is not None
    assert package.error.code is ErrorCode.PARTIAL_EFFECT
    assert package.error.retryability is Retryability.AFTER_RECONCILE
    assert semantic_payload(cli) == semantic
    assert semantic_payload(mcp) == semantic
    assert strip_transport_fields(http) == semantic
    assert strip_transport_fields(p2p) == semantic

    # Unsupported operations reject identically before handler effects.
    unsupported_package = adapters["package"].call("object-unsupported", {})
    unsupported_mcp = adapters["mcp"].call("object-unsupported", {"request": {}})
    assert unsupported_package.error is not None
    assert unsupported_package.error.code is ErrorCode.UNSUPPORTED
    assert semantic_payload(unsupported_package) == semantic_payload(unsupported_mcp)


def test_protected_tool_requires_same_authorization_on_every_surface() -> None:
    calls: list[object] = []

    async def guarded(
        definition: OperationDefinition, request: Any, context: DispatchContext
    ) -> dict[str, Any]:
        calls.append((definition.operation_id, request, context.principal))
        return {"wrote": request}

    def authorizer(requirement: AuthorizationRequirement, context: DispatchContext) -> bool:
        return (
            requirement.classification.value == "protected"
            and requirement.resource == "storage.object"
            and requirement.ability == "write"
            and context.principal == "alice"
        )

    router = _router(guarded, authorizer=authorizer)
    adapters = _all_adapters(router)
    request = {"key": "secret"}
    arguments = {"request": request, "principal": "eve"}

    denied_surfaces = [
        semantic_payload(adapters["package"].call(
            "object-write", request, context=DispatchContext(principal="eve")
        )),
        semantic_payload(asyncio.run(adapters["cli"].invoke(
            "object-write", request, principal="eve"
        ))),
        semantic_payload(adapters["mcp"].call("object-write", arguments)),
        strip_transport_fields(asyncio.run(
            adapters["mcpp"].call_framed("stdio", "object-write", arguments)
        )),
        strip_transport_fields(asyncio.run(
            adapters["mcpp"].call_framed("http", "object-write", arguments)
        )),
        strip_transport_fields(asyncio.run(
            adapters["mcpp"].call_framed("p2p", "object-write", arguments)
        )),
    ]
    assert calls == []
    for payload in denied_surfaces:
        assert payload["success"] is False
        assert payload["error"]["code"] == ErrorCode.FORBIDDEN.value
        assert payload["operation"]["access_requirement"] == {
            "classification": "protected",
            "resource": "storage.object",
            "ability": "write",
        }
    # All denial envelopes are identical after strip.
    assert all(item == denied_surfaces[0] for item in denied_surfaces)

    allowed_arguments = {"request": request, "principal": "alice"}
    allowed = [
        semantic_payload(adapters["package"].call(
            "object-write", request, context=DispatchContext(principal="alice")
        )),
        semantic_payload(adapters["mcp"].call("object-write", allowed_arguments)),
        strip_transport_fields(asyncio.run(
            adapters["mcpp"].call_framed("http", "object-write", allowed_arguments)
        )),
        strip_transport_fields(asyncio.run(
            adapters["mcpp"].call_framed("p2p", "object-write", allowed_arguments)
        )),
    ]
    assert len(calls) == 4
    assert all(item["success"] is True for item in allowed)
    assert all(item == allowed[0] for item in allowed)

    # Tool schema advertises the protected requirement on every MCP surface.
    write_tools = [
        next(t for t in adapters["mcp"].list_tools() if t["name"] == "object-write"),
        next(t for t in adapters["mcpp"].list_tools() if t["name"] == "object-write"),
    ]
    for tool in write_tools:
        assert tool["access_requirement"] == {
            "classification": "protected",
            "resource": "storage.object",
            "ability": "write",
        }


def test_missing_optional_feature_rejects_identically_not_noop() -> None:
    calls: list[object] = []

    async def handler(
        definition: OperationDefinition, request: Any, _context: DispatchContext
    ) -> dict[str, Any]:
        calls.append(request)
        return {"ok": True}

    router = _router(
        handler,
        capability_checker=lambda definition, _context: (
            definition.capability != "storage.object.optional-feature"
        ),
    )
    adapters = _all_adapters(router)
    request = {"feature": "optional"}
    arguments = {"request": request}

    results = [
        semantic_payload(adapters["package"].call("object-optional", request)),
        semantic_payload(asyncio.run(adapters["python_async"].call("object-optional", request))),
        semantic_payload(asyncio.run(adapters["cli"].invoke("object-optional", request))),
        semantic_payload(adapters["mcp"].call("object-optional", arguments)),
        strip_transport_fields(asyncio.run(
            adapters["mcpp"].call_framed("stdio", "object-optional", arguments)
        )),
        strip_transport_fields(asyncio.run(
            adapters["mcpp"].call_framed("http", "object-optional", arguments)
        )),
        strip_transport_fields(asyncio.run(
            adapters["mcpp"].call_framed("p2p", "object-optional", arguments)
        )),
    ]
    assert calls == []
    for payload in results:
        assert payload["success"] is False
        assert payload["error"]["code"] == ErrorCode.CAPABILITY_MISSING.value
        # Tool remains listed — missing capability does not remove the tool.
        assert payload["operation"]["operation_id"] == "storage.object.optional"
    assert all(item == results[0] for item in results)

    listed = {t["name"] for t in adapters["mcp"].list_tools()}
    assert "object-optional" in listed
    assert "object-optional" in {t["name"] for t in adapters["mcpp"].list_tools()}


def test_non_applicable_operations_have_explicit_reasons() -> None:
    router = _router(_success_handler)
    python = PythonAdapter(router.registry, router)
    mcp = MCPToolAdapter(router.registry, router)
    mcpp = MCPPlusPlusToolAdapter(router.registry, router)

    python_map = {p.operation_id: p for p in python.operation_projections()}
    mcp_map = {p.operation_id: p for p in mcp.operation_projections()}
    mcpp_map = {p.operation_id: p for p in mcpp.operation_projections()}

    assert set(python_map) == set(mcp_map) == set(mcpp_map)
    assert python_map["storage.object.mcp-only"].applicable is False
    assert python_map["storage.object.mcp-only"].reason
    assert mcp_map["storage.object.python-only"].applicable is False
    assert mcp_map["storage.object.python-only"].reason
    assert mcpp_map["storage.object.python-only"].applicable is False


def test_package_facade_mcp_tool_manager_parity() -> None:
    router = _router(_success_handler)
    manager = build_tool_manager(router.registry, router)
    tools = manager.get_tools()
    mcp = MCPToolAdapter(router.registry, router)
    assert tools == mcp.list_tools()

    response = asyncio.run(
        manager.handle_tool_request("object-read", {"request": {"key": "x"}})
    )
    direct = mcp.call("object-read", {"request": {"key": "x"}})
    assert strip_transport_fields(response) == semantic_payload(direct)

    unbound = MCPToolManager()
    missing = asyncio.run(unbound.handle_tool_request("object-read", {}))
    assert missing["success"] is False
    assert missing["error"]["code"] == "E_UNAVAILABLE"

    metadata = manager.metadata()
    assert metadata["bound"] is True
    assert "mcp" in metadata and "mcpp" in metadata
    assert json.loads(canonical_json(metadata)) == metadata


def test_mcpp_framing_transport_constants_match_manifest() -> None:
    assert set(FRAMING_TRANSPORTS) == set(MCPP_FRAMINGS)
    assert FRAMING_TRANSPORTS["stdio"] == "mcp-stdio"
    assert FRAMING_TRANSPORTS["http"] == "mcp-http"
    assert FRAMING_TRANSPORTS["p2p"] == "mcp-p2p"
    # Hierarchical groups remain available for HierarchicalToolManager.
    assert "ipfs_tools" in TOOL_GROUPS
    assert "pin_tools" in TOOL_GROUPS


def test_declared_mcp_tools_module_file_exports_registry_facade() -> None:
    """Load the KITA-037 declared path ``mcp/ipfs_kit/mcp_tools.py`` by file.

    A historical package directory may shadow the module under a plain import;
    the declared output file itself must still be a complete registry facade.
    """

    import importlib.util
    import sys

    path = (
        Path(__file__).resolve().parents[3]
        / "ipfs_kit_py"
        / "mcp"
        / "ipfs_kit"
        / "mcp_tools.py"
    )
    assert path.is_file()
    module_name = "_kita037_declared_mcp_tools"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)

    assert module.MCPToolAdapter is MCPToolAdapter
    assert module.MCPPlusPlusToolAdapter is MCPPlusPlusToolAdapter
    assert module.MCPToolManager is MCPToolManager
    assert callable(module.build_tool_manager)

    router = _router(_success_handler)
    manager = module.build_tool_manager(router.registry, router)
    assert manager.get_tools() == MCPToolAdapter(router.registry, router).list_tools()
