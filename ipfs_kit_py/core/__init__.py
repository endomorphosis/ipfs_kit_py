"""Lazy core facade and just-in-time import helpers.

Nothing outside the standard library is imported while this module initializes.
The optional JIT registry is loaded only by an operation that needs it.
"""

from __future__ import annotations

from functools import wraps
from importlib import import_module
from time import monotonic
from typing import Any, Callable

from .. import OptionalDependencyError

_FEATURE_EXTRAS = {
    "mcp": "mcp",
    "mcp_server": "mcp",
    "graphrag": "graphrag",
    "transformers": "transformers",
    "ipfs_datasets": "ipfs_datasets",
    "ipfs_accelerate": "ipfs_accelerate",
}

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "OperationRegistryError": (".operation_registry", "OperationRegistryError"),
    "InvalidOperationDefinitionError": (
        ".operation_registry",
        "InvalidOperationDefinitionError",
    ),
    "DuplicateOperationIdentifierError": (
        ".operation_registry",
        "DuplicateOperationIdentifierError",
    ),
    "UnknownOperationError": (".operation_registry", "UnknownOperationError"),
    "UnsupportedOperationError": (".operation_registry", "UnsupportedOperationError"),
    "CapabilityTier": (".operation_registry", "CapabilityTier"),
    "AuthorizationClass": (".operation_registry", "AuthorizationClass"),
    "AuthorizationRequirement": (".operation_registry", "AuthorizationRequirement"),
    "OperationDefinition": (".operation_registry", "OperationDefinition"),
    "OperationSpec": (".operation_registry", "OperationSpec"),
    "OperationRegistry": (".operation_registry", "OperationRegistry"),
    "OperationRequest": (".operation_contracts", "OperationRequest"),
    "OperationResult": (".operation_contracts", "OperationResult"),
    "StorageError": (".operation_contracts", "StorageError"),
    "StateTransitionReceipt": (".operation_contracts", "StateTransitionReceipt"),
    "OperationState": (".operation_contracts", "OperationState"),
    "canonical_json": (".operation_contracts", "canonical_json"),
    "content_identity": (".operation_contracts", "content_identity"),
    "ServiceRouter": (".service_router", "ServiceRouter"),
    "DispatchContext": (".service_router", "DispatchContext"),
    "CanonicalStorageService": (".service_router", "CanonicalStorageService"),
    # Historical infrastructure exports remain compatible and lazy.
    "ToolRegistry": (".tool_registry", "ToolRegistry"),
    "ToolSchema": (".tool_registry", "ToolSchema"),
    "ToolCategory": (".tool_registry", "ToolCategory"),
    "ToolStatus": (".tool_registry", "ToolStatus"),
    "registry": (".tool_registry", "registry"),
    "tool": (".tool_registry", "tool"),
    "ServiceManager": (".service_manager", "ServiceManager"),
    "IPFSServiceManager": (".service_manager", "IPFSServiceManager"),
    "ServiceConfig": (".service_manager", "ServiceConfig"),
    "ServiceStatus": (".service_manager", "ServiceStatus"),
    "service_manager": (".service_manager", "service_manager"),
    "ipfs_manager": (".service_manager", "ipfs_manager"),
    "ErrorHandler": (".error_handler", "ErrorHandler"),
    "MCPError": (".error_handler", "MCPError"),
    "ErrorCode": (".error_handler", "ErrorCode"),
    "ErrorCategory": (".error_handler", "ErrorCategory"),
    "ErrorSeverity": (".error_handler", "ErrorSeverity"),
    "error_handler": (".error_handler", "error_handler"),
    "create_success_response": (".error_handler", "create_success_response"),
    "TestFramework": (".test_framework", "TestFramework"),
    "TestResult": (".test_framework", "TestResult"),
    "TestSuite": (".test_framework", "TestSuite"),
    "TestStatus": (".test_framework", "TestStatus"),
    "TestCategory": (".test_framework", "TestCategory"),
    "test_framework": (".test_framework", "test_framework"),
}


