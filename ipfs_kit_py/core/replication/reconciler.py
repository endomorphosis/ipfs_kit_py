"""Idempotent replica reconciliation and anti-entropy (KITA-027).

The reconciler deliberately treats a backend inventory as an observation, not
as proof of durability.  Every replica that is to count towards placement is
read and verified against an authoritative digest and version.  Mutations are
read back before they are reported as verified, so a retry after a partial
failure is safe and converges on the same placement plan.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Final, Mapping, Protocol, Sequence

from .contracts import (
    BackendInventory,
    PlacementPlan,
    ReplicaObservation,
    ReplicaPolicy,
    ReplicaState,
)
from .integrity import (
    INTEGRITY_VERIFIER_SCHEMA,
    IntegrityError,
    IntegrityVerifier,
    ReplicaContent,
    normalize_digest,
)
from .placement import plan_placement


REPLICA_RECONCILER_SCHEMA: Final[str] = "ipfs_kit_py/core/replication/reconciler@1"
RECONCILIATION_RECEIPT_SCHEMA: Final[str] = "ipfs_kit_py/core/replication/reconciliation-receipt@1"
ReplicaReconciler_V1: Final[str] = REPLICA_RECONCILER_SCHEMA
ReconciliationReceipt_V1: Final[str] = RECONCILIATION_RECEIPT_SCHEMA
MAX_ACTIONS: Final[int] = 256


class ReconciliationError(ValueError):
    """The requested reconciliation cannot be expressed safely."""


class ReplicaBackend(Protocol):
    """Minimal storage adapter required by :class:`ReplicaReconciler`.

    ``read`` returns ``None`` when the named replica is absent.  Backends may
    raise for unavailable/partitioned services; those failures become receipt
    evidence rather than being mistaken for a missing replica.
    """

    backend_id: str

    def read(self, content_ref: str) -> ReplicaContent | None:
        """Read a replica including its exact version metadata."""

    def write(self, content_ref: str, content: ReplicaContent, *, idempotency_key: str) -> None:
        """Write a replica idempotently."""

    def delete(self, content_ref: str, *, idempotency_key: str) -> None:
        """Delete a replica idempotently."""


class ReconciliationActionKind(str, Enum):
    COPY = "copy"
    REPAIR = "repair"
    REMOVE = "remove"
    BLOCKED = "blocked"


class ReconciliationActionState(str, Enum):
    APPLIED = "applied"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"


class ReconciliationOutcome(str, Enum):
    CONVERGED = "converged"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BACKPRESSURE = "backpressure"


@dataclass(frozen=True)
class ReconciliationAction:
    """A bounded reconciliation attempt and its durable outcome evidence."""

    kind: ReconciliationActionKind
    backend_id: str
    state: ReconciliationActionState
    idempotency_key: str
    reason: str | None = None


@dataclass(frozen=True)
class ReconciliationReceipt:
    """Immutable, deterministic evidence from one reconciliation pass."""

    operation_id: str
    plan: PlacementPlan
    observations: tuple[ReplicaObservation, ...]
    actions: tuple[ReconciliationAction, ...]
    deferred_actions: int
    outcome: ReconciliationOutcome
    integrity_verifier: str = INTEGRITY_VERIFIER_SCHEMA

    @property
    def verified_backend_ids(self) -> tuple[str, ...]:
        return tuple(
            observation.backend_id
            for observation in self.observations
            if observation.counts_toward_desired
        )

    @property
    def converged(self) -> bool:
        return self.outcome is ReconciliationOutcome.CONVERGED


@dataclass(frozen=True)
class _Candidate:
    kind: ReconciliationActionKind
    backend_id: str


def _compact(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 512:
        raise ReconciliationError(f"{field} must be a compact non-empty string")
    return value.strip()


def _operation_id(
    *,
    content_ref: str,
    content_size_bytes: int,
    policy: ReplicaPolicy,
    inventory: BackendInventory,
    expected_digest: str,
    expected_version_id: str,
) -> str:
    payload = {
        "content_ref": content_ref,
        "content_size_bytes": content_size_bytes,
        "policy_content_id": policy.content_id,
        "inventory_content_id": inventory.content_id,
        "expected_digest": expected_digest,
        "expected_version_id": expected_version_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _action_key(operation_id: str, kind: ReconciliationActionKind, backend_id: str) -> str:
    value = f"{operation_id}:{kind.value}:{backend_id}".encode("utf-8")
    return "sha256:" + hashlib.sha256(value).hexdigest()


class ReplicaReconciler:
    """Plan, verify, repair, and conservatively remove content replicas.

    A caller supplies the immutable policy and inventory snapshot used to plan
    a pass.  The reconciler has no pending queue: deferred work is represented
    explicitly in the receipt and is never counted as a replica.
    """

    interface_version: Final[str] = REPLICA_RECONCILER_SCHEMA

    def __init__(
        self,
        backends: Mapping[str, ReplicaBackend],
        *,
        verifier: IntegrityVerifier | None = None,
        max_actions: int = 32,
    ) -> None:
        if not isinstance(backends, Mapping):
            raise ReconciliationError("backends must be a mapping")
        if not isinstance(max_actions, int) or isinstance(max_actions, bool) or not 1 <= max_actions <= MAX_ACTIONS:
            raise ReconciliationError(f"max_actions must be between 1 and {MAX_ACTIONS}")
        normalized: dict[str, ReplicaBackend] = {}
        for backend_id, backend in backends.items():
            backend_id = _compact(backend_id, "backend_id")
            if backend is None:
                raise ReconciliationError("backend cannot be null")
            declared_id = getattr(backend, "backend_id", backend_id)
            if declared_id != backend_id:
                raise ReconciliationError("backend mapping key must match backend_id")
            normalized[backend_id] = backend
        self._backends = normalized
        self._verifier = verifier or IntegrityVerifier()
        self._max_actions = max_actions

    def reconcile(
        self,
        *,
        content_ref: str,
        content_size_bytes: int,
        policy: ReplicaPolicy,
        inventory: BackendInventory,
        expected_digest: str,
        expected_version_id: str,
        replicas: Sequence[ReplicaObservation] = (),
        source: ReplicaContent | None = None,
        max_actions: int | None = None,
        cancel: Callable[[], bool] | None = None,
        dry_run: bool = False,
    ) -> ReconciliationReceipt:
        """Perform one bounded anti-entropy pass.

        ``expected_digest`` and ``expected_version_id`` are authoritative
        content identity.  A copied object only becomes ``VERIFIED`` after a
        write followed by a successful read-back under that identity.
        """

        content_ref = _compact(content_ref, "content_ref")
        if not isinstance(content_size_bytes, int) or isinstance(content_size_bytes, bool) or content_size_bytes <= 0:
            raise ReconciliationError("content_size_bytes must be a positive integer")
        if not isinstance(policy, ReplicaPolicy) or not isinstance(inventory, BackendInventory):
            raise ReconciliationError("policy and inventory must be replication contracts")
        expected_digest = normalize_digest(expected_digest)
        expected_version_id = _compact(expected_version_id, "expected_version_id")
        limit = self._max_actions if max_actions is None else max_actions
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= self._max_actions:
            raise ReconciliationError(f"max_actions must be between 1 and {self._max_actions}")
        if cancel is not None and not callable(cancel):
            raise ReconciliationError("cancel must be callable")
        if not isinstance(dry_run, bool):
            raise ReconciliationError("dry_run must be boolean")

        operation_id = _operation_id(
            content_ref=content_ref,
            content_size_bytes=content_size_bytes,
            policy=policy,
            inventory=inventory,
            expected_digest=expected_digest,
            expected_version_id=expected_version_id,
        )
        observations = self._initial_observations(replicas, content_ref)
        source = self._validate_source(source, expected_digest, expected_version_id)
        source, observations = self._inspect(
            observations=observations,
            content_ref=content_ref,
            inventory=inventory,
            expected_digest=expected_digest,
            expected_version_id=expected_version_id,
            source=source,
        )
        plan = plan_placement(
            content_id=content_ref,
            content_size_bytes=content_size_bytes,
            policy=policy,
            inventory=inventory,
            replicas=tuple(observations.values()),
        )
        candidates = self._candidates(plan, observations)
        actions: list[ReconciliationAction] = []
        deferred = 0
        cancelled = False
        failure = False
        blocked = False

        for index, candidate in enumerate(candidates):
            if len(actions) >= limit:
                deferred = len(candidates) - index
                break
            key = _action_key(operation_id, candidate.kind, candidate.backend_id)
            if cancel is not None and cancel():
                actions.append(
                    ReconciliationAction(candidate.kind, candidate.backend_id, ReconciliationActionState.CANCELLED, key, "cancelled")
                )
                deferred = len(candidates) - index - 1
                cancelled = True
                break
            if dry_run:
                actions.append(
                    ReconciliationAction(candidate.kind, candidate.backend_id, ReconciliationActionState.DEFERRED, key, "dry_run")
                )
                deferred = len(candidates) - index
                break
            if candidate.kind is ReconciliationActionKind.REMOVE:
                action, was_blocked = self._remove(
                    candidate=candidate,
                    key=key,
                    observations=observations,
                    policy=policy,
                    inventory=inventory,
                    content_ref=content_ref,
                    expected_digest=expected_digest,
                    expected_version_id=expected_version_id,
                )
                blocked = blocked or was_blocked
            else:
                action = self._copy_or_repair(
                    candidate=candidate,
                    key=key,
                    observations=observations,
                    source=source,
                    content_ref=content_ref,
                    expected_digest=expected_digest,
                    expected_version_id=expected_version_id,
                )
            actions.append(action)
            blocked = blocked or action.state is ReconciliationActionState.BLOCKED
            failure = failure or action.state is ReconciliationActionState.FAILED

        outcome = self._outcome(
            plan=plan,
            observations=observations,
            actions=actions,
            deferred=deferred,
            cancelled=cancelled,
            blocked=blocked,
            failure=failure,
        )
        return ReconciliationReceipt(
            operation_id=operation_id,
            plan=plan,
            observations=tuple(sorted(observations.values(), key=lambda item: (item.backend_id, item.replica_id))),
            actions=tuple(actions),
            deferred_actions=deferred,
            outcome=outcome,
        )

    def _initial_observations(
        self, replicas: Sequence[ReplicaObservation], content_ref: str
    ) -> dict[str, ReplicaObservation]:
        if isinstance(replicas, (str, bytes)) or not isinstance(replicas, Sequence):
            raise ReconciliationError("replicas must be a sequence")
        result: dict[str, ReplicaObservation] = {}
        for observation in replicas:
            if not isinstance(observation, ReplicaObservation):
                raise ReconciliationError("replicas must contain ReplicaObservation values")
            if observation.content_ref != content_ref:
                continue
            if observation.backend_id in result:
                raise ReconciliationError("at most one replica observation is permitted per backend")
            result[observation.backend_id] = observation
        return result

    def _validate_source(
        self, source: ReplicaContent | None, expected_digest: str, expected_version_id: str
    ) -> ReplicaContent | None:
        if source is None:
            return None
        result = self._verifier.verify(
            source, expected_digest=expected_digest, expected_version_id=expected_version_id
        )
        if not result.valid:
            raise IntegrityError(f"source failed integrity verification: {result.reason}")
        return source

    def _inspect(
        self,
        *,
        observations: dict[str, ReplicaObservation],
        content_ref: str,
        inventory: BackendInventory,
        expected_digest: str,
        expected_version_id: str,
        source: ReplicaContent | None,
    ) -> tuple[ReplicaContent | None, dict[str, ReplicaObservation]]:
        """Read every configured backend so an old listing cannot hide drift."""

        capabilities = {capability.backend_id: capability for capability in inventory.capabilities}
        for backend_id in sorted(capabilities):
            backend = self._backends.get(backend_id)
            old = observations.get(backend_id)
            if backend is None:
                if old is not None and old.state is ReplicaState.VERIFIED:
                    observations[backend_id] = self._observation(old, state=ReplicaState.STALE)
                continue
            try:
                found = backend.read(content_ref)
            except Exception:
                if old is not None and old.state is ReplicaState.VERIFIED:
                    observations[backend_id] = self._observation(old, state=ReplicaState.STALE)
                continue
            if found is None:
                if old is not None:
                    observations[backend_id] = self._observation(old, state=ReplicaState.CORRUPT)
                continue
            result = self._verifier.verify(
                found, expected_digest=expected_digest, expected_version_id=expected_version_id
            )
            if result.valid:
                if source is None:
                    source = found
                observations[backend_id] = ReplicaObservation(
                    replica_id=old.replica_id if old is not None else f"replica:{backend_id}",
                    content_ref=content_ref,
                    backend_id=backend_id,
                    state=ReplicaState.VERIFIED,
                    durable=True,
                    integrity_verified=True,
                )
            else:
                observations[backend_id] = self._observation(
                    old
                    or ReplicaObservation(
                        replica_id=f"replica:{backend_id}",
                        content_ref=content_ref,
                        backend_id=backend_id,
                        state=ReplicaState.CORRUPT,
                    ),
                    state=ReplicaState.CORRUPT,
                )
        return source, observations

    @staticmethod
    def _observation(observation: ReplicaObservation, *, state: ReplicaState) -> ReplicaObservation:
        return ReplicaObservation(
            replica_id=observation.replica_id,
            content_ref=observation.content_ref,
            backend_id=observation.backend_id,
            state=state,
            durable=False,
            integrity_verified=False,
        )

    @staticmethod
    def _candidates(plan: PlacementPlan, observations: Mapping[str, ReplicaObservation]) -> tuple[_Candidate, ...]:
        selected = set(plan.selected_backend_ids)
        additions = {intent.backend_id for intent in plan.intents}
        additions = tuple(
            _Candidate(
                ReconciliationActionKind.REPAIR if backend_id in observations else ReconciliationActionKind.COPY,
                backend_id,
            )
            for backend_id in sorted(additions)
            if not observations.get(backend_id, _MISSING).counts_toward_desired
        )
        removals = tuple(
            _Candidate(ReconciliationActionKind.REMOVE, backend_id)
            for backend_id, observation in sorted(observations.items())
            if observation.counts_toward_desired and backend_id not in selected
        )
        return additions + removals

    def _copy_or_repair(
        self,
        *,
        candidate: _Candidate,
        key: str,
        observations: dict[str, ReplicaObservation],
        source: ReplicaContent | None,
        content_ref: str,
        expected_digest: str,
        expected_version_id: str,
    ) -> ReconciliationAction:
        if source is None:
            return ReconciliationAction(
                candidate.kind, candidate.backend_id, ReconciliationActionState.BLOCKED, key, "no_verified_source"
            )
        backend = self._backends.get(candidate.backend_id)
        if backend is None:
            return ReconciliationAction(
                candidate.kind, candidate.backend_id, ReconciliationActionState.FAILED, key, "backend_unavailable"
            )
        try:
            backend.write(content_ref, source, idempotency_key=key)
            copied = backend.read(content_ref)
            if copied is None:
                raise _ReadbackFailed("missing_after_write")
            result = self._verifier.verify(
                copied, expected_digest=expected_digest, expected_version_id=expected_version_id
            )
            if not result.valid:
                raise _ReadbackFailed(result.reason or "readback_integrity_failure")
        except _ReadbackFailed as error:
            observations[candidate.backend_id] = self._failed_observation(
                observations.get(candidate.backend_id), content_ref, candidate.backend_id
            )
            return ReconciliationAction(candidate.kind, candidate.backend_id, ReconciliationActionState.FAILED, key, str(error))
        except Exception:
            observations[candidate.backend_id] = self._failed_observation(
                observations.get(candidate.backend_id), content_ref, candidate.backend_id
            )
            return ReconciliationAction(candidate.kind, candidate.backend_id, ReconciliationActionState.FAILED, key, "backend_error")
        observations[candidate.backend_id] = ReplicaObservation(
            replica_id=observations.get(candidate.backend_id, _MISSING).replica_id,
            content_ref=content_ref,
            backend_id=candidate.backend_id,
            state=ReplicaState.VERIFIED,
            durable=True,
            integrity_verified=True,
        )
        return ReconciliationAction(candidate.kind, candidate.backend_id, ReconciliationActionState.APPLIED, key)

    def _remove(
        self,
        *,
        candidate: _Candidate,
        key: str,
        observations: dict[str, ReplicaObservation],
        policy: ReplicaPolicy,
        inventory: BackendInventory,
        content_ref: str,
        expected_digest: str,
        expected_version_id: str,
    ) -> tuple[ReconciliationAction, bool]:
        # Re-check surviving verified replicas immediately before deletion.
        # A stale listing or a concurrent backend loss must produce an explicit
        # blocked receipt rather than allowing the durable count to fall below
        # the policy minimum.
        self._refresh_verified(
            observations=observations,
            omit_backend_id=candidate.backend_id,
            content_ref=content_ref,
            inventory=inventory,
            expected_digest=expected_digest,
            expected_version_id=expected_version_id,
        )
        survivors = sum(
            1
            for backend_id, observation in observations.items()
            if backend_id != candidate.backend_id and observation.counts_toward_desired
        )
        if survivors < policy.min_replicas:
            return (
                ReconciliationAction(
                    ReconciliationActionKind.BLOCKED,
                    candidate.backend_id,
                    ReconciliationActionState.BLOCKED,
                    key,
                    "minimum_verified_replicas",
                ),
                True,
            )
        backend = self._backends.get(candidate.backend_id)
        if backend is None:
            return (
                ReconciliationAction(candidate.kind, candidate.backend_id, ReconciliationActionState.FAILED, key, "backend_unavailable"),
                False,
            )
        try:
            backend.delete(content_ref, idempotency_key=key)
        except Exception:
            return (
                ReconciliationAction(candidate.kind, candidate.backend_id, ReconciliationActionState.FAILED, key, "backend_error"),
                False,
            )
        observations[candidate.backend_id] = self._observation(
            observations[candidate.backend_id], state=ReplicaState.REMOVED
        )
        return (ReconciliationAction(candidate.kind, candidate.backend_id, ReconciliationActionState.APPLIED, key), False)

    def _refresh_verified(
        self,
        *,
        observations: dict[str, ReplicaObservation],
        omit_backend_id: str,
        content_ref: str,
        inventory: BackendInventory,
        expected_digest: str,
        expected_version_id: str,
    ) -> None:
        known = {item.backend_id for item in inventory.capabilities}
        for backend_id, observation in tuple(observations.items()):
            if backend_id == omit_backend_id or not observation.counts_toward_desired:
                continue
            if backend_id not in known or backend_id not in self._backends:
                observations[backend_id] = self._observation(observation, state=ReplicaState.STALE)
                continue
            try:
                found = self._backends[backend_id].read(content_ref)
                valid = found is not None and self._verifier.verify(
                    found, expected_digest=expected_digest, expected_version_id=expected_version_id
                ).valid
            except Exception:
                valid = False
            if not valid:
                observations[backend_id] = self._observation(observation, state=ReplicaState.STALE)

    @staticmethod
    def _failed_observation(
        old: ReplicaObservation | None, content_ref: str, backend_id: str
    ) -> ReplicaObservation:
        if old is not None:
            return ReplicaObservation(
                replica_id=old.replica_id,
                content_ref=old.content_ref,
                backend_id=old.backend_id,
                state=ReplicaState.FAILED,
                durable=False,
                integrity_verified=False,
            )
        return ReplicaObservation(
            replica_id=f"replica:{backend_id}",
            content_ref=content_ref,
            backend_id=backend_id,
            state=ReplicaState.FAILED,
        )

    @staticmethod
    def _outcome(
        *,
        plan: PlacementPlan,
        observations: Mapping[str, ReplicaObservation],
        actions: Sequence[ReconciliationAction],
        deferred: int,
        cancelled: bool,
        blocked: bool,
        failure: bool,
    ) -> ReconciliationOutcome:
        selected = set(plan.selected_backend_ids)
        has_all_selected = all(observations.get(backend_id, _MISSING).counts_toward_desired for backend_id in selected)
        has_extra = any(
            observation.counts_toward_desired and backend_id not in selected
            for backend_id, observation in observations.items()
        )
        if cancelled:
            return ReconciliationOutcome.CANCELLED
        if blocked:
            return ReconciliationOutcome.BLOCKED
        if deferred:
            return ReconciliationOutcome.BACKPRESSURE
        if failure:
            return ReconciliationOutcome.FAILED
        if has_all_selected and not has_extra:
            return ReconciliationOutcome.CONVERGED
        return ReconciliationOutcome.PARTIAL


_MISSING = ReplicaObservation(
    replica_id="missing",
    content_ref="missing",
    backend_id="missing",
    state=ReplicaState.FAILED,
)


class _ReadbackFailed(Exception):
    pass


__all__ = [
    "MAX_ACTIONS",
    "RECONCILIATION_RECEIPT_SCHEMA",
    "REPLICA_RECONCILER_SCHEMA",
    "ReconciliationAction",
    "ReconciliationActionKind",
    "ReconciliationActionState",
    "ReconciliationError",
    "ReconciliationOutcome",
    "ReconciliationReceipt",
    "ReconciliationReceipt_V1",
    "ReplicaBackend",
    "ReplicaReconciler",
    "ReplicaReconciler_V1",
]
