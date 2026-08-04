"""Acceptance tests for the closed replica-policy and placement contracts."""

from __future__ import annotations

from typing import Any

import pytest

from ipfs_kit_py.core.operation_contracts import InconsistentStateError
from ipfs_kit_py.core.replication.contracts import (
    BACKEND_CAPABILITY_SCHEMA,
    PLACEMENT_PLAN_SCHEMA,
    REPLICA_POLICY_SCHEMA,
    BackendCapability,
    BackendInventory,
    ConsistencyLevel,
    CostTier,
    EncryptionLevel,
    PlacementIntent,
    PlacementPlan,
    PlacementUnsatisfiableError,
    ReplicaObservation,
    ReplicaPolicy,
    ReplicaPolicyError,
    ReplicaState,
    RetentionLevel,
    assert_legal_replica_transition,
)
from ipfs_kit_py.core.replication.placement import plan_placement


def policy(**overrides: Any) -> ReplicaPolicy:
    values: dict[str, Any] = {
        "policy_id": "policy:runtime-readiness",
        "min_replicas": 1,
        "desired_replicas": 2,
        "max_replicas": 2,
        "critical_replicas": 2,
    }
    values.update(overrides)
    return ReplicaPolicy(**values)


def backend(backend_id: str, failure_domain: str, **overrides: Any) -> BackendCapability:
    values: dict[str, Any] = {
        "backend_id": backend_id,
        "failure_domain": failure_domain,
        "available_bytes": 10_000,
    }
    values.update(overrides)
    return BackendCapability(**values)


def inventory(*capabilities: BackendCapability) -> BackendInventory:
    return BackendInventory(snapshot_id="snapshot:exact-1", capabilities=capabilities)


def test_schema_aliases_and_lifecycle_are_closed() -> None:
    assert REPLICA_POLICY_SCHEMA.endswith("@1")
    assert BACKEND_CAPABILITY_SCHEMA.endswith("@1")
    assert PLACEMENT_PLAN_SCHEMA.endswith("@1")
    assert ReplicaState.VERIFIED.value == "verified"
    assert ReplicaState.QUEUED.value == "queued"
    assert ReplicaState.COPYING.value == "copying"

    assert_legal_replica_transition(ReplicaState.PLANNED, ReplicaState.PENDING)
    with pytest.raises(InconsistentStateError):
        assert_legal_replica_transition(ReplicaState.VERIFIED, ReplicaState.COPYING)


@pytest.mark.parametrize(
    ("minimum", "desired", "maximum", "critical"),
    [
        (2, 1, 2, 2),
        (1, 2, 1, 2),
        (1, 1, 2, 1),
    ],
)
def test_policy_rejects_every_invalid_cardinality_order(
    minimum: int, desired: int, maximum: int, critical: int
) -> None:
    with pytest.raises(ReplicaPolicyError):
        policy(
            min_replicas=minimum,
            desired_replicas=desired,
            max_replicas=maximum,
            critical_replicas=critical,
        )


def test_policy_rejects_overlapping_and_inconsistent_backend_sets() -> None:
    with pytest.raises(ReplicaPolicyError):
        policy(preferred_backends=("backend:a",), excluded_backends=("backend:a",))
    with pytest.raises(ReplicaPolicyError):
        policy(allowed_backends=("backend:b",), excluded_backends=("backend:b",))
    with pytest.raises(ReplicaPolicyError):
        policy(preferred_backends=("backend:a",), allowed_backends=("backend:b",))


def test_capability_requires_all_declared_policy_dimensions() -> None:
    requirements = policy(
        required_consistency=ConsistencyLevel.STRONG,
        required_encryption=EncryptionLevel.CUSTOMER_MANAGED,
        required_retention=RetentionLevel.ARCHIVAL,
        max_cost_tier=CostTier.STANDARD,
        required_localities=("locality:eu",),
    )
    eligible = backend("backend:eligible", "domain:a", localities=("locality:eu",))
    assert eligible.supports(requirements, 100)

    assert not backend("backend:cost", "domain:b", cost_tier=CostTier.PREMIUM, localities=("locality:eu",)).supports(requirements, 100)
    assert not backend("backend:locality", "domain:c").supports(requirements, 100)
    assert not backend("backend:integrity", "domain:d", supports_integrity_verification=False, localities=("locality:eu",)).supports(requirements, 100)
    assert not backend("backend:capacity", "domain:e", available_bytes=99, localities=("locality:eu",)).supports(requirements, 100)


