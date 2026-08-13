"""Concurrency proofs for the durable governor store (SCG-022).

Acceptance:

* concurrent writers never silently overwrite (lost_updates == 0)
* stale candidates cannot overwrite the live head
* concurrent calibration writers yield at most one CAS success per generation
* both immutable histories are preserved when the loser retries
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    GovernorStoreStatus,
)
from ipfs_kit_py.semantic_governor_store.history import (
    DurableAuditHistoryStore,
)
from ipfs_kit_py.semantic_governor_store.policy import (
    DurableCompressionPolicyRepository,
    DurablePromotionStateRepository,
)
from ipfs_kit_py.semantic_governor_store.recovery import recover_governor_store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(store: DurableCoordinationStore, name: str, **extra: Any) -> str:
    payload: dict[str, Any] = {
        "schema": "example/governor-concurrency-entry@1",
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


WORKSPACE = "default"


# ---------------------------------------------------------------------------
# Concurrent calibration writers
# ---------------------------------------------------------------------------


def test_concurrent_calibration_writers_yield_at_most_one_success(
    tmp_path: Path,
) -> None:
    store_dir = tmp_path / "cal-race"
    with DurableCoordinationStore(store_dir) as setup:
        one = _entry(setup, "cal-one")
        two = _entry(setup, "cal-two")

    def attempt(entry_cid: str, operation_id: str) -> str:
        with DurableCoordinationStore(store_dir) as store:
            repo = DurableAuditHistoryStore(store)
            result = repo.append_calibration(
                WORKSPACE,
                entry_cid=entry_cid,
                expected_generation=0,
                expected_head_cid=None,
                operation_id=operation_id,
            )
            return result.status.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda args: attempt(*args),
                ((one, "cal-w1"), (two, "cal-w2")),
            )
        )

    assert sorted(statuses) == ["conflict", "updated"]
    with DurableCoordinationStore(store_dir) as store:
        repo = DurableAuditHistoryStore(store)
        head = repo.current_history(WORKSPACE, "calibration")
        assert head.generation == 1
        assert len(repo.history_transitions(WORKSPACE, "calibration")) == 1
        # Exactly one entry is on the live head; the loser's block remains durable.
        live = set(repo.list_entry_cids(WORKSPACE, "calibration"))
        assert len(live) == 1
        assert live.issubset({one, two})
        assert store.has(one)
        assert store.has(two)
        report = recover_governor_store(store, rebuild=True)
        assert report.errors == ()
        assert len(report.reconstructed_history_heads) == 1


def test_concurrent_calibration_retry_preserves_both_histories(
    tmp_path: Path,
) -> None:
    """Loser retries against the successor so both immutable entries survive."""

    store_dir = tmp_path / "cal-retry"
    with DurableCoordinationStore(store_dir) as setup:
        one = _entry(setup, "cal-a")
        two = _entry(setup, "cal-b")

    def attempt(entry_cid: str, operation_id: str) -> dict[str, Any]:
        with DurableCoordinationStore(store_dir) as store:
            repo = DurableAuditHistoryStore(store)
            first = repo.append_calibration(
                WORKSPACE,
                entry_cid=entry_cid,
                expected_generation=0,
                expected_head_cid=None,
                operation_id=operation_id,
            )
            if first.status is GovernorStoreStatus.UPDATED:
                return {
                    "status": first.status.value,
                    "entry_cid": entry_cid,
                    "retried": False,
                }
            head = repo.current_history(WORKSPACE, "calibration")
            retry = repo.append_calibration(
                WORKSPACE,
                entry_cid=entry_cid,
                expected_generation=head.generation,
                expected_head_cid=head.head_cid,
                operation_id=f"{operation_id}-retry",
            )
            return {
                "status": retry.status.value,
                "entry_cid": entry_cid,
                "retried": True,
                "first_status": first.status.value,
            }

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(attempt, one, "writer-1"),
            pool.submit(attempt, two, "writer-2"),
        ]
        results = [future.result() for future in as_completed(futures)]

    assert all(item["status"] == "updated" for item in results)
    assert sum(1 for item in results if item["retried"]) == 1

    with DurableCoordinationStore(store_dir) as store:
        repo = DurableAuditHistoryStore(store)
        head = repo.current_history(WORKSPACE, "calibration")
        assert head.generation == 2
        assert set(repo.list_entry_cids(WORKSPACE, "calibration")) == {one, two}
        assert len(repo.history_transitions(WORKSPACE, "calibration")) == 2


# ---------------------------------------------------------------------------
# Concurrent policy / promotion — no silent overwrite
# ---------------------------------------------------------------------------


def test_concurrent_policy_writers_never_silently_overwrite(
    tmp_path: Path,
) -> None:
    store_dir = tmp_path / "policy-race"
    with DurableCoordinationStore(store_dir) as setup:
        one = _block(setup, "p-one")
        two = _block(setup, "p-two")

    lost_updates = 0

    def attempt(cid: str, operation_id: str) -> str:
        nonlocal lost_updates
        with DurableCoordinationStore(store_dir) as store:
            repo = DurableCompressionPolicyRepository(store)
            result = repo.compare_and_swap_policy(
                WORKSPACE,
                expected_generation=0,
                expected_policy_cid=None,
                new_policy_cid=cid,
                operation_id=operation_id,
            )
            if result.status is GovernorStoreStatus.UPDATED:
                return "updated"
            if result.status is GovernorStoreStatus.CONFLICT:
                # Typed conflict — not a silent overwrite.
                return "conflict"
            lost_updates += 1
            return result.status.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda args: attempt(*args),
                ((one, "pw-1"), (two, "pw-2")),
            )
        )

    assert lost_updates == 0
    assert sorted(statuses) == ["conflict", "updated"]
    with DurableCoordinationStore(store_dir) as store:
        repo = DurableCompressionPolicyRepository(store)
        head = repo.current_policy(WORKSPACE)
        assert head.generation == 1
        assert head.policy_cid in (one, two)
        assert len(repo.policy_transitions(WORKSPACE)) == 1


def test_concurrent_promotion_writers_never_silently_overwrite(
    tmp_path: Path,
) -> None:
    store_dir = tmp_path / "promo-race"
    with DurableCoordinationStore(store_dir) as setup:
        promo_one = _block(setup, "promo-one")
        promo_two = _block(setup, "promo-two")
        candidate = _block(setup, "candidate")
        auth = _block(setup, "authorization")

    lost_updates = 0

    def attempt(cid: str, operation_id: str) -> str:
        nonlocal lost_updates
        with DurableCoordinationStore(store_dir) as store:
            repo = DurablePromotionStateRepository(store)
            result = repo.compare_and_swap_promotion(
                WORKSPACE,
                expected_generation=0,
                expected_promotion_cid=None,
                new_promotion_cid=cid,
                operation_id=operation_id,
                candidate_cid=candidate,
                authorization_cid=auth,
            )
            if result.status is GovernorStoreStatus.UPDATED:
                return "updated"
            if result.status is GovernorStoreStatus.CONFLICT:
                return "conflict"
            lost_updates += 1
            return result.status.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda args: attempt(*args),
                ((promo_one, "pr-1"), (promo_two, "pr-2")),
            )
        )

    assert lost_updates == 0
    assert sorted(statuses) == ["conflict", "updated"]
    with DurableCoordinationStore(store_dir) as store:
        repo = DurablePromotionStateRepository(store)
        head = repo.current_promotion(WORKSPACE)
        assert head.generation == 1
        assert head.promotion_cid in (promo_one, promo_two)
        assert len(repo.promotion_transitions(WORKSPACE)) == 1


def test_stale_candidate_cannot_overwrite_current_policy(
    tmp_path: Path,
) -> None:
    store_dir = tmp_path / "stale-candidate"
    with DurableCoordinationStore(store_dir) as store:
        policy = DurableCompressionPolicyRepository(store)
        live = _block(store, "live")
        stale_payload = _block(store, "stale")
        updated = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=live,
            operation_id="seed",
        )
        assert updated.status is GovernorStoreStatus.UPDATED

        # Stale writer still holds generation-zero expectation.
        stale = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=stale_payload,
            operation_id="stale-writer",
        )
        assert stale.status is GovernorStoreStatus.CONFLICT
        assert stale.reason_code == "stale_expectation"
        assert stale.after.policy_cid == live
        assert policy.current_policy(WORKSPACE).policy_cid == live
        assert len(policy.policy_transitions(WORKSPACE)) == 1


def test_aba_stale_writer_blocked_across_concurrent_readers(
    tmp_path: Path,
) -> None:
    """ABA: generation pair, not CID alone, gates the write."""

    store_dir = tmp_path / "aba"
    with DurableCoordinationStore(store_dir) as store:
        policy = DurableCompressionPolicyRepository(store)
        a = _block(store, "a")
        b = _block(store, "b")
        stale = _block(store, "stale")

        r1 = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=a,
            operation_id="aba-1",
        )
        r2 = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=1,
            expected_policy_cid=a,
            new_policy_cid=b,
            operation_id="aba-2",
        )
        r3 = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=2,
            expected_policy_cid=b,
            new_policy_cid=a,
            operation_id="aba-3",
        )
        assert r3.after.generation == 3
        assert r3.after.policy_cid == a

        # Observer still holds (1, A); live is (3, A).
        conflict = policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=1,
            expected_policy_cid=a,
            new_policy_cid=stale,
            operation_id="aba-stale",
        )
        assert conflict.status is GovernorStoreStatus.CONFLICT
        assert policy.current_policy(WORKSPACE).generation == 3
        assert policy.current_policy(WORKSPACE).policy_cid == a
        assert r1.after.generation == 1
        assert r2.after.generation == 2


def test_many_concurrent_audit_writers_serialize_without_lost_updates(
    tmp_path: Path,
) -> None:
    store_dir = tmp_path / "many-audit"
    n = 8
    with DurableCoordinationStore(store_dir) as setup:
        entries = [_entry(setup, f"e-{i}") for i in range(n)]

    def attempt(index: int) -> str:
        with DurableCoordinationStore(store_dir) as store:
            repo = DurableAuditHistoryStore(store)
            # Optimistic loop: re-read head until success (bounded).
            for attempt_n in range(n + 2):
                head = repo.current_history(WORKSPACE, "audit")
                result = repo.append_audit(
                    WORKSPACE,
                    entry_cid=entries[index],
                    expected_generation=head.generation,
                    expected_head_cid=head.head_cid,
                    operation_id=f"many-{index}-try-{attempt_n}",
                )
                if result.status is GovernorStoreStatus.UPDATED:
                    return "updated"
                if result.status is not GovernorStoreStatus.CONFLICT:
                    return result.status.value
            return "exhausted"

    with ThreadPoolExecutor(max_workers=n) as pool:
        statuses = list(pool.map(attempt, range(n)))

    assert statuses.count("updated") == n
    assert "exhausted" not in statuses
    with DurableCoordinationStore(store_dir) as store:
        repo = DurableAuditHistoryStore(store)
        head = repo.current_history(WORKSPACE, "audit")
        assert head.generation == n
        assert set(repo.list_entry_cids(WORKSPACE, "audit")) == set(entries)
        assert len(repo.history_transitions(WORKSPACE, "audit")) == n
        report = recover_governor_store(store, rebuild=True)
        assert report.errors == ()
        assert report.reconstructed_history_heads[0].generation == n
