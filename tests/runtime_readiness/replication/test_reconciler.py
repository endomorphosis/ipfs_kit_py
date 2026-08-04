from __future__ import annotations

import pytest

from ipfs_kit_py.core.replication.contracts import (
    BackendCapability,
    BackendInventory,
    ReplicaObservation,
    ReplicaPolicy,
    ReplicaState,
)
from ipfs_kit_py.core.replication.integrity import (
    IntegrityVerifier,
    ReplicaContent,
)
from ipfs_kit_py.core.replication.reconciler import (
    ReconciliationActionKind,
    ReconciliationActionState,
    ReconciliationOutcome,
    ReplicaReconciler,
)


CONTENT_REF = "cid:runtime-readiness-object"
CONTENT = ReplicaContent(b"authoritative payload", "version-1")
DIGEST = IntegrityVerifier().digest(CONTENT.payload)


class MemoryBackend:
    def __init__(self, backend_id: str, content: ReplicaContent | None = None) -> None:
        self.backend_id = backend_id
        self.objects = {} if content is None else {CONTENT_REF: content}
        self.fail_reads = False
        self.fail_writes = False
        self.fail_deletes = False
        self.hide_after_reads: int | None = None
        self.read_count = 0
        self.writes: list[tuple[str, ReplicaContent]] = []
        self.deletes: list[str] = []

    def read(self, content_ref: str) -> ReplicaContent | None:
        self.read_count += 1
        if self.fail_reads:
            raise OSError("backend unavailable")
        if self.hide_after_reads is not None and self.read_count > self.hide_after_reads:
            return None
        return self.objects.get(content_ref)

    def write(
        self, content_ref: str, content: ReplicaContent, *, idempotency_key: str
    ) -> None:
        if self.fail_writes:
            raise OSError("write failed")
        self.writes.append((content_ref, content))
        self.objects[content_ref] = content

    def delete(self, content_ref: str, *, idempotency_key: str) -> None:
        if self.fail_deletes:
            raise OSError("delete failed")
        self.deletes.append(content_ref)
        self.objects.pop(content_ref, None)


def make_inventory(*backend_ids: str) -> BackendInventory:
    return BackendInventory(
        "snapshot-1",
        tuple(
            BackendCapability(backend_id, f"domain-{index}", 4096)
            for index, backend_id in enumerate(backend_ids)
        ),
    )


def make_policy(
    *, minimum: int = 1, desired: int = 2, maximum: int | None = None
) -> ReplicaPolicy:
    maximum = desired if maximum is None else maximum
    return ReplicaPolicy("policy-1", minimum, desired, maximum, maximum)


def observation(backend_id: str, state: ReplicaState) -> ReplicaObservation:
    verified = state is ReplicaState.VERIFIED
    return ReplicaObservation(
        f"replica-{backend_id}",
        CONTENT_REF,
        backend_id,
        state,
        durable=verified,
        integrity_verified=verified,
    )


def test_repeated_reconciliation_converges_to_identical_plan_and_state() -> None:
    backends = {
        "backend-a": MemoryBackend("backend-a", CONTENT),
        "backend-b": MemoryBackend("backend-b"),
        "backend-c": MemoryBackend("backend-c"),
    }
    reconciler = ReplicaReconciler(backends)
    kwargs = dict(
        content_ref=CONTENT_REF,
        content_size_bytes=len(CONTENT.payload),
        expected_digest=DIGEST,
        expected_version_id=CONTENT.version_id,
        policy=make_policy(desired=2, maximum=3),
        inventory=make_inventory(*backends),
    )

    first = reconciler.reconcile(**kwargs)
    second = reconciler.reconcile(replicas=first.observations, **kwargs)
    third = reconciler.reconcile(replicas=second.observations, **kwargs)

    assert first.outcome is ReconciliationOutcome.CONVERGED
    assert second.outcome is third.outcome is ReconciliationOutcome.CONVERGED
    assert second.plan == third.plan
    assert second.observations == third.observations
    assert not second.actions
    assert len(backends["backend-b"].writes) == 1


def test_pending_and_queued_work_never_counts_toward_desired_replicas() -> None:
    backends = {
        "backend-a": MemoryBackend("backend-a", CONTENT),
        "backend-b": MemoryBackend("backend-b"),
    }
    receipt = ReplicaReconciler(backends).reconcile(
        content_ref=CONTENT_REF,
        content_size_bytes=len(CONTENT.payload),
        expected_digest=DIGEST,
        expected_version_id=CONTENT.version_id,
        policy=make_policy(),
        inventory=make_inventory(*backends),
        replicas=(
            observation("backend-a", ReplicaState.VERIFIED),
            observation("backend-b", ReplicaState.QUEUED),
        ),
        dry_run=True,
    )

    assert receipt.plan.retained_backend_ids == ("backend-a",)
    assert receipt.plan.planned_backend_ids == ("backend-b",)
    assert receipt.actions[0].state is ReconciliationActionState.DEFERRED
    assert receipt.outcome is ReconciliationOutcome.BACKPRESSURE
    assert not backends["backend-b"].writes


