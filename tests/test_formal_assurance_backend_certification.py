"""FACP-053: Backend certification suite generator.

Acceptance covered here:

* Generator deterministically produces required suites / receipt schema /
  support row.
* Absent live runner yields Conditional / Unavailable evidence.
* No result can set LiveQualified without a complete observed suite.
* Unit tests never contact a live backend; credentials are never stored;
  unlisted backends are rejected.
"""

from __future__ import annotations

import copy
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = KIT_ROOT / "ipfs_kit_py" / "assurance" / "backend_certification.py"

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _load_module():
    """Load under ``ipfs_kit_py.assurance`` without requiring ``__init__.py``."""

    import importlib.util

    package_name = "ipfs_kit_py"
    assurance_name = "ipfs_kit_py.assurance"
    module_name = "ipfs_kit_py.assurance.backend_certification"

    if package_name not in sys.modules:
        try:
            import ipfs_kit_py as kit_pkg  # noqa: F401
        except ImportError:
            kit_pkg = types.ModuleType(package_name)
            kit_pkg.__path__ = [str(KIT_ROOT / "ipfs_kit_py")]  # type: ignore[attr-defined]
            sys.modules[package_name] = kit_pkg

    if assurance_name not in sys.modules:
        assurance_pkg = types.ModuleType(assurance_name)
        assurance_pkg.__path__ = [str(MODULE_PATH.parent)]  # type: ignore[attr-defined]
        sys.modules[assurance_name] = assurance_pkg
        parent = sys.modules[package_name]
        setattr(parent, "assurance", assurance_pkg)

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    assurance = sys.modules[assurance_name]
    setattr(assurance, "backend_certification", module)
    return module


mod = _load_module()

BackendCertificationError = mod.BackendCertificationError
BackendCertificationRejected = mod.BackendCertificationRejected
CertificationDisposition = mod.CertificationDisposition
ObservationStatus = mod.ObservationStatus
SuiteCaseKind = mod.SuiteCaseKind
OperationObservation = mod.OperationObservation
REQUIRED_SUITE_OPERATIONS = mod.REQUIRED_SUITE_OPERATIONS
REQUIRED_EVIDENCE_BINDINGS = mod.REQUIRED_EVIDENCE_BINDINGS
COHORT_BACKEND_IDS = mod.COHORT_BACKEND_IDS
RECEIPT_SCHEMA = mod.RECEIPT_SCHEMA
CLOSED_OUTCOME_UNAVAILABLE = mod.CLOSED_OUTCOME_UNAVAILABLE
normalize_backend_id = mod.normalize_backend_id
is_cohort_backend = mod.is_cohort_backend
receipt_schema = mod.receipt_schema
cohort_contracts = mod.cohort_contracts
contract_for = mod.contract_for
contract_digest = mod.contract_digest
generate_suite = mod.generate_suite
generate_cohort_suites = mod.generate_cohort_suites
build_receipt = mod.build_receipt
absent_live_runner_result = mod.absent_live_runner_result
evaluate_observations = mod.evaluate_observations
require_live_qualified = mod.require_live_qualified
complete_live_observations = mod.complete_live_observations
generate_all_artifacts = mod.generate_all_artifacts


# ---------------------------------------------------------------------------
# Identity / vocabulary
# ---------------------------------------------------------------------------


def test_module_identity_and_vocabulary() -> None:
    assert mod.TASK_ID == "FACP-053"
    assert mod.GOAL_ID == "FACP-G520"
    assert mod.SCHEMA == "BackendCertificationSuite@1"
    assert mod.RECEIPT_SCHEMA == "BackendCertificationReceipt@1"
    assert mod.EVIDENCE_BUNDLE == "facp/backend-suite@1"
    assert mod.FCA_VOCABULARY_SCHEMA == "facp/formal-claim-algebra-v1@1"
    assert mod.UNSAFE_PROMOTION is False
    assert CLOSED_OUTCOME_UNAVAILABLE == "Unavailable"
    assert COHORT_BACKEND_IDS == ("local_filesystem", "pinned_ipfs", "iroh")


def test_required_suite_operations_cover_evidence_subset() -> None:
    expected = {
        "write",
        "read_back",
        "digest",
        "delete",
        "replay",
        "timeout",
        "concurrency",
        "restart",
        "corruption",
        "large_object",
        "credential",
        "interface_parity",
    }
    assert set(REQUIRED_SUITE_OPERATIONS) == expected
    assert list(REQUIRED_SUITE_OPERATIONS) == sorted(
        REQUIRED_SUITE_OPERATIONS, key=list(REQUIRED_SUITE_OPERATIONS).index
    )
    assert set(REQUIRED_EVIDENCE_BINDINGS) == {
        "environment",
        "source",
        "signature",
        "freshness",
    }


