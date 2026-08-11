from ipfs_kit_py.content_addressed_artifact_store import ArtifactStoreReason, ContentAddressedArtifactStore


def test_transport_payload_is_only_accepted_after_local_verification(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    accepted = store.put({"certificate": "hint"})
    assert accepted.accepted
    rejected = store.import_from_transport(accepted.cid, b'{"certificate":"different"}')
    assert rejected.reason is ArtifactStoreReason.CID_MISMATCH
    assert store.get(accepted.cid) == {"certificate": "hint"}