@pytest.mark.parametrize(
    "bad_content",
    (
        ReplicaContent(b"corrupt payload", "version-1"),
        ReplicaContent(CONTENT.payload, "version-stale"),
    ),
)
def test_repair_requires_readback_content_and_version_verification(
    bad_content: ReplicaContent,
) -> None:
    backends = {
        "backend-a": MemoryBackend("backend-a", CONTENT),
        "backend-b": MemoryBackend("backend-b", bad_content),
    }
    receipt = ReplicaReconciler(backends).reconcile(
        content_ref=CONTENT_REF,
        content_size_bytes=len(CONTENT.payload),
        expected_digest=DIGEST,
        expected_version_id=CONTENT.version_id,
        policy=make_policy(),
        inventory=make_inventory(*backends),
    )

    repair = next(action for action in receipt.actions if action.backend_id == "backend-b")
    assert repair.kind is ReconciliationActionKind.REPAIR
    assert repair.state is ReconciliationActionState.APPLIED
    assert backends["backend-b"].objects[CONTENT_REF] == CONTENT
    assert receipt.outcome is ReconciliationOutcome.CONVERGED


def test_provider_declared_digest_cannot_forge_integrity() -> None:
    result = IntegrityVerifier().verify(
        ReplicaContent(CONTENT.payload, CONTENT.version_id, "sha256:" + "0" * 64),
        expected_digest=DIGEST,
        expected_version_id=CONTENT.version_id,
    )

    assert not result.valid
    assert result.reason == "declared_digest_mismatch"


def test_backend_failure_leaves_recoverable_state_for_retry() -> None:
    backends = {
        "backend-a": MemoryBackend("backend-a", CONTENT),
        "backend-b": MemoryBackend("backend-b"),
    }
    backends["backend-b"].fail_writes = True
    reconciler = ReplicaReconciler(backends)
    kwargs = dict(
        content_ref=CONTENT_REF,
        content_size_bytes=len(CONTENT.payload),
        expected_digest=DIGEST,
        expected_version_id=CONTENT.version_id,
        policy=make_policy(),
        inventory=make_inventory(*backends),
    )

    failed = reconciler.reconcile(**kwargs)
    backends["backend-b"].fail_writes = False
    retried = reconciler.reconcile(replicas=failed.observations, **kwargs)

    assert failed.actions[0].state is ReconciliationActionState.FAILED
    assert any(item.state is ReplicaState.FAILED for item in failed.observations)
    assert retried.outcome is ReconciliationOutcome.CONVERGED
    assert backends["backend-b"].objects[CONTENT_REF] == CONTENT


def test_cancellation_and_backpressure_are_bounded() -> None:
    backends = {
        "backend-a": MemoryBackend("backend-a", CONTENT),
        "backend-b": MemoryBackend("backend-b"),
        "backend-c": MemoryBackend("backend-c"),
    }
    kwargs = dict(
        content_ref=CONTENT_REF,
        content_size_bytes=len(CONTENT.payload),
        expected_digest=DIGEST,
        expected_version_id=CONTENT.version_id,
        policy=make_policy(desired=3, maximum=3),
        inventory=make_inventory(*backends),
    )

    limited = ReplicaReconciler(backends, max_actions=1).reconcile(**kwargs)
    cancelled = ReplicaReconciler(backends).reconcile(
        **kwargs, cancel=lambda: True
    )

    assert len(limited.actions) == 1
    assert limited.deferred_actions == 1
    assert limited.outcome is ReconciliationOutcome.BACKPRESSURE
    assert len(cancelled.actions) == 1
    assert cancelled.actions[0].state is ReconciliationActionState.CANCELLED
    assert cancelled.outcome is ReconciliationOutcome.CANCELLED


def test_removal_is_blocked_when_fresh_verification_would_break_minimum() -> None:
    backends = {
        "backend-a": MemoryBackend("backend-a", CONTENT),
        "backend-b": MemoryBackend("backend-b", CONTENT),
        "backend-c": MemoryBackend("backend-c", CONTENT),
    }
    # The original listing appears healthy, but the second verification pass
    # reveals a stale replica before the candidate deletion is allowed.
    backends["backend-b"].hide_after_reads = 1

    receipt = ReplicaReconciler(backends).reconcile(
        content_ref=CONTENT_REF,
        content_size_bytes=len(CONTENT.payload),
        expected_digest=DIGEST,
        expected_version_id=CONTENT.version_id,
        policy=make_policy(minimum=2, desired=2, maximum=3),
        inventory=make_inventory(*backends),
    )

    blocked = next(action for action in receipt.actions if action.backend_id == "backend-c")
    assert blocked.kind is ReconciliationActionKind.BLOCKED
    assert blocked.state is ReconciliationActionState.BLOCKED
    assert not backends["backend-c"].deletes
    assert receipt.outcome is ReconciliationOutcome.BLOCKED