def test_only_durable_integrity_verified_observations_count() -> None:
    verified = ReplicaObservation(
        replica_id="replica:verified",
        content_ref="cid:object-1",
        backend_id="backend:a",
        state=ReplicaState.VERIFIED,
        durable=True,
        integrity_verified=True,
    )
    copied = ReplicaObservation(
        replica_id="replica:copied",
        content_ref="cid:object-1",
        backend_id="backend:b",
        state=ReplicaState.COPIED,
        durable=True,
    )
    assert verified.counts_toward_desired
    assert not copied.counts_toward_desired

    with pytest.raises(InconsistentStateError):
        ReplicaObservation(
            replica_id="replica:forged",
            content_ref="cid:object-1",
            backend_id="backend:c",
            state=ReplicaState.VERIFIED,
            durable=True,
        )


def test_placement_is_deterministic_and_bound_to_exact_snapshot() -> None:
    requirements = policy(preferred_backends=("backend:b",))
    a = backend("backend:a", "domain:a")
    b = backend("backend:b", "domain:b")
    c = backend("backend:c", "domain:c")
    unordered = inventory(c, a, b)
    ordered = inventory(a, b, c)

    first = plan_placement(
        content_id="cid:object-1", content_size_bytes=100, policy=requirements, inventory=unordered
    )
    second = plan_placement(
        content_id="cid:object-1", content_size_bytes=100, policy=requirements, inventory=ordered
    )

    assert unordered.content_id == ordered.content_id
    assert first.content_id == second.content_id
    assert first.policy_content_id == requirements.content_id
    assert first.inventory_content_id == unordered.content_id
    assert first.content_ref == "cid:object-1"
    assert set(first.planned_backend_ids) == {"backend:a", "backend:b"}


def test_verified_durable_replicas_are_retained_but_unverified_copies_are_not() -> None:
    requirements = policy()
    current = inventory(
        backend("backend:a", "domain:a"),
        backend("backend:b", "domain:b"),
        backend("backend:c", "domain:c"),
    )
    replicas = (
        ReplicaObservation(
            replica_id="replica:a",
            content_ref="cid:object-1",
            backend_id="backend:a",
            state=ReplicaState.VERIFIED,
            durable=True,
            integrity_verified=True,
        ),
        ReplicaObservation(
            replica_id="replica:b",
            content_ref="cid:object-1",
            backend_id="backend:b",
            state=ReplicaState.COPIED,
            durable=True,
        ),
    )

    result = plan_placement(
        content_id="cid:object-1",
        content_size_bytes=100,
        policy=requirements,
        inventory=current,
        replicas=replicas,
    )
    assert result.retained_backend_ids == ("backend:a",)
    assert result.retained_failure_domains == ("domain:a",)
    assert result.planned_backend_ids == ("backend:b",)


def test_placement_plan_cannot_encode_duplicate_failure_domains() -> None:
    with pytest.raises(InconsistentStateError):
        PlacementPlan(
            content_ref="cid:object-1",
            content_size_bytes=100,
            policy_content_id="sha256:" + ("a" * 64),
            inventory_content_id="sha256:" + ("b" * 64),
            desired_replicas=2,
            retained_backend_ids=("backend:a",),
            retained_failure_domains=("domain:shared",),
            intents=(PlacementIntent("backend:b", "domain:shared"),),
        )


def test_invalid_or_unsatisfiable_placement_emits_no_intents_or_effects() -> None:
    requirements = policy()
    insufficient = inventory(
        backend("backend:a", "domain:shared"),
        backend("backend:b", "domain:shared"),
    )
    before = insufficient.to_record()

    with pytest.raises(PlacementUnsatisfiableError):
        plan_placement(
            content_id="cid:object-1",
            content_size_bytes=100,
            policy=requirements,
            inventory=insufficient,
        )

    # Contract objects are immutable, and the pure planner exposes no mutation
    # operation: rejection leaves the exact input inventory unchanged.
    assert insufficient.to_record() == before
