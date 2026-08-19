"""FACP-028: Kit proof-role and freshness transition gate.

Acceptance covered here:

* Candidate never implies admitted.
* Admitted stale evidence cannot become current.
* Unknown verifier outcome persists explicitly.
* Concurrent pointer changes fail CAS and retain immutable history.
"""

from __future__ import annotations

import sys
import types
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = KIT_ROOT / "ipfs_kit_py" / "assurance" / "proof_role_gate.py"

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _load_gate():
    """Load the gate under ``ipfs_kit_py.assurance`` without requiring ``__init__.py``."""

    import importlib.util

    package_name = "ipfs_kit_py"
    assurance_name = "ipfs_kit_py.assurance"
    module_name = "ipfs_kit_py.assurance.proof_role_gate"

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

    spec = importlib.util.spec_from_file_location(module_name, GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    assurance = sys.modules[assurance_name]
    setattr(assurance, "proof_role_gate", module)
    return module


gate = _load_gate()

ProofRole = gate.ProofRole
ProofRoleDisposition = gate.ProofRoleDisposition
ProofRoleEvidence = gate.ProofRoleEvidence
ProofRoleTransitionRejected = gate.ProofRoleTransitionRejected
InMemoryCurrentPointerStore = gate.InMemoryCurrentPointerStore
CLOSED_OUTCOME_UNKNOWN = gate.CLOSED_OUTCOME_UNKNOWN
CLOSED_OUTCOME_REJECTED = gate.CLOSED_OUTCOME_REJECTED
CLOSED_OUTCOME_VERIFIED = gate.CLOSED_OUTCOME_VERIFIED
assess_proof_role = gate.assess_proof_role
candidate_implies_admitted = gate.candidate_implies_admitted
evaluate_admission = gate.evaluate_admission
evaluate_current_promotion = gate.evaluate_current_promotion
advance_current_pointer = gate.advance_current_pointer
advance_via_promotion_repository = gate.advance_via_promotion_repository
current_admitted_evidence = gate.current_admitted_evidence
candidate_evidence = gate.candidate_evidence


CANDIDATE_CID = "bafyCandidateProofRole0001"
AUTH_CID = "bafyAuthorizationProofRole02"
PROMO_CID = "bafyPromotionHeadProofRole03"
PROMO_CID_B = "bafyPromotionHeadProofRole04"


def _admitted(**overrides) -> ProofRoleEvidence:
    evidence = current_admitted_evidence(
        candidate_cid=CANDIDATE_CID,
        authorization_cid=AUTH_CID,
        now=NOW,
    )
    if overrides:
        evidence = evidence.with_overrides(**overrides)
    return evidence


# ---------------------------------------------------------------------------
# Identity / vocabulary
# ---------------------------------------------------------------------------


def test_module_identity_and_vocabulary() -> None:
    assert gate.TASK_ID == "FACP-028"
    assert gate.GOAL_ID == "FACP-G230"
    assert gate.SCHEMA == "KitProofRoleGate@1"
    assert gate.FCA_VOCABULARY_SCHEMA == "facp/formal-claim-algebra-v1@1"
    assert gate.EVIDENCE_BUNDLE == "facp/kit-proof-role-gate@1"
    assert gate.UNSAFE_PROMOTION is False
    assert gate.PROOF_ROLES == frozenset({"candidate", "admitted", "current"})
    assert "unknown" in gate.PROOF_VALUES
    assert "verifier_unavailable" in gate.PROOF_VALUES
    assert CLOSED_OUTCOME_UNKNOWN == "Unknown"


# ---------------------------------------------------------------------------
# Candidate never implies admitted
# ---------------------------------------------------------------------------


def test_candidate_never_implies_admitted() -> None:
    evidence = candidate_evidence(candidate_cid=CANDIDATE_CID, proof="candidate")
    assessment = assess_proof_role(evidence, now=NOW)
    assert assessment.implies_admitted is False
    assert assessment.admission_allowed is False
    assert assessment.current_eligible is False
    assert assessment.disposition is ProofRoleDisposition.CANDIDATE_ONLY
    assert "candidate_never_implies_admitted" in assessment.reason_codes
    assert candidate_implies_admitted(evidence) is False


def test_candidate_with_verified_label_still_does_not_imply_admitted() -> None:
    """Even a forged verified label on role=candidate does not imply admitted."""

    evidence = candidate_evidence(
        candidate_cid=CANDIDATE_CID,
        proof="verified",
        freshness="current",
        authorization_cid=AUTH_CID,
        verifier_identity="verifier:kit@1",
        proof_key="k",
        source_closure="c",
    )
    assessment = assess_proof_role(evidence, now=NOW)
    assert evidence.implies_admitted is False
    assert assessment.implies_admitted is False
    assert assessment.disposition is ProofRoleDisposition.CANDIDATE_ONLY


def test_evaluate_admission_rejects_bare_candidate() -> None:
    result = evaluate_admission(
        candidate_evidence(candidate_cid=CANDIDATE_CID),
        now=NOW,
    )
    assert result.allowed is False
    assert result.implies_admitted is False
    assert result.closed_outcome == CLOSED_OUTCOME_REJECTED
    assert result.disposition is (
        ProofRoleDisposition.REJECTED_CANDIDATE_IMPLIES_ADMITTED
    )
    assert "candidate_never_implies_admitted" in result.reason_codes
    assert result.to_decision_dict()["implies_admitted"] is False


def test_evaluate_admission_rejects_self_authorization() -> None:
    result = evaluate_admission(
        candidate_evidence(
            candidate_cid=CANDIDATE_CID,
            proof="verified",
            freshness="current",
            authorization_cid=CANDIDATE_CID,
            verifier_identity="verifier:kit@1",
            proof_key="proof-key",
            source_closure="closure:1",
        ),
        now=NOW,
    )
    assert result.allowed is False
    assert result.disposition is ProofRoleDisposition.REJECTED_SELF_AUTHORIZATION
    assert "candidate_cannot_authorize_own_promotion" in result.reason_codes


def test_evaluate_admission_allows_with_current_verifier_evidence() -> None:
    evidence = candidate_evidence(
        candidate_cid=CANDIDATE_CID,
        proof="verified",
        freshness="current",
        authorization_cid=AUTH_CID,
        verifier_identity="verifier:kit@1",
        proof_key="proof-key",
        source_closure="closure:admitted@1",
    )
    evidence = evidence.with_overrides(
        issued_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=1),
        evidence_bag={
            "named_current_verifier": "verifier:kit@1",
            "verifier_admission_closure": "closure:admitted@1",
            "proof_key": "proof-key",
        },
    )
    result = evaluate_admission(evidence, now=NOW)
    assert result.allowed is True
    assert result.closed_outcome == CLOSED_OUTCOME_VERIFIED
    assert result.disposition is ProofRoleDisposition.ADMISSION_ALLOWED
    assert result.implies_admitted is False
    assert result.assessment is not None
    assert result.assessment.evidence.role == ProofRole.ADMITTED.value
    assert "candidate_never_implies_admitted" in result.reason_codes


