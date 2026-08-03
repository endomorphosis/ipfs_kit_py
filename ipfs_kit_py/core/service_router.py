"""The sole dispatch boundary between operation adapters and storage services.

This module contains routing and admission only.  It has no provider imports,
fallbacks, retries, transport handling, or storage business logic.  Providers
are supplied explicitly as service bindings after an authorized dispatch is
selected.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol, TypeAlias, runtime_checkable

from .operation_registry import (
    AuthorizationClass,
    AuthorizationRequirement,
    OperationDefinition,
    OperationRegistry,
    UnsupportedOperationError,
)


SERVICE_ROUTER_SCHEMA = "ipfs_kit_py/core/service-router@1"
CANONICAL_STORAGE_SERVICE_SCHEMA = (
    "ipfs_kit_py/core/service-router/canonical-storage-service@1"
)
ServiceRouter_V1 = SERVICE_ROUTER_SCHEMA
CanonicalStorageService_V1 = CANONICAL_STORAGE_SERVICE_SCHEMA


class ServiceRouterError(RuntimeError):
    """Base class for router admission and binding failures."""


class HandlerBindingError(ServiceRouterError):
    """A service binding is invalid or does not match the operation registry."""


class HandlerNotBoundError(ServiceRouterError):
    """The registry route has no concrete service binding."""


class CapabilityUnavailableError(ServiceRouterError):
    """The bound service does not advertise a required capability."""


class AuthorizationDeniedError(ServiceRouterError):
    """A protected operation lacks an explicit successful authorization decision."""


class AsyncDispatchRequiredError(ServiceRouterError):
    """An asynchronous admission check or handler requires ``dispatch_async``."""


@dataclass(frozen=True)
class DispatchContext:
    """Transport-neutral context presented to authorization and service code."""

    principal: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.principal is not None and (
            not isinstance(self.principal, str) or not self.principal
        ):
            raise ValueError("principal must be a non-empty string or None")
        if not isinstance(self.attributes, Mapping):
            raise ValueError("dispatch context attributes must be a mapping")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


CanonicalServiceHandler: TypeAlias = Callable[[OperationDefinition, Any, DispatchContext], Any]
AuthorizationDecider: TypeAlias = Callable[[AuthorizationRequirement, DispatchContext], bool | Any]
CapabilityDecider: TypeAlias = Callable[[OperationDefinition, DispatchContext], bool | Any]


@runtime_checkable
class CanonicalStorageService(Protocol):
    """Minimal service shape accepted by :meth:`ServiceRouter.bind_service`.

    The service owns semantic storage work.  It receives the resolved immutable
    operation definition and cannot choose a fallback operation or provider.
    """

    def execute(
        self, operation: OperationDefinition, request: Any, context: DispatchContext
    ) -> Any:
        """Execute exactly the resolved canonical operation."""


@dataclass(frozen=True)
class ServiceBinding:
    """An explicit service handler and the capabilities it currently exposes."""

    route: str
    handler: CanonicalServiceHandler
    capabilities: frozenset[str]


class ServiceRouter:
    """Resolve, admit, and dispatch operations with no transport fallback.

    A protected operation is denied when no authorizer is supplied, when the
    authorizer denies it, or when the authorizer fails.  A service can execute
    an operation only after its exact route is bound and it advertises the
    exact declared capability.  Explicitly unsupported operations are rejected
    before route lookup, capability checks, authorization, or handler calls.
    """

    def __init__(
        self,
        registry: OperationRegistry,
        *,
        authorizer: AuthorizationDecider | None = None,
        capability_checker: CapabilityDecider | None = None,
    ) -> None:
        if not isinstance(registry, OperationRegistry):
            raise TypeError("registry must be an OperationRegistry")
        if authorizer is not None and not callable(authorizer):
            raise TypeError("authorizer must be callable")
        if capability_checker is not None and not callable(capability_checker):
            raise TypeError("capability_checker must be callable")
        self.registry = registry
        self._authorizer = authorizer
        self._capability_checker = capability_checker
        self._bindings: dict[str, ServiceBinding] = {}

    def bind_handler(
        self,
        route: str,
        handler: CanonicalServiceHandler,
        *,
        capabilities: frozenset[str] | set[str] | tuple[str, ...] | list[str],
    ) -> ServiceBinding:
        """Bind one route to one handler without importing or probing providers."""

        if not isinstance(route, str) or not route:
            raise HandlerBindingError("service route must be a non-empty string")
        if not callable(handler):
            raise HandlerBindingError("service handler must be callable")
        known_routes = {definition.handler_route for definition in self.registry.operations()}
        if route not in known_routes:
            raise HandlerBindingError(f"service route {route!r} is not declared by the registry")
        try:
            declared_capabilities = frozenset(capabilities)
        except TypeError as error:
            raise HandlerBindingError("capabilities must be an iterable of identifiers") from error
        if not declared_capabilities or any(
            not isinstance(capability, str) or not capability for capability in declared_capabilities
        ):
            raise HandlerBindingError("service bindings require non-empty capability identifiers")
        binding = ServiceBinding(route, handler, declared_capabilities)
        self._bindings[route] = binding
        return binding

    register_handler = bind_handler

    def bind_service(
        self,
        route: str,
        service: CanonicalStorageService,
        *,
        capabilities: frozenset[str] | set[str] | tuple[str, ...] | list[str],
    ) -> ServiceBinding:
        """Bind a canonical service through its one required ``execute`` method."""

        execute = getattr(service, "execute", None)
        if not callable(execute):
            raise HandlerBindingError(
                "canonical storage services must expose a callable execute method"
            )
        return self.bind_handler(route, execute, capabilities=capabilities)

    def bindings(self) -> Mapping[str, ServiceBinding]:
        """Expose immutable binding metadata for diagnostics, never provider internals."""

        return MappingProxyType(dict(sorted(self._bindings.items())))

    def dispatch(
        self,
        operation: str,
        request: Any,
        *,
        context: DispatchContext | None = None,
    ) -> Any:
        """Synchronously dispatch one operation, rejecting asynchronous work explicitly."""

        # KITA-044: share the process-wide hot-path bound; authorization and
        # capability checks still run inside _admit with identical semantics.
        from ipfs_kit_py.core.performance import HotPathGate

        with HotPathGate(payload_bytes=0, fairness_class="router-dispatch"):
            definition, binding, dispatch_context = self._admit(
                operation, context, asynchronous=False
            )
            result = binding.handler(definition, request, dispatch_context)
            return self._synchronous_value(result, "service handler")

    async def dispatch_async(
        self,
        operation: str,
        request: Any,
        *,
        context: DispatchContext | None = None,
    ) -> Any:
        """Dispatch one operation while allowing explicit async checks and handlers."""

        from ipfs_kit_py.core.performance import HotPathGate

        with HotPathGate(payload_bytes=0, fairness_class="router-dispatch-async"):
            definition, binding, dispatch_context = await self._admit_async(operation, context)
            result = binding.handler(definition, request, dispatch_context)
            if inspect.isawaitable(result):
                return await result
            return result

    def _admit(
        self,
        operation: str,
        context: DispatchContext | None,
        *,
        asynchronous: bool,
    ) -> tuple[OperationDefinition, ServiceBinding, DispatchContext]:
        definition = self.registry.resolve(operation)
        if definition.is_unsupported:
            raise UnsupportedOperationError(definition)
        dispatch_context = self._context(context)
        binding = self._binding_for(definition)
        self._check_capability(definition, binding, dispatch_context, asynchronous=asynchronous)
        self._check_authorization(definition.authorization, dispatch_context, asynchronous=asynchronous)
        return definition, binding, dispatch_context

    async def _admit_async(
        self, operation: str, context: DispatchContext | None
    ) -> tuple[OperationDefinition, ServiceBinding, DispatchContext]:
        definition = self.registry.resolve(operation)
        if definition.is_unsupported:
            raise UnsupportedOperationError(definition)
        dispatch_context = self._context(context)
        binding = self._binding_for(definition)
        await self._check_capability_async(definition, binding, dispatch_context)
        await self._check_authorization_async(definition.authorization, dispatch_context)
        return definition, binding, dispatch_context

    @staticmethod
    def _context(context: DispatchContext | None) -> DispatchContext:
        if context is None:
            return DispatchContext()
        if not isinstance(context, DispatchContext):
            raise TypeError("context must be a DispatchContext")
        return context

    def _binding_for(self, definition: OperationDefinition) -> ServiceBinding:
        try:
            binding = self._bindings[definition.handler_route]
        except KeyError as error:
            raise HandlerNotBoundError(
                f"no service handler is bound for route {definition.handler_route!r}"
            ) from error
        if definition.capability not in binding.capabilities:
            raise CapabilityUnavailableError(
                f"service route {definition.handler_route!r} does not expose capability "
                f"{definition.capability!r}"
            )
        return binding

    def _check_capability(
        self,
        definition: OperationDefinition,
        binding: ServiceBinding,
        context: DispatchContext,
        *,
        asynchronous: bool,
    ) -> None:
        del binding  # capability declaration was checked in _binding_for
        if self._capability_checker is None:
            return
        try:
            decision = self._capability_checker(definition, context)
        except Exception as error:
            raise CapabilityUnavailableError(
                f"capability check failed for {definition.capability!r}"
            ) from error
        if asynchronous:
            return
        if not self._synchronous_value(decision, "capability checker"):
            raise CapabilityUnavailableError(
                f"capability {definition.capability!r} is unavailable"
            )

    async def _check_capability_async(
        self, definition: OperationDefinition, binding: ServiceBinding, context: DispatchContext
    ) -> None:
        del binding
        if self._capability_checker is None:
            return
        try:
            decision = self._capability_checker(definition, context)
            if inspect.isawaitable(decision):
                decision = await decision
        except Exception as error:
            raise CapabilityUnavailableError(
                f"capability check failed for {definition.capability!r}"
            ) from error
        if not decision:
            raise CapabilityUnavailableError(
                f"capability {definition.capability!r} is unavailable"
            )

    def _check_authorization(
        self,
        requirement: AuthorizationRequirement,
        context: DispatchContext,
        *,
        asynchronous: bool,
    ) -> None:
        if requirement.classification is AuthorizationClass.PUBLIC:
            return
        if self._authorizer is None:
            raise AuthorizationDeniedError("protected operation requires an authorizer")
        try:
            decision = self._authorizer(requirement, context)
        except Exception as error:
            raise AuthorizationDeniedError("authorizer failed while evaluating protected operation") from error
        if asynchronous:
            return
        if not self._synchronous_value(decision, "authorizer"):
            raise AuthorizationDeniedError("authorizer denied protected operation")

    async def _check_authorization_async(
        self, requirement: AuthorizationRequirement, context: DispatchContext
    ) -> None:
        if requirement.classification is AuthorizationClass.PUBLIC:
            return
        if self._authorizer is None:
            raise AuthorizationDeniedError("protected operation requires an authorizer")
        try:
            decision = self._authorizer(requirement, context)
            if inspect.isawaitable(decision):
                decision = await decision
        except Exception as error:
            raise AuthorizationDeniedError("authorizer failed while evaluating protected operation") from error
        if not decision:
            raise AuthorizationDeniedError("authorizer denied protected operation")

    @staticmethod
    def _synchronous_value(value: Any, source: str) -> Any:
        if inspect.isawaitable(value):
            # Avoid leaking a never-awaited coroutine while still refusing to
            # invent an event loop or use a synchronous fallback.
            if inspect.iscoroutine(value):
                value.close()
            raise AsyncDispatchRequiredError(f"{source} is asynchronous; use dispatch_async")
        return value


__all__ = [
    "AsyncDispatchRequiredError",
    "AuthorizationDeniedError",
    "CanonicalServiceHandler",
    "CanonicalStorageService",
    "CANONICAL_STORAGE_SERVICE_SCHEMA",
    "CanonicalStorageService_V1",
    "CapabilityUnavailableError",
    "DispatchContext",
    "HandlerBindingError",
    "HandlerNotBoundError",
    "ServiceBinding",
    "ServiceRouter",
    "ServiceRouterError",
    "SERVICE_ROUTER_SCHEMA",
    "ServiceRouter_V1",
]
