"""Regression tests for the hermetic immutable local proof-object store (IPS-019).

Acceptance coverage:

* identical bytes deduplicate;
* mismatched CID / kind / bytes fail closed;
* path escape and symlink substitution fail closed;
* short write, fsync failure, and readback failure fail closed;
* corrupted on-disk objects fail closed;
* explicit root only (no default user state or daemon).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ArtifactReference,
    ArtifactRole,
    ExplicitRootRequiredError,
    ProofSealStore,
    StoreGetDisposition,
    StorePutDisposition,
)
from ipfs_kit_py.proof_seal_store.local_store import (
    EVIDENCE_SUBSET,
    HermeticProofSealStore,
    LOCAL_STORE_INTERFACE,
    LocalStoreError,
    LocalStoreIntegrityError,
    LocalStoreNotFoundError,
    LocalStorePathError,
    LocalStoreReason,
    LocalStoreUnsupportedError,
    content_cid_for_bytes,
    content_digest_hex,
    sha256_content_id,
    verify_content_identity,
)

def _store(tmp_path: Path, **kwargs: Any) -> HermeticProofSealStore:
    return HermeticProofSealStore(tmp_path, **kwargs)


def _payload(tag: bytes = b"proof-object") -> bytes:
    return b'{"kind":"proof_object","tag":"' + tag + b'"}'


# ---------------------------------------------------------------------------
# Construction / hermetic root
# ---------------------------------------------------------------------------


def test_schema_and_evidence_constants() -> None:
    assert EVIDENCE_SUBSET == "ips/local-proof-store@1"
    assert LOCAL_STORE_INTERFACE == "HermeticProofSealStore@1"


def test_explicit_root_is_mandatory() -> None:
    with pytest.raises(ExplicitRootRequiredError):
        HermeticProofSealStore(None)
    with pytest.raises(ExplicitRootRequiredError):
        HermeticProofSealStore("relative/store")
    with pytest.raises(ExplicitRootRequiredError):
        HermeticProofSealStore("~/proof-seals")


def test_store_implements_proof_seal_store_protocol(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert isinstance(store, ProofSealStore)
    assert store.root.root_path == str(tmp_path)
    assert store.lookup_candidate("any-key") is None
    assert store.get_current_seal("repo:a", "main") is None


def test_cas_and_transition_are_unsupported(tmp_path: Path) -> None:
    from ipfs_kit_py.proof_seal_store.contracts import (
        CurrentSealPointer,
        SealTransitionPhase,
        SealTransitionRecord,
        SealTransitionState,
    )

    store = _store(tmp_path)
    pointer = CurrentSealPointer(
        repository_id="repo:a",
        branch_id="main",
        seal_cid=content_cid_for_bytes(b"seal"),
        seal_kind=ArtifactKind.CHECKPOINT_SEAL,
        generation=1,
    )
    with pytest.raises(LocalStoreUnsupportedError):
        store.compare_and_swap_current_seal(None, pointer)
    record = SealTransitionRecord(
        transition_id="txn:1",
        repository_id="repo:a",
        branch_id="main",
        phase=SealTransitionPhase.INTENT,
        state=SealTransitionState.OPEN,
    )
    with pytest.raises(LocalStoreUnsupportedError):
        store.begin_transition(record)


# ---------------------------------------------------------------------------
# Happy path + dedupe
# ---------------------------------------------------------------------------


def test_put_and_get_round_trip_with_cid_rehash(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"round-trip")
    ref = store.put_immutable(ArtifactKind.PROOF_OBJECT, data)
    assert ref.role is ArtifactRole.ADMITTED
    assert ref.kind is ArtifactKind.PROOF_OBJECT
    assert ref.byte_length == len(data)
    assert verify_content_identity(ref.cid, data)
    assert store.get_verified_bytes(ref) == data
    assert store.contains(ref)
    # No leftover temps.
    assert not list(tmp_path.rglob("*.tmp"))


def test_identical_bytes_deduplicate(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"dedupe")
    first = store.put_immutable(ArtifactKind.PROOF_RECEIPT, data)
    second_result = store.put_immutable_result(ArtifactKind.PROOF_RECEIPT, data)
    assert second_result.disposition is StorePutDisposition.ALREADY_EXISTS
    assert second_result.reason is LocalStoreReason.ALREADY_EXISTS
    assert second_result.reference == first
    second = store.put_immutable(ArtifactKind.PROOF_RECEIPT, data)
    assert second == first
    # Same bytes under an alternate content-identity form still share one blob.
    alias = store.put_immutable_result(
        ArtifactKind.PROOF_RECEIPT, data, claimed_cid=sha256_content_id(data)
    )
    assert alias.disposition is StorePutDisposition.ALREADY_EXISTS
    assert store.get_verified_bytes(first) == data
    assert store.get_verified_bytes(alias.reference) == data  # type: ignore[arg-type]
    # Single blob on disk.
    blobs = list(tmp_path.rglob("*.blob"))
    assert len(blobs) == 1


def test_claimed_cid_accepted_when_it_rehashes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"claimed")
    cid = content_cid_for_bytes(data)
    ref = store.put_immutable(ArtifactKind.MERKLE_NODE, data, claimed_cid=cid)
    assert ref.cid == cid
    assert store.get_verified_bytes(ref) == data

    sha_id = sha256_content_id(data)
    ref_sha = store.put_immutable(
        ArtifactKind.INVALIDATION_RECORD, data, claimed_cid=sha_id
    )
    assert ref_sha.cid == sha_id
    assert store.get_verified_bytes(ref_sha) == data


def test_all_closed_kinds_can_be_stored(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for kind in ArtifactKind:
        data = _payload(kind.value.encode("ascii"))
        ref = store.put_immutable(kind, data)
        assert ref.kind is kind
        assert store.get_verified_bytes(ref) == data


# ---------------------------------------------------------------------------
# Mismatched CID / kind / bytes
# ---------------------------------------------------------------------------


def test_mismatched_claimed_cid_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"cid-mismatch")
    wrong = content_cid_for_bytes(b"different-bytes")
    result = store.put_immutable_result(
        ArtifactKind.PROOF_OBJECT, data, claimed_cid=wrong
    )
    assert not result.stored
    assert result.disposition is StorePutDisposition.REJECTED
    assert result.reason is LocalStoreReason.CID_MISMATCH
    with pytest.raises(LocalStoreError) as exc_info:
        store.put_immutable(ArtifactKind.PROOF_OBJECT, data, claimed_cid=wrong)
    assert exc_info.value.reason is LocalStoreReason.CID_MISMATCH
    assert not list(tmp_path.rglob("*.blob"))


def test_mismatched_kind_on_get_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"kind-mismatch")
    ref = store.put_immutable(ArtifactKind.PROOF_OBJECT, data)
    wrong_kind = ArtifactReference(
        cid=ref.cid,
        kind=ArtifactKind.PROOF_RECEIPT,
        byte_length=ref.byte_length,
    )
    result = store.get_verified_bytes_result(wrong_kind)
    assert not result.hit
    # Wrong kind resolves to a different path → miss (not a silent upgrade).
    assert result.disposition in {
        StoreGetDisposition.MISS,
        StoreGetDisposition.KIND_MISMATCH,
    }
    with pytest.raises((LocalStoreNotFoundError, LocalStoreIntegrityError)):
        store.get_verified_bytes(wrong_kind)


def test_mismatched_byte_length_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"len-mismatch")
    ref = store.put_immutable(ArtifactKind.PROOF_MANIFEST, data)
    bad = ArtifactReference(
        cid=ref.cid,
        kind=ref.kind,
        byte_length=ref.byte_length + 7,
    )
    result = store.get_verified_bytes_result(bad)
    assert not result.hit
    assert result.disposition is StoreGetDisposition.INTEGRITY_FAILED
    with pytest.raises(LocalStoreIntegrityError):
        store.get_verified_bytes(bad)


def test_forbidden_and_unknown_kinds_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"forbidden")
    forbidden = store.put_immutable_result("proving_key", data)
    assert forbidden.disposition is StorePutDisposition.REJECTED
    assert forbidden.reason is LocalStoreReason.FORBIDDEN_KIND
    unknown = store.put_immutable_result("arbitrary_blob", data)
    assert unknown.disposition is StorePutDisposition.REJECTED
    assert unknown.reason is LocalStoreReason.MALFORMED
    non_bytes = store.put_immutable_result(ArtifactKind.PROOF_OBJECT, "not-bytes")  # type: ignore[arg-type]
    assert non_bytes.reason is LocalStoreReason.MALFORMED


def test_over_budget_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path, max_artifact_bytes=16)
    result = store.put_immutable_result(ArtifactKind.PROOF_OBJECT, b"x" * 17)
    assert not result.stored
    assert result.reason is LocalStoreReason.OVER_BUDGET


# ---------------------------------------------------------------------------
# Path escape / symlink fencing
# ---------------------------------------------------------------------------


def test_symlink_blob_rejected_on_get(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"symlink-blob")
    ref = store.put_immutable(ArtifactKind.PROOF_OBJECT, data)
    path = store._object_path(ref.kind, ref.cid, create_parent=False)
    path.unlink()
    outside = tmp_path / "outside-payload"
    outside.write_bytes(data)
    path.symlink_to(outside)

    result = store.get_verified_bytes_result(ref)
    assert not result.hit
    assert result.reason is LocalStoreReason.SYMLINK_REJECTED
    with pytest.raises(LocalStorePathError) as exc_info:
        store.get_verified_bytes(ref)
    assert exc_info.value.reason is LocalStoreReason.SYMLINK_REJECTED


def test_symlink_directory_rejected_on_put(tmp_path: Path) -> None:
    root = tmp_path / "store"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "objects").symlink_to(outside, target_is_directory=True)

    store = HermeticProofSealStore(root, create=False)
    result = store.put_immutable_result(ArtifactKind.PROOF_OBJECT, _payload(b"escape"))
    assert not result.stored
    assert result.reason is LocalStoreReason.SYMLINK_REJECTED
    assert not list(outside.iterdir())


def test_path_escape_via_unsafe_cid_token_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # Direct path helper must reject traversal tokens.
    with pytest.raises(LocalStorePathError) as exc_info:
        store._object_path(
            ArtifactKind.PROOF_OBJECT,
            "../escape",
            create_parent=False,
        )
    assert exc_info.value.reason in {
        LocalStoreReason.PATH_ESCAPE,
        LocalStoreReason.MALFORMED,
    }

    # Claimed identity with separators cannot be admitted.
    data = _payload(b"path-escape")
    result = store.put_immutable_result(
        ArtifactKind.PROOF_OBJECT,
        data,
        claimed_cid="b/../../etc/passwd",
    )
    assert not result.stored
    assert result.reason in {
        LocalStoreReason.CID_MISMATCH,
        LocalStoreReason.PATH_ESCAPE,
        LocalStoreReason.MALFORMED,
    }


def test_root_symlink_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    link = tmp_path / "link"
    real.mkdir()
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(LocalStorePathError) as exc_info:
        HermeticProofSealStore(link)
    assert exc_info.value.reason is LocalStoreReason.SYMLINK_REJECTED


# ---------------------------------------------------------------------------
# Short write / fsync / readback durability
# ---------------------------------------------------------------------------


def test_short_write_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"short-write")
    real_fdopen = os.fdopen

    class _ShortWriter:
        def __init__(self, stream: Any) -> None:
            self._stream = stream

        def write(self, buf: bytes) -> int:
            # Report a short write without persisting the full payload.
            if len(buf) == len(data):
                half = max(1, len(buf) // 2)
                self._stream.write(buf[:half])
                return half
            return self._stream.write(buf)

        def flush(self) -> None:
            self._stream.flush()

        def fileno(self) -> int:
            return self._stream.fileno()

        def __enter__(self) -> "_ShortWriter":
            return self

        def __exit__(self, *args: object) -> None:
            self._stream.close()

    def wrapping_fdopen(fd: int, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        stream = real_fdopen(fd, mode, *args, **kwargs)
        if "w" in mode:
            return _ShortWriter(stream)
        return stream

    with mock.patch("ipfs_kit_py.proof_seal_store.local_store.os.fdopen", wrapping_fdopen):
        result = store.put_immutable_result(ArtifactKind.PROOF_OBJECT, data)
    assert not result.stored
    assert result.reason is LocalStoreReason.SHORT_WRITE
    assert not list(tmp_path.rglob("*.blob"))
    with pytest.raises(LocalStoreError) as exc_info:
        with mock.patch(
            "ipfs_kit_py.proof_seal_store.local_store.os.fdopen", wrapping_fdopen
        ):
            store.put_immutable(ArtifactKind.PROOF_OBJECT, data)
    assert exc_info.value.reason is LocalStoreReason.SHORT_WRITE


def test_fsync_failure_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"fsync-fail")
    calls = {"n": 0}
    real_fsync = os.fsync

    def flaky_fsync(fd: int) -> None:
        calls["n"] += 1
        # Fail the first fsync (object file) so the put never publishes.
        if calls["n"] == 1:
            raise OSError("simulated fsync failure")
        return real_fsync(fd)

    with mock.patch("ipfs_kit_py.proof_seal_store.local_store.os.fsync", flaky_fsync):
        result = store.put_immutable_result(ArtifactKind.DELTA_SEAL, data)
    assert not result.stored
    assert result.reason is LocalStoreReason.FSYNC_FAILED
    assert not list(tmp_path.rglob("*.blob"))


def test_parent_fsync_failure_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"parent-fsync")
    real_fsync = os.fsync
    state = {"file_fsyncs": 0}

    def selective_fsync(fd: int) -> None:
        # First fsync is the temp file; second is the parent directory.
        state["file_fsyncs"] += 1
        if state["file_fsyncs"] >= 2:
            raise OSError("simulated parent fsync failure")
        return real_fsync(fd)

    with mock.patch(
        "ipfs_kit_py.proof_seal_store.local_store.os.fsync", selective_fsync
    ):
        result = store.put_immutable_result(ArtifactKind.CHECKPOINT_SEAL, data)
    assert not result.stored
    assert result.reason is LocalStoreReason.FSYNC_FAILED
    # Published blob must not remain after parent fsync failure.
    assert not list(tmp_path.rglob("*.blob"))


def test_readback_failure_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"readback")
    real_read = HermeticProofSealStore._read_object_locked
    state = {"post_publish": False}

    def tracking_read(self: HermeticProofSealStore, path: Path, reference: ArtifactReference):
        result = real_read(self, path, reference)
        # After a successful-looking publish the write path always readbacks;
        # force the first post-create readback to fail integrity.
        if path.exists() and result.hit and not state["post_publish"]:
            state["post_publish"] = True
            from ipfs_kit_py.proof_seal_store.local_store import LocalGetResult

            return LocalGetResult(
                StoreGetDisposition.INTEGRITY_FAILED,
                LocalStoreReason.CORRUPTED,
                reference=reference,
                byte_length=len(data),
            )
        return result

    with mock.patch.object(
        HermeticProofSealStore, "_read_object_locked", tracking_read
    ):
        result = store.put_immutable_result(ArtifactKind.TOMBSTONE, data)
    assert not result.stored
    assert result.reason is LocalStoreReason.READBACK_FAILED


# ---------------------------------------------------------------------------
# Corruption
# ---------------------------------------------------------------------------


def test_corrupted_object_fails_closed_on_get(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"corrupt-me")
    ref = store.put_immutable(ArtifactKind.PROOF_OBJECT, data)
    path = store._object_path(ref.kind, ref.cid, create_parent=False)
    path.write_bytes(b"tampered-bytes-not-matching-cid")

    result = store.get_verified_bytes_result(ref)
    assert not result.hit
    assert result.disposition is StoreGetDisposition.INTEGRITY_FAILED
    assert result.reason is LocalStoreReason.CORRUPTED
    with pytest.raises(LocalStoreIntegrityError) as exc_info:
        store.get_verified_bytes(ref)
    assert exc_info.value.reason is LocalStoreReason.CORRUPTED


def test_missing_object_is_a_miss(tmp_path: Path) -> None:
    store = _store(tmp_path)
    data = _payload(b"missing")
    cid = content_cid_for_bytes(data)
    ref = ArtifactReference(
        cid=cid, kind=ArtifactKind.PROOF_OBJECT, byte_length=len(data)
    )
    result = store.get_verified_bytes_result(ref)
    assert result.disposition is StoreGetDisposition.MISS
    assert result.reason is LocalStoreReason.NOT_FOUND
    with pytest.raises(LocalStoreNotFoundError):
        store.get_verified_bytes(ref)


def test_content_identity_helpers() -> None:
    data = b"identity-helpers"
    cid = content_cid_for_bytes(data)
    digest = content_digest_hex(data)
    assert digest == hashlib.sha256(data).hexdigest()
    assert verify_content_identity(cid, data)
    assert verify_content_identity(f"sha256:{digest}", data)
    assert not verify_content_identity(cid, data + b"x")
    assert not verify_content_identity("not-a-cid", data)
