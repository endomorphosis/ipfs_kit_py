"""Storage backend type plugins and their side-effect-free registry.

The registry contains configuration behavior, not live backend instances.  In
particular, discovering plugins must never start daemons, resolve credentials,
or connect to storage services.
"""

from __future__ import annotations

import copy
import importlib.metadata
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .backends.spec import (
    ACTIVE_BACKEND_SPECS,
    EXCLUDED_BACKEND_SPECS,
    BackendCapability,
    BackendSpec,
    get_backend_spec,
    normalize_backend_type,
)

BACKEND_ENTRY_POINT_GROUP = "ipfs_kit.backends"
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SENSITIVE_RE = re.compile(
    r"(?:secret|token|ticket|password|passwd|private.?key|node.?key|"
    r"write.?capability|credential|authorization|api.?key|access.?key)",
    re.IGNORECASE,
)


class BackendConfigError(ValueError):
    """A persisted backend document is invalid or unsafe."""

    code = "invalid_backend_config"


class UnknownBackendTypeError(BackendConfigError):
    """No configuration plugin is registered for a backend type."""

    code = "unknown_backend_type"


class BackendRuntimeUnavailableError(BackendConfigError):
    """A configuration backend was asked to perform an undeclared operation."""

    code = "backend_runtime_unavailable"


class ExcludedBackendTypeError(BackendConfigError):
    """A deliberately excluded backend name was requested."""

    code = "excluded_backend_type"


def validate_backend_name(value: Any) -> str:
    """Validate names used both in documents and as config filenames."""

    if not isinstance(value, str) or not _NAME_RE.fullmatch(value):
        raise BackendConfigError(
            "backend name must be 1-64 lowercase letters, digits, underscores, or hyphens"
        )
    return value


def ensure_json_compatible(value: Any, path: str = "config") -> Any:
    """Reject YAML-only values, aliases with cycles, and non-string keys."""

    active: set[int] = set()

    def visit(item: Any, location: str) -> Any:
        if isinstance(item, float) and not math.isfinite(item):
            raise BackendConfigError(f"{location} contains a non-finite number")
        if item is None or isinstance(item, (str, bool, int, float)):
            return item
        if isinstance(item, Mapping):
            identity = id(item)
            if identity in active:
                raise BackendConfigError(f"{location} contains a cyclic mapping")
            active.add(identity)
            result: dict[str, Any] = {}
            try:
                for key, child in item.items():
                    if not isinstance(key, str):
                        raise BackendConfigError(f"{location} contains a non-string key")
                    result[key] = visit(child, f"{location}.{key}")
            finally:
                active.remove(identity)
            return result
        if isinstance(item, (list, tuple)):
            identity = id(item)
            if identity in active:
                raise BackendConfigError(f"{location} contains a cyclic array")
            active.add(identity)
            try:
                return [visit(child, f"{location}[{index}]") for index, child in enumerate(item)]
            finally:
                active.remove(identity)
        raise BackendConfigError(f"{location} contains a non-JSON value")

    return visit(value, path)


def redact_backend_config(value: Any) -> Any:
    """Return an externally safe copy of a backend document.

    Secret reference providers remain visible for diagnostics, but record and
    environment-variable identifiers do not.  This function also protects
    legacy backend documents that may still contain inline credential fields.
    """

    def redact(item: Any, key: str | None = None) -> Any:
        if isinstance(item, Mapping):
            return {str(child_key): redact(child, str(child_key)) for child_key, child in item.items()}
        if isinstance(item, list):
            return [redact(child) for child in item]
        if isinstance(item, tuple):
            return [redact(child) for child in item]
        if key is not None and _SENSITIVE_RE.search(key):
            if isinstance(item, str) and item.startswith("secretref:"):
                parts = item.split(":", 2)
                return f"secretref:{parts[1]}:<redacted>" if len(parts) == 3 else "<redacted>"
            return "<redacted>"
        return copy.deepcopy(item)

    return redact(value)


@runtime_checkable
class BackendPlugin(Protocol):
    """Configuration and introspection contract for named backend types.

    Runtime operations are intentionally *not* part of this protocol.  Plugins
    may implement :class:`BackendRuntimeFactory`, but only a matching
    ``BackendSpec`` capability permits the registry to invoke it.
    """

    type_name: str
    schema_version: int | None

    def validate(self, config: Mapping[str, Any]) -> dict[str, Any]: ...

    def migrate(self, config: Mapping[str, Any]) -> dict[str, Any]: ...

    def capabilities(self, config: Mapping[str, Any]) -> dict[str, Any]: ...

    def health(self, config: Mapping[str, Any]) -> dict[str, Any]: ...

    def schema(self) -> dict[str, Any] | None: ...


