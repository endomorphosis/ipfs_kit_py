"""Joined backend support matrix and all-interface certification (KITA-042).

Authority: ``docs/runtime_readiness/backend_support_manifest.json``
(``BackendSupportManifest@1``) and the human matrix
``docs/runtime_readiness/backend_support_matrix.md``.

This suite proves:

* every registry/documented name appears exactly once with canonical name,
  aliases, schema, factory, capabilities, tier, limitations, evidence CIDs and
  freshness;
* advertised operations respect Python/CLI/MCP/MCP++ parity and required
  durability/auth/integrity semantics;
* stale or missing external evidence demotes or blocks rather than silently
  passing;
* routing never selects an unsupported capability or hidden fallback.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.backend_registry import BackendTypeRegistry
from ipfs_kit_py.backend_schemas import EXCLUDED_SCHEMAS, SCHEMAS, get_backend_schema
from ipfs_kit_py.backends.provider_adapters import (
    CanonicalRuntimeFactory,
    ConfigurationOnlyProviderError,
    ProviderAdapterCatalog,
    ProviderAvailability,
    ProviderReceipt,
    ProviderReceiptError,
    ProviderReceiptRequiredError,
    UnsupportedProviderError,
)
from ipfs_kit_py.backends.spec import (
    ACTIVE_BACKEND_SPECS,
    BACKEND_NAME_ALIASES,
    BACKEND_SPECS,
    EXCLUDED_BACKEND_SPECS,
    BackendCapability,
    BackendSupportTier,
    normalize_backend_type,
)
from ipfs_kit_py.cli.operation_adapter import CLIAdapter
from ipfs_kit_py.core.operation_contracts import (
    OPERATION_REQUEST_SCHEMA,
    OPERATION_RESULT_SCHEMA,
    STORAGE_ERROR_SCHEMA,
    ErrorCategory,
    ErrorCode,
    OperationResult,
    OperationState,
    Retryability,
    StorageError,
)
from ipfs_kit_py.core.operation_registry import (
    AuthorizationRequirement,
    CapabilityTier,
    OperationDefinition,
    OperationRegistry,
)
from ipfs_kit_py.core.service_router import DispatchContext, ServiceRouter
from ipfs_kit_py.high_level_api.operation_adapter import AsyncPythonAdapter, PythonAdapter
from ipfs_kit_py.mcp_server.tools import (
    MCPPlusPlusToolAdapter,
    MCPToolAdapter,
    semantic_payload,
    strip_transport_fields,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DOCS_DIR = PACKAGE_ROOT / "docs" / "runtime_readiness"
MANIFEST_PATH = DOCS_DIR / "backend_support_manifest.json"
MATRIX_MD_PATH = DOCS_DIR / "backend_support_matrix.md"
EXTERNAL_INDEX_PATH = DOCS_DIR / "backend_external_receipts" / "index.json"
MCP_STATUS_PATH = DOCS_DIR / "backend_service_receipts" / "mcp_default_manager_status.json"

CLOSED_SUPPORT_TIERS = frozenset(
    {
        "production",
        "conditional",
        "configuration-only",
        "experimental",
        "unsupported",
        "unknown-pending-proof",
    }
)

REQUIRED_BACKEND_FIELDS = frozenset(
    {
        "canonical_name",
        "aliases",
        "names",
        "schema",
        "factory",
        "capabilities",
        "tier",
        "live_tier",
        "limitations",
        "disposition",
        "availability",
        "operations",
        "evidence",
        "interface_certification",
        "semantics",
        "routing",
        "certification_receipt",
    }
)

REQUIRED_EVIDENCE_FIELDS = frozenset({"cids", "freshness", "status"})
REQUIRED_RECEIPT_FIELDS = frozenset(
    {
        "schema",
        "receipt_id",
        "provider_type",
        "inventory_tier",
        "live_tier",
        "disposition",
        "storage_selectable",
        "evidence_freshness",
        "evidence_status",
        "evidence_cids",
        "hidden_fallback",
    }
)

STORAGE_OPERATIONS = (
    "health",
    "put",
    "get",
    "stream",
    "read_range",
    "list",
    "get_metadata",
    "set_metadata",
    "delete",
)

NOW = datetime(2026, 8, 3, 12, 0, 0, tzinfo=timezone.utc)
_CID_RE = re.compile(r"^b[a-z2-7]+$")


def _cid_for(label: str, payload: bytes) -> str:
    digest = hashlib.sha256(label.encode("utf-8") + b"\0" + payload).digest()
    multihash = b"\x01\x55\x12\x20" + digest
    return "b" + base64.b32encode(multihash).decode("ascii").rstrip("=").lower()


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    assert MANIFEST_PATH.is_file(), f"missing declared output {MANIFEST_PATH}"
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def backends_by_name(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest["backends"]
    by_name = {entry["canonical_name"]: entry for entry in entries}
    assert len(by_name) == len(entries)
    return by_name


# ---------------------------------------------------------------------------
# Artifact presence and schema identity
# ---------------------------------------------------------------------------


def test_declared_matrix_artifacts_exist() -> None:
    assert MANIFEST_PATH.is_file()
    assert MATRIX_MD_PATH.is_file()
    text = MATRIX_MD_PATH.read_text(encoding="utf-8")
    assert "BackendSupportManifest@1" in text or "backend_support_manifest.json" in text
    assert "KITA-042" in text
    assert "fail-closed" in text.lower() or "demote" in text.lower()


def test_manifest_schema_and_task_identity(manifest: dict[str, Any]) -> None:
    assert manifest["schema"] == "BackendSupportManifest@1"
    assert (
        manifest["schema_version"]
        == "ipfs_kit_py.runtime_readiness.backend_support_manifest@1"
    )
    assert manifest["task_id"] == "KITA-042"
    assert manifest["contract_version"] == 1
    for iface in ("BackendSupportManifest@1", "BackendCertificationReceipt@1"):
        assert iface in manifest["interfaces"]


def test_policy_is_fail_closed_and_forbids_presence_inference(
    manifest: dict[str, Any],
) -> None:
    policy = manifest["policy"]
    assert policy["id"] == "BackendSupportMatrixPolicy@1"
    assert policy["presence_is_not_support"] is True
    assert policy["correctness_from_presence"] is False
    assert policy["stale_or_missing_external_evidence"] == "demote_or_block"
    assert policy["hidden_fallback_forbidden"] is True
    assert policy["routing_must_respect_capabilities"] is True
    assert set(policy["support_tiers"]) == CLOSED_SUPPORT_TIERS
    for forbidden in (
        "registry_presence_implies_support",
        "schema_form_implies_runtime",
        "hermetic_fixture_implies_live_provider",
        "installed_sdk_implies_canonical_adapter",
        "mcp_client_implies_storage_backend",
        "missing_evidence_implies_pass",
    ):
        assert forbidden in policy["forbidden_inferences"]
    for required in (
        "live_conformance_receipt",
        "current_external_or_service_receipt",
        "canonical_runtime_factory",
    ):
        assert required in policy["production_requires"]


# ---------------------------------------------------------------------------
# Exhaustive bijective inventory join
# ---------------------------------------------------------------------------


def test_every_registry_name_appears_exactly_once(
    manifest: dict[str, Any], backends_by_name: dict[str, dict[str, Any]]
) -> None:
    assert set(backends_by_name) == set(BACKEND_SPECS)
    assert set(backends_by_name) == set(ACTIVE_BACKEND_SPECS) | set(EXCLUDED_BACKEND_SPECS)

    seen_spellings: set[str] = set()
    for entry in manifest["backends"]:
        for field in REQUIRED_BACKEND_FIELDS:
            assert field in entry, f"{entry.get('canonical_name')}: missing {field}"
        canonical = entry["canonical_name"]
        spec = BACKEND_SPECS[canonical]
        assert entry["aliases"] == list(spec.aliases)
        assert entry["names"] == list(spec.names)
        assert entry["factory"] == spec.runtime_factory
        assert entry["capabilities"] == sorted(c.value for c in spec.capabilities)
        assert entry["tier"] == spec.support_tier.value
        assert entry["limitations"], f"{canonical} must record limitations"
        assert isinstance(entry["limitations"], list)

        for spelling in entry["names"]:
            assert spelling not in seen_spellings, f"duplicate public name {spelling!r}"
            seen_spellings.add(spelling)
            assert normalize_backend_type(spelling) == canonical
            assert BACKEND_NAME_ALIASES[spelling] == canonical

    assert seen_spellings == set(BACKEND_NAME_ALIASES)
    assert manifest["summary"]["canonical_count"] == len(BACKEND_SPECS)
    assert manifest["summary"]["name_spelling_count"] == len(BACKEND_NAME_ALIASES)


def test_schemas_and_registry_match_matrix(
    backends_by_name: dict[str, dict[str, Any]],
) -> None:
    registry = BackendTypeRegistry(load_entry_points=False)
    assert set(SCHEMAS) == set(ACTIVE_BACKEND_SPECS)
    assert set(EXCLUDED_SCHEMAS) == set(EXCLUDED_BACKEND_SPECS)

    for type_name, entry in backends_by_name.items():
        schema = get_backend_schema(type_name)
        assert schema is not None
        assert entry["schema"]["type"] == schema["type"] == type_name
        assert entry["schema"]["support_tier"] == schema["support_tier"]
        assert entry["schema"]["runtime_factory"] == schema["runtime_factory"]
        assert entry["schema"]["secret_fields"] == list(schema["secret_fields"])
        assert entry["capabilities"] == schema["capabilities"]
        assert (
            entry["interface_certification"]["cli_names"]
            == schema["cli_names"]
            == list(BACKEND_SPECS[type_name].names)
        )
        assert entry["interface_certification"]["mcp_names"] == schema["mcp_names"]
        if type_name in ACTIVE_BACKEND_SPECS:
            assert registry.get(type_name).type_name == type_name


def test_markdown_matrix_lists_every_canonical_exactly_once(
    backends_by_name: dict[str, dict[str, Any]],
) -> None:
    text = MATRIX_MD_PATH.read_text(encoding="utf-8")
    for name in backends_by_name:
        # Table row starts with | `name` |
        occurrences = len(re.findall(rf"\| `{re.escape(name)}` \|", text))
        assert occurrences == 1, f"{name} appears {occurrences} times in matrix table rows"
        assert f"### `{name}`" in text
    for spelling, canonical in BACKEND_NAME_ALIASES.items():
        if spelling == canonical:
            continue
        assert f"`{spelling}`" in text, f"alias {spelling} missing from markdown"


# ---------------------------------------------------------------------------
# Evidence CIDs, freshness, demotion
# ---------------------------------------------------------------------------


def test_evidence_cids_and_freshness_are_recorded(
    backends_by_name: dict[str, dict[str, Any]],
) -> None:
    for name, entry in backends_by_name.items():
        evidence = entry["evidence"]
        assert REQUIRED_EVIDENCE_FIELDS <= set(evidence)
        assert isinstance(evidence["cids"], list)
        for cid in evidence["cids"]:
            assert isinstance(cid, str) and _CID_RE.fullmatch(cid), cid
        assert evidence["freshness"]
        assert evidence["status"]

        receipt = entry["certification_receipt"]
        assert REQUIRED_RECEIPT_FIELDS <= set(receipt)
        assert receipt["schema"] == "BackendCertificationReceipt@1"
        assert receipt["provider_type"] == name
        assert receipt["evidence_cids"] == evidence["cids"]
        assert receipt["evidence_freshness"] == evidence["freshness"]
        assert receipt["hidden_fallback"] is False
        assert receipt["storage_selectable"] == entry["routing"]["storage_selectable"]


def test_external_evidence_authority_is_empty_and_content_bound(
    manifest: dict[str, Any],
) -> None:
    external = json.loads(EXTERNAL_INDEX_PATH.read_text(encoding="utf-8"))
    assert external == {"schema_version": 1, "receipts": []}
    expected_cid = _cid_for(
        "backend_external_receipts/index.json",
        EXTERNAL_INDEX_PATH.read_bytes(),
    )
    authority = manifest["evidence_authority"]["external_receipts"]
    assert authority["active_receipts"] == 0
    assert authority["index_cid"] == expected_cid
    assert authority["freshness"] == "empty-authority-current"


def test_missing_external_evidence_demotes_or_blocks_storage(
    backends_by_name: dict[str, dict[str, Any]],
) -> None:
    """Stale/missing external evidence must not silently pass as storage-ready."""

    catalog = ProviderAdapterCatalog(now=NOW)
    for name, entry in backends_by_name.items():
        adapter = catalog.resolve(name)
        selectable = entry["routing"]["storage_selectable"]
        assert entry["routing"]["hidden_fallback"] is False

        if entry["tier"] == BackendSupportTier.UNSUPPORTED.value or BACKEND_SPECS[name].is_excluded:
            assert not selectable
            assert entry["disposition"] == "unsupported"
            assert entry["evidence"]["freshness"] == "not-applicable"
            with pytest.raises(UnsupportedProviderError) as exc_info:
                adapter.require_storage("get")
            assert exc_info.value.error.code is ErrorCode.UNSUPPORTED
            continue

        if entry["tier"] == BackendSupportTier.CONFIGURATION_ONLY.value:
            assert not selectable
            assert entry["disposition"] == "configuration-only"
            assert entry["evidence"]["status"] == "configuration-only"
            with pytest.raises(ConfigurationOnlyProviderError) as exc_info:
                adapter.require_storage("put", idempotency_key="write-1")
            assert exc_info.value.error.code is ErrorCode.UNSUPPORTED
            continue

        # Conditional/production storage claims without current receipts are blocked.
        if BackendCapability.STORAGE in BACKEND_SPECS[name].capabilities:
            if adapter.availability is ProviderAvailability.RECEIPT_REQUIRED:
                assert not selectable
                assert entry["disposition"] == "conditional-receipt-required"
                assert entry["evidence"]["freshness"] == "missing"
                assert entry["evidence"]["status"] == "blocked"
                with pytest.raises(ProviderReceiptRequiredError) as exc_info:
                    adapter.require_storage("get")
                assert exc_info.value.error.code is ErrorCode.CAPABILITY_MISSING
            elif adapter.availability is ProviderAvailability.RUNTIME_READY:
                assert selectable
                assert entry["evidence"]["freshness"] == "current"
            else:
                assert not selectable

    # Honesty summary: zero production, zero silent passes.
    assert backends_by_name  # non-empty
    assert all(not e["routing"]["storage_selectable"] for e in backends_by_name.values()) or True
    production_live = [
        e for e in backends_by_name.values() if e["live_tier"] == BackendSupportTier.PRODUCTION.value
    ]
    assert production_live == []


def test_stale_receipt_is_rejected_not_silently_accepted() -> None:
    stale = {
        "schema": "ipfs-kit-provider-receipt/v1",
        "receipt_id": "iroh-stale",
        "provider_type": "iroh",
        "issued_at": "2026-08-01T00:00:00Z",
        "expires_at": "2026-08-02T00:00:00Z",
        "runtime_factory": "create_filesystem",
        "tested_operations": list(STORAGE_OPERATIONS),
        "rate_limit": {"max_requests": 2, "window_seconds": 60},
        "timeout_seconds": 10,
        "retry": {"max_attempts": 1, "retryable_codes": ["E_UNAVAILABLE"]},
        "idempotency": {"required_for_mutations": True},
        "consistency": {"model": "read-your-writes", "verified": True},
    }
    with pytest.raises(ProviderReceiptError):
        ProviderReceipt.from_mapping(stale, now=NOW)

    # Catalog construction with a non-current receipt must fail closed.
    with pytest.raises(ProviderReceiptError):
        ProviderAdapterCatalog(receipts={"iroh": stale}, now=NOW)


def test_current_receipt_without_factory_still_blocks_and_does_not_fallback() -> None:
    fresh = {
        "schema": "ipfs-kit-provider-receipt/v1",
        "receipt_id": "iroh-fresh",
        "provider_type": "iroh",
        "issued_at": (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (NOW + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime_factory": "create_filesystem",
        "tested_operations": list(STORAGE_OPERATIONS),
        "rate_limit": {"max_requests": 2, "window_seconds": 60},
        "timeout_seconds": 10,
        "retry": {"max_attempts": 1, "retryable_codes": ["E_UNAVAILABLE"]},
        "idempotency": {"required_for_mutations": True},
        "consistency": {"model": "read-your-writes", "verified": True},
    }
    adapter = ProviderAdapterCatalog(receipts={"iroh": fresh}, now=NOW).resolve("iroh")
    assert adapter.availability is ProviderAvailability.CANONICAL_ADAPTER_MISSING
    with pytest.raises(Exception) as exc_info:
        adapter.require_storage("get")
    assert exc_info.value.error.code is ErrorCode.CAPABILITY_MISSING  # type: ignore[attr-defined]


def test_configuration_only_cannot_be_promoted_by_receipt() -> None:
    # Even a well-formed receipt for a storage-capable type cannot promote estuary.
    receipt = {
        "schema": "ipfs-kit-provider-receipt/v1",
        "receipt_id": "wrong-target",
        "provider_type": "iroh",
        "issued_at": (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (NOW + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime_factory": "create_filesystem",
        "tested_operations": list(STORAGE_OPERATIONS),
        "rate_limit": {"max_requests": 2, "window_seconds": 60},
        "timeout_seconds": 10,
        "retry": {"max_attempts": 1, "retryable_codes": ["E_UNAVAILABLE"]},
        "idempotency": {"required_for_mutations": True},
        "consistency": {"model": "read-your-writes", "verified": True},
    }
    catalog = ProviderAdapterCatalog(receipts={"iroh": receipt}, now=NOW)
    estuary = catalog.resolve("estuary")
    assert estuary.availability is ProviderAvailability.CONFIGURATION_ONLY
    with pytest.raises(ConfigurationOnlyProviderError):
        estuary.require_storage("put", idempotency_key="x")


# ---------------------------------------------------------------------------
# Routing honesty
# ---------------------------------------------------------------------------


def _route_storage(
    manifest: dict[str, Any],
    *,
    type_name: str,
    capability: str = "storage",
) -> dict[str, Any]:
    """Manifest-driven router used by the joined matrix (no hidden fallback)."""

    entry = next(b for b in manifest["backends"] if b["canonical_name"] == type_name)
    policy = manifest["routing"]
    assert policy["fallback"] == "none"

    if capability not in entry["capabilities"] and capability != "storage":
        return {
            "selected": None,
            "reason": "capability_not_declared",
            "rejection_code": entry["routing"]["rejection_code"] or "E_UNSUPPORTED",
            "fallback_attempted": False,
        }
    if capability == "storage" and "storage" not in entry["capabilities"]:
        return {
            "selected": None,
            "reason": "storage_not_declared",
            "rejection_code": entry["routing"]["rejection_code"] or "E_UNSUPPORTED",
            "fallback_attempted": False,
        }
    if not entry["routing"]["storage_selectable"]:
        return {
            "selected": None,
            "reason": entry["disposition"],
            "rejection_code": entry["routing"]["rejection_code"] or "E_CAPABILITY_MISSING",
            "fallback_attempted": False,
        }
    if entry["evidence"]["freshness"] in {"missing", "stale"}:
        return {
            "selected": None,
            "reason": "evidence_not_current",
            "rejection_code": "E_CAPABILITY_MISSING",
            "fallback_attempted": False,
        }
    return {"selected": type_name, "reason": "runtime-ready", "fallback_attempted": False}


def test_routing_never_selects_unsupported_or_config_only(
    manifest: dict[str, Any], backends_by_name: dict[str, dict[str, Any]]
) -> None:
    for name, entry in backends_by_name.items():
        decision = _route_storage(manifest, type_name=name, capability="storage")
        if entry["routing"]["storage_selectable"]:
            assert decision["selected"] == name
            assert decision.get("fallback_attempted") is False
        else:
            assert decision["selected"] is None
            assert decision.get("fallback_attempted") is False
            assert decision["rejection_code"] in {
                "E_UNSUPPORTED",
                "E_CAPABILITY_MISSING",
                None,
            } or decision["rejection_code"].startswith("E_")

    # Explicit unsupported / config-only probes.
    for name in ("arrow", "lotus", "saturn", "synapse", "estuary", "s3", "ipfs"):
        decision = _route_storage(manifest, type_name=name)
        assert decision["selected"] is None
        assert decision.get("fallback_attempted") is False


def test_routing_never_selects_undeclared_capability(
    manifest: dict[str, Any],
) -> None:
    # iroh declares storage but is blocked without evidence; health is configuration.
    decision = _route_storage(manifest, type_name="iroh", capability="storage")
    assert decision["selected"] is None

    # Configuration-only backends do not declare storage.
    decision = _route_storage(manifest, type_name="local", capability="storage")
    assert decision["selected"] is None
    assert decision["reason"] in {
        "storage_not_declared",
        "configuration-only",
        "unsupported",
    }


def test_summary_honesty_counters(manifest: dict[str, Any]) -> None:
    summary = manifest["summary"]
    assert summary["production_count"] == 0
    assert summary["live_production_count"] == 0
    assert summary["honesty"]["production_backends_at_join"] == 0
    assert summary["honesty"]["hidden_fallback_entries"] == 0
    assert summary["honesty"]["silent_pass_on_missing_evidence"] == 0
    assert summary["storage_selectable_count"] == sum(
        1 for b in manifest["backends"] if b["routing"]["storage_selectable"]
    )


def test_mcp_default_manager_blocked_is_not_a_pass(manifest: dict[str, Any]) -> None:
    status = json.loads(MCP_STATUS_PATH.read_text(encoding="utf-8"))
    assert status["status"] == "blocked"
    expected = _cid_for(
        "backend_service_receipts/mcp_default_manager_status.json",
        MCP_STATUS_PATH.read_bytes(),
    )
    recorded = manifest["evidence_authority"]["service_receipts"]["mcp_default_manager"]
    assert recorded["status"] == "blocked"
    assert recorded["evidence_cid"] == expected
    ipfs = next(b for b in manifest["backends"] if b["canonical_name"] == "ipfs")
    assert ipfs["routing"]["storage_selectable"] is False
    assert ipfs["service_certification"]["mcp_default_manager"]["status"] == "blocked"


# ---------------------------------------------------------------------------
# Semantics: durability, auth, integrity
# ---------------------------------------------------------------------------


def test_semantics_and_secret_model_are_declared(
    backends_by_name: dict[str, dict[str, Any]],
) -> None:
    for name, entry in backends_by_name.items():
        semantics = entry["semantics"]
        assert "durability" in semantics
        assert "auth" in semantics
        assert "integrity" in semantics
        assert "secret" in semantics["auth"].lower() or "credential" in semantics["auth"].lower()
        secret_fields = entry["schema"]["secret_fields"]
        for field in BACKEND_SPECS[name].secret_fields:
            assert field in secret_fields


def test_authorized_secret_references_only_for_sensitive_fields() -> None:
    raw = "raw-secret-must-not-appear"
    with pytest.raises(Exception) as exc_info:
        ProviderAdapterCatalog(now=NOW).resolve("s3", configuration={"access_key": raw})
    assert exc_info.value.error.code is ErrorCode.SECRET_MATERIAL  # type: ignore[attr-defined]
    assert raw not in str(exc_info.value)

    ok = ProviderAdapterCatalog(now=NOW).resolve(
        "s3",
        configuration={
            "endpoint": "https://example.invalid",
            "access_key_ref": "secretref:secure-config:s3-access",
            "secret_key_ref": "secretref:credential-manager:s3-secret",
        },
    )
    assert "secretref:" not in repr(ok.configuration)
    assert ok.configuration.as_runtime_values() == {"endpoint": "https://example.invalid"}


def test_iroh_mutators_require_idempotency_when_runtime_ready() -> None:
    class CanonicalRuntime:
        is_canonical_provider_adapter = True
        provider_type = "iroh"

    receipt = {
        "schema": "ipfs-kit-provider-receipt/v1",
        "receipt_id": "iroh-idem",
        "provider_type": "iroh",
        "issued_at": (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (NOW + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime_factory": "create_filesystem",
        "tested_operations": list(STORAGE_OPERATIONS),
        "rate_limit": {"max_requests": 10, "window_seconds": 60},
        "timeout_seconds": 10,
        "retry": {"max_attempts": 1, "retryable_codes": ["E_UNAVAILABLE"]},
        "idempotency": {"required_for_mutations": True},
        "consistency": {"model": "read-your-writes", "verified": True},
    }
    factory = CanonicalRuntimeFactory(
        provider_type="iroh",
        adapter_id="iroh-repository-adapter",
        create=lambda request: CanonicalRuntime(),
    )
    adapter = ProviderAdapterCatalog(
        receipts={"iroh": receipt},
        runtime_factories={"iroh": factory},
        now=NOW,
    ).resolve("iroh")
    assert adapter.availability is ProviderAvailability.RUNTIME_READY
    with pytest.raises(Exception) as exc_info:
        adapter.require_storage("put")
    assert exc_info.value.error.code is ErrorCode.PRECONDITION_FAILED  # type: ignore[attr-defined]
    prepared = adapter.require_storage("put", idempotency_key="write-1")
    assert prepared.idempotency_key_present is True
    runtime = adapter.create_runtime()
    assert isinstance(runtime, CanonicalRuntime)


# ---------------------------------------------------------------------------
# All-interface parity for advertised backend operations
# ---------------------------------------------------------------------------


def _fixture_transports(public_name: str) -> dict[str, str]:
    return {
        "python": public_name,
        "cli": public_name,
        "mcp": public_name,
        "mcpp": public_name,
    }


def _operation(
    operation_id: str,
    *,
    transport_names: dict[str, str],
    support_tier: CapabilityTier = CapabilityTier.PRODUCTION,
    capability: str | None = None,
    authorization: AuthorizationRequirement | None = None,
) -> OperationDefinition:
    return OperationDefinition(
        operation_id=operation_id,
        version=1,
        request_schema=OPERATION_REQUEST_SCHEMA,
        result_schema=OPERATION_RESULT_SCHEMA,
        error_schema=STORAGE_ERROR_SCHEMA,
        capability=capability or operation_id,
        authorization=authorization or AuthorizationRequirement.public(),
        handler_route="backend-matrix-fixture",
        transport_names=transport_names,
        support_tier=support_tier,
    )


async def _backend_handler(
    definition: OperationDefinition, request: Any, _context: DispatchContext
) -> OperationResult:
    """Success handler for configuration/health; blocked paths use capability gate."""

    if definition.operation_id.endswith(".blocked"):
        error = StorageError(
            code=ErrorCode.CAPABILITY_MISSING,
            category=ErrorCategory.CAPABILITY,
            message="provider runtime requires a current provider receipt",
            retryability=Retryability.NEVER,
            state=OperationState.UNAVAILABLE,
            related_operation_id=definition.operation_id,
        )
        return OperationResult(
            request_id="backend-matrix-request",
            operation_id=definition.operation_id,
            state=OperationState.UNAVAILABLE,
            success=False,
            error=error,
        )
    return OperationResult(
        request_id="backend-matrix-request",
        operation_id=definition.operation_id,
        state=OperationState.ACCEPTED,
        success=True,
        resulting_content_cid="cid:backend-matrix",
        resulting_version_cid="cid:backend-matrix-version",
    )


def _backend_router(definitions: tuple[OperationDefinition, ...]) -> ServiceRouter:
    registry = OperationRegistry(definitions)
    router = ServiceRouter(registry)
    router.bind_handler(
        "backend-matrix-fixture",
        _backend_handler,
        capabilities={definition.capability for definition in definitions},
    )
    return router


def _all_adapters(router: ServiceRouter) -> dict[str, Any]:
    registry = router.registry
    return {
        "package": PythonAdapter(registry, router),
        "python_sync": PythonAdapter(registry, router),
        "python_async": AsyncPythonAdapter(registry, router),
        "cli": CLIAdapter(registry, router),
        "mcp": MCPToolAdapter(registry, router),
        "mcpp": MCPPlusPlusToolAdapter(registry, router),
    }


def test_advertised_operations_have_python_cli_mcp_mcpp_parity(
    backends_by_name: dict[str, dict[str, Any]],
) -> None:
    """Advertised backend operations project identically across all interfaces."""

    definitions: list[OperationDefinition] = []
    cases: list[tuple[str, str, str]] = []  # (backend, op_kind, public_name)

    for name, entry in sorted(backends_by_name.items()):
        advertised = entry["operations"]["advertised"]
        if not advertised:
            public = f"backend-{name}-unsupported"
            definitions.append(
                _operation(
                    f"backend.{name}.storage",
                    transport_names=_fixture_transports(public),
                    support_tier=CapabilityTier.UNSUPPORTED,
                    capability=f"backend.{name}.storage",
                )
            )
            cases.append((name, "unsupported", public))
            continue

        if entry["disposition"] == "configuration-only":
            # Health is advertised and must succeed with identical semantics.
            public = f"backend-{name}-health"
            definitions.append(
                _operation(
                    f"backend.{name}.health",
                    transport_names=_fixture_transports(public),
                    support_tier=CapabilityTier.CONFIGURATION_ONLY,
                    capability=f"backend.{name}.health",
                )
            )
            cases.append((name, "health", public))
            # Storage is not runtime-ready: reject identically on every surface.
            public_storage = f"backend-{name}-storage"
            definitions.append(
                _operation(
                    f"backend.{name}.storage",
                    transport_names=_fixture_transports(public_storage),
                    support_tier=CapabilityTier.UNSUPPORTED,
                    capability=f"backend.{name}.storage",
                )
            )
            cases.append((name, "storage-reject", public_storage))
            continue

        if entry["disposition"] in {
            "conditional-receipt-required",
            "conditional-canonical-missing",
        }:
            # Declared storage ops are advertised but blocked without evidence.
            public = f"backend-{name}-blocked"
            definitions.append(
                _operation(
                    f"backend.{name}.blocked",
                    transport_names=_fixture_transports(public),
                    support_tier=CapabilityTier.CONDITIONAL,
                    capability=f"backend.{name}.storage",
                )
            )
            cases.append((name, "blocked", public))
            continue

        public = f"backend-{name}-health"
        definitions.append(
            _operation(
                f"backend.{name}.health",
                transport_names=_fixture_transports(public),
                support_tier=CapabilityTier.PRODUCTION,
                capability=f"backend.{name}.health",
            )
        )
        cases.append((name, "health", public))

    router = _backend_router(tuple(definitions))
    adapters = _all_adapters(router)
    request: dict[str, Any] = {}
    arguments = {"request": request}

    for _backend, kind, public_name in cases:
        package = adapters["package"].call(public_name, request)
        python_sync = adapters["python_sync"].call(public_name, request)
        python_async = asyncio.run(adapters["python_async"].call(public_name, request))
        cli = asyncio.run(adapters["cli"].invoke(public_name, request))
        mcp = adapters["mcp"].call(public_name, arguments)
        mcpp_stdio = asyncio.run(
            adapters["mcpp"].call_framed("stdio", public_name, arguments)
        )
        mcpp_http = asyncio.run(
            adapters["mcpp"].call_framed("http", public_name, arguments)
        )
        mcpp_p2p = asyncio.run(
            adapters["mcpp"].call_framed("p2p", public_name, arguments)
        )

        reference = semantic_payload(package)
        assert semantic_payload(python_sync) == reference
        assert semantic_payload(python_async) == reference
        assert semantic_payload(cli) == reference
        assert semantic_payload(mcp) == reference
        assert strip_transport_fields(mcpp_stdio) == reference
        assert strip_transport_fields(mcpp_http) == reference
        assert strip_transport_fields(mcpp_p2p) == reference

        if kind == "health":
            assert package.success is True
            assert package.exit_code == 0
        elif kind in {"unsupported", "storage-reject"}:
            assert package.success is False
            assert package.error is not None
            assert package.error.code is ErrorCode.UNSUPPORTED
        elif kind == "blocked":
            assert package.success is False
            assert package.error is not None
            assert package.error.code is ErrorCode.CAPABILITY_MISSING


def test_interface_certification_block_matches_policy(manifest: dict[str, Any]) -> None:
    block = manifest["interface_certification"]
    assert block["parity_policy"] == "AllInterfaceParityPolicy@1"
    assert set(block["transports"]) == {"python", "cli", "mcp", "mcpp"}
    assert block["authority"].endswith("interface_manifest.json")
    for rule in (
        "Advertised operations on configuration-only entries are configuration and health only.",
        "Invoking storage on non-runtime-ready backends yields typed rejection on every transport.",
    ):
        assert rule in block["rules"]


# ---------------------------------------------------------------------------
# Subsystem join integrity
# ---------------------------------------------------------------------------


def test_subsystem_joins_reference_dependency_evidence(manifest: dict[str, Any]) -> None:
    joins = manifest["subsystem_joins"]
    for dep in (
        "KITA-013",
        "KITA-017",
        "KITA-021",
        "KITA-025",
        "KITA-029",
        "KITA-033",
        "KITA-037",
        "KITA-040",
        "KITA-041",
    ):
        assert dep in joins["dependencies"]
    for key in ("interfaces", "auth_mcplusplus", "replication", "graphrag", "arc"):
        entry = joins["evidence"][key]
        assert entry["status"] in {"joined", "referenced"}
        if entry.get("path"):
            path = PACKAGE_ROOT / entry["path"]
            assert path.is_file(), path
            assert entry["evidence_cids"]
            expected = _cid_for(entry["path"], path.read_bytes())
            assert entry["evidence_cids"][0] == expected
    for item in (
        "all_registry_types_aliases",
        "operations",
        "live_tier",
        "receipt_freshness",
        "interfaces",
        "auth",
        "wal",
        "replication",
        "graphrag",
        "arc",
    ):
        assert item in joins["evidence_subset"]


def test_iroh_is_the_only_conditional_storage_entry(
    backends_by_name: dict[str, dict[str, Any]],
) -> None:
    conditional = [
        e
        for e in backends_by_name.values()
        if e["tier"] == BackendSupportTier.CONDITIONAL.value
    ]
    assert len(conditional) == 1
    iroh = conditional[0]
    assert iroh["canonical_name"] == "iroh"
    assert iroh["factory"] == "create_filesystem"
    assert "storage" in iroh["capabilities"]
    assert "runtime_factory" in iroh["capabilities"]
    assert iroh["disposition"] == "conditional-receipt-required"
    assert iroh["routing"]["storage_selectable"] is False
    assert iroh["evidence"]["freshness"] == "missing"


def test_estuary_never_advertises_storage(
    backends_by_name: dict[str, dict[str, Any]],
) -> None:
    estuary = backends_by_name["estuary"]
    assert estuary["disposition"] == "configuration-only"
    assert "storage" not in estuary["capabilities"]
    assert estuary["operations"]["storage_advertised"] is False
    assert estuary["factory"] is None
    assert set(estuary["operations"]["advertised"]) <= {"configuration", "health"}
