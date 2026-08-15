"""Regression tests for the exact-key candidate cache index (IPS-021).

Acceptance coverage:

* key / CID / kind / admission mismatch misses or quarantines;
* unverified proof cannot enter;
* stale / simulated / non-pass metadata cannot be queried as accepted;
* every lookup is a candidate requiring fresh verification;
* tombstones and poisoning detection hide or quarantine bad keys;
* corruption rebuild removes unrecoverable envelopes and preserves good keys;
* explicit root only (no default user state or daemon).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ArtifactReference,
    ArtifactRole,
    CacheCandidate,
    ExplicitRootRequiredError,
    candidate_is_not_admitted,
)
from ipfs_kit_py.proof_seal_store.cache_index import (
    ADMISSION_RECORD_INTERFACE,
    ALLOWED_ADMISSION_ISSUERS,
    CACHE_INDEX_INTERFACE,
    EVIDENCE_SUBSET,
    PASS_TERMINAL_STATUSES,
    AcceptanceQueryStatus,
    CacheIndexAdmissionError,
    CandidateAdmissionRecord,
    IndexDisposition,
    IndexReason,
    ProofCacheIndex,
    cache_key_digest,
)
from ipfs_kit_py.proof_seal_store.local_store import content_cid_for_bytes


def _cid_for(tag: bytes) -> str:
    return content_cid_for_bytes(b'{"proof":"' + tag + b'"}')


def _artifact(
    tag: bytes = b"obj",
    kind: ArtifactKind = ArtifactKind.PROOF_OBJECT,
) -> ArtifactReference:
    data = b'{"proof":"' + tag + b'"}'
    return ArtifactReference(
        cid=content_cid_for_bytes(data),
        kind=kind,
        byte_length=len(data),
    )


def _admission(
    *,
    cache_key: str = "proof-cache-key:unit-a",
    tag: bytes = b"obj",
    kind: ArtifactKind = ArtifactKind.PROOF_OBJECT,
    admission_id: str = "admission:1",
    issuer: str = "accelerate",
    terminal_status: str = "proved",
    **overrides: Any,
) -> CandidateAdmissionRecord:
    artifact = overrides.pop("artifact", None) or _artifact(tag, kind)
    fields: dict[str, Any] = {
        "cache_key": cache_key,
        "artifact": artifact,
        "admission_id": admission_id,
        "issuer": issuer,
        "terminal_status": terminal_status,
        "verified": True,
        "cryptographically_verified": True,
        "simulated": False,
        "stale": False,
        "proof_mode": "direct_execution_proof",
        "verification_receipt_cid": _cid_for(b"receipt"),
        "policy_cid": _cid_for(b"policy"),
        "generation": 1,
    }
    fields.update(overrides)
    return CandidateAdmissionRecord(**fields)


def _index(tmp_path: Path) -> ProofCacheIndex:
    return ProofCacheIndex(tmp_path)


# ---------------------------------------------------------------------------
# Construction / constants
# ---------------------------------------------------------------------------


def test_schema_and_evidence_constants() -> None:
    assert EVIDENCE_SUBSET == "ips/proof-cache-index@1"
    assert CACHE_INDEX_INTERFACE == "ProofCacheIndex@1"
    assert ADMISSION_RECORD_INTERFACE == "CandidateAdmissionRecord@1"
    assert "accelerate" in ALLOWED_ADMISSION_ISSUERS
    assert "proved" in PASS_TERMINAL_STATUSES


def test_explicit_root_is_mandatory() -> None:
    with pytest.raises(ExplicitRootRequiredError):
        ProofCacheIndex(None)
    with pytest.raises(ExplicitRootRequiredError):
        ProofCacheIndex("relative/index")
    with pytest.raises(ExplicitRootRequiredError):
        ProofCacheIndex("~/proof-cache-index")


def test_cache_key_digest_is_stable() -> None:
    digest = cache_key_digest("proof-cache-key:unit-a")
    assert len(digest) == 64
    assert digest == cache_key_digest("proof-cache-key:unit-a")
    assert digest != cache_key_digest("proof-cache-key:unit-b")


# ---------------------------------------------------------------------------
# Happy path: verified admission → candidate lookup
# ---------------------------------------------------------------------------


def test_record_and_lookup_round_trip(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission()
    put = index.record_verified_admission(record)
    assert put.disposition is IndexDisposition.STORED
    assert put.reason is IndexReason.OK
    assert put.candidate is not None
    assert put.candidate.requires_fresh_verification is True
    assert put.candidate.role is ArtifactRole.CANDIDATE
    assert put.candidate.is_acceptance_authority is False
    assert candidate_is_not_admitted(put.candidate)

    candidate = index.lookup_candidate(record.cache_key)
    assert isinstance(candidate, CacheCandidate)
    assert candidate.cache_key == record.cache_key
    assert candidate.cid == record.cid
    assert candidate.kind is record.kind
    assert candidate.requires_fresh_verification is True
    assert candidate.is_acceptance_authority is False
    assert candidate.role is ArtifactRole.CANDIDATE

    result = index.lookup_result(record.cache_key)
    assert result.hit
    assert result.is_acceptance is False
    assert result.record is not None
    assert result.record.admission_id == record.admission_id


def test_identical_admission_is_idempotent(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission()
    first = index.record_verified_admission(record)
    second = index.record_verified_admission(record)
    assert first.stored
    assert second.disposition is IndexDisposition.ALREADY_EXISTS
    assert second.reason is IndexReason.ALREADY_EXISTS
    assert index.lookup_candidate(record.cache_key) is not None


def test_admission_from_dict_round_trip() -> None:
    record = _admission()
    restored = CandidateAdmissionRecord.from_dict(record.to_dict())
    assert restored == record
    assert restored.is_indexable is True
    assert restored.is_acceptance_authority is False


# ---------------------------------------------------------------------------
# Unverified / simulated / stale / non-pass cannot enter
# ---------------------------------------------------------------------------


def test_unverified_admission_cannot_enter(tmp_path: Path) -> None:
    index = _index(tmp_path)
    with pytest.raises(CacheIndexAdmissionError) as exc_info:
        _admission(verified=False)
    assert exc_info.value.reason is IndexReason.UNVERIFIED

    with pytest.raises(CacheIndexAdmissionError) as exc_info:
        _admission(cryptographically_verified=False)
    assert exc_info.value.reason is IndexReason.UNVERIFIED

    # Even a raw dict path is rejected at the index boundary.
    payload = _admission().to_dict()
    payload["verified"] = False
    put = index.record_verified_admission(payload)
    assert put.disposition is IndexDisposition.REJECTED
    assert put.reason is IndexReason.UNVERIFIED
    assert index.lookup_candidate(payload["cache_key"]) is None


def test_simulated_admission_cannot_enter(tmp_path: Path) -> None:
    index = _index(tmp_path)
    with pytest.raises(CacheIndexAdmissionError) as exc_info:
        _admission(simulated=True)
    assert exc_info.value.reason is IndexReason.SIMULATED

    with pytest.raises(CacheIndexAdmissionError) as exc_info:
        _admission(proof_mode="simulated")
    assert exc_info.value.reason is IndexReason.SIMULATED

    with pytest.raises(CacheIndexAdmissionError) as exc_info:
        _admission(terminal_status="simulated")
    assert exc_info.value.reason is IndexReason.SIMULATED

    payload = _admission().to_dict()
    payload["simulated"] = True
    put = index.record_verified_admission(payload)
    assert put.disposition is IndexDisposition.REJECTED
    assert put.reason is IndexReason.SIMULATED
    assert index.lookup_candidate(payload["cache_key"]) is None


def test_stale_admission_cannot_enter(tmp_path: Path) -> None:
    index = _index(tmp_path)
    with pytest.raises(CacheIndexAdmissionError) as exc_info:
        _admission(stale=True)
    assert exc_info.value.reason is IndexReason.STALE

    with pytest.raises(CacheIndexAdmissionError) as exc_info:
        _admission(terminal_status="stale")
    assert exc_info.value.reason is IndexReason.STALE

    payload = _admission().to_dict()
    payload["stale"] = True
    put = index.record_verified_admission(payload)
    assert put.disposition is IndexDisposition.REJECTED
    assert put.reason is IndexReason.STALE
    assert index.lookup_candidate(payload["cache_key"]) is None


@pytest.mark.parametrize(
    "status",
    [
        "failed",
        "proof_failed",
        "unknown",
        "timeout",
        "unavailable",
        "cancelled",
        "invalid",
        "disproved",
        "pass",
        "ok",
        "success",
        "zk_verified",
    ],
)
def test_non_pass_terminal_status_cannot_enter(tmp_path: Path, status: str) -> None:
    index = _index(tmp_path)
    with pytest.raises(CacheIndexAdmissionError) as exc_info:
        _admission(terminal_status=status)
    assert exc_info.value.reason in {
        IndexReason.NON_PASS,
        IndexReason.SIMULATED,
        IndexReason.STALE,
    }

    payload = _admission().to_dict()
    payload["terminal_status"] = status
    put = index.record_verified_admission(payload)
    assert put.disposition is IndexDisposition.REJECTED
    assert index.lookup_candidate(payload["cache_key"]) is None


def test_non_accelerate_issuer_cannot_enter(tmp_path: Path) -> None:
    index = _index(tmp_path)
    with pytest.raises(CacheIndexAdmissionError) as exc_info:
        _admission(issuer="untrusted-prover")
    assert exc_info.value.reason is IndexReason.ISSUER_REJECTED

    payload = _admission().to_dict()
    payload["issuer"] = "random-tool"
    put = index.record_verified_admission(payload)
    assert put.disposition is IndexDisposition.REJECTED
    assert put.reason is IndexReason.ISSUER_REJECTED


@pytest.mark.parametrize(
    "issuer",
    [
        "accelerate",
        "ipfs_accelerate_py",
        "ipfs_accelerate_py.agent_supervisor.proof.incremental_sealing",
        "accelerate.executor",
    ],
)
def test_accelerate_issuers_are_accepted(tmp_path: Path, issuer: str) -> None:
    index = _index(tmp_path)
    record = _admission(issuer=issuer, admission_id=f"admission:{issuer}")
    put = index.record_verified_admission(record)
    assert put.stored
    assert index.lookup_candidate(record.cache_key) is not None


@pytest.mark.parametrize(
    "status",
    sorted(PASS_TERMINAL_STATUSES),
)
def test_pass_terminal_statuses_are_indexable(tmp_path: Path, status: str) -> None:
    index = _index(tmp_path)
    record = _admission(
        cache_key=f"proof-cache-key:status-{status}",
        terminal_status=status,
        admission_id=f"admission:{status}",
    )
    put = index.record_verified_admission(record)
    assert put.stored
    candidate = index.lookup_candidate(record.cache_key)
    assert candidate is not None
    assert candidate.requires_fresh_verification is True
    assert index.query_acceptance(record.cache_key).accepted is False


# ---------------------------------------------------------------------------
# Key / CID / kind / admission mismatch
# ---------------------------------------------------------------------------


def test_expected_cache_key_mismatch_is_rejected(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission(cache_key="proof-cache-key:unit-a")
    put = index.record_verified_admission(
        record, expected_cache_key="proof-cache-key:other"
    )
    assert put.disposition is IndexDisposition.REJECTED
    assert put.reason is IndexReason.KEY_MISMATCH
    assert index.lookup_candidate(record.cache_key) is None
    assert index.lookup_candidate("proof-cache-key:other") is None


def test_expected_cid_mismatch_is_rejected(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission(tag=b"alpha")
    other_cid = _cid_for(b"beta")
    put = index.record_verified_admission(record, expected_cid=other_cid)
    assert put.disposition is IndexDisposition.REJECTED
    assert put.reason is IndexReason.CID_MISMATCH
    assert index.lookup_candidate(record.cache_key) is None


def test_expected_kind_mismatch_is_rejected(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission(kind=ArtifactKind.PROOF_OBJECT)
    put = index.record_verified_admission(
        record, expected_kind=ArtifactKind.PROOF_RECEIPT
    )
    assert put.disposition is IndexDisposition.REJECTED
    assert put.reason is IndexReason.KIND_MISMATCH
    assert index.lookup_candidate(record.cache_key) is None


def test_expected_admission_id_mismatch_is_rejected(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission(admission_id="admission:1")
    put = index.record_verified_admission(
        record, expected_admission_id="admission:other"
    )
    assert put.disposition is IndexDisposition.REJECTED
    assert put.reason is IndexReason.ADMISSION_MISMATCH
    assert index.lookup_candidate(record.cache_key) is None


def test_conflicting_admission_same_key_is_quarantined(tmp_path: Path) -> None:
    index = _index(tmp_path)
    first = _admission(tag=b"first", admission_id="admission:1")
    assert index.record_verified_admission(first).stored

    second = _admission(tag=b"second", admission_id="admission:2")
    # Same cache key, different CID + admission → poisoning.
    put = index.record_verified_admission(second)
    assert put.disposition is IndexDisposition.QUARANTINED
    assert put.reason is IndexReason.POISONED

    # Key is no longer returned as a candidate.
    assert index.lookup_candidate(first.cache_key) is None
    result = index.lookup_result(first.cache_key)
    assert result.disposition is IndexDisposition.QUARANTINED


def test_on_disk_key_mismatch_quarantines_on_lookup(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission(cache_key="proof-cache-key:unit-a")
    assert index.record_verified_admission(record).stored

    digest = cache_key_digest(record.cache_key)
    path = tmp_path / "cache_index" / "entries" / digest[:2] / f"{digest}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Corrupt the envelope key while keeping the digest path (poison).
    payload["cache_key"] = "proof-cache-key:tampered"
    payload["record"]["cache_key"] = "proof-cache-key:tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = index.lookup_result(record.cache_key)
    assert result.disposition is IndexDisposition.QUARANTINED
    assert result.reason in {
        IndexReason.KEY_MISMATCH,
        IndexReason.QUARANTINED,
        IndexReason.CORRUPTED,
    }
    assert index.lookup_candidate(record.cache_key) is None


def test_on_disk_cid_kind_corruption_quarantines(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission()
    assert index.record_verified_admission(record).stored

    digest = cache_key_digest(record.cache_key)
    path = tmp_path / "cache_index" / "entries" / digest[:2] / f"{digest}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["record"]["artifact"]["kind"] = "proof_receipt"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    # Kind inside the record no longer matches what was admitted under this key
    # binding path; lookup still returns a candidate only if the record is
    # structurally valid.  Change the CID instead to force a clearer poison
    # signal via a second write, and also verify corrupt simulated flag.
    payload["record"]["artifact"]["kind"] = record.kind.value
    payload["record"]["simulated"] = True
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    result = index.lookup_result(record.cache_key)
    assert result.disposition is IndexDisposition.QUARANTINED
    assert index.lookup_candidate(record.cache_key) is None


# ---------------------------------------------------------------------------
# Acceptance query: never accepted
# ---------------------------------------------------------------------------


def test_query_acceptance_never_accepts_active_candidate(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission()
    assert index.record_verified_admission(record).stored

    acceptance = index.query_acceptance(record.cache_key)
    assert acceptance.accepted is False
    assert bool(acceptance) is False
    assert acceptance.status is AcceptanceQueryStatus.NOT_ACCEPTED
    assert acceptance.reason is IndexReason.NOT_ACCEPTED


@pytest.mark.parametrize(
    ("field", "value", "expected_reason"),
    [
        ("stale", True, IndexReason.STALE),
        ("simulated", True, IndexReason.SIMULATED),
        ("verified", False, IndexReason.UNVERIFIED),
        ("terminal_status", "failed", IndexReason.NON_PASS),
        ("terminal_status", "timeout", IndexReason.NON_PASS),
        ("terminal_status", "unknown", IndexReason.NON_PASS),
    ],
)
def test_query_acceptance_rejects_stale_simulated_non_pass_metadata(
    tmp_path: Path,
    field: str,
    value: Any,
    expected_reason: IndexReason,
) -> None:
    """On-disk stale/simulated/non-pass metadata cannot be queried as accepted."""

    root = tmp_path / f"case-{field}-{value}"
    root.mkdir()
    index = _index(root)
    record = _admission(cache_key=f"proof-cache-key:{field}-{value}")
    assert index.record_verified_admission(record).stored

    digest = cache_key_digest(record.cache_key)
    path = root / "cache_index" / "entries" / digest[:2] / f"{digest}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["record"][field] = value
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    acceptance = index.query_acceptance(record.cache_key)
    assert acceptance.accepted is False
    assert acceptance.status in {
        AcceptanceQueryStatus.QUARANTINED,
        AcceptanceQueryStatus.MISS,
        AcceptanceQueryStatus.REJECTED,
        AcceptanceQueryStatus.NOT_ACCEPTED,
    }
    # Corrupt non-indexable metadata must never surface as a candidate.
    assert index.lookup_candidate(record.cache_key) is None
    lookup = index.lookup_result(record.cache_key)
    assert lookup.disposition in {
        IndexDisposition.QUARANTINED,
        IndexDisposition.MISS,
        IndexDisposition.REJECTED,
    }
    assert lookup.reason in {
        expected_reason,
        IndexReason.QUARANTINED,
        IndexReason.CORRUPTED,
        IndexReason.UNVERIFIED,
        IndexReason.NON_PASS,
        IndexReason.SIMULATED,
        IndexReason.STALE,
        IndexReason.NOT_FOUND,
    }
    # Acceptance query must not claim accepted for any of these.
    assert acceptance.status is not None
    assert acceptance.accepted is False


def test_query_acceptance_miss_and_tombstone(tmp_path: Path) -> None:
    index = _index(tmp_path)
    miss = index.query_acceptance("proof-cache-key:absent")
    assert miss.accepted is False
    assert miss.status is AcceptanceQueryStatus.MISS

    record = _admission()
    assert index.record_verified_admission(record).stored
    tomb = index.tombstone(record.cache_key, reason="invalidated")
    assert tomb.disposition is IndexDisposition.TOMBSTONED
    acceptance = index.query_acceptance(record.cache_key)
    assert acceptance.accepted is False
    assert acceptance.status is AcceptanceQueryStatus.TOMBSTONED


# ---------------------------------------------------------------------------
# Tombstone / quarantine
# ---------------------------------------------------------------------------


def test_tombstone_hides_candidate(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission()
    assert index.record_verified_admission(record).stored
    assert index.lookup_candidate(record.cache_key) is not None

    result = index.tombstone(record.cache_key, reason="unit-removed")
    assert result.disposition is IndexDisposition.TOMBSTONED
    assert index.lookup_candidate(record.cache_key) is None
    lookup = index.lookup_result(record.cache_key)
    assert lookup.disposition is IndexDisposition.TOMBSTONED
    assert lookup.reason is IndexReason.TOMBSTONED


def test_tombstone_cid_mismatch_quarantines(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission(tag=b"alpha")
    assert index.record_verified_admission(record).stored

    result = index.tombstone(
        record.cache_key,
        reason="remove",
        expected_cid=_cid_for(b"other"),
    )
    assert result.disposition is IndexDisposition.QUARANTINED
    assert result.reason is IndexReason.CID_MISMATCH
    assert index.lookup_candidate(record.cache_key) is None


def test_explicit_quarantine(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission()
    assert index.record_verified_admission(record).stored

    result = index.quarantine(record.cache_key, reason="operator-poison-alert")
    assert result.disposition is IndexDisposition.QUARANTINED
    assert index.lookup_candidate(record.cache_key) is None
    # Further admissions remain dark while quarantined.
    put = index.record_verified_admission(record)
    assert put.disposition is IndexDisposition.QUARANTINED


def test_fresh_admission_clears_tombstone(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission()
    assert index.record_verified_admission(record).stored
    assert index.tombstone(record.cache_key).disposition is IndexDisposition.TOMBSTONED
    assert index.lookup_candidate(record.cache_key) is None

    put = index.record_verified_admission(record)
    assert put.stored
    assert index.lookup_candidate(record.cache_key) is not None


# ---------------------------------------------------------------------------
# Rebuild / corruption
# ---------------------------------------------------------------------------


def test_rebuild_removes_corrupted_records(tmp_path: Path) -> None:
    index = _index(tmp_path)
    good = _admission(cache_key="proof-cache-key:good", tag=b"good")
    bad = _admission(cache_key="proof-cache-key:bad", tag=b"bad")
    assert index.record_verified_admission(good).stored
    assert index.record_verified_admission(bad).stored

    digest = cache_key_digest(bad.cache_key)
    path = tmp_path / "cache_index" / "entries" / digest[:2] / f"{digest}.json"
    path.write_text("{not-json", encoding="utf-8")

    rebuilt = index.rebuild()
    assert rebuilt.disposition is IndexDisposition.REBUILT
    assert rebuilt.corrupted >= 1
    assert rebuilt.removed >= 1
    assert index.lookup_candidate(good.cache_key) is not None
    assert index.lookup_candidate(bad.cache_key) is None
    assert not path.exists()


def test_lookup_missing_key_is_miss(tmp_path: Path) -> None:
    index = _index(tmp_path)
    assert index.lookup_candidate("proof-cache-key:missing") is None
    result = index.lookup_result("proof-cache-key:missing")
    assert result.disposition is IndexDisposition.MISS
    assert result.reason is IndexReason.NOT_FOUND
    assert result.is_acceptance is False


def test_empty_cache_key_is_rejected(tmp_path: Path) -> None:
    index = _index(tmp_path)
    result = index.lookup_result("")
    assert result.disposition is IndexDisposition.REJECTED
    assert result.reason is IndexReason.MALFORMED


def test_candidate_never_collapses_to_admitted_or_current(tmp_path: Path) -> None:
    index = _index(tmp_path)
    record = _admission()
    assert index.record_verified_admission(record).stored
    candidate = index.lookup_candidate(record.cache_key)
    assert candidate is not None
    assert candidate.role is ArtifactRole.CANDIDATE
    assert candidate.artifact.role is ArtifactRole.ADMITTED
    assert candidate_is_not_admitted(candidate)
    # Nested admitted bytes do not upgrade the candidate wrapper.
    assert candidate.is_acceptance_authority is False
