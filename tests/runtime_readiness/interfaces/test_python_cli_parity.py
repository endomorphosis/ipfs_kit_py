"""Parity contracts for generated Python and CLI operation adapters."""

from __future__ import annotations

import asyncio
import json
from io import StringIO
from typing import Any

from ipfs_kit_py.cli.operation_adapter import CLIAdapter
from ipfs_kit_py.core.operation_contracts import (
    OPERATION_REQUEST_SCHEMA,
    OPERATION_RESULT_SCHEMA,
    STORAGE_ERROR_SCHEMA,
    ErrorCode,
    OperationResult,
    OperationState,
    canonical_json,
)
from ipfs_kit_py.core.operation_registry import (
    AuthorizationRequirement,
    CapabilityTier,
    OperationDefinition,
    OperationRegistry,
)
from ipfs_kit_py.core.service_router import ServiceRouter
from ipfs_kit_py.high_level_api.operation_adapter import (
    AsyncPythonAdapter,
    PythonAdapter,
)


def _operation(
    operation_id: str,
    *,
    transport_names: dict[str, str],
    support_tier: CapabilityTier = CapabilityTier.PRODUCTION,
) -> OperationDefinition:
    return OperationDefinition(
        operation_id=operation_id,
        version=1,
        request_schema=OPERATION_REQUEST_SCHEMA,
        result_schema=OPERATION_RESULT_SCHEMA,
        error_schema=STORAGE_ERROR_SCHEMA,
        capability=operation_id,
        authorization=AuthorizationRequirement.public(),
        handler_route="fixture-service",
        transport_names=transport_names,
        support_tier=support_tier,
    )


def _router(handler: Any) -> ServiceRouter:
    definitions = (
        _operation(
            "storage.object.read",
            transport_names={"python": "object-read", "cli": "object-read"},
        ),
        _operation(
            "storage.object.cli-only",
            transport_names={"cli": "object-list"},
        ),
        _operation(
            "storage.object.python-only",
            transport_names={"python": "object-inspect"},
        ),
        _operation(
            "storage.object.unsupported",
            transport_names={"python": "object-unsupported", "cli": "object-unsupported"},
            support_tier=CapabilityTier.UNSUPPORTED,
        ),
    )
    registry = OperationRegistry(definitions)
    router = ServiceRouter(registry)
    router.bind_handler(
        "fixture-service",
        handler,
        capabilities={definition.capability for definition in definitions},
    )
    return router


async def _result_handler(
    definition: OperationDefinition, _request: Any, _context: Any
) -> OperationResult:
    """A fixture result with content/version/effect fields owned by the contract."""

    return OperationResult(
        request_id="fixture-request",
        operation_id=definition.operation_id,
        state=OperationState.ACCEPTED,
        success=True,
        resulting_content_cid="cid:fixture-content",
        resulting_version_cid="cid:fixture-version",
    )


def test_every_registry_operation_has_a_projection_or_non_applicable_reason() -> None:
    router = _router(_result_handler)
    python = PythonAdapter(router.registry, router)
    cli = CLIAdapter(router.registry, router)

    python_projections = {item.operation_id: item for item in python.operation_projections()}
    cli_projections = {item.operation_id: item for item in cli.operation_projections()}

    assert set(python_projections) == set(cli_projections) == {
        item.operation_id for item in router.registry.operations()
    }
    assert python_projections["storage.object.cli-only"].applicable is False
    assert python_projections["storage.object.cli-only"].reason
    assert cli_projections["storage.object.python-only"].applicable is False
    assert cli_projections["storage.object.python-only"].reason
    assert [command.projection.name for command in cli.commands()] == [
        "object-list",
        "object-read",
        "object-unsupported",
    ]

    # The adapter metadata itself is a valid canonical record: it cannot hide
    # secrets under registry authorization metadata or introduce a second schema.
    assert json.loads(canonical_json(python.metadata())) == python.metadata()
    assert json.loads(canonical_json(cli.metadata())) == cli.metadata()


