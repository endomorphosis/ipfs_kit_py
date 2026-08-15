"""Joined IncrementalProofSealer / kit store seven-boundary crash matrix (IPS-050).

Drives the accelerate sealer over hermetic kit WAL, store, and current-root CAS.
Each plan §9 failure point is injected, recovered, and recovered again.

Acceptance:

* restart deterministically chooses resume, replay, verify-existing,
  discard-uncommitted, repair, or full-reproof as appropriate;
* only the post-CAS case publishes a current seal;
* repeated recovery converges.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from ipfs_accelerate_py.agent_supervisor.proof.incremental_sealing.full_checkpoint import (
    FOREST_CATEGORIES,
    GENESIS_PARENT_SEAL,
    RepositoryStateView,
    RequiredUnitEvidence,
    VerificationPolicyView,
    create_full_checkpoint,
)
from ipfs_accelerate_py.agent_supervisor.proof.incremental_sealing.sealer import (
    IncrementalProofSealer,
    SealerCrash,
)
from ipfs_datasets_py.logic.zkp.incremental_sealing.evidence import (
    ProofMode,
    ProofTerminalStatus,
)
from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    CurrentSealPointer,
    SealTransitionPhase,
    SealTransitionState,
)
from ipfs_kit_py.proof_seal_store.local_store import sha256_content_id
from ipfs_kit_py.proof_seal_store.recovery import (
    AmbiguousProverPolicy,
    RecoveryDisposition,
    RecoveryPolicy,
    RecoveryReason,
    recover_seal_transitions,
)
from ipfs_kit_py.proof_seal_store.wal import (
    CRASH_BOUNDARIES,
    SealTransitionWalCrash,
)

EVIDENCE_SUBSET = "ips/joined-crash-matrix@1"

_DIGEST_A = "sha256:" + ("aa" * 32)
_DIGEST_B = "sha256:" + ("bb" * 32)
_DIGEST_C = "sha256:" + ("cc" * 32)
_DIGEST_D = "sha256:" + ("dd" * 32)

# Plan §9 seven joined crash boundaries and the expected recovery decision when
# intermediate proof / forest / aggregate artifacts are store-admitted.
JOINED_SEVEN_MATRIX: tuple[
    tuple[str, SealTransitionPhase, RecoveryDisposition, bool], ...
] = (
    (
        "before_proof_execution",
        SealTransitionPhase.INTENT,
        RecoveryDisposition.RESUME,
        False,
    ),
    (
        "after_proof_execution",
        SealTransitionPhase.PROOF_EXECUTION,
        RecoveryDisposition.VERIFY_EXISTING,
        False,
    ),
    (
        "after_receipt_persistence",
        SealTransitionPhase.RECEIPT_PERSISTENCE,
        RecoveryDisposition.REPLAY,
        False,
    ),
    (
        "after_forest_update",
        SealTransitionPhase.FOREST_UPDATE,
        RecoveryDisposition.VERIFY_EXISTING,
        False,
    ),
    (
        "after_aggregate_generation",
        SealTransitionPhase.AGGREGATE_GENERATION,
        RecoveryDisposition.VERIFY_EXISTING,
        False,
    ),
    (
        "after_seal_persistence",
        SealTransitionPhase.SEAL_PERSISTENCE,
        RecoveryDisposition.VERIFY_EXISTING,
        False,
    ),
    (
        "after_current_root_cas",
        SealTransitionPhase.CURRENT_ROOT_CAS,
        RecoveryDisposition.REPAIR,
        True,
    ),
)


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _proof_payload(tag: str) -> bytes:
    return _canonical_bytes({"ips-joined-proof": tag})


def _state(**overrides: object) -> RepositoryStateView:
    payload: dict[str, object] = {
        "repository_id": "repo/joined-recovery",
        "revision": "rev-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "source_root_cid": _DIGEST_A,
        "repository_state_cid": _DIGEST_B,
        "environment_cid": _DIGEST_C,
        "parent_revision_ids": (),
    }
    payload.update(overrides)
    return RepositoryStateView(**payload)  # type: ignore[arg-type]


def _policy(**overrides: object) -> VerificationPolicyView:
    payload: dict[str, object] = {
        "policy_cid": _DIGEST_D,
        "proof_schema_version": "1",
        "canonicalization_version": "1",
        "dependency_graph_schema_version": "graph@1",
        "circuit_id": "circuit@v1",
        "verification_key_id": "vk/1",
    }
    payload.update(overrides)
    return VerificationPolicyView(**payload)  # type: ignore[arg-type]


def _unit(unit_id: str, proof_object_cid: str, **overrides: object) -> RequiredUnitEvidence:
    payload: dict[str, object] = {
        "unit_id": unit_id,
        "proof_object_cid": proof_object_cid,
        "category": "unit_test",
        "terminal_status": ProofTerminalStatus.INTEGRITY_VERIFIED.value,
        "proof_mode": ProofMode.INTEGRITY_ONLY.value,
        "required_for_seal": True,
        "freshly_verified": True,
        "cache_reused_without_fresh_verification": False,
    }
    payload.update(overrides)
    return RequiredUnitEvidence(**payload)  # type: ignore[arg-type]


def _content_units(*, tag: str = "joined") -> tuple[RequiredUnitEvidence, ...]:
    proof_a = sha256_content_id(_proof_payload(f"{tag}:a"))
    proof_b = sha256_content_id(_proof_payload(f"{tag}:b"))
    return (
        _unit("unit/a", proof_a),
        _unit(
            "unit/b",
            proof_b,
            category="static_analysis",
            terminal_status=ProofTerminalStatus.PROVED.value,
            proof_mode=ProofMode.DIRECT_EXECUTION_PROOF.value,
        ),
    )


def _admit_proof_objects(
    sealer: IncrementalProofSealer,
    units: tuple[RequiredUnitEvidence, ...],
    *,
    tag: str,
) -> None:
    """Admit content-addressed unit proofs for the given suite tag prefix."""

    suffix_by_unit = {"unit/a": "a", "unit/b": "b"}
    for unit in units:
        suffix = suffix_by_unit[unit.unit_id]
        payload = _proof_payload(f"{tag}:{suffix}")
        assert sha256_content_id(payload) == unit.proof_object_cid
        sealer.store.put_immutable(
            ArtifactKind.PROOF_OBJECT,
            payload,
            claimed_cid=unit.proof_object_cid,
        )


def _admit_joined_phase_artifacts(
    sealer: IncrementalProofSealer,
    *,
    state: RepositoryStateView,
    policy: VerificationPolicyView,
    units: tuple[RequiredUnitEvidence, ...],
    tag: str = "joined",
    parent_seal_cid: str = GENESIS_PARENT_SEAL,
    fallback_reasons: tuple[str, ...] = ("first_state",),
) -> str:
    """Admit proof, forest, and aggregate bytes that rehash to sealer-journaled CIDs.

    The joined sealer journals unit / forest / aggregate digests before it
    persists the seal itself.  Recovery only returns verify-existing / replay
    when those digests rehash against admitted store objects.
    """

    _admit_proof_objects(sealer, units, tag=tag)

    preview = create_full_checkpoint(
        state,
        policy,
        units=units,
        parent_seal_cid=parent_seal_cid,
        fallback_reasons=fallback_reasons,
    )
    assert preview.sealed, (preview.seal_status, preview.reason)

    forest_payload = {
        "domain": "ips.full_checkpoint.repository.v1",
        "repository_id": preview.repository_id,
        "revision": preview.revision,
        "source_root_cid": preview.source_root_cid,
        "repository_state_cid": preview.repository_state_cid,
        "manifest_root_cid": preview.manifest_root_cid,
        "environment_cid": preview.environment_cid,
        "policy_cid": preview.policy_cid,
        "proof_schema_version": preview.proof_schema_version,
        "canonicalization_version": preview.canonicalization_version,
        "dependency_graph_schema_version": preview.dependency_graph_schema_version,
        "circuit_id": preview.circuit_id,
        "verification_key_id": preview.verification_key_id,
        "parent_seal_cid": preview.parent_seal_cid,
        "parent_revision_ids": list(preview.parent_revision_ids),
        "category_roots": {
            cat: preview.category_roots[cat] for cat in FOREST_CATEGORIES
        },
    }
    forest_bytes = _canonical_bytes(forest_payload)
    forest_cid = "sha256:" + hashlib.sha256(forest_bytes).hexdigest()
    assert forest_cid == preview.repository_proof_root
    sealer.store.put_immutable(
        ArtifactKind.MERKLE_NODE,
        forest_bytes,
        claimed_cid=forest_cid,
    )

    aggregate_payload = {
        "domain": "ips.full_checkpoint.aggregation.v1",
        "label": "manifest_aggregation",
        "required_unit_ids": list(preview.required_unit_ids),
        "category_roots": {
            cat: preview.category_roots[cat] for cat in FOREST_CATEGORIES
        },
    }
    aggregate_bytes = _canonical_bytes(aggregate_payload)
    aggregate_cid = "sha256:" + hashlib.sha256(aggregate_bytes).hexdigest()
    assert aggregate_cid == preview.aggregation_root
    sealer.store.put_immutable(
        ArtifactKind.PROOF_MANIFEST,
        aggregate_bytes,
        claimed_cid=aggregate_cid,
    )
    return preview.seal_cid()


def _crash_injector(boundary: str):
    hit = {"fired": False}

    def inject(name: str, transition_id: str | None = None, phase: Any = None) -> None:
        del transition_id, phase
        if name == boundary and not hit["fired"]:
            hit["fired"] = True
            raise SealTransitionWalCrash(name)

    return inject


def _publish_kwargs(
    *,
    transition_id: str,
    units: tuple[RequiredUnitEvidence, ...],
    state: RepositoryStateView | None = None,
) -> dict[str, Any]:
    return {
        "repository_state": state or _state(),
        "verification_policy": _policy(),
        "units": units,
        "parent_seal_cid": GENESIS_PARENT_SEAL,
        "fallback_reasons": ("first_state",),
        "transition_id": transition_id,
    }


# ---------------------------------------------------------------------------
# Closed surface
# ---------------------------------------------------------------------------


def test_joined_evidence_subset_and_seven_boundaries() -> None:
    assert EVIDENCE_SUBSET == "ips/joined-crash-matrix@1"
    assert len(JOINED_SEVEN_MATRIX) == 7
    for boundary, _phase, _disposition, _current in JOINED_SEVEN_MATRIX:
        assert boundary in CRASH_BOUNDARIES
    dispositions = {item[2] for item in JOINED_SEVEN_MATRIX}
    assert RecoveryDisposition.RESUME in dispositions
    assert RecoveryDisposition.REPLAY in dispositions
    assert RecoveryDisposition.VERIFY_EXISTING in dispositions
    assert RecoveryDisposition.REPAIR in dispositions
    current_cases = [item for item in JOINED_SEVEN_MATRIX if item[3]]
    assert len(current_cases) == 1
    assert current_cases[0][0] == "after_current_root_cas"


# ---------------------------------------------------------------------------
# Seven joined crash boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("boundary", "durable_phase", "expected", "becomes_current"),
    JOINED_SEVEN_MATRIX,
    ids=[item[0] for item in JOINED_SEVEN_MATRIX],
)
def test_joined_seven_boundary_recovery(
    tmp_path: Path,
    boundary: str,
    durable_phase: SealTransitionPhase,
    expected: RecoveryDisposition,
    becomes_current: bool,
) -> None:
    root = tmp_path / "joined-store"
    units = _content_units(tag="joined")
    transition_id = f"txn:joined-{boundary}"
    sealer = IncrementalProofSealer(
        root, crash_injector=_crash_injector(boundary)
    )
    state = _state()
    policy = _policy()
    _admit_joined_phase_artifacts(
        sealer, state=state, policy=policy, units=units, tag="joined"
    )

    assert sealer.get_current_seal("repo/joined-recovery") is None

    with pytest.raises((SealTransitionWalCrash, SealerCrash)) as excinfo:
        sealer.publish_full_checkpoint(
            **_publish_kwargs(transition_id=transition_id, units=units, state=state)
        )
    assert boundary in str(excinfo.value)

    leftover = sealer.wal.get_transition(transition_id)
    assert leftover is not None
    assert leftover.phase is durable_phase
    assert leftover.state in {
        SealTransitionState.OPEN,
        SealTransitionState.IN_PROGRESS,
    }

    pre_pointer = sealer.get_current_seal("repo/joined-recovery")
    if becomes_current:
        assert pre_pointer is not None
        assert pre_pointer.seal_cid == leftover.new_seal_cid
        assert leftover.new_seal_cid
    else:
        assert pre_pointer is None

    first = sealer.recover_publication(apply_mutations=True)
    second = sealer.recover_publication(apply_mutations=True)
    decision = first.decision_for(transition_id)
    replay = second.decision_for(transition_id)

    assert decision.disposition is expected
    assert replay.disposition is expected
    assert decision.disposition.value == replay.disposition.value
    assert decision.reason is replay.reason or (
        expected is RecoveryDisposition.REPAIR
        and replay.reason
        in {
            RecoveryReason.POINTER_MATCHES_SEAL,
            RecoveryReason.COMMITTED_PREFIX,
            RecoveryReason.IDEMPOTENT,
        }
    )

    post_pointer = sealer.get_current_seal("repo/joined-recovery")
    if becomes_current:
        assert post_pointer is not None
        assert post_pointer.seal_cid == leftover.new_seal_cid
        assert decision.pointer_recognized is True
        assert decision.reason is RecoveryReason.POINTER_MATCHES_SEAL
        finalized = sealer.wal.get_transition(transition_id)
        assert finalized is not None
        assert finalized.state is SealTransitionState.COMMITTED
        assert sealer.wal.is_current_eligible(transition_id) is True
        recognized = sealer.recognize_post_cas_success(transition_id)
        assert recognized.published is True
        assert recognized.pointer is not None
        assert recognized.pointer.seal_cid == post_pointer.seal_cid
    else:
        assert post_pointer is None
        assert sealer.wal.is_current_eligible(transition_id) is False
        # Pre-CAS failure must not promote an uncommitted seal.
        open_rec = sealer.wal.get_transition(transition_id)
        assert open_rec is not None
        assert open_rec.state is not SealTransitionState.COMMITTED

    sealer.close()


def test_only_post_cas_boundary_makes_seal_current(tmp_path: Path) -> None:
    """Across all seven injections, only after_current_root_cas is current."""

    current_boundaries: list[str] = []
    for boundary, _phase, _expected, becomes_current in JOINED_SEVEN_MATRIX:
        root = tmp_path / boundary
        units = _content_units(tag="joined")
        tid = f"txn:scan-{boundary}"
        sealer = IncrementalProofSealer(
            root, crash_injector=_crash_injector(boundary)
        )
        state = _state()
        _admit_joined_phase_artifacts(
            sealer, state=state, policy=_policy(), units=units, tag="joined"
        )
        with pytest.raises((SealTransitionWalCrash, SealerCrash)):
            sealer.publish_full_checkpoint(
                **_publish_kwargs(transition_id=tid, units=units, state=state)
            )
        pointer = sealer.get_current_seal("repo/joined-recovery")
        if pointer is not None:
            current_boundaries.append(boundary)
            assert becomes_current is True
        else:
            assert becomes_current is False
        sealer.close()

    assert current_boundaries == ["after_current_root_cas"]


def test_repeated_recovery_converges_for_every_boundary(tmp_path: Path) -> None:
    for boundary, _phase, expected, _current in JOINED_SEVEN_MATRIX:
        root = tmp_path / f"conv-{boundary}"
        units = _content_units(tag="joined")
        tid = f"txn:conv-{boundary}"
        sealer = IncrementalProofSealer(
            root, crash_injector=_crash_injector(boundary)
        )
        state = _state()
        _admit_joined_phase_artifacts(
            sealer, state=state, policy=_policy(), units=units, tag="joined"
        )
        with pytest.raises((SealTransitionWalCrash, SealerCrash)):
            sealer.publish_full_checkpoint(
                **_publish_kwargs(transition_id=tid, units=units, state=state)
            )

        reports = [
            sealer.recover_publication(apply_mutations=True) for _ in range(3)
        ]
        dispositions = [report.decision_for(tid).disposition for report in reports]
        assert dispositions[0] is expected
        assert all(item is dispositions[0] for item in dispositions[1:])
        # Pointer identity is stable across restarts.
        pointers = [
            sealer.get_current_seal("repo/joined-recovery") for _ in range(2)
        ]
        assert pointers[0] == pointers[1]
        sealer.close()


# ---------------------------------------------------------------------------
# Ambiguous prover / discard-uncommitted paths
# ---------------------------------------------------------------------------


def test_after_proof_without_admitted_artifact_is_full_reproof(
    tmp_path: Path,
) -> None:
    """Joined sealer never infers prover success from a bare phase record."""

    root = tmp_path / "ambig"
    units = _content_units(tag="joined-ambig")
    tid = "txn:joined-ambig"
    sealer = IncrementalProofSealer(
        root, crash_injector=_crash_injector("after_proof_execution")
    )
    # Intentionally do not admit proof objects.
    with pytest.raises(SealTransitionWalCrash):
        sealer.publish_full_checkpoint(
            **_publish_kwargs(transition_id=tid, units=units)
        )

    report = sealer.recover_publication(apply_mutations=True)
    decision = report.decision_for(tid)
    assert decision.disposition is RecoveryDisposition.FULL_REPROOF
    assert decision.reason is RecoveryReason.AMBIGUOUS_PROVER
    assert decision.verified_artifact_cids == ()
    assert sealer.get_current_seal("repo/joined-recovery") is None
    assert sealer.wal.is_current_eligible(tid) is False

    again = sealer.recover_publication(apply_mutations=True)
    assert again.decision_for(tid).disposition is RecoveryDisposition.FULL_REPROOF
    sealer.close()


def test_ambiguous_prover_discard_policy_aborts_uncommitted(tmp_path: Path) -> None:
    root = tmp_path / "discard-policy"
    units = _content_units(tag="joined-ambig")
    tid = "txn:joined-discard-policy"
    sealer = IncrementalProofSealer(
        root, crash_injector=_crash_injector("after_proof_execution")
    )
    with pytest.raises(SealTransitionWalCrash):
        sealer.publish_full_checkpoint(
            **_publish_kwargs(transition_id=tid, units=units)
        )

    report = recover_seal_transitions(
        root,
        wal=sealer.wal,
        store=sealer.store,
        pointers=sealer.pointers,
        policy=RecoveryPolicy(
            ambiguous_prover=AmbiguousProverPolicy.DISCARD_UNCOMMITTED,
            apply_mutations=True,
        ),
    )
    decision = report.decision_for(tid)
    assert decision.disposition is RecoveryDisposition.DISCARD_UNCOMMITTED
    assert decision.applied is True
    aborted = sealer.wal.get_transition(tid)
    assert aborted is not None
    assert aborted.state is SealTransitionState.ABORTED
    assert sealer.get_current_seal("repo/joined-recovery") is None
    sealer.close()


def test_stale_parent_after_seal_discards_uncommitted(tmp_path: Path) -> None:
    """After seal persistence, a superseded parent rejects publication."""

    root = tmp_path / "stale"
    parent_units = _content_units(tag="joined-parent")
    sealer = IncrementalProofSealer(root)
    parent = sealer.publish_full_checkpoint(
        **_publish_kwargs(
            transition_id="txn:joined-parent",
            units=parent_units,
        )
    )
    assert parent.published is True
    parent_pointer = sealer.get_current_seal("repo/joined-recovery")
    assert parent_pointer is not None

    # Advance current so the interrupted transition's expected parent is stale.
    second_units = _content_units(tag="joined-second")
    second = sealer.publish_full_checkpoint(
        _state(
            revision="rev-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            source_root_cid="sha256:" + ("11" * 32),
            repository_state_cid="sha256:" + ("22" * 32),
        ),
        _policy(),
        units=second_units,
        transition_id="txn:joined-second",
    )
    assert second.published is True
    live = sealer.get_current_seal("repo/joined-recovery")
    assert live is not None
    assert live.seal_cid == second.seal_cid
    sealer.close()

    # Restart with a crash after seal persistence, pinning the superseded parent
    # as the expected CAS pointer so recovery sees stale_parent.
    stale_units = _content_units(tag="joined-stale")
    state = _state(
        revision="rev-cccccccccccccccccccccccccccccccccccccccc",
        source_root_cid="sha256:" + ("33" * 32),
        repository_state_cid="sha256:" + ("44" * 32),
    )
    sealer = IncrementalProofSealer(
        root, crash_injector=_crash_injector("after_seal_persistence")
    )
    _admit_joined_phase_artifacts(
        sealer,
        state=state,
        policy=_policy(),
        units=stale_units,
        tag="joined-stale",
        parent_seal_cid=parent.seal_cid,
        fallback_reasons=(),
    )

    with pytest.raises(SealTransitionWalCrash):
        sealer.publish_full_checkpoint(
            state,
            _policy(),
            units=stale_units,
            parent_seal_cid=parent.seal_cid,
            transition_id="txn:joined-stale",
            # Pin the superseded parent so CAS would target the wrong generation.
            expected_current=CurrentSealPointer(
                repository_id=parent_pointer.repository_id,
                branch_id=parent_pointer.branch_id,
                seal_cid=parent_pointer.seal_cid,
                seal_kind=parent_pointer.seal_kind,
                generation=parent_pointer.generation,
                parent_seal_cid=parent_pointer.parent_seal_cid,
            ),
        )

    leftover = sealer.wal.get_transition("txn:joined-stale")
    assert leftover is not None
    assert leftover.phase is SealTransitionPhase.SEAL_PERSISTENCE
    assert leftover.expected_parent_seal_cid == parent.seal_cid

    # Live pointer is the second seal; expected parent is the first → stale.
    report = sealer.recover_publication(apply_mutations=True)
    decision = report.decision_for("txn:joined-stale")
    assert decision.disposition is RecoveryDisposition.DISCARD_UNCOMMITTED
    assert decision.reason is RecoveryReason.STALE_PARENT
    assert decision.publication_rejected is True
    aborted = sealer.wal.get_transition("txn:joined-stale")
    assert aborted is not None
    assert aborted.state is SealTransitionState.ABORTED

    # Current pointer remains the second published seal across a second restart.
    again = sealer.recover_publication(apply_mutations=True)
    assert again.decision_for("txn:joined-second").disposition is RecoveryDisposition.REPAIR
    current = sealer.get_current_seal("repo/joined-recovery")
    assert current is not None
    assert current.seal_cid == second.seal_cid
    assert current.generation == second.generation
    still_aborted = sealer.wal.get_transition("txn:joined-stale")
    assert still_aborted is not None
    assert still_aborted.state is SealTransitionState.ABORTED
    sealer.close()


def test_post_cas_cleanup_is_idempotent_across_fresh_sealer(
    tmp_path: Path,
) -> None:
    root = tmp_path / "post-cas-fresh"
    units = _content_units(tag="joined")
    tid = "txn:joined-post-cas-fresh"
    sealer = IncrementalProofSealer(
        root, crash_injector=_crash_injector("after_current_root_cas")
    )
    state = _state()
    _admit_joined_phase_artifacts(
        sealer, state=state, policy=_policy(), units=units, tag="joined"
    )
    with pytest.raises(SealTransitionWalCrash):
        sealer.publish_full_checkpoint(
            **_publish_kwargs(transition_id=tid, units=units, state=state)
        )
    published = sealer.get_current_seal("repo/joined-recovery")
    assert published is not None
    sealer.close()

    # Fresh process: open a new sealer on the same root and converge.
    restarted = IncrementalProofSealer(root)
    first = restarted.recover_publication(apply_mutations=True)
    second = restarted.recover_publication(apply_mutations=True)
    assert first.decision_for(tid).disposition is RecoveryDisposition.REPAIR
    assert second.decision_for(tid).disposition is RecoveryDisposition.REPAIR
    current = restarted.get_current_seal("repo/joined-recovery")
    assert current is not None
    assert current.seal_cid == published.seal_cid
    finalized = restarted.wal.get_transition(tid)
    assert finalized is not None
    assert finalized.state is SealTransitionState.COMMITTED
    restarted.close()
