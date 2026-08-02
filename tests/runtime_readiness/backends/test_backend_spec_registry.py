"""Contract tests for the canonical backend inventory."""

from __future__ import annotations

import pytest

from ipfs_kit_py.backend_registry import (
    BackendRuntimeFactory,
    BackendRuntimeUnavailableError,
    BackendTypeRegistry,
    ExcludedBackendTypeError,
    UnknownBackendTypeError,
)
from ipfs_kit_py.backend_schemas import EXCLUDED_SCHEMAS, SCHEMAS, get_backend_schema
from ipfs_kit_py.backends.spec import (
    ACTIVE_BACKEND_SPECS,
    EXCLUDED_BACKEND_SPECS,
    BackendCapability,
    normalize_backend_type,
)


@pytest.fixture
def registry() -> BackendTypeRegistry:
    return BackendTypeRegistry(load_entry_points=False)


def test_registry_schemas_and_public_names_are_bijective(
    registry: BackendTypeRegistry,
) -> None:
    """One active inventory drives plugins, schemas, and public spellings."""

    assert set(registry.types()) == set(ACTIVE_BACKEND_SPECS) == set(SCHEMAS)
    assert set(EXCLUDED_SCHEMAS) == set(EXCLUDED_BACKEND_SPECS)

    descriptions = registry.describe(include_excluded=True)
    for type_name, spec in {**ACTIVE_BACKEND_SPECS, **EXCLUDED_BACKEND_SPECS}.items():
        description = descriptions[type_name]
        schema = get_backend_schema(type_name)
        assert schema is not None
        assert description["type"] == schema["type"] == type_name
        assert description["aliases"] == schema["aliases"] == list(spec.aliases)
        assert description["cli_names"] == schema["cli_names"] == list(spec.names)
        assert description["mcp_names"] == schema["mcp_names"] == list(spec.names)
        assert (
            description["documentation_names"]
            == schema["documentation_names"]
            == list(spec.names)
        )
        assert description["capabilities"] == schema["capabilities"] == sorted(
            capability.value for capability in spec.capabilities
        )
        assert description["support_tier"] == schema["support_tier"] == spec.support_tier.value
        assert description["support_tier_source"] == schema["support_tier_source"] == (
            "explicit-backend-spec"
        )
        for spelling in spec.names:
            assert normalize_backend_type(spelling) == type_name
            assert get_backend_schema(spelling) == schema
            if not spec.is_excluded:
                assert registry.get(spelling) is registry.get(type_name)


def test_ipfs_cluster_spellings_normalize_without_guessing(
    registry: BackendTypeRegistry,
) -> None:
    assert normalize_backend_type("ipfs_cluster") == "ipfs_cluster"
    assert normalize_backend_type("ipfs-cluster") == "ipfs_cluster"
    assert registry.get("ipfs-cluster").type_name == "ipfs_cluster"
    assert registry.get("ipfs_cluster").validate(
        {"name": "cluster_config", "type": "ipfs-cluster"}
    )["type"] == "ipfs_cluster"
    assert normalize_backend_type("IPFS_CLUSTER") is None
    with pytest.raises(UnknownBackendTypeError):
        registry.get("IPFS_CLUSTER")


def test_configuration_only_plugins_cannot_create_storage(
    registry: BackendTypeRegistry,
) -> None:
    plugin = registry.get("ipfs_cluster")

    assert not isinstance(plugin, BackendRuntimeFactory)
    assert plugin.capabilities({})["runtime_factory"] is False
    assert plugin.capabilities({})["storage"] is False
    with pytest.raises(BackendRuntimeUnavailableError):
        registry.get_runtime_factory("ipfs-cluster")
    with pytest.raises(BackendRuntimeUnavailableError):
        registry.create_filesystem("ipfs_cluster", {"name": "cluster_config"})


def test_iroh_is_the_declared_capability_gated_runtime_factory(
    registry: BackendTypeRegistry,
) -> None:
    spec = registry.spec("iroh")
    factory = registry.get_runtime_factory("iroh")

    assert spec.runtime_factory == "create_filesystem"
    assert spec.supports(BackendCapability.RUNTIME_FACTORY)
    assert spec.supports(BackendCapability.STORAGE)
    assert isinstance(factory, BackendRuntimeFactory)
    assert factory is registry.get("iroh")


@pytest.mark.parametrize("type_name", ("arrow", "lotus", "saturn", "synapse"))
def test_unintegrated_surfaces_are_explicitly_excluded(
    registry: BackendTypeRegistry, type_name: str
) -> None:
    spec = registry.spec(type_name)
    schema = get_backend_schema(type_name)

    assert spec.is_excluded
    assert not spec.capabilities
    assert schema is not None
    assert schema["available"] is False
    assert schema["excluded_reason"] == spec.excluded_reason
    with pytest.raises(ExcludedBackendTypeError):
        registry.get(type_name)
    with pytest.raises(ExcludedBackendTypeError):
        registry.get_runtime_factory(type_name)