# ---------------------------------------------------------------------------
# Deterministic suite / schema / support row generation
# ---------------------------------------------------------------------------


def test_cohort_contracts_are_stable_and_digestable() -> None:
    first = cohort_contracts()
    second = cohort_contracts()
    assert [c.backend_id for c in first] == list(COHORT_BACKEND_IDS)
    assert [contract_digest(c) for c in first] == [contract_digest(c) for c in second]
    for contract in first:
        assert "store_credential" in contract.prohibited_effects
        assert "certify_unlisted_backend" in contract.prohibited_effects


def test_generate_suite_is_deterministic_and_complete() -> None:
    contract = contract_for("iroh")
    suite_a = generate_suite(contract, now=NOW)
    suite_b = generate_suite(contract, now=NOW)
    assert suite_a.to_dict() == suite_b.to_dict()
    assert suite_a.suite_digest == suite_b.suite_digest
    assert suite_a.operations == REQUIRED_SUITE_OPERATIONS
    assert suite_a.receipt_schema == RECEIPT_SCHEMA
    assert suite_a.hermetic is True
    assert suite_a.live_calls is False
    assert suite_a.evidence_bindings == REQUIRED_EVIDENCE_BINDINGS

    ops = {case.operation for case in suite_a.cases}
    assert ops == set(REQUIRED_SUITE_OPERATIONS)
    kinds = {case.kind for case in suite_a.cases}
    assert kinds == {
        SuiteCaseKind.TEST,
        SuiteCaseKind.MODEL,
        SuiteCaseKind.FAULT,
        SuiteCaseKind.RECEIPT,
    }
    for case in suite_a.cases:
        for key in REQUIRED_EVIDENCE_BINDINGS:
            assert key in case.binds


def test_generate_cohort_suites_covers_all_backends() -> None:
    suites = generate_cohort_suites(now=NOW)
    assert set(suites) == set(COHORT_BACKEND_IDS)
    digests = {backend: suite.suite_digest for backend, suite in suites.items()}
    assert digests == {
        backend: generate_suite(contract_for(backend), now=NOW).suite_digest
        for backend in COHORT_BACKEND_IDS
    }


def test_receipt_schema_document_lists_required_fields() -> None:
    schema = receipt_schema()
    assert schema["schema"] == RECEIPT_SCHEMA
    required = set(schema["required_fields"])
    for field in (
        "disposition",
        "live_qualified",
        "suite_complete",
        "operations_required",
        "environment",
        "source",
        "signature_valid",
        "freshness",
        "credentials_stored",
    ):
        assert field in required
    assert "live_qualified_without_complete_suite" in schema["forbidden"]
    assert set(schema["operations_enum"]) == set(REQUIRED_SUITE_OPERATIONS)
    assert set(schema["disposition_enum"]) == {
        "LiveQualified",
        "Conditional",
        "Unavailable",
    }


def test_generate_all_artifacts_emits_suites_schema_and_support_rows() -> None:
    artifacts = generate_all_artifacts(now=NOW)
    assert artifacts["task_id"] == "FACP-053"
    assert set(artifacts["suites"]) == set(COHORT_BACKEND_IDS)
    assert artifacts["receipt_schema"]["schema"] == RECEIPT_SCHEMA
    assert len(artifacts["support_rows"]) == len(COHORT_BACKEND_IDS)
    for row in artifacts["support_rows"]:
        assert row["schema"] == "BackendSupportRow@1"
        assert row["receipt_schema"] == RECEIPT_SCHEMA
        assert row["disposition"] in {"Conditional", "Unavailable", "LiveQualified"}
        assert row["storage_selectable"] is False
        assert row["suite_complete"] is False
        assert set(row["operations_required"]) == set(REQUIRED_SUITE_OPERATIONS)
    # Determinism
    assert artifacts == generate_all_artifacts(now=NOW)


# ---------------------------------------------------------------------------
# Absent live runner → Conditional / Unavailable (never LiveQualified)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend", list(COHORT_BACKEND_IDS))
def test_absent_live_runner_yields_conditional_or_unavailable(backend: str) -> None:
    contract = contract_for(backend)
    result = absent_live_runner_result(contract, now=NOW)
    assert result.live_qualified is False
    assert result.suite_complete is False
    assert result.live_runner_present is False
    assert result.disposition in {
        CertificationDisposition.CONDITIONAL,
        CertificationDisposition.UNAVAILABLE,
    }
    assert result.closed_outcome == CLOSED_OUTCOME_UNAVAILABLE
    assert "live_runner_absent" in result.reason_codes
    assert "live_qualified_requires_complete_observed_suite" in result.reason_codes
    assert result.receipt["live_qualified"] is False
    assert result.receipt["credentials_stored"] is False
    assert result.receipt["hidden_fallback"] is False
    assert result.support_row.storage_selectable is False
    assert result.support_row.disposition is CertificationDisposition.CONDITIONAL
    with pytest.raises(BackendCertificationRejected):
        require_live_qualified(result)


