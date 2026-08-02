"""Contract coverage for fail-closed external-provider classifications."""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ipfs_kit_py.backends.provider_adapters import (
    CanonicalAdapterMissingError,
    CanonicalRuntimeFactory,
    ConfigurationOnlyProviderError,
    ProviderAdapterCatalog,
    ProviderAdapterError,
    ProviderAvailability,
    ProviderOperation,
    ProviderOperationSemantics,
    ProviderReceipt,
    ProviderReceiptError,
    ProviderReceiptRequiredError,
    ProviderRequestGate,
    UnsupportedProviderError,
)
from ipfs_kit_py.backends.spec import BACKEND_SPECS, BackendSupportTier
from ipfs_kit_py.core.operation_contracts import ErrorCode, OperationState


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


def _receipt(*, provider_type: str = "iroh", expiry: str = "2026-08-03T12:00:00Z") -> dict[str, object]:
    return {
        "schema": "ipfs-kit-provider-receipt/v1",
        "receipt_id": "iroh-receipt-20260802",
        "provider_type": provider_type,
        "issued_at": "2026-08-02T11:00:00Z",
        "expires_at": expiry,
        "runtime_factory": "create_filesystem",
        "tested_operations": [operation.value for operation in ProviderOperation],
        "rate_limit": {"max_requests": 2, "window_seconds": 60},
        "timeout_seconds": 10,
        "retry": {"max_attempts": 2, "retryable_codes": ["E_UNAVAILABLE", "E_BACKPRESSURE"]},
        "idempotency": {"required_for_mutations": True},
        "consistency": {"model": "read-your-writes", "verified": True},
    }


def test_every_inventoried_type_has_a_typed_non_implicit_outcome() -> None:
    inventory = ProviderAdapterCatalog(now=NOW).inventory()

    assert set(inventory) == set(BACKEND_SPECS)
    for type_name, spec in BACKEND_SPECS.items():
        adapter = inventory[type_name]
        if spec.is_excluded or spec.support_tier == BackendSupportTier.UNSUPPORTED:
            assert adapter.availability is ProviderAvailability.UNSUPPORTED
            with pytest.raises(UnsupportedProviderError) as exc_info:
                adapter.require_storage("get")
            assert exc_info.value.error.code is ErrorCode.UNSUPPORTED
            assert exc_info.value.error.state is OperationState.UNSUPPORTED
        elif spec.type_name == "iroh":
            assert adapter.availability is ProviderAvailability.RECEIPT_REQUIRED
            with pytest.raises(ProviderReceiptRequiredError) as exc_info:
                adapter.require_storage("get")
            assert exc_info.value.error.code is ErrorCode.CAPABILITY_MISSING
        else:
            assert adapter.availability is ProviderAvailability.CONFIGURATION_ONLY
            assert not adapter.supports_storage
            with pytest.raises(ConfigurationOnlyProviderError) as exc_info:
                adapter.require_storage("get")
            assert exc_info.value.error.code is ErrorCode.UNSUPPORTED


def test_registry_only_estuary_never_advertises_storage_even_with_a_receipt() -> None:
    # A matching provider receipt cannot override the registry's declared capability.
    receipt = _receipt(provider_type="iroh")
    catalog = ProviderAdapterCatalog(receipts={"iroh": receipt}, now=NOW)
    estuary = catalog.resolve("estuary", configuration={"token_ref": "secretref:environment:estuary"})

    assert estuary.availability is ProviderAvailability.CONFIGURATION_ONLY
    assert estuary.status().supports_storage is False
    with pytest.raises(ConfigurationOnlyProviderError):
        estuary.require_storage("put", idempotency_key="write-1")


def test_only_authorized_references_are_accepted_and_never_retained() -> None:
    raw_credential = "raw-credential-that-must-not-appear"
    with pytest.raises(ProviderAdapterError) as exc_info:
        ProviderAdapterCatalog().resolve("s3", configuration={"access_key": raw_credential})

    assert exc_info.value.error.code is ErrorCode.SECRET_MATERIAL
    assert raw_credential not in str(exc_info.value)
    assert raw_credential not in repr(exc_info.value)

    adapter = ProviderAdapterCatalog().resolve(
        "s3",
        configuration={
            "endpoint": "https://storage.example.invalid",
            "credentials": {
                "access_key_ref": "secretref:secure-config:s3-access",
                "secret_key_ref": "secretref:credential-manager:s3-secret",
            },
        },
    )
    assert adapter.configuration.credential_fields == ("access_key", "secret_key")
    assert adapter.configuration.as_runtime_values() == {
        "endpoint": "https://storage.example.invalid"
    }
    assert "secretref:" not in repr(adapter.configuration)


