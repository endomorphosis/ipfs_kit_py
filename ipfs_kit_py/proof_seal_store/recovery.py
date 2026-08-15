"""Deterministic seal-transition recovery and ambiguous-outcome policy (IPS-025).

Kit never decides proof validity and never infers external prover success.
Recovery inspects the durable WAL prefix, optional admitted artifacts, and the
current-seal pointer, then produces a closed disposition for every open or
recoverable transition:

* ``resume`` — durable intent exists and later work has not started
* ``replay`` — verified later-phase artifacts exist; resume the next phase
* ``verify-existing`` — rehash durable artifacts before advancing
* ``discard-uncommitted`` — partial work cannot become current
* ``repair`` — preserve the verified WAL prefix / finalize post-CAS cleanup
* ``full-reproof`` — ambiguous prover outcome; require a new proof

Recovery is deterministic and idempotent.  A second restart against the same
durable state yields the same dispositions and does not re-publish a seal
when the expected parent is no longer current.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ArtifactReference,
    CurrentSealPointer,
    ExplicitRootRequiredError,
    ProofSealStoreContractError,
    SealTransitionPhase,
    SealTransitionRecord,
    SealTransitionState,
    StoreRoot,
    validate_explicit_root_path,
)
from ipfs_kit_py.proof_seal_store.local_store import HermeticProofSealStore
from ipfs_kit_py.proof_seal_store.pointer import (
    CurrentSealRepository,
    PointerReason,
)
from ipfs_kit_py.proof_seal_store.wal import (
    PHASE_ORDER,
    SealTransitionWal,
    WalDisposition,
    WalReason,
    abort_transition,
    commit_transition,
    phase_index,
)

EVIDENCE_SUBSET: Final[str] = "ips/transition-recovery@1"
RECOVERY_SCHEMA: Final[str] = "ipfs_kit_py/proof_seal_store/recovery@1"
RECOVERY_INTERFACE: Final[str] = "recover_seal_transitions@1"
CONTRACT_VERSION: Final[int] = 1

# Closed recovery dispositions (task Interfaces + plan §9).
REQUIRED_RECOVERY_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {
        "resume",
        "replay",
        "verify-existing",
        "discard-uncommitted",
        "repair",
        "full-reproof",
    }
)

# Artifact kinds that may bind a durable prover object (never inferred).
_PROVER_KINDS: Final[tuple[ArtifactKind, ...]] = (
    ArtifactKind.PROOF_OBJECT,
    ArtifactKind.PROOF_RECEIPT,
)
_RECEIPT_KINDS: Final[tuple[ArtifactKind, ...]] = (ArtifactKind.PROOF_RECEIPT,)
_FOREST_KINDS: Final[tuple[ArtifactKind, ...]] = (ArtifactKind.MERKLE_NODE,)
_AGGREGATE_KINDS: Final[tuple[ArtifactKind, ...]] = (
    ArtifactKind.PROOF_MANIFEST,
    ArtifactKind.MERKLE_NODE,
)
_SEAL_KINDS: Final[tuple[ArtifactKind, ...]] = (
    ArtifactKind.CHECKPOINT_SEAL,
    ArtifactKind.DELTA_SEAL,
)


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


class RecoveryDisposition(str, Enum):
    """Closed recovery actions for every seal-transition phase."""

    RESUME = "resume"
    REPLAY = "replay"
    VERIFY_EXISTING = "verify-existing"
    DISCARD_UNCOMMITTED = "discard-uncommitted"
    REPAIR = "repair"
    FULL_REPROOF = "full-reproof"


class RecoveryReason(str, Enum):
    """Closed diagnostic reasons for recovery decisions."""

    OK = "ok"
    UNSTARTED = "unstarted"
    AMBIGUOUS_PROVER = "ambiguous_prover"
    VERIFIED_ARTIFACT = "verified_artifact"
    MISSING_ARTIFACT = "missing_artifact"
    STALE_PARENT = "stale_parent"
    POINTER_MATCHES_SEAL = "pointer_matches_seal"
    COMMITTED_PREFIX = "committed_prefix"
    CORRUPT_TAIL = "corrupt_tail"
    ABORTED = "aborted"
    ALREADY_TERMINAL = "already_terminal"
    UNCOMMITTED = "uncommitted"
    PUBLICATION_REJECTED = "publication_rejected"
    IDEMPOTENT = "idempotent"


class AmbiguousProverPolicy(str, Enum):
    """Closed policy for after-proof / before-receipt crashes."""

    FULL_REPROOF = "full-reproof"
    DISCARD_UNCOMMITTED = "discard-uncommitted"


# ---------------------------------------------------------------------------
# Errors / results
# ---------------------------------------------------------------------------


class SealTransitionRecoveryError(ProofSealStoreContractError):
    """A recovery operation failed closed."""

    def __init__(
        self,
        message: str,
        *,
        reason: RecoveryReason = RecoveryReason.UNCOMMITTED,
        disposition: RecoveryDisposition | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.disposition = disposition


@dataclass(frozen=True)
class RecoveryPolicy:
    """Bounded recovery policy.  Prover success is never inferred."""

    ambiguous_prover: AmbiguousProverPolicy = AmbiguousProverPolicy.FULL_REPROOF
    apply_mutations: bool = True

    def __post_init__(self) -> None:
        policy = self.ambiguous_prover
        if isinstance(policy, str):
            try:
                policy = AmbiguousProverPolicy(policy)
            except ValueError as exc:
                raise SealTransitionRecoveryError(
                    f"unknown ambiguous_prover policy: {self.ambiguous_prover!r}",
                    reason=RecoveryReason.UNCOMMITTED,
                ) from exc
            object.__setattr__(self, "ambiguous_prover", policy)
        if not isinstance(self.ambiguous_prover, AmbiguousProverPolicy):
            raise SealTransitionRecoveryError(
                "ambiguous_prover must be a closed AmbiguousProverPolicy",
                reason=RecoveryReason.UNCOMMITTED,
            )
        if type(self.apply_mutations) is not bool:
            raise SealTransitionRecoveryError(
                "apply_mutations must be a bool",
                reason=RecoveryReason.UNCOMMITTED,
            )


DEFAULT_RECOVERY_POLICY: Final[RecoveryPolicy] = RecoveryPolicy()


@dataclass(frozen=True)
class TransitionRecoveryDecision:
    """One transition's deterministic recovery decision."""

    transition_id: str
    repository_id: str
    branch_id: str
    phase: SealTransitionPhase
    state: SealTransitionState
    disposition: RecoveryDisposition
    reason: RecoveryReason
    applied: bool = False
    publication_rejected: bool = False
    pointer_recognized: bool = False
    verified_artifact_cids: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RECOVERY_SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "transition_id": self.transition_id,
            "repository_id": self.repository_id,
            "branch_id": self.branch_id,
            "phase": self.phase.value,
            "state": self.state.value,
            "disposition": self.disposition.value,
            "reason": self.reason.value,
            "applied": self.applied,
            "publication_rejected": self.publication_rejected,
            "pointer_recognized": self.pointer_recognized,
            "verified_artifact_cids": list(self.verified_artifact_cids),
            "diagnostics": dict(self.diagnostics),
        }


