"""Corrupt blob / index / WAL / pointer and transport-ambiguity tests (IPS-026).

Acceptance:

* corrupted blobs fail closed and are never treated as verified artifacts;
* cache-index corruption cannot be queried as acceptance;
* a torn WAL tail preserves the committed prefix;
* a corrupt pointer cannot be swapped by a stale writer;
* optional transport ambiguity is recorded and is never success.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.proof_seal_store.cache_index import (
    CandidateAdmissionRecord,
    ProofCacheIndex,
    cache_key_digest,
)
from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ArtifactReference,
    CurrentSealPointer,
    SealTransitionPhase,
    SealTransitionRecord,
    SealTransitionState,
)
from ipfs_kit_py.proof_seal_store.ipfs_transport import (
    IpfsProofArtifactTransport,
    TransportDisposition,
    TransportReason,
)
from ipfs_kit_py.proof_seal_store.local_store import (
    HermeticProofSealStore,
    LocalStoreIntegrityError,
    StoreGetDisposition,
    content_cid_for_bytes,
)
from ipfs_kit_py.proof_seal_store.pointer import (
    CurrentSealRepository,
    PointerIntegrityError,
    PointerReason,
    namespace_digest,
)
from ipfs_kit_py.proof_seal_store.recovery import (
    RecoveryDisposition,
    recover_seal_transitions,
)
from ipfs_kit_py.proof_seal_store.wal import SealTransitionWal, begin_transition


def _cid(tag: bytes) -> str:
    return content_cid_for_bytes(b'{"corruption":"' + tag + b'"}')


def _pointer(seal_cid: str) -> CurrentSealPointer:
    return CurrentSealPointer(
        repository_id="repo:kit",
        branch_id="main",
        seal_cid=seal_cid,
        seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        generation=0,
    )


def test_corrupt_blob_is_not_a_verified_artifact(tmp_path: Path) -> None:
    store = HermeticProofSealStore(tmp_path)
    data = b'{"kind":"proof_object","tag":"good"}'
    ref = store.put_immutable(ArtifactKind.PROOF_OBJECT, data)
    path = store._object_path(ref.kind, ref.cid, create_parent=False)
    path.write_bytes(path.read_bytes() + b"\x00TAMPER")

    result = store.get_verified_bytes_result(ref)
    assert not result.hit
    assert result.disposition is StoreGetDisposition.INTEGRITY_FAILED
    with pytest.raises(LocalStoreIntegrityError):
        store.get_verified_bytes(ref)
    assert store.contains(ref) is False

    wal = SealTransitionWal(tmp_path)
    begin_transition(
        wal,
        SealTransitionRecord(
            transition_id="txn:corrupt-blob",
            repository_id="repo:kit",
            branch_id="main",
            phase=SealTransitionPhase.INTENT,
            state=SealTransitionState.OPEN,
        ),
    )
    wal.record_phase(
        "txn:corrupt-blob",
        SealTransitionPhase.PROOF_EXECUTION,
        artifact_cids=(ref.cid,),
    )
    report = recover_seal_transitions(tmp_path, wal=wal, store=store)
    decision = report.decision_for("txn:corrupt-blob")
    assert decision.disposition is RecoveryDisposition.FULL_REPROOF
    assert decision.verified_artifact_cids == ()
    wal.close()


def test_corrupt_cache_index_is_not_acceptance(tmp_path: Path) -> None:
    index = ProofCacheIndex(tmp_path)
    data = b'{"proof":"index-good"}'
    record = CandidateAdmissionRecord(
        cache_key="proof-cache-key:unit-a",
        artifact=ArtifactReference(
            cid=content_cid_for_bytes(data),
            kind=ArtifactKind.PROOF_OBJECT,
            byte_length=len(data),
        ),
        admission_id="admission:1",
        issuer="accelerate",
        terminal_status="proved",
        verified=True,
        cryptographically_verified=True,
        simulated=False,
        stale=False,
        proof_mode="direct_execution_proof",
        verification_receipt_cid=_cid(b"receipt"),
        policy_cid=_cid(b"policy"),
        generation=1,
    )
    assert index.record_verified_admission(record).stored
    digest = cache_key_digest(record.cache_key)
    path = tmp_path / "cache_index" / "entries" / digest[:2] / f"{digest}.json"
    path.write_bytes(b"{not-json")

    rebuilt = index.rebuild()
    assert rebuilt.corrupted >= 1
    candidate = index.lookup_candidate(record.cache_key)
    assert candidate is None or candidate.requires_fresh_verification is True
    assert candidate is None
    result = index.lookup_result(record.cache_key)
    assert result.is_acceptance is False


def test_corrupt_wal_tail_preserves_committed_prefix(tmp_path: Path) -> None:
    wal = SealTransitionWal(tmp_path)
    seal = _cid(b"committed")
    begin_transition(
        wal,
        SealTransitionRecord(
            transition_id="txn:keep",
            repository_id="repo:kit",
            branch_id="main",
            phase=SealTransitionPhase.INTENT,
            state=SealTransitionState.OPEN,
        ),
    )
    for phase in (
        SealTransitionPhase.PROOF_EXECUTION,
        SealTransitionPhase.RECEIPT_PERSISTENCE,
        SealTransitionPhase.FOREST_UPDATE,
        SealTransitionPhase.AGGREGATE_GENERATION,
        SealTransitionPhase.SEAL_PERSISTENCE,
    ):
        kwargs: dict[str, object] = {}
        if phase is SealTransitionPhase.SEAL_PERSISTENCE:
            kwargs["new_seal_cid"] = seal
            kwargs["new_seal_kind"] = ArtifactKind.CHECKPOINT_SEAL
        wal.record_phase("txn:keep", phase, **kwargs)
    wal.commit_transition(
        "txn:keep",
        new_seal_cid=seal,
        new_seal_kind=ArtifactKind.CHECKPOINT_SEAL,
    )
    begin_transition(
        wal,
        SealTransitionRecord(
            transition_id="txn:tail",
            repository_id="repo:kit",
            branch_id="main",
            phase=SealTransitionPhase.INTENT,
            state=SealTransitionState.OPEN,
        ),
    )
    segment = wal.segment_path
    wal.close()
    original = segment.read_bytes()
    segment.write_bytes(original + b"\xffTORN")

    report = recover_seal_transitions(tmp_path)
    assert report.repaired_tail is True
    assert report.decision_for("txn:keep").disposition is RecoveryDisposition.REPAIR
    reopened = SealTransitionWal(tmp_path)
    assert reopened.is_current_eligible("txn:keep") is True
    assert reopened.is_current_eligible("txn:tail") is False
    reopened.close()


def test_corrupt_pointer_rejects_stale_writer(tmp_path: Path) -> None:
    repo = CurrentSealRepository(tmp_path)
    first = _pointer(_cid(b"s0"))
    assert repo.compare_and_swap_current_seal(None, first) is True
    digest = namespace_digest(first.repository_id, first.branch_id)
    path = tmp_path / "current_seals" / f"{digest}.json"
    path.write_bytes(b'{"tampered":true}')

    with pytest.raises(PointerIntegrityError) as exc_info:
        repo.get_current_seal("repo:kit", "main")
    assert exc_info.value.reason in {
        PointerReason.CORRUPTED,
        PointerReason.INTEGRITY_FAILED,
        PointerReason.MALFORMED,
    }

    stale = CurrentSealPointer(
        repository_id="repo:kit",
        branch_id="main",
        seal_cid=_cid(b"stale"),
        seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        generation=1,
        parent_seal_cid=first.seal_cid,
    )
    with pytest.raises(PointerIntegrityError):
        repo.compare_and_swap_current_seal(first, stale)


def test_transport_ambiguity_is_never_success(tmp_path: Path) -> None:
    store = HermeticProofSealStore(tmp_path)
    data = b'{"kind":"proof_object","tag":"remote"}'
    cid = content_cid_for_bytes(data)

    def ambiguous_get(_cid: str) -> bytes:
        # Backend returns bytes that do not match the requested identity.
        return b'{"kind":"proof_object","tag":"other"}'

    transport = IpfsProofArtifactTransport(
        local_store=store,
        ipfs_get=ambiguous_get,
    )
    result = transport.fetch_public_artifact(
        ArtifactReference(cid=cid, kind=ArtifactKind.PROOF_OBJECT, byte_length=len(data))
    )
    assert result.disposition in {
        TransportDisposition.AMBIGUOUS,
        TransportDisposition.REJECTED,
        TransportDisposition.ERROR,
        TransportDisposition.MISS,
    }
    assert result.disposition is not TransportDisposition.HIT
    assert result.disposition is not TransportDisposition.OK
    assert result.reason in {
        TransportReason.BACKEND_AMBIGUOUS,
        TransportReason.INTEGRITY_FAILED,
        TransportReason.CID_MISMATCH,
        TransportReason.AMBIGUOUS,
        TransportReason.IPFS_RESPONSE_INVALID,
        TransportReason.CORRUPTED,
    }
    assert store.contains(
        ArtifactReference(cid=cid, kind=ArtifactKind.PROOF_OBJECT, byte_length=len(data))
    ) is False

    def silent_put(_data: bytes) -> None:
        return None

    writer = IpfsProofArtifactTransport(ipfs_put=silent_put)
    replicated = writer.replicate_public_artifact(
        ArtifactKind.PROOF_OBJECT,
        data,
        claimed_cid=cid,
    )
    assert replicated.disposition is TransportDisposition.AMBIGUOUS
    assert writer.ambiguities
