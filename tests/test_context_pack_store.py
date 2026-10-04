"""ASEH-032: Kit ContextPack store, current-root CAS, WAL recovery, and vectors."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import pytest

from ipfs_kit_py.proof_context.artifacts import ArtifactIdentityError, cid_for_bytes
from ipfs_kit_py.proof_context.incremental_seal_store import (
    IncrementalSealStore,
    open_incremental_seal_store,
)
from ipfs_kit_py.proof_context.state_store import (
    CONTEXT_PACK_INTERFACE,
    CONTEXT_PACK_NAMESPACE,
    CONTEXT_PACK_RECORD_FIELDS,
    CONTEXT_PACK_SCHEMA,
    CONTEXT_PACK_VECTOR_RESOURCE,
    CONTEXT_PACK_VECTOR_SCHEMA,
    ContextPackMasqueradeError,
    ContextPackStore,
    KitProofContextStateStore,
    StaleContextPackCasError,
    UnknownFieldError,
    apply_context_pack_contract_vectors,
    load_context_pack_contract_vectors,
    open_context_pack_store,
    open_local_store,
    validate_context_pack_record,
)
from ipfs_kit_py.proof_context.verification_store import (
    KitVerificationStore,
    StaleWriterError,
    open_verification_store,
)
from ipfs_kit_py.proof_seal_store.contracts import ArtifactKind
from ipfs_kit_py.proof_seal_store.local_store import LocalStoreIntegrityError
from ipfs_kit_py.proof_seal_store.wal import SealTransitionWalCrash


def _payload(tag: bytes) -> bytes:
    return b'{"namespace":"ContextPack","tag":"' + tag + b'"}'


def _corrupt_blobs(root: Path) -> None:
    blobs = list((root / "objects").rglob("*.blob"))
    assert blobs, "expected admitted blobs under the hermetic object store"
    for blob in blobs:
        blob.write_bytes(blob.read_bytes() + b"\x00corrupt")


def test_real_cid_equality(tmp_path: Path) -> None:
    store = open_context_pack_store(tmp_path)
    payload = _payload(b"cid-eq")
    reference = store.put_verified_bytes(payload)
    assert reference.cid == cid_for_bytes(payload)
    assert reference.cid.startswith("b")
    assert "sha256:" not in reference.cid
    assert not reference.cid.startswith("Qm")
    assert store.get_immutable(reference) == payload
    with pytest.raises((ArtifactIdentityError, Exception)):
        store.put_verified_bytes(payload, claimed_cid="b" + "a" * 58)
    store.close()


def test_immutable_get_rejects_mutation_and_corruption(tmp_path: Path) -> None:
    store = open_context_pack_store(tmp_path)
    payload = _payload(b"immutable")
    reference = store.put_verified_bytes(payload)
    assert store.get_immutable(reference) == payload
    rewritten = store.put_verified_bytes(payload)
    assert rewritten.cid == reference.cid
    _corrupt_blobs(tmp_path)
    with pytest.raises((ArtifactIdentityError, LocalStoreIntegrityError)):
        store.get_immutable(reference)
    store.close()


def test_candidate_storage_does_not_publish_current_root(tmp_path: Path) -> None:
    store = open_context_pack_store(tmp_path)
    payload = _payload(b"candidate")
    reference = store.put_candidate(payload, cache_key="pack:candidate")
    assert store.get_candidate("pack:candidate")["cid"] == reference.cid
    assert store.get_candidate("pack:candidate")["role"] == "candidate"
    assert store.current_root() is None
    assert store.get_immutable(reference) == payload
    store.close()


def test_stale_cas_rejection(tmp_path: Path) -> None:
    store = open_context_pack_store(tmp_path)
    first = store.put_verified_bytes(_payload(b"first"))
    second = store.put_verified_bytes(_payload(b"second"), kind=ArtifactKind.DELTA_SEAL)
    third = store.put_verified_bytes(_payload(b"third"), kind=ArtifactKind.DELTA_SEAL)
    published = store.compare_and_swap_current_root(new_cid=first.cid, generation=0)
    assert published.seal_cid == first.cid
    assert published.generation == 0
    with pytest.raises(StaleContextPackCasError):
        store.compare_and_swap_current_root(
            new_cid=second.cid,
            expected_parent_cid="",
            generation=0,
            kind=ArtifactKind.DELTA_SEAL,
        )
    with pytest.raises(StaleContextPackCasError):
        store.compare_and_swap_current_root(
            new_cid=third.cid,
            expected_parent_cid=second.cid,
            generation=1,
            kind=ArtifactKind.DELTA_SEAL,
        )
    advanced = store.compare_and_swap_current_root(
        new_cid=second.cid,
        expected_parent_cid=first.cid,
        generation=1,
        kind=ArtifactKind.DELTA_SEAL,
    )
    assert advanced.seal_cid == second.cid
    assert store.current_root().seal_cid == second.cid
    store.close()


def test_wal_crash_recovery_uncommitted_is_not_current(tmp_path: Path) -> None:
    payload = _payload(b"crash-begin")
    admitted = open_context_pack_store(tmp_path)
    reference = admitted.put_verified_bytes(payload)
    admitted.close()

    def crash_after_begin(boundary: str, *args: object, **kwargs: object) -> None:
        if boundary == "after_begin":
            raise SealTransitionWalCrash(boundary)

    crashed = ContextPackStore(tmp_path, crash_injector=crash_after_begin)
    with pytest.raises(SealTransitionWalCrash):
        crashed.compare_and_swap_current_root(new_cid=reference.cid, generation=0)
    crashed.close()

    recovered = open_context_pack_store(tmp_path)
    report = recovered.recover()
    assert recovered.current_root() is None
    again = recovered.recover()
    assert again.dispositions == report.dispositions
    assert recovered.current_root() is None
    recovered.close()


def test_wal_crash_recovery_after_cas_converges(tmp_path: Path) -> None:
    payload = _payload(b"crash-cas")
    admitted = open_context_pack_store(tmp_path)
    reference = admitted.put_verified_bytes(payload)
    admitted.close()

    def crash_after_cas(boundary: str, *args: object, **kwargs: object) -> None:
        if boundary == "after_current_root_cas":
            raise SealTransitionWalCrash(boundary)

    crashed = ContextPackStore(tmp_path, crash_injector=crash_after_cas)
    with pytest.raises(SealTransitionWalCrash):
        crashed.compare_and_swap_current_root(new_cid=reference.cid, generation=0)
    crashed.close()

    recovered = open_context_pack_store(tmp_path)
    recovered.recover()
    current = recovered.current_root()
    assert current is not None
    assert current.seal_cid == reference.cid
    recovered.recover()
    assert recovered.current_root() == current
    recovered.close()


def test_retention_tombstones_candidates_and_keeps_current(tmp_path: Path) -> None:
    store = open_context_pack_store(tmp_path)
    current_payload = _payload(b"keep")
    stale_payload = _payload(b"drop")
    current_ref = store.put_candidate(current_payload, cache_key="pack:keep")
    stale_ref = store.put_candidate(stale_payload, cache_key="pack:drop")
    store.compare_and_swap_current_root(new_cid=current_ref.cid, generation=0)
    result = store.apply_retention()
    assert result["current_cid"] == current_ref.cid
    assert "pack:keep" in result["retained"]
    assert "pack:drop" in result["tombstoned"]
    assert store.get_candidate("pack:drop") is None
    assert store.get_candidate("pack:keep") is not None
    assert store.current_root().seal_cid == current_ref.cid
    assert store.get_immutable(current_ref) == current_payload
    assert store.get_immutable(stale_ref) == stale_payload
    with pytest.raises(Exception):
        store.publish_candidate("pack:drop", expected_parent_cid=current_ref.cid, generation=1)
    store.close()


def test_unknown_field_vectors() -> None:
    vectors = load_context_pack_contract_vectors()
    assert vectors["schema"] == CONTEXT_PACK_VECTOR_SCHEMA
    assert vectors["namespace"] == CONTEXT_PACK_NAMESPACE
    assert set(vectors["closed_fields"]) == set(CONTEXT_PACK_RECORD_FIELDS)
    results = apply_context_pack_contract_vectors(vectors)
    by_id = {item["id"]: item for item in results}
    assert by_id["valid-admitted-seal"]["status"] == "accept"
    assert by_id["unknown-field-top-level"]["status"] == "reject"
    assert by_id["unknown-field-top-level"]["reason"] == "unknown_field"
    assert by_id["unknown-field-semantic-claim"]["reason"] == "unknown_field"
    assert by_id["unknown-field-reuse-admission"]["reason"] == "unknown_field"
    assert by_id["proof-object-masquerade-current"]["reason"] == "masquerade"
    with pytest.raises(UnknownFieldError, match="unknown field"):
        validate_context_pack_record(
            {
                "schema": CONTEXT_PACK_SCHEMA,
                "interface": CONTEXT_PACK_INTERFACE,
                "namespace": CONTEXT_PACK_NAMESPACE,
                "role": "admitted",
                "kind": "checkpoint_seal",
                "extra": 1,
            }
        )


def test_package_data_installation() -> None:
    resource = files("ipfs_kit_py.proof_context").joinpath(CONTEXT_PACK_VECTOR_RESOURCE)
    assert resource.is_file()
    installed = json.loads(resource.read_text(encoding="utf-8"))
    loaded = load_context_pack_contract_vectors()
    assert installed == loaded
    assert installed["interface"] == CONTEXT_PACK_INTERFACE
    assert installed["namespace"] == CONTEXT_PACK_NAMESPACE
    results = apply_context_pack_contract_vectors()
    assert {item["id"] for item in results} == {case["id"] for case in installed["cases"]}


def test_proof_object_masquerade_rejected(tmp_path: Path) -> None:
    store = open_context_pack_store(tmp_path)
    with pytest.raises(ContextPackMasqueradeError):
        store.put_verified_bytes(_payload(b"obj"), kind=ArtifactKind.PROOF_OBJECT)
    with pytest.raises(ContextPackMasqueradeError):
        store.put_candidate(_payload(b"obj"), kind=ArtifactKind.PROOF_OBJECT)
    store.close()


def test_state_store_context_pack_namespace(tmp_path: Path) -> None:
    store = open_local_store(tmp_path)
    assert store.context_pack_namespace == CONTEXT_PACK_NAMESPACE
    payload = _payload(b"state")
    reference = store.put_context_pack(payload)
    assert store.get_context_pack(reference) == payload
    candidate = store.put_context_pack_candidate(payload, cache_key="pack:state")
    assert store.context_pack.current_root() is None
    pointer = store.compare_and_swap_context_pack_root(new_cid=candidate.cid, generation=0)
    assert pointer.repository_id == CONTEXT_PACK_NAMESPACE
    retained = store.retain_context_pack()
    assert retained["current_cid"] == candidate.cid
    store.recover_context_pack()
    generic = store.put(b'{"kind":"proof_object"}')
    assert store.get(generic) == b'{"kind":"proof_object"}'


def test_incremental_seal_store_context_pack_namespace(tmp_path: Path) -> None:
    store = open_incremental_seal_store(tmp_path)
    assert isinstance(store, IncrementalSealStore)
    assert store.context_pack_namespace == CONTEXT_PACK_NAMESPACE
    payload = _payload(b"seal")
    candidate = store.put_context_pack_candidate_seal(payload, cache_key="seal:candidate")
    assert store.context_pack.current_root() is None
    published = store.publish_context_pack_seal(
        _payload(b"published"),
        cache_key="seal:published",
        generation=0,
    )
    assert store.context_pack.current_root().seal_cid == published.cid
    with pytest.raises(StaleWriterError):
        store.publish_context_pack_seal(
            _payload(b"stale"),
            expected_parent_cid="",
            generation=0,
            cache_key="seal:stale",
        )
    assert store.get_seal(candidate) == payload
    store.close()


def test_verification_store_context_pack_namespace(tmp_path: Path) -> None:
    store = open_verification_store(tmp_path)
    assert isinstance(store, KitVerificationStore)
    assert store.context_pack_namespace == CONTEXT_PACK_NAMESPACE
    payload = b'{"kind":"proof_receipt","namespace":"ContextPack"}'
    receipt = store.put_context_pack_verification_receipt(
        payload,
        generation=0,
        expected_generation=0,
        record={
            "schema": CONTEXT_PACK_SCHEMA,
            "interface": CONTEXT_PACK_INTERFACE,
            "namespace": CONTEXT_PACK_NAMESPACE,
            "role": "admitted",
            "cid": cid_for_bytes(payload),
            "kind": "proof_receipt",
            "generation": 0,
            "parent_cid": "",
            "cache_key": "receipt:one",
            "byte_length": len(payload),
        },
    )
    assert store.get_context_pack_verification_receipt(receipt) == payload
    with pytest.raises(UnknownFieldError):
        store.put_context_pack_verification_receipt(
            payload,
            record={
                "schema": CONTEXT_PACK_SCHEMA,
                "interface": CONTEXT_PACK_INTERFACE,
                "namespace": CONTEXT_PACK_NAMESPACE,
                "role": "admitted",
                "kind": "proof_receipt",
                "freshness_admitted": True,
            },
        )
    with pytest.raises(StaleWriterError):
        store.put_context_pack_verification_receipt(payload, generation=4)
    store.close()


def test_kit_state_store_still_rejects_optional_ipfs(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        KitProofContextStateStore(tmp_path, enable_ipfs=True)