@dataclass(frozen=True)
class RecoveryReport:
    """Deterministic recovery outcome for a store root."""

    decisions: tuple[TransitionRecoveryDecision, ...]
    repaired_tail: bool = False
    evidence_subset: str = EVIDENCE_SUBSET

    def __bool__(self) -> bool:
        return True

    @property
    def dispositions(self) -> tuple[RecoveryDisposition, ...]:
        return tuple(item.disposition for item in self.decisions)

    def decision_for(self, transition_id: str) -> TransitionRecoveryDecision:
        for item in self.decisions:
            if item.transition_id == transition_id:
                return item
        raise SealTransitionRecoveryError(
            f"no recovery decision for {transition_id!r}",
            reason=RecoveryReason.UNCOMMITTED,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RECOVERY_SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "evidence_subset": self.evidence_subset,
            "repaired_tail": self.repaired_tail,
            "decisions": [item.to_dict() for item in self.decisions],
        }


# ---------------------------------------------------------------------------
# Artifact verification helpers
# ---------------------------------------------------------------------------


def _as_store_root(
    root: StoreRoot | str | Path | os.PathLike[str] | None,
) -> StoreRoot:
    if root is None:
        raise ExplicitRootRequiredError(
            "recover_seal_transitions requires an explicit StoreRoot; "
            "no default user-state or daemon root exists"
        )
    if isinstance(root, StoreRoot):
        store_root = root
    else:
        store_root = StoreRoot.require(root)
    validate_explicit_root_path(store_root.root_path, field_name="root_path")
    return store_root