def test_require_admission_raises_typed_rejection() -> None:
    with pytest.raises(ProofRoleTransitionRejected) as exc_info:
        evaluate_admission(
            candidate_evidence(candidate_cid=CANDIDATE_CID),
            now=NOW,
            require=True,
        )
    assert exc_info.value.result.allowed is False
    assert exc_info.value.result.current_advanced is False


# ---------------------------------------------------------------------------
# Admitted stale evidence cannot become current
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("freshness", ["stale", "superseded", "withdrawn"])
def test_admitted_stale_cannot_become_current(freshness: str) -> None:
    evidence = _admitted(freshness=freshness)
    assessment = assess_proof_role(evidence, now=NOW)
    assert assessment.admission_allowed is True
    assert assessment.current_eligible is False
    assert assessment.disposition is ProofRoleDisposition.REJECTED_STALE_TO_CURRENT
    assert "admitted_stale_cannot_become_current" in assessment.reason_codes

    result = evaluate_current_promotion(evidence, now=NOW)
    assert result.allowed is False
    assert result.current_advanced is False
    assert result.disposition is ProofRoleDisposition.REJECTED_STALE_TO_CURRENT
    assert "admitted_stale_cannot_become_current" in result.reason_codes


def test_expired_admitted_receipt_cannot_become_current() -> None:
    evidence = _admitted(
        freshness="current",
        issued_at=NOW - timedelta(days=2),
        expires_at=NOW - timedelta(seconds=1),
    )
    result = evaluate_current_promotion(evidence, now=NOW)
    assert result.allowed is False
    assert result.disposition is ProofRoleDisposition.REJECTED_STALE_TO_CURRENT
    assert "admitted_stale_cannot_become_current" in result.reason_codes


