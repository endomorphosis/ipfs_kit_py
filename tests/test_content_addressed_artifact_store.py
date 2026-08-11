import os

import pytest

from ipfs_kit_py.content_addressed_artifact_store import (
    ArtifactStoreReason,
    ContentAddressedArtifactStore,
    canonical_dag_json_bytes,
    cid_for_canonical_bytes,
    is_canonical_dag_json,
    validate_dag_json_cid,
)
from ipfs_kit_py.proof_certificate_store import ProofCertificateStore


def test_exact_canonical_bytes_round_trip_with_cidv1_profile(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    data = canonical_dag_json_bytes({"z": [2, 1], "a": "é"})
    cid = cid_for_canonical_bytes(data)
    assert validate_dag_json_cid(cid)
    assert store.put_bytes(data, claimed_cid=cid).accepted
    assert store.get_bytes(cid).data == data


def test_corrupt_and_oversized_blobs_are_quarantined(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path, max_blob_bytes=32)
    data = canonical_dag_json_bytes({"a": 1})
    cid = cid_for_canonical_bytes(data)
    assert store.put_bytes(data).accepted
    path = store._blob_path(cid)
    path.write_bytes(b'{"a":2}')
    assert store.get_bytes(cid).reason is ArtifactStoreReason.CORRUPT
    assert any(store.quarantine_root.iterdir())
    path = store._blob_path(cid, create_parent=True)
    path.write_bytes(b"x" * 33)
    assert store.get_bytes(cid).reason is ArtifactStoreReason.TOO_LARGE


def test_path_escaping_cid_is_rejected_without_creating_paths(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    assert store.get_bytes("b../../escape").reason is ArtifactStoreReason.INVALID_CID
    assert not (tmp_path / "escape").exists()


def test_symlinked_blob_is_quarantined_without_following_it(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    written = store.put({"a": 1})
    path = store._blob_path(written.cid)
    path.unlink()
    outside = tmp_path / "outside.json"
    outside.write_text('{"a":1}', encoding="utf-8")
    path.symlink_to(outside)
    assert store.get_bytes(written.cid).reason is ArtifactStoreReason.SYMLINK
    assert outside.exists()


def test_root_children_cannot_be_swapped_for_symlinked_destinations(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path / "trusted")
    written = store.put({"a": 1})
    blob_path = store._blob_path(written.cid)
    blob_path.write_bytes(b'{"a":2}')
    outside = tmp_path / "outside"
    outside.mkdir()

    # The store retains an fd for its root.  Replacing the quarantine pathname
    # must turn a corrupt read into a safe miss, never a move into ``outside``.
    held_quarantine = tmp_path / "held-quarantine"
    store.quarantine_root.rename(held_quarantine)
    store.quarantine_root.symlink_to(outside, target_is_directory=True)
    assert store.get_bytes(written.cid).reason is ArtifactStoreReason.CORRUPT
    assert list(outside.iterdir()) == []


def test_deep_json_is_a_bounded_failure_with_the_pure_python_encoder(tmp_path, monkeypatch):
    """Deep hostile inputs must not depend on whichever JSON encoder is active."""
    import json.encoder

    monkeypatch.setattr(json.encoder, "c_make_encoder", None)
    value = 0
    for _ in range(1_100):
        value = [value]
    raw = b"[" * 1_100 + b"0" + b"]" * 1_100
    assert len(raw) < 16_384

    with pytest.raises(ValueError):
        canonical_dag_json_bytes(value)
    assert not is_canonical_dag_json(raw)
    with pytest.raises(ValueError):
        cid_for_canonical_bytes(raw)

    store = ContentAddressedArtifactStore(tmp_path / "artifacts")
    assert store.put(value).reason is ArtifactStoreReason.NOT_CANONICAL
    assert store.put_bytes(raw).reason is ArtifactStoreReason.NOT_CANONICAL

    # Place hostile bytes under an otherwise valid name, emulating a corrupt
    # on-disk cache entry.  Reading it must return a typed miss and move only
    # within the fd-anchored trusted quarantine root.
    valid = store.put({"safe": True})
    path = store._blob_path(valid.cid)
    assert path is not None
    path.write_bytes(raw)
    assert store.get_bytes(valid.cid).reason is ArtifactStoreReason.CORRUPT
    assert any(store.quarantine_root.iterdir())

    candidates = ProofCertificateStore(tmp_path / "candidates")
    # Candidate publication must reject the same hostile value before an index
    # record can be emitted; this exercises its write boundary, not just reads.
    assert candidates.put_candidate("deep-put", context=value).found is False
    assert candidates.put_candidate("deep-record", context={"safe": True}).found
    candidate_path = candidates.index_root / candidates._index_name("deep-record")
    candidate_path.write_bytes(raw)
    assert candidates.get_candidate("deep-record").reason is ArtifactStoreReason.CORRUPT
    assert any(candidates.index_quarantine_root.iterdir())


def test_lone_surrogate_cids_are_total_invalid_inputs(tmp_path):
    bad = "b" + "a" * 9 + chr(0xD800)
    store = ContentAddressedArtifactStore(tmp_path / "artifacts")
    candidates = ProofCertificateStore(tmp_path / "candidates")

    assert validate_dag_json_cid(bad) is False
    assert store.get_bytes(bad).found is False
    assert store.put_bytes(b"{}", claimed_cid=bad).accepted is False
    assert candidates.put_candidate("bad-cid", certificate_cid=bad).found is False
