"""Contract tests for the inert operation registry and canonical router."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from ipfs_kit_py.core.operation_contracts import (
    OPERATION_REQUEST_SCHEMA,
    OPERATION_RESULT_SCHEMA,
    STORAGE_ERROR_SCHEMA,
)
from ipfs_kit_py.core.operation_registry import (
    AuthorizationRequirement,
    CapabilityTier,
    DuplicateOperationIdentifierError,
    OperationDefinition,
    OperationRegistry,
    UnsupportedOperationError,
)
from ipfs_kit_py.core.service_router import (
    AuthorizationDeniedError,
    CanonicalStorageService_V1,
    CapabilityUnavailableError,
    DispatchContext,
    HandlerNotBoundError,
    ServiceRouter,
    ServiceRouter_V1,
)


def operation(
    operation_id: str = "storage.object.read",
    *,
    aliases: tuple[str, ...] = ("object.read",),
    authorization: AuthorizationRequirement | None = None,
    route: str = "object-service",
    capability: str = "storage.object.read",
    support_tier: CapabilityTier = CapabilityTier.PRODUCTION,
    transport_names: dict[str, str] | None = None,
) -> OperationDefinition:
    """Create a complete operation definition with the shared contracts."""

    return OperationDefinition(
        operation_id=operation_id,
        version=1,
        request_schema=OPERATION_REQUEST_SCHEMA,
        result_schema=OPERATION_RESULT_SCHEMA,
        error_schema=STORAGE_ERROR_SCHEMA,
        capability=capability,
        authorization=authorization or AuthorizationRequirement.public(),
        handler_route=route,
        aliases=aliases,
        transport_names=transport_names or {"cli": operation_id.replace(".", "-")},
        support_tier=support_tier,
    )


def test_registry_definitions_are_complete_unique_and_deterministic() -> None:
    assert CanonicalStorageService_V1.endswith("@1")
    assert ServiceRouter_V1.endswith("@1")

    read = operation(transport_names={"cli": "object-read"})
    write = operation(
        "storage.object.write",
        aliases=("object.write",),
        capability="storage.object.write",
        transport_names={"http": "storage.object.write", "cli": "object-write"},
    )

    first = OperationRegistry((write, read))
    second = OperationRegistry((read, write))

    assert first.resolve("object.read") is read
    assert first.resolve_transport("cli", "object-write") is write
    assert first.canonical_projection() == second.canonical_projection()
    assert first.canonical_json_bytes() == second.canonical_json_bytes()
    assert [item.name for item in first.transport_projection("cli")] == [
        "object-read",
        "object-write",
    ]

    projection = first.canonical_projection()["operations"][0]
    assert projection["request_schema"] == OPERATION_REQUEST_SCHEMA
    assert projection["result_schema"] == OPERATION_RESULT_SCHEMA
    assert projection["error_schema"] == STORAGE_ERROR_SCHEMA
    assert projection["handler_route"]
    assert projection["capability"]
    assert projection["authorization"]["classification"] == "public"

    with pytest.raises(DuplicateOperationIdentifierError):
        first.register(replace(read, operation_id="storage.object.inspect"))
    with pytest.raises(DuplicateOperationIdentifierError):
        first.register(
            operation(
                "storage.object.other",
                aliases=("object.other",),
                transport_names={"cli": "object-read"},
            )
        )


def test_registry_source_import_is_inert_and_provider_free() -> None:
    """Load the source alone so the legacy package initializer is irrelevant."""

    source = (
        Path(__file__).resolve().parents[3]
        / "ipfs_kit_py"
        / "core"
        / "operation_registry.py"
    )
    module_name = "_operation_registry_inert_import_probe"
    before = set(sys.modules)
    spec = importlib.util.spec_from_file_location(module_name, source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)

    imported = set(sys.modules) - before
    assert not imported.intersection(
        {"boto3", "ipfshttpclient", "psutil", "requests", "subprocess"}
    )


def test_router_rejects_unsupported_and_unbound_operations_before_execution() -> None:
    unsupported = operation(
        "storage.object.legacy-read",
        aliases=("object.legacy-read",),
        support_tier=CapabilityTier.UNSUPPORTED,
    )
    router = ServiceRouter(OperationRegistry((unsupported,)))
    calls: list[object] = []
    router.bind_handler(
        "object-service",
        lambda *_: calls.append("called"),
        capabilities={"storage.object.read"},
    )

    with pytest.raises(UnsupportedOperationError):
        router.dispatch("object.legacy-read", {"key": "a"})
    assert calls == []

    active = operation()
    with pytest.raises(HandlerNotBoundError):
        ServiceRouter(OperationRegistry((active,))).dispatch(active.operation_id, {})


def test_router_requires_declared_capability_and_exact_protected_authorization() -> None:
    protected = operation(
        "storage.object.delete",
        aliases=("object.delete",),
        authorization=AuthorizationRequirement.protected(
            "storage.object", "delete"
        ),
        capability="storage.object.delete",
    )
    registry = OperationRegistry((protected,))
    calls: list[object] = []

    def handler(_definition: OperationDefinition, request: object, _context: DispatchContext) -> object:
        calls.append(request)
        return {"deleted": request}

    denied = ServiceRouter(registry, authorizer=lambda _requirement, _context: False)
    denied.bind_handler(
        "object-service", handler, capabilities={"storage.object.delete"}
    )
    with pytest.raises(AuthorizationDeniedError):
        denied.dispatch("object.delete", "cid")
    assert calls == []

    unavailable = ServiceRouter(
        registry,
        authorizer=lambda _requirement, _context: True,
        capability_checker=lambda _definition, _context: False,
    )
    unavailable.bind_handler(
        "object-service", handler, capabilities={"storage.object.delete"}
    )
    with pytest.raises(CapabilityUnavailableError):
        unavailable.dispatch(protected.operation_id, "cid")
    assert calls == []

    allowed = ServiceRouter(registry, authorizer=lambda requirement, context: (
        requirement.resource == "storage.object"
        and requirement.ability == "delete"
        and context.principal == "alice"
    ))
    allowed.bind_handler(
        "object-service", handler, capabilities={"storage.object.delete"}
    )
    assert allowed.dispatch("object.delete", "cid", context=DispatchContext("alice")) == {
        "deleted": "cid"
    }
    assert calls == ["cid"]


def test_router_binds_only_the_canonical_service_execute_method() -> None:
    class ObjectService:
        def execute(
            self, definition: OperationDefinition, request: object, context: DispatchContext
        ) -> object:
            return {
                "operation": definition.operation_id,
                "request": request,
                "principal": context.principal,
            }

    definition = operation()
    router = ServiceRouter(OperationRegistry((definition,)))
    router.bind_service(
        "object-service", ObjectService(), capabilities={"storage.object.read"}
    )

    assert router.dispatch(
        definition.operation_id, {"key": "a"}, context=DispatchContext("alice")
    ) == {
        "operation": "storage.object.read",
        "request": {"key": "a"},
        "principal": "alice",
    }