class CoreJITManager:
    """Deferred adapter for :mod:`ipfs_kit_py.jit_imports`."""

    def __init__(self) -> None:
        self._created_at = monotonic()
        self._jit_instance: Any = None
        self._jit_load_attempted = False
        self._cached_modules: dict[str, Any] = {}

    def _get_jit(self) -> Any:
        if self._jit_load_attempted:
            return self._jit_instance
        self._jit_load_attempted = True
        try:
            self._jit_instance = import_module("ipfs_kit_py.jit_imports").get_jit_imports()
        except Exception:
            self._jit_instance = None
        return self._jit_instance

    @property
    def is_available(self) -> bool:
        return self._get_jit() is not None

    @property
    def available_features(self) -> dict[str, bool]:
        jit = self._get_jit()
        if jit is None:
            return {}
        try:
            return {
                name: bool(status.get("available"))
                for name, status in jit.get_feature_status().items()
            }
        except Exception:
            return {}

    def check_feature(self, feature_name: str) -> bool:
        jit = self._get_jit()
        if jit is None:
            return False
        try:
            return bool(jit.is_available(feature_name))
        except Exception:
            return False

    def get_module(self, module_name: str, fallback: Any = None) -> Any:
        if module_name in self._cached_modules:
            return self._cached_modules[module_name]
        jit = self._get_jit()
        try:
            module = jit.import_module(module_name) if jit is not None else import_module(module_name)
        except (ImportError, AttributeError):
            return fallback
        if module is not None:
            self._cached_modules[module_name] = module
            return module
        return fallback

    def get_import_metrics(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "jit_available": self._jit_instance is not None,
            "jit_load_attempted": self._jit_load_attempted,
            "core_init_time": monotonic() - self._created_at,
            "cached_modules": len(self._cached_modules),
        }
        if self._jit_instance is not None:
            try:
                result["jit_metrics"] = self._jit_instance.get_metrics()
            except Exception:
                pass
        return result

    def preload_features(self, feature_names: list[str]) -> dict[str, bool]:
        return {feature_name: self.check_feature(feature_name) for feature_name in feature_names}

    def reset_cache(self) -> None:
        self._cached_modules.clear()
        if self._jit_instance is not None:
            try:
                self._jit_instance.clear_cache()
            except Exception:
                pass


jit_manager = CoreJITManager()


def _extra_for(feature_name: str) -> str:
    return _FEATURE_EXTRAS.get(feature_name, feature_name)


def require_feature(feature_name: str, error_message: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require a feature only when the wrapped function is called."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not jit_manager.check_feature(feature_name):
                if error_message:
                    raise OptionalDependencyError(error_message, extra=_extra_for(feature_name))
                raise OptionalDependencyError(feature_name, extra=_extra_for(feature_name))
            return func(*args, **kwargs)

        return wrapper

    return decorator


def optional_feature(feature_name: str, fallback_result: Any = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a declared fallback when an optional feature is unavailable."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs) if jit_manager.check_feature(feature_name) else fallback_result

        return wrapper

    return decorator


def core_lazy_import(module_name: str, feature_name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Ensure a module is importable at the point a decorated function runs."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if feature_name and not jit_manager.check_feature(feature_name):
                raise OptionalDependencyError(feature_name, extra=_extra_for(feature_name))
            if jit_manager.get_module(module_name) is None:
                raise OptionalDependencyError(module_name, extra=_extra_for(feature_name or module_name), dependency=module_name)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def jit_import(module_name: str, fallback: Any = None) -> Any:
    """Import a module through JIT when requested, with a normal import fallback."""

    return jit_manager.get_module(module_name, fallback)


def jit_import_from(module_name: str, attr_name: str, fallback: Any = None) -> Any:
    module = jit_import(module_name)
    return getattr(module, attr_name, fallback) if module is not None else fallback


def lazy_import(feature_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Compatibility decorator that validates its feature at call time."""

    return require_feature(feature_name)


def get_jit_imports() -> Any:
    """Return the single deferred JIT instance without recursive self-calls."""

    return jit_manager._get_jit()


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))


__all__ = [
    "CoreJITManager", "jit_manager", "require_feature", "optional_feature",
    "core_lazy_import", "jit_import", "jit_import_from", "lazy_import", "get_jit_imports",
    "OperationRegistryError", "InvalidOperationDefinitionError",
    "DuplicateOperationIdentifierError", "UnknownOperationError", "UnsupportedOperationError",
    "CapabilityTier", "AuthorizationClass", "AuthorizationRequirement", "OperationDefinition",
    "OperationSpec", "OperationRegistry", "OperationRequest", "OperationResult", "StorageError",
    "StateTransitionReceipt", "OperationState", "canonical_json", "content_identity",
    "ServiceRouter", "DispatchContext", "CanonicalStorageService",
]