@runtime_checkable
class BackendRuntimeFactory(Protocol):
    """Optional runtime contract for plugins that create filesystem adapters."""

    def create_filesystem(
        self, config: Mapping[str, Any], **storage_options: Any
    ) -> Any: ...


@dataclass(frozen=True)
class LegacyBackendPlugin:
    """Compatibility plugin for the manager's established backend names."""

    type_name: str
    schema_version: int | None = None

    def validate(self, config: Mapping[str, Any]) -> dict[str, Any]:
        value = ensure_json_compatible(config)
        validate_backend_name(value.get("name"))
        supplied_type = value.get("type")
        canonical_type = normalize_backend_type(supplied_type, include_excluded=False)
        if canonical_type != self.type_name:
            raise BackendConfigError(f"backend type must be {self.type_name!r}")
        value["type"] = canonical_type
        return value

    def migrate(self, config: Mapping[str, Any]) -> dict[str, Any]:
        return self.validate(config)

    def capabilities(self, config: Mapping[str, Any]) -> dict[str, Any]:
        del config
        return {
            "named": True,
            "schema_validated": False,
            "configuration": True,
            "health": True,
            "runtime_factory": False,
            "storage": False,
        }

    def health(self, config: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "healthy": None,
            "status": "not-probed",
            "enabled": bool(config.get("enabled", True)),
        }

    def schema(self) -> dict[str, Any]:
        # Keep the legacy plugin protocol useful to callers while sourcing the
        # actual shape from the same canonical inventory as the registry.
        from .backend_schemas import get_backend_schema

        schema = get_backend_schema(self.type_name, include_excluded=False)
        if schema is None:  # Defensive: every active spec must have a schema.
            raise BackendConfigError(f"backend schema is unavailable: {self.type_name!r}")
        return schema


