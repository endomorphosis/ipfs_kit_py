from ipfs_kit_py.proof_certificate_store import ProofCertificateStore
from ipfs_kit_py.content_addressed_artifact_store import ArtifactStoreReason


def test_candidate_context_is_explicitly_non_authoritative(tmp_path):
    store = ProofCertificateStore(tmp_path)
    written = store.put_candidate("case-1", certificate={"proof": "candidate"}, context={"seed": 3})
    assert written.found
    assert written.candidate.authoritative is False
    recovered = store.get_candidate("case-1")
    assert recovered.found
    assert recovered.candidate.requires_verification is True


def test_candidate_index_is_bounded_and_quarantines_malformed_records(tmp_path):
    store = ProofCertificateStore(tmp_path)
    assert store.put_candidate("case-1", context={"seed": 3}).found
    path = store.index_root / store._index_name("case-1")
    path.write_bytes(b'{"locator":"case-1"}')
    recovered = store.get_candidate("case-1")
    assert recovered.reason is ArtifactStoreReason.CORRUPT
    assert any(store.index_quarantine_root.iterdir())
