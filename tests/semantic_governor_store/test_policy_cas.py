"""Fail-closed vectors for versioned policy and promotion CAS (SCG-021).

Acceptance:

* candidate cannot promote itself
* stale candidate cannot overwrite current
* ABA and concurrent writers yield at most one success
* rollback preserves history
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    CompressionPolicyRepository,
    GovernorStoreStatus,
    PromotionStateRepository,
    governor_namespace,
)
from ipfs_kit_py.semantic_governor_store.policy import (
    POLICY_CAS_SCHEMA,
    POLICY_MODULE_INTERFACE,
    PROMOTION_MODULE_INTERFACE,
    DurableCompressionPolicyRepository,
    DurablePolicyCASRepositories,
    DurablePromotionStateRepository,
    GovernorPolicyAdmissionError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _block(store: DurableCoordinationStore, name: str, **extra: Any) -> str:
    payload = {"schema": "example/governor-policy@1", "name": name}
    payload.update(extra)
    return store.put(payload, expected_cid=cid_for_artifact(payload), replicate=False)[
        "cid"
    ]


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "policy-cas-store"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def policy_repo(
    coordination: DurableCoordinationStore,
) -> DurableCompressionPolicyRepository:
    return DurableCompressionPolicyRepository(coordination)


@pytest.fixture()
def promotion_repo(
    coordination: DurableCoordinationStore,
) -> DurablePromotionStateRepository:
    return DurablePromotionStateRepository(coordination)


@pytest.fixture()
def cas(
    coordination: DurableCoordinationStore,
) -> DurablePolicyCASRepositories:
    return DurablePolicyCASRepositories(coordination)


WORKSPACE = "default"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_module_interfaces_are_versioned() -> None:
    assert POLICY_MODULE_INTERFACE == "DurableCompressionPolicyRepository@1"
    assert PROMOTION_MODULE_INTERFACE == "DurablePromotionStateRepository@1"
    assert POLICY_CAS_SCHEMA.endswith("@1")


def test_repositories_satisfy_protocol_shapes(
    policy_repo: DurableCompressionPolicyRepository,
    promotion_repo: DurablePromotionStateRepository,
) -> None:
    # Protocols are not @runtime_checkable; assert the closed method surface.
    for name in ("current_policy", "compare_and_swap_policy"):
        assert callable(getattr(policy_repo, name))
        assert hasattr(CompressionPolicyRepository, name)
    for name in ("current_promotion", "compare_and_swap_promotion"):
        assert callable(getattr(promotion_repo, name))
        assert hasattr(PromotionStateRepository, name)


# ---------------------------------------------------------------------------
# Policy CAS happy path, idempotency, and stale expectations
# ---------------------------------------------------------------------------


def test_policy_starts_at_generation_zero(
    policy_repo: DurableCompressionPolicyRepository,
) -> None:
    head = policy_repo.current_policy(WORKSPACE)
    assert head.generation == 0
    assert head.policy_cid is None
    assert head.transition_cid is None
    assert head.namespace == governor_namespace(WORKSPACE, "policy")


def test_policy_cas_publishes_successor_and_replays_idempotently(
    coordination: DurableCoordinationStore,
    policy_repo: DurableCompressionPolicyRepository,
) -> None:
    first = _block(coordination, "policy-v1")
    updated = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=first,
        operation_id="policy-publish-1",
    )
    assert updated.status is GovernorStoreStatus.UPDATED
    assert updated.before.generation == 0
    assert updated.after.generation == 1
    assert updated.after.policy_cid == first
    assert updated.transition_cid == updated.after.transition_cid
    assert updated.local_durable is True
    assert policy_repo.current_policy(WORKSPACE) == updated.after

    replay = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=first,
        operation_id="policy-publish-1",
    )
    assert replay.status is GovernorStoreStatus.UNCHANGED
    assert replay.reason_code == "idempotent_replay"
    assert replay.after == updated.after
    assert replay.transition_cid is None
    assert len(policy_repo.policy_transitions(WORKSPACE)) == 1


def test_stale_policy_expectation_cannot_overwrite_current(
    coordination: DurableCoordinationStore,
    policy_repo: DurableCompressionPolicyRepository,
) -> None:
    first = _block(coordination, "policy-v1")
    second = _block(coordination, "policy-v2")
    third = _block(coordination, "policy-v3")

    updated = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=first,
        operation_id="policy-1",
    )
    assert updated.status is GovernorStoreStatus.UPDATED

    stale_generation = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=second,
        operation_id="policy-stale-gen",
    )
    assert stale_generation.status is GovernorStoreStatus.CONFLICT
    assert stale_generation.reason_code == "stale_expectation"
    assert stale_generation.after == updated.after

    stale_cid = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=1,
        expected_policy_cid=second,
        new_policy_cid=third,
        operation_id="policy-stale-cid",
    )
    assert stale_cid.status is GovernorStoreStatus.CONFLICT
    assert policy_repo.current_policy(WORKSPACE).policy_cid == first
    assert len(policy_repo.policy_transitions(WORKSPACE)) == 1


def test_operation_id_reuse_with_different_payload_conflicts(
    coordination: DurableCoordinationStore,
    policy_repo: DurableCompressionPolicyRepository,
) -> None:
    first = _block(coordination, "policy-a")
    other = _block(coordination, "policy-b")
    policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=first,
        operation_id="once",
    )
    reuse = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=other,
        operation_id="once",
    )
    assert reuse.status is GovernorStoreStatus.CONFLICT
    assert reuse.reason_code == "operation_id_reused"
    assert policy_repo.current_policy(WORKSPACE).policy_cid == first


def test_policy_rejects_incoherent_expectations_and_same_cid(
    coordination: DurableCoordinationStore,
    policy_repo: DurableCompressionPolicyRepository,
) -> None:
    cid = _block(coordination, "policy-x")
    with pytest.raises(GovernorPolicyAdmissionError):
        policy_repo.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=cid,
            new_policy_cid=_block(coordination, "policy-y"),
            operation_id="bad-zero",
        )
    with pytest.raises(GovernorPolicyAdmissionError):
        policy_repo.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=1,
            expected_policy_cid=None,
            new_policy_cid=cid,
            operation_id="bad-nonzero",
        )
    policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=cid,
        operation_id="seed",
    )
    with pytest.raises(GovernorPolicyAdmissionError, match="must differ"):
        policy_repo.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=1,
            expected_policy_cid=cid,
            new_policy_cid=cid,
            operation_id="same-cid",
        )


# ---------------------------------------------------------------------------
# ABA safety
# ---------------------------------------------------------------------------


def test_aba_policy_generation_pair_blocks_stale_writer(
    coordination: DurableCoordinationStore,
    policy_repo: DurableCompressionPolicyRepository,
) -> None:
    """Writer observing (gen=1, A) must fail after A→B→A even though CID is A again."""

    a = _block(coordination, "aba-a")
    b = _block(coordination, "aba-b")
    stale_payload = _block(coordination, "aba-stale")

    r1 = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=a,
        operation_id="aba-1",
    )
    assert r1.status is GovernorStoreStatus.UPDATED
    assert r1.after.generation == 1

    r2 = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=1,
        expected_policy_cid=a,
        new_policy_cid=b,
        operation_id="aba-2",
    )
    assert r2.status is GovernorStoreStatus.UPDATED
    assert r2.after.generation == 2

    r3 = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=2,
        expected_policy_cid=b,
        new_policy_cid=a,
        operation_id="aba-3",
    )
    assert r3.status is GovernorStoreStatus.UPDATED
    assert r3.after.generation == 3
    assert r3.after.policy_cid == a

    # Stale observer still holds expected (1, A); live is (3, A).
    stale = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=1,
        expected_policy_cid=a,
        new_policy_cid=stale_payload,
        operation_id="aba-stale",
    )
    assert stale.status is GovernorStoreStatus.CONFLICT
    assert stale.reason_code == "stale_expectation"
    head = policy_repo.current_policy(WORKSPACE)
    assert head.generation == 3
    assert head.policy_cid == a
    assert len(policy_repo.policy_transitions(WORKSPACE)) == 3


# ---------------------------------------------------------------------------
# Concurrent writers
# ---------------------------------------------------------------------------


def test_concurrent_policy_writers_yield_at_most_one_success(
    store_dir: Path,
) -> None:
    with DurableCoordinationStore(store_dir) as setup:
        one = _block(setup, "concurrent-one")
        two = _block(setup, "concurrent-two")

    def attempt(cid: str, operation_id: str) -> str:
        with DurableCoordinationStore(store_dir) as store:
            repo = DurableCompressionPolicyRepository(store)
            result = repo.compare_and_swap_policy(
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
    with DurableCoordinationStore(store_dir) as store:
        repo = DurableCompressionPolicyRepository(store)
        head = repo.current_policy(WORKSPACE)
        assert head.generation == 1
        assert head.policy_cid in (one, two)
        assert len(repo.policy_transitions(WORKSPACE)) == 1


def test_concurrent_promotion_writers_yield_at_most_one_success(
    store_dir: Path,
) -> None:
    with DurableCoordinationStore(store_dir) as setup:
        promo_one = _block(setup, "promo-one")
        promo_two = _block(setup, "promo-two")
        candidate = _block(setup, "candidate")
        auth = _block(setup, "authorization")

    def attempt(cid: str, operation_id: str) -> str:
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
            return result.status.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda args: attempt(*args),
                ((promo_one, "promo-w1"), (promo_two, "promo-w2")),
            )
        )

    assert sorted(statuses) == ["conflict", "updated"]
    with DurableCoordinationStore(store_dir) as store:
        repo = DurablePromotionStateRepository(store)
        head = repo.current_promotion(WORKSPACE)
        assert head.generation == 1
        assert head.promotion_cid in (promo_one, promo_two)
        assert len(repo.promotion_transitions(WORKSPACE)) == 1


# ---------------------------------------------------------------------------
# Promotion: self-auth forbidden, stale blocked
# ---------------------------------------------------------------------------


def test_candidate_cannot_promote_itself(
    coordination: DurableCoordinationStore,
    promotion_repo: DurablePromotionStateRepository,
) -> None:
    candidate = _block(coordination, "self-candidate")
    promo = _block(coordination, "self-promo")
    with pytest.raises(
        GovernorPolicyAdmissionError, match="cannot authorize its own promotion"
    ):
        promotion_repo.compare_and_swap_promotion(
            WORKSPACE,
            expected_generation=0,
            expected_promotion_cid=None,
            new_promotion_cid=promo,
            operation_id="self-promote",
            candidate_cid=candidate,
            authorization_cid=candidate,
        )
    head = promotion_repo.current_promotion(WORKSPACE)
    assert head.generation == 0
    assert head.promotion_cid is None
    assert promotion_repo.promotion_transitions(WORKSPACE) == []


def test_promotion_cas_requires_distinct_authorization_and_updates(
    coordination: DurableCoordinationStore,
    promotion_repo: DurablePromotionStateRepository,
) -> None:
    candidate = _block(coordination, "cand-1")
    auth = _block(coordination, "auth-1")
    promo = _block(coordination, "promo-1")
    next_promo = _block(coordination, "promo-2")

    updated = promotion_repo.compare_and_swap_promotion(
        WORKSPACE,
        expected_generation=0,
        expected_promotion_cid=None,
        new_promotion_cid=promo,
        operation_id="promote-1",
        candidate_cid=candidate,
        authorization_cid=auth,
    )
    assert updated.status is GovernorStoreStatus.UPDATED
    assert updated.candidate_cid == candidate
    assert updated.authorization_cid == auth
    assert updated.after.promotion_cid == promo
    assert updated.after.generation == 1

    stale = promotion_repo.compare_and_swap_promotion(
        WORKSPACE,
        expected_generation=0,
        expected_promotion_cid=None,
        new_promotion_cid=next_promo,
        operation_id="promote-stale",
        candidate_cid=candidate,
        authorization_cid=auth,
    )
    assert stale.status is GovernorStoreStatus.CONFLICT
    assert stale.after.promotion_cid == promo

    advanced = promotion_repo.compare_and_swap_promotion(
        WORKSPACE,
        expected_generation=1,
        expected_promotion_cid=promo,
        new_promotion_cid=next_promo,
        operation_id="promote-2",
        candidate_cid=candidate,
        authorization_cid=auth,
    )
    assert advanced.status is GovernorStoreStatus.UPDATED
    assert advanced.after.generation == 2
    assert advanced.after.promotion_cid == next_promo


def test_promotion_idempotent_replay_and_changed_reuse(
    coordination: DurableCoordinationStore,
    promotion_repo: DurablePromotionStateRepository,
) -> None:
    candidate = _block(coordination, "cand-r")
    auth = _block(coordination, "auth-r")
    promo = _block(coordination, "promo-r")
    other = _block(coordination, "promo-other")

    first = promotion_repo.compare_and_swap_promotion(
        WORKSPACE,
        expected_generation=0,
        expected_promotion_cid=None,
        new_promotion_cid=promo,
        operation_id="promote-once",
        candidate_cid=candidate,
        authorization_cid=auth,
    )
    assert first.status is GovernorStoreStatus.UPDATED

    replay = promotion_repo.compare_and_swap_promotion(
        WORKSPACE,
        expected_generation=0,
        expected_promotion_cid=None,
        new_promotion_cid=promo,
        operation_id="promote-once",
        candidate_cid=candidate,
        authorization_cid=auth,
    )
    assert replay.status is GovernorStoreStatus.UNCHANGED
    assert replay.reason_code == "idempotent_replay"

    reuse = promotion_repo.compare_and_swap_promotion(
        WORKSPACE,
        expected_generation=0,
        expected_promotion_cid=None,
        new_promotion_cid=other,
        operation_id="promote-once",
        candidate_cid=candidate,
        authorization_cid=auth,
    )
    assert reuse.status is GovernorStoreStatus.CONFLICT
    assert reuse.reason_code == "operation_id_reused"


# ---------------------------------------------------------------------------
# Rollback preserves history
# ---------------------------------------------------------------------------


def test_rollback_policy_advances_generation_and_preserves_transitions(
    coordination: DurableCoordinationStore,
    policy_repo: DurableCompressionPolicyRepository,
) -> None:
    v1 = _block(coordination, "roll-v1")
    v2 = _block(coordination, "roll-v2")
    v3 = _block(coordination, "roll-v3")

    r1 = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=v1,
        operation_id="roll-1",
    )
    r2 = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=1,
        expected_policy_cid=v1,
        new_policy_cid=v2,
        operation_id="roll-2",
    )
    r3 = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=2,
        expected_policy_cid=v2,
        new_policy_cid=v3,
        operation_id="roll-3",
    )
    assert r3.after.generation == 3
    history_before = policy_repo.policy_transitions(WORKSPACE)
    assert len(history_before) == 3
    transition_cids_before = [row["transition_cid"] for row in history_before]

    rolled = policy_repo.rollback_policy(
        WORKSPACE,
        expected_generation=3,
        expected_policy_cid=v3,
        target_policy_cid=v1,
        operation_id="roll-back-to-v1",
    )
    assert rolled.status is GovernorStoreStatus.UPDATED
    assert rolled.after.policy_cid == v1
    assert rolled.after.generation == 4
    assert rolled.transition_cid is not None
    assert rolled.transition_cid not in transition_cids_before

    history_after = policy_repo.policy_transitions(WORKSPACE)
    assert len(history_after) == 4
    # All prior transition evidence remains; order is generational.
    assert [row["transition_cid"] for row in history_after[:3]] == transition_cids_before
    assert history_after[0]["new_root_cid"] == v1
    assert history_after[1]["new_root_cid"] == v2
    assert history_after[2]["new_root_cid"] == v3
    assert history_after[3]["new_root_cid"] == v1
    assert history_after[3]["new_revision"] == 4

    # Stale writer holding the pre-rollback head still cannot overwrite.
    stale = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=3,
        expected_policy_cid=v3,
        new_policy_cid=v2,
        operation_id="post-rollback-stale",
    )
    assert stale.status is GovernorStoreStatus.CONFLICT
    assert policy_repo.current_policy(WORKSPACE).policy_cid == v1


def test_rollback_rejects_unpublished_target(
    coordination: DurableCoordinationStore,
    policy_repo: DurableCompressionPolicyRepository,
) -> None:
    v1 = _block(coordination, "only-v1")
    unpublished = _block(coordination, "never-published")
    policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=v1,
        operation_id="only-1",
    )
    with pytest.raises(GovernorPolicyAdmissionError, match="previously published"):
        policy_repo.rollback_policy(
            WORKSPACE,
            expected_generation=1,
            expected_policy_cid=v1,
            target_policy_cid=unpublished,
            operation_id="bad-rollback",
        )
    assert policy_repo.current_policy(WORKSPACE).policy_cid == v1
    assert len(policy_repo.policy_transitions(WORKSPACE)) == 1


# ---------------------------------------------------------------------------
# Missing successor / facade
# ---------------------------------------------------------------------------


def test_missing_successor_is_unavailable_without_head_mutation(
    policy_repo: DurableCompressionPolicyRepository,
) -> None:
    # Valid dag-json CID spelling that is not present in the block store.
    missing = cid_for_artifact(
        {"schema": "example/governor-policy@1", "name": "never-stored"}
    )
    result = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=missing,
        operation_id="missing-successor",
    )
    assert result.status is GovernorStoreStatus.UNAVAILABLE
    assert result.reason_code == "successor_unavailable"
    assert result.after.generation == 0
    assert policy_repo.current_policy(WORKSPACE).generation == 0


def test_combined_facade_isolates_policy_and_promotion_namespaces(
    coordination: DurableCoordinationStore,
    cas: DurablePolicyCASRepositories,
) -> None:
    policy_cid = _block(coordination, "facade-policy")
    promo_cid = _block(coordination, "facade-promo")
    candidate = _block(coordination, "facade-cand")
    auth = _block(coordination, "facade-auth")

    p = cas.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=policy_cid,
        operation_id="facade-policy-1",
    )
    m = cas.compare_and_swap_promotion(
        WORKSPACE,
        expected_generation=0,
        expected_promotion_cid=None,
        new_promotion_cid=promo_cid,
        operation_id="facade-promo-1",
        candidate_cid=candidate,
        authorization_cid=auth,
    )
    assert p.status is GovernorStoreStatus.UPDATED
    assert m.status is GovernorStoreStatus.UPDATED
    assert cas.current_policy(WORKSPACE).policy_cid == policy_cid
    assert cas.current_promotion(WORKSPACE).promotion_cid == promo_cid
    # Independent history streams.
    assert len(cas.policy_transitions(WORKSPACE)) == 1
    assert len(cas.promotion_transitions(WORKSPACE)) == 1
    assert cas.policy_transitions(WORKSPACE)[0]["namespace"].endswith("/policy")
    assert cas.promotion_transitions(WORKSPACE)[0]["namespace"].endswith("/promotion")


def test_independent_workspaces_do_not_collide(
    coordination: DurableCoordinationStore,
    policy_repo: DurableCompressionPolicyRepository,
) -> None:
    a = _block(coordination, "ws-a")
    b = _block(coordination, "ws-b")
    ra = policy_repo.compare_and_swap_policy(
        "alpha",
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=a,
        operation_id="ws-alpha",
    )
    rb = policy_repo.compare_and_swap_policy(
        "beta",
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=b,
        operation_id="ws-beta",
    )
    assert ra.status is GovernorStoreStatus.UPDATED
    assert rb.status is GovernorStoreStatus.UPDATED
    assert policy_repo.current_policy("alpha").policy_cid == a
    assert policy_repo.current_policy("beta").policy_cid == b
