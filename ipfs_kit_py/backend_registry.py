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
    """Configuration and introspection contract for named backend types."""

    type_name: str
    schema_version: int | None

    def validate(self, config: Mapping[str, Any]) -> dict[str, Any]: ...

    def migrate(self, config: Mapping[str, Any]) -> dict[str, Any]: ...

    def capabilities(self, config: Mapping[str, Any]) -> dict[str, Any]: ...

    def health(self, config: Mapping[str, Any]) -> dict[str, Any]: ...

    def schema(self) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class LegacyBackendPlugin:
    """Compatibility plugin for the manager's established backend names."""

    type_name: str
    schema_version: int | None = None

    def validate(self, config: Mapping[str, Any]) -> dict[str, Any]:
        value = ensure_json_compatible(config)
        validate_backend_name(value.get("name"))
        if value.get("type") != self.type_name:
            raise BackendConfigError(f"backend type must be {self.type_name!r}")
        return value

    def migrate(self, config: Mapping[str, Any]) -> dict[str, Any]:
        return self.validate(config)

    def capabilities(self, config: Mapping[str, Any]) -> dict[str, Any]:
        del config
        return {"named": True, "schema_validated": False}

    def health(self, config: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "healthy": None,
            "status": "not-probed",
            "enabled": bool(config.get("enabled", True)),
        }

    def schema(self) -> None:
        return None


class BackendTypeRegistry:
    """Mutable registry with built-ins and optional package entry points."""

    LEGACY_TYPES = (
        "cluster",
        "digitalocean",
        "estuary",
        "filecoin",
        "filecoin_pin",
        "filesystem",
        "ftp",
        "gdrive",
        "github",
        "huggingface",
        "ipfs",
        "ipfs_cluster",
        "lassie",
        "local",
        "local_fs",
        "local_storage",
        "minio",
        "parquet",
        "s3",
        "sshfs",
        "storacha",
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
        if type_name in self._plugins and not replace:
            existing = self._plugins[type_name]
            # Installed metadata commonly points to the same built-in plugin.
            if type(existing) is type(plugin):
                return
            raise ValueError(f"backend plugin {type_name!r} is already registered")
        self._plugins[type_name] = plugin

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
        try:
            return self._plugins[type_name]
        except (KeyError, TypeError):
            raise UnknownBackendTypeError(f"unknown backend type: {type_name!r}") from None

    def types(self) -> tuple[str, ...]:
        return tuple(sorted(self._plugins))

    def describe(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "type": name,
                "schema_version": plugin.schema_version,
                "schema_validated": plugin.schema_version is not None,
            }
            for name, plugin in sorted(self._plugins.items())
        }


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
    "BackendConfigError",
    "BackendPlugin",
    "BackendRegistry",
    "BackendTypeRegistry",
    "LegacyBackendPlugin",
    "UnknownBackendTypeError",
    "ensure_json_compatible",
    "get_backend_type_registry",
    "redact_backend_config",
    "validate_backend_name",
]