def test_sync_async_and_cli_share_result_content_version_and_effect_records() -> None:
    router = _router(_result_handler)
    sync_python = PythonAdapter(router.registry, router)
    async_python = AsyncPythonAdapter(router.registry, router)
    cli = CLIAdapter(router.registry, router)

    request = {"key": "fixture"}
    sync_response = sync_python.call("object-read", request)
    async_response = asyncio.run(async_python.call("object-read", request))
    cli_response = asyncio.run(cli.invoke("object-read", request))

    assert sync_response.to_dict() == async_response.to_dict() == cli_response.to_dict()
    result = sync_response.to_dict()["result"]["record"]
    assert result["resulting_content_cid"] == "cid:fixture-content"
    assert result["resulting_version_cid"] == "cid:fixture-version"
    assert result["effect_evidence"] == []

    stdout, stderr = StringIO(), StringIO()
    assert cli.run(["object-read", "--request-json", json.dumps(request)], stdout=stdout, stderr=stderr) == 0
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue()) == sync_response.to_dict()


def test_cancellation_and_unsupported_states_have_matching_python_and_cli_exits() -> None:
    def cancelled_handler(_definition: OperationDefinition, _request: Any, _context: Any) -> None:
        raise asyncio.CancelledError

    router = _router(cancelled_handler)
    sync_python = PythonAdapter(router.registry, router)
    async_python = AsyncPythonAdapter(router.registry, router)
    cli = CLIAdapter(router.registry, router)

    sync_response = sync_python.call("object-read", {})
    async_response = asyncio.run(async_python.call("object-read", {}))
    cli_response = asyncio.run(cli.invoke("object-read", {}))
    assert sync_response.to_dict() == async_response.to_dict() == cli_response.to_dict()
    assert sync_response.error is not None
    assert sync_response.error.code is ErrorCode.CANCELLED
    assert sync_response.error.state is OperationState.CANCELLED
    assert sync_response.exit_code == 130

    stdout, stderr = StringIO(), StringIO()
    assert cli.run(["object-read", "--request-json", "{}"], stdout=stdout, stderr=stderr) == 130
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue()) == sync_response.to_dict()

    unsupported_python = sync_python.call("object-unsupported", {})
    unsupported_cli = asyncio.run(cli.invoke("object-unsupported", {}))
    assert unsupported_python.to_dict() == unsupported_cli.to_dict()
    assert unsupported_python.error is not None
    assert unsupported_python.error.code is ErrorCode.UNSUPPORTED
    assert unsupported_python.exit_code == 64


def test_cli_command_schema_defaults_and_input_exit_are_canonical() -> None:
    router = _router(_result_handler)
    cli = CLIAdapter(router.registry, router)
    read_command = next(
        command.to_dict() for command in cli.commands() if command.projection.name == "object-read"
    )
    assert read_command["request_schema"] == OPERATION_REQUEST_SCHEMA
    assert read_command["result_schema"] == OPERATION_RESULT_SCHEMA
    assert read_command["error_schema"] == STORAGE_ERROR_SCHEMA
    assert read_command["options"] == [
        {
            "option": "--request-json",
            "destination": "request_json",
            "required": True,
            "default": None,
            "schema": OPERATION_REQUEST_SCHEMA,
        },
        {
            "option": "--principal",
            "destination": "principal",
            "required": False,
            "default": None,
            "schema": "ipfs_kit_py/interfaces/principal@1",
        },
        {
            "option": "--context-json",
            "destination": "context_json",
            "required": False,
            "default": "{}",
            "schema": "ipfs_kit_py/interfaces/dispatch-context-attributes@1",
        },
    ]

    stdout, stderr = StringIO(), StringIO()
    assert cli.run(["object-read", "--request-json", "not-json"], stdout=stdout, stderr=stderr) == 2
    response = json.loads(stdout.getvalue())
    assert stderr.getvalue() == ""
    assert response["success"] is False
    assert response["error"]["code"] == ErrorCode.INVALID_REQUEST.value

    stdout = StringIO()
    assert cli.run(["--metadata"], stdout=stdout) == 0
    assert json.loads(stdout.getvalue()) == cli.metadata()