def test_request_semantics_enforce_timeout_retry_idempotency_and_rate_limit() -> None:
    clock = [0.0]
    gate = ProviderRequestGate(
        ProviderOperationSemantics(
            timeout_seconds=5,
            max_retries=1,
            rate_limit_requests=2,
            rate_limit_window_seconds=10,
        ),
        clock=lambda: clock[0],
    )
    with pytest.raises(ProviderAdapterError) as exc_info:
        gate.prepare("put")
    assert exc_info.value.error.code is ErrorCode.PRECONDITION_FAILED

    first = gate.prepare("put", idempotency_key="write-1")
    assert first.idempotency_key_present is True
    gate.prepare("get", retry_attempt=1)
    with pytest.raises(ProviderAdapterError) as exc_info:
        gate.prepare("get")
    assert exc_info.value.error.code is ErrorCode.BACKPRESSURE
    clock[0] = 11.0
    gate.prepare("get")

    with pytest.raises(ProviderAdapterError) as exc_info:
        gate.prepare("get", timeout_seconds=6)
    assert exc_info.value.error.code is ErrorCode.DEADLINE_EXCEEDED
    with pytest.raises(ProviderAdapterError) as exc_info:
        gate.prepare("get", retry_attempt=2)
    assert exc_info.value.error.code is ErrorCode.UNAVAILABLE


def test_current_receipt_and_explicit_canonical_factory_are_both_required() -> None:
    receipt = _receipt()
    receipt_only = ProviderAdapterCatalog(receipts={"iroh": receipt}, now=NOW).resolve("iroh")
    assert receipt_only.availability is ProviderAvailability.CANONICAL_ADAPTER_MISSING
    with pytest.raises(CanonicalAdapterMissingError):
        receipt_only.require_storage("get")

    class CanonicalRuntime:
        is_canonical_provider_adapter = True
        provider_type = "iroh"

    factory = CanonicalRuntimeFactory(
        provider_type="iroh",
        adapter_id="iroh-repository-adapter",
        create=lambda request: CanonicalRuntime(),
    )
    ready = ProviderAdapterCatalog(
        receipts={"iroh": receipt}, runtime_factories={"iroh": factory}, now=NOW
    ).resolve("iroh", configuration={"token_ref": "credential://iroh/runtime-token"})
    assert ready.availability is ProviderAvailability.RUNTIME_READY
    runtime = ready.create_runtime()
    assert isinstance(runtime, CanonicalRuntime)
    assert ready.status().receipt_id == "iroh-receipt-20260802"


def test_standalone_or_fixture_like_runtime_is_not_promoted_as_canonical() -> None:
    factory = CanonicalRuntimeFactory(
        provider_type="iroh",
        adapter_id="iroh-repository-adapter",
        create=lambda request: object(),
    )
    adapter = ProviderAdapterCatalog(
        receipts={"iroh": _receipt()}, runtime_factories={"iroh": factory}, now=NOW
    ).resolve("iroh")

    with pytest.raises(CanonicalAdapterMissingError) as exc_info:
        adapter.create_runtime()
    assert exc_info.value.error.code is ErrorCode.CAPABILITY_MISSING


def test_receipts_are_current_credential_free_evidence() -> None:
    expired = _receipt(expiry="2026-08-02T11:59:59Z")
    with pytest.raises(ProviderReceiptError):
        ProviderReceipt.from_mapping(expired, now=NOW)

    credential_bearing = _receipt()
    credential_bearing["token"] = "must-not-be-recorded"
    with pytest.raises(ProviderReceiptError) as exc_info:
        ProviderReceipt.from_mapping(credential_bearing, now=NOW)
    assert "must-not-be-recorded" not in str(exc_info.value)


def test_receipt_authority_is_explicitly_empty_and_adapter_does_not_import_clients() -> None:
    receipt_dir = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "runtime_readiness"
        / "backend_external_receipts"
    )
    assert json.loads((receipt_dir / "index.json").read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "receipts": [],
    }
    import ipfs_kit_py.backends.provider_adapters as adapters

    source = inspect.getsource(adapters)
    assert "HermeticFilesystemAdapter" not in source
    assert "HermeticIPFSFixtureAdapter" not in source
    assert "import mcp" not in source.lower()
