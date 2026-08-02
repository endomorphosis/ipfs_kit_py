"""Generated Python projections for the canonical operation registry.

The registry owns names and contracts, and :class:`ServiceRouter` owns
admission and execution.  This module deliberately owns neither: it turns a
public Python transport name into an exact registry operation and serializes
the outcome into the same record used by the CLI projection.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from threading import Thread
from typing import Any, Awaitable, Callable, Final, Mapping

from ..core.operation_contracts import (
    CanonicalContract,
    ErrorCategory,
    ErrorCode,
    OperationResult,
    OperationState,
    Retryability,
    StorageError,
    canonical_json,
    content_identity,
)
from ..core.operation_registry import (
    OperationRegistry,
    TransportProjection,
    UnknownOperationError,
    UnsupportedOperationError,
)
from ..core.service_router import (
    AsyncDispatchRequiredError,
    AuthorizationDeniedError,
    CapabilityUnavailableError,
    DispatchContext,
    HandlerBindingError,
    HandlerNotBoundError,
    ServiceRouter,
    ServiceRouterError,
)


PYTHON_ADAPTER_SCHEMA: Final[str] = "ipfs_kit_py/interfaces/python-adapter@1"
ASYNC_PYTHON_ADAPTER_SCHEMA: Final[str] = (
    "ipfs_kit_py/interfaces/async-python-adapter@1"
)
ADAPTER_RESPONSE_SCHEMA: Final[str] = (
    "ipfs_kit_py/interfaces/operation-adapter-response@1"
)
ADAPTER_CONTRACT_VERSION: Final[int] = 1
PYTHON_TRANSPORT: Final[str] = "python"


def _run_async_synchronously(factory: Callable[[], Awaitable[Any]]) -> Any:
    """Run the router's canonical async path from a synchronous projection.

    The async router is the one admission/execution path that accepts both
    synchronous and asynchronous handlers.  If a synchronous API is called
    from an active event loop, a short-lived worker keeps that loop responsive
    while preserving the same router path and result record.
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())

    outcome: list[tuple[bool, Any]] = []

    def execute() -> None:
        try:
            outcome.append((True, asyncio.run(factory())))
        except BaseException as error:
            outcome.append((False, error))

    worker = Thread(target=execute, name="ipfs-kit-python-adapter", daemon=False)
    worker.start()
    worker.join()
    succeeded, value = outcome[0]
    if succeeded:
        return value
    raise value

# This is adapter metadata, rather than a second error taxonomy.  The
# canonical StorageError is still the source of the selected exit code.
EXIT_CODES: Final[Mapping[ErrorCode, int]] = {
    ErrorCode.INVALID_REQUEST: 2,
    ErrorCode.FORGED_IDENTITY: 2,
    ErrorCode.SECRET_MATERIAL: 2,
    ErrorCode.BODY_REJECTED: 2,
    ErrorCode.UNBOUNDED_FIELD: 2,
    ErrorCode.NON_FINITE: 2,
    ErrorCode.CYCLE_DETECTED: 2,
    ErrorCode.INCONSISTENT_STATE: 2,
    ErrorCode.MISSING_EVIDENCE: 2,
    ErrorCode.UNAUTHORIZED: 3,
    ErrorCode.FORBIDDEN: 3,
    ErrorCode.NOT_FOUND: 4,
    ErrorCode.ALREADY_EXISTS: 4,
    ErrorCode.CONFLICT: 4,
    ErrorCode.PRECONDITION_FAILED: 4,
    ErrorCode.DEADLINE_EXCEEDED: 124,
    ErrorCode.CANCELLED: 130,
    ErrorCode.BACKPRESSURE: 75,
    ErrorCode.UNAVAILABLE: 69,
    ErrorCode.UNSUPPORTED: 64,
    ErrorCode.CAPABILITY_MISSING: 69,
    ErrorCode.STORAGE_FAILURE: 1,
    ErrorCode.DURABILITY_FAILURE: 1,
    ErrorCode.INTEGRITY_FAILURE: 1,
    ErrorCode.REPLICATION_FAILURE: 1,
    ErrorCode.PARTIAL_EFFECT: 1,
    ErrorCode.INTERNAL: 1,
    ErrorCode.UNKNOWN: 1,
}