class BackendTypeRegistry:
    """Mutable registry with built-ins and optional package entry points."""

    LEGACY_TYPES = tuple(
        type_name for type_name in ACTIVE_BACKEND_SPECS if type_name != "iroh"
    )

    def __init__(self, *, load_entry_points: bool = True) -> None:
        self._plugins: dict[str, BackendPlugin] = {}
        for type_name in self.LEGACY_TYPES:
            self.register(LegacyBackendPlugin(type_name))

        # Direct registration makes source checkouts work even when package
        # metadata has not been rebuilt.  Importing this module is inert.
        from .iroh.backend import IrohBackendPlugin

        self.register(IrohBackendPlugin())
        if load_entry_points:
            self.load_entry_points()

    def register(self, plugin: BackendPlugin, *, replace: bool = False) -> None:
        if isinstance(plugin, type):
            plugin = plugin()
        if not isinstance(plugin, BackendPlugin):
            raise TypeError("backend plugin does not implement the registry protocol")
        type_name = getattr(plugin, "type_name", None)
        if not isinstance(type_name, str) or not _NAME_RE.fullmatch(type_name):
            raise TypeError("backend plugin type_name is invalid")
        canonical_type = normalize_backend_type(type_name, include_excluded=False)
        if canonical_type is None:
            if get_backend_spec(type_name, include_excluded=True) is not None:
                raise ExcludedBackendTypeError(
                    f"backend type is explicitly excluded: {type_name!r}"
                )
            raise TypeError(
                f"backend plugin {type_name!r} has no canonical BackendSpec"
            )
        if canonical_type != type_name:
            raise TypeError(
                f"backend plugin type_name must be canonical: {canonical_type!r}"
            )
        if canonical_type in self._plugins and not replace:
            existing = self._plugins[canonical_type]
            # Installed metadata commonly points to the same built-in plugin.
            if type(existing) is type(plugin):
                return
            raise ValueError(f"backend plugin {canonical_type!r} is already registered")
        self._plugins[canonical_type] = plugin

    def load_entry_points(self) -> None:
        try:
            selected = importlib.metadata.entry_points(group=BACKEND_ENTRY_POINT_GROUP)
        except TypeError:  # Python/importlib-metadata compatibility
            selected = importlib.metadata.entry_points().select(group=BACKEND_ENTRY_POINT_GROUP)
        except Exception:
            return
        for entry_point in selected:
            try:
                loaded = entry_point.load()
                plugin = loaded() if isinstance(loaded, type) else loaded
                self.register(plugin)
            except Exception:
                # A broken third-party plugin must not make built-ins unusable.
                continue

    def get(self, type_name: str) -> BackendPlugin:
        canonical_type = normalize_backend_type(type_name, include_excluded=False)
        if canonical_type is not None:
            try:
                return self._plugins[canonical_type]
            except KeyError:
                # A plugin might be absent only when an installation is
                # partially broken; do not turn registry presence into support.
                raise UnknownBackendTypeError(
                    f"backend plugin is unavailable: {canonical_type!r}"
                ) from None
        excluded = get_backend_spec(type_name, include_excluded=True)
        if excluded is not None and excluded.is_excluded:
            raise ExcludedBackendTypeError(
                f"backend type is explicitly excluded: {excluded.type_name!r}; "
                f"{excluded.excluded_reason}"
            )
        raise UnknownBackendTypeError(f"unknown backend type: {type_name!r}")

    def spec(self, type_name: str, *, include_excluded: bool = True) -> BackendSpec:
        """Return an explicit inventory record for a canonical name or alias."""

        spec = get_backend_spec(type_name, include_excluded=include_excluded)
        if spec is None:
            raise UnknownBackendTypeError(f"unknown backend type: {type_name!r}")
        return spec

    def get_runtime_factory(self, type_name: str) -> BackendRuntimeFactory:
        """Return a capability-gated runtime factory for ``type_name``.

        Configuration-only plugins intentionally fail here before any plugin
        method is inspected or invoked.
        """

        spec = self.spec(type_name)
        if spec.is_excluded:
            raise ExcludedBackendTypeError(
                f"backend {type_name!r} is explicitly excluded: {spec.excluded_reason}"
            )
        if (
            not spec.supports(BackendCapability.STORAGE)
            or not spec.supports(BackendCapability.RUNTIME_FACTORY)
            or not spec.runtime_factory
        ):
            raise BackendRuntimeUnavailableError(
                f"backend {spec.type_name!r} does not declare a storage runtime factory"
            )
        plugin = self.get(spec.type_name)
        if not isinstance(plugin, BackendRuntimeFactory):
            raise BackendRuntimeUnavailableError(
                f"backend {spec.type_name!r} declares {spec.runtime_factory!r}, "
                "but its plugin does not implement that contract"
            )
        return plugin

    def create_filesystem(
        self, type_name: str, config: Mapping[str, Any], **storage_options: Any
    ) -> Any:
        """Create a filesystem only through the declared runtime capability."""

        factory = self.get_runtime_factory(type_name)
        return factory.create_filesystem(config, **storage_options)

    def types(self) -> tuple[str, ...]:
        return tuple(sorted(self._plugins))

    def describe(self, *, include_excluded: bool = False) -> dict[str, dict[str, Any]]:
        """Describe the explicit contract; support tier never comes from membership."""

        specs: Mapping[str, BackendSpec] = ACTIVE_BACKEND_SPECS
        if include_excluded:
            specs = {**ACTIVE_BACKEND_SPECS, **EXCLUDED_BACKEND_SPECS}
        description: dict[str, dict[str, Any]] = {}
        for name, spec in sorted(specs.items()):
            plugin = self._plugins.get(name)
            names = list(spec.names)
            description[name] = {
                "type": name,
                "aliases": list(spec.aliases),
                # The one declared name set is shared by CLI, MCP, and docs
                # until a surface requires a genuinely distinct public name.
                "cli_names": names,
                "mcp_names": names,
                "documentation_names": names,
                "schema_version": plugin.schema_version if plugin else None,
                "schema_validated": plugin is not None and plugin.schema_version is not None,
                "capabilities": sorted(capability.value for capability in spec.capabilities),
                "health_contract": spec.health_contract,
                "secret_fields": list(spec.secret_fields),
                "runtime_factory": spec.runtime_factory,
                "support_tier": spec.support_tier.value,
                "support_tier_source": "explicit-backend-spec",
                "excluded": spec.is_excluded,
                "excluded_reason": spec.excluded_reason,
            }
        return description


# Compatibility spelling for callers that do not need to distinguish a
# configuration plugin registry from a live backend-instance registry.
BackendRegistry = BackendTypeRegistry


_DEFAULT_REGISTRY: BackendTypeRegistry | None = None


def get_backend_type_registry() -> BackendTypeRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = BackendTypeRegistry()
    return _DEFAULT_REGISTRY


__all__ = [
    "BACKEND_ENTRY_POINT_GROUP",
    "BackendCapability",
    "BackendConfigError",
    "BackendPlugin",
    "BackendRegistry",
    "BackendRuntimeFactory",
    "BackendRuntimeUnavailableError",
    "BackendSpec",
    "BackendTypeRegistry",
    "ExcludedBackendTypeError",
    "LegacyBackendPlugin",
    "UnknownBackendTypeError",
    "ensure_json_compatible",
    "get_backend_type_registry",
    "redact_backend_config",
    "validate_backend_name",
]
