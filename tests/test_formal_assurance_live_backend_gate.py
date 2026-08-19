"""FACP-027: Kit current live-backend qualification gate.

Acceptance covered here:

* Storage selection requires current live evidence.
* Stale / degraded / revoked evidence demotes automatically.
* No qualified backend yields typed Unavailable without fallback success.
* Zero live-qualified backends remain a valid honest state.
* Hermetic / configured / runtime-ready-alone cannot satisfy the live gate.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = KIT_ROOT / "ipfs_kit_py" / "assurance" / "live_backend_gate.py"
MANIFEST_PATH = (
    KIT_ROOT / "docs" / "runtime_readiness" / "backend_support_manifest.json"
)

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _load_gate():
    """Load the gate under ``ipfs_kit_py.assurance`` without requiring ``__init__.py``."""

    import importlib.util

    package_name = "ipfs_kit_py"
    assurance_name = "ipfs_kit_py.assurance"
    module_name = "ipfs_kit_py.assurance.live_backend_gate"

    if package_name not in sys.modules:
        try:
            import ipfs_kit_py as kit_pkg  # noqa: F401
        except ImportError:
            kit_pkg = types.ModuleType(package_name)
            kit_pkg.__path__ = [str(KIT_ROOT / "ipfs_kit_py")]  # type: ignore[attr-defined]
            sys.modules[package_name] = kit_pkg

    if assurance_name not in sys.modules:
        assurance_pkg = types.ModuleType(assurance_name)
        assurance_pkg.__path__ = [str(GATE_PATH.parent)]  # type: ignore[attr-defined]
        sys.modules[assurance_name] = assurance_pkg
        parent = sys.modules[package_name]
        setattr(parent, "assurance", assurance_pkg)

    # Prefer this worktree's module even if another checkout was imported first.
    spec = importlib.util.spec_from_file_location(module_name, GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    assurance = sys.modules[assurance_name]
    setattr(assurance, "live_backend_gate", module)
    return module


gate = _load_gate()

LiveBackendEvidence = gate.LiveBackendEvidence
LiveBackendDisposition = gate.LiveBackendDisposition
LiveBackendUnavailable = gate.LiveBackendUnavailable
DemotionReason = gate.DemotionReason
CLOSED_OUTCOME_UNAVAILABLE = gate.CLOSED_OUTCOME_UNAVAILABLE
assess_live_evidence = gate.assess_live_evidence
demote_if_not_current = gate.demote_if_not_current
is_live_qualified = gate.is_live_qualified
select_storage_backend = gate.select_storage_backend
require_live_qualified = gate.require_live_qualified
evaluate_provider_adapter = gate.evaluate_provider_adapter
select_from_provider_catalog = gate.select_from_provider_catalog
current_live_evidence = gate.current_live_evidence


def _live(backend: str = "iroh", **overrides) -> LiveBackendEvidence:
    evidence = current_live_evidence(backend, now=NOW)
    if overrides:
        evidence = evidence.with_overrides(**overrides)
    return evidence


# ---------------------------------------------------------------------------
# Identity / schema
# ---------------------------------------------------------------------------


def test_module_identity_and_vocabulary() -> None:
    assert gate.TASK_ID == "FACP-027"
    assert gate.GOAL_ID == "FACP-G230"
    assert gate.SCHEMA == "KitLiveBackendGate@1"
    assert gate.FCA_VOCABULARY_SCHEMA == "facp/formal-claim-algebra-v1@1"
    assert gate.UNSAFE_PROMOTION is False
    assert CLOSED_OUTCOME_UNAVAILABLE == "Unavailable"


# ---------------------------------------------------------------------------
# Current live evidence qualifies; storage selection succeeds
# ---------------------------------------------------------------------------


def test_current_live_evidence_qualifies_for_storage_selection() -> None:
    evidence = _live("iroh")
    assessment = assess_live_evidence(evidence, now=NOW)
    assert assessment.live_qualified is True
    assert assessment.disposition is LiveBackendDisposition.LIVE_QUALIFIED
    assert assessment.demotion_reason is None

    result = select_storage_backend([evidence], now=NOW)
    assert result.selected_backend == "iroh"
    assert result.fallback_attempted is False
    assert result.closed_outcome != CLOSED_OUTCOME_UNAVAILABLE
    assert result.production_supported is True
    assert is_live_qualified(result)
    assert "storage_selection_requires_current_live_evidence" in result.reason_codes


def test_require_live_qualified_passes_for_selected_backend() -> None:
    result = select_storage_backend([_live("iroh")], now=NOW)
    asserted = require_live_qualified(result)
    assert asserted.selected_backend == "iroh"


# ---------------------------------------------------------------------------
# Automatic demotion: stale / degraded / revoked
# ---------------------------------------------------------------------------


def test_stale_freshness_demotes_automatically() -> None:
    evidence = _live(freshness="stale")
    assessment = demote_if_not_current(evidence, now=NOW)
    assert assessment.disposition is LiveBackendDisposition.DEMOTED_STALE
    assert assessment.demotion_reason is DemotionReason.STALE
    assert assessment.live_qualified is False
    assert "automatic_demotion_stale" in assessment.reason_codes


def test_expired_receipt_demotes_as_stale() -> None:
    evidence = _live(
        issued_at=NOW - timedelta(days=2),
        expires_at=NOW - timedelta(seconds=1),
        freshness="current",
    )
    assessment = assess_live_evidence(evidence, now=NOW)
    assert assessment.disposition is LiveBackendDisposition.DEMOTED_STALE
    assert assessment.demotion_reason is DemotionReason.STALE
    assert "receipt_not_current" in assessment.reason_codes


@pytest.mark.parametrize("freshness", ["stale", "superseded", "withdrawn", "missing"])
def test_non_current_freshness_labels_demote(freshness: str) -> None:
    assessment = assess_live_evidence(_live(freshness=freshness), now=NOW)
    assert assessment.demoted is True
    assert assessment.demotion_reason is DemotionReason.STALE


@pytest.mark.parametrize("authority", ["revoked", "expired", "denied"])
def test_revoked_authority_demotes_automatically(authority: str) -> None:
    assessment = assess_live_evidence(_live(authority=authority), now=NOW)
    assert assessment.disposition is LiveBackendDisposition.DEMOTED_REVOKED
    assert assessment.demotion_reason is DemotionReason.REVOKED
    assert assessment.live_qualified is False
    assert "automatic_demotion_revoked" in assessment.reason_codes


def test_degraded_flag_demotes_automatically() -> None:
    assessment = assess_live_evidence(_live(degraded=True), now=NOW)
    assert assessment.disposition is LiveBackendDisposition.DEMOTED_DEGRADED
    assert assessment.demotion_reason is DemotionReason.DEGRADED
    assert "automatic_demotion_degraded" in assessment.reason_codes


def test_blocking_limitations_demote_as_degraded() -> None:
    assessment = assess_live_evidence(
        _live(limitations=("partial_outage", "read_only_forced")),
        now=NOW,
    )
    assert assessment.disposition is LiveBackendDisposition.DEMOTED_DEGRADED
    assert "partial_outage" in assessment.reason_codes


def test_revoked_takes_priority_over_stale_and_degraded() -> None:
    assessment = assess_live_evidence(
        _live(authority="revoked", freshness="stale", degraded=True),
        now=NOW,
    )
    assert assessment.demotion_reason is DemotionReason.REVOKED


# ---------------------------------------------------------------------------
# Non-live evidence cannot satisfy the live gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "origin,environment",
    [
        ("hermetic_observed", "hermetic"),
        ("fixture", "hermetic"),
        ("simulated", "conditional"),
        ("declared", "conditional"),
        ("declared", "live"),
        ("live_observed", "hermetic"),
        ("live_observed", "conditional"),
    ],
)
def test_hermetic_configured_fixture_cannot_satisfy_live_gate(
    origin: str, environment: str
) -> None:
    assessment = assess_live_evidence(
        _live(origin=origin, environment=environment),
        now=NOW,
    )
    assert assessment.live_qualified is False
    assert assessment.disposition is LiveBackendDisposition.NONQUALIFYING
    assert "hermetic_or_configured_cannot_satisfy_live_gate" in assessment.reason_codes


def test_missing_required_evidence_bag_nonqualifies() -> None:
    evidence = _live(evidence_bag={})
    assessment = assess_live_evidence(evidence, now=NOW)
    assert assessment.live_qualified is False
    assert assessment.demotion_reason is DemotionReason.MISSING_EVIDENCE
    assert "missing_required_evidence" in assessment.reason_codes


def test_unsigned_integrity_claim_nonqualifies() -> None:
    assessment = assess_live_evidence(
        _live(integrity="signature_valid", signature_valid=False),
        now=NOW,
    )
    assert assessment.live_qualified is False
    assert "integrity_signature_valid" in assessment.reason_codes


# ---------------------------------------------------------------------------
# No qualified backend → typed Unavailable, no fallback success
# ---------------------------------------------------------------------------


def test_empty_candidates_yield_typed_unavailable_without_fallback() -> None:
    result = select_storage_backend([], now=NOW)
    assert result.selected_backend is None
    assert result.closed_outcome == CLOSED_OUTCOME_UNAVAILABLE
    assert result.fallback_attempted is False
    assert result.disposition is LiveBackendDisposition.ZERO_QUALIFIED
    assert result.zero_qualified_is_valid_honest_state is True
    assert "no_fallback_success" in result.reason_codes
    decision = result.to_decision_dict()
    assert decision["selected"] is None
    assert decision["fallback_attempted"] is False
    assert decision["closed_outcome"] == "Unavailable"


def test_only_demoted_candidates_yield_unavailable_without_fallback_success() -> None:
    stale = _live("iroh", freshness="stale")
    revoked = _live("s3", authority="revoked")
    degraded = _live("local", degraded=True)
    result = select_storage_backend([stale, revoked, degraded], now=NOW)
    assert result.selected_backend is None
    assert result.closed_outcome == CLOSED_OUTCOME_UNAVAILABLE
    assert result.fallback_attempted is False
    assert result.live_qualified_count == 0
    assert "demoted_candidates_skipped_without_fallback" in result.reason_codes
    assert {a.demotion_reason for a in result.assessments} == {
        DemotionReason.STALE,
        DemotionReason.REVOKED,
        DemotionReason.DEGRADED,
    }


def test_demoted_preferred_does_not_fallback_to_hermetic_success() -> None:
    """Stale preferred backend must not soft-succeed via hermetic alternate."""

    preferred = _live("iroh", freshness="stale")
    hermetic_alt = _live(
        "local",
        origin="hermetic_observed",
        environment="hermetic",
        freshness="current",
    )
    result = select_storage_backend([preferred, hermetic_alt], now=NOW)
    assert result.selected_backend is None
    assert result.closed_outcome == CLOSED_OUTCOME_UNAVAILABLE
    assert result.fallback_attempted is False


def test_require_raises_typed_unavailable() -> None:
    with pytest.raises(LiveBackendUnavailable) as exc_info:
        select_storage_backend([_live(freshness="stale")], now=NOW, require=True)
    err = exc_info.value
    assert err.closed_outcome == "Unavailable"
    assert err.fallback_attempted is False
    assert err.result.selected_backend is None


def test_require_live_qualified_raises_on_unavailable_result() -> None:
    result = select_storage_backend([], now=NOW)
    with pytest.raises(LiveBackendUnavailable):
        require_live_qualified(result)


def test_selects_first_live_qualified_after_skipping_demoted() -> None:
    stale = _live("iroh", freshness="stale")
    good = _live("s3")
    result = select_storage_backend([stale, good], now=NOW)
    # Skipping a demoted candidate to reach a *live-qualified* one is selection
    # order, not a hidden non-qualified fallback success.
    assert result.selected_backend == "s3"
    assert result.fallback_attempted is False
    assert result.assessments[0].demoted is True
    assert result.assessments[1].live_qualified is True


# ---------------------------------------------------------------------------
# Provider catalog selector seam
# ---------------------------------------------------------------------------


def test_provider_catalog_without_live_evidence_is_nonqualifying() -> None:
    from ipfs_kit_py.backends.provider_adapters import ProviderAdapterCatalog

    catalog = ProviderAdapterCatalog(now=NOW)
    assessment = evaluate_provider_adapter("iroh", catalog=catalog, now=NOW)
    assert assessment.live_qualified is False
    assert assessment.availability == "receipt-required"
    assert assessment.demotion_reason in {
        DemotionReason.RECEIPT_REQUIRED,
        DemotionReason.NON_LIVE,
    }


def test_runtime_ready_alone_is_not_live_qualification() -> None:
    from ipfs_kit_py.backends.provider_adapters import (
        CanonicalRuntimeFactory,
        ProviderAdapterCatalog,
        ProviderAvailability,
        ProviderOperation,
    )

    receipt = {
        "schema": "ipfs-kit-provider-receipt/v1",
        "receipt_id": "iroh-receipt-20260819",
        "provider_type": "iroh",
        "issued_at": "2026-08-19T11:00:00Z",
        "expires_at": "2026-08-20T12:00:00Z",
        "runtime_factory": "create_filesystem",
        "tested_operations": [operation.value for operation in ProviderOperation],
        "rate_limit": {"max_requests": 2, "window_seconds": 60},
        "timeout_seconds": 10,
        "retry": {"max_attempts": 2, "retryable_codes": ["E_UNAVAILABLE"]},
        "idempotency": {"required_for_mutations": True},
        "consistency": {"model": "read-your-writes", "verified": True},
    }

    def _create(request):  # pragma: no cover - not invoked by gate
        raise AssertionError("gate must not create live runtimes")

    factory = CanonicalRuntimeFactory(
        provider_type="iroh",
        adapter_id="test-iroh-adapter",
        create=_create,
    )
    catalog = ProviderAdapterCatalog(
        receipts={"iroh": receipt},
        runtime_factories={"iroh": factory},
        now=NOW,
    )
    adapter = catalog.resolve("iroh")
    assert adapter.availability is ProviderAvailability.RUNTIME_READY
    assert adapter.supports_storage is True

    # Catalog runtime-ready without live evidence product → not live-qualified.
    assessment = evaluate_provider_adapter("iroh", catalog=catalog, now=NOW)
    assert assessment.live_qualified is False
    assert assessment.availability == "runtime-ready"

    result = select_from_provider_catalog(
        ["iroh"],
        catalog=catalog,
        now=NOW,
    )
    assert result.selected_backend is None
    assert result.closed_outcome == CLOSED_OUTCOME_UNAVAILABLE
    assert result.fallback_attempted is False


def test_catalog_selects_when_live_evidence_and_runtime_ready() -> None:
    from ipfs_kit_py.backends.provider_adapters import (
        CanonicalRuntimeFactory,
        ProviderAdapterCatalog,
        ProviderOperation,
    )

    receipt = {
        "schema": "ipfs-kit-provider-receipt/v1",
        "receipt_id": "iroh-receipt-20260819",
        "provider_type": "iroh",
        "issued_at": "2026-08-19T11:00:00Z",
        "expires_at": "2026-08-20T12:00:00Z",
        "runtime_factory": "create_filesystem",
        "tested_operations": [operation.value for operation in ProviderOperation],
        "rate_limit": {"max_requests": 2, "window_seconds": 60},
        "timeout_seconds": 10,
        "retry": {"max_attempts": 2, "retryable_codes": ["E_UNAVAILABLE"]},
        "idempotency": {"required_for_mutations": True},
        "consistency": {"model": "read-your-writes", "verified": True},
    }
    factory = CanonicalRuntimeFactory(
        provider_type="iroh",
        adapter_id="test-iroh-adapter",
        create=lambda request: (_ for _ in ()).throw(AssertionError("no runtime")),
    )
    catalog = ProviderAdapterCatalog(
        receipts={"iroh": receipt},
        runtime_factories={"iroh": factory},
        now=NOW,
    )
    result = select_from_provider_catalog(
        ["iroh"],
        catalog=catalog,
        live_evidence={"iroh": _live("iroh")},
        now=NOW,
    )
    assert result.selected_backend == "iroh"
    assert result.fallback_attempted is False
    assert result.production_supported is True


def test_default_inventory_is_honest_zero_qualified() -> None:
    result = select_from_provider_catalog(now=NOW)
    assert result.selected_backend is None
    assert result.closed_outcome == CLOSED_OUTCOME_UNAVAILABLE
    assert result.fallback_attempted is False
    assert result.live_qualified_count == 0
    assert result.zero_qualified_is_valid_honest_state is True
    assert "zero_live_qualified_backends" in result.reason_codes


def test_joined_manifest_summary_agrees_zero_qualified() -> None:
    import json

    if not MANIFEST_PATH.is_file():
        pytest.skip("joined backend support manifest not present in checkout")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    summary = manifest["summary"]
    assert summary["live_production_count"] == 0
    assert summary["storage_selectable_count"] == 0
    assert summary["honesty"]["hidden_fallback_entries"] == 0

    result = select_from_provider_catalog(now=NOW)
    assert result.zero_qualified_is_valid_honest_state is True
    assert result.closed_outcome == CLOSED_OUTCOME_UNAVAILABLE


def test_configuration_only_backend_never_selected_with_live_labels() -> None:
    """Even if a caller forges live dimensions, catalog configuration-only demotes."""

    forged = _live("estuary")
    assessment = evaluate_provider_adapter(
        "estuary",
        evidence=forged,
        catalog=__import__(
            "ipfs_kit_py.backends.provider_adapters", fromlist=["ProviderAdapterCatalog"]
        ).ProviderAdapterCatalog(now=NOW),
        configuration={"token_ref": "secretref:environment:estuary"},
        now=NOW,
    )
    # configuration-only availability forces nonqualifying before live product.
    assert assessment.live_qualified is False
    assert assessment.availability == "configuration-only"
    assert assessment.demotion_reason is DemotionReason.CONFIGURATION_ONLY


# ---------------------------------------------------------------------------
# Decision shape / invariants
# ---------------------------------------------------------------------------


def test_gate_result_forbids_fallback_attempted_true() -> None:
    with pytest.raises(gate.LiveBackendGateError):
        gate.LiveBackendGateResult(
            disposition=LiveBackendDisposition.UNAVAILABLE,
            closed_outcome=CLOSED_OUTCOME_UNAVAILABLE,
            selected_backend=None,
            fallback_attempted=True,
            reason_codes=("x",),
        )


def test_unavailable_exception_forbids_selected_backend() -> None:
    good = select_storage_backend([_live("iroh")], now=NOW)
    with pytest.raises(gate.LiveBackendGateError):
        LiveBackendUnavailable(good)
