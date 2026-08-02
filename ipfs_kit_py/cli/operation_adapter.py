"""Canonical CLI projection for the operation registry.

This is intentionally a library-facing CLI adapter.  Product-specific legacy
command modules remain separate because they are not declared operation
registry transports and cannot truthfully inherit this adapter's contracts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence, TextIO

from ..core.operation_contracts import (
    ErrorCategory,
    ErrorCode,
    OperationState,
    Retryability,
    StorageError,
    canonical_json,
)
from ..core.operation_registry import OperationRegistry
from ..core.service_router import DispatchContext, ServiceRouter
from ..high_level_api.operation_adapter import (
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_RESPONSE_SCHEMA,
    EXIT_CODES,
    AdapterOperationProjection,
    AdapterResponse,
    AsyncPythonAdapter,
    _failure,
)


CLI_ADAPTER_SCHEMA: Final[str] = "ipfs_kit_py/interfaces/cli-adapter@1"
CLI_COMMAND_SCHEMA: Final[str] = "ipfs_kit_py/interfaces/cli-command@1"
CLI_TRANSPORT: Final[str] = "cli"
DEFAULT_PROGRAM_NAME: Final[str] = "ipfs-kit-operation"


class CLIInputError(ValueError):
    """A command-line input error rendered as a canonical response."""


class _CanonicalArgumentParser(argparse.ArgumentParser):
    """argparse parser that never writes a second, non-canonical error stream."""

    def error(self, message: str) -> None:
        raise CLIInputError(message)


@dataclass(frozen=True)
class CLICommand:
    """CLI syntax derived solely from one registry transport projection."""

    projection: AdapterOperationProjection

    def to_dict(self) -> dict[str, Any]:
        if not self.projection.applicable or self.projection.name is None:
            raise ValueError("non-applicable operations do not have CLI commands")
        return {
            "schema": CLI_COMMAND_SCHEMA,
            "contract_version": ADAPTER_CONTRACT_VERSION,
            "name": self.projection.name,
            "operation_id": self.projection.operation_id,
            "version": self.projection.version,
            "request_schema": self.projection.request_schema,
            "result_schema": self.projection.result_schema,
            "error_schema": self.projection.error_schema,
            "options": [
                {
                    "option": "--request-json",
                    "destination": "request_json",
                    "required": True,
                    "default": None,
                    "schema": self.projection.request_schema,
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
            ],
            "response_schema": ADAPTER_RESPONSE_SCHEMA,
            "exit_codes": {code.value: value for code, value in EXIT_CODES.items()},
        }


class CLIAdapter:
    """A JSON-lines CLI whose command surface is generated from the registry."""

    TRANSPORT: Final[str] = CLI_TRANSPORT
    SCHEMA: Final[str] = CLI_ADAPTER_SCHEMA

    def __init__(
        self,
        registry: OperationRegistry,
        router: ServiceRouter,
        *,
        program_name: str = DEFAULT_PROGRAM_NAME,
    ) -> None:
        if not isinstance(registry, OperationRegistry):
            raise TypeError("registry must be an OperationRegistry")
        if not isinstance(router, ServiceRouter):
            raise TypeError("router must be a ServiceRouter")
        if router.registry is not registry:
            raise ValueError("router must be bound to the supplied registry")
        if not isinstance(program_name, str) or not program_name:
            raise ValueError("program_name must be a non-empty string")
        self.registry = registry
        self.router = router
        self.program_name = program_name
        self._async_adapter = AsyncPythonAdapter(registry, router)

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
                    reason="operation does not advertise a cli transport name",
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

    def commands(self) -> tuple[CLICommand, ...]:
        return tuple(
            CLICommand(projection)
            for projection in self.operation_projections()
            if projection.applicable
        )

    command_specs = commands

    def metadata(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": ADAPTER_CONTRACT_VERSION,
            "transport": self.TRANSPORT,
            "program_name": self.program_name,
            "operations": [item.to_dict() for item in self.operation_projections()],
            "commands": [item.to_dict() for item in self.commands()],
            "response_schema": ADAPTER_RESPONSE_SCHEMA,
            "exit_codes": {code.value: value for code, value in EXIT_CODES.items()},
        }

    def build_parser(self) -> argparse.ArgumentParser:
        parser = _CanonicalArgumentParser(prog=self.program_name, add_help=False)
        parser.add_argument("--metadata", action="store_true", default=False)
        subparsers = parser.add_subparsers(dest="command", parser_class=_CanonicalArgumentParser)
        for command in self.commands():
            spec = command.to_dict()
            subparser = subparsers.add_parser(spec["name"], add_help=False)
            subparser.add_argument("--request-json", dest="request_json", required=True)
            subparser.add_argument("--principal", dest="principal", default=None)
            subparser.add_argument("--context-json", dest="context_json", default="{}")
        return parser

    parser = build_parser

    def _projection_for_command(self, command: str) -> AdapterOperationProjection:
        definition = self.registry.resolve_transport(self.TRANSPORT, command)
        for projection in self.operation_projections():
            if projection.operation_id == definition.operation_id:
                return projection
        raise CLIInputError(f"command {command!r} has no CLI projection")

    @staticmethod
    def _parse_json(value: str, label: str) -> Any:
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError) as error:
            raise CLIInputError(f"{label} must be valid JSON") from error

    async def invoke(
        self,
        command: str,
        request: Any,
        *,
        principal: str | None = None,
        context_attributes: Mapping[str, Any] | None = None,
    ) -> AdapterResponse:
        projection: AdapterOperationProjection | None = None
        try:
            projection = self._projection_for_command(command)
            if context_attributes is not None and not isinstance(context_attributes, Mapping):
                raise CLIInputError("context JSON must be an object")
            context = DispatchContext(principal=principal, attributes=context_attributes or {})
            value = await self.router.dispatch_async(
                projection.operation_id, request, context=context
            )
            return self._async_adapter._response_for_value(projection, value)
        except asyncio.CancelledError as error:
            return AdapterResponse(operation=projection, error=_failure(error, projection))
        except Exception as error:
            return AdapterResponse(operation=projection, error=_failure(error, projection))

    execute = invoke

    def _input_error(self, error: BaseException) -> AdapterResponse:
        return AdapterResponse(
            operation=None,
            error=StorageError(
                code=ErrorCode.INVALID_REQUEST,
                category=ErrorCategory.VALIDATION,
                message="command-line input was rejected",
                retryability=Retryability.NEVER,
                state=OperationState.REJECTED,
            ),
        )

    async def run_async(
        self,
        argv: Sequence[str] | None = None,
        *,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
    ) -> int:
        """Run one command and emit exactly one canonical JSON line on stdout."""

        del stderr  # Error details are represented in the stdout envelope.
        output = stdout if stdout is not None else sys.stdout
        args = list(sys.argv[1:] if argv is None else argv)
        try:
            parsed = self.build_parser().parse_args(args)
            if parsed.metadata:
                output.write(canonical_json(self.metadata()) + "\n")
                return 0
            if parsed.command is None:
                raise CLIInputError("an advertised command is required")
            request = self._parse_json(parsed.request_json, "request JSON")
            attributes = self._parse_json(parsed.context_json, "context JSON")
            if not isinstance(attributes, Mapping):
                raise CLIInputError("context JSON must be an object")
            response = await self.invoke(
                parsed.command,
                request,
                principal=parsed.principal,
                context_attributes=attributes,
            )
        except (CLIInputError, SystemExit, ValueError) as error:
            response = self._input_error(error)
        output.write(response.to_json() + "\n")
        return response.exit_code

    def run(
        self,
        argv: Sequence[str] | None = None,
        *,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
    ) -> int:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run_async(argv, stdout=stdout, stderr=stderr))
        raise RuntimeError("CLIAdapter.run cannot run inside an event loop; use run_async")

    main = run


CLIAdapter_V1: Final[str] = CLI_ADAPTER_SCHEMA


def build_cli_adapter(
    registry: OperationRegistry,
    router: ServiceRouter,
    *,
    program_name: str = DEFAULT_PROGRAM_NAME,
) -> CLIAdapter:
    return CLIAdapter(registry, router, program_name=program_name)


__all__ = [
    "CLI_ADAPTER_SCHEMA",
    "CLI_TRANSPORT",
    "CLIAdapter",
    "CLIAdapter_V1",
    "CLICommand",
    "CLI_COMMAND_SCHEMA",
    "CLIInputError",
    "DEFAULT_PROGRAM_NAME",
    "build_cli_adapter",
]
