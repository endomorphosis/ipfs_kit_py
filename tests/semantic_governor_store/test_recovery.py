"""Fail-closed recovery proofs for the durable governor store (SCG-022).

Acceptance:

* interrupted audits recover safely (prior head or sole durable successor)
* corruption and ambiguous promotion fail closed
* recovery rebuilds indexes from verified immutable blocks
* recovery never invents promotion or completion
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    DurableCoordinationStore,
    ROOT_CAS_INTERRUPTION_POINTS,
    STATE_ROOT_TRANSITION_SCHEMA,
    cid_for_artifact,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    AuditRecoveryReport,
    GovernorHistoryRole,
    GovernorStoreStatus,
    governor_namespace,
    history_namespace,
)
from ipfs_kit_py.semantic_governor_store.history import (
    DurableAuditHistoryStore,
)
from ipfs_kit_py.semantic_governor_store.policy import (
    DurableCompressionPolicyRepository,
    DurablePromotionStateRepository,
)
from ipfs_kit_py.semantic_governor_store.recovery import (
    RECOVERY_MODULE_INTERFACE,
    RECOVERY_SCHEMA,
    DurableGovernorStoreRecovery,
    recover_governor_store,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class InjectedInterruption(RuntimeError):
    """Stand-in for a process stopping at a durable CAS boundary."""


def _entry(store: DurableCoordinationStore, name: str, **extra: Any) -> str:
    payload: dict[str, Any] = {
        "schema": "example/governor-recovery-entry@1",
        "name": name,
        "status": "complete",
    }
    payload.update(extra)
    return store.put(payload, expected_cid=cid_for_artifact(payload), replicate=False)[
        "cid"
    ]


def _block(store: DurableCoordinationStore, name: str, **extra: Any) -> str:
    payload = {"schema": "example/governor-policy@1", "name": name}
    payload.update(extra)
    return store.put(payload, expected_cid=cid_for_artifact(payload), replicate=False)[
        "cid"
    ]


def _wipe_sqlite(root: Path) -> None:
    db = root / "coordination.sqlite3"
    if db.exists():
        db.unlink()
    for sidecar in root.glob("coordination.sqlite3-*"):
        sidecar.unlink()


def _restart(root: Path) -> DurableCoordinationStore:
    return DurableCoordinationStore(root)


WORKSPACE = "default"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_module_interfaces_are_versioned() -> None:
    assert RECOVERY_MODULE_INTERFACE == "GovernorStoreRecovery@1"
    assert RECOVERY_SCHEMA.endswith("@1")


def test_recover_governor_store_requires_coordination_store() -> None:
    with pytest.raises(TypeError, match="DurableCoordinationStore"):
        recover_governor_store(object())  # type: ignore[arg-type]


def test_facade_exposes_protocol_method(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "facade") as store:
        recovery = DurableGovernorStoreRecovery(store)
        assert recovery.store is store
        report = recovery.recover_governor_store()
        assert isinstance(report, AuditRecoveryReport)
        assert report.verified_blocks >= 0
        assert report.reconstructed_policy_heads == ()
        assert report.reconstructed_promotion_heads == ()
        assert report.reconstructed_history_heads == ()
        assert report.errors == ()


# ---------------------------------------------------------------------------
# Happy path: reconstruct policy, promotion, and audit heads
# ---------------------------------------------------------------------------


def test_recovery_reconstructs_policy_promotion_and_audit_heads(
    tmp_path: Path,
) -> None:
    root = tmp_path / "reconstruct"
    with DurableCoordinationStore(root) as store:
        history = DurableAuditHistoryStore(store)
        policy = DurableCompressionPolicyRepository(store)
        promotion = DurablePromotionStateRepository(store)

        entry = _entry(store, "audit-1")
        audit = history.append_audit(
            WORKSPACE,
            entry_cid=entry,
            expected_generation=0,
            expected_head_cid=None,
            operation_id="audit-1",
        )
        assert audit.status is GovernorStoreStatus.UPDATED

        policy_cid = _block(store, "policy-v1")
        policy_result = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=policy_cid,
            operation_id="policy-1",
        )
        assert policy_result.status is GovernorStoreStatus.UPDATED

        promo_cid = _block(store, "promo-v1")
        candidate = _block(store, "candidate")
        auth = _block(store, "authorization")
        promo_result = promotion.compare_and_swap_promotion(
            WORKSPACE,
            expected_generation=0,
            expected_promotion_cid=None,
            new_promotion_cid=promo_cid,
            operation_id="promo-1",
            candidate_cid=candidate,
            authorization_cid=auth,
        )
        assert promo_result.status is GovernorStoreStatus.UPDATED

        before = recover_governor_store(store, rebuild=True)
        assert before.errors == ()
        assert before.verified_blocks >= 1
        assert len(before.reconstructed_policy_heads) == 1
        assert before.reconstructed_policy_heads[0].policy_cid == policy_cid
        assert before.reconstructed_policy_heads[0].generation == 1
        assert len(before.reconstructed_promotion_heads) == 1
        assert before.reconstructed_promotion_heads[0].promotion_cid == promo_cid
        # Recovery reports the head only — never invents completion.
        assert before.reconstructed_promotion_heads[0].generation == 1
        assert len(before.reconstructed_history_heads) == 1
        assert before.reconstructed_history_heads[0].history_role is (
            GovernorHistoryRole.AUDIT
        )
        assert before.reconstructed_history_heads[0].head_cid == audit.after.head_cid

    # Wipe derived indexes; recovery must rebuild solely from immutable blocks.
    _wipe_sqlite(root)
    with _restart(root) as recovered:
        report = recover_governor_store(recovered, rebuild=True)
        assert report.errors == ()
        assert report.verified_blocks >= 1
        assert len(report.reconstructed_policy_heads) == 1
        assert report.reconstructed_policy_heads[0].policy_cid == policy_cid
        assert len(report.reconstructed_promotion_heads) == 1
        assert report.reconstructed_promotion_heads[0].promotion_cid == promo_cid
        assert len(report.reconstructed_history_heads) == 1
        assert report.reconstructed_history_heads[0].head_cid == audit.after.head_cid

        history = DurableAuditHistoryStore(recovered)
        assert history.list_entry_cids(WORKSPACE, "audit") == [entry]
        assert history.current_history(WORKSPACE, "audit").generation == 1


def test_recovery_never_invents_promotion_or_completion(tmp_path: Path) -> None:
    root = tmp_path / "no-invention"
    with DurableCoordinationStore(root) as store:
        # Only an audit entry — no promotion transition exists.
        history = DurableAuditHistoryStore(store)
        entry = _entry(store, "only-audit")
        history.append_audit(
            WORKSPACE,
            entry_cid=entry,
            expected_generation=0,
            expected_head_cid=None,
            operation_id="only-audit",
        )
        report = recover_governor_store(store, rebuild=True)
        assert report.errors == ()
        assert report.reconstructed_promotion_heads == ()
        assert report.reconstructed_policy_heads == ()
        assert len(report.reconstructed_history_heads) == 1
        # Report does not claim any completion / promotion outcome fields.
        wire = report.to_dict()
        assert "completed" not in wire
        assert "promoted" not in wire
        assert wire["reconstructed_promotion_heads"] == []


# ---------------------------------------------------------------------------
# Interrupted audits recover safely
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("boundary", ROOT_CAS_INTERRUPTION_POINTS)
def test_interrupted_audit_append_recovers_to_prior_or_sole_successor(
    tmp_path: Path, boundary: str
) -> None:
    root = tmp_path / f"interrupt-{boundary}"

    def interrupt(point: str) -> None:
        if point == boundary:
            raise InjectedInterruption(point)

    with DurableCoordinationStore(root) as setup:
        entry = _entry(setup, "interrupted-entry")

    with DurableCoordinationStore(root, crash_injector=interrupt) as store:
        history = DurableAuditHistoryStore(store)
        with pytest.raises(InjectedInterruption, match=boundary):
            history.append_audit(
                WORKSPACE,
                entry_cid=entry,
                expected_generation=0,
                expected_head_cid=None,
                operation_id="interrupted-audit",
            )

    # Reopen recovers to prior head or the sole durable successor.
    with _restart(root) as recovered:
        report = recover_governor_store(recovered, rebuild=True)
        assert report.errors == ()
        history = DurableAuditHistoryStore(recovered)
        head = history.current_history(WORKSPACE, GovernorHistoryRole.AUDIT)

        if boundary in {"before_transaction", "after_expectation_verification"}:
            assert head.generation == 0
            assert head.head_cid is None
            assert report.reconstructed_history_heads == ()
        else:
            assert head.generation == 1
            assert head.head_cid is not None
            assert len(report.reconstructed_history_heads) == 1
            assert report.reconstructed_history_heads[0].head_cid == head.head_cid
            assert history.list_entry_cids(WORKSPACE, "audit") == [entry]

        # Idempotent replay completes or no-ops without silent overwrite.
        replay = history.append_audit(
            WORKSPACE,
            entry_cid=entry,
            expected_generation=0,
            expected_head_cid=None,
            operation_id="interrupted-audit",
        )
        if boundary in {"before_transaction", "after_expectation_verification"}:
            assert replay.status is GovernorStoreStatus.UPDATED
        else:
            assert replay.status is GovernorStoreStatus.UNCHANGED
            assert replay.reason_code == "idempotent_replay"
        assert history.current_history(WORKSPACE, "audit").generation == 1
        assert len(history.history_transitions(WORKSPACE, "audit")) == 1


def test_interrupted_chained_audit_preserves_prior_committed_head(
    tmp_path: Path,
) -> None:
    root = tmp_path / "interrupt-chain"
    with DurableCoordinationStore(root) as setup:
        first = _entry(setup, "committed")
        second = _entry(setup, "interrupted")

    with DurableCoordinationStore(root) as store:
        history = DurableAuditHistoryStore(store)
        committed = history.append_audit(
            WORKSPACE,
            entry_cid=first,
            expected_generation=0,
            expected_head_cid=None,
            operation_id="chain-1",
        )
        assert committed.status is GovernorStoreStatus.UPDATED
        prior_head = committed.after.head_cid

    def interrupt(point: str) -> None:
        if point == "before_sqlite_commit":
            raise InjectedInterruption(point)

    with DurableCoordinationStore(root, crash_injector=interrupt) as store:
        history = DurableAuditHistoryStore(store)
        with pytest.raises(InjectedInterruption):
            history.append_audit(
                WORKSPACE,
                entry_cid=second,
                expected_generation=1,
                expected_head_cid=prior_head,
                operation_id="chain-2",
            )

    with _restart(root) as recovered:
        report = recover_governor_store(recovered, rebuild=True)
        assert report.errors == ()
        history = DurableAuditHistoryStore(recovered)
        head = history.current_history(WORKSPACE, "audit")
        # Transition fsynced before commit → sole durable successor is visible.
        assert head.generation == 2
        assert history.list_entry_cids(WORKSPACE, "audit") == [first, second]


# ---------------------------------------------------------------------------
# Corruption and ambiguous promotion fail closed
# ---------------------------------------------------------------------------


def test_ambiguous_promotion_fork_fails_closed_without_picking_winner(
    tmp_path: Path,
) -> None:
    root = tmp_path / "ambiguous-promotion"
    namespace = governor_namespace(WORKSPACE, "promotion")
    with DurableCoordinationStore(root) as store:
        first = _block(store, "promo-a")
        second = _block(store, "promo-b")
        for operation_id, successor in (("fork-a", first), ("fork-b", second)):
            store.put(
                {
                    "schema": STATE_ROOT_TRANSITION_SCHEMA,
                    "namespace": namespace,
                    "operation_id": operation_id,
                    "expected_root_cid": None,
                    "expected_revision": 0,
                    "new_root_cid": successor,
                    "new_revision": 1,
                    "created_at_ms": 1,
                }
            )

    _wipe_sqlite(root)
    # Ambiguous successors break reconstruction: reopen fails closed and never
    # invents a promotion winner from the forked transition evidence.
    with pytest.raises(ArtifactIntegrityError, match="breaks its namespace chain"):
        _restart(root)

    # When the store is still open with forked evidence injected into an empty
    # index, domain recovery also fails closed without projecting a head.
    with DurableCoordinationStore(tmp_path / "ambiguous-live") as store:
        first = _block(store, "promo-a2")
        second = _block(store, "promo-b2")
        for operation_id, successor in (("fork-a", first), ("fork-b", second)):
            store.put(
                {
                    "schema": STATE_ROOT_TRANSITION_SCHEMA,
                    "namespace": namespace,
                    "operation_id": operation_id,
                    "expected_root_cid": None,
                    "expected_revision": 0,
                    "new_root_cid": successor,
                    "new_revision": 1,
                    "created_at_ms": 1,
                }
            )
        report = recover_governor_store(store, rebuild=True)
        assert report.reconstructed_promotion_heads == ()
        assert report.reconstructed_policy_heads == ()
        assert report.reconstructed_history_heads == ()
        assert report.errors
        assert report.errors[0]["code"] in {"corrupt", "ambiguous_promotion"}
        assert "breaks its namespace chain" in report.errors[0]["message"]


def test_corrupt_policy_successor_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "corrupt-policy"
    with DurableCoordinationStore(root) as store:
        policy = DurableCompressionPolicyRepository(store)
        cid = _block(store, "valid-policy")
        result = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=cid,
            operation_id="policy-ok",
        )
        assert result.status is GovernorStoreStatus.UPDATED
        store._block_path(cid).write_bytes(b"tampered-policy-bytes")
        report = recover_governor_store(store, rebuild=True)
        assert report.reconstructed_policy_heads == ()
        assert report.reconstructed_promotion_heads == ()
        assert report.reconstructed_history_heads == ()
        assert report.errors
        assert report.errors[0]["code"] == "corrupt"

    _wipe_sqlite(root)
    with pytest.raises(ArtifactIntegrityError, match="corrupt blocks"):
        _restart(root)


def test_corrupt_audit_head_bytes_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "corrupt-audit"
    with DurableCoordinationStore(root) as store:
        history = DurableAuditHistoryStore(store)
        entry = _entry(store, "audit-ok")
        result = history.append_audit(
            WORKSPACE,
            entry_cid=entry,
            expected_generation=0,
            expected_head_cid=None,
            operation_id="audit-ok",
        )
        head_cid = result.after.head_cid
        assert head_cid is not None
        store._block_path(head_cid).write_bytes(b"tampered-manifest")
        report = recover_governor_store(store, rebuild=True)
        assert report.reconstructed_history_heads == ()
        assert report.errors
        assert report.errors[0]["code"] == "corrupt"

    _wipe_sqlite(root)
    with pytest.raises(ArtifactIntegrityError, match="corrupt blocks"):
        _restart(root)


def test_corrupt_transition_block_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "corrupt-transition"
    with DurableCoordinationStore(root) as store:
        policy = DurableCompressionPolicyRepository(store)
        cid = _block(store, "p1")
        result = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=cid,
            operation_id="p1",
        )
        transition = result.after.transition_cid
        assert transition is not None
        store._block_path(transition).write_bytes(b"tampered-transition")
        report = recover_governor_store(store, rebuild=True)
        assert report.reconstructed_policy_heads == ()
        assert report.errors
        assert report.errors[0]["code"] == "corrupt"

    _wipe_sqlite(root)
    with pytest.raises(ArtifactIntegrityError, match="corrupt blocks"):
        _restart(root)


def test_stale_pointer_cannot_overwrite_after_recovery(tmp_path: Path) -> None:
    root = tmp_path / "stale-after-recovery"
    with DurableCoordinationStore(root) as store:
        policy = DurableCompressionPolicyRepository(store)
        first = _block(store, "live")
        stale = _block(store, "stale-candidate")
        updated = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=first,
            operation_id="live-1",
        )
        assert updated.status is GovernorStoreStatus.UPDATED

    _wipe_sqlite(root)
    with _restart(root) as recovered:
        report = recover_governor_store(recovered, rebuild=True)
        assert report.errors == ()
        policy = DurableCompressionPolicyRepository(recovered)
        head = policy.current_policy(WORKSPACE)
        assert head.policy_cid == first
        assert head.generation == 1

        conflict = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=stale,
            operation_id="stale-after-recover",
        )
        assert conflict.status is GovernorStoreStatus.CONFLICT
        assert conflict.reason_code == "stale_expectation"
        assert policy.current_policy(WORKSPACE).policy_cid == first
        assert len(policy.policy_transitions(WORKSPACE)) == 1


def test_rebuild_false_still_projects_live_heads(tmp_path: Path) -> None:
    root = tmp_path / "verify-only"
    with DurableCoordinationStore(root) as store:
        history = DurableAuditHistoryStore(store)
        entry = _entry(store, "verify")
        history.append_audit(
            WORKSPACE,
            entry_cid=entry,
            expected_generation=0,
            expected_head_cid=None,
            operation_id="verify-1",
        )
        report = recover_governor_store(store, rebuild=False)
        assert report.errors == ()
        assert len(report.reconstructed_history_heads) == 1
        assert report.reconstructed_history_heads[0].namespace == history_namespace(
            WORKSPACE, "audit"
        )


def test_report_round_trips_through_contract_wire(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "wire") as store:
        policy = DurableCompressionPolicyRepository(store)
        cid = _block(store, "wire-policy")
        policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=cid,
            operation_id="wire-1",
        )
        report = recover_governor_store(store, rebuild=True)
        restored = AuditRecoveryReport.from_dict(report.to_dict())
        assert restored.to_dict() == report.to_dict()