def test_stale_admitted_does_not_mutate_pointer_store() -> None:
    store = InMemoryCurrentPointerStore()
    evidence = _admitted(freshness="stale")
    result = advance_current_pointer(
        evidence,
        store,
        new_root_cid=PROMO_CID,
        operation_id="stale-advance",
        now=NOW,
    )
    assert result.allowed is False
    assert result.current_advanced is False
    assert result.cas is None
    assert store.current() == (0, None)
    assert store.history() == ()


def test_current_eligible_admitted_may_advance() -> None:
    store = InMemoryCurrentPointerStore()
    evidence = _admitted()
    result = advance_current_pointer(
        evidence,
        store,
        new_root_cid=PROMO_CID,
        operation_id="advance-1",
        now=NOW,
    )
    assert result.allowed is True
    assert result.current_advanced is True
    assert result.disposition is ProofRoleDisposition.CURRENT_ADVANCED
    assert result.cas is not None
    assert result.cas.status == "updated"
    assert store.current() == (1, PROMO_CID)
    assert len(store.history()) == 1


# ---------------------------------------------------------------------------
# Unknown verifier outcome persists explicitly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("proof", ["unknown", "verifier_unavailable"])
def test_unknown_verifier_outcome_persists_explicitly(proof: str) -> None:
    evidence = candidate_evidence(
        candidate_cid=CANDIDATE_CID,
        proof=proof,
        freshness="current",
        authorization_cid=AUTH_CID,
    )
    assessment = assess_proof_role(evidence, now=NOW)
    assert assessment.unknown_persists is True
    assert assessment.unresolved_verifier_outcome == proof
    assert assessment.proof == proof
    assert assessment.closed_outcome == CLOSED_OUTCOME_UNKNOWN
    assert "unknown_verifier_outcome_persists" in assessment.reason_codes
    assert assessment.implies_admitted is False
    assert assessment.current_eligible is False

    admit = evaluate_admission(evidence, now=NOW)
    assert admit.allowed is False
    assert admit.closed_outcome == CLOSED_OUTCOME_UNKNOWN
    assert admit.disposition is ProofRoleDisposition.REJECTED_UNKNOWN_PERSISTS
    assert admit.assessment is not None
    assert admit.assessment.proof == proof

    promote = evaluate_current_promotion(
        evidence.with_overrides(role=ProofRole.ADMITTED.value, proof=proof),
        now=NOW,
    )
    assert promote.allowed is False
    assert promote.closed_outcome == CLOSED_OUTCOME_UNKNOWN
    assert promote.assessment is not None
    assert promote.assessment.proof == proof


