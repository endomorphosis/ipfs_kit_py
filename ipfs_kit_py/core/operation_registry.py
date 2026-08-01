"""Inert, versioned definitions for canonical storage operations.

The registry is deliberately declarative: an operation records its contracts,
capability, authorization requirement, service route, and public transport
names, but it never imports or instantiates a storage provider.  Adapters use
the deterministic projections in this module; execution belongs exclusively
to :mod:`service_router`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Final


OPERATION_REGISTRY_VERSION: Final[int] = 1
OPERATION_REGISTRY_SCHEMA: Final[str] = "ipfs_kit_py/core/operation-registry@1"
OperationRegistry_V1: Final[str] = OPERATION_REGISTRY_SCHEMA

MAX_IDENTIFIER_BYTES: Final[int] = 512
_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/#@+\-]{0,511}$"
)
_TRANSPORT_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class OperationRegistryError(ValueError):
    """Base class for fail-closed registry failures."""


class InvalidOperationDefinitionError(OperationRegistryError):
    """An operation definition is incomplete, malformed, or ambiguous."""


class DuplicateOperationIdentifierError(OperationRegistryError):
    """An operation id, alias, or transport name would be ambiguous."""


class UnknownOperationError(OperationRegistryError):
    """No registered operation owns the supplied id or alias."""


class UnsupportedOperationError(OperationRegistryError):
    """A known operation is explicitly unsupported and cannot be dispatched."""

    def __init__(self, operation: "OperationDefinition") -> None:
        self.operation = operation
        super().__init__(
            f"operation {operation.operation_id!r} is explicitly unsupported"
        )


class CapabilityTier(str, Enum):
    """Honest support classifications from the runtime-readiness plan."""

    PRODUCTION = "production"
    CONDITIONAL = "conditional"
    CONFIGURATION_ONLY = "configuration_only"
    EXPERIMENTAL = "experimental"
    UNSUPPORTED = "unsupported"


class AuthorizationClass(str, Enum):
    """Whether dispatch is public or requires an exact resource/ability grant."""

    PUBLIC = "public"
    PROTECTED = "protected"


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise InvalidOperationDefinitionError(f"{field_name} must be a string")
    if not value or len(value.encode("utf-8")) > MAX_IDENTIFIER_BYTES:
        raise InvalidOperationDefinitionError(
            f"{field_name} must contain 1..{MAX_IDENTIFIER_BYTES} UTF-8 bytes"
        )
    if _IDENTIFIER_RE.fullmatch(value) is None:
        raise InvalidOperationDefinitionError(
            f"{field_name} contains characters outside the registry identifier grammar"
        )
    return value


@dataclass(frozen=True)
class AuthorizationRequirement:
    """The complete authorization classification for one operation.

    Public operations deliberately carry no resource or ability.  Protected
    operations require both fields so a transport cannot broaden a grant by
    inventing a default resource or ability.
    """

    classification: AuthorizationClass
    resource: str | None = None
    ability: str | None = None

    def __post_init__(self) -> None:
        try:
            classification = AuthorizationClass(self.classification)
        except (TypeError, ValueError) as error:
            raise InvalidOperationDefinitionError(
                "authorization classification must be public or protected"
            ) from error
        object.__setattr__(self, "classification", classification)

        if classification is AuthorizationClass.PUBLIC:
            if self.resource is not None or self.ability is not None:
                raise InvalidOperationDefinitionError(
                    "public operations must not declare an authorization resource or ability"
                )
            return

        object.__setattr__(self, "resource", _identifier(self.resource, "authorization resource"))
        object.__setattr__(self, "ability", _identifier(self.ability, "authorization ability"))

    @classmethod
    def public(cls) -> "AuthorizationRequirement":
        return cls(AuthorizationClass.PUBLIC)

    @classmethod
    def protected(cls, resource: str, ability: str) -> "AuthorizationRequirement":
        return cls(AuthorizationClass.PROTECTED, resource=resource, ability=ability)


@dataclass(frozen=True)
class OperationDefinition:
    """One complete, immutable operation registration.

    ``handler_route`` is an opaque service-side identifier, never a callable.
    Keeping callables out of the registry is what makes importing and
    projecting it safe: provider imports happen only when a router is given a
    concrete service binding.
    """

    operation_id: str
    version: int
    request_schema: str
    result_schema: str
    error_schema: str
    capability: str
    authorization: AuthorizationRequirement
    handler_route: str
    aliases: tuple[str, ...] = ()
    transport_names: Mapping[str, str] = field(default_factory=dict)
    support_tier: CapabilityTier = CapabilityTier.PRODUCTION

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation_id", _identifier(self.operation_id, "operation id"))
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise InvalidOperationDefinitionError("operation version must be a positive integer")

        for name in ("request_schema", "result_schema", "error_schema", "capability", "handler_route"):
            object.__setattr__(self, name, _identifier(getattr(self, name), name.replace("_", " ")))
        if len({self.request_schema, self.result_schema, self.error_schema}) != 3:
            raise InvalidOperationDefinitionError(
                "request, result, and error schemas must be three distinct contracts"
            )
        if not isinstance(self.authorization, AuthorizationRequirement):
            raise InvalidOperationDefinitionError(
                "authorization must be an AuthorizationRequirement"
            )
        try:
            support_tier = CapabilityTier(self.support_tier)
        except (TypeError, ValueError) as error:
            raise InvalidOperationDefinitionError("unsupported capability support tier") from error
        object.__setattr__(self, "support_tier", support_tier)

        aliases = tuple(_identifier(alias, "operation alias") for alias in self.aliases)
        if self.operation_id in aliases or len(set(aliases)) != len(aliases):
            raise InvalidOperationDefinitionError(
                "operation aliases must be distinct and cannot repeat the operation id"
            )
        object.__setattr__(self, "aliases", aliases)

        if not isinstance(self.transport_names, Mapping):
            raise InvalidOperationDefinitionError("transport_names must be a mapping")
        transport_names: dict[str, str] = {}
        for transport, public_name in self.transport_names.items():
            if not isinstance(transport, str) or _TRANSPORT_RE.fullmatch(transport) is None:
                raise InvalidOperationDefinitionError(
                    "transport name must be a lower-case transport identifier"
                )
            transport_names[transport] = _identifier(public_name, "transport operation name")
        object.__setattr__(
            self,
            "transport_names",
            MappingProxyType(dict(sorted(transport_names.items()))),
        )

    @property
    def handler(self) -> str:
        """Compatibility-friendly name for the opaque service route."""

        return self.handler_route

    @property
    def capability_id(self) -> str:
        """Explicit name for the declared capability identifier."""

        return self.capability

    @property
    def is_unsupported(self) -> bool:
        return self.support_tier is CapabilityTier.UNSUPPORTED


# A concise name for callers that prefer "specification" over "definition".
OperationSpec = OperationDefinition


@dataclass(frozen=True)
class TransportProjection:
    """A transport-safe, deterministic projection of an operation definition."""

    transport: str
    name: str
    operation_id: str
    version: int
    request_schema: str
    result_schema: str
    error_schema: str
    capability: str
    support_tier: CapabilityTier
    authorization: AuthorizationRequirement

    def as_dict(self) -> dict[str, Any]:
        """Return plain data in a stable field order for adapter generation."""

        authorization: dict[str, str] = {
            "classification": self.authorization.classification.value,
        }
        if self.authorization.classification is AuthorizationClass.PROTECTED:
            authorization["resource"] = self.authorization.resource  # type: ignore[assignment]
            authorization["ability"] = self.authorization.ability  # type: ignore[assignment]
        return {
            "transport": self.transport,
            "name": self.name,
            "operation_id": self.operation_id,
            "version": self.version,
            "request_schema": self.request_schema,
            "result_schema": self.result_schema,
            "error_schema": self.error_schema,
            "capability": self.capability,
            "support_tier": self.support_tier.value,
            "authorization": authorization,
        }


class OperationRegistry:
    """An in-memory, fail-closed registry with deterministic projections.

    Registering a definition performs all ambiguity checks up front.  No
    provider, service, adapter, or handler is imported or called by this
    class.
    """

    version: Final[int] = OPERATION_REGISTRY_VERSION

    def __init__(self, definitions: Iterable[OperationDefinition] = ()) -> None:
        self._operations: dict[str, OperationDefinition] = {}
        self._aliases: dict[str, str] = {}
        self._transport_names: dict[tuple[str, str], str] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: OperationDefinition) -> OperationDefinition:
        """Add a fully specified operation or reject every ambiguous identifier."""

        if not isinstance(definition, OperationDefinition):
            raise InvalidOperationDefinitionError("registry entries must be OperationDefinition instances")
        identifiers = (definition.operation_id, *definition.aliases)
        for identifier in identifiers:
            if identifier in self._operations or identifier in self._aliases:
                raise DuplicateOperationIdentifierError(
                    f"operation id or alias {identifier!r} is already registered"
                )
        for transport, public_name in definition.transport_names.items():
            key = (transport, public_name)
            if key in self._transport_names:
                raise DuplicateOperationIdentifierError(
                    f"transport operation name {public_name!r} is already registered for {transport!r}"
                )

        self._operations[definition.operation_id] = definition
        self._aliases.update({alias: definition.operation_id for alias in definition.aliases})
        self._transport_names.update(
            {
                (transport, public_name): definition.operation_id
                for transport, public_name in definition.transport_names.items()
            }
        )
        return definition

    def resolve(self, operation: str) -> OperationDefinition:
        """Resolve an exact operation id or a registered alias, never a prefix."""

        if not isinstance(operation, str):
            raise UnknownOperationError("operation id or alias must be a string")
        canonical_id = self._aliases.get(operation, operation)
        try:
            return self._operations[canonical_id]
        except KeyError as error:
            raise UnknownOperationError(f"unknown operation {operation!r}") from error

    get = resolve

    def resolve_transport(self, transport: str, name: str) -> OperationDefinition:
        """Resolve a generated transport name without any adapter-specific logic."""

        try:
            operation_id = self._transport_names[(transport, name)]
        except (KeyError, TypeError) as error:
            raise UnknownOperationError(
                f"unknown operation {name!r} for transport {transport!r}"
            ) from error
        return self._operations[operation_id]

    def operations(self) -> tuple[OperationDefinition, ...]:
        """Return all definitions in canonical operation-id order."""

        return tuple(self._operations[key] for key in sorted(self._operations))

    definitions = operations

    def transport_projection(self, transport: str) -> tuple[TransportProjection, ...]:
        """Return the stable generated projection for one transport."""

        if not isinstance(transport, str):
            raise InvalidOperationDefinitionError("transport must be a string")
        projections = [
            TransportProjection(
                transport=transport,
                name=definition.transport_names[transport],
                operation_id=definition.operation_id,
                version=definition.version,
                request_schema=definition.request_schema,
                result_schema=definition.result_schema,
                error_schema=definition.error_schema,
                capability=definition.capability,
                support_tier=definition.support_tier,
                authorization=definition.authorization,
            )
            for definition in self.operations()
            if transport in definition.transport_names
        ]
        return tuple(sorted(projections, key=lambda projection: (projection.name, projection.operation_id)))

    def projections(self) -> Mapping[str, tuple[TransportProjection, ...]]:
        """Return every transport projection with canonical transport ordering."""

        transports = sorted({transport for transport, _ in self._transport_names})
        return MappingProxyType(
            {transport: self.transport_projection(transport) for transport in transports}
        )

    def canonical_projection(self) -> dict[str, Any]:
        """Return a JSON-ready registry projection with no executable objects."""

        return {
            "schema": OPERATION_REGISTRY_SCHEMA,
            "version": OPERATION_REGISTRY_VERSION,
            "operations": [
                {
                    "operation_id": definition.operation_id,
                    "version": definition.version,
                    "aliases": list(definition.aliases),
                    "request_schema": definition.request_schema,
                    "result_schema": definition.result_schema,
                    "error_schema": definition.error_schema,
                    "capability": definition.capability,
                    "handler_route": definition.handler_route,
                    "support_tier": definition.support_tier.value,
                    "authorization": {
                        "classification": definition.authorization.classification.value,
                        **(
                            {
                                "resource": definition.authorization.resource,
                                "ability": definition.authorization.ability,
                            }
                            if definition.authorization.classification
                            is AuthorizationClass.PROTECTED
                            else {}
                        ),
                    },
                    "transport_names": dict(definition.transport_names),
                }
                for definition in self.operations()
            ],
        }

    def canonical_json_bytes(self) -> bytes:
        """Serialize the projection in one stable, whitespace-free JSON form."""

        return json.dumps(
            self.canonical_projection(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")

    def __contains__(self, operation: object) -> bool:
        return isinstance(operation, str) and (
            operation in self._operations or operation in self._aliases
        )

    def __len__(self) -> int:
        return len(self._operations)


__all__ = [
    "AuthorizationClass",
    "AuthorizationRequirement",
    "CapabilityTier",
    "DuplicateOperationIdentifierError",
    "InvalidOperationDefinitionError",
    "OPERATION_REGISTRY_SCHEMA",
    "OPERATION_REGISTRY_VERSION",
    "OperationDefinition",
    "OperationRegistry",
    "OperationRegistryError",
    "OperationRegistry_V1",
    "OperationSpec",
    "TransportProjection",
    "UnknownOperationError",
    "UnsupportedOperationError",
]
