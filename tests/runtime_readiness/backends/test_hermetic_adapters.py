"""Core CI coverage for the hermetic backend conformance reference adapters."""

from __future__ import annotations

import asyncio

import pytest

from ipfs_kit_py.backends.filesystem_backend import (
    HERMITIC_REFERENCE_OPERATIONS,
    HermeticBackendError,
    HermeticFilesystemAdapter,
)
from ipfs_kit_py.backends.ipfs_backend import HermeticIPFSFixtureAdapter
from ipfs_kit_py.core.operation_contracts import ErrorCode, OperationState
from tests.runtime_readiness.backends.conformance import (
    BackendConformanceKit,
    CONFORMANCE_OPERATIONS,
)


def test_filesystem_reference_passes_common_conformance(tmp_path) -> None:
    adapter = HermeticFilesystemAdapter(tmp_path / "filesystem")

    report = asyncio.run(BackendConformanceKit().run(adapter))

    assert report.executed == CONFORMANCE_OPERATIONS
    assert report.skipped == ()
    assert report.final_effect_count >= 4


def test_hermetic_ipfs_fixture_passes_common_conformance(tmp_path) -> None:
    adapter = HermeticIPFSFixtureAdapter(tmp_path / "ipfs-fixture")

    report = asyncio.run(BackendConformanceKit().run(adapter))

    assert report.executed == CONFORMANCE_OPERATIONS
    assert adapter.provider_identity() == {
        "backend_id": "hermetic_ipfs_fixture",
        "provider_kind": "ipfs",
        "fixture_kind": "hermetic-ipfs-reference",
        "is_hermetic": True,
        "live_provider": False,
        "provider_certified": False,
        "certification_scope": "fixture-only; not live IPFS provider certification",
    }


def test_only_undeclared_operations_are_skipped_and_have_zero_effects(tmp_path) -> None:
    declared = set(HERMITIC_REFERENCE_OPERATIONS)
    declared.remove("stream")
    adapter = HermeticFilesystemAdapter(
        tmp_path / "partial", declared_operations=declared
    )

    report = asyncio.run(BackendConformanceKit().run(adapter))

    assert report.executed == tuple(operation for operation in CONFORMANCE_OPERATIONS if operation != "stream")
    assert report.skipped == ("stream",)


def test_configuration_rejects_secrets_without_retaining_them(tmp_path) -> None:
    secret = "do-not-echo-this"

    with pytest.raises(HermeticBackendError) as caught:
        HermeticFilesystemAdapter(tmp_path / "secret", configuration={"api_token": secret})

    assert caught.value.error.code == ErrorCode.SECRET_MATERIAL
    assert caught.value.error.state == OperationState.REJECTED
    assert secret not in str(caught.value)
    assert not (tmp_path / "secret").exists()
