"""Fail-closed vectors for campaign state, receipts, gaps, and histories (AAE-035).

Acceptance:

* operation-id replay is deterministic
* transitions are closed
* invalid, unknown-key, wrong-audience/action, or unverified signed receipts
  are rejected before persistence
* completed artifacts survive restart
* partial and ambiguous execution claims cannot become terminal success
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Prefer this worktree's kit package when an outer PYTHONPATH pin is present.
_KIT_ROOT = Path(__file__).resolve().parents[2]
_KIT_PKG = _KIT_ROOT / "ipfs_kit_py"
if sys.path[:1] != [str(_KIT_ROOT)]:
    sys.path.insert(0, str(_KIT_ROOT))
import ipfs_kit_py as _ipfs_kit_py  # noqa: E402

if str(_KIT_PKG) not in list(_ipfs_kit_py.__path__):
    _ipfs_kit_py.__path__.insert(0, str(_KIT_PKG))

from ipfs_datasets_py.logic.software_contracts.adversarial_assurance import (
    AssuranceTerminalStatus,
    HeldOutResult,
    ReceiptAction,
    SignatureVerificationStatus,
)
from tests.adversarial_assurance_store.datasets_test_fixtures import (
    analysis_fixtures,
    receipt_fixtures,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
    cid_for_bytes,
)
from ipfs_kit_py.adversarial_assurance_store.artifacts import (
    DurableAssuranceArtifactStore,
    cid_for_assurance_artifact,
)
from ipfs_kit_py.adversarial_assurance_store.contracts import (
    AssuranceArtifactKind,
    AssuranceNamespaceRole,
    AssuranceStoreStatus,
    assurance_namespace,
)
from ipfs_kit_py.adversarial_assurance_store.campaigns import (
    CAMPAIGN_HISTORY_MANIFEST_INTERFACE,
    CAMPAIGN_HISTORY_MANIFEST_SCHEMA,
    CAMPAIGN_MODULE_INTERFACE,
    CAMPAIGN_STATE_INTERFACE,
    CAMPAIGN_STATE_SCHEMA,
    GAP_MODULE_INTERFACE,
    REQUIRED_RECEIPT_AUDIENCE,
    CampaignAdmissionError,
    CampaignPhase,
    CampaignTransitionError,
    DurableAssuranceGapRepository,
    DurableMutationCampaignRepository,
    ExecutionClaimStatus,
    admit_campaign_receipt_payload,
    assert_phase_transition_allowed,
    build_campaign_state,
    build_history_manifest,
    campaign_phases,
    cid_for_campaign_state,
    cid_for_history_manifest,
    execution_claim_statuses,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


WORKSPACE = "worker-1"
CAMPAIGN_ID = "camp-1"


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "campaign-store"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def artifacts(
    coordination: DurableCoordinationStore,
) -> DurableAssuranceArtifactStore:
    store = DurableAssuranceArtifactStore(coordination)
    yield store
    store.close()


@pytest.fixture()
def campaigns(
    coordination: DurableCoordinationStore,
    artifacts: DurableAssuranceArtifactStore,
) -> DurableMutationCampaignRepository:
    repo = DurableMutationCampaignRepository(coordination, artifacts=artifacts)
    yield repo
    repo.close()


@pytest.fixture()
def gaps(
    coordination: DurableCoordinationStore,
    artifacts: DurableAssuranceArtifactStore,
) -> DurableAssuranceGapRepository:
    repo = DurableAssuranceGapRepository(coordination, artifacts=artifacts)
    yield repo
    repo.close()


def _plan_cid() -> str:
    return cid_for_bytes(b"campaign-plan-block")


def _policy_cid() -> str:
    return cid_for_bytes(b"campaign-policy-block")


def _builder_state(
    *,
    phase: CampaignPhase | str,
    execution_claim_status: ExecutionClaimStatus | str,
    plan_cid: str | None = None,
    policy_cid: str | None = None,
    receipt_cid: str | None = None,
    artifact_cids: list[str] | None = None,
    campaign_id: str = CAMPAIGN_ID,
) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "phase": phase if isinstance(phase, str) else phase.value,
        "execution_claim_status": (
            execution_claim_status
            if isinstance(execution_claim_status, str)
            else execution_claim_status.value
        ),
        "plan_cid": plan_cid if plan_cid is not None else _plan_cid(),
        "policy_cid": policy_cid if policy_cid is not None else _policy_cid(),
        "receipt_cid": receipt_cid,
        "artifact_cids": list(artifact_cids or ()),
    }


def _campaign_payload(**overrides: Any) -> dict[str, Any]:
    return receipt_fixtures._campaign(**overrides).to_dict()


def _unverified_campaign_payload() -> dict[str, Any]:
    return receipt_fixtures._campaign(
        header=receipt_fixtures._header(
            "assurance_campaign_receipt",
            terminal_status=AssuranceTerminalStatus.REJECTED,
        ),
        held_out_result=HeldOutResult.FAILED,
        signature=receipt_fixtures._signature(
            signature_verification_status=SignatureVerificationStatus.UNVERIFIED
        ),
    ).to_dict()


def _wrong_audience_payload() -> dict[str, Any]:
    return receipt_fixtures._campaign(
        signature=receipt_fixtures._signature(audience="other.service")
    ).to_dict()


def _wrong_action_payload() -> dict[str, Any]:
    # Use non-complete terminal so datasets admits the action token, while
    # the store-level closed action gate still rejects promote_policy.
    return receipt_fixtures._campaign(
        header=receipt_fixtures._header(
            "assurance_campaign_receipt",
            terminal_status=AssuranceTerminalStatus.REJECTED,
        ),
        held_out_result=HeldOutResult.FAILED,
        signature=receipt_fixtures._signature(
            action=ReceiptAction.PROMOTE_POLICY,
            signature_verification_status=SignatureVerificationStatus.VERIFIED,
        ),
    ).to_dict()


def _gap_payload() -> dict[str, Any]:
    return analysis_fixtures._gap().to_dict()


def _put_receipt(
    campaigns: DurableMutationCampaignRepository,
    payload: dict[str, Any] | None = None,
    *,
    op_suffix: str = "1",
) -> str:
    body = payload if payload is not None else _campaign_payload()
    sealed = admit_campaign_receipt_payload(body)
    expected = cid_for_assurance_artifact(
        AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT, sealed
    )
    head = campaigns.current_receipts_history(WORKSPACE)
    result = campaigns.persist_campaign_receipt(
        WORKSPACE,
        sealed,
        expected_cid=expected,
        artifact_operation_id=f"receipt-art-{op_suffix}",
        history_operation_id=f"receipt-hist-{op_suffix}",
        expected_history_generation=head.generation,
        expected_history_head_cid=head.head_cid,
        replicate=False,
    )
    assert result.artifact.local_durable is True
    assert result.history.status is AssuranceStoreStatus.UPDATED
    return expected


# ---------------------------------------------------------------------------
# Module surface / closed vocabularies
# ---------------------------------------------------------------------------


def test_module_interfaces_and_closed_vocabularies() -> None:
    assert CAMPAIGN_MODULE_INTERFACE == "MutationCampaignRepository@1"
    assert GAP_MODULE_INTERFACE == "AssuranceGapRepository@1"
    assert CAMPAIGN_STATE_INTERFACE == "MutationCampaignState@1"
    assert CAMPAIGN_STATE_SCHEMA.endswith("@1")
    assert CAMPAIGN_HISTORY_MANIFEST_SCHEMA.endswith("@1")
    assert CAMPAIGN_HISTORY_MANIFEST_INTERFACE.endswith("@1")
    assert REQUIRED_RECEIPT_AUDIENCE == "adversarial_assurance.store"
    assert "planned" in campaign_phases()
    assert "complete" in campaign_phases()
    assert set(execution_claim_statuses()) == {
        "none",
        "partial",
        "complete",
        "ambiguous",
        "failed",
    }


def test_closed_phase_transition_table() -> None:
    assert_phase_transition_allowed(None, CampaignPhase.PLANNED)
    assert_phase_transition_allowed(
        CampaignPhase.PLANNED, CampaignPhase.EXECUTING
    )
    assert_phase_transition_allowed(
        CampaignPhase.EVALUATING, CampaignPhase.COMPLETE
    )
    with pytest.raises(CampaignTransitionError, match="closed transition"):
        assert_phase_transition_allowed(
            CampaignPhase.PLANNED, CampaignPhase.COMPLETE
        )
    with pytest.raises(CampaignTransitionError, match="genesis"):
        assert_phase_transition_allowed(None, CampaignPhase.EXECUTING)
    with pytest.raises(CampaignTransitionError, match="closed transition"):
        assert_phase_transition_allowed(
            CampaignPhase.COMPLETE, CampaignPhase.EXECUTING
        )


def test_build_campaign_state_is_deterministic_and_closed() -> None:
    a = build_campaign_state(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        generation=1,
        phase=CampaignPhase.PLANNED,
        execution_claim_status=ExecutionClaimStatus.NONE,
        plan_cid=_plan_cid(),
        policy_cid=_policy_cid(),
        receipt_cid=None,
        previous_state_cid=None,
        artifact_cids=[],
        operation_id="op-state-1",
        previous_phase=None,
        enforce_transition=True,
    )
    b = build_campaign_state(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        generation=1,
        phase="planned",
        execution_claim_status="none",
        plan_cid=_plan_cid(),
        policy_cid=_policy_cid(),
        receipt_cid=None,
        previous_state_cid=None,
        artifact_cids=[],
        operation_id="op-state-1",
        previous_phase=None,
        enforce_transition=True,
    )
    assert a == b
    assert a["schema"] == CAMPAIGN_STATE_SCHEMA
    assert cid_for_campaign_state(a) == cid_for_campaign_state(b)
    with pytest.raises(CampaignAdmissionError, match="unknown"):
        build_campaign_state(
            workspace=WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            generation=1,
            phase="not-a-phase",
            execution_claim_status=ExecutionClaimStatus.NONE,
            plan_cid=_plan_cid(),
            policy_cid=None,
            receipt_cid=None,
            previous_state_cid=None,
            artifact_cids=[],
            operation_id="op-bad-phase",
        )


def test_history_manifest_rejects_unknown_keys_and_roles() -> None:
    entry = cid_for_bytes(b"hist-entry")
    manifest = build_history_manifest(
        workspace=WORKSPACE,
        role=AssuranceNamespaceRole.RECEIPTS,
        generation=1,
        entry_cid=entry,
        previous_head_cid=None,
        operation_id="hist-1",
    )
    assert manifest["schema"] == CAMPAIGN_HISTORY_MANIFEST_SCHEMA
    assert cid_for_history_manifest(manifest) == cid_for_history_manifest(
        dict(manifest)
    )
    with pytest.raises(CampaignAdmissionError, match="not managed|unknown"):
        build_history_manifest(
            workspace=WORKSPACE,
            role=AssuranceNamespaceRole.POLICY,
            generation=1,
            entry_cid=entry,
            previous_head_cid=None,
            operation_id="hist-policy",
        )
    with pytest.raises(CampaignAdmissionError, match="unknown"):
        build_history_manifest(
            workspace=WORKSPACE,
            role="not-a-role",
            generation=1,
            entry_cid=entry,
            previous_head_cid=None,
            operation_id="hist-bad",
        )


# ---------------------------------------------------------------------------
# Campaign state transitions + idempotent replay
# ---------------------------------------------------------------------------


def test_campaign_state_starts_at_generation_zero(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    head = campaigns.current_campaign_state(WORKSPACE)
    assert head.generation == 0
    assert head.state_cid is None
    assert head.phase is None
    assert head.namespace == assurance_namespace(
        WORKSPACE, AssuranceNamespaceRole.CAMPAIGNS
    )


def test_transition_campaign_state_and_idempotent_replay(
    campaigns: DurableMutationCampaignRepository,
    coordination: DurableCoordinationStore,
) -> None:
    first = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.PLANNED,
            execution_claim_status=ExecutionClaimStatus.NONE,
        ),
        expected_generation=0,
        expected_state_cid=None,
        operation_id="camp-plan-1",
    )
    assert first.status is AssuranceStoreStatus.UPDATED
    assert first.before.generation == 0
    assert first.after.generation == 1
    assert first.after.phase is CampaignPhase.PLANNED
    assert first.after.campaign_id == CAMPAIGN_ID
    assert first.local_durable is True
    assert first.state_cid is not None
    assert first.transition_cid is not None

    verified = campaigns.get_verified_campaign_state(first.state_cid)
    assert verified["phase"] == "planned"
    assert verified["operation_id"] == "camp-plan-1"

    replay = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.PLANNED,
            execution_claim_status=ExecutionClaimStatus.NONE,
        ),
        expected_generation=0,
        expected_state_cid=None,
        operation_id="camp-plan-1",
    )
    assert replay.status is AssuranceStoreStatus.UNCHANGED
    assert replay.reason_code == "idempotent_replay"
    assert replay.after.generation == 1
    assert replay.after.state_cid == first.state_cid
    # Exactly one immutable root transition for this operation.
    rows = campaigns.campaign_state_transitions(WORKSPACE)
    assert len(rows) == 1
    assert rows[0]["operation_id"] == "camp-plan-1"
    assert rows[0]["new_root_cid"] == first.state_cid
    assert coordination.has(first.state_cid) is True


def test_closed_transition_rejection_before_persistence(
    campaigns: DurableMutationCampaignRepository,
    coordination: DurableCoordinationStore,
) -> None:
    planned = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.PLANNED,
            execution_claim_status=ExecutionClaimStatus.NONE,
        ),
        expected_generation=0,
        expected_state_cid=None,
        operation_id="camp-plan-closed",
    )
    # Skip to complete from planned — not in closed table.
    with pytest.raises(CampaignTransitionError, match="closed transition"):
        campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.COMPLETE,
                execution_claim_status=ExecutionClaimStatus.COMPLETE,
                receipt_cid=cid_for_bytes(b"unused-receipt"),
            ),
            expected_generation=1,
            expected_state_cid=planned.state_cid,
            operation_id="camp-skip-complete",
        )
    # No second transition was recorded.
    assert len(campaigns.campaign_state_transitions(WORKSPACE)) == 1


def test_unknown_key_on_state_rejected(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    bad = _builder_state(
        phase=CampaignPhase.PLANNED,
        execution_claim_status=ExecutionClaimStatus.NONE,
    )
    bad["extra_field"] = "nope"
    with pytest.raises(CampaignAdmissionError, match="unknown"):
        campaigns.transition_campaign_state(
            WORKSPACE,
            state=bad,
            expected_generation=0,
            expected_state_cid=None,
            operation_id="camp-unknown-key",
        )


def test_stale_expectation_is_conflict(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    first = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.PLANNED,
            execution_claim_status=ExecutionClaimStatus.NONE,
        ),
        expected_generation=0,
        expected_state_cid=None,
        operation_id="camp-stale-a",
    )
    second = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.EXECUTING,
            execution_claim_status=ExecutionClaimStatus.PARTIAL,
        ),
        expected_generation=1,
        expected_state_cid=first.state_cid,
        operation_id="camp-stale-b",
    )
    assert second.status is AssuranceStoreStatus.UPDATED
    # Stale writer still expecting gen 0.
    conflict = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.PLANNED,
            execution_claim_status=ExecutionClaimStatus.NONE,
            campaign_id="camp-other",
        ),
        expected_generation=0,
        expected_state_cid=None,
        operation_id="camp-stale-c",
    )
    assert conflict.status is AssuranceStoreStatus.CONFLICT
    assert conflict.reason_code == "stale_expectation"
    assert campaigns.current_campaign_state(WORKSPACE).generation == 2


# ---------------------------------------------------------------------------
# Partial / ambiguous cannot become terminal success
# ---------------------------------------------------------------------------


def test_partial_execution_claim_cannot_become_terminal_success(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    receipt_cid = _put_receipt(campaigns, op_suffix="partial")
    planned = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.PLANNED,
            execution_claim_status=ExecutionClaimStatus.NONE,
        ),
        expected_generation=0,
        expected_state_cid=None,
        operation_id="camp-partial-plan",
    )
    executing = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.EXECUTING,
            execution_claim_status=ExecutionClaimStatus.PARTIAL,
        ),
        expected_generation=1,
        expected_state_cid=planned.state_cid,
        operation_id="camp-partial-exec",
    )
    evaluating = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.EVALUATING,
            execution_claim_status=ExecutionClaimStatus.PARTIAL,
        ),
        expected_generation=2,
        expected_state_cid=executing.state_cid,
        operation_id="camp-partial-eval",
    )
    with pytest.raises(
        CampaignTransitionError, match="partial and ambiguous|terminal success"
    ):
        campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.COMPLETE,
                execution_claim_status=ExecutionClaimStatus.PARTIAL,
                receipt_cid=receipt_cid,
            ),
            expected_generation=3,
            expected_state_cid=evaluating.state_cid,
            operation_id="camp-partial-complete",
        )
    assert campaigns.current_campaign_state(WORKSPACE).phase is CampaignPhase.EVALUATING


def test_ambiguous_execution_claim_cannot_become_terminal_success(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    receipt_cid = _put_receipt(campaigns, op_suffix="ambiguous")
    with pytest.raises(
        CampaignTransitionError, match="partial and ambiguous|terminal success"
    ):
        build_campaign_state(
            workspace=WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            generation=4,
            phase=CampaignPhase.COMPLETE,
            execution_claim_status=ExecutionClaimStatus.AMBIGUOUS,
            plan_cid=_plan_cid(),
            policy_cid=_policy_cid(),
            receipt_cid=receipt_cid,
            previous_state_cid=cid_for_bytes(b"prior-state"),
            artifact_cids=[],
            operation_id="op-ambiguous",
            previous_phase=CampaignPhase.EVALUATING,
            enforce_transition=True,
        )


def test_complete_requires_receipt_and_complete_claim(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    planned = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.PLANNED,
            execution_claim_status=ExecutionClaimStatus.NONE,
        ),
        expected_generation=0,
        expected_state_cid=None,
        operation_id="camp-need-receipt-plan",
    )
    executing = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.EXECUTING,
            execution_claim_status=ExecutionClaimStatus.COMPLETE,
        ),
        expected_generation=1,
        expected_state_cid=planned.state_cid,
        operation_id="camp-need-receipt-exec",
    )
    evaluating = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.EVALUATING,
            execution_claim_status=ExecutionClaimStatus.COMPLETE,
        ),
        expected_generation=2,
        expected_state_cid=executing.state_cid,
        operation_id="camp-need-receipt-eval",
    )
    with pytest.raises(CampaignTransitionError, match="receipt_cid"):
        campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.COMPLETE,
                execution_claim_status=ExecutionClaimStatus.COMPLETE,
                receipt_cid=None,
            ),
            expected_generation=3,
            expected_state_cid=evaluating.state_cid,
            operation_id="camp-need-receipt-complete",
        )


def test_happy_path_to_terminal_success_with_receipt(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    receipt_cid = _put_receipt(campaigns, op_suffix="success")
    planned = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.PLANNED,
            execution_claim_status=ExecutionClaimStatus.NONE,
        ),
        expected_generation=0,
        expected_state_cid=None,
        operation_id="camp-ok-plan",
    )
    executing = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.EXECUTING,
            execution_claim_status=ExecutionClaimStatus.COMPLETE,
        ),
        expected_generation=1,
        expected_state_cid=planned.state_cid,
        operation_id="camp-ok-exec",
    )
    evaluating = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.EVALUATING,
            execution_claim_status=ExecutionClaimStatus.COMPLETE,
        ),
        expected_generation=2,
        expected_state_cid=executing.state_cid,
        operation_id="camp-ok-eval",
    )
    complete = campaigns.transition_campaign_state(
        WORKSPACE,
        state=_builder_state(
            phase=CampaignPhase.COMPLETE,
            execution_claim_status=ExecutionClaimStatus.COMPLETE,
            receipt_cid=receipt_cid,
        ),
        expected_generation=3,
        expected_state_cid=evaluating.state_cid,
        operation_id="camp-ok-complete",
    )
    assert complete.status is AssuranceStoreStatus.UPDATED
    assert complete.after.phase is CampaignPhase.COMPLETE
    assert complete.after.receipt_cid == receipt_cid
    assert complete.after.execution_claim_status is ExecutionClaimStatus.COMPLETE
    history = campaigns.campaign_state_history_cids(WORKSPACE)
    assert len(history) == 4
    assert history[-1] == complete.state_cid


# ---------------------------------------------------------------------------
# Receipt admission: signature, audience, action, unknown keys
# ---------------------------------------------------------------------------


def test_unverified_receipt_rejected_before_persistence(
    campaigns: DurableMutationCampaignRepository,
    coordination: DurableCoordinationStore,
) -> None:
    payload = _unverified_campaign_payload()
    with pytest.raises(CampaignAdmissionError, match="signature|unverified"):
        admit_campaign_receipt_payload(payload)
    head = campaigns.current_receipts_history(WORKSPACE)
    with pytest.raises(CampaignAdmissionError, match="signature|unverified"):
        campaigns.persist_campaign_receipt(
            WORKSPACE,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            artifact_operation_id="art-unverified",
            history_operation_id="hist-unverified",
            expected_history_generation=head.generation,
            expected_history_head_cid=head.head_cid,
            replicate=False,
        )
    assert campaigns.current_receipts_history(WORKSPACE).generation == 0
    from ipfs_datasets_py.logic.software_contracts.adversarial_assurance import (
        AssuranceCampaignReceipt,
    )

    receipt_cid = AssuranceCampaignReceipt.from_dict(payload).receipt_cid
    assert coordination.has(receipt_cid) is False


def test_wrong_audience_receipt_rejected_before_persistence(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    payload = _wrong_audience_payload()
    with pytest.raises(CampaignAdmissionError, match="wrong-audience|audience"):
        admit_campaign_receipt_payload(payload)
    head = campaigns.current_receipts_history(WORKSPACE)
    with pytest.raises(CampaignAdmissionError, match="wrong-audience|audience"):
        campaigns.persist_campaign_receipt(
            WORKSPACE,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            artifact_operation_id="art-audience",
            history_operation_id="hist-audience",
            expected_history_generation=head.generation,
            expected_history_head_cid=head.head_cid,
            replicate=False,
        )
    assert campaigns.current_receipts_history(WORKSPACE).generation == 0


def test_wrong_action_receipt_rejected_before_persistence(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    payload = _wrong_action_payload()
    with pytest.raises(CampaignAdmissionError, match="wrong-action|action"):
        admit_campaign_receipt_payload(payload)
    head = campaigns.current_receipts_history(WORKSPACE)
    with pytest.raises(CampaignAdmissionError, match="wrong-action|action"):
        campaigns.persist_campaign_receipt(
            WORKSPACE,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            artifact_operation_id="art-action",
            history_operation_id="hist-action",
            expected_history_generation=head.generation,
            expected_history_head_cid=head.head_cid,
            replicate=False,
        )
    assert campaigns.current_receipts_history(WORKSPACE).generation == 0


def test_invalid_unknown_key_receipt_rejected(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    payload = _campaign_payload()
    payload["not_a_receipt_field"] = "x"
    with pytest.raises(CampaignAdmissionError):
        admit_campaign_receipt_payload(payload)
    head = campaigns.current_receipts_history(WORKSPACE)
    with pytest.raises(CampaignAdmissionError):
        campaigns.persist_campaign_receipt(
            WORKSPACE,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            artifact_operation_id="art-unknown",
            history_operation_id="hist-unknown",
            expected_history_generation=head.generation,
            expected_history_head_cid=head.head_cid,
            replicate=False,
        )


def test_verified_receipt_persist_and_history_replay(
    campaigns: DurableMutationCampaignRepository,
) -> None:
    payload = _campaign_payload()
    sealed = admit_campaign_receipt_payload(payload)
    expected = cid_for_assurance_artifact(
        AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT, sealed
    )
    head = campaigns.current_receipts_history(WORKSPACE)
    first = campaigns.persist_campaign_receipt(
        WORKSPACE,
        sealed,
        expected_cid=expected,
        artifact_operation_id="art-receipt-ok",
        history_operation_id="hist-receipt-ok",
        expected_history_generation=head.generation,
        expected_history_head_cid=head.head_cid,
        replicate=False,
    )
    assert first.history.status is AssuranceStoreStatus.UPDATED
    assert first.receipt_cid == expected
    verified = campaigns.get_verified_receipt(expected)
    assert dict(verified) == sealed
    assert (
        verified["signature"]["signature_verification_status"] == "verified"
    )
    assert verified["signature"]["audience"] == REQUIRED_RECEIPT_AUDIENCE

    # Idempotent artifact + history operation replay.
    head2 = campaigns.current_receipts_history(WORKSPACE)
    replay = campaigns.persist_campaign_receipt(
        WORKSPACE,
        sealed,
        expected_cid=expected,
        artifact_operation_id="art-receipt-ok",
        history_operation_id="hist-receipt-ok",
        expected_history_generation=0,
        expected_history_head_cid=None,
        replicate=False,
    )
    assert replay.artifact.reason_code == "unchanged"
    assert replay.history.status is AssuranceStoreStatus.UNCHANGED
    assert replay.history.reason_code == "idempotent_replay"
    assert campaigns.receipt_history_entry_cids(WORKSPACE) == [expected]
    assert head2.generation == 1


# ---------------------------------------------------------------------------
# Gaps repository
# ---------------------------------------------------------------------------


def test_persist_gap_and_idempotent_history(
    gaps: DurableAssuranceGapRepository,
) -> None:
    payload = _gap_payload()
    expected = cid_for_assurance_artifact(
        AssuranceArtifactKind.ASSURANCE_GAP, payload
    )
    head = gaps.current_gaps_history(WORKSPACE)
    first = gaps.persist_gap(
        WORKSPACE,
        payload,
        expected_cid=expected,
        artifact_operation_id="gap-art-1",
        history_operation_id="gap-hist-1",
        expected_history_generation=head.generation,
        expected_history_head_cid=head.head_cid,
        replicate=False,
    )
    assert first.history.status is AssuranceStoreStatus.UPDATED
    assert first.gap_cid == expected
    verified = gaps.get_verified_gap(expected)
    assert dict(verified) == payload

    replay = gaps.persist_gap(
        WORKSPACE,
        payload,
        expected_cid=expected,
        artifact_operation_id="gap-art-1",
        history_operation_id="gap-hist-1",
        expected_history_generation=0,
        expected_history_head_cid=None,
        replicate=False,
    )
    assert replay.artifact.reason_code == "unchanged"
    assert replay.history.status is AssuranceStoreStatus.UNCHANGED
    assert gaps.gap_history_entry_cids(WORKSPACE) == [expected]


def test_invalid_gap_payload_rejected_before_persistence(
    gaps: DurableAssuranceGapRepository,
    coordination: DurableCoordinationStore,
) -> None:
    payload = _gap_payload()
    payload["unknown_gap_key"] = True
    head = gaps.current_gaps_history(WORKSPACE)
    with pytest.raises(CampaignAdmissionError):
        gaps.persist_gap(
            WORKSPACE,
            payload,
            expected_cid=cid_for_bytes(b"unused"),
            artifact_operation_id="gap-bad",
            history_operation_id="gap-bad-hist",
            expected_history_generation=head.generation,
            expected_history_head_cid=head.head_cid,
            replicate=False,
        )
    assert gaps.current_gaps_history(WORKSPACE).generation == 0


# ---------------------------------------------------------------------------
# Restart survival
# ---------------------------------------------------------------------------


def test_completed_artifacts_survive_restart(store_dir: Path) -> None:
    payload = _campaign_payload()
    sealed = admit_campaign_receipt_payload(payload)
    expected_receipt = cid_for_assurance_artifact(
        AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT, sealed
    )
    gap_body = _gap_payload()
    expected_gap = cid_for_assurance_artifact(
        AssuranceArtifactKind.ASSURANCE_GAP, gap_body
    )

    with DurableCoordinationStore(store_dir) as coordination:
        with DurableAssuranceArtifactStore(coordination) as artifacts:
            with DurableMutationCampaignRepository(
                coordination, artifacts=artifacts
            ) as campaigns:
                with DurableAssuranceGapRepository(
                    coordination, artifacts=artifacts
                ) as gaps:
                    head = campaigns.current_receipts_history(WORKSPACE)
                    campaigns.persist_campaign_receipt(
                        WORKSPACE,
                        sealed,
                        expected_cid=expected_receipt,
                        artifact_operation_id="restart-receipt-art",
                        history_operation_id="restart-receipt-hist",
                        expected_history_generation=head.generation,
                        expected_history_head_cid=head.head_cid,
                        replicate=False,
                    )
                    planned = campaigns.transition_campaign_state(
                        WORKSPACE,
                        state=_builder_state(
                            phase=CampaignPhase.PLANNED,
                            execution_claim_status=ExecutionClaimStatus.NONE,
                        ),
                        expected_generation=0,
                        expected_state_cid=None,
                        operation_id="restart-plan",
                    )
                    executing = campaigns.transition_campaign_state(
                        WORKSPACE,
                        state=_builder_state(
                            phase=CampaignPhase.EXECUTING,
                            execution_claim_status=ExecutionClaimStatus.COMPLETE,
                        ),
                        expected_generation=1,
                        expected_state_cid=planned.state_cid,
                        operation_id="restart-exec",
                    )
                    evaluating = campaigns.transition_campaign_state(
                        WORKSPACE,
                        state=_builder_state(
                            phase=CampaignPhase.EVALUATING,
                            execution_claim_status=ExecutionClaimStatus.COMPLETE,
                        ),
                        expected_generation=2,
                        expected_state_cid=executing.state_cid,
                        operation_id="restart-eval",
                    )
                    complete = campaigns.transition_campaign_state(
                        WORKSPACE,
                        state=_builder_state(
                            phase=CampaignPhase.COMPLETE,
                            execution_claim_status=ExecutionClaimStatus.COMPLETE,
                            receipt_cid=expected_receipt,
                        ),
                        expected_generation=3,
                        expected_state_cid=evaluating.state_cid,
                        operation_id="restart-complete",
                    )
                    gap_head = gaps.current_gaps_history(WORKSPACE)
                    gaps.persist_gap(
                        WORKSPACE,
                        gap_body,
                        expected_cid=expected_gap,
                        artifact_operation_id="restart-gap-art",
                        history_operation_id="restart-gap-hist",
                        expected_history_generation=gap_head.generation,
                        expected_history_head_cid=gap_head.head_cid,
                        replicate=False,
                    )
                    state_cid = complete.state_cid
                    assert state_cid is not None

    # Reopen: campaign state, receipt, gap, and histories must re-verify.
    with DurableCoordinationStore(store_dir) as coordination:
        with DurableAssuranceArtifactStore(coordination) as artifacts:
            with DurableMutationCampaignRepository(
                coordination, artifacts=artifacts
            ) as campaigns:
                with DurableAssuranceGapRepository(
                    coordination, artifacts=artifacts
                ) as gaps:
                    head = campaigns.current_campaign_state(WORKSPACE)
                    assert head.generation == 4
                    assert head.phase is CampaignPhase.COMPLETE
                    assert head.receipt_cid == expected_receipt
                    assert head.state_cid == state_cid
                    assert dict(campaigns.get_verified_receipt(expected_receipt)) == sealed
                    assert dict(gaps.get_verified_gap(expected_gap)) == gap_body
                    assert campaigns.receipt_history_entry_cids(WORKSPACE) == [
                        expected_receipt
                    ]
                    assert gaps.gap_history_entry_cids(WORKSPACE) == [expected_gap]
                    assert len(campaigns.campaign_state_transitions(WORKSPACE)) == 4