def test_unknown_cannot_advance_current_pointer() -> None:
    store = InMemoryCurrentPointerStore()
    evidence = _admitted(proof="unknown")
    result = advance_current_pointer(
        evidence,
        store,
        new_root_cid=PROMO_CID,
        operation_id="unknown-advance",
        now=NOW,
    )
    assert result.allowed is False
    assert result.closed_outcome == CLOSED_OUTCOME_UNKNOWN
    assert result.current_advanced is False
    assert store.current() == (0, None)


# ---------------------------------------------------------------------------
# Concurrent pointer changes fail CAS and retain immutable history
# ---------------------------------------------------------------------------


def test_concurrent_pointer_changes_fail_cas_and_retain_history() -> None:
    store = InMemoryCurrentPointerStore()
    evidence = _admitted()

    first = advance_current_pointer(
        evidence,
        store,
        new_root_cid=PROMO_CID,
        operation_id="writer-a",
        expected_generation=0,
        expected_root_cid=None,
        now=NOW,
    )
    assert first.current_advanced is True
    history_after_first = store.history()
    assert len(history_after_first) == 1
    assert history_after_first[0].root_cid == PROMO_CID

    # Stale concurrent writer still expects generation 0.
    second = advance_current_pointer(
        evidence,
        store,
        new_root_cid=PROMO_CID_B,
        operation_id="writer-b",
        expected_generation=0,
        expected_root_cid=None,
        now=NOW,
    )
    assert second.allowed is False
    assert second.current_advanced is False
    assert second.disposition is ProofRoleDisposition.CAS_CONFLICT
    assert second.cas is not None
    assert second.cas.status == "conflict"
    assert "concurrent_pointer_change_failed_cas" in second.reason_codes
    assert "immutable_history_retained" in second.reason_codes

    # Winning head and history unchanged by the loser.
    assert store.current() == (1, PROMO_CID)
    assert store.history() == history_after_first
    assert second.cas.history == history_after_first


def test_threaded_concurrent_writers_yield_one_update() -> None:
    store = InMemoryCurrentPointerStore()
    evidence = _admitted()

    def _attempt(idx: int):
        return advance_current_pointer(
            evidence,
            store,
            new_root_cid=f"bafyConcurrentHead{idx:04d}",
            operation_id=f"concurrent-{idx}",
            expected_generation=0,
            expected_root_cid=None,
            now=NOW,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_attempt, range(4)))

    advanced = [item for item in results if item.current_advanced]
    conflicts = [
        item
        for item in results
        if item.disposition is ProofRoleDisposition.CAS_CONFLICT
    ]
    assert len(advanced) == 1
    assert len(conflicts) == 3
    gen, root = store.current()
    assert gen == 1
    assert root is not None
    assert len(store.history()) == 1
    assert store.history()[0].root_cid == root


def test_idempotent_replay_retains_history_without_double_advance() -> None:
    store = InMemoryCurrentPointerStore()
    evidence = _admitted()
    first = advance_current_pointer(
        evidence,
        store,
        new_root_cid=PROMO_CID,
        operation_id="replay-op",
        now=NOW,
    )
    assert first.current_advanced is True
    history = store.history()
    replay = advance_current_pointer(
        evidence,
        store,
        new_root_cid=PROMO_CID,
        operation_id="replay-op",
        expected_generation=0,
        expected_root_cid=None,
        now=NOW,
    )
    assert replay.disposition is ProofRoleDisposition.CAS_UNCHANGED
    assert replay.current_advanced is False
    assert store.history() == history
    assert store.current() == (1, PROMO_CID)


# ---------------------------------------------------------------------------
# Exact promotion-repository admission / current-pointer seam
# ---------------------------------------------------------------------------


