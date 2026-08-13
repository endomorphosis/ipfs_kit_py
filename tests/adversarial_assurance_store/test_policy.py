"""Fail-closed vectors for assurance-policy revision and promotion CAS (AAE-037).

Acceptance:

* Promotion requires exact candidate/evaluation/authorization identities and
  expected-old revision
* Stale or concurrent writers fail without overwriting newer policy
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

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.adversarial_assurance_store.contracts import (
    AssuranceNamespaceRole,
    AssuranceStoreStatus,
    assurance_namespace,
)
from ipfs_kit_py.adversarial_assurance_store.policy import (
    ASSURANCE_POLICY_REPOSITORY_INTERFACE,
    POLICY_CAS_SCHEMA,
    POLICY_MODULE_INTERFACE,
    PROMOTION_MODULE_INTERFACE,
    AssurancePolicyAdmissionError,
    AssurancePolicyRepository,
    DurableAssurancePolicyRepository,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _block(store: DurableCoordinationStore, name: str, **extra: Any) -> str:
    payload = {"schema": "example/assurance-policy@1", "name": name}
    payload.update(extra)
    return store.put(payload, expected_cid=cid_for_artifact(payload), replicate=False)[
        "cid"
    ]


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "assurance-policy-cas-store"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def policy_repo(
    coordination: DurableCoordinationStore,
) -> DurableAssurancePolicyRepository:
    return DurableAssurancePolicyRepository(coordination)


WORKSPACE = "worker-1"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_module_interfaces_are_versioned() -> None:
    assert ASSURANCE_POLICY_REPOSITORY_INTERFACE == "AssurancePolicyRepository@1"
    assert POLICY_MODULE_INTERFACE == "AssurancePolicyRepository@1"
    assert PROMOTION_MODULE_INTERFACE == "AssurancePromotionStateRepository@1"
    assert POLICY_CAS_SCHEMA.endswith("@1")


def test_repository_satisfies_protocol_shape(
    policy_repo: DurableAssurancePolicyRepository,
) -> None:
    for name in (
        "current_policy",
        "compare_and_swap_policy",
        "promote_policy",
        "current_promotion",
        "compare_and_swap_promotion",
    ):
        assert callable(getattr(policy_repo, name))
        assert hasattr(AssurancePolicyRepository, name)


# ---------------------------------------------------------------------------
# Policy CAS: happy path, idempotency, stale expectations
# ---------------------------------------------------------------------------


def test_policy_starts_at_generation_zero(
    policy_repo: DurableAssurancePolicyRepository,
) -> None:
    head = policy_repo.current_policy(WORKSPACE)
    assert head.generation == 0
    assert head.policy_cid is None
    assert head.transition_cid is None
    assert head.namespace == assurance_namespace(
        WORKSPACE, AssuranceNamespaceRole.POLICY
    )
    assert "semantic-governor/" not in head.namespace
    assert head.namespace.startswith("adversarial-assurance/")


def test_policy_cas_publishes_successor_and_replays_idempotently(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
) -> None:
    first = _block(coordination, "policy-v1")
    updated = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=first,
        operation_id="policy-publish-1",
    )
    assert updated.status is AssuranceStoreStatus.UPDATED
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
    assert replay.status is AssuranceStoreStatus.UNCHANGED
    assert replay.reason_code == "idempotent_replay"
    assert replay.after == updated.after
    assert replay.transition_cid is None
    assert len(policy_repo.policy_transitions(WORKSPACE)) == 1


def test_stale_policy_expectation_cannot_overwrite_current(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
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
    assert updated.status is AssuranceStoreStatus.UPDATED

    stale_generation = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=second,
        operation_id="policy-stale-gen",
    )
    assert stale_generation.status is AssuranceStoreStatus.CONFLICT
    assert stale_generation.reason_code == "stale_expectation"
    assert stale_generation.after == updated.after

    stale_cid = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=1,
        expected_policy_cid=second,
        new_policy_cid=third,
        operation_id="policy-stale-cid",
    )
    assert stale_cid.status is AssuranceStoreStatus.CONFLICT
    assert policy_repo.current_policy(WORKSPACE).policy_cid == first
    assert len(policy_repo.policy_transitions(WORKSPACE)) == 1


def test_operation_id_reuse_with_different_payload_conflicts(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
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
    assert reuse.status is AssuranceStoreStatus.CONFLICT
    assert reuse.reason_code == "operation_id_reused"
    assert policy_repo.current_policy(WORKSPACE).policy_cid == first


def test_policy_rejects_incoherent_expectations_and_same_cid(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
) -> None:
    cid = _block(coordination, "policy-x")
    with pytest.raises(AssurancePolicyAdmissionError):
        policy_repo.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=cid,
            new_policy_cid=_block(coordination, "policy-y"),
            operation_id="bad-zero",
        )
    with pytest.raises(AssurancePolicyAdmissionError):
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
    with pytest.raises(AssurancePolicyAdmissionError, match="must differ"):
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
    policy_repo: DurableAssurancePolicyRepository,
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
    assert r1.status is AssuranceStoreStatus.UPDATED
    assert r1.after.generation == 1

    r2 = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=1,
        expected_policy_cid=a,
        new_policy_cid=b,
        operation_id="aba-2",
    )
    assert r2.status is AssuranceStoreStatus.UPDATED
    assert r2.after.generation == 2

    r3 = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=2,
        expected_policy_cid=b,
        new_policy_cid=a,
        operation_id="aba-3",
    )
    assert r3.status is AssuranceStoreStatus.UPDATED
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
    assert stale.status is AssuranceStoreStatus.CONFLICT
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
            repo = DurableAssurancePolicyRepository(store)
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
        repo = DurableAssurancePolicyRepository(store)
        head = repo.current_policy(WORKSPACE)
        assert head.generation == 1
        assert head.policy_cid in (one, two)
        assert len(repo.policy_transitions(WORKSPACE)) == 1


def test_concurrent_promote_policy_writers_yield_at_most_one_success(
    store_dir: Path,
) -> None:
    with DurableCoordinationStore(store_dir) as setup:
        one = _block(setup, "promote-one")
        two = _block(setup, "promote-two")
        candidate = _block(setup, "candidate")
        evaluation = _block(setup, "evaluation")
        auth = _block(setup, "authorization")

    def attempt(cid: str, operation_id: str) -> str:
        with DurableCoordinationStore(store_dir) as store:
            repo = DurableAssurancePolicyRepository(store)
            result = repo.promote_policy(
                WORKSPACE,
                expected_generation=0,
                expected_policy_cid=None,
                new_policy_cid=cid,
                operation_id=operation_id,
                candidate_cid=candidate,
                evaluation_cid=evaluation,
                authorization_cid=auth,
            )
            return result.status.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda args: attempt(*args),
                ((one, "promo-w1"), (two, "promo-w2")),
            )
        )

    assert sorted(statuses) == ["conflict", "updated"]
    with DurableCoordinationStore(store_dir) as store:
        repo = DurableAssurancePolicyRepository(store)
        head = repo.current_policy(WORKSPACE)
        assert head.generation == 1
        assert head.policy_cid in (one, two)
        assert len(repo.policy_transitions(WORKSPACE)) == 1


# ---------------------------------------------------------------------------
# Promotion: identities + expected-old revision
# ---------------------------------------------------------------------------


def test_promotion_requires_pairwise_distinct_identities(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
) -> None:
    candidate = _block(coordination, "self-candidate")
    evaluation = _block(coordination, "self-eval")
    promo = _block(coordination, "self-promo")

    with pytest.raises(
        AssurancePolicyAdmissionError, match="cannot authorize its own promotion"
    ):
        policy_repo.promote_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=promo,
            operation_id="self-promote",
            candidate_cid=candidate,
            evaluation_cid=evaluation,
            authorization_cid=candidate,
        )

    with pytest.raises(
        AssurancePolicyAdmissionError, match="candidate_cid must differ from evaluation"
    ):
        policy_repo.promote_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=promo,
            operation_id="cand-eq-eval",
            candidate_cid=candidate,
            evaluation_cid=candidate,
            authorization_cid=_block(coordination, "auth-x"),
        )

    with pytest.raises(
        AssurancePolicyAdmissionError, match="evaluation_cid must differ from authorization"
    ):
        policy_repo.promote_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=promo,
            operation_id="eval-eq-auth",
            candidate_cid=candidate,
            evaluation_cid=evaluation,
            authorization_cid=evaluation,
        )

    head = policy_repo.current_policy(WORKSPACE)
    assert head.generation == 0
    assert head.policy_cid is None
    assert policy_repo.policy_transitions(WORKSPACE) == []


def test_promote_policy_binds_identities_and_expected_old_revision(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
) -> None:
    candidate = _block(coordination, "cand-1")
    evaluation = _block(coordination, "eval-1")
    auth = _block(coordination, "auth-1")
    policy_v1 = _block(coordination, "policy-1")
    policy_v2 = _block(coordination, "policy-2")

    first = policy_repo.promote_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=policy_v1,
        operation_id="promote-1",
        candidate_cid=candidate,
        evaluation_cid=evaluation,
        authorization_cid=auth,
    )
    assert first.status is AssuranceStoreStatus.UPDATED
    assert first.candidate_cid == candidate
    assert first.evaluation_cid == evaluation
    assert first.authorization_cid == auth
    assert first.expected_old_policy_generation == 0
    assert first.expected_old_policy_cid is None
    assert first.after.policy_cid == policy_v1
    assert first.after.generation == 1
    assert policy_repo.current_policy(WORKSPACE) == first.after

    # Stale expected-old revision cannot overwrite the newer policy head.
    stale = policy_repo.promote_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=policy_v2,
        operation_id="promote-stale",
        candidate_cid=candidate,
        evaluation_cid=evaluation,
        authorization_cid=auth,
    )
    assert stale.status is AssuranceStoreStatus.CONFLICT
    assert stale.reason_code == "stale_expectation"
    assert stale.after.policy_cid == policy_v1
    assert stale.expected_old_policy_generation == 0
    assert policy_repo.current_policy(WORKSPACE).policy_cid == policy_v1
    assert len(policy_repo.policy_transitions(WORKSPACE)) == 1

    advanced = policy_repo.promote_policy(
        WORKSPACE,
        expected_generation=1,
        expected_policy_cid=policy_v1,
        new_policy_cid=policy_v2,
        operation_id="promote-2",
        candidate_cid=candidate,
        evaluation_cid=evaluation,
        authorization_cid=auth,
    )
    assert advanced.status is AssuranceStoreStatus.UPDATED
    assert advanced.expected_old_policy_generation == 1
    assert advanced.expected_old_policy_cid == policy_v1
    assert advanced.after.generation == 2
    assert advanced.after.policy_cid == policy_v2


def test_promote_policy_idempotent_replay_and_changed_reuse(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
) -> None:
    candidate = _block(coordination, "cand-r")
    evaluation = _block(coordination, "eval-r")
    auth = _block(coordination, "auth-r")
    policy = _block(coordination, "policy-r")
    other = _block(coordination, "policy-other")

    first = policy_repo.promote_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=policy,
        operation_id="promote-once",
        candidate_cid=candidate,
        evaluation_cid=evaluation,
        authorization_cid=auth,
    )
    assert first.status is AssuranceStoreStatus.UPDATED

    replay = policy_repo.promote_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=policy,
        operation_id="promote-once",
        candidate_cid=candidate,
        evaluation_cid=evaluation,
        authorization_cid=auth,
    )
    assert replay.status is AssuranceStoreStatus.UNCHANGED
    assert replay.reason_code == "idempotent_replay"
    assert replay.candidate_cid == candidate
    assert replay.evaluation_cid == evaluation
    assert replay.authorization_cid == auth

    reuse = policy_repo.promote_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=other,
        operation_id="promote-once",
        candidate_cid=candidate,
        evaluation_cid=evaluation,
        authorization_cid=auth,
    )
    assert reuse.status is AssuranceStoreStatus.CONFLICT
    assert reuse.reason_code == "operation_id_reused"
    assert policy_repo.current_policy(WORKSPACE).policy_cid == policy


# ---------------------------------------------------------------------------
# Promotion-state CAS with expected-old policy revision gate
# ---------------------------------------------------------------------------


def test_promotion_state_cas_requires_live_expected_old_policy(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
) -> None:
    candidate = _block(coordination, "cand-p")
    evaluation = _block(coordination, "eval-p")
    auth = _block(coordination, "auth-p")
    policy = _block(coordination, "policy-live")
    promo = _block(coordination, "promo-head")
    promo_next = _block(coordination, "promo-next")

    # Seed a live policy revision first.
    seeded = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=policy,
        operation_id="seed-policy",
    )
    assert seeded.status is AssuranceStoreStatus.UPDATED

    # Wrong expected-old policy revision is rejected without mutation.
    stale_policy = policy_repo.compare_and_swap_promotion(
        WORKSPACE,
        expected_generation=0,
        expected_promotion_cid=None,
        new_promotion_cid=promo,
        operation_id="promo-stale-policy",
        candidate_cid=candidate,
        evaluation_cid=evaluation,
        authorization_cid=auth,
        expected_old_policy_generation=0,
        expected_old_policy_cid=None,
    )
    assert stale_policy.status is AssuranceStoreStatus.CONFLICT
    assert stale_policy.reason_code == "stale_policy_revision"
    assert policy_repo.current_promotion(WORKSPACE).generation == 0
    assert policy_repo.promotion_transitions(WORKSPACE) == []
    # Policy head unchanged.
    assert policy_repo.current_policy(WORKSPACE).policy_cid == policy

    updated = policy_repo.compare_and_swap_promotion(
        WORKSPACE,
        expected_generation=0,
        expected_promotion_cid=None,
        new_promotion_cid=promo,
        operation_id="promo-1",
        candidate_cid=candidate,
        evaluation_cid=evaluation,
        authorization_cid=auth,
        expected_old_policy_generation=1,
        expected_old_policy_cid=policy,
    )
    assert updated.status is AssuranceStoreStatus.UPDATED
    assert updated.candidate_cid == candidate
    assert updated.evaluation_cid == evaluation
    assert updated.authorization_cid == auth
    assert updated.expected_old_policy_generation == 1
    assert updated.expected_old_policy_cid == policy
    assert updated.after.promotion_cid == promo
    assert updated.after.generation == 1

    # Stale promotion expectation cannot overwrite.
    stale_promo = policy_repo.compare_and_swap_promotion(
        WORKSPACE,
        expected_generation=0,
        expected_promotion_cid=None,
        new_promotion_cid=promo_next,
        operation_id="promo-stale-head",
        candidate_cid=candidate,
        evaluation_cid=evaluation,
        authorization_cid=auth,
        expected_old_policy_generation=1,
        expected_old_policy_cid=policy,
    )
    assert stale_promo.status is AssuranceStoreStatus.CONFLICT
    assert policy_repo.current_promotion(WORKSPACE).promotion_cid == promo


def test_promotion_state_rejects_self_authorization(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
) -> None:
    candidate = _block(coordination, "cand-self")
    evaluation = _block(coordination, "eval-self")
    promo = _block(coordination, "promo-self")
    with pytest.raises(
        AssurancePolicyAdmissionError, match="cannot authorize its own promotion"
    ):
        policy_repo.compare_and_swap_promotion(
            WORKSPACE,
            expected_generation=0,
            expected_promotion_cid=None,
            new_promotion_cid=promo,
            operation_id="self-auth",
            candidate_cid=candidate,
            evaluation_cid=evaluation,
            authorization_cid=candidate,
            expected_old_policy_generation=0,
            expected_old_policy_cid=None,
        )
    assert policy_repo.current_promotion(WORKSPACE).generation == 0


# ---------------------------------------------------------------------------
# Rollback preserves history
# ---------------------------------------------------------------------------


def test_rollback_policy_advances_generation_and_preserves_transitions(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
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
    assert r1.status is AssuranceStoreStatus.UPDATED
    r2 = policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=1,
        expected_policy_cid=v1,
        new_policy_cid=v2,
        operation_id="roll-2",
    )
    assert r2.status is AssuranceStoreStatus.UPDATED
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
    assert rolled.status is AssuranceStoreStatus.UPDATED
    assert rolled.after.policy_cid == v1
    assert rolled.after.generation == 4
    assert rolled.transition_cid is not None
    assert rolled.transition_cid not in transition_cids_before

    history_after = policy_repo.policy_transitions(WORKSPACE)
    assert len(history_after) == 4
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
        operation_id="roll-stale",
    )
    assert stale.status is AssuranceStoreStatus.CONFLICT
    assert policy_repo.current_policy(WORKSPACE).policy_cid == v1
    assert policy_repo.current_policy(WORKSPACE).generation == 4


def test_rollback_rejects_unpublished_target(
    coordination: DurableCoordinationStore,
    policy_repo: DurableAssurancePolicyRepository,
) -> None:
    published = _block(coordination, "published")
    unpublished = _block(coordination, "unpublished")
    policy_repo.compare_and_swap_policy(
        WORKSPACE,
        expected_generation=0,
        expected_policy_cid=None,
        new_policy_cid=published,
        operation_id="pub-1",
    )
    with pytest.raises(
        AssurancePolicyAdmissionError, match="not a previously published"
    ):
        policy_repo.rollback_policy(
            WORKSPACE,
            expected_generation=1,
            expected_policy_cid=published,
            target_policy_cid=unpublished,
            operation_id="bad-roll",
        )