def test_evaluate_without_live_runner_ignores_supplied_observations() -> None:
    contract = contract_for("local_filesystem")
    # Even a full "passed" set cannot promote without a live runner.
    result = evaluate_observations(
        contract,
        complete_live_observations(),
        live_runner_present=False,
        now=NOW,
    )
    assert result.live_qualified is False
    assert result.disposition in {
        CertificationDisposition.CONDITIONAL,
        CertificationDisposition.UNAVAILABLE,
    }
    assert "observations_without_live_runner_ignored" in result.reason_codes


def test_daemon_backends_absent_runner_are_unavailable_evidence() -> None:
    for backend in ("pinned_ipfs", "iroh"):
        result = absent_live_runner_result(contract_for(backend), now=NOW)
        assert result.disposition is CertificationDisposition.UNAVAILABLE
        assert "daemon_required" in result.reason_codes
        assert "live_evidence_unavailable" in result.reason_codes


def test_local_filesystem_absent_runner_is_conditional() -> None:
    result = absent_live_runner_result(contract_for("filesystem"), now=NOW)
    assert result.disposition is CertificationDisposition.CONDITIONAL
    assert result.backend_id == "local_filesystem"


# ---------------------------------------------------------------------------
# LiveQualified only with complete observed suite
# ---------------------------------------------------------------------------


def test_complete_live_suite_sets_live_qualified() -> None:
    contract = contract_for("local_filesystem")
    result = evaluate_observations(
        contract,
        complete_live_observations(),
        live_runner_present=True,
        now=NOW,
    )
    assert result.disposition is CertificationDisposition.LIVE_QUALIFIED
    assert result.live_qualified is True
    assert result.suite_complete is True
    assert result.closed_outcome == mod.CLOSED_OUTCOME_VERIFIED
    assert result.operations_missing == ()
    assert result.operations_failed == ()
    assert set(result.operations_observed) == set(REQUIRED_SUITE_OPERATIONS)
    assert result.receipt["storage_selectable"] is True
    assert result.support_row.storage_selectable is True
    assert result.support_row.live_tier == "production"
    assert require_live_qualified(result) is result


def test_incomplete_suite_cannot_set_live_qualified() -> None:
    contract = contract_for("iroh")
    observations = list(complete_live_observations())
    # Drop digest observation.
    observations = [item for item in observations if item.operation != "digest"]
    result = evaluate_observations(
        contract,
        observations,
        live_runner_present=True,
        now=NOW,
    )
    assert result.live_qualified is False
    assert result.suite_complete is False
    assert result.disposition is CertificationDisposition.CONDITIONAL
    assert "digest" in result.operations_missing
    assert "incomplete_observed_suite" in result.reason_codes
    assert result.receipt["live_qualified"] is False
    assert result.support_row.storage_selectable is False
    with pytest.raises(BackendCertificationRejected) as exc_info:
        require_live_qualified(result)
    assert exc_info.value.result.live_qualified is False


def test_failed_operation_yields_unavailable_not_live_qualified() -> None:
    contract = contract_for("pinned_ipfs")
    observations = list(complete_live_observations())
    observations = [
        (
            OperationObservation(
                operation="corruption",
                status=ObservationStatus.FAILED,
                environment="live",
                source="live_observed",
                signature_valid=True,
                freshness="current",
                detail="bit flip undetected",
            )
            if item.operation == "corruption"
            else item
        )
        for item in observations
    ]
    result = evaluate_observations(
        contract,
        observations,
        live_runner_present=True,
        now=NOW,
    )
    assert result.disposition is CertificationDisposition.UNAVAILABLE
    assert result.live_qualified is False
    assert "corruption" in result.operations_failed
    assert "observed_suite_failed" in result.reason_codes


@pytest.mark.parametrize(
    "bad_field,kwargs",
    [
        ("environment", {"environment": "hermetic"}),
        ("source", {"source": "fixture"}),
        ("source", {"source": "configured"}),
        ("signature", {"signature_valid": False}),
        ("freshness", {"freshness": "stale"}),
    ],
)
def test_non_live_observation_dimensions_block_live_qualified(
    bad_field: str, kwargs: dict
) -> None:
    contract = contract_for("iroh")
    base = {
        "environment": "live",
        "source": "live_observed",
        "signature_valid": True,
        "freshness": "current",
    }
    base.update(kwargs)
    observations = complete_live_observations(**base)
    result = evaluate_observations(
        contract,
        observations,
        live_runner_present=True,
        now=NOW,
    )
    assert result.live_qualified is False
    assert result.disposition is CertificationDisposition.CONDITIONAL
    assert result.suite_complete is False
    assert any(bad_field in code or "not_live" in code or "signature" in code or "freshness" in code for code in result.reason_codes)


