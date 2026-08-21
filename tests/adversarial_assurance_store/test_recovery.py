"""Crash recovery, idempotent replay, and concurrency fencing (AAE-038).

Acceptance:

* Injected interruptions at every required persistence/CAS boundary resume
  safely
* Immutable completions are preserved
* Ambiguity is rejected
* Partial promotion is avoided
* Stale writers are prevented
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
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
    SignatureVerificationStatus,
)
from tests.adversarial_assurance_store.datasets_test_fixtures import receipt_fixtures
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    DurableCoordinationStore,
    ROOT_CAS_INTERRUPTION_POINTS,
    cid_for_artifact,
    cid_for_bytes,
)
from ipfs_kit_py.adversarial_assurance_store.artifacts import (
    DurableAssuranceArtifactStore,
    cid_for_assurance_artifact,
)
from ipfs_kit_py.adversarial_assurance_store.campaigns import (
    CampaignPhase,
    CampaignTransitionError,
    DurableMutationCampaignRepository,
    ExecutionClaimStatus,
    admit_campaign_receipt_payload,
    assert_terminal_success_admissible,
)
from ipfs_kit_py.adversarial_assurance_store.contracts import (
    AssuranceArtifactKind,
    AssuranceStoreStatus,
)
from ipfs_kit_py.adversarial_assurance_store.merkle import (
    DurableAssuranceCampaignMerkleRepository,
    MerkleSetKind,
    build_merkle_set_commitment,
    cid_for_merkle_set,
)
from ipfs_kit_py.adversarial_assurance_store.policy import (
    DurableAssurancePolicyRepository,
)
from ipfs_kit_py.adversarial_assurance_store.recovery import (
    ASSURANCE_RECOVERY_INTERFACE,
    ASSURANCE_RECOVERY_REPORT_INTERFACE,
    ASSURANCE_RECOVERY_SCHEMA,
    MAX_RECOVERY_ERRORS,
    REQUIRED_CAS_INTERRUPTION_POINTS,
    AssuranceRecoveryAdmissionError,
    AssuranceRecoveryReport,
    DurableAssuranceRecovery,
    assert_terminal_claim_not_ambiguous,
    assert_writer_fence,
    recover_assurance_campaigns,
)


WORKSPACE = "worker-1"
CAMPAIGN_ID = "camp-1"

_PRE_DURABLE_BOUNDARIES = frozenset(
    {"before_transaction", "after_expectation_verification"}
)


class InjectedInterruption(RuntimeError):
    """Stand-in for a process stopping at a durable CAS boundary."""


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _block(store: DurableCoordinationStore, name: str, **extra: Any) -> str:
    payload = {"schema": "example/assurance-recovery@1", "name": name}
    payload.update(extra)
    return store.put(payload, expected_cid=cid_for_artifact(payload), replicate=False)[
        "cid"
    ]


def _plan_cid() -> str:
    return cid_for_bytes(b"campaign-plan-block")


def _policy_plan_cid() -> str:
    return cid_for_bytes(b"campaign-policy-block")


def _builder_state(
    *,
    phase: CampaignPhase | str,
    execution_claim_status: ExecutionClaimStatus | str,
    receipt_cid: str | None = None,
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
        "plan_cid": _plan_cid(),
        "policy_cid": _policy_plan_cid(),
        "receipt_cid": receipt_cid,
        "artifact_cids": [],
    }


def _campaign_payload(**overrides: Any) -> dict[str, Any]:
    return receipt_fixtures._campaign(**overrides).to_dict()


def _put_receipt(
    campaigns: DurableMutationCampaignRepository,
    *,
    op_suffix: str = "1",
) -> str:
    sealed = admit_campaign_receipt_payload(_campaign_payload())
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
    return expected


def _put_leaf(store: DurableCoordinationStore, label: str) -> str:
    payload = {"schema": "example/merkle-leaf@1", "label": label}
    return store.put(payload, expected_cid=cid_for_artifact(payload), replicate=False)[
        "cid"
    ]


def _commit_all_sets(
    merkle: DurableAssuranceCampaignMerkleRepository,
    coordination: DurableCoordinationStore,
) -> dict[str, str]:
    set_cids: dict[str, str] = {}
    for kind in MerkleSetKind:
        members = [
            _put_leaf(coordination, f"{kind.value}-a"),
            _put_leaf(coordination, f"{kind.value}-b"),
        ]
        sealed = build_merkle_set_commitment(
            workspace=WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            set_kind=kind,
            member_cids=members,
            operation_id=f"set-op-{kind.value}",
        )
        expected = cid_for_merkle_set(sealed)
        result = merkle.commit_merkle_set(
            WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            set_kind=kind,
            member_cids=members,
            expected_cid=expected,
            operation_id=f"set-op-{kind.value}",
        )
        assert result.local_durable is True
        set_cids[kind.value] = expected
    return set_cids


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_module_interfaces_and_required_boundaries() -> None:
    assert ASSURANCE_RECOVERY_INTERFACE == "AssuranceRecovery@1"
    assert ASSURANCE_RECOVERY_REPORT_INTERFACE == "AssuranceRecoveryReport@1"
    assert ASSURANCE_RECOVERY_SCHEMA.endswith("@1")
    assert REQUIRED_CAS_INTERRUPTION_POINTS == ROOT_CAS_INTERRUPTION_POINTS
    assert len(REQUIRED_CAS_INTERRUPTION_POINTS) == 6
    assert MAX_RECOVERY_ERRORS == 32


def test_recovery_report_round_trip_and_closed_errors() -> None:
    report = AssuranceRecoveryReport(
        verified_blocks=3,
        reconstructed_campaign_heads=(),
        reconstructed_history_heads=(),
        reconstructed_merkle_heads=(),
        reconstructed_policy_heads=(),
        reconstructed_promotion_heads=(),
        ignored_idempotent_transitions=(),
        errors=({"code": "corrupt", "message": "block mismatch"},),
    )
    assert AssuranceRecoveryReport.from_dict(report.to_dict()).to_dict() == (
        report.to_dict()
    )
    with pytest.raises(Exception):
        AssuranceRecoveryReport(
            verified_blocks=-1,
            reconstructed_campaign_heads=(),
            reconstructed_history_heads=(),
            reconstructed_merkle_heads=(),
            reconstructed_policy_heads=(),
            reconstructed_promotion_heads=(),
            ignored_idempotent_transitions=(),
            errors=(),
        )
    with pytest.raises(Exception):
        AssuranceRecoveryReport(
            verified_blocks=0,
            reconstructed_campaign_heads=(),
            reconstructed_history_heads=(),
            reconstructed_merkle_heads=(),
            reconstructed_policy_heads=(),
            reconstructed_promotion_heads=(),
            ignored_idempotent_transitions=(),
            errors=({"code": "Not-Normalized", "message": "bad"},),
        )


def test_writer_fence_rejects_stale_expectation() -> None:
    assert_writer_fence(
        expected_generation=1,
        expected_head_cid=cid_for_bytes(b"head-a"),
        current_generation=1,
        current_head_cid=cid_for_bytes(b"head-a"),
    )
    with pytest.raises(AssuranceRecoveryAdmissionError, match="stale writer"):
        assert_writer_fence(
            expected_generation=0,
            expected_head_cid=None,
            current_generation=1,
            current_head_cid=cid_for_bytes(b"head-a"),
        )
    with pytest.raises(AssuranceRecoveryAdmissionError, match="stale writer"):
        assert_writer_fence(
            expected_generation=1,
            expected_head_cid=cid_for_bytes(b"head-a"),
            current_generation=1,
            current_head_cid=cid_for_bytes(b"head-b"),
        )


def test_ambiguous_and_partial_terminal_claims_rejected() -> None:
    with pytest.raises(AssuranceRecoveryAdmissionError, match="partial|ambiguous"):
        assert_terminal_claim_not_ambiguous(
            phase=CampaignPhase.COMPLETE,
            execution_claim_status=ExecutionClaimStatus.PARTIAL,
            receipt_cid=cid_for_bytes(b"receipt"),
        )
    with pytest.raises(AssuranceRecoveryAdmissionError, match="partial|ambiguous"):
        assert_terminal_claim_not_ambiguous(
            phase=CampaignPhase.COMPLETE,
            execution_claim_status=ExecutionClaimStatus.AMBIGUOUS,
            receipt_cid=cid_for_bytes(b"receipt"),
        )
    with pytest.raises(CampaignTransitionError):
        assert_terminal_success_admissible(
            phase=CampaignPhase.COMPLETE,
            execution_claim_status=ExecutionClaimStatus.AMBIGUOUS,
            receipt_cid=cid_for_bytes(b"receipt"),
        )


# ---------------------------------------------------------------------------
# CAS interruption matrix: campaign state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("boundary", REQUIRED_CAS_INTERRUPTION_POINTS)
def test_campaign_cas_interruption_resumes_safely(
    tmp_path: Path, boundary: str
) -> None:
    root = tmp_path / f"campaign-{boundary}"

    def interrupt(point: str) -> None:
        if point == boundary:
            raise InjectedInterruption(point)

    with DurableCoordinationStore(root) as setup:
        campaigns = DurableMutationCampaignRepository(setup)
        planned = campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.PLANNED,
                execution_claim_status=ExecutionClaimStatus.NONE,
            ),
            expected_generation=0,
            expected_state_cid=None,
            operation_id="camp-seed-plan",
        )
        assert planned.status is AssuranceStoreStatus.UPDATED
        seed_cid = planned.state_cid
        assert seed_cid is not None

    with DurableCoordinationStore(root, crash_injector=interrupt) as store:
        campaigns = DurableMutationCampaignRepository(store)
        with pytest.raises(InjectedInterruption, match=boundary):
            campaigns.transition_campaign_state(
                WORKSPACE,
                state=_builder_state(
                    phase=CampaignPhase.EXECUTING,
                    execution_claim_status=ExecutionClaimStatus.COMPLETE,
                ),
                expected_generation=1,
                expected_state_cid=seed_cid,
                operation_id="camp-interrupted-exec",
            )

    with DurableCoordinationStore(root) as recovered:
        report = recover_assurance_campaigns(recovered)
        assert report.verified_blocks >= 1
        campaigns = DurableMutationCampaignRepository(recovered)
        head = campaigns.current_campaign_state(WORKSPACE)
        if boundary in _PRE_DURABLE_BOUNDARIES:
            assert head.generation == 1
            assert head.state_cid == seed_cid
            assert head.phase is CampaignPhase.PLANNED
        else:
            assert head.generation == 2
            assert head.phase is CampaignPhase.EXECUTING
            assert any(
                item.state_cid == head.state_cid
                for item in report.reconstructed_campaign_heads
            )

        replay = campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.EXECUTING,
                execution_claim_status=ExecutionClaimStatus.COMPLETE,
            ),
            expected_generation=1,
            expected_state_cid=seed_cid,
            operation_id="camp-interrupted-exec",
        )
        if boundary in _PRE_DURABLE_BOUNDARIES:
            assert replay.status is AssuranceStoreStatus.UPDATED
        else:
            assert replay.status is AssuranceStoreStatus.UNCHANGED
            assert replay.reason_code == "idempotent_replay"
        assert campaigns.current_campaign_state(WORKSPACE).generation == 2


# ---------------------------------------------------------------------------
# CAS interruption matrix: policy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("boundary", REQUIRED_CAS_INTERRUPTION_POINTS)
def test_policy_cas_interruption_resumes_safely(
    tmp_path: Path, boundary: str
) -> None:
    root = tmp_path / f"policy-{boundary}"

    def interrupt(point: str) -> None:
        if point == boundary:
            raise InjectedInterruption(point)

    with DurableCoordinationStore(root) as setup:
        successor = _block(setup, f"policy-{boundary}")

    with DurableCoordinationStore(root, crash_injector=interrupt) as store:
        policy = DurableAssurancePolicyRepository(store)
        with pytest.raises(InjectedInterruption, match=boundary):
            policy.compare_and_swap_policy(
                WORKSPACE,
                expected_generation=0,
                expected_policy_cid=None,
                new_policy_cid=successor,
                operation_id="policy-interrupted",
            )

    with DurableCoordinationStore(root) as recovered:
        report = DurableAssuranceRecovery(recovered).recover_assurance_campaigns()
        policy = DurableAssurancePolicyRepository(recovered)
        head = policy.current_policy(WORKSPACE)
        if boundary in _PRE_DURABLE_BOUNDARIES:
            assert head.generation == 0
            assert head.policy_cid is None
            assert report.reconstructed_policy_heads == ()
        else:
            assert head.generation == 1
            assert head.policy_cid == successor
            assert any(
                item.policy_cid == successor
                for item in report.reconstructed_policy_heads
            )

        # Immutable successor block survived regardless of CAS commit.
        assert recovered.has(successor) is True

        replay = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=successor,
            operation_id="policy-interrupted",
        )
        expected_status = (
            AssuranceStoreStatus.UPDATED
            if boundary in _PRE_DURABLE_BOUNDARIES
            else AssuranceStoreStatus.UNCHANGED
        )
        assert replay.status is expected_status
        assert policy.current_policy(WORKSPACE).generation == 1
        assert policy.current_policy(WORKSPACE).policy_cid == successor


# ---------------------------------------------------------------------------
# CAS interruption matrix: promotion (no partial promotion)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("boundary", REQUIRED_CAS_INTERRUPTION_POINTS)
def test_promote_policy_interruption_avoids_partial_promotion(
    tmp_path: Path, boundary: str
) -> None:
    root = tmp_path / f"promote-{boundary}"

    def interrupt(point: str) -> None:
        if point == boundary:
            raise InjectedInterruption(point)

    with DurableCoordinationStore(root) as setup:
        candidate = _block(setup, "cand")
        evaluation = _block(setup, "eval")
        auth = _block(setup, "auth")
        policy_cid = _block(setup, f"promo-policy-{boundary}")

    with DurableCoordinationStore(root, crash_injector=interrupt) as store:
        policy = DurableAssurancePolicyRepository(store)
        with pytest.raises(InjectedInterruption, match=boundary):
            policy.promote_policy(
                WORKSPACE,
                expected_generation=0,
                expected_policy_cid=None,
                new_policy_cid=policy_cid,
                operation_id="promote-interrupted",
                candidate_cid=candidate,
                evaluation_cid=evaluation,
                authorization_cid=auth,
            )

    with DurableCoordinationStore(root) as recovered:
        report = recover_assurance_campaigns(recovered)
        policy = DurableAssurancePolicyRepository(recovered)
        policy_head = policy.current_policy(WORKSPACE)
        promotion_head = policy.current_promotion(WORKSPACE)

        # promote_policy only CAS-es the policy head.  Promotion-state remains
        # at generation zero unless a separate promotion CAS ran — recovery
        # must not invent a completed promotion head.
        assert promotion_head.generation == 0
        assert promotion_head.promotion_cid is None
        assert report.reconstructed_promotion_heads == ()

        if boundary in _PRE_DURABLE_BOUNDARIES:
            assert policy_head.generation == 0
            assert policy_head.policy_cid is None
        else:
            assert policy_head.generation == 1
            assert policy_head.policy_cid == policy_cid

        replay = policy.promote_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=policy_cid,
            operation_id="promote-interrupted",
            candidate_cid=candidate,
            evaluation_cid=evaluation,
            authorization_cid=auth,
        )
        if boundary in _PRE_DURABLE_BOUNDARIES:
            assert replay.status is AssuranceStoreStatus.UPDATED
        else:
            assert replay.status is AssuranceStoreStatus.UNCHANGED
            assert replay.reason_code == "idempotent_replay"
        assert policy.current_policy(WORKSPACE).generation == 1
        # Still no invented promotion-state head.
        assert policy.current_promotion(WORKSPACE).generation == 0


# ---------------------------------------------------------------------------
# CAS interruption matrix: Merkle root
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("boundary", REQUIRED_CAS_INTERRUPTION_POINTS)
def test_merkle_cas_interruption_resumes_safely(
    tmp_path: Path, boundary: str
) -> None:
    root = tmp_path / f"merkle-{boundary}"

    def interrupt(point: str) -> None:
        if point == boundary:
            raise InjectedInterruption(point)

    with DurableCoordinationStore(root) as setup:
        artifacts = DurableAssuranceArtifactStore(setup)
        merkle = DurableAssuranceCampaignMerkleRepository(setup, artifacts=artifacts)
        set_cids = _commit_all_sets(merkle, setup)
        artifacts.close()

    with DurableCoordinationStore(root, crash_injector=interrupt) as store:
        artifacts = DurableAssuranceArtifactStore(store)
        merkle = DurableAssuranceCampaignMerkleRepository(store, artifacts=artifacts)
        with pytest.raises(InjectedInterruption, match=boundary):
            merkle.commit_campaign_roots(
                WORKSPACE,
                campaign_id=CAMPAIGN_ID,
                set_commitments=set_cids,
                expected_generation=0,
                expected_root_cid=None,
                operation_id="merkle-interrupted",
            )
        artifacts.close()

    with DurableCoordinationStore(root) as recovered:
        report = recover_assurance_campaigns(recovered)
        artifacts = DurableAssuranceArtifactStore(recovered)
        merkle = DurableAssuranceCampaignMerkleRepository(
            recovered, artifacts=artifacts
        )
        try:
            head = merkle.current_merkle_root(WORKSPACE)
            if boundary in _PRE_DURABLE_BOUNDARIES:
                assert head.generation == 0
                assert head.root_cid is None
            else:
                assert head.generation == 1
                assert head.required_set_completeness is True
                assert any(
                    item.root_cid == head.root_cid
                    for item in report.reconstructed_merkle_heads
                )

            replay = merkle.commit_campaign_roots(
                WORKSPACE,
                campaign_id=CAMPAIGN_ID,
                set_commitments=set_cids,
                expected_generation=0,
                expected_root_cid=None,
                operation_id="merkle-interrupted",
            )
            if boundary in _PRE_DURABLE_BOUNDARIES:
                assert replay.status is AssuranceStoreStatus.UPDATED
            else:
                assert replay.status is AssuranceStoreStatus.UNCHANGED
            assert merkle.current_merkle_root(WORKSPACE).generation == 1
        finally:
            artifacts.close()


# ---------------------------------------------------------------------------
# Immutable completion survival + full recovery projection
# ---------------------------------------------------------------------------


def test_completed_campaign_survives_restart_and_recovery(tmp_path: Path) -> None:
    root = tmp_path / "complete-survive"
    with DurableCoordinationStore(root) as store:
        artifacts = DurableAssuranceArtifactStore(store)
        campaigns = DurableMutationCampaignRepository(store, artifacts=artifacts)
        policy = DurableAssurancePolicyRepository(store)
        receipt_cid = _put_receipt(campaigns, op_suffix="complete")

        planned = campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.PLANNED,
                execution_claim_status=ExecutionClaimStatus.NONE,
            ),
            expected_generation=0,
            expected_state_cid=None,
            operation_id="ok-plan",
        )
        executing = campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.EXECUTING,
                execution_claim_status=ExecutionClaimStatus.COMPLETE,
            ),
            expected_generation=1,
            expected_state_cid=planned.state_cid,
            operation_id="ok-exec",
        )
        evaluating = campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.EVALUATING,
                execution_claim_status=ExecutionClaimStatus.COMPLETE,
            ),
            expected_generation=2,
            expected_state_cid=executing.state_cid,
            operation_id="ok-eval",
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
            operation_id="ok-complete",
        )
        assert complete.status is AssuranceStoreStatus.UPDATED

        policy_cid = _block(store, "policy-live")
        promo = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=policy_cid,
            operation_id="policy-live",
        )
        assert promo.status is AssuranceStoreStatus.UPDATED
        artifacts.close()

    with DurableCoordinationStore(root) as recovered:
        report = recover_assurance_campaigns(recovered)
        assert report.errors == ()
        assert len(report.reconstructed_campaign_heads) == 1
        camp = report.reconstructed_campaign_heads[0]
        assert camp.phase is CampaignPhase.COMPLETE
        assert camp.receipt_cid == receipt_cid
        assert camp.execution_claim_status is ExecutionClaimStatus.COMPLETE
        assert len(report.reconstructed_history_heads) == 1
        assert report.reconstructed_history_heads[0].role.value == "receipts"
        assert len(report.reconstructed_policy_heads) == 1
        assert report.reconstructed_policy_heads[0].policy_cid == policy_cid

        artifacts = DurableAssuranceArtifactStore(recovered)
        try:
            verified = artifacts.get_verified_artifact(
                receipt_cid,
                expected_kind=AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT,
            )
            assert verified["receipt_cid"] == receipt_cid or "header" in verified
        finally:
            artifacts.close()


def test_stale_writer_cannot_overwrite_after_recovery(tmp_path: Path) -> None:
    root = tmp_path / "stale-after-recovery"
    with DurableCoordinationStore(root) as store:
        policy = DurableAssurancePolicyRepository(store)
        first = _block(store, "p1")
        second = _block(store, "p2")
        third = _block(store, "p3")
        updated = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=first,
            operation_id="p-1",
        )
        assert updated.status is AssuranceStoreStatus.UPDATED

    with DurableCoordinationStore(root) as recovered:
        report = recover_assurance_campaigns(recovered)
        assert len(report.reconstructed_policy_heads) == 1
        policy = DurableAssurancePolicyRepository(recovered)
        head = policy.current_policy(WORKSPACE)
        with pytest.raises(AssuranceRecoveryAdmissionError, match="stale writer"):
            assert_writer_fence(
                expected_generation=0,
                expected_head_cid=None,
                current_generation=head.generation,
                current_head_cid=head.policy_cid,
            )
        stale = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=second,
            operation_id="p-stale",
        )
        assert stale.status is AssuranceStoreStatus.CONFLICT
        assert stale.reason_code == "stale_expectation"
        assert policy.current_policy(WORKSPACE).policy_cid == first

        advanced = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=1,
            expected_policy_cid=first,
            new_policy_cid=third,
            operation_id="p-2",
        )
        assert advanced.status is AssuranceStoreStatus.UPDATED
        assert policy.current_policy(WORKSPACE).policy_cid == third


def test_concurrent_writers_yield_at_most_one_success_after_recovery(
    tmp_path: Path,
) -> None:
    root = tmp_path / "concurrent-fence"
    with DurableCoordinationStore(root) as setup:
        one = _block(setup, "c1")
        two = _block(setup, "c2")
        # Seed an unrelated namespace so recovery has blocks to verify.
        seed = _block(setup, "seed")
        DurableAssurancePolicyRepository(setup).compare_and_swap_policy(
            "seed-ws",
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=seed,
            operation_id="seed-op",
        )

    with DurableCoordinationStore(root) as recovered:
        recover_assurance_campaigns(recovered)

    def attempt(cid: str, operation_id: str) -> str:
        with DurableCoordinationStore(root) as store:
            policy = DurableAssurancePolicyRepository(store)
            result = policy.compare_and_swap_policy(
                WORKSPACE,
                expected_generation=0,
                expected_policy_cid=None,
                new_policy_cid=cid,
                operation_id=operation_id,
            )
            return result.status.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda args: attempt(*args),
                ((one, "writer-1"), (two, "writer-2")),
            )
        )
    assert sorted(statuses) == ["conflict", "updated"]
    with DurableCoordinationStore(root) as store:
        report = recover_assurance_campaigns(store)
        policy = DurableAssurancePolicyRepository(store)
        head = policy.current_policy(WORKSPACE)
        assert head.generation == 1
        assert head.policy_cid in (one, two)
        assert any(
            item.policy_cid == head.policy_cid
            for item in report.reconstructed_policy_heads
        )


def test_recovery_rejects_ambiguous_success_without_inventing_completion(
    tmp_path: Path,
) -> None:
    """Recovery reports ambiguous terminal claims as errors, not successes."""

    root = tmp_path / "ambiguous-reject"
    with DurableCoordinationStore(root) as store:
        campaigns = DurableMutationCampaignRepository(store)
        # Mid-campaign partial claim is durable but not terminal success.
        planned = campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.PLANNED,
                execution_claim_status=ExecutionClaimStatus.NONE,
            ),
            expected_generation=0,
            expected_state_cid=None,
            operation_id="amb-plan",
        )
        executing = campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.EXECUTING,
                execution_claim_status=ExecutionClaimStatus.PARTIAL,
            ),
            expected_generation=1,
            expected_state_cid=planned.state_cid,
            operation_id="amb-exec",
        )
        assert executing.status is AssuranceStoreStatus.UPDATED
        evaluating = campaigns.transition_campaign_state(
            WORKSPACE,
            state=_builder_state(
                phase=CampaignPhase.EVALUATING,
                execution_claim_status=ExecutionClaimStatus.PARTIAL,
            ),
            expected_generation=2,
            expected_state_cid=executing.state_cid,
            operation_id="amb-eval",
        )
        assert evaluating.status is AssuranceStoreStatus.UPDATED
        with pytest.raises(CampaignTransitionError, match="partial|ambiguous"):
            campaigns.transition_campaign_state(
                WORKSPACE,
                state=_builder_state(
                    phase=CampaignPhase.COMPLETE,
                    execution_claim_status=ExecutionClaimStatus.PARTIAL,
                    receipt_cid=cid_for_bytes(b"fake-receipt"),
                ),
                expected_generation=3,
                expected_state_cid=evaluating.state_cid,
                operation_id="amb-complete",
            )

    with DurableCoordinationStore(root) as recovered:
        report = recover_assurance_campaigns(recovered)
        # Partial evaluating state is reconstructed; no invented complete head.
        assert len(report.reconstructed_campaign_heads) == 1
        head = report.reconstructed_campaign_heads[0]
        assert head.phase is CampaignPhase.EVALUATING
        assert head.execution_claim_status is ExecutionClaimStatus.PARTIAL
        assert not any(
            item.phase is CampaignPhase.COMPLETE
            for item in report.reconstructed_campaign_heads
        )


def test_corrupt_blocks_fail_closed_on_recovery(tmp_path: Path) -> None:
    root = tmp_path / "corrupt"
    with DurableCoordinationStore(root) as store:
        policy = DurableAssurancePolicyRepository(store)
        cid = _block(store, "good")
        policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=cid,
            operation_id="good-publish",
        )
        store._block_path(cid).write_bytes(b"tampered")

    (root / "coordination.sqlite3").unlink(missing_ok=True)
    for sidecar in root.glob("coordination.sqlite3-*"):
        sidecar.unlink()

    # Reopen may raise during startup recovery, or recovery report captures it.
    try:
        store = DurableCoordinationStore(root)
    except ArtifactIntegrityError:
        return
    try:
        report = recover_assurance_campaigns(store)
        assert report.errors
        assert report.errors[0]["code"] == "corrupt"
        assert report.reconstructed_policy_heads == ()
    finally:
        store.close()


def test_unverified_signed_receipt_rejected_before_completion(
    tmp_path: Path,
) -> None:
    root = tmp_path / "unverified-receipt"
    payload = receipt_fixtures._campaign(
        header=receipt_fixtures._header(
            "assurance_campaign_receipt",
            terminal_status=AssuranceTerminalStatus.REJECTED,
        ),
        held_out_result=HeldOutResult.FAILED,
        signature=receipt_fixtures._signature(
            signature_verification_status=SignatureVerificationStatus.UNVERIFIED
        ),
    ).to_dict()
    with DurableCoordinationStore(root) as store:
        campaigns = DurableMutationCampaignRepository(store)
        with pytest.raises(Exception, match="signature|unverified"):
            admit_campaign_receipt_payload(payload)
        head = campaigns.current_campaign_state(WORKSPACE)
        assert head.generation == 0
        report = recover_assurance_campaigns(store)
        assert report.reconstructed_campaign_heads == ()