def _verify_cid(
    store: HermeticProofSealStore | None,
    cid: str,
    kinds: Sequence[ArtifactKind],
) -> tuple[bool, ArtifactKind | None]:
    """Rehash ``cid`` against admitted bytes.  Absence is not success."""

    if store is None or not cid:
        return False, None
    for kind in kinds:
        try:
            reference = ArtifactReference(cid=cid, kind=kind)
        except ProofSealStoreContractError:
            continue
        try:
            if store.contains(reference):
                return True, kind
        except ProofSealStoreContractError:
            continue
    return False, None


def _verified_cids(
    store: HermeticProofSealStore | None,
    cids: Sequence[str],
    kinds: Sequence[ArtifactKind],
) -> tuple[str, ...]:
    found: list[str] = []
    for cid in cids:
        ok, _kind = _verify_cid(store, cid, kinds)
        if ok:
            found.append(cid)
    return tuple(found)


def _current_pointer(
    pointers: CurrentSealRepository | None,
    repository_id: str,
    branch_id: str,
) -> CurrentSealPointer | None:
    if pointers is None:
        return None
    return pointers.get_current_seal(repository_id, branch_id)


def _parent_is_current(
    pointer: CurrentSealPointer | None,
    record: SealTransitionRecord,
) -> bool:
    """Whether CAS may still publish ``record`` against the expected parent."""

    expected = record.expected_parent_seal_cid
    if pointer is None:
        return expected == ""
    return pointer.seal_cid == expected


def _pointer_equals_new_seal(
    pointer: CurrentSealPointer | None,
    record: SealTransitionRecord,
) -> bool:
    if pointer is None or not record.new_seal_cid:
        return False
    if pointer.seal_cid != record.new_seal_cid:
        return False
    if record.new_seal_kind is not None and pointer.seal_kind != record.new_seal_kind:
        return False
    return (
        pointer.repository_id == record.repository_id
        and pointer.branch_id == record.branch_id
    )


def _is_terminal(state: SealTransitionState) -> bool:
    return state in {
        SealTransitionState.COMMITTED,
        SealTransitionState.ABORTED,
        SealTransitionState.FAILED,
    }


# ---------------------------------------------------------------------------
# Phase policy (plan §9)
# ---------------------------------------------------------------------------


