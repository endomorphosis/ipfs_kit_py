"""FACP-015: Kit evidence / proof-role → FCA adapter gate.

Acceptance covered here:

* Round trip preserves every Kit distinction.
* Unsupported or ambiguous records remain nonqualifying.
* Zero-qualified live-backend state remains valid and nonqualifying.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = (
    KIT_ROOT / "ipfs_kit_py" / "assurance" / "formal_claim_adapter.py"
)
MANIFEST_PATH = (
    KIT_ROOT / "docs" / "runtime_readiness" / "backend_support_manifest.json"
)
SUPPORT_MATRIX_PATH = KIT_ROOT / "docs" / "kernel_vfs" / "support_matrix.json"


def _load_adapter():
    """Load the adapter module under ``ipfs_kit_py.assurance`` without requiring
    an undeclared ``__init__.py`` (task_output_exact allows only the adapter file).
    """

    import importlib.util

    package_name = "ipfs_kit_py"
    assurance_name = "ipfs_kit_py.assurance"
    module_name = "ipfs_kit_py.assurance.formal_claim_adapter"

    if package_name not in sys.modules:
        # Prefer the real package when the kit checkout is already importable.
        try:
            import ipfs_kit_py as kit_pkg  # noqa: F401
        except ImportError:
            kit_pkg = types.ModuleType(package_name)
            kit_pkg.__path__ = [str(KIT_ROOT / "ipfs_kit_py")]  # type: ignore[attr-defined]
            sys.modules[package_name] = kit_pkg

    if assurance_name not in sys.modules:
        assurance_pkg = types.ModuleType(assurance_name)
        assurance_pkg.__path__ = [str(ADAPTER_PATH.parent)]  # type: ignore[attr-defined]
        sys.modules[assurance_name] = assurance_pkg
        parent = sys.modules[package_name]
        setattr(parent, "assurance", assurance_pkg)

    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, ADAPTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    assurance = sys.modules[assurance_name]
    setattr(assurance, "formal_claim_adapter", module)
    return module


adapter = _load_adapter()

KitDistinctionFamily = adapter.KitDistinctionFamily
KitEvidenceRecord = adapter.KitEvidenceRecord
EvidenceEnvelope = adapter.EvidenceEnvelope
AdaptedKitClaim = adapter.AdaptedKitClaim
InformationLosingProjection = adapter.InformationLosingProjection
KitRecordIncompatible = adapter.KitRecordIncompatible
adapt_kit_record = adapter.adapt_kit_record
project_to_kit = adapter.project_to_kit
round_trip = adapter.round_trip
project_from_envelope_only = adapter.project_from_envelope_only
is_nonqualifying = adapter.is_nonqualifying
adapt_kernel_vfs_claim_class = adapter.adapt_kernel_vfs_claim_class
adapt_backend_support_tier = adapter.adapt_backend_support_tier
adapt_configured_selected_state = adapter.adapt_configured_selected_state
adapt_provider_availability = adapter.adapt_provider_availability
adapt_proof_role = adapter.adapt_proof_role
adapt_receipt_freshness = adapter.adapt_receipt_freshness
adapt_cas_outcome = adapter.adapt_cas_outcome
adapt_recovery_disposition = adapter.adapt_recovery_disposition
adapt_cas_identity = adapter.adapt_cas_identity
adapt_live_qualification_summary = adapter.adapt_live_qualification_summary
adapt_zero_qualified_state = adapter.adapt_zero_qualified_state
adapt_joined_manifest_summary = adapter.adapt_joined_manifest_summary
KERNEL_VFS_CLAIM_CLASSES = adapter.KERNEL_VFS_CLAIM_CLASSES
BACKEND_SUPPORT_TIERS = adapter.BACKEND_SUPPORT_TIERS
CONFIGURED_SELECTED_STATES = adapter.CONFIGURED_SELECTED_STATES
PROOF_ROLES = adapter.PROOF_ROLES
RECEIPT_FRESHNESS_LABELS = adapter.RECEIPT_FRESHNESS_LABELS
CAS_OUTCOMES = adapter.CAS_OUTCOMES
RECOVERY_DISPOSITIONS = adapter.RECOVERY_DISPOSITIONS


def _assert_round_trip(record: KitEvidenceRecord) -> AdaptedKitClaim:
    adapted = adapt_kit_record(record)
    restored = project_to_kit(adapted)
    assert restored == record
    assert round_trip(record) == record
    assert restored.to_dict() == record.to_dict()
    assert adapted.unsafe_promotion is False
    assert adapted.production_supported is False or adapted.qualifying
    return adapted


# ---------------------------------------------------------------------------
# Round-trip: every Kit distinction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("claim_class", sorted(KERNEL_VFS_CLAIM_CLASSES))
def test_round_trip_kernel_vfs_claim_classes(claim_class: str) -> None:
    adapted = _assert_round_trip(
        KitEvidenceRecord(
            family=KitDistinctionFamily.KERNEL_VFS_CLAIM_CLASS,
            value=claim_class,
        )
    )
    assert adapted.envelope.environment == claim_class
    assert is_nonqualifying(adapted)
    assert adapted.envelope.origin != "live_observed"


@pytest.mark.parametrize("tier", sorted(BACKEND_SUPPORT_TIERS))
def test_round_trip_backend_support_tiers(tier: str) -> None:
    adapted = _assert_round_trip(
        KitEvidenceRecord(
            family=KitDistinctionFamily.BACKEND_SUPPORT_TIER,
            value=tier,
            backend_name="iroh" if tier == "conditional" else "filesystem",
            inventory_tier=tier,
            live_tier=tier if tier != "unknown-pending-proof" else "unsupported",
        )
    )
    assert is_nonqualifying(adapted)
    assert "inventory" in " ".join(adapted.reason_codes) or any(
        "tier" in code for code in adapted.reason_codes
    )


@pytest.mark.parametrize("state", sorted(CONFIGURED_SELECTED_STATES))
def test_round_trip_configured_selected_states(state: str) -> None:
    adapted = _assert_round_trip(
        KitEvidenceRecord(
            family=KitDistinctionFamily.CONFIGURED_SELECTED_STATE,
            value=state,
            backend_name="iroh",
        )
    )
    assert is_nonqualifying(adapted)
    if state == "configured":
        assert "configured_is_not_selected" in adapted.reason_codes
    if state == "selected":
        assert "selected_is_not_live_qualification" in adapted.reason_codes
    if state == "unsupported":
        assert "unsupported_remains_nonqualifying" in adapted.reason_codes


@pytest.mark.parametrize("role", sorted(PROOF_ROLES))
def test_round_trip_proof_roles(role: str) -> None:
    adapted = _assert_round_trip(
        KitEvidenceRecord(
            family=KitDistinctionFamily.PROOF_ROLE,
            value=role,
            candidate_cid="bafyCandidate0001",
            authorization_cid="bafyAuthorization0002",
            current_cid="bafyCurrent0003" if role == "current" else None,
        )
    )
    assert is_nonqualifying(adapted)
    assert adapted.envelope.proof in {"candidate", "none", "unknown"}
    assert adapted.envelope.proof != "verified"
    if role == "candidate":
        assert "candidate_is_not_verified" in adapted.reason_codes
    if role == "admitted":
        assert "admitted_authorization_is_not_proof_verified" in adapted.reason_codes
    if role == "current":
        assert adapted.envelope.freshness == "current"


@pytest.mark.parametrize("label", sorted(RECEIPT_FRESHNESS_LABELS))
def test_round_trip_receipt_freshness(label: str) -> None:
    adapted = _assert_round_trip(
        KitEvidenceRecord(
            family=KitDistinctionFamily.RECEIPT_FRESHNESS,
            value=label,
        )
    )
    assert is_nonqualifying(adapted)
    if label in {"stale", "missing", "empty-authority", "empty-authority-current"}:
        assert adapted.envelope.freshness == "stale" or adapted.envelope.origin == "absent"


@pytest.mark.parametrize("outcome", sorted(CAS_OUTCOMES))
def test_round_trip_cas_outcomes(outcome: str) -> None:
    adapted = _assert_round_trip(
        KitEvidenceRecord(
            family=KitDistinctionFamily.CAS_OUTCOME,
            value=outcome,
            expected_cid="bafyExpected01",
            current_cid="bafyCurrent01" if outcome != "conflict" else "bafyOther02",
            expected_generation=3,
        )
    )
    assert is_nonqualifying(adapted)
    if outcome == "conflict":
        assert "no_silent_overwrite" in adapted.reason_codes


@pytest.mark.parametrize("disposition", sorted(RECOVERY_DISPOSITIONS))
def test_round_trip_recovery_dispositions(disposition: str) -> None:
    adapted = _assert_round_trip(
        KitEvidenceRecord(
            family=KitDistinctionFamily.RECOVERY_DISPOSITION,
            value=disposition,
            ambiguous=disposition == "ambiguous",
        )
    )
    assert is_nonqualifying(adapted)
    if disposition in {"ambiguous", "corrupt", "fail_closed"}:
        assert adapted.envelope.effect == "externally_unknown"
        assert any("nonqualifying" in code or "ambiguous" in code for code in adapted.reason_codes)


def test_round_trip_cas_identity_distinct_cids() -> None:
    adapted = _assert_round_trip(
        KitEvidenceRecord(
            family=KitDistinctionFamily.CAS_IDENTITY,
            value="distinct_candidate_authorization_current",
            candidate_cid="bafyCandA",
            authorization_cid="bafyAuthB",
            current_cid="bafyCurrC",
            expected_generation=1,
        )
    )
    assert adapted.kit.candidate_cid != adapted.kit.authorization_cid
    assert adapted.kit.current_cid == "bafyCurrC"
    assert is_nonqualifying(adapted)


def test_round_trip_preserves_attribute_sidecar() -> None:
    record = KitEvidenceRecord(
        family=KitDistinctionFamily.CONFIGURED_SELECTED_STATE,
        value="configured",
        backend_name="s3",
        attributes={
            "provider_availability": "configuration-only",
            "health_contract": "not-probed",
        },
    )
    adapted = _assert_round_trip(record)
    assert adapted.kit.attributes["provider_availability"] == "configuration-only"
    assert adapted.kit.attributes["health_contract"] == "not-probed"


# ---------------------------------------------------------------------------
# Nonqualifying: unsupported / ambiguous / forbidden promotions
# ---------------------------------------------------------------------------


def test_unsupported_backend_remains_nonqualifying() -> None:
    adapted = adapt_backend_support_tier("unsupported", backend_name="lotus")
    assert is_nonqualifying(adapted)
    assert adapted.production_supported is False
    assert "unsupported_remains_nonqualifying" in adapted.reason_codes


def test_ambiguous_recovery_remains_nonqualifying() -> None:
    adapted = adapt_recovery_disposition("ambiguous")
    assert adapted.kit.ambiguous is True
    assert is_nonqualifying(adapted)
    assert adapted.envelope.effect == "externally_unknown"
    assert "never_invent_promotion_winner" in adapted.reason_codes


def test_self_authorizing_proof_role_is_nonqualifying() -> None:
    adapted = adapt_proof_role(
        "admitted",
        candidate_cid="bafySame",
        authorization_cid="bafySame",
    )
    assert is_nonqualifying(adapted)
    assert "self_authorization_forbidden" in adapted.reason_codes
    assert adapted.envelope.authority == "denied"


def test_cas_identity_rejects_self_authorization() -> None:
    adapted = adapt_cas_identity(
        candidate_cid="bafySame",
        authorization_cid="bafySame",
        current_cid="bafyHead",
    )
    assert adapted.kit.value == "self_authorization_rejected"
    assert is_nonqualifying(adapted)
    assert project_to_kit(adapted).candidate_cid == "bafySame"


def test_hermetic_claim_class_does_not_become_live_observed() -> None:
    adapted = adapt_kernel_vfs_claim_class("hermetic")
    assert adapted.envelope.environment == "hermetic"
    assert adapted.envelope.origin != "live_observed"
    assert is_nonqualifying(adapted)
    assert "hermetic_is_not_live" in adapted.reason_codes


def test_live_claim_class_without_qualification_stays_nonqualifying() -> None:
    adapted = adapt_kernel_vfs_claim_class("live")
    assert adapted.envelope.environment == "live"
    assert adapted.envelope.origin == "declared"
    assert adapted.envelope.freshness == "stale"
    assert adapted.production_supported is False
    assert is_nonqualifying(adapted)


def test_configured_does_not_promote_to_selected_in_envelope() -> None:
    adapted = adapt_configured_selected_state("configured")
    restored = project_to_kit(adapted)
    assert restored.value == "configured"
    assert restored.value != "selected"
    assert is_nonqualifying(adapted)


def test_provider_availability_maps_without_promotion() -> None:
    configured = adapt_provider_availability("configuration-only", backend_name="s3")
    assert configured.kit.value == "configured"
    assert is_nonqualifying(configured)

    selected = adapt_provider_availability("runtime-ready", backend_name="iroh")
    assert selected.kit.value == "selected"
    assert is_nonqualifying(selected)
    assert selected.production_supported is False


def test_inventory_production_tier_is_not_live_qualification() -> None:
    adapted = adapt_backend_support_tier("production", backend_name="hypothetical")
    assert adapted.envelope.origin != "live_observed"
    assert adapted.envelope.environment != "live" or adapted.envelope.freshness != "current"
    assert is_nonqualifying(adapted)
    assert "inventory_production_is_not_live_qualification" in adapted.reason_codes


def test_stale_and_empty_receipts_nonqualifying() -> None:
    stale = adapt_receipt_freshness("stale")
    empty = adapt_receipt_freshness("empty-authority-current")
    assert is_nonqualifying(stale)
    assert is_nonqualifying(empty)
    assert empty.envelope.origin == "absent"
    assert "empty_authority_is_not_production_evidence" in empty.reason_codes


def test_envelope_only_reverse_projection_refused() -> None:
    envelope = EvidenceEnvelope.weakest().with_overrides(environment="live")
    with pytest.raises(InformationLosingProjection):
        project_from_envelope_only(
            envelope, family=KitDistinctionFamily.KERNEL_VFS_CLAIM_CLASS
        )


def test_unknown_claim_class_rejected() -> None:
    with pytest.raises(KitRecordIncompatible):
        KitEvidenceRecord(
            family=KitDistinctionFamily.KERNEL_VFS_CLAIM_CLASS,
            value="quasi-live",
        )


def test_weakest_envelope_never_production_supported() -> None:
    assert EvidenceEnvelope.weakest().production_supported() is False


# ---------------------------------------------------------------------------
# Zero-qualified state remains valid
# ---------------------------------------------------------------------------


def test_zero_qualified_state_is_valid_and_nonqualifying() -> None:
    adapted = adapt_zero_qualified_state()
    assert adapted.kit.value == "zero_qualified"
    assert adapted.kit.live_qualified_backend_count == 0
    assert adapted.kit.storage_selectable_count == 0
    assert adapted.kit.inventory_production_count == 0
    assert adapted.kit.live_production_count == 0
    assert adapted.kit.zero_qualified_is_valid_honest_state is True
    assert is_nonqualifying(adapted)
    assert adapted.production_supported is False
    assert "zero_qualified_is_valid_honest_state" in adapted.reason_codes
    assert project_to_kit(adapted) == adapted.kit


def test_joined_manifest_summary_zero_qualified() -> None:
    assert MANIFEST_PATH.is_file(), f"missing manifest: {MANIFEST_PATH}"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    summary = manifest["summary"]
    assert summary["production_count"] == 0
    assert summary["live_production_count"] == 0
    assert summary["storage_selectable_count"] == 0

    adapted = adapt_joined_manifest_summary(summary)
    assert adapted.kit.value == "zero_qualified"
    assert adapted.kit.zero_qualified_is_valid_honest_state is True
    assert is_nonqualifying(adapted)
    assert adapted.production_supported is False
    restored = round_trip(adapted.kit)
    assert restored.live_qualified_backend_count == 0
    assert restored.storage_selectable_count == 0


def test_support_matrix_claim_classes_round_trip_against_authority() -> None:
    assert SUPPORT_MATRIX_PATH.is_file()
    matrix = json.loads(SUPPORT_MATRIX_PATH.read_text(encoding="utf-8"))
    classes = set(matrix["claim_classes"])
    assert classes == set(KERNEL_VFS_CLAIM_CLASSES)
    for name in sorted(classes):
        adapted = adapt_kernel_vfs_claim_class(name)
        assert project_to_kit(adapted).value == name
        assert is_nonqualifying(adapted)


def test_live_qualification_summary_round_trip() -> None:
    adapted = adapt_live_qualification_summary(
        live_qualified_backend_count=0,
        storage_selectable_count=0,
        inventory_production_count=0,
        live_production_count=0,
        zero_qualified_is_valid_honest_state=True,
    )
    assert _assert_round_trip(adapted.kit).qualifying is False


def test_adapted_claim_serialization_round_trip_dict() -> None:
    adapted = adapt_zero_qualified_state()
    payload = adapted.to_dict()
    assert payload["schema"] == adapter.SCHEMA
    assert payload["task_id"] == "FACP-015"
    assert payload["unsafe_promotion"] is False
    assert payload["qualifying"] is False
    assert payload["production_supported"] is False
    kit = KitEvidenceRecord.from_dict(payload["kit"])
    envelope = EvidenceEnvelope.from_dimension_map(payload["envelope"])
    again = AdaptedKitClaim(
        kit=kit,
        envelope=envelope,
        qualifying=payload["qualifying"],
        reason_codes=tuple(payload["reason_codes"]),
    )
    assert again.kit == adapted.kit
    assert again.envelope == adapted.envelope


def test_backend_spec_enums_adapt_when_importable() -> None:
    pytest.importorskip("ipfs_kit_py.backends.spec")
    from ipfs_kit_py.backends.provider_adapters import ProviderAvailability
    from ipfs_kit_py.backends.spec import BackendSupportTier

    for tier in BackendSupportTier:
        adapted = adapt_backend_support_tier(tier.value)
        assert project_to_kit(adapted).value == tier.value
        assert is_nonqualifying(adapted)

    for availability in ProviderAvailability:
        adapted = adapt_provider_availability(availability.value)
        assert is_nonqualifying(adapted)
        assert adapted.kit.family is KitDistinctionFamily.CONFIGURED_SELECTED_STATE


def test_all_distinction_families_have_round_trip_coverage() -> None:
    """Guard: every KitDistinctionFamily appears in at least one round-trip."""

    samples = [
        KitEvidenceRecord(
            family=KitDistinctionFamily.KERNEL_VFS_CLAIM_CLASS, value="hermetic"
        ),
        KitEvidenceRecord(
            family=KitDistinctionFamily.BACKEND_SUPPORT_TIER, value="conditional"
        ),
        KitEvidenceRecord(
            family=KitDistinctionFamily.CONFIGURED_SELECTED_STATE, value="absent"
        ),
        KitEvidenceRecord(
            family=KitDistinctionFamily.PROOF_ROLE,
            value="candidate",
            candidate_cid="bafyC",
            authorization_cid="bafyA",
        ),
        KitEvidenceRecord(
            family=KitDistinctionFamily.RECEIPT_FRESHNESS, value="missing"
        ),
        KitEvidenceRecord(
            family=KitDistinctionFamily.CAS_OUTCOME, value="unchanged"
        ),
        KitEvidenceRecord(
            family=KitDistinctionFamily.RECOVERY_DISPOSITION,
            value="rebuilt",
        ),
        KitEvidenceRecord(
            family=KitDistinctionFamily.LIVE_QUALIFICATION_SUMMARY,
            value="zero_qualified",
            live_qualified_backend_count=0,
            storage_selectable_count=0,
            inventory_production_count=0,
            live_production_count=0,
            zero_qualified_is_valid_honest_state=True,
        ),
        KitEvidenceRecord(
            family=KitDistinctionFamily.CAS_IDENTITY,
            value="identity_bound",
            candidate_cid="bafyC",
            authorization_cid="bafyA",
            current_cid="bafyH",
        ),
    ]
    covered = {record.family for record in samples}
    assert covered == set(KitDistinctionFamily)
    for record in samples:
        _assert_round_trip(record)