@dataclass(frozen=True)
class AdapterOperationProjection:
    """One operation's applicability to an adapter transport.

    A non-applicable record is intentional evidence, not a fallback.  It lets
    callers audit every registered operation even when an operation was not
    advertised through a given interface.
    """

    transport: str
    operation_id: str
    version: int
    applicable: bool
    reason: str
    name: str | None
    request_schema: str
    result_schema: str
    error_schema: str
    capability: str
    support_tier: str
    authorization: Mapping[str, str]

    @classmethod
    def from_transport_projection(cls, projection: TransportProjection) -> "AdapterOperationProjection":
        data = projection.as_dict()
        return cls(
            transport=projection.transport,
            operation_id=projection.operation_id,
            version=projection.version,
            applicable=True,
            reason="",
            name=projection.name,
            request_schema=projection.request_schema,
            result_schema=projection.result_schema,
            error_schema=projection.error_schema,
            capability=projection.capability,
            support_tier=projection.support_tier.value,
            authorization=data["authorization"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "operation_id": self.operation_id,
            "version": self.version,
            "applicable": self.applicable,
            "reason": self.reason,
            "name": self.name,
            "request_schema": self.request_schema,
            "result_schema": self.result_schema,
            "error_schema": self.error_schema,
            "capability": self.capability,
            "support_tier": self.support_tier,
            "access_requirement": dict(self.authorization),
        }


@dataclass(frozen=True)
class AdapterResponse:
    """Canonical result/error envelope shared by Python and CLI adapters."""

    operation: AdapterOperationProjection | None
    result: Any | None = None
    error: StorageError | None = None

    @property
    def success(self) -> bool:
        return self.error is None

    @property
    def exit_code(self) -> int:
        if self.error is None:
            return 0
        if self.error.exit_code_hint:
            return self.error.exit_code_hint
        return EXIT_CODES.get(self.error.code, 1)

    def _operation_record(self) -> dict[str, Any] | None:
        if self.operation is None:
            return None
        # Transport-local public names are intentionally omitted.  Equivalent
        # Python and CLI invocations therefore have identical result records.
        return {
            "operation_id": self.operation.operation_id,
            "version": self.operation.version,
            "request_schema": self.operation.request_schema,
            "result_schema": self.operation.result_schema,
            "error_schema": self.operation.error_schema,
            "capability": self.operation.capability,
            "support_tier": self.operation.support_tier,
            # ``authorization`` is intentionally a protected field spelling
            # in canonical records: it can carry bearer material in an
            # untrusted payload.  This is declarative registry metadata, so
            # retain it under a non-secret-shaped contract field instead.
            "access_requirement": dict(self.operation.authorization),
        }

    def _payload(self) -> dict[str, Any]:
        return {
            "schema": ADAPTER_RESPONSE_SCHEMA,
            "contract_version": ADAPTER_CONTRACT_VERSION,
            "operation": self._operation_record(),
            "success": self.success,
            "result": self.result,
            "error": None if self.error is None else self.error.to_record(),
            "exit_code": self.exit_code,
        }

    @property
    def content_id(self) -> str:
        return content_identity(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "content_id": self.content_id}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def _canonical_result(value: Any) -> dict[str, Any]:
    """Freeze arbitrary JSON-compatible handler output behind a content id."""

    if isinstance(value, CanonicalContract):
        record: Any = value.to_record()
    else:
        # Going through the contract serializer rejects non-finite numbers,
        # cycles, secret-shaped values, and non-canonical key types.
        record = json.loads(canonical_json(value))
    return {"record": record, "content_id": content_identity(record)}


def _failure(
    exception: BaseException,
    projection: AdapterOperationProjection | None,
) -> StorageError:
    """Map known admission outcomes to the closed public error taxonomy."""

    operation_id = "" if projection is None else projection.operation_id
    code = ErrorCode.INTERNAL
    category = ErrorCategory.INTERNAL
    state = OperationState.FAILED
    retryability = Retryability.UNKNOWN
    message = "operation execution failed"

    if isinstance(exception, asyncio.CancelledError):
        code, category, state, retryability, message = (
            ErrorCode.CANCELLED,
            ErrorCategory.CANCELLATION,
            OperationState.CANCELLED,
            Retryability.CALLER_DECIDES,
            "operation was cancelled",
        )
    elif isinstance(exception, UnsupportedOperationError):
        code, category, state, retryability, message = (
            ErrorCode.UNSUPPORTED,
            ErrorCategory.UNSUPPORTED,
            OperationState.UNSUPPORTED,
            Retryability.NEVER,
            "operation is explicitly unsupported",
        )
    elif isinstance(exception, (UnknownOperationError, TypeError, ValueError)):
        code, category, state, retryability, message = (
            ErrorCode.INVALID_REQUEST,
            ErrorCategory.VALIDATION,
            OperationState.REJECTED,
            Retryability.NEVER,
            "operation request was rejected",
        )
    elif isinstance(exception, AuthorizationDeniedError):
        code, category, state, retryability, message = (
            ErrorCode.FORBIDDEN,
            ErrorCategory.AUTHORIZATION,
            OperationState.AUTHORIZATION_DENIED,
            Retryability.NEVER,
            "operation authorization was denied",
        )
    elif isinstance(exception, CapabilityUnavailableError):
        code, category, state, retryability, message = (
            ErrorCode.CAPABILITY_MISSING,
            ErrorCategory.CAPABILITY,
            OperationState.UNAVAILABLE,
            Retryability.AFTER_RECONCILE,
            "required operation capability is unavailable",
        )
    elif isinstance(exception, (HandlerNotBoundError, HandlerBindingError, AsyncDispatchRequiredError)):
        code, category, state, retryability, message = (
            ErrorCode.UNAVAILABLE,
            ErrorCategory.UNAVAILABLE,
            OperationState.UNAVAILABLE,
            Retryability.AFTER_RECONCILE,
            "operation service is unavailable",
        )
    elif isinstance(exception, ServiceRouterError):
        code, category, state, retryability, message = (
            ErrorCode.UNAVAILABLE,
            ErrorCategory.UNAVAILABLE,
            OperationState.UNAVAILABLE,
            Retryability.AFTER_RECONCILE,
            "operation service is unavailable",
        )

    return StorageError(
        code=code,
        category=category,
        message=message,
        retryability=retryability,
        state=state,
        related_operation_id=operation_id,
    )


class _OperationAdapter:
    """Shared routing and serialization mechanics for generated adapters."""

    TRANSPORT: Final[str] = PYTHON_TRANSPORT
    SCHEMA: Final[str] = PYTHON_ADAPTER_SCHEMA

    def __init__(self, registry: OperationRegistry, router: ServiceRouter) -> None:
        if not isinstance(registry, OperationRegistry):
            raise TypeError("registry must be an OperationRegistry")
        if not isinstance(router, ServiceRouter):
            raise TypeError("router must be a ServiceRouter")
        if router.registry is not registry:
            raise ValueError("router must be bound to the supplied registry")
        self.registry = registry
        self.router = router

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

    def metadata(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "contract_version": ADAPTER_CONTRACT_VERSION,
            "transport": self.TRANSPORT,
            "signature": {
                "operation": "str",
                "request": "object",
                "context": "DispatchContext | None = None",
            },
            "operations": [item.to_dict() for item in self.operation_projections()],
            "response_schema": ADAPTER_RESPONSE_SCHEMA,
            "exit_codes": {code.value: value for code, value in EXIT_CODES.items()},
        }

    def _projection_for_name(self, name: str) -> AdapterOperationProjection:
        definition = self.registry.resolve_transport(self.TRANSPORT, name)
        for projection in self.operation_projections():
            if projection.operation_id == definition.operation_id:
                return projection
        # resolve_transport only returns advertised operations; this keeps the
        # invariant explicit if a registry implementation changes.
        raise UnknownOperationError(
            f"operation {name!r} has no {self.TRANSPORT} adapter projection"
        )

    @staticmethod
    def _response_for_value(
        projection: AdapterOperationProjection,
        value: Any,
    ) -> AdapterResponse:
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


class PythonAdapter(_OperationAdapter):
    """Synchronous generated Python adapter for advertised registry operations."""

    TRANSPORT: Final[str] = PYTHON_TRANSPORT
    SCHEMA: Final[str] = PYTHON_ADAPTER_SCHEMA

    def call(
        self,
        operation: str,
        request: Any,
        *,
        context: DispatchContext | None = None,
    ) -> AdapterResponse:
        projection: AdapterOperationProjection | None = None
        try:
            projection = self._projection_for_name(operation)
            value = _run_async_synchronously(
                lambda: self.router.dispatch_async(
                    projection.operation_id, request, context=context
                )
            )
            return self._response_for_value(projection, value)
        except asyncio.CancelledError as error:
            return AdapterResponse(operation=projection, error=_failure(error, projection))
        except Exception as error:
            return AdapterResponse(operation=projection, error=_failure(error, projection))

    invoke = call
    execute = call


class AsyncPythonAdapter(_OperationAdapter):
    """Asynchronous generated Python adapter for the same registry projection."""

    TRANSPORT: Final[str] = PYTHON_TRANSPORT
    SCHEMA: Final[str] = ASYNC_PYTHON_ADAPTER_SCHEMA

    async def call(
        self,
        operation: str,
        request: Any,
        *,
        context: DispatchContext | None = None,
    ) -> AdapterResponse:
        projection: AdapterOperationProjection | None = None
        try:
            projection = self._projection_for_name(operation)
            value = await self.router.dispatch_async(
                projection.operation_id, request, context=context
            )
            return self._response_for_value(projection, value)
        except asyncio.CancelledError as error:
            return AdapterResponse(operation=projection, error=_failure(error, projection))
        except Exception as error:
            return AdapterResponse(operation=projection, error=_failure(error, projection))

    invoke = call
    execute = call


PythonAdapter_V1: Final[str] = PYTHON_ADAPTER_SCHEMA
AsyncPythonAdapter_V1: Final[str] = ASYNC_PYTHON_ADAPTER_SCHEMA


def build_python_adapter(registry: OperationRegistry, router: ServiceRouter) -> PythonAdapter:
    return PythonAdapter(registry, router)


def build_async_python_adapter(
    registry: OperationRegistry, router: ServiceRouter
) -> AsyncPythonAdapter:
    return AsyncPythonAdapter(registry, router)


__all__ = [
    "ADAPTER_CONTRACT_VERSION",
    "ADAPTER_RESPONSE_SCHEMA",
    "ASYNC_PYTHON_ADAPTER_SCHEMA",
    "AsyncPythonAdapter",
    "AsyncPythonAdapter_V1",
    "AdapterOperationProjection",
    "AdapterResponse",
    "EXIT_CODES",
    "PYTHON_ADAPTER_SCHEMA",
    "PYTHON_TRANSPORT",
    "PythonAdapter",
    "PythonAdapter_V1",
    "build_async_python_adapter",
    "build_python_adapter",
]