def disposition_for_phase(
    phase: SealTransitionPhase,
    *,
    has_verified_artifact: bool,
    pointer_matches_seal: bool,
    parent_is_current: bool,
    ambiguous_prover: AmbiguousProverPolicy,
    state: SealTransitionState,
) -> tuple[RecoveryDisposition, RecoveryReason]:
    """Return the closed (disposition, reason) for one durable phase."""

    if state is SealTransitionState.ABORTED or state is SealTransitionState.FAILED:
        return RecoveryDisposition.DISCARD_UNCOMMITTED, RecoveryReason.ABORTED
    if state is SealTransitionState.COMMITTED:
        if pointer_matches_seal:
            return RecoveryDisposition.REPAIR, RecoveryReason.POINTER_MATCHES_SEAL
        return RecoveryDisposition.REPAIR, RecoveryReason.COMMITTED_PREFIX

    if phase is SealTransitionPhase.INTENT:
        return RecoveryDisposition.RESUME, RecoveryReason.UNSTARTED

    if phase is SealTransitionPhase.PROOF_EXECUTION:
        # Never guess prover success.  A durable rehashed artifact may be
        # verified; otherwise the outcome is ambiguous.
        if has_verified_artifact:
            return RecoveryDisposition.VERIFY_EXISTING, RecoveryReason.VERIFIED_ARTIFACT
        if ambiguous_prover is AmbiguousProverPolicy.DISCARD_UNCOMMITTED:
            return (
                RecoveryDisposition.DISCARD_UNCOMMITTED,
                RecoveryReason.AMBIGUOUS_PROVER,
            )
        return RecoveryDisposition.FULL_REPROOF, RecoveryReason.AMBIGUOUS_PROVER

    if phase is SealTransitionPhase.RECEIPT_PERSISTENCE:
        if has_verified_artifact:
            return RecoveryDisposition.REPLAY, RecoveryReason.VERIFIED_ARTIFACT
        return RecoveryDisposition.FULL_REPROOF, RecoveryReason.MISSING_ARTIFACT

    if phase is SealTransitionPhase.FOREST_UPDATE:
        if has_verified_artifact:
            return RecoveryDisposition.VERIFY_EXISTING, RecoveryReason.VERIFIED_ARTIFACT
        return RecoveryDisposition.REPLAY, RecoveryReason.MISSING_ARTIFACT

    if phase is SealTransitionPhase.AGGREGATE_GENERATION:
        if has_verified_artifact:
            return RecoveryDisposition.VERIFY_EXISTING, RecoveryReason.VERIFIED_ARTIFACT
        return RecoveryDisposition.RESUME, RecoveryReason.MISSING_ARTIFACT

    if phase is SealTransitionPhase.SEAL_PERSISTENCE:
        if not parent_is_current:
            return (
                RecoveryDisposition.DISCARD_UNCOMMITTED,
                RecoveryReason.STALE_PARENT,
            )
        if has_verified_artifact:
            return RecoveryDisposition.VERIFY_EXISTING, RecoveryReason.VERIFIED_ARTIFACT
        return RecoveryDisposition.RESUME, RecoveryReason.MISSING_ARTIFACT

    if phase is SealTransitionPhase.CURRENT_ROOT_CAS:
        if pointer_matches_seal:
            return RecoveryDisposition.REPAIR, RecoveryReason.POINTER_MATCHES_SEAL
        if not parent_is_current:
            return (
                RecoveryDisposition.DISCARD_UNCOMMITTED,
                RecoveryReason.STALE_PARENT,
            )
        return RecoveryDisposition.RESUME, RecoveryReason.UNSTARTED

    if phase is SealTransitionPhase.CLEANUP:
        if pointer_matches_seal:
            return RecoveryDisposition.REPAIR, RecoveryReason.POINTER_MATCHES_SEAL
        return RecoveryDisposition.REPAIR, RecoveryReason.IDEMPOTENT

    raise SealTransitionRecoveryError(
        f"unknown seal-transition phase: {phase!r}",
        reason=RecoveryReason.UNCOMMITTED,
    )


def _kinds_for_phase(phase: SealTransitionPhase) -> tuple[ArtifactKind, ...]:
    if phase is SealTransitionPhase.PROOF_EXECUTION:
        return _PROVER_KINDS
    if phase is SealTransitionPhase.RECEIPT_PERSISTENCE:
        return _RECEIPT_KINDS + _PROVER_KINDS
    if phase is SealTransitionPhase.FOREST_UPDATE:
        return _FOREST_KINDS
    if phase is SealTransitionPhase.AGGREGATE_GENERATION:
        return _AGGREGATE_KINDS
    if phase in {
        SealTransitionPhase.SEAL_PERSISTENCE,
        SealTransitionPhase.CURRENT_ROOT_CAS,
        SealTransitionPhase.CLEANUP,
    }:
        return _SEAL_KINDS
    return ()