def test_advance_via_promotion_repository_updates_and_conflicts(tmp_path: Path) -> None:
    from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
        DurableCoordinationStore,
        cid_for_artifact,
    )
    from ipfs_kit_py.semantic_governor_store.policy import (
        DurablePromotionStateRepository,
    )

    store = DurableCoordinationStore(tmp_path / "promo-cas")
    try:
        repo = DurablePromotionStateRepository(store)

        def _block(name: str) -> str:
            payload = {"schema": "example/governor-policy@1", "name": name}
            return store.put(
                payload, expected_cid=cid_for_artifact(payload), replicate=False
            )["cid"]

        candidate = _block("candidate-seam")
        auth = _block("authorization-seam")
        promo_a = _block("promo-a")
        promo_b = _block("promo-b")
        evidence = current_admitted_evidence(
            candidate_cid=candidate,
            authorization_cid=auth,
            now=NOW,
        )

        updated = advance_via_promotion_repository(
            evidence,
            repo,
            workspace="default",
            new_promotion_cid=promo_a,
            operation_id="seam-advance-1",
            expected_generation=0,
            expected_promotion_cid=None,
            now=NOW,
        )
        assert updated.allowed is True
        assert updated.current_advanced is True
        assert updated.cas is not None
        assert updated.cas.status == "updated"
        assert "promotion_repository_seam" in updated.reason_codes
        history_after = repo.promotion_transitions("default")
        assert len(history_after) == 1

        conflict = advance_via_promotion_repository(
            evidence,
            repo,
            workspace="default",
            new_promotion_cid=promo_b,
            operation_id="seam-advance-stale",
            expected_generation=0,
            expected_promotion_cid=None,
            now=NOW,
        )
        assert conflict.allowed is False
        assert conflict.disposition is ProofRoleDisposition.CAS_CONFLICT
        assert conflict.cas is not None
        assert conflict.cas.status == "conflict"
        assert "immutable_history_retained" in conflict.reason_codes
        # Losing CAS must not append a second transition.
        assert len(repo.promotion_transitions("default")) == 1
        assert repo.current_promotion("default").promotion_cid == promo_a
    finally:
        store.close()


def test_stale_evidence_never_invokes_successful_promotion_cas(tmp_path: Path) -> None:
    from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
        DurableCoordinationStore,
        cid_for_artifact,
    )
    from ipfs_kit_py.semantic_governor_store.policy import (
        DurablePromotionStateRepository,
    )

    store = DurableCoordinationStore(tmp_path / "promo-stale")
    try:
        repo = DurablePromotionStateRepository(store)

        def _block(name: str) -> str:
            payload = {"schema": "example/governor-policy@1", "name": name}
            return store.put(
                payload, expected_cid=cid_for_artifact(payload), replicate=False
            )["cid"]

        evidence = current_admitted_evidence(
            candidate_cid=_block("cand-stale"),
            authorization_cid=_block("auth-stale"),
            now=NOW,
        ).with_overrides(freshness="stale")
        result = advance_via_promotion_repository(
            evidence,
            repo,
            workspace="default",
            new_promotion_cid=_block("promo-stale"),
            operation_id="should-not-cas",
            now=NOW,
        )
        assert result.allowed is False
        assert result.cas is None
        assert "promotion_repository_not_invoked" in result.reason_codes
        assert repo.current_promotion("default").generation == 0
        assert repo.promotion_transitions("default") == []
    finally:
        store.close()


def test_ambiguous_recovery_blocks_current() -> None:
    evidence = _admitted(ambiguous_recovery=True)
    result = evaluate_current_promotion(evidence, now=NOW)
    assert result.allowed is False
    assert result.disposition is ProofRoleDisposition.REJECTED_AMBIGUOUS_RECOVERY
    assert "cannot_update_current_on_ambiguous" in result.reason_codes or (
        "ambiguous_recovery" in result.reason_codes
    )


def test_candidate_cannot_skip_to_current() -> None:
    result = evaluate_current_promotion(
        candidate_evidence(candidate_cid=CANDIDATE_CID, proof="verified"),
        now=NOW,
    )
    assert result.allowed is False
    assert result.disposition is (
        ProofRoleDisposition.REJECTED_CANDIDATE_IMPLIES_ADMITTED
    )
    assert "candidate_cannot_become_current" in result.reason_codes
