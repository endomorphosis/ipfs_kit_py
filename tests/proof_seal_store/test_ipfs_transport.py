"""Regression tests for the optional injected IPFS transport adapter (IPS-020).

Acceptance coverage:

* mocked corrupt / oversized / wrong-kind responses fail closed;
* backend ambiguity is recorded and never treated as success;
* local committed bytes remain reconcilable after remote faults;
* injected client only; network absence is typed unavailable;
* proving keys / witnesses are forbidden; public kinds only;
* cold construction needs no daemon or ``~/.ipfs``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ArtifactReference,
    ArtifactRole,
)
from ipfs_kit_py.proof_seal_store.local_store import (
    HermeticProofSealStore,
    content_cid_for_bytes,
    content_digest_hex,
    sha256_content_id,
    verify_content_identity,
)
from ipfs_kit_py.proof_seal_store.ipfs_transport import (
    DEFAULT_TIMEOUT_SECONDS,
    EVIDENCE_SUBSET,
    IPFS_TRANSPORT_INTERFACE,
    PUBLIC_ARTIFACT_KINDS,
    IpfsProofArtifactTransport,
    TransportDisposition,
    TransportReason,
    TransportSource,
)


def _payload(tag: bytes = b"ipfs-transport") -> bytes:
    return b'{"kind":"proof_object","tag":"' + tag + b'"}'


def _local(tmp_path: Path, **kwargs: Any) -> HermeticProofSealStore:
    return HermeticProofSealStore(tmp_path, **kwargs)


def _admit(
    store: HermeticProofSealStore,
    data: bytes,
    kind: ArtifactKind = ArtifactKind.PROOF_OBJECT,
) -> ArtifactReference:
    return store.put_immutable(kind, data)


# ---------------------------------------------------------------------------
# Construction / hermetic defaults
# ---------------------------------------------------------------------------


def test_schema_and_evidence_constants() -> None:
    assert EVIDENCE_SUBSET == "ips/ipfs-proof-transport@1"
    assert IPFS_TRANSPORT_INTERFACE == "IpfsProofArtifactTransport@1"
    assert PUBLIC_ARTIFACT_KINDS == frozenset(ArtifactKind)
    assert DEFAULT_TIMEOUT_SECONDS > 0


def test_default_transport_has_no_network_and_is_unavailable() -> None:
    transport = IpfsProofArtifactTransport()
    assert not transport.available
    assert not transport.ipfs_read_enabled
    assert not transport.ipfs_write_enabled
    assert transport.local_store is None

    data = _payload(b"no-network")
    cid = content_cid_for_bytes(data)
    put = transport.replicate_public_artifact(
        ArtifactKind.PROOF_OBJECT, data, claimed_cid=cid
    )
    assert put.disposition is TransportDisposition.UNAVAILABLE
    assert put.reason is TransportReason.UNAVAILABLE
    assert not put.succeeded
    assert not put.ipfs_stored

    fetch = transport.fetch_public_artifact(
        ArtifactReference(cid=cid, kind=ArtifactKind.PROOF_OBJECT, byte_length=len(data))
    )
    assert fetch.disposition is TransportDisposition.UNAVAILABLE
    assert fetch.reason is TransportReason.UNAVAILABLE
    assert not fetch.hit


def test_injected_client_methods_are_discovered() -> None:
    data = _payload(b"client")
    cid = content_cid_for_bytes(data)
    calls: list[str] = []

    class _Client:
        def block_get(self, requested: str) -> bytes:
            calls.append(f"get:{requested}")
            return data

        def block_put(self, payload: bytes) -> dict[str, str]:
            calls.append(f"put:{len(payload)}")
            return {"Hash": content_cid_for_bytes(payload)}

    transport = IpfsProofArtifactTransport(ipfs_client=_Client())
    assert transport.available
    put = transport.replicate_public_artifact(ArtifactKind.PROOF_RECEIPT, data)
    assert put.succeeded and put.ipfs_stored
    fetch = transport.fetch_public_artifact(
        ArtifactReference(cid=cid, kind=ArtifactKind.PROOF_RECEIPT, byte_length=len(data))
    )
    assert fetch.hit and fetch.data == data
    assert calls == [f"put:{len(data)}", f"get:{cid}"]


# ---------------------------------------------------------------------------
# Happy path + local reconciliation
# ---------------------------------------------------------------------------


def test_replicate_from_local_committed_bytes(tmp_path: Path) -> None:
    store = _local(tmp_path)
    data = _payload(b"local-rep")
    ref = _admit(store, data)
    puts: list[bytes] = []

    def ipfs_put(payload: bytes) -> dict[str, str]:
        puts.append(payload)
        return {"cid": content_cid_for_bytes(payload)}

    transport = IpfsProofArtifactTransport(local_store=store, ipfs_put=ipfs_put)
    result = transport.replicate_public_artifact(reference=ref)
    assert result.succeeded
    assert result.local_reconciled is True
    assert result.ipfs_stored is True
    assert result.reference == ref
    assert puts == [data]
    # Local remains reconcilable after remote success.
    reconciled = transport.reconcile_local(ref)
    assert reconciled.hit and reconciled.data == data
    assert reconciled.source is TransportSource.LOCAL


def test_fetch_prefers_local_and_caches_remote(tmp_path: Path) -> None:
    store = _local(tmp_path)
    data = _payload(b"cache-remote")
    cid = content_cid_for_bytes(data)
    ref = ArtifactReference(
        cid=cid, kind=ArtifactKind.MERKLE_NODE, byte_length=len(data)
    )
    remote_calls: list[str] = []

    def ipfs_get(requested: str) -> bytes:
        remote_calls.append(requested)
        return data

    transport = IpfsProofArtifactTransport(
        local_store=store, ipfs_get=ipfs_get, cache_remote_reads=True
    )
    first = transport.fetch_public_artifact(ref)
    assert first.hit
    assert first.source is TransportSource.LOCAL_AND_IPFS
    assert first.local_reconciled is True
    assert first.data == data
    assert remote_calls == [cid]

    # Second fetch is served from local without remote I/O.
    second = transport.fetch_public_artifact(ref)
    assert second.hit
    assert second.source is TransportSource.LOCAL
    assert remote_calls == [cid]
    assert store.get_verified_bytes(ref) == data


def test_sha256_content_identity_round_trip(tmp_path: Path) -> None:
    store = _local(tmp_path)
    data = _payload(b"sha-id")
    sha_id = sha256_content_id(data)
    ref = store.put_immutable(
        ArtifactKind.PROOF_MANIFEST, data, claimed_cid=sha_id
    )
    assert ref.cid == sha_id

    transport = IpfsProofArtifactTransport(
        local_store=store,
        ipfs_put=lambda payload: {"Key": content_cid_for_bytes(payload)},
        ipfs_get=lambda _cid: data,
    )
    put = transport.replicate_public_artifact(reference=ref)
    assert put.succeeded
    # Fetch by sha256 identity still rehashes.
    fetch = transport.fetch_public_artifact(ref, prefer_local=False)
    assert fetch.hit and fetch.data == data


# ---------------------------------------------------------------------------
# Corrupt / oversized / wrong-kind fail closed
# ---------------------------------------------------------------------------


def test_corrupt_remote_bytes_fail_closed_and_local_stays_reconcilable(
    tmp_path: Path,
) -> None:
    store = _local(tmp_path)
    data = _payload(b"corrupt-remote")
    ref = _admit(store, data)

    transport = IpfsProofArtifactTransport(
        local_store=store,
        ipfs_get=lambda _cid: data + b"\x00tampered",
    )
    # Prefer remote path so the corrupt body is exercised.
    result = transport.fetch_public_artifact(ref, prefer_local=False)
    assert not result.hit
    assert result.disposition is TransportDisposition.REJECTED
    assert result.reason is TransportReason.CORRUPTED
    assert result.local_reconciled is True
    # Local committed bytes remain independently reconcilable.
    assert transport.reconcile_local(ref).data == data
    assert store.get_verified_bytes(ref) == data


def test_oversized_remote_response_fails_closed(tmp_path: Path) -> None:
    data = _payload(b"oversized")
    cid = content_cid_for_bytes(data)
    ref = ArtifactReference(
        cid=cid, kind=ArtifactKind.PROOF_OBJECT, byte_length=len(data)
    )
    transport = IpfsProofArtifactTransport(
        ipfs_get=lambda _cid: b"x" * 64,
        max_artifact_bytes=16,
    )
    result = transport.fetch_public_artifact(ref)
    assert not result.hit
    assert result.disposition is TransportDisposition.REJECTED
    assert result.reason is TransportReason.OVER_BUDGET


def test_oversized_replicate_payload_fails_closed() -> None:
    transport = IpfsProofArtifactTransport(
        ipfs_put=lambda payload: {"Hash": content_cid_for_bytes(payload)},
        max_artifact_bytes=8,
    )
    result = transport.replicate_public_artifact(
        ArtifactKind.PROOF_OBJECT, b"0123456789"
    )
    assert not result.succeeded
    assert result.disposition is TransportDisposition.REJECTED
    assert result.reason is TransportReason.OVER_BUDGET


def test_wrong_kind_envelope_fails_closed() -> None:
    data = _payload(b"wrong-kind")
    cid = content_cid_for_bytes(data)
    ref = ArtifactReference(
        cid=cid, kind=ArtifactKind.PROOF_OBJECT, byte_length=len(data)
    )

    def wrong_kind_get(_cid: str) -> dict[str, Any]:
        return {
            "kind": ArtifactKind.PROOF_RECEIPT.value,
            "data": data,
        }

    transport = IpfsProofArtifactTransport(ipfs_get=wrong_kind_get)
    result = transport.fetch_public_artifact(ref)
    assert not result.hit
    assert result.disposition is TransportDisposition.REJECTED
    assert result.reason is TransportReason.WRONG_KIND


def test_kind_mismatch_on_fetch_argument_fails_closed(tmp_path: Path) -> None:
    store = _local(tmp_path)
    data = _payload(b"kind-arg")
    ref = _admit(store, data, kind=ArtifactKind.PROOF_OBJECT)
    transport = IpfsProofArtifactTransport(local_store=store)
    result = transport.fetch_public_artifact(
        ref, kind=ArtifactKind.DELTA_SEAL
    )
    assert not result.hit
    assert result.reason is TransportReason.KIND_MISMATCH


def test_unknown_kind_string_in_envelope_fails_closed() -> None:
    data = _payload(b"unknown-kind")
    cid = content_cid_for_bytes(data)
    ref = ArtifactReference(cid=cid, kind=ArtifactKind.TOMBSTONE)

    transport = IpfsProofArtifactTransport(
        ipfs_get=lambda _cid: {"kind": "not_a_real_kind", "data": data}
    )
    result = transport.fetch_public_artifact(ref)
    assert not result.hit
    assert result.reason is TransportReason.WRONG_KIND


# ---------------------------------------------------------------------------
# Forbidden proving-key / witness material
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden",
    ["proving_key", "witness", "private_witness", "witness_material"],
)
def test_forbidden_kinds_rejected_on_replicate(forbidden: str) -> None:
    transport = IpfsProofArtifactTransport(
        ipfs_put=lambda payload: {"Hash": content_cid_for_bytes(payload)}
    )
    result = transport.replicate_public_artifact(forbidden, b"secret-material")
    assert not result.succeeded
    assert result.disposition is TransportDisposition.REJECTED
    assert result.reason is TransportReason.FORBIDDEN_KIND


@pytest.mark.parametrize(
    "forbidden",
    ["proving_key", "witness", "secret_witness"],
)
def test_forbidden_kinds_rejected_on_fetch(forbidden: str) -> None:
    data = b"not-public"
    cid = content_cid_for_bytes(data)
    transport = IpfsProofArtifactTransport(ipfs_get=lambda _cid: data)
    result = transport.fetch_public_artifact(cid, kind=forbidden)
    assert not result.hit
    assert result.reason is TransportReason.FORBIDDEN_KIND


def test_forbidden_kind_in_remote_envelope_fails_closed() -> None:
    data = _payload(b"forbidden-envelope")
    cid = content_cid_for_bytes(data)
    ref = ArtifactReference(cid=cid, kind=ArtifactKind.VERIFICATION_KEY)
    transport = IpfsProofArtifactTransport(
        ipfs_get=lambda _cid: {"kind": "proving_key", "data": data}
    )
    result = transport.fetch_public_artifact(ref)
    assert not result.hit
    assert result.reason is TransportReason.FORBIDDEN_KIND


# ---------------------------------------------------------------------------
# Backend ambiguity is recorded
# ---------------------------------------------------------------------------


def test_put_response_without_cid_is_ambiguous_and_recorded(tmp_path: Path) -> None:
    store = _local(tmp_path)
    data = _payload(b"no-cid")
    ref = _admit(store, data)
    transport = IpfsProofArtifactTransport(
        local_store=store,
        ipfs_put=lambda _payload: {"status": "ok"},  # no CID
    )
    result = transport.replicate_public_artifact(reference=ref)
    assert not result.succeeded
    assert result.disposition is TransportDisposition.AMBIGUOUS
    assert result.reason is TransportReason.BACKEND_AMBIGUOUS
    assert result.ambiguity is not None
    assert result.ambiguity.local_ok is True
    assert result.local_reconciled is True
    assert len(transport.ambiguities) == 1
    assert transport.ambiguities[0].reason is TransportReason.IPFS_RESPONSE_INVALID
    # Local committed bytes remain reconcilable despite ambiguous remote put.
    assert transport.reconcile_local(ref).data == data


def test_put_response_cid_mismatch_is_ambiguous(tmp_path: Path) -> None:
    store = _local(tmp_path)
    data = _payload(b"cid-mismatch-put")
    ref = _admit(store, data)
    wrong = content_cid_for_bytes(b"other-bytes")
    transport = IpfsProofArtifactTransport(
        local_store=store,
        ipfs_put=lambda _payload: {"Key": wrong},
    )
    result = transport.replicate_public_artifact(reference=ref)
    assert result.disposition is TransportDisposition.AMBIGUOUS
    assert result.reason is TransportReason.BACKEND_AMBIGUOUS
    assert result.ambiguity is not None
    assert result.ambiguity.reason is TransportReason.CID_MISMATCH
    assert result.local_reconciled is True
    assert store.get_verified_bytes(ref) == data


def test_local_corruption_with_valid_remote_is_ambiguous(tmp_path: Path) -> None:
    store = _local(tmp_path)
    data = _payload(b"local-corrupt")
    ref = _admit(store, data)
    # Tamper the on-disk blob under the digest path.
    digest = content_digest_hex(data)
    blob = tmp_path / "objects" / ref.kind.value / digest[:2] / f"{digest}.blob"
    assert blob.is_file()
    blob.write_bytes(b"not-the-original-bytes")

    transport = IpfsProofArtifactTransport(
        local_store=store,
        ipfs_get=lambda _cid: data,
    )
    result = transport.fetch_public_artifact(ref, prefer_local=True)
    assert result.disposition is TransportDisposition.AMBIGUOUS
    assert result.reason is TransportReason.BACKEND_AMBIGUOUS
    assert result.ambiguity is not None
    assert result.ambiguity.local_ok is False
    assert result.ambiguity.remote_ok is True
    assert result.data == data
    assert len(transport.ambiguities) >= 1
    # Ambiguous results are never truthy success.
    assert not result.hit
    assert not bool(result)


def test_timeout_on_get_is_typed_error_not_success() -> None:
    data = _payload(b"timeout")
    cid = content_cid_for_bytes(data)
    ref = ArtifactReference(cid=cid, kind=ArtifactKind.CHECKPOINT_SEAL)

    def slow_get(_cid: str) -> bytes:
        raise TimeoutError("ipfs get timed out")

    transport = IpfsProofArtifactTransport(ipfs_get=slow_get, timeout_seconds=1.0)
    result = transport.fetch_public_artifact(ref)
    assert not result.hit
    assert result.disposition is TransportDisposition.ERROR
    assert result.reason is TransportReason.TIMEOUT


def test_timeout_after_response_is_ambiguous() -> None:
    data = _payload(b"late")
    cid = content_cid_for_bytes(data)
    ref = ArtifactReference(cid=cid, kind=ArtifactKind.DELTA_SEAL)
    ticks = iter([0.0, 100.0])

    transport = IpfsProofArtifactTransport(
        ipfs_get=lambda _cid: data,
        timeout_seconds=1.0,
        clock=lambda: next(ticks),
    )
    result = transport.fetch_public_artifact(ref)
    assert result.disposition is TransportDisposition.AMBIGUOUS
    assert result.reason is TransportReason.BACKEND_AMBIGUOUS
    assert result.ambiguity is not None
    assert result.ambiguity.reason is TransportReason.TIMEOUT
    assert transport.ambiguities[-1].to_dict()["reason"] == "timeout"


def test_ipfs_error_is_typed_and_never_raises(tmp_path: Path) -> None:
    store = _local(tmp_path)
    data = _payload(b"ipfs-error")
    ref = _admit(store, data)

    def boom(_cid: str) -> bytes:
        raise RuntimeError("daemon unavailable")

    transport = IpfsProofArtifactTransport(local_store=store, ipfs_get=boom)
    result = transport.fetch_public_artifact(ref, prefer_local=False)
    assert not result.hit
    assert result.reason is TransportReason.IPFS_ERROR
    assert result.local_reconciled is False or result.diagnostics.get("local_ok") is None
    # Local path still works.
    assert transport.reconcile_local(ref).data == data


def test_malformed_remote_payload_fails_closed() -> None:
    data = _payload(b"malformed")
    cid = content_cid_for_bytes(data)
    ref = ArtifactReference(cid=cid, kind=ArtifactKind.INVALIDATION_RECORD)
    transport = IpfsProofArtifactTransport(
        ipfs_get=lambda _cid: {"unexpected": 123}
    )
    result = transport.fetch_public_artifact(ref)
    assert not result.hit
    assert result.reason is TransportReason.IPFS_RESPONSE_INVALID


# ---------------------------------------------------------------------------
# All public kinds + identity checks
# ---------------------------------------------------------------------------


def test_all_public_kinds_can_be_replicated_and_fetched() -> None:
    for kind in ArtifactKind:
        data = _payload(kind.value.encode("ascii"))
        cid = content_cid_for_bytes(data)
        backend: dict[str, bytes] = {}

        def put(payload: bytes, _backend: dict[str, bytes] = backend) -> dict[str, str]:
            identity = content_cid_for_bytes(payload)
            _backend[identity] = payload
            return {"Hash": identity}

        def get(requested: str, _backend: dict[str, bytes] = backend) -> bytes:
            return _backend[requested]

        transport = IpfsProofArtifactTransport(ipfs_put=put, ipfs_get=get)
        put_result = transport.replicate_public_artifact(kind, data)
        assert put_result.succeeded, kind
        fetch = transport.fetch_public_artifact(
            ArtifactReference(cid=cid, kind=kind, byte_length=len(data))
        )
        assert fetch.hit and fetch.data == data
        assert verify_content_identity(cid, fetch.data)


def test_claimed_cid_mismatch_on_replicate_fails_closed() -> None:
    data = _payload(b"claimed-bad")
    wrong = content_cid_for_bytes(b"nope")
    transport = IpfsProofArtifactTransport(
        ipfs_put=lambda payload: {"Hash": content_cid_for_bytes(payload)}
    )
    result = transport.replicate_public_artifact(
        ArtifactKind.PROOF_OBJECT, data, claimed_cid=wrong
    )
    assert not result.succeeded
    assert result.reason is TransportReason.CID_MISMATCH


def test_reference_role_remains_admitted_after_transport(tmp_path: Path) -> None:
    store = _local(tmp_path)
    data = _payload(b"role")
    ref = _admit(store, data)
    transport = IpfsProofArtifactTransport(
        local_store=store,
        ipfs_put=lambda payload: {"cid": content_cid_for_bytes(payload)},
    )
    result = transport.replicate_public_artifact(reference=ref)
    assert result.reference is not None
    assert result.reference.role is ArtifactRole.ADMITTED


def test_clear_ambiguities() -> None:
    transport = IpfsProofArtifactTransport(
        ipfs_put=lambda _payload: {"status": "ok"},
    )
    data = _payload(b"clear")
    transport.replicate_public_artifact(ArtifactKind.PROOF_OBJECT, data)
    assert transport.ambiguities
    transport.clear_ambiguities()
    assert transport.ambiguities == ()


def test_result_to_dict_is_bounded_and_json_friendly(tmp_path: Path) -> None:
    store = _local(tmp_path)
    data = _payload(b"dict")
    ref = _admit(store, data)
    transport = IpfsProofArtifactTransport(
        local_store=store,
        ipfs_put=lambda payload: {"Hash": content_cid_for_bytes(payload)},
    )
    put = transport.replicate_public_artifact(reference=ref)
    payload = put.to_dict()
    assert payload["disposition"] == "ok"
    assert payload["ipfs_stored"] is True
    assert payload["reference"]["cid"] == ref.cid
    assert payload["ambiguity"] is None

    fetch = transport.fetch_public_artifact(ref)
    fetch_payload = fetch.to_dict()
    assert fetch_payload["disposition"] == "hit"
    assert fetch_payload["has_data"] is True
    assert "data" not in fetch_payload  # exact bytes not dumped into diagnostics
