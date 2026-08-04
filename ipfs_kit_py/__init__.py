"""The lightweight public facade for :mod:`ipfs_kit_py`.

Importing the package is deliberately inert: it neither configures services nor
loads installer, network, model, or optional dependency stacks.  Public
capabilities are resolved on first attribute access instead.
"""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Any

_SOURCE_VERSION = "0.3.0"


def _runtime_version() -> str:
    """Return installed wheel metadata when it belongs to this package copy."""

    try:
        package_root = Path(__file__).resolve().parent
        package_distribution = distribution("ipfs_kit_py")
        distribution_root = Path(package_distribution.locate_file("")).resolve()
        if package_root.is_relative_to(distribution_root):
            return package_distribution.version
    except (PackageNotFoundError, OSError, ValueError):
        pass
    return _SOURCE_VERSION


__version__ = _runtime_version()
__author__ = "Benjamin Barber"
__email__ = "starworks5@gmail.com"


class OptionalDependencyError(ImportError):
    """An optional feature was requested without its declared dependency."""

    def __init__(self, feature: str, *, extra: str, dependency: str | None = None):
        self.feature = feature
        self.extra = extra
        self.dependency = dependency
        missing = f" optional dependency {dependency!r}" if dependency else " an optional dependency"
        super().__init__(
            f"{feature} requires{missing}. Install it with: "
            f"python -m pip install 'ipfs_kit_py[{extra}]'"
        )


_LAZY_EXPORTS: dict[str, tuple[str, str, str | None]] = {
    # Stable operation and service contracts.
    "OperationDefinition": (".core.operation_registry", "OperationDefinition", None),
    "OperationSpec": (".core.operation_registry", "OperationSpec", None),
    "OperationRegistry": (".core.operation_registry", "OperationRegistry", None),
    "AuthorizationRequirement": (".core.operation_registry", "AuthorizationRequirement", None),
    "AuthorizationClass": (".core.operation_registry", "AuthorizationClass", None),
    "CapabilityTier": (".core.operation_registry", "CapabilityTier", None),
    "OperationRequest": (".core.operation_contracts", "OperationRequest", None),
    "OperationResult": (".core.operation_contracts", "OperationResult", None),
    "StorageError": (".core.operation_contracts", "StorageError", None),
    "StateTransitionReceipt": (".core.operation_contracts", "StateTransitionReceipt", None),
    "OperationState": (".core.operation_contracts", "OperationState", None),
    "canonical_json": (".core.operation_contracts", "canonical_json", None),
    "content_identity": (".core.operation_contracts", "content_identity", None),
    "ServiceRouter": (".core.service_router", "ServiceRouter", None),
    "DispatchContext": (".core.service_router", "DispatchContext", None),
    "CanonicalStorageService": (".core.service_router", "CanonicalStorageService", None),
    # JIT helpers are lazy too, so package import never initializes JIT.
    "jit_manager": (".core", "jit_manager", None),
    "require_feature": (".core", "require_feature", None),
    "optional_feature": (".core", "optional_feature", None),
    "core_lazy_import": (".core", "core_lazy_import", None),
    "jit_import": (".core", "jit_import", None),
    "jit_import_from": (".core", "jit_import_from", None),
    "lazy_import": (".core", "lazy_import", None),
    "get_jit_imports": (".core", "get_jit_imports", None),
    # GraphRAG is optional, including its numerical and vector dependencies.
    "IPLDGraphDB": (".ipld_knowledge_graph", "IPLDGraphDB", "graphrag"),
    "GraphRAG": (".ipld_knowledge_graph", "GraphRAG", "graphrag"),
    # Retain the common high-level entry point without paying its import cost.
    "IPFSSimpleAPI": (".high_level_api", "IPFSSimpleAPI", None),
}

_OPTIONAL_MODULES = {
    "ipfs_datasets_py": ("ipfs_datasets_py", "ipfs_datasets"),
    "ipfs_accelerate_py": ("ipfs_accelerate_py", "ipfs_accelerate"),
    "ipfs_transformers_py": ("ipfs_transformers_py", "transformers"),
}


def _optional_module(module_name: str, extra: str) -> Any:
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        raise OptionalDependencyError(module_name, extra=extra, dependency=exc.name) from exc


def get_ipfs_datasets(*, deps: object | None = None, module_override: Any = None) -> Any:
    """Return ``ipfs_datasets_py`` only when the integration is used."""

    return module_override if module_override is not None else _optional_module("ipfs_datasets_py", "ipfs_datasets")


def get_ipfs_accelerate(*, deps: object | None = None, module_override: Any = None) -> Any:
    """Return ``ipfs_accelerate_py`` only when the integration is used."""

    return module_override if module_override is not None else _optional_module("ipfs_accelerate_py", "ipfs_accelerate")


def get_ipfs_transformers(*, deps: object | None = None, module_override: Any = None) -> Any:
    """Return ``ipfs_transformers_py`` only when the integration is used."""

    return module_override if module_override is not None else _optional_module("ipfs_transformers_py", "transformers")


def __getattr__(name: str) -> Any:
    """Resolve a public API or compatibility submodule only on explicit use."""

    if name in _OPTIONAL_MODULES:
        module_name, extra = _OPTIONAL_MODULES[name]
        value = _optional_module(module_name, extra)
    elif name in _LAZY_EXPORTS:
        module_name, attribute, extra = _LAZY_EXPORTS[name]
        try:
            value = getattr(import_module(module_name, __name__), attribute)
        except ModuleNotFoundError as exc:
            if extra:
                raise OptionalDependencyError(name, extra=extra, dependency=exc.name) from exc
            raise
    else:
        # Existing users may import first-party submodules from the package
        # root.  Preserve that explicit-use compatibility without importing
        # every module during package initialization.
        try:
            value = import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"{__name__}.{name}":
                raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
            raise
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS) | set(_OPTIONAL_MODULES))


__all__ = [
    "__version__",
    "OptionalDependencyError",
    "OperationDefinition",
    "OperationSpec",
    "OperationRegistry",
    "AuthorizationRequirement",
    "AuthorizationClass",
    "CapabilityTier",
    "OperationRequest",
    "OperationResult",
    "StorageError",
    "StateTransitionReceipt",
    "OperationState",
    "canonical_json",
    "content_identity",
    "ServiceRouter",
    "DispatchContext",
    "CanonicalStorageService",
]
