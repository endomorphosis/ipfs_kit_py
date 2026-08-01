"""Pure deterministic placement planning for replica contracts (KITA-026)."""

from __future__ import annotations

from collections.abc import Sequence

from ipfs_kit_py.core.replication.contracts import (
    BackendCapability,
    BackendInventory,
    PlacementIntent,
    PlacementPlan,
    PlacementUnsatisfiableError,
    ReplicaContractError,
    ReplicaObservation,
    ReplicaPolicy,
)


def _preference_key(capability: BackendCapability, policy: ReplicaPolicy) -> tuple[int, int, str]:
    """Stable preference order; never depend on provider inventory ordering."""

    try:
        preference = policy.preferred_backends.index(capability.backend_id)
    except ValueError:
        preference = len(policy.preferred_backends)
    # Enum declaration order is the explicit cost order in the contract.
    cost = tuple(type(capability.cost_tier)).index(capability.cost_tier)
    return (preference, cost, capability.backend_id)


def _eligible_verified_replicas(
    *,
    content_id: str,
    policy: ReplicaPolicy,
    inventory: BackendInventory,
    content_size_bytes: int,
    replicas: Sequence[ReplicaObservation],
) -> tuple[BackendCapability, ...]:
    """Select at most one verified durable replica per failure domain."""

    by_backend = inventory.by_backend_id
    candidates: list[BackendCapability] = []
    seen_replica_ids: set[str] = set()
    for replica in replicas:
        if not isinstance(replica, ReplicaObservation):
            raise ReplicaContractError("replicas must contain ReplicaObservation records")
        if replica.replica_id in seen_replica_ids:
            raise ReplicaContractError("replicas cannot contain duplicate replica_id values")
        seen_replica_ids.add(replica.replica_id)
        if replica.content_ref != content_id or not replica.counts_toward_desired:
            continue
        capability = by_backend.get(replica.backend_id)
        # A stale/ineligible capability cannot be silently used to satisfy the
        # current policy.  ``require_writable=False`` is intentional here:
        # this is evidence of an already durable replica, not a new mutation.
        if capability is not None and capability.supports(policy, content_size_bytes, require_writable=False):
            candidates.append(capability)

    selected: list[BackendCapability] = []
    domains: set[str] = set()
    for capability in sorted(candidates, key=lambda item: _preference_key(item, policy)):
        if capability.failure_domain not in domains:
            selected.append(capability)
            domains.add(capability.failure_domain)
    return tuple(selected)


def plan_placement(
    *,
    content_id: str,
    content_size_bytes: int,
    policy: ReplicaPolicy,
    inventory: BackendInventory,
    replicas: Sequence[ReplicaObservation] = (),
) -> PlacementPlan:
    """Return a deterministic, non-mutating placement plan or raise.

    Validation is complete before a plan is constructed.  There are no
    callbacks, writes, reservations, or mutation handles in this module, so an
    invalid policy or an unsatisfiable snapshot has zero effects by design.
    """

    if not isinstance(policy, ReplicaPolicy):
        raise ReplicaContractError("policy must be a ReplicaPolicy")
    if not isinstance(inventory, BackendInventory):
        raise ReplicaContractError("inventory must be a BackendInventory")
    # Trigger the same compact identifier/int checks used by records before
    # observing any candidate.  A tiny ephemeral observation is sufficient and
    # avoids duplicating validation logic in this pure function.
    probe = ReplicaObservation(
        replica_id="placement-probe",
        content_ref=content_id,
        backend_id=inventory.capabilities[0].backend_id,
        state="planned",
    )
    del probe
    if isinstance(content_size_bytes, bool) or not isinstance(content_size_bytes, int) or content_size_bytes <= 0:
        raise ReplicaContractError("content_size_bytes must be a positive integer")
    if not isinstance(replicas, Sequence) or isinstance(replicas, (str, bytes, bytearray)):
        raise ReplicaContractError("replicas must be a sequence")

    writable = inventory.eligible_capabilities(policy, content_size_bytes)
    writable_domains = {capability.failure_domain for capability in writable}
    # Critical capacity is checked before returning any copy intent, even when
    # pre-existing replicas already meet desired count.  This avoids admitting
    # a policy that cannot tolerate its declared critical requirement.
    if len(writable_domains) < policy.critical_replicas:
        raise PlacementUnsatisfiableError(
            "inventory lacks distinct writable failure domains for critical_replicas"
        )

    retained = list(
        _eligible_verified_replicas(
            content_id=content_id,
            policy=policy,
            inventory=inventory,
            content_size_bytes=content_size_bytes,
            replicas=replicas,
        )
    )
    retained = retained[: policy.desired_replicas]
    selected_domains = {capability.failure_domain for capability in retained}
    selected_backends = {capability.backend_id for capability in retained}

    additions: list[BackendCapability] = []
    for capability in sorted(writable, key=lambda item: _preference_key(item, policy)):
        if len(retained) + len(additions) >= policy.desired_replicas:
            break
        if capability.backend_id in selected_backends or capability.failure_domain in selected_domains:
            continue
        additions.append(capability)
        selected_backends.add(capability.backend_id)
        selected_domains.add(capability.failure_domain)

    if len(retained) + len(additions) != policy.desired_replicas:
        raise PlacementUnsatisfiableError(
            "inventory lacks enough distinct writable failure domains for desired_replicas"
        )

    return PlacementPlan(
        content_ref=content_id,
        content_size_bytes=content_size_bytes,
        policy_content_id=policy.content_id,
        inventory_content_id=inventory.content_id,
        desired_replicas=policy.desired_replicas,
        retained_backend_ids=tuple(item.backend_id for item in retained),
        retained_failure_domains=tuple(item.failure_domain for item in retained),
        intents=tuple(
            PlacementIntent(backend_id=item.backend_id, failure_domain=item.failure_domain)
            for item in additions
        ),
    )


# A noun-first alias is convenient for adapters without expanding behavior.
build_placement_plan = plan_placement

__all__ = ["build_placement_plan", "plan_placement"]