# ---------------------------------------------------------------------------
# Mutation application (idempotent)
# ---------------------------------------------------------------------------


def _apply_decision(
    wal: SealTransitionWal,
    record: SealTransitionRecord,
    disposition: RecoveryDisposition,
    reason: RecoveryReason,
    *,
    apply_mutations: bool,
) -> tuple[bool, SealTransitionRecord]:
    """Apply the safe, idempotent mutation implied by ``disposition``."""

    if not apply_mutations:
        return False, record
    if _is_terminal(record.state):
        return False, record

    if (
        disposition is RecoveryDisposition.DISCARD_UNCOMMITTED
        and reason
        in {
            RecoveryReason.STALE_PARENT,
            RecoveryReason.AMBIGUOUS_PROVER,
            RecoveryReason.PUBLICATION_REJECTED,
        }
    ):
        aborted = abort_transition(wal, record.transition_id, phase=record.phase)
        return True, aborted

    if (
        disposition is RecoveryDisposition.REPAIR
        and reason is RecoveryReason.POINTER_MATCHES_SEAL
        and record.new_seal_cid
        and record.new_seal_kind is not None
    ):
        committed = commit_transition(
            wal,
            record.transition_id,
            new_seal_cid=record.new_seal_cid,
            new_seal_kind=record.new_seal_kind,
            phase=SealTransitionPhase.CLEANUP,
        )
        return True, committed

    return False, record


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def recover_seal_transitions(
    root: StoreRoot | str | Path | os.PathLike[str] | None,
    *,
    wal: SealTransitionWal | None = None,
    store: HermeticProofSealStore | None = None,
    pointers: CurrentSealRepository | None = None,
    policy: RecoveryPolicy | Mapping[str, Any] | None = None,
) -> RecoveryReport:
    """Recover every durable seal transition under ``root``.

    ``root`` is mandatory and explicit.  Optional ``wal`` / ``store`` /
    ``pointers`` share that root; when omitted they are opened hermetically.
    Repeated calls converge: corrupt tails are truncated once, post-CAS
    cleanup commits at most once, and a stale parent never publishes.
    """

    store_root = _as_store_root(root)
    if isinstance(policy, RecoveryPolicy) or policy is None:
        recovery_policy = policy or DEFAULT_RECOVERY_POLICY
    elif isinstance(policy, Mapping):
        recovery_policy = RecoveryPolicy(
            ambiguous_prover=policy.get(
                "ambiguous_prover", AmbiguousProverPolicy.FULL_REPROOF
            ),
            apply_mutations=bool(policy.get("apply_mutations", True)),
        )
    else:
        raise SealTransitionRecoveryError(
            "policy must be RecoveryPolicy, mapping, or None",
            reason=RecoveryReason.UNCOMMITTED,
        )

    owns_wal = wal is None
    if wal is None:
        wal = SealTransitionWal(store_root)
    if store is None:
        try:
            store = HermeticProofSealStore(store_root, create=False)
        except (ExplicitRootRequiredError, ProofSealStoreContractError, OSError):
            store = None
    if pointers is None:
        try:
            pointers = CurrentSealRepository(store_root, create=False)
        except (ExplicitRootRequiredError, ProofSealStoreContractError, OSError):
            pointers = None

    repaired_tail = False
    scan = wal.scan()
    if scan.tail_corrupt:
        wal.recover_and_truncate_tail()
        repaired_tail = True

    decisions: list[TransitionRecoveryDecision] = []
    seen: set[str] = set()

    # Open (non-terminal) transitions first — these are the recovery inputs.
    for record in wal.open_transitions():
        decision = _decide_one(
            wal,
            record,
            store=store,
            pointers=pointers,
            policy=recovery_policy,
        )
        decisions.append(decision)
        seen.add(record.transition_id)

    # Committed transitions still need post-CAS cleanup recognition so a
    # restart after successful CAS but missing cleanup stays idempotent.
    for view in wal.committed_transitions():
        if view.transition_id in seen:
            continue
        decision = _decide_one(
            wal,
            view.record,
            store=store,
            pointers=pointers,
            policy=recovery_policy,
        )
        decisions.append(decision)
        seen.add(view.transition_id)

    if repaired_tail and not decisions:
        # Prefix-only repair with no transitions still surfaces a report.
        decisions.append(
            TransitionRecoveryDecision(
                transition_id="wal:prefix",
                repository_id="n/a",
                branch_id="n/a",
                phase=SealTransitionPhase.INTENT,
                state=SealTransitionState.OPEN,
                disposition=RecoveryDisposition.REPAIR,
                reason=RecoveryReason.CORRUPT_TAIL,
                applied=True,
                diagnostics={"tail_repaired": True},
            )
        )

    decisions.sort(
        key=lambda item: (item.repository_id, item.branch_id, item.transition_id)
    )
    report = RecoveryReport(tuple(decisions), repaired_tail=repaired_tail)
    if owns_wal:
        wal.close()
    return report