def test_build_receipt_refuses_live_qualified_without_complete_suite() -> None:
    contract = contract_for("local_filesystem")
    with pytest.raises(BackendCertificationError, match="complete observed suite"):
        build_receipt(
            contract,
            disposition=CertificationDisposition.LIVE_QUALIFIED,
            live_qualified=True,
            suite_complete=False,
            operations_observed=("write",),
            operations_failed=(),
            reason_codes=("attempted_unsafe_promotion",),
            environment="live",
            source="live_observed",
            signature_valid=True,
            freshness="current",
            live_runner_present=True,
            now=NOW,
        )


def test_build_receipt_refuses_live_qualified_without_runner() -> None:
    contract = contract_for("local_filesystem")
    with pytest.raises(BackendCertificationError, match="live runner"):
        build_receipt(
            contract,
            disposition=CertificationDisposition.LIVE_QUALIFIED,
            live_qualified=True,
            suite_complete=True,
            operations_observed=list(REQUIRED_SUITE_OPERATIONS),
            operations_failed=(),
            reason_codes=("attempted_unsafe_promotion",),
            environment="live",
            source="live_observed",
            signature_valid=True,
            freshness="current",
            live_runner_present=False,
            now=NOW,
        )


def test_certification_result_invariant_rejects_live_qualified_incomplete() -> None:
    contract = contract_for("iroh")
    result = absent_live_runner_result(contract, now=NOW)
    with pytest.raises(BackendCertificationError):
        # Force illegal construction via replace if possible.
        result.__class__(
            backend_id=result.backend_id,
            disposition=CertificationDisposition.LIVE_QUALIFIED,
            closed_outcome=mod.CLOSED_OUTCOME_VERIFIED,
            live_qualified=True,
            suite_complete=False,
            live_runner_present=True,
            reason_codes=("illegal",),
            operations_required=REQUIRED_SUITE_OPERATIONS,
            operations_observed=(),
            operations_failed=(),
            operations_missing=REQUIRED_SUITE_OPERATIONS,
            receipt=dict(result.receipt),
            support_row=result.support_row,
            message="illegal",
        )


# ---------------------------------------------------------------------------
# Cohort / alias / unlisted / credential policies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alias,canonical",
    [
        ("filesystem", "local_filesystem"),
        ("local_fs", "local_filesystem"),
        ("ipfs", "pinned_ipfs"),
        ("kubo", "pinned_ipfs"),
        ("iroh", "iroh"),
    ],
)
def test_aliases_normalize_to_cohort(alias: str, canonical: str) -> None:
    assert normalize_backend_id(alias) == canonical
    assert is_cohort_backend(alias) is True
    assert contract_for(alias).backend_id == canonical


def test_unlisted_backend_is_rejected() -> None:
    assert is_cohort_backend("s3") is False
    with pytest.raises(BackendCertificationError, match="not in the first-program"):
        normalize_backend_id("s3")
    with pytest.raises(BackendCertificationError):
        contract_for("storacha")


def test_receipts_never_store_credentials() -> None:
    artifacts = generate_all_artifacts(now=NOW)
    blob = repr(artifacts)
    for result in artifacts["absent_runner_results"].values():
        assert result["receipt"]["credentials_stored"] is False
    assert "api_token" not in blob
    assert "secret_key" not in blob
    assert "raw-credential" not in blob


def test_suite_generation_does_not_perform_live_calls() -> None:
    suites = generate_cohort_suites(now=NOW)
    for suite in suites.values():
        assert suite.live_calls is False
        assert suite.hermetic is True
        assert all(
            case.binds["environment"] == "hermetic_generation" for case in suite.cases
        )


def test_support_row_matches_receipt_disposition_for_live_qualified() -> None:
    contract = contract_for("local_filesystem")
    result = evaluate_observations(
        contract,
        complete_live_observations(),
        live_runner_present=True,
        now=NOW,
    )
    assert result.support_row.to_dict()["disposition"] == result.receipt["disposition"]
    assert result.support_row.operations_observed == tuple(
        result.receipt["operations_observed"]
    )


def test_mutating_returned_suite_dict_does_not_affect_generator() -> None:
    suite = generate_suite(contract_for("iroh"), now=NOW)
    payload = suite.to_dict()
    mutated = copy.deepcopy(payload)
    mutated["cases"].clear()
    mutated["operations"].append("extra")
    again = generate_suite(contract_for("iroh"), now=NOW).to_dict()
    assert again == payload
    assert again != mutated