def _decide_one(
    wal: SealTransitionWal,
    record: SealTransitionRecord,
    *,
    store: HermeticProofSealStore | None,
    pointers: CurrentSealRepository | None,
    policy: RecoveryPolicy,
) -> TransitionRecoveryDecision:
    pointer = _current_pointer(pointers, record.repository_id, record.branch_id)
    pointer_matches = _pointer_equals_new_seal(pointer, record)
    parent_current = _parent_is_current(pointer, record)

    kinds = _kinds_for_phase(record.phase)
    candidates = list(record.artifact_cids)
    if record.new_seal_cid:
        candidates.append(record.new_seal_cid)
    verified = _verified_cids(store, candidates, kinds)

    disposition, reason = disposition_for_phase(
        record.phase,
        has_verified_artifact=bool(verified),
        pointer_matches_seal=pointer_matches,
        parent_is_current=parent_current,
        ambiguous_prover=policy.ambiguous_prover,
        state=record.state,
    )

    publication_rejected = reason is RecoveryReason.STALE_PARENT
    applied, updated = _apply_decision(
        wal,
        record,
        disposition,
        reason,
        apply_mutations=policy.apply_mutations,
    )
    if applied:
        record = updated
        if record.state is SealTransitionState.ABORTED:
            disposition = RecoveryDisposition.DISCARD_UNCOMMITTED
        elif record.state is SealTransitionState.COMMITTED:
            disposition = RecoveryDisposition.REPAIR
            reason = RecoveryReason.POINTER_MATCHES_SEAL

    return TransitionRecoveryDecision(
        transition_id=record.transition_id,
        repository_id=record.repository_id,
        branch_id=record.branch_id,
        phase=record.phase,
        state=record.state,
        disposition=disposition,
        reason=reason,
        applied=applied,
        publication_rejected=publication_rejected,
        pointer_recognized=pointer_matches,
        verified_artifact_cids=verified,
        diagnostics={
            "generation": record.generation,
            "expected_parent_seal_cid": record.expected_parent_seal_cid,
            "new_seal_cid": record.new_seal_cid,
            "phase_index": phase_index(record.phase),
            "parent_is_current": parent_current,
        },
    )


def closed_recovery_disposition_values() -> frozenset[str]:
    """Return the exact closed set of public recovery dispositions."""

    return frozenset(item.value for item in RecoveryDisposition)


__all__ = (
    "CONTRACT_VERSION",
    "DEFAULT_RECOVERY_POLICY",
    "EVIDENCE_SUBSET",
    "RECOVERY_INTERFACE",
    "RECOVERY_SCHEMA",
    "REQUIRED_RECOVERY_DISPOSITIONS",
    "AmbiguousProverPolicy",
    "RecoveryDisposition",
    "RecoveryPolicy",
    "RecoveryReason",
    "RecoveryReport",
    "SealTransitionRecoveryError",
    "TransitionRecoveryDecision",
    "closed_recovery_disposition_values",
    "disposition_for_phase",
    "recover_seal_transitions",
)
